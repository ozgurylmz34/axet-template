# -*- coding: utf-8 -*-
"""sapadt/populate.py — CSV/dizin girdisinden TOPLU obje yazımı (aXet, 2026-09-14; IMPLEMENTATION.md §19).

Türler: `domain` · `dtel` · `cds` · `enqu` (kilit objesi) · `msag` (tek mesaj sınıfının mesajları).
Tablo türü YOK (karar: template Z tablo kabuğu yaratmaz — `tools/shells.py` DESTEKLENMEYEN['table']).

⛔ İKİNCİ BİR YAZMA YOLU DEĞİLDİR. Her adım `sap_adt_cli.calistir` ile koşar (imza → `gate.check_write`
   → profil → araç guard'ları → gömülü reviewer → write-log → sır temizliği); bu modül SAP'ye kendisi
   hiçbir istek atmaz, kütüphane istemcisi kurmaz.

Sıra (fail-closed):
  1. Girdi doğrulaması — TÜM bulgular tek seferde; bulgu varsa hiçbir çağrı yapılmaz (çıkış 3).
  2. ÖN GEÇİŞ — her hedefin HER planlı çağrısı (okuma dahil; `--force-recreate` ile `adt_delete` de)
     `sap_adt_cli.on_kontrol` ile kapıdan geçirilir. Tek red → hiçbir şey yazılmaz (çıkış 2).
  3. Yürütme — hedef hedef; her çağrıda kapı yeniden koşar.

Varlık sondası üç değerlidir: ölçülemedi → o hedef HATA, yazma yok. Var + `--force-recreate` yok → ATLANDI
(yazılmadı; başarı sayılmaz, ayrı sayılır). Sonda: domain/dtel/cds `adt_get(include_source=false)` · enqu
`adt_get(enqu)` (salt GET; varsa daima ATLANDI — kilit objesi güncellenmez/silinmez) · msag `adt_msgclass_read`.

Kilit: bu modül kilit almaz/bırakmaz/temizlemez; kilidi araçlar alır ve hata dalında bırakır. Kilit çakışması
→ o satır HATA + SM12 tarifi (`KILIT_IPUCU`), koşum sonraki satırla devam eder. Enqueue kilidi SİLİNMEZ (Yasak C).

Yazma adımı hatası (`_yazma_hata_sinifi`; tablo IMPLEMENTATION.md §19.10). Kod üç yerden okunur: üst `error.code`,
composite `steps.*.error`, `push_object`'un yuttuğu istisna adı `result.error_type`:
  · sonuç BİLİNMİYOR → koşum DURUR: `unexpected` (araç istisnası `calistir` içinde buna çevrilir) · `connection_failed`
    · `unreachable` · `sap_error` HTTP 502/503/504 · lib `SAPADTError` ağacı dışı ya da `SAPConnectionError` istisna adı
  · hesap kilidi riski → koşum DURUR: `auth_failed` · `SAPAuthenticationError` · `sap_error` HTTP 401
  · diğerleri (4xx, reviewer/preflight blocker, kapı reddi, kilit, aktivasyon hatası) → satır HATA, koşum sürer
  · çağrı hattının KENDİSİ istisna (`step_exception`) → koşum DURUR
Durma yeri/kodu/gerekçesi `result.stop` = {name, row, step, tool, code, class}.

`--force-recreate` (yalnız domain/dtel/cds) `--only <TEK AD>` ister. DELETE yanıtı okunur:
  · `delete_verified=true`  → yaratma; sonraki adım hatalarının mesajı `SILME_ONEKI` ile başlar (obje SİLİNDİ)
  · `delete_verified=null`  → silme sonucu BİLİNMİYOR → koşum DURUR, kalanlar `islenmedi`
  · `ok:false`              → bağımsız varlık sondası: var → HATA (yaratma yok) · yok → HATA (tutarsız,
                              yaratma yok) · ölçülemedi → koşum DURUR
  · adım istisnası (yazma)  → koşum DURUR

CSV: UTF-8 (BOM'lu/BOM'suz, CRLF serbest). UTF-8 dışı ya da `csv.Error` → `csv_unreadable`; eksik/tanınmayan/yinelenen
başlık → `csv_invalid` (ikisi de çıkış 3, çağrı yok).

Çıkış: 0 hata yok · 1 en az bir HATA ya da `islenmedi` (kısmi başarı dahil) · 2 ön geçiş kapı reddi ·
3 kullanım/girdi hatası · 4 hata yok ama ATLANAN var ve `--fail-on-skip`.
"""
from __future__ import annotations

import csv
import re
import shutil
import tempfile
from pathlib import Path
from typing import Callable, Optional

TURLER = ("domain", "dtel", "cds", "enqu", "msag")
EXIT_OK, EXIT_HATA, EXIT_KAPI, EXIT_KULLANIM, EXIT_ATLANDI = 0, 1, 2, 3, 4
YAZILDI, ATLANDI, HATA, ISLENMEDI, DRY_RUN = "yazildi", "atlandi", "hata", "islenmedi", "dry_run"

FORCE_TIPI = {"domain": "doma", "dtel": "dtel", "cds": "ddls"}   # --force-recreate destekli türler
SONDA_TIPI = {**FORCE_TIPI, "enqu": "enqu"}                     # yazmadan önce adt_get varlık sondası
LABEL_MAX = (("short", 10), ("medium", 20), ("long", 40), ("heading", 55))  # check_dtel_creation_labels._MAX
T100_MAX = 73                                                       # tools/msgclass.py ile aynı sınır
_KILIT_MODLARI = ("E", "S", "X")

