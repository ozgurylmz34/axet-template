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
        _KALIP_KOK = Path(tempfile.mkdtemp(prefix="axet-kalip-")).resolve()
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
        self.tmp = Path(tempfile.mkdtemp(prefix="axet-test-")).resolve()
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
        })

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
