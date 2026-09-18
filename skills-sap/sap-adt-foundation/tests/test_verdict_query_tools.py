# -*- coding: utf-8 -*-
"""MCP okuma/sorgu araçlarının dürüstlüğü — çevrimdışı kontrol grubu.

Beş davranış, her biri sahte bir "0" ya da sahte bir "tamam" üretebiliyordu:
  S  `adt_sql_query` / `adt_table_read`: SAP'nin 400/500 gövdesi çıktıya gelmiyordu
     (yalnız `[ERROR] ... [400] Failed to run query`); kırpılan sonuçta `truncated` yoktu.
     `truncated` KESİNDİR: araç `row_limit + 1` satır ister; fazlası gelirse kırpılmıştır.
     Tam `row_limit` kadar satır kırpık SAYILMAZ; `totalRows`'tan türetilmez (aggregate'de
     alttaki satır sayısıdır).
  T  `adt_inactive_objects` TADIR çapraz kontrolü tek uzun `IN` listesiyle 400 alıyordu.
     Artık en fazla 5 adlık parçalar; başarısız ya da kırpık parça YALNIZ kendi adlarını
     `tadir_deleted: null` yapar ve sonuç `ok:false` olur (`count` basılmaz).
  U  `adt_search_objects`: (a) kırpma işareti — sunucu isabeti `max_results` tavanına
     dayandığında `truncated: true` + `truncated_notice` (K3, 2026-09-15); kırpma zaten
     hesaplanıyordu ama yalnız stdout'a yazılıyordu, yapılandırılmış sonucu okuyan ajan
     GÖRMÜYORDU. (b) quickSearch sunucusu `FUNC`/`FUNC/FF` filtresine FM'i `FUGR/FF`
     tipiyle döndürür; istemci tip süzgeci onu eliyordu (var olan FM için `count:0`).
  V  `adt_where_used` / `adt_impact_analysis`: usageReferences bir ağaçtır; `DEVC/K`
     düğümleri çağıranların paket atalarıdır, çağıran değildir.
  X  worklist ayrıştırması tek kaynaktan (`sap_adt_lib.aktivasyon_worklist_ayristir`);
     ioc olmayan 200 gövde "aktive bekleyen yok" sayılmaz.

Kontrol satırları (silinmez): S1b S4b S5 S6 S7 S8b S9 T1 T4 T5 U3 U4 U5 U6 U8 V3 X6 — bunlar
olmadan "her şeye ok:false / truncated:true / uyarı bas" diyen bir düzeltme de geçerdi.

KAPSAM — BAKMADIKLARI: gerçek SAP · MCP SDK açıklama üretimi · TADIR'da SATIRI OLMAYAN ad
(bugün `tadir_deleted:false`; T5 davranışı aynen tutar, değiştirmez) · 500 ardından gelen
"Session Timed Out" 400.
"""
from __future__ import annotations

import contextlib
import io
import os
import re
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

IOC = "http://www.sap.com/abapxml/inactiveCtsObjects"
ADTCORE = "http://www.sap.com/adt/core"

FG = "ZBC000_FG_DEMO"
FM = "ZBC000_FM_DEMO"
CLS = "ZCL_BC000_DEMO"                  # ağaçlı where-used
CLS_PAKET = "ZCL_BC000_YALNIZ_PAKET"    # yalnız paket düğümü dönen (tanımsız şekil)
CLS_BOS = "ZCL_BC000_TUKETICISIZ"
DDLS = "ZBC000_I_DEMO"
TUK = "ZCL_BC000_TUKETICI"
ENH = "ZENH_BC000_DEMO"

HATA400 = ('<?xml version="1.0" encoding="utf-8"?><exc:exception '
           'xmlns:exc="http://www.sap.com/abapxml/types/communicationframework">'
           '<namespace id="http://www.sap.com/adt/wda/dataPreview"/>'
           '<type id="ExceptionDataPreviewGeneral"/>'
           '<message lang="EN">all expressions in the projection list must have an alias name'
           '</message></exc:exception>')
HTML500 = ('<!DOCTYPE html> <html><head> <title>Application Server Error</title> </head>'
           '<body>x</body></html>')
SEBEP400 = "all expressions in the projection list must have an alias name"

ADLAR25 = ["ZCL_BC000_PARCA_%02d" % i for i in range(1, 26)]


def fm_uri(fg, fm):
    return f"/sap/bc/adt/functions/groups/{fg.lower()}/fmodules/{fm.lower()}"


def cls_uri(c):
    return f"/sap/bc/adt/oo/classes/{c.lower()}"


def pkg_uri(p):
    return f"/sap/bc/adt/packages/{p.lower()}"


def dp_xml(kolonlar, satirlar, toplam):
    """dataPreview gövdesi — sütun bazlı (canlı biçim). satirlar: [(değer, ...)]."""
    kol = []
    for i, ad in enumerate(kolonlar):
        veri = "".join(f"<dataPreview:data>{s[i]}</dataPreview:data>" for s in satirlar)
        kol.append(f'<dataPreview:columns><dataPreview:metadata dataPreview:name="{ad}"/>'
                   f'<dataPreview:dataSet>{veri}</dataPreview:dataSet></dataPreview:columns>')
    return ('<?xml version="1.0" encoding="utf-8"?><dataPreview:tableData '
            'xmlns:dataPreview="http://www.sap.com/adt/dataPreview">'
            f'<dataPreview:totalRows>{toplam}</dataPreview:totalRows>'
            '<dataPreview:queryExecutionTime>1</dataPreview:queryExecutionTime>'
            f'{"".join(kol)}</dataPreview:tableData>')


