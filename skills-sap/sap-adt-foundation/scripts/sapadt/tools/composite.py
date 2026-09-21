"""Composite tools — multi-step flows with verification step.

- adt_domain_create  : create_domain + activate + verify
- adt_dtel_create    : create_dataelement + activate + verify (4 labels required)
- adt_struct_create  : create_structure + activate + verify

Pattern (atomic, fail-explicit):
  1. Guardrails (Z/Y prefix, transport, TR text, labels)
  2. Pre-check via adt_get, THREE-VALUED → exists: already_exists · unmeasured: exists_unmeasured (no POST)
  3. SAPClient.create_<x>() — shell + source set (no activation)
  4. SAPClient.activate_object()
  5. SAPClient.get_object_metadata() — verify
  6. Return step-by-step status

Rollback policy:
- Step 3 fail → nothing created, return error
- Step 4 fail → object exists inactive. Do NOT auto-delete; return inactive=true with errors.
  Caller decides: fix-and-retry, manual delete, or accept.
- Step 5 fail → object created+activated but verify mismatched. Return warning.

This conservative policy matches ADR 0007: composite is atomic-create, not atomic-rollback.
"""
from __future__ import annotations

import contextlib
import io
import re
from typing import Any

from sapadt._app import log, profil_tool
from sapadt._reviewer import (
    on_kontrol_ozeti,
    reject_payload,
    run_reviewer,
    run_reviewer_struct,
    task_for_composite,
)
# Q293: post-check hükmü tek kaynakta (atom `adt_push_source` ile AYNI sözleşme).
from sapadt._reviewer import post_check_notice as _post_check_notice
from sapadt._reviewer import post_check_ozeti as _post_check_ozeti
from sapadt.guardrails import (
    GuardrailViolation,
    require_all_labels,
    require_customer_namespace,
    require_label_lengths,
    require_tr_text,
    require_transport,
    require_writable_tier,
)
from sapadt._conn import get_active_tier


def _maybe_reviewer(tool_name: str, name: str, object_type: str,
                    artifact_path: str | None, result=None) -> tuple[dict | None, dict | None]:
    """Run reviewer pre-flight. Returns (reject_payload, reviewer_dict).
    reject_payload is non-None when BLOCKER → tool must return it immediately.
    reviewer_dict DAİMA doludur (PASS/WARNING/SKIP) — aXet: kaynak çekirdek SKIP'te None
    döndürüyordu ve yanıtta "reviewer koşmadı" izi kalmıyordu (sessiz atlama).
    `result` verilirse (D1: artefaktsız struct zinciri) yeniden koşulmaz, aynı hükümle işlenir.
    Ölçülemeyen gate'ler `unmeasured` + ÖLÇÜLEMEDİ notuyla görünür (`_reviewer.on_kontrol_ozeti`).
    """
    if result is None:
        result = run_reviewer(task_for_composite(tool_name), artifact_path)
    if result.is_blocker:
        return reject_payload(name, object_type, result), None
    return None, {"reviewer": on_kontrol_ozeti(result)}


def _master_language() -> str | None:
    """sap-project.json → master_language (çözülemezse None)."""
    try:
        from sapadt.project import load_sap_project
        cfg, _hata = load_sap_project()
        return (cfg or {}).get("master_language")
    except Exception:  # noqa: BLE001
        return None


# Reuse atom helpers
def _get_client():
    from sapadt.tools.atom import _get_client as _g
    return _g()


def _err_from_exc(exc: Exception) -> dict:
    from sapadt.tools.atom import _err_from_exc as _e
    return _e(exc)


@contextlib.contextmanager
def _capture():
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        yield buf


def _ddic_varligi(name: str, object_type: str) -> tuple:
    """Domain / DTEL ön kontrolü — ÜÇ DEĞERLİ: (True|False|None, sonda). Çağıranlar: `adt_domain_create`, `adt_dtel_create`.

    ⛔ Z51 ⓐ (v0.5.1): eski `_exists` `get_object_metadata`'nın yuttuğu HER hatayı "yok" sayıyordu (fail-open) ve
    kütüphanenin `create_domain` / `create_dataelement`'i POST 405 AlreadyExists'i `success:True` döndürüyordu ⇒ ön
    kontrol yanlışlıkla "yok" derse araç VAR OLAN objeyi aktive edip `ok:true` "yaratıldı" diyebiliyordu. Artık yapı
    yoluyla aynı desen: `atom._varlik_olcumu` = `adt_get` (DDIC XML ucu; 404 → yok, 5xx/403/ağ → ÖLÇÜLEMEDİ) ·
    `None` = "yok" DEĞİL ⇒ çağıran yaratma DENEMEZ; kütüphane AlreadyExists'te `SAPObjectExistsError` atar.
    """
    from sapadt.tools.atom import _varlik_olcumu
    var, sonda, _p = _varlik_olcumu(name, object_type)
    return var, sonda


def _paket_bos_mu(package) -> bool:
    """Z50 ⓕ: boş ya da yalnız boşluk paket → True (yaratma araçları ağa gitmeden `validation_error` döner).

    Kütüphane `_validate_package_name` yalnız boş dizgiyi reddediyordu; `"   "` geçip kabuk POST'una kadar gidiyordu,
    tablo tipi yolu ise kütüphane doğrulamasından HİÇ geçmiyordu (ölçüldü 2026-09-21, sahte istemci)."""
    return not (isinstance(package, str) and package.strip())


def _paket_reddi(name, obj_type) -> dict:
    return {"ok": False, "error": "validation_error", "name": name, "type": obj_type,
            "message": "package boş ya da yalnız boşluk — hedef paket zorunlu (paket yaratılmaz). SAP'ye gidilmedi."}


