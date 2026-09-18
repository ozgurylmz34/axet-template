# -*- coding: utf-8 -*-
"""Genel doküman derleyici: Markdown → tek dosya HTML (Mermaid → PNG, figür sarma, TR slug'lı içindekiler, A4 CSS) → PDF.

Kullanım:
    python build_doc_pdf.py <girdi.md> <cikti.html> ["Başlık"] [--also parca2.md ...] [--prefix <ad>] [--pdf] [--pdf-out <yol>]

  --also   : ek Markdown parçaları sırayla birleştirilir (beş parçalı TS gibi).
  --prefix : Mermaid PNG ön eki; verilmezse çıktı adındaki doküman kimliğinden türetilir.
  --pdf    : HTML'den sonra `html_to_pdf.js` ile PDF üretir.

Görseller HTML'in yanındaki `screenshots/` klasöründen göreli yolla okunur.
Çıkış: 0 başarılı · 2 eksik bağımlılık / okunamayan girdi · 1 PDF üretim hatası.
"""
import argparse
import html as _html
import os
import re
import shutil
import subprocess
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from doc_tools import preprocess_mermaid_fences  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SCOPE = ("KAPSAM (SCOPE): build_doc_pdf — Markdown'ı HTML'e (ve istenirse PDF'e) çevirir; basılan sayılar: <img>, <figure>, "
         "mermaid blok/render. Bakılmayanlar: içindekiler bağlantılarının hedefi, görsel dosyalarının varlığı, içerik "
         "doğruluğu → verify_doc_html.py ve doc-checklist.")

MARKDOWN_INSTALL = "python -m pip install markdown"

CSS = """
@page { size: A4; margin: 16mm 14mm 18mm 14mm; }
* { box-sizing: border-box; }
body { font-family: 'Segoe UI','Helvetica Neue',Arial,sans-serif; font-size: 10.5pt; color: #2b2b2b; line-height: 1.55; margin: 0; }
h1 { font-size: 23pt; color: #fff; background: linear-gradient(135deg,#0b4f8a,#1769b0); padding: 22px 24px; border-radius: 10px; margin: 0 0 18px 0; line-height:1.2; }
h2 { font-size: 15pt; color: #0b4f8a; border-bottom: 2px solid #0b4f8a; padding-bottom: 4px; margin: 26px 0 12px; page-break-after: avoid; }
h3 { font-size: 12.5pt; color: #1565a0; margin: 18px 0 8px; page-break-after: avoid; }
h4 { font-size: 11pt; color: #34556e; margin: 14px 0 6px; }
p, li { font-size: 10.5pt; }
a { color: #1769b0; text-decoration: none; }
table { width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 9.6pt; page-break-inside: avoid; }
th { background: #0b4f8a; color: #fff; text-align: left; padding: 7px 9px; font-weight: 600; }
td { border: 1px solid #d0d7de; padding: 6px 9px; vertical-align: top; }
tr:nth-child(even) td { background: #f6f8fa; }
figure { margin: 16px 0; text-align: center; page-break-inside: avoid; }
figure img { max-width: 100%; border: 1px solid #c3ccd6; border-radius: 6px; box-shadow: 0 2px 9px rgba(0,0,0,.13); }
figcaption { font-size: 9pt; color: #5a6b7b; font-style: italic; margin-top: 7px; padding: 0 8px; }
blockquote { border-left: 4px solid #4a90d9; background: #eef5fc; margin: 14px 0; padding: 10px 16px; border-radius: 0 6px 6px 0; }
code { background: #eef1f5; font-family: Consolas,monospace; font-size: 9.2pt; padding: 1px 5px; border-radius: 3px; }
pre { background: #f6f8fa; border: 1px solid #e1e6eb; border-radius: 6px; padding: 12px; page-break-inside: avoid; font-size: 8.8pt; white-space: pre; overflow-x: auto; }
pre code { background: none; padding: 0; font-size: inherit; }
hr { border: none; border-top: 1px solid #dfe5ec; margin: 22px 0; }
ul, ol { padding-left: 22px; }
strong { color: #1d3a52; }
"""


def diagram_prefix(html_path):
    """Mermaid PNG ad alanını doküman başına ayırır: 'KD-SD-001_Ad' → 'kd-sd-001'.

    Neden varsayılan: aynı klasörde iki dokümanın diyagramları aynı adla yazılırsa ikinci derleme birincinin
    PNG'lerini sessizce ezer; birinci doküman yanlış diyagramı gösterir ve hiçbir uyarı çıkmaz.
    """
    base = os.path.splitext(os.path.basename(html_path))[0]
    head = base.split("_", 1)[0]
    slug = re.sub(r"[^A-Za-z0-9]+", "-", head).strip("-").lower()
    return slug or "diagram"


_TR_MAP = str.maketrans("ıİşŞğĞçÇöÖüÜ", "iisSgGcCoOuU")


