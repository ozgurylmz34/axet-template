# -*- coding: utf-8 -*-
"""Z207 (2026-10-19) — genel HTTP adapter'ı yan etkili istekleri YENİDEN GÖNDERMESİN.

Ölçüm (düzeltme öncesi): `SAPADTClient._build_session` genel adapter'ı
`Retry(total=3, status_forcelist=(429,502,503,504), allowed_methods=GET/HEAD/PUT/POST/DELETE)` kuruyordu →
yaratma POST'u, kaynak PUT'u, aktivasyon, silme, kilit, transport kaydı, ATC / ABAP Unit koşusu 503'te ve
okuma zaman aşımında sunucuya 4'er kez gidiyordu (ilk istek SAP'de işlenmiş olabilir ⇒ yan etki 4 kez).

Kural: genel adapter yalnız GET/HEAD/OPTIONS'ı yeniden dener; POST'u OKUMA için kullanan uçlar
(`OKUMA_POST_ONEKLERI`) ayrı izinli adapter'la yeniden denenir; classrun'un Z190 adapter'ı aynen durur.

Testler GERÇEK `_build_session` + `requests` + `urllib3` yolunu yerel bir sahte HTTP sunucusuna (127.0.0.1)
karşı koşar ve sunucuya ULAŞAN istekleri (metot + yol) sayar. SAP'ye bağlanmaz.
"""
from __future__ import annotations

import http.server
import sys
import threading
import time
import unittest

import _helpers as H

sys.dont_write_bytecode = True
LIB = H.SCRIPTS / "sapadt" / "lib"
for _p in (H.SCRIPTS, LIB):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import sapadt  # noqa: E402,F401  (lib yolunu hazırlar)
import requests  # noqa: E402
from urllib3.exceptions import NewConnectionError, ReadTimeoutError  # noqa: E402
import sap_adt_lib  # noqa: E402
from sap_adt_lib import SAPADTClient  # noqa: E402

YAVAS_SN = 0.6
ZAMAN_ASIMI_SN = 0.25

# Yan etkili uçlar — sunucuda obje / sürüm / kilit / kayıt / koşu yaratır ya da değiştirir.
YAN_ETKILI = [
    ("POST", "/sap/bc/adt/oo/classes", "yaratma (sınıf)"),
    ("POST", "/sap/bc/adt/ddic/tables", "yaratma (tablo)"),
    ("PUT", "/sap/bc/adt/oo/classes/zcl_x/source/main", "kaynak PUT"),
    ("POST", "/sap/bc/adt/activation", "aktivasyon"),
    ("DELETE", "/sap/bc/adt/oo/classes/zcl_x", "silme"),
    ("POST", "/sap/bc/adt/oo/classes/zcl_x", "LOCK/UNLOCK"),
    ("POST", "/sap/bc/adt/cts/transportrequests", "transport kaydı"),
    ("POST", "/sap/bc/adt/atc/runs", "ATC koşusu"),
    ("POST", "/sap/bc/adt/atc/worklists", "ATC iş listesi"),
    ("POST", "/sap/bc/adt/abapunit/testruns", "ABAP Unit koşusu"),
    ("POST", "/sap/bc/adt/oo/classrun/zcl_x", "classrun"),
]


class _Sunucu:
    """Her metodu karşılar; (metot, yol) başına ulaşan istek sayacı. Varsayılan yanıt 503."""

    def __init__(self):
        self.sayac: dict[tuple[str, str], int] = {}
        self.yavas = False
        self.kilit = threading.Lock()
        dis = self

        class _H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):  # noqa: D401
                pass

            def _isle(self):
                n = int(self.headers.get("Content-Length") or 0)
                if n:
                    self.rfile.read(n)
                with dis.kilit:
                    k = (self.command, self.path.split("?")[0])
                    dis.sayac[k] = dis.sayac.get(k, 0) + 1
                if dis.yavas:
                    time.sleep(YAVAS_SN)
                try:
                    self.send_response(503)
                    self.send_header("Content-Length", "2")
                    self.end_headers()
                    if self.command != "HEAD":
                        self.wfile.write(b"gw")
                except Exception:  # noqa: BLE001 — istemci zaman aşımıyla kapatmış olabilir
                    pass

            do_GET = do_POST = do_PUT = do_DELETE = do_HEAD = do_OPTIONS = _isle

        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _H)
        self.srv.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def kapat(self):
        self.srv.shutdown()
        self.srv.server_close()


