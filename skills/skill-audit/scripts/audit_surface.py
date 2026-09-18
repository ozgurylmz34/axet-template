#!/usr/bin/env python3
"""audit_surface.py — dışarıdan gelen bir projenin ya da skill'in aXet davranış yüzeyini ÇALIŞTIRMADAN tarar.

Neden: aXet bir klasörde açılınca oradaki talimat dosyaları otomatik yüklenir, `.axet-code.json` izin
kurallarını değiştirebilir (ölçüldü: aynı desen projede kazanır) ve skill/komut metinleri modelin
çalıştıracağı komutları taşır. Tanımadığın içeriği kurmadan ya da o klasörde aXet açmadan önce bu yüzeyi gör.

Kullanım (hedefin DIŞINDAN çalıştır):
  python audit_surface.py <proje_ya_da_skill_klasörü>           özet: dosya ve risk sayıları
  python audit_surface.py <klasör> --deep                       eşleşen satırları da göster
Çıkış kodu: 0 yüksek risk yok · 1 YÜKSEK risk var · 2 kullanım hatası.
Script hiçbir dosyayı çalıştırmaz, import etmez, değiştirmez.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

AXET_HOME = Path(__file__).resolve().parents[3]
# Ölçüldü (aXet 1.3.0): proje kökünde bu dosyalar her oturum bağlama yüklenir.
AUTO_CONTEXT = ["AGENTS.md", "CLAUDE.md", "CLAUDE.local.md", "GEMINI.md", ".cursorrules",
                ".github/copilot-instructions.md"]
TEXT_SUFFIXES = {".md", ".py", ".ps1", ".psm1", ".sh", ".bash", ".js", ".mjs", ".ts", ".bat", ".cmd", ".json",
                 ".yaml", ".yml", ".toml", ".txt"}
RISK = [
    ("YÜKSEK", "ağdan indirip çalıştırma", r"(curl|wget|invoke-webrequest|iwr|irm|invoke-restmethod)\b[^\n]*\|\s*(sh|bash|iex|invoke-expression|python|powershell|pwsh)"),
    ("YÜKSEK", "kodlanmış/gizlenmiş komut", r"(-enc(odedcommand)?\s+[a-z0-9+/=]{20,}|frombase64string|base64\s+(-d|--decode)|invoke-expression|\biex\b)"),
    ("YÜKSEK", "izin/doğrulama atlatma", r"(--no-verify|--yolo|dangerously|auto-accept|git\s+push\s+[^\n]*(--force|-f\b)|git\s+reset\s+--hard)"),
    ("YÜKSEK", "SAP yazma iznini değiştirme", r"(sap-write\.local|install\.py[^\n]*--sap-write)"),
    ("ORTA", "TLS sertifika doğrulaması kapalı", r"(verify\s*=\s*false|ssl_verify\s*=\s*false|rejectunauthorized\s*:\s*false|-skipcertificatecheck|--insecure\b|node_tls_reject_unauthorized\s*=\s*['\"]?0)"),
    ("ORTA", "ağ erişimi", r"(https?://|requests\.(get|post|put|delete|patch)|urllib|\bcurl\b|\bwget\b|invoke-webrequest|invoke-restmethod|socket\.)"),
    ("ORTA", "süreç çalıştırma", r"(subprocess\.|os\.system|os\.popen|start-process|\bexec\(|\beval\()"),
    ("ORTA", "silme", r"(rm\s+-r|remove-item\b[^\n]*-recurse|shutil\.rmtree|os\.remove|del\s+/s|rd\s+/s)"),
    ("ORTA", "kimlik bilgisi/gizli dosya", r"(\.conn_adt|\.conn\b|\.env\b|password|passwd|\btoken\b|secret|credential|\.ssh\b)"),
]
RISK_RX = [(lvl, why, re.compile(rx, re.I)) for lvl, why, rx in RISK]


def template_rules() -> tuple[dict, str | None]:
    try:
        sys.path.insert(0, str(AXET_HOME / "scripts"))
        import install  # noqa: E402
        return install.load_rules(), None
    except Exception as exc:  # noqa: BLE001 — teşhis
        return {}, f"şablon izin kuralları okunamadı ({exc}) → ezme kontrolü ÖLÇÜLEMEDİ"


def scan_text(path: Path, deep: bool, bulgular: list) -> None:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        bulgular.append(("ORTA", f"okunamadı: {exc}", path, None))
        return
    for no, line in enumerate(lines, 1):
        for lvl, why, rx in RISK_RX:
            if rx.search(line):
                bulgular.append((lvl, why, path, (no, line.strip()[:160]) if deep else None))


def scan_config(path: Path, root: Path, bulgular: list) -> None:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        bulgular.append(("YÜKSEK", f".axet-code.json ayrıştırılamadı ({exc}) → elle aç, içeriği gizli olabilir", path, None))
        return
    ours, note = template_rules()
    if note:
        bulgular.append(("ORTA", note, path, None))
    prules = (data.get("permissions") or {}).get("rules") or {}
    for domain, pats in prules.items():
        if not isinstance(pats, dict):
            bulgular.append(("ORTA", f"permissions.rules.{domain} desen haritası değil", path, None))
            continue
        for pattern, decision in pats.items():
            if pattern in (ours.get(domain) or {}) and ours[domain][pattern] != decision:
                bulgular.append(("YÜKSEK", f"şablon kuralını EZİYOR: {domain}:{pattern} = {decision} (şablon: {ours[domain][pattern]})", path, None))
            elif decision == "allow":
                bulgular.append(("ORTA", f"izin veren kural: {domain}:{pattern} = allow", path, None))
    opts = data.get("options") or {}
    for key in ("context_paths", "skills_paths"):
        for entry in opts.get(key) or []:
            p = Path(entry)
            target = p if p.is_absolute() else (root / p)
            try:
                inside = target.resolve().is_relative_to(root.resolve())
            except (OSError, ValueError):
                inside = False
            if not inside:
                bulgular.append(("ORTA", f"proje DIŞINDAN {key} yükler: {entry}", path, None))
    for key in ("mcp", "hooks", "lsp"):
        if key in data:
            bulgular.append(("DÜŞÜK", f"'{key}' alanı var (mcp yok sayılır, hooks çalışmaz — içeriğine yine bak)", path, None))
    if (data.get("models") or {}):
        bulgular.append(("DÜŞÜK", "model sabitleniyor (models)", path, None))


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    deep = "--deep" in sys.argv
    if len(args) != 1 or not Path(args[0]).is_dir():
        print(__doc__)
        return 2
    root = Path(args[0]).resolve()
    bulgular: list = []
    taranan: list[Path] = []

    for rel in AUTO_CONTEXT:
        p = root / rel
        if p.is_file():
            bulgular.append(("ORTA", "her oturum otomatik yüklenen talimat dosyası (talimat enjeksiyonu yüzeyi)", p, None))
            taranan.append(p)
            scan_text(p, deep, bulgular)
    cfg = root / ".axet-code.json"
    if cfg.is_file():
        taranan.append(cfg)
        scan_config(cfg, root, bulgular)
    if not (root / ".axetcode-denylist").is_file():
        bulgular.append(("DÜŞÜK", ".axetcode-denylist yok (kimlik dosyaları dosya araçlarına açık)", root, None))
    dirs = [root / ".axet-code" / "skills", root / ".axet-code" / "commands"]
    if (root / "SKILL.md").is_file():
        dirs.append(root)
    for d in dirs:
        if not d.is_dir():
            continue
        for f in sorted(d.rglob("*")):
            if f.is_file() and f.suffix.lower() in TEXT_SUFFIXES and f not in taranan:
                taranan.append(f)
                scan_text(f, deep, bulgular)
            elif f.is_file() and f.suffix.lower() in {".exe", ".dll", ".so", ".dylib", ".bin", ".msi"}:
                bulgular.append(("YÜKSEK", "ikili (binary) dosya — içeriği okunamaz", f, None))

    print(f"═══ aXet DAVRANIŞ YÜZEYİ TARAMASI: {root} ═══")
    yuksek = 0
    ozet: dict = {}
    for lvl, why, path, hit in bulgular:
        yuksek += lvl == "YÜKSEK"
        key = (lvl, why, str(path))
        ozet.setdefault(key, []).append(hit)
    order = {"YÜKSEK": 0, "ORTA": 1, "DÜŞÜK": 2}
    for (lvl, why, path), hits in sorted(ozet.items(), key=lambda kv: (order[kv[0][0]], kv[0][2])):
        rel = Path(path).relative_to(root) if Path(path).is_relative_to(root) else path
        count = sum(1 for h in hits if h) if deep else len(hits)
        print(f"  [{lvl:6}] {rel} — {why}" + (f" ({count} eşleşme)" if count > 1 else ""))
        if deep:
            for h in hits:
                if h:
                    print(f"           satır {h[0]}: {h[1]}")
    if not bulgular:
        print("  Eşleşen yüzey yok.")
    print(f"KAPSAM: taranan {len(taranan)} metin dosyası (otomatik bağlam dosyaları, .axet-code.json, .axet-code/skills,"
          " .axet-code/commands, hedef bir skill ise tüm klasör). BAKILMAYANLAR: proje kaynak kodu, git geçmişi, "
          "desenle yakalanamayan davranışlar. Eşleşme bir İPUCUDUR: çalıştırılabilir her dosyayı ve SKILL.md'yi yine "
          "baştan sona oku. '0 bulgu' güvenli demek değildir.")
    print("═══ SONUÇ:", "⛔ YÜKSEK risk var — içeriği incele, kullanıcıya göster; onaysız kurma/açma" if yuksek
          else "yüksek risk eşleşmesi yok (ORTA bulguları yine gözden geçir)", "═══")
    return 1 if yuksek else 0


if __name__ == "__main__":
    sys.exit(main())
