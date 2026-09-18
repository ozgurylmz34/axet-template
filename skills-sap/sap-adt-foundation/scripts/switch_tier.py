#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""switch_tier.py — projede aktif SAP sistemini değiştir (conn/ slotu → .conn_adt). aXet 2026-09-13.

Kural (kaynak çekirdek `scripts/switch_tier.py`, salt-okur):
  · Slotlar SİSTEM ADI ile anahtarlanır: `<proje>/conn/<SISTEM_ADI>.env` (:5-9). Sistem adı slottaki
    `ADT_SAP_SYSTEM_NAME`, yoksa dosya adı (:72-74).
  · Argüman önce birebir sistem adı, sonra tier kısaltması (DEV/QA/PRD + eşanlamlılar) ile çözülür; o tier'da
    birden çok sistem varsa BELİRSİZ → sistem adı istenir (:85-106).
  · Anahtar TAM eşleşir (`ADT_SAP_TIER_OLD=` sayılmaz, :46-64). Tier satırı yoksa UNKNOWN (sessiz DEV yok).
  · Doldurulmamış `<...>` değer varsa geçiş YAPILMAZ (:109-117).
  · Mevcut `.conn_adt` → `conn/.conn_adt.bak` yedeklenir, slot kopyalanır (:159-162).

Kaynaktan BİLİNÇLİ farklar:
  1. Dosya içeriği BASILMAZ (kaynak `:120-128` maskeli içerik basıyordu; URL/kullanıcı/client görünürdü).
     Çıktı tek JSON nesnesi: sistem adı + tier + dosya adları.
  2. Aynı dosyada ÇAKIŞAN iki tier değeri → UNKNOWN (aXet `_conn.get_active_tier` ile aynı politika).
  3. Parola satırında `<` yer tutucu sayılmaz (parola `<` içerebilir); yalnız sır olmayan anahtarlara bakılır.
  4. "Sunucuyu yeniden başlat" adımı yok: aXet CLI her çağrıda yeni süreçtir.
