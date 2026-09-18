#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PR birlestirme yardimcisi — CI'yi KENDI dogrular, sonra squash-merge eder.

    python scripts/merge_pr.py --repo <ORG>/<REPO> --pr <N> [--squash] [--admin] [--deneme]

NEDEN VAR: `gh pr merge --admin` kirmizi CI'yi de SESSIZCE birlestirir ve merge GERI
ALINAMAZ. Bu arac, birlestirmeden once statusCheckRollup'i okur; bekleyen ya da basarisiz
kontrol varsa DURUR. `--admin` yalnizca "onaylayan yok" sartini asmak icindir — CI'yi
atlatmak icin DEGIL, ve bu arac onu atlatmaya izin vermez.

IKI YOL (--yol oto|gh|rest): `gh` kuruluysa onu kullanir, degilse ayni fail-closed
dogrulamayi GitHub REST ucundan yapar (token: `git credential fill`). Gerekce olculdu
(2026-09-16): bu makinede `gh` kurulu degildi ve arac tamamen kullanilamaz durumdaydi;
dort PR el yordamiyla ayni disiplinle birlestirildi. Tuketiciye `gh` kurma yuku binmesin.

KAPSAM BEYANI — bu arac NEYE BAKMAZ:
  * PR icerigi: diff'i okumaz, inceleme yapmaz (bug gate'in isi).
  * Dal korumasi kurallari: GitHub'in kendi kurallarini sorgulamaz; yalnizca kontrol
    sonuclarina bakar. Koruma yanlis yapilandirilmissa bunu GORMEZ.
  * Merge sonrasi durum: birlestirmeden sonra dalin silinip silinmedigini denetlemez.
  * Hic kontrol TANIMLANMAMIS bir repoda "0 kontrol" cikar — bu arac bunu BOSLUK sayar
    ve durur (bkz. --kontrolsuz-devam).
  * REST yolunda `--admin` KARSILIGI YOKTUR: REST ucu boyle bir bayrak tanimaz. Bayrak
    verilirse arac bunu yazar ve yok sayar; koruma engellerse GitHub 405 doner.

Cikis: 0 birlestirildi (ya da --deneme ile dogrulandi) · 1 durduruldu · 2 kullanim hatasi.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

BEKLEYEN = {"PENDING", "QUEUED", "IN_PROGRESS", "WAITING", "REQUESTED", "EXPECTED", ""}
BASARILI = {"SUCCESS", "NEUTRAL", "SKIPPED"}
GH_API = "https://api.github.com"


def gh(args: list[str]) -> tuple[int, str, str]:
    p = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or ""), (p.stderr or "")


def gh_var() -> bool:
    return shutil.which("gh") is not None


def rest_rollup(check_runs: list[dict] | None, statuses: list[dict] | None) -> list[dict]:
    """REST'in iki ucunu gh'nin statusCheckRollup bicimine cevirir (saf fonksiyon).

    `/commits/<sha>/check-runs` -> CheckRun bicimi (name + status + conclusion)
    `/commits/<sha>/status`     -> StatusContext bicimi (context + state)

    ⛔ TUZAK (olculdu 2026-09-16, ozgurylmz34/axet): legacy status ucunun TOPLU `state`
    alani, repoda HIC legacy status yokken bile "pending" doner (`total_count` 0 iken
    bile). O toplu alan KULLANILMAZ — yalnizca `statuses` dizisindeki TEKIL kayitlar
    cevrilir. Aksi halde yalniz check-run kullanan bir repo sonsuza dek "bekleyen
    kontrol var" der ve arac hicbir zaman birlestirmez (sessiz kilitlenme).
    """
    rollup: list[dict] = []
    for c in check_runs or []:
        rollup.append({"name": c.get("name"), "status": c.get("status"), "conclusion": c.get("conclusion")})
    for s in statuses or []:
        rollup.append({"context": s.get("context"), "state": s.get("state")})
    return rollup


def rest_mergeable(pr: dict) -> str:
    """REST'in `mergeable`/`mergeable_state` ikilisini gh'nin sozlugune cevirir.

    `mergeable` GitHub tarafinda ASENKRON hesaplanir ve ilk okumada None olabilir —
    None "birlestirilebilir" DEMEK DEGILDIR, "henuz olculmedi" demektir (UNKNOWN).
    """
    if pr.get("mergeable") is False or pr.get("mergeable_state") == "dirty":
        return "CONFLICTING"
    if pr.get("mergeable") is True:
        return "MERGEABLE"
    return "UNKNOWN"


