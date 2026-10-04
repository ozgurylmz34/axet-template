# -*- coding: utf-8 -*-
"""Deneme classrun çıktısındaki base64 PDF'i çözer, yazar ve sayfa sayısını `ev_pages` ile kıyaslar.

Kullanım:
    python pdf_coz.py <classrun çıktısı (.txt ya da CLI JSON'u)> --pdf cikti.pdf

Girdi: deneme sınıfı şablonunun yazdığı satırlar —
    EV_PAGES=<n> · PDF_BAYT=<n> · ADS_IZ_BASI=<…>
    >>>PDF-BASE64-BASLA<<<
    <sabit uzunluklu base64 satırları>
    >>>PDF-BASE64-BITTI<<<
`sap_adt_cli.py adt_classrun` JSON'u verilirse `output` alanı okunur.

Sayfa sayısı yalnız `pypdf` kuruluysa sayılır; değilse ÖLÇÜLEMEDİ yazılır. Ham `/Type /Page` regex'i KULLANILMAZ:
ADS sayfa nesnelerini sıkıştırılmış nesne akışına koyar, regex 0 verir (çekirdekte ölçüldü).
Bu araç PDF'in DOĞRU göründüğünü söylemez — PDF'i açıp gözle oku.

Çıkış: 0 tamam · 1 uyuşmazlık (sayfa ya da bayt `EV_PAGES`/`PDF_BAYT`'tan farklı) · 2 girdi hatası.
"""
import argparse
import base64
import binascii
import io
import json
import re
import sys

sys.dont_write_bytecode = True

BASLA = ">>>PDF-BASE64-BASLA<<<"
BITTI = ">>>PDF-BASE64-BITTI<<<"


class GirdiHatasi(Exception):
    pass


def metni_al(ham):
    """Düz metin ya da {'output': …} JSON'u → çıktı metni."""
    s = ham.lstrip()
    if s.startswith("{"):
        try:
            veri = json.loads(s)
        except ValueError:
            return ham
        if isinstance(veri, dict) and isinstance(veri.get("output"), str):
            return veri["output"]
        if isinstance(veri, dict) and isinstance(veri.get("result"), dict) and isinstance(veri["result"].get("output"), str):
            return veri["result"]["output"]
        raise GirdiHatasi("JSON girdi `output` alanı taşımıyor")
    return ham


def ayikla(metin):
    """Döner: (base64 satırları, {anahtar: değer}). İşaret yoksa/çiftse GirdiHatasi."""
    satirlar = [s.strip() for s in metin.replace("\r\n", "\n").split("\n")]
    bas = [i for i, s in enumerate(satirlar) if s == BASLA]
    son = [i for i, s in enumerate(satirlar) if s == BITTI]
    if not bas and not son:
        raise GirdiHatasi("başlangıç/bitiş işaretleri (%s / %s) yok — deneme sınıfı PDF'i yazmadı mı? "
                          "(render istisnası ise çıktıdaki HATA/ADS_IZ satırlarına bak)" % (BASLA, BITTI))
    if len(bas) != 1 or len(son) != 1:
        raise GirdiHatasi("işaretler tek değil (başla %d · bitti %d) — çıktı kesilmiş ya da iki koşu birleşmiş"
                          % (len(bas), len(son)))
    if son[0] < bas[0]:
        raise GirdiHatasi("bitiş işareti başlangıçtan önce")
    govde = [s for s in satirlar[bas[0] + 1:son[0]] if s]
    if not govde:
        raise GirdiHatasi("işaretler arasında base64 yok")
    meta = {}
    for s in satirlar:
        m = re.match(r"^(EV_PAGES|PDF_BAYT|ADS_IZ_BASI)=(.*)$", s)
        if m:
            meta[m.group(1)] = m.group(2)
    return govde, meta


