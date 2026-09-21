# -*- coding: utf-8 -*-
"""mock_veri.py: OData V2/V4 $metadata → fe-mockserver JSON verisi.

Kapsam: V2 (başlık+kalem+VH, Association/ReferentialConstraint, ValueList) ve V4 RAP draft
(başlık+kalem, NavigationProperty/ReferentialConstraint, Common.ValueList, ada göre VH) örnekleri;
determinizm, MaxLength/Precision/Scale sınırı, FK ve toplam tutarlılığı, draft alanları, --zorla,
bozuk girdide anlaşılır hata + çıkış kodu. Ağa, SAP'ye, tarayıcıya bağlanmaz.
Tek başına koşulabilir: python -m unittest test_mock_veri (tests/ klasöründen) ya da
python tests/test_mock_veri.py.
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from decimal import Decimal

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
SCRIPTS = os.path.join(SKILL, "scripts")
SAMPLES = os.path.join(HERE, "samples")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import mock_veri  # noqa: E402

V2 = os.path.join(SAMPLES, "v2_siparis_metadata.xml")
V4 = os.path.join(SAMPLES, "v4_rap_draft_metadata.xml")
V2_RAP = os.path.join(SAMPLES, "v2_rap_siparis_metadata.xml")          # birincil: RAP SRVB V2, draft'sız
V2_RAP_DRAFT = os.path.join(SAMPLES, "v2_rap_draft_metadata.xml")      # ikincil: RAP SRVB V2, draft'lı
SCRIPT = os.path.join(SCRIPTS, "mock_veri.py")
GUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def calistir(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = mock_veri.main(argv)
        except SystemExit as exc:
            rc = exc.code
    return rc, out.getvalue(), err.getvalue()


def oku(klasor, ad):
    with open(os.path.join(klasor, ad + ".json"), "rb") as fh:
        ham = fh.read()
    return ham, json.loads(ham.decode("utf-8"))


def ondalik_basamak(deger):
    d = Decimal(str(deger))
    return max(0, -d.as_tuple().exponent)


class _Temel(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="mock_veri_")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def uret(self, metadata, *ek, cikti=None):
        cikti = cikti or os.path.join(self.tmp, "data")
        rc, out, err = calistir(["--metadata", metadata, "--cikti", cikti, *ek])
        self.assertEqual(0, rc, "çıkış %r\nstdout:\n%s\nstderr:\n%s" % (rc, out, err))
        return cikti, out


class V2UretimTest(_Temel):
    def setUp(self):
        super().setUp()
        self.cikti, self.out = self.uret(V2, "--adet", "4", "--alt-adet", "3", "--tohum", "7")
        _, self.bas = oku(self.cikti, "SalesOrderSet")
        _, self.kal = oku(self.cikti, "SalesOrderItemSet")
        _, self.vh = oku(self.cikti, "CustomerVHSet")

    def test_her_entityset_icin_dosya_vh_dahil(self):
        self.assertEqual(sorted(["SalesOrderSet.json", "SalesOrderItemSet.json", "CustomerVHSet.json"]),
                         sorted(os.listdir(self.cikti)))
        self.assertEqual(4, len(self.bas))
        self.assertEqual(4, len(self.vh))
        self.assertEqual(12, len(self.kal))

    def test_utf8_bom_yok_ve_turkce_karakter_kacissiz(self):
        ham, _ = oku(self.cikti, "SalesOrderSet")
        self.assertFalse(ham.startswith(b"\xef\xbb\xbf"))
        ham.decode("utf-8")
        self.assertNotIn(b"\\u0", ham)

    def test_anahtarlar_tekil(self):
        self.assertEqual(len(self.bas), len({r["SalesOrder"] for r in self.bas}))
        self.assertEqual(len(self.kal), len({(r["SalesOrder"], r["ItemNo"]) for r in self.kal}))
        self.assertEqual(len(self.vh), len({r["Customer"] for r in self.vh}))

    def test_fk_kalem_basliga_bagli(self):
        basliklar = {r["SalesOrder"] for r in self.bas}
        for r in self.kal:
            self.assertIn(r["SalesOrder"], basliklar)
        self.assertEqual(basliklar, {r["SalesOrder"] for r in self.kal}, "her başlığın kalemi olmalı")

    def test_toplam_kalem_toplamina_esit(self):
        for b in self.bas:
            toplam = sum((Decimal(str(k["NetAmount"])) for k in self.kal if k["SalesOrder"] == b["SalesOrder"]),
                         Decimal("0"))
            self.assertEqual(toplam, Decimal(str(b["TotalAmount"])), b["SalesOrder"])

    def test_maxlength_ve_precision_scale_asilmaz(self):
        sinir = {"SalesOrder": 10, "Customer": 10, "CustomerName": 20, "City": 12, "Phone": 16, "Currency": 5,
                 "Status": 1}
        for r in self.bas:
            for alan, ml in sinir.items():
                self.assertLessEqual(len(r[alan]), ml, "%s=%r" % (alan, r[alan]))
            self.assertLess(abs(Decimal(str(r["TotalAmount"]))), Decimal("100000"))  # P7 S2
            self.assertLessEqual(ondalik_basamak(r["TotalAmount"]), 2)
        for r in self.kal:
            self.assertLessEqual(len(r["ItemNo"]), 6)
            self.assertLessEqual(len(r["MaterialName"]), 15)
            self.assertLessEqual(len(r["Unit"]), 3)
            self.assertLessEqual(ondalik_basamak(r["Quantity"]), 3)
            self.assertLessEqual(ondalik_basamak(r["NetAmount"]), 2)
            self.assertLess(abs(Decimal(str(r["NetAmount"]))), Decimal("100000"))

    def test_deger_yardimi_ile_tutarli(self):
        musteriler = {r["Customer"] for r in self.vh}
        for r in self.bas:
            self.assertIn(r["Customer"], musteriler)

    def test_anlamli_turkce_degerler(self):
        for r in self.bas:
            self.assertEqual("TRY", r["Currency"])
            self.assertIn(r["City"], mock_veri.SEHIRLER)
            self.assertRegex(r["OrderDate"], r"^/Date\(\d+\)/$")
            self.assertRegex(r["CreatedAt"], r"^/Date\(\d+\)/$")
            self.assertIsInstance(r["Urgent"], bool)
        for r in self.kal:
            self.assertIn(r["Unit"], ("ADT", "KG"))
            self.assertEqual(Decimal(str(r["Quantity"])), Decimal(str(r["Quantity"])).to_integral_value())
        for r in self.vh:
            self.assertTrue(any(r["CustomerName"].startswith(f) for f in mock_veri.FIRMA_ADLARI), r["CustomerName"])

    def test_kvkk_telefon_belirgin_sahte(self):
        for r in self.bas:
            self.assertRegex(r["Phone"], r"^0+\d{0,4}$", "telefon belirgin sahte olmalı")

    def test_kapsam_beyani(self):
        self.assertIn("KAPSAM (SCOPE)", self.out)
        self.assertIn("ReleaseOrder", self.out)          # function import bakılmadı
        self.assertIn("CustomerVHSet", self.out)          # VH listesi
        self.assertIn("Edm.Binary", self.out)             # tanınmayan tip
        self.assertIn("SalesOrderSet.TotalAmount", self.out)  # toplam kuralı


class V2RapTaslaksizTest(_Temel):
    """BİRİNCİL YOL: freestyle SAPUI5 + RAP SRVB OData V2, draft'sız başlık+kalem+VH+toplam."""

    def setUp(self):
        super().setUp()
        self.cikti, self.out = self.uret(V2_RAP, "--adet", "4", "--alt-adet", "3", "--tohum", "11")
        _, self.bas = oku(self.cikti, "Order")
        _, self.kal = oku(self.cikti, "Item")
        _, self.vh = oku(self.cikti, "ZBC000_I_CustomerVH")
        _, self.durum = oku(self.cikti, "ZBC000_I_StatusVH")

    def test_dosyalar_ve_sayilar(self):
        self.assertEqual(sorted(["Order.json", "Item.json", "ZBC000_I_CustomerVH.json", "ZBC000_I_StatusVH.json"]),
                         sorted(os.listdir(self.cikti)))
        self.assertEqual((4, 12, 4, 4), (len(self.bas), len(self.kal), len(self.vh), len(self.durum)))

    def test_draft_alani_yok(self):
        for r in self.bas + self.kal:
            for alan in ("IsActiveEntity", "HasActiveEntity", "HasDraftEntity", "DraftAdministrativeData"):
                self.assertNotIn(alan, r)

    def test_fk_ve_anahtar(self):
        basliklar = {r["OrderUUID"] for r in self.bas}
        self.assertEqual(4, len(basliklar))
        for r in self.bas:
            self.assertRegex(r["OrderUUID"], GUID)
        self.assertEqual(basliklar, {r["OrderUUID"] for r in self.kal})
        self.assertEqual(12, len({r["ItemUUID"] for r in self.kal}))

    def test_toplam(self):
        for b in self.bas:
            toplam = sum((Decimal(str(k["NetAmount"])) for k in self.kal if k["OrderUUID"] == b["OrderUUID"]),
                         Decimal("0"))
            self.assertEqual(toplam, Decimal(str(b["TotalAmount"])))

    def test_vh_ve_metin_tutarliligi(self):
        ad = {r["CustomerID"]: r["CustomerName"] for r in self.vh}
        for r in self.bas:
            self.assertIn(r["CustomerID"], ad)
            self.assertEqual(ad[r["CustomerID"]], r["CustomerName"], "müşteri adı seçilen VH kaydından gelmeli")
            self.assertIn(r["OverallStatus"], {d["Status"] for d in self.durum})
        eslesme = {d["Status"]: d["StatusText"] for d in self.durum}
        self.assertEqual({"A": "Açık", "O": "Onaylandı", "T": "Tamamlandı", "I": "İptal"}, eslesme)

    def test_kalem_pozisyonu_ve_tarih(self):
        for r in self.kal:
            self.assertIn(r["ItemPosition"], ("0010", "0020", "0030"))
            self.assertRegex(r["DeliveryDate"], r"^/Date\(\d+\)/$")
        for r in self.bas:
            ms = int(re.match(r"^/Date\((\d+)\)/$", r["OrderDate"]).group(1))
            self.assertEqual(0, ms % 86400000, "display-format=Date → gece yarısı UTC")
            self.assertLessEqual(len(r["CreatedBy"]), 12)

    def test_kapsam(self):
        self.assertIn("releaseOrder", self.out)
        self.assertIn("Item(OrderUUID) → Order(OrderUUID) [kalem]", self.out)

    def test_referential_constraint_yoksa_ad_eslesmesiyle_cikarim(self):
        with open(V2_RAP, encoding="utf-8") as fh:
            metin = fh.read()
        metin, n = re.subn(r"(<Association Name=\"assoc_7A1F0C2E\".*?)<ReferentialConstraint>.*?</ReferentialConstraint>",
                           r"\1", metin, flags=re.S)
        self.assertEqual(1, n)
        meta = os.path.join(self.tmp, "kisitsiz.xml")
        with open(meta, "w", encoding="utf-8") as fh:
            fh.write(metin)
        cikti, out = self.uret(meta, "--adet", "2", "--alt-adet", "2", cikti=os.path.join(self.tmp, "k"))
        self.assertIn("ÇIKARILDI", out)
        _, bas = oku(cikti, "Order")
        _, kal = oku(cikti, "Item")
        self.assertEqual({r["OrderUUID"] for r in bas}, {r["OrderUUID"] for r in kal})
        # ad eşleşmesi yoksa FK uydurulmaz, açıkça raporlanır
        metin2 = metin.replace('<Property Name="OrderUUID" Type="Edm.Guid" sap:label="Sipariş UUID"/>',
                               '<Property Name="ParentUUID" Type="Edm.Guid" sap:label="Sipariş UUID"/>')
        self.assertNotEqual(metin, metin2)
        with open(meta, "w", encoding="utf-8") as fh:
            fh.write(metin2)
        _, out2 = self.uret(meta, cikti=os.path.join(self.tmp, "k2"))
        self.assertIn("FK çıkarılamadı", out2)


