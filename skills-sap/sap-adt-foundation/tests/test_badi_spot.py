# -*- coding: utf-8 -*-
"""BAdI enhancement spot (ENHS/XSB) — lib + okuma aracı + yazma aracı + kapı (süreç içi, ağ yok).

Ayrı ayrı test edilir (lider kararı: önce lib + okuma, sonra yazma):
  · S — lib saf yardımcılar: ölçülmüş canlı readback'in ayrıştırılması, kur(ayrıştır) == ölçülmüş kabul edilmiş PUT
        belgesi (bayt-eşit), ad denetimi, TAM belge koruması, ters `singleUse` eşlemesi.
  · W — lib `write_enhancement_spot`: standart spot'a kilit alınmaz, kilit altı taban değişirse PUT yok, sıra
        LOCK → GET → PUT → UNLOCK, PUT hatasında da unlock.
  · R — `adt_badi_spot_read`: model + pull kaydı, standart spot `writable:false`, yok → exists:false.
  · Y — `adt_badi_spot_write`: kayıt yok → red, canlı değişti → red, standart BAdI adı → red (ağsız), mutlu yol,
        readback farkı → ok:false, ilk yaratım (paket + açıklama).
  · G — yazma kapısı: araç yazma sınıfında, transport zorunlu, standart spot/BAdI adı RED; okuma aracı okuma sınıfında.
Fikstürler `fixtures/enhs_badi_spot/` = kaynak çekirdeğin ölçülmüş canlı belgeleri (adlar örnek, kimlik yer tutucu).
"""
from __future__ import annotations

import copy
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

import sapadt  # noqa: E402,F401
import sap_adt_lib as L  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures" / "enhs_badi_spot"
READBACK = (FIX / "readback_aktif.xml").read_bytes()
PUT_KABUL = (FIX / "put_kabul.xml").read_text(encoding="utf-8").strip()   # dosya sonu satır sonu (kaynak da strip)
SPOT = "ZSD001_ES_BADI_A"
BADI = "ZSD001_BADI_A"


def _std(xml: bytes) -> bytes:
    return xml.replace(b'adtcore:masterSystem="XYZ"', b'adtcore:masterSystem="SAP"')


class _Yanit:
    def __init__(self, kod, govde=b""):
        self.status_code = kod
        self.content = govde if isinstance(govde, bytes) else govde.encode("utf-8")
        self.text = self.content.decode("utf-8", "replace")
        self.headers = {}


# ─────────────────────────── S — saf yardımcılar ───────────────────────────
class S_Lib(unittest.TestCase):
    def test_S1_ayristir_olculen_readback(self):
        m = L.enhs_belgesi_ayristir(READBACK)
        t = m["tanimlar"][0] if m["tanimlar"] else {}
        ok = (m["spot"]["name"] == SPOT and m["spot"]["package"] == "$TMP" and m["modellenmeyen"] == []
              and len(m["tanimlar"]) == 1 and t.get("name") == BADI)
        H.kaydet("ENHS S1 ayrıştır", "1 tanım · modellenmeyen=[]", f"{m['spot'].get('name')} {len(m['tanimlar'])} {m['modellenmeyen']}", ok)
        self.assertTrue(ok)

    def test_S2_kur_ayristir_bayt_esit(self):
        govde = L.enhs_belgesi_kur(L.enhs_belgesi_ayristir(READBACK))
        ok = govde == PUT_KABUL
        H.kaydet("ENHS S2 kur(ayrıştır(readback)) == kabul edilmiş PUT", "bayt-eşit", str(ok), ok)
        self.assertTrue(ok)

    def test_S3_ad_denetimi(self):
        std = L.enhs_ad_denetimi("ES_STANDART", [])
        std_badi = L.enhs_ad_denetimi(SPOT, ["BADI_STANDART"])
        uzun = L.enhs_ad_denetimi("Z" + "X" * 30, [])
        sinir = L.enhs_ad_denetimi("Z" + "X" * 29, [BADI])
        ok = bool(std) and bool(std_badi) and bool(uzun) and sinir == []
        H.kaydet("ENHS S3 ad denetimi", "standart spot/BAdI + 31 kr RED · 30 kr geçer",
                 f"{bool(std)} {bool(std_badi)} {bool(uzun)} {sinir}", ok)
        self.assertTrue(ok)

    def test_S4_tam_belge_korunur_ve_ters_esleme(self):
        m = L.enhs_belgesi_ayristir(READBACK)
        once = copy.deepcopy(m)
        yeni, yap = L.enhs_spec_uygula(m, {"tanimlar": [{"badi": BADI, "shorttext": "Yeni metin",
                                                          "coklu_kullanim": "evet"}]})
        t0, t1 = once["tanimlar"][0], yeni["tanimlar"][0]
        diger = {k: v for k, v in t0.items() if k not in ("shorttext", "singleUse")}
        diger1 = {k: v for k, v in t1.items() if k not in ("shorttext", "singleUse")}
        ok = (m == once and t1["shorttext"] == "Yeni metin" and t1["singleUse"] == "false" and diger == diger1
              and L.enhs_coklu_kullanim("hayir") == "true" and bool(yap))
        H.kaydet("ENHS S4 yalnız verilen alan değişir · evet→singleUse=false", "fallback/örnek/filtre korunur",
                 f"{t1.get('shorttext')} {t1.get('singleUse')} korunan={diger == diger1}", ok)
        self.assertTrue(ok)
        with self.assertRaises(ValueError):
            L.enhs_spec_uygula(m, {"tanimlar": [{"badi": BADI, "bilinmeyen": 1}]})


