#!/usr/bin/env python3
"""aXet.code template kurulumu: bu repoyu kullanıcının global aXet config'ine bağlar.

Yazdığı şeyler (yalnız bunlar; kullanıcının diğer ayarları korunur):
  options.context_paths  -> core/00-temel.md, memory/MEMORY.md (+ core/sap  --sap ile)
  options.skills_paths   -> skills (+ skills-sap  --sap ile)
  permissions.rules      -> config/permissions.json içeriği (yalnız `bash`; merkezi klonun `edit` yazma koruması
                            2026-09-18'de KALDIRILDI — gerekçe `load_rules` üstündeki not)

Kullanım:
  python scripts/install.py              kur / güncelle (SAP durumu korunur; ilk kurulumda kapalı)
  python scripts/install.py --sap        SAP paketini aç
  python scripts/install.py --no-sap     SAP paketini kapat
  python scripts/install.py --dry-run    yazmadan sonucu göster
  python scripts/install.py --uninstall  bu reponun eklediklerini kaldır (SAP yazma iznini de kapatır)
  python scripts/install.py --sap --sap-write   SAP'ye yazma iznini AÇ (yalnız kendi terminalinde; aXet
                                         oturumu bu komutu çalıştıramaz — bash deny kuralı)
  python scripts/install.py --no-sap-write     SAP'ye yazma iznini KAPAT

Global config: %XDG_CONFIG_HOME% ya da %USERPROFILE%\\.config altında axet-code\\axet-code.json
(ölçüldü: `axet-code dirs config`; global ve proje config'i birleşir). Değişiklikten önce yedek alınır.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

AXET_HOME = Path(__file__).resolve().parents[1]
CORE_FILE = AXET_HOME / "core" / "00-temel.md"
TEAM_MEMORY = AXET_HOME / "memory" / "MEMORY.md"
SAP_CORE_DIR = AXET_HOME / "core" / "sap"
SKILLS_DIR = AXET_HOME / "skills"
SAP_SKILLS_DIR = AXET_HOME / "skills-sap"
PERMISSIONS_FILE = AXET_HOME / "config" / "permissions.json"
# SAP'ye yazma için makine düzeyi izin; sap_adt_cli.py yazma kapısının ilk koşulu. Gitignore'lu.
SAP_WRITE_FLAG = AXET_HOME / "config" / "sap-write.local"
# Önceki sürümlerde config/permissions.json ile yayımlanıp artık dosyada olmayan kurallar: alan → desen → o zaman
# yazdığımız karar. Yeniden kurulum ve --uninstall bunları kullanıcı config'inden siler; karar kullanıcı tarafından
# değiştirilmişse dokunmaz, uyarır. Kaynak: `git log -p -- config/permissions.json` — e0e0b13, ae4309c, 42b37b8'de
# yayımlı olup güncel dosyada bulunmayan anahtarların tamamı (testte geçmişle karşılaştırılır).
# Neden (ölçüldü 2026-09-14, aXet.code 1.3.0): başa bağlı desen zincirli/sarmalanmış komutu kaçırır; uzun bir ask
# aynı komuta uyan kısa deny'ı ezer ve run modunda komut sorulmadan çalışır. Kalırsa yeni kuralların düzeltmesi boşa çıkar.
RETIRED_RULES: dict = {
    "bash": {
        # e0e0b13–42b37b8: başa bağlı git deny'ları → '*' önekli hâlleri
        "git push --force*": "deny",
        "git push -f*": "deny",
        "git push *--force*": "deny",
        "git push * -f*": "deny",
        "git reset --hard*": "deny",
        "git clean -f*": "deny",
        # e0e0b13–42b37b8: başa bağlı silme ask'ları → '*' önekli, deny'lardan kısa hâlleri
        "rm -rf *": "ask",
        "rm -r *": "ask",
        "Remove-Item *-Recurse*": "ask",
        "rd /s *": "ask",
        "del /s *": "ask",
        # 42b37b8: uzun deploy ask'ı → '*deploy_ui*'
        "*deploy_ui.py*deploy *": "ask",
    },
}


def config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path.home() / ".config"
    return root / "axet-code" / "axet-code.json"


def _norm(p: str | Path) -> str:
    return os.path.normcase(os.path.abspath(str(p)))


def is_ours(entry: object) -> bool:
    """Girdi bu reponun içini gösteren mutlak bir yol mu?"""
    if not isinstance(entry, str) or not os.path.isabs(entry):
        return False
    home = _norm(AXET_HOME)
    target = _norm(entry)
    return target == home or target.startswith(home + os.sep)


def _pattern_is_ours(pattern: str) -> bool:
    """Bu klonun içini gösteren bir izin deseni mi. `strip_ours` bununla, ARTIK ÜRETMEDİĞİMİZ klon `edit`
    deny'larını da (eski sürümlerin `clone_rules()`'u yazmıştı) yeniden kurulumda temizler — bkz. aşağıdaki not."""
    return is_ours(pattern.rstrip("*").rstrip("/"))


# KALDIRILDI (2026-09-18, TASARIM §"7 karar" madde 1 · P4/A3): `CLONE_PROTECTED` + `clone_rules()`.
# Ne yapıyordu: klonun core/ skills/ skills-sap/ scripts/ config/ templates/ klasörlerine, kullanıcının GLOBAL
# aXet config'ine 24 adet `edit` deny deseni (6 klasör × 4 harf varyantı) yazıyordu. `config/permissions.json`
# hiç `edit` kuralı taşımadığı için config'teki TÜM `edit` deny'ları buradan geliyordu.
# Neden kaldırıldı: `%guncelle` klonun içine YAZAR (3-yollu birleştirme sonucu dosyaya uygulanır); kendi
# koruması kendi akışını engellerdi. Zaten "kazara değişikliğe karşı" bir hatırlatmaydı, güvenlik sınırı
# değildi — eski docstring'in kendi ifadesiyle "başka harf karışımı ve bash atlatır".
# Yerine ne var: doctor `check_template()` klonun davranış yüzeyindeki değişiklikleri git'e karşı raporlar
# (`behavior_manifest.template_sinifla`) — ENGELLEME değil GÖRÜNÜRLÜK.
# Göç: eski kurulumların yazdığı `edit` deny'ları `strip_ours` + `_pattern_is_ours` ile yeniden kurulumda
# ve `--uninstall`'da silinir (tests/test_install.py::KlonKorumasiKaldirildiTest).


def load_rules() -> dict:
    return json.loads(PERMISSIONS_FILE.read_text(encoding="utf-8"))["rules"]


def sap_enabled(cfg: dict) -> bool:
    paths = (cfg.get("options") or {}).get("context_paths") or []
    return any(is_ours(p) and _norm(p) == _norm(SAP_CORE_DIR) for p in paths)


def strip_ours(cfg: dict, rules: dict, retired: dict | None = None) -> dict:
    """Bu reponun eklediklerini config'ten çıkarır. Emekli kurallar (RETIRED_RULES) yalnız karar bizim yazdığımızsa silinir.

    Dönüş: {"emekli_silinen": ["alan:desen", …], "emekli_korunan": ["alan:desen (config kararı ≠ yazdığımız)", …]}.
    """
    retired = RETIRED_RULES if retired is None else retired
    rapor: dict = {"emekli_silinen": [], "emekli_korunan": []}
    opts = cfg.get("options")
    if isinstance(opts, dict):
        for key in ("context_paths", "skills_paths"):
            if isinstance(opts.get(key), list):
                opts[key] = [p for p in opts[key] if not is_ours(p)]
                if not opts[key]:
                    del opts[key]
        if not opts:
            del cfg["options"]
    perms = cfg.get("permissions")
    if isinstance(perms, dict) and isinstance(perms.get("rules"), dict):
        prules = perms["rules"]
        for domain in set(rules) | {d for d, v in prules.items() if isinstance(v, dict)}:
            if isinstance(prules.get(domain), dict):
                for pattern in list(prules[domain]):
                    # bu reponun kuralı ya da (klon taşınmış/klasör listesi değişmiş olsa bile) klon içini gösteren desen
                    if pattern in rules.get(domain, {}) or _pattern_is_ours(pattern):
                        del prules[domain][pattern]
                    elif pattern in retired.get(domain, {}):
                        yazdigimiz = retired[domain][pattern]
                        if prules[domain][pattern] == yazdigimiz:
                            del prules[domain][pattern]
                            rapor["emekli_silinen"].append(f"{domain}:{pattern}")
                        else:
                            rapor["emekli_korunan"].append(
                                f"{domain}:{pattern} (config: {prules[domain][pattern]!r} ≠ yazdığımız: {yazdigimiz!r})")
                if not prules[domain]:
                    del prules[domain]
        if not prules:
            del perms["rules"]
        if not perms:
            del cfg["permissions"]
    return rapor


def apply_ours(cfg: dict, rules: dict, sap: bool) -> None:
    opts = cfg.setdefault("options", {})
    ctx = opts.setdefault("context_paths", [])
    ctx.extend([CORE_FILE.as_posix(), TEAM_MEMORY.as_posix()] + ([SAP_CORE_DIR.as_posix()] if sap else []))
    skills = opts.setdefault("skills_paths", [])
    skills.extend([SKILLS_DIR.as_posix()] + ([SAP_SKILLS_DIR.as_posix()] if sap else []))
    prules = cfg.setdefault("permissions", {}).setdefault("rules", {})
    for domain, patterns in rules.items():
        current = prules.setdefault(domain, {})
        if not isinstance(current, dict):
            raise SystemExit(
                f"HATA: permissions.rules.{domain} bir desen haritası değil ({current!r}). "
                "Bu değeri elle nesneye çevirin; config'e dokunulmadı."
            )
        current.update(patterns)


def check_env() -> list[tuple[str, str, bool]]:
    results = [("python", sys.version.split()[0], sys.version_info >= (3, 9))]
    for tool, args in (("git", ["--version"]), ("axet-code", ["-v"])):
        exe = shutil.which(tool)
        if not exe:
            results.append((tool, "BULUNAMADI (PATH)", False))
            continue
        try:
            out = subprocess.run([exe, *args], capture_output=True, text=True, timeout=30,
                                 stdin=subprocess.DEVNULL).stdout.strip().splitlines()
            results.append((tool, out[0] if out else "?", True))
        except Exception as exc:  # noqa: BLE001 — teşhis çıktısı
            results.append((tool, f"çalıştırılamadı: {exc}", False))
    rg = shutil.which("rg")
    results.append(("rg", rg or "YOK — aXet grep aracı yavaşlar (kurulum: winget install BurntSushi.ripgrep.MSVC)", bool(rg)))
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description="aXet.code template kurulumu")
    sap_group = ap.add_mutually_exclusive_group()
    sap_group.add_argument("--sap", action="store_true", help="SAP paketini aç")
    sap_group.add_argument("--no-sap", action="store_true", help="SAP paketini kapat")
    write_group = ap.add_mutually_exclusive_group()
    write_group.add_argument("--sap-write", action="store_true", help="SAP'ye yazma iznini aç (SAP paketi açık olmalı)")
    write_group.add_argument("--no-sap-write", action="store_true", help="SAP'ye yazma iznini kapat")
    ap.add_argument("--dry-run", action="store_true", help="yazmadan sonucu göster")
    ap.add_argument("--uninstall", action="store_true", help="bu reponun eklediklerini kaldır")
    args = ap.parse_args()
    if args.uninstall and args.sap_write:
        print("HATA: --uninstall ile --sap-write birlikte kullanılamaz.")
        return 3

    missing = [p for p in (CORE_FILE, TEAM_MEMORY, SKILLS_DIR, PERMISSIONS_FILE) if not p.exists()]
    if missing:
        print("HATA: template dosyaları eksik:", *[f"  {m}" for m in missing], sep="\n")
        return 2

    cfg_file = config_path()
    original = cfg_file.read_text(encoding="utf-8-sig") if cfg_file.exists() else ""
    try:
        cfg = json.loads(original) if original.strip() else {}
    except json.JSONDecodeError as exc:
        print(f"HATA: {cfg_file} geçerli JSON değil ({exc}). Dosyaya dokunulmadı.")
        return 2
    if not isinstance(cfg, dict):
        print(f"HATA: {cfg_file} bir JSON nesnesi değil. Dosyaya dokunulmadı.")
        return 2

    rules = load_rules()
    was_sap = sap_enabled(cfg)
    sap = True if args.sap else False if args.no_sap else was_sap
    if sap and not args.uninstall and not SAP_CORE_DIR.exists():
        print(f"HATA: SAP paketi istendi ama {SAP_CORE_DIR} yok.")
        return 2
    if args.sap_write and not sap:
        print("HATA: --sap-write için SAP paketi açık olmalı (python scripts/install.py --sap --sap-write).")
        return 2
    was_write = SAP_WRITE_FLAG.exists()
    if args.uninstall or args.no_sap_write or not sap:
        write_new = False
    else:
        write_new = True if args.sap_write else was_write

    emekli = strip_ours(cfg, rules)
    if not args.uninstall:
        apply_ours(cfg, rules, sap)
    new_text = json.dumps(cfg, indent=2, ensure_ascii=False) + "\n"

    print(f"Template kökü : {AXET_HOME}")
    print(f"Global config : {cfg_file}")
    print(f"İşlem         : {'KALDIR' if args.uninstall else 'KUR/GÜNCELLE'} · SAP paketi: "
          f"{'AÇIK' if was_sap else 'KAPALI'} -> {'—' if args.uninstall else ('AÇIK' if sap else 'KAPALI')}")
    print(f"SAP'ye yazma  : {'AÇIK' if was_write else 'KAPALI'} -> {'AÇIK' if write_new else 'KAPALI'}")
    if emekli["emekli_silinen"]:
        print(f"Eski template kuralları {'kaldırılacak' if args.dry_run else 'kaldırıldı'} "
              f"({len(emekli['emekli_silinen'])}): "
              + ", ".join(emekli["emekli_silinen"]))
    for satir in emekli["emekli_korunan"]:
        print(f"UYARI: eski template kuralının kararı config'te değiştirilmiş, dokunulmadı: {satir}")
    print("Ortam:")
    for name, info, ok in check_env():
        print(f"  [{'OK' if ok else 'UYARI'}] {name}: {info}")

    if args.dry_run:
        print("\n--- yazılacak içerik ---\n" + new_text + "(dry-run: hiçbir şey yazılmadı)")
        return 0
    if write_new != was_write:
        if write_new:
            SAP_WRITE_FLAG.write_text(
                "Bu makinede aXet SAP araçlarına yazma izni verildi (install.py --sap-write).\n"
                f"Açılış: {datetime.datetime.now():%Y-%m-%d %H:%M:%S}\n"
                "Yazma ayrıca şunları ister: .conn_adt tier=DEV, çağrıda --sap-write, kapsam beyanı.\n",
                encoding="utf-8")
            print(f"\nSAP'ye yazma izni AÇILDI: {SAP_WRITE_FLAG}\n"
                  "  Yazma yine yalnız .conn_adt'de tier=DEV olan sistemlerde, çağrıda --sap-write ve kapsam\n"
                  "  beyanıyla yapılır. Kapatmak için: python scripts/install.py --no-sap-write")
        else:
            SAP_WRITE_FLAG.unlink()
            print(f"\nSAP'ye yazma izni KAPATILDI ({SAP_WRITE_FLAG} silindi).")
    if new_text == original:
        print("\nDeğişiklik yok; config zaten güncel.")
        return 0

    cfg_file.parent.mkdir(parents=True, exist_ok=True)
    if cfg_file.exists():
        backup = cfg_file.with_name(f"{cfg_file.name}.bak-{datetime.datetime.now():%Y%m%d-%H%M%S}")
        shutil.copy2(cfg_file, backup)
        print(f"\nYedek: {backup}")
    cfg_file.write_text(new_text, encoding="utf-8")

    if json.loads(cfg_file.read_text(encoding="utf-8")) != cfg:
        print("HATA: yazılan config geri okunduğunda farklı çıktı.")
        return 1
    print(f"Yazıldı ve geri okunarak doğrulandı: {cfg_file}")
    if not args.uninstall:
        print("\nSonraki adım: YENİ bir aXet oturumu aç. İlk yanıtın ilk satırında "
              "'AXET-CORE-…' görünmeli.\nDoğrulama: python scripts/doctor.py  (model çağrılı test: --live)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
