#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_intake_signoff.py — S2 intake artefaktı + mutabakat kapısı (aXet).

Kaynak çekirdekteki `check_itg_signoff.py`'nin uyarlanmış kopyası. Mantık (desenler, doluluk
denetimi, prior-art kuralı, mutabakat işareti) AYNEN korundu; değişenler:
  • İçe aktarılabilir `denetle(yol) -> dict` eklendi: `sap-adt-foundation/scripts/sapadt/gate.py`
    S2 yazma kapısında bunu çağırır ve eksik alanları çıktıya yazar.
  • Mesajlardaki kaynak-çekirdek belge atıfları `sap-intake-triage` skill'ine çevrildi.

S2 (kapsamlı) bir iş SAP'ye yazmadan ÖNCE, intake artefaktının üretildiğini VE kullanıcı
mutabakatının alındığını deterministik doğrular.

Kontroller:
  - MUTABAKAT satırında işaret [x]/[X] var mı (kullanıcı sign-off)?
  - Zorunlu alanlar dolu mu: KAPSAM, Etkilenen objeler, Prior-art, Kabul kriterleri.
  - Prior-art alanı boş bırakılamaz (referans izi VEYA açık "yok").

Kullanım:  python check_intake_signoff.py <proje>/.axet-code/intake/<ad>.md
Çıkış: 0 temiz · 1 bulgu (S2 yazması YASAK)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# ⚠ BAŞLIK VARLIĞI ≠ ALAN DOLULUĞU. Yalnız başlığın GEÇTİĞİNE bakmak, şablonu kopyalayıp
# hiçbir alanı doldurmadan `MUTABAKAT: [x]` işaretlemeyi GEÇİRİYORDU (kaynakta ölçülmüş kusur).
# Doluluk alan-başına denetlenir (`_deger` + `_dolu_mu`); prior-art kendi ek kuralını taşır.
#
# Başlık YAZIMINA tolerans (ör. "ETKİLENEN / İLGİLİ OBJELER") vardır, DOLULUĞA yoktur.
# Araya giren metin satır/`:` sınırını AŞMAZ (iki alanın başlığı birbirine bağlanmasın).
_ARA = r"[^\n:]{0,24}"
_ZORUNLU = [
    # aXet DÜZELTMESİ: kaynakta `kapsam` başlığı YALNIZ `kapsam:` biçiminde tanınıyordu; oysa
    # `_ALAN_MD_BASLIK` markdown başlık biçimini (`## 1. KAPSAM`) değer için destekliyor ⇒ o dal
    # bu alan için ERİŞİLEMEZDİ (başlık-biçimli artefakt "kapsam eksik" alıyordu). Tolerans yalnız
    # BAŞLIK YAZIMINA; değer doluluğu `_deger` + `_dolu_mu` ile AYNEN denetlenir (P1 yine düşer).
    ("kapsam", re.compile(r"kapsam\s*:|^#{1,6}\s+.*\bkapsam\b", re.I | re.M)),
    ("etkilenen objeler", re.compile(r"etkilenen" + _ARA + r"obje", re.I)),
    ("prior-art", re.compile(r"prior-?art", re.I)),
    ("kabul kriterleri", re.compile(r"kabul\s+kriter", re.I)),
]
# Alan DEĞERİNİ çeken desenler (başlık + `:` sonrası; satır sonuna dek; devam satırları dahil).
_ALAN_BASLIK = {
    "kapsam": re.compile(r"^.*?\bkapsam\s*:(?P<deger>.*)$", re.I),
    "etkilenen objeler": re.compile(r"^.*?etkilenen" + _ARA + r"obje[^:]*:(?P<deger>.*)$", re.I),
    "prior-art": re.compile(r"^.*?prior-?art\s*:(?P<deger>.*)$", re.I),
    "kabul kriterleri": re.compile(r"^.*?kabul\s+kriter[^:]*:(?P<deger>.*)$", re.I),
}
# İKİNCİ BİÇİM — MARKDOWN BAŞLIĞI (`## 3. ETKİLENEN / İLGİLİ OBJELER`): değer = başlıktan
# SONRAKİ blok (başlık satırı HARİÇ — dahil edilseydi boş bölüm de "dolu" görünürdü).
_ALAN_MD_BASLIK = {
    "kapsam": re.compile(r"^(?P<d>#{1,6})\s+.*\bkapsam\b.*$", re.I),
    "etkilenen objeler": re.compile(r"^(?P<d>#{1,6})\s+.*etkilenen" + _ARA + r"obje.*$", re.I),
    "prior-art": re.compile(r"^(?P<d>#{1,6})\s+.*prior-?art.*$", re.I),
    "kabul kriterleri": re.compile(r"^(?P<d>#{1,6})\s+.*kabul\s+kriter.*$", re.I),
}
_MD_BASLIK = re.compile(r"^(#{1,6})\s")
# Şablonun KENDİ yer-tutucuları. Değer bunlardan biriyle birebir (normalize) aynıysa alan
# DOLDURULMAMIŞ sayılır. ⚠ sap-intake-triage skill'inin şablonu değişirse bu küme de güncellenir.
_YER_TUTUCULAR = {
    "sd / rapor / s2 (gerekçe: ...)",
    "[obje → reuse/yeni/değişir → blast-radius]",
    "[obje -> reuse/yeni/degisir -> blast-radius]",
    "[bulundu: <ref> / yok]",
    '"<olay> olduğunda sistem <sonuç> yapmalı" / "<durum> ise ..."',
    "[konu → araştırma özeti (a/b/c eksen)]",
}
# aXet: `sap-intake-triage/references/s2-artifact-schema.md` şablonu yer-tutucuları AÇILI PARANTEZLE
# yazar (`<modül>`, `<tek cümle>`, `<nerede>` …). Bunlar yukarıdaki birebir kümede YOK ve harf içerdiği
# için "dolu" sayılıyordu ⇒ o şablon doldurulmadan `[x]` ile KAPIDAN GEÇİYORDU (ölçüldü: test P6).
# Değerde tek bir `<yer-tutucu>` bile kalmışsa alan doldurulmamış sayılır. Karşılaştırma işlecini
# (`a <> b`, `a < b ve c > d`) yakalamamak için içerik boşlukla başlayıp/bitemez (FP çapası: N6).
_ACILI_YER_TUTUCU = re.compile(r"<[^\s<>](?:[^<>\n]{0,58}[^\s<>])?>")
_MUTABAKAT_ISARETLI = re.compile(r"mutabakat.*\[[xX]\]|\[[xX]\].*mutabakat|sign-?off.*\[[xX]\]", re.I)
_MUTABAKAT_SATIR = re.compile(r"mutabakat|sign-?off", re.I)
# Prior-art DEĞERİ: ya AÇIK OLUMSUZ ("yok"), ya REFERANS İZİ (yol · uzantı · backtick · kayıt no · URL).
_PA_OLUMSUZ = re.compile(r"\b(yok|none|bulunamad|not\s+found)\w*\b", re.I)
_PA_REFERANS = re.compile(
    r"`[^`]+`"
    r"|[\w./\\-]+\.(?:md|abap|cds|py|json|ya?ml|txt|pdf)\b"
    r"|\b(?:ADR|KAYIT|PR|core)[\s#-]?\d+"
    r"|https?://\S+"
    r"|[\w-]+/[\w./-]+"
    r"|\b(bulundu|found)\b",
    re.I)
