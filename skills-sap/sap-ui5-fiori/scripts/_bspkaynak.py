#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_bspkaynak.py — deploy edilmiş UI5 uygulamasının (BSP) dosyalarını SAP'den SALT-OKUMA indirir, düzenlenebilir
kaynağı geri kurar ve iki dosya kümesini karşılaştırır (Z144). Tek başına çalıştırılmaz; `fetch_ui_source.py` ve
`deploy_ui.py` içe aktarır.

ÖLÇÜLMÜŞ YÖNTEM (2026-09-26, tek freestyle BSP, 41 dosya, kontrol gruplu):
  • OData  `/sap/opu/odata/UI5/ABAP_REPOSITORY_SRV/Repositories('<BSP>')` → `d.ZipArchive` (base64 zip): TEK istek.
  • ADT    `/sap/bc/adt/filestore/ui5-bsp/objects/<BSP>/content` (Atom, klasörler özyinelemeli; `id` URL-kodlu).
    İki yol BAYT BAYT eşit çıktı (41/41). OData birincil, ADT yedek.
  • ICF    `/sap/bc/ui5_ui5/sap/<bsp>/<dosya>` KULLANILMAZ: dizin listelemez ve HTML'e runtime'da üç meta
    enjekte eder (`sap-client`, `sap-ui-fesr`, `sap.whitelistService`) → HTML dosyaları kaynaktan farklı gelir.
  • BSP'de DERLENMİŞ dist durur. Özgün kaynak `X-dbg.js` / `X-dbg.controller.js`'tir (`X.js.map` `sources` alanı
    `X-dbg.js`'i gösterir). Geri kurma: `-dbg` → asıl ad; preload + `.js.map` + `-dbg` karşılığı olan küçültülmüş
    `.js` atılır; kalan her dosya aynen. METİN dosyalarında satır sonu LF'e indirilir: SAP dosyayı CRLF saklıyor,
    özgün build LF ağaçtan yapılmıştı — CRLF bırakılınca preload yalnız satır sonu farkı verdi, LF'te 41/41 eşit.
  • ÖLÇÜLMEDİ: TypeScript uygulama (sunucuda TS kaynağı yok), `-dbg` üretmeyen build, Fiori Elements. Bu yüzden
    geri kurulan kaynak, DEĞİŞTİRİLMEDEN derlenip canlıyla karşılaştırılmadan (eşlik) düzenlenmez.

KİMLİK: `_bspnet.env_kimlik()` (FIORI_TOOLS_USER / FIORI_TOOLS_PASSWORD) — dosyadan kimlik OKUNMAZ, basılmaz.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import shutil
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import _bspnet as B

ODATA_REPO = "/sap/opu/odata/UI5/ABAP_REPOSITORY_SRV/Repositories('{bsp}')"
ADT_FILESTORE = "/sap/bc/adt/filestore/ui5-bsp/objects/{oge}/content"
ATOM = "{http://www.w3.org/2005/Atom}"
METIN_UZANTI = {".js", ".xml", ".json", ".properties", ".html", ".htm", ".css", ".txt", ".md", ".yaml", ".yml", ".csv"}
# `@ui5/builder` (4.3.2) `lib/processors/minifier.js`: `debugFileRegex =
# /((?:\.view|\.fragment|\.controller|\.designtime|\.support)?\.js)$/` ve `resourcePath.replace(debugFileRegex, "-dbg$1")`
# → `-dbg` bu sonek grubunun ÖNÜNE girer (`Main.view.js` → `Main-dbg.view.js`). `_DBG_ILERI` builder'ın kendisidir;
# `-dbg` varyantı ters regex'le DEĞİL bu ileri kuralla eşlenir (`dbg_ciftleri`): adı zaten `-dbg` ile biten gerçek
# kaynak dosyası (`util-dbg.js`) ters regex'te yanlışlıkla varyant sayılıyordu.
_DBG_SONEKLER = r"\.view|\.fragment|\.controller|\.designtime|\.support"
_DBG_ILERI = re.compile(rf"((?:{_DBG_SONEKLER})?\.js)$")
# builder `minifier.js` `sourceMappingUrlPattern` ile aynı biçim (dosya sonunda referans satırı).
_KAYNAK_HARITASI_REF = re.compile(rb"//# sourceMappingURL=\S+\s*$")
ANLIK_KLASOR = ".canli"          # uygulama klasöründe canlı anlık görüntü (git'e girmez)
ANLIK_BILGI = "bilgi.json"


class IndirmeHatasi(Exception):
    pass


class GuvensizYolHatasi(IndirmeHatasi):
    """Sunucudan gelen dosya adı (zip adı / ADT id) hedef klasörün DIŞINI gösteriyor (zip-slip) — hiçbir dosya yazılmaz.
    `IndirmeHatasi` alt sınıfıdır: indirmeyi saran mevcut `except` dalları bunu "ölçüm yok" olarak yakalar."""


_R_SURUCU = re.compile(r"^[A-Za-z]:")
# Windows aygıt adları: uzantılı hâlleri de (`AUX.json`, `nul.txt`) dosya DEĞİL aygıttır — yazım hata vermeden aygıta
# gider ve dosya kaybolur (ölçüldü: `klasore_yaz(t, {'a/NUL': …})` hata vermedi, dosya yoktu). Üst simge rakamlı
# COM/LPT de Windows'ta aygıttır.
_AYGIT_ADLARI = ({"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
                 | {f"{on}{r}" for on in ("COM", "LPT") for r in (*"123456789", "¹", "²", "³")})


def _aygit_adi_mi(segment: str) -> bool:
    """Segmentin ilk noktaya kadarki kökü (boşluk kırpılmış, harfe duyarsız) bir Windows aygıt adı mı?"""
    return segment.split(".", 1)[0].strip().upper() in _AYGIT_ADLARI


def yol_guvenli_mi(rel: str) -> bool:
    """Metin kuralı (diske bakmaz): göreli, `..` segmentsiz, sürücü harfsiz, `:` içermeyen (NTFS akışı) ad mı?
    Sonu boşluk/nokta ile biten segment (`.` hariç) de güvensizdir: Windows bunları kırpar (`.. ` → `..`), yani
    aynı ad Windows'ta kök dışına, POSIX'te kök içine düşer (ölçüldü: `a/.. /.. /x.js` resolve'dan geçti, yazımda
    `a/f.js` yazıldıktan sonra OSError verdi) — platforma göre anlamı değişen ad fail-closed reddedilir.
    Windows aygıt adı olan segment (`CON`, `NUL`, `AUX.json`, `lpt1.txt` … harfe duyarsız, her segmentte) de
    güvensizdir — POSIX'te sıradan dosya, Windows'ta aygıt: yine platforma göre anlamı değişir."""
    if not rel or rel.startswith(("/", "\\")) or _R_SURUCU.match(rel) or ":" in rel:
        return False
    segmentler = rel.replace("\\", "/").split("/")
    return (".." not in segmentler and all(s == "." or s == s.rstrip(" .") for s in segmentler)
            and not any(_aygit_adi_mi(s) for s in segmentler))


def guvenli_hedef(kok: Path, rel: str) -> Path:
    """`kok / rel` → hedef yol; metin kuralı + `resolve()` ile kökün İÇİNDE olduğu doğrulanır, değilse
    GuvensizYolHatasi (çözülemeyen ad — ör. NUL baytı → ValueError, OSError — dahil)."""
    if not yol_guvenli_mi(rel):
        raise GuvensizYolHatasi(f"güvensiz dosya adı (kök dışı / mutlak / sürücülü / sonu boşluk-nokta): {rel!r}")
    try:
        kok_r = Path(kok).resolve()
        hedef = (kok_r / rel).resolve()
    except (ValueError, OSError) as exc:
        raise GuvensizYolHatasi(f"dosya adı çözülemedi ({type(exc).__name__}: {exc}): {rel!r}") from exc
    if hedef == kok_r or kok_r not in hedef.parents:
        raise GuvensizYolHatasi(f"dosya adı kök dışına çözülüyor: {rel!r}")
    return hedef


# Hedef kök bilinmediğinde (indirme anı) `resolve()` denetimi için var olmayan nötr kök: yalnız ad çözümlemesi
# ölçülür, diske yazılmaz.
_NOTR_KOK = Path(__file__).resolve().parent / "_ad_dogrulama_koku_yok"


def _adlari_dogrula(dosyalar: dict, kok: Path | None = None) -> None:
    """Tüm adlar `guvenli_hedef` ile (metin kuralı + resolve) doğrulanır; biri bile güvensizse GuvensizYolHatasi.
    `kok` verilirse gerçek hedef köke göre çözülür (ör. `.` → kökün kendisi → red)."""
    kotu = []
    for r in sorted(dosyalar):
        try:
            guvenli_hedef(kok if kok is not None else _NOTR_KOK, r)
        except GuvensizYolHatasi:
            kotu.append(r)
    if kotu:
        raise GuvensizYolHatasi(f"sunucu {len(kotu)} güvensiz dosya adı döndürdü (zip-slip): {kotu[:3]}")


def _url(taban: str, yol: str, client: str, ek: dict | None = None) -> str:
    q = dict(ek or {})
    if client:
        q["sap-client"] = client
    return f"{taban.rstrip('/')}{yol}" + ("?" + urllib.parse.urlencode(q, safe="'$") if q else "")


def odata_indir(taban: str, client: str, bsp: str, kimlik, sertifika_yok_say: bool = False,
                get=None) -> tuple[dict, dict]:
    """→ ({rel: bayt}, {Name, Package, Description, Info}). HTTP hatası istisna olarak yükselir."""
    get = get or B.http_get
    url = _url(taban, ODATA_REPO.format(bsp=bsp), client,
               {"$format": "json", "CodePage": "'UTF8'", "DownloadFiles": "'RUNTIME'"})
    ham = get(url, kimlik, sertifika_yok_say)
    try:
        d = json.loads(ham)["d"]
    except (ValueError, KeyError, TypeError) as exc:
        raise IndirmeHatasi(f"OData yanıtı beklenen biçimde değil ({type(exc).__name__})") from exc
    z = d.get("ZipArchive") or ""
    if not z:
        raise IndirmeHatasi("OData yanıtında ZipArchive boş")
    dosyalar = {}
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(z))) as zf:
        for ad in zf.namelist():
            if not ad.endswith("/"):
                dosyalar[ad] = zf.read(ad)
    bilgi = {k: d.get(k, "") for k in ("Name", "Package", "Description", "Info")}
    return dosyalar, bilgi


