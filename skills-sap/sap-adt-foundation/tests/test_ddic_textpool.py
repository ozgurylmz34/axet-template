# -*- coding: utf-8 -*-
"""Z38 adt_table_create · Z40 adt_ttyp_create · Z39 adt_textpool_write — süreç içi, SAHTE istemci (ağ yok).

Sahte ADT oturumu her HTTP çağrısını kaydeder; "doğru sırayla doğru uca doğru gövde gitti", "düzeltme PUT'u koştu",
"hiç ağa gidilmedi" iddiaları çağrı listesiyle kanıtlanır. Tablo testleri kütüphanenin GERÇEK
`SAPADTClient.create_table_with_ddl` metodunu sahte oturum üzerinde koşar (kilit/PUT/UNLOCK sırası kodun kendisi).
"""
from __future__ import annotations

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

from test_new_write_tools import TR, Oturum, SahteADT, SahteIstemci, Yanit  # noqa: E402

TR2 = "TESTK900002"
AKTIF_MD = '<adtcore:mainObject adtcore:masterLanguage="TR" adtcore:version="active"/>'


class Oturum2(Oturum):
    def __init__(self, adt):
        super().__init__(adt)
        self.headers: dict = {}

    def put(self, url, params=None, data=None, headers=None, timeout=None):
        return self.adt._kayit("PUT", url, headers, params, data)


class DdicADT(SahteADT):
    language = "TR"
    timeout_default = 30
    timeout_short = 10

    def __init__(self, yonlendir):
        super().__init__(yonlendir)
        self.session = Oturum2(self)
        self._last_lock_effective_transport = None
        from sap_adt_lib import SAPADTClient  # type: ignore
        k = SAPADTClient
        self.create_table_with_ddl = k.create_table_with_ddl.__get__(self)
        self._extract_lock_xml_field = k._extract_lock_xml_field.__get__(self)
        self._validate_object_name = k._validate_object_name.__get__(self)
        self._validate_package_name = k._validate_package_name.__get__(self)
        self.kilit_tutamaci = "HTP1"

    # textpool yolu: kütüphane kilit yardımcıları (sahte; çağrı kaydı düşer)
    def lock_object(self, object_url, access_mode="MODIFY", transport=None, **kw):
        self.cagri.append({"method": "LIB", "path": "lock_object", "params": {"url": object_url, "transport": transport},
                           "data": None, "headers": {}})
        self._last_lock_effective_transport = transport
        return self.kilit_tutamaci

    def unlock_object(self, object_url, lock_handle):
        self.cagri.append({"method": "LIB", "path": "unlock_object", "params": {"url": object_url,
                                                                                  "handle": lock_handle},
                           "data": None, "headers": {}})
        return getattr(self, "unlock_sonuc", True)


class DdicIstemci(SahteIstemci):
    def __init__(self, adt, sql=None):
        super().__init__(adt)
        self.metadata = AKTIF_MD
        self.sql = sql
        self.last_sql_error = None
        self.aktive = True   # bool ya da sırayla dönen liste (ilk aktivasyon, düzeltme sonrası ikinci)

    def get_object_metadata(self, name, object_type=None):
        """`metadata` bir çağrılabilirse (ad, tip) ile, listeyse sırayla (son öğe tekrar), değilse sabit döner."""
        self.adt_client.cagri.append({"method": "LIB", "path": f"get_object_metadata:{object_type}",
                                      "params": {}, "data": None, "headers": {}})
        if callable(self.metadata):
            return self.metadata(name, object_type)
        if isinstance(self.metadata, list):
            return self.metadata.pop(0) if len(self.metadata) > 1 else self.metadata[0]
        return self.metadata

    def create_structure(self, name, fields, description, package, transport=None):
        self.adt_client.cagri.append({"method": "LIB", "path": "create_structure",
                                      "params": {"name": name, "transport": transport}, "data": None, "headers": {}})
        self.yaratildi = True
        return True

    def activate_object(self, name, object_type=None):
        self.adt_client.cagri.append({"method": "LIB", "path": f"activate:{object_type}", "params": {"name": name},
                                      "data": None, "headers": {}})
        if isinstance(self.aktive, list):
            return self.aktive.pop(0) if self.aktive else True
        return self.aktive

    def run_sql_query(self, query, max_rows=100):
        self.adt_client.cagri.append({"method": "LIB", "path": "sql", "params": {"q": query}, "data": None,
                                      "headers": {}})
        return self.sql(query) if callable(self.sql) else self.sql


def _pass():
    from sapadt._reviewer import ReviewerResult
    return ReviewerResult(verdict="PASS")


ALANLAR = [{"name": "MANDT", "type": "mandt", "key": True},
           {"name": "BELGE", "type": "char10", "key": True},
           {"name": "ACIKLAMA", "type": "char40"}]


