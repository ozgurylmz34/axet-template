#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_ui5_freestyle_traps.py — freestyle UI5 + OData V2 STATİK tuzak kontrolü (yerel; SAP'ye bağlanmaz).

Tuzaklar (her biri gerçek bir geliştirmede kullanıcı testine kadar görünmeyen hata oldu):
  T1 ERROR  V2 navigasyon adı `_X` — RAP composition `_Item` OData V2 `$metadata`'da `to_Item` olur.
            createEntry("_X") · $expand: "_X" · ".../_X" yol segmenti → kaydetme/expand SESSİZCE kırılır.
  T2 WARN   `<Input ... type="Number">` — ok tuşu değeri değiştirir, grid satır gezmesini bozar →
            type="Text" + liveChange sayısal filtre. (Filtre ekranındaki "kaç kayıt" sayacı meşru istisna.)
  T3 WARN   `<core:Title>` — VBox/HBox/CSSGrid çocuğu olarak geçersiz agregasyon → render çöker; sap.m.Title kullan.
            (Form içinde geçerli olduğu için WARN.)
  T4 ERROR  `<f:fields>` (sap.ui.layout.form) içinde HBox/VBox/FlexBox/Panel — geçersiz form içeriği →
            diyalog/görünüm AÇILMAZ. XML geçerli olduğu için sözdizimi kontrolü yakalamaz.

Kullanım:
  python check_ui5_freestyle_traps.py <proje-ya-da-uygulama-klasörü> [--strict]
Çıkış: 0 ERROR yok (WARN olabilir; --strict ile WARN de 1) · 1 ERROR var · 2 ölçüm yok (yol yok / 0 dosya)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ui5scan as S  # noqa: E402

T1_DESENLER = [
    re.compile(r'createEntry\(\s*["\'`]_[A-Z]'),
    re.compile(r'/_[A-Z]'),
    re.compile(r'\$expand["\'`]?\s*:\s*["\'`]_[A-Z]'),
]
T2_NUMBER = re.compile(r'type\s*=\s*"Number"')
T3_CORE_TITLE = re.compile(r'<core:Title\b')
T4_FIELDS = re.compile(r'<(?:\w+:)?fields\b[^>]*>(.*?)</(?:\w+:)?fields\s*>', re.S)
T4_KAP = re.compile(r'<(?:\w+:)?(HBox|VBox|FlexBox|Panel)\b')
ETIKET_ADI = re.compile(r'<\s*([\w.]+:)?([\w.]+)')

BAKILMAYANLAR = [
    "çalışma zamanı davranışı (kaydetme sırası, setData şekli, eşzamanlı update, boş tarih \"\") — runtime smoke + kontrol listesi",
    "canlı $metadata ile ad eşleşmesi (to_X gerçekten var mı) — check_ui_odata_refs.py",
    "Component.js dışındaki özel yardımcı kütüphanelerin çalışma zamanı etkisi; dinamik üretilen yollar (değişkenle kurulan '/_' + ad)",
    "regex literali içindeki tırnaklar (JS yorum ayıklayıcısı ayırt etmez)",
]


def t2_input_mi(metin: str, konum: int) -> bool:
    """type="Number" eşleşmesinin ait olduğu etiket Input mu (XML'de değer içinde '<' kaçışsızdır)."""
    bas = metin.rfind("<", 0, konum)
    if bas < 0:
        return True
    m = ETIKET_ADI.match(metin, bas)
    return bool(m and m.group(2).endswith("Input"))


def tara(kok: Path, kapsam: S.Kapsam) -> list[tuple]:
    bulgular = []
    for f in kapsam.say(S.webapp_dosyalari(kok, (".js", ".xml"))):
        try:
            ham = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        satirlar = ham.splitlines()
        if f.suffix.lower() == ".js":
            for no, kod in S.js_kod_satirlari(ham):
                if kod.strip() and any(p.search(kod) for p in T1_DESENLER):
                    bulgular.append(("ERROR", "T1 V2 nav `_X` → `to_X`", f, no, satirlar[no - 1].strip()[:120]))
            continue
        metin = S.xml_yorumsuz(ham)
        for m in T2_NUMBER.finditer(metin):
            if t2_input_mi(metin, m.start()):
                no = metin.count("\n", 0, m.start()) + 1
                bulgular.append(("WARN", "T2 Input type=Number (grid/miktar ise → type=Text + liveChange)", f, no,
                                 satirlar[no - 1].strip()[:120]))
        for m in T3_CORE_TITLE.finditer(metin):
            no = metin.count("\n", 0, m.start()) + 1
            bulgular.append(("WARN", "T3 core:Title (VBox/HBox/CSSGrid çocuğuysa render çöker → sap.m.Title)", f, no,
                             satirlar[no - 1].strip()[:120]))
        for m in T4_FIELDS.finditer(metin):
            k = T4_KAP.search(m.group(1))
            if k:
                no = metin.count("\n", 0, m.start(1) + k.start()) + 1
                bulgular.append(("ERROR", f"T4 <f:fields> içinde <{k.group(1)}> (geçersiz form içeriği → açılmaz)", f, no,
                                 k.group(0)))
    return bulgular


def main() -> int:
    S.utf8_konsol()
    ap = argparse.ArgumentParser(description="Freestyle UI5 + OData V2 statik tuzak kontrolü")
    ap.add_argument("yol", help="proje kökü, paket ui/ klasörü ya da tek uygulama klasörü")
    ap.add_argument("--strict", action="store_true", help="WARN'ları da başarısız say")
    a = ap.parse_args()
    kok = S.yol_dogrula(a.yol)
    kapsam = S.Kapsam("webapp .js/.xml dosyası", BAKILMAYANLAR)
    bulgular = tara(kok, kapsam)
    if kapsam.sayi == 0:
        return S.olcum_yok(kapsam)
    for sev, tuzak, f, no, metin in bulgular:
        print(f"[{'İHLAL' if sev == 'ERROR' else 'UYARI'}] {S.goreli(f, kok)}:{no}  {tuzak}  → {metin}")
    hata = sum(1 for b in bulgular if b[0] == "ERROR")
    uyari = len(bulgular) - hata
    print()
    kapsam.bas()
    print(f"\nSONUÇ: {hata} ERROR (T1/T4), {uyari} WARN (T2/T3)." if bulgular else
          "\nSONUÇ: T1-T4 bulgusu yok (yalnız yukarıdaki kapsam için).")
    if hata or (uyari and a.strict):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
