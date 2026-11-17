# -*- coding: utf-8 -*-
"""ad_politikasi — "bu SAP adı MÜŞTERİNİN mi?" kararının TEK KAYNAĞI (ADR 0005-A, A-EK).

NEDEN VAR
  ADR 0005-A standart nesneye yazmayı yasaklar. Eski uygulama "müşteri adı" = Z/Y önekli ad diyordu ve
  bu karar birkaç dosyada ayrı ayrı (`^[ZY]…`, `startswith(('Z','Y'))`) yazılıydı. Müşteriye KAYITLI bir
  namespace (`/<NS>/`, SE03 kaydı + geliştirici lisansı) Z/Y kadar meşru müşteri ad alanıdır; SAP'nin kendi
  namespace'leri (`/SCWM/` …) standarttır. Ayrım "önek Z/Y mi" değil "ad alanı müşteriye mi ait" sorusudur ⇒
  kayıtlı namespace'ler PROJEDEN okunur: proje kökündeki `sap-project.json` → `"customer_namespaces": ["/<NS>/"]`.

KARAR (`musteri_adi_mi`)
  müşteri adı ⇔  `^[ZY][A-Z0-9_]*\\Z`
             ∨  kilit nesnesi (ENQU) ise `^E[ZY][A-Z0-9_]*\\Z`   (SAP: kilit nesnesi E ile başlar)
             ∨  `^<bildirilmiş NS>[A-Z0-9_]+\\Z`                   (kilit nesnesi DAHİL; `E/<NS>/…` tanınmaz)
  Büyük/küçük harf duyarsız. `\\Z` (`$` DEĞİL): `$` sondaki tek `\\n`'i kabul eder.

YAPILANDIRMA (`namespace_yapilandirmasi`) — FAIL-CLOSED
  · anahtar yok / boş liste ⇒ () ⇒ bugünkü Z/Y davranışı BİREBİR.
  · `sap-project.json` okunamıyor · JSON değil · anahtar dosyada BİRDEN ÇOK kez yazılı (JSON ayrıştırıcısı
    sessizce sonuncuyu alırdı) · değer liste değil · bir öğe ASCII `^/[A-Z0-9_]{3,8}/\\Z` değil (en az bir
    harf/rakam; `/___/` RED) ⇒ HATA listesi döner ve TÜM liste devre dışı kalır (kısmen geçerli liste yarı açık
    kapıdır). Hata sessiz düşmez: `red_gerekcesi` metnine girer.
  · HANGİ proje: istemcinin bağlanacağı `.conn_adt`'nin dizini (yükleyici `sap_adt_lib` süreçte yüklüyse onun
    `get_conn_path()`'i; değilse AYNI kural: env `AXET_SAP_PROJECT_DIR` → cwd). Yazma hangi sisteme gidiyorsa izin
    listesi o projeden gelir. Açık `root` verilir ve bağlantı dizininden farklıysa ⇒ namespace kabulü KAPALI.
    `.conn_adt` dosyası YOKSA da KAPALI (listenin hangi bağlantıya ait olduğu bilinemez). Z/Y kabulü etkilenmez.
  · Ortam değişkeniyle liste genişletme YOK (bilerek): komutun önüne değişken koyarak izin listesini açmak
    kapıyı aşmanın en kısa yolu olurdu.
  · Önbellek: dosyanın (mtime, boyut)'u değişince yeniden okunur.
  · ⚠ SINIR: hangi namespace'in SAP'ye ait olduğu burada bilinmez ⇒ `["/SCWM/"]` gibi yanlış bir bildirim
    YAKALANAMAZ. Bildirim kullanıcı beyanıdır; yanlış bildirim ADR 0005-A ihlalidir (A-EK).

FONKSİYON GRUBU ADLARI: `ZFG` → include `LZFG…`, ana program `SAPLZFG` · `/NSPC/FG` → `/NSPC/LFG…`, `/NSPC/SAPLFG`.

ADT YOL PARÇASI (`url_segmenti`): `/NS/X` → `%2Fns%2Fx` (kodlamasız `//ns/x` → SAP 404). Z/Y adında çıktı eski
  `ad.lower()` ile bayt bayt aynıdır. İdempotent: önce `unquote` ⇒ zaten kodlanmış ad çift kodlanmaz.

YEREL DOSYA ADI (`dosya_adi` yazma · `dosya_adindan_ad` okuma): `/NSPC/X` ↔ `#nspc#x` (abapGit). Dosya adında `/`
  OLAMAZ: `Path(kok) / "/nspc/x.abap"` sürücü köküne kaçar.

KAYNAK METİNDE AD YAKALAMA — TEK AD GRAMERİ
  Validator'lar adı kaynak metinden kendi desenleriyle (`(\\w+)` …) yakalarsa `\\w` `/` eşlemediği için
  namespace'li ad hiç yakalanmaz ve kontrol KOŞMADAN "kapsam dışı / OK" döner. İki katman:
  · `AD_ADAYI`  — GEVŞEK yakalama: `/` ile başlayan her belirteci tutar (şekli bozuk deneme sessizce düşmesin).
  · `AD_DESENI` — KATI geçerlilik: `(?:/<3-8>/)?<gövde>`, A-Z 0-9 _ (ASCII).
  `ad_coz(aday)` katıya uyan adı döner, uymayan → ('', 'ad-cozulemedi') ⇒ çağıran ÖLÇÜLEMEDİ basar ("OK" değil).
  Yakalama ≠ karar: "müşterinin mi" kararı `musteri_karari` / `musteri_adi_mi`'dedir.

Bu modül `sapadt` paketini import ETMEZ (validator'lar ayrı süreçte yalnız `lib/`i yol'a ekler).
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote as _quote, unquote as _unquote

ANAHTAR = "customer_namespaces"
PROJE_DOSYASI = "sap-project.json"
BAGLANTI_DOSYASI = ".conn_adt"
PROJE_ENV = "AXET_SAP_PROJECT_DIR"


# ── ADT URL yol parçası ──────────────────────────────────────────────────────────────────────
def url_segmenti(ad) -> str:
    """ADT URL'inin TEK yol parçası (nesne adı → URL'e yazılacak biçim).

    `ZSD001_T01` → `zsd001_t01` (eski `ad.lower()` ile bayt bayt aynı) · `/NS/X` → `%2Fns%2Fx`.
    Küçük harfe çevirir; `/` dahil tüm özel karakterleri kodlar (`quote(safe='')`, büyük harfli kaçış).
    İdempotent: girdi önce `unquote` edilir ⇒ `%2Fns%2Fx` yeniden verilirse `%252F` olmaz.
    Müşteri kararı VERMEZ (önce `musteri_adi_mi`). Tersi: `url_parcasindan_ad`.
    """
    return _quote(_unquote(str(ad)).lower(), safe="")


def url_parcasindan_ad(parca) -> str:
    """`url_segmenti`'nin tersi: `%2Fns%2Fx` / `%2fns%2fx` → `/NS/X` (büyük harf)."""
    return _unquote(str(parca)).upper()