# Z52: kütüphanenin `_retry_request`'i 5xx / zaman aşımı / bağlantı hatasında aynı POST'u SESSİZCE yeniden dener.
# İki iz, AYNI kümeye hizalı (bug gate v0.5.1: bağlantı hatası kolu eskiden kaçıyordu, log "ÖNCEKİ DENEME" derken kod düz
# `already_exists` diyordu):
#  ① BİRİNCİL — kütüphanenin kendi hükmü: `_zaten_var_hatasi` eki `ONCEKI_DENEME_IZI` ile başlar ve YALNIZ
#    `_son_yeniden_denemeler` doluysa konur (sarmalayıcı istisnayı yutar, `[ERROR] <mesaj>` basar → log'da görünür).
#  ② YEDEK — `[RETRY]` satırı, kütüphanenin kaydettiği ÜÇ sebeple sınırlı (CSRF hariç: istek işlenmedi).
_RETRY_IZI = re.compile(r"\[RETRY\][^\n]*(?:Server error 5\d\d|Timeout|Connection error)", re.IGNORECASE)


def _yeniden_deneme_izi(log_text: str) -> bool:
    metin = log_text or ""
    try:
        from sap_adt_lib import ONCEKI_DENEME_IZI  # type: ignore
    except Exception:  # noqa: BLE001 — kütüphane içe alınamazsa yalnız yedek iz
        ONCEKI_DENEME_IZI = None
    # Düzeltme turu gate LOW-1: iz TÜM log'da değil, yalnız kütüphanenin AlreadyExists satırının EKİ olarak aranır —
    # sarmalayıcı `Description: …` satırını da log'a basar, açıklamada aynı sözcükler geçebilir (yanlış pozitif).
    if ONCEKI_DENEME_IZI and re.search(r"already exists \(SAP \d+ AlreadyExists\)[^\n]* — "
                                       + re.escape(ONCEKI_DENEME_IZI) + r" \(", metin):
        return True
    return bool(_RETRY_IZI.search(metin))


def _zaten_var_yaniti(tur: str, name: str, obj_type: str, log_text: str, **ek) -> dict:
    """POST AlreadyExists ile reddedildi (ön kontrol "yok" demişti) → yazma/aktivasyon YOK. İki ayrı kod:

    · `already_exists_after_retry` — aynı çağrıda önce 5xx/zaman aşımı/bağlantı hatası + yeniden deneme oldu: ilk POST'u SAP işlemiş ve
      kabuğu BU çağrı yaratmış olabilir (Z52; başkasının objesi olduğu KANITLANMADI).
    · `already_exists` — yeniden deneme izi yok: yarış ya da ön kontrolün görmediği uç.
    """
    if _yeniden_deneme_izi(log_text):
        return {"ok": False, "error": "already_exists_after_retry", "existing_kind": None, "own_shell_possible": True,
                "name": name, "type": obj_type, **ek,
                "message": (f"İlk yaratma isteği sunucu hatası / zaman aşımı / bağlantı hatası aldı, kütüphane yeniden denedi ve SAP 'zaten var' "
                            f"(AlreadyExists) dedi — {tur} {name} büyük olasılıkla ÖNCEKİ DENEMENİN yarattığı kabuk "
                            "(başkasının objesi olduğu kanıtlanmadı). Kaynak YAZILMADI, aktivasyon yapılmadı. "
                            f"adt_get ile bak: inaktif/boş kabuksa kullanıcı onayıyla silip yeniden yarat. ⛔ Kör tekrar yapma.")}
    return {"ok": False, "error": "already_exists", "existing_kind": None, "name": name, "type": obj_type, **ek,
            "message": (f"SAP yaratma isteğini 'zaten var' (AlreadyExists) diye reddetti — {name} mevcut; "
                        f"kaynak YAZILMADI, aktivasyon yapılmadı. ⛔ Tekrar deneme; adt_get ile incele.")}


def _yapi_varligi(name: str) -> tuple:
    """Yapı ön kontrolü — ÜÇ DEĞERLİ: (True|False|None, sonda, bulunan tür 'structure'|'table'|None).

    `atom._varlik_olcumu(name, "structure")` = `adt_get(structure)`: `/ddic/structures/<ad>/source/main`; 404 ise KARDEŞ
    `/ddic/tables/` ucu da sorulur (aynı adlı ŞEFFAF TABLO da ad çakışmasıdır). `None` = ÖLÇÜLEMEDİ (HTTP 5xx/403, istisna,
    ağ; kardeş uç ölçülemedi) — "yok" DEĞİL ⇒ çağıran yaratma DENEMEZ (fail-closed).
    """
    from sapadt.tools.atom import _varlik_olcumu
    var, sonda, p = _varlik_olcumu(name, "structure")
    tur = None
    if var is True:
        tur = "table" if (p or {}).get("resolved_type") == "table" else "structure"
    return var, sonda, tur


