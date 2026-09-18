# -*- coding: utf-8 -*-
"""Çevrimdışı test yardımcıları.

⛔ Gerçek SAP'ye bağlanılmaz: fixture `.conn_adt` erişilemeyen `http://127.0.0.1:9` gösterir.
⛔ Gerçek `<repo>/config/` altına dosya yazılmaz: yazma opt-in testleri için `scripts/`
   ağacı geçici bir AXET_HOME'a KOPYALANIR (CLI AXET_HOME'u kendi konumundan türetir; env kancası YOK).
Fixture dosyaları çalışma anında `tempfile` altında üretilir; repoya `.conn*` dosyası konmaz.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
FOUNDATION = TESTS_DIR.parent
SKILLS_SAP = FOUNDATION.parent
SCRIPTS = FOUNDATION / "scripts"
INTAKE_SCRIPTS = SKILLS_SAP / "sap-intake-triage" / "scripts"

PAROLA = "S3cr3t-Parola!9"
KULLANICI = "AXETTEST"
SAHTE_URL = "http://127.0.0.1:9"
SAP_PROJECT_OK = {"sap_profile": "s4_private", "release": "2025",
                  "master_language": "TR", "cleancore_policy": "balanced"}

# Senaryo → beklenen → gerçekleşen tablosu (run_tests.py basar).
SONUCLAR: list[tuple[str, str, str, bool]] = []

_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc")


def build_home(root: Path, optin: bool) -> Path:
    home = root / ("home_optin" if optin else "home_nooptin")
    shutil.copytree(SCRIPTS, home / "skills-sap" / "sap-adt-foundation" / "scripts", ignore=_IGNORE)
    shutil.copytree(INTAKE_SCRIPTS, home / "skills-sap" / "sap-intake-triage" / "scripts", ignore=_IGNORE)
    (home / "config").mkdir(parents=True, exist_ok=True)
    if optin:
        (home / "config" / "sap-write.local").write_text("test opt-in\n", encoding="utf-8")
    return home


def make_project(root: Path, name: str, *, tier_lines=("ADT_SAP_TIER=DEV",), language="TR",
                 sap_project=SAP_PROJECT_OK, extra_lines=()) -> Path:
    p = root / name
    p.mkdir(parents=True, exist_ok=False)
    satirlar = ["# test fixture — sahte, erişilemeyen sistem",
                f"ADT_SAP_URL={SAHTE_URL}", f"ADT_SAP_USER={KULLANICI}",
                f"ADT_SAP_PASSWORD={PAROLA}", "ADT_SAP_CLIENT=100",
                f"ADT_SAP_LANGUAGE={language}", *tier_lines, *extra_lines]
    (p / ".conn_adt").write_text("\n".join(satirlar) + "\n", encoding="utf-8")
    if sap_project is not None:
        metin = sap_project if isinstance(sap_project, str) else json.dumps(sap_project)
        (p / "sap-project.json").write_text(metin, encoding="utf-8")
    return p


def clean_env(extra: dict | None = None) -> dict:
    env = {k: v for k, v in os.environ.items()
           if not (k.upper().startswith("ADT_") or k.upper().startswith("AXET_")
                   or k.upper() in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"))}
    env["NO_PROXY"] = "127.0.0.1,localhost"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    if extra:
        env.update(extra)
    return env


def run_cli(home: Path, argv: list, *, project: Path | None = None, env_extra: dict | None = None,
            timeout: int = 240):
    cli = home / "skills-sap" / "sap-adt-foundation" / "scripts" / "sap_adt_cli.py"
    cmd = [sys.executable, str(cli), *argv]
    if project is not None:
        cmd += ["--project-dir", str(project)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=clean_env(env_extra), timeout=timeout, stdin=subprocess.DEVNULL,
                       cwd=str(project or home))
    try:
        data = json.loads(r.stdout)
    except (json.JSONDecodeError, TypeError):
        data = None
    return r.returncode, data, r.stdout, r.stderr


def kaydet(ad: str, beklenen: str, gerceklesen: str, ok: bool) -> None:
    SONUCLAR.append((ad, beklenen, gerceklesen, ok))
