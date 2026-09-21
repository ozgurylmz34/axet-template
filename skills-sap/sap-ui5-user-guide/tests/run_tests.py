# -*- coding: utf-8 -*-
"""sap-ui5-user-guide çevrimdışı testleri.

Kullanım:
    python run_tests.py            # tümü
    python run_tests.py -k config  # adında 'config' geçen testler
"""
import os
import sys
import unittest

sys.dont_write_bytecode = True
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))


def main(argv):
    pattern = None
    if "-k" in argv:
        i = argv.index("-k")
        if i + 1 >= len(argv) or argv[i + 1].startswith("-"):
            print("HATA: -k bir desen ister (ör. -k config).", file=sys.stderr)
            return 2
        pattern = argv[i + 1]
    sys.path.insert(0, HERE)
    print("KAPSAM (SCOPE): sap-ui5-user-guide testleri — script birim/süreç koşumları (geçici sahte uygulama "
          "dizinleriyle). SAP'ye, ağa bağlanmaz; hiçbir şey kurmaz; tarayıcı AÇMAZ (Chrome'un gerçekten seçildiği "
          "canlı ölçümdür, test değil). Şema-kaynak testi yalnız PLAYWRIGHT_CORE_PATH verilince koşar.")
    loader = unittest.TestLoader()
    if pattern:
        loader.testNamePatterns = ["*%s*" % pattern]
    suite = loader.discover(HERE, pattern="test_*.py", top_level_dir=HERE)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print("SONUÇ: koşan %d · hata %d · başarısız %d · atlanan %d" % (
        result.testsRun, len(result.errors), len(result.failures), len(result.skipped)))
    for test, reason in result.skipped:
        print("  ATLANDI: %s — %s" % (test.id(), reason))
    if result.testsRun == 0:
        print("HATA: HİÇ TEST KOŞMADI — bu 'başarılı' DEĞİLDİR.%s"
              % (" '-k %s' hiçbir test adıyla eşleşmedi (yazım hatası?)." % pattern
                 if pattern else " Keşif hiçbir test bulamadı (tests/ boş ya da import hatası?)."),
              file=sys.stderr)
        return 2
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