# ── yazma hatası sınıfı (gate-d3 bulgu 1 + lider kararları 2026-09-15; IMPLEMENTATION.md §19.10) ─────────────
SONUC_BILINMIYOR, HESAP_KILIDI_RISKI = "sonuc_bilinmiyor", "hesap_kilidi_riski"
BILINMIYOR_MESAJ = "sonuç BİLİNMİYOR, SAP'de durumu kontrol et"
KIMLIK_MESAJ = "kimlik reddedildi, koşum durduruldu, hesap kilidi riskine karşı kalan satırlar denenmedi"
SILME_ONEKI = "obje SİLİNDİ (delete_verified); yeniden yaratma başarısız: "
INAKTIF_NOTU = "obje SAP'de İNAKTİF olarak var olabilir (adt_get / inaktif obje listesiyle kontrol et)"
READBACK_MESAJ = "PUT kabul edildi, geri okuma doğrulanamadı; SAP'de kontrol et"
_BILINMEYEN_KODLAR = frozenset({"unexpected", "connection_failed", "unreachable"})  # atom._err_from_exc · adt_activate
_BILINMEYEN_HTTP = frozenset({"502", "503", "504"})   # sap_error içinde: ağ geçidi / zaman aşımı — işlenmiş olabilir
_KIMLIK_KODLARI = frozenset({"auth_failed", "SAPAuthenticationError"})
_KIMLIK_HTTP = frozenset({"401"})
# lib `SAPADTError` ağacı − `SAPConnectionError` (test U5 lib ağacıyla eşitliği zorlar). `push_object` istisnayı
# `result.error_type` adına yutar (sap_client.push_object dış except): bu kümede OLMAYAN ad → sonuç bilinmiyor.
_BILINEN_SAP_ISTISNALARI = frozenset({
    "SAPADTError", "SAPAuthenticationError", "SAPObjectNotFoundError", "SAPObjectExistsError", "SAPLockError",
    "SAPActivationError", "SAPValidationError", "DomainTipBilgisiHatasi", "DomainBulunamadi",
    "DomainTipBilgisiOlculemedi", "SAPTransportError"})
# SIKI desen, yalnız mesajın EN BAŞI: `SAPADTError.__str__` = f"[{status_code}] {message}" (sap_adt_lib.py). Gövdenin
# içinden gelen "[502]" eşleşmez (test 12b). Yapısal alan yok: `_err_from_exc` status_code taşımıyor (§19.10 açık kalem).
_HTTP_ONEKI = re.compile(r"^\[(\d{3})\] ")

Cagir = Callable[[str, dict], "tuple[dict, int]"]
Kontrol = Callable[[str, dict], "tuple[str, Optional[tuple]]"]


class KullanimHatasi(Exception):
    def __init__(self, code: str, message: str, bulgular: list | None = None):
        super().__init__(message)
        self.code, self.message, self.bulgular = code, message, list(bulgular or [])


class _SatirHatasi(Exception):
    """Bu hedef HATA; koşum sıradakiyle devam eder."""


class _KosumDurdu(Exception):
    """Koşum durur, kalanlar işlenmez. `kod`/`sinif`/`adim`/`tool` → `result.stop` (nerede, hangi kod, hangi gerekçe)."""

    def __init__(self, mesaj: str, *, kod: str, sinif: str = SONUC_BILINMIYOR, adim=None, tool=None):
        super().__init__(mesaj)
        self.kod, self.sinif, self.adim, self.tool = kod, sinif, adim, tool


# ═════════════════════════════ girdi okuma (fail-closed) ═════════════════════════════════════════

def _csv_oku(yol, zorunlu: tuple, secimli: tuple = ()) -> tuple[list, list]:
    """→ ([(satir_no, alanlar)], bulgular). Başlık eksik/tanınmayan kolon → KullanimHatasi."""
    p = Path(yol)
    try:
        f = open(p, encoding="utf-8-sig", newline="")
    except OSError as exc:
        raise KullanimHatasi("csv_unreadable", f"CSV okunamadı: {p} ({exc})")
    bulgular, satirlar = [], []
    okuyucu = None
    try:
        with f:
            okuyucu = csv.DictReader(f)
            basliklar = [(h or "").strip() for h in (okuyucu.fieldnames or [])]
            tekrar = sorted({h for h in basliklar if h and basliklar.count(h) > 1})
            if tekrar:   # DictReader aynı anahtarda SON sütunu tutar → sessizce başka değer araca gider
                raise KullanimHatasi("csv_invalid", "CSV başlığında tekrar eden kolon(lar): " + ", ".join(tekrar),
                                     ["hangi sütunun araca gideceği belirsiz olur; yinelenen kolonu çıkar "
                                      "(karşılaştırma baştaki/sondaki boşluk ve BOM yok sayılarak yapılır)"])
            yok = [c for c in zorunlu if c not in basliklar]
            if yok:
                raise KullanimHatasi("csv_invalid", "CSV zorunlu kolon(lar) eksik: " + ", ".join(yok),
                                     [f"bulunan başlık: {', '.join(basliklar) or '(boş)'} · beklenen: "
                                      f"{', '.join(zorunlu)}" + (f" (seçimli: {', '.join(secimli)})" if secimli else "")])
            tanimsiz = [h for h in basliklar if h not in zorunlu and h not in secimli]
            if tanimsiz:
                raise KullanimHatasi("csv_invalid", "CSV'de tanınmayan kolon(lar): " + ", ".join(tanimsiz),
                                     ["yazım hatası sessizce yok sayılmaz; kolonu düzelt ya da çıkar"])
            for satir in okuyucu:
                no = okuyucu.line_num
                if None in satir:
                    bulgular.append(f"satır {no}: başlıktan fazla alan var")
                    continue
                alanlar = {(k or "").strip(): str(v or "").strip() for k, v in satir.items()}
                if not any(alanlar.values()):
                    continue   # tamamen boş satır = dolgu
                satirlar.append((no, alanlar))
    except UnicodeDecodeError as exc:
        raise KullanimHatasi("csv_unreadable", f"CSV UTF-8 olarak okunamadı: {p} (bayt {exc.start}: {exc.reason}) — "
                                               "dosyayı UTF-8 kaydet (Excel: 'CSV UTF-8'); BOM ve CRLF sorun değil. "
                                               "Kodlama tahmini yapılmaz.") from None
    except csv.Error as exc:
        satir_no = getattr(okuyucu, "line_num", "?")
        raise KullanimHatasi("csv_unreadable", f"CSV ayrıştırılamadı: {p} (satır {satir_no}: {exc})") from None
    return satirlar, bulgular


def _bos_alanlar(no, alanlar, kolonlar, bulgular) -> bool:
    bos = [c for c in kolonlar if not alanlar.get(c)]
    for c in bos:
        bulgular.append(f"satır {no} ({alanlar.get('name') or '?'}): `{c}` BOŞ")
    return bool(bos)


def _tekrar(no, ad, gorulen: set, bulgular) -> bool:
    if ad in gorulen:
        bulgular.append(f"satır {no} ({ad}): ad CSV'de birden çok kez geçiyor")
        return True
    gorulen.add(ad)
    return False


def _bitir_okuma(hedefler: list, bulgular: list, kaynak) -> list:
    if bulgular:
        raise KullanimHatasi("csv_invalid", f"{len(bulgular)} girdi bulgusu — HİÇBİR çağrı yapılmadı (fail-closed).",
                             bulgular)
    if not hedefler:
        raise KullanimHatasi("csv_empty", f"İşlenecek satır yok: {kaynak}")
    return hedefler


