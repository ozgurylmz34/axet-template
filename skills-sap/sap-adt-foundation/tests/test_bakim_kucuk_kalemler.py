# -*- coding: utf-8 -*-
"""Bakım kalemleri (2026-11-19) — süreç içi, ağ yok, SAP yok.

  · Z150 — `redact.temizle_metin` bilinen sırları HARF DUYARSIZ maskeler (host hata metninde büyük harfle geçebilir).
  · Z210 — `delete_object` başarısız silmede durum kodunu kaybetmez: `requests.Response` 4xx/5xx'te `bool()` False'tur,
           `if last_response` testi kodu 'unknown' yapıyordu (SAPADTError.status_code None, NO_LOCK_SUPPORT dalı ölü).
  · Z209 — `adt_atc_check` bulgu sayısı `max_verdicts` tavanına eşitse `kesilmis_olabilir` bayrağı + kapsam satırı.
  · Z220 — `create_table_type` / `create_message_class` / `create_lock_object` 2xx dışı yanıt gövdesi redaksiyon +
           kesme sırasından geçer (host / parola `***`).
  · D14  — `_err_from_exc` çıktısında yapısal `status_code` alanı (istisna taşıyorsa).
"""
from __future__ import annotations

import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import _helpers as H

sys.dont_write_bytecode = True
LIB = H.SCRIPTS / "sapadt" / "lib"
for _p in (H.SCRIPTS, LIB):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import sapadt  # noqa: E402,F401  (lib yolunu hazırlar)
import requests  # noqa: E402
import sap_adt_lib as L  # noqa: E402
import sap_client as SC  # noqa: E402
from sapadt import redact as R  # noqa: E402

SAHTE_HOST = "sap-dev.ornek.test"
_KOK: Path | None = None
_ESKI_ENV: dict = {}


def setUpModule():
    global _KOK
    _KOK = Path(tempfile.mkdtemp(prefix="axet_bakim_kalem_"))
    dev = H.make_project(_KOK, "dev")
    for k in ("AXET_SAP_PROJECT_DIR", "ADT_SAP_TIER"):
        _ESKI_ENV[k] = os.environ.get(k)
    os.environ.pop("ADT_SAP_TIER", None)
    os.environ["AXET_SAP_PROJECT_DIR"] = str(dev)


def tearDownModule():
    for k, v in _ESKI_ENV.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    if _KOK is not None:
        shutil.rmtree(_KOK, ignore_errors=True)


def _yanit(kod: int, govde: str = "") -> requests.Response:
    r = requests.Response()
    r.status_code = kod
    r._content = govde.encode("utf-8")
    r.encoding = "utf-8"
    return r


class _Taban(unittest.TestCase):
    def kaydet(self, ad, beklenen, gercek, ok):
        H.kaydet(f"BAKIM {ad}", beklenen, str(gercek)[:160], ok)
        self.assertTrue(ok, f"{ad}: {gercek}")


# --------------------------------------------------------------------------------------------- Z150
class Z150HarfDuyarsizMaskeleme(_Taban):
    def test_Z150_host_buyuk_harfle_gecse_de_maskelenir(self):
        sirlar = R.host_sirlari(f"https://{SAHTE_HOST}:44300")
        metin = (f"HTTPSConnectionPool: Max retries exceeded ... Failed to resolve '{SAHTE_HOST.upper()}' · "
                 f"Sertifika adı {SAHTE_HOST.title()}:44300 eşleşmedi · küçük {SAHTE_HOST}")
        cikti = R.temizle_metin(metin, sirlar)
        parola = R.temizle_metin("parola=S3CR3T-PAROLA!9 ve s3cr3t-parola!9",
                                 R.bilinen_sirlar(H.KULLANICI, H.PAROLA))
        kalan = [v for v in (SAHTE_HOST, SAHTE_HOST.upper(), SAHTE_HOST.title()) if v.lower() in cikti.lower()]
        ok = not kalan and cikti.count("***") >= 3 and "s3cr3t" not in parola.lower()
        self.kaydet("Z150 host BÜYÜK / Başlık / küçük harfle → hepsi *** · parola harf varyantı ***",
                    "host izi yok", cikti if not ok else f"{cikti} | {parola}", ok)

    def test_Z150_sir_olmayan_metin_degismez(self):
        metin = "ZCL_X aktive edildi — sap-dev değil, ornek.test de değil"
        self.kaydet("Z150 kontrol: sırla eşleşmeyen metin aynen kalır", "aynı",
                    R.temizle_metin(metin, R.host_sirlari(f"https://{SAHTE_HOST}")),
                    R.temizle_metin(metin, R.host_sirlari(f"https://{SAHTE_HOST}")) == metin)


