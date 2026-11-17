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

    def _onekli_app(self, d, en_ek, tr_ek):
        w = Path(d) / "webapp"
        (w / "i18n").mkdir(parents=True)
        (w / "util").mkdir()
        (w / "util" / "Pencere.js").write_text(
            'sap.ui.define([], function () {\n  return function (oB, sOp) { return oB.getText("kfp.op." + sOp); };\n});\n',
            encoding="utf-8")
        (w / "i18n" / "i18n.properties").write_text("app=A\n" + en_ek, encoding="utf-8")
        (w / "i18n" / "i18n_tr.properties").write_text("app=A\n" + tr_ek, encoding="utf-8")

    def test_dinamik_onek_var(self):
        """`getText("kfp.op." + sOp)` anahtar değil önektir: önekli anahtar iki dosyada varsa temiz."""
        with tempfile.TemporaryDirectory() as d:
            self._onekli_app(d, "kfp.op.EQ=Equals\n", "kfp.op.EQ=Eşittir\n")
            self.kontrol("i18n: dinamik önek `kfp.op.` iki dosyada var → temiz", d, 0,
                         icermeli=("SONUÇ: 0 ERROR, 0 WARN.",))

    def test_dinamik_onek_dil_dosyasinda_yok(self):
        with tempfile.TemporaryDirectory() as d:
            self._onekli_app(d, "kfp.op.EQ=Equals\n", "")
            self.kontrol("i18n: dinamik önek TR dosyasında yok → ERROR (negatif)", d, 1,
                         icermeli=("'kfp.op.*' önekli anahtar i18n_tr.properties'de yok", "SONUÇ: 1 ERROR, 0 WARN."))

    def test_noktali_anahtar_birlestirmesiz_onek_sayilmaz(self):
        """Noktayla biten anahtar YALNIZ JS'te `+` birleştirmesi görülünce önektir (aXet tur 8 bug-gate): XML
        `{i18n>list.}` ve JS `getText("btn.")` düz anahtardır — `list.title` var diye eksik `list.` örtülmez."""
        with tempfile.TemporaryDirectory() as d:
            w = Path(d) / "webapp"
            (w / "i18n").mkdir(parents=True)
            (w / "view").mkdir()
            (w / "view" / "Ana.view.xml").write_text(
                '<mvc:View xmlns:mvc="sap.ui.core.mvc" xmlns="sap.m"><Title text="{i18n>list.}"/></mvc:View>\n',
                encoding="utf-8")
            (w / "util").mkdir()
            (w / "util" / "Y.js").write_text(
                'sap.ui.define([], function () {\n  return function (oB) { return oB.getText("btn."); };\n});\n',
                encoding="utf-8")
            (w / "i18n" / "i18n.properties").write_text("list.title=L\nbtn.save=S\n", encoding="utf-8")
            (w / "i18n" / "i18n_tr.properties").write_text("list.title=L\nbtn.save=K\n", encoding="utf-8")
            self.kontrol("i18n: birleştirmesiz noktalı anahtar önek değil → ERROR", d, 1,
                         icermeli=("'list.' temel i18n.properties'te yok", "'btn.' temel i18n.properties'te yok"))


if __name__ == "__main__":
    unittest.main()
