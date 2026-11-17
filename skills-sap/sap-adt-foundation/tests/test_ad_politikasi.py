# -*- coding: utf-8 -*-
"""Müşteri ad politikası (`lib/utils/ad_politikasi.py`, ADR 0005 A-EK) — birim + kapı (CLI alt süreç) testleri.

Sözleşme (kaynak çekirdek fixture'ları q393_namespace_ad_politikasi · validator_ad_grameri · namespace_tesisat'tan
aXet düzenine çevrildi):
  · Z/Y (+ENQU için E+Z/Y) her zaman müşteri adıdır; `/<NS>/` YALNIZ `sap-project.json` `customer_namespaces` ile
    bildirilmişse müşteri adıdır.
  · FAIL-CLOSED: liste değil / geçersiz öğe / mükerrer anahtar / bozuk JSON / `.conn_adt` yok / açık kök bağlantı
    dizininden farklı ⇒ namespace kabulü KAPALI (Z/Y etkilenmez).
  · Namespace kabulü bir GEVŞETMEDİR ⇒ negatif kontroller: bildirimsiz `/ABC/` RED · standart ad RED · transport
    zorunluluğu ve paket yasağı aynen · transport yaratan/release eden araç yok.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest import mock

import _helpers as H

sys.dont_write_bytecode = True
if str(H.SCRIPTS) not in sys.path:
    sys.path.insert(0, str(H.SCRIPTS))

import sapadt  # noqa: E402,F401  (lib/ dizinini sys.path'e ekler)
from sapadt.guardrails import GuardrailViolation, reject_standard_delete, require_customer_namespace  # noqa: E402
from utils import ad_politikasi as ap  # noqa: E402


def _yaz_proje(kok: Path, icerik) -> None:
    metin = icerik if isinstance(icerik, str) else json.dumps(icerik)
    (kok / "sap-project.json").write_text(metin, encoding="utf-8")


class _Ortam(unittest.TestCase):
    """Her testte temiz proje kökü: `.conn_adt` + `sap-project.json`; env bu köke; süreçte yüklü `sap_adt_lib` yok."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="axet_adpol_")
        self.kok = Path(self._tmp.name).resolve()
        (self.kok / ".conn_adt").write_text("ADT_SAP_URL=http://127.0.0.1:9\n", encoding="utf-8")
        self._yamalar = [mock.patch.dict(os.environ, {"AXET_SAP_PROJECT_DIR": str(self.kok)}),
                         mock.patch.dict(sys.modules)]
        for y in self._yamalar:
            y.start()
        sys.modules.pop("sap_adt_lib", None)
        ap._ONBELLEK.clear()

    def tearDown(self):
        for y in reversed(self._yamalar):
            y.stop()
        ap._ONBELLEK.clear()
        self._tmp.cleanup()

    def liste(self, ns, **ek):
        _yaz_proje(self.kok, {**H.SAP_PROJECT_OK, "customer_namespaces": ns, **ek})