def _activate_and_verify(client, name: str, object_type: str, verify_type: str | None = None) -> dict:
    """Step 4+5 — common tail. Returns dict with activated/verified flags.

    `verify_type`: metadata okumasının tipi (verilmezse `object_type`). Yapı için ŞART: `adt_struct_create`
    aktivasyonu canlıda ölçülen `tabl` adresiyle yapar ama metadata `/ddic/tables/` ucunda BULUNMAZ — yapılar
    `/ddic/structures/` altındadır (canlı 2026-09-21: yapı aktifti, doğrulama `metadata_not_found` dedi).

    verified=True requires:
      - get_object_metadata returns non-None
      - SAP metadata XML contains adtcore:version="active"

    Sprint 6 T10 lesson: existence != active. Bağımlı objeler inconsistent ise
    activate çağrısı OK döner ama version "inactive" kalır.
    """
    import re
    out: dict[str, Any] = {}
    try:
        with _capture() as buf:
            activated = client.activate_object(name, object_type=object_type)
        out["activated"] = bool(activated)
        out["activate_log"] = buf.getvalue().strip()
    except Exception as exc:
        out["activated"] = False
        out["activate_error"] = _err_from_exc(exc)
        return out

    if not out["activated"]:
        return out

    # Verify metadata + version=active
    try:
        with _capture():
            md = client.get_object_metadata(name, object_type=verify_type or object_type)
        if md is None:
            out["verified"] = False
            out["verify_reason"] = "metadata_not_found"
            return out
        md_text = md if isinstance(md, str) else str(md)
        m = re.search(r'adtcore:version="(\w+)"', md_text)
        version = m.group(1) if m else None
        # masterLanguage enforce — beklenen dil sap-project.json master_language (aXet;
        # kaynak çekirdekte sabit "TR"). Ekstra SAP çağrısı yok; çekilen metadata'dan oku.
        ml = re.search(r'masterLanguage="(\w+)"', md_text)
        out["master_language"] = ml.group(1) if ml else None
        beklenen = _master_language()
        if out["master_language"] and beklenen and out["master_language"].upper() != beklenen.upper():
            out["master_language_warning"] = (
                f"masterLanguage={out['master_language']} — sap-project.json master_language="
                f"{beklenen} bekler. İsim ilk yaratımdaki dile yapışmış olabilir (yeni isim gerekebilir)."
            )
        if version == "active":
            out["verified"] = True
            out["sap_version"] = "active"
        else:
            out["verified"] = False
            out["verify_reason"] = f"sap_version={version or 'unknown'}_expected_active"
            out["sap_version"] = version
    except Exception as exc:
        out["verified"] = False
        out["verify_reason"] = f"verify_exception:{exc}"
    return out


def _verify_ddic_content(client, name: str, obj_type: str) -> dict:
    """KOŞULSUZ içerik-doğrulama (varlık DEĞİL) — 'activated' shell'i maskelemesin.

    Ders: create-POST inline source flaky → 'activated' bir placeholder shell olabilir
    (component_to_be_changed:abap.string). Bu yüzden AKTİVASYON SONRASI sistemden İÇERİK
    okunur, success mesajına güvenilmez:
      - structure (eski adıyla `tabl`): /ddic/structures/<ad>/source/main (active) → placeholder yok + alan > 0
      - ttyp (table type): obje XML (active) → rowType/typeName dolu + dataType boş değil

    Returns {ok: bool, reason?, field_count?/row_type?/data_type?}.
    """
    import re
    adt = getattr(client, "adt_client", client)
    try:
        if obj_type in ("structure", "tabl"):
            url = f"/sap/bc/adt/ddic/structures/{name.lower()}/source/main"
            r = adt.session.get(adt.url + url, headers=adt._get_headers("text/plain"),
                                params={"version": "active"}, timeout=30)
            if r.status_code != 200:
                return {"ok": False, "reason": f"source_read_http_{r.status_code}"}
            src = r.text or ""
            if re.search(r"component_to_be_changed\s*:\s*abap\.string", src, re.IGNORECASE):
                return {"ok": False, "reason": "placeholder_shell", "source_head": src[:160]}
            body = src[src.find("{") + 1: src.rfind("}")] if "{" in src else ""
            fcount = len(re.findall(r"^\s*\w+\s*:\s*[^;]+;", body, re.MULTILINE))
            if fcount == 0:
                return {"ok": False, "reason": "no_fields", "source_head": src[:160]}
            return {"ok": True, "field_count": fcount}
        if obj_type == "ttyp":
            url = f"/sap/bc/adt/ddic/tabletypes/{name.lower()}"
            r = adt.session.get(
                adt.url + url,
                headers={"Authorization": adt._get_auth_header(),
                         "sap-client": adt.client,
                         "Accept": "application/vnd.sap.adt.tabletype.v1+xml"},
                params={"version": "active"}, timeout=30)
            if r.status_code != 200:
                return {"ok": False, "reason": f"ttyp_read_http_{r.status_code}"}
            t = r.text or ""
            tn = re.search(r"typeName>([^<]+)<", t)
            dt = re.search(r"dataType>([^<]*)<", t)
            if not tn or not tn.group(1).strip():
                return {"ok": False, "reason": "rowtype_empty", "xml_head": t[:200]}
            if not dt or not dt.group(1).strip():
                return {"ok": False, "reason": "datatype_empty_shell", "xml_head": t[:200]}
            return {"ok": True, "row_type": tn.group(1).strip(), "data_type": dt.group(1).strip()}
        return {"ok": True, "skip_reason": f"no_content_verify_for_{obj_type}"}
    except Exception as exc:
        return {"ok": False, "reason": f"content_verify_exception:{exc}"}


# =============================================================================
# adt_domain_create
# =============================================================================

