#!/usr/bin/env python3
"""Davranış yüzeyi denetimi — ajanın davranışını değiştiren dosyalarda onaysız değişikliği görünür kılar.

aXet'te ayar değişikliği hook'u yok: sapma `doctor.py` (ve oturum özeti) üzerinden görünür. Önleme değil, tespittir.

PROJE modu (dizin template reposunun dışındaysa):
  yüzey    : AGENTS.md · .axet-code.json · .axetcode-denylist · sap-project.json · .githooks/** ·
             validators-local/** · .axet-code/skills/** · .axet-code/commands/**
  manifest : .axet-code/behavior-manifest.json (git'e girmez; ajan erişemez — `.axetcode-denylist`)
  generate [--only YOL ...]   yüzeyi onaylar: hash'leri yazar, NEYİ onayladığını ve neyin beklemede kaldığını basar
  check                       0 eş · 1 sapma · 2 manifest yok ya da okunamıyor
  Onayı kullanıcı KENDİ terminalinde verir; aXet oturumu `generate` çalıştırmaz.

TEMPLATE modu (dizin template reposuysa ya da --template):
  yüzey    : AGENTS.md · .axetcode-denylist · config/permissions.json · core/** · skills/** · skills-sap/** ·
             scripts/** · templates/** (tests/ ve __pycache__ hariç)
  onay     : git. Commit edilmemiş değişiklik ve upstream'e gitmemiş commit'lerdeki yüzey dosyaları sapmadır.
             Manifest tutulmaz (her `git pull` onay istemesin); `generate` bu modda reddedilir.
             İSTİSNA (Z5): `%guncelle`'nin kendi kimliğiyle attığı commit'ler sapma SAYILMAZ, bilgi olarak
             listelenir — klon push edilmediği için bunlar hiçbir zaman upstream'e gitmez (temizlenemez uyarı).

Hash satır sonu normalize edilerek alınır (CRLF↔LF farkı davranış taşımaz).
Kullanım:
  python <TEMPLATE>/scripts/behavior_manifest.py check|generate [--project-dir DİZİN] [--only YOL ...] [--template]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

AXET_HOME = Path(__file__).resolve().parents[1]
MANIFEST = Path(".axet-code") / "behavior-manifest.json"
PROJE_DOSYALAR = ["AGENTS.md", ".axet-code.json", ".axetcode-denylist", "sap-project.json"]
PROJE_DIZINLER = [".githooks", "validators-local", ".axet-code/skills", ".axet-code/commands"]
TEMPLATE_DOSYALAR = ["AGENTS.md", ".axetcode-denylist", "config/permissions.json"]
# scripts/ ve templates/ (Z89, kullanıcı kararı 2026-09-26): klondaki elle değişiklik doctor'da GÖRÜNSÜN — engel değil,
# görünürlük. `%guncelle`'nin kendi commit'leri kimliğiyle INFO'ya düşer (sapma sayılmaz); tests/ ve __pycache__ BUDANAN.
TEMPLATE_DIZINLER = ["core", "skills", "skills-sap", "scripts", "templates"]
BUDANAN = {"__pycache__", ".pytest_cache", "tests", "node_modules", ".git"}
# `%guncelle` akışının git kimliği ve anlık-commit konusu. KOPYADIR — kaynak: scripts/guncelle.py:51 (GIT_KIMLIK)
# ve :1456 (anlık commit mesajı). Eşliği tests/test_behavior_manifest.py::test_guncelle_kimligi_kaynakla_es pinler.
# guncelle.py buradan import EDİLMEZ: o modül ağır ve bu dosya doctor'ın sıcak yolunda.
GUNCELLE_EPOSTA = "guncelle@yerel"
GUNCELLE_ANLIK_ONEKI = "guncelle: yerel anlık"


def _hash(p: Path) -> str:
    ham = p.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(ham).hexdigest()[:16]


def _yuzey_yollari(kok: Path, dosyalar: list[str], dizinler: list[str]) -> list[str]:
    out = [d for d in dosyalar if (kok / d).is_file()]
    for d in dizinler:
        taban = kok / d
        if not taban.is_dir():
            continue
        for f in sorted(taban.rglob("*")):
            if f.is_file() and not (set(f.relative_to(kok).parts) & BUDANAN) and f.suffix != ".pyc":
                out.append(f.relative_to(kok).as_posix())
    return sorted(set(out))


def topla(proj: Path) -> dict[str, str]:
    return {rel: _hash(proj / rel) for rel in _yuzey_yollari(proj, PROJE_DOSYALAR, PROJE_DIZINLER)}


def manifest_oku(proj: Path) -> tuple[dict[str, str] | None, str | None]:
    """(kayıtlar, hata). Dosya yoksa (None, None)."""
    m = proj / MANIFEST
    if not m.is_file():
        return None, None
    try:
        veri = json.loads(m.read_text(encoding="utf-8"))
        kayit = veri.get("dosyalar") if isinstance(veri, dict) else None
        if not isinstance(kayit, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in kayit.items()):
            return None, f"{MANIFEST.as_posix()} biçimi geçersiz ('dosyalar' yol→hash nesnesi değil)"
        return kayit, None
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"{MANIFEST.as_posix()} okunamadı ({type(exc).__name__}: {exc})"


def sapmalar(canli: dict[str, str], beklenen: dict[str, str]) -> list[str]:
    out = []
    for rel, h in sorted(canli.items()):
        if rel not in beklenen:
            out.append(f"KAYITSIZ yeni davranış dosyası: {rel}")
        elif beklenen[rel] != h:
            out.append(f"DEĞİŞMİŞ (onaysız): {rel}")
    out += [f"manifest'te var, diskte YOK: {rel}" for rel in sorted(beklenen) if rel not in canli]
    return out


def proje_denetle(proj: Path) -> tuple[str, list[str]]:
    """('es'|'sapma'|'yok'|'bozuk', satırlar)"""
    kayit, hata = manifest_oku(proj)
    if hata:
        return "bozuk", [hata]
    if kayit is None:
        return "yok", []
    fark = sapmalar(topla(proj), kayit)
    return ("sapma", fark) if fark else ("es", [f"{len(kayit)} dosya"])


def generate(proj: Path, only: list[str] | None) -> tuple[list[str], list[str]]:
    """Manifest'i yazar. (onaylananlar, beklemede kalanlar)."""
    canli = topla(proj)
    onceki, hata = manifest_oku(proj)
    if hata and only is not None:
        raise SystemExit(f"HATA: {hata} — --only için okunabilir manifest gerekli (önce tam generate).")
    if only is None:
        onceki = onceki or {}
        onaylanan = [s for s in sapmalar(canli, onceki)]
        yeni, bekleyen = canli, []
    else:
        if onceki is None:
            raise SystemExit("HATA: --only için mevcut manifest gerekli (yok). Önce yüzeyi gözden geçirip tam generate.")
        istenen = {o.replace("\\", "/").strip() for o in only if o.strip()}
        bilinmeyen = sorted(i for i in istenen if i not in canli and i not in onceki)
        if bilinmeyen:
            raise SystemExit("HATA: --only yolu ne yüzeyde ne manifest'te: " + ", ".join(bilinmeyen)
                             + " — `check` çıktısındaki yolu AYNEN yaz.")
        yeni, onaylanan = dict(onceki), []
        for rel in sorted(istenen):
            if rel in canli:
                if yeni.get(rel) != canli[rel]:
                    onaylanan.append(f"{rel}")
                yeni[rel] = canli[rel]
            elif rel in yeni:
                del yeni[rel]
                onaylanan.append(f"{rel} (kayıt düşürüldü — diskte yok)")
        bekleyen = sapmalar(canli, yeni)
    m = proj / MANIFEST
    m.parent.mkdir(parents=True, exist_ok=True)
    m.write_text(json.dumps({"_aciklama": "behavior_manifest.py generate yazar; elle düzenleme. Davranış yüzeyinin "
                                          "onaylı hash'leri (satır sonu normalize).",
                             "surum": 1, "dosyalar": dict(sorted(yeni.items()))}, indent=1, ensure_ascii=False) + "\n",
                 encoding="utf-8")
    return onaylanan, bekleyen


