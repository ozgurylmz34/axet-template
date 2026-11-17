# -*- coding: utf-8 -*-
"""Validator'ların TEK ad grameri (`utils/ad_politikasi`) + kapsam boşlukları + tablo tip kıyası — hedefli testler.

Sözleşme (kaynak çekirdek fixture'ları validator_ad_grameri · q405_kapsam_bosluklari · cds_curr_referans_tipi ·
#408 tablo tip kıyası'ndan aXet düzenine çevrildi; validator'lar ALT SÜREÇLE, AĞSIZ koşar):
  · Ad çözülemezse (`/AB/X` — ad-alanı 3-8 karakter değil) validator "kapsam dışı / temiz" DEMEZ:
    `AXET-GATE-STATUS … status=SKIPPED measured=false reason=ad-cozulemedi`.
  · Bildirilmemiş namespace'teki katman adı ⇒ `reason=namespace-kayitsiz` (müşterinin mi SAP'nin mi bilinmez).
  · Bildirilmiş namespace ve Y öneki de katman kuralına girer (eskiden yalnız Z).
  · abapGit BDEF dosyası `X.bdef.asbdef` da BDEF sayılır; namespace'li ad referansı `\\b` değil ad sınırıyla aranır.
  · Tablo ALTER tip kıyası fiziksel tiple yapılır: daralma/tür BLOCKER, genişleme WARNING, aynı tip INFO.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import _helpers as H

sys.dont_write_bytecode = True
VAL = H.SCRIPTS / "sapadt" / "lib" / "validators"
LIB = H.SCRIPTS / "sapadt" / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))


def _modul(ad: str):
    spec = importlib.util.spec_from_file_location(f"_t_{ad}", VAL / f"{ad}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _durum(cikti: str) -> str:
    """Son AXET-GATE-STATUS satırının `status=… measured=… reason=…` kısmı ('' = beyan yok)."""
    satirlar = [s for s in cikti.splitlines() if s.startswith("AXET-GATE-STATUS:")]
    return satirlar[-1].split(" ", 2)[2] if satirlar else ""


class _Proje(unittest.TestCase):
    """Geçici proje kökü: `.conn_adt` (sahte, ağsız) + `sap-project.json` (`/NSPC/` bildirili)."""

    NS = ["/NSPC/"]

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="axet_valad_")
        self.kok = Path(self._tmp.name).resolve()
        (self.kok / ".conn_adt").write_text(f"ADT_SAP_URL={H.SAHTE_URL}\n", encoding="utf-8")
        (self.kok / "sap-project.json").write_text(
            json.dumps({**H.SAP_PROJECT_OK, "customer_namespaces": self.NS}), encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def kos(self, validator: str, dosya: str, metin: str, *ek: str, alt: str = "") -> tuple[int, str]:
        hedef = self.kok / alt if alt else self.kok
        hedef.mkdir(parents=True, exist_ok=True)
        p = hedef / dosya
        p.write_text(metin, encoding="utf-8")
        env = dict(os.environ, PYTHONIOENCODING="utf-8", AXET_SAP_PROJECT_DIR=str(self.kok))
        r = subprocess.run([sys.executable, str(VAL / f"{validator}.py"), str(p), *ek], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", cwd=str(self.kok), env=env, timeout=120)
        return r.returncode, (r.stdout or "") + "\n" + (r.stderr or "")


class RapReadonly(_Proje):
    V = "check_rap_readonly_consumption"

    def test_cozulemeyen_entity_adi_olculemedi(self):
        rc, o = self.kos(self.V, "x.asddls", "define view entity /AB/SD001_I_X as select from mara { key matnr }")
        self.assertEqual(rc, 0, o)
        self.assertIn("status=SKIPPED measured=false reason=ad-cozulemedi", _durum(o), o)
        self.assertNotIn("kapsam dışı", o)
        H.kaydet("RRC `/AB/` entity", "SKIPPED ad-cozulemedi", _durum(o), True)

    def test_katman_ihlali_ad_alani_bazinda(self):
        for kaynak, bek_rc, bek_durum in (("ZSD001_C_Y", 1, ""), ("YSD001_C_Y", 1, ""), ("/NSPC/SD001_C_Y", 1, ""),
                                          ("/ABC/SD001_C_Y", 0, "reason=namespace-kayitsiz"),
                                          ("ZSD001_I_Y", 0, "status=OK"), ("MARA", 0, "")):
            with self.subTest(kaynak=kaynak):
                rc, o = self.kos(self.V, "x.asddls",
                                 f"define view entity ZSD001_I_X as select from {kaynak} {{ key a }}")
                self.assertEqual(rc, bek_rc, o)
                if bek_rc:
                    self.assertIn("[Rule A]", o)
                if bek_durum and bek_durum != "status=OK":
                    self.assertIn(bek_durum, _durum(o), o)
                if kaynak in ("ZSD001_I_Y", "MARA"):
                    self.assertTrue(o.lstrip().startswith("OK"), o)
        H.kaydet("RRC Rule A Z/Y/bildirilmiş NS ihlal · bildirimsiz NS ÖLÇÜLEMEDİ", "6 vaka", "eşit", True)

    def _projeksiyon(self, entity: str, bdef: str | None, bdef_dosya: str = "zsd001_c_x.bdef.asbdef"):
        pkg = self.kok / "src" / "pkg"
        pkg.mkdir(parents=True, exist_ok=True)
        (pkg / ".rules.md").write_text("# paket\n", encoding="utf-8")
        if bdef is not None:
            (pkg / bdef_dosya).write_text(bdef, encoding="utf-8")
        return self.kos(self.V, "x.asddls",
                        f"define root view entity {entity} provider contract transactional_query "
                        f"as projection on ZSD001_I_X {{ key a }}", alt="src/pkg")

    def test_asbdef_bdef_sayilir(self):
        rc, o = self._projeksiyon("ZSD001_C_X", "projection;\ndefine behavior for ZSD001_C_X { use update; }")
        self.assertEqual(rc, 0, o)
        rc2, o2 = self._projeksiyon("ZSD001_C_Z", None)
        self.assertEqual(rc2, 1, o2)
        self.assertIn("[Rule B]", o2)
        H.kaydet("RRC Rule B `.bdef.asbdef` BDEF sayılır · BDEF'siz projeksiyon BLOCKER", "0/1", f"{rc}/{rc2}", True)

    def test_namespace_bdef_referansi_ad_siniriyla(self):
        rc, o = self._projeksiyon("/NSPC/SD001_C_X",
                                  "projection;\ndefine behavior for /NSPC/SD001_C_X { use update; }",
                                  bdef_dosya="#nspc#sd001_c_x.bdef.asbdef")
        self.assertEqual(rc, 0, o)
        # Önek eşleşmesi referans SAYILMAZ (`/NSPC/SD001_C_X` ⊂ `/NSPC/SD001_C_XY`)
        rc2, o2 = self._projeksiyon("/NSPC/SD001_C_X",
                                    "projection;\ndefine behavior for /NSPC/SD001_C_XY { use update; }",
                                    bdef_dosya="#nspc#sd001_c_x.bdef.asbdef")
        self.assertEqual(rc2, 1, o2)
        H.kaydet("RRC namespace'li BDEF referansı · önek eşleşmesi referans değil", "0/1", f"{rc}/{rc2}", True)


class ReuseGate(_Proje):
    V = "check_reuse_gate"

    def test_cozulemeyen_ad_olculemedi(self):
        rc, o = self.kos(self.V, "x.asddls", "define view entity /AB/X as select from mara { key matnr }")
        self.assertEqual(rc, 0, o)
        self.assertIn("status=SKIPPED measured=false reason=ad-cozulemedi", _durum(o), o)

    def test_namespace_adi_envantere_girer(self):
        (self.kok / "eski.asddls").write_text("define view entity /NSPC/SD001_I_X as select from mara { key a }",
                                              encoding="utf-8")
        rc, o = self.kos(self.V, "yeni.asddls", "define view entity /nspc/sd001_i_x as select from mara { key a }",
                         alt="alt")
        self.assertEqual(rc, 0, o)
        self.assertIn("status=FINDING measured=true reason=name_defined_locally", _durum(o), o)
        H.kaydet("REUSE namespace'li ad yerel duplicate olarak bulunur", "FINDING", _durum(o), True)


class AktifSurumVeYapi(_Proje):
    def test_active_version_bildirimsiz_namespace(self):
        for ad, neden in (("/ABC/SD001_S_X", "namespace-kayitsiz"), ("/AB/X", "ad-cozulemedi")):
            with self.subTest(ad=ad):
                rc, o = self.kos("check_sap_active_version", "x.asddls",
                                 f"define structure {ad} {{ a : abap.char(1); }}")
                self.assertEqual(rc, 0, o)
                self.assertIn(f"status=SKIPPED measured=false reason={neden}", _durum(o), o)

    def test_struct_consistency_cozulemeyen_ad_ve_alan(self):
        rc, o = self.kos("check_sap_struct_consistency", "x.asddls", "define structure /AB/X { a : abap.char(1); }")
        self.assertIn("reason=ad-cozulemedi", _durum(o), o)
        rc2, o2 = self.kos("check_sap_struct_consistency", "y.asddls",
                           "define structure ZSD001_S_X {\n  /ab/fld : abap.char(1);\n}")
        self.assertEqual((rc, rc2), (0, 0), o + o2)
        self.assertIn("reason=ad-cozulemedi", _durum(o2), o2)

    def test_table_field_drop_cozulemeyen_ad_ve_alan(self):
        rc, o = self.kos("check_table_field_drop", "x.asddls", "define table /AB/T {\n  key a : abap.char(1);\n}")
        self.assertIn("reason=ad-cozulemedi", _durum(o), o)
        self.assertNotIn("measured=true", _durum(o))
        rc2, o2 = self.kos("check_table_field_drop", "y.asddls",
                           "define table ZSD001_T_X {\n  key a : abap.char(1);\n  /ab/f : abap.char(2);\n}")
        self.assertEqual((rc, rc2), (0, 0), o + o2)
        self.assertIn("reason=ad-cozulemedi", _durum(o2), o2)


class TabloTipKiyasi(unittest.TestCase):
    """#408: tip metni TAM alınır ve fiziksel tiple kıyaslanır (eski hâl her yerleşik tipi `abap` sayıyordu)."""

    @classmethod
    def setUpClass(cls):
        cls.m = _modul("check_table_field_drop")

    def test_alan_haritasi_tam_tip(self):
        h = self.m.parse_fields("define table ztab {\n  key id : abap.int4;\n  note : abap.char( 100 );\n"
                             "  amt : abap.dec(15,3);\n  dt : zsd001_e_x;\n}")
        self.assertEqual(h, {"id": "abap.int4", "note": "abap.char(100)", "amt": "abap.dec(15,3)",
                             "dt": "zsd001_e_x"})

    def test_fiziksel_karsilastirma(self):
        y, k = self.m.yerlesik_fiziksel, self.m.tip_karsilastir
        for eski, yeni, bek in (("abap.int4", "abap.int2", "tur"), ("abap.char(100)", "abap.char(10)", "daralma"),
                                ("abap.char(10)", "abap.char(40)", "genisleme"),
                                ("abap.dec(15,3)", "abap.dec(15,2)", "daralma"),
                                ("abap.dec(15,2)", "abap.dec(17,3)", "genisleme"),
                                ("abap.char(10)", "abap.numc(10)", "tur"), ("abap.int4", "abap.int4", "ayni"),
                                ("abap.string", "abap.string", "ayni")):
            with self.subTest(eski=eski, yeni=yeni):
                self.assertEqual(k(y(eski), y(yeni)), bek)
        H.kaydet("TFD fiziksel tip kıyası (tür/daralma/genişleme/aynı)", "8 vaka", "eşit", True)

    def test_dtel_xml_eksik_oge_cozulemez(self):
        f = self.m.dtel_fiziksel
        self.assertEqual(f("<dtel:dataType>CHAR</dtel:dataType><dtel:dataTypeLength>000040</dtel:dataTypeLength>")[0],
                         ("CHAR", 40, 0))
        self.assertEqual(f("<dtel:dataType>CHAR</dtel:dataType>"), (None, "dtel-uzunluk-yok"))
        self.assertEqual(f("<dtel:dataType>DEC</dtel:dataType><dtel:dataTypeLength>15</dtel:dataTypeLength>"),
                         (None, "dtel-ondalik-yok"))
        self.assertEqual(f("<x/>"), (None, "dtel-veri-tipi-yok"))
        self.assertEqual(f("<dtel:dataType>INT4</dtel:dataType>")[0], ("INT4", 0, 0))


