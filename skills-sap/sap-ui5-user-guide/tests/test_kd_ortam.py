# -*- coding: utf-8 -*-
"""kd_ortam.py — check (bağımlılık tablosu, kurmaz) ve config (Chrome'a sabit cli.config.json, idempotent, ezmez).

Sahte uygulama dizinleri repo DIŞINDA geçici klasörde kurulur; tarayıcı açılmaz, ağ kullanılmaz, npm çağrılmaz.
"""
import importlib.util
import json
import os
import unittest
from unittest import mock

from _common import agac_listesi, call_main, gecici_dizin, run_py, yaz_json

import kd_ortam  # noqa: E402  (SCRIPTS _common'da sys.path'e eklenir)

WIN = os.name == "nt"
HEDEF = {"browser": {"browserName": "chromium", "launchOptions": {"channel": "chrome"}}}


def tam_uygulama(kok, start_mock="fiori run --config ./ui5-mock.yaml --open test/flpSandbox.html"):
    """Tüm bileşenleri olan sahte UI5 uygulaması (paketler yalnız package.json iskeleti)."""
    yaz_json(os.path.join(kok, "package.json"), {
        "name": "zbc000-demo", "devDependencies": {"@sap-ux/ui5-middleware-fe-mockserver": "2"},
        "scripts": {"start-mock": start_mock}})
    yaz_json(os.path.join(kok, "node_modules", "@playwright", "cli", "package.json"), {"version": "0.1.21"})
    yaz_json(os.path.join(kok, "node_modules", "playwright-core", "package.json"), {"version": "1.64.0"})
    return kok


# ⚠ Chrome ortamı SÜREÇ İÇİ verilir (cmd_check(proje, env)): Windows, alt sürecin %PROGRAMFILES%'ını ortamda ne
# verilirse verilsin kendisi yeniden yazar (ölçüldü 2026-09-21: alt süreçte 'C:\bos' → 'C:\Program Files'),
# bu yüzden subprocess ile Chrome'suz ortam simüle EDİLEMEZ.
def sahte_chrome_env(kok):
    """Windows'ta Chrome'u yalnız sahte bir LOCALAPPDATA altında 'bulan' ortam (gerçek kurulumdan bağımsız)."""
    lad = os.path.join(kok, "lad")
    exe = os.path.join(lad, "Google", "Chrome", "Application", "chrome.exe")
    os.makedirs(os.path.dirname(exe))
    open(exe, "wb").close()
    bos = os.path.join(kok, "bos")
    os.makedirs(bos)
    return {"LOCALAPPDATA": lad, "PROGRAMFILES": bos, "PROGRAMFILES(X86)": bos, "HOMEDRIVE": bos}


def chromesuz_env(kok):
    bos = os.path.join(kok, "bos-c")
    os.makedirs(bos)
    return {"LOCALAPPDATA": bos, "PROGRAMFILES": bos, "PROGRAMFILES(X86)": bos, "HOMEDRIVE": bos}


def temiz_env(kok):
    """Global config ve kanal-ezen ortam değişkenleri testi etkilemesin."""
    env = {"PWTEST_CLI_GLOBAL_CONFIG": os.path.join(kok, "ev-yok")}
    for k in kd_ortam.EZEN_ORTAM:
        env[k] = ""
    return env


def sabit_node(surum):
    return mock.patch.object(kd_ortam, "node_durumu", return_value=("C:/node/node.exe", surum) if surum else (None, None))


def markdown_var(var):
    gercek = importlib.util.find_spec

    def sahte(ad, *a, **k):
        if ad == "markdown":
            return object() if var else None
        return gercek(ad, *a, **k)
    return mock.patch("importlib.util.find_spec", side_effect=sahte)


