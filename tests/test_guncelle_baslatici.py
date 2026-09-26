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
# Z67: `<TMP>`'yi yaratan hazır komut da belgeden PARSE edilip AYNEN koşulur (tek kaynak).
TMP_BASLA, TMP_BITIR = "<!-- TMP-OLUSTUR:BASLA -->", "<!-- TMP-OLUSTUR:BITIR -->"


def komut_blogu(metin: str, basla: str = BASLA, bitir: str = BITIR) -> list[str]:
    """İki işaret arasındaki tek kod bloğunun komut satırları (yorum ve boş satır atılır)."""
    i, j = metin.find(basla), metin.find(bitir)
    if i < 0 or j < 0 or j < i:
        raise AssertionError(f"kanonik komut bloğu yok ({basla} … {bitir})")
    govde = metin[i + len(basla):j]
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


def komutu_kos(test: GeciciTest, satir: str, klon: Path, tmp: str, env: dict) -> subprocess.CompletedProcess:
    """Belgedeki bir komut satırını yer tutucuları doldurup AYNEN koşar (kabuk yok: shlex)."""
    parcalar = [p.replace("<KLON>", str(klon)).replace("<TMP>", tmp) for p in shlex.split(satir)]
    if parcalar[0] == "python":
        parcalar[0] = sys.executable
    return subprocess.run(parcalar, cwd=str(test.tmp), env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=300)