def adt_indir(taban: str, client: str, bsp: str, kimlik, sertifika_yok_say: bool = False, get=None) -> dict:
    """ADT filestore yedek yolu → {rel: bayt}. Klasörler özyinelemeli gezilir; `id` URL-kodludur (çözülür)."""
    get = get or B.http_get
    dosyalar, kuyruk, gorulen = {}, [bsp], set()
    while kuyruk:
        oge = kuyruk.pop()
        if oge in gorulen:
            continue
        gorulen.add(oge)
        govde = get(_url(taban, ADT_FILESTORE.format(oge=urllib.parse.quote(oge, safe="")), client),
                    kimlik, sertifika_yok_say)
        for e in ET.fromstring(govde).iter(f"{ATOM}entry"):
            ad = urllib.parse.unquote(e.findtext(f"{ATOM}id") or e.findtext(f"{ATOM}title") or "")
            if not ad:
                continue
            turler = [c.get("term") for c in e.iter(f"{ATOM}category")]
            if "folder" in turler:
                kuyruk.append(ad)
                continue
            icerik = get(_url(taban, ADT_FILESTORE.format(oge=urllib.parse.quote(ad, safe="")), client),
                         kimlik, sertifika_yok_say)
            dosyalar[ad.split("/", 1)[1] if "/" in ad else ad] = icerik
    return dosyalar