def _sabit_degerler(metin: str) -> tuple[Optional[list], list]:
    """`A=Açık;K=Kapalı` → [{"value":"A","text":"Açık"}, …]. Boş → None. Her parça `değer=metin` olmalı."""
    if not metin:
        return None, []
    out, hatalar = [], []
    for i, parca in enumerate(metin.split(";"), 1):
        parca = parca.strip()
        if not parca:
            continue
        if "=" not in parca:
            hatalar.append(f"fixed_values parça {i} `değer=metin` değil: {parca!r}")
            continue
        deger, yazi = (x.strip() for x in parca.split("=", 1))
        if not deger or not yazi:
            hatalar.append(f"fixed_values parça {i} değer ya da metin BOŞ: {parca!r}")
            continue
        out.append({"value": deger, "text": yazi})
    return (out or None), hatalar


def domain_hedefleri(csv_yolu) -> list:
    zor = ("name", "datatype", "length", "decimals", "description")
    satirlar, b = _csv_oku(csv_yolu, zor, ("fixed_values",))
    out, gorulen = [], set()
    for no, a in satirlar:
        if _bos_alanlar(no, a, zor, b):
            continue
        ad = a["name"].upper()
        hatali = _tekrar(no, ad, gorulen, b)
        try:
            uzunluk, ondalik = int(a["length"]), int(a["decimals"])
        except ValueError:
            b.append(f"satır {no} ({ad}): length/decimals sayı değil ({a['length']!r}/{a['decimals']!r})")
            hatali = True
        sabit, fv_hata = _sabit_degerler(a.get("fixed_values", ""))
        b.extend(f"satır {no} ({ad}): {h}" for h in fv_hata)
        if hatali or fv_hata:
            continue
        out.append({"satir": no, "ad": ad, "datatype": a["datatype"].upper(), "length": uzunluk,
                    "decimals": ondalik, "description": a["description"], "fixed_values": sabit, "_ham": a})
    return _bitir_okuma(out, b, csv_yolu)


def dtel_hedefleri(csv_yolu) -> list:
    zor = ("name", "type_kind", "type_name", "description", "short", "medium", "long", "heading")
    yok_sayilan = ("datatype", "length", "decimals")
    satirlar, b = _csv_oku(csv_yolu, zor, yok_sayilan)
    out, gorulen = [], set()
    for no, a in satirlar:
        if _bos_alanlar(no, a, zor, b):   # ADR 0005-D: 4 etiket + açıklama dolu; üretilmez/tamamlanmaz
            continue
        ad = a["name"].upper()
        hatali = _tekrar(no, ad, gorulen, b)
        if a["type_kind"].lower() != "domain":
            b.append(f"satır {no} ({ad}): type_kind yalnız 'domain' kabul edilir (görülen {a['type_kind']!r}); "
                     "type_name mevcut bir domain adı olmalı")
            hatali = True
        for alan, sinir in LABEL_MAX:
            if len(a[alan]) > sinir:
                b.append(f"satır {no} ({ad}): `{alan}` {len(a[alan])} karakter > {sinir} (kırpılmaz)")
                hatali = True
        if hatali:
            continue
        out.append({"satir": no, "ad": ad, "domain_name": a["type_name"].upper(), "description": a["description"],
                    "short": a["short"], "medium": a["medium"], "long": a["long"], "heading": a["heading"],
                    "yok_sayilan": [c for c in yok_sayilan if a.get(c)], "_ham": a})
    return _bitir_okuma(out, b, csv_yolu)


def enqu_hedefleri(csv_yolu) -> list:
    zor = ("name", "description", "primary_table", "lock_mode", "allow_rfc", "field_names")
    satirlar, b = _csv_oku(csv_yolu, zor)
    out, gorulen = [], set()
    for no, a in satirlar:
        if _bos_alanlar(no, a, zor, b):
            continue
        ad = a["name"].upper()
        hatali = _tekrar(no, ad, gorulen, b)
        mod = a["lock_mode"].upper()
        if mod not in _KILIT_MODLARI:
            b.append(f"satır {no} ({ad}): lock_mode {a['lock_mode']!r} — geçerli: E, S, X")
            hatali = True
        rfc = a["allow_rfc"].lower()
        if rfc not in ("true", "false"):
            b.append(f"satır {no} ({ad}): allow_rfc {a['allow_rfc']!r} — true/false olmalı")
            hatali = True
        parcalar = [x.strip() for x in a["field_names"].split(";")]
        if any(not x for x in parcalar):
            b.append(f"satır {no} ({ad}): field_names boş parça içeriyor ({a['field_names']!r}; ayırıcı ';')")
            hatali = True
        if hatali:
            continue
        out.append({"satir": no, "ad": ad, "description": a["description"],
                    "extra": {"primary_table": a["primary_table"].upper(), "lock_fields": [x.upper() for x in parcalar],
                              "lock_mode": mod, "allow_rfc": rfc == "true"}})
    return _bitir_okuma(out, b, csv_yolu)


_CDS_TANIM = re.compile(r"\bdefine\s+(?:root\s+)?view\s+(?:entity\s+)?([A-Za-z0-9_/]+)", re.IGNORECASE)
_CDS_ETIKET = re.compile(r"@EndUserText\.label\s*:\s*'([^']*)'")


def cds_hedefleri(kaynak_dizini) -> list:
    d = Path(kaynak_dizini)
    if not d.is_dir():
        raise KullanimHatasi("source_dir_invalid", f"Kaynak dizini yok: {d}")
    b, out, gorulen = [], [], set()
    for dosya in sorted(d.glob("*.cds")):
        try:
            metin = dosya.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:
            b.append(f"{dosya.name}: okunamadı ({type(exc).__name__})")
            continue
        m = _CDS_TANIM.search(metin)
        if not m:
            b.append(f"{dosya.name}: `define [root] view [entity] <ad>` tanımı bulunamadı (başka CDS türü desteklenmez)")
            continue
        ad = m.group(1).upper()
        if ad != dosya.stem.upper():
            b.append(f"{dosya.name}: dosya adı ({dosya.stem.upper()}) ile tanım adı ({ad}) farklı")
            continue
        et = _CDS_ETIKET.search(metin[:m.start()])
        if not et or not et.group(1).strip():
            b.append(f"{dosya.name}: tanımdan önce dolu `@EndUserText.label` yok — açıklama üretilmez (ADR 0005-D)")
            continue
        if _tekrar(dosya.name, ad, gorulen, b):
            continue
        out.append({"satir": dosya.name, "ad": ad, "description": et.group(1).strip(), "source": metin})
    return _bitir_okuma(out, b, d)


