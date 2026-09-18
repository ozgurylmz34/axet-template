# -*- coding: utf-8 -*-
"""Kesin Yasak B kaynak tarayıcısı — standart tabloya DOĞRUDAN veritabanı yazımı.

Saf fonksiyon, ağ yok: `tara(kaynak, object_type) -> list[Bulgu]`.
Yazma kapısı (`gate.check_std_dml`) ve `tools/atom.py::adt_push_source` (ikinci katman) çağırır.
Kural tablosu + bilinen sınırlar: IMPLEMENTATION.md §12.

YAKLAŞIM — satır regex'i DEĞİL, küçük bir sözcük çözümleyici (lexer):
  1. Kaynak karakter karakter okunur; üç kip vardır:
       abap : `*` (1. sütun) ve `"` yorumları atılır; `'…'`, `` `…` `` ve `|…|` literalleri
              yer tutucuya çevrilir; ifade `.` ile biter.
       sql  : `EXEC SQL … ENDEXEC.` ve AMDP gövdesi (`METHOD … BY DATABASE PROCEDURE|FUNCTION`
              … `ENDMETHOD.`). `--` ve `/* */` yorumları + `'…'` literalleri atılır, `"…"`
              TANIMLAYICIDIR (korunur), ifade `;` ile biter.
  2. Her karakterin satır numarası taşınır → bulgu satırı ifadenin başladığı satırdır.
  3. ABAP zincir ifadeleri (`UPDATE: a SET …, b SET ….`) önek + parça olarak açılır.
  4. Eşleme kuralları ifade BAŞINA çapalıdır (abap) — `CALL FUNCTION 'X' IN UPDATE TASK`,
     `MODIFY ENTITIES … UPDATE FIELDS` gibi ifadelerde UPDATE başta olmadığı için eşleşmez.

⚠ `MODIFY|DELETE <ad> FROM <wa>` ve kısa biçimler (`MODIFY <ad>.`/`DELETE <ad>.`) hem iç tablo hem
veritabanı ifadesi olabilir. KARAR (bilinçli, IMPLEMENTATION.md §12.3):
  · kaynakta `<ad>` için iç tablo bildirimi varsa (DATA/STATICS/CLASS-DATA … TYPE TABLE OF |
    LIKE TABLE OF | TYPE <…_t|…_tt|tt_…> | OCCURS | WITH HEADER LINE | BEGIN OF <ad> OCCURS |
    INTO TABLE @DATA(<ad>)) → iç tablo (izinli);
  · değilse `TABLES <ad>` bildirimi varsa → veritabanı;
  · değilse ad değişken önekiyle (lt_, gt_, ls_, t_, it_, et_, ct_) başlıyorsa → iç tablo;
  · değilse → veritabanı.
Kaynak tek obje olduğu için bildirim BAŞKA bir include'da olabilir (TOP include) — o durumda
önek kuralı devreye girer; öneksiz iç tablo adı yanlış pozitif üretir (mesaj satırı gösterir).
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

__all__ = ["Bulgu", "tara", "abap_kaynagi_mi", "mesaj", "YONLENDIRME"]

YONLENDIRME = ("Standart tablo verisi yalnız şu sırayla değiştirilir: BAPI → RFC FM → işlem kodu (BDC) "
               "→ kullanıcıdan manuel. Doğrudan INSERT/UPDATE/DELETE/MODIFY Z'li program içinde de yasaktır.")


@dataclass(frozen=True)
class Bulgu:
    satir: int
    ifade: str
    hedef: str
    neden: str

    def as_dict(self) -> dict:
        return asdict(self)


# ── hangi tipler ABAP kaynağı? ─────────────────────────────────────────────────────────────
# `lib/object_types.py`'den TÜRETİLİR: kanonik tipin `file_extension`'ı `.abap` ile bitiyorsa
# (class, interface, program, include, functiongroup, function) ya da tip bir sınıf alt-include'uysa
# (ccau/ccimp/ccdef/ccmac — hepsi `.abap`) ABAP'tır. DDIC/CDS/DDLX/DCL/SRVD/package değildir.
# object_types'ın TANIMADIĞI ama DML içeremeyen kaynak tipleri (BDEF, SRVB, mesaj sınıfı, kilit
# objesi) aşağıda açıkça listelenir. Bunların dışında TANINMAYAN tip → TARANIR (fail-closed).
_ABAP_OLMAYAN_EK = frozenset({
    "bdef", "behaviordefinition", "srvb", "servicebinding", "msag", "messageclass",
    "enqu", "lock", "lockobject", "lockobjects",
})


def abap_kaynagi_mi(object_type) -> bool:
    if object_type is None or not str(object_type).strip():
        return True
    t = str(object_type).strip().lower()
    if t in _ABAP_OLMAYAN_EK:
        return False
    try:
        import object_types as _ot  # type: ignore  (sapadt import'u lib/'i sys.path'e ekler)
    except Exception:  # noqa: BLE001 — tip tablosu yoksa tara (fail-closed)
        return True
    if _ot.is_class_include(t):
        return True
    try:
        kanonik = _ot.normalize_object_type(t)
    except ValueError:
        return True
    return str(_ot.OBJECT_TYPES.get(kanonik, {}).get("file_extension") or "").endswith(".abap")


# ── lexer ────────────────────────────────────────────────────────────────────────────────
_LIT = "\x00"  # yer tutucu sınırlayıcı: \x00<n>\x00  (n = literal indeksi)
_AMDP_BAS = re.compile(r"^METHOD\s+\S+\s+BY\s+DATABASE\s+(?:PROCEDURE|FUNCTION)\b", re.I)
_EXEC_BAS = re.compile(r"^EXEC\s+SQL\b", re.I)
_SON_AMDP = re.compile(r"ENDMETHOD\s*\.", re.I)
_SON_EXEC = re.compile(r"ENDEXEC\s*\.", re.I)


class _Ifade:
    __slots__ = ("kip", "metin", "satirlar")

    def __init__(self, kip: str, metin: str, satirlar: list[int]):
        self.kip, self.metin, self.satirlar = kip, metin, satirlar


def _parcala(kaynak: str) -> tuple[list[_Ifade], list[str]]:
    src = kaynak.replace("\r\n", "\n").replace("\r", "\n")
    n = len(src)
    ifadeler: list[_Ifade] = []
    literaller: list[str] = []
    buf: list[str] = []
    sat: list[int] = []
    satir = 1
    kip = "abap"
    son_rx = None

    def ekle(s: str, no: int) -> None:
        buf.extend(s)
        sat.extend([no] * len(s))

    def literal(icerik: str, no: int) -> None:
        literaller.append(icerik)
        ekle(f" {_LIT}{len(literaller) - 1}{_LIT} ", no)

    def bosalt(k: str) -> str:
        metin = "".join(buf)
        bas = len(metin) - len(metin.lstrip())
        son = len(metin.rstrip())
        if son > bas:
            ifadeler.append(_Ifade(k, metin[bas:son], sat[bas:son]))
            sonuc = metin[bas:son]
        else:
            sonuc = ""
        buf.clear()
        sat.clear()
        return sonuc

    def satir_sonuna(j: int) -> int:
        k = src.find("\n", j)
        return n if k < 0 else k

    i = 0
    while i < n:
        ch = src[i]
        bol = i == 0 or src[i - 1] == "\n"
        if ch == "\n":
            ekle(" ", satir)
            satir += 1
            i += 1
            continue
        if bol and ch == "*":                       # ABAP tam-satır yorumu (1. sütun) — her kipte
            i = satir_sonuna(i)
            continue
        if kip == "abap":
            if ch == '"':
                i = satir_sonuna(i)
                continue
            if ch in "'`":
                j, parca = i + 1, []
                while j < n and src[j] != "\n":
                    if src[j] == ch:
                        if j + 1 < n and src[j + 1] == ch:
                            parca.append(ch)
                            j += 2
                            continue
                        break
                    parca.append(src[j])
                    j += 1
                literal("".join(parca), satir)
                i = j + 1 if j < n and src[j] == ch else j
                continue
            if ch == "|":
                j, derinlik = i + 1, 0
                while j < n:
                    c = src[j]
                    if derinlik == 0:
                        if c == "\\":
                            j += 2
                            continue
                        if c == "|" or c == "\n":
                            break
                        if c == "{":
                            derinlik = 1
                    else:
                        if c == "\n":
                            satir += 1
                        elif c == "{":
                            derinlik += 1
                        elif c == "}":
                            derinlik -= 1
                    j += 1
                literal("", satir)
                i = j + 1 if j < n and src[j] == "|" else j
                continue
            if ch == ".":
                metin = bosalt("abap")
                if _AMDP_BAS.match(metin):
                    kip, son_rx = "sql", _SON_AMDP
                elif _EXEC_BAS.match(metin):
                    kip, son_rx = "sql", _SON_EXEC
                i += 1
                continue
            ekle(ch, satir)
            i += 1
            continue
        # ── sql kipi ──
        if (ch in "Ee") and (i == 0 or not (src[i - 1].isalnum() or src[i - 1] in '_"/')):
            m = son_rx.match(src, i) if son_rx else None
            if m:
                bosalt("sql")
                kip, son_rx = "abap", None
                i = m.end()
                continue
        if ch == "-" and i + 1 < n and src[i + 1] == "-":
            i = satir_sonuna(i)
            continue
        if ch == "/" and i + 1 < n and src[i + 1] == "*":
            k = src.find("*/", i + 2)
            k = n if k < 0 else k + 2
            satir += src.count("\n", i, k)
            ekle(" ", satir)
            i = k
            continue
        if ch == "'":
            j, parca = i + 1, []
            while j < n and src[j] != "\n":
                if src[j] == "'":
                    if j + 1 < n and src[j + 1] == "'":
                        parca.append("'")
                        j += 2
                        continue
                    break
                parca.append(src[j])
                j += 1
            literal("".join(parca), satir)
            i = j + 1 if j < n and src[j] == "'" else j
            continue
        if ch == '"':
            k = i + 1
            while k < n and src[k] not in '"\n':
                k += 1
            parca = src[i:k + 1] if k < n and src[k] == '"' else src[i:k]
            ekle(parca, satir)
            i = i + len(parca)
            continue
        if ch == ";":
            bosalt("sql")
            i += 1
            continue
        ekle(ch, satir)
        i += 1
    bosalt(kip)
    return ifadeler, literaller


def _zincir_ac(ifade: _Ifade) -> list[_Ifade]:
    """`ANAHTAR: p1, p2.` → `ANAHTAR p1` · `ANAHTAR p2` (parantez/köşeli ayraç dışı ayraçlar)."""
    metin = ifade.metin
    derinlik = 0
    iki_nokta = -1
    for k, c in enumerate(metin):
        if c in "([":
            derinlik += 1
        elif c in ")]":
            derinlik = max(0, derinlik - 1)
        elif c == ":" and derinlik == 0:
            iki_nokta = k
            break
    if iki_nokta < 0:
        return [ifade]
    onek = metin[:iki_nokta].strip()
    parcalar: list[tuple[int, int]] = []
    derinlik, bas = 0, iki_nokta + 1
    for k in range(iki_nokta + 1, len(metin)):
        c = metin[k]
        if c in "([":
            derinlik += 1
        elif c in ")]":
            derinlik = max(0, derinlik - 1)
        elif c == "," and derinlik == 0:
            parcalar.append((bas, k))
            bas = k + 1
    parcalar.append((bas, len(metin)))
    out = []
    for b, s in parcalar:
        parca = metin[b:s]
        if not parca.strip():
            continue
        ofset = b + (len(parca) - len(parca.lstrip()))
        yeni = f"{onek} {parca.strip()}"
        satir = ifade.satirlar[min(ofset, len(ifade.satirlar) - 1)]
        out.append(_Ifade(ifade.kip, yeni, [satir] * len(yeni)))
    return out


# ── ABAP kuralları ──────────────────────────────────────────────────────────────────────
_AD = r"(?:/[A-Z0-9_]+/)?[A-Z_][A-Z0-9_]*"
_DIN = r"\(\s*[^()\s]+\s*\)"
_HEDEF = rf"(?P<tgt>{_AD}|{_DIN})(?=\s|$)"
_EK = r"(?:\s+(?:CLIENT\s+SPECIFIED|USING\s+(?:ALL\s+CLIENTS|CLIENTS\s+IN\s+\S+|CLIENT\s+\S+)|CONNECTION\s+\S+))*"
_F = re.I

_R_INSERT_VALUES = re.compile(rf"^INSERT\s+INTO\s+{_HEDEF}{_EK}\s+VALUES\b", _F)
_R_INSERT_FROM = re.compile(rf"^INSERT\s+{_HEDEF}{_EK}\s+FROM\s", _F)
_R_UPDATE = re.compile(rf"^UPDATE\s+{_HEDEF}{_EK}(?:\s+(?P<kw>SET|FROM)\b|\s*$)", _F)
_R_MODIFY_FROM = re.compile(rf"^MODIFY\s+{_HEDEF}{_EK}\s+FROM\s+(?P<table>TABLE\s+)?(?P<rest>.*)$", _F)
_R_MODIFY_KISA = re.compile(rf"^MODIFY\s+{_HEDEF}{_EK}\s*$", _F)
_R_DELETE_FROM_DB = re.compile(rf"^DELETE\s+FROM\s+(?!(?:MEMORY|SHARED|DATABASE)\b){_HEDEF}", _F)
_R_DELETE_WA = re.compile(rf"^DELETE\s+{_HEDEF}{_EK}\s+FROM\s+(?P<table>TABLE\s+)?(?P<rest>.*)$", _F)
_R_DELETE_KISA = re.compile(rf"^DELETE\s+{_HEDEF}{_EK}\s*$", _F)

_MODIFY_DISI = frozenset({"TABLE", "ENTITIES", "ENTITY", "LINE", "CURRENT", "SCREEN"})
_DELETE_DISI = frozenset({"TABLE", "ADJACENT", "DATASET", "REPORT", "TEXTPOOL", "FROM"})
_ITAB_BELIRTEC = re.compile(r"\b(?:INDEX|TRANSPORTING|USING\s+KEY)\b", _F)
_ITAB_ARALIK = re.compile(r"\b(?:TO|WHERE|USING\s+KEY)\b", _F)
_DEGISKEN_ONEKI = ("LT_", "GT_", "LS_", "T_", "IT_", "ET_", "CT_")

_BILDIRIM_ITAB = re.compile(
    rf"^(?:DATA|STATICS|CLASS-DATA)\s+(?P<ad>{_AD})\s+(?:"
    r"TYPE\s+(?:STANDARD\s+|SORTED\s+|HASHED\s+)?TABLE\s+OF\b"
    r"|LIKE\s+(?:STANDARD\s+|SORTED\s+|HASHED\s+)?TABLE\s+OF\b"
    r"|TYPE\s+(?:\S+=>)?(?:TT_\S+|\S*?_TT?)(?=\s|$)"
    r"|.*\bOCCURS\b|.*\bWITH\s+HEADER\s+LINE\b)", _F)
_BILDIRIM_BEGIN_OCCURS = re.compile(rf"^(?:DATA|STATICS|CLASS-DATA)\s+BEGIN\s+OF\s+(?P<ad>{_AD})\s+OCCURS\b", _F)
_BILDIRIM_INLINE_TABLE = re.compile(rf"\bINTO\s+(?:CORRESPONDING\s+FIELDS\s+OF\s+)?TABLE\s+@?DATA\(\s*(?P<ad>{_AD})\s*\)", _F)
_BILDIRIM_TABLES = re.compile(rf"^TABLES\s+\*?(?P<ad>{_AD})(?=\s|$)", _F)


def _gorunum(metin: str, literaller: list[str], azami: int = 90) -> str:
    s = re.sub(rf"\s*{_LIT}(\d+){_LIT}\s*", lambda m: " '…' ", metin)
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= azami else s[: azami - 1] + "…"


def _hedef_coz(tgt: str, literaller: list[str]) -> tuple[str, bool]:
    """(hedef_adi, dinamik_mi). `('ZTAB')` gibi literal içeren dinamik ad çözülür."""
    t = tgt.strip()
    if t.startswith("("):
        ic = t[1:-1].strip()
        m = re.fullmatch(rf"{_LIT}(\d+){_LIT}", ic)
        if m and int(m.group(1)) < len(literaller):
            return literaller[int(m.group(1))].strip().upper(), False
        return t, True
    return t.upper(), False


def _izinli(hedef: str) -> bool:
    """Z/Y öneki ya da /Z…/ · /Y…/ müşteri namespace'i. Başka `/NS/` bilinemez → yasaklı."""
    h = hedef.strip().upper()
    if h[:1] in ("Z", "Y"):
        return True
    m = re.match(r"^/([A-Z0-9_]+)/", h)
    return bool(m and m.group(1)[:1] in ("Z", "Y"))


