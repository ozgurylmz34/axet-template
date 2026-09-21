# -*- coding: utf-8 -*-
"""Klasik program metin havuzu (text pool) — yük üretimi, ön kontrol, ayrıştırma (ağ YOK).

Kaynak: çekirdek `playbook/adt-programs.md` §23.7 "SOURCE format" (canlı GET ile doğrulanmış biçim) ve
`scripts/push_textpool.py` (`_read_payload`, `_check_symbol_maxlengths`). aXet'te serbest metin dosyası yerine
YAPILI girdi alınır; biçim buradan üretilir ki DS512 ("Text elements contain errors") sınıfı yazım hatası
kullanıcıya düşmesin.

Biçim (kaynaktaki kanonik hâl):
  symbols    : her giriş için `@MaxLength:NN` satırı + `KEY=metin`; girişler BOŞ satırla ayrılır.
  selections : ad 8 karaktere SOLA yaslı + `=metin`; girişler boş satırla ayrılır; `@DDICReference` YAZILMAZ.
  Satır sonu CRLF; SON girişten sonra satır sonu YOK (fazlası hayalet boş giriş → DS512).
"""
from __future__ import annotations

import re

ALT_KAYNAK_CT = {
    "symbols": "application/vnd.sap.adt.textelements.symbols.v1",
    "selections": "application/vnd.sap.adt.textelements.selections.v1",
}
#: Başlıklar (headings) alt kaynağının yazım biçimi kaynak çekirdekte belgelenmedi (yalnız uç adı var) → desteklenmez.
DESTEKLENMEYEN = {"headings": "Liste başlıkları (headings) yazım biçimi kaynakta canlı belgelenmedi; "
                              "SE38 → Metin öğeleri'nden elle girilir."}

_SEMBOL_RE = re.compile(r"^[A-Za-z0-9]{3}$")
_SECIM_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,7}$")
_SATIR_SONU = re.compile(r"[\r\n\u2028\u2029\u0085]")

KONTROL_EDILENLER = ("P1_sembol_anahtari_3_karakter", "P2_metin_bos_degil", "P3_metin_max_length_asmaz",
                     "P4_secim_adi_en_cok_8", "P5_tekil_anahtar", "P6_satir_sonu_yok", "P7_en_az_bir_giris")
KONTROL_EDILMEYENLER = ("seçim metninin SAP'deki azami uzunluğu (SAP PUT'ta reddeder)",
                        "sembolün / seçim adının programda gerçekten kullanılıp kullanılmadığı",
                        "@MaxLength için SAP'nin üst sınırı")


def _bulgu(liste, kural, mesaj):
    liste.append({"rule": kural, "severity": "BLOCKER", "message": mesaj})


def on_kontrol(symbols=None, selections=None) -> dict:
    """Yapılı girdiyi denetle. symbols: [{"key","text","max_length"?}] · selections: [{"name","text"}]."""
    b: list[dict] = []
    if not symbols and not selections:
        _bulgu(b, "P7", "En az bir metin sembolü (symbols) ya da seçim metni (selections) verilmeli.")
    gorulen = set()
    for i, s in enumerate(symbols or []):
        if not isinstance(s, dict):
            _bulgu(b, "P1", f"symbols[{i}] sözlük olmalı: {{'key','text','max_length'?}}")
            continue
        k, t = str(s.get("key") or ""), s.get("text")
        if not _SEMBOL_RE.match(k):
            _bulgu(b, "P1", f"symbols[{i}].key={k!r} — metin sembolü tam 3 harf/rakam olmalı (ör. B01, 001).")
        if not isinstance(t, str) or not t.strip():
            _bulgu(b, "P2", f"symbols[{i}] ({k}) metni boş.")
            continue
        if _SATIR_SONU.search(t):
            _bulgu(b, "P6", f"symbols[{i}] ({k}) metni satır sonu içeriyor.")
        ml = s.get("max_length", len(t))
        if not isinstance(ml, int) or isinstance(ml, bool) or ml < 1:
            _bulgu(b, "P3", f"symbols[{i}] ({k}) max_length pozitif tam sayı olmalı.")
        elif len(t) > ml:
            _bulgu(b, "P3", f"symbols[{i}] ({k}) metin {len(t)} karakter > max_length {ml} — SAP DS512 verir.")
        if k.upper() in gorulen:
            _bulgu(b, "P5", f"symbols: {k.upper()} iki kez verildi.")
        gorulen.add(k.upper())
    gorulen = set()
    for i, s in enumerate(selections or []):
        if not isinstance(s, dict):
            _bulgu(b, "P4", f"selections[{i}] sözlük olmalı: {{'name','text'}}")
            continue
        n, t = str(s.get("name") or ""), s.get("text")
        if not _SECIM_RE.match(n):
            _bulgu(b, "P4", f"selections[{i}].name={n!r} — parametre/seçim kriteri adı harfle başlar, en çok 8 karakter.")
        if not isinstance(t, str) or not t.strip():
            _bulgu(b, "P2", f"selections[{i}] ({n}) metni boş.")
        elif _SATIR_SONU.search(t):
            _bulgu(b, "P6", f"selections[{i}] ({n}) metni satır sonu içeriyor.")
        if n.upper() in gorulen:
            _bulgu(b, "P5", f"selections: {n.upper()} iki kez verildi.")
        gorulen.add(n.upper())
    return {"verdict": "BLOCKER" if b else "PASS", "findings": b, "checked": list(KONTROL_EDILENLER),
            "not_checked": list(KONTROL_EDILMEYENLER)}


