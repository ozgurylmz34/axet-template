#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_i18n_keys.py — kodda kullanılan i18n anahtarları tüm i18n dosyalarında tanımlı mı? (yerel; SAP'ye bağlanmaz)

Neden: `data-sap-ui-language="tr"` ile çalışan uygulama `i18n_tr.properties`'i yükler; anahtar orada yoksa temel
dosyaya düşer (İngilizce ya da diyakritiksiz metin görünür), temel dosyada da yoksa ham anahtar ("btn.cols") görünür.
Etiket değişikliği yalnız bir dosyada yapılınca kullanıcı eski metni görür.

Her `webapp` için:
  ERROR  referans verilen anahtar temel `i18n/i18n.properties`'te yok
  ERROR  referans verilen anahtar bir dil dosyasında yok (dil dosyaları: manifest `supportedLocales`'taki diller;
         manifestte liste yoksa diskteki `i18n_*.properties`). `--locale-optional` ile WARN'a iner
         (çeviri süreci dil dosyalarını üretiyorsa)
  WARN   aynı anahtarda `{0}` yer tutucu kümesi temel ↔ dil dosyası farklı
  WARN   yer tutuculu metinde tek kesme işareti (MessageFormat'ta `'` kaçış karakteridir → `''` yazılır)
Referanslar: XML `{i18n>anahtar}` / `${i18n>anahtar}` · manifest `{{anahtar}}` · JS `getText("anahtar"` ve
`--js-helper` ile verilen yardımcı adları (varsayılan: _txt, _t, _getText).

Kullanım:
  python check_i18n_keys.py <proje-ya-da-uygulama-klasörü> [--locale-optional] [--js-helper _msg]
Çıkış: 0 ERROR yok · 1 ERROR var · 2 ölçüm yok (yol yok / i18n'li webapp yok)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ui5scan as S  # noqa: E402

XML_REF = re.compile(r"\$?\{\s*i18n>([\w.\-]+)\s*\}")
MANIFEST_REF = re.compile(r"\{\{([\w.\-]+)\}\}")
YER_TUTUCU = re.compile(r"\{(\d+)\}")
U_KACIS = re.compile(r"\\u([0-9a-fA-F]{4})")

BAKILMAYANLAR = [
    "değişkenle kurulan anahtarlar (getText(sKey), dizi/haritadan okunan anahtarlar)",
    "i18n modeli dışında adlandırılmış kaynak modelleri (ör. `{msg>...}`) ve kütüphane (sap.m) metinleri",
    "metnin DOĞRULUĞU / dili / yazım hatası (anahtar var ama metin yanlış) — ekranda kullanıcı testi",
    "kullanılmayan (ölü) anahtarlar",
]


def properties_oku(p: Path) -> dict[str, str]:
    sonuc: dict[str, str] = {}
    try:
        satirlar = p.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return sonuc
    birlesik, parca = [], ""
    for s in satirlar:
        if parca:
            s = s.lstrip()
        if s.endswith("\\") and not s.endswith("\\\\"):
            parca += s[:-1]
            continue
        birlesik.append(parca + s)
        parca = ""
    if parca:
        birlesik.append(parca)
    for s in birlesik:
        t = s.strip()
        if not t or t[0] in "#!":
            continue
        m = re.match(r"((?:[^=:\s\\]|\\.)+)\s*[=:]?\s*(.*)$", t)
        if m:
            deger = U_KACIS.sub(lambda x: chr(int(x.group(1), 16)), m.group(2))
            sonuc[m.group(1)] = deger
    return sonuc


def referanslar(webapp: Path, yardimcilar: list[str]) -> dict[str, str]:
    """{anahtar: ilk görüldüğü 'dosya:satır'}"""
    js_ref = re.compile(r"\b(?:" + "|".join(re.escape(h) for h in yardimcilar) + r")\(\s*([\"'])([\w.\-]+)\1")
    bulunan: dict[str, str] = {}
    for dizin, altlar, dosyalar in os.walk(webapp):
        altlar[:] = [a for a in altlar if a.lower() not in S.BUDANAN]
        for ad in dosyalar:
            f = Path(dizin) / ad
            dl = ad.lower()
            if not (dl.endswith(".xml") or dl.endswith(".js") or dl == "manifest.json"):
                continue
            ham = f.read_text(encoding="utf-8", errors="replace")
            if dl.endswith(".js"):
                for no, kod in S.js_kod_satirlari(ham):
                    for m in js_ref.finditer(kod):
                        bulunan.setdefault(m.group(2), f"{f.relative_to(webapp).as_posix()}:{no}")
                continue
            metin = S.xml_yorumsuz(ham) if dl.endswith(".xml") else ham
            desen = MANIFEST_REF if dl == "manifest.json" else XML_REF
            for m in desen.finditer(metin):
                no = metin.count("\n", 0, m.start()) + 1
                bulunan.setdefault(m.group(1), f"{f.relative_to(webapp).as_posix()}:{no}")
    return bulunan


def dil_dosyalari(webapp: Path) -> list[Path]:
    i18n = webapp / "i18n"
    mani = webapp / "manifest.json"
    diller = None
    if mani.is_file():
        try:
            m = json.loads(mani.read_text(encoding="utf-8-sig"))
            ayar = (m.get("sap.app") or {}).get("i18n")
            if isinstance(ayar, dict) and isinstance(ayar.get("supportedLocales"), list):
                diller = [d for d in ayar["supportedLocales"] if d]
        except (OSError, ValueError):
            diller = None
    if diller is None:
        return sorted(p for p in i18n.glob("i18n_*.properties"))
    return [i18n / f"i18n_{d}.properties" for d in diller]


def webapp_denetle(webapp: Path, yardimcilar: list[str], dil_opsiyonel: bool) -> tuple[list, list]:
    hatalar, uyarilar = [], []
    temel_yol = webapp / "i18n" / "i18n.properties"
    temel = properties_oku(temel_yol)
    diller = [(p, properties_oku(p) if p.is_file() else None) for p in dil_dosyalari(webapp)]
    refs = referanslar(webapp, yardimcilar)
    if not temel_yol.is_file():
        hatalar.append(f"temel dosya yok: {temel_yol.name}")
    for anahtar, yer in sorted(refs.items()):
        if anahtar not in temel:
            hatalar.append(f"'{anahtar}' temel i18n.properties'te yok ({yer})")
        for p, tablo in diller:
            if tablo is None:
                continue
            if anahtar not in tablo:
                (uyarilar if dil_opsiyonel else hatalar).append(f"'{anahtar}' {p.name}'de yok ({yer})")
    for p, tablo in diller:
        if tablo is None:
            (uyarilar if dil_opsiyonel else hatalar).append(f"manifest dili listeliyor ama dosya yok: {p.name}")
            continue
        for anahtar, deger in tablo.items():
            if anahtar in temel and set(YER_TUTUCU.findall(deger)) != set(YER_TUTUCU.findall(temel[anahtar])):
                uyarilar.append(f"'{anahtar}' yer tutucu kümesi farklı: temel {sorted(set(YER_TUTUCU.findall(temel[anahtar])))} ↔ {p.name} {sorted(set(YER_TUTUCU.findall(deger)))}")
    for p, tablo in [(temel_yol, temel)] + [(p, t) for p, t in diller if t]:
        for anahtar, deger in tablo.items():
            if YER_TUTUCU.search(deger) and re.search(r"(?<!')'(?!')", deger):
                uyarilar.append(f"'{anahtar}' ({p.name}) yer tutuculu metinde tek kesme işareti → '' yazın")
    return hatalar, uyarilar


def main() -> int:
    S.utf8_konsol()
    ap = argparse.ArgumentParser(description="i18n anahtar tamlığı (temel + dil dosyaları)")
    ap.add_argument("yol")
    ap.add_argument("--locale-optional", action="store_true", help="dil dosyası eksiklerini WARN say")
    ap.add_argument("--js-helper", action="append", default=[], help="ek JS metin yardımcısı adı (tekrarlanabilir)")
    a = ap.parse_args()
    kok = S.yol_dogrula(a.yol)
    yardimcilar = ["getText", "_txt", "_t", "_getText"] + a.js_helper
    webapps = sorted({p.parent.parent for p in S.webapp_dosyalari(kok, ("i18n.properties",))
                      if p.parent.name == "i18n" and p.parent.parent.name == "webapp"})
    kapsam = S.Kapsam("i18n klasörlü webapp", BAKILMAYANLAR)
    toplam_h = toplam_u = 0
    for w in kapsam.say(webapps):
        h, u = webapp_denetle(w, yardimcilar, a.locale_optional)
        for x in h:
            print(f"[İHLAL] {S.goreli(w, kok)}: {x}")
        for x in u:
            print(f"[UYARI] {S.goreli(w, kok)}: {x}")
        toplam_h += len(h)
        toplam_u += len(u)
    if kapsam.sayi == 0:
        return S.olcum_yok(kapsam)
    print()
    kapsam.bas()
    print(f"JS metin yardımcıları: {', '.join(yardimcilar)}")
    print(f"\nSONUÇ: {toplam_h} ERROR, {toplam_u} WARN.")
    return 1 if toplam_h else 0


if __name__ == "__main__":
    raise SystemExit(main())