def canli_indir(taban: str, client: str, bsp: str, kimlik, sertifika_yok_say: bool = False,
                get=None) -> tuple[dict, dict, str]:
    """OData birincil, ADT yedek → (dosyalar, bilgi, kullanılan yol). İkisi de düşerse IndirmeHatasi.
    Dosya adlarından biri güvensizse (zip-slip) GuvensizYolHatasi — yedek yola SESSİZCE geçilmez."""
    try:
        d, bilgi = odata_indir(taban, client, bsp, kimlik, sertifika_yok_say, get)
        yol = "odata"
    except Exception as exc1:  # noqa: BLE001 — yedek yola geç, sebebi taşı
        try:
            d = adt_indir(taban, client, bsp, kimlik, sertifika_yok_say, get)
        except Exception as exc2:  # noqa: BLE001
            raise IndirmeHatasi(f"OData ({type(exc1).__name__}: {getattr(exc1, 'code', '') or exc1}) ve ADT "
                                f"({type(exc2).__name__}: {getattr(exc2, 'code', '') or exc2}) yolları okunamadı") from exc2
        if not d:
            raise IndirmeHatasi(f"OData okunamadı ({type(exc1).__name__}); ADT filestore boş liste döndü") from exc1
        bilgi, yol = {"Name": bsp, "Package": "", "Description": "", "Info": ""}, "adt"
    _adlari_dogrula(d)
    return d, bilgi, yol


def lf(b: bytes) -> bytes:
    return b.replace(b"\r\n", b"\n")


def dbg_adi(rel: str) -> str:
    """Küçültülmüş `a/Main.view.js` → builder'ın ürettiği `-dbg` ADI (`Main-dbg.view.js`; yalnız dosya adı)."""
    return _DBG_ILERI.sub(r"-dbg\1", rel.rpartition("/")[2])


