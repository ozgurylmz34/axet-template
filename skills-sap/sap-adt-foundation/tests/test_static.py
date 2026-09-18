# -*- coding: utf-8 -*-
"""Statik kontroller: derleme · yasak dizgeler · gate-atlatma taraması."""
from __future__ import annotations

import py_compile
import re
import shutil
import tempfile
import unittest
from pathlib import Path

import _helpers as H

KOK = H.SKILLS_SAP  # skills-sap/

# Dizgeler parçalanarak yazılır: bu dosyanın kendisi taramada eşleşmesin.
YASAK_PY = {
    "kaynak-yol": re.compile(re.escape("C:" + "\\" + "IX") + r"|C:/" + "IX", re.I),
    "kaynak-adi": re.compile("DEV" + "_CORE"),
    "mcp-import": re.compile(r"^\s*(?:import|from)\s+(?:fast)?" + "mcp" + r"\b", re.M),
    "fast-mcp": re.compile("fast" + "mcp", re.I),
    "mcp-sunucu-paketi": re.compile("mcp" + "_servers"),
    "ide-proje-env": re.compile("CLAUDE" + "_PROJECT_DIR"),
}

# ── gate-atlatma taraması ───────────────────────────────────────────────────────────────
# Kural: `sapadt` içindeki yazma metodlarını ÇAĞIRAN bir dosya `check_write(...)` çağrısı da taşımalı.
# AST ile yapılır: docstring/mesaj metnindeki adlar (ör. "adt_push_source(... ) ile düzelt") çağrı
# SAYILMAZ — ilk sürüm düz regex'ti ve iki validator'ın yardım metnini yanlış-pozitif işaretledi.
YAZMA_METODLARI = re.compile(
    r"^(create_[a-z_]+|push_object|activate_object|delete_object|lock_object|unlock_object|"
    r"set_object_source|run_classrun|syntax_check)$")
YAZMA_ARACLARI = re.compile(
    r"^adt_(post_shell|push_source|delete|activate|publish_service|classrun|domain_create|"
    r"dtel_create|struct_create|syntax_check|unit_run|screen_generate|msgclass_write|set_description)$")
# Örnek bağlantı şablonunda yer tutucusuz yazılabilen, SIR OLMAYAN anahtarlar (varsayılan davranış değerleri).
SIR_OLMAYAN_ORNEK = frozenset({"ADT_SAP_SSL_VERIFY", "ADT_SAP_TIER"})

IZINLI = (  # yazma metodlarını TANIMLAYAN / içeriden bağlayan modüller + testler
    "sap-adt-foundation/scripts/sapadt/lib/sap_adt_lib.py",
    "sap-adt-foundation/scripts/sapadt/lib/sap_client.py",
    "sap-adt-foundation/scripts/sapadt/lib/rap_service.py",
    "sap-adt-foundation/scripts/sapadt/lib/auth/",
    "sap-adt-foundation/scripts/sapadt/tools/",
    "sap-adt-foundation/tests/",
)


def _cagri_adlari(metin: str) -> set[str]:
    import ast
    adlar = set()
    for dugum in ast.walk(ast.parse(metin)):
        if isinstance(dugum, ast.Call):
            f = dugum.func
            if isinstance(f, ast.Attribute):
                adlar.add(f.attr)
            elif isinstance(f, ast.Name):
                adlar.add(f.id)
    return adlar


# Standart kütüphane çağrıları `create_*` desenine uyar ama SAP'ye yazmaz. Ölçüldü 2026-09-13: başka bir skill'in
# `ssl.create_default_context()` çağrısı taramayı yanlış-pozitif kırdı. Liste dar tutulur (yalnız bilinen stdlib adları).
STDLIB_ISTISNA = frozenset({"create_default_context", "create_connection", "create_unverified_context"})


def gate_atlatan_mi(metin: str) -> bool:
    adlar = _cagri_adlari(metin) - STDLIB_ISTISNA
    yazma = any(YAZMA_METODLARI.match(a) or YAZMA_ARACLARI.match(a) for a in adlar)
    return yazma and "check_write" not in adlar


def py_dosyalari():
    return [p for p in KOK.rglob("*.py") if "__pycache__" not in p.parts]


