#!/usr/bin/env python3
"""md_lite — Markdown alt kümesini bloklara ayırır ve tek dosyalık HTML üretir (yalnız standart kütüphane).

Desteklenen: `#`…`######` başlık · paragraf · `-`/`*`/`+`/`1.` liste (girinti = iç içe) · GFM tablo (`:--` hizalama,
`\\|` kaçışı) · ``` / ~~~ kod bloğu · `>` alıntı · `---` yatay çizgi · tek başına satırda `![alt](yol)` görsel ·
`<!-- pagebreak -->` sayfa sonu · satır içi `**kalın**` `*italik*` `` `kod` `` `[metin](url)` · `\\*` kaçışları.
Desteklenmeyen: HTML etiketi (metin olarak kaçışlanır), dipnot, iç içe alıntı, setext başlık, mermaid çizimi
(kod bloğu olarak basılır).
"""
from __future__ import annotations

import base64
import html
import re
from pathlib import Path

_ESC = re.compile(r"\\([\\`*_{}\[\]()#+\-.!|>~])")
_PROTECTED = re.compile("[\uF000-\uF07F]")
_FENCE = re.compile(r"^\s*(`{3,}|~{3,})\s*([\w+-]*)\s*$")
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_HR = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")
_LIST = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")
_QUOTE = re.compile(r"^\s*>\s?(.*)$")
_IMAGE = re.compile(r'^\s*!\[([^\]]*)\]\(\s*([^)\s]+)(?:\s+"[^"]*")?\s*\)\s*$')
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")
_PAGEBREAK = re.compile(r"^\s*<!--\s*pagebreak\s*-->\s*$", re.IGNORECASE)
_INLINE = re.compile(
    r"(?P<tick>`+)(?P<code>.+?)(?P=tick)"
    r"|\*\*(?P<b1>.+?)\*\*"
    r"|__(?P<b2>.+?)__"
    r"|(?<![\w*])\*(?P<i1>[^\s*](?:.*?[^\s*])?)\*(?![\w*])"
    r"|(?<![\w_])_(?P<i2>[^\s_](?:.*?[^\s_])?)_(?![\w_])"
    r"|!\[(?P<alt>[^\]]*)\]\((?P<isrc>[^)\s]+)[^)]*\)"
    r"|\[(?P<ltext>[^\]]+)\]\((?P<href>[^)\s]+)[^)]*\)"
)
IMAGE_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
              ".bmp": "image/bmp", ".webp": "image/webp", ".svg": "image/svg+xml"}


def protect(s: str) -> str:
    return _ESC.sub(lambda m: chr(0xF000 + ord(m.group(1))), s)


def restore(s: str) -> str:
    return _PROTECTED.sub(lambda m: chr(ord(m.group(0)) - 0xF000), s)


