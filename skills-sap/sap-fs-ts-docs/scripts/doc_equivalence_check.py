#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""doc_equivalence_check.py — doküman yeniden yazımında VERİ KAYBI ölçer (DOC-FS-07, İlke 2b).

Kullanım:
  python doc_equivalence_check.py --old ESKI.md --new YENI.md [--new EK.md ...] [--closed-decision DEGER ...] [--report RAPOR.md]

"Yeni" birden çok dosya olabilir (yeni gövde + EK karar günlüğü + araştırma notu); eski dokümandan çıkan her bilgi bu
KÜMEDE bulunmalıdır. Ölçümler:
  1. KİMLİK kümeleri : FR-/KR-/BR-/AC-/TC-/UT-/IT-/SCR-/S-/Ö-/V-/K-/BT-… — eski \\ yeni = boş olmalı.
  2. MOCKUP blokları : ``` bloklarının içerik satırlarının ≥ %90'ı yeni kümede.
  3. DEĞERLER        : BÜYÜK_HARF obje/alan adları (≥ 4), 4+ haneli sayılar, GG.AA.YYYY tarihleri, `kod` tokenları.
  4. CÜMLELER        : eski her cümle (≥ 40 karakter) yeni kümede difflib oranı ≥ 0.72 ile; kayıp oranı ≤ eşik.
  5. TERS YÖN        : --closed-decision değeri yeni pakette hâlâ geçiyor mu.
Çıkış: 0 DENK · 1 KAYIP VAR ya da kapanmış karar yaşıyor · 2 girdi okunamadı (bu "denk" DEĞİLDİR).
"""
from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path

for _a in (sys.stdout, sys.stderr):
    try:
        _a.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

SCOPE = ("KAPSAM (SCOPE): doc_equivalence_check — ESKİ → YENİ kümesinde kimlik, mockup bloğu, değer ve cümle kaybı; "
         "istenirse kapanmış kararın ters yönü. Ölçmedikleri raporun §6 bölümünde listelenir.")

ID_RES = [
    r"\bFR-\d{3}\b", r"\bKR-\d{3}\b", r"\bBR-\d{3}\b", r"\bAC-\d{2,3}[a-z]?\b", r"\bTC?-\d{2,3}\b",
    r"\bUT-\d{3}\b", r"\bIT-\d{3}\b", r"\bBT-\d{2}\b", r"\bÖK-\d{2}\b", r"\bÖ-\d{2}\b", r"\bV-\d{2}\b",
    r"\bG\d{1,2}(?:-P)?\b", r"\bKI-\d{2}\b", r"\bBG-\d{2}\b", r"\bSF-\d{2}\b", r"\bDÖ-\d{2}\b",
    r"\bR-\d{1,2}\b", r"\bS-\d{1,2}[a-d]?\b", r"\bN-\d\b", r"\bSCR-\d{3}\b", r"\bU-\d{2}\b",
    r"\b[PCOLMFB]-\d{2}\b",   # hata / bağımlılık kodları
    r"\bK-?\d{1,2}\b",        # kullanıcı isteği / karar (K1, K-01)
]
VALUE_RES = [
    r"\b[A-ZÇĞİÖŞÜ][A-Z0-9ÇĞİÖŞÜ_/]{3,}\b",   # obje/alan adları
    r"\b\d{4,}\b",                             # 4+ haneli sayı
    r"\b\d{2}\.\d{2}\.\d{4}\b",                # tarih
    r"`[^`\n]{2,60}`",                         # kod tokenı
]
# Vurgu amaçlı BÜYÜK sözcükler / durum adları veri değildir.
STOP_VALUES = {"YENİ", "HAZIR", "TAMAMLANDI", "İPTAL", "ONAY", "EVET", "HAYIR", "TÜMÜ", "GATE", "HIGH", "MEDIUM", "LOW",
               "AÇIKÇA", "KORUNUR", "OTOMATİK", "SERBEST", "SİLİNİR", "YENİDEN", "DEĞİL", "ZORUNLU", "YASAK", "AYNEN",
               "ASLA", "KESİN", "GERÇEK", "TEMSİLÎ", "KANITLI", "ÖNCE", "SONRA", "ARTIK", "HEMEN", "PASİF", "AKTİF",
               "KAPANDI", "REVİZE", "DÜŞÜRÜLDÜ", "BÜYÜK", "KÜÇÜK", "VEYA", "TAMAM", "BOŞTUR", "YOKTUR", "VARDIR",
               "BLOCKER", "WARNING", "PASS", "MÜKERRER", "İŞLENİYOR", "TÜKENDİ", "NOTE", "TODO"}
