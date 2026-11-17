# -*- coding: utf-8 -*-
"""new_package.py — paket klasörü, .rules.md regex doldurma, PAKETLER.md listesi."""
from __future__ import annotations

import json
import shutil
from datetime import date

from _helpers import AXET_HOME, SCRIPTS, GeciciTest


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


# --- Müşteri namespace'i (kesin yasak A'nın müşteri ad alanı tanımı) ------------------------------------------
# Karar SAP paketindeki ad politikası modülünde; proje `sap-project.json` → `customer_namespaces` ile bildirir.
# Modül bildirimi yalnız bağlantı dosyasının dizinindeki projeye uygular → testte proje köküne İÇERİKSİZ bir
# `.conn_adt` konur (kimlik bilgisi yok; modül yalnız varlığına bakar) ve betik proje dizininde koşar.
class NamespacePaketTest(GeciciTest):
    NS_PAKET = "/NSPC/SD001_CLC"

    def ns_proje(self, namespaces=("/NSPC/",), baglanti: bool = True):
        d = self.proje(sap=True, git_init=False)
        f = d / "sap-project.json"
        veri = json.loads(f.read_text(encoding="utf-8"))
        if namespaces is not None:
            veri["customer_namespaces"] = list(namespaces)
        f.write_text(json.dumps(veri, indent=2, ensure_ascii=False), encoding="utf-8")
        if baglanti:
            (d / ".conn_adt").write_text("", encoding="utf-8")
        return d

    def kur(self, d, ad=None, *ek):
        return self.calistir("new_package.py", ad or self.NS_PAKET, "--title", "x", *ek, "--project-dir", str(d),
                             cwd=d)

    def test_bildirilmis_namespace_paketi_kurulur(self):
        d = self.ns_proje()
        r = self.kur(d)
        self.assertEqual(r.returncode, 0, self.cikti(r))
        pkg = d / "SOURCE_CODES" / "SD" / "#nspc#sd001_clc"
        self.assertTrue(pkg.is_dir(), self.cikti(r))
        kural = (pkg / ".rules.md").read_text(encoding="utf-8")
        self.assertIn("`^/NSPC/SD001_T_[A-Z0-9_]+$`", kural)
        self.assertIn("`^/NSPC/CL_SD001_[A-Z0-9_]+$`", kural)
        self.assertIn("Lock object (**DOĞRULANMADI**", kural)
        self.assertNotRegex(kural, r"\{[A-Z_]+\}")
        # sürücü köküne / proje dışına klasör açılmadı
        self.assertFalse((d / "SOURCE_CODES" / "SD" / "NSPC").exists())
        # ad kuralı denetimi namespace'li adla paketi bulur
        r2 = self.calistir("check_package_naming.py", "--package", self.NS_PAKET, "--project-dir", str(d))
        self.assertEqual(r2.returncode, 0, self.cikti(r2))
        # ikinci kez → zaten var
        self.assertEqual(self.kur(d).returncode, 1)

    def test_bildirilmemis_namespace_red(self):
        """SAP'nin kendi namespace'i ve listede olmayan namespace standarttır → klasör YOK."""
        d = self.ns_proje()
        for ad in ("/SCWM/SD001", "/OTHR/SD001_CLC"):
            r = self.kur(d, ad)
            self.assertEqual(r.returncode, 2, f"{ad}: {self.cikti(r)}")
            self.assertIn("müşteri ad alanında değil", self.cikti(r), ad)
        self.assertFalse((d / "SOURCE_CODES" / "SD").exists())

    def test_liste_yoksa_ya_da_baglanti_yoksa_red(self):
        for kw in ({"namespaces": None}, {"baglanti": False}):
            d = self.ns_proje(**kw)
            r = self.kur(d)
            self.assertEqual(r.returncode, 2, self.cikti(r))
            self.assertIn("müşteri ad alanında değil", self.cikti(r))
            self.assertFalse((d / "SOURCE_CODES" / "SD").exists())
            shutil.rmtree(d)

    def test_bozuk_namespace_adi_red(self):
        d = self.ns_proje()
        for ad in ("/NSPC/", "/NS/SD001", "/NSPC/SD-001", "/NSPC/SD001/X"):
            r = self.kur(d, ad)
            self.assertEqual(r.returncode, 2, f"{ad}: {self.cikti(r)}")
        self.assertFalse((d / "SOURCE_CODES" / "SD").exists())

    def test_msys_yola_cevrilmis_ad_ipucu_verir(self):
        """Git Bash `/NSPC/…` argümanını `C:/Program Files/Git/NSPC/…` yapar: red metni MSYS ipucu taşır (aXet tur 8)."""
        d = self.ns_proje()
        for ad in ("C:/Program Files/Git/NSPC/SD001_CLC", "C:\\Program Files\\Git\\NSPC\\SD001_CLC"):
            r = self.kur(d, ad)
            self.assertEqual(r.returncode, 2, f"{ad}: {self.cikti(r)}")
            self.assertIn("MSYS_NO_PATHCONV=1", self.cikti(r), ad)
            self.assertNotIn("büyük harf olmalı", self.cikti(r), ad)
        self.assertFalse((d / "SOURCE_CODES" / "SD").exists())

    def test_project_dir_ortam_degiskenini_ezer(self):
        """`--project-dir` verildiyse ad politikasının proje kökü O dizindir; ortamda kalmış eski
        AXET_SAP_PROJECT_DIR (başka proje) namespace kabulünü kapatmaz (eskiden `setdefault` onu koruyordu)."""
        d = self.ns_proje()
        baska = self.tmp / "baska"                    # kendi .conn_adt'si olan BAŞKA proje
        baska.mkdir()
        (baska / ".conn_adt").write_text("", encoding="utf-8")
        self.env["AXET_SAP_PROJECT_DIR"] = str(baska)
        r = self.kur(d)
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertTrue((d / "SOURCE_CODES" / "SD" / "#nspc#sd001_clc").is_dir(), self.cikti(r))
        self.assertFalse((baska / "SOURCE_CODES" / "SD").exists())

    def test_modul_yoksa_yalniz_zy_kontrol_grubu(self):
        """SAP paketi kurulu olmayan klon: ad politikası modülü yok → namespace RED, Z/Y aynen çalışır."""
        kok = self.tmp / "_klon"
        (kok / "scripts").mkdir(parents=True)
        shutil.copy2(SCRIPTS / "new_package.py", kok / "scripts" / "new_package.py")
        shutil.copytree(AXET_HOME / "templates" / "package", kok / "templates" / "package")
        d = self.ns_proje()
        yol = kok / "scripts" / "new_package.py"
        r = self.calistir(yol, self.NS_PAKET, "--title", "x", "--project-dir", str(d), cwd=d)
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn("ad politikası modülü bulunamadı", self.cikti(r))
        r2 = self.calistir(yol, "ZSD002", "--title", "x", "--project-dir", str(d), cwd=d)
        self.assertEqual(r2.returncode, 0, self.cikti(r2))
        kural = (d / "SOURCE_CODES" / "SD" / "ZSD002" / ".rules.md").read_text(encoding="utf-8")
        self.assertIn("| Lock object | `EZSD002_*` | `^EZSD002_[A-Z0-9_]+$` |", kural)


