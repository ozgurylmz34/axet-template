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
     (`--channel chrome|msedge` ile kurulu tarayıcı kullanılır → `npx playwright install chromium` GEREKMEZ.)
  2) Kimlik: env FIORI_TOOLS_USER / FIORI_TOOLS_PASSWORD (lokal fiori-tools-proxy Basic auth'u SAP'ye iletir).
     `--no-auth`: kimliksiz koşum (mock/yerel veri ile çalışan uygulama).
  3) HESAP KİLİDİ GÜVENLİ ön kontrol: TEK istek `<base>/sap/opu/odata/sap/`. 401 → DUR, Playwright
     KOŞTURULMAZ (yanlış kimlikle tekrar denemek SAP hesabını kilitler). Ulaşılamıyor → DUR.
  4) `npx --no-install playwright test --config playwright.config.ts` (retries 0).

Tarayıcı seçenekleri (verilmezse davranış eskisiyle aynı: Playwright'ın indirilmiş Chromium'u):
  --channel chrome|msedge  kurulu Google Chrome / Microsoft Edge (env SMOKE_BROWSER_CHANNEL); tarayıcı indirmesi
                           gerekmez. aXet.code'da `install-browser` izin kuralıyla yasak → orada bu biçim kullanılır.
                           '--no-sandbox' bayrağı YOK: Playwright test runner onu zaten varsayılan olarak ekler
                           (playwright-core 1.63.0, `chromiumSandbox` varsayılanı; DEBUG=pw:browser ile görüldü).
                           Bu koşucunun aXet bash'inde açıldığı ÖLÇÜLMEDİ.
  --dry-run                ön koşullara bakmadan koşulacak komutu ve tarayıcı ayarını basar, çıkış 0.

Kullanım:
  python run_ui_smoke.py --port 8080
  python run_ui_smoke.py --base-url http://localhost:8080 [--spec benim.spec.ts] [--no-auth]
  python run_ui_smoke.py --port 8080 --channel chrome      # kurulu Chrome (aXet.code'da önerilen; orada ÖLÇÜLMEDİ)
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
KANALLAR = ("chrome", "msedge")


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


def smoke_env(base: str, kimlik=None, spec: str | None = None, kanal: str | None = None,
              taban: dict | None = None) -> dict:
    """Playwright alt sürecinin ortamı. playwright.config.ts SMOKE_* değişkenlerini okur."""
    env = dict(os.environ if taban is None else taban, SMOKE_BASE_URL=base)
    for k in ("SMOKE_SPEC", "SMOKE_BROWSER_CHANNEL"):
        env.pop(k, None)  # dış kabuktan sızan değer seçilmeyen ayarı sessizce açmasın
    if kimlik:
        env["SAP_USER"], env["SAP_PASS"] = kimlik
    if spec:
        env["SMOKE_SPEC"] = spec
    if kanal:
        env["SMOKE_BROWSER_CHANNEL"] = kanal
    return env


def tarayici_ozeti(kanal: str | None) -> str:
    return f"kurulu {kanal}" if kanal else "Playwright'ın indirilmiş Chromium'u"


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
    ap.add_argument("--channel", choices=KANALLAR,
                    help="kurulu Chrome/Edge kullan (tarayıcı indirmesi gerekmez); verilmezse indirilmiş Chromium")
    ap.add_argument("--dry-run", action="store_true",
                    help="ön koşullara bakmadan komutu ve tarayıcı ayarını bas, çıkış 0")
    a = ap.parse_args()
    if not (a.base_url or a.port):
        print("[DUR] --port ya da --base-url ver (lokal çalışan uygulamanın adresi). (exit 2)")
        return 2
    base = a.base_url or f"http://localhost:{a.port}"
    cmd = ["npx", "--no-install", "playwright", "test", "--config", str(HERE / "playwright.config.ts")]

    if a.dry_run:
        print(f"[kuru] adres: {base}\n[kuru] tarayıcı: {tarayici_ozeti(a.channel)}\n"
              f"[kuru] komut: {' '.join(cmd)}  (cwd {HERE})\n"
              "[kuru] ön koşullar (Playwright kurulumu, kimlik, ön kontrol isteği) BAKILMADI; hiçbir şey koşulmadı.")
        return 0

    if not playwright_kurulu():
        kurulum = "npm install" if a.channel else "npm install && npx playwright install chromium"
        print(f"[DUR] Playwright bu klasörde kurulu değil: {HERE}\n"
              "  Tek seferlik kurulum (geliştirici kararı; script kurmaz):\n"
              f"    cd \"{HERE}\" && {kurulum}   (exit 2)")
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

    env = smoke_env(base, kimlik, a.spec, a.channel)
    print(f"[ok] tarayıcı: {tarayici_ozeti(a.channel)}", flush=True)
    rc = subprocess.run(cmd, cwd=str(HERE), env=env, shell=(os.name == "nt")).returncode
    print("\nKAPSAM: render smoke (console error + $metadata 200 + boş olmayan sayfa). BAKILMAYANLAR: iş akışı, "
          "veri doğruluğu, yerleşim, kalıcı kayıt — uygulamaya özel spec / model API ölçümü / kullanıcı testi.")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
