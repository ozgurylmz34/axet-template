#!/usr/bin/env python3
"""Proje pre-commit denetimi — `.githooks/pre-commit` çağırır (`git config core.hooksPath .githooks`).

aXet'te hook yok: düzenleme anındaki denetimler burada commit anında koşar. YALNIZ staged içerik ve yollar
taranır (`git show :yol`); çalışma ağacındaki kirlilik sonucu değiştirmez (tek istisna WARN'dır: stage'lenmemiş
`.rules.md` değişikliği — adlandırma denetimi kuralları diskten okur).

Kontroller (FAIL → commit ENGELLENİR):
  1. Kimlik dosyası: `.conn*` (`*.example` hariç) · kökte `conn/` altı (`*.example`, `README.md` hariç) ·
     `*.env` ve `.env.*` (`*.example` hariç) · `secrets/` altı · SAML çerez / CSRF dosyaları.
  2. Staged içerikte açık sır deseni: özel anahtar, bilinen token biçimleri, URL içinde parola,
     tırnaklı parola/sır ataması, yapılandırma dosyasında `…PASSWORD=değer`. Yer tutucular (`<…>`, `${…}`) serbest.
  3. Paket adlandırma (SAP projesi): staged obje dosyaları `.rules.md` Naming regex'leri (check_package_naming.py).
     + WARN (engellemez): staged `.rules.md` Naming tablosu / istisna listesi HEAD'e göre değiştiyse
       (ilk kez eklenen `.rules.md` hariç; yeniden adlandırılanın kaynağıyla karşılaştırılır) — eski → yeni
       satırlar gösterilir. Diskte stage'lenmemiş değişikliği olan `.rules.md` de WARN alır.
  4. `validators-local/*.py` (varsa): exit 0 geçer · 1 engeller · başka çıkış/zaman aşımı da engeller (koşmadı ≠ temiz).
  5. SAP kaynak incelemesi, çevrimdışı (SAP projesi): staged `.clas.abap` · `.ddls.asddls`/`.cds` · `.bdef` ·
     `.srvd` · `.tabl.*` dosyası yazma kapısının kullandığı reviewer zincirinden (sap-adt-foundation `run_review`)
     geçer. SAP'ye ya da ağa bağlanan gate'ler çalıştırılmaz (WARN olarak listelenir); BLOCKER bulgu engeller.

Kaçış yok. Yanlış alarmda kullanıcı KENDİ terminalinde `git commit --no-verify` kullanır (aXet oturumu bu komutu
çalıştıramaz — izin kuralı). Git sorgusu çökerse denetim "temiz" SAYILMAZ: commit engellenir.

Kullanım:
  python <TEMPLATE>/scripts/project_precommit.py [--project-dir DİZİN]
Çıkış kodu: 0 geçti · 1 commit engellendi.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPTS = Path(__file__).resolve().parent
AXET_HOME = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))
FOUNDATION_SCRIPTS = AXET_HOME / "skills-sap" / "sap-adt-foundation" / "scripts"
RUN_REVIEW = FOUNDATION_SCRIPTS / "sapadt" / "lib" / "validators" / "run_review.py"
VALIDATORS_LOCAL = "validators-local"
YEREL_ZAMAN_ASIMI = 120
ICERIK_AZAMI_BAYT = 5 * 1024 * 1024
IKILI_UZANTI = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".ico", ".woff", ".woff2", ".ttf",
                ".xlsx", ".docx", ".pptx", ".exe", ".dll", ".jar", ".7z", ".gz"}
# Env-tarzı (`AD=değer`) desen yalnız yapılandırma benzeri dosyalarda aranır: ABAP'ta `LV_TOKEN = LS_X-TOKEN.`
# gibi büyük harfli atamalar yanlış alarm üretir.
AYAR_UZANTI = {"", ".env", ".ini", ".cfg", ".conf", ".properties", ".txt", ".sh", ".ps1", ".bat", ".cmd",
               ".yaml", ".yml", ".toml", ".local"}

ICERIK_DESENLERI: list[tuple[str, re.Pattern, bool]] = [
    # (etiket, desen, değer grubu yer tutucu kontrolünden geçsin mi)
    ("özel anahtar bloğu", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED |PGP )?PRIVATE KEY(?: BLOCK)?-----"), False),
    ("AWS erişim anahtarı", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), False),
    ("GitHub token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{50,})"), False),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"), False),
    ("Google API anahtarı", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}"), False),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"), False),
    ("HTTP Basic kimlik bilgisi", re.compile(r"(?i)authorization\s*[:=]\s*[\"']?basic\s+([A-Za-z0-9+/]{12,}={0,2})"), True),
    ("URL içinde parola", re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^/\s:@\"']+:([^/\s@\"']{3,})@"), True),
    ("parola/sır ataması", re.compile(
        r"(?i)(?:password|passwd|pwd|parola|sifre|şifre|secret|client_secret|api_?key|access_?token|auth_?token)"
        r"[\"']?\s*[:=]\s*[\"']([^\"'\s]{6,})[\"']"), True),
]
ENV_DESENI = re.compile(r"(?m)^\s*(?:export\s+|set\s+)?[A-Z0-9_]*(?:PASSWORD|PASSWD|SECRET|TOKEN|API_KEY)[A-Z0-9_]*\s*=\s*([^\s#]{6,})")
_YER_TUTUCU_PARCALAR = ("<", ">", "${", "{{", "%(", "$(", "***", "xxx", "example", "changeme", "placeholder",
                        "dummy", "redacted", "your_", "your-", "ornek", "örnek")
# SAP/ağ bağlantısı kuran gate'ler commit anında çalıştırılmaz. Liste elle tutulmaz, validator kaynağından türetilir.
_AG_ISARETI = re.compile(r"^\s*(?:from|import)\s+(?:sap_adt_lib|sap_client|urllib3|requests)\b|SAPADTClient\(|['\"]npx['\"]", re.M)


class GitHatasi(RuntimeError):
    pass


def _git(proj: Path, *args: str) -> bytes:
    r = subprocess.run(["git", "-C", str(proj), *args], capture_output=True, stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        raise GitHatasi(f"git {' '.join(args[:3])} rc={r.returncode}: "
                        f"{r.stderr.decode('utf-8', 'replace').strip()[:200]}")
    return r.stdout


def staged_dosyalar(proj: Path) -> list[str]:
    out = _git(proj, "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z")
    return [p for p in out.decode("utf-8", "replace").split("\0") if p]


def staged_icerik(proj: Path, yol: str) -> bytes:
    return _git(proj, "show", f":{yol}")


def kimlik_dosyasi_mi(yol: str) -> str | None:
    """Staged yol bir kimlik/bağlantı dosyasıysa gerekçe, değilse None."""
    parcalar = yol.replace("\\", "/").split("/")
    ad = parcalar[-1].lower()
    if any(p.lower() == "secrets" for p in parcalar[:-1]):
        return "secrets/ klasörü"
    ornek = ad.endswith(".example")
    if ad.startswith(".conn") and not ornek:
        return ".conn* bağlantı dosyası"
    if len(parcalar) == 2 and parcalar[0].lower() == "conn" and not ornek and ad != "readme.md":
        return "conn/ klasörü"
    if (ad.endswith(".env") or ad.startswith(".env.")) and not ornek:
        return "*.env / .env.* dosyası"
    if ad.startswith(".saml_cookies") or ("saml" in ad and "cookie" in ad):
        return "SAML çerez dosyası"
    if ad.startswith(".csrf_token"):
        return "CSRF belirteç dosyası"
    return None


def _yer_tutucu_mu(deger: str) -> bool:
    d = deger.lower()
    return (any(p in d for p in _YER_TUTUCU_PARCALAR) or d[:1] in ("$", "%")
            or len(set(d)) <= 2)


def _maskele(deger: str) -> str:
    return (deger[:2] + "…" + f"({len(deger)} karakter)") if deger else "…"


def sir_bul(yol: str, metin: str) -> list[str]:
    """Metindeki sır desenleri → 'satır: etiket (maskeli)' listesi. Sır değeri çıktıya YAZILMAZ."""
    bulgular = []
    desenler = list(ICERIK_DESENLERI)
    uzanti = Path(yol).suffix.lower()
    if uzanti in AYAR_UZANTI or Path(yol).name.startswith("."):
        desenler.append(("yapılandırmada sır değeri", ENV_DESENI, True))
    for etiket, desen, kontrol in desenler:
        for m in desen.finditer(metin):
            deger = m.group(1) if m.groups() else m.group(0)
            if kontrol and _yer_tutucu_mu(deger):
                continue
            satir = metin.count("\n", 0, m.start()) + 1
            bulgular.append(f"{yol}:{satir}: {etiket} ({_maskele(deger)})")
    return bulgular


class Rapor:
    def __init__(self) -> None:
        self.satirlar: list[tuple[str, str]] = []

    def add(self, durum: str, mesaj: str) -> None:
        self.satirlar.append((durum, mesaj))

    def say(self, durum: str) -> int:
        return sum(1 for d, _ in self.satirlar if d == durum)


def kontrol_kimlik(dosyalar: list[str], rapor: Rapor) -> None:
    bulunan = [(y, g) for y in dosyalar for g in [kimlik_dosyasi_mi(y)] if g]
    for yol, gerekce in bulunan:
        rapor.add("FAIL", f"kimlik dosyası staged: {yol} ({gerekce}) → `git rm --cached \"{yol}\"`; "
                          "commit'lenmiş kimlik bilgisi geri alınamaz sayılır, sızdıysa değiştir")
    if not bulunan:
        rapor.add("PASS", f"kimlik dosyası yok ({len(dosyalar)} staged yol)")


def kontrol_sir_icerik(proj: Path, dosyalar: list[str], rapor: Rapor) -> None:
    taranan, atlanan = 0, 0
    bulgular: list[str] = []
    for yol in dosyalar:
        if Path(yol).suffix.lower() in IKILI_UZANTI:
            atlanan += 1
            continue
        ham = staged_icerik(proj, yol)
        if b"\0" in ham[:8000]:
            atlanan += 1
            continue
        if len(ham) > ICERIK_AZAMI_BAYT:
            rapor.add("WARN", f"sır taraması: {yol} {len(ham)} bayt (> {ICERIK_AZAMI_BAYT}) — taranmadı")
            atlanan += 1
            continue
        taranan += 1
        bulgular += sir_bul(yol, ham.decode("utf-8", "replace"))
    for b in bulgular:
        rapor.add("FAIL", f"sır deseni: {b} → değeri dosyadan çıkar (kimlik bilgisi gitignore'lu dosyada durur)")
    if not bulgular:
        rapor.add("PASS", f"sır deseni yok ({taranan} metin dosyası tarandı · {atlanan} ikili/büyük atlandı)")


def kontrol_paket_adlari(proj: Path, dosyalar: list[str], rapor: Rapor) -> None:
    import check_package_naming as cpn
    sonuc, err = cpn.denetle(proj, files=dosyalar)
    if err:
        rapor.add("FAIL", f"paket adlandırma ÇALIŞTIRILAMADI: {err}")
        return
    for ihlal in sonuc.ihlaller:
        rapor.add("FAIL", f"paket adlandırma: {ihlal}")
    if not sonuc.ihlaller:
        rapor.add("PASS", f"paket adlandırma: {sonuc.taranan} obje dosyası uygun ({sonuc.paket_sayisi} paket)")


def _naming_farki(eski: list[tuple[str, str]], yeni: list[tuple[str, str]]) -> list[str]:
    """Obje tipi başına `eski → yeni` satırları (yalnız değişen satırlar)."""
    giden, gelen = [x for x in eski if x not in yeni], [x for x in yeni if x not in eski]
    satirlar = []
    for tip in dict.fromkeys(t for t, _ in giden + gelen):
        e = [f"`{r}`" for t, r in giden if t == tip]
        y = [f"`{r}`" for t, r in gelen if t == tip]
        satirlar.append(f"{tip}: {' '.join(e) or '(yok)'} → {' '.join(y) or '(silindi)'}")
    return satirlar


def kontrol_kural_degisikligi(proj: Path, dosyalar: list[str], rapor: Rapor) -> None:
    """K-O② (kullanıcı kararı 2026-09-18): staged `.rules.md` Naming tablosu ya da istisna listesi
    HEAD'e göre değiştiyse WARN (engellemez).

    Ölçülen vaka: pre-commit adlandırma FAIL'i alan model `.rules.md` regex'ini kendi obje adını
    kapsayacak şekilde genişletti ve aynı commit'e koydu — adlandırma denetimi `.rules.md`'yi
    diskten okuduğu için geçti, kimse fark etmedi. İlk kez eklenen `.rules.md` (HEAD'de yok ya da
    repo hiç commit almamış) WARN ÜRETMEZ: yeni pakette "genişleme" kavramı yoktur; her yeni pakette
    uyarı basmak gerçek vakayı gürültüye gömerdi.
    """
    import check_package_naming as cpn
    for yol in dosyalar:
        if Path(yol).name != ".rules.md":
            continue
        # Yeniden adlandırılan `.rules.md` "ilk kayıt" SAYILMAZ (bug gate 2026-09-19 #3): HEAD'deki
        # kaynağı `git diff --cached -M` ile bulunur ve karşılaştırma ondan yapılır.
        eski_yol = _yeniden_adlandirma_kaynagi(proj, yol) or yol
        r = subprocess.run(["git", "-C", str(proj), "cat-file", "-e", f"HEAD:{eski_yol}"],
                           capture_output=True, stdin=subprocess.DEVNULL)
        if r.returncode != 0:
            continue  # ilk kayıt (HEAD'de yok / hiç commit yok)
        eski_k, eski_i = cpn.kurallari_oku(_git(proj, "show", f"HEAD:{eski_yol}").decode("utf-8", "replace"))
        yeni_k, yeni_i = cpn.kurallari_oku(staged_icerik(proj, yol).decode("utf-8", "replace"))
        fark = _naming_farki(eski_k, yeni_k)
        eklenen_istisna = sorted(yeni_i - eski_i)
        if eklenen_istisna:
            fark.append(f"yeni istisna: {', '.join(eklenen_istisna)}")
        if fark:
            rapor.add("WARN", f"kural değişikliği: {yol} Naming/istisna değişti — " + " · ".join(fark)
                      + " — kullanıcı onayı yoksa geri al: bir denetimi geçmek için kuralı genişletmek "
                        "kuralı gevşetmektir (core/00-temel.md §3)")
    # ⛔ Adlandırma denetimi `.rules.md`'yi DİSKTEN okur, yukarıdaki karşılaştırma ise STAGED içerikten
    # (bug gate 2026-09-19 #3, ölçüldü): stage'lenmemiş bir regex genişletmesi denetimi geçirir ama
    # commit'e girmediği için hiç WARN üretmezdi. Disk ≠ index olan izlenen `.rules.md` uyarılır —
    # YALNIZ adlandırma denetiminin bu commit'te fiilen OKUDUĞU kural dosyasıysa (ikinci ve üçüncü tur,
    # ölçüldü: ilgisiz commit, kökteki `.rules.md` ve pakette yalnız obje-dışı dosya stage'liyken de
    # uyarı çıkıyordu). Küme `check_package_naming.okunan_kural_dosyalari` — denetimle TEK kaynak.
    okunan = cpn.okunan_kural_dosyalari(proj, dosyalar)
    if not okunan:
        return
    try:
        kirli = _git(proj, "diff", "-z", "--name-only", "--", ":(glob)**/.rules.md").decode("utf-8", "replace")
    except GitHatasi as e:
        rapor.add("WARN", f"kural değişikliği: stage'lenmemiş `.rules.md` denetimi ÖLÇÜLEMEDİ ({e})")
        return
    for yol in filter(None, kirli.split("\0")):
        if (proj / yol).resolve() not in okunan:
            continue
        rapor.add("WARN", f"kural değişikliği: {yol} diskte STAGE'LENMEMİŞ değişiklik var — adlandırma "
                          "denetimi diskteki içeriği okudu, commit'e girecek kural bu DEĞİL. Değişiklik "
                          "kasıtlıysa stage'le (yukarıdaki fark denetimi ona da bakar), değilse geri al.")


def _yeniden_adlandirma_kaynagi(proj: Path, yol: str) -> str | None:
    """Staged bir yeniden adlandırmanın HEAD'deki kaynak yolu; yoksa None (ilk kayıt, hiç commit yok)."""
    # `-z` ŞART (üçüncü tur, ölçüldü): onsuz `core.quotePath` ASCII olmayan yolu tırnaklayıp kaçışlar ⇒
    # eşleşme olmaz, taşınan kural "ilk kayıt" sayılır. `-z` çıktısı: durum, yol[, yeni yol] — NUL ayrık.
    try:
        cikti = _git(proj, "diff", "--cached", "-M", "--name-status", "-z", "HEAD").decode("utf-8", "replace")
    except GitHatasi:
        return None
    parca = cikti.split("\0")
    i = 0
    while i < len(parca) and parca[i]:
        durum = parca[i]
        if durum[:1] in ("R", "C"):
            if durum.startswith("R") and i + 2 < len(parca) and parca[i + 2] == yol:
                return parca[i + 1]
            i += 3
        else:
            i += 2
    return None


