# -*- coding: utf-8 -*-
"""`%guncelle` başlatıcı skill'i (P4/B1) + motor sürüm testi (P4/B2).

Neyi ölçer: `skills/guncelle/SKILL.md`'nin aXet'e yüklenebilir olduğunu (klasör/ad/frontmatter),
K4'ü ihlal etmediğini (kendi script'i YOK) ve içindeki **kanonik motor-çıkarma komut bloğunun**
gerçekten çalıştığını — yerel `scripts/guncelle.py` BOZUKKEN bile.

⛔ Neden komut bloğu belgeden PARSE ediliyor: elle kopyalanan bir komut listesi belgeyle
sessizce ayrışır ve test "çalışıyor" derken kullanıcı bambaşka bir komut görür. Blok tek
kaynaktır; belge değişirse bu test onu koşar.
"""
from __future__ import annotations

import json
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from _helpers import AXET_HOME, GeciciTest  # önce: scripts/ yolunu ekler
import doctor

SKILL = AXET_HOME / "skills" / "guncelle" / "SKILL.md"
BASLA, BITIR = "<!-- MOTOR-CIKAR:BASLA -->", "<!-- MOTOR-CIKAR:BITIR -->"


def komut_blogu(metin: str) -> list[str]:
    """İki işaret arasındaki tek kod bloğunun komut satırları (yorum ve boş satır atılır)."""
    i, j = metin.find(BASLA), metin.find(BITIR)
    if i < 0 or j < 0 or j < i:
        raise AssertionError(f"kanonik motor-çıkarma bloğu yok ({BASLA} … {BITIR})")
    govde = metin[i + len(BASLA):j]
    kodlar = re.findall(r"```[a-zA-Z]*\n(.*?)```", govde, re.S)
    if len(kodlar) != 1:
        raise AssertionError(f"işaretler arasında TAM 1 kod bloğu olmalı, {len(kodlar)} bulundu")
    return [s.strip() for s in kodlar[0].splitlines() if s.strip() and not s.strip().startswith("#")]


class BaslaticiSkillTest(GeciciTest):
    """B1 — skill gövdesi aXet'in yükleme sözleşmesine uyuyor mu."""

    def setUp(self) -> None:
        super().setUp()
        self.assertTrue(SKILL.exists(), f"{SKILL} yok")
        self.metin = SKILL.read_text(encoding="utf-8")

    def test_klasor_adi_frontmatter_adiyla_ayni(self):
        m = re.search(r"^name:\s*(\S+)", self.metin, re.M)
        self.assertIsNotNone(m, "frontmatter 'name' yok")
        self.assertEqual(m.group(1), SKILL.parent.name)

    def test_frontmatter_axet_sozlesmesine_uyar(self):
        """doctor'ın KENDİ denetimi (kopya ölçüt yok): boş liste = aXet skill'i düşürmez."""
        self.assertEqual(doctor.frontmatter_problems(self.metin), [])

    def test_description_blok_stili_ve_1024_siniri(self):
        """`>` blok stili zorunlu: tek satırlık değerde `: ` geçerse aXet skill'i SESSİZCE düşürür."""
        m = re.search(r"^description:(.*)$", self.metin, re.M)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1).strip(), ">", "description `>` blok stiliyle yazılmalı")
        govde = re.search(r"^description:\s*>\n((?:^[ \t]+.*\n)+)", self.metin, re.M)
        self.assertIsNotNone(govde, "description blok gövdesi okunamadı")
        self.assertLessEqual(len(" ".join(govde.group(1).split())), 1024)

    def test_k4_skill_kendi_scriptini_tasimaz(self):
        """K4: motor `origin/main`'den çekilir. Klondaki bir script BAYAT olabilir → skill script TAŞIMAZ."""
        for alt in ("scripts", "tests"):
            self.assertFalse((SKILL.parent / alt).exists(),
                             f"skills/guncelle/{alt}/ VAR — K4 ihlali (yerel kopya bayatlayabilir)")
        self.assertEqual(sorted(p.name for p in SKILL.parent.iterdir()), ["SKILL.md"])

    def test_harita_skill_govde_sinifi_bu_dosyayi_kapsar(self):
        """P7 haritası zaten `skills/*/SKILL.md` diyor → yeni sınıf eklenmemeli; ölçerek doğrula."""
        harita = AXET_HOME / "guncelle" / "harita.json"
        self.assertTrue(harita.exists(), f"{harita} yok")
        d = json.loads(harita.read_text(encoding="utf-8"))
        govde = next((s for s in d["siniflar"] if s["sinif"] == "skill-govde"), None)
        self.assertIsNotNone(govde, "harita.json'da 'skill-govde' sınıfı yok")
        self.assertIn("skills/*/SKILL.md", govde["glob"])
        kendi = [s for s in d["siniflar"] if "skills/guncelle/SKILL.md" in s.get("glob", [])]
        self.assertEqual(kendi, [], "bu dosya için AYRI sınıf açılmış — gereksiz (glob zaten kapsıyor)")

    def test_gevsetme_yasagi_ve_yapmayacaklari_yazili(self):
        """Çekirdek §11 istisnası DAR: skill gövdesi sınırı kendi metninde de taşımalı."""
        for parca in ("gevşet", "DUR", "origin", "commit"):
            self.assertIn(parca, self.metin, f"sınır ifadesi eksik: {parca}")

    def test_tmp_dizini_repo_disi_kurali_yazili(self):
        """Ölçülmüş tuzak: klon İÇİNDEKİ TMP git testlerini yanlış FAIL'e düşürür (guncelle.py onkontrol 7).

        İki YERDE aranır — tanımda (`<TMP>` nedir) ve gerekçede (neden dışarıda). Tek yer ölçülürse
        mutasyon diğerini silip geçebilir: ölçüldü (MB5, 2026-09-18) — bir cümle silindiğinde test
        öteki cümleyle yeşil kaldı, yani kural KISMEN korumasızdı.
        """
        kalip = re.compile(r"(repo|klon)\s*(-|\s)?dışı")
        for baslik in ("## Neden yerel kopyadan", "## How to use this skill"):
            i = self.metin.find(baslik)
            self.assertGreater(i, 0, f"bölüm yok: {baslik}")
            j = self.metin.find("\n## ", i + 1)
            bolum = self.metin[i:j if j > 0 else len(self.metin)]
            self.assertRegex(bolum, kalip, f"'{baslik}' bölümünde `<TMP>` klon dışı kuralı yazmıyor")