# --- Z146: sonradan kurulum kipi (--mevcut) -------------------------------------------------------------------
# SAP'de zaten olan paket için klasör kurulurken Owner / başlangıç / üst paket canlıdan SALT-OKUR okunur. Testte
# canlı yok: `AXET_SAP_ADT_CLI` sahte CLI'yi gösterir. Sahte, her çağrının argümanlarını kayıt dosyasına yazar
# (kod yolundan GERÇEKTEN veri geçtiğini ölçmek için) ve sorgudaki tabloya göre yanıt verir.
SAHTE_CLI = r'''
import json, os, sys
argv = sys.argv[1:]
cfg = json.load(open(os.environ["AXET_TEST_CLI_CFG"], encoding="utf-8"))
with open(os.environ["AXET_TEST_CLI_KAYIT"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps(argv, ensure_ascii=False) + "\n")
args = json.loads(argv[argv.index("--args-json") + 1])
tablo = "tadir" if " tadir " in args["query"].lower() else "tdevc"
if cfg.get("rc"):
    print(json.dumps({"ok": False, "tool": argv[0], "result": None,
                      "error": {"code": "connection_error", "message": "sahte: bağlantı yok"}}))
    sys.exit(cfg["rc"])
satirlar = cfg.get(tablo, [])
print(json.dumps({"ok": True, "tool": argv[0], "class": "read", "error": None,
                  "result": {"ok": True, "row_count": len(satirlar), "truncated": False, "rows": satirlar}}))
'''


