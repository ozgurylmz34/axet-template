"""Reviewer (ADR 0006) integration for MCP tools.

Wraps scripts/validators/run_review.py — calls it as a subprocess with --json,
parses the verdict, and returns a structured result MCP tools can act on.

Used by composite tools and adt_push_source as a mandatory pre-flight (BLOCKER
rejects the tool call). Manual CLI usage (`python scripts/validators/run_review.py
...`) remains a parallel option for local-only drafts.
"""
from __future__ import annotations

import ast
import functools
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

import os

from sapadt._app import REPO_ROOT, log
from sapadt.project import PROJECT_ENV, project_dir
# `sapadt` import'u lib/'i sys.path'e ekler (bkz. sapadt/__init__.py) → `utils.*` buradan görünür.
from utils import butce  # noqa: E402

# aXet: zincir paket içinde → sapadt/lib/validators/run_review.py
_REVIEW_SCRIPT = REPO_ROOT / "validators" / "run_review.py"
_MANUEL = ("python <sap-adt-foundation>/scripts/sapadt/lib/validators/run_review.py "
           "--task <X> --artifact <path> --json  (proje kökünden)")

# Sarmalayıcının tüm `run_review` zincirine verdiği süre: SABİT DEĞİL, YAPILANDIRILABİLİR (K10).
# Katman şeması (L1 sarmalayıcı > L2 zincir > L3 gate-içi) + varsayılanın ÖLÇÜM dayanağı TEK YERDE:
# `utils/butce.py` modül docstring'i. Eski `REVIEWER_ZAMAN_ASIMI_SN = 30` sabiti KALDIRILDI.

# ── K10 (kullanıcı kararı 2026-09-15: "Süreyi ölç + uzat, sonra BLOCKER") ──────────────────────────
# ÖLÇÜLEN KUSUR: sarmalayıcı zaman aşımı DAİMA WARNING'di (yazma yapılır). 2026-09-14'te (B1 a) bu
# YALNIZ DTEL gate'li 4 zincirde BLOCKER'a çevrilmişti ve o kayıt "genelleştirme KULLANICI KARARI
# bekliyor" diyordu. Karar geldi ⇒ KAPSAM SINIRI KALDIRILDI: canlı (SAP'ye bağlanan) bir gate'i
# BLOCKER önemiyle taşıyan HER zincirde zaman aşımı = BLOCKER (ÖLÇÜLEMEDİ). K10 ile kapsama
# YENİ giren zincirler: `struct_post_create`, `sap_active_check` (ikisi de canlı BLOCKER taşır ve
# eskiden zaman aşımında WARNING verip yazmaya izin veriyordu). Dayanak: "ölçülemedi ≠ temiz".
#
# ⭐ KÜME ELLE YAZILMAZ, KODDAN TÜRER (elle liste bayatlar): bir validator "CANLI"dır ⇔ kaynağında
#    `SAPADTClient` geçer (= SAP oturumu kurar, dolayısıyla ağ yüzünden asılabilir). Ölçülen küme
#    (2026-09-17): check_struct_field_dtel_active · check_sap_struct_consistency ·
#    check_sap_active_version · check_table_field_drop · check_standard_table_fields (sonuncusu
#    hiçbir zincirde BLOCKER değil → tek başına bir zinciri kapsama sokmaz).
_CANLI_IMI = re.compile(r"\bSAPADTClient\b")


def _yol_coz(node):
    """`HARICI_VALIDATORLER` değerlerindeki yol ifadesini AST'den çöz (modül ÇALIŞTIRILMADAN).

    Desteklenen biçim `run_review.py`dekiyle aynıdır: `VALIDATORS_DIR.parents[n] / 'a' / 'b.py'`.
    Tanınmayan bir düğüm → `None` (çağıran fail-closed davranır; sessizce "ağsız" SAYMAZ).
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name) and node.id == "VALIDATORS_DIR":
        return _REVIEW_SCRIPT.parent
    if isinstance(node, ast.Attribute):
        taban = _yol_coz(node.value)
        return getattr(taban, node.attr, None) if taban is not None else None
    if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
        taban = _yol_coz(node.value)
        try:
            return taban[node.slice.value]
        except Exception:  # noqa: BLE001
            return None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        sol, sag = _yol_coz(node.left), _yol_coz(node.right)
        return (sol / sag) if isinstance(sol, Path) and sag is not None else None
    return None


@functools.lru_cache(maxsize=1)
def _harici_yollar() -> dict:
    """`run_review.HARICI_VALIDATORLER` — zincirdeki ADI BAŞKA bir dosyaya eşleyen kayıt.

    ⛔ NEDEN GEREKLİ (lider düzeltmesi 2026-09-17): `check_itg_signoff.py` zincirde bu adla geçer
    ama GERÇEK dosya `sap-intake-triage/scripts/check_intake_signoff.py`dir (ad farkı bilinçli ve
    belgeli: "kopyalanmadı — tek kaynak orada kalır"). Bu eşlemeyi okumadan yapılan "dosyayı
    bulamadım ⇒ canlı say" kısayolu, dosya ÇÖZÜLEBİLİR olduğu hâlde yanlış sınıflandırıyordu.
    Yarın ağa ÇIKAN bir harici validator eklenirse aynı boşluk TERS yönde ısırırdı ("ağsız" sanmak).
    """
    try:
        for node in ast.parse(_REVIEW_SCRIPT.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == "HARICI_VALIDATORLER" for t in node.targets):
                if isinstance(node.value, ast.Dict):
                    return {k.value: _yol_coz(v) for k, v in zip(node.value.keys, node.value.values)
                            if isinstance(k, ast.Constant)}
    except Exception as exc:  # noqa: BLE001
        log.warning("HARICI_VALIDATORLER okunamadı (%s) — çözülemeyen ad fail-closed canlı sayılır", exc)
    return {}


def validator_yolu(script: str) -> Optional[Path]:
    """Zincirdeki script adının GERÇEK dosyası (harici eşleme dahil). Çözülemezse None."""
    harici = _harici_yollar()
    if script in harici:
        return harici[script]          # None olabilir → çözülemedi (fail-closed)
    return _REVIEW_SCRIPT.parent / script


def canli_mi(script: str) -> bool:
    """Bu validator SAP'ye canlı bağlanır mı? KODDAN ölçülür (kaynağında `SAPADTClient` geçer mi).

    ⛔ FAIL-CLOSED: yolu çözülemeyen ya da okunamayan dosya CANLI sayılır. "Okuyamadım"/"nerede
    olduğunu bilmiyorum" bir "ağa çıkmıyor" hükmü DEĞİLDİR.
    """
    yol = validator_yolu(script)
    if yol is None:
        log.warning("%s yolu çözülemedi — canlı sayıldı (fail-closed)", script)
        return True
    try:
        if not yol.exists():
            log.warning("%s bulunamadı (%s) — canlı sayıldı (fail-closed)", script, yol)
            return True
        return bool(_CANLI_IMI.search(yol.read_text(encoding="utf-8", errors="replace")))
    except Exception as exc:  # noqa: BLE001
        log.warning("%s okunamadı (%s) — canlı sayıldı (fail-closed)", script, exc)
        return True


@functools.lru_cache(maxsize=1)
def canli_validatorler() -> frozenset:
    """Zincirlerde geçen script adlarından CANLI olanlar — KODDAN türetilir (elle liste değil)."""
    zincir = _gorev_zincirleri() or {}
    adlar = {s for ogeler in zincir.values() for s, _sv, _d in ogeler}
    return frozenset(s for s in sorted(adlar) if canli_mi(s))


@functools.lru_cache(maxsize=1)
def _gorev_zincirleri() -> Optional[dict]:
    """`run_review.TASK_VALIDATORS` — AST ile (modül çalıştırılmadan). Okunamazsa None."""
    try:
        for node in ast.parse(_REVIEW_SCRIPT.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == "TASK_VALIDATORS" for t in node.targets):
                return ast.literal_eval(node.value)
    except Exception as exc:  # noqa: BLE001
        log.warning("TASK_VALIDATORS okunamadı (%s) — zaman aşımı fail-closed BLOCKER sayılır", exc)
    return None


def zaman_asimi_blocker_gorevleri() -> list:
    """Zaman aşımı BLOCKER sayılan görevler = zincirinde CANLI + BLOCKER gate olanlar (koddan türer)."""
    zincir = _gorev_zincirleri() or {}
    canli = canli_validatorler()
    return sorted(t for t, ogeler in zincir.items()
                  if any(s in canli and sv == "BLOCKER" for s, sv, _d in ogeler))


def zaman_asimi_blocker_gateleri(task: Optional[str]) -> list:
    """`task` zincirinde zaman aşımını BLOCKER yapan canlı gate'ler (mesajda adlarıyla geçer)."""
    ogeler = (_gorev_zincirleri() or {}).get(task or "", [])
    canli = canli_validatorler()
    return sorted({s for s, sv, _d in ogeler if s in canli and sv == "BLOCKER"})