class MotorSurumTest(GeciciTest):
    """B2 — başlatıcı, yerel motor BOZUKKEN bile `origin/main` sürümünden çalışır mı.

    Kontrol grubu şart: aynı klonda (a) YEREL motor çağrılır → başarısız olmalı,
    (b) belgedeki blokla çıkarılan motor çağrılır → başarılı olmalı. (a) olmadan (b)'nin
    yeşili bir şey kanıtlamaz — bozukluk gerçekten devrede miydi bilinmez.
    """

    MOTOR_YOLLARI = ("GUNCELLE.md", "scripts/guncelle.py", "guncelle")

    def setUp(self) -> None:
        super().setUp()
        self.klon = self.tmp / "klon"
        (self.klon / "scripts").mkdir(parents=True)
        shutil.copy2(AXET_HOME / "scripts" / "guncelle.py", self.klon / "scripts" / "guncelle.py")
        shutil.copy2(AXET_HOME / "GUNCELLE.md", self.klon / "GUNCELLE.md")
        shutil.copytree(AXET_HOME / "guncelle", self.klon / "guncelle")
        self.git(self.klon, "init", "-q", "-b", "main")
        self.git(self.klon, "add", "-A")
        self.git(self.klon, "commit", "-q", "-m", "motor")
        self.uzak = self.tmp / "uzak.git"
        self.git(self.tmp, "init", "-q", "--bare", str(self.uzak))
        self.git(self.klon, "remote", "add", "origin", str(self.uzak))
        self.git(self.klon, "push", "-q", "-u", "origin", "main")
        # TMP klonun DIŞINDA (ölçülmüş tuzak: içerideki TMP git testlerini yanlış FAIL'e düşürür)
        self.motor_tmp = self.tmp / "motor-tmp"
        self.motor_tmp.mkdir()

    def boz(self) -> None:
        """Yerel motoru ve haritasını kullanılamaz yap (bayat/bozuk kopya senaryosu).

        Bozukluk hem çalışma ağacına hem de YEREL COMMIT'e işlenir: `origin/main`'e gitmemiş bir
        yerel commit, tüketicideki gerçek "bayat / yarım güncellenmiş klon" hâlidir. ⛔ Yalnız
        çalışma ağacını bozmak YETMEZ — o durumda `git archive HEAD` de SAĞLAM motoru verir ve
        `origin/main` ile `HEAD` ayırt edilemez (ölçüldü: mutasyon MB2, 2026-09-18 — semantik test
        sağ kalmıştı, yalnız metinsel test yakalamıştı).
        """
        (self.klon / "scripts" / "guncelle.py").write_text(
            "raise SystemExit('BOZUK YEREL MOTOR')\n", encoding="utf-8", newline="")
        (self.klon / "guncelle" / "harita.json").write_text("{bozuk json", encoding="utf-8", newline="")
        self.git(self.klon, "add", "-A")
        self.git(self.klon, "commit", "-q", "-m", "yerel bozuk surum (origin'e gitmedi)")

    def kart_komutu(self, motor: Path) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(motor), "--klon", str(self.klon), "kart", "V1"],
                              cwd=str(self.tmp), env=self.env, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=300)

    def blogu_kos(self) -> list[subprocess.CompletedProcess]:
        sonuc = []
        for satir in komut_blogu(SKILL.read_text(encoding="utf-8")):
            parcalar = [p.replace("<KLON>", str(self.klon)).replace("<TMP>", str(self.motor_tmp))
                        for p in shlex.split(satir)]
            if parcalar[0] == "python":
                parcalar[0] = sys.executable
            sonuc.append(subprocess.run(parcalar, cwd=str(self.tmp), env=self.env, capture_output=True,
                                        text=True, encoding="utf-8", errors="replace",
                                        stdin=subprocess.DEVNULL, timeout=300))
        return sonuc

    def test_kontrol_grubu_yerel_motor_bozukken_calismaz(self):
        """(a) Bozukluk GERÇEKTEN devrede: yerel motor çağrısı başarısız."""
        self.boz()
        r = self.kart_komutu(self.klon / "scripts" / "guncelle.py")
        self.assertNotEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("BOZUK YEREL MOTOR", self.cikti(r))

    def test_kontrol_grubu_bozulmadan_yerel_motor_calisir(self):
        """(a') Yanlış-pozitif kontrolü: bozmadan yerel motor ÇALIŞIR → (a)'daki hata bozulmadan geliyor."""
        r = self.kart_komutu(self.klon / "scripts" / "guncelle.py")
        self.assertEqual(r.returncode, 0, self.cikti(r))

    def test_belgedeki_blok_bozuk_yerel_motora_ragmen_calisir(self):
        """(b) Asıl iddia: SKILL.md'deki blok motoru origin/main'den çıkarır ve ORADAN koşar."""
        self.boz()
        sonuclar = self.blogu_kos()
        for r in sonuclar:
            self.assertEqual(r.returncode, 0, f"blok satırı başarısız:\n{self.cikti(r)}")
        cikarilan = self.motor_tmp / "scripts" / "guncelle.py"
        self.assertTrue(cikarilan.exists(), "motor geçici dizine çıkarılmadı")
        self.assertNotIn("BOZUK YEREL MOTOR", cikarilan.read_text(encoding="utf-8"))
        self.assertTrue((self.motor_tmp / "guncelle" / "harita.json").exists(), "harita motorla birlikte gelmedi")
        r = self.kart_komutu(cikarilan)
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("V1", r.stdout, "kart içeriği basılmadı")

    def test_cikarilan_motor_klonun_disinda(self):
        """K4 + ölçülmüş TMP tuzağı: motor kopyası klonun İÇİNDE olmamalı."""
        self.boz()
        self.blogu_kos()
        self.assertFalse(str(self.motor_tmp.resolve()).startswith(str(self.klon.resolve())))

    def test_blok_yerel_motoru_calistirmiyor(self):
        """Belge okunurken de görünmeli: blok `<KLON>/scripts/guncelle.py`'yi ÇALIŞTIRMAZ."""
        satirlar = komut_blogu(SKILL.read_text(encoding="utf-8"))
        self.assertTrue(any("origin/main" in s for s in satirlar), satirlar)
        for s in satirlar:
            if s.split()[0] == "python" and "guncelle.py" in s:
                self.assertIn("<TMP>", s, f"motor YEREL kopyadan çalıştırılıyor: {s}")

    def test_blok_yasakli_komut_icermez(self):
        """Gevşetme yasağı: blok, ajanın YAPMAYACAKLARI listesindeki komutları içeremez."""
        metin = "\n".join(komut_blogu(SKILL.read_text(encoding="utf-8")))
        for yasak in ("reset --hard", "push", "--force", "clean -", "checkout"):
            self.assertNotIn(yasak, metin, f"blokta yasaklı komut: {yasak}")


