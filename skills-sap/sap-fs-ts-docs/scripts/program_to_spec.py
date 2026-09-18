#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""program_to_spec.py — ABAP/CDS kaynağı → taslak FS/TS iskeleti (tersine mühendislik).

Kaynakta GERÇEKTEN olan teknik olguları (tablolar, ekran numaraları, FM/BAPI çağrıları, seçim parametreleri, FORM/METHOD,
sınıf, CDS entity) çıkarır; anlatı bölümlerini (amaç, iş kuralları, hedef süreç) `<TODO: …>` bırakır.

Kural: script uydurmaz. Çıktı TASLAKTIR → kullanıcı spesifikasyonu ve çalışan uygulama davranışından doldurulur →
spec mutabakatı → ancak sonra build.

Kullanım:
    python program_to_spec.py <kaynak.abap> [<kaynak2.abap> ...] [--out docs/TASLAK_<ad>.md]
Çıkış: 0 taslak üretildi · 1 geçerli kaynak yok.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

SCOPE = ("KAPSAM (SCOPE): program_to_spec — düzenli ifadeyle TABLES/FROM/JOIN, PARAMETERS/SELECT-OPTIONS, CALL FUNCTION, "
         "FORM/METHODS/CLASS, CALL/SET SCREEN, REPORT/FUNCTION-POOL, CDS define. Bakılmayanlar: satır içi \" yorumları, "
         "dinamik çağrılar ve makrolar, include'ların kendisi (ayrıca verilmezse), iş anlamı; tablo adının sistemde varlığı. "
         "'Tespit edilemedi' = 'yok' değildir.")

PATTERNS = {
    "tables": re.compile(r"\bTABLES?\s*:?\s+(\w+)", re.IGNORECASE),
    "select_from": re.compile(r"\b(?:FROM|JOIN)\s+(\w+)", re.IGNORECASE),
    "params": re.compile(r"\bPARAMETERS?\s*:?\s+(\w+)", re.IGNORECASE),
    "selopts": re.compile(r"\bSELECT-OPTIONS\s*:?\s+(\w+)", re.IGNORECASE),
    "call_func": re.compile(r"\bCALL\s+FUNCTION\s+'([^']+)'", re.IGNORECASE),
    "forms": re.compile(r"^\s*FORM\s+(\w+)", re.IGNORECASE | re.MULTILINE),
    "methods": re.compile(r"\bMETHODS?\s*:?\s+(\w+)", re.IGNORECASE),
    "screens": re.compile(r"\b(?:CALL|SET)\s+SCREEN\s+(\d+)", re.IGNORECASE),
    "classes": re.compile(r"\bCLASS\s+(\w+)\s+DEFINITION", re.IGNORECASE),
    "cds_entity": re.compile(r"\bdefine\s+(?:root\s+)?view\s+entity\s+(\w+)", re.IGNORECASE),
    "report": re.compile(r"^\s*(?:REPORT|PROGRAM)\s+(\w+)", re.IGNORECASE | re.MULTILINE),
    "func_pool": re.compile(r"\bFUNCTION-POOL\s+(\w+)", re.IGNORECASE),
}
CUSTOMER_PREFIX = ("Z", "Y")


def _uniq(seq):
    seen, out = set(), []
    for x in seq:
        u = x.upper()
        if u not in seen:
            seen.add(u)
            out.append(x)
    return out


def extract(text: str) -> dict:
    """`*` ile başlayan yorum satırlarını atıp kalıpları uygular."""
    text = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("*"))
    return {key: _uniq(rx.findall(text)) for key, rx in PATTERNS.items()}


