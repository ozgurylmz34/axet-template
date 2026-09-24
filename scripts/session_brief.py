#!/usr/bin/env python3
"""Oturum açılış özeti — aXet'te SessionStart hook'u olmadığı için çekirdek §0 bunu ilk yanıttan önce bir kez çalıştırtır.

Basar: git durum çapası (dal, son commit, değişen dosyalar, upstream ileri/geri) · template klonu güncel mi ·
hızlı sağlık (doctor statik kontrollerinin FAIL/WARN satırları) · aktif paket ve SESSION_NOTES son kaydı ·
proje iş listesi (aktif işler + ertelenmiş tetikler) · devir notları · AGENTS.md "Açık işler".
Proje dosyalarına yazmaz; model çağrısı yapmaz. Template için saatte en fazla bir `git fetch` yapar
(önbellek: ~/.axet-template-cache/last_fetch) — `--no-fetch` ile kapatılır.

Kullanım:
  python <TEMPLATE>/scripts/session_brief.py [--project-dir DİZİN] [--no-fetch]
"""
from __future__ import annotations

import argparse
import contextlib
import io
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

AXET_HOME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

FETCH_CACHE = Path.home() / ".axet-template-cache" / "last_fetch"
FETCH_EVERY_SEC = 3600
IS_LISTESI = Path(".axet-code") / "memory" / "project_is-listesi.md"
AZAMI_MADDE = 8


def _git(cwd: Path, *args: str, timeout: int = 5) -> tuple[int, str]:
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    try:
        r = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, env=env)
        # ⚠ Yalnız SONDAN kırp: porcelain satırı boşlukla başlar (" M a.txt"); baştan kırpmak ilk
        # dosya adının ilk karakterini yutuyordu (rc taraması 2026-09-18, ölçüldü: `.txt`).
        return r.returncode, r.stdout.rstrip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, type(exc).__name__


def _yorumsuz(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)


def durum_capasi(proj: Path) -> list[str]:
    rc, _ = _git(proj, "rev-parse", "--is-inside-work-tree")
    if rc:
        return ["git reposu değil — durum çapası ÖLÇÜLEMEDİ"]
    _, dal = _git(proj, "rev-parse", "--abbrev-ref", "HEAD")
    _, son = _git(proj, "log", "-1", "--format=%h %s (%cr)")
    rc_st, st = _git(proj, "status", "--porcelain")
    degisen = [s for s in st.splitlines() if s.strip()] if rc_st == 0 else []
    out = [f"dal: {dal}", f"son commit: {son or '(commit yok)'}"]
    if rc_st != 0:
        # git status başarısızsa (bozuk index, zaman aşımı) "temiz" DENMEZ — ölçülemedi ≠ temiz.
        out.append(f"değişiklik: ÖLÇÜLEMEDİ (git status rc={rc_st})")
    elif degisen:
        ornek = ", ".join(s[3:] for s in degisen[:5]) + (" …" if len(degisen) > 5 else "")
        out.append(f"değişiklik: {len(degisen)} dosya — {ornek}")
        if dal in ("main", "master"):
            out.append("⚠ main üzerinde commit edilmemiş değişiklik var — çalışmaya devam etmeden dal aç")
    else:
        out.append("değişiklik: yok (çalışma ağacı temiz)")
    rc, ab = _git(proj, "rev-list", "--left-right", "--count", "@{u}...HEAD")
    if rc == 0 and len(ab.split()) == 2:
        geri, ileri = ab.split()
        out.append(f"upstream: {ileri} ileri · {geri} geri (son fetch'e göre)")
    else:
        out.append("upstream: tanımlı değil ya da ÖLÇÜLEMEDİ")
    return out


