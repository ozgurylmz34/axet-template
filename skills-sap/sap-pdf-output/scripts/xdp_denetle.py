# -*- coding: utf-8 -*-
"""XDP şablonunu render ETMEDEN, metin olarak denetler (AF-XDP-03/04/05 + reçete §3.3, §3.7).

Kullanım:
    python xdp_denetle.py sablon.xdp [--locale tr_TR] [--izgara KART_SATIRI ...]

Kurallar:
  XDP-03  `lr-tb` satırında çocuk `w` toplamı kapsayıcıdan 1 mm'den az küçükse (eşit dahil):
          ≥ 8 eleman → UYARI (çekirdekte 8 ve 11 elemanlı satırlar kaydı) · 5-7 → UYARI (eşik ölçülmedi) ·
          ≤ 4 → BİLGİ (2-4 elemanlı satırlar ölçülen vakada kaymadı). Toplam kapsayıcıdan BÜYÜKSE satır kasıtlı
          sarılıyordur (kart ızgarası, çok satırlı başlık) → BİLGİ. Tekrarlı (`occur`) çocuklu satır ve `--izgara`
          ile adı verilen satır → BİLGİ (statik toplam satır genişliği değildir).
  XDP-04  harflerinin hiçbiri küçük olmayan `<text>` içinde `İ` → UYARI (oku: yabancı sözcük/kısaltmada `I` olmalı).
  XDP-05  kök subform'da `locale` yok (ya da `--locale` ile farklı) · `<font typeface>` Arial değil ya da yok ·
          metinli `draw`/barkod dışı `field` içinde `<font>` yok → UYARI.
  R-3.7   `<event activity="layout:ready">` → HATA (doğrusu `activity="ready" ref="$layout"`; ADS hata VERMEZ).
  R-3.3   `multiLine="1"` alan + sabit `h` → UYARI (`minH` kullan; sabit h uzun metni keser).

Çıkış: 0 HATA yok · 1 HATA var · 2 girdi hatası. Her koşuda KAPSAM BEYANI basılır.
"""
import argparse
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _xdp_ortak as ortak  # noqa: E402

EPS = 0.001
YERLESIM_COCUKLARI = ("field", "draw", "subform", "exclGroup", "subformSet")


def _tekrarli(d):
    if d.ad == "subformSet":
        return True
    occ = d.ilk("occur")
    return occ is not None and occ.oz.get("max", "1").strip() != "1"


def _ui_turu(f):
    ui = f.ilk("ui")
    if ui is None or not ui.cocuklar:
        return None
    return ui.cocuklar[0].ad


