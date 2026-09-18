# -*- coding: utf-8 -*-
"""released_successors.py çevrimdışı testleri + yazma kapısı validator'ıyla uyumluluk.

Ağ yok, canlı SAP yok. Foundation dosyalarına YAZILMAZ: validator yalnız okunur/import edilir,
harita her testte geçici dizinde üretilir.
"""
import ast
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
SCRIPT = SKILL / 'scripts' / 'released_successors.py'
VALIDATOR = (SKILL.parent / 'sap-adt-foundation' / 'scripts' / 'sapadt' / 'lib' / 'validators'
             / 'check_released_objects.py')


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rs = _load(SCRIPT, 'released_successors_under_test')


def _rec(otype, key, state, successors, **extra):
    d = {'objectType': otype, 'objectKey': key, 'state': state, 'successors': successors}
    d.update(extra)
    return d


SOURCE = {'objectReleaseInfo': [
    _rec('TABL', 'MARA', 'notToBeReleased', [{'tadirObjName': 'I_PRODUCT', 'objectKey': 'I_PRODUCT'},
                                             {'tadirObjName': 'I_PRODUCTSALES'}],
         successorClassification='multipleObjects', applicationComponent='LO-MD-MM'),
    _rec('TABL', 'kna1', 'notToBeReleased', [{'objectKey': 'I_CUSTOMER'}]),       # küçük harf + objectKey yedeği
    _rec('TABL', 'T000', 'released', [{'tadirObjName': 'X'}]),                     # durum dışı
    _rec('TABL', 'VBUK', 'deprecated', []),                                        # halefsiz
    _rec('DDLS', 'I_OLD', 'deprecated', [{'tadirObjName': 'I_NEW'}]),              # tip dışı
    _rec('CLAS', 'CL_OLD', 'deprecated', [{'tadirObjName': 'CL_NEW'}]),
    _rec('FUNC', 'BAPI_OLD', 'notToBeReleased', [{'tadirObjName': 'I_NEWVIEW'}]),
    _rec('INTF', 'IF_OLD', 'released_with_restrictions', [{'tadirObjName': 'IF_NEW'}]),
    'bozuk-kayit',
]}


def _cli(*args):
    r = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True,
                       encoding='utf-8', errors='replace', timeout=120)
    return r.returncode, r.stdout, r.stderr


def _write_map(path: Path, tables: dict, generated='2026-01-01', **sections):
    data = {'_meta': {'generated': generated}, 'tables': tables,
            'classes': {}, 'functions': {}, 'interfaces': {}}
    data.update(sections)
    path.write_text(json.dumps(data), encoding='utf-8')


def _tables(n):
    return {f'T{i:03d}': {'successors': [f'I_T{i:03d}'], 'state': 'notToBeReleased'} for i in range(n)}


class BuildMapTests(unittest.TestCase):
    def test_sections_and_filters(self):
        sections, stats = rs.build_map(SOURCE)
        self.assertEqual(set(sections['tables']), {'MARA', 'KNA1'})
        self.assertEqual(sections['tables']['MARA']['successors'], ['I_PRODUCT', 'I_PRODUCTSALES'])
        self.assertEqual(sections['tables']['MARA']['classification'], 'multipleObjects')
        self.assertEqual(sections['tables']['KNA1']['successors'], ['I_CUSTOMER'])
        self.assertEqual(set(sections['classes']), {'CL_OLD'})
        self.assertEqual(set(sections['functions']), {'BAPI_OLD'})
        self.assertEqual(set(sections['interfaces']), {'IF_OLD'})
        self.assertEqual(stats['durum_disi'], 1)
        self.assertEqual(stats['halefsiz'], 1)
        self.assertEqual(stats['tip_disi'], 1)
        self.assertEqual(stats['gecersiz_kayit'], 1)

    def test_rejects_wrong_shape(self):
        for bad in ({}, [], {'objectReleaseInfo': 'x'}, {'objectReleaseInfo': ['a', 1]}):
            with self.assertRaises(rs.DataError):
                rs.build_map(bad)


