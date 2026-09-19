#!/usr/bin/env python3
"""Paket obje dosya adlarını `.rules.md` "Naming" tablosundaki regex'lerle doğrular (SAP projesi).

Mantık:
  1. `<source_root>/<MODÜL>/<PAKET>/.rules.md` içindeki `## Naming` tablosundan (obje tipi → regex) okunur;
     regex 3. kolondadır ve backtick içindedir (`templates/package/.rules.md.tmpl` biçimi). `\\|` kolon ayracı değildir.
  2. Obje tipi klasörlerindeki (`programs/ classes/ functions/ cds/ structures/ tables/`, alt klasörler dahil)
     obje kaynak dosyalarının adı (ilk noktaya kadar, büyük harfe çevrilerek) o klasörün tiplerinden en az
     birinin regex'ine uymalı. abapGit ad alanı yazımı `#ns#ad` → `/NS/AD`.
  3. Klasik include adı programdan türer: `<PKG>_I_<AD>_<Tip><NN>` için pakette `<PKG>_P_<AD>` ya da `<PKG>_R_<AD>`
     programı olmalı; program adı en fazla 26 karakter (include 30 sınırına sığsın).
  4. `.rules.md` "Bilinen istisnalar" bölümünde backtick içinde yazılan obje adları (ör. `ZBP_I_ORDER`) muaftır.

Kullanım (proje kökünden ya da --project-dir ile):
  python <TEMPLATE>/scripts/check_package_naming.py                  tüm paketler
  python <TEMPLATE>/scripts/check_package_naming.py --package ZSD001_CLC
  python <TEMPLATE>/scripts/check_package_naming.py --files <yol> ...  yalnız bu dosyalar (pre-commit)
Çıkış kodu: 0 ihlal yok · 1 ihlal var · 2 kullanım ya da proje hatası.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import new_package as npk  # noqa: E402  (source_root + paket düzeni tek kaynak)

# Naming tablosundaki obje tipi (küçük harf, satır başı) → dosyanın durduğu klasör.
# En uzun önek kazanır ("table type" "table"dan önce; "exception class" "class"tan önce).
# Klasörü olmayan tipler (mesaj sınıfı, numara aralığı, geliştirme, kilit objesi) dosya adından denetlenmez.
TIP_KLASOR = {
    "program": "programs", "include": "programs",
    "class": "classes", "interface": "classes", "exception class": "classes",
    "function group": "functions", "function module": "functions",
    "cds": "cds", "ddl source": "cds", "behavior definition": "cds",
    "service definition": "cds", "service binding": "cds", "access control": "cds",
    "structure": "structures", "table type": "structures", "data element": "structures", "domain": "structures",
    "table": "tables", "draft table": "tables",
    "message class": None, "number range": None, "enhancement implementation": None, "lock object": None,
}
OBJE_KLASORLERI = sorted({k for k in TIP_KLASOR.values() if k})
# Obje kaynağı sayılan dosya adı parçaları (ilk noktadan sonraki segmentler). Bunlardan hiçbirini taşımayan dosya
# (README.md, .txt taslak, görsel …) adlandırma denetimine GİRMEZ ve "bakılmadı" sayacına yazılır.
KAYNAK_SEGMENTLERI = {
    "abap", "clas", "intf", "prog", "fugr", "func", "ccimp", "ccdef", "ccmac", "ccau",
    "ddls", "asddls", "dcls", "asdcls", "ddlx", "asddlxs", "bdef", "asbdef", "srvd", "srvdsrv", "srvb",
    "tabl", "ttyp", "dtel", "doma", "cds", "dcl", "ddl",
}
_YER_TUTUCU = re.compile(r"\{[A-Z_]+\}")
_INCLUDE_SONEK = re.compile(r"_[A-Z]\d{2}$")
_ISTISNA_AD = re.compile(r"`([A-Z0-9_/]{3,40})`")
PROGRAM_AZAMI = 26


@dataclass
class Sonuc:
    ihlaller: list[str] = field(default_factory=list)
    taranan: int = 0
    bakilmayan: int = 0
    paket_sayisi: int = 0
    notlar: list[str] = field(default_factory=list)


def _tip_klasoru(tip: str) -> str | None:
    adaylar = [k for k in TIP_KLASOR if tip == k or tip.startswith(k + " ") or tip.startswith(k + "(")]
    return TIP_KLASOR[max(adaylar, key=len)] if adaylar else None


def kurallari_oku(metin: str) -> tuple[list[tuple[str, str]], set[str]]:
    """(obje tipi, regex) listesi ve istisna adları. Regex hücresi backtick içinde değilse satır atlanır ("—")."""
    kurallar, istisnalar, bolum = [], set(), None
    for ham in metin.splitlines():
        satir = ham.strip()
        if satir.startswith("## "):
            baslik = satir[3:].strip().lower()
            bolum = "naming" if baslik.startswith("naming") else "istisna" if baslik.startswith("bilinen istisna") else None
            continue
        if bolum == "istisna":
            istisnalar.update(_ISTISNA_AD.findall(satir))
        elif bolum == "naming" and satir.startswith("|"):
            hucreler = [h.strip().replace("\x00", "|") for h in satir.replace("\\|", "\x00").split("|")[1:-1]]
            if len(hucreler) >= 3 and len(hucreler[2]) > 2 and hucreler[2].startswith("`") and hucreler[2].endswith("`"):
                kurallar.append((hucreler[0].lower(), hucreler[2][1:-1]))
    return kurallar, istisnalar


def obje_adi(dosya_adi: str) -> str | None:
    """Obje kaynak dosyasıysa SAP obje adı (büyük harf), değilse None."""
    if dosya_adi.startswith("."):
        return None
    parcalar = dosya_adi.split(".")
    if len(parcalar) < 2 or not any(p.lower() in KAYNAK_SEGMENTLERI for p in parcalar[1:]):
        return None
    return parcalar[0].replace("#", "/").upper()


def _paket_dosyalari(pkg: Path) -> list[Path]:
    return sorted(p for k in OBJE_KLASORLERI if (pkg / k).is_dir() for p in (pkg / k).rglob("*") if p.is_file())


def paket_denetle(pkg: Path, dosyalar: list[Path] | None, sonuc: Sonuc) -> None:
    """`dosyalar` None → paketteki tüm dosyalar; aksi hâlde yalnız verilenler (paket içi olmalı)."""
    etiket = f"{pkg.parent.name}/{pkg.name}"
    hedefler = _paket_dosyalari(pkg) if dosyalar is None else dosyalar
    objeler = [(f, obje_adi(f.name)) for f in hedefler]
    sonuc.bakilmayan += sum(1 for _, ad in objeler if ad is None)
    objeler = [(f, ad) for f, ad in objeler if ad is not None]
    if not objeler:
        return
    kural_dosyasi = pkg / ".rules.md"
    if not kural_dosyasi.is_file():
        sonuc.ihlaller.append(f"{etiket}: .rules.md yok — {len(objeler)} obje dosyası adlandırma kuralsız "
                              "(templates/package/.rules.md.tmpl)")
        return
    kurallar, istisnalar = kurallari_oku(kural_dosyasi.read_text(encoding="utf-8", errors="replace"))
    if not kurallar:
        sonuc.ihlaller.append(f"{etiket}: .rules.md 'Naming' tablosundan regex çıkarılamadı "
                              "(3. kolon backtick içinde regex olmalı)")
        return
    klasor_kurallari: dict[str, list[tuple[str, re.Pattern]]] = {}
    for tip, desen in kurallar:
        klasor = _tip_klasoru(tip)
        if _YER_TUTUCU.search(desen):
            sonuc.ihlaller.append(f"{etiket}: .rules.md '{tip}' regex'inde doldurulmamış şablon yer tutucusu: {desen}")
            continue
        try:
            derli = re.compile(desen)
        except re.error as exc:
            sonuc.ihlaller.append(f"{etiket}: .rules.md '{tip}' regex'i geçersiz ({exc}): {desen}")
            continue
        if klasor:
            klasor_kurallari.setdefault(klasor, []).append((tip, derli))

    programlar = {ad for f in _paket_dosyalari(pkg) if (pkg / "programs") in f.parents
                  for ad in [obje_adi(f.name)] if ad and re.search(r"_[PR]_", ad) and not _INCLUDE_SONEK.search(ad)}
    for f, ad in objeler:
        sonuc.taranan += 1
        goreli = f.relative_to(pkg).as_posix()
        klasor = goreli.split("/", 1)[0]
        if ad in istisnalar:
            continue
        uygun = klasor_kurallari.get(klasor, [])
        if not uygun:
            sonuc.ihlaller.append(f"{etiket}/{goreli}: '{klasor}/' klasörü için .rules.md'de regex yok")
            continue
        if not any(rx.match(ad) for _, rx in uygun):
            sonuc.ihlaller.append(f"{etiket}/{goreli}: {ad} hiçbir regex'e uymuyor (denenen tipler: "
                                  f"{', '.join(t for t, _ in uygun)})")
            continue
        if klasor != "programs":
            continue
        if ad in programlar and len(ad) > PROGRAM_AZAMI:
            sonuc.ihlaller.append(f"{etiket}/{goreli}: program adı {len(ad)} karakter (> {PROGRAM_AZAMI}) — "
                                  "include adları 30 karakter sınırına sığmaz")
        parcalar = ad.split("_")
        if "_I_" in ad and _INCLUDE_SONEK.search(ad) and "I" in parcalar:
            i = parcalar.index("I")
            if i >= 1 and len(parcalar) >= i + 3:
                onek, govde = "_".join(parcalar[:i]), "_".join(parcalar[i + 1:-1])
                if f"{onek}_P_{govde}" not in programlar and f"{onek}_R_{govde}" not in programlar:
                    sonuc.ihlaller.append(f"{etiket}/{goreli}: include {ad} bir programdan türemiyor (beklenen "
                                          f"`{onek}_P_{govde}` pakette yok — kısaltma ya da program eksik)")


def denetle(proj: Path, files: list[str] | None = None, package: str | None = None) -> tuple[Sonuc | None, str | None]:
    """(sonuç, hata). `files`: proje köküne göreli ya da mutlak yollar; paket klasörü dışındakiler yok sayılır."""
    root, err = npk.source_root(proj)
    if err:
        return None, err
    sonuc = Sonuc()
    paketler = npk.paketler(root)
    if package:
        paketler = [(m, p) for m, p in paketler if p.name == package]
        if not paketler:
            return None, f"{package} {root.name}/ altında bulunamadı"
    if files is None:
        for _, pkg in paketler:
            sonuc.paket_sayisi += 1
            paket_denetle(pkg, None, sonuc)
        return sonuc, None
    for pkg, liste in sorted(_grupla(proj, root, files).items()):
        sonuc.paket_sayisi += 1
        paket_denetle(pkg, liste, sonuc)
    return sonuc, None


def _grupla(proj: Path, root: Path, files: list[str]) -> dict[Path, list[Path]]:
    """Paket klasörü → o pakete düşen dosyalar (obje klasörü altındakiler; diğerleri yok sayılır)."""
    gruplar: dict[Path, list[Path]] = {}
    root_r = root.resolve()
    for ham in files:
        p = Path(ham)
        p = (p if p.is_absolute() else proj / p).resolve()
        try:
            parcalar = p.relative_to(root_r).parts
        except ValueError:
            continue
        if len(parcalar) >= 4 and parcalar[2] in OBJE_KLASORLERI:
            gruplar.setdefault(root_r / parcalar[0] / parcalar[1], []).append(p)
    return gruplar


def okunan_kural_dosyalari(proj: Path, files: list[str]) -> set[Path]:
    """`denetle(proj, files)`in DİSKTEN okuyacağı `.rules.md` yolları (çözülmüş). Tek kaynak: aynı gruplama
    + `paket_denetle`in "obje yoksa kuralı okuma" kuralı. Kaynak kökü okunamazsa boş küme."""
    root, err = npk.source_root(proj)
    if err:
        return set()
    return {pkg / ".rules.md" for pkg, liste in _grupla(proj, root, files).items()
            if any(obje_adi(f.name) is not None for f in liste)}


# K-O① (davranış testi 2026-09-18): FAIL alan model `.rules.md` Naming regex'ini kendi adını kapsayacak
# şekilde genişletip sessizce geçti. Metin davranışı garanti etmez; FAIL anında hatırlatır.
KURAL_HATIRLATMA = ("HATIRLATMA: bu denetimi geçmek için kuralı / regex'i / `.rules.md`'yi DEĞİŞTİRME — reddi ve sebebini kullanıcıya bildir; kural değişikliği ayrı ve açık onay ister (core/00-temel.md §3).")

KAPSAM = ("KAPSAM — bakılanlar: obje tipi klasörlerindeki obje kaynak dosyalarının adı (.rules.md Naming regex'i + "
          "include türetme + program ≤ 26) · bakılmayanlar: SAP'deki gerçek obje adları, klasörü olmayan tipler "
          "(mesaj sınıfı, numara aralığı, geliştirme, kilit objesi), ui/ docs/ ref_docs/, obje dosyasının doğru "
          "klasörde olup olmadığı, .rules.md'nin staged hâli (diskteki okunur)")


def main() -> int:
    ap = argparse.ArgumentParser(description="Paket obje dosya adlarını .rules.md Naming regex'leriyle doğrular")
    ap.add_argument("--project-dir", default=".", help="proje kökü (varsayılan: bulunulan dizin)")
    ap.add_argument("--package", help="yalnız bu paket")
    ap.add_argument("--files", nargs="+", help="yalnız bu dosyalar (paket klasörü dışındakiler yok sayılır)")
    args = ap.parse_args()
    proj = Path(args.project_dir).resolve()
    sonuc, err = denetle(proj, args.files, args.package)
    if err:
        print(f"HATA: {err}")
        return 2
    for ihlal in sonuc.ihlaller:
        print(f"[FAIL] {ihlal}")
    if sonuc.ihlaller:
        print(KURAL_HATIRLATMA)
    print(KAPSAM)
    print(f"SONUÇ: {len(sonuc.ihlaller)} ihlal · {sonuc.paket_sayisi} paket · {sonuc.taranan} obje dosyası tarandı · "
          f"{sonuc.bakilmayan} dosya obje kaynağı değil (bakılmadı)")
    return 1 if sonuc.ihlaller else 0


if __name__ == "__main__":
    sys.exit(main())