def sembol_yuku(symbols) -> str:
    parcalar = [f"@MaxLength:{int(s.get('max_length', len(s['text'])))}\r\n{str(s['key']).upper()}={s['text']}"
                for s in symbols]
    return "\r\n\r\n".join(parcalar)


def secim_yuku(selections) -> str:
    return "\r\n\r\n".join(f"{str(s['name']).upper():<8}={s['text']}" for s in selections)


def ayristir(alt: str, govde: str) -> dict:
    """Canlı alt kaynak gövdesi → {ANAHTAR: metin}. `@...` satırları ve boş satırlar atlanır.

    selections'ta ad 8 karaktere yaslı olduğundan anahtar `=`'den önceki kısmın kırpılmış hâlidir."""
    out: dict[str, str] = {}
    for satir in (govde or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if not satir.strip() or satir.lstrip().startswith("@"):
            continue
        if "=" not in satir:
            continue
        k, v = satir.split("=", 1)
        k = k.strip().upper()
        if k:
            out[k] = v.rstrip()
    return out


def beklenen(alt: str, girdiler) -> dict:
    if alt == "symbols":
        return {str(s["key"]).upper(): s["text"].rstrip() for s in girdiler}
    return {str(s["name"]).upper(): s["text"].rstrip() for s in girdiler}


def silinecekler(alt: str, canli_govde: str, girdiler) -> list[str]:
    """PUT alt kaynağın TAMAMINI değiştirir → canlıda olup girdide OLMAYAN anahtarlar silinir."""
    return sorted(set(ayristir(alt, canli_govde)) - set(beklenen(alt, girdiler)))


def readback_karsilastir(alt: str, aktif_govde: str, girdiler, silinecek=None) -> dict:
    """Aktif sürüm ↔ beklenen. `=?` (seçim yer tutucusu) ya da eksik/farklı metin = FAIL.

    `silinecek`: yazmadan önce `silinecekler` ile bulunan ve `allow_remove=true` ile silinmesi onaylanan anahtarlar.
    Bunlardan aktif sürümde HÂLÂ duran varsa silme uygulanmamıştır → FAIL (`remove_not_applied`)."""
    canli = ayristir(alt, aktif_govde)
    bek = beklenen(alt, girdiler)
    eksik = sorted(k for k in bek if k not in canli)
    farkli = sorted(k for k in bek if k in canli and canli[k] != bek[k])
    yer_tutucu = sorted(k for k in bek if canli.get(k, "").strip() == "?")
    kalan = sorted(k for k in {str(s).upper() for s in (silinecek or [])} if k in canli)
    ok = not (eksik or farkli or yer_tutucu or kalan) and bool(bek)
    return {"ok": ok, "missing": eksik, "different": [k for k in farkli if k not in yer_tutucu],
            "placeholder": yer_tutucu, "remove_not_applied": kalan, "active_count": len(canli),
            "expected_count": len(bek)}
