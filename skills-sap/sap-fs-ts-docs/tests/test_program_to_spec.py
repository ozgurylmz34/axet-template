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
