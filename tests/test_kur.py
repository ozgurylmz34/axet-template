# -*- coding: utf-8 -*-
"""kur.cmd / kur.ps1 — son kullanıcı kurulum aracı. Yerel bare repo kaynak olarak kullanılır (ağ yok), config geçici
XDG_CONFIG_HOME'a yazılır, winget hiçbir testte gerçek hâliyle çağrılmaz (-WingetKapali ya da PATH'in başında sahte
winget). Windows'a özgüdür; başka platformda atlanır.

KAPSAM — bakılmayanlar: gerçek winget kurulumu ve sonrasında PATH yenileme · GitHub'dan klon (ağ) · etkileşimli
terminalde soru-yanıt (yalnız kapalı stdin ve -Evet ölçülür) · aXet'in yeni config'i fiilen yüklediği (doctor --live) ·
beklenmeyen istisna dalı (dış try/catch) · py launcher'ın ASCII olmayan yolları listelemesi."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

from _helpers import AXET_HOME, GeciciTest, _sil, gecici_dizin

KUR_CMD = AXET_HOME / "kur.cmd"
KUR_PS1 = AXET_HOME / "kur.ps1"
WINDOWS = os.name == "nt"
SYS32 = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"
POWERSHELL = SYS32 / "WindowsPowerShell" / "v1.0" / "powershell.exe"
COMSPEC = os.environ.get("COMSPEC", str(SYS32 / "cmd.exe"))


def _goruntu(kok: Path) -> dict | None:
    """Klasördeki dosyaların (göreli yol -> boyut, mtime, sha256) görüntüsü; klasör yoksa None. Yalnız testin kendi
    geçici klasörleri için kullanılır."""
    if not kok.exists():
        return None
    sonuc = {}
    for p in sorted(kok.rglob("*")):
        if p.is_file():
            st = p.stat()
            sonuc[str(p.relative_to(kok))] = (st.st_size, st.st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest())
    return sonuc


def _gercek_damga() -> dict:
    """Gerçek kullanıcı config'i ve aXet yerel klasöründe kurulumun dokunabileceği dosyaların boyut+mtime damgası.

    Karar: içerik okunmaz, klasör taranmaz. install.py yalnız global config'i ve yanına `.bak-*` yedeğini yazar →
    config dosyası + yedek adları izlenir. %LOCALAPPDATA%\\axet-code'a kur.ps1 hiç yazmaz; oradan yalnız aXet'in
    ayar/kimlik dosyaları (axet-code.json, skills_manifest.json, auth.enc) boyut+mtime ile izlenir. Klasörün tamamını
    (93 MB ikili dahil) hash'lemek yavaştı, açık bir aXet oturumunun değiştirdiği dosyalarda sahte hata verebilirdi ve
    auth.enc'in içeriği okunmamalı."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    cfg_dizin = (Path(xdg) if xdg else Path.home() / ".config") / "axet-code"
    izlenen = [cfg_dizin / "axet-code.json"]
    if os.environ.get("LOCALAPPDATA"):
        lad = Path(os.environ["LOCALAPPDATA"]) / "axet-code"
        izlenen += [lad / "axet-code.json", lad / "skills_manifest.json", lad / "auth.enc"]
    damga: dict = {}
    for f in izlenen:
        damga[str(f)] = (f.stat().st_size, f.stat().st_mtime_ns) if f.is_file() else None
    damga["yedekler"] = sorted(p.name for p in cfg_dizin.glob("axet-code.json.bak-*")) if cfg_dizin.is_dir() else None
    # Z98 bekçisi: kur.ps1 artık kullanıcı PATH'ine yazabilir. Testler yalnız AXET_KUR_PATH_KAYDI sahte hedefine yazar;
    # GERÇEK HKCU\Environment Path ham değeri (genişletilmemiş) ve türü koşum öncesi/sonrası aynı kalmalı.
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            damga["HKCU-Environment-Path"] = winreg.QueryValueEx(k, "Path")
    except (ImportError, OSError):
        damga["HKCU-Environment-Path"] = None
    return damga


