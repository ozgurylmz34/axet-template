# -*- coding: utf-8 -*-
"""OData $metadata (V2 ya da V4) → fe-mockserver için kurgusal Türkçe mock veri (<EntitySet>.json).

Kullanım:
    python mock_veri.py --metadata webapp/localService/<srv>/metadata.xml \\
                        --cikti webapp/localService/<srv>/data [--adet 5] [--alt-adet 3] [--tohum S] [--zorla]

Ne yapar:
  - EntityContainer'daki her EntitySet için `<cikti>/<EntitySet>.json` (JSON dizi, UTF-8, BOM yok) yazar.
    Dosya adı = EntitySet adı; `@sap-ux/ui5-middleware-fe-mockserver` `mockdataPath` klasöründe bu adı arar.
  - Değerler kurgusaldır ama anlamlıdır: alan adı/etiket sezgisiyle firma/kişi/ürün adı, Türkiye şehri, tutar,
    TRY, tarih, durum, miktar, birim. Kişi adları açıkça kurgusal bir sözlükten; telefon/kimlik/IBAN benzeri
    alanlar belirgin sahte (sıfırlarla dolu) biçimde üretilir. MaxLength ve Precision/Scale ASLA aşılmaz.
  - Birincil hedef: freestyle SAPUI5 + RAP SRVB OData V2 (draft'sız). V4 ve draft'lı servisler de desteklenir.
  - Tekil anahtarlar. ReferentialConstraint (V2 Association · V4 NavigationProperty) varsa alt varlıktaki yabancı
    anahtar, üst varlıkta VAR olan bir kayıttan alınır. V2 Association'da kısıt yoksa ve alt varlıkta üst
    anahtarla AYNI ad+tipte alan varsa FK ad eşleşmesiyle çıkarılır (rapora NOT düşer; eşleşme yoksa FK kurulmaz).
    Belge-kalem ilişkisinde (V2: 1→* ve FK alt anahtarın parçası YA DA üstte bu ilişkiyle alta giden gezinme ·
    V4: Partner'lı koleksiyon gezinmesi) her üst kayda `--alt-adet` kalem düşer ve üstteki "toplam" benzeri
    ondalık alan (Total/Toplam/Sum) kalem tutarlarının toplamına eşitlenir. Seçilen üst/VH kaydında aynı adla
    bulunan ad/metin alanları (ör. CustomerName) da o kayıttan kopyalanır.
  - Değer yardımı (VH): adı *VH / *ValueHelp olan ya da Common.ValueList `CollectionPath` hedefi olan setler de
    üretilir; ValueList eşlemesi (InOut/Out parametreleri) varsa yerel alan değeri VH kaydından alınır.
  - Tarih biçimi (fe-mockserver-core kaynağından doğrulandı): V2 → `/Date(ms)/`, V4 → Edm.Date `YYYY-MM-DD`,
    Edm.DateTimeOffset ISO-8601 `...Z`. Ondalıklar JSON sayısıdır (fe-mockserver ondalığı içeride sayı tutar).
  - RAP draft (IsActiveEntity/HasActiveEntity/HasDraftEntity): yalnız AKTİF kayıt üretilir —
    IsActiveEntity=true, HasActiveEntity=false, HasDraftEntity=false (fe-mockserver'ın activate sonrası hâli);
    DraftAdministrativeData / SiblingEntity gibi gezinmeler JSON'a yazılmaz; I_DraftAdministrativeData seti üretilmez.
    Ölçüldü (fe-mockserver-core 1.7.16): V2 draft servisinde aktif kayıtlar okunur, ama V2 function import ile
    Edit (taslak kopyası) SİMÜLE EDİLMEZ — ekran görüntüsü için yalnız aktif kayıt akışı güvenilirdir.
  - Aynı `--tohum` → bayt-bayt aynı çıktı. Mevcut dosya `--zorla` olmadan EZİLMEZ (atlanır, raporlanır;
    atlanan üst dosyadaki anahtarlar alt varlığın yabancı anahtarı için kullanılır).

KAPSAM (SCOPE): yalnız metadata dosyasının kendisine bakar. Bakmadıkları (her koşumda da basılır):
function import / action / function, harici annotation dosyaları, ValueListReferences (başka servis),
karmaşık/enum/koleksiyon tipli alanlar, akış (Edm.Stream) ve ikili (Edm.Binary) alanlar, draft kopya
(IsActiveEntity=false) kayıtları, kalem içi miktar×fiyat tutarlılığı, mevcut (atlanan) dosyaların içerik doğruluğu.

Çıkış: 0 başarılı (atlanan dosya olsa bile; rapora bakın) · 2 kullanım/girdi hatası (dosya yok, bozuk XML,
Edmx değil, EntityContainer yok) · 1 iç tutarlılık hatası (üretilen değer bir sınırı aştı — hata bildirin).
"""
import argparse
import datetime
import json
import os
import random
import re
import sys
import uuid
import xml.etree.ElementTree as ET
from decimal import Decimal, ROUND_DOWN

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ---------------------------------------------------------------- kurgusal sözlükler (gerçek kişi/kurum DEĞİL)
SEHIRLER = ("İstanbul", "Ankara", "İzmir", "Bursa", "Antalya", "Konya", "Kayseri", "Eskişehir", "Trabzon",
            "Gaziantep", "Samsun", "Adana")
FIRMA_ADLARI = ("Örnek Gıda", "Deneme Tekstil", "Kurgu Makine", "Hayali Lojistik", "Örnek Yapı", "Deneme Kimya",
                "Kurgu Elektrik", "Hayali Mobilya")
FIRMA_EKLERI = ("A.Ş.", "Ltd. Şti.")
KISI_ADLARI = ("Ayşe", "Mehmet", "Zeynep", "Ali", "Elif", "Mustafa", "Fatma", "Emre")
KISI_SOYADLARI = ("Örnek", "Deneme", "Kurgu", "Hayali")  # açıkça kurgusal soyadları
URUNLER = ("Çelik Vida M8", "Karton Koli", "Pamuklu Kumaş", "Plastik Kapak", "Ahşap Palet", "Alüminyum Profil",
           "Cam Şişe", "Bakır Kablo")
DURUMLAR = ("Açık", "Onaylandı", "Tamamlandı", "İptal")
DURUM_KODLARI = ("A", "O", "T", "I")
BIRIMLER = ("ADT", "KG")
PARA_BIRIMI = "TRY"
TABAN_TARIH = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
DRAFT_ALANLARI = {"IsActiveEntity": True, "HasActiveEntity": False, "HasDraftEntity": False}
BOS_GUID = "00000000-0000-0000-0000-000000000000"
VARSAYILAN_TOHUM = "axet"

_TR = str.maketrans("İIıŞşĞğÜüÖöÇç", "iiissgguuoocc")


def _katla(metin):
    return (metin or "").translate(_TR).lower()


