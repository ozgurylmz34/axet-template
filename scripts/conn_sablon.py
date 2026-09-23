#!/usr/bin/env python3
"""conn_sablon.py — SAP bağlantı ŞABLONLARI (conn/DEV.env, conn/QA.env): yaz ve doğrula. aXet Z70 (2026-09-23).

`proje-tamamla.cmd` (projede `KURULUMU-TAMAMLA.cmd` kısayolu) bunu çağırır: kullanıcı bağlantı bilgilerini pencereye
değil Notepad'de şablon dosyaya yazar. Kural KOPYALANMAZ: anahtar listesi ve alan kuralları
`skills-sap/sap-adt-foundation/scripts/setup_credentials.py` (`ANAHTARLAR`, `dogrula`) içinden içe aktarılır. Ek olarak
her anahtarda (PAROLA DAHİL) `<...>` yer tutucu aranır — `switch_tier.py` parolada yer tutucu aramaz (parola `<`
içerebilir), bu yüzden doldurulmamış parola ancak burada yakalanır. Sınır: parolanın TAMAMI `<...>` biçimindeyse
(ör. `<abc>`) yer tutucu sayılır; öyle bir parola için `setup_credentials.py --slot` kullanılır.

Hiçbir değer ekrana basılmaz: hata satırları yalnız alan adı + kural içerir.

Kullanım:
  python <TEMPLATE>/scripts/conn_sablon.py hazirla --project-dir P   eksik conn/DEV.env ve conn/QA.env'i yazar (ezmez)
  python <TEMPLATE>/scripts/conn_sablon.py dogrula --project-dir P   her conn/*.env'i sınıflar
  python <TEMPLATE>/scripts/conn_sablon.py ozet --project-dir P [--json]   aktif sistem + her sistemin ad/tier/durumu
                                                                     (`%sistem` skill'i --json okur; değer basılmaz)
Çıkış (hazirla): 0 · 1 yazma hatası · 3 kullanım. Çıkış (ozet): 0 · 3 kullanım.
Çıkış (dogrula): 0 hatalı dosya yok ve en az biri dolu-geçerli · 1 en az bir HATALI dosya · 2 dolu-geçerli dosya yok
(hepsi boş şablon ya da hiç dosya yok) · 3 kullanım.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass

AXET_HOME = Path(__file__).resolve().parents[1]
SETUP_CREDENTIALS = AXET_HOME / "skills-sap" / "sap-adt-foundation" / "scripts" / "setup_credentials.py"
SISTEMLER = ("DEV", "QA")
YER_TUTUCU = re.compile(r"^<[^<>]*>$")
# Kullanıcının doldurduğu alanlar; şablonda hepsi yer tutucuysa dosya "boş şablon" sayılır (atlanır).
DOLDURULACAK = ("ADT_SAP_URL", "ADT_SAP_USER", "ADT_SAP_PASSWORD", "ADT_SAP_CLIENT")


def _sc():
    spec = importlib.util.spec_from_file_location("_axet_setup_credentials", SETUP_CREDENTIALS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # yalnız tanımlar; main() çağrılmaz
    return mod


SC = _sc()
ANAHTARLAR = SC.ANAHTARLAR


def proje_bilgisi(proj: Path) -> tuple[str, str | None]:
    """(sistem adı öneki, master_language ya da None) — sap-project.json'dan; okunamazsa klasör adı / None."""
    try:
        veri = json.loads((proj / "sap-project.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        veri = {}
    ad = veri.get("project") if isinstance(veri, dict) else None
    ad = ad if isinstance(ad, str) and ad.strip() and not YER_TUTUCU.match(ad.strip()) else proj.name
    ad = re.sub(r"[^A-Za-z0-9_.-]", "_", ad.strip())[:36] or "PROJE"  # setup_credentials _AD: en çok 40
    ml = veri.get("master_language") if isinstance(veri, dict) else None
    ml = ml.strip().upper() if isinstance(ml, str) and re.fullmatch(r"[A-Za-z]{2}", ml.strip()) else None
    return ad, ml


def sablon(sistem: str, proj: Path) -> str:
    ad, ml = proje_bilgisi(proj)
    degerler = {"ADT_SAP_URL": "<https://sunucu:port>", "ADT_SAP_USER": "<kullanici>",
                "ADT_SAP_PASSWORD": "<parola>", "ADT_SAP_CLIENT": "<3 haneli client, ör. 100>",
                "ADT_SAP_LANGUAGE": ml or "<2 harf, ör. TR>", "ADT_SAP_SSL_VERIFY": "false",
                "ADT_SAP_TIER": sistem, "ADT_SAP_SYSTEM_NAME": f"{ad}_{sistem}"}
    assert tuple(degerler) == tuple(ANAHTARLAR), "şablon anahtarları setup_credentials.ANAHTARLAR ile aynı sırada olmalı"
    bas = [f"# SAP bağlantı şablonu — {sistem} sistemi. <...> yazan yerleri doldur (köşeli parantezleri de sil), kaydet.",
           "# Sonra proje klasöründeki KURULUMU-TAMAMLA.cmd'ye tekrar çift tıkla.",
           "# Bu dosya git'e girmez (.gitignore: conn/*). Parola burada DÜZ METİN durur: içeriği sohbete yapıştırma.",
           f"# {sistem} sistemi yoksa dosyaya dokunma: boş şablon yok sayılır."
           + (" Yazma yalnız DEV'de; QA/PRD salt-okunur." if sistem != "DEV" else "")]
    return "\n".join(bas + [f"{k}={v}" for k, v in degerler.items()]) + "\n"


def hazirla(proj: Path) -> int:
    conn = proj / "conn"
    try:
        conn.mkdir(exist_ok=True)
    except OSError as exc:
        print(f"  HATA: conn klasörü oluşturulamadı ({type(exc).__name__})")
        return 1
    rc = 0
    for sistem in SISTEMLER:
        f = conn / f"{sistem}.env"
        if f.exists():
            print(f"  [var, dokunulmadı] conn\\{f.name}")
            continue
        try:
            with open(f, "x", encoding="utf-8", newline="\r\n") as fh:  # x: var olanı asla ezme
                fh.write(sablon(sistem, proj))
            print(f"  [şablon yazıldı] conn\\{f.name}")
        except OSError as exc:
            print(f"  HATA: conn\\{f.name} yazılamadı ({type(exc).__name__})")
            rc = 1
    return rc


def oku(f: Path) -> dict[str, str]:
    d: dict[str, str] = {}
    for s in f.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if s.strip() and not s.lstrip().startswith("#") and "=" in s:
            k, v = s.split("=", 1)
            d[k.strip()] = v.strip()
    return d


def sinifla(f: Path) -> tuple[int, list[str]]:
    """(0 dolu-geçerli · 1 hatalı · 2 boş şablon, hata satırları). Satırlar DEĞER İÇERMEZ."""
    try:
        d = oku(f)
    except OSError as exc:
        return 1, [f"dosya okunamadı ({type(exc).__name__})"]
    if all(YER_TUTUCU.match(d.get(k, "<>")) for k in DOLDURULACAK):
        return 2, []
    hatalar = [f"{k}: doldurulmamış (<...> duruyor)" for k in ANAHTARLAR if YER_TUTUCU.match(d.get(k, ""))]
    hatalar += [f"{k}: eksik" for k in ANAHTARLAR if k not in d]
    isaretli = {h.split(":", 1)[0] for h in hatalar}  # aynı alan için kural satırını tekrarlama
    hatalar += [h for h in SC.dogrula(d) if h.split(":", 1)[0] not in isaretli]
    return (1, hatalar) if hatalar else (0, [])


def dogrula(proj: Path) -> int:
    dosyalar = sorted((proj / "conn").glob("*.env"))
    gecerli = hatali = 0
    for f in dosyalar:
        durum, hatalar = sinifla(f)
        if durum == 0:
            gecerli += 1
            print(f"  conn\\{f.name}: dolu, geçerli")
        elif durum == 2:
            print(f"  conn\\{f.name}: boş şablon, atlandı")
        else:
            hatali += 1
            print(f"  conn\\{f.name}: HATALI — düzelt:")
            for h in hatalar:
                print(f"      - {h}")
    if not dosyalar:
        print("  conn klasöründe .env dosyası yok")
    return 1 if hatali else (0 if gecerli else 2)


def _switch_tier():
    """switch_tier.py'nin ad/tier okuyucuları (kural kopyalanmaz). Kendi sapadt yolunu sys.path'e ekler."""
    spec = importlib.util.spec_from_file_location("_axet_switch_tier", SETUP_CREDENTIALS.parent / "switch_tier.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DURUM_ADI = {0: "gecerli", 1: "hatali", 2: "doldurulmamis"}


def sistemler(proj: Path) -> dict:
    """{'aktif': {system, tier} | None, 'systems': [{system, tier, file, durum}]} — yalnız ad + tier + durum; DEĞER YOK."""
    st = _switch_tier()
    aktif = proj / ".conn_adt"
    out = []
    for ad, yol, tier in st.registry(proj / "conn"):
        out.append({"system": ad, "tier": tier, "file": f"conn/{yol.name}", "durum": DURUM_ADI[sinifla(yol)[0]]})
    return {"aktif": {"system": st.name_of(aktif).upper(), "tier": st.tier_of(aktif)} if aktif.is_file() else None,
            "systems": out}


def ozet(proj: Path, as_json: bool) -> int:
    s = sistemler(proj)
    if as_json:
        print(json.dumps(s, ensure_ascii=False))
        return 0
    a = s["aktif"]
    print(f"  SAP sistemi: aktif {a['system'] + ' (' + a['tier'] + ')' if a else 'yok'}")
    for x in s["systems"]:
        etiket = {"gecerli": "", "hatali": "  [HATALI]", "doldurulmamis": "  [doldurulmamış]"}[x["durum"]]
        isaret = "*" if a and a["system"] == x["system"] else " "
        print(f"   {isaret} {x['system']} ({x['tier']}){etiket}")
    if not s["systems"]:
        print("    conn\\ içinde sistem yok")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="SAP bağlantı şablonları (conn/DEV.env, conn/QA.env): yaz / doğrula / özet")
    ap.add_argument("komut", choices=["hazirla", "dogrula", "ozet"])
    ap.add_argument("--project-dir", required=True)
    ap.add_argument("--json", action="store_true", help="ozet: tek JSON nesnesi (ad + tier + durum; değer yok)")
    try:
        ns = ap.parse_args(argv)
    except SystemExit:
        return 3
    proj = Path(ns.project_dir).resolve()
    if not proj.is_dir():
        print("  HATA: proje dizini yok")
        return 3
    if ns.komut == "ozet":
        return ozet(proj, ns.json)
    return hazirla(proj) if ns.komut == "hazirla" else dogrula(proj)


if __name__ == "__main__":
    sys.exit(main())
