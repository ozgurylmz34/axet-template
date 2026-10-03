# -*- coding: utf-8 -*-
"""`adt_dump_read` + `adt_dump_list` (ST22) — SAP'siz davranış korpusu (Z166).

Kaynak: çekirdek K4 (2026-10-03) fixture'ı `dump_okuma` — vektör kimlikleri aynı tutuldu.
  · ARAÇ GÜRÜLTÜSÜ: `GENERATE_SUBPOOL_DIR_FULL` ∧ `CL_ADT_DP_OPEN_SQL_HANDLER====CP` (ADT SQL
    konsolu). İmza İKİ alanın VE'sidir; liste dump'ı ATMAZ, etiketler.
  · BAŞKA CLIENT: feed aynı sistemin tüm client'larını taşır (kaynakta ölçüldü 49/100). Varsayılan
    GİZLENİR / OKUNMAZ; `acknowledge_risk=True` açar. Client'ı tespit edilemeyen girdi de gizlenir
    (fail-closed) ama SAYISI ayrı alanda + notice ile döner ⇒ "dump yok" yanılgısı üretilmez.
Vektörler:
  L*  liste: gizleme + sayaçlar + notice · gürültü VE-imzası · özet başlığı client otoritesi ·
      sabit-genişlik kimlik · tier guard
  R*  okuma: alanlar · kimlik normalizasyonu · 404 ≠ sessiz boş · başka client · özet ·
      formatted bayt tavanı · hata yolları
  G1  aXet'e özgü: `gate.READ_TOOLS` salt-okur allowlist'inde (yoksa yazma kapısına düşer)
⛔ SİLİNMEZ FP ÇAPALARI: L3b/L3c (tek alan eşleşmesi gürültü DEĞİL) · L2/R6b (ack ile başka
   client GÖRÜNÜR) · R1 (aynı client'ta tek GET). Bunlar olmadan "her şeyi gizle / her şeyi
   gürültü say" diyen bir kusur da geçerdi.
KAPSAM — BAKMADIKLARI: gerçek SAP (veri jenerik; gerçek sistem/kullanıcı YOK) · ST22 özet
HTML'inin başka sürümlerdeki biçimi.
"""
from __future__ import annotations

import contextlib
import io
import os
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from xml.sax.saxutils import escape

import _helpers as H

sys.dont_write_bytecode = True
LIB = H.SCRIPTS / "sapadt" / "lib"
for _p in (H.SCRIPTS, LIB):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import sapadt  # noqa: E402,F401
from sapadt import _conn as CONN  # noqa: E402
from sapadt import gate  # noqa: E402
from sap_adt_lib import SAPADTError  # noqa: E402

Q = None
_KOK = None
_ESKI_ENV: dict = {}


def setUpModule():
    global _KOK, Q
    _KOK = Path(tempfile.mkdtemp(prefix="axet_dump_okuma_"))
    dev = H.make_project(_KOK, "dev")
    for k in ("AXET_SAP_PROJECT_DIR", "ADT_SAP_TIER"):
        _ESKI_ENV[k] = os.environ.get(k)
    os.environ.pop("ADT_SAP_TIER", None)
    os.environ["AXET_SAP_PROJECT_DIR"] = str(dev)
    from sapadt.tools import query as _q
    Q = _q


def tearDownModule():
    for k, v in _ESKI_ENV.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    if _KOK is not None:
        shutil.rmtree(_KOK, ignore_errors=True)


# ══ JENERİK VERİ (gerçek sistem/kullanıcı YOK) ═══════════════════════════════════
URL = "https://sap.example.invalid:44300"
HOST = "sapapp01_XYZ_00"
ADT_SQL = "CL_ADT_DP_OPEN_SQL_HANDLER====CP"
ZPROG = "ZCL_SD001_ORNEK===============CP"


def kimlik(ts: str, kullanici: str, client: str, no: str = "07") -> str:
    """SNAP anahtarı biçimi: 14 zaman + 32 host + 12 kullanıcı + 3 client + 9 → uzunluk 70."""
    ham = ts + HOST.ljust(32) + kullanici.ljust(12) + client + no.rjust(9)
    assert len(ham) == 70, len(ham)
    return ham


