# -*- coding: utf-8 -*-
"""Uyum turu 8 — küçük lib düzeltmeleri (süreç içi; ağ yalnız 127.0.0.1 sahte sunucusuna).

  · H — `find_ghost_transports` (kaynak çekirdek 1228623): okunamayan liste `[]` DEĞİL `SAPADTError`;
        `[]` yalnız geçerli boş yanıtta; değer `<dp:data>` eleman METNİNDEN okunur. + revizyon tablo eşlemesi.
  · B — `set_object_source` biçim döngüsü (d7f2fa0): sonraki transport biçimine YALNIZ biçim reddinde
        (409/412/"Parameter … could not be found") geçilir; içerik reddi (400) → tek PUT + DURDU; son biçimdeki
        "Parameter" reddi sahte `True` değil; hata metni tüm denemeleri taşır.
  · O — ADT oturumu best-effort kapatma (2fd6e11): çerezsiz oturumda ağ çağrısı yok; ICF logoff; 404 → bağlam
        düşürme; SAML'de logoff yok; erişilemez sunucu → istisna yok, çerez değeri çıktıda yok.
  · Q — SQL süresi milisaniye (2fd6e11): istemci `execution_time_ms`; araç alanı aynen taşır.
"""
from __future__ import annotations

import contextlib
import io
import os
import shutil
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import _helpers as H

sys.dont_write_bytecode = True
if str(H.SCRIPTS) not in sys.path:
    sys.path.insert(0, str(H.SCRIPTS))

import sapadt  # noqa: E402,F401
import requests  # noqa: E402
import sap_adt_lib as L  # noqa: E402

DP = 'xmlns:dataPreview="http://www.sap.com/adt/dataPreview"'


class _Y:
    def __init__(self, kod, govde=""):
        self.status_code, self.text = kod, govde
        self.content = govde.encode("utf-8")
        self.headers = {}


def _istemci():
    c = L.SAPADTClient.__new__(L.SAPADTClient)
    c.url = "http://sahte.invalid"
    c.user = "SAP_USER_A"
    c.client = "100"
    c.csrf_token = "T"
    c.debug_enabled = False
    c.timeout_default = c.timeout_short = 5
    c._get_headers = lambda *a, **k: {}
    return c


# ─────────────────────────── H — hayalet transport ───────────────────────────
def _veri(sutun_ad="TRKORR", degerler=("SAHK900111",), toplam=None, sutunlu=True):
    if not sutunlu:
        t = f"<dataPreview:totalRows>{toplam}</dataPreview:totalRows>" if toplam is not None else ""
        return f"<dataPreview:tableData {DP}>{t}</dataPreview:tableData>"
    hucre = "".join(f"<dataPreview:data>{d}</dataPreview:data>" for d in degerler)
    return (f"<dataPreview:tableData {DP}><dataPreview:totalRows>{len(degerler)}</dataPreview:totalRows>"
            f"<dataPreview:columns><dataPreview:metadata dataPreview:name=\"{sutun_ad}\"/>"
            f"<dataPreview:dataSet>{hucre}</dataPreview:dataSet></dataPreview:columns></dataPreview:tableData>")


class H_Hayalet(unittest.TestCase):
    def _kos(self, yanit):
        c = _istemci()

        class _O:
            def post(self, *a, **k):
                if isinstance(yanit, Exception):
                    raise yanit
                return yanit
        c.session = _O()
        try:
            return c.find_ghost_transports()
        except L.SAPADTError as e:
            return ("HATA", str(e)[:60])

    def test_H_okunamayan_hata_bos_yalniz_gecerli(self):
        hata = [self._kos(_Y(500, "x")), self._kos(requests.exceptions.ConnectionError("yok")),
                self._kos(_Y(200, "<html>giris</html")), self._kos(_Y(200, _veri(sutunlu=False))),
                self._kos(_Y(200, _veri(sutun_ad="AS4TEXT")))]
        bos = [self._kos(_Y(200, _veri(degerler=()))), self._kos(_Y(200, _veri(sutunlu=False, toplam=0)))]
        dolu = self._kos(_Y(200, _veri(degerler=("SAHK900111", "SAHK900112"))))
        ok = (all(isinstance(h, tuple) and h[0] == "HATA" for h in hata) and bos == [[], []]
              and dolu == ["SAHK900111", "SAHK900112"])
        H.kaydet("H hayalet transport okunamadı ≠ yok", "5 HATA · 2 [] · dolu liste",
                 f"{[h[0] if isinstance(h, tuple) else h for h in hata]} {bos} {dolu}", ok)
        self.assertTrue(ok, (hata, bos, dolu))

    def test_H_revizyon_tablo_ucu(self):
        import object_types as OT
        ok = OT.get_object_url("ZSD001_T", "tabl") == "/sap/bc/adt/ddic/tables/zsd001_t" == \
            OT.get_object_url("ZSD001_T", "table")
        H.kaydet("H revizyon tablo ucu (1228623 list_revisions eşlemesi)", "ddic/tables", str(ok), ok)
        self.assertTrue(ok)