def zaman_asimi_blocker_mi(task: Optional[str]) -> bool:
    if _gorev_zincirleri() is None:
        return True   # zincir okunamadı → hangi gate'in atlandığı bilinemez → fail-closed
    return task in zaman_asimi_blocker_gorevleri()

# Object type → reviewer task name. Tools pass object_type; we map to a known task.
# Tasks must exist in run_review.py TASK_VALIDATORS dict.
# ⚠ Keys are matched RAW (task_for_push lowercases only) — list every synonym that
#   adt_push_source may receive, otherwise the chain is skipped SILENTLY.
OBJECT_TYPE_TO_TASK = {
    "ddls": "cds_update",     # CDS view source push
    "tabl": "table_update",   # table or structure
    # 2026-07-29 — these three were None: ADR 0006 pre-flight was silently skipped for
    # class/bdef/srvd even though full validator chains existed (class_push has 6
    # validators / 2 BLOCKERs). Documented-but-unwired == unenforced.
    # Blast radius MEASURED on the live repo before wiring:
    #   class_push  → 5 real classes: 0 BLOCKER, 1-2 WARNING (non-blocking)
    #   rap_bdef_creation → 20 real bdefs: 19 PASS, 1 BLOCKER — and that one is a
    #     TRUE POSITIVE (managed root without `etag master`, standards/05 §lock).
    #   rap_service_binding → empty chain, degrades gracefully to PASS.
    # Emergency escape stays available: adt_push_source(skip_reviewer=True) (justify in commit).
    "class": "class_push",
    "clas": "class_push",
    "bdef": "rap_bdef_creation",
    "behaviordefinition": "rap_bdef_creation",
    "srvd": "rap_service_binding",
    "servicedefinition": "rap_service_binding",
    "doma": None,             # no validator chain defined yet (domain_creation_csv is CSV-batch)
    # ⚠ 2026-08-29 ÖLÇÜLDÜ (kayıt #3, `_reviewer.py:47` "bayat yorum" iddiası):
    #   Yorum bayat SANILDI; ölçüm AKSİNİ söyledi ve mapping DEĞİŞTİRİLMEDİ.
    #   `run_review.TASK_VALIDATORS['dtel_update']` = **0 validator** (AST + canlı koşum:
    #   `--task dtel_update` → verdict PASS, koşan validator sayısı 0). Yani `None` ile
    #   `"dtel_update"` DAVRANIŞ OLARAK AYNI; ortada atlanan bir zincir YOKTUR.
    #   ⛔ Ayrım: "task ANAHTARI var" ≠ "validator TANIMLI" (kapsam niteleyicisi).
    #   Bu satır DTEL **push/update** eksenidir. DTEL **yaratma** ekseni ayrıdır ve
    #   2026-08-29'da doldu → `COMPOSITE_TOOL_TO_TASK["adt_dtel_create"]`e bakınız.
    #   ⇒ `dtel_update` zincirine ilk validator eklendiği gün burası GÜNCELLENMELİDİR.
    "dtel": None,             # dtel_update zinciri BOŞ (ölçüldü) — atlanan bir gate yok
    "msag": None,             # push'u zaten unsupported_type (atom._PUSH_DESTEKSIZ); uygun gate yok
    # aXet 2026-09-14 K1 (kullanıcı kararı "Uyan kontrolleri bağla"): prog/include → program_push,
    # intf → interface_push (zincirler + gerekçe: run_review.TASK_VALIDATORS). Pin: test_verdict_reviewer_k1_d1.
    "prog": "program_push",
    # ── 2026-08-01 adversarial bug-avı (W2-MCPT-03 / MG-02) ────────────────────────
    # SINIF: push katmanı tip EŞANLAMLILARINI kabul ediyor (`_TYPE_KEY_CANON` +
    # `_ACTIVATION_URI_SEG`), bu harita ise yalnız kanonik adları tanıyordu. Eksik
    # anahtar → `.get()` None → pre-flight SESSİZCE atlanır. Ölçüldü: aynı objeye
    # `object_type="ddls"` ile push → BLOCKER + RED; `"cds"`/`"cdsview"`/`"ddl"` ile
    # push → SKIP + GEÇTİ. Aynı asimetri `tabl` ↔ `table`/`structure`'da vardı ve
    # ORADA sonucu daha ağır: `table_update` zinciri `check_table_field_drop`
    # (VERİ-KAYBI BLOCKER'ı) taşır → `"table"` yazımıyla o guard hiç koşmuyordu.
    #
    # ⛔ AYRIM: "eksik anahtar" ≠ "bilinçli None". Eksik = sessiz atlama (bug).
    # Explicit None = kayda geçmiş karar (zincir henüz yok). Bu yüzden aşağıdaki
    # tipler DEĞER olarak yazıldı; hangisi olursa olsun ARTIK BEYAN EDİLMİŞ durumda.
    # Tazeliği `tests/fixtures/reviewer_tip_kapsam` zorlar: push'un kabul ettiği HER
    # tip burada açıkça bulunmalı — yeni tip eklenip burası unutulursa test KIRILIR.
    "cds": "cds_update", "cdsview": "cds_update", "ddl": "cds_update",
    "table": "table_update", "structure": "table_update",
    "interface": "interface_push", "intf": "interface_push",   # K1 (2026-09-14)
    "program": "program_push",                                 # `prog` ile aynı (K1)
    "dcl": None, "accesscontrol": None,       # ACM zinciri yok
    "ddlx": None, "metadataextension": None,  # MDE zinciri yok
    "domain": None, "dataelement": None,      # doma/dtel eşanlamlıları
    "include": "program_push", "prog/i": "program_push",       # klasik include (K1; abaplint ÖLÇÜLEMEDİ=W)
    "incl": "program_push", "report": "program_push",          # object_types eşanlamlıları (K1)
    "srvb": None, "servicebinding": None,     # publish yolu ayrı
    "tabletype": None,
    # 2026-08-29 (kayıt #70): `fugr`/`functiongroup` `_ACTIVATION_URI_SEG`'e eklendi
    # (FUGR aktivasyonu + `also=` atomik co-activate için) ⇒ `reviewer_tip_kapsam`
    # fixture'ı bu iki anahtarı BURADA da beyan edilmiş görmek ister.
    # ⛔ DEĞER `None` — ve bu bir GEVŞETME DEĞİLDİR: `run_review.TASK_VALIDATORS`
    # ölçüldü (AST; aynı gün 14 → **15 görev**: `dtel_creation` eklendi. Tam küme:
    # cds_creation/cds_update, class_push, domain_creation_csv, dtel_creation,
    # dtel_update, itg_s2_signoff, rap_bdef_creation/rap_cds_creation/
    # rap_service_binding, sap_active_check, struct_creation/struct_post_create,
    # table_creation/table_update) → FUGR için tanımlı bir zincir YOK.
    # ⚠ SAYI BURAYA GÖMÜLÜ: TASK_VALIDATORS büyüdüğünde bu satır BAYATLAR — nitekim
    # "14" yazıldığı gün içinde 15 oldu. Otoriter kaynak DAİMA AST'tir, bu yorum değil.
    # Önceden bu anahtarlar HİÇ yoktu ve `.get()` zaten
    # None döndürüyordu; tek değişen, kararın artık AÇIKÇA KAYDA GEÇMESİ.
    # ⇒ FUGR için bir reviewer zinciri tanımlanırsa bu iki satır GÜNCELLENMELİDİR.
    # Kapsam notu (ölçülmüş): `fugr` push'u yalnız FG ANA INCLUDE'unu yazar
    # (`/functions/groups/<fg>/source/main` = `FUNCTION-POOL` satırı); FM gövdesi `func` yoluyla
    # yazılır ⇒ bu anahtarı doldurmak FM gövdesini KAPSAMAZ. `func` da aşağıda `None`: FM
    # yazmadan önce inceleme elle koşulur (`run_review --task class_push --artifact <fm>.abap`).
    # Pin: `tests/test_verdict_reviewer_fugr.py`.
    "fugr": None, "functiongroup": None,
    # ── aXet 2026-09-13: adt_push_source'un YENİ kabul ettiği tipler (beyan zorunlu) ──────────
    # Sınıf alt-include'u (CCIMP/CCAU): ÖLÇÜLDÜ (çevrimdışı, örnek RAP CCIMP'i —
    # `lhc_* DEFINITION INHERITING FROM cl_abap_behavior_handler` + SELECT FROM vbak):
    # `class_push` zincirinin 6 validator'ı da içerikten (`CLASS … DEFINITION`) tanıyıp KOŞTU;
    # verdict WARNING (released_objects gerçek bulgusu), sahte BLOCKER yok ⇒ `class_push`.
    "ccimp": "class_push", "implementations": "class_push",
    "ccau": "class_push", "testclasses": "class_push",
    # FM kaynağı: kaynak çekirdekte FM push zinciri YOK (`abaplint` kapsamı "class/program",
    # FM → SKIP). Uydurma bağlama yapılmadı; SKIP görünür kalır.
    "func": None, "function": None,
    # Kilit objesi: kaynak push'u desteklenmez (araç `unsupported_type` döner) — beyan için.
    "enqu": None,
    "ttyp": None,   # `tabletype` eşanlamlısı (XML-DDIC; zincir yok)
}