class V2RapTaslakliTest(_Temel):
    """İKİNCİL: RAP V2 draft'lı servis — yalnız aktif kayıt; I_DraftAdministrativeData üretilmez."""

    def setUp(self):
        super().setUp()
        self.cikti, self.out = self.uret(V2_RAP_DRAFT, "--adet", "3", "--alt-adet", "2")
        _, self.bas = oku(self.cikti, "Order")
        _, self.kal = oku(self.cikti, "Item")

    def test_aktif_kayit_ve_draft_yonetimi_yok(self):
        self.assertFalse(os.path.exists(os.path.join(self.cikti, "I_DraftAdministrativeData.json")))
        self.assertIn("I_DraftAdministrativeData", self.out)
        for r in self.bas + self.kal:
            self.assertEqual((True, False, False), (r["IsActiveEntity"], r["HasActiveEntity"], r["HasDraftEntity"]))
            self.assertNotIn("DraftAdministrativeData", r)
            self.assertNotIn("SiblingEntity", r)

    def test_fk_toplam_ve_bilesik_anahtar(self):
        self.assertEqual(6, len({(r["ItemUUID"], r["IsActiveEntity"]) for r in self.kal}))
        for b in self.bas:
            kalemler = [k for k in self.kal if k["OrderUUID"] == b["OrderUUID"]]
            self.assertEqual(2, len(kalemler))
            self.assertEqual(sum((Decimal(str(k["NetAmount"])) for k in kalemler), Decimal("0")),
                             Decimal(str(b["TotalAmount"])))

    def test_kapsam_draft_eylemleri(self):
        for ad in ("OrderActivate", "OrderEdit", "OrderPrepare", "OrderDiscard"):
            self.assertIn(ad, self.out)


