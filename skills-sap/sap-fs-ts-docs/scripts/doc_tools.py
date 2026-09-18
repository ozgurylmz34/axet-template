# -*- coding: utf-8 -*-
"""Doküman araç katmanı — Mermaid (diyagram) ve Marp (eğitim slaytı) ortak yardımcı.

Kanıtlı çağrı bilgisi (gerçek render ile doğrulanmış yöntem):
  - mmdc (Mermaid CLI) kendi Chromium'unu indirmeyebilir → sistem tarayıcısına yönlendirilir
    (puppeteer yapılandırması executablePath).
  - marp --pdf/--pptx açık Chrome profiliyle takılabilir → varsayılan tarayıcı Edge (`--browser edge`).
  - Puppeteer yapılandırmasında Windows yolu ileri eğik çizgiyle yazılır (ters eğik çizgi JSON kaçışını bozar).

Kütüphane:
    from doc_tools import preprocess_mermaid_fences, marp_build
CLI:
    python doc_tools.py check                     # araç + tarayıcı durumu
    python doc_tools.py mermaid girdi.mmd cikti.png
    python doc_tools.py marp deck.md pdf|pptx|html [cikti]

Çıkış: 0 başarılı · 2 eksik araç ya da kullanım hatası · 1 render hatası.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SCOPE = ("KAPSAM (SCOPE): doc_tools — Mermaid blok/dosya render ve Marp derleme; bakılanlar: araç ve tarayıcı "
         "bulunabilirliği, render çıkış kodu ve çıktı dosyasının varlığı. Bakılmayanlar: diyagramın içerik "
         "doğruluğu, görsel okunabilirlik, slayt içeriği.")

MMDC_INSTALL = "npm i -g @mermaid-js/mermaid-cli"
MARP_INSTALL = "npm i -g @marp-team/marp-cli"

_NPM_BIN = os.path.join(os.environ.get("APPDATA", ""), "npm") if os.environ.get("APPDATA") else ""

MERMAID_FENCE = re.compile(r"```mermaid[^\n]*\n(.*?)\n```[^\n]*\n?", re.S)


def _browser_candidates():
    roots = [os.environ.get("PROGRAMFILES(X86)"), os.environ.get("PROGRAMFILES"), os.environ.get("LOCALAPPDATA"),
             r"C:\Program Files (x86)", r"C:\Program Files"]
    out = []
    for r in roots:
        if not r:
            continue
        out.append(os.path.join(r, "Microsoft", "Edge", "Application", "msedge.exe"))
    for r in roots:
        if not r:
            continue
        out.append(os.path.join(r, "Google", "Chrome", "Application", "chrome.exe"))
    return out


def find_browser():
    """Kurulu Chromium tabanlı tarayıcı yolu (Edge önce). Yoksa None. `DOC_TOOLS_BROWSER` ile ezilir."""
    env = os.environ.get("DOC_TOOLS_BROWSER")
    if env and os.path.exists(env):
        return env
    for p in _browser_candidates():
        if os.path.exists(p):
            return p
    for name in ("msedge", "microsoft-edge", "google-chrome", "chrome", "chromium", "chromium-browser"):
        hit = shutil.which(name)
        if hit:
            return hit
    return None


def resolve_cli(name):
    """Global npm CLI'sini bulur (.cmd dahil): PATH + %APPDATA%\\npm."""
    hit = shutil.which(name)
    if hit:
        return hit
    if _NPM_BIN:
        for ext in (".cmd", ".exe", ""):
            cand = os.path.join(_NPM_BIN, name + ext)
            if os.path.exists(cand):
                return cand
    return None


def _browser_for_marp():
    b = (find_browser() or "").lower()
    return "edge" if "edge" in b else "chrome"


# --------------------------------------------------------------------------- Mermaid

def render_mermaid(mmd_path, out_path, scale=2, background="white", theme="default"):
    """Tek .mmd dosyasını SVG/PNG'ye çevirir (uzantı biçimi belirler). Hata → RuntimeError."""
    mmdc = resolve_cli("mmdc")
    if not mmdc:
        raise RuntimeError("mmdc bulunamadı. Kurulum: " + MMDC_INSTALL)
    browser = find_browser()
    cfg_path = None
    cmd = [mmdc, "-i", mmd_path, "-o", out_path, "-t", theme, "-b", background, "-s", str(scale)]
    if browser:
        cfg = {"executablePath": browser.replace("\\", "/"), "args": ["--no-sandbox"]}
        fd, cfg_path = tempfile.mkstemp(suffix=".json", prefix="mmdc-")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh)
        cmd += ["-p", cfg_path]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL)
    finally:
        if cfg_path and os.path.exists(cfg_path):
            os.remove(cfg_path)
    if r.returncode != 0 or not os.path.exists(out_path):
        raise RuntimeError("mermaid render başarısız:\n" + ((r.stderr or r.stdout) or "")[-600:])
    return out_path


def count_mermaid_fences(md):
    return len(MERMAID_FENCE.findall(md))