_YENI_MADDE = re.compile(r"^\s*(?:[-*+]\s|#{1,6}\s|```|\|)")


def _dolu_mu(deger: str) -> bool:
    """Boş / yalnız noktalama / şablon yer-tutucusu → DOLU DEĞİL. ("yok" gibi kısa meşru
    cevaplar geçer — "N harften az" gibi bir sezgisel bilinçli olarak YOK.)"""
    d = " ".join(deger.split()).strip().lower()
    if not d:
        return False
    if d in _YER_TUTUCULAR:
        return False
    if _ACILI_YER_TUTUCU.search(d):
        return False
    return any(c.isalnum() for c in d)


def _prior_art_ok(deger: str) -> bool:
    if not _dolu_mu(deger):
        return False
    return bool(_PA_OLUMSUZ.search(deger) or _PA_REFERANS.search(deger))


def _deger(metin: str, alan: str) -> str:
    """Alanın değeri: başlık satırının kalanı + devam satırları; yoksa markdown bölüm gövdesi."""
    rx = _ALAN_BASLIK.get(alan)
    if rx is None:
        return ""
    satirlar = metin.splitlines()
    for i, s in enumerate(satirlar):
        m = rx.match(s)
        if not m:
            continue
        parcalar = [m.group("deger")]
        for devam in satirlar[i + 1:]:
            if not devam.strip() or _YENI_MADDE.match(devam):
                break
            parcalar.append(devam)
        return " ".join(parcalar)
    brx = _ALAN_MD_BASLIK.get(alan)
    if brx is not None:
        for i, s in enumerate(satirlar):
            bm = brx.match(s)
            if not bm:
                continue
            seviye = len(bm.group("d"))
            govde = []
            for devam in satirlar[i + 1:]:
                hm = _MD_BASLIK.match(devam)
                if hm and len(hm.group(1)) <= seviye:
                    break
                govde.append(devam)
            return " ".join(govde)
    return ""