# ─────────────────────────── W — lib yazma katmanı ───────────────────────────
def _lib_istemci(belgeler):
    """Gerçek `SAPADTClient` metodları; ağ yerine sahte kilit/GET/PUT/UNLOCK. `belgeler` = sıralı GET gövdeleri."""
    c = L.SAPADTClient.__new__(L.SAPADTClient)
    c.url = "http://sahte.invalid"
    c.iz = []
    kuyruk = list(belgeler)

    def get(spot, version=None):
        c.iz.append("GET")
        return _Yanit(200, kuyruk.pop(0) if len(kuyruk) > 1 else kuyruk[0])

    def lock(url, transport=None):
        c.iz.append("LOCK")
        return "H1"

    def unlock(url, h):
        c.iz.append("UNLOCK")
        return True

    def istek(metod, url, **kw):
        c.iz.append(metod.upper())
        return _Yanit(getattr(c, "put_kod", 200), b"")

    c.get_enhancement_spot, c.lock_object, c.unlock_object = get, lock, unlock
    c._request_with_csrf_retry = istek
    c._get_headers = lambda *a, **k: {}
    return c


class W_LibYazma(unittest.TestCase):
    def setUp(self):
        self.taban = L.enhs_belgesi_ayristir(READBACK)
        self.yeni, _ = L.enhs_spec_uygula(self.taban, {"tanimlar": [{"badi": BADI, "shorttext": "X"}]})

    def test_W1_standart_spot_kilit_yok(self):
        c = _lib_istemci([_std(READBACK)])
        r = c.write_enhancement_spot(SPOT, self.yeni, "DEVK900001", taban=self.taban)
        ok = r["ok"] is False and "standart_obje" in (r["hata"] or "") and "LOCK" not in c.iz
        H.kaydet("ENHS W1 masterSystem=SAP → kilit yok", "standart_obje · LOCK yok", f"{r['hata']} {c.iz}", ok)
        self.assertTrue(ok)

    def test_W2_kilit_alti_taban_degisti(self):
        baska = READBACK.replace("Test 413 BAdI tanımı (güncel)".encode("utf-8"), "Araya giren".encode("utf-8"))
        c = _lib_istemci([READBACK, baska])
        r = c.write_enhancement_spot(SPOT, self.yeni, "DEVK900001", taban=self.taban)
        ok = r["ok"] is False and str(r["hata"]).startswith("taban_degisti") and "PUT" not in c.iz and c.iz[-1] == "UNLOCK"
        H.kaydet("ENHS W2 kilit altı değişiklik → PUT yok, unlock", "taban_degisti", f"{r['hata'][:40]} {c.iz}", ok)
        self.assertTrue(ok)

    def test_W3_sira_ve_put_hatasinda_unlock(self):
        c = _lib_istemci([READBACK])
        r = c.write_enhancement_spot(SPOT, self.yeni, "DEVK900001", taban=self.taban)
        ok1 = r["ok"] is True and c.iz == ["GET", "LOCK", "GET", "PUT", "UNLOCK"]
        c2 = _lib_istemci([READBACK])
        c2.put_kod = 400
        r2 = c2.write_enhancement_spot(SPOT, self.yeni, "DEVK900001", taban=self.taban)
        ok2 = r2["ok"] is False and c2.iz[-1] == "UNLOCK" and r2["lock_released"] is True
        r3 = _lib_istemci([READBACK]).write_enhancement_spot(SPOT, self.yeni, "", taban=self.taban)
        ok = ok1 and ok2 and r3["hata"] == "transport_yok"
        H.kaydet("ENHS W3 sıra · PUT 400'de unlock · transportsuz", "GET LOCK GET PUT UNLOCK",
                 f"{c.iz} · {c2.iz} · {r3['hata']}", ok)
        self.assertTrue(ok)


