# -*- coding: utf-8 -*-
"""check_fm_signature_doc_sync.py: senkron (0 bulgu) · imza farkı (EKSİK/HAYALET) · blok sınırı · bozuk girdi (ÖLÇÜLEMEDİ)."""
import json
import os
import tempfile
import unittest
from unittest import mock

from _common import run_py

SCRIPT = "check_fm_signature_doc_sync.py"

FM_SRC = """FUNCTION z_demo_fm
  IMPORTING
    VALUE(iv_bir) TYPE char10
    VALUE(iv_iki) TYPE char10 DEFAULT 'X'
  EXPORTING
    VALUE(ev_rc) TYPE i
  TABLES
    it_uc TYPE ztt_demo OPTIONAL
  EXCEPTIONS
    not_found.
  " gövde
  ev_rc = 0.
ENDFUNCTION.
"""

DOC_OK = """# TS-XX-200 — Demo
## 9. Arayüz
<!-- FM-IMZA: Z_DEMO_FM -->
| Parametre | Anlam |
|---|---|
| `IV_BIR` | birinci |
| `IV_IKI` | ikinci |
| `EV_RC` | sonuç |
| `IT_UC` | tablo |
<!-- /FM-IMZA -->
Blok DIŞI: `IS_LAYOUT` ve `IT_OUTTAB` başka bir API'nin parametresidir.
"""

DOC_DRIFT = """# TS-XX-200 — Demo
<!-- FM-IMZA: Z_DEMO_FM -->
| `IV_BIR` | birinci |
| `EV_RC` | sonuç |
| `IT_UC` | tablo |
| `IV_ESKI` | kaldırılmış parametre |
<!-- /FM-IMZA -->
"""


def _write(root, rel, text, encoding="utf-8"):
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding=encoding, newline="\n") as fh:
        fh.write(text)
    return path


def _project(root, doc=DOC_OK, src=FM_SRC, source_root=None):
    """<proje>/[sap-project.json] + <source_root>/XX/ZXX_DEMO/{functions,docs}/…"""
    sr = source_root or "SOURCE_CODES"
    if source_root:
        _write(root, "sap-project.json", json.dumps({"source_root": source_root}))
    if src is not None:
        _write(root, sr + "/XX/ZXX_DEMO/functions/Z_DEMO_FM.func.abap", src)
    if doc is not None:
        _write(root, sr + "/XX/ZXX_DEMO/docs/TS-XX-200_Demo_v1.0.md", doc)


