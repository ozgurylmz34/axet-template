#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_fs_no_analysis_log.py — FS gövdesine "analiz günlüğü" sızmasını SAYAR (DOC-FS-05 / DOC-FS-06a, İlke 2b).

Neden: çok sürümlü bir FS'te her tur "v1.5'te eklendi", "canlı ölçüldü — ilk turda alan adı yanlış yazılmıştı",
"kullanıcı: '…'" gibi izler GÖVDEYE yazılınca belge, yapılacak işi tarif eden spesifikasyon olmaktan çıkıp çalışma
defterine döner. İlke 2b üç katman ister: gövde = kapanmış hedef durum · karar günlüğü (§11-A/§11-B + EK "Karar ve
kanıt günlüğü") · analiz süreci (ref_docs/RESEARCH-*.md). Bu araç katman-1'e (gövdeye) sızmayı satır bazında sayar.

Kullanım:
  python check_fs_no_analysis_log.py [YOL ...] [--tur fs,ek,ts,kd] [--bulguda-exit1] [--max-examples N]
  python check_fs_no_analysis_log.py --selftest
YOL bir dosyaysa adına bakılmadan doğrudan taranır. YOL bir klasörse (varsayılan: bulunulan klasör) yalnız adı `docs`
olan klasörlerin ALT AĞACINDAKİ `<TÜR>-*.md` dosyaları taranır (varsayılan tür: FS, EK; `--tur` ile TS/KD açılır).

Sayılan işaretler (sınıf sınıf raporlanır):
  A sürüm-etiketi   : v1.5 · v1.5-taslak · v1.6'da · "(YENİ, …)"
  B inceleme-ID     : kontrol listesi madde kimliği (DOC-KD-nn / DOC-FS-nn / DOC-TS-nn / DOC-CR-nn) · mimari karar
                      kaydı atfı (ADR-n / ADR n). Dokümanın KENDİ tablosunda tanımladığı kimliğe atıf sayılmaz.
  C süreç ifadesi   : canlı ölçüldü · DEV'de ölçüldü · ilk turda · yazılmıştı/okunmuştu · 400 döndü · ADT preview ·
                      adt_sql_query/adt_table_read/adt_get · RESEARCH-0n … ters/yanlış · doğrulanmıştır ·
                      kontrol edilmedi/ölçülmedi  (ileriye dönük "TS'te canlı ölçülür" MEŞRU, sayılmaz)
  D kullanıcı alıntı: "kullanıcı: '…'" · "kullanıcı notu/kararı/teyidi GG.AA"  (kısa atıf "kullanıcı isteği K-1" MEŞRU)
  E önceden→şimdi   : "önceden/eskiden … yerine" · "artık … değil/gösterilmez" · "R-6/S-3/K-7 revizyonu" ·
                      "bu revizyonla" · "önceki sürümde" · "ilk taslakta"
  §1.1 uzun satır   : versiyon tablosu satırı > 400 karakter (DOC-FS-06a)

Gövde DIŞI (taranmaz): H1 başlığı · §1.1 versiyon geçmişi (başlıklı ya da `| Versiyon | Tarih |` başlık satırıyla
tanınan başlıksız tablo; yalnız uzunluk ölçülür) · §1.3 ilgili dokümanlar · kapak `| Versiyon | v1.0 |` satırı ·
altbilgi "Doküman sonu" · kod blokları (mockup) · AÇIK ADLI karar günlüğü başlıkları ve ALT başlıkları (ör. EK altındaki
"### Yayılım tablosu"). Günlük başlığı başlık BAŞINDA aranır (önündeki §, ** ve bölüm numarası atılır): 11-A / 11-B /
11A / 11B · EKLER · "EK … Karar (ve kanıt) günlüğü" (EK ile başlar, önek uzunluğu serbest) · "Karar(lar) (ve kanıt)
günlüğü" · "Açık/Bekleyen kararlar" · "Danışman önerileri". Başlığın ortasında "karar önerileri" geçmesi YETMEZ
("4. Fonksiyonel gereksinimler ve karar önerileri" gövdedir). H1'i karar günlüğü olan dosyanın tamamı atlanır; H1'de
"EK" önünde doküman no olabilir ("FS-SD-001 EK — Karar ve Kanıt Günlüğü").

Çıkış: 0 = temiz YA DA bulgu var (varsayılan uyarıdır, kapı değildir) · 1 = bulgu var ve `--bulguda-exit1` verildi ·
2 = ölçülemedi — okunamayan dosya · UTF-8 olmayan dosya · okunamayan klasör · dosya sonunda kapanmamış kod bloğu ·
olmayan yol · hatalı argüman. 2 "temiz" DEĞİLDİR (o anda bulunan işaretler yine listelenir).
Sıfır kapsam (0 doküman) exit 0'dır ama "temiz" denmez; ayrı cümle basılır. Atlanan (_SKIP) bir klasör sayılamadıysa
çıkış değişmez ama sonuç "TEMİZ (taranan kapsamda)" diye nitelenir.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from collections import Counter
from pathlib import Path

for _akis in (sys.stdout, sys.stderr):
    try:
        _akis.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

SCOPE = ("KAPSAM (SCOPE): check_fs_no_analysis_log — FS gövdesinde satır bazında A sürüm-etiketi · B inceleme-ID · "
         "C süreç ifadesi · D kullanıcı alıntı · E önceden→şimdi işaretleri + §1.1 satır uzunluğu (> {max} karakter).")

# Aracın BAKMADIKLARI — "0 bulgu"nun kapsamı okunabilsin diye her koşumda basılır.
BAKILMAYANLAR = [
    "gövde dışı bırakılan bölümler: H1 · §1.1 versiyon geçmişi (yalnız uzunluk) · §1.3 ilgili dokümanlar · "
    "§11-A/§11-B · karar günlüğü/EK bölümleri ve alt başlıkları · kod blokları (mockup)",
    "DOC-FS-06b (11-B birikmemiş, yayılım tablosu tam) — anlam yargısıdır, inceleyici bakar",
    "üslup yargısı: desene uymayan süreç anlatısı (paragraf bugünkü hâli mi, nasıl bulunduğunu mu anlatıyor)",
    "bilerek sayılmayan belirsiz kalıplar: çıplak \"artık\" (isim de olabilir) · çıplak \"bu turda\" · "
    "canlı teyit turu başlıkları C-1…C-5 · BLOCKER/WARNING sözcükleri · tek haneli H-1/M-2/L-3 kimlikleri",
    "Türkçe dışındaki dillerde yazılmış FS (desenler Türkçedir)",
    "bölüm tanıma numara/başlık sezgisidir: \"1.1\"/\"1.3\" ile başlayan her başlık §1.1/§1.3 sayılır "
    "(\"1. Giriş\" altındaki \"1.1 Amaç\" · \"1.3.2\" alt numaraları dahil) — bu bölümler elle okunur",
    "Setext başlıklar (alt satırı === ya da --- olan başlık) başlık olarak tanınmaz; bölüm sınırı olarak işlemez",
    "liste maddesi içinde başlayan kod bloğu (\"- ```\" ya da girintili fence) kod sayılmaz; içi gövde gibi taranır",
    "D sınıfı yanlış pozitifi: adım metnindeki buton/alan alıntısı (Kullanıcı: \"Kaydet\" butonuna basar.) "
    "kullanıcı alıntısı sayılır — satır elle okunur",
    "UTF-8 dışı kodlanmış dosya (ÖLÇÜLEMEDİ yazılır, taranmaz) · dizin bağlantısı (junction/symlink) içeriği "
    "(izlenmez, KAPSAM satırında listelenir)",
]

_SKIP = {"node_modules", "dist", "tmp", ".tmp", ".git", "fixtures", "attic", "archive", "worktrees", "__pycache__"}
_TR = "A-Za-zÇĞİÖŞÜçğıöşü"

A, B, C, D, E = ("A sürüm-etiketi", "B inceleme-ID", "C süreç ifadesi", "D kullanıcı alıntı", "E önceden→şimdi")
PATTERNS = {
    A: re.compile(
        r"(?<![A-Za-z0-9])[vV]\d\.\d{1,2}(?:[a-c])?(?:-taslak)?(?![0-9])"   # v1.5, v1.5c, v1.8-taslak
        r"|\(\*{0,2}YENİ[,\s]"                                               # (YENİ, K-3) — BÜYÜK; "(yeni parça" değil
        r"|\b[vV]\d\.\d'(?:te|de|da|ta)\b"),                                  # v1.6'da
    # Bu template'in inceleme çıktısı kontrol listesi madde kimliğiyle raporlanır (doc-checklist.md: DOC-XX-NN).
    B: re.compile(
        r"(?<![%s0-9-])DOC-(?:KD|FS|TS|CR)-\d{2}[a-z]?(?![0-9])"
        r"|(?<![%s0-9-])ADR[- ]?\d{1,4}(?![0-9])" % (_TR, _TR)),
    C: re.compile(
        r"canlı ölç(?!ül(?:ür|ecek|meli|sün))|canlı teyit(?: edildi|li)|DEV'de ölç|DEV canlı|ilk turda"
        r"|yazılmıştı(?!r)|okumuştu|okunmuştu|sanılmış|sanıyordu"
        r"|400 döndü|\b400 verdi|ADT preview|\badt_(?:sql_query|table_read|get)\b"
        r"|RESEARCH-0\d[^|]{0,40}(?:ters|yanlış)"
        # `doğrulanmış(?!\s*ol)` → ileriye dönük "doğrulanmış OLMALI" gereksinimi MEŞRU.
        r"|doğrulanmıştır|doğrulanmış(?!\s*ol)|ölçümüyle|ölçümü ile|koddan (?:doğrulan|teyit|okun)"
        r"|(?:kontrol|test) edilmedi|sorgulanmadı|ölçülmedi", re.IGNORECASE),
    # re.IGNORECASE Türkçe ı/I/i/İ'yi eş sayar (ölçüldü): "KULLANICI", "Kullanici" de yakalanır.
    D: re.compile(
        r"kullanıcı(?:\s+\d\d\.\d\d)?\s*:\s*[\"“']"
        r"|kullanıcı (?:notu|kararı|teyidi|geri bildirimi)\s+\d\d\.\d\d", re.IGNORECASE),
    # Çıplak `artık` KULLANILMAZ: Türkçede isim de ("bölünmeyen artık miktar"). Sinyal onu izleyen değişim yüklemidir.
    # `değişti\b`: sınırsız hâli "değiştirilir" (iş kuralı) içinde eşleşir. `yerine` yalnız önceden/eskiden kolunda:
    # "artık … yerine" tasarım gerekçesinde meşrudur.
    E: re.compile(
        r"(?:önceden|eskiden|daha önce|eski(?:si|sinde))\b[^|]{0,60}(?:yerine|artık|değişti\b|kalktı|kaldırıldı)"
        r"|\bartık\b[^|]{0,50}(?:değil|kalktı|kalkar|gösterilmez|yazılmaz|üretilmez|kullanılmaz)"
        r"|\b[RSK]-\d{1,2}\s*(?:revizyonu|düzeltmesi|teyidi|netleşmesi|revizyonuyla)"
        r"|\bbu revizyon(?:la|dan|da)\b|\bönceki sürümde\b|\bilk taslakta\b", re.IGNORECASE),
}
VERSION_ROW_MAX = 400  # §1.1 satırı (karakter) — 1-2 satır "ne değişti"

# ── KATMAN-0: dokümanın KENDİ kimlik bilgisi (analiz günlüğü değil, temizlenemez) ──
_META_CELL0 = {"versiyon", "sürüm", "version", "doküman sürümü", "belge sürümü"}
# ⚠ Vurgu öneki `\s*(?:[*_`]+\s*)?` biçimindedir: `\s*[*_`]*\s*` iki `\s*` arasında boşluğu bölüştürüp uzun boşluklu
# satırda geri izleme patlaması yapıyordu (ölçüldü: "|" + 20000 boşluk → 69 s).
_EMP = r"\s*(?:[*_`]+\s*)?"
_DOC_REF_CELL0 = re.compile(
    r"^" + _EMP + r"(?:FS|TS|KD|EK|RESEARCH|INTAKE|SPEC|PRD)[-–—]|\.md[`*_\s)]*$", re.IGNORECASE)
_DOC_FOOTER = re.compile(r"^[*_\s>]*doküman sonu\b", re.IGNORECASE)
# Başlıksız versiyon tablosu BAŞLIK SATIRINDAN tanınır; yazım varyantları (`Versiyon`/`Ver.`) ikinci hücrenin
# Tarih/Date olmasıyla güvenli kılınır.
_VTABLE_HEADER = re.compile(
    r"^\|" + _EMP + r"(?:versiyon|sürüm|version|ver\.?|v\.?)" + _EMP + r"\|" + _EMP + r"(?:tarih|date)\b",
    re.IGNORECASE)
# Yalnız başlık BAŞINDA "1.1"/"1.3" (ör. "3.1.1 Alt süreç" §1.1 sayılmaz).
_VERSION_HEADING = re.compile(r"^1\.1\b|versiyon geçmişi|sürüm geçmişi", re.IGNORECASE)
_RELATED_HEADING = re.compile(r"^1\.3\b|ilgili doküman", re.IGNORECASE)
# Dokümanın KENDİ tanımladığı kimlik: `| **ADR-4** | … |` satırı. Aynı kimliğe gövdedeki atıf sayılmaz.
_B_TOKEN = re.compile(r"DOC-(?:KD|FS|TS|CR)-\d{2}[a-z]?|ADR[- ]?\d{1,4}")
_ID_TANIM_SATIRI = re.compile(r"^\|" + _EMP + r"(%s)" % _B_TOKEN.pattern + _EMP + r"\|")

# Katman-2 (karar günlüğü) YALNIZ açık adlı başlıklardır ve başlık BAŞINDA aranır (önce baştaki §/**/_ atılır):
# "11-A"/"11-B"/"11A"/"11B" (template §11-A danışman önerileri · §11-B açık kararlar; TS §11-A build-time teknik
# teyit) · "EKLER" (tek başına ya da ardından tire/iki nokta) · "EK … Karar(lar) (ve kanıt) günlüğü" (EK ile başlar,
# arada doküman no/ad olabilir — uzunluk sınırı yok) · "[N.] Karar(lar) (ve kanıt) günlüğü" · "Açık/Bekleyen
# kararlar" · "Danışman önerileri". Başlığın ortasında "karar" + "öneri/günlük" geçmesi YETMEZ:
# "4. Fonksiyonel gereksinimler ve karar önerileri" gövdedir.
_GUNLUK = r"karar(?:lar)?(?:\s+ve\s+kanıt)?\s+günlü"
_LOG_HEADING = re.compile(
    r"^(?:bölüm\s+)?11-?[AB]\b"
    r"|^ekler\s*(?:$|[—–:-])"
    r"|^ek\b.*?" + _GUNLUK +
    r"|^(?:(?:bölüm\s+)?\d+(?:\.\d+)*[.:]?\s+)?(?:" + _GUNLUK + r"|(?:açık|bekleyen)\s+karar|danışman\s+önerileri)",
    re.IGNORECASE)
# Yalnız H1 (bütün-dosya atlama) için: "EK" önünde doküman no olabilir — "# FS-SD-001 EK — Karar ve Kanıt Günlüğü".
_LOG_H1 = re.compile(r"(?:^|\s)ek\b.*?" + _GUNLUK, re.IGNORECASE)

_TURLER = ("fs", "ek", "ts", "kd")
_VARSAYILAN_TURLER = ("fs", "ek")


def _is_log_heading(h: str, h1: bool = False) -> bool:
    h2 = re.sub(r"^[\s*_§]+", "", h).rstrip("*_ \t")
    return bool(_LOG_HEADING.search(h2) or (h1 and _LOG_H1.search(h2)))


def _belge_ici_tanimli(lines) -> set:
    return {m.group(1) for ln in lines for m in [_ID_TANIM_SATIRI.match(ln.strip())] if m}


def _metadata_satiri(s: str) -> bool:
    """Tablo satırı dokümanın KİMLİĞİNİ mi bildiriyor (katman-0)? → gövde sayılmaz."""
    if not s.startswith("|") or s.startswith("|---"):
        return False
    hucreler = [c.strip() for c in s.strip("|").split("|")]
    c0 = re.sub(r"[*_`]+", "", hucreler[0]).strip().lower()
    return c0 in _META_CELL0 or bool(_DOC_REF_CELL0.search(hucreler[0]))


_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_FENCE = re.compile(r"^(`{3,}|~{3,})(.*)$")


def _satiri_tara(ln: str, ic_tanimli: set):
    """→ satırda eşleşen sınıflar (B için dokümanın kendi tanımladığı kimliğe atıf muafiyeti uygulanır)."""
    siniflar = []
    for k, rx in PATTERNS.items():
        if not rx.search(ln):
            continue
        if k == B:
            bulunan = {m.group(0) for m in _B_TOKEN.finditer(ln)}
            if bulunan and bulunan <= ic_tanimli:
                continue
        siniflar.append(k)
    return siniflar


def scan_text(text: str):
    """→ (findings {sınıf: [(satır, özet)]}, long_rows [(satır, uzunluk, etiket)], body_lines)."""
    return scan(text)[:3]


def _fence_ac(s: str):
    """Açılış fence'i → (karakter, uzunluk) ya da None. Backtick fence'in bilgi dizesinde backtick olamaz."""
    m = _FENCE.match(s)
    if not m or (m.group(1)[0] == "`" and "`" in m.group(2)):
        return None
    return m.group(1)[0], len(m.group(1))


def _fence_kapar(s: str, acik) -> bool:
    """Kapanış: aynı karakter, en az açılış uzunluğu, ardından yalnız boşluk (CommonMark)."""
    m = _FENCE.match(s)
    return bool(m and m.group(1)[0] == acik[0] and len(m.group(1)) >= acik[1] and not m.group(2).strip())


def scan(text: str):
    """→ (findings, long_rows, body_lines, acik_fence) — acik_fence: dosya sonunda kapanmamış kod bloğunun açıldığı
    satır (sonrası kod sayıldığı için TARANMADI) ya da None."""
    lines = text.splitlines()
    findings = {k: [] for k in PATTERNS}
    long_rows = []
    ic_tanimli = _belge_ici_tanimli(lines)
    # Dosyanın kendisi karar günlüğüyse (H1: "… Karar ve Kanıt Günlüğü") tamamı katman-2'dir.
    for ln in lines[:15]:
        m = _HEADING.match(ln.strip())
        if m and len(m.group(1)) == 1 and _is_log_heading(m.group(2), h1=True):
            return findings, long_rows, 0, None
    # bolum = (tür, seviye): "version" §1.1 · "related" §1.3 · "log" karar günlüğü. YALNIZ "log" türü daha DERİN alt
    # başlığa miras kalır (template'te EK karar günlüğünün altında "### Yayılım tablosu" durur); §1.1/§1.3 her
    # sonraki başlıkta kapanır. Aynı ya da üst seviye başlık her türü kapatır.
    bolum = None
    in_vtable = False
    acik = None                        # açık kod bloğu: (karakter, uzunluk, satır)
    body_lines = 0

    def _say(i, s, satir):
        for k in _satiri_tara(satir, ic_tanimli):
            findings[k].append((i, s[:110]))

    for i, ln in enumerate(lines, 1):
        s = ln.strip()
        if acik:                       # kod bloğu içi: "# yorum" satırı başlık sayılmaz
            if _fence_kapar(s, acik):
                acik = None
            continue
        f = _fence_ac(s)
        if f:
            acik = (f[0], f[1], i)
            continue
        m = _HEADING.match(s)
        if m:
            level, h = len(m.group(1)), m.group(2).strip()
            in_vtable = False
            if not (bolum and bolum[0] == "log" and level > bolum[1]):
                bolum = None
                if 2 <= level <= 3:
                    if _VERSION_HEADING.search(h):
                        bolum = ("version", level)
                    elif _is_log_heading(h):
                        bolum = ("log", level)
                    elif _RELATED_HEADING.search(h):
                        bolum = ("related", level)
            # Başlıklar da gövdedir (H1 = dokümanın kendi kimliği, taranmaz).
            if level > 1 and (bolum is None or bolum[0] == "related"):
                body_lines += 1
                _say(i, s, ln)
            continue
        if not s:
            in_vtable = False          # boş satır tabloyu kapatır: sonraki tablo yine gövdedir
            continue
        tur = bolum[0] if bolum else None
        if tur == "log":
            continue
        if tur == "version":
            if s.startswith("|") and not s.startswith("|---") and not _VTABLE_HEADER.match(s) \
                    and len(s) > VERSION_ROW_MAX:
                long_rows.append((i, len(s), "§1.1"))
            continue
        if s.startswith("|"):
            if _VTABLE_HEADER.match(s):
                in_vtable = True
                continue
        else:
            in_vtable = False
        if in_vtable:                  # başlıksız versiyon tablosu satırı = §1.1
            if not s.startswith("|---") and len(s) > VERSION_ROW_MAX:
                long_rows.append((i, len(s), "§1.1"))
            continue
        if (tur == "related" and s.startswith("|")) or _metadata_satiri(s) or _DOC_FOOTER.match(s):
            # katman-0 kimlik satırı: işaret sayılmaz ama uzunluk ölçütü YİNE uygulanır ("anlatıyı kimlik satırına
            # taşı" kaçışı olmasın).
            if not s.startswith("|---") and len(s) > VERSION_ROW_MAX:
                long_rows.append((i, len(s), "kimlik satırı"))
            continue
        body_lines += 1
        _say(i, s, ln)
    return findings, long_rows, body_lines, (acik[2] if acik else None)


# ── KAPSAM ────────────────────────────────────────────────────────────────────
def _docs_agacinda(dirpath: str, root: Path) -> bool:
    """`docs` bileşeni KÖKE GÖRELİ aranır: kökün üst dizininin adı `docs` ise bütün ağaç "docs" sayılmasın."""
    try:
        parcalar = Path(dirpath).relative_to(root).parts
    except ValueError:
        return False
    return root.name.lower() == "docs" or any(p.lower() == "docs" for p in parcalar)


def _tur(fn: str):
    low = fn.lower()
    if not low.endswith(".md"):
        return None
    for tur in _TURLER:
        if low.startswith(tur + "-"):
            return tur
    return None


def _baglanti_mi(yol: str) -> bool:
    """Dizin bağlantısı mı (symlink ya da Windows junction)? Bağlantı İZLENMEZ: ağaç dışına çıkabilir ya da döngü
    kurabilir (ölçüldü: kendi üst klasörüne dönen junction aynı dosyayı 15 kez saydırdı)."""
    if os.path.islink(yol):
        return True
    isjunction = getattr(os.path, "isjunction", None)          # Python 3.12+
    if isjunction is not None and isjunction(yol):
        return True
    try:                                                        # eski sürüm: gerçek yol, üstün gerçek yolu + ad mı?
        beklenen = os.path.join(os.path.realpath(os.path.dirname(yol)), os.path.basename(yol))
        return os.path.normcase(os.path.realpath(yol)) != os.path.normcase(beklenen)
    except OSError:
        return False


class Kapsam:
    """Tarama evreni: taranan hedefler + taranMAYANLARIN sayımı (hepsi aynı walk'tan türetilir)."""

    def __init__(self):
        self.hedefler = []           # [(yol, kök)]
        self.sayim = Counter()       # docs/ ağacındaki tür sayımı (taranan ve taranmayan türler)
        self.docs_disi = Counter()
        self.eksik = []              # olmayan yol
        self.dogrudan = 0
        self.klasor_hatasi = []      # [(yol, hata)] okunamayan klasör → ÖLÇÜLEMEDİ
        self.baglantilar = []        # izlenmeyen dizin bağlantıları (köke göreli)
        self.atlanan = []            # [(köke göreli klasör, Counter | None)] _SKIP klasörleri (None: sayılamadı)


def _atlanan_say(kok: str):
    c, hata = Counter(), []
    for dp, dn, fn in os.walk(kok, onerror=hata.append):
        dn[:] = [d for d in dn if not _baglanti_mi(os.path.join(dp, d))]
        for f in fn:
            t = _tur(f)
            if t:
                c[t] += 1
    return None if hata else c


def _kimlik(p) -> tuple:
    """Dosya/klasör KİMLİĞİ (st_dev, st_ino): büyük-küçük harf duyarlı klasörde "FS-A.md" ile "fs-a.md" iki ayrı
    dosyadır — normcase ikisini tek sayıp birini sessizce atlıyordu. st_ino verilmeyen sistemde gerçek yola düşer."""
    try:
        st = os.stat(p)
        if st.st_ino:
            return (st.st_dev, st.st_ino)
    except OSError:
        pass
    return ("yol", os.path.realpath(p))


def kapsam(yollar, turler=_VARSAYILAN_TURLER) -> Kapsam:
    k = Kapsam()
    # Çakışan kökler (kök + kök/docs) aynı dosyayı iki kez saymasın. İki ayrı küme: `taranan` yalnız GERÇEKTEN
    # hedefe eklenen dosyalar · `sayilan` walk'ta sayıma girenler. Tek küme kullanılınca walk'ta görülüp taranmayan
    # (docs/ dışı) dosya kümeye giriyor, aynı dosya ardından doğrudan verilince sessizce atlanıyordu.
    taranan, sayilan, gorulen_klasor = set(), set(), set()
    klasorler = []
    # 1. geçiş: doğrudan verilen dosyalar (argüman sırasından bağımsız) · 2. geçiş: klasörler.
    for ham in yollar:
        yol = Path(ham)
        if yol.is_file():
            anahtar = _kimlik(yol)
            if anahtar not in taranan:
                taranan.add(anahtar)
                k.hedefler.append((yol, yol.parent))
                k.dogrudan += 1
        elif yol.is_dir():
            klasorler.append(yol)
        else:
            k.eksik.append(yol)
    for yol in klasorler:
        root = yol.resolve()
        # onerror: okunamayan klasör eskiden sessizce atlanıyordu ve sonuç "TEMİZ" çıkıyordu.
        for dirpath, dirnames, filenames in os.walk(root, onerror=lambda e: k.klasor_hatasi.append(
                (getattr(e, "filename", None) or "?", e))):
            anahtar = _kimlik(dirpath)
            if anahtar in gorulen_klasor:
                dirnames[:] = []
                continue
            gorulen_klasor.add(anahtar)
            kalan = []
            for d in sorted(dirnames):
                tam = os.path.join(dirpath, d)
                rel = Path(tam).relative_to(root).as_posix()
                if _baglanti_mi(tam):
                    k.baglantilar.append(rel)
                elif d.lower() in _SKIP:
                    k.atlanan.append((rel, _atlanan_say(tam)))
                else:
                    kalan.append(d)
            dirnames[:] = kalan
            docs = _docs_agacinda(dirpath, root)
            for fn in sorted(filenames):
                tur = _tur(fn)
                if tur is None:
                    continue
                p = os.path.join(dirpath, fn)
                anahtar = _kimlik(p)
                if anahtar in taranan or anahtar in sayilan:
                    continue                    # doğrudan verilip taranmış ya da başka kökte zaten sayılmış
                sayilan.add(anahtar)
                if not docs:
                    k.docs_disi[tur] += 1
                    continue
                k.sayim[tur] += 1
                if tur in turler:
                    taranan.add(anahtar)
                    k.hedefler.append((Path(p), root))
    return k


def _sayim_metni(c) -> str:
    if c is None:
        return "sayılamadı"
    return " / ".join("%s %d" % (t.upper(), c[t]) for t in _TURLER if c[t]) or "tür dosyası yok"


def kapsam_beyani(turler, k: Kapsam, liste_siniri: int = 10) -> str:
    """Taranan VE taranmayan her şeyin sayısı aynı walk'tan türetilir; sıfır-bulgu anında da basılır."""
    taranan = sum(k.sayim[t] for t in turler)
    parca = ["KAPSAM: %s %d tarandı (docs/ alt ağacı)" % ("/".join(t.upper() for t in turler), taranan)]
    disarida = [t for t in _TURLER if t not in turler]
    if disarida:
        parca.append("%s TARANMADI (--tur %s ile aç)" % (
            " / ".join("%s %d" % (t.upper(), k.sayim[t]) for t in disarida), ",".join(_TURLER)))
    else:
        parca.append("taranmayan tür yok")
    if sum(k.docs_disi.values()):
        parca.append("docs/ DIŞINDA %s TARANMADI (dosyayı doğrudan ver)" % _sayim_metni(k.docs_disi))
    if k.atlanan:
        ogeler = ["%s (%s)" % (rel, _sayim_metni(c)) for rel, c in k.atlanan[:liste_siniri]]
        if len(k.atlanan) > liste_siniri:
            ogeler.append("… %d klasör daha" % (len(k.atlanan) - liste_siniri))
        parca.append("ATLANAN KLASÖR %s TARANMADI" % ", ".join(ogeler))
    if k.baglantilar:
        ogeler = k.baglantilar[:liste_siniri] + (
            ["… %d bağlantı daha" % (len(k.baglantilar) - liste_siniri)] if len(k.baglantilar) > liste_siniri else [])
        parca.append("BAĞLANTI (junction/symlink) İZLENMEDİ: %s" % ", ".join(ogeler))
    if k.dogrudan:
        parca.append("doğrudan verilen dosya %d (adına ve türüne bakılmadan tarandı)" % k.dogrudan)
    return " · ".join(parca)


def _oku(p: Path) -> str:
    # utf-8-sig: BOM'lu dosyada ilk satır U+FEFF ile başlar ve H1 başlık olarak tanınmaz; bu kodlama BOM'u atar.
    # KATI çözme: errors="replace" UTF-16 dosyayı "işaret yok" gösteriyordu → UnicodeDecodeError = ÖLÇÜLEMEDİ.
    return p.read_bytes().decode("utf-8-sig")


def _report(path: Path, root: Path, findings, long_rows, body_lines, max_examples) -> int:
    total = sum(len(v) for v in findings.values())
    if total == 0 and not long_rows:
        return 0
    try:
        rel = path.resolve().relative_to(root.resolve())
    except ValueError:
        rel = path
    print("[WARN] %s: gövde %d satır — analiz-günlüğü işareti %d satır%s" % (
        rel, body_lines, total, (" · uzun satır %d" % len(long_rows)) if long_rows else ""))
    for k, v in findings.items():
        if not v:
            continue
        print("    %s: %d" % (k, len(v)))
        for ln, sn in v[:max_examples]:
            print("       :%d  %s" % (ln, sn))
    for ln, n, etiket in long_rows[:max_examples]:
        print("    %s :%d  %d karakter (> %d) — 1-2 satıra indir, gerekçeyi EK karar günlüğüne taşı" % (
            etiket, ln, n, VERSION_ROW_MAX))
    return total + len(long_rows)


# Template FS şablonunun bölüm yapısıyla (templates/FS-template.md) kırmızı örnek.
RED_FIXTURE = """# FS-XX-999 — Örnek
| Alan | Değer |
|---|---|
| Versiyon | v1.5 |

## 1. Doküman kontrolü
### 1.1 Versiyon geçmişi
| Versiyon | Tarih | Değiştiren | Ne değişti |
|---|---|---|---|
| v1.5-taslak | 01.01.2026 | X | """ + ("uzun anlatı " * 40) + """ |

### 1.3 İlgili dokümanlar
| Doküman | No | Not |
|---|---|---|
| Kullanıcı kılavuzu | KD-XX-999 | v0.9 yazıldı |

## 3. İş süreci
Fatura tipi ZM12 seçilir (DEV canlı ölçüldü; ilk turda alan adı yanlış yazılmıştı, 400 döndü).
| FR-004 | (**YENİ, K-3**) Kontrol Et butonu (DOC-FS-05 bulgusu) |
Kullanıcı: "fiyat koşulumuz Z001 olmalı" — kullanıcı notu 17.08.
Müşteri malzeme no artık kalem satırında gösterilmez (K-6 revizyonu).
Hata kodu L-01 ve M-2 meşru hata kodudur.
Bakiye artık sayılmaz; bölünmeyen artık miktar hesaba katılır.

## 11-B. Açık kararlar
| S-19 | v1.7'de eklendi, DOC-FS-05 | katman-2, sayılmaz |

## EK — Karar ve kanıt günlüğü
### Yayılım tablosu
| K-01 | v1.6'da işlendi, canlı ölçüldü | yapıldı | |
"""


def selftest() -> int:
    f, lr, _ = scan_text(RED_FIXTURE)
    satirlar = RED_FIXTURE.splitlines()
    ok = True
    for k in PATTERNS:
        if not f[k]:
            print("[SELFTEST-FAIL] %s yakalanmadı" % k)
            ok = False
    ilgili = next(i for i, s in enumerate(satirlar, 1) if "KD-XX-999" in s)
    karar = next(i for i, s in enumerate(satirlar, 1) if s.startswith("## 11-B"))
    if any(ln == ilgili or ln >= karar for k in f for ln, _ in f[k]):
        print("[SELFTEST-FAIL] §1.3 kimlik satırı ya da 11-B/EK (alt başlık dahil) gövde sayıldı")
        ok = False
    if any("L-01" in sn or "Bakiye" in sn for k in f for _, sn in f[k]):
        print("[SELFTEST-FAIL] meşru hata kodu ya da isim 'artık' işaretlendi")
        ok = False
    if not any(etiket == "§1.1" for _, _, etiket in lr):
        print("[SELFTEST-FAIL] §1.1 uzun satır yakalanmadı")
        ok = False
    f2, lr2, bl2 = scan_text("# EK-B — Karar ve kanıt günlüğü\n\n## K-22\nv1.5 canlı ölçüldü, kullanıcı: \"x\"\n")
    if sum(len(v) for v in f2.values()) or lr2 or bl2:
        print("[SELFTEST-FAIL] H1'i karar günlüğü olan dosya taranmamalıydı")
        ok = False
    print("[SELFTEST] " + ("OK — kırmızı örnek yakalandı, kimlik satırları/katman-2/meşru kodlar atlandı" if ok else "FAIL"))
    return 0 if ok else 1


def _turleri_coz(tur_arg):
    if tur_arg is None:
        return _VARSAYILAN_TURLER
    istenen = [t for t in (x.strip().lower() for x in tur_arg.split(",")) if t]
    if not istenen or any(t not in _TURLER for t in istenen):
        return None
    return tuple(t for t in _TURLER if t in istenen)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="FS gövdesinde analiz-günlüğü işareti sayımı (DOC-FS-05 / DOC-FS-06a)")
    ap.add_argument("yollar", nargs="*", metavar="YOL", help="dosya ya da klasör (varsayılan: bulunulan klasör)")
    ap.add_argument("--tur", default=None, help="taranacak türler: fs,ek,ts,kd (varsayılan fs,ek)")
    ap.add_argument("--bulguda-exit1", action="store_true", help="bulgu varsa çıkış 1 (varsayılan: uyarı, çıkış 0)")
    ap.add_argument("--max-examples", type=int, default=3, help="sınıf başına örnek satır sayısı")
    ap.add_argument("--selftest", action="store_true", help="gömülü kırmızı örnekle kendini sına")
    try:
        a = ap.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    if a.selftest:
        return selftest()
    print(SCOPE.format(max=VERSION_ROW_MAX))
    turler = _turleri_coz(a.tur)
    if turler is None:
        print("[HATA] --tur yalnız %s değerlerini alır; verilen: %r." % (",".join(_TURLER), a.tur))
        return 2
    if a.max_examples < 0:
        print("[HATA] --max-examples negatif olamaz.")
        return 2
    yollar = a.yollar or ["."]
    k = kapsam(yollar, turler)
    total = n_docs = okunamadi = acik_fence = 0
    for yol in k.eksik:
        print("[ÖLÇÜLEMEDİ] %s: yol yok — bu 'işaret yok' ANLAMINA GELMEZ." % yol)
    for yol, e in k.klasor_hatasi:
        print("[ÖLÇÜLEMEDİ] %s: klasör okunamadı (%s: %s) — içindeki dokümanlar TARANMADI, bu 'işaret yok' "
              "ANLAMINA GELMEZ." % (yol, e.__class__.__name__, e))
    for p, root in k.hedefler:
        n_docs += 1
        try:
            text = _oku(p)
        except (OSError, UnicodeDecodeError) as e:
            neden = "UTF-8 değil" if isinstance(e, UnicodeDecodeError) else "okunamadı"
            print("[ÖLÇÜLEMEDİ] %s: %s (%s: %s) — bu 'işaret yok' ANLAMINA GELMEZ." % (
                p, neden, e.__class__.__name__, e))
            okunamadi += 1
            continue
        f, lr, bl, fence_satiri = scan(text)
        total += _report(p, root, f, lr, bl, a.max_examples)
        if fence_satiri:
            print("[ÖLÇÜLEMEDİ] %s: satır %d'de açılan kod bloğu kapanmadı — sonrası kod sayıldı ve TARANMADI." % (
                p, fence_satiri))
            acik_fence += 1
    print(kapsam_beyani(turler, k))
    print("BU ARAÇ ŞUNLARA BAKMAZ:")
    for b in BAKILMAYANLAR:
        print("  - " + b)
    if okunamadi or k.eksik or k.klasor_hatasi or acik_fence:
        print("SONUÇ: ÖLÇÜLEMEDİ — %d doküman okunamadı, %d dokümanda kod bloğu kapanmadı, %d klasör okunamadı, "
              "%d yol bulunamadı; bulunan işaret %d satır (çıkış 2)." % (
                  okunamadi, acik_fence, len(k.klasor_hatasi), len(k.eksik), total))
        return 2
    if n_docs == 0:
        kokler = ", ".join(str(Path(y).resolve()) for y in yollar)
        print("SONUÇ: DENETLENECEK DOKÜMAN BULUNAMADI (0 doküman) — sıfır kapsam ihlal değildir ama 'işaret yok' da "
              "değildir. Aranan kök: %s (docs/ alt ağacında %s-*.md)." % (
                  kokler, "/".join(t.upper() for t in turler)))
        return 0
    if total == 0:
        sayilamadi = sum(1 for _, c in k.atlanan if c is None)
        if sayilamadi:
            # Çıkış değişmez (atlanan klasör zaten taranmaz) ama "temiz" nitelensin: içinde ne olduğu bilinmiyor.
            print("SONUÇ: TEMİZ (taranan kapsamda) — %d atlanan klasör sayılamadı; %d doküman, gövdede işaret yok "
                  "(yalnız KAPSAM satırındaki yüzeyde)." % (sayilamadi, n_docs))
            return 0
        print("SONUÇ: TEMİZ — %d doküman, gövdede işaret yok (yalnız KAPSAM satırındaki yüzeyde)." % n_docs)
        return 0
    print("SONUÇ: %d işaretli satır (%d doküman) — UYARI, kapı değil. Gövde = kapanmış hedef durum; sürüm etiketi, "
          "inceleme kimliği, süreç ifadesi, kullanıcı alıntısı ve önceden→şimdi anlatısı EK karar günlüğüne "
          "(references/fs-authoring.md İlke 2b)." % (total, n_docs))
    return 1 if a.bulguda_exit1 else 0


if __name__ == "__main__":
    sys.exit(main())
