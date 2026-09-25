#!/usr/bin/env python3
"""recall.py — işe başlarken ilgili ekip/proje derslerini, paket kurallarını ve skill'leri bulan hafif arama.

aXet'te her mesajda otomatik ders getiren bir mekanizma (hook) yoktur; bu script onun elle çağrılan
karşılığıdır. LLM ya da embedding kullanmaz: Türkçe harf katlamalı, ağırlıklı sözcük kesişimi.

Taranan kaynaklar:
  1. Ekip hafızası      <template>/memory/MEMORY.md satırları + indekste olmayan kayıtların `description`'ı
                        + kayıt dosyalarının GÖVDESİ (ilk GOVDE_SINIRI karakter)
  2. Proje hafızası     <proje>/.axet-code/memory/ (aynı kural)
  3. Paket kuralları    <proje>/<source_root>/**/.rules.md (source_root: <proje>/sap-project.json; yoksa taranmaz;
                        en çok RULES_DERINLIK klasör derinliği — paket klasörü <source_root>/<MODÜL>/<PAKET>/)
  4. Skill açıklamaları <template>/skills/*, <template>/skills-sap/*, <proje>/.axet-code/skills/* (gövde DEĞİL)

Puan (Z71, 2026-09-23 — gövde taraması eklendi):
  · başlık sözcükleri ×3 + özet sözcükleri ×1 (sorgudaki sözcük başlık/özette kaç kez geçiyorsa o kadar puan)
  · gövde: başlık/özette ZATEN eşleşmemiş her FARKLI sorgu sözcüğü için +GOVDE_AGIRLIK (tekrar sayılmaz).
    Gerekçe: indeks satırı ve description kaydın özenle yazılmış özetidir; gövde uzun ve gürültülüdür — tekrar
    sayılsaydı uzun kayıt kısa kaydı ezerdi. Eşik (5) değişmedi: yalnız gövdesiyle çıkan kaydın sorgunun en az
    beş farklı sözcüğünü taşıması gerekir. Türkçe ek/çoğul için önek eşleşmesi var (sorgu sözcüğü ≥ ONEK_EN_AZ harf ve
    kayıt sözcüğü onunla başlıyorsa: "aktarim" ↔ "aktarimi"); Z108'den beri başlık/özette de aynı kural geçerli
    ("transport" ↔ "transports").
  · Kayıtların çoğunda geçen (genel) sorgu sözcükleri puana katılmaz: başlık/özet için başlık/özetlerde, gövde için
    gövdelerde ayrı ayrı sayılır (bir sözcük özetlerde seyrek, gövdelerde yaygın olabilir). Başlık/özet sayımı TAM
    sözcükle yapılır (önekle sayılsaydı "review" → reviewer/reviews ile genel sayılıp düşerdi). Eşik altı sonuç basılmaz.
  · İstisna — gövde adayları: toplam puanı eşik altında kalan ama gövdesinde sorgunun ≥ GOVDE_ESIK farklı sözcüğü
    geçen en çok GOVDE_TOP kayıt ayrı ve "düşük güven" etiketiyle basılır. Ölçülen sebep (Z71 kapanış C3, 2026-09-23):
    model sorgusu "... ALV rapor Excel export ..." iken belirsiz indeksli kaydın gövdesi 3 sözcükle eşleşti, eşik 5'in
    altında kaldı ve kayıt görünmedi; aynı kaydı "dışa aktarım" da yazan sorgu buldu. Ana listenin eşiği değişmedi.
  · Eşik ölçekleme (Z108, 2026-09-24): --esik verilmezse eşik, başlık/özette genel sayılmayan sorgu terimi sayısına (n)
    göre min(5, max(1, 2n − 1)) olur: 1 terim → 1, 2 terim → 3, 3+ terim → 5 (değişmez). Ölçülen sebep: "transport"
    sorgusu açıklamasında terimi taşıyan skill'i (1-2 puan) sabit eşik 5'te hiç göstermiyordu. Ölçeklenmiş eşik YALNIZ
    gövdesiyle eşleşen kayda uygulanmaz (o kayıt yine 5 farklı sözcük ister). Açık --esik ölçeklenmez. Sorgunun tüm
    terimleri başlık/özetlerde genel sayılırsa ölçekleme yapılmaz ve UYARI basılır (sessiz boş sonuç yerine).

Kullanım:
  python recall.py "<görevin kısa özeti ve anahtar terimler>" [--project-dir DİZİN] [--top 5] [--esik N] [--json]
Çıkış kodu: 0 (sonuç olsun olmasın) · 3 kullanım hatası.
"""
from __future__ import annotations

