# -*- coding: utf-8 -*-
"""Kesin Yasak A kaynak tarayıcısı — Z adlı bir obje içinden STANDART objeyi genişletmek/değiştirmek.

Saf fonksiyon, ağ yok: `tara(kaynak, object_type) -> list[Bulgu]` · `tara_tabl_xml(xml) -> list[Bulgu]`.
Yazma kapısı (`gate.check_std_extension`), `tools/atom.py::adt_push_source` (ikinci katman) ve
abapGit teslim denetimi (`sap-abapgit-delivery/scripts/abapgit_zip.py`) AYNI fonksiyonu çağırır.

Neden ad denetimi yetmez: genişletme objesinin KENDİ adı Z'lidir (`ZZAVBAK`, `ZE_I_SO`), hedef ise
kaynağın İÇİNDE yazılıdır. `check_names` yalnız obje adına baktığı için bu yol kapıdan geçiyordu
(ölçüldü 2026-09-24: 6/6 sentetik çağrı `allowed=True`).

Tanınan biçimler (kanıt: SAP-samples/abap-platform-rap630-ext `*.ddls.asddls` / `*.bdef.asbdef` /
`zrap630extsshop_sol.tabl.xml`; SAP/abap-file-formats `z_aff_example_bdef_extension.bdef.*`):
  · DDIC append (ADT kaynağı)  : `extend type <hedef> with <append>`
  · CDS genişletme            : `extend view [entity] <hedef> with` · `extend custom|abstract entity <hedef> with`
                                (anahtar sözcük dizisi genel tutulur: EXTEND <sözcükler> <hedef> WITH)
  · metadata extension        : `annotate view|entity <hedef> with`
  · BDEF genişletme           : başlık `extension …;` — genişletilen BDEF kaynakta YAZILMAZ (ADT metadata'sı
                                `extendedBehaviorDefintion`); `extend behavior for <X>`'teki X bir ALIAS olabilir
                                (SAP örneği: Z tabanlı BO'da `extend behavior for Shop`). Hedef yalnız
                                `extension using interface <I>` ile kaynakta görünür ⇒ `using interface` yoksa
                                FAIL-CLOSED (standart olmadığı kanıtlanamaz).
  · abapGit TABL XML          : `<TABCLASS>APPEND</TABCLASS>` + `<SQLTAB><hedef></SQLTAB>`

FAIL-CLOSED: `EXTEND`/`ANNOTATE` sözcüğü (yorum ve dize DIŞINDA) bulunup hedef çözülemezse bulgu üretilir.
Yorum: `//` ve `/* */` atılır; `'…'` dizeleri atılır; baştaki BOM (U+FEFF) atılır.
`--`: SAP'nin CDS/BDL'de `--`'yı yorum sayıp saymadığı DOĞRULANMADI ⇒ kaynak ÜÇ görünümde taranır ve bulgular
BİRLEŞTİRİLİR (görünümler aynı uzunlukta, konum/satır hizalı):
  (a) `--` satırı TÜKETİLİR ama SİLİNMEZ — içindeki `/*` blok açmaz, metni taranır (en geniş görünüm);
  (b) `--` satır yorumudur — içeriği boşaltılır (SAP yorum sayıyorsa gerçek kod budur);
  (c) `--` özel değildir — içindeki `/*`, `//`, `'` normal işler (SAP yorum saymıyorsa gerçek kod budur).
Birleştirme kuralı: herhangi bir görünüm standart hedef çözerse bulgu; hiçbiri standart çözmez ama bir görünüm
genişletmeyi görüp hedefi çözemezse `?` (fail-closed); ancak genişletmeyi gören TÜM görünümler yalnız Z/Y
çözdüyse serbest. Tek görünüm yetmiyordu (ölçüldü 2026-09-24): (a) tek başına `-- /*` … `-- */` sarmalına karşı
güvenliydi ama `--` içindeki `;` BDEF başlığını erken bitirip `--` içindeki YEM Z arayüzünü topluyordu → `[]`.
Güvenlik iddiası iki SAP davranışının (b)/(c) doğru modellenmesine dayanır; SAP'nin gerçek davranışı ölçülmedi.
Bilinen yanlış pozitif: `--` satırında standart hedefli genişletme metni geçerse red ((a)/(c) görür).
ABAP kaynak tipleri (class, program, include, function…) taranmaz: ABAP dilinde standart DDIC/CDS objesini
kaynaktan genişleten ifade yoktur; ENHO yazan araç yoktur.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

__all__ = ["Bulgu", "tara", "tara_tabl_xml", "mesaj", "YONLENDIRME", "izinli"]

YONLENDIRME = ("Standart objeler (Z/Y dışı DDIC, CDS, BDEF, program) yalnız OKUNUR: append yapısını, "
               "extend/annotate genişletmesini ve BDEF extension'ı sen yaratmazsın — kullanıcı yaratır, sonucu "
               "sana bildirir, sen sistemden okuyup doğrularsın. Append/DTEL adı önerme.")


@dataclass(frozen=True)
class Bulgu:
    satir: int
    ifade: str
    hedef: str
    neden: str

    def as_dict(self) -> dict:
        return asdict(self)


def izinli(hedef: str) -> bool:
    """Z/Y öneki ya da /Z…/ · /Y…/ müşteri namespace'i (Yasak B tarayıcısıyla AYNI kural)."""
    from sapadt.std_dml_scan import _izinli
    return _izinli(hedef)


