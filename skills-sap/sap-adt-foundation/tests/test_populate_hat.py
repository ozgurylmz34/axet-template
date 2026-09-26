# -*- coding: utf-8 -*-
"""Toplu yazıcı — GERÇEK hat: `populate.main` → `sap_adt_cli.on_kontrol/calistir` → `gate` → araç → reviewer.

SAP sahtedir (ağ yok): istemci ya sayaçlı "çağrılırsa patla" ya da çağrı kaydeden sahte ADT oturumudur.
Opt-in dosyası repoya YAZILMAZ: `gate.optin_file` test süresince geçici dizine yönlendirilir.
Son sınıf (`AltSurecCLI`) giriş script'ini alt süreçte, kopya AXET_HOME ile koşar (`_helpers.build_home`).

Kapsam beyanı: kapı reddi senaryoları ad (A), transport (C), dil, tier, bayrak, opt-in, kapsam, gerekçe ve profil
kodlarını kapsar. Paket yasağı (ADR_0005_C paket tipi) populate türlerinden erişilemez (tür sabit), `skip_reviewer`
populate'te hiç verilmez, std-DML taraması yalnız ABAP kaynağına bakar — bu üçü burada ÖLÇÜLMEDİ.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

import _helpers as H

sys.dont_write_bytecode = True
for _p in (H.SCRIPTS, H.SCRIPTS / "sapadt" / "lib"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from test_new_write_tools import TR, SahteADT, SahteIstemci, Yanit  # noqa: E402
from test_msgclass_domain import MsagADT, _msag_xml, _sap_put_uygula  # noqa: E402

S1 = ["--sap-write", "--scope", "S1", "--reason", "Toplu yazıcı hat testi gerekçesi"]
PKG = "ZAXET_PKG"
DOMAIN_CSV = ("name,datatype,length,decimals,description,fixed_values\n"
              "ZAXET_D_DURUM,CHAR,1,0,Durum alanı,A=Açık;K=Kapalı\n"
              "ZAXET_D_MIKTAR,QUAN,15,3,Miktar alanı,\n")


def _ddic_yok(object_type, name):
    """`sap_client.get_ddic_object` taklidi — obje YOK: istisnayı yutar, sebebi stdout'a `[ERROR] [404] …` basar.
    v0.5.1 (Z51 ⓐ): domain/DTEL ön kontrolü artık `adt_get` → `get_ddic_object` üzerinden üç değerli ölçer; bu yöntemi
    taşımayan sahte istemci "ÖLÇÜLEMEDİ" (`exists_unmeasured`) üretir ve yaratma yoluna hiç girilmez."""
    print("[ERROR] [404] Object not found: %s %s" % (object_type, name))
    return None


class _Sayac:
    def __init__(self):
        self.n = 0

    def __call__(self):
        self.n += 1
        raise AssertionError("SAP istemcisi çağrıldı")


class _Ortak(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="axet_populate_hat_"))
        cls._eski_env = {"AXET_SAP_PROJECT_DIR": os.environ.get("AXET_SAP_PROJECT_DIR")}
        for k in [k for k in os.environ if k.upper().startswith("ADT_")]:
            cls._eski_env.setdefault(k, os.environ.get(k))
            os.environ.pop(k, None)
        from sapadt import gate, populate
        from sapadt.tools import atom, composite
        import sap_adt_cli
        cls.gate, cls.P, cls.atom, cls.composite, cls.cli = gate, populate, atom, composite, sap_adt_cli
        cls._eski_client = atom._get_client
        cls._eski_optin = gate.optin_file
        cls.optin = cls.root / "home" / "config" / "sap-write.local"
        cls.optin.parent.mkdir(parents=True)
        cls.optin.write_text("test opt-in\n", encoding="utf-8")
        gate.optin_file = lambda axet_home=None: cls.optin
        cls._sayac_ad = 0

    @classmethod
    def tearDownClass(cls):
        cls.atom._get_client = cls._eski_client
        cls.gate.optin_file = cls._eski_optin
        for k, v in cls._eski_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(cls.root, ignore_errors=True)

    def proje(self, **kw):
        type(self)._sayac_ad += 1
        return H.make_project(self.root / "projeler", f"p{self._sayac_ad}", **kw)

    def dosya(self, metin, ad="girdi.csv"):
        type(self)._sayac_ad += 1
        d = self.root / f"g{self._sayac_ad}"
        d.mkdir()
        (d / ad).write_text(metin, encoding="utf-8")
        return str(d / ad)

    def main(self, argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
            kod = self.P.main(argv)
        return json.loads(buf.getvalue()), kod

    def kaydet(self, ad, beklenen, gercek, ok):
        H.kaydet(f"POPULATE-HAT {ad}", beklenen, str(gercek)[:160], ok)
        self.assertTrue(ok, f"{ad}: {gercek}")

    @staticmethod
    def log_satirlari(p):
        yol = Path(p) / ".axet-code" / "sap-write-log.jsonl"
        return [json.loads(s) for s in yol.read_text(encoding="utf-8").splitlines()] if yol.is_file() else []


class KapiReddi(_Ortak):
    """Her ADR 0005 / kapı kuralı, toplu girdide satır bazında: ön geçiş reddi → 0 istemci çağrısı."""

    def _red(self, ad, argv_ek, kod_beklenen, *, proje_kw=None, tur="domain", csv_metin=DOMAIN_CSV, bayrak=S1,
             transport=True, ek=()):
        p = self.proje(**(proje_kw or {}))
        sayac = _Sayac()
        self.atom._get_client = sayac
        argv = [tur, "--csv", self.dosya(csv_metin), "--package", PKG, "--project-dir", str(p), *bayrak, *ek]
        if transport:
            argv += ["--transport", TR]
        d, kod = self.main(argv + list(argv_ek))
        red = d["gate"]["prepass"]["rejections"]
        loglu = [s["result"] for s in self.log_satirlari(p)]
        ok = (kod == 2 and d["error"]["code"] == "prepass_gate_rejected" and red and red[0]["code"] == kod_beklenen
              and sayac.n == 0 and kod_beklenen in loglu)
        self.kaydet(f"K {ad} → ön geçiş 2 · {kod_beklenen} · 0 istemci · red logu", f"2 · {kod_beklenen} · 0",
                    f"{kod} · {red[0]['code'] if red else None} · istemci={sayac.n} · log={loglu[:3]}", ok)
        return d

    def test_K1_ad_standart(self):
        self._red("ad Z/Y değil (satır 3)", [], "ADR_0005_A",
                  csv_metin=DOMAIN_CSV + "MATNR_KOPYA,CHAR,18,0,Malzeme,\n")

    def test_K2_transport_yok(self):
        self._red("transport verilmedi", [], "ADR_0005_C", transport=False)

    def test_K3_dil_uyusmaz(self):
        self._red("bağlantı dili EN ≠ master TR", [], "language_mismatch", proje_kw={"language": "EN"})

    def test_K4_tier_qa(self):
        self._red("tier QA", [], "tier_not_writable", proje_kw={"tier_lines": ("ADT_SAP_TIER=QA",)})

    def test_K5_bayrak_kapsam_gerekce(self):
        self._red("--sap-write yok", [], "write_flag_missing", bayrak=["--scope", "S1", "--reason", "Toplu yazıcı hat testi"])
        self._red("--scope yok", [], "scope_missing", bayrak=["--sap-write"])
        self._red("gerekçe kısa", [], "reason_missing", bayrak=["--sap-write", "--scope", "S1", "--reason", "kısa"])

    def test_K6_optin_yok(self):
        eski = self.gate.optin_file
        self.gate.optin_file = lambda axet_home=None: self.root / "yok" / "sap-write.local"
        try:
            self._red("makinede opt-in yok", [], "write_not_optin_global")
        finally:
            self.gate.optin_file = eski

    def test_K7_force_delete_kapida(self):
        d = self._red("force: adt_delete tier QA'da", ["--force-recreate", "--only", "ZAXET_D_DURUM"], "tier_not_writable",
                      proje_kw={"tier_lines": ("ADT_SAP_TIER=QA",)})
        adimlar = [r["tool"] for r in d["gate"]["prepass"]["rejections"]]
        self.kaydet("K7b ön geçiş reddi listesinde adt_delete var", "adt_delete ∈ red", adimlar, "adt_delete" in adimlar)

    def test_K8_profil(self):
        self._red("msag s4_public profilinde", [], "tool_not_available_for_profile", tur="msag",
                  csv_metin="msgno,msgtext\n001,Kayıt bulunamadı\n",
                  proje_kw={"sap_project": {"sap_profile": "s4_public", "master_language": "TR"}},
                  ek=["--name", "ZAXET_MSG", "--description", "Mesajlar"])


class ReviewerVeMesaj(_Ortak):
    def test_R1_dtel_reviewer_gercekten_kosar(self):
        p = self.proje()
        os.environ["AXET_SAP_PROJECT_DIR"] = str(p)
        tmp = Path(tempfile.mkdtemp(dir=self.root))
        ham = {"name": "ZAXET_E_DURUM", "type_kind": "domain", "type_name": "", "description": "Durum",
               "short": "Durum", "medium": "Durum bilgisi", "long": "Belge durum bilgisi", "heading": "Belge durumu"}
        h = {"satir": 2, "ad": "ZAXET_E_DURUM", "domain_name": "", "description": "Durum", "short": "Durum",
             "medium": "Durum bilgisi", "long": "Belge durum bilgisi", "heading": "Belge durumu", "_ham": ham}
        bayrak = dict(sap_write=True, scope="S1", reason="Toplu yazıcı hat testi gerekçesi")
        sayac = _Sayac()
        self.atom._get_client = sayac
        tool, args = self.P._Plan("dtel", h, PKG, TR, tmp, False).cagrilar["yarat"]
        payload, kod = self.cli.calistir(tool, args, p, tls_uyarisi=False, **bayrak)
        self.kaydet("R1 dtel: plan artefaktı → dtel_creation reviewer BLOCKER (R5 type_name boş; araç guard'ı bunu "
                    "görmez) → 0 istemci", "2 · reviewer_blocker · BLOCKER · 0",
                    f"{kod} · {(payload['error'] or {}).get('code')} · {payload['gate']['review']} · {sayac.n}",
                    kod == 2 and payload["error"]["code"] == "reviewer_blocker"
                    and str(payload["gate"]["review"]).startswith("BLOCKER") and sayac.n == 0)
        h2 = {**h, "domain_name": "ZAXET_D_DURUM", "_ham": {**ham, "type_name": "ZAXET_D_DURUM"}}
        tool, args = self.P._Plan("dtel", h2, PKG, TR, tmp, False).cagrilar["yarat"]
        payload, kod = self.cli.calistir(tool, args, p, tls_uyarisi=False, **bayrak)
        self.kaydet("R1b KONTROL: temiz artefakt → reviewer geçer → istemciye ulaşılır (sayaç 1)", "istemci=1",
                    f"{kod} · {(payload['error'] or {}).get('code')} · istemci={sayac.n}", sayac.n == 1)

    def _msag_hat(self, msgs):
        durum = {"msgs": list(msgs), "ml": "TR", "paket": True, "get": 200}

        def yon(c):
            if c["method"] == "GET" and c["path"] == "/sap/bc/adt/messageclass/zaxet_msg":
                return Yanit(200, _msag_xml(durum))
            if c["method"] == "POST" and c["params"].get("_action") == "LOCK":
                return Yanit(200, "<asx:abap><DATA><LOCK_HANDLE>HX9</LOCK_HANDLE></DATA></asx:abap>")
            if c["method"] == "PUT":
                # Z118ⓔ: ölçülmüş SAP semantiği (tek kaynak `test_msgclass_domain._sap_put_uygula`) — gövdede olmayana
                # DOKUNULMAZ, silme yalnız `<mc:deletedmessages>`. Eski sahte tam listeyle DEĞİŞTİRİYORDU (R2c kalibrasyonu).
                durum["msgs"] = _sap_put_uygula(durum["msgs"], c["data"])
                return Yanit(200, "")
            if c["method"] == "POST" and c["params"].get("_action") == "UNLOCK":
                return Yanit(200, "")
            return Yanit(500, "beklenmedik")
        adt = MsagADT(yon)

        class Ist:
            adt_client = adt
        self.atom._get_client = lambda: Ist()
        return adt, durum

    def test_R2_msag_ustune_yazma_bayraksiz_degismez(self):
        p = self.proje()
        csv_m = self.dosya("msgno,msgtext\n001,Yeni metin\n")
        adt, durum = self._msag_hat([("001", "Eski metin", False, False), ("002", "Kalır", False, False)])
        argv = ["msag", "--name", "ZAXET_MSG", "--description", "Mesajlar", "--csv", csv_m, "--package", PKG,
                "--transport", TR, "--project-dir", str(p), *S1]
        d, kod = self.main(argv)
        put = [c for c in adt.cagri if c["method"] == "PUT" or c["params"].get("_action")]
        ok = (kod == 1 and d["result"]["rows"][0]["status"] == "hata"
              and "msgclass_overwrite_not_allowed" in d["result"]["rows"][0]["message"] and not put
              and durum["msgs"][0][1] == "Eski metin")
        self.kaydet("R2 msag: bayraksız mevcut 001 metni DEĞİŞMEZ (kilit/PUT yok, canlı liste aynı)",
                    "1 · overwrite_not_allowed · 0 PUT", f"{kod} · {d['result']['rows'][0].get('message', '')[:60]} · "
                    f"PUT/LOCK={len(put)} · {durum['msgs'][0]}", ok)
        d, kod = self.main(argv + ["--allow-overwrite"])
        puts = [c for c in adt.cagri if c["method"] == "PUT"]
        ok = (kod == 0 and d["result"]["rows"][0]["status"] == "yazildi" and len(puts) == 1
              and [m[:2] for m in durum["msgs"]] == [("001", "Yeni metin"), ("002", "Kalır")])
        self.kaydet("R2b KONTROL --allow-overwrite → tek PUT, 001 değişti, 002 korundu", "0 · 1 PUT",
                    f"{kod} · PUT={len(puts)} · {durum['msgs']}", ok)

    def test_R2c_msag_sahte_put_semantigi_olculmus_davranis(self):
        """Z118ⓔ — hat sahtesinin KALİBRASYONU: SAP'nin ölçülmüş MSAG PUT davranışı (kaynak çekirdek
        `playbook/adt-message-class.md` §27.5, s4_private 2025): tam PUT gövdesinden ÇIKARILAN mesaj SİLİNMEZ (200, no-op;
        229→229); silme yalnız `<mc:deletedmessages>` ile (229→228). Eski sahte PUT'u tam liste DEĞİŞTİRME sayıyordu —
        o sahteyle "listeden çıkararak silen" bir araç bu hatta yeşil görünürdü."""
        from sapadt.tools import msgclass as mc
        bas = [("001", "Bir", False, False), ("002", "İki", False, False), ("003", "Üç", False, False)]
        yalniz_001 = [{"no": "001", "text": "Bir", "selfexplanatory": False, "documented": False}]
        yol = "/sap/bc/adt/messageclass/zaxet_msg"
        adt, durum = self._msag_hat(bas)
        adt.yonlendir({"method": "PUT", "path": yol, "params": {}, "headers": {},
                       "data": mc._govde("ZAXET_MSG", "Açıklama", "TR", "U", PKG, yalniz_001)})
        self.kaydet("R2c sahte: gövdeden ÇIKARILAN 002/003 silinmez (ölçülmüş no-op)", "001,002,003",
                    [m[0] for m in durum["msgs"]], [m[0] for m in durum["msgs"]] == ["001", "002", "003"])
        adt, durum = self._msag_hat(bas)
        adt.yonlendir({"method": "PUT", "path": yol, "params": {}, "headers": {},
                       "data": mc._govde("ZAXET_MSG", "Açıklama", "TR", "U", PKG, yalniz_001, ["002"])})
        self.kaydet("R2c sahte KONTROL: <mc:deletedmessages 002> → yalnız 002 gider", "001,003",
                    [m[0] for m in durum["msgs"]], [m[0] for m in durum["msgs"]] == ["001", "003"])


class EnquSondasi(_Ortak):
    """adt_get(enqu) — salt-GET üç değerli varlık sondası (kullanıcı onayı 2026-09-14)."""

    def _get(self, cevap, include_source=False):
        def yon(c):
            if isinstance(cevap, Exception):
                return cevap
            return cevap
        adt = SahteADT(yon)
        self.atom._get_client = lambda: SahteIstemci(adt)
        os.environ["AXET_SAP_PROJECT_DIR"] = str(self.proje())
        return self.atom.adt_get("EZAXET_BELGE", "enqu", include_source), adt

    def test_E1_200_var(self):
        r, adt = self._get(Yanit(200, '<enqu:lockobject adtcore:masterLanguage="TR"/>'))
        self.kaydet("E1 enqu GET 200 → ok · exists:true · tek GET, POST yok", "True · 1 GET",
                    f"{r.get('ok')} · {r.get('exists')} · {[(c['method'], c['path']) for c in adt.cagri]}",
                    r.get("ok") is True and r.get("exists") is True
                    and [(c["method"], c["path"]) for c in adt.cagri] == [("GET", "/sap/bc/adt/ddic/lockobjects/sources/ezaxet_belge")])

    def test_E2_404_yok(self):
        r, adt = self._get(Yanit(404, ""))
        self.kaydet("E2 enqu GET 404 → ok · exists:false", "True · False",
                    f"{r.get('ok')} · {r.get('exists')}", r.get("ok") is True and r.get("exists") is False
                    and len(adt.cagri) == 1)

    def test_E3_diger_olculemedi(self):
        for ad, cevap in (("500", Yanit(500, "hata")), ("403", Yanit(403, "")), ("istisna", ConnectionError("koptu"))):
            r, adt = self._get(cevap)
            self.kaydet(f"E3 enqu {ad} → ok:false, exists YOK (ölçülemedi ≠ yok)", "False · exists yok",
                        f"{r.get('ok')} · {r.get('error')} · exists={'exists' in r}",
                        r.get("ok") is False and "exists" not in r and self.cli._sonuc_hatasi(r)[0] == 1)

    def test_E4_kaynak_istegi_desteklenmez(self):
        r, adt = self._get(Yanit(200, ""), include_source=True)
        self.kaydet("E4 enqu include_source=true → unsupported_type, AĞ YOK, CLI çıkış 3", "unsupported_type · 0 · 3",
                    f"{r.get('error')} · {len(adt.cagri)} · {self.cli._sonuc_hatasi(r)[0]}",
                    r.get("error") == "unsupported_type" and not adt.cagri and self.cli._sonuc_hatasi(r)[0] == 3)

    def test_E5_populate_enqu_hat(self):
        csv_e = self.dosya("name,description,primary_table,lock_mode,allow_rfc,field_names\n"
                           "EZAXET_BELGE,Belge kilidi,ZAXET_T_BELGE,E,false,MANDT;BELGE_NO\n")
        for ad, get_kodu, beklenen in (("ölçülemedi (500)", 500, "hata"), ("var (200)", 200, "atlandi")):
            p = self.proje()
            adt = SahteADT(lambda c, k=get_kodu: Yanit(k, "") if c["method"] == "GET" else Yanit(201, ""))
            self.atom._get_client = lambda a=adt: SahteIstemci(a)
            d, kod = self.main(["enqu", "--csv", csv_e, "--package", PKG, "--transport", TR, "--project-dir", str(p), *S1])
            postlar = [c for c in adt.cagri if c["method"] != "GET"]
            self.kaydet(f"E5 populate enqu sonda {ad} → {beklenen}, SAP'ye 0 POST", f"{beklenen} · 0 POST",
                        f"{d['result']['rows'][0]['status']} · POST={len(postlar)} · {[c['method'] for c in adt.cagri]}",
                        d["result"]["rows"][0]["status"] == beklenen and not postlar)
        p = self.proje()
        durum = {"yaratildi": False}

        def yon(c):
            if c["method"] == "GET" and c["path"].startswith("/sap/bc/adt/ddic/lockobjects/sources/"):
                return Yanit(200 if durum["yaratildi"] else 404, '<enqu:lockobject adtcore:masterLanguage="TR"/>')
            if c["method"] == "POST" and c["path"] == "/sap/bc/adt/ddic/lockobjects/sources":
                durum["yaratildi"] = True
                return Yanit(201, "")
            return Yanit(500, "beklenmedik")
        adt = SahteADT(yon)
        self.atom._get_client = lambda: SahteIstemci(adt)
        d, kod = self.main(["enqu", "--csv", csv_e, "--package", PKG, "--transport", TR, "--project-dir", str(p), *S1])
        kabuk = [c for c in adt.cagri if c["method"] == "POST" and c["path"] == "/sap/bc/adt/ddic/lockobjects/sources"]
        araclar = [s["tool"] for s in d["result"]["rows"][0]["steps"]]
        self.kaydet("E5c populate enqu yok (404) → tek kabuk POST'u + adt_activate adımı", "1 POST · get,shell,activate",
                    f"POST={len(kabuk)} · {araclar}",
                    len(kabuk) == 1 and araclar == ["adt_get", "adt_post_shell", "adt_activate"])


class DomainTipBilgisi(_Ortak):
    """lib `_get_domain_typeinfo` fail-closed (lider kararı 2026-09-14): 404 ≠ ölçülemedi, ikisinde de POST yok."""

    DOMA_XML = ("<doma:domain><doma:typeInformation><doma:datatype>CHAR</doma:datatype><doma:length>000010</doma:length>"
                "<doma:decimals>000000</doma:decimals></doma:typeInformation></doma:domain>")

    def _lib(self, get_cevap):
        from sap_adt_lib import SAPADTClient

        class Oturum:
            def __init__(self):
                self.gets, self.posts = [], []

            def get(self, url, headers=None, params=None, timeout=None):
                self.gets.append(url)
                if isinstance(get_cevap, Exception):
                    raise get_cevap
                return get_cevap

            def post(self, url, headers=None, data=None, params=None, timeout=None):
                self.posts.append((url, data))
                return Yanit(201, "", {"Location": "/sap/bc/adt/ddic/dataelements/zaxet_e_x"})
        c = SAPADTClient.__new__(SAPADTClient)
        c.url, c.client, c.language, c.user, c.csrf_token, c.timeout_default = "http://127.0.0.1:9", "100", "TR", H.KULLANICI, "tok", 5
        c._get_headers = lambda *a, **k: {}
        c._retry_request = lambda fn, desc: fn()
        c.session = Oturum()
        return c

    def _yarat(self, c):
        from sap_adt_lib import DomainTipBilgisiHatasi
        try:
            return c.create_dataelement("ZAXET_E_X", "ZAXET_D_YOK", "Durum", PKG, "Durum", "Durum bilgisi",
                                        "Belge durum", "Belge durumu", TR), None
        except DomainTipBilgisiHatasi as exc:
            return None, exc

    def test_L1_404_bulunamadi(self):
        from sap_adt_lib import DomainBulunamadi
        c = self._lib(Yanit(404, ""))
        r, exc = self._yarat(c)
        m = str(exc)
        self.kaydet("L1 domain GET 404 → DomainBulunamadi 'domain bulunamadı: <AD>', ÖLÇÜLEMEDİ DEĞİL, POST yok",
                    "DomainBulunamadi · 0 POST", f"{type(exc).__name__} · {m[:90]} · POST={len(c.session.posts)}",
                    isinstance(exc, DomainBulunamadi) and "domain bulunamadı: ZAXET_D_YOK" in m
                    and "ÖLÇÜLEMEDİ" not in m and not c.session.posts)

    def test_L2_olculemedi_durumlari(self):
        from sap_adt_lib import DomainBulunamadi, DomainTipBilgisiOlculemedi
        xml_ondaliksiz = self.DOMA_XML.replace("<doma:decimals>000000</doma:decimals>", "")
        for ad, cevap, parca in (("HTTP 500", Yanit(500, "hata"), "HTTP 500"),
                                 ("istisna", ConnectionError("koptu"), "okuma istisnası ConnectionError"),
                                 ("decimals alanı yok", Yanit(200, xml_ondaliksiz), "yanıtta alan yok: decimals"),
                                 ("length sayı değil", Yanit(200, self.DOMA_XML.replace("000010", "on")), "sayı değil")):
            c = self._lib(cevap)
            r, exc = self._yarat(c)
            m = str(exc)
            self.kaydet(f"L2 domain {ad} → DomainTipBilgisiOlculemedi 'ÖLÇÜLEMEDİ', bulunamadı DEĞİL, POST yok",
                        "Olculemedi · 0 POST", f"{type(exc).__name__} · {m[:90]} · POST={len(c.session.posts)}",
                        isinstance(exc, DomainTipBilgisiOlculemedi) and not isinstance(exc, DomainBulunamadi)
                        and "ÖLÇÜLEMEDİ" in m and parca in m and "bulunamadı" not in m and not c.session.posts)

    def test_L3_kontrol_tam_yanit_post_gider(self):
        c = self._lib(Yanit(200, self.DOMA_XML))
        r, exc = self._yarat(c)
        govde = c.session.posts[0][1].decode("utf-8") if c.session.posts else ""
        self.kaydet("L3 KONTROL domain 200 tam → tek POST, tip CHAR/10/0 domain'den", "1 POST · CHAR/10/0",
                    f"{exc} · POST={len(c.session.posts)}",
                    exc is None and r.get("success") is True and len(c.session.posts) == 1
                    and "<dtel:dataType>CHAR</dtel:dataType>" in govde and "<dtel:dataTypeLength>10<" in govde
                    and "<dtel:dataTypeDecimals>0<" in govde)

    def test_L4_arac_yapilandirilmis_hata(self):
        from sap_client import SAPClient
        os.environ["AXET_SAP_PROJECT_DIR"] = str(self.proje())
        for ad, cevap, parca in (("404", Yanit(404, ""), "domain bulunamadı: ZAXET_D_YOK"),
                                 ("503", Yanit(503, ""), "ÖLÇÜLEMEDİ")):
            lib = self._lib(cevap)
            ist = types.SimpleNamespace(adt_client=lib, get_object_metadata=lambda name, object_type=None: None,
                                        get_ddic_object=_ddic_yok)
            ist.create_dataelement = types.MethodType(SAPClient.create_dataelement, ist)
            self.atom._get_client = lambda i=ist: i
            with contextlib.redirect_stdout(io.StringIO()):
                r = self.composite.adt_dtel_create("ZAXET_E_X", "ZAXET_D_YOK", "Durum", PKG, TR, "Durum", "Durum bilgisi",
                                                   "Belge durum", "Belge durumu")
            cr = (r.get("steps") or {}).get("create") or {}
            self.kaydet(f"L4 adt_dtel_create domain {ad} → ok:false · steps.create validation_error + mesaj · POST yok",
                        f"validation_error · {parca}", f"{r.get('ok')} · {cr.get('error')} · {str(cr.get('message'))[:70]}",
                        r.get("ok") is False and cr.get("error") == "validation_error" and parca in str(cr.get("message"))
                        and not lib.session.posts)


class BilinmeyenSonucHat(_Ortak):
    """gate-d3 bulgu 1 — GERÇEK hat (`populate.main` → `calistir` → araç): yazma adımında sonucu BİLİNMEYEN hata
    (araç istisnası `calistir` içinde yakalanır) koşumu DURDURUR; bilinen red koşumu durdurmaz."""

    UC = ("name,datatype,length,decimals,description,fixed_values\n"
          "ZAXET_D_BIR,CHAR,1,0,Bir alan,\nZAXET_D_IKI,CHAR,2,0,Iki alan,\nZAXET_D_UC,CHAR,3,0,Uc alan,\n")

    def setUp(self):
        from sapadt._app import REGISTRY, load_all_tools
        load_all_tools()
        self.REG = REGISTRY
        orj = {n: REGISTRY[n].fn for n in REGISTRY}

        def geri():
            for n, f in orj.items():
                REGISTRY[n].fn = f
        self.addCleanup(geri)
        self.addCleanup(setattr, self.atom, "_get_client", self.atom._get_client)
        self.cagri = []
        self._yama("adt_get", lambda **kw: {"ok": True, "exists": False, "name": kw["name"]})

    def _yama(self, ad, fn):
        def kayit(**kw):
            self.cagri.append((ad, kw.get("name")))
            return fn(**kw)
        self.REG[ad].fn = kayit

    def _kos(self):
        p = self.proje()
        return self.main(["domain", "--csv", self.dosya(self.UC), "--package", PKG, "--transport", TR,
                          "--project-dir", str(p), *S1])

    @staticmethod
    def _ilk_sefer(hata):
        n = {"i": 0}

        def fn(**kw):
            n["i"] += 1
            if n["i"] == 1:
                if isinstance(hata, BaseException):
                    raise hata
                return hata
            return {"ok": True, "name": kw["name"]}
        return fn

    def _durdu_mu(self, d, kod, sinif="sonuc_bilinmiyor", mesaj="sonuç BİLİNMİYOR, SAP'de durumu kontrol et"):
        rows = d["result"]["rows"]
        stop = d["result"].get("stop") or {}
        return (kod == 1 and d["error"]["code"] == "run_stopped"
                and [r["status"] for r in rows] == ["hata", "islenmedi", "islenmedi"]
                and mesaj in rows[0].get("message", "")
                and stop.get("class") == sinif and stop.get("row") == 2 and stop.get("name") == "ZAXET_D_BIR"
                and stop.get("tool") == "adt_domain_create")

    def test_U1_arac_istisnasi_calistir_yakalar_kosum_durur(self):
        self._yama("adt_domain_create", self._ilk_sefer(TimeoutError("POST gönderildi, yanıt gelmedi")))
        d, kod = self._kos()
        rows = d["result"]["rows"]
        yarat = [c for c in self.cagri if c[0] == "adt_domain_create"]
        adim = rows[0]["steps"][-1]
        self.kaydet("U1 (probe A) araç istisnası → calistir unexpected → koşum DURUR, kalanlar islenmedi, 1 create",
                    "1 · run_stopped · hata,islenmedi,islenmedi · unexpected",
                    f"{kod} · {d['error']['code']} · {[r['status'] for r in rows]} · {yarat} · {adim.get('error')}",
                    self._durdu_mu(d, kod) and yarat == [("adt_domain_create", "ZAXET_D_BIR")]
                    and adim["error"]["code"] == "unexpected")

    def test_U2_composite_ic_baglanti_hatasi_kosum_durur(self):
        from sap_adt_lib import SAPConnectionError
        n = {"create": 0}

        def create_domain(**kw):
            n["create"] += 1
            raise SAPConnectionError("Connection timeout after 3 attempts: read timed out")
        ist = types.SimpleNamespace(get_object_metadata=lambda name, object_type=None: None, get_ddic_object=_ddic_yok,
                                    create_domain=create_domain)
        self.atom._get_client = lambda: ist
        d, kod = self._kos()
        rows = d["result"]["rows"]
        adim = rows[0]["steps"][-1]
        ic = ((adim.get("result") or {}).get("steps") or {}).get("create") or {}
        self.kaydet("U2 GERÇEK adt_domain_create içinde SAPConnectionError → steps.create connection_failed (üst "
                    "tool_failed) → koşum DURUR", "1 · run_stopped · steps.create=connection_failed · 1 create",
                    f"{kod} · {d['error']['code']} · {[r['status'] for r in rows]} · {adim.get('error')} · {ic} · "
                    f"create={n['create']}",
                    self._durdu_mu(d, kod) and n["create"] == 1 and ic.get("error") == "connection_failed"
                    and adim["error"]["code"] == "tool_failed")

    def test_U3_KONTROL_A2_calistir_kendisi_patlar(self):
        self._yama("adt_domain_create", lambda **kw: {"ok": True, "name": kw["name"]})
        eski = self.cli.calistir
        m = {"i": 0}

        def patlayan(tool, args, proj, **kw):
            if tool == "adt_domain_create":
                m["i"] += 1
                if m["i"] == 1:
                    raise TimeoutError("hat patladı")
            return eski(tool, args, proj, **kw)
        self.cli.calistir = patlayan
        self.addCleanup(setattr, self.cli, "calistir", eski)
        d, kod = self._kos()
        rows = d["result"]["rows"]
        self.kaydet("U3 KONTROL (probe A2) calistir'in kendisi istisna → step_exception → koşum DURUR",
                    "1 · run_stopped · step_exception", f"{kod} · {d['error']['code']} · {[r['status'] for r in rows]}",
                    self._durdu_mu(d, kod) and rows[0]["steps"][-1]["error"]["code"] == "step_exception"
                    and not [c for c in self.cagri if c[0] == "adt_domain_create"])

    def test_U4_KONTROL_bilinen_red_kosum_surer(self):
        from sap_adt_lib import SAPADTError, SAPLockError
        for ad, hata, beklenen in (
            ("araç-içi SAPADTError 400 → sap_error", SAPADTError("[400] Bad Request", status_code=400), "sap_error"),
            ("araç-içi SAPADTError 500 → sap_error (502/503/504 değil)",
             SAPADTError("Failed to create domain ZAXET_D_BIR", status_code=500), "sap_error"),
            ("araç-içi SAPLockError → locked", SAPLockError("is locked by BASKA", lock_owner="BASKA"), "locked"),
            ("araç sonucu create_failed", {"ok": False, "error": "create_failed", "message": "[400]",
                                           "exists_after": False}, "create_failed"),
            ("araç sonucu preflight_blocker", {"ok": False, "error": "preflight_blocker", "message": "FLTP"},
             "preflight_blocker"),
        ):
            self.cagri.clear()
            self._yama("adt_domain_create", self._ilk_sefer(hata))
            d, kod = self._kos()
            rows = d["result"]["rows"]
            self.kaydet(f"U4 KONTROL {ad} → satır HATA, koşum SÜRER (partial_failure)",
                        f"1 · partial_failure · hata,yazildi,yazildi · {beklenen}",
                        f"{kod} · {d['error']['code']} · {[r['status'] for r in rows]} · "
                        f"{rows[0]['steps'][-1].get('error')}",
                        kod == 1 and d["error"]["code"] == "partial_failure"
                        and [r["status"] for r in rows] == ["hata", "yazildi", "yazildi"]
                        and rows[0]["steps"][-1]["error"]["code"] == beklenen
                        and "BİLİNMİYOR" not in rows[0].get("message", ""))

    def test_U5_bilinen_sap_istisna_kumesi_lib_agaciyla_esit(self):
        import sap_adt_lib
        from sap_adt_lib import SAPADTError

        def agac(c):
            out = {c} if c.__module__ == sap_adt_lib.__name__ else set()
            for alt in c.__subclasses__():
                out |= agac(alt)
            return out
        beklenen = {c.__name__ for c in agac(SAPADTError)} - {"SAPConnectionError"}
        gercek = set(getattr(self.P, "_BILINEN_SAP_ISTISNALARI", ()))
        self.kaydet("U5 populate'in bilinen SAP istisna kümesi = lib SAPADTError ağacı − SAPConnectionError",
                    sorted(beklenen), sorted(gercek), gercek == beklenen)

    def test_U6_kimlik_ve_gecit_hatasi_gercek_str_ile_durdurur(self):
        from sap_adt_lib import SAPADTError, SAPAuthenticationError
        kimlik = "kimlik reddedildi, koşum durduruldu, hesap kilidi riskine karşı kalan satırlar denenmedi"
        for ad, hata, sinif, kod_parca, mesaj in (
            ("SAPAuthenticationError → auth_failed", SAPAuthenticationError("Authentication failed. Check credentials."),
             "hesap_kilidi_riski", "auth_failed", kimlik),
            ("SAPADTError(status_code=401) → '[401] …'", SAPADTError("Failed to create domain ZAXET_D_BIR", status_code=401),
             "hesap_kilidi_riski", "401", kimlik),
            ("SAPADTError(status_code=503) → '[503] …'", SAPADTError("Failed to create domain ZAXET_D_BIR", status_code=503),
             "sonuc_bilinmiyor", "503", "sonuç BİLİNMİYOR, SAP'de durumu kontrol et"),
        ):
            self.cagri.clear()
            self._yama("adt_domain_create", self._ilk_sefer(hata))
            d, kod = self._kos()
            stop = d["result"].get("stop") or {}
            yarat = [c for c in self.cagri if c[0] == "adt_domain_create"]
            self.kaydet(f"U6 {ad} → koşum DURUR ({sinif}), 1 create, durma ayrıntısı", f"run_stopped · {sinif} · {kod_parca}",
                        f"{kod} · {d['error']['code']} · {[r['status'] for r in d['result']['rows']]} · {stop} · {yarat}",
                        self._durdu_mu(d, kod, sinif, mesaj) and kod_parca in str(stop.get("code")) and len(yarat) == 1)


class KilitADT(SahteADT):
    """GERÇEK `SAPClient.push_object`'in konuştuğu lib yüzeyi — kilit olayları SIRALI kaydedilir."""

    def __init__(self, yonlendir, put_hatalari=(), kilit_hatalari=()):
        super().__init__(yonlendir)
        self.olay: list[tuple] = []
        self.kaynak: dict[str, str] = {}
        self.put_hatalari, self.kilit_hatalari = list(put_hatalari), list(kilit_hatalari)
        self._n = 0
        self._last_lock_effective_transport = TR
        self._last_lock_is_link_up = ""

    @staticmethod
    def _ad(url):
        return url.rstrip("/").split("/source/main")[0].rsplit("/", 1)[-1].upper()

    def get_transport_info(self, url):
        return TR

    def is_object_locked(self, url):
        self.olay.append(("ENQ_SORGU", self._ad(url)))
        return {"locked": False}

    def clear_enqueue_lock(self, url, transport=None):   # populate yolunda ASLA çağrılmamalı (Yasak C)
        self.olay.append(("CLEAR_ENQUEUE", self._ad(url)))
        return {"success": True}

    def find_ghost_transports(self):
        return []

    def fetch_source_etag(self, url):
        return None

    def lock_object(self, url, transport=None):
        if self.kilit_hatalari:
            exc = self.kilit_hatalari.pop(0)
            if exc is not None:
                self.olay.append(("LOCK_RED", self._ad(url)))
                raise exc
        self._n += 1
        h = f"H{self._n}"
        self.olay.append(("LOCK", self._ad(url), h))
        return h

    def set_object_source(self, url, src, handle, transport=None, etag=None):
        exc = self.put_hatalari.pop(0) if self.put_hatalari else None
        self.olay.append(("PUT", self._ad(url), handle, "HATA" if exc else "OK"))
        if exc:
            raise exc
        self.kaynak[self._ad(url)] = src

    def unlock_object(self, url, handle):
        self.olay.append(("UNLOCK", self._ad(url), handle))

    def activate_object(self, name, url):
        return {"success": True}

    def get_object_source(self, url, return_etag=False, version=None):
        return self.kaynak.get(self._ad(url), "")


