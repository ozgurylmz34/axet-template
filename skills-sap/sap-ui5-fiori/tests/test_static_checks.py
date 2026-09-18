#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Statik validator'lar: pozitif (app_good → 0), negatif (app_bad → 1), ölçüm yok (boş klasör → 2)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import _helpers as H

GOOD = H.FIXTURES / "app_good"
BAD = H.FIXTURES / "app_bad"


class _Taban(unittest.TestCase):
    script = ""

    def kontrol(self, ad, yol, beklenen_rc, *args, icermeli=(), icermemeli=()):
        rc, out = H.kos(self.script, yol, *args)
        eksik = [s for s in icermeli if s not in out]
        fazla = [s for s in icermemeli if s in out]
        ok = rc == beklenen_rc and not eksik and not fazla and "KAPSAM:" in out
        H.kaydet(ad, f"rc={beklenen_rc}", f"rc={rc} eksik={eksik} fazla={fazla}", ok)
        self.assertTrue(ok, f"{ad}: rc={rc} eksik={eksik} fazla={fazla}\n{out}")
        return out


class TestTraps(_Taban):
    script = "check_ui5_freestyle_traps.py"

    def test_pozitif(self):
        self.kontrol("traps: app_good temiz (yorumlar bulgu üretmez)", GOOD, 0,
                     icermeli=("SONUÇ: T1-T4 bulgusu yok",), icermemeli=("[İHLAL]", "[UYARI]"))

    def test_negatif(self):
        self.kontrol("traps: app_bad T1+T4 ERROR, T2+T3 WARN", BAD, 1,
                     icermeli=("T1 V2 nav", "T2 Input type=Number", "T3 core:Title", "T4 <f:fields> içinde <HBox>",
                               "SONUÇ: 2 ERROR (T1/T4), 2 WARN (T2/T3)"))

    def test_olcum_yok(self):
        with tempfile.TemporaryDirectory() as d:
            self.kontrol("traps: webapp'siz klasör → ÖLÇÜM YOK", d, 2, icermeli=("ÖLÇÜM YOK",))


class TestGrid(_Taban):
    script = "check_list_view_grid.py"

    def test_pozitif(self):
        self.kontrol("grid: app_good sap.ui.table → ihlal yok", GOOD, 0, icermemeli=("[İHLAL]",))

    def test_negatif(self):
        self.kontrol("grid: app_bad liste görünümü sap.m.Table → ihlal", BAD, 1,
                     icermeli=("OrderList.view.xml", "sap.m.Table kullanıyor", "SONUÇ: 1 ihlal."))

    def test_olcum_yok(self):
        with tempfile.TemporaryDirectory() as d:
            self.kontrol("grid: boş klasör → ÖLÇÜM YOK", d, 2, icermeli=("ÖLÇÜM YOK",))


class TestFilter(_Taban):
    script = "check_filter_search_pattern.py"

    def test_pozitif(self):
        self.kontrol("filter: app_good MultiInput, bayraksız Contains", GOOD, 0,
                     icermeli=("SONUÇ: 0 BLOCKER, 0 WARNING.",))

    def test_negatif(self):
        self.kontrol("filter: app_bad caseSensitive:false + tek Input VH", BAD, 1,
                     icermeli=("BLOCKER: caseSensitive:false", "WARNING: filtre ekranında value-help",
                               "SONUÇ: 1 BLOCKER, 1 WARNING."))


class TestI18n(_Taban):
    script = "check_i18n_keys.py"

    def test_pozitif(self):
        self.kontrol("i18n: app_good tüm anahtarlar iki dosyada", GOOD, 0, icermeli=("SONUÇ: 0 ERROR, 0 WARN.",))

    def test_negatif(self):
        self.kontrol("i18n: app_bad eksik anahtar + yer tutucu + kesme", BAD, 1,
                     icermeli=("'list.title' temel i18n.properties'te yok", "'list.title' i18n_tr.properties'de yok",
                               "'btn.save' i18n_tr.properties'de yok", "'msg.saved' yer tutucu kümesi farklı",
                               "'msg.del' (i18n.properties) yer tutuculu metinde tek kesme",
                               "SONUÇ: 3 ERROR, 2 WARN."))

    def test_locale_optional(self):
        self.kontrol("i18n: --locale-optional dil eksiği WARN'a iner", BAD, 1, "--locale-optional",
                     icermeli=("SONUÇ: 1 ERROR, 4 WARN.",))

    def test_olcum_yok(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "webapp").mkdir()
            self.kontrol("i18n: i18n klasörsüz webapp → ÖLÇÜM YOK", d, 2, icermeli=("ÖLÇÜM YOK",))


if __name__ == "__main__":
    unittest.main()
