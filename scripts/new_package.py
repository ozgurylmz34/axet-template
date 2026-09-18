#!/usr/bin/env python3
"""SAP projesine yerel paket klasörü kurar (templates/package) ve paket listesini üretir.

SAP'de paket YARATILMAZ: script yalnız `<source_root>/<MODÜL>/<PAKET>/` klasörünü, kural/spesifikasyon/oturum
dosyalarını kurar. SAP paketini (SE21) kullanıcı yaratır — aXet paket yaratmaz (kesin yasak C).
`source_root` proje kökündeki `sap-project.json`'dan okunur (yoksa `SOURCE_CODES`).

Kullanım (proje kökünden ya da --project-dir ile):
  python <TEMPLATE>/scripts/new_package.py ZSD001_CLC --title "Sevkiyat raporu" [--module SD] [--owner AD] [--dry-run]
  python <TEMPLATE>/scripts/new_package.py --index           <source_root>/PAKETLER.md dosyasını yeniden üretir
  python <TEMPLATE>/scripts/new_package.py --index --check   liste bayat mı (çıkış 1 = bayat)
Çıkış kodu: 0 tamam · 1 paket zaten var / liste bayat · 2 kullanım ya da proje hatası.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

AXET_HOME = Path(__file__).resolve().parents[1]
TEMPLATE = AXET_HOME / "templates" / "package"
SAP_PROJECT_FILE = "sap-project.json"
DEFAULT_SOURCE_ROOT = "SOURCE_CODES"
INDEX_FILE = "PAKETLER.md"

AD = re.compile(r"^[ZY][A-Z0-9_]{1,29}$")                 # SAP paket adı en fazla 30 karakter
STANDART = re.compile(r"^[ZY]([A-Z]{2,3})\d{3}(_CLC)?$")  # kurumsal biçim: Z<MODÜL><NNN>[_CLC]
MODUL = re.compile(r"^[A-Z]{2,4}$")
YER_TUTUCU = re.compile(r"\{([A-Z_]+)\}")


def source_root(proj: Path) -> tuple[Path | None, str | None]:
    """(kaynak kök klasörü, hata). SAP projesi değilse ya da alan geçersizse hata döner."""
    p = proj / SAP_PROJECT_FILE
    if not p.is_file():
        return None, f"{SAP_PROJECT_FILE} yok ({p}) → önce new_project.py --sap"
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception as exc:  # noqa: BLE001
        return None, f"{SAP_PROJECT_FILE} geçersiz JSON ({exc})"
    sr = data.get("source_root", DEFAULT_SOURCE_ROOT) if isinstance(data, dict) else None
    if not isinstance(sr, str) or not sr.strip() or Path(sr).is_absolute() or Path(sr).drive or ".." in Path(sr).parts:
        return None, f"{SAP_PROJECT_FILE}: source_root proje içinde göreli bir klasör olmalı ({sr!r})"
    return proj / sr.strip(), None


def _alt_klasorler(d: Path) -> list[Path]:
    return sorted((x for x in d.iterdir() if x.is_dir() and not x.name.startswith(".")), key=lambda x: x.name)


def paketler(root: Path) -> list[tuple[str, Path]]:
    """`<source_root>/<MODÜL>/<PAKET>/` düzenindeki paketler (modül, klasör). Sıra platformdan bağımsız."""
    if not root.is_dir():
        return []
    return [(mod.name, pkg) for mod in _alt_klasorler(root) for pkg in _alt_klasorler(mod)]


def _alan(text: str, etiket: str) -> str:
    m = re.search(rf"^- \*\*{re.escape(etiket)}:\*\*\s*(.+)$", text, re.M)
    return m.group(1).strip().replace("|", "\\|") if m else "?"


def index_metni(root: Path) -> str:
    satirlar = ["# Paketler", "",
                "> `new_package.py --index` üretir; elle düzenleme. Bilgiler her paketin `.rules.md` dosyasından okunur.",
                "", "| Modül | Paket | Başlık | Owner | Durum |", "|---|---|---|---|---|"]
    for mod, pkg in paketler(root):
        kural = pkg / ".rules.md"
        if kural.is_file():
            t = kural.read_text(encoding="utf-8", errors="replace")
            satirlar.append(f"| {mod} | `{pkg.name}` | {_alan(t, 'Başlık')} | {_alan(t, 'Owner')} | {_alan(t, 'Durum')} |")
        else:
            satirlar.append(f"| {mod} | `{pkg.name}` | ? | ? | .rules.md YOK |")
    return "\n".join(satirlar) + "\n"


def _norm(s: str) -> str:
    return "\n".join(line.rstrip() for line in s.replace("\r\n", "\n").strip().split("\n"))


def index_guncel(root: Path) -> bool:
    f = root / INDEX_FILE
    mevcut = f.read_text(encoding="utf-8", errors="replace") if f.is_file() else ""
    return _norm(mevcut) == _norm(index_metni(root))


def eksik_kurallar(root: Path) -> list[str]:
    return [f"{mod}/{pkg.name}" for mod, pkg in paketler(root) if not (pkg / ".rules.md").is_file()]


def tur_notu(pkg: str, klasik: bool) -> str:
    if klasik:
        return (f"**Paket tipi: klasik (`_CLC`).** Klasik ABAP objeleri (program, include, fonksiyon grubu/modül, klasik "
                f"geliştirme) bu pakette durur. Aynı iş için ABAP Cloud nesneleri (RAP, released API) soneksiz `{pkg}` paketindedir.")
    return (f"**Paket tipi: cloud (sonek yok, varsayılan).** Yalnız ABAP Cloud ve released API. Klasik obje (program, include, "
            f"fonksiyon grubu/modül) bu pakete girmez; gerekiyorsa aynı numarayla `{pkg}_CLC` paketi açılır.")


def main() -> int:
    ap = argparse.ArgumentParser(description="SAP projesine yerel paket klasörü kurar (SAP'de paket yaratmaz)")
    ap.add_argument("package", nargs="?", help="paket adı, ör. ZSD001 ya da ZSD001_CLC")
    ap.add_argument("--title", help="paket başlığı")
    ap.add_argument("--module", help="SAP modülü (ör. SD); verilmezse paket adından çıkarılır")
    ap.add_argument("--owner", default="<OWNER>", help="sorumlu (varsayılan: <OWNER> yer tutucusu)")
    ap.add_argument("--project-dir", default=".", help="proje kökü (varsayılan: bulunulan dizin)")
    ap.add_argument("--index", action="store_true", help="yalnız PAKETLER.md dosyasını üret")
    ap.add_argument("--check", action="store_true", help="--index ile: yazma, liste bayat mı bak")
    ap.add_argument("--dry-run", action="store_true", help="yazmadan ne yapılacağını göster")
    args = ap.parse_args()
    if args.check and not args.index:
        ap.error("--check yalnız --index ile kullanılır")
    if not args.index and (not args.package or not args.title):
        ap.error("paket adı ve --title gerekli (ya da --index)")

    proj = Path(args.project_dir).resolve()
    if proj == AXET_HOME or AXET_HOME in proj.parents:
        print(f"HATA: proje dizini template reposunun içinde ({AXET_HOME}).")
        return 2
    root, err = source_root(proj)
    if err:
        print(f"HATA: {err}")
        return 2
    index_yolu = root / INDEX_FILE

    if args.check and not args.index:
        ap.error("--check yalnız --index ile kullanılır")
    if args.index:
        if args.check:
            ok = index_guncel(root)
            print(f"[{'OK' if ok else 'BAYAT'}] {index_yolu}" + ("" if ok else " → new_package.py --index"))
            print("KAPSAM — bakılanlar: paket klasörleri ve .rules.md alanları · bakılmayanlar: SAP'de paketin varlığı, obje adları")
            return 0 if ok else 1
        metin = index_metni(root)
        if args.dry_run:
            print(metin)
        else:
            root.mkdir(parents=True, exist_ok=True)
            index_yolu.write_text(metin, encoding="utf-8")
            print(f"[yazıldı] {index_yolu} ({len(paketler(root))} paket)")
        return 0

    if not args.package or not args.title:
        ap.error("paket adı ve --title gerekli (ya da --index)")
    name = args.package.strip()
    if name != name.upper():
        print(f"HATA: paket adı büyük harf olmalı ({name!r} → {name.upper()!r}).")
        return 2
    if not AD.match(name):
        print(f"HATA: paket adı Z ya da Y ile başlamalı, yalnız A-Z 0-9 _ içermeli ve en fazla 30 karakter olmalı ({name!r}). "
              "Standart ad alanında paket açılmaz.")
        return 2
    m = STANDART.match(name)
    if not m:
        print(f"UYARI: {name} kurumsal biçimde değil (Z<MODÜL><NNN> ya da Z<MODÜL><NNN>_CLC, ör. ZSD001_CLC). "
              "Ad önekleri .rules.md'de bu ada göre üretilecek; gerekirse elle düzelt.")
    module = (args.module or (m.group(1) if m else "")).upper()
    if not MODUL.match(module):
        print("HATA: modül çıkarılamadı ya da geçersiz → --module SD gibi 2-4 harf ver.")
        return 2
    if m and args.module and module != m.group(1):
        print(f"UYARI: --module {module} paket adındaki modülle ({m.group(1)}) aynı değil.")
    for mod, pkg_dir in paketler(root):
        if pkg_dir.name == name:
            print(f"HATA: {name} zaten var: {pkg_dir} — dokunulmadı.")
            return 1
    hedef = root / module / name
    if hedef.exists():
        print(f"HATA: {hedef} zaten var — dokunulmadı.")
        return 1

    klasik = name.endswith("_CLC")
    pkg = name[: -len("_CLC")] if klasik else name
    mapping = {"PKG": pkg, "P": pkg[0], "PKG_BODY": pkg[1:], "PKG_FULL": name, "TITLE": args.title.strip(),
               "MODULE": module, "DATE": date.today().isoformat(), "OWNER": args.owner.strip(),
               "PKG_TYPE_NOTE": tur_notu(pkg, klasik)}

    klasorler = [s.strip() for s in (TEMPLATE / "folders.txt").read_text(encoding="utf-8").splitlines() if s.strip()]
    dosyalar = [p for p in sorted(TEMPLATE.rglob("*.tmpl")) if p.is_file()]
    for k in klasorler:
        print(f"  [klasör] {k}/")
        if not args.dry_run:
            (hedef / k).mkdir(parents=True, exist_ok=True)
            (hedef / k / ".gitkeep").touch()
    for src in dosyalar:
        rel = src.relative_to(TEMPLATE).as_posix()[: -len(".tmpl")]
        print(f"  [dosya]  {rel}")
        if not args.dry_run:
            dst = hedef / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            metin = YER_TUTUCU.sub(lambda x: mapping.get(x.group(1), x.group(0)), src.read_text(encoding="utf-8"))
            dst.write_text(metin, encoding="utf-8")
    if not args.dry_run:
        index_yolu.write_text(index_metni(root), encoding="utf-8")
        print(f"  [liste]  {index_yolu.relative_to(proj).as_posix()} güncellendi")

    print(f"\nPaket: {hedef}" + (" · dry-run: hiçbir şey yazılmadı" if args.dry_run else ""))
    print("Sonraki adımlar:\n"
          f"  1. SAP'de {name} paketini SE21 ile SEN yarat (aXet paket yaratmaz — kesin yasak C) ve transportu belirle.\n"
          "  2. .rules.md: transport, bağımlılık ve bilinen istisnaları doldur.\n"
          "  3. SPEC.md: iş alımı (S0/S1/S2) ve kapsam bölümünü doldur.\n"
          "  4. AGENTS.md proje kimliğindeki paket satırını güncelle.")
    print("KAPSAM — yapılmayanlar: SAP'de paket yaratma ya da varlık kontrolü · obje adlarının doğrulanması")
    return 0


if __name__ == "__main__":
    sys.exit(main())
