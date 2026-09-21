# -*- coding: utf-8 -*-
"""Z tablo (TABL/DT) DDL'i — TEK KAYNAK: ön kontrol + render + alan sayımı (aXet 2026-09-21, Z38).

Kullananlar:
  · `sapadt/tools/ddic.py::adt_table_create` (ön kontrol → render → reviewer → yaz → readback)
  · `lib/sap_adt_lib.py::SAPADTClient.create_table_with_ddl` (SAP'ye PUT edilen metin BU render'dır)
  · `sapadt/_reviewer.py::run_reviewer_tablo` (denetlenen metin = yazılan metin)

Reçetenin kaynağı (kaynak çekirdekte canlı çözülmüş Z tablo yöntemi; bu depoda taşındı):
  1. DDL POST gövdesine KONMAZ — SAP gövdedeki DDL'i SESSİZCE yok sayar, varsayılan
     `client : abap.clnt` koyar. Kabuk POST'u yalnız metadata taşır.
  2. Gerçek DDL: aynı oturumda LOCK → PUT `/source/main` (text/plain, **If-Match YOK** — ETag içerik
     tipine göre değiştiği için If-Match ya 412 verir ya PUT sessizce kaydedilmez) → UNLOCK.
  3. `@AbapCatalog.enhancement.category : #NOT_EXTENSIBLE` ZORUNLU (yoksa 400 "Can't save due to errors").
  4. İstemci alanı: `key mandt : mandt not null;` (kütüphanenin `client : abap.clnt` varsayılanı değil).
  5. `not null` YALNIZ anahtar alanda.
  6. Miktar/tutar referansı NİTELİKLİ yazılır: `'<tablo>.<alan>'` (yalnız `'<alan>'` → "annotation uncomplete").
  7. Tip referansları küçük harf.
Alan açıklaması (`fields[i].description`) DDL'e YAZILMAZ — DDIC alan etiketini DTEL'den alır.
"""
from __future__ import annotations

import re

try:  # paket içinden (lib/ sys.path'te) ve doğrudan test importu
    from utils.ddic_dtel import SATIR_SONU_KARAKTERLERI, field_type_to_ddl
    from utils.ddic_semantics import (UNIT_KIND_CURRENCY, UnitKindError, classify_unit_kind,
                                      normalize_unit_kind)
except ImportError:  # pragma: no cover
    from .ddic_dtel import SATIR_SONU_KARAKTERLERI, field_type_to_ddl  # type: ignore
    from .ddic_semantics import (UNIT_KIND_CURRENCY, UnitKindError, classify_unit_kind,  # type: ignore
                                 normalize_unit_kind)

TABLO_AD_MAX = 16
TESLIMAT_SINIFLARI = ("A", "C", "L", "G", "E", "S", "W")
VERI_BAKIMI = ("ALLOWED", "RESTRICTED", "NOT_ALLOWED", "LIMITED")
_AD_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_YASAK_TIP_KARAKTER = re.compile(r"[\s;{}:'\"@]")

KONTROL_EDILENLER = ("T1_ad_uzunlugu", "T2_istemci_alani", "T3_alan_bicimi", "T4_tekil_alan",
                     "T5_teslimat_sinifi", "T6_veri_bakimi", "T7_birim_referansi", "T8_satir_sonu",
                     "T9_anahtar_bayragi")
KONTROL_EDILMEYENLER = ("anahtar alanların tablonun başında art arda durması (SAP aktivasyonu söyler)",
                        "alan adı uzunluk sınırı", "tablo açıklaması uzunluk sınırı",
                        "standart DTEL'lerin varlığı (reviewer yalnız Z/Y ve /ad-alanı/ DTEL'e bakar)",
                        "teknik ayarlar (veri sınıfı, boyut kategorisi, tamponlama — SAP varsayılanı)")


def _bulgu(liste, kural, mesaj):
    liste.append({"rule": kural, "severity": "BLOCKER", "message": mesaj})


def _satir_sonu(deger) -> str | None:
    if not isinstance(deger, str):
        return None
    for ch in deger:
        if ch in SATIR_SONU_KARAKTERLERI:
            return SATIR_SONU_KARAKTERLERI[ch]
    return None


