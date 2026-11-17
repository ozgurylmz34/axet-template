#!/usr/bin/env python3
"""Template'in özel aXet ajanlarını (`agents/sap-*.md`) kullanıcı ajan dizinine kurar, günceller, kaldırır.

aXet.code ≥ 1.5.1 kullanıcı ajanlarını `$AXET_AGENTS_DIR` → `$XDG_CONFIG_HOME/axet-code/agents` → (Windows, XDG yok)
`%LOCALAPPDATA%\\axet-code\\agents` dizininden okur (`ajan_dizini()`; global config dosyasının yeri `install.py
config_path()` bundan FARKLIDIR). Proje ajanlarından farklı olarak güven onayı istemez. Ölçüldü (1.5.1, 2026-11-16/17): bu dizindeki tanımlar `agent list`'te `user`
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
import re
import shutil
import subprocess
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
# Özel kullanıcı ajanlarının çalıştığı ölçülen en eski motor (docs/axet-davranis-olcumleri.md: 1.5.1'de çalışır,
# 1.3.0'da çalışmıyordu; aradaki sürümler ölçülmedi). Daha eski motora ajan dosyası kurmak doctor'a sahte PASS
# verdirir, kurallar da motorun tanımadığı ajanı önerir ⇒ kurulum atlanır, kullanıcıya motoru güncellemesi söylenir.
ASGARI_MOTOR = (1, 5, 1)


def surum_coz(metin: str | None) -> tuple[int, int, int] | None:
    """`axet-code version 1.5.1` → (1, 5, 1). Çözülemezse None."""
    metin = metin or ""
    # Önce `version` sözcüğüne bağlı sürüm (çıktıda başka bir sürüm numarası geçse de motorunki alınır), yoksa ilk X.Y.Z.
    m = (re.search(r"\bversion\s+v?(\d+)\.(\d+)\.(\d+)", metin, re.I)
         or re.search(r"(?<![\d.])v?(\d+)\.(\d+)\.(\d+)", metin))
    return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def surum_metni(surum: tuple[int, ...] | None) -> str:
    return ".".join(str(p) for p in surum) if surum else "?"


def motor_surumu() -> tuple[int, int, int] | None:
    """PATH'teki `axet-code -v` sürümü. Motor yok · çalışmıyor · çıktı çözülemiyor ⇒ None (ÖLÇÜLEMEDİ). Ölçülemeyen
    sürüm eski SAYILMAZ: kurulumu engellemez, yalnız `AJANLAR:` satırında belirtilir."""
    exe = shutil.which("axet-code")
    if not exe:
        return None
    try:
        r = subprocess.run([exe, "-v"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=30, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return None
    return surum_coz(r.stdout) if r.returncode == 0 else None


def motor_eski_mi(surum: tuple[int, int, int] | None) -> bool:
    return surum is not None and surum < ASGARI_MOTOR


def motor_eski_mesaji(surum: tuple[int, int, int] | None) -> str:
    asgari = surum_metni(ASGARI_MOTOR)
    return (f"aXet.code {surum_metni(surum)} < {asgari}: özel ajanların çalıştığı yalnız {asgari} ve üstünde "
            f"ölçüldü → aXet.code'u {asgari} ya da üstüne güncelle, sonra aXet'te %guncelle yaz (ajanlar o zaman "
            "kurulur)")


def _windows() -> bool:
    return os.name == "nt"


def _ev_dizini() -> Path:
    return Path.home()


def ajan_dizini() -> Path:
    """Motorun kullanıcı ajanlarını okuduğu dizin. Ölçüldü (1.5.1, Windows, `axet-code dirs` + `agent list`, kontrol
    gruplu 2026-11-17): `AXET_AGENTS_DIR` → `XDG_CONFIG_HOME/axet-code/agents` → (XDG yoksa) Windows'ta
    `%LOCALAPPDATA%\\axet-code\\agents`. Global config dosyası ise XDG yokken de `~/.config/axet-code/axet-code.json`'dan
    okunur — ajan dizini config dizininin altı DEĞİLDİR. Windows dışı (XDG yok) ölçülmedi: `~/.config` varsayılır."""
    ozel = os.environ.get("AXET_AGENTS_DIR")
    if ozel:
        return Path(ozel)
    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        return Path(base) / "axet-code" / "agents"
    yerel = os.environ.get("LOCALAPPDATA")
    if _windows() and yerel:
        return Path(yerel) / "axet-code" / "agents"
    return _ev_dizini() / ".config" / "axet-code" / "agents"


def _ayni_dizin(a: Path, b: Path) -> bool:
    """Yol METNİ değil fiziksel dizin karşılaştırılır: junction/symlink ile aynı yere çıkan iki yol aynı sayılır — yoksa
    aynı dosya hem "güncel" hem "eski konumda sil" olur, ajanlar her iki kurulumda bir kaybolur. Ölçülemezse
    (OSError) aynı sayılır: temizlik atlanır, silme olmaz (fail-closed)."""
    if a == b:
        return True
    try:
        if a.exists() and b.exists():
            return os.path.samefile(a, b)
        return a.resolve() == b.resolve()
    except OSError:
        return True


def eski_ajan_dizini() -> Path | None:
    """v0.5.22 Windows'ta XDG yokken ajanları `~/.config/axet-code/agents`'a yazıyordu; motor orayı okumaz. O dizinde
    kalan İŞARETLİ kopyalar temizlenir. Yalnız o durumda (Windows · XDG yok · AXET_AGENTS_DIR yok) ve eski dizin
    fiziksel olarak güncel dizinden FARKLIYSA döner (LOCALAPPDATA yokken ikisi aynı yola düşer). Testlerin gerçek ev
    dizinine ulaşmaması bu fonksiyona BAĞLI DEĞİLDİR: testler ev dizinini ve LOCALAPPDATA'yı kendileri yamalar."""
    if os.environ.get("AXET_AGENTS_DIR") or os.environ.get("XDG_CONFIG_HOME") or not _windows():
        return None
    eski = _ev_dizini() / ".config" / "axet-code" / "agents"
    return None if _ayni_dizin(eski, ajan_dizini()) else eski


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
    eski_konum: bool = False  # motorun okumadığı eski dizindeki işaretli kopya (v0.5.22 Windows)

    def satir(self) -> str:
        acik = {"yaz": "kurulacak", "guncelle": "güncellenecek", "ayni": "güncel",
                "sil": "kaldırılacak", "cakisma": "AYNI ADLI KULLANICI AJANI VAR — dokunulmadı"}[self.tur]
        ek = f" (eski konum, motor okumuyor: {self.hedef.parent})" if self.eski_konum else ""
        return f"{self.hedef.name}: {acik}{ek}"


def _oku(p: Path) -> str | None:
    try:
        return p.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return None


def planla(sap: bool, kaldir: bool = False, kaynak: Path | None = None, hedef_dizin: Path | None = None) -> list[Eylem]:
    kaynak = kaynak or KAYNAK_DIZIN
    eski_dizin = eski_ajan_dizini() if hedef_dizin is None else None
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
    if eski_dizin is not None and eski_dizin.is_dir():
        # Eski (yanlış) konumdaki işaretli kopyalar: kaynakta olsun olmasın kaldırılır; kullanıcının dosyasına dokunulmaz.
        for f in sorted(eski_dizin.glob(KAYNAK_DESEN)):
            mevcut = _oku(f)
            if mevcut is not None and bizim_mi(mevcut):
                plan.append(Eylem("sil", f, eski_konum=True))
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
    if not args.kaldir:
        motor = motor_surumu()
        if motor_eski_mi(motor):
            # install.py ile aynı kapı (bug gate F3): bağımsız CLI de eski motora kurmaz.
            print(f"AJANLAR: ATLANDI — {motor_eski_mesaji(motor)}")
            return 1
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
