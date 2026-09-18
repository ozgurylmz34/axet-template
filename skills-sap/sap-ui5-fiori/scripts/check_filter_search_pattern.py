#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_filter_search_pattern.py — rapor/liste filtre + value-help + grid arama deseni (yerel; SAP'ye bağlanmaz).

BLOCKER: webapp JS'inde ya da XML binding'inde `caseSensitive: false` (anahtar tırnaklı da olabilir).
  Neden (canlı ölçüm, SAP Gateway /IWBEP): UI5 OData V2 bu bayrakla `$filter`'a toupper()/tolower() yazar →
  Gateway desteklemez → HTTP 400 → arama hiç sonuç döndürmez. Düz Contains/StartsWith/EndsWith
  ölçülen sistemde zaten harf duyarsızdı.
WARNING: adı "filter" içeren görünüm/fragment'ta value-help (valueHelpRequest) var ama hiç MultiInput yok →
  tek değerli Input; rapor filtre ekranı select-options pariteli olmalı (MultiInput + ValueHelpDialog, çoklu değer + aralık).

Kullanım:
  python check_filter_search_pattern.py <proje-ya-da-uygulama-klasörü> [--strict]
Çıkış: 0 temiz ya da yalnız WARNING · 1 BLOCKER (ya da --strict ile WARNING) · 2 ölçüm yok
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ui5scan as S  # noqa: E402

CASE_SENS = re.compile(r"""(["'`])?caseSensitive\1?\s*:\s*false""", re.I)
VH_REQ = re.compile(r"valueHelpRequest", re.I)
MULTI = re.compile(r"<(\w+:)?MultiInput\b")

BAKILMAYANLAR = [
    "değişkenle kurulan filtre bayrağı (`caseSensitive: bFlag`) ve `new Filter({...})` nesnesinin çalışma zamanı değeri",
    "wildcard yorumlaması (_parseSearchTerm: x* / *x / *x*) ve varsayılan operatör — kod incelemesi",
    "adı 'filter' içermeyen seçim ekranları (tek değerli Input uyarısı yalnız bu adlarda)",
    "backend tarafı (`$filter` fonksiyon desteği, DPC'de süzme) — sap-odata-backend filter-search",
]


def js_tara(metin: str) -> list[tuple[int, str]]:
    return [(no, kod.strip()) for no, kod in S.js_kod_satirlari(metin) if CASE_SENS.search(kod)]


def xml_tara(metin: str) -> list[int]:
    t = S.xml_yorumsuz(metin)
    return [t.count("\n", 0, m.start()) + 1 for m in CASE_SENS.finditer(t)]


def filtre_gorunumu_mu(ad: str) -> bool:
    ad = ad.lower()
    return "filter" in ad and (ad.endswith(".view.xml") or ad.endswith(".fragment.xml"))


def main() -> int:
    S.utf8_konsol()
    ap = argparse.ArgumentParser(description="Filtre/VH/grid arama deseni kontrolü")
    ap.add_argument("yol")
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args()
    kok = S.yol_dogrula(a.yol)
    kapsam = S.Kapsam("webapp .js/.xml dosyası", BAKILMAYANLAR)
    blocker, warning = [], []
    for f in kapsam.say(S.webapp_dosyalari(kok, (".js", ".xml"))):
        metin = f.read_text(encoding="utf-8", errors="replace")
        if f.suffix.lower() == ".js":
            for no, kod in js_tara(metin):
                blocker.append((f, no, kod[:90]))
            continue
        for no in xml_tara(metin):
            blocker.append((f, no, "caseSensitive: false (XML binding)"))
        if filtre_gorunumu_mu(f.name):
            t = S.xml_yorumsuz(metin)
            if VH_REQ.search(t) and not MULTI.search(t):
                warning.append(f)
    if kapsam.sayi == 0:
        return S.olcum_yok(kapsam)
    for f, no, kod in blocker:
        print(f"[İHLAL] {S.goreli(f, kok)}:{no}  BLOCKER: caseSensitive:false → V2 toupper/tolower → Gateway 400. "
              f"new Filter(yol, FilterOperator.Contains, q) — bayrak VERME. → {kod}")
    for f in warning:
        print(f"[UYARI] {S.goreli(f, kok)}  WARNING: filtre ekranında value-help var ama MultiInput yok → "
              "select-options için MultiInput + ValueHelpDialog (çoklu değer + aralık).")
    print()
    kapsam.bas()
    print(f"\nSONUÇ: {len(blocker)} BLOCKER, {len(warning)} WARNING.")
    if blocker or (warning and a.strict):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