class KilitSirasi(_Ortak):
    """Lider kilit şartı (2026-09-14): hata dalında kilit bırakılır, sonraki satır TAZE kilit alır,
    populate `clear_enqueue_lock` çağırmaz, kilit çakışması satır HATA + SM12 tarifi, koşum devam eder.

    Hat GERÇEK: `populate.main` → `calistir` → `adt_post_shell`/`adt_get`/`adt_push_source`/`adt_activate` →
    GERÇEK `SAPClient.push_object` (LOCK/PUT/UNLOCK mantığı sahte DEĞİL); sahte olan yalnız lib HTTP yüzeyi.
    Kapsam beyanı: `is_object_locked` burada kilitsiz döner — kendi kullanıcısının bayat kilidi dalı
    (`sap_client.push_object` ön-kontrolü) bu testte ÖLÇÜLMEDİ (ayrı ajan kaldırıyor; rapora yazıldı).
    """

    KAYNAK = "@EndUserText.label: '{e}'\ndefine view entity {ad} as select from t000 {{ key mandt }}\n"

    def _hat(self, adt_kw):
        import time as _time
        from sap_client import SAPClient
        yaratilan = set()

        def yon(c):
            if c["method"] == "POST" and c["path"] == "/sap/bc/adt/ddic/ddl/sources":
                m = __import__("re").search(r'adtcore:name="([^"]+)"', c["data"] or "")
                yaratilan.add((m.group(1) if m else "").upper())
                return Yanit(201, "")
            if c["method"] == "GET" and "inactiveobjects" in c["path"]:
                return Yanit(200, '<ioc:inactiveObjects xmlns:ioc="http://www.sap.com/abapxml/inactiveCtsObjects"/>')
            return Yanit(404, "")
        adt = KilitADT(yon, **adt_kw)

        class Ist(SahteIstemci):
            debug_enabled = False

            def get_object_metadata(self, name, object_type=None):
                return self.metadata if name.upper() in yaratilan else None

            def download_object(self, name, object_type=None, save_local=False):
                return adt.kaynak.get(name.upper(), "") if name.upper() in yaratilan else None

            def activate_object(self, name, object_type=None):
                return True
        ist = Ist(adt)
        ist.local_base = self.root
        ist._find_existing_transport = lambda n, t, tr: tr
        ist.push_object = types.MethodType(SAPClient.push_object, ist)
        self.atom._get_client = lambda: ist
        eski_uyku = _time.sleep
        _time.sleep = lambda s: None
        self.addCleanup(setattr, _time, "sleep", eski_uyku)
        type(self)._sayac_ad += 1
        dz = self.root / f"cds{self._sayac_ad}"
        dz.mkdir()
        for ad, e in (("ZAXET_I_KILA", "Kilit A"), ("ZAXET_I_KILB", "Kilit B")):
            (dz / f"{ad}.cds").write_text(self.KAYNAK.format(ad=ad, e=e), encoding="utf-8")
        p = self.proje()
        d, kod = self.main(["cds", "--source-dir", str(dz), "--package", PKG, "--transport", TR,
                            "--project-dir", str(p), *S1])
        return d, kod, adt

    def test_T1_put_hatasi_kilit_birakilir_sonraki_satir_taze_kilit(self):
        from sap_adt_lib import SAPADTError
        d, kod, adt = self._hat({"put_hatalari": [SAPADTError("HTTP 500 sunucu hatası", status_code=500)]})
        o = adt.olay
        rows = d["result"]["rows"]
        try:
            i_lock1 = o.index(("LOCK", "ZAXET_I_KILA", "H1"))
            i_put1 = o.index(("PUT", "ZAXET_I_KILA", "H1", "HATA"))
            i_unlock1 = o.index(("UNLOCK", "ZAXET_I_KILA", "H1"))
            i_lock2 = o.index(("LOCK", "ZAXET_I_KILB", "H2"))
            sira = i_lock1 < i_put1 < i_unlock1 < i_lock2
        except ValueError:
            sira = False
        # Satır 2 çevrimdışı `yazildi` OLAMAZ: push sonrası `sap_active_check` reviewer'ı (BLOCKER) canlı SAP'ye
        # bakar, sahte hostta ölçemez → ok:false (doğru, fail-closed). Bu yüzden satır 2'nin KİLİT yolu ölçülür:
        # taze LOCK(H2) → PUT OK → UNLOCK(H2), satır 2 hatası kilit hatası DEĞİL (SM12 tarifi yok).
        adimlar2 = [s["tool"] for s in rows[1].get("steps", [])]
        ok = (sira and not any(x[0] == "CLEAR_ENQUEUE" for x in o) and kod == 1
              and [r["status"] for r in rows] == ["hata", "hata"]
              and "adt_push_source" in rows[0]["message"] and "SM12" not in rows[0]["message"]
              and ("PUT", "ZAXET_I_KILB", "H2", "OK") in o and ("UNLOCK", "ZAXET_I_KILB", "H2") in o
              and o.index(("LOCK", "ZAXET_I_KILB", "H2")) < o.index(("UNLOCK", "ZAXET_I_KILB", "H2"))
              and adimlar2 == ["adt_get", "adt_post_shell", "adt_get", "adt_push_source"]
              and "post_check" in rows[1]["message"] and "SM12" not in rows[1]["message"])
        self.kaydet("T1 satır1 PUT hata → UNLOCK(H1) satır2 LOCK(H2)'den ÖNCE · clear_enqueue yok · satır2 taze kilitle "
                    "PUT OK + UNLOCK(H2) · exit 1",
                    "LOCK1<PUT1✗<UNLOCK1<LOCK2<UNLOCK2 · 0 CLEAR · satır2 push'a ulaştı",
                    f"sıra={sira} · {[r['status'] for r in rows]} · {kod} · {o} · satır2={adimlar2} "
                    f"{rows[1].get('message', '')[:120]}", ok)

    def test_T2_kilit_cakismasi_sm12_tarifi_kosum_devam(self):
        from sap_adt_lib import SAPLockError
        d, kod, adt = self._hat({"kilit_hatalari": [SAPLockError("Object is locked by user BASKA (enqueue)",
                                                                  lock_owner="BASKA", status_code=403)]})
        o = adt.olay
        rows = d["result"]["rows"]
        m = rows[0].get("message", "")
        ok = (kod == 1 and [r["status"] for r in rows] == ["hata", "hata"] and "SM12" in m
              and "SİLMEZ" in m and not any(x[0] == "CLEAR_ENQUEUE" for x in o)
              and not any(x[0] in ("UNLOCK", "PUT") and x[1] == "ZAXET_I_KILA" for x in o)
              and ("LOCK", "ZAXET_I_KILB", "H1") in o and ("PUT", "ZAXET_I_KILB", "H1", "OK") in o
              and ("UNLOCK", "ZAXET_I_KILB", "H1") in o and "SM12" not in rows[1]["message"])
        self.kaydet("T2 satır1 kilit çakışması → HATA + SM12 tarifi · kilit silme/temizleme YOK · PUT yok · satır2 kilit "
                    "alır, PUT OK, UNLOCK (koşum devam)", "hata(SM12) · 0 CLEAR · satır2 LOCK/PUT/UNLOCK · 1",
                    f"{[r['status'] for r in rows]} · {kod} · {m[-160:]} · {o}", ok)

    def test_T3_populate_kilit_temizleme_cagrisi_icermez(self):
        metin = Path(self.P.__file__).read_text(encoding="utf-8")
        yasak = [k for k in ("clear_enqueue_lock", "is_object_locked", "unlock_object", "lock_object", "SM12_temizle")
                 if k in metin]
        self.kaydet("T3 populate.py kilit açan/silen/temizleyen çağrı içermez (statik)", "[]", yasak, yasak == [])