def dbg_ciftleri(dosyalar) -> dict:
    """{`-dbg` varyantı rel: küçültülmüş asıl dosya rel} — builder'ın İLERİ kuralıyla eşlenir: bir dosya ANCAK aynı
    klasörde `dbg_adi(k) == ad` olan bir `k` dosyası varsa `-dbg` varyantıdır. Kaynakta `util-dbg.js` adlı dosya
    builder'da `util-dbg.js` (küçük) + `util-dbg-dbg.js` (varyant) + `util-dbg.js.map` olur: varyant `util-dbg-dbg.js`,
    `util-dbg.js` ise küçültülmüş asıl dosyadır (karşılığı `util.js` YOK ⇒ varyant sayılmaz)."""
    cift = {}
    for k in sorted(dosyalar):
        if not k.endswith(".js"):
            continue
        dizin = k.rpartition("/")[0]
        d = (dizin + "/" if dizin else "") + dbg_adi(k)
        if d in dosyalar:
            cift[d] = k
    return cift


def harita_sondasi(dosyalar: dict) -> tuple[list[str], int]:
    """Canlı dosyalardaki kaynak haritaları → (sapmalar, bakılan harita sayısı). Boş sapma = beklenen biçim.

    Neden: eşlik kapısı build çıktısını kıyaslar; `-dbg.js` bir DÖNÜŞÜM çıktısıysa (TypeScript vb.) ondan yeniden
    build de aynı çıktıyı üretir ⇒ dosyalar EŞİT çıkar ama geri kurulan dosya özgün kaynak değildir. Ayırt edici iz
    haritadadır (`@ui5/builder` 4.x minifier): düz JS build'inde `X.js.map` `sources` alanı YALNIZ `X-dbg.js`'i
    gösterir ve `-dbg` dosyasının kendi haritası YOKTUR; girdi build'den önce dönüştürülmüşse builder `-dbg`'e de
    harita yazar ve `sources` özgün dosyayı (`X.ts` …) gösterir. Sapmalar (hepsi fail-closed):
      · `X.js.map` okunamıyor (JSON değil / `sources` yok) · `sources` != [`X-dbg.js`]
      · `-dbg` dosyasının kendi haritası var
      · küçültülmüş `X.js` + `X-dbg.js` çifti var ama `X.js.map` YOK — 4.x builder her küçültmede harita yazar; canlı
        başka bir araçla build edilmiş demektir ve transpile ayrımı ölçülemez (zaten bizim build'imiz haritayı
        üreteceği için tam liste de eşit çıkmaz — iki kural aynı yöne bakar).
      · `-dbg` içeriği `//# sourceMappingURL=` ile bitiyor — builder girdideki referansı küçültmeden ÖNCE söker;
        yalnız girdi haritası okunmadığında (`useInputSourceMaps: false`) dış referansı `-dbg`'e GERİ ekler ⇒ girdi
        bir dönüşüm çıktısıdır. (Sınır: aynı seçenekle SATIR İÇİ `data:` haritası geri eklenmez — iz kalmaz.)
    `Component-preload.js.map` bundle haritasıdır, burada bakılmaz (preload modül modül kıyaslanır)."""
    sapma, bakilan = [], 0
    cift = dbg_ciftleri(dosyalar)
    for rel in sorted(dosyalar):
        ad = rel.rpartition("/")[2]
        if not ad.endswith(".js.map") or ad == B.PRELOAD + ".map":
            continue
        bakilan += 1
        js = rel[:-len(".map")]
        if js in cift:
            sapma.append(f"{rel}: -dbg dosyasının KENDİ haritası var (girdi build öncesi dönüştürülmüş — TS?)")
            continue
        try:
            kaynaklar = json.loads(dosyalar[rel].decode("utf-8-sig"))["sources"]
        except (ValueError, UnicodeDecodeError, AttributeError, KeyError, TypeError):
            sapma.append(f"{rel}: harita okunamadı (JSON değil ya da `sources` yok)")
            continue
        if kaynaklar != [dbg_adi(js)]:
            sapma.append(f"{rel}: sources={kaynaklar!r} — beklenen [{dbg_adi(js)!r}] (TS / başka kaynak)")
    for rel, kucuk in sorted(cift.items()):
        if _KAYNAK_HARITASI_REF.search(dosyalar[rel][-512:]):
            sapma.append(f"{rel}: `-dbg` içeriği sourceMappingURL taşıyor (girdi build öncesi dönüştürülmüş — TS?)")
        if kucuk + ".map" not in dosyalar:
            sapma.append(f"{kucuk}.map yok ({rel.rpartition('/')[2]} çifti var) — başka build aracı; transpile ayrımı "
                         "ölçülemez")
    return sapma, bakilan