class DdicTextpool(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="axet_ddic_"))
        cls._eski_env = {k: os.environ.get(k) for k in ("AXET_SAP_PROJECT_DIR", "ADT_SAP_TIER")}
        os.environ.pop("ADT_SAP_TIER", None)
        for k in [k for k in os.environ if k.upper().startswith("ADT_")]:
            cls._eski_env.setdefault(k, os.environ.get(k))
            os.environ.pop(k, None)
        from sapadt.tools import atom, ddic, textpool
        cls.atom, cls.ddic, cls.tp = atom, ddic, textpool
        cls._eski = (atom._get_client, ddic._varlik, ddic.run_reviewer_tablo)
        cls._sayac = 0

    @classmethod
    def tearDownClass(cls):
        cls.atom._get_client, cls.ddic._varlik, cls.ddic.run_reviewer_tablo = cls._eski
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
        self.ddic._varlik = lambda name, t: (False, "checked_absent")
        self.ddic.run_reviewer_tablo = lambda ddl: _pass()

    def kur(self, yon, sql=None):
        adt = DdicADT(yon)
        ist = DdicIstemci(adt, sql)
        self.atom._get_client = lambda: ist
        return adt, ist

    def kaydet(self, ad, beklenen, gercek, ok):
        H.kaydet(f"DDIC {ad}", beklenen, str(gercek)[:160], ok)
        self.assertTrue(ok, f"{ad}: {gercek}")

    # ── Z38 adt_table_create ───────────────────────────────────────────────────────────────
    def _tablo_yon(self, kilit=None, canli=None, put_kod=200, unlock_kod=200):
        durum = {"ddl": None}

        def yon(c):
            m, yol, pr = c["method"], c["path"], c["params"]
            if m == "POST" and yol == "/sap/bc/adt/ddic/tables":
                return Yanit(201, "")
            if m == "POST" and pr.get("_action") == "LOCK":
                return kilit or Yanit(200, f"<DATA><LOCK_HANDLE>HT1</LOCK_HANDLE><CORRNR>{TR}</CORRNR>"
                                           "<IS_LINK_UP></IS_LINK_UP></DATA>")
            if m == "PUT":
                durum["ddl"] = c["data"]
                return Yanit(put_kod, "")
            if m == "POST" and pr.get("_action") == "UNLOCK":
                return Yanit(unlock_kod, "kilit" if unlock_kod != 200 else "")
            if m == "GET" and yol.endswith("/source/main"):
                return Yanit(200, canli if canli is not None else durum["ddl"] or "")
            return Yanit(500, "beklenmedik")
        return yon

    def test_T1_tablo_akis_sirasi(self):
        adt, _ = self.kur(self._tablo_yon(kilit=Yanit(200, "<DATA><LOCK_HANDLE>HT1</LOCK_HANDLE>"
                                                           f"<CORRNR>{TR2}</CORRNR><IS_LINK_UP></IS_LINK_UP></DATA>")))
        r = self.ddic.adt_table_create("ZAXET_T_DEN", "Deneme tablosu", ALANLAR, "ZAXET_PKG", TR)
        ag = [c for c in adt.cagri if c["method"] in ("POST", "PUT", "GET") or c["path"].startswith("activate")]
        sira = [(c["method"], c["params"].get("_action") or c["path"].rsplit("/", 1)[-1]) for c in ag]
        kabuk, put = ag[0], [c for c in ag if c["method"] == "PUT"][0]
        ok = (r.get("ok") is True
              and sira[:5] == [("POST", "tables"), ("POST", "LOCK"), ("PUT", "main"), ("POST", "UNLOCK"),
                               ("LIB", "activate:table")]
              and "define table" not in kabuk["data"] and 'adtcore:type="TABL/DT"' in kabuk["data"]
              and kabuk["headers"].get("Content-Type", "").startswith("application/vnd.sap.adt.tables.v2+xml")
              and "If-Match" not in put["headers"]
              and put["params"] == {"lockHandle": "HT1", "corrNr": TR2}
              and "key mandt : mandt not null;" in put["data"] and "#NOT_EXTENSIBLE" in put["data"]
              and r["steps"]["readback"]["ok"] is True
              and r["steps"]["create"]["effective_transport"] == TR2 and r["steps"]["create"]["warnings"])
        self.kaydet("T1 tablo: POST(DDL'siz)→LOCK→PUT(If-Match yok, CORRNR)→UNLOCK→aktive→readback",
                    "ok · sıra · CORRNR otorite", f"ok={r.get('ok')} err={r.get('error')} sıra={sira}", ok)

    def test_T2_tablo_varsayilan_kabuk_readback_fail(self):
        adt, _ = self.kur(self._tablo_yon(canli="define table zaxet_t_den {\n  key client : abap.clnt not null;\n}"))
        r = self.ddic.adt_table_create("ZAXET_T_DEN", "Deneme tablosu", ALANLAR, "ZAXET_PKG", TR)
        ok = (r.get("ok") is False and r.get("error") == "readback_mismatch"
              and r["steps"]["readback"]["reason"] == "default_shell_client_field")
        self.kaydet("T2 tablo: canlıda varsayılan client kabuğu → FAIL (aktif metadata yetmez)",
                    "readback_mismatch · default_shell", f"{r.get('error')} · {r['steps'].get('readback')}", ok)

    def test_T3_tablo_kilit_reddi_yarim_kabuk(self):
        adt, _ = self.kur(self._tablo_yon(kilit=Yanit(403, "kilitli")))
        r = self.ddic.adt_table_create("ZAXET_T_DEN", "Deneme tablosu", ALANLAR, "ZAXET_PKG", TR)
        ok = (r.get("ok") is False and r.get("error") == "partial_shell"
              and not any(c["method"] == "PUT" for c in adt.cagri)
              and not any(c["path"].startswith("activate") for c in adt.cagri))
        self.kaydet("T3 tablo: kilit 403 → partial_shell, PUT/aktivasyon YOK, silme YOK", "partial_shell",
                    f"{r.get('error')} · {[c['method'] for c in adt.cagri]}", ok)

    def test_T4_tablo_yabanci_transport(self):
        adt, _ = self.kur(self._tablo_yon(kilit=Yanit(200, "<DATA><LOCK_HANDLE>HT1</LOCK_HANDLE>"
                                                           f"<CORRNR>{TR2}</CORRNR><IS_LINK_UP>X</IS_LINK_UP></DATA>")))
        r = self.ddic.adt_table_create("ZAXET_T_DEN", "Deneme tablosu", ALANLAR, "ZAXET_PKG", TR)
        unlock = [c for c in adt.cagri if c["params"].get("_action") == "UNLOCK"]
        ok = (r.get("error") == "partial_shell" and not any(c["method"] == "PUT" for c in adt.cagri)
              and len(unlock) == 1)
        self.kaydet("T4 tablo: yabancı transport (IS_LINK_UP=X) → PUT yok, UNLOCK var", "partial_shell · unlock 1",
                    f"{r.get('error')} · unlock={len(unlock)}", ok)

    def test_T5_tablo_ag_oncesi_redler(self):
        adt, _ = self.kur(lambda c: AssertionError("ağ"))
        vakalar = [
            ("MANDT yok", self.ddic.adt_table_create("ZAXET_T_DEN", "d", ALANLAR[1:], "ZAXET_PKG", TR),
             "preflight_blocker"),
            ("ad > 16", self.ddic.adt_table_create("ZAXET_T_COK_UZUN_AD", "d", ALANLAR, "ZAXET_PKG", TR),
             "preflight_blocker"),
            ("key 'X'", self.ddic.adt_table_create("ZAXET_T_DEN", "d", ALANLAR[:2] + [{"name": "A", "type": "char1",
                                                                                          "key": "X"}],
                                                   "ZAXET_PKG", TR), "preflight_blocker"),
            ("$TMP transportsuz → Yasak C", self.ddic.adt_table_create("ZAXET_T_DEN", "d", ALANLAR, "$TMP", ""),
             "ADR_0005_C"),
            ("standart ad → Yasak A", self.ddic.adt_table_create("MARA2", "d", ALANLAR, "ZAXET_PKG", TR), "ADR_0005_A"),
        ]
        sonuc = []
        for ad, r, kod in vakalar:
            g = r.get("code") if r.get("error") == "guardrail_violation" else r.get("error")
            sonuc.append((ad, g == kod))
        ok = all(v for _a, v in sonuc) and adt.cagri == []
        self.kaydet("T5 tablo: ağ öncesi redler (MANDT/ad/anahtar/$TMP/std)", "hepsi · çağrı 0",
                    f"{sonuc} çağrı={len(adt.cagri)}", ok)

    def test_T6_tablo_reviewer_blocker(self):
        from sapadt._reviewer import ReviewerResult
        self.ddic.run_reviewer_tablo = lambda ddl: ReviewerResult(verdict="BLOCKER", blocker_count=1)
        adt, _ = self.kur(lambda c: AssertionError("ağ"))
        r = self.ddic.adt_table_create("ZAXET_T_DEN", "Deneme tablosu", ALANLAR, "ZAXET_PKG", TR)
        ok = r.get("error") == "reviewer_blocker" and adt.cagri == [] and "define table" in (r.get("ddl") or "")
        self.kaydet("T6 tablo: reviewer BLOCKER → yazma yok (denetlenen = yazılacak DDL)", "reviewer_blocker",
                    f"{r.get('error')} çağrı={len(adt.cagri)}", ok)

    def test_T7_tablo_kardes_yapi_ucu_olculemedi(self):
        """Bug gate L2 (2026-09-22): tablo ucu 404 + kardeş yapı ucu 503 → `exists_unmeasured`, POST YOK.

        Kontrol grubu: iki uç da 404 → sonda `checked_absent` (yaratma kapısı açık)."""
        self.ddic._varlik = self._eski[1]  # gerçek sonda (setUp sahtesi değil)

        def yon_kur(yapi_kod):
            def yon(c):
                if c["method"] == "GET" and c["path"] == "/sap/bc/adt/ddic/tables/zaxet_t_den/source/main":
                    return Yanit(404, "yok")
                if c["method"] == "GET" and c["path"] == "/sap/bc/adt/ddic/structures/zaxet_t_den/source/main":
                    return Yanit(yapi_kod, "geçici" if yapi_kod != 404 else "yok")
                return Yanit(500, "beklenmedik")
            return yon

        adt, _ = self.kur(yon_kur(503))
        r = self.ddic.adt_table_create("ZAXET_T_DEN", "Deneme tablosu", ALANLAR, "ZAXET_PKG", TR)
        yazma = [c for c in adt.cagri if c["method"] in ("POST", "PUT") or c["path"].startswith("activate")]
        self.kur(yon_kur(404))
        kontrol = self.ddic._varlik("ZAXET_T_DEN", "table")
        ok = (r.get("ok") is False and r.get("error") == "exists_unmeasured" and yazma == []
              and str(r["steps"].get("pre_check", "")).startswith("unavailable:sibling")
              and kontrol[0] is False and kontrol[1] == "checked_absent")
        self.kaydet("T7 tablo: tablo ucu 404 + kardeş yapı ucu ÖLÇÜLEMEDİ (503) → exists_unmeasured, yazma YOK",
                    "exists_unmeasured · yazma 0 · kontrol checked_absent",
                    f"ok={r.get('ok')} err={r.get('error')} pre={r['steps'].get('pre_check')} "
                    f"yazma={len(yazma)} kontrol={kontrol[:2]}", ok)

    # ── Z40 adt_ttyp_create ────────────────────────────────────────────────────────────────
    @staticmethod
    def _ttyp_xml(type_name="ZAXET_S_SATIR", data_type="", access="standard", kdef="standard", kind="nonUnique",
                  kk="dictionaryType", length="000010", decimals="000000"):
        tn = f"<ttyp:typeName>{type_name}</ttyp:typeName>" if type_name else "<ttyp:typeName/>"
        dt = f"<ttyp:dataType>{data_type}</ttyp:dataType>" if data_type else "<ttyp:dataType/>"
        return ('<ttyp:tableType xmlns:ttyp="http://www.sap.com/dictionary/tabletype"><ttyp:rowType>'
                f"<ttyp:typeKind>{kk}</ttyp:typeKind>{tn}<ttyp:builtInType>{dt}<ttyp:length>{length}</ttyp:length>"
                f"<ttyp:decimals>{decimals}</ttyp:decimals></ttyp:builtInType></ttyp:rowType>"
                f"<ttyp:accessType>{access}</ttyp:accessType><ttyp:primaryKey><ttyp:definition>{kdef}"
                f"</ttyp:definition><ttyp:kind>{kind}</ttyp:kind><ttyp:components/></ttyp:primaryKey></ttyp:tableType>")

    @staticmethod
    def _dd40l(rowtype="ZAXET_S_SATIR", rowkind="S", datatype="STRU", leng="000000", access="T", keydef="D",
               keykind="N", decimals="000000"):
        return {"columns": ["TYPENAME", "ROWTYPE", "ROWKIND", "DATATYPE", "LENG", "DECIMALS", "ACCESSMODE", "KEYDEF",
                            "KEYKIND"],
                "data": [["ZAXET_TT_DEN", rowtype, rowkind, datatype, leng, decimals, access, keydef, keykind]]}

    def _ttyp(self, xml_seq, sql_seq, put_kod=200, etag="etag-1", aktive=True, **kw):
        """xml_seq / sql_seq: sırayla dönen readback yanıtları (düzeltme sonrası ikinci eleman).

        xml_seq öğesi int ise o HTTP koduyla boş yanıt döner (XML kanalı ölçülemedi)."""
        sayac = {"x": 0, "s": 0}

        def yon(c):
            if c["method"] == "POST" and c["path"] == "/sap/bc/adt/ddic/tabletypes":
                return Yanit(201, "")
            if c["method"] == "GET" and c["path"] == "/sap/bc/adt/ddic/tabletypes/zaxet_tt_den":
                x = xml_seq[min(sayac["x"], len(xml_seq) - 1)]
                sayac["x"] += 1
                if isinstance(x, int):
                    return Yanit(x, "hata")
                return Yanit(200, x, {"ETag": etag} if etag else {})
            if c["method"] == "PUT":
                return put_kod if isinstance(put_kod, Exception) else Yanit(put_kod, "")
            return Yanit(500, "beklenmedik")

        def sql(q):
            s = sql_seq[min(sayac["s"], len(sql_seq) - 1)]
            sayac["s"] += 1
            return s
        adt, ist = self.kur(yon, sql)
        ist.aktive = aktive
        arg = {"row_type": "ZAXET_S_SATIR"}
        arg.update(kw)
        r = self.ddic.adt_ttyp_create("ZAXET_TT_DEN", "Deneme tablo tipi", "ZAXET_PKG", TR, **arg)
        return adt, r

    def test_Y1_ttyp_normal(self):
        adt, r = self._ttyp([self._ttyp_xml()], [self._dd40l()])
        post = [c for c in adt.cagri if c["method"] == "POST"][0]
        ok = (r.get("ok") is True and not any(c["method"] == "PUT" for c in adt.cagri)
              and post["headers"].get("Content-Type") == "application/vnd.sap.adt.tabletype.v1+xml"
              and post["params"] == {"corrNr": TR} and "<ttyp:typeName>ZAXET_S_SATIR</ttyp:typeName>" in post["data"]
              and r["steps"]["readback"]["durum"] == "dolu" and "repair" not in r["steps"])
        self.kaydet("Y1 ttyp: yarat→aktive→iki kanal dolu → OK, düzeltme YOK", "ok · PUT 0",
                    f"ok={r.get('ok')} err={r.get('error')} rb={r['steps'].get('readback', {}).get('durum')}", ok)

    def test_Y2_ttyp_satir_tipi_bos_duzeltme_kostu(self):
        adt, r = self._ttyp([self._ttyp_xml(type_name=""), self._ttyp_xml()],
                            [self._dd40l(rowtype="", rowkind="", datatype=""), self._dd40l()])
        post = [c for c in adt.cagri if c["method"] == "POST"][0]
        put = [c for c in adt.cagri if c["method"] == "PUT"]
        akt = [c for c in adt.cagri if c["path"].startswith("activate")]
        ok = (r.get("ok") is True and len(put) == 1 and put[0]["headers"].get("If-Match") == "etag-1"
              and put[0]["data"] == post["data"] and put[0]["path"] == "/sap/bc/adt/ddic/tabletypes/zaxet_tt_den"
              and len(akt) == 2 and r["steps"]["repair"]["ok"] is True
              and r["steps"]["readback"]["durum"] == "bos" and r["steps"]["readback_2"]["durum"] == "dolu")
        self.kaydet("Y2 ttyp: ROWTYPE boş → If-Match PUT (aynı XML) → yeniden aktive → dolu → OK",
                    "PUT 1 · aktive 2 · ok", f"ok={r.get('ok')} put={len(put)} akt={len(akt)} err={r.get('error')}", ok)

    def test_Y3_ttyp_duzeltme_sonrasi_hala_bos_FAIL(self):
        bos_x, bos_s = self._ttyp_xml(type_name=""), self._dd40l(rowtype="", rowkind="", datatype="")
        adt, r = self._ttyp([bos_x, bos_x], [bos_s, bos_s])
        put = [c for c in adt.cagri if c["method"] == "PUT"]
        ok = r.get("ok") is False and r.get("error") == "row_type_empty_after_repair" and len(put) == 1
        self.kaydet("Y3 ttyp: düzeltme sonrası HÂLÂ boş → FAIL (asla OK değil)", "row_type_empty_after_repair",
                    f"ok={r.get('ok')} err={r.get('error')} put={len(put)}", ok)

    def test_Y4_ttyp_kanal_celiskisi(self):
        adt, r = self._ttyp([self._ttyp_xml()], [self._dd40l(rowtype="", rowkind="", datatype="")])
        ok = (r.get("error") == "readback_channels_disagree" and not any(c["method"] == "PUT" for c in adt.cagri))
        adt2, r2 = self._ttyp([self._ttyp_xml(type_name="")], [self._dd40l()])
        ok = ok and r2.get("error") == "readback_channels_disagree"
        self.kaydet("Y4 ttyp: bir kanal dolu öbürü boş → FAIL (düzeltme yok)", "channels_disagree ×2",
                    f"{r.get('error')} · {r2.get('error')}", ok)

    def test_Y5_ttyp_sql_olculemedi(self):
        adt, r = self._ttyp([self._ttyp_xml()], [None])
        adt2, r2 = self._ttyp([self._ttyp_xml()], [{"columns": ["TYPENAME"], "data": []}])
        ok = r.get("error") == "readback_unmeasured" and r2.get("error") == "readback_unmeasured"
        self.kaydet("Y5 ttyp: DD40L okunamadı / aktif satır yok → ÖLÇÜLEMEDİ (ok:false)", "readback_unmeasured ×2",
                    f"{r.get('error')} · {r2.get('error')}", ok)

    def test_Y6_ttyp_erisim_uyumsuz(self):
        adt, r = self._ttyp([self._ttyp_xml()], [self._dd40l(access="S")])
        ok = r.get("error") == "readback_mismatch" and "ACCESSMODE" in r.get("message", "")
        self.kaydet("Y6 ttyp: DD40L erişim S ≠ standard → FAIL", "readback_mismatch", r.get("message"), ok)

    def test_Y7_ttyp_ilkel_satir(self):
        adt, r = self._ttyp([self._ttyp_xml(type_name="", data_type="CHAR", kk="predefinedAbapType")],
                            [self._dd40l(rowtype="", rowkind="", datatype="CHAR", leng="000010")],
                            row_type=None, builtin={"data_type": "CHAR", "length": 10})
        post = [c for c in adt.cagri if c["method"] == "POST"][0]
        ok = (r.get("ok") is True and "<ttyp:dataType>CHAR</ttyp:dataType>" in post["data"]
              and "predefinedAbapType" in post["data"])
        self.kaydet("Y7 ttyp: ilkel CHAR(10) satır → DATATYPE ölçüsüyle OK", "ok",
                    f"ok={r.get('ok')} err={r.get('error')} {r.get('message')}", ok)

    def test_Y8_ttyp_ag_oncesi_redler(self):
        adt, _ = self.kur(lambda c: AssertionError("ağ"))
        f = self.ddic.adt_ttyp_create
        vakalar = [
            ("ikisi birden", f("ZAXET_TT_DEN", "d", "ZAXET_PKG", TR, row_type="X", builtin={"data_type": "CHAR",
                                                                                         "length": 1})),
            ("hiçbiri", f("ZAXET_TT_DEN", "d", "ZAXET_PKG", TR)),
            ("hashed nonUnique", f("ZAXET_TT_DEN", "d", "ZAXET_PKG", TR, row_type="X", access_type="hashed",
                                   key_kind="nonUnique")),
            ("standard unique", f("ZAXET_TT_DEN", "d", "ZAXET_PKG", TR, row_type="X", key_kind="unique")),
        ]
        ok = all(r.get("error") == "preflight_blocker" for _a, r in vakalar) and adt.cagri == []
        r_tmp = f("ZAXET_TT_DEN", "d", "$TMP", "", row_type="X")
        self.kaydet("Y8 ttyp: ağ öncesi redler; $TMP transportsuz Yasak C DEĞİL (muaf)",
                    "preflight ×4 · $TMP geçer", f"{[(a, r.get('error')) for a, r in vakalar]} tmp={r_tmp.get('code')}",
                    ok and r_tmp.get("code") != "ADR_0005_C")

    # ── Z39 adt_textpool_write ─────────────────────────────────────────────────────────────
    def _tp(self, canli=None, aktif=None, put_kod=200, unlock=True, **kw):
        canli = canli or {}
        durum = {"yaz": {}}

        def yon(c):
            m, yol, pr = c["method"], c["path"], c["params"]
            if m == "GET" and "/textelements/programs/zaxet_p_den/source/" in yol:
                alt = yol.rsplit("/", 1)[-1]
                if pr.get("version") == "active":
                    return Yanit(200, (aktif or {}).get(alt, durum["yaz"].get(alt, "")))
                return Yanit(200, canli.get(alt, ""), {"ETag": f"e-{alt}"})
            if m == "PUT":
                durum["yaz"][yol.rsplit("/", 1)[-1]] = c["data"]
                return Yanit(put_kod, "DS512" if put_kod != 200 else "")
            if m == "POST" and yol == "/sap/bc/adt/activation":
                return Yanit(200, '<chkl:messages activationExecuted="true" checkExecuted="true" '
                                  'generationExecuted="true"/>')
            if m == "GET" and yol == "/sap/bc/adt/activation/inactiveobjects":
                return Yanit(200, self.WL_BOS)   # PX sonrası worklist temiz (varsayılan)
            return Yanit(500, "beklenmedik")
        adt, ist = self.kur(yon)
        adt.unlock_sonuc = unlock
        return adt, self.tp.adt_textpool_write("ZAXET_P_DEN", TR, **kw)

    SEM = [{"key": "B01", "text": "Seçim kriterleri"}]
    SEC = [{"name": "P_BUKRS", "text": "Şirket kodu"}, {"name": "S_BELGE8", "text": "Belge"}]

    def test_P1_textpool_akis(self):
        adt, r = self._tp(symbols=self.SEM, selections=self.SEC)
        putlar = [c for c in adt.cagri if c["method"] == "PUT"]
        sira = [c["path"].rsplit("/", 1)[-1] if c["method"] != "LIB" else c["path"] for c in adt.cagri]
        i_unlock, i_px = sira.index("unlock_object"), sira.index("activation")
        sym = [c for c in putlar if c["path"].endswith("/symbols")][0]
        sel = [c for c in putlar if c["path"].endswith("/selections")][0]
        kilit = [c for c in adt.cagri if c["path"] == "lock_object"][0]
        ok = (r.get("ok") is True
              and kilit["params"] == {"url": "/sap/bc/adt/textelements/programs/zaxet_p_den", "transport": TR}
              and sym["data"] == "@MaxLength:16\r\nB01=Seçim kriterleri"
              and sel["data"] == "P_BUKRS =Şirket kodu\r\n\r\nS_BELGE8=Belge"
              and sym["params"] == {"corrNr": TR, "lockHandle": "HTP1"} and sym["headers"].get("If-Match") == "e-symbols"
              and sym["headers"].get("Content-Type") == "application/vnd.sap.adt.textelements.symbols.v1; charset=utf-8"
              and i_unlock < i_px and "activate_object" in sira
              and all(v["ok"] for v in r["steps"]["readback"].values()))
        self.kaydet("P1 textpool: GET→REPT kilit→PUT(biçim CRLF, If-Match, tutamaç)→UNLOCK→PROG/P+PX→aktif readback",
                    "ok · biçim · unlock<PX", f"ok={r.get('ok')} err={r.get('error')} sıra={sira}", ok)

    def test_P2_textpool_silinecek_giris_izinsiz(self):
        adt, r = self._tp(canli={"symbols": "@MaxLength:5\r\nB99=Eski!\r\n\r\n@MaxLength:3\r\nB01=abc"},
                          symbols=self.SEM)
        ok = (r.get("error") == "would_remove_entries" and r.get("would_remove") == {"symbols": ["B99"]}
              and not any(c["path"] == "lock_object" for c in adt.cagri))
        self.kaydet("P2 textpool: canlıdaki B99 girdide yok → izinsiz yazmaz, kilit yok", "would_remove_entries",
                    f"{r.get('error')} {r.get('would_remove')}", ok)

    def test_P3_textpool_px_terfi_etmedi(self):
        adt, r = self._tp(aktif={"selections": "P_BUKRS =?\r\n\r\nS_BELGE8=?"}, selections=self.SEC)
        ok = (r.get("ok") is False and r.get("error") == "readback_mismatch"
              and r["steps"]["readback"]["selections"]["placeholder"] == ["P_BUKRS", "S_BELGE8"])
        self.kaydet("P3 textpool: aktif sürümde `=?` → FAIL (working sürüm yanıltır)", "readback_mismatch",
                    f"{r.get('error')} {r['steps']['readback']}", ok)

    def test_P4_textpool_ag_oncesi_redler(self):
        adt, _ = self.kur(lambda c: AssertionError("ağ"))
        f = self.tp.adt_textpool_write
        vakalar = [
            ("max_length aşımı", f("ZAXET_P_DEN", TR, symbols=[{"key": "B01", "text": "uzun metin", "max_length": 4}]),
             "preflight_blocker"),
            ("sembol 4 harf", f("ZAXET_P_DEN", TR, symbols=[{"key": "B001", "text": "x"}]), "preflight_blocker"),
            ("seçim adı 9", f("ZAXET_P_DEN", TR, selections=[{"name": "P_COKUZUN", "text": "x"}]), "preflight_blocker"),
            ("boş girdi", f("ZAXET_P_DEN", TR), "preflight_blocker"),
            ("transport yok", f("ZAXET_P_DEN", "", symbols=self.SEM), "ADR_0005_C"),
            ("standart program", f("RSPARAM", TR, symbols=self.SEM), "ADR_0005_A"),
        ]
        sonuc = [(a, (r.get("code") if r.get("error") == "guardrail_violation" else r.get("error")) == k)
                 for a, r, k in vakalar]
        self.kaydet("P4 textpool: ağ öncesi redler", "hepsi · çağrı 0", f"{sonuc} çağrı={len(adt.cagri)}",
                    all(v for _a, v in sonuc) and adt.cagri == [])

    def test_P5_textpool_sahte_tutamac_ve_put_hatasi(self):
        adt = DdicADT(lambda c: Yanit(200, "", {"ETag": "e"}))
        adt.kilit_tutamaci = "NO_LOCK_SUPPORT"
        ist = DdicIstemci(adt)
        self.atom._get_client = lambda: ist
        r = self.tp.adt_textpool_write("ZAXET_P_DEN", TR, symbols=self.SEM)
        ok1 = r.get("error") == "lock_failed" and not any(c["method"] == "PUT" for c in adt.cagri)
        adt2, r2 = self._tp(put_kod=406, symbols=self.SEM)
        ok2 = (r2.get("error") == "put_failed" and any(c["path"] == "unlock_object" for c in adt2.cagri)
               and not any(c["path"] == "/sap/bc/adt/activation" for c in adt2.cagri))
        self.kaydet("P5 textpool: sahte tutamaç → yazmaz · PUT 406 → unlock var, aktivasyon yok",
                    "lock_failed · put_failed", f"{r.get('error')} · {r2.get('error')}", ok1 and ok2)


    # ── Bug-gate WARNING düzeltmeleri (2026-09-21): kapsanmayan dallar + M1-M3 · L1-L3 ─────────────
    def test_T7_tablo_put_4xx_yarim_kabuk_unlock(self):
        adt, _ = self.kur(self._tablo_yon(put_kod=400))
        r = self.ddic.adt_table_create("ZAXET_T_DEN", "Deneme tablosu", ALANLAR, "ZAXET_PKG", TR)
        unlock = [c for c in adt.cagri if c["params"].get("_action") == "UNLOCK"]
        ok = (r.get("ok") is False and r.get("error") == "partial_shell" and r["steps"]["create"].get("stage") == "put"
              and len(unlock) == 1 and unlock[0]["params"].get("lockHandle") == "HT1"
              and not any(c["path"].startswith("activate") for c in adt.cagri) and "unlock_warning" not in r)
        self.kaydet("T7 tablo: PUT 400 → partial_shell(put), UNLOCK 1, aktivasyon yok", "partial_shell · unlock 1",
                    f"{r.get('error')} stage={r['steps']['create'].get('stage')} unlock={len(unlock)}", ok)

    def test_T8_tablo_unlock_hatasi_gorunur(self):
        adt, _ = self.kur(self._tablo_yon(unlock_kod=403))
        r = self.ddic.adt_table_create("ZAXET_T_DEN", "Deneme tablosu", ALANLAR, "ZAXET_PKG", TR)
        c = r["steps"]["create"]
        ok1 = (r.get("ok") is True and c.get("unlock_ok") is False and bool(r.get("unlock_warning"))
               and any("UNLOCK" in w for w in c.get("warnings") or []))
        adt2, _ = self.kur(self._tablo_yon(put_kod=400, unlock_kod=403))
        r2 = self.ddic.adt_table_create("ZAXET_T_DEN", "Deneme tablosu", ALANLAR, "ZAXET_PKG", TR)
        ok2 = (r2.get("error") == "partial_shell" and bool(r2.get("unlock_warning"))
               and r2["steps"]["create"].get("unlock_ok") is False)
        adt3, _ = self.kur(self._tablo_yon())
        r3 = self.ddic.adt_table_create("ZAXET_T_DEN", "Deneme tablosu", ALANLAR, "ZAXET_PKG", TR)
        ok3 = r3["steps"]["create"].get("unlock_ok") is True and "unlock_warning" not in r3
        self.kaydet("T8 tablo: UNLOCK 403 → ok korunur ama unlock_ok:false + unlock_warning (başarı + PUT hatası)",
                    "uyarı görünür ×2 · 200'de uyarı yok",
                    f"ok={r.get('ok')} c={c.get('unlock_ok')} w={str(r.get('unlock_warning'))[:40]} · "
                    f"{r2.get('error')} {str(r2.get('unlock_warning'))[:30]} · {r3['steps']['create'].get('unlock_ok')}",
                    ok1 and ok2 and ok3)

    def test_T9_tablo_aktivasyon_hatasi(self):
        adt, ist = self.kur(self._tablo_yon())
        ist.aktive = False
        r = self.ddic.adt_table_create("ZAXET_T_DEN", "Deneme tablosu", ALANLAR, "ZAXET_PKG", TR)
        ok = (r.get("ok") is False and r.get("error") == "activation_failed" and "readback" not in r["steps"]
              and not any(c["method"] == "GET" for c in adt.cagri))
        self.kaydet("T9 tablo: aktivasyon False → activation_failed, readback yok", "activation_failed",
                    f"{r.get('error')} steps={sorted(r['steps'])}", ok)

    def test_T10_tablo_kucuk_harf_ad_ve_dogrulama_asamasi(self):
        adt, _ = self.kur(self._tablo_yon())
        r = self.ddic.adt_table_create("zaxet_t_den", "Deneme tablosu", ALANLAR, "ZAXET_PKG", TR)
        kabuk = [c for c in adt.cagri if c["method"] == "POST" and c["path"] == "/sap/bc/adt/ddic/tables"]
        ok1 = (r.get("ok") is True and r.get("name") == "ZAXET_T_DEN" and len(kabuk) == 1
               and 'adtcore:name="ZAXET_T_DEN"' in kabuk[0]["data"])
        adt2, _ = self.kur(self._tablo_yon())
        # Z50 ⓕ'den beri boş paket araç kapısında reddedilir (S11); kütüphane doğrulama aşaması > 30 karakterle ölçülür.
        r2 = self.ddic.adt_table_create("ZAXET_T_DEN", "Deneme tablosu", ALANLAR, "Z" * 31, TR)
        msg = r2.get("message") or ""
        ok2 = (r2.get("ok") is False and r2.get("error") == "validation_error"
               and r2["steps"].get("create", {}).get("stage") == "validate" and adt2.cagri == []
               and "reddedildi" not in msg and "gidilmedi" in msg)
        self.kaydet("T10 tablo: küçük harfli ad normalize → OK · paket > 30 → validation_error (POST 0, doğru mesaj)",
                    "ok · validation_error", f"ok={r.get('ok')} err={r.get('error')} · {r2.get('error')} "
                    f"stage={r2['steps'].get('create', {}).get('stage')} msg={msg[:60]} "
                    f"çağrı={len(adt2.cagri)}", ok1 and ok2)

    def test_T11_tablo_csrf_istisnasi_baslik_temizlenir(self):
        adt, _ = self.kur(self._tablo_yon())

        def patla(force_refresh=False):
            raise RuntimeError("csrf ağı düştü")
        adt.fetch_csrf_token = patla
        r = self.ddic.adt_table_create("ZAXET_T_DEN", "Deneme tablosu", ALANLAR, "ZAXET_PKG", TR)
        ok = (r.get("error") == "partial_shell" and r["steps"]["create"].get("stage") == "lock"
              and "X-sap-adt-sessiontype" not in adt.session.headers
              and not any(c["params"].get("_action") == "LOCK" for c in adt.cagri))
        self.kaydet("T11 tablo: kabuk sonrası CSRF istisnası → partial_shell(lock), stateful başlık temizlendi",
                    "partial_shell · başlık yok", f"{r.get('error')} stage={r['steps']['create'].get('stage')} "
                    f"başlık={adt.session.headers}", ok)

    def test_Y9_ttyp_duzeltme_put_412(self):
        bos_x, bos_s = self._ttyp_xml(type_name=""), self._dd40l(rowtype="", rowkind="", datatype="")
        adt, r = self._ttyp([bos_x], [bos_s], put_kod=412)
        akt = [c for c in adt.cagri if c["path"].startswith("activate")]
        ok = (r.get("ok") is False and r.get("error") == "row_type_empty_repair_failed"
              and r["steps"]["repair"].get("http_status") == 412 and len(akt) == 1)
        self.kaydet("Y9 ttyp: düzeltme PUT 412 → row_type_empty_repair_failed, ikinci aktivasyon yok",
                    "repair_failed", f"ok={r.get('ok')} err={r.get('error')} akt={len(akt)}", ok)

    def test_Y10_ttyp_etag_yok(self):
        bos_x, bos_s = self._ttyp_xml(type_name=""), self._dd40l(rowtype="", rowkind="", datatype="")
        adt, r = self._ttyp([bos_x], [bos_s], etag="")
        ok = (r.get("error") == "row_type_empty_repair_failed" and r["steps"]["repair"].get("reason") == "etag_yok"
              and not any(c["method"] == "PUT" for c in adt.cagri))
        self.kaydet("Y10 ttyp: ETag yok → If-Match'siz PUT DENENMEZ", "etag_yok · PUT 0",
                    f"{r.get('error')} {r['steps'].get('repair')}", ok)

    def test_Y11_ttyp_aktivasyon_hatasi(self):
        adt, r = self._ttyp([self._ttyp_xml()], [self._dd40l()], aktive=False)
        ok = (r.get("ok") is False and r.get("error") == "activation_failed" and "readback" not in r["steps"]
              and not any(c["path"] == "sql" for c in adt.cagri))
        self.kaydet("Y11 ttyp: aktivasyon False → activation_failed, readback yok", "activation_failed",
                    f"{r.get('error')} steps={sorted(r['steps'])}", ok)

    def test_Y12_ttyp_dd40l_dolu_xml_olculemedi(self):
        adt, r = self._ttyp([500], [self._dd40l()])
        rb = r["steps"].get("readback", {})
        ok = (r.get("ok") is False and r.get("error") == "readback_unmeasured"
              and rb.get("xml_probe") == "xml_http_500" and rb.get("durum") == "olculemedi")
        self.kaydet("Y12 ttyp: DD40L dolu + XML 500 → readback_unmeasured (ölçülemedi ≠ doğru)", "readback_unmeasured",
                    f"{r.get('error')} {rb.get('xml_probe')}", ok)

    def test_Y13_ttyp_dec_ondalik_uyumsuz(self):
        dec = {"row_type": None, "builtin": {"data_type": "DEC", "length": 15, "decimals": 2}}
        x_iyi = self._ttyp_xml(type_name="", data_type="DEC", kk="predefinedAbapType", length="000015",
                               decimals="000002")
        s_iyi = self._dd40l(rowtype="", rowkind="", datatype="DEC", leng="000015", decimals="000002")
        _a, r0 = self._ttyp([x_iyi], [s_iyi], **dec)
        _a, r1 = self._ttyp([x_iyi], [self._dd40l(rowtype="", rowkind="", datatype="DEC", leng="000015",
                                                  decimals="000000")], **dec)
        _a, r2 = self._ttyp([self._ttyp_xml(type_name="", data_type="DEC", kk="predefinedAbapType", length="000015",
                                            decimals="000000")], [s_iyi], **dec)
        _a, r3 = self._ttyp([self._ttyp_xml(type_name="", data_type="DEC", kk="predefinedAbapType", length="000013",
                                            decimals="000002")], [s_iyi], **dec)
        ok = (r0.get("ok") is True
              and r1.get("error") == "readback_mismatch" and "DD40L.DECIMALS" in r1.get("message", "")
              and r2.get("error") == "readback_mismatch" and "XML decimals" in r2.get("message", "")
              and r3.get("error") == "readback_mismatch" and "XML length" in r3.get("message", ""))
        self.kaydet("Y13 ttyp: DEC 15,2 — DD40L DECIMALS=0 / XML decimals=0 / XML length=13 → readback_mismatch",
                    "ok · mismatch ×3", f"{r0.get('error')} · {str(r1.get('message'))[:70]} · "
                    f"{str(r2.get('message'))[:70]} · {str(r3.get('message'))[:70]}", ok)

    def test_Y14_ttyp_duzeltme_sonrasi_aktivasyon_hatasi(self):
        bos_x, bos_s = self._ttyp_xml(type_name=""), self._dd40l(rowtype="", rowkind="", datatype="")
        adt, r = self._ttyp([bos_x, self._ttyp_xml()], [bos_s, self._dd40l()], aktive=[True, False])
        ok = (r.get("ok") is False and r.get("error") == "activation_failed_after_repair"
              and r["steps"]["activate_2"]["ok"] is False and "readback_2" not in r["steps"])
        self.kaydet("Y14 ttyp: düzeltme PUT'u OK ama yeniden aktivasyon düştü → activation_failed_after_repair",
                    "activation_failed_after_repair", f"ok={r.get('ok')} err={r.get('error')}", ok)

    def test_P6_textpool_unlock_hatasi(self):
        adt, r = self._tp(unlock=False, symbols=self.SEM)
        ok = (r.get("ok") is True and r["steps"]["unlock"]["ok"] is False and bool(r.get("unlock_warning")))
        adt2, r2 = self._tp(unlock=False, put_kod=406, symbols=self.SEM)
        ok = ok and r2.get("error") == "put_failed" and bool(r2.get("unlock_warning"))
        self.kaydet("P6 textpool: UNLOCK başarısız → unlock_warning (başarı + PUT hatası yolunda)", "uyarı ×2",
                    f"ok={r.get('ok')} {str(r.get('unlock_warning'))[:40]} · {r2.get('error')}", ok)

    def test_P7_textpool_silme_uygulanmadi(self):
        canli = {"symbols": "@MaxLength:5\r\nB99=Eski!\r\n\r\n@MaxLength:16\r\nB01=Seçim kriterleri"}
        adt, r = self._tp(canli=canli, aktif=canli, allow_remove=True, symbols=self.SEM)
        rb = r["steps"]["readback"]["symbols"]
        ok1 = (r.get("ok") is False and r.get("error") == "readback_mismatch"
               and rb.get("remove_not_applied") == ["B99"] and rb["ok"] is False)
        adt2, r2 = self._tp(canli=canli, allow_remove=True, symbols=self.SEM)
        ok2 = r2.get("ok") is True and r2["steps"]["readback"]["symbols"].get("remove_not_applied") == []
        self.kaydet("P7 textpool: allow_remove ile silinecek B99 aktifte duruyor → readback_mismatch",
                    "remove_not_applied · temizde ok", f"{r.get('error')} {rb} · {r2.get('ok')}", ok1 and ok2)

    # ── Z39 kalanı: adt_textpool_read (bağımsız OKUMA aracı; yazma aracının okuma yolunu kullanır) ─────────────
    CANLI_SEM = "@MaxLength:10\r\nB00=İşlem Türü\r\n\r\n@MaxLength:16\r\nB01=Seçim Kriterleri"
    CANLI_SEC = "@DDICReference\r\nP_BUKRS =?\r\n\r\nP_FILE  =Excel Dosyası\r\n\r\nRB_RAPOR=Sözleşmeleri Listele"

    def _oku(self, yanit=None, **kw):
        """yanit: alt kaynak → Yanit | Exception; verilmezse iki alt kaynak 200 + CANLI_*."""
        yanit = yanit or {"symbols": Yanit(200, self.CANLI_SEM), "selections": Yanit(200, self.CANLI_SEC)}

        def yon(c):
            if c["method"] == "GET" and "/textelements/programs/zaxet_p_den/source/" in c["path"]:
                return yanit.get(c["path"].rsplit("/", 1)[-1], Yanit(500, "beklenmedik alt kaynak"))
            return AssertionError(f"okuma aracı beklenmedik çağrı yaptı: {c['method']} {c['path']}")
        adt, _ist = self.kur(yon)
        return adt, self.tp.adt_textpool_read("zaxet_p_den", **kw)

    def test_R1_textpool_read_aktif_iki_alt_kaynak(self):
        adt, r = self._oku()
        sem, sec = r["parts"]["symbols"], r["parts"]["selections"]
        get = [c for c in adt.cagri]
        ok = (r.get("ok") is True and r.get("name") == "ZAXET_P_DEN" and r.get("version") == "active"
              and all(c["method"] == "GET" for c in get) and len(get) == 2
              and all(c["params"] == {"version": "active"} for c in get)
              and {c["path"].rsplit("/", 1)[-1]: c["headers"].get("Accept") for c in get}
              == {"symbols": "application/vnd.sap.adt.textelements.symbols.v1",
                  "selections": "application/vnd.sap.adt.textelements.selections.v1"}
              and sem["entries"] == [{"key": "B00", "text": "İşlem Türü", "max_length": 10},
                                     {"key": "B01", "text": "Seçim Kriterleri", "max_length": 16}]
              and sec["entries"] == [
                  {"name": "P_BUKRS", "text": "?", "ddic_reference": True, "placeholder": True},
                  {"name": "P_FILE", "text": "Excel Dosyası", "ddic_reference": False, "placeholder": False},
                  {"name": "RB_RAPOR", "text": "Sözleşmeleri Listele", "ddic_reference": False, "placeholder": False}]
              and sem["count"] == 2 and sec["count"] == 3 and "headings" in " ".join(r.get("not_checked", [])))
        self.kaydet("R1 textpool_read: yalnız GET ×2 · version=active · alt kaynak Accept · ayrıştırma",
                    "ok · 2 GET · girişler", f"ok={r.get('ok')} err={r.get('error')} çağrı={[(c['method'], c['path'][-10:], c['params']) for c in get]} {r.get('parts')}", ok)

    def test_R2_textpool_read_working_ve_parca_secimi(self):
        adt, r = self._oku(version="working", parts=["symbols"])
        ok = (r.get("ok") is True and len(adt.cagri) == 1 and adt.cagri[0]["path"].endswith("/source/symbols")
              and adt.cagri[0]["params"] == {} and list(r["parts"]) == ["symbols"])
        self.kaydet("R2 textpool_read: version=working → parametresiz GET · parts=[symbols] → tek GET",
                    "1 GET · param yok", f"{[(c['path'][-8:], c['params']) for c in adt.cagri]} {r.get('error')}", ok)

    def test_R3_textpool_read_hata_yollari(self):
        _a1, r404 = self._oku({"symbols": Yanit(404, ""), "selections": Yanit(200, self.CANLI_SEC)})
        _a2, r500 = self._oku({"symbols": Yanit(200, self.CANLI_SEM), "selections": Yanit(500, "dump")})
        _a3, rexc = self._oku({"symbols": ConnectionError("ağ"), "selections": Yanit(200, self.CANLI_SEC)})
        ok = (r404.get("ok") is False and r404.get("error") == "not_found"
              and r500.get("ok") is False and r500.get("error") == "read_failed"
              and r500["parts"]["selections"] == {"ok": False, "http_status": 500, "body_head": "dump"}
              and r500["parts"]["symbols"]["ok"] is True
              and rexc.get("error") == "read_failed" and rexc["parts"]["symbols"]["ok"] is False
              and "ConnectionError" in rexc["parts"]["symbols"]["reason"])
        self.kaydet("R3 textpool_read: 404 → not_found · 500 → read_failed (diğer parça korunur) · istisna",
                    "not_found · read_failed ×2", f"{r404.get('error')} · {r500.get('error')} · {rexc.get('error')}", ok)

    def test_R4_textpool_read_ag_oncesi_redler(self):
        adt, _ = self.kur(lambda c: AssertionError("ağ"))
        f = self.tp.adt_textpool_read
        vakalar = [("boş ad", f("  ")), ("boşluklu ad", f("ZAXET P")), ("41 karakter", f("Z" * 41)),
                   ("sürüm bilinmiyor", f("ZAXET_P_DEN", version="inactive")),
                   ("headings desteklenmez", f("ZAXET_P_DEN", parts=["headings"])),
                   ("bilinmeyen parça", f("ZAXET_P_DEN", parts=["xyz"])), ("boş parça listesi", f("ZAXET_P_DEN", parts=[]))]
        sonuc = [(a, r.get("error")) for a, r in vakalar]
        ok = all(e == "invalid_argument" for _a, e in sonuc) and adt.cagri == []
        self.kaydet("R4 textpool_read: ağ öncesi redler", "invalid_argument ×7 · çağrı 0",
                    f"{sonuc} çağrı={len(adt.cagri)}", ok)

    def test_R5_textpool_read_okuma_sinifi_ve_profil(self):
        from sapadt import gate
        from sapadt._app import load_all_tools
        spec = load_all_tools()["adt_textpool_read"]
        ok = (gate.tool_class("adt_textpool_read", {}) == "read" and "adt_textpool_read" in gate.READ_TOOLS
              and "adt_textpool_read" not in gate.REQUIRES_TRANSPORT
              and tuple(spec.available_on) == ("s4_private",))
        self.kaydet("R5 textpool_read: READ_TOOLS + read sınıfı + transport istemez + s4_private",
                    "read · s4_private", f"{gate.tool_class('adt_textpool_read', {})} {spec.available_on}", ok)


    # ── Canlı ölçüm bulguları (DEV, 2026-09-21 — kk-ddic r2_*): kırmızı-önce testler ─────────────────────────
    # Canlı gerçek (r2_10_struct): yapı AKTİF yaratıldı (DD02L INTTAB/A, DD03L 2 satır) ama araç `ok:false`
    # `verify: metadata_not_found` dedi — doğrulama `tabl` → `/ddic/tables/` ucuna soruyordu; yapılar
    # `/ddic/structures/` altında. Sahte istemci canlının davranışını taklit eder: metadata yalnız `structure`
    # tipiyle bulunur, `tabl`/`table` ile None (sap_client istisnayı yutup None döndürür).
    YAPI_DDL = ("@EndUserText.label : 'KKD deneme yapısı'\n@AbapCatalog.enhancement.category : #NOT_EXTENSIBLE\n"
                "define structure zaxet_s_den {\n  belge    : abap.char(10);\n  aciklama : abap.char(40);\n}\n")
    YAPI_ALANLARI = [{"name": "BELGE", "type": "char10"}, {"name": "ACIKLAMA", "type": "char40"}]

    YAPI_SRC = "/sap/bc/adt/ddic/structures/zaxet_s_den/source/main"
    TABLO_SRC = "/sap/bc/adt/ddic/tables/zaxet_s_den/source/main"

    def _yapi(self, var_once=False, kaynak=None, md_yapi=AKTIF_MD, yon_ek=None, gercek_lib=False):
        """`yon_ek(c)` None dışında bir Yanit dönerse o kullanılır (ön kontrol / POST senaryoları).

        Varlık sondası (2026-09-21 düzeltmesi) `adt_get(structure)` = `/ddic/structures/<ad>/source/main` GET'i (+ 404'te
        kardeş `/ddic/tables/` ucu); yapı yaratılmadan önce ikisi de 404, yaratıldıktan sonra yapı ucu 200.
        `gercek_lib=True`: `create_structure` kütüphanenin GERÇEK `SAPClient` + `SAPADTClient` gövdesiyle koşar (POST/LOCK/PUT
        çağrı listesine düşer)."""
        from sapadt.tools import composite
        eski = composite.run_reviewer_struct
        composite.run_reviewer_struct = lambda *a, **k: _pass()
        self.addCleanup(setattr, composite, "run_reviewer_struct", eski)
        ref = {}

        def yon(c):
            if yon_ek is not None:
                y = yon_ek(c)
                if y is not None:
                    return y
            if c["method"] == "GET" and c["path"] == self.YAPI_SRC:
                if not ref["ist"].yaratildi:
                    return Yanit(404, "")
                return Yanit(200, self.YAPI_DDL if kaynak is None else kaynak)
            if c["method"] == "POST" and c["path"] == "/sap/bc/adt/ddic/structures":
                ref["ist"].yaratildi = True
                return Yanit(201, "")
            if c["method"] == "PUT":
                return Yanit(200, "")
            return Yanit(404, "")
        adt, ist = self.kur(yon)
        ref["ist"] = ist
        ist.yaratildi = var_once
        if gercek_lib:
            from sap_adt_lib import SAPADTClient  # type: ignore
            from sap_client import SAPClient  # type: ignore
            k = SAPADTClient
            for m in ("create_structure", "_validate_structure_fields", "_validate_transport", "_zaten_var_mi",
                      "_zaten_var_hatasi", "_yeniden_denendi_mi"):
                setattr(adt, m, getattr(k, m).__get__(adt))
            adt._retry_request = lambda fn, *_a, **_k: fn()
            ist.create_structure = lambda *a, **kw: SAPClient.create_structure(ist, *a, **kw)

        def md(name, tip):
            if tip == "structure" and ist.yaratildi:
                return md_yapi
            return None
        ist.metadata = md
        r = composite.adt_struct_create("ZAXET_S_DEN", self.YAPI_ALANLARI, "KKD deneme yapısı", "ZAXET_PKG", TR)
        return adt, r

    def test_S1_yapi_dogrulama_yapilar_ucundan(self):
        adt, r = self._yapi()
        md_tipleri = [c["path"].split(":", 1)[1] for c in adt.cagri if c["path"].startswith("get_object_metadata")]
        st = r.get("steps", {})
        ok = (r.get("ok") is True and st.get("verify", {}).get("ok") is True
              and st.get("content_verify", {}).get("ok") is True and st["content_verify"].get("field_count") == 2
              and "tabl" not in md_tipleri and "table" not in md_tipleri and r.get("type") == "tabl")
        self.kaydet("S1 yapı: aktif yapı /ddic/structures ile doğrulanır + içerik (2 alan) → OK",
                    "ok · verify · content 2", f"ok={r.get('ok')} verify={st.get('verify')} "
                    f"content={st.get('content_verify')} md_tipleri={md_tipleri}", ok)

    def test_S2_yapi_on_kontrol_mevcut_yapiyi_gorur(self):
        adt, r = self._yapi(var_once=True)
        ok = (r.get("ok") is False and r.get("error") == "already_exists"
              and not any(c["path"] == "create_structure" for c in adt.cagri))
        self.kaydet("S2 yapı: ön kontrol mevcut yapıyı /ddic/structures ile görür → already_exists, yaratma yok",
                    "already_exists · create 0", f"{r.get('error')} steps={r.get('steps')}", ok)

    def test_S3_yapi_icerik_bos_kabuk_FAIL(self):
        adt, r = self._yapi(kaynak="define structure zaxet_s_den {\n  component_to_be_changed : abap.string(0);\n}\n")
        cv = r.get("steps", {}).get("content_verify", {})
        adt2, r2 = self._yapi(md_yapi='<adtcore:mainObject adtcore:masterLanguage="TR" adtcore:version="inactive"/>')
        ok = (r.get("ok") is False and cv.get("reason") == "placeholder_shell"
              and r2.get("ok") is False
              and r2.get("steps", {}).get("verify", {}).get("reason", "").startswith("sap_version=inactive"))
        self.kaydet("S3 yapı: aktif ama yer tutucu kabuk / sürüm inactive → FAIL (asla sahte OK)",
                    "placeholder_shell · inactive", f"{cv} · {r2.get('steps', {}).get('verify')}", ok)

    # ── Üzerine yazma kapısı (2026-09-21, bug gate): `_exists` hata/None'da "yok" diyordu (fail-open) ve
    # `create_structure` POST 405 AlreadyExists'te `pass` → LOCK → PUT → aktivasyon yapıyordu ⇒ ön kontrol yanlış "yok"
    # derse kullanıcının MEVCUT yapısı yeni alanlarla ezilip aktive ediliyordu. Kırmızı-önce (a)(b)(c) + kardeş uç.
    @staticmethod
    def _yazma_izi(adt):
        return [c["method"] + " " + c["path"] for c in adt.cagri
                if c["path"] in ("create_structure", "lock_object") or c["method"] in ("PUT",)
                or c["path"].startswith("activate") or (c["method"] == "POST" and "/ddic/" in c["path"])]

    def test_S4_yapi_on_kontrol_olculemedi_POST_yok(self):
        def ek(c):
            if c["method"] == "GET" and c["path"] == self.YAPI_SRC:
                return Yanit(500, "sunucu hatası")
            return None
        adt, r = self._yapi(yon_ek=ek)
        iz = self._yazma_izi(adt)
        ok = (r.get("ok") is False and r.get("error") == "exists_unmeasured" and iz == []
              and str(r.get("steps", {}).get("pre_check", "")).startswith("unavailable"))
        self.kaydet("S4 yapı (a): ön kontrol ÖLÇÜLEMEDİ (GET 500) → exists_unmeasured, POST/kilit/PUT/aktivasyon YOK",
                    "exists_unmeasured · yazma 0", f"ok={r.get('ok')} err={r.get('error')} "
                    f"pre={r.get('steps', {}).get('pre_check')} iz={iz}", ok)

    def test_S5_yapi_POST_zaten_var_PUT_yok(self):
        def ek(c):
            if c["method"] == "POST" and c["path"] == "/sap/bc/adt/ddic/structures":
                return Yanit(405, "<exc:exception><type id=\"ExceptionResourceAlreadyExists\"/>"
                                  "<localizedMessage>AlreadyExists</localizedMessage></exc:exception>")
            return None
        adt, r = self._yapi(yon_ek=ek, gercek_lib=True)
        put = [c for c in adt.cagri if c["method"] == "PUT"]
        kilit = [c for c in adt.cagri if c["path"] == "lock_object"]
        akt = [c for c in adt.cagri if c["path"].startswith("activate")]
        post = [c for c in adt.cagri if c["method"] == "POST" and c["path"] == "/sap/bc/adt/ddic/structures"]
        ok = (r.get("ok") is False and r.get("error") == "already_exists" and len(post) == 1
              and put == [] and kilit == [] and akt == [] and "YAZILMADI" in str(r.get("message")))
        self.kaydet("S5 yapı (b): ön kontrol 'yok' ama POST 405 AlreadyExists → already_exists, LOCK/PUT/aktivasyon YOK",
                    "already_exists · PUT 0 · kilit 0 · akt 0",
                    f"ok={r.get('ok')} err={r.get('error')} post={len(post)} put={len(put)} kilit={len(kilit)} "
                    f"akt={len(akt)}", ok)

    TABLO_DDL = ("@EndUserText.label : 'Deneme tablosu'\n@AbapCatalog.enhancement.category : #NOT_EXTENSIBLE\n"
                 "define table zaxet_s_den {\n  key mandt : mandt not null;\n}\n")

    def test_S6_yapi_ayni_adli_seffaf_tablo_var(self):
        """Z53 (canlı bulgu, v0.5.1): SAP `/ddic/structures/<TABLO>/source/main` isteğine şeffaf tablo için de
        200 + `define table …` döndürür (structures ucu 404 VERMEZ). Eski sahte structures=404 / tables=200 modelliyordu
        ⇒ kardeş-uç yolundan geçip `existing_kind: table` diyordu; canlıda araç `structure` dedi. Sahte artık canlıyı taklit
        eder: yapı ucu 200 + `define table`, tablo ucu 200 + aynı kaynak."""
        def ek(c):
            if c["method"] == "GET" and c["path"] in (self.YAPI_SRC, self.TABLO_SRC):
                return Yanit(200, self.TABLO_DDL)
            return None
        adt, r = self._yapi(yon_ek=ek)
        iz = self._yazma_izi(adt)
        ok = (r.get("ok") is False and r.get("error") == "already_exists" and iz == []
              and r.get("existing_kind") == "table" and "TABLO" in str(r.get("message")))
        self.kaydet("S6 yapı (c): aynı adlı ŞEFFAF TABLO var (structures ucu 200 + define table) → already_exists(table), "
                    "yazma YOK", "already_exists · table · yazma 0",
                    f"ok={r.get('ok')} err={r.get('error')} kind={r.get('existing_kind')} iz={iz}", ok)

    def test_S6b_adt_get_tur_kaynak_anahtar_kelimesinden(self):
        """Z53: `adt_get(<tablo>, structure)` 200 + `define table` → `resolved_type: table` + uyarı. Kontrol grubu:
        `adt_get(<yapı>, structure)` 200 + `define structure` → resolved_type YOK (tür düzeltmesi yok); ters yön
        `adt_get(<yapı>, tabl)` tablo ucu 404 → kardeş yapı ucu → `resolved_type: structure` (canlıda doğru olan yol)."""
        def kur(yapi_govde, tablo_kod, tablo_govde=""):
            def yon(c):
                if c["method"] == "GET" and c["path"] == self.YAPI_SRC:
                    return Yanit(200, yapi_govde)
                if c["method"] == "GET" and c["path"] == self.TABLO_SRC:
                    return Yanit(tablo_kod, tablo_govde)
                return Yanit(404, "")
            self.kur(yon)
        kur(self.TABLO_DDL, 200, self.TABLO_DDL)
        r1 = self.atom._adt_get_oku("ZAXET_S_DEN", "structure", False)
        kur(self.YAPI_DDL, 404)
        r2 = self.atom._adt_get_oku("ZAXET_S_DEN", "structure", False)
        r3 = self.atom._adt_get_oku("ZAXET_S_DEN", "tabl", False)
        ok = (r1.get("exists") is True and r1.get("resolved_type") == "table" and "define table" in str(r1.get("warning"))
              and r2.get("exists") is True and "resolved_type" not in r2 and "warning" not in r2
              and r3.get("exists") is True and r3.get("resolved_type") == "structure")
        self.kaydet("S6b adt_get: tablo structures ucunda → resolved_type table (anahtar kelime) · yapı düzeltmesiz · ters yön "
                    "structure", "table · yok · structure",
                    f"r1={r1.get('resolved_type')} r2={r2.get('resolved_type')} w2={'warning' in r2} "
                    f"r3={r3.get('resolved_type')}", ok)

    def test_S7_yapi_kardes_tablo_ucu_olculemedi(self):
        def ek(c):
            if c["method"] == "GET" and c["path"] == self.TABLO_SRC:
                return Yanit(503, "geçici")
            return None
        adt, r = self._yapi(yon_ek=ek)
        iz = self._yazma_izi(adt)
        ok = r.get("ok") is False and r.get("error") == "exists_unmeasured" and iz == []
        self.kaydet("S7 yapı: yapı ucu 404 ama kardeş tablo ucu ÖLÇÜLEMEDİ (503) → exists_unmeasured, yazma YOK",
                    "exists_unmeasured · yazma 0", f"ok={r.get('ok')} err={r.get('error')} "
                    f"pre={r.get('steps', {}).get('pre_check')} iz={iz}", ok)

    def test_S8_lib_create_structure_zaten_var_PUT_etmez(self):
        """Kütüphane düzeyi: POST 405 / 400 + AlreadyExists → SAPObjectExistsError, kilit/PUT YOK; 201 → PUT var (kontrol)."""
        import sap_adt_lib  # type: ignore
        from types import SimpleNamespace
        sonuc = []
        for kod in (405, 400, 201):
            iz = []
            c = object.__new__(sap_adt_lib.SAPADTClient)
            c.url, c.language, c.csrf_token, c.timeout_default = "http://127.0.0.1:9", "TR", "t", 1
            c._get_headers = lambda *_a, **_k: {}
            c._retry_request = lambda fn, *_a, **_k: fn()
            c.lock_object = lambda *_a, **_k: iz.append("lock") or "kilit"
            c.unlock_object = lambda *_a, **_k: iz.append("unlock")
            govde = "AlreadyExists" if kod != 201 else ""
            c.session = SimpleNamespace(
                post=lambda *_a, _k=kod, _g=govde, **_kw: SimpleNamespace(status_code=_k, headers={}, text=_g),
                put=lambda *_a, **_k: iz.append("put") or SimpleNamespace(status_code=200, text=""))
            try:
                c.create_structure("ZAXET_S_DEN", self.YAPI_ALANLARI, "KKD deneme yapısı", "ZAXET_PKG", TR)
                hata = None
            except Exception as exc:  # noqa: BLE001
                hata = exc
            sonuc.append((kod, type(hata).__name__ if hata else None, iz))
        ok = (sonuc[0][1] == "SAPObjectExistsError" and sonuc[0][2] == []
              and sonuc[1][1] == "SAPObjectExistsError" and sonuc[1][2] == []
              and sonuc[2][1] is None and "put" in sonuc[2][2])
        self.kaydet("S8 lib create_structure: POST 405/400 AlreadyExists → SAPObjectExistsError, kilit/PUT YOK (201'de PUT)",
                    "Exists ×2 · iz [] · 201 PUT", str(sonuc), ok)

    def _gercek_retry(self, adt):
        """Kütüphanenin GERÇEK `_retry_request` + `_should_retry`'ı (bekleme 0) sahte ADT'ye bağla."""
        import sap_adt_lib  # type: ignore
        k = sap_adt_lib.SAPADTClient
        adt.max_retries, adt.retry_delay = 3, 0.0
        adt.retry_on_timeout = adt.retry_on_csrf_fail = adt.retry_on_5xx = True
        adt.retry_on_lock_conflict = False
        adt._should_retry = k._should_retry.__get__(adt)
        adt._retry_request = k._retry_request.__get__(adt)

    def test_S9_yapi_5xx_retry_sonrasi_zaten_var_ayri_kod(self):
        """Z52 (bug gate L1): ilk POST 500 (SAP kabuğu yaratmış olabilir) → kütüphane yeniden dener → 405 AlreadyExists.
        Beklenen: `already_exists_after_retry` (aracın KENDİ önceki denemesi olabilir), yazma/aktivasyon YOK.
        Kontrol grubu: retry'sız 405 → düz `already_exists` (S5 ile aynı)."""
        import sap_adt_lib  # type: ignore
        sira = {"n": 0}

        def ek(c):
            if c["method"] == "POST" and c["path"] == "/sap/bc/adt/ddic/structures":
                sira["n"] += 1
                if sira["n"] == 1:
                    return Yanit(500, "Internal Server Error")
                return Yanit(405, "<exc:exception><type id=\"ExceptionResourceAlreadyExists\"/>"
                                  "<localizedMessage>AlreadyExists</localizedMessage></exc:exception>")
            return None
        # `_yapi(gercek_lib=True)` `_retry_request`'i düz fn() yapar → gerçek retry (bekleme 0) create_structure
        # çağrısının içinde bağlanır.
        from sap_client import SAPClient  # type: ignore
        eski_cs = SAPClient.create_structure

        def cs(ist, *a, **kw):
            self._gercek_retry(ist.adt_client)
            return eski_cs(ist, *a, **kw)
        SAPClient.create_structure = cs
        self.addCleanup(setattr, SAPClient, "create_structure", eski_cs)
        adt, r = self._yapi(yon_ek=ek, gercek_lib=True)
        post = [c for c in adt.cagri if c["method"] == "POST" and c["path"] == "/sap/bc/adt/ddic/structures"]
        yazma = [c for c in adt.cagri if c["method"] == "PUT" or c["path"] in ("lock_object",)
                 or c["path"].startswith("activate")]
        msg = str(r.get("message"))
        ok = (r.get("ok") is False and r.get("error") == "already_exists_after_retry" and len(post) == 2
              and yazma == [] and "adt_get" in msg and "önceki" in msg.lower())
        self.kaydet("S9 yapı: POST 500 → retry → 405 AlreadyExists → already_exists_after_retry, yazma YOK",
                    "already_exists_after_retry · POST 2 · yazma 0",
                    f"ok={r.get('ok')} err={r.get('error')} post={len(post)} yazma={len(yazma)} msg={msg[:80]}", ok)

    def test_S9b_yapi_baglanti_hatasi_retry_sonrasi_zaten_var(self):
        """Bug gate MEDIUM (v0.5.1): ilk POST gitti ama yanıt yerine bağlantı koptu (ConnectionError) → kütüphane yeniden
        dener → 405 AlreadyExists → `already_exists_after_retry` + `own_shell_possible`, yazma YOK (S9'un bağlantı kolu)."""
        import requests  # type: ignore
        sira = {"n": 0}

        def ek(c):
            if c["method"] == "POST" and c["path"] == "/sap/bc/adt/ddic/structures":
                sira["n"] += 1
                if sira["n"] == 1:
                    raise requests.exceptions.ConnectionError("RemoteDisconnected: bağlantı koptu")
                return Yanit(405, "<exc:exception><type id=\"ExceptionResourceAlreadyExists\"/>"
                                  "<localizedMessage>AlreadyExists</localizedMessage></exc:exception>")
            return None
        from sap_client import SAPClient  # type: ignore
        eski_cs = SAPClient.create_structure

        def cs(ist, *a, **kw):
            self._gercek_retry(ist.adt_client)
            return eski_cs(ist, *a, **kw)
        SAPClient.create_structure = cs
        self.addCleanup(setattr, SAPClient, "create_structure", eski_cs)
        adt, r = self._yapi(yon_ek=ek, gercek_lib=True)
        yazma = [c for c in adt.cagri if c["method"] == "PUT" or c["path"] in ("lock_object",)
                 or c["path"].startswith("activate")]
        ok = (r.get("ok") is False and r.get("error") == "already_exists_after_retry"
              and r.get("own_shell_possible") is True and sira["n"] == 2 and yazma == [])
        self.kaydet("S9b yapı: POST bağlantı hatası → retry → 405 → already_exists_after_retry, yazma YOK",
                    "already_exists_after_retry · POST 2 · yazma 0",
                    f"ok={r.get('ok')} err={r.get('error')} own={r.get('own_shell_possible')} post={sira['n']} "
                    f"yazma={len(yazma)}", ok)

    def test_S9c_yeniden_deneme_izi_iki_kaynak_ayri_ayri(self):
        """Bug gate MEDIUM (v0.5.1): `already_exists_after_retry` kararının iki izi AYRI AYRI ölçülür (uçtan uca testte
        biri öbürünü örter): ① kütüphane hükmü (`ONCEKI_DENEME_IZI`, `[RETRY]` satırı yok) ② `[RETRY] … Connection error`
        satırı (kütüphane eki yok). Kontrol: yalnız CSRF yeniden denemesi · iz yok → düz `already_exists`. Kütüphane eki
        yalnız `_son_yeniden_denemeler` doluysa konur ve sebebi taşır."""
        import sap_adt_lib  # type: ignore
        from types import SimpleNamespace
        from sapadt.tools import composite
        IZ = sap_adt_lib.ONCEKI_DENEME_IZI
        loglar = {
            "lib_hukmu": "[ERROR] [405] Domain ZAXET_D_X already exists (SAP 405 AlreadyExists) — üzerine YAZILMADI "
                         "(kilit/PUT/aktivasyon yok) — %s (…: Connection error (attempt 1)) kabuğu yaratmış olabilir" % IZ,
            "retry_baglanti": "  [RETRY] Create domain - Connection error (attempt 1), retrying in 0.0s...\n[ERROR] [405] x",
            "retry_5xx": "  [RETRY] Create domain - Server error 503 (attempt 1), retrying in 0.0s...\n[ERROR] [405] x",
            "retry_timeout": "  [RETRY] Create domain - Timeout (attempt 1), retrying in 0.0s...\n[ERROR] [405] x",
            "yalniz_csrf": "  [RETRY] Create domain - CSRF token expired (attempt 1), retrying in 0.0s...\n[ERROR] [405] x",
            "iz_yok": "[ERROR] [405] Domain ZAXET_D_X already exists (SAP 405 AlreadyExists)",
            # gate LOW-1 (düzeltme turu): sarmalayıcı açıklamayı da log'a basar — izi TÜM log'da aramak yanlış pozitif
            "aciklama_ici": "  Description: %s TARİHİ\n[ERROR] [405] Domain ZAXET_D_X already exists (SAP 405 "
                            "AlreadyExists) — üzerine YAZILMADI (kilit/PUT/aktivasyon yok)" % IZ,
        }
        sonuc = {k: composite._zaten_var_yaniti("Domain", "ZAXET_D_X", "doma", v)["error"] for k, v in loglar.items()}
        c = SimpleNamespace(_son_yeniden_denemeler=["Connection error (attempt 1)"])
        yanit = SimpleNamespace(status_code=405, text="AlreadyExists")
        dolu = str(sap_adt_lib.SAPADTClient._zaten_var_hatasi(c, "Domain", "ZAXET_D_X", yanit, "/e", yeniden_deneme=True))
        bos = str(sap_adt_lib.SAPADTClient._zaten_var_hatasi(SimpleNamespace(_son_yeniden_denemeler=[]), "Domain",
                                                              "ZAXET_D_X", yanit, "/e", yeniden_deneme=False))
        beklenen = {"lib_hukmu": "already_exists_after_retry", "retry_baglanti": "already_exists_after_retry",
                    "retry_5xx": "already_exists_after_retry", "retry_timeout": "already_exists_after_retry",
                    "yalniz_csrf": "already_exists", "iz_yok": "already_exists", "aciklama_ici": "already_exists"}
        # v0.5.2 (v0.5.1 gate LOW): kütüphanenin GERÇEK mesajı composite regex'inden geçer — ek biçimi değişirse
        # yedek `[RETRY]` izi birincil izi örttüğü için uçtan uca testler yeşil kalırdı; bağ burada doğrudan sınanır.
        gercek_dolu = composite._yeniden_deneme_izi("[ERROR] " + dolu)
        gercek_bos = composite._yeniden_deneme_izi("[ERROR] " + bos)
        ok = (sonuc == beklenen and IZ in dolu and "Connection error (attempt 1)" in dolu and IZ not in bos
              and gercek_dolu is True and gercek_bos is False)
        self.kaydet("S9c after_retry izi: kütüphane hükmü / [RETRY] bağlantı-5xx-timeout ayrı ayrı · CSRF / iz yok → düz",
                    str(beklenen) + " · lib eki sebepli · gerçek mesaj regex'ten True/False",
                    f"{sonuc} · dolu_ek={IZ in dolu} bos_ek={IZ in bos} · regex={gercek_dolu}/{gercek_bos}", ok)

    def test_S6c_ddl_turu_yorumlar_atlanir(self):
        """Bug gate LOW (v0.5.1): `define table|structure` aranmadan önce `/* … */` blokları ve `//` satır yorumları atılır;
        tırnak içindeki `/*` / `//` yorum sayılmaz. Kontrol grubu: annotation'lı yapı · büyük harf `DEFINE TABLE` · yorumsuz."""
        f = self.atom._ddl_kaynak_turu
        vakalar = {
            "blok_yorum": ("/*\ndefine structure old\n*/\ndefine table zaxet_t {\n  key mandt : mandt not null;\n}", "table"),
            "blok_yorum_ters": ("/* define table eski\n   devam */\ndefine structure zaxet_s {\n  f : char10;\n}", "structure"),
            "satir_yorum": ("// define structure eski\ndefine table zaxet_t {\n}", "table"),
            "satir_ici_blok": ("/* define table */ define structure zaxet_s {\n}", "structure"),
            "tirnak_ici": ("@EndUserText.label : 'etiket /* yorum değil'\ndefine table zaxet_t {\n}", "table"),
            "tirnak_ici_kapanan": ("@EndUserText.label : 'etiket /* yorum değil'\ndefine table zaxet_t {\n"
                                   "  f : char10; /* son */\n}", "table"),
            "tirnak_ici_2": ("@EndUserText.label : 'http://ornek'\ndefine structure zaxet_s {\n}", "structure"),
            "annotation": ("@EndUserText.label : 'Yapı'\n@AbapCatalog.enhancement.category : #NOT_EXTENSIBLE\n"
                           "define structure zaxet_s {\n  f : char10;\n}", "structure"),
            "buyuk_harf": ("DEFINE TABLE ZAXET_T {\n}", "table"),
            "tanim_yok": ("/* define table */\n// define structure\n", None),
        }
        sonuc = {k: f(v[0]) for k, v in vakalar.items()}
        beklenen = {k: v[1] for k, v in vakalar.items()}
        # gate LOW-2 (düzeltme turu): çok sayıda KAPANMAMIŞ `/*` ikinci dereceden süre alıyordu (30 KB ≈ 1,4 sn,
        # 100 KB ≈ 43 sn ölçüldü). Kapanmamış blok metin sonuna kadar yorum sayılır → doğrusal.
        import time
        t0 = time.perf_counter()
        kapanmamis = f("/* " * 10000 + "\ndefine table zaxet_t {\n}")
        sure = time.perf_counter() - t0
        sonuc["kapanmamis_cok"] = (kapanmamis, sure < 0.3)
        beklenen["kapanmamis_cok"] = (None, True)
        self.kaydet("S6c DDL türü: yorumlar atlanır, tırnak içi korunur, annotation / büyük harf doğru",
                    str(beklenen), str(sonuc), sonuc == beklenen)

    @staticmethod
    def _lib_istemci(post_yanitlari, put_kod=200, iz=None):
        """`object.__new__(SAPADTClient)`: POST'lar sırayla `post_yanitlari`'ndan döner, kilit/PUT/aktivasyon `iz`'e düşer."""
        import sap_adt_lib  # type: ignore
        from types import SimpleNamespace
        iz = [] if iz is None else iz
        c = object.__new__(sap_adt_lib.SAPADTClient)
        c.url, c.language, c.csrf_token, c.timeout_default, c.debug_enabled = "http://127.0.0.1:9", "TR", "t", 1, False
        c.client = "100"
        c._get_headers = lambda *_a, **_k: {}
        c._retry_request = lambda fn, *_a, **_k: fn()
        c.lock_object = lambda *_a, **_k: iz.append("lock") or "kilit"
        c.unlock_object = lambda *_a, **_k: iz.append("unlock")
        c.activate_object = lambda *_a, **_k: iz.append("activate") or {"success": True}
        c._get_domain_typeinfo = lambda *_a, **_k: ("CHAR", "000010", "000000")
        c.user = "AXETTEST"
        sira = list(post_yanitlari)

        def post(*_a, **_k):
            kod, govde = sira.pop(0) if len(sira) > 1 else sira[0]
            return SimpleNamespace(status_code=kod, headers={}, text=govde)
        c._request_with_csrf_retry = lambda m, *_a, **_k: (
            post() if m == "post" else iz.append("put") or SimpleNamespace(status_code=put_kod, text=""))
        c.session = SimpleNamespace(
            post=post, put=lambda *_a, **_k: iz.append("put") or SimpleNamespace(status_code=put_kod, text=""),
            headers={})
        return c, iz

    def test_S10_lib_ayni_sinif_zaten_var_basari_sayilmaz(self):
        """Z51 ⓐ/ⓑ + kardeş taraması: domain / DTEL / BDEF / CDS / FUGR / FM POST'u 405|400 AlreadyExists → SAPObjectExistsError,
        kilit/PUT/aktivasyon YOK. Kontrol grubu: 201 → başarı (BDEF'te kaynak verildiyse PUT var)."""
        import sap_adt_lib  # type: ignore
        var = "<exc:exception><localizedMessage>ExceptionResourceAlreadyExists AlreadyExists</localizedMessage>"
        cagrilar = {
            "domain": lambda c: c.create_domain("ZAXET_D_X", "CHAR", 10, "Deneme", "ZAXET_PKG", transport=TR),
            "dtel": lambda c: c.create_dataelement("ZAXET_E_X", "CHAR10", "Deneme", "ZAXET_PKG", short_label="a",
                                                   medium_label="b", long_label="c", heading_label="d", transport=TR),
            "bdef": lambda c: c.create_behavior_definition("ZAXET_I_X", "ZAXET_I_X", "Managed", "ZAXET_PKG", "Deneme",
                                                           TR, source="managed;", activate=True),
            "cds": lambda c: c.create_cds_view("ZAXET_I_X", "define view entity ZAXET_I_X as select from t000 "
                                               "{ key mandt }", "Deneme", "ZAXET_PKG", transport=TR),
            "fugr": lambda c: c.create_function_group("ZAXET_FG", "Deneme", "ZAXET_PKG", transport=TR),
            "fm": lambda c: c.create_function_module("Z_AXET_FM", "ZAXET_FG", "Deneme", transport=TR),
        }
        sonuc = {}
        for ad, f in cagrilar.items():
            satir = []
            for kod in (405, 400, 201):
                c, iz = self._lib_istemci([(kod, var if kod != 201 else "")])
                try:
                    r = f(c)
                    hata = None
                except Exception as exc:  # noqa: BLE001
                    r, hata = None, exc
                satir.append((kod, type(hata).__name__ if hata else ("ok" if (r or {}).get("success") else r), iz))
            sonuc[ad] = satir
        kotu = []
        for ad, satir in sonuc.items():
            for kod, h, iz in satir:
                if kod in (405, 400) and not (h == "SAPObjectExistsError" and iz == []):
                    kotu.append((ad, kod, h, iz))
                if kod == 201 and h != "ok":
                    kotu.append((ad, kod, h, iz))
        bdef_201_iz = sonuc["bdef"][2][2]
        ok = not kotu and "put" in bdef_201_iz and sap_adt_lib.SAPObjectExistsError
        self.kaydet("S10 lib: domain/DTEL/BDEF/CDS/FUGR/FM AlreadyExists → SAPObjectExistsError, yazma YOK (201 kontrol)",
                    "kötü 0 · bdef 201 PUT", f"kötü={kotu} bdef201={bdef_201_iz}", bool(ok))

    def test_S10b_lib_type_group_zaten_var_basari_sayilmaz(self):
        """v0.5.2 (v0.5.1 kardeş taramasında raporlanıp bırakılan): `create_type_group` 403 + 'already exists' → erken
        `success:True` dönüyordu (sap_client "created successfully" basıyordu). Artık 403-imzası ve 405|400 AlreadyExists
        → SAPObjectExistsError, PUT YOK. Kontrol grubu: 201 → başarı + kaynak PUT'u."""
        var = "<exc:exception><localizedMessage>ExceptionResourceAlreadyExists AlreadyExists</localizedMessage>"
        satir = []
        for kod, govde in ((403, "Type group ZAXET_TG already exists"), (405, var), (400, var), (201, "")):
            c, iz = self._lib_istemci([(kod, govde)])
            c.fetch_csrf_token = lambda *_a, **_k: None
            try:
                r = c.create_type_group("ZAXET_TG", "TYPES t TYPE c LENGTH 1.", "Deneme", "ZAXET_PKG", transport=TR)
                h = "ok" if (r or {}).get("success") else r
            except Exception as exc:  # noqa: BLE001
                h = type(exc).__name__
            satir.append((kod, h, list(iz)))
        ok = (all(h == "SAPObjectExistsError" and iz == [] for kod, h, iz in satir if kod != 201)
              and satir[-1][1] == "ok" and "put" in satir[-1][2])
        self.kaydet("S10b lib type group: 403/405/400 zaten var → SAPObjectExistsError, PUT yok (201 kontrol)",
                    "istisna ×3 · 201 ok+put", str(satir), ok)

    def test_S11_paket_bos_ya_da_bosluk_ag_oncesi_red(self):
        """Z50 ⓕ: `package` boş / yalnız boşluk → yaratma araçları (ttyp/table/struct) AĞA GİTMEDEN `validation_error`."""
        from sapadt.tools import composite
        eski = composite.run_reviewer_struct
        composite.run_reviewer_struct = lambda *a, **k: _pass()
        self.addCleanup(setattr, composite, "run_reviewer_struct", eski)
        adt, _ = self.kur(lambda c: AssertionError("ağ"))
        self.ddic._varlik = lambda n, t: (_ for _ in ()).throw(AssertionError("sonda"))
        sonuc = []
        for paket in ("", "   "):
            for ad, f in (("ttyp", lambda p: self.ddic.adt_ttyp_create("ZAXET_TT_DEN", "Deneme", p, TR,
                                                                         row_type="ZAXET_S_SATIR")),
                          ("table", lambda p: self.ddic.adt_table_create("ZAXET_T_DEN", "Deneme", ALANLAR, p, TR)),
                          ("struct", lambda p: composite.adt_struct_create("ZAXET_S_DEN", self.YAPI_ALANLARI, "Deneme",
                                                                           p, TR)),
                          # v0.5.2: domain/DTEL de aynı kapıdan (önceden yalnız lib "" reddediyordu, "   " POST'a gidiyordu)
                          ("doma", lambda p: composite.adt_domain_create("ZAXET_D_DEN", "CHAR", 10, "Deneme", p, TR)),
                          ("dtel", lambda p: composite.adt_dtel_create("ZAXET_E_DEN", "CHAR10", "Deneme", p, TR,
                                                                       "Kısa", "Orta etiket", "Uzun etiket", "Başlık"))):
                try:
                    r = f(paket)
                except AssertionError as exc:
                    r = {"error": f"ağa gitti: {exc}"}
                sonuc.append((ad, repr(paket), r.get("error")))
        ok = all(e == "validation_error" for *_x, e in sonuc) and adt.cagri == []
        self.kaydet("S11 paket boş/boşluk → validation_error ×10 (ttyp/table/struct/doma/dtel), ağ 0", "validation_error ×10 · çağrı 0",
                    f"{sonuc} çağrı={len(adt.cagri)}", ok)

    def test_S12_fm_unlock_sonucu_gorunur(self):
        """Z50 ⓓ: `set_function_module_source` UNLOCK yanıtı 200/204 değil ya da istisna → `unlock_ok:false` +
        `unlock_warning` (yazma sonucu korunur); PUT reddinde de istisna `unlock_ok` taşır. Kontrol: UNLOCK 200 → True."""
        import sap_adt_lib  # type: ignore
        from types import SimpleNamespace
        kilit = SimpleNamespace(status_code=200, text="<DATA><LOCK_HANDLE>H1</LOCK_HANDLE><CORRNR></CORRNR></DATA>")

        def kos(unlock, put_kod=200):
            c = object.__new__(sap_adt_lib.SAPADTClient)
            c.url, c.csrf_token, c.timeout_default, c.timeout_short = "http://127.0.0.1:9", "t", 1, 1
            c.fetch_csrf_token = lambda force_refresh=False: None

            def post(url, params=None, **_k):
                if (params or {}).get("_action") == "LOCK":
                    return kilit
                if isinstance(unlock, Exception):
                    raise unlock
                return SimpleNamespace(status_code=unlock, text="kilit gövdesi")
            c.session = SimpleNamespace(headers={}, post=post,
                                        put=lambda *_a, **_k: SimpleNamespace(status_code=put_kod, text=""))
            try:
                return c.set_function_module_source("Z_AXET_FM", "ZAXET_FG", "FUNCTION z_axet_fm.\nENDFUNCTION.",
                                                    transport=TR), None
            except Exception as exc:  # noqa: BLE001
                return None, exc
        r200, _ = kos(200)
        r403, _ = kos(403)
        rexc, _ = kos(ConnectionError("koptu"))
        _r, hata = kos(403, put_kod=500)
        ok = (r200.get("unlock_ok") is True and not r200.get("unlock_warning")
              and r403.get("success") is True and r403.get("unlock_ok") is False and "SM12" in str(r403.get("unlock_warning"))
              and rexc.get("unlock_ok") is False and bool(rexc.get("unlock_warning"))
              and hata is not None and getattr(hata, "unlock_ok", None) is False)
        self.kaydet("S12 FM UNLOCK: 200 → ok · 403/istisna → unlock_ok:false + uyarı · PUT reddinde istisna unlock_ok taşır",
                    "True · False+uyarı ×2 · exc False",
                    f"{r200.get('unlock_ok')} · {r403.get('unlock_ok')} {str(r403.get('unlock_warning'))[:30]} · "
                    f"{rexc.get('unlock_ok')} · {getattr(hata, 'unlock_ok', 'yok')}", ok)

    def test_S13_bdef_push_unlock_yanit_kodu(self):
        """Z50 ⓔ: `_push_bdef_kaynak` UNLOCK yanıtı 200/204 değil → `unlock_ok:false` + `unlock_warning`. Kontrol: 200 → uyarı yok."""
        def kos(unlock_kod):
            def yon(c):
                pr = c["params"]
                if pr.get("_action") == "LOCK":
                    return Yanit(200, "<DATA><LOCK_HANDLE>HB1</LOCK_HANDLE></DATA>")
                if pr.get("_action") == "UNLOCK":
                    return Yanit(unlock_kod, "")
                if c["method"] == "PUT":
                    return Yanit(200, "")
                if c["method"] == "GET":
                    return Yanit(200, "managed;")
                return Yanit(500, "beklenmedik")
            adt, ist = self.kur(yon)
            return self.atom._push_bdef_kaynak(ist, "ZAXET_I_X", "managed;", TR)
        r200, r403 = kos(200), kos(403)
        ok = (r200.get("unlock_ok") is True and "unlock_warning" not in r200
              and r403.get("success") is True and r403.get("unlock_ok") is False and bool(r403.get("unlock_warning")))
        self.kaydet("S13 BDEF push UNLOCK 403 → unlock_ok:false + uyarı (200'de yok)", "True · False+uyarı",
                    f"{r200.get('unlock_ok')} {r200.get('unlock_warning')} · {r403.get('unlock_ok')} "
                    f"{str(r403.get('unlock_warning'))[:30]}", ok)

    def test_S14_ag_istisnasi_belirsiz_mesaj(self):
        """Z50 ⓒ: istek GÖNDERİLDİKTEN sonra ağ istisnası → "yazıldığı / kilit durumu BELİRSİZ" (HTTP reddinden ayrı).
        tablo LOCK/PUT · textpool LOCK/PUT · ttyp onarım PUT. Kontrol grubu: HTTP reddi (403/400) ve CSRF istisnası (istek
        gitmeden, T11) belirsiz DEĞİL."""
        sonuc = {}
        # tablo: LOCK ağ istisnası / PUT ağ istisnası / PUT 400 (kontrol)
        for ad, kilit, put in (("t_lock", ConnectionError("koptu"), None), ("t_put", None, ConnectionError("koptu")),
                               ("t_put400", None, 400)):
            yon0 = self._tablo_yon(put_kod=put if isinstance(put, int) else 200)

            def yon(c, _y=yon0, _k=kilit, _p=put):
                if _k is not None and c["method"] == "POST" and c["params"].get("_action") == "LOCK":
                    return _k
                if isinstance(_p, Exception) and c["method"] == "PUT":
                    return _p
                return _y(c)
            self.kur(yon)
            r = self.ddic.adt_table_create("ZAXET_T_DEN", "Deneme tablosu", ALANLAR, "ZAXET_PKG", TR)
            sonuc[ad] = (r.get("error"), r.get("outcome_uncertain"), "BELİRSİZ" in str(r.get("message")))
        # textpool: kilit ağ istisnası / kilit HTTP reddi (kontrol) / PUT ağ istisnası
        import sap_adt_lib  # type: ignore
        for ad, kilit_hata in (("p_lock", ConnectionError("koptu")),
                               ("p_lock403", sap_adt_lib.SAPLockError("kilitli", status_code=403))):
            adt, _ = self.kur(lambda c: Yanit(200, "", {"ETag": "e"}))

            def lk(*_a, _h=kilit_hata, **_k):
                raise _h
            adt.lock_object = lk
            r = self.tp.adt_textpool_write("ZAXET_P_DEN", TR, symbols=self.SEM)
            sonuc[ad] = (r.get("error"), r.get("outcome_uncertain"), "BELİRSİZ" in str(r.get("message")))
        eski_kur = self.kur

        def kur_put(yon, sql=None):
            def yon2(c):
                if c["method"] == "PUT":
                    return ConnectionError("koptu")
                return yon(c)
            return eski_kur(yon2, sql)
        self.kur = kur_put
        try:
            _a, r = self._tp(symbols=self.SEM)
        finally:
            self.kur = eski_kur
        sonuc["p_put"] = (r.get("error"), r.get("outcome_uncertain"), "BELİRSİZ" in str(r.get("message")))
        # ttyp onarım PUT ağ istisnası
        bos_x, bos_s = self._ttyp_xml(type_name=""), self._dd40l(rowtype="", rowkind="", datatype="")
        _a, r = self._ttyp([bos_x], [bos_s], put_kod=ConnectionError("koptu"))
        sonuc["y_put"] = (r.get("error"), r["steps"].get("repair", {}).get("outcome_uncertain"),
                          "BELİRSİZ" in str(r.get("message")))
        beklenen = {"t_lock": ("partial_shell", "lock", True), "t_put": ("partial_shell", "put", True),
                    "t_put400": ("partial_shell", None, False), "p_lock": ("lock_failed", "lock", True),
                    "p_lock403": ("lock_failed", None, False), "p_put": ("put_failed", "put", True),
                    "y_put": ("row_type_empty_repair_failed", True, True)}
        ok = sonuc == beklenen
        self.kaydet("S14 ağ istisnası (istek gitti) → BELİRSİZ + outcome_uncertain; HTTP reddi belirsiz DEĞİL",
                    str(beklenen)[:150], str(sonuc), ok)

    # Canlı (r2_21_ttyp2 / r2_23_ttyp4): ilkel satırda POST tanımı düşürdü; SAP varsayılanı CHAR·000001 kaldı →
    # `durum:"uyumsuz"` → onarım hiç denenmedi. Readback istenenden FARKLIYSA da bir kez If-Match PUT denenmeli.
    def _varsayilan_char1(self):
        return (self._ttyp_xml(type_name="", data_type="CHAR", kk="predefinedAbapType", length="000001"),
                self._dd40l(rowtype=None, rowkind=None, datatype="CHAR", leng="000001"))

    def test_Y15_ttyp_ilkel_varsayilan_char1_onarim(self):
        x0, s0 = self._varsayilan_char1()
        x1 = self._ttyp_xml(type_name="", data_type="CHAR", kk="predefinedAbapType", length="000010")
        s1 = self._dd40l(rowtype=None, rowkind=None, datatype="CHAR", leng="000010")
        adt, r = self._ttyp([x0, x1], [s0, s1], row_type=None, builtin={"data_type": "CHAR", "length": 10})
        put = [c for c in adt.cagri if c["method"] == "PUT"]
        post = [c for c in adt.cagri if c["method"] == "POST"][0]
        akt = [c for c in adt.cagri if c["path"].startswith("activate")]
        st = r["steps"]
        ok = (r.get("ok") is True and len(put) == 1 and put[0]["data"] == post["data"]
              and put[0]["headers"].get("If-Match") == "etag-1" and len(akt) == 2
              and st["readback"]["durum"] == "uyumsuz" and st.get("readback_2", {}).get("durum") == "dolu")
        self.kaydet("Y15 ttyp: ilkel CHAR(10) → canlı varsayılan CHAR·000001 (uyumsuz) → If-Match PUT → dolu → OK",
                    "PUT 1 · aktive 2 · ok", f"ok={r.get('ok')} err={r.get('error')} put={len(put)} akt={len(akt)}", ok)

    def test_Y16_ttyp_ilkel_onarim_sonrasi_hala_farkli_FAIL(self):
        x0, s0 = self._varsayilan_char1()
        adt, r = self._ttyp([x0, x0], [s0, s0], row_type=None,
                            builtin={"data_type": "DEC", "length": 15, "decimals": 2})
        put = [c for c in adt.cagri if c["method"] == "PUT"]
        st = r["steps"]
        ok = (r.get("ok") is False and r.get("error") == "readback_mismatch" and len(put) == 1
              and st.get("readback_2", {}).get("durum") == "uyumsuz" and "DATATYPE" in r.get("message", ""))
        self.kaydet("Y16 ttyp: DEC 15,2 — onarım PUT'u sonrası hâlâ CHAR·1 → readback_mismatch (asla sahte OK)",
                    "readback_mismatch · PUT 1", f"ok={r.get('ok')} err={r.get('error')} put={len(put)} "
                    f"{str(r.get('message'))[:90]}", ok)

    def test_Y17_ttyp_onarim_sonrasi_verify_t2_kullanilir(self):
        """Z50 ⓐ: onarım sonrası nihai `ok` ikinci aktivasyonun doğrulamasından (t2.verified) gelir."""
        bos_x, bos_s = self._ttyp_xml(type_name=""), self._dd40l(rowtype="", rowkind="", datatype="")
        eski_init = DdicIstemci.__init__

        def init(s, adt, sql=None):
            eski_init(s, adt, sql)
            s.metadata = [AKTIF_MD, '<adtcore:mainObject adtcore:masterLanguage="TR" adtcore:version="inactive"/>']
        DdicIstemci.__init__ = init
        self.addCleanup(setattr, DdicIstemci, "__init__", eski_init)
        adt, r = self._ttyp([bos_x, self._ttyp_xml()], [bos_s, self._dd40l()])
        ok = (r.get("ok") is False and r.get("error") == "verify_failed"
              and r["steps"].get("readback_2", {}).get("durum") == "dolu")
        self.kaydet("Y17 ttyp: onarım sonrası 2. aktivasyon 'active' doğrulanamadı → verify_failed (t2)",
                    "verify_failed", f"ok={r.get('ok')} err={r.get('error')} v2={r['steps'].get('verify_2')}", ok)

    def test_Y18_ttyp_uyumsuz_onarim_put_hatasi(self):
        x0, s0 = self._varsayilan_char1()
        adt, r = self._ttyp([x0], [s0], put_kod=412, row_type=None, builtin={"data_type": "CHAR", "length": 10})
        akt = [c for c in adt.cagri if c["path"].startswith("activate")]
        ok = (r.get("ok") is False and r.get("error") == "readback_mismatch_repair_failed"
              and r["steps"].get("repair", {}).get("http_status") == 412 and len(akt) == 1)
        self.kaydet("Y18 ttyp: uyumsuz → onarım PUT 412 → readback_mismatch_repair_failed, 2. aktivasyon yok",
                    "readback_mismatch_repair_failed", f"ok={r.get('ok')} err={r.get('error')} akt={len(akt)}", ok)

    # Canlı (r2_34_tp1 / r2_35): `activate_prog` her çağrıda ok:false ("yalniz_generation", worklist PROG/P + PX
    # inaktif) raporluyordu; ardından PX aktivasyonu terfi ettiriyordu → yanıltıcı FAIL gürültüsü.
    WL_BOS = '<ioc:inactiveObjects xmlns:ioc="http://www.sap.com/abapxml/inactiveCtsObjects"/>'

    @staticmethod
    def _wl(*girdiler):
        g = "".join(
            '<ioc:entry><ioc:object ioc:user="U"><ioc:ref adtcore:uri="%s" adtcore:type="%s" adtcore:name="%s"/>'
            "</ioc:object></ioc:entry>" % girdi for girdi in girdiler)
        return ('<ioc:inactiveObjects xmlns:ioc="http://www.sap.com/abapxml/inactiveCtsObjects" '
                'xmlns:adtcore="http://www.sap.com/adt/core">' + g + "</ioc:inactiveObjects>")

    AKT_YALNIZ_GEN = {
        "success": False, "aktivasyon_hukmu": False, "hukum_sebep": "yalniz_generation",
        "aktivasyon_dogrulama": {"kaynak": "worklist", "sonda": "checked_inactive", "kalan_inaktif": [
            {"name": "ZAXET_P_DEN", "type": "PROG/P"}, {"name": "ZAXET_P_DEN", "type": "PROG/PX"}]},
        "errors": [{"type": "E", "message": "Aktivasyon GERCEKLESMEDI: govde hukum tasimiyordu (yalniz_generation) "
                                            "ve bagimsiz worklist sondasi hedefleri HALA inaktif gordu: "
                                            "ZAXET_P_DEN (PROG/P), ZAXET_P_DEN (PROG/PX)"}]}

    def _tp_wl(self, wl, akt, **kw):
        eski_kur = self.kur

        def kur(yon, sql=None):
            def yon2(c):
                if c["method"] == "GET" and c["path"] == "/sap/bc/adt/activation/inactiveobjects":
                    return wl if isinstance(wl, Yanit) else Yanit(200, wl)
                return yon(c)
            adt, ist = eski_kur(yon2, sql)
            adt.akt_sonuc = akt
            return adt, ist
        self.kur = kur
        try:
            return self._tp(**kw)
        finally:
            self.kur = eski_kur

    def test_P8_textpool_prog_yalniz_generation_gurultu_degil(self):
        adt, r = self._tp_wl(self.WL_BOS, self.AKT_YALNIZ_GEN, symbols=self.SEM)
        ap, af = r["steps"].get("activate_prog", {}), r["steps"].get("activation_final", {})
        ok = (r.get("ok") is True and ap.get("ok") is True and ap.get("outcome") == "generation_only"
              and af.get("ok") is True and af.get("sonda") == "checked_active")
        self.kaydet("P8 textpool: PROG/P yalnız generation + PX sonrası worklist temiz → ok, activate_prog ok",
                    "ok · generation_only · final temiz", f"ok={r.get('ok')} ap={ap} af={af}", ok)

    def test_P9_textpool_px_sonrasi_hala_inaktif_FAIL(self):
        wl = self._wl(("/sap/bc/adt/programs/programs/zaxet_p_den", "PROG/P", "ZAXET_P_DEN"))
        akt = {"success": False, "aktivasyon_hukmu": False, "hukum_sebep": "hata_mesaji",
               "errors": [{"type": "E", "message": "Sözdizimi hatası satır 3"}]}
        adt, r = self._tp_wl(wl, akt, symbols=self.SEM)
        ap, af = r["steps"].get("activate_prog", {}), r["steps"].get("activation_final", {})
        ok = (r.get("ok") is False and r.get("error") == "activation_incomplete" and ap.get("ok") is False
              and "Sözdizimi hatası satır 3" in ap.get("errors", []) and af.get("ok") is False
              and af.get("kalan_inaktif") == ["ZAXET_P_DEN (PROG/P)"])
        self.kaydet("P9 textpool: PROG/P gerçek hata + PX sonrası worklist'te PROG/P → activation_incomplete",
                    "activation_incomplete", f"ok={r.get('ok')} err={r.get('error')} ap={ap} af={af}", ok)

    def test_P10_textpool_son_sonda_olculemedi_gorunur(self):
        adt, r = self._tp_wl(Yanit(500, "x"), self.AKT_YALNIZ_GEN, symbols=self.SEM)
        ap, af = r["steps"].get("activate_prog", {}), r["steps"].get("activation_final", {})
        ok = (r.get("ok") is True and af.get("ok") is None and str(af.get("sonda", "")).startswith("unavailable")
              and ap.get("ok") is None and bool(r.get("activation_notice")))
        self.kaydet("P10 textpool: son worklist sondası ölçülemedi → readback hükmü + ÖLÇÜLEMEDİ notu görünür",
                    "ok · final None · notice", f"ok={r.get('ok')} ap={ap} af={af} n={r.get('activation_notice')}", ok)

    def test_P12_textpool_prog_hatasi_ve_son_sonda_olculemedi_FAIL(self):
        """P10'un kardeşi: PROG/P gövdesinde GERÇEK E mesajı + son worklist sondası ölçülemedi → ok:false
        (`activation_unverified`); aktif readback doğru görünse de program aktivasyon hatası 'başarı' sayılmaz."""
        akt = {"success": False, "aktivasyon_hukmu": False, "hukum_sebep": "hata_mesaji",
               "errors": [{"type": "E", "message": "Sözdizimi hatası satır 3"}]}
        adt, r = self._tp_wl(Yanit(500, "x"), akt, symbols=self.SEM)
        ap, af = r["steps"].get("activate_prog", {}), r["steps"].get("activation_final", {})
        ok = (r.get("ok") is False and r.get("error") == "activation_unverified"
              and ap.get("outcome") == "failed" and af.get("ok") is None
              and "Sözdizimi hatası satır 3" in str(r.get("message")) and bool(r.get("activation_notice")))
        self.kaydet("P12 textpool: PROG/P gerçek E hatası + son sonda ölçülemedi → activation_unverified (ok:false)",
                    "activation_unverified", f"ok={r.get('ok')} err={r.get('error')} msg={str(r.get('message'))[:80]}", ok)

    def test_P11_textpool_yazilmadiysa_written_bos(self):
        adt, r = self._tp(canli={"symbols": "@MaxLength:5\r\nB99=Eski!"}, symbols=self.SEM, selections=self.SEC)
        adt2, r2 = self._tp(put_kod=406, symbols=self.SEM, selections=self.SEC)
        adt3, r3 = self._tp(symbols=self.SEM, selections=self.SEC)
        ok = (r.get("error") == "would_remove_entries" and r.get("written") == []
              and r2.get("error") == "put_failed" and r2.get("written") == []
              and r3.get("ok") is True and r3.get("written") == ["symbols", "selections"])
        self.kaydet("P11 textpool: yazılmadıysa written=[] (would_remove · PUT hatası); başarıda iki alt",
                    "[] · [] · 2 alt", f"{r.get('written')} · {r2.get('written')} · {r3.get('written')}", ok)


if __name__ == "__main__":
    unittest.main()
