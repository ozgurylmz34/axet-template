# -*- coding: utf-8 -*-
"""BAdI enhancement spot (ENHS/XSB) + BAdI tanımı — okuma (`adt_badi_spot_read`) ve yazma (`adt_badi_spot_write`).

KAYNAK: kaynak çekirdek #413/#415 (2026-11-08/11; canlı ölçümler bir geliştirme sisteminde, SAP_BASIS 758) — lib
yardımcıları `sap_adt_lib` `enhs_*` + `SAPADTClient.get/create/write/activate_enhancement_spot`; akış kaynak
çekirdeğin CLI'ından (bu araçlar onun aXet yüzüdür). Reçete + tuzaklar: `references/enhancement-spot-badi.md`.

AKIŞ (yazma): ad denetimi (spot + her BAdI; ADR 0005-A, ≤ 30 karakter) → GET → [404 ise BOŞ kabuk POST, paket +
açıklama zorunlu] → GET belgesini modele ayrıştır → `masterSystem=SAP` RED → modellenmeyen alan varsa RED (TAM-belge
PUT onu silerdi) → YALNIZ verilen tanımlar eklenir/güncellenir (`enhs_spec_uygula`), kaldırma yalnız `remove_badis`
ile → kilit → KİLİT ALTINDA yeniden okuma (TOCTOU: araya giren değişiklik → yazma YOK) → TAM belge PUT → unlock
(finally) → aktivasyon (hüküm: aktivasyon `success` + worklist sondası + sürümsüz GET) → readback kıyası.

KAYNAKTAN BİLİNÇLİ FARKLAR:
  1. PULL-BEFORE-EDIT (aXet): var olan spot'a yazmadan önce `adt_badi_spot_read` kaydı şarttır; yazma anındaki
     canlı model özeti kayıttan farklıysa `source_changed_since_pull` (lib'in kilit-altı taban kıyası ayrıca koşar).
     Spot YOKSA (404) kayıt aranmaz — üzerine yazılacak bir şey yoktur; ilk yaratım paket + açıklama ister.
  2. Kaynak CLI'ın tekil alan bayrakları (filtre/örnek sınıf/fallback KALDIRMA) bu araçta YOK: ekleme/güncelleme
     `definitions` (kaynağın `--spec` biçimi), tanım kaldırma `remove_badis`. Diğer kaldırmalar kapsam dışı.
  3. Profil: `available_on=("s4_private",)` — ölçüm yalnız bu profilde.
"""
from __future__ import annotations

import json
from typing import Any

from sapadt import pull_state as _pull_state
from sapadt._app import profil_tool
from sapadt._conn import get_active_tier
from sapadt.guardrails import (
    GuardrailViolation,
    require_transport,
    require_writable_tier,
)

_TIP = "enhancementspot"     # pull_state anahtarı: object_types kanonik adı


def _hata(kod: str, mesaj: str, **ek) -> dict:
    return {"ok": False, "error": kod, "message": mesaj, **ek}


def _lib():
    import sap_adt_lib as L  # type: ignore
    return L


def _adt():
    from sapadt.tools import atom as _atom
    client = _atom._get_client()
    return getattr(client, "adt_client", None) or client


def _temizle(resp: dict, adt) -> dict:
    from sapadt import redact
    from sapadt.tools.screen import _sirlar
    try:
        return redact.temizle(resp, _sirlar(adt))
    except Exception:  # noqa: BLE001 — arındırma koşamazsa ham SAP gövdesi dönmesin
        return {k: v for k, v in resp.items() if k not in ("sap_body", "document")}


def model_metni(model: dict) -> str:
    """Pull kaydı için kanonik metin: spot alanları (sürüm HARİÇ — aktivasyon değiştirir) + tanımlar (JSON,
    sıralı anahtar). Kayıt ve yazma anı kıyası AYNI fonksiyondan geçer (`pull_state.ozet`)."""
    spot = {k: v for k, v in (model.get("spot") or {}).items() if k != "version"}
    return json.dumps({"spot": spot, "tanimlar": model.get("tanimlar") or []}, ensure_ascii=False, sort_keys=True)