def denetle(yol) -> dict:
    """İçe aktarılabilir denetim.

    Döner: {"ok": bool, "eksik_alanlar": [...], "bos_alanlar": [...], "prior_art_ok": bool|None,
            "mutabakat": bool|None, "bulgular": [str, ...]}
    İlk bulguda durulmaz; tüm bulgular birlikte raporlanır (kaynakta ilk bulguda çıkılıyordu —
    exit kodu AYNI kalır: herhangi bir bulgu = geçmez).
    """
    p = Path(yol)
    out = {"ok": False, "eksik_alanlar": [], "bos_alanlar": [], "prior_art_ok": None,
           "mutabakat": None, "bulgular": []}
    if not p.is_file():
        out["bulgular"].append(f"intake artefaktı bulunamadı: {yol}")
        return out
    text = p.read_text(encoding="utf-8", errors="replace")

    eksik = [ad for ad, rx in _ZORUNLU if not rx.search(text)]
    out["eksik_alanlar"] = eksik
    if eksik:
        out["bulgular"].append("zorunlu alan(lar) eksik: " + ", ".join(eksik))
    bos = [ad for ad, _rx in _ZORUNLU if ad not in eksik and not _dolu_mu(_deger(text, ad))]
    out["bos_alanlar"] = bos
    if bos:
        out["bulgular"].append("alan BAŞLIK olarak var ama DEĞERİ boş/şablon: " + ", ".join(bos))
    if "prior-art" not in eksik and "prior-art" not in bos:
        out["prior_art_ok"] = _prior_art_ok(_deger(text, "prior-art"))
        if not out["prior_art_ok"]:
            out["bulgular"].append("Prior-art boş/belirsiz (referans izi ya da açık 'yok' gerekir)")
    out["mutabakat"] = bool(_MUTABAKAT_ISARETLI.search(text))
    if not out["mutabakat"]:
        durum = ("MUTABAKAT satırı var ama işaretsiz" if _MUTABAKAT_SATIR.search(text)
                 else "MUTABAKAT satırı yok")
        out["bulgular"].append(f"kullanıcı sign-off'u yok ({durum})")
    out["ok"] = not out["bulgular"]
    return out


def main() -> int:
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass
    ap = argparse.ArgumentParser(description="S2 intake artefaktı + mutabakat kapısı")
    ap.add_argument("artifact", help="intake artefaktı .md yolu")
    args = ap.parse_args()
    sonuc = denetle(args.artifact)
    if not sonuc["ok"]:
        sys.stderr.write("⛔ INTAKE S2 SIGNOFF: artefakt kapıdan geçmedi.\n")
        for b in sonuc["bulgular"]:
            sys.stderr.write(f"  · {b}\n")
        if sonuc["eksik_alanlar"]:
            for ad, rx in _ZORUNLU:
                if ad in sonuc["eksik_alanlar"]:
                    sys.stderr.write(f"    '{ad}' → denenen desen: {rx.pattern}\n")
        sys.stderr.write("Şema: KAPSAM · Etkilenen objeler · Prior-art · Kabul kriterleri + "
                         "'MUTABAKAT: [x]'. Bkz. sap-intake-triage skill'i.\n")
        return 1
    print(f"✓ INTAKE S2 SIGNOFF: intake artefaktı tam + MUTABAKAT işaretli ({Path(args.artifact).name}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
