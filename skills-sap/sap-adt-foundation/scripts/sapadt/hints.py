# -*- coding: utf-8 -*-
"""Engellemeyen yönlendirme ipuçları (aXet 2026-09-13) — CLI yanıtına eklenir, KARAR VERMEZ, çıkış kodunu DEĞİŞTİRMEZ.

  checklist_hint     yazma sınıfı çağrıda: obje tipine göre okunacak skill referansı (iş türü kontrol listesi)
  known_errors_hint  başarısız çağrıda (çıkış 1/2): hata kodu + SAP mesaj sınıfı/numarası/HTTP deseni → bilinen-hata maddesi

KAYNAK (kaynak çekirdek salt-okur; oradaki iki oturum kancasının aXet karşılığı — aXet'te kanca yok, ipucu CLI yanıtında taşınır):
  · iş türü: `scripts/hooks/sap_worktype_hint.py:36-40` (araç → tip: dtel_create→dtel, domain_create→doma, struct_create→struct,
    publish_service→srvb) · `:42` (push_source/activate → object_type) · `:46-62` `_checklist()` grup kuralları
    (ddls/cds/view → cds · bdef/srvd/srvb/beh/behavior/service → rap · doma/dtel → ddic-dd · struct/tabl/stru → ddic-st ·
    prog/report/dynpro → classic). Hedefler aXet skill referanslarına çevrildi. **aXet eki** (kaynak kancada grup yok, hedef dosya var):
    class/interface → classes.md · fugr/func → fugr-fm.md · msag → message-class.md · enqu → lock-objects.md · ekran üreteci → screen-gen-kit.md.
    Alt-tür (abstract entity vb.) ayrımı (`:67-100`) ALINMADI → açık kalem.
  · hata: `scripts/hooks/post_tool_failure.py:37-38` başarısızlık kodları · `:60-66` CDS imzaları · `:86-90` kilit/oturum imzaları.
    Madde eşlemesi aXet indekslerinden: `references/known-errors-adt.md:10-38` (K-01…K-26) ve
    `skills-sap/sap-classic-abap/references/known-errors-classic.md` indeks tablosu. ATC P1 ekseni (`:142-200`) ALINMADI → açık kalem.
"""
from __future__ import annotations

import re
from pathlib import Path

from sapadt import PKG_DIR

SKILLS_SAP = PKG_DIR.parents[2]                      # sapadt → scripts → sap-adt-foundation → skills-sap
# Lider brifingi (2026-09-13): bu iki skill başka bir iş kolunda yazılıyor; dosya yoksa durum "yazılıyor".
YAZILIYOR = frozenset({"sap-ui5-fiori/SKILL.md", "sap-code-review/SKILL.md"})

_CDS = "sap-cds-ddic/references/"
_RAP = "sap-rap/references/"
_KLS = "sap-classic-abap/references/"
GRUP_REFERANSLARI = {
    "cds": (_CDS + "cds.md", _CDS + "checklists.md"),
    "rap": (_RAP + "checklists.md", _RAP + "layering-and-bdef.md", _RAP + "service-publish.md"),
    "ddic-dd": (_CDS + "domain-dtel.md", _CDS + "checklists.md"),
    "ddic-st": (_CDS + "tables-structures.md", _CDS + "checklists.md"),
    "classic": (_KLS + "programs-includes.md", _KLS + "checklists.md"),
    # aXet eki
    "class": (_KLS + "classes.md", _KLS + "checklists.md"),
    "fugr": (_KLS + "fugr-fm.md", _KLS + "checklists.md"),
    "msag": (_CDS + "message-class.md",),
    "enqu": (_CDS + "lock-objects.md",),
    "screen": (_KLS + "screen-gen-kit.md", _KLS + "dynpro-gui-status.md", _KLS + "checklists.md"),
}
# araç → obje tipi (sap_worktype_hint.py:36-40 + aXet araçları)
ARAC_TIPI = {"adt_dtel_create": "dtel", "adt_domain_create": "doma", "adt_struct_create": "struct",
             "adt_table_create": "tabl", "adt_ttyp_create": "ttyp", "adt_textpool_write": "prog",
             "adt_publish_service": "srvb", "adt_msgclass_write": "msag", "adt_screen_generate": "screen"}
