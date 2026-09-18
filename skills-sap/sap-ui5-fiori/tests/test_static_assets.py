#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_ui_static_assets.py: enjekte meta + CRLF + .properties dönüşümü → AYNI; farklı/eksik → FARK."""
from __future__ import annotations

import unittest

import _helpers as H

S = "verify_ui_static_assets.py"
HTML = "<html><head><title>Yardım</title></head><body>Sürüm 2</body></html>\n"
ENJEKTE = ('<meta name="sap-client" content="100"><meta name="sap-ui-fesr" content="true">'
           '<meta name="sap.whitelistService" content="/sap/public/bc/uics/whitelist/service">')
PROP_KAYNAK = "title=Yardım sayfası\n"
PROP_BUILD = "title=Yard\\u0131m sayfas\\u0131\n"


def _app_hazirla(url):
    app = H.gecici_app(url=url)
    for kok, prop in ((app / "webapp" / "help", PROP_KAYNAK), (app / "dist" / "help", PROP_BUILD)):
        kok.mkdir(parents=True, exist_ok=True)
        (kok / "index.html").write_bytes(HTML.encode("utf-8"))
        (kok / "texts.properties").write_bytes(prop.encode("utf-8"))
    return app


def _yol(rel):
    return f"/sap/bc/ui5_ui5/sap/zxx001_order/help/{rel}"


class TestStaticAssets(unittest.TestCase):
    def test_pozitif(self):
        canli_html = HTML.replace("<head>", "<head>" + ENJEKTE).replace("\n", "\r\n").encode("utf-8")
        with H.SahteSunucu({_yol("index.html"): canli_html, _yol("texts.properties"): PROP_BUILD.encode()}) as srv:
            app = _app_hazirla(srv.url)
            try:
                rc, out = H.kos(S, app, kimlik=True)
            finally:
                H.temizle(app)
        ok = rc == 0 and "2/2 dosya canlıda AYNI" in out and "beklenen build dönüşümü" in out and H.PAROLA not in out
        H.kaydet("static: enjekte meta + CRLF + \\uXXXX → AYNI", "rc=0", f"rc={rc}", ok)
        self.assertTrue(ok, out)

    def test_negatif(self):
        eski = HTML.replace("Sürüm 2", "Sürüm 1").encode("utf-8")
        with H.SahteSunucu({_yol("index.html"): eski}) as srv:
            app = _app_hazirla(srv.url)
            try:
                rc, out = H.kos(S, app, kimlik=True)
            finally:
                H.temizle(app)
        ok = rc == 1 and "[FARKLI] index.html" in out and "[CANLIDA YOK/OKUNAMADI] texts.properties (HTTP 404)" in out
        H.kaydet("static: canlı eski html + eksik dosya → FARK", "rc=1", f"rc={rc}", ok)
        self.assertTrue(ok, out)

    def test_kaynak_farki(self):
        with H.SahteSunucu({_yol("index.html"): HTML.encode("utf-8"), _yol("texts.properties"): PROP_BUILD.encode()}) as srv:
            app = _app_hazirla(srv.url)
            try:
                (app / "webapp" / "help" / "index.html").write_text(HTML.replace("Sürüm 2", "Sürüm 3"), encoding="utf-8")
                rc, out = H.kos(S, app, kimlik=True)
            finally:
                H.temizle(app)
        ok = rc == 1 and "[KAYNAK FARKI] index.html" in out
        H.kaydet("static: canlı == dist ama webapp yeni → KAYNAK FARKI", "rc=1", f"rc={rc}", ok)
        self.assertTrue(ok, out)

    def test_kimliksiz(self):
        app = _app_hazirla("http://127.0.0.1:1")
        try:
            rc, out = H.kos(S, app)
        finally:
            H.temizle(app)
        ok = rc == 2 and "set değil" in out
        H.kaydet("static: env kimlik yok → ÖLÇÜM YOK", "rc=2", f"rc={rc}", ok)
        self.assertTrue(ok, out)


if __name__ == "__main__":
    unittest.main()
