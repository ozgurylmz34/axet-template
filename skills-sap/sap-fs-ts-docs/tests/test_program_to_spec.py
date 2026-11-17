# -*- coding: utf-8 -*-
"""program_to_spec.py: kaynaktaki olguların çıkarımı, yorum satırı, taslak çıktı, geçersiz kaynak."""
import os
import tempfile
import unittest

from _common import call_main, sample

import program_to_spec as pts

SRC = sample("abap", "zca000_demo_report.abap")


class ProgramToSpecTest(unittest.TestCase):
    def setUp(self):
        with open(SRC, encoding="utf-8") as fh:
            self.facts = pts.extract(fh.read())

    def test_extract(self):
        f = self.facts
        self.assertEqual(["zca000_demo_report"], f["report"])
        self.assertIn("vbak", f["tables"])
        self.assertIn("zca000_t_demo", f["select_from"])
        self.assertNotIn("yorum_tablosu", f["select_from"], "yorum satırı atlanmalı")
        self.assertEqual(["p_bukrs"], f["params"])
        self.assertEqual(["s_erdat"], f["selopts"])
        self.assertEqual(["BAPI_SALESORDER_GETLIST", "Z_CA000_DEMO_FM"], f["call_func"])
        self.assertEqual(["get_data"], f["forms"])
        self.assertEqual(["100"], f["screens"])

    def test_render(self):
        doc = pts.render(self.facts, [SRC])
        self.assertIn("TASLAK FS/TS — zca000_demo_report", doc)
        self.assertIn("Standart (sistemde varlığı", doc)
        self.assertIn("vbak", doc.split("Standart (sistemde varlığı")[1].splitlines()[0])
        self.assertIn("Müşteri (Z/Y) tabloları:** zca000_t_demo", doc)
        self.assertIn("BAPI_SALESORDER_GETLIST` (BAPI", doc)
        self.assertIn("Ekran 100", doc)
        self.assertIn("<TODO:", doc)

    def test_namespace_tables_separate_bucket(self):
        src = ("REPORT /nspc/sd001_r_demo.\n"
               "SELECT * FROM /nspc/sd001_t_head INTO TABLE @DATA(a).\n"
               "SELECT * FROM ytab INTO TABLE @DATA(b) .\n"
               "SELECT * FROM mara JOIN /ab/x ON 1 = 1 INTO TABLE @DATA(c).\n")
        f = pts.extract(src)
        self.assertEqual(["/nspc/sd001_r_demo"], f["report"])
        self.assertIn("/nspc/sd001_t_head", f["select_from"])
        self.assertNotIn("/ab/x", f["select_from"])               # katı gramer: 2 karakterli namespace düşer
        self.assertFalse([t for t in f["select_from"] if t.startswith("/") and t != "/nspc/sd001_t_head"])
        doc = pts.render(f, ["x.abap"])
        ns_line = [ln for ln in doc.splitlines() if ln.startswith("- **Namespace'li tablolar")]
        self.assertEqual(1, len(ns_line))
        self.assertIn("/nspc/sd001_t_head", ns_line[0])
        std_line = [ln for ln in doc.splitlines() if ln.startswith("- **Standart")][0]
        self.assertNotIn("/nspc/", std_line)
        self.assertIn("mara", std_line)
        self.assertIn("Müşteri (Z/Y) tabloları:** ytab", doc)

    def test_turkish_word_not_cut(self):
        f = pts.extract("DATA x TYPE i.\n\" bu satırdan from satırların seçimi\nSELECT * FROM vbak INTO TABLE @DATA(t).\n")
        self.assertIn("satırların", f["select_from"])               # eski `\w+` davranışı: sözcük bütün
        self.assertNotIn("sat", f["select_from"])

    def test_main_out_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "docs", "TASLAK.md")
            rc, stdout, _ = call_main(pts.main, [SRC, "--out", out])
            self.assertEqual(0, rc)
            self.assertTrue(os.path.isfile(out))
            self.assertIn("KAPSAM (SCOPE)", stdout)

    def test_main_no_valid_source(self):
        rc, _, err = call_main(pts.main, [sample("abap", "yok.abap")])
        self.assertEqual(1, rc)
        self.assertIn("geçerli kaynak yok", err)


if __name__ == "__main__":
    unittest.main()
