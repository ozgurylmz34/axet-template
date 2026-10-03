# -*- coding: utf-8 -*-
"""verify_doc_html.py — üretilmiş doküman HTML'inin (ve istenirse PDF'inin) mekanik doğrulaması.

Kontroller (DOC-KD-11 / DOC-KD-15 / DOC-KD-16'nın ölçülebilen kısmı):
  1. Ölü iç bağlantı : {href="#x"} \\ ({id="x"} ∪ {<a name="x">}) — küme kıyası, sayı değil.
  2. Ham Mermaid     : `language-mermaid` sınıfı ya da <pre>/<code> içinde çıplak diyagram anahtar sözcüğü.
  3. Görseller       : <img> sayısı (--expect-images ile kıyas) ve yerel görsel dosyalarının varlığı.
  4. Yer tutucu      : görünür metinde (kod blokları DAHİL) unutulmuş yer tutucu — kalıplar YER_TUTUCULAR sabitinde,
                       KAPSAM satırı o listeden türetilir. Her kalıp eşleşmesi BULGU'dur (çıkış 1).
                       Kod blokları neden dahil: KD şablonu görsel yer tutucusunu kod bloğu olarak yazar
                       (```[GÖRSEL: …]```); build_kd_pdf eşlemesi o bloğu görselle değiştirmezse blok HTML'de
                       <pre> olarak okuyucuya görünür kalır. Taranmayanlar: <script>/<style> içeriği, HTML yorumları,
                       öznitelik değerleri (alt, title …).
                       `[Açık Konu]` meşru doküman işaretidir (karar bekleyen nokta) → BULGU DEĞİL; sayısı ayrı
                       BİLGİ satırında basılır.
  5. PDF (--pdf)     : dosya var mı, %PDF başlığı, boyut, yaklaşık sayfa ve bağlantı ek açıklaması sayısı.

Kullanım:
    python verify_doc_html.py <doküman.html> [--expect-images N] [--pdf <doküman.pdf>] [--min-pdf-links N]
Çıkış: 0 bulgu yok · 1 bulgu var · 2 girdi okunamadı.
"""
import argparse
import os
import re
import sys
from html.parser import HTMLParser
from urllib.parse import unquote, urlparse

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Unutulmuş yer tutucu kalıpları — TEK liste: tarama (YER_TUTUCU_RX) ve KAPSAM satırı (SCOPE) buradan türetilir.
# (ad, düzenli ifade). Sıra önemlidir: aynı konumda ilk eşleşen kalıp kazanır, eşleşen metin bir kez sayılır
# (ör. "[EKRAN GÖRÜNTÜSÜ — Faz-2'de eklenecek]" üç kalıba da uyar ama 1 bulgu olur).
YER_TUTUCULAR = (
    ("[EKRAN GÖRÜNTÜSÜ …]", r"(?i:\[\s*EKRAN\s+GÖRÜNTÜSÜ\b[^\]\n]*\])"),
    ("[GÖRSEL: …]", r"\[\s*GÖRSEL\s*:[^\]\n]*\]"),
    ("EKRAN GÖRÜNTÜSÜ … eklenecek", r"(?i:EKRAN\s+GÖRÜNTÜSÜ[^\n]{0,80}?\beklenecek\b)"),
    ("Faz-N'de eklenecek", r"(?i:\bFaz[- ]?\d+\s*['’]?\s*(?:de|da|te|ta)\s+eklenecek\b)"),
    ("[AÇIKLAMA YAZILMADI]", r"\[AÇIKLAMA YAZILMADI\]"),  # build_kd_pdf.ACIKLAMA_YOK işaretinin metni
    ("TODO", r"\bTODO\b"),
    ("TBD", r"\bTBD\b"),
    ("FIXME", r"\bFIXME\b"),
)
YER_TUTUCU_RX = re.compile("|".join("(?P<k%d>%s)" % (i, rx) for i, (_, rx) in enumerate(YER_TUTUCULAR)))
ACIK_KONU_RX = re.compile(r"\[Açık Konu(?:[:\s][^\]\n]*)?\]")
# Görünür metin taranırken içeriği atlanan öğeler (tarayıcı göstermez).
GORUNMEZ_ETIKETLER = ("script", "style", "template", "noscript")
# Bu etiketler metni bölmez (satır içi); diğerleri satır sonu sayılır → bitişik bloklar tek kelimeye kaynamaz.
SATIR_ICI = frozenset(("a", "abbr", "b", "bdi", "bdo", "cite", "code", "data", "dfn", "em", "i", "kbd", "mark", "q", "s",
                       "samp", "small", "span", "strong", "sub", "sup", "time", "u", "var", "wbr", "font"))