def preprocess_mermaid_fences(md, out_dir, rel_prefix="screenshots", scale=2, prefix="diagram", stats=None):
    """Markdown içindeki ```mermaid blokları PNG'ye çevrilip `![cap](png)` + `*cap*` ile değiştirilir.

    Render edilemeyen blok DOKUNULMADAN kalır ve stderr'e uyarı yazılır (çıktıda ham diyagram kodu
    kalır → `verify_doc_html.py` yakalar). `stats` sözlüğü verilirse {"blocks": N, "rendered": M} doldurulur.
    """
    total = count_mermaid_fences(md)
    if stats is not None:
        stats.update({"blocks": total, "rendered": 0})
    if total == 0:
        return md
    if not resolve_cli("mmdc"):
        sys.stderr.write("[doc_tools] UYARI: %d mermaid bloğu var ama mmdc bulunamadı; bloklar metin olarak kalır. "
                         "Kurulum: %s\n" % (total, MMDC_INSTALL))
        return md
    os.makedirs(out_dir, exist_ok=True)
    counter = {"n": 0}

    def _sub(m):
        counter["n"] += 1
        idx = counter["n"]
        name = "%s-%02d.png" % (prefix, idx)
        out_png = os.path.join(out_dir, name)
        fd, mmd = tempfile.mkstemp(suffix=".mmd", prefix="mmd-")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(m.group(1))
        try:
            render_mermaid(mmd, out_png, scale=scale)
        except Exception as exc:
            sys.stderr.write("[doc_tools] mermaid blok #%d render edilemedi: %s\n" % (idx, exc))
            return m.group(0)
        finally:
            if os.path.exists(mmd):
                os.remove(mmd)
        if stats is not None:
            stats["rendered"] += 1
        cap = "Şekil — Diyagram %d" % idx
        return "\n\n![%s](%s/%s)\n\n*%s*\n" % (cap, rel_prefix, name, cap)

    return MERMAID_FENCE.sub(_sub, md)


# --------------------------------------------------------------------------- Marp

def marp_build(md_path, fmt, out_path=None, theme=None, allow_local_files=True):
    """Marp Markdown → pdf | pptx | html. PDF/PPTX için Edge tercih edilir."""
    marp = resolve_cli("marp")
    if not marp:
        raise RuntimeError("marp bulunamadı. Kurulum: " + MARP_INSTALL)
    fmt = fmt.lower()
    if fmt not in ("pdf", "pptx", "html"):
        raise ValueError("biçim pdf | pptx | html olmalı: %s" % fmt)
    if out_path is None:
        out_path = os.path.splitext(md_path)[0] + "." + fmt
    cmd = [marp, md_path, "--" + fmt, "-o", out_path]
    if fmt in ("pdf", "pptx"):
        cmd += ["--browser", _browser_for_marp()]
        if allow_local_files:
            cmd += ["--allow-local-files"]
    if theme:
        cmd += ["--theme", theme]
    env = dict(os.environ)
    browser = find_browser()
    if browser:
        env["CHROME_PATH"] = browser
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180, stdin=subprocess.DEVNULL, env=env)
    if r.returncode != 0 or not os.path.exists(out_path):
        raise RuntimeError("marp derleme başarısız:\n" + ((r.stderr or r.stdout) or "")[-600:])
    return out_path


# --------------------------------------------------------------------------- CLI

def check():
    """Bağımlılık durumunu yazar. Döner: {ad: yol ya da None}."""
    status = {}
    try:
        import markdown  # noqa: F401
        status["python-markdown"] = getattr(markdown, "__version__", "kurulu")
    except ImportError:
        status["python-markdown"] = None
    try:
        import PIL  # noqa: F401
        status["Pillow"] = getattr(PIL, "__version__", "kurulu")
    except ImportError:
        status["Pillow"] = None
    status["node"] = shutil.which("node")
    status["mmdc"] = resolve_cli("mmdc")
    status["marp"] = resolve_cli("marp")
    status["tarayıcı"] = find_browser()
    hints = {"python-markdown": "python -m pip install markdown", "Pillow": "python -m pip install Pillow",
             "node": "Node.js kurulmalı", "mmdc": MMDC_INSTALL, "marp": MARP_INSTALL,
             "tarayıcı": "Edge ya da Chrome kurulmalı (ya da DOC_TOOLS_BROWSER)"}
    print("== doc_tools bağımlılık durumu ==")
    for k, v in status.items():
        print("  %-16s: %s" % (k, v if v else "YOK — " + hints[k]))
    print("  playwright-core : node html_to_pdf.js --check ile ölçülür")
    return status


def main(argv):
    print(SCOPE)
    if not argv or argv[0] == "check":
        check()
        return 0
    cmd = argv[0]
    try:
        if cmd == "mermaid":
            if len(argv) < 3:
                print("kullanım: doc_tools.py mermaid girdi.mmd cikti.(svg|png)")
                return 2
            print("OK:", render_mermaid(argv[1], argv[2]))
            return 0
        if cmd == "marp":
            if len(argv) < 3:
                print("kullanım: doc_tools.py marp deck.md (pdf|pptx|html) [cikti]")
                return 2
            print("OK:", marp_build(argv[1], argv[2], argv[3] if len(argv) > 3 else None))
            return 0
    except RuntimeError as exc:
        msg = str(exc)
        print("HATA:", msg, file=sys.stderr)
        return 2 if "bulunamadı" in msg else 1
    print("bilinmeyen komut:", cmd)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
