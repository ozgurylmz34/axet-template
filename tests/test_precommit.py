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
        # K-O①: FAIL anında "kuralı değiştirme" hatırlatması basılır
        self.assertIn("HATIRLATMA: düzeltme = içeriği düzeltmek", r.stdout)

    # --- K-O② (2026-09-18): .rules.md Naming/istisna değişikliği WARN ---
    KURAL = "SOURCE_CODES/SD/ZSD001_CLC/.rules.md"

    def _ilk_commit(self) -> None:
        self.git(self.d, "add", "-A")
        r = self.commit()
        self.assertEqual(r.returncode, 0, self.cikti(r))

    def _class_satiri_genislet(self) -> str:
        """Class satırının regex'ini `^Z[A-Z0-9_]+$`e genişletir; eski regex'i döndürür."""
        metin = (self.d / self.KURAL).read_text(encoding="utf-8")
        satir = next(s for s in metin.splitlines() if s.startswith("| Class"))
        eski = satir.rsplit("`", 2)[1]
        self.yaz(self.d / self.KURAL, metin.replace(satir, satir.replace(f"`{eski}`", "`^Z[A-Z0-9_]+$`")))
        self.git(self.d, "add", self.KURAL)
        return eski

    def test_naming_genisletilirse_WARN_eski_yeni_gosterilir(self):
        """Ölçülen vaka: FAIL alan model regex'i kendi adını kapsayacak şekilde genişletip aynı
        commit'e koydu; adlandırma denetimi `.rules.md`'yi diskten okuduğu için GEÇTİ."""
        self._ilk_commit()
        eski = self._class_satiri_genislet()
        self.stage("SOURCE_CODES/SD/ZSD001_CLC/classes/zcl_yanlis.clas.abap", ABAP_TEMIZ)
        r = self.denetle()
        self.assertEqual(r.returncode, 0, "WARN engellememeli: " + self.cikti(r))
        uyari = [s for s in r.stdout.splitlines() if s.startswith("[WARN] kural değişikliği")]
        self.assertEqual(len(uyari), 1, r.stdout)
        self.assertIn(f"`{eski}` → `^Z[A-Z0-9_]+$`", uyari[0])
        self.assertIn(self.KURAL, uyari[0])

    def test_yalniz_obje_eklenirse_WARN_yok(self):
        """KONTROL GRUBU: kural değişmeden obje eklemek uyarı üretmez."""
        self._ilk_commit()
        self.stage(SINIF, ABAP_TEMIZ)
        r = self.denetle()
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertNotIn("kural değişikliği", r.stdout)

    def test_ilk_kez_eklenen_rules_md_WARN_uretmez(self):
        """Yeni paket: `.rules.md` HEAD'de yok ⇒ "genişleme" yok. Hem hiç commit'siz repo hem de
        commit'li repoya eklenen ikinci paket."""
        self.git(self.d, "add", "-A")
        r = self.denetle()   # repo hiç commit almamış
        self.assertNotIn("kural değişikliği", r.stdout, self.cikti(r))
        self._ilk_commit()
        self.paket(self.d, "ZSD002_CLC")
        self.git(self.d, "add", "-A")
        r = self.denetle()
        self.assertIn("SOURCE_CODES/SD/ZSD002_CLC/.rules.md",
                      self.git(self.d, "diff", "--cached", "--name-only").stdout, "kontrol: yeni kural staged")
        self.assertNotIn("kural değişikliği", r.stdout, self.cikti(r))

    def test_istisna_eklenirse_WARN(self):
        """Aynı sınıf, başka kapı: adı regex'e uydurmak yerine "Bilinen istisnalar"a eklemek."""
        self._ilk_commit()
        metin = (self.d / self.KURAL).read_text(encoding="utf-8")
        self.assertIn("## Bilinen istisnalar", metin, "kontrol: şablonda istisna bölümü var")
        self.yaz(self.d / self.KURAL, metin.replace("## Bilinen istisnalar\n",
                                                    "## Bilinen istisnalar\n- `ZCL_YANLIS` — deneme\n"))
        self.git(self.d, "add", self.KURAL)
        r = self.denetle()
        self.assertIn("yeni istisna: ZCL_YANLIS", r.stdout, self.cikti(r))

    def test_stagelenmemis_genisletme_de_WARN(self):
        """Bug gate 2026-09-19 #3 (ölçüldü): adlandırma denetimi `.rules.md`'yi DİSKTEN okur, fark
        denetimi STAGED içerikten ⇒ stage'lenmemiş genişletme denetimi geçiriyor, WARN hiç çıkmıyordu."""
        self._ilk_commit()
        self._class_satiri_genislet()
        self.git(self.d, "reset", "-q", "--", self.KURAL)   # genişletme yalnız diskte
        self.stage("SOURCE_CODES/SD/ZSD001_CLC/classes/zcl_yanlis.clas.abap", ABAP_TEMIZ)
        r = self.denetle()
        # kontrol grubu: adlandırma gerçekten diskteki genişletilmiş regex'le GEÇTİ (yoksa vaka yok)
        self.assertEqual(r.returncode, 0, self.cikti(r))
        uyari = [s for s in r.stdout.splitlines()
                 if s.startswith("[WARN] kural değişikliği") and "STAGE'LENMEMİŞ" in s]
        self.assertEqual(len(uyari), 1, r.stdout)
        self.assertIn(self.KURAL, uyari[0])

    def test_stagelenmemis_kural_ilgisiz_committe_WARN_uretmez(self):
        """Kontrol grubu (ikinci tur, ölçüldü): pakette staged dosya yoksa o kuralı bu commit'te hiçbir
        denetim okumaz ⇒ uyarı gürültüdür."""
        self._ilk_commit()
        self._class_satiri_genislet()
        self.git(self.d, "reset", "-q", "--", self.KURAL)
        self.stage("notlar/ilgisiz.md", "ilgisiz\n")
        r = self.denetle()
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertNotIn("STAGE'LENMEMİŞ", r.stdout, self.cikti(r))

    def test_stagelenmemis_kural_pakette_yalniz_obje_disi_dosya_varken_WARN_uretmez(self):
        """Üçüncü tur (ölçüldü): pakette yalnız obje-dışı dosya (SESSION_NOTES.md) stage'liyken adlandırma
        denetimi kuralı OKUMAZ ⇒ uyarı gürültüdür."""
        self._ilk_commit()
        self._class_satiri_genislet()
        self.git(self.d, "reset", "-q", "--", self.KURAL)
        self.stage("SOURCE_CODES/SD/ZSD001_CLC/SESSION_NOTES.md", "not\n")
        r = self.denetle()
        self.assertNotIn("STAGE'LENMEMİŞ", r.stdout, self.cikti(r))

    def test_ascii_olmayan_yola_tasinan_rules_md_de_WARN(self):
        """Üçüncü tur (ölçüldü): `-z`'siz `--name-status` ASCII olmayan yolu tırnaklıyordu ⇒ taşınan kural
        "ilk kayıt" sayılıp uyarı çıkmıyordu."""
        self._ilk_commit()
        self._class_satiri_genislet()
        self.git(self.d, "mv", "SOURCE_CODES/SD/ZSD001_CLC", "SOURCE_CODES/SD/ZSD001_ÇLC")
        yeni = "SOURCE_CODES/SD/ZSD001_ÇLC/.rules.md"
        r = self.denetle()
        uyari = [s for s in r.stdout.splitlines() if s.startswith("[WARN] kural değişikliği") and yeni in s]
        self.assertEqual(len(uyari), 1, self.cikti(r))

    def test_yeniden_adlandirilan_rules_md_ilk_kayit_sayilmaz(self):
        """Bug gate 2026-09-19 #3: paket klasörü taşınıp kural aynı commit'te genişletilirse `.rules.md`
        HEAD'de yeni yolda yoktur ⇒ eskiden "ilk kayıt" sayılıp WARN atlanıyordu."""
        self._ilk_commit()
        self._class_satiri_genislet()
        self.git(self.d, "mv", "SOURCE_CODES/SD/ZSD001_CLC", "SOURCE_CODES/SD/ZSD001_TASINDI")
        yeni = "SOURCE_CODES/SD/ZSD001_TASINDI/.rules.md"
        # kontrol grubu: git bunu gerçekten yeniden adlandırma olarak görüyor
        durum = self.git(self.d, "diff", "--cached", "-M", "--name-status", "HEAD").stdout
        self.assertTrue(any(s.startswith("R") and s.endswith(yeni) for s in durum.splitlines()), durum)
        r = self.denetle()
        uyari = [s for s in r.stdout.splitlines() if s.startswith("[WARN] kural değişikliği") and yeni in s]
        self.assertEqual(len(uyari), 1, self.cikti(r))
        self.assertIn("`^Z[A-Z0-9_]+$`", uyari[0])

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
