#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`%testler` — template test takımlarını güncellemeden AYRI, kullanıcı isteğiyle koşar (Z162).

Güncelleme (`%guncelle`) hiçbir koşulda uzun test takımı koşmaz: CI'nın kefil olamadığı ağaçta
etkilenen takımları `.axet-guncelleme/test-borcu.json`a yazar. Bu araç o borcu öder:

    python scripts/testler.py              # test borcundaki takımlar (borç yoksa "borç yok", çıkış 0)
    python scripts/testler.py --takim kok  # adı ya da komutu verilen takım (tekrarlanabilir)
    python scripts/testler.py --hepsi      # haritadaki bütün takımlar (uzun sürer; tahmin önce basılır)
    python scripts/testler.py --liste      # takımlar + son ölçülen süre + borçta mı

Koşum düşük öncelikte (Windows: BelowNormal) ve repo DIŞI geçici dizinle yapılır. Sonuç
`.axet-guncelleme/test-raporu.md` + `.json`a yazılır. Her kırmızı takım için hangi dosyadan /
yayın kaleminden geldiği ve dört giderme seçeneği basılır: ① `guncelle.py geri-al <yol>`
② yerel değişikliği bırak, yayın sürümünü al ③ `kur.cmd -Sifirla` ④ `%hata-bildir`.
Araç hiçbir dosyayı DÜZELTMEZ ve hiçbir seçeneği kendisi uygulamaz — seçim kullanıcınındır.

Borç: geçen takım borçtan düşer (filtresiz eşi geçen `-k` takımı da); kırmızı ya da ÖLÇÜLEMEDİ
kalan takım borçta kalır. Borç boşalınca dosya silinir.

Çıkış: 0 koşulan her takım yeşil (ya da borç yok) · 1 en az bir kırmızı / ÖLÇÜLEMEDİ ·
2 kullanım hatası (hiçbir şey koşmadı).

KAPSAM — bakılanlar: `guncelle/harita.json`'daki template test komutları. Bakılmayanlar:
kullanıcının kendi skill'leri/dosyaları (haritada test komutu yok) · canlı SAP · aXet'in kendisi.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

BURASI = Path(__file__).resolve().parent
sys.path.insert(0, str(BURASI))
import guncelle as g  # noqa: E402  (takım adı/ayıklama/harita eşleşmesi TEK kaynakta)

# Kullanıcı isteğiyle koşan tam takım uzun sürebilir: CI'da gözlenen en uzun kök koşumu 2411 sn
# (tek işlem, 2026-09-20) ⇒ ~2x pay. Aşım çökme değil, ÖLÇÜLEMEDİ hükmüdür.
TAKIM_ZAMAN_ASIMI = 5400
RAPOR_MD = "test-raporu.md"
RAPOR_JSON = "test-raporu.json"
SURE_DOSYASI = "test-sureleri.json"
_FAILURE = re.compile(r"(\d+)\s*failure", re.I)
_KIRMIZI_TEST = re.compile(r"^(FAIL|ERROR): (\S+) \(([^)]+)\)", re.M)


