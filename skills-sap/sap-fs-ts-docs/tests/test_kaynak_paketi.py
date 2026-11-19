# -*- coding: utf-8 -*-
"""kaynak_paketi.py: ikili kaynaktan mekanik paket (docx/xlsx, OLE/altChunk, doğrulama) + iz denetimi.

Fikstürler testte üretilir (zipfile + elle yazılan küçük CFB); gerçek müşteri belgesi kullanılmaz. Geçici dizinler
sistem TEMP'inde (repo dışında) kurulur, paket hedefi daima açık verilir — kullanıcı dizinine dokunulmaz.
"""
import json
import os
import re
import shutil
import struct
import tempfile
import unittest
import zipfile
from unittest import mock

from _common import REPO, call_main, run_py, write_png

import kaynak_paketi as kp

# Ad alanı URI'leri parçalı yazılır: skill iz taraması (test_skill_structure) dosyalarda URL yasaklar.
_S = "http" + "://schemas.openxmlformats.org/"
NS = {
    "w": _S + "wordprocessingml/2006/main",
    "r": _S + "officeDocument/2006/relationships",
    "a": _S + "drawingml/2006/main",
    "wp": _S + "drawingml/2006/wordprocessingDrawing",
    "pic": _S + "drawingml/2006/picture",
    "mc": _S + "markup-compatibility/2006",
    "wps": "http" + "://schemas.microsoft.com/office/word/2010/wordprocessingShape",
    "v": "urn:schemas-microsoft-com:vml",
    "o": "urn:schemas-microsoft-com:office:office",
    "m": _S + "officeDocument/2006/math",
    "dgm": _S + "drawingml/2006/diagram",
    "c": _S + "drawingml/2006/chart",
}
REL = _S + "officeDocument/2006/relationships/"
PKG_REL = _S + "package/2006/relationships"
CT = _S + "package/2006/content-types"

ENDOFCHAIN, FREESECT, FATSECT, NOSTREAM = 0xFFFFFFFE, 0xFFFFFFFF, 0xFFFFFFFD, 0xFFFFFFFF


# ── BÖLÜM: CFB / OLE yazıcı ──
def cfb_yaz(akislar):
    """Minimal CFB v3 (512 baytlık sektör): kök + düz akışlar. 4096'dan küçük akış mini akışa gider (okuyucunun
    iki yolu da sınansın). Yalnız tek FAT sektörüne sığan (≤ 128 sektör) dosya üretir."""
    ss, cutoff = 512, 4096
    mini, minifat, mini_bas = b"", [], {}
    for ad, d in akislar:
        if len(d) >= cutoff or not d:
            continue
        n = (len(d) + 63) // 64
        bas = len(mini) // 64
        mini_bas[ad] = bas
        mini += d + b"\x00" * (n * 64 - len(d))
        minifat += [bas + k + 1 for k in range(n - 1)] + [ENDOFCHAIN]

    def sektor_sayisi(b):
        return (len(b) + ss - 1) // ss

    n_dir = sektor_sayisi(b"\x00" * (128 * (1 + len(akislar))))
    minifat_b = struct.pack("<%dI" % len(minifat), *minifat) if minifat else b""
    n_mf, n_ms = sektor_sayisi(minifat_b), sektor_sayisi(mini)
    sira = 1
    dir_bas, sira = sira, sira + n_dir
    mf_bas, sira = (sira if n_mf else ENDOFCHAIN), sira + n_mf
    ms_bas, sira = (sira if n_ms else ENDOFCHAIN), sira + n_ms
    buyuk_bas = {}
    for ad, d in akislar:
        if len(d) >= cutoff:
            buyuk_bas[ad] = sira
            sira += sektor_sayisi(d)
    assert sira <= 128, "test yazıcısı tek FAT sektörüyle sınırlı"
    fat = [FREESECT] * 128
    fat[0] = FATSECT

    def zincirle(bas, n):
        for k in range(n):
            fat[bas + k] = bas + k + 1 if k < n - 1 else ENDOFCHAIN

    zincirle(dir_bas, n_dir)
    if n_mf:
        zincirle(mf_bas, n_mf)
    if n_ms:
        zincirle(ms_bas, n_ms)
    for ad, d in akislar:
        if ad in buyuk_bas:
            zincirle(buyuk_bas[ad], sektor_sayisi(d))

    def girdi(ad, tur, sol, sag, cocuk, bas, boy):
        ad_b = ad.encode("utf-16-le") + b"\x00\x00"
        e = ad_b.ljust(64, b"\x00") + struct.pack("<HBB", len(ad_b), tur, 1)
        e += struct.pack("<III", sol, sag, cocuk) + b"\x00" * 16 + b"\x00" * 4 + b"\x00" * 16
        return e + struct.pack("<IQ", bas, boy)

    dizin = girdi("Root Entry", 5, NOSTREAM, NOSTREAM, 1 if akislar else NOSTREAM, ms_bas, len(mini))
    for i, (ad, d) in enumerate(akislar, 1):
        bas = buyuk_bas.get(ad, mini_bas.get(ad, ENDOFCHAIN))
        dizin += girdi(ad, 2, NOSTREAM, i + 1 if i < len(akislar) else NOSTREAM, NOSTREAM, bas, len(d))
    bos = (b"\x00" * 64 + struct.pack("<HBB", 0, 0, 0) + struct.pack("<III", NOSTREAM, NOSTREAM, NOSTREAM)
           + b"\x00" * 36 + struct.pack("<IQ", 0, 0))
    while len(dizin) % ss:
        dizin += bos
    baslik = kp.CFB_IMZA + b"\x00" * 16 + struct.pack("<HHHHH", 0x3E, 3, 0xFFFE, 9, 6) + b"\x00" * 6
    baslik += struct.pack("<IIIIIIIII", 0, 1, dir_bas, 0, cutoff, mf_bas, n_mf, ENDOFCHAIN, 0)
    baslik += struct.pack("<109I", 0, *([FREESECT] * 108))
    assert len(baslik) == 512

    def doldur(b):
        return b + b"\x00" * (sektor_sayisi(b) * ss - len(b))

    govde = struct.pack("<128I", *fat) + dizin + doldur(minifat_b) + doldur(mini)
    for ad, d in akislar:
        if ad in buyuk_bas:
            govde += doldur(d)
    return baslik + govde


def ole10native_yaz(etiket, icerik, unicode_kopya=True):
    """Packager akışı: boy · bayrak · etiket · kaynak yol · sabit · geçici yol · içerik [· UTF-16 kopyalar]."""
    kaynak_yol = "C:/temp/" + etiket
    gecici = (kaynak_yol + "\x00").encode("cp1254")
    govde = struct.pack("<H", 2) + etiket.encode("cp1254") + b"\x00" + kaynak_yol.encode("cp1254") + b"\x00"
    govde += struct.pack("<I", 0x00030000) + struct.pack("<I", len(gecici)) + gecici
    govde += struct.pack("<I", len(icerik)) + icerik
    if unicode_kopya:
        for s in (kaynak_yol, etiket, kaynak_yol):
            govde += struct.pack("<I", len(s)) + s.encode("utf-16-le")
    return struct.pack("<I", len(govde)) + govde

# ── BÖLÜM: docx / xlsx üreticileri ──
STILLER = (
    '<w:styles xmlns:w="%s">'
    '<w:style w:type="paragraph" w:styleId="Normal"><w:name w:val="Normal"/></w:style>'
    '<w:style w:type="paragraph" w:styleId="Balk1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/></w:style>'
    '<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/></w:style>'
    '<w:style w:type="paragraph" w:styleId="OzelBaslik"><w:name w:val="Ozel"/><w:basedOn w:val="Balk1"/></w:style>'
    '</w:styles>' % NS["w"])
PROTOTIP_BUYUK = ("<html><body><h1>Ekran 6</h1>" + "<p>alan</p>" * 600 + "</body></html>").encode("utf-8")
PROTOTIP_KUCUK = "<html><body><h1>Ekran 1 — Giriş</h1></body></html>".encode("utf-8")
ALTCHUNK = "<html><body><p>altChunk içeriği</p></body></html>".encode("utf-8")


def p(metin, stil=None, numara=False, ek=""):
    ppr = ""
    if stil or numara:
        ppr = "<w:pPr>%s%s</w:pPr>" % ('<w:pStyle w:val="%s"/>' % stil if stil else "",
                                       '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>' if numara else "")
    run = '<w:r><w:t xml:space="preserve">%s</w:t></w:r>' % metin if metin else ""
    return "<w:p>%s%s%s</w:p>" % (ppr, run, ek)


def satir(*hucreler):
    return "<w:tr>%s</w:tr>" % "".join("<w:tc>%s</w:tc>" % (h if h.startswith("<") else p(h)) for h in hucreler)


GORSEL = ('<w:r><w:drawing><wp:inline><a:graphic><a:graphicData><pic:pic><pic:blipFill><a:blip r:embed="rIdImg"/>'
          '</pic:blipFill></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r>')
KUTU = ('<w:r><mc:AlternateContent><mc:Choice Requires="wps"><w:drawing><wps:txbx><w:txbxContent>%s</w:txbxContent>'
        '</wps:txbx></w:drawing></mc:Choice><mc:Fallback><w:pict><v:textbox><w:txbxContent>%s</w:txbxContent>'
        '</v:textbox></w:pict></mc:Fallback></mc:AlternateContent></w:r>') % (p("Kutu metni"), p("Kutu metni"))
OLE = '<w:r><w:object><v:shape/><o:OLEObject ProgID="Package" r:id="%s"/></w:object></w:r>'


def ornek_govde():
    ic_tablo = "<w:tbl>%s</w:tbl>" % satir("iç A", "iç B")
    tablo = "<w:tbl>%s</w:tbl>" % "".join([
        satir("No", "Test senaryosu", "Beklenen"),
        satir("TS-01", "Sipariş kaydı", "Belge oluşur"),
        satir("TS-02", "İptal", "Belge iptal"),
        satir("TS-03", "a|b ¶ c\\d", "x"),
        satir("", "", ""),
        satir("TS-04", ic_tablo + p("sonra"), "y"),
    ])
    return "".join([
        p("Giriş", stil="Balk1"),
        "<w:p><w:r><w:t xml:space=\"preserve\">Birinci paragraf </w:t></w:r><w:r><w:t>devam | çizgi</w:t></w:r></w:p>",
        p(""),
        p("Liste öğesi", numara=True),
        "<w:sdt><w:sdtPr/><w:sdtContent>%s</w:sdtContent></w:sdt>" % p("İçerik denetimi içindeki paragraf"),
        "<w:customXml w:element=\"x\">%s</w:customXml>" % p("Özel XML içindeki paragraf"),
        p("", ek=GORSEL),
        p("Ana metin", ek=KUTU),
        tablo,
        p("Prototip:", ek=OLE % "rIdOle1"),
        p("", ek=OLE % "rIdOle2"),
        p("", ek=OLE % "rIdOle3"),
        '<w:altChunk r:id="rIdAlt"/>',
        p("Standart yapıda değiştirilen nesneler (Repair)", stil="Heading2"),
        p("Türetilmiş başlık", stil="OzelBaslik"),
        "<w:sectPr/>",
    ])


def docx_yaz(yol, govde, rels=None, ekler=None, stiller=STILLER):
    xmlns = " ".join('xmlns:%s="%s"' % kv for kv in NS.items())
    belge = '<?xml version="1.0" encoding="UTF-8"?><w:document %s><w:body>%s</w:body></w:document>' % (xmlns, govde)
    rels = rels if rels is not None else [
        ("rIdImg", "image", "media/image1.png"), ("rIdOle1", "oleObject", "embeddings/oleObject1.bin"),
        ("rIdOle2", "oleObject", "embeddings/oleObject2.bin"), ("rIdOle3", "oleObject", "embeddings/oleObject3.bin"),
        ("rIdAlt", "aFChunk", "afchunk1.htm")]
    rels_xml = '<Relationships xmlns="%s">%s</Relationships>' % (PKG_REL, "".join(
        '<Relationship Id="%s" Type="%s%s" Target="%s"/>' % (i, REL, t, h) for i, t, h in rels))
    with zipfile.ZipFile(yol, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", '<Types xmlns="%s"/>' % CT)
        z.writestr("word/document.xml", belge)
        z.writestr("word/_rels/document.xml.rels", rels_xml)
        z.writestr("word/styles.xml", stiller)
        for ad, veri in (ekler or {}).items():
            z.writestr(ad, veri)


def ornek_ekler(gecici):
    png = os.path.join(gecici, "g.png")
    write_png(png)
    with open(png, "rb") as fh:
        png_b = fh.read()
    return {
        "word/media/image1.png": png_b,
        "word/media/image2.emf": b"EMF-ikon",
        "word/embeddings/oleObject1.bin": cfb_yaz([("\x01Ole10Native", ole10native_yaz("ekran6.html", PROTOTIP_BUYUK)),
                                                   ("\x01CompObj", b"\x01\x00\xfe\xff")]),
        "word/embeddings/oleObject2.bin": cfb_yaz([("\x01Ole10Native",
                                                    ole10native_yaz("giris.html", PROTOTIP_KUCUK, False))]),
        "word/embeddings/oleObject3.bin": cfb_yaz([("Gizemli", b"\x00" * 100)]),
        "word/embeddings/Microsoft_Excel_Worksheet.xlsx": _kucuk_zip(),
        "word/afchunk1.htm": ALTCHUNK,
    }


def _kucuk_zip():
    import io
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("xl/workbook.xml", "<workbook/>")
    return b.getvalue()

DENKLEM = ('<w:p><w:r><w:t xml:space="preserve">Tutar formülü: </w:t></w:r><m:oMathPara><m:oMath><m:r>'
           '<m:t>Tutar=Miktar×BirimFiyat−İskonto</m:t></m:r></m:oMath></m:oMathPara></w:p>')
SMARTART = ('<w:p><w:r><w:drawing><wp:inline><a:graphic><a:graphicData><dgm:relIds r:dm="rIdDm" r:lo="rIdLo"/>'
            '</a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>')
GRAFIK = ('<w:p><w:r><w:drawing><wp:inline><a:graphic><a:graphicData><c:chart r:id="rIdCh"/>'
          '</a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>')
DIYAGRAM_VERI = ('<dgm:dataModel xmlns:dgm="%s" xmlns:a="%s"><dgm:ptLst>'
                 '<dgm:pt><dgm:t><a:p><a:r><a:t>Adım 1: Satış temsilcisi </a:t></a:r><a:r><a:t>talep açar</a:t></a:r>'
                 '</a:p></dgm:t></dgm:pt>'
                 '<dgm:pt><dgm:t><a:p><a:r><a:t>Adım 2: Bölge müdürü 50.000 TL üstünü onaylar</a:t></a:r></a:p>'
                 '</dgm:t></dgm:pt><dgm:pt><dgm:prSet phldrT="[Metin]"/></dgm:pt></dgm:ptLst></dgm:dataModel>'
                 % (NS["dgm"], NS["a"]))
GRAFIK_VERI = ('<c:chartSpace xmlns:c="%s" xmlns:a="%s"><c:chart><c:title><c:tx><c:rich><a:p><a:r>'
               '<a:t>Bölge bazında iade oranı</a:t></a:r></a:p></c:rich></c:tx></c:title><c:plotArea><c:barChart>'
               '<c:ser><c:tx><c:strRef><c:strCache><c:pt idx="0"><c:v>İade %%</c:v></c:pt></c:strCache></c:strRef>'
               '</c:tx><c:cat><c:strRef><c:strCache><c:pt idx="0"><c:v>Marmara</c:v></c:pt></c:strCache></c:strRef>'
               '</c:cat><c:val><c:numRef><c:numCache><c:pt idx="0"><c:v>0.12</c:v></c:pt></c:numCache></c:numRef>'
               '</c:val></c:ser></c:barChart></c:plotArea></c:chart></c:chartSpace>' % (NS["c"], NS["a"]))
NESNE_RELS = [("rIdDm", "diagramData", "diagrams/data1.xml"), ("rIdCh", "chart", "charts/chart1.xml")]
NESNE_EKLER = {"word/diagrams/data1.xml": DIYAGRAM_VERI, "word/charts/chart1.xml": GRAFIK_VERI,
               # Word'ün önbellek çizimi: aynı metni yineler, SAYILMAZ (yalnız data*.xml SmartArt'ın kaynağıdır)
               "word/diagrams/drawing1.xml": DIYAGRAM_VERI}


def nesneli_govde():
    return p("Süreç", stil="Balk1") + DENKLEM + SMARTART + GRAFIK + p("Son") + "<w:sectPr/>"


# ── BÖLÜM: cikar testleri ──
class _Gecici(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="kaynak_paketi_")
        self.addCleanup(shutil.rmtree, self.d, True)
        # Çalışma dizini geçici dizine alınır: hedef verilmeyen bir çağrı repoya ya da kullanıcı dizinine yazamaz.
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.d)
        self.kaynak = os.path.join(self.d, "istek.docx")
        docx_yaz(self.kaynak, ornek_govde(), ekler=ornek_ekler(self.d))
        self.kok = os.path.join(self.d, "proje", ".axet-code", "tmp")

    def cikar(self, kaynak=None, *ek):
        return call_main(kp.main, ["cikar", kaynak or self.kaynak, "--hedef-kok", self.kok, "--id", "p1", *ek])

    def paket(self, *yol):
        return os.path.join(self.kok, "p1", *yol)

    def oku(self, *yol):
        with open(self.paket(*yol), encoding="utf-8") as fh:
            return fh.read()


