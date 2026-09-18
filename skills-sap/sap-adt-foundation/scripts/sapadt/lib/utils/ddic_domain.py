# -*- coding: utf-8 -*-
"""DDIC domain çıktı uzunluğu — TEK KAYNAK (aXet 2026-09-13).

Kullananlar (kopya YOK): `lib/validators/check_domain_output_length.py` (reviewer zinciri
`domain_creation_csv`), `lib/sap_adt_lib.py::create_domain` (POST gövdesindeki
`<doma:outputInformation><doma:length>`), `sapadt/tools/composite.py::adt_domain_create` (ağ öncesi
argüman kontrolü `steps.pre_flight`).

KURAL (kaynak çekirdek `playbook/adt-domain-dtel.md:131-140` §26.1.1 + `scripts/populate_domains.py:169-191`):
  CHAR/NUMC/DATS/TIMS/CLNT → çıktı uzunluğu = length
  INT1 → 4 · INT2 → 6 · INT4 → 11 · INT8 → 20
  DEC/QUAN/CURR → length + 4 (işaret + ondalık ayırıcı + binlik ayırıcılar)
Yanlış değer: aktivasyonda "Output length (15) is less than the calculated output length (19)" +
ekranda değer kesilmesi (`playbook/adt-domain-dtel.md:125-129`).

FORMUL_TIPLERI dışındaki tip için formül KAYNAKTA YOK: `check_domain_output_length.py` bunları
"Bilinmeyen datatype" ihlali sayar; `expected_output_length` geriye dönük uyum için `length` döndürür
ama çağıranlar (validator, composite ön kontrolü) bu tipleri ayrıca reddeder.
"""
from __future__ import annotations

FORMUL_TIPLERI = ("CHAR", "NUMC", "DATS", "TIMS", "CLNT",
                  "INT1", "INT2", "INT4", "INT8",
                  "DEC", "QUAN", "CURR")

_SABIT = {"INT1": 4, "INT2": 6, "INT4": 11, "INT8": 20}
_ARTI_DORT = ("DEC", "QUAN", "CURR")


def expected_output_length(datatype: str, length: int, decimals: int = 0) -> int:
    """SAP'nin domain output length formülü (bkz. modül başlığı)."""
    dt = (datatype or "").upper()
    if dt in _SABIT:
        return _SABIT[dt]
    if dt in _ARTI_DORT:
        return length + 4
    return length


def formul_tanimli_mi(datatype) -> bool:
    return isinstance(datatype, str) and datatype.strip().upper() in FORMUL_TIPLERI
