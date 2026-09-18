# -*- coding: utf-8 -*-
"""Kontrol listeleri ve referansların iç tutarlılığı — koddan türetilir, elle tutulan liste yok.

Zorlananlar:
- satır biçimi (6 sütun, önem kümesi), kimlik tekliği, SKILL §6'daki "sıradaki kimlik"lerin güncelliği
- Otomasyon iddiaları: `görev` → `check_x.py` (ÖNEM) çifti gerçekten yazma kapısı zincirinde mi
- adı geçen her .py / .md / %skill / adt_* aracı / başka skill kimliği gerçekten var mı
- validator-map.md §1-§2 tablolarının `_reviewer.py` ve `run_review.py` ile eşitliği
- SKILL.md frontmatter (ad = klasör, açıklama ≤ 900) ve iz/kimlik sızıntısı yasağı
Foundation dosyaları yalnız okunur (ast ile; import edilmez).
"""
import ast
import re
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
SKILLS_SAP = SKILL.parent
TEMPLATE = SKILLS_SAP.parent
REFS = SKILL / 'references'
SAPADT = SKILLS_SAP / 'sap-adt-foundation' / 'scripts' / 'sapadt'
RUN_REVIEW = SAPADT / 'lib' / 'validators' / 'run_review.py'
REVIEWER = SAPADT / '_reviewer.py'
TOOL_CATALOG = SKILLS_SAP / 'sap-adt-foundation' / 'references' / 'tool-catalog.md'

CHECKLISTS = sorted(REFS.glob('checklist-*.md'))
DOCS = [SKILL / 'SKILL.md'] + sorted(REFS.glob('*.md'))
ROW_RE = re.compile(r'^\|\s*((BE|SR|OD|CC)-(\d+)[a-z]?)\s*\|')
CELL_SPLIT = re.compile(r'(?<!\\)\|')
SEVERITIES = {'BLOCKER', 'WARNING', 'WARNING · strict: BLOCKER'}
PAIR_RE = re.compile(r'`([a-z0-9_]+)`\s*→\s*`(check_[a-z0-9_]+\.py)`(?:\s*\((BLOCKER|WARNING))?')
EML_TOKENS = {'cid', 'param', 'tky', 'pky', 'key', 'control', 'data', 'pid', 'is', 'fail', 'msg', 'element', 'target'}


def _text(p: Path) -> str:
    return p.read_text(encoding='utf-8')


def _literal(path: Path, name: str):
    for node in ast.parse(_text(path)).body:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        if any(isinstance(t, ast.Name) and t.id == name for t in targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f'{name} bulunamadı: {path}')


def _rows():
    for f in CHECKLISTS:
        for n, line in enumerate(_text(f).splitlines(), 1):
            m = ROW_RE.match(line)
            if m:
                cells = [c.strip() for c in CELL_SPLIT.split(line.strip())[1:-1]]
                yield f, n, m, cells


def _section(text: str, number: int) -> str:
    m = re.search(rf'^## {number}\..*?(?=^## |\Z)', text, re.M | re.S)
    return m.group(0) if m else ''


class ChecklistRowTests(unittest.TestCase):
    def test_checklists_present(self):
        names = {f.name for f in CHECKLISTS}
        for expected in ('checklist-common.md', 'checklist-abap.md', 'checklist-cds-ddic.md', 'checklist-rap.md',
                         'checklist-odata-backend.md', 'checklist-clean-core.md'):
            self.assertIn(expected, names)

    def test_rows_well_formed(self):
        count = 0
        for f, n, _, cells in _rows():
            count += 1
            where = f'{f.name}:{n}'
            self.assertEqual(len(cells), 6, f'{where} sütun sayısı {len(cells)}')
            self.assertTrue(all(cells), f'{where} boş hücre')
            self.assertIn(cells[3], SEVERITIES, f'{where} önem {cells[3]!r}')
        self.assertGreater(count, 50)

    def test_ids_unique(self):
        seen = {}
        for f, n, m, _ in _rows():
            self.assertNotIn(m.group(1), seen, f'{m.group(1)} tekrar: {f.name}:{n} ve {seen.get(m.group(1))}')
            seen[m.group(1)] = f'{f.name}:{n}'

    def test_next_free_ids_in_skill_are_ahead(self):
        maxima = {}
        for _, _, m, _ in _rows():
            maxima[m.group(2)] = max(maxima.get(m.group(2), 0), int(m.group(3)))
        section6 = re.search(r'^### 6\..*?(?=^## )', _text(SKILL / 'SKILL.md'), re.M | re.S).group(0)
        announced = dict((p, int(n)) for p, n in re.findall(r'`(BE|OD|CC|SR)-(\d+)`', section6))
        self.assertEqual(set(announced), set(maxima), 'SKILL §6 her önek için sıradaki kimliği vermeli')
        for prefix, nxt in announced.items():
            self.assertGreater(nxt, maxima[prefix], f'SKILL §6 {prefix}-{nxt} kullanılmış ya da geride')


class ReferenceExistenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.chain = _literal(RUN_REVIEW, 'TASK_VALIDATORS')
        cls.pairs = {(task, script): sev for task, items in cls.chain.items() for script, sev, _ in items}
        cls.py_files = [p.as_posix() for p in SKILLS_SAP.rglob('*.py') if '__pycache__' not in p.parts]
        cls.external = set(re.findall(r"'(check_[a-z0-9_]+\.py)':\s*\(", _text(RUN_REVIEW)))

    def test_automation_pairs_are_real_chain_members(self):
        found = 0
        for doc in DOCS:
            for task, script, sev in PAIR_RE.findall(_text(doc)):
                found += 1
                self.assertIn((task, script), self.pairs, f'{doc.name}: `{task}` → `{script}` zincirde yok')
                if sev:
                    self.assertEqual(sev, self.pairs[(task, script)], f'{doc.name}: {task}/{script} önemi')
        self.assertGreater(found, 5)

    def test_named_python_files_exist(self):
        for doc in DOCS:
            for token in set(re.findall(r'(?<![\w.-])((?:[\w.-]+/)*[\w.-]+\.py)\b', _text(doc))):
                if token in self.external:
                    continue
                suffix = '/' + token.lstrip('/')
                ok = any(p.endswith(suffix) for p in self.py_files)
                self.assertTrue(ok, f'{doc.name}: adı geçen `{token}` template içinde yok')

    def test_named_markdown_files_exist(self):
        project_files = {'SPEC.md', '.rules.md', 'SESSION_NOTES.md', 'AGENTS.md'}
        for doc in DOCS:
            for token in set(re.findall(r'`((?:[\w.-]+/)*[\w.-]+\.md)`', _text(doc))):
                if token in project_files:
                    continue
                cands = [TEMPLATE / token, SKILLS_SAP / token, SKILL / token, REFS / token]
                cands += [d / token for d in SKILLS_SAP.iterdir() if d.is_dir()]
                cands += [d / 'references' / token for d in SKILLS_SAP.iterdir() if d.is_dir()]
                self.assertTrue(any(c.is_file() for c in cands), f'{doc.name}: `{token}` bulunamadı')

    def test_skill_references_exist(self):
        for doc in DOCS:
            for name in set(re.findall(r'(?<![\w%])%([a-z][a-z0-9-]*)', _text(doc))):
                if name in EML_TOKENS:
                    continue
                exists = (SKILLS_SAP / name).is_dir() or (TEMPLATE / 'skills' / name).is_dir()
                self.assertTrue(exists, f'{doc.name}: %{name} skill klasörü yok')

    def test_adt_tools_exist_in_catalog(self):
        catalog = _text(TOOL_CATALOG)
        for doc in DOCS:
            for tool in set(re.findall(r'\b(adt_[a-z_]+[a-z])\b', _text(doc))):
                self.assertIn(tool, catalog, f'{doc.name}: {tool} araç kataloğunda yok')

    def test_cross_skill_ids_exist(self):
        others = '\n'.join(_text(p) for d in SKILLS_SAP.iterdir() if d.is_dir() and d != SKILL
                           for p in d.rglob('*.md'))
        for doc in DOCS:
            for ident in set(re.findall(r'\b((?:CDS|DE|STR|TBL|CLC)-[A-Z0-9]+(?:-\d+)?)\b', _text(doc))):
                self.assertRegex(others, rf'\b{re.escape(ident)}\b', f'{doc.name}: {ident} başka skill\'de yok')


class ValidatorMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = _text(REFS / 'validator-map.md')

    def test_push_mapping_matches_reviewer(self):
        obj = _literal(REVIEWER, 'OBJECT_TYPE_TO_TASK')
        comp = _literal(REVIEWER, 'COMPOSITE_TOOL_TO_TASK')
        rows = re.findall(r'^\|\s*`([a-z_/]+)`\s*\|\s*(?:`([a-z_0-9]+)`|—)', _section(self.doc, 1), re.M)
        self.assertGreater(len(rows), 10)
        for key, task in rows:
            table = comp if key.startswith('adt_') else obj
            self.assertIn(key, table, f'validator-map §1: `{key}` eşlemede yok')
            self.assertEqual(table[key], task or None, f'validator-map §1: `{key}`')

    def test_k1_push_keys_listed(self):
        # Bug gate 2026-09-14 (B5): §1 yalnız satır→kod yönünde eşleniyordu; koddaki K1 anahtarı (`prog/i`)
        # tabloda yoksa test kırılmıyordu. K1 görevlerine giden HER anahtar tabloda olmalı.
        obj = _literal(REVIEWER, 'OBJECT_TYPE_TO_TASK')
        rows = set(re.findall(r'^\|\s*`([a-z_/]+)`\s*\|', _section(self.doc, 1), re.M))
        eksik = sorted(k for k, t in obj.items() if t in ('program_push', 'interface_push') and k not in rows)
        self.assertEqual(eksik, [], f'validator-map §1: K1 anahtarları tabloda yok: {eksik}')

    def test_chain_table_equals_run_review(self):
        chain = _literal(RUN_REVIEW, 'TASK_VALIDATORS')
        sec = _section(self.doc, 2)
        doc_pairs = set(re.findall(r'^\|\s*`([a-z_0-9]+)`\s*\|\s*`(check_[a-z0-9_]+\.py)`\s*\|\s*(BLOCKER|WARNING)\s*\|',
                                   sec, re.M))
        code_pairs = {(t, s, sev) for t, items in chain.items() for s, sev, _ in items}
        self.assertEqual(doc_pairs, code_pairs, 'validator-map §2 zincir tablosu run_review ile aynı değil')
        doc_empty = set(re.findall(r'^\|\s*`([a-z_0-9]+)`\s*\|\s*—\s*\|', sec, re.M))
        self.assertEqual(doc_empty, {t for t, items in chain.items() if not items}, 'boş zincirler')


class SkillHygieneTests(unittest.TestCase):
    def test_frontmatter(self):
        text = _text(SKILL / 'SKILL.md')
        m = re.match(r'^---\n(.*?)\n---\n', text, re.S)
        self.assertIsNotNone(m, 'frontmatter yok')
        fm = m.group(1)
        self.assertRegex(fm, rf'(?m)^name:\s*{re.escape(SKILL.name)}\s*$')
        dm = re.search(r'(?ms)^description:\s*>\s*\n((?:[ \t]+.*\n?)+)', fm + '\n')
        self.assertIsNotNone(dm, 'description katlanmış (>) blok değil')
        desc = ' '.join(line.strip() for line in dm.group(1).splitlines() if line.strip())
        self.assertLessEqual(len(desc), 900, f'description {len(desc)} karakter')

    def test_no_forbidden_traces(self):
        forbidden = ['C:' + '\\IX', 'dev' + '_core', 'mcp' + '__', '.cla' + 'ude', 'zsd' + '0', 'ix-' + 'gate']
        for p in SKILL.rglob('*'):
            if not p.is_file() or '__pycache__' in p.parts:
                continue
            text = p.read_text(encoding='utf-8', errors='replace')
            low = text.lower()
            for bad in forbidden:
                hay = text if bad.startswith('C:') else low
                self.assertNotIn(bad, hay, f'{p.relative_to(SKILL)} yasak iz içeriyor: {bad!r}')
            for host in re.findall(r'https?://([^/\s)\'"`\]]+)', text):
                self.assertIn(host, {'github.com'}, f'{p.relative_to(SKILL)}: izin verilmeyen adres {host}')


if __name__ == '__main__':
    unittest.main()