def wl_xml(girdiler):
    """girdiler: (uri, tip, ad, parent_uri, transport) → `ioc:inactiveObjects` gövdesi.

    Başa bir transport-seviyesi girdi (boş ioc:object) eklenir; ayrıştırıcı onu atlamalıdır.
    """
    parca = ['<ioc:entry><ioc:object/><ioc:transport ioc:user="TESTUSER_B">'
             '<ioc:ref adtcore:uri="/sap/bc/adt/cts/transportrequests/TESTK900001" adtcore:type="/RQ" '
             'adtcore:name="TESTK900001"/></ioc:transport></ioc:entry>']
    for uri, tip, ad, ebeveyn, tr in girdiler:
        ea = f' adtcore:parentUri="{ebeveyn}"' if ebeveyn else ""
        trx = (f'<ioc:transport><ioc:ref adtcore:uri="/sap/bc/adt/cts/transportrequests/{tr}" '
               f'adtcore:type="/RK" adtcore:name="{tr}"/></ioc:transport>') if tr else "<ioc:transport/>"
        parca.append(f'<ioc:entry><ioc:object ioc:user="TESTUSER_A" ioc:deleted="false">'
                     f'<ioc:ref adtcore:uri="{uri}" adtcore:type="{tip}" adtcore:name="{ad}"{ea}/>'
                     f'</ioc:object>{trx}</ioc:entry>')
    return (f'<?xml version="1.0" encoding="utf-8"?><ioc:inactiveObjects xmlns:ioc="{IOC}" '
            f'xmlns:adtcore="{ADTCORE}">{"".join(parca)}</ioc:inactiveObjects>')


def wl_adlar(adlar):
    return wl_xml([(cls_uri(a), "CLAS/OC", a, "", "") for a in adlar])


_FG_URI = "/sap/bc/adt/functions/groups/zbc000_fm_demo"
WL_KARISIK = wl_xml([
    (cls_uri("ZCL_BC000_DEMO_A"), "CLAS/OC", "ZCL_BC000_DEMO_A", "", "TESTK900002"),
    (cls_uri("ZCL_BC000_DEMO_A") + "/source/main#type=CLAS%2FOM;name=RUN", "CLAS/OM", "RUN",
     cls_uri("ZCL_BC000_DEMO_A"), "TESTK900002"),
    (cls_uri("ZCL_BC000_DEMO_B"), "CLAS/OC", "ZCL_BC000_DEMO_B", "", ""),
    (_FG_URI, "FUGR/F", "ZBC000_FM_DEMO", "", ""),
    (_FG_URI + "/fmodules/zbc000_fm_demo", "FUGR/FF", "ZBC000_FM_DEMO", _FG_URI, "TESTK900003"),
])
BEKLENEN_KARISIK = [
    {"name": "ZCL_BC000_DEMO_A", "type": "CLAS/OC", "uri": cls_uri("ZCL_BC000_DEMO_A"),
     "user": "TESTUSER_A", "deleted": False, "transport": "TESTK900002"},
    {"name": "ZCL_BC000_DEMO_B", "type": "CLAS/OC", "uri": cls_uri("ZCL_BC000_DEMO_B"),
     "user": "TESTUSER_A", "deleted": False, "transport": ""},
    {"name": "ZBC000_FM_DEMO", "type": "FUGR/F", "uri": _FG_URI,
     "user": "TESTUSER_A", "deleted": False, "transport": ""},
    {"name": "ZBC000_FM_DEMO", "type": "FUGR/FF", "uri": _FG_URI + "/fmodules/zbc000_fm_demo",
     "user": "TESTUSER_A", "deleted": False, "transport": "TESTK900003"},
]
_ALAN = ("name", "type", "uri", "user", "deleted", "transport")


class _Yanit:
    def __init__(self, kod, metin=""):
        self.status_code, self.text, self.headers = kod, metin, {}


def _agac():
    """Canlı where-used ağacının biçimi: ENHO + sınıf (+tipsiz kullanım satırı) + 3 zincirli paket atası."""
    alt, orta, ust = pkg_uri("ZBC000_ALT"), pkg_uri("ZBC000"), pkg_uri("ZBC")
    return [
        (f"/sap/bc/adt/enhancements/{ENH.lower()}", alt, ENH, "ENHO/XHB"),
        (cls_uri(TUK), alt, TUK, "CLAS/OC"),
        (cls_uri(TUK) + "/source/main#start=10,5", cls_uri(TUK), TUK, None),
        (alt, orta, "ZBC000_ALT", "DEVC/K"),
        (orta, ust, "ZBC000", "DEVC/K"),
        (ust, None, "ZBC", "DEVC/K"),
    ]


