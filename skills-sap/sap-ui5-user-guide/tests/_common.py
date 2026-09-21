# -*- coding: utf-8 -*-
"""Testler için ortak yollar ve yardımcılar (SAP'ye, ağa bağlanmaz; hiçbir şey kurmaz)."""
import io
import json
import os
import subprocess
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
SCRIPTS = os.path.join(SKILL, "scripts")
REPO = os.path.dirname(os.path.dirname(SKILL))

if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)


def _env(extra=None):
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    if extra:
        env.update(extra)
    return env


def run_py(script, *args, cwd=None, env=None, timeout=120):
    return subprocess.run([sys.executable, "-X", "utf8", os.path.join(SCRIPTS, script), *args],
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          cwd=cwd, env=_env(env), timeout=timeout, stdin=subprocess.DEVNULL)


def call_main(fn, argv):
    """Script main(argv)'ı süreç içinde çalıştırır. Döner: (kod, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = fn(argv)
        except SystemExit as exc:
            rc = exc.code
    return rc, out.getvalue(), err.getvalue()


def gecici_dizin():
    """Repo DIŞINDA geçici dizin (repo içi TMP, 'git reposu değil' testlerini yanlış düşürür)."""
    return tempfile.TemporaryDirectory(prefix="kd-ortam-test-")


def yaz_json(yol, veri):
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    with open(yol, "w", encoding="utf-8") as fh:
        json.dump(veri, fh)


def agac_listesi(kok):
    """Dizindeki tüm göreli yollar (değişmezlik denetimi için)."""
    out = []
    for r, dirs, files in os.walk(kok):
        for n in dirs + files:
            out.append(os.path.relpath(os.path.join(r, n), kok))
    return sorted(out)