# ── tip sınıflandırması ─────────────────────────────────────────────────────────────────
_BDEF_TIPLERI = frozenset({"bdef", "behaviordefinition"})


def _kip(object_type) -> str:
    """'abap' (taranmaz) · 'bdef' · 'ddl' · 'bilinmiyor' (içerikten karar; fail-closed)."""
    if object_type is None or not str(object_type).strip():
        return "bilinmiyor"
    t = str(object_type).strip().lower()
    if t in _BDEF_TIPLERI:
        return "bdef"
    try:
        import object_types as _ot  # type: ignore  (sapadt import'u lib/'i sys.path'e ekler)
    except Exception:  # noqa: BLE001 — tip tablosu yoksa içerikten karar ver (tara)
        return "bilinmiyor"
    if _ot.is_class_include(t):
        return "abap"
    try:
        kanonik = _ot.normalize_object_type(t)
    except ValueError:
        return "bilinmiyor"
    uzanti = str(_ot.OBJECT_TYPES.get(kanonik, {}).get("file_extension") or "")
    return "abap" if uzanti.endswith(".abap") else "ddl"


# ── temizleme: yorum + dize → boşluk (satır sonları ve konumlar korunur) ─────────────────
# SAP'nin CDS/BDL'de `--`'yı yorum sayıp saymadığı DOĞRULANMADI ⇒ kaynak ÜÇ görünümde taranır, bulgular BİRLEŞİR:
#   (a) `--` satırı TÜKETİLİR ama SİLİNMEZ (içindeki `/*` blok açmaz, metni taranır) — en geniş görünüm
#   (b) `--` satır yorumudur → içeriği boşaltılır            (SAP yorum sayıyorsa gerçek kod budur)
#   (c) `--` özel değildir → içindeki `/*`, `//`, `'` normal işler (SAP yorum saymıyorsa gerçek kod budur)
# Tek görünüm kördü (bug gate 2026-09-24): (a)'da `--` içindeki `;` BDEF başlığını erken bitiriyor, `--` içindeki
# yem Z arayüzü toplanıyor, gerçek standart arayüz görünmüyordu → `[]`.
_YORUM_DIZE = re.compile(r"'(?:[^'\n]|'')*'?|/\*.*?(?:\*/|\Z)|//[^\n]*|--[^\n]*", re.S)
_YORUM_DIZE_KOD = re.compile(r"'(?:[^'\n]|'')*'?|/\*.*?(?:\*/|\Z)|//[^\n]*", re.S)


def _bosalt(m: re.Match) -> str:
    metin = m.group(0)
    if metin.startswith("--"):
        return metin                                     # (a): tüketildi, silinmedi (bkz. modül notu)
    return re.sub(r"[^\n]", " ", metin)


def _bosalt_tumu(m: re.Match) -> str:
    return re.sub(r"[^\n]", " ", m.group(0))


def _gorunumler(kaynak: str) -> tuple[str, str, str]:
    """(a), (b), (c) görünümleri — aynı uzunlukta (konum ve satır numaraları hizalı). Baştaki BOM (U+FEFF) atılır:
    `\\s` onu boşluk saymaz ⇒ BDEF başlığının `^` çapası BOM'lu kaynakta eşleşmiyordu (ölçüldü 2026-09-24: `[]`)."""
    src = kaynak.replace("\r\n", "\n").replace("\r", "\n")
    if src.startswith("﻿"):
        src = src[1:]
    return (_YORUM_DIZE.sub(_bosalt, src), _YORUM_DIZE.sub(_bosalt_tumu, src),
            _YORUM_DIZE_KOD.sub(_bosalt_tumu, src))


