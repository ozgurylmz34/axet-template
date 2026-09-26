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
  metadata <SERVIS> [--alan AD ...] [--tip ENTITYTYPE] [--app <app_klasoru> | --project-dir <proje> | --url URL --client NNN] [--ignore-cert]
      OData V2 `$metadata`'yı SALT-OKUMA çeker; verilen alanların `<Property …/>` satırını basar (alan var mı,
      tipi, etiketi). `sap-adt-foundation` CLI'de `$metadata` aracı yoktu (foundation-query.md §5).

Kimlik: env FIORI_TOOLS_USER / FIORI_TOOLS_PASSWORD (script basmaz, dosyadan okumaz).
Çıkış: 0 tamam/eşit · 1 fark/ihlal · 2 ölçüm yok (kimlik yok, canlı okunamadı, anlık görüntü yok, `eslik`te
build başarısız / dist yok)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
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


def komut_metadata(a) -> int:
    hedef = _hedef(a)
    kimlik = _kimlik()
    if not hedef or not kimlik:
        return 2
    url, client = hedef
    servis = a.servis.strip()
    try:
        ham = B.http_get(K._url(url, f"/sap/opu/odata/sap/{servis}/$metadata", client), kimlik, a.ignore_cert)
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] $metadata okunamadı ({type(exc).__name__} {getattr(exc, 'code', '')}) — ölçüm yok (exit 2)")
        return 2
    try:
        tipler = K.metadata_tipleri(ham)
    except Exception as exc:  # noqa: BLE001 — XML değil (ör. giriş sayfası)
        print(f"[FAIL] $metadata ayrıştırılamadı ({type(exc).__name__}) — ölçüm yok (exit 2)")
        return 2
    print(f"  {servis} $metadata: {len(ham)} bayt, EntityType {len(tipler)}")
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
    print("KAPSAM: yalnız $metadata metni; verinin dolu gelmesi ayrıca ölçülür (entity okuması / SQL).")
    return 1 if eksik else 0


def main() -> int:
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
    p = alt.add_parser("metadata", help="OData V2 $metadata'da alan var mı")
    p.add_argument("servis")
    p.add_argument("--alan", action="append")
    p.add_argument("--tip", help="EntityType adı — alan aramasını bu tiple sınırla (önerilir)")
    p.add_argument("--app")
    p.add_argument("--project-dir")
    p.add_argument("--url")
    p.add_argument("--client")
    p.add_argument("--ignore-cert", action="store_true")
    a = ap.parse_args()
    return {"indir": komut_indir, "eslik": komut_eslik, "drift": komut_drift, "metadata": komut_metadata}[a.komut](a)


if __name__ == "__main__":
    raise SystemExit(main())