# kaynak metni taşıyan araç → kod inceleme skill'i; servis yayını → UI5 skill'i (ikisi de YAZILIYOR)
ARAC_EK_REFERANS = {"adt_push_source": ("sap-code-review/SKILL.md",), "adt_publish_service": ("sap-ui5-fiori/SKILL.md",),
                    "adt_ttyp_create": ("sap-cds-ddic/references/table-types.md",)}


def tip_grubu(otype) -> str | None:
    """sap_worktype_hint.py:46-62 sırası korunur; aXet grupları sonra denenir."""
    t = str(otype or "").lower().strip()
    if not t:
        return None
    if t.startswith("ddls") or "cds" in t or t.startswith("view"):
        return "cds"
    if t.startswith(("bdef", "srvd", "srvb", "beh")) or "behavior" in t or "service" in t:
        return "rap"
    if t.startswith(("doma", "dtel")) or t in ("dataelement", "domain"):
        return "ddic-dd"
    if t.startswith("struct") or t.startswith("tabl") or t in ("stru", "ttyp"):
        return "ddic-st"
    if t.startswith("prog") or "report" in t or "dynpro" in t or t in ("include", "incl"):
        return "classic"
    if t in ("screen",):
        return "screen"
    if t in ("class", "clas", "interface", "intf", "ccimp", "ccau", "ccdef", "ccmac"):
        return "class"
    if t in ("fugr", "func", "function", "functiongroup"):
        return "fugr"
    if t in ("msag", "messageclass"):
        return "msag"
    if t in ("enqu", "lock", "lockobject", "lockobjects"):
        return "enqu"
    return None


def _ref(rel: str) -> dict:
    var = (SKILLS_SAP / rel).is_file()
    durum = "var" if var else ("yazılıyor" if rel in YAZILIYOR else "yok")
    return {"path": f"skills-sap/{rel}", "status": durum}


def checklist_hint(tool: str, args: dict | None) -> dict | None:
    a = args if isinstance(args, dict) else {}
    otype = ARAC_TIPI.get(tool) or (a.get("object_type") if isinstance(a.get("object_type"), str) else None)
    grup = tip_grubu(otype)
    yollar = list(GRUP_REFERANSLARI.get(grup, ())) + list(ARAC_EK_REFERANS.get(tool, ()))
    if not yollar:
        return None
    return {"group": grup, "object_type": otype, "refs": [_ref(y) for y in dict.fromkeys(yollar)],
            "note": "Engellemez. Bu iş türünün kontrol listesini yazmadan önce/sonra oku; status 'yazılıyor' = hedef henüz yok."}


# ── bilinen hatalar ──────────────────────────────────────────────────────────────────────────────
_KE = "sap-adt-foundation/references/known-errors-adt.md"
_KC = "sap-classic-abap/references/known-errors-classic.md"
_OPS = "sap-adt-foundation/references/foundation-ops.md"
_SKILL = "sap-adt-foundation/SKILL.md"