def rest_token() -> str:
    """GitHub token'ini git'in kimlik yardimcisindan okur. Bulunamazsa bos dizge."""
    p = subprocess.run(["git", "credential", "fill"],
                       input="protocol=https\nhost=github.com\n\n",
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    for satir in (p.stdout or "").splitlines():
        if satir.startswith("password="):
            return satir.split("=", 1)[1].strip()
    return ""


def rest_api(token: str, yol: str, govde: dict | None = None, yontem: str = "GET") -> dict:
    veri = json.dumps(govde).encode("utf-8") if govde is not None else None
    r = urllib.request.Request(f"{GH_API}/{yol}", data=veri, method=yontem,
                               headers={"Authorization": f"Bearer {token}",
                                        "Accept": "application/vnd.github+json",
                                        "Content-Type": "application/json",
                                        "User-Agent": "axet-merge-pr"})
    with urllib.request.urlopen(r, timeout=30) as f:
        metin = f.read().decode("utf-8")
    return json.loads(metin) if metin.strip() else {}


def rest_pr_oku(token: str, repo: str, pr_no: str) -> dict:
    """PR'i REST'ten okur ve gh `pr view --json ...` ciktisiyla AYNI sekle cevirir.

    Boylece asagidaki karar mantigi (kontrol_ozeti + esikler) TEK kod yolu kalir;
    iki backend ayri kurallara gore hukum veremez.
    """
    pr = rest_api(token, f"repos/{repo}/pulls/{pr_no}")
    for _ in range(5):  # mergeable asenkron hesaplanir
        if pr.get("mergeable") is not None:
            break
        time.sleep(3)
        pr = rest_api(token, f"repos/{repo}/pulls/{pr_no}")
    sha = (pr.get("head") or {}).get("sha") or ""
    cr = rest_api(token, f"repos/{repo}/commits/{sha}/check-runs") if sha else {}
    st = rest_api(token, f"repos/{repo}/commits/{sha}/status") if sha else {}
    return {
        "number": pr.get("number"),
        "title": pr.get("title"),
        "state": (pr.get("state") or "").upper(),
        "isDraft": bool(pr.get("draft")),
        "mergeable": rest_mergeable(pr),
        "statusCheckRollup": rest_rollup(cr.get("check_runs"), st.get("statuses")),
        "headSha": sha,
    }


def kontrol_ozeti(rollup: list[dict]) -> tuple[list[str], list[str], list[str]]:
    """statusCheckRollup -> (basarili, bekleyen, basarisiz) ad listeleri.

    Iki bicim vardir: CheckRun (`status` + `conclusion`) ve StatusContext (`state`).
    Ikisi de karsilanir; taninmayan bicim BASARISIZ sayilir (fail-closed) — cunku
    "taninmadi" ile "gecti" ayni sey degildir.
    """
    ok: list[str] = []
    bekleyen: list[str] = []
    kotu: list[str] = []
    for c in rollup or []:
        ad = c.get("name") or c.get("context") or "<adsiz>"
        if "conclusion" in c or "status" in c:
            durum = (c.get("status") or "").upper()
            sonuc = (c.get("conclusion") or "").upper()
            if durum and durum != "COMPLETED":
                bekleyen.append(ad)
            elif sonuc in BASARILI:
                ok.append(ad)
            else:
                kotu.append(f"{ad} ({sonuc or 'sonucsuz'})")
        elif "state" in c:
            st = (c.get("state") or "").upper()
            if st in BEKLEYEN:
                bekleyen.append(ad)
            elif st in BASARILI:
                ok.append(ad)
            else:
                kotu.append(f"{ad} ({st})")
        else:
            kotu.append(f"{ad} (taninmayan kontrol bicimi)")
    return ok, bekleyen, kotu


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="CI'yi dogrulayip PR birlestirir")
    ap.add_argument("--repo", required=True, help="<ORG>/<REPO> — ZORUNLU (cwd'den tahmin YOK)")
    ap.add_argument("--pr", required=True, help="PR numarasi")
    ap.add_argument("--squash", action="store_true", default=True, help="squash merge (varsayilan)")
    ap.add_argument("--merge", action="store_true", help="squash yerine duz merge")
    ap.add_argument("--admin", action="store_true", help="yalnizca 'onaylayan yok' sartini asar")
    ap.add_argument("--deneme", action="store_true", help="yalnizca dogrula, BIRLESTIRME")
    ap.add_argument("--kontrolsuz-devam", action="store_true",
                    help="repoda hic kontrol tanimli degilse yine de birlestir (bilincli)")
    ap.add_argument("--yol", choices=("oto", "gh", "rest"), default="oto",
                    help="backend: oto (gh varsa gh, yoksa rest) · gh · rest")
    a = ap.parse_args(argv)

    if "/" not in a.repo:
        print("HATA: --repo <ORG>/<REPO> bicimindedir.", file=sys.stderr)
        return 2

    yol = a.yol
    if yol == "oto":
        yol = "gh" if gh_var() else "rest"
    if yol == "gh" and not gh_var():
        print("HATA: --yol gh istendi ama `gh` PATH'te bulunamadi.", file=sys.stderr)
        return 2

    token = ""
    if yol == "rest":
        token = rest_token()
        if not token:
            print("HATA: GitHub token'i alinamadi (`git credential fill` parola dondurmedi). "
                  "Once bir kez `git push`/`git fetch` ile kimlik dogrula ya da `gh` kur.", file=sys.stderr)
            return 2

    print(f"Backend: {yol}")
    if yol == "gh":
        rc, out, err = gh(["pr", "view", a.pr, "--repo", a.repo,
                           "--json", "number,title,state,isDraft,mergeable,statusCheckRollup"])
        if rc != 0:
            print(f"HATA: PR okunamadi — {err.strip()}", file=sys.stderr)
            return 1
        pr = json.loads(out)
    else:
        try:
            pr = rest_pr_oku(token, a.repo, a.pr)
        except urllib.error.HTTPError as e:
            print(f"HATA: PR okunamadi — HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}",
                  file=sys.stderr)
            return 1
        except OSError as e:
            print(f"HATA: PR okunamadi — {e}", file=sys.stderr)
            return 1

    print(f"PR #{pr.get('number')} — {pr.get('title')}")
    if pr.get("state") != "OPEN":
        print(f"DURDU: PR durumu {pr.get('state')} (acik degil).")
        return 1
    if pr.get("isDraft"):
        print("DURDU: PR taslak (draft).")
        return 1

    ok, bekleyen, kotu = kontrol_ozeti(pr.get("statusCheckRollup") or [])
    print(f"Kontroller: {len(ok)} basarili · {len(bekleyen)} bekleyen · {len(kotu)} basarisiz")
    for ad in kotu:
        print(f"  BASARISIZ: {ad}")
    for ad in bekleyen:
        print(f"  BEKLIYOR:  {ad}")

    if kotu:
        print("DURDU: basarisiz kontrol var. --admin bunu ASMAZ (bilincli).")
        return 1
    if bekleyen:
        print("DURDU: bekleyen kontrol var; bitmesini bekle.")
        return 1
    if not ok and not a.kontrolsuz_devam:
        print("DURDU: repoda hic kontrol tanimli degil — '0 kontrol' YESIL DEGILDIR. "
              "Bilincliyse --kontrolsuz-devam ver.")
        return 1

    mergeable = pr.get("mergeable")
    if mergeable == "CONFLICTING":
        print("DURDU: PR CONFLICTING — once dali main uzerine guncelle.")
        return 1
    if mergeable != "MERGEABLE":
        print(f"NOT: mergeable = {mergeable!r} (OLCULEMEDI sayiliyor; gh yine de reddedebilir).")

    if a.deneme:
        print("DENEME: dogrulama gecti, birlestirilmedi.")
        return 0

    if yol == "gh":
        komut = ["pr", "merge", a.pr, "--repo", a.repo, "--merge" if a.merge else "--squash"]
        if a.admin:
            komut.append("--admin")
        rc, out, err = gh(komut)
        print(out.strip() or err.strip())
        if rc != 0:
            print("DURDU: birlestirme basarisiz.", file=sys.stderr)
            return 1
        print("Birlestirildi.")
        return 0

    if a.admin:
        print("NOT: --admin REST yolunda KARSILIKSIZ (REST ucu boyle bir bayrak tanimaz); yok sayiliyor.")
    govde = {"merge_method": "merge" if a.merge else "squash"}
    # Yukarida dogrulanan SHA merge istegine KOYULUR: dogrulama ile birlestirme arasinda
    # dala yeni bir commit gelirse GitHub 409 ile reddeder. Yesili olculen sey ile
    # birlestirilen seyin ayni oldugu boylece ARACIN KENDISI tarafindan garanti edilir
    # (gh yolunda boyle bir kilit yok).
    if pr.get("headSha"):
        govde["sha"] = pr["headSha"]
    try:
        s = rest_api(token, f"repos/{a.repo}/pulls/{a.pr}/merge", govde, "PUT")
    except urllib.error.HTTPError as e:
        govde_metin = e.read().decode("utf-8", "replace")[:300]
        if e.code == 409:
            print(f"DURDU: HTTP 409 — dogrulamadan sonra dal DEGISTI ya da birlestirilemedi. {govde_metin}",
                  file=sys.stderr)
        elif e.code == 405:
            print(f"DURDU: HTTP 405 — GitHub birlestirmeye izin vermedi (dal korumasi?). {govde_metin}",
                  file=sys.stderr)
        else:
            print(f"DURDU: birlestirme basarisiz — HTTP {e.code}: {govde_metin}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"DURDU: birlestirme basarisiz — {e}", file=sys.stderr)
        return 1
    if not s.get("merged"):
        print(f"DURDU: birlestirilmedi — {s.get('message') or s}", file=sys.stderr)
        return 1
    print(f"{s.get('message') or 'Birlestirildi.'} sha={(s.get('sha') or '')[:7]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
