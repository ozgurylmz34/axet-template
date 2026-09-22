# -*- coding: utf-8 -*-
"""Kütüphane regresyon testleri (2026-09-13) — kaynak çekirdekteki üç ağsız testin aXet kopyası.

Kaynak testler (salt-okur, aynı adlar): `test_csrf_header_injection.py` (C-CSRF-01),
`test_push_readback_mismatch.py` (C-PUSH-01), `test_search_objects_type_filter.py` (C-SEARCH-01).
Uyarlama: yollar `scripts/sapadt/lib/` · unittest + senaryo satırı · örnek adlar jenerik (ZCA000).
Hepsi GERÇEK kod yolunu çağırır (sahte oturum); mantık testte yeniden uygulanmaz.

Bilinçli ALINMAYAN: kaynak push testindeki `test_result_success_readback_ok_false_ile_duser` ve
`test_readback_ok_yoksa_varsayilan_true` — ifadeyi testin İÇİNDE yeniden yazıp onu doğruluyordu (kod
çağırmıyordu). Aynı güvenceyi kaynağın kendi kablolama testi (`success` atamasının metni) verir; o alındı.
"""
from __future__ import annotations

import re
import sys
import unittest

import _helpers as H

sys.dont_write_bytecode = True
LIB = H.SCRIPTS / "sapadt" / "lib"
for _p in (H.SCRIPTS, LIB):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import sapadt  # noqa: E402,F401  (lib yolunu hazırlar)
from sap_adt_lib import SAPADTClient  # noqa: E402

TOKEN = "TAZE-CSRF-TOKEN-123"
SAP_CLIENT_SRC = LIB / "sap_client.py"


class _Yanit:
    def __init__(self, status_code=200, text="", headers=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}
        self.content = text.encode("utf-8")


class _CsrfOturum:
    def __init__(self, yanitlar=None):
        self.gonderilen = []
        self._yanitlar = list(yanitlar or [])

    def request(self, method, url, headers=None, timeout=None, **kw):
        self.gonderilen.append(dict(headers or {}))
        return self._yanitlar.pop(0) if self._yanitlar else _Yanit()


def _soguk_client(yanitlar=None):
    c = SAPADTClient.__new__(SAPADTClient)
    c.csrf_token = ""
    c.session = _CsrfOturum(yanitlar)
    c.timeout_default = 30
    c.debug_enabled = False
    c._update_cookies = lambda r: None
    c._get_headers = lambda **kw: ({"Accept": "x"} | ({"X-CSRF-Token": c.csrf_token} if c.csrf_token else {}))

    def _fetch(force_refresh=False):
        c.csrf_token = TOKEN
    c.fetch_csrf_token = _fetch
    return c


class _AramaOturum:
    def __init__(self):
        self.calls = []

    def get(self, url, headers=None, params=None, timeout=None):
        self.calls.append({"url": url, "params": dict(params or {})})
        return _Yanit(200, '<?xml version="1.0"?><root/>')


def _arama_client():
    c = SAPADTClient.__new__(SAPADTClient)
    c.url = "https://example.invalid:44300"
    c.timeout_short = 1
    c.session = _AramaOturum()
    c._get_headers = lambda *a, **k: {}
    return c