def kontrol_yerel_validatorler(proj: Path, dosyalar: list[str], rapor: Rapor) -> None:
    klasor = proj / VALIDATORS_LOCAL
    if not klasor.is_dir():
        rapor.add("INFO", f"{VALIDATORS_LOCAL}/ yok — proje validator'ı koşmadı")
        return
    scriptler = sorted(p for p in klasor.glob("*.py") if not p.name.startswith("_"))
    if not scriptler:
        rapor.add("INFO", f"{VALIDATORS_LOCAL}/ içinde çalıştırılacak *.py yok")
        return
    with tempfile.TemporaryDirectory(prefix="axet-precommit-") as td:
        liste = Path(td) / "staged.txt"
        liste.write_text("\n".join(dosyalar) + ("\n" if dosyalar else ""), encoding="utf-8")
        env = dict(os.environ, AXET_PRECOMMIT="1", AXET_PROJECT_DIR=str(proj), AXET_STAGED_FILES=str(liste),
                   PYTHONIOENCODING="utf-8")
        for s in scriptler:
            ad = f"{VALIDATORS_LOCAL}/{s.name}"
            try:
                r = subprocess.run([sys.executable, str(s)], cwd=str(proj), env=env, capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", timeout=YEREL_ZAMAN_ASIMI,
                                   stdin=subprocess.DEVNULL)
            except subprocess.TimeoutExpired:
                rapor.add("FAIL", f"{ad}: {YEREL_ZAMAN_ASIMI} sn içinde bitmedi — ÇALIŞTIRILAMADI (temiz sayılmaz)")
                continue
            except OSError as exc:
                rapor.add("FAIL", f"{ad}: ÇALIŞTIRILAMADI ({exc})")
                continue
            kuyruk = " | ".join((r.stdout + r.stderr).strip().splitlines()[-6:])
            if r.returncode == 0:
                rapor.add("PASS", f"{ad}" + (f" — {kuyruk}" if kuyruk else ""))
            elif r.returncode == 1:
                rapor.add("FAIL", f"{ad}: ihlal — {kuyruk or '(çıktı yok)'}")
            else:
                rapor.add("FAIL", f"{ad}: exit {r.returncode} — ÇALIŞTIRILAMADI sayılır (sözleşme: 0 geçer, 1 ihlal) "
                                  f"— {kuyruk or '(çıktı yok)'}")