# --------------------------------------------------------------------------------------------- Z210
def _silme_istemcisi(kod: int, govde: str) -> tuple[L.SAPADTClient, list]:
    c = L.SAPADTClient.__new__(L.SAPADTClient)
    c.url = "http://127.0.0.1:9"
    c.debug_enabled = False
    c.timeout_short = 1
    c._get_headers = lambda: {}
    cagri: list = []

    def _istek(metot, url, **kw):
        cagri.append((metot, kw.get("params")))
        return _yanit(kod, govde)

    c._request_with_csrf_retry = _istek
    return c, cagri


class Z210SilmeDurumKodu(_Taban):
    def test_Z210_403_silmede_durum_kodu_ve_govde_korunur(self):
        c, cagri = _silme_istemcisi(403, "<exc:exception><message>Yetki yok</message></exc:exception>")
        try:
            c.delete_object("/sap/bc/adt/oo/classes/zcl_x", "KILIT123", transport="DEVK900001")
            hata = None
        except L.SAPADTError as e:
            hata = e
        ok = (hata is not None and not isinstance(hata, L.SAPLockError) and hata.status_code == 403
              and "Yetki yok" in (hata.response_text or "") and len(cagri) >= 1)
        self.kaydet("Z210 silme 403 → SAPADTError.status_code 403 + gövde", "403 · gövde var",
                    None if hata is None else (type(hata).__name__, hata.status_code, hata.response_text), ok)

    def test_Z210_kilit_desteksiz_400_kilit_hatasi_dali_calisir(self):
        c, _ = _silme_istemcisi(400, "lock handle required")
        try:
            c.delete_object("/sap/bc/adt/oo/classes/zcl_x", "NO_LOCK_SUPPORT")
            hata = None
        except L.SAPADTError as e:
            hata = e
        ok = isinstance(hata, L.SAPLockError) and hata.status_code == 400 and "lock endpoint" in str(hata)
        self.kaydet("Z210 NO_LOCK_SUPPORT + 400 → SAPLockError (eskiden ölü dal)", "SAPLockError 400",
                    None if hata is None else (type(hata).__name__, hata.status_code, str(hata)[:80]), ok)


# --------------------------------------------------------------------------------------------- Z209
class _AtcAdt:
    def __init__(self, n):
        self.n = n
        self.giden = []    # SAP'ye giden max_verdicts değerleri (çağrı başına)

    def run_atc_check(self, url, variant=None, max_verdicts=100):
        self.giden.append(max_verdicts)
        return {"findings": [{"priority": "2", "message": f"b{i}"} for i in range(self.n)]}


class _AtcIstemci:
    def __init__(self, n):
        self.adt_client = _AtcAdt(n)


class Z209AtcTavan(_Taban):
    def _kos(self, n, tavan):
        from sapadt.tools import query as Q
        eski = Q._get_client
        self.istemci = _AtcIstemci(n)
        Q._get_client = lambda: self.istemci
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                return Q.adt_atc_check("ZCL_X", "class", variant="V", max_verdicts=tavan)
        finally:
            Q._get_client = eski

    def test_Z209_metin_tavan_kabul_gecersiz_tavan_sapye_gitmez(self):
        """bug-gate F1: CLI JSON'u tip dönüştürmeden geçirir (`{"max_verdicts":"50"}`). Eski kodda (Z209 öncesi)
        bu girdi çalışıyordu; Z209'un `>=` karşılaştırması TypeError verip SAP'de koşmuş ATC'nin bulgularını
        kaybediyordu. Metin → int; geçersiz → `invalid_argument` ve SAP'ye istek GİTMEZ."""
        sonuc = {}
        for tavan, n in (("50", 50), (" 7 ", 3), (100, 5)):
            r = self._kos(n, tavan)
            sonuc[repr(tavan)] = (r.get("ok"), r.get("finding_count"), r.get("kesilmis_olabilir"),
                                  self.istemci.adt_client.giden)
        gecersiz = {}
        for tavan in ("abc", "0", "-5", "", "1.5", "²", None, True, 0, 2.5):
            r = self._kos(5, tavan)
            gecersiz[repr(tavan)] = (r.get("ok"), r.get("error"), self.istemci.adt_client.giden)
        # bug-gate R2 F4: yardımcı `@profil_tool()` ile `def adt_atc_check` arasına girince dekoratör YARDIMCIYI kaydetti,
        # araç kayıttan düştü (her çağrı `unknown_tool`). Doğrudan fonksiyon çağrısı bunu göremez ⇒ kayıt da ölçülür.
        from sapadt._app import load_all_tools
        kayit = load_all_tools()
        sonuc["kayit"] = ("adt_atc_check" in kayit, "_pozitif_tam_sayi" in kayit)
        ok = (sonuc == {"'50'": (True, 50, True, [50]), "' 7 '": (True, 3, False, [7]), "100": (True, 5, False, [100]),
                        "kayit": (True, False)}
              and all(v == (False, "invalid_argument", []) for v in gecersiz.values()))
        self.kaydet("Z209 F1 metin tavan '50'/' 7 ' → int · geçersiz → invalid_argument, SAP'ye gitmez",
                    "50 bayrak · 7 yok · 10 geçersiz reddi", [sonuc, gecersiz], ok)

    def test_Z209_tavana_esit_bulgu_kesilmis_olabilir(self):
        r100 = self._kos(100, 100)
        r99 = self._kos(99, 100)
        r5 = self._kos(5, 5)
        ok = (r100.get("ok") is True and r100.get("kesilmis_olabilir") is True
              and "KESİLMİŞ OLABİLİR" in str(r100.get("kapsam"))
              and r99.get("kesilmis_olabilir") is False and "KESİLMİŞ" not in str(r99.get("kapsam"))
              and r5.get("kesilmis_olabilir") is True and r99.get("finding_count") == 99)
        self.kaydet("Z209 ATC 100/100 → bayrak · 99/100 → yok · 5/5 → bayrak", "True/False/True",
                    [r100.get("kesilmis_olabilir"), r99.get("kesilmis_olabilir"), r5.get("kesilmis_olabilir"),
                     r100.get("kapsam")], ok)


