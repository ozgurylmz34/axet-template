# -*- coding: utf-8 -*-
"""DDIC composite araçları (aXet 2026-09-21): Z tablo (Z38) ve tablo tipi (Z40).

- adt_table_create : ön kontrol → DDL render → reviewer (`table_creation`, yazılacak DDL üzerinde) → varlık
                     sondası → kabuk POST + stateful LOCK→PUT→UNLOCK (`create_table_with_ddl`) → aktivasyon →
                     aktif kaynak readback (alan/anahtar dizisi)
- adt_ttyp_create  : ön kontrol → varlık sondası → POST → aktivasyon → İKİ KANALLI readback (ADT XML + DD40L) →
                     satır tipi boş YA DA tanım istenenden farklıysa If-Match'li PUT düzeltmesi (tek sefer) →
                     yeniden aktivasyon → yeniden readback; hâlâ boş/farklı/çelişkili → FAIL (asla "OK" denmez)

Politika `tools/composite.py` ile aynı: atomik-yaratma, atomik-geri-alma DEĞİL. Yarım kalan obje SİLİNMEZ; durum
`steps`'te ve `message`'da açıkça yazılır, karar kullanıcınındır.

⛔ ÖN KAPI (araç dışında, skill akışında): tablo/tablo tipi TASARIMI (ad, alanlar, DTEL'ler, anahtar) kullanıcıya
gösterilip AÇIK onay alınmadan bu araçlar çağrılmaz — `sap-cds-ddic` skill'i ve `sap-dev` kuralı.
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

from sapadt._app import profil_tool
from sapadt._conn import get_active_tier
from sapadt._reviewer import on_kontrol_ozeti, reject_payload, run_reviewer_tablo
from sapadt.guardrails import (
    GuardrailViolation,
    require_customer_namespace,
    require_tr_text,
    require_transport,
    require_writable_tier,
)


def _get_client():
    from sapadt.tools.atom import _get_client as _g
    return _g()


def _err_from_exc(exc: Exception) -> dict:
    from sapadt.tools.atom import _err_from_exc as _e
    return _e(exc)


def _komp():
    from sapadt.tools import composite
    return composite


def _varlik(name: str, object_type: str) -> tuple:
    from sapadt.tools.atom import _varlik_sondasi
    return _varlik_sondasi(name, object_type)


def _adt(client):
    return getattr(client, "adt_client", None) or client


def _guard(name, package, transport, description, what, tmp_muaf):
    """`tmp_muaf`: `$TMP` paketinde transport istenmez mi (guardrails.TMP_MUAF_ARACLAR ile AYNI karar)."""
    require_writable_tier(get_active_tier(), what=f"{what} create")
    require_customer_namespace(name, what=what)
    require_transport(transport, what=f"{what} create", package=package if tmp_muaf else None)
    require_tr_text(description, what=f"{what} description")


def _ml_kontrol(tail: dict, steps: dict) -> None:
    steps["verify"] = {"ok": tail.get("verified", False)}
    for k_src, k_dst in (("master_language_warning", "master_language_warning"), ("verify_reason", "reason"),
                         ("sap_version", "sap_version")):
        if tail.get(k_src):
            steps["verify"][k_dst] = tail[k_src]


# =============================================================================
# adt_table_create (Z38)
# =============================================================================

# adt_textpool_write'taki `unlock_warning` ile aynı sözleşme: yazma sonucu (`ok`) bozulmaz, uyarı üst seviyede görünür.
_KILIT_UYARI = ("Tablo kilidi AÇILAMADI (UNLOCK yanıtı 200/204 değil ya da istisna; ayrıntı steps.create.warnings) — "
                "sonraki yazımlar kilit hatası alabilir. Kilit silinmez (Kesin Yasak C); kullanıcıya bildir (SM12).")

def _aktif_tablo_kaynagi(client, name: str) -> tuple:
    """Aktif tablo DDL'i → (metin|None, sebep). 200 dışı / istisna = ÖLÇÜLEMEDİ (None)."""
    adt = _adt(client)
    try:
        r = adt.session.get(adt.url + f"/sap/bc/adt/ddic/tables/{quote(name.lower(), safe='')}/source/main",
                            headers={"Accept": "text/plain"}, params={"version": "active"}, timeout=30)
    except Exception as exc:  # noqa: BLE001
        return None, f"readback_exception:{type(exc).__name__}"
    if getattr(r, "status_code", 0) != 200:
        return None, f"readback_http_{getattr(r, 'status_code', '?')}"
    return r.text or "", "ok"


