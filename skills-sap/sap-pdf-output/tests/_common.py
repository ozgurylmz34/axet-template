# -*- coding: utf-8 -*-
"""Testler için ortak yollar ve yardımcılar (SAP'ye, ağa bağlanmaz; hiçbir şey kurmaz)."""
import io
import os
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
SCRIPTS = os.path.join(SKILL, "scripts")
TEMPLATES = os.path.join(SKILL, "templates")

if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

NS_XDP = "http://ns.adobe.com/xdp/"
NS_TPL = "http://www.xfa.org/schema/xfa-template/3.3/"


def xdp(govde, kok='name="data" layout="tb" locale="tr_TR"'):
    """Kök subform'u verilen gövdeyi saran en küçük XDP."""
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<xdp:xdp xmlns:xdp="%s">\n<template xmlns="%s">\n'
            '<subform %s>\n%s\n</subform>\n</template>\n</xdp:xdp>\n' % (NS_XDP, NS_TPL, kok, govde))


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
    """Repo DIŞINDA geçici dizin."""
    return tempfile.TemporaryDirectory(prefix="pdf-output-test-")


def yaz(yol, metin):
    with open(yol, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(metin)
    return yol


def oku(yol):
    with open(yol, encoding="utf-8") as fh:
        return fh.read()