def _oku_json(yol: Path, varsayilan):
    try:
        return json.loads(yol.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return varsayilan


def tum_takimlar(harita: dict) -> list[dict]:
    """Haritadaki bütün test komutları (ayıklanmamış) — `kaynak_siniflar` ile."""
    out: dict[tuple[str, str], dict] = {}
    for s in harita.get("siniflar", []):
        for t in s.get("test", []):
            anahtar = (t.get("cwd", "."), t["komut"])
            k = out.setdefault(anahtar, {"ad": g.takim_adi(t["komut"]), "komut": t["komut"],
                                         "cwd": t.get("cwd", "."), "kaynak_yollar": [],
                                         "kaynak_siniflar": []})
            if s["sinif"] not in k["kaynak_siniflar"]:
                k["kaynak_siniflar"].append(s["sinif"])
    return sorted(out.values(), key=lambda t: t["ad"])


def sure_tahmini(takim: dict, sureler: dict, kok: Path) -> tuple[float | None, str]:
    """(saniye, kaynak). Önce bu makinedeki son koşum; yoksa kök takım için CI küme ağırlıkları."""
    son = sureler.get(f"{takim['cwd']}::{takim['komut']}")
    if isinstance(son, (int, float)):
        return float(son), "son koşum"
    if takim["ad"].split(":")[0] == "kok":
        agirlik = _oku_json(kok / "tests" / "parca-agirlik.json", {}).get("kume_sn") or {}
        filtre = takim["ad"].split(":", 1)[1] if ":" in takim["ad"] else None
        kumeler = [v for k, v in agirlik.items()
                   if isinstance(v, (int, float)) and (filtre is None or filtre in k)]
        if kumeler:
            # `tests/run_tests.py` kümeleri min(cpu, 8, küme) işle paralel koşar (run_tests.py
            # `_is_sayisi`): duvar süresi ≈ toplam ÷ iş, ama en uzun kümeden kısa olamaz.
            is_sayisi = max(1, min(os.cpu_count() or 1, 8, len(kumeler)))
            return (float(max(sum(kumeler) / is_sayisi, max(kumeler))),
                    f"CI küme ağırlığı ÷ {is_sayisi} paralel iş")
    return None, "BİLİNMİYOR"


def _dk(sn: float | None) -> str:
    return "?" if sn is None else (f"{sn:.0f} sn" if sn < 90 else f"~{sn / 60:.0f} dk")


def _oncelik_bayraklari() -> dict:
    if os.name == "nt":
        return {"creationflags": getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)}
    return {"preexec_fn": lambda: os.nice(5)}  # noqa: PLW1509 — yalnız POSIX


def takim_kos(kok: Path, takim: dict, env: dict) -> dict:
    """Tek takımı koşar. Döner: sonuç kaydı (cikis None = ÖLÇÜLEMEDİ — 'temiz' DEĞİL)."""
    kimlik = f"{takim['cwd']}::{takim['komut']}"
    calisma = (kok / takim["cwd"]).resolve()
    sonuc = {"ad": takim["ad"], "komut": takim["komut"], "cwd": takim["cwd"], "kimlik": kimlik,
             "kaynak_yollar": takim.get("kaynak_yollar") or [], "cikis": None,
             "failure": None, "kirmizi_testler": [], "sure_sn": None}
    if not calisma.is_dir():
        sonuc["not"] = "ÖLÇÜLEMEDİ — cwd yok ('temiz' DEĞİL)"
        return sonuc
    parcalar = g._komutu_coz(takim["komut"])
    betik = g._betik_yolu(parcalar)
    if betik is not None and not (calisma / betik).exists():
        sonuc["not"] = f"ÖLÇÜLEMEDİ — {betik} yok ('temiz' DEĞİL)"
        return sonuc
    bas = time.monotonic()
    try:
        r = subprocess.run(parcalar, cwd=str(calisma), env=env, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL,
                           timeout=TAKIM_ZAMAN_ASIMI, **_oncelik_bayraklari())
    except subprocess.TimeoutExpired:
        sonuc["sure_sn"] = round(time.monotonic() - bas, 1)
        sonuc["not"] = f"ÖLÇÜLEMEDİ — {TAKIM_ZAMAN_ASIMI} sn zaman aşımı ('temiz' DEĞİL)"
        return sonuc
    cikti = (r.stdout or "") + (r.stderr or "")
    m = _FAILURE.search(cikti)
    sonuc.update({
        "cikis": r.returncode, "sure_sn": round(time.monotonic() - bas, 1),
        "failure": int(m.group(1)) if m else None,
        "kirmizi_testler": sorted({f"{a.group(2)} ({a.group(3)})"
                                   for a in _KIRMIZI_TEST.finditer(cikti)})[:50],
        "cikti_sonu": cikti[-4000:] if r.returncode != 0 else "",
    })
    return sonuc


def _kalem_bul(plan: dict, yol: str) -> str | None:
    for kalem in plan.get("kalemler", []):
        for d in kalem.get("dosyalar", []):
            if yol in (d.get("yol"), d.get("yeni_yol")):
                return kalem.get("id")
    return None