# ─────────────────────────── R/Y — araçlar ───────────────────────────
class _SahteAdt:
    """`adt_badi_spot_*` araçlarının gördüğü SAPADTClient yüzü (durum makinesi)."""

    url = "http://sahte.invalid"
    language = "TR"

    def __init__(self, belge=READBACK, readback_bozuk=False):
        self.belge = belge
        self.iz: list[str] = []
        self.readback_bozuk = readback_bozuk

    def get_enhancement_spot(self, spot, version=None):
        self.iz.append("GET")
        if self.belge is None:
            return _Yanit(404, b"")
        return _Yanit(200, self.belge)

    def create_enhancement_spot(self, spot, description, package, transport, root=None):
        self.iz.append("CREATE")
        self.belge = L.enhs_bos_kabuk_govdesi(spot, description, package, "TR").encode("utf-8")
        return {"ok": True, "status": 201, "location": "/x", "text": ""}

    def write_enhancement_spot(self, spot, model, transport, taban, root=None):
        self.iz.append("WRITE")
        if self.readback_bozuk:
            model = copy.deepcopy(model)
            model["tanimlar"] = model["tanimlar"][:-1]
        self.belge = L.enhs_belgesi_kur(model).encode("utf-8")
        return {"ok": True, "put_status": 200, "hata": None, "lock_released": True, "gonderilen": None}

    def activate_enhancement_spot(self, spot):
        self.iz.append("ACT")
        return {"aktif": True, "dogrulanamadi": False, "worklist_sonda": "checked", "kalan_inaktif": [],
                "surumsuz_surum": "active", "aktivasyon": {"success": True}, "errors": []}