class _SahteSap:
    """HTTP oturumu: quickSearch · worklist GET · usageReferences POST · datapreview."""

    verify = False

    def __init__(self):
        self.fm = {FM: FG}
        self.siniflar = {CLS, CLS_PAKET, CLS_BOS}
        self.ddls = {DDLS}
        self.refs = {cls_uri(CLS): _agac(),
                     cls_uri(CLS_PAKET): [(pkg_uri("ZBC000"), None, "ZBC000", "DEVC/K")]}
        self.sql = None
        self.worklist, self.worklist_kodu = wl_adlar([]), 200
        self.istekler: list = []

    def get(self, url, headers=None, params=None, timeout=None, **kw):
        yol = url.split("example.invalid", 1)[-1]
        self.istekler.append(("GET", yol, dict(params or {})))
        if yol.endswith("/informationsystem/search"):
            return self._arama(params or {})
        if yol.endswith("/activation/inactiveobjects"):
            return _Yanit(self.worklist_kodu, self.worklist)
        return _Yanit(404, "")

    def _arama(self, params):
        q = str(params.get("query", "")).upper()
        t = str(params.get("objectType") or "").upper()
        satir = []
        # Ölçülmüş sunucu davranışı: FUNC · FUNC/FF · FUGR/FF · filtresiz → FUGR/FF isabet; FUGR → 0
        if t in ("", "FUNC", "FUNC/FF", "FUGR/FF"):
            satir += [(a, "FUGR/FF", fm_uri(g, a)) for a, g in self.fm.items() if a == q]
        if t in ("", "CLAS", "CLAS/OC"):
            satir += [(a, "CLAS/OC", cls_uri(a)) for a in self.siniflar if a == q]
        # SENTETİK takma ad (ölçülmüş bir SAP iddiası DEĞİL): 'CDS' → DDLS/DF isabeti.
        # Yalnız istemci süzgeci elemesinin görünürlük dalını ölçmek içindir (U2).
        if t in ("", "CDS"):
            satir += [(a, "DDLS/DF", f"/sap/bc/adt/ddic/ddl/sources/{a.lower()}")
                      for a in self.ddls if a == q]
        govde = "".join(f'<adtcore:objectReference adtcore:uri="{u}" adtcore:type="{ty}" '
                        f'adtcore:name="{a}"/>' for a, ty, u in satir)
        return _Yanit(200, f'<?xml version="1.0"?><adtcore:objectReferences xmlns:adtcore="{ADTCORE}">'
                           f'{govde}</adtcore:objectReferences>')

    def usage(self, uri):
        self.istekler.append(("POST", "usageReferences", {"uri": uri}))
        ns = f'xmlns:usageReferences="http://www.sap.com/adt/ris/usageReferences" xmlns:adtcore="{ADTCORE}"'
        parca = []
        for u, ebeveyn, ad, tip in self.refs.get(uri, []):
            ea = f' usageReferences:parentUri="{ebeveyn}"' if ebeveyn else ""
            if tip:
                ic = f'<usageReferences:adtObject adtcore:name="{ad}" adtcore:type="{tip}"/>'
            else:
                ic = (f'<usageReferences:adtObject adtcore:name="{ad}"/>'
                      '<usageReferences:objectIdentifier/>')
            parca.append(f'<usageReferences:referencedObject usageReferences:uri="{u}"{ea}>'
                         f'{ic}</usageReferences:referencedObject>')
        return _Yanit(200, f'<?xml version="1.0"?><usageReferences:usageReferenceResult {ns}>'
                           f'{"".join(parca)}</usageReferences:usageReferenceResult>')


class _SahteAdt:
    search_objects = L.SAPADTClient.search_objects
    where_used = L.SAPADTClient.where_used
    MAX_SEARCH_RESULTS = 550

    def __init__(self, sap):
        self.url = "https://example.invalid:44300"
        self.session = sap
        self.timeout_short = 5
        self.debug_enabled = False

    def _get_headers(self, accept_type="application/vnd.sap.adt.core.v1+xml", content_type=None):
        return {"Accept": accept_type}

    def _debug(self, *_a, **_k):
        return None

    def _request_with_csrf_retry(self, method, url, headers=None, params=None, data=None, **kw):
        return self.session.usage((params or {}).get("uri"))

    def get_object_structure(self, url):
        if url.rstrip("/").rsplit("/", 1)[-1].upper() in self.session.siniflar:
            return "<class/>"
        raise L.SAPADTError("yok", status_code=404)

    def run_query(self, query, row_number=100):
        return self.session.sql(query, row_number)


def firlat(kod, govde):
    def _f(query, row_number=100):
        raise L.SAPADTError("Failed to run query", status_code=kod, response_text=govde)
    return _f


def tablo(kolon, toplam, istenen=None):
    """`rowNumber`'a UYAN emülatör (canlı: limit N → en fazla N satır); tabloda `toplam` satır var."""
    def _f(q, n):
        if istenen is not None:
            istenen.append(n)
        return dp_xml([kolon], [(f"A{i}",) for i in range(min(int(n), toplam))], toplam)
    return _f


def tadir_emul(sinir=15, dusen=None, kirpik=None, silinmis=(), istisna=None):
    """`adt_sql_query` yerine: ölçülmüş sınır modeli (> sinir ad → 400) + seçilebilir parça hatası."""
    cagrilar: list = []

    def _f(query, row_limit=100, **kw):
        adlar = re.findall(r"'([^']+)'", query)
        cagrilar.append(adlar)
        if istisna and istisna in adlar:
            raise RuntimeError("baglanti koptu")
        if len(adlar) > sinir:
            return {"ok": False, "error": "sorgu_kosmadi",
                    "message": "ADT data preview sorgusu KOŞMADI — [400] · SAP: uzun liste",
                    "sap_error": {"status_code": 400, "message": "uzun liste"}}
        if dusen and dusen in adlar:
            return {"ok": False, "error": "sorgu_kosmadi",
                    "message": "ADT data preview sorgusu KOŞMADI — SAP: parca reddedildi"}
        rows = [{"OBJ_NAME": a, "OBJECT": "CLAS", "DELFLAG": "X" if a in silinmis else ""}
                for a in adlar]
        return {"ok": True, "row_count": len(rows), "rows": rows,
                "truncated": bool(kirpik and kirpik in adlar)}
    return _f, cagrilar


_ESKI_ENV: dict = {}
_KOK: Path | None = None
Q = None


def setUpModule():
    global _KOK, Q
    _KOK = Path(tempfile.mkdtemp(prefix="axet_query_tools_"))
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