def kaynak_kur(dist: dict) -> tuple[dict, list, list]:
    """Derlenmiş dist → (webapp {rel: bayt}, atılan build ürünleri, uyarılar). Metin dosyaları LF'e indirilir."""
    cift = dbg_ciftleri(dist)              # {`-dbg` varyantı: küçültülmüş asıl} — builder'ın ileri kuralıyla
    dbg_karsiligi = set(cift.values())     # varyantı olan küçültülmüş dosyalar → atılır
    webapp, atilan, uyari = {}, [], []
    for rel, icerik in sorted(dist.items()):
        yol = Path(rel)
        if yol.name.startswith("Component-preload.js") or yol.name.endswith(".js.map") or rel in dbg_karsiligi:
            atilan.append(rel)
            continue
        hedef = cift.get(rel, rel)
        webapp[hedef] = lf(icerik) if yol.suffix.lower() in METIN_UZANTI else icerik
    kucuk_js = [r for r in dist if r.endswith(".js") and r not in cift
                and not Path(r).name.startswith("Component-preload") and r not in dbg_karsiligi]
    if kucuk_js:
        uyari.append(f"{len(kucuk_js)} .js dosyasının -dbg karşılığı yok (ör. {kucuk_js[0]}) — küçültülmüş hâli kaynak "
                     "diye alındı; eşlik ölçümü bunu doğrular, düzenleme okunabilir olmayabilir")
    sapma, _bakilan = harita_sondasi(dist)
    if sapma:
        uyari.append(f"kaynak haritası sapması ({len(sapma)}): {sapma[0]} — geri kurulan JS özgün kaynak "
                     "OLMAYABİLİR (TypeScript / build öncesi dönüşüm); `eslik` bu durumda EŞLİK YOK der, düzenleme "
                     "yapılmaz (kullanıcıya sor)")
    if not any(Path(r).name == "manifest.json" for r in dist):
        uyari.append("manifest.json yok — UI5 uygulaması olmayabilir")
    return webapp, atilan, uyari


def uygulama_kimligi(webapp: dict) -> str:
    """manifest.json `sap.app.id` (ui5.yaml metadata.name için)."""
    ham = webapp.get("manifest.json")
    if not ham:
        return ""
    try:
        return str(json.loads(ham.decode("utf-8-sig")).get("sap.app", {}).get("id") or "")
    except (ValueError, UnicodeDecodeError, AttributeError):
        return ""


def icerik_ozeti(rel: str, b: bytes) -> str:
    """Kıyas özeti: METİN uzantısında satır sonu normalize (`_bspnet.sha` — BSP metni CRLF saklayabilir), İKİLİ dosyada
    (png, font …) HAM bayt: ikili içerikteki
    CR LF baytları veridir, normalize edilirse farklı dosya eşit görünür."""
    return B.sha(b) if Path(rel).suffix.lower() in METIN_UZANTI else hashlib.sha256(b).hexdigest()


def kume_karsilastir(a: dict, b: dict, preload_karsilastir=None) -> dict:
    """İki dosya kümesi → {"esit": [...], "farkli": [...], "yalniz_a": [...], "yalniz_b": [...], "satir_sonu": [...]}.
    Metin dosyasında satır sonu normalize, ikili dosyada ham bayt (`icerik_ozeti`). `Component-preload.js` verilen `preload_karsilastir` ile modül modül
    kıyaslanır: yalnız kaçışlı satır sonu farkıysa `satir_sonu` kovasına düşer (eşit SAYILMAZ, ayrı raporlanır)."""
    sonuc = {"esit": [], "farkli": [], "yalniz_a": [], "yalniz_b": [], "satir_sonu": []}
    for rel in sorted(set(a) | set(b)):
        if rel not in b:
            sonuc["yalniz_a"].append(rel)
        elif rel not in a:
            sonuc["yalniz_b"].append(rel)
        elif icerik_ozeti(rel, a[rel]) == icerik_ozeti(rel, b[rel]):
            sonuc["esit"].append(rel)
        elif preload_karsilastir and Path(rel).name == B.PRELOAD:
            sinif, _ = preload_karsilastir(a[rel], b[rel])
            sonuc["satir_sonu" if sinif == "SATIR_SONU" else "farkli"].append(rel)
        else:
            sonuc["farkli"].append(rel)
    return sonuc


def kume_esit_mi(k: dict) -> bool:
    return not (k["farkli"] or k["yalniz_a"] or k["yalniz_b"] or k["satir_sonu"])


