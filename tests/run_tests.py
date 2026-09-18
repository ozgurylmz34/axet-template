#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Template script testleri (stdlib unittest). Model çağırmaz, SAP'ye bağlanmaz, gerçek global aXet config'ine ve
template klonunun dosyalarına yazmaz: her test geçici dizin + geçici XDG_CONFIG_HOME + izole git config kullanır.

    python tests/run_tests.py            # tümü
    python tests/run_tests.py -k precommit   # ada göre süz

Çıkış: 0 tümü geçti · 1 en az bir başarısız.
"""
from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass

sys.dont_write_bytecode = True
BURASI = Path(__file__).resolve().parent
for _p in (BURASI, BURASI.parent / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    loader = unittest.TestLoader()
    _k_desen = None
    if "-k" in argv:
        i = argv.index("-k")
        if i + 1 >= len(argv) or argv[i + 1].startswith("-"):
            print("HATA: -k bir desen ister (ör. -k precommit).", file=sys.stderr)
            return 2
        _k_desen = argv[i + 1]
        loader.testNamePatterns = [f"*{_k_desen}*"]
    suite = loader.discover(str(BURASI), pattern="test_*.py", top_level_dir=str(BURASI))
    basla = time.time()
    sonuc = unittest.TextTestRunner(verbosity=2).run(suite)
    print("\n" + "=" * 80)
    print(f"SONUÇ: {sonuc.testsRun} test · {len(sonuc.failures)} failure · {len(sonuc.errors)} error · "
          f"{len(sonuc.skipped)} skip · {time.time() - basla:.0f} sn")
    print("KAPSAM — bakılmayanlar: aXet'in bağlamı fiilen yüklediği (doctor.py --live) · canlı SAP · "
          "izin kurallarının aXet'te fiilen blokladığı · Linux/macOS'ta hook çalışması (Windows'ta ölçüldü)")
    if sonuc.testsRun == 0:
        print("HATA: HİÇ TEST KOŞMADI — bu 'başarılı' DEĞİLDİR.%s"
              % (" '-k %s' hiçbir test adıyla eşleşmedi (yazım hatası?)." % _k_desen
                 if _k_desen else " Keşif hiçbir test bulamadı (tests/ boş ya da import hatası?)."),
              file=sys.stderr)
        return 2
    return 0 if sonuc.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