class _Taban(unittest.TestCase):
    ETIKET = ""

    def setUp(self):
        self._eski = (Q._get_client, Q.adt_sql_query)

    def tearDown(self):
        Q._get_client, Q.adt_sql_query = self._eski

    def kur(self):
        sap = _SahteSap()
        c = SC.SAPClient.__new__(SC.SAPClient)
        c.debug_enabled = False
        c.debug_log_path = None
        c.adt_client = _SahteAdt(sap)
        Q._get_client = lambda _c=c: _c
        return c, sap

    def cagir(self, fn, *a, **k):
        """Çökmeyi ölçüme çevir: istisna FAIL satırında görünür, testi ERROR'a düşürmez."""
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                return fn(*a, **k)
        except Exception as exc:  # noqa: BLE001
            return {"ok": None, "_exc": f"{type(exc).__name__}: {exc}"}

    def kaydet(self, ad, beklenen, gercek, ok):
        H.kaydet(f"{self.ETIKET} {ad}", beklenen, str(gercek)[:160], ok)
        self.assertTrue(ok, f"{ad}: {gercek}")

    def inaktif(self, govde, sql):
        _c, sap = self.kur()
        sap.worklist = govde
        if sql is not None:
            Q.adt_sql_query = sql
        return self.cagir(Q.adt_inactive_objects)


def _k(d):
    if not isinstance(d, dict):
        return repr(d)[:160]
    return {k: v for k, v in d.items() if k not in ("client_log", "results", "rows", "data",
                                                    "inactive_objects", "confirmed_live", "unverified")}


class SapHataGovdesi(_Taban):
    ETIKET = "SORGU-S"

    def test_S1_400_sap_sebebi_alt_katmanda(self):
        c, sap = self.kur()
        sap.sql = firlat(400, HATA400)
        d = self.cagir(c.run_sql_query, "SELECT land1, COUNT(*) FROM t005 GROUP BY land1", 10)
        h = getattr(c, "last_sql_error", None)
        ok = d is None and isinstance(h, dict) and h.get("status_code") == 400 and h.get("message") == SEBEP400
        self.kaydet("S1 400 sebep alt katmanda", "None + last_sql_error{400, sebep}", (d, h), ok)

    def test_S1b_kontrol_none_sozlesmesi_ve_error_satiri_aynen(self):
        c, sap = self.kur()
        sap.sql = firlat(400, HATA400)
        b = io.StringIO()
        with contextlib.redirect_stdout(b):
            d = c.run_sql_query("SELECT land1, COUNT(*) FROM t005 GROUP BY land1", 10)
        ok = d is None and "[ERROR] SQL query error: [400] Failed to run query" in b.getvalue()
        self.kaydet("S1b KONTROL None + [ERROR] satırı", "None + eski satır aynen", b.getvalue()[:120], ok)

    def test_S2_500_html_title_okunur(self):
        c, sap = self.kur()
        sap.sql = firlat(500, HTML500)
        self.cagir(c.run_sql_query, "SELECT land1 FROM t005", 10)
        h = getattr(c, "last_sql_error", None)
        ok = (isinstance(h, dict) and h.get("message") == "Application Server Error"
              and str(h.get("body_excerpt", "")).startswith("<!DOCTYPE html>"))
        self.kaydet("S2 500 HTML <title>", "message=Application Server Error", h, ok)

    def test_S3_mcp_400_sap_error_ve_message(self):
        _c, sap = self.kur()
        sap.sql = firlat(400, HATA400)
        r = self.cagir(Q.adt_sql_query, query="SELECT land1, COUNT(*) FROM t005 GROUP BY land1", row_limit=10)
        ok = (r.get("ok") is False and str((r.get("sap_error") or {}).get("message", "")).startswith("all expressions")
              and SEBEP400 in str(r.get("message")))
        self.kaydet("S3 MCP 400", "ok False + sap_error + sebep message'ta", _k(r), ok)

    def test_S7_kontrol_govdesiz_istisna_sap_error_uydurulmaz(self):
        _c, sap = self.kur()

        def _kopuk(q, n):
            raise RuntimeError("baglanti koptu")
        sap.sql = _kopuk
        r = self.cagir(Q.adt_sql_query, query="SELECT land1 FROM t005", row_limit=10)
        ok = r.get("ok") is False and "sap_error" not in r and bool(r.get("message"))
        self.kaydet("S7 KONTROL gövdesiz istisna", "ok False, sap_error YOK", _k(r), ok)

    def test_S9_kontrol_basarili_cagri_onceki_hatayi_tasimaz(self):
        c, sap = self.kur()
        sap.sql = firlat(400, HATA400)
        self.cagir(c.run_sql_query, "SELECT x FROM t000", 5)
        sap.sql = lambda q, n: dp_xml(["MANDT"], [("100",)], 1)
        self.cagir(c.run_sql_query, "SELECT mandt FROM t000", 5)
        h = getattr(c, "last_sql_error", "ATTR_YOK")
        self.kaydet("S9 KONTROL bayat hata yok", "last_sql_error None", h, h is None)


