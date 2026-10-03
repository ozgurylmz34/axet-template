# -*- coding: utf-8 -*-
"""capture_kd_screens.js doğrulama adımları (assert_no_busy · assert_text · assert_in_viewport), etkileşim adımları
(fill · press · scroll_reset — Z171), playwright-core arama sırası (merkezi klon kurulumu) + varsayılan kanal.

Etkileşim adımlarının sayfaya giden çağrıları ve arama sırası tarayıcısız ölçülür: kaydedici sahte playwright-core
(KAYITCI_CORE_JS) çağrıları stdout'a yazar; arama sırası testi script'i geçici bir sahte klon ağacına kopyalar.

Varsayılan kanal testi tarayıcı AÇMAZ: PLAYWRIGHT_CORE_PATH sahte bir playwright-core'a yönlendirilir; sahte
`chromium.launch` aldığı kanalı hata metnine yazar. Tarayıcılı testler yalnız SAP_FS_TS_DOCS_BROWSER_TESTS=1 ve
gerçek bir playwright-core (PLAYWRIGHT_CORE_PATH) ile koşar; sayfa file:// ile açılır (sunucu yok, port dinlenmez).
"""
import json
import os
import shutil
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


# Kaydedici sahte playwright-core: tarayıcı açmaz; sayfaya giden çağrıları stdout'a "SAHTE …" satırı olarak yazar.
# scrollProbe ölçümüne SAHTE_KAYIK ortam değişkeniyle (| ayraçlı liste) "hâlâ kaydırılmış" yanıtı verdirilebilir.
KAYITCI_CORE_JS = r"""
const yaz = m => console.log("SAHTE " + m);
const loc = sel => ({ first: () => ({
  fill: async (v, o) => yaz("fill sel=" + sel + " value=" + JSON.stringify(v) + " timeout=" + o.timeout),
  press: async (k, o) => yaz("press sel=" + sel + " key=" + k + " timeout=" + o.timeout),
  click: async () => yaz("click sel=" + sel),
  screenshot: async () => yaz("screenshot sel=" + sel) }) });
const page = {
  goto: async u => yaz("goto " + u),
  waitForTimeout: async ms => yaz("bekle " + ms),
  locator: loc,
  keyboard: { press: async k => yaz("klavye key=" + k) },
  screenshot: async () => yaz("screenshot sayfa"),
  evaluate: async (fn, arg) => {
    if (typeof fn === "function" && fn.name === "scrollProbe") {
      yaz("scrollProbe selector=" + arg.selector + " sifirla=" + arg.sifirla);
      if (arg.selector === "#yok") return null;
      const kayik = (!arg.sifirla && process.env.SAHTE_KAYIK) ? process.env.SAHTE_KAYIK.split("|") : [];
      return { taranan: 3, kayik };
    }
    return "8080";
  } };
exports.chromium = { launch: async () => ({
  newContext: async () => ({ newPage: async () => page }),
  close: async () => yaz("kapat") }) };
"""


def kayitci_core(dizin):
    os.makedirs(dizin)
    with open(os.path.join(dizin, "package.json"), "w", encoding="utf-8") as fh:
        json.dump({"name": "playwright-core", "version": "0.0.0-kayitci", "main": "index.js"}, fh)
    with open(os.path.join(dizin, "index.js"), "w", encoding="utf-8") as fh:
        fh.write(KAYITCI_CORE_JS)
    return dizin


def sahte_klon(kok):
    """Geçici klon ağacı: <kok>/klon/skills-sap/sap-fs-ts-docs/scripts/capture_kd_screens.js (gerçek dosyanın kopyası)."""
    klon = os.path.join(kok, "klon")
    sdir = os.path.join(klon, "skills-sap", "sap-fs-ts-docs", "scripts")
    os.makedirs(sdir)
    shutil.copy2(os.path.join(SCRIPTS, "capture_kd_screens.js"), sdir)
    return klon, os.path.join(sdir, "capture_kd_screens.js")