def klasor_oku(kok: Path) -> dict:
    return {p.relative_to(kok).as_posix(): p.read_bytes() for p in sorted(kok.rglob("*")) if p.is_file()}


def klasore_yaz(kok: Path, dosyalar: dict) -> None:
    """`rel` sunucudan gelir: ÖNCE tüm hedefler doğrulanır (hepsi-ya-hiç), biri kök dışıysa hiçbir dosya yazılmaz.
    Yazım sırasında OSError olursa GERİ ALINIR, sonra hata yeniden fırlatılır: kök bu çağrıdan önce yoksa kök
    tümüyle silinir (hiç yaratılmamış hâl — yeniden koşum "zaten var" demez); varsa bu çağrının yazdığı dosyalar
    silinir / üzerine yazılanın eski içeriği geri konur ve bu çağrının yarattığı boş klasörler kaldırılır."""
    hedefler = [(guvenli_hedef(kok, rel), icerik) for rel, icerik in dosyalar.items()]
    kok = Path(kok)
    kok_vardi = kok.exists()
    onceki_klasorler = {p for p in kok.rglob("*") if p.is_dir()} if kok_vardi else set()
    yazilan: list[tuple[Path, bytes | None]] = []
    try:
        for hedef, icerik in hedefler:
            hedef.parent.mkdir(parents=True, exist_ok=True)
            yazilan.append((hedef, hedef.read_bytes() if hedef.is_file() else None))
            hedef.write_bytes(icerik)
    except OSError as exc:
        # Geri alma başarısı BEYAN edilmez, ÖLÇÜLÜR: kalanlar hataya iliştirilir (boş liste = temiz).
        exc.kalanlar = _yazimi_geri_al(kok, kok_vardi, onceki_klasorler, yazilan)
        raise


def _agac_sil(p: Path) -> None:
    """Klasörü siler; hata sessizdir — kalan varsa çağıran ÖLÇER ve raporlar (açık dosya tutamacı `rmtree`'yi yarım
    bırakabilir: ölçüldü, `webapp/a.js` kaldı). Testte tutamaç benzetimi bu fonksiyon üzerinden yapılır."""
    shutil.rmtree(p, ignore_errors=True)


def yollari_kaldir(yollar) -> list[str]:
    """Verilen dosya/klasörleri kaldırmayı DENER, sonra KALANLARI ölçer → kalan yolların listesi (boş = temiz).
    Klasörde kalan dosyalar tek tek listelenir; yalnız boş klasör kaldıysa klasörün kendisi."""
    yollar = [Path(p) for p in yollar]
    for p in yollar:
        try:
            if p.is_dir() and not p.is_symlink():
                _agac_sil(p)
            elif p.exists() or p.is_symlink():
                p.unlink()
        except OSError:
            pass
    kalan: list[str] = []
    for p in yollar:
        if p.is_dir():
            kalan += [str(q) for q in sorted(p.rglob("*")) if not q.is_dir()] or [str(p)]
        elif p.exists() or p.is_symlink():
            kalan.append(str(p))
    return kalan


def _yazimi_geri_al(kok: Path, kok_vardi: bool, onceki_klasorler: set, yazilan: list) -> list[str]:
    """`klasore_yaz` geri alımı → geri alınamayan yollar (boş = temiz). Kendi hatası asıl hatayı gölgelemesin diye her
    adım sessizce denenir; sonuç ÖLÇÜLEREK döner."""
    if not kok_vardi:
        return yollari_kaldir([kok])
    for hedef, eski in reversed(yazilan):
        try:
            hedef.unlink(missing_ok=True) if eski is None else hedef.write_bytes(eski)
        except OSError:
            pass
    yeni = sorted((p for p in kok.rglob("*") if p.is_dir() and p not in onceki_klasorler),
                  key=lambda p: len(p.parts), reverse=True)
    for p in yeni:
        try:
            p.rmdir()
        except OSError:
            pass
    def _geri_alinamadi(h: Path, eski: bytes | None) -> bool:
        try:
            return h.exists() if eski is None else (not h.is_file() or h.read_bytes() != eski)
        except OSError:
            return True
    kalan = [str(h) for h, eski in yazilan if _geri_alinamadi(h, eski)]
    return kalan + [str(p) for p in yeni if p.exists()]


def anlik_ham(kok: Path) -> dict | None:
    """Anlık görüntünün KENDİSİNİN baytları (`bilgi.json` + `dist/**`) — koruma ÖLÇÜMÜ için. Geçici adlar
    (`dist.yeni`, `dist.eski`, `bilgi.json.yeni`) dahil DEĞİL: onlar çağıranda ayrıca "kalan" olarak ölçülür.
    Okunamazsa None (ölçüm yok ⇒ çağıran "korundu" DEMEZ)."""
    try:
        if not kok.is_dir():
            return None
        return {r: b for r, b in klasor_oku(kok).items() if r == ANLIK_BILGI or r.startswith("dist/")}
    except OSError:
        return None