def msag_mesajlari(csv_yolu) -> list:
    satirlar, b = _csv_oku(csv_yolu, ("msgno", "msgtext"), ("selfexplainatory",))
    out, gorulen = [], set()
    for no, a in satirlar:
        numara, metin = a["msgno"], a["msgtext"]
        hatali = False
        if not re.fullmatch(r"\d{3}", numara):
            b.append(f"satır {no}: msgno {numara!r} tam 3 hane olmalı (sıfır doldurma tahmini yapılmaz)")
            hatali = True
        elif _tekrar(no, numara, gorulen, b):
            hatali = True
        if not metin:
            b.append(f"satır {no} ({numara}): msgtext BOŞ")
            hatali = True
        elif len(metin) > T100_MAX:
            b.append(f"satır {no} ({numara}): msgtext {len(metin)} karakter > {T100_MAX} (kırpılmaz)")
            hatali = True
        se = a.get("selfexplainatory", "").lower()
        if se not in ("", "true", "false"):
            b.append(f"satır {no} ({numara}): selfexplainatory {a['selfexplainatory']!r} — true/false ya da boş")
            hatali = True
        if hatali:
            continue
        m = {"no": numara, "text": metin}
        if se:
            m["selfexplanatory"] = se == "true"
        out.append(m)
    return _bitir_okuma(out, b, csv_yolu)


# ═════════════════════════════ planlama (ön geçiş ile yürütme AYNI argümanları kullanır) ══════════

def _artefakt_yaz(tmp: Path, ad: str, sonek: str, kolonlar: tuple, satir: dict) -> str:
    """Tek satırlık reviewer girdisi — YALNIZ izole geçici dizine (koşum sonunda silinir)."""
    yol = tmp / f"{re.sub(r'[^A-Za-z0-9_]', '_', ad)}_{sonek}.csv"
    with open(yol, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(kolonlar))
        w.writeheader()
        w.writerow({k: satir.get(k, "") for k in kolonlar})
    return str(yol)


class _Plan:
    def __init__(self, tur: str, h: dict, package, transport, tmp: Path, allow_overwrite: bool):
        self.tur, self.h, self.ad = tur, h, h["ad"]
        c: dict[str, tuple[str, dict]] = {}
        if tur in SONDA_TIPI:
            c["sonda"] = ("adt_get", {"name": self.ad, "object_type": SONDA_TIPI[tur], "include_source": False})
        if tur in FORCE_TIPI:
            c["sil"] = ("adt_delete", {"name": self.ad, "object_type": FORCE_TIPI[tur], "transport": transport})
        if tur == "domain":
            art = _artefakt_yaz(tmp, self.ad, "domains", ("name", "datatype", "length", "decimals", "description",
                                                          "fixed_values"), h["_ham"])
            c["yarat"] = ("adt_domain_create", {"name": self.ad, "datatype": h["datatype"], "length": h["length"],
                                                "description": h["description"], "package": package,
                                                "transport": transport, "decimals": h["decimals"],
                                                "fixed_values": h["fixed_values"], "artifact_path": art})
        elif tur == "dtel":
            art = _artefakt_yaz(tmp, self.ad, "dataelements", ("name", "type_kind", "type_name", "description",
                                                               "short", "medium", "long", "heading"), h["_ham"])
            c["yarat"] = ("adt_dtel_create", {"name": self.ad, "domain_name": h["domain_name"],
                                              "description": h["description"], "package": package,
                                              "transport": transport, "short_label": h["short"],
                                              "medium_label": h["medium"], "long_label": h["long"],
                                              "heading_label": h["heading"], "artifact_path": art})
        elif tur == "cds":
            c["kabuk"] = ("adt_post_shell", {"object_type": "ddls", "name": self.ad, "package": package,
                                             "transport": transport, "description": h["description"]})
            c["pull"] = ("adt_get", {"name": self.ad, "object_type": "ddls", "include_source": True})
            c["push"] = ("adt_push_source", {"name": self.ad, "object_type": "ddls", "source": h["source"],
                                             "transport": transport})
            c["aktive"] = ("adt_activate", {"name": self.ad, "object_type": "ddls"})
        elif tur == "enqu":
            c["kabuk"] = ("adt_post_shell", {"object_type": "enqu", "name": self.ad, "package": package,
                                             "transport": transport, "description": h["description"],
                                             "extra": h["extra"]})
            c["aktive"] = ("adt_activate", {"name": self.ad, "object_type": "enqu"})
        elif tur == "msag":
            c["oku"] = ("adt_msgclass_read", {"name": self.ad})
            c["kabuk"] = ("adt_post_shell", {"object_type": "msag", "name": self.ad, "package": package,
                                             "transport": transport, "description": h["description"]})
            c["yaz"] = ("adt_msgclass_write", {"name": self.ad, "transport": transport, "messages": h["messages"],
                                               "allow_overwrite": allow_overwrite, "package": package})
        self.cagrilar = c

    def on_gecis_cagrilari(self, force: bool) -> list:
        return [(adim, t, a) for adim, (t, a) in self.cagrilar.items() if adim != "sil" or force]


# ═════════════════════════════ yürütme ══════════════════════════════════════════════════════════

_OZET_ALANLARI = ("ok", "error", "code", "message", "exists", "exists_after", "exists_probe", "delete_verified",
                  "delete_reason", "changed", "plan", "activated", "activation_verified", "readback_verified",
                  "pull_state", "notice", "warning", "master_language_warning", "reviewer", "post_check")


def _adim_ozeti(adim: str, tool: str, payload: dict, kod: int) -> dict:
    r = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    oz = {k: (str(r[k])[:600] if k == "message" else r[k]) for k in _OZET_ALANLARI if k in r}
    if isinstance(r.get("steps"), dict):
        oz["steps"] = {ad: ({k: v for k, v in s.items() if k != "log"} if isinstance(s, dict) else s)
                       for ad, s in r["steps"].items()}
    return {"step": adim, "tool": tool, "exit": kod, "ok": payload.get("ok"), "error": payload.get("error"),
            "review": (payload.get("gate") or {}).get("review"), "result": oz}