class Karar(_Ortam):
    def test_zy_ve_kilit_yapilandirmasiz(self):
        _yaz_proje(self.kok, H.SAP_PROJECT_OK)
        for ad, tip, bek in (("ZCL_X", None, True), ("ycl_x", None, True), ("EZDEMO_LOCK", "enqu", True),
                             ("EZDEMO_LOCK", None, False), ("MARA", None, False), ("ZFOO\n", None, False),
                             ("", None, False), ("Z-X", None, False), ("/NSPC/X", None, False)):
            with self.subTest(ad=ad, tip=tip):
                self.assertEqual(ap.musteri_adi_mi(ad, tip), bek)
        H.kaydet("AP Z/Y + ENQU E+Z/Y kabul · MARA/`ZFOO\\n`/bildirimsiz NS red", "9 vaka", "eşit", True)

    def test_bildirilmis_namespace(self):
        self.liste(["/NSPC/"])
        for ad, bek in (("/NSPC/CL_X", True), ("/nspc/cl_x", True), ("/NSPC/", False), ("/NSPC/X-Y", False),
                        ("/NSPC/Xı", False), ("/ABC/CL_X", False), ("/SCWM/ORDIM_O", False), ("ZCL_X", True),
                        ("/NSPC/X\n", False)):
            with self.subTest(ad=ad):
                self.assertEqual(ap.musteri_adi_mi(ad), bek)
        self.assertTrue(ap.musteri_adi_mi("/NSPC/ELOCK", "enqu"))
        self.assertFalse(ap.musteri_adi_mi("E/NSPC/LOCK", "enqu"))
        H.kaydet("AP bildirilmiş /NSPC/ kabul · gövdesiz/bozuk/Unicode/başka NS red", "11 vaka", "eşit", True)

    def test_red_gerekcesi(self):
        self.liste(["/NSPC/"])
        self.assertIn("bildirilmemiş", ap.red_gerekcesi("/ABC/X"))
        self.assertIn("namespace'ten sonraki ad geçersiz", ap.red_gerekcesi("/NSPC/X-Y"))
        self.assertIn("biçimi tanınmadı", ap.red_gerekcesi("/AB/X"))
        self.assertEqual(ap.red_gerekcesi("MARA"), "")
        self.assertIn("MSYS_NO_PATHCONV", ap.musteri_adi_red_metni("C:/Program Files/Git/NS/PROG"))

    def test_musteri_karari_dort_sonuc(self):
        self.liste(["/NSPC/"])
        self.assertEqual(ap.musteri_karari("/NSPC/X"), "musteri")
        self.assertEqual(ap.musteri_karari("MARA"), "standart")
        self.assertEqual(ap.musteri_karari("/SCWM/X"), "namespace-kayitsiz")
        self.assertEqual(ap.musteri_karari("/AB/X"), "ad-cozulemedi")
        self.assertEqual(ap.musteri_govdesi("/NSPC/SD001_CLC"), ("/NSPC/", "SD001_CLC"))
        self.assertEqual(ap.musteri_govdesi("ZSD001"), ("Z", "SD001"))
        self.assertIsNone(ap.musteri_govdesi("/SCWM/X"))

    def test_namespaces_parametresi_projeyi_okumaz(self):
        self.liste([])
        self.assertTrue(ap.musteri_adi_mi("/NSPC/X", namespaces=["/nspc/"]))
        self.assertFalse(ap.musteri_adi_mi("/NSPC/X"))