# ─────────────────────────── B — biçim döngüsü ───────────────────────────
PARAM = "Parameter corrNr could not be found"
ICERIK = ('<exc:exception xmlns:exc="http://www.sap.com/abapxml/types/communicationframework">'
          '<type id="OO_SOURCE_BASED"/><message lang="EN">Kaynak taramasi reddetti</message>'
          '<properties><entry key="T100KEY-ID">OO_SOURCE_BASED</entry><entry key="T100KEY-NO">011</entry>'
          '</properties></exc:exception>')


class B_BicimDongusu(unittest.TestCase):
    def _kos(self, kodlar):
        c = _istemci()
        kuyruk = list(kodlar)
        c.iz = []

        def istek(metod, url, **kw):
            k, g = kuyruk.pop(0)
            c.iz.append(k)
            return _Y(k, g)
        c._request_with_csrf_retry = istek
        c.session = None
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                return c.set_object_source("/sap/bc/adt/oo/classes/zsd001_cl_x/source/main", "x", "LH",
                                           transport="SAHK900001", etag="E1"), c.iz
            except L.SAPADTError as e:
                return e, c.iz

    def test_B_icerik_reddinde_durur(self):
        r, iz = self._kos([(400, ICERIK), (409, "kilit"), (409, "kilit"), (409, "kilit")])
        ok = (isinstance(r, L.SAPADTError) and iz == [400] and "DURDU" in str(r)
              and len(r.denemeler) == 1 and "OO_SOURCE_BASED" in str(r))
        H.kaydet("B içerik reddi (400) → tek PUT + DURDU", "iz=[400] · 1 deneme", f"{iz} {getattr(r, 'denemeler', '')}", ok)
        self.assertTrue(ok)

    def test_B_bicim_reddinde_devam_ve_basari(self):
        r, iz = self._kos([(409, "kilit"), (200, "")])
        r2, iz2 = self._kos([(400, PARAM),(412, "etag"), (200, "")])
        ok = r is True and iz == [409, 200] and r2 is True and iz2 == [400, 412, 200]
        H.kaydet("B biçim reddi (409/412/Parameter) → sonraki biçim", "2. ve 3. biçimde başarı", f"{iz} {iz2}", ok)
        self.assertTrue(ok)

    def test_B_hata_ayrintisi_yanita_temizlenmis(self):
        import sap_client as SC
        r, _iz = self._kos([(400, ICERIK)])
        r.denemeler = [("X-sap-adt-transport header only", 400, "sahte-host.invalid SAP_USER_A Gizli-Parola-1")]
        r.t100_degiskenleri = {"T100KEY-V4": "SAP_USER_A"}

        class _A:
            url, user, password = "https://sahte-host.invalid:44300", "SAP_USER_A", "Gizli-Parola-1"
        sonuc = {"success": False, "error": "x"}
        SC._hata_ayrintisi_ekle(sonuc, r, _A())
        metin = str(sonuc)
        ok = (sonuc.get("put_denemeleri", [[None, None]])[0][1] == 400 and "sahte-host.invalid" not in metin
              and "Gizli-Parola-1" not in metin and "error_response_text" in sonuc and sonuc["success"] is False)
        H.kaydet("B push hata ayrıntısı yanıta temizlenmiş girer", "kod aynen · host/parola yok",
                 metin[:120], ok)
        self.assertTrue(ok, metin)

    def test_B_son_bicim_parameter_sahte_basari_degil(self):
        r, iz = self._kos([(400, PARAM)] * 4)
        ok = isinstance(r, L.SAPADTError) and iz == [400] * 4 and len(r.denemeler) == 4 and "4 attempts" in str(r)
        H.kaydet("B son biçimde Parameter reddi → hata (sahte True yok)", "SAPADTError · 4 deneme",
                 f"{type(r).__name__} {iz}", ok)
        self.assertTrue(ok)