class RY_Araclar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="axet_enhs_"))
        cls._env = {k: os.environ.get(k) for k in ("AXET_SAP_PROJECT_DIR", "ADT_SAP_TIER")}
        os.environ.pop("ADT_SAP_TIER", None)
        from sapadt.tools import atom, badi
        cls.atom, cls.badi = atom, badi
        cls._eski = atom._get_client
        cls._n = 0

    @classmethod
    def tearDownClass(cls):
        cls.atom._get_client = cls._eski
        for k, v in cls._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(cls.root, ignore_errors=True)

    def setUp(self):
        type(self)._n += 1
        self.p = H.make_project(self.root, f"p{self._n}")
        os.environ["AXET_SAP_PROJECT_DIR"] = str(self.p)

    def adt(self, **kw):
        a = _SahteAdt(**kw)
        self.atom._get_client = lambda: a
        return a

    def test_R1_okuma_ve_kayit(self):
        self.adt()
        r = self.badi.adt_badi_spot_read(SPOT.lower())
        ok = (r.get("ok") is True and r.get("exists") is True and r.get("writable") is True
              and r.get("standard") is False and len(r.get("definitions") or []) == 1 and r.get("pull_state") == "kaydedildi")
        H.kaydet("ENHS R1 okuma + pull kaydı", "writable · 1 tanım · kaydedildi",
                 f"{r.get('writable')} {len(r.get('definitions') or [])} {r.get('pull_state')}", ok)
        self.assertTrue(ok, r)

    def test_R2_standart_ve_yok(self):
        self.adt(belge=_std(READBACK))
        r1 = self.badi.adt_badi_spot_read(SPOT)
        self.adt(belge=None)
        r2 = self.badi.adt_badi_spot_read(SPOT)
        ok = r1.get("standard") is True and r1.get("writable") is False and r2.get("exists") is False and r2.get("ok") is True
        H.kaydet("ENHS R2 standart spot okunur ama yazılamaz · yok", "standard · writable=false · exists=false",
                 f"{r1.get('standard')} {r1.get('writable')} {r2.get('exists')}", ok)
        self.assertTrue(ok)

    def test_Y1_kayit_yok_red(self):
        a = self.adt()
        r = self.badi.adt_badi_spot_write(SPOT, "DEVK900001", definitions=[{"badi": BADI, "shorttext": "Y"}])
        ok = r.get("error") == "pull_before_edit_missing" and "WRITE" not in a.iz
        H.kaydet("ENHS Y1 kayıt yok → red", "pull_before_edit_missing · WRITE yok", f"{r.get('error')} {a.iz}", ok)
        self.assertTrue(ok)

    def test_Y2_canli_degisti_red(self):
        a = self.adt()
        self.badi.adt_badi_spot_read(SPOT)
        a.belge = READBACK.replace("Ülke (güncel)".encode("utf-8"), "Ülke (başkası)".encode("utf-8"))
        r = self.badi.adt_badi_spot_write(SPOT, "DEVK900001", definitions=[{"badi": BADI, "shorttext": "Y"}])
        ok = r.get("error") == "source_changed_since_pull" and "WRITE" not in a.iz
        H.kaydet("ENHS Y2 okumadan sonra değişti → red", "source_changed_since_pull", f"{r.get('error')} {a.iz}", ok)
        self.assertTrue(ok)

    def test_Y3_standart_badi_adi_agsiz_red(self):
        a = self.adt()
        r1 = self.badi.adt_badi_spot_write(SPOT, "DEVK900001", definitions=[{"badi": "BADI_STANDART", "shorttext": "Y"}])
        r2 = self.badi.adt_badi_spot_write("ES_STANDART", "DEVK900001", remove_badis=[BADI])
        r3 = self.badi.adt_badi_spot_write(SPOT, "", definitions=[{"badi": BADI, "shorttext": "Y"}])
        ok = (r1.get("code") == "ADR_0005_A" and r2.get("code") == "ADR_0005_A" and r3.get("code") == "ADR_0005_C"
              and a.iz == [])
        H.kaydet("ENHS Y3 standart BAdI/spot adı · transportsuz → ağsız red", "A · A · C · iz=[]",
                 f"{r1.get('code')} {r2.get('code')} {r3.get('code')} {a.iz}", ok)
        self.assertTrue(ok)

    def test_Y4_standart_spot_canlida_red(self):
        a = self.adt(belge=_std(READBACK))
        self.badi.adt_badi_spot_read(SPOT)
        r = self.badi.adt_badi_spot_write(SPOT, "DEVK900001", definitions=[{"badi": BADI, "shorttext": "Y"}])
        ok = r.get("code") == "ADR_0005_A" and "WRITE" not in a.iz
        H.kaydet("ENHS Y4 masterSystem=SAP → red", "ADR_0005_A · WRITE yok", f"{r.get('code')} {a.iz}", ok)
        self.assertTrue(ok)

    def test_Y5_mutlu_yol(self):
        a = self.adt()
        self.badi.adt_badi_spot_read(SPOT)
        r = self.badi.adt_badi_spot_write(SPOT, "DEVK900001", definitions=[
            {"badi": BADI, "shorttext": "Güncel metin"},
            {"badi": "ZSD001_BADI_B", "interface": "ZIF_SD001_BADI_B", "shorttext": "İkinci"}])
        okunan = L.enhs_belgesi_ayristir(a.belge)
        adlar = [t["name"] for t in okunan["tanimlar"]]
        ok = (r.get("ok") is True and r.get("activated") is True and r.get("readback_verified") is True
              and adlar == [BADI, "ZSD001_BADI_B"] and a.iz.index("WRITE") < a.iz.index("ACT")
              and r.get("pull_state") == "guncellendi")
        H.kaydet("ENHS Y5 ekle+güncelle → yaz → aktive → readback", "ok · canlı tanım önce, yeni sonda",
                 f"{r.get('ok')} {r.get('error')} {adlar} {a.iz}", ok)
        self.assertTrue(ok, r)
        r2 = self.badi.adt_badi_spot_write(SPOT, "DEVK900001", remove_badis=["ZSD001_BADI_B"])
        adlar2 = [t["name"] for t in L.enhs_belgesi_ayristir(a.belge)["tanimlar"]]
        self.assertTrue(r2.get("ok") is True and adlar2 == [BADI], (r2, adlar2))

    def test_Y6_readback_farki(self):
        a = self.adt(readback_bozuk=True)
        self.badi.adt_badi_spot_read(SPOT)
        r = self.badi.adt_badi_spot_write(SPOT, "DEVK900001", definitions=[
            {"badi": "ZSD001_BADI_B", "interface": "ZIF_SD001_BADI_B", "shorttext": "İkinci"}])
        ok = r.get("ok") is False and r.get("readback_verified") is False and r.get("error") == "readback_mismatch"
        H.kaydet("ENHS Y6 sunucu tanımı düşürürse", "ok:false · readback_mismatch", f"{r.get('ok')} {r.get('error')}", ok)
        self.assertTrue(ok)

    def test_Y7_ilk_yaratim(self):
        a = self.adt(belge=None)
        r0 = self.badi.adt_badi_spot_write("ZSD001_ES_YENI", "DEVK900001", definitions=[{"badi": BADI}])
        r = self.badi.adt_badi_spot_write("ZSD001_ES_YENI", "DEVK900001", package="ZSD001", description="Yeni nokta",
                                          definitions=[{"badi": BADI, "interface": "ZIF_SD001_BADI_A",
                                                        "shorttext": "İlk"}])
        ok = (r0.get("error") == "spot_not_found" and r.get("ok") is True and r.get("created") is True
              and a.iz.count("CREATE") == 1 and a.iz.index("CREATE") < a.iz.index("WRITE"))
        H.kaydet("ENHS Y7 ilk yaratım", "paketsiz red · kabuk→yaz→aktive", f"{r0.get('error')} {r.get('ok')} {a.iz}", ok)
        self.assertTrue(ok, r)

    def test_A1_atc_kapsam_disi(self):
        from sapadt.tools import query
        import object_types as OT
        eski = query._get_client
        cagri = []
        query._get_client = lambda: cagri.append("client") or None
        try:
            r = query.adt_atc_check(SPOT, "enhs")
        finally:
            query._get_client = eski
        with self.assertRaises(ValueError):
            OT.get_object_url(SPOT, "enhs")                       # işlem bildirmeyen çağıran: fail-closed
        url = OT.get_object_url(SPOT, "enhs", islem="silme")
        ok = (r.get("error") == "atc_kapsam_disi" and r.get("finding_count") is None and cagri == []
              and url == "/sap/bc/adt/enhancements/enhsxsb/zsd001_es_badi_a")
        H.kaydet("ENHS A1 ATC kapsam dışı · işlem-izinli URL", "atc_kapsam_disi · istek yok · silme URL'i",
                 f"{r.get('error')} {cagri} {url}", ok)
        self.assertTrue(ok)

    def test_Y8_dry_run_yazmaz(self):
        a = self.adt()
        self.badi.adt_badi_spot_read(SPOT)
        r = self.badi.adt_badi_spot_write(SPOT, "DEVK900001", definitions=[{"badi": BADI, "shorttext": "D"}],
                                          dry_run=True)
        ok = r.get("ok") is True and r.get("dry_run") is True and "WRITE" not in a.iz and "ACT" not in a.iz
        H.kaydet("ENHS Y8 dry_run", "belge döner · yazma yok", f"{a.iz}", ok)
        self.assertTrue(ok)