def giderme_satirlari(kok: Path, sonuc: dict, plan: dict, borc: dict | None) -> list[str]:
    """Kırmızı takım için: kaynak dosya/kalem + dört seçenek. Hiçbirini UYGULAMAZ."""
    k = kok.as_posix()
    etiket = (borc or {}).get("etiket") or plan.get("yeni_etiket")
    satirlar = []
    yollar = sonuc.get("kaynak_yollar") or []
    if yollar:
        for y in yollar[:10]:
            kalem = _kalem_bul(plan, y)
            satirlar.append(f"  - kaynak: `{y}`" + (f" (yayın kalemi {kalem})" if kalem
                                                     else " (yerel değişiklik / plan dışı)"))
    else:
        satirlar.append("  - kaynak: bilinmiyor (takım borçtan değil, doğrudan koşuldu)")
    ornek = yollar[0] if yollar else "<yol>"
    satirlar += [
        "  Seçenekler (kullanıcı seçer; araç hiçbirini kendisi uygulamaz):",
        f"  ① dosyayı güncelleme öncesine al: `python \"{k}/scripts/guncelle.py\" --klon \"{k}\" geri-al {ornek}`",
        (f"  ② yerel değişikliği bırak, yayın sürümünü al: `git -C \"{k}\" checkout {etiket} -- {ornek}`"
         if etiket else "  ② yerel değişikliği bırak, yayın sürümünü al: yayın etiketi bilinmiyor — ③'ü kullan"),
        f"  ③ klonu yayına sıfırla (yerel değişikliklerin tümü gider): `\"{k}/kur.cmd\" -Sifirla`",
        f"  ④ hatayı bildir (rapor ekli): `%hata-bildir` — `{k}/{g.DURUM_DIZIN_ADI}/{RAPOR_MD}`",
        "  Seçimden sonra aynı takımı yeniden koş: "
        f"`python \"{k}/scripts/testler.py\" --takim {sonuc['ad']}`",
    ]
    return satirlar


