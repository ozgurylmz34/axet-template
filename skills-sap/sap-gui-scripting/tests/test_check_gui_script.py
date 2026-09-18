#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_gui_script.py çevrimdışı testleri (stdlib unittest). SAP GUI'ye bağlanmaz, hiçbir script çalıştırmaz.

    python -m unittest discover -s <TEMPLATE>/skills-sap/sap-gui-scripting/tests -v

Pozitif kontrol: üç şablon BLOCKER'sız geçer; kontrol grubu satırları (yorum, karşılaştırma) bulgu üretmez.
Negatif kontrol: her BLOCKER kuralı en az bir örnekle tetiklenir; gerçek giriş noktası (komut satırı) çıkış kodu ölçülür.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
SKILL = Path(__file__).resolve().parents[1]
CHECKER = SKILL / "scripts" / "check_gui_script.py"
TEMPLATES = SKILL / "templates"

_spec = importlib.util.spec_from_file_location("check_gui_script", CHECKER)
C = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = C  # dataclass çözümlemesi modülü sys.modules'te arar
_spec.loader.exec_module(C)  # type: ignore[union-attr]

ATTACH_VBS = 'Set rot = GetObject("SAPGUI")\nSet app = rot.GetScriptingEngine\nSet ses = app.ActiveSession\n'


def vbs(body: str, mod: str = "okuma", geri: str = "yok", header: bool = True, attach: bool = True) -> str:
    h = f"' AXET-GUI-SCRIPT v1\n' MOD: {mod}\n' GERI-ALINAMAZ: {geri}\n" if header else ""
    return h + "Option Explicit\n" + (ATTACH_VBS if attach else "") + body + "\n"


class Base(unittest.TestCase):
    def scan(self, text: str, lang: str = "vbs", mode: str | None = None):
        return C.check_text(text, lang, mode)

    @staticmethod
    def rules(res, level: str) -> set[str]:
        return {f.rule for f in res.findings if f.level == level}


class TestTemplates(Base):
    def test_templates_have_no_blocker(self):
        files = sorted(TEMPLATES.glob("*.vbs"))
        self.assertEqual(len(files), 3, files)
        for f in files:
            res = C.check_file(f)
            with self.subTest(template=f.name):
                self.assertEqual(res.mode, "okuma")
                self.assertEqual(self.rules(res, "BLOCKER"), set(), [x for x in res.findings if x.level == "BLOCKER"])
                self.assertEqual(self.rules(res, "WARN"), set(), [x for x in res.findings if x.level == "WARN"])

    def test_scroll_templates_report_info(self):
        for name in ("dump-alv-grid.vbs", "dump-table-control.vbs"):
            with self.subTest(template=name):
                self.assertIn("KAYDIRMA", self.rules(C.check_file(TEMPLATES / name), "INFO"))


class TestYasaklar(Base):
    def test_sm12_okcode(self):
        res = self.scan(vbs('ses.findById("wnd[0]/tbar[0]/okcd").Text = "/nSM12"', mod="akis", geri="yok"))
        self.assertIn("YASAK_C", self.rules(res, "BLOCKER"))

    def test_se09_start_transaction(self):
        res = self.scan(vbs('ses.StartTransaction "SE09"', mod="akis", geri="release"))
        self.assertIn("YASAK_C", self.rules(res, "BLOCKER"))

    def test_se80(self):
        res = self.scan(vbs('ses.SendCommand "/nse80"', mod="akis", geri="yok"))
        self.assertIn("YASAK_C", self.rules(res, "BLOCKER"))

    def test_concatenated_tcode(self):
        res = self.scan(vbs('ses.StartTransaction "SM" & "12"', mod="akis", geri="yok"))
        self.assertIn("YASAK_C", self.rules(res, "BLOCKER"))

    def test_variable_tcode(self):
        res = self.scan(vbs('tc = "STMS"\nses.StartTransaction tc', mod="akis", geri="yok"))
        self.assertIn("YASAK_C", self.rules(res, "BLOCKER"))

    def test_se16n_sap_edit(self):
        res = self.scan(vbs('ses.StartTransaction "SE16N"\nses.findById("wnd[0]/tbar[0]/okcd").Text = "&SAP_EDIT"',
                            mod="akis", geri="yok"))
        self.assertIn("YASAK_B", self.rules(res, "BLOCKER"))
        self.assertIn("TABLO_GORUNTU", self.rules(res, "WARN"))

    def test_sm30(self):
        res = self.scan(vbs('ses.StartTransaction "SM30"', mod="akis", geri="yok"))
        self.assertIn("YASAK_B", self.rules(res, "BLOCKER"))

    def test_comment_mention_is_not_a_finding(self):
        res = self.scan(vbs("' Bu script SM12 ya da SE09 kullanmaz\nDim x"))
        self.assertEqual(self.rules(res, "BLOCKER"), set())


