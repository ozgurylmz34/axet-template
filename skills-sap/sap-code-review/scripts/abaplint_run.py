#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""abaplint_run.py — yerel ABAP kaynaklarını abaplint ile toplu lint eder (kod incelemesi için).

Yazma kapısının parçası DEĞİLDİR: kapıdaki `check_abaplint.py` push anında tek dosyaya bakar. Bu script
inceleme sırasında değişen dosyaların hepsini tek koşumda ölçer ve neyi ÖLÇMEDİĞİNİ ayrıca yazar.
Kural seti ve sürüm pini kapıyla aynıdır (tek kaynak: foundation `lib/abaplint/abaplint.json` ve
`check_abaplint.py` ABAPLINT_PIN; eşitliği `tests/test_abaplint_run.py` zorlar).

Kullanım:
    python abaplint_run.py <dosya|klasör> [...] [--config <json>] [--offline] [--json] [--timeout 300]

Desteklenen: *.clas.abap, *.intf.abap, *.prog.abap ve içeriği `CLASS … DEFINITION` / `INTERFACE` / `REPORT` /
`PROGRAM` ile başlayan diğer *.abap dosyaları (ör. behavior pool `*.ccimp.abap` → sınıf olarak).
Desteklenmeyen (ölçülmez, raporda listelenir): fonksiyon grubu/FM (`*.fugr.*`, `*.func.abap`, `FUNCTION`),
CDS, BDEF, SRVD, XML DDIC ve diğer ABAP dışı dosyalar.

--offline : `npx --no` + npm çevrimdışı; yalnız önbellekteki pinli sürüm kullanılır, indirme yapılmaz.
Varsayılan: `npx --yes <pin>` (önbellekte yoksa npm kayıt defterinden indirir; genel kurulum yapmaz).

Çıkış kodları:
    0 — seçilen tüm dosyalar ölçüldü, bulgu yok
    1 — en az bir bulgu
    2 — kullanım hatası (yol yok, config yok/bozuk)
    3 — ölçüm yapılamadı (npx yok, zaman aşımı, abaplint özet satırı yok, dosya/bulgu sayısı tutmuyor)
    4 — ölçülen dosyalar temiz AMA bazı dosyalar desteklenmediği için ölçülmedi (ya da hiçbiri desteklenmiyor)
Son satır makinece okunur: `ABAPLINT-RUN-STATUS: status=… measured=true|false reason=… files_measured=N
files_unmeasured=M issues=K`.
KAPSAM: `check_syntax` kapalı → ad/tip çözümlemesi yok; temiz sonuç derleme kanıtı değildir.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

if sys.platform == 'win32' and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

SKILLS_SAP = Path(__file__).resolve().parents[2]
FOUNDATION_LIB = SKILLS_SAP / 'sap-adt-foundation' / 'scripts' / 'sapadt' / 'lib'
DEFAULT_CONFIG = FOUNDATION_LIB / 'abaplint' / 'abaplint.json'
GATE_SCRIPT = FOUNDATION_LIB / 'validators' / 'check_abaplint.py'

ABAPLINT_PIN = '@abaplint/cli@2.120.38'   # yazma kapısıyla aynı olmak zorunda (test zorlar)

# abaplint çıktı biçimi (2.120.38'de ölçüldü; Windows'ta yol ayırıcı `\`):
#   src\zcl_x.clas.abap[8, 5]    - Unreachable code (unreachable_code) [E]
#   abaplint: 2 issue(s) found, 4 file(s) analyzed
ISSUE_RE = re.compile(r'^(.*\.abap)\[(\d+),\s*(\d+)\]\s*-\s*(.+?)\s*\(([a-z0-9_]+)\)\s*\[[EWI]\]\s*$')
SUMMARY_RE = re.compile(r'^abaplint:\s*(\d+)\s*issue\(s\)\s*found,\s*(\d+)\s*file\(s\)\s*analyzed\s*$', re.M)

SUPPORTED_SUFFIXES = ('.clas.abap', '.intf.abap', '.prog.abap')
_NAME = r'([/\w]+)'
CLASS_RE = re.compile(r'^\s*class\s+' + _NAME + r'\s+definition\b(?!\s+(?:deferred|load)\b)', re.I | re.M)
INTF_RE = re.compile(r'^\s*interface\s+' + _NAME + r'(?:\s+public)?\s*\.', re.I | re.M)
PROG_RE = re.compile(r'^\s*(?:report|program)\s+' + _NAME, re.I | re.M)
FUNC_RE = re.compile(r'^\s*function\s+' + _NAME + r'\s*\.', re.I | re.M)

SCOPE_NOTE = ('KAPSAM: kural seti yapısal/mantık + hijyen (parser_error, unreachable_code, identical_conditions, '
              'empty_statement, contains_tab, dangerous_statement …). check_syntax KAPALI → ad/tip çözümlemesi yok; '
              'temiz sonuç derleme ya da aktivasyon kanıtı DEĞİLDİR.')


def _abapgit_name(name: str) -> str:
    return name.lower().replace('/', '#')