import argparse
import json
import os
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
ESIK_VARSAYILAN = 5
GOVDE_AGIRLIK = 1
GOVDE_ESIK = 3            # eşik altı kalan kayıt, gövdesinde bu kadar FARKLI sorgu sözcüğü geçiyorsa ayrı listelenir
GOVDE_TOP = 3
GOVDE_SINIRI = 20000       # kayıt başına okunan gövde karakteri (performans üst sınırı; aşan kısım taranmaz)
ONEK_EN_AZ = 5             # önek eşleşmesi (gövde + Z108'den beri başlık/özet) için sorgu sözcüğünün en az harf sayısı
RULES_DERINLIK = 4         # <source_root> altında .rules.md aranan en derin klasör seviyesi
PAKET_OZ = "paket kuralları: obje adlandırma, önek, naming, bağımlılık, transport, istisna"
_LINK = re.compile(r"\[((?:[^\[\]]|\[[^\]]*\])+)\]\(([^)]+\.md)\)")
_FM = re.compile(r"^---\r?\n.*?\r?\n---\r?\n?", re.S)


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


def oku(yol: Path) -> str:
    try:
        with open(yol, encoding="utf-8", errors="replace") as fh:
            return fh.read(GOVDE_SINIRI + 4096)
    except OSError:
        return ""


def govde(metin: str) -> set[str]:
    return set(tokenle(_FM.sub("", metin, count=1)[:GOVDE_SINIRI]))


def kayit(tur: str, baslik: str, oz: str, yol: Path, govde_sozcukleri: set[str] | None = None) -> dict:
    anahtar = tokenle(baslik) * 3 + tokenle(oz)
    return {"tur": tur, "baslik": baslik.strip(), "oz": oz.strip()[:200], "yol": str(yol), "anahtar": anahtar,
            "govde": (govde_sozcukleri or set()) - set(anahtar)}


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
            metin = oku(hedef) if hedef.is_file() else ""
            if not oz and metin:
                oz = frontmatter(metin).get("description", "")
            gorulen.add(Path(dosya).name)
            out.append(kayit(tur, m.group(1), oz, hedef, govde(metin) if metin else None))
    for f in sorted(klasor.glob("*.md")):
        if f.name == "MEMORY.md" or f.name in gorulen:
            continue
        metin = oku(f)
        fm = frontmatter(metin)
        if fm.get("description"):
            out.append(kayit(tur + " (indekste yok)", fm.get("name") or f.stem, fm["description"], f, govde(metin)))
    return out


