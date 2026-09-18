#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""quality_scorecard.py — kapı defteri (append-only) + kod kalite karnesi.

⛔ BU BİR GATE DEĞİL, RAPORDUR. Hiçbir akışa bloklayıcı olarak kablolanmamıştır: yazma kapısı
(`gate.py`), reviewer zinciri (`run_review.py`) ve pre-commit bu script'i ÇAĞIRMAZ ve çağırmamalıdır.
Yeni bir kapı açmak ayrı ve açık kullanıcı onayı ister (gate moratoryumu) — o onay YOK. Kendi çıkış
kodunu döndürmesi aracın kendi sözleşmesidir; onu OKUYUP karar veren insandır, bir otomasyon değil.
Kablosuzluk ölçülür: `tests/test_quality_scorecard.py::GateDegilRaporTests` template'teki HİÇBİR .py
dosyasının bu script'in adını geçirmediğini her koşumda doğrular.

İKİ ARTEFAKT:
  (A) KAPI DEFTERİ — her kapı sonucu bir JSONL satırı olarak EKLENİR. Satır hiçbir zaman
      güncellenmez/silinmez: dosya YALNIZ "a" kipinde açılır. Defter bir OLAY kaydıdır; reddedilen
      bir iddia (ör. artefaktsız `pass`) da yazılır — tarih düzeltilmez, üstüne not düşülür.
  (B) KARNE — deftere bakıp tek bir özet üretir. DEĞİŞMEZLERİ (hepsi `tests/` içinde çivilidir):
      D1 `not-run` AYRI bir durumdur; sessizce `pass` sayılmaz, karnede ayrı sütundur.
      D2 Artefaktsız (ya da yolu diskte olmayan) `pass` GEÇERSİZDİR → karne GÜVENİLMEZ, çıkış 2.
      D3 Koşan test sayısı 0 olan kapı `pass` olamaz → zorla `warn`.
      D4 Dar/varsayılan kapsamla koşmuş kontrol `pass` olamaz → `warn` + karneye not.
      D5 Kapsam beyanı BOŞ satır karnede SÖYLENİR (boş beyan "inceleme her şeyi gördü" diye okunur).
      D6 ARKA DURAK: doğrulama yalnız yazma anında değil, OKUMA anında da koşar — kapı yolundan
         geçmeden elle eklenmiş artefaktsız `pass` satırları da yakalanır.

`measured` SÖZLEŞMESİ İCAT EDİLMEZ: `_gate_status.py`'nin ürettiği
`AXET-GATE-STATUS: ... measured=true|false ...` satırı okunur (ikinci üretici: `abaplint_run.py` →
`ABAPLINT-RUN-STATUS: ... measured=...`). `measured=false` "temiz" DEĞİLDİR → satır `not-run` olur;
bu, `run_review.py`'nin aynı olaya verdiği hükmün ta kendisidir.

KAPI ADLARI KODDAN TÜRETİLİR (elle tutulan liste bayatlar ve sahte güven üretir):
  review:<görev>        `run_review.py` TASK_VALIDATORS anahtarları
  validator:<check_ad>  diskteki gerçek `check_*.py` dosyaları
  test:<takım dizini>   diskteki gerçek test takımları
  sap:<adt_aracı>       araç kataloğundaki `adt_*` araçları; `sinif` = okuma|yazma (`gate.py` READ_TOOLS)