def classify(path: Path, text: str) -> tuple[str | None, str | None, str]:
    """(suffix, obje adı, neden). Desteklenmiyorsa suffix None ve neden dolu."""
    low = path.name.lower()
    if not low.endswith('.abap'):
        return None, None, 'abap-disi'
    if '.fugr.' in low or low.endswith('.func.abap') or FUNC_RE.search(text):
        return None, None, 'fonksiyon-grubu'
    for suffix, rx in (('.clas.abap', CLASS_RE), ('.intf.abap', INTF_RE), ('.prog.abap', PROG_RE)):
        if low.endswith(suffix):
            m = rx.search(text)
            return suffix, _abapgit_name(m.group(1) if m else low[:-len(suffix)]), ''
    for suffix, rx in (('.clas.abap', CLASS_RE), ('.intf.abap', INTF_RE), ('.prog.abap', PROG_RE)):
        m = rx.search(text)
        if m:
            return suffix, _abapgit_name(m.group(1)), ''
    return None, None, 'obje-tipi-taninmadi'


def collect(paths: list[str]) -> tuple[list[Path], list[str]]:
    """Dosya ve klasörlerden dosya listesi; bulunamayan yollar ayrı döner."""
    files: list[Path] = []
    missing: list[str] = []
    seen: set[Path] = set()
    for raw in paths:
        p = Path(raw)
        if p.is_file():
            cand = [p]
        elif p.is_dir():
            cand = sorted(f for f in p.rglob('*') if f.is_file()
                          and not any(part.startswith('.') for part in f.relative_to(p).parts))
        else:
            missing.append(raw)
            continue
        for f in cand:
            key = f.resolve()
            if key not in seen:
                seen.add(key)
                files.append(f)
    return files, missing


def parse_output(out: str) -> tuple[list[dict], tuple[int, int] | None]:
    issues = []
    for line in out.splitlines():
        m = ISSUE_RE.match(line.strip())
        if m:
            issues.append({'file': m.group(1).replace('\\', '/').rsplit('/', 1)[-1], 'line': int(m.group(2)),
                           'col': int(m.group(3)), 'message': m.group(4), 'rule': m.group(5)})
    sm = SUMMARY_RE.search(out)
    return issues, ((int(sm.group(1)), int(sm.group(2))) if sm else None)


def evaluate(n_written: int, issues: list[dict], summary: tuple[int, int] | None,
             n_unmeasured: int) -> tuple[int, str, bool, str]:
    """(çıkış kodu, status, measured, reason)."""
    if summary is None:
        return 3, 'FAIL', False, 'ozet-satiri-yok'
    said, analyzed = summary
    if analyzed != n_written:
        return 3, 'FAIL', False, f'dosya-sayisi-tutmuyor-{analyzed}/{n_written}'
    if said != len(issues):
        return 3, 'FAIL', False, f'bulgu-sayisi-tutmuyor-{said}/{len(issues)}'
    if issues:
        return 1, 'FINDING', True, f'{len(issues)}-bulgu'
    if n_unmeasured:
        return 4, 'PARTIAL', True, 'kismi-olcum'
    return 0, 'OK', True, 'temiz'


def _status_line(status: str, measured: bool, reason: str, n_measured: int, n_unmeasured: int, n_issues: int) -> str:
    return (f'ABAPLINT-RUN-STATUS: status={status} measured={"true" if measured else "false"} reason={reason} '
            f'files_measured={n_measured} files_unmeasured={n_unmeasured} issues={n_issues}')


