#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""released_successors.py — released halef haritası: yerel dosyadan yenile, obje ara, tazelik durumu.

Harita TEK kaynaktır ve yazma kapısındaki `check_released_objects.py`'nin okuduğu dosyadır:
    <skills-sap>/sap-adt-foundation/scripts/sapadt/lib/data/released_successors.json
Bu script o dosyayı varsayılan olarak okur/yazar; kopya harita tutulmaz.

AĞ ERİŞİMİ YOKTUR (bilinçli). Kaynak, SAP'nin açık "ABAP cloudification" GitHub reposunda yayımlanan nesne
yayın bilgisi JSON'udur (on-premise / Private Cloud için `objectReleaseInfo_PCELatest.json`). Kullanıcı
dosyayı tarayıcıyla indirir, `refresh --source <dosya>` ile verir.

İNDİRME TALİMATI (kullanıcı için, tek adım):
    https://github.com/SAP/abap-atc-cr-cv-s4hc  ->  src/objectReleaseInfo_PCELatest.json  ->  "Download raw file"
    -> kaydet, sonra:  python skills-sap/sap-code-review/scripts/released_successors.py refresh --source <indirilen.json>
    (S/4HANA Cloud Public Edition kullanıyorsan dosya adı farklıdır — aynı repodaki `src/` klasörüne bak.)
    Tazelik: ... released_successors.py status   -> exit 0 taze · 1 bayat (varsayılan eşik 90 gün)

Neden otomatik indirmiyoruz: ağ erişiminin olmaması BİLİNÇLİ bir karardır, eksiklik değil. Bu haritayı
canlı bir HTTP servisinden çeken üçüncü parti araçlar var (ör. SAP'nin aynı reposunu saran açık kaynak
bir servis); sorgulanan adlar standart SAP obje adları olsa bile, dışarıya çağrı yapmak `sapadt/redact.py`
ile kurulan mahremiyet duruşunu bozar ve bu depo için ölçülmemiş bir bağımlılık ekler. Kazanç yalnız
tazeleme ergonomisidir — doğrulama gücü artmaz. Değerlendirildi ve ALINMADI (2026-09-15).

Alt komutlar:
    refresh --source <json> [--out <json>] [--dry-run] [--allow-shrink] [--today YYYY-MM-DD]
    lookup <OBJE> [<OBJE> ...] [--data <json>] [--json]
    status [--data <json>] [--today YYYY-MM-DD] [--max-age-days 90] [--json]

Çıkış kodları:
    refresh : 0 yazıldı ya da --dry-run geçerli · 2 kaynak/veri hatası (hedef dosya DEĞİŞMEDİ)
              · 3 küçülme reddi (yeni tablo bölümü eskisinin yarısından az; --allow-shrink ile bilinçli geçilir)
    lookup  : 0 en az bir obje haritada · 1 hiçbiri haritada yok (released olduğu anlamına GELMEZ) · 2 veri yok/bozuk
    status  : 0 taze · 1 bayat (ya da üretim tarihi okunamadı) · 2 veri yok/bozuk/boş

Fail-open dersi (neden bu kadar katı): harita hiç üretilmediğinde ya da boş kaldığında yazma kapısındaki
validator "veri yok → SKIP, exit 0" yolundan geçer ve aylarca hiçbir şeye bakmadan temiz görünür. Bu yüzden:
boş sonuç yazılmaz, bozuk kaynak mevcut dosyayı ezmez, yazım atomiktir, yazılan dosya geri okunup doğrulanır,
`lookup` ve `status` veri yoksa gürültülü (exit 2) biter.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

if sys.platform == 'win32' and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

SKILLS_SAP = Path(__file__).resolve().parents[2]
DEFAULT_DATA = (SKILLS_SAP / 'sap-adt-foundation' / 'scripts' / 'sapadt' / 'lib' / 'data'
                / 'released_successors.json')

# TADIR obje tipi → harita bölümü. Yazma kapısı validator'ı yalnız `tables`'ı okur; diğer bölümler
# `lookup` ipucudur (sınıf/FM/arayüz için otorite ATC "Usage of APIs" kontrolüdür).
TYPE_SECTION = {'TABL': 'tables', 'CLAS': 'classes', 'FUGR': 'functions', 'FUNC': 'functions',
                'INTF': 'interfaces'}