_KILIT_KODLARI = frozenset({"locked", "lock_conflict", "lock_failed"})
KILIT_IPUCU = ("KİLİT: bu araç enqueue kilidini SİLMEZ/TEMİZLEMEZ (Kesin Yasak C). SM12'de objenin kilit sahibini "
               "gör; kendi açık oturumun/editörün ise kapat, başkasıysa bitmesini bekle; sonra yalnız bu objeyi "
               "yeniden koş (--only <AD>). Koşum diğer satırlarla devam etti.")


def _kilit_hatasi_mi(payload: dict) -> bool:
    """Adım hatası bir kilit çakışması/kilit alınamaması mı? (yalnız mesaja SM12 tarifi eklemek için)."""
    e = payload.get("error") or {}
    r = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    ic = r.get("result") if isinstance(r.get("result"), dict) else {}
    if e.get("code") in _KILIT_KODLARI or r.get("error") in _KILIT_KODLARI:
        return True
    if ic.get("error_type") == "SAPLockError":
        return True
    metin = " ".join(str(x or "") for x in (e.get("message"), r.get("message"), ic.get("error"))).lower()
    return any(p in metin for p in ("enqueue", "lock handle", "lockhandle", "is locked", "kilitli", "kilidi alınamadı"))


def _hata_metni(payload: dict) -> str:
    e = payload.get("error") or {}
    r = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    ic = r.get("result") if isinstance(r.get("result"), dict) else {}
    ayrinti = e.get("message") or r.get("message") or (str(ic.get("error") or "") or None)
    if not ayrinti and isinstance(r.get("post_check"), dict):   # yazma sonrası reviewer kontrolü düşürdü
        pc = r["post_check"]
        ayrinti = (f"yazma sonrası kontrol (post_check) {pc.get('verdict')}"
                   f"{' · ölçülemeyen: ' + str(pc.get('unmeasured')) if pc.get('unmeasured') else ''}")
    for s in ((r.get("steps") or {}).values() if isinstance(r.get("steps"), dict) else ()):
        if isinstance(s, dict) and s.get("ok") is False and s.get("message"):
            ayrinti = f"{ayrinti} · {s.get('error') or ''}: {s['message']}" if ayrinti else s["message"]
    metin = f"{e.get('code') or 'tool_failed'}: {str(ayrinti or '')[:400]}"
    return f"{metin} · {KILIT_IPUCU}" if _kilit_hatasi_mi(payload) else metin


def _hata_adaylari(payload: dict) -> list:
    """Bir adım yanıtındaki TÜM hata kodu adayları → [(etiket_öneki, kod, mesaj, istisna_adı_mı)].

    Üç yer (koddan): üst `error.code` (`calistir._sonuc_hatasi`) ve `result.error` · composite `steps.<ad>.error`
    (metin ya da `_activate_and_verify`'deki gibi iç içe sözlük) · `push_object`'un yuttuğu `result.result.error_type`."""
    e = payload.get("error") or {}
    r = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    out = [("", e.get("code"), e.get("message"), False), ("", r.get("error"), r.get("message"), False)]
    for ad, s in ((r.get("steps") or {}).items() if isinstance(r.get("steps"), dict) else ()):
        if isinstance(s, dict):
            ic = s.get("error")
            if isinstance(ic, dict):
                out.append((f"steps.{ad}:", ic.get("error"), ic.get("message"), False))
            else:
                out.append((f"steps.{ad}:", ic, s.get("message"), False))
    ic = r.get("result") if isinstance(r.get("result"), dict) else {}
    if isinstance(ic.get("error_type"), str) and ic["error_type"]:
        out.append((f"{r.get('error') or 'result'}:", ic["error_type"], ic.get("error"), True))
    return [(o, k, m, i) for o, k, m, i in out if isinstance(k, str) and k]


def _yazma_hata_sinifi(payload: dict) -> Optional[tuple]:
    """Yazma adımı hatası koşumu durdurur mu? → None (bilinen red: satır HATA, koşum sürer) ya da (sınıf, kod etiketi).

    Kimlik reddi önce gelir (sonraki satırlar aynı kimlikle art arda red alır → SAP hesap kilidi riski)."""
    bilinmez = None
    for onek, kod, mesaj, istisna in _hata_adaylari(payload):
        m = _HTTP_ONEKI.match(str(mesaj or ""))
        durum = m.group(1) if m and kod in ("sap_error", "SAPADTError") else None
        etiket = f"{onek}{kod}" + (f" HTTP {durum}" if durum else "")
        if kod in _KIMLIK_KODLARI or durum in _KIMLIK_HTTP:
            return HESAP_KILIDI_RISKI, etiket
        if kod in _BILINMEYEN_KODLAR or durum in _BILINMEYEN_HTTP or (istisna and kod not in _BILINEN_SAP_ISTISNALARI):
            bilinmez = bilinmez or etiket
    return (SONUC_BILINMIYOR, bilinmez) if bilinmez else None


def _aktivasyon_hatasi_mi(payload: dict) -> bool:
    return any(kod == "activation_failed" for _o, kod, _m, _i in _hata_adaylari(payload))


def force_recreate_onerisi(ad: str) -> str:
    """Öneri DAİMA tek objeye daraltılır (global bayrak toplu DELETE olmasın)."""
    return (f"--force-recreate --only {ad} (DELETE + yeniden yaratma; tüketicisi/bağımlısı olan objede "
            f"KULLANMA — içerik güncellemesi için adt_push_source)")


