# -*- coding: utf-8 -*-
"""adt_textpool_write (Z39, aXet 2026-09-21) — klasik program metin havuzu: metin sembolleri + seçim metinleri.
adt_textpool_read (Z39 kalanı, 2026-09-26) — aynı uçların salt-okur okuması (dosyanın sonunda; kilit/PUT yok).

Neden ayrı araç: `adt_push_source` yalnız `source/main`'i taşır; metin öğeleri ayrı uçta, ayrı kilitle yaşar.
Yüklenmezse `TEXT-xxx` ve seçim ekranı etiketleri çalışma anında BOŞ görünür (program aktif ve sözdizimi temiz
olsa bile).

Akış (kaynak çekirdek `playbook/adt-programs.md` §23.7 "6 zorunlu cephe" + `scripts/push_textpool.py`):
  ön kontrol (ağsız) → her alt kaynak için GET (ETag + canlı içerik; silinecek giriş varsa izin şart)
  → KİLİT metin öğeleri kaynağında (`/textelements/programs/<prog>`, REPT — program kilidi DEĞİL; transport ile)
  → etkin transport kilit yanıtından → her alt kaynağa PUT (If-Match + lockHandle + corrNr; `_get_headers` +
  `_request_with_csrf_retry` = CSRF + stateful) → gerçek kilit tutamacı ŞART → UNLOCK (finally, aktivasyondan
  ÖNCE: aksi hâlde PROG/PX aktivasyonu aracın kendi kilidine çarpar) → PROG/P aktivasyonu → AÇIK PROG/PX
  aktivasyonu (program zaten aktifse PROG/P yalnız generation koşar ve metin havuzunu terfi ettirmez) → PX sonrası
  bağımsız worklist sondası → `?version=active` readback: her beklenen giriş aktif sürümde aynı metinle var mı
  (`=?` yer tutucu = FAIL).
"""
from __future__ import annotations

from typing import Any

from sapadt._app import profil_tool
from sapadt._conn import get_active_tier
from sapadt.guardrails import (
    GuardrailViolation,
    require_customer_namespace,
    require_transport,
    require_writable_tier,
)

_KOK = "/sap/bc/adt/textelements/programs/"
_SAHTE_TUTAMAC = ("NO_LOCK_SUPPORT", "IMPLICIT_LOCK", None, "")


def _get_client():
    from sapadt.tools.atom import _get_client as _g
    return _g()


def _err_from_exc(exc: Exception) -> dict:
    from sapadt.tools.atom import _err_from_exc as _e
    return _e(exc)


def _capture():
    from sapadt.tools.composite import _capture as _c
    return _c()


def _px_govdesi(prog_l: str, prog_u: str) -> str:
    return ('<?xml version="1.0" encoding="UTF-8"?>'
            '<adtcore:objectReferences xmlns:adtcore="http://www.sap.com/adt/core">'
            f'<adtcore:objectReference adtcore:uri="{_KOK}{prog_l}"'
            f' adtcore:type="PROG/PX" adtcore:name="{prog_u}"/>'
            '</adtcore:objectReferences>')