def _modul_yukle(ad: str, yol: Path):
    spec = importlib.util.spec_from_file_location(ad, yol)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)  # type: ignore[union-attr]
    return modul


def obje_tipi(yol: str) -> str | None:
    """Staged dosya → yazma kapısındaki `adt_push_source` obje tipi (reviewer görev eşlemesi için)."""
    ad = Path(yol).name.lower()
    parcalar = ad.split(".")
    if len(parcalar) == 3 and parcalar[1:] == ["clas", "abap"]:
        return "clas"
    if ad.endswith(".ddls.asddls") or (len(parcalar) == 2 and parcalar[1] == "cds"):
        return "ddls"
    if len(parcalar) >= 2 and parcalar[1] == "bdef":
        return "bdef"
    if len(parcalar) >= 2 and parcalar[1] == "srvd":
        return "srvd"
    if len(parcalar) >= 3 and parcalar[1] == "tabl":
        return "tabl"
    return None


def kontrol_sap_inceleme(proj: Path, dosyalar: list[str], rapor: Rapor) -> None:
    abap_benzeri = [y for y in dosyalar if Path(y).suffix.lower() in (".abap", ".asddls", ".cds", ".bdef", ".srvd",
                                                                       ".xml", ".asbdef", ".srvdsrv", ".ddl")]
    adaylar = [(y, obje_tipi(y)) for y in abap_benzeri]
    zincirsiz = [y for y, t in adaylar if t is None]
    adaylar = [(y, t) for y, t in adaylar if t]
    if zincirsiz:
        rapor.add("INFO", "SAP incelemesi: yazma kapısında inceleme zinciri olmayan dosyalar (program, include, "
                          f"arayüz, fonksiyon …) incelenmedi: {', '.join(zincirsiz[:6])}" + (" …" if len(zincirsiz) > 6 else ""))
    if not adaylar:
        return
    try:
        if str(FOUNDATION_SCRIPTS) not in sys.path:
            sys.path.insert(0, str(FOUNDATION_SCRIPTS))
        from sapadt import _reviewer  # noqa: WPS433  (yazma kapısıyla aynı görev eşlemesi)
        rr = _modul_yukle("axet_run_review", RUN_REVIEW)
    except Exception as exc:  # noqa: BLE001
        rapor.add("FAIL", f"SAP incelemesi ÇALIŞTIRILAMADI (sap-adt-foundation reviewer yüklenemedi: "
                          f"{type(exc).__name__}: {exc}) — {len(adaylar)} dosya incelenmedi, temiz sayılmaz")
        return
    os.environ["AXET_SAP_PROJECT_DIR"] = str(proj)
    ag_gate_leri: set[str] = set()
    with tempfile.TemporaryDirectory(prefix="axet-review-") as td:
        for i, (yol, tip) in enumerate(adaylar):
            icerik = staged_icerik(proj, yol)
            kaynak = icerik.decode("utf-8", "replace")
            gorev = _reviewer.task_for_push(tip, kaynak)
            zincir = rr.TASK_VALIDATORS.get(gorev, []) if gorev else []
            if not zincir:
                rapor.add("INFO", f"SAP incelemesi: {yol} ({tip} → {gorev or 'görev yok'}) — zincirde gate yok, ölçüm yapılmadı")
                continue
            artefakt = Path(td) / str(i) / Path(yol).name
            artefakt.parent.mkdir(parents=True, exist_ok=True)
            artefakt.write_bytes(icerik)
            bulgu = 0
            for script, siddet, aciklama in zincir:
                yolu = rr.validator_yolu(script)
                if not yolu.is_file():
                    durum = "FAIL" if siddet == "BLOCKER" else "WARN"
                    rapor.add(durum, f"SAP incelemesi {yol}: {script} bulunamadı — KOŞMADI ({siddet}; temiz sayılmaz)")
                    bulgu += 1
                    continue
                if _AG_ISARETI.search(yolu.read_text(encoding="utf-8", errors="replace")):
                    ag_gate_leri.add(script)
                    continue
                ek = ["--type", "table"] if gorev in ("table_creation", "table_update") and "cds_currency" in script else []
                arg = None if script in getattr(rr, "REPO_WIDE_SCANNERS", set()) else str(artefakt)
                rc, out, err = rr.run_validator(yolu, arg, ek)
                if rc != 0:
                    durum = "FAIL" if siddet == "BLOCKER" else "WARN"
                    kuyruk = " | ".join((out + "\n" + err).replace(str(artefakt), yol).strip().splitlines()[-4:])
                    rapor.add(durum, f"SAP incelemesi {yol} [{gorev}] {script} ({siddet}): {aciklama} — {kuyruk}")
                    bulgu += 1
                    continue
                beyan = rr.gate_durum_beyani(out, script)
                if beyan and beyan.get("measured") == "false":
                    rapor.add("WARN", f"SAP incelemesi {yol}: {script} ölçüm üretmedi ({beyan.get('reason')}) — temiz sayılmaz")
            if not bulgu:
                rapor.add("PASS", f"SAP incelemesi {yol} [{gorev}]: çevrimdışı gate'lerde BLOCKER yok")
    if ag_gate_leri:
        rapor.add("WARN", "SAP incelemesi: SAP/ağ gerektiren gate'ler commit anında ÇALIŞTIRILMADI "
                          f"(yazma kapısında koşar): {', '.join(sorted(ag_gate_leri))}")