# Composite tool name → task for its created object.
#
# ⚠ BU HARİTA `OBJECT_TYPE_TO_TASK` İLE AYNI SINIFTAN ÇÜRÜR: `run_review.TASK_VALIDATORS`
# büyüdüğünde burası kendiliğinden güncellenmez ve YENİ YAZILAN bir gate sessizce
# KABLOSUZ kalır ("kod ≠ kablolama"). Tazeliği `tests/fixtures/reviewer_tip_kapsam`
# zorlar: `None` yazan her satır için o adda bir görev VARSA ve görevin zinciri BOŞ
# DEĞİLSE test KIRILIR.
COMPOSITE_TOOL_TO_TASK = {
    "adt_struct_create": "struct_creation",
    # aXet 2026-09-13 (kullanıcı kararı): eskiden `None` idi — "`domain_creation_csv` CSV-toplu görev,
    # adı eşleşmez" gerekçesiyle açık bırakılmıştı ve domain yaratma HİÇBİR zincir koşturmuyordu.
    # Artık `artifact_path` (domain CSV ya da domain XML) verilirse `domain_creation_csv` koşar
    # (`check_domain_output_length.py`, BLOCKER). Desteklenmeyen uzantı → validator `measured=false`
    # → run_review SKIP'i kendi şiddetiyle sayar ⇒ BLOCKER (fail-closed, görünür).
    # `artifact_path` verilmezse reviewer yine SKIP (`no_artifact_path_provided`); formül ve argüman
    # kuralları artefakt BEKLEMEDEN `tools/composite.py::_domain_on_kontrol` (steps.pre_flight) ile koşar.
    "adt_domain_create": "domain_creation_csv",
    # ⭐ 2026-08-29 (kayıt #3, KOMŞU EKSEN): `None` yorumu "no validators yet" diyordu ve
    # yazıldığı gün DOĞRUYDU. Aynı gün `dtel_creation` görevi + `check_dtel_creation_labels.py`
    # (BLOCKER, ADR 0005-D: 4 label + description doluluk/uzunluk, domain bağı) eklendi ⇒
    # yorum bayatladı ve YENİ YAZILAN GATE bu yüzeyde HİÇ KOŞMUYORDU.
    # BLAST-RADIUS ÖLÇÜLDÜ (canlı, 3 yön):
    #   · `artifact_path=None` (varsayılan; integration_dtel.py böyle çağırır) → `run_reviewer`
    #     zaten "no_artifact_path_provided" ile SKIP döner ⇒ DAVRANIŞ DEĞİŞMEZ.
    #   · `artifact_path=<kirli dataelements.csv>` → verdict BLOCKER (blocker=1) ⇒ push REDDEDİLİR.
    #     Doğru davranış: ADR 0005-D ihlali yazımdan ÖNCE durur.
    #   · `artifact_path=<ilgisiz artefakt (.clas.abap)>` → verdict PASS. Gate tek-dosya
    #     hedefinde repo taramaz (`_aday_dosyalar`: `hedef.is_file()` → [hedef]) ⇒ YANLIŞ-POZİTİF YOK.
    "adt_dtel_create": "dtel_creation",
    # aXet 2026-09-21 (Z38): `adt_table_create` bu görevi artefakt BEKLEMEDEN, yazılacak DDL üzerinde HER çağrıda
    # koşar (`run_reviewer_tablo`); bu satır görev beyanıdır (reviewer_tip_kapsam tazelik denetimi okur).
    "adt_table_create": "table_creation",
}