def _domain_on_kontrol(datatype, length, decimals, lowercase, fixed_values) -> dict:
    """Ağ ÖNCESİ argüman kontrolü (artefakt BEKLEMEZ) → `steps.pre_flight`.

    aXet 2026-09-13. Her kural kaynağıyla (kaynak çekirdek yolları; `lib/…` bu paket):
      R1 datatype çıktı-uzunluğu formülü tanımlı tiplerden biri — `check_domain_output_length.py`
         CSV kuralı ("Bilinmeyen datatype" = BLOCKER) · playbook `adt-domain-dtel.md:133-140`.
         (`lib/sap_adt_lib.py::_validate_datatype` FLTP/RAW/LANG… de kabul eder; bunların formülü kaynakta
         YOK → eskiden çıktı uzunluğu = length gönderiliyordu, doğrulanmamış.)
      R2 length pozitif tamsayı — formül girdisi; `lib/sap_adt_lib.py:5185-5191` (CHAR/NUMC pozitif).
      R3 decimals ≥ 0 tamsayı — `lib/sap_adt_lib.py:5199-5205`.
      R4 lowercase true/false — araç `"true" if lowercase` ile okur ("false" dizesi truthy olurdu).
      R5 fixed_values: her öğe dolu `value` + dolu `text` (master_language metni) — playbook
         `adt-domain-dtel.md:263` ("low=değer, text=TR açıklama") + Yasak D. Kütüphane eskiden metin yoksa
         değeri metin olarak SESSİZCE yazıyordu (`lib/sap_adt_lib.py` fixValue döngüsü).
      Çıktı uzunluğu `utils.ddic_domain.expected_output_length` ile hesaplanır ve AYNI fonksiyon POST
      gövdesine yazılır (kopya yok) — `output_length` alanı gönderilecek değeri gösterir.
    Kaynakta kanıtı olmadığı için EKLENMEYEN kurallar: lowercase yalnız CHAR, decimals yalnız sayısal tip,
    sabit tip uzunlukları (DATS=8 …; playbook tablosu DTEL bağlamında), sabit değer metni uzunluk sınırı.
    """
    from utils.ddic_domain import FORMUL_TIPLERI, expected_output_length, formul_tanimli_mi  # type: ignore
    bulgular: list[dict] = []

    def bul(kural, mesaj, kaynak):
        bulgular.append({"rule": kural, "severity": "BLOCKER", "message": mesaj, "source": kaynak})

    dt = datatype.strip().upper() if isinstance(datatype, str) else None
    if not formul_tanimli_mi(datatype):
        bul("R1_datatype", f"datatype {datatype!r} için çıktı uzunluğu formülü tanımlı değil. Desteklenen: "
                           f"{', '.join(FORMUL_TIPLERI)}.",
            "check_domain_output_length.py (domain_creation_csv) · playbook adt-domain-dtel.md:133-140")
    uzunluk_ok = isinstance(length, int) and not isinstance(length, bool) and length > 0
    if not uzunluk_ok:
        bul("R2_length", f"length pozitif tamsayı olmalı (verilen: {length!r}).", "lib/sap_adt_lib.py:_validate_datatype")
    if not (isinstance(decimals, int) and not isinstance(decimals, bool) and decimals >= 0):
        bul("R3_decimals", f"decimals 0 ya da pozitif tamsayı olmalı (verilen: {decimals!r}).",
            "lib/sap_adt_lib.py:_validate_datatype")
    if not isinstance(lowercase, bool):
        bul("R4_lowercase", f"lowercase true/false olmalı (verilen: {lowercase!r}).", "araç imzası")
    if fixed_values is not None:
        if not isinstance(fixed_values, list):
            bul("R5_fixed_values", "fixed_values bir liste olmalı: [{\"value\":\"A\",\"text\":\"…\"}].",
                "playbook adt-domain-dtel.md:246-263")
        else:
            for i, fv in enumerate(fixed_values):
                if not isinstance(fv, dict):
                    bul("R5_fixed_values", f"fixed_values[{i}] nesne değil.", "playbook adt-domain-dtel.md:246-263")
                    continue
                fazla = sorted(set(fv) - {"value", "text"})
                if fazla:
                    bul("R5_fixed_values", f"fixed_values[{i}] tanınmayan alan: {', '.join(fazla)}.",
                        "playbook adt-domain-dtel.md:246-263")
                if not (isinstance(fv.get("value"), str) and fv["value"].strip()):
                    bul("R5_fixed_values", f"fixed_values[{i}].value boş.", "playbook adt-domain-dtel.md:263")
                if not (isinstance(fv.get("text"), str) and fv["text"].strip()):
                    bul("ADR_0005_D", f"fixed_values[{i}].text boş — sabit değer metni master_language'de "
                                      "ve dolu olmalı (değer metin yerine yazılmaz).",
                        "playbook adt-domain-dtel.md:263 · Kesin Yasak D")
    out: dict[str, Any] = {"verdict": "BLOCKER" if bulgular else "PASS", "findings": bulgular,
                           "checked": ["R1_datatype", "R2_length", "R3_decimals", "R4_lowercase",
                                       "R5_fixed_values"],
                           "not_checked": ["lowercase yalnız CHAR", "decimals yalnız sayısal tip",
                                           "tipe sabit uzunluk (DATS/TIMS/INT*)", "sabit değer metni uzunluğu",
                                           "açıklama uzunluğu"]}
    if dt and uzunluk_ok and formul_tanimli_mi(datatype):
        out["output_length"] = expected_output_length(dt, length, decimals if isinstance(decimals, int) else 0)
        out["output_length_rule"] = ("sabit" if dt.startswith("INT")
                                     else "length+4" if dt in ("DEC", "QUAN", "CURR") else "length")
    return out


