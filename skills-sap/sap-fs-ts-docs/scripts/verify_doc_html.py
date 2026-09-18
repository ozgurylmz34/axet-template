# -*- coding: utf-8 -*-
"""verify_doc_html.py — üretilmiş doküman HTML'inin (ve istenirse PDF'inin) mekanik doğrulaması.

Kontroller (DOC-KD-11 / DOC-KD-15 / DOC-KD-16'nın ölçülebilen kısmı):
  1. Ölü iç bağlantı : {href="#x"} \\ ({id="x"} ∪ {<a name="x">}) — küme kıyası, sayı değil.
  2. Ham Mermaid     : `language-mermaid` sınıfı ya da <pre>/<code> içinde çıplak diyagram anahtar sözcüğü.
  3. Görseller       : <img> sayısı (--expect-images ile kıyas) ve yerel görsel dosyalarının varlığı.
  4. PDF (--pdf)     : dosya var mı, %PDF başlığı, boyut, yaklaşık sayfa ve bağlantı ek açıklaması sayısı.

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

SCOPE = ("KAPSAM (SCOPE): verify_doc_html — bakılanlar: iç bağlantı hedefleri (id ∪ a name), ham Mermaid sızıntısı (HTML), "
         "<img> sayısı ve yerel dosya varlığı, PDF varlığı/boyutu/yaklaşık bağlantı sayısı. Bakılmayanlar: görselin "
         "tarayıcıda gerçekten yüklenmesi (naturalWidth), görüntüdeki verinin temizliği, alt ekran kapsamı, PDF metnindeki "
         "ham diyagram kodu, dış bağlantılar, içerik doğruluğu.")

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

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
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
        if tag in ("pre", "code") and self._pre_depth:
            self._pre_depth -= 1
            if self._pre_depth == 0:
                self.pre_texts.append("".join(self._buf))

    def handle_data(self, data):
        if self._pre_depth:
            self._buf.append(data)


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
    stats = {"internal_links": len(c.hrefs), "unique_targets": len(set(c.hrefs)), "ids": len(c.ids),
             "a_names": len(c.names), "dead": len(dead), "img": len(c.imgs), "missing_img": len(missing),
             "raw_mermaid": c.mermaid_class + raw_mermaid}
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
          "ölü %(dead)d · img %(img)d · eksik görsel %(missing_img)d · ham mermaid %(raw_mermaid)d" % stats)
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