# Profil: reçete kaynak çekirdekte yalnız s4_private sistemde canlı ölçüldü (kanıtsız genişletme yok).
@profil_tool(available_on=("s4_private",))
def adt_textpool_write(
    name: str,
    transport: str,
    symbols: list[dict] | None = None,
    selections: list[dict] | None = None,
    allow_remove: bool = False,
) -> dict:
    """Write a classic program's text pool (text symbols + selection texts), activate PROG/P + PROG/PX, verify active.

    Args:
        name: Z/Y program adı.
        transport: Değiştirilebilir İSTEK numarası (zorunlu; kilit yanıtındaki CORRNR otoritedir).
        symbols: Metin sembolleri — [{"key": "B01", "text": "Seçim kriterleri", "max_length"?: 30}].
            `key` tam 3 harf/rakam (kodda `TEXT-b01`). `max_length` verilmezse metnin uzunluğu; metin onu aşarsa
            ağa gitmeden BLOCKER (SAP DS512).
        selections: Seçim metinleri — [{"name": "P_BUKRS", "text": "Şirket kodu"}]; ad en çok 8 karakter.
            DDIC'ten türeyen etiket kullanılmaz; verilen metin yazılır.
        allow_remove: Alt kaynak PUT ile BÜTÜNÜYLE değişir. Canlıda olup girdide olmayan giriş SİLİNECEKSE
            varsayılan `false` → `would_remove_entries` (hiçbir şey yazılmaz). Silmeyi kullanıcı onayladıysa `true`.
            Mevcut girişleri korumak için onları da girdiye ekle.
        Başlıklar (headings) desteklenmez: yazım biçimi kaynakta belgelenmedi.

    Returns:
        {ok, name, type:'prog', written:[PUT'u başarılı alt kaynaklar; yazılmadıysa []], steps:{pre_flight, read,
         lock, put, unlock, activate_prog{ok, outcome: activated|generation_only|failed}, activate_px,
         activation_final{ok, sonda, kalan_inaktif}, readback}, effective_transport, activation_notice?, error?, message?}
        `ok` = aktif sürüm readback'i doğru VE PX sonrası worklist'te program/metin havuzu kalmadı (ölçülemezse
        yalnız readback + `activation_notice`). `activate_prog.outcome=generation_only` beklenen durumdur (program
        zaten aktif); hükmü `activation_final` verir.
        error: preflight_blocker · read_failed · not_found · would_remove_entries · lock_failed · put_failed ·
        readback_mismatch · activation_incomplete
    """
    try:
        require_writable_tier(get_active_tier(), what="text pool write")
        require_customer_namespace(name, what="program", object_type="prog")
        require_transport(transport, what="text pool write")
    except GuardrailViolation as gv:
        return gv.as_dict()
    from utils import textpool as tp  # type: ignore
    steps: dict[str, Any] = {}
    on = tp.on_kontrol(symbols, selections)
    steps["pre_flight"] = on
    temel = {"name": name.upper(), "type": "prog", "steps": steps}
    if on["verdict"] == "BLOCKER":
        return {"ok": False, "error": "preflight_blocker", **temel,
                "message": "Metin havuzu ön kontrolü BLOCKER (SAP'ye gidilmedi): "
                           + "; ".join(f["message"] for f in on["findings"])}
    alt_girdi = [(a, g) for a, g in (("symbols", symbols), ("selections", selections)) if g]
    yuk = {a: (tp.sembol_yuku(g) if a == "symbols" else tp.secim_yuku(g)) for a, g in alt_girdi}
    # `written` YALNIZ PUT'u başarılı alt kaynakları sayar (canlı 2026-09-21: `would_remove_entries` ile hiçbir şey
    # yazılmadan dönüldüğünde yanıt `written:["symbols"]` gösteriyordu).
    temel["written"] = []

    try:
        client = _get_client()
    except Exception as exc:  # noqa: BLE001
        return {**_err_from_exc(exc), **temel}
    adt = getattr(client, "adt_client", None) or client
    prog_l, prog_u = name.lower(), name.upper()
    kok = adt.url.rstrip("/") + _KOK + prog_l
    te_url = _KOK + prog_l

    # 1) Canlı oku: ETag + silinecek giriş kontrolü (yazmadan ÖNCE).
    etag: dict[str, str] = {}
    steps["read"] = {}
    for alt, g in alt_girdi:
        try:
            r = adt._request_with_csrf_retry("get", f"{kok}/source/{alt}",
                                             headers=adt._get_headers(accept_type=tp.ALT_KAYNAK_CT[alt]), timeout=30)
        except Exception as exc:  # noqa: BLE001
            steps["read"][alt] = {"ok": False, "reason": f"exception:{type(exc).__name__}"}
            return {"ok": False, "error": "read_failed", **temel,
                    "message": f"{alt} canlı okunamadı — silinecek giriş kontrolü yapılamadı, yazma denenmedi."}
        kod = int(getattr(r, "status_code", 0) or 0)
        if kod == 404:
            steps["read"][alt] = {"ok": False, "http_status": 404}
            return {"ok": False, "error": "not_found", **temel,
                    "message": f"{prog_u} metin öğeleri ucu 404 — program yok ya da henüz yaratılmadı."}
        if kod != 200:
            steps["read"][alt] = {"ok": False, "http_status": kod, "body_head": str(getattr(r, "text", ""))[:300]}
            return {"ok": False, "error": "read_failed", **temel,
                    "message": f"{alt} canlı okuma HTTP {kod} — yazma denenmedi."}
        etag[alt] = (getattr(r, "headers", {}) or {}).get("ETag", "")
        sil = tp.silinecekler(alt, r.text or "", g)
        steps["read"][alt] = {"ok": True, "etag_present": bool(etag[alt]), "would_remove": sil}
    silinecek = {a: v["would_remove"] for a, v in steps["read"].items() if v.get("would_remove")}
    if silinecek and not allow_remove:
        return {"ok": False, "error": "would_remove_entries", **temel, "would_remove": silinecek,
                "message": ("PUT alt kaynağı BÜTÜNÜYLE değiştirir; canlıdaki şu girişler silinecekti: "
                            + "; ".join(f"{a}: {', '.join(v)}" for a, v in silinecek.items())
                            + ". Korumak için girdiye ekle; silmek kullanıcı onaylıysa allow_remove=true. Yazılmadı.")}

    # 2) Kilit — metin öğeleri (REPT) kaynağında.
    try:
        with _capture() as buf:
            tutamac = adt.lock_object(te_url, access_mode="MODIFY", transport=transport)
        steps["lock"] = {"ok": tutamac not in _SAHTE_TUTAMAC, "log": buf.getvalue().strip()[:400]}
    except Exception as exc:  # noqa: BLE001
        steps["lock"] = {"ok": False, **_err_from_exc(exc)}
        if getattr(exc, "status_code", None) is None:
            # Z50 ⓒ: HTTP yanıtı YOK (ağ istisnası) — LOCK isteği SAP'ye ulaşıp kilit alınmış olabilir.
            return {"ok": False, "error": "lock_failed", "outcome_uncertain": "lock", **temel,
                    "message": "Metin öğeleri kilit isteği yanıt yerine AĞ İSTİSNASI verdi — kilidin alınıp alınmadığı "
                               "BELİRSİZ (hiçbir şey yazılmadı). Kilit silinmez (Kesin Yasak C); kullanıcı SM12'de "
                               "kendi kilidine bakar, sonra tekrar dener."}
        return {"ok": False, "error": "lock_failed", **temel,
                "message": "Metin öğeleri kilidi alınamadı — hiçbir şey yazılmadı. Kilit silinmez (Kesin Yasak C); "
                           "sahibini kullanıcıya bildir."}
    if tutamac in _SAHTE_TUTAMAC:
        return {"ok": False, "error": "lock_failed", **temel,
                "message": f"Gerçek kilit tutamacı alınamadı ({tutamac}) — metin öğeleri PUT'u tutamaç ister; "
                           "yazılmadı."}
    etkin = getattr(adt, "_last_lock_effective_transport", None) or transport
    temel["effective_transport"] = etkin
    if etkin != transport:
        steps["lock"]["transport_note"] = f"SAP farklı transport bildirdi: istenen={transport} → etkin={etkin}"

    # 3) PUT her alt kaynak; UNLOCK finally (aktivasyondan ÖNCE).
    steps["put"] = {}
    put_hatasi = None
    put_belirsiz = None   # Z50 ⓒ: PUT isteği gitti, yanıt yerine istisna geldi → yazıldığı BELİRSİZ
    try:
        for alt, _g in alt_girdi:
            put_belirsiz = alt
            h = adt._get_headers(accept_type=tp.ALT_KAYNAK_CT[alt],
                                 content_type=tp.ALT_KAYNAK_CT[alt] + "; charset=utf-8")
            if etag.get(alt):
                h["If-Match"] = etag[alt]
            r = adt._request_with_csrf_retry("put", f"{kok}/source/{alt}", headers=h,
                                             params={"corrNr": etkin, "lockHandle": tutamac},
                                             data=yuk[alt].encode("utf-8"), timeout=60)
            put_belirsiz = None
            kod = int(getattr(r, "status_code", 0) or 0)
            steps["put"][alt] = {"ok": kod in (200, 201, 204), "http_status": kod}
            if kod in (200, 201, 204):
                temel["written"].append(alt)
            else:
                steps["put"][alt]["body_head"] = str(getattr(r, "text", ""))[:600]
                put_hatasi = alt
                break
    except Exception as exc:  # noqa: BLE001
        put_hatasi = put_hatasi or put_belirsiz or "exception"
        steps["put"]["exception"] = _err_from_exc(exc)
        if put_belirsiz and getattr(exc, "status_code", None) is None:
            steps["put"][put_belirsiz] = {"ok": None, "outcome_uncertain": True}
        else:
            put_belirsiz = None
    finally:
        try:
            with _capture():
                acildi = adt.unlock_object(te_url, tutamac)
            steps["unlock"] = {"ok": bool(acildi)}
        except Exception as exc:  # noqa: BLE001
            steps["unlock"] = {"ok": False, "reason": f"exception:{type(exc).__name__}"}
    kilit_uyari = None if steps["unlock"]["ok"] else (
        "Kilit AÇILAMADI — sonraki yazımlar kilit hatası alabilir. Kilit silinmez (Kesin Yasak C); kullanıcıya bildir.")
    if put_hatasi and put_belirsiz:
        out = {"ok": False, "error": "put_failed", "outcome_uncertain": "put", **temel,
               "message": f"{put_belirsiz} PUT isteği gönderildi ama yanıt yerine AĞ İSTİSNASI geldi — yazılıp "
                          "yazılmadığı BELİRSİZ (inaktif sürümde yeni metin olabilir); aktivasyon denenmedi. Kör tekrar "
                          "YAPMA: önce canlı metni oku (aynı araç önce canlıyı okur; silinecek giriş kontrolü yeniden koşar)."}
        if kilit_uyari:
            out["unlock_warning"] = kilit_uyari
        return out
    if put_hatasi:
        out = {"ok": False, "error": "put_failed", **temel,
               "message": f"{put_hatasi} PUT'u başarısız — aktivasyon denenmedi. steps.put'a bak "
                          "(406 DS512 = biçim/uzunluk; 423 = kilit/transport)."}
        if kilit_uyari:
            out["unlock_warning"] = kilit_uyari
        return out

    # 4) Aktivasyon: PROG/P, ardından AÇIK PROG/PX.
    # PROG/P adımının ANLAMI (kaynak çekirdek push_textpool.py 4a/4b): programın kaynağını bu araç DEĞİŞTİRMEZ;
    # adım program yükünü yeniden üretir ve program inaktifse onu aktive eder. Program ZATEN aktifse SAP yalnız
    # generation koşar (`activationExecuted=false` + `generationExecuted=true`) ve metin havuzunu TERFİ ETTİRMEZ —
    # o işi AÇIK PROG/PX aktivasyonu yapar. Bu yüzden `yalniz_generation` bu adımda BEKLENEN sonuçtur (canlı
    # 2026-09-21, DEV: her çağrıda worklist PROG/P + PROG/PX'i inaktif gösterdi, PX aktivasyonu terfi ettirdi) —
    # FAIL değildir; hükmü PX'ten SONRAKİ bağımsız worklist sondası (`activation_final`) verir. Gövdede gerçek
    # E/A mesajı varsa (ör. sözdizimi hatası) adım `ok:false` kalır ve son sonda PROG/P'yi inaktif görürse nihai
    # `ok:false` (`activation_incomplete`).
    prog_url = f"/sap/bc/adt/programs/programs/{prog_l}"
    try:
        with _capture():
            akt = adt.activate_object(prog_u, prog_url)
        akt = akt or {}
        if akt.get("success"):
            steps["activate_prog"] = {"ok": True, "outcome": "activated"}
        elif akt.get("hukum_sebep") == "yalniz_generation":
            dog = akt.get("aktivasyon_dogrulama") or {}
            steps["activate_prog"] = {
                "ok": None, "outcome": "generation_only", "decided_by": "activation_final",
                "pending_before_px": ["%s (%s)" % (k.get("name"), k.get("type"))
                                      for k in dog.get("kalan_inaktif") or []],
                "note": "Program zaten aktif: SAP yalnız generation koştu (beklenen). Metin havuzu PROG/PX adımında "
                        "terfi eder; hüküm steps.activation_final'da."}
        else:
            steps["activate_prog"] = {"ok": False, "outcome": "failed", "reason": akt.get("hukum_sebep"),
                                      "errors": [e.get("message") for e in akt.get("errors", [])][:10]}
    except Exception as exc:  # noqa: BLE001
        steps["activate_prog"] = {"ok": False, "outcome": "failed", **_err_from_exc(exc)}
    try:
        from sap_adt_lib import aktivasyon_govde_hukmu  # type: ignore
        ph = adt._get_headers(accept_type="application/vnd.sap.adt.objectactivation.result.v1+xml",
                              content_type="application/xml")
        pr = adt._request_with_csrf_retry("post", adt.url.rstrip("/") + "/sap/bc/adt/activation", headers=ph,
                                          data=_px_govdesi(prog_l, prog_u).encode("utf-8"),
                                          params={"method": "activate", "preauditRequested": "true"}, timeout=60)
        hk = aktivasyon_govde_hukmu(getattr(pr, "text", ""))
        steps["activate_px"] = {"http_status": int(getattr(pr, "status_code", 0) or 0), "body_verdict": hk["hukum"],
                                "reason": hk["sebep"], "note": "Nihai hüküm aktif sürüm readback'indedir."}
    except Exception as exc:  # noqa: BLE001
        steps["activate_px"] = {"ok": False, **_err_from_exc(exc)}

    # 4c) PX SONRASI bağımsız worklist sondası — program + metin havuzu hâlâ aktive-bekleyen listesinde mi?
    #     (Tek kaynak: `aktivasyon_worklist_sondasi`; ölçülemezse None = "temiz" DEĞİL, görünür not.)
    try:
        from sap_adt_lib import aktivasyon_worklist_sondasi  # type: ignore
        son_ok, son_sonda, kalan = aktivasyon_worklist_sondasi(adt, [
            {"uri": prog_url, "name": prog_u, "type": "PROG/P"},
            {"uri": te_url, "name": prog_u, "type": "PROG/PX"}])
    except Exception as exc:  # noqa: BLE001
        son_ok, son_sonda, kalan = None, f"unavailable:{type(exc).__name__}", []
    steps["activation_final"] = {"ok": son_ok, "sonda": son_sonda,
                                 "kalan_inaktif": ["%s (%s)" % (k.get("name"), k.get("type")) for k in kalan]}
    if steps["activate_prog"].get("outcome") == "generation_only":
        steps["activate_prog"]["ok"] = son_ok

    # 5) Readback — ?version=active (working sürüm PUT'lanan metni gösterip yanıltır).
    steps["readback"] = {}
    tamam = True
    for alt, g in alt_girdi:
        try:
            r = adt._request_with_csrf_retry("get", f"{kok}/source/{alt}",
                                             headers=adt._get_headers(accept_type=tp.ALT_KAYNAK_CT[alt]),
                                             params={"version": "active"}, timeout=30)
            kod = int(getattr(r, "status_code", 0) or 0)
        except Exception as exc:  # noqa: BLE001
            steps["readback"][alt] = {"ok": False, "reason": f"exception:{type(exc).__name__}"}
            tamam = False
            continue
        if kod != 200:
            steps["readback"][alt] = {"ok": False, "http_status": kod}
            tamam = False
            continue
        steps["readback"][alt] = tp.readback_karsilastir(alt, r.text or "", g,
                                                         silinecek=steps["read"][alt].get("would_remove"))
        tamam = tamam and steps["readback"][alt]["ok"]
    eksik_aktivasyon = son_ok is False
    out = {"ok": tamam and not eksik_aktivasyon, **temel}
    if kilit_uyari:
        out["unlock_warning"] = kilit_uyari
    if son_ok is None:
        out["activation_notice"] = (f"PX sonrası worklist sondası ÖLÇÜLEMEDİ ({son_sonda}) — program/metin havuzunun "
                                    "aktive-bekleyen listesinde kalmadığı DOĞRULANMADI; hüküm yalnız aktif sürüm "
                                    "readback'ine dayanıyor. `adt_inactive_objects` ile elle bak.")
    if tamam and son_ok is None and steps["activate_prog"].get("outcome") == "failed":
        # Bug gate (2026-09-21): PROG/P gövdesinde GERÇEK hata (E mesajı / istisna) + PX sonrası sonda ölçülemedi →
        # eskiden `ok:true` (yalnız readback'e dayanıyordu). Program aktivasyon hatası doğrulanmadan başarı sayılmaz.
        hatalar = steps["activate_prog"].get("errors") or [
            steps["activate_prog"].get("message") or steps["activate_prog"].get("reason") or "ayrıntı yok"]
        out["ok"] = False
        out["error"] = "activation_unverified"
        out["message"] = ("Metinler aktif sürümde doğru görünüyor AMA program aktivasyonu HATA verdi ("
                          + "; ".join(str(h) for h in hatalar if h)
                          + ") ve PX sonrası worklist sondası ÖLÇÜLEMEDİ — aktivasyonun tamamlandığı doğrulanamadı. "
                            "steps.activate_prog'u düzelt, adt_inactive_objects ile bak.")
    if tamam and eksik_aktivasyon:
        out["error"] = "activation_incomplete"
        out["message"] = ("Metinler aktif sürümde doğru AMA PX sonrası worklist şunları hâlâ inaktif gösteriyor: "
                          + ", ".join(steps["activation_final"]["kalan_inaktif"])
                          + " — program kaynağının inaktif sürümü ya da aktivasyon hatası olabilir; "
                            "steps.activate_prog ve steps.activation_final'a bak.")
    if not tamam:
        out["error"] = "readback_mismatch"
        out["message"] = ("Metinler yazıldı ama AKTİF sürümde doğrulanamadı (eksik / farklı / `=?` / silinmesi onaylanan "
                          "giriş hâlâ duruyor: steps.readback.*.remove_not_applied) — metin havuzu "
                          "terfi etmemiş olabilir; ekranda metin görünmez. steps.activate_px ve steps.readback'e bak.")
    return out


