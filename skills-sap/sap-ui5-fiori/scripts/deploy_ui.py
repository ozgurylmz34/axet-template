#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""deploy_ui.py — freestyle UI5 uygulamasını ABAP UI5 repository'ye (BSP) yayına HAZIRLAR, canlıyı DOĞRULAR,
yalnız AÇIK KULLANICI ONAYIYLA deploy eder.

⛔ AKIŞ KURALI (atlanamaz):
   build → statik kontroller → LOKAL çalıştırma kullanıcıya gösterildi → kullanıcı sohbette açıkça "OK" dedi
   → ANCAK O ZAMAN `deploy`. Model `prepare` ve `verify`'ı kendi başına koşabilir; `deploy`'u KENDİLİĞİNDEN
   koşmaz. `--user-ok` kullanıcının sohbetteki onay cümlesidir (kayıt içindir; kriptografik bir kilit DEĞİLDİR —
   asıl engel izin kuralı + bu akış kuralıdır).

⛔ NEDEN build GÖMÜLÜ: yalın `fiori deploy` build YAPMAZ; mevcut `dist/`'i yükler ve "Deployment Successful"
   der — dist eskiyse canlıya BAYAT içerik gider. Bu yüzden `deploy` build'i atlatmaz ve deploy SONRASI canlı
   `Component-preload.js`'i yerel dist ile hash-karşılaştırır ("Successful" mesajına güvenmez).

Alt komutlar:
  prepare <app_dir>... [--no-build]
      AĞ YOK. ui5-deploy.yaml (deploy-to-abap görevi, BSP adı Z* ve ≤15 karakter, url/client/package/transport),
      webapp+dist'te stray/gizli dosya ve BSP'nin tanımadığı uzantı, `npm run build` (ya da --no-build ile dist
      tazeliği), dist Component-preload.js sha → deploy komutunu BASAR, KOŞMAZ.
  verify <app_dir>... [--ignore-cert]
      SALT-OKUMA canlı GET: canlı Component-preload.js == yerel dist mi (bayat deploy taraması).
      Fark yalnız preload string'lerindeki kaçışlı \\r\\n ise (içerik modül modül eşit) [OK~] — STALE sayılmaz.
  deploy <app_dir> --user-ok "<kullanıcının onay cümlesi>" [--ignore-cert]
      onay + env kimliği kontrolü → prepare (build ZORUNLU) → `npx --no-install fiori deploy --config ui5-deploy.yaml --yes`
      → canlı doğrulama (KATI: kaçış farkı da STALE).

Kimlik: env FIORI_TOOLS_USER / FIORI_TOOLS_PASSWORD (geliştirici set eder; script basmaz). Hedef: ui5-deploy.yaml.
Çıkış: 0 hazır / doğrulandı · 1 ihlal / STALE / build-deploy hatası · 2 ölçüm yok (yol yok, env kimlik yok, canlı okunamadı)
       · 3 REDDEDİLDİ (deploy için --user-ok ya da env kimlik eksik)
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bspnet as B  # noqa: E402

DEPLOY_KOMUTU = "npx --no-install fiori deploy --config ui5-deploy.yaml --yes"
BUILD_KOMUTU = "npm run build"
# BSP repository'nin tanımadığı uzantı → deploy 400 "Type of file X is unknown" (ölçülmüş: .svg, .woff).
RED_UZANTI = {".svg", ".woff"}
# Aynı sınıftan olabilir, bu uzantılar için ölçüm yok → UYARI.
SUPHELI_UZANTI = {".woff2", ".ttf", ".otf", ".eot"}
SATIR_SONU = "SATIR_SONU"