def denetle(kok, locale=None, izgara=()):
    """Döner: (bulgular [(seviye, kural, satır, mesaj)], sayaç sözlüğü)."""
    sablon = ortak.sablonu_bul(kok)
    if sablon is None:
        raise ValueError("XFA `template` öğesi yok")
    bul = []
    say = {"lr-tb satırı": 0, "XDP-03 ölçülemedi": 0, "text": 0, "font": 0, "event": 0, "multiLine alan": 0}

    def ekle(sev, kural, d, mesaj):
        bul.append((sev, kural, d.satir, "%s: %s" % (ortak.yol_adi(d) or d.ad, mesaj)))

    kok_sf = sablon.ilk("subform")
    if kok_sf is not None:
        loc = kok_sf.oz.get("locale")
        if not loc:
            ekle("UYARI", "XDP-05", kok_sf, "kök subform'da `locale` yok (TR projede `tr_TR`)")
        elif locale and loc != locale:
            ekle("UYARI", "XDP-05", kok_sf, "locale '%s', beklenen '%s'" % (loc, locale))

    for d in sablon.torunlar():
        if d.ad == "subform" and d.oz.get("layout") == "lr-tb":
            cocuk = [c for c in d.cocuklar if c.ad in YERLESIM_COCUKLARI
                     and c.oz.get("presence") not in ("hidden", "inactive")]
            if len(cocuk) < 2:
                continue
            say["lr-tb satırı"] += 1
            if d.oz.get("name") in izgara:
                ekle("BİLGİ", "XDP-03", d, "--izgara ile ızgara işaretlendi; kolon toplamı denetlenmedi")
                continue
            if any(_tekrarli(c) for c in cocuk):
                ekle("BİLGİ", "XDP-03", d, "tekrarlı çocuk var (kart ızgarası olabilir) — statik toplam satır genişliği "
                     "değil, denetlenmedi")
                continue
            kap = ortak.mm(d.oz.get("w"))
            genis = [ortak.mm(c.oz.get("w")) for c in cocuk]
            if kap is None or any(g is None for g in genis):
                say["XDP-03 ölçülemedi"] += 1
                ekle("BİLGİ", "XDP-03", d, "ÖLÇÜLEMEDİ — kapsayıcının ya da bir çocuğun `w`'si yok/birimsiz")
                continue
            toplam, n = sum(genis), len(cocuk)
            ek = ""
            mar = d.ilk("margin")
            if mar is not None and (mar.oz.get("leftInset") or mar.oz.get("rightInset")):
                ek = " · kapsayıcıda margin var: iç genişlik daha dar olabilir, hesaba katılmadı"
            ozet = "%d eleman, toplam %.2f mm / kapsayıcı %.2f mm%s" % (n, toplam, kap, ek)
            if toplam > kap + EPS:
                ekle("BİLGİ", "XDP-03", d, "toplam kapsayıcıdan büyük → satır sarılır; kasıtlı (kart ızgarası, çok "
                     "satırlı blok) değilse düzelt (%s)" % ozet)
            elif toplam > kap - 1 + EPS:
                if n >= 8:
                    ekle("UYARI", "XDP-03", d, "kolon toplamını kapsayıcıdan 1 mm küçük yap — çekirdekte 8 ve 11 "
                         "elemanlı satırda son kolon alt satıra kaydı (%s)" % ozet)
                elif n >= 5:
                    ekle("UYARI", "XDP-03", d, "kolon toplamını kapsayıcıdan 1 mm küçük yap — 5-7 elemanda eşik "
                         "ölçülmedi (%s)" % ozet)
                else:
                    ekle("BİLGİ", "XDP-03", d, "toplam kapsayıcıya eşit; 2-4 elemanlı satırlar ölçülen vakada "
                         "kaymadı, eşik ölçülmedi (%s)" % ozet)
        elif d.ad == "text":
            say["text"] += 1
            t = d.metin.strip()
            if "İ" in t and not any(ch.islower() for ch in t):
                sozler = sorted({s for s in t.split() if "İ" in s})
                ekle("UYARI", "XDP-04", d, "büyük harfli etikette İ: «%s» (İ'li sözcük: %s) — Türkçe sözcük mü? "
                     "yabancı sözcük/kısaltmada `I` olmalı" % (t, ", ".join(sozler)))
        elif d.ad == "font":
            say["font"] += 1
            tf = d.oz.get("typeface")
            if tf is None:
                ekle("UYARI", "XDP-05", d, "`<font>` typeface yok (Arial yaz)")
            elif tf != "Arial":
                ekle("UYARI", "XDP-05", d, "typeface '%s' — Arial dışı yazı tipinin ADS'te gömülmesi ve Türkçe glifleri "
                     "ölçülmedi" % tf)
        elif d.ad in ("field", "draw"):
            if d.ad == "draw" and not any(x.ad == "text" for x in d.torunlar()):
                continue
            if d.ad == "field" and _ui_turu(d) == "barcode":
                continue
            if d.ilk("font") is None:
                ekle("UYARI", "XDP-05", d, "`<font>` yok — etkili yazı tipi bu araçla belirlenmedi; "
                     "`<font typeface=\"Arial\" …/>` ver")
            if d.ad == "field":
                ui = d.ilk("ui")
                te = ui.ilk("textEdit") if ui is not None else None
                if te is not None and te.oz.get("multiLine") == "1":
                    say["multiLine alan"] += 1
                    if d.oz.get("h"):
                        ekle("UYARI", "R-3.3", d, "multiLine alanda sabit h=\"%s\" — uzun metin kesilir; `minH` kullan"
                             % d.oz.get("h"))
        elif d.ad == "event":
            say["event"] += 1
            act = d.oz.get("activity", "")
            if act == "layout:ready":
                ekle("HATA", "R-3.7", d, "activity=\"layout:ready\" XFA değeri DEĞİL — ADS hata vermeden render eder; "
                     "`activity=\"ready\" ref=\"$layout\"` yaz")
            elif ":" in act:
                ekle("UYARI", "R-3.7", d, "activity=\"%s\" — ':' içeren değerin XFA'da geçerli olduğu doğrulanmadı" % act)
    bul.sort(key=lambda x: x[2])
    return bul, say


KAPSAM_BAKILMAYAN = ("BAKILMAYANLAR: render · gerçek sayfa kırılımı ve sayfa sayısı (`ev_pages` + PDF'i aç) · barkod "
                     "okunurluğu · glif çıktısı ve `embed_fonts` (ABAP tarafı) · margin/padding'in kolon genişliğine "
                     "etkisi · `<exData>` zengin metin · betiklerin koşup koşmadığı · bağlama (xdp_abap_uret.py). "
                     "'0 bulgu' yalnız yukarıdaki kurallar için anlamlıdır.")


def main(argv=None):
    ap = argparse.ArgumentParser(description="XDP metin denetçisi (render etmez)")
    ap.add_argument("xdp")
    ap.add_argument("--locale", help="beklenen locale (ör. tr_TR)")
    ap.add_argument("--izgara", action="append", default=[], help="kasıtlı sarılan satır subform adı (tekrarlanabilir)")
    try:
        a = ap.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    try:
        kok = ortak.oku(a.xdp)
        bul, say = denetle(kok, a.locale, tuple(a.izgara))
    except (OSError, ortak.XmlHatasi, ValueError) as exc:
        print("HATA: %s" % exc, file=sys.stderr)
        return 2
    for sev, kural, satir, mesaj in bul:
        print("%s %s satır %d — %s" % (sev, kural, satir, mesaj))
    sayim = {s: sum(1 for b in bul if b[0] == s) for s in ("HATA", "UYARI", "BİLGİ")}
    print("SONUÇ: hata %d · uyarı %d · bilgi %d" % (sayim["HATA"], sayim["UYARI"], sayim["BİLGİ"]))
    print("KAPSAM BEYANI: bakılanlar — %s." % " · ".join("%s %d" % kv for kv in say.items()))
    print(KAPSAM_BAKILMAYAN)
    return 1 if sayim["HATA"] else 0


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    sys.exit(main())