class TmpOlusturTest(GeciciTest):
    r"""Z67 — `<TMP>` belgedeki TEK hazır komutla yaratılır; model yol/yöntem uydurmaz.

    Vaka (ölçüldü 2026-09-23): tarif olmadığı için model `mkdir -p /c/Users/.../axet_guncelle_$(date +%s)`
    çalıştırdı ⇒ aXet kabuğu `/c/...`yi çalışma dizinine göreli çözdü (proje içinde boş ağaç) ve
    `$(date +%s)` BOŞ genişledi. aXet ayrıca `%TEMP%`'i proje içindeki `.axet-code/tmp`'ye çekiyor
    (`mkdtemp` oraya düştü) ⇒ komut tabanı `%LOCALAPPDATA%\Temp`'ten alır; klon ya da bir aXet veri
    dizini (`.axet-code`) içine düşerse yarattığını siler ve DUR der.
    """

    def setUp(self) -> None:
        super().setUp()
        self.metin = SKILL.read_text(encoding="utf-8")
        self.klon = self.tmp / "klon"
        self.klon.mkdir()
        self.lad = self.tmp / "lad"                 # sahte %LOCALAPPDATA%
        (self.lad / "Temp").mkdir(parents=True)
        self.sistem_tmp = self.tmp / "sistem-tmp"   # sahte %TEMP% (LOCALAPPDATA yoksa geri düşüş)
        self.sistem_tmp.mkdir()
        self.env.update({"LOCALAPPDATA": str(self.lad), "TEMP": str(self.sistem_tmp),
                         "TMP": str(self.sistem_tmp), "TMPDIR": str(self.sistem_tmp)})

    def satir(self) -> str:
        satirlar = komut_blogu(self.metin, TMP_BASLA, TMP_BITIR)
        self.assertEqual(len(satirlar), 1, f"TMP-OLUSTUR bloğu TEK komut olmalı: {satirlar}")
        return satirlar[0]

    def kos(self) -> subprocess.CompletedProcess:
        return komutu_kos(self, self.satir(), self.klon, "", self.env)

    def test_blok_motor_cikar_blogundan_once(self):
        i = self.metin.find(TMP_BASLA)
        self.assertGreater(i, 0, "TMP-OLUSTUR bloğu yok")
        self.assertLess(i, self.metin.find(BASLA), "`<TMP>` motor çıkarılmadan ÖNCE yaratılmalı")

    def test_komut_klon_disi_bos_dizin_yaratir_ve_C_bicimli_yol_basar(self):
        r = self.kos()
        self.assertEqual(r.returncode, 0, self.cikti(r))
        yol = r.stdout.strip()
        self.assertEqual(len(yol.splitlines()), 1, f"çıktı tek satır (yalnız yol) olmalı: {r.stdout!r}")
        self.assertNotIn("\\", yol, "yol `C:/...` biçiminde (ileri eğik çizgi) basılmalı")
        self.assertNotRegex(yol, r"^/[a-zA-Z]/", "Git Bash biçimi `/c/...` basıldı")
        d = Path(yol)
        self.assertTrue(d.is_dir(), yol)
        self.assertEqual(list(d.iterdir()), [], "dizin boş olmalı")
        self.assertTrue(d.name.startswith("axet_guncelle_"), d.name)
        self.assertEqual(d.resolve().parent, (self.lad / "Temp").resolve(),
                         r"taban %LOCALAPPDATA%\Temp olmalı (aXet %TEMP%'i proje içine çeker)")

    def test_localappdata_yoksa_sistem_tmp_ye_duser(self):
        self.env.pop("LOCALAPPDATA")
        r = self.kos()
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertEqual(Path(r.stdout.strip()).resolve().parent, self.sistem_tmp.resolve())

    def test_iki_kosu_iki_ayri_dizin(self):
        """`$(date +%s)` gibi boş genişleyebilen ad yok: her koşu kendi benzersiz dizinini alır."""
        a, b = self.kos(), self.kos()
        self.assertEqual((a.returncode, b.returncode), (0, 0), self.cikti(a) + self.cikti(b))
        self.assertNotEqual(a.stdout.strip(), b.stdout.strip())

    def test_taban_klon_icindeyse_DUR_ve_artik_birakmaz(self):
        """Kontrol grubu (negatif): taban klonun içine düşerse komut DURur, boş dizin bırakmaz."""
        (self.klon / "Temp").mkdir()
        self.env["LOCALAPPDATA"] = str(self.klon)
        r = self.kos()
        self.assertNotEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("DUR", self.cikti(r))
        self.assertEqual(list((self.klon / "Temp").iterdir()), [], "klon içinde artık dizin kaldı")

    def test_taban_axet_veri_dizinindeyse_DUR(self):
        """aXet `%TEMP%`'i `<proje>/.axet-code/tmp`'ye çeker: oraya düşen `<TMP>` reddedilir."""
        self.env.pop("LOCALAPPDATA")
        cekilen = self.tmp / "proje" / ".axet-code" / "tmp"
        cekilen.mkdir(parents=True)
        self.env.update({"TEMP": str(cekilen), "TMP": str(cekilen), "TMPDIR": str(cekilen)})
        r = self.kos()
        self.assertNotEqual(r.returncode, 0, self.cikti(r))
        self.assertIn(".axet-code", self.cikti(r))
        self.assertEqual(list(cekilen.iterdir()), [], "aXet veri dizininde artık dizin kaldı")

    def test_yol_uydurma_yasagi_yazili(self):
        """Kural metinde: yollar `C:/...`; `/c/...` ve `$(date …)` YASAK. Blokların kendisi de uymalı."""
        i = self.metin.find("## How to use this skill")
        j = self.metin.find("\n## ", i + 1)
        bolum = self.metin[i:j if j > 0 else len(self.metin)]
        self.assertIn("/c/", bolum, "`/c/...` yasağı How-to bölümünde yazmıyor")
        self.assertIn("$(date", bolum, "`$(date …)` yasağı How-to bölümünde yazmıyor")
        self.assertIn("C:/", bolum)
        for s in komut_blogu(self.metin) + komut_blogu(self.metin, TMP_BASLA, TMP_BITIR):
            self.assertNotRegex(s, r"""(^|[\s"'])/[a-zA-Z]/""", f"blokta `/c/...` biçimli yol: {s}")
            self.assertNotIn("$(", s, f"blokta kabuk genişletmesi: {s}")

    def test_cekirdek_kabuk_ortami_satiri_c_yolunu_anar(self):
        cekirdek = (AXET_HOME / "core" / "00-temel.md").read_text(encoding="utf-8")
        self.assertIn("- **Kabuk ortamı:**", cekirdek, "core/00-temel.md 'Kabuk ortamı' satırı yok")
        from test_sap_skill_bilgi import _kabuk_blogu
        satir = _kabuk_blogu(cekirdek)
        self.assertIn("/c/", satir, "Kabuk ortamı satırı `/c/...` tuzağını anmıyor")


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
        # TMP klonun DIŞINDA (ölçülmüş tuzak: içerideki TMP git testlerini yanlış FAIL'e düşürür).
        # Z67: `<TMP>` belgedeki TMP-OLUSTUR komutuyla yaratılır — kullanıcının koşacağı zincirin AYNISI.
        lad = self.tmp / "lad"
        (lad / "Temp").mkdir(parents=True)
        satir = komut_blogu(SKILL.read_text(encoding="utf-8"), TMP_BASLA, TMP_BITIR)[0]
        r = komutu_kos(self, satir, self.klon, "", dict(self.env, LOCALAPPDATA=str(lad)))
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.motor_tmp = Path(r.stdout.strip())
        self.assertTrue(self.motor_tmp.is_dir(), r.stdout)

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
        return [komutu_kos(self, satir, self.klon, str(self.motor_tmp), self.env)
                for satir in komut_blogu(SKILL.read_text(encoding="utf-8"))]

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