class _Yurutucu:
    def __init__(self, cagir: Cagir, force: bool):
        self.cagir, self.force = cagir, force
        self.silme_oneki = ""   # yurut: silme doğrulandıktan sonra SILME_ONEKI

    def _adim(self, kayit: dict, plan: _Plan, adim: str, *, yazma: bool) -> tuple[dict, int]:
        tool, args = plan.cagrilar[adim]
        try:
            payload, kod = self.cagir(tool, args)
        except Exception as exc:  # noqa: BLE001 — çağrı hattının kendisi patladı
            kayit["steps"].append({"step": adim, "tool": tool, "exit": None, "ok": False,
                                   "error": {"code": "step_exception", "message": f"{type(exc).__name__}: {exc}"}})
            if yazma:
                raise _KosumDurdu(f"{plan.ad}: {self.silme_oneki}yazma adımı {tool} istisna verdi ({type(exc).__name__}) "
                                  f"— {BILINMIYOR_MESAJ}; koşum durduruldu.", kod="step_exception", adim=adim, tool=tool)
            raise _SatirHatasi(f"{tool} istisna verdi ({type(exc).__name__}) — yazma yapılmadı")
        kayit["steps"].append(_adim_ozeti(adim, tool, payload, kod))
        return payload, kod

    def _var_mi(self, kayit, plan, adim="sonda") -> Optional[bool]:
        payload, kod = self._adim(kayit, plan, adim, yazma=False)
        r = payload.get("result") if isinstance(payload.get("result"), dict) else {}
        if kod == EXIT_OK and r.get("ok") is True and r.get("exists") in (True, False):
            return r["exists"]
        return None

    def _sil(self, kayit, plan) -> None:
        payload, kod = self._adim(kayit, plan, "sil", yazma=True)
        r = payload.get("result") if isinstance(payload.get("result"), dict) else {}
        if kod == EXIT_OK and r.get("delete_verified") is True:
            return
        if kod == EXIT_OK:
            raise _KosumDurdu(f"{plan.ad}: DELETE ok döndü ama silme DOĞRULANAMADI (delete_verified="
                              f"{r.get('delete_verified')!r}) — {BILINMIYOR_MESAJ}; koşum durduruldu, yaratma denenmedi.",
                              kod=f"delete_verified={r.get('delete_verified')!r}", adim="sil", tool="adt_delete")
        if payload.get("result") is None:   # kapı/profil reddi: araç hiç koşmadı
            raise _SatirHatasi(f"DELETE kapıda reddedildi ({_hata_metni(payload)}) — yaratma denenmedi")
        try:
            var = self._var_mi(kayit, plan, "sonda")
        except _SatirHatasi:
            var = None
        if var is True:
            raise _SatirHatasi(f"DELETE başarısız ({_hata_metni(payload)}); obje hâlâ VAR — yaratma denenmedi")
        if var is False:
            raise _SatirHatasi(f"DELETE başarısız raporlandı ({_hata_metni(payload)}) ama obje artık YOK — tutarsız "
                               "sonuç; yaratma denenmedi, elle doğrula")
        raise _KosumDurdu(f"{plan.ad}: DELETE başarısız ve sonrasında varlık ÖLÇÜLEMEDİ — silme {BILINMIYOR_MESAJ}; "
                          "koşum durduruldu.", kod="delete_failed+probe_unmeasured", adim="sil", tool="adt_delete")

    def _yaz_ya_da_hata(self, kayit, plan, adim, onek=""):
        payload, kod = self._adim(kayit, plan, adim, yazma=True)
        if kod == EXIT_OK:
            return payload
        tool = plan.cagrilar[adim][0]
        onek = self.silme_oneki + onek
        sinif = _yazma_hata_sinifi(payload)
        if sinif:
            neden = KIMLIK_MESAJ if sinif[0] == HESAP_KILIDI_RISKI else BILINMIYOR_MESAJ
            raise _KosumDurdu(f"{plan.ad}: {onek}{tool} → {neden} ({sinif[1]}) — {_hata_metni(payload)}",
                              kod=sinif[1], sinif=sinif[0], adim=adim, tool=tool)
        if (payload.get("error") or {}).get("code") == "readback_failed":
            raise _SatirHatasi(f"{onek}{tool}: {READBACK_MESAJ} — {_hata_metni(payload)}")
        metin = _hata_metni(payload)
        if _aktivasyon_hatasi_mi(payload):
            metin = f"{metin} · {INAKTIF_NOTU}"
        raise _SatirHatasi(f"{onek}{tool} başarısız — {metin}")

    def yurut(self, plan: _Plan, kayit: dict) -> None:
        tur = plan.tur
        self.silme_oneki = ""
        if tur in SONDA_TIPI:
            var = self._var_mi(kayit, plan)
            if var is None:
                raise _SatirHatasi("varlık ÖLÇÜLEMEDİ (adt_get) — 'yok' sayılmadı, yazma yapılmadı")
            if var and tur == "enqu":
                kayit.update(status=ATLANDI, message="kilit objesi zaten var — YAZILMADI (bu araç kilit objesini "
                                                     "güncellemez/silmez)")
                return
            if var and not self.force:
                kayit.update(status=ATLANDI, message="zaten var — YAZILMADI (içerik karşılaştırılmadı)",
                             suggestion=force_recreate_onerisi(plan.ad))
                return
            if var:
                self._sil(kayit, plan)
                self.silme_oneki = SILME_ONEKI   # geri alınamaz silme oturdu — sonraki her hata mesajında görünür
            if tur in ("domain", "dtel"):
                self._yaz_ya_da_hata(kayit, plan, "yarat")
            elif tur == "enqu":
                self._yaz_ya_da_hata(kayit, plan, "kabuk")
                self._yaz_ya_da_hata(kayit, plan, "aktive", "kabuk yaratıldı, aktivasyon: ")
            else:
                self._yaz_ya_da_hata(kayit, plan, "kabuk")
                p, kod = self._adim(kayit, plan, "pull", yazma=False)
                ps = str(((p.get("result") or {}) if isinstance(p.get("result"), dict) else {}).get("pull_state") or "")
                if kod != EXIT_OK or not ps.startswith("kaydedildi"):
                    raise _SatirHatasi(f"{self.silme_oneki}kabuk yaratıldı ama kaynak ÇEKİLEMEDİ (exit {kod}, "
                                       f"pull_state={ps!r}) — kaynak yazılmadı")
                self._yaz_ya_da_hata(kayit, plan, "push", "kabuk var, kaynak yazılamadı: ")
                self._yaz_ya_da_hata(kayit, plan, "aktive", "kaynak yazıldı, aktivasyon: ")
            kayit.update(status=YAZILDI)
            return
        if tur == "msag":
            var = self._var_mi(kayit, plan, "oku")
            if var is None:
                raise _SatirHatasi("mesaj sınıfı varlığı ÖLÇÜLEMEDİ (adt_msgclass_read) — yazma yapılmadı")
            if var is False:
                self._yaz_ya_da_hata(kayit, plan, "kabuk")
                if self._var_mi(kayit, plan, "oku") is not True:
                    raise _SatirHatasi("kabuk POST'u sonrası mesaj sınıfı okunamadı — mesajlar yazılmadı")
            payload = self._yaz_ya_da_hata(kayit, plan, "yaz")
            r = payload.get("result") or {}
            if r.get("changed") is False:
                kayit.update(status=ATLANDI, message="mesaj listesi zaten aynı — YAZILMADI")
            else:
                kayit.update(status=YAZILDI)
            return
        raise _SatirHatasi(f"bilinmeyen tür {tur}")   # pragma: no cover — kullanım doğrulaması bunu önler


# ═════════════════════════════ ana giriş ════════════════════════════════════════════════════════