class KdOrtamCheckTest(unittest.TestCase):
    @unittest.skipUnless(WIN, "Chrome yol simülasyonu Windows arama sırasına göre")
    def test_check_tam_ortam_cikis_0(self):
        """node ve python markdown makineye bağlı → sabitlenir (yoksa bu makinede 0 yolu HİÇ koşmaz)."""
        with gecici_dizin() as t:
            app = tam_uygulama(os.path.join(t, "app"))
            env = dict(temiz_env(t), **sahte_chrome_env(t))
            with sabit_node("v22.19.0"), markdown_var(True):
                rc, out, err = call_main(lambda a: kd_ortam.cmd_check(app, env), [])
        self.assertEqual(0, rc, out + err)
        self.assertIn("SONUÇ: tamam", out)
        self.assertIn("KAPSAM (SCOPE)", out)
        self.assertNotIn("EKSİK", out)
        self.assertIn("PLAYWRIGHT_CORE_PATH=", out)
        self.assertIn(os.path.join("lad", "Google", "Chrome", "Application", "chrome.exe"), out)

    def test_check_eksik_mockserver_ve_start_mock_komut_yazar_kurmaz(self):
        with gecici_dizin() as t:
            app = os.path.join(t, "app")
            yaz_json(os.path.join(app, "package.json"), {"name": "x", "devDependencies": {}, "scripts": {}})
            once = agac_listesi(app)
            r = run_py("kd_ortam.py", "check", "--proje", app, env=temiz_env(t))
            sonra = agac_listesi(app)
        self.assertEqual(2, r.returncode, r.stdout + r.stderr)
        self.assertEqual(once, sonra, "check dizine bir şey yazdı/kurdu")
        self.assertIn("KURULUM KOMUTLARI", r.stdout)
        self.assertIn("--save-dev @sap-ux/ui5-middleware-fe-mockserver", r.stdout)
        self.assertIn("--save-dev @playwright/cli@0.1.21", r.stdout)
        self.assertIn("scripts.start-mock", r.stdout)
        self.assertRegex(r.stdout, r"EKSİK\s+mockserver devDependency")
        self.assertRegex(r.stdout, r"EKSİK\s+start-mock script'i")
        self.assertRegex(r.stdout, r"EKSİK\s+playwright-cli \(yerel\)")

    @unittest.skipUnless(WIN, "Chrome yol simülasyonu Windows arama sırasına göre")
    def test_check_chrome_yok_eksik_ve_indirme_onermez(self):
        with gecici_dizin() as t:
            app = tam_uygulama(os.path.join(t, "app"))
            rc, out, err = call_main(lambda a: kd_ortam.cmd_check(app, dict(temiz_env(t), **chromesuz_env(t))), [])
        self.assertEqual(2, rc, out + err)
        self.assertRegex(out, r"EKSİK\s+Chrome")
        self.assertNotIn("install-browser", out)
        self.assertNotIn("playwright install", out)

    @unittest.skipUnless(WIN, "Chrome yol simülasyonu Windows arama sırasına göre")
    def test_check_node_eski_ve_yok_eksik(self):
        with gecici_dizin() as t:
            app = tam_uygulama(os.path.join(t, "app"))
            env = dict(temiz_env(t), **sahte_chrome_env(t))
            with sabit_node("v16.20.0"), markdown_var(True):
                rc, out, _ = call_main(lambda a: kd_ortam.cmd_check(app, env), [])
            self.assertEqual(2, rc)
            self.assertRegex(out, r"EKSİK\s+node\s+v16.20.0")
            with sabit_node(None), markdown_var(False):
                rc, out, _ = call_main(lambda a: kd_ortam.cmd_check(app, env), [])
        self.assertEqual(2, rc)
        self.assertRegex(out, r"EKSİK\s+node\s+YOK")
        self.assertIn("python -m pip install markdown", out)

    def test_check_package_json_yok(self):
        with gecici_dizin() as t:
            app = os.path.join(t, "app")
            os.makedirs(app)
            r = run_py("kd_ortam.py", "check", "--proje", app, env=temiz_env(t))
        self.assertEqual(2, r.returncode)
        self.assertIn("package.json yok", r.stdout)

    def test_check_dizin_yok_ve_kullanim(self):
        with gecici_dizin() as t:
            r = run_py("kd_ortam.py", "check", "--proje", os.path.join(t, "yok"), env=temiz_env(t))
        self.assertEqual(2, r.returncode)
        self.assertIn("uygulama dizini yok", r.stderr)
        self.assertEqual(2, run_py("kd_ortam.py").returncode)
        self.assertEqual(2, run_py("kd_ortam.py", "check").returncode)

    def test_check_bind_notu_ve_config_bilgisi(self):
        with gecici_dizin() as t:
            app = tam_uygulama(os.path.join(t, "app"))
            r = run_py("kd_ortam.py", "check", "--proje", app, env=temiz_env(t))
            self.assertIn("127.0.0.1", r.stdout)
            self.assertIn("güvenlik duvarı", r.stdout)
            self.assertRegex(r.stdout, r"BİLGİ\s+cli.config.json \(Chrome\)\s+YOK")
            self.assertIn("varsayılanı zaten chromium + kanal chrome", r.stdout)
            call_main(kd_ortam.main, ["config", "--proje", app])
            r2 = run_py("kd_ortam.py", "check", "--proje", app, env=temiz_env(t))
        self.assertRegex(r2.stdout, r"BİLGİ\s+cli.config.json \(Chrome\)\s+Chrome kanalına sabit")

    def test_check_start_mock_uzak_erisim_uyarisi(self):
        with gecici_dizin() as t:
            app = tam_uygulama(os.path.join(t, "app"),
                               start_mock="fiori run --config ./ui5-mock.yaml --accept-remote-connections")
            r = run_py("kd_ortam.py", "check", "--proje", app, env=temiz_env(t))
        self.assertRegex(r.stdout, r"UYARI\s+start-mock host/bind\s+bulunan: --accept-remote-connections")
        self.assertIn("UZAKTAN ERİŞİME AÇIK", r.stdout)

    def test_start_mock_host_tespiti_birim(self):
        self.assertFalse(kd_ortam.start_mock_host_tespiti("fiori run --config ui5-mock.yaml")[1])
        self.assertIn("DOĞRULANMADI", kd_ortam.start_mock_host_tespiti("fiori run --config ui5-mock.yaml")[0])
        ozet, acik = kd_ortam.start_mock_host_tespiti("ui5 serve --host 0.0.0.0")
        self.assertTrue(acik)
        self.assertIn("--host 0.0.0.0", ozet)
        ozet, acik = kd_ortam.start_mock_host_tespiti("ui5 serve --host=127.0.0.1")
        self.assertFalse(acik)
        self.assertIn("--host=127.0.0.1", ozet)
        self.assertEqual(("start-mock yok — tespit yapılmadı", False), kd_ortam.start_mock_host_tespiti(None))

    def test_check_global_config_ve_ortam_uyarisi(self):
        with gecici_dizin() as t:
            app = tam_uygulama(os.path.join(t, "app"))
            ev = os.path.join(t, "ev")
            yaz_json(os.path.join(ev, ".playwright", "cli.config.json"), {"browser": {"browserName": "firefox"}})
            env = dict(temiz_env(t), PWTEST_CLI_GLOBAL_CONFIG=ev, PLAYWRIGHT_MCP_BROWSER="firefox")
            r = run_py("kd_ortam.py", "check", "--proje", app, env=env)
        self.assertIn("global config browser anahtarı taşıyor", r.stdout)
        self.assertIn("PLAYWRIGHT_MCP_BROWSER ortam değişkeni tanımlı", r.stdout)


