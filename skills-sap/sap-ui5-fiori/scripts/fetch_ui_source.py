#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch_ui_source.py — kaynağı repoda/diskte OLMAYAN (yalnız SAP'ye deploy edilmiş) UI5 uygulamasını SAP'den
SALT-OKUMA indirir, düzenlenebilir kaynağı geri kurar ve canlıyla eşliğini ölçer (Z144). SAP'ye YAZMAZ.

Yöntem ve ölçümleri: `_bspkaynak.py` başlığı. Akış (atlanamaz sıra):
  1) indir   → `<app>/webapp` + `package.json` / `ui5.yaml` / `ui5-deploy.yaml` iskeleti + canlı anlık görüntü `.canli/`
  2) npm install (geliştirici)                   → @ui5/cli + fiori deploy aracı
  3) eslik   → kaynak DEĞİŞTİRİLMEDEN derlenir, dist canlı anlık görüntüyle TAM LİSTE kıyaslanır.
               Eşit değilse DÜZENLEME YAPILMAZ (kaynak güvenilir değil: TS, özel build, eksik dosya …) → kullanıcıya sor.
  4) düzenle → yerel test (`ui_local_proxy.py`, salt-okur) → kullanıcı OK → `deploy_ui.py deploy`
     (deploy, anlık görüntü varsa önce DRIFT ölçer: canlı indirildiğinden beri değiştiyse DURUR).

