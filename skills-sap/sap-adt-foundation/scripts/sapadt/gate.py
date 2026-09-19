# -*- coding: utf-8 -*-
"""SAP YAZMA KAPISI — içe aktarılabilir TEK uygulama.

`sap_adt_cli.py` bunu çağırır; toplu/push script'leri de AYNI fonksiyondan geçmelidir
(ikinci bir kapı kopyası YAZILMAZ). Kural ve statik kontrol: IMPLEMENTATION.md.

Kullanım (script'ten):
    from sapadt import gate
    sonuc = gate.check_write("adt_push_source", proje, obje_adi="ZCL_X", object_type="class",
                             scope="S1", reason="Hata düzeltmesi: ...", sap_write_flag=True)
    if not sonuc.allowed:
        gate.log_write_attempt(proje, tool=..., obje_adi=..., scope=..., reason=..., intake=...,
                               result_code=sonuc.code)
        raise SystemExit(2)
    ... yazma işlemi ...
    gate.log_write_attempt(proje, ..., result_code="ok" | <hata kodu>)

KAPI SIRASI (her red ayrı kod; ilk red döner):
  0. sap_project_missing / sap_project_invalid     — sap-project.json (fail-closed)
  1. write_not_optin_global                        — <AXET_HOME>/config/sap-write.local yok
  2. write_flag_missing                            — --sap-write verilmedi
  3. tier_not_writable                             — .conn_adt tier ≠ DEV (fail-closed; env SAYILMAZ)
     conn_env_mismatch                             — ortam değişkeni .conn_adt'deki URL/client'ı eziyor
  4. scope_missing | scope_invalid | reason_missing | intake_missing | intake_invalid
  5. araç guard'ları (ağdan ÖNCE):
       ADR_0005_A (Z/Y namespace; silmede standart obje reddi) ·
       ADR_0005_B (kaynakta standart tabloya doğrudan DML; `check_std_dml`, kaynak `tool_args`'tan —
                   kaynak yok/taranamadı → std_dml_scan_unavailable) · ADR_0005_C (transport) ·
       language_mismatch (bağlantı dili ≠ master_language) · reviewer_bypass_forbidden
  6. write_log_unavailable                          — deneme logu yazılamıyor (iz bırakmadan yazma YOK)
  (Reviewer ön kontrolü araç fonksiyonunun içinde koşar: `adt_push_source` + composite'ler;
   BLOCKER → `reviewer_blocker`. Script'ler için `review_preflight()`.)
"""
from __future__ import annotations

import datetime as _dt
import importlib.util
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from sapadt import PKG_DIR
from sapadt import project as _project
from sapadt import redact as _redact
from sapadt._conn import get_active_tier
from sapadt.guardrails import (
    TMP_MUAF_ARACLAR,
    GuardrailViolation,
    reject_standard_delete,
    require_customer_namespace,
    require_transport,
)

# sapadt → scripts → sap-adt-foundation → skills-sap → AXET_HOME
AXET_HOME = PKG_DIR.parents[3]
WRITE_OPTIN_REL = Path("config") / "sap-write.local"
INTAKE_REL = Path(".axet-code") / "intake"
LOG_REL = Path(".axet-code") / "sap-write-log.jsonl"
INTAKE_CHECKER_REL = Path("skills-sap") / "sap-intake-triage" / "scripts" / "check_intake_signoff.py"

