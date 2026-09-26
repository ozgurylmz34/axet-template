# -*- coding: utf-8 -*-
"""DDIC yapı/tablo alan tipi → DTEL adayı çıkarımı — TEK KAYNAK (aXet 2026-09-14, D1).

Kullananlar:
  · `lib/validators/check_struct_field_dtel_active.py` (artefaktlı yol: struct/tablo DDL'i)
  · `sapadt/_reviewer.py::run_reviewer_struct_alanlari` (`adt_struct_create` her çağrıda:
    `fields[]` → `yapi_ddl_kaynagi` → aynı DDL ayrıştırması)
  · `lib/sap_adt_lib.py::SAPADTClient.create_structure` (SAP'ye PUT edilen DDL `yapi_ddl_kaynagi`'dan gelir;
    böylece "yazılan DDL" ile "denetlenen DDL" ayrışamaz — açıklama satırları dahil)
  · `lib/sap_adt_lib.py::SAPADTClient._field_type_to_ddl` (yazma yolunun tip çevirisi buradan gelir;
    böylece "yazılan tip" ile "kontrol edilen tip" ayrışamaz)

KAPSAM (bilinçli, kullanıcı/lider kararı 2026-09-14):
  · aday = alan tip belirteci Z/Y ile ya da `/ad-alanı/` ile başlıyor.
  · DEĞİL: `abap.*` ilkel tipler, `include <ad>;` satırları, annotation satırları, yorumlar.
  · Standart DTEL'ler (ör. MATNR) KONTROL EDİLMEZ — kapsam beyanı `KAPSAM_BEYANI`.
Önceki hâl: validator yalnız `zsd[0-9_]*_e_*` adlarını yakalıyordu (müşteri önekinden kalan kusur) →
`ZAXET_E_X` gibi var olmayan bir DTEL "kapsam dışı" sayılıp PASS alıyordu.
"""
from __future__ import annotations

import re

KAPSAM_BEYANI = (
    "KAPSAM: yalnız alan tip belirteci Z/Y ya da /ad-alanı/ ile başlayan adlar kontrol edildi "
    "(DTEL değilse yapı/tablo/tablo tipi sondası). ÖLÇÜLMEDİ: standart DTEL'ler (ör. MATNR), "
    "abap.* ilkel tipler, include satırları.")

# Bug gate 2026-09-14 (B4): string, yorum ve anotasyon TEK taramada atılır (en soldaki eşleşme kazanır ⇒ string
# içindeki `/*` ya da `//` yorum sanılmaz), sonra metin YALNIZ `;` `{` `}` ile bölünür (satır sonu bölmez ⇒ iki satıra
# bölünmüş alan birleşir; aynı satırdaki anotasyon silinince alan kalır). Önceki hâl `\n` ile bölüp `@` ile başlayan
# parçayı atıyordu ve yorum regex'i string'i tanımıyordu → üç biçimde aday sessizce kaçıyordu (taban regex'i yakalıyordu).
_STRING_YORUM = re.compile(r"'(?:[^'\n]|'')*'|/\*.*?\*/|//[^\n]*", re.S)
# Z117ⓔ (2026-09-26, `std_ext_scan` ile aynı sınıf): SAP'nin DDL dizesinde `\'`'yü kaçış sayıp saymadığı DOĞRULANMADI.
# Tek (`''`) modelde `'x\'' ; f1 : z…; @A : 'y'` TEK dize sayılıp `f1` adayı gizleniyordu ⇒ adaylar iki modelde
# çıkarılıp BİRLEŞTİRİLİR (üst küme = daha çok varlık denetimi; fail-closed yön).
_STRING_YORUM_TERS = re.compile(r"'(?:[^'\\\n]|\\[^\n]|'')*'|/\*.*?\*/|//[^\n]*", re.S)
_ANOTASYON = re.compile(
    r"@<?[\w.]+(?:\s*:\s*(?:''|#\w+|-?\d+(?:\.\d+)?|\w+|\[[^\]]*\]|\{[^}]*\}))?")
_INCLUDE = re.compile(r"^include\b", re.I)
_TANIM = re.compile(r"^(?:define|extend)\b", re.I)
_ALAN = re.compile(r"(?:^|\s)(?:key\s+)?(?P<ad>[A-Za-z_/][\w/]*)\s*:\s*(?P<tip>[A-Za-z_/][\w/.]*)")


