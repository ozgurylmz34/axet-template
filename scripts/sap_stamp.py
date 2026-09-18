#!/usr/bin/env python3
"""Kesin yasak damgası: `core/sap/00-sap.md` içindeki KESİN YASAKLAR bölümünü SAP projesinin `AGENTS.md`'sine basar
ve denetler.

Neden: kesin yasaklar global kurulumdan (`install.py --sap`) yüklenir. O kurulum yapılmamış bir makinede SAP projesi
açılırsa yasaklar modele hiç gitmez. Proje kökündeki `AGENTS.md` ise aXet tarafından her oturum yüklenir (ölçüldü).
Damga, işaretler arasındaki bölümdür; `new_project.py --sap` basar/yeniler, `doctor.py` kanonik metinle karşılaştırır.
"""
from __future__ import annotations

import re
from pathlib import Path

AXET_HOME = Path(__file__).resolve().parents[1]
SAP_CORE = AXET_HOME / "core" / "sap" / "00-sap.md"
BASLA = "<!-- AXET-SAP-YASAKLAR:BASLA — new_project.py --sap basar; elle düzenleme, doctor.py denetler -->"
BITIR = "<!-- AXET-SAP-YASAKLAR:BITIR -->"
_BOLUM = re.compile(r"^## ⛔ KESİN YASAKLAR.*?(?=^## )", re.S | re.M)


def kanonik_blok() -> str:
    metin = SAP_CORE.read_text(encoding="utf-8")
    m_id = re.search(r"^SAP-CORE-ID:\s*(\S+)", metin, re.M)
    m = _BOLUM.search(metin)
    if not m or not m_id:
        raise RuntimeError(f"{SAP_CORE}: 'KESİN YASAKLAR' bölümü ya da SAP-CORE-ID satırı bulunamadı")
    return f"{BASLA}\nSAP-STAMP-ID: {m_id.group(1)}\n\n{m.group(0).strip()}\n{BITIR}"


def _norm(s: str) -> str:
    return "\n".join(line.rstrip() for line in s.replace("\r\n", "\n").strip().splitlines())


def _sinirlar(metin: str) -> tuple[int, int] | None:
    i, j = metin.find(BASLA), metin.find(BITIR)
    return (i, j + len(BITIR)) if i >= 0 and j > i else None


def govde(agents_metni: str) -> str:
    """Damga bloğu ÇIKARILMIŞ gövde (TASARIM §2b).

    `%guncelle-proje` üç sürümü (taban/yerel/yeni) bu gövde üzerinden karşılaştırır ve birleştirir;
    damgayı sonra `damgala()` yeniden basar. Blok çıkarılmazsa template'te damga olmadığı için her
    SAP projesinin `AGENTS.md`'si sonsuza dek "yerelde değişmiş" görünürdü.

    ⚠ `damgala()`nın TAM TERSİ olmalı, yoksa tek bir boş satır farkı bile dosyayı "değişmiş"
    gösterir (ölçüldü 2026-09-17: ilk sürüm `ust`u `rstrip`liyordu → her SAP AGENTS.md'si V4c
    çıktı). `damgala` başlıklı dosyada `<ust> + blok + "\\n\\n" + <alt>` yazar ⇒ tersi
    `<ust> + <alt'ın baştaki boş satırları atılmış hâli>`; `ust`a DOKUNULMAZ.
    """
    s = _sinirlar(agents_metni)
    if not s:
        return agents_metni
    # `lstrip("\r\n")`: CRLF'li bir dosyada yalnız "\n" atılırsa geride `\r` kalır ve gövde
    # tabandan farklı görünür (ölçüldü 2026-09-17).
    ust, alt = agents_metni[:s[0]], agents_metni[s[1]:].lstrip("\r\n")
    # Başlıksız dosyada `damgala` gövdeyi `rstrip()`leyip sonuna eklemişti; orada da simetrik ol.
    return (ust + alt) if alt else (ust.rstrip() + "\n")