BAKILMAYANLAR_PREPARE = [
    "target.url'in kurumun KANONİK host'u olup olmadığı (alias host lokal çalışır, deploy'da sorun çıkarır) — elle karşılaştır",
    "transport'un geçerliliği/açıklığı ve paketin varlığı (SAP tarafı; transport'u KULLANICI verir, model yaratmaz)",
    "uygulamanın fonksiyonel doğruluğu — statik kontroller + lokal kullanıcı testi",
    "BSP'nin tanıdığı uzantıların tam listesi (yalnız ölçülmüş .svg/.woff ERROR, benzer font uzantıları UYARI)",
]
BAKILMAYANLAR_VERIFY = [
    "preload DIŞI statik dosyalar (webapp/help/**, görseller, i18n dosyaları) — verify_ui_static_assets.py",
    "tarayıcı / FLP / ICM önbelleği (canlı GET cache-bust'lı; kullanıcı tarayıcısı ayrıca hard refresh ister)",
    "yerel dist'in webapp kaynağından güncel build olup olmadığı (dist webapp'ten eskiyse UYARI basılır; kesin kanıt değil)",
]


# ── Q281 portu: preload STRING'lerinin içindeki KAÇIŞLI satır sonu ─────────────────────────────
# `ui5 build` XML/properties/json kaynaklarını preload'a JS string olarak gömer. Çalışma ağacı CRLF ise
# satır sonu string içinde 4 baytlık `\r\n` KAÇIŞI olur → aynı içerik farklı hash verir. Kaçış yalnız
# .xml/.properties/.json string modüllerinde indirilir; JS kodu ve diğer her bayt KATI kıyaslanır.
PRELOAD_HARITASI = b"sap.ui.require.preload("
_PRELOAD_GIRDISI = re.compile(
    rb'"([^"\\\n]+/[^"\\\n]+\.([A-Za-z0-9]+))"\s*:\s*'
    rb"('(?:[^'\\\n]|\\.)*'|\"(?:[^\"\\\n]|\\.)*\")")
_KACISLI_CRLF = re.compile(rb"(?<!\\)((?:\\\\)*)\\r\\n")
KACIS_INDIRILEN_UZANTILAR = {b"xml", b"properties", b"json"}
JS_ISKELETI = "<js-kodu+harita-iskeleti>"


def preload_modulleri(b: bytes, kacis_indir: bool = True) -> dict | None:
    """Component-preload.js → {modül-adı: içerik}. Harita yoksa None (kıyas KATI kalır). Hiçbir bayt kaybolmaz."""
    b = B.satir_sonu_normalize(b)
    bas = b.rfind(PRELOAD_HARITASI)
    if bas < 0:
        return None
    moduller: dict = {}
    iskelet = [b[:bas]]
    konum = bas
    for m in _PRELOAD_GIRDISI.finditer(b, bas):
        iskelet.append(b[konum:m.start(3)])
        ad = m.group(1).decode("utf-8", "replace")
        deger = m.group(3)
        if kacis_indir and m.group(2).lower() in KACIS_INDIRILEN_UZANTILAR:
            deger = _KACISLI_CRLF.sub(rb"\1\\n", deger)
        anahtar, n = ad, 2
        while anahtar in moduller:
            anahtar, n = f"{ad}#{n}", n + 1
        moduller[anahtar] = deger
        konum = m.end(3)
    iskelet.append(b[konum:])
    moduller[JS_ISKELETI] = b"".join(iskelet)
    return moduller


def preload_karsilastir(yerel: bytes, canli: bytes) -> tuple[str, list]:
    """→ (sınıf, modüller). Sınıf: AYNI · SATIR_SONU (fark yalnız kaçışlı \\r\\n) · FARKLI."""
    if B.sha(yerel) == B.sha(canli):
        return "AYNI", []
    my, mc = preload_modulleri(yerel), preload_modulleri(canli)
    if my is None or mc is None:
        return "FARKLI", []
    farkli = sorted(k for k in my.keys() | mc.keys() if my.get(k) != mc.get(k))
    if farkli:
        return "FARKLI", farkli
    hy, hc = preload_modulleri(yerel, False), preload_modulleri(canli, False)
    return SATIR_SONU, sorted(k for k in hy.keys() | hc.keys() if hy.get(k) != hc.get(k))


def _kisalt(adlar: list, n: int = 4) -> str:
    return ", ".join(adlar[:n]) + (f" (+{len(adlar) - n})" if len(adlar) > n else "")