def _bildirimler(ifadeler: list[_Ifade]) -> tuple[set[str], set[str]]:
    itab, tables = set(), set()
    for ifd in ifadeler:
        m = _BILDIRIM_ITAB.match(ifd.metin) or _BILDIRIM_BEGIN_OCCURS.match(ifd.metin)
        if m:
            itab.add(m.group("ad").upper())
        for m in _BILDIRIM_INLINE_TABLE.finditer(ifd.metin):
            itab.add(m.group("ad").upper())
        m = _BILDIRIM_TABLES.match(ifd.metin)
        if m:
            tables.add(m.group("ad").upper())
    return itab, tables


def _belirsiz_db_mi(ad: str, itab: set[str], tables: set[str]) -> tuple[bool, str]:
    u = ad.upper()
    if u in itab:
        return False, "iç tablo bildirimi var"
    if u in tables:
        return True, f"TABLES {u} bildirimi var"
    if u.startswith(_DEGISKEN_ONEKI):
        return False, "değişken öneki"
    return True, "iç tablo bildirimi yok, değişken öneki yok"


def _abap_bulgu(ifd: _Ifade, literaller, itab, tables) -> tuple[str, str, bool] | None:
    """(hedef, neden, dinamik) ya da None."""
    s = re.sub(r"\s+", " ", ifd.metin).strip()
    m = _R_INSERT_VALUES.match(s)
    if m:
        h, d = _hedef_coz(m.group("tgt"), literaller)
        return h, "INSERT INTO <tablo> VALUES", d
    m = _R_INSERT_FROM.match(s)
    if m:
        h, d = _hedef_coz(m.group("tgt"), literaller)
        return h, "INSERT <tablo> FROM", d
    m = _R_UPDATE.match(s)
    if m:
        h, d = _hedef_coz(m.group("tgt"), literaller)
        kw = (m.group("kw") or "").upper()
        return h, (f"UPDATE <tablo> {kw}" if kw else "UPDATE <tablo> (kısa biçim, TABLES iş alanı)"), d
    m = _R_MODIFY_FROM.match(s)
    if m and m.group("tgt").upper() not in _MODIFY_DISI:
        if _ITAB_BELIRTEC.search(m.group("rest")):
            return None
        h, d = _hedef_coz(m.group("tgt"), literaller)
        if d:
            return h, "MODIFY <tablo> FROM", d
        if m.group("tgt").startswith("("):          # literal ile verilmiş ad — iç tablo olamaz
            return h, "MODIFY (<literal ad>) FROM", d
        if m.group("table"):
            return h, "MODIFY <tablo> FROM TABLE", d
        db, gerekce = _belirsiz_db_mi(h, itab, tables)
        return (h, f"MODIFY <ad> FROM <wa> — veritabanı sayıldı ({gerekce})", d) if db else None
    m = _R_MODIFY_KISA.match(s)
    if m and m.group("tgt").upper() not in _MODIFY_DISI:
        h, d = _hedef_coz(m.group("tgt"), literaller)
        if d:
            return h, "MODIFY <tablo> (kısa biçim)", d
        db, gerekce = _belirsiz_db_mi(h, itab, tables)
        return (h, f"MODIFY <ad> (kısa biçim) — veritabanı sayıldı ({gerekce})", d) if db else None
    m = _R_DELETE_FROM_DB.match(s)
    if m:
        h, d = _hedef_coz(m.group("tgt"), literaller)
        return h, "DELETE FROM <tablo>", d
    m = _R_DELETE_WA.match(s)
    if m and m.group("tgt").upper() not in _DELETE_DISI:
        rest = m.group("rest").strip()
        h, d = _hedef_coz(m.group("tgt"), literaller)
        if m.group("table"):
            return h, "DELETE <tablo> FROM TABLE", d
        if _ITAB_ARALIK.search(rest) or re.match(r"^\d+(?:\s|$)", rest):
            return None
        if d:
            return h, "DELETE <tablo> FROM", d
        if m.group("tgt").startswith("("):
            return h, "DELETE (<literal ad>) FROM", d
        db, gerekce = _belirsiz_db_mi(h, itab, tables)
        return (h, f"DELETE <ad> FROM <wa> — veritabanı sayıldı ({gerekce})", d) if db else None
    m = _R_DELETE_KISA.match(s)
    if m and m.group("tgt").upper() not in _DELETE_DISI:
        h, d = _hedef_coz(m.group("tgt"), literaller)
        if d:
            return h, "DELETE <tablo> (kısa biçim)", d
        db, gerekce = _belirsiz_db_mi(h, itab, tables)
        return (h, f"DELETE <ad> (kısa biçim) — veritabanı sayıldı ({gerekce})", d) if db else None
    return None


