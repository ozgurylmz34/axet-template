# -*- coding: utf-8 -*-
"""Tanı / okuma araçları (aXet 2026-09-13) — HEPSİ OKUMA sınıfı (`gate.READ_TOOLS`).

  adt_revisions         obje sürüm geçmişi (versions feed)
  adt_system_info       ADT discovery servis kataloğu (bağlantı kimliği ÇIKTIYA KONMAZ)
  adt_object_structure  obje yapısı (objectstructure bileşenleri)
  sap_doctor            tek komutluk yerel + canlı bağlantı tanısı (PASS/WARN/FAIL + kapsam beyanı)
  adt_pretty_print      SAP Pretty Printer ile biçimlenmiş kaynak → yanıt / YEREL dosya; SAP'de değişiklik YOK (Z128)
  adt_get_method        sınıfın ana kaynağından TEK metot gövdesi → yanıt / YEREL dosya; yalnız GET (Z195)

KANIT (kaynak çekirdek salt-okur; aXet kütüphane kopyası `sapadt/lib/`):
  · sürümler: `lib/sap_adt_lib.py get_object_revisions` — obje GET → `rel="http://www.sap.com/adt/relations/versions"`
    bağlantısı → feed GET Accept `application/atom+xml;type=feed` → `<atom:entry>` ayrıştırma. Kaynak script
    `scripts/list_revisions.py:83` bu metodu çağırır, varsayılan `--limit 20` (`:40`).
    ⛔ Z132 (2026-09-25, canlı ölçüm, DEV): obje GET'i `Accept: objectstructure+xml` ile sınıf/include/arayüzde 406
    veriyordu (araç bu üç tipte sürüm OKUYAMIYORDU); bağlantı `<atom:link …>` ve href GÖRELİ; sınıfta ilk bağlantı
    `includes/definitions`, ana kaynak `includes/main/versions`. Accept, bağlantı bulma/seçme/çözme artık
    kütüphanedeki TEK kaynaktan gelir (`REVISIONS_OBJECT_ACCEPT`, `versions_links`, `select_versions_link`,
    `resolve_adt_href`). Kütüphane metodu da artık hatayı yutmaz; araç iki GET'i kendisi yapıp durumları kodla ayırır.
  · yapı: `lib/sap_adt_lib.py:4366-4400 get_object_structure` (406/415'te sıradaki Accept) +
    bileşen ayrıştırma `lib/sap_client.py:3311-3326 get_structure` (kaynak script `get_object_structure.py:45`).
    `sap_client.get_structure` istisnayı yutup None döndürdüğü için doğrudan kütüphane metodu çağrılır.
  · sistem bilgisi: `lib/sap_adt_lib.py:6791-6845 get_system_info` (kaynak script `get_system_info.py:41`).
    Metot bağlantı URL'si, client, kullanıcı ve sistem kimliği de toplar — bunlar ÇIKTIYA KONMAZ (allowlist).
  · doctor: kaynak `scripts/sap_doctor.py:9-15` katmanları, `:84-91` tier eşlemesi, `:93-98` dil uyarısı,
    `:124-163` "doğrulama koşamadı = doğrulandı" dersi. Canlı katman: `lib/sap_adt_lib.py:1638 check_logon`
    + `:1482 fetch_csrf_token`. Kaynaktan BİLİNÇLİ fark: URL/client/kullanıcı BASILMAZ (kaynak `:75` basıyordu);
    probe objesi/paket katmanı YOK (aXet `sap-project.json`da probe alanı yok) — kapsam beyanında yazılı.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from xml.sax.saxutils import unescape as _xml_unescape

from sapadt._app import profil_tool

_ENTRY = re.compile(r"<atom:entry>(.*?)</atom:entry>", re.DOTALL)       # sap_adt_lib.py:1881
_E_URI = re.compile(r'<atom:content[^>]*src="([^"]+)"')
_E_VER_TR = re.compile(r'<atom:link[^>]*type="application/vnd\.sap\.adt\.transportrequests\.v1\+xml"[^>]*adtcore:name="([^"]+)"')
_E_VER = re.compile(r'<atom:link[^>]*adtcore:name="([^"]+)"')
_E_TITLE = re.compile(r"<atom:title>([^<]+)</atom:title>")
_E_DATE = re.compile(r"<atom:updated>([^<]+)</atom:updated>")
_E_AUTHOR = re.compile(r"<atom:name>([^<]+)</atom:name>")
_NS_AC = "http://www.sap.com/adt/core"


def _temizle(resp: dict, adt) -> dict:
    from sapadt import redact
    from sapadt.tools.screen import _sirlar
    try:
        return redact.temizle(resp, _sirlar(adt))
    except Exception:  # noqa: BLE001 — arındırma koşamazsa ham gövde dönmesin
        return {k: v for k, v in resp.items() if k not in ("sap_body", "message")}


def _obje_url(name: str, object_type: str) -> tuple[str | None, dict | None]:
    """`object_types.get_object_url` (tek kaynak). Üretilemeyen tip → unsupported_type (çıkış 3)."""
    if not (isinstance(name, str) and name.strip()):
        return None, {"ok": False, "error": "invalid_argument", "message": "name boş olamaz."}
    try:
        from object_types import get_object_url  # type: ignore
        return get_object_url(name.strip(), object_type), None
    except Exception as exc:  # noqa: BLE001 — ValueError/KeyError: tip bilinmiyor ya da generic URL yok
        return None, {"ok": False, "error": "unsupported_type",
                      "message": f"object_type={object_type!r} için obje URL'i üretilemedi: {exc}"}


def _pii_maskeli_mi(acknowledge_risk: bool) -> bool:
    """Sürüm yazarları kullanıcı kimliğidir. DEV dışında `acknowledge_risk` yoksa MASKELENİR (engellemez).
    Emsal: `adt_dump_list` DEV-dışı PII kuralı (`tools/query.py:836-840`); burada ret yerine maske — yeni bir
    bloklayıcı kapı açılmaz (gate moratoryumu)."""
    from sapadt._conn import get_active_tier
    return get_active_tier() != "DEV" and not bool(acknowledge_risk)


# ═══════════════════════════════════════ adt_revisions ═══════════════════════════════════════════
@profil_tool()
def adt_revisions(name: str, object_type: str = "class", limit: int = 20,
                  acknowledge_risk: bool = False) -> dict:
    """List the version history (revisions feed) of an ABAP object. READ-ONLY.

    Args:
        name: Obje adı.
        object_type: `object_types` tipi/eşanlamlısı (class, interface, program, include, ddls, ddlx, dcl, srvd,
            dtel, doma, tabl, structure, ttyp …). FM (func) generic URL taşımaz → unsupported_type.
        limit: Döndürülecek en fazla sürüm (1-200, varsayılan 20 — kaynak `list_revisions.py:40`).
        acknowledge_risk: DEV dışı tier'da sürüm yazarlarını (kullanıcı kimliği) açık gösterir.

    Returns:
        {ok, name, type, object_url, versions_link_found, versions_link, versions_link_count, count, returned,
         revisions[{version, versionTitle, author, date, uri}], author_masked, notice?}
        `versions_link` = okunan akışın yolu (sınıfta ana kaynak `…/includes/main/versions`; yoksa ilk bağlantı).
        Obje GET'i 200 dışı (ör. 406) → `revisions_unavailable` (ok:false) — "sürüm yok" diye BOŞ LİSTE DÖNMEZ.
        `versions_link_found:false` + `count:0` = uç bu obje için sürüm linki SUNMADI; "sürüm yok" KANITI DEĞİL.
    """
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
        return {"ok": False, "error": "invalid_argument", "message": "limit 1-200 arası tam sayı olmalı."}
    url, hata = _obje_url(name, object_type)
    if hata:
        return hata
    from sapadt.tools import atom as _atom
    adt = None
    try:
        client = _atom._get_client()
        adt = getattr(client, "adt_client", None) or client
        zaman = getattr(adt, "timeout_short", 30)
        from sap_adt_lib import (REVISIONS_FEED_ACCEPT, REVISIONS_OBJECT_ACCEPT,  # type: ignore
                                 resolve_adt_href, select_versions_link, versions_links)
        with _atom._capture_stdout():
            h = dict(adt._get_headers())
            h["Accept"] = REVISIONS_OBJECT_ACCEPT
            r = adt.session.get(adt.url + url, headers=h, timeout=zaman)
        durum = int(getattr(r, "status_code", 0) or 0)
        temel = {"name": name.strip().upper(), "type": object_type, "object_url": url}
        if durum == 404:
            return _temizle({"ok": False, "error": "not_found", **temel,
                             "message": f"[404] obje bulunamadı: {url}"}, adt)
        if durum != 200:
            return _temizle({"ok": False, "error": "revisions_unavailable", **temel, "http": {"structure": durum},
                             "message": f"Obje yapısı okunamadı (HTTP {durum}) — sürüm geçmişi ÖLÇÜLEMEDİ.",
                             "sap_body": str(getattr(r, "text", "") or "")[:300]}, adt)
        metin = str(getattr(r, "text", "") or "")
        baglantilar = versions_links(metin)
        secilen = select_versions_link(baglantilar)
        if not secilen:
            return {"ok": True, **temel, "versions_link_found": False, "count": 0, "returned": 0, "revisions": [],
                    "author_masked": False,
                    "notice": "Obje yapısında sürüm (versions) linki YOK — bu tip/uç sürüm geçmişi sunmuyor olabilir. "
                              "count:0 'sürüm yok' KANITI DEĞİLDİR."}
        feed = resolve_adt_href(url, secilen)
        temel["versions_link"] = feed if feed.startswith("/") else None
        temel["versions_link_count"] = len(baglantilar)
        feed_url = adt.url + feed if feed.startswith("/") else feed
        with _atom._capture_stdout():
            h = dict(adt._get_headers())
            h["Accept"] = REVISIONS_FEED_ACCEPT
            fr = adt.session.get(feed_url, headers=h, timeout=zaman)
        fdurum = int(getattr(fr, "status_code", 0) or 0)
        if fdurum != 200:
            return _temizle({"ok": False, "error": "revisions_feed_failed", **temel,
                             "http": {"structure": durum, "feed": fdurum},
                             "message": f"Sürüm feed'i okunamadı (HTTP {fdurum}) — sürüm geçmişi ÖLÇÜLEMEDİ.",
                             "sap_body": str(getattr(fr, "text", "") or "")[:300]}, adt)
    except Exception as exc:  # noqa: BLE001
        return _temizle(_atom._err_from_exc(exc), adt) if adt is not None else _atom._err_from_exc(exc)
    maske = _pii_maskeli_mi(acknowledge_risk)
    surumler = []
    for giris in _ENTRY.findall(str(getattr(fr, "text", "") or "")):
        def _g(rx, _metin=giris):
            m_ = rx.search(_metin)
            return m_.group(1) if m_ else ""
        yazar = _g(_E_AUTHOR)
        surumler.append({
            "version": _g(_E_VER_TR) or _g(_E_VER),
            "versionTitle": _xml_unescape(_g(_E_TITLE)),
            "author": ("***" if (maske and yazar) else yazar),
            "date": _g(_E_DATE),
            "uri": _g(_E_URI),
        })
    out = {"ok": True, **temel, "versions_link_found": True, "count": len(surumler),
           "returned": min(len(surumler), limit), "revisions": surumler[:limit], "author_masked": maske}
    if not surumler:
        out["notice"] = ("Sürüm feed'i okundu ama <atom:entry> yok. Ayrıştırma kütüphaneyle aynı desendir "
                         "(`<atom:entry>` önekli; canlıda sınıf/include/arayüz feed'lerinde kayıt ayrıştı, 2026-09-25); "
                         "başka obje tipinin farklı biçimli feed'inde 0 görünebilir — o tipler DOĞRULANMADI.")
    if maske:
        out["author_notice"] = "DEV dışı tier: yazarlar maskelendi (kullanıcı kimliği). Açık görmek: acknowledge_risk=true."
    return _temizle(out, adt)


# ═══════════════════════════════════ adt_object_structure ════════════════════════════════════════
@profil_tool()
def adt_object_structure(name: str, object_type: str = "class", version: str = "active") -> dict:
    """Read the object structure (components: methods, attributes, includes …) of an ABAP object. READ-ONLY.

    Args:
        name: Obje adı.
        object_type: `object_types` tipi/eşanlamlısı (FM generic URL taşımaz → unsupported_type).
        version: "active" | "inactive".

    Returns:
        {ok, name, type, object_url, version, exists, component_count, components[{name, type, uri, description}]}
        404 → `ok:true, exists:false` (uç 404 = yokluk kanıtı, `_bos_sonuc.py`); diğer HTTP → ok:false.
    """
    if version not in ("active", "inactive"):
        return {"ok": False, "error": "invalid_argument", "message": "version 'active' ya da 'inactive' olmalı."}
    url, hata = _obje_url(name, object_type)
    if hata:
        return hata
    from sapadt.tools import atom as _atom
    adt = None
    temel = {"name": name.strip().upper(), "type": object_type, "object_url": url, "version": version}
    try:
        client = _atom._get_client()
        adt = getattr(client, "adt_client", None) or client
        with _atom._capture_stdout():
            xml_text = adt.get_object_structure(url, version=version)
    except Exception as exc:  # noqa: BLE001
        if getattr(exc, "status_code", None) == 404:
            return {"ok": True, **temel, "exists": False, "component_count": 0, "components": []}
        e = _atom._err_from_exc(exc)
        return _temizle({**e, **temel}, adt) if adt is not None else {**e, **temel}
    import xml.etree.ElementTree as ET
    bilesenler = []
    try:
        kok = ET.fromstring(xml_text or "")
    except ET.ParseError as exc:
        return _temizle({"ok": False, "error": "structure_unparseable", **temel,
                         "message": f"Yapı yanıtı XML olarak ayrıştırılamadı ({exc}).",
                         "sap_body": str(xml_text or "")[:300]}, adt)
    kendisi = name.strip().upper()
    for el in kok.iter():   # sap_client.py:3315-3326 ile aynı alanlar ve aynı "objenin kendisi hariç" kuralı
        ad = el.get(f"{{{_NS_AC}}}name", "") or el.get("name", "")
        if ad and ad != kendisi:
            bilesenler.append({"name": ad, "type": el.get(f"{{{_NS_AC}}}type", "") or el.get("type", ""),
                               "uri": el.get(f"{{{_NS_AC}}}uri", "") or el.get("uri", ""),
                               "description": el.get(f"{{{_NS_AC}}}description", "") or el.get("description", "")})
    return _temizle({"ok": True, **temel, "exists": True, "component_count": len(bilesenler),
                     "components": bilesenler}, adt)


# ═════════════════════════════════════ adt_system_info ═══════════════════════════════════════════
_GIZLI_SISTEM_ALANLARI = ("connection_url", "client", "user", "system_id")


@profil_tool()
def adt_system_info() -> dict:
    """List the ADT discovery service catalog of the connected system (no connection identity in output). READ-ONLY.

    Returns:
        {ok, service_count, available_services[{title, href}], logon_language, tier, profile, withheld_fields}
        Kütüphane metodu discovery hatasını yutar: servis listesi yoksa `ok:false discovery_unavailable`.
    """
    from sapadt._conn import get_active_tier
    from sapadt._profile import aktif_profil
    from sapadt.tools import atom as _atom
    adt = None
    try:
        client = _atom._get_client()
        adt = getattr(client, "adt_client", None) or client
        with _atom._capture_stdout():
            bilgi = adt.get_system_info() or {}
    except Exception as exc:  # noqa: BLE001
        return _temizle(_atom._err_from_exc(exc), adt) if adt is not None else _atom._err_from_exc(exc)
    ortak = {"tier": get_active_tier(), "profile": aktif_profil(),
             "logon_language": str(bilgi.get("language") or "") or None,
             "withheld_fields": list(_GIZLI_SISTEM_ALANLARI)}
    servisler = bilgi.get("available_services")
    if not isinstance(servisler, list):
        return _temizle({"ok": False, "error": "discovery_unavailable", **ortak,
                         "message": "ADT discovery (/sap/bc/adt/discovery) okunamadı — kütüphane hatayı yuttuğu için "
                                    "sebep bilinmiyor. sap_doctor ile bağlantı/kimlik katmanına bak."}, adt)
    temiz = [{"title": str(s.get("title") or ""), "href": str(s.get("href") or "")}
             for s in servisler if isinstance(s, dict)]
    return _temizle({"ok": True, "service_count": len(temiz), "available_services": temiz, **ortak}, adt)


# ═════════════════════════════════════════ sap_doctor ════════════════════════════════════════════
_ZORUNLU_ANAHTARLAR = ("ADT_SAP_URL", "ADT_SAP_USER", "ADT_SAP_PASSWORD", "ADT_SAP_CLIENT")  # sap_doctor.py:38
_GIZLI_ANAHTARLAR = frozenset({"ADT_SAP_PASSWORD"})
DOCTOR_NOT_CHECKED = (
    "Obje/paket erişimi ve geliştirme yetkisi (S_DEVELOP) — probe objesi yok, yazma denenmez",
    "Transport durumu/geçerliliği",
    "Parolanın DOĞRULUĞU yalnız canlı kimlik adımıyla dolaylı ölçülür; değer okunmaz, basılmaz",
    "TLS sertifika geçerliliği (ADT_SAP_SSL_VERIFY=false iken sertifika denetlenmez)",
    "Yazma uçlarında (LOCK/PUT) CSRF kabulü — yalnız token alınabildiği ölçülür",
    "SAML/SSO çerez ömrü (check_logon'un HTML tespitinin ötesi)",
    "Profil yetenek matrisinin canlı doğruluğu (references/profiles.md rehberdir)",
    "ATC variant ve sistemdeki aktivasyon kuyruğu",
)


def _anahtar_durumu(proj) -> dict:
    """`.conn_adt`teki anahtarların VARLIĞI/doluluğu — değer DÖNDÜRMEZ. Parola için yalnız "dolu mu"."""
    from sapadt import project as _project
    p = _project.conn_path(proj)
    durum = {k: {"file": False, "env": k in os.environ, "placeholder": False} for k in _ZORUNLU_ANAHTARLAR}
    if not p.is_file():
        return durum
    try:
        satirlar = p.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    except OSError:
        return durum
    for ln in satirlar:
        s = ln.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        k = k.strip()
        if k not in durum:
            continue
        dolu = bool(v.strip())
        durum[k]["file"] = durum[k]["file"] or dolu
        if k not in _GIZLI_ANAHTARLAR and dolu:
            durum[k]["placeholder"] = "<" in v   # switch_tier.py:109-117 (doldurulmamış <...>)
    return durum


@profil_tool()
def sap_doctor(live: bool = True) -> dict:
    """One-command SAP connection diagnosis: local config + live logon/CSRF, PASS/WARN/FAIL with scope statement.

    Yerel katmanlar (ağ yok): sap-project.json · profil · .conn_adt varlığı · zorunlu anahtarlar (yalnız ad) ·
    ortam değişkeni ezmesi · tier · bağlantı dili ↔ master_language · TLS ayarı · araç katmanı.
    Canlı katmanlar (`live=true` ve yerel ön koşullar tamamsa): erişim + kimlik (`check_logon`) · CSRF token alma.
    Değer basılmaz: URL/host, kullanıcı, client, parola, token, sistem kimliği.

    Args:
        live: false → canlı katmanlar SKIP (yalnız yerel tanı).

    Returns:
        {ok, verdict: PASS|WARN|FAIL, summary{pass,warn,fail,skip}, checks[{id, status, detail}], not_checked[]}
        Herhangi bir FAIL → ok:false (error doctor_fail, çıkış 1).
    """
    from sapadt import gate as _gate
    from sapadt import project as _project
    from sapadt._conn import get_active_tier
    from sapadt._profile import aktif_profil, uygun_mu

    kontroller: list[dict] = []

    def ekle(kid, status, detail):
        kontroller.append({"id": kid, "status": status, "detail": detail})

    if not isinstance(live, bool):
        return {"ok": False, "error": "invalid_argument", "message": "live true/false olmalı."}
    proj = _project.project_dir()
    cfg, hata = _project.load_sap_project(proj)
    if cfg:
        ekle("sap_project", "PASS", f"{_project.SAP_PROJECT_FILE} geçerli (profil={cfg.get('sap_profile')}, "
                                    f"release={cfg.get('release')}, master_language={cfg.get('master_language')})")
    else:
        ekle("sap_project", "FAIL", f"{hata} — CLI yalnız --list/ping/sap_doctor açar.")

    profil = aktif_profil(proj)
    if profil:
        from sapadt._app import load_all_tools
        kayit = load_all_tools()
        acik = sum(1 for s in kayit.values() if uygun_mu(s.available_on, profil))
        ekle("profile", "PASS", f"profil={profil}: {acik}/{len(kayit)} araç bu profilde açık (bkz. references/profiles.md)")
    else:
        ekle("profile", "FAIL", "profil çözülemedi → fail-closed (ping dışında araç açılmaz)")

    conn_var = _project.conn_path(proj).is_file()
    ekle("conn_file", "PASS" if conn_var else "FAIL",
         f"{_project.CONN_FILE} proje kökünde {'VAR' if conn_var else 'YOK'} (içerik değerleri okunmadı/basılmadı)"
         + ("" if conn_var else " — scripts/setup_credentials.py ile geliştirici KENDİ terminalinde oluşturur"))

    anahtarlar = _anahtar_durumu(proj)
    eksik = [k for k, d in anahtarlar.items() if not d["file"] and not d["env"]]
    yer_tutucu = [k for k, d in anahtarlar.items() if d["placeholder"]]
    if eksik or yer_tutucu:
        ekle("conn_keys", "FAIL", "; ".join(x for x in (
            f"eksik/boş: {', '.join(eksik)}" if eksik else "",
            f"doldurulmamış <...> değer: {', '.join(yer_tutucu)}" if yer_tutucu else "") if x))
    else:
        ekle("conn_keys", "PASS", "zorunlu anahtarlar dolu: " + ", ".join(_ZORUNLU_ANAHTARLAR) + " (değerler basılmadı)")

    ezme = _gate.check_connection(proj)
    env_adt = sorted(k for k in os.environ if k.upper().startswith("ADT_"))
    if ezme:
        ekle("env_override", "FAIL", ezme[1])
    elif env_adt:
        ekle("env_override", "WARN", f"ortamda ADT_* değişkeni var ({', '.join(env_adt)}; değerler basılmadı) — "
                                     "istemci bunları .conn_adt'ye tercih eder (load_dotenv override=False)")
    else:
        ekle("env_override", "PASS", "ortamda ADT_* değişkeni yok — bağlantı yalnız .conn_adt'den")

    tier = get_active_tier(proj)
    if tier == "DEV":             # sap_doctor.py:84-91
        ekle("tier", "PASS", "tier=DEV — yazma kapısının tier adımı geçer (diğer adımlar ayrıca)")
    elif tier in ("QA", "PRD"):
        ekle("tier", "WARN", f"tier={tier} — SALT-OKUNUR (yazma araçları tier_not_writable ile reddedilir)")
    else:
        ekle("tier", "FAIL", "tier ÇÖZÜLEMEDİ (UNKNOWN) → yazma reddedilir (fail-closed). .conn_adt'ye tek "
                             "ADT_SAP_TIER=DEV|QA|PRD satırı; çok sistem için conn/ + scripts/switch_tier.py")

    dil = (_project.effective_conn_value("ADT_SAP_LANGUAGE", "EN", proj) or "").strip().upper()
    ml = (cfg or {}).get("master_language")
    if ml and dil == ml:
        ekle("language", "PASS", f"bağlantı dili = master_language ({ml})")
    else:                          # sap_doctor.py:93-98 (WARN)
        ekle("language", "WARN", f"bağlantı dili ({dil or 'boş'}) ≠ master_language ({ml or '?'}) — yazma çağrıları "
                                 "language_mismatch ile reddedilir; okuma çalışır")

    tls = (_project.effective_conn_value("ADT_SAP_SSL_VERIFY", "false", proj) or "").strip().lower()
    if tls in ("true", "1", "yes"):
        ekle("tls", "PASS", "ADT_SAP_SSL_VERIFY açık — sertifika doğrulanır")
    else:
        ekle("tls", "WARN", "TLS sertifika doğrulaması KAPALI (ADT_SAP_SSL_VERIFY) — kurum sertifikası "
                            "tanımlanabiliyorsa açılması önerilir")

    try:
        from sapadt._app import load_all_tools
        ekle("tool_layer", "PASS", f"araç katmanı yüklendi ({len(load_all_tools())} araç)")
    except Exception as exc:  # noqa: BLE001
        ekle("tool_layer", "FAIL", f"araç katmanı yüklenemedi ({type(exc).__name__})")

    # ── canlı katmanlar ─────────────────────────────────────────────────────────────────────────
    engel = [k["id"] for k in kontroller if k["status"] == "FAIL"
             and k["id"] in ("sap_project", "profile", "conn_file", "conn_keys", "env_override")]
    if not live:
        ekle("logon", "SKIP", "live=false — canlı katman koşulmadı (bağlantı KANITLANMADI)")
        ekle("csrf", "SKIP", "live=false — canlı katman koşulmadı")
    elif engel:
        ekle("logon", "SKIP", f"yerel ön koşul FAIL ({', '.join(engel)}) — SAP'ye gidilmedi (okuma kapısıyla aynı kural)")
        ekle("csrf", "SKIP", "yerel ön koşul FAIL — SAP'ye gidilmedi")
    else:
        adt = None
        from sapadt.tools import atom as _atom
        try:
            client = _atom._get_client()
            adt = getattr(client, "adt_client", None) or client
        except Exception as exc:  # noqa: BLE001
            e = _atom._err_from_exc(exc)
            ekle("logon", "FAIL", f"istemci kurulamadı ({e.get('error')}): {str(e.get('message') or '')[:200]}")
            ekle("csrf", "SKIP", "istemci kurulamadı")
        if adt is not None:
            try:
                with _atom._capture_stdout():
                    lg = adt.check_logon() or {}
            except Exception as exc:  # noqa: BLE001
                lg = {"success": False, "status_code": None, "message": f"{type(exc).__name__}: {exc}"}
            kod = lg.get("status_code")
            msj = str(lg.get("message") or "")[:240]
            if lg.get("success") is True:
                ekle("logon", "PASS", f"ADT erişimi + kimlik OK (HTTP {kod})")
            elif kod in (401, 403):
                ekle("logon", "FAIL", f"kimlik REDDEDİLDİ (HTTP {kod}) — kullanıcı/parola/client; parola "
                                      "değişti ise known-errors-adt.md K-24")
            elif kod == 200:
                ekle("logon", "FAIL", f"HTML giriş sayfası döndü (SSO/SAML gerekli): {msj}")
            else:
                ekle("logon", "FAIL", f"SAP'ye ULAŞILAMADI ya da ADT ucu yok — bağlantı KANITLANMADI: {msj}")
            if kontroller[-1]["status"] == "PASS":
                try:
                    with _atom._capture_stdout():
                        tok = adt.fetch_csrf_token(force_refresh=True)
                    ekle("csrf", "PASS" if tok else "FAIL",
                         "CSRF token alındı (değer basılmadı)" if tok else "CSRF token BOŞ döndü")
                except Exception as exc:  # noqa: BLE001
                    e = _atom._err_from_exc(exc)
                    ekle("csrf", "FAIL", f"CSRF token alınamadı ({e.get('error')}): {str(e.get('message') or '')[:200]}")
            else:
                ekle("csrf", "SKIP", "erişim/kimlik FAIL — CSRF denenmedi")
        kontroller[:] = _temizle({"k": kontroller}, adt)["k"] if adt is not None else kontroller

    ozet = {s.lower(): sum(1 for k in kontroller if k["status"] == s) for s in ("PASS", "WARN", "FAIL", "SKIP")}
    hukum = "FAIL" if ozet["fail"] else ("WARN" if ozet["warn"] else "PASS")
    out = {"ok": hukum != "FAIL", "verdict": hukum, "summary": ozet, "checks": kontroller,
           "not_checked": list(DOCTOR_NOT_CHECKED)}
    if hukum == "FAIL":
        out.update(error="doctor_fail",
                   message=f"{ozet['fail']} FAIL: " + ", ".join(k["id"] for k in kontroller if k["status"] == "FAIL"))
    return out


# ═══════════════════════════════════════ adt_pretty_print ════════════════════════════════════════
# Z128 (2026-09-25): classes.md §7.1 reçetesinin "birimi biçimle" adımı. Kanıt:
#   · kaynak okuma: `lib/sap_adt_lib.py:2050 get_object_source` — `adt_get` ile AYNI çağrı (sürüm verilmez = son
#     sürüm; `lib/sap_client.py:296-302 download_object`) ⇒ biçimlenen metin PULL-BEFORE-EDIT tabanıyla aynıdır.
#     CRLF → LF normalize eder (`:2099`).
#   · biçimleme: `lib/sap_adt_lib.py:7056 pretty_print` — `POST /sap/bc/adt/abapsource/prettyprinter`, gövde =
#     kaynak, yanıt = biçimlenmiş metin. Durumsuzdur: lock / PUT / activate / transport YOK.
#   · `lib/sap_client.py:3364 pretty_print` KULLANILMAZ: istisnayı yutup None döndürür ("obje yok" ile "biçimleyici
#     hata verdi" ayırt edilemez) ve stdout'a basar (CLI stdout sözleşmesi tek JSON).
# ⛔ SALT-OKUR: SAP'de hiçbir şey değiştirmez; `pull_state` YAZMAZ (tabanı yalnız `adt_get` yazar). Tek yerel yan
#   etki `output_path` dosyasıdır ve yol proje kökü + `.abap` uzantısı + `.axet-code/` dışı ile SINIRLIDIR ⇒ bu araçla
#   `.conn_adt`, `sap-project.json`, `.rules.md` ya da kapı kayıtları ezilemez.
_PP_GENEL_TIPLER = frozenset({"class", "interface", "program", "include"})   # object_types.normalize_object_type çıktısı
_PP_UZANTI = ".abap"
_PP_DIFF_SINIR = 1500


def _pp_hedef(name: str, object_type: str) -> tuple[str | None, str | None, dict | None]:
    """(obje_url, kanonik_tip, hata). Desteklenmeyen tip → unsupported_type (çıkış 3), ağa gidilmez."""
    if not (isinstance(name, str) and name.strip()):
        return None, None, {"ok": False, "error": "invalid_argument", "message": "name boş olamaz."}
    ad = name.strip()
    try:
        from object_types import (get_class_include_url, get_object_url, is_class_include,  # type: ignore
                                  normalize_class_include, normalize_object_type)
        if is_class_include(object_type):
            return get_class_include_url(ad, object_type), normalize_class_include(object_type), None
        kanonik = normalize_object_type(object_type)
    except Exception as exc:  # noqa: BLE001 — bilinmeyen tip
        kanonik, exc_metni = None, str(exc)
    else:
        exc_metni = ""
    if kanonik not in _PP_GENEL_TIPLER:
        return None, None, {"ok": False, "error": "unsupported_type",
                            "message": (f"object_type={object_type!r} biçimlenemez: Pretty Printer yalnız ABAP kaynak "
                                        "objelerinde desteklenir — class, interface, program, include ve sınıf "
                                        "alt-include'ları ccimp/ccau/ccdef/ccmac (name = ANA SINIF). Fonksiyon modülü "
                                        "(func) generic URL taşımaz; CDS/DDIC/BDEF ABAP kaynağı değildir."
                                        + (f" ({exc_metni})" if exc_metni else ""))}
    return get_object_url(ad, kanonik), kanonik, None


def _pp_cikti_yolu(output_path) -> tuple[Path | None, dict | None]:
    """`output_path` → mutlak yol. Proje kökü dışı, `.abap` dışı uzantı, `.axet-code/` altı, `.axetcode-denylist`
    yolu altı → invalid_argument.
    Kural TEK kaynakta (`sapadt.project.yerel_kaynak_yolu`, Z142); bu araç uzantıyı `.abap` ile daraltır."""
    from sapadt import project as _project
    return _project.yerel_kaynak_yolu(output_path, "output_path", (_PP_UZANTI,))


@profil_tool()
def adt_pretty_print(name: str, object_type: str = "class", output_path: str | None = None,
                     overwrite: bool = False) -> dict:
    """Format an ABAP object's source with the SAP Pretty Printer and return / save it LOCALLY. READ-ONLY (SAP is not modified).

    Kaynağı `adt_get` ile aynı uçtan okur, `POST /sap/bc/adt/abapsource/prettyprinter` ile biçimletir. SAP'de
    kaydetme / kilit / aktivasyon / transport YOKTUR; pull kaydı (`sap-pull-state.json`) YAZILMAZ. Biçimlenmiş
    metni sisteme koymak AYRI bir adımdır: `adt_get` (taban) → dosyayı düzenle → `adt_push_source` (yazma kapısı).

    Args:
        name: Obje adı. Sınıf alt-include'unda ANA SINIF adı.
        object_type: class · interface · program · include · ccimp/ccau/ccdef/ccmac (eşanlamlılar kabul).
        output_path: Biçimlenmiş metnin yazılacağı yerel dosya — proje kökü içinde, `.abap` uzantılı, `.axet-code/`
            dışında (göreli yol proje köküne göre). Verilmezse metin yanıtta `source` alanında döner.
        overwrite: Var olan dosyanın üzerine yazılsın mı (varsayılan HAYIR → `output_exists`, çıkış 1).

    Returns:
        {ok, name, type, object_url, server_modified:false, changed, changed_line_count, line_count_before,
         line_count_after, diff_preview, output_path, written, source?}
        `changed:false` = SAP biçimleyicisi (oturum kullanıcısının biçim ayarıyla) fark üretmedi. ATC'nin
        "Pretty Print" kontrolü ATC varyantının parametreleriyle biçimler — iki ayar farklıysa sonuç farklı olabilir.
    """
    import difflib
    url, kanonik, hata = _pp_hedef(name, object_type)
    if hata:
        return hata
    yol = None
    if output_path is not None:
        yol, hata = _pp_cikti_yolu(output_path)
        if hata:
            return hata
        if yol.exists() and not overwrite:
            return {"ok": False, "error": "output_exists",
                    "message": "output_path zaten var; üzerine yazmak için overwrite=true ver ya da başka yol seç. "
                               "SAP'ye gidilmedi."}
    from sapadt import project as _project
    from sapadt.tools import atom as _atom
    temel = {"name": name.strip().upper(), "type": kanonik, "object_url": url, "server_modified": False}
    adt = None
    try:
        client = _atom._get_client()
        adt = getattr(client, "adt_client", None) or client
        with _atom._capture_stdout():
            kaynak = adt.get_object_source(url)
    except Exception as exc:  # noqa: BLE001
        if getattr(exc, "status_code", None) == 404:
            return _temizle({"ok": False, "error": "not_found", **temel,
                             "message": f"[404] kaynak bulunamadı: {url} — hiçbir şey biçimlenmedi/yazılmadı."}, adt)
        e = _atom._err_from_exc(exc)
        return _temizle({**e, **temel}, adt) if adt is not None else {**e, **temel}
    if not isinstance(kaynak, str) or not kaynak.strip():
        return _temizle({"ok": False, "error": "source_empty", **temel,
                         "message": "Obje kaynağı boş döndü — biçimlenecek metin yok, dosya yazılmadı."}, adt)
    try:
        with _atom._capture_stdout():
            bicimli = adt.pretty_print(url, kaynak)
    except Exception as exc:  # noqa: BLE001
        durum = getattr(exc, "status_code", None)
        return _temizle({"ok": False, "error": "pretty_print_failed", **temel, "http": durum,
                         "message": f"SAP Pretty Printer hata verdi (HTTP {durum}) — dosya yazılmadı. {exc}"}, adt)
    if not isinstance(bicimli, str) or not bicimli.strip():
        return _temizle({"ok": False, "error": "pretty_print_empty", **temel,
                         "message": "Pretty Printer boş metin döndü — boş kaynağın yerel kopyaya yazılması "
                                    "ENGELLENDİ (push edilirse kaynağı silerdi)."}, adt)
    bicimli = bicimli.replace("\r\r\n", "\n").replace("\r\n", "\n").replace("\r", "\n")  # get_object_source ile aynı
    once, sonra = kaynak.splitlines(), bicimli.splitlines()
    fark = list(difflib.unified_diff(once, sonra, fromfile="sap", tofile="pretty_print", lineterm="", n=0))
    degisen = sum(1 for s in fark if s[:1] in "+-" and not s.startswith(("+++", "---")))
    diff_metni = "\n".join(fark)
    out = {"ok": True, **temel, "changed": kaynak != bicimli, "changed_line_count": degisen,
           "line_count_before": len(once), "line_count_after": len(sonra),
           "diff_preview": diff_metni[:_PP_DIFF_SINIR] + ("\n…(kırpıldı)" if len(diff_metni) > _PP_DIFF_SINIR else ""),
           "output_path": None, "written": False}
    if yol is None:
        out["source"] = bicimli
    else:
        yazma_hatasi = _project.yerel_dosyaya_yaz(yol, bicimli)
        if yazma_hatasi:
            return _temizle({"ok": False, "error": "output_write_failed", **temel,
                             "message": f"Yerel dosya yazılamadı ({yazma_hatasi}). SAP değişmedi."}, adt)
        out["output_path"] = yol.relative_to(_project.project_dir()).as_posix()
        out["written"] = True
    out["notice"] = ("SAP'de hiçbir şey değişmedi (kaydetme/kilit/aktivasyon/transport yok). Sisteme almak için: "
                     "adt_get (taban) → biçimli metni uygula → adt_push_source → adt_activate.")
    return _temizle(out, adt)


# ═══════════════════════════════════════ adt_get_method ══════════════════════════════════════════
# Z195 ② (2026-10-19; kaynak çekirdek salt-okur `adt_get_method`): sınıfın ANA kaynağından TEK metot gövdesi.
# SAP'ye YAZMAZ (yalnız `adt_get` ile aynı `source/main` GET'i); pull kaydı YAZILMAZ (tam kaynak değil).
_METOT_BAS = re.compile(r"^\s*METHOD\s+([A-Za-z0-9_/~]+)(?=[\s.]|$)", re.IGNORECASE)
_METOT_SON = re.compile(r"^\s*ENDMETHOD\s*\.", re.IGNORECASE)
# Satır içinde (başta olmayan) ENDMETHOD sözcüğü: `METHOD a. ENDMETHOD.` tek satır ya da `y = 2. ENDMETHOD.` zinciri.
_METOT_SON_ICERDE = re.compile(r"(?<![A-Za-z0-9_])ENDMETHOD(?![A-Za-z0-9_])", re.IGNORECASE)
# Yorum ayıklayıcı YOK (bilinçli, kaynak çekirdekle aynı): iki desen satır başına `^\s*` ile çapalıdır ⇒ sütun-1 `*`
# yorumu ve `"` satır-içi yorumu yapısal olarak eşleşemez.
# Sınır güvenle çıkarılamıyorsa (bitiş METHOD satırında / satır ortasında, ya da bitişten önce yeni `METHOD` satırı)
# blok BELİRSİZ döner — yanlış blok döndürmek yerine (2026-10-19 inceleme bulgusu: tek satırlık metot komşu metodun
# gövdesini found:true ile döndürüyordu).
_METOT_KAPSAM = (
    "Sinifin ANA kaynagi (`source/main`, EN GUNCEL surum — `version` parametresiz GET: bekleyen inaktif surum varsa "
    "O okunur, aktif surum DEGIL) METINSEL taranir: `METHOD <ad>.` .. `ENDMETHOD.`. Yerel siniflar / test "
    "include'lari (ccimp/ccau/ccdef) ve makrolar ARANMAZ ⇒ found:false 'metot yok' demek DEGILDIR.")


def _satir_ici_bitis(satir: str) -> bool:
    """Satırda başta olmayan bir ENDMETHOD sözcüğü var mı (tam satır yorumları hariç)."""
    if satir.startswith("*") or satir.lstrip().startswith('"'):
        return False
    return bool(_METOT_SON_ICERDE.search(satir))


def _metot_cikar(kaynak: str, metot: str) -> list:
    """`METHOD <metot>.` .. `ENDMETHOD.` blokları → [(bas, son, metin, belirsiz_sebep)] (1-tabanlı satır).

    Kapanmamış blok `son=None, sebep=None` ile döner (çağıran ÖLÇÜLEMEDİ der). Sınırı güvenle çıkarılamayan
    blok `son=None` + `sebep` (str) ile döner (çağıran `belirsiz` der): METHOD satırında ENDMETHOD · bitiş satır
    ortasında (zincirli) · bitişten önce yeni `METHOD` satırı. Satır bölme yalnız `\n`
    (str.splitlines Unicode ayırıcılarda da böler)."""
    hedef = (metot or "").strip().upper()
    satirlar = [s[:-1] if s.endswith("\r") else s for s in (kaynak or "").split("\n")]
    bulunan, i = [], 0
    while i < len(satirlar):
        m = _METOT_BAS.match(satirlar[i])
        if m and m.group(1).upper() == hedef:
            if _METOT_SON_ICERDE.search(satirlar[i][m.end():]):
                bulunan.append((i + 1, None, satirlar[i], "METHOD satırında ENDMETHOD (tek satırlık metot)"))
                i += 1
                continue
            j, sebep = None, None
            for k in range(i + 1, len(satirlar)):
                if _METOT_SON.match(satirlar[k]):
                    j = k
                    break
                if _METOT_BAS.match(satirlar[k]):
                    j, sebep = k, "ENDMETHOD. bulunmadan yeni METHOD satırı (satır %d)" % (k + 1)
                    break
                if _satir_ici_bitis(satirlar[k]):
                    j, sebep = k, "ENDMETHOD satır ortasında (satır %d)" % (k + 1)
                    break
            if j is None:
                bulunan.append((i + 1, None, "\n".join(satirlar[i:]), None))
                break
            if sebep:
                bulunan.append((i + 1, None, "\n".join(satirlar[i:j]), sebep))
                i = j if _METOT_BAS.match(satirlar[j]) else j + 1
                continue
            bulunan.append((i + 1, j + 1, "\n".join(satirlar[i:j + 1]), None))
            i = j
        i += 1
    return bulunan


@profil_tool()
def adt_get_method(name: str, method: str, output_path: str | None = None, overwrite: bool = False) -> dict:
    """Read ONE method body from a class's main source. READ-ONLY (SAP is not modified).

    Sınıfın ana kaynağını `adt_get` ile aynı uçtan (`/sap/bc/adt/oo/classes/<ad>/source/main`, GET) okur ve
    `METHOD <ad>.` .. `ENDMETHOD.` bloğunu metinsel çıkarır. Kilit/PUT/aktivasyon/transport YOK; pull kaydı
    (`sap-pull-state.json`) YAZILMAZ — metodu düzenleyip geri yazmak için tam kaynak `adt_get` ile çekilir.

    Args:
        name: Sınıf adı (standart sınıf da okunabilir — okuma serbest).
        method: Metot adı (arayüz metodu `zif_x~m` biçimiyle).
        output_path: Metin yerel dosyaya yazılır (`adt_get` ile aynı yol kuralı: proje kökü içi · kaynak uzantısı ·
            `.axet-code/` dışı · denylist dışı); verilmezse metin yanıtta `source` alanında döner.
        overwrite: Var olan dosyanın üzerine yazılsın mı (varsayılan HAYIR → `output_exists`).

    Returns:
        {ok, name, method, found, start_line?, end_line?, source?, output_path, written, scope, client_log}
        `found: false` + `scope` = aranan yüzeyde YOK (yerel include'lar aranmadı).
        Birden çok eşleşme ya da kapanmamış blok ⇒ ok:false (`belirsiz` / `kapanmamis`, found:null).
        Sınırı güvenle çıkarılamayan blok (tek satırlık `METHOD a. ENDMETHOD.` · satır ortasında zincirli
        `ENDMETHOD.` · bitişten önce yeni `METHOD` satırı) ⇒ `belirsiz`, found:null — yanlış blok döndürülmez.
    """
    if not (isinstance(name, str) and name.strip()) or not (isinstance(method, str) and method.strip()):
        return {"ok": False, "error": "invalid_argument", "scope": _METOT_KAPSAM,
                "message": "name ve method boş olamaz. SAP'ye gidilmedi."}
    from sapadt import project as _project
    yol = None
    if output_path is not None:
        yol, hata = _project.yerel_kaynak_yolu(output_path, "output_path")
        if hata:
            return {**hata, "scope": _METOT_KAPSAM, "message": hata["message"] + " SAP'ye gidilmedi."}
        if yol.exists() and not overwrite:
            return {"ok": False, "error": "output_exists", "scope": _METOT_KAPSAM,
                    "message": "output_path zaten var; üzerine yazmak için overwrite=true ver ya da başka yol seç. "
                               "SAP'ye gidilmedi."}
    from sapadt.tools import atom as _atom
    oku = _atom._read_source_object(name.strip(), "oo/classes", "class")
    ortak = {"name": name.strip().upper(), "method": method.strip().upper(), "scope": _METOT_KAPSAM,
             "output_path": None, "written": False, "client_log": oku.get("client_log", "")}
    if not oku.get("ok") or not oku.get("exists"):
        return {**{k: v for k, v in oku.items() if k != "source"}, **ortak}
    bloklar = _metot_cikar(oku.get("source") or "", method)
    if not bloklar:
        return {"ok": True, "found": False, **ortak}
    if len(bloklar) > 1:
        return {"ok": False, "error": "belirsiz", "found": None,
                "matches": [{"start_line": b, "end_line": s} for b, s, _m, _sb in bloklar],
                "message": ("Ana kaynakta %d ayrı `METHOD %s.` bloğu var (yerel sınıf?) — hangisi olduğu ad ile "
                            "AYIRT EDİLEMEZ." % (len(bloklar), method.strip().upper())), **ortak}
    bas, son, metin, sebep = bloklar[0]
    if sebep:
        return {"ok": False, "error": "belirsiz", "found": None,
                "matches": [{"start_line": bas, "end_line": None}],
                "message": ("`METHOD %s.` bloğunun sınırı satır yapısından güvenle çıkarılamadı (%s) — gövde "
                            "DÖNDÜRÜLMEDİ (yanlış blok riski). Tam kaynak için adt_get."
                            % (method.strip().upper(), sebep)), **ortak}
    if son is None:
        return {"ok": False, "error": "kapanmamis", "found": None, "start_line": bas,
                "message": "`METHOD` bulundu ama `ENDMETHOD.` bulunamadı — gövde ÖLÇÜLEMEDİ.", **ortak}
    out = {"ok": True, "found": True, "start_line": bas, "end_line": son, **ortak}
    if yol is None:
        out["source"] = metin
        return out
    yazma_hatasi = _project.yerel_dosyaya_yaz(yol, metin)
    if yazma_hatasi:
        return {**out, "ok": False, "error": "output_write_failed", "source": metin,
                "message": f"Metot okundu ama yerel dosya yazılamadı ({yazma_hatasi}). SAP değişmedi; source yanıtta."}
    out["output_path"] = yol.relative_to(_project.project_dir()).as_posix()
    out["written"] = True
    out["line_count"] = len(metin.splitlines())
    return out
