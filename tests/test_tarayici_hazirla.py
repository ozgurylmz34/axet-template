# -*- coding: utf-8 -*-
"""scripts/tarayici_hazirla.py — tarayıcı testini kullanıcı komut çalıştırmadan hazırlama (v0.5.4, Z60).

Gerçek npm/node/tarayıcı KOŞMAZ: alt süreçler sahte `calistir` ile taklit edilir; Chrome/Edge sahte kurulum
dizinlerinde "bulunur"; global config `PWTEST_CLI_GLOBAL_CONFIG` ile geçici eve yönlenir (playwright-core'un kendi
kuralı — kd_ortam.global_ev). Paylaşılan yapılandırma mantığı (kd_ortam.py) GERÇEK kopyasıyla koşar.

KAPSAM — bakılmayanlar: npm'in gerçekten kurduğu, tarayıcının gerçekten açıldığı ve aXet bash'indeki davranış
(bunlar canlı ölçüldü: maintenance/degerlendirme/2026-09-22-z60-tarayici-hazirligi-olcumu.md).
"""
from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from _helpers import AXET_HOME, GeciciTest

import tarayici_hazirla as th  # noqa: E402  (_helpers scripts/'i sys.path'e ekler)
import doctor  # noqa: E402

WIN = os.name == "nt"
SURUM = "0.1.21"


class SahteSurec:
    """subprocess.run taklidi: npm install → paket dosyasını yazar; node open/snapshot/close → senaryoya göre."""

    def __init__(self, kok: Path, npm_rc: int = 0, open_rc: int = 0, open_cikti: str = "### Browser opened",
                 snapshot_isaretli: bool = True, npm_surum: str = SURUM):
        self.kok, self.npm_rc, self.open_rc, self.open_cikti = kok, npm_rc, open_rc, open_cikti
        self.snapshot_isaretli, self.npm_surum = snapshot_isaretli, npm_surum
        self.cagrilar: list[tuple[list, dict]] = []
        self.isaret = None

    def __call__(self, komut, **kw):
        self.cagrilar.append((list(komut), kw))
        if "install" in komut:
            if self.npm_rc == 0:
                paket = th.arac_dizini(self.kok) / "node_modules" / "@playwright" / "cli" / "package.json"
                paket.parent.mkdir(parents=True, exist_ok=True)
                paket.write_text(json.dumps({"version": self.npm_surum}), encoding="utf-8")
                th.cli_js(self.kok).write_text("// sahte\n", encoding="utf-8")
                cekirdek = th.arac_dizini(self.kok) / "node_modules" / "playwright-core" / "package.json"
                cekirdek.parent.mkdir(parents=True, exist_ok=True)
                cekirdek.write_text(json.dumps({"version": "1.60.0"}), encoding="utf-8")
                return subprocess.CompletedProcess(komut, 0, "added 3 packages", "")
            return subprocess.CompletedProcess(komut, self.npm_rc, "", "npm error network ETIMEDOUT")
        alt = komut[3]
        if alt == "open":
            m = re.search(r"<h1>(.*)</h1>", komut[4])
            self.isaret = m.group(1) if m else None
            return subprocess.CompletedProcess(komut, self.open_rc, self.open_cikti, "")
        if alt == "snapshot":
            metin = '- heading "%s" [level=1]' % (self.isaret if self.snapshot_isaretli else "baska")
            return subprocess.CompletedProcess(komut, 0, metin, "")
        return subprocess.CompletedProcess(komut, 0, "Browser closed", "")

    def adlar(self) -> list[str]:
        return ["npm" if "install" in k else k[3] for k, _ in self.cagrilar]