def tablo_on_kontrol(name, description, fields, delivery_class="A", data_maintenance="RESTRICTED") -> dict:
    """Ağ ÖNCESİ argüman kontrolü → {verdict, findings, checked, not_checked, unit_kinds}.

    `unit_kinds`: miktar/tutar alanı (küçük harf) → 'quantity'|'currency' (render aynısını kullanır)."""
    b: list[dict] = []
    ad = name.strip() if isinstance(name, str) else ""
    if len(ad) > TABLO_AD_MAX:
        _bulgu(b, "T1_ad_uzunlugu", f"Tablo adı {len(ad)} karakter — en çok {TABLO_AD_MAX} (DDIC tablo adı sınırı).")
    if _satir_sonu(description):
        _bulgu(b, "T8_satir_sonu", f"Tablo açıklaması satır sonu içeriyor ({_satir_sonu(description)}) — tek satır olmalı.")
    if str(delivery_class or "").upper() not in TESLIMAT_SINIFLARI:
        _bulgu(b, "T5_teslimat_sinifi", f"delivery_class {delivery_class!r} — geçerli: {', '.join(TESLIMAT_SINIFLARI)}.")
    if str(data_maintenance or "").upper() not in VERI_BAKIMI:
        _bulgu(b, "T6_veri_bakimi", f"data_maintenance {data_maintenance!r} — geçerli: {', '.join(VERI_BAKIMI)}.")
    unit_kinds: dict[str, str] = {}
    if not isinstance(fields, list) or not fields:
        _bulgu(b, "T3_alan_bicimi", "fields boş olamaz — en az MANDT + bir alan gerekli.")
        return _sonuc(b, unit_kinds)
    gorulen: dict[str, int] = {}
    tipler: dict[str, str] = {}
    for i, f in enumerate(fields):
        if not isinstance(f, dict):
            _bulgu(b, "T3_alan_bicimi", f"fields[{i}] nesne değil.")
            continue
        fazla = sorted(set(f) - {"name", "type", "key", "description", "unit_field", "unit_kind"})
        if fazla:
            _bulgu(b, "T3_alan_bicimi", f"fields[{i}] tanınmayan alan: {', '.join(fazla)}.")
        fad, ftip = f.get("name"), f.get("type")
        for yer, deger in (("name", fad), ("type", ftip), ("description", f.get("description"))):
            kod = _satir_sonu(deger)
            if kod:
                _bulgu(b, "T8_satir_sonu", f"fields[{i}].{yer} satır sonu içeriyor ({kod}).")
        if not (isinstance(fad, str) and _AD_RE.match(fad.strip() or "-")):
            _bulgu(b, "T3_alan_bicimi", f"fields[{i}].name {fad!r} — harfle başlamalı, yalnız harf/rakam/_.")
            continue
        if not (isinstance(ftip, str) and ftip.strip() and not _YASAK_TIP_KARAKTER.search(ftip.strip())):
            _bulgu(b, "T3_alan_bicimi", f"fields[{i}].type {ftip!r} — DTEL adı ya da ilkel kısaltma (char10, numc8, "
                                        "abap.dec(15,2)…) olmalı; boşluk/;/{/}/:/tırnak içeremez.")
            continue
        if "key" in f and not isinstance(f.get("key"), bool):
            _bulgu(b, "T9_anahtar_bayragi", f"fields[{i}].key true/false olmalı (verilen: {f.get('key')!r}) — "
                                            "'Y'/'X' gibi bir yazım sessizce anahtar-değil sayılırdı.")
        k = fad.strip().lower()
        if k in gorulen:
            _bulgu(b, "T4_tekil_alan", f"fields[{i}].name {fad!r} fields[{gorulen[k]}] ile aynı.")
        gorulen.setdefault(k, i)
        tipler[k] = ftip.strip().lower()
    ilk = fields[0] if isinstance(fields[0], dict) else {}
    if not (str(ilk.get("name") or "").strip().lower() == "mandt" and str(ilk.get("type") or "").strip().lower() == "mandt"
            and ilk.get("key") is True):
        _bulgu(b, "T2_istemci_alani", "İlk alan istemci alanı olmalı: {\"name\":\"MANDT\",\"type\":\"mandt\",\"key\":true} "
                                      "(kütüphanenin `client : abap.clnt` varsayılanı SE11'de CLIENT adıyla görünür).")
    for i, f in enumerate(fields):
        if not isinstance(f, dict):
            continue
        uf, uk = f.get("unit_field"), f.get("unit_kind")
        fad = str(f.get("name") or "").strip().lower()
        if uf in (None, ""):
            if uk not in (None, ""):
                _bulgu(b, "T7_birim_referansi", f"fields[{i}].unit_kind verilmiş ama unit_field boş.")
            continue
        if not isinstance(uf, str) or uf.strip().lower() not in gorulen:
            _bulgu(b, "T7_birim_referansi", f"fields[{i}].unit_field {uf!r} tabloda bir alan değil.")
            continue
        try:
            tur = normalize_unit_kind(uk)
        except UnitKindError as e:
            _bulgu(b, "T7_birim_referansi", f"fields[{i}]: {e}")
            continue
        if tur is None:
            tur = classify_unit_kind(tipler.get(fad, ""), tipler.get(uf.strip().lower(), ""))
        if tur is None:
            _bulgu(b, "T7_birim_referansi", f"fields[{i}] ({fad.upper()}): unit_kind çıkarılamadı (DTEL sözlükte yok) — "
                                            "\"quantity\" ya da \"currency\" AÇIKÇA ver (varsayılana düşülmez).")
            continue
        unit_kinds[fad] = tur
    return _sonuc(b, unit_kinds)


def _sonuc(bulgular, unit_kinds) -> dict:
    return {"verdict": "BLOCKER" if bulgular else "PASS", "findings": bulgular,
            "checked": list(KONTROL_EDILENLER), "not_checked": list(KONTROL_EDILMEYENLER),
            "unit_kinds": unit_kinds}


