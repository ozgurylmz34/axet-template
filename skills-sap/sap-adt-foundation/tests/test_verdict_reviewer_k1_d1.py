# -*- coding: utf-8 -*-
"""K1 + D1 — yazma kapısının inceleme zinciri (aXet 2026-09-14, kullanıcı kararları).

K1 "Uyan kontrolleri bağla": prog/include → `program_push` (abaplint, released_objects, decimal_write_to) ·
   intf → `interface_push` (method_param_type_c BLOCKER, decimal_write_to, released_objects) · msag değişmez.
   Önem seviyeleri `class_push` ile aynı. Ölçülemeyen kapı (abaplint include'da `measured=false`) PASS görünmez.
D1 "Dosyasız çağrıda da koşsun": `adt_struct_create` artefaktsız çağrıda DTEL'ler `fields[]`'ten çıkarılır ve
   yazmadan ÖNCE `check_struct_field_dtel_active.py` koşar. Çıkarım TEK fonksiyondur (`utils.ddic_dtel`); artefaktlı
   yol da onu kullanır (Z/Y + /ns/; standart DTEL kontrol edilmez). DTEL 404 → önce yapı/tablo/tablo tipi olarak var
   mı ölçülür; varsa kapsam dışı, yoksa BLOCKER. Okunamayan → `measured=false` → verdict BLOCKER + ÖLÇÜLEMEDİ.

Ağ: yalnız bu testin 127.0.0.1'de açtığı sahte ADT sunucusu (gerçek SAP yok). İstemci (`_get_client`) çağrılırsa
ve test bunu beklemiyorsa `_Patla` fırlar → kontrol ağdan ÖNCE koşmadı demektir.
"""
from __future__ import annotations

import http.server
import json
import os
import shutil
import socket
import sys
import tempfile
import subprocess
import threading
import time
import unittest
import urllib.parse
from pathlib import Path
from unittest import mock

import _helpers as H

sys.dont_write_bytecode = True
LIB = H.SCRIPTS / "sapadt" / "lib"
for _p in (H.SCRIPTS, LIB):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

TR = "DEVK900001"
RUN_REVIEW = LIB / "validators" / "run_review.py"


class _Patla(AssertionError):
    pass


def _patla(*_a, **_k):
    raise _Patla("istemci/ağ çağrıldı — inceleme ağdan ÖNCE reddetmedi")


def _rr():
    import importlib.util
    spec = importlib.util.spec_from_file_location("_rr_k1d1", str(RUN_REVIEW))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── sahte ADT sunucusu ───────────────────────────────────────────────────────────────────────────
def _dtel_xml(version: str) -> str:
    return (f'<blue:blueSource xmlns:blue="http://www.sap.com/wbobj/blue" '
            f'xmlns:adtcore="http://www.sap.com/adt/core" adtcore:version="{version}"/>')


YANITLAR = {
    "/sap/bc/adt/ddic/dataelements/zaxet_e_ok": (200, _dtel_xml("active")),
    "/sap/bc/adt/ddic/dataelements/zaxet_e_inak": (200, _dtel_xml("inactive")),
    "/sap/bc/adt/ddic/dataelements//scwm/de_x": (200, _dtel_xml("active")),
    "/sap/bc/adt/ddic/dataelements/zaxet_e_hata": (500, "boom"),
    "/sap/bc/adt/ddic/structures/zaxet_s_ic": (200, "<x/>"),
    "/sap/bc/adt/ddic/tabletypes/zaxet_tt_x": (200, "<x/>"),
    "/sap/bc/adt/ddic/structures/zaxet_e_probhata": (500, "boom"),
    # `sap_adt_lib._build_session` Retry(total=3, status_forcelist 429/502/503/504) bu cevabı tekrar dener; gate'in adaptörü denemez.
    "/sap/bc/adt/ddic/dataelements/zaxet_e_mesgul": (503, "mesgul"),
}


# B1 (bug gate 2026-09-14): adında bu parça geçen her istek bu kadar saniye bekler (yavaş SAP benzetimi).
YAVAS_PARCA, YAVAS_SN = "zaxet_e_yavas", 2.0
# Re-gate 2026-09-15 (LOW): adında bu parça geçen istek başlıkları hemen gönderir, gövdeyi 1 bayt / 1,5 sn damlatır →
# soket okuması başına zaman aşımı hiç dolmaz (gate'in damla sondası `gate-k1d1/drip/probe.py` ile aynı sunucu davranışı).
DAMLA_PARCA, DAMLA_ARALIK_SN = "zaxet_e_damla", 1.5


class _Isleyici(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        ham = urllib.parse.urlsplit(self.path).path
        anahtar = urllib.parse.unquote(ham).lower()
        self.server.kayit.append((ham, anahtar))
        if DAMLA_PARCA in anahtar:
            self.send_response(200)
            self.send_header("Content-Type", "application/xml")
            self.send_header("Content-Length", "200")
            self.end_headers()
            for _ in range(200):
                try:
                    self.wfile.write(b" ")
                    self.wfile.flush()
                except OSError:
                    return
                time.sleep(DAMLA_ARALIK_SN)
            return
        if YAVAS_PARCA in anahtar:
            time.sleep(YAVAS_SN)
        durum, govde = YANITLAR.get(anahtar, (404, "yok"))
        veri = govde.encode("utf-8")
        self.send_response(durum)
        self.send_header("Content-Type", "application/xml")
        self.send_header("Content-Length", str(len(veri)))
        self.end_headers()
        self.wfile.write(veri)

    def log_message(self, *_a):  # sessiz
        pass


def _kapali_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _Taban(unittest.TestCase):
    ETIKET = "K1D1"

    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="axet_k1d1_"))
        izlenen = [k for k in os.environ if k.upper().startswith("ADT_")] + [
            "AXET_SAP_PROJECT_DIR", "NO_PROXY", "no_proxy"]
        cls._eski_env = {k: os.environ.get(k) for k in izlenen}
        for k in [k for k in os.environ if k.upper().startswith("ADT_")]:
            os.environ.pop(k, None)
        os.environ["NO_PROXY"] = os.environ["no_proxy"] = "127.0.0.1,localhost"
        from sapadt.tools import atom, composite
        from sapadt import gate, _reviewer
        cls.atom, cls.comp, cls.gate, cls.rv = atom, composite, gate, _reviewer
        cls._eski_client = atom._get_client
        cls._sayac = 0
        cls.sunucu = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Isleyici)
        cls.sunucu.kayit = []
        # Yavaş istekte istemci zaman aşımıyla koparsa sunucu ipliğinin yazma hatası gürültü basmasın.
        cls.sunucu.handle_error = lambda *_a, **_k: None
        cls.port = cls.sunucu.server_address[1]
        cls._iplik = threading.Thread(target=cls.sunucu.serve_forever, daemon=True)
        cls._iplik.start()

    @classmethod
    def tearDownClass(cls):
        cls.sunucu.shutdown()
        cls.sunucu.server_close()
        cls.atom._get_client = cls._eski_client
        for k, v in cls._eski_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(cls.root, ignore_errors=True)

    def proje(self, port=None, conn=True):
        type(self)._sayac += 1
        p = self.root / f"p{self._sayac}"
        p.mkdir(parents=True)
        if conn == "yalniz_tier":
            # Bağlantı bilgisi YOK ama tier var: `.conn_adt` hiç olmasa kapı ADR_0010_TIER ile reviewer'dan
            # ÖNCE reddeder (ölçüldü) — validator'ın "bağlantı kurulamadı" dalına ancak böyle ulaşılır.
            (p / ".conn_adt").write_text("ADT_SAP_TIER=DEV\n", encoding="utf-8")
        elif conn:
            satirlar = [f"ADT_SAP_URL=http://127.0.0.1:{port or self.port}", f"ADT_SAP_USER={H.KULLANICI}",
                        f"ADT_SAP_PASSWORD={H.PAROLA}", "ADT_SAP_CLIENT=100", "ADT_SAP_LANGUAGE=TR",
                        "ADT_SAP_TIER=DEV"]
            (p / ".conn_adt").write_text("\n".join(satirlar) + "\n", encoding="utf-8")
        (p / "sap-project.json").write_text(json.dumps(H.SAP_PROJECT_OK), encoding="utf-8")
        os.environ["AXET_SAP_PROJECT_DIR"] = str(p)
        return p

    @staticmethod
    def _adt_env_temizle():
        # Re-gate 2026-09-15 (önceden var #1): süreç içinde `import sap_adt_lib` (D1b) import anında `.conn_adt`'yi
        # `os.environ`'a yükler ve bırakır; sonraki testin alt süreci (reviewer → validator) bu ADT_* değerlerini miras
        # alır ve kendi projesinin `.conn_adt`'si onları EZMEZ (load_dotenv override=False) → D1f "kapalı port" vakası
        # eski sunucuya gidip PASS alıyordu (sıra bağımlılığı). Her testin başında ve sonunda ADT_* temizlenir.
        for k in [k for k in os.environ if k.upper().startswith("ADT_")]:
            os.environ.pop(k, None)

    def setUp(self):
        self._adt_env_temizle()
        self.p = self.proje()
        self.sunucu.kayit.clear()
        self.atom._get_client = _patla

    def tearDown(self):
        self._adt_env_temizle()

    def kaydet(self, ad, beklenen, gercek, ok):
        H.kaydet(f"{self.ETIKET} {ad}", beklenen, str(gercek)[:160], ok)
        self.assertTrue(ok, f"{ad}: {gercek}")

    @staticmethod
    def sonuc(rv: dict, gate: str) -> dict:
        for r in (rv or {}).get("results") or []:
            if r.get("validator") == gate:
                return r
        return {}