class ReadmeSkillListesiTest(GeciciTest):
    """B3 — `skills/write-skill/SKILL.md:43`: template seviyesindeki skill README listesine girer."""

    def setUp(self) -> None:
        super().setUp()
        self.metin = (AXET_HOME / "README.md").read_text(encoding="utf-8")

    def satir(self) -> str:
        adaylar = [s for s in self.metin.splitlines() if s.startswith("- `%guncelle`")]
        self.assertEqual(len(adaylar), 1, f"README skill listesinde tam 1 `%guncelle` satırı olmalı: {adaylar}")
        return adaylar[0]

    def test_guncelle_satiri_var(self):
        self.assertIn("klon", self.satir().lower())

    def test_satir_skill_listesi_bloguna_komsu(self):
        """Kontrol grubu: satır rastgele bir yere değil, skill listesinin İÇİNE eklenmiş."""
        satirlar = self.metin.splitlines()
        i = satirlar.index(self.satir())
        komsu = [s for s in satirlar[max(0, i - 3):i + 4] if s.startswith("- `%")]
        self.assertGreaterEqual(len(komsu), 3, f"satır skill listesinin dışında görünüyor:\n" + "\n".join(komsu))

    def test_guncelle_proje_ile_karistirilmaz(self):
        """P5 ileride `%guncelle-proje` satırı ekleyecek — `startswith` ölçütü onu bu satırla karıştırmamalı."""
        self.assertNotIn("`%guncelle`", self.satir().replace("- `%guncelle`", "", 1))
        self.assertFalse(self.satir().startswith("- `%guncelle-proje`"))
