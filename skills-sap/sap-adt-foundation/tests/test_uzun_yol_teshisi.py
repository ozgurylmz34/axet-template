# -*- coding: utf-8 -*-
"""`run_review`: "validator bulunamadı" teşhisi MAX_PATH'i anmalı (2026-09-20, K3).

ÖLÇÜLEN SINIF: Windows'ta `LongPathsEnabled=0` iken 259 karakteri aşan yola **Python dosya
yazamaz ama git yazar** ⇒ uzun yollu bir klonda validator DİSKTE DURUR, git onu izler,
`git status` temizdir; buna karşılık `Path.exists()` `False` döner. Eski mesaj yalnız
"bulunamadı" diyordu ⇒ okuyan kişi gate'i "kurulmamış/silinmiş" sanıp kurulumu onarmaya
çalışıyordu — yanlış yön.

⛔ HÜKÜM DEĞİŞMİYOR ve bu testin bir ayağı tam olarak bunu ölçer: eksik BLOCKER gate hâlâ
`BLOCKER` + `exit 1` üretir. Eklenen şey YALNIZ teşhis metnidir.

KAPSAM — bakılmayanlar: gerçek uzun yollu klonda uçtan uca koşum (mekanizma ayrı ölçüldü,
burada yol uzunluğu sentetik olarak kurulur) · Linux/macOS · `LongPathsEnabled=1` makine.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import re
import sys
import tempfile
import unittest
from pathlib import Path

import _helpers as H

sys.dont_write_bytecode = True
VALIDATORS = H.SCRIPTS / "sapadt" / "lib" / "validators"


def _yukle(ad: str, dosya: str):
    if str(VALIDATORS) not in sys.path:
        sys.path.insert(0, str(VALIDATORS))
    spec = importlib.util.spec_from_file_location(ad, str(VALIDATORS / dosya))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class UzunYolTeshisiTest(unittest.TestCase):
    IPUCU = "YOL UZUN"

    @classmethod
    def setUpClass(cls) -> None:
        cls.rr = _yukle("axet_run_review_uzunyol", "run_review.py")

    # ── ① birim: ipucu eşiği ────────────────────────────────────────────────────────────
    def test_1_KONTROL_kisa_yolda_ipucu_YOK(self):
        """Yanlış pozitif kontrolü — gate gerçekten silinmişse mesaj sapmamalı."""
        self.assertEqual(self.rr.uzun_yol_ipucu(Path("C:/a/check_x.py")), "")

    def test_2_sinirin_iki_yaninda_davranis(self):
        sinir = self.rr.MAX_PATH_SINIRI
        tam = Path("C:/" + "d" * (sinir - 3))
        self.assertEqual(len(str(tam)), sinir, "fixture ön koşulu: tam sınır uzunluğu")
        self.assertEqual(self.rr.uzun_yol_ipucu(tam), "", "sınırın KENDİSİ uzun sayılmaz")
        self.assertIn(self.IPUCU, self.rr.uzun_yol_ipucu(Path(str(tam) + "d")))

    def test_3_ipucu_olculebilir_bilgi_tasiyor(self):
        uzun = Path("C:/" + "d" * 400)
        m = self.rr.uzun_yol_ipucu(uzun)
        self.assertIn(str(len(str(uzun))), m, "gerçek uzunluk yazılmalı")
        self.assertIn("MAX_PATH", m)
        self.assertIn("git", m, "sebebi söylenmeli: dosyayı git yazmış olabilir")

    # ── ② uçtan uca: mesaj gerçekten ZİNCİRDEN çıkıyor mu ───────────────────────────────
    def _main_kos(self, yol: Path):
        """`validator_yolu` VAR OLMAYAN bir yol döndürür → SKIP dalı koşar."""
        rr = self.rr
        with tempfile.TemporaryDirectory() as td:
            art = Path(td) / "z.txt"
            art.write_text("x", encoding="utf-8")
            eski = (rr.TASK_VALIDATORS, rr.validator_yolu, sys.argv)
            rr.TASK_VALIDATORS = {"_uzunyol_testi": [("check_sahte.py", "BLOCKER", "sahte gate")]}
            rr.validator_yolu = lambda ad: yol
            sys.argv = ["run_review.py", "--task", "_uzunyol_testi", "--artifact", str(art)]
            out, err = io.StringIO(), io.StringIO()
            try:
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    rc = rr.main()
            finally:
                rr.TASK_VALIDATORS, rr.validator_yolu, sys.argv = eski
        v = re.search(r"^VERDICT: (\S+)", out.getvalue(), re.M)
        return rc, (v.group(1) if v else None), out.getvalue() + err.getvalue()

    def test_4_uzun_yolda_mesaj_ipucunu_TASIR(self):
        rc, verdict, cikti = self._main_kos(Path("C:/" + "d" * 400 + "/check_sahte.py"))
        self.assertIn(self.IPUCU, cikti, "SKIP mesajı ipucunu taşımıyor → kablolama yok")
        self.assertEqual(verdict, "BLOCKER", "HÜKÜM DEĞİŞMEMELİ: eksik BLOCKER gate hâlâ BLOCKER")
        self.assertEqual(rc, 1)

    def test_5_KONTROL_kisa_yolda_mesaj_eskisi_gibi(self):
        rc, verdict, cikti = self._main_kos(Path("C:/yok/check_sahte.py"))
        self.assertNotIn(self.IPUCU, cikti, "kısa yolda ipucu basılmamalı (gürültü)")
        self.assertIn("PRE-FLIGHT KOŞMADI", cikti, "asıl mesaj korunmalı")
        self.assertEqual((rc, verdict), (1, "BLOCKER"))


if __name__ == "__main__":
    unittest.main()
