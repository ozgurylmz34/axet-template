# -*- coding: utf-8 -*-
"""new_package.py — paket klasörü, .rules.md regex doldurma, PAKETLER.md listesi."""
from __future__ import annotations

from _helpers import GeciciTest


class NewPackageTest(GeciciTest):
    def test_paket_kurulur(self):
        d = self.proje(sap=True, git_init=False)
        pkg = self.paket(d, "ZSD001_CLC")
        kural = (pkg / ".rules.md").read_text(encoding="utf-8")
        self.assertIn("`^ZSD001_[PR]_[A-Z0-9_]+$`", kural)
        self.assertIn("`^ZCL_SD001_[A-Z0-9_]+$`", kural)
        self.assertNotRegex(kural, r"\{[A-Z_]+\}")
        for k in ("cds", "classes", "programs", "ref_docs"):
            self.assertTrue((pkg / k).is_dir(), k)
        self.assertIn("ZSD001_CLC", (d / "SOURCE_CODES" / "PAKETLER.md").read_text(encoding="utf-8"))
        r = self.calistir("new_package.py", "--index", "--check", "--project-dir", str(d))
        self.assertEqual(r.returncode, 0, self.cikti(r))

    # --- negatif ---
    def test_sap_projesi_degilse_red(self):
        d = self.proje(git_init=False)
        r = self.calistir("new_package.py", "ZSD001", "--title", "x", "--project-dir", str(d))
        self.assertEqual(r.returncode, 2)
        self.assertFalse((d / "SOURCE_CODES").exists())

    def test_gecersiz_adlar_red(self):
        """Adin GECERLILIK kuralini olcer (buyuk harf + `^[ZY][A-Z0-9_]{1,29}$`).

        ⛔ `--module SD` ZORUNLU: verilmezse modul paket adindan cikarilir, `MM001`/`ZSD-001`
        icin cikarilamaz ve rc=2 ad kuralindan DEGIL "modul cikarilamadi" korumasindan gelir.
        O hâlde ad kurali tumden silinse bile test yesil kalirdi (olculdu: 5/5 yesil, urun
        `zsd001` · `MM001` · `ZSD-001` klasorlerini yaratti). Bu yuzden HANGI korumanin
        konustugu da dogrulanir — her marker urun kodunda tek bir dalda basilir."""
        d = self.proje(sap=True, git_init=False)
        for ad, marker in (("zsd001", "büyük harf olmalı"),
                           ("MM001", "Z ya da Y ile başlamalı"),
                           ("ZSD-001", "Z ya da Y ile başlamalı")):
            r = self.calistir("new_package.py", ad, "--title", "x", "--module", "SD",
                              "--project-dir", str(d))
            self.assertEqual(r.returncode, 2, f"{ad}: {self.cikti(r)}")
            self.assertIn(marker, self.cikti(r), f"{ad}: red baska bir korumadan geldi")
            self.assertNotIn("modül çıkarılamadı", self.cikti(r), f"{ad}: modul korumasi maskeledi")
        self.assertFalse((d / "SOURCE_CODES" / "SD").exists())

    def test_gecerli_ad_kabul_edilir_kontrol_grubu(self):
        """Kontrol grubu: kural IHLAL EDILMEDIGINDE gecer — yukaridaki assertion'lar
        'her ad reddedilsin' diye asiri-siki yazilmis olamaz."""
        d = self.proje(sap=True, git_init=False)
        r = self.calistir("new_package.py", "ZSD002", "--title", "x", "--module", "SD",
                          "--project-dir", str(d))
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertTrue((d / "SOURCE_CODES" / "SD" / "ZSD002").is_dir())

    def test_ayni_paket_ikinci_kez_red(self):
        """Ayni paket adi ikinci kez acilamaz — IKI kol da olculur.

        ⛔ Ikinci kol (BASKA modul altinda ayni ad) ayri bir if'tir ve yol-carpismasi
        korumasi onu maskeler: yalniz o kol silindiginde test yesil kaliyordu (olculdu).
        Paket adi SAP'de global oldugu icin modul klasoru ayri olsa da cakisma gercektir."""
        d = self.proje(sap=True, git_init=False)
        self.paket(d, "ZSD001")
        # kol 1: ayni modul -> ayni yol
        r = self.calistir("new_package.py", "ZSD001", "--title", "x", "--project-dir", str(d))
        self.assertEqual(r.returncode, 1, self.cikti(r))
        # kol 2: BASKA modul -> yol farkli, ad ayni
        r2 = self.calistir("new_package.py", "ZSD001", "--title", "x", "--module", "MM",
                           "--project-dir", str(d))
        self.assertEqual(r2.returncode, 1, self.cikti(r2))
        self.assertFalse((d / "SOURCE_CODES" / "MM" / "ZSD001").exists(),
                         "capraz-modul ayni ad: paket yine de yaratildi")

    def test_bayat_liste_yakalanir(self):
        d = self.proje(sap=True, git_init=False)
        self.paket(d, "ZSD001")
        (d / "SOURCE_CODES" / "PAKETLER.md").write_text("# eski\n", encoding="utf-8")
        r = self.calistir("new_package.py", "--index", "--check", "--project-dir", str(d))
        self.assertEqual(r.returncode, 1, self.cikti(r))