# ---------------------------------------------------------------- sezgi desenleri (katlanmış küçük harf metinde)
R_PARA = re.compile(r"(currency|waers|waerk|curr$|currcode|parabirim|doviz)")
R_BIRIM = re.compile(r"(unit$|^unit|uom|meins|vrkme|birim|olcu)")
R_EPOSTA = re.compile(r"(email|e_mail|eposta|mail)")
R_TELEFON = re.compile(r"(phone|telefon|telno|^tel$|fax|faks|mobile|gsm|ceptel)")
R_KIMLIK = re.compile(r"(iban|tckn|tckimlik|kimlikno|taxnumber|taxno|vergino|vkn|stcd|ssn|passport|pasaport|"
                      r"bankaccount|hesapno)")
R_SEHIR = re.compile(r"(city|sehir|ort01|town|ilce|province)")
R_ULKE = re.compile(r"(country|ulke|land1)")
R_ADRES = re.compile(r"(street|address|adres|sokak|cadde)")
R_DURUM = re.compile(r"(status|durum)")
R_KULLANICI = re.compile(r"(createdby|changedby|lastchangedby|user$|username|kullanici|^ernam$|^aenam$|^uname$)")
R_AD = re.compile(r"(name|adi$|^ad$|text|tanim|description|descr|aciklama|bezei|txt|note|remark|comment|"
                  r"yorum|^not$|notu?$)")
R_FIRMA = re.compile(r"(customer|musteri|kunnr|supplier|vendor|lifnr|tedarik|company|firma|partner|sirket)")
R_KISI = re.compile(r"(person|kisi|employee|personel|contact|firstname|lastname|ilgili|isim)")
R_URUN = re.compile(r"(material|matnr|product|urun|malzeme|article)")
R_KOD = re.compile(r"(id$|uuid|no$|nr$|number|numara|num$|kod$|code$|key$|belnr|vbeln|posnr|matnr|kunnr|lifnr|"
                   r"customer|musteri|material|malzeme|product|urun|order|siparis)")
R_KALEM = re.compile(r"(item|kalem|posnr|position|pozisyon|^pos|line|satir)")
R_TARIH = re.compile(r"(date|tarih|datum)")
R_MIKTAR = re.compile(r"(quantity|qty|miktar|menge|adet|count|sayi)")
R_TUTAR = re.compile(r"(amount|amt|tutar|price|fiyat|net|gross|brut|total|toplam|value|deger|cost|maliyet|"
                     r"tax|vergi|betrag|wrbtr|dmbtr|netwr)")
R_FIYAT = re.compile(r"(price|fiyat|preis)")
R_TOPLAM = re.compile(r"(total|toplam|sum)", re.I)
R_VH_AD = re.compile(r"(vh|valuehelp)(set)?$", re.I)
R_DRAFT_ADMIN = re.compile(r"draftadministrativedata", re.I)

EDM_TANINAN = {"Edm.String", "Edm.Guid", "Edm.Boolean", "Edm.Byte", "Edm.SByte", "Edm.Int16", "Edm.Int32",
               "Edm.Int64", "Edm.Decimal", "Edm.Double", "Edm.Single", "Edm.DateTime", "Edm.DateTimeOffset",
               "Edm.Date", "Edm.Time", "Edm.TimeOfDay", "Edm.Duration"}
TAMSAYI_SINIR = {"Edm.Byte": (0, 255), "Edm.SByte": (-128, 127), "Edm.Int16": (-32768, 32767),
                 "Edm.Int32": (-2 ** 31, 2 ** 31 - 1), "Edm.Int64": (-2 ** 63, 2 ** 63 - 1)}


class GirdiHatasi(Exception):
    """Kullanıcının düzeltebileceği girdi hatası (çıkış 2)."""


# ---------------------------------------------------------------- XML yardımcıları (ad alanından bağımsız)
def _yerel(etiket):
    return etiket.rsplit("}", 1)[-1] if isinstance(etiket, str) else ""


def _cocuklar(el, ad):
    return [c for c in el if _yerel(c.tag) == ad]


def _torunlar(el, ad):
    return [c for c in el.iter() if _yerel(c.tag) == ad]


def _nitelik(el, ad):
    """Ad alanlı (sap:label) ya da ad alansız niteliği yerel adla okur."""
    if ad in el.attrib:
        return el.attrib[ad]
    for k, v in el.attrib.items():
        if _yerel(k) == ad:
            return v
    return None


def _terim_sonu(terim):
    return (terim or "").rsplit(".", 1)[-1]


# ---------------------------------------------------------------- model
class Alan:
    def __init__(self, ad, tip, maxlen, precision, scale, nullable, etiket, anahtar, bicim):
        self.ad, self.tip, self.maxlen = ad, tip, maxlen
        self.precision, self.scale, self.nullable = precision, scale, nullable
        self.etiket, self.anahtar, self.bicim = etiket, anahtar, bicim


class Model:
    def __init__(self):
        self.surum = None          # "2" | "4"
        self.tipler = {}           # tam ad → {"ad", "alanlar": [Alan], "anahtarlar": [..], "gezinmeler": [..], "vl": bool}
        self.setler = []           # [{"ad", "tip", "baglar": {yol: hedef}}]
        self.iliskiler = []        # [{"alt", "ust", "ciftler": [(alt_alan, ust_alan)], "tur": kalem|arama}]
        self.degeryardimi = {}     # (tip, alan) → {"koleksiyon", "ciftler": [(yerel, vh_alan)]}
        self.vl_isaretli = []      # V2 sap:value-list alanları (tip, alan)
        self.asetler = {}          # V2 Association tam adı → [{rol: EntitySet}]
        self.bakilmayan = []       # ["FunctionImport ReleaseOrder", ...]
        self.notlar = []


def _tam_ad(ad, ns, takma):
    if ad is None:
        return None
    koleksiyon = ad.startswith("Collection(")
    ic = ad[11:-1] if koleksiyon else ad
    if "." in ic:
        bas, son = ic.rsplit(".", 1)
        ic = "%s.%s" % (takma.get(bas, bas), son)
    elif ns:
        ic = "%s.%s" % (ns, ic)
    return ("Collection(%s)" % ic) if koleksiyon else ic


