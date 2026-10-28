# -*- coding: utf-8 -*-
"""Z195 ①② (2026-10-19) — `adt_syntax_check` salt-okur checkrun · `adt_get_method` tek-metot okuma.

Ölçülen sınıf (①): eski `adt_syntax_check` alt katmanı `syntax_check_via_activation` idi; SAP
`preauditRequested=true`'yu onurlandırmadığı için bekleyen TEMİZ sürümü AKTİVE EDİYORDU ⇒ araç yazma
sınıfındaydı. Yeni yol `POST /sap/bc/adt/checkruns?reporters=abapCheckRun` (`version=inactive`).

Kapanış ölçütü (kulvar brifi): sahte sunucuda araç YALNIZ checkruns'a POST eder · kaynak PUT'u 0 ·
aktivasyon 0 · araç okuma kapısında (`gate.tool_class == "read"`).

Yanıt gövdeleri `fixtures/checkrun_sozdizimi/` altındadır: kaynak çekirdeğin canlı DEV ölçümünden
(4 tip: sınıf · FM · tablo · CDS) jenerik `ZSD001_*` adlarıyla. aXet'te canlı SAP ölçümü YOK.

İkinci eksen (②): `adt_get_method` sınıfın ana kaynağını GET ile okur, `METHOD <ad>.` .. `ENDMETHOD.`
bloğunu çıkarır. Belirsiz (birden çok blok) ve kapanmamış blok ÖLÇÜLEMEDİ'dir (found: null).
"""
from __future__ import annotations

import http.server
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path

import _helpers as H

sys.dont_write_bytecode = True
LIB = H.SCRIPTS / "sapadt" / "lib"
for _p in (H.SCRIPTS, LIB):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import sapadt  # noqa: E402,F401  (lib yolunu hazırlar)
import sap_adt_lib as L  # noqa: E402
from sap_adt_lib import SAPADTClient  # noqa: E402
from sap_client import SAPClient  # noqa: E402
from sapadt import gate  # noqa: E402

FX = H.TESTS_DIR / "fixtures" / "checkrun_sozdizimi"
SINIF = "ZSD001_CL_ORNEK"
SINIF_URI = "/sap/bc/adt/oo/classes/zsd001_cl_ornek"
CR_YOL = "/sap/bc/adt/checkruns?reporters=abapCheckRun"


def fx(ad: str) -> str:
    return (FX / ad).read_text(encoding="utf-8")


def _rapor(status="processed", reporter="abapCheckRun", uri=SINIF_URI, mesajlar=""):
    govde = ('<chkrun:checkReport chkrun:reporter="%s" chkrun:triggeringUri="%s" chkrun:status="%s" '
             'chkrun:statusText="t"' % (reporter, uri, status))
    govde += ('><chkrun:checkMessageList>%s</chkrun:checkMessageList></chkrun:checkReport>' % mesajlar
              if mesajlar else "/>")
    return ('<?xml version="1.0" encoding="utf-8"?><chkrun:checkRunReports '
            'xmlns:chkrun="http://www.sap.com/adt/checkrun">%s</chkrun:checkRunReports>' % govde)


def _mesaj(tip="E", satir=3, kolon=5, metin="m"):
    return ('<chkrun:checkMessage chkrun:uri="%s/source/main#start=%d,%d" chkrun:type="%s" '
            'chkrun:shortText="%s"/>' % (SINIF_URI, satir, kolon, tip, metin))


class _Kayit(unittest.TestCase):
    def kaydet(self, ad, beklenen, gercek, ok):
        H.kaydet(f"Z195 {ad}", beklenen, str(gercek)[:160], ok)
        self.assertTrue(ok, f"{ad}: {gercek}")


