#!/usr/bin/env python3
"""md_to_pdf.py — Markdown → HTML (md_lite) → PDF, sistemdeki Edge/Chrome'un başsız yazdırmasıyla.

Python paketi gerektirmez; Chromium tabanlı bir tarayıcı gerektirir (Windows'ta Edge standarttır).
Tarayıcı sırası: --browser · ortam değişkeni OFFICE_PDF_BROWSER · PATH'teki msedge/chrome/chromium ·
standart Windows kurulum yolları. Görseller HTML'e gömülür; uzak (http) görsel indirilmez.
Tarayıcı ayrı ve geçici bir profille çalıştırılır (açık tarayıcı oturumuna dokunmaz).

Kullanım:
  python md_to_pdf.py --input rapor.md --output rapor.pdf [--title "Başlık"] [--redact-pii [--pii-mode genis]]
                      [--keep-html rapor.html] [--browser YOL] [--timeout 120] [--force]
Çıkış: 0 başarı · 1 dönüştürme hatası · 3 kullanım hatası · 4 tarayıcı bulunamadı.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import md_lite  # noqa: E402
import pii_redact  # noqa: E402

_WIN_PATHS = (("ProgramFiles(x86)", r"Microsoft\Edge\Application\msedge.exe"),
              ("ProgramFiles", r"Microsoft\Edge\Application\msedge.exe"),
              ("ProgramFiles", r"Google\Chrome\Application\chrome.exe"),
              ("ProgramFiles(x86)", r"Google\Chrome\Application\chrome.exe"),
              ("LOCALAPPDATA", r"Google\Chrome\Application\chrome.exe"))


def find_browser(explicit: str | None = None) -> str | None:
    candidates = [explicit, os.environ.get("OFFICE_PDF_BROWSER")]
    candidates += [shutil.which(n) for n in ("msedge", "chrome", "google-chrome", "chromium", "chromium-browser")]
    for env, rel in _WIN_PATHS:
        base = os.environ.get(env)
        if base:
            candidates.append(os.path.join(base, rel))
    for c in candidates:
        if c and Path(c).is_file():
            return c
    return None


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Markdown → PDF (Edge/Chrome başsız yazdırma)")
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--title")
    ap.add_argument("--redact-pii", action="store_true", help="TR kimlik/vergi/IBAN numaralarını maskele")
    ap.add_argument("--pii-mode", choices=pii_redact.MODES, default="akilli")
    ap.add_argument("--keep-html", help="ara HTML'i bu yola da yaz")
    ap.add_argument("--browser", help="Edge/Chrome çalıştırılabilir dosya yolu")
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--force", action="store_true")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code in (0, None) else 3

    src, out = Path(args.input), Path(args.output)
    if not src.is_file():
        print(f"HATA (kullanım): girdi yok: {src}", file=sys.stderr)
        return 3
    if out.suffix.lower() != ".pdf":
        print("HATA (kullanım): çıktı .pdf olmalı", file=sys.stderr)
        return 3
    if out.exists() and not args.force:
        print(f"HATA (kullanım): çıktı zaten var: {out} (ezmek için --force)", file=sys.stderr)
        return 3
    if args.browser and not Path(args.browser).is_file():
        print(f"HATA (kullanım): --browser yolu yok: {args.browser}", file=sys.stderr)
        return 3

    text = src.read_text(encoding="utf-8-sig")
    if args.redact_pii:
        text, counts = pii_redact.redact_text(text, args.pii_mode)
        print("maskeleme: " + " · ".join(f"{k}={v}" for k, v in counts.items()))
    blocks = md_lite.parse(text)
    title = args.title or md_lite.first_heading(blocks) or src.stem
    document, warnings = md_lite.to_html(blocks, title, src.parent)
    for w in warnings:
        print(f"UYARI: {w}")
    if args.keep_html:
        Path(args.keep_html).write_text(document, encoding="utf-8")
        print(f"HTML: {args.keep_html}")

    browser = find_browser(args.browser)
    if not browser:
        print("EKSİK BAĞIMLILIK: Edge/Chrome bulunamadı. --browser ile yol ver ya da --keep-html ile HTML'i al ve "
              "tarayıcıda Yazdır → PDF olarak kaydet.", file=sys.stderr)
        return 4

    work = Path(tempfile.mkdtemp(prefix="office_pdf_"))
    try:
        html_path = work / "belge.html"
        html_path.write_text(document, encoding="utf-8")
        tmp_pdf = work / "belge.pdf"
        cmd = [browser, "--headless", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
               "--disable-extensions", f"--user-data-dir={work / 'profil'}", "--no-pdf-header-footer",
               "--print-to-pdf-no-header", f"--print-to-pdf={tmp_pdf}", html_path.as_uri()]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                  stdin=subprocess.DEVNULL, timeout=args.timeout)
        except subprocess.TimeoutExpired:
            print(f"HATA: tarayıcı {args.timeout} sn içinde bitmedi", file=sys.stderr)
            return 1
        data = tmp_pdf.read_bytes() if tmp_pdf.is_file() else b""
        if not data.startswith(b"%PDF"):
            tail = (proc.stderr or proc.stdout or "")[-600:]
            print(f"HATA: PDF üretilmedi (tarayıcı çıkış kodu {proc.returncode}). Son çıktı:\n{tail}", file=sys.stderr)
            return 1
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists():
            out.unlink()
        shutil.move(str(tmp_pdf), str(out))
        pages = len(re.findall(rb"/Type\s*/Page(?![s\w])", data))
        print(f"yazıldı: {out} · {len(data)} bayt · sayfa: {pages or '?'} · tarayıcı: {Path(browser).name}")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