class Z95AkisDisiTestYasagiTest(GeciciTest):
    """Z95ⓐ (2026-09-26) — `%guncelle`de model akış DIŞI test takımı koşmaz (kural İKİ yerde yazılı).

    Vaka (ölçüldü 2026-09-24): motor adımları ~2 dk sürdü; sonra model sıradaki `olc --asama sonra`
    yerine kendi kararıyla `tests/run_tests.py -k …`, proje testleri ve filtresiz takımı koştu, kırmızıları
    teşhise girdi ve klon dışında kendi dizinini açtı. Neden İKİ yer: GUNCELLE.md her koşuda
    `origin/main`'den okunur ⇒ yayından sonraki İLK `%guncelle`de etkindir; SKILL.md ise klondan yüklenir
    (`install.py` `skills_paths`) ⇒ ancak klon dosyası güncellendikten SONRAKİ turda etkindir.
    KAPSAM — bakılmayan: modelin kurala fiilen uyması (canlı `%guncelle` DB izi, Z95ⓑ — lider).
    """

    PARCALAR = ("tests/run_tests.py", "olc --asama sonra", "<TMP>")

    def bolum(self, metin: str, baslik: str) -> str:
        i = metin.find(baslik)
        self.assertGreaterEqual(i, 0, f"bölüm yok: {baslik}")
        j = metin.find("\n## ", i + 1)
        return metin[i:j if j > 0 else len(metin)]

    def madde(self, bolum: str) -> str:
        """Bölümde 'DIŞINDA test' diyen madde (alt satırlarıyla) — kural BAŞKA bir maddede sayılmasın."""
        maddeler = re.split(r"\n(?=- )", bolum)
        adaylar = [m for m in maddeler if re.search(r"DIŞINDA test", m)]
        self.assertEqual(len(adaylar), 1, f"akış dışı test maddesi tam 1 olmalı: {len(adaylar)}")
        return adaylar[0]

    def test_guncelle_md_yapmayacaklar_listesinde(self):
        metin = (AXET_HOME / "GUNCELLE.md").read_text(encoding="utf-8")
        m = self.madde(self.bolum(metin, "## Ajanın YAPMAYACAKLARI"))
        for parca in self.PARCALAR:
            self.assertIn(parca, m, f"GUNCELLE.md maddesinde eksik: {parca}")

    def test_skill_rules_bolumunde(self):
        m = self.madde(self.bolum(SKILL.read_text(encoding="utf-8"), "## Rules"))
        for parca in self.PARCALAR:
            self.assertIn(parca, m, f"SKILL.md maddesinde eksik: {parca}")


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
