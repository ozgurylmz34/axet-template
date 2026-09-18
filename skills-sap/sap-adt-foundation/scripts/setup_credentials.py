#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""setup_credentials.py — SAP bağlantı dosyasını GELİŞTİRİCİNİN KENDİ TERMİNALİNDE oluşturur. aXet 2026-09-13.

⛔ Bu script ajan/araç tarafından ÇALIŞTIRILMAZ: stdin bir terminal değilse (boru, dosya, ajan kabuğu) HİÇBİR
   şey sormadan ve yazmadan çıkar (çıkış 3). Parola `getpass` ile alınır — ekrana yansımaz, argüman olarak
   verilemez, loga/çıktıya yazılmaz. Dosyaya yazılan hiçbir değer ekrana basılmaz.

Kaynak (salt-okur): çekirdek `scripts/setup_credentials.py` alan listesi (URL/USER/PASSWORD/CLIENT/LANGUAGE,
`:33-53`) ve şablon `claude/conn_adt.template:5-18` (anahtar adları + ADT_SAP_SSL_VERIFY/TIER/SYSTEM_NAME).
Kaynaktan BİLİNÇLİ farklar: kaynak parolayı `input()` ile açık yankıyla alıyordu (`:43`) ve `--json` ile parolayı
komut satırı argümanı olarak kabul ediyordu — İKİSİ DE alınmadı. Bağlantı testi yapılmaz; sonraki adım
`sap_doctor` (yerel + canlı tanı) önerilir.

Kullanım (proje kökünde, kendi terminalinde):
    python <foundation>/scripts/setup_credentials.py                 # → .conn_adt
    python <foundation>/scripts/setup_credentials.py --slot DEMO_DEV # → conn/DEMO_DEV.env (çoklu sistem)
    python <foundation>/scripts/setup_credentials.py --project-dir <proje> [--force]
Çıkış: 0 yazıldı · 1 doğrulama/yazma hatası ya da vazgeçildi · 3 kullanım (etkileşimsiz çağrı dahil).
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass

ANAHTARLAR = ("ADT_SAP_URL", "ADT_SAP_USER", "ADT_SAP_PASSWORD", "ADT_SAP_CLIENT", "ADT_SAP_LANGUAGE",
              "ADT_SAP_SSL_VERIFY", "ADT_SAP_TIER", "ADT_SAP_SYSTEM_NAME")
_URL = re.compile(r"^https?://[^\s<>]+$")
_CLIENT = re.compile(r"^\d{3}$")
_DIL = re.compile(r"^[A-Za-z]{2}$")
_AD = re.compile(r"^[A-Za-z0-9_.-]{1,40}$")
_USER = re.compile(r"^[^\s<>=]{1,40}$")


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def dogrula(d: dict) -> list[str]:
    """Hata listesi — mesajlar DEĞER İÇERMEZ (yalnız alan adı + kural)."""
    h = []
    if not _URL.match(d.get("ADT_SAP_URL", "")):
        h.append("ADT_SAP_URL: http(s)://host[:port] biçiminde olmalı, boşluk/<> içermemeli")
    if not _USER.match(d.get("ADT_SAP_USER", "")):
        h.append("ADT_SAP_USER: boş olamaz, boşluk/<>/= içeremez (en çok 40)")
    pw = d.get("ADT_SAP_PASSWORD", "")
    if not pw or "\n" in pw or "\r" in pw:
        h.append("ADT_SAP_PASSWORD: boş olamaz, satır sonu içeremez")
    if not _CLIENT.match(d.get("ADT_SAP_CLIENT", "")):
        h.append("ADT_SAP_CLIENT: 3 haneli sayı olmalı")
    if not _DIL.match(d.get("ADT_SAP_LANGUAGE", "")):
        h.append("ADT_SAP_LANGUAGE: 2 harf (projenin master_language'i) olmalı")
    if d.get("ADT_SAP_SSL_VERIFY") not in ("true", "false"):
        h.append("ADT_SAP_SSL_VERIFY: true|false")
    if d.get("ADT_SAP_TIER") not in ("DEV", "QA", "PRD"):
        h.append("ADT_SAP_TIER: DEV|QA|PRD")
    if not _AD.match(d.get("ADT_SAP_SYSTEM_NAME", "")):
        h.append("ADT_SAP_SYSTEM_NAME: harf/rakam/_ . - (en çok 40)")
    return h


