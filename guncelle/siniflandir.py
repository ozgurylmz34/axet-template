#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""aXet mimari haritası sınıflandırıcısı — `guncelle/harita.json`'u okur, bir yolu sınıfına atar
ve haritanın kendisini denetler.

Neden burada: `harita.json` public sürüme giden `guncelle/` klasöründe durur (TASARIM §3;
`maintenance/` public'e girmez — `maintenance/yayin_hazirla.py:27`). Bu modülü tüketici klonunda
`scripts/guncelle.py` (P2) import edecek, dolayısıyla veriyle aynı klasörde ve public tarafta olmalı.
`maintenance/guncelle-mimari/classify.py` bu modülün tek seferlik, atılabilir atasıdır.

Kural biçimi: `harita.json` → `siniflar` SIRALI bir listedir; her kaydın `glob` deseni
`fnmatch.fnmatchcase` ile denenir (desen biçimi `maintenance/sync_check.py:78-82` ile aynıdır).
İLK eşleşen kayıt kazanır = birincil sınıf. Sonraki eşleşmeler ancak haritada
`beklenen_ortusme` içinde (özel, genel, yol_glob) ÜÇLÜSÜ olarak BEYAN EDİLMİŞSE meşrudur —
beyan yalnız kendi `yol_glob`'una uyan yollar için geçerlidir (çift adı düzeyinde sınırsız muafiyet
verilmez; bug gate 2026-09-15 MEDIUM).

Kullanım:
    python guncelle/siniflandir.py                 # denetim raporu (çıkış 0/1)
    python guncelle/siniflandir.py --json          # aynı denetim, JSON
    python guncelle/siniflandir.py --sinif <yol>   # tek bir yolun sınıfı
    python guncelle/siniflandir.py --dokum         # sınıf → dosya sayısı dökümü
    python guncelle/siniflandir.py --izlenmeyenler-de   # commit öncesi: izlenmeyenleri de kat
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
HARITA_YOLU = Path(__file__).resolve().parent / "harita.json"

# Evren komutu: TASARIM §3 ile AYNI — yalnız izlenen dosyalar. Harita, sevk edilen template'in
# sınıflandırmasıdır; tüketicinin kendi izlenmeyen dosyaları (not, rapor, coverage çıktısı) bu
# evrene GİRMEZ. Girseydi tüketicinin kök dizine bıraktığı her dosya kendi test takımını kırardı
# ve hata metni bunu söylemezdi (bug gate 2026-09-15, MEDIUM — 11 örnek yol ölçüldü).
# Commit ÖNCESİ yakalama ayrı bir ihtiyaçtır ve AÇIKÇA istenir: `--izlenmeyenler-de`.
EVREN_KOMUTU = ["git", "ls-files"]
EVREN_KOMUTU_GENIS = ["git", "ls-files", "--cached", "--others", "--exclude-standard"]

# `test.komut` içinde yol sayılan simge: en az bir "/" içerir ya da bilinen bir uzantıyla biter.
_YOL_UZANTI = (".py", ".ps1", ".cmd", ".json", ".md", ".txt", ".tmpl")


def harita_yukle(yol: Path | None = None) -> dict:
    return json.loads((yol or HARITA_YOLU).read_text(encoding="utf-8"))


def evren(kok: Path | None = None, izlenmeyenler: bool = False) -> list[str]:
    """Repo kökündeki aday yollar (git'e sorar).

    izlenmeyenler=False (varsayılan, TASARIM §3): yalnız izlenen dosyalar.
    izlenmeyenler=True: izlenmeyen ama .gitignore'lanmamış dosyaları da katar (üst küme).
    """
    kok = kok or KOK
    komut = EVREN_KOMUTU_GENIS if izlenmeyenler else EVREN_KOMUTU
    ciktı = subprocess.run(komut, cwd=kok, capture_output=True, text=True, encoding="utf-8")
    if ciktı.returncode != 0:
        raise SystemExit(f"HATA: {' '.join(komut)} başarısız: {ciktı.stderr.strip()}")
    return sorted({s.strip() for s in ciktı.stdout.splitlines() if s.strip()})


def eslesenler(yol: str, harita: dict) -> list[str]:
    """Yola uyan TÜM sınıfları harita sırasıyla döndürür (ilk öğe birincil sınıftır)."""
    bulunan = []
    for kayit in harita["siniflar"]:
        if any(fnmatch.fnmatchcase(yol, d) for d in kayit["glob"]):
            bulunan.append(kayit["sinif"])
    return bulunan


