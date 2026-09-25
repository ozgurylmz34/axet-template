# -*- coding: utf-8 -*-
"""Kesin Yasak B tarayıcısı (`sapadt/std_dml_scan.py`) — saf fonksiyon, ağ yok.

Pozitifler: standart tabloya doğrudan DB yazımı → bulgu (satır + hedef doğru).
Negatifler: yorum/literal, iç tablo işlemleri, EML, update task, Z/Y ve /Z…/ namespace → bulgu YOK.
"""
from __future__ import annotations

import sys
import unittest

import _helpers as H

sys.dont_write_bytecode = True
if str(H.SCRIPTS) not in sys.path:
    sys.path.insert(0, str(H.SCRIPTS))

from sapadt.std_dml_scan import abap_kaynagi_mi, mesaj, tara  # noqa: E402

POZITIF = [
    # (ad, kaynak, beklenen hedef, beklenen satır)
    ("P1 UPDATE vbak SET", "lv_x = 1.\nUPDATE vbak SET netwr = 0 WHERE vbeln = lv_vbeln.", "VBAK", 2),
    ("P2 INSERT INTO mara VALUES", "INSERT INTO mara VALUES ls_mara.", "MARA", 1),
    ("P3 MODIFY mara FROM ls", "DATA ls TYPE mara.\n\nMODIFY mara FROM ls.", "MARA", 3),
    ("P4 DELETE FROM likp WHERE", "DELETE FROM likp\n  WHERE vbeln = lv_vbeln.", "LIKP", 1),
    ("P5 DELETE mara FROM TABLE lt", "DELETE mara FROM TABLE lt_mara.", "MARA", 1),
    ("P6 EXEC SQL UPDATE", "EXEC SQL.\n  UPDATE mara SET mtart = 'X'\nENDEXEC.", "MARA", 2),
    ("P7 dinamik MODIFY (lv_tab)", "MODIFY (lv_tab) FROM ls_row.", "(lv_tab)", 1),
    ("P8 TABLES mara + MODIFY mara FROM mara", "TABLES mara.\nMODIFY mara FROM mara.", "MARA", 2),
    ("P9 AMDP insert into \"MARA\"",
     "CLASS zcl_x IMPLEMENTATION.\n"
     "  METHOD upd BY DATABASE PROCEDURE FOR HDB LANGUAGE SQLSCRIPT USING mara.\n"
     "    -- yorum: update mara set x = 1\n"
     "    insert into \"MARA\" values ( :iv_matnr );\n"
     "  ENDMETHOD.\n"
     "ENDCLASS.", "MARA", 4),
    ("P10 zincir UPDATE: vbak …, vbap …", "UPDATE: zsd_t SET a = 1,\n        vbap SET b = 2.", "VBAP", 2),
    ("P11 dinamik literal ('MARA')", "MODIFY ('MARA') FROM ls_row.", "MARA", 1),
    ("P12 namespace /SCWM/ (standart)", "UPDATE /scwm/ordim_o SET x = 1.", "/SCWM/ORDIM_O", 1),
    ("P13 INSERT mara FROM ls", "INSERT mara FROM ls_mara.", "MARA", 1),
    ("P14 AMDP schema.\"VBAK\" update", "METHOD m BY DATABASE PROCEDURE FOR HDB LANGUAGE SQLSCRIPT.\n"
     "  update \"SAPABAP1\".\"VBAK\" set netwr = 0;\nENDMETHOD.", "VBAK", 2),
]