def icerik(d: dict) -> str:
    satirlar = ["# SAP ADT bağlantısı — setup_credentials.py ile oluşturuldu. REPOYA GİRMEZ (.gitignore: .conn* / conn/*).",
                "# Değerleri yalnız bu dosyada tut; sohbete/log'a yazma. Doğrulama: sap_adt_cli.py sap_doctor"]
    satirlar += [f"{k}={d[k]}" for k in ANAHTARLAR]
    return "\n".join(satirlar) + "\n"


def etkilesimli_mi() -> bool:
    """Gerçek terminal mi? ÖLÇÜLDÜ (2026-09-13, Windows): stdin NUL aygıtına yönlendirilince `isatty()` True döner
    (NUL bir karakter aygıtıdır) → yalnız isatty ile etkileşimsiz çağrı soruları okumaya başladı ve EOFError ile düştü.
    Windows'ta ek olarak stdin tutamacının GERÇEK konsol olduğu (`GetConsoleMode` başarılı) istenir. Git Bash/mintty
    borusu konsol değildir → red (PowerShell/cmd ya da `winpty python …` kullanılır)."""
    try:
        if sys.stdin is None or not sys.stdin.isatty():
            return False
        if os.name == "nt":
            import ctypes
            import msvcrt
            tutamac = msvcrt.get_osfhandle(sys.stdin.fileno())
            mod = ctypes.c_uint32()
            return bool(ctypes.windll.kernel32.GetConsoleMode(ctypes.c_void_p(tutamac), ctypes.byref(mod)))
        return True
    except Exception:  # noqa: BLE001 — ölçülemezse etkileşimsiz say (fail-closed)
        return False


def _master_language(proj: Path) -> str | None:
    try:
        ml = json.loads((proj / "sap-project.json").read_text(encoding="utf-8")).get("master_language")
        return ml.strip().upper() if isinstance(ml, str) and _DIL.match(ml.strip()) else None
    except Exception:  # noqa: BLE001
        return None


def _gitignore_uyarisi(proj: Path, hedef_rel: str) -> str | None:
    gi = proj / ".gitignore"
    try:
        metin = gi.read_text(encoding="utf-8")
    except OSError:
        return "UYARI: proje kökünde .gitignore yok — bağlantı dosyasının repoya girmediğini kendin doğrula."
    desen = "conn/*" if hedef_rel.startswith("conn/") else ".conn*"
    return None if desen in metin else f"UYARI: .gitignore '{desen}' satırını içermiyor — dosya repoya girebilir, ekle."


