#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kaynak_paketi.py — ikili kaynak belgeden (.docx / .xlsx) MEKANİK kaynak paketi ve kaynak → belge iz denetimi.

Kullanım:
  python kaynak_paketi.py cikar <kaynak.docx|.xlsx> [--hedef-kok <dizin>] [--id <ad>]
  python kaynak_paketi.py iz <paket-dizini> --tablo <iz-tablosu.md> --belge <FS.md> [--belge <EK.md> …]

cikar: kaynak belgeyi model YENİDEN YAZMADAN pakete çıkarır → <hedef-kok>/<id>/ (varsayılan hedef kök:
  <çalışma dizini>/.axet-code/tmp, varsayılan id: <dosya adı>-<içerik özetinin ilk 8 hanesi>):
    metin.md   çıkarım kapsamındaki metin, kaynak sırasıyla; her metin bloğu (başlık, paragraf, tablo satırı, nesne,
               geri düşüş grubu) bir kaynak maddesi KM-nnnn; yapılandırılmayan XML metni sonda ham (geri düşüş)
    media/     belgedeki görseller (KG-nn) · gomulu/  gömülü nesneler (KN-nn): OLE paket nesnesinin asıl dosyası
               (ör. HTML prototip), OLE içindeki OOXML paketi, altChunk içeriği; tanınmayan ham kopyalanır
    INDEX.md   sayım tablosu (kaynaktan bağımsız sayım ↔ diskteki paket) + dosya listesi + nasıl okunur
    paket.json makine için aynı bilgi (iz alt komutu okur)
  Doğrulama paketi DİSKTEN yeniden okur ve kaynağın ayrı kodla yapılan sayımıyla karşılaştırır; eşit değilse FAIL.
iz: kaynak maddesi → belge kimliği (FR/KR/TC/SCR…) eşleme tablosunu denetler: her KM/KG/KN satırda mı, boş eşleme,
  belgede olmayan kimlik, pakette olmayan madde. Belgeyi okuyup "doğru eşlendi mi" yargısı VERMEZ (inceleyicinin işi).
Çıkış: 0 PASS · 1 FAIL (paket/tablo kullanılamaz) · 2 girdi okunamadı · 3 biçim desteklenmiyor (.pdf, .doc, .xls …).
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import struct
import sys
import unicodedata
import zipfile
import zlib
from pathlib import Path
from xml.etree import ElementTree as ET

for _a in (sys.stdout, sys.stderr):
    try:
        _a.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

HERE = Path(__file__).resolve().parent

# KM numaralandırma şeması. Betik bir maddeyi farklı sırayla ya da farklı bölünmeyle numaralandırdığında artar; iz
# tablosu bu sayıyı taşır ve `iz` farklıysa FAIL verir (aynı kaynak, başka şema = kimlikler kaymış olabilir).
# 1: v0.5.24 ilk hâli · 2: grafik `pt` hücreleri + "Yapılandırılmamış parça metni" bölümü (geri düşüş).
KM_SEMASI = 2

# Muaf parçalar (evren süpürmesine girmez): YAPISAL parçalar — biçim, ilişki, tema, ayar, belge özelliği. Liste SCOPE'ta
# basılır; her muaf parça INDEX'in parça hesabında metin karakteriyle görünür (muaf ≠ "metin yok").
# Ölçüm (2026-11-19, Microsoft Office'in kurulu şablonları, 23 .dotx + 7 .xltx, yalnız okundu): içerik türleri, ilişki,
# stil, tema, Word ayarı, hesap zinciri, SmartArt düzen/renk/stil → 0 metin karakteri. docProps 75 parça / 4478
# karakter (başlık, yazar, uygulama adı — üst veri), customXml 94 parça / 8520 karakter (SharePoint form adları, base64
# görsel eşlemesi, içerik denetimi bağlama verisi) → metin VAR, belge gövdesi değil. Yazıcı ayarı ve grafik stil/renk
# bu kümede hiç yoktu → DOĞRULANMADI. SmartArt önbellek çizimi koşulludur (muaf_nedeni): 4 parça, metni veri parçasının
# alt kümesi. Aynı ölçümde 30/30 dosyada parça hesabı tuttu.
MUAF = [
    ("içerik türleri", r"^\[Content_Types\]\.xml$"),
    ("ilişki", r"(^|/)_rels/[^/]+\.rels$"),
    ("stil", r"^(word|xl)/styles(WithEffects)?\.xml$"),
    ("tema", r"^(word|xl)/theme/[^/]+\.xml$"),
    ("Word ayarı (settings, webSettings, fontTable, numbering)", r"^word/(settings|webSettings|fontTable|numbering)\.xml$"),
    ("belge özelliği", r"^docProps/"),
    ("özel XML verisi", r"^customXml/"),
    ("hesap zinciri", r"^xl/calcChain\.xml$"),
    ("yazıcı ayarı", r"(^|/)printerSettings/"),
    ("SmartArt düzen/renk/stil tanımı", r"^(word|xl)/diagrams/(layout|colors|quickStyle)\d*\.xml$"),
    ("grafik stil/renk", r"^(word|xl)/charts/(style|colors)\d*\.xml$"),
]
MUAF_RE = [(ad, re.compile(d)) for ad, d in MUAF]
# Dosya olarak çıkan üyeler (görsel KG, gömülü KN): içerikleri evrene girmez, adetleri ayrı sayılır.
DOSYA_PARCA = re.compile(r"^(word|xl)/(media|embeddings)/")
# Görüntülenebilir sayılan görsel biçimleri — TEK liste (paket, INDEX, `iz` buradan okur; belgeler listeyi kopyalamaz,
# adını anar). Motorun `view` aracı: png/jpg/jpeg/gif açar (uzantı büyük/küçük harf duyarsız); bmp/emf/wmf açmaz —
# aXet.code 1.5.1, 2026-11-19/20 ölçümü. webp/tiff/svg ölçülmedi → listede yok. Listede olmayan biçim GÖRÜNTÜLENEMEZ
# sayılır; `iz` boş notunu FAIL değil ÖLÇÜLEMEDİ sayar — kullanıcı PNG'si (KULLANICI_PNG) varsa o PNG okunur ve boş not
# FAIL olur. Betik dönüştürmez (ek bağımlılık yok); Pillow'la çevirme talimatı iskelette ve SKILL'de.
GORUNTULENEBILIR = (".png", ".jpg", ".jpeg", ".gif")
# Görüntülenemeyen görselin okunabilir kopyası: model (Pillow ile) ya da kullanıcı bu adla `media/`'ya koyar. Çıkarım
# kendi dosyalarını DAİMA `<kimlik>_` ile adlandırır → bu ad çıkarımın üreteceği bir adla çakışmaz; sayımda sayılmaz.
KULLANICI_PNG = "media/%s.kullanici.png"
# Harfe DUYARSIZ (Windows dosya sistemi `KG-02.kullanici.PNG` ile `.png`'yi aynı dosya sayar); ad harfi korunur.
KULLANICI_PNG_RE = re.compile(r"^K[GN]-\d+\.kullanici\.png$", re.I)
# Görsel notunda (işaretler arası) yer tutucu: harf/rakam içermeyen metin, yalnız x'lerden oluşan dizgi ya da (HTML
# varlığı/etiketi, Markdown görsel bağlantısı, baştaki "todo:" ve noktalama atılınca) bu sözcüklerden biri boş sayılır.
YER_TUTUCU = ("todo", "boş", "bos", "doldurulacak", "doldur", "na", "tbd", "tba", "yok", "none", "null")
# Görsel açılamayınca yazılan ifade (notun TAMAMI buysa boş; diakritik atılmış biçimde karşılaştırılır). Cümle içinde
# geçmesi notu boşaltmaz. Yalnız bir kimlikten ("KG-02") oluşan not da boştur.
ACILAMADI = ("okunamadi", "okunmadi", "gorulmedi", "henuzyok", "acilamadi", "goruntulenemedi", "gorselacilamadi",
             "gorselokunamadi", "nil")
# Bu sayıyı aşan görsel + gömülü nesne INDEX'te UYARI alır (sert sınır değil; bağlam bütçesi ve not yükü için).
COK_GORSEL = 500
# Gömülü nesne (KN) bu uzantılardan biriyse görsel sayılır ve not bölümü alır (KG'lerin hepsi zaten alır).
GORSEL_UZANTILARI = GORUNTULENEBILIR + (".bmp", ".emf", ".wmf", ".emz", ".wmz", ".tif", ".tiff", ".svg", ".wdp",
                                        ".jxr", ".ico", ".webp")
NOT_DOSYASI = "gorsel-notlari.md"
# Yok sayılan metin düğümleri (çıkarım bilerek almaz; evrenden de düşülür). Ad listesi kapsamı DARALTMAZ: burada
# olmayan her metin ya yapılandırılmış satıra ya geri düşüş bölümüne gider.
# mc:Fallback YALNIZ aynı mc:AlternateContent içinde metni (boşluklar atılmış metin düğümü dizisi) Fallback'inkiyle
# AYNI bir mc:Choice varsa yok sayılır (gerçek yineleme; karakter sayısı eşitliği yetmez); değilse metni geri düşüşe gider. Alan kodu sınıfı yalnız instrText'tir (alan SONUCU w:t
# yapılandırılmış satırdadır). Yaprak sınıfları yalnız alt öğesi olmayan öğeye uygulanır.
YOK_FALLBACK = "yinelenen gösterim (mc:Fallback, Choice ile eşit)"
YOK_ALT_AGAC = {"rPh": "fonetik okunuş (rPh)"}
YOK_KONUM = "konum/ölçü değeri"
# DrawingML (posOffset, align, pct*), çizim çapası (col, colOff, row, rowOff), Excel VML açıklama kutusu (Row, Column, Anchor)
KONUM_ADLARI = ("posOffset", "align", "pctWidth", "pctHeight", "pctPosHOffset", "pctPosVOffset", "col", "colOff", "row",
                "rowOff", "Row", "Column", "Anchor")
YOK_YAPRAK = {"instrText": "alan kodu (instrText)", "delText": "izlenen değişiklikte silinen metin (delText)",
              **{k: "formül / veri başvurusu (f, definedName)" for k in ("f", "definedName")},
              "formatCode": "sayı biçim kodu (formatCode)",
              "trace": "mürekkep koordinatı (inkml:trace)",
              **{k: YOK_KONUM for k in KONUM_ADLARI}}
# Parçaya bağlı yaprak sınıfı: yalnız desene uyan parçada yok sayılır, başka parçada aynı yerel ad geri düşüşe gider.
# definedName yalnız çalışma kitabında (xl/workbook.xml) formül/başvurudur (_xlnm.Print_Area gibi sistem adları dahil);
# f yalnız sayfa ve grafik parçalarında formüldür; formatCode yalnız grafikte biçim kodudur; trace yalnız mürekkep
# (InkML) parçasında koordinat dizisidir. Bilinmeyen parçada aynı yerel ad iş metni taşıyabilir → geri düşüş.
YOK_PARCA_SINIRI = {"definedName": re.compile(r"^xl/workbook\.xml$"),
                    "f": re.compile(r"^(xl/worksheets/|xl/chartsheets/|(word|xl)/charts/)"),
                    "formatCode": re.compile(r"^(word|xl)/charts/"),
                    "trace": re.compile(r"^(word|xl)/ink/")}
# Değere bağlı yaprak sınıfı: konum/ölçü adı yalnız değeri sayı (ya da virgüllü sayı dizisi: VML x:Anchor) veya hizalama
# anahtar sözcüğüyse yok sayılır; `<x:row>iş metni</x:row>` gibi metin taşıyan aynı ad geri düşüşe gider.
KONUM_DEGERI = re.compile(r"^\s*(-?\d+(\.\d+)?(\s*,\s*-?\d+(\.\d+)?)*|left|right|center|inside|outside|top|bottom)\s*$")
YOK_SINIFLAR = sorted({YOK_FALLBACK, *YOK_ALT_AGAC.values(), *YOK_YAPRAK.values()})


def yaprak_sinifi(ad: str, parca: str | None, deger: str | None = None) -> str | None:
    """Yerel adı `ad`, metni `deger` olan yaprak öğe bu parçada yok sayılan sınıfta mı? → sınıf adı ya da None."""
    sinir = YOK_PARCA_SINIRI.get(ad)
    if sinir is not None and not (parca and sinir.match(parca)):
        return None
    sinif = YOK_YAPRAK.get(ad)
    if sinif == YOK_KONUM and not KONUM_DEGERI.match(deger or ""):
        return None
    return sinif
SCOPE_CIKAR = (
    "KAPSAM (SCOPE): kaynak_paketi cikar — .docx: ana gövde (paragraf, başlık, tablo; tablo içi tablo hücre metnine "
    "düzleşir; metin kutusunun paragraf ve tabloları bulunduğu paragrafın satırına düzleşir; denklem metni satır içinde "
    "⟦denklem⟧ işaretiyle), SmartArt (D) ve grafik (G) metni kendi KM satırında, görseller (media/ klasörü, görsel "
    "ilişkisinin hedefi ya da görsel uzantılı üye — klasör adına bağlı değil; SVG'nin svgBlip PNG yedeği eşlenir), "
    "word/embeddings nesneleri, altChunk; dışa bağlı görsel ve çözülemeyen başvuru işaretlenir (UYARI). .xlsx: sayfa "
    "satırları, xl/drawings metin kutuları (K), SmartArt, grafik, xl görselleri, xl/embeddings. GERİ DÜŞÜŞ: yukarıdakilerin kapsamadığı her XML parçasının (üst/altbilgi, dipnot, yorum, "
    "tanınmayan parçalar) ve yapılandırılmış parçalarda alınmayan metin düğümlerinin metni 'Yapılandırılmamış parça "
    "metni' bölümüne ham yazılır. EVREN: zip'teki her XML parçasının her metin düğümü; parça başına evren − yok sayılan "
    "= yapılandırılmış + geri düşüş, değilse FAIL. MUAF PARÇALAR: " + "; ".join("%s `%s`" % kv for kv in MUAF) + ". "
    "YOK SAYILAN METİN DÜĞÜMLERİ (her biri karakter sayısıyla basılır): " + "; ".join(YOK_SINIFLAR) + " — parçaya "
    "bağlı: " + "; ".join("%s yalnız `%s`" % (k, d.pattern) for k, d in YOK_PARCA_SINIRI.items()) + " (başka parçada "
    "geri düşüşe gider); konum/ölçü adı yalnız değeri sayı ya da hizalama sözcüğüyse; mc:Fallback yalnız aynı "
    "AlternateContent'te metni (boşluksuz) AYNI bir Choice varsa; alan kodu yalnız instrText (alan sonucu alınır). "
    "xlsx sayfa ve paylaşılan dizge parçalarında 'yapılandırılmış' pay kaynaktan hesaplanır (pakette yalnız metin "
    "hücresi ölçülür). XML olmayan üyeler (ör. makro kodu vbaProject.bin, gömülü yazı tipi, düz metin) ve XML gibi "
    "başlayıp ayrıştırılamayan üyeler adı ve boyuyla listelenir. "
    "BAKMADIKLARI: öznitelik metni (görsel alternatif metni, veri doğrulama istemi, köprü ipucu, içerik denetimi "
    "açılır liste seçenekleri w:listItem, içerik denetimi adı w:alias), XML olmayan üyelerin içeriği (makro kodu "
    "dahil), xlsx sayfa/paylaşılan dizge parçasının pakette yapılandırılmış payı (sayı/tarih hücresi), gömülü/altChunk "
    "içeriğin ve görselin METNİ (dosya olarak çıkar), Word'ün otomatik numaraları, xlsx'te birleştirilmiş hücre/biçim, "
    "nesnenin hangi hücrede durduğu ve sayı/tarih hücresinin karakteri (xlsx'te yalnız metin hücreleri karakter "
    "sayımına girer). Boyut sınırı: zip üyesi gerçekten açılarak sayılır, ≤ 100 MiB; açılmış metin üyeleri toplamı "
    "≤ 512 MiB — aşan XML parçası ya da toplam ÖLÇÜLEMEDİ (çıkış 2); 100 MiB'ı ya da kendi payını (1 GiB) aşan "
    "görsel/gömülü üye ve XML olmayan ikili üye atlanır, INDEX'te ÖLÇÜLEMEDİ yazar (metin toplamına sayılmaz). "
    "Doğrulama sayım eşitliğidir; içerik doğruluğu değil.")
SCOPE_IZ = (
    "KAPSAM (SCOPE): kaynak_paketi iz — paketin her KM/KG/KN maddesi tabloda tam bir satırda mı, eşleme boş mu, "
    "kimlik belgede geçiyor mu, tablo pakette olmayan madde anıyor mu, tablodaki kaynak sha256'sı ve km şeması "
    "paketinkiyle aynı mı; gorsel-notlari.md'de her görselin notu — YALNIZ `<!-- gorulen:KG-nn -->` ile "
    "`<!-- /gorulen:KG-nn -->` işaret satırlarının arası — dolu mu (görüntülenebilir biçimde ya da "
    "`media/<kimlik>.kullanici.png` kopyası varken boşsa FAIL, okunabilir kopyası olmayan biçimde ÖLÇÜLEMEDİ; PNG "
    "yedeği olan SVG yedeğin bölümünde okunur); işareti eksik ya da sırası bozuk görsel (FAIL); bir görsel bölümünde "
    "işaret dışında kalan metin ve yinelenen işaret çifti, çözülemeyen ve dışa bağlı görsel başvurusu (UYARI); belgedeki FR/KR tabloda anılıyor mu, görsel notunda anılan kimlik o "
    "görselin iz satırında var mı, paket boş mu, tabloda sha256 / km şeması var mı (UYARI). "
    "BAKMADIKLARI: eşlemenin ANLAMCA doğruluğu (KM metni gerçekten o FR'de karşılanmış mı), BİLGİ/KAPSAM-DIŞI "
    "işaretinin haklılığı, görsel notunun görselle UYUMU (notun gerçekten görseli anlattığı; `iz` yalnız dolu olduğunu "
    "sayar) — üçü de inceleyici yargısıdır (inceleyici görseli `view` ile açıp notla karşılaştırır).")

DESTEKLENEN = (".docx", ".docm", ".xlsx", ".xlsm")
DESTEKLENMEYEN_NEDEN = {
    ".pdf": "PDF'ten metin standart kütüphaneyle güvenilir biçimde (sıra, tablo) çıkarılamıyor",
    ".doc": "eski ikili Word biçimi okunmuyor",
    ".xls": "eski ikili Excel biçimi okunmuyor",
    ".rtf": "RTF okunmuyor",
    ".pptx": "sunu biçimi okunmuyor",
}
KM_RE = re.compile(r"^(#{1,6} )?\[(KM-\d{4,})\] ")
NOT_RE = re.compile(r"⟦[^⟧]*⟧")
SATIR_RE = re.compile(r"^⟦(T\d+|SY(\d+))\.S(\d+)⟧ ")
NESNE_RE = re.compile(r"^⟦([DGK])\d+ (SmartArt|grafik|metin kutusu): [^⟧]*⟧ ?")
NESNE_ANAHTAR = {"SmartArt": "diyagram", "grafik": "grafik", "metin kutusu": "metin_kutusu"}
DENKLEM = "⟦denklem⟧"

# Boyut sınırları (zip üyesinin açılmış boyu ve tüm üyelerin toplamı). Zip başlığındaki beyana GÜVENİLMEZ: her üye
# 1 MiB'lık parçalarla gerçekten açılıp sayılır (yalan söyleyen başlık 339 MB'a çıkarmıştı — ölçüldü 2026-11-19).
# Ölçülmüş bir eşik değil, paydır: tipik bir istek belgesi onlarca MB'ın altındadır; çıkarım üyeyi belleğe alır ve
# tepe bellek açılmış boyun yaklaşık iki katıdır (150 MB'lık üye → 339 MB tepe). Aşan metin parçası ya da toplam
# FAIL değil ÖLÇÜLEMEDİ'dir (çıkış 2, paket yazılmaz); aşan görsel/gömülü üye ve aşan XML OLMAYAN ikili üye (makro,
# yazı tipi, yazıcı ayarı) atlanır, INDEX'te ÖLÇÜLEMEDİ yazar — büyük bir makro/yazı tipi paketin metnini düşürmez.
MAX_UYE = 100 * 1024 * 1024
MAX_TOPLAM = 512 * 1024 * 1024        # açılmış METİN (XML) üyelerin toplamı
MAX_DOSYA_TOPLAM = 1024 * 1024 * 1024  # çıkarılan görsel/gömülü üyelerin toplamı; aşan üye atlanır (paket düşmez)
MAX_IKILI_TOPLAM = 1024 * 1024 * 1024  # XML olmayan ikili üyelerin toplamı (ayrı pay); aşan üye atlanır
OKUMA_PARCASI = 1024 * 1024