class ReviewerResult:
    """Structured result from run_review.py invocation."""

    __slots__ = ("verdict", "blocker_count", "warning_count", "results",
                 "skipped", "skip_reason", "raw")

    def __init__(
        self,
        verdict: str,
        blocker_count: int = 0,
        warning_count: int = 0,
        results: Optional[list] = None,
        skipped: bool = False,
        skip_reason: str = "",
        raw: Optional[dict] = None,
    ):
        self.verdict = verdict  # PASS | WARNING | BLOCKER | SKIP
        self.blocker_count = blocker_count
        self.warning_count = warning_count
        self.results = results or []
        self.skipped = skipped
        self.skip_reason = skip_reason
        self.raw = raw or {}

    @property
    def passed(self) -> bool:
        return self.verdict in ("PASS", "SKIP")

    @property
    def is_blocker(self) -> bool:
        return self.verdict == "BLOCKER"

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "blocker_count": self.blocker_count,
            "warning_count": self.warning_count,
            "results": self.results,
            "skipped": self.skipped,
            "skip_reason": self.skip_reason,
        }


def run_reviewer(task: Optional[str], artifact_path: Optional[str],
                 ack_drop: str = "") -> ReviewerResult:
    """Invoke scripts/validators/run_review.py and parse its JSON output.

    Args:
        task: reviewer task type (e.g., 'struct_creation', 'cds_update').
              None → skip (no task mapped yet for this tool/type).
        artifact_path: path to the local file to review. Must exist on disk.
                       None → skip (coordinator did not provide an artifact).
        ack_drop: comma-separated field names whose table DROP is explicitly
                  approved (user+lead, ADR 0005-B). Forwarded to run_review's
                  --ack-drop → ONLY these named drops become ACK-WARNING; any
                  un-named drop or any TYPE/RENAME change still BLOCKER. Empty
                  → no acknowledgement (default; full drop-guard).

    Returns:
        ReviewerResult — coordinator-friendly verdict + details.
        verdict='SKIP' when task or artifact missing (gracefully proceed).
    """
    if not task:
        return ReviewerResult(verdict="SKIP", skipped=True,
                              skip_reason="no_reviewer_task_for_this_operation")
    if not artifact_path:
        return ReviewerResult(verdict="SKIP", skipped=True,
                              skip_reason="no_artifact_path_provided")

    artifact = Path(artifact_path)
    if not artifact.is_absolute():
        # aXet: göreli artefakt yolu PROJE köküne göredir (kaynak çekirdekte repo kökü).
        artifact = project_dir() / artifact_path
    if not artifact.exists():
        return ReviewerResult(verdict="SKIP", skipped=True,
                              skip_reason=f"artifact_not_found:{artifact}")

    if not _REVIEW_SCRIPT.exists():
        log.error("run_review.py not found at %s", _REVIEW_SCRIPT)
        return ReviewerResult(verdict="SKIP", skipped=True,
                              skip_reason="run_review_script_missing")

    cmd = [
        sys.executable,
        str(_REVIEW_SCRIPT),
        "--task", task,
        "--artifact", str(artifact),
        "--json",
    ]
    if ack_drop:
        # Hedefli onaylı-DROP ack — yalnız drop-guard'a iletilir (run_review içinde
        # check_table_field_drop'a geçer). Blanket bypass DEĞİL: isimsiz drop/tip
        # değişikliği yine BLOCKER. ADR 0005-B kullanıcı+lider bilinçli onayı.
        cmd += ["--ack-drop", ack_drop]
    env = os.environ.copy()
    env[PROJECT_ENV] = str(project_dir())
    # K10 ②: bütçe TEK KAYNAKTAN gelir ve alt katmanlara AÇIKÇA taşınır. Alt süreç env'i miras
    # alsa bile değeri burada yeniden yazıyoruz: kullanıcı env'i koymadıysa L2/L3 varsayılanı
    # `butce` modülünden hesaplar — yani üç katman DAİMA aynı sayıya bakar (kayma imkânsız).
    butce_sn = butce.reviewer_butce_sn()
    env[butce.REVIEWER_ENV] = f"{butce_sn:g}"
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(project_dir()),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            # stdin=DEVNULL ZORUNLU: MCP server type=stdio → JSON-RPC'yi stdin/stdout
            # pipe'tan konuşur. Bunu vermezsek çocuk subprocess parent'ın stdin pipe
            # handle'ını miras alır ve Windows'ta bloke olur → her çağrı 120s donardı
            # (standalone 0.6s; bug spawn'da, script'te değil). Bkz. _reviewer-stdio-deadlock.
            stdin=subprocess.DEVNULL,
            timeout=butce_sn,
        )
    except subprocess.TimeoutExpired:
        if zaman_asimi_blocker_mi(task):
            # K10: zincir CANLI bir gate'i BLOCKER olarak taşıyor → sonuç üretilmeden yazmak,
            # checklist BLOCKER'ını yavaş/erişilemez SAP'de sessizce düşürür. İhlal bulunmadı; ÖLÇÜLEMEDİ.
            gateler = zaman_asimi_blocker_gateleri(task) or ["(konumu çözülemeyen gate)"]
            log.warning("Reviewer timeout for task=%s artifact=%s — BLOCKER (ÖLÇÜLEMEDİ; canlı BLOCKER gate)",
                        task, artifact)
            return ReviewerResult(
                verdict="BLOCKER", blocker_count=1,
                skip_reason=(f"reviewer_timeout — zaman aşımı → BLOCKER (ÖLÇÜLEMEDİ): reviewer "
                             f"{butce_sn:g} sn'lik süre bütçesini aştı; zincir canlı (SAP'ye bağlanan) "
                             f"BLOCKER gate taşıyor: {', '.join(gateler)}. İhlal bulunduğu anlamına GELMEZ, "
                             "PASS da sayılmaz — bir kontrol koşmadıysa sonucu 'temiz' değil NOT MEASURED'dır. "
                             + butce.nasil_uzatilir() + " Ya da SAP erişimini/yavaşlığını düzeltip tekrar dene. "
                             "Manuel: " + _MANUEL.replace("<X>", str(task))))
        # Timeout ≠ ihlal. Eskiden BLOCKER (0/0) döndürüp meşru push'u bloklıyordu
        # (2026-06-10 reviewer-kör vakası). Zincirde CANLI BLOCKER gate YOKSA (yani ağ yüzünden
        # düşen bir BLOCKER kontrolü yok) non-blocking WARNING: push geçer ama coordinator manuel
        # run_review.py çalıştırmalı (asıl gate zaten manuel).
        log.warning("Reviewer timeout for task=%s artifact=%s — WARNING (manuel review öner)",
                    task, artifact)
        return ReviewerResult(
            verdict="WARNING", skipped=False, warning_count=1,
            skip_reason=(f"reviewer_timeout — reviewer {butce_sn:g} sn'lik süre bütçesini aştı; zincirde "
                         "canlı BLOCKER gate YOK, push bloke EDİLMEDİ. Yine de bu zincir ÖLÇÜLEMEDİ. "
                         + butce.nasil_uzatilir() + " Manuel doğrula: " + _MANUEL.replace("<X>", str(task))))
    except Exception as exc:
        log.warning("Reviewer subprocess error: %s", exc)
        return ReviewerResult(verdict="SKIP", skipped=True,
                              skip_reason=f"reviewer_exception:{exc}")

    # Parse JSON from stdout. run_review.py with --json emits structured payload.
    raw: dict = {}
    try:
        raw = json.loads(proc.stdout)
    except json.JSONDecodeError:
        # Best-effort: pick last JSON object in output
        try:
            tail = proc.stdout.rfind("{")
            if tail >= 0:
                raw = json.loads(proc.stdout[tail:])
        except Exception:
            raw = {}

    verdict = raw.get("verdict", "BLOCKER" if proc.returncode == 1 else "SKIP")
    # ⚠ VERDICT SEMANTIĞI DEĞİŞMEZ (karar A, 2026-09-20) — burada YALNIZ TEŞHİS eklenir.
    # rc ∉ (0, 1) + ayrıştırılabilir JSON yok ⇒ verdict SKIP olur ve `passed` True döner
    # (`passed` = PASS ∪ SKIP), yani pre-flight KOŞMADAN SAP yazımı sürer. Bugüne kadar bunun
    # NEDENİ hiçbir yere yazılmıyordu: `skip_reason` varsayılanı "" olduğu için kullanıcıya
    # giden not "PRE-FLIGHT KOŞMADI ()" diye BOŞ çıkıyordu (`on_kontrol_ozeti`).
    # Fail-closed'a çevirmek AYRI bir karardır (madde 1b): önce bu teşhisle rc uzayı ölçülecek.
    turetilmis = "verdict" not in raw
    skip_reason = str(raw.get("skip_reason", "") or "")
    if verdict == "SKIP" and turetilmis:
        kuyruk = " ".join((proc.stderr or "").split())[-300:]
        skip_reason = (f"reviewer rc={proc.returncode}, JSON ayrıştırılamadı"
                       + (f" | stderr: {kuyruk}" if kuyruk else " | stderr BOŞ"))
    return ReviewerResult(
        verdict=verdict,
        blocker_count=int(raw.get("blocker_count", 0)),
        warning_count=int(raw.get("warning_count", 0)),
        results=raw.get("results", []),
        skipped=(verdict == "SKIP"),
        skip_reason=skip_reason,
        raw=raw,
    )