# ── SQL kuralları (EXEC SQL + AMDP) ─────────────────────────────────────────────────────
_SQL_ID = r'(?:"[^"]+"|[A-Za-z_/][\w/$#]*)'
_SQL_HEDEF = rf"(?P<tgt>:?{_SQL_ID}(?:\s*\.\s*{_SQL_ID})*)"
_SQL_KURALLAR = (
    (re.compile(rf"(?<![\w\"])INSERT\s+INTO\s+{_SQL_HEDEF}", _F), "SQL INSERT INTO"),
    (re.compile(rf"(?<![\w\"])UPDATE\s+{_SQL_HEDEF}(?:\s+(?:AS\s+)?(?!SET\b)[A-Za-z_]\w*)?\s+SET\b", _F), "SQL UPDATE … SET"),
    (re.compile(rf"(?<![\w\"])DELETE\s+(?:HISTORY\s+)?FROM\s+{_SQL_HEDEF}", _F), "SQL DELETE FROM"),
    (re.compile(rf"(?<![\w\"])MERGE\s+INTO\s+{_SQL_HEDEF}", _F), "SQL MERGE INTO"),
    (re.compile(rf"(?<![\w\"])UPSERT\s+{_SQL_HEDEF}", _F), "SQL UPSERT"),
    (re.compile(rf"(?<![\w\"])REPLACE\s+{_SQL_HEDEF}(?=\s*(?:\(|VALUES\b|SELECT\b|WITH\b|$))", _F), "SQL REPLACE"),
    (re.compile(rf"(?<![\w\"])TRUNCATE\s+TABLE\s+{_SQL_HEDEF}", _F), "SQL TRUNCATE TABLE"),
)


