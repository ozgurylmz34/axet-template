# -*- coding: utf-8 -*-
"""Remote'suz (yalnız yerel) projede dal → `main` birleştirme tarifi (IS-LISTESI Z72).

Ölçülen vaka (2026-09-23, `axet-code run`, izole XDG_CONFIG_HOME, remote'suz AXET_TEST kopyası; kanıt git geçmişi +
`.axet-code/axet-code.db` araç çağrıları): tarif yokken model ⓐ onaylı istemde `git merge --ff-only` yaptı
(birleştirme commit'i yok, dal silinmedi, doğrulama yok) ⓑ onaysız "bu dalı main'e birleştir"de sormadan birleştirdi
ⓒ çakışmada `ask_user` "No interactive user" dönünce iki satırı birleştirip çakışmayı KENDİSİ çözdü ve commit etti.
Tarifin ilk sürümüyle çakışma koşumunda model doğrulama FAIL'i için sordu, cevapsız soruyu ("Proceed using your best
judgment") izin sayıp birleştirmeye geçti ⇒ "cevapsız soru = HAYIR" ve "FAIL'i atlama kararı kullanıcınındır" eklendi.

Burada ölçülen: ⓐ `commit-pr` adım 9'un, `gun-sonu`nun remote-yok davranışının ve çekirdek §6 yönlendirmesinin
metinde durduğu ⓑ skill'in öğrettiği git komutlarının `config/permissions.json` deny/ask desenlerine TAKILMADIĞI
(takılırsa tarif uygulanamaz ve model yöntem uydurur) ve yasakladığı `git branch -D`'nin deny olduğu.
Eşleşme semantiği test_install ile aynı: tam metne glob, harfe duyarlı (fnmatchcase SİMÜLASYONU, motor değil).
KAPSAM — bakılmayanlar: modelin metni bulup UYGULADIĞI (canlı ölçüm IS-LISTESI Z72'de) · `git branch -d -f` /
`--delete --force` gibi zorla-silme eşdeğerlerinin izin katmanında TUTULMADIĞI (ölçüldü: hiçbir desene uymuyor;
yalnız metin yasaklar — açık kalem) · metnin Türkçe doğruluğu.
"""
from __future__ import annotations

import fnmatch
import json
import re
import unittest

from _helpers import AXET_HOME

COMMIT_PR = AXET_HOME / "skills" / "commit-pr" / "SKILL.md"
GUN_SONU = AXET_HOME / "skills" / "gun-sonu" / "SKILL.md"
CEKIRDEK = AXET_HOME / "core" / "00-temel.md"
IZINLER = AXET_HOME / "config" / "permissions.json"

# Tarifin öğrettiği komutlar (yer tutucular gerçek adla). Hiçbiri deny/ask'a uymamalı.
TARIF_KOMUTLARI = [
    "git remote",
    "git switch -c ozellik/x main",
    "git log --oneline main..ozellik/x",
    "git diff --stat main...ozellik/x",
    "git switch main",
    "git merge --no-ff ozellik/x",
    "git diff --name-only --diff-filter=U",
    "git merge --abort",
    "git log --oneline --graph -5",
    "git branch -d ozellik/x",
]


def _oku(yol) -> str:
    return yol.read_text(encoding="utf-8")


def _adim9(metin: str) -> str:
    m = re.search(r"(?ms)^9\. \*\*Yerel birleştirme.*?(?=^## |\Z)", metin)
    return m.group(0) if m else ""


class YerelBirlestirmeMetniTest(unittest.TestCase):
    def test_commit_pr_adim9_zorunlu_ogeleri_tasir(self):
        metin = _oku(COMMIT_PR)
        adim = _adim9(metin)
        self.assertTrue(adim, "commit-pr'de '9. **Yerel birleştirme' adımı yok")
        eksik = [o for o in ("`git remote`", "git merge --no-ff <dal>", "git branch -d <dal>", "--diff-filter=U",
                             "git merge --abort", "No interactive user", "HAYIR", "atlama kararı kullanıcınındır",
                             "DUR", "--squash", "--ff-only")
                 if o not in adim]
        self.assertEqual(eksik, [], f"adım 9'da eksik öğe: {eksik}")
        # remote ölçümü dal adımında da açık olmalı (yerel dal başlangıç noktası açık)
        self.assertIn("`git switch -c <dal> main`", metin)
        # Rules/Merge yerel yolu adım 9'a bağlamalı (yalnız PR + CI yazılıydı)
        self.assertRegex(metin, r"\*\*Merge:\*\*[^\n]*Yerel repoda[^\n]*adım 9")

    def test_gun_sonu_remote_yoksa_durmaz_ve_birlestirmez(self):
        metin = _oku(GUN_SONU)
        for oge in ("**Remote yoksa**", "push adımı YOKTUR", "DURMA", "main'e birleşmedi", "`%commit-pr` adım 9"):
            self.assertIn(oge, metin)
        # eski "Remote yoksa ... DUR" cümlesi geri gelmesin (remote'suz projede her gün sonu DUR'du)
        self.assertNotIn("Remote yoksa ya da push reddedilirse DUR", metin)

    def test_cekirdek_git_bolumu_yonlendirir(self):
        m = re.search(r"(?ms)^## 6\. Git.*?(?=^## )", _oku(CEKIRDEK))
        self.assertIsNotNone(m, "çekirdekte '## 6. Git' bölümü yok")
        bolum = m.group(0)
        for oge in ("`git remote` boş", "`%commit-pr`", "--no-ff", "çakışmada DUR", "git branch -d"):
            self.assertIn(oge, bolum)


class TarifIzinUyumuTest(unittest.TestCase):
    def setUp(self):
        self.bash = json.loads(IZINLER.read_text(encoding="utf-8"))["rules"]["bash"]

    def _eslesen(self, komut: str) -> list[tuple[str, str]]:
        return [(p, k) for p, k in self.bash.items() if fnmatch.fnmatchcase(komut, p)]

    def test_tarif_komutlari_izin_kuralina_takilmaz(self):
        takilan = {k: self._eslesen(k) for k in TARIF_KOMUTLARI if self._eslesen(k)}
        self.assertEqual(takilan, {}, "skill'in öğrettiği komut deny/ask desenine uyuyor — tarif uygulanamaz")

    def test_yasaklanan_zorla_silme_deny(self):
        self.assertIn(("*git branch -D*", "deny"), self._eslesen("git branch -D ozellik/x"))


if __name__ == "__main__":
    unittest.main()
