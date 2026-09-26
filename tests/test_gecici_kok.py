# -*- coding: utf-8 -*-
"""Z96 (+Z120ⓑ) — `GeciciTest`'in geçici kökü bir git reposunun DIŞINDA olmalı.

Vaka (ölçüldü 2026-09-24): aXet `TMP`/`TEMP`'i `<proje>\\.axet-code\\tmp`'ye çekiyor; proje bir git reposu olduğu
için `tempfile.mkdtemp()` repo içine düştü ve "git reposu değil" varsayan testler (test_doctor GitKimlikTest,
test_proje_tamamla, test_new_project …) KOD HATASI OLMADAN kırmızı verdi (28/217). Yardımcı artık kökü
`git rev-parse` ile sınar: TMP repo içindeyse `%LOCALAPPDATA%\\Temp`'e düşer (Z67 TMP-OLUSTUR ile aynı ilke);
o da repo içindeyse test FAIL değil, gerekçesini söyleyen açık SKIP ("ÖLÇÜLEMEDİ") olur.

Ölçüm gerçek giriş noktasından: çocuk süreçte gerçek `_helpers.GeciciTest` koşulur; TMP ortam değişkeniyle
gerçekten bir git reposunun içine yönlendirilir.

KAPSAM — bakılmayanlar: `GeciciTest` KULLANMAYAN testlerin kendi `mkdtemp` çağrıları (skill takımları,
test_install.py:1198/:1253 — kendi TMP'lerini ayrıca seçerler) · Linux/macOS (`LOCALAPPDATA` yoksa yalnız TMP
denenir) · git kurulu değilken davranış (o durumda repo ölçülemez; aday olduğu gibi kullanılır).
"""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

from _helpers import GeciciTest, git_reposunda_mi, gecici_kok_sec

BURASI = Path(__file__).resolve().parent

# Çocuk süreçte koşan tek testlik takım: gerçek GeciciTest'in seçtiği kökü ve repo durumunu basar.
COCUK = textwrap.dedent("""
    import subprocess, sys, unittest
    sys.path.insert(0, {tests!r})
    from _helpers import GeciciTest

    class T(GeciciTest):
        def test_kok(self):
            r = subprocess.run(["git", "-C", str(self.tmp), "rev-parse", "--is-inside-work-tree"],
                               capture_output=True, text=True, env=self.env)
            print("KOK=" + str(self.tmp))
            print("REPO=" + ("ICINDE" if r.returncode == 0 else "DISINDA"))
            print("ENV_TMP=" + self.env.get("TMP", ""))

    unittest.main(argv=["x", "-v"])
""")


class GeciciKokTest(GeciciTest):
    def setUp(self) -> None:
        super().setUp()
        self.repo = self.tmp / "proje"
        self.repo.mkdir()
        self.git(self.repo, "init", "-q")
        self.repo_tmp = self.repo / ".axet-code" / "tmp"     # aXet'in TMP'yi çektiği yer
        self.repo_tmp.mkdir(parents=True)
        self.lad = self.tmp / "lad"                          # sahte %LOCALAPPDATA%
        (self.lad / "Temp").mkdir(parents=True)
        self.cocuk = self.tmp / "cocuk_test.py"
        self.cocuk.write_text(COCUK.format(tests=str(BURASI)), encoding="utf-8")

    def cocuk_kos(self, tmp: Path, lad: Path) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env.update({"TMP": str(tmp), "TEMP": str(tmp), "TMPDIR": str(tmp), "LOCALAPPDATA": str(lad),
                    "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"})
        return subprocess.run([sys.executable, str(self.cocuk)], env=env, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=120)

    # --- birim: seçim kuralı ------------------------------------------------------------------------------
    def test_repo_icindeki_aday_atlanir_sonraki_secilir(self):
        self.assertTrue(git_reposunda_mi(self.repo_tmp))
        self.assertFalse(git_reposunda_mi(self.lad / "Temp"))
        self.assertEqual(gecici_kok_sec([self.repo_tmp, self.lad / "Temp"]), (self.lad / "Temp").resolve())

    def test_KONTROL_repo_disindaki_ilk_aday_aynen_kalir(self):
        disari = self.tmp / "dis_tmp"
        disari.mkdir()
        self.assertEqual(gecici_kok_sec([disari, self.lad / "Temp"]), disari.resolve())

    def test_hicbir_aday_repo_disinda_degilse_none(self):
        self.assertIsNone(gecici_kok_sec([self.repo_tmp, self.repo / "yok"]))

    # --- gerçek giriş noktası: çocuk süreçte GeciciTest -------------------------------------------------
    def test_tmp_repo_icindeyse_kok_repo_disina_sabitlenir(self):
        r = self.cocuk_kos(self.repo_tmp, self.lad)
        c = r.stdout + r.stderr
        self.assertEqual(r.returncode, 0, c)
        self.assertIn("REPO=DISINDA", c)
        kok = Path(c.split("KOK=", 1)[1].splitlines()[0])
        self.assertIn((self.lad / "Temp").resolve(), kok.parents, c)
        # alt süreçler de repo dışı TMP'yi görür (test edilen betiklerin kendi mkdtemp'i)
        self.assertEqual(Path(c.split("ENV_TMP=", 1)[1].splitlines()[0]), (self.lad / "Temp").resolve(), c)

    def test_KONTROL_tmp_repo_disindaysa_tmp_kullanilir(self):
        dis = self.tmp / "dis_tmp"
        dis.mkdir()
        r = self.cocuk_kos(dis, self.lad)
        c = r.stdout + r.stderr
        self.assertEqual(r.returncode, 0, c)
        self.assertIn("REPO=DISINDA", c)
        self.assertIn(dis.resolve(), Path(c.split("KOK=", 1)[1].splitlines()[0]).parents, c)

    def test_iki_aday_da_repo_icindeyse_acik_skip_olculemedi(self):
        lad_ic = self.repo / "lad"
        (lad_ic / "Temp").mkdir(parents=True)
        r = self.cocuk_kos(self.repo_tmp, lad_ic)
        c = r.stdout + r.stderr
        self.assertEqual(r.returncode, 0, c)          # FAIL değil
        self.assertIn("skipped=1", c)
        self.assertIn("ÖLÇÜLEMEDİ", c)
        self.assertNotIn("KOK=", c)                   # test gövdesi hiç koşmadı


if __name__ == "__main__":
    unittest.main()