# (hata kodu kümesi, dosya, bölüm, neden)
KOD_KURALLARI = (
    ({"lock_conflict", "lock_failed", "locked"}, _KE, "K-07 · K-09", "kilit alınamadı — enqueue kilidi silinmez; SM12 kullanıcıda"),
    ({"transport_mismatch"}, _KE, "K-02", "obje istenen transporta kayıtlı değil"),
    ({"put_precondition_failed", "envelope_changed_since_read"}, _KE, "K-01 · K-19", "ETag / envelope PUT 412"),
    ({"activation_required", "activation_failed", "activation_not_verified", "activation_state_unknown",
      "activation_not_executed"}, _KE, "K-10 · K-19", "obje inaktif kaldı ya da aktivasyon kanıtlanmadı"),
    ({"description_too_long", "create_not_persisted"}, _KE, "K-16", "kısa metin sınırı / yaratma sonrası varlık"),
    ({"readback_mismatch", "readback_failed"}, _KE, "K-10", "yazma aktif sürümde doğrulanmadı"),
    ({"auth_failed"}, _KE, "K-24", "kimlik reddi — parolayı tekrar tekrar deneme"),
    ({"connection_failed", "doctor_fail", "discovery_unavailable"}, _OPS, "§1 Bağlantı kontrolü (sap_doctor)", "bağlantı katmanı"),
    ({"tier_not_writable", "conn_env_mismatch"}, _OPS, "§10 Çoklu sistem ve tier", "bağlantı dosyası / tier"),
    ({"language_mismatch", "master_language_unresolved"}, _KE, "K-17", "master_language"),
    ({"pull_before_edit_missing", "source_changed_since_pull", "pull_live_read_failed", "pull_state_unreadable"},
     _SKILL, "§2 Önce oku — pull-before-edit", "çekme kaydı / canlı değişiklik"),
    ({"ADR_0005_A", "ADR_0005_B", "ADR_0005_C", "ADR_0005_D", "ADR_0010_TIER", "std_dml_scan_unavailable",
      "sap_project_missing", "sap_project_invalid", "write_not_optin_global", "write_flag_missing", "scope_missing",
      "scope_invalid", "reason_missing", "intake_missing", "intake_invalid", "reviewer_bypass_forbidden",
      "tool_not_available_for_profile", "type_not_available_for_profile", "repeated_failure"},
     _SKILL, "§4 Yazma ön koşulları ve kapsam beyanı", "kapı reddi — aşmaya çalışma, kullanıcıya bildir"),
)
# (metin deseni, dosya, bölüm, neden) — indeks satırlarındaki belirtilerden
METIN_KURALLARI = (
    (re.compile(r"SADT_RESOURCE\s*0?43"), _KE, "K-19 · K-01", "envelope/kaynak ETag uyuşmazlığı"),
    (re.compile(r"\b412\b|PreconditionFailed|does not match the object ETag", re.I), _KE, "K-01", "412 yanlış ETag"),
    (re.compile(r"InvalidLockHandle|invalid lock handle|is not locked", re.I), _KE, "K-02 · K-03 · K-15", "423 / kilit handle"),
    (re.compile(r"\b423\b"), _KE, "K-02 · K-03", "423"),
    (re.compile(r"\b409\b|\bConflict\b"), _KE, "K-05", "409 — ASLA retry"),
    (re.compile(r"corrNr not found", re.I), _KE, "K-06", "400 corrNr"),
    (re.compile(r"EU\s*510"), _KE, "K-07", "editör kilidi"),
    # 2026-09-14: kilit çakışması tarifi (`sap_adt_lib.KILIT_CAKISMA_TARIFI`). Düz push yanıtında üst seviye `error`
    # yok; kilit mesajı artık "EU 510" demediği için ipucu yalnız bu metinden gelir (test_kilit_politikasi H1).
    (re.compile(r"enqueue kilidini SİLMEZ"), _KE, "K-09", "kilit çakışması — araç kilit silmez; SM12 kullanıcıda"),
    (re.compile(r"REPORT/PROGRAM statement is missing", re.I), _KE, "K-11", "include yanlış tipte"),
    (re.compile(r"Include not found", re.I), _KE, "K-12", "include aktivasyon listesinde yok"),
    (re.compile(r"if_oo_adt_classrun~main", re.I), _KE, "K-13", "classrun bayat/inaktif"),
    (re.compile(r"Session Timed Out", re.I), _KE, "K-14", "classrun dialog context"),
    (re.compile(r"Parameter comment blocks", re.I), _KE, "K-15", "FM imza yorum bloğu"),
    (re.compile(r"CSRF", re.I), _KE, "K-18", "CSRF"),
    (re.compile(r"ResourceScanDuringSaveFailure", re.I), _KE, "K-20", "satırsız save-scan (bisect)"),
    (re.compile(r"TEXT-\w+ cannot be modified", re.I), _KE, "K-21", "TEXT-xxx ataması"),
    (re.compile(r"\b401\b|Unauthorized", re.I), _KE, "K-24", "401"),
    (re.compile(r"does not contain a valid definition", re.I), _OPS, "§4.5 CDS (DDLS) yaratma — protokol notları",
     "CDS kaynağı boş/geçersiz (inline POST boş kaynak tuzağı)"),
    (re.compile(r"OO_SOURCE_BASED\s*0?12|unknown comments", re.I), _KC, "classes.md §3", "yetim yorum"),
    (re.compile(r"\bED\s*170\b"), _KC, "classes.md §5", "test include inaktif sürüm yok"),
    (re.compile(r"FUNC_ADT\s*0?15|\bFL\s*387\b", re.I), _KC, "fugr-fm.md §2.1", "FM parametre tipi"),
    (re.compile(r"CTS_WBO_API\s*0?20"), _KC, "fugr-fm.md §2.2", "görev yerine istek numarası"),
    (re.compile(r"Unexpected Case in Branch", re.I), _KC, "fugr-fm.md §3", "FM yaratma"),
    (re.compile(r"\bDS\s*512\b|SADT_RESOURCE\s*0?17|SADT_RESOURCE\s*0?26|Text elements contain errors", re.I), _KC,
     "programs-includes.md §3", "metin havuzu"),
    (re.compile(r"\b00256\b|\b00264\b"), _KC, "dynpro-gui-status.md §3", "GUI status"),
)
_MESAJ_ANAHTARI = re.compile(r"\b([A-Z][A-Z0-9_]{1,19})\s+(\d{3})\b")
_MESAJ_DISI = frozenset({"HTTP", "STATUS", "ERROR", "CODE", "LINE", "SATIR"})