def template_durumu(fetch: bool) -> list[str]:
    rc, _ = _git(AXET_HOME, "rev-parse", "--is-inside-work-tree")
    if rc:
        return [f"{AXET_HOME}: git reposu değil — güncellik ÖLÇÜLEMEDİ"]
    not_ = ""
    if fetch:
        try:
            yas = time.time() - FETCH_CACHE.stat().st_mtime if FETCH_CACHE.exists() else None
        except OSError:
            yas = None
        if yas is None or yas > FETCH_EVERY_SEC:
            rc, _ = _git(AXET_HOME, "fetch", "--quiet", timeout=8)
            if rc:
                not_ = " (fetch başarısız — son bilinen duruma göre)"
            else:
                with contextlib.suppress(OSError):
                    FETCH_CACHE.parent.mkdir(parents=True, exist_ok=True)
                    FETCH_CACHE.touch()
    rc, ab = _git(AXET_HOME, "rev-list", "--left-right", "--count", "@{u}...HEAD")
    if rc or len(ab.split()) != 2:
        return ["template: upstream tanımlı değil — güncellik ÖLÇÜLEMEDİ"]
    geri = ab.split()[0]
    if geri != "0":
        return [f"template {geri} commit geride{not_} → `git -C \"{AXET_HOME.as_posix()}\" pull` (sonra yeni oturum)"]
    return [f"template güncel{not_}"]


# --- P7 / TASARIM §11: günlük güncelleme kontrolü + kritik hatırlatma ------------------------------------
# Ayrı önbellek ve eşik (Q4): güncelleme kontrolü GÜNDE BİR yapılır, saatlik `FETCH_CACHE` değil.
# Kalem satırı, `template_durumu()`'nun "N commit geride" satırıyla YER DEĞİŞTİRİR — iki bildirim olmasın.
GUNCELLEME_CACHE = Path.home() / ".axet-template-cache" / "last_guncelle_check"
GUNCELLEME_EVERY_SEC = 86400
DURUM_DIZIN_ADI = ".axet-guncelleme"          # scripts/guncelle.py:46 ile AYNI ad
YAYINLAR_REF = "origin/main:guncelle/yayinlar.json"


def _gunluk_fetch(fetch: bool) -> str:
    """Günde en fazla bir `git fetch`. Ağ hatası SESSİZ (bugünkü davranış) — yalnız not döner."""
    if not fetch:
        return ""
    try:
        yas = time.time() - GUNCELLEME_CACHE.stat().st_mtime if GUNCELLEME_CACHE.exists() else None
    except OSError:
        yas = None
    if yas is not None and yas <= GUNCELLEME_EVERY_SEC:
        return ""
    rc, _ = _git(AXET_HOME, "fetch", "--quiet", timeout=8)
    if rc:
        return " (fetch başarısız — son bilinen duruma göre)"
    with contextlib.suppress(OSError):
        GUNCELLEME_CACHE.parent.mkdir(parents=True, exist_ok=True)
        GUNCELLEME_CACHE.touch()
    return ""


def guncelleme_kalemleri() -> list[dict] | None:
    """`origin/main:guncelle/yayinlar.json` x `.axet-guncelleme/uygulanan.json` -> kalem durumları.

    Döner: her kalem için {id, baslik, kritik, durum} — `durum` None ise kalem hiç uygulanmamış
    (bekliyor); "icerildi" ise kalemin yayını klonda zaten var (`guncelle.yayin_durumu`). ÖLÇÜLEMEZSE None döner (dosya yok / bozuk / git okuyamadı): "0 kalem" ile
    "ölçemedim" karıştırılmasın diye ayrı değer. Hiçbir yere YAZMAZ.
    Alan adları `scripts/guncelle.py`'nin yazdığı/okuduğu adlardır (koddan doğrulandı: :529-539, :1312-1327).
    """
    import json  # yerel: bu dosyanın öteki bölümleri json'a bağımlı değil
    rc, ham = _git(AXET_HOME, "show", YAYINLAR_REF, timeout=8)
    if rc or not ham.strip():
        return None
    try:
        veri = json.loads(ham)
    except ValueError:
        return None
    if not isinstance(veri, dict) or not isinstance(veri.get("yayinlar"), list):
        return None
    kayit: dict = {}
    f = AXET_HOME / DURUM_DIZIN_ADI / "uygulanan.json"
    if f.is_file():
        try:
            u = json.loads(f.read_text(encoding="utf-8", errors="replace"))
            kayit = u.get("kalemler") if isinstance(u, dict) and isinstance(u.get("kalemler"), dict) else {}
        except ValueError:
            kayit = {}
    try:
        from guncelle import yayin_durumu  # K-F: motorla TEK KAYNAK (aynı klasör)
    except Exception:  # noqa: BLE001 — motor içe aktarılamıyorsa ata testi ÖLÇÜLEMEZ
        return None
    kalemler = []
    for yayin in veri["yayinlar"]:
        if not isinstance(yayin, dict):
            continue
        # Yayın klonda zaten İÇERİLİYORSA (taze klon) motor onu plana hiç almaz ⇒ kalemi
        # "bekliyor" saymak kalıcı sahte bildirim üretir. Çözülemeyen etiket bekleyen sayılır
        # (motorla aynı: içerilip içerilmediği ölçülemez).
        icerildi = yayin_durumu(lambda *a: _git(AXET_HOME, *a, timeout=8)[0],
                                str(yayin.get("etiket") or "")) == "icerildi"
        for k in yayin.get("kalemler") or []:
            if not isinstance(k, dict) or not k.get("id"):
                continue
            kd = kayit.get(k["id"])
            kalemler.append({
                "id": k["id"], "baslik": k.get("baslik", ""),
                # tur=guvenlik ise kritik (scripts/guncelle.py:600 ile AYNI türetme)
                "kritik": bool(k.get("kritik") or k.get("tur") == "guvenlik"),
                "durum": ("icerildi" if icerildi else
                          kd.get("durum") if isinstance(kd, dict) else None),
            })
    return kalemler