def _bos_npm_env(kok):
    """npm global / APPDATA adayları boş bir dizine yönelir → yalnız testin kurduğu adaylar bulunabilir."""
    bos = os.path.join(kok, "bos-ev")
    os.makedirs(bos, exist_ok=True)
    return {"PLAYWRIGHT_CORE_PATH": "", "AXET_MERKEZI_ARAC": "", "PDF_BROWSER_CHANNEL": "", "APPDATA": bos,
            "USERPROFILE": bos, "HOME": bos, "npm_config_prefix": "", "NODE_PATH": ""}


@unittest.skipUnless(node_path(), "node bulunamadı")
class EtkilesimAdimlariConfigTest(unittest.TestCase):
    """Z171: fill · press · scroll_reset yapılandırma doğrulaması (tarayıcısız)."""

    def test_dry_run_gecerli(self):
        r = run_node("capture_kd_screens.js", sample("capture", "config_etkilesim_ok.json"), "--dry-run")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertIn("YAPILANDIRMA OK: 8 adım, 1 çekim (tarayıcı açılmadı)", r.stdout)

    def test_dry_run_zorunlu_alan_eksik_exit_2(self):
        r = run_node("capture_kd_screens.js", sample("capture", "config_etkilesim_bad.json"), "--dry-run")
        self.assertEqual(2, r.returncode, r.stdout + r.stderr)
        for i in (1, 2, 3, 4):
            self.assertIn("adım %d: fill: selector ve value" % i, r.stderr)
        for i in (5, 6, 7):
            self.assertIn("adım %d: press: boş olmayan key gerekli" % i, r.stderr)
        for i in (8, 9, 10):
            self.assertIn("adım %d: scroll_reset:" % i, r.stderr)
        self.assertNotIn("adım 11", r.stderr)
        self.assertNotIn("bilinmeyen do=", r.stderr)


@unittest.skipUnless(node_path(), "node bulunamadı")
class EtkilesimAdimlariKayitciTest(unittest.TestCase):
    """Tarayıcısız: kaydedici sahte playwright-core ile adımların sayfaya hangi çağrıyı yaptığı (CI'da koşar)."""

    def _kos(self, adimlar, env=None):
        with tempfile.TemporaryDirectory() as tmp:
            core = kayitci_core(os.path.join(tmp, "core"))
            p = os.path.join(tmp, "c.json")
            with open(p, "w", encoding="utf-8") as fh:
                json.dump({"url": "http://localhost:8080/", "out_dir": "o", "steps": adimlar}, fh)
            e = {"PLAYWRIGHT_CORE_PATH": core, "PDF_BROWSER_CHANNEL": ""}
            e.update(env or {})
            return _node("capture_kd_screens.js", p, env=e)

    def test_fill_ve_press_yonlendirme(self):
        r = self._kos([{"do": "fill", "selector": "#m-inner", "value": "Kurgu Ticaret"},
                       {"do": "press", "key": "Enter"},
                       {"do": "press", "key": "ArrowDown", "selector": "#m-inner", "timeout": 1234},
                       {"do": "fill", "selector": "#not", "value": ""},
                       {"do": "shot", "name": "a.png"}])
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertIn('SAHTE fill sel=#m-inner value="Kurgu Ticaret" timeout=30000', r.stdout)
        self.assertIn("SAHTE klavye key=Enter", r.stdout)                       # selector yok → odaktaki öğe
        self.assertIn("SAHTE press sel=#m-inner key=ArrowDown timeout=1234", r.stdout)
        self.assertIn('SAHTE fill sel=#not value="" timeout=30000', r.stdout)  # boş değer = alanı temizle
        self.assertIn("OK   5. shot a.png", r.stdout)

    def test_scroll_reset_sifirla_bekle_olc(self):
        r = self._kos([{"do": "scroll_reset"}, {"do": "scroll_reset", "selector": "#tablo", "ms": 0},
                       {"do": "shot", "name": "a.png"}])
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        satirlar = [ln for ln in r.stdout.splitlines()
                    if ln.startswith("SAHTE scrollProbe") or ln.startswith("SAHTE bekle")]
        self.assertEqual(["SAHTE scrollProbe selector=null sifirla=true", "SAHTE bekle 300",
                          "SAHTE scrollProbe selector=null sifirla=false",
                          "SAHTE scrollProbe selector=#tablo sifirla=true", "SAHTE bekle 0",
                          "SAHTE scrollProbe selector=#tablo sifirla=false"], satirlar)

    def test_scroll_reset_fail_durumlari(self):
        r = self._kos([{"do": "scroll_reset", "selector": "#yok"}, {"do": "shot", "name": "a.png"}])
        self.assertEqual(1, r.returncode, r.stdout + r.stderr)
        self.assertIn("FAIL 1. scroll_reset — scroll_reset: öğe yok: #yok", r.stdout)
        self.assertNotIn("a.png", r.stdout)
        r = self._kos([{"do": "scroll_reset"}, {"do": "shot", "name": "a.png"}], env={"SAHTE_KAYIK": "genis(400,0)"})
        self.assertEqual(1, r.returncode, r.stdout + r.stderr)
        self.assertIn("1 öğe hâlâ kaydırılmış", r.stdout)
        self.assertIn("genis(400,0)", r.stdout)