class FmSignatureDocSyncTest(unittest.TestCase):
    def _run(self, root, *args):
        return run_py(SCRIPT, *args, cwd=root)

    def test_senkron_sifir_bulgu(self):
        with tempfile.TemporaryDirectory() as root:
            _project(root)
            r = self._run(root)
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertIn("KAPSAM (SCOPE)", r.stdout)
        self.assertIn("BU ARAÇ ŞUNLARA BAKMAZ", r.stdout)
        self.assertIn("SONUÇ: TEMİZ", r.stdout)
        self.assertNotRegex(r.stdout, r"(?m)^\s+(EKSİK|HAYALET) ")
        self.assertRegex(r.stdout, r"(?m)^\s+OK .*4 parametrenin tamamı blokta")

    def test_imza_farki_eksik_ve_hayalet_bulgu(self):
        with tempfile.TemporaryDirectory() as root:
            _project(root, doc=DOC_DRIFT)
            r = self._run(root)
            r1 = self._run(root, "--bulguda-exit1")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)      # varsayılan: uyarı
        self.assertRegex(r.stdout, r"EKSİK .*IV_IKI")
        self.assertRegex(r.stdout, r"HAYALET .*IV_ESKI")
        self.assertNotRegex(r.stdout, r"EKSİK .*IV_BIR")
        self.assertIn("SONUÇ: 1 blokta sapma", r.stdout)
        self.assertEqual(1, r1.returncode, r1.stdout + r1.stderr)

    def test_blok_disi_token_sayilmaz(self):
        with tempfile.TemporaryDirectory() as root:
            _project(root)
            r = self._run(root)
        self.assertNotIn("IS_LAYOUT", r.stdout)
        self.assertNotIn("IT_OUTTAB", r.stdout)

    def test_source_root_sap_project_json(self):
        with tempfile.TemporaryDirectory() as root:
            _project(root, doc=DOC_DRIFT, source_root="SRC")
            r = self._run(root)
        self.assertIn("SRC", r.stdout)
        self.assertRegex(r.stdout, r"EKSİK .*IV_IKI")

    def test_dogrudan_dosya_ve_kaynak_koku(self):
        with tempfile.TemporaryDirectory() as root:
            doc = _write(root, "baska/kilavuz.md", DOC_DRIFT)
            src_dir = os.path.join(root, "kaynak")
            _write(root, "kaynak/z_demo_fm.abap", FM_SRC)
            r = self._run(root, doc, "--kaynak-kok", src_dir)
        self.assertRegex(r.stdout, r"HAYALET .*IV_ESKI")

    # --- bir satırda birden çok parametre / bölüm (sessiz yarım sonuç olmamalı) -------------------
    DOC_YALNIZ_A = "<!-- FM-IMZA: Z_DEMO_FM -->\n| `IV_A` | tek |\n<!-- /FM-IMZA -->\n"

    def _tek_satir(self, imza):
        with tempfile.TemporaryDirectory() as root:
            _project(root, doc=self.DOC_YALNIZ_A, src="FUNCTION z_demo_fm\n  %s\n  ev = 1.\nENDFUNCTION.\n" % imza)
            return self._run(root)

    def test_tek_satir_iki_duz_parametre_eksik_yakalanir(self):
        r = self._tek_satir("IMPORTING iv_a TYPE c iv_b TYPE c.")
        self.assertRegex(r.stdout, r"EKSİK .*IV_B", r.stdout)
        self.assertNotIn("SONUÇ: TEMİZ", r.stdout)

    def test_tek_satir_iki_value_parametre_eksik_yakalanir(self):
        r = self._tek_satir("IMPORTING VALUE(iv_a) TYPE c VALUE(iv_b) TYPE c.")
        self.assertRegex(r.stdout, r"EKSİK .*IV_B", r.stdout)
        self.assertNotIn("SONUÇ: TEMİZ", r.stdout)

    def test_tek_satir_iki_bolum_eksik_yakalanir(self):
        r = self._tek_satir("IMPORTING iv_a TYPE c EXPORTING ev_b TYPE c.")
        self.assertRegex(r.stdout, r"EKSİK .*EV_B", r.stdout)
        self.assertNotIn("SONUÇ: TEMİZ", r.stdout)

    def test_tek_satir_karmasik_tipler_ayristirilir(self):
        r = self._tek_satir("IMPORTING iv_a TYPE REF TO zcl_demo iv_b TYPE rsmpe_titt-text DEFAULT 'A b.c' "
                            "iv_c TYPE ANY TABLE OPTIONAL EXPORTING ev_d LIKE sy-datum TABLES it_e it_f STRUCTURE zst OPTIONAL "
                            "EXCEPTIONS not_found.")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertRegex(r.stdout, r"EKSİK .*EV_D, IT_E, IT_F, IV_B, IV_C")

    def test_yorum_bicimi_baslik_varyantlari(self):
        for baslik in ("Local Interface:", "Lokale Schnittstelle:", "Global Interface:", "Update Function Module:"):
            src = ('FUNCTION z_demo_fm.\n*"----\n*"*"%s\n*"  IMPORTING\n*"     VALUE(IV_BIR) TYPE  CHAR10\n'
                   '*"     VALUE(IV_IKI) TYPE  CHAR10 DEFAULT \'X\'\n*"  EXPORTING\n*"     VALUE(EV_RC) TYPE  I\n'
                   '*"  TABLES\n*"      IT_UC STRUCTURE  ZST_DEMO OPTIONAL\n*"----\n  ev_rc = 0.\nENDFUNCTION.\n' % baslik)
            with self.subTest(baslik=baslik), tempfile.TemporaryDirectory() as root:
                _project(root, src=src)
                r = self._run(root)
                self.assertEqual(0, r.returncode, r.stdout + r.stderr)
                self.assertIn("SONUÇ: TEMİZ", r.stdout)

    YORUM_BLOK = ('*"----\n*"*"Local Interface:\n*"  IMPORTING\n*"     VALUE(IV_BIR) TYPE  CHAR10\n'
                  '*"     VALUE(IV_IKI) TYPE  CHAR10 DEFAULT \'X\'\n*"  EXPORTING\n*"     VALUE(EV_RC) TYPE  I\n'
                  '*"  TABLES\n*"      IT_UC STRUCTURE  ZST_DEMO OPTIONAL\n*"----\n')

    def _yorum_arali(self, ara):
        src = "FUNCTION z_demo_fm.\n" + ara + self.YORUM_BLOK + "  ev_rc = 0.\nENDFUNCTION.\n"
        with tempfile.TemporaryDirectory() as root:
            _project(root, doc=DOC_DRIFT, src=src)
            return self._run(root)

    def test_yorum_bicimi_arada_bos_satir_blok_okunur(self):
        r = self._yorum_arali("\n")
        self.assertRegex(r.stdout, r"EKSİK .*IV_IKI", r.stdout)

    def test_yorum_bicimi_arada_yildiz_yorum_blok_okunur(self):
        r = self._yorum_arali("* Açıklama: demo modül\n")
        self.assertRegex(r.stdout, r"EKSİK .*IV_IKI", r.stdout)

    def test_yorum_blogu_koddan_sonra_olculemedi(self):
        src = "FUNCTION z_demo_fm.\n  ev_rc = 0.\n" + self.YORUM_BLOK + "ENDFUNCTION.\n"
        with tempfile.TemporaryDirectory() as root:
            _project(root, doc=DOC_DRIFT, src=src)
            self._olculemedi(root)

    def test_tables_standard_table_of_olculemedi(self):
        with tempfile.TemporaryDirectory() as root:
            _project(root, src="FUNCTION z_demo_fm\n  TABLES it_a TYPE STANDARD TABLE OF zs it_b.\nENDFUNCTION.\n")
            r = self._olculemedi(root)
        self.assertNotRegex(r.stdout, r"EKSİK .*\bOF\b")

    def test_env_proje_dizini_testlere_sizmaz(self):
        import _common
        with mock.patch.dict(os.environ, {"AXET_SAP_PROJECT_DIR": os.path.join(tempfile.gettempdir(), "baska-proje")}):
            self.assertNotIn("AXET_SAP_PROJECT_DIR", _common._env())

    def test_yerel_arayuz_yorum_bicimi(self):
        src = ('FUNCTION z_demo_fm.\n*"----\n*"*"Local Interface:\n*"  IMPORTING\n*"     VALUE(IV_BIR) TYPE  CHAR10\n'
               '*"     VALUE(IV_IKI) TYPE  CHAR10 DEFAULT \'X\'\n*"  EXPORTING\n*"     VALUE(EV_RC) TYPE  I\n'
               '*"  TABLES\n*"      IT_UC STRUCTURE  ZST_DEMO OPTIONAL\n*"----\n  ev_rc = 0.\nENDFUNCTION.\n')
        with tempfile.TemporaryDirectory() as root:
            _project(root, src=src)
            r = self._run(root)
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertIn("SONUÇ: TEMİZ", r.stdout)

    # --- bozuk girdi → ÖLÇÜLEMEDİ (exit 2), "temiz" DEĞİL --------------------------------------
    def _olculemedi(self, root, *args):
        r = self._run(root, *args)
        self.assertEqual(2, r.returncode, r.stdout + r.stderr)
        self.assertIn("ÖLÇÜLEMEDİ", r.stdout)
        self.assertNotIn("SONUÇ: TEMİZ", r.stdout)
        return r

    def test_bozuk_kapanmamis_blok(self):
        with tempfile.TemporaryDirectory() as root:
            _project(root, doc=DOC_OK.replace("<!-- /FM-IMZA -->", ""))
            self._olculemedi(root)

    def test_bozuk_kaynak_yok(self):
        with tempfile.TemporaryDirectory() as root:
            _project(root, src=None)
            os.makedirs(os.path.join(root, "SOURCE_CODES", "XX"), exist_ok=True)
            self._olculemedi(root)

    def test_bozuk_imza_bitmiyor(self):
        with tempfile.TemporaryDirectory() as root:
            _project(root, src=FM_SRC.replace("not_found.", "not_found").replace("  ev_rc = 0.\n", ""))
            self._olculemedi(root)

    def test_bozuk_taninmayan_imza_satiri(self):
        with tempfile.TemporaryDirectory() as root:
            _project(root, src=FM_SRC.replace("VALUE(iv_iki) TYPE char10 DEFAULT 'X'", "iv_iki = garip"))
            self._olculemedi(root)

    def test_bozuk_cift_tanim(self):
        with tempfile.TemporaryDirectory() as root:
            _project(root)
            _write(root, "SOURCE_CODES/YY/ZYY_DEMO/functions/Z_DEMO_FM.func.abap", FM_SRC)
            self._olculemedi(root)

    def test_bozuk_utf8_degil(self):
        with tempfile.TemporaryDirectory() as root:
            _project(root, doc=None)
            _write(root, "SOURCE_CODES/XX/ZXX_DEMO/docs/TS-XX-200.md", DOC_OK, encoding="utf-16")
            self._olculemedi(root)

    def test_bozuk_olmayan_yol(self):
        with tempfile.TemporaryDirectory() as root:
            _project(root)
            self._olculemedi(root, os.path.join(root, "yok.md"))

    def test_blok_yok_temiz_denmez(self):
        with tempfile.TemporaryDirectory() as root:
            _project(root, doc="# TS-XX-200\nimza bloğu yok\n")
            r = self._run(root)
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertIn("DENETLENECEK BLOK YOK", r.stdout)
        self.assertNotIn("SONUÇ: TEMİZ", r.stdout)

    def test_selftest(self):
        r = run_py(SCRIPT, "--selftest")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