def _ad_denetimi(L, spot: str, badi_adlari) -> dict | None:
    hatalar = L.enhs_ad_denetimi(spot, badi_adlari)
    if hatalar:
        return GuardrailViolation("ADR_0005_A", "; ".join(hatalar), name=spot).as_dict()
    return None


def _oku(adt, L, spot: str) -> tuple[str, Any]:
    """GET → ('yok', None) | ('model', model) | ('hata', dict)."""
    try:
        r = adt.get_enhancement_spot(spot)
    except Exception as exc:  # noqa: BLE001 — okunamadı ≠ yok
        return "hata", _hata("read_failed", f"Spot okunamadı ({type(exc).__name__}). 'Yok' anlamına GELMEZ.")
    durum = int(getattr(r, "status_code", 0) or 0)
    if durum == 404:
        return "yok", None
    if durum != 200:
        return "hata", _hata(f"http_{durum}", "Spot okunamadı. 'Yok' anlamına GELMEZ.",
                             sap_body=(getattr(r, "text", "") or "")[:400])
    try:
        return "model", L.enhs_belgesi_ayristir(getattr(r, "content", None) or (getattr(r, "text", "") or ""))
    except Exception as exc:  # noqa: BLE001
        return "hata", _hata("parse_failed", f"Spot belgesi ayrıştırılamadı: {str(exc)[:200]}")


@profil_tool(available_on=("s4_private",))
def adt_badi_spot_read(name: str) -> dict:
    """Read a BAdI enhancement spot (ENHS/XSB) and its BAdI definitions as a model (read-only; records pull state).

    Ağ öncesi ad denetimi YOK (standart spot da okunur). `masterSystem=SAP` olan spot okunur ama `standard: true`
    döner ve yazılamaz. Spot yoksa `exists:false` (+ "yok" pull kaydı — ilk yaratım için gerekmez).
    `writable:false` + `unmodelled` = belge aracın modellemediği alan taşıyor; TAM-belge PUT o alanı silerdi →
    `adt_badi_spot_write` bu spot'a yazmaz.

    Args:
        name: Spot adı (≤ 30 karakter).

    Returns:
        {ok, name, exists, spot{name, description, package, masterSystem, version, …}, definitions[…], standard,
         writable, unmodelled[], server_extras[], pull_state}
        ⚠ `spot.version` AKTİFLİK KANITI DEĞİLDİR (inaktif spot da "active" döner — ölçüldü); aktiflik yalnız
        yazma aracının aktivasyon hükmüdür.
    """
    spot = (name or "").strip().upper()
    if not spot:
        return _hata("invalid_argument", "name boş olamaz. SAP'ye gidilmedi.")
    L = _lib()
    adt = None
    try:
        adt = _adt()
        tur, m = _oku(adt, L, spot)
    except Exception as exc:  # noqa: BLE001
        from sapadt.tools import atom as _atom
        return _atom._err_from_exc(exc)
    if tur == "hata":
        return _temizle({**m, "name": spot}, adt)
    if tur == "yok":
        h = _pull_state.kaydet_yok(spot, _TIP)
        return {"ok": True, "name": spot, "exists": False,
                "pull_state": "kaydedildi (spot yok)" if h is None else f"yazilamadi: {h}"}
    standart = (m["spot"].get("masterSystem") or "").upper() == "SAP"
    h = _pull_state.kaydet(spot, _TIP, model_metni(m))
    return _temizle({
        "ok": True, "name": spot, "exists": True, "spot": m["spot"], "definitions": m["tanimlar"],
        "standard": standart, "writable": (not standart) and not m["modellenmeyen"],
        "unmodelled": m["modellenmeyen"], "server_extras": sorted(set(m.get("sunucu_ek") or [])),
        "pull_state": "kaydedildi" if h is None else f"yazilamadi: {h}",
    }, adt)