@unittest.skipUnless(node_path(), "node bulunamadı")
class PlaywrightCoreAramaSirasiTest(unittest.TestCase):
    """Kapsam eki (Z169): env > merkezi klon kurulumu > npm global > require.resolve; bulunan yol tek satırda basılır.
    Script geçici bir sahte klon ağacına kopyalanır → <klon> = 3 üst dizin türetimi gerçekten ölçülür."""

    def _kos(self, tmp, env_ek=None, kur=()):
        klon, script = sahte_klon(tmp)
        for goreli in kur:
            kayitci_core(os.path.join(klon, *goreli.split("/")))
        p = os.path.join(tmp, "c.json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump({"url": "http://localhost:8080/", "out_dir": "o", "steps": [{"do": "shot", "name": "a.png"}]}, fh)
        e = dict(os.environ, PYTHONIOENCODING="utf-8")
        e.update(_bos_npm_env(tmp))
        e.update(env_ek or {})
        r = subprocess.run([node_path(), script, p], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=e, cwd=tmp, timeout=180)
        return klon, r

    def _satir(self, r):
        return next((ln for ln in r.stdout.splitlines() if ln.startswith("playwright-core: ")), None)

    def test_merkezi_klon_dogrudan(self):
        with tempfile.TemporaryDirectory() as tmp:
            klon, r = self._kos(tmp, kur=[".araclar/playwright-cli/node_modules/playwright-core"])
            beklenen = os.path.join(klon, ".araclar", "playwright-cli", "node_modules", "playwright-core")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertEqual("playwright-core: %s (kaynak: merkezi kurulum (klon .araclar/playwright-cli))" % beklenen,
                         self._satir(r))

    def test_merkezi_klon_cli_altinda(self):
        with tempfile.TemporaryDirectory() as tmp:
            klon, r = self._kos(tmp, kur=[".araclar/playwright-cli/node_modules/@playwright/cli/node_modules/"
                                          "playwright-core"])
            beklenen = os.path.join(klon, ".araclar", "playwright-cli", "node_modules", "@playwright", "cli",
                                    "node_modules", "playwright-core")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertEqual("playwright-core: %s (kaynak: merkezi kurulum (klon .araclar/playwright-cli))" % beklenen,
                         self._satir(r))

    def test_env_merkezden_once_merkez_npm_globalden_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_core = kayitci_core(os.path.join(tmp, "env-core"))
            _, r_env = self._kos(tmp, env_ek={"PLAYWRIGHT_CORE_PATH": env_core},
                                 kur=[".araclar/playwright-cli/node_modules/playwright-core"])
        self.assertEqual("playwright-core: %s (kaynak: PLAYWRIGHT_CORE_PATH)" % env_core, self._satir(r_env))
        with tempfile.TemporaryDirectory() as tmp:
            kayitci_core(os.path.join(tmp, "bos-ev", "npm", "node_modules", "playwright-core"))
            _, r_m = self._kos(tmp, kur=[".araclar/playwright-cli/node_modules/playwright-core"])
        self.assertIn("(kaynak: merkezi kurulum (klon .araclar/playwright-cli))", self._satir(r_m) or "")
        with tempfile.TemporaryDirectory() as tmp:
            kayitci_core(os.path.join(tmp, "bos-ev", "npm", "node_modules", "playwright-core"))
            _, r_g = self._kos(tmp)
        self.assertIn("(kaynak: npm global)", self._satir(r_g) or "")  # kontrol: merkez yokken eski yol çalışır

    def test_axet_merkezi_arac_ezer(self):
        with tempfile.TemporaryDirectory() as tmp:
            baska = os.path.join(tmp, "baska-merkez")
            kayitci_core(os.path.join(baska, "node_modules", "playwright-core"))
            _, r = self._kos(tmp, env_ek={"AXET_MERKEZI_ARAC": baska},
                             kur=[".araclar/playwright-cli/node_modules/playwright-core"])
        self.assertEqual("playwright-core: %s (kaynak: merkezi kurulum (AXET_MERKEZI_ARAC))"
                         % os.path.join(baska, "node_modules", "playwright-core"), self._satir(r))

    def test_hicbiri_yok_exit_2_mesaj(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, r = self._kos(tmp)
        if r.returncode == 0:
            self.skipTest("playwright-core bu ortamda require.resolve ile çözüldü; eksik bağımlılık simüle edilemedi")
        self.assertEqual(2, r.returncode, r.stdout + r.stderr)
        self.assertIn(".araclar/playwright-cli", r.stderr)
        self.assertIsNone(self._satir(r))


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


@unittest.skipUnless(BROWSER_TESTS, "tarayıcı testi kapalı (SAP_FS_TS_DOCS_BROWSER_TESTS=1 ile açılır)")
@unittest.skipUnless(node_path(), "node bulunamadı")
class EtkilesimBrowserTest(unittest.TestCase):
    """Z171 gerçek tarayıcıda: scroll_reset · fill · press (sahte sayfa durumları 'kaydirma', 'kaydirma-inat',
    'etkilesim'). Yardımcılar CaptureAssertBrowserTest'inkiyle aynıdır (o sınıfın testleri burada yeniden koşmasın
    diye miras alınmaz, yöntemler paylaşılır)."""

    SIFIR = "genis=0,0 hsb=0 icerik=0 sayfa=0"
    _kos = CaptureAssertBrowserTest._kos
    _fail = CaptureAssertBrowserTest._fail

    def test_scroll_reset_tum_sayfa(self):
        # kontrol grubu: sıfırlama olmadan durum sıfır DEĞİL (sayfa gerçekten kaydırılmış başlıyor)
        self._fail("kaydirma", {"do": "assert_text", "text": self.SIFIR, "timeout": 700}, "görünmedi")
        r = self._kos("kaydirma", [{"do": "scroll_reset"},
                                   {"do": "assert_text", "text": self.SIFIR, "timeout": 2000}])
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertIn("OK   2. assert_text", r.stdout)

    def test_scroll_reset_selector_yalniz_kapsam(self):
        r = self._kos("kaydirma", [{"do": "scroll_reset", "selector": "#genis"},
                                   {"do": "assert_text", "text": "genis=0,0 hsb=700 icerik=700 sayfa=300",
                                    "timeout": 2000}])
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self._fail("kaydirma", {"do": "scroll_reset", "selector": "#olmayan"}, "öğe yok: #olmayan")

    def test_scroll_reset_geri_yazilirsa_fail(self):
        self._fail("kaydirma-inat", {"do": "scroll_reset", "ms": 300}, "hâlâ kaydırılmış")

    def test_fill_press(self):
        r = self._kos("etkilesim", [{"do": "fill", "selector": "#musteri-inner", "value": "Kurgu Ticaret"},
                                    {"do": "assert_text", "text": "deger:Kurgu Ticaret"},
                                    {"do": "press", "key": "Enter"},
                                    {"do": "assert_text", "text": "tus:Enter@musteri-inner"},
                                    {"do": "press", "key": "Tab", "selector": "#ikinci"},
                                    {"do": "assert_text", "text": "tus:Tab@ikinci"}])
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self._fail("etkilesim", {"do": "fill", "selector": "#olmayan", "value": "x", "timeout": 500}, "fill")


if __name__ == "__main__":
    unittest.main()
