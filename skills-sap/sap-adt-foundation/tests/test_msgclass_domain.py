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

        def post(self, url, headers=None, data=None, params=None, timeout=None, **kw):
            govde = data.decode("utf-8") if isinstance(data, bytes) else data
            self.cagri.append({"method": "POST", "path": url[len(self.url):], "params": dict(params or {}),
                               "headers": dict(headers or {}), "data": govde})
            return Yanit(201, "", {"Location": "/sap/bc/adt/ddic/domains/x"})

        def _get_headers(self, accept_type="application/vnd.sap.adt.core.v1+xml", content_type=None):
            return {"Accept": accept_type, "Content-Type": content_type}

        def _retry_request(self, request_func, operation="API request"):
            return request_func()

    return DomainADT


class DomainIstemci:
    def __init__(self, adt):
        self.adt_client = adt
        self.md = 0

    def get_object_metadata(self, name, object_type=None):
        self.md += 1
        return None if self.md == 1 else '<doma:domain adtcore:version="active" adtcore:masterLanguage="TR"/>'

    def create_domain(self, **kw):
        from sap_client import SAPClient  # type: ignore
        return SAPClient.create_domain(self, **kw)

    def activate_object(self, name, object_type=None):
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
        ET.SubElement(kok, f"{{{NS_MC}}}messages", {f"{{{NS_MC}}}msgno": no, f"{{{NS_MC}}}msgtext": metin,
                                                     f"{{{NS_MC}}}selfexplainatory": "true" if se else "false",
                                                     f"{{{NS_MC}}}documented": "true" if doc else "false"})
    return ET.tostring(kok, encoding="unicode")


def _put_mesajlari(govde: str) -> list:
    kok = ET.fromstring(govde.encode("utf-8"))
    return [(e.get(f"{{{NS_MC}}}msgno"), e.get(f"{{{NS_MC}}}msgtext"), e.get(f"{{{NS_MC}}}selfexplainatory") == "true",
             e.get(f"{{{NS_MC}}}documented") == "true") for e in kok.findall(f"{{{NS_MC}}}messages")]


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

    # ═════════════════════════════ MESAJ SINIFI ═══════════════════════════════════════════════════
    def _msag(self, msgs, *, ml="TR", put_gunceller=True, lock=None, get_durum=200, paket=True, put_durum=200):
        durum = {"msgs": list(msgs), "ml": ml, "paket": paket, "get": get_durum}

        def yon(c):
            if c["method"] == "GET" and c["path"] == "/sap/bc/adt/messageclass/zaxet_msg":
                return Yanit(durum["get"], _msag_xml(durum) if durum["get"] == 200 else "hata")
            if c["method"] == "POST" and c["params"].get("_action") == "LOCK":
                return lock(c) if lock else Yanit(200, "<asx:abap><DATA><LOCK_HANDLE>HX9</LOCK_HANDLE></DATA></asx:abap>")
            if c["method"] == "PUT":
                if put_gunceller and put_durum == 200:
                    durum["msgs"] = _put_mesajlari(c["data"])
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


if __name__ == "__main__":
    unittest.main()