def run(args) -> int:
    report: dict = {'pin': ABAPLINT_PIN, 'offline': args.offline, 'measured': [], 'unmeasured': [],
                    'issues': [], 'summary': None, 'scope': SCOPE_NOTE}

    def finish(rc: int, status: str, measured: bool, reason: str) -> int:
        report.update({'exit_code': rc, 'status': status, 'reason': reason})
        line = _status_line(status, measured, reason, len(report['measured']), len(report['unmeasured']),
                            len(report['issues']))
        if args.json:
            report['status_line'] = line
            print(json.dumps(report, ensure_ascii=False, indent=1))
        else:
            for i in report['issues']:
                print(f"{i['path']}:{i['line']}:{i['col']}  {i['rule']}  {i['message']}")
            if any(i['rule'] == 'parser_error' for i in report['issues']):
                print('UYARI: parser_error modern sözdiziminde ayrıştırıcı kaymasından olabilir ama gerçek kaydetme '
                      'hatalarını da gösterir (checklist BE-36/47/48). Yanlış pozitif sayma; kesin karar push/aktivasyon.')
            if report['unmeasured']:
                print(f"ÖLÇÜLMEDİ ({len(report['unmeasured'])}): " +
                      ', '.join(f"{u['path']} [{u['reason']}]" for u in report['unmeasured']))
            if report['summary']:
                print(f"abaplint özeti: {report['summary']['issues']} bulgu · "
                      f"{report['summary']['files_analyzed']} dosya analiz edildi")
            print(SCOPE_NOTE)
            print(line)
        return rc

    files, missing = collect(args.paths)
    if missing:
        print(f'HATA — yol bulunamadı: {", ".join(missing)}', file=sys.stderr)
        return finish(2, 'FAIL', False, 'yol-yok')

    config = Path(args.config) if args.config else DEFAULT_CONFIG
    report['config'] = str(config)
    try:
        cfg = json.loads(config.read_text(encoding='utf-8'))
        if not isinstance(cfg, dict):
            raise ValueError('config bir JSON nesnesi değil')
    except (OSError, ValueError) as exc:
        print(f'HATA — abaplint config okunamadı: {config} ({exc})', file=sys.stderr)
        return finish(2, 'FAIL', False, 'config-yok')

    plan: list[tuple[Path, str]] = []   # (kaynak, geçici dosya adı)
    used: set[str] = set()
    for f in files:
        try:
            text = f.read_text(encoding='utf-8', errors='replace')
        except OSError as exc:
            report['unmeasured'].append({'path': str(f), 'reason': f'okunamadi-{type(exc).__name__}'})
            continue
        suffix, name, reason = classify(f, text)
        if not suffix:
            report['unmeasured'].append({'path': str(f), 'reason': reason})
            continue
        target, n = f'{name}{suffix}', 2
        while target in used:
            target, n = f'{name}_{n}{suffix}', n + 1
        used.add(target)
        plan.append((f, target))

    if not plan:
        print('Desteklenen ABAP dosyası yok — hiçbir şey ölçülmedi.', file=sys.stderr)
        return finish(4, 'SKIPPED', False, 'desteklenen-dosya-yok')

    npx = shutil.which('npx')
    if not npx:
        report['unmeasured'].extend({'path': str(f), 'reason': 'npx-yok'} for f, _ in plan)
        print('ÖLÇÜLEMEDİ — `npx` bulunamadı (Node.js kurulu değil ya da PATH\'te yok). abaplint koşmadı; bu sonuç '
              '"temiz" DEĞİLDİR. Node.js kurulduktan sonra tekrar koş (genel npm kurulumu gerekmez).', file=sys.stderr)
        return finish(3, 'SKIPPED', False, 'npx-yok')

    cfg.setdefault('global', {})['files'] = '/src/**/*.*'
    by_temp = {t: f for f, t in plan}
    cmd = [npx, '--no' if args.offline else '--yes', ABAPLINT_PIN]
    env = dict(os.environ)
    if args.offline:
        env['npm_config_offline'] = 'true'
    with tempfile.TemporaryDirectory(prefix='abaplint_run_') as td:
        tdp = Path(td)
        (tdp / 'src').mkdir()
        for f, t in plan:
            (tdp / 'src' / t).write_text(f.read_text(encoding='utf-8', errors='replace'), encoding='utf-8')
        (tdp / 'abaplint.json').write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding='utf-8')
        try:
            r = subprocess.run(cmd, cwd=str(tdp), capture_output=True, text=True, encoding='utf-8',
                               errors='replace', timeout=args.timeout, env=env)
            out = (r.stdout or '') + '\n' + (r.stderr or '')
        except subprocess.TimeoutExpired:
            report['unmeasured'].extend({'path': str(f), 'reason': 'zaman-asimi'} for f, _ in plan)
            return finish(3, 'FAIL', False, f'zaman-asimi-{args.timeout}s')
        except OSError as exc:
            report['unmeasured'].extend({'path': str(f), 'reason': 'calistirilamadi'} for f, _ in plan)
            print(f'ÖLÇÜLEMEDİ — npx çalıştırılamadı: {type(exc).__name__}: {exc}', file=sys.stderr)
            return finish(3, 'FAIL', False, 'calistirilamadi')

    issues, summary = parse_output(out)
    for i in issues:
        i['path'] = str(by_temp.get(i['file'], i['file']))
    report['issues'] = issues
    report['summary'] = {'issues': summary[0], 'files_analyzed': summary[1]} if summary else None
    rc, status, measured, reason = evaluate(len(plan), issues, summary, len(report['unmeasured']))
    if measured:
        report['measured'] = [str(f) for f, _ in plan]
    else:
        report['unmeasured'].extend({'path': str(f), 'reason': reason} for f, _ in plan)
        tail = out.strip()[-600:]
        print(f'ÖLÇÜLEMEDİ — abaplint çıktısı doğrulanamadı ({reason}); sonuç "temiz" sayılmaz. '
              f'Çevrimdışıysan ve pin önbellekte yoksa --offline başarısız olur. Çıktının sonu:\n{tail}',
              file=sys.stderr)
    return finish(rc, status, measured, reason)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='abaplint toplu lint (inceleme) — ölçülmeyeni ayrıca raporlar')
    ap.add_argument('paths', nargs='+', help='dosya ya da klasör')
    ap.add_argument('--config', help=f'abaplint config (varsayılan: {DEFAULT_CONFIG})')
    ap.add_argument('--offline', action='store_true', help='indirme yok: npx --no + npm çevrimdışı önbellek')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--timeout', type=int, default=300, help='saniye')
    return run(ap.parse_args(argv))


if __name__ == '__main__':
    sys.exit(main())
