#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Template script testleri (stdlib unittest). Model çağırmaz, SAP'ye bağlanmaz, gerçek global aXet config'ine ve
template klonunun dosyalarına yazmaz: her test geçici dizin + geçici XDG_CONFIG_HOME + izole git config kullanır.

    python tests/run_tests.py            # tümü (PARALEL — varsayılan)
    python tests/run_tests.py -k precommit   # ada göre süz
    python tests/run_tests.py -j 1       # sıralı koş (hata ayıklarken)

PARALELLİK (2026-09-20). Testler `modul.Sınıf` kümelerine bölünür ve her küme AYRI bir
işlemde koşar; sonuçlar toplanır. Ölçülen sebep: takım tek işlemde **2411 sn (≈40 dk)**
sürüyordu (CI, 2026-09-20) ve bu süre üç yeri birden zehirliyordu — ⓐ tüketicinin
`%guncelle` beklemesi ⓑ GitHub Actions kotası (private repo + windows-latest = 2x çarpan)
ⓒ geliştirme döngüsü. Süre test SAYISINDAN değil, her testin kendi sahte yayın + tüketici
klonunu `git` ile kurmasından geliyor (`test_guncelle.py`: 154 test / 242 alt-süreç çağrısı).
İşlem başına izolasyon zaten testlerin tasarımında var (geçici dizin + geçici config), o
yüzden paralellik test anlamını DEĞİŞTİRMEZ; yalnız duvar saatini böler.

⚠ KAPSAM: paralel kol testleri yeniden SIRALAMAZ, yalnız dağıtır. Bir test komşusunun
bıraktığı duruma gizliden bağımlıysa bu kol onu AÇIĞA ÇIKARIR (sessizce gizlemez) — böyle
bir kırmızı gerçek bir kusurdur, paralelliğin yan etkisi değil. `-j 1` ile doğrulanabilir.