def slug_tr(value, separator="-"):
    """Türkçe farkındalı başlık slug'ı (`toc` eklentisinin kimlik üreticisi).

    Varsayılan slug Türkçe harfleri siler ("Kılavuz" → "klavuz"); burada harf ASCII karşılığına çevrilir, noktalama
    silinir, her boşluk ayrı tire olur ("Liste / Tablo" → "liste--tablo").
    """
    v = value.translate(_TR_MAP)
    v = unicodedata.normalize("NFKD", v).encode("ascii", "ignore").decode("ascii")
    v = re.sub(r"[^\w\s-]", "", v).strip().lower()
    return re.sub(r"\s", separator, v)


def _load_markdown():
    try:
        import markdown
    except ImportError:
        print("HATA: Python 'markdown' paketi yok. Kurulum: " + MARKDOWN_INSTALL, file=sys.stderr)
        raise SystemExit(2)
    return markdown


def render_html(md_text, html_path, title=None, prefix=None):
    """Markdown metnini HTML dosyasına yazar. Döner: {"img": n, "figure": n, "mermaid_blocks": n, "mermaid_rendered": n}."""
    markdown = _load_markdown()
    out_dir = os.path.dirname(os.path.abspath(html_path))
    shot_dir = os.path.join(out_dir, "screenshots")
    stats = {}
    md_text = preprocess_mermaid_fences(md_text, out_dir=shot_dir, rel_prefix="screenshots",
                                       prefix=prefix or diagram_prefix(html_path), stats=stats)
    # `toc` eklentisi zorunlu: yoksa başlıklara id verilmez ve içindekiler bağlantılarının tamamı sessizce ölü olur.
    body = markdown.markdown(md_text, extensions=["tables", "fenced_code", "sane_lists", "toc"],
                             extension_configs={"toc": {"slugify": slug_tr}})
    body = re.sub(r"<p>(<img[^>]*?>)</p>\s*<p><em>(.*?)</em></p>",
                  r"<figure>\1<figcaption>\2</figcaption></figure>", body, flags=re.S)
    title = title or os.path.splitext(os.path.basename(html_path))[0]
    page = ('<!DOCTYPE html><html lang="tr"><head><meta charset="utf-8">'
            "<title>%s</title><style>%s</style></head><body>%s</body></html>" % (_html.escape(title), CSS, body))
    os.makedirs(out_dir, exist_ok=True)
    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(page)
    return {"img": body.count("<img"), "figure": body.count("<figure>"),
            "mermaid_blocks": stats.get("blocks", 0), "mermaid_rendered": stats.get("rendered", 0)}


def read_parts(paths):
    parts = []
    for p in paths:
        try:
            with open(p, encoding="utf-8") as fh:
                parts.append(fh.read().rstrip("\n"))
        except OSError as exc:
            print("HATA: okunamadı: %s (%s)" % (p, exc), file=sys.stderr)
            raise SystemExit(2)
    return "\n\n".join(parts) + "\n"


def build(md_path, html_path, title=None, diagram_prefix_value=None, also=None):
    counts = render_html(read_parts([md_path] + list(also or [])), html_path, title, diagram_prefix_value)
    print("OK | %s | <img>: %d | <figure>: %d | mermaid: %d blok, %d render" % (
        html_path, counts["img"], counts["figure"], counts["mermaid_blocks"], counts["mermaid_rendered"]))
    if counts["mermaid_blocks"] > counts["mermaid_rendered"]:
        print("UYARI: %d mermaid bloğu görsele çevrilemedi; çıktıda ham diyagram kodu var (DOC-KD-15)."
              % (counts["mermaid_blocks"] - counts["mermaid_rendered"]))
    return counts


def to_pdf(html_path, pdf_path=None):
    """HTML → PDF (`node html_to_pdf.js`, bu script'in komşusu). Döner: çıkış kodu."""
    pdfjs = os.path.join(os.path.dirname(os.path.abspath(__file__)), "html_to_pdf.js")
    if not shutil.which("node"):
        print("HATA: node bulunamadı; PDF üretilemedi. Node.js kurulmalı.", file=sys.stderr)
        return 2
    pdf_path = pdf_path or (html_path[:-5] + ".pdf" if html_path.endswith(".html") else html_path + ".pdf")
    r = subprocess.run(["node", pdfjs, os.path.abspath(html_path), os.path.abspath(pdf_path)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (r.stdout or "").strip()
    err = (r.stderr or "").strip()
    if out:
        print(out)
    if r.returncode != 0:
        print(err or "PDF üretimi başarısız", file=sys.stderr)
    return r.returncode


def main(argv):
    ap = argparse.ArgumentParser(description="Markdown → HTML (→ PDF)")
    ap.add_argument("md")
    ap.add_argument("html")
    ap.add_argument("title", nargs="?")
    ap.add_argument("--also", action="append", default=[], help="ek Markdown parçası (tekrarlanabilir)")
    ap.add_argument("--prefix", default=None)
    ap.add_argument("--pdf", action="store_true")
    ap.add_argument("--pdf-out", default=None)
    a = ap.parse_args(argv)
    print(SCOPE)
    build(a.md, a.html, a.title, a.prefix, a.also)
    if a.pdf or a.pdf_out:
        return to_pdf(a.html, a.pdf_out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