def _string_yorum_at(m: re.Match) -> str:
    return "''" if m.group(0).startswith("'") else " "

_SKALER = {
    'i': 'abap.int4', 'int1': 'abap.int1', 'int2': 'abap.int2',
    'int4': 'abap.int4', 'int8': 'abap.int8',
    'd': 'abap.dats', 'dats': 'abap.dats',
    't': 'abap.tims', 'tims': 'abap.tims',
    'f': 'abap.fltp', 'fltp': 'abap.fltp',
    'string': 'abap.string', 'xstring': 'abap.rawstring',
    'rawstring': 'abap.rawstring',
    'decfloat16': 'abap.decfloat16', 'decfloat34': 'abap.decfloat34',
    'clnt': 'abap.clnt', 'lang': 'abap.lang',
}


def field_type_to_ddl(field_type) -> str:
    """Bir field 'type' kısayolunu DDL structure-source biçimine çevirir.

    Structure /source/main kanonik DDL bekler:
      - built-in : abap.char(10), abap.numc(8), abap.dec(15,2), abap.int4, ...
      - dictionary (data element / alt-struct) : olduğu gibi (küçük harf)

    Bilinmeyen tip → data element/alt-struct referansı sayılır (pass-through).
    (Taşındı: `sap_adt_lib.SAPADTClient._field_type_to_ddl` gövdesi, davranış aynı.)
    """
    t = (field_type or '').strip()
    if not t:
        return 'abap.char(1)'
    tl = t.lower()
    if tl.startswith('abap.'):
        return t
    m = re.fullmatch(r'(?:char|c)(\d+)', tl)
    if m:
        return f'abap.char({int(m.group(1))})'
    m = re.fullmatch(r'(?:numc|n)(\d+)', tl)
    if m:
        return f'abap.numc({int(m.group(1))})'
    m = re.fullmatch(r'raw(\d+)', tl)
    if m:
        return f'abap.raw({int(m.group(1))})'
    m = re.fullmatch(r'curr(\d+)[_,.](\d+)', tl)
    if m:
        return f'abap.curr({int(m.group(1))},{int(m.group(2))})'
    m = re.fullmatch(r'quan(\d+)[_,.](\d+)', tl)
    if m:
        return f'abap.quan({int(m.group(1))},{int(m.group(2))})'
    m = re.fullmatch(r'(?:dec|p)(\d+)[_,.](\d+)', tl)
    if m:
        return f'abap.dec({int(m.group(1))},{int(m.group(2))})'
    m = re.fullmatch(r'(?:dec|p)(\d+)', tl)
    if m:
        return f'abap.dec({int(m.group(1))},0)'
    if tl in _SKALER:
        return _SKALER[tl]
    return tl


def aday_mi(tip: str) -> bool:
    """Tip belirteci DTEL adayı mı: Z/Y ya da `/ad-alanı/` ile başlar; `abap.*` değildir."""
    t = (tip or '').strip()
    if not t or t.lower().startswith('abap.'):
        return False
    if t[0] in 'zZyY':
        return True
    return t.startswith('/') and t.count('/') >= 2 and not t.endswith('/')


def dtel_adaylari(ddl: str) -> list[str]:
    """Struct/tablo DDL metninden DTEL adaylarını çıkar (BÜYÜK harf, sıralı, tekil). İki dize modelinin birleşimi."""
    adaylar: set[str] = set()
    for desen in (_STRING_YORUM, _STRING_YORUM_TERS):
        metin = desen.sub(_string_yorum_at, ddl or '')
        metin = _ANOTASYON.sub(' ', metin)
        for parca in re.split(r'[;{}]', metin):
            s = parca.strip()
            if not s or _INCLUDE.match(s) or _TANIM.match(s):
                continue
            m = _ALAN.search(s)
            if m and aday_mi(m.group('tip')):
                adaylar.add(m.group('tip').upper())
    return sorted(adaylar)


SATIR_SONU_KARAKTERLERI = {
    "\r": "U+000D (CARRIAGE RETURN)",
    "\n": "U+000A (LINE FEED)",
    "\u2028": "U+2028 (LINE SEPARATOR)",
    "\u2029": "U+2029 (PARAGRAPH SEPARATOR)",
    "\x85": "U+0085 (NEXT LINE)",
}
"""Yapı DDL'ine giren serbest metinde YASAK satır sonu karakterleri — TEK KAYNAK (render reddi + `adt_struct_create` ön kontrolü)."""