class GramerGerilemeBekcisi(unittest.TestCase):
    """Validator kendi ad desenini YAZMAZ: `define …` tanımından ad yakalayan `(\\w+)` geri gelirse kırmızı.

    `\\w+` `/` eşlemez ⇒ namespace'li ad "tanım yok / kapsam dışı" sayılır (kaynak #402 K1 sınıfı). Bakılan: bu
    dizindeki validator'larda aynı satırda `define` + `(\\w+)` geçen regex. BAKILMAYAN: birden çok satıra bölünmüş
    desen · `define` dışı ad konumları (from/join kaynak adı — onlar ayrı testlerle ölçülür)."""

    def test_define_ad_yakalamasi_tek_gramerden(self):
        ihlal = []
        for p in sorted(VAL.glob("*.py")):
            for no, satir in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                # yalnız ham dize (regex) satırı — docstring'deki tarihçe anlatımı sayılmaz
                if ("define" in satir and "(\\w+)" in satir and ("r'" in satir or 'r"' in satir)
                        and not satir.lstrip().startswith("#")):
                    ihlal.append(f"{p.name}:{no}")
        self.assertEqual(ihlal, [])
        H.kaydet("Validator `define … (\\w+)` ad yakalaması yok", "0", str(len(ihlal)), not ihlal)


