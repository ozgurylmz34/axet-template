# -*- coding: utf-8 -*-
"""kd_ortam.py — check (bağımlılık tablosu, kurmaz) ve config (Chrome'a sabit cli.config.json, idempotent, ezmez).

Sahte uygulama dizinleri repo DIŞINDA geçici klasörde kurulur; tarayıcı açılmaz, ağ kullanılmaz, npm çağrılmaz.
"""
import importlib.util
import json
import os
import re
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
    env = {"PWTEST_CLI_GLOBAL_CONFIG": os.path.join(kok, "ev-yok"),
           kd_ortam.MERKEZI_ORTAM: os.path.join(kok, "merkez-yok")}  # makinedeki merkezi kurulum sonucu etkilemesin
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
        self.assertIn("tarayici_hazirla.py", r.stdout)  # proje başına npm kurulumu ÖNERİLMEZ (v0.5.4, merkezi)
        self.assertNotIn("--save-dev @playwright/cli", r.stdout)
        self.assertIn("scripts.start-mock", r.stdout)
        self.assertRegex(r.stdout, r"EKSİK\s+mockserver devDependency")
        self.assertRegex(r.stdout, r"EKSİK\s+start-mock script'i")
        self.assertRegex(r.stdout, r"EKSİK\s+playwright-cli\s+YOK")

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
            self.assertRegex(r.stdout, r"BİLGİ\s+cli.config.json kanalı\s+YOK")
            self.assertIn("varsayılanı zaten chromium + kanal chrome", r.stdout)
            call_main(kd_ortam.main, ["config", "--proje", app])
            r2 = run_py("kd_ortam.py", "check", "--proje", app, env=temiz_env(t))
        self.assertRegex(r2.stdout, r"BİLGİ\s+cli.config.json kanalı\s+Chrome kanalına sabit")

    def test_check_msedge_gecerli_secim_ve_sandbox_dosyadan(self):
        # `config --kanal msedge [--no-sandbox]` ile yazılan dosya check'te "sabit DEĞİL" sayılmamalı; sandbox satırı
        # sabit metin değil, dosyadaki launchOptions.args'ı yansıtmalı.
        with gecici_dizin() as t:
            app = tam_uygulama(os.path.join(t, "app"))
            r0 = run_py("kd_ortam.py", "check", "--proje", app, env=temiz_env(t))
            call_main(kd_ortam.main, ["config", "--proje", app, "--kanal", "msedge"])
            r1 = run_py("kd_ortam.py", "check", "--proje", app, env=temiz_env(t))
            call_main(kd_ortam.main, ["config", "--proje", app, "--kanal", "msedge", "--no-sandbox"])
            r2 = run_py("kd_ortam.py", "check", "--proje", app, env=temiz_env(t))
            yaz_json(os.path.join(app, ".playwright", "cli.config.json"),
                     {"browser": {"launchOptions": {"channel": "chrome", "executablePath": "C:/x/chrome.exe"}}})
            r3 = run_py("kd_ortam.py", "check", "--proje", app, env=temiz_env(t))
        self.assertRegex(r0.stdout, r"BİLGİ\s+cli.config.json sandbox\s+config YOK → --no-sandbox yok — aXet")
        self.assertRegex(r1.stdout, r"BİLGİ\s+cli.config.json kanalı\s+Edge kanalına sabit")
        self.assertNotIn("sabit DEĞİL", r1.stdout)
        self.assertRegex(r1.stdout, r"BİLGİ\s+cli.config.json sandbox\s+launchOptions.args'ta --no-sandbox YOK — aXet")
        self.assertRegex(r2.stdout, r"BİLGİ\s+cli.config.json kanalı\s+Edge kanalına sabit")
        self.assertRegex(r2.stdout, r"BİLGİ\s+cli.config.json sandbox\s+launchOptions.args'ta --no-sandbox VAR")
        self.assertRegex(r3.stdout, r"BİLGİ\s+cli.config.json kanalı\s+Chrome'a da Edge'e de sabit DEĞİL")
        self.assertIn("--zorla", r3.stdout)

    def test_check_msedge_sandbox_onerisi_kanali_korur_ve_calisir(self):
        # v0.5.3 bug gate: Edge'e sabit dosyada check'in önerdiği sandbox komutu `--kanal msedge` taşımalı; önerilen
        # komut AYNEN koşulunca rc 0 olmalı ve dosyaya --no-sandbox eklenmeli (eskiden rc 2 'farklı içerikli').
        import re
        import shlex
        with gecici_dizin() as t:
            app = tam_uygulama(os.path.join(t, "app"))
            call_main(kd_ortam.main, ["config", "--proje", app, "--kanal", "msedge"])
            r = run_py("kd_ortam.py", "check", "--proje", app, env=temiz_env(t))
            m = re.search(r"cli.config.json sandbox.*?`python kd_ortam.py (config [^`]*)`", r.stdout)
            self.assertIsNotNone(m, r.stdout)
            self.assertIn("--kanal msedge", m.group(1))
            argv = [a if a != "<dizin>" else app for a in shlex.split(m.group(1))]
            rc, out, _ = call_main(kd_ortam.main, argv)
            with open(os.path.join(app, ".playwright", "cli.config.json"), encoding="utf-8") as fh:
                veri = json.load(fh)
        self.assertEqual(rc, 0, out)
        self.assertIn("EKLENDİ", out)
        self.assertEqual(veri["browser"]["launchOptions"]["channel"], "msedge")
        self.assertIn("--no-sandbox", veri["browser"]["launchOptions"]["args"])

    def test_check_farkli_dosyada_sandbox_onerisi_calisir(self):
        # Sınıf taraması (v0.5.3 bug gate): check'in önerdiği sandbox komutu hiçbir kanala sabit olmayan dosyada da
        # koşulunca uygulanmalı (eskiden `--zorla`sız → rc 2 'EZİLMEDİ').
        import shlex
        with gecici_dizin() as t:
            app = tam_uygulama(os.path.join(t, "app"))
            yol = os.path.join(app, ".playwright", "cli.config.json")
            yaz_json(yol, {"browser": {"browserName": "firefox"}})
            r = run_py("kd_ortam.py", "check", "--proje", app, env=temiz_env(t))
            m = re.search(r"cli.config.json sandbox.*?`python kd_ortam.py (config [^`]*)`", r.stdout)
            self.assertIsNotNone(m, r.stdout)
            argv = [a if a != "<dizin>" else app for a in shlex.split(m.group(1))]
            rc, out, err = call_main(kd_ortam.main, argv)
            with open(yol, encoding="utf-8") as fh:
                veri = json.load(fh)
        self.assertEqual(rc, 0, out + err)
        self.assertIn("--no-sandbox", veri["browser"]["launchOptions"]["args"])

    # Sınıf kuralı (v0.5.4 Z59): check'in bastığı HER önerilen config komutu, koşulunca rc 0 vermeli ve dosyayı
    # komutun istediği hâle getirmeli. Durum → beklenen öneri sayısı (kanal satırı + sandbox satırı).
    DURUM_MATRISI = (
        ("config yok", None, 2),
        ("chrome", HEDEF, 1),
        ("chrome+no-sandbox", kd_ortam.hedef_config(no_sandbox=True), 0),
        ("msedge", kd_ortam.hedef_config("msedge"), 1),
        ("msedge+no-sandbox", kd_ortam.hedef_config("msedge", True), 0),
        ("firefox", {"browser": {"browserName": "firefox"}}, 2),
        ("executablePath", {"browser": {"launchOptions": {"channel": "chrome", "executablePath": "C:/x/chrome.exe"}}}, 2),
        ("args metin (chrome)", {"browser": {"launchOptions": {"channel": "chrome", "args": "--foo"}}}, 1),
        ("args metin (msedge)", {"browser": {"launchOptions": {"channel": "msedge", "args": "--foo"}}}, 1),
        ("JSON []", [], 2),
        ("bozuk JSON", b"{bozuk", 2),
        ("UTF-16", '{"browser": {}}'.encode("utf-16"), 2),
    )

    @staticmethod
    def _durum_kur(app, icerik):
        yol = os.path.join(app, ".playwright", "cli.config.json")
        if icerik is None:
            return yol
        if isinstance(icerik, bytes):
            os.makedirs(os.path.dirname(yol), exist_ok=True)
            with open(yol, "wb") as fh:
                fh.write(icerik)
        else:
            yaz_json(yol, icerik)
        return yol

    def test_check_onerilen_her_config_komutu_calisir_durum_matrisi(self):
        import shlex
        for ad, icerik, beklenen_sayi in self.DURUM_MATRISI:
            with self.subTest(durum=ad), gecici_dizin() as t:
                app = tam_uygulama(os.path.join(t, "app"))
                self._durum_kur(app, icerik)
                _, out, err = call_main(lambda a: kd_ortam.cmd_check(app, temiz_env(t)), [])
                self.assertNotIn("Traceback", err)
                satirlar = [s for s in out.splitlines() if re.search(r"cli.config.json (kanalı|sandbox)", s)]
                self.assertEqual(2, len(satirlar), out)
                oneriler = [m for s in satirlar for m in re.findall(r"`python kd_ortam.py (config [^`]*)`", s)]
                self.assertEqual(beklenen_sayi, len(oneriler), " | ".join(satirlar))
                # `[--kanal msedge]` isteğe bağlıdır: iki biçim de çalışmalı.
                komutlar = []
                for o in oneriler:
                    if "[--kanal msedge]" in o:
                        komutlar += [o.replace("[--kanal msedge]", ""), o.replace("[--kanal msedge]", "--kanal msedge")]
                    else:
                        komutlar.append(o)
                for komut in komutlar:
                    with gecici_dizin() as t2:
                        app2 = tam_uygulama(os.path.join(t2, "app"))
                        self._durum_kur(app2, icerik)
                        argv = [a if a != "<dizin>" else app2 for a in shlex.split(komut)]
                        rc, cout, cerr = call_main(kd_ortam.main, argv)
                        kanal = argv[argv.index("--kanal") + 1] if "--kanal" in argv else kd_ortam.KANAL
                        durum = kd_ortam.config_durumu(app2, kanal, "--no-sandbox" in argv)[0]
                    self.assertEqual(0, rc, "%s | %s → %s%s" % (ad, komut, cout, cerr))
                    self.assertEqual("uygun", durum, "%s | %s" % (ad, komut))
                    if "--zorla" in argv:  # --zorla yalnız gerektiğinde önerilir: onsuz aynı komut ezmeyi reddetmeli
                        with gecici_dizin() as t3:
                            app3 = tam_uygulama(os.path.join(t3, "app"))
                            self._durum_kur(app3, icerik)
                            argv3 = [a if a != "<dizin>" else app3 for a in shlex.split(komut) if a != "--zorla"]
                            rc3, _, _ = call_main(kd_ortam.main, argv3)
                        self.assertEqual(2, rc3, "%s | gereksiz --zorla: %s" % (ad, komut))

    def test_config_zorla_utf8_olmayan_dosyada_bayt_yedek(self):
        with gecici_dizin() as t:
            app = tam_uygulama(os.path.join(t, "app"))
            yol = os.path.join(app, ".playwright", "cli.config.json")
            os.makedirs(os.path.dirname(yol), exist_ok=True)
            eski = '{"browser": {}}'.encode("utf-16")
            with open(yol, "wb") as fh:
                fh.write(eski)
            rc, out, err = call_main(kd_ortam.main, ["config", "--proje", app, "--zorla"])
            with open(yol + ".bak", "rb") as fh:
                yedek = fh.read()
            with open(yol, encoding="utf-8") as fh:
                veri = json.load(fh)
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(yedek, eski)
        self.assertEqual(veri["browser"]["launchOptions"]["channel"], "chrome")

    def test_check_utf8_olmayan_config_cokmez(self):
        with gecici_dizin() as t:
            app = tam_uygulama(os.path.join(t, "app"))
            yol = os.path.join(app, ".playwright", "cli.config.json")
            os.makedirs(os.path.dirname(yol), exist_ok=True)
            with open(yol, "wb") as fh:
                fh.write(b"\xff\xfe{\x00}\x00")
            r = run_py("kd_ortam.py", "check", "--proje", app, env=temiz_env(t))
        self.assertNotIn("Traceback", r.stderr)
        self.assertRegex(r.stdout, r"cli.config.json kanalı\s+okunamadı")

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