# ══════════════════════════════════════════════════════════════════════════════════════════════
# A — ayrıştırıcı (`checkrun_ayristir`): canlı biçimli gövdeler + belirsiz vektörler
# ══════════════════════════════════════════════════════════════════════════════════════════════
class Ayristirici(_Kayit):
    def test_A1_canli_sinif_hatali(self):
        s = L.checkrun_ayristir(fx("cls_hatali_inactive.resp.xml"), SINIF_URI)
        h = s["hatalar"]
        self.kaydet("A1 sınıf hatalı (canlı biçim)", "hatali · 1 E · 21/25",
                    (s["hukum"], [(e["line"], e["column"]) for e in h]),
                    s["hukum"] == "hatali" and [(e["line"], e["column"]) for e in h] == [(21, 25)]
                    and "LV_TANIMSIZ_DEGISKEN" in h[0]["message"])

    def test_A2_canli_sinif_temiz(self):
        s = L.checkrun_ayristir(fx("cls_temiz_inactive.resp.xml"), SINIF_URI)
        self.kaydet("A2 sınıf temiz (canlı biçim)", "temiz · 0 mesaj", (s["hukum"], s["hatalar"], s["uyarilar"]),
                    s["hukum"] == "temiz" and not s["hatalar"] and not s["uyarilar"])

    def test_A3_canli_notprocessed_temiz_degil(self):
        s = L.checkrun_ayristir(fx("tab_temiz_inactive.resp.xml"), "/sap/bc/adt/ddic/tables/zsd001_t_ornek")
        self.kaydet("A3 notProcessed + 0 mesaj", "OLCULEMEDI (temiz DEĞİL)", (s["hukum"], s["sebep"]),
                    s["hukum"] == "OLCULEMEDI" and s["sebep"].startswith("status=notProcessed"))

    def test_A4_canli_diger_tipler_hatali(self):
        vakalar = (("fm_hatali_inactive.resp.xml",
                    "/sap/bc/adt/functions/groups/zsd001_fg_ornek/fmodules/zsd001_fm_ornek", (10, 23)),
                   ("tab_hatali_inactive.resp.xml", "/sap/bc/adt/ddic/tables/zsd001_t_ornek", (10, 2)),
                   ("cds_hatali_inactive.resp.xml", "/sap/bc/adt/ddic/ddl/sources/zsd001_i_ornek", (8, 6)))
        for dosya, uri, konum in vakalar:
            s = L.checkrun_ayristir(fx(dosya), uri)
            ilk = (s["hatalar"][0]["line"], s["hatalar"][0]["column"]) if s["hatalar"] else None
            self.kaydet(f"A4 {dosya}", f"hatali · ilk {konum}", (s["hukum"], ilk),
                        s["hukum"] == "hatali" and ilk == konum)

    def test_A5_belirsiz_vektorler(self):
        vakalar = (
            ("boş gövde", "", None, "bos_govde"),
            ("bozuk xml", "<<< x", None, "bozuk_xml:"),
            ("rapor yok", '<chkrun:checkRunReports xmlns:chkrun="http://www.sap.com/adt/checkrun"/>',
             None, "rapor_yok"),
            ("başka reporter", _rapor(reporter="baskaReporter"), None, "reporter_yok:"),
            ("obje raporlanmadı", _rapor(uri="/sap/bc/adt/oo/classes/zsd001_cl_baska"), SINIF_URI,
             "obje_raporlanmadi"),
            ("tanınmayan mesaj tipi", _rapor(mesajlar=_mesaj(tip="X")), SINIF_URI, "taninmayan_mesaj_tipi:X"),
        )
        for ad, govde, beklenen_uri, sebep in vakalar:
            s = L.checkrun_ayristir(govde, beklenen_uri)
            self.kaydet(f"A5 {ad}", f"OLCULEMEDI · {sebep}", (s["hukum"], s["sebep"], s["hatalar"]),
                        s["hukum"] == "OLCULEMEDI" and s["sebep"].startswith(sebep) and not s["hatalar"])

    def test_A6_uyari_hata_degil_ve_kapsam_beyani(self):
        s = L.checkrun_ayristir(_rapor(mesajlar=_mesaj(tip="W")), SINIF_URI)
        self.kaydet("A6 yalnız W → temiz + 1 uyarı · kapsam beyanı", "temiz · 1 W · kapsam var",
                    (s["hukum"], len(s["uyarilar"]), s["kapsam"].get("version")),
                    s["hukum"] == "temiz" and len(s["uyarilar"]) == 1 and s["kapsam"]["version"] == "inactive"
                    and "ATC" in s["kapsam"]["bakilan"])

    def test_A7_istek_govdesi_canli_bicimle_ayni(self):
        g = L.checkrun_govdesi(SINIF_URI + "/source/main", "inactive")
        self.kaydet("A7 istek gövdesi = canlı istek (source/main kırpılır)", "bayt-eşit",
                    g[:90], g == fx("cls_hatali_inactive.req.xml").strip())
        kacis = L.checkrun_govdesi('/sap/bc/adt/x/a"b&c', "inactive")
        self.kaydet("A7b öznitelik kaçışı", '&quot; ve &amp;', kacis[-80:],
                    'a&quot;b&amp;c' in kacis and 'a"b' not in kacis)