def render(facts: dict, sources: list[str]) -> str:
    prog = (facts["report"] or facts["func_pool"] or facts["classes"] or facts["cds_entity"] or ["<obje>"])[0]
    tables = _uniq(facts["tables"] + facts["select_from"])
    customer = [t for t in tables if t.upper().startswith(CUSTOMER_PREFIX)]
    standard = [t for t in tables if not t.upper().startswith(CUSTOMER_PREFIX) and len(t) >= 3]
    L: list[str] = []
    w = L.append
    w(f"# TASLAK FS/TS — {prog}")
    w("")
    w("> **OTOMATİK TASLAK** (`program_to_spec.py`). Teknik olgular kaynaktan çıkarıldı; `<TODO>` bölümleri kullanıcı")
    w("> spesifikasyonu ve çalışan uygulama davranışından doldurulur (tahmin yok). **Spec mutabakatı zorunlu** — onaysız build yok.")
    w("")
    w(f"**Kaynak dosya(lar):** {', '.join(sources)}")
    w("**Şablon:** `%sap-fs-ts-docs` → `templates/FS-template.md` ve `templates/TS-template.md`")
    w("")
    w("---")
    w("## FS — Fonksiyonel (taslak)")
    w("")
    w("### 2.1 Amaç")
    w("<TODO: bu program ne için kullanılıyor — kullanıcı ifadesi ya da çalışan uygulama davranışından>")
    w("### 2.2 Kapsam")
    w("<TODO: kapsam içi / dışı>")
    w("### 3. İş süreci (mevcut → hedef)")
    w("<TODO: mevcut akış; hedef akış>")
    w("### 4.2 İş kuralları")
    w("<TODO: doğrulama/belirleme kuralları — kaynaktaki FORM/METHOD mantığından, kullanıcıyla teyitli>")
    w("### 5.1 Ekran listesi")
    if facts["screens"]:
        for s in facts["screens"]:
            w(f"- Ekran {s} — <TODO: amaç>")
    else:
        w("- <ekran numarası tespit edilemedi (liste/rapor olabilir)>")
    w("")
    w("---")
    w("## TS — Teknik (taslak, kaynaktan çıkarıldı)")
    w("")
    w(f"**Ana obje:** {prog}")
    w("")
    w("### Kullanılan tablolar")
    if standard:
        w(f"- **Standart (sistemde varlığı ve released karşılığı teyit edilecek; yalnız okuma):** {', '.join(standard)}")
    if customer:
        w(f"- **Müşteri (Z/Y) tabloları:** {', '.join(customer)}")
    if not tables:
        w("- <tespit edilemedi>")
    w("")
    w("### Seçim ekranı")
    sel = facts["params"] + facts["selopts"]
    w(f"- PARAMETERS / SELECT-OPTIONS: {', '.join(sel) if sel else '<tespit edilemedi>'}")
    w("")
    w("### Çağrılan fonksiyon modülleri / BAPI")
    if facts["call_func"]:
        for fn in facts["call_func"]:
            tag = " (BAPI — hedef profilde kullanılabilir/released mı teyit edilecek)" if fn.upper().startswith("BAPI_") else ""
            w(f"- `{fn}`{tag}")
    else:
        w("- <tespit edilemedi>")
    w("")
    w("### Modülerleştirme")
    if facts["forms"]:
        w(f"- FORM rutinleri: {', '.join(facts['forms'][:30])}")
    if facts["methods"]:
        w(f"- METHOD'lar: {', '.join(facts['methods'][:30])}")
    if facts["classes"]:
        w(f"- Sınıflar: {', '.join(facts['classes'])}")
    if facts["cds_entity"]:
        w(f"- CDS entity: {', '.join(facts['cds_entity'])}")
    if not (facts["forms"] or facts["methods"] or facts["classes"] or facts["cds_entity"]):
        w("- <tespit edilemedi>")
    w("")
    w("### Genişletme seviyesi ve teknoloji kararı")
    w("<TODO: `references/ts-authoring.md` §4 karar ağacı; hedef `sap_profile` sınırı (ecc: RAP yok · s4_public/btp_abap: klasik obje yok)>")
    w("")
    w("> Sonraki adım: taslağı şablona taşı → `<TODO>`'ları kanıtla doldur → spec mutabakatı → build.")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="ABAP/CDS kaynağı → taslak FS/TS")
    ap.add_argument("sources", nargs="+")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    print(SCOPE, file=sys.stderr if not a.out else sys.stdout)

    merged: dict[str, list[str]] = {k: [] for k in PATTERNS}
    used = []
    for s in a.sources:
        p = Path(s)
        if not p.is_file():
            print(f"[uyarı] {p} yok, atlandı", file=sys.stderr)
            continue
        used.append(s)
        facts = extract(p.read_text(encoding="utf-8", errors="replace"))
        for k in merged:
            merged[k].extend(facts[k])
    if not used:
        print("HATA: geçerli kaynak yok", file=sys.stderr)
        return 1
    merged = {k: _uniq(v) for k, v in merged.items()}
    doc = render(merged, used)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(doc + "\n", encoding="utf-8")
        print(f"[OK] Taslak yazıldı: {a.out}  (doldur → spec mutabakatı → build)")
    else:
        print(doc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
