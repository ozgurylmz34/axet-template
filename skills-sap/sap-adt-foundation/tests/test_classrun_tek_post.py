# -*- coding: utf-8 -*-
"""Z190 (2026-10-04) — `adt_classrun` yan etkili koşuyu İKİ KEZ göndermesin.

Kaynak çekirdek kuralı (PDF/ADS kılavuzu §4): "Mail gönderen classrun'u yeniden deneyen
bir araçla koşma. Bazı ADT istemcileri 200 dışı yanıtta POST'u tekrarlar ⇒ mail iki kez gider."
aXet'te iki katmanda ölçüldü:
  ① `SAPClient.run_classrun` — `status_code != 200` dalı 500/4xx'te ikinci POST atıyordu.
  ② `SAPADTClient._build_session` adapter'ı — `Retry(status_forcelist=(429,502,503,504),
     allowed_methods ∋ POST)` → 502/503/504'te ve OKUMA ZAMAN AŞIMINDA POST 4 kez gidiyordu.

Bu testler GERÇEK kod yolunu (gerçek `_build_session` + `requests` + `urllib3`) yerel bir sahte
HTTP sunucusuna (127.0.0.1) karşı koşar ve sunucuya ULAŞAN POST'ları sayar. SAP'ye bağlanmaz.
Kalibrasyon: aynı sunucuda classrun DIŞI bir yol 504'te hâlâ 4 POST alır (sayaç tekrarı görebiliyor).
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
from sap_adt_lib import SAPADTClient  # noqa: E402
from sap_client import SAPClient  # noqa: E402

DNI = "Class ZCL_X does not implement if_oo_adt_classrun~main!"
YAVAS_SN = 1.2
ZAMAN_ASIMI_SN = 0.4


class _Sunucu:
    """Yol başına yanıt planı + ulaşan POST sayacı."""

    def __init__(self):
        self.plan: dict[str, list] = {}
        self.sayac: dict[str, int] = {}
        self.kilit = threading.Lock()
        dis = self

        class _H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):  # noqa: D401
                pass

            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                if n:
                    self.rfile.read(n)
                with dis.kilit:
                    dis.sayac[self.path] = dis.sayac.get(self.path, 0) + 1
                    liste = dis.plan.get(self.path) or [(200, "ok")]
                    kod, govde = liste.pop(0) if len(liste) > 1 else liste[0]
                if kod == "yavas":
                    time.sleep(YAVAS_SN)
                    kod, govde = 200, "gec"
                veri = govde.encode("utf-8")
                try:
                    self.send_response(kod)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_header("Content-Length", str(len(veri)))
                    self.end_headers()
                    self.wfile.write(veri)
                except Exception:  # noqa: BLE001 — istemci zaman aşımıyla kapatmış olabilir
                    pass

        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _H)
        self.srv.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def kapat(self):
        self.srv.shutdown()
        self.srv.server_close()


def _adt_istemcisi(url: str) -> SAPADTClient:
    """Gerçek `_build_session` + gerçek `_request_with_csrf_retry` + gerçek `new_session`."""
    c = SAPADTClient.__new__(SAPADTClient)
    c.url = url
    c.client = "000"
    c.language = "TR"
    c._auth_provider = None
    c._get_auth_headers = lambda: {}
    c.debug_enabled = False
    c.timeout_default = ZAMAN_ASIMI_SN
    c.csrf_token = "T"
    c._update_cookies = lambda r: None
    c._invalidate_csrf_cache = lambda: None
    c.new_session_sayisi = 0

    def _fetch(force_refresh=False):
        c.csrf_token = "T"
    c.fetch_csrf_token = _fetch
    c._get_headers = lambda accept_type=None, content_type=None: {"Accept": accept_type or "x",
                                                                  "X-CSRF-Token": c.csrf_token or ""}
    gercek_new_session = c.new_session

    def _say_new_session():
        c.new_session_sayisi += 1
        gercek_new_session()
    c.new_session = _say_new_session
    c.session = c._build_session()
    return c


def _sap_istemcisi(adt: SAPADTClient) -> SAPClient:
    s = SAPClient.__new__(SAPClient)
    s.adt_client = adt
    s.debug_enabled = False
    # 'does not implement' teşhisi bu testlerin konusu değil — yapısal geçerli say.
    s._diagnose_classrun_binding = lambda name: {"structurally_valid": True, "active_source_bytes": 1}
    return s


class ClassrunTekPost(unittest.TestCase):
    YOL = "/sap/bc/adt/oo/classrun/zcl_x"

    def setUp(self):
        self.sunucu = _Sunucu()
        self.adt = _adt_istemcisi(self.sunucu.url)
        self.sap = _sap_istemcisi(self.adt)

    def tearDown(self):
        try:
            self.adt.session.close()
        except Exception:  # noqa: BLE001
            pass
        self.sunucu.kapat()

    def kaydet(self, ad, beklenen, gercek, ok):
        H.kaydet(f"CLASSRUN {ad}", beklenen, str(gercek)[:160], ok)
        self.assertTrue(ok, f"{ad}: {gercek}")

    def _kos(self, plan):
        self.sunucu.plan[self.YOL] = list(plan)
        res = self.sap.run_classrun("ZCL_X")
        time.sleep(0.05)
        return res, self.sunucu.sayac.get(self.YOL, 0)

    # (a) 500 → tek POST + işaret ------------------------------------------------------------
    def test_classrun_500_tek_post_ve_isaret(self):
        res, n = self._kos([(500, "dump"), (200, "IKINCI KOSU")])
        ok = (n == 1 and res.get("ok") is False and res.get("status") == 500
              and res.get("islenmis_olabilir") is True and res.get("yeniden_denenmedi") is True
              and "SOST" in (res.get("uyari") or "") and self.adt.new_session_sayisi == 0)
        self.kaydet("500 → 1 POST · islenmis_olabilir · oturum sıfırlanmadı", "1 POST", [n, res], ok)

    # (a2) adapter katmanı: 502/503/504 → tek POST ------------------------------------------
    def test_classrun_502_503_504_adapter_tekrarlamaz(self):
        sonuc = {}
        for kod in (502, 503, 504):
            self.sunucu.sayac.clear()
            res, n = self._kos([(kod, "gw")])
            sonuc[kod] = (n, res.get("status"), res.get("islenmis_olabilir"))
        ok = all(v == (1, k, True) for k, v in sonuc.items())
        self.kaydet("502/503/504 → her biri 1 POST + işaret", "(1, kod, True)", sonuc, ok)

    # (b) 200 + "does not implement" → oturum sıfırla + ikinci POST (mevcut davranış) -------
    def test_classrun_200_does_not_implement_oturum_sifirlar_ikinci_post(self):
        eski_oturum = self.adt.session
        res, n = self._kos([(200, DNI), (200, "MERHABA")])
        ok = (n == 2 and self.adt.new_session_sayisi == 1 and self.adt.session is not eski_oturum
              and res.get("ok") is True and res.get("output") == "MERHABA"
              and "islenmis_olabilir" not in res)
        self.kaydet("200+'does not implement' → new_session + 2. POST", "2 POST · ok", [n, res], ok)

    # (c) 200 normal → tek POST, işaret yok --------------------------------------------------
    def test_classrun_200_normal_tek_post(self):
        res, n = self._kos([(200, "MERHABA")])
        ok = n == 1 and res.get("ok") is True and "islenmis_olabilir" not in res
        self.kaydet("200 normal → 1 POST · işaretsiz", "1 POST", [n, res], ok)

    # (c2) sınıfın KENDİ çıktısında "does not implement" geçmesi bayat oturum DEĞİLDİR ---------
    def test_classrun_cikti_icindeki_does_not_implement_tekrar_etmez(self):
        govde = "Mail gonderildi. Kontrol: ZCL_Y does not implement ZIF_Z"
        res, n = self._kos([(200, govde), (200, "IKINCI KOSU")])
        ok = (n == 1 and self.adt.new_session_sayisi == 0 and res.get("ok") is True
              and res.get("output") == govde and "islenmis_olabilir" not in res)
        self.kaydet("çıktıdaki gevşek alt metin → 1 POST · oturum sıfırlanmadı", "1 POST · ok", [n, res], ok)

    # (c3) 200-dışı yanıtta bayat-oturum imzası olsa bile işaret düşmez -----------------------
    def test_classrun_500_bayat_imza_isaret_dusmez(self):
        res, n = self._kos([(500, DNI), (200, "IKINCI KOSU")])
        ok = (n == 1 and self.adt.new_session_sayisi == 0 and res.get("ok") is False
              and res.get("islenmis_olabilir") is True and res.get("code") == "classrun_islenmis_olabilir")
        self.kaydet("500 + imza → 1 POST + işaret (teşhis dalına girmez)", "1 POST · işaret", [n, res], ok)

    # (d) okuma zaman aşımı → tek POST, anlamlı sonuç ----------------------------------------
    def test_classrun_zaman_asimi_tek_post(self):
        res, _ = self._kos([("yavas", "")])
        time.sleep(YAVAS_SN * 4 + 0.5)  # adapter tekrarlasaydı geç gelen POST'lar da sayılsın
        n = self.sunucu.sayac.get(self.YOL, 0)
        ok = (n == 1 and res.get("ok") is False and res.get("islenmis_olabilir") is True
              and res.get("yeniden_denenmedi") is True and "timed out" in (res.get("error") or "").lower())
        self.kaydet("okuma zaman aşımı → 1 POST + işaret", "1 POST", [n, res], ok)

    # (e) bayat-oturum dalındaki ikinci POST da tekrarsız adapter'dan geçer ------------------
    def test_classrun_new_session_sonrasi_mount_korunur(self):
        res, n = self._kos([(200, DNI), (504, "gw")])
        ok = (n == 2 and self.adt.new_session_sayisi == 1 and res.get("status") == 504
              and res.get("islenmis_olabilir") is True)
        self.kaydet("new_session sonrası 504 → yine tek POST (toplam 2)", "2 POST", [n, res], ok)

    # (f) bağlantı kurma tekrarı açık, okuma/durum tekrarı kapalı (urllib3'ün kendi mantığı) -
    def test_classrun_adapter_baglanti_tekrari_serbest_okuma_kapali(self):
        url = self.adt._classrun_onek() + "zcl_x"
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
        ok = baglanti == "tekrar" and okuma != "tekrar" and r.status_forcelist in ((), set(), frozenset())
        self.kaydet("classrun adapter: bağlantı → tekrar · okuma → tekrarsız", "tekrar/tekrarsız",
                    [baglanti, okuma, r.status_forcelist], ok)

    # (g) işaretli sonuç bilinen-hata ipucunu K-28'e yönlendirir; normal 200 yönlendirmez -----
    def test_classrun_isaret_known_errors_k28(self):
        from sapadt import hints
        res, _ = self._kos([(500, "dump")])
        kh = hints.known_errors_hint("adt_classrun", res, None, 1)
        bolumler = [r["section"] for r in (kh or {}).get("refs", [])]
        res_ok, _ = self._kos([(200, "MERHABA")])
        kh_ok = hints.known_errors_hint("adt_classrun", res_ok, None, 0)
        ok = "K-28" in bolumler and kh_ok is None
        self.kaydet("işaret → known_errors_hint K-28 · 200 → ipucu yok", "K-28", [bolumler, kh_ok], ok)

    # Kalibrasyon (doğru-pozitif): classrun DIŞI yol eski adapter'da — 504 → 4 POST -----------
    def test_classrun_disi_yol_kalibrasyon_adapter_degismedi(self):
        yol = "/sap/bc/adt/activation"
        self.sunucu.plan[yol] = [(504, "gw")]
        try:
            self.adt.session.post(self.sunucu.url + yol, timeout=5)
            sonuc = "yanit"
        except requests.exceptions.RetryError:
            sonuc = "RetryError"
        time.sleep(0.05)
        n = self.sunucu.sayac.get(yol, 0)
        ok = n == 4 and sonuc == "RetryError"
        self.kaydet("kalibrasyon: classrun dışı yol 504 → 4 POST (push/activate davranışı aynı)",
                    "4 POST", [n, sonuc], ok)


if __name__ == "__main__":
    unittest.main()