def kodla(ham: str) -> str:
    return ham.replace(" ", "%20")


def ozet_html(client, kullanici: str = "KULLANICI1", ek_bolum: bool = False) -> str:
    satirlar = [("Short Text", "A row already exists with this key"),
                ("Runtime Error", "ITAB_DUPLICATE_KEY"),
                ("Program", ZPROG),
                ("Date/Time", "01.01.2026 12:00:00 (System)"),
                ("User", "%s (Ad Soyad)" % kullanici)]
    if client is not None:
        satirlar.append(("Client", client))
    satirlar.append(("Host", HOST))
    tablo = "".join('<tr><td><b>%s&nbsp;</b></td><td nowrap> %s </td></tr>' % (a, d)
                    for a, d in satirlar)
    h = ('<p><a class="showInRuntimeViewerLink" href="adt://XYZ/x">Show in Runtime Error '
         'Viewer</a></p><h4 id="OVERVIEW">Contents</h4><a href="#HEADERX">Header Information</a>'
         '<br><h4 id="HEADERX">Header Information</h4><table cellspacing="3">' + tablo + '</table>'
         '<h4 id="WHATHAPPENED">What happened?</h4>Error in the ABAP application program.<br><br>'
         'The current program had to be terminated.'
         '<h4 id="ERROR">Error analysis</h4>Duplicate key in "&lt;fs&gt;"<br>second line'
         '<h4 id="TERMINATION">Information on where terminated</h4>The termination occurred in '
         '"LOAD_DATA".<br><br>In the source code, the termination point is in line 6 of include '
         '"ZCL_SD001_ORNEK===============CM009".'
         '<h4 id="SOURCE">Source Code Extract</h4><style> .keyword { color: blue } </style>'
         '<table id="sourcetable"><tr><td id="sourcetablecolumn"><span class="linenumber">1</span>'
         '<span class="linenumber"><a title="Show where terminated" href="adt://XYZ/t#start=211">'
         '<span class="indicator">></span></a></span><span class="linenumber">3</span></td>'
         '<td id="sourcetablecolumn"><div lang="#" class="sourceline"><span>&nbsp;&nbsp;'
         '<span class="keyword">METHOD</span> load_data<span class="keyword">.</span></span></div>'
         '<div lang="#" class="sourceline highlight"><a href="adt://XYZ/t#start=211"><span>'
         '&nbsp;&nbsp;&nbsp;&nbsp;<span class="keyword">INSERT</span> ls INTO TABLE lt.</span></a></div>'
         '<div lang="#" class="sourceline"><span>&nbsp;&nbsp;<span class="keyword">ENDMETHOD</span>'
         '.</span></div></td></tr></table>'
         '<h4 id="STACK">Active Calls/Events</h4><style>code { font-family: x; }</style>'
         '<table cellspacing="5"><tr><th align="left">No.</th><th align="left">Event</th>'
         '<th align="left">Program</th><th align="left">Include</th><th align="left">Line</th></tr>'
         '<tr><td><code><a href="adt://XYZ/sap/bc/adt/oo/classes/zcl_sd001_ornek/source/main#start=211">'
         '2</a></code></td><td><code>LOAD_DATA</code></td><td><code>ZCL_SD001_ORNEK===============CP'
         '</code></td><td><code>ZCL_SD001_ORNEK===============CM009</code></td><td><code>6</code>'
         '</td></tr><tr><td><code><a href="adt://XYZ/sap/bc/adt/programs/programs/zsd001_p_ornek/source/'
         'main#start=83">1</a></code></td><td><code>START-OF-SELECTION</code></td><td><code>'
         'ZSD001_P_ORNEK</code></td><td><code>ZSD001_P_ORNEK</code></td><td><code>83</code></td>'
         '</tr></table>')
    if ek_bolum:
        h += '<h4 id="EXTRA">Yeni bolum</h4>beklenmeyen icerik'
    return h