def _git(kok: Path, *args: str) -> tuple[int, str]:
    try:
        r = subprocess.run(["git", "-C", str(kok), *args], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", stdin=subprocess.DEVNULL, timeout=20)
        return r.returncode, r.stdout
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, type(exc).__name__


def _yuzeyde_mi(rel: str) -> bool:
    parcalar = rel.split("/")
    if rel in TEMPLATE_DOSYALAR:
        return True
    return parcalar[0] in TEMPLATE_DIZINLER and not (set(parcalar) & BUDANAN) and not rel.endswith(".pyc")


def _commit_sahipleri(kok: Path) -> tuple[set[str], set[str], set[str], str]:
    """`@{u}..HEAD` commit'lerindeki yüzey dosyalarını YAZARA göre ayırır.

    Dönüş: (anlik, uygulama, kullanici, not). `%guncelle` iki tür commit atar ve ikisi de kendi git
    kimliğini kullanır (`scripts/guncelle.py:51` GIT_KIMLIK); konusu onları birbirinden ayırır:
      · `guncelle: yerel anlık <tarih>` (`guncelle.py:1456`) → KULLANICININ commit'siz değişikliklerini saklayan anlık commit
      · `guncelle: <etiket> kalemler …`  (`guncelle.py:1331`) → template güncellemesinin uygulanması
    Not dolu dönerse ölçüm yapılamamıştır; çağıran her şeyi 'kullanici' saymalıdır (temkinli taraf).
    """
    anlik: set[str] = set()
    uygulama: set[str] = set()
    kullanici: set[str] = set()
    # %x00 sentinel: dosya adları NUL içeremez → commit başlığı ile dosya satırı karışmaz.
    # --no-merges: merge commit'leri --name-only ile diff üretmez; atfedilemeyen dosya çağırana 'kullanici' olarak döner.
    rc, log = _git(kok, "log", "--no-merges", "--format=%x00%ae%x00%s", "--name-only", "@{u}..HEAD", "--",
                   *TEMPLATE_DOSYALAR, *TEMPLATE_DIZINLER)
    if rc:
        return anlik, uygulama, kullanici, "commit yazarları okunamadı — sapma sınıfı ÖLÇÜLEMEDİ, tümü kullanıcı sayıldı"
    aktif: set[str] | None = None
    for satir in log.splitlines():
        if satir.startswith("\0"):
            parcalar = satir.split("\0")
            eposta = parcalar[1].strip() if len(parcalar) > 1 else ""
            konu = parcalar[2] if len(parcalar) > 2 else ""
            if eposta == GUNCELLE_EPOSTA:
                aktif = anlik if konu.startswith(GUNCELLE_ANLIK_ONEKI) else uygulama
            else:
                aktif = kullanici
        elif satir.strip() and aktif is not None:
            aktif.add(satir.strip())
    return anlik, uygulama, kullanici, ""


def template_sinifla(kok: Path = AXET_HOME) -> dict:
    """Template davranış yüzeyi denetimi, sapma SINIFLARINA ayrılmış (Z5).

    Dönüş: {"durum": 'es'|'sapma'|'olculemedi', "kullanici": [satır], "guncelle_anlik": [yol],
            "guncelle_uygulama": [yol], "notlar": [satır]}.

    `durum` YALNIZ "kullanici" doluysa 'sapma'dır. Gerekçe: `%guncelle` yerel commit atar ve klon
    hiçbir zaman `origin`'e push edilmez (motor `origin/main`'den geçici kopyaya çekilir) → bu
    commit'ler YAPISAL olarak "upstream'de yok" kalır. Her oturumda temizlenemeyecek bir uyarı
    basmak, uyarının tamamını değersizleştirir; bu yüzden bilgi satırına iner (bkz. doctor).
    ⚠ ÖLÇÜLEN SINIR: ayrım commit'i KİMİN ATTIĞINA bakar, içeriği kimin YAZDIĞINA değil. `guncelle:
    yerel anlık` commit'inin İÇERİĞİ kullanıcınındır; bu yüzden ayrı bir sınıfta tutulur ve raporda
    ayrı ifade edilir, `guncelle_uygulama` ile aynı torbaya konmaz.
    """
    o: dict = {"durum": "olculemedi", "kullanici": [], "guncelle_anlik": [], "guncelle_uygulama": [], "notlar": []}
    rc, _ = _git(kok, "rev-parse", "--is-inside-work-tree")
    if rc:
        o["notlar"] = [f"{kok} git reposu değil — template davranış yüzeyi ÖLÇÜLEMEDİ"]
        return o
    rc, st = _git(kok, "status", "--porcelain", "-z", "--untracked-files=all", "--",
                  *TEMPLATE_DOSYALAR, *TEMPLATE_DIZINLER)
    if rc:
        o["notlar"] = ["git status çalışmadı — template davranış yüzeyi ÖLÇÜLEMEDİ"]
        return o
    girdiler = [g for g in st.split("\0") if g]
    i = 0
    while i < len(girdiler):
        g = girdiler[i]
        kod, rel = g[:2], g[3:]
        if kod[0] in "RC":  # yeniden adlandırmada kaynak yol ayrı girdi olarak gelir
            i += 1
        if _yuzeyde_mi(rel):
            # Çalışma ağacı DAİMA kullanıcının: %guncelle işini commit'ler, commit'siz bırakmaz.
            o["kullanici"].append(("KAYITSIZ yeni dosya (commit'siz)" if kod == "??" else f"commit edilmemiş değişiklik [{kod.strip()}]")
                                  + f": {rel}")
        i += 1
    rc, ust = _git(kok, "rev-parse", "--abbrev-ref", "@{u}")
    if rc:
        o["notlar"].append("upstream tanımlı değil — upstream'e gitmemiş commit'ler ÖLÇÜLEMEDİ")
    else:
        rc, fark = _git(kok, "diff", "--name-only", "@{u}...HEAD", "--", *TEMPLATE_DOSYALAR, *TEMPLATE_DIZINLER)
        if rc:
            o["notlar"].append("upstream farkı alınamadı — ÖLÇÜLEMEDİ")
        else:
            tum = sorted({r.strip() for r in fark.splitlines() if r.strip() and _yuzeyde_mi(r.strip())})
            anlik, uygulama, kul_c, uyari = _commit_sahipleri(kok)
            if uyari:
                o["notlar"].append(uyari)
            for r in tum:
                if r in kul_c or (r not in anlik and r not in uygulama):
                    # atfedilemeyen (merge commit'i, ölçüm hatası) → temkinli taraf: kullanıcı
                    o["kullanici"].append(f"upstream'de ({ust.strip()}) olmayan yerel commit'te: {r}")
                elif r in anlik:
                    o["guncelle_anlik"].append(r)
                else:
                    o["guncelle_uygulama"].append(r)
    o["durum"] = "sapma" if o["kullanici"] else "es"
    return o


def template_denetle(kok: Path = AXET_HOME) -> tuple[str, list[str]]:
    """('es'|'sapma'|'olculemedi', satırlar) — `template_sinifla`'nın 2'li geriye uyumlu sarmalayıcısı."""
    o = template_sinifla(kok)
    if o["durum"] == "olculemedi":
        return o["durum"], o["notlar"]
    return o["durum"], (o["kullanici"]
                        + [f"%guncelle anlık commit'inde (kullanıcı içeriği): {r}" for r in o["guncelle_anlik"]]
                        + [f"%guncelle'nin uyguladığı güncellemede: {r}" for r in o["guncelle_uygulama"]]
                        + o["notlar"])


def _template_mi(proj: Path, zorla: bool) -> bool:
    return zorla or proj == AXET_HOME or AXET_HOME in proj.parents


def main() -> int:
    ap = argparse.ArgumentParser(description="Davranış yüzeyi denetimi / onayı")
    ap.add_argument("komut", choices=["check", "generate"])
    ap.add_argument("--project-dir", default=".", help="proje kökü (varsayılan: bulunulan dizin)")
    ap.add_argument("--only", action="append", help="generate: yalnız bu yolu onayla (tekrarlanabilir)")
    ap.add_argument("--template", action="store_true", help="template reposunun yüzeyini denetle")
    args = ap.parse_args()
    proj = Path(args.project_dir).resolve()

    if _template_mi(proj, args.template):
        if args.komut == "generate":
            print("HATA: template modunda manifest yok — onay git'tir (commit + upstream). "
                  "Proje yüzeyini onaylamak için proje kökünde çalıştır.")
            return 2
        o = template_sinifla(AXET_HOME)
        durum = o["durum"]
        print(f"[{'OK' if durum == 'es' else 'SAPMA' if durum == 'sapma' else 'ÖLÇÜLEMEDİ'}] template davranış yüzeyi · {AXET_HOME}")
        for s in o["kullanici"]:
            print(f"   ! {s}")
        for r in o["guncelle_anlik"]:
            print(f"   i %guncelle anlık commit'inde (İÇERİK KULLANICININ, commit `%guncelle`'nin): {r}")
        for r in o["guncelle_uygulama"]:
            print(f"   i %guncelle'nin uyguladığı template güncellemesinde: {r}")
        for s in o["notlar"]:
            print(f"   {s}")
        print("KAPSAM — bakılanlar: git'e göre commit'siz ve upstream'e gitmemiş yüzey dosyaları · bakılmayanlar: "
              "commit'lenmiş değişikliğin içeriği (onay git geçmişidir), memory/ tests/ · "
              f"'{GUNCELLE_EPOSTA}' kimliğiyle atılmış commit'ler sapma SAYILMAZ (yapısal olarak upstream'e gitmez) — "
              "kimlik taklit edilebilir, bu bir güvenlik sınırı DEĞİL, gürültü ayıklamasıdır · "
              "merge commit'leriyle gelen dosyalar atfedilemez ve temkinli olarak kullanıcı sayılır")
        return 0 if durum == "es" else 1

    if args.komut == "generate":
        onaylanan, bekleyen = generate(proj, args.only)
        print(f"[OK] manifest yazıldı: {proj / MANIFEST} ({len(topla(proj))} yüzey dosyası · kapsam: "
              f"{'YALNIZ ' + str(len(args.only)) + ' yol' if args.only else 'TÜM yüzey'})")
        if onaylanan:
            print(f"  ONAYLANAN {len(onaylanan)}:")
            for s in onaylanan:
                print(f"   + {s}")
        else:
            print("  (onaylanan değişiklik yok — manifest zaten günceldi)")
        if not args.only and len(onaylanan) > 1:
            print(f"  ⚠ TOPLU ONAY: {len(onaylanan)} kalem tek komutla onaylandı. Bilinçli olmayan varsa şimdi geri al; "
                  "seçici onay: generate --only <yol>")
        if bekleyen:
            print(f"  BEKLEMEDE {len(bekleyen)} (onaylanmadı):")
            for s in bekleyen:
                print(f"   ! {s}")
        return 0

    durum, satirlar = proje_denetle(proj)
    if durum == "es":
        print(f"[OK] davranış yüzeyi manifest'le eş ({satirlar[0]})")
        rc = 0
    elif durum == "yok":
        print(f"[YOK] {MANIFEST.as_posix()} yok — yüzeyi gözden geçir, sonra kendi terminalinde: "
              f"python \"{Path(__file__).resolve()}\" generate")
        rc = 2
    elif durum == "bozuk":
        print(f"[FAIL] {satirlar[0]}")
        rc = 2
    else:
        print("[SAPMA] davranış yüzeyinde onaysız değişiklik:")
        for s in satirlar:
            print(f"   ! {s}")
        print("Bilinçliyse kendi terminalinde: generate --only <yol>; değilse değişikliği geri al.")
        rc = 1
    print("KAPSAM — bakılanlar: " + " · ".join(PROJE_DOSYALAR + [d + "/**" for d in PROJE_DIZINLER])
          + " · bakılmayanlar: proje hafızası, kaynak kod, global aXet config'i, template klonu (--template)")
    return rc


if __name__ == "__main__":
    sys.exit(main())