class FailClosed(_Ortam):
    def _kapali(self, ad_metni: str, beklenen_parca: str):
        ns, hatalar = ap.namespace_yapilandirmasi()
        ok = ns == () and any(beklenen_parca in h for h in hatalar) and not ap.musteri_adi_mi("/NSPC/X")
        H.kaydet(f"AP fail-closed: {ad_metni}", "liste kapalı + görünür hata", f"ns={ns} hata={hatalar[:1]}", ok)
        self.assertTrue(ok, (ns, hatalar))
        self.assertTrue(ap.musteri_adi_mi("ZCL_X"), "Z/Y etkilenmemeli")
        self.assertIn(beklenen_parca, ap.red_gerekcesi("/NSPC/X"))

    def test_liste_degil(self):
        self.liste("/NSPC/")
        self._kapali("değer liste değil", "LİSTE olmalı")

    def test_gecersiz_oge_tum_listeyi_kapatir(self):
        for kotu in ("/AB/", "/___/", "/NSPCÇ/", "NSPC", "/TOOLONG123/", 123):
            with self.subTest(kotu=kotu):
                ap._ONBELLEK.clear()
                self.liste(["/NSPC/", kotu])
                self._kapali(f"geçersiz öğe {kotu!r}", "öğesi geçersiz")

    def test_mukerrer_anahtar(self):
        _yaz_proje(self.kok, '{"sap_profile": "s4_private", "master_language": "TR", '
                             '"customer_namespaces": ["/NSPC/"], "customer_namespaces": ["/NSPC/"]}')
        self._kapali("anahtar iki kez", "2 kez tanımlı")

    def test_ic_nesnedeki_ayni_ad_mukerrer_sayilmaz(self):
        _yaz_proje(self.kok, '{"x": {"customer_namespaces": 1}, "sap_profile": "s4_private", '
                             '"master_language": "TR", "customer_namespaces": ["/NSPC/"]}')
        self.assertEqual(ap.musteri_namespaceleri(), ("/NSPC/",))

    def test_bozuk_json(self):
        _yaz_proje(self.kok, '{"customer_namespaces": ["/NSPC/"]')
        self._kapali("bozuk JSON", "okunamadı")

    def test_baglanti_dosyasi_yok(self):
        self.liste(["/NSPC/"])
        (self.kok / ".conn_adt").unlink()
        self._kapali(".conn_adt yok", "bağlantı dosyası")

    def test_acik_kok_baglantidan_farkli(self):
        self.liste(["/NSPC/"])
        baska = self.kok / "baska"
        baska.mkdir()
        _yaz_proje(baska, {**H.SAP_PROJECT_OK, "customer_namespaces": ["/NSPC/"]})
        self.assertFalse(ap.musteri_adi_mi("/NSPC/X", root=baska))
        self.assertTrue(ap.musteri_adi_mi("/NSPC/X", root=self.kok))
        H.kaydet("AP açık kök ≠ bağlantı dizini → kapalı · eşit kök → açık", "False/True", "eşit", True)

    def test_yukleyici_baglantisi_onceliklidir(self):
        """Süreçte `sap_adt_lib` yüklüyse liste ONUN bağlantı dosyasının projesinden okunur (env değil)."""
        self.liste([])                                    # env'deki proje: liste boş
        diger = self.kok / "diger"
        diger.mkdir()
        (diger / ".conn_adt").write_text("ADT_SAP_URL=http://127.0.0.1:9\n", encoding="utf-8")
        _yaz_proje(diger, {**H.SAP_PROJECT_OK, "customer_namespaces": ["/NSPC/"]})
        sahte = types.SimpleNamespace(get_conn_path=lambda: diger / ".conn_adt")
        with mock.patch.dict(sys.modules, {"sap_adt_lib": sahte}):
            self.assertTrue(ap.musteri_adi_mi("/NSPC/X"))
            self.assertFalse(ap.musteri_adi_mi("/NSPC/X", root=self.kok))
        self.assertFalse(ap.musteri_adi_mi("/NSPC/X"))

    def test_ortam_degiskeni_listeyi_genisletmez(self):
        self.liste([])
        with mock.patch.dict(os.environ, {"AXET_CUSTOMER_NAMESPACES": "/NSPC/", "CUSTOMER_NAMESPACES": "/NSPC/",
                                          "IX_CUSTOMER_NAMESPACES": "/NSPC/"}):
            self.assertFalse(ap.musteri_adi_mi("/NSPC/X"))

    def test_dosya_degisince_yeniden_okunur(self):
        self.liste(["/NSPC/"])
        self.assertTrue(ap.musteri_adi_mi("/NSPC/X"))
        time.sleep(0.02)
        self.liste([], aciklama="liste boşaltıldı — boyut değişsin")
        self.assertFalse(ap.musteri_adi_mi("/NSPC/X"))
        H.kaydet("AP önbellek: liste boşaltılınca kabul hemen kapanır", "True→False", "eşit", True)


class Guardrails(_Ortam):
    def test_yaratma_ve_silme(self):
        self.liste(["/NSPC/"])
        require_customer_namespace("/NSPC/CL_X", what="class")
        reject_standard_delete("/NSPC/CL_X", "class")
        for ad in ("/ABC/CL_X", "MARA", "/SCWM/X"):
            with self.subTest(ad=ad):
                with self.assertRaises(GuardrailViolation) as c1:
                    require_customer_namespace(ad, what="class")
                self.assertEqual(c1.exception.code, "ADR_0005_A")
                with self.assertRaises(GuardrailViolation) as c2:
                    reject_standard_delete(ad, "class")
                self.assertEqual(c2.exception.code, "ADR_0005_A")
        with self.assertRaises(GuardrailViolation) as c3:
            require_customer_namespace("/ABC/CL_X", what="class")
        self.assertIn("bildirilmemiş", str(c3.exception))
        with self.assertRaises(GuardrailViolation):
            require_customer_namespace("/NSPC/CL_X", what="class", root=self.kok / "yok")
        H.kaydet("AP guardrails: bildirilmiş NS geçer · /ABC/ MARA /SCWM/ yaratma+silme RED", "ADR_0005_A",
                 "ADR_0005_A", True)


