#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sap_adt_populate.py — CSV/dizinden toplu SAP obje yazımı (aXet). Mantık: `sapadt/populate.py`.

    python sap_adt_populate.py domain --csv domains.csv --package <PKG> --transport <TR> \
        --sap-write --scope S1 --reason "<tek satır gerekçe>" [--dry-run] [--fail-on-skip]
    python sap_adt_populate.py dtel   --csv dataelements.csv ...
    python sap_adt_populate.py cds    --source-dir <dizin> ... [--force-recreate --only <TEK AD>]
    python sap_adt_populate.py enqu   --csv lock_objects.csv ...
    python sap_adt_populate.py msag   --name <SINIF> --description "<açıklama>" --csv messages.csv ... [--allow-overwrite]

Her adım `sap_adt_cli.calistir` ile koşar (aynı yazma kapısı, reviewer, write-log). Yazmadan önce tüm planlı
çağrılar kapıdan geçirilir. Çıkış: 0 tamam · 1 hata/işlenmeyen var · 2 ön geçiş kapı reddi · 3 kullanım/girdi ·
4 atlanan var ve --fail-on-skip.
"""
from __future__ import annotations

import sys
from pathlib import Path

for _akis in (sys.stdout, sys.stderr):
    try:
        _akis.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

if __name__ == "__main__":
    from sapadt.populate import main
    sys.exit(main())
