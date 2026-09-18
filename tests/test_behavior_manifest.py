# -*- coding: utf-8 -*-
"""behavior_manifest.py — proje modu (hash manifest) ve template modu (git)."""
from __future__ import annotations

import contextlib
import io
import json
import sys

from _helpers import AXET_HOME, GeciciTest  # önce: scripts/ yolunu ekler
import behavior_manifest as bm


class ProjeManifestTest(GeciciTest):
    def setUp(self) -> None:
        super().setUp()
        self.d = self.proje(git_init=False)

    def bm(self, *args: str):
        return self.calistir("behavior_manifest.py", *args, "--project-dir", str(self.d))

    def onayla(self) -> None:
        r = self.bm("generate")
        self.assertEqual(r.returncode, 0, self.cikti(r))

    def test_yok_sonra_onay_sonra_es(self):
        r = self.bm("check")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(bm.proje_denetle(self.d)[0], "yok")
        self.onayla()
        r = self.bm("check")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        kayit = json.loads((self.d / bm.MANIFEST).read_text(encoding="utf-8"))["dosyalar"]
        for rel in ("AGENTS.md", ".axet-code.json", ".axetcode-denylist", ".githooks/pre-commit", "validators-local/README.md"):
            self.assertIn(rel, kayit)

    def test_satir_sonu_farki_sapma_degil(self):
        self.onayla()
        f = self.d / "AGENTS.md"
        f.write_bytes(f.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
        self.assertEqual(self.bm("check").returncode, 0)

    def test_hafiza_yuzey_disi(self):
        self.onayla()
        self.yaz(self.d / ".axet-code" / "memory" / "MEMORY.md", "değişti\n")
        self.assertEqual(self.bm("check").returncode, 0)

    # --- negatif ---
    def test_tek_karakter_degisikligi_yakalanir(self):
        self.onayla()
        f = self.d / "AGENTS.md"
        f.write_text(f.read_text(encoding="utf-8") + "x", encoding="utf-8")
        r = self.bm("check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("DEĞİŞMİŞ (onaysız): AGENTS.md", r.stdout)

    def test_yeni_ve_silinen_dosya(self):
        self.onayla()
        self.yaz(self.d / "validators-local" / "yeni.py", "print(1)\n")
        (self.d / ".axetcode-denylist").unlink()
        r = self.bm("check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("KAYITSIZ yeni davranış dosyası: validators-local/yeni.py", r.stdout)
        self.assertIn("diskte YOK: .axetcode-denylist", r.stdout)

    def test_secici_onay_digerini_beklemede_birakir(self):
        self.onayla()
        f = self.d / "AGENTS.md"
        f.write_text(f.read_text(encoding="utf-8") + "x", encoding="utf-8")
        self.yaz(self.d / ".githooks" / "ek", "x\n")
        r = self.bm("generate", "--only", "AGENTS.md")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("BEKLEMEDE 1", r.stdout)
        r = self.bm("check")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("AGENTS.md", r.stdout.split("KAPSAM")[0])
        self.assertIn(".githooks/ek", r.stdout)

    def test_only_bilinmeyen_yol_reddedilir(self):
        self.onayla()
        once = (self.d / bm.MANIFEST).read_text(encoding="utf-8")
        r = self.bm("generate", "--only", "yok/boyle.md")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual((self.d / bm.MANIFEST).read_text(encoding="utf-8"), once)

    def test_only_manifest_yokken_reddedilir(self):
        r = self.bm("generate", "--only", "AGENTS.md")
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse((self.d / bm.MANIFEST).exists())

    def test_bozuk_manifest(self):
        self.yaz(self.d / bm.MANIFEST, "{bozuk")
        r = self.bm("check")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(bm.proje_denetle(self.d)[0], "bozuk")
        self.yaz(self.d / bm.MANIFEST, json.dumps({"dosyalar": ["liste"]}))
        self.assertEqual(bm.proje_denetle(self.d)[0], "bozuk")

    def test_template_modunda_generate_reddedilir(self):
        r = self.calistir("behavior_manifest.py", "generate", "--project-dir", str(AXET_HOME))
        self.assertEqual(r.returncode, 2, self.cikti(r))


class TemplateCliCiktiTest(GeciciTest):
    """`check --template` CLI'ının STDOUT'u (main()'in template dalı).

    Sınıflandırmanın kendisi `TemplateGuncelleSinifTest`te ölçülüyor; burada ölçülen YALNIZ CLI'ın o
    sınıfları BASMASI. Bu dal korumasızdı: `guncelle_anlik`/`guncelle_uygulama` döngüleri silinince
    satırlar sessizce düşüyor, rc yine 0 kalıyordu (bug-gate 2026-09-18 · M14).
    `template_sinifla` sentetik bir dönüşle değiştirilir → git'e/diske bağımlılık yok.
    ⚠ KAPSAM: yalnız template dalı + `check`; `generate` reddi ve proje dalı ayrı testlerin alanı.
    """

    SENTETIK = {"durum": "es", "kullanici": [],
                "guncelle_anlik": ["skills/sentetik-anlik/SKILL.md"],
                "guncelle_uygulama": ["core/sentetik-uygulama.md"],
                "notlar": ["sentetik not satırı"]}

    def kos(self, olc: dict, *argv: str):
        eski_sinifla, eski_argv = bm.template_sinifla, sys.argv
        bm.template_sinifla = lambda *a, **k: dict(olc)
        sys.argv = ["behavior_manifest.py", *argv]
        tampon = io.StringIO()
        try:
            with contextlib.redirect_stdout(tampon):
                rc = bm.main()
        finally:
            bm.template_sinifla = eski_sinifla
            sys.argv = eski_argv
        return rc, tampon.getvalue()

    def test_guncelle_siniflari_stdoutta_gorunur(self):
        """Dal SESSİZCE DÜŞEMEZ: iki sınıfın da YOLU ve etiketi çıktıda olmalı, rc 0 kalmalı."""
        rc, cikti = self.kos(self.SENTETIK, "check", "--template")
        self.assertEqual(rc, 0, cikti)
        self.assertIn("skills/sentetik-anlik/SKILL.md", cikti)
        self.assertIn("anlık commit", cikti)
        self.assertIn("core/sentetik-uygulama.md", cikti)
        self.assertIn("uyguladığı template güncellemesinde", cikti)

    def test_kontrol_grubu_sinif_bossa_yol_basilmaz(self):
        """Yanlış-pozitif yönü: sınıflar boşken bu yollar ÇIKMAMALI (yoksa üstteki test, çıktı
        sabit bir metin bassa bile yeşil kalırdı). Notlar dalı kontrol amaçlı hâlâ basılır."""
        rc, cikti = self.kos({**self.SENTETIK, "guncelle_anlik": [], "guncelle_uygulama": []},
                             "check", "--template")
        self.assertEqual(rc, 0, cikti)
        self.assertNotIn("sentetik-anlik", cikti)
        self.assertNotIn("sentetik-uygulama", cikti)
        self.assertIn("sentetik not satırı", cikti)

    def test_kullanici_sapmasi_satiri_ve_rc(self):
        """Kontrol grubu 2: kullanıcı sapması dalı hem basılır hem rc'yi 1 yapar (INFO sınıfları yapmaz)."""
        rc, cikti = self.kos({**self.SENTETIK, "durum": "sapma",
                              "kullanici": ["commit edilmemiş değişiklik [M]: sentetik-kullanici.md"]},
                             "check", "--template")
        self.assertEqual(rc, 1, cikti)
        self.assertIn("sentetik-kullanici.md", cikti)


class TemplateYuzeyTest(GeciciTest):
    def setUp(self) -> None:
        super().setUp()
        import os
        self._eski_env = dict(os.environ)
        os.environ.update({k: v for k, v in self.env.items() if k.startswith("GIT_")})
        self.k = self.tmp / "klon"
        for rel in ("core/00-temel.md", "skills/a/SKILL.md", "config/permissions.json", "memory/MEMORY.md",
                    "skills-sap/b/tests/test_x.py", "scripts/doctor.py"):
            self.yaz(self.k / rel, "ilk\n")
        self.git(self.k, "init", "-q", "-b", "main")
        self.git(self.k, "add", "-A")
        self.git(self.k, "commit", "-q", "-m", "ilk")

    def tearDown(self) -> None:
        import os
        os.environ.clear()
        os.environ.update(self._eski_env)
        super().tearDown()

    def test_temiz(self):
        durum, satirlar = bm.template_denetle(self.k)
        self.assertEqual(durum, "es", satirlar)
        self.assertTrue(any("upstream tanımlı değil" in s for s in satirlar))

    def test_commitsiz_ve_kayitsiz_degisiklik(self):
        self.yaz(self.k / "core/00-temel.md", "değişti\n")
        self.yaz(self.k / "skills/yeni/SKILL.md", "x\n")
        durum, satirlar = bm.template_denetle(self.k)
        self.assertEqual(durum, "sapma")
        metin = "\n".join(satirlar)
        self.assertIn("commit edilmemiş değişiklik [M]: core/00-temel.md", metin)
        self.assertIn("KAYITSIZ yeni dosya (commit'siz): skills/yeni/SKILL.md", metin)

    def test_yuzey_disi_degisiklik_sayilmaz(self):
        for rel in ("memory/MEMORY.md", "skills-sap/b/tests/test_x.py", "scripts/doctor.py"):
            self.yaz(self.k / rel, "değişti\n")
        self.assertEqual(bm.template_denetle(self.k)[0], "es")

    def test_git_degilse_olculemedi(self):
        d = self.tmp / "gitsiz"
        d.mkdir()
        self.assertEqual(bm.template_denetle(d)[0], "olculemedi")


class TemplateGuncelleSinifTest(GeciciTest):
    """`%guncelle` kaynaklı sapmalar ayırt edilebiliyor mu (Z5 gürültü düzeltmesi).

    Kontrol grubu şart: aynı dosya değişikliği (a) `%guncelle` kimliğiyle, (b) kullanıcı kimliğiyle
    commit'lenir; yalnız (b) 'sapma' olmalı. Kimlik `scripts/guncelle.py:51` GIT_KIMLIK'ten gelir.
    ⚠ KAPSAM: commit'ler burada git kimliği TAKLİT edilerek atılır; `guncelle.py`'nin kendisi
    koşturulmaz (o `tests/test_guncelle.py`'nin alanı). Kimlik/konu dizgelerinin kaynakla eşliği
    `test_guncelle_kimligi_kaynakla_es` ile ayrıca pinlenir.
    """

    def setUp(self) -> None:
        super().setUp()
        import os
        self._eski_env = dict(os.environ)
        os.environ.update({k: v for k, v in self.env.items() if k.startswith("GIT_")})
        self.k = self.tmp / "klon"
        for rel in ("core/00-temel.md", "skills/a/SKILL.md", "config/permissions.json"):
            self.yaz(self.k / rel, "ilk\n")
        self.git(self.k, "init", "-q", "-b", "main")
        self.git(self.k, "add", "-A")
        self.git(self.k, "commit", "-q", "-m", "ilk")
        uzak = self.tmp / "uzak.git"
        self.git(self.tmp, "init", "-q", "--bare", str(uzak))
        self.git(self.k, "remote", "add", "origin", str(uzak))
        self.git(self.k, "push", "-q", "-u", "origin", "main")

    def tearDown(self) -> None:
        import os
        os.environ.clear()
        os.environ.update(self._eski_env)
        super().tearDown()

    def commit_et(self, mesaj: str, eposta: str = "kullanici@example.invalid") -> None:
        self.git(self.k, "add", "-A")
        eski = self.env["GIT_AUTHOR_EMAIL"]
        self.env["GIT_AUTHOR_EMAIL"] = eposta
        try:
            self.git(self.k, "commit", "-q", "-m", mesaj)
        finally:
            self.env["GIT_AUTHOR_EMAIL"] = eski

    def test_guncelle_uygulama_commiti_sapma_degil(self):
        self.yaz(self.k / "core/00-temel.md", "template güncellendi\n")
        self.commit_et("guncelle: v0.5.0 kalemler K1, K2", bm.GUNCELLE_EPOSTA)
        o = bm.template_sinifla(self.k)
        self.assertEqual(o["durum"], "es", o)
        self.assertEqual(o["kullanici"], [], o)
        self.assertEqual(o["guncelle_uygulama"], ["core/00-temel.md"], o)
        self.assertEqual(o["guncelle_anlik"], [], o)

    def test_guncelle_anlik_commiti_ayri_sinifta(self):
        self.yaz(self.k / "skills/a/SKILL.md", "kullanıcı elle değiştirdi\n")
        self.commit_et("guncelle: yerel anlık 2026-09-18", bm.GUNCELLE_EPOSTA)
        o = bm.template_sinifla(self.k)
        self.assertEqual(o["durum"], "es", o)
        self.assertEqual(o["guncelle_anlik"], ["skills/a/SKILL.md"], o)
        self.assertEqual(o["guncelle_uygulama"], [], o)

    def test_kontrol_grubu_kullanici_commiti_sapma_kalir(self):
        """Aynı değişiklik, farklı yazar → WARN sınıfı KORUNUR (gevşetme kullanıcıya taşmıyor)."""
        self.yaz(self.k / "core/00-temel.md", "elle değişti\n")
        self.commit_et("elle düzelttim")
        o = bm.template_sinifla(self.k)
        self.assertEqual(o["durum"], "sapma", o)
        self.assertTrue(any("core/00-temel.md" in s for s in o["kullanici"]), o)
        self.assertEqual(o["guncelle_uygulama"] + o["guncelle_anlik"], [], o)

    def test_karisik_dosya_kullaniciya_yazilir(self):
        """Hem %guncelle hem kullanıcı dokunduysa: temkinli taraf → kullanıcı (WARN)."""
        self.yaz(self.k / "core/00-temel.md", "guncelle yazdı\n")
        self.commit_et("guncelle: v0.5.0 kalemler K1", bm.GUNCELLE_EPOSTA)
        self.yaz(self.k / "core/00-temel.md", "sonra kullanıcı yazdı\n")
        self.commit_et("elle düzelttim")
        o = bm.template_sinifla(self.k)
        self.assertEqual(o["durum"], "sapma", o)
        self.assertTrue(any("core/00-temel.md" in s for s in o["kullanici"]), o)
        self.assertEqual(o["guncelle_uygulama"], [], o)

    def test_commitsiz_degisiklik_guncelle_commitine_ragmen_sapma(self):
        """%guncelle commit'i sessizleşse de çalışma ağacındaki commit'siz değişiklik WARN kalır."""
        self.yaz(self.k / "core/00-temel.md", "guncelle yazdı\n")
        self.commit_et("guncelle: v0.5.0 kalemler K1", bm.GUNCELLE_EPOSTA)
        self.yaz(self.k / "config/permissions.json", "commit'siz\n")
        o = bm.template_sinifla(self.k)
        self.assertEqual(o["durum"], "sapma", o)
        self.assertTrue(any("config/permissions.json" in s for s in o["kullanici"]), o)
        self.assertEqual(o["guncelle_uygulama"], ["core/00-temel.md"], o)

    def test_template_denetle_geriye_uyumlu(self):
        """Eski 2'li sözleşme duruyor: %guncelle satırları listede kalır, 'sapma' saymaz."""
        self.yaz(self.k / "core/00-temel.md", "template güncellendi\n")
        self.commit_et("guncelle: v0.5.0 kalemler K1", bm.GUNCELLE_EPOSTA)
        durum, satirlar = bm.template_denetle(self.k)
        self.assertEqual(durum, "es", satirlar)
        self.assertTrue(any("core/00-temel.md" in s for s in satirlar), satirlar)

    def test_atfedilemeyen_merge_dosyasi_kullaniciya_yazilir(self):
        """Temkinli geri düşüş çivisi: `--no-merges` log'unda GÖRÜNMEYEN merge içeriği (evil merge) atfedilemez.

        Atfedilemeyen dosya `%guncelle` sınıfına düşerse, bir merge commit'ine gizlenen yüzey değişikliği
        sessizce INFO'ya iner. Ölçüldü (mutasyon M3, 2026-09-18): bu test olmadan o kural KORUMASIZDI.
        """
        self.git(self.k, "checkout", "-q", "-b", "yan")
        self.yaz(self.k / "config/permissions.json", "yan dal\n")
        self.commit_et("guncelle: v0.5.0 kalemler K9", bm.GUNCELLE_EPOSTA)
        self.git(self.k, "checkout", "-q", "main")
        self.yaz(self.k / "core/00-temel.md", "ana dal\n")
        self.commit_et("guncelle: v0.5.0 kalemler K1", bm.GUNCELLE_EPOSTA)
        self.git(self.k, "merge", "--no-ff", "--no-commit", "-q", "yan", kontrol=False)
        self.yaz(self.k / "AGENTS.md", "merge sırasında elle eklendi\n")  # evil merge: hiçbir non-merge commit'te yok
        self.git(self.k, "add", "-A")
        self.git(self.k, "commit", "-q", "-m", "merge")
        o = bm.template_sinifla(self.k)
        self.assertEqual(o["durum"], "sapma", o)
        self.assertTrue(any("AGENTS.md" in s for s in o["kullanici"]), o)
        # kontrol grubu: atfedilebilen iki dosya DOĞRU sınıfta kaldı (test "her şeyi kullanıcı yap" ile de geçmesin)
        self.assertEqual(sorted(o["guncelle_uygulama"]), ["config/permissions.json", "core/00-temel.md"], o)

    def test_temiz_klonda_hicbir_sinif_dolmaz(self):
        """Yanlış-pozitif kontrol grubu: hiç yerel commit yokken üç sınıf da BOŞ olmalı.

        `notlar` da boş olmalı — aksi hâlde ölçüm HİÇ yapılmamış (upstream tanımsız) ama test
        "üç sınıf boş" diye yeşil kalır: boşluk sebebi 'sapma yok' değil 'ölçülemedi' olurdu.
        """
        o = bm.template_sinifla(self.k)
        self.assertEqual((o["durum"], o["kullanici"], o["guncelle_anlik"], o["guncelle_uygulama"]), ("es", [], [], []), o)
        self.assertEqual(o["notlar"], [], "ölçüm yapılamamış; boşluk 'temiz' anlamına gelmiyor")

    def test_guncelle_kimligi_kaynakla_es(self):
        """Sabitler `scripts/guncelle.py`'den KOPYADIR — kaynak değişirse bu test kırılsın."""
        metin = (AXET_HOME / "scripts" / "guncelle.py").read_text(encoding="utf-8")
        self.assertIn(f"user.email={bm.GUNCELLE_EPOSTA}", metin)
        self.assertIn(f'f"{bm.GUNCELLE_ANLIK_ONEKI} ', metin)