@profil_tool()
def adt_domain_create(
    name: str,
    datatype: str,
    length: int,
    description: str,
    package: str,
    transport: str,
    decimals: int = 0,
    lowercase: bool = False,
    fixed_values: list[dict] | None = None,
    artifact_path: str | None = None,
) -> dict:
    """Create + activate + verify a DDIC domain atomically.

    Guardrails: Z/Y prefix, transport non-empty, description non-empty.
    aXet: argüman ön kontrolü (artefakt beklemeden, ağdan önce) → `steps.pre_flight`; BLOCKER →
    `error: preflight_blocker` (datatype formülü, length/decimals, lowercase, sabit değer metni).
    Reviewer (ADR 0006): artifact_path (domain CSV/XML) verilirse `domain_creation_csv` zinciri; BLOCKER rejects.
    Verilmezse reviewer SKIP (`no_artifact_path_provided`) ve yanıtta görünür.

    Args:
        name: Domain name (Z*/Y*).
        datatype: 'CHAR', 'NUMC', 'INT4', 'CURR', 'QUAN', 'DATS', 'TIMS', 'DEC', ...
        length: Field length.
        description: TR description (ADR 0005 §D — non-empty).
        package: Target package (must exist).
        transport: Modifiable transport.
        decimals: Decimal places (CURR/QUAN/DEC).
        lowercase: Allow lowercase letters.
        fixed_values: [{'value':'A','text':'...'}]
        artifact_path: Optional local domain CSV (`name,datatype,length,decimals,description,fixed_values`)
                       or domain XML for reviewer pre-flight (`domain_creation_csv`, ADR 0006).

    Returns:
        {ok, name, type:'doma', reviewer, steps: {pre_flight, reviewer, pre_check, create, activate, verify}, ...}
    """
    obj_type = "doma"
    try:
        require_writable_tier(get_active_tier(), what="domain create")
        require_customer_namespace(name, what=obj_type)
        require_transport(transport, what=f"{obj_type} create", package=package)
        require_tr_text(description, what="domain description")
    except GuardrailViolation as gv:
        return gv.as_dict()

    steps: dict[str, Any] = {}
    # Argüman ön kontrolü — artefakt BEKLEMEZ, ağdan ÖNCE (aXet 2026-09-13).
    steps["pre_flight"] = _domain_on_kontrol(datatype, length, decimals, lowercase, fixed_values)
    if steps["pre_flight"]["verdict"] == "BLOCKER":
        return {"ok": False, "error": "preflight_blocker", "name": name, "type": obj_type,
                "message": "Domain argüman ön kontrolü BLOCKER (SAP'ye gidilmedi): "
                           + "; ".join(f["message"] for f in steps["pre_flight"]["findings"]),
                "steps": steps}

    # Reviewer pre-flight (ADR 0006)
    blocker, warn = _maybe_reviewer("adt_domain_create", name, obj_type, artifact_path)
    if blocker:
        blocker["steps"] = steps
        return blocker
    steps["reviewer"] = warn["reviewer"]

    try:
        client = _get_client()
    except Exception as exc:  # noqa: BLE001 — bağlantı kurulamadıysa da pre_flight/reviewer izi yanıtta kalsın
        return {**_err_from_exc(exc), "name": name, "type": obj_type, "reviewer": warn["reviewer"], "steps": steps}

    # 1. Pre-check — üç değerli (Z51 ⓐ): var → already_exists · ölçülemedi → exists_unmeasured (POST YOK) · yok → yarat.
    var, sonda = _ddic_varligi(name, obj_type)
    steps["pre_check"] = sonda
    if var is True:
        return {
            "ok": False,
            "error": "already_exists",
            "message": f"Domain {name} zaten mevcut. Önce adt_get ile incele, gerekirse manuel delete sonra tekrar dene.",
            "name": name,
            "type": obj_type,
            "reviewer": warn["reviewer"],
            "steps": steps,
        }
    if var is None:
        return {"ok": False, "error": "exists_unmeasured", "name": name, "type": obj_type,
                "reviewer": warn["reviewer"], "steps": steps,
                "message": (f"Domain varlığı ÖLÇÜLEMEDİ ({sonda}) — bu 'yok' DEĞİL; yaratma denenmedi (fail-closed: var "
                            "olan bir domain'i 'yaratıldı' diye aktive etme riski). Bağlantıyı kontrol edip tekrar dene.")}

    # 2. Create (shell + source)
    try:
        with _capture() as buf:
            created = client.create_domain(
                name=name,
                datatype=datatype,
                length=length,
                description=description,
                package=package,
                transport=transport,
                decimals=decimals,
                lowercase=lowercase,
                fixed_values=fixed_values,
            )
        steps["create"] = {"ok": bool(created), "log": buf.getvalue().strip()}
    except Exception as exc:
        steps["create"] = _err_from_exc(exc)
        return {"ok": False, "name": name, "type": obj_type, "steps": steps, "reviewer": warn["reviewer"]}

    if not created:
        from sapadt.tools.atom import _create_hata_sinifi
        kod, _aciklama = _create_hata_sinifi(steps["create"]["log"])
        if kod == "already_exists":
            # Kütüphane AlreadyExists'te artık `success:True` DÖNMEZ (SAPObjectExistsError) → aktivasyon YOK.
            return _zaten_var_yaniti("Domain", name, obj_type, steps["create"]["log"], steps=steps,
                                     reviewer=warn["reviewer"])
        return {"ok": False, "name": name, "type": obj_type, "steps": steps, "reviewer": warn["reviewer"],
                "error": kod, "message": "create_domain returned False — see steps.create.log"}

    # 3+4. Activate + verify
    tail = _activate_and_verify(client, name, obj_type)
    steps["activate"] = {"ok": tail.get("activated", False), "log": tail.get("activate_log", "")}
    if "activate_error" in tail:
        steps["activate"]["error"] = tail["activate_error"]
    steps["verify"] = {"ok": tail.get("verified", False)}
    if tail.get("master_language_warning"):
        steps["verify"]["master_language_warning"] = tail["master_language_warning"]

    ok_overall = steps["create"].get("ok") and tail.get("activated") and tail.get("verified")
    out = {
        "ok": bool(ok_overall),
        "name": name,
        "type": obj_type,
        "datatype": datatype,
        "length": length,
        "output_length": steps["pre_flight"].get("output_length"),
        "steps": steps,
    }
    if warn:
        out["reviewer"] = warn["reviewer"]
    return out


# =============================================================================
# adt_dtel_create
# =============================================================================

