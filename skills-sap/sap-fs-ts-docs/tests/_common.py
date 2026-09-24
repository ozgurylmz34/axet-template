# -*- coding: utf-8 -*-
"""Testler için ortak yollar ve yardımcılar (SAP'ye ve ağa bağlanmaz)."""
import io
import os
import shutil
import struct
import subprocess
import sys
import zlib
from contextlib import redirect_stderr, redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
SCRIPTS = os.path.join(SKILL, "scripts")
SAMPLES = os.path.join(HERE, "samples")
TEMPLATES = os.path.join(SKILL, "templates")
REPO = os.path.dirname(os.path.dirname(SKILL))

if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

BROWSER_TESTS = os.environ.get("SAP_FS_TS_DOCS_BROWSER_TESTS") == "1"


def sample(*parts):
    return os.path.join(SAMPLES, *parts)


def _env():
    env = dict(os.environ)
    # Kullanıcı kabuğunda ayarlıysa script'ler başka bir projeyi okur (sahte kırmızı/yeşil); testler cwd'deki
    # geçici projeyi ölçmeli.
    env.pop("AXET_SAP_PROJECT_DIR", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def run_py(script, *args, cwd=None, timeout=180):
    return subprocess.run([sys.executable, "-X", "utf8", os.path.join(SCRIPTS, script), *args],
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          cwd=cwd, env=_env(), timeout=timeout)


def node_path():
    return shutil.which("node")


def run_node(script, *args, cwd=None, timeout=180):
    return subprocess.run([node_path(), os.path.join(SCRIPTS, script), *args],
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          cwd=cwd, env=_env(), timeout=timeout)


def call_main(fn, argv):
    """Script main(argv)'ı süreç içinde çalıştırır. Döner: (kod, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = fn(argv)
        except SystemExit as exc:
            rc = exc.code
    return rc, out.getvalue(), err.getvalue()


def write_png(path, width=60, height=40, border=10):
    """Beyaz zemin üzerinde koyu dikdörtgen içeren RGB PNG (yalnız stdlib)."""
    rows = []
    for y in range(height):
        row = bytearray(b"\x00")
        for x in range(width):
            inside = border <= x < width - border and border <= y < height - border
            row += bytes((30, 60, 90)) if inside else bytes((255, 255, 255))
        rows.append(bytes(row))
    raw = zlib.compress(b"".join(rows))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
                 + chunk(b"IDAT", raw) + chunk(b"IEND", b""))
