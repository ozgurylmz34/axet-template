#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_fm_signature_doc_sync.py — bir Z fonksiyon modülünün İMZASI ile onu anlatan DOKÜMAN arasındaki sapma.

Neden: paylaşılan bir Z FM'in (üreteç, ortak servis, RFC arayüzü) parametreleri değişince onu anlatan doküman
(TS §9 arayüz bölümü, kullanım kılavuzu) kimsenin sorumluluğunda olmadan bayatlar. Bayat doküman "bulunamadı" gibi
görünmez: bir sonraki geliştirici onu BULUR ve eksik bilgiyle çağrı kurar (ör. imzaya eklenmiş bir tablo parametresi
dokümanda yoksa "FM bunu yapamıyor" sanılıp yanlış yola girilir). Kaynak ile doküman arasında başka bağ yoktur.

Nasıl (kesin eşleştirme, sezgi yok):
  1. Dokümanlarda MAKİNE-OKUNUR imza blokları aranır:
         <!-- FM-IMZA: Z_DEMO_FM -->
         ... (tablo/metin — parametre adları geçer)
         <!-- /FM-IMZA -->
     Blok sınırı bilinçlidir: dokümanın geri kalanında başka API'lerin parametreleri geçer; blok dışı sayılmaz.
  2. Her bloktaki FM'in kaynağı kaynak kökündeki `*.abap` dosyalarında `FUNCTION <ad>` satırıyla bulunur ve imzası
     ayrıştırılır (IMPORTING/EXPORTING/CHANGING/TABLES; EXCEPTIONS/RAISING parametre sayılmaz). İki biçim: satır içi
     imza (`FUNCTION z … IMPORTING … .`) ve eski `*"Local Interface:` yorum bloğu.
  3. Fark iki yönde raporlanır:
       EKSİK   : imzada VAR, blokta YOK (bayat doküman — asıl vaka). Bloktaki her tanımlayıcı harf duyarsız sayılır.
       HAYALET : blokta VAR, imzada YOK (kaldırılmış/yanlış yazılmış parametre). Yalnız adlandırma önekli BÜYÜK harf
                 token'lar (IV_/IT_/IS_/IO_/IR_/EV_/ET_/ES_/CV_/CT_/CS_/EX_) aday sayılır.

Kullanım:
  python check_fm_signature_doc_sync.py [YOL ...] [--kaynak-kok KLASÖR] [--bulguda-exit1]
  python check_fm_signature_doc_sync.py --selftest
YOL: .md dosyası ya da klasör (varsayılan: proje kaynak kökü = `sap-project.json` `source_root`, yoksa SOURCE_CODES;
proje kökü env `AXET_SAP_PROJECT_DIR` → bulunulan klasör). Klasörde tüm `*.md` taranır (paket `docs/` dahil).
--kaynak-kok: FM kaynağının aranacağı klasör (varsayılan: aynı proje kaynak kökü).

Çıkış ("bakamadım" ≠ "temiz"):
  0 = TEMİZ ya da SAPMA (varsayılan uyarıdır, kapı değildir) · 1 = sapma var ve `--bulguda-exit1` verildi ·
  2 = ÖLÇÜLEMEDİ — olmayan yol · okunamayan/UTF-8 olmayan dosya · kapanmamış blok · FM kaynağı bulunamadı ya da
      birden çok dosyada tanımlı · imza sonu (`.`) bulunamadı · imzada tanınmayan satır.
Sıfır blok exit 0'dır ama "temiz" denmez; ayrı cümle basılır.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

# Paylaşılan yardımcılar (klasör yürüyüşü, bağlantı tespiti, katı UTF-8 okuma) kardeş script'ten alınır; yeniden
# türetilmez — o modülün ölçülmüş tuzakları (junction döngüsü, UTF-16'yı "temiz" okuma) burada da geçerlidir.
from check_fs_no_analysis_log import _SKIP, _baglanti_mi, _kimlik, _oku  # noqa: E402