# ═════════════════════════════════════ K1 ═════════════════════════════════════════════════════════
class K1ProgIntfZinciri(_Taban):
    ETIKET = "K1"
    INTF_TYPE_C = "INTERFACE zif_axet_demo PUBLIC.\n  METHODS m1 IMPORTING iv_a TYPE c LENGTH 10.\nENDINTERFACE.\n"
    INTF_TEMIZ = "INTERFACE zif_axet_demo PUBLIC.\n  METHODS m1 IMPORTING iv_a TYPE string.\nENDINTERFACE.\n"
    INCLUDE = "*&- include\nFORM f_x.\n  DATA lv_x TYPE string.\n  lv_x = |a|.\nENDFORM.\n"
    PROG = "REPORT zaxet_p_demo.\nDATA lv_x TYPE string.\nlv_x = |a|.\n"

    def test_K1a_eslemeler(self):
        tfp = self.rv.task_for_push
        for tip in ("prog", "program", "include", "prog/i"):
            self.kaydet(f"a task_for_push({tip})", "program_push", tfp(tip, self.PROG), tfp(tip, self.PROG) == "program_push")
        for tip in ("intf", "interface"):
            self.kaydet(f"a task_for_push({tip})", "interface_push", tfp(tip, self.INTF_TEMIZ),
                        tfp(tip, self.INTF_TEMIZ) == "interface_push")
        self.kaydet("a task_for_push(msag) değişmedi", "None", tfp("msag"), tfp("msag") is None)

    def test_K1b_zincir_class_push_onemleriyle(self):
        rr = _rr()
        cp = {s: sv for s, sv, _d in rr.TASK_VALIDATORS["class_push"]}
        beklenen = {
            "program_push": {"check_abaplint.py", "check_released_objects.py", "check_decimal_write_to.py"},
            "interface_push": {"check_method_param_type_c.py", "check_decimal_write_to.py", "check_released_objects.py"},
        }
        for gorev, kume in beklenen.items():
            zincir = {s: sv for s, sv, _d in rr.TASK_VALIDATORS.get(gorev, [])}
            ok = set(zincir) == kume and all(zincir[s] == cp[s] for s in kume)
            self.kaydet(f"b {gorev} zinciri + önem = class_push", sorted(kume), zincir, ok)
        self.kaydet("b interface_push method_param_type_c BLOCKER", "BLOCKER",
                    cp.get("check_method_param_type_c.py"), cp.get("check_method_param_type_c.py") == "BLOCKER")

    def test_K1c_intf_type_c_blocker_agdan_once(self):
        r = self.atom.adt_push_source("ZIF_AXET_DEMO", "intf", self.INTF_TYPE_C, TR)
        g = self.sonuc(r.get("reviewer"), "check_method_param_type_c.py")
        self.kaydet("c intf TYPE c LENGTH → reviewer_blocker, istemci yok", "reviewer_blocker · FAIL",
                    f"{r.get('error')} · {g.get('status')}", r.get("error") == "reviewer_blocker" and g.get("status") == "FAIL")
        r = self.atom.adt_push_source("ZIF_AXET_DEMO", "intf", self.INTF_TEMIZ, TR)
        rv = r.get("reviewer") or {}
        adlar = sorted(x.get("validator") for x in rv.get("results") or [])
        self.kaydet("c KONTROL temiz intf → PASS, 3 gate koştu, sonra pull kaydı", "PASS · pull_before_edit_missing",
                    f"{rv.get('verdict')} · {r.get('error')} · {adlar}",
                    rv.get("verdict") == "PASS" and r.get("error") == "pull_before_edit_missing" and len(adlar) == 3)

    def test_K1d_include_abaplint_olculemedi_pass_gorunmez(self):
        r = self.atom.adt_push_source("ZAXET_I_DEMO", "include", self.INCLUDE, TR)
        rv = r.get("reviewer") or {}
        ab = self.sonuc(rv, "check_abaplint.py")
        olc = [k.get("gate") for k in rv.get("unmeasured") or []]
        self.kaydet("d include → abaplint SKIP (measured=false) = WARNING, PASS değil", "WARNING · SKIP",
                    f"{rv.get('verdict')} · {ab.get('status')} · w={rv.get('warning_count')}",
                    rv.get("verdict") == "WARNING" and ab.get("status") == "SKIP" and rv.get("warning_count") == 1
                    and r.get("error") == "pull_before_edit_missing")
        self.kaydet("d yanıtta ÖLÇÜLEMEDİ izi (unmeasured + notice)", "check_abaplint.py · ÖLÇÜLEMEDİ",
                    f"{olc} · {rv.get('notice')}", olc == ["check_abaplint.py"] and "ÖLÇÜLEMEDİ" in str(rv.get("notice")))
        g = self.gate.review_summary("adt_push_source", {}, r)
        self.kaydet("d gate.review ÖLÇÜLEMEDİ gösterir", "WARNING … ÖLÇÜLEMEDİ", g,
                    str(g).startswith("WARNING") and "ÖLÇÜLEMEDİ" in str(g) and "check_abaplint" in str(g))

    def test_K1e_prog_zinciri_kostu(self):
        r = self.atom.adt_push_source("ZAXET_P_DEMO", "prog", self.PROG, TR)
        rv = r.get("reviewer") or {}
        adlar = sorted(x.get("validator") for x in rv.get("results") or [])
        self.kaydet("e prog → program_push'un 3 gate'i koştu (SKIP değil)", "3 gate",
                    f"{rv.get('verdict')} · {adlar}",
                    rv.get("verdict") in ("PASS", "WARNING") and adlar == sorted(
                        ["check_abaplint.py", "check_released_objects.py", "check_decimal_write_to.py"]))

    def test_K1f_msag_push_degismedi(self):
        r = self.atom.adt_push_source("ZAXET_MSG", "msag", "x", TR)
        self.kaydet("f msag push → unsupported_type (reviewer'a ulaşmaz; değişmedi)", "unsupported_type",
                    r.get("error"), r.get("error") == "unsupported_type")


# ═════════════════════════════════════ D1 ═════════════════════════════════════════════════════════
class _Istemci:
    """Ön kontrol için: obje VAR der → araç `already_exists` ile döner (yazma yok).

    2026-09-21: `adt_struct_create` ön kontrolü `_exists` (metadata) yerine üç değerli `adt_get(structure)` sondasıdır
    (`/ddic/structures/<ad>/source/main` GET) → sahte oturum 200 döner. Oturum yokken sonda ÖLÇÜLEMEDİ olur
    (`exists_unmeasured`) — bu testlerin beklediği "reviewer koştu, yazma yok" durağı `already_exists`'tir."""
    url = "http://sahte-istemci.invalid"

    class _Oturum:
        verify = False

        def get(self, *_a, **_k):
            from types import SimpleNamespace
            return SimpleNamespace(status_code=200, text="define structure zaxet_s_demo {\n  a : abap.char(1);\n}\n")

    session = _Oturum()

    def get_object_metadata(self, name, object_type=None):
        return '<adtcore:mainObject adtcore:version="active"/>'