Tier fail-closed kalır: QA/PRD/UNKNOWN geçişi YAPILIR ama yazma kapısı reddeder (uyarı JSON'da).

Kullanım:
    python scripts/switch_tier.py --list [--project-dir P]
    python scripts/switch_tier.py <SISTEM_ADI | DEV | QA | PRD> [--project-dir P]
Çıkış: 0 geçildi/listelendi · 1 slotta yer tutucu ya da dosya hatası · 2 çözülemedi/belirsiz · 3 kullanım.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

TIER_ALIASES = {  # kaynak :36-40
    "DEV": "DEV", "DEVELOPMENT": "DEV", "SANDBOX": "DEV",
    "QA": "QA", "QAS": "QA", "QUALITY": "QA", "TEST": "QA",
    "PRD": "PRD", "PROD": "PRD", "PRODUCTION": "PRD",
}
SIR_ANAHTARLAR = frozenset({"ADT_SAP_PASSWORD"})


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def _cikti(kod: int, **alan) -> int:
    print(json.dumps({"ok": kod == 0, **alan}, ensure_ascii=False))
    return kod


def _satirlar(p: Path) -> list[str]:
    return p.read_text(encoding="utf-8-sig", errors="replace").splitlines()


def _degerler(p: Path, key: str) -> list[str]:
    from sapadt.project import conn_line_value
    return [v for v in (conn_line_value(ln, key) for ln in _satirlar(p)) if v]


def tier_of(p: Path) -> str:
    tierler = {TIER_ALIASES.get(v.strip().upper(), v.strip().upper()) for v in _degerler(p, "ADT_SAP_TIER")}
    if len(tierler) != 1:
        return "UNKNOWN"
    t = tierler.pop()
    return t if t in ("DEV", "QA", "PRD") else "UNKNOWN"


def name_of(p: Path) -> str:
    adlar = _degerler(p, "ADT_SAP_SYSTEM_NAME")
    return (adlar[-1] if adlar else p.stem).strip()


def yer_tutucu_anahtarlar(p: Path) -> list[str]:
    out = []
    for ln in _satirlar(p):
        s = ln.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = (x.strip() for x in s.split("=", 1))
        if k not in SIR_ANAHTARLAR and "<" in v and k not in out:
            out.append(k)
    return out


def registry(conn_dir: Path) -> list[tuple[str, Path, str]]:
    return [(name_of(e).upper(), e, tier_of(e)) for e in sorted(conn_dir.glob("*.env"))] if conn_dir.is_dir() else []


def resolve(raw: str, reg) -> tuple[Path | None, str | None, str | None]:
    """(slot, tier, hata_kodu). hata_kodu: None | 'not_found' | 'ambiguous'."""
    key = raw.strip().upper()
    for ad, yol, tier in reg:
        if ad == key:
            return yol, tier, None
    tk = TIER_ALIASES.get(key)
    if tk:
        isabet = [(ad, yol, tier) for ad, yol, tier in reg if tier == tk]
        if len(isabet) == 1:
            return isabet[0][1], tk, None
        if len(isabet) > 1:
            return None, tk, "ambiguous"
    return None, None, "not_found"


def main(argv=None) -> int:
    p = _Parser(prog="switch_tier.py", description="conn/<SISTEM_ADI>.env slotunu .conn_adt olarak etkinleştir.")
    p.add_argument("target", nargs="?", help="sistem adı ya da DEV|QA|PRD")
    p.add_argument("--list", action="store_true", help="slotları listele (ad + tier)")
    p.add_argument("--project-dir", help="proje kökü (varsayılan: cwd)")
    try:
        ns = p.parse_args(argv)
    except ValueError as exc:
        return _cikti(3, error={"code": "usage_error", "message": str(exc)})
    if bool(ns.list) == bool(ns.target):
        return _cikti(3, error={"code": "usage_error", "message": "Ya --list ya da hedef (sistem adı / DEV|QA|PRD) verin."})
    proj = Path(ns.project_dir).resolve() if ns.project_dir else Path.cwd().resolve()
    if not proj.is_dir():
        return _cikti(3, error={"code": "project_dir_invalid", "message": "Proje dizini yok."})
    conn_dir, aktif = proj / "conn", proj / ".conn_adt"
    reg = registry(conn_dir)
    sistemler = [{"system": ad, "tier": tier, "file": f"conn/{yol.name}"} for ad, yol, tier in reg]
    if ns.list:
        return _cikti(0, action="list", systems=sistemler,
                      active={"system": name_of(aktif).upper(), "tier": tier_of(aktif)} if aktif.is_file() else None)

    slot, tier, hata = resolve(ns.target, reg)
    if hata == "ambiguous":
        return _cikti(2, error={"code": "ambiguous_tier", "message": f"tier={tier} altında birden çok sistem var — "
                                                                     "tier yerine SİSTEM ADI ile geçin."},
                      systems=[s for s in sistemler if s["tier"] == tier])
    if hata:
        return _cikti(2, error={"code": "system_not_found",
                                "message": f"'{ns.target}' bir slota çözülemedi. conn/<SISTEM_ADI>.env oluşturun "
                                           "(scripts/setup_credentials.py --slot <SISTEM_ADI>)."}, systems=sistemler)
    eksik = yer_tutucu_anahtarlar(slot)
    if eksik:
        return _cikti(1, error={"code": "placeholder_values",
                                "message": f"conn/{slot.name} doldurulmamış <...> değer içeriyor: {', '.join(eksik)} "
                                           "(değerler basılmadı). Önce doldurun."})
    try:
        yedek = None
        if aktif.is_file():
            yedek = conn_dir / ".conn_adt.bak"
            shutil.copy2(aktif, yedek)
        shutil.copy2(slot, aktif)
    except OSError as exc:
        return _cikti(1, error={"code": "copy_failed", "message": f"Kopyalama başarısız ({type(exc).__name__})."})
    uyarilar = []
    if tier in ("QA", "PRD"):
        uyarilar.append(f"tier={tier} SALT-OKUNUR: yazma araçları tier_not_writable ile reddedilir.")
    elif tier != "DEV":
        uyarilar.append(f"tier ÇÖZÜLEMEDİ (UNKNOWN): conn/{slot.name} içine TEK 'ADT_SAP_TIER=DEV|QA|PRD' satırı ekleyin; "
                        "o zamana kadar yazma reddedilir (fail-closed).")
    return _cikti(0, action="switch", system=name_of(aktif).upper(), tier=tier, source=f"conn/{slot.name}",
                  active=".conn_adt", backup=("conn/.conn_adt.bak" if yedek else None), warnings=uyarilar,
                  next="python scripts/sap_adt_cli.py sap_doctor — yeni sistemin bağlantısını doğrula")


if __name__ == "__main__":
    raise SystemExit(main())