class Kirpma(_Taban):
    ETIKET = "SORGU-S"

    def test_S4_kirpma_kesin_ve_gorunur(self):
        _c, sap = self.kur()
        istenen: list = []
        sap.sql = tablo("LAND1", 249, istenen)
        r = self.cagir(Q.adt_sql_query, query="SELECT land1 FROM t005", row_limit=10)
        ok = (r.get("ok") is True and r.get("row_count") == 10 and len(r.get("rows") or []) == 10
              and r.get("truncated") is True and r.get("total_rows") == 249
              and bool(r.get("truncated_notice")) and istenen[-1:] == [11])
        self.kaydet("S4 kırpma kesin", "10 satır, truncated True, total 249, istenen 11", (_k(r), istenen), ok)

    def test_S4b_kontrol_tam_limit_kirpik_degil(self):
        _c, sap = self.kur()
        sap.sql = tablo("LAND1", 10)
        r = self.cagir(Q.adt_sql_query, query="SELECT land1 FROM t005 WHERE land1 LIKE 'A%'", row_limit=10)
        ok = (r.get("ok") is True and r.get("row_count") == 10 and r.get("truncated") is False
              and "truncated_notice" not in r)
        self.kaydet("S4b KONTROL 10/10 satır", "truncated False", _k(r), ok)

    def test_S5_kontrol_tam_sonuc_isaret_yok(self):
        _c, sap = self.kur()
        sap.sql = lambda q, n: dp_xml(["LAND1"], [("A1",), ("A2",), ("A3",)], 3)
        r = self.cagir(Q.adt_sql_query, query="SELECT land1 FROM t005 WHERE land1 LIKE 'A%'", row_limit=100)
        ok = (r.get("ok") is True and r.get("truncated") is False and "truncated_notice" not in r
              and "error" not in r and r.get("row_count") == 3)
        self.kaydet("S5 KONTROL tam sonuç", "truncated False, error yok", _k(r), ok)

    def test_S6_kontrol_aggregate_total_rows_turetilmez(self):
        _c, sap = self.kur()
        sap.sql = lambda q, n: dp_xml(["CNT"], [("249",)], 249)
        r = self.cagir(Q.adt_sql_query, query="SELECT COUNT(*) AS cnt FROM t005", row_limit=100)
        ok = r.get("ok") is True and r.get("truncated") is False and r.get("row_count") == 1
        self.kaydet("S6 KONTROL aggregate", "1 satır, truncated False", _k(r), ok)

    def test_S8_table_read_kirpma_ve_sap_error(self):
        _c, sap = self.kur()
        sap.sql = tablo("MANDT", 9)
        r2 = self.cagir(Q.adt_table_read, table="T000", row_limit=5)
        sap.sql = firlat(400, HATA400)
        r = self.cagir(Q.adt_table_read, table="T000", row_limit=5)
        etiket = ((r2.get("data") or {}).get("rows_labeled") or []) if isinstance(r2.get("data"), dict) else []
        ok = (r2.get("ok") is True and r2.get("truncated") is True and len(etiket) == 5
              and r.get("ok") is False and bool((r.get("sap_error") or {}).get("message")))
        self.kaydet("S8 table_read", "5 satır truncated True · 400 sap_error", (_k(r2), _k(r)), ok)

    def test_S8b_kontrol_table_read_tam_limit(self):
        _c, sap = self.kur()
        sap.sql = tablo("MANDT", 5)
        r = self.cagir(Q.adt_table_read, table="T000", row_limit=5)
        etiket = ((r.get("data") or {}).get("rows_labeled") or []) if isinstance(r.get("data"), dict) else []
        ok = r.get("ok") is True and r.get("truncated") is False and len(etiket) == 5
        self.kaydet("S8b KONTROL table_read 5/5", "truncated False", _k(r), ok)


class TadirParca(_Taban):
    ETIKET = "SORGU-T"

    def test_T1_kontrol_tum_parcalar_olculdu_ok(self):
        f, cg = tadir_emul(sinir=15)
        r = self.inaktif(wl_adlar(ADLAR25), f)
        ok = r.get("ok") is True and r.get("count") == 25 and r.get("count_verified") is True
        self.kaydet("T1 KONTROL 25 ad parçalı ölçüldü", "ok True count 25", _k(r), ok)

    def test_T1b_parca_en_fazla_5_ad_ve_her_ad_bir_kez(self):
        f, cg = tadir_emul(sinir=15)
        self.inaktif(wl_adlar(ADLAR25), f)
        sorulan = sorted(a for p in cg for a in p)
        ok = bool(cg) and max(len(p) for p in cg) <= 5 and sorulan == sorted(ADLAR25)
        self.kaydet("T1b parça boyu", "≤5 ve 25 ad tam bir kez", [len(p) for p in cg], ok)

    def test_T2_bir_parca_400_yalniz_kendi_adlari_null(self):
        f, _cg = tadir_emul(sinir=15, dusen=ADLAR25[12])
        r = self.inaktif(wl_adlar(ADLAR25), f)
        ok = (r.get("ok") is False and r.get("unverified_count") == 5 and r.get("confirmed_live_count") == 20
              and sorted(o["name"] for o in r.get("unverified") or []) == ADLAR25[10:15]
              and all(o.get("tadir_deleted") is None for o in r.get("unverified") or [])
              and "parca reddedildi" in str(r.get("tadir_check")) and "count" not in r)
        self.kaydet("T2 1 parça 400", "ok False · 5 null · 20 ölçülü · count YOK", _k(r), ok)

    def test_T3_kirpik_parca_olculmus_sayilmaz(self):
        f, _cg = tadir_emul(sinir=100, kirpik=ADLAR25[0])
        r = self.inaktif(wl_adlar(ADLAR25), f)
        ok = (r.get("ok") is False and r.get("unverified_count") == 5 and r.get("confirmed_live_count") == 20
              and sorted(o["name"] for o in r.get("unverified") or []) == ADLAR25[0:5]
              and "KIRPILDI" in str(r.get("tadir_check")) and "count" not in r)
        self.kaydet("T3 kırpık parça", "ok False · 5 null · KIRPILDI · count YOK", _k(r), ok)

    def test_T3b_parca_istisnasi_null(self):
        f, _cg = tadir_emul(sinir=100, istisna=ADLAR25[24])
        r = self.inaktif(wl_adlar(ADLAR25), f)
        ok = (r.get("ok") is False and r.get("unverified_count") == 5 and r.get("confirmed_live_count") == 20
              and "count" not in r)
        self.kaydet("T3b parça istisnası", "ok False · 5 null", _k(r), ok)

    def test_T4_kontrol_silinmis_hala_elenir(self):
        f, _cg = tadir_emul(sinir=100, silinmis={ADLAR25[0]})
        r = self.inaktif(wl_adlar(ADLAR25[:2]), f)
        ok = r.get("ok") is True and r.get("count") == 1 and r.get("stale_deleted_count") == 1
        self.kaydet("T4 KONTROL silinmiş elenir", "count 1 stale 1", _k(r), ok)

    def test_T5_kontrol_tadir_satiri_olmayan_ad_davranisi_aynen(self):
        yok = {ADLAR25[1], ADLAR25[3]}
        _c, sap = self.kur()
        sap.worklist = wl_adlar(ADLAR25[:5])
        sap.sql = lambda q, n: dp_xml(["OBJ_NAME", "OBJECT", "DELFLAG"],
                                      [(a, "CLAS", "") for a in re.findall(r"'([^']+)'", q) if a not in yok],
                                      3)
        r = self.cagir(Q.adt_inactive_objects)
        durum = {o.get("name"): o.get("tadir_deleted") for o in r.get("inactive_objects") or []}
        ok = r.get("ok") is True and r.get("count") == 5 and len(durum) == 5 and all(v is False for v in durum.values())
        self.kaydet("T5 KONTROL eksik satır kırpık değil", "ok True count 5, hepsi False", (_k(r), durum), ok)

    def test_T6_uctan_uca_sonda_satiri_kirpik(self):
        _c, sap = self.kur()
        sap.worklist = wl_adlar(ADLAR25[:5])
        sap.sql = lambda q, n: dp_xml(["OBJ_NAME", "OBJECT", "DELFLAG"],
                                      [(ADLAR25[0], "CLAS", "")] * min(int(n), 500), 500)
        r = self.cagir(Q.adt_inactive_objects)
        ok = (r.get("ok") is False and r.get("unverified_count") == 5
              and "KIRPILDI" in str(r.get("tadir_check")) and "count" not in r)
        self.kaydet("T6 uçtan uca kırpık", "ok False · 5 null · KIRPILDI", _k(r), ok)


