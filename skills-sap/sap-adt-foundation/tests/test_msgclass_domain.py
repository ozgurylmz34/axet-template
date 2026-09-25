# -*- coding: utf-8 -*-
"""Domain yaratma ön kontrolü + mesaj sınıfı yazma (aXet 2026-09-13) — süreç içi, SAHTE istemci (ağ yok).

Domain: `sap_adt_lib.SAPADTClient.create_domain`'in GERÇEK gövde kurucusu, ağ katmanı sahte bir alt sınıfla
çalıştırılır → POST gövdesindeki çıktı uzunluğu formülle kıyaslanır.
Mesaj sınıfı: sahte ADT oturumu HER HTTP çağrısını kaydeder; PUT gövdesi XML olarak ayrıştırılıp sahte canlı
listeyi günceller → birleştirme / üzerine yazma / silme / geri okuma iddiaları çağrı listesiyle kanıtlanır.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import _helpers as H

sys.dont_write_bytecode = True
if str(H.SCRIPTS) not in sys.path:
    sys.path.insert(0, str(H.SCRIPTS))

from test_new_write_tools import SAHTE_HOST, TR, SahteADT, Yanit  # noqa: E402

NS_DOMA = "http://www.sap.com/dictionary/domain"
NS_MC = "http://www.sap.com/adt/MessageClass"
NS_AC = "http://www.sap.com/adt/core"


class _Patla(AssertionError):
    pass


def _patla(*_a, **_k):
    raise _Patla("istemci/ağ çağrıldı — kontrol ağdan ÖNCE koşmadı")


# ── domain sahteleri ─────────────────────────────────────────────────────────────────────────────
def _domain_adt_sinifi():
    import sap_adt_lib  # type: ignore

    class DomainADT(sap_adt_lib.SAPADTClient):
        def __init__(self):  # noqa: D401 — ağ/bağlantı kurmaz
            self.url = f"http://{SAHTE_HOST}:8000"
            self.client = "100"
            self.language = "TR"
            self.csrf_token = "tok"
            self.timeout_default = 30
            self.debug_enabled = False
            self.cagri = []
            self.session = self
            self.post_yanitlari = []   # sırayla dönen (kod, gövde); boşsa 201

        def post(self, url, headers=None, data=None, params=None, timeout=None, **kw):
            govde = data.decode("utf-8") if isinstance(data, bytes) else data
            self.cagri.append({"method": "POST", "path": url[len(self.url):], "params": dict(params or {}),
                               "headers": dict(headers or {}), "data": govde})
            if self.post_yanitlari:
                oge = self.post_yanitlari.pop(0)
                if isinstance(oge, BaseException):   # POST gitti, yanıt yerine ağ istisnası (ör. bağlantı koptu)
                    raise oge
                kod, metin = oge
                return Yanit(kod, metin)
            return Yanit(201, "", {"Location": "/sap/bc/adt/ddic/domains/x"})

        def _get_headers(self, accept_type="application/vnd.sap.adt.core.v1+xml", content_type=None):
            return {"Accept": accept_type, "Content-Type": content_type}

        def _retry_request(self, request_func, operation="API request"):
            return request_func()

    return DomainADT


class DomainIstemci:
    def __init__(self, adt):
        self.adt_client = adt
        self.aktive_edildi = 0
        self.ddic_on_kontrol = "404"   # "404" → yok · "500" → ölçülemedi · "var" → XML döner
        self.ddic_cagri = 0

    def get_object_metadata(self, name, object_type=None):
        if not self.aktive_edildi:
            return None
        return '<doma:domain adtcore:version="active" adtcore:masterLanguage="TR"/>'

    def get_ddic_object(self, object_type, name):
        """`sap_client.get_ddic_object` taklidi: istisnayı yutar, sebebi stdout'a `[ERROR] [kod] …` basar."""
        self.ddic_cagri += 1
        if self.ddic_on_kontrol == "var":
            return '<doma:domain adtcore:name="%s" adtcore:version="active"/>' % name
        print("Fetching %s: %s" % (object_type, name))
        print("[ERROR] [%s] %s" % (self.ddic_on_kontrol, "Object not found" if self.ddic_on_kontrol == "404"
                                   else "Internal Server Error"))
        return None

    def create_domain(self, **kw):
        from sap_client import SAPClient  # type: ignore
        return SAPClient.create_domain(self, **kw)

    def create_dataelement(self, **kw):
        self.adt_client.cagri.append({"method": "LIB", "path": "create_dataelement", "params": {}, "data": None,
                                      "headers": {}})
        return True

    def activate_object(self, name, object_type=None):
        self.aktive_edildi += 1
        return True


# ── mesaj sınıfı sahteleri ───────────────────────────────────────────────────────────────────────
class MsagADT(SahteADT):
    def clear_enqueue_lock(self, *a, **k):   # ⛔ ÇAĞRILMAMALI — çağrılırsa kayda geçer, test kırılır
        self.cagri.append({"method": "LIB", "path": "clear_enqueue_lock", "params": {}, "data": None, "headers": {}})
        return True

    def lock_object(self, *a, **k):
        self.cagri.append({"method": "LIB", "path": "lock_object", "params": {}, "data": None, "headers": {}})
        return "X"

    def unlock_object(self, *a, **k):
        self.cagri.append({"method": "LIB", "path": "unlock_object", "params": {}, "data": None, "headers": {}})
        return True


def _msag_xml(durum) -> str:
    kok = ET.Element(f"{{{NS_MC}}}messageClass", {
        f"{{{NS_AC}}}name": "ZAXET_MSG", f"{{{NS_AC}}}masterLanguage": durum["ml"],
        f"{{{NS_AC}}}description": "Aksiyon mesajları", f"{{{NS_AC}}}responsible": H.KULLANICI})
    if durum.get("paket", True):
        ET.SubElement(kok, f"{{{NS_AC}}}packageRef", {f"{{{NS_AC}}}name": "ZAXET_PKG"})
    for no, metin, se, doc in durum["msgs"]:
        oz = {f"{{{NS_MC}}}msgno": no, f"{{{NS_MC}}}msgtext": metin,
              f"{{{NS_MC}}}selfexplainatory": "true" if se else "false",
              f"{{{NS_MC}}}documented": "true" if doc else "false"}
        if metin is None:   # canlı XML'de `mc:msgtext` özniteliği HİÇ yok (Z113 L1 vakası)
            del oz[f"{{{NS_MC}}}msgtext"]
        ET.SubElement(kok, f"{{{NS_MC}}}messages", oz)
    return ET.tostring(kok, encoding="unicode")


def _put_mesajlari(govde: str) -> list:
    kok = ET.fromstring(govde.encode("utf-8"))
    return [(e.get(f"{{{NS_MC}}}msgno"), e.get(f"{{{NS_MC}}}msgtext"), e.get(f"{{{NS_MC}}}selfexplainatory") == "true",
             e.get(f"{{{NS_MC}}}documented") == "true") for e in kok.findall(f"{{{NS_MC}}}messages")]


def _silinenler(govde: str) -> list:
    kok = ET.fromstring(govde.encode("utf-8"))
    return [e.get(f"{{{NS_MC}}}msgno") for e in kok.findall(f"{{{NS_MC}}}deletedmessages")]


def _sap_put_uygula(msgs, govde: str, kip: str = "sap") -> list:
    """SAP'nin ölçülmüş PUT davranışı (bkz. `_msag` docstring'i). Eski sahte tam listeyle DEĞİŞTİRİYORDU — kaynak çekirdek
    canlıda çürüttü (tam PUT'tan çıkarmak no-op); o sahte, silmeyi hiç yapmayan aracı yeşil gösteriyordu."""
    mevcut = {m[0]: m for m in msgs}
    for m in _put_mesajlari(govde):
        if m[0] not in mevcut or mevcut[m[0]][1] != m[1]:
            mevcut[m[0]] = m
    if kip != "noop_sil":
        for no in _silinenler(govde):
            mevcut.pop(no or "000", None)
    if kip == "fazla":
        mevcut.pop(sorted(mevcut)[0], None)
    if kip == "degistir":
        ilk = sorted(mevcut)[0]
        eski = mevcut[ilk]
        mevcut[ilk] = (eski[0], eski[1] + " (değişti)", eski[2], eski[3])
    if kip == "doc":   # yalnız `documented` bayrağı değişir — genel readback kıyası (no,text,self) bunu GÖRMEZ, kapı görür
        ilk = sorted(mevcut)[0]
        eski = mevcut[ilk]
        mevcut[ilk] = (eski[0], eski[1], eski[2], not eski[3])
    return [mevcut[k] for k in sorted(mevcut)]