@unittest.skipUnless(WINDOWS and KUR_CMD.exists() and POWERSHELL.exists(), "yalnız Windows (kur.cmd + PowerShell 5.1)")
class KurTest(GeciciTest):
    @classmethod
    def setUpClass(cls) -> None:
        cls._once = _gercek_damga()
        cls.sinif_tmp = gecici_dizin("axet-kur-")   # repo DIŞI (Z96)
        cls.kaynak_sablon = cls.sinif_tmp / "kaynak.git"
        r = subprocess.run(["git", "clone", "-q", "--bare", str(AXET_HOME), str(cls.kaynak_sablon)],
                           capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=300)
        if r.returncode != 0:
            raise RuntimeError(f"bare klon oluşturulamadı: {r.stderr}")

    @classmethod
    def tearDownClass(cls) -> None:
        _sil(cls.sinif_tmp)
        sonra = _gercek_damga()
        if sonra != cls._once:
            raise AssertionError(f"GERÇEK aXet config/yerel dosyası testte değişti:\nönce={cls._once}\nsonra={sonra}")

    def setUp(self) -> None:
        super().setUp()
        self.kaynak = self.tmp / "kaynak.git"
        shutil.copytree(self.kaynak_sablon, self.kaynak)
        self.hedef = self.tmp / "hedef"
        self.cfg = self.xdg / "axet-code" / "axet-code.json"
        # Z98: kur.ps1 hiçbir testte GERÇEK kullanıcı PATH'ine (HKCU\Environment) yazmasın. Varsayılan sahte hedefte
        # makine PATH'i testi koşan yorumlayıcının klasörüdür: `python` çözülür, kur.ps1 hiçbir şey eklemez.
        self.path_kaydi(str(self.kur_python().parent), "")

    # --- yardımcılar ------------------------------------------------------------------------------------------
    def kur(self, *args: str, env: dict | None = None, winget_kapali: bool = True,
            varsayilan: bool = True, hedef: Path | None = None) -> subprocess.CompletedProcess:
        """kur.cmd'yi çağırır. varsayilan=True: -Kaynak <geçici bare> -Hedef <hedef> önden eklenir.

        `/c` ile betik adı arasındaki `call` ZORUNLU (ölçüldü 2026-09-16, izole deney): `cmd /c` komut satırında
        ikiden fazla tırnak varken ilk ve son tırnağı atar; klon yolu ("...\\bos luklu klasor\\kur.cmd") VE bir argüman
        ("-Hedef C:\\...\\hedef bos luk") birlikte boşluk içerdiğinde batch dosyası HİÇ başlamaz
        (rc=1, "'C:\\...\\bos' is not recognized"). `call` ile aynı çağrı rc=0 ve argümanlar bozulmadan geçiyor."""
        arglar = list(args)
        if varsayilan:
            arglar = ["-Kaynak", str(self.kaynak), "-Hedef", str(hedef or self.hedef)] + arglar
        if winget_kapali:
            arglar.append("-WingetKapali")
        return subprocess.run([COMSPEC, "/c", "call", str(KUR_CMD), *arglar], env=env or self.env, cwd=str(self.tmp),
                              capture_output=True, text=True, encoding="utf-8", errors="replace",
                              stdin=subprocess.DEVNULL, timeout=600)

    _kur_python: Path | None = None

    def kur_python(self) -> Path:
        """kur.ps1'in bu test ortamında seçeceği yorumlayıcı: PATH'teki ilk `python`un sys.executable'ı."""
        if KurTest._kur_python is None:
            r = subprocess.run([COMSPEC, "/c", "python", "-c", "import sys;print(sys.executable)"], env=self.env,
                               capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60)
            if r.returncode != 0 or not r.stdout.strip():
                raise RuntimeError(f"test ortamında python çözülemedi: {r.stdout}{r.stderr}")
            KurTest._kur_python = Path(r.stdout.strip().splitlines()[-1])
        return KurTest._kur_python

    def git_dizini(self, env: dict | None = None) -> str:
        """Test ortamının PATH'inde ilk bulunan git'in klasörü (kur.ps1'in `git` çözümüyle aynı sıra)."""
        yol = shutil.which("git", path=self.path_oku(env or self.env))
        if not yol:
            raise RuntimeError("test ortamında git çözülemedi")
        return str(Path(yol).parent)

    def path_kaydi(self, makine: str, kullanici: str, tur: str = "ExpandString", git: bool = True,
                   python_kayit: list | None = None) -> Path:
        """Z98 enjeksiyon noktası: AXET_KUR_PATH_KAYDI sahte kayıt hedefi (JSON). kur.ps1 bu değişken varken kayıt
        defterini ne okur ne yazar, ayar yayını da yapmaz; makine PATH'ini de buradan okur. Kayıt defterindeki PEP 514
        Python kayıtları da yerine `python_kayit` dizisinden okunur (verilmezse boş: gerçek makinenin kaydı görünmez).
        git=True: gerçek git'in klasörü makine PATH'inin SONUNA eklenir — yeni terminalde `git` çözülür, kurulumun Git
        PATH kolu (Z98 Git) hiçbir şey yazmaz; eklenen değer `self.makine_kaydi`nda."""
        if git:
            makine = os.pathsep.join([m for m in (makine, self.git_dizini()) if m])
        self.makine_kaydi = makine
        veri = {"makine": makine, "kullanici": kullanici, "tur": tur}
        if python_kayit is not None:
            veri["python_kayit"] = python_kayit
        f = self.tmp / "_path_kaydi.json"
        f.write_text(json.dumps(veri, ensure_ascii=False), encoding="utf-8")
        self.env["AXET_KUR_PATH_KAYDI"] = str(f)
        return f

    def bos_program_files(self, env: dict) -> dict:
        """Bilinen kurulum klasörleri (ProgramFiles*, LOCALAPPDATA) boş geçici klasörleri gösterir: kur.ps1 artık Git'i
        ve Python'u bu klasörlerde VARSAYILAN olarak arar; dar ortam testleri makinedeki gerçek kurulumu görmesin."""
        pf = self.tmp / "_programfiles"
        pf.mkdir(exist_ok=True)
        env = dict(env)
        for k in list(env):
            if k.upper() in ("PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMW6432"):
                del env[k]
        env.update({"ProgramFiles": str(pf), "ProgramFiles(x86)": str(pf), "ProgramW6432": str(pf)})
        return env

    @staticmethod
    def path_kaydi_oku(f: Path) -> dict:
        return json.loads(f.read_text(encoding="utf-8-sig"))

    def eski_python_dizini(self, surum: str) -> Path:
        """Sürümünü <surum> diye bildiren çalışan sahte python.cmd'nin klasörü (sahte_python_ortami ile aynı biçim)."""
        d = self.tmp / f"_eskipy{surum.replace('.', '_')}"
        d.mkdir()
        (d / "python.cmd").write_text(f"@echo off\r\necho {surum}^|%~f0\r\nexit /b 0\r\n", encoding="ascii", newline="")
        return d

    def cfg_oku(self) -> dict:
        return json.loads(self.cfg.read_text(encoding="utf-8"))

    def uzakta_commit(self, dosya: str = "YENI.txt", kaynak: Path | None = None) -> None:
        """Kaynak bare repoya yeni bir commit iter (klonun geride kalmasını sağlar)."""
        kaynak = kaynak or self.kaynak
        is_klonu = self.tmp / f"is-{kaynak.name}"
        if not is_klonu.exists():
            self.git(self.tmp, "clone", "-q", str(kaynak), str(is_klonu))
        self.yaz(is_klonu / dosya, "uzakta eklendi\n")
        self.git(is_klonu, "add", dosya)
        self.git(is_klonu, "commit", "-q", "-m", f"test: {dosya}")
        self.git(is_klonu, "push", "-q", "origin", "HEAD")

    def kurulu(self) -> None:
        r = self.kur("-Evet")
        self.assertEqual(r.returncode, 0, self.cikti(r))

    def sahte_winget(self) -> tuple[Path, Path]:
        """Çağrıyı dosyaya kaydedip hata dönen sahte winget.cmd; (klasör, kayıt dosyası)."""
        bin_ = self.tmp / "_bin"
        bin_.mkdir(exist_ok=True)
        kayit = self.tmp / "winget-cagri.txt"
        (bin_ / "winget.cmd").write_text(f'@echo off\r\necho %* >> "{kayit}"\r\nexit /b 1\r\n', encoding="ascii")
        return bin_, kayit

    @staticmethod
    def path_degistir(env: dict, yeni: str) -> dict:
        env = dict(env)
        for k in list(env):
            if k.upper() == "PATH":
                del env[k]
        env["PATH"] = yeni
        return env

    @staticmethod
    def path_oku(env: dict) -> str:
        return next(v for k, v in env.items() if k.upper() == "PATH")

    def dar_ortam(self, axet: bool) -> tuple[dict, Path]:
        """PATH'te yalnız: 0 baytlık sahte python.exe/python3.exe + çağrıyı kaydeden sahte winget + System32 + PowerShell.
        LOCALAPPDATA geçici klasör (gerçek aXet görünmesin; axet=True ise sahte axet-code.exe konur)."""
        bin_, kayit = self.sahte_winget()
        (bin_ / "python.exe").write_bytes(b"")
        (bin_ / "python3.exe").write_bytes(b"")
        lad = self.tmp / "_localappdata"
        lad.mkdir()
        if axet:
            (lad / "axet-code" / "bin").mkdir(parents=True)
            (lad / "axet-code" / "bin" / "axet-code.exe").write_bytes(b"")
        self.path_kaydi("", "", git=False)  # kayıttaki PATH de boş: PATH tazeleme gerçek python/git getirmesin
        env = self.path_degistir(self.env, os.pathsep.join([str(bin_), str(SYS32), str(POWERSHELL.parent)]))
        env["LOCALAPPDATA"] = str(lad)
        return self.bos_program_files(env), kayit

    def sahte_python_ortami(self, surum: str) -> tuple[dict, Path]:
        """Sürümünü <surum> diye bildiren, GERÇEKTEN ÇALIŞAN sahte bir python'un tek başına PATH'te olduğu ortam.

        dar_ortam()'ın 0 baytlık sahtesinden farkı: bu aday `Python-Dene`de rc=0 döner, sürümünü bildirir ve
        bildirdiği yol diskte gerçekten vardır → aday asgari sürüm karşılaştırmasına (`$surum -lt $script:PyAsgari`,
        kur.ps1) ULAŞIR ve karar YALNIZ orada verilir. Gerçek yorumlayıcı, py launcher ve git PATH dışındadır;
        `-WingetKapali` ile `Python-Bul -BilinenYerler` koluna hiç girilmez (ProgramFiles'taki gerçek Python
        sonucu bulandırmasın). LOCALAPPDATA sahte: gerçek aXet görünmez, sahte axet-code.exe konur."""
        etiket = surum.replace(".", "_")
        bin_ = self.tmp / f"_py{etiket}"
        bin_.mkdir()
        sahte = bin_ / "python.cmd"
        # `-c <kod>` argümanı okunmaz; çıktı Python-Dene'nin beklediği "MAJ.MIN|<yol>" biçimindedir ve bildirilen yol
        # betiğin kendisidir (Test-Path -PathType Leaf geçsin diye diskte var olan bir dosya olmalı).
        sahte.write_text(f"@echo off\r\necho {surum}^|%~f0\r\nexit /b 0\r\n", encoding="ascii", newline="")
        lad = self.tmp / f"_lad{etiket}"
        (lad / "axet-code" / "bin").mkdir(parents=True)
        (lad / "axet-code" / "bin" / "axet-code.exe").write_bytes(b"")
        self.path_kaydi("", "", git=False)
        env = self.path_degistir(self.env, os.pathsep.join([str(bin_), str(SYS32), str(POWERSHELL.parent)]))
        env["LOCALAPPDATA"] = str(lad)
        return self.bos_program_files(env), sahte

    def sahte_py_launcher_ortami(self) -> tuple[dict, Path, Path]:
        """`py` launcher kolunun TEK yol olarak kaldığı ortam: PATH'te python/python3 YOK, yalnız `-0p` listesi
        veren sahte bir `py` var ve o liste bu testi koşan GERÇEK yorumlayıcıyı gösterir.

        Sahte py YALNIZ `-0p`yi tanır, başka her argümanda rc=1 döner: böylece `py -3` yedek kolu ÇALIŞMAZ ve
        "aday listeden seçildi mi" sorusu tek başına ölçülebilir. Gerçek py.exe (%LOCALAPPDATA%\\Programs\\Python\\Launcher) PATH dışıdır;
        git de yoktur (2. adımda durulur, sahte liste hiç kullanılmadan kurulum ilerlemez)."""
        bin_ = self.tmp / "_pylauncher"
        bin_.mkdir()
        gercek = Path(sys.executable).resolve()
        surum = f"{sys.version_info.major}.{sys.version_info.minor}"
        sahte_py = bin_ / "py.cmd"
        satirlar = ["@echo off", 'if not "%~1"=="-0p" exit /b 1', f"echo  -V:{surum} *        {gercek}", "exit /b 0"]
        sahte_py.write_text("\r\n".join(satirlar) + "\r\n", encoding="ascii", newline="")
        lad = self.tmp / "_lad_pylauncher"
        (lad / "axet-code" / "bin").mkdir(parents=True)
        (lad / "axet-code" / "bin" / "axet-code.exe").write_bytes(b"")
        self.path_kaydi("", "", git=False)
        env = self.path_degistir(self.env, os.pathsep.join([str(bin_), str(SYS32), str(POWERSHELL.parent)]))
        env["LOCALAPPDATA"] = str(lad)
        return self.bos_program_files(env), sahte_py, gercek

    def yabanci_repo(self, ad: str) -> tuple[Path, Path]:
        """scripts/install.py + scripts/doctor.py + skills-sap/ + core/00-temel.md taşıyan ama `CORE-ID: AXET-CORE-`
        imzası OLMAYAN yabancı bare repo; (bare, işaret dosyası). Yabancı betik çalışırsa işaret dosyasını yazar."""
        isaret = self.tmp / f"YABANCI_{ad}_CALISTI.txt"
        bare = self.tmp / f"{ad}.git"
        is_ = self.tmp / f"{ad}-is"
        self.git(self.tmp, "init", "-q", "--bare", "-b", "main", str(bare))
        self.git(self.tmp, "clone", "-q", str(bare), str(is_))
        betik = f"import sys\nopen(r'{isaret}', 'a', encoding='utf-8').write(' '.join(sys.argv) + '\\n')\n"
        self.yaz(is_ / "scripts" / "install.py", betik)
        self.yaz(is_ / "scripts" / "doctor.py", betik)
        self.yaz(is_ / "skills-sap" / "README.md", "yabancı\n")
        self.yaz(is_ / "core" / "00-temel.md", "# başka bir proje\nCORE-ID: BASKA-0.1\n")
        self.git(is_, "add", "-A")
        self.git(is_, "commit", "-q", "-m", "yabanci ilk")
        self.git(is_, "push", "-q", "origin", "main")
        return bare, isaret

    # --- dosya biçimi -----------------------------------------------------------------------------------------
    def test_ps1_bomlu_utf8_ve_cmd_ascii(self):
        # Ölçüldü: PS 5.1 BOM'suz UTF-8 .ps1'i ANSI okur, Türkçe dizgeler bozulur.
        self.assertEqual(KUR_PS1.read_bytes()[:3], b"\xef\xbb\xbf")
        KUR_CMD.read_bytes().decode("ascii")  # cmd.exe kod sayfasından bağımsız kalsın
        metin = KUR_PS1.read_text(encoding="utf-8-sig").lower()
        self.assertNotIn("sap-write", metin)  # Y1: yazma izni ne çalıştırılır ne önerilir
        self.assertNotIn("invoke-expression", metin)
        self.assertIn("install.py", metin)
        self.assertIn("--sap", metin)

    # --- kurulum / güncelleme ---------------------------------------------------------------------------------
    def test_ilk_kurulum_klonlar_sap_config_yazar_doctor_calisir(self):
        r = self.kur("-Evet")
        c = self.cikti(r)
        self.assertEqual(r.returncode, 0, c)
        self.assertTrue((self.hedef / ".git").is_dir())
        self.assertTrue((self.hedef / "scripts" / "install.py").is_file())
        ctx = self.cfg_oku()["options"]["context_paths"]
        skills = self.cfg_oku()["options"]["skills_paths"]
        self.assertIn((self.hedef / "core" / "00-temel.md").as_posix(), ctx)
        self.assertIn((self.hedef / "core" / "sap").as_posix(), ctx)
        self.assertIn((self.hedef / "skills-sap").as_posix(), skills)
        self.assertIn("SONUÇ: 0 FAIL", c)  # doctor.py koştu
        self.assertIn("Kurulum TAMAM — aXet'i aç. (yeni klon)", c)
        self.assertIn("YENİ bir aXet oturumu aç", c)  # Türkçe çıktı bozulmadan geldi
        self.assertIn("AXET-CORE", c)
        self.assertIn("%yeni-proje", c)
        self.assertIn("%guncelle", c)  # tek güncelleme yolu aXet içinden
        self.assertIn("KURULUMU-TAMAMLA", c)
        self.assertNotIn("kur.cmd -Kaldir", c)  # son mesaj kullanıcıya komut vermez
        self.assertNotIn("beklenmeyen hata", c)
        # Git kimliği adımı işe başlamadan koştu; pencere etkileşimsiz (stdin NUL) → soru SORULMADI, hiçbir şey yazılmadı
        self.assertLess(c.index("== 2/5 Git kimliği"), c.index("== 3/5 Template klonu"), c)
        self.assertIn("Git kimliği SORULMADI", c)
        self.assertEqual(Path(self.env["GIT_CONFIG_GLOBAL"]).read_text(encoding="utf-8"), "")
        # Z98 Git kolu kablolu: kayıttaki makine PATH'i git'i içeriyor → yazılmaz, ölçülür
        self.assertIn("OK 'git' komutu yeni terminallerde çalışıyor", c)

    def test_tekrar_calistirma_degisiklik_yok_sonra_guncelleme(self):
        self.kurulu()
        head = self.git(self.hedef, "rev-parse", "HEAD").stdout.strip()
        r = self.kur("-Evet")
        c = self.cikti(r)
        self.assertEqual(r.returncode, 0, c)
        self.assertIn("Değişiklik yok; klon zaten güncel.", c)
        self.assertIn("Config zaten bu klonu gösteriyor", c)
        self.assertNotIn("önceki kurulum şu klonu gösteriyordu", c)
        self.assertNotIn("klonun kaynağı", c)  # origin == kaynak -> uyarı yok
        self.assertEqual(self.git(self.hedef, "rev-parse", "HEAD").stdout.strip(), head)
        self.assertEqual(self.git(self.hedef, "status", "--porcelain").stdout.strip(), "")

        self.uzakta_commit()
        r = self.kur("-Evet")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("Güncellendi (1 yeni commit)", self.cikti(r))
        self.assertTrue((self.hedef / "YENI.txt").is_file())

    def test_origin_harf_ve_git_eki_farki_uyari_vermez(self):
        self.kurulu()
        ayni = str(self.kaynak).upper()
        self.assertTrue(ayni.endswith(".GIT"))
        ayni = ayni[:-4]  # aynı kaynak: harf farkı + .git eki yok
        r = self.kur("-Kaynak", ayni, "-Hedef", str(self.hedef), "-Evet", varsayilan=False)
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertNotIn("klonun kaynağı", self.cikti(r))
        # kontrol grubu: gerçekten farklı bir kaynak uyarı verir
        r = self.kur("-Kaynak", str(self.tmp / "baska.git"), "-Hedef", str(self.hedef), "-Evet", varsayilan=False)
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("klonun kaynağı", self.cikti(r))

    def test_yerel_degisiklik_varsa_guncellemez_dosyayi_korur(self):
        self.kurulu()
        self.uzakta_commit()
        head = self.git(self.hedef, "rev-parse", "HEAD").stdout.strip()
        readme = self.hedef / "README.md"
        readme.write_text(readme.read_text(encoding="utf-8") + "\nyerel not\n", encoding="utf-8")
        icerik = readme.read_bytes()
        r = self.kur("-Evet")
        self.assertNotEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("yerel değişiklik var", self.cikti(r))
        # Bayraksız kur.cmd yalnız "DURDU" demez, İKİ yolu da söyler (TASARIM §1). Mesaj BUGÜN var olan eylemleri
        # göstermeli: `%guncelle` skill'i bu dalda YOK (P2/P4 ile gelecek) — ölü işaretçi yazılmaz.
        self.assertNotIn("%guncelle", self.cikti(r))
        self.assertIn("stash", self.cikti(r))
        self.assertIn("kur.cmd -Sifirla", self.cikti(r))
        self.assertEqual(readme.read_bytes(), icerik)
        self.assertEqual(self.git(self.hedef, "rev-parse", "HEAD").stdout.strip(), head)
        self.assertFalse((self.hedef / "YENI.txt").exists())
        self.assertEqual(self.git(self.hedef, "stash", "list").stdout.strip(), "")

    def test_ayrismis_klon_guncellenmez(self):
        self.kurulu()
        self.uzakta_commit("UZAK.txt")
        self.yaz(self.hedef / "YEREL.txt", "yerel commit\n")
        self.git(self.hedef, "add", "YEREL.txt")
        self.git(self.hedef, "commit", "-q", "-m", "yerel")
        head = self.git(self.hedef, "rev-parse", "HEAD").stdout.strip()
        r = self.kur("-Evet")
        self.assertEqual(r.returncode, 1, self.cikti(r))
        self.assertIn("ayrışmış", self.cikti(r))
        # Ayrışma mesajı da iki yolu söyler, ikisi de bugün çalışan eylem (ölü `%guncelle` işaretçisi yok).
        self.assertNotIn("%guncelle", self.cikti(r))
        self.assertIn("Yerel commit", self.cikti(r))  # mesajdaki biçim: "Yerel commit'lerini korumak istiyorsan"
        self.assertIn("kur.cmd -Sifirla", self.cikti(r))
        self.assertEqual(self.git(self.hedef, "rev-parse", "HEAD").stdout.strip(), head)

    def test_hedef_var_git_degil_durur(self):
        self.hedef.mkdir()
        benim = self.yaz(self.hedef / "benim.txt", "kullanıcı dosyası\n")
        r = self.kur("-Evet")
        self.assertEqual(r.returncode, 1, self.cikti(r))
        self.assertIn("git klonunun kökü değil", self.cikti(r))
        self.assertEqual(benim.read_text(encoding="utf-8"), "kullanıcı dosyası\n")
        self.assertEqual(sorted(p.name for p in self.hedef.iterdir()), ["benim.txt"])
        self.assertFalse(self.cfg.exists())

    # --- madde 3: yabancı git reposu (kontrol grubu: yukarıdaki template klonu testleri aynı yoldan geçer) ---------
    def test_hedef_yabanci_git_reposu_pull_ve_betik_calismaz(self):
        bare, isaret = self.yabanci_repo("yabanci")
        self.git(self.tmp, "clone", "-q", str(bare), str(self.hedef))
        self.uzakta_commit("YABANCI_YENI.txt", kaynak=bare)  # pull yapılsaydı bu dosya gelirdi
        head = self.git(self.hedef, "rev-parse", "HEAD").stdout.strip()
        r = self.kur("-Evet")
        c = self.cikti(r)
        self.assertEqual(r.returncode, 1, c)
        self.assertIn("template'inin klonu değil", c)
        self.assertIn("CORE-ID: AXET-CORE-", c)
        self.assertEqual(self.git(self.hedef, "rev-parse", "HEAD").stdout.strip(), head)
        self.assertFalse((self.hedef / ".git" / "FETCH_HEAD").exists(), "yabancı repoda fetch yapıldı")
        self.assertFalse((self.hedef / "YABANCI_YENI.txt").exists())
        self.assertFalse(isaret.exists(), "yabancı install.py/doctor.py çalıştırıldı")
        self.assertFalse(self.cfg.exists())

    def test_kaynak_yabanci_repo_ise_klon_sonrasi_betik_calismaz(self):
        bare, isaret = self.yabanci_repo("yabanci-kaynak")
        r = self.kur("-Kaynak", str(bare), "-Hedef", str(self.hedef), "-Evet", varsayilan=False)
        self.assertEqual(r.returncode, 1, self.cikti(r))
        self.assertIn("klonlanan kaynak bu aXet template'i değil", self.cikti(r))
        self.assertFalse(isaret.exists(), "yabancı install.py/doctor.py çalıştırıldı")
        self.assertFalse(self.cfg.exists())

    def test_kaldir_yabanci_klasorde_betik_calistirmaz(self):
        bare, isaret = self.yabanci_repo("yabanci-kaldir")
        self.git(self.tmp, "clone", "-q", str(bare), str(self.hedef))
        r = self.kur("-Kaldir")
        self.assertEqual(r.returncode, 1, self.cikti(r))
        self.assertIn("template'inin klonu değil", self.cikti(r))
        self.assertFalse(isaret.exists(), "yabancı install.py çalıştırıldı")

    # --- deneme modu ------------------------------------------------------------------------------------------
    def test_deneme_modu_hicbir_sey_yazmaz(self):
        r = self.kur("-DenemeModu")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("DENEME MODU bitti", self.cikti(r))
        self.assertFalse(self.hedef.exists())
        self.assertEqual(list(self.xdg.iterdir()), [])

    def test_deneme_modu_kurulu_klonda_fetch_ve_config_yazmaz(self):
        self.kurulu()
        self.uzakta_commit()
        once_cfg = self.cfg.read_bytes()
        once_git = _goruntu(self.hedef / ".git")
        r = self.kur("-DenemeModu")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("dry-run", self.cikti(r))
        self.assertEqual(self.cfg.read_bytes(), once_cfg)
        self.assertEqual(_goruntu(self.hedef / ".git"), once_git)
        self.assertEqual(sorted(p.name for p in self.cfg.parent.iterdir()), ["axet-code.json"])  # yedek de yok

    # --- madde 4: sonu ters bölü ile biten tırnaklı -Hedef ------------------------------------------------------
    def test_tirnakli_ters_bolu_ile_biten_hedef_durur(self):
        bin_, kayit = self.sahte_winget()
        env = self.path_degistir(self.env, str(bin_) + os.pathsep + self.path_oku(self.env))  # sahte winget önde

        def sarmala(hedef_metni: str) -> subprocess.CompletedProcess:
            # Python'un argüman kaçışını atlamak için komut satırı .cmd içine kullanıcının yazdığı gibi konur.
            # -Kaynak önde: kusur geri gelse bile yerel bare'den klonlanır, ağa çıkılmaz.
            w = self.tmp / "sarmal.cmd"
            w.write_bytes((f'@echo off\r\ncall "{KUR_CMD}" -Kaynak "{self.kaynak}" -Hedef "{hedef_metni}" '
                           f'-DenemeModu -WingetKapali\r\nexit /b %ERRORLEVEL%\r\n').encode("ascii"))
            return subprocess.run([COMSPEC, "/c", str(w)], env=env, cwd=str(self.tmp), capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=600)

        bozuk = self.tmp / "c b"
        r = sarmala(str(bozuk) + "\\")
        c = self.cikti(r)
        self.assertEqual(r.returncode, 1, c)
        self.assertIn("ters bölü ile BİTİRME", c)
        self.assertNotIn("Klonlanıyor", c)
        self.assertEqual(sorted(p.name for p in self.tmp.iterdir() if p.name.startswith("c b")), [])
        self.assertFalse(kayit.exists(), "winget çağrıldı")
        self.assertEqual(list(self.xdg.iterdir()), [])
        # kontrol grubu: aynı yol ters bölüsüz -> parametreler yerinde, deneme modu tamamlanır, hiçbir şey oluşmaz
        r = sarmala(str(bozuk))
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("DENEME MODU bitti", self.cikti(r))
        self.assertFalse(bozuk.exists())
        self.assertFalse(kayit.exists(), "winget çağrıldı")

    # --- kaldırma ---------------------------------------------------------------------------------------------
    def test_kaldir_config_temizler_klon_kalir(self):
        self.kurulu()
        r = self.kur("-Kaldir")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        metin = json.dumps(self.cfg_oku())
        self.assertNotIn(self.hedef.as_posix(), metin)
        self.assertNotIn(self.hedef.as_posix().lower(), metin.lower())
        self.assertTrue((self.hedef / "scripts" / "install.py").is_file())
        self.assertIn("SİLİNMEDİ", self.cikti(r))
        self.assertIn("SAP'ye yazma iznini de kapatır", self.cikti(r))

    def klondaki_kur(self, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
        """KURULU klonun KENDİ kur.cmd'sini -Hedef VERMEDEN çağırır (kur() -Hedef'i daima ekler, bu yolu göremez)."""
        return subprocess.run([COMSPEC, "/c", "call", str(self.hedef / "kur.cmd"), *args, "-WingetKapali"],
                              env=env or self.env, cwd=str(self.tmp), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=600)

    # --- K-B: klonun içindeki kur.cmd -Kaldir KENDİ klonunu kaldırır ---------------------------------------------
    def test_kaldir_hedefsiz_betigin_kendi_klonunu_kaldirir(self):
        self.kurulu()
        ev = self.tmp / "ev"  # %USERPROFILE%\axet YOK: eski davranış orayı denetleyip "klonu değil" diye dururdu
        ev.mkdir()
        r = self.klondaki_kur("-Kaldir", env=dict(self.env, USERPROFILE=str(ev)))
        c = self.cikti(r)
        self.assertEqual(r.returncode, 0, c)
        self.assertIn(f"Klon   : {self.hedef}", c)
        self.assertNotIn("template'inin klonu değil", c)
        metin = json.dumps(self.cfg_oku()).lower()
        self.assertNotIn(self.hedef.as_posix().lower(), metin)

    def test_kaldir_acik_hedef_betik_konumunu_ezmez(self):
        # Negatif kontrol: -Hedef açıkça verilirse betiğin konumu kullanılmaz (verilen klasör denetlenir).
        self.kurulu()
        yabanci = self.tmp / "baska-klasor"
        yabanci.mkdir()
        r = self.klondaki_kur("-Kaldir", "-Hedef", str(yabanci))
        c = self.cikti(r)
        self.assertEqual(r.returncode, 1, c)
        self.assertIn("template'inin klonu değil", c)
        self.assertIn(self.hedef.as_posix(), json.dumps(self.cfg_oku()))  # kendi kaydı yerinde

    # --- K-A: adsız argüman sessizce -Hedef olmaz ----------------------------------------------------------------
    def test_adsiz_arguman_reddedilir_hicbir_sey_olusmaz(self):
        adsiz = self.tmp / "adsiz-hedef"
        r = self.kur(str(adsiz), "-DenemeModu", varsayilan=False)
        c = self.cikti(r)
        self.assertEqual(r.returncode, 1, c)
        self.assertIn("adı verilmemiş argüman", c)
        self.assertNotIn(f"Klon   : {adsiz}", c)  # eski davranış: adsız değer -Hedef'e bağlanırdı
        self.assertFalse(adsiz.exists())
        self.assertFalse(self.cfg.exists())

    def test_onceki_baska_klon_uyarilir_ve_iki_cekirdek_kalir(self):
        # Config önce BAŞKA bir klonu (burada AXET_HOME) gösteriyor.
        self.global_config(sap=True)
        r = self.kur("-Evet")
        c = self.cikti(r)
        # Ölçüldü (HEAD f179e14): doctor.py iki template kopyasının aynı skill adlarını FAIL sayar -> kurulum yazılır
        # ama doğrulama geçmez, kur.ps1 çıkış 4 verir. İki çekirdek durumunun kullanıcıya görünür olduğu yer burası.
        self.assertEqual(r.returncode, 4, c)
        self.assertIn("son kontrol (doctor) sorun buldu", c)
        self.assertNotIn("Kurulum TAMAM", c)
        ctx = self.cfg_oku()["options"]["context_paths"]
        # Ölçüm: install.py yalnız kendi klonunun kayıtlarını yönetir -> iki çekirdek birlikte kalır.
        self.assertIn((AXET_HOME / "core" / "00-temel.md").as_posix(), ctx)
        self.assertIn((self.hedef / "core" / "00-temel.md").as_posix(), ctx)
        # kur.ps1 bunu açıkça yazar, SAP yazma izninin de kapanacağını söyler, komutu bulunan Python'un tam yoluyla
        # verir ve kendisi ÇALIŞTIRMAZ (AXET_HOME kayıtları config'te duruyor).
        self.assertIn("önceki kurulum şu klonu gösteriyordu", c)
        self.assertIn(str(AXET_HOME), c)
        self.assertIn("SAP'ye yazma iznini de KAPATIR", c)
        desen = r'& "([^"]+)" "' + re.escape(str(AXET_HOME / "scripts" / "install.py")) + r'" --uninstall'
        komut = re.search(desen, c)
        self.assertIsNotNone(komut, c)
        self.assertTrue(Path(komut.group(1)).is_file(), komut.group(1))
        # Y1a: doctor'ın FAIL satırlarından SONRA, son mesajda doğru çözüm yeniden basılır
        son = c[c.index("son kontrol (doctor) sorun buldu"):]
        self.assertIn("önerisini UYGULAMA", son)
        self.assertRegex(son, desen)
        self.assertIn("kur.cmd", son[son.index("önerisini UYGULAMA"):])

    # --- madde 1-2: ASCII olmayan Python yolu + ASCII olmayan hedef, UTF-8 ortam değişkenleri YOK ------------------
    def test_ascii_olmayan_python_ve_hedef_utf8_ayarsiz_ortamda(self):
        venv = self.tmp / "Ğüşı Özgür" / "venv"
        r = subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(venv)], capture_output=True, text=True,
                           stdin=subprocess.DEVNULL, timeout=300)
        self.assertEqual(r.returncode, 0, r.stderr)
        venv_py = venv / "Scripts" / "python.exe"
        env = {k: v for k, v in self.env.items() if k.upper() not in ("PYTHONUTF8", "PYTHONIOENCODING")}
        env = self.path_degistir(env, str(venv_py.parent) + os.pathsep + self.path_oku(env))
        # kontrol: bu ortamda venv Python'u borudan UTF-8 yazmıyor (yoksa test ASCII dışı yolu sınamaz)
        k = subprocess.run([str(venv_py), "-c", "import sys;print(sys.stdout.encoding)"], env=env, capture_output=True,
                           text=True, stdin=subprocess.DEVNULL, timeout=60)
        self.assertNotIn("utf", k.stdout.lower(), "ortam zaten UTF-8; test ASCII dışı yolu sınamıyor")

        hedef = self.tmp / "hedef Özgür ğşı"
        r = self.kur("-Evet", env=env, hedef=hedef)
        c = self.cikti(r)
        self.assertEqual(r.returncode, 0, c)
        self.assertIn(f"OK Python: ", c)
        self.assertIn(str(venv_py), c)  # yol bozulmadan okundu ve o yorumlayıcı seçildi
        self.assertTrue(self.cfg.is_file(), "config yazılmadı:\n" + c)
        ctx = self.cfg_oku()["options"]["context_paths"]
        self.assertIn((hedef / "core" / "00-temel.md").as_posix(), ctx)
        self.assertIn("SONUÇ: 0 FAIL", c)
        self.assertIn("Kurulum TAMAM — aXet'i aç. (yeni klon)", c)
        self.assertNotIn("beklenmeyen hata", c)

        r = self.kur("-Evet", env=env, hedef=hedef)
        c = self.cikti(r)
        self.assertEqual(r.returncode, 0, c)
        self.assertIn("Config zaten bu klonu gösteriyor", c)
        self.assertNotIn("önceki kurulum şu klonu gösteriyordu", c)

    # --- gate 2 / Y2: dubious ownership ----------------------------------------------------------------------
    def test_dubious_ownership_git_hatasi_ve_tarif_basilir_calistirilmaz(self):
        self.kurulu()  # kontrol grubu: aynı klon, ek ortam değişkeni yokken kurulum geçti
        head = self.git(self.hedef, "rev-parse", "HEAD").stdout.strip()
        gitconfig = Path(self.env["GIT_CONFIG_GLOBAL"])
        once = gitconfig.read_bytes()
        env = dict(self.env)
        # Ölçüldü (Git 2.55): git'in test değişkeni gerçek "detected dubious ownership" hatasını üretir; global config'e
        # ya da dosya sahipliğine dokunmadan UNC/başka sahipli klasör durumunu taklit eder.
        env["GIT_TEST_ASSUME_DIFFERENT_OWNER"] = "1"
        r = self.kur("-Evet", env=env)
        c = self.cikti(r)
        self.assertEqual(r.returncode, 1, c)
        self.assertIn("dubious ownership", c)
        self.assertIn("git config --global --add safe.directory", c)
        self.assertNotIn("git klonunun kökü değil", c)
        self.assertEqual(gitconfig.read_bytes(), once, "global git config'e yazıldı")
        self.assertEqual(self.git(self.hedef, "rev-parse", "HEAD").stdout.strip(), head)

    # --- Z101: SAP'nin zorunlu Python paketleri kur.cmd akışında, bulunan yorumlayıcıyla kurulur ----------------
    def _paket_ortami(self, kip: str, kurulu: bool = False) -> tuple[dict, Path]:
        """Gerçek pip yok, ağ yok. "eksik" = PYTHONPATH başında engel modülleri; "kurulu" = boş sahte modüller.
        Sahte pip (AXET_PAKET_PIP) kendisini çalıştıran yorumlayıcıyı + argümanlarını kayda yazar."""
        import install
        d = self.tmp / ("_paket_kurulu" if kurulu else "_paket_engel")
        for ithal, _ in install.ZORUNLU_PAKETLER:
            govde = "" if kurulu else f"raise ModuleNotFoundError(\"No module named '{ithal}'\", name='{ithal}')\n"
            self.yaz(d / f"{ithal}.py", govde)
        kayit = self.tmp / "_pip_kayit.txt"
        pip = self.yaz(self.tmp / "_sahte_pip.py",
                       "import os, sys\n"
                       "open(os.environ['AXET_TEST_PIP_KAYIT'], 'a', encoding='utf-8').write(\n"
                       "    sys.executable + '|' + ' '.join(sys.argv[1:]) + '\\n')\n"
                       # tur 2: proxy tavsiyesi yalnız ağ imzasında verilir ⇒ sahte ağ hatası imzayı da basar
                       + ("print(\"WARNING: Retrying ... ProxyError('Cannot connect to proxy.')\", file=sys.stderr)\n"
                          if kip == "ag" else "")
                       + f"sys.exit({1 if kip == 'ag' else 0})\n")
        env = {k: v for k, v in self.env.items() if k != "AXET_PAKET_KUR"}
        env.update({"AXET_PAKET_PIP": str(pip), "AXET_TEST_PIP_KAYIT": str(kayit), "PYTHONPATH": str(d)})
        return env, kayit

    def test_z101_eksik_paket_bulunan_python_ile_kurulmaya_calisilir_ag_hatasi_durdurmaz(self):
        env, kayit = self._paket_ortami("ag")
        r = self.kur("-Evet", env=env)
        c = self.cikti(r)
        self.assertEqual(r.returncode, 0, c)  # çıkış sözleşmesi: paket kurulamadı diye 1/2/4 DEĞİL
        cagri = kayit.read_text(encoding="utf-8").splitlines()
        self.assertEqual(1, len(cagri), c)
        exe, argumanlar = cagri[0].split("|", 1)
        self.assertEqual(os.path.normcase(exe), os.path.normcase(str(self.kur_python())),
                         "pip, kur.ps1'in bulduğu yorumlayıcıyla çağrılmalı")
        self.assertIn("install", argumanlar.split())
        self.assertIn("PAKETLER: EKSİK", c)
        self.assertIn("proxy", c)
        self.assertTrue(any(s.startswith("[WARN]") and "SAP Python paketleri EKSİK" in s for s in c.splitlines()), c)
        self.assertIn("Kurulum TAMAM", c)

    def test_z101_kontrol_grubu_paketler_kuruluysa_pip_cagrilmaz(self):
        env, kayit = self._paket_ortami("basari", kurulu=True)
        r = self.kur("-Evet", env=env)
        c = self.cikti(r)
        self.assertEqual(r.returncode, 0, c)
        self.assertFalse(kayit.exists(), c)
        self.assertIn("PAKETLER: TAMAM", c)
        self.assertTrue(any(s.startswith("[PASS]") and "SAP Python paketleri" in s for s in c.splitlines()), c)

    # --- geçersiz karakterli XDG_CONFIG_HOME: git var ama `git --version` hata veriyor -------------------------
    def test_gecersiz_xdg_git_bulundu_calismadi(self):
        # Ölçüldü (Git 2.55.0.windows.5, GIT_CONFIG_GLOBAL tanımsız): XDG_CONFIG_HOME içinde < ya da | varsa
        # `git --version` rc 128 + "fatal: unable to access '<xdg>/git/config': Invalid argument". GIT_CONFIG_GLOBAL
        # tanımlıyken git bu yolu okumaz ve kusur görünmez -> iki değişken de kaldırılır. Gerçek ~/.gitconfig okunmasın
        # diye HOME geçici klasör. -DenemeModu: yalnız okuma.
        temel = {k: v for k, v in self.env.items() if k.upper() not in ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM", "HOME")}
        temel["HOME"] = str(self.tmp / "_home")
        (self.tmp / "_home").mkdir()
        # Git sürümüne bağlı: bu git `--version` sırasında XDG config yolunu okumuyorsa senaryo üretilemez -> atla.
        dene = subprocess.run(["git", "--version"], env=dict(temel, XDG_CONFIG_HOME=str(self.tmp / "a<b")),
                              capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60)
        if dene.returncode == 0:
            self.skipTest(f"bu git ({dene.stdout.strip()}) --version sırasında XDG yolunu okumuyor; senaryo üretilemez")
        # kontrol grubu: aynı ortam, geçerli XDG -> Git bulunur, deneme modu tamamlanır
        r = self.kur("-DenemeModu", env=temel)
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("OK Git: git version", self.cikti(r))
        for karakter in ("<", "|"):
            with self.subTest(karakter=karakter):
                env = dict(temel)
                env["XDG_CONFIG_HOME"] = str(self.tmp / f"a{karakter}b")
                r = self.kur("-DenemeModu", env=env)
                c = self.cikti(r)
                self.assertEqual(r.returncode, 2, c)
                self.assertIn("Git bulundu ama çalışmadı", c)
                self.assertIn("unable to access", c)  # git'in kendi mesajı basıldı
                self.assertNotIn("EKSİK: Git bulunamadı", c)
                self.assertNotIn("winget install --id Git.Git", c)  # git zaten kurulu: kurulum önerilmez
                self.assertNotIn("OK Git", c)
                self.assertFalse(self.hedef.exists())

    # --- K1: config'teki başka klon diskte yok (silinmiş/taşınmış) ------------------------------------------------
    def test_configteki_baska_klon_silinmisse_bayat_kayit_denir(self):
        # Kontrol grubu: test_onceki_baska_klon_uyarilir_ve_iki_cekirdek_kalir (klon VAR -> --uninstall önerisi, çıkış 4).
        silinmis = self.tmp / "silinmis-klon"
        bayat_core = (silinmis / "core" / "00-temel.md").as_posix()
        bayat_skills = (silinmis / "skills").as_posix()
        bayat_desen = (silinmis / "core").as_posix() + "/*"
        self.yaz(self.cfg, json.dumps({"options": {"context_paths": [bayat_core], "skills_paths": [bayat_skills]},
                                       "permissions": {"rules": {"edit": {bayat_desen: "deny"}}}}, indent=2))
        r = self.kur("-Evet")
        c = self.cikti(r)
        self.assertEqual(r.returncode, 0, c)
        self.assertIn("SONUÇ: 0 FAIL", c)
        self.assertIn("kayıtlı klon klasörü yok; kayıt bayat", c)
        # K-C: config'te bu klona eşit kayıt YOK (yalnız bayat kayıt var) -> "zaten bu klonu gösteriyor" denmez
        self.assertNotIn("Config zaten bu klonu gösteriyor", c)
        self.assertNotIn(str(silinmis / "scripts" / "install.py"), c)  # olmayan betik önerilmez
        self.assertNotIn("doctor'ın FAIL satırları", c)  # doctor 0 FAIL
        son = c[c.index("Kurulum TAMAM"):]
        self.assertIn(str(self.cfg), son)  # elle temizlenecek dosya
        for giris in (bayat_core, bayat_skills, bayat_desen):
            self.assertIn(giris, son)
        # config'e bayat girişler için otomatik yazma yok: install.py yalnız kendi klonunu ekledi
        cfg = self.cfg_oku()
        self.assertIn(bayat_core, cfg["options"]["context_paths"])
        self.assertIn(bayat_skills, cfg["options"]["skills_paths"])
        self.assertIn(bayat_desen, cfg["permissions"]["rules"]["edit"])
        self.assertIn((self.hedef / "core" / "00-temel.md").as_posix(), cfg["options"]["context_paths"])

    # --- K2: junction ile verilen hedef -------------------------------------------------------------------------
    def test_junction_hedef_klon_koku_sayilir(self):
        # Ölçüldü (Git 2.55): junction'lı yolda `rev-parse --show-toplevel` çözümlenmiş (asıl) yolu döndürür.
        self.git(self.tmp, "clone", "-q", str(self.kaynak), str(self.hedef))
        bag, alt_bag = self.tmp / "hedef-bag", self.tmp / "alt-bag"
        try:
            for b, hedef in ((bag, self.hedef), (alt_bag, self.hedef / "scripts")):
                k = subprocess.run([COMSPEC, "/c", "mklink", "/J", str(b), str(hedef)], capture_output=True, text=True,
                                   stdin=subprocess.DEVNULL, timeout=60)
                self.assertEqual(k.returncode, 0, k.stdout + k.stderr)
            # kontrol grubu: aynı repo junction'sız -> deneme modu güncellemeyi gösterir
            r = self.kur("-DenemeModu")
            self.assertEqual(r.returncode, 0, self.cikti(r))
            self.assertIn("[deneme] güncellenecekti", self.cikti(r))
            r = self.kur("-DenemeModu", hedef=bag)
            c = self.cikti(r)
            self.assertEqual(r.returncode, 0, c)
            self.assertIn("[deneme] güncellenecekti", c)
            self.assertNotIn("okuyamadı", c)
            # kontrol grubu: repo içindeki alt klasörü gösteren junction kök SAYILMAZ
            r = self.kur("-DenemeModu", hedef=alt_bag)
            c = self.cikti(r)
            self.assertEqual(r.returncode, 1, c)
            self.assertIn("git klonunun kökü değil", c)
            self.assertNotIn("okuyamadı", c)
        finally:
            for b in (bag, alt_bag):  # junction yalnız bağ olarak kaldırılır (hedef silinmez)
                subprocess.run([COMSPEC, "/c", "rmdir", str(b)], capture_output=True, stdin=subprocess.DEVNULL, timeout=60)
        self.assertFalse(bag.exists())
        self.assertTrue((self.hedef / "scripts" / "install.py").is_file())

    # --- gate 3 / HIGH: junction'lı hedefle iki GERÇEK kurulum ---------------------------------------------------
    def test_junction_hedef_ikinci_kurulum_aktif_klonu_kaldirmayi_onermez(self):
        # Ölçüldü: install.py klon kökünü Path(__file__).resolve() ile (junction ÇÖZÜLMÜŞ) yazar; kur.ps1 karşılaştırması
        # çözülmemiş yolla yapılınca 2. koşumda AKTİF klon için --uninstall önerisi çıktı.
        env = dict(self.env)
        env["HOME"] = str(self.tmp / "_home")
        (self.tmp / "_home").mkdir()
        self.git(self.tmp, "clone", "-q", str(self.kaynak), str(self.hedef))
        bag = self.tmp / "hedef-bag"
        try:
            k = subprocess.run([COMSPEC, "/c", "mklink", "/J", str(bag), str(self.hedef)], capture_output=True, text=True,
                               stdin=subprocess.DEVNULL, timeout=60)
            self.assertEqual(k.returncode, 0, k.stdout + k.stderr)
            kontrol_env = dict(env, XDG_CONFIG_HOME=str(self.tmp / "_xdg_kontrol"))
            # kontrol grubu önce: aynı klon, gerçek yol, ayrı config
            for etiket, hedef, e in (("kontrol: gerçek yol", self.hedef, kontrol_env), ("junction", bag, env)):
                with self.subTest(etiket):
                    r1 = self.kur("-Evet", env=e, hedef=hedef)
                    self.assertEqual(r1.returncode, 0, self.cikti(r1))
                    r2 = self.kur("-Evet", env=e, hedef=hedef)
                    c = self.cikti(r2)
                    self.assertEqual(r2.returncode, 0, c)
                    self.assertIn("Config zaten bu klonu gösteriyor", c)
                    self.assertNotIn("önceki kurulum şu klonu gösteriyordu", c)
                    self.assertNotIn("--uninstall", c)
                    self.assertNotIn("ÖNCE BUNU YAP", c)
        finally:
            subprocess.run([COMSPEC, "/c", "rmdir", str(bag)], capture_output=True, stdin=subprocess.DEVNULL, timeout=60)
        self.assertFalse(bag.exists())
        self.assertTrue((self.hedef / "scripts" / "install.py").is_file())

    # --- gate 3 / HIGH koşulu: yol çözülemezse karşılaştırma ÖLÇÜLEMEDİ, --uninstall önerisi YOK ---------------
    def test_gercek_yol_olculemezse_uninstall_onerilmez(self):
        # Gercek-Yol başarısızsa çözülmemiş yola düşülmez; düşülseydi junction'lı hedefte AKTİF klon "başka klon" sanılıp
        # --uninstall önerilirdi. Python YALNIZ o çağrı için bozulur: PYTHONPATH'teki sitecustomize, AXET_TEST_RESOLVE_BOZUK
        # yolunun resolve()'una hata verdirir (install.py kendi __file__'ını çözer, etkilenmez). -DenemeModu: yazma yok.
        self.git(self.tmp, "clone", "-q", str(self.kaynak), str(self.hedef))
        self.yaz(self.cfg, json.dumps({"options": {"context_paths": [(self.hedef / "core" / "00-temel.md").as_posix()]}}))
        site = self.yaz(self.tmp / "_site" / "sitecustomize.py", "\n".join([
            "import os, pathlib",
            "_hedef = os.environ.get('AXET_TEST_RESOLVE_BOZUK')",
            "if _hedef:",
            "    _asil = pathlib.Path.resolve",
            "    def _bozuk(self, strict=False):",
            "        if os.path.normcase(os.path.abspath(str(self))) == os.path.normcase(os.path.abspath(_hedef)):",
            "            raise OSError('test: resolve bozuk')",
            "        return _asil(self, strict)",
            "    pathlib.Path.resolve = _bozuk", ""]))
        bag = self.tmp / "hedef-bag"
        try:
            k = subprocess.run([COMSPEC, "/c", "mklink", "/J", str(bag), str(self.hedef)], capture_output=True, text=True,
                               stdin=subprocess.DEVNULL, timeout=60)
            self.assertEqual(k.returncode, 0, k.stdout + k.stderr)
            bozuk_env = dict(self.env, PYTHONPATH=str(site.parent), AXET_TEST_RESOLVE_BOZUK=str(bag))
            # bozma düzeneğinin kendisi ölçülür: yalnız hedef yolun resolve()'u düşer
            kod = "import pathlib,sys; print(pathlib.Path(sys.argv[1]).resolve())"
            dus = subprocess.run([sys.executable, "-c", kod, str(bag)], env=bozuk_env, capture_output=True, text=True, timeout=60)
            self.assertNotEqual(dus.returncode, 0, dus.stdout)
            gec = subprocess.run([sys.executable, "-c", kod, str(bag / "scripts" / "install.py")], env=bozuk_env,
                                 capture_output=True, text=True, timeout=60)
            self.assertEqual(gec.returncode, 0, gec.stderr)
            # kontrol grubu: Python sağlamken junction çözülür -> aynı klon
            r = self.kur("-DenemeModu", hedef=bag)
            c = self.cikti(r)
            self.assertEqual(r.returncode, 0, c)
            self.assertIn("Config zaten bu klonu gösteriyor", c)
            self.assertNotIn("--uninstall", c)
            # bozuk: karşılaştırma ölçülemez -> uyarı, kaldırma önerisi yok
            r = self.kur("-DenemeModu", env=bozuk_env, hedef=bag)
            c = self.cikti(r)
            self.assertEqual(r.returncode, 0, c)
            self.assertIn("klon karşılaştırması ÖLÇÜLEMEDİ", c)
            self.assertNotIn("--uninstall", c)
            self.assertNotIn("önceki kurulum şu klonu gösteriyordu", c)
            self.assertNotIn("Config zaten bu klonu gösteriyor", c)
        finally:
            subprocess.run([COMSPEC, "/c", "rmdir", str(bag)], capture_output=True, stdin=subprocess.DEVNULL, timeout=60)
        self.assertFalse(bag.exists())
        self.assertTrue((self.hedef / "scripts" / "install.py").is_file())

    # --- re-gate / LOW 1: config junction'lı biçimi tutuyor, kur gerçek yolla çalışıyor ---------------------------
    def test_config_junction_bicimi_gercek_hedef_aktif_klonu_kaldirmayi_onermez(self):
        # Ölçüldü (re-gate senaryo G): config'teki kök çözülmeden karşılaştırılınca AKTİF klon "önceki kurulum şu klonu
        # gösteriyordu" + --uninstall önerisi aldı. Config'teki kök çözülemezse ÖLÇÜLEMEDİ: öneri yok. -DenemeModu: yazma yok.
        self.git(self.tmp, "clone", "-q", str(self.kaynak), str(self.hedef))
        diger = self.tmp / "diger-klon"
        self.git(self.tmp, "clone", "-q", str(self.kaynak), str(diger))
        site = self.yaz(self.tmp / "_site" / "sitecustomize.py", "\n".join([
            "import os, pathlib",
            "_hedef = os.environ.get('AXET_TEST_RESOLVE_BOZUK')",
            "if _hedef:",
            "    _asil = pathlib.Path.resolve",
            "    def _bozuk(self, strict=False):",
            "        if os.path.normcase(os.path.abspath(str(self))) == os.path.normcase(os.path.abspath(_hedef)):",
            "            raise OSError('test: resolve bozuk')",
            "        return _asil(self, strict)",
            "    pathlib.Path.resolve = _bozuk", ""]))
        bag = self.tmp / "hedef-bag"
        cekirdek = lambda kok: (kok / "core" / "00-temel.md").as_posix()  # noqa: E731
        try:
            k = subprocess.run([COMSPEC, "/c", "mklink", "/J", str(bag), str(self.hedef)], capture_output=True, text=True,
                               stdin=subprocess.DEVNULL, timeout=60)
            self.assertEqual(k.returncode, 0, k.stdout + k.stderr)
            bozuk_env = dict(self.env, PYTHONPATH=str(site.parent), AXET_TEST_RESOLVE_BOZUK=str(bag))
            vakalar = [  # (ad, config'teki kök, env, beklenen, beklenmeyen)
                ("kontrol: config gerçek yol", self.hedef, self.env, ["Config zaten bu klonu gösteriyor"],
                 ["--uninstall", "önceki kurulum şu klonu gösteriyordu", "ÖLÇÜLEMEDİ"]),
                ("kontrol: gerçekten başka klon önerilir", diger, self.env,
                 ["önceki kurulum şu klonu gösteriyordu", str(diger / "scripts" / "install.py") + '" --uninstall'],
                 ["Config zaten bu klonu gösteriyor"]),
                ("config junction biçimi", bag, self.env, ["Config zaten bu klonu gösteriyor"],
                 ["--uninstall", "önceki kurulum şu klonu gösteriyordu", "kayıt bayat", "ÖLÇÜLEMEDİ"]),
                ("config kökü çözülemez", bag, bozuk_env,
                 ["config'teki klonla karşılaştırma ÖLÇÜLEMEDİ", f"config'te kayıtlı klon: {bag}"],
                 ["--uninstall", "önceki kurulum şu klonu gösteriyordu", "kayıt bayat", "Config zaten bu klonu gösteriyor"]),
            ]
            for ad, kok, env, beklenen, beklenmeyen in vakalar:
                with self.subTest(ad):
                    self.yaz(self.cfg, json.dumps({"options": {"context_paths": [cekirdek(kok)]}}))
                    r = self.kur("-DenemeModu", env=env, hedef=self.hedef)
                    c = self.cikti(r)
                    self.assertEqual(r.returncode, 0, c)
                    for s in beklenen:
                        self.assertIn(s, c)
                    for s in beklenmeyen:
                        self.assertNotIn(s, c)
        finally:
            subprocess.run([COMSPEC, "/c", "rmdir", str(bag)], capture_output=True, stdin=subprocess.DEVNULL, timeout=60)
        self.assertFalse(bag.exists())
        self.assertTrue((self.hedef / "scripts" / "install.py").is_file())

    # --- re-gate / LOW 2: config'te ~ ile yazılmış bayat klon ------------------------------------------------------
    def test_tilde_bayat_kayit_acilmis_yolla_listelenir(self):
        # Ölçüldü (re-gate senaryo H1): Config-Klonlari ~ açmadan GetFullPath yapınca "<cwd>\~\eski-axet" çıktı ve
        # Config-Girisleri (~ açar) eşleşmeyince "giriş kalmamış" dendi; config'te 3 giriş duruyordu.
        ev = self.tmp / "_home"
        ev.mkdir()
        env = dict(self.env, USERPROFILE=str(ev), HOME=str(ev))  # Python expanduser Windows'ta USERPROFILE okur
        girisler = ["~/eski-axet/core/00-temel.md", "~/eski-axet/skills", "~/eski-axet/core/*"]
        self.yaz(self.cfg, json.dumps({"options": {"context_paths": [girisler[0]], "skills_paths": [girisler[1]]},
                                       "permissions": {"rules": {"edit": {girisler[2]: "deny"}}}}))
        r = self.kur("-Evet", env=env)
        c = self.cikti(r)
        self.assertEqual(r.returncode, 0, c)
        self.assertIn(f"kayıt bayat: {ev / 'eski-axet'}", c)
        self.assertNotIn(str(self.tmp / "~"), c)
        self.assertNotIn("giriş kalmamış", c)
        son = c[c.index("BAYAT KAYIT"):]
        for g in girisler:
            self.assertIn(g, son)
        self.assertNotIn(str(ev / "eski-axet" / "scripts" / "install.py"), c)  # olmayan betik önerilmez

    # --- re-gate / ÖNERİ 3: Gercek-Yol stdout'taki başka satırı yol sanmaz (fonksiyon AST'den, betik çalışmaz) --------
    def test_gercek_yol_stdout_banner_yol_sanilmaz(self):
        self.git(self.tmp, "clone", "-q", str(self.kaynak), str(self.hedef))
        site = self.yaz(self.tmp / "_site" / "sitecustomize.py", "\n".join([
            "import atexit, os",
            "_m = os.environ.get('AXET_TEST_BANNER')",
            "if _m == 'duz':",
            "    atexit.register(print, 'AXET-BANNER merhaba')",
            "elif _m == 'isaretli':",
            "    atexit.register(print, 'AXETYOL:C:\\\\sahte-banner')", ""]))
        surucu = self.yaz(self.tmp / "surucu_gy.ps1", "\r\n".join([
            "param([string]$Kur, [string]$Yol, [string]$Py)",
            "$ErrorActionPreference = 'Continue'",
            "[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false",
            "$env:PYTHONUTF8 = '1'",
            "$ast = [System.Management.Automation.Language.Parser]::ParseFile($Kur, [ref]$null, [ref]$null)",
            "$fonk = $ast.FindAll({ param($a) $a -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $true) |",
            "    Where-Object { $_.Name -in @('Son-Kod', 'Gercek-Yol') }",
            "foreach ($f in $fonk) { . ([scriptblock]::Create($f.Extent.Text)) }",
            "$script:PY = $Py",
            "foreach ($m in @('yok', 'duz', 'isaretli')) {",
            "    $env:AXET_TEST_BANNER = $m",
            "    $s = Gercek-Yol $Yol",
            "    [Console]::Out.WriteLine(\"$m|SONUC|$s\")",
            "    [Console]::Out.WriteLine(\"$m|NULL|$($null -eq $s)\")",
            "    [Console]::Out.WriteLine(\"$m|HATA|$($script:GercekYolHata)\")",
            "}", ""]), newline="")
        bag = self.tmp / "hedef-bag"
        try:
            k = subprocess.run([COMSPEC, "/c", "mklink", "/J", str(bag), str(self.hedef)], capture_output=True, text=True,
                               stdin=subprocess.DEVNULL, timeout=60)
            self.assertEqual(k.returncode, 0, k.stdout + k.stderr)
            env = dict(self.env, PYTHONPATH=str(site.parent))
            r = subprocess.run([str(POWERSHELL), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(surucu),
                                "-Kur", str(KUR_PS1), "-Yol", str(bag), "-Py", sys.executable],
                               env=env, capture_output=True, text=True, encoding="utf-8", errors="replace",
                               stdin=subprocess.DEVNULL, timeout=120)
        finally:
            subprocess.run([COMSPEC, "/c", "rmdir", str(bag)], capture_output=True, stdin=subprocess.DEVNULL, timeout=60)
        self.assertFalse(bag.exists())
        c = self.cikti(r)
        cikan = {}
        for satir in r.stdout.splitlines():
            parca = satir.split("|", 2)
            if len(parca) == 3:
                cikan[(parca[0], parca[1])] = parca[2]
        asil = os.path.normcase(str(self.hedef.resolve()))
        with self.subTest("kontrol: banner yok -> junction çözülür"):
            self.assertEqual(os.path.normcase(cikan.get(("yok", "SONUC"), "")), asil, c)
        with self.subTest("stdout banner yol sanılmaz"):
            self.assertNotIn("BANNER", cikan.get(("duz", "SONUC"), "?"), c)
            self.assertEqual(os.path.normcase(cikan.get(("duz", "SONUC"), "")), asil, c)
        with self.subTest("önekli ikinci satır: belirsiz -> ÖLÇÜLEMEDİ"):
            self.assertNotIn("sahte-banner", cikan.get(("isaretli", "SONUC"), "?"), c)
            self.assertEqual(cikan.get(("isaretli", "NULL")), "True", c)
            self.assertTrue(cikan.get(("isaretli", "HATA")), c)

    # --- gate 3 / LOW: git var ama çalışmıyor, XDG ile ilgisiz -----------------------------------------------
    def test_git_calismiyor_xdg_ilgisizse_xdg_notu_basilmaz(self):
        bin_ = self.tmp / "_sahte_git"
        bin_.mkdir()
        shutil.copy(SYS32 / "where.exe", bin_ / "git.exe")  # `git --version` rc 1 veren, git olmayan bir exe
        # Gerçek Git ne kayıttaki PATH'ten (tazeleme) ne bilinen klasörlerden gelsin: aday YALNIZ sahte git.exe.
        self.path_kaydi(str(Path(sys.executable).parent), "", git=False)
        env = self.path_degistir(self.env, os.pathsep.join([str(bin_), str(Path(sys.executable).parent), str(SYS32),
                                                            str(POWERSHELL.parent)]))
        env = self.bos_program_files(env)
        self.assertTrue(env.get("XDG_CONFIG_HOME"))  # XDG tanımlı ve geçerli: XDG notu yine de basılmamalı
        r = self.kur("-DenemeModu", env=env)
        c = self.cikti(r)
        self.assertEqual(r.returncode, 2, c)
        self.assertIn("git çalıştırılamadı", c)
        self.assertIn(str(bin_ / "git.exe"), c)
        self.assertIn("çıkış kodu 1", c)
        self.assertNotIn("XDG_CONFIG_HOME", c)
        self.assertNotIn("yeniden kurmak", c)
        self.assertNotIn("EKSİK: Git bulunamadı", c)
        self.assertFalse(self.hedef.exists())

    # --- gate 3 / LOW: Config-Girisleri tablosu (fonksiyon AST'den çıkarılır, betik çalışmaz) --------------------
    def test_config_girisleri_tablosu(self):
        up = self.tmp / "_userprofile"
        up.mkdir()
        tablo = [  # (ad, bayat kök, aktif klon, config, beklenen girişler)
            ("ata kök aktif klonu listelemez", r"C:\Users\u", r"C:\Users\u\axet",
             {"options": {"context_paths": ["C:/Users/u/core/00-temel.md", "C:/Users/u/axet/core/00-temel.md"]}},
             ["options.context_paths: C:/Users/u/core/00-temel.md"]),
            ("sürücü kökü aktif klonu listelemez", "C:\\", r"C:\axet",
             {"options": {"context_paths": ["C:/core/00-temel.md", "C:/axet/core/00-temel.md"], "skills_paths": ["C:/axet/skills"]},
              "permissions": {"rules": {"edit": {"C:/core/*": "deny", "C:/axet/core/*": "deny"}}}},
             ["options.context_paths: C:/core/00-temel.md", "permissions.rules.edit: C:/core/*"]),
            ("nokta-nokta normalize", r"C:\old", r"C:\yeni",
             {"options": {"context_paths": ["C:/x/../old/core/00-temel.md"]}},
             ["options.context_paths: C:/x/../old/core/00-temel.md"]),
            ("tilde açılır", str(up / "old"), r"C:\yeni",
             {"options": {"context_paths": ["~/old/core/00-temel.md"]}},
             ["options.context_paths: ~/old/core/00-temel.md"]),
            ("bozuk tipler okunamadı demez", r"C:\old", r"C:\yeni", {"options": ["x"], "permissions": {"rules": None}}, []),
            # kontrol grubu: önceki kodda da doğru olanlar
            ("önek axet/axet2 karışmaz", r"C:\axet", r"C:\yeni",
             {"options": {"context_paths": ["C:/axet2/core/00-temel.md", "C:/axet/core/00-temel.md"]}},
             ["options.context_paths: C:/axet/core/00-temel.md"]),
            ("harf + ters bölü + sondaki ayraç", "C:\\axet\\", r"C:\yeni",
             {"options": {"skills_paths": ["c:\\AXET\\skills\\"]}, "permissions": {"rules": {"edit": {"C:/Axet/core/*": "deny"}}}},
             ["options.skills_paths: c:\\AXET\\skills\\", "permissions.rules.edit: C:/Axet/core/*"]),
            # Ad bilerek YER TUTUCUDUR (gerçek bir kişi adı değil): bu dosya public yayın paketine girer ve
            # yayın öncesi sızıntı taramasından geçer — gerçek kullanıcı adı BLOCKER'dır. Türkçe karakterler
            # testin ÖLÇTÜĞÜ şeydir (ASCII dışı yol), o yüzden korunur.
            ("ASCII dışı", r"C:\Users\ÖRNEK\İş", r"C:\yeni",
             {"options": {"context_paths": ["C:/Users/ÖRNEK/İş/core/00-temel.md"]}},
             ["options.context_paths: C:/Users/ÖRNEK/İş/core/00-temel.md"]),
        ]
        vakalar = []
        for i, (ad, kok, aktif, cfg, _) in enumerate(tablo):
            xdg = self.tmp / f"_xdg_tablo{i}"
            self.yaz(xdg / "axet-code" / "axet-code.json", json.dumps(cfg, ensure_ascii=False))
            vakalar.append({"ad": ad, "kok": kok, "aktif": aktif, "xdg": str(xdg)})
        vaka_dosyasi = self.yaz(self.tmp / "vakalar.json", json.dumps(vakalar, ensure_ascii=False))
        surucu = self.yaz(self.tmp / "surucu.ps1", "\r\n".join([
            "param([string]$Kur, [string]$Vakalar, [string]$Py)",
            "$ErrorActionPreference = 'Continue'",
            "[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false",
            "$env:PYTHONUTF8 = '1'",
            "$ast = [System.Management.Automation.Language.Parser]::ParseFile($Kur, [ref]$null, [ref]$null)",
            "$fonk = $ast.FindAll({ param($a) $a -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $true) |",
            "    Where-Object { $_.Name -in @('Son-Kod', 'Config-Yolu', 'Config-Girisleri') }",
            "foreach ($f in $fonk) { . ([scriptblock]::Create($f.Extent.Text)) }",
            "$script:PY = $Py",
            # Ölçüldü (PS 5.1): ConvertFrom-Json JSON dizisini boruda TEK nesne olarak akıtır; önce değişkene atanır.
            "$liste = Get-Content -LiteralPath $Vakalar -Raw -Encoding UTF8 | ConvertFrom-Json",
            "foreach ($v in $liste) {",
            "    $env:XDG_CONFIG_HOME = $v.xdg",
            "    foreach ($s in @(Config-Girisleri $v.kok $v.aktif)) { [Console]::Out.WriteLine(\"$($v.ad)|$s\") }",
            "    [Console]::Out.WriteLine(\"$($v.ad)|<son>\")",
            "}", ""]), newline="")
        env = dict(self.env, USERPROFILE=str(up))
        r = subprocess.run([str(POWERSHELL), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(surucu),
                            "-Kur", str(KUR_PS1), "-Vakalar", str(vaka_dosyasi), "-Py", sys.executable],
                           env=env, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           stdin=subprocess.DEVNULL, timeout=120)
        c = self.cikti(r)
        cikan: dict = {}
        for satir in r.stdout.splitlines():
            if "|" in satir:
                ad, deger = satir.split("|", 1)
                cikan.setdefault(ad, []).append(deger)
        for ad, _, _, _, beklenen in tablo:
            with self.subTest(ad):
                self.assertIn("<son>", cikan.get(ad, []), c)
                self.assertEqual(sorted(x for x in cikan[ad] if x != "<son>"), sorted(beklenen), c)

    # --- gate 2 / Y3: WindowsApps Store yönlendirmesi (bu makinedeki gerçek alias'lar) -------------------------
    def test_windowsapps_store_yonlendirmesi_python_secilmez(self):
        wa = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WindowsApps"
        stub = wa / "python.exe"
        if not stub.exists():
            self.skipTest("WindowsApps python.exe yok")
        k = subprocess.run([str(stub), "-c", "print(1)"], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60)
        if k.returncode == 0:
            self.skipTest("WindowsApps python.exe bu makinede gerçek bir yorumlayıcı (Store yönlendirmesi değil)")
        # kayıttaki PATH boş + ProgramFiles* boş: PATH tazeleme ve bilinen klasörler gerçek git'i getirmesin
        # (LOCALAPPDATA gerçek kalır: stub orada; oradaki gerçek Python bulunursa aşağıdaki dal onu kabul eder)
        self.path_kaydi("", "", git=False)
        env = self.path_degistir(self.env, os.pathsep.join([str(wa), str(SYS32), str(POWERSHELL.parent)]))
        env = self.bos_program_files(env)
        r = self.kur(env=env)  # git bulunmaz -> ön koşulda durur (2); -WingetKapali
        c = self.cikti(r)
        self.assertEqual(r.returncode, 2, c)
        secilen = re.search(r"OK Python: \S+ \((.+)\)", c)
        if secilen:  # py alias'ı gerçek yorumlayıcıya çıkabilir; seçilen yol stub OLMAMALI ve gerçek dosya olmalı
            yol = Path(secilen.group(1))
            self.assertNotEqual(os.path.normcase(str(yol)), os.path.normcase(str(stub)), c)
            self.assertTrue(yol.is_file() and yol.stat().st_size > 0, c)
        else:
            self.assertIn("EKSİK: Python 3.12 ya da üstü bulunamadı", c)
        self.assertNotIn("Python was not found", c.split("== 2/5")[0])

    # --- gate 2 / Y4: GitHub raw biçimi (BOM + LF) --------------------------------------------------------------
    def test_lf_satir_sonlu_bomlu_kopya_deneme_modu(self):
        kopya = self.tmp / "raw-lf" / "kur.ps1"
        kopya.parent.mkdir()
        ham = KUR_PS1.read_bytes().replace(b"\r\n", b"\n")
        kopya.write_bytes(ham)
        self.assertEqual(kopya.read_bytes()[:3], b"\xef\xbb\xbf")
        self.assertNotIn(b"\r", kopya.read_bytes())
        r = subprocess.run([str(POWERSHELL), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(kopya),
                            "-Kaynak", str(self.kaynak), "-Hedef", str(self.hedef), "-DenemeModu", "-WingetKapali"],
                           env=self.env, cwd=str(self.tmp), capture_output=True, text=True, encoding="utf-8",
                           errors="replace", stdin=subprocess.DEVNULL, timeout=300)
        c = self.cikti(r)
        self.assertEqual(r.returncode, 0, c)
        self.assertIn("DENEME MODU bitti", c)
        self.assertIn("Ön koşullar: aXet, Git, Python", c)
        self.assertIn("2/5 Git kimliği", c)
        for bozuk in ("ParserError", "Ã", "Ä", "\ufffd"):
            self.assertNotIn(bozuk, c)
        self.assertFalse(self.hedef.exists())

    # --- gate 2 / Y5: göreli hedef ve dış catch ---------------------------------------------------------------
    def test_goreli_hedef_calisma_dizinine_gore_cozulur(self):
        r = self.kur("-Kaynak", str(self.kaynak), "-Hedef", "goreli-klon", "-Evet", varsayilan=False)  # cwd = self.tmp
        c = self.cikti(r)
        self.assertEqual(r.returncode, 0, c)
        beklenen = self.tmp / "goreli-klon"
        self.assertIn(f"Klon   : {beklenen}", c)
        self.assertTrue((beklenen / ".git").is_dir(), c)
        self.assertIn((beklenen / "core" / "00-temel.md").as_posix(), self.cfg_oku()["options"]["context_paths"])
        r = self.kur("-Kaynak", str(self.kaynak), "-Hedef", "goreli-klon", "-Evet", varsayilan=False)
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("Config zaten bu klonu gösteriyor", self.cikti(r))

    def test_beklenmeyen_hata_dis_catch_cikis_1(self):
        # Ölçüldü: USERPROFILE ve XDG_CONFIG_HOME yokken Config-Yolu içindeki Join-Path sonlandırıcı hata verir.
        env = {k: v for k, v in self.env.items() if k.upper() not in ("USERPROFILE", "XDG_CONFIG_HOME")}
        r = self.kur("-DenemeModu", env=env)
        c = self.cikti(r)
        self.assertEqual(r.returncode, 1, c)
        self.assertIn("DURDU: beklenmeyen hata", c)
        self.assertIn("kur.ps1:", c)
        self.assertNotIn("DENEME MODU bitti", c)
        self.assertFalse(self.hedef.exists())

    # --- ön koşul eksik ---------------------------------------------------------------------------------------
    def test_axet_yoksa_durur_git_python_da_ayni_mesajda(self):
        """aXet yokken Git/Python'a da bakılır; eksiklerin HEPSİ tek mesajda (kullanıcı portaldan bir seferde kurar,
        dosyaya bir kez daha çift tıklar). Eskiden aXet yoksa hemen çıkılıyor, Git/Python ancak 2. denemede görülüyordu."""
        env, kayit = self.dar_ortam(axet=False)
        r = self.kur("-Evet", env=env, winget_kapali=False)
        c = self.cikti(r)
        self.assertEqual(r.returncode, 2, c)
        self.assertIn("şirket kanalından kurulur", c)
        self.assertIn("EKSİK: Git bulunamadı", c)  # aXet yokken de Git'e bakıldı
        self.assertIn("EKSİK: Python 3.12 ya da üstü bulunamadı", c)
        self.assertEqual(c.count("DURDU:"), 1, c)  # tek durdurma mesajı
        blok = c[c.index("DURDU:"):]
        for satir in ("    - aXet", "    - Git (Git for Windows)", "    - Python 3.12 ya da üstü"):
            self.assertIn(satir, blok)
        self.assertIn("Şirket portalından (Software Center / Company Portal) kur", blok)
        self.assertIn("bu dosyaya TEKRAR çift tıkla", blok)
        self.assertFalse(kayit.exists(), "winget çağrıldı")
        self.assertFalse(self.hedef.exists())

    def test_tek_eksik_varsa_yalniz_o_listelenir(self):
        # Kontrol grubu (tek mesaj testinin): aXet VAR → listede yalnız Git + Python; aXet satırı yok.
        env, _kayit = self.dar_ortam(axet=True)
        c = self.cikti(self.kur(env=env))
        blok = c[c.index("DURDU:"):]
        self.assertNotIn("    - aXet", blok)
        self.assertIn("    - Git (Git for Windows)", blok)
        self.assertIn("OK aXet:", c)

    def test_portaldan_yeni_kurulan_python_path_tazelemeyle_ayni_pencerede_gorulur(self):
        """Pencere Explorer'ın ESKİ PATH'iyle açıldı; Python portaldan az önce kuruldu ve yalnız KAYITTAKİ kullanıcı
        PATH'inde. kur.ps1 başta PATH'i kayıttan tazeler → Python aynı pencerede bulunur (kapat-aç gerekmez).
        Kontrol grubu: aynı ortam, kayıtta girdi yok → Python EKSİK (test_git_python_yok...)."""
        env, _ = self.sahte_python_ortami("3.12")
        sahte = next(Path(p) for p in self.path_oku(env).split(os.pathsep) if (Path(p) / "python.cmd").is_file())
        env = self.path_degistir(env, os.pathsep.join([str(SYS32), str(POWERSHELL.parent)]))  # PATH'ten çıkar
        self.path_kaydi("", str(sahte), git=False)
        env["AXET_KUR_PATH_KAYDI"] = self.env["AXET_KUR_PATH_KAYDI"]
        c = self.cikti(self.kur(env=env))
        self.assertIn("PATH   : kayıttan tazelendi (1 yeni girdi", c)
        self.assertIn(f"OK Python: 3.12 ({sahte / 'python.cmd'})", c)
        self.assertNotIn("EKSİK: Python", c)

    def test_python_kayit_defterinden_bulunur_path_disinda(self):
        """PEP 514 kaydı (sahte: AXET_KUR_PATH_KAYDI python_kayit): portal Python'u PATH'e koymadıysa da bulunur.
        3.11 kaydı sürüm kapısında elenir, 3.12 seçilir (sıra: kayıt sürümü büyükten küçüğe DEĞİL, dizi sırası —
        sahte kayıt gerçek kaydın sıralanmış çıktısının yerine geçer)."""
        env, _ = self.sahte_python_ortami("3.12")
        sahte = next(Path(p) / "python.cmd" for p in self.path_oku(env).split(os.pathsep) if (Path(p) / "python.cmd").is_file())
        eski = self.eski_python_dizini("3.11") / "python.cmd"
        env = self.path_degistir(env, os.pathsep.join([str(SYS32), str(POWERSHELL.parent)]))
        for kayit, beklenen in (([str(eski), str(sahte)], f"OK Python: 3.12 ({sahte})"), ([], "EKSİK: Python")):
            with self.subTest(kayit=kayit):
                self.path_kaydi("", "", git=False, python_kayit=kayit)
                env["AXET_KUR_PATH_KAYDI"] = self.env["AXET_KUR_PATH_KAYDI"]
                c = self.cikti(self.kur(env=env))
                self.assertIn(beklenen, c)

    def test_python_bilinen_klasorde_varsayilanda_bulunur(self):
        """%LOCALAPPDATA%\\Programs\\Python\\Python3*\\python.exe winget'e bağlı olmadan taranır. Gerçek bir python.exe
        gerekir (adı python.exe olmalı): venv başlatıcısı + pyvenv.cfg klasöre kopyalanır (ölçüldü: sys.executable
        kopyanın yolu, taban gerçek kurulum). Kontrol grubu: klasör boşken Python EKSİK."""
        env, _kayit = self.dar_ortam(axet=True)
        lad = Path(env["LOCALAPPDATA"])
        hedef = lad / "Programs" / "Python" / "Python312"
        c = self.cikti(self.kur(env=env))
        self.assertIn("EKSİK: Python 3.12 ya da üstü bulunamadı", c)  # kontrol grubu
        v = self.tmp / "_venv_bilinen"
        r = subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(v)], capture_output=True, text=True,
                           stdin=subprocess.DEVNULL, timeout=300)
        self.assertEqual(r.returncode, 0, r.stderr)
        hedef.mkdir(parents=True)
        shutil.copy2(v / "Scripts" / "python.exe", hedef / "python.exe")
        shutil.copy2(v / "pyvenv.cfg", hedef / "pyvenv.cfg")
        c = self.cikti(self.kur(env=env))
        self.assertIn(f"OK Python: {sys.version_info.major}.{sys.version_info.minor} ({hedef / 'python.exe'})", c)

    # --- Z80: şirket ortamı — winget varsayılanda KAPALI, yalnız -Winget ile ----------------------------------------
    # Neden (ölçülmüş vaka, 2026-09-23): kullanıcı "E" deyince winget izinsiz bir Git'i kullanıcı klasörüne kurdu;
    # şirket yazılım merkezinden kurulan izinli Git ile yan yana kaldı. Varsayılan artık hiç sormaz, hiç çağırmaz.
    def test_git_python_yok_varsayilanda_winget_sorulmaz_yazilim_merkezi_denir(self):
        env, kayit = self.dar_ortam(axet=True)
        # -Evet bile winget'i açmaz: soru hiç sorulmadığı için "evet" diyecek bir şey yok
        r = self.kur("-Evet", env=env, winget_kapali=False)
        c = self.cikti(r)
        self.assertEqual(r.returncode, 2, c)
        self.assertNotIn("OK Python", c)  # 0 baytlık sahte python.exe/python3.exe aday olarak elendi
        self.assertIn("EKSİK: Git bulunamadı", c)
        self.assertIn("EKSİK: Python 3.12 ya da üstü bulunamadı", c)
        blok = c[c.index("DURDU:"):]
        self.assertIn("Şirket portalından (Software Center / Company Portal) kur", blok)
        self.assertIn("    - Git (Git for Windows)", blok)
        self.assertIn("    - Python 3.12 ya da üstü", blok)
        self.assertIn("bu dosyaya TEKRAR çift tıkla", blok)
        self.assertNotIn("PowerShell aç", c)  # kullanıcıya terminal komutu/terminal açma talimatı yok
        self.assertIn("https://git-scm.com/download/win", c)
        self.assertIn("https://www.python.org/downloads/windows/", c)
        self.assertNotIn("winget ile kurayım mı", c)
        self.assertNotIn("winget install", c)  # varsayılanda winget komutu önerilmez de
        self.assertFalse(kayit.exists(), "winget varsayılanda çağrıldı")
        self.assertFalse(self.hedef.exists())
        self.assertFalse(self.cfg.exists())

    def test_winget_anahtari_ile_soru_sorulur_kapali_stdin_cagrilmaz(self):
        """-Winget eski soran akışı açar (kur.cmd anahtarı aynen geçirir: kur() kur.cmd üzerinden çağırır)."""
        env, kayit = self.dar_ortam(axet=True)
        r = self.kur("-Winget", env=env, winget_kapali=False)
        c = self.cikti(r)
        self.assertEqual(r.returncode, 2, c)
        # Soru metni Read-Host isteminde (host'a) yazılır, stdout'a düşmez: sorulduğunun izi kapalı girişin yanıtıdır.
        self.assertIn("giriş kapalı -> hayır", c)
        self.assertIn("Git kurulmadı. Elle kurmak için", c)
        self.assertIn("winget install --id Git.Git -e", c)  # -Winget ile tarif winget satırını da taşır
        self.assertIn("https://git-scm.com/download/win", c)
        self.assertIn("https://www.python.org/downloads/windows/", c)
        self.assertNotIn("Software Center", c)
        self.assertFalse(kayit.exists(), "winget soru onaylanmadan çağrıldı")
        self.assertFalse(self.hedef.exists())

    def test_winget_ve_wingetkapali_birlikte_winget_cagrilmaz(self):
        env, kayit = self.dar_ortam(axet=True)
        r = self.kur("-Winget", "-Evet", env=env, winget_kapali=True)
        c = self.cikti(r)
        self.assertEqual(r.returncode, 2, c)
        self.assertNotIn("winget ile kurayım mı", c)
        self.assertIn("Git elle kurulmalı", c)
        self.assertFalse(kayit.exists(), "-WingetKapali varken winget çağrıldı")

    def test_kur_disi_yardim_metinleri_winget_onermez(self):
        """Aynı politika kur.ps1 dışındaki yardım metinlerinde: dört dosyanın hiçbiri winget komutu önermez ve rg için
        HİÇBİR kurulum yolu göstermez (kullanıcı kararı 2026-09-24: ek uygulama önerilmez; install.py rg yokken yalnız
        bilgi satırı basar). Python eksik mesajının yazılım merkezini gösterdiği YALNIZ iki .cmd'de ölçülür;
        install.py/doctor.py için bu iddia ölçülmez. Kapsam: yalnız bu dört dosyanın metni (çalıştırılmaz)."""
        for yol in ("yeni-proje.cmd", "proje-tamamla.cmd", "scripts/install.py", "scripts/doctor.py"):
            with self.subTest(yol=yol):
                metin = (AXET_HOME / yol).read_bytes().decode("utf-8")
                self.assertNotIn("winget install", metin)
                self.assertNotIn("ripgrep/releases", metin)
                if yol.endswith(".cmd"):
                    self.assertRegex(metin.lower(), r"yaz[iı]l[iı]m merkez")

    def test_eski_python_varsayilanda_winget_sorulmaz(self):
        env, _sahte = self.sahte_python_ortami("3.11")
        bin_, kayit = self.sahte_winget()
        env = self.path_degistir(env, str(bin_) + os.pathsep + self.path_oku(env))
        r = self.kur("-Evet", env=env, winget_kapali=False)
        c = self.cikti(r)
        self.assertEqual(r.returncode, 2, c)
        self.assertIn("bulundu ama 3.12 ya da üstü gerekli", c)
        # Z80 nit: eski sürüm KURULU iken "bulunamadı" denmez — yetersiz sürüm ve bulunan sürüm söylenir.
        # Kontrol grubu (Python hiç yok → "bulunamadı"): test_git_python_yok_varsayilanda_winget_sorulmaz_yazilim_merkezi_denir.
        self.assertIn("EKSİK: Python sürümü yetersiz (bulunan 3.11", c)
        self.assertIn("    - Python 3.12 ya da üstü (bulunan 3.11, eski)", c[c.index("DURDU:"):])
        self.assertNotIn("Python bulunamadı", c)
        self.assertNotIn("Python 3.12 ya da üstü bulunamadı", c)
        self.assertNotIn("winget ile kurayım mı", c)
        self.assertFalse(kayit.exists(), "winget varsayılanda çağrıldı")

    def test_deneme_modu_git_yok_winget_kullanilmaz_der(self):
        env, kayit = self.dar_ortam(axet=True)
        r = self.kur("-DenemeModu", env=env, winget_kapali=False)
        c = self.cikti(r)
        self.assertEqual(r.returncode, 2, c)
        self.assertIn("[deneme] Eksik ön koşul var", c)
        self.assertIn("    - Git (Git for Windows)", c)
        self.assertNotIn("önerilecekti (sorarak)", c)
        self.assertNotIn("winget", c)  # varsayılanda winget ne anılır ne çağrılır
        # kontrol grubu: -Winget ile deneme modu eski planı anlatır
        r = self.kur("-DenemeModu", "-Winget", env=env, winget_kapali=False)
        c = self.cikti(r)
        self.assertEqual(r.returncode, 2, c)
        self.assertIn("winget install --id Git.Git -e önerilecekti (sorarak)", c)
        self.assertFalse(kayit.exists(), "deneme modunda winget çağrıldı")

    def test_rg_yok_varsayilanda_winget_sorulmaz_kurulum_surer(self):
        # PATH = sahte winget + gerçek PATH'in rg İÇERMEYEN klasörleri (git/python/klon için gerekenler kalır).
        # Ölçüldü: yalnız git.exe'nin klasörü (mingw64in) bırakılınca yerel `git clone` başarısız oluyor.
        bin_, kayit = self.sahte_winget()
        rg_adlari = ("rg.exe", "rg.cmd", "rg.bat", "rg.ps1")
        temiz = [d for d in self.path_oku(self.env).split(os.pathsep)
                 if d and not any((Path(d) / a).exists() for a in rg_adlari)]
        env = self.path_degistir(self.env, os.pathsep.join([str(bin_)] + temiz))
        kontrol = subprocess.run([str(POWERSHELL), "-NoProfile", "-Command",
                                  "if (Get-Command rg -ErrorAction SilentlyContinue) { exit 1 }"], env=env,
                                 capture_output=True, stdin=subprocess.DEVNULL, timeout=60)
        self.assertEqual(kontrol.returncode, 0, "ortamda rg hâlâ bulunuyor — test rg'siz yolu sınamıyor")
        r = self.kur("-Evet", env=env, winget_kapali=False)
        c = self.cikti(r)
        self.assertIn("rg yok (isteğe bağlı; atlandı)", c)
        # yalnız bilgi: kullanıcıdan kurması İSTENMEZ (ne portal ne adres ne winget). Kapsam: kur.ps1'in kendi ön koşul
        # bölümü. Aynı pencerede koşan install.py/doctor bu testte KAYNAK klonun (bare = commit'lenmiş HEAD) sürümüdür;
        # onların rg satırı (yalnız bilgi, öneri/adres yok) test_install.OrtamRgBilgiTest + test_doctor'da ölçülür.
        onkosul = c.split("== 1/5")[1].split("== 2/5")[0]
        self.assertNotIn("yazılım merkez", onkosul)
        self.assertNotIn("ripgrep", onkosul)
        self.assertNotIn("winget", c)
        self.assertIn("== 4/5", c)  # kurulum durmadı
        self.assertIn("Kurulum TAMAM — aXet'i aç. (yeni klon)", c)
        self.assertFalse(kayit.exists(), "rg için winget varsayılanda çağrıldı")

    def test_asgari_python_surum_kapisi_karari(self):
        """Asgari sürüm kapısının KARARI (mesajı değil): 3.11 RED · 3.12 KABUL · 3.14 KABUL.

        Kontrol grubu ZORUNLU: yalnız "3.11 reddedildi"yi ölçmek yetmez — aday yanlış bir sebepten de (rc != 0,
        bildirilen yol diskte yok) elenmiş olabilirdi. 3.12/3.14 kolunun KABUL dönmesi, sahte yorumlayıcının
        gerçekten çalıştığının ve kararın asgari sürüm karşılaştırmasında verildiğinin kanıtıdır.
        Neden var: mutasyon denetimi Z6/B1 — karşılaştırma `if ($false)` yapıldığında (= 3.12 kapısı tümüyle
        kaldırıldığında) takımın tamamı yeşil kalıyordu; 3.12'yi anan iki test yalnız mesaj metnini ölçüyor ve
        girdileri (0 baytlık sahte, Store yönlendirmesi) karşılaştırmaya hiç ULAŞMIYORDU.

        KAPSAM — bakılmayanlar: py launcher (`py -0p`) listesindeki ön eleme · `-BilinenYerler` taraması ·
        3.12'nin altındaki GERÇEK bir yorumlayıcının install.py'de nasıl davranacağı (burada Git eksik olduğu
        için 2. adımda durulur, sahte yorumlayıcı hiç çalıştırılmaz)."""
        for surum, kabul in (("3.11", False), ("3.12", True), ("3.14", True)):
            with self.subTest(surum=surum, kabul=kabul):
                env, sahte = self.sahte_python_ortami(surum)
                r = self.kur(env=env)  # git PATH'te yok -> her iki kolda da 2. adımda durulur
                c = self.cikti(r)
                self.assertEqual(r.returncode, 2, c)
                self.assertIn("EKSİK: Git bulunamadı", c)  # kontrol: durma sebebi git; Python kararı ayrıca ölçülür
                if kabul:
                    self.assertIn(f"OK Python: {surum} ({sahte})", c)
                    self.assertNotIn("ya da üstü gerekli", c)
                    self.assertNotIn("EKSİK: Python", c)
                else:
                    self.assertIn(f"Python {surum} bulundu ama 3.12 ya da üstü gerekli: {sahte}", c)
                    self.assertIn(f"EKSİK: Python sürümü yetersiz (bulunan {surum};", c)  # Z80 nit: "bulunamadı" değil
                    self.assertNotIn("OK Python", c)
                self.assertFalse(self.hedef.exists(), c)

    def test_py_launcher_listesinden_yorumlayici_secilir(self):
        """py launcher kolu (İKİNCİ asgari sürüm karşılaştırması) gerçekten koşar ve adayı SEÇER.

        Neden var: mutasyon denetimi Z6/B1 yalnız `Python-Dene` içindeki kapıya baktı; aynı karşılaştırma py
        launcher kolunda da var ve kaynak taramasına göre o kolu HİÇBİR test koşturmuyordu (PATH'i değiştiren
        testlerin tümü ya çalışan bir python'u PATH'te bırakıyor ya da py'yi dışarıda bırakıyor). Bu test o
        kolu koşturur: listedeki aday denenmez olursa `py -3` yedeğine düşülür, sahte py orada rc=1 verir ve
        sonuç "bulunamadı"ya döner — yani kol mutasyona karşı ölçülür hâle gelir.

        KAPSAM — bakılmayanlar: bu koldaki REDDETME tarafı ÖLÇÜLEMEDİ (regex yalnız gerçek bir `.exe` yolunu
        kabul eder, bu makinede 3.12'nin ALTINDA gerçek yorumlayıcı yok: `py -0p` tek satır, 3.12) · birden çok
        adayın sıralanması · `py -0p` çıktısındaki ASCII olmayan yollar (modül docstring'i bunu zaten yazar)."""
        if sys.version_info < (3, 12):
            self.skipTest("bu testi koşan yorumlayıcı 3.12'nin altında — kabul kolu ölçülemez")
        env, sahte_py, gercek = self.sahte_py_launcher_ortami()
        self.assertTrue(sahte_py.is_file())
        r = self.kur(env=env)  # git PATH'te yok -> 2. adımda durulur
        c = self.cikti(r)
        self.assertEqual(r.returncode, 2, c)
        self.assertIn("EKSİK: Git bulunamadı", c)
        self.assertIn(f"OK Python: {sys.version_info.major}.{sys.version_info.minor} ({gercek})", c)
        self.assertNotIn("EKSİK: Python", c)
        self.assertFalse(self.hedef.exists(), c)

    def test_winget_hata_verirse_tarif_basar_durur(self):
        env, kayit = self.dar_ortam(axet=True)
        r = self.kur("-Evet", "-Winget", env=env, winget_kapali=False)
        c = self.cikti(r)
        self.assertEqual(r.returncode, 2, c)
        cagrilar = kayit.read_text(encoding="ascii", errors="replace")
        self.assertIn("Git.Git", cagrilar)
        # ⛔ Kurucu OLCULEN surumu kurar: CI 2026-09-20'de yalniz 3.12 kosmaya daraltildi;
        # 3.14 kuran bir kurucu her yeni kullaniciyi olculmemis kola sokardi.
        self.assertIn("Python.Python.3.12", cagrilar)
        self.assertNotIn("Python.Python.3.14", cagrilar,
                         "kurucu artik olculmeyen bir surumu kurmamali")
        self.assertIn("winget Git kurulumunda hata verdi", c)
        self.assertIn("https://www.python.org/downloads/windows/", c)
        self.assertFalse(self.hedef.exists())

    # --- aXet-Kur.cmd çıkış 2: dört üretici, tek son mesaj (bug gate 2026-09-24, MEDIUM) ---------------------------
    def axet_kur_cmd(self, *args: str, env: dict, lf: bool) -> subprocess.CompletedProcess:
        """Çift tıklamalık aXet-Kur.cmd'yi GERÇEKTEN koşar: geçici kopyada yalnız indirme adresi bu klonun kur.ps1'ine
        (file:// — Invoke-WebRequest PS 5.1'de okur, ölçüldü) çevrilir; geri kalan satırlar, çıkış kodu eşlemesi ve
        etiketler aynen. lf=True: GitHub'dan indirilen kopya gibi LF satır sonlu (depoda blob LF'tir; .gitattributes
        eol=crlf yalnız checkout'u etkiler). TEMP geçici klasör: indirilen kur.ps1 oraya yazılır.

        Z121ⓕ (bug gate 274a2d0): cmd.exe LF'li dosyada etiketi 512 baytlık bloklar hâlinde arar ⇒ davranış etiketlerin
        BAYT OFSETİNE bağlıdır. Yerel adres gerçek adresten farklı uzunlukta olduğu için ofsetler kayıyordu; fark
        adres satırından ÖNCEKİ en uzun `rem` satırında dengelenir (yorum gövdesi aynı uzunlukta `x`'lerle yazılır)
        ve her etiketin ofsetinin gerçek dosyayla BİREBİR aynı olduğu assert edilir."""
        gercek = AXET_HOME.joinpath("aXet-Kur.cmd").read_bytes()
        adres = re.search(rb"https://raw\.githubusercontent\.com/\S+?/kur\.ps1", gercek).group(0)
        yerel = KUR_PS1.as_uri().encode("ascii")
        metin = gercek.replace(adres, yerel)
        fark = len(yerel) - len(adres)
        rem = max(re.finditer(rb"(?m)^rem [^\r\n]*", metin[:metin.index(yerel)]), key=lambda m: len(m.group(0)))
        govde = len(rem.group(0)) - len(b"rem ") - fark
        self.assertGreaterEqual(govde, 0, f"yerel adres {fark} bayt uzun; dengeleyecek rem satırı yetmiyor")
        metin = metin[:rem.start()] + b"rem " + b"x" * govde + metin[rem.end():]
        if lf:
            metin = metin.replace(b"\r\n", b"\n")
            gercek = gercek.replace(b"\r\n", b"\n")

        def etiketler(b: bytes) -> list[tuple[int, bytes]]:
            return [(m.start(), m.group(0)) for m in re.finditer(rb"(?m)^:\w+", b)]
        self.assertEqual(len(metin), len(gercek))
        self.assertTrue(etiketler(gercek))
        self.assertEqual(etiketler(metin), etiketler(gercek), "etiket bayt ofsetleri gerçek dosyadan kaydı")
        kopya = self.tmp / ("_axetkur_lf.cmd" if lf else "_axetkur_crlf.cmd")
        kopya.write_bytes(metin)
        temp = self.tmp / "_temp_axetkur"
        temp.mkdir(exist_ok=True)
        env = dict(env, TEMP=str(temp), TMP=str(temp))
        return subprocess.run([COMSPEC, "/c", "call", str(kopya), *args], env=env, cwd=str(self.tmp),
                              capture_output=True, text=True, encoding="utf-8", errors="replace",
                              stdin=subprocess.DEVNULL, timeout=600)

    def test_axet_kur_cmd_cikis_2_son_mesaji_dort_durumda_dogru(self):
        """kur.ps1 dört durumda çıkış 2 verir: ① portaldan kurulacak program eksik ② Git kurulu ama çalışmıyor
        ③ -Winget yolu ④ -Kaldir sırasında Python yok. aXet-Kur.cmd eskiden 2'yi koşulsuz "Eksik program var ... portaldan
        kurun" diye kapatıyordu: ②'de kullanıcıyı Git'i yeniden kurmaya yolluyordu (kur.ps1 "destek ekibine gönder" der).
        Karar: ayrı çıkış kodu DEĞİL, tarafsız son mesaj — ①+② aynı koşumda birlikte olabilir (tek kod ikisini birden
        doğru anlatamaz) ve ne yapılacağını kur.ps1 her durumda hemen yukarıda kendisi yazar. Ölçülen: GERÇEK cmd (LF
        kopya; ① ayrıca CRLF) + GERÇEK kur.ps1; her durumda kur.ps1'in kendi talimatı + cmd'nin tarafsız kapanışı."""
        env_portal, _ = self.dar_ortam(axet=False)
        # ② Git kurulu ama çalışmıyor: aday YALNIZ `--version`da rc 1 veren sahte git.exe; Python gerçek, aXet sahte
        bin_git = self.tmp / "_sahte_git"
        bin_git.mkdir()
        shutil.copy(SYS32 / "where.exe", bin_git / "git.exe")
        env_git = self.path_degistir(env_portal, os.pathsep.join([str(bin_git), str(Path(sys.executable).parent),
                                                                  str(SYS32), str(POWERSHELL.parent)]))
        lad_git = self.tmp / "_lad_git"
        (lad_git / "axet-code" / "bin").mkdir(parents=True)
        (lad_git / "axet-code" / "bin" / "axet-code.exe").write_bytes(b"")
        env_git["LOCALAPPDATA"] = str(lad_git)
        # ④ -Kaldir: hedef imzalı bir template klonu gibi görünür (Template-Eksikleri geçer), Python yok
        sahte_klon = self.tmp / "_sahte_klon"
        self.yaz(sahte_klon / "core" / "00-temel.md", "# aXet\nCORE-ID: AXET-CORE-0.0.0\n")
        self.yaz(sahte_klon / "scripts" / "install.py", "raise SystemExit('çalıştırılmamalı')\n")
        (sahte_klon / "skills-sap").mkdir()
        portal = "Şirket portalından (Software Center / Company Portal) kur:"
        durumlar = [  # (ad, argümanlar, ortam, kur.ps1'in kendi son talimatı, o durumda OLMAMASI gereken)
            ("eksik program", ["-Kaynak", str(self.kaynak), "-Hedef", str(self.hedef), "-Evet", "-WingetKapali"],
             env_portal, ["    - Git (Git for Windows)", "bu dosyaya TEKRAR çift tıkla"], []),
            ("git çalışmıyor", ["-Kaynak", str(self.kaynak), "-Hedef", str(self.hedef), "-Evet", "-WingetKapali"],
             env_git, ["Git kurulu ama çalışmıyor: bu ekranın görüntüsünü destek ekibine gönder.",
                       "DURDU: Ön koşul sorunu var (yukarıda)."], [portal]),
            ("winget", ["-Kaynak", str(self.kaynak), "-Hedef", str(self.hedef), "-Evet", "-Winget"],
             env_portal, ["DURDU: Eksik ön koşul var (yukarıda). Kurduktan sonra bu dosyaya TEKRAR çift tıkla."], [portal]),
            # Z121ⓕ: -Kaldir'da "TEKRAR çift tıkla" YANLIŞ olurdu — seçeneksiz çift tık KURULUMU başlatır.
            ("kaldır python yok", ["-Kaldir", "-Hedef", str(sahte_klon), "-WingetKapali"],
             env_portal, ["bulunamadı; kaldırma install.py ile yapılır.",
                          "kaldırmayı AYNI komutla (-Kaldir ile) yeniden çalıştır"], [portal, "== 1/5"]),
        ]
        kapanis = "Kurulum DURDU: on kosul sorunu var. Ne yapmaniz gerektigi hemen yukaridaki mesajda yazar."
        kaldir_kapanis = "Kaldirma DURDU: on kosul sorunu var. Ne yapmaniz gerektigi hemen yukaridaki mesajda yazar."
        for ad, args, env, kendi, yasak in durumlar:
            kaldirma = "-Kaldir" in args
            son_mesaj = kaldir_kapanis if kaldirma else kapanis
            for lf in ((True, False) if ad in ("eksik program", "kaldır python yok") else (True,)):
                with self.subTest(durum=ad, lf=lf):
                    r = self.axet_kur_cmd(*args, env=env, lf=lf)
                    c = self.cikti(r)
                    self.assertEqual(r.returncode, 2, c)  # cmd kur.ps1'in kodunu aynen döndürür
                    for s in kendi:
                        self.assertIn(s, c)
                    for s in yasak:
                        self.assertNotIn(s, c)
                    # son mesaj: cmd'nin kapanışı, kur.ps1'in talimatından SONRA; koşulsuz "portaldan kurun" yok
                    self.assertIn(son_mesaj, c)
                    self.assertLess(max(c.rindex(s) for s in kendi), c.index(son_mesaj), c)
                    self.assertNotIn("Eksik program var", c)
                    son = c[c.index(son_mesaj):]
                    if kaldirma:
                        self.assertNotIn(kapanis, c)
                        self.assertIn("AYNI komutla (-Kaldir ile) tekrar calistirin", son)
                        self.assertIn("kaldirmayi degil KURULUMU baslatir", son)
                        self.assertNotIn("TEKRAR cift tiklayin", son)
                    else:
                        self.assertNotIn(kaldir_kapanis, c)
                        self.assertIn("Program eksik dediyse", son)  # portal yalnız koşullu anılır
                        self.assertIn("TEKRAR cift tiklayin", son)
                        self.assertIn("destek ekibine", son)
                    self.assertFalse(self.hedef.exists())

    # --- internet işareti (Zone.Identifier) -------------------------------------------------------------------
    def test_internet_isaretli_kopya_kur_cmd_ile_calisir(self):
        kopya = self.tmp / "indirilen"
        kopya.mkdir()
        for f in (KUR_CMD, KUR_PS1):
            shutil.copy2(f, kopya / f.name)
        with open(str(kopya / "kur.ps1") + ":Zone.Identifier", "w", encoding="ascii") as fh:
            fh.write("[ZoneTransfer]\r\nZoneId=3\r\n")
        politika = subprocess.run([str(POWERSHELL), "-NoProfile", "-Command", "Get-ExecutionPolicy"], capture_output=True,
                                  text=True, stdin=subprocess.DEVNULL, timeout=60).stdout.strip()
        arglar = ["-Kaynak", str(self.kaynak), "-Hedef", str(self.hedef), "-DenemeModu", "-WingetKapali"]
        if politika in ("RemoteSigned", "AllSigned"):
            duz = subprocess.run([str(POWERSHELL), "-NoProfile", "-File", str(kopya / "kur.ps1"), *arglar], env=self.env,
                                 capture_output=True, text=True, encoding="utf-8", errors="replace",
                                 stdin=subprocess.DEVNULL, timeout=120)
            self.assertNotEqual(duz.returncode, 0, self.cikti(duz))
            self.assertNotIn("DENEME MODU bitti", self.cikti(duz))
        r = subprocess.run([COMSPEC, "/c", "call", str(kopya / "kur.cmd"), *arglar], env=self.env, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=300)
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("DENEME MODU bitti", self.cikti(r))

    # --- -Sifirla (TASARIM §10) --------------------------------------------------------------------------------
    def _agac(self, kok: Path) -> dict:
        """Klasördeki dosyaların içerik özeti; `.git` HARİÇ (git kendi iç dosyalarını okuma sırasında da tazeler)."""
        sonuc = {}
        for p in sorted(kok.rglob("*")):
            g = p.relative_to(kok)
            if ".git" in g.parts or not p.is_file():
                continue
            sonuc[str(g)] = hashlib.sha256(p.read_bytes()).hexdigest()
        return sonuc

    def sifirla_klonu(self) -> None:
        """hedef = kaynak bare'in `main` dalını izleyen TEMİZ klon (gerçek tüketici klonunun şekli).

        kur.cmd ile değil doğrudan git ile klonlanır: her senaryoya ikinci bir tam kurulum koşumu (klon+install+doctor)
        eklenmesin. Çalışma ağacındaki `.gitignore` klona taşınır: `.axet-guncelleme/` kuralı henüz commit'lenmemiş
        olabilir ve iki senaryo (gitignore'lu dosya korunur · `.axet-guncelleme` yedekte) tam olarak onu ölçer."""
        self.git(self.kaynak, "update-ref", "refs/heads/main", "HEAD")
        self.git(self.kaynak, "symbolic-ref", "HEAD", "refs/heads/main")
        self.git(self.tmp, "clone", "-q", "-b", "main", str(self.kaynak), str(self.hedef))
        shutil.copy2(AXET_HOME / ".gitignore", self.hedef / ".gitignore")
        if self.git(self.hedef, "status", "--porcelain", "--", ".gitignore").stdout.strip():
            self.git(self.hedef, "add", ".gitignore")
            self.git(self.hedef, "commit", "-q", "-m", "test: calisma agacindaki .gitignore")
            self.git(self.hedef, "push", "-q", "origin", "main")
        self.assertEqual(self.git(self.hedef, "status", "--porcelain").stdout.strip(), "")

    def yedek_dallari(self) -> list:
        r = self.git(self.hedef, "for-each-ref", "--format=%(refname:short)", "refs/heads/yedek")
        return [s.strip() for s in r.stdout.splitlines() if s.strip()]

    def tek_yedek(self) -> str:
        d = self.yedek_dallari()
        self.assertEqual(len(d), 1, f"tam bir yedek dalı bekleniyordu, bulunan: {d}")
        return d[0]

    def yedekte(self, dal: str, yol: str) -> str:
        return self.git(self.hedef, "show", f"{dal}:{yol}").stdout

    # 1/12 izlenen değişiklik
    def test_sifirla_izlenen_degisiklik_geri_alinir_yedekte_kalir(self):
        self.sifirla_klonu()
        readme = self.hedef / "README.md"
        ozgun = readme.read_bytes()
        readme.write_bytes(ozgun + b"\nyerel not\n")
        r = self.kur("-Sifirla", "-Evet")
        c = self.cikti(r)
        self.assertEqual(r.returncode, 0, c)
        self.assertEqual(readme.read_bytes(), ozgun)
        self.assertEqual(self.git(self.hedef, "status", "--porcelain").stdout.strip(), "")
        dal = self.tek_yedek()
        self.assertIn(dal, c)
        self.assertIn("yerel not", self.yedekte(dal, "README.md"))

    # 2/12 izlenmeyen dosya
    def test_sifirla_izlenmeyen_dosya_silinir_yedekte_kalir(self):
        self.sifirla_klonu()
        self.yaz(self.hedef / "notlarim" / "benim.txt", "kullanıcı notu\n")
        # Boş klasör `clean -fd`'yi YALITARAK ölçer: git boş klasörü izlemez, bu yüzden yedek commit'ine giremez ve
        # dal değişiminde de silinmez; onu yalnız `clean -fd` kaldırır. (Ölçüldü 2026-09-15: yalnız dosyayla yazılan
        # bu senaryo `clean -fd` satırı tamamen kaldırıldığında da GEÇİYORDU — dosyayı zaten `switch` siliyor.)
        (self.hedef / "bos-klasor").mkdir()
        r = self.kur("-Sifirla", "-Evet")
        c = self.cikti(r)
        self.assertEqual(r.returncode, 0, c)
        self.assertIn("benim.txt", c)  # 1. adım izlenmeyenleri de gösterdi
        self.assertFalse((self.hedef / "notlarim").exists())
        self.assertFalse((self.hedef / "bos-klasor").exists(), "izlenmeyen boş klasör kaldı (clean -fd koşmadı)")
        self.assertIn("kullanıcı notu", self.yedekte(self.tek_yedek(), "notlarim/benim.txt"))

    # 3/12 yerel commit
    def test_sifirla_yerel_commit_geri_alinir_yedek_dalinda_kalir(self):
        self.sifirla_klonu()
        self.yaz(self.hedef / "YEREL.txt", "yerel commit\n")
        self.git(self.hedef, "add", "YEREL.txt")
        self.git(self.hedef, "commit", "-q", "-m", "yerel is")
        yerel_head = self.git(self.hedef, "rev-parse", "HEAD").stdout.strip()
        uzak = self.git(self.hedef, "rev-parse", "origin/main").stdout.strip()
        r = self.kur("-Sifirla", "-Evet")
        c = self.cikti(r)
        self.assertEqual(r.returncode, 0, c)
        self.assertIn("yerel is", c)  # 1. adım yerel commit'leri listeledi
        self.assertEqual(self.git(self.hedef, "rev-parse", "HEAD").stdout.strip(), uzak)
        self.assertFalse((self.hedef / "YEREL.txt").exists())
        self.assertEqual(self.git(self.hedef, "rev-parse", self.tek_yedek()).stdout.strip(), yerel_head)

    # 4/12 gitignore'lu dosya korunur (clean -fd, -x YOK)
    def test_sifirla_gitignorelu_dosya_korunur(self):
        self.sifirla_klonu()
        benim = self.yaz(self.hedef / "_lab" / "deneme.txt", "deneme alanı\n")
        self.assertEqual(self.git(self.hedef, "check-ignore", "-q", "_lab/deneme.txt", kontrol=False).returncode, 0,
                         "_lab/ .gitignore'da değil: senaryonun ön koşulu yok")
        r = self.kur("-Sifirla", "-Evet")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertTrue(benim.is_file(), "gitignore'lu dosya silindi (clean -fdx mi çalıştı?)")
        self.assertEqual(benim.read_text(encoding="utf-8"), "deneme alanı\n")

    # 5/12 .axet-guncelleme silinir ve yedekte var
    def test_sifirla_axet_guncelleme_silinir_ve_yedekte_var(self):
        self.sifirla_klonu()
        self.yaz(self.hedef / ".axet-guncelleme" / "uygulanan.json", '{"surum": 1}\n')
        self.assertEqual(self.git(self.hedef, "check-ignore", "-q", ".axet-guncelleme/uygulanan.json",
                                  kontrol=False).returncode, 0, ".axet-guncelleme/ .gitignore'da değil")
        r = self.kur("-Sifirla", "-Evet")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertFalse((self.hedef / ".axet-guncelleme").exists(), ".axet-guncelleme/ silinmedi")
        self.assertIn('"surum": 1', self.yedekte(self.tek_yedek(), ".axet-guncelleme/uygulanan.json"))

    # 6/12 onaysız -> dokunulmaz
    def test_sifirla_onaysiz_hicbir_seye_dokunmaz(self):
        self.sifirla_klonu()
        self.yaz(self.hedef / "benim.txt", "kullanıcı dosyası\n")
        readme = self.hedef / "README.md"
        readme.write_bytes(readme.read_bytes() + b"\nyerel not\n")
        once = self._agac(self.hedef)
        head = self.git(self.hedef, "rev-parse", "HEAD").stdout.strip()
        r = self.kur("-Sifirla")  # stdin kapalı, -Evet yok: SIFIRLA yazılamaz
        c = self.cikti(r)
        self.assertEqual(r.returncode, 1, c)
        self.assertIn("SIFIRLA", c)
        self.assertIn("iptal", c)
        self.assertEqual(self._agac(self.hedef), once)
        self.assertEqual(self.git(self.hedef, "rev-parse", "HEAD").stdout.strip(), head)
        self.assertEqual(self.yedek_dallari(), [])
        self.assertFalse(self.cfg.exists())

    # 7/12 -DenemeModu hiçbir şey yazmaz
    def test_sifirla_deneme_modu_hicbir_sey_yazmaz(self):
        self.sifirla_klonu()
        self.yaz(self.hedef / "benim.txt", "kullanıcı dosyası\n")
        once = self._agac(self.hedef)
        once_git = _goruntu(self.hedef / ".git")
        r = self.kur("-Sifirla", "-DenemeModu")
        c = self.cikti(r)
        self.assertEqual(r.returncode, 0, c)
        self.assertIn("DENEME MODU bitti", c)
        self.assertIn("benim.txt", c)  # 1. adım basıldı
        self.assertEqual(self._agac(self.hedef), once)
        self.assertEqual(_goruntu(self.hedef / ".git"), once_git)
        self.assertEqual(self.yedek_dallari(), [])
        self.assertFalse(self.cfg.exists())

    # 8/12 git kimliği tanımsız ortamda yedek commit'i
    def test_sifirla_git_kimligi_tanimsizken_yedek_commiti_atilir(self):
        self.sifirla_klonu()
        self.yaz(self.hedef / "benim.txt", "kullanıcı dosyası\n")
        env = dict(self.env)
        for k in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"):
            env.pop(k, None)
        r = self.kur("-Sifirla", "-Evet", env=env)
        c = self.cikti(r)
        self.assertEqual(r.returncode, 0, c)
        dal = self.tek_yedek()
        self.assertEqual(self.git(self.hedef, "log", "-1", "--format=%an <%ae>", dal).stdout.strip(),
                         "axet-yedek <yedek@yerel>")
        # Mesaj BİREBİR karşılaştırılır: PS 5.1 native argümanda hem Türkçe karakteri bozabilir (BOM'suz kopyada
        # ölçüldü: "sÄ±fÄ±rlama") hem de gömülü tırnakta argümanı bölebilir; gözle bakmak ikisini de kaçırır.
        self.assertEqual(self.git(self.hedef, "log", "-1", "--format=%s", dal).stdout.strip(),
                         "yedek: sıfırlama öncesi")
        self.assertIn("kullanıcı dosyası", self.yedekte(dal, "benim.txt"))

    # 9/12 pre-commit kancası tanımlıyken --no-verify
    def test_sifirla_kanca_tanimliyken_no_verify_ile_commitler(self):
        self.sifirla_klonu()
        kancalar = self.tmp / "_kancalar"
        isaret = self.tmp / "KANCA_CALISTI.txt"
        self.yaz(kancalar / "pre-commit", f'#!/bin/sh\necho calisti > "{isaret.as_posix()}"\nexit 1\n')
        self.git(self.hedef, "config", "core.hooksPath", kancalar.as_posix())
        self.yaz(self.hedef / "benim.txt", "kullanıcı dosyası\n")
        r = self.kur("-Sifirla", "-Evet")
        c = self.cikti(r)
        self.assertEqual(r.returncode, 0, c)
        self.assertIn("kullanıcı dosyası", self.yedekte(self.tek_yedek(), "benim.txt"))
        self.assertFalse(isaret.exists(), "pre-commit kancası çalıştı: --no-verify yok")

    # 10/12 klon dışı proje klasörü aynen kalır
    def test_sifirla_klon_disi_proje_klasoru_aynen_kalir(self):
        self.sifirla_klonu()
        proje = self.tmp / "musteri-projesi"
        self.yaz(proje / "AGENTS.md", "proje talimatı\n")
        self.yaz(proje / ".axet-code" / "durum.json", "{}\n")
        self.yaz(proje / ".axet-guncelleme" / "uygulanan.json", "{}\n")
        once = self._agac(proje)
        self.yaz(self.hedef / "benim.txt", "kullanıcı dosyası\n")
        # Klonun KENDİ .axet-guncelleme'si de kurulur: aynı adlı dizinin klon İÇİNDE gidip DIŞINDA kaldığı ölçülsün.
        # ⚠ Bu satır 5. adımdaki `Remove-Item` bloğunu YALITMAZ: ölçüldü (2026-09-16), blok TAMAMEN silindiğinde bu test
        # yine YEŞİL kalıyor — klon içindeki dizini zaten 3. adımın `switch` + 5. adımın `reset --hard`'ı kaldırıyor.
        # (Eski yorum "silme yolu ancak böyle koşar" diyordu; ölçüm bunu çürüttü.) Emniyet ağını yalıtan test ayrıdır:
        # test_sifirla_axet_guncelleme_artigi_5_adimda_silinir.
        self.yaz(self.hedef / ".axet-guncelleme" / "uygulanan.json", "{}\n")
        r = self.kur("-Sifirla", "-Evet")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertFalse((self.hedef / ".axet-guncelleme").exists())  # klon içindeki silindi
        self.assertEqual(self._agac(proje), once)  # klon dışındaki (aynı adlı dizin dahil) duruyor

    # 11/12 yedek dalından tek dosya geri alma
    def test_sifirla_yedek_dalindan_tek_dosya_geri_alinir(self):
        self.sifirla_klonu()
        readme = self.hedef / "README.md"
        degisik = readme.read_bytes() + b"\nyerel not\n"
        readme.write_bytes(degisik)
        r = self.kur("-Sifirla", "-Evet")
        c = self.cikti(r)
        self.assertEqual(r.returncode, 0, c)
        dal = self.tek_yedek()
        self.assertIn(f"restore --source {dal} -- ", c)  # son mesajdaki komut
        self.assertNotIn(b"yerel not", readme.read_bytes(), "sıfırlama satırı geri almadı")
        self.git(self.hedef, "restore", "--source", dal, "--", "README.md")
        # Bayt karşılaştırması yapılmaz: `.gitattributes`'taki `* text=auto` yüzünden git checkout'ta satır sonunu
        # CRLF'ye çevirir, dosyanın özgün baytları birebir geri gelmez (ölçüldü). Geri gelen yedekteki İÇERİKTİR.
        self.assertIn(b"yerel not", readme.read_bytes())

    # 12/12 yabancı repoda DUR
    def test_sifirla_yabanci_repoda_durur(self):
        bare, isaret = self.yabanci_repo("yabanci-sifirla")
        self.git(self.tmp, "clone", "-q", str(bare), str(self.hedef))
        self.yaz(self.hedef / "benim.txt", "kullanıcı dosyası\n")
        head = self.git(self.hedef, "rev-parse", "HEAD").stdout.strip()
        r = self.kur("-Sifirla", "-Evet")
        c = self.cikti(r)
        self.assertEqual(r.returncode, 1, c)
        self.assertIn("template'inin klonu değil", c)
        self.assertEqual(self.git(self.hedef, "rev-parse", "HEAD").stdout.strip(), head)
        self.assertEqual((self.hedef / "benim.txt").read_text(encoding="utf-8"), "kullanıcı dosyası\n")
        self.assertEqual(self.yedek_dallari(), [])
        self.assertFalse(isaret.exists(), "yabancı install.py/doctor.py çalıştırıldı")
        self.assertFalse(self.cfg.exists())

    # --- bug gate turu: yedek bütünlüğü, ana dala dönüş, parametre çakışması -----------------------------------
    def ic_repo(self, ad: str, commitli: bool) -> Path:
        """Klonun İÇİNDE ayrı bir git deposu (gitlink adayı). commitli=False → hiç commit atılmamış depo."""
        d = self.hedef / ad
        d.mkdir(parents=True)
        self.git(d, "init", "-q", "-b", "main", ".")
        if commitli:
            self.yaz(d / "ic.txt", "iç proje dosyası\n")
            self.git(d, "add", "-A")
            self.git(d, "commit", "-q", "-m", "ic ilk")
        return d

    # 13: gömülü git reposu (commit'li) yedeğe alınır ve sıfırlama TAMAMLANIR — gate #M4'ün kalıcı tıkanması
    def test_sifirla_gomulu_git_reposu_yedege_alinir_ve_tamamlanir(self):
        self.sifirla_klonu()
        self.ic_repo("ic-proje", commitli=True)
        ic_dosya = self.hedef / "ic-proje" / "ic.txt"
        r = self.kur("-Sifirla", "-Evet")
        c = self.cikti(r)
        self.assertEqual(r.returncode, 0, c)  # `?? ic-proje/` ↔ ls-tree `ic-proje` normalize edilmezse burada rc 1
        dal = self.tek_yedek()
        # gitlink olarak yedekte: ls-tree modu 160000 (yalnız commit kimliği; iç deponun dosyaları kendi .git'inde)
        satir = self.git(self.hedef, "ls-tree", "-r", dal, "--", "ic-proje").stdout.strip()
        self.assertTrue(satir.startswith("160000 commit"), f"gitlink yedeğe alınmadı: {satir!r}")
        # İç depo YERİNDE KALIR: `git clean -fd` iç içe depoyu bilerek atlar (silmek `-ffd` isterdi ve o deponun
        # geçmişini de yok ederdi — ölçüldü git 2.55). Araç bunu susarak geçmez, kalanı adıyla bildirir.
        self.assertTrue(ic_dosya.is_file(), "iç git deposu silindi (clean -ffd mi çalıştı?)")
        self.assertIn("hâlâ", c)
        self.assertIn("ic-proje", c)

    # 14: yedeklenemeyen yol → 4. ADIM DUR; hiçbir şey silinmez (ağaç bit-bit aynı)
    def test_sifirla_yedeklenemeyen_yol_varsa_dogrulama_durdurur(self):
        self.sifirla_klonu()
        # Hiç commit'i olmayan gömülü depo: `git add -A` onu indekse alamaz ("does not have a commit checked out",
        # ölçüldü git 2.55) ⇒ 1. adımda görülen yol yedek ağacına giremez ⇒ 4. adım silmeye izin VERMEMELİ.
        self.ic_repo("ic-bos", commitli=False)
        self.yaz(self.hedef / "benim.txt", "kullanıcı dosyası\n")
        readme = self.hedef / "README.md"
        readme.write_bytes(readme.read_bytes() + b"\nyerel not\n")
        once = self._agac(self.hedef)
        r = self.kur("-Sifirla", "-Evet")
        c = self.cikti(r)
        self.assertEqual(r.returncode, 1, c)
        self.assertIn("4/7", c)
        self.assertIn("HİÇBİR ŞEY SİLİNMEDİ", c)
        self.assertIn("ic-bos", c)
        self.assertIn("kur.cmd -Sifirla komutunu tekrar", c)  # eyleme dönüştürülebilir mesaj
        self.assertIn("branch -D", c)                          # kalan yedek dalı için ne yapılacağı
        self.assertEqual(self._agac(self.hedef), once, "doğrulama geçmeden dosya değişti/silindi")
        # DUR anında klon YEDEK dalında değil ana dalda durur (3. adımın sonunda dönülür). Mesaj bunu söylemeli:
        # söylemezse kullanıcı kendini yedek dalında sanır (kur.ps1 başlığındaki eski yorum da öyle diyordu).
        self.assertEqual(self.git(self.hedef, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip(), "main")
        self.assertIn("Klon şu an main dalında", c)

    # 15: main olmayan daldan sıfırlama → klon main'e alınır ve upstream'i olur
    def test_sifirla_main_olmayan_daldan_main_e_doner_upstream_kurulur(self):
        self.sifirla_klonu()
        self.git(self.hedef, "switch", "-q", "-c", "benim-dalim")
        self.yaz(self.hedef / "YEREL.txt", "dal işi\n")
        self.git(self.hedef, "add", "YEREL.txt")
        self.git(self.hedef, "commit", "-q", "-m", "dal isi")
        self.git(self.hedef, "branch", "-D", "main")  # yerel main hiç yok: -Sifirla onu kurmalı
        r = self.kur("-Sifirla", "-Evet")
        c = self.cikti(r)
        self.assertEqual(r.returncode, 0, c)
        self.assertEqual(self.git(self.hedef, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip(), "main")
        self.assertEqual(self.git(self.hedef, "rev-parse", "--abbrev-ref", "@{u}").stdout.strip(), "origin/main")
        self.assertEqual(self.git(self.hedef, "rev-parse", "HEAD").stdout.strip(),
                         self.git(self.hedef, "rev-parse", "origin/main").stdout.strip())
        self.assertIn("benim-dalim", c)  # son mesaj eski dalı söylüyor
        self.assertIn("dal işi", self.yedekte(self.tek_yedek(), "YEREL.txt"))

    # 16: -Kaldir + -Sifirla birlikte → DURDU (hiçbir işlemden önce)
    def test_kaldir_ve_sifirla_birlikte_durur(self):
        self.sifirla_klonu()
        once = self._agac(self.hedef)
        r = self.kur("-Sifirla", "-Kaldir")
        c = self.cikti(r)
        self.assertEqual(r.returncode, 1, c)
        self.assertIn("birlikte kullanılamaz", c)
        self.assertEqual(self._agac(self.hedef), once)
        self.assertEqual(self.yedek_dallari(), [])
        self.assertFalse(self.cfg.exists())

    # 17: 5. adımdaki .axet-guncelleme/ silme bloğunu YALITAN test (M5 mutasyonu bunu KIRMIZI yapar)
    def test_sifirla_axet_guncelleme_artigi_5_adimda_silinir(self):
        """Emniyet ağı: dizinin izlenen dosyasını `switch`/`reset` kaldırsa bile git'in izleyemediği artık kalır.

        BOŞ alt klasör bu bloğu yalıtarak ölçer (ölçüldü 2026-09-16): git boş klasörü izlemez ⇒ yedek commit'ine
        girmez ⇒ dal değişimi/`reset --hard` onu kaldırmaz; `clean -fd` ise gitignore'lu `.axet-guncelleme/`'ye
        (-x YOK) hiç girmez. Geriye TEK mekanizma olarak 5. adımdaki `Remove-Item` kalır. Kontrol grubu: aynı
        senaryo boş klasörsüz kurulduğunda blok silinse bile test geçiyordu (test 10'daki nota bak)."""
        self.sifirla_klonu()
        self.yaz(self.hedef / ".axet-guncelleme" / "uygulanan.json", '{"surum": 1}\n')
        (self.hedef / ".axet-guncelleme" / "oneri").mkdir()  # boş: git izlemez
        r = self.kur("-Sifirla", "-Evet")
        c = self.cikti(r)
        self.assertEqual(r.returncode, 0, c)
        # ön koşul: dizin gerçekten yedeğe girdi (silme izni yalnız ölçülmüş yedekten doğar)
        self.assertIn('"surum": 1', self.yedekte(self.tek_yedek(), ".axet-guncelleme/uygulanan.json"))
        self.assertFalse((self.hedef / ".axet-guncelleme").exists(),
                         "5. adımdaki emniyet ağı koşmadı: gitignore'lu dizin artığı klonda kaldı\n" + c)

    # 18: yedeğe ALINAMAYAN .axet-guncelleme/ SİLİNMEZ (fail-safe) — akış durmaz, çıkış kodu 0 kalır
    def test_sifirla_yedeklenemeyen_axet_guncelleme_silinmez(self):
        """Ölçülmüş vaka (2026-09-16, bug gate): `.axet-guncelleme/` içinde commit'i olmayan gömülü bir depo varken
        `git add -f -- .axet-guncelleme` rc=128 ("does not have a commit checked out") ile düşüyor, hiçbir şey
        sahnelenmiyor. 4. adım bu yolu YAPISAL OLARAK göremez (`git status --porcelain` gitignore'lu yol basmaz) ⇒
        eskiden 5. adım dizini YEDEKSİZ siliyor ve araç rc=0 ile "hepsi yedekte" diyordu.

        Beklenen: silme ATLANIR, dizin diskte kalır, kullanıcıya adıyla söylenir; DUR verilmez (gömülü depo
        -Sifirla'yı kalıcı tıkamamalı) ve sıfırlamanın geri kalanı tamamlanır."""
        self.sifirla_klonu()
        durum_dizini = self.hedef / ".axet-guncelleme"
        veri = self.yaz(durum_dizini / "uygulanan.json", '{"surum": 1}\n')
        ic = durum_dizini / "ic-bos"
        ic.mkdir(parents=True)
        self.git(ic, "init", "-q", "-b", "main", ".")  # hiç commit YOK: `add -f` bunu indeksleyemez
        readme = self.hedef / "README.md"
        ozgun = readme.read_bytes()
        readme.write_bytes(ozgun + b"\nyerel not\n")
        r = self.kur("-Sifirla", "-Evet")
        c = self.cikti(r)
        self.assertEqual(r.returncode, 0, c)
        # ön koşul kanıtı: add -f gerçekten düştü (3. adım uyarısı) — senaryo ölçmek istediği yolu koştu
        self.assertIn("git add -f düştü", c)
        # 1. fail-safe: dizin ve içindeki gömülü depo YERİNDE
        self.assertTrue(veri.is_file(), "yedeklenemeyen .axet-guncelleme/ silindi (veri kaybı)\n" + c)
        self.assertEqual(veri.read_text(encoding="utf-8"), '{"surum": 1}\n')
        self.assertTrue((ic / ".git").is_dir(), "gömülü deponun .git'i silindi\n" + c)
        # 2. yedekte olmadığı ölçülür (silmeme kararının dayanağı)
        dal = self.tek_yedek()
        self.assertEqual(self.git(self.hedef, "ls-tree", "-r", "--name-only", dal, "--",
                                  ".axet-guncelleme").stdout.strip(), "")
        # 3. kullanıcıya ADIYLA söylendi
        self.assertIn(str(durum_dizini), c)
        self.assertIn("SİLİNMEDİ", c)
        # 4. akış DURMADI: sıfırlamanın geri kalanı tamamlandı (izlenen değişiklik geri alındı, kurulum bitti)
        self.assertEqual(readme.read_bytes(), ozgun)
        self.assertIn("yerel not", self.yedekte(dal, "README.md"))

    # 19: .axet-guncelleme/ içinde COMMIT'Lİ gömülü depo → yedeğe yalnız gitlink girer ⇒ dizin SİLİNMEZ
    def test_sifirla_axet_guncelleme_icindeki_commitli_gomulu_depo_silinmez(self):
        """Vaka A — test 18'in (vaka C) açık kalan yarısı. Fark TEK bir ayrıntıda: iç deponun commit'i VAR.

        Ölçüldü (2026-09-16, git 2.55.0.windows.3): commit'i olan gömülü depoda `git add -f -- .axet-guncelleme`
        rc=0 döner (yalnız "warning: adding embedded git repository") ve sahneye SADECE bir gitlink koyar:
        `160000 commit <sha>`. İç deponun dosyaları ve NESNELERİ dış depoya hiç girmez. `ls-tree --name-only`
        çıktısında bu girdi düz bir dosyadan ayırt edilemediği için yol "yedekte" sanılıyor, 5. adım dizini
        siliyor ve iç deponun çalışma ağacı + `.git`'i + tüm geçmişi gidiyordu; yedek dalında yalnız hiçbir
        nesnesi bulunmayan 40 baytlık commit kimliği kalıyordu ⇒ GERİ ALINAMAZ veri kaybı, üstelik rc=0 ile
        sessiz (vaka C'nin ATLANDI satırı basılmıyor, çünkü `add -f` düşmüyor).

        Beklenen: vaka C ile AYNI güvenli yol — dizin olduğu gibi bırakılır, adıyla bildirilir, rc=0 kalır
        (gömülü depo -Sifirla'yı kalıcı tıkamamalı). Vaka B'nin (düz dosya → silinir + yedekten geri alınır)
        kontrol grubu olarak testleri: test 5 (test_sifirla_axet_guncelleme_silinir_ve_yedekte_var) ve
        test 17 (test_sifirla_axet_guncelleme_artigi_5_adimda_silinir)."""
        self.sifirla_klonu()
        durum_dizini = self.hedef / ".axet-guncelleme"
        veri = self.yaz(durum_dizini / "uygulanan.json", '{"surum": 1}\n')
        ic = durum_dizini / "ic-repo"
        ic.mkdir(parents=True)
        self.git(ic, "init", "-q", "-b", "main", ".")
        ic_dosya = self.yaz(ic / "ic.txt", "iç depo dosyası\n")
        self.git(ic, "add", "-A")
        self.git(ic, "commit", "-q", "-m", "ic ilk")
        ic_head = self.git(ic, "rev-parse", "HEAD").stdout.strip()
        readme = self.hedef / "README.md"
        ozgun = readme.read_bytes()
        readme.write_bytes(ozgun + b"\nyerel not\n")
        r = self.kur("-Sifirla", "-Evet")
        c = self.cikti(r)
        self.assertEqual(r.returncode, 0, c)
        # ön koşul 1 — vaka C'den ayrışma kanıtı: `add -f` DÜŞMEDİ, yani C'yi yakalayan kapı burada hiç kapanmıyor
        self.assertNotIn("git add -f düştü", c)
        dal = self.tek_yedek()
        # ön koşul 2: yedek ağacında gitlink VAR (mod 160000) — `--name-only` ile bu düz dosyadan ayırt edilemezdi
        satirlar = [s for s in self.git(self.hedef, "ls-tree", "-r", dal, "--",
                                        ".axet-guncelleme").stdout.splitlines() if s.strip()]
        self.assertTrue(any(s.startswith("160000 commit") for s in satirlar),
                        f"gitlink yedek ağacında yok, senaryo kurulmadı: {satirlar!r}")
        # ön koşul 3: gitlink'in gösterdiği commit DIŞ depoda YOK ⇒ yedek dalı iç depoyu geri getiremez
        self.assertNotEqual(self.git(self.hedef, "cat-file", "-t", ic_head, kontrol=False).returncode, 0,
                            "iç deponun commit'i dış depoda bulundu: gitlink senaryosu kurulmamış")
        # 1. fail-safe: gömülü deponun dosyası + .git'i DİSKTE DURUYOR (kurtarılamaz olan tek şey bunlardı)
        self.assertTrue(ic_dosya.is_file(), "gömülü deponun dosyası silindi (GERİ ALINAMAZ veri kaybı)\n" + c)
        self.assertEqual(ic_dosya.read_text(encoding="utf-8"), "iç depo dosyası\n")
        self.assertTrue((ic / ".git").is_dir(), "gömülü deponun .git'i silindi (geçmiş yok oldu)\n" + c)
        # Aynı dizindeki DÜZ dosya blob olarak yedeğe girdiği için diskten kalkar (onu 3. adımdaki `switch main`
        # kaldırır, 5. adımdaki Remove-Item değil) — ölçüldü 2026-09-16: yedek commit'i `100644 uygulanan.json` +
        # `160000 ic-repo` içeriyor. Kayıp DEĞİL: yedek dalından geri alınır. Vaat "kurtarılamayanı silme"dir,
        # "hiçbir şeyi silme" değil; iddiayı olduğundan geniş yazmamak için dosya varlığı DEĞİL kurtarılabilirlik
        # ölçülür.
        self.assertFalse(veri.is_file(), "senaryo değişti: düz dosya diskte kaldı (switch main koşmadı mı?)\n" + c)
        self.assertIn('"surum": 1', self.yedekte(dal, ".axet-guncelleme/uygulanan.json"))
        # 2. kullanıcıya ADIYLA söylendi (sessiz geçilmedi)
        self.assertIn(str(durum_dizini), c)
        self.assertIn("SİLİNMEDİ", c)
        # 3. sebep DOĞRU anlatıldı: burada 3/7'de UYARI satırı BASILMAZ ⇒ mesaj vaka C'nin sebebini (add -f düştü)
        # göstermemeli, gitlink sebebini söylemeli. "gitlink" kelimesi yalnız bu dalda geçer.
        self.assertIn("gitlink", c)
        self.assertIn("AYRI bir git deposu", c)
        # 4. akış DURMADI: sıfırlamanın geri kalanı tamamlandı
        self.assertEqual(readme.read_bytes(), ozgun)
        self.assertIn("yerel not", self.yedekte(dal, "README.md"))

    # --- Z98: kurulum bulduğu Python'u kullanıcı PATH'ine ekler (sahte kayıt hedefiyle) ----------------------------
    def z98_beklenen(self) -> list:
        d = self.kur_python().parent
        return [str(d)] + ([str(d / "Scripts")] if (d / "Scripts").is_dir() else [])

    def z98_kayit(self) -> Path:
        return self.hedef / ".axet-kurulum" / "kullanici-path.json"

    def test_z98_python_cozulmuyorsa_kullanici_pathinin_basina_eklenir(self):
        self.env["AXET_Z98_DENEME"] = str(self.tmp)
        ilk = r"C:\kullanicinin\araci;%AXET_Z98_DENEME%\bin"
        f = self.path_kaydi(str(SYS32), ilk)
        r = self.kur("-Evet")
        c = self.cikti(r)
        self.assertEqual(r.returncode, 0, c)
        k = self.path_kaydi_oku(f)
        beklenen = self.z98_beklenen()
        # başa eklendi; mevcut değer AYNEN (sıra, %VAR% genişletilmeden) korundu; tür korundu
        self.assertEqual(k["kullanici"], ";".join(beklenen) + ";" + ilk, c)
        self.assertEqual(k["tur"], "ExpandString")
        self.assertEqual(k["makine"], self.makine_kaydi)
        self.assertIn(f"Python yolu kullanıcı PATH'ine eklendi: {beklenen[0]}", c)
        self.assertIn("yeni terminal / yeni aXet oturumu aç", c)
        self.assertNotIn("UYARI: yeni terminalde 'python'", c)
        self.assertEqual(json.loads(self.z98_kayit().read_text(encoding="utf-8-sig"))["eklenen"], beklenen)
        self.assertEqual(self.git(self.hedef, "status", "--porcelain").stdout.strip(), "",
                         "kayıt dosyası git'e görünmemeli (gitignore'lu)")
        # ikinci koşum: python artık çözülüyor -> hiçbir şey yazılmaz
        once = f.read_bytes()
        r = self.kur("-Evet")
        c = self.cikti(r)
        self.assertEqual(r.returncode, 0, c)
        self.assertEqual(f.read_bytes(), once, c)
        self.assertNotIn("PATH'ine eklendi", c)

    def test_z98_kontrol_grubu_python_zaten_dogruysa_hicbir_sey_yazilmaz(self):
        f = self.path_kaydi(str(self.kur_python().parent), r"C:\x;%AXET_Z98_DENEME%\y")
        once = f.read_bytes()
        r = self.kur("-Evet")
        c = self.cikti(r)
        self.assertEqual(r.returncode, 0, c)
        self.assertEqual(f.read_bytes(), once, c)
        self.assertNotIn("PATH'ine eklendi", c)
        self.assertFalse(self.z98_kayit().exists(), c)

    def test_z98_zaten_varsa_eklenmez_harf_ve_ters_bolu_farki_esit(self):
        beklenen = self.z98_beklenen()
        eski = self.eski_python_dizini("3.9")
        # kullanıcı PATH'inde aynı klasörler zaten var: biri BÜYÜK harf + sonda "\", öbürü küçük harf
        ilk = ";".join([beklenen[0].upper() + "\\"] + [b.lower() for b in beklenen[1:]] + [r"C:\x"])
        f = self.path_kaydi(os.pathsep.join([str(eski), str(SYS32)]), ilk)
        once = f.read_bytes()
        r = self.kur("-Evet")
        c = self.cikti(r)
        self.assertEqual(r.returncode, 0, c)
        self.assertEqual(f.read_bytes(), once, c)
        self.assertNotIn("PATH'ine eklendi", c)
        self.assertFalse(self.z98_kayit().exists(), c)
        self.assertIn("UYARI: yeni terminalde 'python'", c)  # öndeki eski Python yüzünden hâlâ yanlış

    def test_z98_makine_pathinde_eski_python_onde_ise_uyari_fail_degil(self):
        eski = self.eski_python_dizini("3.9")
        f = self.path_kaydi(os.pathsep.join([str(eski), str(SYS32)]), r"C:\x", tur="String")
        r = self.kur("-Evet")
        c = self.cikti(r)
        self.assertEqual(r.returncode, 0, c)
        k = self.path_kaydi_oku(f)
        self.assertEqual(k["kullanici"], ";".join(self.z98_beklenen()) + r";C:\x", c)
        self.assertEqual(k["tur"], "String")  # REG_SZ olan değer REG_SZ kalır
        self.assertIn("UYARI: yeni terminalde 'python'", c)
        self.assertIn(str(eski / "python.cmd"), c)
        self.assertIn("makine PATH", c)  # çözülen komut makine PATH'inden geliyor: BT'ye yönlendirilir
        self.assertIn("Kurulum TAMAM", c)

    def test_z98_deneme_modu_eklenecegi_gosterir_yazmaz(self):
        f = self.path_kaydi(str(SYS32), r"C:\x")
        once = f.read_bytes()
        r = self.kur("-DenemeModu")
        c = self.cikti(r)
        self.assertEqual(r.returncode, 0, c)
        self.assertEqual(f.read_bytes(), once, c)
        self.assertIn(f"[deneme] Python yolu kullanıcı PATH'ine eklenecekti: {self.z98_beklenen()[0]}", c)
        self.assertFalse(self.hedef.exists())

    def test_z98_kaldir_bozuk_kayit_uyarir_kaldirma_tamamlanir(self):
        f = self.path_kaydi(str(SYS32), r"C:\x")
        r = self.kur("-Evet")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertTrue(self.z98_kayit().is_file(), self.cikti(r))
        self.z98_kayit().write_text("{bozuk", encoding="utf-8")
        once = f.read_bytes()
        r = self.kur("-Kaldir")
        c = self.cikti(r)
        self.assertEqual(r.returncode, 0, c)
        self.assertIn("geri alınamadı", c)
        self.assertIn("kayıtları kaldırıldı", c)  # kaldırmanın geri kalanı sürdü
        self.assertEqual(f.read_bytes(), once, c)

    def test_z98_kaldir_yalniz_kurulumun_ekledigini_geri_alir(self):
        d = self.kur_python().parent
        if not (d / "Scripts").is_dir():
            self.skipTest("yorumlayıcının Scripts klasörü yok")
        self.env["AXET_Z98_DENEME"] = str(self.tmp)
        # Scripts kullanıcının KENDİ girdisi (kurulumdan önce vardı): kurulum yalnız klasörü ekler, -Kaldir onu siler
        ilk = str(d / "Scripts") + r";C:\kendi;%AXET_Z98_DENEME%\z"
        f = self.path_kaydi(str(SYS32), ilk)
        r = self.kur("-Evet")
        c = self.cikti(r)
        self.assertEqual(r.returncode, 0, c)
        k = self.path_kaydi_oku(f)
        self.assertEqual(k["kullanici"], f"{d};{ilk}", c)
        # kurulumdan SONRA kullanıcı kendi girdisini ekledi
        k["kullanici"] = "C:\\sonradan;" + k["kullanici"]
        f.write_text(json.dumps(k, ensure_ascii=False), encoding="utf-8")
        r = self.kur("-Kaldir")
        c = self.cikti(r)
        self.assertEqual(r.returncode, 0, c)
        k = self.path_kaydi_oku(f)
        self.assertEqual(k["kullanici"], "C:\\sonradan;" + ilk, c)
        self.assertEqual(k["tur"], "ExpandString")
        self.assertFalse(self.z98_kayit().exists(), c)
        self.assertIn("kullanıcı PATH'inden çıkarıldı", c)
        # kayıt yokken -Kaldir PATH'e dokunmaz
        once = f.read_bytes()
        r = self.kur("-Kaldir")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertEqual(f.read_bytes(), once, self.cikti(r))

    # --- statik: sığ klon yasağı + README varyantı --------------------------------------------------------------
    def test_kur_ps1_sig_klon_yapmaz(self):
        """Sığ/kısmi klon `origin/main..HEAD`, `merge-base` ve yedek dalını bozar (TASARIM §1, §12 satır 351)."""
        metin = KUR_PS1.read_text(encoding="utf-8-sig")
        klon_satirlari = [s for s in metin.splitlines() if re.search(r"'clone'|\bgit clone\b", s)]
        self.assertTrue(klon_satirlari, "kur.ps1'de clone çağrısı bulunamadı (test kör kaldı)")
        for s in klon_satirlari:
            for yasak in ("--depth", "--shallow", "--filter", "--single-branch"):
                self.assertNotIn(yasak, s, f"sığ/kısmi klon: {s.strip()}")

    def test_onboarding_sifirla_tek_satir_varyanti(self):
        """Bozuk yerel kur.ps1'den bağımsız sıfırlama: indirilen dosyayı -Sifirla ile çalıştıran varyant (TASARIM §10).
        Kurulum sadeleştirme (2026-09-24): terminal satırları README'den onboarding "Sorun giderme"ye taşındı —
        sözleşme onunla birlikte taşındı (gevşetilmedi)."""
        metin = (AXET_HOME / "docs" / "onboarding.md").read_text(encoding="utf-8")
        metin = metin[metin.index("## 5. Sorun giderme"):]
        self.assertIn("-File $f -Sifirla", metin)
        self.assertIn("kur.cmd -Sifirla", metin)

    # --- statik: tüketici-yüzü depo işaretçileri ----------------------------------------------------------------
    def test_tuketici_isaretcileri_public_depoyu_gosterir(self):
        """Kurulum yolundaki her GitHub işaretçisi PUBLIC yayın deposuna (`ozgurylmz34/axet-template`) gitmeli.

        Kullanıcı kararı (2026-09-18): kurulum public depodan yapılır. `ozgurylmz34/axet` PRIVATE geliştirme
        deposudur; tüketicinin izlediği bir yolda kalırsa yetkisiz hesap 404 alır ve kurulum başlamaz.
        Sayım alt sınırı testin kör kalmasını önler (işaretçiler silinirse NotIn tek başına yeşil kalırdı)."""
        dosyalar = {"README.md": "utf-8", "kur.ps1": "utf-8-sig", "docs/onboarding.md": "utf-8"}
        toplam = 0
        for yol, kodlama in dosyalar.items():
            metin = (AXET_HOME / yol).read_text(encoding=kodlama)
            eski = re.findall(r"ozgurylmz34/axet(?!-template)", metin)
            self.assertEqual([], eski, f"{yol}: tüketici-yüzü işaretçi PRIVATE geliştirme deposunu gösteriyor")
            toplam += metin.count("ozgurylmz34/axet-template")
        self.assertGreaterEqual(toplam, 5, "işaretçiler kayboldu — test kör kaldı")
        # kur.ps1'in klonladığı varsayılan kaynak
        ps1 = KUR_PS1.read_text(encoding="utf-8-sig")
        self.assertIn("$Kaynak = 'https://github.com/ozgurylmz34/axet-template.git'", ps1)

    def test_readme_ve_onboarding_private_notu_tasimaz(self):
        """Depo public olduktan sonra "private / yetki gerekir / 404" notu YANILTICIDIR ve belgede kalmamalı."""
        for yol, kodlama in (("README.md", "utf-8"), ("docs/onboarding.md", "utf-8")):
            metin = (AXET_HOME / yol).read_text(encoding=kodlama)
            self.assertNotIn("Depo şu an private", metin, f"{yol}: bayat private notu duruyor")
            self.assertNotIn("private dönemde", metin, f"{yol}: bayat private notu duruyor")


@unittest.skipUnless(WINDOWS and POWERSHELL.exists(), "yalnız Windows (PowerShell 5.1)")
class KurPythonYoluTest(GeciciTest):
    """Z98 düzeltme turu: kur.ps1'in PATH fonksiyonları AST ile yüklenip DOĞRUDAN koşulur (tam kurulum yok, hızlı).
    Sürücü AXET_KUR_PATH_KAYDI yoksa 99 ile çıkar: kayıt defterine giden yol hiç açılmaz. GERÇEK HKCU Path sınıf
    öncesi/sonrası karşılaştırılır (_gercek_damga).
    KAPSAM — bakılmayanlar: kur.ps1 ana akışındaki çağrı yerleri (KurTest ölçer) · gerçek kayıt defteri yazımı ve
    WM_SETTINGCHANGE yayını · gerçek WindowsApps yönlendirmesi (rc 9009 dönen sahte python.cmd kullanılır) ·
    kullanıcı PATH'inden gelen uyarı metni (yazımdan sonra oluşturulabilen bir senaryo bulunamadı)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._once = _gercek_damga()
        cls.sinif_tmp = gecici_dizin("axet-kurpy-")   # repo DIŞI (Z96)
        cls.venv = cls.sinif_tmp / "venv"
        r = subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(cls.venv)], capture_output=True,
                           text=True, stdin=subprocess.DEVNULL, timeout=300)
        if r.returncode != 0:
            raise RuntimeError(f"venv oluşturulamadı: {r.stdout}{r.stderr}")

    @classmethod
    def tearDownClass(cls) -> None:
        _sil(cls.sinif_tmp)
        sonra = _gercek_damga()
        if sonra != cls._once:
            raise AssertionError(f"GERÇEK aXet config/HKCU Path testte değişti:\nönce={cls._once}\nsonra={sonra}")

    def setUp(self) -> None:
        super().setUp()
        self.klon = self.tmp / "klon"
        self.klon.mkdir()
        self.kayit = self.tmp / "_path_kaydi.json"
        self.env["AXET_KUR_PATH_KAYDI"] = str(self.kayit)
        self.taban = Path(getattr(sys, "_base_executable", sys.executable)).resolve()
        self.pydir = self.taban.parent

    def beklenen(self, d: Path) -> list:
        return [str(d)] + ([str(d / "Scripts")] if (d / "Scripts").is_dir() else [])

    def path_yaz(self, makine: str, kullanici: str, tur: str = "ExpandString") -> None:
        self.kayit.write_text(json.dumps({"makine": makine, "kullanici": kullanici, "tur": tur}, ensure_ascii=False),
                              encoding="utf-8")

    def path_oku(self) -> dict:
        return json.loads(self.kayit.read_text(encoding="utf-8-sig"))

    def klon_kaydi(self) -> Path:
        return self.klon / ".axet-kurulum" / "kullanici-path.json"

    def kos(self, govde: str, py: Path | None = None, deneme: bool = False, git: str | None = None,
            girdi: str | None = None) -> subprocess.CompletedProcess:
        asgari = re.search(r"^\$script:PyAsgari = \[version\]'([\d.]+)'", KUR_PS1.read_text(encoding="utf-8-sig"), re.M)
        satirlar = [
            "Set-StrictMode -Version 2",
            "$ErrorActionPreference = 'Continue'",
            "try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false } catch { }",
            "if (-not $env:AXET_KUR_PATH_KAYDI) { exit 99 }",
            f"$ast = [System.Management.Automation.Language.Parser]::ParseFile('{KUR_PS1}', [ref]$null, [ref]$null)",
            "foreach ($f in $ast.EndBlock.Statements) { if ($f -is [System.Management.Automation.Language.FunctionDefinitionAst]) { . ([scriptblock]::Create($f.Extent.Text)) } }",
            f"$script:PyAsgari = [version]'{asgari.group(1)}'",
            "$script:PyEski = $null",
            f"$DenemeModu = ${'true' if deneme else 'false'}",
            f"$script:PY = '{py or sys.executable}'",
            f"$script:GIT = '{git or ''}'",
            "$script:GitKod = 0",
            f"$klon = '{self.klon}'",
            govde,
        ]
        surucu = self.tmp / "_surucu.ps1"
        surucu.write_bytes(b"\xef\xbb\xbf" + "\r\n".join(satirlar).encode("utf-8") + b"\r\n")
        komut = [str(POWERSHELL), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(surucu)]
        if girdi == "<konsol>":
            # Gerçek konsol girişi: yeni (gizli) konsol, standart tutamaçlar YÖNLENDİRİLMEZ (çift tıklanan pencere gibi).
            # Çıktı yakalanamaz; gövde sonucunu dosyaya yazmalıdır.
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 0
            return subprocess.run(komut, env=self.env, cwd=str(self.tmp), timeout=300,
                                  creationflags=subprocess.CREATE_NEW_CONSOLE, startupinfo=si)
        girdi_kw = {"input": girdi} if girdi is not None else {"stdin": subprocess.DEVNULL}
        return subprocess.run(komut, env=self.env, cwd=str(self.tmp), capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=300, **girdi_kw)

    # --- PATH tazeleme (kurulumun başı) -------------------------------------------------------------------------
    def test_path_tazele_kayittaki_eksik_girdileri_sona_ekler_sirayi_bozmaz(self):
        self.env["AXET_TAZE_DENEME"] = str(self.tmp)
        self.path_yaz(r"C:\m1;%AXET_TAZE_DENEME%\m2", r"C:\U1\;c:\p")
        r = self.kos("$env:Path = 'C:\\p;C:\\m1'\r\n$n = Path-Tazele\r\nYaz \"N=$n\"\r\nYaz \"P=$env:Path\"\r\n"
                     "$n = Path-Tazele\r\nYaz \"N2=$n\"")
        c = r.stdout + r.stderr
        self.assertEqual(r.returncode, 0, c)
        # mevcut sıra aynen; eksikler (%VAR% açılmış) sona; harf/sondaki \ farkı aynı girdi sayılır (c:\p tekrar eklenmez)
        self.assertIn(f"P=C:\\p;C:\\m1;{self.tmp}\\m2;C:\\U1\\", c)
        self.assertIn("N=2", c)
        self.assertIn("N2=0", c)  # ikinci çağrı: eklenecek bir şey yok

    # --- Python bilinen klasörler: SÜRÜM sırası (bug gate 2026-09-24, LOW) -------------------------------------------
    def test_python_bilinen_klasorler_surume_gore_denenir_eski_surum_satiri_yok(self):
        """Python39 + Python310 + Python312 + Python313: ilk aday 3.13, eski sürüm hiç denenmez (satırı basılmaz).
        Eskiden `Sort-Object Name -Descending` alfabetikti: "Python39" > "Python313" → 3.9 önce denenip
        "3.9 bulundu ama 3.12 gerekli" basılıyordu. Klasörlerde GERÇEK yorumlayıcı (venv başlatıcısı + pyvenv.cfg);
        bildirdiği sürüm site-packages'taki .pth ile klasör adından türetilir (yorumlayıcı gerçek, yalnız
        sys.version_info sahte). Kontrol grubu: sahte 3.9 gerçekten 3.9 bildirir ve Python-Dene onu eski sayar."""
        lad = self.tmp / "_lad"
        kok = lad / "Programs" / "Python"
        klasorler = ["Python39", "Python310", "Python312", "Python313"]
        paketler = set()
        for ad in klasorler:
            (kok / ad).mkdir(parents=True)
            shutil.copy2(self.venv / "Scripts" / "python.exe", kok / ad / "python.exe")
            shutil.copy2(self.venv / "pyvenv.cfg", kok / ad / "pyvenv.cfg")
            r = subprocess.run([str(kok / ad / "python.exe"), "-c", "import site;print(site.getsitepackages()[-1])"],
                               capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60)
            self.assertEqual(r.returncode, 0, r.stderr)
            paketler.add(r.stdout.strip())
        for sp in paketler:  # "import" ile başlayan .pth satırı site yüklenirken çalışır
            self.yaz(Path(sp) / "_axet_sahte_surum.pth",
                     "import sys, os, re; _m = re.match(r'Python(\\d)(\\d+)$', os.path.basename(os.path.dirname("
                     "sys.executable))); _m and setattr(sys, 'version_info', (int(_m[1]), int(_m[2]), 0, 'final', 0))\n")
        bos = self.tmp / "_bos"
        bos.mkdir()
        self.path_yaz("", "")  # PEP 514 adayları boş (python_kayit yok)
        govde = "\r\n".join([
            f"$env:Path = '{SYS32}'",  # PATH'te python/py yok: yalnız bilinen klasör kolu kalır
            f"$env:LOCALAPPDATA = '{lad}'",
            f"$env:ProgramFiles = '{bos}'", f"$env:ProgramW6432 = '{bos}'", f"${{env:ProgramFiles(x86)}} = '{bos}'",
            f"$env:SystemDrive = '{bos}'",
            "Yaz ('ADAY=' + ((@(Python-Bilinen-Adaylari) | ForEach-Object { Split-Path -Leaf (Split-Path -Parent $_) }) -join ','))",
            "$p = Python-Bul",
            "Yaz \"SECILEN=$($p.Surum)|$($p.Yol)\"",
            "Yaz '--KONTROL--'",
            f"$null = Python-Dene '{kok / 'Python39' / 'python.exe'}' @()",
        ])
        r = self.kos(govde)
        c = r.stdout + r.stderr
        self.assertEqual(r.returncode, 0, c)
        asil, kontrol = c.split("--KONTROL--", 1)
        self.assertIn("ADAY=Python313,Python312,Python310,Python39", asil)
        self.assertIn(f"SECILEN=3.13|{kok / 'Python313' / 'python.exe'}", asil)
        self.assertNotIn("bulundu ama", asil)  # eski sürüm hiç denenmedi
        self.assertIn(f"Python 3.9 bulundu ama 3.12 ya da üstü gerekli: {kok / 'Python39' / 'python.exe'}", kontrol)

    # --- Konsol-Etkilesimli: Add-Type derlenemezse saf .NET yedeği (bug gate 2026-09-24, ÖNERİ) -------------------
    def test_konsol_etkilesimli_add_type_yoksa_yedek_ayni_karari_verir(self):
        """Gerçek konsol (yeni gizli konsol, giriş yönlendirilmemiş) → True; NUL ve boru → False. Hem birincil yol
        (Add-Type + GetConsoleMode) hem yedek ([Console]::IsInputRedirected; AXET_KUR_KONSOL_YEDEK=1 Add-Type kolunu
        atlar) için. Eskiden Add-Type hatası her zaman False'tu: gerçek çift tıkta kimlik hiç sorulmazdı.
        KAPSAM — bakılmayan: Add-Type'ın GERÇEKTEN derlenemediği ortam (uygulama denetimi) üretilmedi; yedek kol test
        anahtarıyla sınanır. Constrained Language'ta kur.ps1'in kendisi de çalışmaz ([Console] çağrıları)."""
        for k in ("AXET_KUR_SORMA", "AXET_KUR_KONSOL", "AXET_KUR_KONSOL_YEDEK"):
            self.env.pop(k, None)
        cikis = self.tmp / "_konsol.txt"
        govde = f"[IO.File]::WriteAllText('{cikis}', \"SONUC=$(Konsol-Etkilesimli)\")"
        for yedek in (False, True):
            if yedek:
                self.env["AXET_KUR_KONSOL_YEDEK"] = "1"
            for giris, beklenen in (("<konsol>", "True"), (None, "False"), ("", "False")):  # None = NUL, "" = boru
                with self.subTest(yedek=yedek, giris={"<konsol>": "konsol", None: "NUL", "": "boru"}[giris]):
                    cikis.unlink(missing_ok=True)
                    r = self.kos(govde, girdi=giris)
                    self.assertEqual(r.returncode, 0, getattr(r, "stderr", ""))
                    self.assertEqual(cikis.read_text(encoding="utf-8-sig"), f"SONUC={beklenen}")

    # --- Git bilinen klasör + Z98 Git kolu -----------------------------------------------------------------------
    def gercek_git_koku(self) -> Path:
        """Git for Windows kök klasörü (içinde cmd\\git.exe olan). PATH'teki git cmd\\ ya da mingw64\\bin\\ altında
        olabilir (Git Bash'ten koşunca ikincisi önde — ölçüldü)."""
        yol = shutil.which("git", path=next(v for k, v in self.env.items() if k.upper() == "PATH"))
        for kok in ((Path(yol).parents[1], Path(yol).parents[2]) if yol else ()):
            if (kok / "cmd" / "git.exe").is_file():
                return kok
        self.skipTest(f"Git for Windows düzeni (<kök>\\cmd\\git.exe) bulunamadı: {yol}")

    def test_git_bilinen_klasorde_varsayilanda_bulunur(self):
        """Git PATH'te değil, %ProgramFiles%\\Git\\cmd\\git.exe'de (portal Git'i PATH'e koymadıysa). ProgramFiles geçici bir
        klasörü gösterir; içindeki Git bağlantısı (junction, yönetici gerekmez) gerçek Git kurulumuna gider. Kontrol grubu:
        bağlantı yokken Git bulunamaz."""
        kok = self.gercek_git_koku()
        pf = self.tmp / "_pf"
        pf.mkdir()
        for k in list(self.env):
            if k.upper() in ("PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMW6432", "LOCALAPPDATA", "PATH"):
                del self.env[k]
        self.env.update({"ProgramFiles": str(pf), "ProgramFiles(x86)": str(pf), "ProgramW6432": str(pf),
                         "LOCALAPPDATA": str(self.tmp / "_lad"), "PATH": os.pathsep.join([str(SYS32), str(POWERSHELL.parent)])})
        govde = "$g = Git-Bul\r\nif ($g) { Yaz \"GIT=$($g.Yol)\" } else { Yaz 'GIT=YOK' }"
        r = self.kos(govde)
        self.assertIn("GIT=YOK", r.stdout + r.stderr)  # kontrol grubu
        bag = pf / "Git"
        subprocess.run([COMSPEC, "/c", "mklink", "/J", str(bag), str(kok)], check=True, capture_output=True,
                       stdin=subprocess.DEVNULL, timeout=60)
        try:
            r = self.kos(govde)
            self.assertIn(f"GIT={bag / 'cmd' / 'git.exe'}", r.stdout + r.stderr)
        finally:
            os.rmdir(bag)  # YALNIZ bağlantı kaldırılır; hedefe (gerçek Git) dokunulmaz
        self.assertTrue((kok / "cmd" / "git.exe").is_file(), "gerçek Git kurulumu etkilendi!")

    def test_git_yolu_kullanici_pathinin_sonuna_eklenir_kaldir_geri_alir(self):
        kok = self.gercek_git_koku()
        git = kok / "cmd" / "git.exe"
        self.path_yaz(str(SYS32), "C:\\a;%AXET_Z98_DENEME%\\b")
        r = self.kos("Git-Yolu-Adimi $klon", git=str(git))
        c = r.stdout + r.stderr
        self.assertEqual(r.returncode, 0, c)
        self.assertEqual(self.path_oku()["kullanici"], f"C:\\a;%AXET_Z98_DENEME%\\b;{git.parent}", c)  # sona, metin aynen
        self.assertIn("Git yolu kullanıcı PATH'ine eklendi", c)
        self.assertNotIn("UYARI", c)
        self.assertEqual(json.loads(self.klon_kaydi().read_text(encoding="utf-8-sig"))["eklenen"], [str(git.parent)])
        # ikinci koşum: yeni terminalde git artık çözülüyor → yazılmaz
        once = self.kayit.read_bytes()
        r = self.kos("Git-Yolu-Adimi $klon", git=str(git))
        self.assertIn("OK 'git' komutu yeni terminallerde çalışıyor", r.stdout)
        self.assertEqual(self.kayit.read_bytes(), once)
        # -Kaldir: yalnız kurulumun eklediği Git klasörü çıkar
        r = self.kos("Python-Yolu-Kaldir-Adimi $klon")
        c = r.stdout + r.stderr
        self.assertEqual(self.path_oku()["kullanici"], "C:\\a;%AXET_Z98_DENEME%\\b", c)
        self.assertIn("kullanıcı PATH'inden çıkarıldı", c)
        self.assertFalse(self.klon_kaydi().exists(), c)

    def test_git_yolu_kontrol_grubu_ve_deneme_modu_yazmaz(self):
        kok = self.gercek_git_koku()
        git = kok / "cmd" / "git.exe"
        for makine, deneme, beklenen in ((f"{SYS32};{git.parent}", False, "OK 'git' komutu"),
                                         (str(SYS32), True, "[deneme] Git yolu kullanıcı PATH'ine eklenecekti")):
            with self.subTest(deneme=deneme):
                self.path_yaz(makine, "C:\\a")
                once = self.kayit.read_bytes()
                r = self.kos("Git-Yolu-Adimi $klon", git=str(git), deneme=deneme)
                self.assertIn(beklenen, r.stdout + r.stderr)
                self.assertEqual(self.kayit.read_bytes(), once)
                self.assertFalse(self.klon_kaydi().exists())

    # --- Git kimliği (işe başlamadan) ---------------------------------------------------------------------------
    def kimlik(self, anahtar: str) -> str:
        return self.git(self.tmp, "config", "--global", "--get", anahtar, kontrol=False).stdout.strip()

    def git_exe(self) -> str:
        return shutil.which("git", path=next(v for k, v in self.env.items() if k.upper() == "PATH"))

    def test_git_kimligi_etkilesimsiz_konsolda_sorulmaz_yazilmaz(self):
        r = self.kos("Git-Kimligi-Adimi", git=self.git_exe())  # stdin NUL: gerçek konsol değil
        c = r.stdout + r.stderr
        self.assertEqual(r.returncode, 0, c)
        self.assertIn("Git kimliği SORULMADI", c)
        self.assertEqual((self.kimlik("user.name"), self.kimlik("user.email")), ("", ""))

    def test_git_kimligi_sorulur_eposta_bicimi_denetlenir_yazilir(self):
        self.env["AXET_KUR_KONSOL"] = "1"  # yalnız test: yanıtlar boruyla
        r = self.kos("Git-Kimligi-Adimi", git=self.git_exe(), girdi="Ayse Yilmaz\nayse-at-firma\nayse.yilmaz@firma.com\n")
        c = r.stdout + r.stderr
        self.assertEqual(r.returncode, 0, c)
        self.assertIn("e-posta adresine benzemiyor", c)  # geçersiz biçim reddedildi, yeniden soruldu
        self.assertEqual((self.kimlik("user.name"), self.kimlik("user.email")), ("Ayse Yilmaz", "ayse.yilmaz@firma.com"))
        self.assertIn("Git kimliği kaydedildi: Ayse Yilmaz <ayse.yilmaz@firma.com>", c)

    def test_git_kimligi_tanimliysa_gosterilir_dogru_mu_sorulur(self):
        self.git(self.tmp, "config", "--global", "user.name", "Eski Ad")
        self.git(self.tmp, "config", "--global", "user.email", "eski@firma.com")
        self.env["AXET_KUR_KONSOL"] = "1"
        r = self.kos("Git-Kimligi-Adimi", git=self.git_exe(), girdi="\n")  # Enter = doğru
        c = r.stdout + r.stderr
        self.assertIn("Git kimliğin: Eski Ad <eski@firma.com>", c)
        self.assertIn("aynen kaldı", c)
        self.assertEqual(self.kimlik("user.name"), "Eski Ad")
        # "h" → yeniden sorulur; boş yanıt köşeli parantezdeki mevcut değeri korur
        r = self.kos("Git-Kimligi-Adimi", git=self.git_exe(), girdi="h\nYeni Ad\n\n")
        c = r.stdout + r.stderr
        self.assertEqual((self.kimlik("user.name"), self.kimlik("user.email")), ("Yeni Ad", "eski@firma.com"), c)

    def test_git_kimligi_ortam_degiskeni_ve_deneme_modu(self):
        self.env.update({"AXET_KUR_GIT_AD": "Öykü Şahin", "AXET_KUR_GIT_EPOSTA": "oto@firma.com"})
        r = self.kos("Git-Kimligi-Adimi", git=self.git_exe(), deneme=True)
        self.assertIn("[deneme] Git kimliği yazılacaktı: Öykü Şahin <oto@firma.com>", r.stdout)
        self.assertEqual(self.kimlik("user.name"), "")  # deneme modu yazmaz
        r = self.kos("Git-Kimligi-Adimi", git=self.git_exe())
        self.assertEqual((self.kimlik("user.name"), self.kimlik("user.email")), ("Öykü Şahin", "oto@firma.com"), r.stdout)
        # geçersiz e-posta ortamdan gelse de yazılmaz
        self.env["AXET_KUR_GIT_EPOSTA"] = "bozuk"
        r = self.kos("Git-Kimligi-Adimi", git=self.git_exe())
        self.assertIn("geçerli bir e-posta değil", r.stdout)
        self.assertEqual(self.kimlik("user.email"), "oto@firma.com")

    def test_git_kimligi_sorma_kapali(self):
        self.env.update({"AXET_KUR_KONSOL": "1", "AXET_KUR_SORMA": "1"})  # SORMA konsol zorlamasından önce gelir
        r = self.kos("Git-Kimligi-Adimi", git=self.git_exe(), girdi="Ad\nad@firma.com\n")
        self.assertIn("SORULMADI", r.stdout)
        self.assertEqual(self.kimlik("user.name"), "")

    def test_magaza_kisayolu_arkasindaki_klasor_basa_tasinir_kaldir_silmez(self):
        wa = self.tmp / "_wa"
        wa.mkdir()
        (wa / "python.cmd").write_text("@echo off\r\nexit /b 9009\r\n", encoding="ascii", newline="")
        self.env["AXET_Z98_PYDIR"] = str(self.pydir)
        tasinan = "%AXET_Z98_PYDIR%\\"
        self.path_yaz(str(SYS32), f"{wa};{tasinan};C:\\x")
        r = self.kos("Python-Yolu-Adimi $klon")
        c = r.stdout + r.stderr
        self.assertEqual(r.returncode, 0, c)
        eklenen = self.beklenen(self.pydir)[1:]  # klasörün kendisi zaten vardı: yalnız Scripts eklenir
        # girdinin METNİ aynen (%VAR% ve sondaki \ dahil) başa taşındı, önündeki kısayol arkaya düştü
        self.assertEqual(self.path_oku()["kullanici"], ";".join([tasinan] + eklenen + [str(wa), "C:\\x"]), c)
        self.assertIn("başa taşındı", c)
        self.assertNotIn("UYARI", c)
        kayit = json.loads(self.klon_kaydi().read_text(encoding="utf-8-sig"))
        self.assertEqual(kayit["tasinan"], [tasinan], c)
        self.assertEqual(kayit["eklenen"], eklenen, c)
        # -Kaldir: taşınan girdi kullanıcınındı, SİLİNMEZ; yalnız kurulumun eklediği çıkar
        r = self.kos("Python-Yolu-Kaldir-Adimi $klon")
        c = r.stdout + r.stderr
        self.assertEqual(r.returncode, 0, c)
        self.assertEqual(self.path_oku()["kullanici"], ";".join([tasinan, str(wa), "C:\\x"]), c)
        self.assertFalse(self.klon_kaydi().exists(), c)
        self.assertIn("yerinde bırakıldı", c)

    def test_venv_icinden_kosulunca_taban_klasor_eklenir(self):
        vpy = self.venv / "Scripts" / "python.exe"
        taban = subprocess.run([str(vpy), "-c", "import sys;print(sys._base_executable)"], capture_output=True,
                               text=True, stdin=subprocess.DEVNULL, timeout=60).stdout.strip()
        self.assertTrue(Path(taban).is_file(), taban)
        self.assertNotEqual(Path(taban).parent.resolve(), vpy.parent.resolve())  # senaryo gerçekten venv
        self.path_yaz(str(SYS32), "C:\\a")
        r = self.kos("Python-Yolu-Adimi $klon", py=vpy)
        c = r.stdout + r.stderr
        self.assertEqual(r.returncode, 0, c)
        deger = self.path_oku()["kullanici"]
        self.assertEqual(deger, ";".join(self.beklenen(Path(taban).parent)) + ";C:\\a", c)
        self.assertNotIn(str(self.venv).lower(), deger.lower(), c)

    def test_taban_belirlenemezse_eklenmez_uyarir(self):
        d = self.tmp / "_tabansiz"
        d.mkdir()
        sahte = d / "python.cmd"
        sahte.write_text("@echo off\r\necho 3.12^|%~f0\r\nexit /b 0\r\n", encoding="ascii", newline="")
        self.path_yaz(str(SYS32), "C:\\a")
        once = self.kayit.read_bytes()
        r = self.kos("Python-Yolu-Adimi $klon", py=sahte)
        c = r.stdout + r.stderr
        self.assertEqual(r.returncode, 0, c)
        self.assertEqual(self.kayit.read_bytes(), once, c)
        self.assertIn("taban kurulumu belirlenemedi", c)
        self.assertFalse(self.klon_kaydi().exists(), c)

    def test_kayit_birlestirmesi_tekillestirir(self):
        self.klon_kaydi().parent.mkdir()
        self.klon_kaydi().write_text(json.dumps({"eklenen": [str(self.pydir).upper() + "\\"]}), encoding="utf-8")
        self.path_yaz(str(SYS32), "C:\\a")  # kullanıcı eklenen girdiyi elle silmiş
        r = self.kos("Python-Yolu-Adimi $klon")
        c = r.stdout + r.stderr
        self.assertEqual(r.returncode, 0, c)
        kayit = json.loads(self.klon_kaydi().read_text(encoding="utf-8-sig"))
        self.assertEqual(len(kayit["eklenen"]), len(self.beklenen(self.pydir)), c)

    def test_kaldir_bozuk_kayit_uyarir_devam_eder(self):
        self.klon_kaydi().parent.mkdir()
        self.klon_kaydi().write_text("{bozuk", encoding="utf-8")
        self.path_yaz(str(SYS32), "C:\\a")
        once = self.kayit.read_bytes()
        r = self.kos("Python-Yolu-Kaldir-Adimi $klon\r\nYaz 'SONRAKI-ADIM'")
        c = r.stdout + r.stderr
        self.assertEqual(r.returncode, 0, c)
        self.assertIn("geri alınamadı", c)
        self.assertIn("SONRAKI-ADIM", c)
        self.assertEqual(self.kayit.read_bytes(), once, c)


class IlkKurulumCmdTest(unittest.TestCase):
    """Z81: repoda olmayan makineye e-posta/ortak klasörle dağıtılan çift tıklamalık ilk kurulum dosyası.
    Ağ gerektirmeyen biçim ve sözleşme denetimi; gerçek indirme + `-DenemeModu` koşumu elle ölçüldü (Z81)."""

    CMD = AXET_HOME / "aXet-Kur.cmd"

    def test_ascii_ve_crlf(self):
        veri = self.CMD.read_bytes()
        veri.decode("ascii")  # cmd.exe OEM kod sayfasıyla okur; ASCII her sayfada aynı
        satirlar = veri.split(b"\n")[:-1]
        self.assertTrue(satirlar and all(s.endswith(b"\r") for s in satirlar),
                        "her satır CRLF olmalı (cmd LF'li dosyada goto/etiketleri yanlış okuyabilir)")

    def test_onboarding_tek_satiriyla_ayni_adresi_indirir(self):
        """Terminal tek satırı README'den onboarding "Sorun giderme"ye taşındı (2026-09-24); eşlik sözleşmesi onunla."""
        adres = re.findall(r"https://raw\.githubusercontent\.com/\S+?/kur\.ps1", self.CMD.read_text("ascii"))
        onb = re.findall(r"https://raw\.githubusercontent\.com/\S+?/kur\.ps1",
                         (AXET_HOME / "docs" / "onboarding.md").read_text("utf-8"))
        self.assertEqual(len(set(adres)), 1, adres)
        self.assertTrue(onb)
        self.assertEqual(set(adres), set(onb), "cmd ile onboarding'deki tek satır aynı kur.ps1'i indirmeli")

    def test_readme_kurulumu_sade_uc_adim_powershell_yok(self):
        """Kullanıcı kararı (2026-09-24): README kurulum kısmı teknik olmayan okuyucu için: portaldan üç program →
        aXet-Kur.cmd'ye çift tık (git kimliği sorulur) → aXet'te %guncelle → %yeni-proje / %guncelle-proje →
        KURULUMU-TAMAMLA → conn\\DEV.env → tekrar çift tık. PowerShell komutu (tek satır dahil) kurulum kısmında YOK;
        ayrıntı onboarding'e tek satır linkle. SAP yazma bölümü AYRI ve aynen kalır."""
        readme = (AXET_HOME / "README.md").read_text("utf-8")
        bas = readme.index("## Gereksinimler")
        yazma = readme.index("**SAP'ye yazma varsayılan kapalıdır.**")
        kurulum = readme[bas:yazma]
        for ifade in ("aXet", "Git", "Python 3.12", "şirket portalından", "aXet-Kur.cmd", "çift", "git adın",
                      "tekrar çift tıkla", "%guncelle", "%yeni-proje", "%guncelle-proje", "KURULUMU-TAMAMLA",
                      "conn\\DEV.env", "docs/onboarding.md#5-sorun-giderme"):
            self.assertIn(ifade, kurulum)
        for yasak in ("```powershell", "Invoke-WebRequest", "raw.githubusercontent.com", "kur.cmd -", "-Kaldir",
                      "-Sifirla", "git config --global", "winget", "Winget"):
            self.assertNotIn(yasak, kurulum, "README kurulum kısmında terminal/ayrıntı kalmış: " + yasak)
        # güncelleme bölümü tek yolu gösterir
        guncelleme = readme[readme.index("## Güncelleme"):readme.index("## Günlük kullanım")]
        self.assertIn("%guncelle", guncelleme)
        self.assertNotIn("kur.cmd", guncelleme)
        # SAP yazma bölümü ayrı ve yerinde (dokunulmadı)
        self.assertIn("python $HOME\\axet\\scripts\\install.py --sap --sap-write      # kapatmak: --no-sap-write",
                      readme[yazma:yazma + 400])
        # onboarding git kimlik komutlarını ve ön koşul kontrol komutlarını taşımaz (kurulum sorar/denetler)
        onb = (AXET_HOME / "docs" / "onboarding.md").read_text("utf-8")
        self.assertNotIn("git config --global user.name", onb)
        onkosul = onb[onb.index("## 0. Makine"):onb.index("## 1. Kurulum")]
        for yasak in ("--version", "axet-code -v", "```powershell"):
            self.assertNotIn(yasak, onkosul)

    def test_secenekleri_gecirir_pencereyi_acik_tutar_kodu_dondurur(self):
        metin = self.CMD.read_text("ascii")
        calistir = [s for s in metin.splitlines() if "-File" in s and "powershell" in s.lower()]
        self.assertEqual(len(calistir), 1, calistir)
        self.assertIn("%*", calistir[0], "ek seçenekler (ör. -DenemeModu) kur.ps1'e geçmeli")
        self.assertIn("-ExecutionPolicy Bypass", calistir[0])
        self.assertRegex(metin, r"(?m)^pause\s*$", "çift tıklamada pencere mesaj okunmadan kapanmamalı")
        self.assertRegex(metin, r"(?m)^exit /b %RC%\s*$", "kur.ps1'in çıkış kodu korunmalı")
        for kod in ("0", "2", "3"):
            self.assertIn(f'if "%RC%"=="{kod}"', metin, f"çıkış kodu {kod} için ayrı kullanıcı mesajı")
        # 2 (ön koşul sorunu: eksik program, çalışmayan Git, -Winget, -Kaldir'da Python yok) ve 3 (yeni kurulan program
        # görünmüyor): ikisi de "tekrar çift tıkla" der; komut vermez. 2'nin metni tarafsızdır (dört durumun gerçek koşumu:
        # KurTest.test_axet_kur_cmd_cikis_2_son_mesaji_dort_durumda_dogru)
        for etiket in (":onkosul", ":yeniden"):
            govde = metin.split(f"\n{etiket}\n", 1)[1].split("goto son", 1)[0]  # read_text CRLF'i \n'e çevirir
            self.assertIn("TEKRAR cift tiklayin", govde, etiket)
            self.assertNotIn("PowerShell", govde, etiket)
        onkosul = metin.split("\n:onkosul\n", 1)[1].split("goto son", 1)[0]
        self.assertNotIn("Eksik program var", onkosul)  # koşulsuz "eksik program" iddiası yok
        self.assertIn("yukaridaki mesajda", onkosul)
        self.assertNotIn("sap-write", metin.lower())
        self.assertNotIn("invoke-expression", metin.lower())

    def test_readme_dosyayi_gosterir(self):
        readme = (AXET_HOME / "README.md").read_text("utf-8")
        self.assertIn("aXet-Kur.cmd", readme)


if __name__ == "__main__":
    unittest.main()
