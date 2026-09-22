#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_ui_smoke.py: hesap-kilidi güvenli ön kontrol (200/401) ve ön koşul dalları. Playwright KOŞTURULMAZ."""
from __future__ import annotations

import importlib.util
import unittest

import _helpers as H

S = "ui-smoke/run_ui_smoke.py"


def _modul():
    spec = importlib.util.spec_from_file_location("run_ui_smoke_t", H.SCRIPTS / "ui-smoke" / "run_ui_smoke.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


R = _modul()


class TestSmoke(unittest.TestCase):
    def test_auth_on_kontrol(self):
        H.proxy_bypass_surec_ici()
        with H.SahteSunucu({"/sap/opu/odata/sap/": b"ok"}) as srv:
            iyi = R.auth_on_kontrol(srv.url, (H.KULLANICI, H.PAROLA))
            kotu = R.auth_on_kontrol(srv.url, (H.KULLANICI, "yanlis"))
            istek = len(srv.istekler)
        ok = iyi == 200 and kotu == 401 and istek == 2
        H.kaydet("smoke: ön kontrol doğru=200, yanlış=401, tek istek/deneme", "200/401/2", f"{iyi}/{kotu}/{istek}", ok)
        self.assertTrue(ok)

    def test_playwright_yok(self):
        rc, out = H.kos(S, "--port", "1", kimlik=True)
        kurulu = R.playwright_kurulu()
        beklenen = 2 if not kurulu else None
        ok = (rc == 2 and "kurulu değil" in out) if not kurulu else True
        H.kaydet("smoke: playwright kurulu değil → DUR, kurulum YAPMAZ", f"rc={beklenen}", f"rc={rc} kurulu={kurulu}", ok)
        self.assertTrue(ok, out)

    def test_kanal_ortami(self):
        taban = {"PATH": "x", "SMOKE_BROWSER_CHANNEL": "dis-kabuk", "SMOKE_SPEC": "eski.spec.ts"}
        varsayilan = R.smoke_env("http://127.0.0.1:1", taban=taban)
        kanalli = R.smoke_env("http://127.0.0.1:1", kanal="msedge", taban=taban)
        ok = ("SMOKE_BROWSER_CHANNEL" not in varsayilan and "SMOKE_SPEC" not in varsayilan
              and kanalli.get("SMOKE_BROWSER_CHANNEL") == "msedge" and kanalli["SMOKE_BASE_URL"] == "http://127.0.0.1:1")
        H.kaydet("smoke: --channel yalnız verilince env'e yazılır, dış kabuk değeri sızmaz", "yok/msedge",
                 f"{varsayilan.get('SMOKE_BROWSER_CHANNEL')}/{kanalli.get('SMOKE_BROWSER_CHANNEL')}", ok)
        self.assertTrue(ok)

    def test_kanal_kurulum_mesaji_ve_kuru(self):
        rc_k, out_k = H.kos(S, "--port", "1", "--channel", "chrome", "--no-auth")
        rc_d, out_d = H.kos(S, "--port", "1", "--channel", "chrome", "--dry-run")
        rc_x, _ = H.kos(S, "--port", "1", "--channel", "firefox", "--dry-run")
        kurulu = R.playwright_kurulu()
        mesaj_ok = kurulu or (rc_k == 2 and "npm install" in out_k and "playwright install" not in out_k)
        ok = mesaj_ok and rc_d == 0 and "kurulu chrome" in out_d and "BAKILMADI" in out_d and rc_x == 2
        H.kaydet("smoke: --channel → tarayıcı indirme önerilmez; --dry-run 0; geçersiz kanal 2", "2/0/2",
                 f"{rc_k}/{rc_d}/{rc_x} kurulu={kurulu}", ok)
        self.assertTrue(ok, out_k + out_d)

    def test_adres_yok(self):
        rc, out = H.kos(S)
        ok = rc == 2 and "--port ya da --base-url" in out
        H.kaydet("smoke: adres verilmedi → DUR", "rc=2", f"rc={rc}", ok)
        self.assertTrue(ok, out)


if __name__ == "__main__":
    unittest.main()
