# -*- coding: utf-8 -*-
"""XDP şablonunu (ve istenirse örnek veri XML'ini) ABAP metoduna çevirir; önce BAĞLAMA SİMÜLASYONU yapar.

Kullanım:
    python xdp_abap_uret.py --xdp sablon.xdp --veri ornek.xml --abap ZCL_X.clas.abap [--veri-gom] [--check]

- Simülasyon: şablondaki her `<bind match="dataRef" ref="…">` örnek veride çözülür. Çözülemeyen = HATA (yazılmaz),
  hiçbir alana bağlanmayan veri yaprağı = UYARI.
- Üretim: `METHOD get_xdp.` (ve `--veri-gom` ile `METHOD get_veri.`) gövdesi `rv_xml = rv_xml && `…` && nl.`
  satırlarıyla; ters tırnak ikilenir, ABAP satırı ≤ 255 karakter (uzun satır parçalanır).
- Blok işaret satırları arasında durur (`" >>> URETILDI: <metot>` … `" <<< URETILDI: <metot>`). `--abap` dosyası
  varsa yalnız işaretli bloklar değişir; yoksa yalnız bloklardan oluşan yeni dosya yazılır.
- `--check`: hiçbir şey yazmaz; dosyadaki bloklar `.xdp`/veri ile güncel mi söyler.

Çıkış: 0 tamam/güncel · 1 bağlama HATASI ya da BAYAT blok · 2 kullanım/girdi hatası.
SAP'ye bağlanmaz; yalnız Python standart kütüphanesi.
"""
import argparse
import hashlib
import os
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _xdp_ortak as ortak  # noqa: E402

ABAP_SATIR_SINIRI = 255
GIRINTI = "  "
KAPSAM = ("KAPSAM: bakılanlar — şablondaki subform/field `bind` öğeleri (dataRef: `$record.…`, `$.…`, `$`, `[*]`, `[n]`; "
          "match=\"none\"; adsız subform; adlı + bind'siz subform/alan uyarısı) ve örnek verinin eleman yaprakları. "
          "BAKILMAYANLAR: veri öznitelikleri · `match=\"global\"`/`once` ad eşlemesinin gerçek davranışı (yalnız uyarılır) · "
          "`$data`/`!`/`..` gibi diğer SOM biçimleri (SİMÜLE EDİLMEDİ diye listelenir) · render, sayfa kırılımı, betikler. "
          "Simülasyon ADS DEĞİLDİR: 'bağlama hatası 0' PDF'in doğru çıkacağını söylemez.")

_SEGMENT = re.compile(r"^([A-Za-z_][\w-]*)(?:\[(\*|\d+)\])?$")
_KAP_TURLERI = ("subformSet", "area", "pageSet", "pageArea", "exclGroup")


class Bulgular:
    def __init__(self):
        self.hata, self.uyari, self.bilgi = [], [], []


def _ref_coz(ref, baglam, veri_kok):
    """Döner: (düğüm listesi, tekrar_mi) ya da desteklenmeyen biçimde None."""
    ref = ref.strip()
    if ref.startswith("$record"):
        bas, kalan = veri_kok, ref[len("$record"):]
    elif ref.startswith("$"):
        bas, kalan = baglam, ref[1:]
    else:
        return None
    if kalan == "":
        return [bas], False
    if not kalan.startswith("."):
        return None
    dugumler, tekrar = [bas], False
    for seg in kalan[1:].split("."):
        m = _SEGMENT.match(seg)
        if not m:
            return None
        ad, idx = m.group(1), m.group(2)
        sonraki = []
        for d in dugumler:
            esler = d.cocuk(ad)
            if idx == "*":
                sonraki.extend(esler)
            elif idx is not None:
                n = int(idx)
                if n < len(esler):
                    sonraki.append(esler[n])
            elif esler:
                sonraki.append(esler[0])
        if idx == "*":
            tekrar = True
        dugumler = sonraki
    return dugumler, tekrar