class KdOrtamMerkeziTest(unittest.TestCase):
    """v0.5.4 (Z60): merkezi kurulum (<klon>/.araclar/playwright-cli) + global ~/.playwright config."""

    def _merkez(self, t):
        m = os.path.join(t, "merkez")
        yaz_json(os.path.join(m, "node_modules", "@playwright", "cli", "package.json"), {"version": "0.1.21"})
        yaz_json(os.path.join(m, "node_modules", "playwright-core", "package.json"), {"version": "1.64.0"})
        return m

    def test_merkezi_kurulum_projede_yokken_bulunur(self):
        with gecici_dizin() as t:
            app = os.path.join(t, "app")
            os.makedirs(app)
            m = self._merkez(t)
            env = dict(temiz_env(t), **{kd_ortam.MERKEZI_ORTAM: m})
            dizin, surum = kd_ortam.playwright_cli_yolu(app, env)
            core = kd_ortam.playwright_core_yolu(app, env)
        self.assertEqual("0.1.21", surum)
        self.assertTrue(dizin.startswith(m), dizin)
        self.assertEqual(os.path.join(m, "node_modules", "playwright-core"), core)

    def test_proje_kurulumu_merkeziden_once_gelir(self):
        with gecici_dizin() as t:
            app = tam_uygulama(os.path.join(t, "app"))
            env = dict(temiz_env(t), **{kd_ortam.MERKEZI_ORTAM: self._merkez(t)})
            dizin, _ = kd_ortam.playwright_cli_yolu(app, env)
        self.assertTrue(dizin.startswith(app), dizin)

    def test_global_uygunsa_sandbox_satiri_globali_soyler_uyari_yok(self):
        with gecici_dizin() as t:
            app = tam_uygulama(os.path.join(t, "app"))
            ev = os.path.join(t, "ev")
            yaz_json(os.path.join(ev, ".playwright", "cli.config.json"), kd_ortam.hedef_config("chrome", True))
            env = dict(temiz_env(t), PWTEST_CLI_GLOBAL_CONFIG=ev)
            r = run_py("kd_ortam.py", "check", "--proje", app, env=env)
        self.assertRegex(r.stdout, r"BİLGİ\s+cli.config.json sandbox\s+config YOK → global dosya geçerli: VAR")
        self.assertIn("global ~/.playwright/cli.config.json VAR (kanal chrome", r.stdout)
        self.assertNotIn("global config browser anahtarı taşıyor", r.stdout)

    def test_global_ev_ve_sandbox_ekle_paylasilan(self):
        """tarayici_hazirla.py bu iki fonksiyonu kullanır: global yol playwright-core'un kuralıyla aynı olmalı."""
        with gecici_dizin() as t:
            self.assertEqual(t, kd_ortam.global_ev({"PWTEST_CLI_GLOBAL_CONFIG": t}))
            yol = os.path.join(t, ".playwright", "cli.config.json")
            yaz_json(yol, {"browser": {"launchOptions": {"channel": "msedge", "args": ["--x"]}}, "diger": 1})
            durum, _, ham = kd_ortam.config_durumu(t, "msedge", True)
            self.assertEqual("eksik-sandbox", durum)
            kd_ortam.sandbox_ekle(yol, ham)
            with open(yol, encoding="utf-8") as fh:
                veri = json.load(fh)
        self.assertEqual(["--x", "--no-sandbox"], veri["browser"]["launchOptions"]["args"])
        self.assertEqual(1, veri["diger"])


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

    def test_config_kanal_ve_no_sandbox_yazar(self):
        with gecici_dizin() as t:
            app = os.path.join(t, "app")
            os.makedirs(app)
            rc, out, err = call_main(kd_ortam.main, ["config", "--proje", app, "--kanal", "msedge", "--no-sandbox"])
            with open(self._cfg(app), encoding="utf-8") as fh:
                veri = json.load(fh)
            rc2, out2, _ = call_main(kd_ortam.main, ["config", "--proje", app, "--kanal", "msedge", "--no-sandbox"])
        self.assertEqual(0, rc, out + err)
        self.assertEqual({"browser": {"browserName": "chromium",
                                      "launchOptions": {"channel": "msedge", "args": ["--no-sandbox"]}}}, veri)
        self.assertIn("süreç izolasyonunu kapatır", out)
        self.assertEqual(0, rc2)
        self.assertIn("ZATEN UYGUN", out2)

    def test_config_no_sandbox_uygun_dosyaya_eklenir_digerleri_korunur(self):
        with gecici_dizin() as t:
            app = os.path.join(t, "app")
            kullanici = {"outputDir": "x", "browser": {"launchOptions": {"channel": "chrome", "args": ["--lang=tr"]}}}
            yaz_json(self._cfg(app), kullanici)
            rc, out, err = call_main(kd_ortam.main, ["config", "--proje", app, "--no-sandbox"])
            with open(self._cfg(app), encoding="utf-8") as fh:
                veri = json.load(fh)
            self.assertFalse(os.path.exists(self._cfg(app) + ".bak"))
        self.assertEqual(0, rc, out + err)
        self.assertIn("EKLENDİ", out)
        self.assertEqual({"outputDir": "x", "browser": {"launchOptions": {"channel": "chrome",
                                                                          "args": ["--lang=tr", "--no-sandbox"]}}}, veri)

    def test_config_no_sandbox_farkli_kanalda_ezmez(self):
        with gecici_dizin() as t:
            app = os.path.join(t, "app")
            eski = {"browser": {"launchOptions": {"channel": "msedge"}}}
            yaz_json(self._cfg(app), eski)
            rc, _, err = call_main(kd_ortam.main, ["config", "--proje", app, "--no-sandbox"])
            with open(self._cfg(app), encoding="utf-8") as fh:
                self.assertEqual(eski, json.load(fh))
        self.assertEqual(2, rc)
        self.assertIn("EZİLMEDİ", err)

    def test_config_varsayilan_no_sandbox_istemez(self):
        # --no-sandbox'lı dosya varsayılan koşumda da uygun sayılır (argüman silinmez); argümansız dosya
        # --no-sandbox istendiğinde uygun sayılmaz.
        ns = kd_ortam.hedef_config(no_sandbox=True)
        self.assertTrue(kd_ortam._uygun_mu(ns))
        self.assertFalse(kd_ortam._uygun_mu(HEDEF, no_sandbox=True))
        self.assertFalse(kd_ortam._uygun_mu(HEDEF, kanal="msedge"))
        self.assertEqual(HEDEF, kd_ortam.HEDEF_CONFIG)

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

    def _hata_satiri_ve_dosya_korunur(self, rc, err, yol, eski):
        with open(yol, "rb") as fh:
            self.assertEqual(eski, fh.read(), "asıl dosya değişti")
        self.assertEqual(2, rc, err)
        self.assertNotIn("Traceback", err)
        self.assertTrue(err.startswith("HATA:"), err)
        self.assertIn("dokunulmadı", err)

    def test_config_zorla_yedek_alinamazsa_hata_satiri(self):
        # v0.5.4 Z59: yedek alınamazsa traceback + rc 1 değil, HATA satırı + rc 2; asıl dosya korunur.
        for ad in ("bak dizin", "bak hard link"):
            with self.subTest(durum=ad), gecici_dizin() as t:
                app = os.path.join(t, "app")
                yol = self._cfg(app)
                yaz_json(yol, {"browser": {"browserName": "firefox"}})
                with open(yol, "rb") as fh:
                    eski = fh.read()
                if ad == "bak dizin":
                    os.makedirs(yol + ".bak")
                else:
                    os.link(yol, yol + ".bak")
                rc, _, err = call_main(kd_ortam.main, ["config", "--proje", app, "--zorla"])
                self._hata_satiri_ve_dosya_korunur(rc, err, yol, eski)
                self.assertIn("yedek", err)

    def test_config_asil_dosya_yazilamazsa_hata_satiri(self):
        import stat
        for ad, veri, argv in (("zorla", {"browser": {"browserName": "firefox"}}, ["--zorla"]),
                               ("eksik-sandbox", HEDEF, ["--no-sandbox"])):
            with self.subTest(durum=ad), gecici_dizin() as t:
                app = os.path.join(t, "app")
                yol = self._cfg(app)
                yaz_json(yol, veri)
                with open(yol, "rb") as fh:
                    eski = fh.read()
                os.chmod(yol, stat.S_IREAD)
                try:
                    if os.access(yol, os.W_OK):
                        self.skipTest("salt-okunur dosya bu ortamda yazılabilir (ör. root)")
                    rc, _, err = call_main(kd_ortam.main, ["config", "--proje", app] + argv)
                finally:
                    os.chmod(yol, stat.S_IREAD | stat.S_IWRITE)
                self._hata_satiri_ve_dosya_korunur(rc, err, yol, eski)

    def test_config_yazim_yarida_kalirsa_asil_dosya_korunur(self):
        # v0.5.4 bug gate madde 3: eksik-sandbox yolu (tarayici_hazirla'da GLOBAL dosya) yedeksiz yazıyordu; açıldıktan
        # sonraki bir hata (disk dolu, fsync, rename) dosyayı yarım bırakıyordu. Artık geçici dosya + os.replace:
        # yazım/commit adımı düşerse asıl dosya bayt bayt aynı kalır ve geçici dosya artık bırakmaz.
        for adim in ("fsync", "replace"):
            with self.subTest(adim=adim), gecici_dizin() as t:
                app = os.path.join(t, "app")
                yol = self._cfg(app)
                yaz_json(yol, HEDEF)
                with open(yol, "rb") as fh:
                    eski = fh.read()
                with mock.patch.object(kd_ortam.os, adim, side_effect=OSError("disk dolu (sahte)")):
                    rc, _, err = call_main(kd_ortam.main, ["config", "--proje", app, "--no-sandbox"])
                self._hata_satiri_ve_dosya_korunur(rc, err, yol, eski)
                self.assertIn("disk dolu", err)
                self.assertEqual(["cli.config.json"], os.listdir(os.path.dirname(yol)), "geçici dosya kaldı")

    def test_yaz_basarida_none_ve_icerik_tam(self):
        with gecici_dizin() as t:
            yol = os.path.join(t, "a", "cli.config.json")
            self.assertIsNone(kd_ortam._yaz(yol, {"x": "ğ"}))
            with open(yol, encoding="utf-8") as fh:
                self.assertEqual({"x": "ğ"}, json.load(fh))
            self.assertIsNone(kd_ortam._yaz(yol, {"x": 2}))  # mevcut dosyanın üstüne (os.replace)
            with open(yol, "rb") as fh:
                self.assertEqual(b'{\n  "x": 2\n}\n', fh.read())  # LF, BOM yok
            self.assertEqual(["cli.config.json"], os.listdir(os.path.dirname(yol)))

    # --- Z64 L4: atomik os.replace'in Windows yan etkileri ------------------------------------------------------
    @unittest.skipUnless(WIN, "FILE_SHARE_DELETE'siz tutamak ve Hidden özniteliği Windows'a özgü")
    def test_yaz_hedef_kisa_sure_tutuluyorsa_tekrar_dener(self):
        # Python open() Windows'ta FILE_SHARE_DELETE'siz açar: tutamak açıkken os.replace PermissionError verir (eski
        # open(yol, "w") geçerdi). Tutamak kısa süre sonra bırakılıyorsa (virüs tarayıcı/indeksleyici) yazım tutmalı.
        with gecici_dizin() as t:
            yol = os.path.join(t, "cli.config.json")
            yaz_json(yol, {"x": 1})
            fh = open(yol, "rb")
            beklemeler = []

            def sahte_uyku(sn):
                beklemeler.append(sn)
                if not fh.closed:
                    fh.close()  # ilk beklemede tutan taraf bırakır
            try:
                with mock.patch("time.sleep", sahte_uyku):
                    sonuc = kd_ortam._yaz(yol, {"x": 2})
            finally:
                fh.close()
            self.assertIsNone(sonuc, sonuc)
            with open(yol, encoding="utf-8") as f:
                self.assertEqual({"x": 2}, json.load(f))
            self.assertEqual(1, len(beklemeler), beklemeler)
            self.assertEqual(["cli.config.json"], os.listdir(t))

    @unittest.skipUnless(WIN, "FILE_SHARE_DELETE'siz tutamak Windows'a özgü")
    def test_yaz_hedef_hep_tutuluyorsa_sinirli_denemede_metin_doner(self):
        with gecici_dizin() as t:
            yol = os.path.join(t, "cli.config.json")
            yaz_json(yol, {"x": 1})
            with open(yol, "rb") as f:
                eski = f.read()
            beklemeler = []
            with open(yol, "rb"), mock.patch("time.sleep", beklemeler.append):
                sonuc = kd_ortam._yaz(yol, {"x": 2})
            self.assertIsInstance(sonuc, str)
            self.assertIn("yazılamadı", sonuc)
            self.assertLessEqual(len(beklemeler), 3, beklemeler)
            self.assertLessEqual(sum(beklemeler), 1.0, beklemeler)
            with open(yol, "rb") as f:
                self.assertEqual(eski, f.read())
            self.assertEqual(["cli.config.json"], os.listdir(t), "geçici dosya kaldı")

    @unittest.skipUnless(WIN, "Hidden/System öznitelikleri Windows'a özgü")
    def test_yaz_gizli_ozniteligi_korur(self):
        import ctypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.GetFileAttributesW.restype = ctypes.c_uint32
        gizli = 0x2
        with gecici_dizin() as t:
            yol = os.path.join(t, "cli.config.json")
            yaz_json(yol, {"x": 1})
            self.assertTrue(k32.SetFileAttributesW(yol, gizli))
            self.assertIsNone(kd_ortam._yaz(yol, {"x": 2}))
            ozn = k32.GetFileAttributesW(yol)
            with open(yol, encoding="utf-8") as f:
                self.assertEqual({"x": 2}, json.load(f))
            self.assertTrue(ozn & gizli, "Hidden özniteliği düştü (0x%x)" % ozn)

    def test_config_hedef_yol_dizinse_hata_satiri(self):
        with gecici_dizin() as t:
            app = os.path.join(t, "app")
            os.makedirs(self._cfg(app))
            rc, _, err = call_main(kd_ortam.main, ["config", "--proje", app])
            self.assertTrue(os.path.isdir(self._cfg(app)))
        self.assertEqual(2, rc, err)
        self.assertNotIn("Traceback", err)
        self.assertTrue(err.startswith("HATA:"), err)

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
        # --no-sandbox seçeneğinin gerekçesi: playwright-cli Windows'ta HER kanalda sandbox'ı AÇIK başlatır.
        # validateBrowserConfig'te kanala bağlı ifade yalnız linux dalında; Windows (else) dalı koşulsuz `= true`.
        # Önek eşleşmesiyle sahte geçmesin diye dal yapısı bütün olarak ve `true;` ile sınırlı aranır.
        bas = kaynak.find("async function validateBrowserConfig(")
        self.assertNotEqual(-1, bas, "validateBrowserConfig kaynakta yok")
        govde = kaynak[bas:bas + 2000]
        self.assertRegex(govde, re.compile(
            r'if \(process\.platform === "linux"\) \{\s*'
            r'const \{ channel \} = browser\.launchOptions;\s*'
            r'browser\.launchOptions\.chromiumSandbox = channel !== void 0 && channel !== "chromium"[^;]*;\s*'
            r'\} else \{\s*browser\.launchOptions\.chromiumSandbox = true;\s*\}'))
        # Başlatıcı: chromiumSandbox true değilse --no-sandbox eklenir (test runner farkının kaynağı).
        self.assertRegex(kaynak, r'if \(options\.chromiumSandbox !== true\)\s*chromeArguments\.push\("--no-sandbox"\);')


if __name__ == "__main__":
    unittest.main()
