# -*- coding: utf-8 -*-
"""abaplint_run.py çevrimdışı testleri.

abaplint'i gerçekten koşturan tek test `ABAPLINT_SMOKE=1` ile açılır ve `--offline` kullanır (indirme yok).
Diğer testler npx çağırmaz: ayrıştırma/karar birim testleri ve npx'e ulaşmadan biten CLI yolları.
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
SCRIPT = SKILL / 'scripts' / 'abaplint_run.py'


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ar = _load(SCRIPT, 'abaplint_run_under_test')

CLASS_SRC = 'CLASS zcl_demo DEFINITION PUBLIC.\n  PUBLIC SECTION.\n    METHODS run.\nENDCLASS.\n' \
            'CLASS zcl_demo IMPLEMENTATION.\n  METHOD run.\n    RETURN.\n    DATA(lv_a) = 1.\n  ENDMETHOD.\nENDCLASS.\n'


def _cli(*args, path_env=None, cwd=None):
    env = dict(os.environ)
    if path_env is not None:
        env['PATH'] = path_env
    r = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, encoding='utf-8',
                       errors='replace', timeout=600, env=env, cwd=cwd)
    return r.returncode, r.stdout, r.stderr


class ParseEvaluateTests(unittest.TestCase):
    def test_parse_windows_and_posix_paths(self):
        out = ('abaplint 2.120.38\nUsing config: x\n'
               'src\\zcl_demo.clas.abap[8, 5]    - Unreachable code (unreachable_code) [E]\n'
               'src/zdemo.prog.abap[3, 1] - Identical conditions: lv_x = 1 (identical_conditions) [E]\n'
               'abaplint: 2 issue(s) found, 3 file(s) analyzed\n')
        issues, summary = ar.parse_output(out)
        self.assertEqual(summary, (2, 3))
        self.assertEqual([i['file'] for i in issues], ['zcl_demo.clas.abap', 'zdemo.prog.abap'])
        self.assertEqual((issues[0]['line'], issues[0]['col'], issues[0]['rule']), (8, 5, 'unreachable_code'))
        self.assertEqual(issues[1]['message'], 'Identical conditions: lv_x = 1')

    def test_generic_error_is_not_clean(self):
        out = ('generic[1, 1] - Error: No files found, ./src/**/*.* undefined (generic_error) [E]\n'
               'abaplint: 1 issue(s) found, 0 file(s) analyzed\n')
        issues, summary = ar.parse_output(out)
        self.assertEqual(ar.evaluate(1, issues, summary, 0)[0], 3)

    def test_evaluate_matrix(self):
        one = [{'file': 'a.clas.abap', 'line': 1, 'col': 1, 'message': 'm', 'rule': 'r'}]
        self.assertEqual(ar.evaluate(2, [], None, 0)[:3], (3, 'FAIL', False))        # özet yok
        self.assertEqual(ar.evaluate(2, [], (0, 1), 0)[:3], (3, 'FAIL', False))      # dosya sayısı tutmuyor
        self.assertEqual(ar.evaluate(1, [], (1, 1), 0)[:3], (3, 'FAIL', False))      # bulgu sayısı tutmuyor
        self.assertEqual(ar.evaluate(1, [], (0, 1), 0)[:3], (0, 'OK', True))
        self.assertEqual(ar.evaluate(1, [], (0, 1), 2)[:3], (4, 'PARTIAL', True))
        self.assertEqual(ar.evaluate(1, one, (1, 1), 2)[:3], (1, 'FINDING', True))


class ClassifyCollectTests(unittest.TestCase):
    def test_classify(self):
        c = ar.classify
        self.assertEqual(c(Path('x.clas.abap'), CLASS_SRC)[:2], ('.clas.abap', 'zcl_demo'))
        self.assertEqual(c(Path('zif_a.intf.abap'), 'INTERFACE zif_a PUBLIC.\nENDINTERFACE.')[:2],
                         ('.intf.abap', 'zif_a'))
        self.assertEqual(c(Path('zrep.prog.abap'), 'REPORT zrep.\n')[:2], ('.prog.abap', 'zrep'))
        pool = 'CLASS lhc_order DEFINITION DEFERRED.\nCLASS lhc_order DEFINITION INHERITING FROM cbp_x.\nENDCLASS.'
        self.assertEqual(c(Path('zbp_x.ccimp.abap'), pool)[:2], ('.clas.abap', 'lhc_order'))
        self.assertEqual(c(Path('x.clas.abap'), 'CLASS /abc/cl_x DEFINITION.\nENDCLASS.')[1], '#abc#cl_x')
        self.assertEqual(c(Path('zfg.fugr.zfg_fm.abap'), 'FUNCTION zfg_fm.\nENDFUNCTION.')[2], 'fonksiyon-grubu')
        self.assertEqual(c(Path('z_inc.abap'), 'FUNCTION z_fm.\nENDFUNCTION.')[2], 'fonksiyon-grubu')
        self.assertEqual(c(Path('zi_x.ddls.asddls'), 'define view entity ZI_X')[2], 'abap-disi')
        self.assertEqual(c(Path('z_top.abap'), 'DATA gv TYPE i.')[2], 'obje-tipi-taninmadi')

    def test_collect_recurses_and_skips_hidden(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'a' / 'b').mkdir(parents=True)
            (root / '.git').mkdir()
            (root / 'a' / 'b' / 'zcl_x.clas.abap').write_text(CLASS_SRC, encoding='utf-8')
            (root / '.git' / 'zcl_y.clas.abap').write_text(CLASS_SRC, encoding='utf-8')
            files, missing = ar.collect([str(root), str(root / 'a' / 'b' / 'zcl_x.clas.abap'), str(root / 'yok')])
            self.assertEqual([f.name for f in files], ['zcl_x.clas.abap'])
            self.assertEqual(missing, [str(root / 'yok')])


class CliWithoutAbaplintTests(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.tmp = Path(td.name)
        self.cls = self.tmp / 'zcl_demo.clas.abap'
        self.cls.write_text(CLASS_SRC, encoding='utf-8')

    def test_missing_path(self):
        rc, so, se = _cli(str(self.tmp / 'yok.abap'))
        self.assertEqual(rc, 2, so + se)

    def test_missing_config(self):
        rc, so, se = _cli(str(self.cls), '--config', str(self.tmp / 'yok.json'), path_env='', cwd=self.tmp)
        self.assertEqual(rc, 2, so + se)

    def test_unsupported_only_is_partial_without_npx(self):
        fm = self.tmp / 'zfg.fugr.zfg_fm.abap'
        fm.write_text('FUNCTION zfg_fm.\nENDFUNCTION.\n', encoding='utf-8')
        rc, so, se = _cli(str(fm), path_env='', cwd=self.tmp)
        self.assertEqual(rc, 4, so + se)
        self.assertIn('measured=false', so)
        self.assertIn('fonksiyon-grubu', so)

    def test_npx_missing_is_not_clean(self):
        rc, so, se = _cli(str(self.cls), '--json', path_env='', cwd=self.tmp)
        self.assertEqual(rc, 3, so + se)
        rep = json.loads(so)
        self.assertEqual(rep['reason'], 'npx-yok')
        self.assertIn('measured=false', rep['status_line'])
        self.assertEqual(rep['measured'], [])


class ParityWithWriteGateTests(unittest.TestCase):
    def test_pin_equals_write_gate(self):
        if not ar.GATE_SCRIPT.is_file():
            self.skipTest('yazma kapısı script\'i yok')
        m = re.search(r"^ABAPLINT_PIN\s*=\s*'([^']+)'", ar.GATE_SCRIPT.read_text(encoding='utf-8'), re.M)
        self.assertIsNotNone(m)
        self.assertEqual(ar.ABAPLINT_PIN, m.group(1))

    def test_default_config_is_shared_and_syntax_check_off(self):
        self.assertTrue(ar.DEFAULT_CONFIG.is_file(), ar.DEFAULT_CONFIG)
        cfg = json.loads(ar.DEFAULT_CONFIG.read_text(encoding='utf-8'))
        self.assertIs(cfg['rules']['check_syntax'], False)   # KAPSAM notunun dayanağı


@unittest.skipUnless(os.environ.get('ABAPLINT_SMOKE') == '1', 'abaplint duman testi: ABAPLINT_SMOKE=1 (önbellekte pin gerekir)')
class SmokeTests(unittest.TestCase):
    def test_offline_run_finds_unreachable_code(self):
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / 'zcl_demo.clas.abap'
            f.write_text(CLASS_SRC, encoding='utf-8')
            rc, so, se = _cli(str(f), '--offline', '--json')
            self.assertEqual(rc, 1, so + se)
            rep = json.loads(so)
            self.assertEqual([i['rule'] for i in rep['issues']], ['unreachable_code'])
            self.assertEqual(rep['summary'], {'issues': 1, 'files_analyzed': 1})


if __name__ == '__main__':
    unittest.main()