class Yuklayici(_Ortam):
    """`sap_adt_lib` ad/paket doğrulaması ad politikasına bağlı (yükleyici modül gerçek, ağ yok)."""

    def setUp(self):
        super().setUp()
        import sap_adt_lib as lib  # noqa: PLC0415 — setUp'taki sys.modules yaması sonunda geri alınır
        self.lib = lib
        y = mock.patch.object(lib, "conn_path", self.kok / ".conn_adt")
        y.start()
        self.addCleanup(y.stop)
        y2 = mock.patch.object(lib, "_explicit_working_dir", None)
        y2.start()
        self.addCleanup(y2.stop)

    def test_validate_object_name(self):
        self.liste(["/NSPC/"])
        v = self.lib.validate_object_name
        self.assertTrue(v("/NSPC/CL_X", "class"))
        self.assertTrue(v("/NSPC/X_TAB", "table"))
        self.assertTrue(v("ZCL_X", "class"))
        for ad, tip in (("/ABC/CL_X", "class"), ("/NSPC/CLX", "class"), ("MARA", "table"), ("/NSPC/", "table")):
            with self.subTest(ad=ad):
                with self.assertRaises(self.lib.SAPValidationError):
                    v(ad, tip)

    def test_validate_package_name(self):
        self.liste(["/NSPC/"])
        self.assertTrue(self.lib.validate_package_name("/NSPC/SD001"))
        self.assertTrue(self.lib.validate_package_name("ZSD001_CLC"))
        with self.assertRaises(self.lib.SAPValidationError):
            self.lib.validate_package_name("/ABC/SD001")

    def test_istemci_ad_dogrulamasi_ve_referans(self):
        self.liste(["/NSPC/"])
        istemci = self.lib.SAPADTClient.__new__(self.lib.SAPADTClient)
        istemci._validate_object_name("/NSPC/X_STR", "Structure")
        with self.assertRaises(self.lib.SAPValidationError):
            istemci._validate_object_name("/SCWM/X_STR", "Structure")
        istemci._validate_object_name("/SCWM/X_STR", "Referenced Structure", referans=True)
        with self.assertRaises(self.lib.SAPValidationError):
            istemci._validate_object_name("/AB/X", "Referenced Structure", referans=True)


class AdresVeDosya(unittest.TestCase):
    def test_url_segmenti(self):
        for ad in ("ZSD001_T01", "ZCL_X", "zsd_i_view"):
            self.assertEqual(ap.url_segmenti(ad), ad.lower())          # Z/Y: eski `ad.lower()` ile bayt bayt aynı
        self.assertEqual(ap.url_segmenti("/NS/X"), "%2Fns%2Fx")
        self.assertEqual(ap.url_segmenti("%2Fns%2Fx"), "%2Fns%2Fx")     # idempotent
        self.assertEqual(ap.url_segmenti("%2fNS%2fX"), "%2Fns%2Fx")
        self.assertEqual(ap.url_parcasindan_ad("%2fns%2fx"), "/NS/X")
        self.assertEqual(ap.url_adi("/sap/bc/adt/oo/classes/%2fns%2fcl_x/source/main"), "/NS/CL_X")
        self.assertEqual(ap.url_adi("/sap/bc/adt/oo/classes/zcl_x?version=active"), "ZCL_X")
        self.assertEqual(ap.url_adi(""), "")
        H.kaydet("AP url_segmenti: Z adı = lower() · /NS/X → %2Fns%2Fx · idempotent · ters", "eşit", "eşit", True)

    def test_dosya_adi(self):
        self.assertEqual(ap.dosya_adi("/NSPC/CL_X"), "#nspc#cl_x")
        self.assertEqual(ap.dosya_adi("ZCL_X"), "zcl_x")
        self.assertEqual(ap.dosya_adindan_ad("#ns#cl_x"), "/NS/CL_X")
        self.assertEqual(ap.dosya_adindan_ad("%23ns%23cl_x"), "/NS/CL_X")
        self.assertEqual(ap.dosya_adindan_ad("(ns)cl_x"), "/NS/CL_X")
        self.assertEqual(ap.dosya_adindan_ad(ap.dosya_adi("/NSPC/X_Y")), "/NSPC/X_Y")
        self.assertEqual(ap.yerel_ad("ZCL_X"), "ZCL_X")
        self.assertEqual(ap.yerel_ad("/NSPC/CL_X"), "#nspc#cl_x")
        for kotu in ("/AB/X", "A/B", "/NS/X/Y", "C:\\X"):
            with self.subTest(kotu=kotu):
                with self.assertRaises(ValueError):
                    ap.yerel_ad(kotu)

    def test_fugr_ve_odata(self):
        self.assertEqual(ap.fugr_include_oneki("ZFG"), "LZFG")
        self.assertEqual(ap.fugr_include_oneki("/NSPC/FG"), "/NSPC/LFG")
        self.assertEqual(ap.fugr_ana_program("zfg"), "SAPLZFG")
        self.assertEqual(ap.fugr_ana_program("/NSPC/FG"), "/NSPC/SAPLFG")
        self.assertEqual(ap.odata_servis_yolu("ZSD001_SRV"), "/sap/opu/odata/sap/ZSD001_SRV")
        self.assertEqual(ap.odata_servis_yolu("/NSPC/X_SRV"), "/sap/opu/odata/nspc/X_SRV")
        self.assertEqual(ap.odata_uri_servisi("/sap/opu/odata/nspc/X_SRV/"), "/NSPC/X_SRV")
        self.assertEqual(ap.odata_uri_servisi("/sap/opu/odata/sap/ZSD001_SRV"), "ZSD001_SRV")
        self.assertIsNone(ap.odata_uri_servisi("/sap/opu/odata/ab/X_SRV"))