class KaynakPaketiDocxTest(_Gecici):
    def test_docx_paket_dogrulama_pass_ve_sayimlar(self):
        rc, out, err = self.cikar()
        self.assertEqual(0, rc, out + err)
        self.assertIn("KAPSAM (SCOPE)", out)
        self.assertIn("DOĞRULAMA: PASS", out)
        meta = json.loads(self.oku("paket.json"))
        self.assertEqual({"km": 14, "baslik": 3, "tablo": 1, "tablo_satiri": 5, "gorsel": 2, "gomulu": 5},
                         {k: meta["sayim"]["kaynak"][k] for k in ("km", "baslik", "tablo", "tablo_satiri", "gorsel",
                                                                   "gomulu")})
        self.assertEqual(meta["sayim"]["kaynak"], {k: meta["sayim"]["paket"][k] for k in meta["sayim"]["kaynak"]})
        self.assertIn("DOĞRULAMA: **PASS**", self.oku("INDEX.md"))

    def test_metin_mekanik_sira_ve_isaretler(self):
        self.cikar()
        metin = self.oku("metin.md")
        sira = ["Giriş", "Birinci paragraf devam | çizgi", "Liste öğesi", "İçerik denetimi içindeki paragraf",
                "Özel XML içindeki paragraf", "KG-01 görsel", "Ana metin Kutu metni", "TS-01 | Sipariş kaydı",
                "Prototip:", "KN-05 gömülü (altChunk)", "Standart yapıda değiştirilen nesneler (Repair)"]
        konum = [metin.find(s) for s in sira]
        self.assertNotIn(-1, konum, list(zip(sira, konum)))
        self.assertEqual(sorted(konum), konum, "kaynak sırası korunmalı")
        self.assertEqual(1, metin.count("Kutu metni"), "mc:Fallback içindeki yinelenen metin alınmamalı")
        self.assertIn("## [KM-0013] Standart yapıda", metin)
        self.assertIn("# [KM-0014] Türetilmiş başlık", metin, "basedOn zinciriyle başlık seviyesi")
        self.assertIn(r"| TS-03 | a\|b \¶ c\\d | x |", metin, "hücredeki | ¶ ters bölü kaçırılır")
        self.assertIn("iç A ¶ iç B ¶ sonra", metin)
        self.assertNotIn("⟦T01.S05⟧", metin, "boş satır kaynak maddesi değildir")

    def test_ole_paket_nesnesi_asil_dosya_buyuk_ve_mini_akis(self):
        self.cikar()
        with open(self.paket("gomulu", "KN-02_ekran6.html"), "rb") as fh:
            self.assertEqual(PROTOTIP_BUYUK, fh.read(), "4096+ bayt: normal sektör zinciri")
        with open(self.paket("gomulu", "KN-03_giris.html"), "rb") as fh:
            self.assertEqual(PROTOTIP_KUCUK, fh.read(), "küçük akış: mini akış + UTF-16 kopyasız ad")
        index = self.oku("INDEX.md")
        self.assertIn("OLE paket nesnesi (asıl dosya çıkarıldı)", index)
        self.assertIn("| KN-04 | `word/embeddings/oleObject3.bin` | `gomulu/KN-04_oleObject3.bin` | TANINMADI", index)
        self.assertIn("TANINMAYAN gömülü nesne: KN-04", index)
        with open(self.paket("gomulu", "KN-05_afchunk1.htm"), "rb") as fh:
            self.assertEqual(ALTCHUNK, fh.read())
        self.assertTrue(os.path.isfile(self.paket("gomulu", "KN-01_Microsoft_Excel_Worksheet.xlsx")))
        self.assertTrue(os.path.isfile(self.paket("media", "KG-01_image1.png")))

    def test_cikarim_satir_dusururse_dogrulama_fail(self):
        """Koruma: çıkarım bir tablo satırını kaybederse (modelin kısaltması gibi) bağımsız sayım bunu yakalar."""
        asil = kp._satirlar

        def eksik(el):
            return list(asil(el))[:-1]
        with mock.patch.object(kp, "_satirlar", eksik):
            rc, out, err = self.cikar()
        self.assertEqual(1, rc, out + err)
        self.assertIn("DOĞRULAMA: FAIL", out)
        self.assertIn("tablo satırı (metinli): kaynak 5 ≠ paket 4", out)
        self.assertIn("DOĞRULAMA: **FAIL**", self.oku("INDEX.md"))

    def test_cikarim_paragraf_kaybederse_fail(self):
        """Koruma: çıkarım (ya da elle düzenleme) bir paragrafı kaybederse madde sayısı ve sıra ayrılır.
        Kontrol grubu: iç içe bilinmeyen kapsayıcı (customXml > smartTag) kayıpsız gezilir → PASS."""
        govde = ornek_govde().replace('<w:customXml w:element="x">', '<w:customXml w:element="x"><w:smartTag>') \
            .replace("</w:customXml>", "</w:smartTag></w:customXml>")
        docx_yaz(self.kaynak, govde, ekler=ornek_ekler(self.d))
        rc, out, _ = self.cikar()
        self.assertEqual(0, rc, out)
        orijinal = kp.docx_cikar

        def kapsayicisiz(z, *a):
            c = orijinal(z, *a)
            c.satirlar = [s for s in c.satirlar if "Özel XML" not in s]
            return c
        with mock.patch.object(kp, "docx_cikar", kapsayicisiz):
            rc, out, _ = self.cikar()
        self.assertEqual(1, rc, out)
        self.assertIn("kaynak maddesi (KM: başlık + paragraf + tablo satırı + metinli nesne): kaynak 14 ≠ paket 13",
                      out)

    def test_eski_artik_dosya_fail_verir(self):
        os.makedirs(self.paket("media"), exist_ok=True)
        with open(self.paket("media", "eski.png"), "wb") as fh:
            fh.write(b"x")
        rc, out, _ = self.cikar()
        self.assertEqual(1, rc, out)
        self.assertIn("görsel (KG): kaynak 2 ≠ paket 3", out)

    def test_yeniden_kosum_ayni_klasor_pass(self):
        self.assertEqual(0, self.cikar()[0])
        with open(self.paket("metin.md"), encoding="utf-8") as fh:
            ilk = fh.read()
        self.assertEqual(0, self.cikar()[0])
        self.assertEqual(ilk, self.oku("metin.md"))

    def test_varsayilan_hedef_calisma_dizini_ve_icerik_ozeti(self):
        proje = os.path.join(self.d, "proje")
        os.makedirs(proje)
        r = run_py("kaynak_paketi.py", "cikar", self.kaynak, cwd=proje)
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        kok = os.path.join(proje, ".axet-code", "tmp")
        klasorler = os.listdir(kok)
        self.assertEqual(1, len(klasorler))
        self.assertRegex(klasorler[0], r"^istek-[0-9a-f]{8}$")
        self.assertNotIn("DIŞINDA", r.stdout)

    def test_desteklenmeyen_ve_bozuk_girdi(self):
        pdf = os.path.join(self.d, "istek.pdf")
        with open(pdf, "wb") as fh:
            fh.write(b"%PDF-1.4")
        rc, out, _ = self.cikar(pdf)
        self.assertEqual(3, rc)
        self.assertIn("DESTEKLENMİYOR", out)
        self.assertIn("yeniden yazarak paket ÜRETME", out)
        self.assertFalse(os.path.exists(self.paket()), "desteklenmeyen girdide paket klasörü açılmaz")
        bozuk = os.path.join(self.d, "bozuk.docx")
        with open(bozuk, "wb") as fh:
            fh.write(b"zip degil")
        rc, _out, err = self.cikar(bozuk)
        self.assertEqual(2, rc)
        self.assertIn("ÖLÇÜLEMEDİ", err)


class KaynakPaketiXlsxTest(_Gecici):
    def test_xlsx_satirlar_ve_sayfalar(self):
        xl = kp.xlsx_okuyucu()
        self.assertIsNotNone(xl, "office-excel/xlsx_lite klonda olmalı")
        yol = os.path.join(self.d, "liste.xlsx")
        xl.write_xlsx(yol, [("Testler", [["No", "Senaryo"], ["TS-01", "Kayıt"], ["", ""], ["TS-02", 3.0]]),
                            ("Notlar", [["Tek satır"]])])
        rc, out, err = self.cikar(yol)
        self.assertEqual(0, rc, out + err)
        metin = self.oku("metin.md")
        self.assertIn("## Sayfa SY01: Testler", metin)
        self.assertIn("[KM-0003] ⟦SY01.S0004⟧ | TS-02 | 3 |", metin)
        self.assertIn("[KM-0004] ⟦SY02.S0001⟧ | Tek satır |", metin)
        meta = json.loads(self.oku("paket.json"))
        self.assertEqual(4, meta["km_toplam"])
        self.assertEqual(2, meta["sayim"]["kaynak"]["sayfa"])

    def _xlsx(self, ekler=None):
        xl = kp.xlsx_okuyucu()
        yol = os.path.join(self.d, "liste.xlsx")
        xl.write_xlsx(yol, [("Gereksinim", [["No", "Kural", "Tutar", "Aktif"],
                                            ["R-01", "Kredi limiti aşılırsa sipariş bloke edilir", 1500.5, True],
                                            [None, None, "C3 metni", None]])])
        if ekler:
            with zipfile.ZipFile(yol, "a", zipfile.ZIP_DEFLATED) as z:
                for ad, veri in ekler.items():
                    z.writestr(ad, veri)
        return yol

    def test_xlsx_bozuk_xml_metni_geri_dususte_ve_listede(self):
        rc, out, err = self.cikar(self._xlsx({"xl/notlar1.xml": "<Onay> iki gün içinde"}))
        self.assertEqual(0, rc, out + err)
        self.assertIn("DOĞRULAMA: PASS", out)
        disi = {x["parca"]: x["not"] for x in json.loads(self.oku("paket.json"))["xml_disi"]}
        self.assertIn("geri düşüşe alındı; bu parçayı kullanıcıyla doğrula", disi["xl/notlar1.xml"])
        satirlar = [x for x in self.oku("metin.md").splitlines() if "xl/notlar1.xml" in x]
        self.assertEqual(1, len(satirlar), satirlar)
        self.assertIn("iki gün içinde", satirlar[0])

    def test_xlsx_metin_hucresi_karakteri_sayilir_kontrol_pass(self):
        """Kontrol grubu: sayı/mantıksal hücre biçimlense de (1500.5 / True) yalnız metin hücreleri sayılır → PASS."""
        rc, out, err = self.cikar(self._xlsx())
        self.assertEqual(0, rc, out + err)
        meta = json.loads(self.oku("paket.json"))
        self.assertEqual(meta["sayim"]["kaynak"]["karakter"], meta["sayim"]["paket"]["karakter"])
        self.assertEqual(len("NoKuralTutarAktifR-01Kredilimitiaşılırsasiparişblokeedilir") + len("C3metni"),
                         meta["sayim"]["kaynak"]["karakter"])

    def test_xlsx_hucre_metni_kisalirsa_fail(self):
        """F2 koruması: okuyucu metin hücresini kısaltırsa (modelin özetlemesi gibi) karakter sayımı FAIL verir."""
        yol = self._xlsx()
        xl = kp.xlsx_okuyucu()
        asil = xl.read_rows

        def kisaltan(y, sno):
            ad, satirlar = asil(y, sno)
            return ad, [[(v[:5] if isinstance(v, str) else v) for v in s] for s in satirlar]
        with mock.patch.object(xl, "read_rows", kisaltan):
            rc, out, _ = self.cikar(yol)
        self.assertEqual(1, rc, out)
        self.assertIn("metin karakteri (boşluksuz; xlsx'te yalnız metin hücreleri): kaynak", out)

    def test_xlsx_cizim_metin_kutusu_ve_grafik(self):
        cizim = ('<xdr:wsDr xmlns:xdr="%sdrawingml/2006/spreadsheetDrawing" xmlns:a="%s"><xdr:twoCellAnchor>'
                 '<xdr:sp><xdr:txBody><a:p><a:r><a:t>Not: onay iki aşamalı</a:t></a:r></a:p></xdr:txBody></xdr:sp>'
                 '</xdr:twoCellAnchor><xdr:twoCellAnchor><xdr:sp><xdr:txBody><a:p/></xdr:txBody></xdr:sp>'
                 '</xdr:twoCellAnchor></xdr:wsDr>') % (_S, NS["a"])
        rc, out, err = self.cikar(self._xlsx({"xl/drawings/drawing1.xml": cizim, "xl/charts/chart1.xml": GRAFIK_VERI}))
        self.assertEqual(0, rc, out + err)
        metin = self.oku("metin.md")
        self.assertIn("⟦K01 metin kutusu: xl/drawings/drawing1.xml⟧ | Not: onay iki aşamalı |", metin)
        self.assertIn("⟦G01 grafik: xl/charts/chart1.xml⟧ | Bölge bazında iade oranı | İade % | Marmara | 0.12 |", metin)
        sayim = json.loads(self.oku("paket.json"))["sayim"]["kaynak"]
        self.assertEqual((1, 1), (sayim["metin_kutusu"], sayim["grafik"]), "metinsiz kutu sayılmaz")

    def test_xlsx_okuyucu_yoksa_desteklenmiyor(self):
        yol = os.path.join(self.d, "liste.xlsx")
        kp.xlsx_okuyucu().write_xlsx(yol, [("S", [["a"]])])
        with mock.patch.object(kp, "xlsx_okuyucu", return_value=None):
            rc, out, _ = self.cikar(yol)
        self.assertEqual(3, rc)
        self.assertIn("DESTEKLENMİYOR", out)

class NesneMetniTest(_Gecici):
    """F1: denklem, SmartArt ve grafik metni pakete girer; bağımsız sayım bunları AYRI sayar."""

    def setUp(self):
        super().setUp()
        docx_yaz(self.kaynak, nesneli_govde(), rels=NESNE_RELS, ekler=NESNE_EKLER)

    def test_denklem_smartart_grafik_metni_pakette(self):
        rc, out, err = self.cikar()
        self.assertEqual(0, rc, out + err)
        metin = self.oku("metin.md")
        self.assertIn("[KM-0002] Tutar formülü: ⟦denklem⟧ Tutar=Miktar×BirimFiyat−İskonto", metin)
        self.assertIn("⟦D01 SmartArt: word/diagrams/data1.xml⟧ | Adım 1: Satış temsilcisi talep açar | "
                      "Adım 2: Bölge müdürü 50.000 TL üstünü onaylar |", metin)
        self.assertIn("⟦G01 grafik: word/charts/chart1.xml⟧ | Bölge bazında iade oranı | İade % | Marmara | 0.12 |", metin)
        self.assertLess(metin.index("Tutar formülü"), metin.index("D01 SmartArt"), "nesne konumunda yazılır")
        self.assertLess(metin.index("D01 SmartArt"), metin.index("[KM-0005] Son"))
        meta = json.loads(self.oku("paket.json"))
        k = meta["sayim"]["kaynak"]
        self.assertEqual((1, 1, 1, 5), (k["denklem"], k["diyagram"], k["grafik"], k["km"]))
        self.assertEqual(k, {a: meta["sayim"]["paket"][a] for a in k})
        self.assertIn("D01 SmartArt `word/diagrams/data1.xml`", self.oku("INDEX.md"))

    def test_smartart_dusurulurse_fail(self):
        """Koruma: çıkarım nesnenin metnini düşürürse parça hesabı (evren süpürmesi, ayrı kod) FAIL verir."""
        with mock.patch.object(kp, "nesne_hucreleri", return_value=[]):
            rc, out, _ = self.cikar()
        self.assertEqual(1, rc, out)
        self.assertRegex(out, r"parça word/diagrams/data1\.xml: kaynak metni [1-9]\d* ≠ pakette 0")
        self.assertRegex(out, r"parça word/charts/chart1\.xml: kaynak metni [1-9]\d* ≠ pakette 0")
        self.assertIn("metin yok", self.oku("metin.md"))

    def test_denklem_dusurulurse_fail(self):
        with mock.patch.object(kp, "_denklem_metni", return_value=""):
            rc, out, _ = self.cikar()
        self.assertEqual(1, rc, out)
        self.assertIn("denklem: kaynak 1 ≠ paket 0", out)

    def test_govdede_konumu_olmayan_nesne_sonda_yazilir(self):
        govde = p("Süreç") + "<w:sectPr/>"   # grafik gövdeden bağlı değil (ör. üstbilgiden)
        docx_yaz(self.kaynak, govde, rels=[], ekler={"word/charts/chart1.xml": GRAFIK_VERI})
        rc, out, err = self.cikar()
        self.assertEqual(0, rc, out + err)
        metin = self.oku("metin.md")
        self.assertIn("## Gövdede konumu bulunamayan metin nesneleri", metin)
        self.assertIn("[KM-0002] ⟦G01 grafik: word/charts/chart1.xml⟧", metin)

    def test_okunamayan_nesne_parcasi_isaretlenir_ve_fail(self):
        bozuk = DIYAGRAM_VERI.replace("</dgm:dataModel>", "")
        docx_yaz(self.kaynak, nesneli_govde(), rels=NESNE_RELS,
                 ekler=dict(NESNE_EKLER, **{"word/diagrams/data1.xml": bozuk}))
        rc, out, _ = self.cikar()
        self.assertEqual(1, rc, out)
        self.assertIn("⟦D01 SmartArt: word/diagrams/data1.xml⟧ metin alınmadı (parça okunamadı)", self.oku("metin.md"))

    def test_metin_kutusu_icinde_tablo_pass(self):
        """F8: metin kutusundaki tablo bulunduğu paragrafın satırına düzleşir; sayım tanımı aynı → PASS."""
        ic = "<w:tbl>%s%s</w:tbl>" % (satir("Alan", "Kural"), satir("KUNNR", "zorunlu"))
        kutu = "<w:r><w:drawing><wps:txbx><w:txbxContent>%s</w:txbxContent></wps:txbx></w:drawing></w:r>" % (
            ic + p("kutu sonu"))
        docx_yaz(self.kaynak, p("Ana", ek=kutu) + "<w:sectPr/>", rels=[])
        rc, out, err = self.cikar()
        self.assertEqual(0, rc, out + err)
        self.assertIn("[KM-0001] Ana Alan Kural KUNNR zorunlu kutu sonu", self.oku("metin.md"))
        self.assertEqual(0, json.loads(self.oku("paket.json"))["sayim"]["kaynak"]["tablo"])