def url_adi(object_url) -> str:
    """ADT nesne URL'inin AD parçası (sorgu/parça + `/source/main` · `/source` kuyruğu atılır), çözülmüş:
    `…/classes/%2fns%2fcl_x/source/main` → `/NS/CL_X`. Çözülemezse ''."""
    yol = str(object_url or "").split("?")[0].split("#")[0].rstrip("/")
    for kuyruk in ("/source/main", "/source"):
        if yol.lower().endswith(kuyruk):
            yol = yol[: -len(kuyruk)].rstrip("/")
    ad = yol.rsplit("/", 1)[-1].strip()
    return url_parcasindan_ad(ad) if ad else ""


_ZY = re.compile(r"^[ZY][A-Z0-9_]*\Z", re.IGNORECASE)
_KILIT_ZY = re.compile(r"^E[ZY][A-Z0-9_]*\Z", re.IGNORECASE)
# Namespace gövdesi — TEK sabit: yapılandırma (`_NS_BICIM`), ad içinden ayırma (`_AD_NS`) ve metinden yakalama
# (`AD_DESENI`) buradan türer. İç kısım 3-8 karakter (SAP: namespace `/` dahil 5-10; abaplint `{3,8}`).
NS_GOVDE = r"[A-Za-z0-9_]{3,8}"
_NS_BICIM = re.compile(r"^/(?=[A-Z0-9_]*[A-Z0-9])" + NS_GOVDE + r"/\Z")  # `/___/` RED: en az bir harf/rakam
_AD_NS = re.compile(r"^(/" + NS_GOVDE + r"/)")
KILIT_TIPLERI = frozenset({"enqu", "lock", "lockobject", "lockobjects"})