def satir_sonu_ihlali(fields, description):
    """Render'a giren serbest metinlerde ilk satır sonu karakterini bul → `(yer, kod)` ya da `None`.

    Bakılan yerler (sırayla): yapı açıklaması (`yapı açıklaması`), her alan için `fields[i].description`, `fields[i].name`,
    `fields[i].type`. Yalnız `str` değerlere bakılır (render da yalnız onları metne döker; `None`/eksik = boş)."""
    denetlenecek = [("yapı açıklaması", description)]
    for i, field in enumerate(fields or []):
        if not isinstance(field, dict):
            continue
        for anahtar in ("description", "name", "type"):
            denetlenecek.append((f"fields[{i}].{anahtar}", field.get(anahtar)))
    for yer, deger in denetlenecek:
        if not isinstance(deger, str):
            continue
        for ch in deger:
            if ch in SATIR_SONU_KARAKTERLERI:
                return yer, SATIR_SONU_KARAKTERLERI[ch]
    return None


def yapi_ddl_kaynagi(name: str, fields, description) -> str:
    """Yapı (INTTAB) DDL kaynağı — `sap_adt_lib.SAPADTClient.create_structure`'ın SAP'ye PUT ettiği metin. TEK render.

    Re-gate 2026-09-15 (önceden var #2): yazma yolu alan açıklamasını `// {açıklama}` satırı, yapı açıklamasını
    `@EndUserText.label` olarak yazıyordu; gate'in DDL'i ikisini de almıyordu → açıklamadaki satır sonu gate'in görmediği
    bir alan satırı yazdırabiliyordu (ölçüldü: `"x\\n  b : zaxet_e_yok_desc;"` → gate adayı [], yazılan DDL adayı
    ['ZAXET_E_YOK_DESC']). Artık yazma yolu ve gate (`_reviewer.run_reviewer_struct_alanlari`) BU fonksiyonu çağırır ⇒
    denetlenen metin = yazılan metin. Gövde `create_structure`'dan aynen taşındı (yazılan DDL değişmedi).

    Tur 3 (3. dar gate, MEDIUM — kök sınıf "serbest metinde satır sonu"): tek render açıklama satırlarını gate'e de taşıyınca
    çıkarıcının `--`'yı tanımaması ve `/*`'ı blok yorum sanması yeni bir kör nokta açtı (ölçüldü: açıklama `"x\\n-- /*"` +
    sonraki açıklama `"*/"` → aradaki `ZAXET_E_YOK` gate'ten gizlendi, verdict PASS; HEAD c9b5538'de BLOCKER). Aynı sınıf alan
    adı ve tipinde de ölçüldü. Bu yüzden render'a giren serbest metinde (`SATIR_SONU_KARAKTERLERI`) satır sonu varsa
    `ValueError` verilir ⇒ gate (render hatası = BLOCKER `ddl_render_hatasi`), `create_structure` ve onu çağıran her yol
    kapanır. Satır sonu içermeyen girdide çıktı değişmedi (HEAD ile bayt bayt pin: test B7g)."""
    ihlal = satir_sonu_ihlali(fields, description)
    if ihlal:
        yer, kod = ihlal
        raise ValueError(f"yapı DDL'i render edilemez: {yer} satır sonu karakteri içeriyor ({kod})")
    field_lines = []
    for field in fields:
        field_name = (field.get('name') or '').strip()
        field_desc = field.get('description', '')
        ddl_type = field_type_to_ddl(field.get('type', 'char10'))
        if field_desc:
            field_lines.append(f'  // {field_desc}')
        field_lines.append(f'  {field_name.lower()} : {ddl_type};')
    fields_source = '\n'.join(field_lines)
    _label = (description or '').replace("'", "''")
    return (
        f"@EndUserText.label : '{_label}'\n"
        f"@AbapCatalog.enhancement.category : #NOT_EXTENSIBLE\n"
        f"define structure {name.lower()} {{\n"
        f"{fields_source}\n"
        f"}}"
    )


def alanlardan_ddl(name: str, fields, description: str = '') -> str:
    """Geriye uyumlu ad → `yapi_ddl_kaynagi` (gate'in denetlediği DDL = yazılan DDL)."""
    return yapi_ddl_kaynagi(name, fields, description)