_CDS_YORUM = re.compile(r"/\*.*?\*/|//[^\n]*", re.S)
# RAP view entity / projection imzaları (kaynak çekirdekte `rap_cds_creation` zincirinin kapsamı:
# "RAP view entity de DDLS — klasik CDS validator zinciri + view-entity kuralları").
_RAP_CDS = re.compile(r"\bdefine\s+(?:root\s+)?view\s+entity\b|\bas\s+projection\s+on\b", re.I)


def rap_cds_mi(source: Optional[str]) -> bool:
    """Kaynak (yorumlar atılarak) `define [root] view entity` ya da `as projection on` içeriyor mu?"""
    if not isinstance(source, str):
        return False
    return bool(_RAP_CDS.search(_CDS_YORUM.sub(" ", source)))


def task_for_push(object_type: str, source: Optional[str] = None) -> Optional[str]:
    """Resolve reviewer task for adt_push_source by object type (+ CDS içeriği).

    aXet (2026-09-13): DDLS push'u kaynağına göre ayrılır — view entity / projection →
    `rap_cds_creation` (klasik CDS kontrolleri + RAP read-only consumption + reuse), klasik
    `define view` → `cds_update`. Önceden RAP view entity'ler `cds_update`'e düşüyor ve RAP
    zinciri hiç koşmuyordu.
    """
    task = OBJECT_TYPE_TO_TASK.get((object_type or "").lower())
    if task == "cds_update" and rap_cds_mi(source):
        return "rap_cds_creation"
    return task


