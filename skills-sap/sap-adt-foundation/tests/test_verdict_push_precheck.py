# -*- coding: utf-8 -*-
"""Push sözdizimi ön-kontrolü ÖLÇÜLEMEDİĞİNDE görünür iz — çevrimdışı kontrol grubu.

`SAPClient.push_object` aktivasyondan önce class/interface için sözdizimi kontrolü koşar ve
YALNIZ `valid is False and errors` durumunda aktivasyonu durdurur. Kontrolün KOŞMADIĞI üç giriş
push'u sürdürür ama sonuçta iz bırakmıyordu:
  (1) `valid is None` (SAP kontrolü koşmadı: boş/kısa gövde, yalnız generation)
  (2) `SAPClient.syntax_check` istisnayı yuttu → `{'valid': False, 'error': ...}`, errors YOK
  (3) `self.syntax_check` istisna fırlattı → `_pre = None`
Davranış (devam) korunur — engellemek sahte-HATA üretirdi. Eklenen yalnız görünürlüktür:
`syntax_precheck: 'olculemedi'` + `sozdizimi_sebep` + `[UNVERIFIED]` satırı; MCP
`adt_push_source` üst seviyede `syntax_precheck` + `syntax_precheck_notice` verir.

Kontrol satırları (silinmez): gerçek E mesajı ve 403 kilit aktivasyonu DURDURMAYA devam eder;
SAP kontrolü koşup temiz dönerse işaret YOK; kapsam dışı tip (prog) işaretlenmez.
Gerçek SAP'ye bağlanılmaz: yalnız sözdizimi POST'u sahte HTTP'dir; lock/upload/aktivasyon uçları
sahte alt sınıfta sayaçtır. GERÇEK `push_object` · `syntax_check` · `syntax_check_via_activation`
gövdeleri koşar.
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

import sapadt  # noqa: E402,F401
import sap_adt_lib as L  # noqa: E402
import sap_client as SC  # noqa: E402

CAPA_SC = "on-kontrolu OLCULEMEDI"
CAPA_BLOCK = "[BLOCK] Aktivasyon-oncesi syntax-check BASARISIZ"

_CHKL = "http://www.sap.com/abapxml/checklist"
GOVDE_TRUE = ('<?xml version="1.0" encoding="utf-8"?><chkl:messages xmlns:chkl="%s"><chkl:properties '
              'checkExecuted="true" activationExecuted="true" generationExecuted="false"/></chkl:messages>' % _CHKL)
GOVDE_GEN = ('<?xml version="1.0" encoding="utf-8"?><chkl:messages xmlns:chkl="%s"><chkl:properties '
             'checkExecuted="false" activationExecuted="false" generationExecuted="true"/></chkl:messages>' % _CHKL)
GOVDE_E = ('<?xml version="1.0" encoding="utf-8"?><chkl:messages xmlns:chkl="%s"><chkl:properties '
           'checkExecuted="true" activationExecuted="false" generationExecuted="false"/><msg type="E" line="3">'
           '<shortText><txt>Ornek sozdizimi hatasi</txt></shortText></msg></chkl:messages>' % _CHKL)
KILIT_403 = ('<?xml version="1.0"?><exc:exception xmlns:exc="http://www.sap.com/abapxml/types/'
             'communicationframework"><properties><entry key="T100KEY-V1">TESTUSER_B</entry>'
             '</properties></exc:exception>')
AD = "ZCL_BC000_DEMO_PUSH"
KAYNAK = ("CLASS zcl_bc000_demo_push DEFINITION.\nENDCLASS.\n"
          "CLASS zcl_bc000_demo_push IMPLEMENTATION.\nENDCLASS.\n")
TRANSPORT = "TESTK900001"


class _Y:
    def __init__(self, kod, metin=""):
        self.status_code, self.text, self.headers = kod, metin, {}
        self.content = metin.encode("utf-8")


class _SozSunucu:
    """Sözdizimi kontrolü POST'u: sabit (kod, gövde) döner; başka her istek 599."""

    def __init__(self, kod, govde):
        self.kod, self.govde, self.postlar = kod, govde, []
        self.headers: dict = {}

    def request(self, method, url, headers=None, timeout=None, **kw):
        if method.lower() == "post" and url.endswith("/sap/bc/adt/activation"):
            self.postlar.append(dict(kw.get("params") or {}))
            return _Y(self.kod, self.govde)
        return _Y(599, "beklenmeyen istek")


