# -*- coding: utf-8 -*-
"""Tablo tipi (TTYP/DA) — TEK KAYNAK: ön kontrol + ADT XML'i + iki kanallı readback karşılaştırması (aXet 2026-09-21, Z40).

Kullananlar: `sapadt/tools/ddic.py::adt_ttyp_create` (yaratma + düzeltme PUT'u AYNI XML'i gönderir).

Değer eşlemeleri canlıda OKUNARAK ölçüldü (2026-09-21, DEV, yalnız okuma — aynı objenin ADT XML'i ile DD40L satırı
yan yana): standart hazır tip (dictionaryType + yapı satırı), yapı satırlı sıralı/anahtar bileşenli/tekil, yapı satırlı
hashed/satır-tipi anahtarlı/tekil, DTEL satırlı, ve 6 hazır ilkel tip (CHAR/NUMC/STRING/INT4/DEC/DATS). YAZMA biçimi
(POST/PUT gövdesi) standart anahtarlı yapı satırı dışında CANLI ÖLÇÜLMEDİ — ilk yaratım canlı ölçüm planındadır.

    XML accessType   ↔ DD40L ACCESSMODE : standard↔T · sorted↔S · hashed↔H
    XML definition   ↔ DD40L KEYDEF     : standard↔D · rowType↔T · keyComponents↔K
    XML kind         ↔ DD40L KEYKIND    : nonUnique↔N · unique↔U
    XML typeKind     ↔ DD40L ROWKIND    : dictionaryType↔S (yapı/tablo) ya da E (DTEL) · predefinedAbapType↔boş
    XML dataType     ↔ DD40L DATATYPE   : STRING↔STRG, diğerleri aynı (CHAR/NUMC/INT4/DEC/DATS)
Veride görülen tutarlılık (aynı ölçüm, tüm aktif DD40L): standard erişimde KEYKIND=U yok · hashed erişimde yalnız U.

Anahtar tanımı ↔ ABAP: DDIC "Standard key" (KEYDEF=D) = ABAP `WITH DEFAULT KEY` — `WITH EMPTY KEY` DEĞİL. `EMPTY KEY`
taşıyan aktüel, bu tipe TAM tipli bir FM parametresinden devredilirse çalışma zamanında CX_SY_DYN_CALL_ILLEGAL_TYPE.
"""
from __future__ import annotations

import re
from xml.sax.saxutils import escape as _xml_escape

ERISIM = {"standard": "T", "sorted": "S", "hashed": "H"}
ANAHTAR_TANIM = {"standard": "D", "rowType": "T", "keyComponents": "K"}
ANAHTAR_TUR = {"nonUnique": "N", "unique": "U"}
# İlkel tip → (uzunluk ister, ondalık ister, DD40L DATATYPE). Canlıda okunarak ölçülen 6 tip; başkası desteklenmez.
ILKEL_TIPLER = {
    "CHAR": (True, False, "CHAR"), "NUMC": (True, False, "NUMC"), "STRING": (False, False, "STRG"),
    "INT4": (False, False, "INT4"), "DEC": (True, True, "DEC"), "DATS": (False, False, "DATS"),
}
DESTEKLENMEYEN_SATIR = ("aralık tablosu (rangeTypeOnPredefinedType / rangeTypeOnDataelement)",
                        "referans satır (refToDictionaryType / refToPredefinedAbapType / refToClassOrInterfaceType)",
                        "tablo tipi satırı (iç içe tablo)", "boş/genel anahtar (notSpecified)", "ikincil anahtarlar")
_AD_RE = re.compile(r"^(/[A-Z0-9_]+/)?[A-Z][A-Z0-9_]*$")


def _att(v) -> str:
    return _xml_escape(str(v), {'"': "&quot;"})


def _bulgu(liste, kural, mesaj):
    liste.append({"rule": kural, "severity": "BLOCKER", "message": mesaj})