def task_for_composite(tool_name: str) -> Optional[str]:
    """Resolve reviewer task for a composite tool by its name."""
    return COMPOSITE_TOOL_TO_TASK.get(tool_name)


# ── POST-CHECK HÜKMÜ — TEK KAYNAK (Q273 atom.py'de doğdu · Q293 2026-09-13 buraya taşındı) ──
# ÖLÇÜLEN KUSUR (Q273, `adt_push_source`): başarılı push'ta WARNING kapısı ÖLÇÜM ÜRETEMEYİNCE
# (`measured=false` → run_review WARNING) `ReviewerResult.passed` False → `ok:false` (sahte-FAIL).
# AYNI SINIF (Q293, `adt_struct_create`): `consistency_ok = consistency.passed` İKİ YÖNDE ayrışıyordu:
#   · WARNING (reviewer_timeout / measured=false) → `ok:false` (sahte-FAIL, re-create/yanlış teşhis)
#   · SKIP (artifact_not_found / reviewer_exception / script_missing) → `ok:true` + `post_check.ok:true`
#     ⇒ post-check HİÇ KOŞMADI ama yanıt "temiz" görünüyordu (ölçülemedi = geçti).
# ⭐ `passed` = verdict ∈ {PASS, SKIP} (yukarıda). run_review.py JSON'da yalnız BLOCKER/WARNING/PASS
#   üretir (`run_review.py:471-478`) ⇒ SKIP verdict'i DAİMA bu sarmalayıcıdan gelir = zincir KOŞMADI.
# KARAR (ADR 0006: WARNING = "yazabilir ama raporda belirt"):
#   • işlemin `ok`'u YALNIZ verdict BLOCKER, TANINMAYAN verdict ya da blocker_count>0 iken düşer.
#   • ölçülemeyen kapı SESSİZ KALMAZ: `unmeasured` (+ sebep), ölçülmüş uyarı `warnings`,
#     açık üç-durumlu hüküm `hukum` ∈ {gecti, uyari, olculemedi, kaldi}; çağıran üst düzeye notice koyar.
#   • `ok` iç alanı ESKİ anlamını korur (= `passed` ve blocker_count==0); etkisi `ok_etkisi`nde.
# ⛔ `ReviewerResult.passed` DEĞİŞMEDİ (pre-flight tüketicileri SKIP'i "geç" sayar — doğru).
POST_CHECK_OK_DUSURMEYEN = ("PASS", "SKIP", "WARNING")


def post_check_ozeti(post) -> tuple[dict, bool]:
    """Post-check sonucunu yanıt alanına çevir + işlemin `ok`'unu düşürmeli mi söyle.

    Returns: (post_check_dict, ok_dusur)
    """
    verdict = str(getattr(post, "verdict", "") or "")
    blocker_count = int(getattr(post, "blocker_count", 0) or 0)
    warning_count = int(getattr(post, "warning_count", 0) or 0)
    dusur = verdict not in POST_CHECK_OK_DUSURMEYEN or blocker_count > 0
    ozet: dict = {
        "ok": verdict in ("PASS", "SKIP") and blocker_count == 0,
        "verdict": verdict,
        "blocker_count": blocker_count,
        "warning_count": warning_count,
        "ok_etkisi": "dusurdu" if dusur else "yok",
    }
    skip_reason = getattr(post, "skip_reason", "") or ""
    if skip_reason:
        ozet["skip_reason"] = skip_reason

    unmeasured, warnings = [], []
    for r in (getattr(post, "results", None) or []):
        if not isinstance(r, dict):
            continue
        kayit = {"gate": r.get("validator"), "severity": r.get("severity")}
        if r.get("status") == "SKIP":
            kayit["reason"] = str(r.get("message") or "")[:240]
            unmeasured.append(kayit)
        elif r.get("status") == "FAIL" and r.get("severity") != "BLOCKER":
            warnings.append(kayit)
    if not unmeasured and not warnings:
        if verdict == "WARNING" and skip_reason:
            # reviewer_timeout gibi: zincir sonuç ÜRETMEDİ ama WARNING döndü ⇒ ölçülemedi.
            unmeasured.append({"gate": "reviewer", "severity": "WARNING",
                               "reason": skip_reason[:240]})
        elif verdict == "SKIP":
            # Q293: SKIP = zincir hiç koşmadı (sebep: skip_reason) ⇒ "temiz" DEĞİL, ölçülemedi.
            unmeasured.append({"gate": "reviewer", "severity": "SKIP",
                               "reason": (skip_reason or "reviewer sonuç üretmedi")[:240]})
    if unmeasured:
        ozet["unmeasured"] = unmeasured
    if warnings:
        ozet["warnings"] = warnings
    if dusur:
        ozet["hukum"] = "kaldi"
    elif unmeasured:
        ozet["hukum"] = "olculemedi"
    elif warnings or verdict == "WARNING":
        ozet["hukum"] = "uyari"
    else:
        ozet["hukum"] = "gecti"
    return ozet, dusur