def borcu_guncelle(durum: Path, borc: dict | None, sonuclar: list[dict], hepsi: bool) -> dict | None:
    """Geçen takımı borçtan düşür; kırmızı/ölçülemeyeni ekle/koru. Boşsa dosyayı sil."""
    gecen = {(s["cwd"], tuple(s["komut"].split())) for s in sonuclar if s["cikis"] == 0}
    kalan = []
    for t in (borc or {}).get("takimlar") or []:
        anahtar = (t.get("cwd", "."), tuple(t["komut"].split()))
        taban = g._taban_argv(t["komut"])
        if anahtar in gecen or (taban is not None and (t.get("cwd", "."), taban) in gecen):
            continue
        kalan.append(t)
    mevcut = {(t.get("cwd", "."), t["komut"]) for t in kalan}
    for s in sonuclar:
        if s["cikis"] != 0 and (s["cwd"], s["komut"]) not in mevcut:
            kalan.append({"ad": s["ad"], "komut": s["komut"], "cwd": s["cwd"],
                          "kaynak_yollar": s.get("kaynak_yollar") or []})
    yol = durum / g.TEST_BORCU_DOSYASI
    if hepsi and all(s["cikis"] == 0 for s in sonuclar):
        kalan = []
    if not kalan:
        yol.unlink(missing_ok=True)
        return None
    yeni = dict(borc or {"surum": g.TEST_BORCU_SURUMU, "ilk_kayit": g._simdi(),
                         "neden": "`%testler` koşumunda kırmızı/ölçülemedi"})
    yeni.pop("bozuk", None)
    yeni.update({"zaman": g._simdi(), "takimlar": kalan})
    yeni.setdefault("kapsam_disi", "Kırmızı ya da ÖLÇÜLEMEDİ takımlar borçta kalır; "
                                   "`%testler` yeşil verene dek doctor WARN basar.")
    durum.mkdir(parents=True, exist_ok=True)
    yol.write_text(json.dumps(yeni, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return yeni


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass
    ap = argparse.ArgumentParser(prog="testler.py",
                                 description="template test takımlarını isteğe bağlı koşar (Z162)")
    ap.add_argument("--klon", type=Path, default=BURASI.parent, help="klon kökü (varsayılan: bu betiğin kökü)")
    ap.add_argument("--takim", action="append", default=[], metavar="AD",
                    help="takım adı ya da komutu (tekrarlanabilir; adlar: --liste)")
    ap.add_argument("--hepsi", action="store_true", help="haritadaki bütün takımlar")
    ap.add_argument("--liste", action="store_true", help="takımları listele, koşma")
    args = ap.parse_args(argv)
    if args.hepsi and args.takim:
        print("KULLANIM: --hepsi ile --takim birlikte verilmez.", file=sys.stderr)
        return 2

    kok = args.klon.resolve()
    durum = kok / g.DURUM_DIZIN_ADI
    harita_yolu = kok / "guncelle" / "harita.json"
    if not harita_yolu.is_file():
        print(f"KULLANIM: harita yok: {harita_yolu} (klon kökü doğru mu?)", file=sys.stderr)
        return 2
    harita = json.loads(harita_yolu.read_text(encoding="utf-8"))
    tumu = tum_takimlar(harita)
    sureler = _oku_json(durum / SURE_DOSYASI, {})
    borc_ham = _oku_json(durum / g.TEST_BORCU_DOSYASI, None) if (durum / g.TEST_BORCU_DOSYASI).exists() else None
    if (durum / g.TEST_BORCU_DOSYASI).exists() and not isinstance(borc_ham, dict):
        print(f"UYARI: {g.TEST_BORCU_DOSYASI} okunamadı — borç ÖLÇÜLEMEDİ; `--hepsi` ile tümünü koş.")
        borc_ham = {"bozuk": True, "takimlar": []}
    borc = borc_ham
    borcta = {(t.get("cwd", "."), t["komut"]) for t in (borc or {}).get("takimlar") or []}

    if args.liste:
        print(f"{'TAKIM':28} {'SON SÜRE / TAHMİN':44} BORÇ  KOMUT")
        for t in tumu:
            sn, kaynak = sure_tahmini(t, sureler, kok)
            print(f"{t['ad']:28} {_dk(sn) + ' (' + kaynak.split(' (')[0] + ')':44} "
                  f"{'evet' if (t['cwd'], t['komut']) in borcta else '—':5} {t['komut']}")
        print(f"\nBorç: {len(borcta)} takım" + ("" if borcta else " (yok)"))
        return 0

    if args.hepsi:
        secim = g._takimlari_ayikla([dict(t) for t in tumu])
    elif args.takim:
        secim, bilinmeyen = [], []
        for ad in args.takim:
            eslesen = [t for t in tumu if ad in (t["ad"], t["komut"])]
            if not eslesen:
                bilinmeyen.append(ad)
            for t in eslesen:
                if t not in secim:
                    secim.append(dict(t))
        if bilinmeyen:
            print(f"KULLANIM: bilinmeyen takım: {', '.join(bilinmeyen)} — adlar için `--liste`.",
                  file=sys.stderr)
            return 2
        for t in secim:  # borçtaki kaynak yolları taşı (giderme önerisi için)
            for b in (borc or {}).get("takimlar") or []:
                if (b.get("cwd", "."), b["komut"]) == (t["cwd"], t["komut"]):
                    t["kaynak_yollar"] = b.get("kaynak_yollar") or []
    else:
        if borc is None:
            print("TEST BORCU: yok — koşulacak takım yok. (Tümü için `--hepsi`, liste için `--liste`.)")
            return 0
        if borc.get("bozuk"):
            print("TEST BORCU: ÖLÇÜLEMEDİ — kayıt okunamadı; `--hepsi` ile tüm takımları koş.",
                  file=sys.stderr)
            return 1
        secim = [dict(t) for t in borc.get("takimlar") or []]
        if not secim:
            (durum / g.TEST_BORCU_DOSYASI).unlink(missing_ok=True)
            print("TEST BORCU: kayıt boştu, silindi.")
            return 0

    toplam = [sure_tahmini(t, sureler, kok)[0] for t in secim]
    bilinen = sum(x for x in toplam if x is not None)
    print(f"TESTLER — {len(secim)} takım koşulacak (düşük öncelik). Tahmini süre: "
          + (_dk(bilinen) if bilinen else "BİLİNMİYOR")
          + (f" + {sum(1 for x in toplam if x is None)} takım süresi bilinmiyor"
             if any(x is None for x in toplam) and bilinen else ""))

    env, tmp = g._izole_tmp(None)
    sonuclar = []
    try:
        for i, t in enumerate(secim, 1):
            sn, _ = sure_tahmini(t, sureler, kok)
            print(f"[{i}/{len(secim)}] {t['ad']} — `{t['komut']}` (tahmin {_dk(sn)}) …", flush=True)
            s = takim_kos(kok, t, env)
            sonuclar.append(s)
            if s["cikis"] is None:
                print(f"  [ ? ] ÖLÇÜLEMEDİ — {s.get('not')}")
            else:
                print(f"  [{'OK ' if s['cikis'] == 0 else 'RED'}] rc={s['cikis']} · {_dk(s['sure_sn'])}"
                      + (f" · {s['failure']} failure" if s["failure"] else ""))
                sureler[s["kimlik"]] = s["sure_sn"]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    durum.mkdir(parents=True, exist_ok=True)
    (durum / SURE_DOSYASI).write_text(json.dumps(sureler, ensure_ascii=False, indent=1) + "\n",
                                      encoding="utf-8")
    plan = _oku_json(durum / "plan.json", {})
    bozuk = bool((borc or {}).get("bozuk"))
    if bozuk and not args.hepsi:
        # Okunamayan kayıttaki takımlar bilinmiyor ⇒ tek takımın yeşili onu KAPATAMAZ; kayıt
        # yalnız `--hepsi` ile kapanır (silinmesi "borç yok" demek olurdu — ölçülemedi ≠ temiz).
        yeni_borc = borc
    else:
        yeni_borc = borcu_guncelle(durum, None if bozuk else borc, sonuclar, args.hepsi)

    kirmizi = [s for s in sonuclar if s["cikis"] not in (0, None)]
    olculemedi = [s for s in sonuclar if s["cikis"] is None]
    rapor = [f"# Test raporu — {g._simdi()}", "",
             f"Koşulan: {len(sonuclar)} · yeşil: {len(sonuclar) - len(kirmizi) - len(olculemedi)} · "
             f"kırmızı: {len(kirmizi)} · ÖLÇÜLEMEDİ: {len(olculemedi)}", ""]
    for s in sonuclar:
        durum_ad = "ÖLÇÜLEMEDİ" if s["cikis"] is None else ("PASS" if s["cikis"] == 0 else "FAIL")
        rapor.append(f"- [{durum_ad}] {s['ad']} — `{s['komut']}` · {_dk(s['sure_sn'])}"
                     + (f" · {s.get('not')}" if s.get("not") else ""))
    if kirmizi or olculemedi:
        rapor += ["", "## Giderme"]
        for s in kirmizi + olculemedi:
            rapor += ["", f"### {s['ad']} ({'ÖLÇÜLEMEDİ' if s['cikis'] is None else 'FAIL'})"]
            rapor += [f"  - kırmızı test: {x}" for x in s["kirmizi_testler"][:15]]
            rapor += giderme_satirlari(kok, s, plan, borc)
    if yeni_borc and yeni_borc.get("bozuk"):
        borc_satiri = ("ÖLÇÜLEMEDİ — borç kaydı okunamadı, olduğu gibi KALDI; yalnız `--hepsi` "
                       "yeşil verince kapanır")
    elif yeni_borc:
        borc_satiri = (f"{len(yeni_borc['takimlar'])} takım borçta kalıyor: "
                       + ", ".join(t["ad"] for t in yeni_borc["takimlar"]))
    else:
        borc_satiri = "kapandı (borç yok)"
    rapor += ["", "## Test borcu", borc_satiri,
              "", "KAPSAM — bakılanlar: seçilen template test takımlarının çıkış kodu ve "
                  "`failure` sayısı. Bakılmayanlar: kullanıcının kendi skill/dosyaları · canlı SAP · "
                  "kırmızının KÖK NEDENİ (araç teşhis etmez, kaynağını ve seçenekleri gösterir)."]
    (durum / RAPOR_MD).write_text("\n".join(rapor) + "\n", encoding="utf-8")
    (durum / RAPOR_JSON).write_text(json.dumps({"zaman": g._simdi(), "sonuclar": sonuclar,
                                                "borc_kalan": (yeni_borc or {}).get("takimlar", [])},
                                               ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("\n" + "\n".join(rapor))
    return 1 if (kirmizi or olculemedi) else 0


if __name__ == "__main__":
    raise SystemExit(main())
