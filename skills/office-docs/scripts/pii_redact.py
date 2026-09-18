#!/usr/bin/env python3
"""pii_redact — belge üretmeden önce Türkiye'ye özgü kimlik ve banka numaralarını maskeler (KVKK).

Bu dosyanın birebir kopyası office-slides skill'inde de durur (her skill tek başına çalışsın diye);
iki kopyanın aynı kaldığını office-slides testleri denetler.

Modlar:
  akilli (varsayılan)
    · TR IBAN (TR + 24 hane; 4'lü gruplu ya da bitişik)
    · 11 haneli TC kimlik no — yalnız resmî kontrol hanesi hesabını sağlayanlar
    · 10 haneli vergi kimlik no — yalnız hemen önünde "VKN", "vergi no", "vergi kimlik no", "tax id" geçiyorsa
  genis
    · TR IBAN + bağımsız duran TÜM 10-11 haneli sayılar
Neden iki mod: SAP'de satış/muhasebe belge numaraları 10 hanedir (ör. 0080001234). "Tüm 10-11 hane" kuralı
bunları da maskeler ve belgeyi okunmaz yapar; `akilli` bunlara dokunmaz ama bağlamsız yazılmış bir VKN'yi
kaçırır. Ad, adres, e-posta ve ayraçlı telefon numarası hiçbir modda maskelenmez.

Kütüphane:  from pii_redact import redact_text;  metin, sayilar = redact_text(metin, mode="akilli")
CLI:        python pii_redact.py --in rapor.md --out rapor.maskeli.md [--mode genis] [--count-only]
"""
from __future__ import annotations

import argparse
import re
import sys

DEFAULT_MASK = "**********"
MODES = ("akilli", "genis")

_IBAN = re.compile(r"\bTR\d{2}(?:[ ]?\d{4}){5}[ ]?\d{2}\b", re.IGNORECASE)
_VKN_CONTEXT = re.compile(r"(\b(?:vkn|vergi\s*(?:kimlik\s*)?(?:no|numaras[ıi])|tax\s*id)\b\W{0,5})(\d{10})(?!\d)",
                          re.IGNORECASE)
_ELEVEN = re.compile(r"(?<!\d)\d{11}(?!\d)")
_TEN_OR_ELEVEN = re.compile(r"(?<!\d)\d{10,11}(?!\d)")


def tckn_valid(s: str) -> bool:
    """TC kimlik no kontrol hanesi: ilk hane 0 değil; 10. hane ve 11. hane resmî formülle tutar."""
    if len(s) != 11 or not s.isdigit() or s[0] == "0":
        return False
    d = [int(c) for c in s]
    if (sum(d[0:9:2]) * 7 - sum(d[1:8:2])) % 10 != d[9]:
        return False
    return sum(d[:10]) % 10 == d[10]


def redact_text(text: str, mode: str = "akilli", mask: str = DEFAULT_MASK) -> tuple[str, dict]:
    if mode not in MODES:
        raise ValueError(f"mod {mode!r} geçersiz: {MODES}")
    counts = {"iban": 0, "tckn": 0, "vkn": 0, "10_11_hane": 0}
    if not text:
        return text, counts

    def iban(_m):
        counts["iban"] += 1
        return mask
    text = _IBAN.sub(iban, text)
    if mode == "genis":
        def any_id(_m):
            counts["10_11_hane"] += 1
            return mask
        return _TEN_OR_ELEVEN.sub(any_id, text), counts

    def vkn(m):
        counts["vkn"] += 1
        return m.group(1) + mask
    text = _VKN_CONTEXT.sub(vkn, text)

    def tckn(m):
        if tckn_valid(m.group(0)):
            counts["tckn"] += 1
            return mask
        return m.group(0)
    return _ELEVEN.sub(tckn, text), counts


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="TR kimlik/vergi/IBAN numaralarını maskele (KVKK)")
    ap.add_argument("--in", dest="inp", help="girdi dosyası (varsayılan: stdin)")
    ap.add_argument("--out", help="çıktı dosyası (varsayılan: stdout)")
    ap.add_argument("--mode", choices=MODES, default="akilli")
    ap.add_argument("--mask", default=DEFAULT_MASK)
    ap.add_argument("--count-only", action="store_true", help="yalnız sayıları bas, metni değiştirme")
    args = ap.parse_args(argv)
    text = open(args.inp, encoding="utf-8-sig").read() if args.inp else sys.stdin.read()
    masked, counts = redact_text(text, args.mode, args.mask)
    summary = " · ".join(f"{k}={v}" for k, v in counts.items())
    if args.count_only:
        print(summary)
        return 0
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(masked)
        print(f"[maskeleme] {summary} → {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(masked)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