def _veri_yolu(d):
    parcalar = []
    while d is not None:
        parcalar.append(d.ad)
        d = d.ata
    return "/".join(reversed(parcalar))


def _tekrarli_occur(sf):
    occ = sf.ilk("occur")
    if occ is None:
        return False
    return occ.oz.get("max", "1").strip() != "1"


def bagla_simule(sablon, veri_kok):
    """Şablon (template Dugum) + veri kökü → Bulgular. Yan etki yok."""
    b = Bulgular()
    tuketilen = set()
    kok_sf = sablon.ilk("subform")
    if kok_sf is None:
        b.hata.append("şablonda kök subform yok")
        return b, tuketilen
    kok_ad = kok_sf.oz.get("name")
    if kok_ad and kok_ad != veri_kok.ad:
        b.hata.append("satır %d: kök subform adı '%s' ama veri kökü '<%s>' — kök adları aynı olmalı"
                      % (kok_sf.satir, kok_ad, veri_kok.ad))

    def alan(f, baglamlar):
        bind = f.ilk("bind")
        yer = "satır %d %s" % (f.satir, ortak.yol_adi(f))
        if bind is None:
            if f.oz.get("name"):
                b.uyari.append("%s: adlı alan bind'siz — ad eşlemesi yapar, simüle edilmedi; açık `bind` ver" % yer)
            return
        match = bind.oz.get("match", "once")
        if match == "none":
            return
        if match != "dataRef":
            b.uyari.append("%s: bind match=\"%s\" SİMÜLE EDİLMEDİ" % (yer, match))
            return
        ref = bind.oz.get("ref", "")
        toplam = 0
        for bg in baglamlar:
            sonuc = _ref_coz(ref, bg, veri_kok)
            if sonuc is None:
                b.uyari.append("%s: ref=\"%s\" biçimi SİMÜLE EDİLMEDİ" % (yer, ref))
                return
            for d in sonuc[0]:
                toplam += 1
                tuketilen.add(id(d))
                if d.cocuklar:
                    b.uyari.append("%s: ref=\"%s\" alt elemanı olan veri düğümüne bağlı (%s)" % (yer, ref, _veri_yolu(d)))
        if toplam == 0:
            b.hata.append("%s: ref=\"%s\" örnek veride ÇÖZÜLEMEDİ (bağlam: %s)"
                          % (yer, ref, ", ".join(sorted({_veri_yolu(x) for x in baglamlar})) or "boş"))

    def subform(sf, baglamlar):
        bind = sf.ilk("bind")
        yer = "satır %d %s" % (sf.satir, ortak.yol_adi(sf))
        yeni = baglamlar
        if bind is None:
            if sf.oz.get("name") and sf is not kok_sf:
                b.uyari.append("%s: adlı subform bind'siz — ad eşlemesi bağlamı kaydırabilir (simüle edilmedi); "
                               "açık `bind` ya da `<bind match=\"none\"/>` ver" % yer)
        else:
            match = bind.oz.get("match", "once")
            if match == "dataRef":
                ref = bind.oz.get("ref", "")
                yeni, tekrar, desteksiz = [], False, False
                for bg in baglamlar:
                    sonuc = _ref_coz(ref, bg, veri_kok)
                    if sonuc is None:
                        desteksiz = True
                        break
                    yeni.extend(sonuc[0])
                    tekrar = tekrar or sonuc[1]
                if desteksiz:
                    b.uyari.append("%s: ref=\"%s\" biçimi SİMÜLE EDİLMEDİ — alt bağlar denetlenmedi" % (yer, ref))
                    return
                if not yeni:
                    b.hata.append("%s: ref=\"%s\" örnek veride ÇÖZÜLEMEDİ — alt bağlar denetlenmedi" % (yer, ref))
                    return
                tekrarli = _tekrarli_occur(sf)
                if tekrar and not tekrarli:
                    b.uyari.append("%s: ref `[*]` ama `<occur max>` yok ya da 1 — tekrarlı subform için ikisi birlikte "
                                   "gerekir (reçete: bağlama kuralları)" % yer)
                elif tekrarli and not tekrar:
                    b.uyari.append("%s: `<occur>` tekrarlı ama ref `[*]` değil — her veri örneği bir kopya olmaz" % yer)
            elif match != "none":
                b.uyari.append("%s: bind match=\"%s\" SİMÜLE EDİLMEDİ — alt bağlar mevcut bağlamla denetlendi" % (yer, match))
        gez(sf, yeni)

    def gez(dugum, baglamlar):
        for c in dugum.cocuklar:
            if c.ad == "subform":
                subform(c, baglamlar)
            elif c.ad == "field":
                alan(c, baglamlar)
            elif c.ad in _KAP_TURLERI:
                if c.ad == "exclGroup" and c.ilk("bind") is not None and c.ilk("bind").oz.get("match") not in (None, "none"):
                    b.uyari.append("satır %d: exclGroup bind'i SİMÜLE EDİLMEDİ" % c.satir)
                gez(c, baglamlar)

    gez(kok_sf, [veri_kok])

    yapraklar = {}
    for d in veri_kok.torunlar():
        if not d.cocuklar and id(d) not in tuketilen:
            yapraklar.setdefault(_veri_yolu(d), []).append(d.satir)
    for yol, satirlar in sorted(yapraklar.items()):
        b.uyari.append("veri yaprağı hiçbir alana bağlanmıyor: %s (veri satırı %s%s)"
                       % (yol, satirlar[0], ", %d örnek" % len(satirlar) if len(satirlar) > 1 else ""))
    return b, tuketilen


