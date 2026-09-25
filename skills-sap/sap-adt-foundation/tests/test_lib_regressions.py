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


    # ── Z132 (2026-09-25): get_object_revisions — ölçülen gövde biçimi + hatayı YUTMAMA ──
    @staticmethod
    def _surum_client(obje_durum=200, govde="", feed_durum=200):
        """Obje isteği yalnız `Accept: */*` ile `obje_durum` döner (canlı ölçüm: objectstructure/xml → 406)."""
        feed = ('<atom:feed xmlns:atom="http://www.w3.org/2005/Atom" xmlns:adtcore="http://www.sap.com/adt/core">'
                '<atom:entry><atom:title>s2</atom:title><atom:updated>2026-09-02T10:00:00Z</atom:updated>'
                '<atom:author><atom:name>DEVUSER1</atom:name></atom:author>'
                '<atom:link href="/y" adtcore:name="00002"/></atom:entry>'
                '<atom:entry><atom:title>s1</atom:title><atom:updated>2026-09-01T10:00:00Z</atom:updated>'
                '<atom:author><atom:name>DEVUSER2</atom:name></atom:author>'
                '<atom:link href="/x" adtcore:name="00001"/></atom:entry></atom:feed>')
        c = SAPADTClient.__new__(SAPADTClient)
        c.url = "https://example.invalid:44300"
        c.timeout_short = 1
        c.debug_enabled = False
        c._get_headers = lambda *a, **kw: {"Accept": "application/xml"}
        cagri = []

        class _Oturum:
            def get(self, url, headers=None, params=None, timeout=None):
                acc = (headers or {}).get("Accept", "")
                cagri.append((url[len(c.url):], acc))
                if "atom+xml" in acc:
                    return _Yanit(feed_durum, feed if feed_durum == 200 else "hata")
                return _Yanit(obje_durum if acc == "*/*" else 406, govde)
        c.session = _Oturum()
        return c, cagri

    def test_rev_01_z132_sinif_atom_link_goreli(self):
        rel = 'rel="http://www.sap.com/adt/relations/versions"'
        govde = (f'<class:abapClass><atom:link href="includes/definitions/versions" {rel}/>'
                 f'<atom:link href="includes/main/versions" {rel}/></class:abapClass>')
        c, cagri = self._surum_client(govde=govde)
        r = c.get_object_revisions("/sap/bc/adt/oo/classes/zcl_zsd001_rev")
        ok = ([x["version"] for x in r] == ["00002", "00001"]
              and cagri == [("/sap/bc/adt/oo/classes/zcl_zsd001_rev", "*/*"),
                            ("/sap/bc/adt/oo/classes/zcl_zsd001_rev/includes/main/versions",
                             "application/atom+xml;type=feed")])
        self.kaydet("REV-1 Z132 lib: Accept */* · atom:link · göreli href · includes/main seçilir", "2 sürüm · doğru yol",
                    cagri, ok)

    def test_rev_02_z132_hata_yutulmaz(self):
        from sap_adt_lib import SAPADTError, SAPObjectNotFoundError  # type: ignore
        rel = 'rel="http://www.sap.com/adt/relations/versions"'
        durum = {}
        for ad, kw in (("obje406", {"obje_durum": 406}), ("obje404", {"obje_durum": 404}),
                       ("feed500", {"govde": f'<atom:link href="source/main/versions" {rel}/>', "feed_durum": 500})):
            c, _ = self._surum_client(**kw)
            try:
                durum[ad] = ("dondu", c.get_object_revisions("/sap/bc/adt/programs/includes/zsd001_i_rev"))
            except SAPObjectNotFoundError as e:
                durum[ad] = ("SAPObjectNotFoundError", e.status_code)
            except SAPADTError as e:
                durum[ad] = ("SAPADTError", e.status_code)
        c, _ = self._surum_client(govde="<x/>")
        durum["baglantisiz"] = ("dondu", c.get_object_revisions("/sap/bc/adt/programs/includes/zsd001_i_rev"))
        ok = durum == {"obje406": ("SAPADTError", 406), "obje404": ("SAPObjectNotFoundError", 404),
                       "feed500": ("SAPADTError", 500), "baglantisiz": ("dondu", [])}
        self.kaydet("REV-2 Z132 lib: 406/404/feed 500 istisna (sessiz [] YOK) · bağlantı yoksa []", "3 istisna · []",
                    durum, ok)

    def test_rev_03_z132_baglanti_yardimcilari(self):
        from sap_adt_lib import resolve_adt_href, select_versions_link, versions_links  # type: ignore
        rel = "http://www.sap.com/adt/relations/versions"
        govde = (f'<link href="/sap/bc/adt/a/versions" rel="{rel}"/>'
                 f"<atom:link rel='{rel}' href='includes/main/versions?x=1&amp;y=2'/>"
                 '<atom:link href="includes/x" rel="http://www.sap.com/adt/relations/source"/>')
        durum = {
            "bul": versions_links(govde) == ["/sap/bc/adt/a/versions", "includes/main/versions?x=1&y=2"],
            "sec_main": select_versions_link(["includes/definitions/versions", "includes/main/versions"])
            == "includes/main/versions",
            "sec_ilk": select_versions_link(["includes/definitions/versions", "includes/macros/versions"])
            == "includes/definitions/versions",
            "sec_bos": select_versions_link([]) is None,
            "sec_sinir": select_versions_link(["includes/definitions/versions", "/sap/bc/adt/x/zdomain/versions"])
            == "includes/definitions/versions",
            "sec_mutlak_main": select_versions_link(["includes/definitions/versions", "/sap/bc/adt/x/main/versions"])
            == "/sap/bc/adt/x/main/versions",
            "coz_goreli": resolve_adt_href("/sap/bc/adt/oo/classes/zcl_x", "includes/main/versions")
            == "/sap/bc/adt/oo/classes/zcl_x/includes/main/versions",
            "coz_nokta": resolve_adt_href("/sap/bc/adt/oo/classes/zcl_x/", "./source/main/versions")
            == "/sap/bc/adt/oo/classes/zcl_x/source/main/versions",
            "coz_mutlak": resolve_adt_href("/o", "/sap/bc/adt/v") == "/sap/bc/adt/v"
            and resolve_adt_href("/o", "https://h/v") == "https://h/v",
        }
        self.kaydet("REV-3 Z132 yardımcılar: link/atom:link · öznitelik sırası · tırnak · seçim · göreli çözüm",
                    "hepsi True", durum, all(durum.values()))


if __name__ == "__main__":
    unittest.main()
