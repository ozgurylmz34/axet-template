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
Dize kaçışı (Z117ⓔ, 2026-09-26): SAP'nin CDS/BDL dizesinde `\\'`'yü kaçış sayıp saymadığı DOĞRULANMADI ⇒ aşağıdaki
her görünüm İKİ dize modeliyle üretilir: `''` kaçışı (taban) ve ters bölü kaçışı (`\\'` dizeyi kapatmaz). Tek modelde
`'x\\'' extend view entity I_… with` satırının geri kalanı dize sanılıp gizleniyordu (ölçüldü: `[]`).
`--`: SAP'nin CDS/BDL'de `--`'yı yorum sayıp saymadığı DOĞRULANMADI ⇒ kaynak ÜÇ görünümde (× iki dize modeli = altı)
taranır ve bulgular BİRLEŞTİRİLİR (görünümler aynı uzunlukta, konum/satır hizalı):
  (a) `--` satırı TÜKETİLİR ama SİLİNMEZ — içindeki `/*` blok açmaz, metni taranır (en geniş görünüm);
  (b) `--` satır yorumudur — içeriği boşaltılır (SAP yorum sayıyorsa gerçek kod budur);
  (c) `--` özel değildir — içindeki `/*`, `//`, `'` normal işler (SAP yorum saymıyorsa gerçek kod budur).