class TarayiciHazirlaTest(GeciciTest):
    def setUp(self) -> None:
        super().setUp()
        self.kok = self.tmp / "kok"
        kd = self.kok / th.KD_ORTAM_GORELI
        kd.parent.mkdir(parents=True)
        shutil.copy2(AXET_HOME / th.KD_ORTAM_GORELI, kd)
        self.ev = self.tmp / "ev"
        self.ev.mkdir()
        self.bos = self.tmp / "bos"
        self.bos.mkdir()
        self.env = {"PWTEST_CLI_GLOBAL_CONFIG": str(self.ev), "LOCALAPPDATA": str(self.bos),
                    "PROGRAMFILES": str(self.bos), "PROGRAMFILES(X86)": str(self.bos), "HOMEDRIVE": str(self.bos)}
        self.cfg = self.ev / ".playwright" / "cli.config.json"
        # İkinci emniyet: kod PWTEST_CLI_GLOBAL_CONFIG'i yok sayarsa (ölçüldü: mutasyon M15 bu yüzden GERÇEK
        # ~/.playwright/cli.config.json'u yazdı, 2026-09-22) ev yine geçici dizin olsun.
        koruma = self.tmp / "ev-koruma"
        koruma.mkdir()
        yama = mock.patch.dict(os.environ, {"USERPROFILE": str(koruma), "HOME": str(koruma)})
        yama.start()
        self.addCleanup(yama.stop)

    # --- düzenek -----------------------------------------------------------------------------------------------
    def chrome_kur(self) -> None:
        exe = Path(self.env["LOCALAPPDATA"]) / "Google" / "Chrome" / "Application" / "chrome.exe"
        exe.parent.mkdir(parents=True, exist_ok=True)
        exe.write_bytes(b"")

    def edge_kur(self) -> None:
        pf = self.tmp / "pf86"
        exe = pf / "Microsoft" / "Edge" / "Application" / "msedge.exe"
        exe.parent.mkdir(parents=True, exist_ok=True)
        exe.write_bytes(b"")
        self.env["PROGRAMFILES(X86)"] = str(pf)

    def kos(self, surec: SahteSurec | None = None, node: tuple = ("C:/node/node.exe", "v22.19.0"),
            npm: str | None = "C:/node/npm.cmd"):
        surec = surec or SahteSurec(self.kok)
        kd = th.kd_yukle(self.kok)
        with mock.patch.object(kd, "node_durumu", return_value=node), \
                mock.patch.object(th, "kd_yukle", return_value=kd):
            durum, parcalar = th.hazirla(self.kok, dict(self.env), calistir=surec,
                                         which=lambda ad: npm if ad == "npm" else None)
        return durum, " · ".join(parcalar), surec

    def yaz_cfg(self, veri) -> bytes:
        self.cfg.parent.mkdir(parents=True, exist_ok=True)
        metin = veri if isinstance(veri, str) else json.dumps(veri)
        self.cfg.write_text(metin, encoding="utf-8")
        return self.cfg.read_bytes()

    # --- ön koşullar -------------------------------------------------------------------------------------------
    @unittest.skipUnless(WIN, "Chrome/Edge yol simülasyonu Windows arama yerlerine göre")
    def test_tarayici_yoksa_atlanir_hicbir_sey_yazilmaz(self):
        durum, metin, surec = self.kos()
        self.assertEqual("ATLANDI", durum)
        self.assertIn("kurulu Chrome/Edge yok", metin)
        self.assertEqual([], surec.cagrilar)
        self.assertFalse(self.cfg.exists())
        self.assertFalse((self.kok / ".araclar").exists())

    @unittest.skipUnless(WIN, "Chrome yol simülasyonu Windows arama yerlerine göre")
    def test_npm_yoksa_atlanir_hicbir_sey_yazilmaz(self):
        self.chrome_kur()
        durum, metin, surec = self.kos(npm=None)
        self.assertEqual("ATLANDI", durum)
        self.assertIn("npm PATH'te yok", metin)
        self.assertEqual([], surec.cagrilar)
        self.assertFalse(self.cfg.exists())
        self.assertFalse((self.kok / ".araclar").exists())

    @unittest.skipUnless(WIN, "Chrome yol simülasyonu Windows arama yerlerine göre")
    def test_node_yoksa_ve_eskiyse_atlanir(self):
        self.chrome_kur()
        self.assertIn("node PATH'te yok", self.kos(node=(None, None))[1])
        durum, metin, _ = self.kos(node=("C:/node/node.exe", "v16.20.0"))
        self.assertEqual("ATLANDI", durum)
        self.assertIn("node v16.20.0 < 18", metin)

    def test_kapatma_ortami_hicbir_sey_yapmaz(self):
        surec = SahteSurec(self.kok)
        self.env[th.KAPAT_ORTAM] = "0"
        durum, parcalar = th.hazirla(self.kok, dict(self.env), calistir=surec, which=lambda ad: "x")
        self.assertEqual("ATLANDI", durum)
        self.assertIn(th.KAPAT_ORTAM, parcalar[0])
        self.assertEqual([], surec.cagrilar)

    def test_paylasilan_modul_yoksa_atlanir(self):
        (self.kok / th.KD_ORTAM_GORELI).unlink()
        durum, parcalar = th.hazirla(self.kok, dict(self.env), calistir=SahteSurec(self.kok))
        self.assertEqual("ATLANDI", durum)
        self.assertIn("paylaşılan yapılandırma modülü yüklenemedi", parcalar[0])

    # --- ana yol -----------------------------------------------------------------------------------------------
    @unittest.skipUnless(WIN, "Chrome yol simülasyonu Windows arama yerlerine göre")
    def test_taze_kurulum_hazir_ve_ikinci_kosu_hicbir_sey_degistirmez(self):
        self.chrome_kur()
        durum, metin, surec = self.kos()
        self.assertEqual("HAZIR", durum, metin)
        self.assertEqual(["npm", "open", "snapshot", "close"], surec.adlar())
        npm_komut, npm_kw = surec.cagrilar[0]
        self.assertIn("@playwright/cli@%s" % SURUM, npm_komut)  # sürüm SABİT
        self.assertEqual(str(th.arac_dizini(self.kok)), npm_komut[npm_komut.index("--prefix") + 1])
        self.assertEqual("1", npm_kw["env"]["PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD"])  # tarayıcı İNDİRİLMEZ
        self.assertEqual({"browser": {"browserName": "chromium",
                                      "launchOptions": {"channel": "chrome", "args": ["--no-sandbox"]}}},
                         json.loads(self.cfg.read_text(encoding="utf-8")))
        self.assertEqual("# tarayici_hazirla.py: merkezi araç kurulumu, repoya girmez\n*\n",
                         (self.kok / ".araclar" / ".gitignore").read_text(encoding="utf-8"))
        self.assertIn("global config yazıldı", metin)
        # duman testi GEÇİCİ dizinde koşar (klon/proje kirlenmez) ve o dizin silinir
        cwd = surec.cagrilar[1][1]["cwd"]
        self.assertFalse(Path(cwd).exists())
        self.assertFalse(str(Path(cwd).resolve()).startswith(str(self.kok)))

        once = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in [self.cfg, self.kok / ".araclar" / ".gitignore"]}
        durum2, metin2, surec2 = self.kos()
        self.assertEqual("HAZIR", durum2, metin2)
        self.assertEqual(["open", "snapshot", "close"], surec2.adlar())  # npm YOK
        self.assertIn("zaten kurulu", metin2)
        self.assertIn("zaten uygun", metin2)
        self.assertEqual(once, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in once})

    @unittest.skipUnless(WIN, "Edge yol simülasyonu Windows arama yerlerine göre")
    def test_yalniz_edge_varsa_msedge_kanali_yazilir(self):
        self.edge_kur()
        durum, metin, _ = self.kos()
        self.assertEqual("HAZIR", durum, metin)
        self.assertEqual("msedge", json.loads(self.cfg.read_text(encoding="utf-8"))["browser"]["launchOptions"]["channel"])

    # --- global config: ezmez / ekler / dokunmaz ---------------------------------------------------------------
    @unittest.skipUnless(WIN, "Chrome yol simülasyonu Windows arama yerlerine göre")
    def test_farkli_global_config_ezilmez(self):
        self.chrome_kur()
        for veri in ({"browser": {"browserName": "firefox"}}, {"outputDir": "x"}, "{bozuk json",
                     {"browser": {"launchOptions": {"channel": "chrome", "executablePath": "C:/x.exe"}}}):
            with self.subTest(veri=veri):
                bayt = self.yaz_cfg(veri)
                durum, metin, _ = self.kos()
                self.assertEqual(bayt, self.cfg.read_bytes(), "kullanıcının global config'i EZİLDİ")
                self.assertIn("EZİLMEDİ", metin)
                # Sahte duman geçti ama bu kabukta geçmesi aXet'te --no-sandbox'sız açılışı KANITLAMAZ: ilk satır
                # düz "HAZIR" demez, ayırt edici ek taşır (v0.5.4 bug gate öneri 5). Önek korunur (tüketiciler
                # `TARAYICI: HAZIR` ile başlar).
                self.assertTrue(durum.startswith("HAZIR ("), durum)
                self.assertIn("global config uyumsuz", durum)

    @unittest.skipUnless(WIN, "Chrome yol simülasyonu Windows arama yerlerine göre")
    def test_uyumsuz_global_configte_ilk_satir_ayirt_edici_komut_satiri_yok(self):
        self.chrome_kur()
        self.yaz_cfg({"browser": {"browserName": "firefox"}})
        kd = th.kd_yukle(self.kok)
        surec = SahteSurec(self.kok)
        out = io.StringIO()
        with mock.patch.object(kd, "node_durumu", return_value=("C:/node/node.exe", "v22.19.0")), \
                mock.patch.object(th, "kd_yukle", return_value=kd), \
                mock.patch.object(th.shutil, "which", return_value="C:/node/npm.cmd"), \
                mock.patch.object(th, "sinirli_calistir", surec), \
                mock.patch.dict(os.environ, self.env), redirect_stdout(out):
            rc = th.main(["--kok", str(self.kok)])
        self.assertEqual(0, rc)
        self.assertEqual(["npm", "open", "snapshot", "close"], surec.adlar())
        satirlar = out.getvalue().splitlines()
        self.assertTrue(satirlar[0].startswith("TARAYICI: HAZIR (aXet için global config uyumsuz"), satirlar[0])
        # KOMUT satırı "global config geçerli" der — bu durumda yanlış olurdu
        self.assertFalse(any(s.startswith("KOMUT:") for s in satirlar), satirlar)

    @unittest.skipUnless(WIN, "Chrome yol simülasyonu Windows arama yerlerine göre")
    def test_uygun_global_config_dokunulmaz_edge_olsa_bile(self):
        self.chrome_kur()
        bayt = self.yaz_cfg({"browser": {"launchOptions": {"channel": "msedge", "args": ["--no-sandbox", "--x"]}},
                             "timeouts": {"action": 5}})
        durum, metin, _ = self.kos()
        self.assertEqual(bayt, self.cfg.read_bytes())
        self.assertIn("zaten uygun", metin)
        self.assertIn("kanal msedge", metin)

    @unittest.skipUnless(WIN, "Chrome yol simülasyonu Windows arama yerlerine göre")
    def test_yalniz_no_sandbox_eksikse_eklenir_digerleri_korunur(self):
        self.chrome_kur()
        self.yaz_cfg({"browser": {"browserName": "chromium", "launchOptions": {"channel": "chrome", "args": ["--x"]}},
                      "outputDir": "o"})
        durum, metin, _ = self.kos()
        veri = json.loads(self.cfg.read_text(encoding="utf-8"))
        self.assertEqual(["--x", "--no-sandbox"], veri["browser"]["launchOptions"]["args"])
        self.assertEqual("o", veri["outputDir"])
        self.assertIn("--no-sandbox eklendi", metin)
        self.assertEqual("HAZIR", durum)

    # --- global config yazılamazsa: "yazıldı/eklendi" DENMEZ, EKSİK, duman koşmaz (Z59 `_yaz` dönüşü) ----------
    @unittest.skipUnless(WIN, "Chrome yol simülasyonu Windows arama yerlerine göre")
    def test_global_config_yolu_dizinse_yazildi_denmez(self):
        self.chrome_kur()
        self.cfg.mkdir(parents=True)  # config yolunda DİZİN: open(..., "w") OSError
        durum, metin, surec = self.kos()
        self.assertEqual("EKSİK", durum, metin)
        self.assertNotIn("yazıldı", metin)
        self.assertIn("global config yazılamadı", metin)
        self.assertNotIn("open", surec.adlar())  # config olmadan aXet'te duman testi anlamsız
        self.assertTrue(self.cfg.is_dir())

    @unittest.skipUnless(WIN, "salt-okunur bit Windows'ta open('w')'yi reddeder (POSIX root'ta reddetmeyebilir)")
    def test_salt_okunur_global_config_eklendi_denmez(self):
        self.chrome_kur()
        bayt = self.yaz_cfg({"browser": {"launchOptions": {"channel": "chrome", "args": ["--x"]}}})
        os.chmod(self.cfg, 0o444)  # GeciciTest.tearDown salt-okunuru kendisi temizler
        durum, metin, surec = self.kos()
        self.assertEqual("EKSİK", durum, metin)
        self.assertNotIn("eklendi", metin)
        self.assertIn("global config yazılamadı", metin)
        self.assertEqual(bayt, self.cfg.read_bytes())
        self.assertNotIn("open", surec.adlar())

    def test_main_yazma_hatasinda_da_cikis_0(self):
        with mock.patch.object(th, "hazirla", return_value=("EKSİK", ["global config yazılamadı (x)"])):
            tampon = io.StringIO()
            with redirect_stdout(tampon):
                rc = th.main([])
        self.assertEqual(0, rc)  # güncellemeyi/kurulumu DURDURMAZ
        self.assertTrue(tampon.getvalue().startswith("TARAYICI: EKSİK — global config yazılamadı"))

    # --- başarısızlıklar: EKSİK ama çıkış yine 0 ---------------------------------------------------------------
    @unittest.skipUnless(WIN, "Chrome yol simülasyonu Windows arama yerlerine göre")
    def test_npm_basarisizsa_eksik_ve_config_yazilmaz(self):
        self.chrome_kur()
        durum, metin, surec = self.kos(SahteSurec(self.kok, npm_rc=1))
        self.assertEqual("EKSİK", durum)
        self.assertIn("npm install başarısız (rc=1)", metin)
        self.assertIn("ETIMEDOUT", metin)
        self.assertEqual(["npm"], surec.adlar())
        self.assertFalse(self.cfg.exists())

    @unittest.skipUnless(WIN, "Chrome yol simülasyonu Windows arama yerlerine göre")
    def test_npm_yanlis_surum_kurarsa_eksik(self):
        self.chrome_kur()
        durum, metin, _ = self.kos(SahteSurec(self.kok, npm_surum="0.1.20"))
        self.assertEqual("EKSİK", durum)
        self.assertIn("kurulu sürüm 0.1.20 (beklenen 0.1.21)", metin)

    @unittest.skipUnless(WIN, "Chrome yol simülasyonu Windows arama yerlerine göre")
    def test_duman_open_duserse_eksik_ve_close_yine_cagrilir(self):
        self.chrome_kur()
        s = SahteSurec(self.kok, open_rc=1, open_cikti="### Browser opened\n### Error\nError: Target crashed \n")
        durum, metin, surec = self.kos(s)
        self.assertEqual("EKSİK", durum)
        self.assertIn("open rc=1 — Error: Target crashed", metin)
        self.assertEqual("close", surec.adlar()[-1])

    @unittest.skipUnless(WIN, "Chrome yol simülasyonu Windows arama yerlerine göre")
    def test_duman_snapshotta_isaret_yoksa_eksik(self):
        self.chrome_kur()
        durum, metin, _ = self.kos(SahteSurec(self.kok, snapshot_isaretli=False))
        self.assertEqual("EKSİK", durum)
        self.assertIn("işaret YOK", metin)

    # --- kısmi kurulum kendini onarır (v0.5.4 bug gate madde 2) -------------------------------------------------
    @unittest.skipUnless(WIN, "Chrome yol simülasyonu Windows arama yerlerine göre")
    def test_kismi_kurulum_yeniden_kurulur(self):
        """package.json sürümü doğru ama giriş dosyası ya da playwright-core eksikse "zaten kurulu" DENMEZ."""
        self.chrome_kur()
        for ad, yol in (("cli_js", lambda: th.cli_js(self.kok)),
                        ("playwright-core", lambda: th.arac_dizini(self.kok) / "node_modules" / "playwright-core"
                         / "package.json")):
            with self.subTest(eksik=ad):
                durum, metin, _ = self.kos()
                self.assertEqual("HAZIR", durum, metin)
                yol().unlink()
                self.assertFalse(th.durum_oku(self.kok, dict(self.env))[0], "kısmi kurulum doctor'da hazır göründü")
                durum2, metin2, surec2 = self.kos()
                self.assertEqual("HAZIR", durum2, metin2)
                self.assertEqual("npm", surec2.adlar()[0], "kısmi kurulum 'zaten kurulu' sayıldı")
                self.assertNotIn("zaten kurulu", metin2)
                self.assertTrue(yol().is_file())

    @unittest.skipUnless(WIN, "Chrome yol simülasyonu Windows arama yerlerine göre")
    def test_npm_rc0_ama_kurulum_eksikse_eksik(self):
        self.chrome_kur()
        kok = self.kok

        class GirisDosyasizSurec(SahteSurec):
            def __call__(self, komut, **kw):
                r = super().__call__(komut, **kw)
                if "install" in komut:
                    th.cli_js(kok).unlink()
                return r
        durum, metin, surec = self.kos(GirisDosyasizSurec(self.kok))
        self.assertEqual("EKSİK", durum, metin)
        self.assertIn("playwright-cli.js", metin)
        self.assertEqual(["npm"], surec.adlar())

    def test_main_beklenmeyen_hatada_bile_cikis_0_ve_kapsam(self):
        out = io.StringIO()
        with mock.patch.object(th, "hazirla", side_effect=RuntimeError("patladı")), redirect_stdout(out):
            rc = th.main(["--kok", str(self.kok)])
        self.assertEqual(0, rc)
        satirlar = out.getvalue().splitlines()
        self.assertEqual("TARAYICI: EKSİK — beklenmeyen hata: RuntimeError: patladı", satirlar[0])
        self.assertTrue(satirlar[-1].startswith("KAPSAM (SCOPE): tarayici_hazirla"))

    def test_main_kullanim_hatasi_2(self):
        with redirect_stdout(io.StringIO()), mock.patch("sys.stderr", io.StringIO()):
            self.assertEqual(2, th.main(["--bilinmeyen"]))

    # --- salt-okunur durum (doctor) ----------------------------------------------------------------------------
    @unittest.skipUnless(WIN, "Chrome yol simülasyonu Windows arama yerlerine göre")
    def test_durum_oku_salt_okunur(self):
        self.chrome_kur()
        hazir, metin = th.durum_oku(self.kok, dict(self.env))
        self.assertFalse(hazir)
        self.assertIn("playwright-cli YOK", metin)
        self.assertIn("global config YOK", metin)
        self.assertFalse(self.cfg.exists())
        self.assertFalse((self.kok / ".araclar").exists())
        self.kos()
        hazir, metin = th.durum_oku(self.kok, dict(self.env))
        self.assertTrue(hazir, metin)
        self.assertIn('node "%s"' % th.cli_js(self.kok).as_posix(), metin)

    def test_merkezi_yol_kd_ortam_ile_ayni_ve_pw_komutu_windows_bicimi(self):
        kd = th.kd_yukle(self.kok)
        self.assertEqual(Path(kd.MERKEZI_GORELI), th.ARAC_GORELI)
        self.assertEqual(kd.PLAYWRIGHT_CLI_SURUM, SURUM)
        komut = th.pw_komutu(Path("C:/Users/x/axet"))
        self.assertEqual('node "C:/Users/x/axet/.araclar/playwright-cli/node_modules/@playwright/cli/playwright-cli.js"',
                         komut)  # /c/… değil: aXet bash'inde MODULE_NOT_FOUND (ölçüldü)

    def test_izin_kurali_betik_komutunu_bloklamaz(self):
        """%guncelle ve install.py betiği `python "<klon>/scripts/tarayici_hazirla.py"` ile çağırır; bu metin template
        deny/ask desenlerinden hiçbirine uymamalı (fnmatch simülasyonu; aXet eşleştiricisi değil)."""
        import fnmatch
        kurallar = json.loads((AXET_HOME / "config" / "permissions.json").read_text(encoding="utf-8"))["rules"]["bash"]
        komut = 'python "C:/Users/x/axet/scripts/tarayici_hazirla.py"'
        self.assertEqual([], [d for d in kurallar if fnmatch.fnmatchcase(komut, d)])


