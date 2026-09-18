#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_list_view_grid.py — liste/rapor görünümü `sap.ui.table.Table` (grid) mı? (yerel; SAP'ye bağlanmaz)

Kural (SAP çekirdeği, liste ekranı ALV paritesi): UI5'te liste/rapor ekranı grid ile yapılır; `sap.m.Table`
yalnız mobil öncelikli ya da hücre-zengin istisnadır.

Temkinli tespit — İHLAL için ÜÇ koşulun hepsi:
  (a) dosya adı list / report / liste / rapor içeriyor (büyük-küçük harf duyarsız) ve `.view.xml`
  (b) görünümde gerçek bir `sap.m` Table etiketi var
  (c) görünümün hiçbir yerinde `sap.ui.table` ad alanı yok (XML yorumları ayıklanır)
Detay/düzenleme formundaki kalem tablosu ve tablosuz belge listesi işaretlenmez (yanlış pozitif yerine
nadir kaçırma tercih edilir).

Kullanım:
  python check_list_view_grid.py <proje-ya-da-uygulama-klasörü>
Çıkış: 0 ihlal yok · 1 ihlal · 2 ölçüm yok (yol yok / 0 görünüm)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ui5scan as S  # noqa: E402

LISTE_ADI = re.compile(r"list|report|liste|rapor", re.I)
UI_TABLE_NS = re.compile(r"sap\.ui\.table", re.I)
M_TABLE = re.compile(r"<(\w+:)?Table\b")
KOLON = re.compile(r"<(\w+:)?Column\b")

BAKILMAYANLAR = [
    "adı list/report/liste/rapor içermeyen görünümler ve fragment'lar (adlandırma sinyali yoksa atlanır)",
    "ALV paritesinin diğer maddeleri: kolon göster/gizle, varyant, Excel (tüm filtreli satırlar), operatörlü filtre — kontrol listesi",
    "grid'in doğru kurulumu (rows binding, sortProperty/filterProperty, rowMode) — kod incelemesi",
    "`sap.m.Table`'ın meşru mobil/hücre-zengin istisna olup olmadığı — kullanıcı kararı",
]


def gorunum_tara(ad: str, metin: str) -> list[int]:
    metin = S.xml_yorumsuz(metin)
    if UI_TABLE_NS.search(metin) or not LISTE_ADI.search(ad):
        return []
    m = M_TABLE.search(metin)
    if not m:
        return []
    return [metin.count("\n", 0, m.start()) + 1]


def main() -> int:
    S.utf8_konsol()
    ap = argparse.ArgumentParser(description="Liste/rapor görünümü grid (sap.ui.table) kontrolü")
    ap.add_argument("yol", help="proje kökü, paket ui/ klasörü, uygulama klasörü ya da tek .view.xml")
    a = ap.parse_args()
    kok = S.yol_dogrula(a.yol)
    kapsam = S.Kapsam(".view.xml görünümü (webapp altında)", BAKILMAYANLAR)
    ihlal = 0
    for f in kapsam.say(S.webapp_dosyalari(kok, (".view.xml",)) if kok.is_dir() else [kok]):
        metin = f.read_text(encoding="utf-8", errors="replace")
        for no in gorunum_tara(f.name, metin):
            ihlal += 1
            print(f"[İHLAL] {S.goreli(f, kok)}:{no}  liste/rapor görünümü sap.m.Table kullanıyor "
                  f"({len(KOLON.findall(metin))} kolon), sap.ui.table yok → grid + kolon göster/gizle + varyant + Excel.")
    if kapsam.sayi == 0:
        return S.olcum_yok(kapsam)
    print()
    kapsam.bas()
    print(f"\nSONUÇ: {ihlal} ihlal." if ihlal else "\nSONUÇ: liste görünümü grid ihlali yok (yalnız yukarıdaki kapsam için).")
    return 1 if ihlal else 0


if __name__ == "__main__":
    raise SystemExit(main())