SCOPE = ("KAPSAM (SCOPE): verify_doc_html — bakılanlar: iç bağlantı hedefleri (id ∪ a name), ham Mermaid sızıntısı (HTML), "
         "<img> sayısı ve yerel dosya varlığı, görünür metinde (kod blokları dahil) yer tutucu kalıpları: "
         + " · ".join(ad for ad, _ in YER_TUTUCULAR)
         + " ([Açık Konu] yalnız sayılır, BİLGİ), PDF varlığı/boyutu/yaklaşık bağlantı sayısı. Bakılmayanlar: görselin "
         "tarayıcıda gerçekten yüklenmesi (naturalWidth), görüntüdeki verinin temizliği, alt ekran kapsamı, PDF metnindeki "
         "ham diyagram kodu ve yer tutucular, <script>/<style>/yorum/öznitelik (alt, title) içindeki yer tutucular, "
         "listede olmayan yer tutucu biçimleri, dış bağlantılar, içerik doğruluğu.")

MERMAID_WORDS = re.compile(r"^\s*(flowchart|graph\s+(TD|TB|BT|LR|RL)|sequenceDiagram|classDiagram|stateDiagram(-v2)?|"
                           r"erDiagram|gantt|pie|journey|mindmap|timeline)\b")


class _Collector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids, self.names, self.hrefs, self.imgs = set(), set(), [], []
        self.mermaid_class = 0
        self._pre_depth = 0
        self._buf = []
        self.pre_texts = []
        self._gizli = 0
        self.gorunur = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in GORUNMEZ_ETIKETLER:
            self._gizli += 1
        if tag not in SATIR_ICI:
            self.gorunur.append("\n")
        if a.get("id"):
            self.ids.add(a["id"])
        if tag == "a":
            if a.get("name"):
                self.names.add(a["name"])
            href = a.get("href") or ""
            if href.startswith("#") and len(href) > 1:
                self.hrefs.append(unquote(href[1:]))
        if tag == "img":
            self.imgs.append(a.get("src") or "")
        if "language-mermaid" in (a.get("class") or ""):
            self.mermaid_class += 1
        if tag in ("pre", "code"):
            if self._pre_depth == 0:
                self._buf = []
            self._pre_depth += 1

    def handle_endtag(self, tag):
        if tag in GORUNMEZ_ETIKETLER and self._gizli:
            self._gizli -= 1
        if tag not in SATIR_ICI:
            self.gorunur.append("\n")
        if tag in ("pre", "code") and self._pre_depth:
            self._pre_depth -= 1
            if self._pre_depth == 0:
                self.pre_texts.append("".join(self._buf))

    def handle_data(self, data):
        if self._pre_depth:
            self._buf.append(data)
        if not self._gizli:
            self.gorunur.append(data)


def yer_tutucu_tara(metin):
    """Döner: ({kalıp adı: [eşleşen metin, ...]}, [Açık Konu] sayısı). Eşleşmeler çakışmaz (tek birleşik ifade)."""
    bulunan = {}
    for m in YER_TUTUCU_RX.finditer(metin):
        ad = YER_TUTUCULAR[int(m.lastgroup[1:])][0]
        bulunan.setdefault(ad, []).append(" ".join(m.group(0).split()))
    return bulunan, len(ACIK_KONU_RX.findall(metin))


