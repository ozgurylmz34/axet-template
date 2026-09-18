# -*- coding: utf-8 -*-
"""Test yardımcıları — geçici dizinler, izole git/aXet ortamı, script çağırma. Gerçek global config'e ve
template klonunun dosyalarına yazılmaz."""
from __future__ import annotations

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
        d.mkdir()
        if git_init:
            self.git(d, "init", "-q", "-b", "main")
        r = self.calistir("new_project.py", str(d), *(["--sap"] if sap else []))
        self.assertEqual(r.returncode, 0, self.cikti(r))
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