class KapsamVeSozluk(unittest.TestCase):
    def test_run_review_dcl_beyani(self):
        m = _modul("run_review")
        satir = m.olculmeyen_tur_satirlari("zsd001_dcl_x.dcls.asdcls")
        self.assertTrue(any("DCL" in s and "İNCELENEN DOSYA BU TÜRDE" in s for s in satir), satir)
        satir2 = m.olculmeyen_tur_satirlari("zsd001_i_x.ddls.asddls")
        self.assertTrue(satir2 and all("ÖLÇÜLMEDİ" in s and "İNCELENEN" not in s for s in satir2), satir2)

    def test_para_birimi_sozlugu(self):
        from utils import ddic_semantics as ds
        self.assertTrue({"konwa", "konws"} <= ds.CUKY_DTELS)
        self.assertTrue({"kmein", "konms"} <= ds.UNIT_DTELS)
        self.assertNotIn("curr", ds.CURR_DTELS)
        self.assertEqual(ds.classify_unit_kind("zsd001_e_rate", "konwa"), ds.UNIT_KIND_CURRENCY)


class CurrReferansTipi(_Proje):
    """C-TBL-CUR: `konwa` (CUKY) tipli para birimi alanına başvuran tutar yanlış BLOCKER almaz (kaynak #399)."""

    def _tablo(self, govde: str) -> str:
        return ("@EndUserText.label : 'Test'\n@AbapCatalog.tableCategory : #TRANSPARENT\n"
                f"define table zsd001_t_test {{\n  key mandt : mandt not null;\n{govde}}}\n")

    def test_konwa_referansi_temiz_marker_eksigi_blocker(self):
        rc, o = self.kos("check_cds_currency_reference", "r1.tabl.ddl", self._tablo(
            "  @Semantics.amount.currencyCode : 'zsd001_t_test.curr'\n  rate : kbetr;\n"
            "  @Semantics.currencyCode : true\n  curr : konwa;\n"))
        self.assertEqual(rc, 0, o)
        self.assertNotIn("[BLOCKER]", o)
        rc2, o2 = self.kos("check_cds_currency_reference", "r5.tabl.ddl", self._tablo(
            "  @Semantics.amount.currencyCode : 'zsd001_t_test.curr'\n  rate : kbetr;\n  curr : konwa;\n"))
        self.assertEqual(rc2, 1, o2)
        self.assertIn("[BLOCKER]", o2)
        H.kaydet("CUR konwa referansı temiz · marker eksik BLOCKER korunur", "0/1", f"{rc}/{rc2}", True)


if __name__ == "__main__":
    unittest.main()