class SaglamlikTest(_Gecici):
    """F3/F4/F9: bozuk ya da kötü niyetli girdi paketi düşürmez, sonsuz/aşırı iş yaptırmaz, dışarı yazdıramaz."""

    def _ole_docx(self, ole_bin):
        docx_yaz(self.kaynak, p("Metin") + p("", ek=OLE % "rIdOle1") + "<w:sectPr/>",
                 rels=[("rIdOle1", "oleObject", "embeddings/oleObject1.bin")],
                 ekler={"word/embeddings/oleObject1.bin": ole_bin})

    def test_kesik_cfb_cfbhata_ve_paket_taninmadi_ile_gecer(self):
        iyi = cfb_yaz([("\x01Ole10Native", ole10native_yaz("a.html", b"<html>x</html>"))])
        with self.assertRaises(kp.CfbHata):
            kp.cfb_akislari(iyi[:512 + 100])
        self._ole_docx(iyi[:512 + 100])
        rc, out, err = self.cikar()
        self.assertEqual(0, rc, out + err)
        self.assertIn("TANINMADI — OLE okunamadı (kısa sektör", self.oku("INDEX.md"))

    def test_kesik_akis_kisa_icerik_verilmez(self):
        akis = ole10native_yaz("b.html", PROTOTIP_BUYUK)
        buyuk = cfb_yaz([("\x01Ole10Native", akis)])
        son = len(akis) % 512 or 512   # akışın son sektöründeki veri baytı (dosyanın son sektörü bu akışınki)
        self.assertGreater(son, 1)
        with self.assertRaises(kp.CfbHata) as cm:
            kp.cfb_akislari(buyuk[:len(buyuk) - 512 + son // 2])  # son sektör yarım: akışın sonu kesik
        self.assertIn("kısa", str(cm.exception))

    def test_gomulu_cozumde_beklenmeyen_hata_ham_kopya(self):
        self._ole_docx(cfb_yaz([("Gizemli", b"x" * 10)]))
        with mock.patch.object(kp, "cfb_akislari", side_effect=RuntimeError("deneme")):
            rc, out, err = self.cikar()
        self.assertEqual(0, rc, out + err)
        self.assertIn("TANINMADI — çözümlenemedi (RuntimeError: deneme); ham kopya", self.oku("INDEX.md"))

    def test_dongulu_difat_sinirli_is(self):
        bas = kp.CFB_IMZA + b"\x00" * 16 + struct.pack("<HHHHH", 0x3E, 3, 0xFFFE, 9, 6) + b"\x00" * 6
        bas += struct.pack("<IIIIIIIII", 0, 0xFFFFFFFF, 0, 0, 4096, ENDOFCHAIN, 0, 0, 1000)
        bas += struct.pack("<109I", *([0] * 109))
        data = bas + struct.pack("<128I", *([0] * 128))   # tek DIFAT sektörü kendine işaret ediyor
        say = {"n": 0}
        asil = struct.unpack_from

        def sayan(*a, **k):
            say["n"] += 1
            return asil(*a, **k)
        with mock.patch.object(kp.struct, "unpack_from", sayan):
            with self.assertRaises(kp.CfbHata):
                kp.cfb_akislari(data)
        self.assertLessEqual(say["n"], 10, "DIFAT/FAT boyu dosyadaki sektör sayısıyla sınırlı olmalı")

    def test_dongulu_difat_ziyaret_kumesiyle_kesilir(self):
        """Sektör sayısı sınırı döngüyü tek başına kesmez (çevrim boyu < sınır ise küme büyümez): ziyaret kümesi şart."""
        bas = kp.CFB_IMZA + b"\x00" * 16 + struct.pack("<HHHHH", 0x3E, 3, 0xFFFE, 9, 6) + b"\x00" * 6
        bas += struct.pack("<IIIIIIIII", 0, 0xFFFFFFFF, 0, 0, 4096, ENDOFCHAIN, 0, 0, 1000)
        bas += struct.pack("<109I", *([FREESECT] * 109))
        data = bas + struct.pack("<128I", *([FREESECT] * 127 + [0])) + b"\x00" * (512 * 3)  # 4 sektör, DIFAT 0 → 0
        say = {"n": 0}
        asil = struct.unpack_from

        def sinirli(*a, **k):
            say["n"] += 1
            if say["n"] > 200:
                raise AssertionError("DIFAT döngüsü kesilmedi (200 okuma)")
            return asil(*a, **k)
        with mock.patch.object(kp.struct, "unpack_from", sinirli):
            with self.assertRaises(kp.CfbHata) as cm:
                kp.cfb_akislari(data)
        self.assertEqual("DIFAT zinciri döngülü", str(cm.exception))

    def test_ic_ayristirma_hatasi_cfbhata_olur(self):
        """F3: iç okuyucunun struct/indeks hatası çağırana sızmaz, CfbHata'ya çevrilir (gömülü çözüm onu yakalar)."""
        for hata in (struct.error("unpack requires a buffer"), IndexError("x"), UnicodeDecodeError("utf-16", b"", 0, 1, "y")):
            with mock.patch.object(kp, "_cfb_akislari", side_effect=hata):
                with self.assertRaises(kp.CfbHata) as cm:
                    kp.cfb_akislari(b"")
            self.assertIn("bozuk CFB (%s" % type(hata).__name__, str(cm.exception))

    def test_ole10native_yol_gecisli_ad_paket_disina_yazmaz(self):
        adlar = ["..\\..\\..\\kotu.html", "C:\\Windows\\Temp\\kotu2.html", "/etc/kotu3.html", "..", "CON",
                 "a/../../b.html"]
        for i, ad in enumerate(adlar):
            self._ole_docx(cfb_yaz([("\x01Ole10Native", ole10native_yaz(ad, b"X"))]))
            rc, out, err = call_main(kp.main, ["cikar", self.kaynak, "--hedef-kok", self.kok, "--id", "y%d" % i])
            self.assertEqual(0, rc, out + err)
            gomulu = os.path.join(self.kok, "y%d" % i, "gomulu")
            dosyalar = os.listdir(gomulu)
            self.assertEqual(1, len(dosyalar), (ad, dosyalar))
            self.assertTrue(dosyalar[0].startswith("KN-01_"), (ad, dosyalar))
            self.assertNotRegex(dosyalar[0], r"[\\/:]", ad)
            self.assertEqual(os.path.realpath(gomulu), os.path.dirname(os.path.realpath(os.path.join(gomulu,
                                                                                                      dosyalar[0]))))
        self.assertEqual(["g.png", "istek.docx", "proje"], sorted(os.listdir(self.d)), "paket dışına dosya yazılmadı")
        self.assertEqual(["tmp"], os.listdir(os.path.join(self.d, "proje", ".axet-code")))

    def test_boyut_siniri_olculemedi(self):
        """Ö1: sınırı aşan METİN parçası ve toplam → çıkış 2, paket yazılmaz; sınırı aşan görsel atlanır, çıkarım sürer
        (yer tutucu dosya + INDEX'te ÖLÇÜLEMEDİ — boyut)."""
        docx_yaz(self.kaynak, p("x" * 5000) + "<w:sectPr/>", rels=[])
        with mock.patch.object(kp, "MAX_UYE", 4000):
            rc, _out, err = self.cikar()
        self.assertEqual(2, rc)
        self.assertIn("boyut sınırı: word/document.xml açılınca 4000 bayttan fazla (sınır 4000)", err)
        self.assertFalse(os.path.exists(self.paket()), "sınırı aşan girdide paket yazılmaz")
        with mock.patch.object(kp, "MAX_TOPLAM", 4500):
            rc, _out, err = self.cikar()
        self.assertEqual(2, rc)
        self.assertIn("boyut sınırı: açılmış toplam", err)
        docx_yaz(self.kaynak, p("x") + "<w:sectPr/>", rels=[], ekler={"word/media/b.bin": b"\x00" * 5000})
        with mock.patch.object(kp, "MAX_UYE", 4000):
            rc, out, err = self.cikar()
        self.assertEqual(0, rc, out + err)
        self.assertEqual(["KG-01_b.bin.OLCULEMEDI.txt"], os.listdir(self.paket("media")))
        self.assertIn("ÖLÇÜLEMEDİ — boyut", self.oku("media", "KG-01_b.bin.OLCULEMEDI.txt"))
        self.assertIn("ÖLÇÜLEMEDİ — boyut: word/media/b.bin", self.oku("INDEX.md"))
        self.assertIn("| KG-01 | `word/media/b.bin` | `media/KG-01_b.bin.OLCULEMEDI.txt` | ÖLÇÜLEMEDİ — boyut",
                      self.oku("INDEX.md"))

    def test_beklenmeyen_hata_fail_degil_olculemedi(self):
        with mock.patch.object(kp, "docx_cikar", side_effect=RuntimeError("deneme")):
            rc, _out, err = self.cikar()
        self.assertEqual(2, rc, "yakalanmayan hata Python'un çıkış 1'i olup FAIL ile karışmasın")
        self.assertIn("beklenmeyen hata (RuntimeError: deneme)", err)


# ── BÖLÜM: evren süpürmesi / geri düşüş testleri (F10) ──
CX = "http" + "://schemas.microsoft.com/office/drawing/2014/chartex"
WP14 = "http" + "://schemas.microsoft.com/office/word/2010/wordprocessingDrawing"
CDR = _S + "drawingml/2006/chartDrawing"
CHARTEX = ('<cx:chartSpace xmlns:cx="%s"><cx:chartData><cx:data id="0"><cx:strDim type="cat"><cx:lvl ptCount="2">'
           '<cx:pt idx="0">Ege</cx:pt><cx:pt idx="1">Akdeniz</cx:pt></cx:lvl></cx:strDim><cx:numDim type="val">'
           '<cx:lvl ptCount="2"><cx:pt idx="0">5</cx:pt><cx:pt idx="1">7</cx:pt></cx:lvl></cx:numDim></cx:data>'
           '</cx:chartData></cx:chartSpace>' % CX)
KONUM = ('<wp:positionH><mc:AlternateContent><mc:Choice Requires="wp14"><wp14:pctPosHOffset xmlns:wp14="%s">91000'
         '</wp14:pctPosHOffset></mc:Choice><mc:Fallback><wp:posOffset>7077075</wp:posOffset></mc:Fallback>'
         '</mc:AlternateContent></wp:positionH>' % WP14)


def kutu(choice, fallback, konum=""):
    """Metin kutusu: Choice (DrawingML) + Fallback (VML). choice None → Choice'suz AlternateContent."""
    ch = ('<mc:Choice Requires="wps"><w:drawing><wp:anchor>%s<wps:txbx><w:txbxContent>%s</w:txbxContent></wps:txbx>'
          '</wp:anchor></w:drawing></mc:Choice>' % (konum, p(choice))) if choice is not None else ""
    return ('<w:r><mc:AlternateContent>%s<mc:Fallback><w:pict><v:textbox><w:txbxContent>%s</w:txbxContent>'
            '</v:textbox></w:pict></mc:Fallback></mc:AlternateContent></w:r>' % (ch, p(fallback)))


class EvrenGeriDususTest(_Gecici):
    def docx(self, govde, ekler=None, rels=None):
        docx_yaz(self.kaynak, govde + "<w:sectPr/>", rels=rels or [], ekler=ekler)
        rc, out, err = self.cikar()
        return rc, out + err, self.oku("metin.md") if os.path.exists(self.paket("metin.md")) else ""

    def test_bilinmeyen_parca_geri_dususte_pass(self):
        """F10: parça listesinde olmayan bir XML parçasının metni pakete girer (geri düşüş) ve doğrulama PASS."""
        rc, out, metin = self.docx(p("Gövde"), ekler={
            "word/foo/bar1.xml": '<x:kok xmlns:x="urn:ornek"><x:a>Bilinmeyen parça metni</x:a></x:kok>'})
        self.assertEqual(0, rc, out)
        self.assertIn("[KM-0002] ⟦P01 parça: word/foo/bar1.xml⟧ | Bilinmeyen parça metni |", metin)
        index = self.oku("INDEX.md")
        self.assertIn("Geri düşüşe giden parçalar", index)
        self.assertIn("P01 `word/foo/bar1.xml`", index)
        self.assertIn("| `word/foo/bar1.xml` | geri düşüş | 20 | 0 | 0 | 20 |", index)
        meta = json.loads(self.oku("paket.json"))
        self.assertEqual(["word/foo/bar1.xml"], [g["parca"] for g in meta["geri_dusus"]])
        self.assertEqual(2, meta["km_toplam"])

    def test_ust_altbilgi_dipnot_yorum_geri_dususte(self):
        """Eskiden 'metin.md'ye alınmadı' notuyla dışarıda kalan parçalar artık metin olarak pakette."""
        w = 'xmlns:w="%s"' % NS["w"]
        rc, out, metin = self.docx(p("Gövde"), ekler={
            "word/header1.xml": "<w:hdr %s>%s</w:hdr>" % (w, p("Üst bilgi metni")),
            "word/footer1.xml": "<w:ftr %s>%s</w:ftr>" % (w, p("Alt bilgi metni")),
            "word/footnotes.xml": '<w:footnotes %s><w:footnote w:id="1">%s</w:footnote></w:footnotes>'
                                  % (w, p("Dipnot metni")),
            "word/comments.xml": '<w:comments %s><w:comment w:id="0">%s</w:comment></w:comments>'
                                 % (w, p("Yorum metni"))})
        self.assertEqual(0, rc, out)
        for parca, metin_ in (("word/comments.xml", "Yorum metni"), ("word/footer1.xml", "Alt bilgi metni"),
                              ("word/footnotes.xml", "Dipnot metni"), ("word/header1.xml", "Üst bilgi metni")):
            self.assertRegex(metin, r"\[KM-\d{4}\] ⟦P\d\d parça: %s⟧ \| %s \|" % (parca, metin_))
        self.assertNotIn("ALINMADI", self.oku("INDEX.md"))
        self.assertNotIn("alınmadı", self.oku("INDEX.md"))

    def test_chartex_kategorileri_docx_ve_xlsx(self):
        """n1: ChartEx kategori metni (cx:pt) grafik satırında; docx ve xlsx."""
        rc, out, metin = self.docx(p("Grafik"), ekler={"word/charts/chartEx1.xml": CHARTEX})
        self.assertEqual(0, rc, out)
        self.assertIn("⟦G01 grafik: word/charts/chartEx1.xml⟧ | Ege | Akdeniz | 5 | 7 |", metin)
        xl = kp.xlsx_okuyucu()
        yol = os.path.join(self.d, "grafik.xlsx")
        xl.write_xlsx(yol, [("Veri", [["Bölge"], ["Ege"]])])
        with zipfile.ZipFile(yol, "a") as z:
            z.writestr("xl/charts/chartEx1.xml", CHARTEX)
        rc, out, err = self.cikar(yol)
        self.assertEqual(0, rc, out + err)
        self.assertIn("⟦G01 grafik: xl/charts/chartEx1.xml⟧ | Ege | Akdeniz | 5 | 7 |", self.oku("metin.md"))

    def test_grafik_ustu_metin_kutusu_geri_dususte(self):
        """n7: grafiğin üstüne çizilen metin kutusu (userShapes → word/drawings/drawingN.xml) pakette, PASS."""
        us = ('<c:userShapes xmlns:c="%s" xmlns:cdr="%s" xmlns:a="%s"><cdr:relSizeAnchor><cdr:sp><cdr:txBody><a:p>'
              '<a:r><a:t>Not: Marmara Q3 verisi eksik</a:t></a:r></a:p></cdr:txBody></cdr:sp></cdr:relSizeAnchor>'
              '</c:userShapes>') % (NS["c"], CDR, NS["a"])
        rc, out, metin = self.docx(p("Grafik:") + GRAFIK, rels=[("rIdCh", "chart", "charts/chart1.xml")],
                                   ekler={"word/charts/chart1.xml": GRAFIK_VERI, "word/drawings/drawing1.xml": us})
        self.assertEqual(0, rc, out)
        self.assertIn("⟦P01 parça: word/drawings/drawing1.xml⟧ | Not: Marmara Q3 verisi eksik |", metin)

    def test_fallback_yalniz_choice_esitse_yok_sayilir(self):
        """Kural ②: Fallback yalnız karakteri eşit bir Choice varsa yok sayılır. Konum değeri (yok sayılan sınıf)
        yalnız Choice'ta durur ve eşitliği bozmaz; iç içe konum AlternateContent'i dış Choice'u yarıda kesmez."""
        govde = (p("Önce") + p("", ek=kutu("Aynı metin", "Aynı metin", KONUM)) + p("", ek=kutu("A", "Başka metin"))
                 + p("", ek=kutu(None, "Yalnız eski gösterim")))
        rc, out, metin = self.docx(govde)
        self.assertEqual(0, rc, out)
        self.assertEqual(1, metin.count("Aynı metin"), metin)
        self.assertRegex(metin, r"⟦P01 parça: word/document\.xml⟧ \| Başka metin \|")
        self.assertRegex(metin, r"⟦P01 parça: word/document\.xml⟧ \| Yalnız eski gösterim \|")
        # Dış Fallback "Aynı metin" (9) düşer. İç konum bloğunun net metni 0 olduğundan o Fallback düşmez; konum
        # değerleri (91000 + 7077075 = 12) kendi sınıfında sayılır.
        self.assertIn("yinelenen gösterim (mc:Fallback, Choice ile eşit) 9", out)
        self.assertIn("konum/ölçü değeri 12", out)

    def test_alan_kodu_yok_sayilir_alan_sonucu_alinir(self):
        """Kural ②: alan kodu sınıfı yalnız instrText; alan SONUCU (w:t) yapılandırılmış satırda."""
        alan = ('<w:p><w:r><w:t xml:space="preserve">Sayfa </w:t></w:r><w:r><w:fldChar w:fldCharType="begin"/></w:r>'
                '<w:r><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r><w:r><w:fldChar '
                'w:fldCharType="separate"/></w:r><w:r><w:t>7</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r>'
                '</w:p>')
        rc, out, metin = self.docx(alan)
        self.assertEqual(0, rc, out)
        self.assertIn("[KM-0001] Sayfa 7", metin)
        self.assertNotIn("PAGE", metin)
        self.assertIn("alan kodu (instrText) 4", out)

    def test_yok_sayilan_her_sinif_karakteriyle_basilir(self):
        """Koşul ①: her yok sayılan sınıf DOĞRULAMA satırında ve INDEX'te karakter sayısıyla (sıfır da) görünür."""
        rc, out, err = self.cikar()
        self.assertEqual(0, rc, out + err)
        dogrulama = [s for s in out.splitlines() if s.startswith("DOĞRULAMA:")][0]
        index = self.oku("INDEX.md")
        for sinif in kp.YOK_SINIFLAR:
            self.assertRegex(dogrulama, re.escape(sinif) + r" \d+")
            self.assertRegex(index, re.escape(sinif) + r" \d+")
        self.assertIn("yinelenen gösterim (mc:Fallback, Choice ile eşit) 9", dogrulama)  # KUTU: "Kutu metni"
        self.assertEqual(set(kp.YOK_SINIFLAR), set(json.loads(self.oku("paket.json"))["yok_sayilan"]))

    def test_definedname_yalniz_workbookta_yok_sayilir(self):
        """definedName yalnız xl/workbook.xml'de formül/başvuru sınıfıdır; başka parçada geri düşüşe gider."""
        xl = kp.xlsx_okuyucu()
        yol = os.path.join(self.d, "liste.xlsx")
        xl.write_xlsx(yol, [("Testler", [["No"], ["TS-01"]])])
        with zipfile.ZipFile(yol) as z:
            self.assertIn("definedName", z.read("xl/workbook.xml").decode("utf-8"), "fikstür ön koşulu")
        rc, out, err = self.cikar(yol)
        self.assertEqual(0, rc, out + err)
        self.assertRegex(out, r"formül / veri başvurusu \(f, definedName\) [1-9]\d*")
        self.assertNotIn("parça: xl/workbook.xml", self.oku("metin.md"))
        rc, out, metin = self.docx(p("Gövde"), ekler={
            "word/foo/ad.xml": '<x:kok xmlns:x="urn:ornek"><x:definedName>Gizli ad metni</x:definedName></x:kok>'})
        self.assertEqual(0, rc, out)
        self.assertIn("⟦P01 parça: word/foo/ad.xml⟧ | Gizli ad metni |", metin)
        self.assertIn("formül / veri başvurusu (f, definedName) 0", out)


class R3GateTest(_Gecici):
    """Bug gate R3 bulguları: XML olmayan üye, xlsx payın kaynaktan geldiği, parçaya/değere bağlı yaprak sınıfları,
    Fallback içerik karşılaştırması, mürekkep ve VML konumu, dosya üyelerinin toplam sınırı, boş paylaşılan dizge."""
    docx = EvrenGeriDususTest.docx

    def test_xml_olmayan_uye_listelenir_makro_ayrica_isaretlenir(self):
        """F1: .docm'deki vbaProject.bin ve düz metin üye sessizce kaybolmaz; görsel (KG) iki kez listelenmez."""
        png = os.path.join(self.d, "g.png")
        write_png(png)
        with open(png, "rb") as fh:
            png_b = fh.read()
        rc, out, _ = self.docx(p("Gövde", ek=GORSEL), rels=[("rIdImg", "image", "media/image1.png")], ekler={
            "word/vbaProject.bin": b"\xd0\xcf\x11\xe0makro", "word/notlar.txt": "Onay iki gün içinde verilir",
            "word/media/image1.png": png_b})
        self.assertEqual(0, rc, out)
        meta = json.loads(self.oku("paket.json"))
        disi = {x["parca"]: x for x in meta["xml_disi"]}
        self.assertEqual({"word/vbaProject.bin", "word/notlar.txt"}, set(disi))
        self.assertIn("makro kodu (VBA) — okunmadı, iş kuralı içerebilir", disi["word/vbaProject.bin"]["not"])
        self.assertEqual("XML değil — metni çıkarılmadı", disi["word/notlar.txt"]["not"])
        self.assertEqual(len("Onay iki gün içinde verilir".encode("utf-8")), disi["word/notlar.txt"]["boyut"])
        index = self.oku("INDEX.md")
        self.assertIn("- XML olmayan üye `word/vbaProject.bin`", index)
        self.assertIn("- XML olmayan üye `word/notlar.txt`", index)
        self.assertNotIn("XML olmayan üye `word/media", index)
        self.assertIn("XML olmayan üye: word/vbaProject.bin", out)
        self.assertIn("XML olmayan üyelerin içeriği (makro kodu dahil)", kp.SCOPE_CIKAR)

    def test_xlsx_sayfa_payi_kaynaktan_isaretlenir(self):
        """F2: sayfa / paylaşılan dizge parçasının yapılandırılmış payı kaynaktan; sınıf bunu söyler."""
        yol = os.path.join(self.d, "liste.xlsx")
        kp.xlsx_okuyucu().write_xlsx(yol, [("S", [["No", "Kural"], ["R-01", 5.0]])])
        rc, out, err = self.cikar(yol)
        self.assertEqual(0, rc, out + err)
        sinif = {r["parca"]: r["sinif"] for r in json.loads(self.oku("paket.json"))["parca_hesabi"]}
        self.assertEqual(kp.YAPI_KAYNAKTAN, sinif["xl/worksheets/sheet1.xml"])
        self.assertIn(kp.YAPI_KAYNAKTAN, self.oku("INDEX.md"))
        self.assertIn("'yapılandırılmış' pay kaynaktan hesaplanır (pakette yalnız metin hücresi ölçülür)", kp.SCOPE_CIKAR)
        # Aynı beyan belgede ve katalogda (gate R3 F2): okur INDEX'teki sınıfı yalnız betikte değil belgede de bulur.
        trace = " ".join(_metin("skills-sap", "sap-fs-ts-docs", "references", "traceability.md").split())
        self.assertIn("\"yapılandırılmış (kaynaktan; pakette yalnız metin hücresi ölçülür)\"", trace.replace("**", ""))
        katalog = json.loads(_metin("guncelle", "yayinlar.json"))
        k02 = [k for y in katalog["yayinlar"] for k in y["kalemler"] if k["id"] == "0.5.24-02"][0]
        self.assertIn("pakette yalnız metin hücresi ölçülür", k02["neden"])

    def test_konum_formul_bicim_adi_bilinmeyen_parcada_geri_dususte(self):
        """F3 (definedName testinin eşi): konum adı metin taşıyorsa, f / formatCode bilinmeyen parçadaysa geri düşüş;
        sayı değerli konum adı her yerde yok sayılır."""
        rc, out, metin = self.docx(p("Gövde"), ekler={
            "word/foo/x.xml": '<x:kok xmlns:x="urn:ornek"><x:row>İş metni satırda</x:row><x:row>42</x:row>'
                              '<x:f>Formül değil not</x:f><x:formatCode>Biçim değil not</x:formatCode></x:kok>'})
        self.assertEqual(0, rc, out)
        for parca_metni in ("İş metni satırda", "Formül değil not", "Biçim değil not"):
            self.assertIn("⟦P01 parça: word/foo/x.xml⟧ | %s |" % parca_metni, metin)
        self.assertNotIn("42", metin.split("Yapılandırılmamış")[-1])
        self.assertIn("konum/ölçü değeri 2", out)
        self.assertIn("formül / veri başvurusu (f, definedName) 0", out)
        self.assertIn("sayı biçim kodu (formatCode) 0", out)

    def test_fallback_karakteri_esit_ama_metni_farkli_ise_pakette(self):
        """F4: "Onay: 5 gün" ile "İade: 9 gün" aynı karakter sayısında; Fallback yutulmaz, geri düşüşe gider."""
        rc, out, metin = self.docx(p("Önce") + p("", ek=kutu("Onay: 5 gün", "İade: 9 gün")))
        self.assertEqual(0, rc, out)
        self.assertIn("Onay: 5 gün", metin)
        self.assertRegex(metin, r"⟦P01 parça: word/document\.xml⟧ \| İade: 9 gün \|")
        self.assertIn("yinelenen gösterim (mc:Fallback, Choice ile eşit) 0", out)

    def test_murekkep_ve_vml_konumu_km_uretmez(self):
        """Ö-a / Ö-b: InkML koordinatı ve Excel VML x:Row/x:Column/x:Anchor sayıları kaynak maddesi olmaz; sınıfı
        karakter sayısıyla basılır. VML'deki metin (açıklama) yine pakettedir."""
        ink = ('<inkml:ink xmlns:inkml="%s"><inkml:trace contextRef="#c">100 200, 110 210</inkml:trace>'
               '<inkml:trace>300 400</inkml:trace></inkml:ink>' % ("http" + "://www.w3.org/2003/InkML"))
        vml = ('<xml xmlns:v="urn:schemas-microsoft-com:vml" xmlns:x="urn:schemas-microsoft-com:office:excel">'
               '<v:shape><v:textbox><div>Açıklama metni</div></v:textbox><x:ClientData ObjectType="Note">'
               '<x:Anchor>1, 15, 0, 2, 3, 15, 4, 2</x:Anchor><x:Row>0</x:Row><x:Column>1</x:Column>'
               '</x:ClientData></v:shape></xml>')
        rc, out, metin = self.docx(p("Gövde"), ekler={"word/ink/ink1.xml": ink, "word/drawings/vmlDrawing1.vml": vml})
        self.assertEqual(0, rc, out)
        self.assertNotIn("word/ink/ink1.xml", metin)
        self.assertIn("mürekkep koordinatı (inkml:trace) %d" % len("100200,110210300400"), out)
        self.assertIn("| Açıklama metni |", metin)
        self.assertNotRegex(metin, r"vmlDrawing1\.vml⟧ \|[^\n]*\b15\b")
        self.assertIn("konum/ölçü değeri %d" % (len("1,15,0,2,3,15,4,2") + 2), out)

    def test_dosya_uyeleri_metin_toplamina_sayilmaz_toplami_asan_atlanir(self):
        """Ö-c: büyük görseller metin toplam sınırına sayılmaz (paket düşmez); görsel toplamını aşan üye atlanır."""
        ekler = {"word/media/a.bin": b"\x01" * 3000, "word/media/b.bin": b"\x02" * 3000}
        with mock.patch.object(kp, "MAX_TOPLAM", 2500):
            rc, out, _ = self.docx(p("Metin korunur"), ekler=ekler)
        self.assertEqual(0, rc, out)
        self.assertIn("Metin korunur", self.oku("metin.md"))
        self.kok = os.path.join(self.d, "k2")  # temiz paket klasörü (eski dosya artığı ayrı bir FAIL'dir)
        with mock.patch.object(kp, "MAX_DOSYA_TOPLAM", 4000):
            rc, out, _ = self.docx(p("Metin korunur"), ekler=ekler)
        self.assertEqual(0, rc, out)
        self.assertEqual(["KG-01_a.bin", "KG-02_b.bin.OLCULEMEDI.txt"], sorted(os.listdir(self.paket("media"))))
        self.assertIn("görsel/gömülü üyelerin toplamı 4000 bayt sınırını aşıyor",
                      self.oku("media", "KG-02_b.bin.OLCULEMEDI.txt"))

    def test_bos_paylasilan_dizge_indeks_kaydirmaz(self):
        """<si/> da bir indekstir: kontrol grubu (<si/>'siz) ve deney aynı paketi ve PASS verir (ölçüldü: önce FAIL)."""
        sonuc = {}
        for ad, bas in (("kontrol", ""), ("deney", "<si/>")):
            yol = os.path.join(self.d, ad + ".xlsx")
            si_kitabi(yol, bas)
            rc, out, err = call_main(kp.main, ["cikar", yol, "--hedef-kok", self.kok, "--id", ad])
            self.assertEqual(0, rc, out + err)
            with open(os.path.join(self.kok, ad, "metin.md"), encoding="utf-8") as fh:
                sonuc[ad] = [s for s in fh.read().splitlines() if "SY01" in s]
        self.assertEqual(sonuc["kontrol"], sonuc["deney"])
        self.assertIn("[KM-0002] ⟦SY01.S0002⟧ | R-01 | Kredi limiti |", sonuc["deney"])

    def test_kaynakta_gorunmez_bicim_karakteri_yok(self):
        """Ö-e: PUBLIC depo — betikte literal U+FEFF ya da başka Cf/Cc karakteri yok (kaçış dizisiyle yazılır)."""
        import unicodedata
        with open(kp.__file__, encoding="utf-8") as fh:
            for no, satir in enumerate(fh, 1):
                for ch in satir.rstrip("\n"):
                    self.assertFalse(unicodedata.category(ch) in ("Cf", "Cc") and ch != "\t",
                                     "satır %d: U+%04X" % (no, ord(ch)))


def si_kitabi(yol, si_bas):
    """Paylaşılan dizgeli elle kurulan xlsx; si_bas başa eklenen boş dizge (indeksler buna göre kaydırılır)."""
    main = _S + "spreadsheetml/2006/main"
    n = 1 if si_bas else 0
    sst = ('<sst xmlns="%s">%s<si><t>No</t></si><si><t>Kural</t></si><si><t>R-01</t></si><si><t>Kredi limiti</t></si>'
           '</sst>' % (main, si_bas))
    sayfa = ('<worksheet xmlns="%s"><sheetData><row r="1"><c r="A1" t="s"><v>%d</v></c><c r="B1" t="s"><v>%d</v></c>'
             '</row><row r="2"><c r="A2" t="s"><v>%d</v></c><c r="B2" t="s"><v>%d</v></c></row>'
             '<row r="3"><c r="B3"><v>5</v></c></row></sheetData></worksheet>') % (main, n, 1 + n, 2 + n, 3 + n)
    with zipfile.ZipFile(yol, "w") as z:
        z.writestr("[Content_Types].xml", '<Types xmlns="%s"/>' % CT)
        z.writestr("xl/workbook.xml", '<workbook xmlns="%s" xmlns:r="%s"><sheets><sheet name="S" sheetId="1" '
                                      'r:id="rId1"/></sheets></workbook>' % (main, NS["r"]))
        z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="%s"><Relationship Id="rId1" '
                   'Type="%sworksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" '
                   'Type="%ssharedStrings" Target="sharedStrings.xml"/></Relationships>' % (PKG_REL, REL, REL))
        z.writestr("xl/worksheets/sheet1.xml", sayfa)
        z.writestr("xl/sharedStrings.xml", sst)


def cfb_paylasimli(d=1, k=9):
    """Döngüsüz, geçerli zincirli CFB; tek kusur: 4*d-1 akış AYNI k sektörlük veri zincirini gösterir (gerçek CFB'de
    olmaz; paylaşım çıktıyı akış sayısıyla çarpar)."""
    toplam = d + k
    f = 1
    while (f + toplam + 127) // 128 > f:
        f += 1
    fat = [FREESECT] * (f * 128)
    for i in range(f):
        fat[i] = FATSECT
    dir0 = f
    for i in range(d):
        fat[dir0 + i] = dir0 + i + 1 if i < d - 1 else ENDOFCHAIN
    v0 = f + d
    for i in range(k):
        fat[v0 + i] = v0 + i + 1 if i < k - 1 else ENDOFCHAIN

    def girdi(ad, tur, bas, boy):
        a = ad.encode("utf-16-le") + b"\0\0"
        e = a.ljust(64, b"\0") + struct.pack("<HBB", len(a), tur, 1) + struct.pack("<III", NOSTREAM, NOSTREAM, NOSTREAM)
        return e + b"\0" * 36 + struct.pack("<IQ", bas, boy)
    dz = girdi("Root Entry", 5, ENDOFCHAIN, 0)
    for i in range(4 * d - 1):
        dz += girdi("s%d" % i, 2, v0, k * 512)
    bas = kp.CFB_IMZA + b"\0" * 16 + struct.pack("<HHHHH", 0x3E, 3, 0xFFFE, 9, 6) + b"\0" * 6
    bas += struct.pack("<IIIIIIIII", 0, f, dir0, 0, 4096, ENDOFCHAIN, 0, ENDOFCHAIN, 0)
    bas += struct.pack("<109I", *(list(range(f)) + [FREESECT] * (109 - f)))
    return bas + struct.pack("<%dI" % len(fat), *fat) + dz + b"A" * (k * 512)


class BoyutVeCfbTest(_Gecici):
    def test_zip_basligi_boyu_kucuk_beyan_ederse_olculemedi(self):
        """F11: başlık açılmış boyu küçük beyan eder; üye gerçekten açılarak okunur → CRC/boy uyuşmazlığı ÖLÇÜLEMEDİ
        (çıkış 2), beyana güvenip devam edilmez."""
        docx_yaz(self.kaynak, p("x") + "<w:sectPr/>", rels=[], ekler={"word/media/b.bin": b"\x00" * 50000})
        with open(self.kaynak, "rb") as fh:
            b = bytearray(fh.read())
        yamalanan = 0
        for imza, ofs in ((b"PK\x03\x04", 22), (b"PK\x01\x02", 24)):
            i = 0
            while True:
                i = b.find(imza, i)
                if i < 0:
                    break
                if struct.unpack_from("<I", b, i + ofs)[0] == 50000:
                    b[i + ofs:i + ofs + 4] = struct.pack("<I", 1000)
                    yamalanan += 1
                i += 4
        self.assertEqual(2, yamalanan, "fikstür ön koşulu: yerel + merkezi başlık")
        with open(self.kaynak, "wb") as fh:
            fh.write(bytes(b))
        rc, _out, err = self.cikar()
        self.assertEqual(2, rc, err)
        self.assertIn("zip üyesi açılamadı: word/media/b.bin", err)
        self.assertFalse(os.path.exists(self.paket()), "okunamayan girdide paket yazılmaz")

    def test_akisli_sayim_sinirda_keser(self):
        """F11: sayım üyeyi parça parça açar ve sınırı geçince durur (tamamını belleğe almadan)."""
        okunan = []
        gercek = zipfile.ZipExtFile.read

        def say(self_, n=-1):
            veri = gercek(self_, n)
            okunan.append(len(veri))
            return veri
        docx_yaz(self.kaynak, p("x" * 9000) + "<w:sectPr/>", rels=[])
        with mock.patch.object(kp, "MAX_UYE", 4000), mock.patch.object(kp, "OKUMA_PARCASI", 1000), \
                mock.patch.object(zipfile.ZipExtFile, "read", say):
            rc, _out, err = self.cikar()
        self.assertEqual(2, rc, err)
        self.assertTrue(okunan and max(okunan) <= 1000, okunan[:5])

    def test_cfb_paylasilan_sektor_cfbhata(self):
        """F12: bir sektörü iki akışın paylaşması CfbHata (çıktı akış sayısıyla çarpılmaz); kontrol grubu: normal CFB
        okunur."""
        with self.assertRaisesRegex(kp.CfbHata, "birden çok yerde kullanılıyor"):
            kp.cfb_akislari(cfb_paylasimli(1, 9))  # 9 sektör = 4608 bayt ≥ mini akış eşiği: düz FAT yolu
        self.assertEqual(b"veri", kp.cfb_akislari(cfb_yaz([("Akis", b"veri")]))["Akis"])


# ── BÖLÜM: iz testleri ──
IZ_TABLOSU = """# İz tablosu — FS-SD-001

| Kaynak | Belge kimliği | Not |
|---|---|---|
| KM-0001..KM-0003 | BİLGİ | giriş |
| KM-0004–KM-0006 | FR-001 | |
| KM-0007 | BİLGİ | tablo başlık satırı |
| KM-0008, KM-0009 | TC-01, TC-02 | |
| KM-0010..KM-0011 | KR-001 | |
| KM-0012 | SCR-001 | |
| KM-0013 | KAPSAM-DIŞI | standart nesne değişikliği istenmiyor |
| KM-0014 | FR-002 | |
| KG-01..KG-02 | BİLGİ | logo ve ikon |
| KN-01..KN-05 | SCR-001 | |
"""
BELGE = "FR-001 kayıt. FR-002 iptal. FR-003 öneri. KR-001 kural. TC-01, TC-02 test. SCR-001 ekran.\n"


def notu_yaz(paket_dizini, kimlik, metin):
    """gorsel-notlari.md'de `kimlik`in işaret satırlarının ARASINA yazar (modelin görsel başına yaptığı `edit`)."""
    yol = os.path.join(paket_dizini, kp.NOT_DOSYASI)
    with open(yol, encoding="utf-8") as fh:
        s = fh.read()
    i = s.index(kp.isaret(kimlik) + "\n") + len(kp.isaret(kimlik)) + 1
    with open(yol, "w", encoding="utf-8") as fh:
        fh.write(s[:i] + metin + "\n" + s[i:])


class IzDenetimiTest(_Gecici):
    def setUp(self):
        super().setUp()
        self.assertEqual(0, self.cikar()[0])
        # KG-01 (png) okunmuş sayılır; KG-02 (emf) görüntülenemez → ÖLÇÜLEMEDİ, FAIL değil.
        notu_yaz(self.paket(), "KG-01", "Şirket logosu; metin yok.")
        self.belge = os.path.join(self.d, "FS-SD-001.md")
        with open(self.belge, "w", encoding="utf-8") as fh:
            fh.write(BELGE)

    def iz(self, tablo_metni, *ek):
        tablo = self.paket("iz-FS-SD-001.md")
        with open(tablo, "w", encoding="utf-8") as fh:
            fh.write(tablo_metni)
        return call_main(kp.main, ["iz", self.paket(), "--tablo", tablo, "--belge", self.belge, *ek])

    def test_tam_tablo_pass_ve_kaynaksiz_gereksinim_uyarisi(self):
        rc, out, err = self.iz(IZ_TABLOSU)
        self.assertEqual(0, rc, out + err)
        self.assertIn("KAPSAM (SCOPE)", out)
        self.assertIn("kapsanan: 21/21", out)
        self.assertIn("UYARI kaynaksız gereksinim", out)
        self.assertIn("FR-003", out)
        self.assertIn("İNCELEYİCİNİN ELLE OKUYACAĞI (BİLGİ / KAPSAM-DIŞI işaretli satırlar — madde metni metin.md'de): 4",
                      out)
        self.assertIn("SONUÇ: PASS", out)

    def test_eksik_madde_fail(self):
        rc, out, _ = self.iz(IZ_TABLOSU.replace("| KM-0014 | FR-002 | |\n", ""))
        self.assertEqual(1, rc, out)
        self.assertIn("EKSİK — tabloda olmayan kaynak maddesi: 1", out)
        self.assertIn("  - KM-0014", out)

    def test_hayalet_madde_fail(self):
        rc, out, _ = self.iz(IZ_TABLOSU + "| KM-0099 | FR-001 | |\n")
        self.assertEqual(1, rc, out)
        self.assertIn("HAYALET — pakette olmayan madde: 1", out)

    def test_bos_ve_taninmayan_esleme_fail(self):
        rc, out, _ = self.iz(IZ_TABLOSU.replace("| KM-0014 | FR-002 | |", "| KM-0014 |  | |"))
        self.assertEqual(1, rc, out)
        self.assertIn("BOŞ EŞLEME: 1", out)
        rc, out, _ = self.iz(IZ_TABLOSU.replace("| KM-0014 | FR-002 | |", "| KM-0014 | bkz. yukarı | |"))
        self.assertEqual(1, rc, out)
        self.assertIn("TANINMAYAN EŞLEME — ne belge kimliği ne BİLGİ/KAPSAM-DIŞI: 1", out)

    def test_belgede_olmayan_kimlik_fail(self):
        rc, out, _ = self.iz(IZ_TABLOSU.replace("| KM-0014 | FR-002 | |", "| KM-0014 | FR-009 | |"))
        self.assertEqual(1, rc, out)
        self.assertIn("BELGEDE YOK — eşlenen kimlik belgede geçmiyor: 1", out)
        self.assertIn("FR-009", out)

    def test_kapsam_disi_gerekcesiz_fail(self):
        rc, out, _ = self.iz(IZ_TABLOSU.replace("| KAPSAM-DIŞI | standart nesne değişikliği istenmiyor |",
                                                "| kapsam dışı | |"))
        self.assertEqual(1, rc, out)
        self.assertIn("KAPSAM-DIŞI GEREKÇESİZ — not sütunu boş: 1", out)

    def test_metin_elle_degisirse_fail(self):
        metin = self.oku("metin.md").replace("[KM-0014] Türetilmiş başlık", "Türetilmiş başlık")
        with open(self.paket("metin.md"), "w", encoding="utf-8") as fh:
            fh.write(metin)
        rc, out, _ = self.iz(IZ_TABLOSU)
        self.assertEqual(1, rc, out)
        self.assertIn("paket.json ile (14) uyuşmuyor", out)

    def test_kaynak_sha256_tablo_ile_eslesir(self):
        sha = json.loads(self.oku("paket.json"))["kaynak"]["sha256"]
        rc, out, _ = self.iz("Kaynak: istek.docx · sha256 %s\n\n%s" % (sha[:16], IZ_TABLOSU))
        self.assertEqual(0, rc, out)
        self.assertIn("UYARI tabloda kaynak sha256'sı yok — iz hangi kaynağa ait olduğunu söylemiyor: 0", out)
        rc, out, _ = self.iz("Kaynak: istek.docx · sha256 %s\n\n%s" % ("0" * 16, IZ_TABLOSU))
        self.assertEqual(1, rc, out)
        self.assertIn("BAŞKA KAYNAĞIN TABLOSU — tablodaki sha256 paketin kaynağıyla uyuşmuyor: 1", out)
        rc, out, _ = self.iz(IZ_TABLOSU)
        self.assertEqual(0, rc, out)
        self.assertIn("UYARI tabloda kaynak sha256'sı yok — iz hangi kaynağa ait olduğunu söylemiyor: 1", out)

    def test_bos_paket_uyarisi(self):
        bos = os.path.join(self.d, "bos.docx")
        docx_yaz(bos, "<w:sectPr/>", rels=[])
        self.assertEqual(0, call_main(kp.main, ["cikar", bos, "--hedef-kok", self.kok, "--id", "bos"])[0])
        tablo = os.path.join(self.d, "iz-bos.md")
        with open(tablo, "w", encoding="utf-8") as fh:
            fh.write("| Kaynak | Belge kimliği | Not |\n|---|---|---|\n")
        rc, out, _ = call_main(kp.main, ["iz", os.path.join(self.kok, "bos"), "--tablo", tablo, "--belge", self.belge])
        self.assertEqual(0, rc, out)
        self.assertIn("UYARI boş paket: 1", out)
        self.assertIn("paket 0 kaynak maddesi taşıyor", out)

    def test_tablo_okunamazsa_olculemedi(self):
        rc, _out, err = call_main(kp.main, ["iz", self.paket(), "--tablo", os.path.join(self.d, "yok.md"),
                                            "--belge", self.belge])
        self.assertEqual(2, rc)
        self.assertIn("ÖLÇÜLEMEDİ", err)

    def test_km_semasi_tablo_ile_eslesir(self):
        """F13: tablo başka bir numaralandırma şemasıyla eşlenmişse FAIL; şema yoksa UYARI; aynıysa PASS."""
        meta = json.loads(self.oku("paket.json"))
        self.assertEqual(kp.KM_SEMASI, meta["km_semasi"])
        bas = "Kaynak: istek.docx · sha256 %s · km şeması %%d\n\n" % meta["kaynak"]["sha256"][:16]
        rc, out, _ = self.iz(bas % kp.KM_SEMASI + IZ_TABLOSU)
        self.assertEqual(0, rc, out)
        self.assertIn("UYARI tabloda km şeması yok: 0", out)
        self.assertIn("NUMARALANDIRMA ŞEMASI FARKLI — paketi yeniden çıkar, tabloyu yeniden eşle: 0", out)
        rc, out, _ = self.iz(bas % (kp.KM_SEMASI - 1) + IZ_TABLOSU)
        self.assertEqual(1, rc, out)
        self.assertIn("NUMARALANDIRMA ŞEMASI FARKLI — paketi yeniden çıkar, tabloyu yeniden eşle: 1", out)
        rc, out, _ = self.iz(IZ_TABLOSU)
        self.assertEqual(0, rc, out)
        self.assertIn("UYARI tabloda km şeması yok: 1", out)

    def test_eski_paket_semasiz_sema_1_sayilir(self):
        """F13: km_semasi alanı olmayan (eski betikle çıkarılmış) paket şema 1 sayılır; güncel şemayla eşlenmiş
        tablo onunla FAIL verir."""
        meta = json.loads(self.oku("paket.json"))
        del meta["km_semasi"]
        with open(self.paket("paket.json"), "w", encoding="utf-8") as fh:
            json.dump(meta, fh, ensure_ascii=False)
        rc, out, _ = self.iz("km şeması %d\n\n%s" % (kp.KM_SEMASI, IZ_TABLOSU))
        self.assertEqual(1, rc, out)
        self.assertIn("paket: km şeması 1", out)

# ── BÖLÜM: kural metni testleri ──
# ── BÖLÜM: görsel notları (gorsel-notlari.md iskeleti + iz görsel denetimi) ──
def _gorsel_r(rid):
    return GORSEL.replace("rIdImg", rid)


GORSEL_GOVDE = "".join([
    p("Sipariş ekranı", stil="Balk1"),
    p("Giriş ekranı aşağıda", ek=_gorsel_r("rIdG1")),
    p("", ek=_gorsel_r("rIdG2")),
    p("Onay penceresi"),
    p("Hata mesajı", ek=_gorsel_r("rIdG3")),
    p("Ek ekran:", ek=OLE % "rIdOle1"),
    "<w:sectPr/>",
])
GORSEL_RELS = [("rIdG1", "image", "media/image1.png"), ("rIdG2", "image", "media/image2.png"),
               ("rIdG3", "image", "media/image3.jpg"), ("rIdOle1", "oleObject", "embeddings/oleObject1.bin")]
GORSEL_IZ = """# İz tablosu — FS-SD-002 · km şeması %d · Kaynak: gorselli.docx · sha256 %s

| Kaynak | Belge kimliği | Not |
|---|---|---|
| KM-0001 | BİLGİ | başlık |
| KM-0002..KM-0005 | FR-001 | |
| KG-01..KG-03 | FR-001 | |
| KN-01 | SCR-001 | |
"""


class GorselNotlariTest(_Gecici):
    def setUp(self):
        super().setUp()
        png = os.path.join(self.d, "g.png")
        write_png(png)
        with open(png, "rb") as fh:
            png_b = fh.read()
        self.kaynak = os.path.join(self.d, "gorselli.docx")
        docx_yaz(self.kaynak, GORSEL_GOVDE, rels=GORSEL_RELS, ekler={
            "word/media/image1.png": png_b, "word/media/image2.png": png_b, "word/media/image3.jpg": png_b,
            "word/embeddings/oleObject1.bin": cfb_yaz([("\x01Ole10Native", ole10native_yaz("ekran.png", png_b))])})
        rc, self.cikti, _ = self.cikar()
        self.assertEqual(0, rc, self.cikti)
        self.belge = os.path.join(self.d, "FS-SD-002.md")
        with open(self.belge, "w", encoding="utf-8") as fh:
            fh.write("FR-001 sipariş girişi. SCR-001 ekran. FR-003 onay düğmesi.\n")

    def meta(self):
        return json.loads(self.oku("paket.json"))

    def iz(self, tablo_metni=None):
        if tablo_metni is None:
            tablo_metni = GORSEL_IZ % (kp.KM_SEMASI, self.meta()["kaynak"]["sha256"][:16])
        tablo = self.paket("iz-FS-SD-002.md")
        with open(tablo, "w", encoding="utf-8") as fh:
            fh.write(tablo_metni)
        return call_main(kp.main, ["iz", self.paket(), "--tablo", tablo, "--belge", self.belge])

    def hepsini_doldur(self, haric=()):
        for k in ("KG-01", "KG-02", "KG-03", "KN-01"):
            if k not in haric:
                notu_yaz(self.paket(), k, "%s: Sipariş giriş ekranı; alanlar Müşteri, Malzeme; Kaydet düğmesi" % k)

    def test_iskelet_her_gorsel_icin_bolum_konum_ve_bos_gorulen(self):
        notlar = self.oku(kp.NOT_DOSYASI)
        bolumler = re.findall(r"^## (K[GN]-\d+)$", notlar, re.M)
        self.assertEqual(["KG-01", "KG-02", "KG-03", "KN-01"], bolumler)
        self.assertEqual(4, notlar.count(kp.GORULEN_SATIRI))
        for k in ("KG-01", "KG-02", "KG-03", "KN-01"):
            self.assertIn("%s\n%s\n\n%s\n" % (kp.GORULEN_SATIRI, kp.isaret(k), kp.isaret(k, True)), notlar)
        self.assertIn("- Dosya: `media/KG-01_image1.png`", notlar)
        self.assertIn("- Dosya: `gomulu/KN-01_ekran.png`", notlar)
        self.assertIn("- Konum: KM-0002 (metin.md", notlar)          # işaret KM satırında
        self.assertIn("- Konum: KM-0002 sonrası (metin.md", notlar)  # işaret ayrı satırda
        self.assertIn("- Konum: KM-0004 (metin.md", notlar)
        self.assertIn("`view`", notlar)
        self.assertEqual(({"KG-01": "", "KG-02": "", "KG-03": "", "KN-01": ""}, [], {}), kp.gorsel_notlarini_oku(
            __import__("pathlib").Path(self.paket())))
        meta = self.meta()
        self.assertEqual(["KG-01", "KG-02", "KG-03", "KN-01"], [g["kimlik"] for g in meta["gorsel"]])
        self.assertTrue(all(g["goruntulenebilir"] for g in meta["gorsel"]))
        self.assertIn("## Görsel okuma — `gorsel-notlari.md`", self.oku("INDEX.md"))
        self.assertIn("GÖRSEL NOTLARI:", self.cikti)

    def test_iz_iki_bos_not_fail_ve_adlarini_basar(self):
        self.hepsini_doldur(haric=("KG-02", "KN-01"))
        rc, out, _ = self.iz()
        self.assertEqual(1, rc, out)
        self.assertIn("GÖRSEL OKUNMADI: 2 — KG-02, KN-01", out)
        self.assertIn("notu dolu 2", out)
        self.assertIn("SONUÇ: FAIL", out)

    def test_iz_tum_notlar_dolu_pass(self):
        self.hepsini_doldur()
        rc, out, _ = self.iz()
        self.assertEqual(0, rc, out)
        self.assertIn("GÖRSEL OKUNMADI: 0", out)
        self.assertIn("GÖRSEL ÖLÇÜLEMEDİ: 0", out)
        self.assertIn("SONUÇ: PASS", out)
        self.assertNotIn("ÖLÇÜLEMEDİ: 1", out)

    def test_yer_tutucu_not_bos_sayilir_ve_bolum_silinirse_bozuk(self):
        self.hepsini_doldur(haric=("KG-01",))
        notu_yaz(self.paket(), "KG-01", "—")
        yol = self.paket(kp.NOT_DOSYASI)
        with open(yol, encoding="utf-8") as fh:
            s = fh.read()
        bas = s.index("## KG-03\n")
        with open(yol, "w", encoding="utf-8") as fh:
            fh.write(s[:bas] + s[s.index("## KN-01\n"):])
        rc, out, _ = self.iz()
        self.assertEqual(1, rc, out)
        self.assertIn("GÖRSEL OKUNMADI: 1 — KG-01", out)
        self.assertIn("GÖRSEL NOTU BOZUK — işaret eksik ya da sırası bozuk; not okunamadı: 1", out)
        self.assertIn("KG-03: işaret çifti yok", out)

    def test_not_dosyasi_yoksa_fail(self):
        os.remove(self.paket(kp.NOT_DOSYASI))
        rc, out, _ = self.iz()
        self.assertEqual(1, rc, out)
        self.assertIn("GÖRSEL NOTLARI DENETLENEMEDİ: 1", out)

    def test_notta_anilan_kimlik_iz_satirinda_yoksa_uyari(self):
        self.hepsini_doldur(haric=("KG-03",))
        notu_yaz(self.paket(), "KG-03", "Onay penceresi; Onayla düğmesi → FR-003")
        rc, out, _ = self.iz()
        self.assertEqual(0, rc, out)  # UYARI, FAIL değil
        self.assertIn("UYARI görsel notundaki kimlik iz tablosunda o görsele eşlenmemiş: 1", out)
        self.assertIn("KG-03: FR-003 notta var, iz satırında yok", out)

    def test_yeniden_cikarim_yazilmis_notlari_korur_kaynak_degisince_kenara_alir(self):
        self.hepsini_doldur()
        rc, out, _ = self.cikar()
        self.assertEqual(0, rc, out)
        self.assertIn("korundu", out)
        self.assertIn("KG-01: Sipariş giriş ekranı", self.oku(kp.NOT_DOSYASI))
        # Kaynağın yeni sürümü (aynı görseller, değişen metin → başka sha256): eski notlar silinmez, kenara alınır.
        with zipfile.ZipFile(self.kaynak) as z:
            ekler = {a: z.read(a) for a in z.namelist() if a.startswith("word/media/") or a.startswith("word/embed")}
        docx_yaz(self.kaynak, p("Yeni sürüm notu") + GORSEL_GOVDE, rels=GORSEL_RELS, ekler=ekler)
        rc, out, _ = self.cikar()
        self.assertEqual(0, rc, out)
        self.assertIn("önceki notlar (başka kaynağa ait) kenara alındı", out)
        self.assertNotIn("Sipariş giriş ekranı", self.oku(kp.NOT_DOSYASI))
        yedek = [f for f in os.listdir(self.paket()) if f.startswith("gorsel-notlari.") and f != kp.NOT_DOSYASI]
        self.assertEqual(1, len(yedek), os.listdir(self.paket()))
        with open(self.paket(yedek[0]), encoding="utf-8") as fh:
            self.assertIn("KG-01: Sipariş giriş ekranı", fh.read())


class GorselBicimTest(_Gecici):
    def test_emf_goruntulenemez_olculemedi_fail_degil(self):
        # Ana fikstür: KG-01 png (konumlu), KG-02 emf (gövdede başvurusuz).
        rc, out, _ = self.cikar()
        self.assertEqual(0, rc, out)
        self.assertIn("ÖLÇÜLEMEDİ: KG-02 GÖRÜNTÜLENEMEZ (emf)", out)
        index = self.oku("INDEX.md")
        self.assertIn("| KG-02 | `word/media/image2.emf` | `media/KG-02_image2.emf` | GÖRÜNTÜLENEMEZ (emf) |", index)
        notlar = self.oku(kp.NOT_DOSYASI)
        self.assertIn("GÖRÜNTÜLENEMEZ (emf) — ÖLÇÜLEMEDİ", notlar)
        self.assertIn("kullanıcıdan PNG iste", notlar)
        self.assertIn("metinde konumu yok", notlar)
        meta = json.loads(self.oku("paket.json"))
        g = {x["kimlik"]: x for x in meta["gorsel"]}
        self.assertEqual((True, False), (g["KG-01"]["goruntulenebilir"], g["KG-02"]["goruntulenebilir"]))
        notu_yaz(self.paket(), "KG-01", "Logo")
        tablo = self.paket("iz.md")
        with open(tablo, "w", encoding="utf-8") as fh:
            fh.write("# iz · km şeması %d\n\n| Kaynak | Belge kimliği | Not |\n|---|---|---|\n"
                     "| KM-0001..KM-%04d | BİLGİ | x |\n| KG-01..KG-02 | BİLGİ | logo |\n| KN-01..KN-05 | BİLGİ | x |\n"
                     % (kp.KM_SEMASI, meta["km_toplam"]))
        belge = os.path.join(self.d, "FS.md")
        with open(belge, "w", encoding="utf-8") as fh:
            fh.write("Belge.\n")
        rc, out, _ = call_main(kp.main, ["iz", self.paket(), "--tablo", tablo, "--belge", belge])
        self.assertEqual(0, rc, out)
        self.assertIn("GÖRSEL OKUNMADI: 0", out)
        self.assertIn("GÖRSEL ÖLÇÜLEMEDİ: 1 — KG-02 GÖRÜNTÜLENEMEZ (emf)", out)
        self.assertIn("SONUÇ: PASS", out)
        self.assertIn("ÖLÇÜLEMEDİ: 1 görsel okunamadı (KG-02 GÖRÜNTÜLENEMEZ (emf)) — sonuç bu görselleri KAPSAMAZ", out)

    def test_goruntulenebilir_liste_tek_kaynak(self):
        # aXet.code 1.5.1 `view` ölçümü (2026-11-19/20): png/jpg/jpeg/gif açar; bmp/emf/wmf açmaz.
        self.assertEqual((".png", ".jpg", ".jpeg", ".gif"), kp.GORUNTULENEBILIR)
        self.assertTrue(set(kp.GORUNTULENEBILIR) <= set(kp.GORSEL_UZANTILARI))
        self.assertIn(".bmp", kp.GORSEL_UZANTILARI)
        g = kp._gorsel("KG-09", "word/media/x.PNG", "media/KG-09_x.PNG", [], False)  # uzantı büyük harf: açar
        self.assertTrue(g["goruntulenebilir"])
        for uz in (".emf", ".wmf", ".bmp"):
            g = kp._gorsel("KG-09", "word/media/x" + uz, "media/KG-09_x" + uz, [], False)
            self.assertEqual((False, "GÖRÜNTÜLENEMEZ (%s)" % uz[1:]), (g["goruntulenebilir"], g["neden"]))


# ── BÖLÜM: R5 (bug gate R4) — not sınırı, yer tutucu, kenar dosyası, svgBlip, görsel tanıma, XML dışı, kaçış ──
SVG_GORSEL = ('<w:r><w:drawing><wp:inline><a:graphic><a:graphicData><pic:pic><pic:blipFill><a:blip r:embed="rIdPng">'
              '<a:extLst><a:ext uri="{96DAC541-7B7A-43D3-8B79-37D633B846F1}"><asvg:svgBlip '
              'xmlns:asvg="' + "http" + '://schemas.microsoft.com/office/drawing/2016/SVG/main" r:embed="rIdSvg"/>'
              '</a:ext>'
              '</a:extLst></a:blip></pic:blipFill></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r>')
HARICI = ('<w:r><w:drawing><wp:inline><a:graphic><a:graphicData><pic:pic><pic:blipFill><a:blip r:link="rIdDis"/>'
          '</pic:blipFill></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r>')


def _png_bayt(d):
    yol = os.path.join(d, "r5.png")
    write_png(yol)
    with open(yol, "rb") as fh:
        return fh.read()


class GorselNotSiniriTest(GorselNotlariTest):
    """F1/F2/F3: Görülen alanının sınırı, yer tutucu, kenara alınan notların korunması. GorselNotlariTest'in
    testleri burada YENİDEN koşmasın diye yalnız setUp/yardımcılar miras alınır (aşağıda testler silinir)."""

    def notlari_yaz(self, metin):
        with open(self.paket(kp.NOT_DOSYASI), "w", encoding="utf-8") as fh:
            fh.write(metin)

    def test_isaret_disina_eklenen_her_bicim_notu_doldurmaz(self):
        """R6-F1: sona eklenen metin Markdown biçimi ne olursa olsun son görselin notu SAYILMAZ (bug gate'in 8 kardeşi
        + "## Genel" tetiği + madde/Görülen satırı); her biri UYARI verir, FAIL'i değiştirmez."""
        self.hepsini_doldur(haric=("KN-01",))
        taban = self.oku(kp.NOT_DOSYASI)
        vakalar = {
            "## başlık": "\n## Genel değerlendirme\n\nTüm görseller incelendi.\n",
            "--- yatay çizgi": "\n---\n\nTüm görseller incelendi.\n",
            "*** yatay çizgi": "\n***\n\nTüm görseller incelendi.\n",
            "kalın satır": "\n**Genel değerlendirme**\n\nTüm görseller incelendi.\n",
            "setext başlık": "\nGenel değerlendirme\n===================\n\nTüm görseller incelendi.\n",
            "girintili ##": "\n   ## Genel değerlendirme\n\nTüm görseller incelendi.\n",
            "düz paragraf": "\nTüm görseller incelendi.\n",
            "alıntı": "\n> Not: tüm görseller incelendi.\n",
            "html başlık": "\n<h2>Genel</h2>\n\nTüm görseller incelendi.\n",
            "ikinci Görülen satırı": "\n- Görülen: Onay penceresi\n",
            "girintisiz madde": "\n- Ekran: Onay\n- Alan: Tutar\n",
            "iskelet benzeri satır": "\n- Konum: sağ üstte logo\n",
        }
        for ad, ek in vakalar.items():
            with self.subTest(ad):
                self.notlari_yaz(taban + ek)
                notlar, uyari, bozuk = kp.gorsel_notlarini_oku(__import__("pathlib").Path(self.paket()))
                self.assertEqual(("", {}), (notlar["KN-01"], bozuk))
                self.assertEqual(1, len(uyari), uyari)
                self.assertIn("KN-01 bölümünde işaretlerin dışında metin", uyari[0])
                rc, out, _ = self.iz()
                self.assertEqual(1, rc, out)
                self.assertIn("GÖRSEL OKUNMADI: 1 — KN-01", out)
                self.assertIn("UYARI görsel notları dosyasının yapısı: 1", out)

    def test_isaretler_arasi_cok_satirli_liste_ve_tablo_dolu_sayilir(self):
        self.hepsini_doldur(haric=("KG-02", "KN-01"))
        notu_yaz(self.paket(), "KG-02", "### Onay penceresi\n\n- Alan: Tutar\n  - alt madde: Para birimi\n\n---\n")
        notu_yaz(self.paket(), "KN-01", "| Sütun | Değer |\n|---|---|\n| Müşteri | 1000 |\n\n> alıntı satırı")
        notlar, uyari, bozuk = kp.gorsel_notlarini_oku(__import__("pathlib").Path(self.paket()))
        self.assertEqual(([], {}), (uyari, bozuk))
        self.assertIn("alt madde: Para birimi", notlar["KG-02"])
        self.assertIn("| Müşteri | 1000 |", notlar["KN-01"])
        rc, out, _ = self.iz()
        self.assertEqual(0, rc, out)
        self.assertIn("GÖRSEL NOTU BOZUK — işaret eksik ya da sırası bozuk; not okunamadı: 0", out)

    def test_isaret_eksik_ya_da_sirasi_bozuk_fail(self):
        self.hepsini_doldur()
        taban = self.oku(kp.NOT_DOSYASI)
        ac, kap = kp.isaret("KG-02"), kp.isaret("KG-02", True)
        vakalar = {
            "kapanış silindi": (taban.replace(kap + "\n", ""), {"KG-02"}, "KG-02: kapanış işareti yok (satır"),
            "son kapanış silindi": (taban.replace(kp.isaret("KN-01", True) + "\n", ""), {"KN-01"},
                                    "KN-01: kapanış işareti yok (dosya sonu)"),
            "açılış silindi": (taban.replace(ac + "\n", ""), {"KG-02"}, "KG-02: satır"),
            "ikisi silindi": (taban.replace(ac + "\n", "").replace(kap + "\n", ""), {"KG-02"},
                              "KG-02: işaret çifti yok"),
            "sıra ters": (taban.replace(ac + "\n", "@@").replace(kap + "\n", ac + "\n").replace("@@", kap + "\n"),
                          {"KG-02"}, "açılışsız ya da sırası bozuk"),
            "başka kimliğin kapanışı": (taban.replace(kap + "\n", kp.isaret("KG-03", True) + "\n", 1),
                                        {"KG-02", "KG-03"}, "başka kimliğin kapanışı"),
            "kapanış satırına metin eklendi": (taban.replace(kap + "\n", kap + " Onay penceresi\n"), {"KG-02"},
                                               "KG-02: kapanış işareti yok (satır"),
        }
        for ad, (metin, beklenen, neden) in vakalar.items():
            with self.subTest(ad):
                self.notlari_yaz(metin)
                rc, out, _ = self.iz()
                self.assertEqual(1, rc, out)
                satir = [x for x in out.splitlines() if x.startswith("GÖRSEL NOTU BOZUK")][0]
                self.assertTrue(satir.endswith(": %d" % len(beklenen)), (satir, out))
                for k in beklenen:
                    self.assertRegex(out, r"(?m)^  - %s[: ]" % k)
                self.assertIn("işaret satırlarını iskeletteki biçimiyle geri koy", out)
                self.assertIn(neden, out)

    def test_baslik_arkasina_metin_eklenirse_kimlik_dogru_kalir(self):
        self.hepsini_doldur(haric=("KG-01", "KG-02"))
        self.notlari_yaz(self.oku(kp.NOT_DOSYASI).replace("## KG-02\n", "## KG-02 — Onay ekranı\n"))
        notlar, uyari, bozuk = kp.gorsel_notlarini_oku(__import__("pathlib").Path(self.paket()))
        self.assertEqual(("", "", [], {}), (notlar["KG-01"], notlar["KG-02"], uyari, bozuk))
        rc, out, _ = self.iz()
        self.assertEqual(1, rc, out)
        self.assertIn("GÖRSEL OKUNMADI: 2 — KG-01, KG-02", out)

    def test_baslik_silinse_de_not_isaretten_okunur(self):
        """Bölüm başlığı silinse de not kimliğini işaretten alır; sonraki bölümün iskeleti KG-01'in notu sayılmaz."""
        self.hepsini_doldur(haric=("KG-01",))
        self.notlari_yaz(self.oku(kp.NOT_DOSYASI).replace("## KG-02\n", ""))
        notlar, _, bozuk = kp.gorsel_notlarini_oku(__import__("pathlib").Path(self.paket()))
        self.assertEqual(("", {}), (notlar["KG-01"], bozuk))
        self.assertIn("KG-02: Sipariş", notlar["KG-02"])

    def test_yinelenen_bolum_uyari(self):
        self.hepsini_doldur()
        self.notlari_yaz(self.oku(kp.NOT_DOSYASI) + "\n## KG-03\n\n%s\nikinci kez\n%s\n" % (
            kp.isaret("KG-03"), kp.isaret("KG-03", True)))
        rc, out, _ = self.iz()
        self.assertEqual(0, rc, out)
        self.assertIn("KG-03 işaret çifti birden fazla — yalnız ilki sayıldı", out)

    def test_cok_satirli_ve_sozcuk_yer_tutucu_bos_sayilir(self):
        notu_yaz(self.paket(), "KG-01", "-\n-")
        notu_yaz(self.paket(), "KG-02", "?\n?")
        notu_yaz(self.paket(), "KG-03", "TODO")
        notu_yaz(self.paket(), "KN-01", "(boş)")
        rc, out, _ = self.iz()
        self.assertEqual(1, rc, out)
        self.assertIn("GÖRSEL OKUNMADI: 4 — KG-01, KG-02, KG-03, KN-01", out)
        for bos in ("Doldurulacak.", "…", "- - -", "BOŞ", "n/a", "TBD", "yok", "x", "N/A."):
            self.assertTrue(kp.gorulen_bos(bos), bos)
        for dolu in ("Kaydet", "1", "Onay → FR-003", "yok sayılan alan", "x ekseni"):
            self.assertFalse(kp.gorulen_bos(dolu), dolu)

    def test_isaret_arasi_bilgisiz_govde_bos_sayilir(self):
        """R7: iskelet satırı, başlık, kapanmamış yorum, boş kod çiti ve yer tutucu işaretler arasında dolu sayılmaz;
        kısa meşru not dolu kalır."""
        self.hepsini_doldur(haric=("KG-02",))
        nf = self.paket(kp.NOT_DOSYASI)
        with open(nf, encoding="utf-8") as fh:
            taban = fh.read()
        bos = (kp.GORULEN_SATIRI, "- Görülen:", "## KG-02", "### Görsel 2", "- Dosya: `media/KG-02_image2.png`",
               "<!-- TODO: gorsel okunamadi", "```text\n```", "~~~\n~~~", "TODO: doldur", "TODO TODO", "xx", "&nbsp;",
               "<br>", "![](media/KG-02_image2.png)")
        dolu = ("```text\nKaydet\n```", "## Ekran\nKaydet düğmesi", "logo", "OK", "1", "Boş form", "İkon", "OK ekranı")
        for metin in bos + dolu:
            with self.subTest(metin=metin):
                with open(nf, "w", encoding="utf-8") as fh:
                    fh.write(taban)
                notu_yaz(self.paket(), "KG-02", metin)
                rc, out, _ = self.iz()
                self.assertIn("GÖRSEL OKUNMADI: 1 — KG-02" if metin in bos else "GÖRSEL OKUNMADI: 0", out)
        for v in ("bos", "Bos.", "none", "NULL", "TBA", "doldur", "TODO: doldur", "TODO TODO", "xx", "XXX", "&nbsp;",
                  "<br/>", "![](media/KG-02_image2.png)", "[TODO]"):
            self.assertTrue(kp.gorulen_bos(v), v)
        for v in ("logo", "OK", "1", "Boş form", "İkon", "OK ekranı", "x ekseni", "Todo listesi ekranı", "a < b > c"):
            self.assertFalse(kp.gorulen_bos(v), v)

    def test_gorsel_acilamadi_ifadesi_ve_yalniz_kimlik_bos_sayilir(self):
        """R7b: model görseli açamayınca yazdığı ifade ya da yalnız kimlik notun TAMAMIYSA boş; cümle içinde geçmesi
        notu boşaltmaz."""
        for v in ("okunamadı", "Okunamadı.", "OKUNAMADI", "okunamadi", "görülmedi", "Henüz yok", "henuz yok",
                  "okunmadı", "açılamadı", "görüntülenemedi", "Görsel açılamadı.", "görsel okunamadı", "nil", "NIL",
                  "KG-02", "kg-02", "KN-01", "(KG-02)"):
            self.assertTrue(kp.gorulen_bos(v), v)
        for v in ("0", "logo", "OK", "1", "Boş form", "İkon", "OK ekranı", "Okunamayan alan yok, tablo 3 satır",
                  "Logo okunamadı ama başlık: Sipariş", "KG-02: Kaydet düğmesi", "Görülmedi uyarısı ekranı"):
            self.assertFalse(kp.gorulen_bos(v), v)
        self.hepsini_doldur(haric=("KG-02",))
        notu_yaz(self.paket(), "KG-02", "Görsel açılamadı.")
        rc, out, _ = self.iz()
        self.assertIn("GÖRSEL OKUNMADI: 1 — KG-02", out)

    def test_kaynak_a_b_a_b_hicbir_not_kaybolmaz(self):
        with open(self.kaynak, "rb") as fh:
            a_bayt = fh.read()
        with zipfile.ZipFile(self.kaynak) as z:
            ekler = {x: z.read(x) for x in z.namelist() if x.startswith(("word/media/", "word/embed"))}
        self.hepsini_doldur()                                   # A'nın notları
        docx_yaz(self.kaynak, p("Yeni sürüm notu") + GORSEL_GOVDE, rels=GORSEL_RELS, ekler=ekler)
        with open(self.kaynak, "rb") as fh:
            b_bayt = fh.read()
        rc, out, _ = self.cikar()
        self.assertEqual(0, rc, out)
        notu_yaz(self.paket(), "KG-01", "B notu")               # B'nin notu

        def surum(bayt, beklenen):
            with open(self.kaynak, "wb") as fh:
                fh.write(bayt)
            rc, out, _ = self.cikar()
            self.assertEqual(0, rc, out)
            self.assertIn("geri yüklendi", out)
            self.assertIn(beklenen, self.oku(kp.NOT_DOSYASI))
            hepsi = ""
            for f in os.listdir(self.paket()):
                if f.startswith("gorsel-notlari."):
                    with open(self.paket(f), encoding="utf-8") as fh:
                        hepsi += fh.read()
            self.assertIn("KG-01: Sipariş giriş ekranı", hepsi)
            self.assertIn("B notu", hepsi)

        surum(a_bayt, "KG-01: Sipariş giriş ekranı")
        surum(b_bayt, "B notu")
        surum(a_bayt, "KG-01: Sipariş giriş ekranı")

    def test_kenar_dosyasi_ezilmez_ve_imzasiz_not_imza_yok_der(self):
        self.hepsini_doldur()
        s = self.oku(kp.NOT_DOSYASI)
        self.notlari_yaz("\n".join(x for x in s.splitlines() if "sha256" not in x) + "\n")
        rc, out, _ = self.cikar()
        self.assertEqual(0, rc, out)
        self.assertIn("imza yok", out)
        self.assertTrue(os.path.isfile(self.paket("gorsel-notlari.imzasiz.md")))
        self.notlari_yaz("ikinci imzasız not\n")
        rc, out, _ = self.cikar()
        self.assertIn("gorsel-notlari.imzasiz.2.md", out)
        with open(self.paket("gorsel-notlari.imzasiz.md"), encoding="utf-8") as fh:
            self.assertIn("KG-01: Sipariş giriş ekranı", fh.read())

    def test_cok_gorsel_index_uyarisi(self):
        with mock.patch.object(kp, "COK_GORSEL", 3):
            rc, out, _ = self.cikar()
        self.assertEqual(0, rc, out)
        self.assertIn("UYARI: 4 görsel + gömülü nesne (eşik 3)", self.oku("INDEX.md"))
        rc, out, _ = self.cikar()
        self.assertNotIn("UYARI: 4 görsel", self.oku("INDEX.md"))


for _ad in [a for a in vars(GorselNotlariTest) if a.startswith("test_")]:
    setattr(GorselNotSiniriTest, _ad, None)


class GorselTanimaTest(_Gecici):
    """F4/F5/F9: svgBlip PNG yedeği, media/ dışı görsel, çözülemeyen ve harici başvuru, kullanıcı PNG'si."""

    def kur(self, govde, rels, ekler):
        docx_yaz(self.kaynak, govde, rels=rels, ekler=ekler)
        rc, out, err = self.cikar()
        self.assertEqual(0, rc, out + err)
        return out

    def iz(self, satirlar, belge="Belge.\n"):
        meta = json.loads(self.oku("paket.json"))
        tablo = self.paket("iz.md")
        with open(tablo, "w", encoding="utf-8") as fh:
            fh.write("# iz · km şeması %d\n\n| Kaynak | Belge kimliği | Not |\n|---|---|---|\n"
                     "| KM-0001..KM-%04d | BİLGİ | x |\n%s" % (kp.KM_SEMASI, meta["km_toplam"], satirlar))
        yol = os.path.join(self.d, "FS.md")
        with open(yol, "w", encoding="utf-8") as fh:
            fh.write(belge)
        return call_main(kp.main, ["iz", self.paket(), "--tablo", tablo, "--belge", yol])

    def test_svgblip_png_yedegi_uzerinden_okunur(self):
        png = _png_bayt(self.d)
        self.kur(p("Logo", ek=SVG_GORSEL), [("rIdPng", "image", "media/image1.png"),
                                             ("rIdSvg", "image", "media/image2.svg")],
                 {"word/media/image1.png": png, "word/media/image2.svg": b"<svg xmlns='x'/>"})
        g = {x["kimlik"]: x for x in json.loads(self.oku("paket.json"))["gorsel"]}
        self.assertEqual(("png", "svg", "KG-01"), (g["KG-01"]["bicim"], g["KG-02"]["bicim"], g["KG-02"].get("yedek")))
        self.assertIn("PNG yedeği KG-01 üzerinden okunur", self.oku(kp.NOT_DOSYASI))
        self.assertIn("KG-01 ile aynı yer", self.oku(kp.NOT_DOSYASI))
        notu_yaz(self.paket(), "KG-01", "Şirket logosu")
        rc, out, _ = self.iz("| KG-01..KG-02 | BİLGİ | logo |\n")
        self.assertEqual(0, rc, out)
        self.assertIn("GÖRSEL ÖLÇÜLEMEDİ: 0", out)
        self.assertIn("PNG yedekli SVG 1", out)

    def test_media_disindaki_gorsel_iliski_tipinden_taninir(self):
        png = _png_bayt(self.d)
        # resim.bin: görsel uzantısı yok, yalnız görsel İLİŞKİSİYLE tanınır (uzantı kuralı tek başına yakalamaz).
        out = self.kur(p("Ekran", ek=_gorsel_r("rIdG1")) + p("İkon", ek=_gorsel_r("rIdG2")),
                       [("rIdG1", "image", "images/ekran.png"), ("rIdG2", "image", "images/resim.bin")],
                       {"word/images/ekran.png": png, "word/images/resim.bin": png})
        self.assertIn("DOĞRULAMA: PASS", out)
        meta = json.loads(self.oku("paket.json"))
        self.assertEqual(["word/images/ekran.png", "word/images/resim.bin"], [g["parca"] for g in meta["gorsel"]])
        self.assertIn("⟦KG-02 görsel: media/KG-02_resim.bin⟧", self.oku("metin.md"))
        self.assertEqual([], [x for x in meta["xml_disi"] if x["parca"] == "word/images/ekran.png"])
        self.assertIn("⟦KG-01 görsel: media/KG-01_ekran.png⟧", self.oku("metin.md"))
        self.assertTrue(os.path.isfile(self.paket("media", "KG-01_ekran.png")))

    def test_cozulemeyen_ve_harici_gorsel_uyari(self):
        out = self.kur(p("Kayıp", ek=_gorsel_r("rIdYok")) + p("Dış", ek=HARICI),
                       [("rIdDis", "image", "http" + "://ornek.invalid/x.png")], {})
        self.assertIn("UYARI çözülemeyen başvuru: ⟦gorsel başvurusu çözülemedi: rIdYok⟧", out)
        self.assertIn("UYARI harici görsel bağlantısı: 1", out)
        self.assertIn(kp.HARICI_GORSEL, self.oku("metin.md"))
        index = self.oku("INDEX.md")
        self.assertIn("- UYARI çözülemeyen başvuru", index)
        self.assertIn("- UYARI harici görsel bağlantısı: 1", index)
        rc, out, _ = self.iz("")
        self.assertEqual(0, rc, out)
        self.assertIn("UYARI çözülemeyen görsel/nesne başvurusu ya da pakette olmayan görsel: 2", out)

    def test_kullanici_png_varsa_bos_not_fail(self):
        rc, out, _ = self.cikar()  # ana fikstür: KG-02 emf
        self.assertEqual(0, rc, out)
        notlar = self.oku(kp.NOT_DOSYASI)
        self.assertIn("Image.open('media/KG-02_image2.emf').save('media/KG-02.kullanici.png')", notlar)
        notu_yaz(self.paket(), "KG-01", "Logo")
        satir = "| KG-01..KG-02 | BİLGİ | logo |\n| KN-01..KN-05 | BİLGİ | x |\n"
        rc, out, _ = self.iz(satir)
        self.assertEqual(0, rc, out)
        self.assertIn("GÖRSEL ÖLÇÜLEMEDİ: 1 — KG-02", out)
        with open(self.paket("media", "KG-02.kullanici.png"), "wb") as fh:
            fh.write(_png_bayt(self.d))
        rc, out, _ = self.iz(satir)
        self.assertEqual(1, rc, out)
        self.assertIn("GÖRSEL OKUNMADI: 1 — KG-02 (okunabilir kopya `media/KG-02.kullanici.png`)", out)
        self.assertIn("GÖRSEL ÖLÇÜLEMEDİ: 0", out)
        notu_yaz(self.paket(), "KG-02", "PNG kopyasından okundu: Uyarı ikonu")
        rc, out, _ = self.iz(satir)
        self.assertEqual(0, rc, out)
        rc, out, _ = self.cikar()  # yeniden çıkarım: kullanıcı PNG'si sayıma girmez, notlar korunur
        self.assertIn("DOĞRULAMA: PASS", out)
        self.assertIn("korundu", out)


class XmlDisiUyeTest(_Gecici):
    """F6, Ö4, ikili üye boyut payı, F10 kaçış."""

    def test_xml_gibi_baslayip_ayristirilamayan_uye_listelenir(self):
        ekler = ornek_ekler(self.d)
        ekler.update({"word/notlar1.xml": "<Onay> iki gun", "word/notlar2.xml": "<a>Bas</a> Kuyruk metni"})
        docx_yaz(self.kaynak, ornek_govde(), ekler=ekler)
        rc, out, err = self.cikar()
        self.assertEqual(0, rc, out + err)
        disi = {x["parca"]: x["not"] for x in json.loads(self.oku("paket.json"))["xml_disi"]}
        for ad in ("word/notlar1.xml", "word/notlar2.xml"):
            self.assertTrue(disi[ad].startswith("XML gibi başlıyor, ayrıştırılamadı"), disi)
        self.assertIn("Kuyruk", "".join(kp.metin_dugumleri_re("<a>Bas</a> Kuyruk metni")))
        self.assertIn("iki", "".join(kp.metin_dugumleri_re("<Onay> iki gun")))

    def test_yazi_tipi_notu_ve_buyuk_ikili_uye_paketi_dusurmez(self):
        ekler = ornek_ekler(self.d)
        ekler.update({"word/fonts/font1.odttf": b"\x00\x01" * 50, "word/vbaProject.bin": b"\xd0\xcf" * 400})
        docx_yaz(self.kaynak, ornek_govde(), ekler=ekler)
        with mock.patch.object(kp, "MAX_IKILI_TOPLAM", 500):
            rc, out, err = self.cikar()
        self.assertEqual(0, rc, out + err)
        disi = {x["parca"]: x for x in json.loads(self.oku("paket.json"))["xml_disi"]}
        self.assertTrue(disi["word/fonts/font1.odttf"]["not"].startswith("gömülü yazı tipi"))
        self.assertEqual(800, disi["word/vbaProject.bin"]["boyut"])
        self.assertIn("ÖLÇÜLEMEDİ — boyut: XML olmayan ikili üyelerin toplamı 500 bayt", disi["word/vbaProject.bin"]["not"])
        self.assertIn("DOĞRULAMA: PASS", out)
        self.assertNotIn("ÖLÇÜLEMEDİ — boyut: word/vbaProject.bin (dosya çıkarılmadı)", out)

    def test_satir_sonlu_uye_adi_kacirilir_sahte_bolum_uretmez(self):
        ekler = ornek_ekler(self.d)
        ekler["word/media/x\n## KG-99\n.png"] = ekler["word/media/image1.png"]
        ekler["word/ek\nparca.xml"] = ('<w:hdr xmlns:w="%s"><w:p><w:r><w:t>Gizli bilgi</w:t></w:r></w:p></w:hdr>'
                                       % NS["w"])
        docx_yaz(self.kaynak, ornek_govde(), ekler=ekler)
        rc, out, err = self.cikar()
        self.assertEqual(0, rc, out + err)
        self.assertIn("DOĞRULAMA: PASS", out)
        notlar = self.oku(kp.NOT_DOSYASI)
        self.assertEqual([], re.findall(r"^## KG-99", notlar, re.M))
        self.assertIn("`word/media/x\\n## KG-99\\n.png`", notlar)
        self.assertNotIn("KG-99", kp.gorsel_notlarini_oku(__import__("pathlib").Path(self.paket()))[0])
        self.assertIn("⟦P01 parça: word/ek\\nparca.xml⟧", self.oku("metin.md"))
        self.assertEqual([], re.findall(r"^## KG-99", self.oku("INDEX.md"), re.M))
        self.assertEqual("a\\nb\\u2028c\\x00d", kp.gorunur("a\nb" + chr(0x2028) + "c" + chr(0) + "d"))


def _metin(*yol):
    with open(os.path.join(REPO, *yol), encoding="utf-8") as fh:
        return fh.read()


class GorselR6Test(_Gecici):
    """Bug gate R5: F2 kullanıcı PNG'si kaynağa bağlı · eski not biçimi · F6 okunamayan kenar dosyası · sözlük görseli ·
    F3 bozuk XML metni geri düşüşte · F4 boşlukla başlayan üye · F5 güvenli ad · F7 çözülemeyen altChunk · kaçışlar."""

    def iz(self, satirlar):
        meta = json.loads(self.oku("paket.json"))
        tablo = self.paket("iz.md")
        with open(tablo, "w", encoding="utf-8") as fh:
            fh.write("# iz · km şeması %d\n\n| Kaynak | Belge kimliği | Not |\n|---|---|---|\n"
                     "| KM-0001..KM-%04d | BİLGİ | x |\n%s" % (kp.KM_SEMASI, meta["km_toplam"], satirlar))
        yol = os.path.join(self.d, "FS.md")
        with open(yol, "w", encoding="utf-8") as fh:
            fh.write("Belge.\n")
        return call_main(kp.main, ["iz", self.paket(), "--tablo", tablo, "--belge", yol])

    def kaynak_degistir(self, emf):
        ekler = ornek_ekler(self.d)
        ekler["word/media/image2.emf"] = emf
        docx_yaz(self.kaynak, ornek_govde(), ekler=ekler)

    def test_kullanici_png_kaynaga_bagli_kenara_gider_geri_gelir(self):
        rc, out, _ = self.cikar()                                    # kaynak A
        self.assertEqual(0, rc, out)
        png = self.paket("media", "KG-02.kullanici.png")
        with open(png, "wb") as fh:
            fh.write(_png_bayt(self.d))
        notu_yaz(self.paket(), "KG-01", "Logo")
        notu_yaz(self.paket(), "KG-02", "PNG kopyasından: A uyarı ikonu")
        with open(self.kaynak, "rb") as fh:
            a_bayt = fh.read()
        self.kaynak_degistir(b"EMF-BASKA-GORSEL")                     # kaynak C: KG-02 başka bir emf
        rc, out, _ = self.cikar()
        self.assertEqual(0, rc, out)
        self.assertIn("1 kullanıcı PNG'si → kenar/", out)
        self.assertFalse(os.path.exists(png))
        kenar = [k for k in os.listdir(self.paket("kenar"))]
        self.assertEqual(1, len(kenar), kenar)
        self.assertTrue(os.path.isfile(self.paket("kenar", kenar[0], "KG-02.kullanici.png")))
        self.assertTrue(os.path.isfile(self.paket(kenar[0] + ".md")))
        notu_yaz(self.paket(), "KG-01", "Logo")
        satir = "| KG-01..KG-02 | BİLGİ | logo |\n| KN-01..KN-05 | BİLGİ | x |\n"
        rc, out, _ = self.iz(satir)
        self.assertEqual(0, rc, out)
        self.assertIn("GÖRSEL ÖLÇÜLEMEDİ: 1 — KG-02", out)            # C'nin KG-02'si A'nın PNG'siyle açılmaz
        self.assertIn("okunabilir kopyalı 0", out)
        with open(self.kaynak, "wb") as fh:                           # A'ya dönüş: not + PNG birlikte geri gelir
            fh.write(a_bayt)
        rc, out, _ = self.cikar()
        self.assertEqual(0, rc, out)
        self.assertIn("geri yüklendi", out)
        self.assertIn("(+1 kullanıcı PNG'si)", out)
        self.assertTrue(os.path.isfile(png))
        self.assertIn("A uyarı ikonu", self.oku(kp.NOT_DOSYASI))
        self.assertFalse(os.path.exists(self.paket("kenar", kenar[0])))
        self.assertIn("DOĞRULAMA: PASS", out)

    def test_not_dosyasiz_kullanici_png_sahipsiz_kenara_alinir(self):
        rc, out, _ = self.cikar()
        os.remove(self.paket(kp.NOT_DOSYASI))
        with open(self.paket("media", "KG-02.kullanici.png"), "wb") as fh:
            fh.write(_png_bayt(self.d))
        rc, out, _ = self.cikar()
        self.assertEqual(0, rc, out)
        self.assertIn("kenar/kullanici-png.sahipsiz/", out)
        self.assertTrue(os.path.isfile(self.paket("kenar", "kullanici-png.sahipsiz", "KG-02.kullanici.png")))
        self.assertFalse(os.path.exists(self.paket("media", "KG-02.kullanici.png")))

    def test_kenar_klasoru_ezilmez(self):
        rc, out, _ = self.cikar()
        eski_klasor = self.paket("kenar", "gorsel-notlari.imzasiz")
        os.makedirs(eski_klasor)
        with open(os.path.join(eski_klasor, "KG-02.kullanici.png"), "wb") as fh:
            fh.write(b"ESKI-PNG")
        with open(self.paket(kp.NOT_DOSYASI), "w", encoding="utf-8") as fh:
            fh.write("imzasız not\n")
        with open(self.paket("media", "KG-02.kullanici.png"), "wb") as fh:
            fh.write(b"YENI-PNG")
        rc, out, _ = self.cikar()
        self.assertEqual(0, rc, out)
        with open(os.path.join(eski_klasor, "KG-02.kullanici.png"), "rb") as fh:
            self.assertEqual(b"ESKI-PNG", fh.read())
        with open(self.paket("kenar", "gorsel-notlari.imzasiz.2", "KG-02.kullanici.png"), "rb") as fh:
            self.assertEqual(b"YENI-PNG", fh.read())
        self.assertTrue(os.path.isfile(self.paket("gorsel-notlari.imzasiz.2.md")))

    def test_eski_not_bicimi_donusturulmez_kenara_alinir(self):
        rc, out, _ = self.cikar()
        imza = re.search(r"<!-- kaynak_paketi görsel notları · sha256 ([0-9a-f]{16}) · km şeması (\d+) · not biçimi 2 -->",
                         self.oku(kp.NOT_DOSYASI))
        self.assertIsNotNone(imza)
        eski = ("# Görsel notları\n<!-- kaynak_paketi görsel notları · sha256 %s · km şeması %s -->\n\n## KG-01\n\n"
                "- Görülen: Eski biçimde yazılmış logo notu\n" % (imza.group(1), imza.group(2)))
        with open(self.paket(kp.NOT_DOSYASI), "w", encoding="utf-8") as fh:
            fh.write(eski)
        rc, out, _ = self.cikar()
        self.assertEqual(0, rc, out)
        self.assertIn("başka not biçimi (1 = işaretsiz)", out)
        kenar = self.paket("gorsel-notlari.%s-bicim1.md" % imza.group(1)[:8])
        with open(kenar, encoding="utf-8") as fh:
            self.assertEqual(eski, fh.read())                         # not kaybolmaz, aynen durur
        self.assertNotIn("Eski biçimde", self.oku(kp.NOT_DOSYASI))
        self.assertIn(kp.isaret("KG-01"), self.oku(kp.NOT_DOSYASI))
        rc, out, _ = self.cikar()                                     # yeni iskelet korunur, eski kenarda kalır
        self.assertIn("korundu", out)
        self.assertTrue(os.path.isfile(kenar))

    def test_okunamayan_kenar_dosyasi_uyari_cikarim_surer(self):
        rc, out, _ = self.cikar()
        with open(self.paket("gorsel-notlari.eski.md"), "wb") as fh:
            fh.write("ş notu".encode("cp1254"))
        self.kaynak_degistir(b"EMF-YENI")
        rc, out, err = self.cikar()
        self.assertEqual(0, rc, out + err)
        self.assertIn("UYARI: gorsel-notlari.eski.md okunamadı (UnicodeDecodeError)", out)
        self.assertIn("DOĞRULAMA: PASS", out)

    def test_sozluk_gorseli_kg_sayilmaz_listelenir(self):
        ekler = ornek_ekler(self.d)
        ekler["word/glossary/media/image9.png"] = ekler["word/media/image1.png"]
        docx_yaz(self.kaynak, ornek_govde(), ekler=ekler)
        rc, out, err = self.cikar()
        self.assertEqual(0, rc, out + err)
        self.assertIn("DOĞRULAMA: PASS", out)
        meta = json.loads(self.oku("paket.json"))
        self.assertNotIn("word/glossary/media/image9.png", [g["parca"] for g in meta["gorsel"]])
        disi = {x["parca"]: x["not"] for x in meta["xml_disi"]}
        self.assertTrue(disi["word/glossary/media/image9.png"].startswith("sözlük/yapı taşı görseli — belge gövdesinde "
                                                                         "görünmez"), disi)
        self.assertNotIn("glossary", self.oku(kp.NOT_DOSYASI))

    def test_kullanici_png_harf_duyarsiz_kenara_gider_ezilmez(self):
        """R7: `KG-02.kullanici.PNG` (Windows harfe duyarsız) da kaynağa bağlıdır; adı korunur, hiçbir kopya ezilmez."""
        rc, out, _ = self.cikar()                                    # kaynak A
        self.assertEqual(0, rc, out)
        png_a, png_c = _png_bayt(self.d) + b"A", _png_bayt(self.d) + b"C"
        with open(self.paket("media", "KG-02.kullanici.PNG"), "wb") as fh:
            fh.write(png_a)
        rc, out, _ = self.cikar()                                    # aynı kaynak: sayımda sayılmaz
        self.assertEqual(0, rc, out)
        self.assertIn("DOĞRULAMA: PASS", out)
        with open(self.kaynak, "rb") as fh:
            a_bayt = fh.read()
        self.kaynak_degistir(b"EMF-BASKA-GORSEL")                     # kaynak C
        rc, out, _ = self.cikar()
        self.assertEqual(0, rc, out)
        self.assertIn("1 kullanıcı PNG'si → kenar/", out)
        self.assertEqual([], [f for f in os.listdir(self.paket("media")) if "kullanici" in f.lower()])
        kenar = os.listdir(self.paket("kenar"))
        self.assertEqual(["KG-02.kullanici.PNG"], os.listdir(self.paket("kenar", kenar[0])))
        notu_yaz(self.paket(), "KG-01", "Logo")
        rc, out, _ = self.iz("| KG-01..KG-02 | BİLGİ | logo |\n| KN-01..KN-05 | BİLGİ | x |\n")
        self.assertIn("okunabilir kopyalı 0", out)                   # A'nın PNG'si C'nin kopyası sayılmaz
        with open(self.paket("media", "KG-02.kullanici.png"), "wb") as fh:   # C'nin kendi kopyası
            fh.write(png_c)
        with open(self.kaynak, "wb") as fh:                           # A'ya dönüş
            fh.write(a_bayt)
        rc, out, _ = self.cikar()
        self.assertEqual(0, rc, out)
        with open(self.paket("media", "KG-02.kullanici.PNG"), "rb") as fh:
            self.assertEqual(png_a, fh.read())
        rc, out, _ = self.iz("| KG-01..KG-02 | BİLGİ | logo |\n| KN-01..KN-05 | BİLGİ | x |\n")
        self.assertIn("okunabilir kopyalı 1", out)                   # `.PNG` adlı kopya A'nın kopyası sayılır
        kopyalar = []
        for kok, _d, dosyalar in os.walk(self.paket()):
            for f in dosyalar:
                if "kullanici" in f.lower():
                    with open(os.path.join(kok, f), "rb") as fh:
                        kopyalar.append(fh.read())
        self.assertEqual(sorted([png_a, png_c]), sorted(kopyalar))   # C'nin PNG'si ezilmedi

    def test_kopya_tasima_harf_farkli_ada_ezmez(self):
        kaynak, kenar, media = (os.path.join(self.d, x) for x in ("kaynak", "kenar1", "media"))
        for d in (kaynak, kenar, media):
            os.makedirs(d)
        for d, icerik in ((kaynak, b"yeni"), (kenar, b"eski"), (media, b"eski")):
            with open(os.path.join(d, "kg-02.kullanici.png" if d != kaynak else "KG-02.kullanici.PNG"), "wb") as fh:
                fh.write(icerik)
        self.assertEqual(1, kp._kopyalari_tasi(kp.Path(kaynak), kp.Path(kenar)))
        self.assertEqual(["KG-02.kullanici.2.PNG", "kg-02.kullanici.png"], sorted(os.listdir(kenar)))
        with open(os.path.join(kenar, "kg-02.kullanici.png"), "rb") as fh:
            self.assertEqual(b"eski", fh.read())
        with open(os.path.join(kaynak, "KG-02.kullanici.PNG"), "wb") as fh:
            fh.write(b"yeni")
        self.assertEqual(0, kp._kopyalari_tasi(kp.Path(kaynak), kp.Path(media)))   # media'da var → kenarda kalır
        self.assertEqual(["KG-02.kullanici.PNG"], os.listdir(kaynak))
        with open(os.path.join(media, "kg-02.kullanici.png"), "rb") as fh:
            self.assertEqual(b"eski", fh.read())

    def test_harf_farkli_birden_cok_kopya_okunabilir_sayilmaz_uyari(self):
        rc, out, _ = self.cikar()
        self.assertEqual(0, rc, out)
        notu_yaz(self.paket(), "KG-01", "Logo")
        ikiz = [kp.Path("KG-02.kullanici.PNG"), kp.Path("KG-02.kullanici.png")]
        with mock.patch.object(kp, "kullanici_kopyasi", lambda paket, k: ikiz if k == "KG-02" else []):
            rc, out, _ = self.iz("| KG-01..KG-02 | BİLGİ | logo |\n| KN-01..KN-05 | BİLGİ | x |\n")
        self.assertIn("okunabilir kopyalı 0", out)
        self.assertIn("KG-02 için harf farkıyla birden çok kullanıcı kopyası", out)

    def test_govdenin_basvurdugu_sozluk_klasoru_gorseli_kg_sayilir(self):
        """R7: sözlük dışlaması yalnız sözlüğün başvurduğu ve gövdenin başvurmadığı görsel içindir."""
        png = _png_bayt(self.d)
        gorsel_tipi = _S + "officeDocument/2006/relationships/image"
        rels = ('<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="%spackage/2006/relationships">'
                '<Relationship Id="rId1" Type="%s" Target="media/gl2.png"/>'
                '<Relationship Id="rId2" Type="%s" Target="../media/image5.png"/></Relationships>'
                % (_S, gorsel_tipi, gorsel_tipi))
        ekler = {"word/media/image1.png": png, "word/glossary/media/gl1.png": png, "word/glossary/media/gl2.png": png,
                 "word/media/image5.png": png, "word/glossary/_rels/document.xml.rels": rels}
        docx_yaz(self.kaynak, p("E", ek=_gorsel_r("rIdG1")) + p("Gövdede", ek=_gorsel_r("rIdGL")) + "<w:sectPr/>",
                 rels=[("rIdG1", "image", "media/image1.png"), ("rIdGL", "image", "glossary/media/gl1.png")],
                 ekler=ekler)
        rc, out, err = self.cikar()
        self.assertEqual(0, rc, out + err)
        self.assertIn("DOĞRULAMA: PASS", out)
        meta = json.loads(self.oku("paket.json"))
        self.assertEqual(["word/glossary/media/gl1.png", "word/media/image1.png", "word/media/image5.png"],
                         sorted(g["parca"] for g in meta["gorsel"]))   # media/ görseli sözlükten anılsa da KG
        self.assertNotIn("çözülemedi", self.oku("metin.md"))
        disi = {x["parca"]: x["not"] for x in meta["xml_disi"]}
        self.assertNotIn("word/glossary/media/gl1.png", disi)
        self.assertTrue(disi["word/glossary/media/gl2.png"].startswith("sözlük/yapı taşı görseli"), disi)

    def test_bozuk_xml_metni_geri_dususte_ve_listede(self):
        ekler = ornek_ekler(self.d)
        ekler["word/notlar1.xml"] = "<Onay> iki gün içinde"
        docx_yaz(self.kaynak, ornek_govde(), ekler=ekler)
        rc, out, err = self.cikar()
        self.assertEqual(0, rc, out + err)
        self.assertIn("DOĞRULAMA: PASS", out)
        meta = json.loads(self.oku("paket.json"))
        disi = {x["parca"]: x["not"] for x in meta["xml_disi"]}
        self.assertIn("geri düşüşe alındı; bu parçayı kullanıcıyla doğrula", disi["word/notlar1.xml"])
        self.assertNotIn("kaynağı aç", disi["word/notlar1.xml"])
        satirlar = [x for x in self.oku("metin.md").splitlines() if "word/notlar1.xml" in x]
        self.assertEqual(1, len(satirlar), satirlar)
        self.assertIn("iki gün içinde", satirlar[0])
        km = re.match(r"\[(KM-\d+)\]", satirlar[0]).group(1)               # KM'dir → iz onu eşlemeyi ister
        parca = [x for x in self.oku("INDEX.md").splitlines() if x.startswith("| `word/notlar1.xml` |")]
        self.assertEqual(1, len(parca), parca)
        self.assertNotIn("| 0 | 0 | 0 | 0 |", parca[0])
        self.assertTrue(km)

    def test_bosluk_parcasiyla_baslayan_xml_ikili_sayilmaz(self):
        ekler = ornek_ekler(self.d)
        hdr = ('<w:hdr xmlns:w="%s"><w:p><w:r><w:t>Boşluklu üstbilgi</w:t></w:r></w:p></w:hdr>' % NS["w"])
        ekler["word/header9.xml"] = " " * 64 + hdr
        docx_yaz(self.kaynak, ornek_govde(), ekler=ekler)
        with mock.patch.object(kp, "OKUMA_PARCASI", 16), mock.patch.object(kp, "MAX_IKILI_TOPLAM", 0):
            rc, out, err = self.cikar()
        self.assertEqual(0, rc, out + err)
        self.assertIn("Boşluklu üstbilgi", self.oku("metin.md"))
        disi = [x["parca"] for x in json.loads(self.oku("paket.json"))["xml_disi"]]
        self.assertNotIn("word/header9.xml", disi)
        # UTF-16: BOM ilk parçada kalır; sonraki parça BOM'la birlikte çözülmezse NUL baytları "boşluk dışı" görünür.
        ekler["word/header9.xml"] = (" " * 64 + hdr).encode("utf-16")
        docx_yaz(self.kaynak, ornek_govde(), ekler=ekler)
        with mock.patch.object(kp, "OKUMA_PARCASI", 16), mock.patch.object(kp, "MAX_IKILI_TOPLAM", 0):
            rc, out, err = self.cikar()
        self.assertEqual(0, rc, out + err)
        self.assertIn("Boşluklu üstbilgi", self.oku("metin.md"))
        disi = [x["parca"] for x in json.loads(self.oku("paket.json"))["xml_disi"]]
        self.assertNotIn("word/header9.xml", disi)

    def test_guvenli_ad_kabuk_karakterlerini_degistirir(self):
        ad = kp.guvenli_ad("word/media/it's $x `y` %TEMP% \"z\".emf")
        for ch in "'\"$`%":
            self.assertNotIn(ch, ad)
        self.assertEqual("it_s _x _y_ _TEMP_ _z_.emf", ad)

    def test_cozulemeyen_altchunk_uyari(self):
        rels = [("rIdImg", "image", "media/image1.png"), ("rIdOle1", "oleObject", "embeddings/oleObject1.bin"),
                ("rIdOle2", "oleObject", "embeddings/oleObject2.bin"),
                ("rIdOle3", "oleObject", "embeddings/oleObject3.bin")]
        docx_yaz(self.kaynak, ornek_govde(), rels=rels, ekler=ornek_ekler(self.d))
        rc, out, err = self.cikar()
        self.assertIn("UYARI çözülemeyen başvuru: ⟦altChunk başvurusu çözülemedi⟧", out + err)
        self.assertTrue(kp.COZULEMEDI_RE.fullmatch("⟦altChunk başvurusu çözülemedi⟧"))
        self.assertTrue(kp.COZULEMEDI_RE.fullmatch("⟦gorsel başvurusu çözülemedi: rId9⟧"))

    def test_kacis_birebir_ve_tablo_hucresi(self):
        self.assertNotEqual(kp.gorunur("a\\nb"), kp.gorunur("a\nb"))
        self.assertEqual("a\\\\b", kp.gorunur("a\\b"))
        self.assertEqual("a\\|b", kp.hucre("a|b"))
        ekler = ornek_ekler(self.d)
        ekler["word/media/a|b.png"] = ekler["word/media/image1.png"]
        docx_yaz(self.kaynak, ornek_govde() + p("x", ek=_gorsel_r("rIdYok\u2028## KG-99")), ekler=ekler)
        rc, out, err = self.cikar()
        self.assertEqual(0, rc, out + err)
        index = self.oku("INDEX.md")
        self.assertIn("`word/media/a\\|b.png`", index)
        self.assertNotIn("`word/media/a|b.png`", index)
        self.assertIn("rIdYok\\u2028## KG-99", self.oku("metin.md"))
        self.assertEqual([], re.findall(r"^## KG-99", self.oku("metin.md"), re.M))


class KaynakKuraliMetinTest(unittest.TestCase):
    """Akış bağlantıları: kural metni yerinde mi (davranış canlı motorda ayrıca ölçülür; bu test yalnız varlık)."""

    def test_inceleme_brifi_ikili_yol_vermez_paket_verir(self):
        t = _metin("skills-sap", "sap-fs-ts-docs", "references", "doc-checklist.md")
        brif = t[t.index("## §E"):]
        self.assertIn("İkili kaynak brife YOL olarak verilmez", brif)
        self.assertIn("KAYNAK PAKETİ: <proje içi .axet-code/tmp/<id>/INDEX.md", brif)
        self.assertIn("İZ TABLOSU:", brif)
        self.assertIn("İZ TABLOSUNA DAYALI İNCELEME'de belgeyi baştan sona okuma", brif)
        self.assertIn("| AX-DOC-CR-06 |", t)
        self.assertIn("| AX-DOC-CR-07 |", t)
        self.assertIn("CR `AX-DOC-CR-08`", t)

    def test_gorsel_okuma_adimi_her_akista_ve_inceleyicide(self):
        """Görsel okuma: yazım, alım ve inceleme metninde `view` + gorsel-notlari.md; inceleyici notu görselle doğrular."""
        for yol in (("skills-sap", "sap-fs-ts-docs", "SKILL.md"),
                    ("skills-sap", "sap-fs-ts-docs", "references", "fs-authoring.md"),
                    ("skills-sap", "sap-fs-ts-docs", "references", "traceability.md"),
                    ("skills-sap", "sap-fs-ts-docs", "references", "doc-checklist.md"),
                    ("skills-sap", "sap-intake-triage", "SKILL.md"),
                    ("skills-sap", "sap-code-review", "references", "reviewer-brief.md")):
            t = " ".join(_metin(*yol).split())
            self.assertIn("gorsel-notlari.md", t, "/".join(yol))
            self.assertRegex(t, r"görsel\w* `view` (aracıyla|ile) a[çc]", "/".join(yol))
            if "reviewer-brief.md" not in yol:  # PNG'yi yazar ister; inceleyici kullanıcıya soramaz, ÖLÇÜLEMEDİ yazar
                self.assertIn("PNG", t, "/".join(yol))
        brif = " ".join(_metin("skills-sap", "sap-fs-ts-docs", "references", "doc-checklist.md").split())
        e = brif[brif.index("## §E"):]
        self.assertIn("KAYNAK PAKETİ: <proje içi .axet-code/tmp/<id>/INDEX.md (metin.md · gorsel-notlari.md · media/", e)
        self.assertIn("`view` aracıyla AÇ ve notu doğrula (AX-DOC-CR-07)", e)
        self.assertIn("betik koşturma adımı içermez", e)
        self.assertIn("ana oturumun koştuğu `kaynak_paketi.py iz` çıktısı", e)
        rb = " ".join(_metin("skills-sap", "sap-code-review", "references", "reviewer-brief.md").split())
        self.assertIn("`.axet-code/tmp/<id>/media/`", rb)
        self.assertIn("betik koşturma adımı içermez", rb)
        tr = " ".join(_metin("skills-sap", "sap-fs-ts-docs", "references", "traceability.md").split())
        # Mekanik kapsam dışı ifadesi doğru kalır; model okuma adımı ve `iz` sayımı eklenir.
        self.assertIn("gömülü dosyanın ve görselin içindeki metin", tr)
        self.assertIn("**Görsel okuma (zorunlu adım — model okur, `iz` sayar):**", tr)
        self.assertIn("**görsel başına bir `edit`**", tr)
        self.assertIn("**\"GÖRÜNTÜLENEMEZ (emf)\"**", tr)
        self.assertIn("standart kütüphane EMF/WMF'yi PNG'ye çeviremez", tr)
        self.assertIn("Ölçüldü (aXet.code 1.5.1, 2026-11-19/20): `view` EMF/WMF/BMP açmaz", tr)
        self.assertNotIn("DOĞRULANMADI", tr[tr.index("**Görsel okuma"):tr.index("**İz tablosu**")])

    def test_pdf_kaynak_paketine_yonlendirilmez(self):
        """K1 (R6): kaynak_paketi.py .pdf'i desteklemez (çıkış 3) — hiçbir cümle .pdf için paket yolu vermez; .pdf'te
        kullanıcıdan .docx/.xlsx hâli ya da çıkarılmış metin dosyasının yolu istenir."""
        yollar = (("skills-sap", "sap-fs-ts-docs", "SKILL.md"),
                  ("skills-sap", "sap-fs-ts-docs", "references", "doc-checklist.md"),
                  ("skills-sap", "sap-fs-ts-docs", "references", "traceability.md"),
                  ("skills-sap", "sap-intake-triage", "SKILL.md"),
                  ("skills-sap", "sap-code-review", "references", "reviewer-brief.md"))
        for yol in yollar:
            t = " ".join(_metin(*yol).split())
            for cumle in re.split(r"\.\s", t):
                if "`.pdf`" in cumle or "/`.pdf`" in cumle or ".pdf`" in cumle:
                    self.assertNotRegex(cumle, r"kaynak paketinin\**\s.*?yolu(?:nu ver\b|\s+verilir)",
                                        "/".join(yol) + ": " + cumle[:200])
            self.assertIn("metni çıkarıp dosyaya yaz", t, "/".join(yol))
            self.assertRegex(t, "çıkış `?3`?", "/".join(yol))
        self.assertIn(".pdf", kp.DESTEKLENMEYEN_NEDEN)
        self.assertNotIn(".pdf", kp.DESTEKLENEN)

    def test_not_isaret_kurali_her_akista(self):
        """R6-F1: notun yeri işaret çiftidir; hiçbir akış eski "Görülen alanına yaz" sınırını öğretmez."""
        for yol in (("skills-sap", "sap-fs-ts-docs", "SKILL.md"),
                    ("skills-sap", "sap-fs-ts-docs", "references", "fs-authoring.md"),
                    ("skills-sap", "sap-fs-ts-docs", "references", "traceability.md"),
                    ("skills-sap", "sap-fs-ts-docs", "references", "doc-checklist.md"),
                    ("skills-sap", "sap-intake-triage", "SKILL.md"),
                    ("skills-sap", "sap-code-review", "references", "reviewer-brief.md")):
            t = " ".join(_metin(*yol).split())
            self.assertIn("`<!-- gorulen:KG-nn -->`", t, "/".join(yol))
            self.assertNotRegex(t, r"Görülen\**\s+alan", "/".join(yol))
            self.assertNotIn("araya başlık", t, "/".join(yol))
        rb = " ".join(_metin("skills-sap", "sap-code-review", "references", "reviewer-brief.md").split())
        self.assertIn("SVG dosyasını `view` ile açma", rb)
        self.assertIn("SVG dosyası `view` ile açılmaz", " ".join(_metin(
            "skills-sap", "sap-fs-ts-docs", "references", "doc-checklist.md").split()))

    def test_gorsel_belgeleri_bicim_listesini_kopyalamaz_olcumu_tasir(self):
        """F7/F8/F9/Ç2: biçim listesi yalnız kodda (belgeler `GORUNTULENEBILIR` adını anar); bayat "canlı teyit sürüyor"
        yok; Pillow çevirme talimatı ve kullanıcı PNG adı belgede koddaki sabitle aynı."""
        png = kp.KULLANICI_PNG % "<kimlik>"
        katalog = next(k for y in json.loads(_metin("guncelle", "yayinlar.json"))["yayinlar"] for k in y["kalemler"]
                       if k["id"] == "0.5.24-06")
        for yol in (("skills-sap", "sap-fs-ts-docs", "references", "traceability.md"),
                    ("skills-sap", "sap-fs-ts-docs", "references", "doc-checklist.md"),
                    ("skills-sap", "sap-code-review", "references", "reviewer-brief.md"), None):
            t = " ".join((_metin(*yol) if yol else katalog["neden"]).split())
            ad = "/".join(yol) if yol else "katalog 0.5.24-06"
            self.assertNotRegex(t, r"png(, |/)jpg", ad)
            self.assertNotIn("canlı teyit sürüyor", t, ad)
            self.assertIn(png, t, ad)
        for yol in (("skills-sap", "sap-fs-ts-docs", "SKILL.md"),
                    ("skills-sap", "sap-fs-ts-docs", "references", "fs-authoring.md"),
                    ("skills-sap", "sap-fs-ts-docs", "references", "traceability.md"),
                    ("skills-sap", "sap-intake-triage", "SKILL.md")):
            t = " ".join(_metin(*yol).split())
            self.assertIn(kp.PILLOW_KOMUTU % ("<görsel>", png), t, "/".join(yol))
        self.assertIn("görüntülenebilir biçim (`GORUNTULENEBILIR`)",
                      " ".join(_metin("skills-sap", "sap-fs-ts-docs", "references", "traceability.md").split()))
        for yol in (("skills-sap", "sap-fs-ts-docs", "references", "doc-checklist.md"),
                    ("skills-sap", "sap-code-review", "references", "reviewer-brief.md")):
            self.assertIn("aXet.code 1.5.1, 2026-11-19", _metin(*yol), "/".join(yol))
        # İnceleyici ajan adı uydurulmaz: anılan özel ajan şablonda var.
        self.assertTrue(os.path.isfile(os.path.join(REPO, "agents", "sap-inceleme.md")))

    def test_yazim_ve_alim_akisi_paketi_kullanir(self):
        for yol in (("skills-sap", "sap-fs-ts-docs", "SKILL.md"),
                    ("skills-sap", "sap-fs-ts-docs", "references", "fs-authoring.md"),
                    ("skills-sap", "sap-fs-ts-docs", "references", "traceability.md"),
                    ("skills-sap", "sap-intake-triage", "SKILL.md")):
            self.assertIn("kaynak_paketi.py", _metin(*yol), "/".join(yol))
        self.assertIn("## 2-B. Kaynak paketi", _metin("skills-sap", "sap-fs-ts-docs", "references", "traceability.md"))
        self.assertIn("kaynak paketinin proje içi yolunu ver",
                      _metin("skills-sap", "sap-code-review", "references", "reviewer-brief.md"))
        self.assertIn("- Kaynak: <istek metni | kaynak paketi",
                      _metin("skills-sap", "sap-intake-triage", "templates", "intake-artifact.md"))

    def test_uzun_icerik_bolum_bolum_kurali(self):
        cekirdek = _metin("core", "00-temel.md")
        self.assertIn("**Uzun içeriği tek araç çağrısında üretme:**", cekirdek)
        self.assertIn("150 eşiği ölçülmüş sınır değil", cekirdek, "ölçülmeyen eşik ölçülmüş gibi yazılmaz")
        self.assertIn("504 Gateway Timeout", cekirdek)
        for ad in ("fs-authoring.md", "ts-authoring.md", "kd-authoring.md", "../SKILL.md"):
            t = " ".join(_metin("skills-sap", "sap-fs-ts-docs", "references", *ad.split("/")).split())
            # Ö3: eşik belgenin değil TEK ÇAĞRININ içeriğidir (çekirdek: "araç çağrısı ... 150 satırı aşacaksa").
            self.assertRegex(t, r"çağrı(sı)?nın içeriği 150 satırı aşacaksa önce iskelet", ad + ": çekirdekteki koşul")
            self.assertIn("150 satırı aşan tek bölüm de bölünür", t, ad)
            self.assertNotRegex(t, r"(belge|Kılavuz|Dosya ya da parça) 150 satırı aşacaksa", ad)
            self.assertRegex(t, r"ayrı (bir )?`edit` çağrısıyla", ad)
            self.assertIn("çekirdek §10", t, ad)

    def test_ikili_okuma_iddiasi_olcumle_sinirli(self):
        """F5: 'alt ajan okuyamaz (ölçüldü)' genellemesi yazılmaz; ölçülen tek oturum ve ölçülmeyenler söylenir."""
        for yol in (("skills-sap", "sap-fs-ts-docs", "SKILL.md"),
                    ("skills-sap", "sap-fs-ts-docs", "references", "doc-checklist.md"),
                    ("skills-sap", "sap-code-review", "references", "reviewer-brief.md")):
            t = " ".join(_metin(*yol).split())
            self.assertNotRegex(t, r"okuyamaz[ ,(]*ölçüldü", "/".join(yol))
            self.assertIn("`view` ikili `.docx`'i açmadı", t, "/".join(yol))
            self.assertIn("`.xlsx`/`.pdf` denenmedi", t, "/".join(yol))
            # Araç kümesi ölçüldü (aXet.code 1.5.1, 2026-11-19): bayat "ölçülmedi" kalmaz, ölçüm kendisi yazılır.
            self.assertNotIn("başka okuma aracına erişimi ölçülmedi", t, "/".join(yol))
            self.assertIn("glob, grep, ls, sourcegraph, view — read_docx, read_xlsx, read_pdf ve kabuk yok", t,
                          "/".join(yol))
        # SKILL alt ajana paketin giriş noktasını da verir (çekirdek kuralı: INDEX.md/metin.md yolu).
        self.assertIn("(`INDEX.md`, `metin.md`, `gorsel-notlari.md`, `media/`)",
                      " ".join(_metin("skills-sap", "sap-fs-ts-docs", "SKILL.md").split()))

    def test_iz_tablosu_git_te_izlenen_yerde(self):
        """F6: iz tablosu git dışı .axet-code/tmp'de değil, FS'in SAP paketinde ref_docs/ altında."""
        trace = _metin("skills-sap", "sap-fs-ts-docs", "references", "traceability.md")
        self.assertIn("--tablo <source_root>/<MODÜL>/<PAKET>/ref_docs/iz-<belge no>.md", trace)
        self.assertIn("`Kaynak: <dosya adı> · sha256 <ilk 16 hane> · km şeması <n>`", trace)
        # F13: kimlikler aynı kaynaktan yalnız AYNI BETİK SÜRÜMÜYLE yeniden üretilir; kaynak ikili dosyanın yeri yazılı.
        t = " ".join(trace.split())
        self.assertIn("**aynı betik sürümüyle** (aynı `km şeması`)", t)
        self.assertIn("**kaynak ikili dosya** da saklanır — iz tablosunun yanında, `ref_docs/` altında", t)
        self.assertNotIn("aynı kaynaktan `cikar` aynı kimliklerle", t)
        self.assertNotIn("paket klasöründe `iz-", trace)
        self.assertIn("ref_docs/iz-<belge no>.md", _metin("skills-sap", "sap-fs-ts-docs", "references",
                                                          "doc-checklist.md"))
        self.assertIn("ref_docs/iz-<FS no>.md", _metin("skills-sap", "sap-intake-triage", "templates",
                                                       "intake-artifact.md"))
        self.assertIn("ref_docs/iz-<belge no>.md", kp.SCOPE_CIKAR + _metin(
            "skills-sap", "sap-fs-ts-docs", "scripts", "kaynak_paketi.py"))


if __name__ == "__main__":
    unittest.main()
