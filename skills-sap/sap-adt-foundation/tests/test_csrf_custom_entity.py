# -*- coding: utf-8 -*-
"""CSRF reddi dilden bağımsız TEK yüklemde + CDS custom entity kaynak kapısından geçer (kaynak çekirdek #410/#411).

  · S/N — `SAPADTClient._csrf_reddi_mi` + `_should_retry`: EN/DE gövde, başlık (`x-csrf-token: Required`) tanınır;
          CSRF dışı 403, 200 + "CSRF" gövdesi, 500 + İngilizce CSRF metni tanınmaz (403 şartı — davranış değişikliği).
  · Q  — `_request_with_csrf_retry`: DE gövdeli CSRF 403 → ikinci istek TAZE token taşır; yetki 403 → tek istek.
  · W  — kablolama: yüklem dört çağrı noktasında (`self._csrf_reddi_mi(`), eski İngilizce-yalnız yüklem kodda yok.
  · C  — `_validate_cds_source`: `define [root] custom entity` (parametreli dahil) kabul; gövdesiz custom entity
          ve table function reddi korunur; yorumdaki `custom entity` başlık sayılmaz. `cds_kod_metni` tek kaynak.
SAP GEREKTİRMEZ: oturum/token sahte.
"""
from __future__ import annotations

import re
import sys
import unittest

import _helpers as H

sys.dont_write_bytecode = True
if str(H.SCRIPTS) not in sys.path:
    sys.path.insert(0, str(H.SCRIPTS))

import sapadt  # noqa: E402,F401
import sap_adt_lib as L  # noqa: E402

EN = "CSRF token validation failed"
DE = "Überprüfung des CSRF-Tokens fehlgeschlagen"


class _Y:
    def __init__(self, kod, govde="", basliklar=None):
        self.status_code, self.text = kod, govde
        self.content = govde.encode("utf-8")
        self.headers = basliklar or {}


def _istemci():
    c = L.SAPADTClient.__new__(L.SAPADTClient)
    c.max_retries = 3
    c.debug_enabled = False
    c.retry_on_csrf_fail = True
    c.retry_on_5xx = True
    c.timeout_default = 5
    c.url = "http://sahte.invalid"
    c._update_cookies = lambda r: None
    return c


class S_Yuklem(unittest.TestCase):
    def test_S_tanir_N_tanimaz(self):
        f = L.SAPADTClient._csrf_reddi_mi
        tanir = [f(_Y(403, EN)), f(_Y(403, DE)), f(_Y(403, "Zugriff verweigert", {"x-csrf-token": "Required"})),
                 f(_Y(403, "", {"X-CSRF-Token": "Required"}))]
        tanimaz = [f(_Y(403, "Keine Berechtigung")), f(_Y(200, EN)), f(_Y(500, EN))]
        ok = all(tanir) and not any(tanimaz)
        H.kaydet("CSRF S1-S4/N1-N3 ortak yüklem", "4 tanır · 3 tanımaz", f"{tanir} · {tanimaz}", ok)
        self.assertTrue(ok)

    def test_S_should_retry_ayni_yuklem(self):
        c = _istemci()
        c.csrf_token = "T1"
        r_de = c._should_retry(_Y(403, DE), 0, "x")[0]
        r_yetki = c._should_retry(_Y(403, "Keine Berechtigung"), 0, "x")[0]
        ok = r_de is True and r_yetki is False
        H.kaydet("CSRF _should_retry DE gövde", "DE → retry · yetki 403 → yok", f"{r_de} {r_yetki}", ok)
        self.assertTrue(ok)