class D1StructDtel(_Taban):
    ETIKET = "D1"

    def yarat(self, fields, **kw):
        return self.comp.adt_struct_create("ZAXET_S_DEMO", fields, "Test yapısı", "ZAXET_PKG", TR, **kw)

    def dtel_istekleri(self):
        return [a for _h, a in self.sunucu.kayit if "/ddic/" in a]

    # ── çıkarım (tek fonksiyon) ────────────────────────────────────────────────────────────────
    def test_D1a_cikarim_ddl(self):
        from utils.ddic_dtel import dtel_adaylari
        ddl = ("@EndUserText.label : 'Zaxet etiket zaxet_e_etiket'\n"
               "@AbapCatalog.enhancement.category : #NOT_EXTENSIBLE\n"
               "define structure zaxet_s_demo {\n"
               "  // yorum : zaxet_e_yorum;\n"
               "  /* blok zaxet_e_blok */\n"
               "  key mandt : mandt not null;\n"
               "  alan1 : abap.char(10);\n"
               "  alan2 : zaxet_e_ok;\n"
               "  @Semantics.amount.currencyCode : 'zaxet_s_demo.waers'\n"
               "  tutar : abap.curr(15,2);\n"
               "  ns : /scwm/de_x;\n"
               "  ic : YAXET_S_IC;\n"
               "  matnr : matnr;\n"
               "  include zaxet_s_inc;\n"
               "  include zaxet_s_inc2 with suffix _x;\n"
               "}\n")
        g = dtel_adaylari(ddl)
        beklenen = ["/SCWM/DE_X", "YAXET_S_IC", "ZAXET_E_OK"]
        self.kaydet("a DDL: Z/Y + /ns/ tip belirteci; include/abap./std/yorum/annotation hariç", beklenen, g,
                    g == beklenen)

    def test_D1b_alanlar_ayni_cikarimdan_gecer(self):
        from utils.ddic_dtel import alanlardan_ddl, dtel_adaylari, field_type_to_ddl
        import sap_adt_lib  # type: ignore
        fields = [{"name": "A", "type": "char10"}, {"name": "B", "type": "ZAXET_E_OK"},
                  {"name": "C", "type": "/scwm/de_x"}, {"name": "D", "type": "matnr"},
                  {"name": "E", "type": "abap.char(3)"}, {"name": "F", "type": "dec15_2"},
                  {"name": "G", "type": "yaxet_tt_x"}, {"name": "H", "type": "i"}]
        g = dtel_adaylari(alanlardan_ddl("ZAXET_S_DEMO", fields))
        self.kaydet("b fields[] → DDL → aynı çıkarım", ["/SCWM/DE_X", "YAXET_TT_X", "ZAXET_E_OK"], g,
                    g == ["/SCWM/DE_X", "YAXET_TT_X", "ZAXET_E_OK"])
        tipler = ["char10", "c5", "numc8", "n3", "raw16", "curr15_2", "quan13,3", "dec15.2", "p8", "i", "int8",
                  "d", "t", "string", "xstring", "clnt", "lang", "abap.dats", "ZAXET_E_OK", "", "Matnr"]
        lib = [sap_adt_lib.SAPADTClient._field_type_to_ddl(None, t) for t in tipler]
        tek = [field_type_to_ddl(t) for t in tipler]
        self.kaydet("b sap_adt_lib yazma yolu ile çıkarım aynı tip çevirisini kullanıyor", "eşit", lib == tek, lib == tek)

    # ── dosyasız yol ───────────────────────────────────────────────────────────────────────────
    def test_D1c_dosyasiz_olmayan_dtel_blocker_agdan_once(self):
        r = self.yarat([{"name": "A", "type": "ZAXET_E_OK"}, {"name": "B", "type": "ZAXET_E_YOK"}])
        g = self.sonuc(r.get("reviewer"), "check_struct_field_dtel_active.py")
        istek = self.dtel_istekleri()
        ok = (r.get("error") == "reviewer_blocker" and g.get("status") == "FAIL" and g.get("severity") == "BLOCKER"
              and "/sap/bc/adt/ddic/dataelements/zaxet_e_yok" in istek
              and all(f"/sap/bc/adt/ddic/{u}/zaxet_e_yok" in istek for u in ("structures", "tables", "tabletypes")))
        self.kaydet("c artefaktsız: var olmayan Z DTEL (başka tipte de yok) → reviewer_blocker, yazma yok",
                    "reviewer_blocker · FAIL · 1+3 GET", f"{r.get('error')} · {g.get('status')} · {istek}", ok)
        self.kaydet("c gate.review BLOCKER", "BLOCKER (1 blocker", self.gate.review_summary("adt_struct_create", {}, r),
                    str(self.gate.review_summary("adt_struct_create", {}, r)).startswith("BLOCKER (1 blocker"))

    def test_D1d_dosyasiz_aktif_ic_ice_tablo_tipi_ns_gecer(self):
        self.atom._get_client = lambda: _Istemci()
        fields = [{"name": "A", "type": "ZAXET_E_OK"}, {"name": "B", "type": "/scwm/de_x"},
                  {"name": "C", "type": "ZAXET_S_IC"}, {"name": "D", "type": "zaxet_tt_x"},
                  {"name": "E", "type": "matnr"}, {"name": "F", "type": "char10"}]
        r = self.yarat(fields)
        rv = r.get("reviewer") or {}
        g = self.sonuc(rv, "check_struct_field_dtel_active.py")
        ham = [h for h, _a in self.sunucu.kayit]
        ok = (r.get("error") == "already_exists" and rv.get("verdict") == "PASS" and g.get("status") == "PASS"
              and "/sap/bc/adt/ddic/dataelements/%2Fscwm%2Fde_x" in ham
              and not any("matnr" in a for a in self.dtel_istekleri())
              and "kapsam" in (g.get("stdout") or "").lower())
        self.kaydet("d aktif DTEL + iç içe yapı + tablo tipi + /ns/ (kodlanmış) → PASS; standart DTEL sorulmadı",
                    "PASS · %2F · matnr yok", f"{r.get('error')} · {rv.get('verdict')} · {ham}", ok)

    def test_D1e_dosyasiz_inaktif_blocker(self):
        r = self.yarat([{"name": "A", "type": "ZAXET_E_INAK"}])
        g = self.sonuc(r.get("reviewer"), "check_struct_field_dtel_active.py")
        self.kaydet("e inaktif DTEL → reviewer_blocker", "reviewer_blocker · FAIL",
                    f"{r.get('error')} · {g.get('status')}", r.get("error") == "reviewer_blocker" and g.get("status") == "FAIL")

    def test_D1f_olculemedi_blocker_ve_gorunur(self):
        vakalar = [("DTEL GET 500", self.p, [{"name": "A", "type": "ZAXET_E_HATA"}]),
                   ("404 sonrası yapı sondası 500", self.p, [{"name": "A", "type": "ZAXET_E_PROBHATA"}]),
                   ("bağlantı yok (kapalı port)", None, [{"name": "A", "type": "ZAXET_E_OK"}]),
                   (".conn_adt'de bağlantı bilgisi yok (yalnız tier)", "yok", [{"name": "A", "type": "ZAXET_E_OK"}])]
        for ad, proj, fields in vakalar:
            if proj is None:
                self.proje(port=_kapali_port())
            elif proj == "yok":
                self.proje(conn="yalniz_tier")
            r = self.yarat(fields)
            rv = r.get("reviewer") or {}
            g = self.sonuc(rv, "check_struct_field_dtel_active.py")
            olc = [k.get("gate") for k in rv.get("unmeasured") or r.get("unmeasured") or []]
            ok = (r.get("error") == "reviewer_blocker" and g.get("status") == "SKIP"
                  and olc == ["check_struct_field_dtel_active.py"] and "ÖLÇÜLEMEDİ" in str(r.get("message")))
            self.kaydet(f"f {ad} → measured=false → BLOCKER + ÖLÇÜLEMEDİ (PASS değil)", "reviewer_blocker · SKIP",
                        f"{r.get('error')} · {g.get('status')} · {olc} · {str(r.get('message'))[:60]}", ok)

    def test_D1g_dtel_adayi_yok_ag_yok_kapsam_beyani(self):
        self.atom._get_client = lambda: _Istemci()
        r = self.yarat([{"name": "A", "type": "char10"}, {"name": "B", "type": "matnr"}])
        rv = r.get("reviewer") or {}
        g = self.sonuc(rv, "check_struct_field_dtel_active.py")
        ok = (rv.get("verdict") == "PASS" and g.get("status") == "PASS" and not self.sunucu.kayit
              and "standart" in (g.get("stdout") or "").lower())
        self.kaydet("g yalnız ilkel + standart DTEL → PASS, SAP'ye istek yok, kapsam beyanı stdout'ta",
                    "PASS · 0 istek · 'standart'", f"{rv.get('verdict')} · {self.sunucu.kayit} · {(g.get('stdout') or '')[:80]}", ok)

    # ── artefaktlı yol (aynı çıkarım) ──────────────────────────────────────────────────────────
    def test_D1h_artefaktli_genis_kapsam(self):
        ddl = ("@EndUserText.label : 'Test'\ndefine structure zaxet_s_demo {\n"
               "  a : zaxet_e_ok;\n  b : zaxet_e_yok;\n}\n")
        yol = self.p / "zaxet_s_demo.ddls.asddls"
        yol.write_text(ddl, encoding="utf-8")
        rv = self.rv.run_reviewer("struct_creation", str(yol))
        g = next((x for x in rv.results if x.get("validator") == "check_struct_field_dtel_active.py"), {})
        self.kaydet("h artefaktlı: zsd öneki olmayan var olmayan Z DTEL → FAIL (eskiden kapsam dışı PASS)", "FAIL",
                    f"{rv.verdict} · {g.get('status')}", g.get("status") == "FAIL" and rv.verdict == "BLOCKER")
        yol.write_text(ddl.replace("zaxet_e_yok", "zaxet_s_ic"), encoding="utf-8")
        rv = self.rv.run_reviewer("struct_creation", str(yol))
        g = next((x for x in rv.results if x.get("validator") == "check_struct_field_dtel_active.py"), {})
        self.kaydet("h KONTROL artefaktlı: iç içe yapı → gate PASS", "PASS", g.get("status"), g.get("status") == "PASS")


# ═══════════════════════ bug gate düzeltmeleri (2026-09-14, B1-B4) ═══════════════════════════════════
_ZAMAN_ASIMI_GOREVLERI = {"table_creation", "table_update", "struct_creation", "struct_fields_dtel"}