class RefreshCliTests(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.tmp = Path(td.name)
        self.src = self.tmp / 'objectReleaseInfo.json'
        self.src.write_text(json.dumps(SOURCE), encoding='utf-8')

    def test_refresh_writes_readable_map_and_creates_parent(self):
        out = self.tmp / 'yeni' / 'alt' / 'released_successors.json'   # klasör yok (fail-open dersi)
        rc, so, se = _cli('refresh', '--source', str(self.src), '--out', str(out), '--today', '2026-09-01')
        self.assertEqual(rc, 0, se)
        data = json.loads(out.read_text(encoding='utf-8'))
        self.assertEqual(data['_meta']['generated'], '2026-09-01')
        self.assertEqual(data['_meta']['counts']['tables'], 2)
        self.assertEqual(sorted(data['tables']), ['KNA1', 'MARA'])
        rc, so, se = _cli('status', '--data', str(out), '--today', '2026-09-02')
        self.assertEqual(rc, 0, so + se)
        self.assertFalse([p for p in out.parent.iterdir() if p.suffix == '.tmp'], 'geçici dosya kaldı')

    def test_invalid_source_leaves_target_untouched(self):
        out = self.tmp / 'map.json'
        out.write_bytes(b'ONCEKI-ICERIK')
        for content in ('{bozuk json', json.dumps({'baska': []})):
            self.src.write_text(content, encoding='utf-8')
            rc, _, se = _cli('refresh', '--source', str(self.src), '--out', str(out))
            self.assertEqual(rc, 2, se)
            self.assertEqual(out.read_bytes(), b'ONCEKI-ICERIK')

    def test_missing_source(self):
        rc, _, se = _cli('refresh', '--source', str(self.tmp / 'yok.json'), '--out', str(self.tmp / 'm.json'))
        self.assertEqual(rc, 2)
        self.assertFalse((self.tmp / 'm.json').exists())

    def test_empty_tables_not_written(self):
        self.src.write_text(json.dumps({'objectReleaseInfo': [
            _rec('CLAS', 'CL_OLD', 'deprecated', [{'tadirObjName': 'CL_NEW'}])]}), encoding='utf-8')
        out = self.tmp / 'm.json'
        rc, _, se = _cli('refresh', '--source', str(self.src), '--out', str(out))
        self.assertEqual(rc, 2)
        self.assertIn('fail-open', se)
        self.assertFalse(out.exists())

    def test_shrink_refused_unless_allowed(self):
        out = self.tmp / 'm.json'
        _write_map(out, _tables(10))
        before = out.read_bytes()
        rc, _, se = _cli('refresh', '--source', str(self.src), '--out', str(out))
        self.assertEqual(rc, 3, se)
        self.assertEqual(out.read_bytes(), before)
        rc, _, se = _cli('refresh', '--source', str(self.src), '--out', str(out), '--allow-shrink')
        self.assertEqual(rc, 0, se)
        self.assertEqual(len(json.loads(out.read_text(encoding='utf-8'))['tables']), 2)

    def test_dry_run_does_not_write(self):
        out = self.tmp / 'm.json'
        rc, so, se = _cli('refresh', '--source', str(self.src), '--out', str(out), '--dry-run')
        self.assertEqual(rc, 0, se)
        self.assertIn('DRY-RUN', so)
        self.assertFalse(out.exists())


class LookupStatusTests(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.tmp = Path(td.name)
        self.map = self.tmp / 'm.json'
        sections, _ = rs.build_map(SOURCE)
        _write_map(self.map, sections['tables'], generated='2026-06-01',
                   classes=sections['classes'], functions=sections['functions'], interfaces=sections['interfaces'])

    def test_lookup_found_not_found_and_case(self):
        rc, so, _ = _cli('lookup', 'mara', 'cl_old', '--data', str(self.map))
        self.assertEqual(rc, 0)
        self.assertIn('I_PRODUCT', so)
        self.assertIn('[classes]', so)
        self.assertIn('BE-68', so)
        rc, so, _ = _cli('lookup', 'ZFOO', '--data', str(self.map))
        self.assertEqual(rc, 1)
        self.assertIn("'released' demek DEĞİL", so)

    def test_lookup_json(self):
        rc, so, _ = _cli('lookup', 'KNA1', 'ZFOO', '--data', str(self.map), '--json')
        self.assertEqual(rc, 0)
        res = json.loads(so)['results']
        self.assertEqual([r['found'] for r in res], [True, False])

    def test_lookup_missing_data_is_loud(self):
        rc, _, se = _cli('lookup', 'MARA', '--data', str(self.tmp / 'yok.json'))
        self.assertEqual(rc, 2)
        self.assertIn('ÖLÇÜLEMEDİ', se)

    def test_status_fresh_stale_and_errors(self):
        self.assertEqual(_cli('status', '--data', str(self.map), '--today', '2026-06-30')[0], 0)
        rc, so, _ = _cli('status', '--data', str(self.map), '--today', '2026-12-31', '--json')
        self.assertEqual(rc, 1)
        self.assertEqual(json.loads(so)['verdict'], 'BAYAT')
        self.assertEqual(_cli('status', '--data', str(self.tmp / 'yok.json'))[0], 2)
        empty = self.tmp / 'bos.json'
        _write_map(empty, {})
        self.assertEqual(_cli('status', '--data', str(empty))[0], 2)
        broken = self.tmp / 'kirik.json'
        _write_map(broken, {'MARA': {'successors': 'I_PRODUCT'}})
        self.assertEqual(_cli('status', '--data', str(broken))[0], 2)
        nodate = self.tmp / 'tarihsiz.json'
        _write_map(nodate, _tables(1), generated=None)
        self.assertEqual(_cli('status', '--data', str(nodate))[0], 1)


class ConsumerCompatibilityTests(unittest.TestCase):
    """Üretilen harita yazma kapısındaki validator tarafından okunuyor mu (import; foundation'a yazılmaz)."""

    def setUp(self):
        if not VALIDATOR.is_file():
            self.skipTest(f'validator yok: {VALIDATOR}')
        self.v = _load(VALIDATOR, 'check_released_objects_under_test')
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.tmp = Path(td.name)

    def _refresh(self) -> Path:
        src = self.tmp / 'src.json'
        src.write_text(json.dumps(SOURCE), encoding='utf-8')
        out = self.tmp / 'map.json'
        self.assertEqual(_cli('refresh', '--source', str(src), '--out', str(out))[0], 0)
        return out

    def test_default_path_is_validator_data_path(self):
        self.assertEqual(os.path.normcase(str(rs.DEFAULT_DATA.resolve())),
                         os.path.normcase(str(Path(self.v.DATA_PATH).resolve())))

    def test_validator_reads_generated_map(self):
        self.v.DATA_PATH = self._refresh()
        table_map = self.v.load_map()
        self.assertIn('MARA', table_map)
        findings = self.v.scan('select matnr from mara', table_map)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]['successors'], ['I_PRODUCT', 'I_PRODUCTSALES'])

    def test_validator_scope_limits_documented_in_clean_core_md(self):
        """clean-core.md §4'teki kör noktaların ölçümü (kod okumasına değil çalıştırmaya dayanır)."""
        self.v.DATA_PATH = self._refresh()
        m = self.v.load_map()
        self.assertEqual(self.v.scan('select matnr from\n  mara', m), [], 'çok satırlı FROM')
        self.assertEqual(self.v.scan('association [0..1] to mara as _Product on 1 = 1', m), [], 'association')
        self.assertEqual(self.v.scan('" select matnr from mara', m), [], 'satır yorumu atlanır')
        self.assertEqual(len(self.v.scan('/* select matnr from mara */', m)), 1, 'blok yorum atlanmaz')

    def test_validator_skip_is_visible_without_data(self):
        self.v.DATA_PATH = self.tmp / 'yok.json'
        artefakt = self.tmp / 'z.clas.abap'
        artefakt.write_text('select matnr from mara into table @data(x).', encoding='utf-8')
        buf = io.StringIO()
        old_argv = sys.argv
        try:
            sys.argv = ['check_released_objects.py', str(artefakt)]
            with contextlib.redirect_stdout(buf):
                rc = self.v.main()
        finally:
            sys.argv = old_argv
        self.assertEqual(rc, 0)
        self.assertIn('SKIP', buf.getvalue())
        # 2026-09-14: veri yokken durum satırı basılır → run_review SKIP'i PASS saymaz (önceden fail-open idi)
        self.assertIn('status=SKIPPED measured=false', buf.getvalue())

    def test_shipped_map_is_valid(self):
        if not rs.DEFAULT_DATA.is_file():
            self.skipTest('dağıtılan harita yok')
        data = rs.load_data(rs.DEFAULT_DATA)
        self.assertGreater(len(data['tables']), 0)


class NoNetworkTests(unittest.TestCase):
    def test_script_imports_no_network_modules(self):
        tree = ast.parse(SCRIPT.read_text(encoding='utf-8'))
        mods = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods.update(a.name.split('.')[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods.add(node.module.split('.')[0])
        self.assertFalse(mods & {'urllib', 'http', 'socket', 'ssl', 'ftplib', 'requests'}, mods)


if __name__ == '__main__':
    unittest.main()