def _cells(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def parse(text: str) -> list[dict]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: list[dict] = []
    para: list[str] = []

    def flush():
        if para:
            blocks.append({"type": "paragraph", "text": " ".join(x.strip() for x in para)})
            para.clear()
    i = 0
    while i < len(lines):
        raw = lines[i]
        fence = _FENCE.match(raw)
        if fence:
            flush()
            body, i = [], i + 1
            while i < len(lines) and not lines[i].strip().startswith(fence.group(1)):
                body.append(lines[i])
                i += 1
            blocks.append({"type": "code", "lang": fence.group(2), "text": "\n".join(body)})
            i += 1
            continue
        line = protect(raw)
        if not line.strip():
            flush()
            i += 1
            continue
        if _PAGEBREAK.match(line):
            flush()
            blocks.append({"type": "pagebreak"})
            i += 1
            continue
        m = _HEADING.match(line)
        if m:
            flush()
            blocks.append({"type": "heading", "level": len(m.group(1)), "text": m.group(2)})
            i += 1
            continue
        if _HR.match(line):
            flush()
            blocks.append({"type": "hr"})
            i += 1
            continue
        if "|" in line and i + 1 < len(lines) and _TABLE_SEP.match(lines[i + 1]):
            flush()
            header = _cells(line)
            seps = _cells(lines[i + 1])
            align = ["center" if s.startswith(":") and s.endswith(":") else "right" if s.endswith(":") else "left"
                     for s in seps]
            rows, i = [], i + 2
            while i < len(lines) and lines[i].strip() and "|" in lines[i]:
                rows.append((_cells(protect(lines[i])) + [""] * len(header))[:len(header)])
                i += 1
            blocks.append({"type": "table", "header": header, "rows": rows,
                           "align": (align + ["left"] * len(header))[:len(header)]})
            continue
        m = _IMAGE.match(line)
        if m:
            flush()
            blocks.append({"type": "image", "alt": m.group(1), "src": m.group(2)})
            i += 1
            continue
        m = _LIST.match(line)
        if m:
            flush()
            items, ordered = [], m.group(2)[0].isdigit()
            while i < len(lines):
                current = protect(lines[i])
                mm = _LIST.match(current)
                if mm:
                    items.append([len(mm.group(1).expandtabs(4)), mm.group(3)])
                elif current.strip() and current[:1] in (" ", "\t") and items:
                    items[-1][1] += " " + current.strip()
                else:
                    break
                i += 1
            ranks = {indent: n for n, indent in enumerate(sorted({it[0] for it in items}))}
            blocks.append({"type": "list", "ordered": ordered, "items": [(ranks[ind], txt) for ind, txt in items]})
            continue
        m = _QUOTE.match(line)
        if m:
            flush()
            quote = []
            while i < len(lines) and _QUOTE.match(protect(lines[i])):
                quote.append(_QUOTE.match(protect(lines[i])).group(1).strip())
                i += 1
            blocks.append({"type": "quote", "text": " ".join(q for q in quote if q)})
            continue
        para.append(line)
        i += 1
    flush()
    return blocks


def _run(text: str, bold: bool, italic: bool, code: bool = False, href: str | None = None) -> dict:
    return {"text": restore(text), "bold": bold, "italic": italic, "code": code, "href": restore(href) if href else None}


def inline_runs(text: str, bold: bool = False, italic: bool = False) -> list[dict]:
    runs: list[dict] = []
    pos = 0
    for m in _INLINE.finditer(text):
        if m.start() > pos:
            runs.append(_run(text[pos:m.start()], bold, italic))
        if m.group("tick"):
            runs.append(_run(m.group("code"), bold, italic, code=True))
        elif m.group("b1") is not None or m.group("b2") is not None:
            runs.extend(inline_runs(m.group("b1") or m.group("b2") or "", True, italic))
        elif m.group("i1") is not None or m.group("i2") is not None:
            runs.extend(inline_runs(m.group("i1") or m.group("i2") or "", bold, True))
        elif m.group("isrc") is not None:
            runs.append(_run(m.group("alt") or "[görsel]", bold, italic))
        else:
            runs.append(_run(m.group("ltext"), bold, italic, href=m.group("href")))
        pos = m.end()
    if pos < len(text):
        runs.append(_run(text[pos:], bold, italic))
    return runs


def plain_text(text: str) -> str:
    return "".join(r["text"] for r in inline_runs(text))


def resolve_image(src: str, base_dir) -> tuple[Path | None, str]:
    src = restore(src)
    if re.match(r"^[a-z][a-z0-9+.-]*:", src, re.IGNORECASE) and not re.match(r"^[a-z]:[\\/]", src, re.IGNORECASE):
        return None, src
    p = Path(src)
    return (p if p.is_absolute() else Path(base_dir) / p), src


CSS = """
@page { size: A4; margin: 16mm 14mm; }
* { -webkit-print-color-adjust: exact; print-color-adjust: exact; box-sizing: border-box; }
body { font-family: "Segoe UI", Arial, sans-serif; font-size: 10.5pt; line-height: 1.5; color: #222; margin: 0; }
h1 { font-size: 20pt; color: #1F4E79; border-bottom: 2px solid #1F4E79; padding-bottom: 4px; }
h2 { font-size: 15pt; color: #1F4E79; page-break-after: avoid; }
h3, h4, h5, h6 { color: #333; page-break-after: avoid; }
table { width: 100%; border-collapse: collapse; table-layout: fixed; margin: 10px 0; font-size: 9.5pt; }
th, td { border: 1px solid #c8ced6; padding: 5px 7px; vertical-align: top; overflow-wrap: anywhere; }
th { background: #1F4E79; color: #fff; }
tr:nth-child(even) td { background: #f3f6f9; }
pre { background: #f6f8fa; border: 1px solid #e1e6eb; padding: 8px; white-space: pre-wrap; overflow-wrap: anywhere; font-size: 9pt; }
code { font-family: Consolas, "Courier New", monospace; background: #eef1f5; padding: 0 3px; }
pre code { background: none; padding: 0; }
blockquote { border-left: 4px solid #1F4E79; background: #eef4fa; margin: 10px 0; padding: 6px 12px; }
figure { margin: 12px 0; text-align: center; page-break-inside: avoid; }
figure img { max-width: 100%; border: 1px solid #ccd; }
figcaption { font-size: 9pt; color: #555; font-style: italic; }
hr { border: none; border-top: 1px solid #bbb; margin: 16px 0; }
.pagebreak { page-break-after: always; }
.missing { color: #a00; font-style: italic; }
"""


def runs_html(runs: list[dict]) -> str:
    out = []
    for r in runs:
        t = html.escape(r["text"])
        if r["code"]:
            t = f"<code>{t}</code>"
        if r["href"]:
            t = f'<a href="{html.escape(r["href"], quote=True)}">{t}</a>'
        if r["italic"]:
            t = f"<em>{t}</em>"
        if r["bold"]:
            t = f"<strong>{t}</strong>"
        out.append(t)
    return "".join(out)


def _list_html(block: dict) -> str:
    tag = "ol" if block["ordered"] else "ul"
    out, depth = [], -1
    for level, text in block["items"]:
        level = max(0, min(level, depth + 1))
        if level > depth:
            out.append(f"<{tag}>")
            depth = level
        else:
            out.append("</li>")
            while depth > level:
                out.append(f"</{tag}></li>")
                depth -= 1
        out.append(f"<li>{runs_html(inline_runs(text))}")
    while depth >= 0:
        out.append(f"</li></{tag}>")
        depth -= 1
    return "".join(out)


def to_html(blocks: list[dict], title: str = "", base_dir=".") -> tuple[str, list[str]]:
    warnings: list[str] = []
    body: list[str] = []
    for b in blocks:
        kind = b["type"]
        if kind == "heading":
            body.append(f"<h{b['level']}>{runs_html(inline_runs(b['text']))}</h{b['level']}>")
        elif kind == "paragraph":
            body.append(f"<p>{runs_html(inline_runs(b['text']))}</p>")
        elif kind == "list":
            body.append(_list_html(b))
        elif kind == "table":
            head = "".join(f'<th style="text-align:{a}">{runs_html(inline_runs(c))}</th>' for c, a in zip(b["header"], b["align"]))
            rows = "".join("<tr>" + "".join(f'<td style="text-align:{a}">{runs_html(inline_runs(c))}</td>'
                                            for c, a in zip(r, b["align"])) + "</tr>" for r in b["rows"])
            body.append(f"<table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>")
        elif kind == "code":
            body.append(f"<pre><code>{html.escape(b['text'])}</code></pre>")
        elif kind == "quote":
            body.append(f"<blockquote>{runs_html(inline_runs(b['text']))}</blockquote>")
        elif kind == "hr":
            body.append("<hr>")
        elif kind == "pagebreak":
            body.append('<div class="pagebreak"></div>')
        elif kind == "image":
            path, src = resolve_image(b["src"], base_dir)
            alt = restore(b["alt"])
            if path is None:
                warnings.append(f"uzak görsel gömülmedi (çıktı çevrimdışı üretilir): {src}")
                img = f'<p class="missing">[uzak görsel: {html.escape(src)}]</p>'
            elif path.is_file() and path.suffix.lower() in IMAGE_MIME:
                data = base64.b64encode(path.read_bytes()).decode("ascii")
                img = f'<img src="data:{IMAGE_MIME[path.suffix.lower()]};base64,{data}" alt="{html.escape(alt, quote=True)}">'
            else:
                warnings.append(f"görsel bulunamadı ya da desteklenmiyor: {src}")
                img = f'<p class="missing">[görsel bulunamadı: {html.escape(src)}]</p>'
            caption = f"<figcaption>{html.escape(alt)}</figcaption>" if alt else ""
            body.append(f"<figure>{img}{caption}</figure>")
    doc = (f'<!doctype html><html lang="tr"><head><meta charset="utf-8"><title>{html.escape(title)}</title>'
           f"<style>{CSS}</style></head><body>{''.join(body)}</body></html>")
    return doc, warnings


def first_heading(blocks: list[dict]) -> str | None:
    for b in blocks:
        if b["type"] == "heading":
            return plain_text(b["text"])
    return None