# ══════════════════════════════════════════════════════════════════════════════════════════════
# B — `SAPADTClient.check_run` + MCP aracı, GERÇEK HTTP katmanı (yerel sahte sunucu)
# ══════════════════════════════════════════════════════════════════════════════════════════════
class _Sunucu:
    """Tüm metotları (GET/POST/PUT/DELETE) yol başına kaydeder; yol başına yanıt planı."""

    def __init__(self):
        self.plan: dict[str, tuple] = {}
        self.istekler: list[tuple] = []
        self.kilit = threading.Lock()
        dis = self

        class _H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):  # noqa: D401
                pass

            def _isle(self):
                n = int(self.headers.get("Content-Length") or 0)
                govde = self.rfile.read(n).decode("utf-8", "replace") if n else ""
                with dis.kilit:
                    dis.istekler.append((self.command, self.path, govde))
                    kod, metin = dis.plan.get((self.command, self.path), (200, "ok"))
                veri = metin.encode("utf-8")
                self.send_response(kod)
                self.send_header("Content-Type", "application/xml; charset=utf-8")
                self.send_header("Content-Length", str(len(veri)))
                self.end_headers()
                self.wfile.write(veri)

            do_GET = do_POST = do_PUT = do_DELETE = _isle

        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _H)
        self.srv.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def kapat(self):
        self.srv.shutdown()
        self.srv.server_close()


def _adt_istemcisi(url: str) -> SAPADTClient:
    """Gerçek `_build_session` + gerçek `_request_with_csrf_retry`; CSRF/kimlik sahte."""
    c = SAPADTClient.__new__(SAPADTClient)
    c.url = url
    c.client = "000"
    c.language = "TR"
    c.user = "TESTUSER_A"
    c._auth_provider = None
    c._get_auth_headers = lambda: {}
    c.debug_enabled = False
    c.timeout_default = 5
    c.timeout_short = 5
    c.csrf_token = "T"
    c._update_cookies = lambda r: None
    c._invalidate_csrf_cache = lambda: None

    def _fetch(force_refresh=False):
        c.csrf_token = "T"
    c.fetch_csrf_token = _fetch
    c._get_headers = lambda accept_type=None, content_type=None: {"Accept": accept_type or "x",
                                                                  "X-CSRF-Token": c.csrf_token or ""}
    c.session = c._build_session()
    return c