NEGATIF = [
    ("N1 yorumdaki UPDATE mara", "* UPDATE mara SET x = 1.\nlv = 1. \" UPDATE mara SET x = 1\n"),
    ("N2 dizedeki UPDATE mara", "lv_t = 'UPDATE mara SET x = 1'.\nlv_s = |UPDATE mara SET { lv } = 1|.\n"
     "lv_b = `DELETE FROM mara`."),
    ("N3 MODIFY lt_items FROM ls INDEX sy-tabix", "MODIFY lt_items FROM ls INDEX sy-tabix."),
    ("N4 DELETE lt_x WHERE", "DELETE lt_x WHERE matnr IS INITIAL."),
    ("N5 INSERT ls INTO TABLE lt", "INSERT ls INTO TABLE lt."),
    ("N6 UPDATE zsd_tab SET", "UPDATE zsd_tab SET status = 'A' WHERE id = lv_id."),
    ("N7 MODIFY ztab FROM ls", "MODIFY ztab FROM ls."),
    ("N8 MODIFY ENTITIES … UPDATE FIELDS", "MODIFY ENTITIES OF zi_order IN LOCAL MODE\n"
     "  ENTITY Order UPDATE FIELDS ( Status ) WITH lt_upd\n  FAILED DATA(ls_f)."),
    ("N9 CALL FUNCTION 'X' IN UPDATE TASK", "CALL FUNCTION 'Z_UPD' IN UPDATE TASK EXPORTING iv = lv."),
    ("N10 DELETE ADJACENT DUPLICATES FROM lt", "DELETE ADJACENT DUPLICATES FROM lt COMPARING matnr."),
    ("N11 DELETE DATASET lv_file", "DELETE DATASET lv_file."),
    ("N12 /zns/ müşteri namespace", "UPDATE /zns/tab SET a = 1.\nDELETE FROM /yabc/log WHERE x = 1."),
    ("N13 MODIFY TABLE lt FROM ls", "MODIFY TABLE lt FROM ls."),
    ("N14 DELETE TABLE lt FROM ls", "DELETE TABLE lt FROM ls."),
    ("N15 INSERT … INTO lt INDEX", "INSERT ls INTO lt_items INDEX 1."),
    ("N16 INSERT LINES OF", "INSERT LINES OF lt_a INTO TABLE lt_b."),
    ("N17 DELETE FROM MEMORY / SHARED", "DELETE FROM MEMORY ID 'X'.\nDELETE FROM SHARED BUFFER indx(xy) ID 'K'."),
    ("N18 itab bildirimi öneksiz (DATA items TYPE TABLE OF)", "DATA items TYPE TABLE OF mara.\n"
     "MODIFY items FROM ls TRANSPORTING mtart WHERE matnr = 'X'.\nMODIFY items FROM ls.\nDELETE items FROM ls."),
    ("N19 UPDATE ifade başında değil / değişken adı", "lv_update = abap_true.\nupdate = 1.\n"
     "SELECT * FROM mara INTO TABLE @DATA(lt_m) FOR UPDATE."),
    ("N20 AMDP tablo değişkeni + SELECT + yorum", "METHOD m BY DATABASE PROCEDURE FOR HDB LANGUAGE SQLSCRIPT.\n"
     "  /* delete from mara */ lt = select * from \"MARA\";\n  insert into :lt_out values ( 1 );\n"
     "  x = replace(:a, 'b', 'c');\nENDMETHOD."),
    ("N21 DELETE lt FROM 2 TO 5", "DELETE lt_x FROM 2 TO 5."),
    ("N22 EXEC SQL SELECT", "EXEC SQL.\n SELECT * FROM mara INTO :ls\nENDEXEC."),
]


class StdDmlTarama(unittest.TestCase):
    def test_pozitif(self):
        for ad, kaynak, hedef, satir in POZITIF:
            with self.subTest(ad):
                b = tara(kaynak, "class")
                ok = any(x.hedef == hedef and x.satir == satir for x in b)
                H.kaydet(f"B {ad}", f"bulgu {hedef}@{satir}",
                         "; ".join(f"{x.hedef}@{x.satir}" for x in b) or "bulgu yok", ok)
                self.assertTrue(ok, f"{ad}: {b}")
                if hedef.startswith("("):
                    self.assertIn("dinamik tablo adı", b[0].neden)

    def test_negatif(self):
        for ad, kaynak in NEGATIF:
            with self.subTest(ad):
                b = tara(kaynak, "class")
                H.kaydet(f"B {ad}", "bulgu yok", "; ".join(f"{x.hedef}@{x.satir}" for x in b) or "bulgu yok", not b)
                self.assertEqual(b, [], f"{ad}: {b}")

    def test_tip_kapsami(self):
        dml = "UPDATE mara SET x = 1."
        for tip, beklenen in (("class", True), ("prog", True), ("program", True), ("include", True),
                              ("interface", True), ("ccimp", True), ("fugr", True), ("func", True),
                              ("ddls", False), ("cds", False), ("bdef", False), ("srvd", False),
                              ("srvb", False), ("ddlx", False), ("dcl", False), ("tabl", False),
                              ("structure", False), ("dtel", False), (None, True), ("uydurma_tip", True)):
            with self.subTest(tip):
                self.assertEqual(abap_kaynagi_mi(tip), beklenen, tip)
                self.assertEqual(bool(tara(dml, tip)), beklenen, tip)
        H.kaydet("B tip kapsamı (ABAP taranır, CDS/BDEF/SRVD/DDIC taranmaz, bilinmeyen taranır)",
                 "20 tip beklenene eşit", "eşit", True)

    def test_mesaj(self):
        kaynak = "\n".join(f"UPDATE vbak SET x = {i}." for i in range(7))
        b = tara(kaynak, "class")
        m = mesaj(b)
        self.assertEqual(len(b), 7)
        self.assertIn("satır 1: UPDATE vbak SET x = 0 → hedef VBAK", m)
        self.assertIn("satır 5:", m)
        self.assertNotIn("satır 6:", m)
        self.assertIn("+2 bulgu daha", m)
        self.assertIn("released API (released RAP BO/EML · released BAPI · released OData) → BAPI → RFC FM → işlem kodu (BDC) → kullanıcıdan manuel", m)
        self.assertIn("write-api-selection.md", m)
        H.kaydet("B mesaj: ilk 5 bulgu + satır no + yönlendirme", "5 satır + '+2' + released API→BAPI→RFC→BDC + karar ağacı",
                 "uyuşuyor", True)


if __name__ == "__main__":
    unittest.main()
