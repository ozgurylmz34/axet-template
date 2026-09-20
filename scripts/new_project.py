#!/usr/bin/env python3
"""Bir projeye aXet.code proje iskeletini kurar (templates/project).

Kurduğu dosyalar: AGENTS.md (oturum açılış komutu template yoluyla doldurulur) · .axet-code.json ·
.axet-code/.gitignore · .axet-code/memory/MEMORY.md + project_is-listesi.md · .axetcode-denylist · .gitignore
(kimlik dosyaları git'e kapalı) · .gitattributes. Var olan dosyalar EZİLMEZ; tek istisna aXet'in kendi ürettiği varsayılan
`.axet-code/.gitignore` (içeriği yalnız `*` — skill/komut/hafıza klasörlerini repodan saklar).

`--sap` ile ayrıca templates/project-sap (sap-project.json: SAP profili, sürüm, master_language) kurulur;
SAP araçları bu dosya doldurulmadan yalnız bağlantı testi (ping) çalıştırır.

Kullanım:
  python <TEMPLATE>/scripts/new_project.py [HEDEF_DİZİN] [--name AD] [--sap] [--dry-run] [--no-next-steps]

`--no-next-steps`: sondaki "Sonraki adımlar" listesi basılmaz (kendi adımlarını basan çağıran araç için, ör.
yeni_proje.py); başka hiçbir çıktı ve davranış değişmez.
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
TEMPLATE = AXET_HOME / "templates" / "project"
TEMPLATE_SAP = AXET_HOME / "templates" / "project-sap"
PLACEHOLDER = "<PROJE_ADI>"
AXET_DEFAULT_GITIGNORE = ".axet-code/.gitignore"

# --- şablon sürüm kaydı (TASARIM §2b seçenek A) ----------------------------------------------------
# Projenin hangi template sürümünden doğduğu. `%guncelle-proje`nin 3-yollu birleştirmesi TABAN
# İÇERİĞİNİ bu commit'ten geri kurar (`git show <commit>:templates/project/<rel>` + `_doldur`).
# Kayıt YOKSA taban bilinmez ⇒ `guncelle_proje.py` içerik eşleştirmesiyle geri düşer, o da
# tutmazsa vaka VTB olur. Bu yüzden kayıt İLK projelerden başlamalı (yayından önce).
SURUM_KAYDI = ".axet-code/sablon-surumu.json"
SURUM_KAYDI_SURUMU = 1


def _ikili_sablon_mu(rel: str, ham: bytes) -> bool:
    import guncelle  # aynı klasör; uzantı listesinin tek kaynağı
    return Path(rel).suffix.lower() in guncelle.IKILI_UZANTI or b"\0" in ham[:8000]


def satir_sonu_normalize(veri: bytes) -> bytes:
    """METİN içeriğin satır sonu normalizasyonu — CRLF **ve tek-başına CR** → LF.

    ⛔ TEK KAYNAK (K1, 2026-09-20). Eskiden iki yol AYRI normalize ediyordu: burası
    (`read_text`in universal-newlines'ı taklit ederek) tek-başına CR'yi de çeviriyordu,
    `guncelle_proje._norm` ise YALNIZ `CRLF`yi. Tek-başına CR içeren bir şablonda ikisi
    farklı sonuç verir ⇒ proje dosyası ile şablon blob'u aynı olduğu hâlde "yerel değişmiş"
    görünür. Sonucu SESSİZDİR: o dosya V3'e düşer ve V3 "listelenmez, yalnız sayılır" ⇒
    güncelleme kullanıcıya hiç sorulmadan kaybolur.

    ⚠ İKİLİ dosyaya UYGULANMAZ — PNG başlığı bile `CR LF` içerir. Çağıranın `ikili_mi`
    ile ayırması şarttır (`guncelle_proje._yazilacak` ayırır; `new_project` `_ikili_sablon_mu`).
    ⚠ Sıra önemli: önce `CRLF`, sonra kalan tek `CR`. Ters sırada `CRLF` → `LFLF` olurdu.

    Bugün 0/791 dosyada tek-başına CR var (2026-09-20'de ölçüldü, ikili hariç; kapsam:
    yalnız bu depo/bu dal) ⇒ sınıf teoriktir, bu yüzden YENİ GATE AÇILMADI (ADR 0019).
    """
    return veri.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def sablon_yollari(sap: bool) -> list[str]:
    """Projeye kurulan şablon dizinleri (klon-göreli). Tek kaynak: doctor ve guncelle_proje da bunu çağırır."""
    return ["templates/project"] + (["templates/project-sap"] if sap else [])


def sablon_commit(sap: bool, axet_home: Path | None = None) -> str | None:
    """Şablon dizinlerine DOKUNAN son commit. Git yoksa/klon değilse None (ÖLÇÜLEMEDİ)."""
    kok = axet_home or AXET_HOME
    try:
        r = subprocess.run(["git", "-C", str(kok), "log", "-1", "--format=%H", "--",
                            *sablon_yollari(sap)],
                           capture_output=True, text=True, stdin=subprocess.DEVNULL,
                           encoding="utf-8", errors="replace")
    except OSError:
        return None
    return (r.stdout.strip() or None) if r.returncode == 0 else None


def surum_kaydi_oku(target: Path) -> dict | None:
    f = target / SURUM_KAYDI
    if not f.is_file():
        return None
    try:
        veri = json.loads(f.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    return veri if isinstance(veri, dict) else None


def surum_kaydi_yaz(target: Path, name: str, sap: bool, commit: str | None, kaynak: str,
                    axet_home: Path | None = None) -> dict:
    """Kaydı yazar ve GERİ OKUYUP doğrular. Döner: yazılan kayıt."""
    kok = (axet_home or AXET_HOME).resolve()
    kayit = {"surum": SURUM_KAYDI_SURUMU, "template_commit": commit,
             "sablon_yollari": sablon_yollari(sap), "sap": sap, "ad": name,
             "axet_home": kok.as_posix(), "kaynak": kaynak,
             "zaman": datetime.datetime.now().isoformat(timespec="seconds")}
    f = target / SURUM_KAYDI
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(kayit, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if json.loads(f.read_text(encoding="utf-8")) != kayit:
        raise RuntimeError(f"{SURUM_KAYDI} yazıldı ama geri okunduğunda farklı çıktı.")
    return kayit


def sablon_surumu_durumu(target: Path, axet_home: Path | None = None) -> tuple[str, str]:
    """Projenin şablon sürümü klondakiyle aynı mı (TASARIM §9 tetiği).

    Döner: (durum, mesaj). durum ∈ guncel · eski · kayitsiz · cozulemedi · olculemedi.
    TEK KAYNAK: `doctor.py` ve `session_brief.py` ikisi de bunu çağırır (iki yerde ayrı ölçüm
    yapılırsa biri bayatlar). §9 "N yayın" der; yayın listesi (`guncelle/yayinlar.json`, P7)
    henüz yokken ÖLÇÜLEBİLİR birim ŞABLONA DOKUNAN COMMİT sayısıdır — metin bunu böyle söyler.
    """
    kok = (axet_home or AXET_HOME).resolve()
    sap = (target / "sap-project.json").is_file()
    guncel = sablon_commit(sap, kok)
    if guncel is None:
        return "olculemedi", (f"proje şablonu güncelliği ÖLÇÜLEMEDİ ({kok.as_posix()} git klonu "
                              "değil ya da git yok) — 'güncel' DEĞİL")
    kayit = surum_kaydi_oku(target)
    if kayit is None:
        return "kayitsiz", ("proje şablon sürümü kayıtlı değil → %guncelle-proje "
                            "(taban eşleştirmesiyle)")
    kayitli = kayit.get("template_commit")
    if kayitli == guncel:
        return "guncel", f"proje şablonu güncel ({str(guncel)[:10]})"
    try:
        r = subprocess.run(["git", "-C", str(kok), "rev-list", "--count",
                            f"{kayitli}..{guncel}", "--", *sablon_yollari(sap)],
                           capture_output=True, text=True, stdin=subprocess.DEVNULL,
                           encoding="utf-8", errors="replace")
        sayi = r.stdout.strip() if r.returncode == 0 else None
    except OSError:
        sayi = None
    if sayi is None:
        return "cozulemedi", (f"proje şablon kaydındaki commit klonda çözülemedi "
                              f"({str(kayitli)[:10]}) → %guncelle-proje (taban bilinmiyor: VTB)")
    return "eski", (f"proje şablonu eski ({sayi} şablon commit'i geride; "
                    f"{str(kayitli)[:10]} → {str(guncel)[:10]}) → %guncelle-proje")


def _doldur(text: str, name: str, axet_home: Path | None = None) -> str:
    """Şablon yer tutucuları: proje adı + template klonunun mutlak yolu (session_brief.py komutu için).

    `axet_home`: `%guncelle-proje` TABAN içeriğini geri kurarken, klon o günden beri taşınmış olabilir
    diye kayıttaki yolu verir (`sablon-surumu.json` `axet_home`). Verilmezse bugünkü klon kullanılır.
    """
    kok = (axet_home or AXET_HOME).resolve() if axet_home else AXET_HOME
    return text.replace(PLACEHOLDER, name).replace("<AXET_HOME>", kok.as_posix())


def git_hook_kablola(target: Path, dry_run: bool) -> str:
    """Hedef bir git reposunun köküyse `core.hooksPath=.githooks` ayarlar. Başka bir değer varsa dokunmaz."""
    def git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(target), *args], capture_output=True, text=True, stdin=subprocess.DEVNULL)

    elle = f'git -C "{target}" config core.hooksPath .githooks'
    try:
        r = git("rev-parse", "--show-toplevel")
    except OSError:
        return f"  [git] git bulunamadı — pre-commit kablolanmadı; elle: {elle}"
    if r.returncode != 0:
        return f"  [git] git reposu değil — pre-commit kablolanmadı; `git init` sonrası: {elle}"
    if Path(r.stdout.strip()).resolve() != target:
        return (f"  [git] hedef repo kökü değil ({r.stdout.strip()}) — core.hooksPath ayarlanmadı "
                "(.githooks repo kökünde olmalı)")
    mevcut = git("config", "--get", "core.hooksPath").stdout.strip()
    if mevcut.rstrip("/\\") == ".githooks":
        return "  [git] core.hooksPath=.githooks (zaten ayarlı)"
    if mevcut:
        return f"  [git] core.hooksPath başka bir değerde ({mevcut!r}) — dokunulmadı; aXet pre-commit'i için: {elle}"
    if dry_run:
        return "  [git] core.hooksPath=.githooks ayarlanacak (dry-run)"
    if git("config", "core.hooksPath", ".githooks").returncode != 0:
        return f"  [git] core.hooksPath AYARLANAMADI — elle: {elle}"
    return "  [git] core.hooksPath=.githooks ayarlandı (commit anında pre-commit denetimi koşar)"


def main() -> int:
    ap = argparse.ArgumentParser(description="aXet.code proje iskeleti kurar")
    ap.add_argument("target", nargs="?", default=os.getcwd(), help="hedef proje dizini (varsayılan: bulunulan dizin)")
    ap.add_argument("--name", help="proje adı (varsayılan: dizin adı)")
    ap.add_argument("--sap", action="store_true", help="SAP proje dosyalarını da kur (sap-project.json)")
    ap.add_argument("--dry-run", action="store_true", help="yazmadan ne yapılacağını göster")
    ap.add_argument("--allow-inside", action="store_true", help="template reposunun içine kurmaya izin ver")
    ap.add_argument("--no-next-steps", action="store_true",
                    help="sondaki 'Sonraki adımlar' listesini basma (kendi adımlarını basan çağıran araç için)")
    args = ap.parse_args()

    target = Path(args.target).resolve()
    if not target.is_dir():
        print(f"HATA: hedef dizin yok: {target}")
        return 2
    if (target == AXET_HOME or AXET_HOME in target.parents) and not args.allow_inside:
        print(f"HATA: hedef template reposunun içinde ({AXET_HOME}). Proje ayrı bir dizinde olmalı.")
        return 2
    name = args.name or target.name

    counts = {"oluşturuldu": 0, "değiştirildi": 0, "atlandı": 0}
    # Sürüm kaydı kararının girdisi `counts`'tan AYRI tutulur (K-E, ölçüldü 2026-09-18): aXet klasörü açılınca
    # `.axet-code/.gitignore`'ı `*` içeriğiyle KENDİSİ yazar. O dosya "değiştirildi"/"aynı" sayılır ama kullanıcının
    # önceden kurduğu bir proje dosyası DEĞİLDİR; sayılırsa her aXet'le açılmış klasörde doğum kaydı yazılmaz.
    # ⚠ Bu yüzden `counts` ile `onceden_kullanici` birebir eşleşmez — biri ekran özeti, öbürü karar girdisi.
    onceden_kullanici = 0
    sources = [(TEMPLATE, p) for p in sorted(TEMPLATE.rglob("*")) if p.is_file()]
    if args.sap:
        sources += [(TEMPLATE_SAP, p) for p in sorted(TEMPLATE_SAP.rglob("*")) if p.is_file()]
    for base, src in sources:
        rel = src.relative_to(base).as_posix()
        dst = target / rel
        # İkili şablon (görsel, arşiv …): yer tutucu doldurulmaz, bayt bayt kopyalanır (Z9 — eskiden
        # UnicodeDecodeError ile tüm kurulum yarıda kalıyordu; bugün repoda ikili şablon yok, gizli tuzak).
        # Ölçüt `%guncelle-proje` ile AYNI (uzantı + NUL): UTF-8 olarak çözülebilen ikili dosya (bug gate
        # 2026-09-19 #6) eskiden metin sayılıp yer tutucusu doldurulur ve satır sonları çevrilirdi.
        ham = src.read_bytes()
        text = None
        if not _ikili_sablon_mu(rel, ham):
            try:
                # `read_text()` ile AYNI satır sonu çevirisi (universal newlines): çevrilmezse CRLF şablon
                # aşağıdaki `write_text` ile Windows'ta `\r\r\n` olur.
                # K1 (2026-09-20): çeviri artık `satir_sonu_normalize` — `guncelle_proje._norm` ile
                # TEK kaynak. Elle yazılmış iki kopya tek-başına CR'de ayrışıyordu (bkz. fonksiyon notu).
                text = _doldur(satir_sonu_normalize(ham).decode("utf-8"), name)
            except UnicodeDecodeError:
                text = None
        if dst.exists():
            if text is None:
                current = dst.read_bytes()
                ayni = current == src.read_bytes()
                axet_varsayilani = False
            else:
                current = dst.read_text(encoding="utf-8", errors="replace")
                ayni = current == text
                axet_varsayilani = rel == AXET_DEFAULT_GITIGNORE and current.strip() == "*"
            if not axet_varsayilani:
                onceden_kullanici += 1
            if ayni:
                print(f"  [aynı]        {rel}")
                counts["atlandı"] += 1
                continue
            if axet_varsayilani:
                status, key = "[değiştirildi] (aXet varsayılanı `*` idi)", "değiştirildi"
            else:
                print(f"  [VAR, dokunulmadı] {rel}  — template ile farklı; gerekirse elle birleştir")
                counts["atlandı"] += 1
                continue
        else:
            status, key = "[oluşturuldu]", "oluşturuldu"
        print(f"  {status} {rel}")
        counts[key] += 1
        if not args.dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if text is None:
                shutil.copy2(src, dst)
            elif rel.startswith(".githooks/"):
                # git hook'u her platformda LF olmalı: CRLF'li `#!/bin/sh` satırı hook'u çalıştırmaz.
                with open(dst, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(text)
                dst.chmod(0o755)
            else:
                dst.write_text(text, encoding="utf-8")

    cikis = 0
    if args.sap:
        import sap_stamp  # aynı klasör
        agents = target / "AGENTS.md"
        mevcut = (agents.read_text(encoding="utf-8") if agents.exists()
                  else _doldur((TEMPLATE / "AGENTS.md").read_text(encoding="utf-8"), name))
        st, ayrinti = sap_stamp.denetle(mevcut)
        if st == "kanonik_yok":
            print(f"HATA: kanonik kesin yasak metni okunamadı — damgalanmadı: {ayrinti}")
            return 2
        if st == "bozuk":
            print(f"  [damga BOZUK — dokunulmadı] AGENTS.md: {ayrinti}. Tek BASLA/BITIR bloğu bırak, sonra tekrar çalıştır.")
            cikis = 1
        else:
            yeni, onceki = sap_stamp.damgala(mevcut)
            etiket = {"guncel": "[damga güncel]", "farkli": "[damga YENİLENDİ]", "yok": "[damgalandı]"}[onceki]
            print(f"  {etiket} AGENTS.md — kesin yasaklar (SAP)")
            if onceki != "guncel" and not args.dry_run:
                agents.write_text(yeni, encoding="utf-8")

    # --- şablon sürüm kaydı (TASARIM §2b) ---------------------------------------------------------
    # Kayıt DOĞUM sürümüdür: yalnız kaydı olmayan ve bu koşumda BAŞTAN kurulan projeye yazılır.
    # · Kayıt varsa dokunulmaz — yeniden çalıştırmada bugünü yazmak, dosyalar eski sürümde kalmışken
    #   tabanı ileri kaydırır (yanlış 3-yollu birleştirme).
    # · Kullanıcının dosyaları zaten varken doğum sürümü BİLİNMİYOR ⇒ uydurulmaz (aXet'in kendi yazdığı
    #   `.axet-code/.gitignore` `*` bu sayıma girmez — yukarıdaki `onceden_kullanici` notu);
    #   `%guncelle-proje` içerik eşleştirmesiyle geri düşer (SHA'sız geri düşüş).
    mevcut_kayit = surum_kaydi_oku(target)
    onceden_vardi = onceden_kullanici > 0
    if args.dry_run:
        print(f"  [şablon sürüm kaydı] {SURUM_KAYDI} " +
              ("var, dokunulmaz" if mevcut_kayit else "yazılacak" if not onceden_vardi
               else "YAZILMAYACAK (proje dosyaları zaten vardı)") + " (dry-run)")
    elif mevcut_kayit:
        print(f"  [şablon sürüm kaydı var] {SURUM_KAYDI} "
              f"({str(mevcut_kayit.get('template_commit'))[:10]}) — dokunulmadı")
    elif onceden_vardi:
        print(f"  [şablon sürüm kaydı yazılmadı] {SURUM_KAYDI} — proje dosyaları zaten vardı, "
              "doğum sürümü bilinmiyor; %guncelle-proje tabanı içerik eşleştirmesiyle bulur")
    else:
        commit = sablon_commit(args.sap)
        surum_kaydi_yaz(target, name, args.sap, commit, "new_project")
        print(f"  [şablon sürüm kaydı] {SURUM_KAYDI} = "
              f"{commit[:10] if commit else 'ÖLÇÜLEMEDİ (git yok ya da klon değil)'}")

    print(git_hook_kablola(target, args.dry_run))

    print(f"\nProje: {target} (ad: {name}) · " + " · ".join(f"{k}: {v}" for k, v in counts.items())
          + (" · dry-run: hiçbir şey yazılmadı" if args.dry_run else ""))
    if args.no_next_steps:
        return cikis
    adimlar = ["AGENTS.md içindeki <…> alanlarını doldur."]
    if args.sap:
        # 2026-09-14: bu satır yokken profil yer tutuculu kalıyor, SAP araçları yalnız --list/ping açıyordu.
        adimlar.append("sap-project.json içindeki sap_profile, release, master_language, cleancore_policy alanlarını doldur "
                       "(doldurulmazsa SAP araçları yalnız --list ve ping çalıştırır).")
    adimlar += [
        "Projede YENİ aXet oturumu aç; ilk satırda PROJECT-ID görünmeli.",
        "Davranış yüzeyini (AGENTS.md, .axet-code.json, denylist, .githooks, validators-local) gözden geçir ve\n"
        f"     KENDİ terminalinde onayla: python \"{AXET_HOME / 'scripts' / 'behavior_manifest.py'}\" generate",
        f"Doğrulama: python \"{AXET_HOME / 'scripts' / 'doctor.py'}\"",
    ]
    print("Sonraki adımlar:\n" + "\n".join(f"  {i}. {a}" for i, a in enumerate(adimlar, 1)))
    return cikis


if __name__ == "__main__":
    sys.exit(main())