# ═══════════════════════════════════════ adt_textpool_read ═══════════════════════════════════════
# Z39 kalanı (2026-09-26): bağımsız OKUMA aracı. Yazma aracının readback'i yalnız KENDİ yazdığı girişleri
# kıyaslıyordu; metin havuzunun ne içerdiğini (başka biri yazdıysa, yazma hiç yapılmadıysa) gösteren salt-okur
# yol yoktu. Okuma yolu yazma aracınınkiyle AYNIDIR: `_KOK` + `/source/<alt>`, alt kaynağın KENDİ Accept tipi
# (`tp.ALT_KAYNAK_CT`; çekirdek §23.7 okuma reçetesi, canlı-doğrulanmış 2026-07-31: `text/plain` → 406),
# `_request_with_csrf_retry` + `_get_headers`. Kilit YOK, PUT/POST YOK.
_OKUMA_SURUMLERI = {"active": {"version": "active"}, "working": {}}
_OKUMA_KAPSAM_DISI = ("headings (liste başlıkları): okuma Accept tipi kaynakta belgelenmedi — ÖLÇÜLEMEDİ",
                      "metin sembolünün / seçim adının programda kullanılıp kullanılmadığı",
                      "programın varlığı ve aktifliği (404 yalnız metin öğeleri ucu için)")


