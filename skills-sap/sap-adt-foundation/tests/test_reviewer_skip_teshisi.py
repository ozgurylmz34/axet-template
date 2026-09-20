# -*- coding: utf-8 -*-
"""Madde 1 (karar A, 2026-09-20) — reviewer SKIP'inin NEDENİ taşınır.

Kusur (ölçüldü): `run_reviewer` sonunda `verdict = raw.get("verdict", "BLOCKER" if rc==1 else
"SKIP")` rc ∉ (0,1) + JSON yok durumunda SKIP üretiyordu, ama `skip_reason` HİÇ verilmiyordu.
`passed` = PASS ∪ SKIP olduğu için pre-flight KOŞMADAN SAP yazımı sürüyor, kullanıcıya giden
not ise `on_kontrol_ozeti` üzerinden "PRE-FLIGHT KOŞMADI ()" diye BOŞ çıkıyordu.

⛔ Bu test VERDICT semantiğini çivilemez-değiştirmez (fail-closed AYRI karar: madde 1b).
Çivilediği tek şey TEŞHİS: rc + stderr kuyruğu nota düşüyor mu.

KONTROL GRUBU zorunlu: aynı sarmalayıcı, YALNIZ rc/JSON değişir → sağlıklı koşumda
`skip_reason` BOŞ kalmalı; aksi hâlde test kendi kendini kanıtlar.
"""
from __future__ import annotations

import subprocess
import sys
import unittest
from unittest import mock

import _helpers as H

sys.dont_write_bytecode = True
if str(H.SCRIPTS) not in sys.path:
    sys.path.insert(0, str(H.SCRIPTS))

from sapadt import _reviewer as rv  # noqa: E402


def _tamam(rc: int, stdout: str, stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["run_review.py"], returncode=rc,
                                       stdout=stdout, stderr=stderr)


class ReviewerSkipTeshisi(unittest.TestCase):

    def _kos(self, rc: int, stdout: str, stderr: str = ""):
        with mock.patch.object(rv.subprocess, "run", return_value=_tamam(rc, stdout, stderr)):
            return rv.run_reviewer("struct_creation", __file__)

    def test_1_rc_bilinmeyen_json_yok_neden_tasinir(self):
        r = self._kos(127, "komut bulunamadı", "python: can't open file 'run_review.py'")
        self.assertEqual(r.verdict, "SKIP", "verdict semantiği DEĞİŞMEMELİ")
        self.assertTrue(r.skipped, "türetilmiş SKIP `skipped` bayrağını da taşımalı")
        self.assertIn("rc=127", r.skip_reason)
        self.assertIn("run_review.py", r.skip_reason, "stderr kuyruğu nota girmeli")

    def test_2_kullaniciya_giden_not_artik_bos_degil(self):
        """Asıl semptom: 'PRE-FLIGHT KOŞMADI ()'."""
        r = self._kos(3, "", "ImportError: no module named yaml")
        not_ = rv.on_kontrol_ozeti(r)["notice"]
        self.assertNotIn("KOŞMADI ()", not_)
        self.assertIn("rc=3", not_)
        self.assertIn("ImportError", not_)

    def test_3_stderr_bos_olsa_bile_rc_soylenir(self):
        r = self._kos(9, "çöp", "")
        self.assertIn("rc=9", r.skip_reason)
        self.assertIn("BOŞ", r.skip_reason)

    def test_4_KONTROL_saglikli_kosumda_skip_reason_BOS(self):
        """Kontrol grubu: rc=0 + geçerli JSON → teşhis metni ÜRETİLMEZ (yanlış pozitif yok)."""
        r = self._kos(0, '{"verdict": "PASS", "blocker_count": 0, "warning_count": 0}')
        self.assertEqual(r.verdict, "PASS")
        self.assertFalse(r.skipped)
        self.assertEqual(r.skip_reason, "")

    def test_5_KONTROL_rc1_hala_BLOCKER(self):
        """rc=1 + JSON yok → eskisi gibi BLOCKER; SKIP teşhis dalı buraya KARIŞMAZ."""
        r = self._kos(1, "", "gate patladı")
        self.assertEqual(r.verdict, "BLOCKER")
        self.assertEqual(r.skip_reason, "")
        self.assertFalse(r.skipped)

    def test_6_KONTROL_JSON_kendi_SKIPini_soylerse_ezilmez(self):
        """JSON açıkça SKIP + kendi gerekçesini veriyorsa türetilmiş metin ONU EZMEZ."""
        r = self._kos(0, '{"verdict": "SKIP", "skip_reason": "no_artifact_path_provided"}')
        self.assertEqual(r.skip_reason, "no_artifact_path_provided")


if __name__ == "__main__":
    unittest.main(verbosity=2)