class Gramer(unittest.TestCase):
    def test_ad_coz(self):
        for ad, bek in (("/NSPC/SD001_I_X", True), ("ZSD001_X", True), ("/AB/X", False), ("/NSPC/", False),
                        ("", False), (None, False), ("/NSPC/X/Y", False), ("/ABCDEFGHI/X", False)):
            with self.subTest(ad=ad):
                self.assertEqual(ap.ad_gecerli_mi(ad), bek)
                self.assertEqual(ap.ad_coz(ad), (ad, None) if bek else ("", "ad-cozulemedi"))

    def test_aday_yakalama_ve_gecis(self):
        m = re.search(r"define\s+view\s+entity\s+(" + ap.AD_ADAYI + ")", "define view entity /NSPC/SD001_I_X as")
        self.assertEqual(m.group(1), "/NSPC/SD001_I_X")
        m = re.search(r"from\s+(" + ap.AD_ADAYI + ")", "select from /AB/X {")
        self.assertEqual(m.group(1), "/AB/X")                     # gevşek: bozuk deneme de yakalanır
        self.assertEqual(ap.ad_coz(m.group(1))[1], "ad-cozulemedi")
        des = ap.ad_gecis_deseni("ZSD001_X")
        self.assertIsNone(re.search(des, "ZSD001_X_Y"))
        self.assertIsNotNone(re.search(des, "a ZSD001_X."))
        self.assertIsNone(re.search(ap.ad_gecis_deseni("/NS/X"), "/NS/X/Y"))
        H.kaydet("AP gramer: AD_ADAYI NS'li adı tam yakalar · bozuk ad ÖLÇÜLEMEDİ · sınır", "eşit", "eşit", True)


# ── Kapı (CLI alt süreç): namespace kabulü yalnız bildirimle; diğer yasaklar aynen ────────────────
ROOT: Path
HOME_OPT: Path
S1 = ["--sap-write", "--scope", "S1", "--reason", "Test gerekçesi: namespace kapı sözleşmesi"]
TR = "TESTK900001"


def setUpModule():
    global ROOT, HOME_OPT
    ROOT = Path(tempfile.mkdtemp(prefix="axet_adpol_cli_"))
    HOME_OPT = H.build_home(ROOT, optin=True)


def tearDownModule():
    shutil.rmtree(ROOT, ignore_errors=True)


_sayac = [0]


def _proje(ns_json) -> Path:
    _sayac[0] += 1
    sp = ns_json if isinstance(ns_json, str) else {**H.SAP_PROJECT_OK, "customer_namespaces": ns_json}
    return H.make_project(ROOT / "projeler", f"p{_sayac[0]}", sap_project=sp)


