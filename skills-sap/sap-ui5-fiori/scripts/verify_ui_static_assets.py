#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_ui_static_assets.py — BSP'deki STATİK uygulama dosyaları canlıda güncel mi? (SALT-OKUMA)

NEDEN: `deploy_ui.py verify` yalnız `Component-preload.js`'i kanıtlar. `webapp/help/**` (uygulama içi kılavuz,
ekran görüntüleri) gibi statik dosyalar preload'a GİRMEZ, ayrı servis edilir → yardım sayfası bayat kalsa bile
preload doğrulaması "güncel" der. Bu script dosyaların KENDİSİNİ canlıdan çeker.

KIYAS İNCELİKLERİ (ölçülmüş; ham bayt kıyası yanlış alarm verir):
  1) BSP runtime HTML `<head>`'ine üç meta enjekte eder: sap-client · sap-ui-fesr · sap.whitelistService.
     Metin kıyasından önce bu blok ayıklanır, satır sonu normalize edilir. İkili dosya ham bayt kıyaslanır.
  2) `ui5 build` `.properties` dosyasını dönüştürür (non-ASCII → `\\uXXXX`, LF). Kaynak (webapp) kıyasında
     `.properties` çözülmüş (anahtar, değer) dizisi olarak karşılaştırılır.

Her uygulama için (`--subdir`, varsayılan help):
  EKSEN ① canlı ↔ dist (deploy edilen): fark = FARKLI. Dosya dist'te yoksa taban webapp (not basılır).
  EKSEN ② canlı ↔ webapp (kaynak): fark = KAYNAK FARKI (canlı == dist ama webapp'te build edilmemiş değişiklik).

Kullanım:
  python verify_ui_static_assets.py <app_dir> [<app_dir>...] [--subdir help] [--ignore-cert]
Kimlik: env FIORI_TOOLS_USER / FIORI_TOOLS_PASSWORD. Hedef URL/client/BSP: her uygulamanın ui5-deploy.yaml'ı.
Çıkış: 0 tüm dosyalar AYNI · 1 fark / canlıda yok · 2 ölçüm yok (yol yok, env kimlik yok, deploy ayarı okunamadı)
YAZMAZ, DEPLOY ETMEZ.
"""
from __future__ import annotations

import argparse
import re
import sys
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bspnet as B  # noqa: E402

INJECTED_META = re.compile(
    r'<meta name="sap-client"[^>]*>'
    r'<meta name="sap-ui-fesr"[^>]*>'
    r'<meta name="sap\.whitelistService"[^>]*>'
)
TEXT_SUFFIXES = {".html", ".htm", ".css", ".js", ".json", ".txt", ".xml", ".properties"}
BUILD_DONUSUMLU = {".properties"}
_U_KACIS = re.compile(r"(?<!\\)((?:\\\\)*)\\u([0-9a-fA-F]{4})")
_PROP_SATIR = re.compile(r"\s*((?:[^=:\s\\]|\\.)+)\s*[=:]?\s*(.*)$")

BAKILMAYANLAR = [
    "--subdir dışındaki dosyalar (preload için: deploy_ui.py verify)",
    "tarayıcı/FLP önbelleği (GET cache-bust'lı; kullanıcı tarayıcısı hard refresh ister)",
    "BSP enjekte meta bloğunun biçimi değişirse HTML kıyası yanlış FARKLI verebilir — dokunulmamış uygulama da FARKLI ise önce ölçümden şüphelen",
    "yalnız .properties için build dönüşümü modellenmiştir; başka dönüşen uzantı ölçülmedi",
]


def normalize(raw: bytes, is_text: bool) -> bytes:
    if not is_text:
        return raw
    s = raw.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
    return INJECTED_META.sub("", s).encode("utf-8", errors="replace")


def properties_cozumle(raw: bytes) -> list:
    """`.properties` → sıralı (anahtar, değer) listesi; `\\uXXXX` çözülür, yorum/boş satır atlanır."""
    t = raw.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
    t = _U_KACIS.sub(lambda m: m.group(1) + chr(int(m.group(2), 16)), t)
    t = t.encode("utf-16", "surrogatepass").decode("utf-16", errors="replace")
    ciftler = []
    for satir in t.split("\n"):
        s = satir.lstrip()
        if not s or s[0] in "#!":
            continue
        m = _PROP_SATIR.match(satir)
        ciftler.append((m.group(1), m.group(2)) if m else (s, ""))
    return ciftler


def icerik_esit(a: bytes, b: bytes, sonek: str, cozumle: bool) -> bool:
    if cozumle and sonek in BUILD_DONUSUMLU:
        return properties_cozumle(a) == properties_cozumle(b)
    is_text = sonek in TEXT_SUFFIXES
    return normalize(a, is_text) == normalize(b, is_text)


def _kisalt(adlar: list, n: int = 4) -> str:
    return ", ".join(adlar[:n]) + (f" (+{len(adlar) - n})" if len(adlar) > n else "")


def _prop_fark(a: bytes, b: bytes) -> str:
    da, db = dict(properties_cozumle(a)), dict(properties_cozumle(b))
    anahtarlar = sorted(k for k in da.keys() | db.keys() if da.get(k) != db.get(k))
    return " — anahtar/değer kümesi aynı, SIRA ya da tekrar farkı" if not anahtarlar else f" — anahtar: {_kisalt(anahtarlar)}"


def _dosyalar(kok: Path) -> dict:
    return {p.relative_to(kok).as_posix(): p for p in kok.rglob("*") if p.is_file()} if kok.is_dir() else {}


def check_app(app_dir: Path, subdir: str, kimlik, ignore_cert: bool) -> tuple[str, str]:
    """→ (durum, not). durum: OK · FARK · OLCULEMEDI · ATLANDI."""
    ayar = B.deploy_ayari(app_dir)
    if not ayar or not ayar.get("gorev") or not ayar.get("url") or not ayar.get("name"):
        return "OLCULEMEDI", "ui5-deploy.yaml yok / deploy-to-abap target.url ya da app.name okunamadı"
    src, dist = app_dir / "webapp" / subdir, app_dir / "dist" / subdir
    if not src.is_dir() and not dist.is_dir():
        return "ATLANDI", f"webapp/{subdir} ve dist/{subdir} yok — kıyaslanacak statik dosya yok"
    webapp_d, dist_d = _dosyalar(src), _dosyalar(dist)
    adlar = sorted(webapp_d.keys() | dist_d.keys())
    same, diff, kaynak_farki, missing, dist_stale = [], [], [], [], []
    taban_webapp, yalniz_dist, donusum = [], [], []
    for rel in adlar:
        w, d = webapp_d.get(rel), dist_d.get(rel)
        sonek = Path(rel).suffix.lower()
        try:
            live = B.http_get(B.bsp_url(ayar, f"{subdir}/{rel}"), kimlik, ignore_cert)
        except urllib.error.HTTPError as e:
            missing.append(f"{rel} (HTTP {e.code})")
            continue
        except Exception as e:  # noqa: BLE001 — ağ/TLS: ölçüm yok, "aynı" SAYILMAZ
            missing.append(f"{rel} ({type(e).__name__})")
            continue
        wb = w.read_bytes() if w is not None else None
        db = None
        if d is not None:
            db = d.read_bytes()
            if not icerik_esit(live, db, sonek, cozumle=False):
                diff.append(f"{rel} (canlı={len(live)}B dist={len(db)}B)")
                if wb is not None and not icerik_esit(db, wb, sonek, cozumle=True):
                    dist_stale.append(rel)
                continue
        else:
            taban_webapp.append(rel)
            if not icerik_esit(live, wb, sonek, cozumle=True):
                diff.append(f"{rel} (canlı={len(live)}B webapp={len(wb)}B — dist'te yok, taban webapp)")
                continue
        if wb is None:
            yalniz_dist.append(rel)
            same.append(rel)
            continue
        if not icerik_esit(live, wb, sonek, cozumle=True):
            kaynak_farki.append(rel + (_prop_fark(live, wb) if sonek in BUILD_DONUSUMLU else ""))
            continue
        if db is not None and sonek in BUILD_DONUSUMLU and db != wb:
            donusum.append(rel)
        same.append(rel)

    for rel in diff:
        print(f"      [FARKLI] {rel}")
    for rel in kaynak_farki:
        print(f"      [KAYNAK FARKI] {rel}  (canlı == dist ama webapp'te build edilmemiş değişiklik → build + onaylı deploy)")
    for rel in missing:
        print(f"      [CANLIDA YOK/OKUNAMADI] {rel}")
    for rel in dist_stale:
        print(f"      [UYARI] webapp ≠ dist: {rel}  (deploy dist'i gönderir → önce build)")
    if taban_webapp:
        print(f"      [BİLGİ] dist/{subdir}'de yok → taban webapp ({len(taban_webapp)}): {_kisalt(taban_webapp)}")
    if yalniz_dist:
        print(f"      [BİLGİ] yalnız dist'te, kaynak kıyası yok ({len(yalniz_dist)}): {_kisalt(yalniz_dist)}")
    if donusum:
        print(f"      [BİLGİ] beklenen build dönüşümü ({len(donusum)}): \\uXXXX çözülünce EŞİT — {_kisalt(donusum)}")
    note = f"{len(same)}/{len(adlar)} dosya canlıda AYNI (BSP={ayar['name']}, taban={'dist' if dist.is_dir() else 'webapp (dist yok)'})"
    for etiket, liste in (("FARKLI", diff), ("KAYNAK-FARKI", kaynak_farki), ("YOK", missing), ("webapp≠dist", dist_stale)):
        if liste:
            note += f" · {etiket}={len(liste)}"
    if diff or kaynak_farki or missing:
        return "FARK", note
    return "OK", note


def main() -> int:
    for akis in (sys.stdout, sys.stderr):
        try:
            akis.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass
    ap = argparse.ArgumentParser(description="BSP statik dosyaları canlıda güncel mi — SALT OKUMA")
    ap.add_argument("apps", nargs="+", help="uygulama klasör(ler)i (ui5-deploy.yaml'ın bulunduğu)")
    ap.add_argument("--subdir", default="help", help="webapp/dist altında kıyaslanacak klasör (varsayılan: help)")
    ap.add_argument("--ignore-cert", action="store_true", help="TLS sertifika doğrulamasını kapat (self-signed)")
    a = ap.parse_args()
    appler = [Path(x) for x in a.apps]
    eksik = [str(x) for x in appler if not x.is_dir()]
    if eksik:
        print(f"[FAIL] uygulama klasörü yok: {', '.join(eksik)} — ÖLÇÜM YOK (exit 2)")
        return 2
    kimlik = B.env_kimlik()
    if not kimlik:
        print(f"[FAIL] env {B.ENV_KULLANICI}/{B.ENV_PAROLA} set değil — canlı okunamaz, ÖLÇÜM YOK (exit 2).")
        return 2
    print(f"=== STATİK DOSYA DOĞRULAMA [{a.subdir}: canlı↔dist · canlı↔webapp] ===")
    sayac = {"OK": 0, "FARK": 0, "OLCULEMEDI": 0, "ATLANDI": 0}
    for app in appler:
        print(f"\n--- {app.name} ---")
        durum, notu = check_app(app, a.subdir, kimlik, a.ignore_cert)
        sayac[durum] += 1
        print(f"  [{durum}] {notu}")
    print(f"\nKAPSAM: {len(appler)} uygulama, alt klasör '{a.subdir}'. BAKILMAYANLAR:")
    for m in BAKILMAYANLAR:
        print(f"  - {m}")
    print(f"\nSONUÇ: OK={sayac['OK']} FARK={sayac['FARK']} ÖLÇÜLEMEDİ={sayac['OLCULEMEDI']} ATLANDI={sayac['ATLANDI']}")
    if sayac["FARK"]:
        print("  FARKLI (canlı ≠ dist) → build + kullanıcı onaylı deploy → tekrar koş. "
              "KAYNAK FARKI (canlı == dist ≠ webapp) → dist bayat: build + onaylı deploy.")
        return 1
    if sayac["OLCULEMEDI"] or sayac["OK"] == 0:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
