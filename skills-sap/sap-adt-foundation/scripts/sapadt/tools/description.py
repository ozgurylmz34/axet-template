# -*- coding: utf-8 -*-
"""adt_set_description — mevcut Z/Y objenin kısa açıklamasını (adtcore:description) değiştirir (aXet 2026-09-13). YAZMA.

REÇETE (kaynak çekirdek, salt-okur):
  · `scripts/sap_set_object_description.py:48-57` tip → ana envelope URL segmenti · `:68-70` açıklama regex'i ·
    `:73-87` 412 gövdesinden sunucu ETag'i (`SADT_RESOURCE` + `T100KEY-NO 043` → `T100KEY-V2`, yoksa "object ETag <B> ") ·
    `:90-119` LOCK → PUT (envelope Content-Type, stateful, If-Match, lockHandle, corrNr = kilit yanıtındaki CORRNR ya da istenen) → UNLOCK ·
    `:122-138` aktive-bekleyen listesinde ad/URI eşleşmesi · `:145-178` aktivasyon + listenin yeniden okunması + `?version=active` readback ·
    `:210-237` envelope GET (Accept `application/*`), aynıysa NOOP, tek öznitelik değişimi · `:248-276` 412'de TEK retry, yalnız
    envelope ilk okumadan beri bayt bayt aynıysa, yeni LOCK döngüsünde; ikinci 412 = FAIL · `:277-282` 200/204 dışı FAIL, 423 → teşhis.
  · Canlı ölçüm (kaynak `playbook/known-errors.md:279-290` §12.7c eki; script docstring `:19-31`): YALNIZ DDLS — 412 + tek retry 200,
    başarılı PUT objeyi hemen inaktife düşürür. Diğer tipler reçete kodunda var, canlı ÖLÇÜLMEDİ (`live_evidence`).
  · Desteklenmeyen (kanıtlı): `srvb` — REST'te LOCK 200 → PUT 423 (`playbook/adt-rap.md:180-189`); program açıklaması (TRDIRT) ADT ile
    değişmez, 406/404/403 → SE38 (`playbook/howto-dynpro-gui-status-generation.md:457-459`); `dtel` — envelope'ta `adtcore:description` İKİ
    kez geçer (kök + packageRef) ve DTEL PUT'u If-Match'siz ayrı reçetedir (`playbook/adt-domain-dtel.md:30-75`); açıklama değişikliği ölçülmedi.

KAYNAKTAN BİLİNÇLİ FARKLAR:
  1. Kilit: kütüphane `lock_object` (4 strateji) yerine obje URL'ine `_action=LOCK` (kütüphanenin 3. stratejisi `sap_adt_lib.py:2640-2655`,
     `tools/msgclass.py` ile aynı yol) + `<LOCK_HANDLE>`/`<CORRNR>` ayrıştırma (`sap_adt_lib.py:2277-2290`). CORRNR istenen transporttan
     farklıysa kütüphane gibi (`sap_adt_lib.py:2472-2515`) PUT YAPILMADAN kilit bırakılır → `transport_mismatch`. Kilit alınamazsa
     `lock_conflict` / `lock_failed`; enqueue kilidi SİLİNMEZ (Kesin Yasak C). Eşdeğerlik canlı DOĞRULANMADI.
  2. Açıklama öznitelik değeri XML-kaçışlı yazılır ve kaçışı çözülmüş hâliyle kıyaslanır (kaynak ham `replace` yapıyordu — `&`/`"` bozardı).
     Değiştirilen öznitelik KÖK öğenin başlangıç etiketinde olmalıdır (packageRef açıklamasına yazma riski, DTEL dersi).
  3. Otomatik aktivasyon YALNIZ PUT'tan ÖNCE okunan aktive-bekleyen listesi objenin temiz olduğunu KANITLADIYSA yapılır (yalnız bu
     değişikliğin sürümü aktive edilir). Obje zaten listedeyse ya da liste okunamadıysa aktive EDİLMEZ → `activation_required`
     (kullanıcının bekleyen kaynağını habersiz aktive etmemek için). `--force-put` taşınmadı.
  4. Uzunluk: envelope'taki `adtcore:descriptionTextLimit` (varsa) ağ yazımından ÖNCE uygulanır; sınıf için ölçülen sınır 60
     (`tools/atom.py:1094-1121`, `references/known-errors-adt.md` K-16) ağdan önce. Diğer tiplerde sabit sınır kanıtı yok.
  5. PULL-BEFORE-EDIT: obje için çekme kaydı VARSA canlı kaynak özeti kıyaslanır (farklı → `source_changed_since_pull`); yazımdan sonra kayıt
     silinir (sonraki push `adt_get` ister). Kayıt yoksa açıklama değişikliği için çekme istenmez (kaynak metnine dokunulmaz).
  6. Envelope'un `adtcore:masterLanguage`'i `sap-project.json` master_language ile aynı olmalı (`tools/msgclass.py` emsali, ADR_0005_D).
Profil: `available_on=("s4_private",)` — reçete kanıtlarının `applies_to`'su (`playbook/known-errors.md:2`, `adt-rap.md`, `adt-cds.md`).
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote
from xml.sax.saxutils import escape as _xml_escape
from xml.sax.saxutils import unescape as _xml_unescape

from sapadt import pull_state as _pull_state
from sapadt._app import profil_tool
from sapadt._conn import get_active_tier
from sapadt.guardrails import (
    GuardrailViolation,
    require_customer_namespace,
    require_tr_text,
    require_transport,
    require_writable_tier,
)

# tip → (envelope URL segmenti, kanonik kısa ad). sap_set_object_description.py:48-57 (srvb/prog ÇIKARILDI)
_ANA_URI = {
    "class": ("oo/classes", "class"), "clas": ("oo/classes", "class"),
    "bdef": ("bo/behaviordefinitions", "bdef"), "behaviordefinition": ("bo/behaviordefinitions", "bdef"),
    "srvd": ("ddic/srvd/sources", "srvd"), "servicedefinition": ("ddic/srvd/sources", "srvd"),
    "ddls": ("ddic/ddl/sources", "ddls"), "cds": ("ddic/ddl/sources", "ddls"),
    "ddlx": ("ddic/ddlx/sources", "ddlx"), "metadataextension": ("ddic/ddlx/sources", "ddlx"),
    "dcl": ("acm/dcl/sources", "dcl"), "dcls": ("acm/dcl/sources", "dcl"), "accesscontrol": ("acm/dcl/sources", "dcl"),
}
_REDDEDILEN = {
    "srvb": "SRVB açıklaması REST'te değiştirilemez (LOCK 200 → PUT 423, kaynak playbook adt-rap). Kullanıcı ADT/Eclipse'te değiştirir.",
    "servicebinding": "SRVB açıklaması REST'te değiştirilemez (LOCK 200 → PUT 423). Kullanıcı ADT/Eclipse'te değiştirir.",
    "prog": "Program açıklaması (TRDIRT) ADT ile değişmez (406/404/403 ölçüldü) → kullanıcı SE38'de değiştirir.",
    "program": "Program açıklaması (TRDIRT) ADT ile değişmez (406/404/403 ölçüldü) → kullanıcı SE38'de değiştirir.",
    "dtel": "DTEL envelope'unda açıklama İKİ kez geçer ve DTEL PUT'u ayrı reçetedir; açıklama değişikliği ölçülmedi.",
    "dataelement": "DTEL envelope'unda açıklama İKİ kez geçer ve DTEL PUT'u ayrı reçetedir; açıklama değişikliği ölçülmedi.",
}
_OLCULEN_TIP = "ddls"                       # known-errors.md:281-290 (tek ölçülen tip)
SINIF_ACIKLAMA_SINIRI = 60                  # atom.py:1094-1121 · K-16 (sınıf için ölçülen)
_KILIT_ACCEPT = "application/*,application/vnd.sap.as+xml;dataname=com.sap.adt.lock.result"
_KILIT_CAKISMA = re.compile(r"EU\s*510|locked|gesperrt|currently being edited|enqueue", re.I)
_ACIKLAMA = re.compile(r'adtcore:description="([^"]*)"')                   # sap_set_object_description.py:69
_ML = re.compile(r'adtcore:masterLanguage="([^"]*)"')
_SINIR = re.compile(r'adtcore:descriptionTextLimit="(\d+)"')
_KOK_ETIKET = re.compile(r"<(?![?!/])[^>]*>")                              # ilk öğe başlangıç etiketi (bildirim/yorum hariç)
_ETAG_V2 = re.compile(r'<entry key="T100KEY-V2">([^<\s]+)</entry>')      # :75
_ETAG_METIN = re.compile(r"object ETag (\S+) ")                            # :76
_SM12 = ("Araç enqueue kilidini SİLMEZ (Kesin Yasak C). SM12'de kendi kilidini kendin kontrol et; objeyi ADT/SE80'de açık bırakan "
         "ekranı kapat; başka biri düzenliyorsa bitmesini bekle. Sonra tekrar dene.")
_AKT_NOTU = ("Obje İNAKTİF: yeni açıklama yalnız inaktif sürümde. Kullanıcıyla kontrol et: adt_inactive_objects → "
             "adt_activate(name, object_type). Aracı yeniden koşmak düzeltmez (açıklama aynı görünür → NOOP).")


def _hata(kod: str, mesaj: str, **ek) -> dict:
    return {"ok": False, "error": kod, "message": mesaj, **ek}


def _temizle(resp: dict, adt) -> dict:
    from sapadt import redact
    from sapadt.tools.screen import _sirlar
    try:
        return redact.temizle(resp, _sirlar(adt))
    except Exception:  # noqa: BLE001 — arındırma koşamazsa ham SAP gövdesi dönmesin
        resp = dict(resp)
        resp.pop("sap_body", None)
        return resp


def _master_language() -> str | None:
    try:
        from sapadt.project import load_sap_project
        cfg, _h = load_sap_project()
        ml = (cfg or {}).get("master_language")
        return ml.strip().upper() if isinstance(ml, str) and ml.strip() else None
    except Exception:  # noqa: BLE001
        return None


def _etag_412(text: str) -> str | None:
    """sap_set_object_description.py:79-87 — çıkarılamazsa None (tahmin YOK)."""
    text = text or ""
    if "SADT_RESOURCE" in text and '<entry key="T100KEY-NO">043</entry>' in text:
        m = _ETAG_V2.search(text)
        if m:
            return m.group(1)
    m = _ETAG_METIN.search(text)
    return m.group(1) if m else None


def _kok_aciklama(govde: str):
    """(kök etiket eşleşmesi, açıklama eşleşmesi) — açıklama kök başlangıç etiketinde değilse açıklama None."""
    kok = _KOK_ETIKET.search(govde or "")
    if not kok:
        return None, None
    m = _ACIKLAMA.search(govde, kok.start(), kok.end())
    return kok, m


def _listede_mi(adt, name: str, url: str):
    """sap_set_object_description.py:122-138 — (True/False, iz) ya da okunamazsa (None, sebep)."""
    try:
        girdiler = adt.get_inactive_objects()
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}"
    kok = url.lower()
    for e in girdiler or []:
        ad = str((e or {}).get("name") or "").strip().upper()
        uri = str((e or {}).get("uri") or "").split("#", 1)[0].lower()
        if ad == name or uri == kok or uri.startswith(kok + "/"):
            return True, f"{ad} ({(e or {}).get('type')})"
    return False, ""


@profil_tool(available_on=("s4_private",))
def adt_set_description(name: str, object_type: str, description: str, transport: str) -> dict:
    """Change the short description (adtcore:description) of an existing Z/Y object: LOCK → PUT → UNLOCK → activation state → readback.

    Desteklenen tipler: class, bdef, srvd, ddls (cds), ddlx, dcl — canlı ölçüm yalnız ddls. `srvb`, `prog`, `dtel` ve diğerleri →
    `unsupported_type` (gerekçe mesajda). Obje kaynağına dokunmaz. Açıklama `master_language`'de, kullanıcıdan/spesifikasyondan gelir.

    Args:
        name: Obje adı (Z*/Y*).
        object_type: Yukarıdaki tiplerden biri.
        description: Yeni açıklama (tek satır, boş olamaz; sınıfta ≤ 60; envelope `descriptionTextLimit` varsa ona göre).
        transport: Değiştirilebilir transport (zorunlu; kilit corrNr ile alınır).

    Returns:
        {ok, name, type, object_url, changed, description_before, description_after, state: active|inactive|unknown,
         readback_verified, activation{pre_put_inactive, post_put_inactive, activated, post_activation_inactive}, etag_retry,
         http{get, lock, put, unlock, …}, live_evidence, pull_state, unlock_warning?, notice?}
    """
    tip = str(object_type or "").strip().lower()
    if tip in _REDDEDILEN:
        return _hata("unsupported_type", f"adt_set_description object_type={object_type}: {_REDDEDILEN[tip]}")
    if tip not in _ANA_URI:
        return _hata("unsupported_type",
                     f"adt_set_description object_type={object_type!r} desteklenmiyor. Desteklenen: "
                     "class, bdef, srvd, ddls (cds), ddlx, dcl (kaynak reçetenin tip tablosu; srvb/prog/dtel kanıtla dışarıda).")
    seg, kisa = _ANA_URI[tip]
    try:
        require_writable_tier(get_active_tier(), what="açıklama değiştirme")
        require_customer_namespace(name, what=kisa)
        require_transport(transport, what="açıklama değiştirme")
        require_tr_text(description if isinstance(description, str) else None, what="açıklama")
    except GuardrailViolation as gv:
        return gv.as_dict()
    yeni = description.strip()
    if "\n" in yeni or "\r" in yeni:
        return _hata("invalid_argument", "description tek satır olmalı.")
    if kisa == "class" and len(yeni) > SINIF_ACIKLAMA_SINIRI:
        return _hata("invalid_argument",
                     f"description {len(yeni)} karakter > sınıf açıklama sınırı {SINIF_ACIKLAMA_SINIRI} (ölçülen; K-16). "
                     "Kısaltmak onaylı metni değiştirir — metin sahibine sor.")
    ml = _master_language()
    if not ml:
        return _hata("master_language_unresolved",
                     "sap-project.json master_language çözülemedi — açıklamanın dili doğrulanamaz, yazma yapılmadı.")
    ad = name.strip().upper()
    obj = f"/sap/bc/adt/{seg}/{quote(ad.lower(), safe='')}"
    kanit = "measured_ddls" if kisa == _OLCULEN_TIP else "not_measured"
    temel: dict[str, Any] = {"name": ad, "type": kisa, "object_url": obj, "live_evidence": kanit}

    # ── pull-before-edit (kayıt VARSA) ────────────────────────────────────────────────────────────
    kayit, pst_hata = _pull_state.kayit_al(ad, object_type)
    if pst_hata:
        return _hata("pull_state_unreadable", f"Pull-state okunamadı: {pst_hata}. adt_get ile yeniden çek.", **temel)
    from sapadt.tools import atom as _atom
    adt = None
    try:
        client = _atom._get_client()
        adt = getattr(client, "adt_client", None) or client
    except Exception as exc:  # noqa: BLE001
        return {**_atom._err_from_exc(exc), **temel}
    if kayit is not None:
        try:
            canli = _atom._adt_get_oku(ad, object_type, True)
        except Exception as exc:  # noqa: BLE001
            canli = _atom._err_from_exc(exc)
        c = canli if isinstance(canli, dict) else {}
        if not (c.get("ok") is True and c.get("exists") in (True, False)):
            return _temizle(_hata("pull_live_read_failed",
                                  "PULL-BEFORE-EDIT: çekme kaydı var ama canlı kaynak yazmadan önce OKUNAMADI — yazma yapılmadı.",
                                  **temel, live_read={"error": c.get("error"), "message": str(c.get("message") or "")[:300]}), adt)
        if c.get("exists") is False or not isinstance(c.get("source"), str) \
                or _pull_state.ozet(c.get("source")) != kayit.get("sha256"):
            return _hata("source_changed_since_pull",
                         f"PULL-BEFORE-EDIT: obje {kayit.get('pulled_at')} tarihli çekmeden sonra SAP'de değişmiş/silinmiş — açıklama "
                         "yazılmadı. adt_get ile yeniden çek, kullanıcıya bildir.", **temel, pulled_at=kayit.get("pulled_at"))
    zaman = getattr(adt, "timeout_default", 60)
    full = adt.url + obj
    http: dict[str, Any] = {}

    # ── 1) envelope GET (:210-217) ────────────────────────────────────────────────────────────────
    try:
        with _atom._capture_stdout():
            r = adt.session.get(full, headers={"Accept": "application/*"}, timeout=zaman)
    except Exception as exc:  # noqa: BLE001
        return _temizle({**_atom._err_from_exc(exc), **temel}, adt)
    http["get"] = int(getattr(r, "status_code", 0) or 0)
    govde = str(getattr(r, "text", "") or "")
    if http["get"] == 404:
        return _hata("not_found", f"[404] obje bulunamadı: {obj}", **temel, http=http)
    if http["get"] != 200:
        return _temizle(_hata("envelope_read_failed", f"Envelope okunamadı (HTTP {http['get']}) — yazma yapılmadı.",
                              **temel, http=http, sap_body=govde[:300]), adt)
    basliklar = getattr(r, "headers", {}) or {}
    etag = basliklar.get("ETag") or basliklar.get("etag")
    ctype = (basliklar.get("Content-Type") or basliklar.get("content-type") or "").split(";")[0].strip() or "application/xml"
    kok, m = _kok_aciklama(govde)
    if m is None:
        return _hata("envelope_unrecognized",
                     "Envelope'un KÖK öğesinde adtcore:description bulunamadı — güvenli değiştirilemez (başka bir öğenin, ör. paketin "
                     "açıklamasına yazma riski). Yazma yapılmadı.", **temel, http=http)
    eski = _xml_unescape(m.group(1), {"&quot;": '"', "&apos;": "'"})
    temel["description_before"] = eski
    kok_metin = kok.group(0)
    ml_m = _ML.search(kok_metin)
    if not ml_m or not ml_m.group(1).strip():
        return _hata("master_language_unresolved",
                     "Envelope'ta adtcore:masterLanguage okunamadı — açıklamanın dili doğrulanamaz, yazma yapılmadı.", **temel, http=http)
    if ml_m.group(1).strip().upper() != ml:
        return GuardrailViolation(
            "ADR_0005_D", f"Objenin master dili {ml_m.group(1).strip().upper()} ≠ sap-project.json master_language {ml}. Açıklama "
                          "yanlış dile yazılırdı; yazma yapılmadı.").as_dict()
    if eski == yeni:
        return {"ok": True, **temel, "changed": False, "description_after": eski, "state": "unknown",
                "readback_verified": None, "http": http, "pull_state": "degismedi",
                "notice": "Açıklama zaten istenen değer — kilit alınmadı, PUT gönderilmedi (aktif/inaktif durumu ölçülmedi)."}
    sinir_m = _SINIR.search(kok_metin)
    if sinir_m and len(yeni) > int(sinir_m.group(1)):
        return _hata("description_too_long",
                     f"description {len(yeni)} karakter > objenin descriptionTextLimit {sinir_m.group(1)} — yazma yapılmadı. "
                     "Kısaltmak onaylı metni değiştirir; metin sahibine sor.", **temel, http=http)
    yeni_govde = govde[:m.start(1)] + _xml_escape(yeni, {'"': "&quot;"}) + govde[m.end(1):]
    _k2, m2 = _kok_aciklama(yeni_govde)
    if m2 is None or _xml_unescape(m2.group(1), {"&quot;": '"', "&apos;": "'"}) != yeni:
        return _hata("envelope_unrecognized", "Öznitelik değişimi doğrulanamadı (beklenmeyen envelope biçimi) — yazma yapılmadı.",
                     **temel, http=http)

    # aktive-bekleyen listesi PUT'tan ÖNCE (fark 3)
    once, once_iz = _listede_mi(adt, ad, obj)
    akt: dict[str, Any] = {"pre_put_inactive": once, "post_put_inactive": None, "activated": False,
                           "post_activation_inactive": None}
    resp: dict[str, Any] = {"ok": False, **temel, "changed": False, "description_after": None, "state": "unknown",
                            "readback_verified": None, "activation": akt, "etag_retry": False, "http": http}
    if once_iz:
        akt["pre_put_trace"] = once_iz

    def tur(etiket_etag: str | None, sonek: str) -> tuple[int | None, str]:
        """TEK LOCK → PUT → UNLOCK döngüsü (:90-119). Döner (PUT HTTP | None: kilit/PUT olmadı, gövde)."""
        handle = None
        try:
            lr = adt._request_with_csrf_retry(
                "post", full, headers={"X-sap-adt-sessiontype": "stateful", "Accept": _KILIT_ACCEPT},
                params={"_action": "LOCK", "accessMode": "MODIFY", "corrNr": transport})
            http["lock" + sonek] = int(getattr(lr, "status_code", 0) or 0)
            lt = str(getattr(lr, "text", "") or "")
            hm = re.search(r"<LOCK_HANDLE[^>]*>([^<]+)</LOCK_HANDLE>", lt)
            if not hm:
                cakisma = http["lock" + sonek] in (403, 409, 423) or bool(_KILIT_CAKISMA.search(lt))
                resp.update(error="lock_conflict" if cakisma else "lock_failed",
                            message=f"Obje kilidi alınamadı (HTTP {http['lock' + sonek]}). " + _SM12, sap_body=lt[:300])
                return None, ""
            handle = hm.group(1)
            cm = re.search(r"<CORRNR>([^<]+)</CORRNR>", lt)
            corr = cm.group(1).strip() if cm else ""
            if corr and corr.upper() != transport.strip().upper():
                resp.update(error="transport_mismatch",
                            message=f"SAP kilidi başka bir transporta bağladı (CORRNR ≠ istenen) — PUT yapılmadı, kilit bırakıldı. "
                                    "Obje hangi transportta: SE01/SE09 ya da E071 sorgusu (known-errors-adt.md K-02). Kullanıcıya bildir.")
                return None, ""
            h = dict(adt._get_headers(ctype, ctype))                           # :98
            h["X-sap-adt-sessiontype"] = "stateful"
            if etiket_etag:
                h["If-Match"] = etiket_etag
            put_izi["gonderildi"] = True          # istisna PUT sırasında gelirse sonuç BELİRSİZ sayılır
            pr = adt._request_with_csrf_retry("put", full, headers=h,
                                              params={"lockHandle": handle, "corrNr": corr or transport},
                                              data=yeni_govde.encode("utf-8"))
            http["put" + sonek] = int(getattr(pr, "status_code", 0) or 0)
            return http["put" + sonek], str(getattr(pr, "text", "") or "")
        finally:
            if handle:
                try:
                    ur = adt._request_with_csrf_retry("post", full, headers={"X-sap-adt-sessiontype": "stateful"},
                                                      params={"_action": "UNLOCK", "lockHandle": handle})
                    http["unlock" + sonek] = int(getattr(ur, "status_code", 0) or 0)
                    if http["unlock" + sonek] not in (200, 204):
                        resp["unlock_warning"] = f"UNLOCK HTTP {http['unlock' + sonek]}. " + _SM12
                except Exception:  # noqa: BLE001 — kilit bırakma hatası yazma sonucunu değiştirmez
                    resp["unlock_warning"] = "UNLOCK başarısız. " + _SM12

    put_izi = {"gonderildi": False}
    try:
        durum, metin = tur(etag, "")
        if durum == 412:                                                        # :248-276
            sunucu = _etag_412(metin)
            if not sunucu:
                resp.update(error="put_precondition_failed", sap_body=metin[:300],
                            message="PUT 412 ama gövdeden sunucunun beklediği ETag çıkarılamadı — retry yapılmadı (K-19).")
                return _temizle(resp, adt)
            if sunucu == etag:
                resp.update(error="put_precondition_failed",
                            message="PUT 412 ve sunucunun beklediği ETag gönderilenle aynı — retry anlamsız, yapılmadı.")
                return _temizle(resp, adt)
            with _atom._capture_stdout():
                taze = adt.session.get(full, headers={"Accept": "application/*"}, timeout=zaman)
            http["get_before_retry"] = int(getattr(taze, "status_code", 0) or 0)
            if http["get_before_retry"] != 200 or str(getattr(taze, "text", "") or "") != govde:
                resp.update(error="envelope_changed_since_read",
                            message="PUT 412 ve envelope ilk okumadan beri DEĞİŞMİŞ ya da yeniden okunamadı — eşzamanlı bir değişikliğin "
                                    "üzerine yazmamak için retry yapılmadı.")
                return _temizle(resp, adt)
            resp["etag_retry"] = True
            durum, metin = tur(sunucu, "_retry")
            if durum == 412:
                resp.update(error="put_precondition_failed", sap_body=metin[:300],
                            message="Retry de 412 — ikinci retry yok (döngü koruması).")
                return _temizle(resp, adt)
        if durum is None:
            return _temizle(resp, adt)
        if durum not in (200, 204):                                             # :277-282
            resp.update(error="put_failed", message=f"Açıklama PUT'u reddedildi (HTTP {durum}).", sap_body=metin[:300])
            if durum == 423 and hasattr(adt, "put_423_diagnosis"):
                try:
                    resp["diagnosis_423"] = adt.put_423_diagnosis(obj, transport)
                except Exception:  # noqa: BLE001
                    pass
            return _temizle(resp, adt)
    except Exception as exc:  # noqa: BLE001
        e = _atom._err_from_exc(exc)
        resp.update(error=e.get("error"), message=e.get("message"))
        if put_izi["gonderildi"]:
            resp["notice"] = "PUT sırasında istisna — açıklamanın yazılıp yazılmadığı BELİRSİZ; adt_get ile metadata'yı oku."
        return _temizle(resp, adt)

    # ── yazıldı: pull kaydı + aktivasyon durumu + readback (:145-178) ──────────────────────────────
    resp["changed"] = True
    if kayit is not None:
        h = _pull_state.sil(ad, object_type)
        resp["pull_state"] = "silindi: açıklama PUT'u sonrası kaynağı push etmeden önce adt_get ile yeniden çek" if h is None \
            else f"silinemedi: {h}"
    else:
        resp["pull_state"] = "kayit_yok"
    sonra, sonra_iz = _listede_mi(adt, ad, obj)
    akt["post_put_inactive"] = sonra
    if sonra_iz:
        akt["post_put_trace"] = sonra_iz
    if sonra is None:
        resp.update(error="activation_state_unknown", state="unknown",
                    message="PUT oturdu ama aktive-bekleyen listesi OKUNAMADI — obje inaktif kalmış olabilir. " + _AKT_NOTU)
        return _temizle(resp, adt)
    if sonra:
        if once is not False:
            resp.update(error="activation_required", state="inactive",
                        message=("Obje PUT'tan ÖNCE de aktive-bekleyen listesindeydi" if once else
                                 "PUT'tan önce aktive-bekleyen listesi okunamadı") +
                                " — bekleyen başka bir sürümü habersiz aktive etmemek için otomatik aktivasyon YAPILMADI. " + _AKT_NOTU)
            return _temizle(resp, adt)
        try:
            with _atom._capture_stdout():
                ar = adt.activate_object(ad, obj) or {}
        except Exception as exc:  # noqa: BLE001
            ar = {"success": False, "errors": [{"message": f"{type(exc).__name__}: {exc}"}]}
        if not ar.get("success"):
            resp.update(error="activation_failed", state="inactive",
                        activation_errors=[str((x or {}).get("message", ""))[:300] for x in (ar.get("errors") or [])][:10],
                        message="Aktivasyon BAŞARISIZ. " + _AKT_NOTU)
            return _temizle(resp, adt)
        akt["activated"] = True
        tekrar, tekrar_iz = _listede_mi(adt, ad, obj)
        akt["post_activation_inactive"] = tekrar
        if tekrar is not False:
            resp.update(error="activation_not_verified", state="inactive" if tekrar else "unknown",
                        message=("Aktivasyon 'başarılı' dedi ama obje hâlâ aktive-bekleyen listesinde" if tekrar else
                                 "Aktivasyon sonrası liste okunamadı") + " (Q187 sınıfı). " + _AKT_NOTU)
            if tekrar_iz:
                akt["post_activation_trace"] = tekrar_iz
            return _temizle(resp, adt)
    try:
        with _atom._capture_stdout():
            rb = adt.session.get(full, headers={"Accept": "application/*"}, params={"version": "active"}, timeout=zaman)
        http["readback"] = int(getattr(rb, "status_code", 0) or 0)
        _kr, mr = _kok_aciklama(str(getattr(rb, "text", "") or "")) if http["readback"] == 200 else (None, None)
        simdi = _xml_unescape(mr.group(1), {"&quot;": '"', "&apos;": "'"}) if mr else None
    except Exception as exc:  # noqa: BLE001
        simdi = None
        resp["readback_reason"] = type(exc).__name__
    resp["description_after"] = simdi
    if simdi != yeni:
        resp.update(error="readback_mismatch", readback_verified=False, state="unknown",
                    message="Aktif sürümdeki açıklama beklenen değer DEĞİL (ya da okunamadı) — PUT aktif sürüme oturmadı.")
        return _temizle(resp, adt)
    resp.update(ok=True, readback_verified=True, state="active")
    resp.pop("error", None)
    resp.pop("message", None)
    return _temizle(resp, adt)