# ── SINIFLANDIRMA — salt-okur ALLOWLIST (bu küme dışındaki HER araç yazma kapısından geçer) ──
READ_TOOLS = frozenset({
    "ping",
    "adt_get", "adt_msgclass_read", "adt_search_objects", "adt_transport_list",
    "adt_where_used", "adt_atc_check", "adt_package_contents", "adt_table_read",
    "adt_sql_query", "adt_dump_list", "adt_inactive_objects", "adt_enhancements",
    "adt_enhancement_read", "adt_enhancement_options", "adt_feature_probe",
    "adt_grep_source", "adt_impact_analysis", "adt_lock_check", "adt_unit_run",
    # aXet 2026-09-13 (tools/diag.py): sürüm geçmişi · sistem servis kataloğu · obje yapısı · bağlantı tanısı
    "adt_revisions", "adt_system_info", "adt_object_structure", "sap_doctor",
})
# Okuma kapısını (`check_read`) ve profil kontrolünü CLI'de ATLAYAN araçlar. `ping` SAP'ye gitmez;
# `sap_doctor` sap-project.json/.conn_adt eksikliğini TEŞHİS etmek için var — aynı ön koşulları
# (`load_sap_project` + `check_connection`) KENDİSİ denetler ve biri FAIL ise canlı katmana GİTMEZ
# (tools/diag.py `engel` listesi; test: test_diag_tools.py). Okuma kapısından gevşek değildir.
PRECHECK_EXEMPT_TOOLS = frozenset({"ping", "sap_doctor"})
# Argümana bağlı yazma: değer TRUTHY ise yazma (araç `if allow_risky_tests:` ile okur —
# "false" dizesi bile truthy'dir ve riskli bandı açar; sınıflandırma araçla AYNI kuralı kullanır).
CONDITIONAL_WRITE = {
    "adt_unit_run": ("allow_risky_tests",
                     "allow_risky_tests truthy ise yazma sınıfı (dangerous/critical testler kalıcı veri değiştirebilir)"),
}
REQUIRES_TRANSPORT = frozenset({"adt_post_shell", "adt_domain_create", "adt_dtel_create",
                                "adt_struct_create", "adt_msgclass_write", "adt_set_description"})
DELETE_TOOLS = frozenset({"adt_delete"})
SCOPES = ("S0", "S1", "S2")
REASON_MIN_LEN = 15


def tool_class(tool: str, args: dict | None = None) -> str:
    if tool in CONDITIONAL_WRITE:
        return "write" if (args or {}).get(CONDITIONAL_WRITE[tool][0]) else "read"
    return "read" if tool in READ_TOOLS else "write"


@dataclass
class GateResult:
    allowed: bool
    code: str | None = None
    message: str | None = None
    project_dir: str = ""
    tier: str = "UNKNOWN"
    sap_write_optin: bool = False
    scope: str | None = None
    reason: str | None = None
    intake: str | None = None
    review: str | None = None
    details: dict = field(default_factory=dict)

    def gate_dict(self) -> dict:
        return {"project_dir": self.project_dir, "tier": self.tier,
                "sap_write_optin": self.sap_write_optin, "scope": self.scope,
                "reason": self.reason, "intake": self.intake, "review": self.review}


# ── yardımcı denetimler (her biri tek başına da çağrılabilir) ─────────────────────────────

def optin_file(axet_home: str | os.PathLike | None = None) -> Path:
    return Path(axet_home or AXET_HOME) / WRITE_OPTIN_REL


def check_project(proj) -> tuple[dict | None, tuple[str, str] | None]:
    """(cfg, (kod, mesaj)|None)."""
    cfg, hata = _project.load_sap_project(proj)
    if cfg:
        return cfg, None
    kod = "sap_project_missing" if "yok" in (hata or "") else "sap_project_invalid"
    return None, (kod, f"{_project.SAP_PROJECT_FILE} yok/geçersiz — {hata}. Yalnız --list ve ping çalışır.")


def _norm_url(u: str | None) -> str:
    u = (u or "").strip()
    if not u:
        return ""
    p = urlparse(u if "://" in u else "https://" + u)
    return f"{(p.scheme or '').lower()}://{(p.hostname or '').lower()}:{p.port or ''}{(p.path or '').rstrip('/')}"


def check_connection(proj) -> tuple[str, str] | None:
    """Ortam değişkeni `.conn_adt`'deki sistem kimliğini eziyor mu?

    ÖLÇÜLDÜ: istemci `.conn_adt`'yi `load_dotenv(override=False)` ile yükler ⇒ ortamda
    `ADT_SAP_URL`/`ADT_SAP_CLIENT` varsa bağlantı ONA gider, tier ise dosyadan okunur.
    İkisi ayrışırsa "DEV" diye doğrulanan kapı başka bir sisteme yazdırır → red.
    """
    ayrisan = []
    for key, norm in (("ADT_SAP_URL", _norm_url), ("ADT_SAP_CLIENT", lambda s: (s or "").strip())):
        if key not in os.environ:
            continue
        dosya = _project.conn_file_last(key, proj)
        if norm(os.environ.get(key)) != norm(dosya):
            ayrisan.append(key)
    if ayrisan:
        return ("conn_env_mismatch",
                f"Ortam değişkeni .conn_adt'yi eziyor: {', '.join(ayrisan)} (değerler basılmadı). "
                "Bağlantı ortamdaki sisteme giderdi, tier ise .conn_adt'den okunuyor. "
                "Bu değişkenleri ortamdan kaldır; sistem yalnız proje kökündeki .conn_adt'den seçilir.")
    return None