class AramaTakmaAdi(_Taban):
    ETIKET = "SORGU-U"

    def test_U1_fm_takma_adlari_bulunur(self):
        sonuc = {}
        for tip in ("FUNC", "FUNC/FF", "func", "function"):
            self.kur()
            r = self.cagir(Q.adt_search_objects, FM, object_type=tip)
            sonuc[tip] = (r.get("count"), r.get("object_type_sent"))
        ok = all(v == (1, "FUGR/FF") for v in sonuc.values())
        self.kaydet("U1 FM takma adları", "hepsi (1, FUGR/FF)", sonuc, ok)

    def test_U2_suzgec_elemesi_gorunur(self):
        self.kur()
        r = self.cagir(Q.adt_search_objects, DDLS, object_type="CDS")
        ok = (r.get("ok") is True and r.get("count") == 0 and r.get("type_filter_dropped") == 1
              and r.get("server_hit_count") == 1 and "ANLAMINA GELMEZ" in str(r.get("warning")))
        self.kaydet("U2 süzgeç elemesi", "count 0 + dropped 1 + warning", _k(r), ok)

    def test_U2b_sap_client_uyari_satiri(self):
        c, _sap = self.kur()
        b = io.StringIO()
        with contextlib.redirect_stdout(b):
            try:
                cl = c.search_objects(DDLS, 20, "CDS")
            except Exception as exc:  # noqa: BLE001
                cl = repr(exc)
        ok = cl == [] and "[UYARI] Sunucu 1 isabet" in b.getvalue()
        self.kaydet("U2b SAPClient uyarı satırı", "[] + [UYARI] Sunucu 1 isabet", b.getvalue()[-160:], ok)

    def _refs(self, sap, n, tip="CLAS/OC"):
        """Sunucuyu n adet objectReference dönecek şekilde sabitler (kırpma dalını ölçmek için)."""
        govde = "".join('<adtcore:objectReference adtcore:uri="/x/%d" adtcore:type="%s" '
                        'adtcore:name="ZA%03d"/>' % (i, tip, i) for i in range(n))
        sap._arama = lambda params: _Yanit(
            200, '<?xml version="1.0"?><adtcore:objectReferences xmlns:adtcore="%s">%s'
                 '</adtcore:objectReferences>' % (ADTCORE, govde))

    def test_U7_tavana_dayanan_sonuc_truncated_isaretlenir(self):
        """K3: kırpılmış liste SESSİZ kalmaz — 'bulunamadı' ile 'kesildi' ayırt edilebilmeli."""
        _c, sap = self.kur()
        self._refs(sap, 7)
        r = self.cagir(Q.adt_search_objects, "ZA*", max_results=7)
        ok = (r.get("ok") is True and r.get("count") == 7 and r.get("truncated") is True
              and r.get("max_results") == 7 and r.get("server_hit_count") == 7
              and "EKSİK olabilir" in str(r.get("truncated_notice")))
        self.kaydet("U7 tavana dayanan sonuç", "truncated True + notice", _k(r), ok)

    def test_U8_kontrol_tavanin_altinda_truncated_false(self):
        """KONTROL (PATTERN #19): aynı yol, tavanın ALTINDA — truncated False, notice YOK.

        Bu satır olmadan 'her sonuçta truncated:true bas' diyen bir düzeltme de geçerdi."""
        _c, sap = self.kur()
        self._refs(sap, 3)
        r = self.cagir(Q.adt_search_objects, "ZA*", max_results=7)
        ok = (r.get("ok") is True and r.get("count") == 3 and r.get("truncated") is False
              and "truncated_notice" not in r)
        self.kaydet("U8 KONTROL tavan altı", "truncated False, notice yok", _k(r), ok)

    def test_U9_suzgec_elemesi_kirpma_ile_birlikte(self):
        """En tehlikeli bileşim: count 0 + kırpılmış sayfa. İKİ uyarı da çıkmalı."""
        _c, sap = self.kur()
        self._refs(sap, 4, tip="DDLS/DF")
        r = self.cagir(Q.adt_search_objects, "ZA*", max_results=4, object_type="CLAS")
        ok = (r.get("count") == 0 and r.get("truncated") is True
              and r.get("type_filter_dropped") == 4
              and "ANLAMINA GELMEZ" in str(r.get("warning"))
              and "EKSİK olabilir" in str(r.get("truncated_notice")))
        self.kaydet("U9 eleme + kırpma", "count 0 · truncated True · iki uyarı", _k(r), ok)

    def test_U3_kontrol_tam_adt_tipi_uyari_yok(self):
        self.kur()
        r = self.cagir(Q.adt_search_objects, CLS, object_type="CLAS/OC")
        ok = r.get("count") == 1 and r.get("type_filter_dropped") == 0 and "warning" not in r
        self.kaydet("U3 KONTROL CLAS/OC", "count 1, dropped 0, warning yok", _k(r), ok)

    def test_U4_kontrol_filtresiz(self):
        self.kur()
        r = self.cagir(Q.adt_search_objects, FM)
        ok = r.get("count") == 1 and r.get("object_type_sent") is None and "warning" not in r
        self.kaydet("U4 KONTROL filtresiz", "count 1, sent None", _k(r), ok)

    def test_U5_kontrol_resolver_degismedi(self):
        c, sap = self.kur()
        fm = self.cagir(c.resolve_function_module, FM)
        tipler = [p.get("objectType") for m, y, p in sap.istekler if y.endswith("/search")]
        ok = isinstance(fm, dict) and fm.get("status") == "found" and tipler == ["FUGR/FF"]
        self.kaydet("U5 KONTROL resolver", "found + yalnız FUGR/FF sorulur", (fm, tipler), ok)

    def test_U6_kontrol_sunucunun_gercek_sifiri_sessiz(self):
        self.kur()
        r = self.cagir(Q.adt_search_objects, FM, object_type="FUGR")
        ok = r.get("count") == 0 and r.get("type_filter_dropped") == 0 and "warning" not in r
        self.kaydet("U6 KONTROL FUGR gerçek sıfır", "count 0, dropped 0, warning yok", _k(r), ok)


