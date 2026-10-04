# -*- coding: utf-8 -*-
"""mock_sunucu.py (Z181): sunucu aXet'in arka plan işinden bağımsız başlar, hazır olunca döner, durdurma yalnız
SOYU kanıtlanan süreçleri kapatır (portu dinlemek kimlik değildir), başkasının sürecine dokunmaz.

Gerçek npm yerine SAHTE zincir: kök → ara → sunucu (python http.server, URL'yi stdout'a basar). Ağ: yalnız
127.0.0.1. SAP'ye, tarayıcıya bağlanmaz. Tek başına: python tests/test_mock_sunucu.py
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest

from _common import SCRIPTS

import mock_sunucu as M  # noqa: E402  (SCRIPTS _common'da sys.path'e eklenir)

BETIK = os.path.join(SCRIPTS, "mock_sunucu.py")
SAHTE = r'''
import http.server, os, subprocess, sys, time
rol = sys.argv[1]
if rol == "kok":
    if os.environ.get("SAHTE_YABANCI_URL"):  # fiori-tools backend satırı gibi: başka bir localhost adresi ÖNCE basılır
        print('backend: [{"path":"/sap","url":"http://localhost:%s"}]' % os.environ["SAHTE_YABANCI_URL"], flush=True)
    subprocess.Popen([sys.executable, __file__, "ara"])
    if os.environ.get("SAHTE_KOK_OLSUN"):
        sys.exit(int(os.environ["SAHTE_KOK_OLSUN"]))
    while True: time.sleep(1)
elif rol == "ara":
    time.sleep(float(os.environ.get("SAHTE_ARA_GEC") or 0))  # sunucuyu geç doğur (npx → ui5 serve gibi)
    subprocess.Popen([sys.executable, __file__, "sunucu"])
    if os.environ.get("SAHTE_KOPUK"):
        sys.exit(0)          # ara süreç kapanır: sunucu YETİM kalır (kopuk ağaç)
    while True: time.sleep(1)
else:
    if os.environ.get("SAHTE_DINLEMEZ"):
        while True: time.sleep(1)  # hiç dinlemeyen sunucu
    time.sleep(float(os.environ.get("SAHTE_GEC") or 0))
    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), http.server.SimpleHTTPRequestHandler)
    print("Server started - URL: http://localhost:%d" % s.server_address[1], flush=True)
    s.serve_forever()
'''


class MockSunucuTest(unittest.TestCase):
    def setUp(self):
        self.app = tempfile.mkdtemp(prefix="axet-mock-test-")
        with open(os.path.join(self.app, "index.html"), "w", encoding="utf-8") as fh:
            fh.write("<html>ok</html>")
        with open(os.path.join(self.app, "sahte.py"), "w", encoding="utf-8") as fh:
            fh.write(SAHTE)
        self.komut = json.dumps([sys.executable, os.path.join(self.app, "sahte.py"), "kok"])

    def _artiklar(self):
        """Bu testin sahte zincirinden hâlâ yaşayan süreçler (komut satırında bu testin geçici dizini)."""
        return [pid for pid, b in M.surec_tablosu().items() if self.app in (b.get("komut") or "")]

    def tearDown(self):
        k = M.kayit_oku(self.app)
        if k:  # test kırıldıysa bile süreç bırakma
            self._kos("durdur")
        M._oldur(self._artiklar(), None)
        shutil.rmtree(self.app, ignore_errors=True)
        for yol in M.kayit_yollari(self.app):
            try:
                os.remove(yol)
            except OSError:
                pass

    def _kos(self, *arg, env=None, zaman=120):
        e = dict(os.environ, PYTHONIOENCODING="utf-8")
        for ad in ("SAHTE_KOPUK", "SAHTE_KOK_OLSUN", "SAHTE_GEC", "SAHTE_DINLEMEZ", "SAHTE_ARA_GEC", "SAHTE_YABANCI_URL"):
            e.pop(ad, None)
        e.update(env or {})
        t0 = time.monotonic()
        p = subprocess.run([sys.executable, BETIK, *arg, "--app", self.app], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=e, timeout=zaman, stdin=subprocess.DEVNULL)
        return p.returncode, p.stdout + p.stderr, time.monotonic() - t0

    def test_baslat_doner_sunucu_yasar_durdur_agaci_kapatir(self):
        rc, out, sure = self._kos("baslat", "--komut-json", self.komut, "--zaman-asimi", "60")
        self.assertEqual(0, rc, out)
        self.assertIn("MOCK SUNUCU: HAZIR", out)
        self.assertIn("KAPSAM", out)
        k = M.kayit_oku(self.app)
        port = k["port"]
        self.assertTrue(M.port_dinleniyor(port), "araç döndükten sonra sunucu yaşamalı")
        self.assertEqual(200, M.http_durum(port))
        self.assertGreaterEqual(len(k["alt"]), 2, k)  # ara + sunucu kayıtlı
        self.assertGreaterEqual(len(self._artiklar()), 3, "pozitif kontrol: artık ölçümü süreçleri görebilmeli")
        rc2, out2, _ = self._kos("durum")
        self.assertIn("ÇALIŞIYOR", out2)
        rc3, out3, _ = self._kos("baslat", "--komut-json", self.komut)
        self.assertEqual(0, rc3, out3)
        self.assertIn("ZATEN ÇALIŞIYOR", out3)
        self.assertEqual(k["pid"], M.kayit_oku(self.app)["pid"])
        rc4, out4, _ = self._kos("durdur")
        self.assertEqual(0, rc4, out4)
        self.assertIn("DURDU", out4)
        self.assertFalse(M.port_dinleniyor(port))
        self.assertEqual([], self._artiklar(), "zincirin hepsi kapanmalı")
        self.assertIsNone(M.kayit_oku(self.app))

    def test_kopuk_agac_yetim_kapatilmaz_durust_fail(self):
        """Soyu kanıtlanamayan sunucu (ara süreci kayıttan önce kapanmış) kapatılMAZ; araç DURDU demez (bug gate
        2026-10-03, 3 tur: portu dinlemek kimlik değildir). Gerçek zincirde sunucu kökün soyundadır (ölçüldü 3/3)."""
        rc, out, _ = self._kos("baslat", "--komut-json", self.komut, env={"SAHTE_KOPUK": "1"})
        self.assertEqual(0, rc, out)
        port = M.kayit_oku(self.app)["port"]
        rc2, out2, _ = self._kos("durdur")
        self.assertEqual(1, rc2, out2)
        self.assertIn(f"port {port} hâlâ dinleniyor", out2)
        self.assertNotIn("DURDU", out2)
        self.assertTrue(M.port_dinleniyor(port), "soyu kanıtlanmayan dinleyiciye dokunulmamalı")

    def test_port_bayragi_baskasinin_dinleyicisini_benimsemez(self):
        """Bug gate 2026-10-03 (3. tur) HIGH: `--port P` ile başlatılırken P'yi ilgisiz bir süreç dinlemeye başlarsa
        araç onu "hazır" sayıp kaydediyor, `durdur` onu kapatıyordu. Port yalnız kendi log'undaki adresten alınır."""
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            p_port = s.getsockname()[1]
        e = dict(os.environ, PYTHONIOENCODING="utf-8", SAHTE_GEC="30")
        baslat = subprocess.Popen([sys.executable, BETIK, "baslat", "--app", self.app, "--komut-json", self.komut,
                                   "--port", str(p_port), "--zaman-asimi", "6"], stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=e, text=True,
                                  encoding="utf-8", errors="replace")
        time.sleep(1.5)
        ilgisiz = subprocess.Popen([sys.executable, "-m", "http.server", str(p_port), "--bind", "127.0.0.1"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
        try:
            out, _ = baslat.communicate(timeout=120)
            self.assertEqual(2, baslat.returncode, out)
            self.assertNotIn("HAZIR", out)
            self.assertNotIn(ilgisiz.pid, [a["pid"] for a in M.kayit_oku(self.app)["alt"]])
            rc2, out2, _ = self._kos("durdur")
            self.assertEqual(1, rc2, out2)
            self.assertIsNone(ilgisiz.poll(), "ilgisiz süreç kapatılmamalı")
        finally:
            ilgisiz.kill()
            ilgisiz.wait()

    def test_logda_once_gecen_yabanci_adres_hazir_sayilmaz(self):
        """Bug gate 2026-10-04 (4. tur) MEDIUM: log'daki İLK localhost adresi alınıyordu; kendi sunucumuz dinlemeden
        önce basılan başka bir adres (backend satırı) "HAZIR" sayılıyordu. Port yalnız `URL:` satırından alınır."""
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            u_port = s.getsockname()[1]
        ilgisiz = subprocess.Popen([sys.executable, "-m", "http.server", str(u_port), "--bind", "127.0.0.1"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
        try:
            bitis = time.monotonic() + 15
            while time.monotonic() < bitis and not M.port_dinleniyor(u_port):
                time.sleep(0.2)
            self.assertTrue(M.port_dinleniyor(u_port), "ön koşul: ilgisiz sunucu dinliyor")
            rc, out, _ = self._kos("baslat", "--komut-json", self.komut, "--zaman-asimi", "60",
                                   env={"SAHTE_YABANCI_URL": str(u_port), "SAHTE_GEC": "3"})
            self.assertEqual(0, rc, out)
            port = M.kayit_oku(self.app)["port"]
            self.assertNotEqual(u_port, port, out)
            self.assertNotIn(f":{u_port}/", out)
            rc2, out2, _ = self._kos("durdur")
            self.assertEqual(0, rc2, out2)
            self.assertIn(f"port {port} boş", out2)
            self.assertIsNone(ilgisiz.poll(), "ilgisiz süreç kapatılmamalı")
        finally:
            ilgisiz.kill()
            ilgisiz.wait()

    def test_baslamayan_sunucu_fail_log_kuyrugu(self):
        rc, out, _ = self._kos("baslat", "--komut-json", self.komut, env={"SAHTE_KOK_OLSUN": "3"})
        self.assertEqual(2, rc, out)
        self.assertIn("[FAIL] sunucu süreci kapandı (çıkış 3;", out)
        self.assertIn("log kuyruğu", out)
        time.sleep(1)
        self.assertEqual([], self._artiklar(), "kök kapanınca başlattığı alt süreçler yetim kalmamalı")

    def _gec_port(self):
        """Zaman aşımından sonra geç açılan sunucunun log'a yazdığı port (30 sn bekler)."""
        bitis = time.monotonic() + 30
        while time.monotonic() < bitis and not M.log_portu(M.kayit_oku(self.app)["log"]):
            time.sleep(0.5)
        port = M.log_portu(M.kayit_oku(self.app)["log"])
        self.assertTrue(port and M.port_dinleniyor(port), "ön koşul: geç açılan sunucu dinliyor")
        return port

    def test_zaman_asimi_sonrasi_durdur_gec_acilan_sunucuyu_kapatir(self):
        """Bug gate 2026-10-03 HIGH: zaman aşımı kaydı port 0 / alt [] idi, `durdur` sunucu yaşarken DURDU diyordu.
        Ara süreç kayıtlı, sunucu KAYITTAN SONRA doğuyor ve kök kapanıyor ⇒ sunucu yalnız kayıtlı ara sürecin soyundan
        kanıtlanır ve kapatılır."""
        # 15 sn: CI runner'ında süreç tablosu okuması birkaç sn sürer; 4 sn'de sunucu kayıttan ÖNCE doğdu (2026-10-04)
        rc, out, _ = self._kos("baslat", "--komut-json", self.komut, "--zaman-asimi", "2", env={"SAHTE_ARA_GEC": "15"})
        self.assertEqual(2, rc, out)
        self.assertIn("hazır olmadı", out)
        k = M.kayit_oku(self.app)
        tablo = M.surec_tablosu()
        roller = [tablo.get(a["pid"], {}).get("komut", "").rsplit(" ", 1)[-1] for a in k["alt"]]
        self.assertIn("ara", roller)
        self.assertNotIn("sunucu", roller, "ön koşul: sunucu kayıttan SONRA doğmalı")
        M._oldur([], k["pid"])  # kök (npm) kendiliğinden çıktı
        port = self._gec_port()
        rc2, out2, _ = self._kos("durdur")
        self.assertEqual(0, rc2, out2)
        self.assertIn(f"port {port} boş", out2)
        self.assertFalse(M.port_dinleniyor(port))
        self.assertEqual([], self._artiklar())

    def test_zaman_asimi_kopuk_yetim_durdurda_durust_fail(self):
        """Soyu kanıtlanamayan (ara süreci kayıttan önce kapanmış) geç sunucu kapatılMAZ; araç DURDU demez."""
        env = {"SAHTE_KOPUK": "1", "SAHTE_GEC": "5"}
        rc, out, _ = self._kos("baslat", "--komut-json", self.komut, "--zaman-asimi", "2", env=env)
        self.assertEqual(2, rc, out)
        port = self._gec_port()
        rc2, out2, _ = self._kos("durdur")
        self.assertEqual(1, rc2, out2)
        self.assertIn(f"port {port} hâlâ dinleniyor", out2)
        self.assertNotIn("DURDU", out2)

    def test_bayat_kayitta_baskasinin_sunucusu_kapatilmaz(self):
        """Bug gate 2026-10-03 (2. tur) HIGH: kayıt bayatken aynı portu dinleyen ilgisiz süreç `durdur`la ölüyordu."""
        rc, out, _ = self._kos("baslat", "--komut-json", self.komut)
        self.assertEqual(0, rc, out)
        k = M.kayit_oku(self.app)
        M._oldur([a["pid"] for a in k["alt"]], k["pid"])  # zincir araç DIŞINDA kapandı (çökme / yeniden başlatma)
        bitis = time.monotonic() + 15
        while time.monotonic() < bitis and M.port_dinleniyor(k["port"]):
            time.sleep(0.5)
        ilgisiz = subprocess.Popen([sys.executable, "-m", "http.server", str(k["port"]), "--bind", "127.0.0.1"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
        try:
            bitis = time.monotonic() + 15
            while time.monotonic() < bitis and not M.port_dinleniyor(k["port"]):
                time.sleep(0.3)
            self.assertTrue(M.port_dinleniyor(k["port"]), "ön koşul: ilgisiz süreç portu dinliyor")
            rc2, out2, _ = self._kos("durdur")
            self.assertEqual(1, rc2, out2)
            self.assertIn("hâlâ dinleniyor", out2)
            self.assertIsNone(ilgisiz.poll(), "ilgisiz süreç kapatılmamalı")
        finally:
            ilgisiz.kill()
            ilgisiz.wait()

    def test_hazir_olmayan_kayit_ikinci_baslatta_silinmez(self):
        """Bug gate 2026-10-03 MEDIUM: ikinci `baslat` yaşayan süreçlerin kaydını silip onları sahipsiz bırakıyordu."""
        env = {"SAHTE_DINLEMEZ": "1"}
        rc, out, _ = self._kos("baslat", "--komut-json", self.komut, "--zaman-asimi", "2", env=env)
        self.assertEqual(2, rc, out)
        ilk = M.kayit_oku(self.app)["pid"]
        rc2, out2, _ = self._kos("baslat", "--komut-json", self.komut, "--zaman-asimi", "2", env=env)
        self.assertEqual(2, rc2, out2)
        self.assertIn("önce `durdur`", out2)
        self.assertEqual(ilk, M.kayit_oku(self.app)["pid"])
        rc3, out3, _ = self._kos("durdur")
        self.assertEqual(1, rc3, out3)  # port hiç bilinmedi: DURDU denmez
        self.assertIn("ÖLÇÜLEMEDİ", out3)
        self.assertNotIn("DURDU", out3)
        time.sleep(1)
        self.assertEqual([], self._artiklar())

    def test_kayitsiz_durdur_hicbir_seyi_kapatmaz(self):
        rc, out, _ = self._kos("durdur")
        self.assertEqual(0, rc, out)
        self.assertIn("kayıt yok", out)

    def test_dolu_port_baslatmaz(self):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            s.listen(1)
            port = s.getsockname()[1]
            rc, out, _ = self._kos("baslat", "--komut-json", self.komut, "--port", str(port))
        self.assertEqual(2, rc, out)
        self.assertIn(f"port {port} zaten dolu", out)
        self.assertIsNone(M.kayit_oku(self.app))

    def test_package_json_yoksa_durur(self):
        rc, out, _ = self._kos("baslat")
        self.assertEqual(2, rc, out)
        self.assertIn("package.json yok", out)

    def test_canli_pid_yeniden_kullanimi_eslesmez(self):
        tablo = {100: {"ebeveyn": 1, "zaman": "A", "komut": "x"}}
        self.assertTrue(M.canli(100, "A", tablo))
        self.assertFalse(M.canli(100, "B", tablo), "aynı PID başka süreçse kapatılmamalı")
        self.assertFalse(M.canli(200, "A", tablo))
        self.assertFalse(M.canli(100, "", tablo), "zaman kaydı yoksa kimlik kanıtlanamaz")

    def test_torunlar_agaci(self):
        tablo = {1: {"ebeveyn": 0, "zaman": "10"}, 2: {"ebeveyn": 1, "zaman": "11"}, 3: {"ebeveyn": 2, "zaman": "12"},
                 4: {"ebeveyn": 9, "zaman": "13"},
                 5: {"ebeveyn": 1, "zaman": "5"},   # PID 1'in ESKİ sahibinin çocuğu: kökten önce doğmuş
                 6: {"ebeveyn": 1, "zaman": ""}}    # zamanı ölçülemeyen: alınmaz
        self.assertEqual({2, 3}, set(M.torunlar(1, tablo)))

    def test_durum_dosyasi_uygulamaya_yazilmaz(self):
        for yol in M.kayit_yollari(self.app):
            self.assertFalse(os.path.abspath(yol).startswith(os.path.abspath(self.app)), yol)


if __name__ == "__main__":
    unittest.main(verbosity=2)