# ── Proje kökü + bağlantı dizini ────────────────────────────────────────────────────────────
def _proje_koku_env() -> Path:
    env = os.environ.get(PROJE_ENV)
    return (Path(env) if env else Path.cwd()).resolve()


def _baglanti_dosyasi() -> Path | None:
    """İstemcinin kullanacağı `.conn_adt` yolu (var olmayabilir). Yükleyici süreçte yüklüyse ONUN yolu
    (açık çalışma dizini dahil); değilse yükleyicinin `find_conn_file` kuralı: env → cwd."""
    lib = sys.modules.get("sap_adt_lib")
    if lib is not None and hasattr(lib, "get_conn_path"):
        try:
            p = lib.get_conn_path()
        except Exception:  # noqa: BLE001
            return None
        return Path(p) if p else None
    return _proje_koku_env() / BAGLANTI_DOSYASI


def _kok_coz(root) -> tuple[Path | None, str | None]:
    """(kök, hata). Kök = bağlantı dosyasının dizini; dosya yoksa ya da verilen `root` ondan ayrışırsa hata
    (namespace kabulü KAPALI — fail-closed)."""
    p = _baglanti_dosyasi()
    if p is None or not p.is_file():
        return None, (f"{ANAHTAR}: bağlantı dosyası ({BAGLANTI_DOSYASI}) proje kökünde yok — liste hangi "
                      f"bağlantıya ait belirsiz, namespace kabulü KAPALI")
    baglanti = p.parent.resolve()
    if root and Path(root).resolve() != baglanti:
        return None, (f"{ANAHTAR}: proje kökü ({Path(root).resolve()}) bağlantı dosyasının dizininden "
                      f"({baglanti}) farklı — namespace kabulü KAPALI")
    return baglanti, None


_ONBELLEK: dict = {}


def _proje_oku(yol: Path) -> tuple[dict, int]:
    """(ayrıştırılmış sap-project.json, `customer_namespaces` anahtarının KÖK düzeyde kaç kez yazıldığı).

    Dosya yoksa ({}, 0). JSON değil / kök nesne değil ⇒ ValueError. Önbellek anahtarı (mtime_ns, boyut)."""
    try:
        st = os.stat(yol)
    except OSError:
        return {}, 0
    anahtar = (st.st_mtime_ns, st.st_size)
    kayit = _ONBELLEK.get(str(yol))
    if kayit is not None and kayit[0] == anahtar:
        return kayit[1], kayit[2]
    sayac = {"n": 0}

    def _kanca(ciftler):
        # object_pairs_hook İÇTEN DIŞA çağrılır; kök nesne EN SON gelir ⇒ sonda kalan sayı kökün sayısıdır.
        sayac["n"] = sum(1 for k, _ in ciftler if k == ANAHTAR)
        return dict(ciftler)

    veri = json.loads(Path(yol).read_text(encoding="utf-8-sig"), object_pairs_hook=_kanca)
    if not isinstance(veri, dict):
        raise ValueError("kök bir JSON nesnesi değil")
    _ONBELLEK[str(yol)] = (anahtar, veri, sayac["n"])
    return veri, sayac["n"]