def check_language(proj, cfg: dict) -> tuple[str, str] | None:
    """Yazma çağrısında bağlantı dili == sap-project.json master_language (sessiz eşitleme YOK)."""
    master = (cfg or {}).get("master_language")
    baglanti = (_project.effective_conn_value("ADT_SAP_LANGUAGE", "EN", proj) or "").strip().upper()
    if not master or baglanti != master.upper():
        return ("language_mismatch",
                f"Bağlantı dili ({baglanti or 'boş'}; .conn_adt/ortam ADT_SAP_LANGUAGE, varsayılan EN) "
                f"≠ sap-project.json master_language ({master}). Z obje yaratan/yazan çağrılar "
                "master_language ile oturum açmalı; dil sessizce eşitlenmez. .conn_adt'yi düzelt.")
    return None


def check_scope(proj, scope, reason, intake, axet_home=None) -> tuple[tuple[str, str] | None, dict]:
    """Kapsam beyanı. Döner ((kod, mesaj)|None, ayrıntı)."""
    ayrinti: dict = {}
    if scope is None or str(scope).strip() == "":
        return ("scope_missing", "Yazma çağrısı --scope S0|S1|S2 beyanı ister."), ayrinti
    s = str(scope).strip().upper()
    if s not in SCOPES:
        return ("scope_invalid", f"Geçersiz kapsam {scope!r} — geçerli: S0, S1, S2."), ayrinti
    if s in ("S0", "S1"):
        r = reason if isinstance(reason, str) else ""
        if not r.strip():
            return ("reason_missing", f"{s} kapsamı --reason \"<tek satır gerekçe>\" ister."), ayrinti
        if "\n" in r or "\r" in r:
            return ("reason_missing", "Gerekçe TEK satır olmalı."), ayrinti
        if len(r.strip()) < REASON_MIN_LEN:
            return ("reason_missing",
                    f"Gerekçe çok kısa ({len(r.strip())} < {REASON_MIN_LEN} karakter)."), ayrinti
        return None, ayrinti
    # S2
    if intake is None or str(intake).strip() == "":
        return ("intake_missing",
                f"S2 kapsamı --intake <proje-göreli .md> ister ({INTAKE_REL.as_posix()}/ altında)."), ayrinti
    return _check_intake(proj, str(intake).strip(), axet_home)


def _check_intake(proj, intake: str, axet_home=None) -> tuple[tuple[str, str] | None, dict]:
    ayrinti: dict = {}
    kok = _project.project_dir(proj)
    ham = Path(intake)
    if ham.is_absolute() or ham.drive:
        return ("intake_invalid", "Intake yolu proje-GÖRELİ olmalı (mutlak yol kabul edilmez)."), ayrinti
    hedef = (kok / ham).resolve()
    izinli = (kok / INTAKE_REL).resolve()
    try:
        hedef.relative_to(izinli)
    except ValueError:
        return ("intake_invalid",
                f"Intake dosyası {INTAKE_REL.as_posix()}/ altında olmalı (verilen: {intake})."), ayrinti
    if hedef.suffix.lower() != ".md":
        return ("intake_invalid", "Intake dosyası .md olmalı."), ayrinti
    if not hedef.is_file():
        return ("intake_invalid", f"Intake dosyası bulunamadı: {intake}"), ayrinti
    denetci = Path(axet_home or AXET_HOME) / INTAKE_CHECKER_REL
    if not denetci.is_file():
        return ("intake_invalid",
                f"Intake denetleyicisi bulunamadı ({INTAKE_CHECKER_REL.as_posix()}) — fail-closed."), ayrinti
    try:
        spec = importlib.util.spec_from_file_location("_axet_intake_signoff", str(denetci))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        sonuc = mod.denetle(hedef)
    except Exception as exc:  # noqa: BLE001 — denetleyici koşamadıysa GEÇMEZ
        return ("intake_invalid", f"Intake denetleyicisi koşamadı ({type(exc).__name__}) — fail-closed."), ayrinti
    ayrinti["intake_check"] = sonuc
    if not sonuc.get("ok"):
        return ("intake_invalid", "Intake artefaktı kapıdan geçmedi: " + "; ".join(sonuc.get("bulgular") or [])), ayrinti
    return None, ayrinti


