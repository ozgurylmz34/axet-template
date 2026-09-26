#!/usr/bin/env python3
"""SAP projesine yerel paket klasörü kurar (templates/package) ve paket listesini üretir.

SAP'de paket YARATILMAZ: script yalnız `<source_root>/<MODÜL>/<PAKET>/` klasörünü, kural/spesifikasyon/oturum
dosyalarını kurar. SAP paketini (SE21) kullanıcı yaratır — aXet paket yaratmaz (kesin yasak C).
`source_root` proje kökündeki `sap-project.json`'dan okunur (yoksa `SOURCE_CODES`).

Kullanım (proje kökünden ya da --project-dir ile):
  python <TEMPLATE>/scripts/new_package.py ZSD001_CLC --title "Sevkiyat raporu" [--module SD] [--owner AD] [--dry-run]
  python <TEMPLATE>/scripts/new_package.py ZSD001_CLC --title "…" --mevcut [--owner AD]
                                           SAP'de ZATEN VAR olan paketin klasörü (sonradan kurulum; aşağıda)
  python <TEMPLATE>/scripts/new_package.py --index           <source_root>/PAKETLER.md dosyasını yeniden üretir
  python <TEMPLATE>/scripts/new_package.py --index --check   liste bayat mı (çıkış 1 = bayat)
Çıkış kodu: 0 tamam · 1 paket zaten var / liste bayat · 2 kullanım ya da proje hatası (--mevcut: Owner çelişkisi ya da
eksik Owner dahil) · 3 --mevcut: canlı okuma ÖLÇÜLEMEDİ ya da paket canlıda bulunamadı (klasör YAZILMADI).

--mevcut (Z146, 2026-09-26): var olan paket için klasör sonradan kurulunca şablon alanları kanıtsız doluyordu (Owner
olarak oturum kullanıcısı yazıldı, canlı TADIR.AUTHOR başkaydı; README'de `<OWNER>` ve "Başlangıç: bugün" kaldı).
Bu kipte sap-adt-foundation CLI'nin salt-okur `adt_sql_query` aracıyla iki sorgu koşar: TADIR (`PGMID='R3TR'
OBJECT='DEVC'`) → AUTHOR, CREATED_ON · TDEVC → PARENTCL. Owner kaynağı TADIR.AUTHOR'dur (TDEVC'nin sorumlu alanı
canlıda boş ölçüldü). Owner canlıda yoksa VARSAYILAN YAZILMAZ: betik durur ve `--owner` ister (model kullanıcıya
sorar); `--owner` canlıdakiyle çelişirse durur; canlı okunamazsa klasör yazılmaz (fail-closed). Canlıdan
doğrulanmayan şablon iddiaları (paket tipi, bilinen istisnalar) `DOĞRULANMADI` etiketiyle yazılır.
`AXET_SAP_ADT_CLI` yalnız testin enjeksiyon noktasıdır: gerçek CLI yerine sahte betik koşar, canlıya çıkılmaz.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
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
SAP_ADT_CLI = AXET_HOME / "skills-sap" / "sap-adt-foundation" / "scripts" / "sap_adt_cli.py"
CLI_ZAMAN_ASIMI = 180  # sn — tek salt-okur sorgu; aşılırsa ÖLÇÜLEMEDİ

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


class CanliOkunamadi(Exception):
    """--mevcut: canlı okuma yapılamadı (CLI yok/çöktü/ok:false/JSON bozuk). Çağıran klasör YAZMAZ (çıkış 3)."""


def canli_sorgu(proj: Path, sorgu: str) -> list[dict]:
    """sap-adt-foundation CLI'si ile TEK salt-okur `adt_sql_query`. Satırlar ([{KOLON: değer}]) ya da CanliOkunamadi.
    Yazma bayrağı verilmez (kapı okuma sınıfı değerlendirir); `.conn_adt` bu betik tarafından AÇILMAZ."""
    cli = Path(os.environ.get("AXET_SAP_ADT_CLI") or SAP_ADT_CLI)
    if not cli.is_file():
        raise CanliOkunamadi(f"sap-adt-foundation CLI bulunamadı ({cli}) — template klonu eksik ya da SAP paketi "
                             "kurulmamış (`install.py --sap`)")
    komut = [sys.executable, str(cli), "adt_sql_query", "--args-json",
             json.dumps({"query": sorgu, "row_limit": 5}, ensure_ascii=False), "--project-dir", str(proj)]
    try:
        r = subprocess.run(komut, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           stdin=subprocess.DEVNULL, timeout=CLI_ZAMAN_ASIMI)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CanliOkunamadi(f"CLI çalıştırılamadı ({type(exc).__name__}: {exc})") from exc
    try:
        cikti = json.loads(r.stdout or "")
    except json.JSONDecodeError as exc:
        kuyruk = (r.stdout or r.stderr or "").strip()[:200]
        raise CanliOkunamadi(f"CLI çıktısı JSON değil (çıkış {r.returncode}): {kuyruk}") from exc
    if not isinstance(cikti, dict):
        raise CanliOkunamadi(f"CLI çıktısı JSON nesnesi değil (çıkış {r.returncode})")
    sonuc = cikti.get("result")
    if r.returncode != 0 or not cikti.get("ok") or not isinstance(sonuc, dict) or not sonuc.get("ok"):
        hata = cikti.get("error") or {}
        sonuc_d = sonuc if isinstance(sonuc, dict) else {}
        kod = hata.get("code") or sonuc_d.get("error") or "?"
        neden = hata.get("message") or sonuc_d.get("message") or f"çıkış {r.returncode}"
        raise CanliOkunamadi(f"`adt_sql_query` başarısız: {kod} — {neden}")
    satirlar = sonuc.get("rows")
    if not isinstance(satirlar, list) or sonuc.get("truncated"):
        raise CanliOkunamadi("`adt_sql_query` yanıtında satır listesi yok ya da yanıt kırpılmış")
    return [s for s in satirlar if isinstance(s, dict)]


def _deger(satir: dict, kolon: str) -> str:
    """Kolon değeri; boş ve None → "" (canlıda boş alan `null` geldi — ölçüldü 2026-09-26). Ad harf duyarsız aranır."""
    for k, v in satir.items():
        if str(k).upper() == kolon:
            return "" if v is None else str(v).strip()
    return ""


def _tarih(ham: str) -> str | None:
    """CREATED_ON `YYYYMMDD` (canlıda ölçülen biçim, 2026-09-26) ya da `YYYY-MM-DD` → `YYYY-MM-DD`; geçersizse None."""
    m = re.fullmatch(r"(\d{4})-?(\d{2})-?(\d{2})", ham or "")
    if not m:
        return None
    try:
        return date(int(m[1]), int(m[2]), int(m[3])).isoformat()
    except ValueError:
        return None


def mevcut_paket_bilgisi(proj: Path, ad: str) -> dict:
    """Var olan SAP paketinin canlı bilgisi. Paket canlıda yoksa {"bulunamadi": True}; okuma yapılamazsa
    CanliOkunamadi. Ad sorguya gömüldüğü için `AD` regex'inden (yalnız A-Z 0-9 _) geçmiş olmalı."""
    if not AD.match(ad):
        raise ValueError(f"geçersiz paket adı: {ad!r}")
    tadir = canli_sorgu(proj, "SELECT author, created_on FROM tadir "
                              f"WHERE pgmid = 'R3TR' AND object = 'DEVC' AND obj_name = '{ad}'")
    tdevc = canli_sorgu(proj, f"SELECT devclass, parentcl FROM tdevc WHERE devclass = '{ad}'")
    if not tadir and not tdevc:
        return {"bulunamadi": True}
    t = tadir[0] if tadir else {}
    ham = _deger(t, "CREATED_ON")
    return {"bulunamadi": False, "tdevc_var": bool(tdevc), "author": _deger(t, "AUTHOR"),
            "created_on_ham": ham, "baslangic": _tarih(ham),
            "parent": _deger(tdevc[0], "PARENTCL") if tdevc else ""}