class B1ZamanButcesi(_Taban):
    """B1: 404 sondası DTEL başına 1+3 GET → zincir 30 sn sarmalayıcıyı aşıyor, zaman aşımı WARNING → YAZMA.
    (b) validator toplam süre bütçesiyle döner (bütçe biterse kalan adaylar ÖLÇÜLEMEDİ → BLOCKER) ·
    (a) `check_struct_field_dtel_active` içeren zincirde sarmalayıcı zaman aşımı = BLOCKER (yalnız bu zincirler)."""
    ETIKET = "B1"

    def setUp(self):
        super().setUp()
        self._eski_butce = os.environ.get("AXET_DTEL_GATE_BUTCE_SN")
        os.environ["AXET_DTEL_GATE_BUTCE_SN"] = "1"

    def tearDown(self):
        if self._eski_butce is None:
            os.environ.pop("AXET_DTEL_GATE_BUTCE_SN", None)
        else:
            os.environ["AXET_DTEL_GATE_BUTCE_SN"] = self._eski_butce
        super().tearDown()

    def yarat(self, fields, **kw):
        return self.comp.adt_struct_create("ZAXET_S_DEMO", fields, "Test yapısı", "ZAXET_PKG", TR, **kw)

    def test_B1a_butce_biterse_olculemedi_blocker_zamaninda(self):
        t0 = time.monotonic()
        r = self.yarat([{"name": f"Y{i}", "type": f"ZAXET_E_YAVAS{i}"} for i in range(3)])
        sure = time.monotonic() - t0
        rv = r.get("reviewer") or {}
        g = self.sonuc(rv, "check_struct_field_dtel_active.py")
        ok = (r.get("error") == "reviewer_blocker" and g.get("status") == "SKIP" and sure < 10
              and "bütçe" in (g.get("stderr") or "").lower())
        self.kaydet("a yavaş SAP (istek 2 sn), bütçe 1 sn → SKIP=BLOCKER + 'bütçe', < 10 sn, yazma yok",
                    "reviewer_blocker · SKIP · <10 sn", f"{r.get('error')} · {g.get('status')} · {sure:.1f} sn", ok)
        # Lider şartı 1: red mesajı "DTEL yok" ile karışmaz — bütçe, denetlenmeyen sayısı ve ÖLÇÜLEMEDİ görünür.
        mesaj = str(r.get("message"))
        ok = ("ÖLÇÜLEMEDİ: süre bütçesi (1 sn) doldu, 3 aday denetlenmedi" in mesaj and "denetlenen 0/3" in mesaj
              and "bulunamadı" not in mesaj)
        self.kaydet("a red mesajı: 'ÖLÇÜLEMEDİ: süre bütçesi (1 sn) doldu, 3 aday denetlenmedi' + denetlenen 0/3",
                    "bütçe + sayılar", mesaj[-220:], ok)
        # ÖLÇÜLDÜ (2026-09-14, asılı sahte SAP): oturumun Retry(total=3) adaptörü bütçe kısıtlı GET'i 4 kez deniyordu
        # (gate 42,7 sn, 4 istek). Tek geçiş = tekrar deneme YOK → bütçe 1 sn'de sunucuya en fazla 2 istek ulaşır.
        yavas = [a for _h, a in self.sunucu.kayit if YAVAS_PARCA in a]
        self.kaydet("a tekrar deneme yok: bütçe 1 sn'de yavaş adaylara ≤ 2 istek", "≤ 2", len(yavas), len(yavas) <= 2)

    def test_B1b_bulgu_varken_butce_biterse_fail_ve_kalanlar_gorunur(self):
        t0 = time.monotonic()
        r = self.yarat([{"name": "A", "type": "ZAXET_E_A_YOK"}, {"name": "B", "type": "ZAXET_E_YAVAS1"},
                        {"name": "C", "type": "ZAXET_E_YAVAS2"}])
        sure = time.monotonic() - t0
        g = self.sonuc(r.get("reviewer"), "check_struct_field_dtel_active.py")
        hata = (g.get("stderr") or "")
        ok = (r.get("error") == "reviewer_blocker" and g.get("status") == "FAIL" and sure < 10
              and "ZAXET_E_A_YOK" in hata and "ZAXET_E_YAVAS2" in hata and "bütçe" in hata.lower())
        self.kaydet("b 1 eksik + 2 yavaş, bütçe 1 sn → FAIL (eksik ölçüldü) + kalanlar 'bütçe' ile adlı, < 10 sn",
                    "FAIL · <10 sn · adlar", f"{r.get('error')} · {g.get('status')} · {sure:.1f} sn · {hata[-120:]}", ok)

    def test_B1g_damla_sunucu_uctan_uca_butce_icinde_blocker(self):
        # Re-gate 2026-09-15 (LOW): zaman aşımı soket okuması başınaydı → damlayan yanıtta gate bütçeyi aşıyor, hükmü
        # sarmalayıcının 30 sn zaman aşımı veriyordu. Artık bütçe + süreç açılışları içinde ÖLÇÜLEMEDİ → BLOCKER.
        # Bütçe 3 sn (damla aralığı 1,5 sn'den BÜYÜK): 1 sn'lik bütçede soket başı zaman aşımı (≤ 1 sn) damla aralığından küçük
        # kalıp eski kodu da durduruyordu → test ayırt etmiyordu (mutasyon MR2a' ile ölçüldü).
        os.environ["AXET_DTEL_GATE_BUTCE_SN"] = "3"
        t0 = time.monotonic()
        r = self.yarat([{"name": "A", "type": "ZAXET_E_DAMLA1"}])
        sure = time.monotonic() - t0
        rv = r.get("reviewer") or {}
        g = self.sonuc(rv, "check_struct_field_dtel_active.py")
        ok = (r.get("error") == "reviewer_blocker" and g.get("status") == "SKIP" and sure < 12
              and "ÖLÇÜLEMEDİ: süre bütçesi (3 sn) doldu, 1 aday denetlenmedi" in str(r.get("message")))
        self.kaydet("g damla sunucu (1 bayt/1,5 sn), bütçe 3 sn → SKIP=BLOCKER + bütçe mesajı, < 12 sn (30 sn sarmalayıcı değil)",
                    "reviewer_blocker · SKIP · <10 sn", f"{r.get('error')} · {g.get('status')} · {sure:.1f} sn · "
                    f"{str(r.get('message'))[-120:]}", ok)

    def test_B1c_kontrol_butce_icinde_hizli_sap_degismez(self):
        self.atom._get_client = lambda: _Istemci()
        r = self.yarat([{"name": "A", "type": "ZAXET_E_OK"}, {"name": "C", "type": "ZAXET_S_IC"}])
        rv = r.get("reviewer") or {}
        self.kaydet("c KONTROL: hızlı SAP, aktif DTEL + iç içe yapı → PASS (bütçe 1 sn yeter)", "PASS",
                    f"{r.get('error')} · {rv.get('verdict')}", r.get("error") == "already_exists" and rv.get("verdict") == "PASS")

    def _zaman_asimi(self, *a, **k):
        raise subprocess.TimeoutExpired(cmd="run_review", timeout=30)

    def test_B1d_sarmalayici_zaman_asimi_dtel_zincirinde_blocker(self):
        with mock.patch.object(self.rv.subprocess, "run", side_effect=self._zaman_asimi):
            r = self.yarat([{"name": "A", "type": "ZAXET_E_OK"}])
        olc = [k.get("gate") for k in r.get("unmeasured") or []]
        ok = (r.get("error") == "reviewer_blocker" and "reviewer_timeout" in str((r.get("reviewer") or {}).get("skip_reason"))
              and olc == ["reviewer"] and "ÖLÇÜLEMEDİ" in str(r.get("message")))
        self.kaydet("d dosyasız struct: sarmalayıcı zaman aşımı → reviewer_blocker + ÖLÇÜLEMEDİ, yazma yok",
                    "reviewer_blocker · reviewer_timeout", f"{r.get('error')} · {olc} · {str(r.get('message'))[:80]}", ok)
        yol = self.p / "zaxet_s_demo.ddls.asddls"
        yol.write_text("define structure zaxet_s_demo {\n  a : zaxet_e_ok;\n}\n", encoding="utf-8")
        with mock.patch.object(self.rv.subprocess, "run", side_effect=self._zaman_asimi):
            hukum = {t: self.rv.run_reviewer(t, str(yol)).verdict
                     for t in sorted(_ZAMAN_ASIMI_GOREVLERI | {"class_push", "interface_push", "cds_update", "program_push"})}
        beklenen = {t: ("BLOCKER" if t in _ZAMAN_ASIMI_GOREVLERI else "WARNING") for t in hukum}
        # ⭐ 2026-09-17 K10 — ESKİ PİN (silinmedi, kayda geçiyor): burada
        #   "DTEL gate'li 4 zincir BLOCKER; diğerleri WARNING kalır (KAPSAM SINIRI)"
        # yazıyordu ve `_ZAMAN_ASIMI_GOREVLERI` elle yazılmış 4 görevdi. B1 (a) kaydının kendisi
        # "genelleştirme KULLANICI KARARI bekliyor" diyordu. KARAR GELDİ (2026-09-15: "Süreyi ölç +
        # uzat, sonra BLOCKER") ⇒ kapsam sınırı BİLİNÇLİ OLARAK KALDIRILDI: artık CANLI (SAP'ye
        # bağlanan) BLOCKER gate taşıyan HER zincirde zaman aşımı BLOCKER'dır. Bu testin B1 kapsamı
        # (DTEL gate'li 4 zincir) hâlâ geçerli bir ALT KÜME olarak çivilenir; genişleyen kümenin
        # tamamı + kontrol grubu `tests/test_k10_zaman_asimi_butce.py::K10b3`te ölçülür.
        self.kaydet("d zaman aşımı: DTEL gate'li 4 zincir BLOCKER (kapsam K10 ile GENİŞLETİLDİ; "
                    "canlı BLOCKER'sız 4 zincir hâlâ WARNING)",
                    "4 BLOCKER / 4 WARNING", hukum, hukum == beklenen)

    def test_B1e_zaman_asimi_kumesi_koddan_turetilir(self):
        gorevler = set(self.rv.zaman_asimi_blocker_gorevleri())
        # ⭐ K10: küme artık "elle yazılmış gate listesi ∩ BLOCKER" değil, "KODDAN türetilen CANLI
        # validator kümesi ∩ BLOCKER". Eski pin `set(...) == _ZAMAN_ASIMI_GOREVLERI` (tam eşitlik)
        # idi; K10 kümeyi genişlettiği için artık ALT KÜME çivilenir, tam küme K10b2'de ölçülür.
        self.kaydet("e zaman aşımı=BLOCKER görevleri TASK_VALIDATORS'tan türetilir (B1'in 4 zinciri ⊆ küme)",
                    f"⊇ {sorted(_ZAMAN_ASIMI_GOREVLERI)}", sorted(gorevler),
                    _ZAMAN_ASIMI_GOREVLERI <= gorevler)
        canli = set(self.rv.canli_validatorler())
        self.kaydet("e canlı küme koddan türer ve DTEL gate'ini içerir (eski elle-liste kaldırıldı)",
                    "check_struct_field_dtel_active.py ∈ canlı", sorted(canli),
                    "check_struct_field_dtel_active.py" in canli and not hasattr(self.rv, "ZAMAN_ASIMI_BLOCKER_GATELERI"))


