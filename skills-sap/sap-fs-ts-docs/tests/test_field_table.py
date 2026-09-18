# -*- coding: utf-8 -*-
"""gen_field_table.py: projeksiyon → interface etiket yedeği, BDEF readonly, CSV etiketi, etiketsiz alan işareti."""
import os
import unittest

from _common import call_main, sample

import gen_field_table as gft

CDS = sample("cds", "ZCA000_C_DEMO.cds")
CSV = sample("cds", "fields.csv")


def _rows(md):
    rows = {}
    for line in md.splitlines():
        if line.startswith("| ") and not line.startswith("| Alan"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            rows[cells[0]] = cells
    return rows


class FieldTableTest(unittest.TestCase):
    def test_parse_projection_skips_header_braces_and_associations(self):
        name, proj, fields = gft.parse_cds(CDS)
        self.assertEqual("ZCA000_C_DEMO", name)
        self.assertEqual("ZCA000_I_DEMO", proj)
        self.assertEqual(["RequestId", "Status", "Amount", "CurrencyCode", "RefNo", "Note"], [f["name"] for f in fields])

    def test_table_content(self):
        md, unresolved = gft.build_table(CDS, CSV)
        rows = _rows(md)
        self.assertEqual(["RequestId", "Talep No", "Evet", "Evet (zorunlu)", "", "Hayır"], rows["RequestId"])
        self.assertEqual("Durum", rows["Status"][1])
        self.assertEqual("ZCA000_I_STATUS_VH", rows["Status"][4])
        self.assertEqual("Hayır", rows["Status"][5])
        self.assertEqual(["Amount", "Tutar", "", "", "", "Evet"], rows["Amount"])
        self.assertEqual("Para Birimi", rows["CurrencyCode"][1])
        self.assertEqual("Referans Numarası", rows["RefNo"][1])
        self.assertEqual(["Note"], unresolved)
        self.assertIn("_(etiket kaynakta yok)_", rows["Note"][1])
        self.assertIn("6 alan; 2 salt okunur", md)

    def test_without_csv_refno_unresolved(self):
        _, unresolved = gft.build_table(CDS)
        self.assertEqual(["RefNo", "Note"], unresolved)

    def test_stem(self):
        self.assertEqual(os.path.join("a", "X"), gft._stem(os.path.join("a", "X.ddls.asddls")))
        self.assertEqual("X", gft._stem("X.bdef.asbdef"))
        self.assertEqual("X", gft._stem("X.cds"))

    def test_main_missing_file_exit_2(self):
        rc, _, err = call_main(gft.main, [sample("cds", "YOK.cds")])
        self.assertEqual(2, rc)
        self.assertIn("okunamadı", err)
        self.assertIn("KAPSAM (SCOPE)", err)


if __name__ == "__main__":
    unittest.main()