class TestKimlikVeBaglanti(Base):
    def test_password_variable(self):
        res = self.scan(vbs('pwd = "Gizli123"'))
        self.assertIn("KIMLIK", self.rules(res, "BLOCKER"))

    def test_password_field_fill(self):
        res = self.scan(vbs('ses.findById("wnd[0]/usr/pwdRSYST-BCODE").text = "abc"', mod="akis", geri="yok"))
        self.assertIn("KIMLIK", self.rules(res, "BLOCKER"))

    def test_user_variable(self):
        res = self.scan(vbs('userName = "DEVUSER01"'))
        self.assertIn("KIMLIK", self.rules(res, "BLOCKER"))

    def test_open_connection(self):
        res = self.scan(vbs('Set con = app.OpenConnection("DEV", True)'))
        self.assertIn("BAGLANTI", self.rules(res, "BLOCKER"))

    def test_ip_literal(self):
        # 192.0.2.x = RFC 5737 belgeleme aralığı (gerçek sistem adresi değil)
        res = self.scan(vbs('x = "/H/192.0.2.10/S/3299"'))
        self.assertIn("BAGLANTI", self.rules(res, "BLOCKER"))

    def test_missing_attach(self):
        res = self.scan(vbs("Dim x", attach=False))
        self.assertIn("BAGLANMA", self.rules(res, "BLOCKER"))

    def test_identity_read_warns(self):
        res = self.scan(vbs('OutLine ses.Info.User & ses.Info.SystemName'))
        self.assertIn("KIMLIK_OKU", self.rules(res, "WARN"))
        self.assertEqual(self.rules(res, "BLOCKER"), set())

    def test_chr_obfuscation_warns(self):
        res = self.scan(vbs('tc = Chr(83) & Chr(77)'))
        self.assertIn("OBFUSKASYON", self.rules(res, "WARN"))


class TestModVeBaslik(Base):
    INTERACT = 'ses.findById("wnd[0]/usr/btnX").press'

    def test_interaction_blocks_in_okuma(self):
        res = self.scan(vbs(self.INTERACT))
        self.assertIn("ETKILESIM", self.rules(res, "BLOCKER"))

    def test_interaction_warns_in_akis(self):
        res = self.scan(vbs(self.INTERACT, mod="akis", geri="yok"))
        self.assertNotIn("ETKILESIM", self.rules(res, "BLOCKER"))
        self.assertIn("ETKILESIM", self.rules(res, "WARN"))

    def test_mode_override(self):
        res = self.scan(vbs(self.INTERACT, mod="akis", geri="yok"), mode="okuma")
        self.assertIn("ETKILESIM", self.rules(res, "BLOCKER"))

    def test_field_assignment_blocks_in_okuma(self):
        res = self.scan(vbs('ses.findById("wnd[0]/usr/ctxtX").Text = "1000"'))
        self.assertIn("ETKILESIM", self.rules(res, "BLOCKER"))

    def test_comparison_is_not_assignment(self):
        res = self.scan(vbs('If ses.ActiveWindow.Text = "SAP" Then x = 1\ny = ses.ActiveWindow.Text'))
        self.assertEqual(self.rules(res, "BLOCKER"), set())

    def test_missing_header(self):
        res = self.scan(vbs("Dim x", header=False))
        self.assertIn("BASLIK", self.rules(res, "BLOCKER"))

    def test_okuma_with_irreversible_step(self):
        res = self.scan(vbs("Dim x", geri="belge kaydedilir"))
        self.assertIn("BASLIK", self.rules(res, "BLOCKER"))

    def test_invalid_mode(self):
        res = self.scan(vbs("Dim x", mod="yazma"))
        self.assertIn("BASLIK", self.rules(res, "BLOCKER"))


class TestPowerShell(Base):
    HEAD = ('# AXET-GUI-SCRIPT v1\n# MOD: okuma\n# GERI-ALINAMAZ: yok\n'
            '$rot = New-Object -ComObject SapROTWr.SapROTWrapper\n$gui = $rot.GetROTEntry("SAPGUI")\n'
            '$app = $gui.GetType().InvokeMember("GetScriptingEngine", [System.Reflection.BindingFlags]::InvokeMethod, $null, $gui, $null)\n'
            '$ses = $app.ActiveSession\n')

    def test_clean_read(self):
        res = self.scan(self.HEAD + '$t = $ses.ActiveWindow.Text\n', lang="ps")
        self.assertEqual(self.rules(res, "BLOCKER"), set())

    def test_assignment_blocks(self):
        res = self.scan(self.HEAD + '$ses.findById("wnd[0]/usr/txtX").Text = "1"\n', lang="ps")
        self.assertIn("ETKILESIM", self.rules(res, "BLOCKER"))

    def test_invokemember_setproperty_blocks(self):
        res = self.scan(self.HEAD + '$f.GetType().InvokeMember("Text", [System.Reflection.BindingFlags]::SetProperty, $null, $f, @("1"))\n', lang="ps")
        self.assertIn("ETKILESIM", self.rules(res, "BLOCKER"))


class TestCommandLine(unittest.TestCase):
    """Gerçek giriş noktası: komut satırı çıkış kodları."""

    def run_cli(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-B", str(CHECKER), *args], capture_output=True, text=True,
                              encoding="utf-8", errors="replace")

    def test_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / "bad.vbs"
            bad.write_text(vbs('ses.StartTransaction "SM12"', mod="akis", geri="yok"), encoding="utf-8")
            good = Path(d) / "good.vbs"
            good.write_text(vbs("Dim x"), encoding="utf-8")
            other = Path(d) / "x.txt"
            other.write_text("x", encoding="utf-8")
            r_bad = self.run_cli(str(bad))
            r_good = self.run_cli(str(good))
            self.assertEqual(r_bad.returncode, 1, r_bad.stdout)
            self.assertEqual(r_good.returncode, 0, r_good.stdout)
            self.assertIn("BAKILMAYANLAR", r_good.stdout)
            self.assertEqual(self.run_cli(str(Path(d) / "yok.vbs")).returncode, 2)
            self.assertEqual(self.run_cli(str(other)).returncode, 2)

    def test_templates_directory(self):
        r = self.run_cli(str(TEMPLATES))
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("3 dosya", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