_EK_PREFIX = re.compile(r"^(?:Gövdede kalan sonuç|Taşınan metin(?: \(aynen\))?|Yeniden ifade edilen orijinal(?: \([^)]*\))?"
                        r"|Tür|Karar/kanıt no)\s*:\s*", re.IGNORECASE)

# Aracın ÖLÇMEDİKLERİ — yeşilin kapsamı okunabilsin diye her koşumda basılır.
NOT_MEASURED = [
    "yeni içeriğin DOĞRULUĞU (yalnız ESKİ→YENİ kayıp ölçülür)",
    "belgeler arası TUTARLILIK (aynı değer iki belgede çelişebilir)",
    "KORUNMUŞ AMA GEÇERSİZ değer: kapanmış bir kararın eski değeri 'elenmiştir' cümlesi içinde geçtiği için "
    "'korunmuş' sayılır (bkz. --closed-decision)",
    "kapsam SEÇİMİ: hangi belgelerin pakete dahil olduğu (çağıranın verdiğiyle yetinilir)",
]


class Unreadable(Exception):
    """Girdi okunamadı — 'kayıp var' ile aynı çıkışa düşmemeli (çıkış 2)."""


def read(p: str) -> str:
    try:
        return Path(p).read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        raise Unreadable(f"{p}: {e.__class__.__name__}: {e}") from None


def ids(text: str) -> set[str]:
    out: set[str] = set()
    for r in ID_RES:
        out.update(re.findall(r, text))
    return out


def values(text: str) -> set[str]:
    out: set[str] = set()
    for r in VALUE_RES:
        for m in re.findall(r, text):
            m = m.strip("`")
            if m in STOP_VALUES or len(m) < 4:
                continue
            out.add(m)
    return out


def code_blocks(text: str) -> list[list[str]]:
    blocks, cur, inb = [], [], False
    for ln in text.splitlines():
        if ln.strip().startswith("```"):
            if inb and cur:
                blocks.append(cur)
            cur, inb = [], not inb
            continue
        if inb:
            cur.append(ln.rstrip())
    return blocks


def _units(text: str) -> list[str]:
    """Karşılaştırma birimleri: satır kırılımlı paragraflar birleştirilir, tablo satırları hücrelere ayrılır."""
    units: list[str] = []
    para: list[str] = []
    inb = False

    def flush():
        if para:
            units.append(" ".join(para))
            para.clear()

    for ln in text.splitlines():
        s = ln.strip()
        if s.startswith("```"):
            flush()
            inb = not inb
            continue
        if inb:
            continue
        if not s or s.startswith("#") or s.startswith("|---"):
            flush()
            continue
        if s.startswith("|"):
            flush()
            units.extend(c.strip() for c in s.strip("|").split("|"))
            continue
        if s.startswith(("- ", "* ", "> ")) or re.match(r"^\d+\.\s", s):
            flush()
            para.append(s.lstrip("->* ").strip())
            continue
        para.append(s)
    flush()
    return units


def sentences(text: str) -> list[str]:
    out = []
    for u in _units(text):
        u = re.sub(r"[*_`]+", "", u).strip()
        u = _EK_PREFIX.sub("", u)
        for p in re.split(r"(?<=[.!?;])\s+", u):
            p = p.strip()
            if len(p) >= 40:
                out.append(p)
    return out


