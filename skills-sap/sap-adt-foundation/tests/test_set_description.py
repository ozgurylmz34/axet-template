# -*- coding: utf-8 -*-
"""adt_set_description (2026-09-13) — süreç içi, SAHTE istemci (ağ yok).

Sahte ADT oturumu her HTTP çağrısını kaydeder; "LOCK→PUT→UNLOCK sırası", "kilit silinmedi",
"412'de tek retry", "ağdan önce red" iddiaları çağrı listesiyle kanıtlanır. Envelope örnekleri
jeneriktir (ZCA000 demo adları); gerçek sistemden alınmamıştır.
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

from test_new_write_tools import SAHTE_HOST, TR, SahteADT, SahteIstemci, Yanit  # noqa: E402

AD = "ZCA000_I_DEMO"
YOL = "/sap/bc/adt/ddic/ddl/sources/zca000_i_demo"
KILIT_OK = f"<LOCK_HANDLE>H1</LOCK_HANDLE><CORRNR>{TR}</CORRNR>"
INAKTIF = [{"name": AD, "uri": YOL, "type": "DDLS/DF"}]


def zarf(desc="Eski açıklama", ml="TR", limit="60", kok_desc=True):
    d = f' adtcore:description="{desc}"' if kok_desc else ""
    return ('<?xml version="1.0" encoding="utf-8"?>'
            '<ddl:ddlSource xmlns:ddl="http://www.sap.com/adt/ddic/ddlsources" '
            f'xmlns:adtcore="http://www.sap.com/adt/core"{d} adtcore:descriptionTextLimit="{limit}" '
            f'adtcore:masterLanguage="{ml}" adtcore:name="{AD}" adtcore:type="DDLS/DF">'
            '<adtcore:packageRef adtcore:description="Paket açıklaması" adtcore:name="ZCA000"/></ddl:ddlSource>')


class Senaryo:
    """Yönlendirici: GET envelope · LOCK · PUT · UNLOCK · aktif readback."""

    def __init__(self):
        self.zarf = zarf()
        self.zarf2 = None            # 412 sonrası yeniden okuma farklı olsun istenirse
        self.get_durum = 200
        self.etag = "E1"
        self.lock = [Yanit(200, KILIT_OK)]
        self.put = [Yanit(200)]
        self.aktif = None            # None → son PUT gövdesi okunur
        self.son_put = None
        self._get = 0

    @staticmethod
    def _sira(liste):
        return liste.pop(0) if len(liste) > 1 else liste[0]

    def __call__(self, c):
        m, prm = c["method"], c["params"]
        if m == "GET" and prm.get("version") == "active":
            return Yanit(200, self.aktif if self.aktif is not None else (self.son_put or self.zarf))
        if m == "GET":
            self._get += 1
            metin = self.zarf if (self._get == 1 or self.zarf2 is None) else self.zarf2
            return Yanit(self.get_durum, metin, {"ETag": self.etag,
                                                 "Content-Type": "application/vnd.sap.adt.ddlsource+xml; charset=utf-8"})
        if m == "POST" and prm.get("_action") == "LOCK":
            return self._sira(self.lock)
        if m == "POST" and prm.get("_action") == "UNLOCK":
            return Yanit(200)
        if m == "PUT":
            self.son_put = c["data"]
            return self._sira(self.put)
        return Yanit(599, "beklenmeyen çağrı")


class SahteADTAciklama(SahteADT):
    timeout_default = 60

    def __init__(self, yonlendir, inaktif):
        super().__init__(yonlendir)
        self.inaktif = list(inaktif)

    def get_inactive_objects(self):
        self.cagri.append({"method": "LIB", "path": "get_inactive_objects", "params": {}, "data": None, "headers": {}})
        v = self.inaktif.pop(0) if len(self.inaktif) > 1 else self.inaktif[0]
        if isinstance(v, Exception):
            raise v
        return v

    def put_423_diagnosis(self, url, transport):
        return {"likely": "başka transport"}


class AciklamaAraci(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="axet_aciklama_"))
        cls._eski_env = {k: v for k, v in os.environ.items() if k.startswith("ADT_") or k == "AXET_SAP_PROJECT_DIR"}
        for k in list(cls._eski_env):
            os.environ.pop(k, None)
        from sapadt import pull_state
        from sapadt.tools import atom, description
        cls.atom, cls.desc, cls.ps = atom, description, pull_state
        cls._eski_client = atom._get_client
        cls._eski_oku = atom._adt_get_oku
        cls._sayac = 0

    @classmethod
    def tearDownClass(cls):
        cls.atom._get_client = cls._eski_client
        cls.atom._adt_get_oku = cls._eski_oku
        os.environ.pop("AXET_SAP_PROJECT_DIR", None)
        os.environ.update(cls._eski_env)
        shutil.rmtree(cls.root, ignore_errors=True)

    def setUp(self):
        type(self)._sayac += 1
        self.p = H.make_project(self.root, f"p{self._sayac}")
        os.environ["AXET_SAP_PROJECT_DIR"] = str(self.p)
        self.atom._adt_get_oku = self._eski_oku

    def kur(self, sen=None, inaktif=([],)):
        sen = sen or Senaryo()
        adt = SahteADTAciklama(sen, inaktif)
        ist = SahteIstemci(adt)
        self.atom._get_client = lambda: ist
        return adt, sen

    def kos(self, **kw):
        a = {"name": AD, "object_type": "ddls", "description": "Yeni açıklama", "transport": TR}
        a.update(kw)
        return self.desc.adt_set_description(**a)

    def kaydet(self, ad, beklenen, gercek, ok):
        H.kaydet(f"AÇIKLAMA {ad}", beklenen, str(gercek)[:160], ok)
        self.assertTrue(ok, f"{ad}: {gercek}")

    @staticmethod
    def yontemler(adt):
        out = []
        for c in adt.cagri:
            if c["method"] == "POST":
                out.append(c["params"].get("_action") or "POST")
            elif c["method"] in ("GET", "PUT", "DELETE"):
                out.append(c["method"] + ("(active)" if c["params"].get("version") == "active" else ""))
            else:
                out.append(c["path"])
        return out

    # ── başarı yolları ───────────────────────────────────────────────────────────────────
    def test_01_basari_otomatik_aktivasyon(self):
        adt, sen = self.kur(inaktif=([], INAKTIF, []))
        r = self.kos(description='Satış & "Dağıtım"')
        sira = self.yontemler(adt)
        beklenen = ["GET", "get_inactive_objects", "LOCK", "PUT", "UNLOCK", "get_inactive_objects",
                    "activate_object", "get_inactive_objects", "GET(active)"]
        put = [c for c in adt.cagri if c["method"] == "PUT"][0]
        ok = (r.get("ok") is True and r["state"] == "active" and r["readback_verified"] is True
              and r["activation"]["activated"] is True and sira == beklenen
              and put["headers"].get("If-Match") == "E1" and put["params"] == {"lockHandle": "H1", "corrNr": TR}
              and put["headers"].get("Content-Type") == "application/vnd.sap.adt.ddlsource+xml"
              and 'adtcore:description="Satış &amp; &quot;Dağıtım&quot;"' in put["data"]
              and 'adtcore:packageRef adtcore:description="Paket açıklaması"' in put["data"]
              and r["description_after"] == 'Satış & "Dağıtım"' and r["live_evidence"] == "measured_ddls")
        self.kaydet("01 başarı: LOCK→PUT→UNLOCK→aktive→readback, kaçış, paket açıklaması dokunulmadı",
                    "ok · active · sıra doğru", f"{r.get('error')} {sira}", ok)

    def test_02_ayni_deger_noop(self):
        adt, _s = self.kur()
        r = self.kos(description="Eski açıklama")
        ok = r.get("ok") is True and r["changed"] is False and self.yontemler(adt) == ["GET"]
        self.kaydet("02 aynı açıklama → NOOP, kilit/PUT yok", "ok · changed:false · yalnız GET", self.yontemler(adt), ok)

    def test_03_412_tek_retry(self):
        sen = Senaryo()
        govde412 = ('<exc><entry key="T100KEY-ID">SADT_RESOURCE</entry><entry key="T100KEY-NO">043</entry>'
                    '<entry key="T100KEY-V2">E2</entry></exc>')
        sen.put = [Yanit(412, "SADT_RESOURCE " + govde412), Yanit(200)]
        adt, _s = self.kur(sen, inaktif=([], INAKTIF, []))
        r = self.kos()
        putlar = [c for c in adt.cagri if c["method"] == "PUT"]
        sira = self.yontemler(adt)
        ok = (r.get("ok") is True and r["etag_retry"] is True and len(putlar) == 2
              and putlar[0]["headers"].get("If-Match") == "E1" and putlar[1]["headers"].get("If-Match") == "E2"
              and sira.count("LOCK") == 2 and sira.count("UNLOCK") == 2)
        self.kaydet("03 412 SADT_RESOURCE 043 → yeni LOCK döngüsünde T100KEY-V2 ile TEK retry",
                    "ok · 2 PUT · 2 LOCK/UNLOCK", sira, ok)

    def test_04_412_envelope_degismis_retry_yok(self):
        sen = Senaryo()
        sen.put = [Yanit(412, 'SADT_RESOURCE <entry key="T100KEY-NO">043</entry><entry key="T100KEY-V2">E2</entry>')]
        sen.zarf2 = zarf(desc="Başkası değiştirdi")
        adt, _s = self.kur(sen)
        r = self.kos()
        sira = self.yontemler(adt)
        ok = r.get("error") == "envelope_changed_since_read" and sira.count("PUT") == 1 and sira.count("UNLOCK") == 1
        self.kaydet("04 412 + envelope ilk okumadan beri değişmiş → retry yok", "envelope_changed_since_read · 1 PUT",
                    f"{r.get('error')} {sira}", ok)

    def test_05_ikinci_412_fail(self):
        sen = Senaryo()
        sen.put = [Yanit(412, "object ETag E2 does not match")]
        adt, _s = self.kur(sen)
        r = self.kos()
        ok = r.get("error") == "put_precondition_failed" and self.yontemler(adt).count("PUT") == 2
        self.kaydet("05 retry de 412 → put_precondition_failed, üçüncü deneme yok", "put_precondition_failed · 2 PUT",
                    f"{r.get('error')} {self.yontemler(adt)}", ok)

    # ── kilit ────────────────────────────────────────────────────────────────────────────
    def test_06_kilit_cakismasi_silme_yok_ve_sizinti_yok(self):
        sen = Senaryo()
        sen.lock = [Yanit(403, f"EU 510 locked by {H.KULLANICI} ({H.PAROLA}) at {SAHTE_HOST}")]
        adt, _s = self.kur(sen)
        r = self.kos()
        sira = self.yontemler(adt)
        dump = json.dumps(r, ensure_ascii=False)
        ok = (r.get("error") == "lock_conflict" and "SM12" in r.get("message", "") and "PUT" not in sira
              and "UNLOCK" not in sira and "DELETE" not in sira
              and all(c["params"].get("_action") in (None, "LOCK") for c in adt.cagri)
              and H.PAROLA not in dump and SAHTE_HOST not in dump)
        self.kaydet("06 kilit çakışması → lock_conflict + SM12, PUT/UNLOCK/DELETE yok, parola/host maskeli",
                    "lock_conflict · yalnız LOCK", f"{r.get('error')} {sira}", ok)

    def test_07_kilit_handle_yok_lock_failed(self):
        sen = Senaryo()
        sen.lock = [Yanit(500, "iç hata")]
        adt, _s = self.kur(sen)
        r = self.kos()
        ok = r.get("error") == "lock_failed" and "PUT" not in self.yontemler(adt)
        self.kaydet("07 LOCK 500 handle yok → lock_failed", "lock_failed", r.get("error"), ok)

    def test_08_transport_uyusmazligi(self):
        sen = Senaryo()
        sen.lock = [Yanit(200, "<LOCK_HANDLE>H1</LOCK_HANDLE><CORRNR>TESTK900999</CORRNR>")]
        adt, _s = self.kur(sen)
        r = self.kos()
        sira = self.yontemler(adt)
        ok = r.get("error") == "transport_mismatch" and "PUT" not in sira and sira.count("UNLOCK") == 1
        self.kaydet("08 CORRNR ≠ istenen → transport_mismatch, PUT yok, kilit bırakıldı", "transport_mismatch · UNLOCK 1",
                    f"{r.get('error')} {sira}", ok)

    def test_09_put_istisnasinda_unlock_finally(self):
        sen = Senaryo()
        sen.put = [RuntimeError("bağlantı koptu")]
        adt, _s = self.kur(sen)
        r = self.kos()
        sira = self.yontemler(adt)
        ok = r.get("ok") is False and sira.count("UNLOCK") == 1 and "BELİRSİZ" in r.get("notice", "")
        self.kaydet("09 PUT istisnası → UNLOCK yine koştu (finally) + belirsizlik notu", "UNLOCK 1 · notice",
                    f"{r.get('error')} {sira}", ok)

    def test_10_put_423_teshis(self):
        sen = Senaryo()
        sen.put = [Yanit(423, "InvalidLockHandle")]
        adt, _s = self.kur(sen)
        r = self.kos()
        ok = r.get("error") == "put_failed" and "diagnosis_423" in r and self.yontemler(adt).count("UNLOCK") == 1
        self.kaydet("10 PUT 423 → put_failed + diagnosis_423", "put_failed", r.get("error"), ok)

    # ── aktivasyon / readback ────────────────────────────────────────────────────────────
    def test_11_once_inaktif_otomatik_aktivasyon_yok(self):
        adt, _s = self.kur(inaktif=(INAKTIF, INAKTIF))
        r = self.kos()
        sira = self.yontemler(adt)
        ok = (r.get("error") == "activation_required" and r["state"] == "inactive" and "activate_object" not in sira
              and r["changed"] is True)
        self.kaydet("11 PUT öncesi zaten inaktif → activation_required, otomatik aktivasyon YOK",
                    "activation_required · inactive", f"{r.get('error')} {sira}", ok)

    def test_12_liste_okunamadi(self):
        adt, _s = self.kur(inaktif=([], RuntimeError("liste yok")))
        r = self.kos()
        ok = r.get("error") == "activation_state_unknown" and r["state"] == "unknown"
        self.kaydet("12 PUT sonrası liste okunamadı → activation_state_unknown", "activation_state_unknown", r.get("error"), ok)

    def test_13_aktivasyon_basarisiz(self):
        adt, _s = self.kur(inaktif=([], INAKTIF))
        adt.akt_sonuc = {"success": False, "errors": [{"message": "aktivasyon hatası"}]}
        r = self.kos()
        ok = r.get("error") == "activation_failed" and r["state"] == "inactive"
        self.kaydet("13 aktivasyon başarısız → activation_failed", "activation_failed", r.get("error"), ok)

    def test_14_aktivasyon_sonrasi_hala_listede(self):
        adt, _s = self.kur(inaktif=([], INAKTIF, INAKTIF))
        r = self.kos()
        ok = r.get("error") == "activation_not_verified" and r["activation"]["activated"] is True
        self.kaydet("14 aktive 'başarılı' ama hâlâ listede → activation_not_verified", "activation_not_verified",
                    r.get("error"), ok)

    def test_15_readback_uyusmazligi(self):
        sen = Senaryo()
        sen.aktif = zarf(desc="Eski açıklama")
        adt, _s = self.kur(sen, inaktif=([], []))
        r = self.kos()
        ok = r.get("error") == "readback_mismatch" and r["readback_verified"] is False and r.get("ok") is False
        self.kaydet("15 aktif sürümde eski açıklama → readback_mismatch", "readback_mismatch", r.get("error"), ok)

    # ── ağdan önce redler ────────────────────────────────────────────────────────────────
    def test_16_desteklenmeyen_tipler_ag_yok(self):
        adt, _s = self.kur()
        sonuc = {t: self.kos(object_type=t).get("error") for t in ("srvb", "prog", "program", "dtel", "tabl", "fugr")}
        ok = set(sonuc.values()) == {"unsupported_type"} and adt.cagri == []
        self.kaydet("16 srvb/prog/dtel/tabl/fugr → unsupported_type, ağ çağrısı yok", "unsupported_type × 6 · 0 çağrı",
                    sonuc, ok)

    def test_17_guardrail_redleri_ag_yok(self):
        adt, _s = self.kur()
        r = {
            "std": self.kos(name="MARA").get("code"),
            "tr": self.kos(transport="").get("code"),
            "bos": self.kos(description="  ").get("code"),
            "cok_satir": self.kos(description="a\nb").get("error"),
            "sinif60": self.kos(object_type="class", name="ZCA000_CL_DEMO", description="x" * 61).get("error"),
        }
        ok = (r == {"std": "ADR_0005_A", "tr": "ADR_0005_C", "bos": "ADR_0005_D", "cok_satir": "invalid_argument",
                    "sinif60": "invalid_argument"} and adt.cagri == [])
        self.kaydet("17 std ad / transport yok / boş / çok satır / sınıf>60 → ağdan önce red", "A · C · D · invalid ×2",
                    r, ok)

    def test_18_tier_qa_red(self):
        p = H.make_project(self.root, f"qa{self._sayac}", tier_lines=("ADT_SAP_TIER=QA",))
        os.environ["AXET_SAP_PROJECT_DIR"] = str(p)
        adt, _s = self.kur()
        r = self.kos()
        ok = r.get("error") == "guardrail_violation" and adt.cagri == []
        self.kaydet("18 tier QA → guardrail, ağ yok", "guardrail_violation", r.get("code"), ok)

    def test_19_kok_etiket_korumasi(self):
        sen = Senaryo()
        sen.zarf = zarf(kok_desc=False)          # açıklama yalnız packageRef'te
        adt, _s = self.kur(sen)
        r = self.kos()
        ok = r.get("error") == "envelope_unrecognized" and self.yontemler(adt) == ["GET"]
        self.kaydet("19 açıklama kökte değil (yalnız packageRef) → envelope_unrecognized, LOCK yok",
                    "envelope_unrecognized", f"{r.get('error')} {self.yontemler(adt)}", ok)

    def test_20_master_dil_uyusmazligi(self):
        sen = Senaryo()
        sen.zarf = zarf(ml="EN")
        adt, _s = self.kur(sen)
        r = self.kos()
        ok = r.get("code") == "ADR_0005_D" and self.yontemler(adt) == ["GET"]
        self.kaydet("20 envelope masterLanguage EN ≠ TR → ADR_0005_D, LOCK yok", "ADR_0005_D", r.get("code"), ok)

    def test_21_description_text_limit(self):
        sen = Senaryo()
        sen.zarf = zarf(limit="10")
        adt, _s = self.kur(sen)
        r = self.kos(description="On karakterden uzun")
        ok = r.get("error") == "description_too_long" and self.yontemler(adt) == ["GET"]
        self.kaydet("21 descriptionTextLimit aşımı → description_too_long, LOCK yok", "description_too_long",
                    r.get("error"), ok)

    def test_22_envelope_404(self):
        sen = Senaryo()
        sen.get_durum = 404
        adt, _s = self.kur(sen)
        r = self.kos()
        ok = r.get("error") == "not_found" and self.yontemler(adt) == ["GET"]
        self.kaydet("22 envelope 404 → not_found", "not_found", r.get("error"), ok)

    # ── pull-before-edit ─────────────────────────────────────────────────────────────────
    def test_23_pull_kaydi_canli_degismis(self):
        self.assertIsNone(self.ps.kaydet(AD, "ddls", "define view entity eski {}"))
        self.atom._adt_get_oku = lambda n, t, s=True: {"ok": True, "exists": True, "source": "define view entity yeni {}"}
        adt, _s = self.kur()
        r = self.kos()
        ok = r.get("error") == "source_changed_since_pull" and adt.cagri == []
        self.kaydet("23 çekme kaydı var, canlı kaynak değişmiş → source_changed_since_pull, envelope GET yok",
                    "source_changed_since_pull", r.get("error"), ok)

    def test_24_pull_kaydi_ayni_yazim_sonrasi_silinir(self):
        kaynak = "define view entity ayni {}"
        self.assertIsNone(self.ps.kaydet(AD, "ddls", kaynak))
        self.atom._adt_get_oku = lambda n, t, s=True: {"ok": True, "exists": True, "source": kaynak}
        adt, _s = self.kur(inaktif=([], INAKTIF, []))
        r = self.kos()
        kayit, _h = self.ps.kayit_al(AD, "ddls")
        ok = r.get("ok") is True and str(r.get("pull_state", "")).startswith("silindi") and kayit is None
        self.kaydet("24 çekme kaydı taze → yazıldı, kayıt silindi (sonraki push adt_get ister)", "ok · silindi",
                    f"{r.get('error')} {r.get('pull_state')}", ok)


if __name__ == "__main__":
    unittest.main()
