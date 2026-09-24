# -*- coding: utf-8 -*-
"""new_project.py — iskelet, ezmeme, pre-commit kablolaması, SAP damgası."""
from __future__ import annotations

from _helpers import AXET_HOME, GeciciTest  # önce: scripts/ yolunu ekler
import sap_stamp


class NewProjectTest(GeciciTest):
    def test_iskelet_ve_hook_kablolama(self):
        d = self.proje()
        for rel in ("AGENTS.md", ".axet-code.json", ".gitignore", ".gitattributes", ".axetcode-denylist",
                    ".githooks/pre-commit", "validators-local/README.md", ".axet-code/memory/project_is-listesi.md"):
            self.assertTrue((d / rel).is_file(), rel)
        agents = (d / "AGENTS.md").read_text(encoding="utf-8")
        self.assertNotIn("<PROJE_ADI>", agents)
        self.assertNotIn("<AXET_HOME>", agents)
        hook = (d / ".githooks" / "pre-commit").read_bytes()
        self.assertNotIn(b"\r", hook, "hook CRLF yazıldı — sh çalıştırmaz")
        self.assertIn(b"project_precommit.py", hook)
        self.assertNotIn(b"<AXET_HOME>", hook)
        self.assertEqual(self.git(d, "config", "--get", "core.hooksPath").stdout.strip(), ".githooks")
        self.assertIn(".axet-code/behavior-manifest.json", (d / ".axetcode-denylist").read_text(encoding="utf-8"))

    def test_dry_run_hicbir_sey_yazmaz(self):
        d = self.tmp / "p"
        d.mkdir()
        self.git(d, "init", "-q")
        r = self.calistir("new_project.py", str(d), "--dry-run")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertFalse((d / "AGENTS.md").exists())
        self.assertEqual(self.git(d, "config", "--get", "core.hooksPath", kontrol=False).stdout.strip(), "")

    # --- negatif ---
    def test_var_olan_dosya_ezilmez(self):
        d = self.proje()
        (d / "AGENTS.md").write_text("# benim\n", encoding="utf-8")
        r = self.calistir("new_project.py", str(d))
        self.assertEqual(r.returncode, 0)
        self.assertIn("VAR, dokunulmadı", r.stdout)
        self.assertEqual((d / "AGENTS.md").read_text(encoding="utf-8"), "# benim\n")

    def test_template_icine_kurulmaz(self):
        hedef = AXET_HOME / "templates"
        once = sorted(p.name for p in hedef.iterdir())
        r = self.calistir("new_project.py", str(hedef))
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertEqual(sorted(p.name for p in hedef.iterdir()), once)

    def test_git_reposu_degilse_komut_basar(self):
        d = self.proje(git_init=False)
        r = self.calistir("new_project.py", str(d))
        self.assertIn("git reposu değil", r.stdout)
        self.assertFalse((d / ".git").exists())

    def test_baska_hookspath_ezilmez(self):
        d = self.proje()
        self.git(d, "config", "core.hooksPath", "kurumsal-hooks")
        r = self.calistir("new_project.py", str(d))
        self.assertIn("dokunulmadı", r.stdout)
        self.assertEqual(self.git(d, "config", "--get", "core.hooksPath").stdout.strip(), "kurumsal-hooks")

    def test_alt_dizin_repo_koku_degil(self):
        kok = self.tmp / "repo"
        kok.mkdir()
        self.git(kok, "init", "-q")
        alt = kok / "alt"
        alt.mkdir()
        r = self.calistir("new_project.py", str(alt))
        self.assertIn("repo kökü değil", r.stdout)
        self.assertEqual(self.git(kok, "config", "--get", "core.hooksPath", kontrol=False).stdout.strip(), "")

    def test_sap_damga_ve_bozuk_damga(self):
        d = self.proje(sap=True)
        self.assertTrue((d / "sap-project.json").is_file())
        metin = (d / "AGENTS.md").read_text(encoding="utf-8")
        self.assertEqual(sap_stamp.denetle(metin)[0], "guncel")
        bozuk = metin + "\n" + sap_stamp.BASLA + "\nkopya\n" + sap_stamp.BITIR + "\n"
        (d / "AGENTS.md").write_text(bozuk, encoding="utf-8")
        r = self.calistir("new_project.py", str(d), "--sap")
        self.assertEqual(r.returncode, 1, self.cikti(r))
        self.assertIn("damga BOZUK", r.stdout)
        self.assertEqual((d / "AGENTS.md").read_text(encoding="utf-8"), bozuk)
        # gate F2: --no-next-steps çıkış kodunu değiştirmez (yeni_proje.py kur akışı bu koda dayanır)
        r = self.calistir("new_project.py", str(d), "--sap", "--no-next-steps")
        self.assertEqual(r.returncode, 1, self.cikti(r))
        self.assertIn("damga BOZUK", r.stdout)
        self.assertNotIn("Sonraki adımlar", r.stdout)

    def test_sap_conn_readme_makine_yolu_tasimaz(self):
        # Z83: conn/README.md git'e AÇIK tutulur (`conn/*` + `!conn/README.md`) ⇒ klonun mutlak yolunu taşımamalı
        d = self.proje(sap=True)
        readme = d / "conn" / "README.md"
        self.assertTrue(readme.is_file())
        metin = readme.read_text(encoding="utf-8")
        self.assertNotIn("<AXET_HOME>", metin)
        self.assertNotIn(AXET_HOME.resolve().as_posix(), metin)
        self.assertIn("setup_credentials.py", metin)
        # kontrol grubu: dosya gerçekten git'e açık (kapalı olsaydı yol taşıması zararsız olurdu)
        r = self.git(d, "check-ignore", "-q", "conn/README.md", kontrol=False)
        self.assertEqual(r.returncode, 1, "conn/README.md git'e kapalı görünüyor — test varsayımı geçersiz")

    def test_sap_sonraki_adimlar_profil_alanlarini_soyler(self):
        d = self.tmp / "sap"
        d.mkdir()
        self.git(d, "init", "-q", "-b", "main")
        r = self.calistir("new_project.py", str(d), "--sap")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("sap_profile, release, master_language, cleancore_policy", r.stdout)
        # kontrol grubu: SAP'siz kurulum profil satırı basmaz
        k = self.tmp / "genel"
        k.mkdir()
        self.git(k, "init", "-q", "-b", "main")
        r2 = self.calistir("new_project.py", str(k))
        self.assertEqual(r2.returncode, 0, self.cikti(r2))
        self.assertNotIn("sap_profile", r2.stdout)

    def test_no_next_steps_yalniz_sonraki_adimlari_atar(self):
        d = self.tmp / "nns"
        d.mkdir()
        self.git(d, "init", "-q", "-b", "main")
        ilk = self.calistir("new_project.py", str(d), "--sap", "--no-next-steps")
        self.assertEqual(ilk.returncode, 0, self.cikti(ilk))
        self.assertTrue((d / "AGENTS.md").is_file() and (d / "sap-project.json").is_file(), "iskelet kurulmadı")
        self.assertIn("[oluşturuldu]", ilk.stdout)
        self.assertNotIn("Sonraki adımlar", ilk.stdout)
        self.assertNotIn("behavior_manifest.py", ilk.stdout)
        # kontrol grubu: aynı durumda bayraksız çıktı = bayraklı çıktı + "Sonraki adımlar" bölümü (başka fark yok)
        bayraksiz = self.calistir("new_project.py", str(d), "--sap")
        bayrakli = self.calistir("new_project.py", str(d), "--sap", "--no-next-steps")
        self.assertEqual((bayraksiz.returncode, bayrakli.returncode), (0, 0), self.cikti(bayraksiz) + self.cikti(bayrakli))
        self.assertIn("\nSonraki adımlar:\n", bayraksiz.stdout)
        self.assertEqual(bayrakli.stdout, bayraksiz.stdout.split("Sonraki adımlar:")[0])
        self.assertIn("Proje: ", bayrakli.stdout, "özet satırı kalmalı")