def _istemci(url: str) -> SAPADTClient:
    """Gerçek `_build_session` / `new_session` / `_retry_request`; auth ve CSRF sahte."""
    c = SAPADTClient.__new__(SAPADTClient)
    c.url, c.client, c.language, c._auth_provider = url, "000", "TR", None
    c._get_auth_headers = lambda: {}
    c.debug_enabled = False
    c.csrf_token = "T"
    c.fetch_csrf_token = lambda force_refresh=False: None
    c._invalidate_csrf_cache = lambda: None
    c.max_retries, c.retry_delay = 3, 0.01
    c.retry_on_timeout = c.retry_on_csrf_fail = c.retry_on_5xx = True
    c.session = c._build_session()
    return c


class YanEtkiliTekrar(unittest.TestCase):

    def setUp(self):
        self.sunucu = _Sunucu()
        self.adt = _istemci(self.sunucu.url)

    def tearDown(self):
        try:
            self.adt.session.close()
        except Exception:  # noqa: BLE001
            pass
        self.sunucu.kapat()

    def kaydet(self, ad, beklenen, gercek, ok):
        H.kaydet(f"Z207 {ad}", beklenen, str(gercek)[:160], ok)
        self.assertTrue(ok, f"{ad}: {gercek}")

    def _gonder(self, metot, yol, timeout=5):
        try:
            r = self.adt.session.request(metot, self.sunucu.url + yol, timeout=timeout)
            sonuc = f"yanit {r.status_code}"
        except requests.exceptions.RetryError:
            sonuc = "RetryError"
        except requests.exceptions.Timeout:
            sonuc = "Timeout"
        except requests.exceptions.ConnectionError:  # okuma tekrarları tükendi (MaxRetryError)
            sonuc = "ConnectionError"
        time.sleep(0.05)
        return self.sunucu.sayac.get((metot, yol), 0), sonuc

    # Y1 — KAPANIŞ: yan etkili uçlar 503'te sunucuya 1 kez gider ve 503 yanıtı çağırana ulaşır -----
    def test_yan_etkili_uclar_503_tek_istek(self):
        olcum = {ad: self._gonder(m, y) for m, y, ad in YAN_ETKILI}
        kotu = {ad: v for ad, v in olcum.items() if v != (1, "yanit 503")}
        self.kaydet(f"yan etkili {len(YAN_ETKILI)} uç 503 → 1 istek + 503 yanıtı", "hepsi (1, yanit 503)",
                    kotu or olcum, not kotu)

    # Y2 — okuma GET'i (ve HEAD) yeniden denenir: 503 → 4 istek (doğru-pozitif kalibrasyon) ---------
    def test_okuma_get_head_503_yeniden_denenir(self):
        yol = "/sap/bc/adt/oo/classes/zcl_x/source/main"
        get = self._gonder("GET", yol)
        head = self._gonder("HEAD", yol)
        ok = get == (4, "RetryError") and head == (4, "RetryError")
        self.kaydet("okuma GET/HEAD 503 → 4 istek (tekrar korunur)", "(4, RetryError) ×2", [get, head], ok)

    # Y3 — okuma amaçlı POST önekleri yeniden denenir (alt yol + sorgu dizgesi dahil) ---------------
    def test_okuma_post_onekleri_503_yeniden_denenir(self):
        olcum = {}
        for onek in sap_adt_lib.OKUMA_POST_ONEKLERI:
            olcum[onek] = self._gonder("POST", onek)
        alt = self._gonder("POST", "/sap/bc/adt/datapreview/freestyle?rowNumber=5")
        olcum["freestyle?rowNumber"] = (self.sunucu.sayac.get(("POST", "/sap/bc/adt/datapreview/freestyle"), 0)
                                        - olcum["/sap/bc/adt/datapreview/freestyle"][0], alt[1])
        kotu = {k: v for k, v in olcum.items() if v != (4, "RetryError")}
        ok = not kotu and len(sap_adt_lib.OKUMA_POST_ONEKLERI) == 5
        self.kaydet("okuma-POST önekleri 503 → 4 istek", "hepsi (4, RetryError)", kotu or olcum, ok)

    # Y4 — okuma zaman aşımı: yaratma POST'u 1 kez gider; okuma GET'i yeniden denenir ---------------
    def test_okuma_zaman_asimi_yaratma_post_tek_get_tekrar(self):
        self.sunucu.yavas = True
        post = self._gonder("POST", "/sap/bc/adt/ddic/tables", timeout=ZAMAN_ASIMI_SN)
        put = self._gonder("PUT", "/sap/bc/adt/oo/classes/zcl_x/source/main", timeout=ZAMAN_ASIMI_SN)
        time.sleep(YAVAS_SN * 4 + 0.5)  # tekrarlansaydı geç gelen istekler de sayılsın
        post_n = self.sunucu.sayac.get(("POST", "/sap/bc/adt/ddic/tables"), 0)
        put_n = self.sunucu.sayac.get(("PUT", "/sap/bc/adt/oo/classes/zcl_x/source/main"), 0)
        get = self._gonder("GET", "/sap/bc/adt/discovery", timeout=ZAMAN_ASIMI_SN)
        time.sleep(YAVAS_SN + 0.3)
        get_n = self.sunucu.sayac.get(("GET", "/sap/bc/adt/discovery"), 0)
        ok = (post_n == 1 and put_n == 1 and post[1] == "Timeout" and put[1] == "Timeout"
              and get_n == 4)
        self.kaydet("okuma zaman aşımı: POST 1 · PUT 1 · GET 4", "1 / 1 / 4",
                    [post_n, post[1], put_n, put[1], get_n, get[1]], ok)

    # Y5 — genel adapter'ın kendi kuralı: bağlantı KURMA tekrarı POST için açık; durum/okuma kapalı --
    def test_genel_adapter_baglanti_tekrari_acik_durum_okuma_kapali(self):
        url = self.sunucu.url + "/sap/bc/adt/oo/classes"
        r = self.adt.session.get_adapter(url).max_retries
        try:
            r.increment(method="POST", url=url, error=NewConnectionError(None, "refused"))
            baglanti = "tekrar"
        except Exception as e:  # noqa: BLE001
            baglanti = type(e).__name__
        try:
            r.increment(method="POST", url=url, error=ReadTimeoutError(None, url, "read timed out"))
            okuma = "tekrar"
        except Exception as e:  # noqa: BLE001
            okuma = type(e).__name__
        durum = {m: r.is_retry(m, 503) for m in ("GET", "HEAD", "OPTIONS", "POST", "PUT", "DELETE")}
        ok = (baglanti == "tekrar" and okuma != "tekrar"
              and durum == {"GET": True, "HEAD": True, "OPTIONS": True,
                            "POST": False, "PUT": False, "DELETE": False}
              and 500 not in r.status_forcelist)
        self.kaydet("genel adapter: bağlantı → tekrar · POST okuma/durum → tekrarsız", "tekrar/tekrarsız",
                    [baglanti, okuma, durum], ok)

    # Y6 — izinli liste sınırlı: geniş önek / yan etkili uç / başka host kapsanmaz -----------------
    def test_okuma_post_listesi_sinirli_ve_host_bagli(self):
        onekler = sap_adt_lib.OKUMA_POST_ONEKLERI
        yasak_parca = ("/atc", "/abapunit", "/classrun", "/activation", "/oo/", "/ddic/", "/cts/",
                       "/programs/", "/functions/", "/ddl", "/bo/")
        ihlal = [o for o in onekler
                 if not o.startswith("/sap/bc/adt/") or o.rstrip("/").count("/") < 4
                 or any(p in o for p in yasak_parca)]
        baska = self.adt.session.get_adapter("http://baska-host:1/sap/bc/adt/checkruns").max_retries
        kendi = self.adt.session.get_adapter(self.sunucu.url + "/sap/bc/adt/checkruns").max_retries
        ok = (not ihlal and baska.is_retry("POST", 503) is False and kendi.is_retry("POST", 503) is True)
        self.kaydet("izinli liste dar + yalnız bu sistemin URL'si", "ihlal yok · başka host POST tekrarsız",
                    [ihlal, baska.is_retry("POST", 503), kendi.is_retry("POST", 503)], ok)

    # Y7 — new_session aynı kurulumu taşır (tek kaynak `_build_session`) ---------------------------
    def test_new_session_sonrasi_kural_korunur(self):
        self.adt.new_session()
        yaratma = self._gonder("POST", "/sap/bc/adt/oo/classes")
        okuma = self._gonder("POST", "/sap/bc/adt/checkruns")
        ok = yaratma == (1, "yanit 503") and okuma == (4, "RetryError")
        self.kaydet("new_session sonrası: yaratma 1 · checkrun 4", "1 / 4", [yaratma, okuma], ok)

    # Y8 — Z207 BİLİNÇLİ İSTİSNASI: ikinci katman `_retry_request` (Z52) yaratma POST'unu 3 kez gönderir. ----
    # Beş yaratma çağrısı (DTEL · domain · struct · tablo · CDS) 5xx / 504 / zaman aşımını uygulama
    # katmanında kendisi yeniden dener (`max_retries=3`). Z207 öncesi: 503 → 4 POST (adapter) +
    # RetryError · okuma zaman aşımı → 12 POST (adapter 4 × uygulama 3). Z207 sonrası: 503 → 3 ·
    # zaman aşımı → 3. "1 POST" bu katmanda BİLİNÇLİ OLARAK SAĞLANMAZ (lider kararı 2026-10-19):
    # yaratma tekrarı ÇİFT OBJE üretemez — ikinci deneme "already exists" alır ve Z52 telafisi
    # (`_son_yeniden_denemeler` → araçta `already_exists_after_retry` + `own_shell_possible`) tam bu
    # yolu işler. ⛔ Bu sayıyı 3 → 1 yapmaya kalkarsan Z52 telafisi ölü kalır: önce onu yeniden tasarla.
    # Z211 (2026-10-28; kaynak çekirdek #363): tekrarlar tükenince son yanıt (503, gövdesiyle) istisna yerine ÇAĞIRANA
    # döner — eskiden "Request failed after 3 retries: Unknown error" (SAPConnectionError) idi, gövde kayboluyordu.
    # Zaman aşımı dalı değişmedi (son denemede SAPConnectionError). 500 bu katmanda artık tekrarlanmaz (Y9).
    def test_z207_istisnasi_yaratma_post_3_kez_z52_telafisine_dayanir(self):
        yol = "/sap/bc/adt/ddic/tables"

        def _kos():
            once = self.sunucu.sayac.get(("POST", yol), 0)
            try:
                r = self.adt._retry_request(
                    lambda: self.adt.session.post(self.sunucu.url + yol, data=b"x", timeout=ZAMAN_ASIMI_SN),
                    "create table ZT")
                son = f"yanit {r.status_code} {r.text}"
            except Exception as e:  # noqa: BLE001
                son = type(e).__name__
            time.sleep(YAVAS_SN * 4 + 0.3 if self.sunucu.yavas else 0.05)
            return self.sunucu.sayac.get(("POST", yol), 0) - once, son, len(self.adt._son_yeniden_denemeler)

        h503 = _kos()
        self.sunucu.yavas = True
        zaman = _kos()
        ok = h503 == (3, "yanit 503 gw", 2) and zaman == (3, "SAPConnectionError", 2)
        self.kaydet("İSTİSNA _retry_request yaratma 503 → 3 POST + son 503 yanıtı GÖVDESİYLE döner · zaman aşımı → 3 "
                    "(önce 4/12) — iki yolda da Z52 izi 2 kayıt (already_exists_after_retry telafisi CANLI)",
                    "(3, yanit 503 gw, 2) / (3, SAPConnectionError, 2)", [h503, zaman], ok)


