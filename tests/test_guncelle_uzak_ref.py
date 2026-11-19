# -*- coding: utf-8 -*-
"""Q349 (güncelleme motoru): `origin/main` kısa adını aynı adlı bir ETİKET gölgeler — git ref çözümünde `refs/tags/`
`refs/remotes/`'tan önce gelir ⇒ yayın kataloğu, kartlar ve CI kaydı yanlış kaynaktan okunur. Motor git'e ref olarak
daima tam `refs/remotes/origin/main` verir. session_brief eşleniği: tests/test_session_brief.py YayinlarRefTest.

İki katman: ① kaynak taraması — guncelle.py / guncelle_proje.py içinde git'e giden her `origin/main` ref'i tam ref;
② davranış — gölgeleme gerçekten kurulur (kontrol grubu) ve tam ref yine dalı okur.
KAPSAM: yalnız bu iki dosyanın git çağrılarındaki dizge sabitleri; kullanıcıya gösterilen mesaj metni bakılmaz.
"""
from __future__ import annotations

import re
import unittest

from _helpers import AXET_HOME, GeciciTest

TAM = "refs/remotes/origin/main"
DOSYALAR = ("scripts/guncelle.py", "scripts/guncelle_proje.py")
# git'e giden çağrı biçimleri: .git(...) / .g(...) / var_mi(...) ve `return "<ref>"` (yayın tabanı)
CAGRI = re.compile(r'(?:\.git|\.g|var_mi)\((?P<arg>[^)]*)\)|return\s+(?P<don>f?"[^"]*")')
REF = re.compile(r'f?"((?:refs/remotes/)?origin/main)\b')


def ref_kullanimlari() -> list[tuple[str, int, str]]:
    bulunan = []
    for d in DOSYALAR:
        for no, satir in enumerate((AXET_HOME / d).read_text(encoding="utf-8").splitlines(), 1):
            for m in CAGRI.finditer(satir):
                parca = m.group("arg") or m.group("don") or ""
                for r in REF.finditer(parca):
                    bulunan.append((d, no, r.group(1)))
    return bulunan


# Motoru çıkaran ve sürümü söyleyen talimat komutları da git'e ref verir (bug gate 2026-11-17: skill adım 3-4 kısa ad
# kullanıyordu ⇒ gölge etiket motorun KENDİSİNİ seçerdi). Kapsam: satır başında ya da ters tırnak içinde `git ` geçen satırlar.
TALIMATLAR = ("skills/guncelle/SKILL.md", "GUNCELLE.md")
KOMUT_REF = re.compile(r"(?<![/\w])origin/main\b")


def komut_satiri_mi(satir: str) -> bool:
    return re.search(r"(^|`)git ", satir.strip()) is not None


def kisa_ref_var_mi(satir: str) -> bool:
    """Komut satırında tam ref dışında kısa `origin/main` var mı (tarama ve kalibrasyon AYNI kararı kullanır)."""
    return KOMUT_REF.search(satir.replace(TAM, "")) is not None and "gölgelen" not in satir


def talimat_kisa_refleri() -> tuple[int, list[tuple[str, int, str]]]:
    sayi, kisa = 0, []
    for d in TALIMATLAR:
        for no, satir in enumerate((AXET_HOME / d).read_text(encoding="utf-8").splitlines(), 1):
            if not komut_satiri_mi(satir):
                continue
            sayi += satir.count(TAM)
            if kisa_ref_var_mi(satir):
                kisa.append((d, no, satir.strip()[:120]))
    return sayi, kisa


class TalimatRefTest(unittest.TestCase):
    def test_talimat_komutlari_tam_ref(self):
        sayi, kisa = talimat_kisa_refleri()
        self.assertGreaterEqual(sayi, 3, "tarama kör: talimatlarda tam ref bulunamadı (beklenen ≥3)")
        self.assertEqual([], kisa, "talimat komutunda kısa `origin/main` — aynı adlı etiket gölgeler")

    def test_komut_tarayici_kalibrasyonu(self):
        """Z242: bilinen kısa ref'li komut satırları YAKALANMALI, tam ref'li olanlar yakalanmamalı (tarayıcı kör değil).
        Eskiden desende `\\b` yerine 0x08 baytı vardı ⇒ kısa ref hiç eşleşmiyor, tarama her zaman temiz diyordu."""
        kisa = ["`git -C <KLON> show origin/main:GUNCELLE.md`",
                "git -C <KLON> archive --format=tar -o <TMP>/m.tar origin/main GUNCELLE.md",
                "`git rev-parse origin/main`"]
        tam = [f"`git -C <KLON> show {TAM}:GUNCELLE.md`", "`git fetch origin main`",
               "`git -C <KLON> log origin/mainline`", "`git -C <KLON> log upstream/origin/main`"]
        self.assertTrue(all(komut_satiri_mi(s) for s in kisa + tam))
        self.assertEqual([True] * len(kisa), [kisa_ref_var_mi(s) for s in kisa], "kısa ref kaçtı — desen kör")
        self.assertEqual([False] * len(tam), [kisa_ref_var_mi(s) for s in tam], "tam ref / başka ad yanlış pozitif")


