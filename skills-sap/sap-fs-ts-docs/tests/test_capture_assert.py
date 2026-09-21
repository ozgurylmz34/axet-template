# -*- coding: utf-8 -*-
"""capture_kd_screens.js doğrulama adımları (assert_no_busy · assert_text · assert_in_viewport) + varsayılan kanal.

Varsayılan kanal testi tarayıcı AÇMAZ: PLAYWRIGHT_CORE_PATH sahte bir playwright-core'a yönlendirilir; sahte
`chromium.launch` aldığı kanalı hata metnine yazar. Tarayıcılı testler yalnız SAP_FS_TS_DOCS_BROWSER_TESTS=1 ve
gerçek bir playwright-core (PLAYWRIGHT_CORE_PATH) ile koşar; sayfa file:// ile açılır (sunucu yok, port dinlenmez).
"""
import json
import os
import subprocess
import tempfile
import unittest

from _common import BROWSER_TESTS, SCRIPTS, node_path, run_node, sample

SAHTE_CORE_JS = ("exports.chromium = { launch: async (o) => { throw new Error('SAHTE-LAUNCH kanal=' + "
                 "(o.channel === undefined ? 'PAKETLI' : o.channel)); } };\n")


def _node(script, *args, env=None, cwd=None):
    e = dict(os.environ, PYTHONIOENCODING="utf-8")
    if env:
        e.update(env)
    return subprocess.run([node_path(), os.path.join(SCRIPTS, script), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=e, cwd=cwd, timeout=180)


def sahte_core(kok):
    d = os.path.join(kok, "sahte-playwright-core")
    os.makedirs(d)
    with open(os.path.join(d, "package.json"), "w", encoding="utf-8") as fh:
        json.dump({"name": "playwright-core", "version": "0.0.0-sahte", "main": "index.js"}, fh)
    with open(os.path.join(d, "index.js"), "w", encoding="utf-8") as fh:
        fh.write(SAHTE_CORE_JS)
    return d


@unittest.skipUnless(node_path(), "node bulunamadı")
class CaptureAssertConfigTest(unittest.TestCase):
    def test_dry_run_assert_adimlari_gecerli(self):
        r = run_node("capture_kd_screens.js", sample("capture", "config_assert_ok.json"), "--dry-run")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertIn("8 adım, 1 çekim, 6 doğrulama", r.stdout)

    def test_dry_run_assert_hatalari_exit_2(self):
        r = run_node("capture_kd_screens.js", sample("capture", "config_assert_bad.json"), "--dry-run")
        self.assertEqual(2, r.returncode, r.stdout + r.stderr)
        for parca in ("adım 1: assert_no_busy: timeout pozitif sayı olmalı",
                      "adım 2: assert_text: boş olmayan text gerekli",
                      "adım 3: assert_text: boş olmayan text gerekli",
                      "adım 4: assert_text: boş olmayan text gerekli",
                      "adım 5: assert_in_viewport: selector gerekli"):
            self.assertIn(parca, r.stderr)
        self.assertNotIn("bilinmeyen do=assert", r.stderr)

    def test_eski_dry_run_ciktisi_degismedi(self):
        """Doğrulama adımı olmayan yapılandırmada dry-run satırı eski biçimde kalır (geriye uyum)."""
        r = run_node("capture_kd_screens.js", sample("capture", "config_ok.json"), "--dry-run")
        self.assertIn("YAPILANDIRMA OK: 7 adım, 2 çekim (tarayıcı açılmadı)", r.stdout)


@unittest.skipUnless(node_path(), "node bulunamadı")
class VarsayilanKanalTest(unittest.TestCase):
    """Tarayıcısız: sahte playwright-core launch'a giden kanalı yakalar."""

    def _capture(self, tmp, cfg_ek=None, env=None):
        cfg = {"url": "http://localhost:8080/", "out_dir": "o", "steps": [{"do": "shot", "name": "a.png"}]}
        cfg.update(cfg_ek or {})
        p = os.path.join(tmp, "c.json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh)
        e = {"PLAYWRIGHT_CORE_PATH": sahte_core(tmp), "PDF_BROWSER_CHANNEL": ""}
        e.update(env or {})
        return _node("capture_kd_screens.js", p, env=e)

    def test_capture_varsayilan_chrome(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self._capture(tmp)
        self.assertEqual(2, r.returncode, r.stdout + r.stderr)
        self.assertIn("kanal chrome", r.stderr)
        self.assertIn("SAHTE-LAUNCH kanal=chrome", r.stderr)

    def test_capture_env_ve_config_onceligi(self):
        with tempfile.TemporaryDirectory() as tmp:
            r_env = self._capture(tmp, env={"PDF_BROWSER_CHANNEL": "msedge"})
        with tempfile.TemporaryDirectory() as tmp:
            r_cfg = self._capture(tmp, cfg_ek={"channel": "chromium"}, env={"PDF_BROWSER_CHANNEL": "msedge"})
        self.assertIn("SAHTE-LAUNCH kanal=msedge", r_env.stderr)
        self.assertIn("SAHTE-LAUNCH kanal=PAKETLI", r_cfg.stderr)  # cfg.channel env'den önce gelir

    def test_html_to_pdf_varsayilan_chrome_ve_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = os.path.join(tmp, "a.html")
            with open(html, "w", encoding="utf-8") as fh:
                fh.write("<html></html>")
            core = sahte_core(tmp)
            r = _node("html_to_pdf.js", html, os.path.join(tmp, "a.pdf"),
                      env={"PLAYWRIGHT_CORE_PATH": core, "PDF_BROWSER_CHANNEL": ""})
            r_env = _node("html_to_pdf.js", html, os.path.join(tmp, "a.pdf"),
                          env={"PLAYWRIGHT_CORE_PATH": core, "PDF_BROWSER_CHANNEL": "msedge"})
        self.assertEqual(2, r.returncode, r.stdout + r.stderr)
        self.assertIn("SAHTE-LAUNCH kanal=chrome", r.stderr)
        self.assertIn("SAHTE-LAUNCH kanal=msedge", r_env.stderr)


@unittest.skipUnless(BROWSER_TESTS, "tarayıcı testi kapalı (SAP_FS_TS_DOCS_BROWSER_TESTS=1 ile açılır)")
@unittest.skipUnless(node_path(), "node bulunamadı")
class CaptureAssertBrowserTest(unittest.TestCase):
    """Gerçek tarayıcıda (varsayılan kanal chrome) sahte UI5 sayfasına karşı: tutan adım OK, tutmayan FAIL + çıkış 1."""

    def _kos(self, durum, adimlar):
        url = "file:///" + sample("capture", "ui5_sahte.html").replace(os.sep, "/") + "?durum=" + durum
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "c.json")
            with open(p, "w", encoding="utf-8") as fh:
                json.dump({"url": url, "out_dir": "o", "viewport": {"width": 800, "height": 600},
                           "device_scale_factor": 1, "steps": adimlar}, fh)
            return _node("capture_kd_screens.js", p)

    def _ok(self, durum, adim):
        r = self._kos(durum, [adim])
        self.assertEqual(0, r.returncode, "%s %s\n%s%s" % (durum, adim, r.stdout, r.stderr))
        self.assertIn("OK   1. " + adim["do"], r.stdout)

    def _fail(self, durum, adim, parca):
        r = self._kos(durum, [adim, {"do": "shot", "name": "sonra.png"}])
        self.assertEqual(1, r.returncode, "%s %s\n%s%s" % (durum, adim, r.stdout, r.stderr))
        self.assertIn("FAIL 1. " + adim["do"], r.stdout)
        self.assertIn(parca, r.stdout)
        self.assertNotIn("sonra.png", r.stdout, "zorunlu doğrulama FAIL'inden sonra koşu durmadı")

    def test_no_busy(self):
        self._ok("bos", {"do": "assert_no_busy", "timeout": 1000})
        self._ok("artik-sinif", {"do": "assert_no_busy", "timeout": 1000})     # yalnız ebeveyn sınıfı → meşgul değil
        self._ok("gizli-mesgul", {"do": "assert_no_busy", "timeout": 1000})    # görünmeyen kontrol sayılmaz
        self._ok("yerel-kapanir", {"do": "assert_no_busy", "timeout": 5000})   # 800 ms sonra kapanır → bekler
        self._fail("yerel", {"do": "assert_no_busy", "timeout": 1000}, "tablo")
        self._fail("yerel-kapanir", {"do": "assert_no_busy", "timeout": 300}, "kapanmadı")
        self._fail("global", {"do": "assert_no_busy", "timeout": 600}, "BusyIndicator açık")
        self._fail("global-bekliyor", {"do": "assert_no_busy", "timeout": 600}, "gösterim bekliyor")
        self._fail("global-dom", {"do": "assert_no_busy", "timeout": 600}, "#sapUiBusyIndicator görünür")
        self._fail("ui5yok", {"do": "assert_no_busy", "timeout": 600}, "UI5 yüklü değil")

    def test_no_busy_freestyle_sap_m(self):
        self._fail("busydialog", {"do": "assert_no_busy", "timeout": 600}, "BusyDialog açık bd-Dialog")
        self._fail("busydialog-dom", {"do": "assert_no_busy", "timeout": 600}, "BusyDialog görünür bd-Dialog")
        self._fail("m-busy", {"do": "assert_no_busy", "timeout": 600}, "sap.m.BusyIndicator yukleniyor")
        self._ok("m-busy-gizli", {"do": "assert_no_busy", "timeout": 600})

    def test_text(self):
        self._ok("bos", {"do": "assert_text", "text": "Siparişler"})
        self._ok("bos", {"do": "assert_text", "text": "Kaydet", "selector": "#alt"})
        self._fail("bos", {"do": "assert_text", "text": "Yok böyle", "timeout": 500}, "görünmedi")
        self._fail("bos", {"do": "assert_text", "text": "Siparişler", "selector": "#alt", "timeout": 500}, "#alt")
        self._fail("bos", {"do": "assert_text", "text": "Gizli metin", "timeout": 500}, "görünmedi")  # display:none

    def test_in_viewport(self):
        self._ok("bos", {"do": "assert_in_viewport", "selector": "#baslik"})
        self._ok("bos", {"do": "assert_in_viewport", "selector": "#yarim", "partial": True})
        self._fail("bos", {"do": "assert_in_viewport", "selector": "#yarim"}, "tamamen içinde değil")
        self._fail("bos", {"do": "assert_in_viewport", "selector": "#asagi", "partial": True}, "kesişmiyor")
        self._fail("bos", {"do": "assert_in_viewport", "selector": "#gizli"}, "görünür değil")
        self._fail("bos", {"do": "assert_in_viewport", "selector": "#olmayan", "timeout": 500}, "öğe yok")


if __name__ == "__main__":
    unittest.main()