class Okunamadi(Exception):
    """Girdi okunamadı (bozuk zip, eksik ana parça) — çıkış 2."""


def yerel(tag) -> str:
    """'{ad alanı}yerel' → 'yerel'. Ad alanı URI'leri bu dosyada bilerek yazılmaz (skill iz taraması URL yasaklar)."""
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def attr_yerel(el, ad: str):
    for k, v in el.attrib.items():
        if yerel(k) == ad:
            return v
    return None


def ozet(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def guvenli_ad(ad: str, varsayilan: str = "dosya") -> str:
    ad = ad.replace("\\", "/").rsplit("/", 1)[-1]
    # Kabukta ya da tırnaklı komut satırında anlam taşıyan karakterler de (' " $ ` %) değiştirilir: ad iskeletteki
    # çevirme komutuna gömülür (`it's.emf` SyntaxError, `$x.emf` PowerShell'de açılır).
    ad = re.sub(r"""[<>:"'|?*$`%\x00-\x1f]""", "_", ad).strip(" .")
    return ad[:120] or varsayilan


def gorunur(s: str) -> str:
    """Zip üye adı gibi kaynaktan gelen metni tek satırlık işaret/tablo hücresine yazılabilir yapar: denetim karakteri,
    satır/paragraf ayracı, işaret parantezi ⟦⟧, ters tırnak ve ters bölünün kendisi kaçırılır (`\\n`, `\\u2028`,
    `\\\\`, …) — kaçış birebirdir: iki farklı ad aynı metne düşmez. Sıradan ad değişmez."""
    def kac(ch: str) -> str:
        if ch in "\n\r\t\\":
            return {"\n": "\\n", "\r": "\\r", "\t": "\\t", "\\": "\\\\"}[ch]
        return "\\x%02x" % ord(ch) if ord(ch) < 0x100 else "\\u%04x" % ord(ch)
    return "".join(kac(ch) if ch in "⟦⟧`\\" or unicodedata.category(ch) in ("Cc", "Cf", "Zl", "Zp") else ch
                   for ch in s)


def hucre(s: str) -> str:
    """Markdown tablo hücresine yazılacak kaynak metni: `gorunur` + dikey çizgi kaçışı."""
    return gorunur(s).replace("|", "\\|")


def bosluksuz(s: str) -> int:
    return sum(1 for ch in s if not ch.isspace())


# ── OLE / CFB (bileşik ikili dosya) okuyucu — yalnız okuma, stdlib ─────────────────────────────────────────────
ENDOFCHAIN = 0xFFFFFFFE
FREESECT = 0xFFFFFFFF
CFB_IMZA = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


class CfbHata(Exception):
    pass


def cfb_akislari(data: bytes) -> dict[str, bytes]:
    """CFB içindeki akışlar {ad: içerik}. Bozuk/kısa dosya her yolda CfbHata verir (struct/indeks hatası sızmaz)."""
    try:
        return _cfb_akislari(data)
    except CfbHata:
        raise
    except (struct.error, IndexError, ValueError, OverflowError, UnicodeError) as exc:
        raise CfbHata(f"bozuk CFB ({type(exc).__name__}: {exc})") from None


def _cfb_akislari(data: bytes) -> dict[str, bytes]:
    """Ağaç yürünmez, dizin girdileri sırayla okunur (yalnız ad gerekiyor). Tablo boyları (DIFAT/FAT sektör sayısı)
    dosyadaki sektör sayısıyla sınırlanır; DIFAT zinciri ziyaret kümesiyle yürünür (döngü = bozuk)."""
    if len(data) < 512 or data[:8] != CFB_IMZA:
        raise CfbHata("CFB imzası yok")
    sector_shift, mini_shift = struct.unpack_from("<HH", data, 0x1E)
    if sector_shift not in (9, 12) or mini_shift != 6:
        raise CfbHata("beklenmeyen sektör boyu")
    ssz = 1 << sector_shift
    n_sektor = max(0, (len(data) - ssz + ssz - 1) // ssz)  # başlıktan sonraki sektör sayısı (son kısmi dahil)
    n_fat, first_dir = struct.unpack_from("<II", data, 0x2C)
    cutoff, first_minifat, n_minifat, first_difat, n_difat = struct.unpack_from("<IIIII", data, 0x38)
    n_fat, n_difat = min(n_fat, n_sektor), min(n_difat, n_sektor)

    def sektor(n: int, tam: bool = True) -> bytes:
        off = (n + 1) * ssz
        if n >= 0xFFFFFFFA or off >= len(data):
            raise CfbHata(f"sektör dışı: {n}")
        parca = data[off:off + ssz]
        if tam and len(parca) < ssz:  # tablo sektörü (DIFAT/FAT/dizin/mini FAT) kesik olamaz
            raise CfbHata(f"kısa sektör: {n} ({len(parca)}/{ssz} bayt)")
        return parca

    fat_ids = [x for x in struct.unpack_from("<109I", data, 0x4C) if x != FREESECT]
    d, gorulen = first_difat, set()
    while d not in (ENDOFCHAIN, FREESECT) and len(gorulen) < n_difat:
        if d in gorulen:
            raise CfbHata("DIFAT zinciri döngülü")
        gorulen.add(d)
        vals = struct.unpack_from("<%dI" % (ssz // 4), sektor(d))
        fat_ids += [x for x in vals[:-1] if x != FREESECT]
        d = vals[-1]
    fat: list[int] = []
    for f in fat_ids[:n_fat]:
        fat += struct.unpack_from("<%dI" % (ssz // 4), sektor(f))
    # Her sektörün tek sahibi olur (tablo, dizin, mini akış ya da tek bir akış). Paylaşılan sektör gerçek bir CFB'de
    # olmaz; kabul edilirse aynı sektörleri gösteren N akış bellekte N kez kopyalanır (ölçüldü: 155 KB → 41 MB).
    kullanilan: set[int] = set(gorulen) | set(fat_ids[:n_fat])
    kullanilan_mini: set[int] = set()

    def sahiplen(liste: list[int], kume: set[int], ne: str) -> list[int]:
        for n in liste:
            if n in kume:
                raise CfbHata(f"sektör {n} birden çok yerde kullanılıyor ({ne}) — bozuk ya da kötü niyetli dosya")
            kume.add(n)
        return liste

    def zincir(start: int, tablo: list[int]) -> list[int]:
        out, n = [], start
        while n not in (ENDOFCHAIN, FREESECT):
            if n >= len(tablo) or len(out) > len(tablo):
                raise CfbHata("bozuk sektör zinciri")
            out.append(n)
            n = tablo[n]
        return out

    dir_data = b"".join(sektor(n) for n in sahiplen(zincir(first_dir, fat), kullanilan, "dizin"))
    girdiler = []
    for i in range(0, len(dir_data) - 127, 128):
        e = dir_data[i:i + 128]
        ad_len = struct.unpack_from("<H", e, 64)[0]
        tur = e[66]
        start, size = struct.unpack_from("<IQ", e, 116)
        if tur == 0:
            continue
        ad = e[:max(0, ad_len - 2)].decode("utf-16-le", "replace")
        if (struct.unpack_from("<H", data, 0x1A)[0]) == 3:
            size &= 0xFFFFFFFF
        girdiler.append((ad, tur, start, size))
    kok = next((g for g in girdiler if g[1] == 5), None)
    if kok is None:
        raise CfbHata("kök girdi yok")
    mini_stream = (b"".join(sektor(n) for n in sahiplen(zincir(kok[2], fat), kullanilan, "mini akış"))[:kok[3]]
                   if kok[3] else b"")
    minifat: list[int] = []
    if n_minifat and first_minifat not in (ENDOFCHAIN, FREESECT):
        for n in sahiplen(zincir(first_minifat, fat), kullanilan, "mini FAT"):
            minifat += struct.unpack_from("<%dI" % (ssz // 4), sektor(n))
    akislar: dict[str, bytes] = {}
    for ad, tur, start, size in girdiler:
        if tur != 2:
            continue
        if size < cutoff:
            parca = b"".join(mini_stream[n * 64:(n + 1) * 64]
                             for n in sahiplen(zincir(start, minifat), kullanilan_mini, repr(ad))) if size else b""
        else:
            parca = b"".join(sektor(n, tam=False) for n in sahiplen(zincir(start, fat), kullanilan, repr(ad)))
        if len(parca) < size:  # kesik dosya: akışı kısaltıp "tam" diye vermek yerine bozuk say
            raise CfbHata(f"akış kısa: {ad!r} {len(parca)}/{size} bayt")
        akislar[ad] = parca[:size]
    return akislar


def _cstr(b: bytes, i: int) -> tuple[bytes, int]:
    j = b.index(b"\x00", i)
    return b[i:j], j + 1


def ole10native(akis: bytes) -> tuple[str, bytes]:
    """Packager (\\x01Ole10Native) akışı → (dosya adı, içerik). Biçim dışıysa ValueError."""
    try:
        i = 4  # toplam boy
        i += 2  # bayrak
        etiket, i = _cstr(akis, i)
        _kaynak, i = _cstr(akis, i)
        i += 4  # sabit (0x00030000)
        tlen = struct.unpack_from("<I", akis, i)[0]
        i += 4 + tlen
        dlen = struct.unpack_from("<I", akis, i)[0]
        i += 4
        if dlen > len(akis) - i:
            raise ValueError("içerik boyu akıştan büyük")
        icerik = akis[i:i + dlen]
        ad = etiket.decode("cp1254", "replace")
        # Yeni Packager sürümleri içerikten sonra UTF-16 kopyalar yazar: geçici yol, etiket, kaynak yol.
        j = i + dlen
        try:
            uni = []
            for _ in range(3):
                n = struct.unpack_from("<I", akis, j)[0]
                uni.append(akis[j + 4:j + 4 + 2 * n].decode("utf-16-le"))
                j += 4 + 2 * n
            if uni[1].strip():
                ad = uni[1]
        except (struct.error, UnicodeDecodeError):
            pass
        return ad, icerik
    except (ValueError, struct.error, IndexError) as exc:
        raise ValueError(f"Ole10Native biçimi okunamadı: {exc}") from None


def ooxml_uzanti(data: bytes) -> str | None:
    """Zip ise içeriğe bakıp .docx/.xlsx/.pptx; değilse None."""
    import io
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            adlar = z.namelist()
    except (zipfile.BadZipFile, zipfile.LargeZipFile, OSError, ValueError, EOFError):
        return None
    for onek, uz in (("word/", ".docx"), ("xl/", ".xlsx"), ("ppt/", ".pptx")):
        if any(a.startswith(onek) for a in adlar):
            return uz
    return ".zip"


def gomulu_coz(ad: str, data: bytes) -> tuple[str, bytes, str]:
    """Gömülü parça → (önerilen dosya adı, içerik, tür açıklaması). Tanınmazsa ham içerik + 'TANINMADI'.
    Tek bir bozuk gömülü nesne paketin tamamını düşürmez: beklenmeyen her hata ham kopya + TANINMADI olur."""
    taban = guvenli_ad(ad)
    try:
        return _gomulu_coz(taban, data)
    except Exception as exc:  # noqa: BLE001 — bilinçli geniş: girdi güvenilmez, tek nesne paketi düşürmesin
        return taban, data, f"TANINMADI — çözümlenemedi ({type(exc).__name__}: {exc}); ham kopya"


def _gomulu_coz(taban: str, data: bytes) -> tuple[str, bytes, str]:
    uz = ooxml_uzanti(data)
    if uz:
        return (taban if taban.lower().endswith(uz) else taban + uz), data, f"OOXML paketi ({uz})"
    if data[:8] == CFB_IMZA:
        try:
            akislar = cfb_akislari(data)
        except CfbHata as exc:
            return taban, data, f"TANINMADI — OLE okunamadı ({exc}); ham kopya"
        if "\x01Ole10Native" in akislar:
            try:
                p_ad, icerik = ole10native(akislar["\x01Ole10Native"])
                return guvenli_ad(p_ad, taban + ".bin"), icerik, "OLE paket nesnesi (asıl dosya çıkarıldı)"
            except ValueError as exc:
                return taban, data, f"TANINMADI — {exc}; ham kopya"
        if "Package" in akislar:
            uz2 = ooxml_uzanti(akislar["Package"]) or ".bin"
            return Path(taban).stem + uz2, akislar["Package"], f"OLE içinde OOXML paketi ({uz2})"
        return taban, data, "TANINMADI — OLE akışları: " + ", ".join(sorted(repr(k) for k in akislar)[:8]) + "; ham kopya"
    return taban, data, "doğrudan dosya (ham kopya)"

# ── BÖLÜM: docx ─────────────────────────────────────────────────────────────────────────────────────────────
W_SON = "wordprocessingml/2006/main}"
PARAGRAF_AYRACI = "\x00"  # yalnız bellekte; diske hücrede " ¶ ", paragrafta boşluk olarak yazılır


M_SON = "officeDocument/2006/math}"
A_SON = "drawingml/2006/main}"


def w(tag, ad: str) -> bool:
    """Öğe Word ana ad alanında `ad` mı? (DrawingML `a:t` gibi aynı yerel adlı başka öğeler sayılmaz.)"""
    return isinstance(tag, str) and tag.endswith(W_SON + ad)


def m_(tag, ad: str) -> bool:
    """Öğe Office Math (denklem) ad alanında `ad` mı?"""
    return isinstance(tag, str) and tag.endswith(M_SON + ad)


def _denklem_metni(el) -> str:
    return "".join((x.text or "") for x in el.iter() if m_(x.tag, "t")).replace("\r", " ").replace("\n", " ")


# Metin taşıyan çizim nesneleri: parça adı deseni (tür başına). Bağımsız sayım da AYNI desenle parça bulur ama
# metni ayrı (düzenli ifade) kodla sayar.
NESNE_PARCA = {
    "docx": {"diyagram": re.compile(r"^word/diagrams/data\d*\.xml$"),
             "grafik": re.compile(r"^word/charts/chart(?:Ex)?\d*\.xml$")},
    "xlsx": {"diyagram": re.compile(r"^xl/diagrams/data\d*\.xml$"),
             "grafik": re.compile(r"^xl/charts/chart(?:Ex)?\d*\.xml$"),
             "cizim": re.compile(r"^xl/drawings/drawing\d*\.xml$")},
}
NESNE_ETIKET = {"diyagram": ("D", "SmartArt"), "grafik": ("G", "grafik"), "metin_kutusu": ("K", "metin kutusu")}


_BOSLUK = re.compile(r"\s+")


def _temiz(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("\r", " ").replace("\n", " ")).strip()


# ── Evren: metin düğümleri (düzenli ifade; çıkarımın ElementTree yürüyüşünden ve parça listelerinden BAĞIMSIZ) ──
_ISLEMSIZ = re.compile(r"<!--.*?-->|<\?.*?\?>|<!DOCTYPE[^>]*>", re.S)
_CDATA = re.compile(r"<!\[CDATA\[(.*?)\]\]>", re.S)
_ATTR = r"""(?:[^>"'/]|/(?!>)|"[^"]*"|'[^']*')*"""   # öznitelik değerindeki '>' etiketi bitirmez
_ETIKET = re.compile(r"""<(?:[^>"']|"[^"]*"|'[^']*')*>""")
_AC_IC = re.compile(r"<((?:[\w.-]+:)?AlternateContent)\b%s>((?:(?!<(?:[\w.-]+:)?AlternateContent\b).)*?)</\1\s*>"
                    % _ATTR, re.S)
_BLOK = r"<((?:[\w.-]+:)?%s)\b" + _ATTR.replace("%", "%%") + r">.*?</\1\s*>"
_CHOICE = re.compile(_BLOK % "Choice", re.S)
_FALLBACK = re.compile(_BLOK % "Fallback", re.S)
_AC_DAL = re.compile(r"<(/?)(?:[\w.-]+:)?(Choice|Fallback)\b")
_ALT_AGAC_RE = {ad: re.compile(_BLOK % ad, re.S) for ad in YOK_ALT_AGAC}
_YAPRAK_RE = re.compile(r"<((?:[\w.-]+:)?(%s))\b%s>([^<]*)</\1\s*>" % ("|".join(YOK_YAPRAK), _ATTR))


def _xml_cozumle(veri: bytes) -> str:
    if veri[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return veri.decode("utf-16", "replace")
    return veri.decode("utf-8", "replace").lstrip("\ufeff")


def xml_gibi(veri: bytes) -> bool:
    """Üye içerikten XML'e benziyor mu (ilk anlamlı karakter `<`)? Adına bakılmaz. Boyut denetimi ilk parçayla çağırır."""
    return _xml_cozumle(veri).lstrip().startswith("<")


def xml_metni(veri: bytes) -> str | None:
    """Üye XML mi (içerikten, adından değil)? Öyleyse işlem talimatı/yorumu ayıklanmış metin; değilse None."""
    if not xml_gibi(veri):
        return None
    s = _ISLEMSIZ.sub("", _xml_cozumle(veri))
    return _CDATA.sub(lambda m: html.escape(m.group(1), quote=False), s)


def metin_dugumleri_re(s: str) -> list[str]:
    """Etiketler arasındaki metinler (öğe metni ve kuyruğu), varlıkları çözülmüş. İlk etiketten önceki ve son etiketten
    sonraki metin de dahildir (ayrıştırılabilir XML'de yalnız boşluktur; değilse sessizce düşmez)."""
    return [html.unescape(x) for x in _ETIKET.split(s)] if "<" in s else []


def metin_karakteri(s: str) -> int:
    return sum(bosluksuz(x) for x in metin_dugumleri_re(s))


def yok_sayilani_cikar(s: str, parca: str | None = None) -> tuple[str, dict[str, int]]:
    """Yok sayılan metni ayıklar → (net XML metni, {sınıf: karakter}). Fallback en içteki AlternateContent'ten başlayarak
    yalnız Choice'un NET metni (yok sayılan sınıflar hariç: ör. DrawingML konumu yalnız Choice'ta durur; boşluklar
    atılmış metin düğümü dizisi) Fallback'inkiyle AYNIYSA düşülür — karakter sayısı eşitliği yetmez ("Onay: 5 gün" ile
    "İade: 9 gün" farklıdır); iç blokta düşülen, dış bloğun karşılaştırmasına girmez. Düşülen Fallback'in tüm metni
    yinelenen gösterim sınıfına yazılır."""
    yok = dict.fromkeys(YOK_SINIFLAR, 0)

    def net_metin(blok: str) -> str:
        for desen in _ALT_AGAC_RE.values():
            blok = desen.sub("", blok)
        blok = _YAPRAK_RE.sub(lambda m: "" if yaprak_sinifi(m.group(2), parca, html.unescape(m.group(3)))
                              else m.group(0), blok)
        return _BOSLUK.sub("", "".join(metin_dugumleri_re(blok)))

    def ac(m: re.Match) -> str:
        ic = m.group(2)
        choice = "".join(net_metin(b.group(0)) for b in _CHOICE.finditer(ic))
        fb_net = "".join(net_metin(b.group(0)) for b in _FALLBACK.finditer(ic))
        if fb_net and choice == fb_net:
            yok[YOK_FALLBACK] += sum(metin_karakteri(b.group(0)) for b in _FALLBACK.finditer(ic))
            ic = _FALLBACK.sub("", ic)
        # İç blok çözüldü; dıştaki bir sonraki turda eşleşir. Kalan Choice/Fallback etiketleri yeniden adlandırılır:
        # yoksa dış bloğun tembel Choice deseni içtekinin kapanışında durur ve dış Choice'u yarım ölçer (ölçüldü:
        # wp14 konum bloğu içeren metin kutusunda Fallback düşülmedi, ElementTree tarafıyla ayrıştı).
        return "<_ac_cozuldu>%s</_ac_cozuldu>" % _AC_DAL.sub(r"<\1_\2_cozuldu", ic)

    while True:
        yeni = _AC_IC.sub(ac, s)
        if yeni == s:
            break
        s = yeni
    for ad, desen in _ALT_AGAC_RE.items():
        yok[YOK_ALT_AGAC[ad]] += sum(metin_karakteri(b.group(0)) for b in desen.finditer(s))
        s = desen.sub("", s)

    def yaprak(m: re.Match) -> str:
        sinif = yaprak_sinifi(m.group(2), parca, html.unescape(m.group(3)))
        if sinif is None:
            return m.group(0)
        yok[sinif] += bosluksuz(html.unescape(m.group(3)))
        return ""
    s = _YAPRAK_RE.sub(yaprak, s)
    return s, yok


def muaf_nedeni(ad: str, metinler: dict[str, str] | None = None) -> str | None:
    """Yapısal parça mı? SmartArt önbellek çizimi (diagrams/drawingN) YALNIZ metin düğümleri aynı paketteki SmartArt
    veri parçalarınınkilerin alt kümesiyse muaftır (yineleme bu girdide ölçülür); değilse geri düşüşe gider."""
    for neden, desen in MUAF_RE:
        if desen.search(ad):
            return neden
    if metinler is not None and re.match(r"^(word|xl)/diagrams/drawing\d*\.xml$", ad) and ad in metinler:
        def dugumler(s: str) -> set[str]:
            return {_temiz(x) for x in metin_dugumleri_re(s) if bosluksuz(x)}
        veri: set[str] = set()
        for a, s in metinler.items():
            if re.match(r"^(word|xl)/diagrams/data\d*\.xml$", a):
                veri |= dugumler(s)
        if dugumler(metinler[ad]) <= veri:
            return "SmartArt önbellek çizimi (metni veri parçasını yineler — bu girdide ölçüldü)"
    return None


XML_BOZUK_NOTU = ("XML gibi başlıyor, ayrıştırılamadı (%s) — metni düzenli ifadeyle geri düşüşe alındı; bu parçayı "
                  "kullanıcıyla doğrula")
IKILI_ATLANDI_NOTU = "ÖLÇÜLEMEDİ — boyut: %s; okunmadı"


def ikili_atlanma_nedeni(n: int) -> str:
    return ("açılınca %d bayttan fazla (sınır %d)" % (MAX_UYE, MAX_UYE) if n > MAX_UYE else
            "XML olmayan ikili üyelerin toplamı %d bayt sınırını aşıyor (bu üye %d bayt)" % (MAX_IKILI_TOPLAM, n))


def xml_disi_notu(ad: str) -> str:
    if ad.startswith("word/glossary/") and Path(ad).suffix.lower() in GORSEL_UZANTILARI:
        return "sözlük/yapı taşı görseli — belge gövdesinde görünmez (KG sayılmaz, not istenmez)"
    if re.search(r"(^|/)fonts/[^/]+\.odttf$", ad, re.I):
        return "gömülü yazı tipi (karartılmış yazı tipi dosyası; metin taşımaz)"
    if re.search(r"(^|/)vbaProject\.bin$", ad, re.I):
        return "makro kodu (VBA) — okunmadı, iş kuralı içerebilir; kullanıcıya sor"
    if re.search(r"(^|/)printerSettings/", ad):
        return "yazıcı ayarı (ikili)"
    if re.match(r"^docProps/thumbnail\.", ad, re.I):  # Office şablonlarında `Thumbnail.jpeg` (ölçüldü)
        return "belge küçük resmi (ilk sayfa önizlemesi)"
    return "XML değil — metni çıkarılmadı"


def xml_uyeleri(z: zipfile.ZipFile, atla: set[str] | frozenset = frozenset(),
                disi: list[dict] | None = None) -> dict[str, str]:
    """Zip'teki HER üye gezilir (parça listesi yok); XML olanlar {ad: metin}. Dosya olarak çıkan üyeler (görsel,
    gömülü, altChunk) ve boyut sınırıyla atlananlar hariç. XML olmayan üye sessizce atlanmaz: `disi` verilirse
    {parca, boyut, not} olarak eklenir (INDEX ve paket.json listeler). XML gibi başlayıp ayrıştırılamayan üye hem oraya
    yazılır hem metniyle döner (evrene girer; geri düşüş düzenli ifadeyle düz metin düğümlerini yazar). Boyut sınırıyla
    atlanan XML olmayan üye (`atla` sözlükse bayt sayısıyla) ÖLÇÜLEMEDİ notuyla listelenir."""
    dosya = dosya_uyeleri(z)
    haric = _afchunk_hedefleri(z)
    out: dict[str, str] = {}
    for bilgi in z.infolist():
        ad = bilgi.filename
        if ad.endswith("/") or ad in dosya or ad in haric:
            continue
        if ad in atla:
            if disi is not None:
                n = atla[ad] if isinstance(atla, dict) else bilgi.file_size
                disi.append({"parca": ad, "boyut": n, "not": IKILI_ATLANDI_NOTU % ikili_atlanma_nedeni(n)})
            continue
        veri = z.read(ad)
        s = xml_metni(veri)
        if s is not None:
            try:
                ET.fromstring(veri)
            except ET.ParseError as exc:  # listelenir VE metni evrende kalır (geri düşüş düz düğümlerle yazar)
                if disi is not None:
                    disi.append({"parca": ad, "boyut": len(veri), "not": XML_BOZUK_NOTU % exc})
            out[ad] = s
        elif disi is not None:
            disi.append({"parca": ad, "boyut": len(veri), "not": xml_disi_notu(ad)})
    return out


def _gorsel_uyeleri(z: zipfile.ZipFile, kok: str) -> list[str]:
    """`kok` (word | xl) altındaki görsel üyeleri: media/ klasörü + herhangi bir parçanın görsel (image) ilişkisinin iç
    hedefi + görsel uzantılı üye. embeddings/ hariç (gömülü nesnedir). Klasör adına bağlı değil (`word/images/…`)."""
    adlar = {a for a in z.namelist() if not a.endswith("/")}
    out = {a for a in adlar if a.startswith(kok + "/media/")}
    out |= {a for a in adlar if a.startswith(kok + "/") and Path(a).suffix.lower() in GORSEL_UZANTILARI}
    govde_ref = set()
    for rels in adlar:
        if rels.startswith(kok + "/") and rels.endswith(".rels") and "_rels/" in rels:
            parca = rels.replace("_rels/", "", 1)[:-len(".rels")]
            try:
                hedefler = parca_iliskileri(z, parca).values()
            except ET.ParseError:
                continue
            gorsel = {h for tip, h in hedefler if tip.lower() == "image" and h in adlar}
            out |= gorsel
            if not rels.startswith(kok + "/glossary/"):
                govde_ref |= gorsel
    # word/glossary/: yapı taşı (sözlük) belgesi — klasöründeki görsel, gövde parçaları (belge, üst/altbilgi …)
    # başvurmadıkça belgede görünmez; XML dışı üye olarak listelenir. Gövdenin başvurduğu sözlük görseli KG'dir.
    # (media/ altındaki görsel yalnız sözlükten anılsa da KG kalır: dışlanırsa ne KG ne XML dışı listesinde görünürdü.)
    sozluk = {a for a in out if a.startswith(kok + "/glossary/")} - govde_ref
    return sorted(a for a in out if not a.startswith(kok + "/embeddings/") and a not in sozluk)


def dosya_uyeleri(z: zipfile.ZipFile) -> frozenset:
    """Dosya olarak çıkan üyeler (görsel KG + gömülü KN): içerikleri evrene girmez, boyutları ayrı paydan sayılır."""
    return frozenset(_gorsel_uyeleri(z, "word") + _gorsel_uyeleri(z, "xl")
                     + [a for a in z.namelist() if DOSYA_PARCA.match(a) and not a.endswith("/")])


def svg_yedekleri(z: zipfile.ZipFile) -> dict[str, str]:
    """SVG görselin PNG yedeği: `a:blip r:embed` (PNG) içinde `asvg:svgBlip r:embed` (SVG) → {svg üyesi: png üyesi}.
    Word/Excel SVG'yi böyle saklar; PNG aynı görselin yedeğidir."""
    out: dict[str, str] = {}
    for ad in z.namelist():
        if not ad.endswith(".xml") or not ad.startswith(("word/", "xl/")):
            continue
        veri = z.read(ad)
        if b"svgBlip" not in veri:
            continue
        try:
            kok = ET.fromstring(veri)
            rels = parca_iliskileri(z, ad)
        except ET.ParseError:
            continue
        for el in kok.iter():
            if yerel(el.tag) != "blip":
                continue
            png = rels.get(attr_yerel(el, "embed") or "", ("", ""))[1]
            for alt in el.iter():
                if yerel(alt.tag) == "svgBlip":
                    svg = rels.get(attr_yerel(alt, "embed") or "", ("", ""))[1]
                    if png and svg and png != svg:
                        out.setdefault(svg, png)
    return out


def evren_tara(z: zipfile.ZipFile, atla: set[str] | frozenset = frozenset(),
               disi: list[dict] | None = None) -> dict[str, dict]:
    """Her XML üyesi için {evren, net (evren − yok sayılan), yok {sınıf: karakter}, muaf (neden | None)}. XML olmayan
    üyeler `disi`'ye yazılır."""
    metinler = xml_uyeleri(z, atla, disi)
    out = {}
    for ad, s in metinler.items():
        net, yok = yok_sayilani_cikar(s, ad)
        out[ad] = {"evren": metin_karakteri(s), "net": metin_karakteri(net), "yok": yok,
                   "muaf": muaf_nedeni(ad, metinler)}
    return out

# ── Çıkarım tarafı: ElementTree ile metin düğümü sınıflama (tüketilen / yok sayılan / geri düşüş) ──
GRUP_ADLARI = ("p", "si")   # geri düşüşte metin düğümleri en yakın paragraf ya da paylaşılan dizge altında birleşir


def _fallback_dusen(kok, parca: str | None = None) -> set[int]:
    """Yok sayılacak mc:Fallback öğeleri: en içteki AlternateContent'ten başlayarak, Choice'un NET metni (içte düşülenler
    ve yok sayılan sınıflar hariç, boşluklar atılmış) Fallback'inkiyle AYNIYSA. Evren tarafındaki `yok_sayilani_cikar`
    ile aynı kural."""
    dusen: set[int] = set()

    def etkin(el) -> str:
        if id(el) in dusen or yerel(el.tag) in YOK_ALT_AGAC:
            return ""
        oz = "" if len(el) == 0 and yaprak_sinifi(yerel(el.tag), parca, el.text) else _BOSLUK.sub("", el.text or "")
        return oz + "".join(etkin(c) + _BOSLUK.sub("", c.tail or "") for c in el)

    def sonra(el) -> None:
        for c in el:
            sonra(c)
        if yerel(el.tag) == "AlternateContent":
            choice = "".join(etkin(c) for c in el if yerel(c.tag) == "Choice")
            fb = [c for c in el if yerel(c.tag) == "Fallback"]
            fb_k = "".join(etkin(c) for c in fb)
            if fb_k and choice == fb_k:
                dusen.update(id(c) for c in fb)

    sonra(kok)
    return dusen


def metin_dugumleri(kok, tuketilen: set[int] = frozenset(), parca: str | None = None) -> tuple[list[str], dict[str, int]]:
    """Ağacın her metin düğümünü sınıflar → (geri düşüş grupları, {yok sayılan sınıf: karakter}). `tuketilen` = metni
    yapılandırılmış satıra girmiş öğelerin id'leri. Sınıf kuralları evren tarafındaki düzenli ifadelerle aynıdır."""
    gruplar: dict[int, list[str]] = {}
    yok = dict.fromkeys(YOK_SINIFLAR, 0)

    def ekle(grup: int, s: str | None) -> None:
        if s and bosluksuz(s):
            gruplar.setdefault(grup, []).append(s)

    def say(sinif: str, s: str | None) -> None:
        yok[sinif] += bosluksuz(s or "")

    dusen = _fallback_dusen(kok, parca)

    def yuru(el, sinif: str | None, grup: int | None) -> None:
        ad = yerel(el.tag)
        if sinif is None and ad in YOK_ALT_AGAC:
            sinif = YOK_ALT_AGAC[ad]
        yaprak = yaprak_sinifi(ad, parca, el.text) if sinif is None and len(el) == 0 else None
        if ad in GRUP_ADLARI:
            grup = id(el)
        if sinif or yaprak:
            say(sinif or yaprak, el.text)
        elif id(el) not in tuketilen:
            ekle(grup if grup is not None else id(el), el.text)
        for c in el:
            yuru(c, YOK_FALLBACK if id(c) in dusen else sinif, grup)
            if sinif:
                say(sinif, c.tail)
            else:
                ekle(grup if grup is not None else id(el), c.tail)

    yuru(kok, None, None)
    return [_temiz("".join(g)) for g in gruplar.values() if bosluksuz("".join(g))], yok


def _a_t(x) -> bool:
    return isinstance(x.tag, str) and x.tag.endswith(A_SON + "t")


def nesne_secimi(kok, tur: str) -> list[list]:
    """Yapılandırılmış nesne satırının hücreleri (öğe listeleri). SmartArt: her DrawingML paragrafının `a:t`'leri ·
    grafik: her yaprak `t` / `v` / `pt` (başlık, seri adı, kategori, değer; ChartEx kategorileri `cx:pt`) ·
    çizim (xlsx metin kutusu): her `txBody` içindeki paragrafların `a:t`'leri."""
    if tur == "diyagram":
        return [[x for x in p.iter() if _a_t(x)] for p in kok.iter() if isinstance(p.tag, str)
                and p.tag.endswith(A_SON + "p")]
    return [[x] for x in kok.iter() if yerel(x.tag) in ("t", "v", "pt") and len(x) == 0]


def kutu_secimi(kok) -> list[list[list]]:
    out = []
    for tb in kok.iter():
        if yerel(tb.tag) == "txBody":
            out.append([[x for x in p.iter() if _a_t(x)] for p in tb.iter() if isinstance(p.tag, str)
                        and p.tag.endswith(A_SON + "p")])
    return out


def _hucre(ogeler: list) -> str:
    return _temiz("".join((x.text or "") for x in ogeler))


def nesne_hucreleri(z: zipfile.ZipFile, parca: str, tur: str) -> list[str]:
    """Nesne satırının hücre metinleri; boş hücre yazılmaz."""
    kok = ET.fromstring(z.read(parca))
    return [h for h in (_hucre(o) for o in nesne_secimi(kok, tur)) if bosluksuz(h)]


def cizim_kutulari(z: zipfile.ZipFile, parca: str) -> list[list[str]]:
    """xlsx çizim parçasındaki metin kutuları: her `txBody` bir kutu, her DrawingML paragrafı bir hücre."""
    kok = ET.fromstring(z.read(parca))
    out = []
    for kutu in kutu_secimi(kok):
        hucreler = [h for h in (_hucre(o) for o in kutu) if bosluksuz(h)]
        if hucreler:
            out.append(hucreler)
    return out


def tuketilen_idler(gruplar) -> set[int]:
    """İç içe öğe listelerinin id kümesi (yapılandırılmış satıra giren metin öğeleri)."""
    out: set[int] = set()
    for g in gruplar:
        if isinstance(g, list):
            out |= tuketilen_idler(g)
        else:
            out.add(id(g))
    return out


def nesne_yapilandir(c: "Cikti", z: zipfile.ZipFile, parca: str, tur: str, no: int) -> None:
    """SmartArt/grafik parçası → KM satırı; satıra girmeyen metin düğümleri geri düşüşe. Okunamayan parça 'metin
    alınmadı' der ve geri düşüşe de gitmez: evren metni bulursa parça hesabı FAIL verir."""
    try:
        hucreler = nesne_hucreleri(z, parca, tur)
        kok = ET.fromstring(z.read(parca))
    except ET.ParseError:
        nesne_satiri(c, tur, no, parca, None)
        c.artik[parca] = ([], "yapılandırılmış parça okunamadı — metin alınmadı")
        return
    nesne_satiri(c, tur, no, parca, hucreler)
    parca_artigi(c, parca, kok, tuketilen_idler(nesne_secimi(kok, tur)))


def parca_artigi(c: "Cikti", parca: str, kok, tuk: set[int]) -> None:
    """Yapılandırılmış bir parçanın satıra girmeyen metin düğümleri → geri düşüş (parça daha önce işlendiyse eklenir)."""
    gruplar, _yok = metin_dugumleri(kok, tuk, parca)
    eski = c.artik.get(parca, ([], ""))[0]
    c.artik[parca] = (eski + gruplar, "yapılandırılmış parçanın artığı")


def geri_dusus_yaz(c: "Cikti", z: zipfile.ZipFile) -> None:
    """Yapılandırılmamış her XML parçası (muaf değil) + yapılandırılmış parçaların artığı → metin.md sonunda ham
    bölüm. Parça listesi YOKTUR: zip'teki her XML üyesi gezilir; yapılandırılmış çıkarımın işlemediği her parça buraya
    gelir. Ayrıştırılamayan parça (XML gibi başlayan ama ET'nin okuyamadığı) düzenli ifadeyle düz metin düğümleri olarak
    yazılır — ilk etiketten önceki ve sonuncudan sonraki metin dahil — ve INDEX'te "XML gibi başlıyor" notuyla ayrıca
    listelenir."""
    metinler = xml_uyeleri(z, set(c.atlanan))
    for ad in sorted(metinler):
        if ad in c.artik or muaf_nedeni(ad, metinler):
            continue
        try:
            gruplar, _yok = metin_dugumleri(ET.fromstring(z.read(ad)), parca=ad)
            c.artik[ad] = (gruplar, "yapılandırılmamış parça")
        except ET.ParseError:
            net, _yok = yok_sayilani_cikar(metinler[ad], ad)
            c.artik[ad] = ([_temiz(x) for x in metin_dugumleri_re(net) if bosluksuz(x)],
                           "ayrıştırılamadı — düz metin düğümleri")
    baslik = ["", "## Yapılandırılmamış parça metni (ham — yapılandırılmış çıkarımın kapsamadığı XML metni; parça "
              "başına metin düğümleri belge sırasıyla, paragraf altında birleşik)", ""]
    for ad, (gruplar, notu) in c.artik.items():
        if not gruplar:
            continue
        pid = "P%02d" % (len(c.geri) + 1)
        c.satirlar += baslik
        baslik = []
        kimlikler = []
        for g in gruplar:
            kid = c.km_yeni()
            kimlikler.append(kid)
            c.satirlar.append("[%s] ⟦%s parça: %s⟧ | %s |" % (kid, pid, gorunur(ad), _tablo_kacis(g)))
        c.geri.append((pid, ad, kimlikler, notu))


def nesne_satiri(c: "Cikti", tur: str, no: int, parca: str, hucreler: list[str] | None) -> None:
    """Metinli nesne = bir KM satırı (hücreler tablo satırı gibi kaçırılır); metinsiz nesne yalnız işaret satırı;
    okunamayan parça (hucreler None) işaret satırında 'metin alınmadı' der — bağımsız sayım metin bulursa FAIL olur."""
    harf, etiket = NESNE_ETIKET[tur]
    isaret = "⟦%s%02d %s: %s⟧" % (harf, no, etiket, gorunur(parca))
    if hucreler:
        c.satirlar.append("[%s] %s | %s |" % (c.km_yeni(), isaret, " | ".join(_tablo_kacis(h) for h in hucreler)))
    else:
        c.satirlar.append("%s %s" % (isaret, "metin yok" if hucreler is not None else "metin alınmadı (parça okunamadı)"))
    c.nesneler.append(("%s%02d" % (harf, no), etiket, gorunur(parca)))


class Cikti:
    """Çıkarımın bellek içi sonucu; paket diske bundan yazılır, doğrulama ise diskten okur."""

    def __init__(self, tur: str):
        self.tur = tur
        self.satirlar: list[str] = []
        self.km = 0
        self.gorseller: list[tuple[str, str, str]] = []           # (KG id, zip parçası, paket dosyası)
        self.gomululer: list[tuple[str, str, str, bytes, str]] = []  # (KN id, zip parçası, dosya, içerik, tür)
        self.notlar: list[str] = []
        self.sayfalar: list[str] = []
        self.nesneler: list[tuple[str, str, str]] = []  # (D01/G01/K01, etiket, kaynak parçası)
        self.artik: dict[str, tuple[list[str], str]] = {}  # parça → (geri düşüş grupları, not); sıra korunur
        self.geri: list[tuple[str, str, list[str], str]] = []  # (P01, parça, KM kimlikleri, not)
        self.gorsel_bilgi: list[dict] = []  # okunacak görseller (gorsel_listesi) — paketi_yaz doldurur
        self.not_durumu = ""
        self.xml_disi: list[dict] = []  # XML olmayan zip üyeleri (ör. vbaProject.bin) — metni çıkarılmaz, listelenir
        self.atlanan: dict[str, int] = {}  # boyut sınırıyla atlanan görsel/gömülü/ikili üye → okunan bayt (> sınır)
        self.svg_yedek: dict[str, str] = {}  # SVG görsel üyesi → aynı görselin PNG yedeği üyesi (svgBlip)
        self.harici_gorsel = 0  # pakette olmayan, dışa bağlı görsel sayısı (a:blip r:link)

    def km_yeni(self) -> str:
        self.km += 1
        return "KM-%04d" % self.km


def parca_iliskileri(z: zipfile.ZipFile, parca: str) -> dict[str, tuple[str, str]]:
    """rId → (ilişki tipinin son parçası, zip içi hedef yol). Dış hedefler atlanır."""
    klasor, ad = parca.rsplit("/", 1) if "/" in parca else ("", parca)
    rels = (klasor + "/" if klasor else "") + "_rels/" + ad + ".rels"
    try:
        kok = ET.fromstring(z.read(rels))
    except KeyError:
        return {}
    out = {}
    for r in kok:
        if (r.get("TargetMode") or "").lower() == "external":
            continue
        hedef = r.get("Target", "")
        yol = hedef.lstrip("/") if hedef.startswith("/") else os.path.normpath(
            os.path.join(klasor, hedef)).replace("\\", "/")
        out[r.get("Id", "")] = ((r.get("Type") or "").rsplit("/", 1)[-1], yol)
    return out


def stil_seviyeleri(z: zipfile.ZipFile) -> dict[str, int]:
    """Paragraf stil kimliği → başlık seviyesi (1-9). Ad ('heading 2', 'Başlık 2', 'Title') ya da outlineLvl;
    basedOn zinciri izlenir. Türkçe Word'ün 'Balk1' gibi kimlikleri ad üzerinden yakalanır."""
    try:
        kok = ET.fromstring(z.read("word/styles.xml"))
    except KeyError:
        return {}
    ham: dict[str, tuple[int | None, str | None]] = {}
    for st in kok:
        if not w(st.tag, "style") or attr_yerel(st, "type") != "paragraph":
            continue
        sid = attr_yerel(st, "styleId") or ""
        seviye, temel = None, None
        for c in st:
            if w(c.tag, "name"):
                ad = (attr_yerel(c, "val") or "").lower().replace("İ", "i")
                m = re.match(r"^(?:heading|başlık|baslik)\s*(\d)$", ad)
                if m:
                    seviye = int(m.group(1))
                elif ad in ("title", "konu başlığı", "konu basligi"):
                    seviye = 1
            elif w(c.tag, "basedOn"):
                temel = attr_yerel(c, "val")
            elif w(c.tag, "pPr"):
                for o in c:
                    if w(o.tag, "outlineLvl"):
                        v = attr_yerel(o, "val") or ""
                        if v.isdigit() and int(v) < 9 and seviye is None:
                            seviye = int(v) + 1
        ham[sid] = (seviye, temel)
    out: dict[str, int] = {}
    for sid in ham:
        s, adim, cur = None, 0, sid
        while cur in ham and adim < 20:
            if ham[cur][0] is not None:
                s = ham[cur][0]
                break
            cur, adim = ham[cur][1], adim + 1
        if s:
            out[sid] = s
    return out


def _yuru(el, parcalar: list[str], nesneler: list[tuple[str, str]], tuk: set[int] | None = None):
    """Metni ve nesne başvurularını belge sırasıyla toplar; mc:Fallback (yinelenen eski gösterim) atlanır. `tuk` metni
    satıra giren öğelerin id'lerini toplar; satıra girmeyen metin düğümleri sonra geri düşüşe gider (ya da yok sayılan
    sınıftadır: Choice'a eşit Fallback, instrText, delText)."""
    tuk = set() if tuk is None else tuk
    for c in el:
        t = yerel(c.tag)
        if t == "Fallback" or w(c.tag, "pPr") or w(c.tag, "rPr") or w(c.tag, "instrText") or w(c.tag, "delText"):
            continue
        if w(c.tag, "t"):
            parcalar.append((c.text or "").replace("\r", " ").replace("\n", " "))
            tuk.add(id(c))
            continue
        if m_(c.tag, "oMath"):
            tuk.update(id(x) for x in c.iter() if m_(x.tag, "t"))
            metin = _denklem_metni(c)
            if bosluksuz(metin):
                parcalar.append(" %s %s " % (DENKLEM, metin))
            continue
        if t == "relIds" and attr_yerel(c, "dm"):
            nesneler.append(("diyagram", attr_yerel(c, "dm")))
        elif t == "chart" and attr_yerel(c, "id"):
            nesneler.append(("grafik", attr_yerel(c, "id")))
        if w(c.tag, "tab") or w(c.tag, "br") or w(c.tag, "cr"):
            parcalar.append(" ")
            continue
        if w(c.tag, "p") and any(p.strip() for p in parcalar):
            parcalar.append(PARAGRAF_AYRACI)
        if t == "blip":
            rid = attr_yerel(c, "embed")
            if rid:
                nesneler.append(("gorsel", rid))
            elif attr_yerel(c, "link"):  # dışa bağlı görsel (TargetMode External): pakette dosyası yok
                nesneler.append(("harici", attr_yerel(c, "link")))
        elif t == "imagedata":
            rid = attr_yerel(c, "id")
            if rid:
                nesneler.append(("gorsel", rid))
        elif t == "OLEObject":
            rid = attr_yerel(c, "id")
            if rid:
                nesneler.append(("gomulu", rid))
        _yuru(c, parcalar, nesneler, tuk)


def _tablo_kacis(s: str) -> str:
    """Hücre metni: kaynaktaki \\ | ¶ ters bölüyle kaçırılır, sonra paragraf ayracı ¶ olur (sayım ikisini ayırır)."""
    return re.sub(r"([\\|¶])", r"\\\1", s).replace(PARAGRAF_AYRACI, " ¶ ")


def _satirlar(el):
    """Tablonun satırları (sdt/customXml sarmalı içindekiler dahil); iç içe tablonun satırları hariç."""
    for c in el:
        if w(c.tag, "tr"):
            yield c
        elif not w(c.tag, "tbl") and not w(c.tag, "tc"):
            yield from _satirlar(c)


def _hucreler(el):
    for c in el:
        if w(c.tag, "tc"):
            yield c
        elif not w(c.tag, "tbl") and not w(c.tag, "tr"):
            yield from _hucreler(c)


def atlanan_dosya(c: Cikti, kid: str, ad: str) -> tuple[str, str] | None:
    """Boyut sınırıyla atlanan görsel/gömülü üye → (yer tutucu dosya adı, tür notu); atlanmadıysa None."""
    if ad not in c.atlanan:
        return None
    neden = ("açılınca %d bayttan fazla (sınır %d)" % (MAX_UYE, MAX_UYE) if c.atlanan[ad] > MAX_UYE else
             "görsel/gömülü üyelerin toplamı %d bayt sınırını aşıyor (bu üye %d bayt)" % (MAX_DOSYA_TOPLAM, c.atlanan[ad]))
    return ("%s_%s.OLCULEMEDI.txt" % (kid, guvenli_ad(ad)),
            "ÖLÇÜLEMEDİ — boyut: %s; dosya çıkarılmadı, kaynağı aç" % neden)


def docx_cikar(z: zipfile.ZipFile, atla: dict[str, int] | None = None) -> Cikti:
    try:
        govde_xml = z.read("word/document.xml")
    except KeyError:
        raise Okunamadi("word/document.xml yok — .docx değil ya da bozuk") from None
    try:
        kok = ET.fromstring(govde_xml)
    except ET.ParseError as exc:
        raise Okunamadi(f"word/document.xml ayrıştırılamadı: {exc}") from None
    govde = next((c for c in kok if w(c.tag, "body")), None)
    if govde is None:
        raise Okunamadi("belge gövdesi (body) yok")
    c = Cikti("docx")
    c.atlanan = dict(atla or {})
    rels = parca_iliskileri(z, "word/document.xml")
    stiller = stil_seviyeleri(z)
    adlar = z.namelist()

    kg_by = {}
    c.svg_yedek = svg_yedekleri(z)
    for i, ad in enumerate(_gorsel_uyeleri(z, "word"), 1):
        kid = "KG-%02d" % i
        dosya = (atlanan_dosya(c, kid, ad) or ("%s_%s" % (kid, guvenli_ad(ad)),))[0]
        c.gorseller.append((kid, ad, dosya))
        kg_by[ad] = (kid, "media/" + dosya)
    gomulu_adlar = sorted(a for a in adlar if a.startswith("word/embeddings/") and not a.endswith("/"))
    gomulu_adlar += sorted({h for tip, h in rels.values() if tip.lower() == "afchunk" and h in adlar})
    kn_by = {}
    for i, ad in enumerate(gomulu_adlar, 1):
        kid = "KN-%02d" % i
        yt = atlanan_dosya(c, kid, ad)
        if yt:
            dosya, icerik, tur = yt[0], yt[1].encode("utf-8"), yt[1]
        else:
            p_ad, icerik, tur = gomulu_coz(ad, z.read(ad))
            dosya = "%s_%s" % (kid, p_ad)
        c.gomululer.append((kid, ad, dosya, icerik, tur))
        kn_by[ad] = (kid, "gomulu/" + dosya)

    nesne_by: dict[str, tuple[str, int]] = {}
    for tur, desen in NESNE_PARCA["docx"].items():
        for i, ad in enumerate(sorted(a for a in adlar if desen.match(a)), 1):
            nesne_by[ad] = (tur, i)
    yazilan_nesne: set[str] = set()

    def nesne_yaz(parca: str) -> None:
        if parca in yazilan_nesne:
            return
        yazilan_nesne.add(parca)
        tur, no = nesne_by[parca]
        nesne_yapilandir(c, z, parca, tur, no)

    def notlar_metni(nesneler) -> tuple[str, list[str]]:
        """(satır sonu işaretleri, bu satırdan SONRA yazılacak metinli nesne parçaları)."""
        out, sonra = [], []
        for tur, rid in nesneler:
            hedef = rels.get(rid, ("", ""))[1]
            if tur == "gorsel" and hedef in kg_by:
                out.append("⟦%s görsel: %s⟧" % kg_by[hedef])
            elif tur == "gomulu" and hedef in kn_by:
                out.append("⟦%s gömülü: %s⟧" % kn_by[hedef])
            elif tur == "harici":
                out.append(HARICI_GORSEL)
                c.harici_gorsel += 1
            elif tur in ("diyagram", "grafik") and hedef in nesne_by:
                harf, _etiket = NESNE_ETIKET[tur]
                out.append("⟦%s%02d sonraki satırda⟧" % (harf, nesne_by[hedef][1]))
                sonra.append(hedef)
            else:
                out.append("⟦%s başvurusu çözülemedi: %s⟧" % (tur, gorunur(rid)))
        return " ".join(dict.fromkeys(out)), list(dict.fromkeys(sonra))

    sayac = {"tablo": 0}
    tuk: set[int] = set()

    def paragraf(p):
        parcalar, nesneler = [], []
        _yuru(p, parcalar, nesneler, tuk)
        metin = re.sub(r"\s+", " ", "".join(parcalar).replace(PARAGRAF_AYRACI, " ")).strip()
        ek, sonra = notlar_metni(nesneler)
        seviye, liste = None, False
        ppr = next((x for x in p if w(x.tag, "pPr")), None)
        if ppr is not None:
            for x in ppr:
                if w(x.tag, "pStyle"):
                    seviye = stiller.get(attr_yerel(x, "val") or "")
                elif w(x.tag, "outlineLvl"):
                    v = attr_yerel(x, "val") or ""
                    seviye = int(v) + 1 if v.isdigit() and int(v) < 9 else None
                elif w(x.tag, "numPr"):
                    liste = True
        if metin:
            kid = c.km_yeni()
            if seviye:
                c.satirlar.append("%s [%s] %s%s" % ("#" * min(seviye, 6), kid, metin, (" " + ek) if ek else ""))
            else:
                c.satirlar.append("[%s] %s%s%s" % (kid, "⟦liste⟧ " if liste else "", metin, (" " + ek) if ek else ""))
        elif ek:
            c.satirlar.append(ek)
        for parca in sonra:
            nesne_yaz(parca)

    def tablo(tbl):
        sayac["tablo"] += 1
        tno = sayac["tablo"]
        satirlar = list(_satirlar(tbl))
        ic_ice = any(w(x.tag, "tbl") for tr in satirlar for x in tr.iter())
        c.satirlar.append("")
        c.satirlar.append("**Tablo T%02d** — %d satır%s" % (tno, len(satirlar),
                                                         " (iç içe tablo hücre metnine düzleştirildi)" if ic_ice else ""))
        for sno, tr in enumerate(satirlar, 1):
            hucre_metinleri, nesneler = [], []
            for tc in _hucreler(tr):
                parcalar = []
                _yuru(tc, parcalar, nesneler, tuk)
                hucre_metinleri.append(re.sub(r"\s+", " ", "".join(parcalar)).strip())
            ek, sonra = notlar_metni(nesneler)
            if any(bosluksuz(h.replace(PARAGRAF_AYRACI, "")) for h in hucre_metinleri):
                kid = c.km_yeni()
                c.satirlar.append("[%s] ⟦T%02d.S%02d⟧ | %s |%s" % (
                    kid, tno, sno, " | ".join(_tablo_kacis(h) for h in hucre_metinleri), (" " + ek) if ek else ""))
            elif ek:
                c.satirlar.append("⟦T%02d.S%02d⟧ %s" % (tno, sno, ek))
            for parca in sonra:
                nesne_yaz(parca)
        c.satirlar.append("")

    def kapsayici(el):
        for x in el:
            if w(x.tag, "p"):
                paragraf(x)
            elif w(x.tag, "tbl"):
                tablo(x)
            elif w(x.tag, "altChunk"):
                hedef = rels.get(attr_yerel(x, "id") or "", ("", ""))[1]
                c.satirlar.append("⟦%s gömülü (altChunk): %s⟧" % kn_by[hedef] if hedef in kn_by
                                  else "⟦altChunk başvurusu çözülemedi⟧")
            elif w(x.tag, "sectPr") or w(x.tag, "sdtPr") or w(x.tag, "sdtEndPr"):
                continue
            else:
                kapsayici(x)

    kapsayici(govde)
    kalan = [a for a in sorted(nesne_by, key=lambda a: (nesne_by[a][0], nesne_by[a][1])) if a not in yazilan_nesne]
    if kalan:
        c.satirlar += ["", "## Gövdede konumu bulunamayan metin nesneleri (üst/altbilgi ya da başka parçadan bağlı)", ""]
        for parca in kalan:
            nesne_yaz(parca)
    # Gövde parçasının satıra girmeyen metni (çizim konumu dışında tanınmayan her şey) geri düşüşe gider; sonra
    # zip'teki diğer her XML parçası (üst/altbilgi, dipnot, yorum, tanınmayan parçalar).
    c.artik = {"word/document.xml": (metin_dugumleri(kok, tuk, "word/document.xml")[0], "yapılandırılmış parçanın artığı"), **c.artik}
    geri_dusus_yaz(c, z)
    return c

# ── BÖLÜM: xlsx ─────────────────────────────────────────────────────────────────────────────────────────────
def xlsx_okuyucu():
    """office-excel skill'inin stdlib okuyucusu (aynı template klonunda). Yoksa None → xlsx desteklenmiyor."""
    yol = HERE.parent.parent.parent / "skills" / "office-excel" / "scripts"
    if not (yol / "xlsx_lite.py").is_file():
        return None
    if str(yol) not in sys.path:
        sys.path.insert(0, str(yol))
    try:
        import xlsx_lite  # noqa: WPS433
    except Exception:
        return None
    return xlsx_lite


def _hucre_metni(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v)


def xlsx_artik(c: Cikti, z: zipfile.ZipFile, sayfa_parcalari: list[str]) -> None:
    """Sayfa ve paylaşılan dizge parçalarının satıra girmeyen metni → geri düşüş. Satıra giren: hücrenin `v` metni ve
    satır içi dizgesi (`is`), paylaşılan dizgede bir hücrenin andığı `si`. Geri kalan (üst/altbilgi, veri doğrulama
    listesi, anılmayan dizge …) geri düşüşe gider; formül metni yok sayılan sınıftadır."""
    anilan: set[int] = set()
    for parca in sayfa_parcalari:
        try:
            kok = ET.fromstring(z.read(parca))
        except (KeyError, ET.ParseError):
            c.artik[parca] = ([], "sayfa parçası okunamadı — metin alınmadı")
            continue
        tuk: set[int] = set()
        for h in kok.iter():
            if yerel(h.tag) != "c":
                continue
            for ch in h:
                if yerel(ch.tag) == "v":
                    tuk.add(id(ch))
                    if h.get("t") == "s" and (ch.text or "").strip().isdigit():
                        anilan.add(int(ch.text.strip()))
                elif yerel(ch.tag) == "is":
                    tuk.update(id(x) for x in ch.iter())
        parca_artigi(c, parca, kok, tuk)
    ss = next((h for tip, h in parca_iliskileri(z, "xl/workbook.xml").values() if tip == "sharedStrings"), None)
    if ss and ss in z.namelist():
        try:
            kok = ET.fromstring(z.read(ss))
        except ET.ParseError:
            c.artik[ss] = ([], "paylaşılan dizge parçası okunamadı — metin alınmadı")
            return
        si = [x for x in kok if yerel(x.tag) == "si"]
        parca_artigi(c, ss, kok, {id(x) for i, s in enumerate(si) if i in anilan for x in s.iter()})


def xlsx_cikar(z: zipfile.ZipFile, yol: Path, xl, atla: dict[str, int] | None = None) -> Cikti:
    c = Cikti("xlsx")
    c.atlanan = dict(atla or {})
    try:
        sayfalar = xl.sheet_parts(z)
    except Exception as exc:
        raise Okunamadi(f"çalışma kitabı okunamadı: {exc}") from None
    for sno, (ad, _parca) in enumerate(sayfalar, 1):
        c.sayfalar.append(ad)
        try:
            _ad, satirlar = xl.read_rows(str(yol), sno)
        except Exception as exc:
            raise Okunamadi(f"sayfa {ad!r} okunamadı: {exc}") from None
        c.satirlar.append("")
        c.satirlar.append("## Sayfa SY%02d: %s" % (sno, ad))
        for rno, satir in enumerate(satirlar, 1):
            hucreler = [_hucre_metni(v).replace("\r", " ").replace("\n", " ") for v in satir]
            if not any(bosluksuz(h) for h in hucreler):
                continue
            c.satirlar.append("[%s] ⟦SY%02d.S%04d⟧ | %s |" % (c.km_yeni(), sno, rno,
                                                          " | ".join(_tablo_kacis(h) for h in hucreler)))
    adlar = z.namelist()
    nesne_basligi = ["", "## Çizim, SmartArt ve grafik metinleri (hangi hücrede durduğu yazılmaz)", ""]
    for tur in ("diyagram", "grafik"):
        for no, parca in enumerate(sorted(a for a in adlar if NESNE_PARCA["xlsx"][tur].match(a)), 1):
            c.satirlar += nesne_basligi
            nesne_basligi = []
            nesne_yapilandir(c, z, parca, tur, no)
    kutu_no = 0
    for parca in sorted(a for a in adlar if NESNE_PARCA["xlsx"]["cizim"].match(a)):
        try:
            kutular = cizim_kutulari(z, parca)
            kok = ET.fromstring(z.read(parca))
        except ET.ParseError:
            c.notlar.append("çizim parçası okunamadı: %s — metin kutuları ALINMADI" % parca)
            c.artik[parca] = ([], "yapılandırılmış parça okunamadı — metin alınmadı")
            continue
        for hucreler in kutular:
            kutu_no += 1
            c.satirlar += nesne_basligi
            nesne_basligi = []
            nesne_satiri(c, "metin_kutusu", kutu_no, parca, hucreler)
        parca_artigi(c, parca, kok, tuketilen_idler(kutu_secimi(kok)))
    c.svg_yedek = svg_yedekleri(z)
    for i, ad in enumerate(_gorsel_uyeleri(z, "xl"), 1):
        kid = "KG-%02d" % i
        c.gorseller.append((kid, ad, (atlanan_dosya(c, kid, ad) or ("%s_%s" % (kid, guvenli_ad(ad)),))[0]))
    for i, ad in enumerate(sorted(a for a in adlar if a.startswith("xl/embeddings/") and not a.endswith("/")), 1):
        kid = "KN-%02d" % i
        yt = atlanan_dosya(c, kid, ad)
        if yt:
            c.gomululer.append((kid, ad, yt[0], yt[1].encode("utf-8"), yt[1]))
            continue
        p_ad, icerik, tur = gomulu_coz(ad, z.read(ad))
        c.gomululer.append((kid, ad, "%s_%s" % (kid, p_ad), icerik, tur))
    if c.gorseller or c.gomululer:
        c.notlar.append("xlsx'te görsel/nesnenin hangi hücrede durduğu metin.md'ye yazılmaz (yalnız dosya olarak çıkar)")
    xlsx_artik(c, z, [p for _a, p in sayfalar])
    geri_dusus_yaz(c, z)
    return c

# ── BÖLÜM: bağımsız sayım + paket yazımı + doğrulama ──────────────────────────────────────────────────────────
# Bağımsız sayım çıkarım kodunu KULLANMAZ: gövdeyi kapsayıcı yürüyüşüyle değil ata haritasıyla sayar; nesne
# parçalarının (SmartArt, grafik, çizim) metnini ElementTree yerine düzenli ifadeyle sayar. Çıkarım bir kapsayıcıyı
# ya da nesneyi atlarsa iki sayı ayrılır ve paket FAIL olur.
SAYIM_ADLARI = [("km", "kaynak maddesi (KM: başlık + paragraf + tablo satırı + metinli nesne)"), ("baslik", "başlık"),
                ("tablo", "tablo"), ("tablo_satiri", "tablo satırı (metinli)"),
                ("karakter", "metin karakteri (boşluksuz; xlsx'te yalnız metin hücreleri)"),
                ("denklem", "denklem"), ("sayfa", "çalışma sayfası"), ("diyagram", "SmartArt (D)"),
                ("grafik", "grafik (G)"), ("metin_kutusu", "çizim metin kutusu (K)"),
                ("parca_metni", "XML parça metni (evren − muaf − yok sayılan; boşluksuz)"),
                ("gorsel", "görsel (KG)"), ("gomulu", "gömülü nesne (KN)")]
_YAPRAK = r"<(?:\w+:)?(%s)(?:\s[^<>]*)?>([^<]*)</(?:\w+:)?\1>"
_YAPRAK_T = re.compile(_YAPRAK % "t")
_YAPRAK_TVP = re.compile(_YAPRAK % "t|v|pt")
_TXBODY = re.compile(r"<((?:\w+:)?txBody)\b.*?</\1>", re.S)


def _yaprak_karakteri(xml: str, desen: re.Pattern) -> int:
    return sum(bosluksuz(html.unescape(m.group(2))) for m in desen.finditer(xml))


def _nesne_say(z: zipfile.ZipFile, tur: str) -> dict[str, int]:
    """SmartArt / grafik / (xlsx) çizim metin kutusu: adet + metinli olanlar (KM satırı). Metnin TAMAMININ pakete
    girdiğini bu sayım değil, parça hesabı (evren süpürmesi) ölçer."""
    s = {"diyagram": 0, "grafik": 0, "nesne_km": 0}
    if tur == "xlsx":
        s["metin_kutusu"] = 0
    for ad in z.namelist():
        for anahtar, desen in NESNE_PARCA[tur].items():
            if not desen.match(ad):
                continue
            xml = z.read(ad).decode("utf-8", "replace")
            if anahtar == "cizim":
                for blok in _TXBODY.finditer(xml):
                    if _yaprak_karakteri(blok.group(0), _YAPRAK_T):
                        s["metin_kutusu"] += 1
                        s["nesne_km"] += 1
                continue
            s[anahtar] += 1
            s["nesne_km"] += 1 if _yaprak_karakteri(xml, _YAPRAK_T if anahtar == "diyagram" else _YAPRAK_TVP) else 0
    return s


def _afchunk_hedefleri(z: zipfile.ZipFile) -> set[str]:
    try:
        rels = z.read("word/_rels/document.xml.rels").decode("utf-8", "replace")
    except KeyError:
        return set()
    out = set()
    for m in re.finditer(r"<(?:\w+:)?Relationship\b([^>]*)/?>", rels):
        a = m.group(1)
        tip = re.search(r'Type="([^"]*)"', a)
        hed = re.search(r'Target="([^"]*)"', a)
        if tip and hed and tip.group(1).lower().endswith("/afchunk") and 'TargetMode="External"' not in a:
            h = hed.group(1)
            yol = h.lstrip("/") if h.startswith("/") else os.path.normpath("word/" + h).replace("\\", "/")
            if yol in z.namelist():
                out.add(yol)
    return out


def bagimsiz_docx(z: zipfile.ZipFile) -> dict[str, int]:
    kok = ET.fromstring(z.read("word/document.xml"))
    ebeveyn = {ch: par for par in kok.iter() for ch in par}

    def atalar(el):
        while el in ebeveyn:
            el = ebeveyn[el]
            yield el

    def fallbackta(el) -> bool:
        return any(yerel(a.tag) == "Fallback" for a in atalar(el))

    # Gövde metni: Word metni + denklem metni (ikisi de satırın metnine girer).
    metinler = [t for t in kok.iter() if (w(t.tag, "t") or m_(t.tag, "t")) and not fallbackta(t)]
    dolu = {t for t in metinler if (t.text or "").strip()}
    dolu_atalar: set = set()
    for t in dolu:
        dolu_atalar.update(atalar(t))
    stiller = stil_seviyeleri(z)
    s = {"km": 0, "baslik": 0, "tablo": 0, "tablo_satiri": 0, "denklem": 0,
         "karakter": sum(bosluksuz(t.text or "") for t in metinler)}
    for el in kok.iter():
        if w(el.tag, "p"):
            if any(w(a.tag, "p") or w(a.tag, "tbl") for a in atalar(el)) or el not in dolu_atalar:
                continue
            s["km"] += 1
            seviye = None
            for x in el.iter():
                if w(x.tag, "pStyle") and ebeveyn.get(ebeveyn.get(x)) is el:
                    seviye = stiller.get(attr_yerel(x, "val") or "")
                if w(x.tag, "outlineLvl") and ebeveyn.get(ebeveyn.get(x)) is el:
                    v = attr_yerel(x, "val") or ""
                    seviye = int(v) + 1 if v.isdigit() and int(v) < 9 else None
            if seviye:
                s["baslik"] += 1
        elif w(el.tag, "tbl"):
            # Paragraf içindeki tablo (metin kutusu) paragrafın satırına düzleşir: tablo/satır sayılmaz.
            if not any(w(a.tag, "tbl") or w(a.tag, "p") for a in atalar(el)):
                s["tablo"] += 1
        elif w(el.tag, "tr"):
            ust = list(atalar(el))
            if sum(1 for a in ust if w(a.tag, "tbl")) == 1 and not any(w(a.tag, "p") for a in ust) \
                    and el in dolu_atalar:
                s["tablo_satiri"] += 1
                s["km"] += 1
        elif m_(el.tag, "oMath") and not fallbackta(el) and not any(m_(a.tag, "oMath") for a in atalar(el)):
            if any(bosluksuz(x.text or "") for x in el.iter() if m_(x.tag, "t")):
                s["denklem"] += 1
    nesne = _nesne_say(z, "docx")
    s["km"] += nesne.pop("nesne_km")
    s.update(nesne)
    adlar = z.namelist()
    s["gorsel"] = len(_gorsel_uyeleri(z, "word"))
    s["gomulu"] = sum(1 for a in adlar if a.startswith("word/embeddings/") and not a.endswith("/")) \
        + len(_afchunk_hedefleri(z))
    return s


def _xml_metni(parca: str) -> str:
    parca = re.sub(r"<(?:\w+:)?rPh\b.*?</(?:\w+:)?rPh>", "", parca, flags=re.S)
    return html.unescape("".join(re.findall(r"<(?:\w+:)?t\b[^>]*>(.*?)</(?:\w+:)?t>", parca, flags=re.S)))


def _sutun_no(ref: str) -> int | None:
    m = re.match(r"^([A-Z]+)\d", ref or "")
    if not m:
        return None
    n = 0
    for ch in m.group(1):
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def bagimsiz_xlsx(z: zipfile.ZipFile) -> tuple[dict[str, int], set[tuple[int, int, int]]]:
    """Döner: (sayım, metin hücresi maskesi {(sayfa no, Excel satır no, sütun sırası)}). Sayfa sırası workbook.xml'deki
    `sheet` sırasıdır. Karakter yalnız metin hücrelerinden (paylaşılan dizge, satır içi dizge, formül dizgesi) sayılır;
    sayı/tarih/mantıksal hücrenin gösterimi çıkarımda biçimlendiği için sayılmaz — maske diskteki pakette aynı
    konumdaki hücreleri seçer."""
    def oku(ad):
        try:
            return z.read(ad).decode("utf-8", "replace")
        except KeyError:
            return ""
    rid_yol, paylasilan_yolu = {}, None
    for m in re.finditer(r"<(?:\w+:)?Relationship\b([^>]*)/?>", oku("xl/_rels/workbook.xml.rels")):
        tip = re.search(r'Type="([^"]*)"', m.group(1))
        hed = re.search(r'Target="([^"]*)"', m.group(1))
        rid = re.search(r'\bId="([^"]*)"', m.group(1))
        if not (tip and hed):
            continue
        h = hed.group(1)
        yol = h.lstrip("/") if h.startswith("/") else os.path.normpath("xl/" + h).replace("\\", "/")
        if tip.group(1).endswith("/worksheet") and rid:
            rid_yol[rid.group(1)] = yol
        elif tip.group(1).endswith("/sharedStrings"):
            paylasilan_yolu = yol
    sayfa_yollari = []
    for m in re.finditer(r"<(?:\w+:)?sheet\b([^>]*)/?>", oku("xl/workbook.xml")):
        rid = re.search(r'\b(?:\w+:)?id="([^"]*)"', m.group(1))
        if rid and rid.group(1) in rid_yol:
            sayfa_yollari.append(rid_yol[rid.group(1)])
    paylasilan = [_xml_metni(m.group(2) or "") for m in _SI_RE.finditer(oku(paylasilan_yolu) if paylasilan_yolu else "")]
    km, karakter, maske = 0, 0, set()
    for sno, yol in enumerate(sayfa_yollari, 1):
        rno_sira = 0
        for r_attr, satir in re.findall(r"<(?:\w+:)?row\b([^>]*?)(?<!/)>(.*?)</(?:\w+:)?row>", oku(yol), flags=re.S):
            rm = re.search(r'\br="(\d+)"', r_attr)
            rno = int(rm.group(1)) if rm else rno_sira + 1
            rno_sira = rno
            dolu, sira = False, 0
            for attrs, ic in re.findall(r"<(?:\w+:)?c\b([^>]*?)(?:/>|>(.*?)</(?:\w+:)?c>)", satir, flags=re.S):
                ref = re.search(r'\br="([^"]*)"', attrs)
                sno_c = _sutun_no(ref.group(1)) if ref else None
                sira = sno_c if sno_c is not None else sira
                tur = re.search(r'\bt="([^"]*)"', attrs)
                tur = tur.group(1) if tur else "n"
                v = re.search(r"<(?:\w+:)?v\b[^>]*>(.*?)</(?:\w+:)?v>", ic or "", flags=re.S)
                v = html.unescape(v.group(1)) if v else ""
                if tur == "s":
                    deger = paylasilan[int(v)] if v.strip().isdigit() and int(v) < len(paylasilan) else ""
                elif tur == "inlineStr":
                    deger = _xml_metni(ic or "")
                else:
                    deger = v
                if tur in ("s", "inlineStr", "str"):
                    karakter += bosluksuz(deger)
                    maske.add((sno, rno, sira))
                if deger.strip():
                    dolu = True
                sira += 1
            km += 1 if dolu else 0
    adlar = z.namelist()
    s = {"km": km, "karakter": karakter, "sayfa": len(sayfa_yollari),
         "gorsel": len(_gorsel_uyeleri(z, "xl")),
         "gomulu": sum(1 for a in adlar if a.startswith("xl/embeddings/") and not a.endswith("/"))}
    nesne = _nesne_say(z, "xlsx")
    s["km"] += nesne.pop("nesne_km")
    s.update(nesne)
    return s, maske, xlsx_yapi_payi(z, sayfa_yollari, paylasilan_yolu)


_HUCRE_RE = re.compile(r"<(?:[\w.-]+:)?c\b(%s)(?:/>|>(.*?)</(?:[\w.-]+:)?c\s*>)" % _ATTR, re.S)
_V_RE = re.compile(r"<(?:[\w.-]+:)?v\b%s>([^<]*)</" % _ATTR)
_IS_RE = re.compile(_BLOK % "is", re.S)
# Paylaşılan dizge: kendinden kapanan boş `<si/>` da bir indekstir (ölçüldü: atlanınca sonraki hücreler kaydı, paket
# doğruyken DOĞRULAMA FAIL verdi).
_SI_RE = re.compile(r"<((?:[\w.-]+:)?si)\b(?:%s/>|%s>(.*?)</\1\s*>)" % (_ATTR, _ATTR), re.S)


def xlsx_yapi_payi(z: zipfile.ZipFile, sayfa_yollari: list[str], ss_yolu: str | None) -> dict[str, int]:
    """Sayfa ve paylaşılan dizge parçalarında hücre satırlarına giren metin (yok sayılan ayıklandıktan sonra):
    sayfada hücrenin `v` ve `is` metni, paylaşılan dizgede bir hücrenin andığı `si`'ler. Parça hesabında bu pay +
    diskteki geri düşüş = parçanın net evreni olmalı (hücre metninin pakete doğru yazıldığını karakter sayımı ölçer)."""
    def net(ad: str) -> str:
        try:
            return yok_sayilani_cikar(xml_metni(z.read(ad)) or "", ad)[0]
        except KeyError:
            return ""
    out: dict[str, int] = {}
    anilan: set[int] = set()
    for yol in sayfa_yollari:
        n = 0
        for attrs, ic in _HUCRE_RE.findall(net(yol)):
            vler = _V_RE.findall(ic or "")
            n += sum(bosluksuz(html.unescape(v)) for v in vler)
            n += sum(metin_karakteri(b.group(0)) for b in _IS_RE.finditer(ic or ""))
            if re.search(r'\bt\s*=\s*"s"', attrs) and vler and vler[0].strip().isdigit():
                anilan.add(int(vler[0].strip()))
        out[yol] = n
    if ss_yolu:
        si = [b.group(0) for b in _SI_RE.finditer(net(ss_yolu))]
        out[ss_yolu] = sum(metin_karakteri(b) for i, b in enumerate(si) if i in anilan)
    return out


def _satir_karakteri(govde: str, tablo_satiri: bool) -> int:
    govde = NOT_RE.sub("", govde)
    if tablo_satiri:
        govde = re.sub(r"\\(.)|[|¶]", lambda m: m.group(1) or "", govde)
    return bosluksuz(govde)


def _hucre_bol(govde: str) -> list[str]:
    """`| a | b\\|c |` → ['a', 'b|c'] — kaçışı çözer; `|` yalnız kaçırılmamışsa ayraçtır."""
    s = govde.strip()
    if s.startswith("|"):
        s = s[1:]
    hucreler, cur, i = [], [], 0
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s):
            cur.append(s[i + 1])
            i += 2
            continue
        if ch == "|":
            hucreler.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
        i += 1
    if "".join(cur).strip():
        hucreler.append("".join(cur))
    return [h.strip() for h in hucreler]


GERI_RE = re.compile(r"^⟦P(\d+) parça: ([^⟧]*)⟧ ?")
NESNE_PARCA_RE = re.compile(r"^⟦[DGK]\d+ [^:⟧]+: ([^⟧]*)⟧")


def diskten_say(paket: Path, tur: str, maske: set | None = None) -> tuple[dict[str, int], list[str], dict]:
    """Paketi DİSKTEN okuyup sayar (bellekteki çıkarım sonucuna bakmaz). Döner: (sayım, biçim sorunları, parça payları
    {parça: {"yapi": n, "geri": n}}). xlsx'te karakter yalnız `maske` (bağımsız sayımın metin hücresi konumları)
    verilirse sayılır. `km` yapılandırılmış maddelerdir; geri düşüş maddeleri `km_geri`."""
    sorunlar: list[str] = []
    metin = (paket / "metin.md").read_text(encoding="utf-8")
    s = {"km": 0, "km_geri": 0, "baslik": 0, "tablo": 0, "tablo_satiri": 0, "karakter": 0, "denklem": 0, "sayfa": 0,
         "diyagram": 0, "grafik": 0, "metin_kutusu": 0}
    pay: dict[str, dict[str, int]] = {}
    beklenen = 1
    for satir in metin.splitlines():
        if re.match(r"^\*\*Tablo T\d+\*\* ", satir):
            s["tablo"] += 1
        if re.match(r"^## Sayfa SY\d+: ", satir):
            s["sayfa"] += 1
        m = KM_RE.match(satir)
        govde = satir[m.end():] if m else satir
        om = NESNE_RE.match(govde)
        if om:
            s[NESNE_ANAHTAR[om.group(2)]] += 1
        if not m:
            continue
        if m.group(2) != "KM-%04d" % beklenen:
            sorunlar.append(f"KM sırası bozuk: {m.group(2)} (beklenen KM-{beklenen:04d})")
        beklenen = int(m.group(2)[3:]) + 1
        gm = GERI_RE.match(govde)
        if gm:
            s["km_geri"] += 1
            pay.setdefault(gm.group(2), {"yapi": 0, "geri": 0})["geri"] += _satir_karakteri(govde[gm.end():], True)
            continue
        s["km"] += 1
        if m.group(1):
            s["baslik"] += 1
        if om:
            parca = NESNE_PARCA_RE.match(govde).group(1)
            pay.setdefault(parca, {"yapi": 0, "geri": 0})["yapi"] += _satir_karakteri(govde[om.end():], True)
            continue
        s["denklem"] += govde.count(DENKLEM)
        rm = SATIR_RE.match(govde)
        if rm and rm.group(1).startswith("T"):
            s["tablo_satiri"] += 1
        if rm and rm.group(2):  # xlsx satırı: yalnız metin hücresi konumları
            if maske is not None:
                sno, rno = int(rm.group(2)), int(rm.group(3))
                s["karakter"] += sum(bosluksuz(h) for i, h in enumerate(_hucre_bol(govde[rm.end():]))
                                     if (sno, rno, i) in maske)
            continue
        s["karakter"] += _satir_karakteri(govde[rm.end():] if rm else govde, bool(rm))
    if tur == "docx":  # gövde satırlarının tamamı word/document.xml'den gelir
        pay.setdefault("word/document.xml", {"yapi": 0, "geri": 0})["yapi"] += s["karakter"]
    for klasor, anahtar in (("media", "gorsel"), ("gomulu", "gomulu")):
        d = paket / klasor
        s[anahtar] = sum(1 for p in d.iterdir() if p.is_file() and not KULLANICI_PNG_RE.match(p.name)) \
            if d.is_dir() else 0
    return s, sorunlar, pay


def karsilastir(kaynak: dict[str, int], paket: dict[str, int]) -> list[str]:
    return ["%s: kaynak %d ≠ paket %d" % (ad, kaynak[k], paket.get(k, 0))
            for k, ad in SAYIM_ADLARI if k in kaynak and kaynak[k] != paket.get(k, 0)]


# xlsx sayfa ve paylaşılan dizge parçalarında yapılandırılmış pay hücre tanımından (KAYNAKTAN) hesaplanır; pakette bu
# parçanın payı ölçülmez, yalnız metin hücrelerinin karakteri (ayrı sayım satırı) pakete karşı ölçülür. Paket satırı
# hücrenin biçimli gösterimini taşır, hangi hücrenin paylaşılan dizge olduğunu taşımaz → parça payı paketten kurulamaz.
YAPI_KAYNAKTAN = "yapılandırılmış (kaynaktan; pakette yalnız metin hücresi ölçülür)"


def parca_hesabi(evren: dict[str, dict], pay: dict, yapi_kaynak: dict[str, int]) -> tuple[list[dict], list[str]]:
    """Parça başına: evren − yok sayılan (bağımsız) = yapılandırılmış + geri düşüş (diskten; xlsx sayfa/paylaşılan
    dizge parçalarında yapılandırılmış pay hücre tanımından). Pakette olup evrende olmayan parça da fark sayılır."""
    satirlar, farklar = [], []
    evren = {gorunur(a): e for a, e in evren.items()}
    yapi_kaynak = {gorunur(a): n for a, n in yapi_kaynak.items()}
    for ad in sorted(set(evren) | set(pay)):
        e = evren.get(ad)
        d = pay.get(ad, {"yapi": 0, "geri": 0})
        if e and e["muaf"]:
            satirlar.append({"parca": ad, "sinif": "muaf: " + e["muaf"], "evren": e["evren"], "yok": 0,
                             "yapi": 0, "geri": d["geri"] + d["yapi"]})
            if d["geri"] or d["yapi"]:
                farklar.append("muaf parça pakette: %s" % ad)
            continue
        net = e["net"] if e else 0
        yapi = yapi_kaynak.get(ad, d["yapi"])
        if not (net or yapi or d["geri"]):
            continue
        sinif = "evrende yok" if not e else ("geri düşüş" if not yapi else
                                            YAPI_KAYNAKTAN if ad in yapi_kaynak else "yapılandırılmış")
        satirlar.append({"parca": ad, "sinif": sinif, "evren": e["evren"] if e else 0,
                         "yok": (e["evren"] - net) if e else 0, "yapi": yapi, "geri": d["geri"]})
        if net != yapi + d["geri"]:
            farklar.append("parça %s: kaynak metni %d ≠ pakette %d (yapılandırılmış %d + geri düşüş %d)"
                           % (ad, net, yapi + d["geri"], yapi, d["geri"]))
    return satirlar, farklar


def yok_toplami(evren: dict[str, dict]) -> dict[str, int]:
    """Yok sayılan sınıfların toplam karakteri (muaf olmayan parçalarda; bağımsız taraftan). Sıfırlar da döner."""
    out = dict.fromkeys(YOK_SINIFLAR, 0)
    for e in evren.values():
        if not e["muaf"]:
            for k, n in e["yok"].items():
                out[k] += n
    return out


def yok_satiri(yok: dict[str, int]) -> str:
    return "yok sayılan: " + " · ".join("%s %d" % (k, yok[k]) for k in YOK_SINIFLAR)


def boyut_denetle(z: zipfile.ZipFile) -> dict[str, int]:
    """Her üye GERÇEKTEN açılıp (z.open, 1 MiB'lık parçalar) açılan bayt sayılır; zip başlığındaki beyana güvenilmez.
    Sınırı aşan görsel/gömülü üye atlanır (döner {ad: okunan bayt}); görsel/gömülü üyeler metin toplamına SAYILMAZ, kendi
    toplamlarını aşan üye de atlanır (büyük görselli belgenin metni korunur). XML olmayan ikili üye (içerikten: ilk
    anlamlı karakter `<` değil) aynı biçimde kendi payından sayılır, aşan atlanır. Sınırı aşan XML parçası, metin toplamı
    ya da açılamayan üye (bozuk sıkıştırma, CRC/boy uyuşmazlığı, şifre) → Okunamadi (çıkış 2)."""
    toplam, dosya_toplam, ikili_toplam, atla = 0, 0, 0, {}
    dosya = dosya_uyeleri(z)
    for bilgi in z.infolist():
        if bilgi.is_dir():
            continue
        n, ilk, bom = 0, b"", b""
        try:
            with z.open(bilgi) as f:
                while True:
                    parca = f.read(OKUMA_PARCASI)
                    if not parca:
                        break
                    if not ilk:  # sınıflama ilk BOŞLUK OLMAYAN parçaya göre (baştaki boşluk parçası ikili sayılmaz);
                        # boşluk parçaları biriktirilmez (bellek/zaman sabit), UTF-16 BOM'u sonraki parçaya taşınır
                        if n == 0 and parca[:2] in (b"\xff\xfe", b"\xfe\xff"):
                            bom = parca[:2]
                        deneme = parca if n == 0 else bom + parca
                        if _xml_cozumle(deneme).strip():
                            ilk = deneme
                    n += len(parca)
                    if n > MAX_UYE:
                        break
        except (zipfile.BadZipFile, zlib.error, EOFError, OSError, NotImplementedError, RuntimeError) as exc:
            raise Okunamadi("zip üyesi açılamadı: %s (%s: %s) — başlıktaki boy/CRC içerikle uyuşmuyor olabilir"
                            % (bilgi.filename, type(exc).__name__, exc)) from None
        if bilgi.filename in dosya:
            if n > MAX_UYE or dosya_toplam + n > MAX_DOSYA_TOPLAM:
                atla[bilgi.filename] = n
            else:
                dosya_toplam += n
            continue
        if not xml_gibi(ilk):
            if n > MAX_UYE or ikili_toplam + n > MAX_IKILI_TOPLAM:
                atla[bilgi.filename] = n
            else:
                ikili_toplam += n
            continue
        if n > MAX_UYE:
            raise Okunamadi("boyut sınırı: %s açılınca %d bayttan fazla (sınır %d) — çıkarım yapılmadı"
                            % (bilgi.filename, MAX_UYE, MAX_UYE))
        toplam += n
        if toplam > MAX_TOPLAM:
            raise Okunamadi("boyut sınırı: açılmış toplam %d bayttan fazla (sınır %d) — çıkarım yapılmadı"
                            % (MAX_TOPLAM, MAX_TOPLAM))
    return atla


# ── BÖLÜM: görsel notları (model görseli `view` ile okur, `iz` boş notu sayar) ────────────────────────────────────
HARICI_GORSEL = "⟦harici görsel bağlantısı — pakette yok⟧"
COZULEMEDI_RE = re.compile(r"⟦(\w+) başvurusu çözülemedi(?::[^⟧]*)?⟧")
GORSEL_IMLEC = re.compile(r"⟦(K[GN]-\d+) (?:görsel|gömülü)")
YORUM_RE = re.compile(r"<!--.*?-->", re.S)
PILLOW_KOMUTU = '''python -c "from PIL import Image; Image.open('%s').save('%s')"'''
# Görülen notu AÇIK SINIRLAYICI arasında durur: `<!-- gorulen:KG-02 -->` … `<!-- /gorulen:KG-02 -->`. `iz` notu YALNIZ
# bu iki satırın arasından okur; neyin alanı "bitirdiği" Markdown biçiminden tahmin edilmez (başlık, yatay çizgi,
# alıntı, düz paragraf… hepsi işaret dışında kalır ve sayılmaz). İşaret eksik/sırası bozuksa o görselin notu BOZUK.
NOT_BICIMI = 2  # 1 = işaretsiz "- Görülen:" alanı (yalnız bu geliştirme dalında vardı); 2 = işaret çifti
ISARET_RE = re.compile(r"^[ \t]*<!--[ \t]*(/?)gorulen:(K[GN]-\d+)[ \t]*-->[ \t]*$")
GORULEN_SATIRI = "- Görülen (yalnız aşağıdaki iki işaret satırının ARASINA yaz):"
# İşaret dışında kalan ve metin SAYILMAYAN iskelet satırları (bölüm başlığı + alan satırları + Görülen satırı aynen)
ISKELET_SATIRI_RE = re.compile(r"^(?:##[ \t]+K[GN]-\d+\b.*|- (?:Dosya|Kaynak parçası|Konum|Biçim): .*|%s)$"
                               % re.escape(GORULEN_SATIRI))
BOLUM_RE = re.compile(r"^##[ \t]+(K[GN]-\d+)\b")
GORULEN_ALAN_RE = re.compile(r"^\s*-?\s*Görülen\b.*:\s*$")


def isaret(kid: str, kapanis: bool = False) -> str:
    return "<!-- %sgorulen:%s -->" % ("/" if kapanis else "", kid)


def gorsel_konumlari(satirlar: list[str]) -> dict[str, list[str]]:
    """metin.md satırlarından görsel/gömülü işaretinin konumu: işaret bir KM satırındaysa o KM, işaret ayrı satırdaysa
    'KM-nnnn sonrası' (önünde KM yoksa 'belge başı'). xlsx'te işaret yazılmadığı için konum yoktur."""
    out: dict[str, list[str]] = {}
    son_km = None
    for s in satirlar:
        m = KM_RE.match(s)
        if m:
            son_km = m.group(2)
        for kid in GORSEL_IMLEC.findall(s):
            yer = son_km if m else ("%s sonrası" % son_km if son_km else "belge başı")
            if yer not in out.setdefault(kid, []):
                out[kid].append(yer)
    return out


def _gorsel(kid: str, ad: str, yol: str, konum: list[str], atlandi: bool) -> dict:
    uz = (Path(ad).suffix if atlandi else Path(yol).suffix).lower()
    if atlandi:
        neden = "ÖLÇÜLEMEDİ — boyut"
    elif uz in GORUNTULENEBILIR:
        neden = None
    else:
        neden = "GÖRÜNTÜLENEMEZ (%s)" % (uz.lstrip(".") or "uzantısız")
    return {"kimlik": kid, "parca": ad, "dosya": yol, "konum": konum, "bicim": uz.lstrip("."),
            "goruntulenebilir": neden is None, "neden": neden}


def cozulemeyen_basvurular(c: "Cikti") -> list[str]:
    """metin.md'de dosyaya bağlanamayan görsel/nesne işaretleri (ör. ilişkisi pakette olmayan bir üyeyi gösteren)."""
    return list(dict.fromkeys(m.group(0) for s in c.satirlar for m in COZULEMEDI_RE.finditer(s)))


def olculemez(g: dict) -> bool:
    """Notu boşken ÖLÇÜLEMEDİ sayılan görsel: görüntülenemez ve okunabilir bir yedeği (svgBlip PNG'si) yok."""
    return not g["goruntulenebilir"] and not g.get("yedek")


def gorsel_listesi(c: "Cikti") -> list[dict]:
    """Okunması gereken görseller: her KG + içeriği görsel olan KN (OLE paket nesnesindeki resim vb.). SVG'nin PNG yedeği
    pakette görüntülenebilirse SVG `yedek` alır: okuma PNG'nin bölümünde yapılır, SVG ÖLÇÜLEMEDİ sayılmaz."""
    konum = gorsel_konumlari(c.satirlar)
    out = [_gorsel(k, a, "media/" + d, konum.get(k, []), a in c.atlanan) for k, a, d in c.gorseller]
    by_ad = {g["parca"]: g for g in out}
    for g in out:
        png = by_ad.get(c.svg_yedek.get(g["parca"], ""))
        if png and png["goruntulenebilir"] and not g["goruntulenebilir"] and g["neden"] != "ÖLÇÜLEMEDİ — boyut":
            g["yedek"] = png["kimlik"]
            g["konum"] = g["konum"] or ["%s ile aynı yer (aynı görselin SVG sürümü)" % png["kimlik"]]
    for k, a, d, _i, _t in c.gomululer:
        uz = (Path(a).suffix if a in c.atlanan else Path(d).suffix).lower()
        if uz in GORSEL_UZANTILARI:
            out.append(_gorsel(k, a, "gomulu/" + d, konum.get(k, []), a in c.atlanan))
    return out


def _not_imzasi(veri: bytes) -> str:
    return "<!-- kaynak_paketi görsel notları · sha256 %s · km şeması %d · not biçimi %d -->" % (
        ozet(veri)[:16], KM_SEMASI, NOT_BICIMI)


def _bos_ad(hedef: Path, kok: str) -> str:
    """Kenara alma adı (`<kok>[.n]`): ne `<ad>.md` dosyası ne `kenar/<ad>/` klasörü var — hiçbir kenar kaydı ezilmez."""
    ad, n = kok, 2
    while (hedef / (ad + ".md")).exists() or (hedef / "kenar" / ad).exists():
        ad, n = "%s.%d" % (kok, n), n + 1
    return ad


def _kopyalari_tasi(kaynak: Path, hedef: Path) -> int:
    """`<kimlik>.kullanici.png` kopyalarını (ad harfe duyarsız tanınır, harfi korunur) taşır: notlarla aynı kaderi
    paylaşırlar (kaynak değişince kenara gider, notlar geri yüklenince geri gelir). Hedefte aynı ad harf farkıyla bile
    varsa EZİLMEZ: `media/`'ya dönüşte kopya kenarda kalır, kenara gidişte `.<n>` ekiyle yazılır. Taşınan sayısını döner."""
    n = 0
    if kaynak.is_dir():
        for p in sorted(kaynak.iterdir()):
            if not (p.is_file() and KULLANICI_PNG_RE.match(p.name)):
                continue
            hedef.mkdir(parents=True, exist_ok=True)
            var = {q.name.casefold() for q in hedef.iterdir()}
            ad, i = p.name, 2
            while ad.casefold() in var:
                if hedef.name == "media":
                    ad = None
                    break
                ad, i = "%s.%d%s" % (p.stem, i, p.suffix), i + 1
            if ad is None:
                continue
            p.replace(hedef / ad)
            n += 1
    return n


def kullanici_kopyasi(paket: Path, kimlik: str) -> list[Path]:
    """`media/<kimlik>.kullanici.png` kopyaları — ad harfe duyarsız eşlenir (tek kanonik eşleşme beklenir)."""
    d = paket / "media"
    hedef = (KULLANICI_PNG % kimlik).split("/", 1)[1].casefold()
    return sorted(p for p in d.iterdir() if p.is_file() and p.name.casefold() == hedef) if d.is_dir() else []


def _bicim_satiri(g: dict) -> str:
    if g["goruntulenebilir"]:
        return "%s — görüntülenebilir: `view` ile aç" % g["bicim"]
    if g.get("yedek"):
        return ("%s — PNG yedeği %s üzerinden okunur: notu %s bölümüne yaz (bu bölümün işaretleri arası boş kalabilir)"
                % (g["bicim"], g["yedek"], g["yedek"]))
    png = KULLANICI_PNG % g["kimlik"]
    if g["neden"] == "ÖLÇÜLEMEDİ — boyut":
        return "%s — dosya çıkarılmadı; kullanıcıdan PNG iste, `%s` adıyla kaydet" % (g["neden"], png)
    return ("%s — ÖLÇÜLEMEDİ: `view` açmaz. Pillow kuruluysa paket klasöründe `%s` ile çevir ve PNG'yi `view` ile aç; "
            "olmazsa kullanıcıdan PNG iste, `%s` adıyla kaydet" % (g["neden"], PILLOW_KOMUTU % (g["dosya"], png), png))


def gorsel_notlari_yaz(hedef: Path, kaynak: Path, veri: bytes, gorseller: list[dict]) -> str:
    """`gorsel-notlari.md` iskeleti. Aynı kaynak + aynı km şeması + aynı not biçimiyle yeniden çıkarımda var olan dosya
    KORUNUR. Değilse (başka kaynak/şema, eski not biçimi, imzasız) notlar `gorsel-notlari.<etiket>[.n].md` adıyla, o anki
    `media/<kimlik>.kullanici.png` kopyaları da `kenar/<aynı ad>/` altına kenara alınır — var olan kenar kaydı EZİLMEZ.
    Kenarda bu kaynağın imzasını taşıyan notlar varsa kopyalarıyla birlikte geri yüklenir (A→B→A ne notu ne PNG'yi
    kaybeder, C'nin KG-02'si A'nın PNG'siyle açılmaz). Eski biçim (işaretsiz) dönüştürülmez, kenara alınır: biçim yalnız
    yayınlanmamış geliştirme dalında vardı ve dönüştürmek, kaldırılan sezgisel sınırı yeniden kullanmak olurdu."""
    yol = hedef / NOT_DOSYASI
    imza = _not_imzasi(veri)
    durum: list[str] = []
    if yol.is_file():
        eski = yol.read_bytes().decode("utf-8", "replace")
        if imza in eski:
            return "korundu (aynı kaynak, aynı km şeması — yazılmış notlar silinmedi)"
        m = re.search(r"sha256 ([0-9a-f]{16}) · km şeması (\d+)", eski)
        if not m:
            etiket, neden = "imzasiz", "imza yok — hangi kaynağa ait olduğu belirlenemedi"
        elif m.group(1) != ozet(veri)[:16]:
            etiket, neden = m.group(1)[:8], "başka kaynağa ait"
        elif int(m.group(2)) != KM_SEMASI:
            etiket, neden = "%s-sema%s" % (m.group(1)[:8], m.group(2)), "aynı kaynak, başka km şeması"
        else:
            b = re.search(r"not biçimi (\d+)", eski)
            etiket, neden = ("%s-bicim%s" % (m.group(1)[:8], b.group(1) if b else "1"),
                             "aynı kaynak, başka not biçimi (1 = işaretsiz) — notları yeni iskelette işaretlerin "
                             "arasına taşı")
        ad = _bos_ad(hedef, "gorsel-notlari.%s" % etiket)
        yol.replace(hedef / (ad + ".md"))
        n = _kopyalari_tasi(hedef / "media", hedef / "kenar" / ad)
        durum.append("önceki notlar (%s) kenara alındı → %s.md%s" % (
            neden, ad, "; %d kullanıcı PNG'si → kenar/%s/" % (n, ad) if n else ""))
    else:
        ad = _bos_ad(hedef, "kullanici-png.sahipsiz")
        n = _kopyalari_tasi(hedef / "media", hedef / "kenar" / ad)
        if n:
            durum.append("not dosyası olmadan bulunan %d kullanıcı PNG'si kenara alındı → kenar/%s/ (hangi kaynağa ait "
                         "olduğu bilinmiyor)" % (n, ad))
    adaylar = []
    for p in sorted(hedef.glob("gorsel-notlari.*.md")):
        if not p.is_file():
            continue
        try:
            icerik = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as exc:
            durum.append("UYARI: %s okunamadı (%s) — geri yükleme adayı sayılmadı" % (p.name, type(exc).__name__))
            continue
        if imza in icerik:
            adaylar.append(p)
    if adaylar:
        sec = max(adaylar, key=lambda p: (p.stat().st_mtime, p.name))
        sec.replace(yol)
        n = _kopyalari_tasi(hedef / "kenar" / sec.stem, hedef / "media")
        try:
            (hedef / "kenar" / sec.stem).rmdir()
        except OSError:
            pass
        durum.append("bu kaynağın kenardaki notları geri yüklendi ← %s%s" % (
            sec.name, " (+%d kullanıcı PNG'si)" % n if n else ""))
        return "; ".join(durum)
    L = ["# Görsel notları — %s" % kaynak.name, imza, "",
         "> Her görseli `view` aracıyla aç ve gördüğünü YALNIZ o görselin iki işaret satırının ARASINA yaz",
         "> (`<!-- gorulen:KG-nn -->` ile `<!-- /gorulen:KG-nn -->`): ekran ya da pencere adı, alanlar, düğmeler, tablo",
         "> sütunları, değerler, okunabilen her metin — madde listesi ve tablo da olur. FS'te karşılığı olan her öğenin",
         "> yanına belge kimliğini yaz (`→ FR-003`); o görselin iz tablosu satırı da aynı kimliği taşır. Görsel başına AYRI",
         "> bir `edit`. İşaret satırlarını silme ya da değiştirme: `kaynak_paketi.py iz` notu YALNIZ işaretlerin arasından",
         "> okur; işaret dışındaki metin sayılmaz (UYARI), işareti eksik ya da sırası bozuk görsel FAIL'dir.",
         "> GÖRÜNTÜLENEMEZ biçimi `media/<kimlik>.kullanici.png` adına çevir (Pillow) ya da kullanıcıdan o adla PNG iste;",
         "> PNG'den okuduğunu notta yaz. `iz`: görüntülenebilir görselin (ya da kullanıcı PNG'si olanın) notu boşsa FAIL,",
         "> okunabilir kopyası olmayanınki boşsa ÖLÇÜLEMEDİ.",
         ""]
    if not gorseller:
        L.append("(Bu kaynakta okunacak görsel yok.)")
    for g in gorseller:
        L += ["## %s" % g["kimlik"], "",
              "- Dosya: `%s`" % gorunur(g["dosya"]),
              "- Kaynak parçası: `%s`" % gorunur(g["parca"]),
              "- Konum: %s" % (", ".join(g["konum"]) + " (metin.md'de işaretin durduğu satır)" if g["konum"]
                               else "metinde konumu yok (xlsx, üst/altbilgi ya da başka parçadan bağlı)"),
              "- Biçim: %s" % _bicim_satiri(g),
              GORULEN_SATIRI, isaret(g["kimlik"]), "", isaret(g["kimlik"], True), ""]
    yol.write_text("\n".join(L).rstrip() + "\n", encoding="utf-8")
    durum.append("iskelet yazıldı")
    return "; ".join(durum)


def gorulen_bos(metin: str) -> bool:
    """Yer tutucu boş sayılır: harf/rakam yoksa ("-", "?", "…" çok satırlı da olsa) ya da noktalama atılınca YER_TUTUCU."""
    s = re.sub(r"&#?\w+;", " ", metin)                  # HTML varlığı (&nbsp; …)
    s = re.sub(r"<[^<>\n]*>", " ", s)                   # HTML etiketi (<br> …)
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", s)         # Markdown görsel bağlantısı
    s = re.sub(r"^\W*todo\b:?", " ", s.casefold())      # baştaki "TODO:" ("TODO: doldur", "TODO TODO")
    net = re.sub(r"[\W_]+", "", s)
    duz = unicodedata.normalize("NFKD", net.replace("ı", "i")).encode("ascii", "ignore").decode()
    return (net == "" or net in YER_TUTUCU or re.fullmatch(r"x+", net) is not None or duz in ACILAMADI
            or re.fullmatch(r"k[gn]\d+", duz) is not None)


def _not_govdesi(metin: str) -> str:
    """Boşluk değerlendirmesi için işaretler arası metin: yorum (kapanmamışı dahil), iskelet satırı ("## KG-nn",
    "- Dosya: …", Görülen satırı), Markdown başlığı ve kod çiti satırı atılır — bunlar bilgi taşımaz."""
    s = re.sub(r"<!--.*", "", YORUM_RE.sub("", metin), flags=re.S)
    return "\n".join(x for x in s.splitlines()
                     if not (ISKELET_SATIRI_RE.match(x) or GORULEN_ALAN_RE.match(x) or re.match(r"^#{1,6}\s", x)
                             or re.match(r"^\s*(```|~~~)\S*\s*$", x)))


def gorsel_notlarini_oku(paket: Path) -> tuple[dict[str, str], list[str], dict[str, str]] | None:
    """(notlar {kimlik: işaretler arası metin, yer tutucu boş}, uyarılar, bozuk {kimlik: neden}); dosya yoksa None.
    Not YALNIZ `<!-- gorulen:K -->` ile `<!-- /gorulen:K -->` satırları arasından okunur (yorumlar ayıklanır). Kapanmayan
    açılış, açılışsız ya da başka kimliğin kapanışı → o kimlik BOZUK. Yinelenen işaret çifti ve bir görsel bölümünde
    işaretlerin dışında kalan metin (iskelet satırları hariç) UYARI'dır — sayılmaz, FAIL'i etkilemez."""
    yol = paket / NOT_DOSYASI
    if not yol.is_file():
        return None
    notlar: dict[str, str] = {}
    bozuk: dict[str, str] = {}
    uyari: list[str] = []
    dis: dict[str, list[int]] = {}
    acik, govde, bolum, kapanan = None, [], None, set()
    for no, s in enumerate(yol.read_bytes().decode("utf-8", "replace").splitlines(), 1):
        m = ISARET_RE.match(s)
        if m is None:
            if acik:
                govde.append(s)
                continue
            b = BOLUM_RE.match(s)
            if b:
                bolum = b.group(1)
            elif bolum and YORUM_RE.sub("", s).strip() and (bolum in kapanan or not ISKELET_SATIRI_RE.match(s)):
                # iskelet satırı yalnız işaret çiftinden ÖNCE muaftır; çift kapandıktan sonra gelen her metin dışarıdadır
                dis.setdefault(bolum, []).append(no)
            continue
        kapanis, kid = m.group(1) == "/", m.group(2)
        if not kapanis:
            if acik:
                bozuk.setdefault(acik, "kapanış işareti yok (satır %d'de `%s` açıldı)" % (no, isaret(kid)))
            acik, govde = kid, []
            continue
        if acik != kid:
            bozuk.setdefault(kid, "satır %d: `%s` açılışsız ya da sırası bozuk" % (no, isaret(kid, True)))
            if acik:
                bozuk.setdefault(acik, "kapanış işareti yok (satır %d'de başka kimliğin kapanışı)" % no)
            acik = None
            continue
        acik = None
        kapanan.add(kid)
        metin = YORUM_RE.sub("", "\n".join(govde)).strip()
        if kid in notlar:
            uyari.append("%s işaret çifti birden fazla — yalnız ilki sayıldı; fazlasını ilkine taşı" % kid)
        else:
            notlar[kid] = "" if gorulen_bos(_not_govdesi(metin)) else metin
    if acik:
        bozuk.setdefault(acik, "kapanış işareti yok (dosya sonu)")
    for kid, satirlar in sorted(dis.items()):
        uyari.append("%s bölümünde işaretlerin dışında metin (satır %s) — sayılmaz; notu `%s` ile `%s` arasına taşı"
                     % (kid, ", ".join(map(str, satirlar[:5])), isaret(kid), isaret(kid, True)))
    return notlar, uyari, bozuk


def varsayilan_id(kaynak: Path, veri: bytes) -> str:
    kok = re.sub(r"[^A-Za-z0-9ÇĞİÖŞÜçğıöşü_-]+", "-", kaynak.stem).strip("-")[:40] or "kaynak"
    return "%s-%s" % (kok, ozet(veri)[:8])


def paketi_yaz(c: Cikti, z: zipfile.ZipFile, kaynak: Path, veri: bytes, hedef: Path) -> None:
    (hedef / "media").mkdir(parents=True, exist_ok=True)
    (hedef / "gomulu").mkdir(parents=True, exist_ok=True)
    bas = ["<!-- kaynak_paketi.py MEKANİK çıkarım: %s (sha256 %s · km şeması %d). Elle ya da modelle yeniden "
           "yazılmaz; işaretler INDEX.md 'Nasıl okunur' bölümünde. -->" % (kaynak.name, ozet(veri)[:16], KM_SEMASI), ""]
    (hedef / "metin.md").write_text("\n".join(bas + c.satirlar).rstrip() + "\n", encoding="utf-8")
    for kid, ad, dosya in c.gorseller:
        yt = atlanan_dosya(c, kid, ad)
        (hedef / "media" / dosya).write_bytes(yt[1].encode("utf-8") if yt else z.read(ad))
    for _kid, _ad, dosya, icerik, _tur in c.gomululer:
        (hedef / "gomulu" / dosya).write_bytes(icerik)
    c.gorsel_bilgi = gorsel_listesi(c)
    c.not_durumu = gorsel_notlari_yaz(hedef, kaynak, veri, c.gorsel_bilgi)


def index_yaz(c: Cikti, kaynak: Path, veri: bytes, hedef: Path, kaynak_say: dict, paket_say: dict,
              farklar: list[str], parca: list[dict], yok: dict[str, int]) -> None:
    sonuc = "PASS" if not farklar else "FAIL"
    L = ["# Kaynak paketi — %s" % kaynak.name, "",
         "> Mekanik çıkarım (`kaynak_paketi.py cikar`). Bu klasördeki metin model tarafından YENİDEN YAZILMAZ, "
         "özetlenip kaynağın yerine konmaz. Alt ajana ya da inceleyiciye ikili kaynağın değil bu klasörün yolu verilir.",
         "", "- Kaynak: `%s` · %d bayt · sha256 `%s` · tür %s · km şeması %d" % (
             kaynak.name, len(veri), ozet(veri), c.tur, KM_SEMASI),
         "- Paket: `%s`" % hedef.as_posix(),
         "- DOĞRULAMA: **%s** — kaynağın bağımsız sayımı ↔ diskteki paket%s" % (
             sonuc, "" if not farklar else " (EŞİT DEĞİL: " + "; ".join(farklar) + ") — bu paketi KULLANMA"),
         "- " + yok_satiri(yok) + " (karakter; çıkarım bu metni bilerek almaz — sınıf tanımları SCOPE'ta)",
         "", "## Sayım", "", "| Ölçü | Kaynak (bağımsız) | Paket (diskten) | Durum |", "|---|---|---|---|"]
    for k, ad in SAYIM_ADLARI:
        if k in kaynak_say:
            L.append("| %s | %d | %d | %s |" % (ad, kaynak_say[k], paket_say.get(k, 0),
                                               "eşit" if kaynak_say[k] == paket_say.get(k, 0) else "**FARKLI**"))
    L.append("| geri düşüş maddesi (bilgi; bağımsız karşılığı parça hesabıdır) | — | %d | — |" % paket_say.get("km_geri", 0))
    L += ["", "## Parça hesabı (zip'teki her XML parçası; evren − yok sayılan = yapılandırılmış + geri düşüş)", "",
          "| Parça | Sınıf | Evren | Yok sayılan | Yapılandırılmış | Geri düşüş |", "|---|---|---|---|---|---|"]
    L += ["| `%s` | %s | %d | %d | %d | %d |" % (r["parca"].replace("|", "\\|"), r["sinif"], r["evren"], r["yok"],
                                                    r["yapi"], r["geri"])
          for r in parca]
    if c.geri:
        L += ["", "**Geri düşüşe giden parçalar** (yapılandırılmış çıkarım bu metni tanımıyor; metni metin.md sonunda "
              "ham — okurken bu parçaları ayrıca değerlendir): " + " · ".join(
                  "%s `%s` (%s; %s)" % (p, gorunur(a), "%s..%s" % (k[0], k[-1]) if len(k) > 1 else k[0], n)
                  for p, a, k, n in c.geri), ""]
    L += ["", "## Dosyalar", "", "- `metin.md` — kaynak maddeleri %s" % (
        "KM-0001…KM-%04d" % c.km if c.km else "yok"), ""]
    if c.sayfalar:
        L += ["Sayfalar: " + " · ".join("SY%02d = %s" % (i, a) for i, a in enumerate(c.sayfalar, 1)), ""]
    if c.gorseller or c.gomululer:
        L += ["| Kimlik | Kaynak parçası | Paket dosyası | Tür |", "|---|---|---|---|"]
        gb = {g["kimlik"]: g for g in c.gorsel_bilgi}

        def gorsel_turu(k: str, a: str) -> str:
            if atlanan_dosya(c, k, a):
                return atlanan_dosya(c, k, a)[1]
            g = gb.get(k)
            if g and g.get("yedek"):
                return "görsel (%s; PNG yedeği %s)" % (g["bicim"], g["yedek"])
            return "görsel (%s)" % g["bicim"] if g and g["goruntulenebilir"] else (g["neden"] if g else "görsel")
        L += ["| %s | `%s` | `media/%s` | %s |" % (k, hucre(a), hucre(d), gorsel_turu(k, a))
              for k, a, d in c.gorseller]
        L += ["| %s | `%s` | `gomulu/%s` | %s%s |" % (k, hucre(a), hucre(d), t, (" · " + gb[k]["neden"])
                                                       if k in gb and gb[k]["neden"] and not t.startswith("ÖLÇÜLEMEDİ")
                                                       else "")
              for k, a, d, _i, t in c.gomululer]
        L.append("")
    if c.gorsel_bilgi:
        olc = [g for g in c.gorsel_bilgi if olculemez(g)]
        L += ["## Görsel okuma — `%s`" % NOT_DOSYASI, "",
              "- %d görsel: %d görüntülenebilir · %d ÖLÇÜLEMEDİ%s. Not dosyası: %s." % (
                  len(c.gorsel_bilgi), len(c.gorsel_bilgi) - len(olc), len(olc),
                  (" (" + ", ".join("%s %s" % (g["kimlik"], g["neden"]) for g in olc) + ")") if olc else "",
                  c.not_durumu),
              "- Mekanik çıkarım görselin İÇİNDEKİ metni almaz. Her görseli `view` aracıyla aç, gördüğünü (ekran adı, "
              "alanlar, düğmeler, değerler, okunabilen metin) `%s`'de YALNIZ o görselin `<!-- gorulen:KG-nn -->` ile "
              "`<!-- /gorulen:KG-nn -->` işaret satırlarının arasına yaz — görsel başına bir `edit`. `kaynak_paketi.py "
              "iz` notu yalnız işaretlerin arasından okur; görüntülenebilir görselin boş notunu ve işareti bozuk notu "
              "FAIL sayar." % NOT_DOSYASI,
              "- Görüntülenebilir biçimler: %s. Diğerleri GÖRÜNTÜLENEMEZ (ör. `emf`): Pillow kuruluysa `%s` adına çevir, "
              "olmazsa kullanıcıdan PNG iste ve aynı ada kaydet — kopya varken boş not FAIL'dir. Paket dönüştürmez (ek "
              "bağımlılık yok). Kopyası olmayanın boş notu `iz`'de ÖLÇÜLEMEDİ'dir, PASS onu kapsamaz. SVG'nin PNG yedeği "
              "pakette varsa (`svgBlip`) SVG o PNG'nin bölümünde okunur." % (
                  ", ".join(u.lstrip(".") for u in GORUNTULENEBILIR), KULLANICI_PNG % "<kimlik>"), ""]
        if len(c.gorseller) + len(c.gomululer) > COK_GORSEL:
            L += ["- UYARI: %d görsel + gömülü nesne (eşik %d) — not yükü ve bağlam bütçesi büyük; okumayı bölümlere "
                  "ayır, kullanıcıyla önceliklendir." % (len(c.gorseller) + len(c.gomululer), COK_GORSEL), ""]
    if c.nesneler:
        L += ["Metin taşıyan çizim nesneleri (metni metin.md'de kendi KM satırında): " + " · ".join(
            "%s %s `%s`" % n for n in c.nesneler), ""]
    tanınmayan = [k for k, _a, _d, _i, t in c.gomululer if t.startswith("TANINMADI")]
    L += ["## Kapsam dışı / notlar", ""]
    L += ["- " + n for n in c.notlar] or ["- (yok)"]
    if tanınmayan:
        L.append("- TANINMAYAN gömülü nesne: %s — ham kopyalandı, içeriği kullanıcıya sor" % ", ".join(tanınmayan))
    disi_adlari = {x["parca"] for x in c.xml_disi}
    atlanan_dosyalar = sorted(a for a in c.atlanan if a not in disi_adlari)
    if atlanan_dosyalar:
        L.append("- ÖLÇÜLEMEDİ — boyut: %s — dosya çıkarılmadı, yerinde not dosyası var"
                 % ", ".join(gorunur(a) for a in atlanan_dosyalar))
    for x in c.xml_disi:
        L.append("- XML olmayan üye `%s` (%d bayt): %s" % (gorunur(x["parca"]), x["boyut"], x["not"]))
    cozulemeyen = cozulemeyen_basvurular(c)
    if cozulemeyen:
        L.append("- UYARI çözülemeyen başvuru (görsel/nesne işareti pakette bir dosyaya bağlanamadı): "
                 + " · ".join(cozulemeyen))
    if c.harici_gorsel:
        L.append("- UYARI harici görsel bağlantısı: %d — görsel kaynağın dışında (bağlantı), pakette yok; metin.md'de "
                 "`%s` işareti; kullanıcıdan görseli iste" % (c.harici_gorsel, HARICI_GORSEL))
    L += ["- Otomatik numaralar (başlık/liste numarası) Word'ün ürettiği metindir, metin.md'de yoktur.",
          "- Öznitelikteki metin (görsel alternatif metni, veri doğrulama istemi, köprü ipucu) alınmaz.", "",
          "## Nasıl okunur", "",
          "- Her `[KM-nnnn]` satırı bir kaynak maddesidir; `#` ile başlayan satır başlıktır.",
          "- `⟦T01.S03⟧ | a | b |` = tablo 1, satır 3; hücreler `|`, hücre içi paragraf `¶`; hücredeki gerçek `|`, `¶`, "
          "ters bölü ters bölüyle kaçırılır. xlsx'te `⟦SY01.S0003⟧` = sayfa 1, Excel satırı 3.",
          "- `⟦…⟧` paketin eklediği işarettir (görsel/gömülü nesnenin konumu, liste öğesi, `⟦denklem⟧`); kaynak metni "
          "değildir. `⟦D01 SmartArt: …⟧ | a | b |` = SmartArt'ın paragrafları, `⟦G01 grafik: …⟧` = grafiğin başlık, "
          "seri, kategori ve değer metni, `⟦K01 metin kutusu: …⟧` = xlsx çizimindeki metin kutusu.",
          "- `⟦P01 parça: <zip parçası>⟧ | … |` = geri düşüş: yapılandırılmış çıkarımın kapsamadığı metin, parçadan ham "
          "(paragraf altında birleşik). Üst/altbilgi, dipnot ve yorum buradadır; yapısı (hangi sayfa, hangi hücre) yoktur.",
          "- Gömülü HTML prototip tarayıcıda açılabilir; ekran görüntüsü `capture_kd_screens.js` ile `file://` "
          "adresinden çekilebilir.",
          "- İzlenebilirlik: FS yazılırken bu kimliklerle iz tablosu kurulur — paketin yanında DEĞİL, git'te izlenen "
          "`<source_root>/<MODÜL>/<PAKET>/ref_docs/iz-<belge no>.md` — ve `kaynak_paketi.py iz` ile denetlenir "
          "(`traceability.md` §2-B). Tablonun başına `Kaynak: %s · sha256 %s · km şeması %d` yazılır: paket git "
          "dışıdır; aynı kaynaktan AYNI BETİK SÜRÜMÜYLE (aynı km şeması) `cikar` aynı kimlikleri yeniden üretir."
          % (kaynak.name, ozet(veri)[:16], KM_SEMASI)]
    (hedef / "INDEX.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    meta = {"surum": 1, "km_semasi": KM_SEMASI,
            "kaynak": {"ad": kaynak.name, "boyut": len(veri), "sha256": ozet(veri), "tur": c.tur},
            "km_toplam": c.km, "kg": [k for k, _a, _d in c.gorseller], "kn": [k for k, *_r in c.gomululer],
            "sayim": {"kaynak": kaynak_say, "paket": paket_say}, "dogrulama": {"sonuc": sonuc, "farklar": farklar},
            "yok_sayilan": yok, "parca_hesabi": parca,
            "geri_dusus": [{"kimlik": p, "parca": a, "km": k, "not": n} for p, a, k, n in c.geri],
            "atlanan": c.atlanan, "xml_disi": c.xml_disi, "gorsel": c.gorsel_bilgi,
            "cozulemeyen": cozulemeyen_basvurular(c), "harici_gorsel": c.harici_gorsel,
            "gomulu": [{"kimlik": k, "parca": a, "dosya": "gomulu/" + d, "tur": t} for k, a, d, _i, t in c.gomululer],
            "nesne": [{"kimlik": k, "tur": t, "parca": a} for k, t, a in c.nesneler]}
    (hedef / "paket.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

# ── BÖLÜM: iz denetimi ────────────────────────────────────────────────────────────────────────────────────────
MADDE_RE = re.compile(r"\b(K[MGN])-(\d+)(?:\s*(?:\.\.|…|–|—)\s*(?:K[MGN]-)?(\d+))?\b")
GEREKSINIM_RE = re.compile(r"\b(?:FR|KR)-\d{3}\b")
SHA_RE = re.compile(r"\bsha256\W{0,3}([0-9a-fA-F]{16,64})\b")
SEMA_RE = re.compile(r"\bkm\s*[şs]emas[ıi]\W{0,3}(\d+)", re.I)


def _norm(s: str) -> str:
    s = s.replace("İ", "i").replace("I", "ı").lower()
    return s.translate(str.maketrans("ışğüöç", "isguoc"))


def _hucreler_md(satir: str) -> list[str]:
    govde = satir.strip()
    if govde.startswith("|"):
        govde = govde[1:]
    if govde.endswith("|") and not govde.endswith("\\|"):
        govde = govde[:-1]
    return [h.strip() for h in re.split(r"(?<!\\)\|", govde)]


def iz_denetle(paket: Path, tablo: Path, belgeler: list[Path]) -> tuple[int, list[str]]:
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    from doc_equivalence_check import ids as belge_kimlikleri  # aynı klasör; kimlik desenleri tek yerde

    L: list[str] = [SCOPE_IZ]
    try:
        meta = json.loads((paket / "paket.json").read_text(encoding="utf-8"))
        tablo_metni = tablo.read_text(encoding="utf-8")
        belge_metni = "\n".join(p.read_text(encoding="utf-8") for p in belgeler)
        disk, _sorun, _pay = diskten_say(paket, meta.get("kaynak", {}).get("tur", ""))
    except (OSError, ValueError) as exc:
        raise Okunamadi(str(exc)) from None
    fail: list[str] = []
    uyari: list[str] = []
    if meta.get("dogrulama", {}).get("sonuc") != "PASS":
        fail.append("paketin kendi doğrulaması PASS değil — önce paketi yeniden çıkar")
    if disk["km"] + disk["km_geri"] != meta.get("km_toplam"):
        fail.append("metin.md'deki KM sayısı (%d) paket.json ile (%s) uyuşmuyor — paket elle değiştirilmiş"
                    % (disk["km"] + disk["km_geri"], meta.get("km_toplam")))
    paket_sema = int(meta.get("km_semasi", 1))
    beklenen = {("KM", i) for i in range(1, int(meta.get("km_toplam") or 0) + 1)}
    beklenen |= {(k[:2], int(k[3:])) for k in meta.get("kg", []) + meta.get("kn", [])}
    belge_ids = belge_kimlikleri(belge_metni)
    kapsanan: dict[tuple[str, int], list[int]] = {}
    hayalet, bos, taninmayan, belgede_yok, gerekcesiz, elle = [], [], [], [], [], []
    anilan_ids: set[str] = set()
    esleme_ids: dict[tuple[str, int], set[str]] = {}   # madde → iz satırlarında eşlendiği belge kimlikleri
    satir_say = 0
    for no, satir in enumerate(tablo_metni.splitlines(), 1):
        if not satir.strip().startswith("|") or re.match(r"^\s*\|[\s:|-]+\|?\s*$", satir):
            continue
        h = _hucreler_md(satir)
        maddeler = []
        for m in MADDE_RE.finditer(h[0]):
            bas = int(m.group(2))
            son = int(m.group(3)) if m.group(3) else bas
            maddeler += [(m.group(1), i) for i in range(bas, son + 1)] if son >= bas else [(m.group(1), bas)]
        if not maddeler:
            continue  # başlık satırı
        satir_say += 1
        for md in maddeler:
            kapsanan.setdefault(md, []).append(no)
            if md not in beklenen:
                hayalet.append("%s-%s (satır %d)" % (md[0], md[1], no))
        esleme = h[1] if len(h) > 1 else ""
        notu = h[2] if len(h) > 2 else ""
        n = _norm(esleme)
        if not n or n in ("-", "—", "?"):
            bos.append("satır %d: %s" % (no, h[0]))
        elif re.match(r"^bilgi\b", n):
            elle.append("satır %d BİLGİ: %s" % (no, h[0]))
        elif re.match(r"^kapsam[- ]?disi\b", n):
            elle.append("satır %d KAPSAM-DIŞI: %s" % (no, h[0]))
            if not notu.strip(" -—"):
                gerekcesiz.append("satır %d: %s" % (no, h[0]))
        else:
            ids = belge_kimlikleri(esleme)
            if not ids:
                taninmayan.append("satır %d: %r" % (no, esleme))
            anilan_ids |= ids
            for md in maddeler:
                esleme_ids.setdefault(md, set()).update(ids)
            for i in sorted(ids - belge_ids):
                belgede_yok.append("%s (satır %d)" % (i, no))
    kaynak_bilgi = meta.get("kaynak", {})
    sha = str(kaynak_bilgi.get("sha256", "")).lower()
    sha_tabloda = [x.lower() for x in SHA_RE.findall(tablo_metni)]
    sha_yanlis = ["tablo: %s · paket: %s" % (", ".join(sha_tabloda), sha[:16])] \
        if sha_tabloda and not any(sha.startswith(x) for x in sha_tabloda) else []
    sha_yok = ["tablonun başına `Kaynak: %s · sha256 %s · km şeması %d` satırını yaz"
               % (kaynak_bilgi.get("ad", "?"), sha[:16], paket_sema)] if not sha_tabloda else []
    sema_tabloda = sorted({int(x) for x in SEMA_RE.findall(tablo_metni)})
    sema_farkli = ["tablo: km şeması %s · paket: km şeması %d — paketi yeniden çıkar, tabloyu yeniden eşle"
                   % (", ".join(map(str, sema_tabloda)), paket_sema)] \
        if sema_tabloda and sema_tabloda != [paket_sema] else []
    sema_yok = ["tablonun başlık satırına `km şeması %d` ekle — yoksa tablonun hangi numaralandırmayla eşlendiği "
                "denetlenemez" % paket_sema] if not sema_tabloda else []
    # Görsel okuma: görüntülenebilir görselin notu boşsa FAIL; görüntülenemeyeninki boşsa ÖLÇÜLEMEDİ (FAIL değil).
    # Not doluysa UYARI: notta anılan belge kimliği o görselin iz satırında yok (görselden gelen kalem tabloya
    # taşınmamış). "Not dolu ama satır BİLGİ" ayrıca uyarılmaz: logo/ikon için meşrudur ve her pakette gürültü üretir;
    # görselden gereksinim türediğinin mekanik işareti nottaki `→ FR-nnn` kimliğidir (iskelet bunu ister).
    gorseller = meta.get("gorsel")
    okuma = gorsel_notlarini_oku(paket)
    notlar, not_yapi, bozuk = okuma if okuma is not None else (None, [], {})
    gorsel_sorun, okunmadi, olculemedi, not_kimlik, not_bozuk = [], [], [], [], []
    # Görüntülenemeyen görselin okunabilir kopyası (`media/<kimlik>.kullanici.png`) varsa görsel okunabilir sayılır.
    kopyali = {g["kimlik"] for g in gorseller or [] if not g["goruntulenebilir"]
               and len(kullanici_kopyasi(paket, g["kimlik"])) == 1}
    for g in gorseller or []:
        if len(kullanici_kopyasi(paket, g["kimlik"])) > 1:
            not_yapi.append("%s için harf farkıyla birden çok kullanıcı kopyası (%s) — birini bırak" % (
                g["kimlik"], ", ".join(gorunur(p.name) for p in kullanici_kopyasi(paket, g["kimlik"]))))
    if gorseller is None and meta.get("kg"):
        gorsel_sorun.append("paket.json'da görsel listesi yok — paket görsel notlarından önceki sürümle çıkarılmış; "
                            "yeniden çıkar")
    elif gorseller and notlar is None:
        gorsel_sorun.append("`%s` yok — paketi yeniden çıkar, görselleri `view` ile okuyup notlara yaz" % NOT_DOSYASI)
    if notlar is not None:
        bilinen = {g["kimlik"] for g in gorseller or []}
        for k, neden in sorted(bozuk.items()):
            not_bozuk.append("%s: %s" % (k, neden) if k in bilinen else "%s (pakette böyle görsel yok): %s" % (k, neden))
        for k in sorted(bilinen - set(notlar) - set(bozuk)):
            not_bozuk.append("%s: işaret çifti yok (`%s` … `%s`) — iskelet satırları silinmiş" % (
                k, isaret(k), isaret(k, True)))
    for g in (gorseller or []) if notlar is not None else []:
        k = g["kimlik"]
        if k in bozuk or k not in notlar:
            continue
        gorulen = notlar[k]
        if not gorulen:
            if g["goruntulenebilir"]:
                okunmadi.append(k)
            elif k in kopyali:
                okunmadi.append("%s (okunabilir kopya `%s`)" % (k, KULLANICI_PNG % k))
            elif not g.get("yedek"):  # SVG'nin PNG yedeği kendi bölümünde okunur
                olculemedi.append("%s %s" % (k, g["neden"]))
            continue
        eslenen = esleme_ids.get((k[:2], int(k[3:])), set())
        for i in sorted(belge_kimlikleri(gorulen) - eslenen):
            not_kimlik.append("%s: %s notta var, iz satırında yok" % (k, i))
    bos_paket = ["paket 0 kaynak maddesi taşıyor — kaynak gerçekten boş mu? INDEX.md kapsam notlarına bak"] \
        if not beklenen else []
    eksik = sorted(beklenen - set(kapsanan))
    cift = {md: s for md, s in kapsanan.items() if len(s) > 1}
    kaynaksiz = sorted(set(GEREKSINIM_RE.findall(belge_metni)) - anilan_ids)

    def fmt(md):
        return "%s-%0*d" % (md[0], 4 if md[0] == "KM" else 2, md[1])

    L.append("## İz denetimi — paket `%s` · tablo `%s` · belge %s" % (
        paket.as_posix(), tablo.as_posix(), ", ".join("`%s`" % p.as_posix() for p in belgeler)))
    L.append("kaynak: %s · sha256 %s · km şeması %d" % (kaynak_bilgi.get("ad", "?"), sha[:16], paket_sema))
    L.append("paket maddeleri: %d (KM %d · KG %d · KN %d) · madde anan tablo satırı: %d · kapsanan: %d/%d" % (
        len(beklenen), meta.get("km_toplam") or 0, len(meta.get("kg", [])), len(meta.get("kn", [])), satir_say,
        len(beklenen & set(kapsanan)), len(beklenen)))
    if gorseller:
        L.append("görseller: %d (görüntülenebilir %d · okunabilir kopyalı %d · PNG yedekli SVG %d · ÖLÇÜLEMEDİ biçim/boyut "
                 "%d) · notu dolu %d — `%s`" % (
                     len(gorseller), sum(1 for g in gorseller if g["goruntulenebilir"]), len(kopyali),
                     sum(1 for g in gorseller if g.get("yedek")),
                     sum(1 for g in gorseller if olculemez(g) and g["kimlik"] not in kopyali),
                     sum(1 for g in gorseller if (notlar or {}).get(g["kimlik"])), NOT_DOSYASI))
    cozulemeyen = list(meta.get("cozulemeyen") or [])
    if meta.get("harici_gorsel"):
        cozulemeyen.append("%d harici görsel bağlantısı — görsel pakette yok, kullanıcıdan iste"
                           % meta["harici_gorsel"])
    olcu: list[str] = []
    for baslik, liste, sinif in (
            ("EKSİK — tabloda olmayan kaynak maddesi", [fmt(m) for m in eksik], fail),
            ("HAYALET — pakette olmayan madde", hayalet, fail),
            ("BOŞ EŞLEME", bos, fail),
            ("TANINMAYAN EŞLEME — ne belge kimliği ne BİLGİ/KAPSAM-DIŞI", taninmayan, fail),
            ("BELGEDE YOK — eşlenen kimlik belgede geçmiyor", belgede_yok, fail),
            ("KAPSAM-DIŞI GEREKÇESİZ — not sütunu boş", gerekcesiz, fail),
            ("BAŞKA KAYNAĞIN TABLOSU — tablodaki sha256 paketin kaynağıyla uyuşmuyor", sha_yanlis, fail),
            ("NUMARALANDIRMA ŞEMASI FARKLI — paketi yeniden çıkar, tabloyu yeniden eşle", sema_farkli, fail),
            ("GÖRSEL NOTLARI DENETLENEMEDİ", gorsel_sorun, fail),
            ("GÖRSEL NOTU BOZUK — işaret eksik ya da sırası bozuk; not okunamadı", not_bozuk, fail),
            ("GÖRSEL OKUNMADI", okunmadi, fail),
            ("GÖRSEL ÖLÇÜLEMEDİ", olculemedi, olcu),
            ("UYARI boş paket", bos_paket, uyari),
            ("UYARI tabloda kaynak sha256'sı yok — iz hangi kaynağa ait olduğunu söylemiyor", sha_yok, uyari),
            ("UYARI tabloda km şeması yok", sema_yok, uyari),
            ("UYARI çift eşleme — aynı madde birden çok satırda",
             ["%s (satır %s)" % (fmt(m), ", ".join(map(str, s))) for m, s in sorted(cift.items())], uyari),
            ("UYARI kaynaksız gereksinim — belgede var, tabloda anılmıyor (danışman önerisi mi? gerekçesi 11-A/EK'te mi?)",
             kaynaksiz, uyari),
            ("UYARI görsel notundaki kimlik iz tablosunda o görsele eşlenmemiş", not_kimlik, uyari),
            ("UYARI görsel notları dosyasının yapısı", not_yapi, uyari),
            ("UYARI çözülemeyen görsel/nesne başvurusu ya da pakette olmayan görsel", cozulemeyen, uyari)):
        if baslik in ("GÖRSEL OKUNMADI", "GÖRSEL ÖLÇÜLEMEDİ"):
            L.append("%s: %d%s" % (baslik, len(liste), (" — " + ", ".join(liste)) if liste else ""))
        else:
            L.append("%s: %d" % (baslik, len(liste)))
            for x in liste[:200]:
                L.append("  - %s" % x)
        if liste:
            sinif.append(baslik)
    if okunmadi:
        L.append("  → `%s`'de bu görsellerin işaretleri arası boş: görseli `view` ile aç, gördüğünü `%s` ile `%s` "
                 "arasına yaz" % (NOT_DOSYASI, isaret("<kimlik>"), isaret("<kimlik>", True)))
    if not_bozuk:
        L.append("  → işaret satırlarını iskeletteki biçimiyle geri koy (her görselde bir `%s` ve onu izleyen bir `%s`); "
                 "işaret dışındaki metin sayılmaz" % (isaret("<kimlik>"), isaret("<kimlik>", True)))
    if olculemedi:
        L.append("  → görüntülenemeyen biçim: Pillow ile `%s` adına çevir ya da kullanıcıdan o adla PNG iste; okununca "
                 "notu yaz (PNG'den okunduğunu belirt)" % (KULLANICI_PNG % "<kimlik>"))
    L.append("İNCELEYİCİNİN ELLE OKUYACAĞI (BİLGİ / KAPSAM-DIŞI işaretli satırlar — madde metni metin.md'de): %d" % len(elle))
    for x in elle[:200]:
        L.append("  - %s" % x)
    for f in fail:
        if f.startswith(("paket", "metin.md")):
            L.append("FAIL: " + f)
    L.append("SONUÇ: " + ("PASS — her kaynak maddesi bir satırda, eşlemeler belgede var (anlamca doğruluk ölçülmedi)"
                          if not fail else "FAIL — yukarıdaki listeler kapatılmadan inceleme bu tabloya dayanamaz")
             + (" · ÖLÇÜLEMEDİ: %d görsel okunamadı (%s) — sonuç bu görselleri KAPSAMAZ"
                % (len(olculemedi), ", ".join(olculemedi)) if olculemedi else ""))
    return (0 if not fail else 1), L

# ── BÖLÜM: main ───────────────────────────────────────────────────────────────────────────────────────────────
def cikar(a: argparse.Namespace) -> int:
    print(SCOPE_CIKAR)
    kaynak = Path(a.kaynak)
    uz = kaynak.suffix.lower()
    if uz not in DESTEKLENEN:
        neden = DESTEKLENMEYEN_NEDEN.get(uz, "bu uzantı için okuyucu yok")
        print(f"DESTEKLENMİYOR: {kaynak.name} ({uz or 'uzantısız'}) — {neden}. Desteklenen: {', '.join(DESTEKLENEN)}. "
              "Kullanıcıdan kaynağın .docx/.xlsx hâlini iste. Metni modelle yeniden yazarak paket ÜRETME.")
        return 3
    try:
        veri = kaynak.read_bytes()
    except OSError as exc:
        print(f"[ÖLÇÜLEMEDİ] {kaynak}: {exc}", file=sys.stderr)
        return 2
    import io
    try:
        z = zipfile.ZipFile(io.BytesIO(veri))
    except zipfile.BadZipFile:
        print(f"[ÖLÇÜLEMEDİ] {kaynak.name}: zip değil — bozuk ya da uzantısı yanlış (eski .doc/.xls olabilir)",
              file=sys.stderr)
        return 2
    maske, yapi_kaynak = None, {}
    try:
        atla = boyut_denetle(z)
        if uz in (".xlsx", ".xlsm"):
            xl = xlsx_okuyucu()
            if xl is None:
                print("DESTEKLENMİYOR: xlsx okuyucusu (skills/office-excel/scripts/xlsx_lite.py) bu klonda yok.")
                return 3
            c = xlsx_cikar(z, kaynak, xl, atla)
            kaynak_say, maske, yapi_kaynak = bagimsiz_xlsx(z)
        else:
            c = docx_cikar(z, atla)
            kaynak_say = bagimsiz_docx(z)
        evren = evren_tara(z, atla, c.xml_disi)
    except Okunamadi as exc:
        print(f"[ÖLÇÜLEMEDİ] {kaynak.name}: {exc}", file=sys.stderr)
        return 2
    kok = Path(a.hedef_kok) if a.hedef_kok else Path.cwd() / ".axet-code" / "tmp"
    hedef = (kok / guvenli_ad(a.id or varsayilan_id(kaynak, veri), "kaynak")).resolve()
    paketi_yaz(c, z, kaynak, veri, hedef)
    paket_say, sorunlar, pay = diskten_say(hedef, c.tur, maske)
    parca, parca_fark = parca_hesabi(evren, pay, yapi_kaynak)
    kaynak_say["parca_metni"] = sum(e["net"] for e in evren.values() if not e["muaf"])
    paket_say["parca_metni"] = sum(r["yapi"] + r["geri"] for r in parca if not r["sinif"].startswith("muaf"))
    yok = yok_toplami(evren)
    farklar = karsilastir(kaynak_say, paket_say) + parca_fark + sorunlar
    index_yaz(c, kaynak, veri, hedef, kaynak_say, paket_say, farklar, parca, yok)
    print(f"PAKET: {hedef.as_posix()}")
    if c.gorsel_bilgi:
        olc = [g["kimlik"] + " " + g["neden"] for g in c.gorsel_bilgi if olculemez(g)]
        print("GÖRSEL NOTLARI: %s — %d görsel%s; %s. Her görseli `view` ile aç, notunu yalnız o görselin işaret "
              "satırlarının arasına yaz (görsel başına bir edit); `iz` boş ya da işareti bozuk notu FAIL sayar." % ((hedef / NOT_DOSYASI).as_posix(), len(c.gorsel_bilgi),
                                                   (" (ÖLÇÜLEMEDİ: " + ", ".join(olc) + " — Pillow ile `"
                                                    + KULLANICI_PNG % "<kimlik>" + "` adına çevir ya da kullanıcıdan "
                                                    "PNG iste)") if olc else "", c.not_durumu))
    for x in cozulemeyen_basvurular(c):
        print("UYARI çözülemeyen başvuru: %s" % x)
    if c.harici_gorsel:
        print("UYARI harici görsel bağlantısı: %d — pakette yok, kullanıcıdan iste" % c.harici_gorsel)
    for k, ad in SAYIM_ADLARI:
        if k in kaynak_say:
            print("  %-45s kaynak %6d · paket %6d%s" % (ad, kaynak_say[k], paket_say.get(k, 0),
                                                       "" if kaynak_say[k] == paket_say.get(k, 0) else "  ← FARKLI"))
    for kid, _ad, dosya, _i, tur in c.gomululer:
        print(f"  {kid}: gomulu/{dosya} — {tur}")
    for kid, etiket, parca_adi in c.nesneler:
        print(f"  {kid}: {etiket} — {parca_adi} (metni metin.md'de)")
    for pid, parca_adi, kimlikler, notu in c.geri:
        print(f"  {pid}: geri düşüş — {gorunur(parca_adi)} ({len(kimlikler)} KM; {notu})")
    disi_adlari = {x["parca"] for x in c.xml_disi}
    for parca_adi in sorted(a for a in c.atlanan if a not in disi_adlari):
        print("  ÖLÇÜLEMEDİ — boyut: %s (dosya çıkarılmadı)" % gorunur(parca_adi))
    for x in c.xml_disi:
        print("  XML olmayan üye: %s (%d bayt) — %s" % (gorunur(x["parca"]), x["boyut"], x["not"]))
    print("  " + yok_satiri(yok))
    try:
        hedef.relative_to(Path.cwd().resolve())
    except ValueError:
        print("UYARI: paket çalışma dizini DIŞINDA — alt ajanın dış okuması izin sorusunda asılı kalabilir; "
              "brife proje içindeki bir yol ver.")
    if farklar:
        print("DOĞRULAMA: FAIL — " + "; ".join(farklar) + " · " + yok_satiri(yok)
              + ". Bu paketi brife/yazıma KAYNAK olarak verme.")
        return 1
    print(f"DOĞRULAMA: PASS · {yok_satiri(yok)}. Yazıma ve brife verilecek yol: {(hedef / 'INDEX.md').as_posix()}")
    return 0


def iz(a: argparse.Namespace) -> int:
    try:
        rc, satirlar = iz_denetle(Path(a.paket), Path(a.tablo), [Path(b) for b in a.belge])
    except Okunamadi as exc:
        print(SCOPE_IZ)
        print(f"[ÖLÇÜLEMEDİ] {exc} — bu 'PASS' ANLAMINA GELMEZ.", file=sys.stderr)
        return 2
    print("\n".join(satirlar))
    return rc


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="İkili kaynak belgeden mekanik kaynak paketi + kaynak→belge iz denetimi")
    alt = ap.add_subparsers(dest="komut", required=True)
    c = alt.add_parser("cikar", help="kaynak paketi üret")
    c.add_argument("kaynak")
    c.add_argument("--hedef-kok", default=None, help="varsayılan: <çalışma dizini>/.axet-code/tmp")
    c.add_argument("--id", default=None, help="paket klasör adı; varsayılan <dosya adı>-<içerik özeti 8 hane>")
    i = alt.add_parser("iz", help="kaynak maddesi → belge kimliği tablosunu denetle")
    i.add_argument("paket")
    i.add_argument("--tablo", required=True)
    i.add_argument("--belge", action="append", required=True, help="tekrarlanabilir: FS + EK …")
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    try:
        return cikar(a) if a.komut == "cikar" else iz(a)
    except Exception as exc:  # noqa: BLE001 — yakalanmayan hata Python'un çıkış 1'i olur ve FAIL ile karışır
        print(f"[ÖLÇÜLEMEDİ] beklenmeyen hata ({type(exc).__name__}: {exc}) — bu 'PASS' ya da 'FAIL' DEĞİLDİR; "
              "girdiyi ve hatayı bakımcıya bildir.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