def _yasiyor(pid: int) -> bool:
    if WIN:
        import ctypes
        k32 = ctypes.windll.kernel32
        h = k32.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
        if not h:
            return False
        try:
            return k32.WaitForSingleObject(h, 0) == 0x102  # WAIT_TIMEOUT → hâlâ çalışıyor
        finally:
            k32.CloseHandle(h)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _oldur(pid: int) -> None:
    try:
        if WIN:
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, stdin=subprocess.DEVNULL,
                           timeout=30)
        else:
            os.kill(pid, 9)
    except (OSError, subprocess.SubprocessError):
        pass


class ZamanAsimiAgacTest(GeciciTest):
    """v0.5.4 bug gate madde 1 (ölçüldü): `subprocess.run(capture_output=True, timeout=…)` zaman aşımında yalnız
    doğrudan çocuğu öldürür; boruyu tutan TORUN (npm.cmd → cmd.exe → node) yaşadıkça communicate() sınırsız
    bekler (timeout=2 → 15.1 sn). Bu testler GERÇEK alt süreç koşar (npm/node DEĞİL: sahte betik + python torun)
    ve dönüşün sınır içinde geldiğini ölçer. Kırmızıda torunun uyku süresi kadar takılır."""

    UYKU = 15
    SINIR = 10.0

    def torun_kodu(self) -> str:
        """Torun: PID'ini dosyaya yazar (sayaçlı ad: duman testinde open ve close ayrı torun başlatır), sonra uyur."""
        return ("import os, time, itertools; "
                "d = r'%s'; "
                "n = next(i for i in itertools.count() if not os.path.exists(os.path.join(d, 'torun%%d.pid' %% i))); "
                "open(os.path.join(d, 'torun%%d.pid' %% n), 'w').write(str(os.getpid())); "
                "time.sleep(%d)") % (self.pid_dizini, self.UYKU)

    def setUp(self) -> None:
        super().setUp()
        self.pid_dizini = self.tmp / "pid"
        self.pid_dizini.mkdir()

    def torunlar_olmus_olmali(self) -> None:
        """Zaman aşımı yalnız dönüşü değil TORUNU da bitirmeli (dosyaya yönlendirme tek başına dönüşü sınırlar ama
        torunu yetim bırakırdı — mutasyonla ölçüldü)."""
        time.sleep(1.0)  # yetim torun PID'ini henüz yazmadıysa yazsın
        pidler = [int(p.read_text()) for p in self.pid_dizini.glob("torun*.pid") if p.read_text().strip()]
        son = time.monotonic() + 5
        yasayan = pidler
        while time.monotonic() < son:
            yasayan = [p for p in pidler if _yasiyor(p)]
            if not yasayan:
                break
            time.sleep(0.2)
        for p in yasayan:  # testin kendi kalıntısını temizle (kırmızıda)
            _oldur(p)
        self.assertEqual([], yasayan, "zaman aşımından sonra torun süreç(ler) YAŞIYOR (ağaç öldürülmedi)")

    def test_npm_zaman_asiminda_surec_agaci_olur_sinirli_surede_doner(self):
        kok = self.tmp / "kok"
        torun = '"%s" -c "%s"' % (sys.executable, self.torun_kodu())
        if WIN:  # gerçek sınıf: npm.CMD → cmd.exe → (torun) node
            npm = self.tmp / "sahte-npm.cmd"
            npm.write_text("@echo off\r\n%s\r\n" % torun.replace("%", "%%"), encoding="utf-8")  # cmd: % kaçışı
        else:
            npm = self.tmp / "sahte-npm"
            npm.write_text("#!/bin/sh\n%s\n" % torun, encoding="utf-8")
            npm.chmod(0o755)
        bas = time.monotonic()
        with mock.patch.object(th, "NPM_ZAMAN", 2):
            ok, metin = th.npm_kur(kok, str(npm), SURUM, dict(self.env))
        gecen = time.monotonic() - bas
        self.assertFalse(ok)
        self.assertIn("bitmedi", metin)
        self.assertLess(gecen, self.SINIR, "zaman aşımı süreç ağacını öldürmedi (%.1f sn)" % gecen)
        self.torunlar_olmus_olmali()

    def test_duman_zaman_asiminda_surec_agaci_olur_sinirli_surede_doner(self):
        kok = self.tmp / "kok"
        giris = th.cli_js(kok)
        giris.parent.mkdir(parents=True)
        # "node" yerine python: çocuk, stdout'u miras alan bir torun başlatıp bekler (playwright-cli oturum süreci
        # sınıfı). open ve (finally'deki) close ikisi de zaman aşımına düşer.
        giris.write_text("import subprocess, sys, time\n"
                         "subprocess.Popen([sys.executable, '-c', %r])\n"
                         "time.sleep(%d)\n" % (self.torun_kodu(), self.UYKU), encoding="utf-8")
        bas = time.monotonic()
        with mock.patch.object(th, "DUMAN_ZAMAN", 2):
            ok, metin = th.duman_testi(kok, sys.executable, dict(self.env))
        gecen = time.monotonic() - bas
        self.assertFalse(ok)
        self.assertIn("bitmedi", metin)
        # open + close iki zaman aşımı (≈2×2 sn + öldürme; ölçüldü 6.5 sn). Eski kod: iki kez UYKU (ölçüldü 30.7 sn).
        self.assertLess(gecen, self.UYKU - 2, "zaman aşımı süreç ağacını öldürmedi (%.1f sn)" % gecen)
        self.torunlar_olmus_olmali()

    def test_sinirli_calistir_normal_cikti_ve_rc(self):
        r = th.sinirli_calistir([sys.executable, "-c", "import sys; sys.stdout.reconfigure(encoding='utf-8'); "
                                 "print('merhaba ğ'); print('hata', file=sys.stderr); sys.exit(3)"],
                                env=dict(self.env), cwd=str(self.tmp), timeout=60)
        self.assertEqual(3, r.returncode)
        self.assertIn("merhaba ğ", r.stdout)
        self.assertIn("hata", r.stderr)