@profil_tool()
def adt_dtel_create(
    name: str,
    domain_name: str,
    description: str,
    package: str,
    transport: str,
    short_label: str,
    medium_label: str,
    long_label: str,
    heading_label: str,
    artifact_path: str | None = None,
) -> dict:
    """Create + activate + verify a DDIC data element atomically.

    ADR 0005 §D: All 4 labels (short/medium/long/heading) MUST be filled with TR text.
    Reviewer (ADR 0006): if artifact_path given, pre-flight runs; BLOCKER rejects.

    Args:
        name: Data element name (Z*/Y*).
        domain_name: Underlying domain (Z* preferred; standard ABAP types like CHAR1 also OK).
        description: TR description.
        package: Target package.
        transport: Modifiable transport.
        short_label, medium_label, long_label, heading_label: 4 TR labels (non-empty each).
        artifact_path: Optional local file path for reviewer pre-flight (ADR 0006).

    Returns:
        {ok, name, type:'dtel', steps, ...}
    """
    obj_type = "dtel"
    labels = {
        "short": short_label or "",
        "medium": medium_label or "",
        "long": long_label or "",
        "heading": heading_label or "",
    }
    try:
        require_writable_tier(get_active_tier(), what="dtel create")
        require_customer_namespace(name, what=obj_type)
        require_transport(transport, what=f"{obj_type} create", package=package)
        require_tr_text(description, what="dtel description")
        require_all_labels(labels, expected=["short", "medium", "long", "heading"])
        require_label_lengths(labels)
    except GuardrailViolation as gv:
        return gv.as_dict()

    blocker, warn = _maybe_reviewer("adt_dtel_create", name, obj_type, artifact_path)
    if blocker:
        return blocker

    client = _get_client()
    steps: dict[str, Any] = {}

    # Üç değerli ön kontrol (Z51 ⓐ) — domain ile aynı.
    var, sonda = _ddic_varligi(name, obj_type)
    steps["pre_check"] = sonda
    if var is True:
        return {
            "ok": False,
            "error": "already_exists",
            "message": f"Data element {name} zaten mevcut.",
            "name": name,
            "type": obj_type,
            "steps": steps,
        }
    if var is None:
        return {"ok": False, "error": "exists_unmeasured", "name": name, "type": obj_type, "steps": steps,
                "message": (f"Data element varlığı ÖLÇÜLEMEDİ ({sonda}) — bu 'yok' DEĞİL; yaratma denenmedi "
                            "(fail-closed). Bağlantıyı kontrol edip tekrar dene.")}

    try:
        with _capture() as buf:
            created = client.create_dataelement(
                name=name,
                domain_name=domain_name,
                description=description,
                package=package,
                transport=transport,
                short_label=short_label,
                medium_label=medium_label,
                long_label=long_label,
                heading_label=heading_label,
            )
        steps["create"] = {"ok": bool(created), "log": buf.getvalue().strip()}
    except Exception as exc:
        steps["create"] = _err_from_exc(exc)
        return {"ok": False, "name": name, "type": obj_type, "steps": steps}

    if not created:
        from sapadt.tools.atom import _create_hata_sinifi
        kod, _aciklama = _create_hata_sinifi(steps["create"]["log"])
        if kod == "already_exists":
            return _zaten_var_yaniti("Data element", name, obj_type, steps["create"]["log"], steps=steps)
        return {"ok": False, "name": name, "type": obj_type, "steps": steps, "error": kod,
                "message": "create_dataelement returned False"}

    tail = _activate_and_verify(client, name, obj_type)
    steps["activate"] = {"ok": tail.get("activated", False), "log": tail.get("activate_log", "")}
    if "activate_error" in tail:
        steps["activate"]["error"] = tail["activate_error"]
    steps["verify"] = {"ok": tail.get("verified", False)}
    if tail.get("master_language_warning"):
        steps["verify"]["master_language_warning"] = tail["master_language_warning"]

    ok_overall = steps["create"].get("ok") and tail.get("activated") and tail.get("verified")
    out = {
        "ok": bool(ok_overall),
        "name": name,
        "type": obj_type,
        "domain": domain_name,
        "steps": steps,
    }
    if warn:
        out["reviewer"] = warn["reviewer"]
    return out


# =============================================================================
# adt_struct_create
# =============================================================================