class WhereUsedPaket(_Taban):
    ETIKET = "SORGU-V"

    def test_V1_agac_count_yalniz_obje(self):
        self.kur()
        r = self.cagir(Q.adt_where_used, CLS, "class")
        tipler = sorted(x["type"] for x in r.get("references") or [])
        ok = (r.get("ok") is True and r.get("count") == 2 and r.get("package_count") == 3
              and tipler == ["CLAS/OC", "ENHO/XHB"])
        self.kaydet("V1 ağaç", "count 2 (ENHO+CLAS), 3 paket ayrı", (_k(r), tipler), ok)

    def test_V2_yalniz_paket_ok_false(self):
        self.kur()
        r = self.cagir(Q.adt_where_used, CLS_PAKET, "class")
        ok = r.get("ok") is False and r.get("error") == "where_used_belirsiz" and "count" not in r
        self.kaydet("V2 yalnız paket", "ok False where_used_belirsiz, count YOK", _k(r), ok)

    def test_V3_kontrol_bos_agac_sifir_cagiran(self):
        self.kur()
        r = self.cagir(Q.adt_where_used, CLS_BOS, "class")
        ok = r.get("ok") is True and r.get("count") == 0 and r.get("existence_verified") is True
        self.kaydet("V3 KONTROL boş ağaç", "ok True count 0 existence_verified", _k(r), ok)

    def test_V4_impact_paketleri_saymaz_izlemez(self):
        _c, sap = self.kur()
        r = self.cagir(Q.adt_impact_analysis, CLS, "class", max_depth=2)
        post = [p.get("uri") for m, y, p in sap.istekler if m == "POST"]
        ok = (r.get("ok") is True and r.get("impacted_count") == 2 and r.get("packages_skipped") == 3
              and not any("/packages/" in str(u) for u in post))
        self.kaydet("V4 impact", "impacted 2, packages_skipped 3, paket POST yok", (_k(r), post), ok)