for _akis in (sys.stdout, sys.stderr):
    try:
        _akis.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

SCOPE = ("KAPSAM (SCOPE): check_fm_signature_doc_sync — bakılanlar: dokümanlardaki `<!-- FM-IMZA: <FM> -->` "
         "bloklarında geçen parametre adları ↔ FM kaynağındaki imza parametreleri (IMPORTING/EXPORTING/CHANGING/"
         "TABLES), iki yönde (EKSİK · HAYALET).")

BAKILMAYANLAR = [
    "FM-IMZA bloğu OLMAYAN doküman — bloksuz dokümandaki imza anlatımı hiç karşılaştırılmaz (sıfır blok ≠ temiz)",
    "parametre TİPİ, varsayılan değeri, OPTIONAL işareti ve anlamı — yalnız parametre ADI karşılaştırılır",
    "EXCEPTIONS / RAISING (istisnalar) — parametre sayılmaz",
    "HAYALET yalnız önekli BÜYÜK harf token'larda aranır (IV_/IT_/IS_/IO_/IR_/EV_/ET_/ES_/CV_/CT_/CS_/EX_); "
    "başka adlandırmayla yazılmış hayalet parametre görülmez",
    "EKSİK harf duyarsız tanımlayıcı eşleşmesidir: parametre adı blokta başka bir anlamda (ör. düz yazıda) geçerse "
    "belgelenmiş sayılır",
    "SAP sistemindeki güncel imza — yalnız yerel kaynak dosyası okunur; yerel kaynak bayatsa önce sistemden çek",
    "makro/dinamik biçimde üretilmiş imza · kaynak kökü dışındaki FM kaynağı",
    "tipsiz IMPORTING/EXPORTING/CHANGING parametresi ve tanınmayan tip sözdizimi — atlanmaz, ÖLÇÜLEMEDİ (çıkış 2) verir",
    "atlanan klasörler (%s) ve dizin bağlantıları (junction/symlink) — izlenmez" % ", ".join(sorted(_SKIP)),
]

_BLOK = re.compile(r"<!--\s*FM-IMZA:\s*([A-Za-z0-9_/]+)\s*-->")
_BLOK_SON = "<!-- /FM-IMZA -->"
_BOLUMLER = {"IMPORTING", "EXPORTING", "CHANGING", "TABLES", "EXCEPTIONS", "RAISING"}
_PARAM_BOLUM = {"IMPORTING", "EXPORTING", "CHANGING", "TABLES"}
_AYRILMIS = _BOLUMLER | {"TYPE", "LIKE", "STRUCTURE", "DEFAULT", "OPTIONAL", "REF", "TO", "OF"}
# İmza token'ları: dize ('…', `…`) · VALUE(x)/REFERENCE(x) · boşluksuz sözcük · deyim sonu nokta.
_TOKEN = re.compile(r"'(?:[^']|'')*'|`[^`]*`|(?:VALUE|REFERENCE)\s*\(\s*[A-Za-z_][A-Za-z0-9_]*\s*\)|[^\s.'`]+|\.",
                    re.IGNORECASE)
_BAS = re.compile(r"^(?:VALUE|REFERENCE)\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)$", re.IGNORECASE)
_AD = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_TIP_ADI = re.compile(r"^[A-Za-z_/][A-Za-z0-9_/\-=>~]*$")
_GENEL_TABLO = {"STANDARD", "SORTED", "HASHED", "INDEX", "ANY"}   # `TYPE ANY TABLE` gibi iki sözcüklü genel tip
_KIMLIK = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_ONEKLI = re.compile(r"\b(?:IV|IT|IS|IO|IR|EV|ET|ES|CV|CT|CS|EX)_[A-Z0-9][A-Z0-9_]*\b")


class Olculemedi(Exception):
    """Ölçüm yapılamadı — 'temiz' ile aynı çıkışa düşmesin diye ayrı sınıf."""


