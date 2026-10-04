# -*- coding: utf-8 -*-
"""XDP / veri XML'i için ortak ayrıştırıcı: satır numaralı küçük ağaç (yalnız standart kütüphane).

`xml.etree` öğelere satır numarası vermez; denetçi ve üretici bulguyu `satır N` ile söylesin diye
`xml.parsers.expat` ile kendi düğüm ağacımızı kuruyoruz. Ad alanı (namespace) bilgisi düşürülür,
yalnız yerel ad kalır (`{uri}subform` → `subform`): XFA şablonunda öğe adları zaten tekildir.
"""
import xml.parsers.expat

XFA_TEMPLATE_PREFIX = "http://www.xfa.org/schema/xfa-template/"


class Dugum:
    __slots__ = ("ad", "ns", "oz", "cocuklar", "metin", "satir", "ata")

    def __init__(self, ad, ns, oz, satir, ata):
        self.ad = ad
        self.ns = ns
        self.oz = oz
        self.cocuklar = []
        self.metin = ""
        self.satir = satir
        self.ata = ata

    def cocuk(self, ad):
        return [c for c in self.cocuklar if c.ad == ad]

    def ilk(self, ad):
        for c in self.cocuklar:
            if c.ad == ad:
                return c
        return None

    def torunlar(self):
        for c in self.cocuklar:
            yield c
            yield from c.torunlar()

    def __repr__(self):  # pragma: no cover - hata ayıklama
        return "<%s satır %d>" % (self.ad, self.satir)


class XmlHatasi(Exception):
    pass


def ayristir(metin):
    """XML metnini Dugum ağacına çevirir. Döner: kök Dugum. Bozuk XML → XmlHatasi (satır bilgisiyle)."""
    p = xml.parsers.expat.ParserCreate(namespace_separator=" ")
    kok = {"d": None}
    yigin = []

    def basla(ad, oz):
        if " " in ad:
            ns, yerel = ad.split(" ", 1)
        else:
            ns, yerel = "", ad
        yeni = {}
        for k, v in oz.items():
            yeni[k.split(" ", 1)[1] if " " in k else k] = v
        ata = yigin[-1] if yigin else None
        d = Dugum(yerel, ns, yeni, p.CurrentLineNumber, ata)
        if ata is None:
            kok["d"] = d
        else:
            ata.cocuklar.append(d)
        yigin.append(d)

    def bitir(_ad):
        yigin.pop()

    def veri(m):
        if yigin:
            yigin[-1].metin += m

    p.StartElementHandler = basla
    p.EndElementHandler = bitir
    p.CharacterDataHandler = veri
    try:
        p.Parse(metin.encode("utf-8") if isinstance(metin, str) else metin, True)
    except xml.parsers.expat.ExpatError as exc:
        raise XmlHatasi("XML ayrıştırılamadı: %s" % exc) from None
    if kok["d"] is None:
        raise XmlHatasi("XML boş")
    return kok["d"]


def oku(yol):
    with open(yol, "rb") as fh:
        ham = fh.read()
    try:
        return ayristir(ham)
    except XmlHatasi as exc:
        raise XmlHatasi("%s: %s" % (yol, exc)) from None


def sablonu_bul(kok):
    """XDP içindeki XFA `template` öğesi (ad alanı xfa-template/*). Yoksa None."""
    if kok.ad == "template" and kok.ns.startswith(XFA_TEMPLATE_PREFIX):
        return kok
    for d in kok.torunlar():
        if d.ad == "template" and d.ns.startswith(XFA_TEMPLATE_PREFIX):
            return d
    return None


def yol_adi(d):
    """Şablon düğümünün okunur yolu: data/ITEMS/ROW/MATNR (adsızlar `(adsız <öğe>)`)."""
    parcalar = []
    while d is not None and d.ad != "template":
        if d.ad in ("subform", "field", "draw", "exclGroup", "subformSet", "area", "pageArea", "pageSet"):
            parcalar.append(d.oz.get("name") or "(adsız %s)" % d.ad)
        d = d.ata
    return "/".join(reversed(parcalar))


UZUNLUK_MM = {"mm": 1.0, "cm": 10.0, "in": 25.4, "pt": 25.4 / 72.0}


def mm(deger):
    """XFA ölçüsünü mm'ye çevirir ('48mm', '1.5cm', '1in', '10pt'). Birimsiz ya da çevrilemeyen değer → None
    (çağıran 'ölçülemedi' sayar; birimsiz değerin XFA'daki varsayılan birimi burada VARSAYILMAZ)."""
    if deger is None:
        return None
    s = deger.strip()
    for birim, carpan in UZUNLUK_MM.items():
        if s.endswith(birim):
            try:
                return float(s[: -len(birim)]) * carpan
            except ValueError:
                return None
    return None