class KaynakTaramaTest(unittest.TestCase):
    def test_git_cagrilari_tam_ref_kullanir(self):
        kullanim = ref_kullanimlari()
        self.assertGreaterEqual(len(kullanim), 8, f"tarama hiçbir şey bulmadı ya da kör (beklenen ≥8): {kullanim}")
        kisa = [k for k in kullanim if k[2] != TAM]
        self.assertEqual([], kisa, "kısa `origin/main` ref'i — aynı adlı etiket gölgeler")

    def test_tarayici_kisa_ref_yakalar(self):
        """Kalibrasyon: bilinen kısa ref'li satır yakalanmalı (tarayıcı kör değil)."""
        satir = 'r = self.k.git("show", "origin/main:guncelle/yayinlar.json")'
        m = CAGRI.search(satir)
        self.assertEqual(["origin/main"], [r.group(1) for r in REF.finditer(m.group("arg"))])


class EtiketGolgesiTest(GeciciTest):
    def test_tam_ref_dali_okur_kisa_ad_etiketi(self):
        kaynak = self.tmp / "kaynak"
        kaynak.mkdir()
        self.git(kaynak, "init", "-q", "-b", "main")
        (kaynak / "guncelle").mkdir()
        (kaynak / "guncelle" / "yayinlar.json").write_text('{"kaynak": "dal"}', encoding="utf-8")
        self.git(kaynak, "add", ".")
        self.git(kaynak, "commit", "-q", "-m", "dal")
        klon = self.tmp / "klon"
        self.git(self.tmp, "clone", "-q", str(kaynak), str(klon))
        self.git(klon, "checkout", "-q", "-b", "yan")
        (klon / "guncelle" / "yayinlar.json").write_text('{"kaynak": "etiket"}', encoding="utf-8")
        self.git(klon, "commit", "-q", "-am", "etiket")
        self.git(klon, "tag", "origin/main")
        kisa = self.git(klon, "show", "origin/main:guncelle/yayinlar.json", kontrol=False)
        self.assertIn("etiket", kisa.stdout, "kontrol grubu: gölgeleme kurulamadı — test hiçbir şey ölçmez")
        tam = self.git(klon, "show", f"{TAM}:guncelle/yayinlar.json")
        self.assertIn('"dal"', tam.stdout)

    def test_archive_tam_ref_dali_cikarir(self):
        """%guncelle adım 3 motoru `git archive` ile çıkarır: aynı gölge archive'da da var (kontrol grubu) ve tam ref
        dalı verir (bug gate 2026-11-17 MEDIUM-1 — o adım kısa ad kullanıyordu)."""
        import tarfile
        kaynak = self.tmp / "kaynak2"
        kaynak.mkdir()
        self.git(kaynak, "init", "-q", "-b", "main")
        (kaynak / "GUNCELLE.md").write_text("dal", encoding="utf-8")
        self.git(kaynak, "add", ".")
        self.git(kaynak, "commit", "-q", "-m", "dal")
        klon = self.tmp / "klon2"
        self.git(self.tmp, "clone", "-q", str(kaynak), str(klon))
        self.git(klon, "checkout", "-q", "-b", "yan")
        (klon / "GUNCELLE.md").write_text("etiket", encoding="utf-8")
        self.git(klon, "commit", "-q", "-am", "etiket")
        self.git(klon, "tag", "origin/main")

        def icerik(ref: str) -> str:
            cikti = self.tmp / f"m-{len(ref)}.tar"
            self.git(klon, "archive", "--format=tar", "-o", str(cikti), ref, "GUNCELLE.md")
            with tarfile.open(cikti) as t:
                return t.extractfile("GUNCELLE.md").read().decode("utf-8")
        self.assertEqual("etiket", icerik("origin/main"), "kontrol grubu: archive'da gölge kurulamadı")
        self.assertEqual("dal", icerik(TAM))


class PlanRefNormalTest(unittest.TestCase):
    """Eski motorun plana/mühre yazdığı kısa `origin/main` geri düşüşü yeni motorda aynı tur sayılır (bug gate LOW-1)."""

    @classmethod
    def setUpClass(cls):
        import sys
        yol = str(AXET_HOME / "scripts")
        if yol not in sys.path:
            sys.path.insert(0, yol)
        import guncelle  # noqa: PLC0415
        cls.g = guncelle

    def test_ref_normal(self):
        self.assertEqual(TAM, self.g._ref_normal("origin/main"))
        self.assertEqual(TAM, self.g._ref_normal(TAM))
        self.assertEqual("v0.5.21", self.g._ref_normal("v0.5.21"))

    def test_eski_muhur_ayni_tur(self):
        plan = {"taban_commit": "abc", "yeni_etiket": TAM}
        eski = {"plan": {"taban_commit": "abc", "yeni_etiket": "origin/main"}}
        self.assertIsNone(self.g._muhur_sorunu("x.json", eski, plan))
        ham_plan = {"taban_commit": "abc", "yeni_etiket": "origin/main"}  # R3 ÖNERİ-1: ham plan geçen çağıran
        self.assertIsNone(self.g._muhur_sorunu("x.json", {"plan": dict(plan)}, ham_plan))
        baska = {"plan": {"taban_commit": "abc", "yeni_etiket": "v0.5.21"}}
        self.assertIsNotNone(self.g._muhur_sorunu("x.json", baska, plan))


if __name__ == "__main__":
    unittest.main()