SECTIONS = ('tables', 'classes', 'functions', 'interfaces')
RELEVANT_STATES = {'notToBeReleased', 'deprecated', 'released_with_restrictions'}
MAX_AGE_DAYS = 90
SHRINK_RATIO = 0.5


class DataError(Exception):
    """Harita ya da kaynak dosyası kullanılamaz."""


# ── yardımcılar ──────────────────────────────────────────────────────────────

def _today(value: str | None) -> date:
    if not value:
        return date.today()
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise DataError(f'--today geçersiz (YYYY-MM-DD bekleniyor): {value}') from exc


def _read_json(path: Path) -> object:
    if not path.is_file():
        raise DataError(f'dosya yok: {path}')
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DataError(f'JSON okunamadı: {path} ({type(exc).__name__}: {exc})') from exc


def _successor_names(raw) -> list[str]:
    """Halef adları. Liste olmayan değer (ör. düz metin) geçersizdir → boş liste."""
    if not isinstance(raw, list):
        return []
    names = []
    for s in raw:
        if isinstance(s, dict):
            name = s.get('tadirObjName') or s.get('objectKey')
        elif isinstance(s, str):
            name = s
        else:
            name = None
        if isinstance(name, str) and name.strip():
            names.append(name.strip())
    return names


# ── yenileme ────────────────────────────────────────────────────────────────

def build_map(source: object) -> tuple[dict, dict]:
    """SAP nesne yayın bilgisi JSON'undan harita bölümlerini üretir. (bölümler, sayaçlar) döner."""
    if not isinstance(source, dict) or not isinstance(source.get('objectReleaseInfo'), list):
        raise DataError('kaynakta `objectReleaseInfo` listesi yok — beklenen SAP nesne yayın bilgisi JSON\'u değil')
    records = source['objectReleaseInfo']
    sections: dict[str, dict] = {s: {} for s in SECTIONS}
    stats = {'kayit': len(records), 'alinan': 0, 'gecersiz_kayit': 0, 'halefsiz': 0,
             'tip_disi': 0, 'durum_disi': 0, 'adsiz': 0}
    for rec in records:
        if not isinstance(rec, dict):
            stats['gecersiz_kayit'] += 1
            continue
        section = TYPE_SECTION.get(str(rec.get('objectType', '')).upper())
        if not section:
            stats['tip_disi'] += 1
            continue
        if rec.get('state') not in RELEVANT_STATES:
            stats['durum_disi'] += 1
            continue
        successors = _successor_names(rec.get('successors'))
        if not successors:
            stats['halefsiz'] += 1
            continue
        name = str(rec.get('objectKey') or rec.get('tadirObjName') or '').strip().upper()
        if not name:
            stats['adsiz'] += 1
            continue
        sections[section][name] = {
            'successors': successors,
            'state': rec.get('state'),
            'classification': rec.get('successorClassification'),
            'app': rec.get('applicationComponent'),
        }
        stats['alinan'] += 1
    if records and stats['gecersiz_kayit'] == len(records):
        raise DataError('kaynaktaki kayıtların hiçbiri nesne değil')
    return sections, stats