class GercekHttp(_Kayit):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="axet_checkrun_"))
        cls.dev = H.make_project(cls.root, "dev")
        cls._eski_env = {k: os.environ.get(k) for k in ("AXET_SAP_PROJECT_DIR", "ADT_SAP_TIER")}
        os.environ.pop("ADT_SAP_TIER", None)
        os.environ["AXET_SAP_PROJECT_DIR"] = str(cls.dev)
        from sapadt.tools import atom, diag, query
        cls.atom, cls.query, cls.diag = atom, query, diag
        cls._eski_client = atom._get_client

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
        self.sunucu = _Sunucu()
        self.adt = _adt_istemcisi(self.sunucu.url)
        s = SAPClient.__new__(SAPClient)
        s.adt_client = self.adt
        s.debug_enabled = False
        self.atom._get_client = lambda: s

    def tearDown(self):
        try:
            self.adt.session.close()
        except Exception:  # noqa: BLE001
            pass
        self.sunucu.kapat()

    def _sayim(self):
        yollar = [(m, p) for m, p, _ in self.sunucu.istekler]
        return {"checkrun_post": yollar.count(("POST", CR_YOL)),
                "put": sum(1 for m, _ in yollar if m == "PUT"),
                "aktivasyon": sum(1 for _, p in yollar if "activation" in p),
                "lock": sum(1 for _, p in yollar if "_action=LOCK" in p),
                "toplam": len(yollar)}

    # ── kapanış ölçütü ──
    def test_B1_arac_yalniz_checkrun_post(self):
        self.sunucu.plan[("POST", CR_YOL)] = (200, fx("cls_hatali_inactive.resp.xml"))
        r = self.query.adt_syntax_check(SINIF, "class")
        say = self._sayim()
        govde = self.sunucu.istekler[0][2] if self.sunucu.istekler else ""
        self.kaydet("B1 KAPANIŞ: yalnız checkruns POST · PUT 0 · aktivasyon 0 · kilit 0",
                    "1/0/0/0 · toplam 1", say,
                    say == {"checkrun_post": 1, "put": 0, "aktivasyon": 0, "lock": 0, "toplam": 1})
        self.kaydet("B1b istek gövdesi version=inactive + kök URI", 'chkrun:version="inactive"', govde[-120:],
                    'chkrun:version="inactive"' in govde and 'adtcore:uri="%s"' % SINIF_URI in govde)
        self.kaydet("B1c araç hükmü", "ok True · valid False · satır 21 · source checkrun",
                    (r.get("ok"), r.get("valid"), [e.get("line") for e in r.get("errors") or []], r.get("source")),
                    r.get("ok") is True and r.get("valid") is False
                    and [e.get("line") for e in r.get("errors")] == [21] and r.get("source") == "checkrun"
                    and "ATC" in (r.get("scope") or {}).get("bakilan", ""))

    def test_B2_arac_temiz(self):
        self.sunucu.plan[("POST", CR_YOL)] = (200, fx("cls_temiz_inactive.resp.xml"))
        r = self.query.adt_syntax_check(SINIF, "class")
        self.kaydet("B2 temiz gövde", "ok True · valid True", (r.get("ok"), r.get("valid"), self._sayim()["toplam"]),
                    r.get("ok") is True and r.get("valid") is True and self._sayim()["toplam"] == 1)

    def test_B3_arac_notprocessed_belirsiz(self):
        self.sunucu.plan[("POST", CR_YOL)] = (200, _rapor(status="notProcessed"))
        r = self.query.adt_syntax_check(SINIF, "class")
        self.kaydet("B3 notProcessed", "ok False · sozdizimi_belirsiz · valid None",
                    (r.get("ok"), r.get("error"), r.get("valid"), r.get("valid_reason")),
                    r.get("ok") is False and r.get("error") == "sozdizimi_belirsiz" and r.get("valid") is None
                    and "notProcessed" in (r.get("valid_reason") or ""))

    def test_B4_http_500_belirsiz_tek_istek(self):
        self.sunucu.plan[("POST", CR_YOL)] = (500, "Internal Server Error")
        s = self.adt.check_run(SINIF_URI)
        self.kaydet("B4 HTTP 500", "OLCULEMEDI · http_500 · temiz değil",
                    (s["hukum"], s["sebep"], s.get("http_status")),
                    s["hukum"] == "OLCULEMEDI" and s["sebep"] == "http_500" and s.get("http_status") == 500)

    def test_B5_gecersiz_version_aga_gitmez(self):
        with self.assertRaises(L.SAPValidationError):
            self.adt.check_run(SINIF_URI, version="latest")
        self.kaydet("B5 geçersiz version → istisna, ağ yok", "0 istek", self._sayim()["toplam"],
                    self._sayim()["toplam"] == 0)

    def test_B6_istisna_belirsiz(self):
        self.adt._request_with_csrf_retry = lambda *a, **k: (_ for _ in ()).throw(ConnectionError("ag yok"))
        s = self.adt.check_run(SINIF_URI)
        self.kaydet("B6 ağ istisnası", "OLCULEMEDI · istisna:ConnectionError", (s["hukum"], s["sebep"]),
                    s["hukum"] == "OLCULEMEDI" and s["sebep"] == "istisna:ConnectionError")

    # ── ② adt_get_method ──
    _KAYNAK = "\n".join([
        "CLASS zsd001_cl_ornek DEFINITION PUBLIC.",
        "  PUBLIC SECTION.",
        "    METHODS hesapla.",
        "    METHODS yaz.",
        "ENDCLASS.",
        "CLASS zsd001_cl_ornek IMPLEMENTATION.",
        "  METHOD hesapla.",
        "    \" METHOD yaz. yorum içinde — eşleşmez",
        "    rv = 1.",
        "  ENDMETHOD.",
        "  METHOD yaz.",
        "    rv = 2.",
        "  ENDMETHOD.",
        "ENDCLASS.",
    ])
    _GM_YOL = SINIF_URI + "/source/main"

    def test_C1_get_method_bulundu_yalniz_get(self):
        self.sunucu.plan[("GET", self._GM_YOL)] = (200, self._KAYNAK)
        r = self.diag.adt_get_method(SINIF, "hesapla")
        say = self._sayim()
        self.kaydet("C1 metot bulundu · satır 7-10 · yalnız 1 GET",
                    "found · 7-10 · GET 1 · PUT/POST 0",
                    (r.get("found"), r.get("start_line"), r.get("end_line"), self.sunucu.istekler and
                     [m for m, _p, _g in self.sunucu.istekler]),
                    r.get("ok") is True and r.get("found") is True and (r["start_line"], r["end_line"]) == (7, 10)
                    and r["source"].splitlines()[-1].strip() == "ENDMETHOD." and "rv = 1." in r["source"]
                    and [m for m, _p, _g in self.sunucu.istekler] == ["GET"] and say["put"] == 0)

    def test_C2_get_method_yok(self):
        self.sunucu.plan[("GET", self._GM_YOL)] = (200, self._KAYNAK)
        r = self.diag.adt_get_method(SINIF, "olmayan")
        self.kaydet("C2 metot yok", "ok True · found False · kapsam beyanı", (r.get("ok"), r.get("found")),
                    r.get("ok") is True and r.get("found") is False and "include" in r.get("scope", ""))

    def test_C3_get_method_belirsiz(self):
        kaynak = self._KAYNAK + "\nCLASS lcl DEFINITION.\nENDCLASS.\nCLASS lcl IMPLEMENTATION.\n" \
                                "  METHOD hesapla.\n  ENDMETHOD.\nENDCLASS."
        self.sunucu.plan[("GET", self._GM_YOL)] = (200, kaynak)
        r = self.diag.adt_get_method(SINIF, "HESAPLA")
        self.kaydet("C3 iki blok", "ok False · belirsiz · found None · 2 eşleşme",
                    (r.get("ok"), r.get("error"), r.get("found"), len(r.get("matches") or [])),
                    r.get("ok") is False and r.get("error") == "belirsiz" and r.get("found") is None
                    and len(r["matches"]) == 2)

    def test_C4_get_method_kapanmamis(self):
        self.sunucu.plan[("GET", self._GM_YOL)] = (200, "CLASS x IMPLEMENTATION.\n  METHOD yaz.\n    rv = 2.\n")
        r = self.diag.adt_get_method(SINIF, "yaz")
        self.kaydet("C4 ENDMETHOD yok", "ok False · kapanmamis · found None", (r.get("ok"), r.get("error"), r.get("found")),
                    r.get("ok") is False and r.get("error") == "kapanmamis" and r.get("found") is None)

    def test_C5_get_method_bos_arguman_aga_gitmez(self):
        r1 = self.diag.adt_get_method("", "yaz")
        r2 = self.diag.adt_get_method(SINIF, "  ")
        self.kaydet("C5 boş name/method", "invalid_argument ×2 · 0 istek",
                    (r1.get("error"), r2.get("error"), self._sayim()["toplam"]),
                    r1.get("error") == r2.get("error") == "invalid_argument" and self._sayim()["toplam"] == 0)

    def test_C6_get_method_output_path(self):
        self.sunucu.plan[("GET", self._GM_YOL)] = (200, self._KAYNAK)
        hedef = "SOURCE_CODES/zsd001_hesapla.abap"
        r = self.diag.adt_get_method(SINIF, "hesapla", output_path=hedef)
        dosya = self.dev / hedef
        self.kaydet("C6 output_path yazıldı · source yanıtta yok · pull kaydı yok",
                    "written · dosya = blok · sap-pull-state.json yok",
                    (r.get("written"), r.get("output_path"), "source" in r),
                    r.get("ok") is True and r.get("written") is True and dosya.is_file()
                    and "rv = 1." in dosya.read_text(encoding="utf-8") and "source" not in r
                    and not any(self.dev.rglob("sap-pull-state.json")))
        r2 = self.diag.adt_get_method(SINIF, "hesapla", output_path=hedef)
        self.kaydet("C6b var olan dosya overwrite'sız", "output_exists · ağa gidilmez (GET sayısı 1)",
                    (r2.get("error"), self._sayim()["toplam"]),
                    r2.get("error") == "output_exists" and self._sayim()["toplam"] == 1)

    # Z213 (2026-10-28; kaynak çekirdek #362): sınır = ilk METHOD/ENDMETHOD DEYİMİ ⇒ tek satırlık metot artık DESTEKLENİR
    # (2026-10-19 temkinli sürümü burada `belirsiz` diyordu; komşunun gövdesi o sürümde de dönmüyordu, şimdi de dönmez).
    def test_C7_get_method_tek_satir_desteklenir_komsu_govdesi_donmez(self):
        kaynak = ("CLASS x IMPLEMENTATION.\n  METHOD a. ENDMETHOD.\n  METHOD b.\n    x = 1.\n  ENDMETHOD.\n"
                  "ENDCLASS.")
        self.sunucu.plan[("GET", self._GM_YOL)] = (200, kaynak)
        r = self.diag.adt_get_method(SINIF, "a")
        rb = self.diag.adt_get_method(SINIF, "b")
        self.kaydet("C7 tek satırlık a → found 2-2, gövde YALNIZ o satır (b'nin gövdesi yok) · b found 3-5",
                    "a: found · 2-2 · '  METHOD a. ENDMETHOD.' | b: found · 3-5",
                    (r.get("found"), r.get("start_line"), r.get("end_line"), r.get("source"),
                     rb.get("found"), rb.get("start_line"), rb.get("end_line")),
                    r.get("ok") is True and r.get("found") is True and (r["start_line"], r["end_line"]) == (2, 2)
                    and r.get("source") == "  METHOD a. ENDMETHOD."
                    and rb.get("found") is True and (rb["start_line"], rb["end_line"]) == (3, 5))
        # Sınıfın son metodu tek satır → yine found (kapanmamış DEĞİL).
        self.sunucu.plan[("GET", self._GM_YOL)] = (200, "CLASS x IMPLEMENTATION.\n  METHOD c. ENDMETHOD.\nENDCLASS.")
        rc = self.diag.adt_get_method(SINIF, "c")
        self.kaydet("C7b son metot tek satır → found 2-2 (kapanmamis değil)", "found · 2-2",
                    (rc.get("error"), rc.get("found"), rc.get("start_line"), rc.get("end_line")),
                    rc.get("found") is True and (rc.get("start_line"), rc.get("end_line")) == (2, 2))

    def test_C8_get_method_bitissiz_yeni_metot_belirsiz(self):
        kaynak = "CLASS x IMPLEMENTATION.\n  METHOD a.\n    x = 1.\n  METHOD b.\n    y = 2.\n  ENDMETHOD.\nENDCLASS."
        self.sunucu.plan[("GET", self._GM_YOL)] = (200, kaynak)
        r = self.diag.adt_get_method(SINIF, "a")
        self.kaydet("C8 ENDMETHOD'dan önce yeni METHOD → belirsiz",
                    "ok False · belirsiz · found None · source yok",
                    (r.get("ok"), r.get("error"), r.get("found"), "source" in r),
                    r.get("ok") is False and r.get("error") == "belirsiz" and r.get("found") is None
                    and "source" not in r and "yeni METHOD" in r.get("message", ""))

    def test_C9_get_method_satir_ortasi_bitis_desteklenir(self):
        kaynak = ("CLASS x IMPLEMENTATION.\n  METHOD a.\n    y = 2. ENDMETHOD.\n  METHOD b.\n  ENDMETHOD.\n"
                  "ENDCLASS.")
        self.sunucu.plan[("GET", self._GM_YOL)] = (200, kaynak)
        r = self.diag.adt_get_method(SINIF, "a")
        self.kaydet("C9 satır ortasındaki `y = 2. ENDMETHOD.` bitiştir → found 2-3, b'nin gövdesi YOK",
                    "found · 2-3 · 'METHOD b' yok",
                    (r.get("ok"), r.get("found"), r.get("start_line"), r.get("end_line"), r.get("source")),
                    r.get("ok") is True and r.get("found") is True and (r["start_line"], r["end_line"]) == (2, 3)
                    and "y = 2. ENDMETHOD." in r["source"] and "METHOD b" not in r["source"])
        # Satır ortası bitiş sınıfın son metodunda → yine found (kapanmamış DEĞİL).
        self.sunucu.plan[("GET", self._GM_YOL)] = (200, "CLASS x IMPLEMENTATION.\n  METHOD c.\n    z = 3. ENDMETHOD.\nENDCLASS.")
        rc = self.diag.adt_get_method(SINIF, "c")
        self.kaydet("C9b son metotta satır ortası bitiş → found 2-3", "found · 2-3",
                    (rc.get("error"), rc.get("found"), rc.get("start_line"), rc.get("end_line")),
                    rc.get("found") is True and (rc.get("start_line"), rc.get("end_line")) == (2, 3))

    def test_C10_get_method_yorumdaki_endmethod_kontrol_grubu(self):
        # Kontrol grubu: tam satır yorumundaki ENDMETHOD (sütun-1 `*`, satır başı `"`) belirsiz YAPMAZ.
        kaynak = ("CLASS x IMPLEMENTATION.\n  METHOD a.\n* ENDMETHOD.\n    \" ENDMETHOD.\n    x = 1.\n"
                  "  ENDMETHOD.\nENDCLASS.")
        self.sunucu.plan[("GET", self._GM_YOL)] = (200, kaynak)
        r = self.diag.adt_get_method(SINIF, "a")
        self.kaydet("C10 yorum satırlarında ENDMETHOD · çok satırlı metot found 2-6",
                    "ok True · found True · 2-6",
                    (r.get("ok"), r.get("found"), r.get("start_line"), r.get("end_line")),
                    r.get("ok") is True and r.get("found") is True
                    and (r["start_line"], r["end_line"]) == (2, 6) and "x = 1." in r["source"])


    # Z213: kaynak çekirdeğin `sinir_belirsiz`'i aXet sözleşmesinde `error:"belirsiz"` (hata kodu DEĞİŞMEDİ).
    def test_C11_get_method_ayni_satirda_karisik_belirsiz_govde_donmez(self):
        kaynak = "CLASS x IMPLEMENTATION.\n  METHOD a. ENDMETHOD. METHOD b. ENDMETHOD.\nENDCLASS."
        self.sunucu.plan[("GET", self._GM_YOL)] = (200, kaynak)
        r = self.diag.adt_get_method(SINIF, "a")
        self.kaydet("C11 aynı satırda METHOD/ENDMETHOD karışık → belirsiz · found None · source yok · end_line None",
                    "ok False · belirsiz · source yok",
                    (r.get("ok"), r.get("error"), r.get("found"), "source" in r, r.get("matches")),
                    r.get("ok") is False and r.get("error") == "belirsiz" and r.get("found") is None
                    and "source" not in r and r.get("matches") == [{"start_line": 2, "end_line": None}]
                    and "METHOD satırında" in r.get("message", ""))

    def test_C12_get_method_literal_ve_sablon_kacisi(self):
        bs = chr(92)
        kaynak = ("CLASS x IMPLEMENTATION.\n  METHOD a.\n    lv = 'x. ENDMETHOD.'.\n    r = |x" + bs
                  + "|. ENDMETHOD. |.\n    method = 'GET'.\n  ENDMETHOD.\n  METHOD b.\n  ENDMETHOD.\nENDCLASS.")
        self.sunucu.plan[("GET", self._GM_YOL)] = (200, kaynak)
        r = self.diag.adt_get_method(SINIF, "a")
        self.kaydet("C12 literal/şablon kaçışı/`method =` içindeki ENDMETHOD bitiş SAYILMAZ → found 2-6",
                    "found · 2-6", (r.get("ok"), r.get("found"), r.get("start_line"), r.get("end_line")),
                    r.get("ok") is True and r.get("found") is True and (r["start_line"], r["end_line"]) == (2, 6))

    def test_C13_get_method_amdp_okuma_yolu_doner(self):
        kaynak = ("CLASS x IMPLEMENTATION.\n  METHOD a\n    BY DATABASE PROCEDURE FOR HDB LANGUAGE SQLSCRIPT\n"
                  "    USING t.\n    lt = select t.method,\n      method,\n      x from t;\n  ENDMETHOD.\nENDCLASS.")
        self.sunucu.plan[("GET", self._GM_YOL)] = (200, kaynak)
        r = self.diag.adt_get_method(SINIF, "a")
        self.kaydet("C13 okuma yolu AMDP'yi DÖNDÜRÜR (yazma yolu PUT etmez) → found 2-8", "found · 2-8",
                    (r.get("ok"), r.get("found"), r.get("start_line"), r.get("end_line")),
                    r.get("ok") is True and r.get("found") is True and (r["start_line"], r["end_line"]) == (2, 8))

    def test_C14_get_method_kapsam_metni(self):
        r = self.diag.adt_get_method("", "a")
        kap = r.get("scope") or ""
        self.kaydet("C14 KAPSAM metni tek satır desteği + belirsiz + çok satırlı şablon SINIRINI söyler",
                    "üç ifade de var", kap[-200:],
                    all(p in kap for p in ("tek satirlik", "`belirsiz`", "cok satirli string", "include")))