# Profil: reçete kaynak çekirdekte yalnız s4_private sistemde canlı ölçüldü (kanıtsız genişletme yok).
@profil_tool(available_on=("s4_private",))
def adt_table_create(
    name: str,
    description: str,
    fields: list[dict],
    package: str,
    transport: str = "",
    delivery_class: str = "A",
    data_maintenance: str = "RESTRICTED",
) -> dict:
    """Create + activate + verify a transparent Z table (TABL/DT) — DDL is written by LOCK→PUT, never in the POST body.

    ⛔ Ön kapı skill akışındadır: ad + alanlar + DTEL'ler + anahtar kullanıcıya gösterilip AÇIK onay alınmadan
    çağırma (`sap-cds-ddic` references/tables-structures.md §3). Araç onay sormaz.

    Args:
        name: Z/Y tablo adı, en çok 16 karakter.
        description: Tablo açıklaması (master_language'de, dolu, tek satır).
        fields: İlki DAİMA istemci alanı: {"name":"MANDT","type":"mandt","key":true}. Her öğe:
            {"name", "type" (DTEL adı ya da ilkel kısaltma: char10 · numc8 · dec15_2 · abap.dec(15,2) …),
             "key": true|false, "unit_field"?: miktar/tutar alanının birim/para alanı, "unit_kind"?: "quantity"|"currency"}.
            `description` alan açıklaması DDL'e YAZILMAZ (etiket DTEL'den gelir).
        package: Mevcut paket (paket yaratılmaz).
        transport: Değiştirilebilir İSTEK numarası — `$TMP` dahil DAİMA zorunlu (yapı aracı gibi: DDL yazımı kilit
            ister; transportsuz kilit canlı ÖLÇÜLMEDİ, yarım kabuk riski). Kilit yanıtındaki CORRNR otoritedir.
        delivery_class: A (varsayılan) · C · L · G · E · S · W.
        data_maintenance: RESTRICTED (varsayılan) · ALLOWED · NOT_ALLOWED · LIMITED.

    Returns:
        {ok, name, type:'table', ddl, fields_count, reviewer, steps:{pre_flight, reviewer, pre_check, create,
         activate, verify, readback}, error?, message?, unlock_warning?}
        `unlock_warning`: UNLOCK yanıtı 200/204 değilse (steps.create.unlock_ok=false) — `ok`'u bozmaz.
        `error='validation_error'`: ad/paket kütüphane doğrulamasında düştü, SAP'ye gidilmedi.
    """
    obj_type = "table"
    # Ad büyük harfe normalize edilir (ttyp/textpool ile aynı): küçük harfli ad kapıyı geçip kütüphanenin
    # `_validate_object_name` (yalnız A-Z) adımında düşüyordu ve "Kabuk POST'u reddedildi" diye YANLIŞ raporlanıyordu.
    name = name.strip().upper() if isinstance(name, str) else name
    try:
        _guard(name, package, transport, description, "table", False)
    except GuardrailViolation as gv:
        return gv.as_dict()
    if _komp()._paket_bos_mu(package):   # Z50 ⓕ: ağ (varlık sondası dahil) öncesi
        return _komp()._paket_reddi(name, obj_type)
    from utils.ddic_tablo import tablo_ddl_kaynagi, tablo_on_kontrol, tablo_readback_karsilastir  # type: ignore
    steps: dict[str, Any] = {}
    on = tablo_on_kontrol(name, description, fields, delivery_class, data_maintenance)
    steps["pre_flight"] = {k: v for k, v in on.items() if k != "unit_kinds"}
    if on["verdict"] == "BLOCKER":
        return {"ok": False, "error": "preflight_blocker", "name": name, "type": obj_type, "steps": steps,
                "message": "Tablo ön kontrolü BLOCKER (SAP'ye gidilmedi): "
                           + "; ".join(f["message"] for f in on["findings"])}
    try:
        ddl = tablo_ddl_kaynagi(name, description, fields, delivery_class, data_maintenance, on["unit_kinds"])
    except ValueError as exc:
        return {"ok": False, "error": "preflight_blocker", "name": name, "type": obj_type, "steps": steps,
                "message": str(exc)}

    rv = run_reviewer_tablo(ddl)
    if rv.is_blocker:
        out = reject_payload(name, obj_type, rv)
        out["steps"] = steps
        out["ddl"] = ddl
        return out
    steps["reviewer"] = on_kontrol_ozeti(rv)
    temel = {"name": name.upper(), "type": obj_type, "ddl": ddl, "fields_count": len(fields),
             "reviewer": steps["reviewer"], "steps": steps}

    try:
        client = _get_client()
    except Exception as exc:  # noqa: BLE001
        return {**_err_from_exc(exc), **temel}
    var, sonda = _varlik(name, obj_type)
    steps["pre_check"] = sonda
    if var is True:
        return {"ok": False, "error": "already_exists", **temel,
                "message": f"Tablo {name} zaten var — üzerine YAZILMADI. Mevcut tabloyu değiştirmek bu aracın kapsamı "
                           "dışında (adt_get ile incele; değişiklik yolu ayrı karar)."}
    if var is None:
        return {"ok": False, "error": "exists_unmeasured", **temel,
                "message": f"Tablo varlığı ÖLÇÜLEMEDİ ({sonda}) — 'yok' DEĞİL; yaratma denenmedi (fail-closed)."}

    from sapadt.tools.composite import _master_language
    adt = _adt(client)
    try:
        with _komp()._capture() as buf:
            yaz = adt.create_table_with_ddl(name, description, package, ddl, transport=transport or None,
                                            master_language=_master_language())
        steps["create"] = {"ok": True, **{k: yaz.get(k) for k in ("shell_status", "put_status", "corrnr_lock",
                                                                  "effective_transport", "warnings", "unlock_ok")},
                           "log": buf.getvalue().strip()}
    except Exception as exc:  # noqa: BLE001
        asama = getattr(exc, "stage", None)
        steps["create"] = {**_err_from_exc(exc), "stage": asama}
        kismi = getattr(exc, "partial", None) or {}
        for k in ("corrnr_lock", "effective_transport", "put_status", "warnings", "unlock_ok"):
            if k in kismi:
                steps["create"][k] = kismi[k]
        belirsiz = getattr(exc, "outcome_uncertain", None)   # Z50 ⓒ: istek GİTTİ, yanıt yerine ağ istisnası
        if asama == "validate":
            return {"ok": False, "error": "validation_error", **temel,
                    "message": f"Ad/paket doğrulaması reddetti — SAP'ye gidilmedi (kabuk POST'u atılmadı): {exc}"}
        if asama in ("lock", "put"):
            if belirsiz == "put":
                durum = ("Tablo KABUĞU SAP'de yaratıldı; DDL PUT isteği gönderildi ama yanıt yerine AĞ İSTİSNASI geldi — "
                         "DDL'in yazılıp yazılmadığı BELİRSİZ (kabuk varsayılan içerikte de olabilir, DDL yazılmış da). "
                         "Kör tekrar YAPMA; önce adt_get(tabl) ile canlı kaynağa bak. Obje SİLİNMEDİ.")
            elif belirsiz == "lock":
                durum = ("Tablo KABUĞU SAP'de yaratıldı; KİLİT isteği gönderildi ama yanıt yerine AĞ İSTİSNASI geldi — "
                         "kilidin alınıp alınmadığı BELİRSİZ (DDL yazılmadı). Kilit silinmez (Kesin Yasak C); kullanıcı "
                         "SM12'de bakar. Kabuk SİLİNMEDİ.")
            else:
                durum = ("Tablo KABUĞU SAP'de yaratıldı ama DDL YAZILAMADI (%s aşaması). Kabuk varsayılan "
                         "`client : abap.clnt` içeriğiyle İNAKTİF duruyor; SİLİNMEDİ." % asama)
            out = {"ok": False, "error": "partial_shell", **temel,
                    "message": (durum + " Seçenekler: sebebi düzeltip kabuğu kullanıcı onayıyla adt_delete ile sil ve "
                                "aracı yeniden çalıştır. adt_push_source(tabl) ile DDL yazma kaynak çekirdekte 'invalid "
                                "lock handle' verdi (aXet'te ÖLÇÜLMEDİ) — önerilmez.")}
            if belirsiz:
                out["outcome_uncertain"] = belirsiz
            if kismi.get("unlock_ok") is False:
                out["unlock_warning"] = _KILIT_UYARI
            return out
        var2, sonda2 = _varlik(name, obj_type)
        steps["exists_after"] = sonda2
        return {"ok": False, "error": "create_failed", **temel, "exists_after": var2,
                "message": ("Kabuk POST'u reddedildi." if var2 is False else
                            "⚠ Kabuk POST'u hata verdi AMA tablo SAP'de VAR — tekrar yaratma; adt_get ile incele."
                            if var2 is True else "⚠ Tablo yaratıldı mı ÖLÇÜLEMEDİ — kör tekrar YAPMA.")}

    tail = _komp()._activate_and_verify(client, name, obj_type)
    steps["activate"] = {"ok": tail.get("activated", False), "log": tail.get("activate_log", "")}
    if "activate_error" in tail:
        steps["activate"]["error"] = tail["activate_error"]
    _ml_kontrol(tail, steps)
    readback_ok = False
    if tail.get("verified"):
        canli, sebep = _aktif_tablo_kaynagi(client, name)
        if canli is None:
            steps["readback"] = {"ok": False, "reason": sebep,
                                 "message": "Aktif kaynak OKUNAMADI — 'aktif' metadata'sı içeriğin doğru olduğunu kanıtlamaz."}
        else:
            steps["readback"] = tablo_readback_karsilastir(ddl, canli)
            readback_ok = steps["readback"]["ok"]
    ok = bool(tail.get("activated") and tail.get("verified") and readback_ok)
    out = {"ok": ok, **temel}
    if not ok:
        out["error"] = ("activation_failed" if not tail.get("activated") else
                        "verify_failed" if not tail.get("verified") else "readback_mismatch")
        out["message"] = ("Tablo yazıldı ama doğrulanamadı — obje SİLİNMEDİ; steps.activate / steps.readback'e bak. "
                          "Aktivasyon hatası çoğunlukla DTEL/birim referansıdır; düzeltme için kabuğu onayla silip yeniden yarat.")
    if yaz.get("unlock_ok") is False:
        out["unlock_warning"] = _KILIT_UYARI
    return out