def check_html(html_path, expect_images=None):
    with open(html_path, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    c = _Collector()
    c.feed(text)
    findings = []
    targets = c.ids | c.names
    dead = sorted(set(h for h in c.hrefs if h not in targets))
    for h in dead:
        findings.append("ÖLÜ BAĞLANTI: #%s (%d kez)" % (h, c.hrefs.count(h)))
    raw_mermaid = sum(1 for t in c.pre_texts if MERMAID_WORDS.match(t))
    if c.mermaid_class or raw_mermaid:
        findings.append("HAM MERMAID: language-mermaid sınıfı %d · diyagram kodu içeren blok %d (DOC-KD-15)"
                        % (c.mermaid_class, raw_mermaid))
    base = os.path.dirname(os.path.abspath(html_path))
    missing = []
    for src in c.imgs:
        u = urlparse(src)
        if not src or u.scheme in ("http", "https", "data"):
            continue
        if not os.path.exists(os.path.join(base, unquote(u.path))):
            missing.append(src)
    for m in missing:
        findings.append("EKSİK GÖRSEL DOSYASI: %s" % m)
    if expect_images is not None and len(c.imgs) != expect_images:
        findings.append("GÖRSEL SAYISI: beklenen %d, bulunan %d" % (expect_images, len(c.imgs)))
    yer_tutucu, acik_konu = yer_tutucu_tara("".join(c.gorunur))
    for ad, ornekler in yer_tutucu.items():
        tekil = list(dict.fromkeys(ornekler))
        findings.append("YER TUTUCU (%s): %d kez — %s%s" % (
            ad, len(ornekler), " | ".join("«%s»" % o for o in tekil[:3]),
            (" …(+%d farklı)" % (len(tekil) - 3)) if len(tekil) > 3 else ""))
    stats = {"internal_links": len(c.hrefs), "unique_targets": len(set(c.hrefs)), "ids": len(c.ids),
             "a_names": len(c.names), "dead": len(dead), "img": len(c.imgs), "missing_img": len(missing),
             "raw_mermaid": c.mermaid_class + raw_mermaid,
             "placeholder": sum(len(v) for v in yer_tutucu.values()), "acik_konu": acik_konu}
    return findings, stats


def check_pdf(pdf_path, internal_links, min_links=None):
    findings, stats = [], {}
    if not os.path.exists(pdf_path):
        return ["PDF YOK: %s" % pdf_path], stats
    with open(pdf_path, "rb") as fh:
        data = fh.read()
    stats["bytes"] = len(data)
    if not data.startswith(b"%PDF"):
        findings.append("PDF BAŞLIĞI YOK: %s" % pdf_path)
        return findings, stats
    stats["pages"] = len(re.findall(rb"/Type\s*/Page(?!s)\b", data))
    links = len(re.findall(rb"/Subtype\s*/Link\b", data))
    stats["link_annotations"] = links
    compressed = b"/ObjStm" in data
    if links == 0 and compressed:
        stats["link_note"] = "ÖLÇÜLEMEDİ — nesneler sıkıştırılmış akışta; bağlantıları PDF görüntüleyicide elle dene"
    elif min_links is not None and links < min_links:
        findings.append("PDF BAĞLANTI SAYISI: en az %d beklendi, %d bulundu" % (min_links, links))
    elif internal_links and links == 0:
        findings.append("PDF'TE BAĞLANTI YOK: HTML'de %d iç bağlantı var" % internal_links)
    return findings, stats


def main(argv):
    ap = argparse.ArgumentParser(description="Doküman HTML/PDF mekanik doğrulaması")
    ap.add_argument("html")
    ap.add_argument("--expect-images", type=int, default=None)
    ap.add_argument("--pdf", default=None)
    ap.add_argument("--min-pdf-links", type=int, default=None)
    a = ap.parse_args(argv)
    print(SCOPE)
    try:
        findings, stats = check_html(a.html, a.expect_images)
    except OSError as exc:
        print("ÖLÇÜLEMEDİ: HTML okunamadı: %s — bu 'temiz' anlamına gelmez." % exc, file=sys.stderr)
        return 2
    print("HTML: iç bağlantı %(internal_links)d (tekil hedef %(unique_targets)d) · id %(ids)d · a-name %(a_names)d · "
          "ölü %(dead)d · img %(img)d · eksik görsel %(missing_img)d · ham mermaid %(raw_mermaid)d · "
          "yer tutucu %(placeholder)d" % stats)
    if stats["acik_konu"]:
        print("BİLGİ: [Açık Konu] işareti %d kez — meşru karar-bekleyen-nokta işaretidir, BULGU sayılmaz; "
              "yayından önce kapatılıp kapatılmayacağı doküman sahibinin kararıdır." % stats["acik_konu"])
    if a.pdf:
        pf, ps = check_pdf(a.pdf, stats["internal_links"], a.min_pdf_links)
        findings += pf
        if ps:
            print("PDF: %s bayt · yaklaşık sayfa %s · bağlantı ek açıklaması %s%s" % (
                ps.get("bytes"), ps.get("pages", "?"), ps.get("link_annotations", "?"),
                (" · " + ps["link_note"]) if ps.get("link_note") else ""))
    for f in findings:
        print("BULGU:", f)
    print("SONUÇ:", "TEMİZ (yalnız KAPSAM satırındaki yüzeyde)" if not findings else "%d BULGU" % len(findings))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