def siniflandir(yol: str, harita: dict) -> str | None:
    """Yolun birincil sınıfı; hiçbir kural uymuyorsa None."""
    m = eslesenler(yol, harita)
    return m[0] if m else None


def dokum(harita: dict, yollar: list[str]) -> dict[str, list[str]]:
    """sınıf → o sınıfa BİRİNCİL olarak düşen yollar."""
    sonuc: dict[str, list[str]] = {k["sinif"]: [] for k in harita["siniflar"]}
    for y in yollar:
        s = siniflandir(y, harita)
        if s is not None:
            sonuc[s].append(y)
    return sonuc


def _yol_simgeleri(komut: str) -> list[str]:
    """Bir komut satırındaki yol gibi görünen simgeler (varlık denetimi için)."""
    simgeler = []
    for parca in komut.split():
        if parca.startswith("-"):
            continue
        if "/" in parca or parca.endswith(_YOL_UZANTI):
            simgeler.append(parca)
    return simgeler


def _k_degerleri(komut: str) -> list[str | None]:
    """Komut satırındaki her `-k` bayrağının DEĞERİ; değer yoksa None.

    `_yol_simgeleri` `-` ile başlayan her parçayı atladığı için filtre değeri "yol gibi
    görünmediğinden" hiç denetlenmiyordu: haritaya yazım hatalı bir `-k` girilirse denetim
    sessiz kalıyordu (D17 açık kalemi, 2026-09-17). Okuma koşucunun kendi sözleşmesiyle AYNI:
    `tests/run_tests.py` de `-k`'dan sonraki parçayı alır; yoksa ya da `-` ile başlıyorsa
    "HATA: -k bir desen ister" deyip çıkış 2 verir.
    """
    parcalar = komut.split()
    degerler: list[str | None] = []
    for i, parca in enumerate(parcalar):
        if parca != "-k":
            continue
        if i + 1 >= len(parcalar) or parcalar[i + 1].startswith("-"):
            degerler.append(None)
        else:
            degerler.append(parcalar[i + 1])
    return degerler


# Keşif sonuçları süreç ömrü boyunca önbelleklenir: `denetle()` tek koşumda onlarca kez
# çağrılabilir (negatif testler), keşif ise her seferinde alt süreç başlatır.
_TEST_ADI_ONBELLEK: dict[str, tuple[list[str], str | None]] = {}

# Alt süreçte KOŞAN keşif programı. `unittest.discover` test modüllerini yalnız IMPORT eder,
# hiçbir testi KOŞTURMAZ — tüm takımı koşturmak 20+ dk sürerdi (ölçüldü: keşif ~0,7 sn / 282 ad).
# sys.path, `tests/run_tests.py`'nin kendi kurulumuyla aynı (tests dizini + repo `scripts/`).
_KESIF_PROGRAMI = r"""
import json, sys, unittest
test_dizini, kok = sys.argv[1], sys.argv[2]
for _p in (test_dizini, kok + "/scripts"):
    if _p not in sys.path:
        sys.path.insert(0, _p)
sys.dont_write_bytecode = True
loader = unittest.TestLoader()
paket = loader.discover(test_dizini, pattern="test_*.py", top_level_dir=test_dizini)
def duzle(s):
    for x in s:
        if isinstance(x, unittest.TestSuite):
            yield from duzle(x)
        else:
            yield x
adlar, kirik = [], []
for t in duzle(paket):
    adlar.append(t.id())
    if type(t).__name__ == "_FailedTest":
        kirik.append(t.id())
sys.stdout.write(json.dumps({"adlar": adlar, "kirik": kirik}))
"""