@profil_tool(available_on=("s4_private",))
def adt_badi_spot_write(
    name: str,
    transport: str,
    definitions: list | None = None,
    remove_badis: list | None = None,
    package: str | None = None,
    description: str | None = None,
    activate: bool = True,
    dry_run: bool = False,
) -> dict:
    """Create a customer BAdI enhancement spot and/or add/update/remove its BAdI definitions (full-document PUT, built from a fresh GET).

    Var olan spot'ta önce `adt_badi_spot_read(name)` şarttır (PULL-BEFORE-EDIT). Sıra (kaynak reçete): BAdI arabirimi
    + fallback/örnek sınıflar ÖNCE aktif olmalı; BAdI'ye atıf yapan sınıflar spot aktive edildikten SONRA.

    Args:
        name: Spot adı — müşteri adı (Z/Y ya da `customer_namespaces` ile bildirilmiş `/<NS>/`), ≤ 30 karakter.
        transport: Değiştirilebilir transport (zorunlu; kilit/POST corrNr ile).
        definitions: Eklenecek/güncellenecek tanımlar: [{"badi": "<müşteri adı>", "interface": "...",
            "shorttext": "...", "coklu_kullanim": "evet|hayir", "fallback": "<sınıf>", "ornek": ["<sınıf>"],
            "filtreler": [{"ad": "...", "tip": "C|I", "kisa": "...", "dtel": "..."}]}]. Verilmeyen alan canlıdaki
            hâliyle kalır; listede olmayan tanım KORUNUR. Bilinmeyen anahtar → `invalid_argument`.
            ⚠ `coklu_kullanim: evet` ⇒ singleUse="false" (TERS eşleme).
        remove_badis: Spot'tan KALDIRILACAK BAdI tanımı adları (yalnız açık listeyle silinir).
        package / description: YALNIZ spot yoksa (yaratım) — ikisi birlikte zorunlu; var olan spot'ta canlıdan farklı
            verilirse red (paket/açıklama değişikliği bu aracın işi değil, ölçülmedi).
        activate: PUT sonrası aktive et (varsayılan true). false → spot İNAKTİF kalır (`inactive_notice`).
        dry_run: Belgeyi kurup döndürür, YAZMAZ (spot yoksa yaratılacak kabuk gövdesi döner).

    Returns:
        {ok, name, created, changes[], activated, activation{…}, readback_verified, readback_diff?, pull_state,
         lock_released, document? (dry_run)}
    """
    spot = (name or "").strip().upper()
    try:
        require_writable_tier(get_active_tier(), what="ENHS write")
        require_transport(transport, what="ENHS write")
    except GuardrailViolation as gv:
        return gv.as_dict()
    if not spot:
        return _hata("invalid_argument", "name boş olamaz. SAP'ye gidilmedi.")
    if definitions is not None and not (isinstance(definitions, list) and all(isinstance(d, dict) for d in definitions)):
        return _hata("invalid_argument", "definitions nesne listesi olmalı. SAP'ye gidilmedi.")
    if remove_badis is not None and not (isinstance(remove_badis, list)
                                         and all(isinstance(x, str) and x.strip() for x in remove_badis)):
        return _hata("invalid_argument", "remove_badis boş olmayan ad listesi olmalı. SAP'ye gidilmedi.")
    if not isinstance(activate, bool) or not isinstance(dry_run, bool):
        return _hata("invalid_argument", "activate / dry_run true/false olmalı. SAP'ye gidilmedi.")
    tanimlar = definitions or []
    kaldir = [x.strip().upper() for x in (remove_badis or [])]
    adlar = [str(d.get("badi") or "").strip().upper() for d in tanimlar] + kaldir
    cakisan = sorted(set(a for a in adlar if adlar.count(a) > 1))
    if cakisan:
        return _hata("invalid_argument", f"Aynı BAdI birden çok kez verildi: {', '.join(cakisan)}. SAP'ye gidilmedi.")
    yaratim_istegi = bool(package and description)
    if not tanimlar and not kaldir and not yaratim_istegi:
        return _hata("invalid_argument", "Değişiklik yok: definitions / remove_badis ya da yeni spot için "
                                         "package + description ver. SAP'ye gidilmedi.")
    L = _lib()
    red = _ad_denetimi(L, spot, adlar)
    if red:
        return red

    adt = None
    try:
        adt = _adt()
        tur, model = _oku(adt, L, spot)
        if tur == "hata":
            return _temizle({**model, "name": spot}, adt)
        yaratildi = False
        if tur == "yok":
            if not yaratim_istegi:
                return _hata("spot_not_found", f"Spot {spot} yok; yaratmak için package + description ver.",
                             name=spot)
            if dry_run:
                return {"ok": True, "name": spot, "dry_run": True, "created": False,
                        "document": L.enhs_bos_kabuk_govdesi(spot, description, package, getattr(adt, "language", None)),
                        "note": "Spot yok; boş kabuk yaratılacaktı (tanımlar kabuktan sonra ayrı PUT ile yazılır)."}
            try:
                y = adt.create_enhancement_spot(spot, description, package, transport)
            except Exception as exc:  # noqa: BLE001 — SAPValidationError dahil
                return _temizle(_hata("create_rejected", f"Spot yaratma reddedildi: {str(exc)[:300]}", name=spot), adt)
            if not y.get("ok"):
                return _temizle(_hata("create_failed", f"Spot yaratılamadı: HTTP {y.get('status')}", name=spot,
                                      sap_body=str(y.get("text") or "")[:400]), adt)
            yaratildi = True
            tur, model = _oku(adt, L, spot)
            if tur != "model":
                return _temizle(_hata("read_after_create_failed",
                                      "Spot yaratıldı ama geri okunamadı — tanım yazılmadı. adt_badi_spot_read ile bak.",
                                      name=spot, created=True), adt)
        else:
            # PULL-BEFORE-EDIT (var olan spot)
            kayit, pst_hata = _pull_state.kayit_al(spot, _TIP)
            if pst_hata:
                return _hata("pull_state_unreadable", f"Pull-state okunamadı: {pst_hata}. adt_badi_spot_read ile yeniden oku.")
            if kayit is None or kayit.get("absent"):
                return _hata("pull_before_edit_missing",
                             f"PULL-BEFORE-EDIT: {_pull_state.anahtar(spot, _TIP)} için okuma kaydı yok. Önce "
                             "adt_badi_spot_read ile canlı belgeyi oku; değişiklik onun üzerine kurulur.", name=spot)
            canli_ozet = _pull_state.ozet(model_metni(model))
            if canli_ozet != kayit.get("sha256"):
                return _hata("source_changed_since_pull",
                             f"PULL-BEFORE-EDIT: spot {kayit.get('pulled_at')} tarihli okumadan sonra SAP'de DEĞİŞMİŞ — "
                             "üzerine yazılmadı. adt_badi_spot_read ile yeniden oku.", name=spot,
                             pulled_at=kayit.get("pulled_at"))
        if (model["spot"].get("masterSystem") or "").upper() == "SAP":
            return GuardrailViolation("ADR_0005_A", f"Standart spot (masterSystem=SAP): {spot} — yazma YOK.",
                                      name=spot).as_dict()
        if not yaratildi:
            if description is not None and description != model["spot"].get("description"):
                return _hata("invalid_argument", "description var olan spot'ta uygulanmaz (açıklama değişikliği "
                                                 f"ÖLÇÜLMEDİ); okunan: {model['spot'].get('description')!r}.")
            if package and package.strip().upper() != (model["spot"].get("package") or "").upper():
                return _hata("invalid_argument", "package var olan spot'ta uygulanmaz; okunan: "
                                                 f"{model['spot'].get('package')!r}.")
        if model["modellenmeyen"]:
            return _hata("unmodelled_fields", "Belge aracın modellemediği alan(lar) taşıyor; TAM-belge PUT bunları "
                                              "SİLERDİ — yazma YOK: " + ", ".join(model["modellenmeyen"]),
                         name=spot, created=yaratildi)
        yeni, yapilan = model, []
        try:
            if tanimlar:
                yeni, y1 = L.enhs_spec_uygula(yeni, {"tanimlar": tanimlar})
                yapilan += y1
            for ad in kaldir:
                yeni, y2 = L.enhs_tanim_uygula(yeni, {"badi": ad, "kaldir": True})
                yapilan += [f"{ad}: {x}" for x in y2]
        except (ValueError, AttributeError, TypeError) as exc:
            return _hata("invalid_argument", f"Tanım değişikliği uygulanamadı: {exc}", name=spot, created=yaratildi)
        if dry_run:
            return {"ok": True, "name": spot, "dry_run": True, "created": False, "changes": yapilan,
                    "document": L.enhs_belgesi_kur(yeni)}
        resp: dict = {"ok": False, "name": spot, "created": yaratildi, "changes": yapilan}
        if yapilan:
            w = adt.write_enhancement_spot(spot, yeni, transport, taban=model)
            resp["lock_released"] = w.get("lock_released")
            resp["put_status"] = w.get("put_status")
            if w.get("lock_released") is False:
                resp["lock_notice"] = L.kilit_birakilamadi_uyarisi(spot)
            if not w.get("ok"):
                _pull_state.sil(spot, _TIP)
                resp.update(error="write_failed", message=f"Yazma: {w.get('hata')}",
                            pull_state="silindi: yazma başarısız — adt_badi_spot_read ile yeniden oku")
                return _temizle(resp, adt)
        elif not yaratildi:
            return {"ok": True, "name": spot, "created": False, "changes": [], "message": "Değişiklik yok."}
        if not activate:
            resp.update(ok=True, activated=False, inactive_notice="activate=false: spot İNAKTİF bırakıldı "
                                                                   "(worklist'te kalır).")
        else:
            ak = adt.activate_enhancement_spot(spot)
            resp["activated"] = ak.get("aktif") is True
            resp["activation"] = {k: ak.get(k) for k in ("dogrulanamadi", "worklist_sonda", "surumsuz_surum",
                                                          "aktivasyon")}
            if ak.get("kalan_inaktif"):
                resp["still_inactive"] = ak["kalan_inaktif"]
            if not resp["activated"]:
                resp.update(error="activation_unverified" if ak.get("dogrulanamadi") else "activation_failed",
                            message=("Aktivasyon DOĞRULANAMADI — aktif SAYILMAZ." if ak.get("dogrulanamadi")
                                     else "Aktivasyon olmadı."),
                            activation_errors=[e.get("message") for e in (ak.get("errors") or [])][:5])
        # readback (aktivasyon başarısız olsa da: yazılanın sunucuda olup olmadığını söyler)
        tur, okunan = _oku(adt, L, spot)
        if tur != "model":
            resp["readback_verified"] = None
            resp["readback_notice"] = "READBACK KOŞMADI — spot geri okunamadı; 'yazım doğrulandı' DEĞİLDİR."
            _pull_state.sil(spot, _TIP)
            resp["pull_state"] = "silindi: geri okunamadı — adt_badi_spot_read ile yeniden oku"
            resp["ok"] = False
            resp.setdefault("error", "readback_failed")
            return _temizle(resp, adt)
        fark = L.enhs_kiyasla(yeni, okunan)
        resp["readback_verified"] = not fark
        if fark:
            resp["readback_diff"] = fark[:10]
            resp["ok"] = False
            resp.setdefault("error", "readback_mismatch")
        elif not resp.get("error"):
            resp["ok"] = True
        h = _pull_state.kaydet(spot, _TIP, model_metni(okunan))
        resp["pull_state"] = "guncellendi" if h is None else f"yazilamadi: {h}"
        resp["definition_count"] = len(okunan["tanimlar"])
        return _temizle(resp, adt)
    except Exception as exc:  # noqa: BLE001
        from sapadt.tools import atom as _atom
        _pull_state.sil(spot, _TIP)
        return _temizle(_atom._err_from_exc(exc), adt)