def _metinler(result, err) -> str:
    parcalar = []
    if err:
        parcalar += [str(err[0] or ""), str(err[1] or "")]
    if isinstance(result, dict):
        for k in ("message", "sap_body", "client_log", "diagnosis", "diagnosis_423", "hint", "sap_message", "ev_message"):
            v = result.get(k)
            if isinstance(v, str):
                parcalar.append(v[:4000])
        for k in ("errors", "activation_errors", "syntax_errors"):
            v = result.get(k)
            if isinstance(v, list):
                parcalar += [str(x)[:500] for x in v[:20]]
    return "\n".join(parcalar)


def known_errors_hint(tool: str, result, err, exit_code: int) -> dict | None:
    if exit_code not in (1, 2):
        return None
    kodlar = {str(err[0])} if err else set()
    if isinstance(result, dict):
        for k in ("error", "code"):
            if isinstance(result.get(k), str):
                kodlar.add(result[k])
    eslesme: list[dict] = []

    def ekle(dosya, bolum, neden, tetik):
        anahtar = (dosya, bolum)
        if anahtar not in {(e["_d"], e["section"]) for e in eslesme}:
            eslesme.append({"_d": dosya, "path": f"skills-sap/{dosya}", "section": bolum, "why": neden, "matched": tetik})

    for kume, dosya, bolum, neden in KOD_KURALLARI:
        vur = sorted(kodlar & kume)
        if vur:
            ekle(dosya, bolum, neden, f"code:{vur[0]}")
    metin = _metinler(result, err)
    for rx, dosya, bolum, neden in METIN_KURALLARI:
        m = rx.search(metin)
        if m:
            ekle(dosya, bolum, neden, f"text:{m.group(0)[:40]}")
    anahtarlar = []
    for m in _MESAJ_ANAHTARI.finditer(metin):
        if m.group(1) not in _MESAJ_DISI:
            k = f"{m.group(1)} {m.group(2)}"
            if k not in anahtarlar:
                anahtarlar.append(k)
    if not eslesme and exit_code != 1:
        return None
    out = {"refs": [{k: v for k, v in e.items() if k != "_d"} for e in eslesme[:6]],
           "note": "Engellemez. Kör retry yapmadan önce maddeyi oku; eşleşme desen tabanlıdır, teşhis değildir."}
    if not eslesme:
        out["refs"] = [{"path": f"skills-sap/{_KE}", "section": "İndeks", "why": "eşleşen desen yok — indekste belirtiyle ara",
                        "matched": None},
                       {"path": f"skills-sap/{_KC}", "section": "İndeks", "why": "klasik ABAP (sınıf/program/FM/Dynpro) belirtileri",
                        "matched": None}]
    if anahtarlar:
        out["sap_message_keys"] = anahtarlar[:5]
    return out