# ── imza ayrıştırma ─────────────────────────────────────────────────────────────
def _yorumsuz(satir: str) -> str:
    """Satır sonu `"` yorumunu at — dize ('…' / `…`) içindeki `"` yorum başlatmaz."""
    dize = None
    for i, c in enumerate(satir):
        if dize:
            if c == dize:
                dize = None
        elif c in "'`":
            dize = c
        elif c == '"':
            return satir[:i]
    return satir


def _imza_tokenlari(metin: str, fm: str) -> list:
    """FUNCTION satırından imza deyiminin sonuna kadar token listesi. Sonu bulunamazsa Olculemedi.

    İki biçim: satır içi imza (`FUNCTION z … IMPORTING … .` — sonu ilk dize-dışı nokta) ve `FUNCTION z.` ardından gelen
    `*"` yorum bloğu (eski biçim; başlık satırları — sonu `:` ile biten `*"*"…:` — ve çizgiler atlanır, blok sonu = imza sonu)."""
    satirlar = metin.splitlines()
    bas = next((i for i, s in enumerate(satirlar)
                if re.match(r"^\s*FUNCTION\s+%s(?![A-Za-z0-9_/])" % re.escape(fm), s, re.IGNORECASE)), None)
    if bas is None:
        raise Olculemedi("kaynakta `FUNCTION %s` satırı yok" % fm)
    ilk = _yorumsuz(satirlar[bas]).strip()
    kalan = re.sub(r"^FUNCTION\s+[A-Za-z0-9_/]+", "", ilk, flags=re.IGNORECASE).strip()
    if kalan == ".":
        # Blok FUNCTION satırından sonra boş ya da düz `*` yorum satırlarıyla ayrılmış olabilir → onlar atlanıp blok
        # yine bulunur. Kod başladıktan SONRA bir `*"` satırı görülürse bu imza mı, alıntı mı belirsizdir → ÖLÇÜLEMEDİ
        # (sessizce "parametresiz FM" saymak EKSİK'i gizler, önekli blok token'larını sahte HAYALET yapardı).
        j = bas + 1
        while j < len(satirlar) and (not satirlar[j].strip() or (satirlar[j].lstrip().startswith("*")
                                                                    and not satirlar[j].lstrip().startswith('*"'))):
            j += 1
        if not (j < len(satirlar) and satirlar[j].lstrip().startswith('*"')):
            for s in satirlar[j:]:
                if re.match(r"^\s*ENDFUNCTION\b", s, re.IGNORECASE):
                    break
                if s.lstrip().startswith('*"'):
                    raise Olculemedi("`FUNCTION %s.` sonrasında imza bloğu yok ama gövdede `*\"` satırı var — imza mı "
                                     "yorum mu belirsiz" % fm)
            return []                             # imzasız (parametresiz) FM
        tokenlar = []
        for s in satirlar[j:]:
            if not s.lstrip().startswith('*"'):
                break
            govde = s.lstrip()[2:]
            ic = govde.lstrip(' *"-\t')
            if not ic.strip() or ic.rstrip().endswith(":"):
                continue                          # çizgi ya da başlık (Local Interface: · Lokale Schnittstelle: …)
            tokenlar += _TOKEN.findall(govde)
        if "." in tokenlar:
            raise Olculemedi("yorum biçimli imzada beklenmeyen nokta — ayrıştırma belirsiz")
        return tokenlar
    tokenlar = []
    for s in [kalan] + [_yorumsuz(x) for x in satirlar[bas + 1:] if not x.lstrip().startswith("*")]:
        for tok in _TOKEN.findall(s):
            if tok.upper() == "ENDFUNCTION":
                raise Olculemedi("`FUNCTION %s` imzasının sonu (`.`) bulunamadı — ayrıştırma yarım kalırdı" % fm)
            if tok == ".":
                return tokenlar
            tokenlar.append(tok)
    raise Olculemedi("`FUNCTION %s` imzasının sonu (`.`) bulunamadı — ayrıştırma yarım kalırdı" % fm)