# ══════════════════════════════════════════════════════════════════════════════════════════════
# D — sınıf kapısı: iki araç okuma kapısında; eski aktive eden yol araçtan KALDIRILDI
# ══════════════════════════════════════════════════════════════════════════════════════════════
class SinifKapisi(_Kayit):
    def test_D1_okuma_sinifi(self):
        sinif = {a: gate.tool_class(a) for a in ("adt_syntax_check", "adt_get_method", "adt_classrun")}
        self.kaydet("D1 sınıf", "syntax_check read · get_method read · classrun write (kontrol)", sinif,
                    sinif == {"adt_syntax_check": "read", "adt_get_method": "read", "adt_classrun": "write"})

    def test_D2_arac_aktivasyon_yolunu_cagirmaz(self):
        import ast
        kaynak = (H.SCRIPTS / "sapadt" / "tools" / "query.py").read_text(encoding="utf-8")
        cagrilar = {d.func.attr for d in ast.walk(ast.parse(kaynak))
                    if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)}
        yasak = cagrilar & {"syntax_check", "syntax_check_via_activation", "activate_object", "push_object"}
        self.kaydet("D2 query.py aktive eden yolu ÇAĞIRMAZ", "boş küme", sorted(yasak), not yasak)


if __name__ == "__main__":
    unittest.main(verbosity=2)