PACKAGE_TYPES = {"package", "devc", "devc/k"}


# aXet 2026-09-13: obje adını `name` DIŞINDA bir argümanda taşıyan araçlar → (argüman, obje tipi).
# Kapı bu adları da Z/Y denetler. FAIL-CLOSED: argüman kapıya verilmezse ad boş sayılır → ADR_0005_A
# (script `check_write`'ı tool_args'sız çağırırsa ad denetimi sessizce atlanmasın).
ARG_ADLARI = {
    "adt_screen_generate": (("fm_name", "function"), ("program", "program")),
}
_FM_TIPLERI = frozenset({"func", "function"})


def arg_adlari(tool: str, tool_args: dict | None, object_type=None) -> list[tuple]:
    """Kapının ek olarak Z/Y denetleyeceği (ad, tip) çiftleri."""
    a = tool_args if isinstance(tool_args, dict) else {}
    out = [(a.get(k), tip) for k, tip in ARG_ADLARI.get(tool, ())]
    if tool == "adt_post_shell" and str(object_type or "").strip().lower() in _FM_TIPLERI:
        ek = a.get("extra") if isinstance(a.get("extra"), dict) else {}
        out.append((ek.get("function_group"), "functiongroup"))   # standart FUGR içine FM = Yasak A
    return out


def obje_adi(tool: str, tool_args: dict | None):
    """Log/kapı için birincil obje adı: `name`; yoksa aracın hedef-obje argümanı (ekran üreteci: program)."""
    a = tool_args if isinstance(tool_args, dict) else {}
    if isinstance(a.get("name"), str):
        return a["name"]
    if tool == "adt_screen_generate" and isinstance(a.get("program"), str):
        return a["program"]
    return None


# Argümana bağlı transport zorunluluğu: araç → (açıklama, koşul).
TRANSPORT_KOSULLU = {
    "adt_screen_generate": ("mode WRITE/DELETE (READ hariç)",
                            lambda a: str((a or {}).get("mode") or "WRITE").strip().upper() != "READ"),
}


def transport_gerekli(tool: str, tool_args: dict | None) -> bool:
    if tool in REQUIRES_TRANSPORT:
        return True
    kosul = TRANSPORT_KOSULLU.get(tool)
    return bool(kosul and kosul[1](tool_args if isinstance(tool_args, dict) else {}))


def check_names(tool: str, obje_adi, object_type=None, ek_obje_adlari=(),
                adli_ekler=()) -> tuple[str, str] | None:
    # Kesin Yasak C: paket yaratma/değiştirme/silme yok. Ölçüldü (2026-09-13): guardrails obje tipine
    # bakmadığı için `adt_post_shell` object_type=package ile Z'li bir paket adı kapıdan geçiyordu.
    if isinstance(object_type, str) and object_type.strip().lower() in PACKAGE_TYPES:
        return ("ADR_0005_C", f"Paket yaratma/değiştirme/silme yasak (Kesin Yasak C): {tool} object_type={object_type}. "
                              "Paketi kullanıcı açar; yalnız mevcut pakete obje yaratılabilir.")
    try:
        if obje_adi is not None:
            if tool in DELETE_TOOLS:
                reject_standard_delete(str(obje_adi), object_type)
            else:
                require_customer_namespace(str(obje_adi), what=object_type or "object",
                                           object_type=object_type)
        for ek in ek_obje_adlari or ():
            require_customer_namespace(str(ek or ""), what="also[]")
        for ad, tip in adli_ekler or ():
            require_customer_namespace(ad.strip() if isinstance(ad, str) else "", what=tip, object_type=tip)
    except GuardrailViolation as gv:
        return gv.code, str(gv)
    return None


