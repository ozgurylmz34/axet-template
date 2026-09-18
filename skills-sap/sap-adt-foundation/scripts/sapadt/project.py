# -*- coding: utf-8 -*-
"""Proje kökü + `sap-project.json` + `.conn_adt` okuma — TEK kaynak.

Proje kökü: `AXET_SAP_PROJECT_DIR` (CLI `--project-dir`/cwd'den kendisi basar) → cwd.
`sap-project.json` proje kökündedir:
    {"sap_profile": "ecc|s4_private|s4_public|btp_abap", "release": "...",
     "master_language": "TR|EN|...", "cleancore_policy": "..."}

FAIL-CLOSED: dosya yok / JSON değil / nesne değil / `sap_profile` enum dışı /
`master_language` iki harf değil → `load_sap_project` hata döner; çağıran (CLI/gate)
yalnız `--list` ve `ping`e izin verir.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

PROJECT_ENV = "AXET_SAP_PROJECT_DIR"
SAP_PROJECT_FILE = "sap-project.json"
CONN_FILE = ".conn_adt"

GECERLI_PROFILLER = ("ecc", "s4_private", "s4_public", "btp_abap")
_DIL = re.compile(r"^[A-Za-z]{2}$")


def project_dir(explicit: str | os.PathLike | None = None) -> Path:
    """Proje kökü: açık parametre → env AXET_SAP_PROJECT_DIR → cwd."""
    if explicit:
        return Path(explicit).resolve()
    env = os.environ.get(PROJECT_ENV)
    return Path(env).resolve() if env else Path.cwd().resolve()


def conn_path(proj: str | os.PathLike | None = None) -> Path:
    return project_dir(proj) / CONN_FILE


def load_sap_project(proj: str | os.PathLike | None = None) -> tuple[dict | None, str | None]:
    """(config, hata). Hata varsa config None'dır (fail-closed)."""
    p = project_dir(proj) / SAP_PROJECT_FILE
    if not p.is_file():
        return None, f"{SAP_PROJECT_FILE} yok ({p})"
    try:
        # utf-8-sig: PowerShell'in eklediği BOM ilk anahtarı bozmasın.
        data = json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception as exc:  # noqa: BLE001
        return None, f"{SAP_PROJECT_FILE} geçersiz JSON ({type(exc).__name__}: {exc})"
    if not isinstance(data, dict):
        return None, f"{SAP_PROJECT_FILE} geçersiz: kök bir JSON nesnesi değil"
    profil = data.get("sap_profile")
    if not isinstance(profil, str) or profil not in GECERLI_PROFILLER:
        return None, (f"{SAP_PROJECT_FILE} geçersiz: sap_profile={profil!r} "
                      f"(geçerli: {', '.join(GECERLI_PROFILLER)})")
    dil = data.get("master_language")
    if not isinstance(dil, str) or not _DIL.match(dil.strip()):
        return None, (f"{SAP_PROJECT_FILE} geçersiz: master_language={dil!r} "
                      "(iki harfli dil anahtarı bekleniyor, ör. TR/EN)")
    for anahtar in ("release", "cleancore_policy"):
        if anahtar in data and not isinstance(data[anahtar], str):
            return None, f"{SAP_PROJECT_FILE} geçersiz: {anahtar} metin olmalı"
    out = dict(data)
    out["master_language"] = dil.strip().upper()
    return out, None


def conn_line_value(line: str, key: str) -> str | None:
    """`.conn_adt` satırından değer — TAM anahtar eşleşmesi (önek gaspı yok)."""
    s = line.strip()
    if not s or s.startswith("#") or "=" not in s:
        return None
    k, v = s.split("=", 1)
    if k.strip() != key:
        return None
    return v.strip()


def conn_file_values(key: str, proj: str | os.PathLike | None = None) -> list[str]:
    """`.conn_adt` içinde `key`in TÜM (boş olmayan) değerleri, dosya sırasıyla."""
    p = conn_path(proj)
    if not p.is_file():
        return []
    out = []
    for ln in p.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        v = conn_line_value(ln, key)
        if v:
            out.append(v)
    return out


def conn_file_last(key: str, proj: str | os.PathLike | None = None) -> str | None:
    """SON-KAZANIR (istemcinin dotenv okumasıyla aynı politika)."""
    vals = conn_file_values(key, proj)
    return vals[-1] if vals else None


def effective_conn_value(key: str, default: str | None = None,
                         proj: str | os.PathLike | None = None) -> str | None:
    """İstemcinin FİİLEN kullanacağı değer.

    ÖLÇÜLDÜ (lib/sap_adt_lib.py modül gövdesi): `.conn_adt` `load_dotenv(override=False)` ile
    yüklenir ⇒ ortamda ANAHTAR ZATEN VARSA (boş dize dahil) dosyadaki değer onu EZMEZ.
    Bu fonksiyon o kuralı taklit eder: env'de anahtar varsa env, yoksa dosyanın son değeri.
    """
    if key in os.environ:
        return os.environ[key]
    v = conn_file_last(key, proj)
    return v if v is not None else default