def template_bolumu(fetch: bool) -> list[str]:
    """TEMPLATE bölümü. Kalem satırı ölçülebiliyorsa commit sayısı satırının YERİNE geçer (Q4);
    ölçülemiyorsa ya da HİÇ kalem tanımlı değilse bugünkü satır AYNEN kalır.

    Üç durum bilinçli olarak AYRIDIR:
      None  ÖLÇÜLEMEDİ (yayinlar.json yok / bozuk / git okuyamadı) → bugünkü satır aynen.
      []    ölçüldü ama HİÇ yayın kalemi tanımlı değil → bugünkü satır aynen (aşağıdaki nota bak).
      [...] kalemler var → kalem satırı commit sayısı satırının YERİNE geçer (Q4).
    """
    not_ = _gunluk_fetch(fetch)
    satirlar = template_durumu(False)          # fetch'i yukarıda GÜNLÜK eşikle biz yaptık
    kalemler = guncelleme_kalemleri()
    if kalemler is None:
        return satirlar
    if not kalemler:
        # ÖLÇÜLDÜ ama hiç yayın kalemi YOK (`"yayinlar": []` — ilk gerçek yayına kadarki hâl).
        # Bu, "kalemler var, hepsi uygulanmış" ile AYNI ŞEY DEĞİLDİR: commit sayısı satırının
        # yerine geçecek bir bilgi yoktur, o yüzden o satır KORUNUR.
        # REGRESYON 2026-09-18 (ölçüldü): bu dal ayrılmadığında klon 5 commit geride olduğu hâlde
        # "template güncel" deniyordu — tek satırlık çıktı sessizce yanlıştı.
        # Kilit: tests/…::test_kalem_tanimli_degilse_commit_geride_satiri_korunur
        return satirlar
    bekleyen = [k for k in kalemler if k["durum"] is None]
    yeni = ([f"template: {len(bekleyen)} güncelleme kalemi bekliyor{not_} -> `%guncelle`"] if bekleyen
            else [f"template güncel{not_} (bekleyen güncelleme kalemi yok)"])
    # Q3: kritik kalemler ayrı liste tutulmaz, aynı kaynaktan türetilir; `atlandi` işaretlense de görünür kalır.
    for k in kalemler:
        if not k["kritik"] or k["durum"] in ("uygulandi", "icerildi"):
            continue
        durum = "atlandı (kritik)" if k["durum"] == "atlandi" else "bekliyor"
        yeni.append(f"WARN kritik güncelleme {durum}: {k['id']} {k['baslik']}".rstrip())
    # commit sayısı satırı düşer, ÖLÇÜLEMEDİ satırları korunur (bilgi kaybı olmasın)
    return yeni + [s for s in satirlar if "ÖLÇÜLEMEDİ" in s or "git reposu değil" in s]