# ══════════════════════════════════════════════════════════════════════════════════════════════
# Z211 (2026-10-28; kaynak çekirdek #363) — uygulama katmanı `_retry_request` / `_should_retry`
# ① son deneme = tekrar YOK: son yanıt (gövdesiyle) çağırana döner, son denemeden sonra uyku YOK
# ② 500 tekrar EDİLMEZ (kalıcı red gövdesi; adapter'daki 2026-08-19 kararıyla tutarlı); 502/503/504 · 408 · CSRF aynen
# GERÇEK `_retry_request` + `_should_retry`; istek fonksiyonu ve `time.sleep` sahte (ağ yok, bekleme sayılır).
# Kaynak çekirdek vektör adları (C1–C8) korunur. ⛔ SİLİNMEZ ÇAPALAR: C2b (son denemeden sonra uyku yok) ·
# C3/C7/C8 FP çapaları (tekrarı tümden söken bir "fix" C1/C2'yi geçirir).
# ══════════════════════════════════════════════════════════════════════════════════════════════
class _Yanit:
    def __init__(self, kod, govde=""):
        self.status_code, self.text, self.headers = kod, govde, {}


class UygulamaKatmaniTekrar(unittest.TestCase):

    def setUp(self):
        c = SAPADTClient.__new__(SAPADTClient)
        c.url = "http://127.0.0.1:9"
        c.max_retries, c.retry_delay = 3, 1.0
        c.retry_on_timeout = c.retry_on_csrf_fail = c.retry_on_5xx = True
        self.tazelenen = []
        c.fetch_csrf_token = lambda force_refresh=False: self.tazelenen.append(force_refresh)
        self.c = c
        self.uykular = []
        eski = sap_adt_lib.time.sleep
        sap_adt_lib.time.sleep = lambda s: self.uykular.append(s)
        self.addCleanup(setattr, sap_adt_lib.time, "sleep", eski)

    def kos(self, yanitlar):
        sira = list(yanitlar)
        istek = []

        def f():
            istek.append(1)
            return sira.pop(0) if len(sira) > 1 else sira[0]
        try:
            r = self.c._retry_request(f, "create domain ZD")
            son = (r.status_code, r.text)
        except Exception as e:  # noqa: BLE001
            son = type(e).__name__
        return len(istek), len(self.uykular), son, list(self.c._son_yeniden_denemeler)

    def kaydet(self, ad, beklenen, gercek, ok):
        H.kaydet(f"Z211 {ad}", beklenen, str(gercek)[:160], ok)
        self.assertTrue(ok, f"{ad}: {gercek}")

    def test_C1_500_tekrar_edilmez_govde_doner(self):
        n, u, son, iz = self.kos([_Yanit(500, "<exc:exception><message>CTS_WBO_API 019</message></exc:exception>")])
        self.kaydet("C1 500 → 1 istek · uyku 0 · 500 yanıtı GÖVDESİYLE döner · Z52 izi boş (tekrar yok)",
                    "(1, 0, 500+gövde, [])", (n, u, son, iz),
                    n == 1 and u == 0 and son[0] == 500 and "CTS_WBO_API 019" in son[1] and iz == [])

    def test_C2_kalici_503_son_yanit_doner_son_denemeden_sonra_uyku_yok(self):
        n, u, son, iz = self.kos([_Yanit(503, "gecici gw")])
        self.kaydet("C2/C2b kalıcı 503 → 3 istek · 2 uyku (son denemeden sonra YOK) · son 503 gövdesiyle döner · "
                    "Z52 izi 2", "(3, 2, (503, gecici gw), 2 kayıt)", (n, u, son, iz),
                    n == 3 and u == 2 and son == (503, "gecici gw") and len(iz) == 2
                    and all("Server error 503" in x for x in iz))

    def test_C3_503_sonra_201_fp(self):
        n, u, son, iz = self.kos([_Yanit(503, "gw"), _Yanit(201, "")])
        self.kaydet("C3 FP: 503 → 201 → 2 istek · 1 uyku · başarı (tekrar KORUNDU)", "(2, 1, 201, 1 kayıt)",
                    (n, u, son, iz), n == 2 and u == 1 and son[0] == 201 and len(iz) == 1)

    def test_C4_C5_400_ve_201_tek_istek(self):
        a = self.kos([_Yanit(400, "bad")])
        self.uykular.clear()
        b = self.kos([_Yanit(201, "")])
        self.kaydet("C4/C5 400 · 201 → 1 istek, uyku 0", "(1,0,400) · (1,0,201)", (a, b),
                    a[:2] == (1, 0) and a[2][0] == 400 and b[:2] == (1, 0) and b[2][0] == 201)

    def test_C6_kalici_502_ve_504(self):
        a = self.kos([_Yanit(502, "bgw")])
        self.uykular.clear()
        b = self.kos([_Yanit(504, "gto")])
        self.kaydet("C6 kalıcı 502 / 504 → 3 istek · 2 uyku · son yanıt döner (tekrar korundu)",
                    "(3,2,502) · (3,2,504)", (a[:3], b[:3]),
                    a[:2] == (3, 2) and a[2] == (502, "bgw") and b[:2] == (3, 2) and b[2] == (504, "gto"))

    def test_C7_kalici_csrf_iki_taze_token_yanit_doner(self):
        n, u, son, iz = self.kos([_Yanit(403, "CSRF token validation failed")])
        self.kaydet("C7 FP kalıcı CSRF 403 → 3 istek · 2 taze token · 403 yanıtı döner · Z52 izi BOŞ (istek işlenmedi)",
                    "(3, 2 taze, 403, [])", (n, self.tazelenen, son, iz),
                    n == 3 and self.tazelenen == [True, True] and son[0] == 403 and iz == [])

    def test_C8_408_sonra_200_fp(self):
        n, u, son, iz = self.kos([_Yanit(408, ""), _Yanit(200, "ok")])
        self.kaydet("C8 FP: 408 → 200 → 2 istek · başarı", "(2, 1, 200)", (n, u, son),
                    n == 2 and u == 1 and son == (200, "ok"))

    def test_C9_501_dokunulmadi(self):
        n, u, son, _iz = self.kos([_Yanit(501, "ni")])
        self.kaydet("C9 501 bilinçli dokunulmadı (kaynak çekirdekle aynı, minimal) → 3 istek · son yanıt döner",
                    "(3, 2, 501)", (n, u, son), n == 3 and u == 2 and son == (501, "ni"))


if __name__ == "__main__":
    unittest.main()