class GitTemizligiTest(GeciciTest):
    """Merkezi node_modules klonun git durumuna girmez (`%guncelle` "temiz ağaç" kontrolleri + yayın taraması)."""

    def test_kok_gitignore_araclari_kapsar(self):
        r = subprocess.run(["git", "-C", str(AXET_HOME), "check-ignore", "-q", "--no-index",
                            ".araclar/playwright-cli/node_modules/@playwright/cli/package.json"],
                           capture_output=True, stdin=subprocess.DEVNULL, timeout=60)
        self.assertEqual(0, r.returncode, "kök .gitignore .araclar/'ı dışlamıyor")

    def test_kok_gitignore_eski_olsa_da_dizin_kendini_dislar(self):
        repo = self.tmp / "klon"
        repo.mkdir()
        self.git(repo, "init", "-q")
        self.yaz(repo / "a.txt", "x\n")
        self.git(repo, "add", "a.txt")
        self.git(repo, "commit", "-q", "-m", "ilk")
        kd = repo / th.KD_ORTAM_GORELI
        kd.parent.mkdir(parents=True)
        shutil.copy2(AXET_HOME / th.KD_ORTAM_GORELI, kd)
        self.git(repo, "add", "-A")
        self.git(repo, "commit", "-q", "-m", "kd")
        ok, _ = th.npm_kur(repo, "npm", SURUM, {}, calistir=SahteSurec(repo))
        self.assertTrue(ok)
        self.assertTrue((th.arac_dizini(repo) / "node_modules").is_dir())
        st = self.git(repo, "status", "--porcelain", "--untracked-files=all").stdout
        self.assertEqual("", st, "merkezi kurulum git durumunda görünüyor")
        others = self.git(repo, "ls-files", "--others", "--exclude-standard").stdout
        self.assertEqual("", others)


