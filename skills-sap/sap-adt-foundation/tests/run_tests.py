#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Çevrimdışı test koşucusu (stdlib unittest). Gerçek SAP'ye bağlanmaz.

    python tests/run_tests.py            # tümü
    python tests/run_tests.py -k intake  # ada göre süz (unittest -k)

Çıkış: 0 tümü geçti · 1 en az bir başarısız.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass

sys.dont_write_bytecode = True
BURASI = Path(__file__).resolve().parent
if str(BURASI) not in sys.path:
    sys.path.insert(0, str(BURASI))


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    loader = unittest.TestLoader()
    _k_desen = None
    if "-k" in argv:
        i = argv.index("-k")
        if i + 1 >= len(argv) or argv[i + 1].startswith("-"):
            print("HATA: -k bir desen ister (ör. -k query).", file=sys.stderr)
            return 2
        _k_desen = argv[i + 1]
        loader.testNamePatterns = [f"*{_k_desen}*"]
    suite = loader.discover(str(BURASI), pattern="test_*.py", top_level_dir=str(BURASI))
    sonuc = unittest.TextTestRunner(verbosity=2).run(suite)

    import _helpers as H
    print("\n" + "=" * 100)
    print(f"{'SENARYO':60} | {'BEKLENEN':24} | GERÇEKLEŞEN")
    print("-" * 100)
    for ad, beklenen, gercek, ok in H.SONUCLAR:
        print(f"{'OK  ' if ok else 'FAIL'} {str(ad)[:55]:55} | {str(beklenen)[:24]:24} | {gercek}")
    gecen = sum(1 for *_x, ok in H.SONUCLAR if ok)
    print("-" * 100)
    print(f"Senaryo satırı: {gecen}/{len(H.SONUCLAR)} OK · unittest: {sonuc.testsRun} test, "
          f"{len(sonuc.failures)} failure, {len(sonuc.errors)} error")
    if sonuc.testsRun == 0:
        print("HATA: HİÇ TEST KOŞMADI — bu 'başarılı' DEĞİLDİR.%s"
              % (" '-k %s' hiçbir test adıyla eşleşmedi (yazım hatası?)." % _k_desen
                 if _k_desen else " Keşif hiçbir test bulamadı (tests/ boş ya da import hatası?)."),
              file=sys.stderr)
        return 2
    return 0 if sonuc.wasSuccessful() and gecen == len(H.SONUCLAR) else 1


if __name__ == "__main__":
    raise SystemExit(main())
