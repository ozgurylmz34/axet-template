#!/usr/bin/env python3
"""Template'in özel aXet ajanlarını (`agents/sap-*.md`) kullanıcı ajan dizinine kurar, günceller, kaldırır.

aXet.code ≥ 1.5.1 kullanıcı ajanlarını `$AXET_AGENTS_DIR` ya da `<config tabanı>/axet-code/agents` dizininden okur
(config tabanı: `XDG_CONFIG_HOME`, yoksa `~/.config` — `install.py config_path()` ile aynı çözüm). Proje ajanlarından
farklı olarak güven onayı istemez. Ölçüldü (1.5.1, 2026-11-16/17): bu dizindeki tanımlar `agent list`'te `user`
kapsamıyla görünür, `agent validate` geçer; özel alt ajan çekirdeği ve proje `AGENTS.md`'sini görür.

Sahiplik: kurulan her dosyanın gövdesinin ilk satırı `İŞARET` + klon yoludur. İşareti taşımayan aynı adlı dosya
kullanıcınındır — üzerine yazılmaz, silinmez, yalnız bildirilir. Kaldırma yalnız işaretli dosyaları siler.
Kaynakta artık olmayan işaretli `sap-*.md` (emekli ajan) kaldırılır.

Kullanım (kütüphane): `planla(sap=True)` → eylem listesi · `uygula(plan)` → yazar.
Komut satırı: `python scripts/ajan_kurulum.py [--kaldir] [--dry-run]` (install.py bunu kendisi çağırır).
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

AXET_HOME = Path(__file__).resolve().parents[1]
KAYNAK_DIZIN = AXET_HOME / "agents"
KAYNAK_DESEN = "sap-*.md"
YER_TUTUCU = "{{AXET_KLON}}"
İŞARET = "<!-- aXet şablonu tarafından kurulur, elle değiştirme; kaynak:"


def ajan_dizini() -> Path:
    ozel = os.environ.get("AXET_AGENTS_DIR")
    if ozel:
        return Path(ozel)
    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path.home() / ".config"
    return root / "axet-code" / "agents"


def klon_yolu() -> str:
    return AXET_HOME.as_posix()


def isaret_satiri(ad: str) -> str:
    return f"{İŞARET} {klon_yolu()}/agents/{ad} -->"


def isle(ad: str, metin: str) -> str:
    """Kaynak tanımı kurulacak hâle getirir: yer tutucu → klon yolu, gövdenin başına sahiplik işareti."""
    metin = metin.replace("\r\n", "\n").replace(YER_TUTUCU, klon_yolu())
    if not metin.startswith("---\n"):
        raise ValueError(f"{ad}: YAML frontmatter ile başlamıyor")
    son = metin.find("\n---\n", 4)
    if son < 0:
        raise ValueError(f"{ad}: frontmatter kapanmıyor")
    ust, govde = metin[: son + 5], metin[son + 5:]
    return ust + "\n" + isaret_satiri(ad) + "\n" + govde.lstrip("\n")


def bizim_mi(metin: str) -> bool:
    for satir in metin.replace("\r\n", "\n").split("\n")[:60]:
        if satir.startswith(İŞARET):
            return True
    return False


@dataclass
class Eylem:
    tur: str        # yaz · guncelle · ayni · sil · cakisma
    hedef: Path
    icerik: str | None = None

    def satir(self) -> str:
        acik = {"yaz": "kurulacak", "guncelle": "güncellenecek", "ayni": "güncel",
                "sil": "kaldırılacak", "cakisma": "AYNI ADLI KULLANICI AJANI VAR — dokunulmadı"}[self.tur]
        return f"{self.hedef.name}: {acik}"


def _oku(p: Path) -> str | None:
    try:
        return p.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return None


def planla(sap: bool, kaldir: bool = False, kaynak: Path | None = None, hedef_dizin: Path | None = None) -> list[Eylem]:
    kaynak = kaynak or KAYNAK_DIZIN
    hedef_dizin = hedef_dizin or ajan_dizini()
    istenen: dict[str, str] = {}
    if sap and not kaldir and not kaynak.is_dir():
        # Bug gate LOW-4: kaynak klasörü yoksa (kısmi %guncelle: script geldi, `agents/` gelmedi) kurulu işaretli
        # ajanların hepsini "emekli" sayıp silmek yerine HİÇBİR ŞEY yapma.
        return []
    if sap and not kaldir:
        for f in sorted(kaynak.glob(KAYNAK_DESEN)):
            istenen[f.name] = isle(f.name, f.read_text(encoding="utf-8"))
    plan: list[Eylem] = []
    for ad, icerik in istenen.items():
        hedef = hedef_dizin / ad
        mevcut = _oku(hedef) if hedef.exists() else None
        if mevcut is None and not hedef.exists():
            plan.append(Eylem("yaz", hedef, icerik))
        elif mevcut is None or not bizim_mi(mevcut):
            plan.append(Eylem("cakisma", hedef))
        elif mevcut.replace("\r\n", "\n") == icerik:
            plan.append(Eylem("ayni", hedef))
        else:
            plan.append(Eylem("guncelle", hedef, icerik))
    if hedef_dizin.is_dir():
        for f in sorted(hedef_dizin.glob(KAYNAK_DESEN)):
            if f.name in istenen:
                continue
            mevcut = _oku(f)
            if mevcut is not None and bizim_mi(mevcut):
                plan.append(Eylem("sil", f))
    return plan


def uygula(plan: list[Eylem]) -> list[str]:
    """Planı yazar; her yazımı geri okuyarak doğrular. Dönüş: hata satırları (boş = başarı)."""
    hatalar: list[str] = []
    for e in plan:
        try:
            if e.tur in ("yaz", "guncelle"):
                e.hedef.parent.mkdir(parents=True, exist_ok=True)
                e.hedef.write_text(e.icerik, encoding="utf-8", newline="\n")
                if e.hedef.read_text(encoding="utf-8") != e.icerik:
                    hatalar.append(f"{e.hedef}: geri okunan içerik farklı")
            elif e.tur == "sil":
                e.hedef.unlink()
        except OSError as exc:
            hatalar.append(f"{e.hedef}: {exc}")
    return hatalar


def ozet(plan: list[Eylem]) -> str:
    sayac = {t: sum(1 for e in plan if e.tur == t) for t in ("yaz", "guncelle", "ayni", "sil", "cakisma")}
    return (f"kurulacak {sayac['yaz']} · güncellenecek {sayac['guncelle']} · güncel {sayac['ayni']} · "
            f"kaldırılacak {sayac['sil']} · çakışma {sayac['cakisma']}")


def degisiklik_var(plan: list[Eylem]) -> bool:
    return any(e.tur in ("yaz", "guncelle", "sil") for e in plan)


def main() -> int:
    ap = argparse.ArgumentParser(description="aXet özel ajanlarını kur/güncelle/kaldır")
    ap.add_argument("--kaldir", action="store_true", help="şablonun kurduğu ajanları kaldır")
    ap.add_argument("--dry-run", action="store_true", help="yazmadan planı göster")
    args = ap.parse_args()
    plan = planla(sap=True, kaldir=args.kaldir)
    print(f"Ajan dizini: {ajan_dizini()}")
    for e in plan:
        print(f"  {e.satir()}")
    print(f"Özet: {ozet(plan)}")
    if args.dry_run:
        print("(dry-run: hiçbir şey yazılmadı)")
        return 0
    hatalar = uygula(plan)
    for h in hatalar:
        print(f"HATA: {h}")
    return 1 if hatalar else 0


if __name__ == "__main__":
    sys.exit(main())