def anlik_yaz(app: Path, dosyalar: dict, bilgi: dict) -> Path:
    """Canlı anlık görüntüyü `<app>/.canli/dist/` + `bilgi.json`'a yazar (eskisinin yerine) — HEPSİ-YA-HİÇ.

    Yeni görüntü önce `dist.yeni/` + `bilgi.json.yeni`'ye yazılır; ANCAK ikisi de tamamsa takas edilir
    (`dist`→`dist.eski`, `dist.yeni`→`dist`, `bilgi.json.yeni`→`bilgi.json` [`os.replace`], sonra `dist.eski` silinir).
    Bir adım düşerse eski görüntü (dist + bilgi.json) yerine geri konur, geçici adlar temizlenir ve hata yeniden
    fırlatılır; temizlenemeyen geçici yollar `exc.kalanlar`'a iliştirilir. Eski görüntünün KORUNDUĞU burada beyan
    edilmez: çağıran `anlik_ham` ile önce/sonra BAYT BAYT ölçer (`indir`, `deploy`).
    Eskiden eski `dist` yeni yazımdan ÖNCE siliniyordu → yazım düşünce `anlik_oku` = ({}, eski bilgi) (ölçüldü)."""
    kok = app / ANLIK_KLASOR
    dist, yeni, eski = kok / "dist", kok / "dist.yeni", kok / "dist.eski"
    bilgi_yol, bilgi_yeni = kok / ANLIK_BILGI, kok / (ANLIK_BILGI + ".yeni")
    # Tüm adlar GERÇEK hedef köke göre (metin kuralı + resolve) doğrulanır: güvensiz ad (`.`, `.. /x.js`, NUL'lu ad …)
    # → GuvensizYolHatasi ve hiçbir şeye dokunulmaz.
    _adlari_dogrula(dosyalar, dist)
    # Önceki bir koşum takasın ORTASINDA kesildiyse (`dist` yok, `dist.eski` var) eski görüntü önce geri konur.
    if eski.is_dir() and not dist.exists():
        eski.rename(dist)
    artik = yollari_kaldir([yeni, eski, bilgi_yeni])  # bayat geçici adlar
    if artik:
        hata = OSError(f"önceki koşumdan kalan geçici anlık görüntü silinemedi: {artik[:5]}")
        hata.kalanlar = artik
        raise hata
    dist_vardi = dist.exists()
    try:
        kok.mkdir(parents=True, exist_ok=True)
        klasore_yaz(yeni, dosyalar)
        bilgi_yeni.write_text(json.dumps(
            {**bilgi, "dosyalar": {r: icerik_ozeti(r, v)[:16] for r, v in sorted(dosyalar.items())}},
            ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if dist_vardi:
            dist.rename(eski)
        try:
            yeni.rename(dist)
            _yer_degistir(bilgi_yeni, bilgi_yol)
        except OSError:
            if dist.exists() and not yeni.exists():   # yeni görüntü `dist`'e geçmişti → geri çek
                dist.rename(yeni)
            if dist_vardi:
                eski.rename(dist)
            raise
    except OSError as exc:
        exc.kalanlar = list(getattr(exc, "kalanlar", [])) + yollari_kaldir([yeni, bilgi_yeni])
        raise
    yollari_kaldir([eski])  # kalırsa zararsız: `anlik_oku` okumaz, sonraki `anlik_yaz` temizler
    return kok


def _yer_degistir(kaynak: Path, hedef: Path) -> None:
    """`os.replace` — testte takasın ikinci adımında hata benzetimi bu fonksiyon üzerinden yapılır."""
    os.replace(kaynak, hedef)


def anlik_oku(app: Path) -> tuple[dict, dict] | None:
    kok = app / ANLIK_KLASOR
    if not (kok / ANLIK_BILGI).is_file() or not (kok / "dist").is_dir():
        return None
    return klasor_oku(kok / "dist"), json.loads((kok / ANLIK_BILGI).read_text(encoding="utf-8"))


def ozet(k: dict, n: int = 6) -> str:
    parca = []
    for anahtar, etiket in (("farkli", "farklı"), ("yalniz_a", "yalnız-1"), ("yalniz_b", "yalnız-2"),
                            ("satir_sonu", "yalnız-satır-sonu")):
        if k[anahtar]:
            liste = ", ".join(k[anahtar][:n]) + (f" (+{len(k[anahtar]) - n})" if len(k[anahtar]) > n else "")
            parca.append(f"{etiket} {len(k[anahtar])}: {liste}")
    return f"eşit {len(k['esit'])}" + ("; " + "; ".join(parca) if parca else "")


def _deploy_haric(rel: str, desenler: list) -> bool:
    """ui5-deploy.yaml `configuration.exclude` — fiori deploy bunları REGEX olarak okur (yüklenmez)."""
    for d in desenler or []:
        try:
            if re.search(str(d), rel) or re.search(str(d), "/" + rel):
                return True
        except re.error:
            if str(d) in rel:
                return True
    return False


def drift_olc(app: Path, kimlik, sertifika_yok_say: bool = False, get=None) -> tuple[str, str, dict | None]:
    """Canlı, anlık görüntüden (`.canli/`) sonra değişti mi? → (durum, not, canlı dosyalar).
    durum: AYNI · DEGISTI · YOK (anlık görüntü yok — ölçülmedi) · OLCULEMEDI."""
    anlik = anlik_oku(app)
    if anlik is None:
        return "YOK", f"{ANLIK_KLASOR}/ anlık görüntüsü yok — drift ölçülmedi", None
    eski, _ = anlik
    ayar = B.deploy_ayari(app) or {}
    if not ayar.get("url") or not ayar.get("name"):
        return "OLCULEMEDI", "ui5-deploy.yaml'da target.url/app.name yok", None
    try:
        yeni, _, _ = canli_indir(ayar["url"], ayar.get("client", ""), ayar["name"], kimlik, sertifika_yok_say, get)
    except Exception as exc:  # noqa: BLE001 — ölçüm yok, "aynı" SAYILMAZ
        return "OLCULEMEDI", f"canlı indirilemedi: {exc}", None
    k = kume_karsilastir(eski, yeni)
    if kume_esit_mi(k):
        return "AYNI", f"canlı, anlık görüntüyle aynı ({len(k['esit'])} dosya)", yeni
    return "DEGISTI", (f"canlı, anlık görüntü alındıktan sonra DEĞİŞMİŞ (başkası deploy etmiş olabilir) — {ozet(k)} "
                       "(1=anlık görüntü, 2=şimdiki canlı)"), yeni


def tam_liste_olc(app: Path, ayar: dict, kimlik, sertifika_yok_say: bool = False, preload_karsilastir=None,
                  get=None) -> tuple[str, str, dict | None]:
    """Canlı BSP'nin TÜM dosyaları == yerel dist mi (deploy'un `exclude` regex'leriyle dışlananlar hariç)?
    → (durum, not, canlı dosyalar). durum: OK · STALE · OLCULEMEDI. Preload hash'i statik dosyaları kanıtlamaz."""
    dist_kok = Path(app) / "dist"
    if not dist_kok.is_dir():
        return "OLCULEMEDI", "dist/ yok", None
    try:
        canli, _, yol = canli_indir(ayar["url"], ayar.get("client", ""), ayar["name"], kimlik, sertifika_yok_say, get)
    except Exception as exc:  # noqa: BLE001
        return "OLCULEMEDI", f"canlı indirilemedi: {exc}", None
    dist = {r: v for r, v in klasor_oku(dist_kok).items() if not _deploy_haric(r, ayar.get("exclude", []))}
    k = kume_karsilastir(dist, canli, preload_karsilastir)
    if kume_esit_mi(k):
        return "OK", f"tam liste CANLI == dist ({len(k['esit'])} dosya, {yol})", canli
    return "STALE", f"tam liste canlı ≠ dist — {ozet(k)} (1=dist, 2=canlı)", canli


def metadata_tipleri(ham: bytes) -> dict:
    """OData V2/V4 `$metadata` → {EntityType adı: {Property adı: {öznitelikler}}} (ad alanından bağımsız).
    Alan doğrulaması TİP-KAPSAMLI yapılır: belge-geneli metin araması başka tipteki (ör. imza/yardımcı) aynı adlı
    alanı "var" diye sayar (yanlış pozitif)."""
    tipler: dict = {}
    for el in ET.fromstring(ham).iter():
        if el.tag.rsplit("}", 1)[-1] != "EntityType":
            continue
        alanlar = {}
        for p in el:
            if p.tag.rsplit("}", 1)[-1] == "Property":
                alanlar[p.get("Name", "")] = {k.rsplit("}", 1)[-1]: v for k, v in p.attrib.items() if k != "Name"}
        tipler[el.get("Name", "")] = alanlar
    return tipler