def ttyp_on_kontrol(row_type=None, builtin=None, access_type="standard", key_definition="standard",
                    key_kind=None, key_components=None) -> dict:
    """Ağ ÖNCESİ → {verdict, findings, spec, checked, not_checked}. `spec` normalize edilmiş tanımdır (XML bunu yazar)."""
    b: list[dict] = []
    spec: dict = {}
    if (row_type in (None, "")) == (builtin in (None, {}, "")):
        _bulgu(b, "Y1_satir_tipi", "Tam olarak BİRİ verilmeli: row_type (DDIC yapı/tablo/DTEL adı) YA DA builtin "
                                   "({\"data_type\":\"CHAR\",\"length\":10}).")
    elif row_type not in (None, ""):
        rt = str(row_type).strip().upper()
        if not _AD_RE.match(rt):
            _bulgu(b, "Y1_satir_tipi", f"row_type {row_type!r} geçerli bir DDIC adı değil.")
        spec.update(type_kind="dictionaryType", type_name=rt, data_type="", length=0, decimals=0)
    else:
        if not isinstance(builtin, dict):
            _bulgu(b, "Y1_satir_tipi", "builtin bir nesne olmalı: {\"data_type\":\"CHAR\",\"length\":10}.")
        else:
            fazla = sorted(set(builtin) - {"data_type", "length", "decimals"})
            dt = str(builtin.get("data_type") or "").strip().upper()
            if fazla:
                _bulgu(b, "Y1_satir_tipi", f"builtin tanınmayan alan: {', '.join(fazla)}.")
            if dt not in ILKEL_TIPLER:
                _bulgu(b, "Y2_ilkel_tip", f"builtin.data_type {dt or '(boş)'} desteklenmiyor — canlıda ölçülen: "
                                          f"{', '.join(ILKEL_TIPLER)}.")
            else:
                uz_ister, on_ister, _dd = ILKEL_TIPLER[dt]
                uz, on = builtin.get("length"), builtin.get("decimals", 0)
                if uz_ister and not (isinstance(uz, int) and not isinstance(uz, bool) and uz > 0):
                    _bulgu(b, "Y2_ilkel_tip", f"{dt} için length pozitif tamsayı olmalı (verilen: {uz!r}).")
                if not uz_ister and uz not in (None, 0):
                    _bulgu(b, "Y2_ilkel_tip", f"{dt} uzunluk almaz (verilen: {uz!r}).")
                if on_ister and not (isinstance(on, int) and not isinstance(on, bool) and on >= 0):
                    _bulgu(b, "Y2_ilkel_tip", f"{dt} için decimals 0 ya da pozitif tamsayı olmalı (verilen: {on!r}).")
                if not on_ister and on not in (None, 0):
                    _bulgu(b, "Y2_ilkel_tip", f"{dt} ondalık almaz (verilen: {on!r}).")
                spec.update(type_kind="predefinedAbapType", type_name="", data_type=dt,
                            length=uz if uz_ister and isinstance(uz, int) else 0,
                            decimals=on if on_ister and isinstance(on, int) else 0)
    if access_type not in ERISIM:
        _bulgu(b, "Y3_erisim", f"access_type {access_type!r} — geçerli: {', '.join(ERISIM)}.")
    if key_definition not in ANAHTAR_TANIM:
        _bulgu(b, "Y4_anahtar_tanimi", f"key_definition {key_definition!r} — geçerli: {', '.join(ANAHTAR_TANIM)} "
                                       "(boş/genel anahtar desteklenmez).")
    if key_kind is None:
        key_kind = "unique" if access_type == "hashed" else "nonUnique"
    if key_kind not in ANAHTAR_TUR:
        _bulgu(b, "Y5_anahtar_turu", f"key_kind {key_kind!r} — geçerli: {', '.join(ANAHTAR_TUR)}.")
    if access_type == "standard" and key_kind == "unique":
        _bulgu(b, "Y5_anahtar_turu", "standard tablo tekil (unique) anahtar alamaz — nonUnique ya da sorted/hashed.")
    if access_type == "hashed" and key_kind != "unique":
        _bulgu(b, "Y5_anahtar_turu", "hashed tablo yalnız tekil (unique) anahtarla tanımlanır.")
    bilesenler: list[str] = []
    if key_definition == "keyComponents":
        if not (isinstance(key_components, list) and key_components
                and all(isinstance(k, str) and re.match(r"^[A-Za-z][A-Za-z0-9_]*$", k.strip()) for k in key_components)):
            _bulgu(b, "Y6_anahtar_bilesenleri", "keyComponents için key_components boş olmayan alan adı listesi olmalı.")
        else:
            bilesenler = [k.strip().upper() for k in key_components]
        if spec.get("type_kind") == "predefinedAbapType":
            _bulgu(b, "Y6_anahtar_bilesenleri", "İlkel satır tipinde bileşen yok — keyComponents kullanılamaz.")
    elif key_components:
        _bulgu(b, "Y6_anahtar_bilesenleri", "key_components yalnız key_definition='keyComponents' ile verilir.")
    spec.update(access_type=access_type, key_definition=key_definition, key_kind=key_kind, key_components=bilesenler)
    return {"verdict": "BLOCKER" if b else "PASS", "findings": b, "spec": spec,
            "checked": ["Y1_satir_tipi", "Y2_ilkel_tip", "Y3_erisim", "Y4_anahtar_tanimi", "Y5_anahtar_turu",
                        "Y6_anahtar_bilesenleri"],
            "not_checked": ["satır tipinin SAP'de var/aktif olduğu (aktivasyon söyler)",
                            "anahtar bileşenlerinin satır tipinde bulunduğu (aktivasyon söyler)",
                            "tip adı uzunluğu", "açıklama uzunluğu (ADT'de sınır 60)"],
            "unsupported": list(DESTEKLENMEYEN_SATIR)}


