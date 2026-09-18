# -*- coding: utf-8 -*-
"""sap_stamp.py — damga ↔ kanonik: güncel / sürüm farkı / elle değişiklik / bozuk işaret / kanonik bozuk."""
from __future__ import annotations

import re
from unittest import mock

from _helpers import GeciciTest  # önce: scripts/ yolunu ekler
import sap_stamp

TABAN = "# P — Proje\nPROJECT-ID: p\n\n## Proje kimliği\n- x\n"


class SapStampTest(GeciciTest):
    def damgali(self) -> str:
        metin, onceki = sap_stamp.damgala(TABAN)
        self.assertEqual(onceki, "yok")
        return metin

    def test_guncel(self):
        self.assertEqual(sap_stamp.denetle(self.damgali()), ("guncel", ""))
        self.assertEqual(sap_stamp.denetle(TABAN)[0], "yok")

    def test_kanonik_gercek_template_saglam(self):
        ok, bilgi = sap_stamp.kanonik_denetle()
        self.assertTrue(ok, bilgi)

    # --- negatif ---
    def test_elle_degisiklik(self):
        metin = self.damgali().replace("istisna yok", "istisna var", 1)
        st, ayrinti = sap_stamp.denetle(metin)
        self.assertEqual(st, "farkli")
        self.assertIn("elle", ayrinti)

    def test_surum_farki(self):
        metin = re.sub(r"SAP-STAMP-ID: \S+", "SAP-STAMP-ID: AXET-SAP-0.0.1", self.damgali())
        st, ayrinti = sap_stamp.denetle(metin)
        self.assertEqual(st, "farkli")
        self.assertIn("AXET-SAP-0.0.1", ayrinti)

    def test_ikinci_kopya_bozuk(self):
        metin = self.damgali()
        self.assertEqual(sap_stamp.durum(metin + "\n" + sap_stamp.kanonik_blok().replace("yok", "var") + "\n"), "guncel",
                         "kontrol grubu: eski durum() ikinci kopyayı görmüyordu")
        st, _ = sap_stamp.denetle(metin + "\n" + sap_stamp.kanonik_blok() + "\n")
        self.assertEqual(st, "bozuk")

    def test_yetim_isaret_bozuk(self):
        metin = self.damgali().replace(sap_stamp.BITIR, "")
        self.assertEqual(sap_stamp.denetle(metin)[0], "bozuk")
        metin = self.damgali().replace(sap_stamp.BASLA, "<!-- AXET-SAP-YASAKLAR:BASLA elle -->")
        self.assertEqual(sap_stamp.denetle(metin)[0], "bozuk")

    def test_kanonik_okunamazsa_istisna_yok(self):
        bozuk = self.yaz(self.tmp / "00-sap.md", "# SAP\nSAP-CORE-ID: X\n\n## Başka\n")
        with mock.patch.object(sap_stamp, "SAP_CORE", bozuk):
            self.assertEqual(sap_stamp.denetle(TABAN)[0], "kanonik_yok")
            self.assertFalse(sap_stamp.kanonik_denetle()[0])

    def test_kanonik_kategori_eksik(self):
        gercek = sap_stamp.SAP_CORE.read_text(encoding="utf-8")
        eksik = re.sub(r"^\| \*\*D — .*$\n", "", gercek, flags=re.M)
        self.assertNotEqual(gercek, eksik, "kategori D satırı bulunamadı — test kurulamadı")
        f = self.yaz(self.tmp / "00-sap.md", eksik)
        with mock.patch.object(sap_stamp, "SAP_CORE", f):
            ok, bilgi = sap_stamp.kanonik_denetle()
        self.assertFalse(ok)
        self.assertIn("D", bilgi)