def _hedefler(tur, csv_yolu, kaynak_dizini, msag_adi, msag_aciklama) -> list:
    if tur == "cds":
        if not kaynak_dizini or csv_yolu:
            raise KullanimHatasi("usage_error", "cds türü yalnız --source-dir alır (--csv değil).")
        return cds_hedefleri(kaynak_dizini)
    if not csv_yolu or kaynak_dizini:
        raise KullanimHatasi("usage_error", f"{tur} türü yalnız --csv alır (--source-dir değil).")
    if tur == "msag":
        if not (msag_adi and msag_adi.strip()) or not (msag_aciklama and msag_aciklama.strip()):
            raise KullanimHatasi("usage_error", "msag türü --name ve --description ister (açıklama üretilmez).")
        return [{"satir": "-", "ad": msag_adi.strip().upper(), "description": msag_aciklama.strip(),
                 "messages": msag_mesajlari(csv_yolu)}]
    return {"domain": domain_hedefleri, "dtel": dtel_hedefleri, "enqu": enqu_hedefleri}[tur](csv_yolu)


def kos(tur: str, *, cagir: Cagir, kontrol: Kontrol, logla: Callable | None = None, csv_yolu=None,
        kaynak_dizini=None, package=None, transport=None, only=None, force_recreate=False, dry_run=False,
        fail_on_skip=False, allow_overwrite=False, msag_adi=None, msag_aciklama=None) -> tuple[dict, int]:
    """Toplu koşum. Dönüş `(payload, çıkış_kodu)`; yazdırmaz. `cagir`/`kontrol` gerçek koşumda
    `sap_adt_cli.calistir`/`on_kontrol` sarmalayıcılarıdır (bkz. `main`)."""
    sonuc: dict = {"type": tur, "rows": [], "summary": {}, "notices": []}
    kapi: dict = {"prepass": {"checked": 0, "rejections": []}}

    def cikis(kod, err=None, ok=False):
        return {"ok": ok, "tool": "populate", "class": "write", "result": sonuc,
                "error": ({"code": err[0], "message": err[1]} if err else None), "gate": kapi}, kod

    tmp = None
    try:
        if tur not in TURLER:
            raise KullanimHatasi("usage_error", f"Bilinmeyen tür {tur!r}; geçerli: {', '.join(TURLER)} "
                                                "(tablo türü yok — template Z tablo kabuğu yaratmaz).")
        if not (package and str(package).strip()):
            raise KullanimHatasi("usage_error", "--package zorunlu (paket yaratılmaz; mevcut paket adı).")
        adlar = [x.strip().upper() for x in (only or "").split(",") if x.strip()] if only else []
        if force_recreate:
            if tur not in FORCE_TIPI:
                raise KullanimHatasi("usage_error", f"--force-recreate {tur} türünde yok (yalnız "
                                                    f"{', '.join(FORCE_TIPI)}; silme yolu olmayan tür).")
            if len(adlar) != 1:
                raise KullanimHatasi("usage_error", "--force-recreate yalnız --only <TEK AD> ile verilir "
                                                    "(toplu DELETE yok).")
        if allow_overwrite and tur != "msag":
            raise KullanimHatasi("usage_error", "--allow-overwrite yalnız msag türünde geçerli.")
        if tur == "msag" and only:
            raise KullanimHatasi("usage_error", "--only msag türünde yok (tek mesaj sınıfı).")
        hedefler = _hedefler(tur, csv_yolu, kaynak_dizini, msag_adi, msag_aciklama)
        if adlar:
            bilinmeyen = [a for a in adlar if a not in {h["ad"] for h in hedefler}]
            if bilinmeyen:
                raise KullanimHatasi("usage_error", "--only girdide olmayan ad(lar): " + ", ".join(bilinmeyen))
            hedefler = [h for h in hedefler if h["ad"] in adlar]
    except KullanimHatasi as kh:
        if kh.bulgular:
            sonuc["findings"] = kh.bulgular
        return cikis(EXIT_KULLANIM, (kh.code, kh.message))

    try:
        tmp = Path(tempfile.mkdtemp(prefix="axet_populate_"))
        sonuc["temp_dir"] = str(tmp)
        planlar = [_Plan(tur, h, package, transport, tmp, allow_overwrite) for h in hedefler]
        for p in planlar:
            if p.h.get("yok_sayilan"):
                sonuc["notices"].append(f"{p.ad}: CSV kolonları {', '.join(p.h['yok_sayilan'])} araca GEÇMEZ — "
                                        "tip bilgisi domain'den okunur.")

        # ── ÖN GEÇİŞ: yazmadan önce HER planlı çağrı kapıdan ────────────────────────────────────
        for p in planlar:
            for adim, tool, args in p.on_gecis_cagrilari(force_recreate):
                sinif, err = kontrol(tool, args)
                kapi["prepass"]["checked"] += 1
                if err:
                    kapi["prepass"]["rejections"].append({"name": p.ad, "row": p.h["satir"], "step": adim,
                                                          "tool": tool, "code": err[0], "message": err[1]})
                    if logla and sinif == "write" and not dry_run:
                        logla(tool, args, err)
        if kapi["prepass"]["rejections"]:
            for p in planlar:
                sonuc["rows"].append({"name": p.ad, "row": p.h["satir"], "status": ISLENMEDI, "steps": [],
                                      "message": "ön geçiş kapı reddi — koşuma başlanmadı"})
            sonuc["summary"] = _ozet(sonuc["rows"])
            ilk = kapi["prepass"]["rejections"][0]
            return cikis(EXIT_KAPI, ("prepass_gate_rejected",
                                     f"{len(kapi['prepass']['rejections'])} planlı çağrı kapıda reddedildi (ilk: "
                                     f"{ilk['name']} {ilk['tool']} → {ilk['code']}) — HİÇBİR şey yazılmadı."))

        if dry_run:
            for p in planlar:
                sonuc["rows"].append({"name": p.ad, "row": p.h["satir"], "status": DRY_RUN, "steps": [],
                                      "planned_tools": [t for _a, t, _x in p.on_gecis_cagrilari(force_recreate)]})
            sonuc["summary"] = _ozet(sonuc["rows"])
            sonuc["notices"].append("DRY-RUN: girdi + kapı ön geçişi koştu; SAP'ye hiçbir çağrı yapılmadı "
                                    "(varlık sondası dahil).")
            return cikis(EXIT_OK, ok=True)

        yurutucu = _Yurutucu(cagir, force_recreate)
        durdu = None
        for i, p in enumerate(planlar):
            kayit = {"name": p.ad, "row": p.h["satir"], "status": None, "steps": []}
            sonuc["rows"].append(kayit)
            try:
                yurutucu.yurut(p, kayit)
            except _SatirHatasi as sh:
                kayit.update(status=HATA, message=str(sh))
            except _KosumDurdu as kd:
                kayit.update(status=HATA, message=str(kd))
                sonuc["stop"] = {"name": p.ad, "row": p.h["satir"], "step": kd.adim, "tool": kd.tool,
                                 "code": kd.kod, "class": kd.sinif}
                durdu = f"satır {p.h['satir']} · {kd.adim}/{kd.tool} · kod={kd.kod} · gerekçe={kd.sinif}: {kd}"
                for q in planlar[i + 1:]:
                    sonuc["rows"].append({"name": q.ad, "row": q.h["satir"], "status": ISLENMEDI, "steps": [],
                                          "message": "koşum durduruldu — işlenmedi"})
                break
        ozet = sonuc["summary"] = _ozet(sonuc["rows"])
        if durdu:
            sonuc["stopped"] = durdu
        if ozet[YAZILDI] == 0 and ozet[ATLANDI]:
            sonuc["notices"].append(f"Hiçbir obje YAZILMADI: {ozet[ATLANDI]} hedef atlandı (zaten vardı/aynıydı).")
        if ozet[HATA] or ozet[ISLENMEDI]:
            return cikis(EXIT_HATA, ("run_stopped" if durdu else "partial_failure",
                                     f"yazıldı {ozet[YAZILDI]} · atlandı {ozet[ATLANDI]} · hata {ozet[HATA]} · "
                                     f"işlenmedi {ozet[ISLENMEDI]}" + (f" — {durdu}" if durdu else "")))
        if ozet[ATLANDI] and fail_on_skip:
            return cikis(EXIT_ATLANDI, ("skipped_rows", f"{ozet[ATLANDI]} hedef atlandı (--fail-on-skip)."))
        return cikis(EXIT_OK, ok=True)
    finally:
        if tmp is not None:
            shutil.rmtree(tmp, ignore_errors=True)
            sonuc["temp_dir_removed"] = not tmp.exists()