_AD = r"(?:/[A-Z0-9_]+/)?[A-Z_][A-Z0-9_]*"
_F = re.I
_ANAHTAR = re.compile(r"(?<![\w/$#@.:\-])(?P<kw>EXTEND|ANNOTATE)(?![\w/])", _F)
_R_EXTEND = re.compile(
    rf"EXTEND\s+(?P<ara>(?:(?:VIEW|ENTITY|CUSTOM|ABSTRACT|TYPE|PROJECTION|HIERARCHY|TABLE|STRUCTURE|ASPECT)\s+)*)"
    rf"(?P<tgt>{_AD})\s+WITH\b", _F)
_R_ANNOTATE = re.compile(rf"ANNOTATE\s+(?P<ara>(?:VIEW|ENTITY)\s+)(?P<tgt>{_AD})\s+WITH\b", _F)
# Baştaki `--` satırları atlanır ((a)/(c) görünümünde SİLİNMEZLER): `--` SAP'de yorumsa başlık onlardan sonradır.
# Her tekrar `\n` ile biter ⇒ bölüştürme tek yollu (geri izleme patlaması yok).
_R_BDEF_BASLIK = re.compile(r"^(?:[ \t\n]*--[^\n]*\n)*\s*(?P<bas>EXTENSION\b(?P<govde>[^;]*);?)", _F)
_R_BDEF_ARAYUZ = re.compile(rf"\bUSING\s+INTERFACE\s+(?P<tgt>{_AD})(?![\w/])", _F)
_R_EXTEND_BEHAVIOR = re.compile(rf"(?<![\w/])EXTEND\s+BEHAVIOR\s+FOR\s+(?P<tgt>{_AD})", _F)


def _satir(metin: str, konum: int) -> int:
    return metin.count("\n", 0, konum) + 1


def _gorunum(s: str, azami: int = 80) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= azami else s[: azami - 1] + "…"


def _ddl_bulgulari(gorunumler) -> list[Bulgu]:
    """Her görünümde her EXTEND/ANNOTATE sözcüğü. Görünümler konumca hizalı: aynı sözcükte HERHANGİ bir görünüm
    standart hedef çözerse o bulgu; hiçbiri standart çözmez ama biri çözemezse `?` (fail-closed); hepsi Z/Y → serbest."""
    std: dict[tuple[int, str], Bulgu] = {}
    belirsiz: dict[int, Bulgu] = {}
    for temiz in gorunumler:
        for m in _ANAHTAR.finditer(temiz):
            kw = m.group("kw").upper()
            rx = _R_EXTEND if kw == "EXTEND" else _R_ANNOTATE
            e = rx.match(temiz, m.start())
            satir = _satir(temiz, m.start())
            if not e:
                parca = temiz[m.start(): m.start() + 80].split("\n", 2)
                belirsiz.setdefault(m.start(), Bulgu(
                    satir, _gorunum(" ".join(parca[:2])), "?",
                    f"{kw} sözcüğü var ama hedef çözülemedi (tanınmayan biçim) — fail-closed"))
                continue
            hedef = e.group("tgt").upper()
            if not izinli(hedef):
                bicim = " ".join([kw.lower()] + e.group("ara").lower().split())
                std.setdefault((m.start(), hedef),
                               Bulgu(satir, _gorunum(e.group(0)), hedef, f"{bicim} <standart obje>"))
    std_konum = {konum for konum, _h in std}
    return list(std.values()) + [b for konum, b in belirsiz.items() if konum not in std_konum]