Birleştirme kuralı: herhangi bir görünüm standart hedef çözerse bulgu; hiçbiri standart çözmez ama bir görünüm
genişletmeyi görüp hedefi çözemezse `?` (fail-closed); ancak genişletmeyi gören TÜM görünümler yalnız Z/Y
çözdüyse serbest. Tek görünüm yetmiyordu (ölçüldü 2026-09-24): (a) tek başına `-- /*` … `-- */` sarmalına karşı
güvenliydi ama `--` içindeki `;` BDEF başlığını erken bitirip `--` içindeki YEM Z arayüzünü topluyordu → `[]`.
Güvenlik iddiası iki SAP davranışının (b)/(c) doğru modellenmesine dayanır; SAP'nin gerçek davranışı ölçülmedi.
Bilinen yanlış pozitifler: `--` satırında standart hedefli genişletme metni geçerse red ((a)/(c) görür; bitişik
`--extend` yazılışı dahil — Z117ⓔ N3) · BDEF başlığında `;` `using interface`'ten ÖNCE bir `--` içindeyse `?`
((a)/(c) görünümünde başlık o `;`'da biter; (c) modelinde başlık gerçekten arayüzsüzdür ⇒ düşürülmez — Z117ⓒ,
testle sabitlendi).
BDEF başlık çapası (Z117ⓐ): başlık `^` + boşluk/`--` satırlarına bağlıdır; `\\s` sayılmayan baş karakteri (çift BOM,
ZWSP, NUL, WJ…) çapayı kırıyordu → `[]`. SAP'nin bu önekleri kabul edip etmediği DOĞRULANMADI ⇒ kaynağın İLK SÖZCÜĞÜ
`EXTENSION` olup çapalı başlık eşleşmezse `?` (fail-closed; hedef çözülmeye çalışılmaz). Sınır: önek bir SÖZCÜK ise
(`x extension …`) tetiklenmez (SAP'de sözdizimi hatası olduğu varsayılır — DOĞRULANMADI).
ABAP kaynak tipleri (class, program, include, function…) taranmaz: ABAP dilinde standart DDIC/CDS objesini
kaynaktan genişleten ifade yoktur; ENHO yazan araç yoktur.
"""
from __future__ import annotations

import bisect
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
# SAP'nin CDS/BDL'de `--`'yı yorum sayıp saymadığı DOĞRULANMADI ⇒ kaynak ÜÇ görünümde (× iki dize modeli) taranır,
# bulgular BİRLEŞİR:
#   (a) `--` satırı TÜKETİLİR ama SİLİNMEZ (içindeki `/*` blok açmaz, metni taranır) — en geniş görünüm
#   (b) `--` satır yorumudur → içeriği boşaltılır            (SAP yorum sayıyorsa gerçek kod budur)
#   (c) `--` özel değildir → içindeki `/*`, `//`, `'` normal işler (SAP yorum saymıyorsa gerçek kod budur)
# Tek görünüm kördü (bug gate 2026-09-24): (a)'da `--` içindeki `;` BDEF başlığını erken bitiriyor, `--` içindeki
# yem Z arayüzü toplanıyor, gerçek standart arayüz görünmüyordu → `[]`.
# Her görünüm iki dize modeliyle üretilir (Z117ⓔ): `''` kaçışı (taban) · ters bölü kaçışı (`\'` dizeyi KAPATMAZ).
_DIZE = r"'(?:[^'\n]|'')*'?"
_DIZE_TERS = r"'(?:[^'\\\n]|\\[^\n]|'')*'?"
_YORUM = r"/\*.*?(?:\*/|\Z)|//[^\n]*"
_YORUM_DIZE = re.compile(rf"{_DIZE}|{_YORUM}|--[^\n]*", re.S)
_YORUM_DIZE_KOD = re.compile(rf"{_DIZE}|{_YORUM}", re.S)
_YORUM_DIZE_T = re.compile(rf"{_DIZE_TERS}|{_YORUM}|--[^\n]*", re.S)
_YORUM_DIZE_KOD_T = re.compile(rf"{_DIZE_TERS}|{_YORUM}", re.S)


def _bosalt(m: re.Match) -> str:
    metin = m.group(0)
    if metin.startswith("--"):
        return metin                                     # (a): tüketildi, silinmedi (bkz. modül notu)
    return re.sub(r"[^\n]", " ", metin)


def _bosalt_tumu(m: re.Match) -> str:
    return re.sub(r"[^\n]", " ", m.group(0))


def _gorunumler(kaynak: str) -> tuple[str, ...]:
    """(a), (b), (c) görünümleri × iki dize modeli (`''` · ters bölü) — aynı uzunlukta (konum ve satır numaraları
    hizalı). Baştaki TEK BOM (U+FEFF) atılır: `\\s` onu boşluk saymaz ⇒ BDEF başlığının `^` çapası BOM'lu kaynakta
    eşleşmiyordu (ölçüldü 2026-09-24: `[]`). Diğer baş karakterleri: `_capasiz_extension` (Z117ⓐ)."""
    src = kaynak.replace("\r\n", "\n").replace("\r", "\n")
    if src.startswith("\ufeff"):
        src = src[1:]
    return (_YORUM_DIZE.sub(_bosalt, src), _YORUM_DIZE.sub(_bosalt_tumu, src),
            _YORUM_DIZE_KOD.sub(_bosalt_tumu, src),
            _YORUM_DIZE_T.sub(_bosalt, src), _YORUM_DIZE_T.sub(_bosalt_tumu, src),
            _YORUM_DIZE_KOD_T.sub(_bosalt_tumu, src))


_AD = r"(?:/[A-Z0-9_]+/)?[A-Z_][A-Z0-9_]*"
_F = re.I
# Önündeki TEK `-` sözcüğü bağlar (`a-extend` genişletme değil); `--extend` ise `--` satırının içeriğidir ve (a)/(c)
# görünümünde `-- extend` gibi taranır (Z117ⓔ N3: bitişik yazılış `[]` veriyordu, boşluklusu red).
_ANAHTAR = re.compile(r"(?<![\w/$#@.:])(?:(?<=--)|(?<!-))(?P<kw>EXTEND|ANNOTATE)(?![\w/])", _F)
_DDL_BICIM = r"VIEW|ENTITY|CUSTOM|ABSTRACT|TYPE|PROJECTION|HIERARCHY|TABLE|STRUCTURE|ASPECT"
_R_EXTEND = re.compile(rf"EXTEND\s+(?P<ara>(?:(?:{_DDL_BICIM})\s+)*)(?P<tgt>{_AD})\s+WITH\b", _F)
# Z117ⓑ: tip bilinmezken BDEF algılanınca düşürülebilecek TEK `?` biçimi — `EXTEND` ardından DDL biçim sözcüğü
# OLMAYAN bir sözcük (BDEF gövdesi: `extend behavior for` · `extend draft determine action` …). `EXTEND view…`,
# `EXTEND }`, `EXTEND "…"` ve her ANNOTATE `?`'i KALIR.
_R_EXTEND_BDEF_ICI = re.compile(rf"EXTEND\s+(?!(?:{_DDL_BICIM})(?![\w/]))[A-Z_]", _F)
_R_ANNOTATE = re.compile(rf"ANNOTATE\s+(?P<ara>(?:VIEW|ENTITY)\s+)(?P<tgt>{_AD})\s+WITH\b", _F)
# Baştaki `--` satırları atlanır ((a)/(c) görünümünde SİLİNMEZLER): `--` SAP'de yorumsa başlık onlardan sonradır.
# Her tekrar `\n` ile biter ⇒ bölüştürme tek yollu (geri izleme patlaması yok).
_R_BDEF_BASLIK = re.compile(r"^(?:[ \t\n]*--[^\n]*\n)*\s*(?P<bas>EXTENSION\b(?P<govde>[^;]*);?)", _F)
_R_BDEF_ARAYUZ = re.compile(rf"\bUSING\s+INTERFACE\s+(?P<tgt>{_AD})(?![\w/])", _F)
_R_EXTEND_BEHAVIOR = re.compile(rf"(?<![\w/])EXTEND\s+BEHAVIOR\s+FOR\s+(?P<tgt>{_AD})", _F)
# Z117ⓐ: kaynağın İLK SÖZCÜĞÜ. Atlanan: sözcük olmayan karakterler (ZWSP, NUL, ikinci BOM, noktalama…), tek `-`,
# `--` satırı. Seçenekler birbirini DIŞLAMAZ: `--[^\n]*` satırın ortasında durup kalan `--…`'yı yeni bir tekrara
# bırakabilir ⇒ sözcüksüz tire dizisinde geri izleme ÜSTELDİ (ölçüldü 2026-09-26: `tara('-'*38, 'bdef')` 32 sn;
# 24/28/30 tire → 0,017/0,105/0,276 sn). Çare: sahiplenici niceleyiciler (`*+`, Python ≥ 3.11; CI tabanı 3.12) — her
# `--` satırın sonuna kadar yer ve tekrar dizisi geri verilmez ⇒ doğrusal. Sonuç değişmez: açgözlü geçiş bir sözcükte
# duruyorsa iki sürüm aynı eşleşmeyi verir; durmuyorsa (yalnız `--` içinde sözcük var) eski sürüm yorumun SON
# sözcüğünün son harf(ler)ini bulurdu — `EXTENSION` olamaz ⇒ `_capasiz_extension` iki sürümde de None.
_R_ILK_SOZCUK = re.compile(r"(?:[^\w\-]|-(?!-)|--[^\n]*+)*+(?P<soz>\w+)")


def _capasiz_extension(temiz: str) -> int | None:
    """İlk sözcük `EXTENSION` ise konumu, değilse None (çapalı başlık eşleşmediğinde çağrılır)."""
    m = _R_ILK_SOZCUK.match(temiz)
    return m.start("soz") if m and m.group("soz").upper() == "EXTENSION" else None


class _SatirDizini:
    """Konum → satır no, `bisect` ile O(log n) (Z117ⓓ). Önceki `metin.count("\\n", 0, konum)` her bulguda baştan
    sayıyordu: O(k·n) — 100k satır + 2000 EXTEND 14,2 sn (ölçüldü 2026-09-26). Görünümler satır sonlarını korur ⇒
    bir görünümün dizini hepsi için geçerlidir."""

    def __init__(self, metin: str):
        self._nl = [m.start() for m in re.finditer("\n", metin)]

    def __call__(self, konum: int) -> int:
        return bisect.bisect_left(self._nl, konum) + 1


def _satir(metin: str, konum: int) -> int:
    """Tek seferlik çağrı (TABL XML); döngüde `_SatirDizini` kullanılır."""
    return metin.count("\n", 0, konum) + 1


def _gorunum(s: str, azami: int = 80) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= azami else s[: azami - 1] + "…"


def _ddl_bulgulari(gorunumler, satir_no, bdef_ici_atla: bool = False) -> list[Bulgu]:
    """Her görünümde her EXTEND/ANNOTATE sözcüğü. Görünümler konumca hizalı: aynı sözcükte HERHANGİ bir görünüm
    standart hedef çözerse o bulgu; hiçbiri standart çözmez ama biri çözemezse `?` (fail-closed); hepsi Z/Y → serbest.
    `bdef_ici_atla` (yalnız tip bilinmezken BDEF algılandıysa): `_R_EXTEND_BDEF_ICI` biçimindeki `?` üretilmez —
    BDEF gövdesinin kendi `extend <sözcük>` ifadeleri (DDL tarayıcısı onları çözemez). Başka hiçbir `?` düşmez."""
    std: dict[tuple[int, str], Bulgu] = {}
    belirsiz: dict[int, Bulgu] = {}
    for temiz in gorunumler:
        for m in _ANAHTAR.finditer(temiz):
            kw = m.group("kw").upper()
            rx = _R_EXTEND if kw == "EXTEND" else _R_ANNOTATE
            e = rx.match(temiz, m.start())
            if not e:
                if bdef_ici_atla and kw == "EXTEND" and _R_EXTEND_BDEF_ICI.match(temiz, m.start()):
                    continue
                parca = temiz[m.start(): m.start() + 80].split("\n", 2)
                belirsiz.setdefault(m.start(), Bulgu(
                    satir_no(m.start()), _gorunum(" ".join(parca[:2])), "?",
                    f"{kw} sözcüğü var ama hedef çözülemedi (tanınmayan biçim) — fail-closed"))
                continue
            hedef = e.group("tgt").upper()
            if not izinli(hedef):
                bicim = " ".join([kw.lower()] + e.group("ara").lower().split())
                std.setdefault((m.start(), hedef),
                               Bulgu(satir_no(m.start()), _gorunum(e.group(0)), hedef, f"{bicim} <standart obje>"))
    std_konum = {konum for konum, _h in std}
    return list(std.values()) + [b for konum, b in belirsiz.items() if konum not in std_konum]


def _bdef_bulgulari(gorunumler, satir_no) -> tuple[list[Bulgu], bool]:
    """→ (bulgular, BDEF genişletmesi algılandı mı). Başlık ve `using interface` HER görünümde ayrı çözülür, bulgular
    birleşir: herhangi bir görünümde standart arayüz → bulgu; standart yok ama algılayan bir görünümde arayüz
    çözülemedi ya da başlık çapasız (Z117ⓐ) → `?` (fail-closed); algılayan tüm görünümler yalnız Z/Y arayüz
    çözdüyse serbest."""
    std: dict[str, Bulgu] = {}
    belirsiz: Bulgu | None = None
    capasiz_belirsiz: Bulgu | None = None
    algilandi = False
    for temiz in gorunumler:
        baslik = _R_BDEF_BASLIK.match(temiz)
        capasiz = None if baslik else _capasiz_extension(temiz)
        davranis = _R_EXTEND_BEHAVIOR.search(temiz)
        if not baslik and capasiz is None and not davranis:
            continue                                     # bu görünümde BDEF genişletmesi yok (define behavior)
        algilandi = True
        if capasiz is not None:
            # Z117ⓐ: ilk sözcük EXTENSION ama önünde `\s` sayılmayan karakter var. SAP'nin bunu başlık sayıp
            # saymadığı DOĞRULANMADI ⇒ hedef çözülmeye çalışılmaz (Z arayüz görünse de) → `?`.
            if capasiz_belirsiz is None:
                capasiz_belirsiz = Bulgu(
                    satir_no(capasiz), _gorunum(temiz[capasiz: capasiz + 80].split("\n", 1)[0]), "?",
                    "BDEF başlığı `EXTENSION` önünde tanınmayan baş karakteri var (çift BOM / ZWSP / NUL …; SAP'nin "
                    "kabulü DOĞRULANMADI) — başlık çözülmedi, fail-closed")
            continue
        satir = satir_no(baslik.start("govde") if baslik else davranis.start())
        # HEPSİ denetlenir (ilki değil): (a) görünümünde ilk eşleşme bir `--` satırındaki Z adı olabilir.
        arayuzler = [a.group("tgt").upper() for a in _R_BDEF_ARAYUZ.finditer(baslik.group("govde"))] if baslik else []
        if not arayuzler:
            if belirsiz is None:
                ifade = _gorunum(baslik.group("bas")) if baslik else _gorunum(davranis.group(0))
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
    tek = capasiz_belirsiz or belirsiz
    return ([tek] if tek else []), algilandi


def tara(kaynak: str, object_type: str | None = None) -> list[Bulgu]:
    """Standart (Z/Y dışı) objeyi genişleten/değiştiren ifadeler. ABAP kaynak tipinde `[]`."""
    if not isinstance(kaynak, str):
        raise TypeError("kaynak metin (str) olmalı")
    kip = _kip(object_type)
    if kip == "abap":
        return []
    gorunumler = _gorunumler(kaynak)
    satir_no = _SatirDizini(gorunumler[0])
    if kip == "bdef":
        bulgular = _bdef_bulgulari(gorunumler, satir_no)[0]
    elif kip == "ddl":
        bulgular = _ddl_bulgulari(gorunumler, satir_no)
    else:
        # Tip bilinmiyor: BDEF genişletmesi algılanırsa BDEF kuralları + DDL taramasının bulguları. Tek-yollu karar
        # kördü (ölçüldü 2026-09-24): Z arayüzlü `extension` başlığı, arkasındaki `extend view entity <std>`'yi
        # `[]`'e gizliyordu. DDL `?`'lerinden YALNIZ BDEF gövdesinin kendi `extend <sözcük>` ifadeleri düşer
        # (`_R_EXTEND_BDEF_ICI`). Z117ⓑ: önceki hâl TÜM DDL `?`'lerini düşürüyordu (yorum yalnız `extend behavior`
        # diyordu) ⇒ gerçek çözülemeyen `extend }` / `extend view "…"` `[]`'e gidiyordu (ölçüldü 2026-09-26).
        bulgular, bdef_mi = _bdef_bulgulari(gorunumler, satir_no)
        ddl = _ddl_bulgulari(gorunumler, satir_no, bdef_ici_atla=bdef_mi)
        if bdef_mi:
            gorulen = {(b.satir, b.hedef) for b in bulgular}
            bulgular = bulgular + [b for b in ddl if (b.satir, b.hedef) not in gorulen]
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