class B1fButceEnvGecersiz(unittest.TestCase):
    """Lider şartı 4: geçersiz env değeri (negatif, sıfır, sayı değil) → varsayılan + görünür uyarı
    satırı (sessizce yutulmaz). Ağ yok: aday içermeyen DDL.

    ⭐ K10 (2026-09-17): "env bütçeyi YALNIZ DÜŞÜREBİLİR + üst sınır sabit 15 sn" şartı KALDIRILDI
    (kullanıcı kararı "Süreyi ölç + UZAT"): bütçeyi yükseltmek gevşetme değil DAHA ÇOK ölçüm
    demektir. Üst sınır artık ZİNCİR bütçesidir ⇒ varsayılan ve sınır `utils/butce.py`den OKUNUR
    (sayı elle yazılmaz — kaynak değişince test sessizce bayatlamasın). "99" hâlâ geçersizdir ama
    ARTIK BAŞKA SEBEPLE: zincir bütçesini (varsayılanda 56 sn) aşıyor, "15'ten büyük" olduğu için değil."""

    def test_B1f_gecersiz_env_varsayilan_ve_uyari(self):
        from utils import butce as _B
        dizin = Path(tempfile.mkdtemp(prefix="axet_b1f_"))
        try:
            ddl = dizin / "s.ddls.asddls"
            ddl.write_text("define structure s {\n  a : abap.char(3);\n}\n", encoding="utf-8")
            betik = LIB / "validators" / "check_struct_field_dtel_active.py"
            for deger, gecerli in (("abc", False), ("-1", False), ("0", False), ("99", False), ("2.5", True)):
                env = dict(os.environ, AXET_DTEL_GATE_BUTCE_SN=deger, PYTHONIOENCODING="utf-8")
                env.pop("AXET_REVIEWER_BUTCE_SN", None)
                p = subprocess.run([sys.executable, str(betik), str(ddl)], capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", env=env, stdin=subprocess.DEVNULL, timeout=60)
                uyari = "AXET_DTEL_GATE_BUTCE_SN" in p.stderr and "varsayılan" in p.stderr
                # Beklenen varsayılan: alt sürecin env'inde AXET_REVIEWER_BUTCE_SN YOK ⇒ modül
                # varsayılanlarından hesaplanır (bu sürecin env'ine bakılmaz — sızıntı olmasın).
                _vars_gate = round((_B.VARSAYILAN_SN - _B.ZINCIR_PAYI_SN) * _B.GATE_ORANI, 1)
                butce = "SÜRE BÜTÇESİ: 2.5 sn" if gecerli else f"SÜRE BÜTÇESİ: {_vars_gate:g} sn"
                ok = p.returncode == 0 and (butce in p.stdout) and (uyari != gecerli)
                H.kaydet(f"B1f env={deger!r} → {'kabul' if gecerli else 'varsayılan + uyarı'}", butce,
                         f"rc={p.returncode} · uyarı={uyari} · {[s for s in p.stdout.splitlines() if 'BÜTÇE' in s]}", ok)
                self.assertTrue(ok, f"{deger}: {p.stdout} {p.stderr}")
        finally:
            shutil.rmtree(dizin, ignore_errors=True)


class B1hGercekToplamSure(unittest.TestCase):
    """Re-gate 2026-09-15 (LOW): bütçe GERÇEK toplam süre sınırıdır — damlayan yanıt ve yavaş istemci kurulumu dahil.
    Gate'in damla sondası (`gate-k1d1/drip/probe.py`: bütçe 3 sn, 1 bayt/1,5 sn, 90 sn'de bitmedi) burada sabitlendi;
    gate doğrudan alt süreçte koşar (sarmalayıcı yok) → süre yalnız gate'in kendisidir."""
    BUTCE = 3
    PAY_SN = 2.0   # süreç açılışı + modül importları (bütçe dışı, yerel) + çıkış; ölçülen aşım 0,3-0,7 sn (IMPLEMENTATION §20.7)
    BETIK = LIB / "validators" / "check_struct_field_dtel_active.py"

    @classmethod
    def setUpClass(cls):
        cls.dizin = Path(tempfile.mkdtemp(prefix="axet_b1h_"))
        cls.sunucu = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Isleyici)
        cls.sunucu.kayit = []
        cls.sunucu.handle_error = lambda *_a, **_k: None
        threading.Thread(target=cls.sunucu.serve_forever, daemon=True).start()
        cls.proj = cls.dizin / "proje"
        cls.proj.mkdir()
        (cls.proj / ".conn_adt").write_text("\n".join([
            f"ADT_SAP_URL=http://127.0.0.1:{cls.sunucu.server_address[1]}", f"ADT_SAP_USER={H.KULLANICI}",
            f"ADT_SAP_PASSWORD={H.PAROLA}", "ADT_SAP_CLIENT=100", "ADT_SAP_LANGUAGE=TR", "ADT_SAP_TIER=DEV"]) + "\n",
            encoding="utf-8")
        (cls.proj / "sap-project.json").write_text(json.dumps(H.SAP_PROJECT_OK), encoding="utf-8")
        cls.ddl_damla = cls.proj / "damla.ddls.asddls"
        cls.ddl_damla.write_text("define structure zs {\n  a : zaxet_e_damla1;\n  b : zaxet_e_damla2;\n}\n", encoding="utf-8")
        cls.ddl_hizli = cls.proj / "hizli.ddls.asddls"
        cls.ddl_hizli.write_text("define structure zs {\n  a : zaxet_e_ok;\n  b : zaxet_e_inak;\n}\n", encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.sunucu.shutdown()
        cls.sunucu.server_close()
        shutil.rmtree(cls.dizin, ignore_errors=True)

    def kos(self, ddl, on_kod=None):
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("ADT_", "AXET_"))}
        env.update(NO_PROXY="127.0.0.1,localhost", no_proxy="127.0.0.1,localhost", PYTHONIOENCODING="utf-8",
                   AXET_SAP_PROJECT_DIR=str(self.proj), AXET_DTEL_GATE_BUTCE_SN=str(self.BUTCE))
        cmd = ([sys.executable, "-c", on_kod] if on_kod else [sys.executable]) + [str(self.BETIK), str(ddl)]
        t0 = time.monotonic()
        try:
            p = subprocess.run(cmd, cwd=str(self.proj), env=env, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=40, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            return None, time.monotonic() - t0
        return p, time.monotonic() - t0

    def _olculemedi_zamaninda(self, ad, p, sure, aday):
        cikti = "" if p is None else p.stdout + p.stderr
        ok = (p is not None and p.returncode == 0 and sure <= self.BUTCE + self.PAY_SN
              and "status=SKIPPED measured=false" in p.stdout
              and f"ÖLÇÜLEMEDİ: süre bütçesi ({self.BUTCE} sn) doldu, {aday} aday denetlenmedi" in p.stderr)
        H.kaydet(f"B1h {ad}", f"≤ {self.BUTCE + self.PAY_SN:g} sn · measured=false · ÖLÇÜLEMEDİ",
                 f"{'ZAMAN AŞIMI 40 sn' if p is None else f'rc={p.returncode}'} · {sure:.1f} sn · {cikti[-160:]!r}", ok)
        self.assertTrue(ok, f"{ad}: {sure:.1f} sn · {cikti[-400:]}")

    def test_B1h_a_damla_yanit_toplam_sinir(self):
        p, sure = self.kos(self.ddl_damla)
        self._olculemedi_zamaninda("a damla yanıt (1 bayt/1,5 sn), bütçe 3 sn → bütçe+pay içinde ÖLÇÜLEMEDİ", p, sure, 2)

    def test_B1h_b_yavas_istemci_kurulumu_butce_icinde(self):
        on_kod = (
            "import runpy, sys, time\n"
            f"sys.path.insert(0, {str(LIB)!r})\n"
            "import sap_adt_lib\n"
            "_asil = sap_adt_lib.SAPADTClient.__init__\n"
            "def _yavas(self, *a, **k):\n"
            "    time.sleep(30)\n"
            "    _asil(self, *a, **k)\n"
            "sap_adt_lib.SAPADTClient.__init__ = _yavas\n"
            "sys.argv = sys.argv[1:]\n"
            "runpy.run_path(sys.argv[0], run_name='__main__')\n")
        p, sure = self.kos(self.ddl_hizli, on_kod)
        self._olculemedi_zamaninda("b istemci kurulumu 30 sn asılı, bütçe 3 sn → bütçe+pay içinde ÖLÇÜLEMEDİ", p, sure, 2)

    def test_B1h_d_tekrar_deneme_yok_503_tek_istek(self):
        # Regresyon pini (lider: "retry'sız adaptör davranışını bozma"): iplikli bütçeden sonra B1a'nın istek sayısı kontrolü
        # adaptör kaldırılınca artık kırılmıyordu (süreç, terk edilen ipliğin tekrarlarından önce çıkıyor — mutasyon MR2d).
        # Hızlı 503 bütçe içinde tekrar denenebilir → sayılır: adaptör varsa TEK istek.
        ddl = self.proj / "mesgul.ddls.asddls"
        ddl.write_text("define structure zs {\n  a : zaxet_e_mesgul;\n}\n", encoding="utf-8")
        self.sunucu.kayit.clear()
        p, sure = self.kos(ddl)
        istek = [a for _h, a in self.sunucu.kayit if "zaxet_e_mesgul" in a]
        ok = (p is not None and p.returncode == 0 and "status=SKIPPED measured=false" in p.stdout and len(istek) == 1)
        H.kaydet("B1h d 503 dönen DTEL → tek istek (tekrar deneme yok), ÖLÇÜLEMEDİ", "1 istek · measured=false",
                 f"{len(istek)} istek · {sure:.1f} sn · {None if p is None else p.returncode}", ok)
        self.assertTrue(ok, f"{len(istek)} istek · {'' if p is None else p.stdout + p.stderr}")

    def test_B1h_c_kontrol_hizli_sap_olculur(self):
        p, sure = self.kos(self.ddl_hizli)
        ok = (p is not None and p.returncode == 1 and "status=FINDING measured=true" in p.stdout
              and "ZAXET_E_INAK" in p.stderr and "ÖLÇÜLEMEDİ" not in p.stderr)
        H.kaydet("B1h c KONTROL hızlı SAP (aktif + inaktif DTEL) → FINDING ölçüldü, iplik/bütçe hükmü bozmaz",
                 "rc=1 · FINDING measured=true", f"{None if p is None else p.returncode} · {sure:.1f} sn", ok)
        self.assertTrue(ok, "" if p is None else p.stdout + p.stderr)


class B2ArtefaktliYolFields(_Taban):
    """B2: `artifact_path` verilince D1 (fields[]) koşmuyordu; var olmayan yol SKIP = geçti."""
    ETIKET = "B2"
    TEMIZ_DDL = "@EndUserText.label : 'Test'\ndefine structure zaxet_s_demo {\n  a : zaxet_e_ok;\n}\n"

    def yarat(self, fields, **kw):
        return self.comp.adt_struct_create("ZAXET_S_DEMO", fields, "Test yapısı", "ZAXET_PKG", TR, **kw)

    def test_B2a_olmayan_artefakt_blocker(self):
        for ad, fields in (("eksik DTEL'li fields", [{"name": "B", "type": "ZAXET_E_YOK"}]),
                           ("temiz fields", [{"name": "A", "type": "ZAXET_E_OK"}])):
            r = self.yarat(fields, artifact_path=str(self.p / "yok_boyle_dosya.ddls.asddls"))
            metin = json.dumps(r, ensure_ascii=False)
            self.kaydet(f"a olmayan artifact_path + {ad} → reviewer_blocker, yazma yok", "reviewer_blocker",
                        f"{r.get('error')} · {'artifact_not_found' in metin}",
                        r.get("error") == "reviewer_blocker" and ("artifact_not_found" in metin or ad.startswith("eksik")))
        r = self.yarat([{"name": "A", "type": "ZAXET_E_OK"}], artifact_path=str(self.p / "yok_boyle_dosya.ddls.asddls"))
        self.kaydet("a temiz fields'ta red sebebi artifact_not_found", "artifact_not_found",
                    str((r.get("reviewer") or {}).get("skip_reason")),
                    "artifact_not_found" in str((r.get("reviewer") or {}).get("skip_reason")))

    def test_B2b_gercek_artefakt_verilse_de_fields_denetlenir(self):
        yol = self.p / "zaxet_s_demo.ddls.asddls"
        yol.write_text(self.TEMIZ_DDL, encoding="utf-8")
        r = self.yarat([{"name": "A", "type": "ZAXET_E_OK"}, {"name": "B", "type": "ZAXET_E_YOK"}], artifact_path=str(yol))
        g = self.sonuc(r.get("reviewer"), "check_struct_field_dtel_active.py")
        self.kaydet("b temiz artefakt + fields'ta eksik DTEL → reviewer_blocker (fields denetlendi)",
                    "reviewer_blocker · FAIL", f"{r.get('error')} · {g.get('status')}",
                    r.get("error") == "reviewer_blocker" and g.get("status") == "FAIL")

    def test_B2d_bos_fields_artefaktla_da_yazmaz(self):
        # Lider şartı 3: yazılan yük fields[]; boşsa artefakt tek başına "PASS" üretemez — araç reviewer'dan önce reddeder.
        yol = self.p / "zaxet_s_demo.ddls.asddls"
        yol.write_text(self.TEMIZ_DDL, encoding="utf-8")
        r = self.yarat([], artifact_path=str(yol))
        self.kaydet("d boş fields[] + geçerli artefakt → validation_error, reviewer/istemci yok", "validation_error",
                    f"{r.get('error')} · istek={len(self.sunucu.kayit)}",
                    r.get("error") == "validation_error" and not self.sunucu.kayit)

    def test_B2c_kontrol_temiz_artefakt_temiz_fields_gecer_iki_girdi_de_koştu(self):
        self.atom._get_client = lambda: _Istemci()
        yol = self.p / "zaxet_s_demo.ddls.asddls"
        yol.write_text(self.TEMIZ_DDL, encoding="utf-8")
        r = self.yarat([{"name": "A", "type": "ZAXET_E_OK"}], artifact_path=str(yol))
        rv = r.get("reviewer") or {}
        girdiler = sorted({x.get("girdi") for x in rv.get("results") or []
                           if x.get("validator") == "check_struct_field_dtel_active.py"})
        self.kaydet("c KONTROL temiz artefakt + temiz fields → PASS; DTEL gate iki girdide de koştu",
                    "already_exists · PASS · [artifact, fields]", f"{r.get('error')} · {rv.get('verdict')} · {girdiler}",
                    r.get("error") == "already_exists" and rv.get("verdict") == "PASS" and girdiler == ["artifact", "fields"])


class B3BelgeKodEsit(unittest.TestCase):
    """B3: belgeler fail-closed davranışı koda eşit anlatır (düzeltmeden sonraki gerçek davranış)."""

    def test_B3_belgeler(self):
        refs = H.FOUNDATION / "references"
        katalog = (refs / "tool-catalog.md").read_text(encoding="utf-8")
        bolum = katalog.split("### `adt_struct_create`", 1)[1].split("\n### ", 1)[0]
        ops = (refs / "foundation-ops.md").read_text(encoding="utf-8")
        satir = next((s for s in ops.splitlines() if "Struct DTEL denetimi" in s), "")
        blok = ops[ops.find(satir):ops.find(satir) + 900] if satir else ""
        for ad, metin in (("tool-catalog adt_struct_create", bolum), ("foundation-ops §3.2", blok)):
            ok = all(p in metin for p in ("artifact_not_found", "reviewer_timeout", "bütçe"))
            H.kaydet(f"B3 {ad}: artifact_not_found + reviewer_timeout + bütçe anlatılıyor", "3 terim", ok, ok)
            self.assertTrue(ok, ad)

    def test_B3b_validator_map_ve_kod_metinleri(self):
        # Re-gate 2026-09-15 (MEDIUM): validator-map ve kodun kendi açıklamaları hâlâ "artefaktsız / artefakt verilmezse" diyordu;
        # kod `fields[]`'i HER çağrıda denetler (`composite.adt_struct_create` → `_reviewer.run_reviewer_struct`).
        from sapadt import _reviewer as rv
        vm = (H.SKILLS_SAP / "sap-code-review" / "references" / "validator-map.md").read_text(encoding="utf-8").splitlines()
        s1 = next((s for s in vm if s.startswith("| `adt_struct_create`")), "")
        s2 = next((s for s in vm if s.startswith("| `struct_fields_dtel`")), "")
        aciklama = {s: d for s, _sv, d in _rr().TASK_VALIDATORS["struct_fields_dtel"]}.get("check_struct_field_dtel_active.py", "")
        doc = rv.run_reviewer_struct_alanlari.__doc__ or ""
        kontroller = {
            "validator-map §1 adt_struct_create": (s1, "her çağrıda" in s1 and "artifact_not_found" in s1 and "verilmezse" not in s1),
            "validator-map §2 struct_fields_dtel": (s2, "her çağrıda" in s2 and "artefaktsız" not in s2.lower()),
            "run_review struct_fields_dtel açıklaması (rapora basılır)": (aciklama, "her çağrıda" in aciklama
                                                                          and "artefaktsız" not in aciklama.lower()),
            "_reviewer.run_reviewer_struct_alanlari docstring": (doc, "her çağrıda" in doc and "artefaktsız" not in doc.lower()),
        }
        for ad, (metin, ok) in kontroller.items():
            H.kaydet(f"B3b {ad}: 'her çağrıda', 'artefaktsız/verilmezse' yok", "koda eşit", metin[:150], ok)
            self.assertTrue(ok, f"{ad}: {metin}")


class B6BirlestirNormalize(unittest.TestCase):
    """Re-gate 2026-09-15 (ÖNERİ): `_birlestir` tanınmayan verdict'e BLOCKER SIRASI veriyor ama metni aynen döndürüyordu
    (`X` + `BLOCKER` → `X`, `is_blocker` False) → tanınmayan verdict "BLOCKER"a normalize edilir (fail-closed)."""

    def test_B6_tanimsiz_verdict_blocker(self):
        from sapadt import _reviewer as rv
        RR = rv.ReviewerResult
        vakalar = [
            ("tanımsız + BLOCKER (eşitlikte ilk parça)", [("fields", RR("X")), ("artifact", RR("BLOCKER"))], "BLOCKER"),
            ("yalnız tanımsız", [("fields", RR("garip"))], "BLOCKER"),
            ("küçük harf 'pass' tanımsızdır", [("fields", RR("pass")), ("artifact", RR("PASS"))], "BLOCKER"),
            ("KONTROL PASS + WARNING", [("fields", RR("PASS")), ("artifact", RR("WARNING"))], "WARNING"),
            ("KONTROL PASS + SKIP", [("fields", RR("PASS")), ("artifact", RR("SKIP"))], "SKIP"),
        ]
        for ad, parcalar, beklenen in vakalar:
            r = rv._birlestir(parcalar)
            ok = r.verdict == beklenen and r.is_blocker == (beklenen == "BLOCKER")
            H.kaydet(f"B6 _birlestir {ad}", beklenen, f"{r.verdict} · is_blocker={r.is_blocker}", ok)
            self.assertTrue(ok, f"{ad}: {r.verdict}")


class B7TekRender(_Taban):
    """Re-gate 2026-09-15 (önceden var #2): `create_structure` alan açıklamasını `// {desc}` satırı olarak yazar, gate'in DDL'i
    açıklamayı almıyordu → açıklamadaki satır sonu, gate'in görmediği bir alan satırı yazdırabiliyordu. Artık gate'in DDL'i
    yazma yolunun AYNI render fonksiyonundan gelir (`utils.ddic_dtel`)."""
    ETIKET = "B7"
    ENJEKTE = "x\n  b : zaxet_e_yok_desc;"
    # Tur 3 (3. dar gate, MEDIUM): tek render açıklama satırlarını da gate'e taşıdı; çıkarıcı `--`'yı tanımıyor ve `/*` görünce blok
    # yorum sanıyor → sonraki açıklamadaki `*/`'a kadar gerçek alan satırları gizleniyordu (HEAD c9b5538'de BLOCKER, yeni ağaçta PASS).
    REGRESYON = [{"name": "A", "type": "ZAXET_E_OK", "description": "x\n-- /*"}, {"name": "B", "type": "ZAXET_E_YOK"},
                 {"name": "C", "type": "ZAXET_E_OK", "description": "*/"}]
    # Lider kararı: render'a giren serbest metinde bu karakterler YASAK (ValueError / validation_error).
    YASAK = {"\r": "U+000D", "\n": "U+000A", "\u2028": "U+2028", "\u2029": "U+2029", "\x85": "U+0085"}

    @staticmethod
    def _yerlestir(yer, ch):
        """(yer etiketi, fields, yapı açıklaması) — karakter yalnız bir serbest metne konur."""
        f = [{"name": "A", "type": "ZAXET_E_OK", "description": "tutar"}, {"name": "B", "type": "char10"}]
        aciklama = "Test yapısı"
        if yer == "yapı açıklaması":
            aciklama = f"Test{ch}yapısı"
        elif yer == "fields[0].description":
            f[0]["description"] = f"tu{ch}tar"
        elif yer == "fields[1].name":
            f[1]["name"] = f"B{ch}X"
        elif yer == "fields[1].type":
            f[1]["type"] = f"char10{ch}"
        return f, aciklama

    YERLER = ("yapı açıklaması", "fields[0].description", "fields[1].name", "fields[1].type")

    def test_B7a_aciklamadaki_satir_sonu_agdan_once_reddedilir(self):
        # Önce (re-gate tur 2): gate yazılan satırı görüp BLOCKER veriyordu. Tur 3: satır sonu ağdan ÖNCE validation_error.
        try:
            r = self.comp.adt_struct_create("ZAXET_S_DEMO", [{"name": "A", "type": "ZAXET_E_OK", "description": self.ENJEKTE}],
                                            "Test yapısı", "ZAXET_PKG", TR)
        except _Patla:
            r = {"error": "incelemeden_gecti_istemci_cagrildi"}
        ok = r.get("error") == "validation_error" and not self.sunucu.kayit
        self.kaydet("a alan açıklamasında satır sonu + gizli alan → validation_error, SAP'ye istek yok",
                    "validation_error · 0 istek", f"{r.get('error')} · {len(self.sunucu.kayit)} istek", ok)

    def test_B7c_regresyon_dashdash_blok_yorum(self):
        try:
            r = self.comp.adt_struct_create("ZAXET_S_DEMO", self.REGRESYON, "Test yapısı", "ZAXET_PKG", TR)
        except _Patla:
            r = {"error": "incelemeden_gecti_istemci_cagrildi"}
        ok = (r.get("error") == "validation_error" and not self.sunucu.kayit
              and "fields[0].description" in str(r.get("message")) and "U+000A" in str(r.get("message")))
        self.kaydet("c gate probe girdisi (A açıklama 'x\\n-- /*', B eksik DTEL, C açıklama '*/') → validation_error, istemci/ağ yok",
                    "validation_error · fields[0].description · U+000A · 0 istek",
                    f"{r.get('error')} · {str(r.get('message'))[:120]} · {len(self.sunucu.kayit)} istek", ok)

    def test_B7d_render_satir_sonu_reddi(self):
        from utils.ddic_dtel import yapi_ddl_kaynagi
        kalan = []
        for ch, kod in self.YASAK.items():
            for yer in self.YERLER:
                f, aciklama = self._yerlestir(yer, ch)
                try:
                    yapi_ddl_kaynagi("ZAXET_S_DEMO", f, aciklama)
                    sonuc, ok = "ValueError YOK (render etti)", False
                except ValueError as exc:
                    sonuc, ok = str(exc), yer in str(exc) and kod in str(exc)
                # Her vaka ayrı satır: bir vakada düşünce diğerleri de ölçülsün (karakter başına mutasyon görünür olsun).
                H.kaydet(f"{self.ETIKET} d render {kod} · {yer} → ValueError (yer + kod adıyla)", "ValueError", sonuc[:120], ok)
                if not ok:
                    kalan.append(f"{kod}·{yer}")
        self.assertFalse(kalan, f"render reddetmedi: {kalan}")

    def test_B7e_composite_on_kontrol_agdan_once(self):
        cagri = []

        def izle(*a, **k):
            cagri.append(a)
            return self.rv.ReviewerResult(verdict="BLOCKER", blocker_count=1, skip_reason="test_izleme")

        kalan = []
        for ch, kod in self.YASAK.items():
            for yer in self.YERLER:
                f, aciklama = self._yerlestir(yer, ch)
                cagri.clear()
                self.sunucu.kayit.clear()
                with mock.patch.object(self.comp, "run_reviewer_struct", side_effect=izle):
                    try:
                        r = self.comp.adt_struct_create("ZAXET_S_DEMO", f, aciklama, "ZAXET_PKG", TR)
                    except _Patla:
                        r = {"error": "istemci_cagrildi"}
                mesaj = str(r.get("message"))
                ok = (r.get("error") == "validation_error" and not cagri and not self.sunucu.kayit
                      and yer in mesaj and kod in mesaj)
                H.kaydet(f"{self.ETIKET} e composite {kod} · {yer} → validation_error, reviewer/ağ yok, mesaj yeri + kodu söyler",
                         "validation_error · 0 reviewer · 0 istek",
                         f"{r.get('error')} · reviewer={len(cagri)} · {len(self.sunucu.kayit)} istek · {mesaj[:90]}"[:160], ok)
                if not ok:
                    kalan.append(f"{kod}·{yer}")
        self.assertFalse(kalan, f"composite ön kontrolü yakalamadı: {kalan}")

    def test_B7f_gate_yolu_render_reddi_blocker(self):
        r = self.rv.run_reviewer_struct("ZAXET_S_DEMO", self.REGRESYON, description="Test yapısı")
        ok = r.verdict == "BLOCKER" and r.skip_reason.startswith("ddl_render_hatasi") and not self.sunucu.kayit
        self.kaydet("f gate yolu (run_reviewer_struct doğrudan) probe girdisi → BLOCKER ddl_render_hatasi, ağ yok",
                    "BLOCKER · ddl_render_hatasi · 0 istek", f"{r.verdict} · {r.skip_reason[:60]} · {len(self.sunucu.kayit)} istek", ok)

    def _yazilan_ddl(self, name, fields, description):
        """`sap_adt_lib.SAPADTClient.create_structure`'ın source PUT'unda SAP'ye gönderdiği DDL (ağsız taslak istemci)."""
        import sap_adt_lib  # type: ignore
        from types import SimpleNamespace
        yakala = {}

        def put(*_a, **k):
            yakala["ddl"] = k["data"].decode("utf-8")
            return SimpleNamespace(status_code=200, text="")

        c = object.__new__(sap_adt_lib.SAPADTClient)
        c.url, c.language, c.csrf_token, c.timeout_default = "http://127.0.0.1:9", "TR", "t", 1
        c._get_headers = lambda *_a, **_k: {}
        c._retry_request = lambda fn, _m: fn()
        c.lock_object = lambda *_a, **_k: "kilit"
        c.unlock_object = lambda *_a, **_k: None
        c.session = SimpleNamespace(post=lambda *_a, **_k: SimpleNamespace(status_code=201, headers={}, text=""), put=put)
        c.create_structure(name, fields, description, "ZAXET_PKG", TR)
        return yakala.get("ddl")

    def _gate_ddl(self, name, fields, description):
        """`adt_struct_create`'in `fields[]` denetimi için gate'e verdiği geçici DDL dosyasının içeriği."""
        yakala = {}

        def sahte(_task, yol, *_a, **_k):
            yakala["ddl"] = Path(yol).read_text(encoding="utf-8")
            return self.rv.ReviewerResult(verdict="BLOCKER", blocker_count=1, skip_reason="test_yakalama")

        with mock.patch.object(self.rv, "run_reviewer", side_effect=sahte):
            self.comp.adt_struct_create(name, fields, description, "ZAXET_PKG", TR)
        return yakala.get("ddl")

    def test_B7b_gate_ddl_yazilan_ddl_ile_ayni(self):
        vakalar = {
            "düz alanlar": ([{"name": "A", "type": "ZAXET_E_OK"}, {"name": "B", "type": "char10"}], "Test yapısı"),
            "alan açıklamasında -- ve /* */ (satır sonu yok)": (
                [{"name": "A", "type": "ZAXET_E_OK", "description": "x -- /* not */"}], "Test yapısı"),
            "yapı açıklamasında tırnak": ([{"name": "A", "type": "dec15_2", "description": "tutar"}], "Ali'nin test yapısı"),
        }
        for ad, (fields, aciklama) in vakalar.items():
            gate, yazilan = self._gate_ddl("ZAXET_S_DEMO", fields, aciklama), self._yazilan_ddl("ZAXET_S_DEMO", fields, aciklama)
            ok = bool(yazilan) and gate == yazilan
            self.kaydet(f"b {ad}: gate'in DDL'i = create_structure'ın PUT ettiği DDL", "aynı metin",
                        f"gate={gate!r} · yazılan={yazilan!r}"[:300], ok)

    # Pin (tur 3): satır sonu İÇERMEYEN açıklamanın PUT DDL'i HEAD c9b5538 ile bayt bayt aynı kalır. Beklenen metinler HEAD'in
    # `sap_adt_lib.create_structure`'ı ağsız taslak istemciyle koşturularak üretildi (git archive c9b5538 → head_ddl.py;
    # sha256 d2d9e8f00583acf4… 161 bayt · 3bbc55c188fb9040… 220 bayt).
    HEAD_PUT_DDL = {
        "aciklamasiz": ([{"name": "A", "type": "ZAXET_E_OK"}, {"name": "B", "type": "char10"}], "Test yapısı",
                        "@EndUserText.label : 'Test yapısı'\n@AbapCatalog.enhancement.category : #NOT_EXTENSIBLE\ndefine structure zaxet_s_demo {\n  a : zaxet_e_ok;\n  b : abap.char(10);\n}"),
        "alan_aciklamali_tirnakli_etiket": (
            [{"name": "A", "type": "ZAXET_E_OK", "description": "Müşteri numarası -- /* not */"},
             {"name": "B", "type": "dec15_2", "description": "tutar"}], "Ali'nin test yapısı",
            "@EndUserText.label : 'Ali''nin test yapısı'\n@AbapCatalog.enhancement.category : #NOT_EXTENSIBLE\ndefine structure zaxet_s_demo {\n  // Müşteri numarası -- /* not */\n  a : zaxet_e_ok;\n  // tutar\n  b : abap.dec(15,2);\n}"),
    }

    def test_B7g_pin_satir_sonsuz_aciklama_put_ddl_head_ile_bayt_bayt(self):
        for ad, (fields, aciklama, beklenen) in self.HEAD_PUT_DDL.items():
            yazilan = self._yazilan_ddl("ZAXET_S_DEMO", fields, aciklama)
            ok = yazilan is not None and yazilan.encode("utf-8") == beklenen.encode("utf-8")
            self.kaydet(f"g pin {ad}: PUT DDL = HEAD c9b5538 (bayt bayt)", "eşit", f"{yazilan!r}"[:200], ok)


class B4CikarimDaralmasi(unittest.TestCase):
    """B4: artefaktlı yolda aday kaçıyordu (aynı satırda anotasyon+alan · string içinde `/*` · bölünmüş alan)."""

    def test_B4_kacan_adaylar(self):
        from utils.ddic_dtel import dtel_adaylari
        vakalar = {
            "aynı satırda anotasyon + alan": (
                "define structure s {\n  @Semantics.amount.currencyCode : 's.waers' tutar : zaxet_e_amt;\n"
                "  @Semantics.currencyCode : true waers : zaxet_e_cuky;\n}\n", ["ZAXET_E_AMT", "ZAXET_E_CUKY"]),
            "string içinde /*": (
                "@EndUserText.label : 'x /* y'\ndefine structure s {\n  a : zaxet_e_s1;\n}\n/* sonra */\n", ["ZAXET_E_S1"]),
            "string içinde //": (
                "@EndUserText.label : 'a // b'\ndefine structure s {\n  a : zaxet_e_after;\n}\n", ["ZAXET_E_AFTER"]),
            "iki satıra bölünmüş alan": (
                "define structure s {\n  a :\n    zaxet_e_ml;\n  b\n  : zaxet_e_ml2;\n}\n", ["ZAXET_E_ML", "ZAXET_E_ML2"]),
            "tek satırda iki alan": ("define structure s { a : zaxet_e_1; b : zaxet_e_2; }", ["ZAXET_E_1", "ZAXET_E_2"]),
            "KONTROL nesne değerli anotasyon alan sayılmaz": (
                "define structure s {\n  @Anno.nesne : { hedef : zaxet_e_anno }\n  a : zaxet_e_gercek;\n}\n", ["ZAXET_E_GERCEK"]),
            "KONTROL yorum/etiket/include/std hariç": (
                "@EndUserText.label : 'etiket zaxet_e_etiket'\ndefine structure s {\n  // x : zaxet_e_yorum;\n"
                "  /* y : zaxet_e_blok; */\n  include zaxet_s_inc;\n  key mandt : mandt not null;\n  a : abap.char(3);\n"
                "  b : zaxet_e_ok; // kuyruk zaxet_e_kuyruk\n}\n", ["ZAXET_E_OK"]),
        }
        for ad, (ddl, beklenen) in vakalar.items():
            g = dtel_adaylari(ddl)
            H.kaydet(f"B4 {ad}", beklenen, g, g == beklenen)
            self.assertEqual(g, beklenen, ad)


if __name__ == "__main__":
    unittest.main()