def imza_parametreleri(metin: str, fm: str) -> set:
    """FM imzasındaki parametre adları (BÜYÜK harf). Bir satırda birden çok parametre/bölüm olabilir; token token
    ayrıştırılır. Tanınmayan her yapı Olculemedi'dir (sessiz yarım sonuç yok)."""
    tok = _imza_tokenlari(metin, fm)
    parametreler, bolum, i, n = set(), None, 0, len(tok)

    def bozuk(neden):
        raise Olculemedi("imza ayrıştırılamadı (%s): …%s…" % (neden, " ".join(tok[max(0, i - 3):i + 4])))

    def tip_adi(j):
        return j < n and tok[j].upper() not in _AYRILMIS and bool(_TIP_ADI.match(tok[j]))

    while i < n:
        u = tok[i].upper()
        if u in _BOLUMLER:
            bolum, i = u, i + 1
            continue
        if bolum is None:
            bozuk("bölüm anahtar sözcüğünden önce token")
        if bolum not in _PARAM_BOLUM:             # EXCEPTIONS / RAISING: istisna adları, parametre değil
            i += 1
            continue
        m = _BAS.match(tok[i])
        if m:
            ad = m.group(1)
        elif _AD.match(tok[i]) and u not in _AYRILMIS:
            ad = tok[i]
        else:
            bozuk("parametre adı beklenirken")
        i += 1
        if i < n and tok[i].upper() in ("TYPE", "LIKE", "STRUCTURE"):
            i += 1
            if i < n and tok[i].upper() == "REF":
                if not (i + 1 < n and tok[i + 1].upper() == "TO" and tip_adi(i + 2)):
                    bozuk("TYPE REF TO <tip> beklenirken")
                i += 3
            elif i + 1 < n and tok[i].upper() in _GENEL_TABLO and tok[i + 1].upper() == "TABLE":
                i += 2
            elif tip_adi(i):
                i += 1
            else:
                bozuk("tip adı beklenirken")
        elif bolum != "TABLES" or m:
            bozuk("tipsiz parametre (yalnız TABLES'ta tanınır)")
        if i < n and tok[i].upper() == "OF":
            bozuk("`… TABLE OF <tip>` imza sözdizimi tanınmıyor")   # `OF`/tip adı sahte parametre sayılmasın
        if i < n and tok[i].upper() == "DEFAULT":
            if i + 1 >= n or tok[i + 1].upper() in _AYRILMIS:
                bozuk("DEFAULT değeri beklenirken")
            i += 2
        if i < n and tok[i].upper() == "OPTIONAL":
            i += 1
        parametreler.add(ad.upper())
    return parametreler


def belge_bloklari(metin: str):
    """[(fm, blok metni, satır no)]. Kapanmamış blok Olculemedi."""
    out, poz = [], 0
    while True:
        m = _BLOK.search(metin, poz)
        if not m:
            return out
        son = metin.find(_BLOK_SON, m.end())
        sonraki = _BLOK.search(metin, m.end())
        if son < 0 or (sonraki and sonraki.start() < son):
            raise Olculemedi("satır %d: `%s` açıldı ama `%s` ile kapatılmadı"
                             % (metin.count("\n", 0, m.start()) + 1, m.group(0), _BLOK_SON))
        out.append((m.group(1).upper(), metin[m.end():son], metin.count("\n", 0, m.start()) + 1))
        poz = son + len(_BLOK_SON)


def karsilastir(imza: set, blok: str):
    """(eksik, hayalet) — sıralı listeler."""
    tanimlayicilar = {t.upper() for t in _KIMLIK.findall(blok)}
    eksik = sorted(imza - tanimlayicilar)
    hayalet = sorted(set(_ONEKLI.findall(blok)) - imza)
    return eksik, hayalet