⚠ `adt_syntax_check` bizde YAZMA sınıfıdır (SAP'ye gider) — ücretsiz bir ön kontrol değildir; karne
bunu ayrıca işaretler.

Kullanım:
    python quality_scorecard.py kaydet --kapi validator:check_abaplint --sonuc pass \
        --artefakt .axet-code/kanit/abaplint.txt --kapsam "3 sınıf; CDS/BDEF HARİÇ" \
        [--test-sayisi N] [--dar-kapsam] [--komut "..."] [--durum-ciktisi <dosya|->] [--defter <yol>]
    python quality_scorecard.py karne [--defter <yol>] [--json] [--artefakt-kok <dizin>]
    python quality_scorecard.py kapilar [--json]

Çıkış kodları (her iki kip için AYNI; fark yalnız GÖRÜNÜRLÜKTEDİR):
    kaydet: 0 satır eklendi · 2 satır eklendi AMA sözleşmeye aykırı (artefaktsız pass) / yazılamadı
    karne : 0 karne üretildi (PASS | WARN | OLCULMEDI) · 1 defterde `fail` var
            2 KARNE GÜVENİLMEZ (artefaktsız/diskte olmayan pass · bozuk satır · defter yok)
"""
from __future__ import annotations

import argparse
import ast
import contextlib
import datetime as _dt
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path

for _akis in (sys.stdout, sys.stderr):
    try:
        _akis.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass

# skills-sap/<skill>/scripts/<bu dosya> → template kökü
KOK = Path(__file__).resolve().parents[3]
DEFTER_REL = Path(".axet-code") / "quality-gate-log.jsonl"
GECERLI_SONUC = ("pass", "fail", "warn", "not-run")
# ⛔ KAPALI KÜME: defterdeki bir satır YALNIZ bu alanları taşıyabilir. Sebep kozmetik değil —
# `"dar-kapsam"` (tire) gibi bir AD KAÇAMAĞI, D4 düşürmesini sessizce atlatıyordu (ölçüldü).
# Tip kaçamağı (`"0"`) kapatılmıştı; ad kaçamağı bu küme kablolanana kadar açıktı.
ANAHTARLAR = ("ts", "kapi", "sonuc", "artefakt", "kapsam", "test_sayisi", "dar_kapsam",
              "measured", "measured_reason", "komut", "kosum")

# ── measured sözleşmesi — ayrıştırıcı (üretici: _gate_status.py / abaplint_run.py) ───────────────
# Çapalar `run_review.py`'nin tüketicisiyle AYNI: satır-başı (`^`, re.M) + `measured=(true|false)`
# TAM eşleşme. Sözleşmeyi TARİF EDEN girintili örnek metin beyan sayılmaz.
_AXET_TAM = re.compile(r"^AXET-GATE-STATUS:\s+gate=(?P<gate>\S+)\s+status=(?P<status>\S+)\s+"
                       r"measured=(?P<measured>true|false)\s+reason=(?P<reason>\S+)\s*$", re.M)
_AXET_SATIR = re.compile(r"^AXET-GATE-STATUS:.*$", re.M)
_YABANCI_ONEK = re.compile(r"^(?P<onek>[^\s:]+)-GATE-STATUS:", re.M)
_ABAPLINT_SATIR = re.compile(r"^ABAPLINT-RUN-STATUS:.*$", re.M)
_ABAPLINT_MEASURED = re.compile(r"\bmeasured=(true|false)\b")
_ABAPLINT_REASON = re.compile(r"\breason=(\S+)")


def durum_beyani(ciktı: str, gate_adi: str | None = None) -> tuple[bool | None, str | None]:
    """Bir aracın stdout'undan (measured, reason) çıkar. Beyan YOKSA (None, None) döner.

    ⛔ HÜKÜM SIRASI `run_review.gate_durum_beyani` İLE AYNIDIR — ve bu eşlik test edilir
    (V1/V2 fixture'ları). Sıra KEYFİ DEĞİL: ikisi de fail-closed yönde çalışır.
      ① biçimi bozuk `AXET-` satırı  → measured=false, `bicim-bozuk` (çelişkili beyan kanıt değil)
      ② geçerli `AXET-` beyanları    → `gate=` alanı `gate_adi` ile eşleşen SÜZÜLÜR; eşleşme
         yoksa SON beyan alınır (script'in nihai sözü). ⚠ Süzgeç OLMADAN çok-beyanlı çıktıda
         BAŞKA bir gate'in `measured=true` satırı okunur ve `pass` sessizce ayakta kalırdı —
         ayrışma tam da false-green yönündeydi (ölçüldü: V1).
      ③ tanınmayan `<X>-GATE-STATUS:` öneki → measured=false (bayat/yabancı kopya kendi
         `measured=false`'unu gizlemesin). ⚠ Bu dal ABAPLINT dalından ÖNCE gelir: tersi olursa
         yabancı önekli bir `measured=false`, aynı çıktıdaki ABAPLINT `measured=true` ile
         örtülürdü (ölçüldü: V2).
      ④ `ABAPLINT-RUN-STATUS` (ikinci üretici, `abaplint_run.py`) → kendi `measured` alanı.
         `run_review`'da bu dal YOKTUR (orası yalnız `-GATE-STATUS:` satırlarına bakar); burada
         BİLİNÇLİ bir GENİŞLETMEDİR ve yalnız hiçbir `-GATE-STATUS:` satırı yokken devreye girer,
         yani run_review'ın hüküm verdiği HİÇBİR girdide ayrışma üretmez.
      ⑤ hiç beyan yok → (None, None). "Beyan yok" ≠ "ölçülmedi": varsayım YAPILMAZ.
    """
    metin = ciktı or ""
    if any(not _AXET_TAM.fullmatch(m.group(0)) for m in _AXET_SATIR.finditer(metin)):
        return False, "bicim-bozuk"
    beyanlar = [m.groupdict() for m in _AXET_TAM.finditer(metin)]
    if beyanlar:
        kendi = [b for b in beyanlar if gate_adi and b["gate"] == gate_adi]
        son = (kendi or beyanlar)[-1]
        return son["measured"] == "true", son["reason"]
    yabanci = [m.group("onek") for m in _YABANCI_ONEK.finditer(metin) if m.group("onek") != "AXET"]
    if yabanci:
        return False, f"taninmayan-onek-{yabanci[-1]}"
    lint = _ABAPLINT_SATIR.findall(metin)
    if lint:
        m = _ABAPLINT_MEASURED.search(lint[-1])
        if m:
            r = _ABAPLINT_REASON.search(lint[-1])
            return m.group(1) == "true", (r.group(1) if r else None)
        return False, "bicim-bozuk"
    return None, None


def gate_adi_turet(kapi: str | None) -> str | None:
    """`validator:check_abaplint` → `check_abaplint` (AXET beyanındaki `gate=` alanının karşılığı).

    Namespace'i olmayan ya da eşleşmeyen adlarda süzgeç kendiliğinden devre dışı kalır (② dalı
    son beyana düşer) — yani türetme YANLIŞSA davranış eski davranışa döner, sessiz bir
    daralma üretmez.
    """
    if not isinstance(kapi, str) or not kapi.strip():
        return None
    return kapi.split(":", 1)[-1].strip() or None


# ── KAPI KAYIT DEFTERİ — koddan türetilir ────────────────────────────────────────────────────────

def _literal(yol: Path, ad: str):
    """Dosyayı IMPORT ETMEDEN bir modül-düzeyi sabitini oku (yan etki yok)."""
    for dugum in ast.parse(yol.read_text(encoding="utf-8")).body:
        hedefler = (dugum.targets if isinstance(dugum, ast.Assign)
                    else [dugum.target] if isinstance(dugum, ast.AnnAssign) else [])
        if any(isinstance(t, ast.Name) and t.id == ad for t in hedefler):
            return ast.literal_eval(dugum.value)
    raise KeyError(ad)


def kapi_defteri(kok: Path | None = None) -> tuple[dict, list[str]]:
    """(kapılar, ölçülemeyen kaynaklar). Kaynak okunamıyorsa SESSİZCE boş dönmez — söyler."""
    kok = kok or KOK
    kapilar: dict[str, dict] = {}
    olculemedi: list[str] = []

    run_review = kok / "skills-sap/sap-adt-foundation/scripts/sapadt/lib/validators/run_review.py"
    try:
        for gorev in _literal(run_review, "TASK_VALIDATORS"):
            kapilar[f"review:{gorev}"] = {"sinif": "cevrimdisi", "kaynak": "run_review.py"}
    except (OSError, KeyError, ValueError, SyntaxError) as e:
        olculemedi.append(f"review: — run_review.py TASK_VALIDATORS okunamadı ({type(e).__name__})")

    checkler = sorted({p.name for p in kok.glob("skills-sap/*/scripts/**/check_*.py")}
                      | {p.name for p in kok.glob("scripts/check_*.py")})
    if checkler:
        for ad in checkler:
            kapilar[f"validator:{Path(ad).stem}"] = {"sinif": "cevrimdisi", "kaynak": "check_*.py"}
    else:
        olculemedi.append("validator: — diskte hiç check_*.py bulunamadı")

    takimlar = sorted({p.parent.relative_to(kok).as_posix()
                       for p in kok.glob("**/tests/test_*.py") if "__pycache__" not in p.parts})
    if takimlar:
        for t in takimlar:
            kapilar[f"test:{t}"] = {"sinif": "cevrimdisi", "kaynak": "tests/"}
    else:
        olculemedi.append("test: — diskte hiç test takımı bulunamadı")

    katalog = kok / "skills-sap/sap-adt-foundation/references/tool-catalog.md"
    gate_py = kok / "skills-sap/sap-adt-foundation/scripts/sapadt/gate.py"
    try:
        araclar = sorted(set(re.findall(r"^###\s+`(adt_[a-z_]+)`", katalog.read_text(encoding="utf-8"), re.M)))
        blok = re.search(r"READ_TOOLS\s*=\s*frozenset\(\{(.*?)\}\)", gate_py.read_text(encoding="utf-8"), re.S)
        okuma = set(re.findall(r'"([a-z_]+)"', blok.group(1))) if blok else set()
        if not araclar or not okuma:
            raise ValueError("boş küme")
        for a in araclar:
            kapilar[f"sap:{a}"] = {"sinif": "okuma" if a in okuma else "yazma",
                                   "kaynak": "tool-catalog.md + gate.READ_TOOLS"}
    except (OSError, AttributeError, ValueError) as e:
        olculemedi.append(f"sap: — araç kataloğu / gate.READ_TOOLS okunamadı ({type(e).__name__})")

    return kapilar, olculemedi


# ── DEĞERLENDİRME KURALLARI — karnenin KAPSAM BEYANI bu tablodan türetilir ──────────────────────

# Alan tipleri: gevşek bırakılırsa ELLE yazılmış bir satır düşürme kurallarını TİP ÜZERİNDEN
# atlatır (ölçüldü: `"test_sayisi": "0"` metin olarak D3'e takılmaz ve satır `pass` kalır).
# Tip denetimi bu yüzden D6 arka durağının bir parçasıdır, kozmetik bir şema kontrolü değil.
TIP_SOZLESMESI = (
    ("test_sayisi", (int,), "tam sayı"),
    ("kosum", (str,), "metin"),
    ("dar_kapsam", (bool,), "true/false"),
    ("measured", (bool,), "true/false"),
    ("artefakt", (str,), "metin"),
    ("kapsam", (str,), "metin"),
)


def _kural_sema(kayit, etkin, bayrak, kok):
    notlar = []
    if not isinstance(kayit.get("kapi"), str) or not kayit.get("kapi", "").strip():
        bayrak["gecersiz"] = True
        notlar.append("kapı adı boş — bu satır bir kapı sonucu olarak okunamaz")
    if etkin not in GECERLI_SONUC:
        bayrak["gecersiz"] = True
        notlar.append(f"sözleşme dışı sonuç değeri {etkin!r} (beklenen: {', '.join(GECERLI_SONUC)})")
    # AD KAÇAMAĞI: kapalı küme dışı bir alan adı (`dar-kapsam` gibi) düşürme kurallarını
    # sessizce atlatır — kural alanı `dar_kapsam` diye arar, satırda o ad YOKTUR.
    yabanci_alan = sorted(set(kayit) - set(ANAHTARLAR))
    if yabanci_alan:
        bayrak["gecersiz"] = True
        notlar.append(f"tanınmayan alan adı: {', '.join(yabanci_alan)} — sözleşme kapalı bir "
                      f"kümedir; yanlış yazılmış bir ad düşürme kurallarını atlatır "
                      f"(beklenen: {', '.join(ANAHTARLAR)})")
    for alan, tipler, beklenen in TIP_SOZLESMESI:
        deger = kayit.get(alan)
        if deger is None:
            continue
        # `bool` Python'da `int`'in alt sınıfıdır: `True` bir test sayısı DEĞİLDİR.
        if not isinstance(deger, tipler) or (int in tipler and isinstance(deger, bool)):
            bayrak["gecersiz"] = True
            notlar.append(f"`{alan}` {beklenen} olmalı, {type(deger).__name__} geldi — "
                          f"tip kaçamağı düşürme kurallarını atlatır")
    # NEGATİF SAYI: `test_sayisi == 0` eşitliğine dayanan D3, `-1` yazılarak bedelsiz atlanıyordu.
    ts = kayit.get("test_sayisi")
    if isinstance(ts, int) and not isinstance(ts, bool) and ts < 0:
        bayrak["gecersiz"] = True
        notlar.append(f"`test_sayisi` negatif ({ts}) — koşan test sayısı negatif olamaz; "
                      f"bu, 0-test kuralının (D3) etrafından dolaşmaktır")
    return etkin, notlar


def _kural_artefakt(kayit, etkin, bayrak, kok):
    if etkin != "pass":
        return etkin, []
    ham = kayit.get("artefakt")
    if not isinstance(ham, str) or not ham.strip():
        bayrak["gecersiz"] = True
        return etkin, ["artefakt yolu YOK — kanıtsız `pass` geçersizdir (D2)"]
    yol = Path(ham)
    if not yol.is_absolute():
        yol = Path(kok) / yol
    if not yol.exists():
        bayrak["gecersiz"] = True
        return etkin, [f"artefakt diskte YOK: {ham} — kanıtı bulunmayan `pass` geçersizdir (D2)"]
    # Belge artefaktı "kanıt DOSYASININ yolu" diye tanımlar. Bir DİZİN `exists()` der ama hiçbir
    # şey kanıtlamaz; 0 baytlık bir dosya da öyle. İkisi de sessizce `pass` taşıyordu (ölçüldü).
    if not yol.is_file():
        bayrak["gecersiz"] = True
        return etkin, [f"artefakt bir dosya değil (dizin ya da özel dosya): {ham} — "
                       f"kanıt bir DOSYAdır, `pass` geçersizdir (D2)"]
    try:
        boyut = yol.stat().st_size
    except OSError as e:
        bayrak["gecersiz"] = True
        return etkin, [f"artefakt okunamadı ({e.__class__.__name__}): {ham} — ÖLÇÜLEMEDİ, "
                       f"`pass` geçersizdir (D2)"]
    if boyut == 0:
        return "warn", ["artefakt 0 bayt — boş bir dosya kanıt taşımaz; `warn`'a düşürüldü (D2)"]
    return etkin, []


def _kural_measured(kayit, etkin, bayrak, kok):
    if kayit.get("measured") is False and etkin in ("pass", "warn"):
        sebep = kayit.get("measured_reason") or "belirtilmedi"
        return "not-run", [f"measured=false (reason={sebep}) — kapı ÖLÇÜM ÜRETMEDİ; "
                           f"'koşmadı' ≠ 'temiz', satır `not-run` sayıldı"]
    return etkin, []


def _kural_sifir_test(kayit, etkin, bayrak, kok):
    if kayit.get("test_sayisi") == 0 and etkin == "pass":
        return "warn", ["0 test koştu — sıfır testli bir kapı `pass` olamaz, `warn`'a düşürüldü (D3)"]
    return etkin, []


def _kural_dar_kapsam(kayit, etkin, bayrak, kok):
    if kayit.get("dar_kapsam") and etkin == "pass":
        return "warn", ["kapsam daraltılmış (varsayılan/dar kapsamla koşuldu) — `warn`'a düşürüldü (D4)"]
    return etkin, []


def _kural_kapsam_beyani(kayit, etkin, bayrak, kok):
    kapsam = kayit.get("kapsam")
    if not isinstance(kapsam, str) or not kapsam.strip():
        bayrak["kapsam_bos"] = True
        return etkin, ["kapsam beyanı BOŞ — boş beyan okuyucuya 'inceleme her şeyi gördü' diye "
                       "okunur; neye BAKILMADIĞI yazılmalı (D5)"]
    return etkin, []


KURALLAR = (
    ("sema", "satır şeması: kapı adı, sonuç değeri ve alan TİPLERİ sözleşmede mi", _kural_sema),
    ("artefakt", "`pass` satırında artefakt yolu VAR mı ve diskte MEVCUT mu", _kural_artefakt),
    ("measured", "`measured=false` beyanı varsa `pass`/`warn` → `not-run`", _kural_measured),
    ("sifir-test", "koşan test sayısı 0 ise `pass` → `warn`", _kural_sifir_test),
    ("dar-kapsam", "dar/varsayılan kapsam bayrağı varsa `pass` → `warn`", _kural_dar_kapsam),
    ("kapsam-beyani", "kapsam notu boş mu", _kural_kapsam_beyani),
)

BAKILMAYANLAR = (
    "artefaktın İÇERİĞİ — yalnız yolun diskte VARLIĞI ölçülür, gövdesi okunmaz",
    "kapının gerçekten koşup koşmadığı — defter bir BEYAN kaydıdır; koşum kanıtı artefakttır",
    "`dar_kapsam` bayrağı VERİLMEDİYSE kapsam daralması (kapsam metni serbesttir, ayrıştırılmaz)",
    "canlı SAP durumu — bu araç ağ kullanmaz, hiçbir şeyi yeniden koşmaz",
    "defterin TAMLIĞI — yalnız bilinen kapı listesine göre 'kaydedilmemiş kapı' sayılır",
)


def satir_degerlendir(kayit: dict, artefakt_kok: Path) -> tuple[str, list[str], dict]:
    etkin = kayit.get("sonuc")
    notlar: list[str] = []
    bayrak = {"gecersiz": False, "kapsam_bos": False}
    for _ad, _aciklama, fn in KURALLAR:
        etkin, yeni = fn(kayit, etkin, bayrak, artefakt_kok)
        notlar.extend(yeni)
    return etkin, notlar, bayrak


# ── DEFTER ───────────────────────────────────────────────────────────────────────────────────────

def defter_yolu(arg: str | None) -> Path:
    if arg:
        return Path(arg)
    proje = Path(os.environ.get("AXET_SAP_PROJECT_DIR") or os.getcwd())
    return proje / DEFTER_REL


class KilitAlinamadi(OSError):
    """Defter kilidi alınamadı — yazma YAPILMADI. Sessiz devam YOK (çağıran rc≠0 döner)."""


def kilit_yolu(defter: Path) -> Path:
    """Öngörülebilir ad: `<defter>.lock` — harici bir araç da AYNI kilidi alabilsin."""
    return defter.parent / (defter.name + ".lock")


@contextlib.contextmanager
def defter_kilidi(defter: Path, saniye: float = 10.0):
    """Süreçler arası dışlayıcı kilit (Windows: msvcrt · POSIX: fcntl).

    ⛔ NEDEN GEREKLİ (ölçüldü, 6 süreç × 25 `kaydet` = 150 satır, 6 koşum): `open(…, "a")`
    Windows'ta süreçler arası ATOMİK DEĞİLDİR — 6 koşumun 6'sında satır KAYBOLDU (toplam 11),
    kaybolan çağrıların HEPSİ rc=0 döndü ve dosyada bozuk satır yoktu. Yani kayıp HİÇBİR
    kanaldan görünmüyordu ve kaybolan satır bir `fail` ise karne `FAIL` yerine `PASS` derdi.
    Kontrol grubu: tek süreçte kayıp yok.
    """
    kilit = kilit_yolu(defter)
    kilit.parent.mkdir(parents=True, exist_ok=True)
    bitis = time.monotonic() + max(0.1, float(saniye))
    with open(kilit, "a+b") as lf:
        while True:
            try:
                lf.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(lf.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lf.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as e:
                if time.monotonic() >= bitis:
                    raise KilitAlinamadi(
                        f"defter kilidi {saniye}s içinde alınamadı ({kilit}): {e} — "
                        f"YAZMA YAPILMADI") from e
                time.sleep(0.05)
        try:
            yield
        finally:
            try:
                lf.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(lf.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lf.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass


def satir_ekle(defter: Path, kayit: dict, kilit_saniye: float = 10.0) -> None:
    """TEK yazma yolu. ⛔ Kip DAİMA "a" (append-only) VE kilit altında (eşzamanlı kayıp yok).

    Kilit alınamazsa `KilitAlinamadi` fırlatır ve HİÇBİR ŞEY yazmaz — yarım/sessiz yazma yoktur.
    """
    defter.parent.mkdir(parents=True, exist_ok=True)
    with defter_kilidi(defter, kilit_saniye):
        with open(defter, "a", encoding="utf-8") as f:
            f.write(json.dumps(kayit, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())


def defter_oku(defter: Path) -> tuple[list[dict], list[tuple[int, str]]]:
    kayitlar, bozuk = [], []
    for n, satir in enumerate(defter.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if not satir.strip():
            continue
        try:
            k = json.loads(satir)
            if not isinstance(k, dict):
                raise ValueError("satır bir JSON nesnesi değil")
            kayitlar.append(k)
        except (json.JSONDecodeError, ValueError) as e:
            bozuk.append((n, str(e)))
    return kayitlar, bozuk


# ── KARNE ────────────────────────────────────────────────────────────────────────────────────────

def satir_kapsamda(kayit: dict, kosum: str | None, since: str | None) -> bool:
    """Okuma-tarafı kapsam süzgeci. ⛔ Defter DEĞİŞMEZ (append-only) — süzgeç yalnız okumadadır.

    `ts` alanı okunamayan bir satır `--since` süzgecinde DIŞARI ATILMAZ, İÇERİDE kalır: kanıtı
    düşürmek, kanıtı görmezden gelmekten daha tehlikelidir (satır yine de şema kuralına takılır).
    """
    if kosum is not None and kayit.get("kosum") != kosum:
        return False
    if since is not None:
        ts = kayit.get("ts")
        if isinstance(ts, str) and ts and ts < since:
            return False
    return True


def karne_uret(defter: Path, artefakt_kok: Path, kok: Path,
               kosum: str | None = None, since: str | None = None) -> dict:
    kapilar, kapi_olculemedi = kapi_defteri(kok)
    karne = {
        "uretim_ts": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "defter": str(defter),
        "hukum": "OLCULMEDI",
        "guvenilmez": False,
        "satir_sayisi": 0,
        "toplam_satir": 0,
        "okunan_satir": 0,
        "kapsam_suzgeci": {"kosum": kosum, "since": since},
        "olculmemis": 0,
        "bozuk_satir_sayisi": 0,
        "bozuk_satirlar": [],
        "sayim": {s: 0 for s in GECERLI_SONUC},
        "kapsam_beyani_bos": 0,
        "bilinmeyen_kapi": [],
        "yazma_sinifi_kapi": [],
        "kapilar": {"bilinen": len(kapilar), "defterde": 0, "kaydedilmemis": [],
                    "olculemedi": kapi_olculemedi},
        "satirlar": [],
        "kapsam_beyani": {
            "bakilanlar": [aciklama for _ad, aciklama, _fn in KURALLAR],
            "bakilmayanlar": list(BAKILMAYANLAR),
            "olculemedi": list(kapi_olculemedi),
        },
    }

    if not defter.exists():
        karne["guvenilmez"] = True
        karne["hukum"] = "GUVENILMEZ"
        karne["bozuk_satirlar"] = [[0, f"kapı defteri YOK: {defter}"]]
        return karne

    tum_kayitlar, bozuk = defter_oku(defter)
    # ⛔ BOZUK SATIRLAR SÜZGECE TABİ DEĞİLDİR: ayrıştırılamayan bir satırın `kosum`u da
    # okunamaz ve defterin BÜTÜNLÜĞÜ bir koşumun değil, dosyanın özelliğidir.
    kayitlar = [k for k in tum_kayitlar if satir_kapsamda(k, kosum, since)]
    karne["toplam_satir"] = len(tum_kayitlar)
    karne["okunan_satir"] = len(kayitlar)
    karne["satir_sayisi"] = len(kayitlar)
    karne["bozuk_satir_sayisi"] = len(bozuk)
    karne["bozuk_satirlar"] = [[n, m] for n, m in bozuk]

    gecen_kapilar = []
    for kayit in kayitlar:
        etkin, notlar, bayrak = satir_degerlendir(kayit, artefakt_kok)
        ad = kayit.get("kapi") if isinstance(kayit.get("kapi"), str) else None
        if ad:
            gecen_kapilar.append(ad)
            if kapilar.get(ad, {}).get("sinif") == "yazma":
                karne["yazma_sinifi_kapi"].append(ad)
                notlar.append("bu kapı YAZMA sınıfıdır (SAP'ye yazar) — ücretsiz bir ön kontrol değildir")
            elif ad not in kapilar:
                onek = ad.split(":", 1)[0] + ":"
                if any(o.startswith(onek) for o in kapi_olculemedi):
                    notlar.append(f"kapı adı doğrulanamadı — {onek} kayıt defteri ÖLÇÜLEMEDİ")
                else:
                    karne["bilinmeyen_kapi"].append(ad)
                    notlar.append("bu ad bizim kapı kayıt defterimizde YOK (var olmayan kapı adı)")
        if bayrak["gecersiz"]:
            karne["guvenilmez"] = True
        if bayrak["kapsam_bos"]:
            karne["kapsam_beyani_bos"] += 1
        if etkin in karne["sayim"] and not bayrak["gecersiz"]:
            karne["sayim"][etkin] += 1
        karne["satirlar"].append({
            "kapi": ad, "sonuc": kayit.get("sonuc"), "etkin": etkin,
            "artefakt": kayit.get("artefakt"), "kapsam": kayit.get("kapsam"),
            "test_sayisi": kayit.get("test_sayisi"), "dar_kapsam": bool(kayit.get("dar_kapsam")),
            "measured": kayit.get("measured"), "ts": kayit.get("ts"),
            "gecersiz": bayrak["gecersiz"], "notlar": notlar,
        })

    karne["kapilar"]["defterde"] = len(set(gecen_kapilar))
    karne["kapilar"]["kaydedilmemis"] = sorted(set(kapilar) - set(gecen_kapilar))
    karne["olculmemis"] = len(karne["kapilar"]["kaydedilmemis"])

    if bozuk:
        karne["guvenilmez"] = True
    if karne["guvenilmez"]:
        karne["hukum"] = "GUVENILMEZ"
    elif not kayitlar:
        karne["hukum"] = "OLCULMEDI"
    elif karne["sayim"]["fail"]:
        karne["hukum"] = "FAIL"
    elif (karne["sayim"]["warn"] or karne["sayim"]["not-run"] or karne["kapsam_beyani_bos"]
          or karne["bilinmeyen_kapi"] or kapi_olculemedi):
        karne["hukum"] = "WARN"
    elif karne["olculmemis"]:
        # ⛔ KISMI (kullanıcı kararı): bilinen kapıların bir kısmı HİÇ kaydedilmemişse bu "temiz"
        # değil, "eksik kapsam"dır — "ölçülemedi ≠ temiz" kuralının doğrudan karşılığı. Dipnotu
        # okumayan ya da JSON'dan yalnız `hukum` alan tüketici sahte güvence almamalı.
        # ⚠ Çıkış kodu 0 KALIR: eksik kapsam bir BAŞARISIZLIK değildir; `fail`/güvenilmezlik
        # kodlarıyla karışmaz. Öncelik: GUVENILMEZ > FAIL > WARN > KISMI > PASS.
        karne["hukum"] = "KISMI"
    else:
        karne["hukum"] = "PASS"
    return karne


def karne_cikis_kodu(karne: dict) -> int:
    if karne["hukum"] == "GUVENILMEZ":
        return 2
    return 1 if karne["hukum"] == "FAIL" else 0


ISARET = {"pass": "✓", "warn": "~", "fail": "✗", "not-run": "⊘"}


def karne_bas(karne: dict) -> None:
    print("=" * 78)
    print("KOD KALİTE KARNESİ  (RAPOR — bloklayıcı bir kapı DEĞİLDİR)")
    suz = karne["kapsam_suzgeci"]
    if suz.get("kosum") or suz.get("since"):
        parcalar = []
        if suz.get("kosum"):
            parcalar.append(f"kosum={suz['kosum']}")
        if suz.get("since"):
            parcalar.append(f"since={suz['since']}")
        print(f"KAPSAM: {' '.join(parcalar)} "
              f"(defterdeki {karne['toplam_satir']} satırın {karne['okunan_satir']}'i)")
    else:
        print(f"KAPSAM: TÜM DEFTER ({karne['toplam_satir']} satır) — süzgeç yok; eski bir "
              f"koşumun `fail`i de sayılır (`--kosum` / `--since` ile daralt)")
    print(f"Defter: {karne['defter']}")
    print(f"Üretim: {karne['uretim_ts']}")
    print("=" * 78)

    for s in karne["satirlar"]:
        isaret = "⛔" if s["gecersiz"] else ISARET.get(s["etkin"], "?")
        dusme = f"  ({s['sonuc']} → {s['etkin']})" if s["sonuc"] != s["etkin"] else ""
        print(f"\n{isaret} [{s['etkin']}] {s['kapi']}{dusme}")
        print(f"   artefakt: {s['artefakt'] or '— YOK —'}")
        print(f"   kapsam  : {s['kapsam'] if (s['kapsam'] or '').strip() else '— BOŞ —'}")
        for n in s["notlar"]:
            print(f"   ! {n}")
    if karne["bozuk_satirlar"]:
        print()
        for n, m in karne["bozuk_satirlar"]:
            print(f"⛔ defter satırı {n} okunamadı: {m}")

    print("\n" + "=" * 78)
    sayim = karne["sayim"]
    print(f"HÜKÜM: {karne['hukum']}   (satır: {karne['satir_sayisi']})")
    print(f"  pass {sayim['pass']} · warn {sayim['warn']} · fail {sayim['fail']} · "
          f"not-run {sayim['not-run']}"
          + (f" · GEÇERSİZ {sum(1 for s in karne['satirlar'] if s['gecersiz'])}"
             if any(s["gecersiz"] for s in karne["satirlar"]) else ""))
    print("  ⊘ `not-run` AYRI bir durumdur — `pass` sayılmaz, 'ölçülmedi' demektir.")
    if karne["kapsam_beyani_bos"]:
        print(f"  ⚠ {karne['kapsam_beyani_bos']} satırın KAPSAM BEYANI BOŞ — boş beyan "
              f"'her şey görüldü' diye okunur (D5).")
    if karne["bilinmeyen_kapi"]:
        print(f"  ⚠ kayıt defterinde OLMAYAN kapı adı: {', '.join(karne['bilinmeyen_kapi'])}")
    if karne["yazma_sinifi_kapi"]:
        print(f"  ⚠ YAZMA sınıfı kapı(lar) kullanıldı (SAP'ye yazar): "
              f"{', '.join(sorted(set(karne['yazma_sinifi_kapi'])))}")
    if karne["olculmemis"]:
        print(f"  ⊘ olculmemis={karne['olculmemis']} — bilinen "
              f"{karne['kapilar']['bilinen']} kapının {karne['olculmemis']}'i bu kapsamda HİÇ "
              f"kaydedilmemiş.")
    if karne["hukum"] == "KISMI":
        print("  ⊘ HÜKÜM KISMI: bulunan her şey temiz ama KAPSAM EKSİK — 'PASS' demek "
              "ölçülmeyen kapılar için güvence vermek olurdu.")
    if karne["hukum"] == "OLCULMEDI":
        print("  ⊘ DEFTERDE HİÇ SATIR YOK — bu 'temiz' DEĞİL, 'hiç ölçülmedi' demektir.")

    if karne["guvenilmez"]:
        print()
        print("█" * 78)
        print("█  ⛔  KARNE GÜVENİLMEZ — ÜRETİLEMEDİ SAYILIR (çıkış kodu 2)")
        print("█  Kanıtsız `pass` ya da okunamayan satır var: yukarıdaki ⛔ satırlarına bak.")
        print("█  Bu karne bir güvence BEYANI olarak KULLANILAMAZ.")
        print("█" * 78)

    kap = karne["kapilar"]
    print("\nKAPSAM BEYANI — BAKILANLAR:")
    for a in karne["kapsam_beyani"]["bakilanlar"]:
        print(f"  • {a}")
    print(f"  • kapı adları kayıt defteriyle eşleştirildi (bilinen {kap['bilinen']} kapı; "
          f"defterde {kap['defterde']} ayrı kapı)")
    print("KAPSAM BEYANI — BAKILMAYANLAR:")
    for a in karne["kapsam_beyani"]["bakilmayanlar"]:
        print(f"  • {a}")
    if kap["kaydedilmemis"]:
        print(f"  • bu koşumda HİÇ KAYIT GİRMEMİŞ kapı sayısı: {len(kap['kaydedilmemis'])} "
              f"(ilk 5: {', '.join(kap['kaydedilmemis'][:5])})")
    if karne["kapsam_beyani"]["olculemedi"]:
        print("KAPSAM BEYANI — ÖLÇÜLEMEDİ (sessizce atlanmadı):")
        for a in karne["kapsam_beyani"]["olculemedi"]:
            print(f"  • {a}")
    print("=" * 78)


# ── CLI ──────────────────────────────────────────────────────────────────────────────────────────

def _kaydet(args) -> int:
    defter = defter_yolu(args.defter)
    measured, sebep = (None, None)
    if args.durum_ciktisi:
        try:
            ham = (sys.stdin.read() if args.durum_ciktisi == "-"
                   else Path(args.durum_ciktisi).read_text(encoding="utf-8", errors="replace"))
        except OSError as e:
            print(f"HATA: durum çıktısı okunamadı: {e}", file=sys.stderr)
            return 2
        measured, sebep = durum_beyani(ham, args.gate or gate_adi_turet(args.kapi))

    kayit = {
        "ts": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "kapi": args.kapi,
        "sonuc": args.sonuc,
        "artefakt": args.artefakt,
        "kapsam": args.kapsam,
        "test_sayisi": args.test_sayisi,
        "dar_kapsam": bool(args.dar_kapsam),
        "measured": measured,
        "measured_reason": sebep,
        "komut": args.komut,
        # Koşum kimliği: `--kosum` → env `AXET_KARNE_KOSUM` → üretilen. Aynı işin satırlarını
        # gruplamak için kabuğa bir kez `AXET_KARNE_KOSUM` yazmak yeter; verilmezse her satır
        # kendi kimliğini alır (gruplanamaz — ve karne bunu gizlemez).
        "kosum": (args.kosum or os.environ.get("AXET_KARNE_KOSUM")
                  or f"{_dt.datetime.now(_dt.timezone.utc):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:6]}"),
    }
    try:
        satir_ekle(defter, kayit, kilit_saniye=args.kilit_saniye)
    except KilitAlinamadi as e:
        print(f"HATA: {e}", file=sys.stderr)
        return 3
    except OSError as e:
        print(f"HATA: kapı defterine yazılamadı ({defter}): {e}", file=sys.stderr)
        return 2

    # Yazma anı doğrulaması. ⛔ Satır YİNE DE yazıldı: defter bir olay kaydıdır, reddedilen iddia da
    # tarihe geçer. Aynı doğrulama OKUMA anında tekrar koşar (D6 arka durağı).
    _etkin, notlar, bayrak = satir_degerlendir(kayit, Path(args.artefakt_kok or os.getcwd()))
    print(f"kapı defterine eklendi: {defter}")
    for n in notlar:
        print(f"  ! {n}", file=sys.stderr)
    if bayrak["gecersiz"]:
        print("UYARI: bu satır sözleşmeye AYKIRI (kanıtsız `pass`) — karne bunu GÜVENİLMEZ sayacak.",
              file=sys.stderr)
        return 2
    return 0


def _karne(args) -> int:
    defter = defter_yolu(args.defter)
    karne = karne_uret(defter, Path(args.artefakt_kok or os.getcwd()), Path(args.kok or KOK),
                       kosum=args.kosum, since=args.since)
    if args.json_cikti:
        print(json.dumps(karne, ensure_ascii=False, indent=2))
    else:
        karne_bas(karne)
        if not defter.exists():
            print(f"\n⛔ KARNE ÜRETİLEMEDİ — kapı defteri YOK: {defter}", file=sys.stderr)
    return karne_cikis_kodu(karne)


def _kapilar(args) -> int:
    kapilar, olculemedi = kapi_defteri(Path(args.kok or KOK))
    if args.json_cikti:
        print(json.dumps({"kapilar": kapilar, "olculemedi": olculemedi}, ensure_ascii=False, indent=2))
    else:
        for ad in sorted(kapilar):
            print(f"{ad:58s} sinif={kapilar[ad]['sinif']:10s} kaynak={kapilar[ad]['kaynak']}")
        print(f"\nTOPLAM: {len(kapilar)} kapı (koddan türetildi)")
        print("KAPSAM — bakılmayanlar: kapının gerçekten KOŞTUĞU · zincire kayıtlı olduğu · "
              "adı geçen aracın canlı sistemde çalıştığı")
        for a in olculemedi:
            print(f"ÖLÇÜLEMEDİ: {a}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Kapı defteri (append-only) + kod kalite karnesi — RAPOR, gate DEĞİL")
    alt = ap.add_subparsers(dest="komut_adi", required=True)

    k = alt.add_parser("kaydet", help="kapı defterine bir satır EKLE (append-only)")
    k.add_argument("--kapi", required=True, help="kapı adı (ör. validator:check_abaplint)")
    k.add_argument("--sonuc", required=True, choices=list(GECERLI_SONUC))
    k.add_argument("--artefakt", default=None, help="kanıt dosyası yolu (pass için ZORUNLU)")
    k.add_argument("--kapsam", default="", help="kapsam notu: neye bakıldı, neye BAKILMADI")
    k.add_argument("--test-sayisi", type=int, default=None, dest="test_sayisi",
                   help="koşan test sayısı (0 → `pass` olamaz); test saymayan kapıda verme")
    k.add_argument("--dar-kapsam", action="store_true", dest="dar_kapsam",
                   help="varsayılan/dar kapsamla koşuldu (ör. varsayılan ATC varyantı)")
    k.add_argument("--komut", default=None, help="koşulan komut (kablolama kanıtı)")
    k.add_argument("--durum-ciktisi", default=None, dest="durum_ciktisi",
                   help="aracın stdout'u (dosya ya da '-'): AXET-GATE-STATUS/ABAPLINT-RUN-STATUS okunur")
    k.add_argument("--gate", default=None,
                   help="AXET-GATE-STATUS `gate=` alanı (varsayılan: --kapi'nin namespace sonrası)")
    k.add_argument("--kosum", default=None,
                   help="koşum kimliği (varsayılan: env AXET_KARNE_KOSUM ya da üretilir)")
    k.add_argument("--kilit-saniye", type=float, default=10.0, dest="kilit_saniye",
                   help="defter kilidi için bekleme (alınamazsa YAZMA YOK, rc=3)")
    k.add_argument("--defter", default=None)
    k.add_argument("--artefakt-kok", default=None, dest="artefakt_kok")
    k.set_defaults(fn=_kaydet)

    r = alt.add_parser("karne", help="defterden karne üret (defteri DEĞİŞTİRMEZ)")
    r.add_argument("--defter", default=None)
    r.add_argument("--json", action="store_true", dest="json_cikti")
    r.add_argument("--artefakt-kok", default=None, dest="artefakt_kok",
                   help="göreli artefakt yollarının çözüleceği kök (varsayılan: cwd)")
    r.add_argument("--kok", default=None, help="template kökü (kapı kayıt defteri için)")
    r.add_argument("--kosum", default=None,
                   help="YALNIZ bu koşumun satırlarını oku (varsayılan: TÜM defter)")
    r.add_argument("--since", default=None,
                   help="bu zaman damgasından itibaren oku, ör. 2026-09-15 (varsayılan: TÜM defter)")
    r.set_defaults(fn=_karne)

    g = alt.add_parser("kapilar", help="koddan türetilmiş kapı kayıt defterini yaz")
    g.add_argument("--json", action="store_true", dest="json_cikti")
    g.add_argument("--kok", default=None)
    g.set_defaults(fn=_kapilar)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