def _existing_table_count(path: Path) -> int | None:
    try:
        data = _read_json(path)
    except DataError:
        return None
    tables = data.get('tables') if isinstance(data, dict) else None
    return len(tables) if isinstance(tables, dict) else None


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.released_successors.', suffix='.tmp', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def cmd_refresh(args) -> int:
    src = Path(args.source)
    out = Path(args.out) if args.out else DEFAULT_DATA
    try:
        today = _today(args.today)
        sections, stats = build_map(_read_json(src))
    except DataError as exc:
        print(f'HATA — {exc}. Hedef dosya DEĞİŞMEDİ: {out}', file=sys.stderr)
        return 2

    counts = {s: len(sections[s]) for s in SECTIONS}
    print(f'kaynak: {src.name} · kayıt {stats["kayit"]} · alınan {stats["alinan"]} · '
          f'atlanan: tip dışı {stats["tip_disi"]}, durum dışı {stats["durum_disi"]}, halefsiz {stats["halefsiz"]}, '
          f'adsız {stats["adsiz"]}, geçersiz {stats["gecersiz_kayit"]}')
    print(f'bölümler: {counts}')

    if counts['tables'] == 0:
        print('HATA — tablo bölümü boş çıktı; yazılmadı. Boş harita yazma kapısındaki validator\'ı hiçbir şeye '
              f'bakmadan geçirir (fail-open). Kaynak dosyayı kontrol et. Hedef DEĞİŞMEDİ: {out}', file=sys.stderr)
        return 2

    old = _existing_table_count(out)
    if old and counts['tables'] < old * SHRINK_RATIO and not args.allow_shrink:
        print(f'RED — tablo bölümü {old} → {counts["tables"]} (yarıdan fazla küçülme). Yanlış dosya (ör. farklı ürün '
              'hattının JSON\'u) olabilir. Bilinçliyse --allow-shrink ile tekrar koş. Hedef DEĞİŞMEDİ.',
              file=sys.stderr)
        return 3

    payload = {
        '_meta': {
            'purpose': 'Clean core: released olmayan standart obje → released halef (SAP nesne yayın bilgisi JSON\'undan üretildi).',
            'source': f'SAP nesne yayın bilgisi JSON\'u (yerel dosya: {src.name})',
            'generated': today.isoformat(),
            'counts': counts,
            'note': 'Yazma kapısı validator\'ı (check_released_objects.py) yalnız `tables` bölümünü okur. '
                    'classes/functions/interfaces yalnız ipucudur; tüm obje tipleri için otorite ATC "Usage of APIs".',
            'refresh': 'python <skills-sap>/sap-code-review/scripts/released_successors.py refresh --source <json>',
        },
    }
    payload.update(sections)
    text = json.dumps(payload, ensure_ascii=False, indent=1) + '\n'

    if args.dry_run:
        print(f'DRY-RUN — geçerli; yazılmadı. Hedef: {out} (mevcut tablo sayısı: {old if old is not None else "yok"})')
        return 0

    try:
        _atomic_write(out, text)
        check = load_data(out)
    except (OSError, DataError) as exc:
        print(f'HATA — yazma ya da geri okuma başarısız: {exc}', file=sys.stderr)
        return 2
    print(f'yazıldı ve geri okundu: {out} · tablo {len(check["tables"])} · üretim {today.isoformat()}')
    return 0


# ── okuma: veri doğrulama, lookup, status ────────────────────────────────────

def load_data(path: Path) -> dict:
    """Haritayı okur ve şemasını doğrular. Kullanılamazsa DataError."""
    data = _read_json(path)
    if not isinstance(data, dict):
        raise DataError(f'harita bir JSON nesnesi değil: {path}')
    missing = [s for s in SECTIONS if not isinstance(data.get(s), dict)]
    if missing:
        raise DataError(f'harita bölümü eksik ya da nesne değil: {", ".join(missing)}')
    if not data['tables']:
        raise DataError('`tables` bölümü boş — yazma kapısındaki validator hiçbir şeye bakmadan geçer')
    bad = [f'{s}/{k}' for s in SECTIONS for k, v in data[s].items()
           if not isinstance(v, dict) or not _successor_names(v.get('successors'))]
    if bad:
        raise DataError(f'{len(bad)} kayıt geçersiz (successors listesi yok/boş), ör. {bad[:3]}')
    return data


def cmd_lookup(args) -> int:
    path = Path(args.data) if args.data else DEFAULT_DATA
    try:
        data = load_data(path)
    except DataError as exc:
        print(f'HATA — {exc}. Halef bilgisi ÖLÇÜLEMEDİ.', file=sys.stderr)
        return 2
    rows = []
    for raw in args.names:
        name = raw.strip().upper()
        hits = [(s, data[s][name]) for s in SECTIONS if name in data[s]]
        if not hits:
            rows.append({'name': name, 'found': False})
        for section, entry in hits:
            rows.append({'name': name, 'found': True, 'section': section,
                         'successors': _successor_names(entry.get('successors')),
                         'state': entry.get('state'), 'classification': entry.get('classification'),
                         'app': entry.get('app')})
    if args.json:
        print(json.dumps({'data': str(path), 'generated': data.get('_meta', {}).get('generated'),
                          'results': rows}, ensure_ascii=False, indent=1))
    else:
        for r in rows:
            if r['found']:
                print(f"{r['name']}  [{r['section']}]  {r['state']}  → {', '.join(r['successors'])}"
                      f"  ({r['classification'] or '-'} · {r['app'] or '-'})")
            else:
                print(f"{r['name']}  haritada yok — bu 'released' demek DEĞİL: harita yalnız halefi olan "
                      "released-olmayan objeleri taşır. Otorite: ATC \"Usage of APIs\" (adt_atc_check).")
        if any(r['found'] and r['section'] == 'tables' for r in rows):
            print('NOT: halefe geçmeden önce halefin @AccessControl.authorizationCheck değerini canlı oku; '
                  '#CHECK halef bir kontrolü besliyorsa 0 satır = fail-open (checklist BE-68).')
    return 0 if any(r['found'] for r in rows) else 1


