#!/usr/bin/env python3
"""recall.py — işe başlarken ilgili ekip/proje derslerini ve skill'leri bulan hafif arama.

aXet'te her mesajda otomatik ders getiren bir mekanizma (hook) yoktur; bu script onun elle çağrılan
karşılığıdır. LLM ya da embedding kullanmaz: Türkçe harf katlamalı, ağırlıklı sözcük kesişimi.

Taranan kaynaklar (yalnız indeks satırı ve açıklama; tam metin DEĞİL — gerekirse kaynağı `view` ile oku):
  1. Ekip hafızası      <template>/memory/MEMORY.md satırları + indekste olmayan kayıtların `description`'ı
  2. Proje hafızası     <proje>/.axet-code/memory/MEMORY.md (aynı kural)
  3. Skill açıklamaları <template>/skills/*, <template>/skills-sap/*, <proje>/.axet-code/skills/*

Puan: başlık sözcükleri ×3 + özet sözcükleri ×1; sorgudaki sözcük kaydın başlık/özetinde kaç kez geçiyorsa o
kadar puan. Kayıtların çoğunda geçen (genel) sorgu sözcükleri puana katılmaz. Eşik altı sonuç basılmaz.

Kullanım:
  python recall.py "<görevin kısa özeti ve anahtar terimler>" [--project-dir DİZİN] [--top 5] [--esik 5] [--json]
Çıkış kodu: 0 (sonuç olsun olmasın) · 3 kullanım hatası.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

AXET_HOME = Path(__file__).resolve().parents[3]
_TR = str.maketrans("İIıŞşĞğÜüÖöÇç", "iiissgguuoocc")
_STOP = {"ve", "ile", "icin", "bir", "bu", "da", "de", "the", "for", "and", "yok", "var", "olan", "her",
         "yap", "olarak", "sonra", "gibi", "daha", "cok", "ama", "nasil", "neden", "hangi", "ise", "kullan"}
GENEL_ORAN = 0.05
GENEL_TABAN = 4
_LINK = re.compile(r"\[((?:[^\[\]]|\[[^\]]*\])+)\]\(([^)]+\.md)\)")


def tokenle(s: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9_]{3,}", s.translate(_TR).lower()) if t not in _STOP]


def frontmatter(text: str) -> dict:
    m = re.match(r"^---\r?\n(.*?)\r?\n---", text, re.S)
    if not m:
        return {}
    out, key = {}, None
    for line in m.group(1).splitlines():
        if line and line[0] not in " \t" and ":" in line:
            key, _, val = line.partition(":")
            key, val = key.strip(), val.strip()
            out[key] = "" if val in (">", "|", ">-", "|-") else val.strip("'\"")
        elif key and line.strip():
            out[key] = (out[key] + " " + line.strip()).strip()
    return out


def kayit(tur: str, baslik: str, oz: str, yol: Path) -> dict:
    return {"tur": tur, "baslik": baslik.strip(), "oz": oz.strip()[:200], "yol": str(yol),
            "anahtar": tokenle(baslik) * 3 + tokenle(oz)}


def hafiza_kayitlari(tur: str, klasor: Path) -> list[dict]:
    indeks = klasor / "MEMORY.md"
    if not klasor.is_dir():
        return []
    out, gorulen = [], set()
    if indeks.is_file():
        for satir in indeks.read_text(encoding="utf-8", errors="replace").splitlines():
            m = _LINK.search(satir)
            if not m or not satir.lstrip().startswith("-"):
                continue
            dosya = m.group(2).strip()
            oz = satir[m.end():].strip().lstrip("—-–:").strip()
            hedef = klasor / dosya
            if not oz and hedef.is_file():
                oz = frontmatter(hedef.read_text(encoding="utf-8", errors="replace")).get("description", "")
            gorulen.add(Path(dosya).name)
            out.append(kayit(tur, m.group(1), oz, hedef))
    for f in sorted(klasor.glob("*.md")):
        if f.name == "MEMORY.md" or f.name in gorulen:
            continue
        fm = frontmatter(f.read_text(encoding="utf-8", errors="replace"))
        if fm.get("description"):
            out.append(kayit(tur + " (indekste yok)", fm.get("name") or f.stem, fm["description"], f))
    return out


def skill_kayitlari(tur: str, kok: Path) -> list[dict]:
    out = []
    if not kok.is_dir():
        return out
    for skill in sorted(kok.glob("*/SKILL.md")):
        fm = frontmatter(skill.read_text(encoding="utf-8", errors="replace"))
        ad = fm.get("name") or skill.parent.name
        out.append(kayit(tur, ad.replace("-", " ") + f" (%{ad})", fm.get("description", ""), skill))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="ekip/proje hafızası ve skill araması")
    ap.add_argument("sorgu", nargs="+", help="görevin kısa özeti ve anahtar terimler")
    ap.add_argument("--project-dir", default=".", help="proje kökü (varsayılan: bulunulan dizin)")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--esik", type=int, default=5, help="en düşük puan (varsayılan 5)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    proje = Path(args.project_dir).resolve()

    kaynaklar = {
        "ekip hafızası": hafiza_kayitlari("ekip hafızası", AXET_HOME / "memory"),
        "proje hafızası": hafiza_kayitlari("proje hafızası", proje / ".axet-code" / "memory"),
        "skill": skill_kayitlari("skill", AXET_HOME / "skills") + skill_kayitlari("SAP skill", AXET_HOME / "skills-sap")
                 + skill_kayitlari("proje skill", proje / ".axet-code" / "skills"),
    }
    kayitlar = [k for liste in kaynaklar.values() for k in liste]
    q = set(tokenle(" ".join(args.sorgu)))
    if kayitlar and q:
        tavan = max(GENEL_ORAN * len(kayitlar), GENEL_TABAN)
        genel = {t for t in q if sum(1 for k in kayitlar if t in k["anahtar"]) > tavan}
        q -= genel
    else:
        genel = set()
    skorlu = sorted(((sum(1 for a in k["anahtar"] if a in q), k) for k in kayitlar),
                    key=lambda x: -x[0])
    sonuc = [(s, k) for s, k in skorlu if s >= args.esik][: args.top]

    sayac = {ad: len(liste) for ad, liste in kaynaklar.items()}
    if args.json:
        print(json.dumps({"sonuc": [{"puan": s, **{x: k[x] for x in ("tur", "baslik", "oz", "yol")}} for s, k in sonuc],
                          "taranan": sayac, "esik": args.esik, "genel_sayilan": sorted(genel)},
                         ensure_ascii=False, indent=2))
        return 0
    if sonuc:
        print("İlgili olabilecek kayıtlar (hipotezdir; gerekirse kaynağı oku, alakasızsa yok say):")
        for s, k in sonuc:
            print(f"· [{k['tur']}] {k['baslik']} — {k['oz'][:110]}  (puan {s})\n    {k['yol']}")
    else:
        print("Eşik üstü kayıt yok. Bu 'ilgili ders yok' demek DEĞİL: başka anahtar terimlerle tekrar dene "
              "ya da MEMORY.md indekslerini doğrudan oku.")
    print(f"KAPSAM: taranan {', '.join(f'{ad} {n}' for ad, n in sayac.items())} · eşik {args.esik}"
          + (f" · genel sayılıp yok sayılan sözcükler: {', '.join(sorted(genel))}" if genel else "")
          + " · bakılmayan: kayıt/skill gövdeleri, skill referans dosyaları, proje dokümanları")
    return 0


if __name__ == "__main__":
    sys.exit(main())
