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

    # --- Başlık / yorum / namespace grameri (kaynak çekirdek G1-G10 sözleşmesinin gen_field_table kısmı) ---
    def _parse(self, metin):
        return gft._body(gft._strip_comments(metin))

    def test_g1_custom_entity_name_and_body(self):
        name, proj, body = self._parse("@EndUserText.label: 'X'\ndefine custom entity ZCA001_CE_X\n{\n  key Id : abap.char(10);\n}\n")
        self.assertEqual("ZCA001_CE_X", name)
        self.assertIsNone(proj)
        self.assertIn("key Id", body)

    def test_g2_root_custom_header_brace_not_body(self):
        src = ("@ObjectModel.query.implementedBy: 'ABAP:ZCL_X'\n"
               "@UI.headerInfo: { typeName: 'Baslik' }\n"
               "define root custom entity ZCA001_CE_R\n{\n  key Id : abap.char(10);\n}\n")
        name, _, body = self._parse(src)
        self.assertEqual("ZCA001_CE_R", name)
        self.assertIn("key Id", body)
        self.assertNotIn("typeName", body)

    def test_g4_g5_dash_comment(self):
        src = ("-- define view entity ZCA001_ESKI as select from x\n"
               "define view entity ZCA001_C_NEW as projection on ZCA001_I_NEW\n{\n"
               "  key Id, -- anahtar 601'in kopyası\n  Status -- durum\n}\n")
        name, proj, body = self._parse(src)
        self.assertEqual("ZCA001_C_NEW", name)                       # G4: yorumdaki eski başlık ad vermez
        self.assertEqual("ZCA001_I_NEW", proj)
        fields = [ln.strip().rstrip(",").strip() for ln in body.splitlines() if ln.strip()]
        self.assertEqual(["key Id", "Status"], fields)               # G5: `-- yorum`lu satır alan üretir

    def test_g6_g8_label_string_preserved(self):
        txt = gft._strip_comments("@EndUserText.label: 'A -- B // C'\nx // yorum\ny -- yorum\n")
        self.assertIn("'A -- B // C'", txt)                          # G6 + G8: string içi korunur
        self.assertNotIn("yorum", txt)                                # G7 kontrol grubu: gerçek yorum atılır

    def test_namespace_name_and_sibling_file(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "#nspc#sd001_c_x.cds"), "w", encoding="utf-8") as fh:
                fh.write("define view entity /NSPC/SD001_C_X as projection on /NSPC/SD001_I_X\n{\n  key Id,\n  Status\n}\n")
            with open(os.path.join(d, "#nspc#sd001_i_x.cds"), "w", encoding="utf-8") as fh:
                fh.write("define view entity /NSPC/SD001_I_X as select from t\n{\n"
                         "  @EndUserText.label: 'Kimlik'\n  key id as Id,\n  @EndUserText.label: 'Durum'\n  st as Status\n}\n")
            name, proj, fields = gft.parse_cds(os.path.join(d, "#nspc#sd001_c_x.cds"))
            self.assertEqual("/NSPC/SD001_C_X", name)
            self.assertEqual("/NSPC/SD001_I_X", proj)
            md, unresolved = gft.build_table(os.path.join(d, "#nspc#sd001_c_x.cds"))
            self.assertEqual([], unresolved)                          # etiketler komşu `#nspc#…` dosyasından
            self.assertIn("| Status | Durum |", md)

    def test_namespace_source_field_kept_unresolvable_reported(self):
        """Namespace'li KAYNAK alanı (`/nspc/fld as X`, `key /nspc/tab.vbeln as Y`, `_tab./nspc/fld as Z`) tabloya girer;
        alan konumunda olup gramere uymayan satır sessizce düşmez, "çözülemedi" diye raporlanır (aXet tur 8 bug-gate)."""
        import tempfile
        src = ("define view entity ZCA001_I_NS as select from /nspc/tab as t\n"
               "  association [0..1] to /NSPC/X as _tab on _tab.a = t.a\n{\n"
               "  key /nspc/tab.vbeln as SalesOrder,\n"
               "  @EndUserText.label: 'NS alan'\n  /nspc/fld as NsField,\n"
               "  _tab./nspc/fld as AssocNs,\n"
               "  /ab/bozuk as Bozuk,\n"
               "  normal_fld as Normal,\n  _tab\n}\n")
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "zca001_i_ns.cds")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(src)
            name, _, fields = gft.parse_cds(p)                        # 3'lü dönüş sözleşmesi korunur
            self.assertEqual("ZCA001_I_NS", name)
            self.assertEqual(["SalesOrder", "NsField", "AssocNs", "Normal"], [f["name"] for f in fields])
            self.assertTrue(fields[0]["key"])
            self.assertEqual("NS alan", fields[1]["label"])
            self.assertEqual(["/ab/bozuk as Bozuk"], gft.parse_cds_ayrintili(p)[3])
            md, _ = gft.build_table(p)
            self.assertIn("1 alan satırı çözülemedi", md)
            self.assertIn("`/ab/bozuk as Bozuk`", md)
            self.assertNotIn("| Bozuk |", md)
            # kontrol grubu: çözülemeyen satır yoksa uyarı satırı da yok
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(src.replace("  /ab/bozuk as Bozuk,\n", ""))
            self.assertNotIn("çözülemedi", gft.build_table(p)[0])

    def test_unresolvable_name_is_question_mark(self):
        name, _, body = self._parse("@UI.headerInfo: { typeName: 'T' }\ndefine view entity /AB/X as select from t\n{\n  a\n}\n")
        self.assertEqual("?", name)
        self.assertNotIn("typeName", body)                           # gövde yine define'dan sonra aranır

    def test_g9_helper_is_stdlib_only(self):
        """Yardımcı modül yalnız stdlib import eder; gen_field_table foundation/bağlantı katmanını yüklemez."""
        import ast
        import sys as _sys
        scripts = os.path.dirname(os.path.abspath(gft.__file__))
        izinli = set(getattr(_sys, "stdlib_module_names", ())) | {"doc_ad_metin"}
        self.assertTrue(len(izinli) > 1, "stdlib listesi okunamadı (Python < 3.10)")
        for fn in ("doc_ad_metin.py", "gen_field_table.py"):
            with open(os.path.join(scripts, fn), encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
            mods = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    mods.update(a.name.split(".")[0] for a in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    mods.add(node.module.split(".")[0])
            self.assertEqual(set(), mods - izinli, fn)

    def test_main_missing_file_exit_2(self):
        rc, _, err = call_main(gft.main, [sample("cds", "YOK.cds")])
        self.assertEqual(2, rc)
        self.assertIn("okunamadı", err)
        self.assertIn("KAPSAM (SCOPE)", err)


if __name__ == "__main__":
    unittest.main()