def _sql_hedef_adi(tgt: str) -> str:
    son = re.split(r'\s*\.\s*(?=(?:"|[A-Za-z_/]))', tgt.strip())[-1]
    return son.strip().strip('"').upper()


# ── ana fonksiyon ───────────────────────────────────────────────────────────────────────

def tara(kaynak: str, object_type: str | None = None) -> list[Bulgu]:
    """Standart (Z/Y dışı) tabloya doğrudan DB yazımı bulguları. ABAP kaynağı değilse `[]`."""
    if not isinstance(kaynak, str):
        raise TypeError("kaynak metin (str) olmalı")
    if not abap_kaynagi_mi(object_type):
        return []
    ham, literaller = _parcala(kaynak)
    abap: list[_Ifade] = []
    sql: list[_Ifade] = []
    for ifd in ham:
        if ifd.kip == "abap":
            abap.extend(_zincir_ac(ifd))
        else:
            sql.append(ifd)
    itab, tables = _bildirimler(abap)
    bulgular: list[Bulgu] = []
    for ifd in abap:
        sonuc = _abap_bulgu(ifd, literaller, itab, tables)
        if not sonuc:
            continue
        hedef, neden, dinamik = sonuc
        if dinamik:
            bulgular.append(Bulgu(ifd.satirlar[0], _gorunum(ifd.metin, literaller), hedef,
                                  f"{neden} — dinamik tablo adı (hedef derleme anında bilinemez)"))
        elif not _izinli(hedef):
            bulgular.append(Bulgu(ifd.satirlar[0], _gorunum(ifd.metin, literaller), hedef, neden))
    for ifd in sql:
        for rx, neden in _SQL_KURALLAR:
            for m in rx.finditer(ifd.metin):
                tgt = m.group("tgt")
                if tgt.startswith(":"):          # SQLScript tablo değişkeni — veritabanı değil
                    continue
                hedef = _sql_hedef_adi(tgt)
                if _izinli(hedef):
                    continue
                satir = ifd.satirlar[min(m.start(), len(ifd.satirlar) - 1)]
                parca = ifd.metin[m.start():]
                bulgular.append(Bulgu(satir, _gorunum(parca, literaller), hedef,
                                      f"{neden} (EXEC SQL / AMDP gövdesi)"))
    bulgular.sort(key=lambda b: (b.satir, b.hedef))
    return bulgular


def mesaj(bulgular: list[Bulgu], azami: int = 5) -> str:
    satirlar = [f"satır {b.satir}: {b.ifade} → hedef {b.hedef} ({b.neden})" for b in bulgular[:azami]]
    ek = f" (+{len(bulgular) - azami} bulgu daha)" if len(bulgular) > azami else ""
    return (f"Kesin Yasak B: standart tabloya doğrudan veritabanı yazımı — {len(bulgular)} bulgu{ek}. "
            + " · ".join(satirlar) + ". " + YONLENDIRME + " Kaynak SAP'ye gönderilmedi.")
