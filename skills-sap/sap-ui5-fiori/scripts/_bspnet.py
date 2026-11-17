#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_bspnet.py — ABAP UI5 repository (BSP) erişimi + `ui5-deploy.yaml` okuma ORTAK yardımcıları (stdlib).

Tek başına çalıştırılmaz; `deploy_ui.py` ve `verify_ui_static_assets.py` içe aktarır.

KİMLİK SÖZLEŞMESİ:
  • Kimlik YALNIZ ortam değişkeninden okunur: FIORI_TOOLS_USER / FIORI_TOOLS_PASSWORD.
    Bunları geliştirici kendi kabuğunda set eder; script dosyadan kimlik OKUMAZ, CLI argümanı ALMAZ,
    parolayı hiçbir çıktıya BASMAZ.
  • Neden env: `fiori deploy` kimliği CLI argümanıyla alınca özel karakterli parola kabukta bozulur (401)
    ve parola loga düşer; env değişkeni doğrudan okunur.
  • Değerin sonundaki `\\r` atılır (CRLF'li bir dosyadan kopyalanan parola sessizce 401 üretir).

HEDEF SÖZLEŞMESİ:
  • Hedef sistem URL'i, client ve BSP adı uygulamanın kendi `ui5-deploy.yaml` dosyasından okunur
    (`deploy-to-abap` görevi → configuration.target / configuration.app). Script host UYDURMAZ.
  • TLS doğrulaması varsayılan AÇIK; yalnız `--ignore-cert` verilirse kapatılır (kurum içi self-signed sertifika).
"""
from __future__ import annotations

import base64
import hashlib
import os
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ENV_KULLANICI = "FIORI_TOOLS_USER"
ENV_PAROLA = "FIORI_TOOLS_PASSWORD"
PRELOAD = "Component-preload.js"
ZAMAN_ASIMI = 60

_KV = re.compile(r"^([A-Za-z0-9_.\-]+)\s*:(?:\s+(.*))?$")
FOUNDATION_SCRIPTS = Path(__file__).resolve().parents[2] / "sap-adt-foundation" / "scripts"


def ad_politikasi():
    """Müşteri ad alanı kararının TEK kaynağı: foundation `sapadt/lib/utils/ad_politikasi.py` (Z/Y · projede
    `sap-project.json` → `customer_namespaces` ile bildirilmiş `/<NS>/`). Burada desen YENİDEN YAZILMAZ.
    Yüklenemezse istisna yükselir — çağıran fail-closed davranır (adı reddeder)."""
    if str(FOUNDATION_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(FOUNDATION_SCRIPTS))
    import sapadt  # noqa: F401 — import anında `sapadt/lib/`i sys.path'e ekler
    from utils import ad_politikasi as pol
    return pol


def env_kimlik() -> tuple[str, str] | None:
    """(kullanıcı, parola) ya da None. Değerler BASILMAZ."""
    u = (os.environ.get(ENV_KULLANICI) or "").replace("\r", "").strip()
    p = (os.environ.get(ENV_PAROLA) or "").rstrip("\r\n")
    return (u, p) if u and p else None


def maskele(metin: str, kimlik: tuple[str, str] | None) -> str:
    """Çıktıya parola sızmışsa `***` ile değiştir (alt süreç çıktısı basılmadan önce)."""
    if kimlik and kimlik[1]:
        metin = metin.replace(kimlik[1], "***")
    return metin


# YAML'da TIRNAKSIZ bu değerler null'dur (PyYAML: None). Tırnaklı `'null'` / `"~"` dizedir, dokunulmaz.
YAML_NULL = frozenset({"null", "Null", "NULL", "~"})


def _temiz(v: str) -> str:
    """Tek skaler → dize. Null (tırnaksız null/Null/NULL/~) ve yalnız yorumdan oluşan değer (`# TODO ...`) → "".

    Z106 (2026-09-24, bug gate ölçümü): `transport: # TODO transport gir` "# TODO transport gir", `transport: null`
    "null", `transport: ~` "~" dönüyordu ⇒ boş olması gereken transport DOLU sayılıp deploy kapısından geçiyordu."""
    v = v.strip()
    if not v:
        return ""
    if v[:1] in "\"'":
        q = v[0]
        j = v.find(q, 1)
        return v[1:j] if j > 0 else v[1:]
    if v[:1] == "#":
        return ""
    v = re.split(r"\s+#", v, 1)[0].strip()
    return "" if v in YAML_NULL else v


def yaml_duzlestir(metin: str, yinelenen: set | None = None) -> tuple[dict, dict]:
    """ui5*.yaml için KÜÇÜK alt küme okuyucu → ({"a.b[0].c": skaler}, {"a.b": [liste öğeleri]}).

    Desteklenen: girintili eşleme, `- skaler` listesi, `- anahtar: değer` eşleme-listesi, tırnak, satır sonu yorumu,
    tırnaksız null (`null`/`Null`/`NULL`/`~`) ve yalnız-yorum değer (`# ...`) → boş (skaler yazılmaz).
    Desteklenmeyen (yok sayılır): anchor/alias, akış stili `{}`/`[]`, çok satırlı blok metin içeriği.
    Yinelenen anahtar: sonraki değer öncekini EZER (PyYAML gibi); `yinelenen` kümesi verilirse aynı skaler yolun
    İKİNCİ yazılışı oraya eklenir — çağıran fail-closed karar verebilsin diye (`deploy_ayari`).
    """
    yigin: list[tuple[int, str]] = []
    skaler: dict[str, str] = {}
    listeler: dict[str, list[str]] = {}
    sayac: dict[str, int] = {}

    def yol(ekler: list[str]) -> str:
        s = ""
        for seg in [x for _, x in yigin] + ekler:
            s += seg if seg.startswith("[") else ("." + seg if s else seg)
        return s

    def kv(ind: int, anahtar: str, deger: str | None) -> None:
        d = (deger or "").strip()
        # Değer yok / blok metin / tırnaksız null ya da yalnız yorum (`app:  # açıklama`) → alt eşleme olabilir:
        # yığına it (alt anahtar yoksa bir sonraki kardeş satır onu çıkarır; skaler YAZILMAZ = boş).
        if not d or d[:1] in "|>" or (d[:1] not in "\"'" and not _temiz(d)):
            yigin.append((ind, anahtar))
        else:
            y = yol([anahtar])
            if yinelenen is not None and y in skaler:
                yinelenen.add(y)
            skaler[y] = _temiz(deger)

    for ham in metin.splitlines():
        satir = ham.rstrip()
        govde = satir.lstrip()
        if not govde or govde.startswith("#"):
            continue
        ind = len(satir) - len(govde)
        if govde == "-" or govde.startswith("- "):
            while yigin and yigin[-1][0] > ind:
                yigin.pop()
            if yigin and yigin[-1][0] == ind and yigin[-1][1].startswith("["):
                yigin.pop()
            ust = yol([])
            ic = govde[1:].strip()
            m = _KV.match(ic)
            if m and ic[:1] not in "/\"'":
                i = sayac.get(ust, 0)
                sayac[ust] = i + 1
                yigin.append((ind, f"[{i}]"))
                kv(ind + (len(govde) - len(ic)), m.group(1), m.group(2))
            elif ic and (ic[:1] in "\"'" or _temiz(ic)):  # null / yalnız-yorum liste öğesi eklenmez
                listeler.setdefault(ust, []).append(_temiz(ic))
            continue
        while yigin and yigin[-1][0] >= ind:
            yigin.pop()
        m = _KV.match(govde)
        if m:
            kv(ind, m.group(1), m.group(2))
    return skaler, listeler


def deploy_ayari(app_dir: Path) -> dict | None:
    """`ui5-deploy.yaml` → deploy ayarı sözlüğü. Dosya yoksa None; `gorev=False` = deploy-to-abap görevi yok."""
    y = Path(app_dir) / "ui5-deploy.yaml"
    if not y.is_file():
        return None
    yinelenen: set = set()
    sk, ls = yaml_duzlestir(y.read_text(encoding="utf-8-sig", errors="replace"), yinelenen)
    sonuc = {"gorev": False, "resources_excludes": ls.get("builder.resources.excludes", []), "yinelenen": []}
    for i in range(50):
        if sk.get(f"builder.customTasks[{i}].name") == "deploy-to-abap":
            c = f"builder.customTasks[{i}].configuration"
            sonuc.update({
                "gorev": True,
                "url": sk.get(c + ".target.url", ""),
                "client": sk.get(c + ".target.client", ""),
                "name": sk.get(c + ".app.name", ""),
                "description": sk.get(c + ".app.description", ""),
                "package": sk.get(c + ".app.package", ""),
                "transport": sk.get(c + ".app.transport", ""),
                "exclude": ls.get(c + ".exclude", []),
                # Görev bloğunda (ya da görev adında) yinelenen anahtar: hangi değerin geçerli olduğu belirsiz ⇒
                # `deploy_ui` bunu İHLAL sayar (fail-closed; fiori aracının hangisini okuduğu ölçülmedi).
                "yinelenen": sorted(k for k in yinelenen
                                    if k.startswith(c + ".") or k == f"builder.customTasks[{i}].name"),
            })
            break
    return sonuc


def satir_sonu_normalize(b: bytes) -> bytes:
    """GERÇEK CR/LF baytlarını LF'e indirir (BSP dosyayı CRLF saklayabilir, dist LF'tir)."""
    return b.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def sha(b: bytes) -> str:
    return hashlib.sha256(satir_sonu_normalize(b)).hexdigest()


def bsp_icf_yolu(bsp: str) -> str:
    """Canlı BSP'nin ICF yolu (`/` ile biter) — canlı dosya URL'lerinin (`bsp_url`: deploy doğrulaması + statik
    varlık doğrulaması) TEK kaynağı.

    · Z/Y: `/sap/bc/ui5_ui5/sap/<bsp>/` (önceki tek yol, aynen).
    · `/NS/APP`: `/sap/bc/ui5_ui5/<ns>/<app>/` — `sap` düğümünün KARDEŞİ olan namespace düğümü.
      ⚠ Bu yol kaynak çekirdekte tek bir tüketici sisteminde (ilk deploy) ölçüldü; aXet'te namespace'li gerçek
      bir BSP'ye istek ÖLÇÜLMEDİ.
    · Eğik çizgili ama namespace biçimine (`/<3-8>/`) uymayan ad → ValueError: `sap` düğümüne düşürmek
      `…/sap//x/app/` gibi sahte bir yol kurar ve 404 "BSP yok" diye okunur (sessiz yanlış teşhis). Fail-closed.
    Bildirilmişliğe BAKMAZ (yol kurar; müşteri adı kararı `ad_politikasi.musteri_adi_mi`'dedir)."""
    ad = str(bsp or "").strip()
    if "/" not in ad:
        return f"/sap/bc/ui5_ui5/sap/{ad.lower()}/"
    ns = ad_politikasi().ad_namespace(ad)
    govde = ad[len(ns):] if ns else ""
    if not ns or not govde or "/" in govde:
        raise ValueError(f"BSP adı ICF yoluna çevrilemez (namespace biçimi /<3-8>/<AD> değil): {bsp!r}")
    return f"/sap/bc/ui5_ui5/{ns.strip('/').lower()}/{govde.lower()}/"


def bsp_url(ayar: dict, rel: str) -> str:
    """Canlı BSP dosya URL'i (cache-bust parametreli). Yol `bsp_icf_yolu`'ndan (namespace dalı dahil)."""
    q = f"cb={int(time.time() * 1000)}"
    if ayar.get("client"):
        q = f"sap-client={ayar['client']}&" + q
    return f"{ayar['url'].rstrip('/')}{bsp_icf_yolu(ayar['name'])}{rel}?{q}"


def _koken(url: str) -> tuple:
    u = urllib.parse.urlsplit(url)
    try:
        port = u.port
    except ValueError:
        port = u.netloc
    return u.scheme.lower(), (u.hostname or "").lower(), port or {"http": 80, "https": 443}.get(u.scheme.lower())


class _KimlikKoruyanYonlendirme(urllib.request.HTTPRedirectHandler):
    """urllib Basic `Authorization`'ı yönlendirmede başka hosta da taşır (ölçüldü: 127.0.0.1 → 127.0.0.2 302).
    Köken (şema + host + port) değişirse başlık düşürülür — `requests` ile aynı ilke; kimlik başka sisteme gitmez."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        yeni = super().redirect_request(req, fp, code, msg, headers, newurl)
        if yeni is not None and _koken(req.full_url) != _koken(yeni.full_url):
            yeni.remove_header("Authorization")
        return yeni


def http_get(url: str, kimlik: tuple[str, str] | None, sertifika_yok_say: bool = False,
             zaman: int = ZAMAN_ASIMI) -> bytes:
    """Salt-okuma GET: no-cache + identity encoding + (varsa) Basic auth. Hata istisna olarak döner."""
    basliklar = {"Cache-Control": "no-cache", "Pragma": "no-cache", "Accept-Encoding": "identity"}
    if kimlik:
        basliklar["Authorization"] = "Basic " + base64.b64encode(f"{kimlik[0]}:{kimlik[1]}".encode()).decode()
    ctx = None
    if url.lower().startswith("https"):
        ctx = ssl.create_default_context()
        if sertifika_yok_say:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers=basliklar)
    isleyiciler = [_KimlikKoruyanYonlendirme()] + ([urllib.request.HTTPSHandler(context=ctx)] if ctx else [])
    with urllib.request.build_opener(*isleyiciler).open(req, timeout=zaman) as r:
        return r.read()