def source_root(proje: Path) -> Path | None:
    """<proje>/sap-project.json `source_root` alanı; dosya/alan yoksa ya da okunamazsa None (paket kuralı taranmaz)."""
    try:
        veri = json.loads((proje / "sap-project.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    kok = veri.get("source_root") if isinstance(veri, dict) else None
    if not isinstance(kok, str) or not kok.strip():
        return None
    return proje / kok.strip()


def paket_kurallari(proje: Path) -> list[dict]:
    kok = source_root(proje)
    if kok is None or not kok.is_dir():
        return []
    out = []
    for dizin, altlar, dosyalar in os.walk(kok):
        derinlik = len(Path(dizin).relative_to(kok).parts)
        if derinlik >= RULES_DERINLIK:
            altlar[:] = []
        altlar[:] = [a for a in altlar if not a.startswith(".")]
        if ".rules.md" not in dosyalar:
            continue
        f = Path(dizin) / ".rules.md"
        metin = oku(f)
        rel = Path(dizin).relative_to(kok).as_posix() or "."
        bas = re.search(r"\*\*Başlık:\*\*\s*(.+)", metin)
        oz = PAKET_OZ + (f" — {bas.group(1).strip()}" if bas else "")
        out.append(kayit("paket kuralı", f"{rel} paket kuralları (.rules.md)", oz, f, govde(metin)))
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


def eslesen(q: set[str], sozcukler: set[str]) -> set[str]:
    """Sözcük kümesinde geçen sorgu sözcükleri: tam eşleşme ya da (≥ ONEK_EN_AZ harfli sorgu sözcüğü için) önek eşleşmesi.
    Gövde ve indeks (başlık/özet) AYNI kuralı kullanır."""
    if not sozcukler:
        return set()
    bulunan = q & sozcukler
    for t in q - bulunan:
        if len(t) >= ONEK_EN_AZ and any(s.startswith(t) for s in sozcukler):
            bulunan.add(t)
    return bulunan


def sozcuk_eslesir(sozcuk: str, q: set[str]) -> bool:
    """Tek indeks sözcüğü sorgunun bir sözcüğüyle eşleşiyor mu (tam ya da `eslesen` ile aynı önek kuralı)."""
    return sozcuk in q or any(len(t) >= ONEK_EN_AZ and sozcuk.startswith(t) for t in q)


def varsayilan_esik(terim_sayisi: int) -> int:
    """Z108: varsayılan eşik, başlık/özette genel sayılmayan sorgu terimi sayısına (n) göre:
    min(ESIK_VARSAYILAN, max(1, 2n − 1)).
    n=1 → 1 · n=2 → 3 · n≥3 → 5 (değişmez). Önce/sonra ölçümünde k·n (k=1) 3-4 terimli sorgulara alakasız kayıt
    ekledi (ör. "mesaj sınıfı mesaj silme" eşik 3 → 2 alakasız ekip kaydı); 2n − 1 üç ve daha çok terimli sorguyu
    hiç değiştirmez."""
    return min(ESIK_VARSAYILAN, max(1, 2 * terim_sayisi - 1))


def main() -> int:
    ap = argparse.ArgumentParser(description="ekip/proje hafızası, paket kuralları ve skill araması")
    ap.add_argument("sorgu", nargs="+", help="görevin kısa özeti ve anahtar terimler")
    ap.add_argument("--project-dir", default=".", help="proje kökü (varsayılan: bulunulan dizin)")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--esik", type=int, default=None,
                    help=f"en düşük puan (verilmezse {ESIK_VARSAYILAN}; 1 terimli sorguda 1, 2 terimlide 3 — açık verilen "
                         "değer ölçeklenmez)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    proje = Path(args.project_dir).resolve()

    kaynaklar = {
        "ekip hafızası": hafiza_kayitlari("ekip hafızası", AXET_HOME / "memory"),
        "proje hafızası": hafiza_kayitlari("proje hafızası", proje / ".axet-code" / "memory"),
        "paket kuralı": paket_kurallari(proje),
        "skill": skill_kayitlari("skill", AXET_HOME / "skills") + skill_kayitlari("SAP skill", AXET_HOME / "skills-sap")
                 + skill_kayitlari("proje skill", proje / ".axet-code" / "skills"),
    }
    kayitlar = [k for liste in kaynaklar.values() for k in liste]
    govdeli = [k for k in kayitlar if k["govde"]]
    anahtar_kumeleri = [set(k["anahtar"]) for k in kayitlar]
    q_tum = set(tokenle(" ".join(args.sorgu)))
    genel: set[str] = set()
    govde_genel: set[str] = set()
    if kayitlar and q_tum:
        tavan = max(GENEL_ORAN * len(kayitlar), GENEL_TABAN)
        # Genel sayımı TAM eşleşmedir (önek DEĞİL), puanlama önekli olsa da. Ölçüldü (Z108 bug gate, tüketici projesi 55 kayıt,
        # tavan 4): önekle sayılınca "review" (tam 3 kayıt; reviewed/reviewer/reviewing/reviews ile 5) ve 22 terim daha
        # genel sayıldı, "code review" sorgusu code-review skill'ini kaybetti. Tam sayımla 4190 sentetik sorguda
        # (1-3 terim) tabanın (f2b2839) bulduğu kayıtlardan kaybolan 0; önekli sayımda 32.
        genel = {t for t in q_tum if sum(1 for a in anahtar_kumeleri if t in a) > tavan}
    if govdeli and q_tum:
        g_tavan = max(GENEL_ORAN * len(govdeli), GENEL_TABAN)
        sayim: dict[str, int] = {}
        for k in govdeli:
            for t in eslesen(q_tum, k["govde"]):
                sayim[t] = sayim.get(t, 0) + 1
        govde_genel = {t for t, n in sayim.items() if n > g_tavan}
    q = q_tum - genel
    q_govde = q_tum - govde_genel
    # Z108: varsayılan eşik başlık/özet puanı getirebilen terim sayısına (q = indekste genel sayılmayanlar) göre
    # ölçeklenir. q boşsa ölçeklenecek bir şey yoktur (indeks puanı alan kayıt olamaz) → varsayılan kalır.
    terim_sayisi = len(q)
    if args.esik is None and q:
        esik = varsayilan_esik(terim_sayisi)
        olceklendi = esik != ESIK_VARSAYILAN
    else:
        esik, olceklendi = (ESIK_VARSAYILAN if args.esik is None else args.esik), False
    # Ölçeklenmiş eşik yalnız başlık/özette eşleşen kayda uygulanır; YALNIZ gövdesiyle eşleşen kayıt varsayılan eşiği
    # (sorgunun ESIK_VARSAYILAN farklı sözcüğü) korur. Ölçüldü (tüketici projesi): aksi hâlde "test", "backend", "UI5 bootstrap
    # backend" sorgusu gövdesinde sözcüğü bir kez geçen alakasız kayıtları listeliyordu (sonuncusunda 7 kayıt).
    govde_esik = ESIK_VARSAYILAN if olceklendi else esik
    uyari = ""
    if q_tum and not q:
        uyari = (f"sorgunun tüm terimleri ({', '.join(sorted(q_tum))}) başlık/özetlerde genel sayıldı ve indeks puanına "
                 "katılmadı" + ("; gövdede de genel — hiçbir kayıt puan alamaz" if not q_govde else
                                f"; yalnız gövde eşleşmesi aranır (eşik {govde_esik})")
                 + ". Daha belirli bir terim ekle (obje tipi, işlem, araç adı).")

    def gecer(s: int, g: int) -> bool:
        return s >= (esik if s > g else govde_esik)

    def puanla(k: dict) -> tuple[int, int]:
        indeks_puani = sum(1 for a in k["anahtar"] if sozcuk_eslesir(a, q))
        govde_puani = GOVDE_AGIRLIK * len(eslesen(q_govde, k["govde"]) - eslesen(q_tum, set(k["anahtar"])))
        return indeks_puani + govde_puani, govde_puani

    skorlu = sorted(((*puanla(k), k) for k in kayitlar), key=lambda x: -x[0])
    sonuc = [(s, g, k) for s, g, k in skorlu if gecer(s, g)][: args.top]
    secilen = {id(k) for _, _, k in sonuc}
    govde_aday = [(s, g, k) for s, g, k in sorted(skorlu, key=lambda x: -x[1])
                  if id(k) not in secilen and not gecer(s, g) and g >= GOVDE_ESIK][:GOVDE_TOP]

    sayac = {ad: len(liste) for ad, liste in kaynaklar.items()}
    if args.json:
        print(json.dumps({"sonuc": [{"puan": s, "govde_puani": g, **{x: k[x] for x in ("tur", "baslik", "oz", "yol")}}
                                    for s, g, k in sonuc],
                          "govde_adaylari": [{"puan": s, "govde_puani": g, **{x: k[x] for x in ("tur", "baslik", "yol")}}
                                             for s, g, k in govde_aday],
                          "taranan": sayac, "govdesi_taranan": len(govdeli), "esik": esik,
                          "esik_varsayilan": ESIK_VARSAYILAN, "esik_olceklendi": olceklendi, "terim_sayisi": terim_sayisi,
                          "govde_esik": govde_esik, "uyari": uyari,
                          "genel_sayilan": sorted(genel), "govdede_genel_sayilan": sorted(govde_genel)},
                         ensure_ascii=False, indent=2))
        return 0
    if sonuc:
        print("İlgili olabilecek kayıtlar (hipotezdir; gerekirse kaynağı oku, alakasızsa yok say):")
        for s, g, k in sonuc:
            print(f"· [{k['tur']}] {k['baslik']} — {k['oz'][:110]}  (puan {s}"
                  + (f", gövdeden {g}" if g else "") + f")\n    {k['yol']}")
    if govde_aday:
        print(f"Yalnız GÖVDESİNDE sorgunun ≥ {GOVDE_ESIK} farklı sözcüğü geçen kayıtlar (düşük güven; indeks satırı konuyu "
              "söylemiyor olabilir — göreve dokunuyorsa aç):")
        for s, g, k in govde_aday:
            print(f"· [{k['tur']}] {k['baslik']}  (gövdede {g} sözcük)\n    {k['yol']}")
    if uyari:
        print(f"UYARI: {uyari}")
    if not sonuc and not govde_aday:
        print("Eşik üstü kayıt yok. Bu 'ilgili ders yok' demek DEĞİL: başka anahtar terimlerle tekrar dene "
              "ya da MEMORY.md indekslerini doğrudan oku.")
    print(f"KAPSAM: taranan {', '.join(f'{ad} {n}' for ad, n in sayac.items())} · gövdesi taranan kayıt {len(govdeli)} "
          f"(ilk {GOVDE_SINIRI} karakter) · eşik {esik}"
          + (f" (varsayılan {ESIK_VARSAYILAN}, {terim_sayisi} terimli sorgu için ölçeklendi) · yalnız gövdesiyle "
             f"eşleşen kayıt için eşik {govde_esik}" if olceklendi else "")
          + f" · gövde-aday eşiği {GOVDE_ESIK}"
          + (f" · genel sayılıp yok sayılan sözcükler: {', '.join(sorted(genel))}" if genel else "")
          + (f" · gövdede genel sayılan: {', '.join(sorted(govde_genel))}" if govde_genel else "")
          + (" · paket kuralı: sap-project.json source_root yok/okunamadı → taranmadı"
             if source_root(proje) is None else "")
          + f" · bakılmayan: skill gövdeleri ve referans dosyaları, paket SESSION_NOTES/SPEC ve kaynak kodu, "
            f"source_root altında {RULES_DERINLIK} seviyeden derin .rules.md, proje dokümanları")
    return 0


if __name__ == "__main__":
    sys.exit(main())