# Kaynak METNİ taşıyan yazma araçları → kaynağın geldiği argüman. Ölçüldü (tools/*.py imzaları,
# 2026-09-13): yalnız `adt_push_source(source=...)` ABAP kaynağı taşır. `adt_post_shell` kaynak
# almaz (`extra` → `create_object` imzasında kaynak yok); composite'lerin `artifact_path`'i DDIC
# reviewer girdisidir (ABAP değil); `adt_activate`/`adt_syntax_check`/`adt_classrun` SAP'deki
# mevcut kodu işler, kaynak metni almaz (bilinen sınır: IMPLEMENTATION.md §12.5).
SOURCE_ARG_TOOLS = {"adt_push_source": "source"}


def check_std_dml(tool: str, tool_args: dict | None, object_type=None,
                  ayrinti: dict | None = None) -> tuple[str, str] | None:
    """Kesin Yasak B: kaynakta standart tabloya doğrudan INSERT/UPDATE/DELETE/MODIFY var mı.

    FAIL-CLOSED: kaynak taşıyan araçta kaynak metni yoksa / metin değilse / tarayıcı koşamazsa
    `std_dml_scan_unavailable` ile reddedilir (sessiz geçiş YOK). Script'ler `check_write`'a
    `tool_args` (kaynak dahil) vermek zorundadır."""
    anahtar = SOURCE_ARG_TOOLS.get(tool)
    if anahtar is None:
        return None
    kaynak = (tool_args or {}).get(anahtar)
    if not isinstance(kaynak, str):
        return ("std_dml_scan_unavailable",
                f"Kesin Yasak B taraması koşamadı: {tool} için `{anahtar}` metni kapıya verilmedi "
                f"(tool_args). Kaynak taranmadan yazma yapılmaz.")
    try:
        from sapadt.std_dml_scan import mesaj, tara
        bulgular = tara(kaynak, object_type if isinstance(object_type, str) else None)
    except Exception as exc:  # noqa: BLE001 — tarayıcı koşamadıysa GEÇMEZ
        return ("std_dml_scan_unavailable",
                f"Kesin Yasak B taraması koşamadı ({type(exc).__name__}) — fail-closed.")
    if ayrinti is not None:
        ayrinti["std_dml_bulgular"] = [b.as_dict() for b in bulgular]
    if bulgular:
        return ("ADR_0005_B", mesaj(bulgular))
    return None


def log_path(proj) -> Path:
    return _project.project_dir(proj) / LOG_REL


def _log_yazilabilir(proj) -> bool:
    p = log_path(proj)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8"):
            pass
        return True
    except OSError:
        return False


def log_write_attempt(proj, *, tool: str, obje_adi=None, object_type=None, scope=None, reason=None,
                      intake=None, result_code: str, exit_code: int | None = None) -> bool:
    """Deneme satırı ekle. Şifre/token/cookie/host YAZILMAZ (gerekçe metni de temizlenir)."""
    sirlar = (_redact.bilinen_sirlar(_project.effective_conn_value("ADT_SAP_USER", None, proj),
                                     _project.effective_conn_value("ADT_SAP_PASSWORD", None, proj))
              + _redact.host_sirlari(_project.effective_conn_value("ADT_SAP_URL", None, proj)))
    satir = {
        "ts": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "tool": tool,
        "object": obje_adi if isinstance(obje_adi, str) else None,
        "object_type": object_type if isinstance(object_type, str) else None,
        "scope": scope,
        "reason": _redact.temizle_metin(reason, sirlar) if isinstance(reason, str) else None,
        "intake": intake,
        "result": result_code,
        "exit_code": exit_code,
    }
    try:
        p = log_path(proj)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(satir, ensure_ascii=False) + "\n")
        return True
    except OSError:
        return False


# ── ANA KAPI ──────────────────────────────────────────────────────────────────────────────