def saglik(proj: Path) -> list[str]:
    import doctor  # aynı klasör
    doctor.results.clear()
    with contextlib.redirect_stdout(io.StringIO()):
        _, sap = doctor.check_global()
        doctor.check_template()
        doctor.check_project(proj, sap)
        # Z101: SAP oturumu requests/dotenv eksikken ilk SAP çağrısında düşer — açılışta görünsün (yalnız WARN taşınır)
        doctor.check_paketler(sap or (proj / "sap-project.json").exists())
    kotu = [f"{s}: {m}" for s, m in doctor.results if s in ("FAIL", "WARN")]
    return kotu or ["doctor statik kontroller: FAIL/WARN yok"]


def sablon_surumu(proj: Path) -> list[str]:
    """PROJE ŞABLONU bölümü — TASARIM §9 tetiği: "proje şablonu eski → %guncelle-proje".

    Ölçüm `new_project.sablon_surumu_durumu`'ndadır; `doctor.py check_sablon_surumu` AYNI
    fonksiyonu çağırır (tek kaynak; iki ayrı ölçüm yazılırsa biri bayatlar). Bu fonksiyon
    yalnız sunum yapar, hiçbir şey YAZMAZ ve ağa ÇIKMAZ.
    """
    import new_project as nprj  # aynı klasör
    durum, mesaj = nprj.sablon_surumu_durumu(proj)
    satirlar = [("⚠ " if durum in ("eski", "kayitsiz", "cozulemedi") else "") + mesaj]
    if durum in ("eski", "kayitsiz", "cozulemedi"):
        satirlar.append("her proje AYRI onaylanır — toplu tarama yok (Q1)")
    return satirlar


def son_kayit(notes: Path) -> list[str]:
    if not notes.is_file():
        return ["SESSION_NOTES.md yok"]
    m = re.search(r"^### .+?(?=^### |\Z)", _yorumsuz(notes.read_text(encoding="utf-8", errors="replace")), re.S | re.M)
    if not m:
        return ["SESSION_NOTES: kayıt yok"]
    satirlar = [s.rstrip() for s in m.group(0).strip().splitlines() if s.strip()]
    return ["SESSION_NOTES son kayıt:"] + ["  " + s for s in satirlar[:AZAMI_MADDE]] + (["  …"] if len(satirlar) > AZAMI_MADDE else [])


# SAP paket adı: müşteri adı alanı Z/Y (new_package.AD ile aynı) ya da /ADALANI/AD; uzunluk ayrıca en fazla 30.
PAKET_ADI = re.compile(r"[ZY][A-Z0-9_]{1,29}|/[A-Z0-9_]+/[A-Z0-9_]+")


def aktif_paket(proj: Path) -> list[str]:
    if not (proj / "sap-project.json").is_file():
        return []
    import new_package as npk  # aynı klasör
    root, err = npk.source_root(proj)
    if err:
        return [f"paket: {err}"]
    paketler = npk.paketler(root)
    agents = proj / "AGENTS.md"
    ad = deger = None
    if agents.is_file():
        # Değer aynı satırdan, ilk " · " / " (" öncesine kadar okunur; ilk sözcüğü SAP paket adı biçimine uymalı.
        # Büyük harfe çevrilmez: "yok" → "YOK" (Y + 2 karakter, biçimce geçerli) olurdu; SAP paket adları büyük harftir.
        m = re.search(r"aktif paket:[ \t]*([^·(\r\n]*)", agents.read_text(encoding="utf-8", errors="replace"), re.I)
        if m and m.group(1).strip():
            deger = m.group(1).strip()
            aday = deger.split()[0].strip("`")
            if len(aday) <= 30 and PAKET_ADI.fullmatch(aday):
                ad = aday
    if not ad:
        adlar = ", ".join(p.name for _, p in paketler[:6]) + (" …" if len(paketler) > 6 else "")
        liste = f"{len(paketler)} paket" + (f": {adlar}" if paketler else "")
        if deger and not deger.startswith(("<", "—", "-")):  # yer tutucu / yeni_proje.AKTIF_PAKET_YOK = yazılmamış
            return [f"aktif paket ÖLÇÜLEMEDİ: AGENTS.md değeri {deger!r} geçerli bir SAP paket adı değil "
                    f"(Z/Y ile başlayan ya da /ADALANI/AD) → paket yok sayıldı · {liste}"]
        return [f"aktif paket AGENTS.md'de yazılı değil · {liste}"]
    bulunan = [p for _, p in paketler if p.name == ad]
    if not bulunan:
        return [f"aktif paket {ad}: {root.name}/ altında klasörü yok → new_package.py"]
    return [f"aktif paket: {ad}"] + son_kayit(bulunan[0] / "SESSION_NOTES.md")


