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

    def test_adres_yok(self):
        rc, out = H.kos(S)
        ok = rc == 2 and "--port ya da --base-url" in out
        H.kaydet("smoke: adres verilmedi → DUR", "rc=2", f"rc={rc}", ok)
        self.assertTrue(ok, out)


if __name__ == "__main__":
    unittest.main()