class KdOrtamConfigTest(unittest.TestCase):
    def _cfg(self, app):
        return os.path.join(app, ".playwright", "cli.config.json")

    def test_config_yazar_ve_idempotent(self):
        with gecici_dizin() as t:
            app = os.path.join(t, "app")
            os.makedirs(app)
            rc, out, err = call_main(kd_ortam.main, ["config", "--proje", app])
            self.assertEqual(0, rc, out + err)
            self.assertIn("YAZILDI", out)
            self.assertIn("KAPSAM (SCOPE)", out)
            with open(self._cfg(app), encoding="utf-8") as fh:
                ham1 = fh.read()
            self.assertEqual(HEDEF, json.loads(ham1))
            self.assertFalse(ham1.startswith("\ufeff"), "BOM yazıldı")
            st1 = os.stat(self._cfg(app)).st_mtime_ns
            rc, out, err = call_main(kd_ortam.main, ["config", "--proje", app])
            self.assertEqual(0, rc)
            self.assertIn("ZATEN UYGUN", out)
            with open(self._cfg(app), encoding="utf-8") as fh:
                self.assertEqual(ham1, fh.read())
            self.assertEqual(st1, os.stat(self._cfg(app)).st_mtime_ns, "idempotent koşum dosyaya yeniden yazdı")
            self.assertFalse(os.path.exists(self._cfg(app) + ".bak"))

    def test_config_kullanici_ek_anahtarlari_uygunsa_dokunmaz(self):
        with gecici_dizin() as t:
            app = os.path.join(t, "app")
            kullanici = {"outputDir": "x", "browser": {"launchOptions": {"channel": "chrome", "headless": True}}}
            yaz_json(self._cfg(app), kullanici)
            rc, out, _ = call_main(kd_ortam.main, ["config", "--proje", app])
            with open(self._cfg(app), encoding="utf-8") as fh:
                self.assertEqual(kullanici, json.load(fh))
        self.assertEqual(0, rc)
        self.assertIn("ZATEN UYGUN", out)

    def test_config_farkli_dosyayi_zorlasiz_ezmez_zorlayla_yedekler(self):
        with gecici_dizin() as t:
            app = os.path.join(t, "app")
            eski = {"browser": {"browserName": "chromium", "launchOptions": {"channel": "msedge"}}}
            yaz_json(self._cfg(app), eski)
            with open(self._cfg(app), encoding="utf-8") as fh:
                ham = fh.read()
            rc, out, err = call_main(kd_ortam.main, ["config", "--proje", app])
            self.assertEqual(2, rc)
            self.assertIn("EZİLMEDİ", err)
            with open(self._cfg(app), encoding="utf-8") as fh:
                self.assertEqual(ham, fh.read(), "--zorla olmadan dosya değişti")
            rc, out, err = call_main(kd_ortam.main, ["config", "--proje", app, "--zorla"])
            self.assertEqual(0, rc, out + err)
            with open(self._cfg(app), encoding="utf-8") as fh:
                self.assertEqual(HEDEF, json.load(fh))
            with open(self._cfg(app) + ".bak", encoding="utf-8") as fh:
                self.assertEqual(ham, fh.read())

    def test_config_farkli_sayilanlar(self):
        for veri in ({"browser": {"browserName": "firefox", "launchOptions": {"channel": "chrome"}}},
                     {"browser": {"launchOptions": {"channel": "chrome", "executablePath": "C:/x/chrome.exe"}}},
                     {"browser": {"cdpEndpoint": "cdp-uc-noktasi", "launchOptions": {"channel": "chrome"}}},
                     {"browser": {"browserName": "chromium"}}, {"allowUnrestrictedFileAccess": True}, []):
            self.assertFalse(kd_ortam._uygun_mu(veri), veri)
        self.assertTrue(kd_ortam._uygun_mu(HEDEF))

    def test_config_bozuk_json_ezilmez(self):
        with gecici_dizin() as t:
            app = os.path.join(t, "app")
            os.makedirs(os.path.join(app, ".playwright"))
            with open(self._cfg(app), "w", encoding="utf-8") as fh:
                fh.write("{bozuk")
            rc, _, err = call_main(kd_ortam.main, ["config", "--proje", app])
            with open(self._cfg(app), encoding="utf-8") as fh:
                self.assertEqual("{bozuk", fh.read())
        self.assertEqual(2, rc)
        self.assertIn("JSON değil", err)

    def test_config_dizin_yok(self):
        with gecici_dizin() as t:
            rc, _, err = call_main(kd_ortam.main, ["config", "--proje", os.path.join(t, "yok")])
        self.assertEqual(2, rc)
        self.assertIn("uygulama dizini yok", err)


@unittest.skipUnless(os.environ.get("PLAYWRIGHT_CORE_PATH"), "PLAYWRIGHT_CORE_PATH verilmedi — şema kaynak testi atlandı")
class KdOrtamSemaKaynakTest(unittest.TestCase):
    """Yazılan anahtarlar kurulu playwright-core'un config şemasında var mı (tahmin değil, kaynaktan)."""

    def test_anahtarlar_kaynakta(self):
        bundle = os.path.join(os.environ["PLAYWRIGHT_CORE_PATH"], "lib", "coreBundle.js")
        if not os.path.isfile(bundle):
            self.skipTest("coreBundle.js yok: %s" % bundle)
        with open(bundle, encoding="utf-8", errors="replace") as fh:
            kaynak = fh.read()
        for anahtar in ('"browser.browserName": "string"', '"browser.launchOptions.channel": "string"',
                        'resolve(".playwright", "cli.config.json")'):
            self.assertIn(anahtar, kaynak)
        self.assertIn('"win32": `\\\\Google\\\\Chrome\\\\Application\\\\chrome.exe`', kaynak)


if __name__ == "__main__":
    unittest.main()