def _sayi(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def metadata_oku(yol):
    if not os.path.isfile(yol):
        raise GirdiHatasi("metadata dosyası bulunamadı: %s" % yol)
    try:
        kok = ET.parse(yol).getroot()
    except ET.ParseError as exc:
        raise GirdiHatasi("metadata ayrıştırılamadı (bozuk XML): %s: %s" % (yol, exc))
    if _yerel(kok.tag) != "Edmx":
        raise GirdiHatasi("kök öğe Edmx değil (<%s>): %s — OData $metadata bekleniyor" % (_yerel(kok.tag), yol))
    m = Model()
    m.surum = "4" if (_nitelik(kok, "Version") or "").startswith("4") else "2"

    semalar = _torunlar(kok, "Schema")
    takma = {}
    for r in _torunlar(kok, "Include"):  # V4 edmx:Reference/Include takma adları
        if _nitelik(r, "Alias"):
            takma[_nitelik(r, "Alias")] = _nitelik(r, "Namespace")
    for s in semalar:
        if _nitelik(s, "Alias"):
            takma[_nitelik(s, "Alias")] = _nitelik(s, "Namespace")

    etiketler = {}
    v2_iliskiler = {}
    kapsayici = None
    kapsayici_ad = None
    for s in semalar:
        ns = _nitelik(s, "Namespace")
        for et in _cocuklar(s, "EntityType"):
            tam = "%s.%s" % (ns, _nitelik(et, "Name"))
            anahtarlar = [_nitelik(p, "Name") for k in _cocuklar(et, "Key") for p in _cocuklar(k, "PropertyRef")]
            alanlar = []
            for p in _cocuklar(et, "Property"):
                ad = _nitelik(p, "Name")
                etiket = _nitelik(p, "label")
                for a in _cocuklar(p, "Annotation"):
                    if _terim_sonu(_nitelik(a, "Term")) == "Label" and _nitelik(a, "String"):
                        etiket = _nitelik(a, "String")
                ml = _nitelik(p, "MaxLength")
                alanlar.append(Alan(ad, _tam_ad(_nitelik(p, "Type"), None, takma), _sayi(ml),
                                    _sayi(_nitelik(p, "Precision")), _nitelik(p, "Scale"),
                                    (_nitelik(p, "Nullable") or "true") != "false", etiket, ad in anahtarlar,
                                    _nitelik(p, "display-format")))
                if _nitelik(p, "value-list"):
                    m.vl_isaretli.append((tam, ad))
            gezinmeler = []
            for n in _cocuklar(et, "NavigationProperty"):
                gezinmeler.append({
                    "ad": _nitelik(n, "Name"),
                    "tip": _tam_ad(_nitelik(n, "Type"), ns, takma),
                    "partner": _nitelik(n, "Partner"),
                    "kisit": [(_nitelik(r, "Property"), _nitelik(r, "ReferencedProperty"))
                              for r in _cocuklar(n, "ReferentialConstraint")],
                    "iliski": _tam_ad(_nitelik(n, "Relationship"), ns, takma),
                    "from": _nitelik(n, "FromRole"), "to": _nitelik(n, "ToRole"),
                })
            m.tipler[tam] = {"ad": _nitelik(et, "Name"), "alanlar": alanlar, "anahtarlar": anahtarlar,
                             "gezinmeler": gezinmeler}
        for asc in _cocuklar(s, "Association"):
            uclar = {_nitelik(e, "Role"): (_tam_ad(_nitelik(e, "Type"), ns, takma), _nitelik(e, "Multiplicity"))
                     for e in _cocuklar(asc, "End")}
            kisit = None
            for rc in _cocuklar(asc, "ReferentialConstraint"):
                p = _cocuklar(rc, "Principal")[0]
                d = _cocuklar(rc, "Dependent")[0]
                kisit = {"ust_rol": _nitelik(p, "Role"), "alt_rol": _nitelik(d, "Role"),
                         "ust": [_nitelik(x, "Name") for x in _cocuklar(p, "PropertyRef")],
                         "alt": [_nitelik(x, "Name") for x in _cocuklar(d, "PropertyRef")]}
            v2_iliskiler["%s.%s" % (ns, _nitelik(asc, "Name"))] = {"uclar": uclar, "kisit": kisit}
        for ad in ("Action", "Function"):
            for f in _cocuklar(s, ad):
                m.bakilmayan.append("%s %s" % (ad, _nitelik(f, "Name")))
        for k in _cocuklar(s, "EntityContainer"):
            if kapsayici is None or _nitelik(k, "IsDefaultEntityContainer") == "true":
                kapsayici, kapsayici_ad = k, "%s.%s" % (ns, _nitelik(k, "Name"))
        for ann in _cocuklar(s, "Annotations"):
            etiketler.setdefault("__ann__", []).append(ann)
    if kapsayici is None:
        raise GirdiHatasi("EntityContainer bulunamadı: %s" % yol)

    for es in _cocuklar(kapsayici, "EntitySet"):
        m.setler.append({"ad": _nitelik(es, "Name"), "tip": _tam_ad(_nitelik(es, "EntityType"), None, takma),
                         "baglar": {_nitelik(b, "Path"): _nitelik(b, "Target")
                                    for b in _cocuklar(es, "NavigationPropertyBinding")}})
    for aset in _cocuklar(kapsayici, "AssociationSet"):
        m.asetler.setdefault(_tam_ad(_nitelik(aset, "Association"), None, takma), []).append(
            {_nitelik(e, "Role"): _nitelik(e, "EntitySet") for e in _cocuklar(aset, "End")})
    for ad in ("FunctionImport", "ActionImport"):
        for f in _cocuklar(kapsayici, ad):
            m.bakilmayan.append("%s %s" % (ad, _nitelik(f, "Name")))

    # ---- annotation'lar: etiket + ValueList
    for ann in etiketler.get("__ann__", []):
        hedef = _hedef_coz(_nitelik(ann, "Target") or "", m, kapsayici_ad, takma)
        if not hedef:
            continue
        tip, alan = hedef
        for a in _cocuklar(ann, "Annotation"):
            terim = _terim_sonu(_nitelik(a, "Term"))
            if terim == "Label" and _nitelik(a, "String") and tip in m.tipler:
                for x in m.tipler[tip]["alanlar"]:
                    if x.ad == alan:
                        x.etiket = _nitelik(a, "String")
            elif terim == "ValueList":
                vl = _degeryardimi_oku(a)
                if vl:
                    m.degeryardimi[(tip, alan)] = vl
            elif terim in ("ValueListReferences", "ValueListMapping"):
                m.bakilmayan.append("%s %s/%s (başka servis)" % (terim, m.tipler.get(tip, {}).get("ad", tip), alan))

    _iliskileri_kur(m, v2_iliskiler)
    return m


def _hedef_coz(hedef, m, kapsayici_ad, takma):
    parcalar = hedef.split("/")
    if len(parcalar) < 2:
        return None
    bas = _tam_ad(parcalar[0], None, takma)
    if bas in m.tipler:
        return bas, parcalar[1]
    if bas == kapsayici_ad and len(parcalar) >= 3:
        for s in m.setler:
            if s["ad"] == parcalar[1]:
                return s["tip"], parcalar[2]
    return None


def _degeryardimi_oku(ann):
    koleksiyon = None
    ciftler = []
    for pv in _torunlar(ann, "PropertyValue"):
        if _nitelik(pv, "Property") == "CollectionPath":
            koleksiyon = _nitelik(pv, "String") or "".join(c.text or "" for c in _cocuklar(pv, "String")).strip()
    for rec in _torunlar(ann, "Record"):
        tur = _terim_sonu(_nitelik(rec, "Type"))
        if tur not in ("ValueListParameterInOut", "ValueListParameterOut"):
            continue
        yerel = vh = None
        for pv in _cocuklar(rec, "PropertyValue"):
            if _nitelik(pv, "Property") == "LocalDataProperty":
                yerel = _nitelik(pv, "PropertyPath") or "".join(
                    c.text or "" for c in _cocuklar(pv, "PropertyPath")).strip()
            elif _nitelik(pv, "Property") == "ValueListProperty":
                vh = _nitelik(pv, "String") or "".join(c.text or "" for c in _cocuklar(pv, "String")).strip()
        if yerel and vh:
            ciftler.append((yerel, vh))
    if not koleksiyon:
        return None
    return {"koleksiyon": koleksiyon, "ciftler": ciftler}


def _setler_tipten(m, tip):
    return [s["ad"] for s in m.setler if s["tip"] == tip]


def _v2_kisit_cikar(m, asc_ad, bilgi):
    """ReferentialConstraint'siz V2 Association (1 → *): üst anahtarlarıyla AYNI ad ve tipte alt alanlar varsa
    FK çıkarımı yapar (draft anahtarı IsActiveEntity hariç). Çıkarım rapora NOT olarak düşer."""
    roller = list(bilgi["uclar"].items())
    ust = [(r, t) for r, (t, c) in roller if c in ("1", "0..1")]
    alt = [(r, t) for r, (t, c) in roller if c == "*"]
    if len(ust) != 1 or len(alt) != 1 or ust[0][1] not in m.tipler or alt[0][1] not in m.tipler:
        return None
    ust_tip, alt_tip = m.tipler[ust[0][1]], m.tipler[alt[0][1]]
    ust_anahtar = [a for a in ust_tip["anahtarlar"] if a not in DRAFT_ALANLARI]
    alt_alanlar = {a.ad: a.tip for a in alt_tip["alanlar"]}
    ust_alanlar = {a.ad: a.tip for a in ust_tip["alanlar"]}
    if not ust_anahtar or any(alt_alanlar.get(a) != ust_alanlar.get(a) for a in ust_anahtar):
        m.notlar.append("%s: ReferentialConstraint yok, ad eşleşmesiyle FK çıkarılamadı — FK tutarlılığı YOK"
                        % asc_ad)
        return None
    m.notlar.append("%s: ReferentialConstraint yok → FK ad eşleşmesiyle ÇIKARILDI (%s.%s)"
                    % (asc_ad, alt_tip["ad"], ",".join(ust_anahtar)))
    return {"ust_rol": ust[0][0], "alt_rol": alt[0][0], "ust": ust_anahtar, "alt": list(ust_anahtar)}


def _iliskileri_kur(m, v2_iliskiler):
    if m.surum == "2":
        for asc_ad, bilgi in sorted(v2_iliskiler.items()):
            k = bilgi["kisit"] or _v2_kisit_cikar(m, asc_ad, bilgi)
            if not k:
                continue
            ust_tip, ust_carp = bilgi["uclar"].get(k["ust_rol"], (None, None))
            alt_tip, alt_carp = bilgi["uclar"].get(k["alt_rol"], (None, None))
            if not ust_tip or not alt_tip or ust_tip not in m.tipler or alt_tip not in m.tipler:
                continue
            if ust_tip == alt_tip:
                m.notlar.append("öz-ilişki atlandı: %s" % asc_ad)
                continue
            ciftler = list(zip(k["alt"], k["ust"]))
            alt_anahtar = set(m.tipler[alt_tip]["anahtarlar"])
            # belge-kalem: 1→* ve (FK alt anahtarın parçası YA DA üstte bu ilişkiyle alta giden gezinme var —
            # RAP V2'de kalem anahtarı çoğu kez yalnız kendi UUID'sidir, üst anahtar anahtar DEĞİLDİR)
            ustten_gezinme = any(g["iliski"] == asc_ad and g["to"] == k["alt_rol"]
                                 for g in m.tipler[ust_tip]["gezinmeler"])
            kalem = (ust_carp in ("1", "0..1") and alt_carp == "*" and
                     (set(k["alt"]) <= alt_anahtar or ustten_gezinme))
            eslesmeler = [(a[k["alt_rol"]], a[k["ust_rol"]]) for a in m.asetler.get(asc_ad, [])
                          if k["alt_rol"] in a and k["ust_rol"] in a]
            if not eslesmeler:  # AssociationSet yoksa tipten (ilk üst set)
                ust_setler = _setler_tipten(m, ust_tip)
                eslesmeler = [(a, ust_setler[0]) for a in _setler_tipten(m, alt_tip)] if ust_setler else []
            for alt_set, ust_set in eslesmeler:
                m.iliskiler.append({"alt": alt_set, "ust": ust_set, "ciftler": ciftler,
                                    "tur": "kalem" if kalem else "arama", "kaynak": asc_ad})
    else:
        for s in m.setler:
            tip = m.tipler.get(s["tip"])
            if not tip:
                continue
            for n in tip["gezinmeler"]:
                if not n["kisit"] or n["tip"].startswith("Collection("):
                    continue
                ust_tip = m.tipler.get(n["tip"])
                if not ust_tip or n["tip"] == s["tip"]:
                    continue
                ust_set = s["baglar"].get(n["ad"]) or (_setler_tipten(m, n["tip"]) or [None])[0]
                if not ust_set:
                    continue
                kalem = any(g["tip"] == "Collection(%s)" % s["tip"] and
                            (g["ad"] == n["partner"] or g["partner"] == n["ad"])
                            for g in ust_tip["gezinmeler"])
                m.iliskiler.append({"alt": s["ad"], "ust": ust_set, "ciftler": list(n["kisit"]),
                                    "tur": "kalem" if kalem else "arama", "kaynak": "%s/%s" % (s["ad"], n["ad"])})
    # değer yardımı setlerine yapılan ilişkiler "arama"dır; bir setin yalnız ilk kalem ilişkisi sayıyı belirler
    vh = vh_setleri(m)
    goruldu = set()
    for r in m.iliskiler:
        if r["ust"] in vh:
            r["tur"] = "arama"
        if r["tur"] == "kalem":
            if r["alt"] in goruldu:
                r["tur"] = "arama"
            goruldu.add(r["alt"])


def vh_setleri(m):
    adlar = {s["ad"] for s in m.setler}
    sonuc = {s["ad"] for s in m.setler if R_VH_AD.search(s["ad"])}
    sonuc |= {v["koleksiyon"] for v in m.degeryardimi.values() if v["koleksiyon"] in adlar}
    return sonuc


# ---------------------------------------------------------------- değer üretimi
def _kes(metin, ml):
    if ml is None or len(metin) <= ml:
        return metin
    return metin[:ml].rstrip()


def _olcek(alan):
    s = _sayi(alan.scale)
    if s is None:
        return 2 if alan.scale in ("variable", "floating") else 0
    return s


def _ust_sinir(alan):
    """Precision/Scale'e sığan en büyük mutlak değer."""
    s = _olcek(alan)
    p = alan.precision
    if p is None:
        return Decimal(10) ** 9
    tam = p - s
    birim = Decimal(1).scaleb(-s)
    return (Decimal(10) ** tam - birim) if tam > 0 else (Decimal(1) - birim)


def _ondalik(rng, alt, ust, s):
    birim = 10 ** s
    lo, hi = int(alt * birim), int(ust * birim)
    if hi < lo:
        hi = lo
    return Decimal(rng.randint(lo, hi)).scaleb(-s)


def _json_ondalik(d, s):
    return int(d) if s == 0 else float(d)


def _sirali_metin(n, ml):
    """Tekil anahtar/numara: önce sıfır dolgulu rakam, sığmazsa taban-36; sığmazsa None."""
    if ml is None:
        ml = 10
    genislik = min(ml, 10)
    if n < 10 ** genislik:
        return str(n).zfill(genislik)
    alfabe = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if n < 36 ** ml:
        cikti = ""
        while n:
            n, r = divmod(n, 36)
            cikti = alfabe[r] + cikti
        return cikti.rjust(ml, "0")
    return None


def _kapasite(alan):
    if alan.tip == "Edm.String":
        ml = alan.maxlen if alan.maxlen is not None else 10
        return max(10 ** min(ml, 10), 36 ** ml) - 1
    if alan.tip in TAMSAYI_SINIR:
        return TAMSAYI_SINIR[alan.tip][1]
    return None


def _tarih(rng, gun_araligi=365):
    return TABAN_TARIH + datetime.timedelta(days=rng.randint(0, gun_araligi - 1))


def _ms(zaman):
    return int(zaman.timestamp() * 1000)


def _metin_sinifi(metin):
    k = _katla(metin)
    if not k:
        return None
    for ad, desen in (("para", R_PARA), ("eposta", R_EPOSTA), ("telefon", R_TELEFON), ("kimlik", R_KIMLIK),
                      ("birim", R_BIRIM), ("sehir", R_SEHIR), ("ulke", R_ULKE), ("adres", R_ADRES),
                      ("durum", R_DURUM), ("kullanici", R_KULLANICI)):
        if desen.search(k):
            return ad
    if R_AD.search(k):
        if R_FIRMA.search(k):
            return "firma"
        if R_KISI.search(k):
            return "kisi"
        if R_URUN.search(k):
            return "urun"
        return "aciklama"
    if R_KISI.search(k):
        return "kisi"
    if R_TARIH.search(k):
        return "tarih"
    if R_KOD.search(k):
        return "kod"
    return None


def _durum_listesi(ml):
    """MaxLength'e sığan durum adları (en az 2); sığmazsa tek harfli kodlar (Açık=A, Onaylandı=O, ...)."""
    uygun = [d for d in DURUMLAR if ml is None or len(d) <= ml]
    return uygun if len(uygun) == len(DURUMLAR) else [_kes(d, ml) for d in DURUM_KODLARI]


def _sigani_sec(rng, adaylar, ml):
    """MaxLength'e sığan adaylardan seçer; hiçbiri sığmıyorsa kesilmiş bir aday döner."""
    uygun = [a for a in adaylar if ml is None or len(a) <= ml]
    return rng.choice(uygun) if uygun else _kes(rng.choice(adaylar), ml)


def _sabit_uzunluk_sahte(ml, n, varsayilan):
    genislik = min(ml or varsayilan, varsayilan)
    return str(n).zfill(genislik)[-genislik:]


class Uretici:
    def __init__(self, model, tohum, adet, alt_adet):
        self.m = model
        self.tohum = str(tohum)
        self.adet = adet
        self.alt_adet = alt_adet
        self.havuz = {}            # set adı → kayıtlar (üretilen ya da mevcut dosyadan)
        self.tanınmayan = []       # "Set.Alan (tip)"
        self.kesilen = []          # "Set.Alan" (ValueList/FK değeri MaxLength'e kesildi)
        self.toplamlar = []        # (ust_set, ust_alan, alt_set, alt_alan, ciftler)
        self.kisitli = []          # "Set: N → M (anahtar kapasitesi)"
        self.yinelenen = []
        self.toplam_notlari = []
        self.vh = vh_setleri(model)
        self._durum_anahtarli = False
        self._toplam_plani()

    # -- toplam planı: kalem ilişkisinde üstte Total/Toplam/Sum ondalık alan → alttaki tutar alanı
    def _toplam_plani(self):
        set_tip = {s["ad"]: s["tip"] for s in self.m.setler}
        for r in self.m.iliskiler:
            if r["tur"] != "kalem":
                continue
            ust = self.m.tipler[set_tip[r["ust"]]]
            alt = self.m.tipler[set_tip[r["alt"]]]
            alt_ondalik = [a for a in alt["alanlar"] if a.tip == "Edm.Decimal" and not a.anahtar]
            for ua in ust["alanlar"]:
                if ua.tip != "Edm.Decimal" or ua.anahtar or not R_TOPLAM.search(ua.ad):
                    continue
                kok = _katla(R_TOPLAM.sub("", ua.ad))
                aday = [a for a in alt_ondalik if kok and kok in _katla(a.ad) and not R_FIYAT.search(_katla(a.ad))
                        and not R_MIKTAR.search(_katla(a.ad))]
                if not aday:
                    aday = [a for a in alt_ondalik if R_TUTAR.search(_katla(a.ad))
                            and not R_FIYAT.search(_katla(a.ad)) and not R_MIKTAR.search(_katla(a.ad))]
                if aday:
                    self.toplamlar.append({"ust_set": r["ust"], "ust_alan": ua, "alt_set": r["alt"],
                                           "alt_alan": aday[0], "ciftler": r["ciftler"]})
                else:
                    self.toplam_notlari.append("%s.%s: kalemde eşlenecek tutar alanı bulunamadı" % (r["ust"], ua.ad))

    def _alt_tutar_siniri(self, set_ad, alan):
        for t in self.toplamlar:
            if t["alt_set"] == set_ad and t["alt_alan"] is alan:
                return (_ust_sinir(t["ust_alan"]) / max(1, self.alt_adet)).quantize(
                    Decimal(1).scaleb(-_olcek(alan)), rounding=ROUND_DOWN)
        return None

    def rng(self, set_ad):
        return random.Random("%s|%s" % (self.tohum, set_ad))

    def uret(self, set_bilgi):
        ad = set_bilgi["ad"]
        tip = self.m.tipler[set_bilgi["tip"]]
        rng = self.rng(ad)
        alanlar = tip["alanlar"]
        taslak = all(any(a.ad == d for a in alanlar) for d in DRAFT_ALANLARI)
        self._durum_anahtarli = any(a.anahtar and a.tip == "Edm.String" and _metin_sinifi(a.ad) == "durum"
                                    for a in alanlar)
        iliskiler = [r for r in self.m.iliskiler if r["alt"] == ad]
        kalem = next((r for r in iliskiler if r["tur"] == "kalem"), None)
        vl = {alan: v for (t, alan), v in self.m.degeryardimi.items() if t == set_bilgi["tip"]}

        ust_kayitlar = None
        if kalem:
            ust_kayitlar = [k for k in self.havuz.get(kalem["ust"], [])
                            if all(u in k for _, u in kalem["ciftler"])]
            sayi = len(ust_kayitlar) * self.alt_adet
        else:
            sayi = self.adet
        for a in alanlar:
            if a.anahtar and not any(a.ad == x for r in iliskiler for x, _ in r["ciftler"]):
                kap = _kapasite(a)
                if kap is not None and kap < sayi and a.tip != "Edm.Boolean":
                    self.kisitli.append("%s: %d → %d (%s anahtar kapasitesi)" % (ad, sayi, kap, a.ad))
                    sayi = kap

        kayitlar = []
        for i in range(sayi):
            kayit = {}
            dolu = {}
            if kalem:
                ust = ust_kayitlar[i // self.alt_adet]
                grup_sira = i % self.alt_adet + 1
                for alt_a, ust_a in kalem["ciftler"]:
                    dolu[alt_a] = ust[ust_a]
            else:
                grup_sira = i + 1
            for r in iliskiler:
                if r is kalem:
                    continue
                havuz = [k for k in self.havuz.get(r["ust"], []) if all(u in k for _, u in r["ciftler"])]
                if havuz:
                    secim = _uyumlu_sec(rng, havuz, r["ciftler"], dolu)
                    for alt_a, ust_a in r["ciftler"]:
                        dolu.setdefault(alt_a, secim[ust_a])
                    _metin_kopyala(alanlar, secim, dolu)
            for alan_ad, v in sorted(vl.items()):
                havuz = [k for k in self.havuz.get(v["koleksiyon"], []) if all(x in k for _, x in v["ciftler"])]
                if havuz and v["ciftler"]:
                    secim = _uyumlu_sec(rng, havuz, v["ciftler"], dolu)
                    for yerel, vh_alan in v["ciftler"]:
                        dolu.setdefault(yerel, secim[vh_alan])
                    _metin_kopyala(alanlar, secim, dolu)
            for a in alanlar:
                if taslak and a.ad in DRAFT_ALANLARI:
                    kayit[a.ad] = DRAFT_ALANLARI[a.ad]
                    continue
                if a.ad in dolu:
                    deger = dolu[a.ad]
                    if isinstance(deger, str) and a.maxlen is not None and len(deger) > a.maxlen:
                        deger = _kes(deger, a.maxlen)
                        not_ = "%s.%s" % (ad, a.ad)
                        if not_ not in self.kesilen:
                            self.kesilen.append(not_)
                    kayit[a.ad] = deger
                    continue
                deger = self._deger(ad, a, rng, i, grup_sira, taslak, kalem is not None)
                if deger is _ATLA:
                    etiket = "%s.%s (%s)" % (ad, a.ad, a.tip)
                    if etiket not in self.tanınmayan:
                        self.tanınmayan.append(etiket)
                    continue
                kayit[a.ad] = deger
            kayitlar.append(kayit)

        # anahtar tekilliği
        anahtar = tip["anahtarlar"]
        gorulen, temiz = set(), []
        for k in kayitlar:
            t = tuple(json.dumps(k.get(x), ensure_ascii=False) for x in anahtar)
            if t in gorulen:
                continue
            gorulen.add(t)
            temiz.append(k)
        if len(temiz) != len(kayitlar):
            self.yinelenen.append("%s: %d yinelenen anahtar atıldı" % (ad, len(kayitlar) - len(temiz)))
        return temiz

    def toplamlari_uygula(self, uretilen):
        for t in self.toplamlar:
            if t["ust_set"] not in uretilen:
                self.toplam_notlari.append("%s.%s: toplam uygulanamadı — üst dosya atlandı (mevcut)"
                                           % (t["ust_set"], t["ust_alan"].ad))
                continue
            if t["alt_set"] not in self.havuz:
                continue
            s = _olcek(t["ust_alan"])
            kalemler = self.havuz[t["alt_set"]]
            for ust in self.havuz[t["ust_set"]]:
                toplam = Decimal(0)
                for k in kalemler:
                    if all(k.get(a) == ust.get(u) for a, u in t["ciftler"]) and t["alt_alan"].ad in k:
                        toplam += Decimal(str(k[t["alt_alan"].ad]))
                toplam = toplam.quantize(Decimal(1).scaleb(-s))
                if abs(toplam) > _ust_sinir(t["ust_alan"]):
                    raise AssertionError("toplam sınırı aştı: %s.%s" % (t["ust_set"], t["ust_alan"].ad))
                ust[t["ust_alan"].ad] = _json_ondalik(toplam, s)

    # -- tek alan değeri
    def _deger(self, set_ad, a, rng, i, grup_sira, taslak, kalem_mi):
        tip = a.tip or ""
        ad_k = _katla(a.ad)
        n = i + 1
        if tip not in EDM_TANINAN:
            return _ATLA
        if tip == "Edm.Guid":
            if taslak and a.ad == "DraftUUID":
                return BOS_GUID
            return str(uuid.UUID(int=rng.getrandbits(128), version=4))
        if tip == "Edm.Boolean":
            return rng.random() < 0.3
        if tip in TAMSAYI_SINIR:
            lo, hi = TAMSAYI_SINIR[tip]
            if kalem_mi and R_KALEM.search(ad_k):
                return min(hi, grup_sira * 10)
            if a.anahtar:
                return min(hi, n)
            if R_MIKTAR.search(ad_k):
                return rng.randint(max(lo, 1), min(hi, 50))
            return rng.randint(max(lo, 1), min(hi, 999))
        if tip == "Edm.Decimal":
            s = _olcek(a)
            sinir = _ust_sinir(a)
            if a.anahtar:
                return _json_ondalik(min(Decimal(n), sinir), s)
            if R_MIKTAR.search(ad_k):
                return _json_ondalik(Decimal(rng.randint(1, int(min(Decimal(50), max(sinir, 1))))), s)
            if R_TUTAR.search(ad_k) or R_TUTAR.search(_katla(a.etiket)):
                ust = min(Decimal(20000), sinir)
                alt_sinir = self._alt_tutar_siniri(set_ad, a)
                if alt_sinir is not None:
                    ust = min(ust, alt_sinir)
                return _json_ondalik(_ondalik(rng, min(Decimal(10), ust), ust, s), s)
            return _json_ondalik(_ondalik(rng, Decimal(0), min(Decimal(1000), sinir), s), s)
        if tip in ("Edm.Double", "Edm.Single"):
            return round(rng.uniform(0, 1000), 2)
        if tip in ("Edm.DateTime", "Edm.DateTimeOffset", "Edm.Date"):
            gun = _tarih(rng)
            tarih_mi = tip == "Edm.Date" or (a.bicim or "").lower() == "date" or (
                tip == "Edm.DateTime" and R_TARIH.search(ad_k) and "time" not in ad_k and "zaman" not in ad_k)
            if not tarih_mi:
                gun = gun + datetime.timedelta(hours=rng.randint(8, 17), minutes=rng.choice((0, 15, 30, 45)))
            if self.m.surum == "2":
                return "/Date(%d)/" % _ms(gun)
            if tip == "Edm.Date":
                return gun.strftime("%Y-%m-%d")
            return gun.strftime("%Y-%m-%dT%H:%M:%SZ")
        if tip == "Edm.Time":
            return "PT%02dH%02dM00S" % (rng.randint(8, 17), rng.choice((0, 15, 30, 45)))
        if tip == "Edm.TimeOfDay":
            return "%02d:%02d:00" % (rng.randint(8, 17), rng.choice((0, 15, 30, 45)))
        if tip == "Edm.Duration":
            return "PT%dH" % rng.randint(1, 8)
        return self._metin(a, rng, n, grup_sira, kalem_mi)

    def _metin(self, a, rng, n, grup_sira, kalem_mi):
        ml = a.maxlen
        ad_k = _katla(a.ad)
        sinif = _metin_sinifi(a.ad) or _metin_sinifi(a.etiket)
        if not a.anahtar and (kalem_mi and R_KALEM.search(ad_k) or (a.bicim or "").lower() == "nonnegative"):
            deger = grup_sira * 10 if kalem_mi and R_KALEM.search(ad_k) else n
            return _sirali_metin(deger, min(ml or 10, 10)) or _kes(str(deger), ml)
        if a.anahtar:
            if kalem_mi and R_KALEM.search(ad_k):
                return _sirali_metin(grup_sira * 10, min(ml or 6, 6)) or _sirali_metin(grup_sira, ml)
            if sinif == "durum":  # durum değer yardımı: sıra küçükse okunur kod/ad
                uygun = _durum_listesi(ml)
                if n <= len(uygun):
                    return uygun[n - 1]
            return _sirali_metin(n, ml)
        if sinif == "para":
            return _kes(PARA_BIRIMI, ml)
        if sinif == "birim":
            return _kes(rng.choice(BIRIMLER), ml)
        if sinif == "eposta":
            return _kes("kullanici" + str(n) + "@" + "ornek" + ".invalid", ml)
        if sinif in ("telefon", "kimlik"):
            return _sabit_uzunluk_sahte(ml, n, 11 if sinif == "telefon" else 16)
        if sinif == "sehir":
            uygun = [s for s in SEHIRLER if ml is None or len(s) <= ml] or list(SEHIRLER)
            return _kes(rng.choice(uygun), ml)
        if sinif == "ulke":
            return _kes("TR", ml)
        if sinif == "adres":
            return _kes("Örnek Mah. Deneme Sok. No:%d" % n, ml)
        if sinif == "durum":
            if self._durum_anahtarli and n <= len(DURUMLAR):  # durum VH metni: anahtarla aynı sıradaki ad
                return _kes(DURUMLAR[n - 1], ml)
            return rng.choice(_durum_listesi(ml))
        if sinif == "kullanici":
            return _kes("KULLANICI%02d" % rng.randint(1, 20), ml)
        if sinif == "firma":
            return _sigani_sec(rng, ["%s %s" % (f, e) for f in FIRMA_ADLARI for e in FIRMA_EKLERI] +
                               list(FIRMA_ADLARI), ml)
        if sinif == "kisi":
            return _sigani_sec(rng, ["%s %s" % (a_, s_) for a_ in KISI_ADLARI for s_ in KISI_SOYADLARI], ml)
        if sinif == "urun":
            return _sigani_sec(rng, list(URUNLER), ml)
        if sinif == "aciklama":
            if re.search(r"(note|remark|comment|yorum|not$|notu$)", ad_k):
                return _kes("Örnek not %d" % n, ml)
            return _kes("Örnek açıklama %d" % n, ml)
        if sinif == "tarih" and ml in (8, None):
            return _tarih(rng).strftime("%Y%m%d")
        if sinif == "kod":
            if kalem_mi and R_KALEM.search(ad_k):
                return _sirali_metin(grup_sira * 10, min(ml or 6, 6)) or _kes(str(grup_sira), ml)
            return _sirali_metin(n, ml) or _kes(str(n), ml)
        ek = str(n)
        if ml is not None and ml <= len(ek):
            return _kes(ek, ml)
        on = a.ad if ml is None else a.ad[:max(0, ml - len(ek))]
        return on + ek


_ATLA = object()


def _uyumlu_sec(rng, havuz, ciftler, dolu):
    """Havuzdan bir kayıt seçer; yerel alan önceden doldurulduysa (ör. FK ilişkisiyle) o değere uyan kaydı tercih
    eder — aynı kayda hem ilişki hem ValueList bağlıysa Out/metin alanları aynı üst kayıttan gelir."""
    uyan = [k for k in havuz if all(k.get(u) == dolu[y] for y, u in ciftler if y in dolu)]
    aday = uyan or havuz
    return aday[rng.randrange(len(aday))]


def _metin_kopyala(alanlar, secim, dolu):
    """Seçilen üst/VH kaydında AYNI adla bulunan ad/metin alanlarını (CustomerName gibi, anahtar değil) kopyalar."""
    for a in alanlar:
        if not a.anahtar and a.tip == "Edm.String" and a.ad in secim and R_AD.search(_katla(a.ad)):
            dolu.setdefault(a.ad, secim[a.ad])


# ---------------------------------------------------------------- sıra, sınır doğrulaması, yazım
def uretim_sirasi(m):
    """Üst setler ve değer yardımı setleri önce (topolojik; bağ eşitliğinde metadata sırası)."""
    adlar = [s["ad"] for s in m.setler]
    bag = {a: set() for a in adlar}
    for r in m.iliskiler:
        if r["ust"] in bag and r["ust"] != r["alt"]:
            bag[r["alt"]].add(r["ust"])
    set_tip = {s["ad"]: s["tip"] for s in m.setler}
    for (tip, _), v in m.degeryardimi.items():
        for a in adlar:
            if set_tip[a] == tip and v["koleksiyon"] in bag and v["koleksiyon"] != a:
                bag[a].add(v["koleksiyon"])
    sira, durum, donguler = [], {}, []

    def ziyaret(a, yol):
        if durum.get(a) == 2:
            return
        if durum.get(a) == 1:
            donguler.append(" → ".join(yol + [a]))
            return
        durum[a] = 1
        for b in sorted(bag[a], key=adlar.index):
            ziyaret(b, yol + [a])
        durum[a] = 2
        sira.append(a)

    for a in adlar:
        ziyaret(a, [])
    return sira, donguler


def sinirlari_dogrula(m, set_bilgi, kayitlar):
    """Üretilen her değer MaxLength/Precision/Scale'e uyuyor mu (güvenlik ağı)."""
    hatalar = []
    for a in m.tipler[set_bilgi["tip"]]["alanlar"]:
        for k in kayitlar:
            v = k.get(a.ad)
            if v is None:
                continue
            if isinstance(v, str) and a.maxlen is not None and len(v) > a.maxlen:
                hatalar.append("%s.%s=%r MaxLength %d" % (set_bilgi["ad"], a.ad, v, a.maxlen))
            if a.tip == "Edm.Decimal" and isinstance(v, (int, float)):
                d = Decimal(str(v))
                if abs(d) > _ust_sinir(a) or max(0, -d.as_tuple().exponent) > _olcek(a):
                    hatalar.append("%s.%s=%s Precision/Scale %s/%s" % (set_bilgi["ad"], a.ad, v, a.precision,
                                                                        a.scale))
    return hatalar


def json_metni(kayitlar):
    return json.dumps(kayitlar, ensure_ascii=False, indent=2) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(prog="mock_veri.py",
                                 description="OData V2/V4 $metadata → fe-mockserver için kurgusal Türkçe mock veri.")
    ap.add_argument("--metadata", required=True, help="metadata.xml yolu (OData V2 ya da V4)")
    ap.add_argument("--cikti", required=True, help="çıktı klasörü (fe-mockserver mockdataPath)")
    ap.add_argument("--adet", type=int, default=5, help="üst/bağımsız set başına kayıt (varsayılan 5)")
    ap.add_argument("--alt-adet", type=int, default=3, help="belge-kalem ilişkisinde üst kayıt başına kalem (3)")
    ap.add_argument("--tohum", default=VARSAYILAN_TOHUM, help="rastgelelik tohumu; aynı tohum → aynı çıktı")
    ap.add_argument("--zorla", action="store_true", help="mevcut <EntitySet>.json dosyalarını ez")
    args = ap.parse_args(argv)
    if args.adet < 1 or args.alt_adet < 1:
        print("HATA: --adet ve --alt-adet en az 1 olmalı.", file=sys.stderr)
        return 2
    try:
        m = metadata_oku(args.metadata)
    except GirdiHatasi as exc:
        print("HATA: %s" % exc, file=sys.stderr)
        return 2

    set_bilgi = {s["ad"]: s for s in m.setler}
    u = Uretici(m, args.tohum, args.adet, args.alt_adet)
    sira, donguler = uretim_sirasi(m)
    uretilen, atlanan, draft_admin, hatalar = {}, [], [], []
    for ad in sira:
        s = set_bilgi[ad]
        if s["tip"] not in m.tipler:
            m.notlar.append("%s: EntityType bulunamadı (%s)" % (ad, s["tip"]))
            continue
        if R_DRAFT_ADMIN.search(m.tipler[s["tip"]]["ad"]) or R_DRAFT_ADMIN.search(ad):
            draft_admin.append(ad)
            continue
        yol = os.path.join(args.cikti, ad + ".json")
        if os.path.exists(yol) and not args.zorla:
            atlanan.append(ad)
            try:
                with open(yol, encoding="utf-8-sig") as fh:
                    mevcut = json.load(fh)
                u.havuz[ad] = [k for k in mevcut if isinstance(k, dict)] if isinstance(mevcut, list) else []
            except (OSError, ValueError) as exc:
                m.notlar.append("%s: mevcut dosya okunamadı (%s) — alt setler bu üste bağlanamaz" % (ad, exc))
                u.havuz[ad] = []
            continue
        kayitlar = u.uret(s)
        u.havuz[ad] = kayitlar
        uretilen[ad] = kayitlar
    u.toplamlari_uygula(uretilen)
    for ad, kayitlar in uretilen.items():
        hatalar += sinirlari_dogrula(m, set_bilgi[ad], kayitlar)
    if hatalar:
        print("HATA (iç tutarlılık): üretilen değer sınırı aştı — dosya yazılmadı:\n  " + "\n  ".join(hatalar),
              file=sys.stderr)
        return 1
    if uretilen:
        os.makedirs(args.cikti, exist_ok=True)
    for ad in sira:
        if ad in uretilen:
            with open(os.path.join(args.cikti, ad + ".json"), "w", encoding="utf-8", newline="\n") as fh:
                fh.write(json_metni(uretilen[ad]))

    vh = sorted(u.vh)
    print("MOCK VERİ — OData V%s · metadata: %s · çıktı: %s · tohum: %s · adet: %d · alt-adet: %d"
          % (m.surum, args.metadata, args.cikti, args.tohum, args.adet, args.alt_adet))
    print("YAZILDI (%d): %s" % (len(uretilen), ", ".join("%s (%d kayıt)" % (a, len(uretilen[a]))
                                                          for a in sira if a in uretilen) or "-"))
    print("ATLANDI (mevcut dosya, --zorla yok) (%d): %s" % (len(atlanan), ", ".join(atlanan) or "-"))
    print("DEĞER YARDIMI setleri (%d): %s" % (len(vh), ", ".join(vh) or "-"))
    for (tip, alan), v in sorted(m.degeryardimi.items()):
        print("  ValueList: %s.%s → %s (%s)" % (m.tipler.get(tip, {}).get("ad", tip), alan, v["koleksiyon"],
                                                ", ".join("%s=%s" % c for c in v["ciftler"]) or "eşleme yok"))
    eslemesiz = [(t, a) for t, a in m.vl_isaretli if (t, a) not in m.degeryardimi]
    if eslemesiz:
        print("  sap:value-list işaretli ama ValueList eşlemesi metadata'da yok (harici annotation?): %s"
              % ", ".join("%s.%s" % (m.tipler[t]["ad"], a) for t, a in eslemesiz))
    print("İLİŞKİLER (%d):" % len(m.iliskiler))
    for r in m.iliskiler:
        print("  %s(%s) → %s(%s) [%s]" % (r["alt"], ",".join(x for x, _ in r["ciftler"]), r["ust"],
                                          ",".join(y for _, y in r["ciftler"]), r["tur"]))
    for t in u.toplamlar:
        print("TOPLAM: %s.%s = Σ %s.%s" % (t["ust_set"], t["ust_alan"].ad, t["alt_set"], t["alt_alan"].ad))
    for n in u.toplam_notlari:
        print("TOPLAM notu: %s" % n)
    if u.kesilen:
        print("KESİLEN (ilişki/VH değeri alanın MaxLength'ine kısaltıldı): %s" % ", ".join(u.kesilen))
    if u.kisitli:
        print("SAYI KISITLANDI: %s" % "; ".join(u.kisitli))
    if u.yinelenen:
        print("YİNELENEN ANAHTAR: %s" % "; ".join(u.yinelenen))
    if draft_admin:
        print("DRAFT yönetim setleri üretilmedi: %s" % ", ".join(draft_admin))
    if donguler:
        print("DÖNGÜLÜ bağımlılık (kırıldı): %s" % "; ".join(donguler))
    for n in m.notlar:
        print("NOT: %s" % n)
    print("TANINMAYAN tipler (alan JSON'a yazılmadı) (%d): %s" % (len(u.tanınmayan), ", ".join(u.tanınmayan) or "-"))
    print("KAPSAM (SCOPE) — bakılmayanlar: function import / action / function (%d: %s); harici annotation "
          "dosyaları; ValueListReferences (başka servis); karmaşık/enum/koleksiyon/akış/ikili tipli alanlar; "
          "gezinme (navigation) alanları JSON'a yazılmaz; draft kopya kayıtları (yalnız aktif kayıt); kalem içi "
          "miktar×fiyat tutarlılığı; atlanan dosyaların içerik doğruluğu. Toplam kuralı yalnız belge-kalem "
          "ilişkisinde Total/Toplam/Sum adlı ondalık alan için kurulur."
          % (len(m.bakilmayan), ", ".join(m.bakilmayan) or "-"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