class MevcutPaketTest(GeciciTest):
    PAKET = "ZSD001"

    def setUp(self) -> None:
        super().setUp()
        self.cli = self.yaz(self.tmp / "_sahte_cli.py", SAHTE_CLI)
        self.cfg = self.tmp / "_cli_cfg.json"
        self.kayit = self.tmp / "_cli_kayit.jsonl"
        self.env.update({"AXET_SAP_ADT_CLI": str(self.cli), "AXET_TEST_CLI_CFG": str(self.cfg),
                         "AXET_TEST_CLI_KAYIT": str(self.kayit)})
        self.d = self.proje(sap=True, git_init=False)
        self.hedef = self.d / "SOURCE_CODES" / "SD" / self.PAKET

    def canli(self, author="ZXXUSER1", created_on="20260415", parent="ZXX", rc=0, var=True) -> None:
        tadir = [{"AUTHOR": author, "CREATED_ON": created_on}] if var else []
        tdevc = [{"DEVCLASS": self.PAKET, "PARENTCL": parent}] if var else []
        self.cfg.write_text(json.dumps({"tadir": tadir, "tdevc": tdevc, "rc": rc}), encoding="utf-8")

    def kur(self, *ek: str):
        return self.calistir("new_package.py", self.PAKET, "--title", "Deneme", "--mevcut", *ek,
                             "--project-dir", str(self.d))

    def cagrilar(self) -> list[list[str]]:
        if not self.kayit.is_file():
            return []
        return [json.loads(s) for s in self.kayit.read_text(encoding="utf-8").splitlines() if s.strip()]

    def test_owner_baslangic_ust_paket_canlidan_dolar(self):
        self.canli()
        r = self.kur()
        self.assertEqual(r.returncode, 0, self.cikti(r))
        kural = (self.hedef / ".rules.md").read_text(encoding="utf-8")
        readme = (self.hedef / "README.md").read_text(encoding="utf-8")
        self.assertIn("- **Owner:** ZXXUSER1", kural)
        self.assertIn("**Başlangıç:** 2026-04-15", readme)
        self.assertIn("**Owner:** ZXXUSER1", readme)
        self.assertIn("- Üst paket: `ZXX`", kural)
        self.assertNotIn("<OWNER>", kural + readme)
        self.assertIn("TADIR.AUTHOR", kural, "Owner'ın kaynağı .rules.md'de yazılı değil")
        self.assertIn("DOĞRULANMADI", kural, "doğrulanmamış şablon iddiası etiketsiz")
        self.assertIn("ZXXUSER1", (self.d / "SOURCE_CODES" / "PAKETLER.md").read_text(encoding="utf-8"))
        # Kod yolundan GERÇEKTEN veri geçti: iki salt-okur sorgu, doğru tablo/anahtar, yazma bayrağı yok.
        cagri = self.cagrilar()
        self.assertEqual(len(cagri), 2, cagri)
        sorgular = " | ".join(json.loads(c[c.index("--args-json") + 1])["query"] for c in cagri)
        for parca in ("tadir", "'R3TR'", "'DEVC'", "'ZSD001'", "tdevc", "parentcl"):
            self.assertIn(parca, sorgular.lower() if parca.islower() else sorgular)
        self.assertTrue(all(c[0] == "adt_sql_query" and "--sap-write" not in c for c in cagri), cagri)
        self.assertTrue(all(c[c.index("--project-dir") + 1] == str(self.d) for c in cagri), cagri)

    def test_owner_canlida_yoksa_sorulur_varsayilan_yazilmaz(self):
        for bos in ("", None):
            self.canli(author=bos)
            r = self.kur()
            self.assertEqual(r.returncode, 2, self.cikti(r))
            self.assertIn("--owner", self.cikti(r))
            self.assertIn("SOR", self.cikti(r))
            self.assertFalse(self.hedef.exists(), "Owner kanıtsızken klasör yazıldı")

    def test_owner_canlida_yoksa_kullanici_cevabi_yazilir(self):
        self.canli(author="")
        r = self.kur("--owner", "ZXXUSER2")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        kural = (self.hedef / ".rules.md").read_text(encoding="utf-8")
        self.assertIn("- **Owner:** ZXXUSER2", kural)
        self.assertIn("**Owner:** ZXXUSER2", (self.hedef / "README.md").read_text(encoding="utf-8"))

    def test_owner_celiskisi_red(self):
        self.canli(author="ZXXUSER1")
        r = self.kur("--owner", "ZXXUSER9")
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn("ZXXUSER1", self.cikti(r))
        self.assertFalse(self.hedef.exists())

    def test_ayni_owner_verilirse_kabul(self):
        """Kontrol grubu: --owner canlıyla AYNIYSA çelişki yok — yukarıdaki red aşırı-sıkı değil."""
        self.canli(author="ZXXUSER1")
        r = self.kur("--owner", "zxxuser1")
        self.assertEqual(r.returncode, 0, self.cikti(r))

    def test_canli_okunamazsa_fail_closed(self):
        self.canli(rc=1)
        r = self.kur("--owner", "ZXXUSER2")
        self.assertEqual(r.returncode, 3, self.cikti(r))
        self.assertIn("ÖLÇÜLEMEDİ", self.cikti(r))
        self.assertFalse(self.hedef.exists())

    def test_cli_yoksa_fail_closed(self):
        self.env["AXET_SAP_ADT_CLI"] = str(self.tmp / "yok.py")
        r = self.kur("--owner", "ZXXUSER2")
        self.assertEqual(r.returncode, 3, self.cikti(r))
        self.assertFalse(self.hedef.exists())

    def test_paket_canlida_yoksa_red(self):
        self.canli(var=False)
        r = self.kur("--owner", "ZXXUSER2")
        self.assertEqual(r.returncode, 3, self.cikti(r))
        self.assertIn("bulunamadı", self.cikti(r))
        self.assertFalse(self.hedef.exists())

    def test_gecersiz_tarih_dogrulanmadi_etiketli(self):
        self.canli(created_on="00000000")
        r = self.kur()
        self.assertEqual(r.returncode, 0, self.cikti(r))
        readme = (self.hedef / "README.md").read_text(encoding="utf-8")
        self.assertIn("**Başlangıç:** DOĞRULANMADI", readme)

    def test_normal_kip_canliya_gitmez_kontrol_grubu(self):
        """Kontrol grubu: --mevcut YOKKEN CLI çağrılmaz, eski davranış aynen (Başlangıç = bugün, <OWNER>)."""
        self.canli()
        r = self.calistir("new_package.py", self.PAKET, "--title", "Deneme", "--project-dir", str(self.d))
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertEqual(self.cagrilar(), [])
        readme = (self.hedef / "README.md").read_text(encoding="utf-8")
        self.assertIn(f"**Başlangıç:** {date.today().isoformat()}", readme)
        self.assertIn("**Owner:** <OWNER>", readme)
        self.assertNotIn("DOĞRULANMADI", (self.hedef / ".rules.md").read_text(encoding="utf-8"))
