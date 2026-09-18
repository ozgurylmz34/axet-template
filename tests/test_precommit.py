# -*- coding: utf-8 -*-
"""project_precommit.py + .githooks/pre-commit — gerçek git reposunda; uçtan uca iki vaka gerçek `git commit` ile."""
from __future__ import annotations

from _helpers import ABAP_TEMIZ, ABAP_TYPE_C, GeciciTest  # önce: scripts/ yolunu ekler
import project_precommit as pc

SINIF = "SOURCE_CODES/SD/ZSD001_CLC/classes/zcl_sd001_helper.clas.abap"


class PrecommitTest(GeciciTest):
    def setUp(self) -> None:
        super().setUp()
        self.d = self.proje(sap=True)
        self.paket(self.d, "ZSD001_CLC")

    def stage(self, rel: str, metin: str, zorla: bool = False) -> None:
        self.yaz(self.d / rel, metin)
        self.git(self.d, "add", *(["-f"] if zorla else []), rel)

    def denetle(self):
        return self.calistir("project_precommit.py", "--project-dir", str(self.d))

    def commit(self):
        return self.git(self.d, "commit", "-q", "-m", "deneme", kontrol=False)

    def commit_sayisi(self) -> int:
        r = self.git(self.d, "rev-list", "--count", "HEAD", kontrol=False)
        return int(r.stdout.strip()) if r.returncode == 0 else 0

    # --- uçtan uca (git hook) ---
    def test_uctan_uca_temiz_commit_gecer(self):
        self.git(self.d, "add", "-A")
        r = self.commit()
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertEqual(self.commit_sayisi(), 1)

    def test_uctan_uca_conn_adt_engellenir(self):
        self.git(self.d, "add", "-A")
        self.stage(".conn_adt", "ORNEK=1\n", zorla=True)
        r = self.commit()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn(".conn_adt", self.cikti(r))
        self.assertEqual(self.commit_sayisi(), 0)

    def test_uctan_uca_runner_yoksa_engellenir(self):
        hook = self.d / ".githooks" / "pre-commit"
        metin = hook.read_text(encoding="utf-8")
        self.yaz(hook, metin.replace("scripts/project_precommit.py", "scripts/yok_boyle_bir_dosya.py"))
        self.git(self.d, "add", "-A")
        r = self.commit()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("bulunamadı", self.cikti(r))
        self.assertEqual(self.commit_sayisi(), 0)

    # --- kimlik dosyası ---
    def test_kimlik_dosyasi_siniflamasi(self):
        engel = [".conn_adt", "alt/derin/.conn_adt.bak", ".conn_prod", "conn/sistem1", "x.env", ".env", ".env.local",
                 "secrets/a.txt", "a/secrets/b.json", ".saml_cookies.json", "sap_saml_cookies.json", ".csrf_token.json"]
        serbest = [".conn_adt.example", "conn/sistem1.example", "conn/README.md", ".env.example", "a/conn/x",
                   "docs/secrets.md", "connection.md", "env.md"]
        for y in engel:
            self.assertIsNotNone(pc.kimlik_dosyasi_mi(y), y)
        for y in serbest:
            self.assertIsNone(pc.kimlik_dosyasi_mi(y), y)

    def test_ornek_dosyalar_serbest(self):
        self.stage(".conn_adt.example", "SAP_HOST=<HOST>\nSAP_PASSWORD=<PASSWORD>\n", zorla=True)
        self.stage(".env.example", "SAP_PASSWORD=${SAP_PASSWORD}\n", zorla=True)
        r = self.denetle()
        self.assertEqual(r.returncode, 0, self.cikti(r))

    def test_derin_turev_engellenir(self):
        self.stage("alt/derin/.conn_adt.bak", "x\n", zorla=True)
        r = self.denetle()
        self.assertEqual(r.returncode, 1, self.cikti(r))
        self.assertIn("alt/derin/.conn_adt.bak", r.stdout)

    # --- sır içeriği ---
    def test_sir_icerigi_engellenir(self):
        vakalar = {
            "config.ini": "SAP_PASSWORD=hunter22x\n",
            "app.py": 'password = "S3cretValu3"\n',
            "anahtar.txt": "-----BEGIN " + "RSA PRIVATE KEY-----\nabc\n",
            "notlar.md": "token: " + "gh" + "p_" + "A1b2C3d4" * 5 + "\n",
            "baglanti.yaml": "url: https://kullanici:" + "Gizli123" + "@ornek.invalid/x\n",
        }
        for rel, metin in vakalar.items():
            with self.subTest(rel=rel):
                self.git(self.d, "reset", "-q", kontrol=False)
                self.stage(rel, metin)
                r = self.denetle()
                self.assertEqual(r.returncode, 1, f"{rel}: {self.cikti(r)}")
                self.assertIn("sır deseni", r.stdout)
                self.assertNotIn("hunter22x", r.stdout, "sır değeri çıktıya yazılmamalı")
                self.git(self.d, "rm", "-q", "--cached", rel)

    def test_yer_tutucu_ve_abap_serbest(self):
        self.stage("app.py", 'password = "<PASSWORD>"\napi_key = "${API_KEY}"\n')
        self.stage("config.ini", "SAP_PASSWORD=%SAP_PASSWORD%\n")
        self.stage("legacy/zeski.abap", "  LV_TOKEN = LS_RESP-TOKEN.\n  LV_PASSWORD = LS_X-PASSWORD_HASH.\n")
        r = self.denetle()
        self.assertEqual(r.returncode, 0, self.cikti(r))

    def test_yalniz_staged_icerik_taranir(self):
        self.stage("app.py", 'password = "S3cretValu3"\n')
        self.yaz(self.d / "app.py", "temiz = 1\n")  # çalışma ağacı temiz, index kirli
        self.assertEqual(self.denetle().returncode, 1)
        self.git(self.d, "add", "app.py")
        self.yaz(self.d / "app.py", 'password = "S3cretValu3"\n')  # index temiz, çalışma ağacı kirli
        r = self.denetle()
        self.assertEqual(r.returncode, 0, self.cikti(r))

    # --- paket adları ---
    def test_paket_adi_ihlali_engellenir(self):
        self.stage("SOURCE_CODES/SD/ZSD001_CLC/classes/zcl_yanlis.clas.abap", ABAP_TEMIZ)
        r = self.denetle()
        self.assertEqual(r.returncode, 1, self.cikti(r))
        self.assertIn("paket adlandırma", r.stdout)

    def test_sap_projesi_degilse_ad_ve_inceleme_atlanir(self):
        d = self.proje("genel")
        self.yaz(d / "SOURCE_CODES/SD/X/classes/zcl_yanlis.clas.abap", ABAP_TYPE_C)
        self.git(d, "add", "-A")
        r = self.calistir("project_precommit.py", "--project-dir", str(d))
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("SAP projesi değil", r.stdout)

    # --- validators-local ---
    def test_yerel_validator_sozlesmesi(self):
        self.yaz(self.d / "validators-local" / "check_tmp.py",
                 "import os, sys\nfrom pathlib import Path\n"
                 "s = Path(os.environ['AXET_STAGED_FILES']).read_text(encoding='utf-8').splitlines()\n"
                 "k = [y for y in s if y.endswith('.tmp')]\nprint('tmp staged: ' + ','.join(k) if k else 'temiz')\n"
                 "sys.exit(1 if k else 0)\n")
        self.yaz(self.d / "validators-local" / "_yardimci.py", "import sys\nsys.exit(1)\n")
        self.stage("a.tmp", "x\n")
        r = self.denetle()
        self.assertEqual(r.returncode, 1, self.cikti(r))
        self.assertIn("tmp staged: a.tmp", r.stdout)
        self.git(self.d, "rm", "-q", "--cached", "a.tmp")
        r = self.denetle()
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertNotIn("_yardimci.py", r.stdout)

    def test_yerel_validator_calistirilamadi_engeller(self):
        self.yaz(self.d / "validators-local" / "bozuk.py", "import sys\nsys.exit(3)\n")
        r = self.denetle()
        self.assertEqual(r.returncode, 1)
        self.assertIn("ÇALIŞTIRILAMADI", r.stdout)

    # --- SAP incelemesi (çevrimdışı) ---
    def test_sap_inceleme_blocker_engeller_temiz_gecer(self):
        self.stage(SINIF, ABAP_TYPE_C)
        r = self.denetle()
        self.assertEqual(r.returncode, 1, self.cikti(r))
        self.assertIn("check_method_param_type_c.py (BLOCKER)", r.stdout)
        self.assertNotIn("axet-review-", r.stdout, "geçici artefakt yolu çıktıya sızmamalı")
        self.stage(SINIF, ABAP_TEMIZ)
        r = self.denetle()
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("çevrimdışı gate'lerde BLOCKER yok", r.stdout)

    def test_ag_gerektiren_gate_calistirilmaz(self):
        self.stage(SINIF, ABAP_TEMIZ)
        r = self.denetle()
        self.assertIn("ÇALIŞTIRILMADI", r.stdout)
        self.assertIn("check_abaplint.py", r.stdout)

    # --- fail-closed ---
    def test_git_sorgusu_cokerse_engeller(self):
        self.git(self.d, "add", "-A")
        (self.d / ".git" / "index").write_bytes(b"bozuk-index" * 10)
        r = self.denetle()
        self.assertEqual(r.returncode, 1, self.cikti(r))
        self.assertIn("git sorgusu ÇÖKTÜ", r.stdout)