def dump_xml(ham: str, hata: str, program: str, istisna: str = "") -> bytes:
    k = kodla(ham)
    return ('<?xml version="1.0" encoding="utf-8"?><dump:dump title="Runtime Error: %s 01.01.2026 '
            '12:00:00 KULLANICI1 (Ad Soyad)" error="%s" author="KULLANICI1" exception="%s" '
            'terminatedProgram="%s" serverInstance="%s" datetime="2026-01-01T09:00:00Z" '
            'systemDate="01.01.2026" systemTime="12:00:00" language="TR" '
            'xmlns:dump="http://www.sap.com/adt/categories/dump"><dump:links>'
            '<dump:link relation="self" uri="/sap/bc/adt/runtime/dump/%s" '
            'contentType="application/vnd.sap.adt.runtime.dump.v1+xml"/>'
            '<dump:link relation="http://www.sap.com/adt/relations/runtime/dump/termination" '
            'uri="adt://XYZ/sap/bc/adt/oo/classes/zcl_sd001_ornek/source/main#start=211" '
            'contentType=""/></dump:links><dump:chapters><dump:chapter name="kap0" '
            'title="Short Text" line="10"/></dump:chapters></dump:dump>'
            % (hata, hata, istisna, program, HOST, k)).encode("utf-8")


NOTFOUND = ('<?xml version="1.0" encoding="utf-8"?><exc:exception xmlns:exc="http://www.sap.com/'
            'abapxml/types/communicationframework"><namespace id="com.sap.adt.runtime.dump"/>'
            '<type id="notFound"/><message lang="EN">An exception was raised</message>'
            '<localizedMessage lang="TR">An exception was raised</localizedMessage><properties>'
            '<entry key="T100KEY-ID">SY</entry><entry key="T100KEY-NO">530</entry></properties>'
            '</exc:exception>').encode("utf-8")

FEED_GIRDI = [
    # ad, ham kimlik, hata, program, özet-client (None=özet YOK, "-"=özette Client satırı yok)
    ("E1", kimlik("20260101120001", "KULLANICI1", "100"), "GENERATE_SUBPOOL_DIR_FULL", ADT_SQL, "100"),
    ("E2", kimlik("20260101120002", "KULLANICI1", "100"), "GENERATE_SUBPOOL_DIR_FULL", ZPROG, "100"),
    ("E3", kimlik("20260101120003", "KULLANICI1", "100"), "ITAB_DUPLICATE_KEY", ADT_SQL, "100"),
    ("E4", kimlik("20260101120004", "KULLANICI2", "110"), "ITAB_DUPLICATE_KEY", ZPROG, "110"),
    ("E5", "20260101120005" + HOST + " KISA", "ITAB_DUPLICATE_KEY", ZPROG, None),
    ("E6", kimlik("20260101120006", "KULLANICI1", "100"), "ITAB_DUPLICATE_KEY", ZPROG, None),
    ("E7", kimlik("20260101120007", "KULLANICI1", "110"), "ITAB_DUPLICATE_KEY", ZPROG, "100"),
    ("E8", kimlik("20260101120008", "KULLANICIUZN", "110"), "ITAB_DUPLICATE_KEY", ZPROG, None),
]


def feed_xml() -> bytes:
    A = "http://www.w3.org/2005/Atom"
    girdiler = []
    for ad, ham, hata, prog, oz in FEED_GIRDI:
        k = kodla(ham)
        ozet = ("" if oz is None else
                '<summary type="html">%s</summary>' % escape(ozet_html(None if oz == "-" else oz)))
        girdiler.append(
            '<entry><author><name>%s</name></author><category term="%s" label="ABAP runtime error"/>'
            '<category term="%s" label="Terminated ABAP program"/><id>/sap/bc/adt/vit/runtime/dumps/'
            '%s</id><link href="adt://XYZ/sap/bc/adt/runtime/dump/%s" rel="self"/><updated>'
            '2026-01-01T09:00:00Z</updated><title>%s</title>%s</entry>'
            % (ad, hata, prog, k, k, ad, ozet))
    return ('<?xml version="1.0" encoding="utf-8"?><feed xmlns="%s">%s</feed>'
            % (A, "".join(girdiler))).encode("utf-8")


FEED = {"/sap/bc/adt/runtime/dumps": (200, feed_xml())}


# ══ SAHTE HTTP ═════════════════════════════════════════════════════════════════
class _Yanit:
    def __init__(self, status: int, govde: bytes):
        self.status_code = status
        self.content = govde
        self.text = govde.decode("utf-8", "replace")
        self.headers = {}