def main() -> int:
    ap = argparse.ArgumentParser(description="aXet proje pre-commit denetimi (yalnız staged içerik)")
    ap.add_argument("--project-dir", default=".", help="proje kökü (varsayılan: bulunulan dizin)")
    args = ap.parse_args()
    proj = Path(args.project_dir).resolve()
    rapor = Rapor()
    try:
        dosyalar = staged_dosyalar(proj)
        print(f"[pre-commit] aXet proje denetimi — {len(dosyalar)} staged dosya · {proj}")
        kontrol_kimlik(dosyalar, rapor)
        kontrol_sir_icerik(proj, dosyalar, rapor)
        sap = (proj / "sap-project.json").is_file()
        if sap:
            kontrol_paket_adlari(proj, dosyalar, rapor)
            kontrol_kural_degisikligi(proj, dosyalar, rapor)
        kontrol_yerel_validatorler(proj, dosyalar, rapor)
        if sap:
            kontrol_sap_inceleme(proj, dosyalar, rapor)
        else:
            rapor.add("INFO", "SAP projesi değil (sap-project.json yok): paket adlandırma ve SAP incelemesi atlandı")
    except GitHatasi as exc:
        rapor.add("FAIL", f"git sorgusu ÇÖKTÜ — denetim yapılamadı, 'temiz' sayılmaz: {exc}")
    except Exception as exc:  # noqa: BLE001 — denetim çökerse commit geçmemeli
        rapor.add("FAIL", f"denetim ÇÖKTÜ ({type(exc).__name__}: {exc}) — 'temiz' sayılmaz")

    for durum, mesaj in rapor.satirlar:
        print(f"[{durum}] {mesaj}")
    print("KAPSAM — bakılanlar: staged yollar ve staged içerik · bakılmayanlar: commit edilmiş geçmiş, çalışma "
          "ağacındaki staged olmayan değişiklik, kimlik bilgisinin desen dışı biçimleri, SAP/ağ gerektiren gate'ler, "
          "ikili ve 5 MB üstü dosyalar, commit mesajı")
    fails = rapor.say("FAIL")
    print(f"SONUÇ: {fails} FAIL · {rapor.say('WARN')} WARN → " + ("commit ENGELLENDİ" if fails else "geçti"))
    if fails:
        print("Düzelt ve tekrar commit et. Yanlış alarm ise kullanıcı kendi terminalinde karar verir "
              "(git commit --no-verify); aXet oturumu bu denetimi atlatmaz.")
        # K-O① (2026-09-18): "düzelt" = İÇERİĞİ düzelt. Ölçülen vaka: model kuralı genişletip geçti.
        print("HATIRLATMA: düzeltme = içeriği düzeltmek. Denetimi geçmek için kuralı / regex'i / "
              "`.rules.md`'yi / validator'ı DEĞİŞTİRME — reddi ve sebebini kullanıcıya bildir; kural "
              "değişikliği ayrı ve açık onay ister (core/00-temel.md §3).")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