def main(argv=None, *, girdi=input, parola=getpass.getpass, tty=None) -> int:
    p = _Parser(prog="setup_credentials.py", description="SAP bağlantı dosyasını etkileşimli oluştur (yalnız terminal).")
    p.add_argument("--project-dir", help="proje kökü (varsayılan: cwd)")
    p.add_argument("--slot", help="çoklu sistem: conn/<SLOT>.env yaz (yoksa .conn_adt)")
    p.add_argument("--force", action="store_true", help="var olan dosyanın üzerine sormadan yaz")
    try:
        ns = p.parse_args(argv)
    except ValueError as exc:
        print(f"[KULLANIM] {exc}", file=sys.stderr)
        return 3
    etkilesimli = etkilesimli_mi() if tty is None else tty
    if not etkilesimli:
        print("[RED] Bu script yalnız geliştiricinin KENDİ terminalinde, etkileşimli çalışır (stdin terminal değil). "
              "Hiçbir şey sorulmadı, hiçbir dosya yazılmadı. Ajan/araç üzerinden çalıştırma.", file=sys.stderr)
        return 3
    proj = Path(ns.project_dir).resolve() if ns.project_dir else Path.cwd().resolve()
    if not proj.is_dir():
        print("[KULLANIM] proje dizini yok.", file=sys.stderr)
        return 3
    if ns.slot is not None and not _AD.match(ns.slot):
        print("[KULLANIM] --slot: harf/rakam/_ . - (en çok 40).", file=sys.stderr)
        return 3
    hedef = proj / "conn" / f"{ns.slot}.env" if ns.slot else proj / ".conn_adt"
    hedef_rel = hedef.relative_to(proj).as_posix()
    if hedef.exists() and not ns.force:
        if girdi(f"{hedef_rel} zaten var. Üzerine yazılsın mı? [e/H]: ").strip().lower() not in ("e", "evet", "y", "yes"):
            print("Vazgeçildi — dosyaya dokunulmadı.")
            return 1

    ml = _master_language(proj)
    print(f"SAP bağlantı bilgileri → {hedef_rel}  (girdiler ekrana geri basılmaz; parola yankılanmaz)")
    d = {
        "ADT_SAP_URL": girdi("SAP URL (https://host:port): ").strip(),
        "ADT_SAP_USER": girdi("SAP kullanıcı: ").strip(),
        "ADT_SAP_CLIENT": girdi("Client (3 hane): ").strip(),
        "ADT_SAP_LANGUAGE": (girdi(f"Oturum dili [{ml or 'master_language'}]: ").strip() or (ml or "")).upper(),
        "ADT_SAP_SSL_VERIFY": (girdi("TLS sertifikası doğrulansın mı? (true/false) [false]: ").strip().lower() or "false"),
        "ADT_SAP_TIER": girdi("Tier (DEV/QA/PRD — yazma yalnız DEV'de): ").strip().upper(),
        "ADT_SAP_SYSTEM_NAME": (girdi(f"Sistem adı [{ns.slot or ''}]: ").strip() or (ns.slot or "")),
    }
    pw1 = parola("SAP parola (yankılanmaz): ")
    pw2 = parola("SAP parola (tekrar): ")
    if pw1 != pw2:
        print("[HATA] Parolalar eşleşmiyor — dosya yazılmadı.", file=sys.stderr)
        return 1
    d["ADT_SAP_PASSWORD"] = pw1
    hatalar = dogrula(d)
    if ml and d["ADT_SAP_LANGUAGE"] and d["ADT_SAP_LANGUAGE"] != ml:
        hatalar.append(f"ADT_SAP_LANGUAGE: sap-project.json master_language ({ml}) ile aynı olmalı (Yasak D; yazma "
                       "çağrıları aksi hâlde language_mismatch ile reddedilir)")
    if hatalar:
        print("[HATA] Dosya yazılmadı:\n  - " + "\n  - ".join(hatalar), file=sys.stderr)
        return 1
    try:
        hedef.parent.mkdir(parents=True, exist_ok=True)
        with open(hedef, "w", encoding="utf-8", newline="\n") as f:
            f.write(icerik(d))
        if os.name == "posix":
            os.chmod(hedef, 0o600)
    except OSError as exc:
        print(f"[HATA] Yazılamadı ({type(exc).__name__}).", file=sys.stderr)
        return 1
    finally:
        d["ADT_SAP_PASSWORD"] = ""
    print(f"[OK] {hedef_rel} yazıldı ({len(ANAHTARLAR)} anahtar; değerler basılmadı). tier={d['ADT_SAP_TIER']}")
    uy = _gitignore_uyarisi(proj, hedef_rel)
    if uy:
        print(uy)
    if ns.slot:
        print(f"Sonraki adım: python <foundation>/scripts/switch_tier.py {ns.slot} --project-dir <proje>")
    print("Sonraki adım: python <foundation>/scripts/sap_adt_cli.py sap_doctor --project-dir <proje>")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EOFError, KeyboardInterrupt):
        print("\nVazgeçildi — dosya yazılmadı.", file=sys.stderr)
        raise SystemExit(1)
