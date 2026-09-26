#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sap_adt_cli.py — SAP ADT araçlarının TEK komut satırı giriş noktası (aXet).

    python sap_adt_cli.py --list [--grep <desen>]
    python sap_adt_cli.py <tool> [--args-json '{...}' | --args-file <f.json>] [--project-dir <dir>]
      yazma sınıfı araçlar ek olarak:
        --sap-write --scope S0|S1|S2 [--reason "<tek satır>"] [--intake <.axet-code/intake/..md>]

Çıktı: stdout'a TEK JSON nesnesi
  {"ok", "tool", "class", "result", "error": {"code","message"}|null,
   "gate": {"project_dir","tier","sap_write_optin","scope","reason","intake","review"}}
Çıkış kodu: 0 başarı · 2 guard/kapı reddi (SAP'ye gidilmedi) · 1 araç/bağlantı hatası · 3 kullanım hatası

⛔ Yazma kapısı `sapadt/gate.py::check_write` içindedir; bu dosya yalnız çağırır.
"""
from __future__ import annotations

import argparse
import inspect
import json
import os
import sys
from pathlib import Path

for _akis in (sys.stdout, sys.stderr):
    try:
        _akis.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

EXIT_OK, EXIT_TOOL, EXIT_GATE, EXIT_USAGE = 0, 1, 2, 3

# Araç sonucu `ok:false` iken çıkış kodu sınıfı (hepsi SAP'ye gidilmeden üretilir).
GATE_RESULT_ERRORS = frozenset({"guardrail_violation", "reviewer_blocker", "tier_pii_guard",
                                "not_select", "write_keyword", "gecersiz_tablo_adi",
                                "gecersiz_kolon_adi", "std_dml_scan_unavailable", "std_ext_scan_unavailable",
                                "pull_before_edit_missing", "pull_state_unreadable",
                                "source_changed_since_pull",
                                # aXet 2026-09-13: domain argüman ön kontrolü · mesaj sınıfı üzerine yazma onaysız
                                "preflight_blocker", "msgclass_overwrite_not_allowed",
                                # Z90: patinaj kesicisi (`calistir` üretir, araç çağrılmadan; burada katalog eşliği için)
                                "repeated_failure"})
USAGE_RESULT_ERRORS = frozenset({"unsupported_type", "bad_regex", "no_scope", "invalid_argument"})
TLS_UYARI = "UYARI: TLS sertifika doğrulaması kapalı (ADT_SAP_SSL_VERIFY)"


class UsageError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class _Parser(argparse.ArgumentParser):
    def error(self, message):  # argparse varsayılanı exit 2 → sözleşme 3 ister
        raise UsageError("usage_error", message)


def _parser() -> _Parser:
    p = _Parser(prog="sap_adt_cli.py", add_help=True,
                description="SAP ADT araçları — tek giriş noktası (JSON çıktı).")
    p.add_argument("tool", nargs="?", help="araç adı (bkz. --list)")
    p.add_argument("--list", action="store_true", help="araçları listele")
    p.add_argument("--grep", help="yalnız --list ile: adı ya da açıklaması <desen>'i içeren araçlar "
                                  "(büyük/küçük harf duyarsız alt dize; çıktı şeması aynı)")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--args-json", help="araç argümanları (JSON nesnesi)")
    g.add_argument("--args-file", help="araç argümanları dosyası (JSON nesnesi)")
    p.add_argument("--project-dir", help="proje kökü (varsayılan: cwd)")
    p.add_argument("--sap-write", action="store_true", help="yazma sınıfı çağrı onayı")
    p.add_argument("--scope", help="S0|S1|S2")
    p.add_argument("--reason", help="tek satır gerekçe (S0/S1)")
    p.add_argument("--intake", help="proje-göreli intake .md (S2)")
    return p


KAPI_HATIRLATMA = ("HATIRLATMA: kapı reddini aşmak için kapı ayarını, kuralı ya da proje dosyalarını "
                   "(sap-project.json, .rules.md, izinler) DEĞİŞTİRME ve başka yoldan yazmayı deneme — "
                   "reddi ve sebebini kullanıcıya bildir (core/00-temel.md §3).")


def _cikti(payload: dict, kod: int) -> int:
    print(json.dumps(payload, ensure_ascii=False, default=str))
    if kod == EXIT_GATE:
        # K-O① (2026-09-18): stdout sözleşmesi TEK JSON — hatırlatma yalnız stderr'e
        print(KAPI_HATIRLATMA, file=sys.stderr)
    return kod


def _payload(tool=None, cls=None, result=None, err=None, gate=None, ok=False) -> dict:
    return {"ok": bool(ok), "tool": tool, "class": cls, "result": result,
            "error": ({"code": err[0], "message": err[1]} if err else None), "gate": gate}


def _arg_listesi(fn) -> list:
    out = []
    for ad, prm in inspect.signature(fn).parameters.items():
        kayit = {"name": ad, "type": (prm.annotation if isinstance(prm.annotation, str)
                                      else getattr(prm.annotation, "__name__", None)
                                      if prm.annotation is not inspect.Parameter.empty else None),
                 "required": prm.default is inspect.Parameter.empty}
        if prm.default is not inspect.Parameter.empty:
            try:
                json.dumps(prm.default)
                kayit["default"] = prm.default
            except TypeError:
                kayit["default"] = repr(prm.default)
        out.append(kayit)
    return out


def _ilk_satir(fn) -> str:
    doc = inspect.getdoc(fn) or ""
    return doc.strip().splitlines()[0].strip() if doc.strip() else ""


def _listele(desen: str | None = None) -> int:
    """`desen` verilirse (Z111ⓕ) yalnız adı ya da açıklaması onu içeren araçlar döner — büyük/küçük harf duyarsız ALT
    DİZE (regex değil). Öğe biçimi ve `counts` anahtarları süzmesiz listeyle aynıdır; `counts` süzülen kümeden sayılır.
    Araç kayıt tablosu (`load_all_tools`) değişmez — yalnız bu çıktı süzülür."""
    from sapadt import gate
    from sapadt._app import load_all_tools
    from sapadt._profile import TIP_KISITLI_ARACLAR, TIP_PROFIL_KISITI
    kayit = load_all_tools()
    araclar = []
    for ad in sorted(kayit):
        spec = kayit[ad]
        satir = {"name": ad, "class": gate.tool_class(ad, {}),
                 "description": _ilk_satir(spec.fn), "args": _arg_listesi(spec.fn),
                 "available_on": list(spec.available_on)}
        if ad in gate.CONDITIONAL_WRITE:
            satir["write_when"] = gate.CONDITIONAL_WRITE[ad][1]
        if ad in gate.REQUIRES_TRANSPORT:
            satir["requires_transport"] = True
        elif ad in gate.TRANSPORT_KOSULLU:
            satir["requires_transport"] = True
            satir["requires_transport_when"] = gate.TRANSPORT_KOSULLU[ad][0]
        if ad in TIP_KISITLI_ARACLAR:
            satir["object_type_available_on"] = {t: list(p) for t, p in TIP_PROFIL_KISITI.items()}
        araclar.append(satir)
    if desen is not None:
        d = desen.casefold()
        araclar = [a for a in araclar if d in a["name"].casefold() or d in (a["description"] or "").casefold()]
    sayim = {"read": sum(1 for a in araclar if a["class"] == "read"),
             "write": sum(1 for a in araclar if a["class"] == "write"), "total": len(araclar)}
    return _cikti(_payload(result={"tools": araclar, "counts": sayim}, ok=True), EXIT_OK)


def _args_yukle(ns) -> dict:
    ham = None
    if ns.args_json is not None:
        ham = ns.args_json
    elif ns.args_file is not None:
        try:
            ham = Path(ns.args_file).read_text(encoding="utf-8-sig")
        except OSError as exc:
            raise UsageError("args_file_unreadable", f"--args-file okunamadı: {exc}")
    if ham is None:
        return {}
    try:
        veri = json.loads(ham)
    except json.JSONDecodeError as exc:
        raise UsageError("args_invalid_json", f"Argümanlar geçersiz JSON: {exc}")
    if not isinstance(veri, dict):
        raise UsageError("args_not_object", "Argümanlar bir JSON nesnesi olmalı.")
    return veri


def _tls_uyarisi(proj) -> None:
    from sapadt import project
    deger = project.effective_conn_value("ADT_SAP_SSL_VERIFY", "false", proj) or ""
    if deger.strip().lower() not in ("true", "1", "yes"):
        print(TLS_UYARI, file=sys.stderr)


def _sonuc_hatasi(result) -> tuple[int, tuple[str, str] | None]:
    if not isinstance(result, dict):
        return (EXIT_OK, None) if result else (EXIT_TOOL, ("tool_failed", "araç boş sonuç döndü"))
    if result.get("ok") is True:
        return EXIT_OK, None
    hata = result.get("error")
    if hata == "guardrail_violation":
        return EXIT_GATE, (str(result.get("code") or "guardrail_violation"), str(result.get("message") or ""))
    kod = str(hata or result.get("error_code") or "tool_failed")
    mesaj = str(result.get("message") or result.get("hint") or result.get("diagnosis") or "")
    if hata in GATE_RESULT_ERRORS:
        return EXIT_GATE, (kod, mesaj)
    if hata in USAGE_RESULT_ERRORS:
        return EXIT_USAGE, (kod, mesaj)
    return EXIT_TOOL, (kod, mesaj)


def main(argv=None) -> int:
    try:
        ns = _parser().parse_args(argv)
    except UsageError as exc:
        return _cikti(_payload(err=(exc.code, exc.message)), EXIT_USAGE)

    if ns.grep is not None and not ns.list:
        return _cikti(_payload(err=("usage_error", "--grep yalnız --list ile kullanılır.")), EXIT_USAGE)
    if ns.list:
        if ns.tool:
            return _cikti(_payload(err=("usage_error", "--list ile araç adı birlikte verilmez.")), EXIT_USAGE)
        if ns.grep is not None and not ns.grep.strip():
            return _cikti(_payload(err=("usage_error", "--grep boş olamaz (süzmesiz liste için --grep verme).")),
                          EXIT_USAGE)
        return _listele(ns.grep.strip() if ns.grep is not None else None)
    if not ns.tool:
        return _cikti(_payload(err=("usage_error", "Araç adı ya da --list gerekli.")), EXIT_USAGE)

    # Proje kökü — kütüphane import edilmeden ÖNCE ortama basılır (.conn_adt çözümü buna bakar).
    proj = Path(ns.project_dir).resolve() if ns.project_dir else Path.cwd().resolve()
    if not proj.is_dir():
        return _cikti(_payload(tool=ns.tool, err=("project_dir_invalid", f"Proje dizini yok: {proj}")), EXIT_USAGE)
    from sapadt.project import PROJECT_ENV
    os.environ[PROJECT_ENV] = str(proj)

    from sapadt._app import load_all_tools
    if ns.tool not in load_all_tools():
        return _cikti(_payload(tool=ns.tool, err=("unknown_tool", f"Bilinmeyen araç: {ns.tool} (bkz. --list)")), EXIT_USAGE)
    try:
        args = _args_yukle(ns)
    except UsageError as exc:
        return _cikti(_payload(tool=ns.tool, err=(exc.code, exc.message)), EXIT_USAGE)
    payload, kod = calistir(ns.tool, args, proj, sap_write=ns.sap_write, scope=ns.scope,
                            reason=ns.reason, intake=ns.intake)
    return _cikti(payload, kod)


def on_kontrol(tool: str, args: dict, proj: Path, *, sap_write: bool = False, scope=None, reason=None,
               intake=None):
    """Kapı + profil ön kontrolü — araç ÇAĞRILMAZ, ağa gidilmez, log YAZILMAZ (log çağıranın).

    Dönüş: `(sinif, gdurum, err)` · `err` None = geçti, değilse `(kod, mesaj)` (çıkış 2 sınıfı).
    `calistir` bunu kullanır; toplu yazıcı (`sapadt/populate.py`) yazmaya başlamadan önce HER planlı
    çağrı için aynı fonksiyonu koşar ⇒ ikinci bir kapı mantığı yoktur.
    """
    from sapadt import gate
    from sapadt._app import load_all_tools
    spec = load_all_tools()[tool]
    sinif = gate.tool_class(tool, args)
    obje = gate.obje_adi(tool, args)
    otip = args.get("object_type") if isinstance(args.get("object_type"), str) else None
    gdurum = gate.GateResult(allowed=False, project_dir=str(proj), tier=gate.get_active_tier(proj),
                             sap_write_optin=gate.optin_file().is_file(),
                             scope=scope, reason=reason, intake=intake)
    if tool in gate.PRECHECK_EXEMPT_TOOLS:
        return sinif, gdurum, None
    if sinif == "write":
        ek = [o.get("name") for o in (args.get("also") or []) if isinstance(o, dict)]
        gdurum = gate.check_write(tool, proj, obje_adi=obje, object_type=otip, ek_obje_adlari=ek,
                                  transport=args.get("transport"), scope=scope, reason=reason,
                                  intake=intake, sap_write_flag=sap_write, tool_args=args,
                                  log=False)
        if not gdurum.allowed:
            return sinif, gdurum, (gdurum.code, gdurum.message)
    else:
        okuma = gate.check_read(tool, proj)
        if not okuma.allowed:
            return sinif, gdurum, (okuma.code, okuma.message)
    from sapadt._profile import aktif_profil, tip_uygun_mu, uygun_mu
    profil = aktif_profil(proj)
    if not uygun_mu(spec.available_on, profil):
        return sinif, gdurum, ("tool_not_available_for_profile",
                               f"{tool} bu profilde kullanılamaz (profil={profil}, "
                               f"available_on={list(spec.available_on)}).")
    tip_ok, tip_izinli = tip_uygun_mu(tool, otip, profil)
    if not tip_ok:
        return sinif, gdurum, ("type_not_available_for_profile",
                               f"{tool} object_type={otip} bu profilde kullanılamaz "
                               f"(profil={profil}, izinli={list(tip_izinli or ())}). Klasik "
                               "FUGR/FM ABAP Cloud profillerinde açılmaz.")
    return sinif, gdurum, None


def calistir(tool: str, args: dict, proj: Path, *, sap_write: bool = False, scope=None, reason=None,
             intake=None, tls_uyarisi: bool = True) -> tuple[dict, int]:
    """Tek araç çağrısının TAM hattı, süreç içi: imza → kapı/profil (`on_kontrol`) → araç → çıkış kodu
    → write-log → ipuçları → sır temizliği. Yazdırmaz; `(payload, çıkış_kodu)` döner.

    `main` bunu kullanır (2026-09-14 çıkarımından önceki `main` gövdesiyle aynı davranış; bayt kıyası
    IMPLEMENTATION.md §19). Toplu yazıcı her adımı bu fonksiyonla çağırır — kapıyı atlayan yol yoktur.
    Çağıran `PROJECT_ENV`'i önceden `proj`'a ayarlamış olmalıdır (`.conn_adt` çözümü buna bakar).
    """
    from sapadt import gate, project, redact
    from sapadt._app import load_all_tools
    spec = load_all_tools().get(tool)
    if spec is None:
        return _payload(tool=tool, err=("unknown_tool", f"Bilinmeyen araç: {tool} (bkz. --list)")), EXIT_USAGE
    try:
        inspect.signature(spec.fn).bind(**args)
    except TypeError as exc:
        return _payload(tool=tool, err=("invalid_args", f"Argümanlar araç imzasına uymuyor: {exc}")), EXIT_USAGE

    sirlar = (redact.bilinen_sirlar(project.effective_conn_value("ADT_SAP_USER", None, proj),
                                    project.effective_conn_value("ADT_SAP_PASSWORD", None, proj))
              + redact.host_sirlari(project.effective_conn_value("ADT_SAP_URL", None, proj)))
    obje = gate.obje_adi(tool, args)
    otip = args.get("object_type") if isinstance(args.get("object_type"), str) else None
    if tls_uyarisi:
        _tls_uyarisi(proj)
    sinif, gdurum, kapi_hatasi = on_kontrol(tool, args, proj, sap_write=sap_write, scope=scope,
                                           reason=reason, intake=intake)

    def bitir(result, kod, err, ok=False):
        gd = gdurum.gate_dict()
        gd["review"] = gate.review_summary(tool, args, result)
        if sinif == "write":
            gate.log_write_attempt(proj, tool=tool, obje_adi=obje, object_type=otip, scope=gdurum.scope,
                                   reason=gdurum.reason, intake=gdurum.intake,
                                   result_code=("ok" if kod == EXIT_OK else (err[0] if err else "tool_failed")),
                                   exit_code=kod)
        payload = _payload(tool=tool, cls=sinif, result=result, err=err, gate=gd, ok=ok)
        # aXet 2026-09-13: engellemeyen yönlendirme (sapadt/hints.py) — çıkış kodunu ve kararı DEĞİŞTİRMEZ.
        try:
            from sapadt import hints
            if sinif == "write":
                ch = hints.checklist_hint(tool, args)
                if ch:
                    payload["checklist_hint"] = ch
            kh = hints.known_errors_hint(tool, result, err, kod)
            if kh:
                payload["known_errors_hint"] = kh
        except Exception:  # noqa: BLE001 — ipucu hatası sözleşmeyi kırmaz
            pass
        return redact.temizle(payload, sirlar), kod

    if kapi_hatasi:
        return bitir(None, EXIT_GATE, kapi_hatasi)

    # Z90 PATİNAJ KESİCİSİ (sapadt/write_failures.py): aynı obje + aynı hata koduyla ESIK ardışık başarısız
    # yazmadan sonra araç ÇAĞRILMADAN çıkış 2. Fren, kapı değil: sayaç dosyası okunamazsa yazma sürer (stderr uyarısı).
    wf = None
    if sinif == "write":
        from sapadt import write_failures as wf
        engel, uyari = wf.kontrol(obje, otip, proj)
        if uyari:
            print(f"UYARI: patinaj sayacı: {uyari} — kesici bu çağrıda ölçemedi, yazma engellenmedi.", file=sys.stderr)
        if engel:
            return bitir(None, EXIT_GATE, (wf.KOD, wf.red_mesaji(engel)))

    try:
        result = spec.fn(**args)
    except Exception as exc:  # noqa: BLE001 — istisna JSON sözleşmesini kırmasın
        try:
            from sapadt.tools.atom import _err_from_exc
            result = _err_from_exc(exc)
        except Exception:  # noqa: BLE001
            result = {"ok": False, "error": "unexpected", "message": f"{type(exc).__name__}: {exc}"}
    kod, err = _sonuc_hatasi(result)
    seri = None
    if wf is not None:
        seri, uyari = wf.kaydet(obje, otip, None if kod == EXIT_OK else (err[0] if err else "tool_failed"), proj)
        if uyari:
            print(f"UYARI: patinaj sayacı: {uyari} — seri kaydedilemedi.", file=sys.stderr)
    payload, kod = bitir(result, kod, err, ok=(kod == EXIT_OK))
    if seri:
        payload["failure_streak"] = seri
    return payload, kod


if __name__ == "__main__":
    sys.exit(main())