class V4DraftUretimTest(_Temel):
    def setUp(self):
        super().setUp()
        self.cikti, self.out = self.uret(V4, "--adet", "3", "--alt-adet", "2", "--tohum", "7")
        _, self.bas = oku(self.cikti, "Order")
        _, self.kal = oku(self.cikti, "Item")
        _, self.vh = oku(self.cikti, "Customer")
        _, self.durum_vh = oku(self.cikti, "ZBC000_I_StatusVH")

    def test_vh_setleri_uretildi(self):
        self.assertEqual(3, len(self.vh))
        self.assertEqual(3, len(self.durum_vh))
        self.assertEqual(6, len(self.kal))
        self.assertIn("ZBC000_I_StatusVH", self.out)

    def test_draft_aktif_kayit_varsayilanlari(self):
        for r in self.bas + self.kal:
            self.assertIs(True, r["IsActiveEntity"])
            self.assertIs(False, r["HasActiveEntity"])
            self.assertIs(False, r["HasDraftEntity"])
            self.assertNotIn("DraftAdministrativeData", r)
            self.assertNotIn("SiblingEntity", r)

    def test_guid_ve_tarih_bicimi(self):
        for r in self.bas:
            self.assertRegex(r["OrderUUID"], GUID)
            self.assertRegex(r["OrderDate"], r"^\d{4}-\d{2}-\d{2}$")
            self.assertRegex(r["LocalLastChangedAt"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
            self.assertNotIn("Attachment", r)  # Edm.Stream üretilmez
        self.assertIn("Edm.Stream", self.out)

    def test_fk_referential_constraint(self):
        basliklar = {r["OrderUUID"] for r in self.bas}
        for r in self.kal:
            self.assertIn(r["ParentUUID"], basliklar)
        self.assertEqual(len(self.kal), len({r["ItemUUID"] for r in self.kal}))

    def test_toplam_kalem_toplamina_esit(self):
        for b in self.bas:
            toplam = sum((Decimal(str(k["GrossAmount"])) for k in self.kal if k["ParentUUID"] == b["OrderUUID"]),
                         Decimal("0"))
            self.assertEqual(toplam, Decimal(str(b["GrossTotal"])))

    def test_value_list_ile_tutarli(self):
        musteriler = {r["CustomerID"] for r in self.vh}
        for r in self.bas:
            self.assertIn(r["CustomerID"], musteriler)

    def test_sinirlar(self):
        for r in self.bas:
            self.assertLessEqual(len(r["OrderID"]), 8)
            self.assertLessEqual(len(r["Description"]), 30)
            self.assertEqual(3, len(r["CurrencyCode"]))
            self.assertLessEqual(len(r["OverallStatus"]), 10)
            self.assertLessEqual(ondalik_basamak(r["GrossTotal"]), 2)
            self.assertLess(abs(Decimal(str(r["GrossTotal"]))), Decimal("10000000"))  # P9 S2
        for r in self.kal:
            self.assertIsInstance(r["Quantity"], int)
            self.assertIsInstance(r["ItemPosition"], int)
            self.assertLessEqual(len(r["ProductName"]), 20)

    def test_kapsam_action_bakilmadi(self):
        self.assertIn("releaseOrder", self.out)


class DavranisTest(_Temel):
    def test_ayni_tohum_bayt_bayt_ayni(self):
        a, _ = self.uret(V4, "--tohum", "42", cikti=os.path.join(self.tmp, "a"))
        b, _ = self.uret(V4, "--tohum", "42", cikti=os.path.join(self.tmp, "b"))
        c, _ = self.uret(V4, "--tohum", "43", cikti=os.path.join(self.tmp, "c"))
        for ad in ("Order", "Item", "Customer", "ZBC000_I_StatusVH"):
            self.assertEqual(oku(a, ad)[0], oku(b, ad)[0], ad)
        self.assertNotEqual(oku(a, "Order")[0], oku(c, "Order")[0])

    def test_zorla_olmadan_ezmez_zorla_ile_ezer(self):
        cikti, _ = self.uret(V2)
        yol = os.path.join(cikti, "SalesOrderSet.json")
        with open(yol, "w", encoding="utf-8") as fh:
            fh.write("[]")
        _, out = self.uret(V2, cikti=cikti)
        with open(yol, encoding="utf-8") as fh:
            self.assertEqual("[]", fh.read())
        self.assertIn("ATLANDI", out)
        self.assertIn("SalesOrderSet", out.split("ATLANDI", 1)[1])
        self.uret(V2, "--zorla", cikti=cikti)
        with open(yol, encoding="utf-8") as fh:
            self.assertNotEqual("[]", fh.read())

    def test_atlanan_ust_dosyanin_anahtarlari_fk_icin_kullanilir(self):
        cikti = os.path.join(self.tmp, "data")
        os.makedirs(cikti)
        with open(os.path.join(cikti, "SalesOrderSet.json"), "w", encoding="utf-8") as fh:
            json.dump([{"SalesOrder": "9000000001"}, {"SalesOrder": "9000000002"}], fh)
        _, out = self.uret(V2, "--alt-adet", "2", cikti=cikti)
        _, kal = oku(cikti, "SalesOrderItemSet")
        self.assertEqual({"9000000001", "9000000002"}, {r["SalesOrder"] for r in kal})
        self.assertIn("SalesOrderSet.TotalAmount: toplam uygulanamadı", out)

    def test_bozuk_xml_anlasilir_hata_ve_cikis_2(self):
        bozuk = os.path.join(self.tmp, "bozuk.xml")
        with open(bozuk, "w", encoding="utf-8") as fh:
            fh.write("<edmx:Edmx><kapanmayan>")
        r = subprocess.run([sys.executable, "-X", "utf8", SCRIPT, "--metadata", bozuk, "--cikti",
                            os.path.join(self.tmp, "x")], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=60)
        self.assertEqual(2, r.returncode, r.stderr)
        self.assertIn("HATA", r.stderr)
        self.assertIn("bozuk.xml", r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "x")))

    def test_edmx_olmayan_xml_ve_eksik_dosya_cikis_2(self):
        yanlis = os.path.join(self.tmp, "yanlis.xml")
        with open(yanlis, "w", encoding="utf-8") as fh:
            fh.write("<kok><a/></kok>")
        rc, _, err = calistir(["--metadata", yanlis, "--cikti", os.path.join(self.tmp, "y")])
        self.assertEqual(2, rc)
        self.assertIn("Edmx", err)
        rc, _, err = calistir(["--metadata", os.path.join(self.tmp, "yok.xml"), "--cikti", self.tmp])
        self.assertEqual(2, rc)
        self.assertIn("HATA", err)

    def test_kucuk_maxlength_anahtar_kapasitesi_asilmaz(self):
        meta = os.path.join(self.tmp, "kucuk.xml")
        with open(V2, encoding="utf-8") as fh:
            metin = fh.read()
        metin = metin.replace('Name="Customer" Type="Edm.String" Nullable="false" MaxLength="10"',
                              'Name="Customer" Type="Edm.String" Nullable="false" MaxLength="1"')
        with open(meta, "w", encoding="utf-8") as fh:
            fh.write(metin)
        cikti, out = self.uret(meta, "--adet", "50")
        _, vh = oku(cikti, "CustomerVHSet")
        anahtarlar = [r["Customer"] for r in vh]
        self.assertEqual(len(anahtarlar), len(set(anahtarlar)))
        self.assertTrue(all(len(a) <= 1 for a in anahtarlar))


if __name__ == "__main__":
    unittest.main()
