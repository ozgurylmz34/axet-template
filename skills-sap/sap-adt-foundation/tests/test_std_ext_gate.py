# -*- coding: utf-8 -*-
"""Z104 — Kesin Yasak A: Z adlı obje içinden STANDART objeyi genişletme (append / extend / annotate / BDEF extension).

Üç katman: tarayıcı (`sapadt/std_ext_scan.py`, saf) · yazma kapısı (`gate.check_std_extension`, adım 5) ·
araç içi ikinci katman (`tools/atom.py::adt_push_source`). Ağ yok; SAP'ye bağlanılmaz.

Kırmızı ölçüm (2026-09-24, taban f2b2839): aynı sentetik `check_write` çağrıları 6/6 `allowed=True` döndü.
Kontrol grubu: Z/Y ve /Z…/ hedefli genişletme, yorum/dize içindeki metin, BDEF tanımı → SERBEST.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _helpers as H

sys.dont_write_bytecode = True
if str(H.SCRIPTS) not in sys.path:
    sys.path.insert(0, str(H.SCRIPTS))

from sapadt.std_ext_scan import mesaj, tara, tara_tabl_xml  # noqa: E402

APPEND_VBAK = ("@EndUserText.label : 'Satış belgesi eki'\n@AbapCatalog.enhancement.category : #NOT_EXTENSIBLE\n"
               "extend type vbak with zzavbak {\n  zzfield : abap.char(10);\n}\n")
EXT_VIEW_ENTITY = "extend view entity I_SalesOrder with {\n  _Extension.zz_x as ZzX\n}\n"
ANNOTATE_ENTITY = "@Metadata.layer: #CUSTOMER\nannotate entity I_Product with {\n  @UI.hidden: true\n  Product;\n}\n"

# (ad, tip, kaynak, beklenen hedef, beklenen satır)
POZITIF = [
    ("a extend type vbak with zzavbak", "tabl", APPEND_VBAK, "VBAK", 3),
    ("a2 extend type (structure tipi)", "structure", "extend type bapiret2 with zzbapiret2 {\n  zz : abap.char(1);\n}", "BAPIRET2", 1),
    ("b extend view entity I_SalesOrder", "ddls", EXT_VIEW_ENTITY, "I_SALESORDER", 1),
    ("b2 extend view (DDIC tabanlı CDS)", "ddls",
     "@AbapCatalog.sqlViewAppendName: 'ZXV_SO'\nextend view I_SalesOrder with ZE_I_SO {\n  zz\n}", "I_SALESORDER", 2),
    ("b3 extend custom entity", "ddls", "extend custom entity I_CustomX with {\n  zz : abap.char(1);\n}", "I_CUSTOMX", 1),
    ("b4 extend abstract entity", "ddls", "extend abstract entity D_AbstractX with {\n  zz : abap.char(1);\n}", "D_ABSTRACTX", 1),
    ("c annotate entity I_Product", "ddlx", ANNOTATE_ENTITY, "I_PRODUCT", 2),
    ("c2 annotate view C_Product", "ddlx", "annotate view C_Product with {\n  @UI.hidden: true Product;\n}", "C_PRODUCT", 1),
    ("d1 BÜYÜK harf", "tabl", "EXTEND TYPE VBAK WITH ZZAVBAK {\n  ZZF : ABAP.CHAR(1);\n}", "VBAK", 1),
    ("d2 KaRıŞıK harf + satır bölünmesi", "ddls", "Extend\n  View\n    ENTITY\n  i_salesorder\n with {\n  a\n}", "I_SALESORDER", 1),
    ("d3 yorumdan SONRA gerçek ifade", "ddls",
     "// açıklama: extend view entity ZI_X with\nextend view entity I_SalesOrder with { a }", "I_SALESORDER", 2),
    ("d4 standart namespace /SCWM/", "ddls", "extend view entity /SCWM/I_Task with { a }", "/SCWM/I_TASK", 1),
    ("d5 tip bilinmiyor (None) → yine taranır", None, APPEND_VBAK, "VBAK", 3),
    ("j BDEF extension using interface I_SalesOrderTP", "bdef",
     "extension using interface I_SalesOrderTP\n  implementation in class zbp_ext_so unique;\n\n"
     "extend behavior for SalesOrder\n{\n  validation zz_check on save { create; }\n}", "I_SALESORDERTP", 1),
]

NEGATIF = [
    ("e1 yorumda extend type vbak", "tabl",
     "// extend type vbak with zzavbak\n/* extend view entity I_SalesOrder with {\n} */\n"
     "@EndUserText.label : 'x'\n@AbapCatalog.enhancement.category : #NOT_EXTENSIBLE\n"
     "define structure zaxet_s {\n  zz : abap.char(1);\n}"),
    ("e2 dizede extend type vbak", "ddls",
     "@EndUserText.label: 'extend type vbak with zzavbak'\ndefine view entity ZI_X as select from vbak {\n"
     "  key vbeln,\n  'annotate entity I_Product with' as Metin\n}"),
    ("f extend view entity ZI_X (Z hedef)", "ddls", "extend view entity ZI_X with {\n  a\n}"),
    ("f2 extend type zaxet_t (Z tablo)", "tabl", "extend type zaxet_t with zzaxet_t_ek {\n  zz : abap.char(1);\n}"),
    ("f3 annotate entity ZC_X (Z hedef)", "ddlx", "annotate entity ZC_X with {\n  @UI.hidden: true Id;\n}"),
    ("g namespace /ZABC/ hedef", "ddls", "extend view entity /ZABC/I_X with {\n  a\n}"),
    ("g2 namespace /YNS/ append", "tabl", "extend type /yns/tab with zzyns {\n  zz : abap.char(1);\n}"),
    ("j2 BDEF extension using interface Z (SAP örneği)", "bdef",
     "extension using interface zrap630i_shoptp_sol\nimplementation in class zbp_zrap630r_shop_x_fbk_sol unique;\n\n"
     "extend behavior for Shop\n{\n  extend draft determine action Prepare\n  {\n  }\n}"),
    ("j3 BDEF tanımı (genişletme değil)", "bdef",
     "managed implementation in class zbp_axet_i_x unique;\nstrict ( 2 );\ndefine behavior for ZAXET_I_X\n{\n}\n"),
    ("k ABAP kaynağı taranmaz (class)", "class", "CLASS zcl_x IMPLEMENTATION.\n  \" extend type vbak\nENDCLASS."),
    ("k2 define view entity std tablodan OKUR", "ddls",
     "define view entity ZI_SO as select from I_SalesOrder {\n  key SalesOrder\n}"),
]

FAIL_CLOSED = [
    # (ad, tip, kaynak) — hedef çözülemez → bulgu hedef "?"
    ("i1 BDEF extension for projection (hedef kaynakta yok)", "bdef",
     "extension for projection;\nextend behavior for Shop\n{\n  use action ZZ_ProvideFeedback;\n}"),
    ("i2 BDEF extension, using interface yok", "bdef",
     "extension implementation in class bp_z_aff_example_bdef_ext unique;\n\nextend behavior for RootEntity {\n"
     "  action extensionAction;\n}"),
    ("i3 EXTEND sözcüğü, tanınmayan biçim", "ddls",
     "define view entity ZI_X as select from vbak {\n  key vbeln,\n  extend\n}"),
    ("i4 ANNOTATE hedefsiz", "ddlx", "annotate entity with {\n  a;\n}"),
]

# `--` satırı (bug gate BULGU 1, 2026-09-24): `--` yorum sayılmadığı için içindeki `/*` blok yorum AÇIYOR ve sonraki
# `*/`'a kadar gerçek kod siliniyordu → `[]`, kapı allowed=True. SAP'nin CDS/BDL'de `--`'yı yorum sayıp saymadığı
# DOĞRULANMADI ⇒ her vaka İKİ yorumda da güvenli olmalı. (ad, tip, kaynak, beklenen hedef, beklenen satır)
TIRE_YORUM = [
    ("t1 -- /* … -- */ arası extend view entity (ddls)", "ddls",
     "-- /*\nextend view entity I_SalesOrder with { a }\n-- */", "I_SALESORDER", 2),
    ("t2 -- /* … -- */ arası annotate entity (ddlx)", "ddlx",
     "-- /*\nannotate entity I_Product with {\n  @UI.hidden: true Product;\n}\n-- */", "I_PRODUCT", 2),
    ("t3 -- /* … -- */ arası BDEF extension using interface", "bdef",
     "-- /*\nextension using interface I_SalesOrderTP\n  implementation in class zbp_ext_so unique;\n\n"
     "extend behavior for SalesOrder\n{\n}\n-- */", "I_SALESORDERTP", 2),
    ("t4 -- /* … -- */ arası extend type (tip None)", None,
     "-- /*\nextend type vbak with zzavbak {\n  zz : abap.char(1);\n}\n-- */", "VBAK", 2),
    ("t5 -- yorumundaki Z arayüzü ilk eşleşme olamaz (BDEF)", "bdef",
     "extension -- using interface ZI_X\n  using interface I_SalesOrderTP implementation in class zbp_x unique;\n"
     "extend behavior for SalesOrder\n{\n}", "I_SALESORDERTP", 1),
    ("t6 baştaki -- satırından sonra BDEF başlığı (extend behavior YOK, tip None)", None,
     "-- başlık notu\nextension using interface I_SalesOrderTP implementation in class zbp_x unique;\n"
     "define behavior for ZAXET_EXT_NODE\n{\n}", "I_SALESORDERTP", 2),
    # `--` metni SİLİNMEZ: SAP `--`'yı yorum saymıyorsa bu satır canlı koddur. Bilinen yanlış pozitif (SAP sayıyorsa).
    ("t7 -- satırındaki genişletme metni silinmez (tüketilir, taranır)", "ddls",
     "-- extend view entity I_SalesOrder with { a }\ndefine view entity ZI_X as select from vbak { key vbeln }",
     "I_SALESORDER", 1),
]

TIRE_YORUM_SERBEST = [
    ("u1 -- yorumlu Z kaynak (genişletme metni yok)", "ddls",
     "-- yorum: Z görünümü\ndefine view entity ZI_X as select from vbak { key vbeln } -- satır sonu notu"),
    ("u2 baştaki -- satırından sonra Z→Z BDEF extension", "bdef",
     "-- başlık notu\nextension using interface zrap630i_shoptp_sol\nimplementation in class zbp_x unique;\n\n"
     "extend behavior for Shop\n{\n}"),
    ("u3 -- /* … -- */ arası Z hedefli extend", "ddls", "-- /*\nextend view entity ZI_X with { a }\n-- */"),
]

# `--` YEM arayüzü (bug gate BLOCKER, taban efbd48f): `--` metni silinmeyen TEK görünümde BDEF başlığı `--` içindeki
# `;`'da bitiyor, `--` içindeki Z arayüzü toplanıyor, gerçek standart arayüz görünmüyordu → `[]`, kapı allowed=True.
# Düzeltme: üç görünüm ((a) `--` tüketilir-silinmez · (b) `--` yorum · (c) `--` kod) birleşimi. (ad, tip, kaynak, hedef, satır)
_B1 = ("extension -- using interface ZI_X ;\nusing interface I_SalesOrderTP implementation in class zbp_x unique;\n"
       "extend behavior for SalesOrder {}")
TIRE_YEM = [
    ("y1 B1 -- içindeki ; başlığı bitiriyor (bdef)", "bdef", _B1, "I_SALESORDERTP", 1),
    ("y2 B2 using -- c araya girmiş + yem (bdef)", "bdef",
     "extension -- using interface ZI_X\nusing -- c\ninterface I_SalesOrderTP implementation in class zbp_x unique;\n"
     "extend behavior for SalesOrder {}", "I_SALESORDERTP", 1),
    ("y3 B3 using interface -- c araya girmiş + yem (bdef)", "bdef",
     "extension -- using interface ZI_X\nusing interface -- c\nI_SalesOrderTP implementation in class zbp_x unique;\n"
     "extend behavior for SalesOrder {}", "I_SALESORDERTP", 1),
    ("y4 B4 = B1, tip None", None, _B1, "I_SALESORDERTP", 1),
    ("y5 B14 = B1 tip None, extend behavior YOK", None,
     "extension -- using interface ZI_X ;\nusing interface I_SalesOrderTP implementation in class zbp_x unique;\n"
     "define behavior for ZAXET_EXT_NODE {}", "I_SALESORDERTP", 1),
    # (c) görünümü: `--` kod sayılırsa baştaki `-- /*` gerçek blok açar, Z başlık yorumda kalır, canlı başlık standarttır
    ("y6 baştaki -- /* yalnız (c)'de std başlık (bdef)", "bdef",
     "-- /*\nextension using interface ZI_X implementation in class zbp_x unique;\n"
     "-- */ extension using interface I_SalesOrderTP implementation in class zbp_x unique;\n"
     "extend behavior for SalesOrder {}", "I_SALESORDERTP", 3),
    # tip None: Z arayüzlü BDEF başlığı kip kararını BDEF'e çevirip DDL genişletmesini gizliyordu
    ("y7 tip None: Z extension başlığı + extend view entity <std>", None,
     "extension using interface zi_x implementation in class zbp_x unique;\nextend view entity I_SalesOrder with { a }",
     "I_SALESORDER", 2),
    # DDL: (b) görünümü `--` araya girmiş hedefi ÇÖZER (önce `?` idi; iki durumda da red)
    ("y8 extend view entity -- ZI_X with / I_SalesOrder with (ddls)", "ddls",
     "extend view entity -- ZI_X with\nI_SalesOrder with { a }", "I_SALESORDER", 1),
]

TIRE_YEM_SERBEST = [
    ("v1 Z→Z BDEF extension (B8)", "bdef",
     "extension using interface zi_a implementation in class zbp_x unique;\nextend behavior for Shop {}"),
    ("v2 başlıkta -- notu ve ; — üç görünümde de yalnız Z", "bdef",
     "extension using interface zi_a -- not: ; using interface zi_b\nimplementation in class zbp_x unique;\n"
     "extend behavior for Shop {}"),
    ("v3 BOM'lu Z→Z BDEF extension (tip None)", None,
     "﻿extension using interface zi_a implementation in class zbp_x unique;\nextend behavior for Shop {}"),
]

# Baştaki BOM (U+FEFF): `\s` onu boşluk saymadığı için BDEF başlığı `^` çapası eşleşmiyordu (B13: `[]`).
BOM = [
    ("bom1 BOM + BDEF extension, extend behavior YOK (tip None)", None,
     "﻿extension using interface I_SalesOrderTP implementation in class zbp_x unique;\n"
     "define behavior for ZAXET_EXT_NODE {}", "I_SALESORDERTP", 1),
    ("bom2 BOM + BDEF extension (bdef)", "bdef",
     "﻿extension using interface I_SalesOrderTP implementation in class zbp_x unique;\n"
     "define behavior for ZAXET_EXT_NODE {}", "I_SALESORDERTP", 1),
    ("bom3 BOM + extend view entity (ddls)", "ddls", "﻿" + EXT_VIEW_ENTITY, "I_SALESORDER", 1),
]


class Tarayici(unittest.TestCase):
    def test_std_ext_tarayici_pozitif(self):
        for ad, tip, kaynak, hedef, satir in POZITIF:
            with self.subTest(ad):
                b = tara(kaynak, tip)
                ok = len(b) == 1 and b[0].hedef == hedef and b[0].satir == satir
                H.kaydet(f"Z104 tarayıcı {ad}", f"1 bulgu {hedef}@{satir}",
                         str([(x.hedef, x.satir) for x in b]), ok)
                self.assertTrue(ok, b)

    def test_std_ext_tarayici_negatif(self):
        for ad, tip, kaynak in NEGATIF:
            with self.subTest(ad):
                b = tara(kaynak, tip)
                H.kaydet(f"Z104 tarayıcı {ad}", "0 bulgu", str([(x.hedef, x.satir) for x in b]), not b)
                self.assertEqual(b, [], ad)

    def test_std_ext_tarayici_fail_closed(self):
        for ad, tip, kaynak in FAIL_CLOSED:
            with self.subTest(ad):
                b = tara(kaynak, tip)
                ok = len(b) == 1 and b[0].hedef == "?" and "fail-closed" in b[0].neden
                H.kaydet(f"Z104 tarayıcı {ad}", "1 bulgu hedef ?", str([(x.hedef, x.satir) for x in b]), ok)
                self.assertTrue(ok, b)

    def test_std_ext_tarayici_tire_yorum_bypass(self):
        for ad, tip, kaynak, hedef, satir in TIRE_YORUM:
            with self.subTest(ad):
                b = tara(kaynak, tip)
                ok = len(b) == 1 and b[0].hedef == hedef and b[0].satir == satir
                H.kaydet(f"Z104 tarayıcı {ad}", f"1 bulgu {hedef}@{satir}",
                         str([(x.hedef, x.satir) for x in b]), ok)
                self.assertTrue(ok, (ad, b))
        for ad, tip, kaynak in TIRE_YORUM_SERBEST:
            with self.subTest(ad):
                b = tara(kaynak, tip)
                H.kaydet(f"Z104 tarayıcı KONTROL {ad}", "0 bulgu", str([(x.hedef, x.satir) for x in b]), not b)
                self.assertEqual(b, [], ad)

    def test_std_ext_tarayici_tire_yem_arayuz(self):
        for ad, tip, kaynak, hedef, satir in TIRE_YEM:
            with self.subTest(ad):
                b = tara(kaynak, tip)
                ok = len(b) == 1 and b[0].hedef == hedef and b[0].satir == satir
                H.kaydet(f"Z104 tarayıcı {ad}", f"1 bulgu {hedef}@{satir}",
                         str([(x.hedef, x.satir) for x in b]), ok)
                self.assertTrue(ok, (ad, b))
        for ad, tip, kaynak in TIRE_YEM_SERBEST:
            with self.subTest(ad):
                b = tara(kaynak, tip)
                H.kaydet(f"Z104 tarayıcı KONTROL {ad}", "0 bulgu", str([(x.hedef, x.satir) for x in b]), not b)
                self.assertEqual(b, [], ad)

    def test_std_ext_tarayici_bom(self):
        for ad, tip, kaynak, hedef, satir in BOM:
            with self.subTest(ad):
                b = tara(kaynak, tip)
                ok = len(b) == 1 and b[0].hedef == hedef and b[0].satir == satir
                H.kaydet(f"Z104 tarayıcı {ad}", f"1 bulgu {hedef}@{satir}",
                         str([(x.hedef, x.satir) for x in b]), ok)
                self.assertTrue(ok, (ad, b))

    def test_std_ext_tarayici_tabl_xml(self):
        std = ("<DD02V>\n <TABNAME>ZZAVBAK</TABNAME>\n <TABCLASS>APPEND</TABCLASS>\n <SQLTAB>VBAK</SQLTAB>\n</DD02V>")
        z = "<DD02V><TABNAME>ZRAP630EXTSSHOP_SOL</TABNAME><TABCLASS>APPEND</TABCLASS><SQLTAB>ZRAP630SSHOP_SOL</SQLTAB></DD02V>"
        tablo = "<DD02V><TABNAME>ZAXET_T</TABNAME><TABCLASS>TRANSP</TABCLASS><SQLTAB>X</SQLTAB></DD02V>"
        eksik = "<DD02V><TABNAME>ZZX</TABNAME><TABCLASS>APPEND</TABCLASS></DD02V>"
        self.assertEqual([b.hedef for b in tara_tabl_xml(std)], ["VBAK"])
        self.assertEqual(tara_tabl_xml(z), [])
        self.assertEqual(tara_tabl_xml(tablo), [])
        self.assertEqual([b.hedef for b in tara_tabl_xml(eksik)], ["?"])

    def test_std_ext_mesaj_yonlendirme(self):
        m = mesaj(tara(APPEND_VBAK, "tabl"))
        for parca in ("Kesin Yasak A", "satır 3", "hedef VBAK", "yalnız OKUNUR", "kullanıcı yaratır",
                      "sonucu sana bildirir", "Kaynak SAP'ye gönderilmedi"):
            self.assertIn(parca, m)


class Kapi(unittest.TestCase):
    """Kapı (`gate.check_write`, adım 5) — opt-in AÇIK, --sap-write VAR, tier DEV: yine de red (h)."""

    @classmethod
    def setUpClass(cls):
        from sapadt import gate
        cls.gate = gate
        cls.root = Path(tempfile.mkdtemp(prefix="axet_z104_"))
        cls.p = H.make_project(cls.root, "dev")
        cls.home = cls.root / "home"
        (cls.home / "config").mkdir(parents=True)
        (cls.home / "config" / "sap-write.local").write_text("test opt-in\n", encoding="utf-8")
        cls._eski_env = {k: os.environ.pop(k) for k in list(os.environ) if k.upper().startswith("ADT_")}

    @classmethod
    def tearDownClass(cls):
        os.environ.update(cls._eski_env)
        shutil.rmtree(cls.root, ignore_errors=True)

    def yaz(self, tool="adt_push_source", ad="ZZAVBAK", tip="tabl", **args):
        tool_args = {"name": ad, "object_type": tip, **args}
        return self.gate.check_write(tool, self.p, obje_adi=ad, object_type=tip, transport="TESTK900001",
                                     scope="S1", reason="Z104 kapı birim testi gerekçesi", sap_write_flag=True,
                                     tool_args=tool_args, axet_home=self.home, log=False)

    def test_std_ext_gate_red(self):
        for ad, tip, kaynak, hedef, _satir in POZITIF:
            with self.subTest(ad):
                g = self.yaz(ad="ZAXET_EXT", tip=tip, source=kaynak)
                ok = (not g.allowed and g.code == "ADR_0005_A" and f"hedef {hedef}" in (g.message or "")
                      and g.tier == "DEV" and g.sap_write_optin)
                H.kaydet(f"Z104 kapı {ad}", "ADR_0005_A (DEV + opt-in)", f"{g.code} tier={g.tier}", ok)
                self.assertTrue(ok, (g.code, g.message))
                self.assertIn("std_ext_bulgular", g.details)

    def test_std_ext_gate_serbest_kontrol_grubu(self):
        for ad, tip, kaynak in NEGATIF:
            with self.subTest(ad):
                g = self.yaz(ad="ZAXET_EXT", tip=tip, source=kaynak)
                H.kaydet(f"Z104 kapı KONTROL {ad}", "allowed", f"{g.allowed} {g.code}", g.allowed)
                self.assertTrue(g.allowed, (g.code, g.message))

    def test_std_ext_gate_tire_yorum_bypass(self):
        for ad, tip, kaynak, hedef, _satir in TIRE_YORUM:
            with self.subTest(ad):
                g = self.yaz(ad="ZAXET_EXT", tip=tip, source=kaynak)
                ok = not g.allowed and g.code == "ADR_0005_A" and f"hedef {hedef}" in (g.message or "")
                H.kaydet(f"Z104 kapı {ad}", "ADR_0005_A", f"{g.code}", ok)
                self.assertTrue(ok, (ad, g.code, g.message))
        for ad, tip, kaynak in TIRE_YORUM_SERBEST:
            with self.subTest(ad):
                g = self.yaz(ad="ZAXET_EXT", tip=tip, source=kaynak)
                H.kaydet(f"Z104 kapı KONTROL {ad}", "allowed", f"{g.allowed} {g.code}", g.allowed)
                self.assertTrue(g.allowed, (ad, g.code, g.message))
        # adt_struct_create: iki alan adıyla `-- /*` … `-- */` sarmalı (render edilen DDL taranır)
        alan = [{"name": "x -- /*", "type": "char10"},
                {"name": "extend type mara with zzx { b -- */", "type": "char10"}]
        with self.subTest("t8 struct_create iki alan -- /* … -- */"):
            g = self.yaz(tool="adt_struct_create", ad="ZAXET_S", tip=None, fields=alan, description="Test yapısı",
                         package="ZAXET_PKG", transport="TESTK900001")
            ok = g.code == "ADR_0005_A" and "hedef MARA" in (g.message or "")
            H.kaydet("Z104 kapı struct_create -- /* iki alan", "ADR_0005_A hedef MARA", str(g.code), ok)
            self.assertTrue(ok, (g.code, g.message))

    def test_std_ext_gate_tire_yem_arayuz_ve_bom(self):
        for ad, tip, kaynak, hedef, _satir in TIRE_YEM + BOM:
            with self.subTest(ad):
                g = self.yaz(ad="ZAXET_EXT", tip=tip, source=kaynak)
                ok = not g.allowed and g.code == "ADR_0005_A" and f"hedef {hedef}" in (g.message or "")
                H.kaydet(f"Z104 kapı {ad}", "ADR_0005_A", f"{g.code}", ok)
                self.assertTrue(ok, (ad, g.code, g.message))
        for ad, tip, kaynak in TIRE_YEM_SERBEST:
            with self.subTest(ad):
                g = self.yaz(ad="ZAXET_EXT", tip=tip, source=kaynak)
                H.kaydet(f"Z104 kapı KONTROL {ad}", "allowed", f"{g.allowed} {g.code}", g.allowed)
                self.assertTrue(g.allowed, (ad, g.code, g.message))

    def test_std_ext_gate_fail_closed(self):
        for ad, tip, kaynak in FAIL_CLOSED:
            with self.subTest(ad):
                g = self.yaz(ad="ZAXET_EXT", tip=tip, source=kaynak)
                self.assertEqual(g.code, "ADR_0005_A", (ad, g.message))
        # tarayıcı koşamazsa → std_ext_scan_unavailable (sessiz geçiş YOK)
        with mock.patch("sapadt.std_ext_scan.tara", side_effect=RuntimeError("bozuk")):
            g = self.yaz(ad="ZAXET_EXT", tip="ddls", source="define view entity ZI_X as select from vbak { key vbeln }")
        H.kaydet("Z104 kapı tarayıcı koşamaz", "std_ext_scan_unavailable", str(g.code),
                 g.code == "std_ext_scan_unavailable")
        self.assertEqual(g.code, "std_ext_scan_unavailable")
        # doğrudan çağrı: kaynak yok / metin değil → fail-closed
        self.assertEqual(self.gate.check_std_extension("adt_push_source", {})[0], "std_ext_scan_unavailable")
        self.assertEqual(self.gate.check_std_extension("adt_push_source", {"source": 12})[0],
                         "std_ext_scan_unavailable")
        # kaynak taşımayan araç → denetim yok (None)
        self.assertIsNone(self.gate.check_std_extension("adt_activate", {"name": "ZX"}))

    def test_std_ext_gate_struct_create_alan_enjeksiyonu(self):
        """`adt_struct_create` alan adını doğrulamaz ⇒ render edilen DDL'e tek satırda `extend type` metni girer; kapı
        yazılacak DDL'i aynı render ile üretip tarar. Kontrol: normal alanlar serbest.
        DOĞRULANMADI (savunma derinliği): SAP'nin TEK yapı kaynağında `define structure` + `extend type` birlikte
        kabul edip etmediği ölçülmedi — kabul etmese de metni reddetmek güvenli yöndür."""
        alan = [{"name": "a : abap.char(1); } extend type vbak with zzx { b", "type": "char10"}]
        g = self.yaz(tool="adt_struct_create", ad="ZAXET_S", tip=None, fields=alan, description="Test yapısı",
                     package="ZAXET_PKG", transport="TESTK900001")
        H.kaydet("Z104 kapı struct_create alan enjeksiyonu", "ADR_0005_A", str(g.code), g.code == "ADR_0005_A")
        self.assertEqual(g.code, "ADR_0005_A", g.message)
        g = self.yaz(tool="adt_struct_create", ad="ZAXET_S", tip=None,
                     fields=[{"name": "extend_flag", "type": "char1", "description": "extend type vbak with zz"}],
                     description="extend type vbak with zz", package="ZAXET_PKG", transport="TESTK900001")
        self.assertTrue(g.allowed, (g.code, g.message))


class _IstemciCagrildi(AssertionError):
    pass


def _patla(*_a, **_k):
    raise _IstemciCagrildi("istemci/ağ çağrıldı — std_ext ikinci katmanı ağdan ÖNCE koşmadı")


class AracIkinciKatman(unittest.TestCase):
    """`adt_push_source` kapıyı atlayan çağrıda da (script/doğrudan) ağdan ÖNCE reddeder."""

    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="axet_z104a_"))
        cls.dev = H.make_project(cls.root, "dev")
        cls._eski_env = {k: os.environ.get(k) for k in ("AXET_SAP_PROJECT_DIR", "ADT_SAP_TIER")}
        os.environ.pop("ADT_SAP_TIER", None)
        os.environ["AXET_SAP_PROJECT_DIR"] = str(cls.dev)
        from sapadt.tools import atom
        cls.atom = atom
        cls._eski_client = atom._get_client
        atom._get_client = _patla

    @classmethod
    def tearDownClass(cls):
        cls.atom._get_client = cls._eski_client
        for k, v in cls._eski_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(cls.root, ignore_errors=True)

    def test_std_ext_push_source_ikinci_katman(self):
        for ad, tip, kaynak in (("append", "tabl", APPEND_VBAK), ("view entity", "ddls", EXT_VIEW_ENTITY),
                                ("annotate", "ddlx", ANNOTATE_ENTITY), ("-- /* sarmalı", "ddls", TIRE_YORUM[0][2]),
                                ("-- yem arayüz B1", "bdef", _B1), ("BOM bdef", "bdef", BOM[1][2])):
            with self.subTest(ad):
                r = self.atom.adt_push_source("ZAXET_EXT", tip, kaynak, transport="TESTK900001")
                ok = isinstance(r, dict) and r.get("code") == "ADR_0005_A"
                H.kaydet(f"Z104 süreç-içi push {ad}", "ADR_0005_A", str(r.get("code")), ok)
                self.assertTrue(ok, r)
        with mock.patch("sapadt.std_ext_scan.tara", side_effect=RuntimeError("bozuk")):
            r = self.atom.adt_push_source("ZAXET_EXT", "ddls", "define view entity ZI_X as select from t { a }")
        self.assertEqual(r.get("error"), "std_ext_scan_unavailable", r)


if __name__ == "__main__":
    unittest.main()