class LibRegresyon(unittest.TestCase):
    def kaydet(self, ad, beklenen, gercek, ok):
        H.kaydet(f"LIB {ad}", beklenen, str(gercek)[:160], ok)
        self.assertTrue(ok, f"{ad}: {gercek}")

    # ── C-CSRF-01 ────────────────────────────────────────────────────────────────────────
    def test_csrf_01_onceden_kurulan_headera_token_enjekte(self):
        c = _soguk_client()
        hdr = c._get_headers()
        self.assertNotIn("X-CSRF-Token", hdr)
        c._request_with_csrf_retry("post", "http://x/y", headers=hdr)
        g = c.session.gonderilen[0].get("X-CSRF-Token")
        self.kaydet("CSRF-1 soğuk oturumda önceden kurulan başlığa token enjekte", TOKEN, g, g == TOKEN)

    def test_csrf_02_cagiranin_dicti_degismez(self):
        c = _soguk_client()
        hdr = c._get_headers()
        c._request_with_csrf_retry("post", "http://x/y", headers=hdr)
        self.kaydet("CSRF-2 çağıranın dict'i mutasyona uğramaz", "token yok", hdr, "X-CSRF-Token" not in hdr)

    def test_csrf_03_headers_none(self):
        c = _soguk_client()
        c._request_with_csrf_retry("post", "http://x/y", headers=None)
        g = c.session.gonderilen[0].get("X-CSRF-Token")
        self.kaydet("CSRF-3 headers=None yolu", TOKEN, g, g == TOKEN)

    def test_csrf_04_403_tek_retry(self):
        c = _soguk_client([_Yanit(403, "CSRF token validation failed"), _Yanit(200, "ok")])
        r = c._request_with_csrf_retry("post", "http://x/y", headers=c._get_headers())
        ok = r.status_code == 200 and len(c.session.gonderilen) == 2 \
            and c.session.gonderilen[1].get("X-CSRF-Token") == TOKEN
        self.kaydet("CSRF-4 403 + CSRF → tam 1 retry", "200 · 2 istek", len(c.session.gonderilen), ok)

    def test_csrf_05_sicak_oturum(self):
        c = _soguk_client()
        c.csrf_token = TOKEN
        c._request_with_csrf_retry("post", "http://x/y", headers={"Accept": "x", "X-CSRF-Token": TOKEN})
        g = c.session.gonderilen[0].get("X-CSRF-Token")
        self.kaydet("CSRF-5 sıcak oturum aynı token bozulmaz", TOKEN, g, g == TOKEN)

    # ── C-PUSH-01 ────────────────────────────────────────────────────────────────────────
    def test_push_01_bicim_ve_icerik_ayrimi(self):
        from sap_client import readback_farki_yalniz_bicim_mi as ayrim  # type: ignore
        durum = {
            "pretty_print": ayrim("key mandt : mandt not null;\nkey ctype : zca000_e_ctype not null;",
                                  "key mandt   : mandt not null;\nkey ctype   : zca000_e_ctype not null;") is True,
            "icerik": ayrim("Header.fld1 as FieldOne,\nHeader.fld2 as FieldTwo,", "Header.fld1 as LegacyCombinedField,") is False,
            "ayni": ayrim("define view entity ZCA000_I_X as select from zca000_t_y { key a }",
                          "define view entity ZCA000_I_X as select from zca000_t_y { key a }") is True,
            "crlf": ayrim("a\r\nb\r\n", "a\nb\n") is True,
            "tek_karakter": ayrim("as FieldOne,   // not1", 'as FieldOne,   " not1') is False,
            "bos_none": ayrim("", "") is True and ayrim(None, None) is True and ayrim("abc", None) is False,
        }
        self.kaydet("PUSH-1 readback biçim farkı geçer · içerik farkı yakalanır (6 vaka)", "hepsi True", durum,
                    all(durum.values()))

    def test_push_02_kablolama(self):
        src = SAP_CLIENT_SRC.read_text(encoding="utf-8")
        m = re.search(r"result\['success'\]\s*=\s*\((.*?)\)", src, re.S)
        ifade = m.group(1) if m else ""
        durum = {
            "helper_cagrisi": "readback_farki_yalniz_bicim_mi(uploaded_norm, active_norm)" in src,
            "false_dali": "result['readback_ok'] = False" in src,
            "none_dali": "result['readback_ok'] = None" in src,
            "success_atamasi": bool(m) and all(k in ifade for k in ("readback_ok", "source_uploaded", "activated")),
            "uc_degerli": "and result.get('readback_ok') is not False" in src,
        }
        self.kaydet("PUSH-2 readback helper push akışına kablolu, success readback_ok'i okuyor", "hepsi True", durum,
                    all(durum.values()))

    # ── C-SEARCH-01 ──────────────────────────────────────────────────────────────────────
    def test_search_01_tip_sunucuya_gider(self):
        c = _arama_client()
        c.search_objects("ZCA000*", max_results=50, obj_type="TABL/DT")
        c2 = _arama_client()
        c2.search_objects("ZCA000*", obj_type="TABL")
        c3 = _arama_client()
        c3.search_objects("ZCA000*", max_results=77)
        p1, p2, p3 = c.session.calls[0]["params"], c2.session.calls[0]["params"], c3.session.calls[0]["params"]
        ok = (p1.get("objectType") == "TABL/DT" and p2.get("objectType") == "TABL" and "objectType" not in p3
              and p3.get("operation") == "quickSearch" and p3.get("query") == "ZCA000*" and p3.get("maxResults") == 77
              and len(c.session.calls) == 1)
        self.kaydet("SEARCH-1 objectType sunucuya · tipsizde yok · temel parametreler · tek çağrı", "doğru",
                    [p1, p3], ok)

    def test_search_02_sabit_kablolama_uyari(self):
        src = SAP_CLIENT_SRC.read_text(encoding="utf-8")
        m = re.search(r"self\.adt_client\.search_objects\((.*?)\)", src, re.S)
        durum = {"MAX_SEARCH_RESULTS": getattr(SAPADTClient, "MAX_SEARCH_RESULTS", None) == 550,
                 "obj_type_iletiliyor": bool(m) and "obj_type" in m.group(1),
                 "kirpma_uyarisi": "truncated" in src and "KIRPILMIS" in src.upper()}
        self.kaydet("SEARCH-2 tavan 550 · sap_client obj_type iletir · kırpma uyarısı var", "hepsi True", durum,
                    all(durum.values()))


    # ── v0.5.3: silme başarısızsa kilit bırakılır — mevcut `finally` davranışının regresyon kilidi
    # (v0.5.2 gate'i bunu 'finally yok' diye yanlış raporladı; kod okununca finally bulundu) ──
    @staticmethod
    def _sil_istemcisi(sil_hata):
        from sap_client import SAPClient  # type: ignore
        c = SAPClient.__new__(SAPClient)
        c.debug_enabled = False
        cagri = []

        class _Adt:
            def lock_object(self, url, transport=None):
                cagri.append(("lock", url))
                return "KILIT-1"

            def delete_object(self, url, kilit, transport=None):
                cagri.append(("delete", url, kilit))
                if sil_hata:
                    raise RuntimeError("423 kilitli / silinemedi")

            def unlock_object(self, url, kilit):
                cagri.append(("unlock", url, kilit))
        c.adt_client = _Adt()
        return c, cagri

    def test_sil_01_delete_hatasinda_kilit_birakilir(self):
        c, cagri = self._sil_istemcisi(sil_hata=True)
        r = c.delete_object("ZCA000_X", "class", transport="DEVK900001", confirm=False)
        adimlar = [a[0] for a in cagri]
        self.kaydet("SİL-1 DELETE hatası → False + kilit aynı handle ile bırakılır", "False · lock/delete/unlock",
                    (r, cagri), r is False and adimlar == ["lock", "delete", "unlock"] and cagri[-1][2] == "KILIT-1")


if __name__ == "__main__":
    unittest.main()