# ----------------------------------------------------------------------------------------------- ABAP üretimi

def _abap_uzunluk(s):
    return len(s.encode("utf-16-le")) // 2


def _kac(s):
    return s.replace("`", "``")


def _parcala(satir, sigan):
    """Ham satırı, KAÇIŞLI uzunluğu `sigan`ı aşmayan parçalara böler (ikilenmiş tırnak bölünmez)."""
    parcalar, cur, cur_len = [], [], 0
    for ch in satir:
        u = _abap_uzunluk(_kac(ch))
        if cur and cur_len + u > sigan:
            parcalar.append("".join(cur))
            cur, cur_len = [], 0
        cur.append(ch)
        cur_len += u
    if cur or not parcalar:
        parcalar.append("".join(cur))
    return parcalar


def abap_blok(metin, metot, kaynak_adi):
    metin = metin.replace("\r\n", "\n").replace("\r", "\n")
    satirlar = metin.split("\n")
    son_nl = satirlar and satirlar[-1] == ""
    if son_nl:
        satirlar = satirlar[:-1]
    ozet = hashlib.sha256(metin.encode("utf-8")).hexdigest()[:12]
    g2 = GIRINTI * 2
    on = g2 + "rv_xml = rv_xml && `"
    son = "` && nl."
    sigan = ABAP_SATIR_SINIRI - _abap_uzunluk(on) - len(son)
    baslik = '%s" >>> URETILDI: %s — xdp_abap_uret.py; elle düzenlenmez. Kaynak: %s sha256:%s'
    while _abap_uzunluk(baslik % (GIRINTI, metot, kaynak_adi, ozet)) > ABAP_SATIR_SINIRI and len(kaynak_adi) > 8:
        kaynak_adi = "…" + kaynak_adi[-(len(kaynak_adi) - 2):]
    out = [baslik % (GIRINTI, metot, kaynak_adi, ozet),
           "%sMETHOD %s." % (GIRINTI, metot),
           "%sDATA(nl) = cl_abap_char_utilities=>newline." % g2,
           "%srv_xml = ``." % g2]
    for i, satir in enumerate(satirlar):
        nl_ekle = son_nl or i < len(satirlar) - 1
        if satir == "":
            if nl_ekle:
                out.append("%srv_xml = rv_xml && nl." % g2)
            continue
        parcalar = _parcala(satir, sigan)
        for j, p in enumerate(parcalar):
            sonuncu = j == len(parcalar) - 1
            out.append(on + _kac(p) + ("` && nl." if (sonuncu and nl_ekle) else "`."))
    out.append("%sENDMETHOD." % GIRINTI)
    out.append('%s" <<< URETILDI: %s' % (GIRINTI, metot))
    for s in out:
        if _abap_uzunluk(s) > ABAP_SATIR_SINIRI:
            raise ValueError("üretilen satır %d karakter (> %d): %s…" % (_abap_uzunluk(s), ABAP_SATIR_SINIRI, s[:60]))
    return out