Çıkış: 0 tümü geçti · 1 en az bir başarısız · 2 KULLANIM HATASI (ölçüm yapılmadı).
"""
from __future__ import annotations

import json
import os
import subprocess
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

KAPSAM_SATIRI = ("KAPSAM — bakılmayanlar: aXet'in bağlamı fiilen yüklediği (doctor.py --live) · canlı SAP · "
                 "izin kurallarının aXet'te fiilen blokladığı · Linux/macOS'ta hook çalışması (Windows'ta ölçüldü)")
ISARET = "AXET-PARALEL-SONUC "


def _yukleyici(desen: str | None) -> unittest.TestLoader:
    loader = unittest.TestLoader()
    if desen:
        loader.testNamePatterns = ["*" + desen + "*"]
    return loader


def _kimlikleri_topla(desen: str | None) -> list[str]:
    """Keşfedilen (ve `-k` ile süzülen) test kimlikleri. Yükleme hatası da bir kimliktir."""
    suite = _yukleyici(desen).discover(str(BURASI), pattern="test_*.py", top_level_dir=str(BURASI))
    out: list[str] = []

    def gez(s):
        for x in s:
            if isinstance(x, unittest.TestSuite):
                gez(x)
            else:
                out.append(x.id())

    gez(suite)
    return out


def _kume(kimlik: str) -> str:
    """`modul.Sinif.metot` → `modul.Sinif` (dağıtım birimi)."""
    return kimlik.rsplit(".", 1)[0]


def _sirali(kimlikler: list[str] | None, desen: str | None, sessiz: bool) -> tuple[int, dict]:
    loader = _yukleyici(None if kimlikler else desen)
    if kimlikler:
        suite = loader.loadTestsFromNames(kimlikler)
    else:
        suite = loader.discover(str(BURASI), pattern="test_*.py", top_level_dir=str(BURASI))
    akis = open(os.devnull, "w", encoding="utf-8") if sessiz else sys.stderr
    sonuc = unittest.TextTestRunner(verbosity=0 if sessiz else 2, stream=akis).run(suite)
    ozet = {"test": sonuc.testsRun, "failure": len(sonuc.failures), "error": len(sonuc.errors),
            "skip": len(sonuc.skipped),
            "kirmizilar": [{"kimlik": t.id(), "iz": iz} for t, iz in sonuc.failures + sonuc.errors]}
    return (0 if sonuc.wasSuccessful() else 1), ozet


def _isci_kos(kimlikler: list[str]) -> dict:
    r = subprocess.run([sys.executable, "-X", "utf8", str(Path(__file__).resolve()),
                        "--isci"] + kimlikler,
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       cwd=str(BURASI.parent))
    for satir in (r.stdout or "").splitlines():
        if satir.startswith(ISARET):
            return json.loads(satir[len(ISARET):])
    # İşçi hiç özet basmadıysa bu SESSİZ YEŞİL olamaz: çökmeyi bir "error" gibi raporla.
    return {"test": 0, "failure": 0, "error": 1, "skip": 0,
            "kirmizilar": [{"kimlik": "<işçi çöktü: %d test>" % len(kimlikler),
                            "iz": "rc=%s\n%s\n%s" % (r.returncode, (r.stdout or "")[-1500:],
                                                     (r.stderr or "")[-1500:])}]}


def _paralel(kimlikler: list[str], is_sayisi: int) -> tuple[int, dict]:
    from concurrent.futures import ThreadPoolExecutor  # noqa: PLC0415
    kumeler: dict[str, list[str]] = {}
    for k in kimlikler:
        kumeler.setdefault(_kume(k), []).append(k)
    # Büyük küme önce: en uzun iş en erken başlasın (duvar saati max(küme) tarafından belirlenir).
    sirali = sorted(kumeler.values(), key=len, reverse=True)
    toplam: dict = {"test": 0, "failure": 0, "error": 0, "skip": 0, "kirmizilar": []}
    with ThreadPoolExecutor(max_workers=is_sayisi) as havuz:
        for ozet in havuz.map(_isci_kos, sirali):
            for alan in ("test", "failure", "error", "skip"):
                toplam[alan] += ozet[alan]
            toplam["kirmizilar"] += ozet["kirmizilar"]
    return (0 if not toplam["failure"] and not toplam["error"] else 1), toplam


def _is_sayisi(argv: list[str]) -> int | None:
    if "-j" not in argv:
        return None
    i = argv.index("-j")
    if i + 1 >= len(argv) or not argv[i + 1].isdigit() or int(argv[i + 1]) < 1:
        print("HATA: -j pozitif bir tamsayı ister (ör. -j 4).", file=sys.stderr)
        raise SystemExit(2)
    return int(argv[i + 1])


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if "--isci" in argv:                      # alt-süreç kolu: verilen kimlikleri koş, özet bas
        kod, ozet = _sirali(argv[argv.index("--isci") + 1:], None, sessiz=True)
        print(ISARET + json.dumps(ozet, ensure_ascii=False))
        return kod

    desen = None
    if "-k" in argv:
        i = argv.index("-k")
        if i + 1 >= len(argv) or argv[i + 1].startswith("-"):
            print("HATA: -k bir desen ister (ör. -k precommit).", file=sys.stderr)
            return 2
        desen = argv[i + 1]

    istenen = _is_sayisi(argv)
    kimlikler = _kimlikleri_topla(desen)
    # ⛔ "0 test" hükmü HER İKİ kolda da aynı: sayıyı koşumdan ÖNCE biliyoruz.
    if not kimlikler:
        print("SONUÇ: 0 test · 0 failure · 0 error · 0 skip · 0 sn")
        print(KAPSAM_SATIRI)
        print("HATA: HİÇ TEST KOŞMADI — bu 'başarılı' DEĞİLDİR.%s"
              % (" '-k %s' hiçbir test adıyla eşleşmedi (yazım hatası?)." % desen
                 if desen else " Keşif hiçbir test bulamadı (tests/ boş ya da import hatası?)."),
              file=sys.stderr)
        return 2

    kume_sayisi = len({_kume(k) for k in kimlikler})
    is_sayisi = istenen if istenen else max(1, min(os.cpu_count() or 1, 8, kume_sayisi))
    basla = time.time()
    if is_sayisi == 1:
        kod, ozet = _sirali(kimlikler if desen else None, desen, sessiz=False)
    else:
        kod, ozet = _paralel(kimlikler, is_sayisi)
        for kirmizi in ozet["kirmizilar"]:
            print("\n%s\nKIRMIZI: %s\n%s\n%s" % ("=" * 70, kirmizi["kimlik"], "-" * 70, kirmizi["iz"]),
                  file=sys.stderr)
    gecen = time.time() - basla

    print("\n" + "=" * 80)
    print("SONUÇ: %d test · %d failure · %d error · %d skip · %.0f sn%s"
          % (ozet["test"], ozet["failure"], ozet["error"], ozet["skip"], gecen,
             (" · %d paralel iş (%d küme)" % (is_sayisi, kume_sayisi)) if is_sayisi > 1 else " · sıralı"))
    print(KAPSAM_SATIRI)
    if ozet["test"] == 0:
        print("HATA: HİÇ TEST KOŞMADI — bu 'başarılı' DEĞİLDİR.", file=sys.stderr)
        return 2
    return kod


if __name__ == "__main__":
    raise SystemExit(main())