# ── kapsam ────────────────────────────────────────────────────────────────────────
def _yuru(kok: Path, uzanti: str, atlanan: list, baglanti: list, hata: list):
    for dp, dn, fn in os.walk(kok, onerror=hata.append):
        kalan = []
        for d in sorted(dn):
            tam = os.path.join(dp, d)
            if _baglanti_mi(tam):
                baglanti.append(tam)
            elif d.lower() in _SKIP:
                atlanan.append(tam)
            else:
                kalan.append(d)
        dn[:] = kalan
        for f in sorted(fn):
            if f.lower().endswith(uzanti):
                yield Path(dp) / f


def _proje_kaynak_koku():
    """(kaynak kökü, açıklama). Proje kimliği aXet'in tek okuma noktasından (sap-project.json) alınır."""
    lib = Path(__file__).resolve().parents[2] / "sap-adt-foundation" / "scripts" / "sapadt" / "lib"
    sys.path.insert(0, str(lib))
    try:
        from utils.project_config import project_root, source_dir, source_root_name  # noqa: E402
    except Exception as e:  # noqa: BLE001
        raise Olculemedi("proje yapılandırması okunamadı (%s: %s) — YOL ve --kaynak-kok ver" % (
            e.__class__.__name__, e))
    finally:
        sys.path.pop(0)
    return source_dir(), "sap-project.json source_root=%s (proje kökü %s)" % (source_root_name(), project_root())


def _fm_kaynaklari(kok: Path, fmler: set, atlanan, baglanti, hata):
    """{fm: [dosya, …]} — `FUNCTION <fm>` satırı taşıyan .abap dosyaları."""
    bul = {fm: [] for fm in fmler}
    if not fmler:
        return bul
    desen = re.compile(r"^\s*FUNCTION\s+([A-Za-z0-9_/]+)", re.IGNORECASE | re.MULTILINE)
    for p in _yuru(kok, ".abap", atlanan, baglanti, hata):
        try:
            metin = p.read_text(encoding="utf-8-sig", errors="replace")
        except OSError as e:
            hata.append(e)
            continue
        for m in desen.finditer(metin):
            ad = m.group(1).upper().rstrip(".")
            if ad in bul and p not in bul[ad]:
                bul[ad].append(p)
    return bul


# ── selftest ──────────────────────────────────────────────────────────────────────
_SELFTEST_ABAP = """FUNCTION z_selftest_fm
  IMPORTING
    VALUE(iv_bir) TYPE char10
    VALUE(iv_iki) TYPE char10 DEFAULT 'X'
  EXPORTING
    VALUE(ev_rc) TYPE i
  TABLES
    it_uc TYPE ztt_demo OPTIONAL.
  ev_rc = 0.
ENDFUNCTION.
"""


def selftest() -> int:
    belge = ("<!-- FM-IMZA: Z_SELFTEST_FM -->\n| `IV_BIR` | … |\n| `IV_ESKI` | kaldırılmış |\n<!-- /FM-IMZA -->\n"
             "Blok DIŞI: `IS_LAYOUT` / `IT_OUTTAB` sayılmamalı.\n")
    sorun = []
    imza = imza_parametreleri(_SELFTEST_ABAP, "Z_SELFTEST_FM")
    if imza != {"IV_BIR", "IV_IKI", "EV_RC", "IT_UC"}:
        sorun.append("imza ayrıştırma hatalı: %s" % sorted(imza))
    tek = imza_parametreleri("FUNCTION z_selftest_fm IMPORTING iv_a TYPE c iv_b TYPE c EXPORTING ev_c TYPE c.\n",
                             "Z_SELFTEST_FM")
    if tek != {"IV_A", "IV_B", "EV_C"}:
        sorun.append("tek satırda birden çok parametre/bölüm yarım ayrıştırıldı: %s" % sorted(tek))
    bloklar = belge_bloklari(belge)
    eksik, hayalet = karsilastir(imza, bloklar[0][1])
    if eksik != ["EV_RC", "IT_UC", "IV_IKI"]:
        sorun.append("EKSİK sınıfı yakalanmadı: %s" % eksik)
    if hayalet != ["IV_ESKI"]:
        sorun.append("HAYALET sınıfı yakalanmadı / blok dışı sayıldı: %s" % hayalet)
    for bozuk, ad in ((_SELFTEST_ABAP.replace("OPTIONAL.", "OPTIONAL"), "imza sonu yok"),
                      (_SELFTEST_ABAP.replace("TYPE char10\n", "= x\n", 1), "tanınmayan satır")):
        try:
            imza_parametreleri(bozuk.replace("  ev_rc = 0.\n", ""), "Z_SELFTEST_FM")
            sorun.append("%s ÖLÇÜLEMEDİ vermedi (fail-open)" % ad)
        except Olculemedi:
            pass
    try:
        belge_bloklari("<!-- FM-IMZA: Z_SELFTEST_FM -->\nkapanmıyor")
        sorun.append("kapanmamış blok ÖLÇÜLEMEDİ vermedi (fail-open)")
    except Olculemedi:
        pass
    if sorun:
        print("[SELFTEST FAIL]\n  " + "\n  ".join(sorun))
        return 1
    print("[SELFTEST OK] imza ayrıştırma + EKSİK + HAYALET + blok sınırı + fail-closed (imza sonu, satır, blok)")
    return 0