class _SahteAdt(L.SAPADTClient):
    def __init__(self, sunucu):  # noqa: D401 — gerçek __init__ bağlantı arar
        self.url = "https://example.invalid:44300"
        self.session = sunucu
        self.csrf_token = "TOKEN"
        self.client = "100"
        self.language = "TR"
        self.user = "TESTUSER_A"
        self._auth_provider = None
        self.debug_enabled = False
        self.timeout_default = 5
        self.timeout_short = 5
        self._last_lock_effective_transport = TRANSPORT
        self._last_lock_is_link_up = ""
        self.aktivasyon = 0

    def _get_headers(self, *a, **k):
        return {}

    def fetch_csrf_token(self, force_refresh=False):
        return self.csrf_token

    def _update_cookies(self, response):
        return None

    def get_transport_info(self, url):
        return TRANSPORT

    def is_object_locked(self, url):
        return {"locked": False}

    def register_object_in_transport(self, name, transport, object_type):
        return {"registered": True, "method": "sahte"}

    def fetch_source_etag(self, url):
        return "etag-sahte"

    def lock_object(self, url, transport=None, **kw):
        return "LOCK1"

    def set_object_source(self, url, src, lock, transport, etag=None):
        return True

    def unlock_object(self, url, lock):
        return True

    def activate_object(self, name, url):
        self.aktivasyon += 1
        return {"success": True}

    def get_object_source(self, url, return_etag=False, version=None):
        return KAYNAK


class PushOnKontrol(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="axet_push_onkontrol_"))
        cls.dosya = cls.root / f"{AD}.clas.abap"
        cls.dosya.write_text(KAYNAK, encoding="utf-8")
        cls._eski_sleep = SC.time.sleep if hasattr(SC, "time") else None

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def kaydet(self, ad, beklenen, gercek, ok):
        H.kaydet(f"PUSH-ÖN {ad}", beklenen, str(gercek)[:160], ok)
        self.assertTrue(ok, f"{ad}: {gercek}")

    def push(self, kod, govde, tip="class", sc_istisna=False):
        sv = _SozSunucu(kod, govde)
        ist = object.__new__(SC.SAPClient)
        ist.adt_client = _SahteAdt(sv)
        ist.debug_enabled = False
        ist.local_base = self.root
        ist._find_existing_transport = lambda name, otype, transport: transport
        if sc_istisna:
            def _patlar(*a, **k):
                raise RuntimeError("sahte cagri istisnasi")
            ist.syntax_check = _patlar
        tampon = io.StringIO()
        import time as _time
        eski_sleep = _time.sleep
        _time.sleep = lambda *_a, **_k: None   # readback bekleme adımı; ağ yok
        try:
            with contextlib.redirect_stdout(tampon):
                r = ist.push_object(AD, object_type=tip, transport=TRANSPORT, source_file=str(self.dosya))
        finally:
            _time.sleep = eski_sleep
        return r, tampon.getvalue(), ist.adt_client, sv

    @staticmethod
    def ozet(r, log, adt):
        return (f"precheck={r.get('syntax_precheck')} sebep={r.get('sozdizimi_sebep')!r} "
                f"aktivasyon={adt.aktivasyon} success={r.get('success')} capa={'VAR' if CAPA_SC in log else 'YOK'}")

    def olculemedi(self, ad, r, log, adt, sebep_on):
        ok = (r.get("syntax_precheck") == "olculemedi"
              and str(r.get("sozdizimi_sebep") or "").startswith(sebep_on)
              and adt.aktivasyon == 1 and r.get("activated") is True and r.get("success") is True
              and CAPA_SC in log and CAPA_BLOCK not in log)
        self.kaydet(ad, "devam + olculemedi(%s)" % sebep_on, self.ozet(r, log, adt), ok)

    def test_K1_valid_none_yalniz_generation_isaretlenir(self):
        r, log, adt, sv = self.push(200, GOVDE_GEN)
        self.olculemedi("K1 valid None (yalnız generation)", r, log, adt, "kontrol_kosmadi")

    def test_K2_valid_none_bos_govde_isaretlenir(self):
        r, log, adt, sv = self.push(200, "")
        self.olculemedi("K2 valid None (boş gövde)", r, log, adt, "govde_bos_veya_kisa")

    def test_K3_yutulan_kontrol_istisnasi_isaretlenir(self):
        r, log, adt, sv = self.push(400, "<html>Bad Request</html>")
        self.olculemedi("K3 syntax_check istisnası yutuldu", r, log, adt, "kontrol_istisnasi:")

    def test_K4_cagri_istisnasi_isaretlenir(self):
        r, log, adt, sv = self.push(200, GOVDE_TRUE, sc_istisna=True)
        self.olculemedi("K4 syntax_check çağrısı istisna fırlattı", r, log, adt, "cagri_istisnasi:")

    def test_K5_kontrol_sap_e_mesaji_durdurur(self):
        r, log, adt, sv = self.push(200, GOVDE_E)
        ok = (adt.aktivasyon == 0 and r.get("activated") is False and r.get("success") is False
              and r.get("syntax_precheck") == "failed" and bool(r.get("syntax_errors")) and CAPA_BLOCK in log
              and "sozdizimi_sebep" not in r and CAPA_SC not in log)
        self.kaydet("K5 KONTROL E mesajı durdurur", "failed, işaret yok", self.ozet(r, log, adt), ok)

    def test_K6_kontrol_403_kilit_durdurur(self):
        r, log, adt, sv = self.push(403, KILIT_403)
        ok = adt.aktivasyon == 0 and r.get("syntax_precheck") == "failed" and r.get("success") is False
        self.kaydet("K6 KONTROL 403 kilit durdurur", "failed", self.ozet(r, log, adt), ok)

    def test_K7_kontrol_temiz_isaret_yok(self):
        r, log, adt, sv = self.push(200, GOVDE_TRUE)
        ok = (adt.aktivasyon == 1 and r.get("success") is True and "syntax_precheck" not in r
              and "sozdizimi_sebep" not in r and CAPA_SC not in log)
        self.kaydet("K7 KONTROL temiz → işaret yok", "success, işaret yok", self.ozet(r, log, adt), ok)

    def test_K8_kontrol_kapsam_disi_tip_isaretlenmez(self):
        r, log, adt, sv = self.push(200, GOVDE_GEN, tip="prog")
        ok = len(sv.postlar) == 0 and adt.aktivasyon == 1 and "syntax_precheck" not in r and CAPA_SC not in log
        self.kaydet("K8 KONTROL prog (kapsam dışı)", "POST yok, işaret yok",
                    f"post={len(sv.postlar)} " + self.ozet(r, log, adt), ok)


