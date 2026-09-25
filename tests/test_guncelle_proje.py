# -*- coding: utf-8 -*-
"""`scripts/guncelle_proje.py` + `%guncelle-proje` — proje şablonu güncellemesi (TASARIM §2b, §9).

İÇERİK: (a) FIXTURE — geçici dizinde sahte template klonu (templates/project* iki commit'te
ilerler) + ondan `new_project.py` ile doğmuş tüketici projesi; (b) P5 kabul ölçütünün istediği
senaryolar: `_doldur` tabanı · damga ayrımı · SHA'sız geri düşüş · VTB · "her proje ayrı onaylanır".

ÖLÇÜLEN TUZAK (2026-09-17, bu turda): Windows'ta `new_project.py` proje dosyalarını CRLF
yazar (`Path.write_text` çeviri yapar), template blob'u ise LF'tir (`.githooks/**` istisna,
orada açıkça newline="\\n" verilir). Ham bayt karşılaştırması bu yüzden HER dosyayı "yerelde
değişmiş" gösterir ve SHA'sız geri düşüşte hiçbir sürüm eşleşmez. Karşılaştırma normalize edilmeli.

Repo DIŞI TMP zorunlu (ölçülmüş tuzak) — `GeciciTest` `tempfile.mkdtemp()` kullanır.

KAPSAM — bakılmayanlar: gerçek bir tüketici klonunda uçtan uca koşum (`_lab`, P9) · aXet'in
modeli talimatı gerçekten izlemesi · Linux/macOS (Windows'ta ölçüldü) · yeniden adlandırma (+R)
proje kapsamında UYGULANMAZ (bkz. guncelle_proje.py KAPSAM notu) · `templates/package/**`
(K5: kapsam dışı, yalnız bilgi satırı).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

BURASI = Path(__file__).resolve().parent
if str(BURASI) not in sys.path:
    sys.path.insert(0, str(BURASI))

from _helpers import GeciciTest  # noqa: E402  — scripts/ yolunu da ekler
import yeni_proje  # noqa: E402  — kısayol metni (Z79) tek kaynaktan

AXET_HOME = BURASI.parent
GERCEK_SCRIPTS = AXET_HOME / "scripts"

# Sahte klona kopyalanan gerçek script'ler (motorun kendisi + bağımlı olduğu yardımcılar).
# Z79: SAP projesinde motor `yeni_proje` (kısayol) içe aktarır → onun `doctor` zinciri de gerekir.
KOPYALANAN_SCRIPTLER = ("guncelle.py", "guncelle_proje.py", "new_project.py", "sap_stamp.py",
                        "yeni_proje.py", "doctor.py", "install.py", "new_package.py", "behavior_manifest.py",
                        "project_precommit.py")  # Z93: doctor onu içe aktarır

V1_SABLON = {
    "templates/project/AGENTS.md": (
        "# <PROJE_ADI> — Proje Talimatı\n\n"
        "## Oturum\n"
        "python \"<AXET_HOME>/scripts/session_brief.py\"\n\n"
        "## Açık işler\n- yok\n\n"
        "## Notlar\nsatir1\nsatir2\nsatir3\nsatir4\nson\n"
    ),
    "templates/project/.axet-code.json": '{"options": {"context_paths": ["x"]}}\n',
    "templates/project/.axet-code/.gitignore": "*\n",
    "templates/project/.gitignore": ".conn_adt\n",
    "templates/project/proje-recetesi.ornek.md": "# Reçete\nA\nB\nC\n",
    "templates/project/.githooks/pre-commit": "#!/bin/sh\necho v1\n",
    "templates/project-sap/sap-project.json": '{"sap_profile": "<PROJE_ADI>-yok"}\n',
    "templates/package/.rules.md.tmpl": "# paket kurallari v1\n",
}

V2_SABLON = {
    # V1 adayı: kullanıcı dokunmaz, biz değiştiririz
    "templates/project/proje-recetesi.ornek.md": "# Reçete v2\nA\nB\nC\n",
    # V4 adayı: gövdenin ÜST tarafı bizden (kullanıcı ALT tarafı değiştirecek → temiz birleşme)
    "templates/project/AGENTS.md": (
        "# <PROJE_ADI> — Proje Talimatı (v2)\n\n"
        "## Oturum\n"
        "python \"<AXET_HOME>/scripts/session_brief.py\"\n\n"
        "## Açık işler\n- yok\n\n"
        "## Notlar\nsatir1\nsatir2\nsatir3\nsatir4\nson\n"
    ),
    # V2 adayı: yepyeni dosya
    "templates/project/validators-local/README.md": "# yerel validator'lar\n",
    # K5: paket şablonu da değişir — kapsam DIŞI kalmalı
    "templates/package/.rules.md.tmpl": "# paket kurallari v2\n",
}


class SahteKlon:
    """Sahte aXet template klonu (c1 → c2) + ondan doğmuş tüketici projesi."""

    def __init__(self, test: GeciciTest, kok: Path) -> None:
        self.t = test
        self.kok = kok
        self.home = kok / "axet"
        self.proje = kok / "proje"

    def _yaz(self, agac: dict) -> None:
        for yol, icerik in agac.items():
            h = self.home / yol
            if icerik is None:
                if h.exists():
                    h.unlink()
                continue
            h.parent.mkdir(parents=True, exist_ok=True)
            with open(h, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(icerik)

    def uret(self, sap: bool = False, onceden: dict | None = None,
             ikili: dict | None = None, kisayol: bool | None = None) -> "SahteKlon":
        """onceden: new_project'ten ÖNCE projede duran dosyalar (rel -> içerik); aXet'in kendi yazdıkları gibi.
        ikili: şablona eklenecek ikili dosyalar (klon-göreli yol -> bayt).
        kisayol: resmi `KURULUMU-TAMAMLA.cmd`'yi `yeni_proje.py` gibi yaz (varsayılan: SAP projesinde evet —
        gerçek SAP projeleri `yeni_proje.py` ile doğar, Z70)."""
        (self.home / "scripts").mkdir(parents=True)
        for ad in KOPYALANAN_SCRIPTLER:
            shutil.copy2(GERCEK_SCRIPTS / ad, self.home / "scripts" / ad)
        (self.home / "core" / "sap").mkdir(parents=True)
        shutil.copy2(AXET_HOME / "core" / "sap" / "00-sap.md",
                     self.home / "core" / "sap" / "00-sap.md")
        self._yaz(V1_SABLON)
        for yol, bayt in (ikili or {}).items():
            (self.home / yol).parent.mkdir(parents=True, exist_ok=True)
            (self.home / yol).write_bytes(bayt)
        g = self.t.git
        g(self.home, "init", "-q", "-b", "main")
        g(self.home, "add", "-A")
        g(self.home, "commit", "-q", "-m", "v1")
        self.proje.mkdir()
        g(self.proje, "init", "-q", "-b", "main")
        for rel, icerik in (onceden or {}).items():
            (self.proje / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.proje / rel).write_bytes(icerik.encode("utf-8"))
        r = self.t.calistir("new_project.py", str(self.proje), "--name", "PROJE",
                            *(["--sap"] if sap else []),
                            scripts_dir=self.home / "scripts")
        self.t.assertEqual(r.returncode, 0, self.t.cikti(r))
        if sap if kisayol is None else kisayol:
            self.kisayol_yaz()
        return self

    # --- KURULUMU-TAMAMLA.cmd (Z79) ------------------------------------------------------------
    def kisayol_bayt(self, axet_home: Path | None = None) -> bytes:
        """`yeni_proje.kisayol_yaz`'ın diske yazdığı bayt (CRLF, Windows'ta OEM kod sayfası)."""
        metin = yeni_proje.kisayol_metni((axet_home or self.home).resolve())
        return metin.encode("oem" if os.name == "nt" else "utf-8")

    def kisayol_yaz(self, veri: bytes | None = None) -> None:
        (self.proje / yeni_proje.KISAYOL).write_bytes(self.kisayol_bayt() if veri is None else veri)

    def kisayol_oku(self) -> bytes | None:
        f = self.proje / yeni_proje.KISAYOL
        return f.read_bytes() if f.is_file() else None

    def ilerlet(self, degisim: dict | None = None) -> str:
        self._yaz(degisim if degisim is not None else V2_SABLON)
        g = self.t.git
        g(self.home, "add", "-A")
        g(self.home, "commit", "-q", "-m", "ilerleme")
        return g(self.home, "rev-parse", "HEAD").stdout.strip()

    # --- motoru çağır --------------------------------------------------------------------------
    def calistir(self, *args: str, ad: str | None = None,
                 timeout: int = 300) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(self.home / "scripts" / "guncelle_proje.py"),
             "--proje", str(self.proje), *(["--ad", ad] if ad else []), *args],
            cwd=str(self.kok), env=self.t.env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=timeout)

    def onayla(self, ad: str | None = None) -> subprocess.CompletedProcess:
        return self.calistir("onay", "--kabul", "PROJE", ad=ad)

    def kayit_yolu(self) -> Path:
        return self.proje / ".axet-code" / "sablon-surumu.json"

    def kayit(self) -> dict:
        return json.loads(self.kayit_yolu().read_text(encoding="utf-8"))

    def durum_dizini(self) -> Path:
        return self.proje / ".axet-code" / ".guncelle-proje"

    def plan(self) -> dict:
        return json.loads((self.durum_dizini() / "plan.json").read_text(encoding="utf-8"))

    def vakalar(self) -> dict:
        return {d["yol"]: d["vaka"] for d in self.plan()["dosyalar"]}

    def yerel_degistir(self, rel: str, icerik: str) -> None:
        h = self.proje / rel
        h.parent.mkdir(parents=True, exist_ok=True)
        h.write_text(icerik, encoding="utf-8")   # new_project.py ile AYNI yazım (Windows'ta CRLF)

    def oku(self, rel: str) -> str:
        return (self.proje / rel).read_text(encoding="utf-8")


class ProjeTemel(GeciciTest):
    sap = False

    def setUp(self) -> None:
        super().setUp()
        self.f = SahteKlon(self, self.tmp).uret(sap=self.sap)

    def planla(self, onayla: bool = True, ad: str | None = None) -> subprocess.CompletedProcess:
        if onayla:
            r = self.f.onayla(ad=ad)
            self.assertEqual(r.returncode, 0, self.cikti(r))
        return self.f.calistir("plan", ad=ad)


# =====================================================================================================
# 1. SÜRÜM KAYDI (`new_project.py`)
# =====================================================================================================
class SurumKaydiTest(GeciciTest):
    def setUp(self) -> None:
        super().setUp()
        self.f = SahteKlon(self, self.tmp)

    def test_yeni_proje_surum_kaydini_yazar(self):
        self.f.uret()
        self.assertTrue(self.f.kayit_yolu().exists(),
                        "new_project.py yeni projeye şablon sürüm kaydını YAZMALI (doğum kaydı)")
        kayit = self.f.kayit()
        beklenen = self.git(self.f.home, "log", "-1", "--format=%H", "--",
                            "templates/project").stdout.strip()
        self.assertEqual(kayit["template_commit"], beklenen)
        self.assertEqual(kayit["ad"], "PROJE")
        self.assertFalse(kayit["sap"])
        self.assertEqual(kayit["axet_home"], self.f.home.resolve().as_posix())
        self.assertEqual(kayit["kaynak"], "new_project")

    def test_sap_projesinde_kayit_sap_sablonunu_da_kapsar(self):
        self.f.uret(sap=True)
        self.assertTrue(self.f.kayit_yolu().exists(),
                        "SAP projesinde de şablon sürüm kaydı YAZILMALI")
        kayit = self.f.kayit()
        self.assertTrue(kayit["sap"])
        self.assertIn("templates/project-sap", kayit["sablon_yollari"])

    def test_var_olan_kayit_yeniden_calistirmada_EZILMEZ(self):
        self.f.uret()
        once = self.f.kayit()
        self.f.ilerlet()
        r = self.calistir("new_project.py", str(self.f.proje), "--name", "PROJE",
                          scripts_dir=self.f.home / "scripts")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertEqual(self.f.kayit(), once, "kayıt doğum sürümüdür; yeniden kurulumda ezilmez")

    def test_dry_run_kayit_yazmaz(self):
        self.f.uret()
        # missing_ok: bu test kaydın YAZILMAMASINI ölçer; kaydın önce var olması ön koşul DEĞİL
        # (yoksa kayıt-yazma kusuru bu testi de kırar ve kontrol grubu değerini yitirir).
        self.f.kayit_yolu().unlink(missing_ok=True)
        r = self.calistir("new_project.py", str(self.f.proje), "--name", "PROJE", "--dry-run",
                          scripts_dir=self.f.home / "scripts")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertFalse(self.f.kayit_yolu().exists())

    def test_dosyalari_zaten_olan_projede_kayit_YAZILMAZ(self):
        """Kayıtsız eski proje: doğum sürümü BİLİNMİYOR → uydurulmaz (SHA'sız geri düşüş devreye girer)."""
        self.f.uret()
        self.f.kayit_yolu().unlink(missing_ok=True)  # bkz. yukarıdaki missing_ok notu
        self.f.ilerlet()
        r = self.calistir("new_project.py", str(self.f.proje), "--name", "PROJE",
                          scripts_dir=self.f.home / "scripts")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertFalse(self.f.kayit_yolu().exists(), self.cikti(r))
        self.assertIn("sürüm kaydı yazılmadı", self.cikti(r))

    def test_axetin_kendi_gitignoreu_varken_kayit_YAZILIR(self):
        """K-E: aXet klasörü açınca `.axet-code/.gitignore`'ı `*` ile kendisi yazar; bu, kullanıcı dosyası DEĞİLDİR."""
        self.f.uret(onceden={".axet-code/.gitignore": "*\n"})
        self.assertTrue(self.f.kayit_yolu().exists(),
                        "aXet'in yazdığı `*` .gitignore'u 'proje zaten vardı' sayılmamalı")

    def test_axet_gitignoreu_YANINDA_kullanici_dosyasi_varsa_kayit_YAZILMAZ(self):
        """Negatif kontrol: aXet dosyasının yanında kullanıcının farklı bir proje dosyası varsa doğum bilinmiyor."""
        self.f.uret(onceden={".axet-code/.gitignore": "*\n", "AGENTS.md": "# kullanicinin kendi AGENTS'i\n"})
        self.assertFalse(self.f.kayit_yolu().exists(),
                         "kullanıcı dosyası önceden varken doğum sürümü uydurulmamalı")

    def test_ikili_sablon_dosyasi_bayt_bayt_kopyalanir(self):
        """Z9: şablondaki ikili dosya eskiden UnicodeDecodeError ile tüm kurulumu yarıda bırakıyordu."""
        png = b"\x89PNG\r\n\x1a\n\x00\xff\xfe<PROJE_ADI>"  # geçersiz UTF-8 + yer tutucu: doldurulMAMALI
        self.f.uret(ikili={"templates/project/logo.png": png})  # rc != 0 ise uret kendisi FAIL eder
        self.assertEqual((self.f.proje / "logo.png").read_bytes(), png)
        r = self.calistir("new_project.py", str(self.f.proje), "--name", "PROJE",
                          scripts_dir=self.f.home / "scripts")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("[aynı]        logo.png", self.cikti(r))  # ikinci koşumda bayt karşılaştırması

    def test_utf8_cozulebilen_ikili_sablon_da_bayt_bayt_kopyalanir(self):
        """Bug gate 2026-09-19 #6: ölçüt yalnız UnicodeDecodeError'dı ⇒ geçerli UTF-8 olan ikili dosya
        (NUL içerir) metin sayılıp yer tutucusu dolduruluyor, satır sonu çevriliyordu. Uzantısı ikili
        listesinde OLMAYAN bir ad seçildi: ölçülen tek ölçüt NUL taramasıdır."""
        veri = b"AXB1\x00\x01<PROJE_ADI>\n\x00\x02son\n"
        veri.decode("utf-8")  # kontrol grubu: gerçekten çözülebilir (yoksa eski dal da bayt kopyalardı)
        self.f.uret(ikili={"templates/project/veri.bin": veri})
        self.assertEqual((self.f.proje / "veri.bin").read_bytes(), veri)

    def test_ikili_sablon_guncellemesi_bayt_bayt_yazilir(self):
        """Bug gate 2026-09-19 ikinci tur (ölçüldü): `%guncelle-proje uygula` ikili dosyayı `_norm` ile
        CRLF→LF çevirip (PNG başlığı `\\r\\n` içerir) ya da `write_text` ile LF→CRLF çevirip yazıyordu;
        doğrulama iki tarafı da normalize ettiği için bozulma SESSİZDİ."""
        png_eski, png_yeni = b"\x89PNG\r\n\x1a\n\x00ESKI", b"\x89PNG\r\n\x1a\n\x00YENI\r\n"
        bin_eski, bin_yeni = b"AXB1\x00\x01sabit\n\x00son\n", b"AXB2\x00\x01sabit\n\x00son\n"
        self.f.uret(ikili={"templates/project/logo.png": png_eski, "templates/project/veri.bin": bin_eski})
        (self.f.home / "templates/project/logo.png").write_bytes(png_yeni)
        (self.f.home / "templates/project/veri.bin").write_bytes(bin_yeni)
        self.f.ilerlet({})
        self.assertEqual(self.f.onayla().returncode, 0)
        r = self.f.calistir("plan")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        # kontrol grubu: iki dosya da otomatik uygulanan vakada (yoksa `uygula` onlara dokunmaz)
        self.assertEqual((self.f.vakalar().get("logo.png"), self.f.vakalar().get("veri.bin")), ("V1", "V1"))
        r = self.f.calistir("uygula", "--otomatik")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertEqual((self.f.proje / "logo.png").read_bytes(), png_yeni)
        self.assertEqual((self.f.proje / "veri.bin").read_bytes(), bin_yeni)


# =====================================================================================================
# 2. PLAN / VAKA KODLARI
# =====================================================================================================
class PlanTest(ProjeTemel):
    def test_sablon_ilerlemeden_plan_cikis_1(self):
        r = self.planla()
        self.assertEqual(r.returncode, 1, self.cikti(r))
        self.assertIn("güncel", self.cikti(r))

    def test_V1_dokunulmamis_dosya_ve_V2_yeni_dosya(self):
        self.f.ilerlet()
        r = self.planla()
        self.assertEqual(r.returncode, 0, self.cikti(r))
        v = self.f.vakalar()
        self.assertEqual(v.get("proje-recetesi.ornek.md"), "V1")
        self.assertEqual(v.get("validators-local/README.md"), "V2")

    def test_CRLF_proje_dosyasi_yerel_degismis_SAYILMAZ(self):
        """ÖLÇÜLEN TUZAK: proje dosyaları CRLF, blob LF. Ham bayt kıyası hepsini V3/V4 yapardı."""
        disk = (self.f.proje / "proje-recetesi.ornek.md").read_bytes()
        self.assertIn(b"\r\n", disk, "fixture ön koşulu: Windows'ta proje dosyası CRLF olmalı")
        self.f.ilerlet()
        self.planla()
        self.assertEqual(self.f.vakalar().get("proje-recetesi.ornek.md"), "V1")

    def test_doldur_tabani_AGENTS_md_yi_yerel_degismis_gostermez(self):
        """`_doldur` uygulanmadan taban kurulursa `<PROJE_ADI>`/`<AXET_HOME>` farkı V4 üretir."""
        self.assertIn("PROJE", self.f.oku("AGENTS.md"))
        self.assertNotIn("<AXET_HOME>", self.f.oku("AGENTS.md"))
        self.f.ilerlet()
        self.planla()
        self.assertEqual(self.f.vakalar().get("AGENTS.md"), "V1")

    def test_V4t_iki_taraf_degisti_temiz_birlesme(self):
        """Ad "temiz birleşme" diyor ⇒ vaka kodunu DEĞİL, çakışmasızlığı da ölçer."""
        self.f.yerel_degistir("AGENTS.md", self.f.oku("AGENTS.md").replace("son\n", "son yerel\n"))
        self.f.ilerlet()
        self.planla()
        self.assertEqual(self.f.vakalar().get("AGENTS.md"), "V4t")
        r = self.f.calistir("oneri", "AGENTS.md")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        birlesik = (self.f.durum_dizini() / "oneri" / "AGENTS.md").read_text(encoding="utf-8")
        for isaret in ("<<<<<<<", "=======", ">>>>>>>"):
            self.assertNotIn(isaret, birlesik, "V4t temiz birleşmelidir: çakışma işareti olmamalı")

    def test_V3_yerel_degisti_yeni_gelmiyor_listelenmez_sayilir(self):
        self.f.yerel_degistir(".gitignore", ".conn_adt\nkendi-satirim\n")
        self.f.ilerlet()
        self.planla()
        self.assertNotIn(".gitignore", self.f.vakalar())
        self.assertEqual(self.f.plan()["sayaclar"].get("V3"), 1)

    def test_V6d_yerelde_degismis_dosya_silinmez(self):
        """Ad "silinmez" diyor ⇒ vaka kodunu DEĞİL, dosyanın sağ kaldığını da ölçer."""
        self.f.yerel_degistir("proje-recetesi.ornek.md", "# Reçete YEREL\n")
        self.f.ilerlet({"templates/project/proje-recetesi.ornek.md": None,
                        "templates/project/validators-local/README.md": "# yerel\n"})
        self.planla()
        self.assertEqual(self.f.vakalar().get("proje-recetesi.ornek.md"), "V6d")
        r = self.f.calistir("uygula", "--otomatik")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertTrue((self.f.proje / "proje-recetesi.ornek.md").is_file(), self.cikti(r))
        self.assertEqual(self.f.oku("proje-recetesi.ornek.md"), "# Reçete YEREL\n")

    def test_V6_yerelde_degismemis_dosya_SILINIR(self):
        """V6d'nin KONTROL GRUBU: aynı şablon değişikliği, yerel dokunulmamışken dosya gider."""
        self.f.ilerlet({"templates/project/proje-recetesi.ornek.md": None,
                        "templates/project/validators-local/README.md": "# yerel\n"})
        self.planla()
        self.assertEqual(self.f.vakalar().get("proje-recetesi.ornek.md"), "V6")
        r = self.f.calistir("uygula", "--otomatik")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertFalse((self.f.proje / "proje-recetesi.ornek.md").exists(), self.cikti(r))
        self.assertIn("SİLİNDİ", self.cikti(r))

    def test_paket_sablonu_kapsam_disi_bilgi_satiri(self):
        self.f.ilerlet()
        r = self.planla()
        self.assertNotIn(".rules.md.tmpl", json.dumps(self.f.vakalar()))
        self.assertIn("paket şablonunda değişiklik var", self.cikti(r))


# =====================================================================================================
# 3. SHA'SIZ GERİ DÜŞÜŞ + VTB
# =====================================================================================================
class GeriDususTest(ProjeTemel):
    def test_kayitsiz_projede_taban_icerik_eslesmesiyle_bulunur(self):
        self.f.kayit_yolu().unlink()
        self.f.ilerlet()
        # Kayıt silinince proje ADI da kaybolur (`<PROJE_ADI>` onunla dolduruldu) → açıkça ver.
        r = self.planla(ad="PROJE")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertEqual(self.f.plan()["taban_kaynagi"], "eslesme")
        self.assertEqual(self.f.vakalar().get("proje-recetesi.ornek.md"), "V1")

    def test_kayitsiz_ve_yerelde_degismis_dosya_VTB(self):
        self.f.kayit_yolu().unlink()
        self.f.yerel_degistir("proje-recetesi.ornek.md", "# bambaska icerik\n")
        self.f.ilerlet()
        self.planla(ad="PROJE")
        v = self.f.vakalar()
        self.assertEqual(v.get("proje-recetesi.ornek.md"), "VTB")
        # KONTROL GRUBU: aynı koşumda tabanı bulunabilen dosya VTB DEĞİL (vakum-assertion koruması)
        self.assertEqual(v.get("AGENTS.md"), "V1")

    def test_kayitli_commit_cozulemezse_VTB(self):
        kayit = self.f.kayit()
        kayit["template_commit"] = "0" * 40
        self.f.kayit_yolu().write_text(json.dumps(kayit, ensure_ascii=False), encoding="utf-8")
        self.f.ilerlet()
        self.planla(ad="PROJE")
        v = self.f.vakalar()
        self.assertEqual(v.get("proje-recetesi.ornek.md"), "VTB")
        # ÖLÇÜLDÜ 2026-09-18: kayıt VAR ama commit klonda yoksa içerik eşleştirmesine
        # DÜŞÜLMEZ (`Baglam.adaylar` boş; `taban_bul` hemen VTB döner) ⇒ HEPSİ VTB olur.
        # Kontrol grubu bu sınıftaki `test_kayitsiz_projede_taban_icerik_eslesmesiyle_bulunur`
        # testidir: kayıt HİÇ yoksa aynı AGENTS.md V1 çıkar.
        self.assertEqual(v.get("AGENTS.md"), "VTB")
        self.assertEqual(set(v.values()), {"VTB"}, "kayıttaki commit yoksa taban uydurulmaz")

    def test_VTB_dosyasinda_oneri_reddedilir(self):
        self.f.kayit_yolu().unlink()
        self.f.yerel_degistir("proje-recetesi.ornek.md", "# bambaska icerik\n")
        self.f.ilerlet()
        self.planla(ad="PROJE")
        r = self.f.calistir("oneri", "proje-recetesi.ornek.md", ad="PROJE")
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn("taban", self.cikti(r).lower())

    def test_KONTROL_tabani_bilinen_dosyada_oneri_calisir(self):
        """Yukarıdaki negatif testin vakum olmadığını gösterir."""
        self.f.yerel_degistir("AGENTS.md", self.f.oku("AGENTS.md").replace("son\n", "son yerel\n"))
        self.f.ilerlet()
        self.planla(ad="PROJE")
        r = self.f.calistir("oneri", "AGENTS.md")
        self.assertIn(r.returncode, (0, 1), self.cikti(r))
        self.assertTrue((self.f.durum_dizini() / "oneri" / "AGENTS.md").is_file(), self.cikti(r))

    def test_VTB_uygula_otomatik_dosyaya_DOKUNMAZ(self):
        self.f.kayit_yolu().unlink()
        self.f.yerel_degistir("proje-recetesi.ornek.md", "# bambaska icerik\n")
        self.f.ilerlet()
        self.planla(ad="PROJE")
        r = self.f.calistir("uygula", "--otomatik", ad="PROJE")
        self.assertEqual(self.f.oku("proje-recetesi.ornek.md"), "# bambaska icerik\n", self.cikti(r))


class AdVarsayimiTest(ProjeTemel):
    def test_kayitsiz_projede_YANLIS_ad_her_seyi_VTB_yapar_ve_IPUCU_basar(self):
        """Proje adı bilinmiyorsa taban üretilemez; motor bunu gizlemez, ipucu basar."""
        self.f.kayit_yolu().unlink()
        self.f.ilerlet()
        # `plan` onaya BAĞLI DEĞİLDİR (salt-okur) → onay adımı olmadan çağrılır.
        # `--ad` YOK → dizin adı ("proje") varsayılır; gerçek ad "PROJE".
        r = self.f.calistir("plan")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertEqual(self.f.plan()["ad_kaynagi"], "dizin-adi-varsayimi")
        self.assertIn("İPUCU", self.cikti(r))
        self.assertTrue(self.f.plan()["sayaclar"].get("VTB"), self.cikti(r))
        # KONTROL GRUBU: doğru ad verilince aynı koşumda taban bulunur (vakum-assertion koruması)
        r = self.f.calistir("plan", ad="PROJE")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertEqual(self.f.plan()["ad_kaynagi"], "parametre")
        self.assertFalse(self.f.plan()["sayaclar"].get("VTB"), self.cikti(r))


# =====================================================================================================
# 4. "HER PROJE AYRI ONAYLANIR" (kullanıcı kararı Q1)
# =====================================================================================================
class OnayTest(ProjeTemel):
    def test_onaysiz_uygula_HICBIR_dosyaya_dokunmaz(self):
        self.f.ilerlet()
        r = self.f.calistir("plan")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        once = self.f.oku("proje-recetesi.ornek.md")
        r = self.f.calistir("uygula", "--otomatik")
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn("onay", self.cikti(r).lower())
        self.assertEqual(self.f.oku("proje-recetesi.ornek.md"), once)

    def test_KONTROL_onayli_uygula_dosyayi_yazar(self):
        """Yukarıdaki negatif testin vakum olmadığını gösterir (mutlu yol)."""
        self.f.ilerlet()
        self.planla()
        r = self.f.calistir("uygula", "--otomatik")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("Reçete v2", self.f.oku("proje-recetesi.ornek.md"))

    def test_onay_baska_projeye_gecerli_DEGIL(self):
        """Toplu tarama yok: bir projenin onayı ikinci projeyi açmaz."""
        self.f.ilerlet()
        self.planla()
        ikinci = SahteKlon(self, self.tmp)
        ikinci.home = self.f.home
        ikinci.proje = self.tmp / "proje2"
        ikinci.proje.mkdir()
        r = self.calistir("new_project.py", str(ikinci.proje), "--name", "PROJE2",
                          scripts_dir=self.f.home / "scripts")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        shutil.copytree(self.f.durum_dizini(), ikinci.durum_dizini())
        r = ikinci.calistir("uygula", "--otomatik")
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn("onay", self.cikti(r).lower())

    def test_onay_hedef_sablon_commiti_degisirse_gecersizlesir(self):
        self.f.ilerlet()
        self.planla()
        self.f.ilerlet({"templates/project/proje-recetesi.ornek.md": "# Reçete v3\nA\nB\nC\n"})
        r = self.f.calistir("uygula", "--otomatik")
        self.assertEqual(r.returncode, 2, self.cikti(r))

    def test_onay_kabul_proje_adini_ister(self):
        r = self.f.calistir("onay", "--kabul", "YANLIS-AD")
        self.assertEqual(r.returncode, 2, self.cikti(r))

    def test_onaysiz_isaretle_karar_yeni_dosyaya_DOKUNMAZ(self):
        """`uygula` gibi `isaretle --karar yeni|birlesik|yeniden-adlandir` de bir YAZMA yoludur:
        kullanıcının dosyasını EZER ⇒ onay kapısı burada da geçerli (Q1 · SKILL.md §"onay
        olmadan dosya yazmak"). Kapanış `onay.json` SİLİNEREK kurulur; tek değişken onaydır.

        ⚠ ÜÇ YAZMA KOLUNUN HEPSİ ölçülür. Tek kol ölçmek YETMEZ: `onay_dogrula`yı
        `if args.karar == "yeni":` ile SEÇİCİ hâle getiren bir kusur, yalnız `yeni` kolunu
        ölçen bir testin altında SAĞ KALIR — `birlesik` ve `yeniden-adlandir` onaysız yazmaya
        devam eder (ölçüldü: rc=0 · dosya değişti · `.yerel` kopya oluştu).
        (Test adı tarihseldir; kapsam üç karara genişletildi.)

        ⚠ VAKUM TUZAĞI: `birlesik` kolu, öneri dosyası YOKSA onay kapısına hiç varmadan
        "öneri dosyası yok" diye ZATEN rc=2 döner ⇒ o hâlde rc assertion'ı onay kapısını
        DEĞİL, eksik dosyayı ölçerdi. Bu yüzden öneri dosyası ÖNCEDEN üretilir ve her kolda
        hatanın KİMLİĞİ ("proje onayı YOK") ayrıca assert edilir."""
        self.f.yerel_degistir("AGENTS.md", self.f.oku("AGENTS.md").replace("son\n", "son yerel\n"))
        self.f.ilerlet()
        self.planla()
        self.assertIn("AGENTS.md", self.f.vakalar(), "fixture ön koşulu: dosya planda olmalı")
        # `oneri` onaya BAĞLI DEĞİLDİR → `birlesik` kolunun ön koşulu olarak şimdi üretilir.
        r = self.f.calistir("oneri", "AGENTS.md")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertTrue((self.f.durum_dizini() / "oneri" / "AGENTS.md").is_file(),
                        "fixture ön koşulu: `birlesik` kolu öneri dosyası ister")
        once = self.f.oku("AGENTS.md")
        self.assertIn("son yerel", once, "fixture ön koşulu: yerel satır diskte olmalı")
        yerel_kopya = self.f.proje / "AGENTS.md.yerel"

        (self.f.durum_dizini() / "onay.json").unlink()
        for karar in ("yeni", "birlesik", "yeniden-adlandir"):
            with self.subTest(karar=karar):
                r = self.f.calistir("isaretle", "AGENTS.md", "--karar", karar)
                # rc=2 başka bir arızadan da gelebilir → HANGİ hata olduğunu da ölç (vakum koruması).
                self.assertEqual(r.returncode, 2, self.cikti(r))
                self.assertIn("proje onayı YOK", self.cikti(r), self.cikti(r))
                self.assertEqual(self.f.oku("AGENTS.md"), once,
                                 "onaysız `isaretle` kullanıcının dosyasına DOKUNMAMALI")
                self.assertFalse(yerel_kopya.exists(),
                                 "onaysız `yeniden-adlandir` `.yerel` kopya da ÜRETMEMELİ")

        # KONTROL GRUBU: tek fark onaydır — geri verilince aynı komut gerçekten YAZAR.
        self.assertEqual(self.f.onayla().returncode, 0)
        r = self.f.calistir("isaretle", "AGENTS.md", "--karar", "yeni")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertNotEqual(self.f.oku("AGENTS.md"), once, self.cikti(r))

    def test_onaysiz_isaretle_yerel_ve_ertelendi_KARAR_KAYDETMEZ(self):
        """P5 ⓐ: `yerel`/`ertelendi` dosyaya yazmaz ama DURUMA yazar — kaydedilen karar `kapanis`ın
        o dosyayı "kapandı" saymasına yeter. Onay kapısı tek çağrı noktasında (tüm dallardan önce);
        SEÇİCİ bir kusur (`if args.karar in ("yeni", ...)`) yazma-kolu testinin altında SAĞ KALIR
        ⇒ bu iki kol ayrıca ölçülür. Hata kimliği de assert edilir (rc=2 başka arızadan gelebilir)."""
        self.f.yerel_degistir("AGENTS.md", self.f.oku("AGENTS.md").replace("son\n", "son yerel\n"))
        self.f.ilerlet()
        self.planla()
        self.assertIn("AGENTS.md", self.f.vakalar(), "fixture ön koşulu: dosya planda olmalı")
        durum_f = self.f.durum_dizini() / "durum.json"
        once = durum_f.read_bytes() if durum_f.exists() else None
        (self.f.durum_dizini() / "onay.json").unlink()
        for karar, ek in (("yerel", ()), ("ertelendi", ("--gerekce", "sonra bakilacak"))):
            with self.subTest(karar=karar):
                r = self.f.calistir("isaretle", "AGENTS.md", "--karar", karar, *ek)
                self.assertEqual(r.returncode, 2, self.cikti(r))
                self.assertIn("proje onayı YOK", self.cikti(r), self.cikti(r))
                self.assertEqual(durum_f.read_bytes() if durum_f.exists() else None, once,
                                 f"onaysız `--karar {karar}` durum.json'a karar yazdı")
        # KONTROL GRUBU: onay geri verilince aynı komut kararı KAYDEDER
        self.assertEqual(self.f.onayla().returncode, 0)
        r = self.f.calistir("isaretle", "AGENTS.md", "--karar", "yerel")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn('"yerel"', durum_f.read_text(encoding="utf-8"))

    def test_onaysiz_kapanis_SURUM_KAYDINI_ilerletmez(self):
        """Sürüm kaydı gelecekteki TÜM 3-yollu birleştirmelerin TABANI'dır. Onaysız bir kapanış
        tabanı ilerletirse sonraki `%guncelle-proje` kullanıcının hiç almadığı değişiklikleri
        "zaten sende var" sayar ⇒ SESSİZ VERİ KAYBI. Kontrol grubu (mutlu yol) =
        `AkisTest.test_kapanis_tamamlaninca_surum_kaydini_gunceller`."""
        self.f.ilerlet()
        self.planla()
        r = self.f.calistir("uygula", "--otomatik")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        once = self.f.kayit()
        (self.f.durum_dizini() / "onay.json").unlink()
        r = self.f.calistir("kapanis")
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn("proje onayı YOK", self.cikti(r), self.cikti(r))
        self.assertEqual(self.f.kayit(), once,
                         "onaysız kapanış şablon sürüm kaydını İLERLETMEMELİ")


# =====================================================================================================
# 5. DAMGA (SAP projesi)
# =====================================================================================================
class DamgaTest(ProjeTemel):
    sap = True

    def test_damga_blogu_karsilastirmaya_GIRMEZ(self):
        """AGENTS.md damgalıdır; template'te damga yoktur. Blok çıkarılmazsa her SAP projesinde V4 çıkar."""
        self.assertIn("AXET-SAP-YASAKLAR:BASLA", self.f.oku("AGENTS.md"))
        self.f.ilerlet()
        self.planla()
        self.assertEqual(self.f.vakalar().get("AGENTS.md"), "V1")

    def test_uygula_sonrasi_damga_KORUNUR(self):
        self.f.ilerlet()
        self.planla()
        r = self.f.calistir("uygula", "--otomatik")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        metin = self.f.oku("AGENTS.md")
        self.assertIn("AXET-SAP-YASAKLAR:BASLA", metin)
        self.assertIn("Proje Talimatı (v2)", metin)

    def test_bozuk_damga_DURDURUR(self):
        metin = self.f.oku("AGENTS.md")
        self.f.yerel_degistir("AGENTS.md", metin + "\n" + metin)   # iki BASLA/BITIR → bozuk
        self.f.ilerlet()
        r = self.planla()
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn("damga", self.cikti(r).lower())


# =====================================================================================================
# 6. ÖNERİ / İŞARETLE / KAPANIŞ / GERİ AL
# =====================================================================================================
class AkisTest(ProjeTemel):
    def kur_v4(self) -> None:
        self.f.yerel_degistir("AGENTS.md", self.f.oku("AGENTS.md").replace("son\n", "son yerel\n"))
        self.f.ilerlet()
        self.planla()

    def test_oneri_birlesik_dosya_ve_iki_farki_basar(self):
        self.kur_v4()
        r = self.f.calistir("oneri", "AGENTS.md")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("T→L", self.cikti(r))
        self.assertIn("T→Y", self.cikti(r))
        birlesik = (self.f.durum_dizini() / "oneri" / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("Proje Talimatı (v2)", birlesik)
        self.assertIn("son yerel", birlesik)

    def test_isaretle_birlesik_yazar_ve_geri_okuyup_dogrular(self):
        self.kur_v4()
        self.f.calistir("oneri", "AGENTS.md")
        r = self.f.calistir("isaretle", "AGENTS.md", "--karar", "birlesik")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        metin = self.f.oku("AGENTS.md")
        self.assertIn("Proje Talimatı (v2)", metin)
        self.assertIn("son yerel", metin)

    def test_isaretle_cakisma_isareti_kalirsa_cikis_1(self):
        self.kur_v4()
        self.f.calistir("oneri", "AGENTS.md")
        oneri = self.f.durum_dizini() / "oneri" / "AGENTS.md"
        oneri.write_text(oneri.read_text(encoding="utf-8") + "\n<<<<<<< YEREL\n", encoding="utf-8")
        r = self.f.calistir("isaretle", "AGENTS.md", "--karar", "birlesik")
        self.assertEqual(r.returncode, 1, self.cikti(r))

    def test_isaretle_yerel_karari_dosyaya_dokunmaz(self):
        self.kur_v4()
        once = self.f.oku("AGENTS.md")
        r = self.f.calistir("isaretle", "AGENTS.md", "--karar", "yerel")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertEqual(self.f.oku("AGENTS.md"), once)

    def test_ertelendi_gerekce_ister(self):
        self.kur_v4()
        r = self.f.calistir("isaretle", "AGENTS.md", "--karar", "ertelendi")
        self.assertEqual(r.returncode, 2, self.cikti(r))
        # rc=2 başka bir DUR'dan da gelebilir → hatanın KİMLİĞİ ölçülür (vakum koruması)
        self.assertIn("GEREKÇE ister", self.cikti(r))
        # kontrol grubu + kapanış kolu: gerekçeyle kabul edilir, kapanışta WARN (PASS DEĞİL) basılır
        self.assertEqual(self.f.calistir("uygula", "--otomatik").returncode, 0)
        r = self.f.calistir("isaretle", "AGENTS.md", "--karar", "ertelendi", "--gerekce", "elle bakılacak")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.f.calistir("kapanis")
        rapor = (self.f.durum_dizini() / "RAPOR.md").read_text(encoding="utf-8")
        self.assertTrue(any(s.startswith("[WARN] AGENTS.md") and "atlandi (elle bakılacak)" in s
                            for s in rapor.splitlines()), rapor)

    def test_kapanis_bekleyen_dosya_varsa_cikis_1(self):
        self.kur_v4()
        self.f.calistir("uygula", "--otomatik")
        r = self.f.calistir("kapanis")
        self.assertEqual(r.returncode, 1, self.cikti(r))
        self.assertIn("KAPANMADI", self.cikti(r))

    def test_kapanis_tamamlaninca_surum_kaydini_gunceller(self):
        yeni = self.f.ilerlet()
        self.planla()
        r = self.f.calistir("uygula", "--otomatik")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        r = self.f.calistir("kapanis")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertEqual(self.f.kayit()["template_commit"], yeni)
        self.assertEqual(self.f.kayit()["kaynak"], "guncelle-proje")
        self.assertIn("KAPSAM —", self.cikti(r))

    def test_kapanis_diskten_YENIDEN_dogrular(self):
        """durum.json 'dogrulandi' dese de disk farklıysa kapanış 1 döner (§6 atlanamazlık)."""
        self.f.ilerlet()
        self.planla()
        self.f.calistir("uygula", "--otomatik")
        self.f.yerel_degistir("proje-recetesi.ornek.md", "# elle bozuldu\n")
        r = self.f.calistir("kapanis")
        self.assertEqual(r.returncode, 1, self.cikti(r))

    def test_kapanis_durum_UYGULANDI_kalan_dosyayi_KAPATMAZ(self):
        """`uygula` yazıp DOĞRULAYAMADIĞI dosyayı `durum: uygulandi` bırakır. Kapanış bu kaydı
        eksik saymazsa dosya `[PASS]` basılır, çıkış 0 olur ve sürüm kaydı ilerler. Diskten yeniden
        doğrulama bu durumu yakalamaz (yalnız `dogrulandi` kaydına bakar). Mutasyon PK6
        (`("bekliyor",)`'a daraltma) bu testten önce modülün TAMAMINI yeşil bırakıyordu."""
        self.f.ilerlet()
        self.planla()
        r = self.f.calistir("uygula", "--otomatik")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        y = self.f.durum_dizini() / "durum.json"
        veri = json.loads(y.read_text(encoding="utf-8"))
        veri["dosyalar"]["proje-recetesi.ornek.md"]["durum"] = "uygulandi"
        y.write_text(json.dumps(veri, ensure_ascii=False), encoding="utf-8")
        once = self.f.kayit()
        r = self.f.calistir("kapanis")
        self.assertEqual(r.returncode, 1, self.cikti(r))
        self.assertIn("proje-recetesi.ornek.md: durum 'uygulandi'", self.cikti(r))
        self.assertEqual(self.f.kayit(), once, "doğrulanmamış yazımla sürüm kaydı İLERLEMEMELİ")

    def test_kapanis_CAKISMA_ISARETI_kalan_dosyayi_KAPATMAZ(self):
        """`test_kapanis_diskten_YENIDEN_dogrular`ın İKİNCİ kolu. O test yalnız HASH kolunu
        ölçer; bu test hash'i bilerek EŞLETİR (dosya bozulduktan SONRA `isaretle --karar yerel`
        ile beklenen özet diskten yeniden hesaplanır) ⇒ kapanışı durdurabilecek TEK şey
        çakışma-işareti koludur.

        ⚠ ÖLÇÜM TUZAĞI (gate'in kendi aracı buna düştü): `kapanis` RAPOR.md'yi stdout'a basar
        ve onun KAPSAM beyanında da "çakışma işareti" ifadesi GEÇER. Bu yüzden aranan dize
        kasten dar tutuldu: "AGENTS.md: çakışma işareti duruyor" (yalnız `eksikler` satırı)."""
        self.f.ilerlet()
        self.planla()
        r = self.f.calistir("uygula", "--otomatik")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.f.yerel_degistir("AGENTS.md", self.f.oku("AGENTS.md") +
                              "\n<<<<<<< YEREL\nx\n=======\ny\n>>>>>>> YENİ\n")
        r = self.f.calistir("isaretle", "AGENTS.md", "--karar", "yerel")
        self.assertEqual(r.returncode, 0, self.cikti(r))   # ön koşul: hash kolu artık EŞLEŞİR
        once = self.f.kayit()
        r = self.f.calistir("kapanis")
        self.assertEqual(r.returncode, 1, self.cikti(r))
        self.assertIn("AGENTS.md: çakışma işareti duruyor", self.cikti(r), self.cikti(r))
        self.assertEqual(self.f.kayit(), once,
                         "kapanmayan kapanış şablon sürüm kaydını GÜNCELLEMEMELİ")

    def test_plan_disi_dosyaya_oneri_REDDEDILIR(self):
        """§7: kart kapsamdır — planda olmayan bir dosyaya dokunulmaz. (`isaretle` de aynı
        `_plan_kaydi` kapısından geçer; burada gate'in ölçtüğü `oneri` yolu ölçülür.)"""
        self.f.ilerlet()
        self.planla()
        disardaki = ".axet-code.json"
        self.assertNotIn(disardaki, self.f.vakalar(), "fixture ön koşulu: dosya planda OLMAMALI")
        self.assertTrue((self.f.proje / disardaki).is_file(),
                        "fixture ön koşulu: dosya projede VAR (yani 'yok' diye reddedilmiyor)")
        r = self.f.calistir("oneri", disardaki)
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn("planda yok", self.cikti(r), self.cikti(r))
        self.assertFalse((self.f.durum_dizini() / "oneri" / disardaki).exists(),
                         "plan DIŞI dosyaya öneri YAZILMAMALI")

    def test_kapanis_kabul_ile_cikis_3(self):
        self.kur_v4()
        self.f.calistir("uygula", "--otomatik")
        r = self.f.calistir("kapanis", "--kabul", "kullanıcı bilerek yarım bıraktı")
        self.assertEqual(r.returncode, 3, self.cikti(r))
        # `--kabul` bir KAPANIŞTIR: sürüm kaydı hedef şablona ilerler (komut_kapanis `kod in (0, 3)`).
        # Bu dal ölçülmüyordu — `kod == 0`a daraltmak modülü YEŞİL bırakıyordu (mutasyon PK3).
        self.assertEqual(self.f.kayit()["template_commit"], self.f.plan()["yeni_commit"],
                         self.cikti(r))
        self.assertIn("kullanıcı bilerek yarım bıraktı",
                      (self.f.durum_dizini() / "RAPOR.md").read_text(encoding="utf-8"))

    def test_geri_al_yedekten_geri_yazar(self):
        self.f.ilerlet()
        self.planla()
        once = self.f.oku("proje-recetesi.ornek.md")
        self.f.calistir("uygula", "--otomatik")
        self.assertNotEqual(self.f.oku("proje-recetesi.ornek.md"), once)
        r = self.f.calistir("geri-al", "--hepsi")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertEqual(self.f.oku("proje-recetesi.ornek.md"), once)

    def test_ekip_reposu_uyarisi_onkontrolde_gorunur(self):
        self.git(self.f.proje, "remote", "add", "origin", "https://example.invalid/x.git")
        r = self.f.calistir("onkontrol")
        self.assertIn("ekip", self.cikti(r).lower())

    def test_ekip_reposu_denetlenemezse_OLCULEMEDI_der(self):
        """rc taraması 2026-09-18 (Z15): `git remote` rc≠0 iken EKİP REPOSU uyarısı sessizce
        düşüyordu. Arıza: proje `.git/config`'i bozuk (her git çağrısı rc=128)."""
        (self.f.proje / ".git" / "config").write_text("[bozuk", encoding="utf-8")
        r = self.f.calistir("onkontrol")
        self.assertIn("ekip reposu denetimi ÖLÇÜLEMEDİ (git remote rc=", self.cikti(r))

    def test_git_deposu_olmayan_proje_OLCULEMEDI_gurultusu_uretmez(self):
        """Bug gate 2026-09-19 #5: git'siz projede `git remote` de rc=128 döner ⇒ "ÖLÇÜLEMEDİ"
        gürültüsü basılıyordu. Bozuk `.git/config` (üstteki test) ile ayrım `.git`in varlığıdır."""
        (self.f.proje / ".git").rename(self.f.proje / ".git_gizli")
        try:
            r = self.f.calistir("onkontrol")
            self.assertIn("ekip reposu: proje bir git deposu değil", self.cikti(r))
            self.assertNotIn("ekip reposu denetimi ÖLÇÜLEMEDİ", self.cikti(r))
        finally:
            (self.f.proje / ".git_gizli").rename(self.f.proje / ".git")

    def test_durum_tablosu_basar(self):
        self.f.ilerlet()
        self.planla()
        r = self.f.calistir("durum")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("proje-recetesi.ornek.md", self.cikti(r))


# =====================================================================================================
# 7. P2 İLE PAYLAŞIM (kopyalanmadı, çağrıldı)
# =====================================================================================================
class GuncellikTest(GeciciTest):
    """`%guncelle` sonrası klon "geride" SAYILMAMALI (Z29, 2026-09-21 — kullanıcı canlıda yaşadı).

    Motor yayınları MERGE etmez; kalemleri yerel commit'le uygular ⇒ `HEAD..origin/main` commit
    sayısı güncellemeden sonra da > 0 kalır. Eski ölçüm bu yüzden her `%guncelle`'den sonra
    `%guncelle-proje`'yi "klon N commit geride" diye DURDURUYORDU. Doğru ölçü `session_brief`
    ile aynıdır (Q4): bekleyen YAYIN KALEMİ var mı.
    """

    def _kur(self) -> tuple[Path, Path]:
        yukari, klon = self.tmp / "yukari", self.tmp / "klon"
        yukari.mkdir()
        g = self.git
        g(yukari, "init", "-q", "-b", "main")
        katalog = {"yayinlar": [{"etiket": "v0.1.0", "kalemler": [{"id": "k1"}]}]}
        self.yaz(yukari / "guncelle" / "yayinlar.json", json.dumps(katalog))
        self.yaz(yukari / "a.txt", "v1\n")
        g(yukari, "add", "-A"); g(yukari, "commit", "-q", "-m", "v1"); g(yukari, "tag", "v0.1.0")
        katalog["yayinlar"].append({"etiket": "v0.2.0", "kalemler": [{"id": "k2"}]})
        self.yaz(yukari / "guncelle" / "yayinlar.json", json.dumps(katalog))
        self.yaz(yukari / "a.txt", "v2\n")
        g(yukari, "add", "-A"); g(yukari, "commit", "-q", "-m", "v2"); g(yukari, "tag", "v0.2.0")
        g(self.tmp, "clone", "-q", str(yukari), str(klon))
        g(klon, "reset", "-q", "--hard", "v0.1.0")
        return yukari, klon

    def _geride(self, klon: Path):
        if str(GERCEK_SCRIPTS) not in sys.path:
            sys.path.insert(0, str(GERCEK_SCRIPTS))
        import guncelle_proje as gp  # noqa: PLC0415
        return gp.Klon(klon).geride_mi()

    def test_1_guncelle_sonrasi_klon_geride_degil(self) -> None:
        _, klon = self._kur()
        # motorun yaptığı: içeriği yerel commit'le uygula + uygulanan.json'a yaz
        self.yaz(klon / "a.txt", "v2\n")
        self.git(klon, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-am",
                 "guncelle: v0.2.0 kalemler k2")
        self.yaz(klon / ".axet-guncelleme" / "uygulanan.json",
                 json.dumps({"surum": 1, "kalemler": {"k2": {"durum": "uygulandi"}}}))
        self.assertGreater(int(self.git(klon, "rev-list", "--count", "HEAD..@{u}").stdout), 0,
                           "kalibrasyon: commit sayısı hâlâ > 0 olmalı (hatanın koşulu)")
        geride, ayrinti = self._geride(klon)
        self.assertIs(geride, False, ayrinti)

    def test_2_uygulanmamis_kalem_varsa_geride(self) -> None:
        _, klon = self._kur()
        geride, ayrinti = self._geride(klon)
        self.assertIs(geride, True, ayrinti)
        self.assertIn("k2", ayrinti)

    def test_3_yayini_iceren_taze_klon_geride_degil(self) -> None:
        _, klon = self._kur()
        self.git(klon, "reset", "-q", "--hard", "v0.2.0")
        geride, ayrinti = self._geride(klon)
        self.assertIs(geride, False, ayrinti)


class PaketSablonuRcTest(unittest.TestCase):
    """rc taraması 2026-09-18 (Z15): `git diff` rc≠0 "paket şablonu: değişiklik yok" diye
    okunuyordu. Taklit Baglam: `k.git` rc=128 döner; kontrol grubu rc=0 + boş çıktı."""

    def _satir(self, rc: int, stdout: str = "") -> str:
        import guncelle_proje as gp  # noqa: PLC0415
        from types import SimpleNamespace
        cp = subprocess.CompletedProcess([], rc, stdout=stdout, stderr="fatal: bozuk")
        b = SimpleNamespace(taban_commit="aaa", yeni_commit="bbb",
                            k=SimpleNamespace(git=lambda *a, **kw: cp))
        return gp._paket_sablonu_satiri(b)

    def test_diff_basarisizsa_olculemedi(self):
        satir = self._satir(128)
        self.assertIn("ÖLÇÜLEMEDİ (git diff rc=128)", satir)
        self.assertNotIn("değişiklik yok", satir)

    def test_kontrol_grubu_bos_diff_degisiklik_yok(self):
        self.assertIn("değişiklik yok", self._satir(0, ""))


class DamgaKapanisTest(ProjeTemel):
    """Kapanışın damga bölümü (yeniden basma + bozuk damga) hiç ölçülmüyordu: SAP projesinde
    kapanış koşan test yoktu. Mutasyon PK11/PK12 modülün TAMAMINI yeşil bırakıyordu (2026-09-18)."""
    sap = True

    def _uygulanmis(self) -> None:
        self.f.ilerlet()
        self.planla()
        r = self.f.calistir("uygula", "--otomatik")
        self.assertEqual(r.returncode, 0, self.cikti(r))

    def test_kapanis_elle_degismis_damgayi_YENIDEN_BASAR(self):
        self._uygulanmis()
        m = self.f.oku("AGENTS.md")
        i = m.index("\n", m.index("AXET-SAP-YASAKLAR:BASLA")) + 1
        self.f.yerel_degistir("AGENTS.md", m[:i] + "ELLE EKLENDI\n" + m[i:])
        r = self.f.calistir("kapanis")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertNotIn("ELLE EKLENDI", self.f.oku("AGENTS.md"), "damga yeniden basılmadı")
        rapor = (self.f.durum_dizini() / "RAPOR.md").read_text(encoding="utf-8")
        self.assertIn("damga: guncel", rapor)

    def test_kapanis_bozuk_damgada_KAPANMAZ(self):
        self._uygulanmis()
        m = self.f.oku("AGENTS.md")
        self.f.yerel_degistir("AGENTS.md", m + "\n" + m)   # iki BASLA/BITIR → bozuk
        once = self.f.kayit()
        r = self.f.calistir("kapanis")
        self.assertEqual(r.returncode, 1, self.cikti(r))
        # RAPOR'un `## Damga` satırı da "BOZUK" der ⇒ ölçüt `EKSİK:` satırıdır (vakum koruması).
        eksikler = [x for x in r.stderr.splitlines() if x.startswith("EKSİK:")]
        self.assertTrue(any("damgası BOZUK" in x for x in eksikler), eksikler)
        self.assertEqual(self.f.kayit(), once, "bozuk damgayla sürüm kaydı İLERLEMEMELİ")


class UygulaSavunmaDaliTest(ProjeTemel):
    """`uygula`nın iki savunma dalı fixture ile tetiklenemiyor (yazım her zaman tutuyor, yeni içerik
    her zaman okunuyor) ⇒ dallar tamamen silinse de modül YEŞİL kalıyordu (mutasyon PU8/PU10,
    2026-09-18). Arıza süreç İÇİNDE enjekte edilir; motor `--klon` ile sahte klona yönlendirilir."""

    def _uygula_icerde(self, **yamalar):
        import contextlib
        import io
        from unittest import mock
        if str(GERCEK_SCRIPTS) not in sys.path:
            sys.path.insert(0, str(GERCEK_SCRIPTS))
        import guncelle_proje as gp
        out, err = io.StringIO(), io.StringIO()
        with contextlib.ExitStack() as st:
            for ad, yeni in yamalar.items():
                sinif, oznitelik = ad.split("__")
                st.enter_context(mock.patch.object(getattr(gp, sinif), oznitelik, yeni))
            st.enter_context(contextlib.redirect_stdout(out))
            st.enter_context(contextlib.redirect_stderr(err))
            rc = gp.main(["--proje", str(self.f.proje), "--klon", str(self.f.home),
                          "uygula", "--otomatik"])
        return rc, out.getvalue() + err.getvalue()

    def test_yazim_dogrulanamazsa_FAIL_ve_durum_uygulandi(self):
        self.f.ilerlet()
        self.planla()
        self.assertEqual(self.f.vakalar().get("proje-recetesi.ornek.md"), "V1", "fixture ön koşulu")

        def bozuk_yaz(proje, rel, veri_lf):
            (proje.kok / rel).parent.mkdir(parents=True, exist_ok=True)
            (proje.kok / rel).write_bytes(b"# yazim sessizce bozuldu\n")
        rc, c = self._uygula_icerde(Proje__yaz=bozuk_yaz)
        self.assertEqual(rc, 1, c)
        self.assertIn("proje-recetesi.ornek.md: yazıldı ama doğrulanamadı", c)
        d = json.loads((self.f.durum_dizini() / "durum.json").read_text(encoding="utf-8"))["dosyalar"]
        self.assertEqual(d["proje-recetesi.ornek.md"]["durum"], "uygulandi", d)

    def test_yeni_icerik_okunamazsa_dosyaya_DOKUNMAZ(self):
        self.f.ilerlet()
        self.planla()
        once = self.f.oku("proje-recetesi.ornek.md")
        rc, c = self._uygula_icerde(Baglam__yeni_icerik=lambda b, rel: None)
        self.assertEqual(rc, 1, c)
        self.assertIn("yeni sürümde içerik okunamadı", c)
        self.assertEqual(self.f.oku("proje-recetesi.ornek.md"), once,
                         "yeni içerik yokken dosya boşaltıldı/ezildi")


class PaylasimTest(unittest.TestCase):
    def test_3_yollu_birlestirme_P2den_gelir(self):
        sys.path.insert(0, str(GERCEK_SCRIPTS))
        import guncelle
        import guncelle_proje
        self.assertIs(guncelle_proje.g.birlestir, guncelle.birlestir)
        self.assertIs(guncelle_proje.g.vaka_kodu, guncelle.vaka_kodu)
        self.assertIs(guncelle_proje.g.yerel_fark_orani, guncelle.yerel_fark_orani)

    def test_birlestir_klon_parametresi_None_ile_calisir(self):
        """`guncelle.birlestir` klonu kullanmaz; P2 ileride kullanırsa bu test kırmızı olur.

        ⚠ Değişiklikler UZAK satırlarda: git BİTİŞİK satır değişikliklerini de çakışma sayar
        (TASARIM §14 "ÖLÇÜLDÜ 2026-09-17"; bu turda `a`/`b` ile yeniden ölçüldü → cakisma=1).
        """
        sys.path.insert(0, str(GERCEK_SCRIPTS))
        import guncelle
        birlesik, cakisma = guncelle.birlestir(None, "x.md", b"a\nb\nc\nd\ne\n",
                                               b"a yerel\nb\nc\nd\ne\n", b"a\nb\nc\nd\ne yeni\n")
        self.assertEqual(cakisma, 0)
        self.assertIn(b"a yerel", birlesik)
        self.assertIn(b"e yeni", birlesik)


# =====================================================================================================
# 8. TETİK KABLOLAMASI — doctor + session_brief (TASARIM §9)
# =====================================================================================================
class TetikKablolamaTest(GeciciTest):
    """⚠ Tetik GERÇEK GİRİŞ NOKTASINDAN ölçülür: `doctor.py` / `session_brief.py` ALT SÜREÇ olarak
    koşturulur, fonksiyon doğrudan çağrılmaz. "Kod var" ≠ "kablolu": bu dosyalara paralel
    lane'ler (P4/P7/Z5) de dokunuyor; çağrı noktası kayarsa tetik sessizce ölü kalır ve
    fonksiyonu doğrudan çağıran bir test bunu GÖREMEZ.
    """

    def kayit_yolu(self, proje: Path) -> Path:
        return proje / ".axet-code" / "sablon-surumu.json"

    def test_doctor_guncel_sablonda_PASS(self):
        proje = self.proje("p_guncel")
        r = self.calistir("doctor.py", cwd=proje)
        self.assertIn("proje şablonu güncel", self.cikti(r), self.cikti(r))

    def test_doctor_kayitsiz_projede_WARN(self):
        proje = self.proje("p_kayitsiz")
        self.kayit_yolu(proje).unlink()
        r = self.calistir("doctor.py", cwd=proje)
        self.assertIn("proje şablon sürümü kayıtlı değil", self.cikti(r), self.cikti(r))
        self.assertIn("%guncelle-proje", self.cikti(r))

    def test_doctor_eski_sablonda_WARN(self):
        proje = self.proje("p_eski")
        # ⚠ "templates/project"e dokunan commit bu repoda ŞU AN tek tanedir (ölçüldü 2026-09-17:
        # `git log --format=%H -- templates/project | wc -l` = 1) ⇒ "en eski şablon commit'i"
        # ile "en yeni" AYNIDIR ve eski-kayıt senaryosu kurulamaz. Bu yüzden kayda gerçek ama
        # BAŞKA bir ata commit yazılır; ölçülen şey "kayıt ≠ güncel" dalıdır.
        # Sığ klonda (CI checkout'u, fetch-depth=1) ata commit YOKTUR ⇒ senaryo kurulamaz; geçmişe
        # bağlı öteki testlerle aynı kural (test_install EmekliKuralTest): atla, sessiz geçme.
        # Tüketici klonu tamdır (kur.ps1 --depth kullanmaz; test_kur.py bunu denetler).
        #
        # ⛔ v0.5.6 (2026-09-23, birleşim dalında kırmızı): eskiden `HEAD~1` alınıyordu. HEAD'in hemen
        # altındaki commit şablona DOKUNAN son commit olduğunda (ölçüldü: HEAD~1 = 8339d45 = son
        # `templates/project` commit'i) "eski" ile "güncel" aynı çıkıyor, test geçmişin ŞEKLİNE bağlı
        # kırılıyordu. Artık eski = GÜNCEL ŞABLON COMMIT'İNİN EBEVEYNİ: ebeveyn varsa tanım gereği
        # güncelden farklıdır. Güncel şablon commit'i kök commit'se (tek commit'li/squash geçmiş, sığ
        # klon) başka commit yoktur ⇒ senaryo kurulamaz: açık nedenle ATLA.
        import new_project  # noqa: PLC0415  (_helpers scripts/'i yola ekledi)
        yollar = new_project.sablon_yollari((proje / "sap-project.json").is_file())
        guncel = self.git(AXET_HOME, "log", "-1", "--format=%H", "--", *yollar).stdout.strip()
        self.assertTrue(guncel, "fixture ön koşulu: şablon commit'i okunamadı")
        ebeveyn = self.git(AXET_HOME, "rev-parse", "--verify", "--quiet", f"{guncel}^",
                           kontrol=False)
        if ebeveyn.returncode != 0:
            self.skipTest(f"şablon commit'i {guncel[:10]} kök commit (tek commit'li/sığ geçmiş): "
                          "'eski kayıt' için klonda başka commit yok — tam geçmişte koşar")
        eski = ebeveyn.stdout.strip()
        self.assertNotEqual(eski, guncel, "fixture ön koşulu: iki commit farklı olmalı")
        kayit = json.loads(self.kayit_yolu(proje).read_text(encoding="utf-8"))
        kayit["template_commit"] = eski
        self.kayit_yolu(proje).write_text(json.dumps(kayit, ensure_ascii=False), encoding="utf-8")
        r = self.calistir("doctor.py", cwd=proje)
        self.assertIn("proje şablonu eski", self.cikti(r), self.cikti(r))
        self.assertIn("%guncelle-proje", self.cikti(r))

    def test_session_brief_PROJE_SABLONU_bolumunu_MAIN_uzerinden_basar(self):
        proje = self.proje("p_brief")
        self.kayit_yolu(proje).unlink()
        r = self.calistir("session_brief.py", "--project-dir", str(proje), "--no-fetch", cwd=proje)
        cikti = self.cikti(r)
        self.assertIn("PROJE ŞABLONU:", cikti, cikti)
        self.assertIn("proje şablon sürümü kayıtlı değil", cikti, cikti)
        self.assertIn("her proje AYRI onaylanır", cikti, cikti)

    def test_session_brief_guncel_projede_de_bolumu_basar(self):
        """KONTROL GRUBU: bölüm yalnız uyarı halinde değil, HER koşumda görünür."""
        proje = self.proje("p_brief2")
        r = self.calistir("session_brief.py", "--project-dir", str(proje), "--no-fetch", cwd=proje)
        self.assertIn("PROJE ŞABLONU:", self.cikti(r), self.cikti(r))
        self.assertIn("proje şablonu güncel", self.cikti(r), self.cikti(r))


class DamgaGovdeTest(unittest.TestCase):
    """`sap_stamp.govde` `damgala`nın TAM TERSİ olmalı (ölçüldü: değilse her SAP AGENTS.md V4c)."""

    def test_govde_damgalanin_tersidir(self):
        sys.path.insert(0, str(GERCEK_SCRIPTS))
        import sap_stamp
        ornekler = ["# Baslik\n\n## Bolum\nmetin\n",
                    "# Baslik\nsatir\n\n## A\nx\n\n## B\ny\n"]
        for govde in ornekler:
            damgali, _ = sap_stamp.damgala(govde)
            self.assertIn("AXET-SAP-YASAKLAR:BASLA", damgali)
            self.assertEqual(sap_stamp.govde(damgali), govde)

    def test_damgasiz_metin_aynen_doner(self):
        sys.path.insert(0, str(GERCEK_SCRIPTS))
        import sap_stamp
        damgasiz = "# yok\n"
        self.assertEqual(sap_stamp.govde(damgasiz), damgasiz)


# =====================================================================================================
# 9. TEK-BAŞINA CR (K1, karar 2026-09-20)
# =====================================================================================================
class TekBasinaCRTest(GeciciTest):
    """`new_project` tek-başına CR'yi çeviriyordu, `guncelle_proje._norm` çevirmiyordu.

    Mevcut `PlanTest.test_CRLF_proje_dosyasi_yerel_degismis_SAYILMAZ`ın kardeşi: o CRLF'i
    ölçer, bu tek-başına CR'i. Sonucun SESSİZ olması bu maddeyi önemli kılıyor — ayrışan
    dosya V3'e düşer ve V3 "listelenmez, yalnız sayılır" ⇒ güncelleme sorulmadan kaybolur.

    KAPSAM — bakılmayanlar: ikili dosyada davranış (ayrı ölçüt `ikili_mi` ile ayrılır,
    `_yazilacak` testleri kapsar) · Linux/macOS (Windows'ta ölçüldü) · gerçek tüketici klonu.
    """

    CR_YOL = "templates/project/cr-li.md"
    REL = "cr-li.md"

    def _klon(self, v1: bytes) -> SahteKlon:
        return SahteKlon(self, self.tmp).uret(ikili={self.CR_YOL: v1})

    @staticmethod
    def _tek_cr_var(ham: bytes) -> bool:
        """CRLF'leri düşürdükten sonra geriye CR kalıyor mu — CRLF ile karışmaz."""
        return b"\r" in ham.replace(b"\r\n", b"")

    def test_1_KONTROL_fixture_gercekten_tek_basina_CR_uretiyor(self):
        """Ön koşul ölçümü: bu satır olmadan 2. test 'hiç tetiklenmediği için' de geçerdi."""
        f = self._klon(b"# CR\rbir\n")
        self.assertTrue(self._tek_cr_var((f.home / self.CR_YOL).read_bytes()),
                        "fixture ön koşulu: ŞABLONDA tek-başına CR olmalı")
        self.assertFalse(self._tek_cr_var((f.proje / self.REL).read_bytes()),
                         "new_project tek-başına CR'yi çevirmeli (V3 sahte-farkın kaynağı)")

    def test_2_tek_basina_CR_li_dosya_yerel_degismis_SAYILMAZ(self):
        """Kullanıcı DOKUNMADI, şablon ilerledi ⇒ vaka V1 (otomatik al) olmalı.

        Kusurluyken proje dosyası (CR→LF) ile taban blob'u (CR duruyor) ayrışır, dosya
        "kullanıcı değiştirmiş" sayılır ve V1 olmaktan çıkar.
        """
        f = self._klon(b"# CR\rbir\n")
        f.ilerlet({self.CR_YOL: "# CR\riki\n"})
        r = f.onayla()
        self.assertEqual(r.returncode, 0, self.cikti(r))
        r = f.calistir("plan")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertEqual(f.vakalar().get(self.REL), "V1", self.cikti(r))

    def test_3_KONTROL_ayni_klonda_CRsiz_dosya_da_V1(self):
        """Yanlış pozitif kontrolü: V1 sonucunu üreten şey CR değil, 'kullanıcı dokunmadı'."""
        f = self._klon(b"# CR\rbir\n")
        f.ilerlet({self.CR_YOL: "# CR\riki\n",
                   "templates/project/proje-recetesi.ornek.md": "# Reçete v2\nA\nB\nC\n"})
        self.assertEqual(f.onayla().returncode, 0)
        r = f.calistir("plan")
        self.assertEqual(f.vakalar().get("proje-recetesi.ornek.md"), "V1", self.cikti(r))

    def test_4_iki_yol_TEK_normalizasyona_bagli(self):
        """Kablolama: davranış eşitliği tesadüf değil, `_norm` gerçekten devrediyor mu?"""
        sys.path.insert(0, str(GERCEK_SCRIPTS))
        import guncelle_proje as gp
        import new_project as np
        ornek = b"a\rb\r\nc\n"
        self.assertEqual(np.satir_sonu_normalize(ornek), b"a\nb\nc\n")
        self.assertEqual(gp._norm(ornek), np.satir_sonu_normalize(ornek))
        self.assertIsNone(gp._norm(None))


class Z55EskiDamgaGuncelSablonTest(ProjeTemel):
    """⛔ Z55 (2026-09-22, canlı vaka): `%guncelle` kanonik SAP metnini yükseltti (core/sap/00-sap.md)
    ama proje ŞABLON dosyaları değişmedi ⇒ `plan` "işlem gerektiren dosya yok" deyip rc=1 ile
    plan.json YAZMADAN çıkıyordu; damgayı basan tek yer (`kapanis`) plan.json istediği için hiç
    koşmuyordu. Proje eski `SAP-STAMP-ID` ile kaldı, `doctor` FAIL verdi.

    Fixture gerçek vakayı kurar: klonda YALNIZ `core/sap/00-sap.md` ilerler (şablon commit'i aynı).
    KAPSAM — bakılmayan: gerçek `doctor` çıktısı (yayın provası ölçer) · Linux/macOS.
    """
    sap = True
    YENI_ID = "AXET-SAP-9.9.9"

    def _kanonigi_yukselt(self) -> None:
        import re  # noqa: PLC0415
        yol = self.f.home / "core" / "sap" / "00-sap.md"
        metin = yol.read_text(encoding="utf-8")
        yeni = re.sub(r"^SAP-CORE-ID:\s*\S+", f"SAP-CORE-ID: {self.YENI_ID}", metin, count=1, flags=re.M)
        self.assertNotEqual(yeni, metin, "fixture geçersiz: SAP-CORE-ID satırı yok")
        with open(yol, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(yeni)
        self.git(self.f.home, "add", "-A")
        self.git(self.f.home, "commit", "-q", "-m", "kanonik yukseldi")

    def test_1_eski_damga_guncel_sablonda_plan_0_ve_DAMGA_kalemi(self):
        self._kanonigi_yukselt()
        r = self.planla()
        self.assertEqual(r.returncode, 0, self.cikti(r))
        plan = self.f.plan()
        self.assertEqual(plan["dosyalar"], [], "şablon dosyası değişmedi; kalem yalnız damga olmalı")
        self.assertEqual(plan["damga"]["durum"], "farkli", plan.get("damga"))
        self.assertIn(self.YENI_ID, plan["damga"]["ayrinti"])
        self.assertIn("DAMGA", self.cikti(r), "kullanıcı plan tablosunda damga kalemini GÖRMELİ")

    def test_2_akis_sonunda_damga_kanonik_ve_manifest_komutu_verilir(self):
        self._kanonigi_yukselt()
        self.assertEqual(self.planla().returncode, 0)
        r = self.f.calistir("uygula", "--otomatik")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        manifest = self.f.proje / ".axet-code" / "behavior-manifest.json"
        once = manifest.read_bytes() if manifest.is_file() else None
        r = self.f.calistir("kapanis")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        metin = self.f.oku("AGENTS.md")
        self.assertIn(f"SAP-STAMP-ID: {self.YENI_ID}", metin)
        self.assertEqual(metin.count("AXET-SAP-YASAKLAR:BASLA"), 1)
        rapor = (self.f.durum_dizini() / "RAPOR.md").read_text(encoding="utf-8")
        self.assertIn("damga: guncel", rapor)
        self.assertIn("Davranış yüzeyi DEĞİŞTİ", rapor)
        self.assertIn("AGENTS.md kesin yasak damgası yenilendi", rapor)
        self.assertIn('behavior_manifest.py" generate --project-dir "', rapor)
        self.assertIn(str(self.f.proje.resolve()), rapor)
        # Z48: motor manifest'i KENDİSİ yenilemez — onay kullanıcının terminalinde kalır
        sonra = manifest.read_bytes() if manifest.is_file() else None
        self.assertEqual(once, sonra, "guncelle-proje behavior manifest'e DOKUNMAMALI (Z48)")

    def test_3_KONTROL_damga_guncel_ve_sablon_guncelse_plan_1(self):
        r = self.planla()
        self.assertEqual(r.returncode, 1, self.cikti(r))
        self.assertNotIn("DAMGA", self.cikti(r))
        self.assertFalse((self.f.durum_dizini() / "plan.json").exists())

    def test_4_NEGATIF_bozuk_damga_guncel_sablonda_da_DURDURUR(self):
        self._kanonigi_yukselt()
        m = self.f.oku("AGENTS.md")
        self.f.yerel_degistir("AGENTS.md", m + "\n" + m)   # iki BASLA/BITIR → bozuk
        r = self.planla()
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn("damgası BOZUK", self.cikti(r))
        self.assertFalse((self.f.durum_dizini() / "plan.json").exists(),
                         "bozuk damgada plan YAZILMAMALI")
        self.assertEqual(self.f.oku("AGENTS.md"), m + "\n" + m, "bozuk damgalı dosyaya DOKUNULMAMALI")

    def test_5_KONTROL_damga_guncel_ama_dosya_yazildiysa_da_komut_verilir(self):
        """Sebep listesi yalnız damgaya bağlı değil: şablon dosyası yazılınca da GEREKLİ bölümü çıkar."""
        self.f.ilerlet()
        self.assertEqual(self.planla().returncode, 0)
        self.assertIsNone(self.f.plan()["damga"])
        self.assertEqual(self.f.calistir("uygula", "--otomatik").returncode, 0)
        self.f.calistir("kapanis")
        rapor = (self.f.durum_dizini() / "RAPOR.md").read_text(encoding="utf-8")
        self.assertIn("şablon dosyası yazıldı", rapor)
        self.assertNotIn("damgası yenilendi", rapor)

    # --- bug gate 2026-09-22 düzeltme turu -------------------------------------------------------
    def test_6_BAYAT_ONAY_yeni_damga_kalemini_ACMAZ(self):
        """MEDIUM probe'u birebir: onay + plan(1) → kanonik yükselir → YENİ ONAY OLMADAN plan(0,
        DAMGA) → uygula → kapanış. Eski kodda damga ONAYSIZ yazılıyordu (AXET-SAP-9.9.9)."""
        self.assertEqual(self.planla().returncode, 1)          # onay verildi, iş yok
        once = self.f.oku("AGENTS.md")
        self._kanonigi_yukselt()
        r = self.f.calistir("plan")
        self.assertEqual(r.returncode, 0, self.cikti(r))       # plan salt-okur, onaysız çalışır
        r_u = self.f.calistir("uygula", "--otomatik")
        r_k = self.f.calistir("kapanis")
        self.assertNotIn(self.YENI_ID, self.f.oku("AGENTS.md"), "bayat onayla damga YAZILDI")
        self.assertEqual(self.f.oku("AGENTS.md"), once)
        self.assertEqual(r_u.returncode, 2, self.cikti(r_u))
        self.assertEqual(r_k.returncode, 2, self.cikti(r_k))
        self.assertIn("kanoniği değişti", self.cikti(r_k))

    def test_6b_KONTROL_kanonik_degismeden_onay_GECERLI_kalir(self):
        self.f.ilerlet()
        self.assertEqual(self.planla().returncode, 0)
        r = self.f.calistir("uygula", "--otomatik")
        self.assertEqual(r.returncode, 0, self.cikti(r))

    def test_6c_eski_bicim_onay_alansiz_GECERSIZ(self):
        """Fail-closed: `damga_hedefi` alanı olmayan onay.json geriye uyumluluk için geçerli SAYILMAZ."""
        self.f.ilerlet()
        self.assertEqual(self.planla().returncode, 0)
        yol = self.f.durum_dizini() / "onay.json"
        kayit = json.loads(yol.read_text(encoding="utf-8"))
        kayit.pop("damga_hedefi")
        yol.write_text(json.dumps(kayit), encoding="utf-8")
        r = self.f.calistir("uygula", "--otomatik")
        self.assertEqual(r.returncode, 2, self.cikti(r))

    def test_7_ikinci_kapanis_GEREKLI_satirini_KORUR(self):
        """LOW: tam akış → plan(1, plan.json bayat kalır) → kapanış tekrar. Manifest hâlâ onaysız ⇒
        GEREKLİ bölümü ikinci raporda da durmalı (kapanış idempotent)."""
        self._kanonigi_yukselt()
        self.assertEqual(self.planla().returncode, 0)
        self.assertEqual(self.f.calistir("uygula", "--otomatik").returncode, 0)
        self.assertEqual(self.f.calistir("kapanis").returncode, 0)
        self.assertEqual(self.f.calistir("plan").returncode, 1)
        r = self.f.calistir("kapanis")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        rapor = (self.f.durum_dizini() / "RAPOR.md").read_text(encoding="utf-8")
        self.assertIn("Kullanıcının kendi terminalinde — GEREKLİ", rapor)
        self.assertIn("AGENTS.md kesin yasak damgası yenilendi", rapor)
        # v0.5.2 (gate LOW-1): plan.json bayat kalabildiği için metin manifest zaten onaylanmışsa da doğru olmalı
        self.assertIn("zaten onayladıysan", rapor)

    # --- v0.5.2: v0.5.1 düzeltme turu gate'inin LOW notları -------------------------------------
    def test_8_onkontrol_bayat_onayi_GECERSIZ_gosterir(self):
        """`onkontrol` "proje onayı: var" satırını yalnız proje yoluna bakarak basıyordu; bayat onay da
        "var" görünüyordu (asıl engel onay_dogrula'da). Kontrol grubu: geçerli onay → "var (geçerli)"."""
        self.assertEqual(self.planla().returncode, 1)
        r = self.f.calistir("onkontrol")
        self.assertIn("proje onayı: var (geçerli)", self.cikti(r))
        self._kanonigi_yukselt()
        r = self.f.calistir("onkontrol")
        self.assertIn("proje onayı: var ama GEÇERSİZ", self.cikti(r))
        self.assertIn("kanoniği değişti", self.cikti(r))

    def test_9_DUR_gerekcesi_eski_bicim_ve_damga_durumu_ayrilir(self):
        """Gate LOW-3: onayı düşüren sebep her zaman "kanonik değişti" değildir."""
        self.f.ilerlet()
        self.assertEqual(self.planla().returncode, 0)
        yol = self.f.durum_dizini() / "onay.json"
        kayit = json.loads(yol.read_text(encoding="utf-8"))
        eski = dict(kayit)
        kayit.pop("damga_hedefi")
        yol.write_text(json.dumps(kayit), encoding="utf-8")
        r = self.f.calistir("uygula", "--otomatik")
        self.assertIn("eski biçimde", self.cikti(r))
        self.assertNotIn("kanoniği değişti", self.cikti(r))
        eski["damga_hedefi"] = "damgasiz"          # onay damgasız dönemde verilmiş, proje artık damgalı
        yol.write_text(json.dumps(eski), encoding="utf-8")
        r = self.f.calistir("uygula", "--otomatik")
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn("damga durumu değişti", self.cikti(r))

    def test_10_onay_mesaji_kanonigi_de_anar(self):
        r = self.f.onayla()
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("kesin yasak kanoniğini", self.cikti(r))

    def test_11_damga_yazilamadiysa_rapor_YENILENDI_demez(self):
        """Gate LOW-2: plan damga kalemi taşıyor ama kapanıştan önce damga bozuldu → yazım yok; rapor
        "damgası yenilendi" DEMEMELİ (KAPANMADI + eksik zaten söylenir)."""
        self._kanonigi_yukselt()
        self.assertEqual(self.planla().returncode, 0)
        self.assertEqual(self.f.calistir("uygula", "--otomatik").returncode, 0)
        m = self.f.oku("AGENTS.md")
        self.f.yerel_degistir("AGENTS.md", m + "\n" + m)
        self.f.calistir("kapanis")
        rapor = (self.f.durum_dizini() / "RAPOR.md").read_text(encoding="utf-8")
        self.assertIn("damga: DUR", rapor)
        self.assertNotIn("damgası yenilendi", rapor)


# =====================================================================================================
# Z79. KURULUMU-TAMAMLA.cmd kısayolu mevcut SAP projesine de ulaşır
# =====================================================================================================
class Z79KisayolTest(ProjeTemel):
    """Z79 (2026-09-23): `yeni_proje.py` kısayolu yalnız YENİ projeye yazıyordu; `%guncelle-proje`
    yalnız `templates/project(-sap)` ağacını günceller ⇒ Z70'ten önce kurulmuş SAP projesine kısayol
    hiç ulaşmıyordu. Kısayol planın AYRI kalemidir (damga/Z55 deseni): plan gösterir, onay kapsar,
    `uygula --otomatik` yazar (`yeni_proje.kisayol_yaz`), `kapanis` diskten doğrular.

    KAPSAM — bakılmayan: kısayolun cmd.exe'de çift tıklanınca çalışması (test_proje_tamamla ölçer) ·
    ASCII dışı klon yolu (OEM kodlaması yeni_proje testlerinde) · Linux/macOS.
    """
    sap = True
    ISARETSIZ = b"@echo off\r\nrem elle yazilmis gecici surum\r\ncall C:\\eski\\proje-tamamla.cmd\r\n"

    def _akis(self) -> subprocess.CompletedProcess:
        r = self.planla()
        self.assertEqual(r.returncode, 0, self.cikti(r))
        u = self.f.calistir("uygula", "--otomatik")
        self.assertEqual(u.returncode, 0, self.cikti(u))
        return u

    def test_1_eksik_kisayol_planda_gorunur_plan_YAZMAZ(self):
        (self.f.proje / yeni_proje.KISAYOL).unlink()
        r = self.planla()      # şablon İLERLEMEDİ: kalem yalnız kısayol
        self.assertEqual(r.returncode, 0, "eksik kısayol tek başına plan kalemidir (Z55 dersi)\n"
                         + self.cikti(r))
        self.assertIn("kısayol yazılacak", self.cikti(r))
        self.assertEqual(self.f.plan()["kisayol"]["durum"], "yok")
        self.assertIsNone(self.f.kisayol_oku(), "plan salt-okurdur, kısayolu YAZMAMALI")

    def test_2_eksik_kisayol_uygula_yazar_icerik_kisayol_metni_kapanis_PASS(self):
        (self.f.proje / yeni_proje.KISAYOL).unlink()
        u = self._akis()
        self.assertEqual(self.f.kisayol_oku(), self.f.kisayol_bayt())
        # sahte şablonun .gitignore'unda kısayol satırı yok ⇒ git'e açık: uyarı (v0.5.6 gate, yeni_proje ile aynı)
        self.assertIn("git'e kapalı değil", self.cikti(u))
        k = self.f.calistir("kapanis")
        self.assertEqual(k.returncode, 0, self.cikti(k))
        rapor = (self.f.durum_dizini() / "RAPOR.md").read_text(encoding="utf-8")
        self.assertIn(f"[PASS] {yeni_proje.KISAYOL}", rapor)
        # kurulum sadeleştirme (2026-09-24): onay yolu önce çift tık (kısayol var) — komut BT/terminal yedeği olarak kalır
        onay = rapor[rapor.index("## Kullanıcının kendi terminalinde"):]
        self.assertIn(f"proje klasöründeki {yeni_proje.KISAYOL}'ye çift tıkla", onay)
        self.assertIn(str(self.f.proje / yeni_proje.KISAYOL), onay)
        self.assertLess(onay.index("çift tıkla"), onay.index('behavior_manifest.py" generate'))

    def test_2b_kisayol_git_e_kapaliysa_uyari_YOK(self):
        (self.f.proje / yeni_proje.KISAYOL).unlink()
        (self.f.proje / ".git" / "info").mkdir(parents=True, exist_ok=True)
        (self.f.proje / ".git" / "info" / "exclude").write_text(yeni_proje.KISAYOL + "\n", encoding="utf-8")
        u = self._akis()
        self.assertEqual(self.f.kisayol_oku(), self.f.kisayol_bayt())
        self.assertNotIn("git'e kapalı değil", self.cikti(u))

    def test_3_onaysiz_uygula_kisayolu_YAZMAZ(self):
        (self.f.proje / yeni_proje.KISAYOL).unlink()
        self.assertEqual(self.planla(onayla=False).returncode, 0)
        u = self.f.calistir("uygula", "--otomatik")
        self.assertNotEqual(u.returncode, 0, self.cikti(u))
        self.assertIsNone(self.f.kisayol_oku())

    def test_4_resmi_ama_farkli_kisayol_guncellenir_yedeklenir_geri_alinir(self):
        eski = self.f.kisayol_bayt(self.tmp / "eski-klon")        # klon yolu değişmiş resmi kısayol
        self.f.kisayol_yaz(eski)
        r = self.planla()
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("kısayol güncellenecek", self.cikti(r))
        self.assertEqual(self.f.kisayol_oku(), eski, "plan yazmamalı")
        self._akis()
        self.assertEqual(self.f.kisayol_oku(), self.f.kisayol_bayt())
        g = self.f.calistir("geri-al", yeni_proje.KISAYOL)
        self.assertEqual(g.returncode, 0, self.cikti(g))
        self.assertEqual(self.f.kisayol_oku(), eski, "geri-al eski kısayolu bayt bayt geri getirmeli")

    def test_5_resmi_ve_guncel_kisayola_DOKUNULMAZ(self):
        once = self.f.kisayol_oku()
        self.assertIsNotNone(once)
        r = self.planla()
        self.assertEqual(r.returncode, 1, "kısayol güncel + şablon güncel ⇒ plan yok\n" + self.cikti(r))
        self.f.ilerlet()
        u = self._akis()
        self.assertIsNone(self.f.plan()["kisayol"])
        self.assertNotIn(yeni_proje.KISAYOL, self.cikti(u))
        self.assertEqual(self.f.kisayol_oku(), once)
        self.assertFalse((self.f.durum_dizini() / "yedek" / yeni_proje.KISAYOL).exists())

    def test_6_isaretsiz_kisayol_EZILMEZ_bilgi_satiri_basilir(self):
        self.f.kisayol_yaz(self.ISARETSIZ)
        r = self.planla()
        self.assertEqual(r.returncode, 1, "işaretsiz kısayol tek başına iş kalemi DEĞİL\n" + self.cikti(r))
        self.assertIn("resmi olmayan kısayol", self.cikti(r))
        self.assertIn("dosyayı sil", self.cikti(r))
        self.f.ilerlet()
        r = self.planla()
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("resmi olmayan kısayol", self.cikti(r))
        self.assertEqual(self.f.plan()["kisayol"]["durum"], "resmi-degil")
        u = self.f.calistir("uygula", "--otomatik")
        self.assertEqual(u.returncode, 0, self.cikti(u))
        self.assertEqual(self.f.kisayol_oku(), self.ISARETSIZ, "işaretsiz dosya EZİLMEMELİ")
        k = self.f.calistir("kapanis")
        self.assertEqual(k.returncode, 0, self.cikti(k))
        rapor = (self.f.durum_dizini() / "RAPOR.md").read_text(encoding="utf-8")
        self.assertIn("resmi olmayan kısayol", rapor)


class Z79SapDisiTest(ProjeTemel):
    """SAP dışı projede kısayol kalemi YOKTUR (kısayolu `yeni_proje.py` yalnız SAP projesine yazar)."""
    sap = False

    def test_SAP_disi_projede_kisayol_yazilmaz_planda_gorunmez(self):
        self.f.ilerlet()
        r = self.planla()
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertNotIn(yeni_proje.KISAYOL, self.cikti(r))
        self.assertIsNone(self.f.plan().get("kisayol"))
        u = self.f.calistir("uygula", "--otomatik")
        self.assertEqual(u.returncode, 0, self.cikti(u))
        self.assertIsNone(self.f.kisayol_oku())
        # kontrol grubu (çift tık satırı): kısayolu olmayan projede rapor olmayan dosyayı göstermez, komutu verir
        k = self.f.calistir("kapanis")
        self.assertEqual(k.returncode, 0, self.cikti(k))
        rapor = (self.f.durum_dizini() / "RAPOR.md").read_text(encoding="utf-8")
        self.assertNotIn("çift tıkla", rapor)
        self.assertIn('behavior_manifest.py" generate --project-dir "', rapor)


if __name__ == "__main__":
    unittest.main()
