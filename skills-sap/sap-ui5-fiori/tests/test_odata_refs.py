#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_ui_odata_refs.py (çevrimdışı $metadata): temiz, kırmızı, kısmi ölçüm, ölçüm yok."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import _helpers as H

S = "check_ui_odata_refs.py"
GOOD = H.FIXTURES / "app_good"
BAD = H.FIXTURES / "app_bad"
MD = H.FIXTURES / "metadata_order.xml"
MD_VH = H.FIXTURES / "metadata_vh.xml"


class TestOdataRefs(unittest.TestCase):
    def kontrol(self, ad, beklenen_rc, args, icermeli=()):
        rc, out = H.kos(S, *args)
        eksik = [s for s in icermeli if s not in out]
        ok = rc == beklenen_rc and not eksik
        H.kaydet(ad, f"rc={beklenen_rc}", f"rc={rc} eksik={eksik}", ok)
        self.assertTrue(ok, f"{ad}: rc={rc} eksik={eksik}\n{out}")

    def test_pozitif_cok_servis(self):
        self.kontrol("odata: app_good + vh metadata → TEMİZ", 0,
                     ["--app", GOOD, "--metadata", MD, "--metadata-for", f"ZCA000_VH_O2={MD_VH}"],
                     icermeli=("[OK] ReleaseOrder", "[OK] CountryVHSet (servis ZCA000_VH_O2)", "TEMİZ (",
                               "BAKILMAYANLAR"))

    def test_ikincil_metadata_yok(self):
        self.kontrol("odata: vh metadata verilmedi → kısmi ÖLÇEMEDİM", 2, ["--app", GOOD, "--metadata", MD],
                     icermeli=("ÖLÇÜLEMEDİ: CountryVHSet", "ÖLÇEMEDİM (kısmi)"))

    def test_negatif(self):
        self.kontrol("odata: app_bad yanlış FI/entity/property → KIRMIZI", 1, ["--app", BAD, "--metadata", MD],
                     icermeli=("FUNC YOK: ReleaseOrders", "ENTITY SET YOK: OrdersSet", "property YOK: CustomerName",
                               "3 KIRMIZI uyumsuzluk"))

    def test_metadata_edmx_degil(self):
        with tempfile.TemporaryDirectory() as d:
            sahte = Path(d) / "login.html"
            sahte.write_text("<html><body>Logon</body></html>", encoding="utf-8")
            self.kontrol("odata: EDMX olmayan metadata → ÖLÇEMEDİM", 2, ["--app", GOOD, "--metadata", sahte],
                         icermeli=("içerik EDMX değil",))

    def test_app_yok(self):
        self.kontrol("odata: olmayan --app → exit 2", 2, ["--app", H.FIXTURES / "yok_app", "--metadata", MD],
                     icermeli=("--app yolu YOK",))


class TestNamespaceServis(unittest.TestCase):
    """`/<NS>/<AD>` servis kökü `/sap/opu/odata/<ns>/<AD>` (sap/ DEĞİL). Ana servis manifest'ten yalnız müşteri
    namespace'iyse seçilir (sap-project.json `customer_namespaces` + .conn_adt); sap/ yolu öncelikli. Negatif
    vakalarda manifest'te HİÇ sap/ yolu yoktur — sap/ yolu varsa (ikincil servis de olsa) o seçilir (önceki davranış)."""

    def _app(self, ana_uri, vh_uri):
        kok = Path(tempfile.mkdtemp(prefix="odatans_"))
        app = kok / "app"
        shutil.copytree(GOOD, app)
        m = app / "webapp" / "manifest.json"
        m.write_text(m.read_text(encoding="utf-8").replace("/sap/opu/odata/sap/ZXX001_UI_ORDER_O2/", ana_uri)
                     .replace("/sap/opu/odata/sap/ZCA000_VH_O2/", vh_uri), encoding="utf-8")
        proje = kok / "proje"
        proje.mkdir()
        (proje / "sap-project.json").write_text(json.dumps({"customer_namespaces": ["/NSPC/"]}), encoding="utf-8")
        return kok, app, proje

    def _kos(self, ad, beklenen_rc, ana_uri, vh_uri, ek=(), conn=True, proje_ver=True, icermeli=(),
             icermemeli=()):
        kok, app, proje = self._app(ana_uri, vh_uri)
        try:
            if conn:
                (proje / ".conn_adt").write_text("", encoding="utf-8")
            args = ["--app", app, "--metadata", MD, *ek] + (["--project-dir", proje] if proje_ver else [])
            rc, out = H.kos(S, *args)
        finally:
            shutil.rmtree(kok, ignore_errors=True)
        eksik = [x for x in icermeli if x not in out]
        fazla = [x for x in icermemeli if x in out]
        ok = rc == beklenen_rc and not eksik and not fazla
        H.kaydet(ad, f"rc={beklenen_rc}", f"rc={rc} eksik={eksik} fazla={fazla}", ok)
        self.assertTrue(ok, f"{ad}: rc={rc} eksik={eksik} fazla={fazla}\n{out}")

    def test_bildirilmis_namespace_ana_ve_ikincil(self):
        self._kos("odata: /nspc/ kökü → /NSPC/ ana + ikincil servis çözülür", 0,
                  "/sap/opu/odata/nspc/ZXX001_UI_ORDER_O2/", "/sap/opu/odata/nspc/ZCA000_VH_O2/",
                  ek=("--metadata-for", f"/NSPC/ZCA000_VH_O2={MD_VH}"),
                  icermeli=("[OK] ReleaseOrder", "(servis /NSPC/ZCA000_VH_O2)", "TEMİZ ("))

    def test_sap_yolu_oncelikli_namespace_ikincil(self):
        self._kos("odata: ana sap/ yolu korunur, ikincil /nspc/ haritada", 0,
                  "/sap/opu/odata/sap/ZXX001_UI_ORDER_O2/", "/sap/opu/odata/nspc/ZCA000_VH_O2/",
                  ek=("--metadata-for", f"/NSPC/ZCA000_VH_O2={MD_VH}"), proje_ver=False,
                  icermeli=("(servis /NSPC/ZCA000_VH_O2)", "TEMİZ ("))

    def test_sap_namespace_ana_servis_secilmez(self):
        self._kos("odata: bildirilmemiş /iwfnd/ kökü ana servis SEÇİLMEZ (negatif)", 2,
                  "/sap/opu/odata/iwfnd/ZXX001_UI_ORDER_O2/", "/sap/opu/odata/iwfnd/ZCA000_VH_O2/",
                  icermeli=("servis adı çözülemedi",))

    def test_baglanti_dosyasi_yoksa_secilmez(self):
        self._kos("odata: .conn_adt yok → /NSPC/ ana servis seçilmez (fail-closed)", 2,
                  "/sap/opu/odata/nspc/ZXX001_UI_ORDER_O2/", "/sap/opu/odata/nspc/ZCA000_VH_O2/", conn=False,
                  icermeli=("servis adı çözülemedi",))


if __name__ == "__main__":
    unittest.main()