def ttyp_xml(name: str, description: str, package: str, spec: dict) -> str:
    """POST (yaratma) ve düzeltme PUT'u için AYNI gövde. Varsayılan tanımda `tools/shells.py` ttyp reçetesiyle aynı."""
    dt = spec.get("data_type") or ""
    rowtype_dt = f"<ttyp:dataType>{_att(dt)}</ttyp:dataType>" if dt else "<ttyp:dataType/>"
    tn = spec.get("type_name") or ""
    tn_xml = f"<ttyp:typeName>{_att(tn)}</ttyp:typeName>" if tn else "<ttyp:typeName/>"
    if spec.get("key_components"):
        bil = ("<ttyp:components>" + "".join(f'<ttyp:component ttyp:name="{_att(k)}"/>' for k in spec["key_components"])
               + "</ttyp:components>")
    else:
        bil = "<ttyp:components/>"
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<ttyp:tableType xmlns:ttyp="http://www.sap.com/dictionary/tabletype"\n'
            '                xmlns:adtcore="http://www.sap.com/adt/core"\n'
            f'                adtcore:name="{_att(name.upper())}"\n'
            f'                adtcore:description="{_att(description)}">\n'
            f'    <adtcore:packageRef adtcore:name="{_att(package.upper())}"/>\n'
            '    <ttyp:rowType>\n'
            f'        <ttyp:typeKind>{_att(spec["type_kind"])}</ttyp:typeKind>\n'
            f'        {tn_xml}\n'
            f'        <ttyp:builtInType>{rowtype_dt}<ttyp:length>{int(spec.get("length") or 0):06d}</ttyp:length>'
            f'<ttyp:decimals>{int(spec.get("decimals") or 0):06d}</ttyp:decimals></ttyp:builtInType>\n'
            '        <ttyp:rangeType/>\n'
            '    </ttyp:rowType>\n'
            '    <ttyp:initialRowCount>00000</ttyp:initialRowCount>\n'
            f'    <ttyp:accessType>{_att(spec["access_type"])}</ttyp:accessType>\n'
            '    <ttyp:primaryKey>\n'
            f'        <ttyp:definition>{_att(spec["key_definition"])}</ttyp:definition>\n'
            f'        <ttyp:kind>{_att(spec["key_kind"])}</ttyp:kind>\n'
            f'        {bil}\n'
            '        <ttyp:alias/>\n'
            '    </ttyp:primaryKey>\n'
            '</ttyp:tableType>')


def _etiket(xml: str, ad: str) -> str | None:
    m = re.search(r"<ttyp:%s(?:\s[^>]*)?>([^<]*)</ttyp:%s>" % (ad, ad), xml or "")
    if m:
        return m.group(1).strip()
    return "" if re.search(r"<ttyp:%s(?:\s[^>]*)?/>" % ad, xml or "") else None


def ttyp_xml_oku(xml: str) -> dict:
    """ADT XML'inden satır tipi + erişim + anahtar. Bulunmayan etiket `None` (okunamadı), boş etiket ''."""
    blok = re.search(r"<ttyp:rowType>(.*?)</ttyp:rowType>", xml or "", re.S)
    satir = blok.group(1) if blok else ""
    pk = re.search(r"<ttyp:primaryKey(?:\s[^>]*)?>(.*?)</ttyp:primaryKey>", xml or "", re.S)
    pkm = pk.group(1) if pk else ""
    return {"type_kind": _etiket(satir, "typeKind") if blok else None,
            "type_name": _etiket(satir, "typeName") if blok else None,
            "data_type": _etiket(satir, "dataType") if blok else None,
            "length": _etiket(satir, "length") if blok else None,
            "decimals": _etiket(satir, "decimals") if blok else None,
            "access_type": _etiket(xml, "accessType"),
            "key_definition": _etiket(pkm, "definition") if pk else None,
            "key_kind": _etiket(pkm, "kind") if pk else None,
            "key_components": re.findall(r'<ttyp:component\s+ttyp:name="([^"]+)"', pkm)}


def dd40l_sorgusu(name: str) -> str:
    ad = str(name).upper().replace("'", "")
    return ("SELECT typename, rowtype, rowkind, datatype, leng, decimals, accessmode, keydef, keykind "
            f"FROM dd40l WHERE typename = '{ad}' AND as4local = 'A'")


def _bos(v) -> bool:
    return v is None or not str(v).strip()