def kesfedilen_test_adlari(test_dizini: Path, kok: Path) -> tuple[list[str], str | None]:
    """(test adları, ölçülemedi_nedeni). Ad biçimi `modul.Sinif.metot` — unittest'in
    `testNamePatterns` ile karşılaştırdığı TAM ad (`TestLoader.getTestCaseNames`).

    Testler KOŞTURULMAZ, yalnız keşfedilir. Hata hâlinde ad listesi BOŞ döner ve neden metni
    dolar; çağıran bunu "temiz" değil "ÖLÇÜLEMEDİ" olarak yazar.
    """
    anahtar = str(test_dizini.resolve())
    if anahtar in _TEST_ADI_ONBELLEK:
        return _TEST_ADI_ONBELLEK[anahtar]
    if not test_dizini.is_dir():
        sonuc: tuple[list[str], str | None] = ([], f"test dizini yok: {test_dizini}")
    else:
        ciktı = subprocess.run(
            [sys.executable, "-c", _KESIF_PROGRAMI, anahtar, str(kok.resolve())],
            cwd=kok, capture_output=True, text=True, encoding="utf-8")
        if ciktı.returncode != 0:
            sonuc = ([], f"keşif başarısız (çıkış {ciktı.returncode}): "
                         f"{(ciktı.stderr or '').strip()[-300:]}")
        else:
            try:
                veri = json.loads(ciktı.stdout)
            except ValueError as h:
                sonuc = ([], f"keşif çıktısı okunamadı: {h}")
            else:
                if veri["kirik"]:
                    sonuc = ([], f"keşif import hatası verdi: {veri['kirik']}")
                elif not veri["adlar"]:
                    sonuc = ([], "keşif hiçbir test bulamadı")
                else:
                    sonuc = (veri["adlar"], None)
    _TEST_ADI_ONBELLEK[anahtar] = sonuc
    return sonuc


def _kosucu_test_dizini(calisma: Path, komut: str) -> Path | None:
    """`python <...>/run_tests.py -k X` komutundaki koşucunun test dizini (betiğin klasörü).

    `-k` yalnız `run_tests.py` biçimli koşucularda modellenmiştir; başka bir çağrı biçimi
    (ör. `python -m unittest discover ...`) için None döner ve filtre DOĞRULANMAZ.
    """
    for parca in komut.split():
        if parca.endswith("run_tests.py"):
            return calisma / parca
    return None


_DIZIN_ONBELLEK: dict[str, set[str]] = {}


def _dizin_girdileri(dizin: Path) -> set[str]:
    anahtar = str(dizin)
    if anahtar not in _DIZIN_ONBELLEK:
        try:
            _DIZIN_ONBELLEK[anahtar] = {g.name for g in dizin.iterdir()}
        except OSError:
            _DIZIN_ONBELLEK[anahtar] = set()
    return _DIZIN_ONBELLEK[anahtar]


def _harf_duyarli_var_mi(kok: Path, bagil: str) -> bool:
    """Yol diskte GERÇEK harfleriyle var mı — her parça dizin girdisiyle karşılaştırılır.

    `Path.exists()` Windows'ta ve varsayılan macOS dosya sistemlerinde harf-DUYARSIZdır:
    yanlış harfli bir yol orada GEÇER, Linux tüketicisinde FAIL olur. Yani eski kontrol
    taşınabilir değildi (D17 açık kalemi, 2026-09-17); bu kontrol dosya sisteminden bağımsız
    olarak her yerde aynı cevabı verir.
    """
    gecerli = kok
    for parca in bagil.replace("\\", "/").split("/"):
        if parca in ("", "."):
            continue
        if parca == "..":
            return False  # harita yollarında üst-dizin atlaması beklenmez
        if parca not in _dizin_girdileri(gecerli):
            return False
        gecerli = gecerli / parca
    return True


def _var_mi(kok: Path, desen: str) -> bool:
    """Yol ya da glob deseni diskte en az bir şeye karşılık geliyor mu — HARF-DUYARLI."""
    if not re.search(r"[*?\[]", desen):
        return _harf_duyarli_var_mi(kok, desen)
    # `Path.glob` de Windows'ta harf-duyarsız eşler. Döndürdüğü yolun harfleri SÜRÜME BAĞLIDIR:
    # 3.12'de diskteki GERÇEK harfler, 3.13+'ta joker içermeyen parçalar DESENDEKİ harflerle gelir
    # (CI 3.14'te ölçüldü: "Scripts/*.py" yanlış harfle geçti) ⇒ glob sonucunun harflerine
    # GÜVENİLMEZ; her aday dizin girdileriyle harf-duyarlı yeniden doğrulanır.
    duzgun = desen.replace("\\", "/")
    for p in kok.glob(desen):
        try:
            bagil = p.relative_to(kok).as_posix()
        except ValueError:
            continue
        if fnmatch.fnmatchcase(bagil, duzgun) and _harf_duyarli_var_mi(kok, bagil):
            return True
    return False