def _bdef_bulgulari(gorunumler) -> tuple[list[Bulgu], bool]:
    """→ (bulgular, BDEF genişletmesi algılandı mı). Başlık ve `using interface` HER görünümde ayrı çözülür, bulgular
    birleşir: herhangi bir görünümde standart arayüz → bulgu; standart yok ama algılayan bir görünümde arayüz
    çözülemedi → `?` (fail-closed); algılayan tüm görünümler yalnız Z/Y arayüz çözdüyse serbest."""
    std: dict[str, Bulgu] = {}
    belirsiz: Bulgu | None = None
    algilandi = False
    for temiz in gorunumler:
        baslik = _R_BDEF_BASLIK.match(temiz)
        davranis = list(_R_EXTEND_BEHAVIOR.finditer(temiz))
        if not baslik and not davranis:
            continue                                     # bu görünümde BDEF genişletmesi yok (define behavior)
        algilandi = True
        satir = _satir(temiz, baslik.start("govde") if baslik else davranis[0].start())
        # HEPSİ denetlenir (ilki değil): (a) görünümünde ilk eşleşme bir `--` satırındaki Z adı olabilir.
        arayuzler = [a.group("tgt").upper() for a in _R_BDEF_ARAYUZ.finditer(baslik.group("govde"))] if baslik else []
        if not arayuzler:
            if belirsiz is None:
                ifade = _gorunum(baslik.group("bas")) if baslik else _gorunum(davranis[0].group(0))
                belirsiz = Bulgu(satir, ifade, "?",
                                 "BDEF genişletmesi: genişletilen BDEF kaynakta yazılı değil (ADT metadata'sında; "
                                 "`extend behavior for <X>` alias olabilir) — standart olmadığı kanıtlanamadı, fail-closed")
            continue
        for hedef in arayuzler:
            if not izinli(hedef):
                std.setdefault(hedef, Bulgu(satir, _gorunum(baslik.group("bas")), hedef,
                                            "BDEF extension using interface <standart BO>"))
    if std:
        return list(std.values()), algilandi
    return ([belirsiz] if belirsiz else []), algilandi


def tara(kaynak: str, object_type: str | None = None) -> list[Bulgu]:
    """Standart (Z/Y dışı) objeyi genişleten/değiştiren ifadeler. ABAP kaynak tipinde `[]`."""
    if not isinstance(kaynak, str):
        raise TypeError("kaynak metin (str) olmalı")
    kip = _kip(object_type)
    if kip == "abap":
        return []
    gorunumler = _gorunumler(kaynak)
    if kip == "bdef":
        bulgular = _bdef_bulgulari(gorunumler)[0]
    elif kip == "ddl":
        bulgular = _ddl_bulgulari(gorunumler)
    else:
        # Tip bilinmiyor: BDEF genişletmesi algılanırsa BDEF kuralları + DDL taramasının ÇÖZÜLMÜŞ standart hedefleri
        # (`extend behavior` DDL tarayıcısında `?` üretir — o atlanır). Tek-yollu karar kördü (ölçüldü 2026-09-24):
        # Z arayüzlü `extension` başlığı, arkasındaki `extend view entity <std>`'yi `[]`'e gizliyordu.
        bulgular, bdef_mi = _bdef_bulgulari(gorunumler)
        ddl = _ddl_bulgulari(gorunumler)
        if bdef_mi:
            gorulen = {(b.satir, b.hedef) for b in bulgular}
            bulgular = bulgular + [b for b in ddl if b.hedef != "?" and (b.satir, b.hedef) not in gorulen]
        else:
            bulgular = ddl
    bulgular.sort(key=lambda b: (b.satir, b.hedef))
    return bulgular


_R_TABCLASS = re.compile(r"<TABCLASS>\s*APPEND\s*</TABCLASS>", _F)
_R_SQLTAB = re.compile(r"<SQLTAB>\s*(?P<tgt>[^<\s]*)\s*</SQLTAB>", _F)


def tara_tabl_xml(xml: str) -> list[Bulgu]:
    """abapGit TABL XML'i: append yapısı (`TABCLASS=APPEND`) standart tabloyu (`SQLTAB`) genişletiyor mu.
    `SQLTAB` yok/boşsa FAIL-CLOSED."""
    if not isinstance(xml, str):
        raise TypeError("xml metin (str) olmalı")
    m = _R_TABCLASS.search(xml)
    if not m:
        return []
    satir = _satir(xml, m.start())
    s = _R_SQLTAB.search(xml)
    hedef = (s.group("tgt").strip().upper() if s else "")
    if not hedef:
        return [Bulgu(satir, "TABCLASS=APPEND", "?",
                      "append yapısı ama genişletilen tablo (SQLTAB) okunamadı — fail-closed")]
    if izinli(hedef):
        return []
    return [Bulgu(satir, f"TABCLASS=APPEND SQLTAB={hedef}", hedef, "append yapısı <standart tablo>")]


def mesaj(bulgular: list[Bulgu], azami: int = 5) -> str:
    satirlar = [f"satır {b.satir}: {b.ifade} → hedef {b.hedef} ({b.neden})" for b in bulgular[:azami]]
    ek = f" (+{len(bulgular) - azami} bulgu daha)" if len(bulgular) > azami else ""
    return (f"Kesin Yasak A: standart obje genişletme/değiştirme — {len(bulgular)} bulgu{ek}. "
            + " · ".join(satirlar) + ". " + YONLENDIRME + " Kaynak SAP'ye gönderilmedi.")