def namespace_yapilandirmasi(root=None) -> tuple[tuple[str, ...], list[str]]:
    """`sap-project.json` → (geçerli namespace'ler, hatalar). Hata varsa namespace'ler BOŞTUR (fail-closed)."""
    try:
        kok, kok_hatasi = _kok_coz(root)
        if kok_hatasi:
            return (), [kok_hatasi]
        veri, tekrar = _proje_oku(kok / PROJE_DOSYASI)
        ham = veri.get(ANAHTAR)
    except Exception as exc:  # noqa: BLE001 — okunamayan yapılandırma = namespace YOK
        return (), [f"{ANAHTAR} okunamadı ({type(exc).__name__}) — yalnız Z/Y geçerli"]
    if tekrar > 1:
        return (), [f"{ANAHTAR} {PROJE_DOSYASI}'da {tekrar} kez tanımlı — hangisinin geçerli olduğu belirsiz, "
                    f"namespace kabulü KAPALI"]
    if ham is None:
        return (), []
    if not isinstance(ham, list):
        return (), [f"{ANAHTAR} bir LİSTE olmalı (örn. \"{ANAHTAR}\": [\"/<NS>/\"]); verilen: {ham!r} — "
                    f"namespace kabulü KAPALI"]
    gecerli: list[str] = []
    hatalar: list[str] = []
    for oge in ham:
        s = str(oge).upper()
        if not isinstance(oge, str) or not oge.isascii() or not _NS_BICIM.match(s):
            hatalar.append(f"{ANAHTAR} öğesi geçersiz: {oge!r} (beklenen biçim /<NS>/, A-Z 0-9 _, 3-8 karakter)")
        elif s not in gecerli:
            gecerli.append(s)
    if hatalar:
        return (), hatalar + [f"{ANAHTAR} hatalı olduğu için namespace kabulü KAPALI (yalnız Z/Y geçerli)"]
    return tuple(gecerli), []


def musteri_namespaceleri(root=None) -> tuple[str, ...]:
    return namespace_yapilandirmasi(root)[0]


def ad_namespace(ad: str) -> str | None:
    """`/NSPC/CL_X` → `/NSPC/` (büyük harf); namespace'siz ad → None. Bildirilmişliğe BAKMAZ."""
    m = _AD_NS.match(ad or "")
    return m.group(1).upper() if m else None


def _kayitli(namespaces, root) -> tuple[str, ...]:
    if namespaces is None:
        return musteri_namespaceleri(root)
    return tuple(str(n).upper() for n in namespaces)


def musteri_adi_mi(ad: str, object_type: str | None = None, *, namespaces=None, root=None) -> bool:
    """ADR 0005-A: ad müşteri ad alanında mı? (`namespaces` verilmezse projeden okunur, fail-closed)."""
    if not ad or not isinstance(ad, str):
        return False
    if _ZY.match(ad):
        return True
    if object_type and str(object_type).lower() in KILIT_TIPLERI and _KILIT_ZY.match(ad):
        return True
    ns = ad_namespace(ad)
    if ns is None:
        return False
    if ns not in _kayitli(namespaces, root):
        return False
    # re.ASCII: `[A-Z]` Unicode harf kabul ETMEZ ('ı'/'ſ'/'K' IGNORECASE'te I/S/K'ye eşlenip sızardı).
    return re.match(r"^" + re.escape(ns) + r"[A-Z0-9_]+\Z", ad, re.IGNORECASE | re.ASCII) is not None


def red_gerekcesi(ad: str, *, root=None) -> str:
    """Red metnine eklenecek NAMESPACE ayrıntısı ('' = ekleyecek bir şey yok)."""
    ad = ad if isinstance(ad, str) else ""
    ns = ad_namespace(ad)
    if ns is None and not ad.startswith("/"):
        return ""
    kayitli, hatalar = namespace_yapilandirmasi(root)
    if hatalar:
        return " · " + " · ".join(hatalar)
    if ns is None:
        return " · namespace biçimi tanınmadı (/<NS>/<AD>, NS 3-8 karakter)"
    if ns not in kayitli:
        return (f" · namespace {ns} projede {PROJE_DOSYASI} `{ANAHTAR}` ile müşteri namespace'i olarak "
                f"bildirilmemiş (SAP namespace'leri standarttır)")
    return f" · {ns} bildirilmiş, ama namespace'ten sonraki ad geçersiz (A-Z 0-9 _, boş olamaz)"


_SURUCU_YOLU = re.compile(r"^[A-Za-z]:[/\\]")


def musteri_adi_red_metni(ad, *, root=None) -> str:
    """Komut satırı araçlarının ortak red metni (karar `musteri_adi_mi`'de, metin TEK yerde)."""
    a = "" if ad is None else str(ad)
    ipucu = ""
    if _SURUCU_YOLU.match(a):
        ipucu = (" · ad bir Windows yoluna dönüşmüş görünüyor: Git Bash `/` ile başlayan argümanı yol sanıp "
                 "çevirir — komutun önüne MSYS_NO_PATHCONV=1 koy")
    return (f"yalnız müşteri ad alanı (Z/Y ya da bildirilmiş /<NS>/). Verilen: {a}"
            f"{red_gerekcesi(a, root=root)}{ipucu}")


