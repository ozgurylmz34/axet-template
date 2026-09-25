# -*- coding: utf-8 -*-
"""Tanı/okuma araçları (2026-09-13): adt_revisions · adt_object_structure · adt_system_info · sap_doctor.

Süreç içi, SAHTE istemci (ağ yok). Örnek XML'ler jeneriktir (ZCA000 demo adları). Kütüphane
uçlarının GERÇEK yanıt biçimi canlı DOĞRULANMADI — testler aracın kütüphane desenleriyle tutarlı
ayrıştırdığını ve durumları ayırdığını kanıtlar, SAP'nin bu biçimi döndürdüğünü değil.
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

from test_new_write_tools import SAHTE_HOST, Oturum, Yanit  # noqa: E402

YAPI_LINKLI = ('<class:abapClass xmlns:class="http://www.sap.com/adt/oo/classes" xmlns:adtcore="http://www.sap.com/adt/core" '
               'adtcore:name="ZCA000_CL_DEMO"><link href="/sap/bc/adt/oo/classes/zca000_cl_demo/source/main/versions" '
               'rel="http://www.sap.com/adt/relations/versions"/></class:abapClass>')
FEED = ('<atom:feed xmlns:atom="http://www.w3.org/2005/Atom" xmlns:adtcore="http://www.sap.com/adt/core">'
        '<atom:entry><atom:title>Sürüm &amp; iki</atom:title><atom:updated>2026-09-02T10:00:00Z</atom:updated>'
        '<atom:author><atom:name>DEVUSER1</atom:name></atom:author>'
        '<atom:content type="text/plain" src="/sap/bc/adt/oo/classes/zca000_cl_demo/source/main/versions/00002/content"/>'
        '<atom:link href="/x" type="application/vnd.sap.adt.transportrequests.v1+xml" adtcore:name="TESTK900002"/></atom:entry>'
        '<atom:entry><atom:title>Sürüm bir</atom:title><atom:updated>2026-09-01T10:00:00Z</atom:updated>'
        '<atom:author><atom:name>DEVUSER2</atom:name></atom:author>'
        '<atom:content type="text/plain" src="/sap/bc/adt/oo/classes/zca000_cl_demo/source/main/versions/00001/content"/>'
        '<atom:link href="/y" adtcore:name="00001"/></atom:entry></atom:feed>')
YAPI_BILESEN = ('<class:abapClass xmlns:class="http://www.sap.com/adt/oo/classes" xmlns:adtcore="http://www.sap.com/adt/core" '
                'adtcore:name="ZCA000_CL_DEMO" adtcore:type="CLAS/OC">'
                '<abapsource:objectStructureElement xmlns:abapsource="http://www.sap.com/adt/abapsource" '
                'adtcore:name="RUN" adtcore:type="CLAS/OM" adtcore:description="Çalıştır"/>'
                '<abapsource:objectStructureElement xmlns:abapsource="http://www.sap.com/adt/abapsource" '
                'adtcore:name="GV_SAYAC" adtcore:type="CLAS/OA"/></class:abapClass>')


# Z132 (2026-09-25) — canlı ölçülen biçim: `atom:` önekli bağlantı, GÖRELİ href; sınıfta ilk bağlantı `includes/definitions`,
# ana kaynak `includes/main/versions`. Bağlantı dışındaki gövde jeneriktir (ölçüm kaydı yalnız bağlantıyı yazıyor).
_REL = 'rel="http://www.sap.com/adt/relations/versions"'
Z132_SINIF = ('<class:abapClass xmlns:class="http://www.sap.com/adt/oo/classes" xmlns:atom="http://www.w3.org/2005/Atom" '
              'xmlns:adtcore="http://www.sap.com/adt/core" adtcore:name="ZCL_ZSD001_REV">'
              f'<class:include><atom:link href="includes/definitions/versions" {_REL} type="application/atom+xml;type=feed"/></class:include>'
              f'<class:include><atom:link href="includes/implementations/versions" {_REL}/></class:include>'
              f'<class:include><atom:link href="includes/main/versions" {_REL}/></class:include></class:abapClass>')
Z132_KAYNAK = ('<abapsource:x xmlns:abapsource="http://www.sap.com/adt/abapsource" xmlns:atom="http://www.w3.org/2005/Atom">'
               f'<atom:link href="source/main/versions" {_REL}/></abapsource:x>')
Z132_TEK_DEF = ('<class:abapClass xmlns:class="http://www.sap.com/adt/oo/classes" xmlns:atom="http://www.w3.org/2005/Atom">'
                f'<atom:link {_REL} href="includes/definitions/versions"/></class:abapClass>')


class SahteTani:
    url = f"http://{SAHTE_HOST}:8000"
    client = "100"
    user = H.KULLANICI
    password = H.PAROLA
    language = "TR"
    timeout_short = 30

    def __init__(self, yonlendir=None):
        self.cagri: list[dict] = []
        self.yonlendir = yonlendir
        self.session = Oturum(self)
        self.yapi = None
        self.bilgi = {}
        self.logon = {"success": True, "status_code": 200, "message": "ok"}
        self.token = "SAHTE-CSRF-7781"

    def _kayit(self, method, url, headers, params, data):
        yol = url[len(self.url):] if url.startswith(self.url) else url
        c = {"method": method, "path": yol, "headers": dict(headers or {}), "params": dict(params or {}), "data": data}
        self.cagri.append(c)
        return self.yonlendir(c)

    def _get_headers(self, accept_type="application/vnd.sap.adt.core.v1+xml", content_type=None):
        return {"Accept": accept_type, "sap-client": self.client}

    def get_object_structure(self, url, version="active"):
        self.cagri.append({"method": "LIB", "path": "get_object_structure", "params": {"url": url, "version": version}})
        if isinstance(self.yapi, Exception):
            raise self.yapi
        return self.yapi

    def get_system_info(self):
        self.cagri.append({"method": "LIB", "path": "get_system_info", "params": {}})
        return dict(self.bilgi)

    def check_logon(self):
        self.cagri.append({"method": "LIB", "path": "check_logon", "params": {}})
        return dict(self.logon)

    def fetch_csrf_token(self, force_refresh=False):
        self.cagri.append({"method": "LIB", "path": "fetch_csrf_token", "params": {"force": force_refresh}})
        if isinstance(self.token, Exception):
            raise self.token
        return self.token


class _Istemci:
    def __init__(self, adt):
        self.adt_client = adt


class TaniAraclari(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="axet_tani_"))
        cls._eski_env = {k: v for k, v in os.environ.items() if k.startswith("ADT_") or k == "AXET_SAP_PROJECT_DIR"}
        for k in list(cls._eski_env):
            os.environ.pop(k, None)
        from sapadt.tools import atom, diag
        cls.atom, cls.diag = atom, diag
        cls._eski_client = atom._get_client
        cls._sayac = 0

    @classmethod
    def tearDownClass(cls):
        cls.atom._get_client = cls._eski_client
        os.environ.pop("AXET_SAP_PROJECT_DIR", None)
        os.environ.update(cls._eski_env)
        shutil.rmtree(cls.root, ignore_errors=True)

    def proje(self, **kw):
        type(self)._sayac += 1
        p = H.make_project(self.root, f"p{self._sayac}", **kw)
        os.environ["AXET_SAP_PROJECT_DIR"] = str(p)
        return p

    def setUp(self):
        self.p = self.proje()

    def kur(self, yonlendir=None):
        adt = SahteTani(yonlendir)
        self.atom._get_client = lambda: _Istemci(adt)
        return adt

    def kaydet(self, ad, beklenen, gercek, ok):
        H.kaydet(f"TANI {ad}", beklenen, str(gercek)[:160], ok)
        self.assertTrue(ok, f"{ad}: {gercek}")

    @staticmethod
    def rev_yonlendir(yapi_durum=200, yapi=YAPI_LINKLI, feed_durum=200, feed=FEED):
        """Z132 canlı ölçümünü taklit eder: obje isteği yalnız `Accept: */*` ile 200 döner, objectstructure/xml → 406;
        akış yalnız `atom+xml` Accept ile döner."""
        def yon(c):
            acc = c["headers"].get("Accept", "")
            if "atom+xml" in acc:
                return Yanit(feed_durum, feed)
            if acc == "*/*":
                return Yanit(yapi_durum, yapi)
            return Yanit(406, "not acceptable")
        return yon

    # ── adt_revisions ────────────────────────────────────────────────────────────────────
    def test_01_revisions_dev(self):
        adt = self.kur(self.rev_yonlendir())
        r = self.diag.adt_revisions("ZCA000_CL_DEMO", "class")
        g = [c for c in adt.cagri if c["method"] == "GET"]
        ok = (r.get("ok") is True and r["count"] == 2 and r["versions_link_found"] is True
              and r["revisions"][0] == {"version": "TESTK900002", "versionTitle": "Sürüm & iki", "author": "DEVUSER1",
                                        "date": "2026-09-02T10:00:00Z",
                                        "uri": "/sap/bc/adt/oo/classes/zca000_cl_demo/source/main/versions/00002/content"}
              and r["revisions"][1]["version"] == "00001" and r["author_masked"] is False
              and len(g) == 2 and g[1]["path"] == "/sap/bc/adt/oo/classes/zca000_cl_demo/source/main/versions")
        self.kaydet("01 revisions: yapı→versions linki→feed, 2 sürüm, DEV'de yazar açık", "ok · 2 · 2 GET", r, ok)

    def test_02_revisions_limit_ve_arguman(self):
        self.kur(self.rev_yonlendir())
        r1 = self.diag.adt_revisions("ZCA000_CL_DEMO", "class", limit=1)
        r2 = self.diag.adt_revisions("ZCA000_CL_DEMO", "class", limit=0).get("error")
        r3 = self.diag.adt_revisions("ZCA000_FM", "func").get("error")
        ok = r1["returned"] == 1 and r1["count"] == 2 and r2 == "invalid_argument" and r3 == "unsupported_type"
        self.kaydet("02 limit=1 · limit=0 · func tipi", "1 · invalid_argument · unsupported_type",
                    f"{r1['returned']} {r2} {r3}", ok)

    def test_03_revisions_durumlari_ayirir(self):
        self.kur(self.rev_yonlendir(yapi=YAPI_BILESEN))
        linksiz = self.diag.adt_revisions("ZCA000_CL_DEMO")
        self.kur(self.rev_yonlendir(yapi_durum=404))
        yok = self.diag.adt_revisions("ZCA000_CL_DEMO").get("error")
        self.kur(self.rev_yonlendir(yapi_durum=500))
        yapi500 = self.diag.adt_revisions("ZCA000_CL_DEMO").get("error")
        self.kur(self.rev_yonlendir(feed_durum=403))
        feed403 = self.diag.adt_revisions("ZCA000_CL_DEMO").get("error")
        ok = (linksiz.get("ok") is True and linksiz["versions_link_found"] is False and "KANITI DEĞİL" in linksiz["notice"]
              and yok == "not_found" and yapi500 == "revisions_unavailable" and feed403 == "revisions_feed_failed")
        self.kaydet("03 link yok (ok, kanıt değil) · 404 · yapı 500 · feed 403 AYRI kodlar",
                    "link:false · not_found · unavailable · feed_failed", f"{yok} {yapi500} {feed403}", ok)

    def test_04_revisions_dev_disi_maske(self):
        self.proje(tier_lines=("ADT_SAP_TIER=QA",))
        self.kur(self.rev_yonlendir())
        m = self.diag.adt_revisions("ZCA000_CL_DEMO")
        a = self.diag.adt_revisions("ZCA000_CL_DEMO", acknowledge_risk=True)
        ok = ({x["author"] for x in m["revisions"]} == {"***"} and m["author_masked"] is True
              and "DEVUSER1" not in json.dumps(m) and a["revisions"][0]["author"] == "DEVUSER1")
        self.kaydet("04 tier QA → yazar maskeli (engellemez); acknowledge_risk → açık", "*** · DEVUSER1",
                    [x["author"] for x in m["revisions"]], ok)

    # ── adt_object_structure ─────────────────────────────────────────────────────────────
    def test_05_structure(self):
        adt = self.kur()
        adt.yapi = YAPI_BILESEN
        r = self.diag.adt_object_structure("ZCA000_CL_DEMO", "class")
        adlar = [b["name"] for b in r.get("components", [])]
        ok = (r.get("ok") is True and r["exists"] is True and adlar == ["RUN", "GV_SAYAC"]
              and r["components"][0]["description"] == "Çalıştır" and r["components"][0]["type"] == "CLAS/OM")
        self.kaydet("05 structure: bileşenler (objenin kendisi hariç)", "RUN, GV_SAYAC", adlar, ok)

    def test_06_structure_404_bozuk_surum(self):
        from sap_adt_lib import SAPADTError, SAPObjectNotFoundError  # type: ignore
        adt = self.kur()
        adt.yapi = SAPObjectNotFoundError("yok", status_code=404, endpoint="/x")
        yok = self.diag.adt_object_structure("ZCA000_CL_YOK")
        adt.yapi = "<bozuk"
        bozuk = self.diag.adt_object_structure("ZCA000_CL_DEMO").get("error")
        adt.yapi = SAPADTError(f"sunucu hatası {SAHTE_HOST}", status_code=500, endpoint="/x")
        e500 = self.diag.adt_object_structure("ZCA000_CL_DEMO")
        surum = self.diag.adt_object_structure("ZCA000_CL_DEMO", version="x").get("error")
        ok = (yok.get("ok") is True and yok["exists"] is False and bozuk == "structure_unparseable"
              and e500.get("ok") is False and SAHTE_HOST not in json.dumps(e500) and surum == "invalid_argument")
        self.kaydet("06 404 → exists:false · bozuk XML · 500 (host maskeli) · version geçersiz",
                    "false · unparseable · ok:false · invalid", f"{bozuk} {e500.get('error')} {surum}", ok)

    # ── adt_system_info ──────────────────────────────────────────────────────────────────
    def test_07_system_info_allowlist(self):
        adt = self.kur()
        adt.bilgi = {"connection_url": adt.url, "client": "321", "user": H.KULLANICI, "language": "TR",
                     "system_id": "QZ9", "available_services": [{"title": "Data Preview", "href": "/sap/bc/adt/datapreview"}],
                     "service_count": 1}
        r = self.diag.adt_system_info()
        dump = json.dumps(r, ensure_ascii=False)
        ok = (r.get("ok") is True and r["service_count"] == 1 and r["logon_language"] == "TR"
              and all(s not in dump for s in (SAHTE_HOST, "321", H.KULLANICI, "QZ9", H.PAROLA))
              and set(r["withheld_fields"]) == {"connection_url", "client", "user", "system_id"})
        self.kaydet("07 system_info: yalnız servis kataloğu; URL/client/kullanıcı/SID çıktıda YOK", "ok · 0 sızıntı", r, ok)
        adt.bilgi = {"connection_url": adt.url, "language": "TR"}
        self.assertEqual(self.diag.adt_system_info().get("error"), "discovery_unavailable")

    # ── sap_doctor ───────────────────────────────────────────────────────────────────────
    @staticmethod
    def durumlar(r):
        return {k["id"]: k["status"] for k in r["checks"]}

    def test_08_doctor_basari(self):
        adt = self.kur()
        r = self.diag.sap_doctor()
        d = self.durumlar(r)
        dump = json.dumps(r, ensure_ascii=False)
        ok = (r["ok"] is True and r["verdict"] == "WARN" and d["logon"] == "PASS" and d["csrf"] == "PASS"
              and d["tls"] == "WARN" and d["tier"] == "PASS" and d["conn_keys"] == "PASS" and len(r["not_checked"]) >= 8
              and all(s not in dump for s in (H.PAROLA, H.KULLANICI, "127.0.0.1", SAHTE_HOST, "SAHTE-CSRF-7781"))
              and [c["path"] for c in adt.cagri] == ["check_logon", "fetch_csrf_token"])
        self.kaydet("08 doctor: yerel PASS + canlı logon/CSRF PASS, TLS WARN, değer basılmadı, kapsam beyanı",
                    "WARN · ok · sızıntı yok", d, ok)

    def test_09_doctor_kimlik_reddi(self):
        adt = self.kur()
        adt.logon = {"success": False, "status_code": 401, "message": f"401 {adt.url}"}
        r = self.diag.sap_doctor()
        d = self.durumlar(r)
        ok = (r["ok"] is False and r["error"] == "doctor_fail" and d["logon"] == "FAIL" and d["csrf"] == "SKIP"
              and "fetch_csrf_token" not in [c["path"] for c in adt.cagri])
        self.kaydet("09 doctor: 401 → logon FAIL, CSRF denenmedi, doctor_fail", "FAIL · SKIP", d, ok)

    def test_10_doctor_ulasilamaz_host_maskeli(self):
        adt = self.kur()
        adt.logon = {"success": False, "status_code": None, "message": f"Connection refused {adt.url}"}
        r = self.diag.sap_doctor()
        ok = self.durumlar(r)["logon"] == "FAIL" and SAHTE_HOST not in json.dumps(r, ensure_ascii=False)
        self.kaydet("10 doctor: ulaşılamaz → FAIL, mesajdaki host maskeli", "FAIL · host yok", self.durumlar(r), ok)

    def test_11_doctor_yer_tutucu_canli_atlanir(self):
        self.proje(extra_lines=("ADT_SAP_CLIENT=<CLIENT>",))
        cagrildi = []
        self.atom._get_client = lambda: cagrildi.append(1)
        r = self.diag.sap_doctor()
        d = self.durumlar(r)
        ok = d["conn_keys"] == "FAIL" and d["logon"] == "SKIP" and d["csrf"] == "SKIP" and not cagrildi \
            and "<CLIENT>" not in json.dumps(r)
        self.kaydet("11 doctor: <...> yer tutucu → conn_keys FAIL, SAP'ye gidilmedi", "FAIL · SKIP · 0 istemci", d, ok)

    def test_12_doctor_proje_yok_ve_tier(self):
        self.proje(sap_project=None, tier_lines=())
        cagrildi = []
        self.atom._get_client = lambda: cagrildi.append(1)
        r = self.diag.sap_doctor()
        d = self.durumlar(r)
        ok = (d["sap_project"] == "FAIL" and d["profile"] == "FAIL" and d["tier"] == "FAIL"
              and d["logon"] == "SKIP" and not cagrildi and r["verdict"] == "FAIL")
        self.kaydet("12 doctor: sap-project.json yok + tier yok → FAIL, canlı SKIP", "FAIL · SKIP", d, ok)

    def test_13_doctor_live_false_ve_env_ezme(self):
        self.kur()
        r = self.diag.sap_doctor(live=False)
        d1 = self.durumlar(r)
        os.environ["ADT_SAP_CLIENT"] = "999"
        try:
            d2 = self.durumlar(self.diag.sap_doctor(live=True))
        finally:
            os.environ.pop("ADT_SAP_CLIENT", None)
        ok = (d1["logon"] == "SKIP" and r["ok"] is True and d2["env_override"] == "FAIL" and d2["logon"] == "SKIP")
        self.kaydet("13 doctor: live=false SKIP · env ADT_SAP_CLIENT ezmesi FAIL → canlı SKIP", "SKIP · FAIL",
                    f"{d1['logon']} {d2['env_override']} {d2['logon']}", ok)


    # ── Z132 (2026-09-25): canlı ölçülen gövde biçimleri — `atom:link`, GÖRELİ href, sınıfta çoklu bağlantı ──
    def test_14_revisions_z132_sinif_atom_link_goreli_ana_kaynak(self):
        adt = self.kur(self.rev_yonlendir(yapi=Z132_SINIF))
        r = self.diag.adt_revisions("ZCL_ZSD001_REV", "class")
        g = [c for c in adt.cagri if c["method"] == "GET"]
        ok = (r.get("ok") is True and r["versions_link_found"] is True and r["count"] == 2
              and r["versions_link"] == "/sap/bc/adt/oo/classes/zcl_zsd001_rev/includes/main/versions"
              and r["versions_link_count"] == 3 and len(g) == 2
              and g[0]["path"] == "/sap/bc/adt/oo/classes/zcl_zsd001_rev" and g[0]["headers"]["Accept"] == "*/*"
              and g[1]["path"] == "/sap/bc/adt/oo/classes/zcl_zsd001_rev/includes/main/versions"
              and g[1]["headers"]["Accept"] == "application/atom+xml;type=feed")
        self.kaydet("14 Z132 sınıf: Accept */* · atom:link · göreli href · ilk değil includes/main seçilir",
                    "ok · 2 · includes/main", [(c["path"], c["headers"].get("Accept")) for c in g], ok)

    def test_15_revisions_z132_include_ve_arayuz_source_main(self):
        sonuc = {}
        for tip, ad, kok in (("include", "ZSD001_I_REV", "/sap/bc/adt/programs/includes/zsd001_i_rev"),
                             ("interface", "ZIF_ZSD001_REV", "/sap/bc/adt/oo/interfaces/zif_zsd001_rev")):
            adt = self.kur(self.rev_yonlendir(yapi=Z132_KAYNAK))
            r = self.diag.adt_revisions(ad, tip)
            g = [c["path"] for c in adt.cagri if c["method"] == "GET"]
            sonuc[tip] = (r.get("ok"), r.get("count"), g == [kok, kok + "/source/main/versions"])
        ok = sonuc == {"include": (True, 2, True), "interface": (True, 2, True)}
        self.kaydet("15 Z132 include + arayüz: href source/main/versions obje URL'ine göre çözülür", "ok · 2 · yol doğru",
                    sonuc, ok)

    def test_16_revisions_z132_406_acik_hata_ve_tek_baglanti(self):
        adt = self.kur(self.rev_yonlendir(yapi_durum=406, yapi="not acceptable"))
        r406 = self.diag.adt_revisions("ZCL_ZSD001_REV")
        feed_yok = [c for c in adt.cagri if "atom+xml" in c["headers"].get("Accept", "")] == []
        self.kur(self.rev_yonlendir(yapi=Z132_TEK_DEF))
        tek = self.diag.adt_revisions("ZCL_ZSD001_REV")
        ok = (r406.get("ok") is False and r406["error"] == "revisions_unavailable" and r406["http"]["structure"] == 406
              and "revisions" not in r406 and feed_yok
              and tek.get("ok") is True
              and tek["versions_link"] == "/sap/bc/adt/oo/classes/zcl_zsd001_rev/includes/definitions/versions")
        self.kaydet("16 Z132 obje 406 → revisions_unavailable (boş liste DEĞİL) · main yoksa ilk bağlantı",
                    "unavailable · definitions", (r406.get("error"), tek.get("versions_link")), ok)


if __name__ == "__main__":
    unittest.main()