# =============================================================================
# adt_ttyp_create (Z40)
# =============================================================================

_TTYP_CT = "application/vnd.sap.adt.tabletype.v1+xml"
_TTYP_ACCEPT = "application/vnd.sap.adt.tabletype.v1+xml, */*"


def _ttyp_url(name: str) -> str:
    return "/sap/bc/adt/ddic/tabletypes/" + quote(name.lower(), safe="")


def _ttyp_xml_oku(client, name: str) -> tuple:
    """Aktif ADT XML → (xml|None, etag, sebep)."""
    adt = _adt(client)
    try:
        r = adt.session.get(adt.url + _ttyp_url(name), headers={"Accept": _TTYP_ACCEPT},
                            params={"version": "active"}, timeout=30)
    except Exception as exc:  # noqa: BLE001
        return None, "", f"xml_exception:{type(exc).__name__}"
    if getattr(r, "status_code", 0) != 200:
        return None, "", f"xml_http_{getattr(r, 'status_code', '?')}"
    return r.text or "", (getattr(r, "headers", {}) or {}).get("ETag", ""), "ok"


def _dd40l_oku(client, name: str) -> tuple:
    """DD40L aktif satırı → (satır|None, sebep). Satır yok = ('{}', 'no_row') — obje aktif değil demektir."""
    from utils.ddic_ttyp import dd40l_sorgusu  # type: ignore
    try:
        with _komp()._capture():
            res = client.run_sql_query(dd40l_sorgusu(name), max_rows=5)
    except Exception as exc:  # noqa: BLE001
        return None, f"dd40l_exception:{type(exc).__name__}"
    if not isinstance(res, dict):
        err = getattr(client, "last_sql_error", None) or {}
        return None, f"dd40l_query_failed:{(err or {}).get('status_code', '?')}"
    kol = [str(c).upper() for c in res.get("columns") or []]
    satirlar = [dict(zip(kol, s)) for s in res.get("data") or []]
    if not satirlar:
        return {}, "no_row"
    return satirlar[0], "ok"