def cmd_status(args) -> int:
    path = Path(args.data) if args.data else DEFAULT_DATA
    try:
        today = _today(args.today)
        data = load_data(path)
    except DataError as exc:
        msg = f'VERİ HATASI — {exc}'
        if args.json:
            print(json.dumps({'data': str(path), 'verdict': 'VERI_HATASI', 'reason': str(exc)}, ensure_ascii=False))
        else:
            print(msg, file=sys.stderr)
        return 2
    meta = data.get('_meta', {}) if isinstance(data.get('_meta'), dict) else {}
    counts = {s: len(data[s]) for s in SECTIONS}
    generated = meta.get('generated')
    age = None
    try:
        age = (today - date.fromisoformat(str(generated))).days
    except ValueError:
        pass
    if age is None:
        verdict, rc, reason = 'BAYAT', 1, 'üretim tarihi (_meta.generated) okunamadı → tazelik ölçülemedi, bayat sayıldı'
    elif age > args.max_age_days:
        verdict, rc, reason = 'BAYAT', 1, f'{age} gün > {args.max_age_days} gün'
    else:
        verdict, rc, reason = 'TAZE', 0, f'{age} gün ≤ {args.max_age_days} gün'
    scope = ('KAPSAM: yalnız dosya yaşı ve şema ölçülür. S/4 sürüm yükseltmesi tarihi bu script tarafından '
             'bilinmez — yükseltmeden sonra yenilenmediyse harita bayattır (DOĞRULANMADI).')
    if args.json:
        print(json.dumps({'data': str(path), 'verdict': verdict, 'reason': reason, 'generated': generated,
                          'age_days': age, 'counts': counts, 'source': meta.get('source'), 'scope': scope},
                         ensure_ascii=False, indent=1))
    else:
        print(f'harita: {path}')
        print(f'üretim: {generated} · kaynak: {meta.get("source", "-")}')
        print(f'bölümler: {counts}')
        print(f'{verdict} — {reason}')
        print(scope)
        if rc:
            print('Yenile: SAP nesne yayın bilgisi JSON\'unu indir → refresh --source <dosya> (SKILL references/clean-core.md §5)')
    return rc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='Released halef haritası: refresh (yerel dosya) · lookup · status')
    sub = ap.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('refresh', help='yerel SAP nesne yayın bilgisi JSON\'undan haritayı yeniden üret')
    p.add_argument('--source', required=True, help='indirilmiş objectReleaseInfo JSON dosyası')
    p.add_argument('--out', help=f'hedef harita (varsayılan: {DEFAULT_DATA})')
    p.add_argument('--dry-run', action='store_true', help='yazmadan doğrula ve say')
    p.add_argument('--allow-shrink', action='store_true', help='tablo bölümünün yarıdan fazla küçülmesine izin ver')
    p.add_argument('--today', help='üretim tarihi olarak yazılacak gün (test için; YYYY-MM-DD)')
    p.set_defaults(func=cmd_refresh)

    p = sub.add_parser('lookup', help='obje adına göre halef ara')
    p.add_argument('names', nargs='+')
    p.add_argument('--data', help=f'harita (varsayılan: {DEFAULT_DATA})')
    p.add_argument('--json', action='store_true')
    p.set_defaults(func=cmd_lookup)

    p = sub.add_parser('status', help='harita tazeliği ve şeması')
    p.add_argument('--data', help=f'harita (varsayılan: {DEFAULT_DATA})')
    p.add_argument('--today', help='bugün yerine kullanılacak gün (test için; YYYY-MM-DD)')
    p.add_argument('--max-age-days', type=int, default=MAX_AGE_DAYS)
    p.add_argument('--json', action='store_true')
    p.set_defaults(func=cmd_status)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