class _Oturum:
    verify = True

    def __init__(self, yollar: dict, firlat=None):
        self.yollar = yollar
        self.cagrilar: list = []
        self.firlat = firlat

    def get(self, url, params=None, headers=None, verify=None, timeout=None):
        yol = url[len(URL):]
        self.cagrilar.append((yol, (headers or {}).get("Accept"), params))
        if self.firlat:
            raise self.firlat
        st, g = self.yollar.get(yol, (404, NOTFOUND))
        return _Yanit(st, g)


def D(ham: str, son: str = "") -> str:
    return "/sap/bc/adt/runtime/dump/" + kodla(ham) + son


H100 = kimlik("20260101130000", "KULLANICI1", "100")
H110 = kimlik("20260101130001", "KULLANICI2", "110")
HSUB = kimlik("20260101130002", "KULLANICI1", "100")
KISA = "20260101130003" + HOST + "_KISA"
YOLLAR = {
    D(H100): (200, dump_xml(H100, "ITAB_DUPLICATE_KEY", ZPROG)),
    D(H110): (200, dump_xml(H110, "ITAB_DUPLICATE_KEY", ZPROG)),
    D(HSUB): (200, dump_xml(HSUB, "GENERATE_SUBPOOL_DIR_FULL", ADT_SQL, "CX_SY_GENERATE_SUBPOOL_FULL")),
    D(H100, "/summary"): (200, ozet_html("100", ek_bolum=True).encode("utf-8")),
    D(KISA): (200, dump_xml(KISA, "ITAB_DUPLICATE_KEY", ZPROG)),
    D(KISA, "/summary"): (200, ozet_html("100").encode("utf-8")),
}


class _Taban(unittest.TestCase):
    def setUp(self):
        self._eski = (Q._get_client, CONN.get_active_tier)
        self.tier = "DEV"
        CONN.get_active_tier = lambda: self.tier

    def tearDown(self):
        Q._get_client, CONN.get_active_tier = self._eski

    def kur(self, yollar, client="100", firlat=None):
        adt = types.SimpleNamespace(url=URL, session=_Oturum(yollar, firlat), client=client)
        c = types.SimpleNamespace(adt_client=adt)
        Q._get_client = lambda _c=c: _c
        return adt.session

    def cagir(self, fn, **k):
        with contextlib.redirect_stdout(io.StringIO()):
            return fn(**k)