# ── KAYNAK METİNDE AD YAKALAMA — TEK AD GRAMERİ ──────────────────────────────────────────────
AD_DESENI = r"(?a:(?:/" + NS_GOVDE + r"/)?[A-Za-z0-9_]+)"
_AD_DURAK = r"\s{}\[\]();,.:'\"<>=|`\-"
AD_ADAYI = r"(?a:/[^" + _AD_DURAK + r"]*|[A-Za-z0-9_]+)"
_AD_TAM = re.compile(r"\A" + AD_DESENI + r"\Z", re.IGNORECASE)
_AD_SINIR_ONCE = r"(?<![A-Za-z0-9_/])"
_AD_SINIR_SONRA = r"(?![A-Za-z0-9_/])"


def ad_gecerli_mi(ad) -> bool:
    """Ad katı gramere TAM uyuyor mu (`/NSPC/X` · `ZSD001_X` → True; `/AB/X` · `/NSPC/` · `` → False)."""
    return bool(ad) and _AD_TAM.match(str(ad)) is not None


def ad_coz(aday) -> tuple[str, str | None]:
    """(ad, None) ya da ('', 'ad-cozulemedi'). Harf DEĞİŞTİRİLMEZ (çağıran karar verir)."""
    a = "" if aday is None else str(aday)
    return (a, None) if ad_gecerli_mi(a) else ("", "ad-cozulemedi")


def ad_gecis_deseni(ad: str) -> str:
    """Metinde `ad`ın TAM geçişini arayan desen. `\\b` namespace'li adda `/` önünde tutmaz; sınır
    `[A-Za-z0-9_/]` dışıdır (`ZSD001_X` `ZSD001_X_Y` içinde bulunmaz)."""
    return _AD_SINIR_ONCE + re.escape(ad) + _AD_SINIR_SONRA


def musteri_karari(ad, object_type: str | None = None, *, namespaces=None, root=None) -> str:
    """'musteri' · 'standart' · 'namespace-kayitsiz' · 'ad-cozulemedi'.

    'namespace-kayitsiz' = katı gramere uyan namespace'li ad ama namespace projede bildirilmemiş (ya da
    yapılandırma hatalı ⇒ liste kapalı): müşterinin bildirmediği kendi namespace'i mi, SAP'nin mi — BİLİNEMEZ."""
    a = "" if ad is None else str(ad)
    if not ad_gecerli_mi(a):
        return "ad-cozulemedi"
    if musteri_adi_mi(a, object_type, namespaces=namespaces, root=root):
        return "musteri"
    return "namespace-kayitsiz" if a.startswith("/") else "standart"


# ── Yerel dosya adı ↔ SAP adı ────────────────────────────────────────────────────────────────
def dosya_adindan_ad(parca) -> str:
    """Yerel dosya adının nesne-adı parçası → SAP adı (OKUMA yönü). abapGit `#ns#x` · URL-kodlu `%23ns%23x` ·
    AFF `(ns)x` → `/NS/X`; namespace'siz ad büyük harfe çevrilir. Biçim doğrulaması YAPMAZ (`ad_coz`'a ver)."""
    s = _unquote(str(parca or ""))
    m = re.match(r"^#([^#]*)#(.*)\Z", s, re.S) or re.match(r"^\(([^()]*)\)(.*)\Z", s, re.S)
    if m:
        s = "/" + m.group(1) + "/" + m.group(2)
    return s.upper()


def dosya_adi(ad) -> str:
    """SAP adı → yerel dosya adının nesne-adı parçası (YAZMA yönü; tersi `dosya_adindan_ad`).
    `/NSPC/X` → `#nspc#x` (abapGit) · `ZX` → `zx`. Müşteri kararı VERMEZ; dönüşümden sonra `/` ya da `\\` kalırsa
    ValueError (dosya adı yol ayıracı taşıyamaz)."""
    a = str(ad or "").strip().upper()
    ns = ad_namespace(a)
    if ns:
        a = "#" + ns[1:-1] + "#" + a[len(ns):]
    if "/" in a or "\\" in a:
        raise ValueError(f"dosya adına çevrilemez (yol ayıracı kalıyor): {ad!r}")
    return a.lower()


