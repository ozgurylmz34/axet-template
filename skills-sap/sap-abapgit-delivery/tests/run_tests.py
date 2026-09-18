#!/usr/bin/env python3
"""sap-abapgit-delivery çevrimdışı testleri (stdlib unittest; SAP bağlantısı yok).

    python skills-sap/sap-abapgit-delivery/tests/run_tests.py

Fikstürler SENTETİKTİR: abapGit dosya adı kalıbına uyan, denetim kurallarını tetiklemeye yetecek kadar XML/ABAP;
gerçek bir SAP dışa aktarımının tam şeması değildir. Çıkış: 0 tümü geçti · 1 en az bir başarısız.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "abapgit_zip.py"

DOT = """<?xml version="1.0" encoding="utf-8"?>
<asx:abap xmlns:asx="http://www.sap.com/abapxml" version="1.0">
 <asx:values>
  <DATA>
   <MASTER_LANGUAGE>{lang}</MASTER_LANGUAGE>
   <STARTING_FOLDER>/src/</STARTING_FOLDER>
   <FOLDER_LOGIC>PREFIX</FOLDER_LOGIC>
  </DATA>
 </asx:values>
</asx:abap>
"""
CLAS_XML = """<?xml version="1.0" encoding="utf-8"?>
<abapGit version="v1.0.0" serializer="LCL_OBJECT_CLAS">
 <asx:abap xmlns:asx="http://www.sap.com/abapxml" version="1.0">
  <asx:values>
   <VSEOCLASS>
    <CLSNAME>{name}</CLSNAME>
    <LANGU>{lang}</LANGU>
    <DESCRIPT>{descript}</DESCRIPT>
   </VSEOCLASS>
  </asx:values>
 </asx:abap>
</abapGit>
"""
DTEL_XML = """<?xml version="1.0" encoding="utf-8"?>
<abapGit version="v1.0.0" serializer="LCL_OBJECT_DTEL">
 <asx:abap xmlns:asx="http://www.sap.com/abapxml" version="1.0">
  <asx:values>
   <DD04V>
    <ROLLNAME>ZDEMO_DTEL</ROLLNAME>
    <DDLANGUAGE>T</DDLANGUAGE>
    <DDTEXT>Demo alanı</DDTEXT>
{labels}
   </DD04V>
  </asx:values>
 </asx:abap>
