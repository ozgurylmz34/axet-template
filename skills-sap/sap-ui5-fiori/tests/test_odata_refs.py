#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_ui_odata_refs.py (çevrimdışı $metadata): temiz, kırmızı, kısmi ölçüm, ölçüm yok."""
from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
