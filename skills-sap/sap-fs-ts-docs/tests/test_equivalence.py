# -*- coding: utf-8 -*-
"""doc_equivalence_check.py: denk, kayıplı, kapanmış karar, okunamayan girdi, kapsam uyarısı."""
import os
import tempfile
import unittest

from _common import call_main, sample

import doc_equivalence_check as dec

OLD, NEW, EK, LOSSY = sample("fs_old.md"), sample("fs_new.md"), sample("fs_ek.md"), sample("fs_new_lossy.md")


class EquivalenceTest(unittest.TestCase):
    def test_equivalent_with_appendix(self):
        rc, out, _ = call_main(dec.main, ["--old", OLD, "--new", NEW, "--new", EK, "--no-scope-warning"])
        self.assertEqual(0, rc, out)
        self.assertIn("SONUÇ: DENK", out)
        self.assertIn("KAPSAM (SCOPE)", out)
        self.assertIn("BU ARAÇ ŞUNLARI ÖLÇMEZ", out)

    def test_body_only_loses_moved_sentence(self):
        rc, out, _ = call_main(dec.main, ["--old", OLD, "--new", NEW, "--no-scope-warning"])
        self.assertEqual(1, rc)
        self.assertIn("v1.1 revizyonunda", out)

    def test_lossy_rewrite_detected(self):
        rc, out, _ = call_main(dec.main, ["--old", OLD, "--new", LOSSY, "--no-scope-warning"])
        self.assertEqual(1, rc)
        self.assertIn("FR-002", out)
        self.assertIn("2500", out)
        self.assertIn("KAYIP VAR", out)

    def test_closed_decision_reverse_direction(self):
        for flag in ("--closed-decision", "--kapanmis-karar"):
            rc, out, _ = call_main(dec.main, ["--old", OLD, "--new", NEW, "--new", EK, "--no-scope-warning",
                                              flag, "ref_no"])
            self.assertEqual(1, rc, flag)
            self.assertIn("KAPANMIŞ KARAR YAŞIYOR", out)
            self.assertIn("fs_new.md", out)

    def test_closed_decision_absent_is_clean(self):
        rc, out, _ = call_main(dec.main, ["--old", OLD, "--new", NEW, "--new", EK, "--no-scope-warning",
                                          "--closed-decision", "ESKI_ALAN_YOK"])
        self.assertEqual(0, rc, out)
        self.assertIn("TEMİZ `ESKI_ALAN_YOK`", out)

    def test_unreadable_input_exit_2(self):
        rc, _, err = call_main(dec.main, ["--old", sample("yok.md"), "--new", NEW])
        self.assertEqual(2, rc)
        self.assertIn("ÖLÇÜLEMEDİ", err)

    def test_scope_warning_lists_unscanned_siblings(self):
        _, out, _ = call_main(dec.main, ["--old", OLD, "--new", NEW, "--new", EK])
        self.assertIn("TARANMAYAN", out)
        self.assertIn("fs_new_lossy.md", out)

    def test_report_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            rep = os.path.join(tmp, "rapor.md")
            call_main(dec.main, ["--old", OLD, "--new", NEW, "--new", EK, "--no-scope-warning", "--report", rep])
            with open(rep, encoding="utf-8") as fh:
                self.assertIn("Doküman denklik raporu", fh.read())

    def test_turkish_lowercase(self):
        self.assertEqual("kesinlikle", dec.kucult("KESİNLİKLE"))
        self.assertEqual(dec.norm("**KESİNLİKLE**  zorunlu"), dec.norm("kesinlikle zorunlu"))


if __name__ == "__main__":
    unittest.main()
