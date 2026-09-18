#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_ui_smoke.py — lokal çalışan freestyle UI5 uygulamasına headless Playwright RENDER SMOKE testi.

Yakaladıkları: render çökmesi (geçersiz agregasyon), routing hedef çökmesi, `undefined` hataları,
`$metadata` 401 (lokal proxy'de kimlik kopuk), boş sayfa.
Yakalamadıkları: iş akışı (kaydet/sil/filtre), veri doğruluğu, yerleşim — uygulamaya özel spec yazılır
ya da tarayıcıda model API'siyle ölçülür (references/runtime-verification.md).

AKIŞ:
  1) Playwright yerel kurulu mu? (bu klasörde node_modules/@playwright/test). Değilse DUR (exit 2) —
     script KURULUM YAPMAZ; tek seferlik kurulum geliştiricinin kararıdır:
       cd <bu klasör> && npm install && npx playwright install chromium
  2) Kimlik: env FIORI_TOOLS_USER / FIORI_TOOLS_PASSWORD (lokal fiori-tools-proxy Basic auth'u SAP'ye iletir).
     `--no-auth`: kimliksiz koşum (mock/yerel veri ile çalışan uygulama).
  3) HESAP KİLİDİ GÜVENLİ ön kontrol: TEK istek `<base>/sap/opu/odata/sap/`. 401 → DUR, Playwright
     KOŞTURULMAZ (yanlış kimlikle tekrar denemek SAP hesabını kilitler). Ulaşılamıyor → DUR.
  4) `npx --no-install playwright test --config playwright.config.ts` (retries 0).

Kullanım:
  python run_ui_smoke.py --port 8080
  python run_ui_smoke.py --base-url http://localhost:8080 [--spec benim.spec.ts] [--no-auth]
Çıkış: Playwright'ın kodu (0 geçti) · 2 ön koşul yok (playwright kurulu değil, env kimlik yok, sunucu yok)
       · 3 DUR: kimlik 401 ile reddedildi
"""
from __future__ import annotations

import argparse
import base64
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENV_KULLANICI = "FIORI_TOOLS_USER"
ENV_PAROLA = "FIORI_TOOLS_PASSWORD"


def playwright_kurulu(kok: Path = HERE) -> bool:
    return (kok / "node_modules" / "@playwright" / "test" / "package.json").is_file()


def env_kimlik():
    u = (os.environ.get(ENV_KULLANICI) or "").replace("\r", "").strip()
    p = (os.environ.get(ENV_PAROLA) or "").rstrip("\r\n")
    return (u, p) if u and p else None


def auth_on_kontrol(base_url: str, kimlik, zaman: int = 20):
    """TEK istek → HTTP durum kodu; ağ hatasında None. Lokal proxy http'dir; https ise sistem TLS doğrulaması."""
    url = base_url.rstrip("/") + "/sap/opu/odata/sap/"
    req = urllib.request.Request(url)
    if kimlik:
        req.add_header("Authorization", "Basic " + base64.b64encode(f"{kimlik[0]}:{kimlik[1]}".encode()).decode())
    try:
        with urllib.request.urlopen(req, timeout=zaman) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:  # noqa: BLE001
        print(f"[uyarı] ön kontrol isteği başarısız ({type(e).__name__})")
        return None


def main() -> int:
    for akis in (sys.stdout, sys.stderr):
        try:
            akis.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass
    ap = argparse.ArgumentParser(description="UI5 lokal render smoke (Playwright, headless)")
    ap.add_argument("--port", type=int, help="lokal uygulama portu")
    ap.add_argument("--base-url", help="tam base url (ör. http://localhost:8080)")
    ap.add_argument("--spec", help="varsayılan jenerik smoke yerine koşulacak spec dosyası")
    ap.add_argument("--no-auth", action="store_true", help="kimliksiz koş (mock veri)")
    a = ap.parse_args()
    if not (a.base_url or a.port):
        print("[DUR] --port ya da --base-url ver (lokal çalışan uygulamanın adresi). (exit 2)")
        return 2
    base = a.base_url or f"http://localhost:{a.port}"

    if not playwright_kurulu():
        print(f"[DUR] Playwright bu klasörde kurulu değil: {HERE}\n"
              "  Tek seferlik kurulum (geliştirici kararı; script kurmaz):\n"
              f"    cd \"{HERE}\" && npm install && npx playwright install chromium   (exit 2)")
        return 2

    kimlik = None
    if not a.no_auth:
        kimlik = env_kimlik()
        if not kimlik:
            print(f"[DUR] env {ENV_KULLANICI}/{ENV_PAROLA} set değil. Geliştirici kendi kabuğunda set eder "
                  "ya da mock veriyle --no-auth. (exit 2)")
            return 2
        durum = auth_on_kontrol(base, kimlik)
        if durum == 401:
            print(f"[DUR] {base} kimliği 401 ile reddetti — Playwright KOŞTURULMADI (hesap kilidi önlemi: "
                  "yanlış kimlikle tekrar deneme). Kimliği düzelt. (exit 3)")
            return 3
        if durum is None:
            print(f"[DUR] {base} ulaşılamadı — uygulama lokal çalışıyor mu? (exit 2)")
            return 2
        print(f"[ok] ön kontrol: HTTP {durum} (401 değil = kimlik kabul). Playwright başlıyor…")

    env = dict(os.environ, SMOKE_BASE_URL=base)
    if kimlik:
        env["SAP_USER"], env["SAP_PASS"] = kimlik
    if a.spec:
        env["SMOKE_SPEC"] = a.spec
    cmd = ["npx", "--no-install", "playwright", "test", "--config", str(HERE / "playwright.config.ts")]
    rc = subprocess.run(cmd, cwd=str(HERE), env=env, shell=(os.name == "nt")).returncode
    print("\nKAPSAM: render smoke (console error + $metadata 200 + boş olmayan sayfa). BAKILMAYANLAR: iş akışı, "
          "veri doğruluğu, yerleşim, kalıcı kayıt — uygulamaya özel spec / model API ölçümü / kullanıcı testi.")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