def run(cmd: str, cwd: Path, env: dict) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=str(cwd), env=env, shell=True, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def _haric_mi(rel: str, desenler: list[str]) -> bool:
    for d in desenler:
        dd = d.strip().lstrip("/")
        if not dd:
            continue
        if dd.endswith("/**"):
            kok = dd[:-3]
        elif dd.endswith("/"):
            kok = dd[:-1]
        else:
            if fnmatch.fnmatch(rel, dd):
                return True
            continue
        if rel == kok or rel.startswith(kok + "/"):
            return True
    return False


def stray_tara(kok: Path, desenler: list[str], etiket: str) -> tuple[list, list]:
    hatalar, uyarilar = [], []
    if not kok.is_dir():
        return hatalar, uyarilar
    for p in sorted(kok.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(kok).as_posix()
        if _haric_mi(rel, desenler):
            continue
        sonek = p.suffix.lower()
        if any(parca.startswith(".") for parca in rel.split("/")):
            hatalar.append(f"{etiket}/{rel}: gizli/stray dosya → sil ya da ui5-deploy.yaml excludes'a ekle "
                           "(deploy 400 'Type of file ... is unknown')")
        elif sonek in RED_UZANTI:
            hatalar.append(f"{etiket}/{rel}: BSP bu uzantıyı tanımaz (deploy 400) → inline SVG / base64 kullan")
        elif sonek in SUPHELI_UZANTI:
            uyarilar.append(f"{etiket}/{rel}: BSP bu uzantıyı tanımayabilir (DOĞRULANMADI) → deploy 400 riski")
    return hatalar, uyarilar


def _en_yeni(kok: Path, desenler: list[str]) -> tuple[float, str]:
    en, ad = 0.0, ""
    for p in kok.rglob("*"):
        if p.is_file():
            rel = p.relative_to(kok).as_posix()
            if not _haric_mi(rel, desenler) and p.stat().st_mtime > en:
                en, ad = p.stat().st_mtime, rel
    return en, ad


def hazirla(app: Path, build: bool, env: dict) -> tuple[list, list, dict]:
    """prepare çekirdeği → (hatalar, uyarılar, bilgi)."""
    h, u, bilgi = [], [], {}
    ayar = B.deploy_ayari(app)
    if ayar is None:
        return ["ui5-deploy.yaml yok — deploy edilebilir uygulama değil"], u, bilgi
    bilgi["ayar"] = ayar
    if not ayar["gorev"]:
        return ["ui5-deploy.yaml'da `deploy-to-abap` görevi yok"], u, bilgi
    ad = ayar["name"]
    if not ad:
        h.append("app.name (BSP adı) boş")
    else:
        if "<" in ad or ">" in ad:
            h.append(f"app.name yer tutucu içeriyor: {ad}")
        if not ad.upper().startswith("Z"):
            h.append(f"BSP adı '{ad}' Z ile başlamıyor")
        if len(ad) > 15:
            h.append(f"BSP adı '{ad}' {len(ad)} karakter (en çok 15)")
    for alan in ("url", "client", "package"):
        v = ayar.get(alan, "")
        if not v:
            h.append(f"ui5-deploy.yaml alanı boş: {alan}")
        elif "<" in v or ">" in v:
            h.append(f"ui5-deploy.yaml alanı yer tutucu içeriyor: {alan}")
    if ayar["url"] and not re.match(r"^https?://", ayar["url"], re.I):
        h.append("target.url http:// ya da https:// ile başlamıyor")
    tr = ayar.get("transport", "")
    if "<" in tr or ">" in tr:
        h.append("app.transport yer tutucu içeriyor — transport numarasını KULLANICI verir")
    elif not tr and ayar.get("package", "").upper() != "$TMP":
        u.append("app.transport boş — transport'lu pakette deploy transport isteyebilir (DOĞRULANMADI); "
                 "transport'u KULLANICI verir, model yaratmaz")
    webapp = app / "webapp"
    if not webapp.is_dir():
        h.append("webapp/ yok")
        return h, u, bilgi
    sh, su = stray_tara(webapp, ayar.get("resources_excludes", []), "webapp")
    h += sh
    u += su
    dist = app / "dist"
    preload = dist / B.PRELOAD
    if build:
        pkg = app / "package.json"
        try:
            betikler = json.loads(pkg.read_text(encoding="utf-8-sig")).get("scripts", {}) if pkg.is_file() else {}
        except ValueError:
            betikler = {}
        if "build" not in betikler:
            h.append("package.json'da `build` script'i yok — build atlanamaz")
            return h, u, bilgi
        print(f"  [{app.name}] build: {BUILD_KOMUTU} …")
        rc, out = run(BUILD_KOMUTU, app, env)
        if rc != 0:
            h.append(f"BUILD FAIL rc={rc}: {out.strip()[-400:]}")
            return h, u, bilgi
    if not preload.is_file():
        h.append(f"dist/{B.PRELOAD} yok — " + ("build çıktısı beklenmedik" if build else "önce build (--no-build verildi)"))
        return h, u, bilgi
    if not build:
        yeni, yeni_ad = _en_yeni(webapp, ayar.get("resources_excludes", []))
        if yeni > preload.stat().st_mtime:
            h.append(f"dist BAYAT: webapp/{yeni_ad} dist/{B.PRELOAD}'dan yeni → build et (deploy dist'i gönderir)")
    dh, du = stray_tara(dist, ayar.get("exclude", []), "dist")
    h += dh
    u += du
    bilgi["sha"] = B.sha(preload.read_bytes())
    return h, u, bilgi


def canli_dogrula(app: Path, ayar: dict, kimlik, ignore_cert: bool, kati: bool) -> tuple[str, str]:
    """→ (durum, not). durum: OK · OK~ · STALE · OLCULEMEDI."""
    preload = app / "dist" / B.PRELOAD
    if not preload.is_file():
        return "OLCULEMEDI", f"dist/{B.PRELOAD} yok — kıyaslanacak yerel çıktı yok (önce prepare)"
    yerel = preload.read_bytes()
    try:
        canli = B.http_get(B.bsp_url(ayar, B.PRELOAD), kimlik, ignore_cert)
    except Exception as exc:  # noqa: BLE001 — ağ/HTTP/TLS: ölçüm yok, "aynı" SAYILMAZ
        kod = getattr(exc, "code", "")
        return "OLCULEMEDI", f"canlı okunamadı ({type(exc).__name__}{' ' + str(kod) if kod else ''})"
    ys, cs = B.sha(yerel), B.sha(canli)
    if ys == cs:
        return "OK", f"CANLI == dist sha={ys[:12]} BSP={ayar['name']}"
    sinif, moduller = preload_karsilastir(yerel, canli)
    if sinif == SATIR_SONU and not kati:
        return "OK~", (f"yalnız kaçışlı \\r\\n farkı ({len(moduller)} modül: {_kisalt(moduller)}) — içerik modül modül "
                       f"EŞİT, STALE sayılmadı · dist={ys[:12]} canlı={cs[:12]}")
    if sinif == SATIR_SONU:
        ek = f" Fark yalnız kaçışlı satır sonu ({len(moduller)} modül) ama yüklenen dist canlıda DEĞİL."
    elif moduller:
        ek = f" Farklı modül ({len(moduller)}): {_kisalt(moduller)}."
    else:
        ek = " (preload haritası ayrıştırılamadı — modül kıyası yapılamadı, hash hükmü geçerli)"
    return "STALE", f"canlı ≠ dist · dist={ys[:12]} canlı={cs[:12]}.{ek}"


def _uygulamalar(yollar: list[str]) -> list[Path] | None:
    appler = [Path(y) for y in yollar]
    eksik = [str(a) for a in appler if not a.is_dir()]
    if eksik:
        print(f"[FAIL] uygulama klasörü yok: {', '.join(eksik)} — ÖLÇÜM YOK (exit 2)")
        return None
    return appler


def komut_prepare(a) -> int:
    appler = _uygulamalar(a.apps)
    if appler is None:
        return 2
    toplam_h = 0
    for app in appler:
        print(f"\n--- {app.name} (prepare{' --no-build' if a.no_build else ''}) ---")
        h, u, bilgi = hazirla(app, build=not a.no_build, env=os.environ.copy())
        for x in h:
            print(f"  [İHLAL] {x}")
        for x in u:
            print(f"  [UYARI] {x}")
        toplam_h += len(h)
        if not h:
            ayar = bilgi["ayar"]
            print(f"  [HAZIR] BSP={ayar['name']} paket={ayar['package']} transport={ayar['transport'] or '-'} "
                  f"dist sha={bilgi['sha'][:12]}")
            print("  DEPLOY KOMUTU (KOŞULMADI):")
            print(f"    python \"{Path(__file__).resolve()}\" deploy \"{app}\" --user-ok \"<kullanıcının onay cümlesi>\"")
            print("  ÖN KOŞUL: kullanıcı LOKAL çalışan uygulamayı gördü ve sohbette açıkça onay verdi; "
                  f"{B.ENV_KULLANICI}/{B.ENV_PAROLA} geliştiricinin kabuğunda set.")
    print("\nKAPSAM: prepare AĞA ÇIKMAZ. BAKILMAYANLAR:")
    for m in BAKILMAYANLAR_PREPARE:
        print(f"  - {m}")
    print(f"\nSONUÇ: {len(appler)} uygulama, {toplam_h} ihlal." + (" Deploy'a HAZIR DEĞİL." if toplam_h else ""))
    return 1 if toplam_h else 0


def komut_verify(a) -> int:
    appler = _uygulamalar(a.apps)
    if appler is None:
        return 2
    kimlik = B.env_kimlik()
    if not kimlik:
        print(f"[FAIL] env {B.ENV_KULLANICI}/{B.ENV_PAROLA} set değil — canlı okunamaz, ÖLÇÜM YOK (exit 2).")
        return 2
    sayac = {"OK": 0, "OK~": 0, "STALE": 0, "OLCULEMEDI": 0}
    for app in appler:
        ayar = B.deploy_ayari(app)
        if not ayar or not ayar.get("gorev") or not ayar.get("url") or not ayar.get("name"):
            print(f"  [ÖLÇÜLEMEDİ] {app.name}: ui5-deploy.yaml'da deploy-to-abap target.url/app.name yok")
            sayac["OLCULEMEDI"] += 1
            continue
        webapp = app / "webapp"
        preload = app / "dist" / B.PRELOAD
        if webapp.is_dir() and preload.is_file():
            yeni, yeni_ad = _en_yeni(webapp, ayar.get("resources_excludes", []))
            if yeni > preload.stat().st_mtime:
                print(f"  [UYARI] {app.name}: webapp/{yeni_ad} dist'ten yeni — kıyas BAYAT dist'e karşı yapılıyor")
        durum, notu = canli_dogrula(app, ayar, kimlik, a.ignore_cert, kati=False)
        sayac[durum] += 1
        etiket = {"OK": "[OK]  ", "OK~": "[OK~] ", "STALE": "[STALE]", "OLCULEMEDI": "[ÖLÇÜLEMEDİ]"}[durum]
        print(f"  {etiket} {app.name} — {notu}")
    print("\nKAPSAM: yalnız Component-preload.js kıyaslandı. BAKILMAYANLAR:")
    for m in BAKILMAYANLAR_VERIFY:
        print(f"  - {m}")
    print(f"\nSONUÇ: OK={sayac['OK']} OK~={sayac['OK~']} STALE={sayac['STALE']} ÖLÇÜLEMEDİ={sayac['OLCULEMEDI']}")
    if sayac["STALE"]:
        return 1
    return 2 if sayac["OLCULEMEDI"] else 0


def komut_deploy(a) -> int:
    app = Path(a.app)
    if not app.is_dir():
        print(f"[FAIL] uygulama klasörü yok: {app} (exit 2)")
        return 2
    onay = (a.user_ok or "").strip()
    if len(onay) < 2 or "<" in onay:
        print("[REDDEDİLDİ] --user-ok yok ya da yer tutucu. Deploy YALNIZ kullanıcı lokal çalışan uygulamayı "
              "gördükten ve sohbette açıkça onay verdikten sonra, o onay cümlesi --user-ok ile verilerek koşulur. "
              "Şimdi yapılacak: prepare + lokal test + kullanıcıdan OK iste. (exit 3)")
        return 3
    kimlik = B.env_kimlik()
    if not kimlik:
        print(f"[REDDEDİLDİ] env {B.ENV_KULLANICI}/{B.ENV_PAROLA} set değil. Kimliği geliştirici kendi kabuğunda "
              "set eder; model kimlik dosyası OKUMAZ, parola İSTEMEZ. (exit 3)")
        return 3
    print(f"=== DEPLOY {app.name} — kullanıcı onayı (kayıt): {onay!r} ===")
    env = os.environ.copy()
    if a.ignore_cert:
        env["NODE_TLS_REJECT_UNAUTHORIZED"] = "0"
    h, u, bilgi = hazirla(app, build=True, env=env)
    for x in u:
        print(f"  [UYARI] {x}")
    if h:
        for x in h:
            print(f"  [İHLAL] {x}")
        print("\n[FAIL] hazırlık ihlali — deploy KOŞULMADI (exit 1).")
        return 1
    ayar = bilgi["ayar"]
    print(f"  [{app.name}] deploy → BSP {ayar['name']} (paket {ayar['package']}, transport {ayar['transport'] or '-'}) …")
    rc, out = run(DEPLOY_KOMUTU, app, env)
    out = B.maskele(out, kimlik)
    print("  --- deploy çıktısı (son 25 satır) ---")
    for satir in out.strip().splitlines()[-25:]:
        print(f"  | {satir}")
    if rc != 0 or "Deployment Successful" not in out:
        print(f"\n[FAIL] deploy başarısız ya da başarı satırı yok (rc={rc}) — canlı DOĞRULANMADI (exit 1).")
        return 1
    durum, notu = canli_dogrula(app, ayar, kimlik, a.ignore_cert, kati=True)
    print(f"  canlı doğrulama: [{durum}] {notu}")
    if durum == "OK":
        print("\n[OK] deploy doğrulandı: canlı Component-preload == yüklenen dist. "
              "Preload dışı statik dosyalar için: verify_ui_static_assets.py")
        return 0
    if durum == "OLCULEMEDI":
        print("\n[FAIL] 'Deployment Successful' dendi ama canlı OKUNAMADI — başarı BEYAN EDİLMEZ (exit 2).")
        return 2
    print("\n[FAIL] 'Deployment Successful' dendi ama canlı ≠ dist (STALE/CACHE) — başarı BEYAN EDİLMEZ (exit 1).")
    return 1


def main() -> int:
    for akis in (sys.stdout, sys.stderr):
        try:
            akis.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass
    ap = argparse.ArgumentParser(description="UI5 BSP deploy: hazırla / canlı doğrula / onaylı deploy")
    alt = ap.add_subparsers(dest="komut", required=True)
    p1 = alt.add_parser("prepare", help="ağsız hazırlık + build + deploy komutunu bas (koşmaz)")
    p1.add_argument("apps", nargs="+", help="uygulama klasör(ler)i (ui5-deploy.yaml'ın bulunduğu)")
    p1.add_argument("--no-build", action="store_true", help="build etme; mevcut dist'in tazeliğini kontrol et")
    p2 = alt.add_parser("verify", help="salt-okuma: canlı preload == yerel dist mi")
    p2.add_argument("apps", nargs="+")
    p2.add_argument("--ignore-cert", action="store_true", help="TLS sertifika doğrulamasını kapat (self-signed)")
    p3 = alt.add_parser("deploy", help="YALNIZ kullanıcı onayıyla: build + deploy + canlı doğrulama")
    p3.add_argument("app")
    p3.add_argument("--user-ok", help="kullanıcının sohbetteki açık onay cümlesi (zorunlu)")
    p3.add_argument("--ignore-cert", action="store_true")
    a = ap.parse_args()
    return {"prepare": komut_prepare, "verify": komut_verify, "deploy": komut_deploy}[a.komut](a)


if __name__ == "__main__":
    raise SystemExit(main())
