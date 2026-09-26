#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""deploy_ui.py — freestyle UI5 uygulamasını ABAP UI5 repository'ye (BSP) yayına HAZIRLAR, canlıyı DOĞRULAR,
yalnız AÇIK KULLANICI ONAYIYLA deploy eder.

⛔ AKIŞ KURALI (atlanamaz):
   build → statik kontroller → LOKAL çalıştırma kullanıcıya gösterildi → kullanıcı sohbette açıkça "OK" dedi
   → ANCAK O ZAMAN `deploy`. Model `prepare` ve `verify`'ı kendi başına koşabilir; `deploy`'u KENDİLİĞİNDEN
   koşmaz. `--user-ok` kullanıcının sohbetteki onay cümlesidir (kayıt içindir; kriptografik bir kilit DEĞİLDİR).

⛔ SAP YAZMA KAPISI (Z106, 2026-09-24): `deploy` SAP'ye (BSP) YAZAR ⇒ build'den ve ağdan ÖNCE `sap_adt_cli.py`
   yazmalarıyla AYNI kapıdan geçer: `sap-adt-foundation/scripts/sapadt/gate.py::check_write` (araç adı
   `deploy_ui`) — `config/sap-write.local` anahtarı + `--sap-write` + `.conn_adt` tier DEV + sap-project.json +
   kapsam beyanı (`--scope S0|S1 --reason` / `S2 --intake`) + bağlantı dili; ardından `gate.check_target_system`:
   `ui5-deploy.yaml` target.url/client ≠ `.conn_adt` ADT_SAP_URL/ADT_SAP_CLIENT → red (tier başka sistemi
   doğrulamış olurdu); ardından `$TMP` dışı pakette `app.transport` ZORUNLU (foundation'ın kanonik
   `guardrails.require_transport`'u, kod `ADR_0005_C`; `$TMP` TAM eşleşme, yer tutucu transport yok sayılır;
   `app.package` boş/yalnız boşluk/yer tutucu da kapıda `ADR_0005_C`).
   Kapı yüklenemezse de red (fail-closed). Her deneme proje `.axet-code/sap-write-log.jsonl`'a
   yazılır. `--user-ok` kalır; kapı ona EKTİR. İzin katmanındaki `*deploy_ui*` `ask` kuralı artık ikincil katmandır
   (oturum izni verilince sormadan geçer — Z106 ölçümü). `prepare` (ağsız) ve `verify` (salt GET) kapıdan GEÇMEZ.

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
  deploy <app_dir> --user-ok "<kullanıcının onay cümlesi>" --sap-write --scope S0|S1|S2
         [--reason "<tek satır>"] [--intake <.axet-code/intake/..md>] [--project-dir <proje>] [--ignore-cert]
      onay + env kimliği kontrolü → SAP YAZMA KAPISI → prepare (build ZORUNLU)
      → `npx --no-install fiori deploy --config ui5-deploy.yaml --yes` → canlı doğrulama (KATI: kaçış farkı da STALE).
      Z144: uygulamada `.canli/` anlık görüntüsü varsa (kaynak `fetch_ui_source.py indir` ile SAP'den alındıysa)
      build'den ÖNCE DRIFT ölçülür — canlı, anlık görüntüden sonra değiştiyse (başkası deploy etti) DURUR (exit 1),
      ölçülemezse DURUR (exit 2). Deploy SONRASI preload'a ek olarak canlının TÜM dosya listesi dist ile kıyaslanır
      (fark → exit 1); eşitse `.canli/` yeni canlıyla güncellenir.
  verify ... --tam
      Preload'a ek olarak canlının tüm dosya listesini dist ile kıyaslar (OData repo servisi; yedek ADT filestore).

Kimlik: env FIORI_TOOLS_USER / FIORI_TOOLS_PASSWORD (geliştirici set eder; script basmaz). Hedef: ui5-deploy.yaml.
Proje kökü (sap-project.json + .conn_adt): --project-dir, yoksa cwd (sap_adt_cli ile aynı).
Çıkış: 0 hazır / doğrulandı · 1 ihlal / STALE / build-deploy hatası · 2 ölçüm yok (yol yok, env kimlik yok, canlı okunamadı)
       · 3 REDDEDİLDİ (deploy için --user-ok ya da env kimlik eksik, ya da SAP yazma kapısı reddi)
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
import _bspkaynak as K  # noqa: E402

DEPLOY_KOMUTU = "npx --no-install fiori deploy --config ui5-deploy.yaml --yes"
BUILD_KOMUTU = "npm run build"
# SAP yazma kapısı: AYNI AXET_HOME'daki sap-adt-foundation (gate AXET_HOME'u kendi konumundan türetir).
FOUNDATION_SCRIPTS = Path(__file__).resolve().parents[2] / "sap-adt-foundation" / "scripts"
KAPI_ARACI = "deploy_ui"  # kapı + write-log'daki araç adı (READ_TOOLS dışı ⇒ yazma sınıfı)
# Yalnız `prepare` UYARISI için (ağsız, foundation'a bağımlı değil). Kapıdaki kural foundation'ın kendisidir;
# eşitlik test_deploy_ui'de `guardrails.YEREL_PAKET` ile zorlanır.
YEREL_PAKET = "$TMP"
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
    "preload DIŞI statik dosyalar (webapp/help/**, görseller, i18n dosyaları) — `verify --tam` ya da verify_ui_static_assets.py",
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
        if not v.strip():  # yalnız boşluk (`package: " "`) da boştur
            h.append(f"ui5-deploy.yaml alanı boş: {alan}")
        elif "<" in v or ">" in v:
            h.append(f"ui5-deploy.yaml alanı yer tutucu içeriyor: {alan}")
    if ayar["url"] and not re.match(r"^https?://", ayar["url"], re.I):
        h.append("target.url http:// ya da https:// ile başlamıyor")
    tr = ayar.get("transport", "")
    paket = ayar.get("package", "")
    if "<" in tr or ">" in tr:
        h.append("app.transport yer tutucu içeriyor — transport numarasını KULLANICI verir")
    elif not tr.strip() and paket != YEREL_PAKET:
        # `deploy` kapısıyla AYNI kanonik kural (`guardrails.require_transport`): istisna yalnız TAM `$TMP`.
        ek = (f" (paket '{paket}' TAM `{YEREL_PAKET}` değil — istisna yalnız büyük harfli `{YEREL_PAKET}`)"
              if paket.strip().upper() == YEREL_PAKET else "")
        u.append(f"app.transport boş ve paket `{YEREL_PAKET}` değil{ek} — `deploy` bunu REDDEDER (ADR_0005_C). "
                 "Transport numarasını KULLANICI verir (ui5-deploy.yaml `app.transport`), model yaratmaz")
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
            print(f"    python \"{Path(__file__).resolve()}\" deploy \"{app}\" --user-ok \"<kullanıcının onay cümlesi>\" "
                  "--sap-write --scope <S0|S1|S2> --reason \"<tek satır gerekçe>\" --project-dir \"<proje kökü>\"")
            print("  ÖN KOŞUL: kullanıcı LOKAL çalışan uygulamayı gördü ve sohbette açıkça onay verdi; "
                  f"{B.ENV_KULLANICI}/{B.ENV_PAROLA} geliştiricinin kabuğunda set; SAP yazma kapısı "
                  "(config/sap-write.local + .conn_adt tier DEV + ui5-deploy.yaml hedefi == .conn_adt) açık.")
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
        if getattr(a, "tam", False) and durum in ("OK", "OK~"):
            tdurum, tnot, _ = K.tam_liste_olc(app, ayar, kimlik, a.ignore_cert, preload_karsilastir)
            notu += f" · {tnot}"
            if tdurum != "OK":
                durum = tdurum
        sayac[durum] += 1
        etiket = {"OK": "[OK]  ", "OK~": "[OK~] ", "STALE": "[STALE]", "OLCULEMEDI": "[ÖLÇÜLEMEDİ]"}[durum]
        print(f"  {etiket} {app.name} — {notu}")
    tam = getattr(a, "tam", False)
    print(f"\nKAPSAM: {'Component-preload.js + canlının tüm dosya listesi' if tam else 'yalnız Component-preload.js'} "
          "kıyaslandı. BAKILMAYANLAR:")
    for m in BAKILMAYANLAR_VERIFY[1 if tam else 0:]:
        print(f"  - {m}")
    print(f"\nSONUÇ: OK={sayac['OK']} OK~={sayac['OK~']} STALE={sayac['STALE']} ÖLÇÜLEMEDİ={sayac['OLCULEMEDI']}")
    if sayac["STALE"]:
        return 1
    return 2 if sayac["OLCULEMEDI"] else 0


def _kapi_modulleri():
    """(gate modülü, KAPI_HATIRLATMA) — sap_adt_cli ile AYNI kapı ve aynı red hatırlatması.
    Yüklenemezse istisna yükselir; çağıran bunu RED sayar (fail-closed)."""
    if str(FOUNDATION_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(FOUNDATION_SCRIPTS))
    from sapadt import gate
    from sap_adt_cli import KAPI_HATIRLATMA
    return gate, KAPI_HATIRLATMA


def transport_denetimi(ayar: dict, require_transport, ihlal_sinifi) -> tuple[str, str] | None:
    """Kesin Yasak C — `$TMP` dışı pakette transport ZORUNLU. Kuralın kendisi foundation'ın KANONİK
    `guardrails.require_transport`'udur (sap_adt_cli yazmalarıyla aynı: `$TMP` TAM eşleşme; `$tmp`, `$TMP2`,
    `" $TMP"` istisna DEĞİL — fail-closed). Burada yalnız iki uyarlama var:
      · paket alanı boş / yalnız boşluk / yer tutucu (`<SAP_PAKET>`) → KAPIDA red (`ADR_0005_C`), build'den önce.
        Eskiden bu durumda denetim atlanıp `hazirla`'ya bırakılıyordu: `package: " "` orada da boş sayılmadığı
        için build + deploy KOŞUYORDU (bug gate ölçümü, rc=0). "Kapı reddinde build yok" değişmezi için
        tamamen boş paket de artık kapıda reddedilir (yalnız `hazirla`'nın `prepare_failed`'ı build'den SONRA gelir);
      · yer tutucu transport (`<TRANSPORT_NO>` gibi `<`/`>` içeren) YOK sayılır — require_transport yalnız
        boşluğa bakar, şablondan kalan yer tutucuyu geçirirdi.
    Döner: None (geçti) ya da (red kodu, mesaj). Transport/paket YARATILMAZ, yalnız varlığı istenir."""
    paket = ayar.get("package") or ""
    if not paket.strip() or "<" in paket or ">" in paket:
        durum = f"yer tutucu kalmış ({paket})" if paket.strip() else "boş"
        return ("ADR_0005_C", f"ui5-deploy.yaml `app.package` {durum} — hangi pakete yazılacağı belli değil. Paketi "
                              "KULLANICI verir (mevcut bir paket ya da yerel `$TMP`); ui5-deploy.yaml'daki deploy-to-abap "
                              "görevinin `app.package` alanına yazılır. Model paket yaratmaz (Kesin Yasak C).")
    tr = ayar.get("transport") or ""
    yer_tutucu = "<" in tr or ">" in tr
    try:
        require_transport(None if yer_tutucu else tr, what="deploy_ui (BSP deploy)", package=paket)
    except ihlal_sinifi as gv:
        durum = f"yer tutucu kalmış ({tr})" if yer_tutucu else "boş"
        kanonik, onek = str(gv), f"[{gv.code}] "  # kod başlıkta zaten basılıyor — tekrar etme
        kanonik = kanonik[len(onek):] if kanonik.startswith(onek) else kanonik
        return (gv.code, f"{kanonik}. Paket '{paket}' yerel ($TMP) değil ⇒ transport numarası zorunlu, ama "
                         f"ui5-deploy.yaml `app.transport` {durum}. Transport numarasını KULLANICI verir; "
                         "ui5-deploy.yaml'daki deploy-to-abap görevinin `app.transport` alanına yazılır "
                         "(deploy_ui'nin transport argümanı yok). Model transport yaratmaz (Kesin Yasak C).")
    return None


def sap_yazma_kapisi(a, app: Path):
    """SAP'ye yazmadan (build + deploy) ÖNCE kapı. Döner: int (red çıkış kodu 3) ya da `logla(sonuc, cikis)`.

    Sıra: `gate.check_write` (sap_adt_cli `on_kontrol` ile aynı çağrı, log=False) → `gate.check_target_system`
    (ui5-deploy.yaml hedefi == .conn_adt) → `transport_denetimi` (kanonik `require_transport`; `$TMP` dışı pakette
    transport zorunlu). Red de izin sonrası sonuç da proje write-log'una yazılır."""
    proj = Path(a.project_dir).resolve() if getattr(a, "project_dir", None) else Path.cwd().resolve()
    try:
        gate, hatirlatma = _kapi_modulleri()
        from sapadt.project import PROJECT_ENV
        from sapadt.guardrails import GuardrailViolation, require_transport
    except Exception as exc:  # noqa: BLE001 — kapı koşamıyorsa YAZMA YOK
        print(f"[REDDEDİLDİ] SAP yazma kapısı (gate_unavailable): kapı yüklenemedi ({type(exc).__name__}: {exc}) "
              f"— {FOUNDATION_SCRIPTS} beklenen yerde değil ya da bozuk. Fail-closed: deploy KOŞULMADI. (exit 3)")
        return 3
    os.environ[PROJECT_ENV] = str(proj)  # .conn_adt çözümü buna bakar (sap_adt_cli ile aynı)
    ayar = B.deploy_ayari(app) or {}
    bsp = ayar.get("name") or ""          # boş ad → ADR_0005_A (fail-closed; None denetimi atlardı)
    sonuc = gate.check_write(KAPI_ARACI, proj, obje_adi=bsp, object_type="bsp", scope=a.scope,
                             reason=a.reason, intake=a.intake, sap_write_flag=bool(a.sap_write),
                             tool_args={"name": bsp}, log=False)
    red = None if sonuc.allowed else (sonuc.code, sonuc.message)
    if red is None:
        red = gate.check_target_system(proj, ayar.get("url"), ayar.get("client"))
    if red is None:
        red = transport_denetimi(ayar, require_transport, GuardrailViolation)

    def logla(sonuc_kodu: str, cikis: int) -> None:
        if not gate.log_write_attempt(proj, tool=KAPI_ARACI, obje_adi=bsp, object_type="bsp", scope=sonuc.scope,
                                      reason=sonuc.reason, intake=sonuc.intake, result_code=sonuc_kodu,
                                      exit_code=cikis):
            print("  [UYARI] SAP yazma logu yazılamadı (.axet-code/sap-write-log.jsonl)", file=sys.stderr)

    if red:
        logla(red[0], 3)
        print(f"[REDDEDİLDİ] SAP yazma kapısı ({red[0]}): {red[1]} Deploy KOŞULMADI, build yapılmadı. (exit 3)")
        print(hatirlatma, file=sys.stderr)
        return 3
    print(f"  SAP yazma kapısı: GEÇTİ (araç={KAPI_ARACI}, tier={sonuc.tier}, kapsam={sonuc.scope}, "
          f"BSP={bsp}; hedef == .conn_adt; paket={ayar.get('package') or '-'} "
          f"transport={ayar.get('transport') or '-'})")
    return logla


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
    logla = sap_yazma_kapisi(a, app)  # SAP'ye yazan HER yol buradan geçer; build dahil hiçbir şey kapıdan önce koşmaz
    if isinstance(logla, int):
        return logla
    drift, dnot, _ = K.drift_olc(app, kimlik, a.ignore_cert)
    print(f"  deploy öncesi drift: [{drift}] {dnot}")
    if drift == "DEGISTI":
        print("\n[FAIL] canlı, kaynağın indirildiği andan sonra değişmiş — deploy o değişikliği EZERDİ. Deploy "
              "KOŞULMADI, build yapılmadı. Kullanıcıya göster; yeniden indir (`fetch_ui_source.py indir` yeni "
              "klasöre) → değişikliği yeniden uygula. (exit 1)")
        logla("drift", 1)
        return 1
    if drift == "OLCULEMEDI":
        print("\n[FAIL] anlık görüntü var ama canlı ile kıyaslanamadı — araya giren deploy olmadığı KANITLANMADI. "
              "Deploy KOŞULMADI. (exit 2)")
        logla("drift_unmeasured", 2)
        return 2
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
        logla("prepare_failed", 1)
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
        logla("deploy_failed", 1)
        return 1
    durum, notu = canli_dogrula(app, ayar, kimlik, a.ignore_cert, kati=True)
    print(f"  canlı doğrulama: [{durum}] {notu}")
    if durum == "OK":
        tdurum, tnot, canli = K.tam_liste_olc(app, ayar, kimlik, a.ignore_cert, preload_karsilastir)
        print(f"  tam liste doğrulama: [{tdurum}] {tnot}")
        if tdurum == "STALE":
            print("\n[FAIL] canlı preload == dist ama canlının dosya listesi dist'ten FARKLI — başarı BEYAN EDİLMEZ "
                  "(exit 1). Fark 'yalnız-2' ise canlıda dist'te olmayan dosya kalmış (ör. dışlanan klasör).")
            logla("verify_stale_files", 1)
            return 1
        anlik = K.anlik_oku(app)
        if tdurum == "OK" and anlik is not None:
            # Deploy + doğrulama BİTTİ; anlık görüntü yazımı düşerse deploy başarısı geri alınmaz. Çıkış kodu:
            #  · eski görüntü BAYT BAYT yerinde (ölçüldü) → exit 0 + açık UYARI: sonraki drift eskiye göre ölçer ve
            #    DEGISTI der → sonraki deploy DURUR (güvenli yön); sıfırdan farklı kod "deploy başarısız" okunup
            #    doğrulanmış deploy'un gereksiz tekrarına yol açardı.
            #  · eski görüntü KORUNAMADI / temizlenemeyen geçici yol → exit 2: `.canli/` bozuk ya da eksikse sonraki
            #    deploy'un drift kapısı sessizce devre dışı kalabilir — operatör müdahalesi şart (deploy yine
            #    doğrulandı, TEKRAR EDİLMEZ).
            kok = app / K.ANLIK_KLASOR
            onceki = K.anlik_ham(kok)
            try:
                K.anlik_yaz(app, canli, {**anlik[1], "guncellendi": "deploy sonrası"})
                print(f"  {K.ANLIK_KLASOR}/ anlık görüntüsü deploy edilen canlıyla güncellendi (sonraki drift buna karşı).")
            except (K.GuvensizYolHatasi, OSError) as exc:
                kalan = [str(p) for p in (kok / "dist.yeni", kok / (K.ANLIK_BILGI + ".yeni")) if p.exists()]
                korundu = onceki is not None and K.anlik_ham(kok) == onceki
                if korundu and not kalan:
                    print(f"  [UYARI] {K.ANLIK_KLASOR}/ anlık görüntüsü GÜNCELLENEMEDİ ({type(exc).__name__}: {exc}) — "
                          "eski görüntü bayt bayt yerinde (ölçüldü); sonraki drift ESKİYE göre ölçer ve DEGISTI der "
                          f"(sonraki deploy durur). Gidermek için: `fetch_ui_source.py indir` ile yeni klasöre anlık "
                          "görüntü al.")
                    print("\n[OK] deploy doğrulandı: canlı Component-preload == yüklenen dist ve canlının tüm dosya "
                          f"listesi == dist. ({K.ANLIK_KLASOR}/ güncellenemedi — yukarıdaki UYARI.)")
                    logla("ok_snapshot_not_updated", 0)
                    return 0
                print(f"\n[FAIL] deploy DOĞRULANDI (preload + tam liste == dist; TEKRAR DEPLOY ETME) ama "
                      f"{K.ANLIK_KLASOR}/ anlık görüntüsü güncellenemedi ({type(exc).__name__}: {exc}) ve "
                      + ("eski görüntü KORUNAMADI (bayt bayt farklı ya da okunamıyor)" if not korundu else
                         f"geçici yollar kaldı: {kalan}")
                      + f" — sonraki deploy'un drift kapısı buna güvenemez: {K.ANLIK_KLASOR}/'yi silip "
                        "`fetch_ui_source.py indir` ile yeniden al. (exit 2)")
                logla("ok_snapshot_broken", 2)
                return 2
        if tdurum == "OLCULEMEDI":
            print("  [UYARI] tam liste ÖLÇÜLEMEDİ — yalnız preload kanıtlandı; preload dışı dosyalar için "
                  "`verify --tam` ya da verify_ui_static_assets.py."
                  + (f" {K.ANLIK_KLASOR}/ güncellenmedi ⇒ sonraki deploy'un drift ölçümü DEGISTI diyebilir; önce "
                     "`fetch_ui_source.py drift` ile bak." if anlik is not None else ""))
        print("\n[OK] deploy doğrulandı: canlı Component-preload == yüklenen dist"
              + (" ve canlının tüm dosya listesi == dist." if tdurum == "OK" else "."))
        logla("ok", 0)
        return 0
    if durum == "OLCULEMEDI":
        print("\n[FAIL] 'Deployment Successful' dendi ama canlı OKUNAMADI — başarı BEYAN EDİLMEZ (exit 2).")
        logla("verify_unmeasured", 2)
        return 2
    print("\n[FAIL] 'Deployment Successful' dendi ama canlı ≠ dist (STALE/CACHE) — başarı BEYAN EDİLMEZ (exit 1).")
    logla("verify_stale", 1)
    return 1


def main() -> int:
    for akis in (sys.stdout, sys.stderr):
        try:
            akis.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass
    ap = argparse.ArgumentParser(description="UI5 BSP deploy: hazırla / canlı doğrula / onaylı deploy (SAP yazma kapılı)")
    alt = ap.add_subparsers(dest="komut", required=True)
    p1 = alt.add_parser("prepare", help="ağsız hazırlık + build + deploy komutunu bas (koşmaz)")
    p1.add_argument("apps", nargs="+", help="uygulama klasör(ler)i (ui5-deploy.yaml'ın bulunduğu)")
    p1.add_argument("--no-build", action="store_true", help="build etme; mevcut dist'in tazeliğini kontrol et")
    p2 = alt.add_parser("verify", help="salt-okuma: canlı preload == yerel dist mi")
    p2.add_argument("apps", nargs="+")
    p2.add_argument("--ignore-cert", action="store_true", help="TLS sertifika doğrulamasını kapat (self-signed)")
    p2.add_argument("--tam", action="store_true", help="preload'a ek olarak canlının tüm dosya listesini kıyasla")
    p3 = alt.add_parser("deploy", help="YALNIZ kullanıcı onayıyla: build + deploy + canlı doğrulama")
    p3.add_argument("app")
    p3.add_argument("--user-ok", help="kullanıcının sohbetteki açık onay cümlesi (zorunlu)")
    p3.add_argument("--ignore-cert", action="store_true")
    # SAP yazma kapısı argümanları — sap_adt_cli.py ile AYNI adlar ve anlam (gate.check_write'a aynen gider).
    p3.add_argument("--sap-write", action="store_true", help="yazma sınıfı çağrı onayı (SAP'ye BSP yazar)")
    p3.add_argument("--scope", help="S0|S1|S2")
    p3.add_argument("--reason", help="tek satır gerekçe (S0/S1)")
    p3.add_argument("--intake", help="proje-göreli intake .md (S2)")
    p3.add_argument("--project-dir", help="proje kökü: sap-project.json + .conn_adt (varsayılan: cwd)")
    a = ap.parse_args()
    return {"prepare": komut_prepare, "verify": komut_verify, "deploy": komut_deploy}[a.komut](a)


if __name__ == "__main__":
    raise SystemExit(main())
