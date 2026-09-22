# -*- coding: utf-8 -*-
"""Yeni yazma yolları (2026-09-13) — süreç içi, SAHTE istemci (ağ yok).

`atom._get_client` sahte bir istemciyle değiştirilir; sahte ADT oturumu HER HTTP çağrısını
(yöntem, yol, parametreler, başlıklar, gövde) kaydeder. Böylece "doğru uca doğru Content-Type ile
doğru gövde gitti" ve "hiç ağa gidilmedi" iddiaları çağrı listesiyle kanıtlanır.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import _helpers as H

sys.dont_write_bytecode = True
if str(H.SCRIPTS) not in sys.path:
    sys.path.insert(0, str(H.SCRIPTS))

SAHTE_HOST = "sahte-sap.example"
TR = "TESTK900001"


class Yanit:
    def __init__(self, status_code=200, text="", headers=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}


class Oturum:
    verify = False

    def __init__(self, adt):
        self.adt = adt

    def get(self, url, headers=None, params=None, verify=None, timeout=None):
        return self.adt._kayit("GET", url, headers, params, None)

    def post(self, url, params=None, data=None, headers=None, verify=None, timeout=None):
        return self.adt._kayit("POST", url, headers, params, data)

    def request(self, method, url, headers=None, timeout=None, **kw):
        return self.adt._kayit(method.upper(), url, headers, kw.get("params"), kw.get("data"))


class SahteADT:
    url = f"http://{SAHTE_HOST}:8000"
    client = "100"
    language = "TR"
    user = H.KULLANICI
    password = H.PAROLA
    csrf_token = "tok"

    def __init__(self, yonlendir):
        self.cagri: list[dict] = []
        self.yonlendir = yonlendir
        self.session = Oturum(self)

    def _kayit(self, method, url, headers, params, data):
        yol = url[len(self.url):] if url.startswith(self.url) else url
        govde = data.decode("utf-8") if isinstance(data, bytes) else data
        c = {"method": method, "path": yol, "headers": dict(headers or {}), "params": dict(params or {}),
             "data": govde}
        self.cagri.append(c)
        sonuc = self.yonlendir(c)
        if isinstance(sonuc, Exception):
            raise sonuc
        return sonuc

    def _get_headers(self, accept_type="application/vnd.sap.adt.core.v1+xml", content_type=None):
        h = {"Accept": accept_type, "x-sap-adt-sessiontype": "stateful", "sap-client": self.client}
        if content_type:
            h["Content-Type"] = content_type
        return h

    def _request_with_csrf_retry(self, method, url, headers=None, timeout=None, **kw):
        return self.session.request(method, url, headers=headers, timeout=timeout, **kw)

    def fetch_csrf_token(self, force_refresh=False):
        return self.csrf_token

    def set_function_module_source(self, name, function_group, source_code, transport=None, activate=False):
        self.cagri.append({"method": "LIB", "path": "set_function_module_source",
                           "params": {"name": name, "fg": function_group, "transport": transport,
                                      "activate": activate}, "data": source_code, "headers": {}})
        self.yonlendir({"method": "LIB", "path": "set_function_module_source", "data": source_code,
                        "params": {}, "headers": {}})
        return {"success": True, "object_url": f"/sap/bc/adt/functions/groups/{function_group.lower()}"
                                              f"/fmodules/{name.lower()}"}

    def activate_object(self, name, url):
        self.cagri.append({"method": "LIB", "path": "activate_object", "params": {"name": name, "url": url},
                           "data": None, "headers": {}})
        return self.akt_sonuc if hasattr(self, "akt_sonuc") else {"success": True}


class SahteIstemci:
    def __init__(self, adt):
        self.adt_client = adt
        self.metadata = '<adtcore:mainObject adtcore:masterLanguage="TR" adtcore:version="inactive"/>'
        self.ddic = None
        self.fm = None
        self.include_canli = None   # push_class_include sonrası canlı içerik

    def get_object_metadata(self, name, object_type=None):
        self.adt_client.cagri.append({"method": "LIB", "path": f"get_object_metadata:{object_type}",
                                      "params": {}, "data": None, "headers": {}})
        return self.metadata

    def download_object(self, name, object_type=None, save_local=False):
        return ""

    def get_ddic_object(self, object_type, name):
        return self.ddic

    def read_function_module(self, name, include_source=True):
        return dict(self.fm)

    def push_class_include(self, class_name, include_kind, transport=None, source_file=None):
        src = Path(source_file).read_text(encoding="utf-8")
        self.adt_client.cagri.append({"method": "LIB", "path": "push_class_include",
                                      "params": {"class_name": class_name, "kind": include_kind,
                                                 "transport": transport}, "data": src, "headers": {}})
        self.include_canli = src
        return {"success": True, "source_uploaded": True, "activated": True,
                "include": {"kind": include_kind, "verified": True}}


def _xml_inaktif_bos():
    return Yanit(200, '<ioc:inactiveObjects xmlns:ioc="http://www.sap.com/abapxml/inactiveCtsObjects"/>')


class YeniYazmaYollari(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="axet_yeni_"))
        cls._eski_env = {k: os.environ.get(k) for k in ("AXET_SAP_PROJECT_DIR", "ADT_SAP_TIER")}
        os.environ.pop("ADT_SAP_TIER", None)
        from sapadt.tools import atom, screen
        from sapadt import pull_state
        cls._adt_ortamini_kaldir(cls._eski_env)
        cls.atom, cls.screen, cls.ps = atom, screen, pull_state
        cls._eski_client = atom._get_client
        cls._sayac = 0

    @staticmethod
    def _adt_ortamini_kaldir(yedek: dict) -> None:
        """ADT_* ortam değişkenlerini kaldır; ilk görülen değeri `yedek`e yaz (tearDownClass geri koyar).

        `sap_adt_lib` içe aktarılırken cwd'de bir `.conn_adt` varsa onu ortam değişkenlerine yükler
        (load_dotenv). Bu, yalnız aynı süreçte başka bir test modülü kütüphaneyi önce içe aktardığında
        görünür (ör. `run_tests.py -k`); tek modül koşumunda görünmez. Kapı birimi
        (`gate.check_connection`) bu değerleri proje dosyasıyla kıyaslar, bu yüzden kaldırılır.
        """
        for k in [k for k in os.environ if k.upper().startswith("ADT_")]:
            yedek.setdefault(k, os.environ.get(k))
            os.environ.pop(k, None)

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

    def kur(self, yonlendir):
        adt = SahteADT(yonlendir)
        ist = SahteIstemci(adt)
        self.atom._get_client = lambda: ist
        return adt, ist

    def kaydet(self, ad, beklenen, gercek, ok):
        H.kaydet(f"YENİ {ad}", beklenen, str(gercek)[:160], ok)
        self.assertTrue(ok, f"{ad}: {gercek}")

    @staticmethod
    def postlar(adt, yol=None):
        return [c for c in adt.cagri if c["method"] == "POST" and (yol is None or c["path"] == yol)]

    # ── A. kabuk yaratma ─────────────────────────────────────────────────────────────────
    def _kabuk(self, tip, ad, beklenen_yol, ct, accept, icerir, icermez=(), extra=None, probe=None,
               ek_baslik=None):
        def yon(c):
            if c["method"] == "POST":
                return Yanit(201, "")
            if probe and c["method"] == "GET":
                return probe(c)
            return Yanit(404, "")
        adt, ist = self.kur(yon)
        r = self.atom.adt_post_shell(tip, ad, "ZAXET_PKG", TR, 'Açıklama & "tırnak"', extra)
        posts = self.postlar(adt)
        ok = (r.get("ok") is True and len(posts) == 1 and posts[0]["path"] == beklenen_yol
              and posts[0]["headers"].get("Content-Type") == ct and posts[0]["headers"].get("Accept") == accept
              and posts[0]["params"] == {"corrNr": TR}
              and all(s in posts[0]["data"] for s in icerir) and not any(s in posts[0]["data"] for s in icermez)
              and "&amp;" in posts[0]["data"] and "&quot;" in posts[0]["data"]
              and r.get("exists_after") is True)
        if ek_baslik:
            ok = ok and all(posts[0]["headers"].get(k) == v for k, v in ek_baslik.items())
        self.kaydet(f"A {tip} kabuk: uç/CT/gövde/corrNr/sonda", f"POST {beklenen_yol}",
                    f"ok={r.get('ok')} err={r.get('error')} {[(p['path'], p['headers'].get('Content-Type')) for p in posts]} "
                    f"exists_after={r.get('exists_after')}", ok)
        return r, adt, ist

    def test_A1_ddls(self):
        r, adt, _ = self._kabuk("ddls", "ZAXET_I_X", "/sap/bc/adt/ddic/ddl/sources",
                                "application/vnd.sap.adt.ddlSource+xml; charset=utf-8",
                                "application/vnd.sap.adt.ddlSource+xml",
                                ['<ddl:ddlSource', 'adtcore:name="ZAXET_I_X"', 'adtcore:masterLanguage="TR"',
                                 'adtcore:uri="/sap/bc/adt/packages/zaxet_pkg"'],
                                icermez=("sourceMainArtifact", "<ddl:source>"))
        self.assertIn("adt_push_source", r.get("next_step", ""))

    def test_A2_srvd(self):
        self._kabuk("srvd", "ZAXET_UI_X", "/sap/bc/adt/ddic/srvd/sources",
                    "application/vnd.sap.adt.ddic.srvd.v1+xml; charset=utf-8", "application/vnd.sap.adt.ddic.srvd.v1+xml",
                    ['<srvd:srvdSource', 'srvd:srvdSourceType="S"', 'adtcore:type="SRVD/SRV"'])

    def test_A3_bdef(self):
        self._kabuk("bdef", "ZAXET_I_X", "/sap/bc/adt/bo/behaviordefinitions",
                    "application/vnd.sap.adt.blues.v1+xml; charset=utf-8", "application/vnd.sap.adt.blues.v1+xml",
                    ['<blue:blueSource xmlns:blue="http://www.sap.com/wbobj/blue"', 'adtcore:type="BDEF/BDO"'],
                    probe=lambda c: Yanit(200, ""))

    def test_A3b_ddlx(self):
        """v0.5.2 Z42: Content-Type ADT discovery'nin kabul ettiği `ddic.ddlx.v1+xml` (eski `ddlxSource+xml` canlıda 415)."""
        r, _, _ = self._kabuk("ddlx", "ZAXET_E_X", "/sap/bc/adt/ddic/ddlx/sources",
                              "application/vnd.sap.adt.ddic.ddlx.v1+xml", "application/vnd.sap.adt.ddic.ddlx.v1+xml",
                              ['<ddlx:ddlxSource xmlns:ddlx="http://www.sap.com/adt/ddic/ddlxsources"',
                               'adtcore:name="ZAXET_E_X"', 'adtcore:masterLanguage="TR"'],
                              icermez=("ddlxSource+xml",), probe=lambda c: Yanit(200, ""))
        self.assertIn("adt_push_source(ddlx)", r.get("next_step", ""))

    def test_A3c_dcls(self):
        for tip in ("dcls", "dcl", "accesscontrol"):
            with self.subTest(tip):
                self._kabuk(tip, "ZAXET_A_X", "/sap/bc/adt/acm/dcl/sources",
                            "application/vnd.sap.adt.dclSource+xml", "application/vnd.sap.adt.dclSource+xml",
                            ['<acm:dclSource xmlns:acm="http://www.sap.com/adt/acm/dclsources"',
                             'adtcore:name="ZAXET_A_X"', 'adtcore:masterLanguage="TR"'],
                            probe=lambda c: Yanit(200, ""))

    def test_A4_fugr(self):
        self._kabuk("fugr", "ZAXET_FG", "/sap/bc/adt/functions/groups",
                    "application/vnd.sap.adt.functions.groups.v2+xml", "application/vnd.sap.adt.functions.groups.v2+xml",
                    ['<group:abapFunctionGroup', 'adtcore:masterLanguage="TR"'])

    def test_A5_func(self):
        def probe(c):
            ok = (c["path"] == "/sap/bc/adt/functions/groups/zaxet_fg/fmodules/zaxet_fm_x"
                  and c["headers"].get("Accept") == "application/vnd.sap.adt.functions.fmodules.v3+xml")
            return Yanit(200, '<fmodule:abapFunctionModule adtcore:masterLanguage="TR"/>') if ok else Yanit(406, "")
        r, _adt, _ = self._kabuk("func", "ZAXET_FM_X", "/sap/bc/adt/functions/groups/zaxet_fg/fmodules",
                                 "application/vnd.sap.adt.functions.fmodules+xml",
                                 "application/vnd.sap.adt.functions.fmodules.v2+xml",
                                 ['<fmodule:abapFunctionModule', 'adtcore:name="ZAXET_FM_X"'],
                                 icermez=("processingType", "packageRef"),
                                 extra={"function_group": "zaxet_fg"}, probe=probe)
        self.assertEqual(r.get("master_language"), "TR")

    def test_A6_msag(self):
        xml = ('<mc:messageClass xmlns:mc="http://www.sap.com/adt/MessageClass" '
               'xmlns:adtcore="http://www.sap.com/adt/core" adtcore:name="ZAXET_MSG" adtcore:masterLanguage="TR"/>')
        self._kabuk("msag", "ZAXET_MSG", "/sap/bc/adt/messageclass", "application/vnd.sap.adt.messageclass.v2+xml",
                    "*/*", ['<mc:messageClass', '<adtcore:packageRef adtcore:name="ZAXET_PKG"/>'],
                    icermez=("masterLanguage",), probe=lambda c: Yanit(200, xml),
                    ek_baslik={"x-sap-adt-sessiontype": "stateless"})

    def test_A7_enqu(self):
        self._kabuk("enqu", "EZAXET_LO", "/sap/bc/adt/ddic/lockobjects/sources",
                    "application/vnd.sap.adt.lockobjects.v1+xml", "*/*",
                    ['<enqu:lockobject', '<enqu:tableName>ZAXET_T</enqu:tableName>',
                     '<enqu:parameterName>MANDT</enqu:parameterName>', '<enqu:parameterName>ID</enqu:parameterName>',
                     '<enqu:lockMode>E</enqu:lockMode>', '<enqu:allowRFC>false</enqu:allowRFC>'],
                    extra={"primary_table": "zaxet_t", "lock_fields": ["mandt", "id"]},
                    probe=lambda c: Yanit(200, "<enqu:lockobject/>"))

    def test_A8_ttyp(self):
        def yon_hazirla(ist):
            ist.ddic = '<ttyp:tableType adtcore:masterLanguage="TR"><ttyp:typeName>ZAXET_S_ROW</ttyp:typeName></ttyp:tableType>'
        adt, ist = self.kur(lambda c: Yanit(201, "") if c["method"] == "POST" else Yanit(404, ""))
        yon_hazirla(ist)
        r = self.atom.adt_post_shell("ttyp", "ZAXET_TT_ROW", "ZAXET_PKG", TR, 'Açıklama & "tırnak"',
                                     {"row_type": "zaxet_s_row"})
        p = self.postlar(adt)[0]
        ok = (r.get("ok") is True and p["path"] == "/sap/bc/adt/ddic/tabletypes"
              and p["headers"]["Content-Type"] == "application/vnd.sap.adt.tabletype.v1+xml"
              and '<ttyp:typeName>ZAXET_S_ROW</ttyp:typeName>' in p["data"] and '<ttyp:dataType/>' in p["data"]
              and r.get("row_type_live") == "ZAXET_S_ROW")
        self.kaydet("A ttyp kabuk: uç/CT/satır tipi + canlı rowType", "tabletypes + row_type_live",
                    f"ok={r.get('ok')} {p['path']} row={r.get('row_type_live')}", ok)

    def test_A9_zaten_var_ve_kalici_degil(self):
        adt, _ = self.kur(lambda c: Yanit(400, "<exc>ExceptionResourceAlreadyExists</exc>") if c["method"] == "POST"
                          else Yanit(200, "managed;"))
        r = self.atom.adt_post_shell("bdef", "ZAXET_I_X", "ZAXET_PKG", TR, "Davranış")
        self.kaydet("A zaten var → already_exists + exists_after=true", "already_exists · True",
                    f"{r.get('error')} · {r.get('exists_after')}",
                    r.get("error") == "already_exists" and r.get("exists_after") is True and r.get("ok") is False)
        adt, _ = self.kur(lambda c: Yanit(201, "") if c["method"] == "POST" else Yanit(404, ""))
        r = self.atom.adt_post_shell("msag", "ZAXET_MSG", "ZAXET_PKG", TR, "Mesajlar")
        self.kaydet("A 201 ama sonda yok → create_not_persisted (sahte-200)", "ok:false · create_not_persisted",
                    f"ok={r.get('ok')} {r.get('error')}", r.get("ok") is False and r.get("error") == "create_not_persisted")

    def test_A10_ag_oncesi_redler(self):
        def patla(c):
            raise AssertionError("ağa gidildi")
        adt, _ = self.kur(patla)
        a = self.atom
        vakalar = [
            ("srvb desteklenmiyor", a.adt_post_shell("srvb", "ZAXET_UI_X_O2", "$TMP", TR, "d"), "unsupported_type"),
            ("doma → composite", a.adt_post_shell("doma", "ZAXET_D", "$TMP", TR, "d"), "unsupported_type"),
            ("paket → Yasak C", a.adt_post_shell("devc", "ZAXET_PKG2", "$TMP", TR, "d"), "ADR_0005_C"),
            ("açıklama boş → Yasak D", a.adt_post_shell("ddls", "ZAXET_I_X", "$TMP", TR, "  "), "ADR_0005_D"),
            ("func std grup → Yasak A", a.adt_post_shell("func", "ZAXET_FM", "$TMP", TR, "d",
                                                         {"function_group": "V45A"}), "ADR_0005_A"),
            ("func extra yok", a.adt_post_shell("func", "ZAXET_FM", "$TMP", TR, "d"), "invalid_argument"),
            ("enqu lock_fields nesne listesi", a.adt_post_shell("enqu", "EZAXET_LO", "$TMP", TR, "d",
                                                                {"primary_table": "T", "lock_fields": [{"name": "X"}]}),
             "invalid_argument"),
            ("class + extra", a.adt_post_shell("class", "ZCL_AXET", "$TMP", TR, "d", {"x": 1}), "invalid_argument"),
            ("ddls tanınmayan extra", a.adt_post_shell("ddls", "ZAXET_I_X", "$TMP", TR, "d", {"row_type": "X"}),
             "invalid_argument"),
        ]
        for ad, r, kod in vakalar:
            gercek = r.get("code") if r.get("error") == "guardrail_violation" else r.get("error")
            self.kaydet(f"A ağ öncesi red: {ad}", kod, gercek, gercek == kod)
        self.assertEqual(adt.cagri, [])

    # ── B. kaynak yazma ──────────────────────────────────────────────────────────────────
    def test_B1_bdef_push(self):
        durum = {"canli": "managed;\n"}

        def yon(c):
            if c["method"] == "GET" and c["path"].endswith("/source/main"):
                return Yanit(200, durum["canli"])
            if c["method"] == "POST" and c["params"].get("_action") == "LOCK":
                return Yanit(200, "<DATA><LOCK_HANDLE>H123</LOCK_HANDLE></DATA>")
            if c["method"] == "PUT":
                durum["canli"] = c["data"]
                return Yanit(200, "")
            if c["method"] == "POST" and c["params"].get("_action") == "UNLOCK":
                return Yanit(200, "")
            return Yanit(500, "beklenmedik")
        adt, _ = self.kur(yon)
        g = self.atom.adt_get("ZAXET_I_X", "bdef")
        self.assertEqual(g.get("pull_state"), "kaydedildi")
        adt.cagri.clear()
        yeni = "managed implementation in class zbp_axet unique;\ndefine behavior for ZAXET_I_X\n{\n}\n"
        r = self.atom.adt_push_source("ZAXET_I_X", "bdef", yeni, transport=TR)
        sira = [(c["method"], c["params"].get("_action") or c["path"].rsplit("/", 2)[-2:][-1]) for c in adt.cagri]
        put = [c for c in adt.cagri if c["method"] == "PUT"][0]
        ok = (r.get("ok") is True and r.get("activated") is False and r.get("readback_verified") is True
              and r.get("pull_state") == "guncellendi"
              and [m for m, _ in sira][:4] == ["GET", "POST", "PUT", "POST"]
              and adt.cagri[1]["params"] == {"_action": "LOCK", "accessMode": "MODIFY", "corrNr": TR}
              and put["path"] == "/sap/bc/adt/bo/behaviordefinitions/zaxet_i_x/source/main"
              and put["params"] == {"corrNr": TR, "lockHandle": "H123"}
              and put["headers"].get("Content-Type") == "text/plain; charset=utf-8"
              and "If-Match" not in put["headers"]
              and not any("/activation" in c["path"] for c in adt.cagri)
              and "activation_note" in r)
        self.kaydet("B bdef push: canlı oku→LOCK→PUT(If-Match yok)→UNLOCK→readback, aktivasyon YOK",
                    "ok · sıra · aktivasyon yok", f"ok={r.get('ok')} err={r.get('error')} sıra={sira}", ok)

    def test_B2_bdef_transport_yok_ve_ccdef(self):
        # Z41 (2026-09-21): ccdef artık yazılabilir segment — transportsuz ccdef ağ öncesi Yasak C ile reddedilir
        # (eskiden `unsupported_type` idi). Uydurma segment hâlâ desteklenmez.
        adt, _ = self.kur(lambda c: AssertionError("ağ"))
        r1 = self.atom.adt_push_source("ZAXET_I_X", "bdef", "managed;")
        r2 = self.atom.adt_push_source("ZCL_AXET_BP", "ccdef", "* x")
        r3 = self.atom.adt_push_source("ZAXET_MSG", "msag", "x", transport=TR)
        ok = (r1.get("code") == "ADR_0005_C" and r2.get("code") == "ADR_0005_C"
              and r3.get("error") == "unsupported_type" and adt.cagri == [])
        self.kaydet("B bdef transportsuz / ccdef transportsuz / msag push → ağ öncesi red", "C · C · unsupported",
                    f"{r1.get('code')} · {r2.get('code')} · {r3.get('error')} · çağrı={len(adt.cagri)}", ok)

    def test_B2b_ccdef_ccmac_push_yolu(self):
        """Z41: ccdef/ccmac ccimp ile AYNI yoldan (`push_class_include`) yazılır. Yazma yolu canlıda ÖLÇÜLDÜ
        (DEV, 2026-09-21: PUT /includes/definitions ve /includes/macros + aktivasyon + readback eşit; kontrol grubu
        ccimp) → dördü de `write_path_measured: true`."""
        canli = {}

        def yon(c):
            if c["method"] == "GET" and "/includes/" in c["path"]:
                seg = c["path"].rsplit("/", 1)[-1]
                return Yanit(200, canli.get(seg, "* eski\n"))
            return Yanit(500, "")
        adt, ist = self.kur(yon)
        orig = ist.push_class_include

        def push(**kw):
            s = orig(**kw)
            canli[kw["include_kind"]] = ist.include_canli
            return s
        ist.push_class_include = push
        sonuc = {}
        for tip, seg in (("ccdef", "definitions"), ("ccmac", "macros"), ("ccimp", "implementations")):
            self.atom.adt_get("ZCL_AXET_BP", tip)
            r = self.atom.adt_push_source("ZCL_AXET_BP", tip, f"* {tip} yeni\n", transport=TR)
            lib = [c for c in adt.cagri if c["path"] == "push_class_include" and c["params"]["kind"] == seg]
            sonuc[tip] = (r.get("ok"), r.get("include"), r.get("write_path_measured"), len(lib))
        ok = (sonuc["ccdef"] == (True, "definitions", True, 1) and sonuc["ccmac"] == (True, "macros", True, 1)
              and sonuc["ccimp"] == (True, "implementations", True, 1))
        self.kaydet("B ccdef/ccmac → push_class_include(definitions|macros) · write_path_measured=true (canlı)",
                    "ccdef/ccmac/ccimp ok+true", sonuc, ok)

    def test_B3_ccimp_push(self):
        canli = {"t": "CLASS lhc_x DEFINITION.\nENDCLASS.\n"}

        def yon(c):
            if c["method"] == "GET" and c["path"] == "/sap/bc/adt/oo/classes/zcl_axet_bp/includes/implementations":
                return Yanit(200, canli["t"])
            return Yanit(500, "")
        adt, ist = self.kur(yon)
        g = self.atom.adt_get("ZCL_AXET_BP", "ccimp")
        kayit = self.ps.kayit_al("ZCL_AXET_BP", "ccimp")[0] or {}
        self.assertEqual(g.get("pull_state"), "kaydedildi")
        yeni = canli["t"] + "CLASS lhc_x IMPLEMENTATION.\nENDCLASS.\n"
        orig = ist.push_class_include

        def push(**kw):
            s = orig(**kw)
            canli["t"] = ist.include_canli
            return s
        ist.push_class_include = push
        r = self.atom.adt_push_source("ZCL_AXET_BP", "ccimp", yeni, transport=TR)
        lib = [c for c in adt.cagri if c["path"] == "push_class_include"]
        ok = (r.get("ok") is True and len(lib) == 1 and lib[0]["params"] == {"class_name": "ZCL_AXET_BP",
                                                                             "kind": "implementations", "transport": TR}
              and lib[0]["data"] == yeni and r.get("readback_verified") is True
              and r.get("pull_state") == "guncellendi" and "implementations:ZCL_AXET_BP" in json.dumps(
                  json.loads((self.p / ".axet-code" / "sap-pull-state.json").read_text(encoding="utf-8")))
              and kayit.get("sha256") == self.ps.ozet("CLASS lhc_x DEFINITION.\nENDCLASS.\n"))
        self.kaydet("B ccimp: adt_get include ucu okur+kaydeder · push_class_include(implementations)",
                    "ok · kayıt anahtarı implementations:", f"ok={r.get('ok')} lib={lib[:1]} ps={r.get('pull_state')}", ok)

    def test_B4_ccau_ilk_yaratim_ve_silinmis(self):
        canli = {"durum": 404, "t": ""}

        def yon(c):
            if c["method"] == "GET" and c["path"].endswith("/includes/testclasses"):
                return Yanit(canli["durum"], canli["t"])
            return Yanit(500, "")
        adt, ist = self.kur(yon)
        g = self.atom.adt_get("ZCL_AXET_BP", "ccau")
        ok1 = g.get("exists") is False and g.get("pull_state") == "kaydedildi (include yok)"
        r = self.atom.adt_push_source("ZCL_AXET_BP", "ccau", "CLASS ltc DEFINITION FOR TESTING.\nENDCLASS.\n",
                                      transport=TR)
        ok2 = r.get("ok") is True and any(c["path"] == "push_class_include" for c in adt.cagri)
        self.kaydet("B ccau yokken çek (kayıt: yok) → yazma anında hâlâ yok → ilk yaratım geçer",
                    "kaydedildi (include yok) · ok", f"{g.get('pull_state')} · ok={r.get('ok')} err={r.get('error')}",
                    ok1 and ok2)
        # başkası arada yarattı: kayıt "yok", canlı dolu → değişti
        p2 = H.make_project(self.root, f"p{self._sayac}_b")
        os.environ["AXET_SAP_PROJECT_DIR"] = str(p2)
        canli.update(durum=404, t="")
        adt, ist = self.kur(yon)
        self.atom.adt_get("ZCL_AXET_BP", "ccau")
        canli.update(durum=200, t="CLASS ltc_baskasi DEFINITION FOR TESTING.\nENDCLASS.\n")
        r = self.atom.adt_push_source("ZCL_AXET_BP", "ccau", "CLASS ltc DEFINITION FOR TESTING.\nENDCLASS.\n",
                                      transport=TR)
        self.kaydet("B ccau çekildiğinde yoktu, şimdi dolu → source_changed_since_pull, push YOK",
                    "source_changed_since_pull", f"{r.get('error')} push={[c['path'] for c in adt.cagri if c['method']=='LIB']}",
                    r.get("error") == "source_changed_since_pull"
                    and not any(c["path"] == "push_class_include" for c in adt.cagri))

    def _fm_kur(self, grup="ZAXET_FG", canli="FUNCTION zaxet_fm_x.\nENDFUNCTION.\n"):
        adt, ist = self.kur(lambda c: Yanit(500, ""))
        durum = {"t": canli}
        ist.fm = {"status": "found", "uri": f"/sap/bc/adt/functions/groups/{grup.lower()}/fmodules/zaxet_fm_x",
                  "function_group": grup, "source": canli, "metadata": "<m/>", "probe": "p"}

        def okuma(name, include_source=True):
            return {**ist.fm, "source": durum["t"]}
        ist.read_function_module = okuma
        return adt, ist, durum

    def test_B5_func_push(self):
        adt, ist, durum = self._fm_kur()
        self.atom.adt_get("ZAXET_FM_X", "func")
        yeni = "FUNCTION zaxet_fm_x\n  IMPORTING\n    VALUE(iv_in) TYPE string.\nENDFUNCTION.\n"
        orig = adt.set_function_module_source

        def sfms(*a, **k):
            s = orig(*a, **k)
            durum["t"] = a[2]
            return s
        adt.set_function_module_source = sfms
        r = self.atom.adt_push_source("ZAXET_FM_X", "func", yeni, transport=TR)
        lib = [c for c in adt.cagri if c["method"] == "LIB"]
        ok = (r.get("ok") is True and r.get("function_group") == "ZAXET_FG"
              and lib[0]["path"] == "set_function_module_source"
              and lib[0]["params"] == {"name": "ZAXET_FM_X", "fg": "ZAXET_FG", "transport": TR, "activate": False}
              and lib[0]["data"] == yeni
              and lib[1]["path"] == "activate_object"
              and lib[1]["params"]["url"] == "/sap/bc/adt/functions/groups/zaxet_fg/fmodules/zaxet_fm_x"
              and r.get("pull_state") == "guncellendi")
        self.kaydet("B func push: grup canlıdan → set_function_module_source(activate=False) → activate_object",
                    "ok · ZAXET_FG · sıra", f"ok={r.get('ok')} err={r.get('error')} lib={[c['path'] for c in lib]}", ok)

    def test_B6_func_std_grup_dml_degisti_aktivasyon(self):
        adt, ist, durum = self._fm_kur(grup="V45A")
        self.atom.adt_get("ZAXET_FM_X", "func")
        r = self.atom.adt_push_source("ZAXET_FM_X", "func", "FUNCTION zaxet_fm_x.\n* y\nENDFUNCTION.\n")
        self.kaydet("B func canlı grup standart → Yasak A, yazma YOK", "ADR_0005_A",
                    f"{r.get('code')} lib={[c['path'] for c in adt.cagri]}",
                    r.get("code") == "ADR_0005_A" and not any(c["method"] == "LIB" for c in adt.cagri))
        adt, ist, durum = self._fm_kur()
        r = self.atom.adt_push_source("ZAXET_FM_X", "func", "FUNCTION zaxet_fm_x.\n MODIFY mara FROM ls.\nENDFUNCTION.\n")
        self.kaydet("B func std tablo DML → Yasak B (2. katman), ağ yok", "ADR_0005_B",
                    r.get("code"), r.get("code") == "ADR_0005_B" and adt.cagri == [])
        self.atom.adt_get("ZAXET_FM_X", "func")
        durum["t"] = "FUNCTION zaxet_fm_x.\n* başkası\nENDFUNCTION.\n"
        r = self.atom.adt_push_source("ZAXET_FM_X", "func", "FUNCTION zaxet_fm_x.\n* ben\nENDFUNCTION.\n")
        self.kaydet("B func çekildikten sonra değişti → source_changed_since_pull", "source_changed_since_pull",
                    r.get("error"), r.get("error") == "source_changed_since_pull"
                    and not any(c["path"] == "set_function_module_source" for c in adt.cagri))
        adt, ist, durum = self._fm_kur()
        adt.akt_sonuc = {"success": False, "errors": [{"message": "FL 387"}]}
        self.atom.adt_get("ZAXET_FM_X", "func")
        r = self.atom.adt_push_source("ZAXET_FM_X", "func", "FUNCTION zaxet_fm_x.\n* yeni\nENDFUNCTION.\n")
        self.kaydet("B func yüklendi ama aktivasyon düştü → ok:false push_failed, kayıt güncellendi",
                    "push_failed · guncellendi", f"{r.get('error')} · {r.get('pull_state')}",
                    r.get("ok") is False and r.get("error") == "push_failed" and r.get("pull_state") == "guncellendi"
                    and r.get("activation_errors"))

    # ── A2. kilit objesi aktivasyonu ─────────────────────────────────────────────────────
    def test_C1_enqu_aktivasyon(self):
        def yon(c):
            if c["method"] == "POST" and c["path"] == "/sap/bc/adt/activation":
                return Yanit(200, '<chkl:messages xmlns:chkl="x" activationExecuted="true"/>')
            if c["method"] == "GET" and "inactiveobjects" in c["path"]:
                return _xml_inaktif_bos()
            return Yanit(500, "")
        adt, _ = self.kur(yon)
        r = self.atom.adt_activate("EZAXET_LO", "enqu")
        p = self.postlar(adt, "/sap/bc/adt/activation")
        ok = (r.get("ok") is True and r.get("activation_verified") is True and len(p) == 1
              and p[0]["params"] == {"method": "activate", "preauditRequested": "true"}
              and 'adtcore:type="ENQU/DL"' in p[0]["data"]
              and 'adtcore:uri="/sap/bc/adt/ddic/lockobjects/sources/ezaxet_lo"' in p[0]["data"])
        self.kaydet("C enqu aktivasyon: reçete gövdesi (ENQU/DL, preaudit=true) + worklist doğrulama",
                    "ok · verified", f"ok={r.get('ok')} err={r.get('error')} v={r.get('activation_verified')}", ok)
        adt, _ = self.kur(lambda c: Yanit(200, '<chkl:messages xmlns:chkl="x" activationExecuted="false"/>'))
        r = self.atom.adt_activate("EZAXET_LO", "enqu")
        self.kaydet("C enqu activationExecuted=false → activation_failed", "activation_failed", r.get("error"),
                    r.get("ok") is False and r.get("error") == "activation_failed")

    # ── C. ekran üreteci ────────────────────────────────────────────────────────────────
    def _soap(self, rc, mesaj):
        return Yanit(200, '<soap-env:Envelope xmlns:soap-env="http://schemas.xmlsoap.org/soap/envelope/">'
                          '<soap-env:Body><n0:ZAXET_FM_SCREEN_GENResponse xmlns:n0="urn:sap-com:document:sap:rfc:functions">'
                          f'<EV_MESSAGE>{mesaj}</EV_MESSAGE><EV_RC>{rc}</EV_RC><IT_BUTTONS/><IT_FIELDS/>'
                          '</n0:ZAXET_FM_SCREEN_GENResponse></soap-env:Body></soap-env:Envelope>')

    def test_D1_ekran_write_ok(self):
        uzun = "screen rc=0; donor=SAPLKKBL/STANDARD; nav_remap=ON(F3/Sh+F3/F12->BACK/EXIT/CANCEL); cua_merge=ok " \
               "kept_status=2 kept_title=1; " + "x" * 450 + " DIKKAT: sonda uyarı"
        adt, _ = self.kur(lambda c: self._soap(0, uzun))
        r = self.screen.adt_screen_generate("ZAXET_FM_SCREEN_GEN", "ZAXET_P_EKRAN", title="Liste & <Rapor>",
                                            transport=TR, src_prog="SAPLKKBL", src_status="STANDARD")
        c = adt.cagri[0]
        d = c["data"]
        ok = (r.get("ok") is True and c["method"] == "POST" and c["path"] == "/sap/bc/soap/rfc"
              and c["params"] == {"sap-client": "100", "sap-language": "TR"}
              and c["headers"] == {"Content-Type": "text/xml; charset=utf-8", "SOAPAction": ""}
              and "<urn:ZAXET_FM_SCREEN_GEN>" in d and "<IV_PROGRAM>ZAXET_P_EKRAN</IV_PROGRAM>" in d
              and "<IV_MODE>WRITE</IV_MODE>" in d and "<IV_TITLE>Liste &amp; &lt;Rapor&gt;</IV_TITLE>" in d
              and "<IT_FIELDS></IT_FIELDS><IT_BUTTONS></IT_BUTTONS>" in d
              and "IV_CUA_MERGE" not in d and "IV_RECREATE" not in d
              and r.get("ev_message") == uzun and r.get("nav_remap") == "ON"
              and r["signals"]["dikkat"] == ["DIKKAT: sonda uyarı"])
        self.kaydet("D ekran WRITE: /sap/bc/soap/rfc · sap-language=master · TABLES boş etiket · EV_MESSAGE kırpılmaz",
                    "ok + zarf doğru", f"ok={r.get('ok')} err={r.get('error')} len={len(r.get('ev_message') or '')}", ok)

    def test_D2_ekran_bantlar_ve_nav_off(self):
        vakalar = [
            (0, "nav_remap=OFF(varsayilan donor)", "nav_remap_off", None),
            (120, "donor status yok", "screen_gen_rc", "donor_status_missing"),
            (301, "guard", "screen_gen_rc", "zy_guard"),
            (2, "screen rc=2 zaten var", "screen_gen_rc", "bilesik"),
        ]
        for rc, mesaj, kod, band in vakalar:
            adt, _ = self.kur(lambda c, rc=rc, mesaj=mesaj: self._soap(rc, mesaj))
            r = self.screen.adt_screen_generate("ZAXET_FM_SCREEN_GEN", "ZAXET_P_EKRAN", title="Liste", transport=TR)
            ok = r.get("ok") is False and r.get("error") == kod and (band is None or r.get("ev_rc_band") == band)
            self.kaydet(f"D EV_RC={rc} → {kod}", f"{kod}/{band}", f"{r.get('error')}/{r.get('ev_rc_band')}", ok)
        adt, _ = self.kur(lambda c: self._soap(5, "fields hatali: X"))
        r = self.screen.adt_screen_generate("ZAXET_FM_SCREEN_GEN", "ZAXET_P_EKRAN", title="Liste", transport=TR,
                                            fields=[{"name": "VBAK-VBELN", "type": "TEMPLATE", "line": 1,
                                                     "column": 1, "from_dict": "X"}],
                                            buttons=[{"fcode": "REFRESH", "text": "Yenile"}])
        d = adt.cagri[0]["data"]
        ok = (r.get("ev_rc_band") == "fields_invalid"
              and "<IT_FIELDS><item><CONT_TYPE></CONT_TYPE><CONT_NAME></CONT_NAME><NAME>VBAK-VBELN</NAME>" in d
              and "<IT_BUTTONS><item><FCODE>REFRESH</FCODE><TEXT>Yenile</TEXT><ICON></ICON>" in d)
        self.kaydet("D EV_RC=5 + fields → fields_invalid; item sırası reçeteyle aynı", "fields_invalid + sıra",
                    r.get("ev_rc_band"), ok)
        adt, _ = self.kur(lambda c: Yanit(500, '<soap-env:Envelope xmlns:soap-env="http://schemas.xmlsoap.org/soap/envelope/">'
                                                '<soap-env:Body><soap-env:Fault><faultstring>RABAX</faultstring>'
                                                '</soap-env:Fault></soap-env:Body></soap-env:Envelope>'))
        r = self.screen.adt_screen_generate("ZAXET_FM_SCREEN_GEN", "ZAXET_P_EKRAN", title="Liste", transport=TR)
        self.kaydet("D SOAP fault → soap_fault", "soap_fault", r.get("error"), r.get("error") == "soap_fault")
        adt, _ = self.kur(lambda c: Yanit(200, "<html>logon</html>"))
        r = self.screen.adt_screen_generate("ZAXET_FM_SCREEN_GEN", "ZAXET_P_EKRAN", mode="READ")
        self.kaydet("D EV_RC yok → ev_rc_missing (başarı sayılmaz)", "ev_rc_missing", r.get("error"),
                    r.get("ok") is False and r.get("error") == "ev_rc_missing")

    def test_D3_ekran_ag_oncesi_redler(self):
        adt, _ = self.kur(lambda c: AssertionError("ağ"))
        s = self.screen.adt_screen_generate
        vakalar = [
            ("fm standart", s("RS_CUA_INTERNAL_WRITE", "ZAXET_P", title="T", transport=TR), "ADR_0005_A"),
            ("program standart", s("ZAXET_FM", "SAPMV45A", title="T", transport=TR), "ADR_0005_A"),
            ("DELETE program standart", s("ZAXET_FM", "SAPLKKBL", mode="DELETE", transport=TR), "ADR_0005_A"),
            ("WRITE transport yok", s("ZAXET_FM", "ZAXET_P", title="T"), "ADR_0005_C"),
            ("WRITE title yok", s("ZAXET_FM", "ZAXET_P", transport=TR), "ADR_0005_D"),
            ("dynpro 100", s("ZAXET_FM", "ZAXET_P", title="T", transport=TR, dynpro="100"), "invalid_argument"),
            ("mode uydurma", s("ZAXET_FM", "ZAXET_P", mode="SIL", transport=TR), "invalid_argument"),
            ("recreate Q", s("ZAXET_FM", "ZAXET_P", title="T", transport=TR, recreate="Q"), "invalid_argument"),
            ("CONTAINER + fields", s("ZAXET_FM", "ZAXET_P", title="T", transport=TR, screen_type="container",
                                     fields=[{"NAME": "X"}]), "invalid_argument"),
            ("buttons tanınmayan alan", s("ZAXET_FM", "ZAXET_P", title="T", transport=TR,
                                          buttons=[{"FCODE": "A", "RENK": "k"}]), "invalid_argument"),
        ]
        for ad, r, kod in vakalar:
            gercek = r.get("code") if r.get("error") == "guardrail_violation" else r.get("error")
            self.kaydet(f"D ağ öncesi red: {ad}", kod, gercek, gercek == kod)
        self.assertEqual(adt.cagri, [])
        qa = H.make_project(self.root, f"qa{self._sayac}", tier_lines=("ADT_SAP_TIER=QA",))
        os.environ["AXET_SAP_PROJECT_DIR"] = str(qa)
        r = s("ZAXET_FM", "ZAXET_P", title="T", transport=TR)
        self.kaydet("D QA tier → ADR_0010_TIER", "ADR_0010_TIER", r.get("code"), r.get("code") == "ADR_0010_TIER")

    def test_D4_ekran_sizinti_yok(self):
        hata = ConnectionError(f"HTTPSConnectionPool(host='{SAHTE_HOST}', port=8000): Max retries exceeded "
                               f"url=http://{H.KULLANICI}:{H.PAROLA}@{SAHTE_HOST}:8000/sap/bc/soap/rfc")
        adt, _ = self.kur(lambda c: hata)
        r = self.screen.adt_screen_generate("ZAXET_FM_SCREEN_GEN", "ZAXET_P_EKRAN", mode="READ")
        metin = json.dumps(r, ensure_ascii=False)
        sizinti = [s for s in (SAHTE_HOST, H.PAROLA) if s in metin]
        self.kaydet("D ağ istisnası mesajında host/parola → çıktıda YOK", "sızıntı yok",
                    f"ok={r.get('ok')} sizinti={sizinti}", r.get("ok") is False and not sizinti)
        adt, _ = self.kur(lambda c: Yanit(500, '<soap-env:Envelope xmlns:soap-env="http://schemas.xmlsoap.org/soap/envelope/">'
                                                f'<soap-env:Body><soap-env:Fault><faultstring>logon {SAHTE_HOST} {H.PAROLA}'
                                                '</faultstring></soap-env:Fault></soap-env:Body></soap-env:Envelope>'))
        r = self.screen.adt_screen_generate("ZAXET_FM_SCREEN_GEN", "ZAXET_P_EKRAN", mode="READ")
        metin = json.dumps(r, ensure_ascii=False)
        self.kaydet("D fault gövdesinde host/parola → çıktıda YOK", "sızıntı yok",
                    [s for s in (SAHTE_HOST, H.PAROLA) if s in metin], SAHTE_HOST not in metin and H.PAROLA not in metin)

    # ── D. reviewer eşlemesi + kapı birim ────────────────────────────────────────────────
    def test_E1_reviewer_eslemesi(self):
        from sapadt._reviewer import task_for_push
        vakalar = [
            (("ddls", "define root view entity ZX as select from t {\n key a }"), "rap_cds_creation"),
            (("cds", "define view entity ZX as projection on ZY { key a }"), "rap_cds_creation"),
            (("ddls", "@AbapCatalog.sqlViewName: 'ZXV'\ndefine view ZX as select from t { key a }"), "cds_update"),
            (("ddls", "// define view entity ZX\ndefine view ZX as select from t { key a }"), "cds_update"),
            (("ddls", "/* as projection on */ define view ZX as select from t { key a }"), "cds_update"),
            (("ccimp", "CLASS lhc DEFINITION."), "class_push"),
            (("bdef", "managed;"), "rap_bdef_creation"),
            (("func", "FUNCTION x."), None),
        ]
        for (tip, kaynak), beklenen in vakalar:
            g = task_for_push(tip, kaynak)
            self.kaydet(f"E task_for_push({tip}, …{kaynak[:22]!r})", str(beklenen), str(g), g == beklenen)

    def test_E2_zincir_validatorlari_var(self):
        import importlib.util
        yol = H.SCRIPTS / "sapadt" / "lib" / "validators" / "run_review.py"
        spec = importlib.util.spec_from_file_location("_rr_test", str(yol))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        eksik = sorted({f"{t}:{s}" for t, z in mod.TASK_VALIDATORS.items() for s, _sv, _d in z
                        if not mod.validator_yolu(s).is_file()})
        self.kaydet("E run_review zincirlerindeki TÜM validator dosyaları mevcut (harici eşleme dahil)",
                    "0 eksik", eksik, not eksik)

    def test_E3_kapi_birim(self):
        from sapadt import gate
        import object_types as ot
        self.assertTrue(gate.transport_gerekli("adt_screen_generate", {"mode": "write"}))
        self.assertFalse(gate.transport_gerekli("adt_screen_generate", {"mode": "Read"}))
        home = self.root / f"home{self._sayac}"
        (home / "config").mkdir(parents=True)
        (home / "config" / "sap-write.local").write_text("x", encoding="utf-8")
        g = gate.check_write("adt_screen_generate", self.p, scope="S1", reason="Birim test gerekçesi uzun",
                             sap_write_flag=True, axet_home=home, log=False)
        self.kaydet("E check_write screen tool_args'sız → ad denetimi fail-closed", "ADR_0005_A", g.code,
                    g.code == "ADR_0005_A")
        g = gate.check_write("adt_screen_generate", self.p, scope="S1", reason="Birim test gerekçesi uzun",
                             sap_write_flag=True, axet_home=home, log=False,
                             tool_args={"fm_name": "ZAXET_FM", "program": "ZAXET_P", "mode": "READ"})
        self.kaydet("E check_write screen READ Z/Y → izin (transport şartı yok)", "allowed", g.code, g.allowed)
        dogru = {k for k, v in ot.OBJECT_TYPES.items() if v["supports_create"]}
        self.kaydet("E supports_create yalnız genel yaratıcının tipleri", "class/include/interface/program",
                    sorted(dogru), dogru == {"class", "interface", "program", "include"})

    def test_E3b_adt_ortam_yalitimi_kosum_kipinden_bagimsiz(self):
        """Kirli ortam (cwd `.conn_adt`'sinin load_dotenv ile bıraktığı ADT_* değerleri) belirlenimli kurulur.

        Kontrol grubu: temizlik OLMADAN kapı `conn_env_mismatch` verir (kirlilik gerçekten ısırır).
        Temizlikten SONRA aynı çağrı `ADR_0005_A` verir. Koşum kipine (tek modül / tüm keşif) bağlı değildir.
        """
        from sapadt import gate
        home = self.root / f"home{self._sayac}"
        (home / "config").mkdir(parents=True)
        (home / "config" / "sap-write.local").write_text("x", encoding="utf-8")
        kirli = {"ADT_SAP_URL": "http://127.0.0.9:1", "ADT_SAP_CLIENT": "999"}
        yedek_env = {k: os.environ.get(k) for k in kirli}
        yedek_sinif = dict(type(self)._eski_env)
        cagir = lambda: gate.check_write("adt_screen_generate", self.p, scope="S1",  # noqa: E731
                                         reason="Birim test gerekçesi uzun", sap_write_flag=True,
                                         axet_home=home, log=False)
        try:
            os.environ.update(kirli)
            kontrol = cagir().code
            self._adt_ortamini_kaldir({})
            kalan = sorted(k for k in os.environ if k.upper().startswith("ADT_"))
            sonra = cagir().code
        finally:
            for k, v in yedek_env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
            type(self)._eski_env.clear()
            type(self)._eski_env.update(yedek_sinif)
        self.kaydet("E3b KONTROL kirli ADT_* ortamı temizliksiz", "conn_env_mismatch", kontrol,
                    kontrol == "conn_env_mismatch")
        self.kaydet("E3b temizlik sonrası aynı çağrı", "ADR_0005_A · ADT_* kalmadı", (sonra, kalan),
                    sonra == "ADR_0005_A" and kalan == [])

    # ── F. BDEF silme (v0.5.2, Z35 canlı bulgusu: genel tip tablosu BDEF'i tanımıyordu) ─────────────
    def _bdef_sil(self, sonra_get: int, sil_hata: Exception | None = None):
        uc = "/sap/bc/adt/bo/behaviordefinitions/zaxet_i_x"

        def yon(c):
            if c["method"] == "GET" and c["path"] == uc + "/source/main":
                return Yanit(sonra_get, "managed;" if sonra_get == 200 else "")
            return Yanit(404, "")
        adt, ist = self.kur(yon)
        adt.lock_object = lambda url, transport=None: (adt.cagri.append(
            {"method": "LIB", "path": "lock", "params": {"url": url, "tr": transport}, "data": None,
             "headers": {}}) or "KILIT1")

        def sil(url, kilit, transport=None):
            adt.cagri.append({"method": "LIB", "path": "delete", "params": {"url": url, "kilit": kilit,
                                                                            "tr": transport}, "data": None, "headers": {}})
            if sil_hata:
                raise sil_hata
            return {"success": True}
        adt.delete_object = sil
        adt.unlock_object = lambda url, kilit: adt.cagri.append(
            {"method": "LIB", "path": "unlock", "params": {"url": url, "kilit": kilit}, "data": None, "headers": {}})
        r = self.atom.adt_delete("ZAXET_I_X", "bdef", TR)
        lib = [(c["path"], c["params"].get("url")) for c in adt.cagri if c["method"] == "LIB"]
        return r, lib, uc

    def test_F1_bdef_sil_kilit_delete_unlock_readback(self):
        r, lib, uc = self._bdef_sil(404)
        ok = (r.get("ok") is True and r.get("deleted") is True and r.get("delete_verified") is True
              and lib == [("lock", uc), ("delete", uc), ("unlock", uc)])
        self.kaydet("F1 bdef sil: kilit→DELETE→unlock (BDEF ucu) + 404 readback → doğrulandı",
                    "ok · verified · lock/delete/unlock", f"ok={r.get('ok')} err={r.get('error')} "
                    f"v={r.get('delete_verified')} {lib}", ok)

    def test_F2_bdef_sil_hala_var_ve_hata_kolu(self):
        r, _, _ = self._bdef_sil(200)
        self.kaydet("F2a bdef sil: readback 200 (hâlâ var) → ok:false · verified:false", "False · False",
                    (r.get("ok"), r.get("delete_verified")), r.get("ok") is False and r.get("delete_verified") is False)
        r2, lib2, uc = self._bdef_sil(404, sil_hata=RuntimeError("423 kilitli"))
        self.kaydet("F2b bdef sil: DELETE hatası → ok:false + kilit yine açılır", "ok False · unlock var",
                    f"ok={r2.get('ok')} {lib2}", r2.get("ok") is False and ("unlock", uc) in lib2)

    def test_F4_dcls_aktivasyon_ve_kaynak_tipi_esanlamlisi(self):
        """v0.5.2 gate LOW: `dcls` (shells'in kanonik adı) aktivasyon/okuma tablolarında da tanınır."""
        durum = {t: (t in self.atom._SOURCE_BASED_TYPES, self.atom._activation_uri("ZAXET_A_X", t))
                 for t in ("dcls", "dcl", "accesscontrol")}
        ok = all(k and u == "/sap/bc/adt/acm/dcl/sources/zaxet_a_x" for k, u in durum.values())
        self.kaydet("F4 dcls/dcl/accesscontrol → kaynak tipi + /acm/dcl/sources aktivasyon URI'si",
                    "üçü de True + aynı URI", durum, ok)

    def test_F5_standart_bdef_silme_dal_oncesi_reddedilir(self):
        """v0.5.2 gate LOW: standart adlı BDEF silme, BDEF dalına (kilit/DELETE) ULAŞMADAN reddedilir."""
        adt, _ = self.kur(lambda c: Yanit(404, ""))
        adt.lock_object = lambda *a, **kw: adt.cagri.append({"method": "LIB", "path": "lock"}) or "K"
        adt.delete_object = lambda *a, **kw: adt.cagri.append({"method": "LIB", "path": "delete"})
        r = self.atom.adt_delete("I_PRODUCTTP", "bdef", TR)
        lib = [c for c in adt.cagri if c.get("method") == "LIB"]
        self.kaydet("F5 standart BDEF (I_PRODUCTTP) silme → ok:false, kilit/DELETE çağrısı yok",
                    "ok False · LIB 0", f"ok={r.get('ok')} err={r.get('error')} lib={lib}",
                    r.get("ok") is False and not lib)

    def test_F3_lib_ddlx_dcl_media_tipi_ve_yukleme_hatasi(self):
        """v0.5.2 Z42: kütüphane DDLX'i discovery'nin kabul ettiği tiple POST eder; kaynak yükleme hatası YUTULMAZ.
        Kontrol grubu: yükleme başarılıysa success:True."""
        import sap_adt_lib  # type: ignore
        k = sap_adt_lib.SAPADTClient

        def sahte(yukleme_hatasi):
            adt = SahteADT(lambda c: Yanit(201, ""))
            adt._validate_object_name = adt._validate_package_name = adt._validate_transport = \
                lambda *a, **kw: None
            adt.timeout_default, adt.debug_enabled = 30, False

            def yukle(*a, **kw):
                if yukleme_hatasi:
                    raise RuntimeError("423 kilitli")
            adt.set_object_source = yukle
            return adt
        sonuc = {}
        for ad, fn in (("ddlx", k.create_metadata_extension), ("dcl", k.create_access_control)):
            a1 = sahte(True)
            hata = fn(a1, "ZAXET_E_X", "src", "d", "$TMP", TR)
            a2 = sahte(False)
            iyi = fn(a2, "ZAXET_E_X", "src", "d", "$TMP", TR)
            sonuc[ad] = (hata.get("success"), hata.get("shell_created"), iyi.get("success"),
                         a1.cagri[0]["headers"].get("Content-Type"))
        ok = (sonuc["ddlx"] == (False, True, True, "application/vnd.sap.adt.ddic.ddlx.v1+xml")
              and sonuc["dcl"] == (False, True, True, "application/vnd.sap.adt.dclSource+xml"))
        self.kaydet("F3 lib DDLX/DCL: doğru Content-Type · yükleme hatası success:false · kontrol success:true",
                    "ddlx.v1 / dclSource · False/True/True", sonuc, ok)


if __name__ == "__main__":
    unittest.main()