def _maddeler(text: str, baslik: str) -> list[str]:
    m = re.search(rf"^## {re.escape(baslik)}[^\n]*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    if not m:
        return []
    return [s.strip() for s in m.group(1).splitlines()
            if s.strip().startswith(("- ", "* ")) and not re.search(r"^[-*]\s*<", s.strip())]


def is_listesi(proj: Path) -> list[str]:
    f = proj / IS_LISTESI
    if not f.is_file():
        return [f"{IS_LISTESI.as_posix()} yok → new_project.py (var olan dosyaları ezmez)"]
    t = _yorumsuz(f.read_text(encoding="utf-8", errors="replace"))
    out = []
    for baslik in ("Aktif işler", "Ertelenmiş tetikler"):
        maddeler = _maddeler(t, baslik)
        out.append(f"{baslik}: {len(maddeler)}")
        out += ["  " + s for s in maddeler[:AZAMI_MADDE]] + (["  …"] if len(maddeler) > AZAMI_MADDE else [])
    return out


def devir_notlari(proj: Path) -> list[str]:
    notlar = sorted((proj / ".axet-code" / "memory").glob("project_devir-*.md"))
    out = []
    for n in notlar:
        m = re.search(r"^description:\s*(.+)$", n.read_text(encoding="utf-8", errors="replace"), re.M)
        out.append(f"{n.name} — {m.group(1).strip() if m else '(açıklama yok)'}")
    return out or ["yok"]


def agents_acik_isler(proj: Path) -> list[str]:
    f = proj / "AGENTS.md"
    if not f.is_file():
        return []
    return _maddeler(_yorumsuz(f.read_text(encoding="utf-8", errors="replace")), "Açık işler")


def main() -> int:
    ap = argparse.ArgumentParser(description="aXet oturum açılış özeti (salt-okur)")
    ap.add_argument("--project-dir", default=".", help="proje kökü (varsayılan: bulunulan dizin)")
    ap.add_argument("--no-fetch", action="store_true", help="template için git fetch yapma")
    args = ap.parse_args()
    proj = Path(args.project_dir).resolve()
    template_ici = proj == AXET_HOME or AXET_HOME in proj.parents

    bolumler = [("DURUM ÇAPASI (git)", lambda: durum_capasi(proj)),
                ("TEMPLATE", lambda: template_bolumu(not args.no_fetch)),
                ("SAĞLIK", lambda: saglik(proj))]
    if not template_ici:
        bolumler += [("PAKET", lambda: aktif_paket(proj)),
                     ("İŞ LİSTESİ", lambda: is_listesi(proj)),
                     ("DEVİR NOTLARI", lambda: devir_notlari(proj)),
                     ("AGENTS.md AÇIK İŞLER", lambda: agents_acik_isler(proj))]
        # P5 tetiği (TASARIM §9) — ayrı bölüm, ayrı fonksiyon (paylaşılan dosya: satır serpiştirme yok)
        bolumler.append(("PROJE ŞABLONU", lambda: sablon_surumu(proj)))

    print(f"[OTURUM ÖZETİ — session_brief.py · {datetime.now():%Y-%m-%d %H:%M} · {proj}]")
    for ad, fn in bolumler:
        try:
            satirlar = fn()
        except Exception as exc:  # noqa: BLE001 — bir bölüm düşerse diğerleri yine basılır
            satirlar = [f"ÖLÇÜLEMEDİ ({type(exc).__name__}: {exc})"]
        if satirlar:
            print(f"\n{ad}:")
            for s in satirlar:
                print(f"  {s}")
    print("\nKAPSAM — bakılmayanlar: SAP bağlantısı · bağlamın fiilen yüklendiği (doctor.py --live) · "
          "uzak depodaki değişiklikler (fetch yapılmadıysa) · iş listesi maddelerinin güncelliği")
    return 0


if __name__ == "__main__":
    sys.exit(main())