def post_check_notice(ozet: dict, islem: str = "push") -> str:
    """WARNING/ölçülemeyen kapının görünür izi — `ok` düşmediğinde yanıtın ÜST düzeyinde durur."""
    parcalar = []
    for k in ozet.get("unmeasured") or []:
        parcalar.append("ÖLÇÜLEMEDİ %s (%s)" % (k.get("gate"), (k.get("reason") or "-")[:120]))
    for k in ozet.get("warnings") or []:
        parcalar.append("UYARI %s" % k.get("gate"))
    return ("POST-CHECK %s — %s BAŞARILI, `ok` DÜŞÜRÜLMEDİ (yalnız BLOCKER düşürür, Q273). "
            "Bu 'post-check temiz' DEĞİLDİR: %s. Kritik objede elle teyit et."
            % (ozet.get("verdict"), islem, "; ".join(parcalar) or "ayrıntı yok"))


# ── ÖN KONTROL GÖRÜNÜRLÜĞÜ — ölçülemeyen gate PASS görünmez (aXet 2026-09-14, K1/D1) ──────────────
# ÖLÇÜLEN KUSUR: `run_review` ölçüm üretmeyen gate'i (dosya yok / `measured=false`) SKIP olarak
# önemiyle verdict'e sayıyordu ama araç yanıtı yalnız `verdict`'i taşıyordu: include push'unda
# abaplint ölçülemediğinde yanıt "WARNING" diyordu ve nedeni (ÖLÇÜLEMEDİ) yalnız `results[]`
# derinliğindeydi; BLOCKER reddinde ise "1 blocker" ihlal bulunmuş gibi okunuyordu.
# KARAR: hüküm DEĞİŞMEZ; ölçülemeyen gate'ler `unmeasured` + `notice`/`message` ile üst düzeye çıkar.


def olculemeyenler(result) -> list:
    """Zincirde ölçüm üretmeyen gate'ler (status SKIP) — `[{gate, severity, reason}]`."""
    out = []
    for r in (getattr(result, "results", None) or []):
        if isinstance(r, dict) and r.get("status") == "SKIP":
            # Gate kendi ÖLÇÜLEMEDİ satırını bastıysa (ör. "süre bütçesi (15 sn) doldu, 3 aday denetlenmedi")
            # sebep o satırdır; yoksa run_review mesajı.
            ayrinti = next((s.strip() for s in str(r.get("stderr") or "").splitlines() if "ÖLÇÜLEMEDİ" in s), "")
            out.append({"gate": r.get("validator"), "severity": r.get("severity"),
                        "reason": (ayrinti or str(r.get("message") or ""))[:240]})
    if (not out and getattr(result, "verdict", "") in ("WARNING", "BLOCKER") and getattr(result, "skip_reason", "")
            and not getattr(result, "results", None)):
        # reviewer_timeout (WARNING ya da DTEL gate'li zincirde BLOCKER) / artefakt bulunamadı:
        # zincir sonuç üretmedi ⇒ ölçülemedi.
        out.append({"gate": "reviewer", "severity": result.verdict, "reason": str(result.skip_reason)[:240]})
    return out


def _olculemedi_metni(olc: list) -> str:
    return ", ".join(f"{k.get('gate')} ({k.get('severity')})" for k in olc)


def on_kontrol_ozeti(result: ReviewerResult, skip_notice: Optional[str] = None) -> dict:
    """Pre-flight sonucunun yanıt sözlüğü: SKIP → KOŞMADI notu · ölçülemeyen gate → `unmeasured` + ÖLÇÜLEMEDİ notu."""
    out = result.to_dict()
    if result.verdict == "SKIP":
        out["notice"] = skip_notice or f"PRE-FLIGHT KOŞMADI ({result.skip_reason}) — 'reviewer PASS' SANMA."
        return out
    olc = olculemeyenler(result)
    if olc:
        out["unmeasured"] = olc
        out["notice"] = (f"PRE-FLIGHT ÖLÇÜLEMEDİ: {_olculemedi_metni(olc)} — bu gate'ler ölçüm üretmedi; "
                         "sonuç 'temiz' DEĞİL, önemleriyle verdict'e sayıldı.")
    return out


# ── D1 (aXet 2026-09-14, kullanıcı kararı "Dosyasız çağrıda da koşsun") ───────────────────────────
# Tarihçe: D1'den önce `adt_struct_create`'in dosyasız çağrısı `COMPOSITE_TOOL_TO_TASK` yolunda SKIP
# (no_artifact_path_provided) alıyor ve yapı DTEL'i kontrol edilmeden yazılıyordu. Bug gate 2026-09-14 (B2): artefaktlı
# çağrıda bu görev KOŞMUYORDU ve olmayan artefakt yolu SKIP (= geçti) idi.
# Bugün: SAP'ye fiilen yazılan yük `fields[]`'ten kurulan DDL'dir ⇒ `run_reviewer_struct` bu görevi HER çağrıda koşar
# (artefakt verilsin verilmesin); artefakt verilirse `struct_creation` ayrıca koşar ve sonuçlar birleşir.
# Re-gate 2026-09-15: denetlenen DDL = yazılan DDL — ikisi de `utils.ddic_dtel.yapi_ddl_kaynagi` (tek render; alan
# açıklaması `// …` satırları ve yapı etiketi dahil). Önceden gate'in DDL'i açıklamaları almıyordu.
STRUCT_ALANLAR_GOREVI = "struct_fields_dtel"


def run_reviewer_struct_alanlari(name: str, fields, description: str = "") -> ReviewerResult:
    """`adt_struct_create` her çağrıda: SAP'ye yazılacak DDL (`yapi_ddl_kaynagi` — `sap_adt_lib.create_structure`'ın aynı
    render'ı, açıklama satırları dahil) üzerinde `struct_fields_dtel` zinciri. Render yüklenemez/hata verirse BLOCKER."""
    try:
        from utils.ddic_dtel import yapi_ddl_kaynagi  # type: ignore
    except Exception as exc:  # noqa: BLE001 — çıkarım yüklenemezse GEÇMEZ (fail-closed)
        return ReviewerResult(verdict="BLOCKER", blocker_count=1,
                              skip_reason=f"dtel_cikarimi_yuklenemedi:{type(exc).__name__}")
    try:
        metin = yapi_ddl_kaynagi(name, fields, description)
    except Exception as exc:  # noqa: BLE001 — yazılacak DDL kurulamıyorsa denetlenemez → GEÇMEZ (fail-closed)
        return ReviewerResult(verdict="BLOCKER", blocker_count=1, skip_reason=f"ddl_render_hatasi:{type(exc).__name__}")
    fd, yol = tempfile.mkstemp(prefix="axet_struct_alanlar_", suffix=".ddls.asddls")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(metin)
        return run_reviewer(STRUCT_ALANLAR_GOREVI, yol)
    finally:
        try:
            os.unlink(yol)
        except OSError:
            pass


