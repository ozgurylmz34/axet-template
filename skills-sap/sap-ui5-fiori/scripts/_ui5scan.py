#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_ui5scan.py — sap-ui5-fiori statik kontrollerinin ORTAK yardımcıları (stdlib).

Tek başına çalıştırılmaz; aynı klasördeki `check_*.py` script'leri içe aktarır.
  • webapp_dosyalari(kok, uzantilar) — `webapp` ağacı altındaki dosyalar (node_modules/dist/test/.git budanır)
  • js_kod_satirlari(metin)          — JS'te yorumlar (// ve çok satırlı /* */) boşaltılmış satırlar; string içeriği KORUNUR
  • xml_yorumsuz(metin)               — XML'de <!-- --> yorumları boşaltılır, satır numaraları korunur
  • Kapsam                            — "taranan N dosya" + "BAKILMAYANLAR" beyanı (0 dosya = ÖLÇÜM YOK, temiz değil)
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

BUDANAN = {"node_modules", "dist", ".git", ".tmp", "tmp", "test", "localservice", ".axet-code", "coverage"}


def utf8_konsol() -> None:
    for akis in (sys.stdout, sys.stderr):
        try:
            akis.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass


def webapp_dosyalari(kok: Path, uzantilar: tuple[str, ...]) -> list[Path]:
    """`kok` altında, yolunda bir `webapp` klasörü bulunan ve uzantısı eşleşen dosyalar (sıralı)."""
    kok = Path(kok)
    if kok.is_file():
        return [kok] if kok.name.lower().endswith(uzantilar) else []
    bulunan: list[Path] = []
    for dizin, altlar, dosyalar in os.walk(kok):
        altlar[:] = [a for a in altlar if a.lower() not in BUDANAN]
        parcalar = {p.lower() for p in Path(dizin).parts}
        if "webapp" not in parcalar:
            continue
        for ad in dosyalar:
            if ad.lower().endswith(uzantilar):
                bulunan.append(Path(dizin) / ad)
    return sorted(bulunan)


def js_kod_satirlari(metin: str) -> list[tuple[int, str]]:
    """[(satır_no, kod)] — yorum karakterleri boşlukla değiştirilir; string/template literal içeriği korunur.

    Durum dosya genelinde tutulur (çok satırlı `/* */` bloğunun içi kod sayılmaz).
    Sınır: regex literali (`/"/`) ayırt edilmez — nadir; yanlış eşleşmede bulgu satırı ham satırla basılır.
    """
    cikti = []
    durum = None  # None | '//' | '/*' | '"' | "'" | '`'
    i, n = 0, len(metin)
    buf = []
    while i < n:
        c = metin[i]
        s = metin[i + 1] if i + 1 < n else ""
        if durum is None:
            if c == "/" and s == "/":
                durum = "//"
                buf.append("  ")
                i += 2
                continue
            if c == "/" and s == "*":
                durum = "/*"
                buf.append("  ")
                i += 2
                continue
            if c in "\"'`":
                durum = c
            buf.append(c)
        elif durum == "//":
            if c == "\n":
                durum = None
                buf.append(c)
            else:
                buf.append(" ")
        elif durum == "/*":
            if c == "*" and s == "/":
                durum = None
                buf.append("  ")
                i += 2
                continue
            buf.append(c if c == "\n" else " ")
        else:  # string / template literal
            if c == "\\" and i + 1 < n:
                buf.append(c + s)
                i += 2
                continue
            if c == durum:
                durum = None
            elif c == "\n" and durum != "`":
                durum = None  # kapanmamış tek satırlık string: satır sonunda bırak
            buf.append(c)
        i += 1
    for no, satir in enumerate("".join(buf).split("\n"), 1):
        cikti.append((no, satir))
    return cikti


_XML_YORUM = re.compile(r"<!--.*?-->", re.S)


def xml_yorumsuz(metin: str) -> str:
    """<!-- --> bloklarını aynı sayıda satır sonu bırakarak boşaltır (satır numaraları değişmez)."""
    return _XML_YORUM.sub(lambda m: "\n" * m.group(0).count("\n"), metin)


class Kapsam:
    """Taranan dosya paydası + bakılmayan yüzey beyanı. Her koşumda basılır."""

    def __init__(self, birim: str, bakilmayanlar: list[str]):
        self.birim = birim
        self.bakilmayanlar = bakilmayanlar
        self.sayi = 0

    def say(self, dosyalar):
        for d in dosyalar:
            self.sayi += 1
            yield d

    def bas(self) -> None:
        print(f"KAPSAM: {self.sayi} {self.birim} tarandı.")
        print("BAKILMAYANLAR (bu araç şunları ÖLÇMEZ):")
        for madde in self.bakilmayanlar:
            print(f"  - {madde}")


def yol_dogrula(yol: str) -> Path:
    p = Path(yol)
    if not p.exists():
        print(f"[FAIL] yol yok: {p} (çözülen: {p.resolve()}) — ÖLÇÜM YOK (exit 2)")
        sys.exit(2)
    return p


def olcum_yok(kapsam: Kapsam) -> int:
    kapsam.bas()
    print("\nÖLÇÜM YOK — 'temiz' DEĞİL: verilen yolda `webapp` altında taranacak dosya bulunamadı (exit 2).")
    return 2


def goreli(p: Path, kok: Path) -> str:
    try:
        return p.relative_to(kok if kok.is_dir() else kok.parent).as_posix()
    except ValueError:
        return p.as_posix()