# ── ana akış ──────────────────────────────────────────────────────────────────────
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="FM imzası ↔ doküman FM-IMZA bloğu senkron kontrolü")
    ap.add_argument("yollar", nargs="*", metavar="YOL", help=".md dosyası ya da klasör (varsayılan: proje kaynak kökü)")
    ap.add_argument("--kaynak-kok", help="FM kaynağının aranacağı klasör (varsayılan: proje kaynak kökü)")
    ap.add_argument("--bulguda-exit1", action="store_true", help="sapma varsa çıkış 1 (varsayılan: uyarı, çıkış 0)")
    ap.add_argument("--selftest", action="store_true", help="gömülü kırmızı örnekle kendini sına")
    try:
        a = ap.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    if a.selftest:
        return selftest()
    print(SCOPE)

    olculemedi, atlanan, baglanti, hata = [], [], [], []
    proje_kok = aciklama = None
    if not a.yollar or not a.kaynak_kok:
        try:
            proje_kok, aciklama = _proje_kaynak_koku()
        except Olculemedi as e:
            olculemedi.append(str(e))
    yollar = [Path(y) for y in a.yollar] or ([proje_kok] if proje_kok else [])
    kaynak_kok = Path(a.kaynak_kok) if a.kaynak_kok else proje_kok

    # 1. dokümanlar → bloklar
    belgeler, gorulen = [], set()
    for y in yollar:
        if y.is_file():
            adaylar = [y]
        elif y.is_dir():
            adaylar = list(_yuru(y, ".md", atlanan, baglanti, hata))
        else:
            olculemedi.append("yol yok: %s" % y)
            continue
        for p in adaylar:
            if _kimlik(p) not in gorulen:
                gorulen.add(_kimlik(p))
                belgeler.append(p)
    bloklar = []                                  # [(belge, fm, blok, satır)]
    for p in belgeler:
        try:
            metin = _oku(p)
        except (OSError, UnicodeDecodeError) as e:
            olculemedi.append("%s: %s (%s)" % (p, "UTF-8 değil" if isinstance(e, UnicodeDecodeError) else "okunamadı",
                                               e.__class__.__name__))
            continue
        try:
            bloklar += [(p, fm, b, n) for fm, b, n in belge_bloklari(metin)]
        except Olculemedi as e:
            olculemedi.append("%s: %s" % (p, e))

    # 2. FM kaynakları → imza → karşılaştırma
    sapma = temiz = 0
    if bloklar:
        if kaynak_kok is None or not kaynak_kok.is_dir():
            olculemedi.append("kaynak kökü yok: %s — FM kaynağı aranamadı" % kaynak_kok)
        else:
            kaynaklar = _fm_kaynaklari(kaynak_kok, {fm for _, fm, _, _ in bloklar}, atlanan, baglanti, hata)
            imzalar = {}
            for fm, dosyalar in sorted(kaynaklar.items()):
                if not dosyalar:
                    olculemedi.append("%s: kaynak kökünde `FUNCTION %s` tanımı bulunamadı (%s) — FM henüz yazılmadıysa "
                                      "blok erken eklenmiştir; yerel kaynak eksikse önce sistemden çek" % (fm, fm, kaynak_kok))
                elif len(dosyalar) > 1:
                    olculemedi.append("%s: birden çok dosyada tanımlı — hangisinin kanonik olduğu belirsiz: %s"
                                      % (fm, ", ".join(str(d) for d in dosyalar)))
                else:
                    try:
                        imzalar[fm] = (imza_parametreleri(_oku(dosyalar[0]), fm), dosyalar[0])
                    except (Olculemedi, OSError, UnicodeDecodeError) as e:
                        olculemedi.append("%s: %s — %s" % (fm, dosyalar[0], e))
            for p, fm, blok, n in bloklar:
                if fm not in imzalar:
                    continue
                imza, src = imzalar[fm]
                eksik, hayalet = karsilastir(imza, blok)
                yer = "%s:%d [%s ↔ %s]" % (p, n, fm, src.name)
                if eksik:
                    print("  EKSİK   %s: imzada VAR, blokta YOK → %s" % (yer, ", ".join(eksik)))
                if hayalet:
                    print("  HAYALET %s: blokta VAR, imzada YOK → %s" % (yer, ", ".join(hayalet)))
                if eksik or hayalet:
                    sapma += 1
                else:
                    temiz += 1
                    print("  OK      %s: %d parametrenin tamamı blokta" % (yer, len(imza)))
    for e in hata:
        olculemedi.append("klasör/dosya okunamadı: %s (%s)" % (getattr(e, "filename", None) or "?", e))

    # 3. kapsam beyanı + sonuç
    print("KAPSAM: doküman %d tarandı · FM-IMZA bloğu %d · FM kaynak kökü %s%s" % (
        len(belgeler), len(bloklar), kaynak_kok, (" (%s)" % aciklama) if aciklama and not a.kaynak_kok else ""))
    if atlanan:
        print("  ATLANAN KLASÖR TARANMADI: %s" % ", ".join(str(x) for x in atlanan[:10]))
    if baglanti:
        print("  BAĞLANTI (junction/symlink) İZLENMEDİ: %s" % ", ".join(str(x) for x in baglanti[:10]))
    print("BU ARAÇ ŞUNLARA BAKMAZ:")
    for b in BAKILMAYANLAR:
        print("  - " + b)
    for o in olculemedi:
        print("[ÖLÇÜLEMEDİ] " + o)
    if olculemedi:
        print("SONUÇ: ÖLÇÜLEMEDİ — %d sorun; ölçülen blok %d (sapma %d) — bu 'temiz' DEĞİLDİR (çıkış 2)." % (
            len(olculemedi), sapma + temiz, sapma))
        return 2
    if not bloklar:
        print("SONUÇ: DENETLENECEK BLOK YOK (0 FM-IMZA bloğu, %d doküman) — sıfır kapsam ihlal değildir ama "
              "'senkron' da değildir. İmzası belgelenen FM varsa bloğu ekle (references/ts-authoring.md §5.3)."
              % len(belgeler))
        return 0
    if sapma:
        print("SONUÇ: %d blokta sapma (%d blok temiz) — UYARI, kapı değil. Bloğu FM KAYNAĞINDAN güncelle; bayat "
              "doküman sessizce yanlış çağrı ürettirir." % (sapma, temiz))
        return 1 if a.bulguda_exit1 else 0
    print("SONUÇ: TEMİZ — %d blok, imza ↔ doküman senkron (yalnız KAPSAM satırındaki yüzeyde)." % temiz)
    return 0


if __name__ == "__main__":
    sys.exit(main())