def _ttyp_readback(client, name: str, spec: dict) -> dict:
    """İki kanal: ADT XML + DD40L. {durum: 'dolu'|'bos'|'celiski'|'olculemedi', xml, dd40l, farklar, etag}."""
    from utils.ddic_ttyp import dd40l_uyumsuzluklari, satir_tipi_bos_mu, ttyp_xml_oku, xml_uyumsuzluklari  # type: ignore
    xml, etag, xs = _ttyp_xml_oku(client, name)
    oku = ttyp_xml_oku(xml) if xml is not None else None
    satir, ds = _dd40l_oku(client, name)
    dolu = satir_tipi_bos_mu(oku, satir, spec)
    rb = {"xml_probe": xs, "dd40l_probe": ds, "xml": oku, "dd40l": satir or None, "row_type_filled": dolu,
          "etag_present": bool(etag), "_etag": etag, "_xml": xml}
    # Birincil ölçü DD40L (kaynak çekirdekte sessiz NULL burada görüldü). Karar tablosu:
    #   DD40L ölçülemedi / aktif satır yok      → olculemedi
    #   DD40L boş  + XML dolu                   → celiski (kanallardan biri kör)
    #   DD40L boş  + XML boş ya da ölçülemedi   → bos (düzeltme yolu)
    #   DD40L dolu + XML boş                    → celiski
    #   DD40L dolu + XML ölçülemedi             → olculemedi
    if dolu["dd40l"] is None or ds == "no_row":
        rb["durum"] = "olculemedi"
        return rb
    if not dolu["dd40l"]:
        rb["durum"] = "celiski" if dolu["xml"] is True else "bos"
        return rb
    if dolu["xml"] is False:
        rb["durum"] = "celiski"
        return rb
    if dolu["xml"] is None:
        rb["durum"] = "olculemedi"
        return rb
    rb["farklar"] = dd40l_uyumsuzluklari(spec, satir) + xml_uyumsuzluklari(spec, oku)
    rb["durum"] = "uyumsuz" if rb["farklar"] else "dolu"
    return rb