</abapGit>
"""
FULL_LABELS = ("    <REPTEXT>Demo</REPTEXT>\n    <SCRTEXT_S>Demo</SCRTEXT_S>\n"
               "    <SCRTEXT_M>Demo alan</SCRTEXT_M>\n    <SCRTEXT_L>Demo alanı</SCRTEXT_L>")
ABAP_OK = "CLASS zcl_demo DEFINITION.\nENDCLASS.\nCLASS zcl_demo IMPLEMENTATION.\nENDCLASS.\n"


def run(*args, script: Path = SCRIPT):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([sys.executable, str(script)] + [str(a) for a in args], capture_output=True, text=True,
                       encoding="utf-8", stdin=subprocess.DEVNULL, env=env, timeout=120)
    return p.returncode, p.stdout, p.stderr


def make_export(path: Path, lang: str = "T", extra: dict | None = None) -> None:
    members = {
        ".abapgit.xml": DOT.format(lang=lang),
        "src/zcl_demo.clas.abap": ABAP_OK,
        "src/zcl_demo.clas.xml": CLAS_XML.format(name="ZCL_DEMO", lang="T", descript="Demo sınıfı"),
        "src/zdemo_dtel.dtel.xml": DTEL_XML.format(labels=FULL_LABELS),
        "README.md": "kök dosyası: başlangıç klasörü dışında, alınmamalı\n",
    }
    members.update(extra or {})
    with zipfile.ZipFile(path, "w") as zf:
        for name, text in members.items():
            zf.writestr(name, text)


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = Path(self._tmp.name)
        self.ws = self.d / "ws"
        self.project = self.d / "proje"
        self.project.mkdir()
        self.set_language("TR")
        self.export = self.d / "export.zip"
        make_export(self.export)
        rc, out, err = run("unpack", self.export, "--root", self.ws)
        self.assertEqual(rc, 0, err)

    def tearDown(self):
        self._tmp.cleanup()

    def set_language(self, value: str) -> None:
        (self.project / "sap-project.json").write_text(json.dumps({"master_language": value}), encoding="utf-8")

    def write(self, rel: str, text: str, newline: str = "\n") -> None:
        p = self.ws / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(text.replace("\n", newline).encode("utf-8"))

    def check(self, *args):
        rc, out, err = run("check", "--root", self.ws, "--project-dir", self.project, "--json", *args)
        self.assertIn(rc, (0, 2), err)
        data = json.loads(out)
        return rc, data, {f["code"] for f in data["findings"] if f["level"] == "FAIL"}, \
            {f["code"] for f in data["findings"] if f["level"] == "WARN"}


class UnpackTests(Base):
    def test_baseline_and_starting_folder(self):
        base = json.loads((self.ws / ".abapgit-baseline.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(base["files"]), [".abapgit.xml", "src/zcl_demo.clas.abap", "src/zcl_demo.clas.xml",
                                                 "src/zdemo_dtel.dtel.xml"])
        self.assertFalse((self.ws / "README.md").exists())

    def test_zip_slip_refused_before_writing(self):
        evil = self.d / "evil.zip"
        with zipfile.ZipFile(evil, "w") as zf:
            zf.writestr(".abapgit.xml", DOT.format(lang="T"))
            zf.writestr("src/zok.clas.abap", ABAP_OK)
            zf.writestr("../kacak.txt", "x")
        target = self.d / "ws2"
        rc, _, err = run("unpack", evil, "--root", target)
        self.assertEqual(rc, 2)
        self.assertIn("güvensiz", err)
        self.assertFalse(target.exists())
        self.assertFalse((self.d / "kacak.txt").exists())

    def test_local_change_not_overwritten_without_force(self):
        self.write("src/zcl_demo.clas.abap", ABAP_OK + "* yerel\n")
        rc, _, err = run("unpack", self.export, "--root", self.ws)
        self.assertEqual(rc, 2)
        self.assertIn("* yerel", (self.ws / "src/zcl_demo.clas.abap").read_text(encoding="utf-8"))
        self.assertEqual(run("unpack", self.export, "--root", self.ws, "--force")[0], 0)
        self.assertNotIn("* yerel", (self.ws / "src/zcl_demo.clas.abap").read_text(encoding="utf-8"))

    def test_not_an_abapgit_zip(self):
        bad = self.d / "bad.zip"
        with zipfile.ZipFile(bad, "w") as zf:
            zf.writestr("src/x.txt", "x")
        self.assertEqual(run("unpack", bad, "--root", self.d / "ws3")[0], 1)


class PackTests(Base):
    def test_happy_path_lf_siblings_manifest(self):
        self.write("src/zcl_demo.clas.abap", ABAP_OK + "METHOD x.\n  UPDATE zdemo_tab SET durum = 'A'.\nENDMETHOD.\n",
                   newline="\r\n")
        out_zip = self.d / "teslim.zip"
        rc, out, err = run("pack", "--root", self.ws, "--all", "--project-dir", self.project, "--out", out_zip, "-m", "test")
        self.assertEqual(rc, 0, out + err)
        self.assertIn("KAPSAM", out)
        self.assertIn("Import zip", out)
        with zipfile.ZipFile(out_zip) as zf:
            names = sorted(zf.namelist())
            self.assertEqual(names, [".abapgit.xml", ".axet-abapgit-manifest.json", "src/zcl_demo.clas.abap",
                                     "src/zcl_demo.clas.xml"])
            self.assertNotIn(b"\r", zf.read("src/zcl_demo.clas.abap"))
            manifest = json.loads(zf.read(".axet-abapgit-manifest.json"))
        self.assertEqual(manifest["note"], "test")
        self.assertEqual(sorted(manifest["files"]), ["src/zcl_demo.clas.abap", "src/zcl_demo.clas.xml"])
        rc, _, _ = run("pack", "--root", self.ws, "--all", "--project-dir", self.project, "--out", out_zip)
        self.assertEqual(rc, 3)  # var olan çıktı --force olmadan ezilmez

    def test_nothing_changed_is_denied(self):
        rc, data, fails, _ = self.check("--all")
        self.assertEqual(rc, 2)
        self.assertIn("empty_selection", fails)

    def test_fail_blocks_zip(self):
        self.write("src/mara.tabl.xml", "<abapGit><DD02V><TABNAME>MARA</TABNAME></DD02V></abapGit>\n")
        rc, out, err = run("pack", "--root", self.ws, "--files", "src/mara.tabl.xml", "--project-dir", self.project)
        self.assertEqual(rc, 2)
        self.assertIn("ADR_0005_A", out)
        self.assertFalse((self.ws / "dist").exists())


class RuleTests(Base):
    def test_standard_object_A(self):
        self.write("src/mara.tabl.xml", "<abapGit><DD02V><DDTEXT>x</DDTEXT></DD02V></abapGit>\n")
        self.assertIn("ADR_0005_A", self.check("--files", "src/mara.tabl.xml")[2])

    def test_customer_namespaces_and_lock_object_allowed(self):
        self.write("src/#zns#cl_x.clas.abap", ABAP_OK)
        self.write("src/#zns#cl_x.clas.xml", CLAS_XML.format(name="/ZNS/CL_X", lang="T", descript="x"))
        self.write("src/ezdemo_lock.enqu.xml", "<abapGit><DD25V><DDTEXT>Kilit</DDTEXT></DD25V></abapGit>\n")
        self.write("src/#sapns#cl_y.clas.xml", CLAS_XML.format(name="/SAPNS/CL_Y", lang="T", descript="y"))
        _, data, fails, _ = self.check("--files", "src/#zns#cl_x.clas.abap", "src/ezdemo_lock.enqu.xml")
        self.assertNotIn("ADR_0005_A", fails)
        self.assertIn("ADR_0005_A", self.check("--files", "src/#sapns#cl_y.clas.xml")[2])

    def test_package_definition_C(self):
        self.write("src/package.devc.xml", "<abapGit><DEVC><CTEXT>Paket</CTEXT></DEVC></abapGit>\n")
        self.assertIn("ADR_0005_C_package", self.check("--files", "src/package.devc.xml")[2])

    def test_new_subfolder_C(self):
        self.write("src/alt/zcl_yeni.clas.abap", ABAP_OK)
        self.write("src/alt/zcl_yeni.clas.xml", CLAS_XML.format(name="ZCL_YENI", lang="T", descript="Yeni"))
        _, _, fails, _ = self.check("--all")
        self.assertIn("ADR_0005_C_subpackage", fails)
        rc, _, fails, _ = self.check("--all", "--subpackages-exist")
        self.assertNotIn("ADR_0005_C_subpackage", fails)
        self.assertEqual(rc, 0)

    def test_metadata_missing(self):
        self.write("src/zcl_metasiz.clas.abap", ABAP_OK)
        self.assertIn("metadata_missing", self.check("--files", "src/zcl_metasiz.clas.abap")[2])

    def test_direct_standard_table_write_B(self):
        self.write("src/zcl_demo.clas.abap", ABAP_OK + "METHOD x.\n  UPDATE mara SET matkl = 'X' WHERE matnr = '1'.\nENDMETHOD.\n")
        rc, data, fails, _ = self.check("--all")
        self.assertIn("ADR_0005_B", fails)
        self.assertEqual(rc, 2)

    def test_scanner_unavailable_is_fail_closed(self):
        fake = self.d / "kopya" / "skills-sap" / "sap-abapgit-delivery" / "scripts" / "abapgit_zip.py"
        fake.parent.mkdir(parents=True)
        shutil.copy(SCRIPT, fake)
        self.write("src/zcl_demo.clas.abap", ABAP_OK + "* değişti\n")
        rc, out, _ = run("check", "--root", self.ws, "--all", "--project-dir", self.project, "--json", script=fake)
        self.assertEqual(rc, 2)
        self.assertIn("std_dml_scan_unavailable", {f["code"] for f in json.loads(out)["findings"]})

    def test_repo_language_mismatch_D(self):
        self.write(".abapgit.xml", DOT.format(lang="E"))
        self.write("src/zcl_demo.clas.abap", ABAP_OK + "* değişti\n")
        self.assertIn("language_mismatch", self.check("--all")[2])

    def test_unknown_language_mapping_warns_until_letter_given(self):
        self.set_language("DE")
        self.write(".abapgit.xml", DOT.format(lang="D"))
        self.write("src/zcl_demo.clas.abap", ABAP_OK + "* değişti\n")
        _, _, fails, warns = self.check("--all")
        self.assertIn("language_unverified", warns)
        _, _, fails, warns = self.check("--all", "--main-language-letter", "D")
        self.assertNotIn("language_unverified", warns)
        self.assertNotIn("language_mismatch", fails)
        self.assertIn("ADR_0005_D_language", fails)  # sınıf XML'i LANGU=T, proje D

    def test_dtel_labels_D(self):
        partial = FULL_LABELS.replace("<SCRTEXT_M>Demo alan</SCRTEXT_M>", "<SCRTEXT_M></SCRTEXT_M>")
        self.write("src/zdemo_dtel.dtel.xml", DTEL_XML.format(labels=partial))
        self.assertIn("ADR_0005_D_text", self.check("--all")[2])
        self.write("src/zdemo_dtel.dtel.xml", DTEL_XML.format(labels=""))
        rc, _, fails, warns = self.check("--all")
        self.assertIn("ADR_0005_D_labels_unverified", warns)
        self.assertNotIn("ADR_0005_D_text", fails)

    def test_empty_description_and_wrong_object_language_D(self):
        self.write("src/zcl_demo.clas.xml", CLAS_XML.format(name="ZCL_DEMO", lang="E", descript=""))
        fails = self.check("--all")[2]
        self.assertIn("ADR_0005_D_text", fails)
        self.assertIn("ADR_0005_D_language", fails)

    def test_outside_starting_folder_and_name_pattern(self):
        self.write("diger/zcl_demo.clas.abap", ABAP_OK)
        self.write("src/notlar.txt", "x")
        fails = self.check("--files", "diger/zcl_demo.clas.abap", "src/notlar.txt")[2]
        self.assertIn("outside_starting_folder", fails)
        self.assertIn("name_pattern", fails)

    def test_baseline_warnings(self):
        path = self.ws / ".abapgit-baseline.json"
        base = json.loads(path.read_text(encoding="utf-8"))
        base["created_utc"] = "2020-01-01T00:00:00+00:00"
        path.write_text(json.dumps(base), encoding="utf-8")
        (self.ws / "src/zdemo_dtel.dtel.xml").unlink()
        self.write("src/zcl_demo.clas.abap", ABAP_OK + "* değişti\n")
        rc, _, fails, warns = self.check("--all")
        self.assertEqual(rc, 0)
        self.assertTrue({"baseline_stale", "deleted_locally"} <= warns)
        _, _, _, warns = self.check("--files", "src/zcl_demo.clas.xml")
        self.assertIn("unchanged_selected", warns)

    def test_scope_statement_always_printed(self):
        rc, out, _ = run("check", "--root", self.ws, "--all", "--project-dir", self.project)
        self.assertIn("BAKILMAYANLAR", out)


class StatusInTests(Base):
    def test_zip_filters_text_outside_src(self):
        art = self.d / "donus.zip"
        with zipfile.ZipFile(art, "w") as zf:
            zf.writestr("aktivasyon.log", "Satır 12: hata")
            zf.writestr("src/zcl_demo.clas.abap", ABAP_OK)
            zf.writestr("ekran.bin", b"\x00\x01")
        rc, out, err = run("status-in", art, "--root", self.ws, "--label", "pull 1")
        self.assertEqual(rc, 0, err)
        saved = list((self.ws / ".abapgit-status").iterdir())
        self.assertEqual(len(saved), 1)
        self.assertTrue(saved[0].name.endswith("-pull-1-aktivasyon.log"))

    def test_text_file_and_unsupported(self):
        log = self.d / "hata.txt"
        log.write_text("hata", encoding="utf-8")
        self.assertEqual(run("status-in", log, "--root", self.ws)[0], 0)
        exe = self.d / "x.exe"
        exe.write_bytes(b"MZ")
        self.assertEqual(run("status-in", exe, "--root", self.ws)[0], 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