def kucult(s: str) -> str:
    """Türkçe duyarlı küçültme: "İ".lower() Python'da i + U+0307 üretir; düz lower() "KESİNLİKLE" ile
    "kesinlikle"yi eşitsiz sayar ve sahte kayıp üretir."""
    return s.replace("İ", "i").replace("I", "ı").replace("̇", "").lower()


def norm(s: str) -> str:
    return kucult(re.sub(r"\s+", " ", re.sub(r"[*_`>|]+", "", s)).strip())


def unscanned_siblings(new_paths: list[Path], old_path: Path) -> list[Path]:
    """Aynı klasörlerdeki, --new'e VERİLMEYEN .md dosyaları: eksik kapsam sessiz kalmasın."""
    given = {p.resolve() for p in new_paths} | {old_path.resolve()}
    found: list[Path] = []
    seen: set[Path] = set()
    for folder in sorted({p.parent for p in new_paths}):
        try:
            for c in sorted(folder.glob("*.md")):
                r = c.resolve()
                if r not in given and r not in seen:
                    seen.add(r)
                    found.append(c)
        except OSError:
            continue
    return found


def run(a: argparse.Namespace) -> tuple[int, str]:
    old = read(a.old)
    new_texts = [(p, read(p)) for p in a.new]
    new = "\n".join(t for _, t in new_texts)
    lines: list[str] = []
    P = lines.append

    P(SCOPE)
    P(f"## 0. Kapsam — taranan: {len(a.new) + 1} dosya")
    P(f"  eski (1): {a.old}")
    P(f"  yeni ({len(a.new)}): " + ", ".join(a.new))
    if not a.no_scope_warning:
        extra = unscanned_siblings([Path(p) for p in a.new], Path(a.old))
        if extra:
            P(f"  UYARI: AYNI KLASÖRDE TARANMAYAN {len(extra)} .md dosyası var — pakete dahilse --new ile ekle:")
            for c in extra:
                P(f"      - {c}")
        else:
            P("  (aynı klasörlerde taranmamış .md yok)")

    mi = sorted(ids(old) - ids(new))
    P(f"## 1. Kimlik kümeleri — eski {len(ids(old))} · yeni {len(ids(new))} · EKSİK {len(mi)}")
    if mi:
        P("  " + ", ".join(mi))

    nb_lines = {norm(l) for b in code_blocks(new) for l in b if l.strip()}
    lost_blocks = []
    ob = code_blocks(old)
    for k, b in enumerate(ob, 1):
        content = [norm(l) for l in b if l.strip()]
        if not content:
            continue
        ratio = sum(1 for l in content if l in nb_lines) / len(content)
        if ratio < 0.9:
            lost_blocks.append((k, ratio, b[0][:80]))
    P(f"## 2. Mockup/kod blokları — eski {len(ob)} · ≥%90 korunmayan {len(lost_blocks)}")
    for k, r, head in lost_blocks:
        P(f"  blok #{k} korunma %{r * 100:.0f} — {head}")

    # Token yeni metinde HARF DUYARSIZ geçiyorsa kaybolmamış, yalnız yeniden yazılmıştır.
    new_ci = kucult(new)
    old_vals = values(old)
    mv = sorted(v for v in (old_vals - values(new)) if kucult(v) not in new_ci)
    P(f"## 3. Değerler (obje/alan/sayı/tarih/kod) — eski {len(old_vals)} · EKSİK {len(mv)}")
    if mv:
        P("  " + ", ".join(mv[:200]) + (" …" if len(mv) > 200 else ""))

    ns = [norm(s) for s in sentences(new)]
    ns_set = set(ns)
    lost = []
    osents = sentences(old)
    for s in osents:
        n = norm(s)
        if n in ns_set:
            continue
        if not difflib.get_close_matches(n, ns, n=1, cutoff=a.fuzzy):
            lost.append(s)
    pct = 100.0 * len(lost) / max(1, len(osents))
    P(f"## 4. Cümleler (bulanık ≥{a.fuzzy}) — eski {len(osents)} · bulunmayan {len(lost)} (%{pct:.1f}; eşik %{a.sentence_loss_max})")
    for s in lost[:400]:
        P(f"  - {s[:200]}")

    closed_hits = []
    if a.closed_decision:
        P("")
        P(f"## 5. Kapanmış kararlar — TERS YÖN ({len(a.closed_decision)} değer arandı)")
        for value in a.closed_decision:
            target = kucult(value)
            hits = []
            for path, text in new_texts:
                for i, row in enumerate(text.splitlines(), 1):
                    if target in kucult(row):
                        hits.append((path, i, row.strip()))
            if hits:
                closed_hits.append((value, len(hits)))
                P(f"  BULGU `{value}` — YENİ pakette {len(hits)} geçiş (kapanmış kararın değeri hâlâ yaşıyor):")
                for path, i, row in hits[:40]:
                    P(f"      {path}:{i}: {row[:160]}")
                if len(hits) > 40:
                    P(f"      … +{len(hits) - 40} geçiş daha")
            else:
                P(f"  TEMİZ `{value}` — yeni pakette geçmiyor")
        if closed_hits:
            P("  Her geçişi SINIFLA: çözüm/koşul ise BLOCKER; reddedilen alternatif ya da ölçüm kaydı ise metinde AÇIKÇA öyle yazmalı.")

    P("")
    P("## 6. BU ARAÇ ŞUNLARI ÖLÇMEZ (yeşil = 'kayıp yok', 'belge doğru' DEĞİL)")
    for item in NOT_MEASURED:
        P(f"  - {item}")
    if not a.closed_decision:
        P("  - (bu koşumda --closed-decision verilmedi ⇒ ters yön HİÇ ölçülmedi)")

    ok = not mi and not lost_blocks and not mv and pct <= a.sentence_loss_max and not closed_hits
    P("")
    if closed_hits and not (mi or lost_blocks or mv) and pct <= a.sentence_loss_max:
        P("SONUÇ: KAPANMIŞ KARAR YAŞIYOR — veri kaybı yok, ama elenmiş değer(ler) yeni pakette duruyor (§5); sınıflanmadan onaya çıkmaz")
    else:
        P("SONUÇ: " + ("DENK — veri kaybı yok (1-3 sıfır, 4 eşik altı)" if ok
                       else "KAYIP VAR — yukarıdaki listeler kapatılmadan onaya çıkmaz"))
    return (0 if ok else 1), "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Doküman yeniden yazımında veri kaybı kontrolü")
    ap.add_argument("--old", required=True)
    ap.add_argument("--new", action="append", required=True, help="tekrarlanabilir: yeni gövde + EK + …")
    ap.add_argument("--report", default=None)
    ap.add_argument("--sentence-loss-max", type=float, default=3.0, help="yüzde; varsayılan 3")
    ap.add_argument("--fuzzy", type=float, default=0.72)
    ap.add_argument("--closed-decision", "--kapanmis-karar", dest="closed_decision", action="append", default=None,
                    metavar="DEGER", help="TERS YÖN: kapanmış kararın ESKİ DEĞERİ; yeni pakette geçerse bulgu. Tekrarlanabilir.")
    ap.add_argument("--no-scope-warning", "--kapsam-uyarisi-kapat", dest="no_scope_warning", action="store_true",
                    help="aynı klasördeki taranmamış .md uyarısını sustur")
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    try:
        rc, text = run(a)
    except Unreadable as e:
        print(SCOPE)
        print(f"[ÖLÇÜLEMEDİ] {e} — bu 'denk' ANLAMINA GELMEZ.", file=sys.stderr)
        return 2
    print(text)
    if a.report:
        Path(a.report).write_text("# Doküman denklik raporu\n\n- eski: `%s`\n- yeni: %s\n\n```\n%s\n```\n" % (
            a.old, ", ".join("`%s`" % p for p in a.new), text), encoding="utf-8")
    return rc


if __name__ == "__main__":
    sys.exit(main())