_BAS = re.compile(r'^\s*" >>> URETILDI: (\S+)')
_SON = re.compile(r'^\s*" <<< URETILDI: (\S+)')


def bloklari_bul(satirlar):
    """Döner: {metot: (bas, son)} ; bozuk/çift işaret → ValueError."""
    bloklar, acik = {}, None
    for i, s in enumerate(satirlar):
        m = _BAS.match(s)
        if m:
            if acik is not None:
                raise ValueError("satır %d: '%s' bloğu kapanmadan yeni blok açıldı" % (i + 1, acik[0]))
            acik = (m.group(1), i)
            continue
        m = _SON.match(s)
        if m:
            if acik is None or acik[0] != m.group(1):
                raise ValueError("satır %d: eşsiz kapanış işareti '%s'" % (i + 1, m.group(1)))
            if acik[0] in bloklar:
                raise ValueError("'%s' bloğu iki kez var" % acik[0])
            bloklar[acik[0]] = (acik[1], i)
            acik = None
    if acik is not None:
        raise ValueError("'%s' bloğu kapanmamış" % acik[0])
    return bloklar


def _norm(satirlar):
    return [s.strip() for s in satirlar]


def main(argv=None):
    ap = argparse.ArgumentParser(description="XDP → ABAP metodu (bağlama simülasyonlu)")
    ap.add_argument("--xdp", required=True)
    ap.add_argument("--veri", required=True, help="örnek veri XML'i (simülasyon için ZORUNLU)")
    ap.add_argument("--abap", required=True, help="yazılacak/denetlenecek ABAP dosyası")
    ap.add_argument("--veri-gom", action="store_true", help="örnek veriyi de get_veri metodu olarak göm (deneme sınıfı)")
    ap.add_argument("--xdp-metot", default="get_xdp")
    ap.add_argument("--veri-metot", default="get_veri")
    ap.add_argument("--check", action="store_true", help="yazma; ABAP dosyası güncel mi denetle")
    try:
        a = ap.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    print(KAPSAM)
    try:
        with open(a.xdp, encoding="utf-8-sig") as fh:
            xdp_metin = fh.read()
        with open(a.veri, encoding="utf-8-sig") as fh:
            veri_metin = fh.read()
        sablon = ortak.sablonu_bul(ortak.ayristir(xdp_metin))
        veri_kok = ortak.ayristir(veri_metin)
    except (OSError, UnicodeDecodeError, ortak.XmlHatasi) as exc:
        print("HATA: girdi okunamadı: %s" % exc, file=sys.stderr)
        return 2
    if sablon is None:
        print("HATA: %s içinde XFA `template` öğesi yok" % a.xdp, file=sys.stderr)
        return 2

    b, _ = bagla_simule(sablon, veri_kok)
    for s in b.hata:
        print("HATA bağlama: " + s)
    for s in b.uyari:
        print("UYARI bağlama: " + s)
    if "\t" in xdp_metin:
        print("UYARI: XDP'de sekme karakteri var — ABAP literalindeki davranışı DOĞRULANMADI; boşluğa çevir")
    print("BAĞLAMA: hata %d · uyarı %d" % (len(b.hata), len(b.uyari)))

    try:
        bloklar = {a.xdp_metot: abap_blok(xdp_metin, a.xdp_metot, os.path.basename(a.xdp))}
        if a.veri_gom:
            bloklar[a.veri_metot] = abap_blok(veri_metin, a.veri_metot, os.path.basename(a.veri))
    except ValueError as exc:  # ör. 255'i aşan başlık/metot adı — girdi hatası, bayat değil
        print("HATA: ABAP üretilemedi: %s" % exc, file=sys.stderr)
        return 2

    if a.check:
        if not os.path.isfile(a.abap):
            print("HATA: %s yok" % a.abap, file=sys.stderr)
            return 2
        try:
            with open(a.abap, encoding="utf-8") as fh:
                mevcut = fh.read().split("\n")
        except (OSError, UnicodeDecodeError) as exc:
            print("HATA: %s okunamadı (UTF-8 bekleniyor): %s" % (a.abap, exc), file=sys.stderr)
            return 2
        try:
            yerler = bloklari_bul(mevcut)
        except ValueError as exc:
            print("HATA: işaretler bozuk: %s" % exc, file=sys.stderr)
            return 2
        bayat = 0
        for metot, blok in bloklar.items():
            if metot not in yerler:
                print("BAYAT: %s — dosyada '%s' bloğu yok" % (a.abap, metot))
                bayat += 1
                continue
            bas, son = yerler[metot]
            if _norm(mevcut[bas:son + 1]) == _norm(blok):
                print("GÜNCEL: %s" % metot)
            else:
                print("BAYAT: %s — kaynak dosyadan farklı; yeniden üret" % metot)
                bayat += 1
        for metot in sorted(set(yerler) - set(bloklar)):
            # Dosyada üretilmiş bir blok var ama bu koşu onu üretmedi (ör. --veri-gom verilmedi) ⇒
            # denetlenmeyen blok "güncel" sayılmaz (gate bulgusu: get_veri sessizce atlanıyordu).
            print("DENETLENMEDİ: %s — dosyada üretilmiş blok var ama bu koşu üretmedi "
                  "(veri bloğuysa --veri-gom ile koş)" % metot)
            bayat += 1
        print("NOT: karşılaştırma satır başı/sonu boşluklarını yok sayar; SAP pretty printer'ın harf değişikliği BAYAT görünür.")
        return 1 if (bayat or b.hata) else 0

    if b.hata:
        print("YAZILMADI: bağlama hatası var — önce şablonu ya da örnek veriyi düzelt.", file=sys.stderr)
        return 1
    if os.path.isfile(a.abap):
        try:
            with open(a.abap, encoding="utf-8") as fh:
                mevcut = fh.read().split("\n")
        except (OSError, UnicodeDecodeError) as exc:
            print("HATA: %s okunamadı (UTF-8 bekleniyor): %s" % (a.abap, exc), file=sys.stderr)
            return 2
        try:
            yerler = bloklari_bul(mevcut)
        except ValueError as exc:
            print("HATA: işaretler bozuk: %s" % exc, file=sys.stderr)
            return 2
        eksik = [m for m in bloklar if m not in yerler]
        if eksik:
            print("HATA: %s içinde işaretli blok yok: %s — dosyaya `\" >>> URETILDI: <metot>` / "
                  "`\" <<< URETILDI: <metot>` satırlarını koy ya da yeni dosya adı ver (var olan dosya ezilmez)"
                  % (a.abap, ", ".join(eksik)), file=sys.stderr)
            return 2
        for metot in sorted(bloklar, key=lambda m: yerler[m][0], reverse=True):
            bas, son = yerler[metot]
            mevcut[bas:son + 1] = bloklar[metot]
        yeni = "\n".join(mevcut)
    else:
        yeni = "\n\n".join("\n".join(bl) for bl in bloklar.values()) + "\n"
    with open(a.abap, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(yeni)
    print("YAZILDI: %s (%s)" % (a.abap, ", ".join("%s %d satır" % (m, len(bl)) for m, bl in bloklar.items())))
    return 0


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    sys.exit(main())
