# -*- coding: utf-8 -*-
"""Z128 (2026-09-25): `adt_pretty_print` — SAP Pretty Printer ile biçimle, YEREL dosyaya yaz, SAP'yi DEĞİŞTİRME.

HTTP taklidi: GERÇEK `SAPADTClient` (`lib/sap_adt_lib.py`) sahte bir oturumla kurulur ⇒ kütüphanenin kendi
`get_object_source` ve `pretty_print` gövdeleri koşar; ağa giden HER istek (yöntem + yol + gövde) oturumda
kaydedilir. Örnek adlar jeneriktir (ZCL_ZSD001_*). SAP'nin biçimleme ucunun gerçek yanıt biçimi canlı
DOĞRULANMADI — testler aracın kütüphane uçlarını doğru çağırdığını ve yan etkisizliğini kanıtlar.

Negatif kilit (`test_08_yazma_yok_*`): araç SAP'ye yazan bir yola (lock/PUT/aktivasyon, herhangi bir yazma sınıfı
araç, pull kaydı) girerse test kırılır — HTTP katmanında yöntem/yol allowlist'i + yazma araçlarına casus.
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
LIB = H.SCRIPTS / "sapadt" / "lib"
for _p in (H.SCRIPTS, LIB):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import sapadt  # noqa: E402,F401  (lib yolunu hazırlar)
from sap_adt_lib import SAPADTClient  # noqa: E402

SAHTE_HOST = "sahte-sap-pp.example"
PP_YOL = "/sap/bc/adt/abapsource/prettyprinter"
SINIF = "ZCL_ZSD001_DEMO"
KAYNAK = ("class zcl_zsd001_demo definition public create public.\n"
          "  public section.\n    methods run.\nendclass.\n"
          "class zcl_zsd001_demo implementation.\n  method run.\n"
          "data lv_x type i.\nlv_x = 1.\n  endmethod.\nendclass.\n")
BICIMLI_CRLF = ("CLASS zcl_zsd001_demo DEFINITION PUBLIC CREATE PUBLIC.\r\n"
                "  PUBLIC SECTION.\r\n    METHODS run.\r\nENDCLASS.\r\n"
                "CLASS zcl_zsd001_demo IMPLEMENTATION.\r\n  METHOD run.\r\n"
                "    DATA lv_x TYPE i.\r\n    lv_x = 1.\r\n  ENDMETHOD.\r\nENDCLASS.\r\n")
BICIMLI = BICIMLI_CRLF.replace("\r\n", "\n")


class _Yanit:
    def __init__(self, status_code=200, text="", headers=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}
        self.content = text.encode("utf-8")


class _Oturum:
    """Her HTTP isteğini kaydeder. Yönlendirici (method, yol) → _Yanit."""

    verify = False

    def __init__(self, url, yonlendir):
        self.url, self.yonlendir, self.istekler = url, yonlendir, []

    def _k(self, method, url, headers=None, params=None, data=None, **_kw):
        yol = url[len(self.url):] if url.startswith(self.url) else url
        self.istekler.append({"method": method.upper(), "path": yol, "params": dict(params or {}),
                              "data": data, "headers": dict(headers or {})})
        return self.yonlendir(method.upper(), yol, data)

    def get(self, url, headers=None, params=None, timeout=None, **kw):
        return self._k("GET", url, headers, params)

    def post(self, url, data=None, headers=None, params=None, timeout=None, **kw):
        return self._k("POST", url, headers, params, data)

    def put(self, url, data=None, headers=None, params=None, timeout=None, **kw):
        return self._k("PUT", url, headers, params, data)

    def delete(self, url, headers=None, params=None, timeout=None, **kw):
        return self._k("DELETE", url, headers, params)

    def request(self, method, url, headers=None, timeout=None, **kw):
        return self._k(method, url, headers, kw.get("params"), kw.get("data"))


def _gercek_istemci(yonlendir):
    c = SAPADTClient.__new__(SAPADTClient)
    c.url = f"https://{SAHTE_HOST}:44300"
    c.client, c.user, c.password, c.language = "100", H.KULLANICI, H.PAROLA, "TR"
    c.csrf_token = ""
    c.timeout_default = c.timeout_short = 30
    c.debug_enabled = False
    c.session = _Oturum(c.url, yonlendir)
    c._update_cookies = lambda r: None
    c._get_headers = lambda *a, **kw: {"Accept": (a[0] if a else "x"), "sap-client": "100",
                                       **({"X-CSRF-Token": c.csrf_token} if c.csrf_token else {})}

    def _fetch(force_refresh=False):
        c.csrf_token = "SAHTE-CSRF-PP"
        return c.csrf_token
    c.fetch_csrf_token = _fetch
    return c


class _Istemci:
    def __init__(self, adt):
        self.adt_client = adt


def _yon(kaynak=KAYNAK, bicimli=BICIMLI_CRLF, get_durum=200, pp_durum=200):
    def yon(method, yol, data):
        if method == "GET" and (yol.endswith("/source/main") or "/includes/" in yol):
            return _Yanit(get_durum, kaynak if get_durum == 200 else f"hata {SAHTE_HOST}")
        if method == "POST" and yol == PP_YOL:
            return _Yanit(pp_durum, bicimli if pp_durum == 200 else f"<exc>sunucu {SAHTE_HOST}</exc>")
        return _Yanit(599, "beklenmeyen istek")
    return yon


class PrettyPrint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="axet_pp_"))
        cls._eski_env = {k: v for k, v in os.environ.items() if k.startswith("ADT_") or k == "AXET_SAP_PROJECT_DIR"}
        for k in list(cls._eski_env):
            os.environ.pop(k, None)
        from sapadt import gate
        from sapadt._app import REGISTRY, load_all_tools
        from sapadt.tools import atom, diag
        import sap_adt_cli
        load_all_tools()
        cls.gate, cls.REG, cls.atom, cls.diag, cls.cli = gate, REGISTRY, atom, diag, sap_adt_cli
        cls._eski_client = atom._get_client
        cls._n = 0

    @classmethod
    def tearDownClass(cls):
        cls.atom._get_client = cls._eski_client
        os.environ.pop("AXET_SAP_PROJECT_DIR", None)
        os.environ.update(cls._eski_env)
        shutil.rmtree(cls.root, ignore_errors=True)

    def setUp(self):
        type(self)._n += 1
        self.p = H.make_project(self.root, f"p{self._n}")
        os.environ["AXET_SAP_PROJECT_DIR"] = str(self.p)

    def kur(self, **kw):
        adt = _gercek_istemci(_yon(**kw))
        self.atom._get_client = lambda: _Istemci(adt)
        return adt

    def kaydet(self, ad, beklenen, gercek, ok):
        H.kaydet(f"PP {ad}", beklenen, str(gercek)[:160], ok)
        self.assertTrue(ok, f"{ad}: {gercek}")

    def dosyalar(self):
        return sorted(p.relative_to(self.p).as_posix() for p in self.p.rglob("*") if p.is_file())

    # ── mutlu yol ────────────────────────────────────────────────────────────────────────
    def test_01_sinif_yerel_dosyaya(self):
        adt = self.kur()
        r = self.diag.adt_pretty_print(SINIF, "class", output_path="out/zcl_zsd001_demo.clas.abap")
        ist = [(i["method"], i["path"]) for i in adt.session.istekler]
        hedef = self.p / "out" / "zcl_zsd001_demo.clas.abap"
        post = [i for i in adt.session.istekler if i["method"] == "POST"]
        ok = (r.get("ok") is True and r["written"] is True and r["output_path"] == "out/zcl_zsd001_demo.clas.abap"
              and r["server_modified"] is False and r["changed"] is True and r["changed_line_count"] > 0
              and "source" not in r and hedef.read_bytes() == BICIMLI.encode("utf-8")
              and ist == [("GET", "/sap/bc/adt/oo/classes/zcl_zsd001_demo/source/main"), ("POST", PP_YOL)]
              and post[0]["data"] == KAYNAK.encode("utf-8") and post[0]["params"] == {})
        self.kaydet("01 class: GET kaynak → POST prettyprinter → yerel dosya (LF), başka istek yok",
                    "ok · written · 2 istek", ist, ok)

    def test_02_yolsuz_metin_yanitta(self):
        self.kur()
        once = self.dosyalar()
        r = self.diag.adt_pretty_print(SINIF)
        ok = (r.get("ok") is True and r["source"] == BICIMLI and r["written"] is False and r["output_path"] is None
              and self.dosyalar() == once and "SAP'de hiçbir şey değişmedi" in r["notice"])
        self.kaydet("02 output_path yok → metin yanıtta, diske HİÇ dosya yazılmaz", "source · 0 dosya", r.get("written"), ok)

    def test_03_degisiklik_yoksa_changed_false(self):
        self.kur(bicimli=KAYNAK)
        r = self.diag.adt_pretty_print(SINIF)
        ok = r.get("ok") is True and r["changed"] is False and r["changed_line_count"] == 0 and r["diff_preview"] == ""
        self.kaydet("03 biçimleyici fark üretmedi → changed:false, 0 satır", "false · 0", r.get("changed"), ok)

    # ── tipler ───────────────────────────────────────────────────────────────────────────
    def test_04_desteklenen_tipler_url(self):
        beklenen = {("interface", "ZIF_ZSD001_X"): "/sap/bc/adt/oo/interfaces/zif_zsd001_x/source/main",
                    ("program", "ZSD001_R_X"): "/sap/bc/adt/programs/programs/zsd001_r_x/source/main",
                    ("prog", "ZSD001_R_X"): "/sap/bc/adt/programs/programs/zsd001_r_x/source/main",
                    ("include", "ZSD001_I_X"): "/sap/bc/adt/programs/includes/zsd001_i_x/source/main",
                    ("ccau", SINIF): "/sap/bc/adt/oo/classes/zcl_zsd001_demo/includes/testclasses",
                    ("ccimp", SINIF): "/sap/bc/adt/oo/classes/zcl_zsd001_demo/includes/implementations",
                    ("ccdef", SINIF): "/sap/bc/adt/oo/classes/zcl_zsd001_demo/includes/definitions",
                    ("ccmac", SINIF): "/sap/bc/adt/oo/classes/zcl_zsd001_demo/includes/macros"}
        gercek = {}
        for (tip, ad), yol in beklenen.items():
            adt = self.kur()
            r = self.diag.adt_pretty_print(ad, tip)
            gercek[(tip, ad)] = (r.get("ok"), [i["path"] for i in adt.session.istekler])
        ok = all(gercek[k] == (True, [v, PP_YOL]) for k, v in beklenen.items())
        self.kaydet("04 interface/program/include + ccau/ccimp/ccdef/ccmac doğru kaynak ucu", "8/8", gercek, ok)

    def test_05_desteklenmeyen_tip_aga_gitmez(self):
        sonuc = {}
        for tip in ("func", "ddls", "bdef", "dtel", "tabl", "fugr", "yok_boyle_tip"):
            adt = self.kur()
            r = self.diag.adt_pretty_print("ZSD001_X", tip)
            sonuc[tip] = (r.get("error"), len(adt.session.istekler))
        bos = self.diag.adt_pretty_print("  ", "class").get("error")
        ok = all(v == ("unsupported_type", 0) for v in sonuc.values()) and bos == "invalid_argument"
        self.kaydet("05 func/ddls/bdef/dtel/tabl/fugr/bilinmeyen → unsupported_type, 0 istek", "unsupported · 0", sonuc, ok)

    # ── çıktı yolu korumaları ────────────────────────────────────────────────────────────
    def test_06_cikti_yolu_korumalari(self):
        (self.p / "var.abap").write_text("ESKI\n", encoding="utf-8")
        disari = str(Path(self.root) / "disari.abap")
        vakalar = {"../kardes.abap": "invalid_argument", disari: "invalid_argument",
                   ".conn_adt": "invalid_argument", "sap-project.json": "invalid_argument",
                   "notlar/x.txt": "invalid_argument", ".axet-code/x.abap": "invalid_argument",
                   ".AXET-CODE/y.abap": "invalid_argument", "": "invalid_argument",
                   "var.abap": "output_exists"}
        sonuc = {}
        for yol, kod in vakalar.items():
            adt = self.kur()
            r = self.diag.adt_pretty_print(SINIF, output_path=yol)
            sonuc[yol] = (r.get("error"), len(adt.session.istekler))
        conn_ayni = (self.p / ".conn_adt").read_text(encoding="utf-8").startswith("# test fixture")
        ok = (all(sonuc[y] == (k, 0) for y, k in vakalar.items()) and conn_ayni
              and (self.p / "var.abap").read_text(encoding="utf-8") == "ESKI\n"
              and not (self.root / "disari.abap").exists())
        self.kaydet("06 kök dışı/.abap dışı/.axet-code/var olan dosya → red, SAP'ye 0 istek", "9/9 red", sonuc, ok)

    def test_07_overwrite_true_ezer(self):
        (self.p / "var.abap").write_text("ESKI\n", encoding="utf-8")
        self.kur()
        r = self.diag.adt_pretty_print(SINIF, output_path="var.abap", overwrite=True)
        ok = (r.get("ok") is True and r["written"] is True
              and (self.p / "var.abap").read_bytes() == BICIMLI.encode("utf-8")
              and not (self.p / "var.abap.tmp").exists())
        self.kaydet("07 overwrite=true → var olan .abap yeni metinle değişir, .tmp kalmaz", "ok · yeni içerik", r.get("written"), ok)

    # ── NEGATİF KİLİT: SAP'ye yazma yok ──────────────────────────────────────────────────
    def test_08_yazma_yok_http_ve_arac_casusu(self):
        """Mutasyon kilidi: araç lock/PUT/aktivasyon ya da herhangi bir YAZMA sınıfı aracı çağırırsa kırılır."""
        adt = self.kur()
        casus: list = []
        yazma = [ad for ad in self.REG if self.gate.tool_class(ad, {}) == "write"]
        for ad in yazma:
            spec = self.REG[ad]
            mod = sys.modules.get(spec.module)
            orj_fn, orj_mod = spec.fn, getattr(mod, ad, None)

            def sahte(*a, _ad=ad, **kw):
                casus.append(_ad)
                return {"ok": False, "error": "test_casus", "message": _ad}
            spec.fn = sahte
            self.addCleanup(setattr, spec, "fn", orj_fn)
            if mod is not None and orj_mod is not None:
                setattr(mod, ad, sahte)
                self.addCleanup(setattr, mod, ad, orj_mod)
        pull_cagri: list = []
        from sapadt import pull_state
        for fn_ad in ("kaydet", "kaydet_yok"):
            if hasattr(pull_state, fn_ad):
                orj = getattr(pull_state, fn_ad)
                setattr(pull_state, fn_ad, lambda *a, _n=fn_ad, **kw: pull_cagri.append(_n))
                self.addCleanup(setattr, pull_state, fn_ad, orj)
        r = self.diag.adt_pretty_print(SINIF, "class", output_path="z.abap")
        yontemler = {i["method"] for i in adt.session.istekler}
        postlar = {i["path"] for i in adt.session.istekler if i["method"] != "GET"}
        durum = {"ok": r.get("ok"), "yontemler": sorted(yontemler), "post_yollari": sorted(postlar),
                 "yazma_araci": casus, "pull_state": pull_cagri,
                 "pull_dosyasi": (self.p / ".axet-code" / "sap-pull-state.json").exists(),
                 "yazma_logu": (self.p / ".axet-code" / "sap-write-log.jsonl").exists()}
        ok = (r.get("ok") is True and yontemler <= {"GET", "POST"} and postlar == {PP_YOL} and not casus
              and not pull_cagri and not durum["pull_dosyasi"] and not durum["yazma_logu"] and len(yazma) >= 10)
        self.kaydet("08 NEGATİF: yalnız GET + prettyprinter POST; yazma aracı/pull kaydı/yazma logu YOK",
                    "GET,POST · 0 yazma", durum, ok)

    def test_09_hata_durumlari_ayri_dosya_yok(self):
        durum = {}
        for ad, kw in (("get404", {"get_durum": 404}), ("get500", {"get_durum": 500}),
                       ("pp500", {"pp_durum": 500}), ("pp_bos", {"bicimli": "  \r\n"}), ("kaynak_bos", {"kaynak": ""})):
            self.kur(**kw)
            r = self.diag.adt_pretty_print(SINIF, output_path=f"{ad}.abap")
            durum[ad] = (r.get("ok"), r.get("error"), (self.p / f"{ad}.abap").exists(), SAHTE_HOST in json.dumps(r))
        ok = (durum["get404"] == (False, "not_found", False, False)
              and durum["get500"][:3] == (False, "sap_error", False) and durum["get500"][3] is False
              and durum["pp500"] == (False, "pretty_print_failed", False, False)
              and durum["pp_bos"] == (False, "pretty_print_empty", False, False)
              and durum["kaynak_bos"] == (False, "source_empty", False, False))
        self.kaydet("09 404/500/biçimleyici hata/boş biçim/boş kaynak AYRI kod, dosya YOK, host maskeli",
                    "5 ayrı kod · 0 dosya", durum, ok)

    # ── CLI hattı: okuma sınıfı, --sap-write istemez ─────────────────────────────────────
    def test_10_cli_okuma_sinifi(self):
        self.kur()
        payload, kod = self.cli.calistir("adt_pretty_print", {"name": SINIF, "output_path": "cli/x.abap"},
                                         self.p, tls_uyarisi=False)
        red_payload, red_kod = self.cli.calistir("adt_pretty_print", {"name": "ZSD001_FM", "object_type": "func"},
                                                 self.p, tls_uyarisi=False)
        ok = (self.gate.tool_class("adt_pretty_print", {}) == "read" and "adt_pretty_print" in self.gate.READ_TOOLS
              and kod == 0 and payload["ok"] is True and payload["class"] == "read"
              and payload["result"]["written"] is True and (self.p / "cli" / "x.abap").is_file()
              and not (self.p / ".axet-code" / "sap-write-log.jsonl").exists()
              and red_kod == 3 and red_payload["error"]["code"] == "unsupported_type")
        self.kaydet("10 CLI: read sınıfı, --sap-write'sız çıkış 0, yazma logu yok; func → çıkış 3",
                    "read · 0 · 3", (payload.get("class"), kod, red_kod), ok)


if __name__ == "__main__":
    unittest.main()