class AltSurecCLI(unittest.TestCase):
    """Giriş script'i alt süreçte (kopya AXET_HOME, erişilemeyen sahte host)."""

    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="axet_populate_cli_"))
        cls.home_opt = H.build_home(cls.root, optin=True)
        cls.home_no = H.build_home(cls.root, optin=False)
        cls.n = 0

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def kos(self, home, argv, p):
        script = home / "skills-sap" / "sap-adt-foundation" / "scripts" / "sap_adt_populate.py"
        r = subprocess.run([sys.executable, str(script), *argv, "--project-dir", str(p)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=H.clean_env(), timeout=240,
                           stdin=subprocess.DEVNULL, cwd=str(p))
        try:
            return json.loads(r.stdout), r.returncode, r.stdout
        except json.JSONDecodeError:
            return None, r.returncode, r.stdout + r.stderr

    def hazirla(self, metin=DOMAIN_CSV):
        type(self).n += 1
        p = H.make_project(self.root / "projeler", f"c{self.n}")
        (p / "domains.csv").write_text(metin, encoding="utf-8")
        return p

    def kaydet(self, ad, beklenen, gercek, ok):
        H.kaydet(f"POPULATE-CLI {ad}", beklenen, str(gercek)[:160], ok)
        self.assertTrue(ok, f"{ad}: {gercek}")

    def test_C1_ag_yok_sonda_olculemedi(self):
        p = self.hazirla()
        d, kod, out = self.kos(self.home_opt, ["domain", "--csv", "domains.csv", "--package", PKG, "--transport", TR, *S1], p)
        rows = (d or {}).get("result", {}).get("rows", [])
        ok = (d is not None and kod == 1 and len(rows) == 2 and all(r["status"] == "hata" for r in rows)
              and all([s["tool"] for s in r["steps"]] == ["adt_get"] for r in rows)
              and H.PAROLA not in out and "127.0.0.1" not in out)
        self.kaydet("C1 CLI: kapı geçer, sonda ağsız ölçülemedi → 2 HATA, yalnız adt_get, exit 1, sızıntı yok",
                    "1 · 2 hata · adt_get", f"{kod} · {[r['status'] for r in rows]}", ok)

    def test_C2_red_ve_log(self):
        p = self.hazirla(DOMAIN_CSV + "MATNR_KOPYA,CHAR,18,0,Malzeme,\n")
        d, kod, out = self.kos(self.home_opt, ["domain", "--csv", "domains.csv", "--package", PKG, "--transport", TR, *S1], p)
        log = (p / ".axet-code" / "sap-write-log.jsonl")
        satirlar = [json.loads(s) for s in log.read_text(encoding="utf-8").splitlines()] if log.is_file() else []
        ok = (kod == 2 and d["error"]["code"] == "prepass_gate_rejected"
              and any(s["result"] == "ADR_0005_A" and s["object"] == "MATNR_KOPYA" for s in satirlar)
              and all(s["result"] != "ok" for s in satirlar))
        self.kaydet("C2 CLI: standart ad → ön geçiş 2, red logda, başarılı yazma satırı yok", "2 · ADR_0005_A logda",
                    f"{kod} · {[(s['tool'], s['result']) for s in satirlar]}", ok)

    def test_C3_optin_yok_kullanim_dryrun(self):
        p = self.hazirla()
        d, kod, _o = self.kos(self.home_no, ["domain", "--csv", "domains.csv", "--package", PKG, "--transport", TR, *S1], p)
        self.kaydet("C3a CLI opt-in yok → 2 write_not_optin_global", "2 · write_not_optin_global",
                    f"{kod} · {d['gate']['prepass']['rejections'][0]['code']}",
                    kod == 2 and d["gate"]["prepass"]["rejections"][0]["code"] == "write_not_optin_global")
        d, kod, _o = self.kos(self.home_opt, ["--package", PKG], p)
        self.kaydet("C3b CLI tür argümanı yok → 3 usage_error (tek JSON)", "3 · usage_error",
                    f"{kod} · {(d or {}).get('error')}", kod == 3 and d["error"]["code"] == "usage_error")
        d, kod, _o = self.kos(self.home_opt, ["tabl", "--csv", "domains.csv", "--package", PKG, *S1], p)
        self.kaydet("C3c CLI tablo türü → 3", "3", kod, kod == 3)
        d, kod, _o = self.kos(self.home_opt, ["domain", "--csv", "domains.csv", "--package", PKG, "--transport", TR,
                                              "--dry-run", *S1], p)
        self.kaydet("C3d CLI dry-run → 0, satırlar dry_run", "0 · dry_run×2",
                    f"{kod} · {d['result']['summary']}", kod == 0 and d["result"]["summary"]["dry_run"] == 2)

    def test_C4_okunamaz_kodlama_cikis_3_json(self):
        bas = "name,datatype,length,decimals,description,fixed_values\n"
        argv = ["domain", "--csv", "domains.csv", "--package", PKG, "--transport", TR, "--dry-run", *S1]
        for ad, veri in (("cp1254", (bas + "ZAXET_D_BIR,CHAR,1,0,Durum alanı şğı,\n").encode("cp1254")),
                         ("UTF-16", (bas + "ZAXET_D_BIR,CHAR,1,0,Durum,\n").encode("utf-16"))):
            p = self.hazirla()
            (p / "domains.csv").write_bytes(veri)
            d, kod, out = self.kos(self.home_opt, argv, p)
            self.kaydet(f"C4 CLI {ad} CSV → çıkış 3 · tek JSON · csv_unreadable (traceback yok)", "3 · csv_unreadable",
                        f"{kod} · {(d or {}).get('error')} · {out[-120:] if d is None else ''}",
                        d is not None and kod == 3 and d["error"]["code"] == "csv_unreadable")
        p = self.hazirla()
        (p / "domains.csv").write_bytes(("﻿" + bas + "ZAXET_D_BIR,CHAR,1,0,Durum alanı,\n")
                                        .replace("\n", "\r\n").encode("utf-8"))
        d, kod, _o = self.kos(self.home_opt, argv, p)
        self.kaydet("C4 KONTROL CLI UTF-8 + BOM + CRLF → dry-run 0", "0 · dry_run 1",
                    f"{kod} · {(d or {}).get('result', {}).get('summary')}",
                    d is not None and kod == 0 and d["result"]["summary"]["dry_run"] == 1)


if __name__ == "__main__":
    unittest.main()