class Statik(unittest.TestCase):
    def test_derleme(self):
        tmp = Path(tempfile.mkdtemp(prefix="axet_pyc_"))
        hatalar = []
        try:
            for i, p in enumerate(py_dosyalari()):
                try:
                    py_compile.compile(str(p), cfile=str(tmp / f"{i}.pyc"), doraise=True)
                except py_compile.PyCompileError as exc:
                    hatalar.append(f"{p}: {exc}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        H.kaydet("9a py_compile tüm .py", "0 hata", f"{len(py_dosyalari())} dosya, {len(hatalar)} hata", not hatalar)
        self.assertEqual(hatalar, [])

    def test_yasak_dizgeler(self):
        bulunan = []
        for p in py_dosyalari():
            metin = p.read_text(encoding="utf-8", errors="replace")
            for ad, rx in YASAK_PY.items():
                for m in rx.finditer(metin):
                    bulunan.append(f"{p.relative_to(KOK)}:{metin.count(chr(10), 0, m.start()) + 1}: {ad}")
        impl = H.FOUNDATION / "IMPLEMENTATION.md"
        if impl.is_file():
            if YASAK_PY["kaynak-yol"].search(impl.read_text(encoding="utf-8")):
                bulunan.append("IMPLEMENTATION.md: kaynak yol")
        # 2026-09-13: `.gitignore` `!.conn*.example` istisnasıyla uyumlu — örnek şablon SERBEST, ama değer
        # satırlarında YALNIZ <...> yer tutucu (ya da tier/TLS gibi sır olmayan sabit) bulunabilir.
        conn = [str(p.relative_to(KOK)) for p in KOK.rglob(".conn*") if not p.name.endswith(".example")]
        conn += [str(p.relative_to(KOK)) for p in KOK.rglob("*.env")]
        ornek_ihlal = []
        for p in KOK.rglob(".conn*.example"):
            for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                s = ln.strip()
                if not s or s.startswith("#") or "=" not in s:
                    continue
                k, v = (x.strip() for x in s.split("=", 1))
                if k not in SIR_OLMAYAN_ORNEK and not re.fullmatch(r"(?:https?://)?<[A-Z_]+>(?::<[A-Z_]+>)?", v):
                    ornek_ihlal.append(f"{p.relative_to(KOK)}:{i}: {k}")
        H.kaydet("9b yasak dizge (" + " · ".join(YASAK_PY) + ")",
                 "0 eşleşme", f"{len(bulunan)} eşleşme: {bulunan[:5]}", not bulunan)
        H.kaydet("9c repoda .conn*/*.env dosyası (*.example hariç)", "0", str(len(conn)), not conn)
        H.kaydet("9c2 .conn*.example yalnız <...> yer tutucu", "0 ihlal", str(ornek_ihlal), not ornek_ihlal)
        self.assertEqual(bulunan, [])
        self.assertEqual(conn, [])
        self.assertEqual(ornek_ihlal, [])

    def test_gate_atlatma_taramasi(self):
        # Negatif/pozitif kontrol: tarayıcının kendisi çalışıyor mu?
        self.assertTrue(gate_atlatan_mi("from sap_client import SAPClient\nSAPClient().push_object('Z', 'class')\n"))
        self.assertFalse(gate_atlatan_mi("r = gate.check_write('t', p)\nc.push_object('Z', 'class')\n"))
        self.assertTrue(gate_atlatan_mi("from sapadt.tools.atom import adt_activate\nadt_activate('ZX')\n"))
        self.assertFalse(gate_atlatan_mi("import ssl\nctx = ssl.create_default_context()\n"))
        self.assertTrue(gate_atlatan_mi("import ssl\nctx = ssl.create_default_context()\nc.create_domain('ZX')\n"))
        ihlal = []
        for p in py_dosyalari():
            rel = p.relative_to(KOK).as_posix()
            if any(rel.startswith(i) for i in IZINLI):
                continue
            if gate_atlatan_mi(p.read_text(encoding="utf-8", errors="replace")):
                ihlal.append(rel)
        H.kaydet("9d gate-atlatma taraması (yazma çağrısı + check_write yok)", "0 dosya",
                 f"{len(ihlal)} dosya: {ihlal}", not ihlal)
        self.assertEqual(ihlal, [])


if __name__ == "__main__":
    unittest.main()