# ─────────────────────────── O — oturum kapatma ───────────────────────────
class _Sunucu:
    def __init__(self, logoff_kod=200):
        self.istekler = []
        dis = self

        class _H(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                dis.istekler.append((self.path, self.headers.get("x-sap-adt-sessiontype")))
                kod = dis.logoff_kod if self.path.startswith(L.ICF_LOGOFF_YOLU) else 200
                self.send_response(kod)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *a):
                pass
        self.logoff_kod = logoff_kod
        self.srv = HTTPServer(("127.0.0.1", 0), _H)
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def kapat(self):
        self.srv.shutdown()
        self.srv.server_close()


def _oturum(*cerezler):
    s = requests.Session()
    s.trust_env = False
    for ad in cerezler:
        s.cookies.set(ad, "GIZLI-CEREZ-DEGERI", domain="127.0.0.1", path="/")
    return s


class O_OturumKapatma(unittest.TestCase):
    def test_O_dallar(self):
        sv = _Sunucu()
        try:
            r_yok = L._oturumu_kapat(_oturum(), sv.url, False, "test")
            n_yok = len(sv.istekler)
            r_icf = L._oturumu_kapat(_oturum("SAP_SESSIONID_X_100", "sap-contextid"), sv.url, False, "test")
            iz_icf = list(sv.istekler)
            sv.istekler.clear()
            r_saml = L._oturumu_kapat(_oturum("SAP_SESSIONID_X_100", "sap-contextid"), sv.url, True, "test")
            iz_saml = list(sv.istekler)
            sv.istekler.clear()
            sv.logoff_kod = 404
            r_404 = L._oturumu_kapat(_oturum("SAP_SESSIONID_X_100", "sap-contextid"), sv.url, False, "test")
            iz_404 = list(sv.istekler)
        finally:
            sv.kapat()
        ok = (r_yok == "oturum-yok" and n_yok == 0 and r_icf == "icf-logoff" and iz_icf[0][0].startswith(L.ICF_LOGOFF_YOLU)
              and r_saml == "baglam-dusuruldu" and all(not p.startswith(L.ICF_LOGOFF_YOLU) for p, _ in iz_saml)
              and iz_saml[0][1] == "stateless" and r_404 == "baglam-dusuruldu" and len(iz_404) == 2)
        H.kaydet("O oturum kapatma dalları", "yok(ağsız) · icf · saml→bağlam · 404→bağlam",
                 f"{r_yok}/{n_yok} {r_icf} {r_saml} {r_404}", ok)
        self.assertTrue(ok, (iz_icf, iz_saml, iz_404))

    def test_O_erisilemez_istisna_yok_cerez_sizmaz(self):
        sv = _Sunucu()
        url = sv.url
        sv.kapat()
        hata = io.StringIO()
        with contextlib.redirect_stderr(hata):
            r = L._oturumu_kapat(_oturum("SAP_SESSIONID_X_100"), url, False, "test")
        metin = hata.getvalue()
        ok = r.startswith("basarisiz:") and "GIZLI-CEREZ-DEGERI" not in metin and metin.count("\n") <= 1
        H.kaydet("O erişilemez sunucu", "basarisiz · istisna yok · çerez değeri yok", f"{r} {metin.strip()[:60]}", ok)
        self.assertTrue(ok)