TABLO_GOREVI = "table_creation"


def run_reviewer_tablo(ddl: str) -> ReviewerResult:
    """`adt_table_create` her çağrıda (aXet 2026-09-21, Z38): SAP'ye PUT edilecek DDL'in KENDİSİ (`utils.ddic_tablo.
    tablo_ddl_kaynagi`) `table_creation` zincirinden geçer (Z/Y + /ns/ DTEL var/aktif · CURR/QUAN nitelikli referans ·
    eskimiş annotation). Denetlenen metin = yazılan metin; ayrı bir "gate DDL'i" yok. Dosya yazılamazsa BLOCKER."""
    try:
        fd, yol = tempfile.mkstemp(prefix="axet_tablo_", suffix=".tabl.asddls")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(ddl)
    except Exception as exc:  # noqa: BLE001 — denetlenemiyorsa GEÇMEZ (fail-closed)
        return ReviewerResult(verdict="BLOCKER", blocker_count=1, skip_reason=f"ddl_dosyasi_yazilamadi:{type(exc).__name__}")
    try:
        return run_reviewer(TABLO_GOREVI, yol)
    finally:
        try:
            os.unlink(yol)
        except OSError:
            pass


_VERDICT_SIRASI = {"PASS": 0, "SKIP": 1, "WARNING": 2, "BLOCKER": 3}


def _birlestir(parcalar: list) -> ReviewerResult:
    """[(girdi, ReviewerResult)] → tek hüküm. En ağır verdict kazanır (BLOCKER > WARNING > SKIP > PASS; SKIP PASS'in
    önündedir ki "bir zincir koşmadı" görünür kalsın). Her sonuç kaydına `girdi` (fields | artifact) eklenir;
    sonuç üretmeyen sarmalayıcı hükmü (ör. artifact_not_found) `validator="reviewer"` SKIP kaydı olarak girer."""
    # Re-gate 2026-09-15 (ÖNERİ): tanınmayan verdict BLOCKER SIRASI alıyor ama metni aynen dönüyordu (`X` + `BLOCKER` → `X`,
    # `is_blocker` False) → önce "BLOCKER"a normalize edilir (fail-closed), sonra en ağırı seçilir.
    verdict = max((r.verdict if r.verdict in _VERDICT_SIRASI else "BLOCKER" for _g, r in parcalar),
                  key=_VERDICT_SIRASI.__getitem__)
    results = []
    for girdi, r in parcalar:
        if r.results:
            results.extend({**x, "girdi": girdi} for x in r.results if isinstance(x, dict))
        elif r.skip_reason:
            results.append({"validator": "reviewer", "severity": r.verdict, "status": "SKIP", "description": "",
                            "stdout": "", "stderr": "", "message": r.skip_reason, "girdi": girdi})
    return ReviewerResult(
        verdict=verdict,
        blocker_count=sum(r.blocker_count for _g, r in parcalar),
        warning_count=sum(r.warning_count for _g, r in parcalar),
        results=results,
        skipped=all(r.skipped for _g, r in parcalar),
        skip_reason="; ".join(f"{g}: {r.skip_reason}" for g, r in parcalar if r.skip_reason),
    )


def run_reviewer_struct(name: str, fields, artifact_path: Optional[str] = None, description: str = "") -> ReviewerResult:
    """`adt_struct_create` ön kontrolü (B2). Sıra: artefakt yolu verildiyse VAR mı (yerel, ağsız; yoksa BLOCKER) →
    `fields[]` DTEL denetimi (yazılan yük; DAİMA) → BLOCKER değilse artefaktın `struct_creation` zinciri → birleşik hüküm."""
    if artifact_path:
        yol = Path(artifact_path)
        if not yol.is_absolute():
            yol = project_dir() / artifact_path
        if not yol.exists():
            return ReviewerResult(
                verdict="BLOCKER", blocker_count=1,
                skip_reason=(f"artifact_not_found:{yol} — adt_struct_create'te verilen artefakt yolu bulunamazsa "
                             "BLOCKER (yol düzeltilmeli ya da artifact_path verilmemeli; SKIP = geçti sayılmaz)"))
    alan = run_reviewer_struct_alanlari(name, fields, description)
    if not artifact_path:
        return alan
    if alan.is_blocker:
        return _birlestir([("fields", alan)])
    return _birlestir([("fields", alan), ("artifact", run_reviewer(task_for_composite("adt_struct_create"),
                                                                    artifact_path))])


def reject_payload(name: str, object_type: str, result: ReviewerResult) -> dict:
    """Build the MCP error payload when reviewer returns BLOCKER."""
    olc = olculemeyenler(result)
    mesaj = (f"Reviewer pre-flight (ADR 0006) BLOCKER verdict: "
             f"{result.blocker_count} blocker, {result.warning_count} warning. ")
    if olc:
        mesaj += (f"ÖLÇÜLEMEDİ: {_olculemedi_metni(olc)} — ölçüm üretmeyen BLOCKER gate yazmayı durdurur "
                  "(ihlal bulunduğu anlamına gelmez; PASS da sayılmaz — sebebi/bağlantıyı düzeltip tekrar dene). ")
        ayrinti = " | ".join(str(k.get("reason"))[:200] for k in olc if k.get("reason"))
        if ayrinti:
            mesaj += f"Ayrıntı: {ayrinti}. "
    mesaj += f"Düzelt ve tekrar dene. Manuel: {_MANUEL}"
    rv = result.to_dict()
    payload = {
        "ok": False,
        "error": "reviewer_blocker",
        "message": mesaj,
        "name": name,
        "type": object_type,
        "reviewer": rv,
    }
    if olc:
        rv["unmeasured"] = olc
        payload["unmeasured"] = olc
    return payload