class ListeTest(_Taban):
    """L — adt_dump_list."""

    def test_L1_varsayilan_gizler_sayar_notice(self):
        self.kur(FEED)
        r = self.cagir(Q.adt_dump_list, limit=50)
        adlar = [d["user"] for d in r.get("dumps", [])]
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(adlar, ["E1", "E2", "E3", "E6", "E7"])
        self.assertEqual((r.get("gizlenen_baska_client"), r.get("gizlenen_client_bilinmeyen"),
                          r.get("taranan")), (2, 1, 8))
        self.assertIn("dump yok", r.get("notice", ""))
        self.assertIn("acknowledge_risk=True", r.get("notice", ""))

    def _ack(self):
        self.kur(FEED)
        return self.cagir(Q.adt_dump_list, limit=50, acknowledge_risk=True)

    def test_L2_ack_hepsi_gorunur(self):
        ra = self._ack()
        cl = {d["user"]: d.get("client") for d in ra.get("dumps", [])}
        self.assertEqual(ra.get("count"), 8)
        self.assertEqual((cl.get("E4"), cl.get("E5"), cl.get("E1")), ("110", None, "100"))
        self.assertNotIn("notice", ra)

    def test_L3a_gurultu_ve_imzasi(self):
        ra = self._ack()
        gr = {d["user"]: d.get("arac_gurultusu") for d in ra["dumps"]}
        self.assertIs(gr.get("E1"), True)
        self.assertTrue(ra["dumps"][0].get("arac_gurultusu_sebep"))
        self.assertEqual(ra.get("arac_gurultusu_sayisi"), 1)

    def test_L3b_subpool_baska_programda_gurultu_degil(self):
        gr = {d["user"]: d.get("arac_gurultusu") for d in self._ack()["dumps"]}
        self.assertIs(gr.get("E2"), False)

    def test_L3c_sql_isleyicisi_baska_hatayla_gurultu_degil(self):
        gr = {d["user"]: d.get("arac_gurultusu") for d in self._ack()["dumps"]}
        self.assertIs(gr.get("E3"), False)

    def test_L4_limit_gorunenleri_sayar(self):
        self.kur(FEED)
        r4 = self.cagir(Q.adt_dump_list, limit=4)
        self.assertEqual([d["user"] for d in r4["dumps"]], ["E1", "E2", "E3", "E6"])
        self.assertEqual((r4["taranan"], r4["gizlenen_baska_client"],
                          r4["gizlenen_client_bilinmeyen"]), (6, 1, 1))

    def test_L5_qa_tier_acksiz_http_yok(self):
        self.tier = "QA"
        s = self.kur(FEED)
        r5 = self.cagir(Q.adt_dump_list)
        self.assertEqual(r5.get("error"), "tier_pii_guard")
        self.assertEqual(s.cagrilar, [])

    def test_L6_baglanti_client_bilinmiyor_fail_closed(self):
        self.kur(FEED, client=None)
        r6 = self.cagir(Q.adt_dump_list, limit=50)
        self.assertEqual((r6.get("count"), r6.get("gizlenen_client_bilinmeyen")), (0, 8))
        self.assertIn("notice", r6)

    def test_L7_ozet_basligi_client_otorite(self):
        self.kur(FEED)
        r = self.cagir(Q.adt_dump_list, limit=50)
        self.assertIn("E7", [d["user"] for d in r.get("dumps", [])])

    def test_L8_sabit_genislik_kimlik_12_karakter_kullanici(self):
        cl = {d["user"]: d.get("client") for d in self._ack()["dumps"]}
        self.assertEqual(cl.get("E8"), "110")