class DomainVeMesajSinifi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="axet_msag_doma_"))
        cls._eski_env = {k: os.environ.get(k) for k in ("AXET_SAP_PROJECT_DIR", "ADT_SAP_TIER")}
        os.environ.pop("ADT_SAP_TIER", None)
        from sapadt.tools import atom, composite, msgclass
        from sapadt import pull_state, gate
        cls.atom, cls.comp, cls.mc, cls.ps, cls.gate = atom, composite, msgclass, pull_state, gate
        cls._eski_client = atom._get_client
        cls._sayac = 0

    @classmethod
    def tearDownClass(cls):
        cls.atom._get_client = cls._eski_client
        for k, v in cls._eski_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(cls.root, ignore_errors=True)

    def setUp(self):
        type(self)._sayac += 1
        self.p = H.make_project(self.root, f"p{self._sayac}")
        os.environ["AXET_SAP_PROJECT_DIR"] = str(self.p)

    def kaydet(self, ad, beklenen, gercek, ok):
        H.kaydet(f"MSAG/DOMA {ad}", beklenen, str(gercek)[:160], ok)
        self.assertTrue(ok, f"{ad}: {gercek}")

    # ═════════════════════════════ DOMAIN ═════════════════════════════════════════════════════════
    def _domain(self, datatype, length, decimals=0, **kw):
        adt = _domain_adt_sinifi()()
        ist = DomainIstemci(adt)
        self.atom._get_client = lambda: ist
        r = self.comp.adt_domain_create("ZAXET_D_X", datatype, length, kw.pop("description", "Test alanı"),
                                        "ZAXET_PKG", TR, decimals=decimals, **kw)
        return r, adt

    def test_D1_cikti_uzunlugu_formulu_her_tip_ailesi(self):
        vakalar = [("CHAR", 10, 0, 10), ("NUMC", 8, 0, 8), ("DATS", 8, 0, 8), ("TIMS", 6, 0, 6), ("CLNT", 3, 0, 3),
                   ("INT1", 3, 0, 4), ("INT2", 5, 0, 6), ("INT4", 10, 0, 11), ("INT8", 19, 0, 20),
                   ("DEC", 13, 2, 17), ("QUAN", 15, 3, 19), ("CURR", 13, 2, 17)]
        for dt, ln, dec, beklenen in vakalar:
            r, adt = self._domain(dt, ln, dec)
            post = [c for c in adt.cagri if c["method"] == "POST"]
            kok = ET.fromstring(post[0]["data"].encode("utf-8")) if post else None
            cikti = kok.find(f"{{{NS_DOMA}}}content/{{{NS_DOMA}}}outputInformation/{{{NS_DOMA}}}length").text if post else None
            girdi = kok.find(f"{{{NS_DOMA}}}content/{{{NS_DOMA}}}typeInformation/{{{NS_DOMA}}}length").text if post else None
            ok = (r.get("ok") is True and len(post) == 1 and post[0]["path"] == "/sap/bc/adt/ddic/domains"
                  and cikti == f"{beklenen:06d}" and girdi == f"{ln:06d}"
                  and r["steps"]["pre_flight"]["verdict"] == "PASS"
                  and r["steps"]["pre_flight"]["output_length"] == beklenen and r.get("output_length") == beklenen)
            self.kaydet(f"D1 {dt}({ln},{dec}) POST outputLength", f"{beklenen:06d}",
                        f"ok={r.get('ok')} err={r.get('error')} out={cikti} in={girdi}", ok)

    def test_D2_on_kontrol_blocker_ag_yok(self):
        self.atom._get_client = _patla
        c = self.comp.adt_domain_create
        vakalar = [
            ("FLTP formülsüz tip", c("ZAXET_D_X", "FLTP", 16, "Test", "ZAXET_PKG", TR), "R1_datatype"),
            ("uydurma tip", c("ZAXET_D_X", "CHARX", 10, "Test", "ZAXET_PKG", TR), "R1_datatype"),
            ("length 0", c("ZAXET_D_X", "CHAR", 0, "Test", "ZAXET_PKG", TR), "R2_length"),
            ("length true", c("ZAXET_D_X", "CHAR", True, "Test", "ZAXET_PKG", TR), "R2_length"),
            ("length metin", c("ZAXET_D_X", "QUAN", "15", "Test", "ZAXET_PKG", TR, decimals=3), "R2_length"),
            ("decimals -1", c("ZAXET_D_X", "DEC", 13, "Test", "ZAXET_PKG", TR, decimals=-1), "R3_decimals"),
            ("lowercase 'false' dizesi", c("ZAXET_D_X", "CHAR", 10, "Test", "ZAXET_PKG", TR, lowercase="false"),
             "R4_lowercase"),
            ("sabit değer metni yok", c("ZAXET_D_X", "CHAR", 1, "Test", "ZAXET_PKG", TR,
                                        fixed_values=[{"value": "A"}]), "ADR_0005_D"),
            ("sabit değer metni boşluk", c("ZAXET_D_X", "CHAR", 1, "Test", "ZAXET_PKG", TR,
                                           fixed_values=[{"value": "A", "text": "  "}]), "ADR_0005_D"),
            ("sabit değer değeri boş", c("ZAXET_D_X", "CHAR", 1, "Test", "ZAXET_PKG", TR,
                                         fixed_values=[{"value": "", "text": "Boş"}]), "R5_fixed_values"),
            ("sabit değer tanınmayan alan", c("ZAXET_D_X", "CHAR", 1, "Test", "ZAXET_PKG", TR,
                                              fixed_values=[{"value": "A", "text": "A", "renk": "k"}]), "R5_fixed_values"),
        ]
        for ad, r, kural in vakalar:
            kurallar = [f["rule"] for f in ((r.get("steps") or {}).get("pre_flight") or {}).get("findings", [])]
            self.kaydet(f"D2 ön kontrol: {ad}", f"preflight_blocker · {kural}", f"{r.get('error')} · {kurallar}",
                        r.get("error") == "preflight_blocker" and kural in kurallar)
        g = self.gate.review_summary("adt_domain_create", {}, vakalar[0][1])
        self.kaydet("D2 gate.review ön kontrol BLOCKER metni", "NOT_RUN: argüman ön kontrolü", g,
                    str(g).startswith("NOT_RUN: argüman ön kontrolü BLOCKER"))
        self.kaydet("D2 CLI çıkış eşlemesi preflight_blocker → 2", "exit 2", "",
                    __import__("sap_adt_cli")._sonuc_hatasi(vakalar[0][1])[0] == 2)

    def test_D3_artefaktli_zincir_domain_creation_csv(self):
        from sapadt._reviewer import COMPOSITE_TOOL_TO_TASK, task_for_composite
        self.kaydet("D3 eşleme adt_domain_create → domain_creation_csv", "domain_creation_csv",
                    task_for_composite("adt_domain_create"), task_for_composite("adt_domain_create") == "domain_creation_csv")
        import importlib.util
        spec = importlib.util.spec_from_file_location("_rr_doma", str(H.SCRIPTS / "sapadt" / "lib" / "validators" / "run_review.py"))
        rr = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rr)
        bayat = sorted(f"{a}:{t}" for a, t in COMPOSITE_TOOL_TO_TASK.items()
                       if t is not None and not rr.TASK_VALIDATORS.get(t))
        self.kaydet("D3 composite eşlemelerinin görevi var ve zinciri boş değil", "0 bayat", bayat, not bayat)
        kirli = self.p / "domains_kirli.csv"
        kirli.write_text("name,datatype,length,decimals,description,fixed_values\nZAXET_D_X,FOO,10,0,Test,\n",
                         encoding="utf-8")
        self.atom._get_client = _patla
        r = self.comp.adt_domain_create("ZAXET_D_X", "CHAR", 10, "Test", "ZAXET_PKG", TR, artifact_path=str(kirli))
        rv = r.get("reviewer") or {}
        self.kaydet("D3 kirli CSV → reviewer_blocker, ağ yok", "reviewer_blocker",
                    f"{r.get('error')} verdict={rv.get('verdict')}",
                    r.get("error") == "reviewer_blocker" and rv.get("verdict") == "BLOCKER"
                    and "pre_flight" in (r.get("steps") or {}))
        temiz = self.p / "domains_temiz.csv"
        temiz.write_text("name,datatype,length,decimals,description,fixed_values\nZAXET_D_X,QUAN,15,3,Test,\n",
                         encoding="utf-8")
        r, adt = self._domain("QUAN", 15, 3, artifact_path=str(temiz))
        self.kaydet("D3 temiz CSV → PASS + yaratma", "ok · PASS", f"ok={r.get('ok')} verdict={(r.get('reviewer') or {}).get('verdict')}",
                    r.get("ok") is True and (r.get("reviewer") or {}).get("verdict") == "PASS"
                    and len([c for c in adt.cagri if c["method"] == "POST"]) == 1)
        yanlis = self.p / "domain.txt"
        yanlis.write_text("x", encoding="utf-8")
        self.atom._get_client = _patla
        r = self.comp.adt_domain_create("ZAXET_D_X", "CHAR", 10, "Test", "ZAXET_PKG", TR, artifact_path=str(yanlis))
        self.kaydet("D3 desteklenmeyen artefakt uzantısı → ölçülemedi = BLOCKER (fail-closed)", "reviewer_blocker",
                    r.get("error"), r.get("error") == "reviewer_blocker")

    def test_D4_artefaktsiz_skip_gorunur(self):
        r, _adt = self._domain("CHAR", 10)
        rv = r.get("reviewer") or {}
        g = self.gate.review_summary("adt_domain_create", {}, r)
        self.kaydet("D4 artefakt yok → reviewer SKIP görünür (üst düzey + steps) · gate.review", "SKIP (no_artifact…)",
                    f"{rv.get('verdict')} {rv.get('skip_reason')} · {g}",
                    rv.get("verdict") == "SKIP" and rv.get("skip_reason") == "no_artifact_path_provided"
                    and "KOŞMADI" in rv.get("notice", "") and r["steps"].get("reviewer") == rv
                    and g == "SKIP (no_artifact_path_provided)")
        self.atom._get_client = lambda: (_ for _ in ()).throw(ConnectionError("bağlantı yok"))
        r = self.comp.adt_domain_create("ZAXET_D_X", "CHAR", 10, "Test", "ZAXET_PKG", TR)
        self.kaydet("D4 istemci kurulamadı → ok:false ama pre_flight + reviewer yanıtta", "ok:false · izler var",
                    f"ok={r.get('ok')} keys={sorted(r)}", r.get("ok") is False and "reviewer" in r
                    and "pre_flight" in (r.get("steps") or {}))

    def test_D5_gövde_xml_kacisli_ve_formul_tek_kaynak(self):
        r, adt = self._domain("CHAR", 1, description='Tür & "tırnak" <x>',
                              fixed_values=[{"value": "A&", "text": '<Açık> & "kapalı"'}])
        post = [c for c in adt.cagri if c["method"] == "POST"][0]
        kok = ET.fromstring(post["data"].encode("utf-8"))
        fv = kok.find(f"{{{NS_DOMA}}}content/{{{NS_DOMA}}}valueInformation/{{{NS_DOMA}}}fixValues/{{{NS_DOMA}}}fixValue")
        ok = (r.get("ok") is True and kok.get(f"{{{NS_AC}}}description") == 'Tür & "tırnak" <x>'
              and fv.find(f"{{{NS_DOMA}}}low").text == "A&" and fv.find(f"{{{NS_DOMA}}}text").text == '<Açık> & "kapalı"')
        self.kaydet("D5 açıklama + sabit değer XML kaçışlı, gövde ayrıştırılabilir", "ok", f"ok={r.get('ok')}", ok)
        import importlib.util
        from utils import ddic_domain  # type: ignore
        spec = importlib.util.spec_from_file_location(
            "_cdol", str(H.SCRIPTS / "sapadt" / "lib" / "validators" / "check_domain_output_length.py"))
        v = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(v)
        self.kaydet("D5 validator formülü = utils.ddic_domain (tek kaynak)", "aynı fonksiyon",
                    v.expected_output_length.__module__, v.expected_output_length is ddic_domain.expected_output_length)

    # ── Z51 ⓐ / Z52 (v0.5.1): domain/DTEL ön kontrolü üç değerli; AlreadyExists aktivasyon DEĞİL ──────────────
    VAR_GOVDE = "<exc:exception><type id=\"ExceptionResourceAlreadyExists\"/><localizedMessage>AlreadyExists" \
                "</localizedMessage></exc:exception>"

    def _domain_kur(self, on_kontrol="404", post=None, gercek_retry=False):
        import sap_adt_lib  # type: ignore
        adt = _domain_adt_sinifi()()
        adt.post_yanitlari = list(post or [])
        if gercek_retry:
            k = sap_adt_lib.SAPADTClient
            adt.max_retries, adt.retry_delay = 3, 0.0
            adt.retry_on_timeout = adt.retry_on_csrf_fail = adt.retry_on_5xx = True
            adt._retry_request = k._retry_request.__get__(adt)
        ist = DomainIstemci(adt)
        ist.ddic_on_kontrol = on_kontrol
        self.atom._get_client = lambda: ist
        return adt, ist

    def test_D6_domain_on_kontrol_uc_degerli(self):
        sonuc = {}
        for durum in ("500", "var", "404"):
            adt, ist = self._domain_kur(on_kontrol=durum)
            r = self.comp.adt_domain_create("ZAXET_D_X", "CHAR", 10, "Test alanı", "ZAXET_PKG", TR)
            sonuc[durum] = (r.get("ok"), r.get("error"), len([c for c in adt.cagri if c["method"] == "POST"]),
                            ist.aktive_edildi, str(r.get("steps", {}).get("pre_check")))
        ok = (sonuc["500"][:4] == (False, "exists_unmeasured", 0, 0) and sonuc["500"][4].startswith("unavailable")
              and sonuc["var"][:4] == (False, "already_exists", 0, 0)
              and sonuc["404"][:4] == (True, None, 1, 1) and sonuc["404"][4] == "checked_absent")
        self.kaydet("D6 domain ön kontrol: 500 → exists_unmeasured (POST 0) · var → already_exists · 404 → yarat",
                    "unmeasured · exists · ok", str(sonuc), ok)

    def test_D7_domain_post_zaten_var_aktivasyon_yok(self):
        adt, ist = self._domain_kur(post=[(405, self.VAR_GOVDE)])
        r = self.comp.adt_domain_create("ZAXET_D_X", "CHAR", 10, "Test alanı", "ZAXET_PKG", TR)
        adt2, ist2 = self._domain_kur(post=[(500, "Internal Server Error"), (405, self.VAR_GOVDE)], gercek_retry=True)
        r2 = self.comp.adt_domain_create("ZAXET_D_X", "CHAR", 10, "Test alanı", "ZAXET_PKG", TR)
        post2 = [c for c in adt2.cagri if c["method"] == "POST"]
        ok = (r.get("ok") is False and r.get("error") == "already_exists" and ist.aktive_edildi == 0
              and r2.get("ok") is False and r2.get("error") == "already_exists_after_retry" and ist2.aktive_edildi == 0
              and len(post2) == 2 and "adt_get" in str(r2.get("message")))
        self.kaydet("D7 domain: POST 405 AlreadyExists → already_exists, aktivasyon YOK · 500→retry→405 → after_retry",
                    "already_exists · after_retry · aktivasyon 0",
                    f"{r.get('error')} akt={ist.aktive_edildi} · {r2.get('error')} akt={ist2.aktive_edildi} "
                    f"post={len(post2)}", ok)

    def test_D9_baglanti_hatasi_retry_sonrasi_zaten_var(self):
        """Bug gate MEDIUM (v0.5.1): POST gitti, SAP işledi, yanıt gelmeden bağlantı koptu (ConnectionError) → kütüphane
        yeniden dener → 405 AlreadyExists. Beklenen: `already_exists_after_retry` (5xx/zaman aşımı ile aynı sınıf) — log
        'ÖNCEKİ DENEME' derken kodun düz `already_exists` demesi çelişkiydi.
        Kontrol grupları: retry'sız 405 → düz `already_exists` · yalnız CSRF yeniden denemesi (istek işlenmedi) → düz
        `already_exists`."""
        import requests  # type: ignore
        sonuc = {}
        adt, ist = self._domain_kur(post=[requests.exceptions.ConnectionError("RemoteDisconnected: bağlantı koptu"),
                                          (405, self.VAR_GOVDE)], gercek_retry=True)
        r = self.comp.adt_domain_create("ZAXET_D_X", "CHAR", 10, "Test alanı", "ZAXET_PKG", TR)
        sonuc["baglanti"] = (r.get("error"), r.get("own_shell_possible"), ist.aktive_edildi,
                             len([c for c in adt.cagri if c["method"] == "POST"]))
        adt, ist = self._domain_kur(post=[(405, self.VAR_GOVDE)], gercek_retry=True)
        r = self.comp.adt_domain_create("ZAXET_D_X", "CHAR", 10, "Test alanı", "ZAXET_PKG", TR)
        sonuc["retrysiz"] = (r.get("error"), r.get("own_shell_possible"), ist.aktive_edildi,
                             len([c for c in adt.cagri if c["method"] == "POST"]))
        adt, ist = self._domain_kur(post=[(403, "CSRF token validation failed"), (405, self.VAR_GOVDE)],
                                    gercek_retry=True)
        adt.fetch_csrf_token = lambda force_refresh=False: "tok2"
        r = self.comp.adt_domain_create("ZAXET_D_X", "CHAR", 10, "Test alanı", "ZAXET_PKG", TR)
        sonuc["csrf"] = (r.get("error"), r.get("own_shell_possible"), ist.aktive_edildi,
                         len([c for c in adt.cagri if c["method"] == "POST"]))
        ok = sonuc == {"baglanti": ("already_exists_after_retry", True, 0, 2),
                       "retrysiz": ("already_exists", None, 0, 1),
                       "csrf": ("already_exists", None, 0, 2)}
        self.kaydet("D9 domain: bağlantı hatası → retry → 405 → after_retry · retry'sız / yalnız CSRF → already_exists",
                    "after_retry · already_exists · already_exists", str(sonuc), ok)

    def test_D8_dtel_on_kontrol_uc_degerli(self):
        sonuc = {}
        for durum in ("500", "var", "404"):
            adt, ist = self._domain_kur(on_kontrol=durum)
            r = self.comp.adt_dtel_create("ZAXET_E_X", "ZAXET_D_X", "Test alanı", "ZAXET_PKG", TR,
                                          "Kısa", "Orta etiket", "Uzun etiket", "Başlık")
            sonuc[durum] = (r.get("error"), [c["path"] for c in adt.cagri].count("create_dataelement"))
        ok = sonuc == {"500": ("exists_unmeasured", 0), "var": ("already_exists", 0), "404": (None, 1)}
        self.kaydet("D8 DTEL ön kontrol: 500 → exists_unmeasured (create 0) · var → already_exists · 404 → yarat",
                    "unmeasured · exists · create 1", str(sonuc), ok)

    # ═════════════════════════════ MESAJ SINIFI ═══════════════════════════════════════════════════
    def _msag(self, msgs, *, ml="TR", put_gunceller=True, lock=None, get_durum=200, paket=True, put_durum=200,
              put_kip="sap", on_lock=None, put_istisna=False):
        """Sahte MSAG ucu. PUT semantiği SAP'nin ÖLÇÜLMÜŞ davranışıdır (kaynak çekirdek `playbook/adt-message-class.md`
        §27.5, s4_private 2025: 229→229 no-op / 229→228 deletedmessages): gövdedeki mesaj eklenir, METNİ farklıysa
        güncellenir; gövdede OLMAYAN mesaja DOKUNULMAZ; yalnız `<mc:deletedmessages>` siler (boş msgno → 000).
        `put_kip`: "sap" · "noop_sil" (deletedmessages yok sayılır) · "fazla" (istenmeyen bir mesaj da gider) ·
        "degistir" (kalan bir mesajın metni değişir). `durum["get_plan"]`: sıradaki GET'lerin durum kodları
        (200/500 ya da istisna nesnesi; tükenince `durum["get"]`). `on_lock(durum)`: LOCK anında canlıyı değiştirir
        (TOCTOU). `put_istisna`: PUT işlenir ama yanıt yerine ağ istisnası."""
        durum = {"msgs": list(msgs), "ml": ml, "paket": paket, "get": get_durum, "get_plan": []}

        def yon(c):
            if c["method"] == "GET" and c["path"] == "/sap/bc/adt/messageclass/zaxet_msg":
                kod = durum["get_plan"].pop(0) if durum["get_plan"] else durum["get"]
                if isinstance(kod, BaseException):
                    return kod
                return Yanit(kod, _msag_xml(durum) if kod == 200 else "hata")
            if c["method"] == "POST" and c["params"].get("_action") == "LOCK":
                if on_lock:
                    on_lock(durum)
                return lock(c) if lock else Yanit(200, "<asx:abap><DATA><LOCK_HANDLE>HX9</LOCK_HANDLE></DATA></asx:abap>")
            if c["method"] == "PUT":
                if put_gunceller and put_durum == 200:
                    durum["msgs"] = _sap_put_uygula(durum["msgs"], c["data"], put_kip)
                if put_istisna:
                    return ConnectionError("Read timed out (PUT)")
                return Yanit(put_durum, "")
            if c["method"] == "POST" and c["params"].get("_action") == "UNLOCK":
                return Yanit(200, "")
            return Yanit(500, "beklenmedik")
        adt = MsagADT(yon)

        class Ist:
            adt_client = adt
        self.atom._get_client = lambda: Ist()
        return adt, durum

    @staticmethod
    def _yollar(adt):
        return [(c["method"], c["params"].get("_action") or c["path"]) for c in adt.cagri]

    def _yaz(self, **kw):
        return self.mc.adt_msgclass_write("ZAXET_MSG", kw.pop("transport", TR), **kw)

    def test_M1_birlestirme_mevcutlar_korunur(self):
        adt, durum = self._msag([("001", "Müşteri bulunamadı", False, False), ("002", "Tarih boş", True, True)])
        g = self.atom.adt_msgclass_read("ZAXET_MSG")
        self.assertEqual(g.get("pull_state"), "kaydedildi")
        self.assertNotIn("_responsible", g)
        adt.cagri.clear()
        r = self._yaz(messages=[{"no": "003", "text": "Yeni & <özel> \"mesaj\""}])
        put = [c for c in adt.cagri if c["method"] == "PUT"]
        lock = [c for c in adt.cagri if c["params"].get("_action") == "LOCK"]
        unlock = [c for c in adt.cagri if c["params"].get("_action") == "UNLOCK"]
        gonderilen = _put_mesajlari(put[0]["data"]) if put else []
        kok = ET.fromstring(put[0]["data"].encode("utf-8")) if put else None
        ok = (r.get("ok") is True and r.get("readback_verified") is True and r.get("changed") is True
              and gonderilen == [("001", "Müşteri bulunamadı", False, False), ("002", "Tarih boş", True, True),
                                 ("003", 'Yeni & <özel> "mesaj"', False, False)]
              and [a["no"] for a in r["plan"]["added"]] == ["003"] and r["plan"]["preserved_count"] == 2
              and not r["plan"]["overwritten"] and not r["plan"]["deleted"]
              and lock[0]["params"] == {"_action": "LOCK", "accessMode": "MODIFY", "corrNr": TR}
              and lock[0]["headers"].get("Accept") == "application/*,application/vnd.sap.as+xml;dataname=com.sap.adt.lock.result"
              and put[0]["path"] == "/sap/bc/adt/messageclass/zaxet_msg"
              and put[0]["params"] == {"corrNr": TR, "lockHandle": "HX9", "accessMode": "MODIFY"}
              and put[0]["headers"].get("Content-Type") == "application/vnd.sap.adt.mc.messageclass+xml; charset=utf-8"
              and put[0]["headers"].get("sap-language") == "TR"
              and not any(k.lower() == "if-match" for k in put[0]["headers"])
              and unlock and unlock[0]["params"] == {"_action": "UNLOCK", "lockHandle": "HX9"}
              and [m for m, _ in self._yollar(adt)] == ["GET", "POST", "PUT", "POST", "GET"]
              and kok.get(f"{{{NS_AC}}}masterLanguage") == "TR" and kok.get(f"{{{NS_AC}}}type") == "MSAG/N"
              and kok.find(f"{{{NS_AC}}}packageRef").get(f"{{{NS_AC}}}name") == "ZAXET_PKG"
              and r.get("pull_state") == "guncellendi"
              and not any(c["path"] in ("clear_enqueue_lock", "lock_object", "unlock_object") for c in adt.cagri))
        self.kaydet("M1 birleştirme: 003 eklendi, 001/002 korundu (documented dahil) · LOCK→PUT(If-Match yok)→UNLOCK→readback",
                    "ok · 3 mesaj · sıra", f"ok={r.get('ok')} err={r.get('error')} put={gonderilen} sıra={self._yollar(adt)}", ok)

    def test_M2_uzerine_yazma_yalniz_bayrakla(self):
        adt, durum = self._msag([("001", "Eski metin", False, False), ("002", "Kalır", False, False)])
        self.atom.adt_msgclass_read("ZAXET_MSG")
        adt.cagri.clear()
        r = self._yaz(messages=[{"no": "001", "text": "Yeni metin"}])
        self.kaydet("M2 mevcut metin değişirdi, bayrak yok → msgclass_overwrite_not_allowed, kilit/PUT YOK",
                    "msgclass_overwrite_not_allowed", f"{r.get('error')} sıra={self._yollar(adt)}",
                    r.get("error") == "msgclass_overwrite_not_allowed" and r["plan"]["overwritten"][0]["no"] == "001"
                    and not any(c["method"] in ("PUT",) or c["params"].get("_action") for c in adt.cagri))
        self.kaydet("M2 CLI çıkış eşlemesi → 2", "exit 2", "",
                    __import__("sap_adt_cli")._sonuc_hatasi(r)[0] == 2)
        adt.cagri.clear()
        r = self._yaz(messages=[{"no": "001", "text": "Yeni metin"}, {"no": "002", "text": "Kalır"}], allow_overwrite=True)
        put = [c for c in adt.cagri if c["method"] == "PUT"]
        ok = (r.get("ok") is True and r["plan"]["overwritten"] == [
            {"no": "001", "before": {"text": "Eski metin", "selfexplanatory": False},
             "after": {"text": "Yeni metin", "selfexplanatory": False}}]
              and r["plan"]["unchanged"] == ["002"]
              and _put_mesajlari(put[0]["data"]) == [("001", "Yeni metin", False, False), ("002", "Kalır", False, False)])
        self.kaydet("M2 allow_overwrite=true → önce/sonra listelenir, yazılır", "ok · overwritten 001",
                    f"ok={r.get('ok')} plan={r.get('plan')}", ok)

    def test_M3_silme_yalniz_listeyle(self):
        adt, durum = self._msag([("001", "Bir", False, False), ("002", "İki", False, False), ("003", "Üç", False, False)])
        self.atom.adt_msgclass_read("ZAXET_MSG")
        adt.cagri.clear()
        r = self._yaz(delete_numbers=["002"])
        put = [c for c in adt.cagri if c["method"] == "PUT"]
        self.kaydet("M3 delete_numbers=[002] → yalnız 002 gider, silinen listelenir", "ok · 001,003",
                    f"ok={r.get('ok')} put={_put_mesajlari(put[0]['data']) if put else None}",
                    r.get("ok") is True and r["plan"]["deleted"] == [{"no": "002", "text": "İki"}]
                    and [m[0] for m in _put_mesajlari(put[0]["data"])] == ["001", "003"])
        adt.cagri.clear()
        r = self._yaz(delete_numbers=["009"])
        self.kaydet("M3 canlıda olmayan numarayı silme → invalid_argument, kilit/PUT yok", "invalid_argument",
                    f"{r.get('error')} sıra={self._yollar(adt)}",
                    r.get("error") == "invalid_argument" and not any(c["params"].get("_action") or c["method"] == "PUT"
                                                                     for c in adt.cagri))
        adt.cagri.clear()
        r = self._yaz(messages=[{"no": "001", "text": "Bir"}])
        self.kaydet("M3 değişiklik yok → ok, changed:false, kilit alınmaz", "ok · changed False",
                    f"ok={r.get('ok')} changed={r.get('changed')} sıra={self._yollar(adt)}",
                    r.get("ok") is True and r.get("changed") is False
                    and not any(c["params"].get("_action") or c["method"] == "PUT" for c in adt.cagri))

    def test_M4_okuma_basarisiz_yazma_yok(self):
        adt, durum = self._msag([("001", "Bir", False, False)])
        self.atom.adt_msgclass_read("ZAXET_MSG")
        durum["get"] = 500
        adt.cagri.clear()
        r = self._yaz(messages=[{"no": "002", "text": "İki"}])
        self.kaydet("M4 yazma öncesi canlı okuma 500 → pull_live_read_failed, kilit/PUT YOK", "pull_live_read_failed",
                    f"{r.get('error')} sıra={self._yollar(adt)}",
                    r.get("error") == "pull_live_read_failed"
                    and self._yollar(adt) == [("GET", "/sap/bc/adt/messageclass/zaxet_msg")])

    def test_M5_kilit_cakismasi_silme_cagrisi_yok(self):
        adt, durum = self._msag([("001", "Bir", False, False)],
                                lock=lambda c: Yanit(403, "<exc>EU 510: ZAXET_MSG is locked by AXETTEST</exc>"))
        self.atom.adt_msgclass_read("ZAXET_MSG")
        adt.cagri.clear()
        r = self._yaz(messages=[{"no": "002", "text": "İki"}])
        ok = (r.get("ok") is False and r.get("error") == "lock_conflict" and "SM12" in r.get("message", "")
              and "SİLMEZ" in r.get("message", "")
              and not any(c["method"] == "PUT" for c in adt.cagri)
              and not any(c["params"].get("_action") == "UNLOCK" for c in adt.cagri)
              and not any(c["path"] in ("clear_enqueue_lock", "lock_object", "unlock_object") for c in adt.cagri)
              and self.ps.kayit_al("ZAXET_MSG", "msag")[0] is not None)
        self.kaydet("M5 kilit çakışması → lock_conflict + SM12 mesajı · PUT/UNLOCK/clear_enqueue_lock YOK", "lock_conflict",
                    f"{r.get('error')} sıra={self._yollar(adt)}", ok)
        self.kaydet("M5 CLI çıkış eşlemesi → 1", "exit 1", "", __import__("sap_adt_cli")._sonuc_hatasi(r)[0] == 1)
        adt, durum = self._msag([("001", "Bir", False, False)], lock=lambda c: Yanit(500, "dump"))
        self.atom.adt_msgclass_read("ZAXET_MSG")
        r = self._yaz(messages=[{"no": "002", "text": "İki"}])
        self.kaydet("M5 kilit başka sebeple alınamadı → lock_failed (silme çağrısı yok)", "lock_failed", r.get("error"),
                    r.get("error") == "lock_failed" and not any(c["path"] == "clear_enqueue_lock" for c in adt.cagri))

    def test_M6_geri_okuma_farki_ok_false(self):
        adt, durum = self._msag([("001", "Bir", False, False)], put_gunceller=False)
        self.atom.adt_msgclass_read("ZAXET_MSG")
        r = self._yaz(messages=[{"no": "002", "text": "İki"}])
        ok = (r.get("ok") is False and r.get("error") == "readback_mismatch" and r.get("readback_verified") is False
              and ["002", "İki", False] in r["readback_diff"]["missing"]
              and any(c["params"].get("_action") == "UNLOCK" for c in adt.cagri)
              and self.ps.kayit_al("ZAXET_MSG", "msag")[0] is None)
        self.kaydet("M6 PUT 200 ama canlı liste değişmedi → readback_mismatch ok:false, kayıt silindi", "readback_mismatch",
                    f"{r.get('error')} diff={r.get('readback_diff')}", ok)
        adt, durum = self._msag([("001", "Bir", False, False)], put_durum=400)
        self.atom.adt_msgclass_read("ZAXET_MSG")
        r = self._yaz(messages=[{"no": "002", "text": "İki"}])
        self.kaydet("M6 PUT 400 → push_failed + kendi kilidi bırakıldı", "push_failed · UNLOCK",
                    f"{r.get('error')} sıra={self._yollar(adt)}",
                    r.get("error") == "push_failed" and any(c["params"].get("_action") == "UNLOCK" for c in adt.cagri))

    def test_M7_ag_oncesi_redler(self):
        adt, _ = self._msag([])
        adt.yonlendir = lambda c: AssertionError("ağ")
        uzun = "x" * 74
        vakalar = [
            ("standart sınıf", self.mc.adt_msgclass_write("VL", TR, messages=[{"no": "001", "text": "a"}]), "ADR_0005_A"),
            ("transport yok", self._yaz(transport="", messages=[{"no": "001", "text": "a"}]), "ADR_0005_C"),
            ("metin boş", self._yaz(messages=[{"no": "001", "text": "  "}]), "ADR_0005_D"),
            ("metin 74 karakter", self._yaz(messages=[{"no": "001", "text": uzun}]), "invalid_argument"),
            ("numara '1'", self._yaz(messages=[{"no": "1", "text": "a"}]), "invalid_argument"),
            ("numara int", self._yaz(messages=[{"no": 1, "text": "a"}]), "invalid_argument"),
            ("aynı numara iki kez", self._yaz(messages=[{"no": "001", "text": "a"}, {"no": "001", "text": "b"}]),
             "invalid_argument"),
            ("yaz + sil çakışır", self._yaz(messages=[{"no": "001", "text": "a"}], delete_numbers=["001"]),
             "invalid_argument"),
            ("hiçbir şey istenmedi", self._yaz(), "invalid_argument"),
            ("documented alanı", self._yaz(messages=[{"no": "001", "text": "a", "documented": True}]), "invalid_argument"),
            ("selfexplanatory dize", self._yaz(messages=[{"no": "001", "text": "a", "selfexplanatory": "true"}]),
             "invalid_argument"),
            ("allow_overwrite dize", self._yaz(messages=[{"no": "001", "text": "a"}], allow_overwrite="true"),
             "invalid_argument"),
            ("pull kaydı yok", self._yaz(messages=[{"no": "001", "text": "a"}]), "pull_before_edit_missing"),
        ]
        for ad, r, kod in vakalar:
            gercek = r.get("code") if r.get("error") == "guardrail_violation" else r.get("error")
            self.kaydet(f"M7 ağ öncesi red: {ad}", kod, gercek, gercek == kod)
        self.assertEqual(adt.cagri, [])
        qa = H.make_project(self.root, f"qa{self._sayac}", tier_lines=("ADT_SAP_TIER=QA",))
        os.environ["AXET_SAP_PROJECT_DIR"] = str(qa)
        r = self._yaz(messages=[{"no": "001", "text": "a"}])
        self.kaydet("M7 QA tier → ADR_0010_TIER", "ADR_0010_TIER", r.get("code"), r.get("code") == "ADR_0010_TIER")
        dilsiz = H.make_project(self.root, f"dilsiz{self._sayac}",
                                sap_project={"sap_profile": "s4_private", "release": "2025"})
        os.environ["AXET_SAP_PROJECT_DIR"] = str(dilsiz)
        r = self._yaz(messages=[{"no": "001", "text": "a"}])
        self.kaydet("M7 master_language çözülemedi → master_language_unresolved, ağ yok", "master_language_unresolved",
                    r.get("error"), r.get("error") == "master_language_unresolved" and adt.cagri == [])

    def test_M8_dil_ve_pull_degisti(self):
        adt, durum = self._msag([("001", "Bir", False, False)], ml="EN")
        self.atom.adt_msgclass_read("ZAXET_MSG")
        adt.cagri.clear()
        r = self._yaz(messages=[{"no": "002", "text": "İki"}])
        self.kaydet("M8 sınıfın master dili EN ≠ TR → ADR_0005_D, kilit yok", "ADR_0005_D",
                    f"{r.get('code')} sıra={self._yollar(adt)}",
                    r.get("code") == "ADR_0005_D" and not any(c["params"].get("_action") for c in adt.cagri))
        adt, durum = self._msag([("001", "Bir", False, False)])
        self.atom.adt_msgclass_read("ZAXET_MSG")
        durum["msgs"].append(("002", "Başkası ekledi", False, False))
        adt.cagri.clear()
        r = self._yaz(messages=[{"no": "003", "text": "Benim"}])
        self.kaydet("M8 okumadan sonra biri mesaj ekledi → source_changed_since_pull, kilit/PUT yok",
                    "source_changed_since_pull", f"{r.get('error')} sıra={self._yollar(adt)}",
                    r.get("error") == "source_changed_since_pull"
                    and not any(c["params"].get("_action") or c["method"] == "PUT" for c in adt.cagri))
        durum["get"] = 404
        r = self._yaz(messages=[{"no": "003", "text": "Benim"}])
        self.kaydet("M8 okumadan sonra sınıf silindi → source_changed_since_pull", "source_changed_since_pull",
                    r.get("error"), r.get("error") == "source_changed_since_pull")
        adt, durum = self._msag([("001", "Bir", False, False)], paket=False)
        self.atom.adt_msgclass_read("ZAXET_MSG")
        r = self._yaz(messages=[{"no": "002", "text": "İki"}])
        self.kaydet("M8 canlıda paket yok + package argümanı yok → msgclass_live_incomplete (tahmin yok)",
                    "msgclass_live_incomplete", r.get("error"), r.get("error") == "msgclass_live_incomplete")
        (self.p / ".axet-code" / "sap-pull-state.json").write_text("{bozuk", encoding="utf-8")
        r = self._yaz(messages=[{"no": "002", "text": "İki"}])
        self.kaydet("M8 pull-state bozuk → pull_state_unreadable", "pull_state_unreadable", r.get("error"),
                    r.get("error") == "pull_state_unreadable")

    def test_M9_sizinti_yok_ve_ic_okuma_kayit_yazmaz(self):
        adt, durum = self._msag([("001", "Bir", False, False)],
                                lock=lambda c: Yanit(403, f"locked; host {SAHTE_HOST} user {H.KULLANICI}:{H.PAROLA}"))
        self.atom.adt_msgclass_read("ZAXET_MSG")
        r = self._yaz(messages=[{"no": "002", "text": "İki"}])
        metin = json.dumps(r, ensure_ascii=False)
        sizinti = [s for s in (SAHTE_HOST, H.PAROLA) if s in metin]
        self.kaydet("M9 kilit hata gövdesinde host/parola → yanıtta YOK", "sızıntı yok", f"{r.get('error')} {sizinti}",
                    r.get("error") == "lock_conflict" and not sizinti)
        p2 = H.make_project(self.root, f"ic{self._sayac}")
        os.environ["AXET_SAP_PROJECT_DIR"] = str(p2)
        self._msag([("001", "Bir", False, False)])
        self.atom._msgclass_oku("ZAXET_MSG")
        self.atom._adt_get_oku("ZAXET_MSG", "msag")
        yok = not (p2 / ".axet-code" / "sap-pull-state.json").exists()
        g = self.atom.adt_get("ZAXET_MSG", "msag")
        self.kaydet("M9 iç okumalar kayıt yazmaz · adt_get(msag) kaydeder · responsible dışarı çıkmaz",
                    "yok · kaydedildi", f"yok={yok} {g.get('pull_state')} keys={sorted(g)}",
                    yok and g.get("pull_state") == "kaydedildi" and "_responsible" not in g
                    and H.KULLANICI not in json.dumps(g, ensure_ascii=False))

    # ═════════════════════════════ MESAJ SİLME (Z113 — kaynak çekirdek 2026-09-24 portu) ══════════════════
    # Kök (kaynak çekirdek canlı, s4_private 2025): tam PUT'tan mesajı ÇIKARMAK silmez (229→229); silme yalnız
    # `<mc:deletedmessages mc:msgno="NNN"/>` ile (229→228). Senaryolar kaynak çekirdek `tests/fixtures/msag_mesaj_silme/run.py`
    # S1/S4-S8/S9-S11/S19-S22/S25/U5'ten uyarlandı. Zor metinler bilerek: `&` yer tutucu, çift tırnak, `<`, documented=true.
    _SIL_BAS = [("000", "&1 &2 &3 &4", True, False), ("001", 'Belge "&1" bulunamadı.', False, True),
                ("002", "Miktar < 0 olamaz (&1).", False, False), ("006", "Atıl mesaj — silinecek.", True, False),
                ("011", "İkinci atıl mesaj; uzun metinli.", False, True), ("020", "Şube & depo eşleşmedi.", True, False)]
    _GET = ("GET", "/sap/bc/adt/messageclass/zaxet_msg")
    _PUT = ("PUT", "/sap/bc/adt/messageclass/zaxet_msg")

    def _sil_kur(self, **kw):
        adt, durum = self._msag(self._SIL_BAS, **kw)
        g = self.atom.adt_msgclass_read("ZAXET_MSG")
        self.assertEqual(g.get("pull_state"), "kaydedildi")
        adt.cagri.clear()
        return adt, durum

    @staticmethod
    def _say(adt, method, action=None):
        return len([c for c in adt.cagri if c["method"] == method
                    and (action is None or c["params"].get("_action") == action)])

    def test_MS1_silme_govdesi_deletedmessages(self):
        """(a) delete_numbers → gövdede `mc:deletedmessages`; silinen yalnız listeden çıkarılmaz; canlıdan gerçekten gider."""
        adt, durum = self._sil_kur()
        r = self._yaz(delete_numbers=["006", "011"])
        put = [c for c in adt.cagri if c["method"] == "PUT"]
        g = put[0]["data"] if put else ""
        kalan_bekl = [m for m in self._SIL_BAS if m[0] not in ("006", "011")]
        ok = (r.get("ok") is True and r.get("readback_verified") is True and r.get("changed") is True
              and len(put) == 1 and _silinenler(g) == ["006", "011"]
              and _put_mesajlari(g) == kalan_bekl                                  # kalanlar CANLI öznitelikleriyle birebir
              and g.rfind("<mc:messages ") < g.find("<mc:deletedmessages")        # son mesajdan SONRA (ST sırası)
              and 'mc:msgno=""' not in g
              and durum["msgs"] == kalan_bekl                                      # canlıdan gerçekten gitti
              and [d["no"] for d in r["plan"]["deleted"]] == ["006", "011"]
              and r.get("message_count_before") == 6 and r.get("message_count_after") == 4
              and (r.get("delete_gate") or {}).get("ok") is True
              and (r.get("delete_gate") or {}).get("scope_not_checked"))
        self.kaydet("MS1 delete_numbers=[006,011] → gövdede deletedmessages 006,011 (mesajlardan sonra) · kalanlar birebir · "
                    "canlı 6→4 · kapı tuttu", "ok · deletedmessages · 6→4",
                    f"ok={r.get('ok')} err={r.get('error')} del={_silinenler(g) if g else None} "
                    f"canli={[m[0] for m in durum['msgs']]} gate={r.get('delete_gate')}", ok)

    def test_MS2_kilit_altinda_yeniden_okuma_ve_sira(self):
        """(b) silmede kilit ALTINDA canlı yeniden okunur (TOCTOU); sıra GET→LOCK→GET→PUT→UNLOCK→GET."""
        adt, durum = self._sil_kur()
        r = self._yaz(delete_numbers=["006"])
        sira = self._yollar(adt)
        self.kaydet("MS2 silme sırası: GET → LOCK → GET (kilit altında) → PUT → UNLOCK → GET (readback)",
                    "6 adım", f"ok={r.get('ok')} sıra={sira}",
                    r.get("ok") is True and sira == [self._GET, ("POST", "LOCK"), self._GET, self._PUT,
                                                     ("POST", "UNLOCK"), self._GET])

        def baskasi_degistirir(d):   # ÖNCE okumasından sonra, kilit alınırken başkası 002'nin metnini değiştirir
            d["msgs"] = [(n, t + " [başkası]", s, dc) if n == "002" else (n, t, s, dc) for n, t, s, dc in d["msgs"]]
        adt, durum = self._sil_kur(on_lock=baskasi_degistirir)
        r = self._yaz(delete_numbers=["006"])
        m002 = dict((m[0], m[1]) for m in durum["msgs"]).get("002", "")
        self.kaydet("MS2 TOCTOU: kilit altında canlı değişmiş → source_changed_since_pull · SIFIR PUT · 1 UNLOCK · 002 korunur",
                    "source_changed_since_pull · PUT 0", f"{r.get('error')} sıra={self._yollar(adt)} 002={m002!r}",
                    r.get("error") == "source_changed_since_pull" and r.get("ok") is False
                    and self._say(adt, "PUT") == 0 and self._say(adt, "POST", "UNLOCK") == 1
                    and m002.endswith("[başkası]") and "006" in [m[0] for m in durum["msgs"]])

        adt, durum = self._sil_kur()
        durum["get_plan"] = [200, 500]   # 1 = yazma öncesi canlı · 2 = kilit altında
        r = self._yaz(delete_numbers=["006"])
        self.kaydet("MS2 kilit altında okuma 500 → pull_live_read_failed · SIFIR PUT · 1 UNLOCK (ölçülemeyen = yazılmaz)",
                    "pull_live_read_failed · PUT 0", f"{r.get('error')} sıra={self._yollar(adt)}",
                    r.get("error") == "pull_live_read_failed" and self._say(adt, "PUT") == 0
                    and self._say(adt, "POST", "UNLOCK") == 1 and durum["msgs"] == self._SIL_BAS)

    def test_MS3_silme_korumalari_yazmadan_durur(self):
        """(c) olmayan numara / tüm sınıf / oturum dili ≠ master / yaz+sil karışık → red, SAP'ye LOCK/PUT GİTMEZ."""
        vakalar = [
            ("canlıda olmayan 999", {"delete_numbers": ["999"]}, "invalid_argument", None),
            ("tüm sınıf", {"delete_numbers": [m[0] for m in self._SIL_BAS]}, "invalid_argument", None),
            ("oturum dili EN ≠ master TR", {"delete_numbers": ["006"]}, "ADR_0005_D", "EN"),
            ("yaz + sil aynı çağrıda", {"messages": [{"no": "030", "text": "Yeni"}], "delete_numbers": ["006"]},
             "invalid_argument", None),
            ("numara '6'", {"delete_numbers": ["6"]}, "invalid_argument", None),
            ("boş numara", {"delete_numbers": [""]}, "invalid_argument", None),
        ]
        for ad, arg, kod, dil in vakalar:
            adt, durum = self._sil_kur()
            if dil:
                adt.language = dil
            r = self._yaz(**arg)
            gercek = r.get("code") if r.get("error") == "guardrail_violation" else r.get("error")
            yazma = self._say(adt, "PUT") + self._say(adt, "POST", "LOCK")
            self.kaydet(f"MS3 silme koruması: {ad} → {kod}, LOCK/PUT YOK", kod, f"{gercek} yazma={yazma}",
                        gercek == kod and yazma == 0 and durum["msgs"] == self._SIL_BAS)

    def test_MS4_silme_sonrasi_readback_kapisi(self):
        """(d) PUT 200 ≠ silindi: mesaj hâlâ varsa / fazlası gittiyse / kalan değiştiyse / okunamadıysa başarı DÖNMEZ."""
        for ad, kip in (("NEGATİF noop (deletedmessages yok sayılır — eski tam-PUT davranışı)", "noop_sil"),
                        ("fazla silen sunucu", "fazla"), ("kalan metni değiştiren sunucu", "degistir"),
                        ("kalanın yalnız documented bayrağını değiştiren sunucu", "doc")):
            adt, durum = self._sil_kur(put_kip=kip)
            r = self._yaz(delete_numbers=["006"])
            gate = r.get("delete_gate") or {}
            self.kaydet(f"MS4 {ad} → ok:false readback_mismatch + delete_gate hata + pull kaydı silindi",
                        "readback_mismatch · gate.ok False",
                        f"ok={r.get('ok')} err={r.get('error')} gate={gate}",
                        r.get("ok") is False and r.get("error") == "readback_mismatch"
                        and gate.get("ok") is False and gate.get("errors")
                        and self.ps.kayit_al("ZAXET_MSG", "msag")[0] is None
                        and self._say(adt, "POST", "UNLOCK") == 1)
        adt, durum = self._sil_kur(put_kip="noop_sil")
        r = self._yaz(delete_numbers=["006"])
        self.kaydet("MS4 noop: kapı silinmeyen numarayı ADIYLA söyler (006)", "006 not_deleted",
                    str((r.get("delete_gate") or {}).get("not_deleted")),
                    (r.get("delete_gate") or {}).get("not_deleted") == ["006"])
        adt, durum = self._sil_kur()
        durum["get_plan"] = [200, 200, 500]   # önce · kilit altı · SONRA
        r = self._yaz(delete_numbers=["006"])
        self.kaydet("MS4 SONRA okunamaz → readback_failed ok:false (ölçülemedi ≠ tuttu)", "readback_failed",
                    f"ok={r.get('ok')} err={r.get('error')} gate={r.get('delete_gate')}",
                    r.get("ok") is False and r.get("error") == "readback_failed"
                    and (r.get("delete_gate") or {}).get("ok") is None)
        adt, durum = self._sil_kur(put_istisna=True)
        r = self._yaz(delete_numbers=["006"])
        self.kaydet("MS4 PUT gönderildikten sonra ağ istisnası → ok:false · 'OLABİLİR' · pull kaydı silindi · UNLOCK",
                    "ok False · ölçülemedi", f"ok={r.get('ok')} err={r.get('error')} msg={str(r.get('message'))[:80]}",
                    r.get("ok") is False and "silindi" in str(r.get("pull_state"))
                    and (r.get("delete_gate") or {}).get("ok") is None
                    and "OLABİLİR" in str((r.get("delete_gate") or {}).get("note"))
                    and self._say(adt, "POST", "UNLOCK") == 1)

    def test_MS5_silmesiz_yazma_kontrol_grubu(self):
        """(e) KONTROL GRUBU — silme yokken yazma akışı DEĞİŞMEZ: kilit altı okuma yok, gövdede deletedmessages yok."""
        adt, durum = self._sil_kur()
        r = self._yaz(messages=[{"no": "030", "text": "Yeni mesaj"}])
        put = [c for c in adt.cagri if c["method"] == "PUT"]
        g = put[0]["data"] if put else ""
        ok = (r.get("ok") is True and r.get("readback_verified") is True
              and self._yollar(adt) == [self._GET, ("POST", "LOCK"), self._PUT, ("POST", "UNLOCK"), self._GET]
              and g and "deletedmessages" not in g and "delete_gate" not in r
              and [m[0] for m in durum["msgs"]] == ["000", "001", "002", "006", "011", "020", "030"])
        self.kaydet("MS5 kontrol: silmesiz ekleme → GET→LOCK→PUT→UNLOCK→GET · deletedmessages YOK · 7 mesaj",
                    "ok · 5 adım", f"ok={r.get('ok')} sıra={self._yollar(adt)}", ok)

    def test_MS6_silme_govdesi_oz_denetimi(self):
        """Gövde öz-denetimi KENDİ BAŞINA (kaynak çekirdek U5): doğru gövde → [], her bozuk gövde → hata listesi."""
        liste = [{"no": m[0], "text": m[1], "selfexplanatory": m[2], "documented": m[3]}
                 for m in self._SIL_BAS if m[0] != "006"]
        iyi = self.mc._govde("ZAXET_MSG", "Açıklama", "TR", "U", "ZAXET_PKG", liste, ["006"])
        satir = iyi.split("\n")
        di = next(i for i, s in enumerate(satir) if "<mc:deletedmessages" in s)
        mi = next(i for i, s in enumerate(satir) if "<mc:messages " in s)
        once = satir[:]
        once.insert(mi, once.pop(di))
        bozuklar = {
            "deleted mesajlardan önce": "\n".join(once),
            "boş msgno": iyi.replace('<mc:deletedmessages mc:msgno="006"/>', '<mc:deletedmessages mc:msgno=""/>'),
            "kalan metin değişmiş": iyi.replace("Miktar &lt; 0 olamaz", "Miktar &lt; 1 olamaz"),
            "yanlış numara silinir": iyi.replace('<mc:deletedmessages mc:msgno="006"/>',
                                                 '<mc:deletedmessages mc:msgno="020"/>'),
            "deletedmessages yok": iyi.replace('<mc:deletedmessages mc:msgno="006"/>', ""),
        }
        sonuc = {k: self.mc._silme_govdesi_denetle(v, liste, ["006"]) for k, v in bozuklar.items()}
        degismeyen = [k for k, v in bozuklar.items() if v == iyi]
        self.kaydet("MS6 gövde öz-denetimi: doğru gövde boş liste, 5 bozuk gövdenin her biri hata listesi",
                    "[] · 5 hata", f"iyi={self.mc._silme_govdesi_denetle(iyi, liste, ['006'])} "
                                   f"boş dönen={[k for k, v in sonuc.items() if not v]} bozulamayan={degismeyen}",
                    self.mc._silme_govdesi_denetle(iyi, liste, ["006"]) == [] and not degismeyen
                    and all(sonuc.values()))

    def test_MS7_tab_lf_cr_kacisi(self):
        """kaynak çekirdek T13/S25: öznitelikte çıplak TAB/LF/CR boşluğa normalleşir → geri gönderilen canlı metin değişir."""
        cok = "Satır1\nSatır2\tsekme\rSON"
        govde = self.mc._govde("ZAXET_MSG", "Açıklama", "TR", "U", "ZAXET_PKG",
                               [{"no": "001", "text": cok, "selfexplanatory": False, "documented": False}])
        geri = _put_mesajlari(govde)[0][1]
        self.kaydet("MS7 _govde TAB/LF/CR: geri ayrıştırma AYNI metni verir", repr(cok), repr(geri), geri == cok)
        adt, durum = self._msag(self._SIL_BAS + [("030", "İlk satır\nikinci\tsatır", False, False)])
        self.atom.adt_msgclass_read("ZAXET_MSG")
        adt.cagri.clear()
        r = self._yaz(delete_numbers=["006"])
        m030 = dict((m[0], m[1]) for m in durum["msgs"]).get("030")
        self.kaydet("MS7 çok satırlı canlı metinle silme → ok · 030 metni birebir", "ok · 030 aynı",
                    f"ok={r.get('ok')} err={r.get('error')} 030={m030!r}",
                    r.get("ok") is True and m030 == "İlk satır\nikinci\tsatır"
                    and "006" not in [m[0] for m in durum["msgs"]])

    # ── Z113 bug gate LOW bulguları ─────────────────────────────────────────────────────────────
    def test_ML1a_msgtext_yok_ayristirici_bos_dize(self):
        """L1: canlı XML'de `mc:msgtext` özniteliği yoksa ayrıştırıcı '' döner, None DEĞİL (kaynak çekirdek
        populate_message_class.py:462 `m.get(..., '')`)."""
        xml = _msag_xml({"ml": "TR", "msgs": [("001", None, False, False), ("002", "Var", False, False)]})
        p = self.atom._parse_msgclass_xml(xml)
        metinler = [m["text"] for m in p["messages"]]
        self.kaydet("ML1a msgtext özniteliği yok → text '' (None değil)", "['', 'Var']", repr(metinler),
                    "msgtext" not in xml.split('msgno="001"')[1].split("/>")[0] and metinler == ["", "Var"])

    def test_ML1b_msgtext_none_govde_ve_kiyas(self):
        """L1: `_govde` None metne `mc:msgtext=""` yazar ("None" değil); `_tam`/`_kiyas_listesi` None ile "None" dizesini
        KARIŞTIRMAZ (eskiden ikisi de `str()` ile "None" oluyordu ⇒ öz-denetim/kapı sahte eşitlik görüyordu)."""
        govde = self.mc._govde("ZAXET_MSG", "Açıklama", "TR", "U", "ZAXET_PKG",
                               [{"no": "001", "text": None, "selfexplanatory": False, "documented": False}])
        n, s = {"no": "001", "text": None}, {"no": "001", "text": "None"}
        ok = ('mc:msgtext=""' in govde and "None" not in govde and _put_mesajlari(govde)[0][1] == ""
              and self.mc._tam(n) != self.mc._tam(s) and self.mc._kiyas_listesi([n]) != self.mc._kiyas_listesi([s])
              and self.mc._tam(n) == self.mc._tam({"no": "001", "text": ""}))
        self.kaydet("ML1b _govde None → msgtext=\"\" · _tam/_kiyas None ≠ 'None'", 'msgtext="" · ayrık',
                    f"govde_msgtext={_put_mesajlari(govde)[0][1]!r} tam={self.mc._tam(n)} vs {self.mc._tam(s)}", ok)

    def test_ML1c_msgtext_yok_arac_silme_ve_birlestirme(self):
        """L1 araç düzeyi: `mc:msgtext`'siz canlı mesaj hem SİLME hem BİRLEŞTİRME (silmesiz) yolunda gövdeye
        `mc:msgtext=""` ile gider; gövdede "None" dizesi YOK, canlı metin "None" olmaz. İki yol aynı ayrıştırıcıyı
        (`_msgclass_oku` → `_parse_msgclass_xml`) kullanır."""
        bas = [("001", None, False, True), ("002", "İki", False, False), ("003", "Üç", False, False)]
        for ad, kw in (("silme", {"delete_numbers": ["003"]}),
                       ("birleştirme", {"messages": [{"no": "004", "text": "Dört"}]})):
            adt, durum = self._msag(bas)
            self.atom.adt_msgclass_read("ZAXET_MSG")
            adt.cagri.clear()
            r = self._yaz(**kw)
            put = [c for c in adt.cagri if c["method"] == "PUT"]
            g = put[0]["data"] if put else ""
            m001 = [m for m in _put_mesajlari(g) if m[0] == "001"] if g else None
            canli001 = dict((m[0], m[1]) for m in durum["msgs"]).get("001")
            self.kaydet(f"ML1c {ad}: msgtext'siz 001 → gövdede msgtext=\"\" · 'None' yok · canlı metin 'None' olmaz",
                        "ok · ('001','',False,True)",
                        f"ok={r.get('ok')} err={r.get('error')} m001={m001} canli001={canli001!r}",
                        r.get("ok") is True and len(put) == 1 and 'mc:msgtext=""' in g and "None" not in g
                        and m001 == [("001", "", False, True)] and canli001 == "")

    def test_ML2_oz_denetim_kablolamasi(self):
        """L2: öz-denetim ARACA kablolu — `_govde` bozuk gövde üretirse `delete_body_selfcheck_failed`, LOCK 0, PUT 0.
        (`_silme_govdesi_denetle` MS6'da kendi başına sınanır; bu test onun ÇAĞRILDIĞINI ve sonucunun uygulandığını sınar.)"""
        adt, durum = self._sil_kur()
        gercek = self.mc._govde
        cagri = []

        def bozuk(*a, **k):   # deletedmessages'ı düşürür → tam PUT no-op olurdu (§27.5: 229→229)
            cagri.append(1)
            return gercek(*a, **k).replace('<mc:deletedmessages mc:msgno="006"/>', "")
        self.mc._govde = bozuk
        try:
            r = self._yaz(delete_numbers=["006"])
        finally:
            self.mc._govde = gercek
        self.kaydet("ML2 bozuk silme gövdesi → delete_body_selfcheck_failed · LOCK 0 · PUT 0 · canlı değişmez",
                    "delete_body_selfcheck_failed · 0/0",
                    f"err={r.get('error')} govde_cagri={len(cagri)} lock={self._say(adt, 'POST', 'LOCK')} "
                    f"put={self._say(adt, 'PUT')}",
                    r.get("ok") is False and r.get("error") == "delete_body_selfcheck_failed" and len(cagri) == 1
                    and self._say(adt, "POST", "LOCK") == 0 and self._say(adt, "PUT") == 0
                    and self._say(adt, "POST", "UNLOCK") == 0 and durum["msgs"] == self._SIL_BAS)


if __name__ == "__main__":
    unittest.main()