def _ozet(satirlar: list) -> dict:
    oz = {k: 0 for k in (YAZILDI, ATLANDI, HATA, ISLENMEDI, DRY_RUN)}
    for s in satirlar:
        oz[s["status"]] = oz.get(s["status"], 0) + 1
    oz["total"] = len(satirlar)
    return oz


# ═════════════════════════════ komut satırı ═════════════════════════════════════════════════════

def main(argv=None) -> int:
    """`scripts/sap_adt_populate.py` giriş noktası — stdout'a TEK JSON."""
    import argparse
    import json
    import os
    import sys

    class _P(argparse.ArgumentParser):
        def error(self, message):
            raise KullanimHatasi("usage_error", message)

    p = _P(prog="sap_adt_populate.py", description="CSV/dizinden toplu SAP obje yazımı (her adım kapıdan geçer).")
    p.add_argument("type", help="|".join(TURLER))
    p.add_argument("--csv")
    p.add_argument("--source-dir", help="cds: *.cds dosyaları (dosya adı = tanım adı)")
    p.add_argument("--package")
    p.add_argument("--transport")
    p.add_argument("--only", help="virgüllü ad listesi; --force-recreate ile TEK ad")
    p.add_argument("--force-recreate", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--fail-on-skip", action="store_true")
    p.add_argument("--allow-overwrite", action="store_true", help="msag: mevcut mesaj metnini değiştirmeye izin")
    p.add_argument("--name", help="msag: mesaj sınıfı adı")
    p.add_argument("--description", help="msag: kabuk açıklaması (sınıf yoksa)")
    p.add_argument("--project-dir")
    p.add_argument("--sap-write", action="store_true")
    p.add_argument("--scope")
    p.add_argument("--reason")
    p.add_argument("--intake")

    def yaz(payload, kod):
        print(json.dumps(payload, ensure_ascii=False, default=str))
        return kod

    try:
        ns = p.parse_args(argv)
    except KullanimHatasi as kh:
        return yaz({"ok": False, "tool": "populate", "class": "write", "result": None,
                    "error": {"code": kh.code, "message": kh.message}, "gate": None}, EXIT_KULLANIM)
    proj = Path(ns.project_dir).resolve() if ns.project_dir else Path.cwd().resolve()
    if not proj.is_dir():
        return yaz({"ok": False, "tool": "populate", "class": "write", "result": None,
                    "error": {"code": "project_dir_invalid", "message": f"Proje dizini yok: {proj}"}, "gate": None},
                   EXIT_KULLANIM)
    from sapadt.project import PROJECT_ENV
    os.environ[PROJECT_ENV] = str(proj)
    import sap_adt_cli as cli  # noqa: E402 — PROJECT_ENV'den SONRA
    from sapadt import gate, project, redact

    bayrak = dict(sap_write=ns.sap_write, scope=ns.scope, reason=ns.reason, intake=ns.intake)
    cli._tls_uyarisi(proj)

    def cagir(tool, args):
        return cli.calistir(tool, args, proj, tls_uyarisi=False, **bayrak)

    def kontrol(tool, args):
        sinif, _g, err = cli.on_kontrol(tool, args, proj, **bayrak)
        return sinif, err

    def logla(tool, args, err):
        gate.log_write_attempt(proj, tool=tool, obje_adi=gate.obje_adi(tool, args),
                               object_type=args.get("object_type"), scope=ns.scope, reason=ns.reason,
                               intake=ns.intake, result_code=err[0], exit_code=EXIT_KAPI)

    payload, kod = kos(ns.type, cagir=cagir, kontrol=kontrol, logla=logla, csv_yolu=ns.csv,
                       kaynak_dizini=ns.source_dir, package=ns.package, transport=ns.transport, only=ns.only,
                       force_recreate=ns.force_recreate, dry_run=ns.dry_run, fail_on_skip=ns.fail_on_skip,
                       allow_overwrite=ns.allow_overwrite, msag_adi=ns.name, msag_aciklama=ns.description)
    payload["gate"]["project_dir"] = str(proj)
    sirlar = (redact.bilinen_sirlar(project.effective_conn_value("ADT_SAP_USER", None, proj),
                                    project.effective_conn_value("ADT_SAP_PASSWORD", None, proj))
              + redact.host_sirlari(project.effective_conn_value("ADT_SAP_URL", None, proj)))
    return yaz(redact.temizle(payload, sirlar), kod)