Alt komutlar:
  indir <BSP> --out <app_klasoru> [--project-dir <proje>] [--url URL --client NNN] [--ignore-cert]
      Hedef: --url/--client verilmezse proje kökündeki `.conn_adt` (ADT_SAP_URL / ADT_SAP_CLIENT). Klasörde
      `webapp/` varsa ÜZERİNE YAZMAZ (exit 1).
  eslik <app_klasoru> [--no-build]
      AĞ YOK. `npm run build` (ya da --no-build ile mevcut dist) → dist ↔ `.canli/dist` tam liste.
  drift <app_klasoru> [--ignore-cert]
      Canlıyı yeniden indirir → `.canli/dist` ile kıyaslar: canlı, anlık görüntüden sonra değişti mi?
  anlik-kur <app_klasoru> [--no-build] [--kabul] [--ignore-cert]
      Z160 — kaynağı ZATEN yerelde olan uygulama (repoda doğmuş, `indir` görmemiş) için `.canli/` kurar: yerel
      build ↔ canlı tam liste; eşitse yazar, farklıysa gösterir ve YAZMAZ (--kabul = kullanıcı canlıyı ezmeyi
      kabul etti). Canlıda BSP yoksa yazacak bir şey yok. `deploy`, `.canli/` yokken canlıda BSP varsa bunu ister.
  metadata <SERVIS> [--kaydet [<yol>]] [--alan AD ...] [--tip ENTITYTYPE] [--app <app_klasoru>] [--project-dir <proje>]
           [--url URL --client NNN] [--ignore-cert]
      OData V2 `$metadata`'yı SALT-OKUMA çeker; verilen alanların `<Property …/>` satırını basar (alan var mı,
      tipi, etiketi). `sap-adt-foundation` CLI'de `$metadata` aracı yoktu (foundation-query.md §5). Yanıtın kökü
      `Edmx` değilse (ör. giriş sayfası HTML/XHTML) ölçüm yoktur (exit 2) — "alan yok" hükmü verilmez.
      --kaydet (Z168): yanıtı BAYT BAYT dosyaya yazar (elle satır eklenmez — dosya SAP çıktısıdır). Yol verilmezse
        --app gerekir ve yol şu sırayla bulunur: ① `ui5-mock.yaml` `services[].urlPath`'i bu servis olan girdinin
        `metadataPath`'i (mock sunucunun fiilen okuduğu dosya; uygulama köküne göre) ② `webapp/manifest.json`
        `sap.app.dataSources`'ta `uri`'si bu servis olan girdinin `settings.localUri`'si (webapp'e göre) ③ o girdi
        `mainService` ise `webapp/localService/mainService/metadata.xml` ④ hiçbiri değilse YAZMAZ (exit 2; açık yol
        ver — başka servisin metadata'sı mainService dosyasını ezmesin). ① ile ② farklıysa ① yazılır + UYARI.
        Türetilen yol uygulama klasörünün dışına çıkamaz. Dosya varsa üzerine yazılır; önce/sonra boyut, EntityType
        ve Property sayısı ile eklenen/kalkan Property'ler basılır (bayt bayt aynıysa yazılmaz).
      Kimlik sırası (YALNIZ bu salt-okur komut — kullanıcı kararı 2026-10-03): ① env FIORI_TOOLS_USER/PASSWORD
        ② proje kökündeki `.conn_adt` ADT_SAP_USER/ADT_SAP_PASSWORD (sap_adt_cli ile aynı ayrıştırma: python-dotenv;
        YALNIZ hedef URL+client `.conn_adt` ADT_SAP_URL+ADT_SAP_CLIENT ile aynıysa — kimlik başka sisteme
        gönderilmez) ③ Windows giriş penceresi (Windows PowerShell 5.1 `Get-Credential`; parola süreç içi borudan
        base64 gelir — komut satırına, çıktıya, log'a, hata mesajına GİRMEZ). Kullanılan kaynak `kimlik: env|.conn_adt|
        pencere` satırıyla basılır (değer basılmaz). Windows kimlik deposunda saklama YOK.
      Sertifika (yalnız ② `.conn_adt` kolu): ADT kanalıyla aynı kural — `ADT_SAP_SSL_VERIFY` (env > `.conn_adt`)
        true/1/yes değilse doğrulama KAPALI (`sertifika doğrulaması: kapalı …` satırı basılır); açmak için
        `.conn_adt`'ye `ADT_SAP_SSL_VERIFY=true`. Yönlendirme host/şema/port değiştirirse `Authorization` düşürülür
        (kimlik başka sisteme gitmez).

Kimlik (indir/drift/anlik-kur): env FIORI_TOOLS_USER / FIORI_TOOLS_PASSWORD (script basmaz, dosyadan okumaz).
Çıkış: 0 tamam/eşit · 1 fark/ihlal · 2 ölçüm yok (kimlik yok, canlı okunamadı, anlık görüntü yok, `eslik`te
build başarısız / dist yok)
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bspkaynak as K  # noqa: E402
import _bspnet as B  # noqa: E402

FOUNDATION_SCRIPTS = Path(__file__).resolve().parents[2] / "sap-adt-foundation" / "scripts"
BUILD_KOMUTU = "npm run build"

PACKAGE_JSON = {
    "private": True,
    "version": "0.0.1",
    "scripts": {"build": "ui5 build --clean-dest --dest dist", "start": "ui5 serve"},
    "devDependencies": {"@ui5/cli": "^4.0.0", "@sap/ux-ui5-tooling": "^1.0.0"},
}
GITIGNORE = "dist/\nnode_modules/\n.canli/\n"


def _yaml_dize(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)  # JSON dizesi geçerli YAML çift tırnaklı dizedir


def ui5_yaml(uyg_id: str) -> str:
    return f'specVersion: "4.0"\nmetadata:\n  name: {uyg_id}\ntype: application\n'


def ui5_deploy_yaml(uyg_id: str, url: str, client: str, bilgi: dict) -> str:
    # `builder.resources.excludes` BİLEREK YOK: canlıdan indirilen her dosya (ör. localService/**) deploy'da da
    # gitmeli — şablondaki dışlama canlıda bu dosyaları taşıyan uygulamada dist'i canlı listeden eksik bırakır.
    return (f'specVersion: "4.0"\nmetadata:\n  name: {uyg_id}\ntype: application\n'
            "builder:\n  customTasks:\n    - name: deploy-to-abap\n      afterTask: generateCachebusterInfo\n"
            "      configuration:\n        target:\n"
            f"          url: {url}\n          client: '{client}'\n"
            f"        app:\n          name: {bilgi.get('Name', '')}\n"
            f"          description: {_yaml_dize(bilgi.get('Description', ''))}\n"
            f"          package: {bilgi.get('Package', '')}\n"
            "          transport: # transport numarasını KULLANICI verir (model yaratmaz)\n")


def _foundation_conn(proj: str | None) -> tuple[str, str] | tuple[None, str]:
    """(url, client) ya da (None, hata) — proje `.conn_adt`'sinden, sap_adt_cli ile aynı okuyucu."""
    try:
        if str(FOUNDATION_SCRIPTS) not in sys.path:
            sys.path.insert(0, str(FOUNDATION_SCRIPTS))
        from sapadt.project import conn_file_values, conn_path
    except Exception as exc:  # noqa: BLE001
        return None, f"sap-adt-foundation yüklenemedi ({type(exc).__name__}) — --url/--client ver"
    if not conn_path(proj).is_file():
        return None, f".conn_adt yok ({conn_path(proj)}) — --project-dir ya da --url/--client ver"
    urller = conn_file_values("ADT_SAP_URL", proj)
    clientlar = conn_file_values("ADT_SAP_CLIENT", proj)
    if len(urller) != 1 or len(clientlar) > 1:
        return None, f".conn_adt'de ADT_SAP_URL {len(urller)} / ADT_SAP_CLIENT {len(clientlar)} kez var (1 bekleniyor)"
    return urller[0].rstrip("/"), (clientlar[0] if clientlar else "")


def _hedef(a) -> tuple[str, str] | None:
    if getattr(a, "url", None):
        return a.url.rstrip("/"), (a.client or "")
    app = getattr(a, "app", None)
    if app:
        ayar = B.deploy_ayari(Path(app)) or {}
        if ayar.get("url"):
            return ayar["url"].rstrip("/"), ayar.get("client", "")
    url, client = _foundation_conn(getattr(a, "project_dir", None))
    if url is None:
        print(f"[FAIL] hedef sistem belirlenemedi: {client} (exit 2)")
        return None
    return url, client


def _kimlik():
    k = B.env_kimlik()
    if not k:
        print(f"[FAIL] env {B.ENV_KULLANICI}/{B.ENV_PAROLA} set değil — canlı okunamaz (exit 2). Kimliği geliştirici "
              "kendi kabuğunda set eder; model parola istemez, dosyadan okumaz.")
    return k


def komut_indir(a) -> int:
    bsp = a.bsp.strip().upper()
    app = Path(a.out)
    if (app / "webapp").exists():
        print(f"[FAIL] {app / 'webapp'} zaten var — üzerine YAZILMAZ. Yeni bir klasör ver ya da mevcut kaynakla "
              "`drift` / `eslik` kullan. (exit 1)")
        return 1
    hedef = _hedef(a)
    kimlik = _kimlik()
    if not hedef or not kimlik:
        return 2
    url, client = hedef
    try:
        dist, bilgi, yol = K.canli_indir(url, client, bsp, kimlik, a.ignore_cert)
    except Exception as exc:  # noqa: BLE001 — ölçüm yok
        print(f"[FAIL] {bsp} indirilemedi: {exc} (exit 2)")
        return 2
    webapp, atilan, uyarilar = K.kaynak_kur(dist)
    uyg_id = K.uygulama_kimligi(webapp) or bsp.lower()
    # Bu koşumun YARATTIĞI her şey kaydedilir; herhangi bir yazım adımı düşerse (webapp · iskelet · .canli) HEPSİ geri
    # alınır — yarım kalan iskelet "webapp zaten var" / "önce indir" çıkmazı üretmesin. Önceden var olan dokunulmaz.
    canli = app / K.ANLIK_KLASOR
    canli_vardi = canli.exists()
    # `.canli/` önceden varsa bu koşum onu YARATMADI ⇒ geri alma onu silmez; korunduğu BAYT BAYT ölçülür (beyan değil).
    onceki_canli = K.anlik_ham(canli) if canli_vardi else None
    yaratilan = [app / "webapp"]  # webapp başta yoktu (yukarıda denetlendi)
    olusan = ["webapp/"]
    try:
        K.klasore_yaz(app / "webapp", webapp)
        for ad, icerik in (("package.json", json.dumps({"name": bsp.lower().replace("_", "-"), **PACKAGE_JSON},
                                                       ensure_ascii=False, indent=2) + "\n"),
                           ("ui5.yaml", ui5_yaml(uyg_id)),
                           ("ui5-deploy.yaml", ui5_deploy_yaml(uyg_id, url, client,
                                                               {**bilgi, "Name": bilgi.get("Name") or bsp})),
                           (".gitignore", GITIGNORE)):
            if not (app / ad).exists():
                yaratilan.append(app / ad)
                (app / ad).write_text(icerik, encoding="utf-8", newline="\n")
                olusan.append(ad)
        if not canli_vardi:
            yaratilan.append(canli)
        K.anlik_yaz(app, dist, {"bsp": bsp, "yol": yol, "paket": bilgi.get("Package", ""),
                                "aciklama": bilgi.get("Description", "")})
    except (K.GuvensizYolHatasi, OSError) as exc:
        neden = ("güvensiz dosya adı" if isinstance(exc, K.GuvensizYolHatasi)
                 else f"yazılamadı ({type(exc).__name__})")
        kalan = K.yollari_kaldir(yaratilan)  # geri alma ÖLÇÜLÜR — başarı beyan edilmez
        korundu = None
        if canli_vardi:
            kalan += [str(p) for p in (canli / "dist.yeni", canli / (K.ANLIK_BILGI + ".yeni")) if p.exists()]
            korundu = onceki_canli is not None and K.anlik_ham(canli) == onceki_canli
        adlar = ", ".join(p.name + ("/" if p.name in ("webapp", K.ANLIK_KLASOR) else "") for p in yaratilan)
        if kalan or korundu is False:
            print(f"[FAIL] {bsp} {neden}: {exc}. Bu koşumun yazdıkları GERİ ALINAMADI"
                  + (f" — kalan {len(kalan)} yol: {kalan[:10]}{' …' if len(kalan) > 10 else ''}" if kalan else "")
                  + (f" — önceki {K.ANLIK_KLASOR}/ anlık görüntüsü KORUNAMADI (bayt bayt farklı ya da okunamıyor; "
                     f"`drift`/`eslik` ona güvenemez: {K.ANLIK_KLASOR}/'yi silip yeniden `indir`)"
                     if korundu is False else "")
                  + " — elle düzeltin, sonra yeniden koşun. (exit 2)")
        else:
            print(f"[FAIL] {bsp} {neden}: {exc}. Bu koşumun yazdıkları geri alındı ({adlar})"
                  + (f"; önceki {K.ANLIK_KLASOR}/ anlık görüntüsü bayt bayt aynı (ölçüldü)" if canli_vardi else "")
                  + "; sebebi (izin / disk / yol uzunluğu) giderip yeniden koşun. (exit 2)")
        return 2
    print(f"[OK] {bsp} indirildi ({yol}): canlı {len(dist)} dosya → kaynak {len(webapp)} dosya, "
          f"atılan build ürünü {len(atilan)}. Paket={bilgi.get('Package') or '?'}")
    print(f"  yazılan: {', '.join(olusan)} · canlı anlık görüntü: {K.ANLIK_KLASOR}/ (git'e girmez)")
    for u in uyarilar:
        print(f"  [UYARI] {u}")
    print("SIRADAKİ (atlanamaz): `npm install` → "
          f"`python \"{Path(__file__).resolve()}\" eslik \"{app}\"` — eşit değilse kaynak DÜZENLENMEZ.")
    print("KAPSAM: yalnız okundu, SAP'ye yazılmadı. ui5-deploy.yaml transport'u BOŞ (kullanıcı verir). "
          "BAKILMAYANLAR: TS kaynağı / Fiori Elements (ölçülmedi) · uygulamanın FLP kataloğu, rol, hedef eşlemesi.")
    return 0


def _eslik_kapsami(harita: str) -> str:
    """`eslik` KAPSAM satırı — her çıkışta (EŞLİK anında da) basılır: sıfır bulgu, bakılmayan yüzeyde temizlik DEĞİLDİR."""
    return ("KAPSAM: bakılan — değiştirilmemiş kaynaktan build (dist/) ↔ " + K.ANLIK_KLASOR + "/ canlı anlık görüntüsü, "
            "tüm dosyalar (preload modül modül · metin satır sonu normalize · ikili ham bayt) + kaynak haritası sondası "
            f"({harita}). BAKILMAYANLAR: anlık görüntüden SONRA canlıdaki değişiklik (`drift`) · TS / Fiori Elements "
            "özgün kaynağı (harita yoksa transpile ayrımı ölçülemez) · `.map` dışında iz bırakmayan dönüşüm · sunucu "
            "tarafı (OData servisi, FLP kataloğu, rol).")


def komut_eslik(a) -> int:
    app = Path(a.app)
    anlik = K.anlik_oku(app)
    if anlik is None:
        print(f"[FAIL] {app}/{K.ANLIK_KLASOR} yok — önce `indir` (canlı anlık görüntü olmadan eşlik ölçülemez) (exit 2)")
        print(_eslik_kapsami("ÖLÇÜLEMEDİ — anlık görüntü yok"))
        return 2
    canli, _ = anlik
    # Üçüncü şart — kaynak haritası sondası (build'den bağımsız, canlı anlık görüntü üzerinde): dosyalar eşit olsa bile
    # `-dbg` bir dönüşüm çıktısıysa geri kurulan kaynak özgün DEĞİLDİR.
    sapma, bakilan = K.harita_sondasi(canli)
    harita = f"{bakilan} harita, {len(sapma)} sapma"
    for s_ in sapma[:10]:
        print(f"  [KAYNAK HARİTASI SAPMASI] {s_}")
    if len(sapma) > 10:
        print(f"  … +{len(sapma) - 10} sapma")
    if not a.no_build:
        import deploy_ui as D
        print(f"  build: {BUILD_KOMUTU} …")
        rc, out = D.run(BUILD_KOMUTU, app, os.environ.copy())
        if rc != 0:
            # exit 2 (ölçüm yok): build düşünce dist ↔ canlı kıyası HİÇ yapılmadı — "fark bulundu" (1) değil. İkisi de
            # sıfırdan farklı ⇒ düzenleme kapısı kapalı kalır; ayrım, sebebin kaynak farkı değil build olduğunu söyler.
            print(f"[FAIL] build başarısız rc={rc}: {out.strip()[-400:]} — eşlik ÖLÇÜLMEDİ (exit 2)")
            print(_eslik_kapsami(harita + " · build ÖLÇÜLEMEDİ"))
            return 2
    dist_kok = app / "dist"
    if not dist_kok.is_dir():
        print("[FAIL] dist/ yok — build et (exit 2)")
        print(_eslik_kapsami(harita + " · dist ÖLÇÜLEMEDİ"))
        return 2
    import deploy_ui as D
    k = K.kume_karsilastir(K.klasor_oku(dist_kok), canli, D.preload_karsilastir)
    print(f"  dist ↔ canlı anlık görüntü: {K.ozet(k)}")
    if K.kume_esit_mi(k) and not sapma:
        print(f"[OK] EŞLİK: değiştirilmemiş kaynaktan build == canlı ({len(k['esit'])}/{len(k['esit'])}) ve kaynak "
              f"haritaları `-dbg` kaynağını gösteriyor ({bakilan}). Kaynak düzenlemeye hazır.")
        print(_eslik_kapsami(harita))
        return 0
    if K.kume_esit_mi(k):
        print(f"[FAIL] EŞLİK YOK — build == canlı AMA kaynak haritası sapması var ({len(sapma)}): geri kurulan `-dbg` "
              "özgün kaynak değil (TypeScript / build öncesi dönüşüm / başka araç). Düzenleme YAPILMAZ; kaynağı "
              "kullanıcıdan iste. (exit 1)")
    elif k["satir_sonu"] and not (k["farkli"] or k["yalniz_a"] or k["yalniz_b"]) and not sapma:
        print("[FAIL] fark YALNIZ preload'daki kaçışlı satır sonu — webapp metin dosyaları CRLF mi? LF'e çevir, tekrar "
              "ölç. (exit 1)")
    else:
        print("[FAIL] EŞLİK YOK — geri kurulan kaynak canlıyı üretmiyor"
              + (f" ve kaynak haritası sapması var ({len(sapma)})" if sapma else "")
              + ". Düzenleme YAPILMAZ; farkları kullanıcıya göster (TS / özel build / eksik dosya olabilir). (exit 1)")
    print(_eslik_kapsami(harita))
    return 1


def komut_drift(a) -> int:
    kapsam = ("KAPSAM: bakılan — şimdiki canlı BSP dosyaları (liste + içerik; metin satır sonu normalize, ikili ham) ↔ "
              f"{K.ANLIK_KLASOR}/ anlık görüntüsü. BAKILMAYANLAR: yerel kaynak / dist (`eslik`) · kaynak haritası "
              "sondası (`eslik`) · sunucu tarafı (OData servisi, FLP kataloğu, rol) · canlıya anlık görüntüden önce "
              "yapılmış değişiklik.")
    kimlik = _kimlik()
    if not kimlik:
        print(kapsam.replace("KAPSAM:", "KAPSAM (ÖLÇÜLEMEDİ — kimlik yok):", 1))
        return 2
    durum, notu, _ = K.drift_olc(Path(a.app), kimlik, a.ignore_cert)
    print(f"  [{durum}] {notu}")
    print(kapsam if durum in ("AYNI", "DEGISTI") else kapsam.replace("KAPSAM:", f"KAPSAM ({durum} — ölçüm yok):", 1))
    return {"AYNI": 0, "DEGISTI": 1}.get(durum, 2)


def komut_anlik_kur(a) -> int:
    """Z160: kaynağı ZATEN yerelde olan (repoda doğmuş / `indir`'siz) uygulama için canlı anlık görüntüsünü kur.
    Yerel build (dist, deploy `exclude`'ları hariç) ↔ canlı TAM LİSTE: eşitse `.canli/` yazılır (0); farklıysa
    farklar basılır, hiçbir şey yazılmaz (1) — `--kabul` = kullanıcı farkı gördü ve canlıyı ezmeyi kabul etti (0,
    anlık görüntü ŞİMDİKİ canlıdır; sonraki deploy o farkı EZER). Canlıda BSP yoksa yazılacak bir şey yok (0)."""
    import deploy_ui as D
    app = Path(a.app)
    kapsam = ("KAPSAM: bakılan — yerel build (dist/, ui5-deploy.yaml `exclude` regex'leriyle dışlananlar hariç) ↔ "
              "şimdiki canlı BSP tam dosya listesi (preload modül modül · metin satır sonu normalize · ikili ham). "
              "BAKILMAYANLAR: kaynak haritası sondası (`eslik`) · build'in üretmediği kaynak farkı · sunucu tarafı "
              "(OData servisi, FLP kataloğu, rol).")
    if K.anlik_oku(app) is not None:
        print(f"[FAIL] {app / K.ANLIK_KLASOR} zaten var — üzerine YAZILMAZ; kayma için `drift` kullan. (exit 1)")
        return 1
    if (app / K.ANLIK_KLASOR).exists():
        # Eksik/bozuk görüntü (bilgi.json ya da dist/ yok): deploy onu YOK sayar ve buraya yönlendirir — burada da
        # reddedilirse çıkmaz olur. Otomatik silinmez (içinde kurtarılacak bir şey olabilir); kullanıcıya gösterilir.
        print(f"[FAIL] {app / K.ANLIK_KLASOR} VAR ama eksik/bozuk (bilgi.json ya da dist/ yok) — okunamıyor. İçeriğini "
              "kullanıcıya göster; onaylarsa klasörü silip bu komutu yeniden koş. Hiçbir şey yazılmadı. (exit 2)")
        return 2
    ayar = B.deploy_ayari(app) or {}
    if not ayar.get("url") or not ayar.get("name"):
        print("[FAIL] ui5-deploy.yaml'da target.url/app.name yok — canlı belirlenemez (exit 2)")
        print(kapsam.replace("KAPSAM:", "KAPSAM (ÖLÇÜLEMEDİ):", 1))
        return 2
    kimlik = _kimlik()
    if not kimlik:
        print(kapsam.replace("KAPSAM:", "KAPSAM (ÖLÇÜLEMEDİ — kimlik yok):", 1))
        return 2
    var, vnot = K.bsp_canlida_mi(ayar["url"], ayar.get("client", ""), ayar["name"], kimlik, a.ignore_cert)
    print(f"  canlıda BSP {ayar['name']}: {vnot}")
    if var is False:
        print("[OK] canlıda BSP yok — ilk deploy; anlık görüntü gerekmez (deploy sonrası kurulur). Hiçbir şey yazılmadı.")
        return 0
    if var is None:
        print("[FAIL] BSP'nin canlıda olup olmadığı ölçülemedi — hiçbir şey yazılmadı (exit 2)")
        print(kapsam.replace("KAPSAM:", "KAPSAM (ÖLÇÜLEMEDİ):", 1))
        return 2
    if not a.no_build:
        print(f"  build: {BUILD_KOMUTU} …")
        rc, out = D.run(BUILD_KOMUTU, app, os.environ.copy())
        if rc != 0:
            print(f"[FAIL] build başarısız rc={rc}: {out.strip()[-400:]} — kıyas ÖLÇÜLMEDİ, hiçbir şey yazılmadı (exit 2)")
            print(kapsam.replace("KAPSAM:", "KAPSAM (ÖLÇÜLEMEDİ — build):", 1))
            return 2
    durum, notu, canli = K.tam_liste_olc(app, ayar, kimlik, a.ignore_cert, D.preload_karsilastir)
    print(f"  yerel dist ↔ canlı: [{durum}] {notu}")
    if durum == "OLCULEMEDI" or canli is None:
        print("[FAIL] kıyas ölçülemedi — hiçbir şey yazılmadı (exit 2)")
        print(kapsam.replace("KAPSAM:", "KAPSAM (ÖLÇÜLEMEDİ):", 1))
        return 2
    if durum != "OK" and not a.kabul:
        print("[FAIL] yerel build ≠ canlı. Fark ya yerelde henüz deploy edilmemiş iştir ya da canlıda YERELDE OLMAYAN "
              "bir değişikliktir (başkası deploy etmiş). Farkı kullanıcıya göster; otorite kullanıcınındır:\n"
              "  · canlı doğruysa → `indir` ile YENİ klasöre al, değişikliği oraya taşı\n"
              "  · yerel doğruysa (canlıyı bilerek ezmek) → aynı komuta --kabul\n"
              "Hiçbir şey yazılmadı. (exit 1)")
        print(kapsam)
        return 1
    try:
        K.anlik_yaz(app, canli, {"bsp": ayar["name"], "kaynak": "anlik-kur"
                                 + (" (--kabul: yerel ≠ canlı, kullanıcı kabul etti)" if durum != "OK" else "")})
        eklendi = K.gitignore_anlik_ekle(app)
    except (K.GuvensizYolHatasi, OSError) as exc:
        kalan = K.yollari_kaldir([app / K.ANLIK_KLASOR])
        print(f"[FAIL] anlık görüntü yazılamadı ({type(exc).__name__}: {exc})"
              + (f" — GERİ ALINAMADI, kalan: {kalan}" if kalan else " — yazılanlar geri alındı") + " (exit 2)")
        return 2
    print(f"[OK] {K.ANLIK_KLASOR}/ anlık görüntüsü kuruldu ({len(canli)} canlı dosya)"
          + (f"; .gitignore'a {K.ANLIK_KLASOR}/ eklendi" if eklendi else "")
          + (". ⚠ --kabul: sonraki deploy canlıdaki farkı EZER." if durum != "OK" else ". Deploy kaymayı buna karşı ölçer."))
    print(kapsam)
    return 0


# ───────────────────────── metadata: kimlik sırası (Z168 — YALNIZ bu salt-okur komut) ─────────────────────────

PENCERE_ZAMAN_ASIMI = 300  # kullanıcının pencereyi doldurma süresi (sn)

# Windows PowerShell 5.1 betiği: Get-Credential GUI penceresi (pwsh 7 konsolda sorar — o yüzden powershell.exe).
# Kullanıcı adı + parola UTF-8 → base64 olarak YALNIZ stdout borusuna yazılır (konsol kod sayfası ASCII dışı parolayı
# bozmasın); stderr'e / komut satırına sır girmez. Betik `-EncodedCommand` ile geçer (tırnak/boş değişken tuzağı yok).
# Pencere mesajı betiğe GÖMÜLMEZ, ortam değişkeniyle geçer: servis/URL argv'den ya da uygulamanın `ui5-deploy.yaml`'ından
# gelir ve PowerShell tipografik tırnakları (U+2018…U+201B) da dizge sonu sayar — gömülürse kod enjeksiyonu (bug-gate 2026-10-03).
_PS_MESAJ_ENV = "AXET_PENCERE_MESAJ"
_PS_BETIK = """$ErrorActionPreference = 'Stop'
$c = Get-Credential -Message $env:AXET_PENCERE_MESAJ
if ($null -eq $c) { exit 3 }
$n = $c.GetNetworkCredential()
$e = [System.Text.Encoding]::UTF8
[Console]::Out.Write([Convert]::ToBase64String($e.GetBytes($n.UserName)) + ' ' + [Convert]::ToBase64String($e.GetBytes($n.Password)))
"""


def _sistem_anahtari(url: str, client: str) -> tuple:
    """URL + client → karşılaştırma anahtarı (şema/host küçük harf, varsayılan port, sondaki `/` yok)."""
    u = urllib.parse.urlsplit((url or "").strip())
    sema = u.scheme.lower()
    try:
        port = u.port or {"http": 80, "https": 443}.get(sema)
    except ValueError:  # geçersiz port: traceback yerine eşleşmeyen anahtar (güvenli yön)
        port = "geçersiz:" + u.netloc
    return sema, (u.hostname or "").lower(), port, u.path.rstrip("/"), (client or "").strip()


def _conn_kimlik(proj, url: str, client: str):
    """② `.conn_adt` kimliği → ((kullanıcı, parola), None) | (None, neden). Değer BASILMAZ.
    Kimlik YALNIZ hedef sistem `.conn_adt`'nin kendi sistemiyse kullanılır: `--url` ya da `ui5-deploy.yaml` başka bir
    host gösteriyorsa `.conn_adt` parolası oraya gönderilmez."""
    try:
        if str(FOUNDATION_SCRIPTS) not in sys.path:
            sys.path.insert(0, str(FOUNDATION_SCRIPTS))
        from sapadt.project import conn_file_values, conn_path
    except Exception as exc:  # noqa: BLE001
        return None, f"sap-adt-foundation yüklenemedi ({type(exc).__name__})"
    yol = conn_path(proj)
    if not yol.is_file():
        return None, ".conn_adt yok"
    sayi = {k: len(conn_file_values(k, proj)) for k in ("ADT_SAP_USER", "ADT_SAP_PASSWORD", "ADT_SAP_URL")}
    if any(n != 1 for n in sayi.values()):
        return None, ".conn_adt'de " + " / ".join(f"{k} {n}" for k, n in sayi.items()) + " kez var (1 bekleniyor)"
    clientlar = conn_file_values("ADT_SAP_CLIENT", proj)
    if len(clientlar) > 1:
        return None, f".conn_adt'de ADT_SAP_CLIENT {len(clientlar)} kez var (en çok 1)"
    if _sistem_anahtari(url, client) != _sistem_anahtari(conn_file_values("ADT_SAP_URL", proj)[0],
                                                          clientlar[0] if clientlar else ""):
        return None, ("hedef URL/client .conn_adt ADT_SAP_URL/ADT_SAP_CLIENT ile aynı değil — .conn_adt kimliği "
                      "başka sisteme gönderilmez")
    # Değer: sap_adt_cli ile AYNI ayrıştırıcı (python-dotenv `load_dotenv` — tırnak/`export`/satır sonu yorumu).
    # dotenv yoksa ham `ANAHTAR=değer` (tam anahtar eşleşmesi).
    try:
        from dotenv import dotenv_values
        d = dotenv_values(yol)
        kullanici, parola = d.get("ADT_SAP_USER"), d.get("ADT_SAP_PASSWORD")
    except ImportError:
        kullanici = conn_file_values("ADT_SAP_USER", proj)[0]
        parola = conn_file_values("ADT_SAP_PASSWORD", proj)[0]
    kullanici = (kullanici or "").replace("\r", "").strip()
    parola = (parola or "").rstrip("\r\n")
    if not kullanici or not parola:
        return None, ".conn_adt ADT_SAP_USER/ADT_SAP_PASSWORD boş"
    return (kullanici, parola), None


_DOGRU = ("true", "1", "yes")
_HOST_DESENI = re.compile(r"(?i)\b(?:[a-z0-9-]+\.){2,}[a-z0-9-]+\b")  # en az 3 parçalı ad / IPv4


def _conn_ssl_dogrula(proj) -> bool:
    """`.conn_adt` kolunda sertifika doğrulaması: sap-adt-foundation ADT kütüphanesiyle AYNI kural — env
    `ADT_SAP_SSL_VERIFY` (varsa) > `.conn_adt` değeri > varsayılan KAPALI (`sap_adt_lib.py`: verify yalnız true/1/yes).
    Aynı sisteme ADT kanalı bağlanırken bu komutun sertifika yüzünden düşmemesi için (ölçüldü 2026-10-03: ADT çalışıyor,
    metadata `CERTIFICATE_VERIFY_FAILED` hostname mismatch).
    Değer ADT kütüphanesiyle AYNI ayrıştırıcıdan okunur (python-dotenv: satır sonu yorumu, `export`, tekrar eden
    anahtarda son kazanır); ham satır okuması bu üç durumda doğrulamayı yanlışlıkla KAPATIYORDU (bug-gate 2026-10-03)."""
    deger = os.environ.get("ADT_SAP_SSL_VERIFY")
    if deger is None:
        try:
            if str(FOUNDATION_SCRIPTS) not in sys.path:
                sys.path.insert(0, str(FOUNDATION_SCRIPTS))
            from sapadt.project import conn_file_values, conn_path
            try:
                from dotenv import dotenv_values
                deger = dotenv_values(conn_path(proj)).get("ADT_SAP_SSL_VERIFY") or "false"
            except ImportError:
                degerler = conn_file_values("ADT_SAP_SSL_VERIFY", proj)
                deger = degerler[-1] if degerler else "false"
        except Exception:  # noqa: BLE001
            deger = "false"
    return deger.strip().strip("'\"").lower() in _DOGRU


def _host_maskele(metin: str) -> str:
    """Ağ hatası metnindeki host adı / IP'yi gizler (SSL hata metni host adını içerir — ölçüldü)."""
    return _HOST_DESENI.sub("<host>", metin)


def _powershell_yolu() -> tuple[str | None, str | None]:
    """Windows PowerShell 5.1 (`powershell.exe`) yolu — Get-Credential GUI penceresi yalnız onda (pwsh 7 konsolda sorar)."""
    if os.name != "nt":
        return None, "Windows değil — giriş penceresi yok"
    ps = shutil.which("powershell.exe")
    return (ps, None) if ps else (None, "powershell.exe (Windows PowerShell 5.1) bulunamadı")


def _pencere_kimlik(servis: str, url: str, client: str, calistir=None):
    """③ Windows giriş penceresi → ((kullanıcı, parola), None) | (None, neden). Neden metninde sır YOK: PowerShell'in
    stdout'u (sırrı taşıyan tek kanal) ve stderr'i hiçbir koşulda basılmaz; yalnız çıkış kodu söylenir."""
    ps, neden = _powershell_yolu()
    if not ps:
        return None, neden
    mesaj = f"SAP kullanıcı adı ve parolası — {servis} $metadata salt-okuma ({url} client {client or '-'})"
    komut = [ps, "-NoProfile", "-NoLogo", "-EncodedCommand", base64.b64encode(_PS_BETIK.encode("utf-16-le")).decode()]
    try:
        p = (calistir or subprocess.run)(komut, capture_output=True, stdin=subprocess.DEVNULL,
                                         timeout=PENCERE_ZAMAN_ASIMI, env={**os.environ, _PS_MESAJ_ENV: mesaj})
    except subprocess.TimeoutExpired:
        return None, f"giriş penceresi {PENCERE_ZAMAN_ASIMI} sn içinde doldurulmadı"
    except OSError as exc:
        return None, f"giriş penceresi açılamadı ({type(exc).__name__})"
    if p.returncode != 0:
        return None, f"giriş penceresi iptal edildi ya da açılamadı (rc={p.returncode})"
    try:
        k64, p64 = (p.stdout or b"").decode("ascii").strip().split(" ")
        kullanici = base64.b64decode(k64, validate=True).decode("utf-8").strip().lstrip("\\")
        parola = base64.b64decode(p64, validate=True).decode("utf-8")
    except Exception as exc:  # noqa: BLE001 — içerik sır taşıyabilir: yalnız tür adı
        return None, f"giriş penceresi yanıtı beklenen biçimde değil ({type(exc).__name__})"
    if not kullanici or not parola:
        return None, "giriş penceresinde kullanıcı adı ya da parola boş bırakıldı"
    return (kullanici, parola), None


def _metadata_kimlik(a, url: str, client: str):
    """Sıra: env → `.conn_adt` (yalnız aynı sistem) → pencere. → ((kullanıcı, parola), kaynak) | (None, None)."""
    k = B.env_kimlik()
    if k:
        return k, "env"
    k, conn_neden = _conn_kimlik(getattr(a, "project_dir", None), url, client)
    if k:
        return k, ".conn_adt"
    print(f"  .conn_adt kimliği kullanılmadı: {conn_neden}")
    k, pencere_neden = _pencere_kimlik(a.servis.strip(), url, client)
    if k:
        return k, "pencere"
    print(f"[FAIL] kimlik yok — env {B.ENV_KULLANICI}/{B.ENV_PAROLA} set değil · .conn_adt: {conn_neden} · "
          f"pencere: {pencere_neden}. Model parola İSTEMEZ (sohbet/log'a düşer). (exit 2)")
    return None, None


# ───────────────────────── metadata: EDMX denetimi + kaydetme (Z168) ─────────────────────────

def _edmx_tipleri(ham: bytes) -> dict:
    """Kökü `Edmx` olan belge → {EntityType: {Property: öznitelikler}}; değilse ValueError (kök adı mesajda).
    XHTML giriş sayfası XML olarak ayrışabilir ve 0 EntityType verir — bu "alan yok" DEĞİL, ölçüm yok demektir."""
    kok = ET.fromstring(ham)
    ad = kok.tag.rsplit("}", 1)[-1]
    if ad != "Edmx":
        raise ValueError(f"kök <{ad[:40]}> — Edmx değil")
    return K.metadata_tipleri(ham)


def _servis_eslesir(yol: str, servis: str) -> bool:
    son = (yol or "").strip().rstrip("/").rsplit("/", 1)[-1]
    return bool(son) and son.upper() == servis.upper()


def _uygulama_ici(app: Path, yol: Path) -> Path | None:
    try:
        r = yol.resolve()
        r.relative_to(app.resolve())
        return r
    except (ValueError, OSError):
        return None


def _kayit_yolu(a, servis: str) -> tuple[Path | None, list[str]]:
    """--kaydet hedefi → (yol, notlar) | (None, [neden]). Sıra docstring'de (①–④)."""
    if isinstance(a.kaydet, str) and a.kaydet.strip():
        return Path(a.kaydet.strip()), ["yol: --kaydet ile verildi"]
    if not a.app:
        return None, ["--kaydet yol almadıysa --app <app_klasoru> gerekir (ya da --kaydet <yol>)"]
    app = Path(a.app)
    notlar: list[str] = []
    mock = None
    mock_dosya = app / "ui5-mock.yaml"
    if mock_dosya.is_file():
        sk, _ = B.yaml_duzlestir(mock_dosya.read_text(encoding="utf-8-sig", errors="replace"))
        for k, v in sk.items():
            if k.endswith(".urlPath") and _servis_eslesir(v, servis):
                mp = sk.get(k[: -len("urlPath")] + "metadataPath", "")
                if mp:
                    mock = (app / mp, mp)
                    break
    man = None
    ds_ad = None
    man_dosya = app / "webapp" / "manifest.json"
    if man_dosya.is_file():
        try:
            kaynaklar = (json.loads(man_dosya.read_text(encoding="utf-8-sig")).get("sap.app") or {}).get("dataSources")
        except (ValueError, AttributeError) as exc:
            return None, [f"webapp/manifest.json okunamadı ({type(exc).__name__}) — --kaydet <yol> ver"]
        for ad, ds in (kaynaklar or {}).items():
            if isinstance(ds, dict) and _servis_eslesir(ds.get("uri", ""), servis):
                ds_ad = ad
                lu = (ds.get("settings") or {}).get("localUri") if isinstance(ds.get("settings"), dict) else None
                if isinstance(lu, str) and lu.strip():
                    man = (app / "webapp" / lu.strip().lstrip("/"), lu.strip())
                break
    if mock:
        secilen, kaynak = mock[0], f"ui5-mock.yaml metadataPath ({mock[1]})"
        if man and _uygulama_ici(app, man[0]) != _uygulama_ici(app, mock[0]):
            notlar.append(f"[UYARI] manifest {ds_ad}.settings.localUri ({man[1]}) ui5-mock.yaml metadataPath'ten "
                          "FARKLI — mock sunucunun okuduğu dosya yazılıyor; localUri'yi eşleyin ya da --kaydet <yol>")
    elif man:
        secilen, kaynak = man[0], f"manifest {ds_ad}.settings.localUri ({man[1]})"
    elif ds_ad == "mainService":
        secilen, kaynak = app / "webapp" / "localService" / "mainService" / "metadata.xml", "varsayılan (mainService)"
    else:
        neden = (f"servis manifest'te '{ds_ad}' dataSource'u — localUri yok ve mainService değil" if ds_ad
                 else "servis ne ui5-mock.yaml'da ne manifest dataSources'ta")
        return None, [f"yol türetilemedi: {neden}. Başka servisin dosyası ezilmesin diye YAZILMADI — --kaydet <yol> ver"]
    r = _uygulama_ici(app, secilen)
    if r is None:
        return None, [f"türetilen yol uygulama klasörünün DIŞINDA ({kaynak}) — YAZILMADI; --kaydet <yol> ver"]
    return r, [f"yol: {kaynak}"] + notlar


def _ozellikler(tipler: dict) -> set:
    return {(t, p) for t, alanlar in tipler.items() for p in alanlar}


def _kaydet(yol: Path, ham: bytes, tipler: dict) -> bool:
    """Atomik yaz + önce/sonra özeti. Bayt bayt aynıysa yazmaz. Hata → False (basıldı)."""
    eski_ham = None
    if yol.is_file():
        try:
            eski_ham = yol.read_bytes()
        except OSError as exc:
            print(f"[FAIL] mevcut {yol} okunamadı ({type(exc).__name__}) — üzerine YAZILMADI (exit 2)")
            return False
    if eski_ham == ham:
        print(f"  kaydet: {yol} zaten bayt bayt aynı ({len(ham)} bayt) — yazılmadı, değişiklik yok")
        return True
    try:
        yol.parent.mkdir(parents=True, exist_ok=True)
        gecici = yol.with_name(yol.name + ".yeni")
        gecici.write_bytes(ham)
        os.replace(gecici, yol)
    except OSError as exc:
        print(f"[FAIL] {yol} yazılamadı ({type(exc).__name__}: {exc}) (exit 2)")
        return False
    yeni = _ozellikler(tipler)
    sonra = f"{len(ham)} bayt, EntityType {len(tipler)}, Property {len(yeni)}"
    if eski_ham is None:
        print(f"  [KAYDEDİLDİ] {yol} — önce: dosya yoktu · sonra: {sonra}")
        return True
    try:
        eski_t = _edmx_tipleri(eski_ham)
    except Exception as exc:  # noqa: BLE001
        print(f"  [KAYDEDİLDİ] {yol} — önce: {len(eski_ham)} bayt, ayrıştırılamadı ({type(exc).__name__}; "
              f"karşılaştırma yok) · sonra: {sonra}")
        return True
    eski = _ozellikler(eski_t)
    eklenen, kalkan = sorted(yeni - eski), sorted(eski - yeni)
    et_ek, et_kalk = sorted(set(tipler) - set(eski_t)), sorted(set(eski_t) - set(tipler))
    print(f"  [KAYDEDİLDİ] {yol} — önce: {len(eski_ham)} bayt, EntityType {len(eski_t)}, Property {len(eski)} · "
          f"sonra: {sonra}")
    print(f"    Property +{len(eklenen)} eklenen / -{len(kalkan)} kalkan · EntityType +{len(et_ek)} / -{len(et_kalk)}")
    for isaret, liste in (("+", eklenen), ("-", kalkan)):
        for t, p in liste[:20]:
            print(f"    {isaret} {t}.{p}")
        if len(liste) > 20:
            print(f"    … {isaret}{len(liste) - 20} daha")
    for isaret, liste in (("+", et_ek), ("-", et_kalk)):
        for t in liste[:20]:
            print(f"    {isaret} EntityType {t}")
    return True


def komut_metadata(a) -> int:
    hedef = _hedef(a)
    if not hedef:
        return 2
    url, client = hedef
    servis = a.servis.strip()
    kayit_yolu = None
    if a.kaydet is not None:  # yol sorunu ağdan ÖNCE söylensin (kimlik/pencere boşuna istenmesin)
        kayit_yolu, notlar = _kayit_yolu(a, servis)
        if kayit_yolu is None:
            print(f"[FAIL] --kaydet: {notlar[0]} (exit 2)")
            return 2
        for n in notlar:
            print(f"  {n}")
    kimlik, kaynak = _metadata_kimlik(a, url, client)
    if not kimlik:
        return 2
    print(f"  kimlik: {kaynak}")
    sertifika_yok = a.ignore_cert
    if kaynak == ".conn_adt" and not sertifika_yok and not _conn_ssl_dogrula(getattr(a, "project_dir", None)):
        sertifika_yok = True
        print("  sertifika doğrulaması: kapalı (.conn_adt ADT_SAP_SSL_VERIFY ≠ true — ADT kanalıyla aynı kural)")
    try:
        ham = B.http_get(K._url(url, f"/sap/opu/odata/sap/{servis}/$metadata", client), kimlik, sertifika_yok)
    except Exception as exc:  # noqa: BLE001
        neden = getattr(exc, "reason", "")  # URLError: ağ sebebi (DNS/SSL); host adı maskelenir, kimlik içermez
        print(f"[FAIL] $metadata okunamadı ({type(exc).__name__} {getattr(exc, 'code', '')}"
              f"{(' · ' + _host_maskele(str(neden))) if neden else ''}) — ölçüm yok (exit 2)")
        return 2
    try:
        tipler = _edmx_tipleri(ham)
    except Exception as exc:  # noqa: BLE001 — XML değil ya da kök Edmx değil (ör. giriş sayfası)
        neden = str(exc) if isinstance(exc, ValueError) and "Edmx" in str(exc) else type(exc).__name__
        print(f"[FAIL] $metadata yanıtı EDMX değil ({neden}; giriş/hata sayfası olabilir) — ölçüm yok"
              + (", dosya YAZILMADI" if kayit_yolu else "") + " (exit 2)")
        return 2
    print(f"  {servis} $metadata: {len(ham)} bayt, EntityType {len(tipler)}")
    if kayit_yolu is not None and not _kaydet(kayit_yolu, ham, tipler):
        return 2
    if a.tip and a.tip not in tipler:
        print(f"[FAIL] EntityType '{a.tip}' yok. Var olanlar: {', '.join(sorted(tipler)) or '-'} (exit 2)")
        return 2
    kapsam = {a.tip: tipler[a.tip]} if a.tip else tipler
    eksik = 0
    for alan in a.alan or []:
        bulunan = [(t, alanlar[alan]) for t, alanlar in sorted(kapsam.items()) if alan in alanlar]
        if not bulunan:
            eksik += 1
            print(f"  [YOK] {alan}" + (f" ({a.tip} içinde)" if a.tip else " (hiçbir EntityType'ta)"))
            continue
        for t, oz in bulunan:
            print(f"  [VAR] {t}.{alan} " + " ".join(f'{k}="{v}"' for k, v in oz.items()))
    if a.alan and not a.tip:
        print("  NOT: --tip verilmedi — alanın UYGULAMANIN KULLANDIĞI EntityType'ta olduğunu hükme bağlamak için "
              "--tip <EntityType> ver (başka tipteki aynı adlı alan yanlış pozitif verir).")
    print("KAPSAM: yalnız $metadata metni; verinin dolu gelmesi ayrıca ölçülür (entity okuması / SQL)."
          + (" Kaydedilen dosya SAP yanıtıdır (bayt bayt); annotation dosyaları (ANNO_MDL) ve mock veri "
             "(mockdataPath) GÜNCELLENMEDİ." if kayit_yolu is not None else ""))
    return 1 if eksik else 0


def main(argv: list[str] | None = None) -> int:
    for akis in (sys.stdout, sys.stderr):
        try:
            akis.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass
    ap = argparse.ArgumentParser(description="UI5 BSP kaynağını SAP'den indir / eşlik / drift / $metadata (salt-okuma)")
    alt = ap.add_subparsers(dest="komut", required=True)
    p = alt.add_parser("indir", help="canlıdan indir + kaynağı geri kur + iskelet + anlık görüntü")
    p.add_argument("bsp")
    p.add_argument("--out", required=True, help="uygulama klasörü (ör. <source_root>/SD/<PAKET>/ui/<app>)")
    p.add_argument("--project-dir")
    p.add_argument("--url")
    p.add_argument("--client")
    p.add_argument("--ignore-cert", action="store_true")
    p = alt.add_parser("eslik", help="değiştirilmemiş kaynaktan build == canlı mı (ağsız)")
    p.add_argument("app")
    p.add_argument("--no-build", action="store_true")
    p = alt.add_parser("drift", help="canlı, anlık görüntüden sonra değişti mi")
    p.add_argument("app")
    p.add_argument("--ignore-cert", action="store_true")
    p = alt.add_parser("anlik-kur", help="Z160: kaynağı yerelde olan uygulama için canlı anlık görüntüsünü kur")
    p.add_argument("app")
    p.add_argument("--no-build", action="store_true")
    p.add_argument("--kabul", action="store_true",
                   help="yerel ≠ canlı olsa da yaz — YALNIZ kullanıcı farkı gördü ve canlıyı ezmeyi kabul ettiyse")
    p.add_argument("--ignore-cert", action="store_true")
    p = alt.add_parser("metadata", help="OData V2 $metadata'da alan var mı / tam $metadata'yı kaydet")
    p.add_argument("servis")
    p.add_argument("--kaydet", nargs="?", const="", default=None, metavar="YOL",
                   help="tam $metadata'yı yaz; YOL yoksa --app'ten türetilir (ui5-mock.yaml → manifest localUri → "
                        "mainService varsayılanı)")
    p.add_argument("--alan", action="append")
    p.add_argument("--tip", help="EntityType adı — alan aramasını bu tiple sınırla (önerilir)")
    p.add_argument("--app")
    p.add_argument("--project-dir")
    p.add_argument("--url")
    p.add_argument("--client")
    p.add_argument("--ignore-cert", action="store_true")
    a = ap.parse_args(argv)
    return {"indir": komut_indir, "eslik": komut_eslik, "drift": komut_drift, "anlik-kur": komut_anlik_kur,
            "metadata": komut_metadata}[a.komut](a)


if __name__ == "__main__":
    raise SystemExit(main())
