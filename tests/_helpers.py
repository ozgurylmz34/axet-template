# -*- coding: utf-8 -*-
"""Test yardımcıları — geçici dizinler, izole git/aXet ortamı, script çağırma. Gerçek global config'e ve
template klonunun dosyalarına yazılmaz."""
from __future__ import annotations

import atexit
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

AXET_HOME = Path(__file__).resolve().parents[1]
SCRIPTS = AXET_HOME / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _sil(yol: Path) -> None:
    def duzelt(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    if sys.version_info >= (3, 12):
        shutil.rmtree(yol, onexc=duzelt)
    else:
        shutil.rmtree(yol, onerror=duzelt)


# Z96 (+Z120ⓑ, 2026-09-26): geçici kök bir git reposunun DIŞINDA olmalı. Ölçülen vaka (2026-09-24): aXet TMP/TEMP'i
# `<proje>\.axet-code\tmp`'ye çekiyor; `mkdtemp()` repo içine düştü ve "git reposu değil" varsayan testler kod hatası
# olmadan kırmızı verdi (28/217). Adaylar sırayla: sistem TMP'si (tempfile) → %LOCALAPPDATA%\Temp (Z67 TMP-OLUSTUR
# ile aynı ilke). Hiçbiri repo dışında değilse `GeciciTest` FAIL değil, açık SKIP verir (ölçülemedi ≠ kırmızı).
# Kök TMP'den farklı seçildiyse `GeciciTest.env` TMP/TEMP/TMPDIR'i de oraya çevirir: test edilen betiklerin kendi
# `mkdtemp`'i de repo dışına düşsün. KAPSAM: git kurulu değilse repo ölçülemez → aday olduğu gibi kullanılır.
_GIT_ORTAM_DISI = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_CEILING_DIRECTORIES")


def git_reposunda_mi(yol: Path) -> bool:
    """`yol` bir git çalışma ağacının (ya da `.git` dizininin) içinde mi. git yoksa False (ölçülemez)."""
    env = {k: v for k, v in os.environ.items() if k not in _GIT_ORTAM_DISI}
    try:
        r = subprocess.run(["git", "-C", str(yol), "rev-parse", "--is-inside-work-tree"], env=env,
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           stdin=subprocess.DEVNULL, timeout=60)
    except OSError:
        return False
    return r.returncode == 0   # rc 0 + "false" = `.git` dizininin içi: o da repo içidir


def gecici_kok_sec(adaylar: list[Path]) -> Path | None:
    """Var olan ve git reposu DIŞINDA kalan ilk aday (çözülmüş yol); yoksa None."""
    for aday in adaylar:
        try:
            aday = Path(aday).resolve()
        except OSError:
            continue
        if aday.is_dir() and not git_reposunda_mi(aday):
            return aday
    return None


def _kok_adaylari() -> list[Path]:
    adaylar = [Path(tempfile.gettempdir())]
    lad = os.environ.get("LOCALAPPDATA")
    if lad:
        adaylar.append(Path(lad) / "Temp")
    return adaylar


_GECICI_KOK: list = []   # işlem başına bir kez ölçülür: [Path | None]


def gecici_kok() -> Path | None:
    if not _GECICI_KOK:
        _GECICI_KOK.append(gecici_kok_sec(_kok_adaylari()))
    return _GECICI_KOK[0]


def gecici_dizin(prefix: str) -> Path:
    """Repo DIŞINDA yeni geçici dizin (`tempfile.mkdtemp` yerine). Kök sabitlenemezse `unittest.SkipTest`."""
    kok = gecici_kok()
    if kok is None:
        raise unittest.SkipTest(
            "ÖLÇÜLEMEDİ: geçici kök bir git reposunun DIŞINA sabitlenemedi (adaylar: "
            + ", ".join(str(a) for a in _kok_adaylari()) + ") — 'git reposu değil' varsayan testler burada "
            "yanlış kırmızı verirdi (Z96). TMP'yi repo dışına al ve tekrar koş.")
    return Path(tempfile.mkdtemp(prefix=prefix, dir=str(kok))).resolve()


# Z8 (2026-09-22): `proje()` her testte `git init` + `new_project.py` alt süreçlerini koşuyordu (ölçüldü: test
# başına ≈1,6 sn). Üretilen proje yalnız ADA bağlı: iki farklı mutlak yolda üretilen ağaçlar yalnız
# `.axet-code/sablon-surumu.json` `zaman` alanında ayrışıyor, XDG'ye yazılmıyor. Kalıp işlem başına bir kez
# üretilir, testler `copytree` ile kopyalar. Anahtar (ad, sap, git_init) — üreticiyi etkileyen tüm girdiler.
# KAPSAM: `new_project.py`'nin kendisini değiştiren (monkeypatch/ortam) bir test kalıbı ÖLÇMEZ; böyle testler
# `new_project.py`'yi doğrudan `calistir` ile koşar (bugün hepsi öyle).
_KALIP_KOK: Path | None = None
_KALIPLAR: dict[tuple[str, bool, bool], Path] = {}


def _proje_kalibi(test: "GeciciTest", ad: str, sap: bool, git_init: bool) -> Path:
    global _KALIP_KOK
    anahtar = (ad, sap, git_init)
    if anahtar in _KALIPLAR:
        return _KALIPLAR[anahtar]
    if _KALIP_KOK is None:
        _KALIP_KOK = gecici_dizin("axet-kalip-")
        atexit.register(_sil, _KALIP_KOK)
    d = _KALIP_KOK / str(len(_KALIPLAR)) / ad
    d.mkdir(parents=True)
    if git_init:
        test.git(d, "init", "-q", "-b", "main")
    r = test.calistir("new_project.py", str(d), *(["--sap"] if sap else []))
    test.assertEqual(r.returncode, 0, test.cikti(r))
    _KALIPLAR[anahtar] = d
    return d


class GeciciTest(unittest.TestCase):
    """Her test kendi geçici kökünü alır: `self.tmp`. Ortam: XDG config geçici, git kimliği sabit, git global/sistem
    config'i yok sayılır (kullanıcının hooksPath/autocrlf ayarı sonucu değiştirmesin)."""

    def setUp(self) -> None:
        self.tmp = gecici_dizin("axet-test-")   # repo DIŞI; sabitlenemezse SkipTest (Z96)
        self.xdg = self.tmp / "_xdg"
        self.xdg.mkdir()
        bos_gitconfig = self.tmp / "_gitconfig"
        bos_gitconfig.write_text("", encoding="utf-8")
        self.env = dict(os.environ)
        for k in ("AXET_SAP_PROJECT_DIR", "AXET_PRECOMMIT", "AXET_STAGED_FILES", "GIT_DIR", "GIT_INDEX_FILE"):
            self.env.pop(k, None)
        self.env.update({
            "XDG_CONFIG_HOME": str(self.xdg), "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1",
            "GIT_CONFIG_GLOBAL": str(bos_gitconfig), "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.invalid",
            # install.py (ve kur.cmd → install.py) tarayici_hazirla.py'yi çağırır: testte gerçek npm kurulumu ve
            # GERÇEK ~/.playwright yazımı olmasın (HOME/USERPROFILE burada değiştirilmiyor).
            "AXET_TARAYICI_HAZIRLA": "0",
            # Z101: install.py (ve kur.cmd → install.py) eksik SAP Python paketlerini pip ile kurar: testte GERÇEK
            # pip çalışmasın, ağa çıkılmasın. Adımı ölçen testler (test_install.PaketAdimiTest) bunu kendisi kaldırır
            # ve AXET_PAKET_PIP ile sahte pip verir.
            "AXET_PAKET_KUR": "0",
        })
        kok = gecici_kok()
        if kok is not None and kok != Path(tempfile.gettempdir()).resolve():
            # Z96: sistem TMP'si repo içindeydi → test edilen betiklerin mkdtemp'i de repo dışı köke düşsün.
            self.env.update({"TMP": str(kok), "TEMP": str(kok), "TMPDIR": str(kok)})

    def tearDown(self) -> None:
        _sil(self.tmp)

    # --- çağırma ---------------------------------------------------------------------------------------------
    def calistir(self, script: str | Path, *args: str, cwd: Path | None = None, timeout: int = 300,
                 scripts_dir: Path = SCRIPTS) -> subprocess.CompletedProcess:
        yol = Path(script) if Path(script).is_absolute() else scripts_dir / script
        return subprocess.run([sys.executable, str(yol), *args], cwd=str(cwd or self.tmp), env=self.env,
                              capture_output=True, text=True, encoding="utf-8", errors="replace",
                              stdin=subprocess.DEVNULL, timeout=timeout)

    def git(self, dizin: Path, *args: str, kontrol: bool = True) -> subprocess.CompletedProcess:
        r = subprocess.run(["git", "-C", str(dizin), *args], env=self.env, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=300)
        if kontrol and r.returncode != 0:
            raise AssertionError(f"git {' '.join(args)} rc={r.returncode}: {r.stderr}")
        return r

    @staticmethod
    def cikti(r: subprocess.CompletedProcess) -> str:
        return (r.stdout or "") + (r.stderr or "")

    # --- kurulum ---------------------------------------------------------------------------------------------
    def proje(self, ad: str = "proje", sap: bool = False, git_init: bool = True) -> Path:
        d = self.tmp / ad
        shutil.copytree(_proje_kalibi(self, ad, sap, git_init), d)
        if sap:
            f = d / "sap-project.json"
            veri = json.loads(f.read_text(encoding="utf-8"))
            veri.update({"sap_profile": "s4_private", "release": "2023", "master_language": "TR",
                         "cleancore_policy": "balanced"})
            f.write_text(json.dumps(veri, indent=2, ensure_ascii=False), encoding="utf-8")
        return d

    def paket(self, proje: Path, ad: str = "ZSD001_CLC") -> Path:
        r = self.calistir("new_package.py", ad, "--title", "Deneme paketi", "--project-dir", str(proje))
        self.assertEqual(r.returncode, 0, self.cikti(r))
        return proje / "SOURCE_CODES" / "SD" / ad

    def global_config(self, sap: bool = False) -> Path:
        import install
        cfg: dict = {}
        install.apply_ours(cfg, install.load_rules(), sap)
        f = self.xdg / "axet-code" / "axet-code.json"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
        return f

    @staticmethod
    def yaz(yol: Path, metin: str, newline: str | None = "\n") -> Path:
        yol.parent.mkdir(parents=True, exist_ok=True)
        with open(yol, "w", encoding="utf-8", newline=newline) as fh:
            fh.write(metin)
        return yol


ABAP_TYPE_C = """CLASS zcl_sd001_helper DEFINITION PUBLIC FINAL CREATE PUBLIC.
  PUBLIC SECTION.
    METHODS get_description
      IMPORTING iv_id          TYPE c LENGTH 10
      RETURNING VALUE(rv_desc) TYPE string.
ENDCLASS.

CLASS zcl_sd001_helper IMPLEMENTATION.
  METHOD get_description.
    rv_desc = iv_id.
  ENDMETHOD.
ENDCLASS.
"""
ABAP_TEMIZ = ABAP_TYPE_C.replace("TYPE c LENGTH 10", "TYPE string")


def rg_siz_path(env: dict, sahte_rg: Path | None = None) -> dict:
    """PATH'ten rg taşıyan klasörler çıkarılır; sahte_rg verilirse (rg.cmd'nin klasörü) başa eklenir."""
    adlar = ("rg.exe", "rg.cmd", "rg.bat", "rg.com")
    anahtar = next(k for k in env if k.upper() == "PATH")
    parca = [d for d in env[anahtar].split(os.pathsep) if d and not any((Path(d) / a).exists() for a in adlar)]
    env = dict(env)
    env[anahtar] = os.pathsep.join(([str(sahte_rg)] if sahte_rg else []) + parca)
    return env