def coz(govde):
    uzunluklar = {len(s) for s in govde[:-1]}
    uyari = None
    if len(uzunluklar) > 1:
        uyari = "base64 satır uzunlukları tutarsız (%s) — konsol satırları sarmış ya da kesilmiş olabilir" % sorted(uzunluklar)
    try:
        pdf = base64.b64decode("".join(govde), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise GirdiHatasi("base64 çözülemedi: %s" % exc) from None
    if not pdf.startswith(b"%PDF-"):
        raise GirdiHatasi("çözülen veri PDF değil (ilk baytlar %r)" % pdf[:8])
    return pdf, uyari


def sayfa_say(pdf):
    """pypdf ile sayar. Döner: (sayı ya da None, açıklama)."""
    try:
        import pypdf  # noqa: WPS433
    except ImportError:
        return None, "ÖLÇÜLEMEDİ (pypdf kurulu değil; ham `/Type /Page` sayımı hüküm DEĞİLDİR)"
    try:
        return len(pypdf.PdfReader(io.BytesIO(pdf)).pages), "pypdf"
    except Exception as exc:  # pypdf bozuk PDF'te çeşitli istisnalar atar
        return None, "ÖLÇÜLEMEDİ (pypdf okuyamadı: %s)" % exc


def main(argv=None):
    ap = argparse.ArgumentParser(description="classrun çıktısındaki base64 PDF'i çöz")
    ap.add_argument("girdi", help="classrun çıktısı dosyası ('-' = stdin)")
    ap.add_argument("--pdf", required=True, help="yazılacak PDF yolu")
    try:
        a = ap.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    print("KAPSAM: işaretler arası base64 → PDF · `%PDF-` imzası · bayt ve sayfa (`pypdf`) kıyası. BAKILMAYANLAR: "
          "yerleşim, taşma, glif, barkod okunurluğu — PDF'i aç ve gözle oku (AF-XDP-06).")
    try:
        if a.girdi == "-":
            ham = sys.stdin.read()
        else:
            with open(a.girdi, encoding="utf-8-sig", errors="strict") as fh:
                ham = fh.read()
        govde, meta = ayikla(metni_al(ham))
        pdf, uyari = coz(govde)
    except (OSError, UnicodeDecodeError, GirdiHatasi) as exc:
        print("HATA: %s" % exc, file=sys.stderr)
        return 2
    with open(a.pdf, "wb") as fh:
        fh.write(pdf)
    uyusmazlik = 0
    print("YAZILDI: %s (%d bayt)" % (a.pdf, len(pdf)))
    if uyari:
        print("UYARI: " + uyari)
    if "PDF_BAYT" in meta:
        try:
            beklenen = int(meta["PDF_BAYT"].strip().replace(".", ""))
        except ValueError:
            beklenen = None
        if beklenen is None:
            print("UYARI: PDF_BAYT okunamadı: %r" % meta["PDF_BAYT"])
        elif beklenen != len(pdf):
            print("UYUŞMAZLIK: PDF_BAYT=%d ama çözülen %d bayt — çıktı kesilmiş olabilir" % (beklenen, len(pdf)))
            uyusmazlik += 1
        else:
            print("BAYT: eşit (%d)" % beklenen)
    sayi, nasil = sayfa_say(pdf)
    ev = meta.get("EV_PAGES", "").strip()
    print("SAYFA: %s · EV_PAGES=%s" % (sayi if sayi is not None else nasil, ev or "YOK"))
    if sayi is not None and ev:
        if ev.isdigit() and int(ev) == sayi:
            print("SAYFA KIYASI: eşit")
        else:
            print("UYUŞMAZLIK: pypdf %d · EV_PAGES %s" % (sayi, ev))
            uyusmazlik += 1
    elif sayi is None:
        print("SAYFA KIYASI: ÖLÇÜLEMEDİ — beklenen sayfa sayısını EV_PAGES ve PDF'i açarak kontrol et")
    if "ADS_IZ_BASI" in meta:
        print("ADS_IZ_BASI: %s" % meta["ADS_IZ_BASI"][:200])
    print("SIRADAKİ: PDF'i aç ve gözle oku (sayfa sayısı, taşma, glif, barkod, büyük harf İ).")
    return 1 if uyusmazlik else 0


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    sys.exit(main())