class OkumaTest(_Taban):
    """R — adt_dump_read."""

    def test_R1_varsayilan_tek_get(self):
        s = self.kur(YOLLAR)
        r = self.cagir(Q.adt_dump_read, dump="adt://XYZ" + D(H100))
        self.assertTrue(r.get("ok"), r)
        self.assertEqual((r.get("error_type"), r.get("program"), r.get("user"), r.get("exception")),
                         ("ITAB_DUPLICATE_KEY", ZPROG, "KULLANICI1", None))
        self.assertEqual(r.get("termination", {}).get("line"), 211)
        self.assertEqual(r.get("client"), "100")
        self.assertEqual(s.cagrilar, [(D(H100), "application/vnd.sap.adt.runtime.dump.v1+xml", None)])
        self.assertIn("formatted OKUNMADI", r.get("kapsam", ""))

    def test_R2_kimlik_normalizasyonu(self):
        bicimler = ["adt://XYZ" + D(H100), "/sap/bc/adt/vit/runtime/dumps/" + kodla(H100), H100,
                    kodla(H100), D(H100, "/summary"), "  " + kodla(H100) + "#x  "]
        urller = []
        for b in bicimler:
            s = self.kur(YOLLAR)
            self.cagir(Q.adt_dump_read, dump=b)
            urller.append(s.cagrilar[-1][0] if s.cagrilar else None)
        self.assertEqual(set(urller), {D(H100)}, urller)

    def test_R3_okumada_gurultu_etiketi(self):
        self.kur(YOLLAR)
        rs = self.cagir(Q.adt_dump_read, dump=kodla(HSUB))
        self.kur(YOLLAR)
        r = self.cagir(Q.adt_dump_read, dump=H100)
        self.assertIs(rs.get("arac_gurultusu"), True)
        self.assertEqual(rs.get("exception"), "CX_SY_GENERATE_SUBPOOL_FULL")
        self.assertIs(r.get("arac_gurultusu"), False)

    def test_R4_404_sessiz_bos_degil(self):
        self.kur(YOLLAR)
        r4 = self.cagir(Q.adt_dump_read, dump=kodla(kimlik("20260101139999", "KULLANICI1", "100")))
        self.assertIs(r4.get("ok"), False)
        self.assertEqual(r4.get("error"), "dump_bulunamadi")
        self.assertIn("notFound", r4.get("message", ""))
        self.assertIn("SY/530", r4.get("message", ""))

    def test_R5_500_ayristirilmis_mesaj(self):
        self.kur({D(H100): (500, NOTFOUND.replace(b"notFound", b"internal"))})
        r5 = self.cagir(Q.adt_dump_read, dump=H100)
        self.assertEqual(r5.get("error"), "http_500")
        self.assertIn("internal", r5.get("message", ""))

    def test_R6a_baska_client_acksiz_govde_istenmez(self):
        s = self.kur(YOLLAR)
        r6 = self.cagir(Q.adt_dump_read, dump=H110)
        self.assertEqual((r6.get("error"), r6.get("client")), ("baska_client_pii", "110"))
        self.assertEqual(s.cagrilar, [])

    def test_R6b_ack_ile_baska_client_okunur(self):
        self.kur(YOLLAR)
        r6b = self.cagir(Q.adt_dump_read, dump=H110, acknowledge_risk=True)
        self.assertTrue(r6b.get("ok"))
        self.assertEqual(r6b.get("client"), "110")

    def test_R7a_tanimsiz_kimlik_client_ozetten(self):
        self.kur(YOLLAR)
        r7 = self.cagir(Q.adt_dump_read, dump=KISA)
        self.assertTrue(r7.get("ok"), r7)
        self.assertEqual((r7.get("client_kaynagi"), r7.get("client")), ("summary", "100"))

    def test_R7b_tanimsiz_kimlik_ozet_baska_client(self):
        y = dict(YOLLAR)
        y[D(KISA, "/summary")] = (200, ozet_html("110").encode("utf-8"))
        self.kur(y)
        self.assertEqual(self.cagir(Q.adt_dump_read, dump=KISA).get("error"), "baska_client_pii")

    def test_R7c_tanimsiz_kimlik_ozet_404(self):
        y = dict(YOLLAR)
        del y[D(KISA, "/summary")]
        del y[D(KISA)]
        self.kur(y)
        self.assertEqual(self.cagir(Q.adt_dump_read, dump=KISA).get("error"), "dump_bulunamadi")

    def test_R7d_client_tespit_edilemedi_fail_closed(self):
        y = dict(YOLLAR)
        y[D(KISA, "/summary")] = (500, b"<x/>")
        self.kur(y)
        self.assertEqual(self.cagir(Q.adt_dump_read, dump=KISA).get("error"), "baska_client_pii")

    def test_R7e_71_uzunluk_kimlikten_client_okunmaz(self):
        uzun = kimlik("20260101130004", "KULLANICI2", "110") + "9"
        y = dict(YOLLAR)
        y[D(uzun)] = (200, dump_xml(uzun, "ITAB_DUPLICATE_KEY", ZPROG))
        y[D(uzun, "/summary")] = (200, ozet_html("100").encode("utf-8"))
        s = self.kur(y)
        r = self.cagir(Q.adt_dump_read, dump=uzun)
        self.assertEqual((len(uzun), uzun[58:61]), (71, "110"))
        self.assertTrue(r.get("ok"), r)
        self.assertEqual((r.get("client"), r.get("client_kaynagi")), ("100", "summary"))
        self.assertTrue(s.cagrilar and s.cagrilar[0][0] == D(uzun, "/summary"), s.cagrilar)

    def test_R8_summary_ayristirma(self):
        s = self.kur(YOLLAR)
        r8 = self.cagir(Q.adt_dump_read, dump=H100, summary=True)
        oz = r8.get("summary") or {}
        src = oz.get("source_extract", "")
        self.assertTrue(r8.get("ok"), r8)
        self.assertEqual(oz.get("header", {}).get("Runtime Error"), "ITAB_DUPLICATE_KEY")
        self.assertEqual(oz.get("header", {}).get("Client"), "100")
        self.assertEqual(oz.get("error_analysis"), "Duplicate key in \"<fs>\"\nsecond line")
        self.assertIn("line 6 of include", oz.get("where_terminated", ""))
        self.assertIn(">     INSERT ls INTO TABLE lt.", src)
        self.assertIn("  METHOD load_data.", src)
        self.assertNotIn("color", src)
        self.assertNotIn("211", src)
        self.assertEqual(oz.get("active_calls", [{}])[0].get("include"),
                         "ZCL_SD001_ORNEK===============CM009")
        self.assertEqual(oz["active_calls"][0].get("line"), "6")
        self.assertTrue(oz["active_calls"][1].get("uri", "").endswith("#start=83"))
        self.assertEqual(oz.get("other_sections"), {"EXTRA": "beklenmeyen icerik"})
        self.assertEqual(len(s.cagrilar), 2)

    def test_R9_ozet_client_kimlikten_farkli(self):
        y = dict(YOLLAR)
        y[D(H100, "/summary")] = (200, ozet_html("110").encode("utf-8"))
        self.kur(y)
        r9 = self.cagir(Q.adt_dump_read, dump=H100, summary=True)
        self.assertEqual(r9.get("error"), "baska_client_pii")

    def _formatted(self, max_bytes):
        metin = ("Kısa döküm başlığı\n" + "ş" * 3000).encode("utf-8")
        y = dict(YOLLAR)
        y[D(H100, "/formatted")] = (200, metin)
        self.kur(y)
        return metin, self.cagir(Q.adt_dump_read, dump=H100, formatted=True, max_bytes=max_bytes)

    def test_R10a_formatted_bayt_tavani(self):
        metin, r = self._formatted(1001)
        ft = r.get("formatted_text", "")
        self.assertIs(r.get("truncated"), True)
        self.assertEqual(r.get("formatted_total_bytes"), len(metin))
        self.assertLessEqual(r.get("formatted_returned_bytes", 10 ** 9), 1001)
        self.assertNotIn("�", ft)
        self.assertEqual(len(ft.encode("utf-8")), r.get("formatted_returned_bytes"))

    def test_R10b_tavan_kistirilir(self):
        _, rb = self._formatted(10 ** 9)
        _, rc = self._formatted(5)
        self.assertEqual(rb.get("max_bytes"), 200000)
        self.assertIs(rb.get("truncated"), False)
        self.assertEqual(rc.get("max_bytes"), 1000)

    def test_R11_qa_tier_acksiz_http_yok(self):
        self.tier = "QA"
        s = self.kur(YOLLAR)
        self.assertEqual(self.cagir(Q.adt_dump_read, dump=H100).get("error"), "tier_pii_guard")
        self.assertEqual(s.cagrilar, [])

    def test_R12_cozulemeyen_kimlik_http_yok(self):
        s = self.kur(YOLLAR)
        r = self.cagir(Q.adt_dump_read, dump="/sap/bc/adt/runtime/dumps")
        self.assertEqual(r.get("error"), "gecersiz_dump_kimligi")
        self.assertEqual(s.cagrilar, [])

    def test_R12b_nokta_kimlik_yol_bolutu_degil(self):
        sonuc = []
        for b in [".", "..", "%2E%2E", "adt://XYZ/sap/bc/adt/runtime/dump/..", "  ..  ", ""]:
            s = self.kur(YOLLAR)
            sonuc.append((self.cagir(Q.adt_dump_read, dump=b).get("error"), len(s.cagrilar)))
        self.assertTrue(all(e == "gecersiz_dump_kimligi" and n == 0 for e, n in sonuc), sonuc)

    def test_R13_oturum_istisnasi_cokmez(self):
        self.kur(YOLLAR, firlat=SAPADTError("baglanti koptu", status_code=503))
        self.assertIs(self.cagir(Q.adt_dump_read, dump=H100).get("ok"), False)

    def test_R14_istenen_ozet_okunamadi(self):
        y = dict(YOLLAR)
        y[D(H100, "/summary")] = (500, b"<x/>")
        self.kur(y)
        r = self.cagir(Q.adt_dump_read, dump=H100, summary=True)
        self.assertIs(r.get("ok"), False)
        self.assertEqual(r.get("error"), "summary_okunamadi")


class GateTest(unittest.TestCase):
    def test_G1_dump_read_salt_okur_allowlist(self):
        self.assertIn("adt_dump_read", gate.READ_TOOLS)
        self.assertEqual(gate.tool_class("adt_dump_read", {}), "read")


if __name__ == "__main__":
    unittest.main()
