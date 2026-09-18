# -*- coding: utf-8 -*-
"""MCP'siz paylaşılan altyapı: araç kayıt defteri + logger.

Kaynak çekirdekte bu dosya bir MCP sunucu örneği kuruyor ve `profil_tool` araçları sunucuya
kaydediyordu. Burada MCP YOK: `profil_tool` aracı yalnız yerel `REGISTRY`e yazar; profil
uygunluğu ÇAĞRI ANINDA (proje başına) CLI/gate tarafından denetlenir — tek süreç birden
çok projeye bakabildiği için import-anı gizleme burada doğru yer değildir.
"""
from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field

from sapadt import LIB_DIR, PKG_DIR  # noqa: F401  (sys.path'e lib/ eklenir)

# Reviewer zinciri (lib/validators/run_review.py) bu kökü kullanır.
REPO_ROOT = LIB_DIR

logging.basicConfig(
    level=os.getenv("AXET_SAP_LOG", "WARNING"),
    format="%(levelname)s [%(name)s] %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("sap-adt")
# urllib3 yeniden-deneme uyarıları her denemede host'u stderr'e basıyor; yalnız hata seviyesi kalsın.
logging.getLogger("urllib3").setLevel(logging.ERROR)


@dataclass
class ToolSpec:
    name: str
    fn: object
    available_on: tuple = ("all",)
    module: str = ""
    extra: dict = field(default_factory=dict)


REGISTRY: dict[str, ToolSpec] = {}


def profil_tool(available_on: tuple = ("all",)):
    """Aracı kayıt defterine yaz (MCP kaydı YOK). Fonksiyonu değiştirmeden döndürür."""

    def sarmalayici(fn):
        ad = getattr(fn, "__name__", "?")
        REGISTRY[ad] = ToolSpec(name=ad, fn=fn, available_on=tuple(available_on),
                                module=getattr(fn, "__module__", ""))
        return fn

    return sarmalayici


def load_all_tools() -> dict[str, ToolSpec]:
    """Araç modüllerini import et (dekoratörler REGISTRY'yi doldurur)."""
    from sapadt.tools import atom, composite, description, diag, meta, msgclass, query, screen  # noqa: F401
    return REGISTRY
