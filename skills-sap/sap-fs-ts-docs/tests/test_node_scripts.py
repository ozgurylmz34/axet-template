# -*- coding: utf-8 -*-
"""Node script'leri: sözdizimi, yapılandırma doğrulaması (tarayıcısız), kullanım hataları; isteğe bağlı uçtan uca PDF."""
import importlib.util
import os
import subprocess
import tempfile
import unittest

from _common import BROWSER_TESTS, TEMPLATES, node_path, run_node, run_py, sample


@unittest.skipUnless(node_path(), "node bulunamadı")
class NodeScriptsTest(unittest.TestCase):
    def test_syntax(self):
        for js in ("html_to_pdf.js", "capture_kd_screens.js"):
            r = subprocess.run([node_path(), "--check", os.path.join(os.path.dirname(__file__), "..", "scripts", js)],
                               capture_output=True, text=True)
            self.assertEqual(0, r.returncode, js + r.stderr)

    def test_capture_dry_run_ok(self):
        r = run_node("capture_kd_screens.js", sample("capture", "config_ok.json"), "--dry-run")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertIn("7 adım, 2 çekim", r.stdout)
        self.assertIn("KAPSAM (SCOPE)", r.stdout)

    def test_capture_bad_config_exit_2(self):
        r = run_node("capture_kd_screens.js", sample("capture", "config_bad.json"), "--dry-run")
        self.assertEqual(2, r.returncode)
        for part in (".png uzantılı", "bilinmeyen do=teleport", "data_file yok", "aynı çekim adı"):
            self.assertIn(part, r.stderr)

    def test_capture_usage_exit_2(self):
        self.assertEqual(2, run_node("capture_kd_screens.js").returncode)

    def test_html_to_pdf_usage_and_missing_input(self):
        self.assertEqual(2, run_node("html_to_pdf.js").returncode)
        r = run_node("html_to_pdf.js", sample("html", "yok.html"), "yok.pdf")
        self.assertEqual(2, r.returncode)
        self.assertIn("girdi yok", r.stderr)

    def test_html_to_pdf_check_reports_state(self):
        r = run_node("html_to_pdf.js", "--check")
        self.assertIn(r.returncode, (0, 2))
        self.assertTrue("playwright-core:" in r.stdout or "npm install playwright-core" in r.stderr)

    def test_playwright_missing_message(self):
        env = dict(os.environ, APPDATA=os.devnull, USERPROFILE=os.devnull, HOME=os.devnull, npm_config_prefix="",
                   NODE_PATH="", PLAYWRIGHT_CORE_PATH="")
        with tempfile.TemporaryDirectory() as tmp:
            html = os.path.join(tmp, "a.html")
            with open(html, "w", encoding="utf-8") as fh:
                fh.write("<html></html>")
            r = subprocess.run([node_path(), os.path.join(os.path.dirname(__file__), "..", "scripts", "html_to_pdf.js"),
                                html, os.path.join(tmp, "a.pdf")], capture_output=True, text=True, encoding="utf-8",
                               errors="replace", env=env, cwd=tmp)
        if r.returncode == 0:
            self.skipTest("playwright-core bu ortamda başka yoldan çözüldü; eksik bağımlılık simüle edilemedi")
        self.assertEqual(2, r.returncode, r.stdout + r.stderr)
        self.assertIn("npm install playwright-core", r.stderr)


@unittest.skipUnless(BROWSER_TESTS, "tarayıcı testi kapalı (SAP_FS_TS_DOCS_BROWSER_TESTS=1 ile açılır)")
@unittest.skipUnless(importlib.util.find_spec("markdown"), "python markdown kurulu değil")
class BrowserPdfTest(unittest.TestCase):
    def test_kd_template_pdf_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = os.path.join(tmp, "KD-XX-001_Sablon.html")
            pdf = os.path.join(tmp, "KD-XX-001_Sablon.pdf")
            r = run_py("build_doc_pdf.py", os.path.join(TEMPLATES, "KD-template.md"), html, "--pdf-out", pdf, timeout=300)
            self.assertEqual(0, r.returncode, r.stdout + r.stderr)
            v = run_py("verify_doc_html.py", html, "--pdf", pdf, "--min-pdf-links", "14")
            self.assertEqual(0, v.returncode, v.stdout)
            self.assertIn("bağlantı ek açıklaması 14", v.stdout)


if __name__ == "__main__":
    unittest.main()
