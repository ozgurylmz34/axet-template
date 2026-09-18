# -*- coding: utf-8 -*-
"""Skill yapısı: frontmatter, açıklama uzunluğu, dosya/atıf varlığı, iz taraması, script kapsam beyanı."""
import os
import re
import sys
import unittest

from _common import REPO, SCRIPTS, SKILL

TEXT_EXT = (".md", ".py", ".js", ".json", ".cds", ".bdef", ".csv", ".abap", ".html", ".txt")
EXPECTED_SCRIPTS = ["doc_tools.py", "build_doc_pdf.py", "build_kd_pdf.py", "capture_kd_screens.js", "html_to_pdf.js",
                    "gen_field_table.py", "doc_equivalence_check.py", "program_to_spec.py", "verify_doc_html.py",
                    "check_fs_no_analysis_log.py"]
EXPECTED_DOCS = ["SKILL.md", "references/fs-authoring.md", "references/ts-authoring.md", "references/kd-authoring.md",
                 "references/doc-checklist.md", "references/traceability.md", "references/pdf-with-screenshots.md",
                 "references/live-confirmation-tour.md", "templates/FS-template.md", "templates/TS-template.md",
                 "templates/KD-template.md"]


def _read(rel):
    with open(os.path.join(SKILL, rel), encoding="utf-8") as fh:
        return fh.read()


def _skill_files():
    for root, dirs, files in os.walk(SKILL):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            if f.lower().endswith(TEXT_EXT):
                yield os.path.join(root, f)


def _frontmatter(text):
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", text, re.S)
    return m.group(1) if m else None


class SkillStructureTest(unittest.TestCase):
    def test_expected_files_exist(self):
        for rel in EXPECTED_DOCS:
            self.assertTrue(os.path.isfile(os.path.join(SKILL, rel)), rel)
        for s in EXPECTED_SCRIPTS:
            self.assertTrue(os.path.isfile(os.path.join(SCRIPTS, s)), s)

    def test_frontmatter_local_rules(self):
        fm = _frontmatter(_read("SKILL.md"))
        self.assertIsNotNone(fm, "frontmatter yok")
        self.assertRegex(fm, r"(?m)^name: sap-fs-ts-docs$")
        m = re.search(r"(?ms)^description: >\s*\n((?:[ \t]+\S.*\n?)+)", fm + "\n")
        self.assertIsNotNone(m, "description '>' katlanmış blok olmalı")
        desc = " ".join(l.strip() for l in m.group(1).splitlines() if l.strip())
        self.assertLessEqual(len(desc), 900, "description %d karakter (hedef ≤ 900, sınır 1024)" % len(desc))
        self.assertGreater(len(desc), 200)
        for line in fm.splitlines():
            if line and not line[0].isspace():
                key, _, value = line.partition(":")
                self.assertNotIn(": ", value.strip() if value.strip() != ">" else "", "tırnaksız ': ' — %s" % line)

    def test_frontmatter_doctor(self):
        sys.path.insert(0, os.path.join(REPO, "scripts"))
        try:
            import doctor  # noqa: WPS433
            problems_fn = doctor.frontmatter_problems
        except Exception as exc:  # doctor bu ortamda içe aktarılamıyorsa yerel kural testi yine koşar
            self.skipTest("doctor.frontmatter_problems içe aktarılamadı: %s" % exc)
        finally:
            sys.path.pop(0)
        self.assertEqual([], problems_fn(_read("SKILL.md")))

    def test_referenced_paths_exist(self):
        """Dokümanlarda `references/…`, `templates/…`, `scripts/…` atıfları bu skill'de ya da başka bir skill'de var."""
        roots = [SKILL, REPO]
        for group in ("skills-sap", "skills"):
            base = os.path.join(REPO, group)
            if os.path.isdir(base):
                roots += [os.path.join(base, d) for d in os.listdir(base)]
        missing = []
        for rel in EXPECTED_DOCS:
            for m in re.finditer(r"(?<![\w<>/-])((?:skills/[\w-]+/)?(?:references|templates|scripts)/[\w.-]+\.(?:md|py|js))",
                                 _read(rel)):
                path = m.group(1)
                if not any(os.path.isfile(os.path.join(r, path)) for r in roots):
                    missing.append("%s → %s" % (rel, path))
        self.assertEqual([], missing)

    def test_skill_links_exist(self):
        names = set()
        for group in ("skills-sap", "skills"):
            base = os.path.join(REPO, group)
            if os.path.isdir(base):
                names |= {d for d in os.listdir(base) if os.path.isfile(os.path.join(base, d, "SKILL.md"))}
        bad = []
        for rel in EXPECTED_DOCS:
            for m in re.finditer(r"%([a-z][a-z0-9]*(?:-[a-z0-9]+)+)", _read(rel)):
                if m.group(1) not in names:
                    bad.append("%s → %%%s" % (rel, m.group(1)))
        self.assertEqual([], bad)

    def test_trace_grep_clean(self):
        forbidden = ["C:" + "\\" + "IX", "C:/" + "IX", "DEV" + "_CORE", "mcp" + "__", "." + "claude",
                     "CLAUDE" + ".md", "ZSD" + "0", "FIT" + "_SE", "ZSD" + "_ONAY", "ADR " + "00", "Claude" + " Code"]
        url = re.compile(r"https?://(?!localhost[:/]|example\.invalid[/\"])")
        email = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z]{2,}\b")
        hits = []
        for path in _skill_files():
            with open(path, encoding="utf-8", errors="replace") as fh:
                for i, line in enumerate(fh, 1):
                    for f in forbidden:
                        if f in line:
                            hits.append("%s:%d: %s" % (os.path.relpath(path, SKILL), i, f))
                    if url.search(line):
                        hits.append("%s:%d: url" % (os.path.relpath(path, SKILL), i))
                    if email.search(line):
                        hits.append("%s:%d: e-posta" % (os.path.relpath(path, SKILL), i))
        self.assertEqual([], hits)

    def test_scripts_declare_scope_and_no_mcp(self):
        for s in EXPECTED_SCRIPTS:
            with open(os.path.join(SCRIPTS, s), encoding="utf-8") as fh:
                text = fh.read()
            self.assertIn("KAPSAM (SCOPE)", text, s)
            self.assertNotRegex(text, r"(?m)^\s*(import|from)\s+mcp\b", s)
            self.assertNotIn("sap_adt_lib", text, s)


if __name__ == "__main__":
    unittest.main()