class WorklistKanonik(_Taban):
    ETIKET = "SORGU-X"

    def test_X1_kanonik_ayristirici_alanlari(self):
        k = self.cagir(L.aktivasyon_worklist_ayristir, WL_KARISIK)
        ff = [x for x in k if x.get("type") == "FUGR/FF"] if isinstance(k, list) else []
        om = [x for x in k if x.get("type") == "CLAS/OM"] if isinstance(k, list) else []
        ok = (isinstance(k, list) and len(k) == 5 and len(ff) == 1 and len(om) == 1
              and (ff[0].get("user"), ff[0].get("deleted"), ff[0].get("transport"))
              == ("TESTUSER_A", False, "TESTK900003")
              and ff[0].get("parent_uri") == _FG_URI and om[0].get("transport") == "TESTK900002")
        self.kaydet("X1 kanonik alanlar", "5 girdi, FF user/deleted/transport", k, ok)

    def test_X3_mcp_kanonik_liste(self):
        f, _cg = tadir_emul(sinir=100)
        r = self.inaktif(WL_KARISIK, f)
        mcp = [{k: o.get(k) for k in _ALAN} for o in r.get("inactive_objects") or []]
        ok = r.get("ok") is True and mcp == BEKLENEN_KARISIK
        self.kaydet("X3 MCP liste", "F ve FF ayrı, OM ve transport girdisi yok", (_k(r), mcp), ok)

    def test_X4_kablolama_nobetci(self):
        asil = L.aktivasyon_worklist_ayristir
        nobet = [{"name": "ZCL_BC000_NOBETCI", "type": "CLAS/OC", "uri": cls_uri("ZCL_BC000_NOBETCI"),
                  "parent_uri": "", "user": "TESTUSER_N", "deleted": False, "transport": ""}]
        L.aktivasyon_worklist_ayristir = lambda govde: [dict(x) for x in nobet]
        try:
            f, _cg = tadir_emul(sinir=100)
            r = self.inaktif(WL_KARISIK, f)
        finally:
            L.aktivasyon_worklist_ayristir = asil
        adlar = [o.get("name") for o in r.get("inactive_objects") or []]
        ok = adlar == ["ZCL_BC000_NOBETCI"]
        self.kaydet("X4 kablolama", "MCP kanonik ayrıştırıcıyı izler", (_k(r), adlar), ok)

    def test_X5_ioc_olmayan_govde_ok_false(self):
        r = self.inaktif("<root/>", tadir_emul(sinir=100)[0])
        ok = r.get("ok") is False and r.get("error") == "worklist_govdesi_degil" and "count" not in r
        self.kaydet("X5 ioc olmayan gövde", "ok False worklist_govdesi_degil", _k(r), ok)

    def test_X6_kontrol_html_govde_ok_false(self):
        r = self.inaktif("<html><body>Logon</body></html", tadir_emul(sinir=100)[0])
        ok = r.get("ok") is False and "count" not in r
        self.kaydet("X6 KONTROL bozuk HTML", "ok False", _k(r), ok)


class TadirAdSuzgeci(_Taban):
    """TADIR sorgusuna uygun olmayan ad (ör. `-` içeren) sorulmaz; sorulmayan ad ölçülmüş SAYILMAZ."""

    ETIKET = "SORGU-T"

    def test_T7_kontrol_bos_worklist_ok_sifir_sql_yok(self):
        f, cg = tadir_emul(sinir=100)
        r = self.inaktif(wl_adlar([]), f)
        ok = r.get("ok") is True and r.get("count") == 0 and cg == []
        self.kaydet("T7 KONTROL boş worklist", "ok True · count 0 · 0 SQL", (_k(r), cg), ok)

    def test_T8_yalniz_suzgece_takilan_ad_ok_false(self):
        f, cg = tadir_emul(sinir=100)
        r = self.inaktif(wl_xml([(cls_uri("zcl-x"), "CLAS/OC", "ZCL-X", "", "")]), f)
        durum = [(o.get("name"), o.get("tadir_deleted")) for o in r.get("unverified") or []]
        ok = (r.get("ok") is False and r.get("error") == "tadir_kontrolu_belirsiz" and "count" not in r
              and durum == [("ZCL-X", None)] and cg == [])
        self.kaydet("T8 yalnız süzgece takılan ad", "ok False · tadir_deleted [None] · 0 SQL", (_k(r), durum, cg), ok)

    def test_T9_karisik_yalniz_uygun_ad_sorulur(self):
        f, cg = tadir_emul(sinir=100)
        r = self.inaktif(wl_xml([(cls_uri("zcl-x"), "CLAS/OC", "ZCL-X", "", ""),
                                 (cls_uri("zcl_ok"), "CLAS/OC", "ZCL_OK", "", "")]), f)
        durum = [(o.get("name"), o.get("tadir_deleted")) for o in r.get("unverified") or []]
        ok = (r.get("ok") is False and r.get("error") == "tadir_kontrolu_belirsiz" and "count" not in r
              and cg == [["ZCL_OK"]] and durum == [("ZCL-X", None)] and r.get("confirmed_live_count") == 1)
        self.kaydet("T9 karışık liste", "ok False · yalnız ZCL_OK sorulur · ZCL-X null", (_k(r), durum, cg), ok)

    def test_T10_bos_200_govde_ok_false(self):
        f, cg = tadir_emul(sinir=100)
        r = self.inaktif("", f)
        ok = r.get("ok") is False and r.get("error") == "unexpected" and "count" not in r and cg == []
        self.kaydet("T10 boş 200 gövde", "ok False · unexpected", _k(r), ok)


class SapHataGovdesiSiniri(_Taban):
    ETIKET = "SORGU-S"

    def test_S10_body_excerpt_siniri(self):
        uzun = "<html><head><title>Uzun Hata</title></head><body>" + "A" * 900 + "</body></html>"
        try:
            firlat(500, uzun)("SELECT x FROM t000")
            h = None
        except L.SAPADTError as exc:
            h = SC.sap_hata_govdesi(exc)
        ok = (isinstance(h, dict) and len(uzun) > SC.SAP_HATA_GOVDE_SINIRI == 500
              and len(h.get("body_excerpt") or "") == SC.SAP_HATA_GOVDE_SINIRI
              and uzun.startswith(h.get("body_excerpt") or "-") and h.get("message") == "Uzun Hata")
        self.kaydet("S10 body_excerpt 500 bayt sınırı", "500 bayt · message=title",
                    (len(uzun), len((h or {}).get("body_excerpt") or ""), (h or {}).get("message")), ok)

    def test_S10b_kontrol_kisa_govde_aynen(self):
        try:
            firlat(400, HATA400)("SELECT x FROM t000")
            h = None
        except L.SAPADTError as exc:
            h = SC.sap_hata_govdesi(exc)
        ok = isinstance(h, dict) and h.get("body_excerpt") == HATA400 and len(HATA400) < 500
        self.kaydet("S10b KONTROL kısa gövde kırpılmaz", "gövde aynen", len((h or {}).get("body_excerpt") or ""), ok)


if __name__ == "__main__":
    unittest.main()
