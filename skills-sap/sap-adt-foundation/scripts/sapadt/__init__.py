# -*- coding: utf-8 -*-
"""sapadt — SAP ADT araç katmanı (MCP'siz). Tek giriş noktası: ../sap_adt_cli.py

Yapı:
  sapadt/            araç sarmalayıcıları + kapı (gate.py) + guard'lar
  sapadt/tools/      araç fonksiyonları (atom / composite / query / meta)
  sapadt/lib/        düz modüller: sap_adt_lib, sap_client, object_types, auth/, utils/,
                     validators/ (reviewer zinciri). Bu dizin import anında sys.path'e eklenir;
                     kopyalanan kodun düz import'ları (`import sap_adt_lib`) böylece değişmeden çalışır.

⛔ KURAL: `sapadt` içindeki yazma metodlarını (create_*/push/activate/delete/lock) kapıdan
(`sapadt.gate.check_write`) geçmeden çağıran script repoya girmez. Bkz. IMPLEMENTATION.md.
"""
from __future__ import annotations

import sys
from pathlib import Path

__version__ = "0.1.0"

PKG_DIR = Path(__file__).resolve().parent
LIB_DIR = PKG_DIR / "lib"
SCRIPTS_DIR = PKG_DIR.parent

if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))