def mevcut_kip(proj: Path, name: str, owner: str) -> dict | int:
    """--mevcut: canlıdan oku, Owner kararını ver. Döner: şablon eşlemesine eklenecekler ya da çıkış kodu (2/3).
    Owner canlıda varsa O yazılır; `--owner` ancak canlıyla aynıysa ya da canlıda Owner yoksa kabul edilir.
    Varsayılan (`<OWNER>`, oturum kullanıcısı …) HİÇBİR dalda yazılmaz."""
    try:
        bilgi = mevcut_paket_bilgisi(proj, name)
    except CanliOkunamadi as exc:
        print(f"HATA: canlı okuma ÖLÇÜLEMEDİ — {exc}. Klasör YAZILMADI (fail-closed). Bağlantıyı düzelt "
              "(`sap_adt_cli.py sap_doctor`) ve tekrar dene; paket SAP'de yoksa --mevcut olmadan kur.")
        return 3
    if bilgi["bulunamadi"]:
        print(f"HATA: {name} canlıda bulunamadı (TADIR R3TR DEVC ve TDEVC'de 0 satır). Klasör YAZILMADI. "
              "Paket adını kullanıcıyla teyit et; SAP'de henüz yoksa paketi kullanıcı yaratır, sonra --mevcut ile kur.")
        return 3
    canli = bilgi["author"]
    if canli and owner and owner.upper() != canli.upper():
        print(f"HATA: Owner çelişkisi — canlı TADIR.AUTHOR = {canli}, --owner = {owner}. Klasör YAZILMADI. "
              "Kullanıcıya SOR: canlıdaki değer için --owner'ı çıkar; kullanıcı farklı bir sorumlu belirlediyse "
              "kurulumdan sonra .rules.md ve README'deki Owner'ı kullanıcının cevabıyla düzelt.")
        return 2
    if not canli and not owner:
        print(f"HATA: {name} için Owner canlıda yok (TADIR.AUTHOR boş). Varsayılan YAZILMAZ — kullanıcıya SOR ve "
              "cevabı --owner <AD> ile ver. Klasör YAZILMADI.")
        return 2
    kaynak = "canlı TADIR.AUTHOR" if canli else "kullanıcı cevabı (`--owner`; canlı TADIR.AUTHOR boş)"
    baslangic = bilgi["baslangic"] or f"DOĞRULANMADI (canlı TADIR.CREATED_ON okunamadı: {bilgi['created_on_ham']!r})"
    if not bilgi["tdevc_var"]:
        parent = "DOĞRULANMADI (TDEVC satırı yok)"
    elif bilgi["parent"]:
        parent = f"`{bilgi['parent']}` (canlı TDEVC.PARENTCL)"
    else:
        parent = "yok (canlı TDEVC.PARENTCL boş)"
    return {
        "OWNER": canli or owner, "START": baslangic, "PARENT": parent,
        "OPENING_TITLE": f"yerel klasör kuruldu (SAP paketi {baslangic} tarihinden beri var)",
        "EXCEPTIONS": ("**DOĞRULANMADI** — paketteki mevcut objeler yukarıdaki önek tablosuyla karşılaştırılmadı. "
                       "`adt_package_contents` ile oku; desene uymayanları gerekçesiyle buraya yaz."),
        "_KAYNAK": (f"> **Sonradan kurulum ({date.today().isoformat()}, `new_package.py --mevcut`):** Owner = {kaynak} · "
                    "Başlangıç = canlı TADIR.CREATED_ON · Üst paket = canlı TDEVC.PARENTCL. Canlıdan doğrulanmayan "
                    "şablon cümleleri `DOĞRULANMADI` etiketlidir; doğrulayınca etiketi kaldır."),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="SAP projesine yerel paket klasörü kurar (SAP'de paket yaratmaz)")
    ap.add_argument("package", nargs="?", help="paket adı, ör. ZSD001 ya da ZSD001_CLC")
    ap.add_argument("--title", help="paket başlığı")
    ap.add_argument("--module", help="SAP modülü (ör. SD); verilmezse paket adından çıkarılır")
    ap.add_argument("--owner", help="sorumlu (varsayılan: <OWNER> yer tutucusu; --mevcut'ta canlı TADIR.AUTHOR)")
    ap.add_argument("--mevcut", action="store_true",
                    help="SAP'de zaten var olan paketin klasörü: Owner/başlangıç/üst paket canlıdan salt-okur okunur")
    ap.add_argument("--project-dir", default=".", help="proje kökü (varsayılan: bulunulan dizin)")
    ap.add_argument("--index", action="store_true", help="yalnız PAKETLER.md dosyasını üret")
    ap.add_argument("--check", action="store_true", help="--index ile: yazma, liste bayat mı bak")
    ap.add_argument("--dry-run", action="store_true", help="yazmadan ne yapılacağını göster")
    args = ap.parse_args()
    if args.check and not args.index:
        ap.error("--check yalnız --index ile kullanılır")
    if args.mevcut and args.index:
        ap.error("--mevcut --index ile kullanılmaz")
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
    bugun = date.today().isoformat()
    owner = (args.owner or "").strip()
    mapping = {"PKG": pkg, "P": pkg[0], "PKG_BODY": pkg[1:], "PKG_FULL": name, "TITLE": args.title.strip(),
               "MODULE": module, "DATE": bugun, "START": bugun, "OWNER": owner or "<OWNER>",
               "PKG_TYPE_NOTE": tur_notu(pkg, klasik), "PARENT": "<varsa>", "OPENING_TITLE": "paket açıldı",
               "EXCEPTIONS": ("<Yukarıdaki desene uymayan mevcut objeler ve gerekçesi. Ör. eski sistemden gelen ad, "
                              "BAdI implementasyon sınıfı.>")}
    if args.mevcut:
        ek = mevcut_kip(proj, name, owner)
        if isinstance(ek, int):
            return ek
        kaynak = ek.pop("_KAYNAK")
        mapping.update(ek)
        mapping["PKG_TYPE_NOTE"] = (f"{mapping['PKG_TYPE_NOTE']} **DOĞRULANMADI** — paket tipi adın sonekinden "
                                    "çıkarıldı; paketteki objelerle karşılaştırılmadı (`adt_package_contents`).\n\n"
                                    + kaynak)

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
    if args.mevcut:
        print("Sonraki adımlar:\n"
              f"  1. {name} SAP'de VAR (TADIR/TDEVC okundu); transportu kullanıcı verir → .rules.md Transport bölümü.\n"
              "  2. .rules.md'deki DOĞRULANMADI satırlarını paketteki objelerle doğrula (adt_package_contents) ya da "
              "kullanıcıya sor.\n"
              "  3. Değiştirilecek objeleri build'den ÖNCE bu klasöre indir (%sap-dev §3).\n"
              "  4. AGENTS.md proje kimliğindeki paket satırını güncelle.")
        print("KAPSAM — bakılanlar: TADIR (R3TR DEVC) AUTHOR/CREATED_ON · TDEVC PARENTCL · bakılmayanlar: paketteki "
              "objeler ve öneklere uyumu · transport · paket başlığı (TDEVCT) · yazılım bileşeni")
        return 0
    print("Sonraki adımlar:\n"
          f"  1. SAP'de {name} paketini SE21 ile SEN yarat (aXet paket yaratmaz — kesin yasak C) ve transportu belirle.\n"
          "  2. .rules.md: transport, bağımlılık ve bilinen istisnaları doldur.\n"
          "  3. SPEC.md: iş alımı (S0/S1/S2) ve kapsam bölümünü doldur.\n"
          "  4. AGENTS.md proje kimliğindeki paket satırını güncelle.")
    print("KAPSAM — yapılmayanlar: SAP'de paket yaratma ya da varlık kontrolü · obje adlarının doğrulanması")
    return 0


if __name__ == "__main__":
    sys.exit(main())