def _ttyp_duzelt(client, name: str, xml_govde: str, transport: str, etag: str) -> dict:
    """Satır tipi boş ya da tanım farklı kaldıysa: AYNI XML (istenen tam tanım) ile If-Match'li PUT (kaynak çekirdek tablo tipi bölümü 'Adım 4')."""
    adt = _adt(client)
    if not etag:
        try:
            g = adt.session.get(adt.url + _ttyp_url(name), headers={"Accept": _TTYP_ACCEPT}, timeout=30)
            etag = (getattr(g, "headers", {}) or {}).get("ETag", "")
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "reason": f"etag_exception:{type(exc).__name__}"}
    if not etag:
        return {"ok": False, "reason": "etag_yok", "message": "ETag alınamadı — If-Match'siz PUT denenmez."}
    basliklar = adt._get_headers(_TTYP_ACCEPT, _TTYP_CT)
    basliklar["If-Match"] = etag
    try:
        r = adt._request_with_csrf_retry("put", adt.url + _ttyp_url(name), headers=basliklar,
                                         params={"corrNr": transport} if transport else {},
                                         data=xml_govde.encode("utf-8"))
    except Exception as exc:  # noqa: BLE001 — istek gitti, yanıt gelmedi (Z50 ⓒ): yazıldığı BELİRSİZ
        return {"ok": False, "reason": f"put_exception:{type(exc).__name__}", "outcome_uncertain": True}
    kod = int(getattr(r, "status_code", 0) or 0)
    return {"ok": kod in (200, 201, 204), "http_status": kod, "body_head": (getattr(r, "text", "") or "")[:300]}