@profil_tool()
def adt_struct_create(
    name: str,
    fields: list[dict],
    description: str,
    package: str,
    transport: str,
    artifact_path: str | None = None,
) -> dict:
    """Create + activate + verify a DDIC structure (INTTAB) atomically.

    Reviewer (ADR 0006): the DDL actually written (`fields[]` + descriptions, same renderer as create_structure) ALWAYS
    runs `struct_fields_dtel` (Z/Y + /ns/ DTEL existence/activity; configurable total budget incl. client setup, default 28 s, no retry); if artifact_path is given it must
    exist (else BLOCKER artifact_not_found) and run_review.py struct_creation runs too, verdicts merged.
    BLOCKER rejects (must fix and retry). Unmeasured DTEL gate / budget exhausted / wrapper timeout (default 60 s,
    `AXET_REVIEWER_BUTCE_SN`) = BLOCKER. Strongly recommended for Sprint 6 flow:
    coordinator generates a local .asddls via sprint6_adapt_struct.py, then passes
    that path here so the reviewer can validate DTEL activity and annotations.

    Args:
        name: Structure name (Z*/Y*).
        fields: [{'name':'FIELD1','type':'char10'}, {'name':'CUST','type':'ZDEMO0_E_CUST'}, ...]
                'type' is either ABAP primitive (char10, numc8, ...) or a data element name.
        description: TR description.
        package: Target package.
        transport: Modifiable transport.
        artifact_path: Path to local .asddls / .ddls / struct source for reviewer.

    Returns:
        {ok, name, type:'tabl', steps, fields_count, reviewer?, ...}
        Ön kontrol üç değerli (üzerine yazma YOK): var → `already_exists` (`existing_kind: structure|table`) ·
        ölçülemedi → `exists_unmeasured` (POST atılmaz) · POST 400/405 AlreadyExists → `already_exists` (PUT/aktivasyon yok).
    """
    obj_type = "tabl"  # yanıt/reviewer sözleşmesindeki tip (TABL ana tipi; yapı = INTTAB kategorisi)
    # ⛔ ADRES tipi AYRI (canlı 2026-09-21, DEV): yapılar ADT'de `/ddic/structures/` altında yaşar. `tabl` ile
    # varlık sondası ve metadata doğrulaması `/ddic/tables/` ucuna soruyordu → yapı AKTİF yaratıldığı hâlde
    # `verify: metadata_not_found` + `ok:false` (DD02L INTTAB/A, DD03L 2 satır ile teyit), ön kontrol de mevcut
    # yapıyı "yok" görüyordu. Kusur 2026-09-16 ilk commit'ten beri `main`'de. Aktivasyon adresi `tabl` KALDI:
    # o yol canlıda çalıştı (yapı aktive oldu); `structure` ucuyla aktivasyon ÖLÇÜLMEDİ.
    adres_tipi = "structure"
    try:
        require_writable_tier(get_active_tier(), what="structure create")
        require_customer_namespace(name, what="structure")
        require_transport(transport, what="structure create")
        require_tr_text(description, what="structure description")
    except GuardrailViolation as gv:
        return gv.as_dict()
    if _paket_bos_mu(package):
        return _paket_reddi(name, obj_type)
    if not fields or not isinstance(fields, list):
        return {"ok": False, "error": "validation_error",
                "message": "fields boş olamaz — en az 1 field gerekli"}
    for i, f in enumerate(fields):
        if not isinstance(f, dict) or not f.get("name") or not f.get("type"):
            return {"ok": False, "error": "validation_error",
                    "message": f"fields[{i}] geçersiz — 'name' ve 'type' zorunlu"}
    # Tur 3 (3. dar gate, MEDIUM): yapı açıklaması ile alan açıklaması/adı/tipi DDL'e tek satır olarak girer; satır sonu
    # (CR, LF, U+2028, U+2029, U+0085) gate'in çıkarıcısında gerçek alan satırlarını gizleyebiliyordu (`--` + `/*`). Karakter kümesi
    # ve bakılan yerler TEK KAYNAK: `utils.ddic_dtel.satir_sonu_ihlali` (render da aynı fonksiyonla reddeder). Ağa/reviewer'a GİTMEDEN.
    try:
        from utils.ddic_dtel import satir_sonu_ihlali  # type: ignore
    except Exception as exc:  # noqa: BLE001 — kontrol yüklenemezse yazma yok (fail-closed)
        return {"ok": False, "error": "validation_error",
                "message": f"satır sonu kontrolü yüklenemedi ({type(exc).__name__}) — yapı yaratılmadı"}
    ihlal = satir_sonu_ihlali(fields, description)
    if ihlal:
        yer, kod = ihlal
        return {"ok": False, "error": "validation_error",
                "message": f"{yer} satır sonu karakteri içeriyor: {kod}. Yapı açıklaması ile alan açıklaması, "
                           f"adı ve tipi tek satır olmalı — satır sonunu kaldırıp tekrar dene."}

    # D1 (aXet 2026-09-14, kullanıcı kararı "Dosyasız çağrıda da koşsun") + bug gate B1/B2 düzeltmesi:
    # SAP'ye yazılan yük `fields[]`'ten kurulan DDL'dir (`sap_adt_lib.create_structure` → `utils.ddic_dtel.yapi_ddl_kaynagi`;
    # re-gate 2026-09-15: gate AYNI render'ı denetler, alan/yapı açıklamaları dahil → `description` geçirilir) → DTEL'ler DAİMA
    # `fields[]`'ten çıkarılır ve yazmadan ÖNCE `check_struct_field_dtel_active.py` koşar (`struct_fields_dtel`),
    # artefakt verilsin verilmesin. `artifact_path` verilirse: yol yoksa BLOCKER (artifact_not_found; ağa gidilmez),
    # varsa `struct_creation` zinciri de koşar, hükümler birleşir (`_reviewer.run_reviewer_struct`). Fail-closed:
    # DTEL yok/inaktif → BLOCKER · SAP okunamadı ya da gate'in süre bütçesi doldu (measured=false) → SKIP = BLOCKER ·
    # sarmalayıcı zaman aşımı (varsayılan 60 sn, `AXET_REVIEWER_BUTCE_SN` ile ayarlanır) → BLOCKER
    # (ÖLÇÜLEMEDİ; K10'dan beri canlı BLOCKER gate taşıyan HER zincirde — IMPLEMENTATION §20.9).
    # Boş `fields[]` yukarıda `validation_error` ile reviewer'dan ÖNCE reddedilir (yazma yok).
    on_sonuc = run_reviewer_struct(name, fields, artifact_path, description=description)
    blocker, warn = _maybe_reviewer("adt_struct_create", name, obj_type, artifact_path, result=on_sonuc)
    if blocker:
        return blocker

    client = _get_client()
    steps: dict[str, Any] = {}

    # ⛔ ÜZERİNE YAZMA KAPISI (2026-09-21, bug gate): eski `_exists` hata/None'da "yok" diyordu (fail-open) ve
    # `create_structure` POST 405 AlreadyExists'te kaynağı yine PUT edip aktive ediyordu ⇒ ön kontrol yanlış "yok"
    # derse MEVCUT yapı yeni alanlarla EZİLİYORDU. Artık üç değerli: var → already_exists · ölçülemedi →
    # exists_unmeasured (POST YOK) · yok → yarat. Aynı adlı şeffaf tablo da `already_exists` (existing_kind: table).
    var, sonda, tur = _yapi_varligi(name)
    steps["pre_check"] = sonda
    if var is True:
        return {
            "ok": False,
            "error": "already_exists",
            "existing_kind": tur,
            "message": (f"Structure {name} zaten mevcut — üzerine YAZILMADI." if tur == "structure" else
                        f"{name} adında bir ŞEFFAF TABLO zaten var (/ddic/tables/) — yapı yaratılmadı, hiçbir şey "
                        "yazılmadı. Farklı bir ad seç."),
            "name": name,
            "type": obj_type,
            "steps": steps,
            "reviewer": warn["reviewer"],
        }
    if var is None:
        return {
            "ok": False,
            "error": "exists_unmeasured",
            "message": (f"Yapı varlığı ÖLÇÜLEMEDİ ({sonda}) — bu 'yok' DEĞİL; yaratma denenmedi (fail-closed, mevcut "
                        "bir yapının üzerine yazma riski). Bağlantıyı kontrol edip tekrar dene ya da adt_get(structure) ile ölç."),
            "name": name,
            "type": obj_type,
            "steps": steps,
            "reviewer": warn["reviewer"],
        }

    try:
        with _capture() as buf:
            created = client.create_structure(
                name=name,
                fields=fields,
                description=description,
                package=package,
                transport=transport,
            )
        steps["create"] = {"ok": bool(created), "log": buf.getvalue().strip()}
    except Exception as exc:
        steps["create"] = _err_from_exc(exc)
        return {"ok": False, "name": name, "type": obj_type, "steps": steps, "reviewer": warn["reviewer"]}

    if not created:
        from sapadt.tools.atom import _create_hata_sinifi
        kod, _aciklama = _create_hata_sinifi(steps["create"]["log"])
        if kod == "already_exists":
            # Ön kontrol "yok" dedi ama SAP POST'u "zaten var" diye reddetti (yarış, görünmeyen uç ya da Z52: aynı
            # çağrıdaki 5xx sonrası yeniden deneme). `create_structure` bu durumda PUT ETMEZ (SAPObjectExistsError).
            return _zaten_var_yaniti("Yapı", name, obj_type, steps["create"]["log"], steps=steps,
                                     reviewer=warn["reviewer"])
        return {"ok": False, "name": name, "type": obj_type, "steps": steps, "reviewer": warn["reviewer"],
                "error": kod, "message": "create_structure returned False — steps.create.log'a bak."}

    tail = _activate_and_verify(client, name, obj_type, verify_type=adres_tipi)
    steps["activate"] = {"ok": tail.get("activated", False), "log": tail.get("activate_log", "")}
    if "activate_error" in tail:
        steps["activate"]["error"] = tail["activate_error"]
    steps["verify"] = {"ok": tail.get("verified", False), "endpoint": "ddic/structures"}
    if tail.get("master_language_warning"):
        steps["verify"]["master_language_warning"] = tail["master_language_warning"]
    if "verify_reason" in tail:
        steps["verify"]["reason"] = tail["verify_reason"]
    if "sap_version" in tail:
        steps["verify"]["sap_version"] = tail["sap_version"]

    # KOŞULSUZ içerik-doğrulama (artifact_path OLMASA da) — 'activated' bir placeholder
    # shell'i maskeliyor olabilir. Aktivasyon+versiyon OK ise sistemden İÇERİK okunur.
    content_ok = True
    if tail.get("verified"):
        content = _verify_ddic_content(client, name, adres_tipi)
        steps["content_verify"] = content
        content_ok = content.get("ok", False)

    # Sprint 6 T10 — post-create consistency check (placeholder + field count diff).
    # adt_struct_create fields[] yöntemi bazen SAP'de sadece placeholder bırakır.
    # artifact_path verilmişse, lokal artifact ile SAP'deki source'u karşılaştır.
    # ⛔ Q293 (2026-09-13): `consistency_ok = consistency.passed` İKİ YÖNDE yanlıştı —
    # WARNING (reviewer_timeout / measured=false) `ok:false` (sahte-FAIL), SKIP (post-check HİÇ
    # koşmadı) `ok:true` + `post_check.ok:true` (ölçülemedi = temiz). Artık Q273 sözleşmesi
    # (tek kaynak `_reviewer.post_check_ozeti`): `ok` yalnız BLOCKER / tanınmayan verdict /
    # blocker_count>0 ile düşer; ölçülemeyen kapı `post_check.unmeasured` + `hukum` +
    # üst düzey `post_check_notice` ile GÖRÜNÜR.
    consistency_ok = True
    notice_ozet = None
    if artifact_path:
        consistency = run_reviewer("struct_post_create", artifact_path)
        ozet, dusur = _post_check_ozeti(consistency)
        steps["post_check"] = ozet
        consistency_ok = not dusur
        if not dusur and (ozet.get("verdict") == "WARNING" or ozet.get("unmeasured")):
            notice_ozet = ozet

    ok_overall = (steps["create"].get("ok") and tail.get("activated")
                  and tail.get("verified") and consistency_ok and content_ok)
    out = {
        "ok": bool(ok_overall),
        "name": name,
        "type": obj_type,
        "fields_count": len(fields),
        "steps": steps,
    }
    if not ok_overall:
        # Hata kodu: CLI eskiden `tool_failed` + boş mesaj gösteriyordu (canlı 2026-09-21) — hangi adımın düştüğü görünsün.
        out["error"] = ("activation_failed" if not tail.get("activated") else
                        "verify_failed" if not tail.get("verified") else
                        "content_verify_failed" if not content_ok else "post_check_blocker")
        out["message"] = ("Yapı yaratıldı ama doğrulama tamamlanmadı — obje SİLİNMEDİ; steps.%s'e bak."
                          % {"activation_failed": "activate", "verify_failed": "verify",
                             "content_verify_failed": "content_verify",
                             "post_check_blocker": "post_check"}[out["error"]])
    if notice_ozet is not None and ok_overall:
        # Notice "yaratma BAŞARILI" der ⇒ yalnız işlem gerçekten başarılıyken üst düzeye konur;
        # başarısız yanıtta ölçülemeyen kapı `steps.post_check.unmeasured`'da zaten durur.
        out["post_check_notice"] = _post_check_notice(notice_ozet, islem="yaratma")
    if warn:
        out["reviewer"] = warn["reviewer"]
    return out