def yerel_ad(ad) -> str:
    """"Dosya adı = SAP adı" yazan araçların YAZMA yönü: namespace'siz ad AYNEN döner (harf DEĞİŞMEZ) ·
    `/NSPC/X` → `dosya_adi` (`#nspc#x`). `/` ile başlayıp namespace biçimine uymayan ad ya da gövdede yol
    ayıracı ⇒ ValueError (`Path(kok) / "/NSPC/X.abap"` sürücü köküne kaçardı)."""
    a = str(ad or "").strip()
    if "/" in a or "\\" in a:
        return dosya_adi(a)
    return a


def musteri_govdesi(ad, *, namespaces=None, root=None) -> tuple[str, str] | None:
    """(önek, gövde): `ZSD001_CLC` → ('Z', 'SD001_CLC') · `YSD001` → ('Y', 'SD001') · `/NSPC/SD001_CLC` →
    ('/NSPC/', 'SD001_CLC') YALNIZ namespace projede bildirilmişse; aksi None. Z/Y adında yapılandırma OKUNMAZ."""
    a = str(ad or "").strip().upper()
    if a[:1] in ("Z", "Y"):
        return a[:1], a[1:]
    ns = ad_namespace(a)
    if ns is None:
        return None
    return (ns, a[len(ns):]) if ns in _kayitli(namespaces, root) else None


# ── OData V2 servis kökü ─────────────────────────────────────────────────────────────────────
# Gateway ICF ağacında namespace düğümleri `…/sap/opu/odata/` altında `sap` düğümünün KARDEŞİDİR ⇒ `/<NS>/<AD>`
# servisinin kökü `/sap/opu/odata/<ns>/<AD>`'dir. ⚠ Namespace'li gerçek bir müşteri servisine istek ÖLÇÜLMEDİ
# (kaynak çekirdekte yol kayıttan ve ICF ağacından türetildi). Z/Y servisinde çıktı eski yolla aynıdır.
ODATA_KOK = "/sap/opu/odata"
_ODATA_URI = re.compile(r"^/sap/opu/odata/([^/\"?]+)/([^/\"?]+)/?\Z", re.IGNORECASE)


def odata_servis_yolu(servis) -> str:
    """`ZSD001_SRV` → `/sap/opu/odata/sap/ZSD001_SRV` · `/NSPC/X_SRV` → `/sap/opu/odata/nspc/X_SRV`."""
    s = str(servis or "").strip()
    ns = ad_namespace(s)
    if ns:
        return f"{ODATA_KOK}/{ns[1:-1].lower()}/{s[len(ns):]}"
    return f"{ODATA_KOK}/sap/{s}"


def odata_uri_servisi(uri) -> str | None:
    """`odata_servis_yolu`'nun tersi: `…/sap/<AD>/` → `<AD>` · `…/<ns>/<AD>/` → `/NS/<AD>`; aksi None."""
    m = _ODATA_URI.match(str(uri or ""))
    if not m:
        return None
    seg, ad = m.group(1), m.group(2)
    if seg.lower() == "sap":
        return ad
    ns = "/" + seg.upper() + "/"
    return ns + ad if _NS_BICIM.match(ns) else None


# ── Fonksiyon grubu adları ───────────────────────────────────────────────────────────────────
def fugr_include_oneki(grup: str) -> str:
    """Grubun include öneki: `ZFG` → `LZFG` · `/NSPC/FG` → `/NSPC/LFG`."""
    g = (grup or "").strip().upper()
    ns = ad_namespace(g)
    return ns + "L" + g[len(ns):] if ns else "L" + g


def fugr_ana_program(grup: str) -> str:
    """Grubun ana programı: `ZFG` → `SAPLZFG` · `/NSPC/FG` → `/NSPC/SAPLFG`."""
    g = (grup or "").strip().upper()
    ns = ad_namespace(g)
    return ns + "SAPL" + g[len(ns):] if ns else "SAPL" + g