def check_write(tool: str, proj, *, obje_adi=None, object_type=None, ek_obje_adlari=(),
                transport=None, require_transport_flag: bool | None = None,
                scope=None, reason=None, intake=None, sap_write_flag: bool = False,
                tool_args: dict | None = None, axet_home=None, log: bool = True) -> GateResult:
    """Yazma kapısı. Red kararını `log=True` iken KENDİSİ loglar; izin verildiyse işlemin
    sonucunu çağıran `log_write_attempt` ile loglar."""
    kok = _project.project_dir(proj)
    res = GateResult(allowed=False, project_dir=str(kok),
                     tier=get_active_tier(kok),
                     sap_write_optin=optin_file(axet_home).is_file(),
                     scope=(str(scope).strip().upper() if isinstance(scope, str) and scope.strip() else None),
                     reason=reason if isinstance(reason, str) else None,
                     intake=intake if isinstance(intake, str) else None)

    def red(kod: str, mesaj: str) -> GateResult:
        res.code, res.message = kod, mesaj
        if log:
            log_write_attempt(kok, tool=tool, obje_adi=obje_adi, object_type=object_type, scope=res.scope,
                              reason=res.reason, intake=res.intake, result_code=kod, exit_code=2)
        return res

    cfg, hata = check_project(kok)
    if hata:
        return red(*hata)
    if not res.sap_write_optin:
        return red("write_not_optin_global",
                   f"SAP yazma bu makinede açılmamış: {WRITE_OPTIN_REL.as_posix()} yok. "
                   "Kullanıcı `install.py --sap-write` ile açar; araç bu dosyayı oluşturmaz.")
    if not sap_write_flag:
        return red("write_flag_missing", "Yazma sınıfı araç --sap-write bayrağı ister.")
    if res.tier != "DEV":
        return red("tier_not_writable",
                   f"Bağlantı tier'ı {res.tier} — yazma yalnız DEV'de. Tier .conn_adt `ADT_SAP_TIER` "
                   "satırından okunur (fail-closed: satır yok/çakışık → UNKNOWN; ortam değişkeni sayılmaz).")
    baglanti = check_connection(kok)
    if baglanti:
        return red(*baglanti)
    kapsam, ayrinti = check_scope(kok, scope, reason, intake, axet_home)
    res.details.update(ayrinti)
    if kapsam:
        return red(*kapsam)
    isim = check_names(tool, obje_adi, object_type, ek_obje_adlari,
                       arg_adlari(tool, tool_args, object_type))
    if isim:
        return red(*isim)
    dml = check_std_dml(tool, tool_args, object_type, res.details)
    if dml:
        return red(*dml)
    if require_transport_flag if require_transport_flag is not None else transport_gerekli(tool, tool_args):
        try:
            require_transport(transport if isinstance(transport, str) else None, what=f"{tool}",
                              package=(tool_args or {}).get("package")
                              if tool in TMP_MUAF_ARACLAR else None)
        except GuardrailViolation as gv:
            return red(gv.code, str(gv))
    dil = check_language(kok, cfg)
    if dil:
        return red(*dil)
    if (tool_args or {}).get("skip_reviewer"):
        return red("reviewer_bypass_forbidden",
                   "skip_reviewer=true kabul edilmez: reviewer ön kontrolü bu yolda atlanamaz. "
                   "BLOCKER'ı düzelt.")
    if str((tool_args or {}).get("ack_drop") or "").strip():
        # ÖLÇÜLDÜ (lib/validators/check_table_field_drop.py:143-153): adı verilen alanların DROP'u
        # BLOCKER yerine exit 0 (`onayli-drop-ack`) olur ⇒ ack_drop veri-kaybı BLOCKER'ını
        # ATLATIR. Onay kullanıcı+lider kararıdır; model tarafından verilen bir argüman olamaz.
        return red("reviewer_bypass_forbidden",
                   "ack_drop kabul edilmez: tablo alanı DROP BLOCKER'ını atlatır (veri kaybı). "
                   "Bilinçli alan silme kullanıcının kendi yaptığı ayrı bir işlemdir.")
    if not _log_yazilabilir(kok):
        return red("write_log_unavailable",
                   f"Deneme logu yazılamıyor ({LOG_REL.as_posix()}) — iz bırakmadan yazma yapılmaz.")
    res.allowed = True
    return res