# --------------------------------------------------------------------------------------------- Z220
class _Oturum:
    def __init__(self, kod, govde):
        self.kod, self.govde = kod, govde

    def post(self, *a, **k):
        return _yanit(self.kod, self.govde)


class _YaratmaAdt:
    def __init__(self, kod, govde):
        self.url = f"https://{SAHTE_HOST}:44300"
        self.client, self.language, self.csrf_token = "100", "TR", "T"
        self.user, self.password = H.KULLANICI, H.PAROLA
        self.session = _Oturum(kod, govde)

    def fetch_csrf_token(self, force_refresh=False):
        return "T"

    def _get_auth_header(self):
        return "Basic eA=="


class Z220YaratmaHataGovdesi(_Taban):
    def _istemci(self, kod, govde):
        c = SC.SAPClient.__new__(SC.SAPClient)
        c.debug_enabled = False
        c.debug_log_path = None
        c.adt_client = _YaratmaAdt(kod, govde)
        return c

    def test_Z220_uc_yaratma_yolu_govdeyi_redakte_ve_kesik_basar(self):
        govde = (f"<exc:exception><message>Kayit reddedildi {SAHTE_HOST.upper()}</message>"
                 f"<detail>https://{SAHTE_HOST}:44300/sap/bc/adt parola={H.PAROLA} {'x' * 700}</detail>"
                 "</exc:exception>")
        sonuc = {}
        for ad, cagir in (("ttyp", lambda c: c.create_table_type("ZTT_X", "ZDT", "Tablo tipi", "ZPKG")),
                          ("msag", lambda c: c.create_message_class("ZMSG_X", "Mesaj", "ZPKG")),
                          ("enqu", lambda c: c.create_lock_object("EZX", "ZTAB", "Kilit", "ZPKG", ["F1"]))):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                donus = cagir(self._istemci(500, govde))
            log = buf.getvalue()
            satir = next((s for s in log.splitlines() if s.startswith(SC.SAP_GOVDE_IMZASI)), "")
            sonuc[ad] = (donus, SAHTE_HOST in log.lower(), H.PAROLA in log, "***" in satir, "KESİLDİ" in satir,
                         "[ERROR] [500]" in log, "Kayit reddedildi" in satir)
        ok = all(v == (False, False, False, True, True, True, True) for v in sonuc.values())
        self.kaydet("Z220 ttyp/msag/enqu 500 → gövde ***'lı, KESİLDİ, [ERROR] [500] · host/parola yok",
                    "üçü (False, F, F, T, T, T, T)", sonuc, ok)


# --------------------------------------------------------------------------------------------- D14
class D14ErrStatusCode(_Taban):
    def test_D14_err_from_exc_status_code_yapisal(self):
        from sapadt.tools import atom as A
        r = A._err_from_exc(L.SAPADTError("Failed", status_code=409, response_text="x"))
        r_kilit = A._err_from_exc(L.SAPLockError("kilitli", status_code=403))
        r_yok = A._err_from_exc(L.SAPADTError("durumsuz"))
        r_genel = A._err_from_exc(ValueError("boom"))
        ok = (r.get("status_code") == 409 and r.get("error") == "sap_error"
              and r_kilit.get("status_code") == 403 and r_kilit.get("error") == "locked"
              and "status_code" not in r_yok and "status_code" not in r_genel)
        self.kaydet("D14 _err_from_exc: 409/403 → status_code alanı · durumsuz/genel → alan yok", "409 · 403 · yok · yok",
                    [r.get("status_code"), r_kilit.get("status_code"), "status_code" in r_yok,
                     "status_code" in r_genel], ok)


if __name__ == "__main__":
    unittest.main()