def satir_tipi_bos_mu(xml_oku: dict | None, dd40l: dict | None, spec: dict) -> dict:
    """Her kanal için satır tipi DOLU mu → {'xml': True|False|None, 'dd40l': True|False|None} (None = ölçülemedi).

    Sözlük satır tipinde ölçü ROWTYPE/typeName; ilkel satır tipinde DATATYPE/dataType (ROWTYPE ilkelde boştur)."""
    ilkel = spec.get("type_kind") == "predefinedAbapType"
    x = None
    if xml_oku is not None:
        deger = xml_oku.get("data_type") if ilkel else xml_oku.get("type_name")
        x = None if deger is None else not _bos(deger)
    d = None
    if dd40l is not None:
        d = not _bos(dd40l.get("DATATYPE") if ilkel else dd40l.get("ROWTYPE"))
    return {"xml": x, "dd40l": d}


def dd40l_uyumsuzluklari(spec: dict, satir: dict) -> list[str]:
    """Beklenen tanım ↔ DD40L satırı. Boş liste = uyumlu. (Satır tipi BOŞLUĞU ayrıca `satir_tipi_bos_mu` ile ölçülür.)"""
    fark = []

    def es(alan, beklenen):
        canli = (satir.get(alan) or "").strip().upper()
        if canli != beklenen:
            fark.append(f"DD40L.{alan}={canli or '(boş)'} ≠ beklenen {beklenen or '(boş)'}")

    if spec.get("type_kind") == "dictionaryType":
        es("ROWTYPE", spec["type_name"])
        if (satir.get("ROWKIND") or "").strip().upper() not in ("S", "E"):
            fark.append(f"DD40L.ROWKIND={(satir.get('ROWKIND') or '(boş)')} ≠ beklenen S (yapı/tablo) ya da E (DTEL)")
    else:
        es("ROWTYPE", "")
        es("DATATYPE", ILKEL_TIPLER[spec["data_type"]][2])
        uz_ister, on_ister, _dd = ILKEL_TIPLER[spec["data_type"]]
        for alan, anahtar, ister in (("LENG", "length", uz_ister), ("DECIMALS", "decimals", on_ister)):
            if not ister:
                continue
            try:
                if int(satir.get(alan) or 0) != int(spec.get(anahtar) or 0):
                    fark.append(f"DD40L.{alan}={satir.get(alan)} ≠ beklenen {spec.get(anahtar)}")
            except ValueError:
                fark.append(f"DD40L.{alan} okunamadı: {satir.get(alan)!r}")
    es("ACCESSMODE", ERISIM[spec["access_type"]])
    es("KEYDEF", ANAHTAR_TANIM[spec["key_definition"]])
    es("KEYKIND", ANAHTAR_TUR[spec["key_kind"]])
    return fark


def xml_uyumsuzluklari(spec: dict, oku: dict) -> list[str]:
    fark = []
    for alan in ("access_type", "key_definition", "key_kind", "type_kind"):
        if (oku.get(alan) or "") != (spec.get(alan) or ""):
            fark.append(f"XML {alan}={oku.get(alan)!r} ≠ beklenen {spec.get(alan)!r}")
    if spec.get("type_kind") == "dictionaryType" and (oku.get("type_name") or "").upper() != spec["type_name"]:
        fark.append(f"XML typeName={oku.get('type_name')!r} ≠ beklenen {spec['type_name']!r}")
    if spec.get("type_kind") == "predefinedAbapType" and (oku.get("data_type") or "").upper() != spec["data_type"]:
        fark.append(f"XML dataType={oku.get('data_type')!r} ≠ beklenen {spec['data_type']!r}")
    if spec.get("type_kind") == "predefinedAbapType" and spec.get("data_type") in ILKEL_TIPLER:
        # Uzunluk/ondalık yalnız tip onu İSTİYORSA ve XML alanı SAYI olarak okunabildiyse kıyaslanır. Etiket yok /
        # boş / sayı değil = bu kanalda ÖLÇÜLEMEDİ → fark UYDURULMAZ (birincil ölçü DD40L; o kanal ayrıca kıyaslar).
        uz_ister, on_ister, _dd = ILKEL_TIPLER[spec["data_type"]]
        for anahtar, etiket, ister in (("length", "length", uz_ister), ("decimals", "decimals", on_ister)):
            deger = str(oku.get(anahtar) or "").strip()
            if ister and deger.isdigit() and int(deger) != int(spec.get(anahtar) or 0):
                fark.append(f"XML {etiket}={deger} ≠ beklenen {spec.get(anahtar)}")
    if spec.get("key_components") and [k.upper() for k in oku.get("key_components") or []] != spec["key_components"]:
        fark.append(f"XML anahtar bileşenleri {oku.get('key_components')} ≠ beklenen {spec['key_components']}")
    return fark