def _kabuk(ad, *, tip="class", transport=TR, package="ZAXET_PKG"):
    return ["adt_post_shell", "--args-json", json.dumps({"object_type": tip, "name": ad, "package": package,
                                                         "transport": transport, "description": "Test nesnesi"}), *S1]


class KapiNamespace(unittest.TestCase):
    def kos(self, ad, argv, project, *, code=None, not_code=None):
        rc, data, out, err = H.run_cli(HOME_OPT, argv, project=project)
        kod = ((data or {}).get("error") or {}).get("code") if data else "JSON-YOK"
        ok = data is not None and (code is None or kod == code) and (not_code is None or kod != not_code)
        H.kaydet(ad, f"{code or 'kod≠' + str(not_code)}", f"exit {rc} · {kod}", ok)
        self.assertTrue(ok, f"{ad}: exit {rc} kod {kod}\n{out[-1500:]}\n{err[-800:]}")
        return rc, data

    def test_bildirilmis_gecer_digerleri_red(self):
        p = _proje(["/NSPC/"])
        rc, _d = self.kos("AP-K1 bildirilmiş /NSPC/CL_X post_shell → ad kapısını geçer", _kabuk("/NSPC/CL_X"), p,
                          not_code="ADR_0005_A")
        self.assertNotEqual(rc, 0)   # sahte host: ağa gidildi → bağlantı hatası (kapı geçti, yazma olmadı)
        _rc, d = self.kos("AP-K2 bildirilmemiş /ABC/CL_X → ADR_0005_A", _kabuk("/ABC/CL_X"), p, code="ADR_0005_A")
        self.assertIn("bildirilmemiş", d["error"]["message"])
        self.kos("AP-K3 standart MARA (liste dolu) → ADR_0005_A", _kabuk("MARA", tip="tabl"), p, code="ADR_0005_A")
        self.kos("AP-K4 bildirilmiş NS ama transport yok (paket ≠ $TMP) → ADR_0005_C",
                 _kabuk("/NSPC/CL_Y", transport=""), p, code="ADR_0005_C")
        self.kos("AP-K5 bildirilmiş NS paket yaratma → ADR_0005_C (paket yasağı)",
                 _kabuk("/NSPC/PKG", tip="package"), p, code="ADR_0005_C")
        self.kos("AP-K6 silme /SCWM/X → ADR_0005_A", ["adt_delete", "--args-json",
                 json.dumps({"name": "/SCWM/X", "object_type": "tabl", "transport": TR}), *S1], p, code="ADR_0005_A")
        self.kos("AP-K7 silme bildirilmiş /NSPC/X → ad kapısını geçer", ["adt_delete", "--args-json",
                 json.dumps({"name": "/NSPC/X", "object_type": "tabl", "transport": TR}), *S1], p,
                 not_code="ADR_0005_A")

    def test_bildirimsiz_proje_namespace_red(self):
        p = _proje([])
        self.kos("AP-K8 liste boş → /NSPC/CL_X ADR_0005_A", _kabuk("/NSPC/CL_X"), p, code="ADR_0005_A")
        p2 = _proje(json.dumps(H.SAP_PROJECT_OK)[:-1] + ', "customer_namespaces": ["/NSPC/"], '
                    '"customer_namespaces": ["/NSPC/"]}')
        _rc, d = self.kos("AP-K9 mükerrer anahtar → kapalı ADR_0005_A", _kabuk("/NSPC/CL_X"), p2, code="ADR_0005_A")
        self.assertIn("2 kez", d["error"]["message"])
        p3 = _proje(["/NSPC/", "/AB/"])
        self.kos("AP-K10 bir öğe geçersiz → tüm liste kapalı", _kabuk("/NSPC/CL_X"), p3, code="ADR_0005_A")

    def test_transport_yaratan_arac_yok(self):
        _rc, _d, out, _e = H.run_cli(HOME_OPT, ["--list"])
        adlar = {t["name"] for t in json.loads(out)["result"]["tools"]}
        yasak = {a for a in adlar if "transport" in a and a != "adt_transport_list"}
        H.kaydet("AP-K11 transport yaratan/release eden araç yok", "yalnız adt_transport_list", str(sorted(yasak)),
                 not yasak)
        self.assertEqual(yasak, set())


if __name__ == "__main__":
    unittest.main()