def check_read(tool: str, proj) -> GateResult:
    """Okuma çağrısı ön denetimi (sap-project.json + bağlantı kimliği). PII guard araç içindedir;
    script'ler için `check_data_access` kullan."""
    kok = _project.project_dir(proj)
    res = GateResult(allowed=False, project_dir=str(kok), tier=get_active_tier(kok),
                     sap_write_optin=optin_file().is_file())
    _cfg, hata = check_project(kok)
    if hata:
        res.code, res.message = hata
        return res
    baglanti = check_connection(kok)
    if baglanti:
        res.code, res.message = baglanti
        return res
    res.allowed = True
    return res


def check_data_access(proj, table, *, fields=None, acknowledge_risk=False, approval_text=None) -> tuple[str, str] | None:
    """KVKK/PII guard'ı script'ler için (araçlar `data_guard.require_data_access`'i zaten çağırır)."""
    from sapadt.data_guard import require_data_access
    try:
        require_data_access(get_active_tier(proj), table, fields=fields,
                            acknowledge_risk=acknowledge_risk, approval_text=approval_text)
    except GuardrailViolation as gv:
        return gv.code, str(gv)
    return None


def review_preflight(task: str | None, artifact_path: str | None, ack_drop: str = "") -> tuple[tuple[str, str] | None, str]:
    """Reviewer ön kontrolü (script'ler için). Döner ((kod, mesaj)|None, özet)."""
    from sapadt._reviewer import run_reviewer
    r = run_reviewer(task, artifact_path, ack_drop=ack_drop)
    ozet = f"{r.verdict}" + (f" ({r.skip_reason})" if r.skip_reason else "")
    if r.is_blocker:
        return ("reviewer_blocker", f"Reviewer BLOCKER: {r.blocker_count} blocker, {r.warning_count} warning"), ozet
    return None, ozet


_REVIEWER_ICEREN = frozenset({"adt_push_source", "adt_domain_create", "adt_dtel_create", "adt_struct_create"})


def _olculemedi_eki(rv: dict) -> str:
    """aXet 2026-09-14 (K1/D1): reviewer `unmeasured` taşıyorsa `gate.review` bunu da söyler."""
    gates = [str(k.get("gate")) for k in (rv.get("unmeasured") or []) if isinstance(k, dict)]
    return f"; ÖLÇÜLEMEDİ: {', '.join(gates)}" if gates else ""


def review_summary(tool: str, args: dict | None, result) -> str | None:
    """Araç sonucundan `gate.review` metni üret — reviewer koşmadıysa bunu AÇIKÇA söyler."""
    if tool_class(tool, args) != "write":
        return None
    if result is None:
        return "NOT_RUN: kapı çağrıyı araçtan önce reddetti"
    if not isinstance(result, dict):
        return "UNKNOWN: araç sonucu sözlük değil"
    if result.get("error") == "reviewer_blocker":
        rv = result.get("reviewer") or {}
        return (f"BLOCKER ({rv.get('blocker_count')} blocker, {rv.get('warning_count')} warning)"
                + _olculemedi_eki(rv))
    if result.get("error") == "preflight_blocker":
        n = len(((result.get("steps") or {}).get("pre_flight") or {}).get("findings") or [])
        return f"NOT_RUN: argüman ön kontrolü BLOCKER ({n} bulgu; steps.pre_flight) — reviewer'a ulaşılmadı"
    if tool not in _REVIEWER_ICEREN:
        return "NONE: bu araçta reviewer ön kontrolü tanımlı değil (kaynak çekirdekle aynı)"
    rv = result.get("reviewer")
    if isinstance(rv, dict):
        metin = str(rv.get("verdict"))
        if rv.get("skip_reason"):
            metin += f" ({rv.get('skip_reason')})"
        metin += _olculemedi_eki(rv)
        pc = result.get("post_check") or (result.get("steps") or {}).get("post_check")
        if isinstance(pc, dict) and pc.get("hukum"):
            metin += f"; post_check={pc.get('hukum')}"
        return metin
    return "NOT_RUN: araç reviewer'a ulaşmadan döndü (guard reddi ya da istisna)"