def tablo_ddl_kaynagi(name: str, description: str, fields, delivery_class: str = "A",
                      data_maintenance: str = "RESTRICTED", unit_kinds: dict | None = None) -> str:
    """Z tablo DDL'i — SAP'ye PUT edilen metin. `tablo_on_kontrol` PASS vermiş girdi bekler.

    Satır sonu içeren serbest metin `ValueError` (render da reddeder — kontrolden bağımsız ikinci katman)."""
    for yer, deger in [("tablo açıklaması", description)] + [
            (f"fields[{i}].{a}", (f or {}).get(a)) for i, f in enumerate(fields or []) for a in ("name", "type")]:
        if _satir_sonu(deger):
            raise ValueError(f"tablo DDL'i render edilemez: {yer} satır sonu içeriyor")
    tablo = name.strip().lower()
    unit_kinds = unit_kinds or {}
    referanslar = {str(f.get("name")).strip().lower(): str(f.get("unit_field")).strip().lower()
                   for f in fields if f.get("unit_field")}
    isaret = {ref: unit_kinds.get(alan) for alan, ref in referanslar.items()}
    satirlar = []
    for f in fields:
        ad = str(f["name"]).strip().lower()
        tip = field_type_to_ddl(str(f["type"]).strip()).lower()
        anahtar = f.get("key") is True
        if ad in isaret:
            satirlar.append("  @Semantics.currencyCode : true" if isaret[ad] == UNIT_KIND_CURRENCY
                            else "  @Semantics.unitOfMeasure : true")
        if ad in referanslar:
            if unit_kinds.get(ad) == UNIT_KIND_CURRENCY:
                satirlar.append(f"  @Semantics.amount.currencyCode : '{tablo}.{referanslar[ad]}'")
            else:
                satirlar.append(f"  @Semantics.quantity.unitOfMeasure : '{tablo}.{referanslar[ad]}'")
        satirlar.append(f"  {'key ' if anahtar else ''}{ad} : {tip}{' not null' if anahtar else ''};")
    etiket = (description or "").replace("'", "''")
    return (f"@EndUserText.label : '{etiket}'\n"
            "@AbapCatalog.enhancement.category : #NOT_EXTENSIBLE\n"
            "@AbapCatalog.tableCategory : #TRANSPARENT\n"
            f"@AbapCatalog.deliveryClass : #{str(delivery_class).upper()}\n"
            f"@AbapCatalog.dataMaintenance : #{str(data_maintenance).upper()}\n"
            f"define table {tablo} {{\n" + "\n".join(satirlar) + "\n}")


_ALAN_SATIRI_RE = re.compile(r"^\s*(key\s+)?([A-Za-z_/][\w/]*)\s*:\s*([^;]+);\s*$", re.I)


def ddl_alanlari(ddl: str) -> list[tuple[bool, str, str]]:
    """DDL gövdesindeki alan tanımları → [(anahtar_mi, ad_küçük, tip_küçük)] (annotation/başlık/yorum hariç).

    Metin birebir kıyaslanmaz: SAP kaynağı normalize eder (girinti, yorum atma, gereksiz annotation silme)."""
    out = []
    for ln in (ddl or "").splitlines():
        s = ln.strip()
        if not s or s.startswith("@") or s.startswith("//") or s.lower().startswith("define"):
            continue
        m = _ALAN_SATIRI_RE.match(ln)
        if m:
            tip = re.sub(r"\s+not\s+null\s*$", "", m.group(3).strip(), flags=re.I).strip().lower()
            out.append((bool(m.group(1)), m.group(2).lower(), tip))
    return out


def ddl_alan_sayisi(ddl: str) -> int:
    return len(ddl_alanlari(ddl))


def tablo_readback_karsilastir(beklenen_ddl: str, canli_ddl: str) -> dict:
    """Yazılan DDL ↔ canlı (aktif) DDL: alan adı sırası + anahtar bayrağı. {ok, reason?, expected, live}."""
    b, c = ddl_alanlari(beklenen_ddl), ddl_alanlari(canli_ddl)
    ozet = {"expected_fields": len(b), "live_fields": len(c)}
    if re.search(r"\bclient\s*:\s*abap\.clnt\b", canli_ddl or "", re.I) and not any(a == "client" for _k, a, _t in b):
        return {"ok": False, "reason": "default_shell_client_field", **ozet,
                "message": "Canlıda varsayılan `client : abap.clnt` kabuğu duruyor — DDL YAZILMAMIŞ (sessiz kayıp)."}
    if not c:
        return {"ok": False, "reason": "no_fields", **ozet, "message": "Canlı kaynakta alan yok (boş/yarım kabuk)."}
    if [(k, a) for k, a, _t in b] != [(k, a) for k, a, _t in c]:
        return {"ok": False, "reason": "field_mismatch", **ozet,
                "message": f"Alan/anahtar dizisi farklı — beklenen {[a for _k, a, _t in b]}, canlı {[a for _k, a, _t in c]}."}
    return {"ok": True, **ozet}