def durum(agents_metni: str) -> str:
    """'yok' | 'farkli' | 'guncel'"""
    s = _sinirlar(agents_metni)
    if not s:
        return "yok"
    return "guncel" if _norm(agents_metni[s[0]:s[1]]) == _norm(kanonik_blok()) else "farkli"


_BASLA_ONEK = "AXET-SAP-YASAKLAR:BASLA"
_BITIR_ONEK = "AXET-SAP-YASAKLAR:BITIR"
KATEGORILER = ("A", "B", "C", "D")


def kanonik_denetle() -> tuple[bool, str]:
    """Template tarafı: kanonik bölüm okunuyor mu ve dört kategori satırını da taşıyor mu.

    Bölüm bir sonraki `## ` başlığında biter; araya yanlışlıkla `## ` girerse bölüm sessizce kısalır ve damga kısa
    metinle yenilenirdi. Kategori sayımı bunu yakalar.
    """
    try:
        blok = kanonik_blok()
    except (OSError, RuntimeError) as exc:
        return False, str(exc)
    eksik = [k for k in KATEGORILER if not re.search(rf"^\|\s*\*\*{k} — ", blok, re.M)]
    if eksik:
        return False, f"{SAP_CORE}: KESİN YASAKLAR bölümünde kategori satırı eksik: {', '.join(eksik)}"
    m = re.search(r"^SAP-STAMP-ID:\s*(\S+)", blok, re.M)
    return True, m.group(1) if m else "?"


def denetle(agents_metni: str) -> tuple[str, str]:
    """(durum, ayrıntı). durum: guncel | farkli | yok | bozuk | kanonik_yok.

    `durum()`'dan farkı: kanonik metin okunamazsa istisna yerine `kanonik_yok`; işaretler birden fazla ya da eksikse
    `bozuk` (ilk blok doğru, ikinci kopya değiştirilmişse `durum()` bunu görmez); `farkli` ayrıntısı sürüm farkı mı
    elle değişiklik mi ayırır.
    """
    try:
        kanon = kanonik_blok()
    except (OSError, RuntimeError) as exc:
        return "kanonik_yok", str(exc)
    nb, nt = agents_metni.count(_BASLA_ONEK), agents_metni.count(_BITIR_ONEK)
    if nb == 0 and nt == 0:
        return "yok", ""
    s = _sinirlar(agents_metni)
    if nb != 1 or nt != 1 or not s or agents_metni.count(BASLA) != 1:
        return "bozuk", f"işaret sayısı BASLA×{nb} BITIR×{nt} (tam 1'er ve değiştirilmemiş olmalı)"
    blok = agents_metni[s[0]:s[1]]
    if _norm(blok) == _norm(kanon):
        return "guncel", ""
    m_eski = re.search(r"^SAP-STAMP-ID:\s*(\S+)", blok, re.M)
    m_yeni = re.search(r"^SAP-STAMP-ID:\s*(\S+)", kanon, re.M)
    eski, yeni = (m_eski.group(1) if m_eski else "YOK"), (m_yeni.group(1) if m_yeni else "?")
    if eski != yeni:
        return "farkli", f"damga sürümü {eski} ≠ kanonik {yeni} (template güncellendi)"
    return "farkli", f"sürüm aynı ({eski}) ama metin kanonikten farklı (elle değiştirilmiş)"


def damgala(agents_metni: str) -> tuple[str, str]:
    """(yeni metin, önceki durum). Blok varsa yalnız işaretler arası yenilenir; yoksa ilk '## ' başlığından önce eklenir."""
    onceki = durum(agents_metni)
    if onceki == "guncel":
        return agents_metni, onceki
    blok = kanonik_blok()
    s = _sinirlar(agents_metni)
    if s:
        return agents_metni[:s[0]] + blok + agents_metni[s[1]:], onceki
    m = re.search(r"^## ", agents_metni, re.M)
    if m:
        return agents_metni[:m.start()] + blok + "\n\n" + agents_metni[m.start():], onceki
    return agents_metni.rstrip() + "\n\n" + blok + "\n", onceki