class PushOnKontrolMcp(unittest.TestCase):
    """MCP `adt_push_source`: ölçülemedi işareti ÜST SEVİYEDE; `ok` değişmez.

    Ağdan önceki kapılar gerçek kalır (tier, namespace, Yasak B taraması). Yalnız çekme kaydı ve
    canlı okuma sahtedir (PULL-BEFORE-EDIT kaydı "çekildi ve değişmedi" der); reviewer atlanır.
    """

    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="axet_push_mcp_"))
        cls.dev = H.make_project(cls.root, "dev")
        cls._eski_env = {k: os.environ.get(k) for k in ("AXET_SAP_PROJECT_DIR", "ADT_SAP_TIER")}
        os.environ.pop("ADT_SAP_TIER", None)
        os.environ["AXET_SAP_PROJECT_DIR"] = str(cls.dev)
        from sapadt.tools import atom
        cls.atom = atom
        ps = atom._pull_state
        cls._eski = (atom._get_client, atom._adt_get_oku, ps.kayit_al, ps.kaydet, ps.sil)
        ozet = ps.ozet(KAYNAK)
        atom._adt_get_oku = lambda name, object_type, *a, **k: {"ok": True, "exists": True, "source": KAYNAK}
        ps.kayit_al = lambda name, object_type: ({"sha256": ozet, "pulled_at": "test"}, None)
        ps.kaydet = lambda *a, **k: None
        ps.sil = lambda *a, **k: None

    @classmethod
    def tearDownClass(cls):
        atom, ps = cls.atom, cls.atom._pull_state
        atom._get_client, atom._adt_get_oku, ps.kayit_al, ps.kaydet, ps.sil = cls._eski
        for k, v in cls._eski_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(cls.root, ignore_errors=True)

    def kaydet(self, ad, beklenen, gercek, ok):
        H.kaydet(f"PUSH-ÖN {ad}", beklenen, str(gercek)[:160], ok)
        self.assertTrue(ok, f"{ad}: {gercek}")

    def mcp(self, kod, govde):
        ist = object.__new__(SC.SAPClient)
        ist.adt_client = _SahteAdt(_SozSunucu(kod, govde))
        ist.debug_enabled = False
        ist.local_base = self.root
        ist._find_existing_transport = lambda name, otype, transport: transport
        self.atom._get_client = lambda: ist
        import time as _time
        eski_sleep = _time.sleep
        _time.sleep = lambda *_a, **_k: None
        try:
            r = self.atom.adt_push_source(name=AD, object_type="class", source=KAYNAK,
                                          transport=TRANSPORT, skip_reviewer=True)
        finally:
            _time.sleep = eski_sleep
        return r, ist.adt_client

    def test_K9_mcp_valid_none_ust_seviye_isaret(self):
        r, adt = self.mcp(200, GOVDE_GEN)
        ok = (r.get("ok") is True and adt.aktivasyon == 1 and r.get("syntax_precheck") == "olculemedi"
              and "OLCULEMEDI" in str(r.get("syntax_precheck_notice") or "")
              and (r.get("result") or {}).get("syntax_precheck") == "olculemedi")
        self.kaydet("K9 MCP valid None", "ok True + üst seviye olculemedi + notice",
                    (r.get("ok"), r.get("syntax_precheck"), bool(r.get("syntax_precheck_notice")), r.get("error")), ok)

    def test_K10_mcp_kontrol_e_mesaji(self):
        r, adt = self.mcp(200, GOVDE_E)
        ok = (r.get("ok") is False and r.get("syntax_precheck") == "failed" and bool(r.get("syntax_errors"))
              and "syntax_precheck_notice" not in r and adt.aktivasyon == 0)
        self.kaydet("K10 KONTROL MCP E mesajı", "ok False failed, notice yok",
                    (r.get("ok"), r.get("syntax_precheck"), r.get("error")), ok)

    def test_K11_mcp_kontrol_temiz(self):
        r, adt = self.mcp(200, GOVDE_TRUE)
        ok = r.get("ok") is True and "syntax_precheck" not in r and "syntax_precheck_notice" not in r
        self.kaydet("K11 KONTROL MCP temiz", "ok True, işaret yok",
                    (r.get("ok"), r.get("syntax_precheck", "YOK"), r.get("error")), ok)
