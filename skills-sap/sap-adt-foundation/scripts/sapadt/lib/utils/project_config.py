# -*- coding: utf-8 -*-
"""project_config — proje kimliğinin TEK okuma noktası (validator'lar için).

aXet uyarlaması (kaynak çekirdekte `project.yaml` + önekli ortam değişkenleri + IDE'nin proje-dizini env'i idi):
  • Proje kökü: env `AXET_SAP_PROJECT_DIR` (CLI basar) → cwd.
  • Proje değerleri: proje kökündeki `sap-project.json`.
  • Env ile değer EZME (kaynak çekirdekte `<ÖNEK>_<KEY>`) KALDIRILDI: validator'lar CLI'nin alt süreci olarak koşar
    ve ortamı miras alır; env ile profil/dil ezmek kapıyı gevşetme yoluydu.

Bu modül `sapadt` paketini import ETMEZ (validator'lar ayrı süreçte yalnız `lib/`i yol'a
ekler); `sapadt/project.py` ile aynı kuralları küçük bir kopya olarak taşır.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

_SAP_PROJECT_FILE = "sap-project.json"
_DIL = re.compile(r"^[A-Za-z]{2}$")


def project_root() -> Path:
    env = os.environ.get("AXET_SAP_PROJECT_DIR")
    return Path(env) if env else Path.cwd()


def _load() -> dict:
    p = project_root() / _SAP_PROJECT_FILE
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:  # noqa: BLE001
        return {}
    return data if isinstance(data, dict) else {}


def cfg(key: str, default=None):
    """sap-project.json değeri (yoksa default)."""
    return _load().get(key, default)


def has_project_config() -> bool:
    return (project_root() / _SAP_PROJECT_FILE).is_file()


# Kaynak çekirdekle ad uyumu (bazı validator'lar bu adı kullanabilir).
has_project_yaml = has_project_config


def source_root_name() -> str:
    """Kaynak-kod klasörü adı: sap-project.json `source_root` → mevcut `SOURCE_CODES` → fallback."""
    v = cfg("source_root")
    if isinstance(v, str) and v.strip():
        return v.strip()
    return "SOURCE_CODES"


def source_dir() -> Path:
    return project_root() / source_root_name()


def sap_profile() -> str | None:
    v = cfg("sap_profile")
    return str(v) if isinstance(v, str) and v.strip() else None


def master_language() -> str | None:
    """sap-project.json `master_language` (iki harf, büyük). Geçersizse None — UYDURULMAZ."""
    v = cfg("master_language")
    if isinstance(v, str) and _DIL.match(v.strip()):
        return v.strip().upper()
    return None


SOURCE_ROOT_NAME = source_root_name()