# ─────────────────────────── G — yazma kapısı ───────────────────────────
class G_Kapi(unittest.TestCase):
    def test_G1_sinif_ve_transport(self):
        from sapadt import gate
        ok = (gate.tool_class("adt_badi_spot_write") == "write" and gate.tool_class("adt_badi_spot_read") == "read"
              and gate.transport_gerekli("adt_badi_spot_write", {}) is True)
        H.kaydet("ENHS G1 kapı sınıfı", "write · read · transport zorunlu", str(ok), ok)
        self.assertTrue(ok)

    def test_G2_standart_adlar_kapida_red(self):
        from sapadt import gate
        t = "adt_badi_spot_write"

        def isim(ad, args):
            return gate.check_names(t, ad, None, (), gate.arg_adlari(t, args))
        r_spot = isim("ES_STANDART", {"definitions": [{"badi": BADI}]})
        r_badi = isim(SPOT, {"definitions": [{"badi": "BADI_STANDART"}]})
        r_kaldir = isim(SPOT, {"remove_badis": ["BADI_STANDART"]})
        r_eksik = isim(SPOT, {"definitions": [{"shorttext": "adsız"}]})
        r_bicim = isim(SPOT, {"definitions": "ZSD001_BADI_A"})
        r_ok = isim(SPOT, {"definitions": [{"badi": BADI}], "remove_badis": ["ZSD001_BADI_B"]})
        kodlar = [r and r[0] for r in (r_spot, r_badi, r_kaldir, r_eksik, r_bicim)]
        ok = kodlar == ["ADR_0005_A"] * 5 and r_ok is None
        H.kaydet("ENHS G2 kapı ad denetimi", "standart spot/BAdI/kaldırma/adsız/biçimsiz RED · müşteri geçer",
                 f"{kodlar} {r_ok}", ok)
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