def denetle(harita: dict, yollar: list[str], kok: Path | None = None) -> list[str]:
    """Haritanın TÜM değişmezlerini ölçer; bulunan sorunların metin listesini döndürür.

    KAPSAM BEYANI — bu denetim ŞUNLARA BAKAR:
      1. her yol tam bir sınıfa düşüyor mu (sınıfsız = FAIL)
      2. birden fazla birincil sınıf var mı (beyan edilmemiş örtüşme = FAIL) — beyan YOLA
         göre kapsanır: `beklenen_ortusme` üçlüsünün `yol_glob`'una uymayan örtüşme de FAIL
      2b. bugün hiçbir yolda gerçekleşmeyen (ölü) örtüşme beyanı var mı = FAIL
      3. birincil olarak 0 dosya eşleyen sınıf var mı (`beklenen_bos: true` değilse FAIL);
         `beklenen_bos` kullanan her sınıf `beklenen_bos_neden` yazmak ZORUNDA
      4. `esler` ve `test.komut` içinde adı geçen her yol diskte var mı — HARF-DUYARLI
         (`Path.exists()` Windows/macOS'ta harf-duyarsızdır; yanlış harfli yol orada geçip
         Linux tüketicisinde FAIL olurdu)
      4b. `test.komut` içindeki `-k` filtre DEĞERİ gerçek bir test adıyla eşleşiyor mu
         (testler KOŞTURULMAZ; unittest KEŞFİ ile ad listesi toplanır)
      5. şema: zorunlu alanlar, `etkin`/`risk` değer kümesi, `ust_sinif` tanımlı mı, sınıf adı tekil mi
      6. TASARIM §3 özet tablosunun çekirdek üst sınıflarının (s3_cekirdek=true) her birinin
         en az bir alt sınıfı var mı
    BAKMADIKLARI: komutların gerçekten KOŞTUĞU / testlerin GEÇTİĞİ (yalnız yol varlığı ve `-k`
    filtresinin bir test adına denk geldiği ölçülür) · `run_tests.py` dışı koşucularda `-k`
    (ölçülemez → sorun olarak YAZILIR, sessizce atlanmaz) · `on_kosul` metinlerinin doğruluğu ·
    `yukleme` metinlerinin doğruluğu · `risk`/`kritik_yol` yargısının isabeti · dosya İÇERİĞİ.
    """
    kok = kok or KOK
    sorunlar: list[str] = []

    zorunlu = ("sinif", "ust_sinif", "glob", "yukleme", "etkin", "esler", "test", "risk",
               "ozel_adim", "kritik_yol")
    etkin_kumesi = harita.get("etkin_degerleri", [])
    risk_kumesi = harita.get("risk_degerleri", [])
    ust_idler = {u["id"] for u in harita.get("ust_siniflar", [])}

    # 5 — şema
    gorulen = set()
    for kayit in harita["siniflar"]:
        ad = kayit.get("sinif", "<adsız>")
        for alan in zorunlu:
            if alan not in kayit:
                sorunlar.append(f"şema: {ad!r} kaydında '{alan}' alanı yok")
        if ad in gorulen:
            sorunlar.append(f"şema: {ad!r} sınıf adı birden fazla kez tanımlı")
        gorulen.add(ad)
        if not kayit.get("glob"):
            sorunlar.append(f"şema: {ad!r} sınıfının glob listesi boş")
        if kayit.get("ust_sinif") not in ust_idler:
            sorunlar.append(f"şema: {ad!r} bilinmeyen ust_sinif {kayit.get('ust_sinif')!r}")
        if kayit.get("etkin") not in etkin_kumesi:
            sorunlar.append(f"şema: {ad!r} geçersiz etkin {kayit.get('etkin')!r}")
        if kayit.get("risk") not in risk_kumesi:
            sorunlar.append(f"şema: {ad!r} geçersiz risk {kayit.get('risk')!r}")

    # 6 — TASARIM §3 çekirdek üst sınıfları boş kalmasın
    kullanilan_ust = {k.get("ust_sinif") for k in harita["siniflar"]}
    for u in harita.get("ust_siniflar", []):
        if u.get("s3_cekirdek") and u["id"] not in kullanilan_ust:
            sorunlar.append(f"§3 çekirdek üst sınıfı {u['id']!r} hiçbir alt sınıfa sahip değil")

    # şema — örtüşme beyanları üçlü olmalı
    ortusme_beyani: dict[tuple, list[str]] = {}
    for o in harita.get("beklenen_ortusme", []):
        if not isinstance(o, list) or len(o) != 3:
            sorunlar.append("şema: beklenen_ortusme kaydı [kazanan, golgelenen, yol_glob_listesi] "
                            f"üçlüsü olmalı: {o!r}")
            continue
        if not isinstance(o[2], list) or not o[2] or not all(isinstance(g, str) for g in o[2]):
            sorunlar.append(f"şema: beklenen_ortusme {o[0]}+{o[1]} üçüncü alanı BOŞ OLMAYAN bir "
                            f"glob listesi olmalı (gerekçesiz sınırsız muafiyet verilmez): {o[2]!r}")
            continue
        ortusme_beyani[(o[0], o[1])] = o[2]

    # 1 + 2 — sınıflandırma
    kullanilan_ortusme: set[tuple] = set()
    for y in yollar:
        m = eslesenler(y, harita)
        if not m:
            sorunlar.append(f"sınıfsız dosya: {y}")
            continue
        kazanan = m[0]
        for golgelenen in m[1:]:
            desenler = ortusme_beyani.get((kazanan, golgelenen))
            if desenler is None:
                sorunlar.append(
                    f"birden fazla birincil sınıf: {y} → {kazanan} + {golgelenen} "
                    f"(beklenen_ortusme'de beyan edilmemiş)")
            elif not any(fnmatch.fnmatchcase(y, d) for d in desenler):
                sorunlar.append(
                    f"beyan dışı örtüşme yolu: {y} → {kazanan} + {golgelenen} "
                    f"(beyan yalnız şu yolları kapsıyor: {desenler})")
            else:
                kullanilan_ortusme.add((kazanan, golgelenen))

    # 2b — ölü örtüşme beyanı (gereksiz kalan bir beyan gelecekteki gerçek bir örtüşmeyi
    # sessizce meşrulaştırır)
    for cift in ortusme_beyani:
        if cift not in kullanilan_ortusme:
            sorunlar.append(
                f"ölü örtüşme beyanı: {cift[0]} + {cift[1]} bugün hiçbir yolda gerçekleşmiyor "
                f"(gereksizse beklenen_ortusme'den çıkar)")

    # 3 — boş sınıf
    sayim = {s: len(v) for s, v in dokum(harita, yollar).items()}
    for kayit in harita["siniflar"]:
        if sayim.get(kayit["sinif"], 0) == 0 and not kayit.get("beklenen_bos"):
            sorunlar.append(
                f"ölü kural: {kayit['sinif']!r} birincil olarak HİÇBİR dosya eşlemiyor "
                f"(kasıtlıysa haritada 'beklenen_bos': true + 'beklenen_bos_neden' yaz)")
        if kayit.get("beklenen_bos") and not kayit.get("beklenen_bos_neden"):
            sorunlar.append(
                f"şema: {kayit['sinif']!r} 'beklenen_bos' kullanıyor ama 'beklenen_bos_neden' "
                f"yazılmamış (gerekçesiz muafiyet = sınırsız kaçış deliği)")

    # 4 — esler + test.komut yolları diskte var mı
    for kayit in harita["siniflar"]:
        ad = kayit["sinif"]
        for e in kayit.get("esler", []):
            if not _var_mi(kok, e):
                sorunlar.append(f"eş yolu diskte yok: {ad} → {e}")
        for t in kayit.get("test", []):
            for alan in ("komut", "cwd", "on_kosul"):
                if alan not in t:
                    sorunlar.append(f"şema: {ad} test kaydında '{alan}' alanı yok")
            calisma = kok / t.get("cwd", ".")
            if not calisma.is_dir():
                sorunlar.append(f"test cwd'si yok: {ad} → {t.get('cwd')}")
                continue
            komut = t.get("komut", "")
            for simge in _yol_simgeleri(komut):
                if not _var_mi(calisma, simge):
                    sorunlar.append(f"test komutundaki yol diskte yok: {ad} → {simge}")
            # 4b — `-k` filtre DEĞERİ gerçek bir test adıyla eşleşiyor mu
            for deger in _k_degerleri(komut):
                if deger is None:
                    sorunlar.append(
                        f"test komutunda -k bayrağının değeri yok: {ad} → {komut!r} "
                        f"(koşucu bu durumda çıkış 2 verir)")
                    continue
                kosucu = _kosucu_test_dizini(calisma, komut)
                if kosucu is None:
                    sorunlar.append(
                        f"-k filtresi ÖLÇÜLEMEDİ ('temiz' DEĞİL): {ad} → {komut!r} "
                        f"(run_tests.py biçimli bir koşucu bulunamadı)")
                    continue
                adlar, neden = kesfedilen_test_adlari(kosucu.parent, kok)
                if neden is not None:
                    sorunlar.append(
                        f"-k filtresi ÖLÇÜLEMEDİ ('temiz' DEĞİL): {ad} → {komut!r} ({neden})")
                    continue
                # Koşucunun kendi eşleştirmesiyle AYNI: `testNamePatterns = ["*<deger>*"]`,
                # unittest bunu `modul.Sinif.metot` TAM adına `fnmatchcase` ile uygular.
                if not any(fnmatch.fnmatchcase(t_ad, f"*{deger}*") for t_ad in adlar):
                    sorunlar.append(
                        f"test komutundaki -k filtresi hiçbir test adıyla eşleşmiyor: "
                        f"{ad} → -k {deger} ({len(adlar)} test adı tarandı: {kosucu.parent})")

    return sorunlar


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="aXet mimari haritası sınıflandırıcısı/denetçisi")
    ap.add_argument("--harita", type=Path, default=None, help="harita.json yolu")
    ap.add_argument("--kok", type=Path, default=None, help="repo kökü")
    ap.add_argument("--sinif", metavar="YOL", help="tek bir yolun sınıfını yaz")
    ap.add_argument("--dokum", action="store_true", help="sınıf → dosya sayısı dökümü")
    ap.add_argument("--json", action="store_true", dest="json_cikti", help="JSON çıktı")
    ap.add_argument("--izlenmeyenler-de", action="store_true", dest="genis",
                    help="izlenmeyen (ama .gitignore'lanmamış) dosyaları da evrene kat — "
                         "commit öncesi kontrol içindir, varsayılan DEĞİLDİR")
    args = ap.parse_args(argv)

    kok = (args.kok or KOK).resolve()
    harita = harita_yukle(args.harita)

    if args.sinif:
        print(siniflandir(args.sinif, harita) or "(sınıfsız)")
        return 0

    yollar = evren(kok, args.genis)
    komut_metni = " ".join(EVREN_KOMUTU_GENIS if args.genis else EVREN_KOMUTU)
    if args.dokum:
        d = dokum(harita, yollar)
        if args.json_cikti:
            print(json.dumps({k: len(v) for k, v in d.items()}, ensure_ascii=False, indent=2))
        else:
            for kayit in harita["siniflar"]:
                print(f"{kayit['sinif']:32s} {len(d[kayit['sinif']]):4d}")
            print("-" * 40)
            print(f"{'TOPLAM':32s} {sum(len(v) for v in d.values()):4d} / {len(yollar)}")
        return 0

    sorunlar = denetle(harita, yollar, kok)
    if args.json_cikti:
        print(json.dumps({"dosya": len(yollar), "sorun": sorunlar}, ensure_ascii=False, indent=2))
    else:
        print(f"Evren: {len(yollar)} dosya ({komut_metni})")
        muaf = [k["sinif"] for k in harita["siniflar"] if k.get("beklenen_bos")]
        if muaf:
            print(f"  beklenen_bos muafiyeti: {len(muaf)} sınıf → {', '.join(muaf)}")
        for s in sorunlar:
            print(f"  SORUN: {s}")
        print(f"SONUÇ: {len(sorunlar)} sorun")
        print("KAPSAM — bakılanlar: sınıflandırma · örtüşme beyanı · şema · §3 çekirdek · yol "
              "varlığı (HARF-DUYARLI) · -k filtresinin bir test adına denk geldiği")
        print("KAPSAM — bakılmayanlar: test komutlarının gerçekten koştuğu / testlerin GEÇTİĞİ · "
              "run_tests.py dışı koşucularda -k · on_kosul ve yukleme metinlerinin doğruluğu · "
              "risk/kritik_yol yargısı · dosya içeriği")
    return 1 if sorunlar else 0


if __name__ == "__main__":
    raise SystemExit(main())