def _rb_ozet(rb: dict) -> dict:
    return {k: v for k, v in rb.items() if not k.startswith("_")}


# Profil: reçete kaynak çekirdekte yalnız s4_private sistemde canlı ölçüldü (kanıtsız genişletme yok).
@profil_tool(available_on=("s4_private",))
def adt_ttyp_create(
    name: str,
    description: str,
    package: str,
    transport: str = "",
    row_type: str | None = None,
    builtin: dict | None = None,
    access_type: str = "standard",
    key_definition: str = "standard",
    key_kind: str | None = None,
    key_components: list[str] | None = None,
) -> dict:
    """Create + activate + two-channel verify a DDIC table type (TTYP); repairs an empty row type once, else FAILS.

    ⛔ Ön kapı skill akışındadır: ad (`<gövde>_TT_<AD>`), satır tipi ve anahtar kullanıcıya gösterilip AÇIK onay
    alınmadan çağırma. Önce hazır standart tip var mı bak (ör. mesaj tablosu için BAPIRET2_T) — yeni tip yaratma.

    Satır tipi — TAM OLARAK BİRİ:
        row_type: DDIC yapı / tablo / DTEL adı (typeKind=dictionaryType).
        builtin: {"data_type": CHAR|NUMC (length) · DEC (length+decimals) · STRING|INT4|DATS}.
        Desteklenmez: aralık tablosu, referans satır, iç içe tablo tipi, boş/genel anahtar, ikincil anahtar.
    access_type: standard (varsayılan) · sorted · hashed.
    key_definition: standard (varsayılan; DDIC "Standard key" = ABAP `WITH DEFAULT KEY`, EMPTY KEY DEĞİL) ·
        rowType · keyComponents (key_components ile).
    key_kind: nonUnique | unique (verilmezse: hashed → unique, diğerleri nonUnique). standard+unique ve
        hashed+nonUnique reddedilir.

    Doğrulama (canlıda OKUNUR, mesaja güvenilmez): aktivasyon → ADT XML (`rowType/typeName`, erişim, anahtar) VE
    DD40L (ROWTYPE/DATATYPE, ACCESSMODE, KEYDEF, KEYKIND). İki kanal da BOŞ ya da tanım istenenden FARKLI → bir kez
    If-Match'li PUT (istenen tam tanım) → yeniden aktivasyon → yeniden iki kanal; nihai `ok` ikinci aktivasyonun
    doğrulamasından gelir. Kanallar çelişirse ya da düzeltme sonrası hâlâ boş/farklıysa `ok:false` (asla sahte OK).

    Returns:
        {ok, name, type:'ttyp', spec, steps:{pre_flight, pre_check, create, activate, verify, readback,
         repair?{trigger: bos|uyumsuz}, activate_2?, verify_2?, readback_2?}, error?, message?}
        error: preflight_blocker · already_exists · exists_unmeasured · create_uncertain · create_failed ·
        activation_failed · row_type_empty_repair_failed · readback_mismatch_repair_failed ·
        activation_failed_after_repair · row_type_empty_after_repair · readback_channels_disagree ·
        readback_unmeasured · readback_mismatch · verify_failed
    """
    obj_type = "ttyp"
    try:
        _guard(name, package, transport, description, "ttyp", True)
    except GuardrailViolation as gv:
        return gv.as_dict()
    if _komp()._paket_bos_mu(package):   # Z50 ⓕ: bu yol kütüphane paket doğrulamasından HİÇ geçmez (ham POST)
        return _komp()._paket_reddi(name, obj_type)
    from utils.ddic_ttyp import ttyp_on_kontrol, ttyp_xml  # type: ignore
    steps: dict[str, Any] = {}
    on = ttyp_on_kontrol(row_type, builtin, access_type, key_definition, key_kind, key_components)
    spec = on["spec"]
    steps["pre_flight"] = {k: v for k, v in on.items() if k != "spec"}
    if on["verdict"] == "BLOCKER":
        return {"ok": False, "error": "preflight_blocker", "name": name, "type": obj_type, "steps": steps,
                "message": "Tablo tipi ön kontrolü BLOCKER (SAP'ye gidilmedi): "
                           + "; ".join(f["message"] for f in on["findings"])}
    govde = ttyp_xml(name, description, package, spec)
    temel = {"name": name.upper(), "type": obj_type, "spec": spec, "steps": steps,
             "reviewer": {"verdict": "SKIP", "skip_reason": "no_reviewer_task_for_ttyp",
                          "notice": "Tablo tipi için validator zinciri yok; doğrulama iki kanallı canlı readback'tir."}}
    try:
        client = _get_client()
    except Exception as exc:  # noqa: BLE001
        return {**_err_from_exc(exc), **temel}
    var, sonda = _varlik(name, obj_type)
    steps["pre_check"] = sonda
    if var is True:
        return {"ok": False, "error": "already_exists", **temel,
                "message": f"Tablo tipi {name} zaten var — üzerine YAZILMADI."}
    if var is None:
        return {"ok": False, "error": "exists_unmeasured", **temel,
                "message": f"Tablo tipi varlığı ÖLÇÜLEMEDİ ({sonda}) — 'yok' DEĞİL; yaratma denenmedi."}

    adt = _adt(client)
    try:
        r = adt._request_with_csrf_retry("post", adt.url + "/sap/bc/adt/ddic/tabletypes",
                                         headers=adt._get_headers(_TTYP_ACCEPT, _TTYP_CT),
                                         params={"corrNr": transport} if transport else {},
                                         data=govde.encode("utf-8"))
        kod, metin = int(getattr(r, "status_code", 0) or 0), str(getattr(r, "text", "") or "")
    except Exception as exc:  # noqa: BLE001
        steps["create"] = _err_from_exc(exc)
        var2, sonda2 = _varlik(name, obj_type)
        return {"ok": False, "error": "create_uncertain", **temel, "exists_after": var2, "exists_probe": sonda2,
                "message": "POST istisna verdi — obje yaratıldı mı varlık sondasına bak; kör tekrar YAPMA."}
    steps["create"] = {"ok": kod in (200, 201), "http_status": kod, "body_head": metin[:300]}
    if kod not in (200, 201):
        var2, sonda2 = _varlik(name, obj_type)
        return {"ok": False, "error": "already_exists" if "alreadyexists" in metin.lower() else "create_failed",
                **temel, "exists_after": var2, "exists_probe": sonda2,
                "message": f"Tablo tipi POST'u HTTP {kod} verdi (ham gövde steps.create.body_head)."}

    def aktive_et(anahtar):
        t = _komp()._activate_and_verify(client, name, "tabletype")
        steps[anahtar] = {"ok": t.get("activated", False), "log": t.get("activate_log", "")}
        if "activate_error" in t:
            steps[anahtar]["error"] = t["activate_error"]
        return t

    tail = aktive_et("activate")
    _ml_kontrol(tail, steps)
    if not tail.get("activated"):
        return {"ok": False, "error": "activation_failed", **temel,
                "message": "Tablo tipi yaratıldı ama aktive EDİLEMEDİ — obje SİLİNMEDİ; steps.activate'e bak "
                           "(tipik: satır tipi yok/inaktif, anahtar bileşeni satır tipinde yok)."}
    rb = _ttyp_readback(client, name, spec)
    steps["readback"] = _rb_ozet(rb)
    son_tail = tail
    onarildi = False
    # Onarım (TEK sefer): satır tipi BOŞ ya da tanım istenenden FARKLI. Canlı 2026-09-21 (DEV): POST gövdedeki satır
    # tanımını düşürdü, SAP varsayılanı `CHAR · 000001` kaldı (ROWTYPE NULL). Yapı satırlıda bu `bos` olarak
    # yakalanıp If-Match PUT ile düzeldi (erişim/anahtar dahil); ilkel satırda varsayılan CHAR "dolu" göründüğü için
    # `uyumsuz` çıkıyordu ve onarım hiç denenmiyordu. İlkel satırda PUT onarımı canlıda henüz ÖLÇÜLMEDİ.
    if rb["durum"] in ("bos", "uyumsuz"):
        ilk_durum = rb["durum"]
        steps["repair"] = _ttyp_duzelt(client, name, govde, transport, rb.get("_etag", ""))
        steps["repair"]["trigger"] = ilk_durum
        if not steps["repair"].get("ok"):
            if steps["repair"].get("outcome_uncertain"):
                belirsiz_ek = (" Düzeltme PUT'u gönderildi ama yanıt yerine AĞ İSTİSNASI geldi — yazıldığı BELİRSİZ "
                               "(inaktif sürümde düzeltilmiş tanım olabilir); kör tekrar YAPMA, adt_get(ttyp) ile bak.")
            else:
                belirsiz_ek = ""
            if ilk_durum == "bos":
                return {"ok": False, "error": "row_type_empty_repair_failed", **temel,
                        "message": "Satır tipi iki kanalda da BOŞ; If-Match'li PUT düzeltmesi BAŞARISIZ — obje "
                                   "kullanılamaz (ABAP'ta belirsiz çalışma zamanı hatası verir). steps.repair'e bak."
                                   + belirsiz_ek}
            return {"ok": False, "error": "readback_mismatch_repair_failed", **temel,
                    "message": "Tablo tipi aktif ama tanımı istenenden FARKLI (" + "; ".join(rb.get("farklar") or [])
                               + "); If-Match'li PUT onarımı BAŞARISIZ — obje SİLİNMEDİ. steps.repair'e bak."
                               + belirsiz_ek}
        t2 = aktive_et("activate_2")
        if not t2.get("activated"):
            return {"ok": False, "error": "activation_failed_after_repair", **temel,
                    "message": "Düzeltme PUT'u yazıldı ama yeniden aktivasyon BAŞARISIZ — satır tipi aktif sürümde "
                               "doğrulanamaz; obje SİLİNMEDİ (inaktif sürüm kalabilir). steps.activate_2'ye bak."}
        # Z50 ⓐ: onarım sonrası nihai doğrulama İKİNCİ aktivasyonun metadata'sından gelir (ilk tail bayattır).
        steps["verify_2"] = {"ok": t2.get("verified", False)}
        for k_src, k_dst in (("verify_reason", "reason"), ("sap_version", "sap_version")):
            if t2.get(k_src):
                steps["verify_2"][k_dst] = t2[k_src]
        son_tail = t2
        onarildi = True
        rb = _ttyp_readback(client, name, spec)
        steps["readback_2"] = _rb_ozet(rb)
        if rb["durum"] == "bos":
            return {"ok": False, "error": "row_type_empty_after_repair", **temel,
                    "message": "Düzeltme PUT'u + yeniden aktivasyon sonrası satır tipi HÂLÂ BOŞ — FAIL. Obje "
                               "silinmedi; kullanıcıya bildir (SE11'de elle bakılır)."}
    if rb["durum"] == "celiski":
        return {"ok": False, "error": "readback_channels_disagree", **temel,
                "message": "ADT XML ile DD40L satır tipi konusunda ÇELİŞİYOR (biri dolu biri boş) — FAIL; "
                           "ölçüm kanallarından biri kör olabilir, kullanıcıya bildir."}
    if rb["durum"] == "olculemedi":
        return {"ok": False, "error": "readback_unmeasured", **temel,
                "message": "Readback ÖLÇÜLEMEDİ (XML ya da DD40L okunamadı / DD40L'de aktif satır yok) — "
                           "'ölçülemedi' 'doğru' DEĞİLDİR."}
    if rb["durum"] == "uyumsuz":
        return {"ok": False, "error": "readback_mismatch", **temel,
                "message": ("Tablo tipi aktif ama tanımı istenenden FARKLI"
                            + (" (If-Match'li PUT onarımı + yeniden aktivasyon SONRASI da)" if onarildi else "")
                            + ": " + "; ".join(rb.get("farklar") or []))}
    return {"ok": bool(son_tail.get("verified")), **temel,
            **({} if son_tail.get("verified") else {
                "error": "verify_failed",
                "message": "Readback dolu ama metadata 'active' doğrulanamadı"
                           + (" (onarım sonrası ikinci aktivasyon: steps.verify_2)." if onarildi else ".")})}