# ─────────────────────────── U — URL yol parçası kodlama ───────────────────────────
class U_UrlKodlama(unittest.TestCase):
    """`/NS/` adı yol parçasında `url_segmenti` ile kodlanır (`%2Fns%2F…`); Z adı AYNEN (negatif kontrol)."""

    def _domain_url(self, ad):
        c = _istemci()
        c.client, c.language = "100", "TR"
        gorulen = []

        class _O:
            def get(self, url, **k):
                gorulen.append(url)
                return _Y(404, "")
        c.session = _O()
        try:
            c._get_domain_typeinfo(ad)
        except Exception:
            pass
        return gorulen[0].replace(c.url, "") if gorulen else None

    def _classrun_url(self, ad):
        import sap_client as SC
        sc = SC.SAPClient.__new__(SC.SAPClient)
        gorulen = []

        class _A:
            url = "http://sahte.invalid"

            def _get_headers(self, **k):
                return {}

            def _request_with_csrf_retry(self, metod, url, **k):
                gorulen.append(url)
                return _Y(404, "")
        sc.adt_client = _A()
        sc._diagnose_classrun_binding(ad)
        return gorulen[0].replace(_A.url, "") if gorulen else None

    def test_U_ns_kodlu_z_aynen(self):
        d_ns, d_z = self._domain_url("/NSX/DOMA"), self._domain_url("ZSD001_DOMA")
        c_ns, c_z = self._classrun_url("/NSX/CL_RUN"), self._classrun_url("ZSD001_CL_RUN")
        ok = (d_ns == "/sap/bc/adt/ddic/domains/%2Fnsx%2Fdoma" and d_z == "/sap/bc/adt/ddic/domains/zsd001_doma"
              and c_ns == "/sap/bc/adt/oo/classes/%2Fnsx%2Fcl_run/source/main"
              and c_z == "/sap/bc/adt/oo/classes/zsd001_cl_run/source/main")
        H.kaydet("U /NS/ yol parçası kodlu · Z aynen", "%2Fnsx%2F… · zsd001_…", f"{d_ns} {d_z} {c_ns} {c_z}", ok)
        self.assertTrue(ok)

    def test_U_kablolama_kodsuz_url_kalmadi(self):
        import re
        import sap_client as SC
        desen = re.compile(r"\{[a-z_][a-z_0-9]*\.lower\(\)\}")
        kalan = []
        for mod in (L, SC):
            for i, satir in enumerate(Path(mod.__file__).read_text(encoding="utf-8").split("\n"), 1):
                if desen.search(satir) and not satir.lstrip().startswith("#"):
                    kalan.append((Path(mod.__file__).name, i, satir.strip()[:40]))
        # Bilinçli kalan iki satır yol değil KAYNAK METNİ: `define table <ad>` · `type-pool <ad>`.
        ok = len(kalan) == 2 and all(k[2].startswith(("define table", "source_code = f\"type-pool")) for k in kalan)
        H.kaydet("U kablolama: kodsuz {ad.lower()} yol parçası yok", "yalnız 2 kaynak-metni satırı", str(kalan), ok)
        self.assertTrue(ok, kalan)


# ─────────────────────────── Q — SQL süresi ms ───────────────────────────
class Q_SqlSure(unittest.TestCase):
    def test_Q_istemci_ve_arac_ms(self):
        import sap_client as SC
        c = SC.SAPClient.__new__(SC.SAPClient)

        class _A:
            def run_query(self, q, row_number=100):
                return (f"<dataPreview:tableData {DP}><dataPreview:totalRows>1</dataPreview:totalRows>"
                        "<dataPreview:queryExecutionTime>24.407</dataPreview:queryExecutionTime>"
                        "<dataPreview:columns><dataPreview:metadata dataPreview:name=\"CNT\"/>"
                        "<dataPreview:dataSet><dataPreview:data>3</dataPreview:data></dataPreview:dataSet>"
                        "</dataPreview:columns></dataPreview:tableData>")
        c.adt_client = _A()
        with contextlib.redirect_stdout(io.StringIO()):
            d = c.run_sql_query("SELECT COUNT(*) AS cnt FROM zsd001_t")
        ok1 = isinstance(d, dict) and d.get("execution_time_ms") == 24.407 == d.get("execution_time")

        from sapadt.tools import atom, query
        kok = Path(tempfile.mkdtemp(prefix="axet_sqlms_"))
        eski_env = {k: os.environ.get(k) for k in ("AXET_SAP_PROJECT_DIR", "ADT_SAP_TIER")}
        eski = (atom._get_client, query._get_client)
        try:
            os.environ.pop("ADT_SAP_TIER", None)
            os.environ["AXET_SAP_PROJECT_DIR"] = str(H.make_project(kok, "p"))

            class _C:
                def run_sql_query(self, q, max_rows=100):
                    return {"columns": ["CNT"], "data": [["3"]], "total_rows": 1, "execution_time": 24.407,
                            "execution_time_ms": 24.407}
            atom._get_client = query._get_client = lambda: _C()
            r = query.adt_sql_query("SELECT COUNT(*) AS cnt FROM zsd001_t")
        finally:
            atom._get_client, query._get_client = eski
            for k, v in eski_env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
            shutil.rmtree(kok, ignore_errors=True)
        ok = ok1 and r.get("ok") is True and r.get("execution_time_ms") == 24.407
        H.kaydet("Q SQL süresi ms", "istemci 24.407 ms · araç alanı taşır", f"{d.get('execution_time_ms')} {r.get('execution_time_ms')} {r.get('error')}", ok)
        self.assertTrue(ok, r)


if __name__ == "__main__":
    unittest.main()