class Q_Tekrar(unittest.TestCase):
    def _kur(self, yanitlar):
        c = _istemci()
        gonderilen = []
        kuyruk = list(yanitlar)

        class _Oturum:
            verify = False
            headers = {}

            def request(self, metod, url, **kw):
                gonderilen.append(dict(kw.get("headers") or {}))
                return kuyruk.pop(0)

            def __getattr__(self, ad):
                def f(url, **kw):
                    gonderilen.append(dict(kw.get("headers") or {}))
                    return kuyruk.pop(0)
                return f
        c.session = _Oturum()
        tokenlar = iter(["TAZE1", "TAZE2", "TAZE3"])
        c.csrf_token = "ESKI"

        def taze(force_refresh=False):
            c.csrf_token = next(tokenlar)
            return c.csrf_token
        c.fetch_csrf_token = taze
        return c, gonderilen

    def test_Q_taze_token_ve_yetki(self):
        c, g = self._kur([_Y(403, DE), _Y(200, "ok")])
        r = c._request_with_csrf_retry("post", c.url + "/x", headers={"X-CSRF-Token": "ESKI"})
        c2, g2 = self._kur([_Y(403, "Keine Berechtigung"), _Y(200, "ok")])
        r2 = c2._request_with_csrf_retry("post", c2.url + "/x", headers={"X-CSRF-Token": "ESKI"})
        ikinci = (g[1] if len(g) > 1 else {}).get("X-CSRF-Token") or (g[1] if len(g) > 1 else {}).get("x-csrf-token")
        ok = len(g) == 2 and r.status_code == 200 and ikinci not in (None, "ESKI") and len(g2) == 1 and r2.status_code == 403
        H.kaydet("CSRF Q DE 403 → taze token ile 2. istek · yetki 403 → 1 istek", "2 · TAZE · 1",
                 f"{len(g)} {ikinci} {len(g2)}", ok)
        self.assertTrue(ok, (g, g2))


class W_Kablolama(unittest.TestCase):
    def test_W1_dort_cagri(self):
        metin = open(L.__file__, encoding="utf-8").read()
        n = len(re.findall(r"self\._csrf_reddi_mi\(", metin))
        eski = "'CSRF token validation failed' in" in metin
        ok = n == 4 and not eski
        H.kaydet("CSRF W1 kablolama", "4 çağrı · eski yüklem yok", f"{n} {eski}", ok)
        self.assertTrue(ok)


class C_CustomEntity(unittest.TestCase):
    def _gecer(self, kaynak):
        try:
            _istemci()._validate_cds_source(kaynak)
            return True
        except L.SAPValidationError:
            return False

    def test_C_kabul_ve_red(self):
        kabul = [
            "@EndUserText.label: 'Ornek'\n@ObjectModel.query.implementedBy: 'ABAP:ZCL_X'\n"
            "define custom entity ZI_CE_X {\n  key id : abap.char(10);\n  ad : abap.char(40);\n}",
            "define root custom entity ZI_CE_Y { key id : abap.char(10); }",
            "define custom entity ZI_CE_P with parameters p_tarih : abap.dats { key id : abap.char(10); }",
            "define view entity ZI_X as select distinct from zt_x { key id }",
        ]
        red = [
            "define custom entity ZI_CE_BOS",                                   # gövde yok
            "// define custom entity ZI_CE_YORUM { key id : abap.char(1); }\n",   # yalnız yorumda
            "define table function ZI_TF returns { key id : abap.char(1); } implemented by method zcl_x=>m;",
        ]
        k = [self._gecer(s) for s in kabul]
        r = [self._gecer(s) for s in red]
        ok = all(k) and not any(r)
        H.kaydet("CDS C custom entity kapısı", "4 kabul · 3 red", f"{k} · {r}", ok)
        self.assertTrue(ok, (k, r))

    def test_C_cds_kod_metni_tek_kaynak(self):
        from utils import cds_metin
        ok = (L.cds_kod_metni is cds_metin.cds_kod_metni
              and cds_metin.cds_kod_metni("a // yorum\nb 'x//y' /* c */ d") .split() == ["a", "b", "''", "d"])
        H.kaydet("CDS cds_kod_metni tek kaynak", "aynı nesne · yorum/string ayıklanır", str(ok), ok)
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