class InstallBaglamaTest(GeciciTest):
    """install.py → tarayici_hazirla.py: ayrı süreç, çıkış kodunu değiştirmez, dry-run/uninstall'da koşmaz."""

    SAHTE = ("import sys\nprint('SAHTE-TARAYICI-KOSTU')\nsys.exit(7)\n")

    def setUp(self) -> None:
        super().setUp()
        self.klon = self.tmp / "klon"
        for rel in ("scripts/install.py", "config/permissions.json", "core/00-temel.md", "core/sap/00-sap.md",
                    "memory/MEMORY.md"):
            hedef = self.klon / rel
            hedef.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(AXET_HOME / rel, hedef)
        (self.klon / "skills").mkdir()
        (self.klon / "skills-sap").mkdir()

    def install(self, *args):
        return self.calistir(self.klon / "scripts" / "install.py", *args)

    def test_kurulumda_betik_cagrilir_basarisizligi_cikisi_degistirmez(self):
        self.yaz(self.klon / "scripts" / "tarayici_hazirla.py", self.SAHTE)
        r = self.install()
        self.assertEqual(0, r.returncode, self.cikti(r))
        self.assertIn("Tarayıcı hazırlığı:", r.stdout)
        self.assertIn("SAHTE-TARAYICI-KOSTU", r.stdout)
        # betiğin kendi çıkış kodu (7) "çalıştırılamadı" sayılmaz: durumu betiğin ilk satırı söyler (mutasyon M12)
        self.assertNotIn("çalıştırılamadı", r.stdout)
        r2 = self.install()  # "Değişiklik yok" dalı da çağırır
        self.assertEqual(0, r2.returncode, self.cikti(r2))
        self.assertIn("Değişiklik yok", r2.stdout)
        self.assertIn("SAHTE-TARAYICI-KOSTU", r2.stdout)

    def test_dry_run_ve_uninstall_cagirmaz(self):
        self.yaz(self.klon / "scripts" / "tarayici_hazirla.py", self.SAHTE)
        for args in (("--dry-run",), ("--uninstall",)):
            with self.subTest(args=args):
                r = self.install(*args)
                self.assertEqual(0, r.returncode, self.cikti(r))
                self.assertNotIn("SAHTE-TARAYICI-KOSTU", r.stdout)

    def test_betik_yoksa_atlandi_der(self):
        r = self.install()
        self.assertEqual(0, r.returncode, self.cikti(r))
        self.assertIn("TARAYICI: ATLANDI", r.stdout)

    def test_gercek_betik_kapatma_ortamiyla_hicbir_sey_yapmaz(self):
        """Bu test takımının güvencesi: _helpers AXET_TARAYICI_HAZIRLA=0 verir → gerçek betik npm'e/~'a dokunmaz."""
        shutil.copy2(AXET_HOME / "scripts" / "tarayici_hazirla.py", self.klon / "scripts" / "tarayici_hazirla.py")
        r = self.install()
        self.assertEqual(0, r.returncode, self.cikti(r))
        self.assertIn("TARAYICI: ATLANDI — AXET_TARAYICI_HAZIRLA=0", r.stdout)
        self.assertFalse((self.klon / ".araclar").exists())


class DoctorBilgiTest(unittest.TestCase):
    def setUp(self) -> None:
        doctor.results.clear()

    def tearDown(self) -> None:
        doctor.results.clear()

    def test_doctor_satiri_hic_fail_ya_da_warn_degil(self):
        for donus in ((True, "kanal chrome"), (False, "global config YOK")):
            with self.subTest(donus=donus), mock.patch.object(th, "durum_oku", return_value=donus):
                doctor.results.clear()
                doctor.check_tarayici()
                self.assertEqual(1, len(doctor.results))
                durum, metin = doctor.results[0]
                self.assertEqual("INFO", durum)
                self.assertIn("tarayıcı testi: " + ("hazır" if donus[0] else "eksik"), metin)

    def test_doctor_olcemezse_olcumedi_der(self):
        with mock.patch.object(th, "durum_oku", side_effect=OSError("x")):
            doctor.check_tarayici()
        self.assertEqual([("INFO", "tarayıcı testi: ÖLÇÜLEMEDİ (OSError: x)")], doctor.results)


if __name__ == "__main__":
    unittest.main()