def _prog_adi_gecerli(name) -> bool:
    import re
    return isinstance(name, str) and bool(re.fullmatch(r"(?:/[A-Za-z0-9_]+/)?[A-Za-z0-9_]+", name)) \
        and len(name) <= 40


# Profil: yazma aracıyla AYNI kanıt tabanı (uç reçetesi yalnız s4_private sistemde canlı ölçüldü).
@profil_tool(available_on=("s4_private",))
def adt_textpool_read(name: str, version: str = "active", parts: list[str] | None = None) -> dict:
    """Read a classic program's text pool (text symbols + selection texts). READ-ONLY — no lock, no write.

    Args:
        name: Program adı (Z/Y ya da standart; okuma). En çok 40 karakter; `/ad-alanı/` önekli olabilir.
        version: `active` (varsayılan; ekranda görünen = aktif sürüm) · `working` (sürüm parametresiz GET — inaktif
            sürüm varsa onu gösterir; yazma sonrası "yazıldı ama terfi etmedi" ayrımı için `active` ile kıyasla).
        parts: `["symbols", "selections"]` alt kümesi (varsayılan ikisi). `headings` desteklenmez.

    Returns:
        {ok, name, type:'prog', version, parts:{<alt>: {ok, http_status, count, entries}}, checked, not_checked,
         error?, message?}
        symbols.entries    : [{key, text, max_length}]
        selections.entries : [{name, text, ddic_reference, placeholder}] (`placeholder` = metin `?`: aktif sürümde
                             terfi etmemiş seçim metni). Tanınmayan `@…` satırı girişte `annotations` olarak kalır.
        error: invalid_argument (ağa gidilmedi) · not_found (metin öğeleri ucu 404) · read_failed (HTTP ≠ 200 ya da
               istisna; diğer alt kaynağın sonucu `parts` içinde korunur)
    """
    from utils import textpool as tp  # type: ignore
    alt_liste = list(tp.ALT_KAYNAK_CT) if parts is None else parts
    hata = None
    if not _prog_adi_gecerli(name):
        hata = f"name={name!r}: program adı harf/rakam/_ (isteğe bağlı /ad-alanı/ öneki), en çok 40 karakter olmalı."
    elif version not in _OKUMA_SURUMLERI:
        hata = f"version={version!r}: {' | '.join(_OKUMA_SURUMLERI)} olmalı."
    elif not isinstance(alt_liste, list) or not alt_liste:
        hata = f"parts={parts!r}: {list(tp.ALT_KAYNAK_CT)} alt kümesi (boş olmayan liste) olmalı."
    else:
        yanlis = [a for a in alt_liste if a not in tp.ALT_KAYNAK_CT]
        if yanlis:
            hata = (f"parts içinde desteklenmeyen alt kaynak: {yanlis} — desteklenen {list(tp.ALT_KAYNAK_CT)}. "
                    + " ".join(v for k, v in tp.DESTEKLENMEYEN.items() if k in yanlis))
    temel = {"name": str(name).strip().upper(), "type": "prog", "version": version,
             "checked": [f"{a} ({version})" for a in alt_liste] if not hata else [],
             "not_checked": list(_OKUMA_KAPSAM_DISI)}
    if hata:
        return {"ok": False, "error": "invalid_argument", **temel, "message": hata + " SAP'ye gidilmedi."}

    from urllib.parse import quote
    try:
        client = _get_client()
    except Exception as exc:  # noqa: BLE001
        return {**_err_from_exc(exc), **temel}
    adt = getattr(client, "adt_client", None) or client
    kok = adt.url.rstrip("/") + _KOK + quote(name.lower(), safe="")
    sonuc: dict[str, dict] = {}
    for alt in dict.fromkeys(alt_liste):
        try:
            r = adt._request_with_csrf_retry("get", f"{kok}/source/{alt}",
                                             headers=adt._get_headers(accept_type=tp.ALT_KAYNAK_CT[alt]),
                                             params=dict(_OKUMA_SURUMLERI[version]), timeout=30)
        except Exception as exc:  # noqa: BLE001
            sonuc[alt] = {"ok": False, "reason": f"exception:{type(exc).__name__}: {exc}"[:300]}
            continue
        kod = int(getattr(r, "status_code", 0) or 0)
        if kod != 200:
            sonuc[alt] = {"ok": False, "http_status": kod, "body_head": str(getattr(r, "text", ""))[:300]}
            continue
        g = tp.girisler(alt, r.text or "")
        sonuc[alt] = {"ok": True, "http_status": 200, "count": len(g), "entries": g}
    temel["parts"] = sonuc
    if any(v.get("http_status") == 404 for v in sonuc.values()):
        return {"ok": False, "error": "not_found", **temel,
                "message": f"{temel['name']} metin öğeleri ucu 404 — program yok ya da henüz yaratılmadı."}
    if not all(v["ok"] for v in sonuc.values()):
        return {"ok": False, "error": "read_failed", **temel,
                "message": "Metin havuzu okunamadı: " + "; ".join(
                    f"{a}: HTTP {v.get('http_status')}" if "http_status" in v else f"{a}: {v.get('reason')}"
                    for a, v in sonuc.items() if not v["ok"]) + ". Okunabilen alt kaynaklar `parts` içinde."}
    return {"ok": True, **temel}
