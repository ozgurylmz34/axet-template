#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""aXet tüketici güncelleme motoru — `%guncelle` akışının hükmünü veren script.

TASARIM: `maintenance/guncelle-mimari/TASARIM.md` §2 (taban) · §3 (harita) · §4 (vaka kodları) ·
§5 (kartlar) · §6 (plan/durum sözleşmesi) · §7 (akış) · §8 (bütünlük turu). Bu dosya o belgenin
UYGULAMASIDIR; sözleşme (alan adları, çıkış kodları, vaka kodları) oradan gelir.

⛔ K4 — MOTOR KENDİ KENDİNE YETER: `%guncelle` bu dosyayı ve `guncelle/**`'yi `git show
origin/main:` ile repo DIŞI geçici bir dizine çıkarıp oradan çalıştırır. Bu yüzden klondaki
(eski sürüm olabilecek) `scripts/*.py` modülleri **import EDİLMEZ**; klondaki araçlar yalnız
ALT SÜREÇ olarak çalıştırılır (`butunluk`, `ozel-adim`). Bu dosya **hiçbir yerel modülü import
etmez** — yalnız stdlib kullanır.

⚠ `guncelle/siniflandir.py` de import EDİLMEZ (eski docstring "tek import edilen yardımcı" diyordu;
ölçüldü, öyle değildi). Sebep K4 değil API farkıdır: `siniflandir.siniflandir()` SINIF ADINI
döndürür, motorun ihtiyacı olan `sinif_bul()` ise `etkin`/`esler`/`test`/`ozel_adim` alanlarını
taşıyan KAYDI döndürür ⇒ ikisi tek fonksiyona indirilemez. Eşleşme kuralı (harita sırası, ilk
eşleşen kazanır) iki gövdede ayrı yazılıdır ve zamanla SESSİZCE ayrışabilir; bu risk
`tests/test_guncelle.py::SiniflandirmaTekKaynakTest` ile mekanik olarak kapatılır (izlenen TÜM
yollarda iki gerçekleştirmenin aynı sınıfı verdiğini ölçer).

Kullanım:
    python scripts/guncelle.py --klon <klon> <altkomut> [...]

Alt komutlar (§6): onkontrol · hazirla · plan · sec · olc · uygula · oneri · isaretle ·
ozel-adim · butunluk · geri-al · kapanis · durum · kart

Çıkış kodları alt komut başına değişir; §6 tablosuna birebir uyar.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime
import difflib
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass

BURASI = Path(__file__).resolve().parent
MOTOR_KOK = BURASI.parent                      # motorun kendi kopyasının kökü (geçici olabilir)
DURUM_DIZIN_ADI = ".axet-guncelleme"
RESMI_ORIGIN = "https://github.com/ozgurylmz34/axet-template.git"
# ⚠ DÖRT işaret: `git merge-file --diff3` (bkz. `birlestir`) ÜÇ değil DÖRT satır üretir ve
# dördüncüsü `||||||| TABAN:<yol>` bloğudur. Dördüncüsü listede yokken üçünü silip TABAN bloğunu
# bırakan bir öneri dosyası `dogrulandi` sayılıyordu ⇒ tabanın ESKİ satırları sessizce birleşmiş
# içeriğe karışıyordu (P3 doküman gate'i 2026-09-18; kart `guncelle/kartlar/V4c.md:39-40,52-54`
# kullanıcıya "dördünü de sil, kalırsa FAIL" diye söz veriyordu — söz kodda karşılanmamıştı).
CAKISMA_ISARETLERI = ("<<<<<<<", "|||||||", "=======", ">>>>>>>")


# Git işareti YALNIZ satır başında durur: `<<<<<<< ad`, `||||||| ad`, `>>>>>>> ad` (ad isteğe
# bağlı) ve TEK BAŞINA `=======`. ⛔ Alt-dizi araması yanlıştı (v0.4.1, gerçek güncellemede
# ölçüldü): `# =====…` ayracı taşıyan 7 ürün dosyası — motorun kendisi dahil — FAIL veriyordu.
_CAKISMA_DESENI = re.compile(
    r"^(<<<<<<<|\|\|\|\|\|\|\||>>>>>>>)(?:[ \t].*)?\r?$|^(=======)[ \t]*\r?$", re.M)


def _isaret_sayilari(metin: str) -> dict[str, int]:
    sayac: dict[str, int] = {}
    for m in _CAKISMA_DESENI.finditer(metin):
        i = m.group(1) or m.group(2)
        sayac[i] = sayac.get(i, 0) + 1
    return sayac


def cakisma_isaretleri(metin: str, referans: str | None = None) -> list[str]:
    """Metinde satır başında duran git çakışma işaretleri (tekrarsız, `CAKISMA_ISARETLERI` sırasıyla).

    `referans` (yayının o dosyadaki içeriği) verilirse yalnız referanstakinden FAZLA olan işaretler
    sayılır: ürünün kendisi satır başında işaret taşıyabilir (`guncelle/kartlar/V4c.md` örnek
    bloğu — bug gate 2026-09-21) ve yayınla bayt-bayt aynı dosya "çakışma kaldı" sayılmamalı.
    Gerçek bir çakışma bloğu her işaretten en az birini EKLER ⇒ sayı karşılaştırması onu kaçırmaz.
    """
    sayac = _isaret_sayilari(metin)
    taban = _isaret_sayilari(referans) if referans is not None else {}
    return [i for i in CAKISMA_ISARETLERI if sayac.get(i, 0) > taban.get(i, 0)]

# §10/§2a: tüketicide git kimliği tanımsız olabilir → her yazan commit kendi kimliğini taşır.
GIT_KIMLIK = ["-c", "user.name=axet-guncelle", "-c", "user.email=guncelle@yerel"]

# K6(a) ayrışma eşiği: >3 çakışma bloğu YA DA yerel fark >%50 → birleştirme DENENMEZ.
ESIK_CAKISMA_BLOGU = 3
ESIK_YEREL_FARK = 0.50

# §4: işlem gerektirmeyen kodlar — plan bunları LİSTELEMEZ, yalnız sayar (§5 "işlem yok").
ISLEMSIZ_VAKALAR = {"V0", "V3", "V2e", "V4e", "V5s", "V6x", "VKD"}
# `uygula --otomatik`'in yazdıkları (§7 adım 7).
OTOMATIK_VAKALAR = {"V1", "V2", "V5", "V6", "V1R"}
# Yargı isteyen vakalar (§7 adım 8).
YARGI_VAKALARI = {"V4t", "V4c", "V4c+ESIK", "V4B", "V4R", "V6d", "V7", "VTB"}

GECERLI_KARARLAR = ("birlesik", "yerel", "yeni", "yeniden-adlandir", "ertelendi")

# VAKA ↔ İZİNLİ KARAR (TASARIM §5 kartlarından birebir; kapsam: YARGI vakaları).
# ⛔ Neden gerekli: `GECERLI_KARARLAR` yalnız "böyle bir karar var mı" der, "bu vakada geçerli
# mi" DEMEZ. §5'in V7 kartı yalnız `yeniden-adlandir|yerel` tanımlarken kod `--karar yeni`yi de
# kabul ediyordu; `yeni` ise kullanıcının YEDEKLENMEMİŞ dosyasını (izlenmeyen ⇒ `hazirla`nın
# `git add -u`'su onu commit'lemez ⇒ `guncelle-oncesi-*` etiketinde blob'u YOKTUR) geri
# alınamaz biçimde eziyordu. Kontrol grubu aynı dosyada vardı: `--karar yeniden-adlandir`
# içeriği `.yerel` olarak KORUYOR ⇒ kod bunu yapabiliyordu, yalnız bu yolda yapmıyordu.
# `ertelendi` HER vakada geçerlidir (§6 `atlandi(gerekce)`); burada listelenmez.
# Listede OLMAYAN bir vaka (V1/V2/V5/V6 gibi otomatikler) daraltılmaz — §5 onlar için karar
# kartı tanımlamıyor, dolayısıyla kanıtsız daraltma olurdu.
VAKA_IZINLI_KARARLAR: dict[str, set[str]] = {
    "V4t": {"birlesik", "yerel", "yeni"},
    "V4c": {"birlesik", "yerel", "yeni"},
    "V4c+ESIK": {"yerel", "yeni"},          # §5: birleştirme DENENMEDİ ⇒ öneri dosyası yok
    "V4B": {"yerel", "yeni"},               # §5: ikili dosya, birleştirme yok
    "V4R": {"birlesik", "yerel", "yeni"},   # §5: "V4t/V4c kartı, hedef yol yeni ad"
    "V6d": {"yerel"},                       # §5: "dokunma, bilgi ver"
    "V7": {"yeniden-adlandir", "yerel"},    # §5 V7 kartı adım 2-3
    "VTB": {"yerel", "yeni"},               # §4: otomatik birleştirme YASAK (taban uydurma)
}


# =====================================================================================================
# `etkin`in BEŞ değeri — D17'de kayıtlı tuzak
# =====================================================================================================
# harita.json `etkin_degerleri` BEŞ değerlidir ve beşincisi `null`'dur (2026-09-17 ölçümü: 38
# sınıfın 13'ü null). `null` = "bu dosyanın aXet davranışına giren AYRI bir etkinleşme anı YOKTUR"
# (TASARIM §3): ya dosya hiç yüklenmez (LICENSE, belge), ya da etkinleşmesi aXet oturumunun
# DIŞINDAKİ bir kullanıcı eylemine bağlıdır (`kur.ps1`'in bir sonraki elle çalıştırılması).
# ⛔ Dört değer varsayan bir if/elif zinciri o 13 sınıfı SESSİZCE "bilinmeyen" kovasına düşürür.
# Bu yüzden eşleme AÇIK bir sözlüktür ve bilinmeyen bir değer SESSİZ DÜŞMEZ, patlar (fail-loud).
ETKIN_DAVRANIS: dict[str | None, dict] = {
    "aninda": {"yeniden_baslat": None,
               "aciklama": "değişiklik anında geçerli; yeniden başlatma gerekmez"},
    "skill-cagrisi": {"yeniden_baslat": None,
                      "aciklama": "skill bir sonraki çağrısında yeni gövdeyi okur"},
    "yeni-oturum": {"yeniden_baslat": "yeni-oturum",
                    "aciklama": "bağlam oturum başında yüklenir → aXet'i kapat-aç"},
    "install-sonra-yeni-oturum": {"yeniden_baslat": "install-sonra-yeni-oturum",
                                  "aciklama": "önce scripts/install.py, sonra aXet'i kapat-aç"},
    None: {"yeniden_baslat": None,
           "aciklama": "ayrı bir etkinleşme anı yok (hiç yüklenmez ya da etkinleşmesi aXet "
                       "oturumunun dışındaki bir kullanıcı eylemine bağlıdır)"},
}
YENIDEN_BASLAT_SIRA = [None, "yeni-oturum", "install-sonra-yeni-oturum"]


class BilinmeyenEtkin(Exception):
    """harita.json'a motorun tanımadığı bir `etkin` değeri girmiş — sessizce yutulmaz."""


def etkin_davranis(deger):
    """`etkin` → davranış kaydı. Bilinmeyen değer SESSİZ DÜŞMEZ (D17 tuzağı)."""
    try:
        return ETKIN_DAVRANIS[deger]
    except (KeyError, TypeError):
        raise BilinmeyenEtkin(
            f"harita.json'daki `etkin` değeri motorda ele alınmıyor: {deger!r}. "
            f"Bilinenler: {sorted(str(k) for k in ETKIN_DAVRANIS)}. "
            "Yeni bir değer eklendiyse scripts/guncelle.py ETKIN_DAVRANIS sözlüğü de "
            "güncellenmelidir (TASARIM §3 + D17)."
        ) from None


# =====================================================================================================
# temel yardımcılar
# =====================================================================================================
class Dur(Exception):
    """Akışı durduran, kullanıcıya aynen gösterilecek sebep."""

    def __init__(self, sebep: str, kod: int = 2) -> None:
        super().__init__(sebep)
        self.kod = kod


def _run(args: list[str], cwd: Path, ikili: bool = False,
         env: dict | None = None, timeout: int = 1800) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(cwd), capture_output=True, env=env, timeout=timeout,
                          stdin=subprocess.DEVNULL,
                          **({} if ikili else {"text": True, "encoding": "utf-8",
                                               "errors": "replace"}))


class Klon:
    """Tüketici klonu üzerindeki git işlemleri (motorun tek durum kaynağı)."""

    def __init__(self, kok: Path) -> None:
        self.kok = kok.resolve()
        self.durum_dizini = self.kok / DURUM_DIZIN_ADI
        # Toplu okuma önbelleği (Z31) — YALNIZ `toplu_okuma` bloğunun içinde dolu, dışında None.
        self._agaclar: dict[str, dict[str, str]] | None = None
        self._disk: dict[str, str] | None = None
        self._refler: dict[str, str | None] = {}

    @contextlib.contextmanager
    def toplu_okuma(self, yollar):
        """Plan turunda blob/disk hash'lerini TEK git çağrısıyla okur (Z31, 2026-09-21).

        ⛔ NEDEN: plan, 476 dosyalık kapsam için dosya başına 3 git süreci başlatıyordu (iki
        `rev-parse <ref>:<yol>` + bir `hash-object`) — ölçüldü: 1455 süreç, 76.3 sn; Windows'ta
        süreç başlatma başına ~52 ms. Ref başına tek `ls-tree -r -t` + disk için tek
        `hash-object --stdin-paths` aynı cevabı verir.
        ⛔ KAPSAM BİLİNÇLİ OLARAK DAR: disk hash'i önbelleklenirse bir YAZIMDAN sonra bayat değer
        döner ve doğrulama sessizce körleşir ⇒ önbellek yalnız bu bloğun içinde yaşar, blok
        içinde klona yazan kod çağrılmamalıdır (plan turu yazmaz). Önbellekte OLMAYAN her soru
        eski tek-tek yola düşer (fail-safe: hız kaybı, doğruluk kaybı değil).
        """
        self._agaclar, self._disk, self._refler = {}, {}, {}
        try:
            dosyalar = [y for y in sorted(set(yollar)) if (self.kok / y).is_file()]
            if dosyalar:
                r = subprocess.run(["git", "-C", str(self.kok), "hash-object", "--stdin-paths"],
                                   cwd=str(self.kok), input="\n".join(dosyalar) + "\n",
                                   capture_output=True, text=True, encoding="utf-8",
                                   errors="replace")
                satirlar = r.stdout.split()
                # Tek dosya okunamazsa git TÜM çağrıyı düşürür ⇒ önbellek boş kalır ve her dosya
                # tek-tek yoldan ölçülür (orada okunamayan dosya `Dur` ile açıkça durur).
                if r.returncode == 0 and len(satirlar) == len(dosyalar):
                    self._disk = dict(zip(dosyalar, satirlar))
            yield
        finally:
            self._agaclar, self._disk, self._refler = None, None, {}

    def _agac(self, ref: str) -> dict[str, str] | None:
        """`ref` ağacının yol → nesne sha eşlemi (tree girdileri DAHİL: `rev-parse ref:dizin` de
        tree sha döndürür). Anahtar ÇÖZÜLMÜŞ commit'tir: ad aynı kalıp hedef kayarsa karışmasın."""
        if ref not in self._refler:   # blok içinde ref'ler kaymaz (plan fetch/commit yapmaz)
            c = self.git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
            self._refler[ref] = c.stdout.strip() if c.returncode == 0 else None
        sha = self._refler[ref]
        if not sha:
            return None
        if sha not in self._agaclar:
            r = self.git("ls-tree", "-r", "-t", "-z", "--full-tree", sha)
            if r.returncode != 0:
                return None
            esle: dict[str, str] = {}
            for girdi in r.stdout.split("\0"):
                if "\t" in girdi:
                    bas, yol = girdi.split("\t", 1)
                    esle[yol] = bas.split()[2]
            self._agaclar[sha] = esle
        return self._agaclar[sha]

    # --- git ---------------------------------------------------------------------------------
    def git(self, *args: str, kontrol: bool = False, ikili: bool = False,
            kimlik: bool = False) -> subprocess.CompletedProcess:
        komut = ["git", "-C", str(self.kok)] + (GIT_KIMLIK if kimlik else []) + list(args)
        r = _run(komut, self.kok, ikili=ikili)
        if kontrol and r.returncode != 0:
            hata = r.stderr if isinstance(r.stderr, str) else r.stderr.decode("utf-8", "replace")
            raise Dur(f"git {' '.join(args)} başarısız (rc={r.returncode}): {hata.strip()}")
        return r

    def g(self, *args: str) -> str:
        return self.git(*args, kontrol=True).stdout.strip()

    def var_mi(self, ref: str) -> bool:
        return self.git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}").returncode == 0

    def ls_tree(self, ref: str) -> set[str]:
        r = self.git("ls-tree", "-r", "--name-only", "-z", ref)
        if r.returncode != 0:
            return set()
        return {y for y in r.stdout.split("\0") if y}

    def blob_sha(self, ref: str, yol: str) -> str | None:
        if self._agaclar is not None:
            agac = self._agac(ref)
            if agac is not None:
                return agac.get(yol)
        r = self.git("rev-parse", "--verify", "--quiet", f"{ref}:{yol}")
        return r.stdout.strip() or None

    def izlenen_yollar(self, yollar: list[str]) -> set[str]:
        """Verilen yollardan INDEX'te İZLENENLER.

        ⚠ Neden HEAD değil index: `git add <pathspec>` eşleşmeyi ÇALIŞMA AĞACI + INDEX
        üzerinde yapar, HEAD'e BAKMAZ. "Bu yolu `git add` eşleştirebilir mi" sorusunun index
        yarısı budur; disk yarısı `(kok / yol).exists()`tir. İkisinin birleşimi dışındaki her
        pathspec `git add`i `fatal` ile düşürür ve o çağrıda HİÇBİR yol stage EDİLMEZ.
        """
        if not yollar:
            return set()
        r = self.git("ls-files", "-z", "--", *yollar)
        if r.returncode != 0:
            return set()
        return {y for y in r.stdout.split("\0") if y}

    def blob(self, sha: str) -> bytes:
        r = self.git("cat-file", "blob", sha, ikili=True)
        if r.returncode != 0:
            raise Dur(f"blob okunamadı: {sha}")
        return r.stdout

    def disk_sha(self, yol: str) -> str | None:
        """Çalışma ağacındaki dosyanın git-normalize edilmiş blob hash'i.

        ⚠ Neden `hash-object --path`: `.gitattributes` `text=auto`/`eol=crlf` yüzünden çalışma
        ağacındaki baytlar depodakinden farklı olabilir (`kur.cmd` CRLF). Ham bayt karşılaştırması
        her CRLF'li dosyayı "değişmiş" gösterirdi. `--path` aynı temizleme (clean) filtresini
        uygular ⇒ karşılaştırma git'in gördüğü düzlemde yapılır.
        """
        tam = self.kok / yol
        if not tam.is_file():
            return None
        if self._disk is not None and yol in self._disk:
            return self._disk[yol]
        r = self.git("hash-object", "--path", yol, "--", str(tam))
        sha = r.stdout.strip()
        if r.returncode != 0 or not sha:
            # ⛔ Dosya VAR ama hash'lenemedi. None döndürmek "dosya yok" demektir: V7 → V2
            # (otomatik ezme) olur ve `_yedeksiz_mi` "ezilecek içerik yok" deyip yedek almaz.
            raise Dur(f"`git hash-object {yol}` başarısız (rc={r.returncode}): "
                      f"{' '.join((r.stderr or '').split())[:300]} — dosya diskte VAR ama "
                      f"okunamadı; durumu ÖLÇÜLEMEDİ, dokunulmadı.")
        return sha

    def stdin_sha(self, yol: str, veri: bytes) -> str:
        komut = ["git", "-C", str(self.kok), "hash-object", "--path", yol, "--stdin"]
        r = subprocess.run(komut, cwd=str(self.kok), input=veri, capture_output=True)
        sha = r.stdout.decode("ascii", "replace").strip()
        if r.returncode != 0 or not sha:
            raise Dur(f"`git hash-object --stdin` ({yol}) başarısız (rc={r.returncode})")
        return sha

    def crlf_mi(self, yol: str) -> bool:
        r = self.git("check-attr", "eol", "--", yol)
        return "eol: crlf" in (r.stdout or "")

    # --- çalışma ağacına yazma ---------------------------------------------------------------
    def yaz(self, yol: str, veri: bytes) -> None:
        """Baytları çalışma ağacına yazar; `eol=crlf` beyanlı dosyada satır sonunu dönüştürür."""
        tam = self.kok / yol
        tam.parent.mkdir(parents=True, exist_ok=True)
        gov = veri.replace(b"\r\n", b"\n")
        if self.crlf_mi(yol):
            gov = gov.replace(b"\n", b"\r\n")
        tam.write_bytes(gov)

    def checkout_yol(self, ref: str, yol: str) -> None:
        """Dosyayı `ref`ten çalışma ağacına yazar — git kendi smudge/eol dönüşümünü uygular."""
        (self.kok / yol).parent.mkdir(parents=True, exist_ok=True)
        self.git("checkout", ref, "--", yol, kontrol=True)

    def sil(self, yol: str) -> None:
        tam = self.kok / yol
        if tam.is_file():
            tam.unlink()
        self.git("rm", "-q", "--cached", "--ignore-unmatch", "--", yol)
        ana = tam.parent
        while ana != self.kok and ana.is_dir() and not any(ana.iterdir()):
            ana.rmdir()
            ana = ana.parent


def yayin_durumu(git_rc, etiket: str) -> str:
    """Bir yayının klonda İÇERİLİP içerilmediği — TEK KAYNAK (K-F, 2026-09-18).

    `git_rc(*args) -> int` çağıranın git koşucusudur (motor `Klon.git`, `session_brief` kendi
    kısa zaman aşımlı `_git`i) — ölçüm kuralı ortak, koşucu değil. Döner:
      "icerildi"   etiket HEAD'in atası (taze klon / yayından sonra `kur.cmd` ile çekilmiş)
      "bekliyor"   etiket çözülüyor ama HEAD'de değil (ya da ata testi hata verdi — güvenli taraf)
      "cozulemedi" etiket klonda yok ⇒ içerilip içerilmediği ÖLÇÜLEMEZ
    Neden ortak: `session_brief` ata testini YAPMIYORDU ⇒ yayını zaten içeren taze klonda
    "1 güncelleme kalemi bekliyor" satırı `%guncelle` sonrasında bile KALICI kalıyordu
    (motor o yayını plana hiç almadığı için kalem hiçbir zaman `uygulandi` olmuyordu).
    """
    if not etiket or git_rc("rev-parse", "--verify", "--quiet", f"{etiket}^{{commit}}") != 0:
        return "cozulemedi"
    if git_rc("merge-base", "--is-ancestor", etiket, "HEAD") == 0:
        return "icerildi"
    return "bekliyor"


# --- durum dizini I/O -------------------------------------------------------------------------
SOZLESME_SURUMU = 1  # §6 durum dosyalarının şema sürümü (plan.json / durum.json / uygulanan.json)


def _surum_dogrula(ad: str, veri):
    """§6 şema sürümü kontrolü. `surum` alanı YAZILIYOR ama hiç OKUNMUYORDU.

    Ölçülen sonuç: `uygulanan.json`'a `surum: 2` verilince motor onu sessizce v1 gibi okuyor,
    beklediği alanları bulamayınca `dosyalar` BOŞ dönüyor ⇒ dosya-başı taban sessizce
    merge-base'e düşüyor ⇒ §2a'nın ÖNLEMEK için var olduğu yanlış çakışma geri geliyor.
    İleri uyumluluk YOKTUR: daha yeni bir şemayı eski alan adlarıyla okumak sessiz kayıptır.
    """
    if isinstance(veri, dict):
        s = veri.get("surum", SOZLESME_SURUMU)
        if isinstance(s, int) and s > SOZLESME_SURUMU:
            raise Dur(f"{ad}: `surum` {s} — bu motor yalnız surum {SOZLESME_SURUMU} şemasını "
                      f"okur. Daha yeni şemayı eski alan adlarıyla okumak SESSİZ veri kaybıdır "
                      f"(taban merge-base'e düşer, §2a'nın önlediği yanlış çakışma geri gelir). "
                      f"Motoru tazele (`git -C <klon> fetch --tags origin`) ya da {ad} "
                      f"dosyasını kaldır.")
    return veri


def _oku(yol: Path, varsayilan):
    if not yol.is_file():
        return varsayilan
    try:
        veri = json.loads(yol.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return varsayilan
    return _surum_dogrula(yol.name, veri)


def _plan_muhru(plan: dict) -> dict:
    """Döngü kimliği (K2 kararı 2026-09-20): bu durum dosyası HANGİ turun ürünü.

    `durum_dizini`'ni temizleyen HİÇBİR yer yok (20 kullanım tarandı) ve bu BİLERÇEDİR:
    `uygulanan.json` döngüler-üstüdür (`:458`), kör temizlik onu götürürdü. Dolayısıyla
    çare SİLMEK değil MÜHÜRLEMEK: döngü-kapsamlı dosya kendi turunu söyler, kapanış
    uymayanı "koştu" saymaz — "ÖLÇÜLMEDİ" sayar (ölçülmedi ≠ temiz).
    """
    return {"taban_commit": plan.get("taban_commit"), "yeni_etiket": plan.get("yeni_etiket")}


def _muhur_sorunu(ad: str, veri: dict | None, plan: dict) -> str | None:
    """None = mühür UYUYOR. Aksi hâlde neden. (`veri is None` çağıranın dalıdır.)"""
    if veri is None:
        return None
    m = veri.get("plan")
    if not isinstance(m, dict):
        return f"{ad} plan damgası TAŞIMIYOR (önceki sürümden kalmış olabilir)"
    bekl = _plan_muhru(plan)
    if m != bekl:
        return (f"{ad} BAŞKA bir güncelleme turuna ait — damga "
                f"`{m.get('yeni_etiket')}`/{str(m.get('taban_commit'))[:10]}, "
                f"bu tur `{bekl['yeni_etiket']}`/{str(bekl['taban_commit'])[:10]}")
    return None


def _yaz_json(yol: Path, veri) -> None:
    """Yazar ve GERİ OKUYUP doğrular (`install.py:297-299` deseni, §6)."""
    yol.parent.mkdir(parents=True, exist_ok=True)
    metin = json.dumps(veri, ensure_ascii=False, indent=1, sort_keys=False) + "\n"
    yol.write_text(metin, encoding="utf-8")
    if json.loads(yol.read_text(encoding="utf-8")) != veri:
        raise Dur(f"HATA: {yol.name} yazıldı ama geri okunduğunda farklı çıktı.")


def _simdi() -> str:
    """Saat dilimli yerel an (Z65): `_kayit_tuketildi_mi` damgaları AN olarak karşılaştırır."""
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


# =====================================================================================================
# harita
# =====================================================================================================
def harita_yukle(ozel: Path | None = None) -> dict:
    """Motorun KENDİ kopyasındaki harita (K4: klondakine güvenilmez)."""
    if ozel:
        return json.loads(ozel.read_text(encoding="utf-8"))
    aday = MOTOR_KOK / "guncelle" / "harita.json"
    if not aday.is_file():
        raise Dur(f"harita.json bulunamadı: {aday} (motor kopyası eksik — K4 §6)")
    return json.loads(aday.read_text(encoding="utf-8"))


def sinif_bul(yol: str, harita: dict) -> dict | None:
    for kayit in harita["siniflar"]:
        if any(fnmatch.fnmatchcase(yol, d) for d in kayit["glob"]):
            return kayit
    return None


# =====================================================================================================
# §4 — VAKA KODLARI
# =====================================================================================================
def vaka_kodu(t_sha: str | None, l_sha: str | None, y_sha: str | None,
              taban_var: bool) -> str:
    """§4 tablosu, birebir. T/L/Y = taban/yerel/yeni blob hash'i (None = o sürümde dosya yok)."""
    if not taban_var:
        return "VTB"
    if t_sha is not None:
        if l_sha == t_sha:
            if y_sha == t_sha:
                return "V0"
            return "V6" if y_sha is None else "V1"
        if l_sha is None:
            if y_sha == t_sha:
                return "V5s"
            return "V6x" if y_sha is None else "V5"
        # L ≠ T
        if y_sha == t_sha:
            return "V3"
        if y_sha is None:
            return "V6d"
        if l_sha == y_sha:
            return "V4e"
        return "V4"
    # taban YOK
    if l_sha is None:
        return "V2" if y_sha is not None else "V0"
    if y_sha is None:
        return "VKD"
    return "V2e" if l_sha == y_sha else "V7"


IKILI_UZANTI = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".exe", ".xlsx", ".docx"}


def ikili_mi(klon: Klon, yol: str, ornekler: list[bytes]) -> bool:
    """`.gitattributes` binary satırları (TASARIM §4 +B) ya da içerikte NUL."""
    if Path(yol).suffix.lower() in IKILI_UZANTI:
        return True
    r = klon.git("check-attr", "binary", "--", yol)
    if "binary: set" in (r.stdout or ""):
        return True
    return any(b"\0" in (o or b"")[:8000] for o in ornekler)


def _satirlar(veri: bytes) -> list[str]:
    return veri.decode("utf-8", "replace").replace("\r\n", "\n").splitlines(keepends=True)


def yerel_fark_orani(t: bytes, l: bytes) -> float:
    ts, ls = _satirlar(t), _satirlar(l)
    if not ts:
        return 1.0 if ls else 0.0
    degisen = sum(1 for s in difflib.unified_diff(ts, ls, n=0)
                  if s[:1] in "+-" and not s.startswith(("---", "+++")))
    return min(1.0, degisen / max(1, len(ts)))


def birlestir(klon: Klon, yol: str, t: bytes, l: bytes, y: bytes) -> tuple[bytes, int]:
    """`git merge-file` ile 3-yollu birleştirme. Döner: (içerik, çakışma sayısı).

    ⚠ CRLF/LF: üç taraf da git-blob düzlemine (LF) indirgenir; çalışma ağacına yazarken
    `Klon.yaz` `eol` niteliğine göre geri dönüştürür (TASARIM §14 DOĞRULANMADI kalemi).
    """
    with tempfile.TemporaryDirectory(prefix="axet-merge-") as d:
        dd = Path(d)
        p_l, p_t, p_y = dd / "yerel", dd / "taban", dd / "yeni"
        for p, v in ((p_l, l), (p_t, t), (p_y, y)):
            p.write_bytes(v.replace(b"\r\n", b"\n"))
        r = subprocess.run(
            ["git", "merge-file", "-p", "--diff3",
             "-L", f"YEREL:{yol}", "-L", f"TABAN:{yol}", "-L", f"YENİ:{yol}",
             str(p_l), str(p_t), str(p_y)],
            cwd=str(dd), capture_output=True, stdin=subprocess.DEVNULL)
    # merge-file: çakışma sayısı 127'de kırpılır, hata NEGATİF döner — Windows'ta 255 olarak
    # görünür (ölçüldü, git 2.55). >127'yi "çakışma sayısı" saymak hatayı "ayrışma eşiği aşıldı"
    # diye yanlış teşhis ediyordu (rc taraması 2026-09-18).
    if r.returncode < 0 or r.returncode > 127:
        hata = " ".join((r.stderr or b"").decode("utf-8", "replace").split())[:300]
        raise Dur(f"git merge-file başarısız (rc={r.returncode}): {yol} — {hata or 'çıktı yok'}")
    return r.stdout, r.returncode


def fark_metni(a: bytes, b: bytes, a_ad: str, b_ad: str) -> str:
    return "".join(difflib.unified_diff(_satirlar(a), _satirlar(b),
                                        fromfile=a_ad, tofile=b_ad))


# =====================================================================================================
# TABAN + KAPSAM (§2a)
# =====================================================================================================
class Baglam:
    """Bir koşumun değişmez zemini: referanslar, harita, durum dosyaları."""

    def __init__(self, klon: Klon, harita: dict) -> None:
        self.k = klon
        self.harita = harita
        self.uygulanan = _oku(klon.durum_dizini / "uygulanan.json",
                              {"surum": 1, "dosyalar": {}, "kalemler": {}})
        if not klon.var_mi("origin/main"):
            raise Dur("origin/main bulunamadı — önce `git fetch` gerekiyor.")
        self.yayinlar = self._yayinlar_oku()
        self.yeni_ref = self._hedef_ref()
        self.taban_global = self.k.g("merge-base", "HEAD", "origin/main")

    def _yayinlar_oku(self) -> dict:
        r = self.k.git("show", "origin/main:guncelle/yayinlar.json")
        if r.returncode != 0:
            raise Dur(
                "origin/main:guncelle/yayinlar.json okunamadı. Bu dosya yayın tarafının "
                "(`yayin_hazirla.py`, iş paketi P7) ürettiği yapısal değişiklik listesidir; "
                "kalem↔dosya eşlemesi ondan gelir. YOKSA plan üretilemez — eşlemesiz bir plan "
                "kalem sözleşmesini uydurmak olurdu. (Dosya bozuksa git hatası yukarıdadır; "
                "henüz hiç yayınlanmadıysa bu sürümde `%guncelle` kullanılamaz.)")
        try:
            return json.loads(r.stdout)
        except ValueError as e:
            raise Dur(f"guncelle/yayinlar.json ayrıştırılamadı: {e}") from None

    @property
    def gecmis_yeniden_yazildi(self) -> bool:
        """TASARIM §11 force-push istisnası (sır sızıntısı): yayın tarafı geçmişi yeniden yazdı.

        Bugüne dek kodda hiç OKUNMUYORDU. Okunmadığında "etiket çözülemiyor" hatası, çözümü
        `fetch` olan bir ağ sorunuyla çözümü `kur.cmd -Sifirla` olan bir geçmiş kopuşunu
        ayırt edemez ve kullanıcı sonsuza dek `fetch` dener.
        """
        return bool(self.yayinlar.get("gecmis_yeniden_yazildi"))

    def _hedef_ref(self) -> str:
        """En yeni ÇÖZÜLEBİLEN yayın etiketi.

        ⚠ Buradaki geri düşüş TEK BAŞINA bir hata değildir (eski yayınlar için doğrudur); hata
        onu SESSİZ bırakmaktı. Çözülemeyen bir yayın hâlâ BEKLİYORSA `komut_plan` durur —
        yoksa v3 kalemleri v2 içeriğiyle uygulanır ve "uygulandi" mühürlenir (kalıcı kayıp).
        """
        etiketler = [y["etiket"] for y in self.yayinlar.get("yayinlar", [])]
        for e in reversed(etiketler):
            if self.k.var_mi(e):
                return e
        return "origin/main"

    # --- taban -------------------------------------------------------------------------------
    def taban_ref(self, yol: str) -> str | None:
        """§2a: dosya başına taban — uygulanan kaydı varsa o yayın, yoksa merge-base.
        Ref klonda çözülemiyorsa None (→ VTB)."""
        kayit = self.uygulanan.get("dosyalar", {}).get(yol)
        if kayit:
            return kayit if self.k.var_mi(kayit) else None
        return self.taban_global

    # --- kapsam ------------------------------------------------------------------------------
    def yeniden_adlandirmalar(self) -> dict[str, str]:
        r = self.k.git("diff", "-M", "--name-status", "-z", self.taban_global, self.yeni_ref)
        if r.returncode != 0:
            return {}
        parcalar = [p for p in r.stdout.split("\0") if p]
        harita: dict[str, str] = {}
        i = 0
        while i < len(parcalar):
            durum = parcalar[i]
            if durum.startswith("R") and i + 2 < len(parcalar):
                harita[parcalar[i + 1]] = parcalar[i + 2]
                i += 3
            else:
                i += 2
        return harita

    def kapsam(self) -> set[str]:
        """§2a: yalnız git'in bildiği template yolları. DİZİN TARAMASI YOK."""
        yollar = self.k.ls_tree(self.taban_global) | self.k.ls_tree(self.yeni_ref)
        for etiket in set(self.uygulanan.get("dosyalar", {}).values()):
            if self.k.var_mi(etiket):
                yollar |= self.k.ls_tree(etiket)
        return yollar

    def kullanici_dosya_sayisi(self) -> int:
        """VKD sayacı: kapsamda olmayan, izlenmeyen kullanıcı dosyaları — ADI hiç geçmez."""
        r = self.k.git("ls-files", "--others", "--exclude-standard", "-z")
        return len([y for y in r.stdout.split("\0") if y]) if r.returncode == 0 else 0


# =====================================================================================================
# PLAN
# =====================================================================================================
def _union_find(kalem_dosyalari: dict[str, set[str]]) -> dict[str, str]:
    """Aynı dosyaya dokunan kalemleri tek pakete bağlar (§6 'paket')."""
    ebeveyn: dict[str, str] = {k: k for k in kalem_dosyalari}

    def bul(x):
        while ebeveyn[x] != x:
            ebeveyn[x] = ebeveyn[ebeveyn[x]]
            x = ebeveyn[x]
        return x

    def birlestir_(a, b):
        ra, rb = bul(a), bul(b)
        if ra != rb:
            ebeveyn[rb] = ra

    dosya_sahibi: dict[str, str] = {}
    for kid in kalem_dosyalari:
        for d in kalem_dosyalari[kid]:
            if d in dosya_sahibi:
                birlestir_(dosya_sahibi[d], kid)
            else:
                dosya_sahibi[d] = kid
    kok_ad: dict[str, str] = {}
    sonuc: dict[str, str] = {}
    for kid in kalem_dosyalari:
        r = bul(kid)
        if r not in kok_ad:
            kok_ad[r] = f"P{len(kok_ad) + 1}"
        sonuc[kid] = kok_ad[r]
    return sonuc


def dosya_vakasi(b: Baglam, yol: str, yeniden_ad: dict[str, str]) -> dict:
    """Tek bir yolun vaka kaydı (§4). `oneri` ile aynı hesabı kullanır."""
    k = b.k
    taban = b.taban_ref(yol)
    t_sha = k.blob_sha(taban, yol) if taban else None
    l_sha = k.disk_sha(yol)
    hedef_yol = yeniden_ad.get(yol)
    y_sha = k.blob_sha(b.yeni_ref, hedef_yol or yol)

    if hedef_yol and hedef_yol != yol:
        # §4 +R son cümlesi: "Yeni yolda zaten L varsa → **V7**" (ad çakışması, DUR).
        # ⛔ Bu dal kodda YOKTU: `uygula --otomatik` V1R'yi koşulsuz `checkout_yol(yeni, hedef)`
        # ile yazıyordu ⇒ hedefteki İZLENMEYEN kullanıcı dosyası (hazirla onu commit'lemez,
        # geri dönüş etiketinde blob'u YOKTUR) uyarısız ve GERİ ALINAMAZ biçimde siliniyordu.
        # İki bağımsız gate aynı senaryoyu ölçtü (2026-09-18); kart V1R.md:26-27 zaten
        # "motor üzerine yazmaz" diyordu — kart doğruydu, motor yanlıştı.
        hedef_disk = k.disk_sha(hedef_yol)
        if hedef_disk is not None and hedef_disk != y_sha:
            return {"yol": yol, "vaka": "V7", "yeni_yol": hedef_yol}

    if hedef_yol and taban is not None:
        # +R değiştiricisi (§4): yol DEĞİŞTİ ⇒ içerik aynı olsa bile TAŞIMA bir eylemdir.
        # ⚠ Düz `vaka_kodu` burada yanlış cevap verir: %100 benzerlikli bir yeniden
        # adlandırmada T == L == Y olduğu için V0 ("değişiklik yok") çıkar ve dosya
        # plandan SESSİZCE düşer — ölçüldü 2026-09-17, `docs/tasinacak.md` fixture'ı.
        if l_sha is None:
            kod = "V5" if y_sha is not None else "V6x"
        elif y_sha is None:
            kod = "V6" if l_sha == t_sha else "V6d"
        elif l_sha in (t_sha, y_sha):
            kod = "V1R"
        else:
            kod = "V4R"
    else:
        # Buraya taşımalı bir yol YALNIZ taban çözülemediğinde gelir (⇒ VTB). Z66 ③: hedef yol
        # KORUNUR. Eskiden `hedef_yol = None` yapılıyordu: hedef plan döngüsünde "yeniden
        # adlandırma hedefi" olarak atlandığı için hiçbir kayıtta kalmıyor, `isaretle --karar yeni`
        # "yeni sürümde yok" DUR'u veriyordu ⇒ kullanıcının yeni içeriği alma yolu yoktu (yalnız
        # yerel/ertelendi; Z62 her tur yeniden önerir — kalıcı çıkmaz). Vaka VTB KALIR (otomatik
        # birleştirme yasak, §4); `yeni` hedefe yazar + kaynağı siler, `yerel` kaynağı bırakır.
        kod = vaka_kodu(t_sha, l_sha, y_sha, taban_var=taban is not None)

    kayit: dict = {"yol": yol, "vaka": kod}
    if hedef_yol:
        kayit["yeni_yol"] = hedef_yol

    if kod in ("V4", "V4R"):
        t = k.blob(t_sha) if t_sha else b""
        y = k.blob(y_sha) if y_sha else b""
        tam = k.kok / yol
        l = tam.read_bytes() if tam.is_file() else b""
        if ikili_mi(k, yol, [t, l, y]):
            alt = "V4B"
        else:
            _birlesik, cakisma = birlestir(k, yol, t, l, y)
            oran = yerel_fark_orani(t, l)
            kayit["cakisma"] = cakisma
            kayit["yerel_fark_orani"] = round(oran, 3)
            if cakisma > ESIK_CAKISMA_BLOGU or oran > ESIK_YEREL_FARK:
                alt = "V4c+ESIK"
            elif cakisma:
                alt = "V4c"
            else:
                alt = "V4t"
        # §5: V4R = "V4t/V4c kartı, hedef yol yeni ad" ⇒ kod V4R kalır, birleşme sonucu ayrı alanda
        kayit["vaka"] = "V4R" if kod == "V4R" else alt
        if kod == "V4R":
            kayit["birlesme"] = alt
    return kayit


def _kart_var_mi(k: Klon, kod: str) -> bool:
    """Kart YENİ sürümden okunur (`komut_kart` da öyle yapar) — yerel kopya bozuk/eski olabilir."""
    return k.git("cat-file", "-e", f"origin/main:guncelle/kartlar/{kod}.md").returncode == 0


def _kart_listesi(kayit: dict, sinif: dict | None) -> list[str]:
    kartlar = [kayit["vaka"]]
    if kayit.get("birlesme"):
        kartlar.append(kayit["birlesme"])
    if sinif:
        aday = f"sinif-{sinif['ust_sinif']}"
        kartlar.append(aday)
    return kartlar


def komut_plan(b: Baglam, args) -> int:
    k = b.k
    yeniden_ad = b.yeniden_adlandirmalar()
    kapsam = b.kapsam()

    # 1) hangi yayınlar bekliyor
    bekleyen_yayinlar, beyan, kalem_kaydi, cozulemeyen = [], {}, {}, []
    # Z57: plana ALINMAYAN ama KARŞILANMIŞ kalemler (yayını içerilmiş ya da `uygulanan.json`'da
    # mühürlü). `komut_sec` `gerektirir` bağını bu kümeye de bakarak çözer; eskiden yalnız seçim
    # kümesine bakıyordu ⇒ önceki yayında uygulanmış kaleme bağlı yeni kalem "seçili değil" DUR'u
    # veriyordu (v0.5.2 CI yayın provası, ölçüldü). Plan hangi kalemi NEDEN dışarıda bıraktıysa
    # seçim de AYNI kümeyi görür — iki ayrı ölçüm iki ayrı sonuç veremez.
    # ⚠ `uygulanan.json`'da `durum: atlandi` olan kalem de KARŞILANMIŞ sayılır: `_kapanis_git` hiçbir
    # dosyası doğrulanmayan kalemi böyle mühürler. DUR etmek bağımlıyı KALICI kilitlerdi (atlandi
    # kalem bir daha plana girmez) ⇒ seçim bozulmaz. Z58 (v0.5.4): mühür `neden` taşır
    # (`_atlandi_nedeni`: ertelendi | kabul | is-yok). `is-yok` = yapılacak iş yoktu ⇒ sessizce
    # karşılanmış. `kabul`, tanınmayan değer ya da alan YOK (Z58 öncesi kayıt: ertelendi mi iş-yok
    # mu ayırt edilemez) — fail-closed `karsilanan_atlandi`'ya da yazılır; `komut_sec` o yolla
    # karşılanan her bağ için nedeni söyleyen UYARI basar. `ertelendi` artık buraya girmez (Z62).
    # Z62 (v0.5.5, kullanıcı kararı): `neden: ertelendi` mühürlü kalem KARŞILANMIŞ SAYILMAZ — plana
    # normal kalem olarak YENİDEN girer (`yeniden_onerilen`). Kullanıcı "sonra bakarım" demişti;
    # eskiden mühür onu kalıcı olarak plandan düşürüyordu. İstisna: kalemin beyan ettiği yolların
    # HİÇBİRİ bu turda EYLEM gerektirmiyorsa (işlemsiz vaka) önerilecek iş yoktur ⇒ `is-yok` gibi
    # sessizce karşılanır (aşağıda, kalemler kurulmadan önce). Dosyaları sonraki bir kaleme
    # DEVREDİLMİŞ kalem bu istisnaya GİRMEZ (v0.5.5 entegrasyonu, v0.5.4 `_atlandi_nedeni` ilkesi):
    # plana dosyasız kalem olarak girer, karar kapanışa kalır.
    # `kabul` KAPALI kalır; `is-yok` ve neden YOK (eski kayıt) önerilmez — gerekçe TASARIM §6.
    karsilanan: set[str] = set()
    karsilanan_atlandi: set[str] = set()
    atlandi_nedenleri: dict[str, str | None] = {}
    yeniden_onerilen: set[str] = set()
    for yayin in b.yayinlar.get("yayinlar", []):
        etiket = yayin["etiket"]
        durum_y = yayin_durumu(lambda *a: k.git(*a).returncode, etiket)
        if durum_y == "cozulemedi":
            # Etiket çözülemiyorsa bu yayının İÇERİLİP içerilmediği de ÖLÇÜLEMEZ ⇒ bekleyen say.
            cozulemeyen.append(etiket)
            continue
        if durum_y == "icerildi":
            # tüketici bu yayını gerçekten içeriyor (taze klon)
            karsilanan |= {kalem["id"] for kalem in yayin.get("kalemler", [])}
            continue
        bekleyen_yayinlar.append(etiket)
        for kalem in yayin.get("kalemler", []):
            kid = kalem["id"]
            muhur = b.uygulanan.get("kalemler", {}).get(kid)
            if (isinstance(muhur, dict) and muhur.get("durum") == "atlandi"
                    and muhur.get("neden") == "ertelendi"):
                yeniden_onerilen.add(kid)          # karşılanmış DEĞİL ⇒ aşağıda beyan'a girer
            elif kid in b.uygulanan.get("kalemler", {}):
                karsilanan.add(kid)
                if isinstance(muhur, dict) and muhur.get("durum") == "atlandi":
                    neden = muhur.get("neden")
                    if neden != "is-yok":
                        karsilanan_atlandi.add(kid)
                        atlandi_nedenleri[kid] = neden if isinstance(neden, str) else None
                continue
            beyan[kid] = set(kalem.get("dosyalar", []))
            kalem_kaydi[kid] = (etiket, kalem)

    if cozulemeyen:
        # ⛔ Buradan sonrası SESSİZ KAYIP olurdu: `yeni_ref` bir ÖNCEKİ yayına düşer, o yayının
        # kalemleri eski içerikle uygulanır, `kapanis` `uygulanan.json`'a "uygulandi" yazar ve
        # kalem bir daha plana GİRMEZ — bakımcı etiketi sonradan bassa bile "Klon güncel" denir.
        ortak = (f"Bekleyen yayın etiketleri klonda çözülemiyor: {', '.join(cozulemeyen)}. "
                 f"Motor o yayınların İÇERİĞİNİ okuyamaz; en yeni çözülebilen ref "
                 f"`{b.yeni_ref}`. ")
        if b.gecmis_yeniden_yazildi:
            raise Dur(ortak + "`yayinlar.json` `gecmis_yeniden_yazildi: true` diyor (TASARIM "
                              "§11 force-push istisnası) ⇒ bu klonun geçmişi yayın tarafıyla "
                              "artık örtüşmüyor; `fetch` bunu DÜZELTMEZ. `kur.cmd -Sifirla` ile "
                              "klonu yeniden kur.")
        raise Dur(ortak + "Plan üretilirse o kalemler sessizce ESKİ içerikle uygulanır ve "
                          "`uygulanan.json`'a 'uygulandi' yazılır (kalıcı kayıp). Önce "
                          "`git -C <klon> fetch --tags origin` çalıştır.")

    if not beyan:
        print("Klon güncel: bekleyen yayın kalemi yok.")
        return 1

    # 2) kapsamın tamamını sınıflandır (sayaçlar), kalem dosyalarını ayrıca kaydet
    sayaclar: dict[str, int] = {}
    vaka_kayitlari: dict[str, dict] = {}
    yeniden_hedefleri = set(yeniden_ad.values())
    with k.toplu_okuma(set(kapsam) | yeniden_hedefleri):  # Z31: dosya başına 3 git süreci yerine toplu
        for yol in sorted(kapsam):
            if yol in yeniden_hedefleri:
                # yeniden adlandırma HEDEFİ kaynak kaydında (`yeni_yol`) taşınır; ayrıca V2
                # listelenirse aynı dosya iki kez uygulanır ve `kapanis` iki kez doğrulamaya çalışır
                continue
            kayit = dosya_vakasi(b, yol, yeniden_ad)
            sayaclar[kayit["vaka"]] = sayaclar.get(kayit["vaka"], 0) + 1
            if kayit["vaka"] not in ISLEMSIZ_VAKALAR:
                vaka_kayitlari[yol] = kayit
    sayaclar["VKD"] = sayaclar.get("VKD", 0) + b.kullanici_dosya_sayisi()
    # v0.5.5 bug gate (P1/P2): taşıma HEDEFİ yukarıda atlandı — işi KAYNAĞIN kaydı taşır (`yeni_yol`).
    # Hedefi beyan eden kalem bu yüzden "EYLEM yolu yok" sanılıyordu: Z62 düşürmesi ertelenmiş kalemi
    # sessizce `karsilanan` yapıyor (P2), kapanış da taşıma ertelense bile onu `is-yok` mühürlüyordu
    # (P1). Hedef yol, kaynağın kaydı/sahibi/durumu üzerinden görülür: aşağıdaki üç ölçüm (düşürme,
    # paket, `devredilen`) `_eylem_yolu` ile aynı kaynağa bakar. Taşıma HEDEFİ işlemsiz DEĞİLDİR.
    hedef_kaynak = {kayit["yeni_yol"]: yol for yol, kayit in vaka_kayitlari.items()
                    if kayit.get("yeni_yol")}

    def _eylem_yolu(yol: str) -> str | None:
        """Beyan edilen yolun işini taşıyan `vaka_kayitlari` anahtarı (hedef → kaynak) ya da None."""
        return yol if yol in vaka_kayitlari else hedef_kaynak.get(yol)

    # 3) her yolu onu BEYAN EDEN EN SON kaleme bağla
    yol_kalemi: dict[str, str] = {}
    for kid in kalem_kaydi:
        for d in beyan[kid]:
            yol_kalemi[d] = kid  # yayınlar sırayla gezildi → son yazan en yeni kalem

    # Z62: yeniden önerilecek (ertelenmiş) kalemin beyan ettiği yolların HİÇBİRİ bu turda EYLEM
    # gerektirmiyorsa (hepsi işlemsiz vaka / kapsam dışı) `is-yok` davranışı: plana girmez, sessizce
    # karşılanır (UYARI kümesine YAZILMAZ). Ölçüt adım 4'ün süzgeciyle AYNI kaynaktır
    # (`vaka_kayitlari`; taşıma hedefi kaynağı üzerinden — `_eylem_yolu`, v0.5.5 bug gate P2).
    # ⛔ v0.5.5 entegrasyonu (v0.5.4 `_atlandi_nedeni` ilkesi): EYLEM yolu sonraki bir kaleme
    # DEVREDİLMİŞ kalem düşürülMEZ. O yolun sahibi `yol_kalemi` ⇒ `kalem_kaydi` üyesidir, yani BU
    # planda bekleyen kalemdir (mühürlü kalem `kalem_kaydi`'ye girmez) ⇒ plan anında içerik diske
    # İNMEMİŞTİR ve hiçbir kayıt (`uygulanan.json` sahip mührü, `durum.json`) bunun aksini
    # söyleyemez. Kalem dosyasız ama `devredilen`li olarak plana girer (sahibiyle aynı pakette:
    # union-find beyan üzerinden); nedeni kapanışta sahibin mührü + yolun durumu belirler
    # (`_atlandi_nedeni`: indiyse `is-yok`, yine ertelendiyse `ertelendi` ⇒ sonraki turda yine
    # önerilir). Eskiden (Z62 dalı) "planda dosyası yok ⇒ is-yok gibi" deniyordu: bağımlısının
    # önkoşulu içerik inmeden sessizce "karşılanmış" oluyordu.
    # Düşen kalem hiçbir EYLEM yolunun sahibi değildir ⇒ başka kalemin `dosyalar`ı/`devredilen`i
    # değişmez. Paketler (union-find) düşürmeden SONRA kurulur ki düşen kalem başka kalemleri
    # (ortak işlemsiz yol üzerinden) tek pakete bağlamasın.
    for kid in sorted(yeniden_onerilen):
        if not any(_eylem_yolu(y) for y in beyan[kid]):
            yeniden_onerilen.discard(kid)
            karsilanan.add(kid)
            del beyan[kid], kalem_kaydi[kid]
    if not beyan:
        print("Klon güncel: bekleyen yayın kalemi yok.")
        return 1
    # Taşıma hedefini beyan eden kalem, kaynağın sahibiyle aynı pakete girer (sahip seçilince o da
    # seçilsin ki kapanış nedenini ölçebilsin) ⇒ union-find'e hedefin kaynağı da verilir.
    paketler = _union_find({kid: ys | {hedef_kaynak[y] for y in ys if y in hedef_kaynak}
                            for kid, ys in beyan.items()})

    # 4) kalemleri kur
    kalemler, restart, uyarilar = [], None, []
    kart_onbellek: dict[str, bool] = {}
    eksik_kartlar: set[str] = set()
    for kid, (etiket, kalem) in kalem_kaydi.items():
        dosyalar, ozel_adimlar = [], []
        # Z58 bug gate (v0.5.4): kalemin BEYAN ETTİĞİ ve EYLEM gerektiren ama sonraki bir kaleme
        # devredilen yollar → yeni sahipleri. `_atlandi_nedeni` dosyasız kalemi yalnız bu yolların
        # içeriği bu turda gerçekten indiyse `is-yok` sayar; aksi hâlde devir sessiz bir kayıptı.
        # v0.5.5 bug gate (P1): taşıma HEDEFİ beyanı kaynağın ANAHTARIYLA yazılır (durum.json ve
        # `vaka_kayitlari` kaynağı anahtar tutar) ve kaynağın sahibine bağlanır. Kaynağı hiçbir
        # kalem beyan etmiyorsa sahip `None`dır (taşıma "beyansız EYLEM" uyarısıyla uygulanmaz) ⇒
        # içerik inmez; `_atlandi_nedeni` onu `is-yok` SAYMAZ (fail-closed).
        devredilen: dict[str, str | None] = {}
        for yol in sorted(beyan[kid]):
            eylem = _eylem_yolu(yol)
            if eylem is not None and yol_kalemi.get(eylem) != kid:
                devredilen[eylem] = yol_kalemi.get(eylem)
            if yol_kalemi.get(yol) != kid or yol not in vaka_kayitlari:
                continue
            kayit = dict(vaka_kayitlari[yol])
            sinif = sinif_bul(yol, b.harita)
            kayit["sinif"] = sinif["sinif"] if sinif else None
            kayit["etkin"] = sinif["etkin"] if sinif else None
            kayit["esler"] = sinif.get("esler", []) if sinif else []
            kayit["kart"] = _kart_listesi(kayit, sinif)
            for kod in kayit["kart"]:
                if kod not in kart_onbellek:
                    kart_onbellek[kod] = _kart_var_mi(k, kod)
                if not kart_onbellek[kod]:
                    eksik_kartlar.add(kod)
            if sinif is None:
                uyarilar.append(f"WARN sınıfsız dosya (harita bilmiyor): {yol}")
            else:
                dv = etkin_davranis(sinif["etkin"])
                if dv["yeniden_baslat"] is not None:
                    if (YENIDEN_BASLAT_SIRA.index(dv["yeniden_baslat"])
                            > YENIDEN_BASLAT_SIRA.index(restart)):
                        restart = dv["yeniden_baslat"]
                if sinif.get("ozel_adim"):
                    ozel_adimlar.append(sinif["sinif"])
            dosyalar.append(kayit)
        testler = []
        for kayit in dosyalar:
            sinif = sinif_bul(kayit["yol"], b.harita)
            for t in (sinif or {}).get("test", []):
                if t not in testler:
                    testler.append(t)
        kalemler.append({
            "id": kid, "baslik": kalem.get("baslik", ""), "tur": kalem.get("tur", ""),
            "kritik": bool(kalem.get("kritik") or kalem.get("tur") == "guvenlik"),
            "gerektirir": kalem.get("gerektirir", []), "min_axet": kalem.get("min_axet"),
            "yayin": etiket, "paket": paketler[kid], "dosyalar": dosyalar,
            "devredilen": devredilen, "testler": testler, "ozel_adimlar": sorted(set(ozel_adimlar)),
            "yeniden_onerilen": kid in yeniden_onerilen,
        })

    # Kapsamda EYLEM gerektiren ama hiçbir kalemin `dosyalar` listesinde geçmeyen yollar:
    # sessizce uygulanmıyor, yalnız sayaçta görünüyordu ⇒ kullanıcı "güncellendi" sanırdı.
    listelenen = {d["yol"] for kalem in kalemler for d in kalem["dosyalar"]}
    for yol in sorted(set(vaka_kayitlari) - listelenen):
        uyarilar.append(f"WARN beyansız EYLEM vakası: {yol} ({vaka_kayitlari[yol]['vaka']}) "
                        f"kapsamda ama hiçbir kalemin `dosyalar` listesinde geçmiyor — "
                        f"UYGULANMAYACAK (yayın tarafında kalem beyanı eksik olabilir)")

    # Plan bir kart ADI verdiğinde o kartın gerçekten VAR olduğunu da söylemelidir; yoksa ajan
    # §7 adım 8'de `kart <KOD>` deyip çıkış 2 alır ve akış orada tıkanır. Kart adları burada
    # DEĞİŞTİRİLMEZ, yalnız varlıkları ölçülür.
    for kod in sorted(eksik_kartlar):
        uyarilar.append(f"WARN kart bulunamadı: guncelle/kartlar/{kod}.md (origin/main) — "
                        f"ajan bu kartı basamaz (§7 adım 8)")

    if not any(k2["dosyalar"] for k2 in kalemler):
        print("Klon güncel: bekleyen kalemlerin hiçbiri dosya değişikliği gerektirmiyor.")
        return 1

    plan = {
        "surum": 1, "taban_commit": b.taban_global, "yeni_etiket": b.yeni_ref,
        "yayinlar": bekleyen_yayinlar, "kalemler": kalemler,
        "karsilanan": sorted(karsilanan),
        "karsilanan_atlandi": sorted(karsilanan_atlandi),
        "karsilanan_atlandi_neden": dict(sorted(atlandi_nedenleri.items())),
        "paketler": {p: sorted(kid for kid, pp in paketler.items() if pp == p)
                     for p in sorted(set(paketler.values()))},
        "sayaclar": dict(sorted(sayaclar.items())),
        "yeniden_baslat": restart or "gerekmez",
        "uyarilar": uyarilar,
        "uretim": _simdi(),
    }
    _yaz_json(k.durum_dizini / "plan.json", plan)
    # K2: durum.json döngü-kapsamlıdır ama SİLİNMEZ (bkz. `_plan_muhru`) → bu turun damgasını
    # taşır. Önceki turun kayıtları KORUNUR; kapanış damgaya bakarak "bu tur ölçüldü mü"
    # sorusunu cevaplayabilir (eskiden cevaplayamadan "koştu" sayıyordu).
    d = durum_oku(k)
    d["plan"] = _plan_muhru(plan)
    temizlenen = _tuketilmis_ertelemeleri_temizle(d, plan, b.uygulanan)
    tuketilen = _tuketilmis_dogrulamalari_temizle(d, plan, b.uygulanan)
    durum_yaz(k, d)
    _plan_tablosu(plan)
    for yol in temizlenen:
        print(f"  NOT: {yol} önceki turda ertelenmişti; o karar kapanışta mühürlendi, bu turda "
              f"dosya yeniden karar bekliyor.")
    for yol in tuketilen:
        print(f"  NOT: {yol} önceki turda doğrulanmıştı; o kayıt kapanışta mühürlendi, bu "
              f"yayının değişikliği için dosya bu turda yeniden işlenecek.")
    return 0


def _kayit_tuketildi_mi(kayit_zaman, muhur_zaman) -> bool:
    """Z62: dosya kaydı, kaleminin `uygulanan.json` mührü basılmadan ÖNCE mi verildi?

    `kapanis` mührü dosya kararlarından SONRA basar (`_kapanis_git`), dolayısıyla mühürden önceki
    (ya da aynı saniyedeki) karar o kapanışta TÜKETİLMİŞTİR. Mühürden sonraki karar, kalem yeniden
    önerildikten sonra BU turda verilmiştir ⇒ korunur (aynı turda `plan` yeniden koşulabilir).
    Zaman okunamazsa tüketilmiş sayılır: kaydı silmek dosyayı `bekliyor`a döndürür ve kapanış onu
    açık madde olarak GÖSTERİR; tutmak ise dosyayı `uygula`da SESSİZCE atlatırdı.

    Z65: karşılaştırma METİN değil ANDIR — farklı dilimde yazılmış iki damga metin olarak yanlış
    sıralanır. Dilimsiz (Z65 öncesi `_simdi()`) damga bu makinenin yerel saati kabul edilir."""
    if not (isinstance(kayit_zaman, str) and isinstance(muhur_zaman, str)):
        return True
    try:
        kayit = datetime.datetime.fromisoformat(kayit_zaman)
        muhur = datetime.datetime.fromisoformat(muhur_zaman)
        if kayit.tzinfo is None:
            kayit = kayit.astimezone()
        if muhur.tzinfo is None:
            muhur = muhur.astimezone()
        return kayit <= muhur
    except (ValueError, OverflowError, OSError):
        return True


def _tuketilmis_ertelemeleri_temizle(d: dict, plan: dict, uygulanan: dict) -> list[str]:
    """Z62: bu planın dosyalarındaki, önceki bir kapanışta TÜKETİLMİŞ `atlandi/ertelendi` kayıtlarını
    `durum.json`'dan siler. Döner: temizlenen yollar.

    Neden gerekli (ölçüldü, `test_Z62_ertelenen_dosyanin_bayat_kaydi_planda_temizlenir_uygula_atlamaz`):
    `durum.json` turlar arasında SİLİNMEZ (`_plan_muhru`) ve `komut_uygula` yargı vakasında önceki
    `atlandi` kaydını koruyup dosyayı atlar ⇒ yeniden önerilen kalemin dosyası bu turda hiç
    `bekliyor` açılmazdı; `_atlandi_nedeni` de bayat kararı okuyup kalemi kullanıcı hiçbir şey
    demeden yine `ertelendi` mühürlerdi. Aynı bayat kayıt, dosyası SONRAKİ bir yayının kalemine
    geçmiş ertelenmiş kalemde o yeni kalemi de atlatırdı — bu yüzden ölçüt kalem değil DOSYADIR:
    kaydın kalemi (`kayit["kalem"]`) mühürlüyse ve kayıt mühürden önce verildiyse temizlenir.

    Neden PLAN anında (uygula değil): turu `plan` başlatır ve `durum.json`'u zaten o damgalar
    (K2); `uygula` tekrar koşulabilen adımdır ve yalnız seçili kalemleri gezer. Planda silmek her
    tüketiciye (`uygula`, `isaretle`, `kapanis`, `durum`) aynı temiz durumu verir."""
    temizlenen = []
    muhurler = uygulanan.get("kalemler", {})
    for kalem in plan["kalemler"]:
        for dosya in kalem["dosyalar"]:
            kayit = d["dosyalar"].get(dosya["yol"])
            if not (isinstance(kayit, dict) and kayit.get("durum") == "atlandi"
                    and kayit.get("karar") == "ertelendi"):
                continue
            muhur = muhurler.get(kayit.get("kalem"))
            if isinstance(muhur, dict) and _kayit_tuketildi_mi(kayit.get("zaman"),
                                                              muhur.get("zaman")):
                del d["dosyalar"][dosya["yol"]]
                temizlenen.append(dosya["yol"])
    return temizlenen


def _tuketilmis_dogrulamalari_temizle(d: dict, plan: dict, uygulanan: dict) -> list[str]:
    """Z61 (b): bu planın dosyalarındaki, önceki bir kapanışta TÜKETİLMİŞ `dogrulandi` kayıtlarını
    `durum.json`'dan siler. Döner: temizlenen yollar. Ölçüt Z62 temizliğinin aynısı (dosya bazlı;
    kaydın kalemi mühürlü VE kayıt mühürden önce/aynı saniyede ⇒ tüketilmiş; `_kayit_tuketildi_mi`).

    Neden gerekli (ölçüldü, `test_Z61_b_bayat_dogrulandi_yeni_turun_yargi_vakasini_atlatmaz`):
    `komut_uygula` yargı vakasında önceki `dogrulandi` kaydını "verilmiş karar" sayıp dosyayı
    `bekliyor` açmadan atlar. Önceki turun `yerel`/`birlesik` kararında disk hâlâ o kaydın
    `beklenen_sha`sıdır ⇒ kapanış dosyayı PASS sayar ve sonraki yayının kalemini kullanıcıya hiç
    sorulmadan `uygulandi` mühürler (içeriği diske inmeden; `--kabul` bile gerekmez).
    `_tuketilmis_ertelemeleri_temizle` yalnız `atlandi/ertelendi`yi siler — bilinçli olarak ayrı
    fonksiyon: o kaydın silinmesi kullanıcıya "yeniden karar bekliyor" notu verir, bunun notu farklıdır."""
    temizlenen = []
    muhurler = uygulanan.get("kalemler", {})
    for kalem in plan["kalemler"]:
        for dosya in kalem["dosyalar"]:
            kayit = d["dosyalar"].get(dosya["yol"])
            if not (isinstance(kayit, dict) and kayit.get("durum") == "dogrulandi"):
                continue
            muhur = muhurler.get(kayit.get("kalem"))
            if isinstance(muhur, dict) and _kayit_tuketildi_mi(kayit.get("zaman"),
                                                              muhur.get("zaman")):
                del d["dosyalar"][dosya["yol"]]
                temizlenen.append(dosya["yol"])
    return temizlenen


def _plan_tablosu(plan: dict) -> None:
    print(f"Plan: {plan['yeni_etiket']}  (taban {plan['taban_commit'][:10]}, "
          f"bekleyen yayın: {', '.join(plan['yayinlar']) or '—'})")
    for kalem in plan["kalemler"]:
        if not kalem["dosyalar"]:
            continue
        isaret = "★" if kalem["kritik"] else " "
        ek = "  — önceki turda ertelenmişti, yeniden önerildi" if kalem.get("yeniden_onerilen") else ""
        print(f"{isaret} [{kalem['paket']}] {kalem['id']}  {kalem['baslik']}  ({kalem['tur']}){ek}")
        for d in kalem["dosyalar"]:
            hedef = f" → {d['yeni_yol']}" if d.get("yeni_yol") else ""
            print(f"      {d['vaka']:9s} {d['yol']}{hedef}  [{d['sinif']}]")
    print("Sayaçlar: " + ", ".join(f"{k}={v}" for k, v in plan["sayaclar"].items()))
    for u in plan.get("uyarilar", []):
        print("  " + u)
    print(f"Yeniden başlatma: {plan['yeniden_baslat']}")


# =====================================================================================================
# SEÇİM
# =====================================================================================================
def plan_oku(k: Klon) -> dict:
    p = _oku(k.durum_dizini / "plan.json", None)
    if p is None:
        raise Dur("plan.json yok — önce `guncelle.py plan` çalıştır.")
    return p


def _atlandi_aciklamasi(neden) -> str:
    """Z58: `sec` UYARI'sında önkoşulun NEDEN atlandığı (`uygulanan.json` mührünün `neden` alanı).

    Z62 notu: bugünkü `komut_plan` `ertelendi` kalemi `karsilanan_atlandi`'ya YAZMAZ (yeniden önerir
    ya da beyan yolları işlemsizse `is-yok` gibi karşılar); o dal Z58 motorunun (v0.5.4) ürettiği `plan.json`
    okunurken doğru metni basmak için durur (`test_Z58_v054_plani_ertelendi_neden_UYARI_ertelenmis_der`)."""
    if neden == "ertelendi":
        return "ertelenmiş: `isaretle --karar ertelendi`"
    if neden == "kabul":
        return "`kapanis --kabul` ile kapatılmış: dosyaları `bekliyor` kaldı"
    if neden is None:
        return "eski kayıt: ertelenmiş ya da iş yoktu, ayırt edilemiyor"
    return f"tanınmayan neden {neden!r}: ertelenmiş olabilir"


def komut_sec(b: Baglam, args) -> int:
    plan = plan_oku(b.k)
    kalemler = {x["id"]: x for x in plan["kalemler"]}
    paket_uyeleri = plan["paketler"]

    if args.hepsi:
        secili = set(kalemler)
    else:
        secili = {kid for kid, x in kalemler.items() if x["kritik"]}
        for ad in args.kalem or []:
            if ad in kalemler:
                secili.add(ad)
            elif ad in paket_uyeleri:
                secili |= set(paket_uyeleri[ad])
            else:
                print(f"DUR: bilinmeyen kalem/paket: {ad}", file=sys.stderr)
                return 2
    for ad in args.cikar or []:
        secili.discard(ad)
        if ad in paket_uyeleri:
            secili -= set(paket_uyeleri[ad])

    # paket birimi (Q2): seçilen kalemin paketi bütün gelir
    genisletilmis = set(secili)
    for kid in secili:
        genisletilmis |= set(paket_uyeleri[kalemler[kid]["paket"]])
    # `--cikar` paket genişletmesini de bağlar (kullanıcı açıkça çıkardı)
    genisletilmis -= set(args.cikar or [])

    # Z62 + Z63 (kullanıcı kararları): önkoşul PLANDA bekleyen bir kalemse — yeniden önerilen
    # (önceki turda ertelenmiş, Z62) ya da normal bekleyen (Z63) — `sec` DUR vermez, onu (paketiyle)
    # kendiliğinden seçer ve stdout'a bir satırla söyler; zincir sabit noktaya kadar izlenir.
    # İlke: kullanıcı ayrı komut çalıştırmamalı. Aşağıdaki kontrolde YİNE DUR veren iki dal:
    # `--cikar` ile AÇIKÇA dışlanan önkoşul (kalem adıyla ya da paket adıyla — kullanıcının açık
    # iradesi) ve planda da `karsilanan`'da da OLMAYAN önkoşul (seçilecek kalem yok ⇒ fail-closed).
    cikarilan = set(args.cikar or [])
    for ad in args.cikar or []:
        if ad in paket_uyeleri:
            cikarilan |= set(paket_uyeleri[ad])
    degisti = True
    while degisti:
        degisti = False
        for kid in sorted(genisletilmis):
            for bag in kalemler[kid]["gerektirir"]:
                if bag in genisletilmis or bag in cikarilan or bag not in kalemler:
                    continue
                ek = set(paket_uyeleri[kalemler[bag]["paket"]]) - cikarilan - genisletilmis
                genisletilmis |= ek | {bag}
                neden = (f"; {bag} önceki turda ertelenmişti ve yeniden önerildi"
                         if kalemler[bag].get("yeniden_onerilen") else "")
                print(f"{kid} kalemi {bag} kalemini gerektiriyor{neden} — kendiliğinden seçildi"
                      + (f" (paketiyle: {', '.join(sorted(ek - {bag}))})" if ek - {bag} else "")
                      + ".")
                degisti = True

    # Z57: bağ, seçimde YA DA önceki bir turda karşılanmışsa (plan `karsilanan`) tamamdır.
    # Alan yoksa/bozuksa (eski motorun planı) karşılanmışlık ÖLÇÜLEMEZ ⇒ boş küme ⇒ fail-closed.
    ham = plan.get("karsilanan")
    karsilanan = set(ham) if isinstance(ham, list) and all(isinstance(x, str) for x in ham) else set()
    # `atlandi` mühürlü kalem de karşılanmış sayılır (bkz. `komut_plan`) ama bağ YALNIZ bu yolla
    # karşılanıyorsa UYARI basılır; rc değişmez. Alan yoksa/bozuksa (Z57 ilk sürümünün planı) boş
    # küme — seçimi etkilemez, yalnız uyarı basılamaz (`karsilanan` fail-closed'u AYNEN kalır).
    ham_a = plan.get("karsilanan_atlandi")
    karsilanan_atlandi = (set(ham_a) if isinstance(ham_a, list)
                          and all(isinstance(x, str) for x in ham_a) else set())
    # Z58: kalem → neden. Alan yoksa (v0.5.3 planı) ya da kalem içinde yoksa neden BİLİNMİYOR
    # (None ⇒ "eski kayıt" metni); küme üyeliği `karsilanan_atlandi`dan gelir, bu alandan DEĞİL.
    ham_n = plan.get("karsilanan_atlandi_neden")
    atlandi_nedenleri = ham_n if isinstance(ham_n, dict) else {}
    for kid in sorted(genisletilmis):
        for bag in kalemler[kid]["gerektirir"]:
            if bag not in genisletilmis and bag in karsilanan and bag in karsilanan_atlandi:
                print(f"UYARI: {kid} kalemi {bag} kalemini gerektiriyor; {bag} önceki bir turda "
                      f"`atlandi` olarak mühürlü "
                      f"({_atlandi_aciklamasi(atlandi_nedenleri.get(bag))}). Bağ karşılanmış "
                      f"sayıldı, ama {bag} kaleminin dosyaları diskte olmayabilir "
                      f"(§6 `gerektirir`).", file=sys.stderr)
            if bag not in genisletilmis and bag not in karsilanan:
                ipucu = ("" if isinstance(ham, list) else
                         " plan.json `karsilanan` alanını taşımıyor (eski motorun planı) — "
                         "önceki turda uygulanmış olsa bile ÖLÇÜLEMEZ; `plan`ı yeniden koş.")
                print(f"DUR: {kid} kalemi {bag} kalemini gerektiriyor ama {bag} seçili değil "
                      f"ve önceki bir turda karşılanmış da değil (§6 `gerektirir`).{ipucu}",
                      file=sys.stderr)
                return 2

    # v0.5.5 bug gate (P3): seçili kalemin devredilen yolunun SAHİBİ seçimde yoksa (`--cikar`) o yol
    # bu turda işlenmez ⇒ kapanış kalemi `ertelendi` mühürler (sonraki turda yeniden önerilir; `kabul`
    # DEĞİL — `kabul` yalnız `kapanis --kabul` ile). Kullanıcı bunu seçim anında görsün.
    # ⛔ `ertelendi` vaadi YALNIZ dosyasız kalemde verilir: `_atlandi_nedeni` yalnız `uygulandi`
    # OLMAYAN kalem için çağrılır; kalemin KENDİ dosyaları (`kalemler[kid]["dosyalar"]`) inerse mühür
    # `uygulandi` olur (v0.5.5 mini gate, ölçüldü: 3-06 `docs/tasindi2.md` + `kur.cmd`,
    # `sec --kalem 3-06 --cikar 3-04` ⇒ NOT "ertelendi" diyordu, mühür `uygulandi`).
    for kid in sorted(genisletilmis):
        dv = kalemler[kid].get("devredilen")
        if not isinstance(dv, dict):
            continue
        disarida = sorted(y for y, sahip in dv.items() if sahip not in genisletilmis)
        if disarida:
            parca = ", ".join(f"{y} → {dv[y] or 'beyansız (hiçbir kalem)'}" for y in disarida)
            if kalemler[kid]["dosyalar"]:
                print(f"NOT: {kid} kaleminin bu yolları bu turda işlenmez — işleri seçilmeyen kalemde "
                      f"({parca}); bu yollar ancak sahip kalem seçildiğinde gelir (beyansız yolu "
                      f"getirecek kalem yoktur). {kid} kendi "
                      f"dosyalarıyla işlenir; kapanış mührü o dosyaların sonucuna göre belirlenir.")
            else:
                print(f"NOT: {kid} kaleminin işi bu turda seçilmeyen kalemde ({parca}) ⇒ {kid} "
                      f"kapanışta `ertelendi` mühürlenir ve sonraki turda yeniden önerilir "
                      f"(`kabul` DEĞİL).")

    secim = {"kalemler": sorted(genisletilmis),
             "paketler": sorted({kalemler[k2]["paket"] for k2 in genisletilmis}),
             "zaman": _simdi()}
    _yaz_json(b.k.durum_dizini / "secim.json", secim)
    print(f"Seçildi: {len(secim['kalemler'])} kalem / {len(secim['paketler'])} paket → "
          + ", ".join(secim["kalemler"]))
    return 0


def secim_oku(k: Klon, plan: dict) -> set[str]:
    s = _oku(k.durum_dizini / "secim.json", None)
    if s is None:
        raise Dur("secim.json yok — önce `guncelle.py sec` çalıştır.")
    return set(s["kalemler"])


def secili_dosyalar(k: Klon, plan: dict) -> list[tuple[str, dict]]:
    secili = secim_oku(k, plan)
    out = []
    for kalem in plan["kalemler"]:
        if kalem["id"] in secili:
            for d in kalem["dosyalar"]:
                out.append((kalem["id"], d))
    return out


# =====================================================================================================
# DURUM
# =====================================================================================================
def durum_oku(k: Klon) -> dict:
    return _oku(k.durum_dizini / "durum.json", {"surum": 1, "dosyalar": {}, "ozel_adimlar": {}})


def durum_yaz(k: Klon, d: dict) -> None:
    _yaz_json(k.durum_dizini / "durum.json", d)


def durum_kaydet(k: Klon, yol: str, **alanlar) -> None:
    d = durum_oku(k)
    kayit = d["dosyalar"].setdefault(yol, {})
    kayit.update(alanlar)
    kayit["zaman"] = _simdi()
    durum_yaz(k, d)


# =====================================================================================================
# UYGULA
# =====================================================================================================
def komut_uygula(b: Baglam, args) -> int:
    k, plan = b.k, plan_oku(b.k)
    if not args.otomatik:
        print("DUR: `uygula` yalnız `--otomatik` ile çalışır (yargı vakaları `isaretle` ile).",
              file=sys.stderr)
        return 2
    hata = 0
    # Bu koşumdan ÖNCE verilmiş kararların anlık görüntüsü (döngü içinde durum.json yeniden
    # yazıldığı için tek seferde alınır).
    onceki_durum = durum_oku(k)["dosyalar"]
    for kid, d in secili_dosyalar(k, plan):
        yol, kod = d["yol"], d["vaka"]
        if kod not in OTOMATIK_VAKALAR:
            # ⛔ Koşulsuz `durum="bekliyor"` yazmak, `uygula` tekrarında VERİLMİŞ bir yargı
            # kararını `dogrulandi`/`atlandi`'dan düşürüyordu ve geriye ÇELİŞKİLİ bir kayıt
            # kalıyordu (`durum=bekliyor` + `karar=yerel`). Karar kullanıcınındır; `uygula`
            # onu geri alamaz.
            if onceki_durum.get(yol, {}).get("durum") in ("dogrulandi", "atlandi"):
                continue
            durum_kaydet(k, yol, kalem=kid, vaka=kod, durum="bekliyor")
            continue
        hedef = d.get("yeni_yol") or yol
        korunan = None
        try:
            # V6/V1R'nin "L == T"si PLAN anında ölçüldü; plan → uygula arasındaki düzenleme
            # yedeksizdir ⇒ silme `_sil_korunarak` ile (içerik `.yerel`de kalır).
            if kod == "V6":
                korunan = _sil_korunarak(k, yol)
                beklenen = None
            elif kod == "V1R":
                k.checkout_yol(b.yeni_ref, hedef)
                if hedef != yol:
                    korunan = _sil_korunarak(k, yol)
                beklenen = k.blob_sha(b.yeni_ref, hedef)
            else:
                k.checkout_yol(b.yeni_ref, hedef)
                beklenen = k.blob_sha(b.yeni_ref, hedef)
        except Dur as e:
            print(f"FAIL {yol}: {e}", file=sys.stderr)
            durum_kaydet(k, yol, kalem=kid, vaka=kod, durum="bekliyor", not_=str(e))
            hata = 1
            continue
        if korunan:
            print(f"Yedeksiz yerel içerik saklandı: {korunan}")

        gercek = _yazim_sonrasi_sha(k, hedef)
        if gercek != beklenen:
            print(f"FAIL {yol}: yazıldı ama doğrulanamadı (beklenen {beklenen}, disk {gercek})",
                  file=sys.stderr)
            durum_kaydet(k, yol, kalem=kid, vaka=kod, durum="uygulandi",
                         beklenen_sha=beklenen, not_="doğrulanamadı")
            hata = 1
            continue
        durum_kaydet(k, yol, kalem=kid, vaka=kod, durum="dogrulandi",
                     beklenen_sha=beklenen, hedef_yol=hedef)
        if kod == "V5":
            print(f"GERİ GETİRİLDİ: {yol} — yerelde silinmişti, bu yayında güncellendi; "
                  f"istemiyorsan tekrar sil")
        elif kod == "V6":
            print(f"SİLİNDİ: {yol} — template emekliye ayırdı, sende değişmemişti")
        elif kod == "V1R":
            print(f"TAŞINDI: {yol} → {hedef}")
        else:
            print(f"ALINDI: {hedef} ({kod})")

    ozel = sorted({a for kalem in plan["kalemler"] if kalem["id"] in secim_oku(k, plan)
                   for a in kalem["ozel_adimlar"]})
    if ozel:
        print("Özel adımlar (§7 adım 9 — ayrıca koşulmalı): " + ", ".join(ozel))
    return hata


# =====================================================================================================
# ÖNERİ
# =====================================================================================================
def _plan_kaydi(plan: dict, yol: str) -> tuple[str, dict]:
    for kalem in plan["kalemler"]:
        for d in kalem["dosyalar"]:
            if d["yol"] == yol:
                return kalem["id"], d
    raise Dur(f"{yol} planda yok — kartta olmayan bir dosyaya dokunulmaz (§7).")


def komut_oneri(b: Baglam, args) -> int:
    k, plan = b.k, plan_oku(b.k)
    yol = args.yol.replace("\\", "/")
    kid, d = _plan_kaydi(plan, yol)
    taban = b.taban_ref(yol)
    hedef = d.get("yeni_yol") or yol
    if taban is None:
        tasima = (f" Yayın dosyayı taşıyor: yeni içerik `{hedef}` yolunda (`--karar yeni` onu "
                  f"yazar ve `{yol}`u siler; `--karar yerel` taşımayı reddeder)."
                  if hedef != yol else "")
        print(f"DUR: {yol} için taban bilinmiyor (VTB) — otomatik birleştirme YASAK (§4). "
              f"Fark göster, kullanıcı 'yeniyi al / yereli koru / elle' seçsin.{tasima}",
              file=sys.stderr)
        return 2
    t_sha, y_sha = k.blob_sha(taban, yol), k.blob_sha(b.yeni_ref, hedef)
    t = k.blob(t_sha) if t_sha else b""
    y = k.blob(y_sha) if y_sha else b""
    tam = k.kok / yol
    l = tam.read_bytes() if tam.is_file() else b""

    if ikili_mi(k, yol, [t, l, y]):
        print(f"V4B — ikili dosya, birleştirme yok: {yol}. Karar: `isaretle {yol} "
              f"--karar yerel|yeni`.")
        return 1

    birlesik, cakisma = birlestir(k, yol, t, l, y)
    oran = yerel_fark_orani(t, l)
    print(f"--- T→L (senin değişikliğin) ---\n{fark_metni(t, l, 'TABAN', 'YEREL') or '(fark yok)'}")
    print(f"--- T→Y (bizim değişikliğimiz) ---\n{fark_metni(t, y, 'TABAN', 'YENİ') or '(fark yok)'}")
    print(f"Çakışma bloğu: {cakisma} · yerel fark oranı: {oran:.0%} "
          f"(eşik: >{ESIK_CAKISMA_BLOGU} blok ya da >%{int(ESIK_YEREL_FARK * 100)})")

    if cakisma > ESIK_CAKISMA_BLOGU or oran > ESIK_YEREL_FARK:
        elle = k.durum_dizini / "elle"
        for ad, metin in ((f"{yol}.yerel.diff", fark_metni(t, l, "TABAN", "YEREL")),
                          (f"{yol}.yeni.diff", fark_metni(t, y, "TABAN", "YENİ"))):
            h = elle / ad
            h.parent.mkdir(parents=True, exist_ok=True)
            h.write_text(metin, encoding="utf-8")
        print(f"V4c+ESIK — ayrışma eşiği aşıldı, birleştirme DENENMEDİ. Farklar: {elle}\n"
              f"Kullanıcıya 'elle karşılaştırman gerekiyor' de; sonra "
              f"`isaretle {yol} --karar ertelendi --gerekce ...`")
        return 3

    hedef_dosya = k.durum_dizini / "oneri" / yol
    hedef_dosya.parent.mkdir(parents=True, exist_ok=True)
    hedef_dosya.write_bytes(birlesik)
    print(f"Öneri yazıldı: {hedef_dosya}")
    return 1 if cakisma else 0


# =====================================================================================================
# İŞARETLE
# =====================================================================================================
def komut_isaretle(b: Baglam, args) -> int:
    k, plan = b.k, plan_oku(b.k)
    # ⛔ REF PLANA SABİTLENİR (karar 2026-09-20). `b.yeni_ref` CANLIdir: `Baglam` kurulurken
    # yeniden hesaplanır. Plan hedefi çivilerken (`plan["yeni_etiket"]`) işaretleme canlı ref'i
    # okursa, plan ile işaretleme arasında bir `fetch` olması hâlinde İÇERİK yeni sürümden
    # yazılır ama MÜHÜR (beklenen_sha/durum kaydı) ESKİ sürümü der. Geriye sürüklenme için
    # zaten DUR var; İLERİ sürüklenme korumasızdı. K2'nin mühür kararıyla aynı ilke.
    plan_ref = plan.get("yeni_etiket") or b.yeni_ref
    if plan_ref != b.yeni_ref:
        print(f"NOT: plan `{plan_ref}` hedefiyle kuruldu, klonun canlı hedefi artık "
              f"`{b.yeni_ref}`. İşaretleme PLANA sabitlendi — yeni hedefi uygulamak için "
              f"planı yeniden kur (`hazirla`).", file=sys.stderr)
    yol = args.yol.replace("\\", "/")
    if args.karar not in GECERLI_KARARLAR:
        print(f"DUR: geçersiz karar {args.karar!r}. Geçerli: {', '.join(GECERLI_KARARLAR)}",
              file=sys.stderr)
        return 2
    kid, d = _plan_kaydi(plan, yol)
    hedef = d.get("yeni_yol") or yol

    izinli = VAKA_IZINLI_KARARLAR.get(d["vaka"])
    if izinli is not None and args.karar != "ertelendi" and args.karar not in izinli:
        print(f"DUR: {d['vaka']} vakasında `--karar {args.karar}` TANIMLI DEĞİL "
              f"(TASARIM §5 {d['vaka']} kartı: {', '.join(sorted(izinli))}, ayrıca `ertelendi`). "
              f"{yol} dosyasına DOKUNULMADI.", file=sys.stderr)
        return 2

    if args.karar == "ertelendi":
        if not args.gerekce:
            print("DUR: `--karar ertelendi` GEREKÇE ister (§6 `atlandi(gerekce)`).",
                  file=sys.stderr)
            return 2
        durum_kaydet(k, yol, kalem=kid, vaka=d["vaka"], durum="atlandi",
                     karar="ertelendi", gerekce=args.gerekce)
        print(f"ERTELENDİ: {yol} — {args.gerekce}")
        return 0

    if args.karar == "yerel":
        sha = k.disk_sha(yol)
        durum_kaydet(k, yol, kalem=kid, vaka=d["vaka"], durum="dogrulandi",
                     karar="yerel", beklenen_sha=sha, hedef_yol=yol)
        print(f"YEREL KORUNDU: {yol}")
        return 0

    if args.karar == "yeni":
        y_sha = k.blob_sha(plan_ref, hedef)
        if y_sha is None:
            print(f"DUR: {hedef} yeni sürümde yok — `--karar yeni` uygulanamaz.", file=sys.stderr)
            return 2
        korunan = _yerel_kopya(k, hedef) if _yedeksiz_mi(k, hedef) else None
        k.checkout_yol(plan_ref, hedef)
        kaynak_korunan = None
        if hedef != yol and (k.kok / yol).is_file():
            kaynak_korunan = _sil_korunarak(k, yol)
        for ad in (korunan, kaynak_korunan):
            if ad:
                print(f"Yedeksiz yerel içerik saklandı: {ad}")
        return _dogrula_ve_kaydet(k, kid, yol, hedef, d["vaka"], "yeni", y_sha)

    if args.karar == "yeniden-adlandir":
        y_sha = k.blob_sha(plan_ref, hedef)
        if y_sha is None:
            print(f"DUR: {hedef} yeni sürümde yok.", file=sys.stderr)
            return 2
        # ⚠ Ezilecek dosya DAİMA `hedef`tir. Yeniden adlandırmalı bir V7'de (`yol` ≠ `hedef`)
        # kullanıcının dosyası YENİ yolda durur; eski kod `yol`u saklayıp `hedef`i eziyordu.
        korunan = _yerel_kopya(k, hedef)
        kaynak_korunan = None
        if hedef != yol and (k.kok / yol).is_file():
            # taşımanın kaynağı: etikette yalnız `hazirla` ANINDAKİ hâli durur
            kaynak_korunan = _sil_korunarak(k, yol)
        k.checkout_yol(plan_ref, hedef)
        if korunan:
            print(f"Senin dosyan korundu: {korunan}")
        if kaynak_korunan:
            print(f"Yedeksiz yerel içerik saklandı: {kaynak_korunan}")
        return _dogrula_ve_kaydet(k, kid, yol, hedef, d["vaka"], "yeniden-adlandir", y_sha)

    # birlesik
    oneri = k.durum_dizini / "oneri" / yol
    if not oneri.is_file():
        print(f"DUR: öneri dosyası yok — önce `guncelle.py oneri {yol}`.", file=sys.stderr)
        return 2
    veri = oneri.read_bytes()
    metin = veri.decode("utf-8", "replace")
    y_sha_ref = k.blob_sha(plan_ref, hedef)
    kalanlar = cakisma_isaretleri(
        metin, k.blob(y_sha_ref).decode("utf-8", "replace") if y_sha_ref else None)
    if kalanlar:
        print(f"FAIL {yol}: öneri dosyasında çakışma işareti duruyor ({', '.join(kalanlar)}). "
              f"Çakışmaları çöz, sonra yeniden işaretle.", file=sys.stderr)
        durum_kaydet(k, yol, kalem=kid, vaka=d["vaka"], durum="bekliyor", karar="birlesik",
                     not_="çakışma işareti kaldı")
        return 1
    beklenen = k.stdin_sha(hedef, veri)
    korunan = _yerel_kopya(k, hedef) if _yedeksiz_mi(k, hedef) else None
    k.yaz(hedef, veri)
    kaynak_korunan = None
    if hedef != yol and (k.kok / yol).is_file():
        kaynak_korunan = _sil_korunarak(k, yol)
    for ad in (korunan, kaynak_korunan):
        if ad:
            print(f"Yedeksiz yerel içerik saklandı: {ad}")
    return _dogrula_ve_kaydet(k, kid, yol, hedef, d["vaka"], "birlesik", beklenen)


def _yedeksiz_mi(k: Klon, yol: str) -> bool:
    """Diskteki içeriğin `guncelle-oncesi-*` etiketinde AYNI blob'u var mı? Yoksa üzerine
    yazmak GERİ ALINAMAZ (ne `geri-al` ne `git fsck` getirebilir).

    İki yedeksiz sınıf vardır: ① izlenmeyen dosya (`hazirla`nın `git add -u`'su commit'lemez)
    ② etiket atıldıktan SONRA yapılan düzenleme.
    """
    disk = k.disk_sha(yol)
    if disk is None:
        return False                      # dosya yok → ezilecek içerik de yok
    try:
        etiket = geri_donus_etiketi(k)
    except Dur:
        return True                       # geri dönüş noktası hiç yok → her yazma yedeksiz
    return k.blob_sha(etiket, yol) != disk


def _sil_korunarak(k: Klon, yol: str, kurtarilabilir_ref: str | None = None) -> str | None:
    """`k.sil` — ama önce yedeksiz içeriği `.yerel` olarak saklar. Döner: saklanan ad ya da None.

    ⛔ Motorun dosya SİLMELERİ buradan geçer (v0.5.6). Eskiden yedek sorusu yalnız ezilen
    HEDEF için soruluyordu; taşımanın KAYNAĞI, otomatik silmeler (V6/V1R) ve `geri-al`
    doğrudan `k.sil` ile gidiyordu. İzlenen kaynak etikette durur — ama yalnız `hazirla`
    ANINDAKİ hâli; sonraki düzenleme (V6/V1R'nin "L == T"si de PLAN anında ölçülür) ve
    izlenmeyen dosya sessizce kayboluyordu (ölçüldü 2026-09-23, `TasimaKaynagiYedekTest`).
    Silme davranışı DEĞİŞMEZ: yol boşalır, yalnız içerik korunur.
    `kurtarilabilir_ref`: içerik bu ref'teki blob'la aynıysa da yedekli sayılır (`geri-al`
    motorun kendi yazdığı dosyayı silerken `.yerel` çöpü üretmesin).
    """
    korunan = None
    if _yedeksiz_mi(k, yol) and not (
            kurtarilabilir_ref and k.blob_sha(kurtarilabilir_ref, yol) == k.disk_sha(yol)):
        korunan = _yerel_kopya(k, yol)
    k.sil(yol)
    return korunan


def _yerel_kopya(k: Klon, yol: str) -> str | None:
    """Üzerine yazılacak yerel dosyayı `<yol>.yerel` olarak saklar. Döner: saklanan ad (ya da None).

    Var olan bir `.yerel`i EZMEZ — sayı ekler. Yedek yoksa kullanıcı içeriği geri alınamaz
    biçimde kaybeder: `hazirla` yalnız İZLENEN dosyaları commit'ler (`git add -u`), dolayısıyla
    izlenmeyen bir kullanıcı dosyasının `guncelle-oncesi-*` etiketinde blob'u YOKTUR.
    """
    tam = k.kok / yol
    if not tam.is_file():
        return None
    aday = tam.with_name(tam.name + ".yerel")
    n = 1
    while aday.exists():
        aday = tam.with_name(f"{tam.name}.yerel.{n}")
        n += 1
    shutil.move(str(tam), str(aday))
    return aday.relative_to(k.kok).as_posix()


def _yazim_sonrasi_sha(k: Klon, hedef: str) -> str | None:
    """Yazım SONRASI geri okuma. `disk_sha` hash'leyemezse `Dur` atar; yazım olmuş olduğu için
    burada akışı kesmek dosyayı durum kaydı olmadan bırakırdı ⇒ "doğrulanamadı" say (hiçbir
    beklenen sha'ya eşit olmayan bir metin döner)."""
    try:
        return k.disk_sha(hedef)
    except Dur as e:
        return f"ÖLÇÜLEMEDİ ({e})"


def _dogrula_ve_kaydet(k: Klon, kid: str, yol: str, hedef: str, vaka: str,
                       karar: str, beklenen: str | None) -> int:
    gercek = _yazim_sonrasi_sha(k, hedef)
    if gercek != beklenen:
        print(f"FAIL {yol}: yazıldı ama geri okunduğunda farklı "
              f"(beklenen {beklenen}, disk {gercek}).", file=sys.stderr)
        durum_kaydet(k, yol, kalem=kid, vaka=vaka, durum="uygulandi", karar=karar,
                     beklenen_sha=beklenen, not_="doğrulanamadı")
        return 1
    durum_kaydet(k, yol, kalem=kid, vaka=vaka, durum="dogrulandi", karar=karar,
                 beklenen_sha=beklenen, hedef_yol=hedef)
    print(f"İŞARETLENDİ: {yol} → {karar} (dogrulandi)")
    return 0


# =====================================================================================================
# ÖLÇÜM
# =====================================================================================================
def _izole_tmp(k: Klon) -> tuple[dict, str]:
    """Repo DIŞI TMP (ölçülmüş tuzak: repo içi TMP'de git testleri yanlış FAIL verir)."""
    d = tempfile.mkdtemp(prefix="axet-guncelle-tmp-")
    env = dict(os.environ)
    env.update({"TMP": d, "TEMP": d, "TMPDIR": d,
                "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"})
    return env, d


def _komutu_coz(komut: str) -> list[str]:
    parcalar = komut.split()
    if parcalar and parcalar[0] in ("python", "python3", "py"):
        parcalar[0] = sys.executable
    return parcalar


def _betik_yolu(parcalar: list[str]) -> str | None:
    """Ölçüm komutunun VARLIĞI önceden denetlenecek dosya/dizin argümanı; None = denetlenecek yol yok.

    ⛔ Z54 (2026-09-22, canlı `butunluk.json`): üç çağrı yeri (`olc` · `ozel-adim` · `butunluk`)
    `parcalar[1]`i koşulsuz betik yolu sayıyordu. `python -m unittest discover -s X` için
    `parcalar[1]` = `-m` ⇒ `<kök>/-m` hiç yoktur ⇒ adım HER ZAMAN "ÖLÇÜLEMEDİ — -m yok" yazılıyor,
    komut hiç koşmuyordu (harita.json'da 5 sınıf / 6 komut + bütünlükteki sap-code-review adımı).
    `-m` biçiminde denetlenecek yol YALNIZ `-m unittest discover -s <dizin>`in dizinidir (başka
    modülde `-s` başka anlam taşır: pytest'te "çıktıyı yakalama"); öbür `-m` çağrıları için ön denetim
    yoktur, varlık rc ile hükme bağlanır."""
    if len(parcalar) < 2:
        return None
    if parcalar[1] == "-m":
        if parcalar[2:4] == ["unittest", "discover"] and "-s" in parcalar[4:]:
            i = parcalar.index("-s", 2)
            return parcalar[i + 1] if i + 1 < len(parcalar) else None
        return None
    return parcalar[1]


_SONUC_DESEN = re.compile(r"(\d+)\s*failure", re.I)


# Ölçüm komutlarının zaman aşımı. ⛔ `_run`'ın 1800 sn'lik VARSAYILANI burada YETMEZ ve
# yetmediği ÖLÇÜLDÜ (2026-09-20, gerçek tüketici klonu): kök takımı CI'da 2411 sn sürüyor,
# yani `once` turu 1800 sn'de **yapısal olarak** zaman aşımına uğruyordu — planında
# `test-kok`/`bakim-script-kok` sınıfı olan HER tüketicide. Üstelik aşım `TimeoutExpired`
# olarak yukarı kaçıyor, `komut_olc`'nin "ÖLÇÜLEMEDİ ≠ temiz" koluna HİÇ uğramıyordu:
# 35 dakikalık ölçüm traceback'le çöküp `olcum-once.json`'u yazmadan ölüyordu.
# Değer kanıttan türetildi: gözlenen en uzun CI koşumu 2411 sn; yerel makine daha yavaş
# olabilir ⇒ ~2x pay. Yine de aşılırsa artık ÇÖKMEZ, `ÖLÇÜLEMEDİ` yazılır.
OLCUM_ZAMAN_ASIMI = 5400


def _yargi_gerektiren(plan: dict) -> list[str]:
    """Planda YEREL DEĞİŞİKLİK yüzünden yargı isteyen dosyalar (§4 `YARGI_VAKALARI`).

    Tek kaynak bilerek `YARGI_VAKALARI`dır: "yerel değişiklik var mı" sorusunun cevabı zaten
    o kümedir; ikinci bir liste tutmak onunla sessizce ayrışırdı.
    """
    return sorted({f["yol"] for kal in plan.get("kalemler", [])
                   for f in kal.get("dosyalar", []) if f.get("vaka") in YARGI_VAKALARI})


def _ci_tabani(b: Baglam, plan: dict) -> dict | None:
    """`once` turunun yerine CI hükmünü koy — KOŞULLAR SAĞLANIYORSA (Z16, 2026-09-20).

    ⛔ NEDEN (hız DEĞİL, doğruluk): `once` ve `sonra` **aynı testleri koşmuyor**. `komut_olc`
    testleri klon kökünde koşar (`calisma = k.kok / cwd`) ve `tests/**` güncellemenin parçası
    olabilir ⇒ `once` ESKİ test kodunu, `sonra` YENİ test kodunu ölçer. `yeni_kirmizilar` ise
    ikisini komut kimliği bazında karşılaştırır. Testlerin kendisi değişirken *"fark =
    regresyon"* çıkarımı KURULAMAZ. CI ise yeni testleri yeni ürüne karşı temiz ortamda
    ölçmüştür ⇒ daha iyi bir tabandır.

    ⛔ YALNIZ yargı vakası YOKKEN: yerel değişiklik varsa uygulama sonrası ağaç yayınlanan
    ağaçtan FARKLI olur ve o ağacı hiçbir CI test etmemiştir ⇒ o vakada ölçüm zorunludur.

    ⛔ FAIL-SAFE: her belirsizlikte `None` = normal ölç. Dosya yok (eski yayın), ayrıştırılamadı,
    etiket tutmadı, yeşil değil → hepsinde ÖLÇ. "Ölçemedim" asla "atlayabilirim" demek değildir.
    """
    if _yargi_gerektiren(plan):
        return None
    etiket = plan.get("yeni_etiket")
    if not etiket:
        return None
    r = b.k.git("show", "origin/main:guncelle/ci-durum.json")
    if r.returncode != 0:
        return None
    try:
        veri = json.loads(r.stdout)
    except ValueError:
        return None
    kayit = (veri.get("yayinlar") or {}).get(etiket)
    if not isinstance(kayit, dict) or kayit.get("hepsi_yesil") is not True:
        return None
    takimlar = kayit.get("takimlar") or []
    if not takimlar or any(t.get("sonuc") != "success" for t in takimlar):
        return None
    return {
        "asama": "once", "zaman": _simdi(), "kaynak": "ci", "testler": [],
        "ci": kayit, "etiket": etiket,
        "gerekce": (f"{etiket} yayınının CI hükmü taban alındı: planda yargı gerektiren "
                    "(yerel değişiklik) dosya YOK, dolayısıyla uygulama sonrası ağaç "
                    "yayınlanan ağacın aynısı olacak ve CI o ağacı zaten ölçtü."),
        "kapsam_disi": ("Bu taban YEREL ortamda ölçülmedi — CI ortamında ölçüldü "
                        f"({kayit.get('isletim_sistemi', 'BİLİNMİYOR')} · Python "
                        f"{kayit.get('python', 'BİLİNMİYOR')}). Yerele özgü sapma (yerel ayar, "
                        "uzun yol, antivirüs, eksik araç) bu tabanda GÖRÜNMEZ; onu `sonra` turu "
                        "yakalar — `sonra` turu da CI ile ikame edilirse (Z26) yalnız bütünlük "
                        "turundaki asgari yerel kontrol (install --dry-run · doctor · hızlı "
                        "takımlar) kalır. Yargı vakası çıksaydı ikame YAPILMAZDI."),
    }


# Yayın aracının ÜRETTİĞİ meta veri (`maintenance/yayin_hazirla.py::URETILEN_DOSYALAR` ile aynı
# küme): tüketici klonuna UYGULANMAZ, motor onları `origin/main`'den okur ⇒ disk↔yayın ağacı
# karşılaştırmasında sayılmazlar. Ölçüldü (2026-09-21): dışlanmasalar ağaç HİÇBİR ZAMAN eşit çıkmaz.
YAYIN_META_YOLLARI = ("CHANGELOG.md", "guncelle/yayinlar.json", "guncelle/ci-durum.json")


def _agac_yayinla_ayni(k: Klon, etiket: str) -> tuple[bool, str]:
    """Diskteki ağaç (izlenmeyen ama yok sayılmayan dosyalar DAHİL) `etiket` ağacının AYNISI mı?

    Plan beyanı değil DOĞRUDAN ölçüm: geçici bir index'e çalışma ağacı `git add -A` ile alınır
    ve o index `etiket` ile karşılaştırılır. Asıl index'e dokunulmaz. Her git hatası = "aynı değil"
    (fail-safe: ölçemediysek ölçüme döneriz). Yalnız `YAYIN_META_YOLLARI` karşılaştırma dışıdır."""
    haric = [f":(exclude){y}" for y in YAYIN_META_YOLLARI]
    with tempfile.TemporaryDirectory() as d:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(d) / "index"))
        for argv in (["add", "-A", "--", "."],
                     ["diff", "--cached", "--name-status", etiket, "--", "."] + haric):
            r = _run(["git", "-C", str(k.kok)] + argv, k.kok, env=env)
            if r.returncode != 0:
                return False, f"disk ağacı ölçülemedi (git {argv[0]} rc={r.returncode})"
        fark = [s for s in (r.stdout or "").splitlines() if s.strip()]
        if fark:
            return False, (f"disk ağacı {etiket} ağacından FARKLI ({len(fark)} yol: "
                           + ", ".join(s.replace("\t", " ") for s in fark[:5])
                           + (" …" if len(fark) > 5 else "") + ")")
    return True, (f"disk ağacı {etiket} ağacıyla aynı (geçici index ile ölçüldü; "
                  "gitignore'lu dosyalar ve satır sonu farkı karşılaştırma DIŞI)")


def _ci_sonrasi(b: Baglam, plan: dict) -> dict | None:
    """`sonra` turunun yerine CI hükmünü koy — İKİ şart birden sağlanırsa (Z26, 2026-09-21).

    ⛔ NEDEN: yargı vakası yokken uygulama sonrası ağaç, CI'nin temiz ortamda ÖLÇTÜĞÜ yayın
    ağacının aynısıdır ⇒ aynı testleri kullanıcının makinesinde yeniden koşmak yeni bilgi
    üretmez, yalnız dakikalar harcar (ölçüldü: sonra turu ~25-30 dk).
    Şart 1: `_ci_tabani` koşulları (yargı vakası yok + etiket için CI `hepsi_yesil`).
    Şart 2: plan beyanına GÜVENİLMEZ — disk ağacı etiket ağacıyla DOĞRUDAN karşılaştırılır.
    ⛔ FAIL-SAFE: biri tutmazsa `None` = normal ölç.
    """
    taban = _ci_tabani(b, plan)
    if taban is None:
        return None
    ayni, neden = _agac_yayinla_ayni(b.k, taban["etiket"])
    if not ayni:
        print(f"[ÖLÇ] sonra-ölçüm CI ile ikame EDİLMEDİ — {neden}")
        return None
    return {
        "asama": "sonra", "zaman": _simdi(), "kaynak": "ci", "testler": [],
        "ci": taban["ci"], "etiket": taban["etiket"],
        "gerekce": f"{neden}; bu ağacı CI ölçtü ve hepsi yeşil.",
        "kapsam_disi": ("Testler YEREL ortamda koşulmadı. Yerel ortamın asgari kontrolü "
                        "(install --dry-run · doctor · hızlı takımlar) bütünlük turunda koşar."),
    }


def _taban_argv(komut: str) -> tuple[str, ...] | None:
    """`-k <desen>` ekini atılmış argv — komut `-k` taşımıyorsa `None`.

    `-k`'nın anlamı ÇALIŞTIRICIDAN okunur, tahmin edilmez: `tests/run_tests.py` onu
    `loader.testNamePatterns = ["*<desen>*"]` yapar (`tests/run_tests.py:38`), yani
    **yalnız süzer** — filtreli koşumun kapsamı filtresizin ÖZ ALT KÜMESİDİR.
    """
    parcalar = komut.split()
    if "-k" not in parcalar:
        return None
    i = parcalar.index("-k")
    if i + 1 >= len(parcalar):          # değersiz `-k` — süzme iddiası kurulamaz, DOKUNMA
        return None
    return tuple(parcalar[:i] + parcalar[i + 2:])


def _kapsananlari_ayikla(testler: list[dict]) -> tuple[list[dict], list[str]]:
    """Aynı cwd'de FİLTRESİZ eşi de koşacaksa `-k` filtreli komutu listeden düşür (A, Z16).

    Gerçek koşumda ölçüldü (2026-09-20, v0.3.0 planı): 18 komutun 6'sı
    `python tests/run_tests.py -k …` idi ve aynı listede FİLTRESİZ `python tests/run_tests.py`
    de vardı (sınıf `test-kok` + `bakim-script-kok`) ⇒ o 6 koşum tur başına iki kez, tümüyle
    gereksiz tekrarlanıyordu.

    ⛔ Bu bir sezgi değil, çalıştırıcının kendi semantiğinden çıkan KAPSAMA ilişkisidir
    (`_taban_argv`). Düşürme koşulları dar: aynı `cwd`, aynı taban argv, ve filtresiz eş
    AYNI ÖLÇÜMDE koşuyor olmalı.

    ⚠ Kaybedilmeyen şey: "bayat/yazım hatalı `-k` deseni" tanısı bu ayıklamayla körleşmez —
    onu BAĞIMSIZ bir katman ölçer (`tests/test_guncelle_harita.py`, harita doğrulayıcı: hiçbir
    testle eşleşmeyen desen ve değersiz `-k` ayrı ayrı yakalanır) ve o katman CI'da koşar.
    """
    filtresiz = {(t.get("cwd", "."), tuple(t["komut"].split()))
                 for t in testler if "-k" not in t["komut"].split()}
    kalan, dusen = [], []
    for t in testler:
        taban = _taban_argv(t["komut"])
        if taban is not None and (t.get("cwd", "."), taban) in filtresiz:
            dusen.append(f"{t.get('cwd', '.')}::{t['komut']}")
            continue
        kalan.append(t)
    return kalan, dusen


def komut_olc(b: Baglam, args) -> int:
    if args.asama not in ("once", "sonra"):
        print("DUR: --asama yalnız `once` ya da `sonra` olabilir.", file=sys.stderr)
        return 2
    k, plan = b.k, plan_oku(b.k)
    if args.asama == "once":
        ikame = _ci_tabani(b, plan)
        if ikame is not None:
            _yaz_json(k.durum_dizini / "olcum-once.json", ikame)
            print(f"[İKAME] önce-ölçüm KOŞULMADI — taban {ikame['etiket']} CI hükmü. "
                  f"{ikame['gerekce']}")
            print(f"KAPSAM — {ikame['kapsam_disi']}")
            return 0
    else:
        ikame = _ci_sonrasi(b, plan)
        if ikame is not None:
            _yaz_json(k.durum_dizini / "olcum-sonra.json", ikame)
            print(f"[İKAME] sonra-ölçüm KOŞULMADI — {ikame['etiket']} CI hükmü. "
                  f"{ikame['gerekce']}")
            print(f"KAPSAM — {ikame['kapsam_disi']}")
            return 0
    testler, gorulen = [], set()
    for _kid, d in secili_dosyalar(k, plan):
        sinif = sinif_bul(d["yol"], b.harita)
        for t in (sinif or {}).get("test", []):
            anahtar = (t["komut"], t.get("cwd", "."))
            if anahtar in gorulen:
                continue
            gorulen.add(anahtar)
            testler.append(t)
    testler, kapsanan = _kapsananlari_ayikla(testler)
    if kapsanan:
        print(f"[KAPSANDI] {len(kapsanan)} filtreli komut koşulmadı — aynı cwd'de filtresiz eşi "
              f"koşuyor, kapsamı onun öz alt kümesi: {', '.join(kapsanan)}")

    env, tmp = _izole_tmp(k)
    sonuclar = []
    try:
        for t in testler:
            calisma = (k.kok / t.get("cwd", ".")).resolve()
            kimlik = f"{t.get('cwd', '.')}::{t['komut']}"
            if not calisma.is_dir():
                sonuclar.append({"kimlik": kimlik, "cikis": None, "failure": None,
                                 "not": "ÖLÇÜLEMEDİ — cwd yok ('temiz' DEĞİL)"})
                continue
            ilk = _komutu_coz(t["komut"])
            betik = _betik_yolu(ilk)
            if betik is not None and not (calisma / betik).exists():
                sonuclar.append({"kimlik": kimlik, "cikis": None, "failure": None,
                                 "not": f"ÖLÇÜLEMEDİ — {betik} yok ('temiz' DEĞİL)"})
                continue
            try:
                r = _run(ilk, calisma, env=env, timeout=OLCUM_ZAMAN_ASIMI)
            except subprocess.TimeoutExpired:
                # ⛔ ÇÖKME DEĞİL, HÜKÜM: aşım da bir ölçüm sonucudur ve 'temiz' DEĞİLDİR.
                # Diğer komutlar ölçülmeye devam eder; kayıt yine de diske yazılır.
                sonuclar.append({"kimlik": kimlik, "cikis": None, "failure": None,
                                 "not": f"ÖLÇÜLEMEDİ — {OLCUM_ZAMAN_ASIMI} sn zaman aşımı "
                                        f"('temiz' DEĞİL)"})
                print(f"[ZAMAN AŞIMI] {kimlik} — {OLCUM_ZAMAN_ASIMI} sn'de bitmedi; "
                      f"ÖLÇÜLEMEDİ yazıldı, akış durmadı")
                continue
            cikti = (r.stdout or "") + (r.stderr or "")
            m = _SONUC_DESEN.search(cikti)
            sonuclar.append({"kimlik": kimlik, "cikis": r.returncode,
                             "failure": int(m.group(1)) if m else None,
                             "on_kosul": t.get("on_kosul")})
            print(f"[{'OK ' if r.returncode == 0 else 'RED'}] {kimlik} (rc={r.returncode})")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    _yaz_json(k.durum_dizini / f"olcum-{args.asama}.json",
              {"asama": args.asama, "zaman": _simdi(), "testler": sonuclar,
               "kapsam_disi": "Bu ölçüm YALNIZ seçili sınıfların haritada yazılı test "
                              "komutlarını koşar; koşulamayanlar 'ÖLÇÜLEMEDİ' yazılır."})
    # §6: "0 koştu (kırmızı olsa bile) · **2 koşturulamadı**" · §7 adım 6: "2 → DUR".
    # ⛔ Koşulsuz `return 0`, "ölçülemeyen güncelleme yapılmaz" kuralını mekanik olarak devre
    # dışı bırakıyordu: hem "haritada hiç test komutu yok" hem de "komutların hiçbiri
    # koşturulamadı" hâllerinde akış "ölçüldü" sayılıp devam ediyordu. ÖLÇÜLEMEDİ ≠ TEMİZ.
    kosan = [s for s in sonuclar if s.get("cikis") is not None]
    if kosan:
        return 0
    if not sonuclar:
        print("DUR: seçili sınıfların haritada test komutu YOK — hiçbir şey ÖLÇÜLEMEDİ "
              "('temiz' DEĞİL, §6 çıkış 2).", file=sys.stderr)
    else:
        print(f"DUR: {len(sonuclar)} test komutunun HİÇBİRİ koşturulamadı — hepsi ÖLÇÜLEMEDİ "
              f"('temiz' DEĞİL, §6 çıkış 2). Ayrıntı: "
              + " · ".join(f"{s['kimlik']}: {s.get('not', '—')}" for s in sonuclar[:5]),
              file=sys.stderr)
    return 2


def yeni_kirmizilar(k: Klon) -> list[str]:
    once = _oku(k.durum_dizini / "olcum-once.json", None)
    sonra = _oku(k.durum_dizini / "olcum-sonra.json", None)
    if once is None or sonra is None:
        return []
    if once.get("kaynak") == "ci":
        # ⛔ CI tabanı = "hepsi yeşil" (`_ci_tabani` bunu `hepsi_yesil` + takım başına
        # `sonuc == "success"` ile DOĞRULAMADAN bu dosyayı hiç yazmaz). Dolayısıyla `sonra`
        # turundaki HER kırmızı yenidir. Bu dal olmasaydı `once["testler"]` boş olduğu için
        # aşağıdaki eşleme hiçbir kimliği bulamaz ve döngü her testi `continue` ile atlardı ⇒
        # her şey kırmızıyken bile "yeni kırmızı yok" denirdi. Sessiz sahte-yeşil.
        return [t["kimlik"] for t in sonra["testler"] if t.get("cikis") not in (0, None)]
    o = {t["kimlik"]: t for t in once["testler"]}
    yeni = []
    for t in sonra["testler"]:
        eski = o.get(t["kimlik"])
        if eski is None:
            continue
        if eski.get("cikis") == 0 and t.get("cikis") not in (0, None):
            yeni.append(t["kimlik"])
        elif (eski.get("failure") is not None and t.get("failure") is not None
              and t["failure"] > eski["failure"]):
            yeni.append(t["kimlik"])
    return yeni


# =====================================================================================================
# ÖZEL ADIM
# =====================================================================================================
_PY_KOMUT = re.compile(r"python\s+[\w./\\-]+\.py[^,;\n]*")

# ⛔ `ozel-adim` SERBEST METİNDEN çıkardığı komutu koşar; metin `harita.json`'dan gelir.
# Kabuk enjeksiyonu YOK (`shell=` bu dosyada hiç kullanılmıyor) — sorun başkadır: bir Türkçe
# cümleye `python scripts/install.py --sap-write` yazılması, `config/permissions.json`'ın
# `deny`'ını (`*install.py*--sap-write*`) TEK bir izinli `guncelle.py` çağrısı içinden atlatır.
# Motor, klondaki `permissions.json`'a güvenemez (K4: klon eski/bozuk olabilir) ⇒ karar
# motorun KENDİ kopyasında, DAR bir allowlist olarak durur: yalnız şu betikler, yalnız şu
# bayraklar. Listede olmayan her şey koşturulmaz, kullanıcıya MANUEL ADIM olarak bırakılır.
# Bugün haritadaki tüm özel adım komutları bu listeye sığıyor (ölçüldü: `scripts/install.py`
# çıplak ve `--dry-run` ile).
#
# ⭐ KAPSAM BEYANI — bu allowlist YALNIZ `ozel-adim` yüzeyini kapsar (asimetri BİLİNÇLİDİR).
# BAKILAN: `komut_ozel_adim`ın `harita.json` → `ozel_adim` SERBEST METNİNDEN `_PY_KOMUT` ile
#   çıkardığı komutlar. Tehdit modeli: bir Türkçe cümlenin içine sıkıştırılan tehlikeli bayrak
#   göz denetiminden kaçar ve tek bir izinli `guncelle.py` çağrısı içinden koşar.
# BAKILMAYAN (ve kasıtlı olarak BAKILMAYACAK): `komut_olc`ün `harita.json` → `test[].komut`
#   listesi ve `komut_butunluk`un motor kaynağına GÖMÜLÜ komutları. Gerekçe — ölçüldü:
#   (a) o komutlar serbest metinden ÇIKARILMAZ, yapısal bir listede tek tek durur (gözden
#       kaçma tehdidi yok, `butunluk`unkiler zaten kodun kendisinde);
#   (b) `harita_yukle` MOTORUN KENDİ kopyasını okur (K4) — klonunkine hiç bakılmaz;
#   (c) haritadaki 44 test komutunun çoğu `python -m unittest discover -s ...` ve
#       `python skills-sap/.../tests/run_tests.py` biçimindedir; bunları bu allowlist'ten
#       geçirmek `olc`u her sınıfta rc=2 (DUR) yapardı — yani ölçüm mekanizmasını kapatırdı;
#   (d) `olc` zaten KLONDA duran test betiklerini koşar ve o betiklerin İÇERİĞİ motor
#       tarafından denetlenemez ⇒ komut-dizgesi allowlist'i orada SAHTE GÜVENCE olurdu.
# `_ozel_adim_izinli_mi` bu yüzden `komut_olc`ten çağrılmaz. Bu satırları silmeden önce
# `test_olc_ALLOWLISTTEN_GECMEZ_kapsam_beyani` testini oku.
OZEL_ADIM_IZINLI: dict[str, set[str]] = {
    "scripts/install.py": {"--dry-run"},
}


def _ozel_adim_izinli_mi(komut: str) -> tuple[bool, str]:
    """(izinli mi, red sebebi). Allowlist DIŞINDA kalan her şey reddedilir (fail-closed)."""
    parcalar = komut.split()
    if len(parcalar) < 2 or parcalar[0] not in ("python", "python3", "py"):
        return False, "yorumlayıcı `python` değil"
    betik = parcalar[1].replace("\\", "/")
    if betik not in OZEL_ADIM_IZINLI:
        return False, f"betik allowlist'te yok: {betik}"
    fazla = [p for p in parcalar[2:] if p not in OZEL_ADIM_IZINLI[betik]]
    if fazla:
        return False, f"izinli olmayan bayrak/argüman: {' '.join(fazla)}"
    return True, ""


def komut_ozel_adim(b: Baglam, args) -> int:
    k = b.k
    sinif = next((s for s in b.harita["siniflar"] if s["sinif"] == args.ad), None)
    if sinif is None or not sinif.get("ozel_adim"):
        print(f"DUR: '{args.ad}' sınıfının özel adımı yok.", file=sys.stderr)
        return 2
    metin = sinif["ozel_adim"]
    komutlar = [m.group(0).strip() for m in _PY_KOMUT.finditer(metin)]
    d = durum_oku(k)
    kayit = d.setdefault("ozel_adimlar", {}).setdefault(args.ad, {})
    env, tmp = _izole_tmp(k)
    try:
        if not komutlar:
            kayit.update({"durum": "manuel", "metin": metin, "zaman": _simdi()})
            durum_yaz(k, d)
            print(f"MANUEL ADIM ({args.ad}): {metin}\n  (koşulacak komut içermiyor — "
                  f"kullanıcıya aynen söyle)")
            return 0
        reddedilen = []
        for komut in komutlar:
            ok, sebep = _ozel_adim_izinli_mi(komut)
            if not ok:
                reddedilen.append({"komut": komut, "sebep": sebep})
        if reddedilen:
            # HİÇBİRİ koşulmaz: aynı metindeki izinli komutu koşup diğerini atlamak, adımı
            # yarım uygulanmış bir durumda bırakırdı.
            kayit.update({"durum": "manuel", "metin": metin, "zaman": _simdi(),
                          "izin_disi": reddedilen})
            durum_yaz(k, d)
            print(f"MANUEL ADIM ({args.ad}): motor bu adımı KOŞMAZ — çıkarılan komut(lar) "
                  f"allowlist dışında:")
            for x in reddedilen:
                print(f"  · `{x['komut']}` → {x['sebep']}")
            print(f"  Metin aynen: {metin}\n  (kullanıcı kendi terminalinde, kendi izin "
                  f"kurallarıyla çalıştırır — `config/permissions.json` orada uygulanır)")
            return 0
        cikislar = []
        for komut in komutlar:
            parcalar = _komutu_coz(komut)
            betik = _betik_yolu(parcalar)
            if betik is not None and not (k.kok / betik).exists():
                cikislar.append({"komut": komut, "cikis": None,
                                 "not": "ÖLÇÜLEMEDİ — betik yok ('temiz' DEĞİL)"})
                print(f"ATLANDI: {komut} (betik yok)")
                continue
            try:
                r = _run(parcalar, k.kok, env=env, timeout=OLCUM_ZAMAN_ASIMI)
            except subprocess.TimeoutExpired:
                cikislar.append({"komut": komut, "cikis": None,
                                 "not": f"ÖLÇÜLEMEDİ — {OLCUM_ZAMAN_ASIMI} sn zaman aşımı"})
                kayit.update({"durum": "hata", "komutlar": cikislar, "zaman": _simdi()})
                durum_yaz(k, d)
                print(f"FAIL özel adım {args.ad}: `{komut}` {OLCUM_ZAMAN_ASIMI} sn'de bitmedi "
                      f"(ÖLÇÜLEMEDİ — 'temiz' DEĞİL)", file=sys.stderr)
                return 1
            print((r.stdout or "") + (r.stderr or ""), end="")
            cikislar.append({"komut": komut, "cikis": r.returncode})
            if r.returncode != 0:
                kayit.update({"durum": "hata", "komutlar": cikislar, "zaman": _simdi()})
                durum_yaz(k, d)
                print(f"FAIL özel adım {args.ad}: `{komut}` rc={r.returncode}", file=sys.stderr)
                return r.returncode
        kayit.update({"durum": "kostu", "komutlar": cikislar, "zaman": _simdi()})
        durum_yaz(k, d)
        print(f"ÖZEL ADIM KOŞTU: {args.ad}")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# =====================================================================================================
# BÜTÜNLÜK (§8)
# =====================================================================================================
ASGARI_GUVENCE_YOLLARI = [
    "core/sap/00-sap.md",
    "skills-sap/sap-adt-foundation/scripts/sapadt/gate.py",
    "skills-sap/sap-adt-foundation/scripts/sapadt/_reviewer.py",
    "skills-sap/sap-adt-foundation/scripts/sapadt/lib/validators/run_review.py",
    "skills-sap/sap-adt-foundation/scripts/sapadt/sap_adt_cli.py",
    "config/permissions.json",
]


def komut_butunluk(b: Baglam, args) -> int:
    k = b.k
    plan = _oku(k.durum_dizini / "plan.json", {"kalemler": []})
    ust_siniflar = set()
    for kalem in plan.get("kalemler", []):
        for d in kalem["dosyalar"]:
            s = sinif_bul(d["yol"], b.harita)
            if s:
                ust_siniflar.add(s["ust_sinif"])
            ust_siniflar.add(d["yol"].split("/")[0])

    adimlar: list[dict] = []
    env, tmp = _izole_tmp(k)

    def kos(ad: str, komut: str, kosul: bool = True) -> None:
        if not kosul:
            adimlar.append({"ad": ad, "cikis": None, "not": "ATLANDI — koşul sağlanmadı"})
            return
        parcalar = _komutu_coz(komut)
        betik = _betik_yolu(parcalar)
        if betik is not None and not (k.kok / betik).exists():
            adimlar.append({"ad": ad, "cikis": None,
                            "not": f"ÖLÇÜLEMEDİ — {betik} yok ('temiz' DEĞİL)"})
            print(f"[ ? ] {ad}: ÖLÇÜLEMEDİ ({betik} yok)")
            return
        try:
            r = _run(parcalar, k.kok, env=env, timeout=OLCUM_ZAMAN_ASIMI)
        except subprocess.TimeoutExpired:
            adimlar.append({"ad": ad, "cikis": None,
                            "not": f"ÖLÇÜLEMEDİ — {OLCUM_ZAMAN_ASIMI} sn zaman aşımı"})
            print(f"[ ? ] {ad}: ÖLÇÜLEMEDİ ({OLCUM_ZAMAN_ASIMI} sn zaman aşımı)")
            return
        adimlar.append({"ad": ad, "cikis": r.returncode,
                        "cikti": ((r.stdout or "") + (r.stderr or ""))[-4000:]})
        print(f"[{'OK ' if r.returncode == 0 else 'FAIL'}] {ad} (rc={r.returncode})")

    try:
        kos("install --dry-run", "python scripts/install.py --dry-run")
        kos("doctor", "python scripts/doctor.py")
        kos("doctor --skills", "python scripts/doctor.py --skills",
            kosul=any(u.startswith("skill") for u in ust_siniflar))
        kos("sap-code-review takımı",
            "python -m unittest discover -s skills-sap/sap-code-review/tests "
            "-t skills-sap/sap-code-review/tests",
            kosul="validator-ailesi" in ust_siniflar)
        kos("foundation test_static",
            "python skills-sap/sap-adt-foundation/tests/test_static.py",
            kosul="skills-sap" in ust_siniflar)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # 7 — asgari güvence raporu (ENGELLEMEZ)
    guvence = []
    for yol in ASGARI_GUVENCE_YOLLARI:
        y_sha = b.k.blob_sha(b.yeni_ref, yol)
        if y_sha is None:
            continue
        # disk_sha ölçemezse `Dur` fırlatır; yakalanmazsa `butunluk.json` HİÇ yazılmaz ve kapanış
        # önceki koşumun bayat dosyasını okur (bug gate 2026-09-19 #4) ⇒ satır ÖLÇÜLEMEDİ olur.
        try:
            l_sha = b.k.disk_sha(yol)
        except Dur as e:
            guvence.append(f"WARN asgari güvence: {yol} ÖLÇÜLEMEDİ ({e})")
            continue
        if l_sha is None:
            guvence.append(f"WARN asgari güvence: {yol} YERELDE YOK (yeni sürümde var)")
        elif l_sha != y_sha:
            guvence.append(f"WARN asgari güvence: {yol} yerelde template'ten FARKLI")
    if not guvence:
        guvence.append("asgari güvence: bakılan yolların hiçbirinde sapma yok "
                       f"({len(ASGARI_GUVENCE_YOLLARI)} yol bakıldı)")
    for g in guvence:
        print(g)

    fail = [a for a in adimlar if a.get("cikis") not in (0, None)]
    olculemedi = [a for a in adimlar if a.get("cikis") is None]
    _yaz_json(k.durum_dizini / "butunluk.json", {
        "zaman": _simdi(), "plan": _plan_muhru(plan), "adimlar": adimlar,
        "asgari_guvence": guvence,
        "kapsam_disi": "B1–B4 kontrolleri (memory indeksi, skill referansları, ters yön "
                       "validator, markdown link) BU TURDA YOK — iş paketi P8. Koşulamayan "
                       "adımlar 'ÖLÇÜLEMEDİ' yazılır; ölçülemedi ≠ temiz.",
    })
    print(f"Bütünlük: {len(adimlar) - len(fail) - len(olculemedi)} geçti · {len(fail)} FAIL · "
          f"{len(olculemedi)} ÖLÇÜLEMEDİ")
    return 1 if fail else 0


# =====================================================================================================
# GERİ AL
# =====================================================================================================
def geri_donus_etiketi(k: Klon) -> str:
    h = _oku(k.durum_dizini / "hazirla.json", None)
    if not h or not k.var_mi(h["etiket"]):
        raise Dur("geri dönüş etiketi yok — `guncelle.py hazirla` çalışmamış (§7 adım 3).")
    return h["etiket"]


def komut_geri_al(b: Baglam, args) -> int:
    k = b.k
    etiket = geri_donus_etiketi(k)
    plan = plan_oku(k)
    yeni_ref = plan.get("yeni_etiket") or b.yeni_ref
    if args.hepsi:
        yollar = []
        for kalem in plan["kalemler"]:
            for d in kalem["dosyalar"]:
                yollar.append(d["yol"])
                if d.get("yeni_yol"):
                    yollar.append(d["yeni_yol"])
    elif args.yol:
        yollar = [args.yol.replace("\\", "/")]
    else:
        print("DUR: `geri-al` bir yol ya da `--hepsi` ister.", file=sys.stderr)
        return 2

    hata = 0
    for yol in sorted(set(yollar)):
        if k.blob_sha(etiket, yol):
            r = k.git("checkout", etiket, "--", yol)
            if r.returncode != 0:
                print(f"FAIL geri-al {yol}: {r.stderr.strip()}", file=sys.stderr)
                hata = 1
                continue
            print(f"GERİ ALINDI: {yol}")
        elif (k.kok / yol).is_file():
            # Etikette blob yok ⇒ ya motorun yazdığı dosya (yeni ref'te var, kurtarılabilir) ya da
            # kullanıcının İZLENMEYEN dosyası (V7: hiçbir yerde yedeği yok — ölçüldü 2026-09-23).
            korunan = _sil_korunarak(k, yol, kurtarilabilir_ref=yeni_ref)
            print(f"GERİ ALINDI (silindi): {yol} — tabanda yoktu")
            if korunan:
                print(f"Yedeksiz yerel içerik saklandı: {korunan}")
        durum_kaydet(k, yol, durum="geri_alindi")
    return hata


# =====================================================================================================
# KAPANIŞ
# =====================================================================================================
def _tek_satir(metin: str | None) -> str:
    """Alt-süreç stderr'ini tek satıra indirir: `EKSİK:` satırı ve RAPOR.md madde işareti
    çok satırlı bir metinle bozulmasın (git'in `.gitignore` hint bloğu 5 satırdır)."""
    return " ".join((metin or "").split())


def _atlandi_nedeni(kalem: dict, durum: dict, uygulanan_kalemler: set,
                    secili: set | None = None) -> str | None:
    """Z58 (v0.5.4): `uygulandi` mühürlenmeyen kalemin (Z61 c: kendi dosyalarının hepsi `dogrulandi`
    değil) `uygulanan.json` mührüne NEDEN.

    Kapanış anında güvenilir biçimde bilinir: `durum` bu turun `durum.json`'udur (`komut_kapanis`
    okur, hiçbir yer silmez — `_plan_muhru`), dosya→kalem eşlemesi planın `kalem["dosyalar"]`ıdır
    (`komut_plan` adım 3: her yol TEK kaleme, onu beyan eden en son kaleme bağlanır). Kalemin
    beyan ettiği ama sonraki bir kaleme DEVREDİLEN yollar planın `kalem["devredilen"]`ındadır
    ({yol: sahip kalem}); `uygulanan_kalemler` bu turda en az bir dosyası İNEN seçili kalemlerdir
    (Z61 c: `_kapanis_git`in `inen_kalemler`i — onları mühür yazmadan ÖNCE hesaplar; kendi
    dosyalarının hepsi inmeyen sahip `atlandi` mühürlenir ama burada yine sayılır).
    Devredilen bir yol ancak sahibinde bu turda bir dosya indiyse VE yolun kendisi `dogrulandi`
    ise İNMİŞ sayılır (sahibin başka dosyası inip bu yol ertelenmiş olabilir).
      · `ertelendi` — kalemin dosyalarından ya da İNMEYEN devredilen yollarından en az birinde
                      `isaretle --karar ertelendi`; YA DA (v0.5.5 bug gate P3) inmeyen bir devredilen
                      yolun sahibi bu turda SEÇİLMEDİ (`secili` verilmişse): o yolun işi sahipte hâlâ
                      bekliyor, sahip mühürlenmez ve plana yine girer ⇒ devreden kalem de yeniden
                      önerilmeli. Eskiden `kabul` deniyordu: Z62'ye göre `kabul` KAPALIDIR ⇒ kullanıcı
                      `--kabul` demeden kalem kalıcı kapanıyordu (ölçüldü, `--cikar <sahip>`);
      · `is-yok`    — kalemin planda dosyası yok VE devredilen her yolu bu turda indi (ya da hiç
                      devredilen yolu yok: işlemsiz vaka) ⇒ yapılacak iş kalmadı;
      · `kabul`     — inmeyen iş var, ertelenmemiş, sahibi seçiliydi: `kapanis --kabul` (kod 3)
                      ile buraya gelinir (dosyalar `bekliyor`/`uygulandi` kaldı). `secili` verilmezse
                      (birim çağrısı) sahip-seçilmedi dalı ölçülemez ⇒ eski davranış (`kabul`);
      · `None`      — plan `devredilen` alanını taşımıyor (v0.5.4 öncesi motorun planı) ve kalem
                      dosyasız: iş-yok mu devir mi ÖLÇÜLEMEZ ⇒ "bilinmiyor" (fail-closed, uyarı üretir).
    ⛔ `is-yok` yalnız yapılacak işi KALMAYAN kalemdir: "ertelendi değilse iş yoktu" DENMEZ —
    `--kabul` ile açık FAIL'le kapanan kalem ya da dosyası sonraki kalemde ertelenen kalem `is-yok`
    sayılsaydı `komut_sec`in önkoşul UYARI'sı sessizce kaybolurdu (bug gate 2026-09-22, ölçüldü).
    """
    devredilen = kalem.get("devredilen")
    if not isinstance(devredilen, dict):
        if not kalem["dosyalar"]:
            return None
        devredilen = {}
    inmeyen = [yol for yol, sahip in devredilen.items()
               if not (sahip in uygulanan_kalemler
                       and durum["dosyalar"].get(yol, {}).get("durum") == "dogrulandi")]
    if not kalem["dosyalar"] and not inmeyen:
        return "is-yok"
    if any(durum["dosyalar"].get(y, {}).get("karar") == "ertelendi"
           for y in [d["yol"] for d in kalem["dosyalar"]] + inmeyen):
        return "ertelendi"
    if secili is not None and any(devredilen[y] not in secili for y in inmeyen):
        return "ertelendi"
    return "kabul"


def _kapanis_git(b: Baglam, plan: dict, durum: dict, secili: set,
                 eksikler: list, kod: int) -> int:
    """Kapanışın git tarafı: stage → commit → ANCAK SONRA `uygulanan.json` mührü.

    ⛔ Bu fonksiyon `komut_kapanis`in İÇİNDEN, RAPOR.md ÜRETİLMEDEN ÖNCE çağrılır. Eskiden
    rapordan SONRA koşuyordu ve başarısızlığı yalnız `UYARI:` basıyordu ⇒ `kapanis` 0 dönüyor,
    RAPOR.md "KAPANMADI" demiyor, kullanıcı "temiz kapandı" sanıyordu. Buradaki her başarısızlık
    artık `eksikler`e girer ve çıkış kodunu 1'e düşürür — **ölçülemedi ≠ temiz**.

    ⛔ MÜHÜR EN SONA: `uygulanan.json` YÜK TAŞIR (ölçüldü, varsayılmadı):
      · `komut_plan`: mühürlü kalem bir daha PLANA GİRMEZ (Z62 istisnası: `atlandi` +
        `neden: ertelendi` yeniden önerilir; mührün `zaman`ı, `_kayit_tuketildi_mi` ile hangi
        `durum.json` ertelendi kaydının bu kapanışta tüketildiğini de belirler);
      · `Baglam.taban_ref`: dosya-başı taban o yayın etiketine çekilir ⇒ sonraki 3-yollu
        karşılaştırma yanlış tabandan yapılır.
    Commit atılmadan mühürlemek "uygulandı" yalanını KALICILAŞTIRIR. Bu yüzden mühür yalnız
    (a) commit atıldıysa ya da (b) ÖLÇÜLEREK commit'lenecek bir şey olmadığı görüldüyse basılır.
    """
    k = b.k
    # ⛔ `git add -A` kullanıcının İZLENMEYEN dosyalarını da commit'liyordu (§1/§2a kapsam
    # ihlali: motor yalnız template yollarına dokunur). Yan etki ölçüldü:
    # `kullanici_dosya_sayisi()` `--others --exclude-standard` okuduğu için ilk kapanıştan
    # sonra VKD sayacı 0'a düşüyordu — sayaç bir daha hiç saymıyordu.
    # Kapsam artık PLANDAKİ yollar (+ yeniden adlandırma hedefleri).
    add_yollari = sorted({y for kalem in plan["kalemler"] if kalem["id"] in secili
                          for d in kalem["dosyalar"]
                          for y in (d["yol"], d.get("yeni_yol")) if y})
    # ⛔ SÜZGEÇ ÖLÇÜTÜ = `git add`in eşleştirdiği küme: ÇALIŞMA AĞACI ∪ INDEX. HEAD DEĞİL.
    # Eski ölçüt `blob_sha("HEAD", y)` idi ve sessiz veri kaybı üretiyordu: `Klon.sil()` yolu
    # `git rm -q --cached` ile index'ten düşürür, dosya diskte de yoktur, ama HEAD'de DURUR ⇒
    # yol süzgeçten geçer, `git add` `fatal: pathspec ... did not match any files` der ve o
    # çağrıda HİÇBİR yolu stage etmez (kısmi başarı yoktur) ⇒ o koşumun tüm birleştirme sonucu
    # commit'e GİRMEZ. Ölçüldü (`--karar birlesik`): `core/00-temel.md` diskte v3, HEAD'de v1,
    # `kapanis` yine rc=0. Silmeleri normalde `Klon.sil()` stage'ler; onun `git rm --cached`'i
    # başarısız olsa bile yol index'te kaldığı için `izlenen` kümesine girer ve `git add` silmeyi
    # stage'ler (rc taraması 2026-09-18 ölçtü: `git add -- <silinmiş izlenen yol>` → `D`, rc=0).
    izlenen = k.izlenen_yollar(add_yollari)
    # ⛔ M-6 (kullanıcı kararı 2026-09-18, TASARIM §6): `--karar yerel` = "bu dosyaya DOKUNMA". Dosya
    # daha önce İZLENMİYORSA (V7: kullanıcının kendi dosyası template'in yeni yolunda) kapanış onu
    # git'e ekleyip commit'lemez — eskiden ekliyordu: içerik korunuyor ama dosya sessizce klonun
    # geçmişine giriyordu. İzlenen bir dosyada `yerel` zaten "değişiklik yok" demektir.
    # ⛔ Korunan küme (bug gate 2026-09-19, iki tur, ölçüldü):
    #   · `karar == yerel` → eski VE yeni yol. Yeniden adlandırmalı V7'de kayıt `hedef_yol` olarak
    #     ESKİ yolu tutar, kullanıcının dosyası ise YENİ yoldadır ⇒ yalnız `hedef_yol`a bakmak yanlış
    #     yolu koruyordu.
    #   · V7 (kullanıcının İZLENMEYEN dosyası template yolunda) + motor YAZMADI (`ertelendi`, karar
    #     verilmemiş + `--kabul`) → aynı iki yol.
    # ⚠ "Motor yazmadıysa HER izlenmeyen yol korunur" DENMEZ: V4R'de `birlesik` sonra `ertelendi`
    # sırasında yeni yolu motor oluşturmuş, eski yolun silmesi zaten stage'lidir ⇒ yeni yolu dışarıda
    # bırakmak HEAD'de iki yolu da yok eden YARIM taşıma üretiyordu (ikinci tur ölçümü).
    # ⚠ Aynı sınıf `yerel` kararında da vardı (üçüncü tur, ölçüldü: V4R `birlesik` → `yerel`): YENİ yol
    # yalnız taşıma GERÇEKLEŞMEDİYSE (eski yol hâlâ diskte ya da index'te) korunur. Taşıma olduysa yeni
    # yolu motor yazmıştır; onu dışarıda bırakmak yine yarım taşıma olurdu.
    # ⚠ V7'de "eski yol duruyor mu" sinyali YETMEZ (dördüncü tur, ölçüldü): kullanıcı eski yolu önceden
    # kendisi silmişse işaret "taşındı" der ve kullanıcının yeni yoldaki dosyası commit'e girerdi. V7'nin
    # tanımı içeriktir (yeni yoldaki disk ≠ template blob'u) ⇒ ayırt edici sinyal de içerik: motor yeni
    # yola yalnız `yeniden-adlandir` ile YAZAR ve o zaman disk = blob olur. Ölçülemezse KORU (fail-closed).
    def _kullanicinin(yol: str) -> bool:
        try:
            disk = k.disk_sha(yol)
        except Dur:
            return True
        return disk is not None and disk != k.blob_sha(b.yeni_ref, yol)

    def _korunan_yollar(d: dict) -> set:
        kayit = durum["dosyalar"].get(d["yol"], {})
        motor_yazdi = kayit.get("durum") in ("dogrulandi", "uygulandi")
        v7 = d.get("vaka") == "V7"
        if kayit.get("karar") != "yerel" and not (v7 and not motor_yazdi):
            return set()
        yollar = {d["yol"]}
        yeni = d.get("yeni_yol")
        if yeni:
            eski_duruyor = (k.kok / d["yol"]).exists() or d["yol"] in izlenen
            if (_kullanicinin(yeni) if v7 else eski_duruyor):
                yollar.add(yeni)
        return yollar
    yerel_izlenmeyen = {y for kalem in plan["kalemler"] if kalem["id"] in secili
                        for d in kalem["dosyalar"] for y in _korunan_yollar(d)} - izlenen
    plan_yollari = list(add_yollari)   # süzgeçten ÖNCEKİ küme — hata dalında index'i bununla geri al
    add_yollari = [y for y in add_yollari
                   if ((k.kok / y).exists() or y in izlenen) and y not in yerel_izlenmeyen]
    if add_yollari:
        r_add = k.git("add", "--", *add_yollari)
        if r_add.returncode != 0:
            # Index kapanıştan önceki yarım hâlinde bırakılmaz: `Klon.sil()` silmeleri ÖNCEDEN
            # stage'lemişti. Kullanıcının sonraki elle `git commit`i bu yarım durumu commit'lemesin
            # diye YALNIZ plandaki yollar HEAD'e geri alınır (çalışma ağacına dokunulmaz; kapanış
            # yeniden koşunca silmeleri `izlenen_yollar` üzerinden yeniden stage'ler).
            # ⚠ SÜZGEÇLİ liste YETMEZ: `Klon.sil()`in stage'lediği silme yolu ne diskte ne
            # index'tedir ⇒ süzgeçten düşer; geri alma onu kaçırırdı. `git reset -- <yol>` HEAD'de
            # ve index'te olmayan yolda da rc=0 döner (ölçüldü 2026-09-18) ⇒ tüm plan kümesi verilir.
            r_reset = k.git("reset", "-q", "--", *plan_yollari)
            geri = ("plandaki yolların index'i HEAD'e geri alındı, çalışma ağacı değişmedi"
                    if r_reset.returncode == 0 else
                    f"index geri ALINAMADI (elle: git reset -- <yollar>): {_tek_satir(r_reset.stderr)}")
            eksikler.append(f"kapanış `git add` başarısız — plandaki değişiklikler commit'e "
                            f"GİRMEDİ: {_tek_satir(r_add.stderr)} · {geri}")
            return 1

    # ⛔ ÇIKIŞ KODU SİNYALDİR, ÖLÇÜM DEĞİL. `git commit` rc=1 "commit edilecek bir şey yok"
    # anlamına geldiği KADAR "hook reddetti / index kilitli / config bozuk" anlamına da gelir.
    # rc=1'i koşulsuz tolere etmek, kapatılan sessiz-geçiş sınıfının aynısını yeniden açardı ⇒
    # karar DURUMDAN okunur: `git diff --cached --quiet` → 0 = stage'de fark YOK · 1 = fark VAR
    # · başka = ÖLÇÜLEMEDİ ('temiz' DEĞİL).
    r_stage = k.git("diff", "--cached", "--quiet")
    if r_stage.returncode not in (0, 1):
        eksikler.append(f"kapanış: stage durumu ÖLÇÜLEMEDİ ('temiz' DEĞİL) — "
                        f"`git diff --cached --quiet` rc={r_stage.returncode}: "
                        f"{_tek_satir(r_stage.stderr)}")
        return 1
    if r_stage.returncode == 1:
        # ⛔ PATHSPEC'SİZ COMMIT SINIFI (karar B — "DUR + uyar", 2026-09-20).
        # Aşağıdaki `git commit` pathspec ALMAZ: index'te NE VARSA commit'ler. Kullanıcının
        # kapanıştan ÖNCE kendi stage'lediği iş, ARACIN mesajıyla ve `--no-verify` ile
        # (yani pre-commit gate'i KOŞMADAN) commit'e girerdi — PRE-EXISTING sınıf.
        # ⛔ Seçenek A (commit'e pathspec vermek) REDDEDİLDİ: aracın kendi dosya listesi
        # eksik kalırsa kendi değişikliğini SESSİZCE commit'lemez ve kapanış "atildı" der ⇒
        # YENİ bir sessiz kayıp sınıfı doğardı. Bu yüzden araç DURUR ve kullanıcıya söyler.
        r_isim = k.git("diff", "--cached", "--name-only", "-z")
        if r_isim.returncode != 0:
            eksikler.append("kapanış: index kapsamı ÖLÇÜLEMEDİ ('yalnız aracın dosyaları' DEĞİL) — "
                            f"`git diff --cached --name-only` rc={r_isim.returncode}: "
                            f"{_tek_satir(r_isim.stderr)}")
            return 1
        yabanci = sorted({y for y in (r_isim.stdout or "").split("\0") if y} - set(plan_yollari))
        if yabanci:
            ornek = ", ".join(yabanci[:5]) + (" …" if len(yabanci) > 5 else "")
            eksikler.append(
                f"kapanış commit'i ATILMADI — index'te aracın kendi dosyaları DIŞINDA "
                f"{len(yabanci)} yol var: {ornek}. Bu commit `--no-verify` ile ve aracın "
                f"mesajıyla atılırdı ⇒ senin işin araç commit'ine karışır ve pre-commit gate'i "
                f"o dosyalar için KOŞMAZDI. Çözüm: `git restore --staged <yol>` ile kendi "
                f"dosyalarını index'ten çıkar, sonra kapanışı yeniden koş. "
                f"(Araç senin dosyalarına DOKUNMADI; planın yolları index'te hazır duruyor.)")
            return 1
        mesaj = (f"guncelle: {plan['yeni_etiket']} kalemler "
                 + ", ".join(sorted(secili)))
        r = k.git("commit", "--no-verify", "-q", "-m", mesaj, kimlik=True)
        if r.returncode != 0:
            eksikler.append(f"kapanış commit'i atılamadı (stage'de fark VARDI — yani 'commit "
                            f"edilecek bir şey yok' DEĞİL): {_tek_satir(r.stderr)}")
            return 1

    u = b.uygulanan
    u.setdefault("dosyalar", {})
    u.setdefault("kalemler", {})
    # ⛔ İKİ GEÇİŞ (Z58 bug gate): atlandi kalemin `is-yok` nedeni, devrettiği yolların SAHİBİNİN bu
    # turdaki mührüne bağlıdır (`_atlandi_nedeni`). Sahip plan sırasında SONRA gelir (en son beyan
    # eden kalem) ⇒ önce tüm seçili kalemlerin uygulandi/atlandi hâli hesaplanır, sonra nedenler.
    # ⛔ Z61 (c) (kullanıcı kararı 2026-09-23, seçenek 1): kalem ancak KENDİ dosyalarının HEPSİ
    # `dogrulandi` ise `uygulandi` mühürlenir. Eskiden tek bir `dogrulandi` dosya yetiyordu: kalemin
    # kendi dosyası `ertelendi` (ya da `--kabul` altında `bekliyor`/`uygulandi`) kalsa bile kalem
    # `uygulandi` mühürleniyor ⇒ Z62 yeniden önerisi hiç devreye girmiyor, o dosyanın içeriği bir
    # daha önerilmiyordu (ölçüldü, `Z61KismiKalemTest`). Artık böyle kalem `atlandi` olur, nedeni
    # `_atlandi_nedeni` verir (kendi dosyası ertelendi ⇒ `ertelendi` → Z62 yeniden önerir; yalnız
    # `--kabul` altında kalan açık FAIL ⇒ `kabul`).
    # İKİ KÜME bilinçli: `inen_kalemler` (en az bir dosyası indi) `_atlandi_nedeni`nin devredilen-yol
    # ölçütüdür — orada soru "bu YOL indi mi"dir (yolun kendi `dogrulandi`si ayrıca aranır), sahibin
    # tamamı değil; sahibin başka dosyası ertelendi diye inmiş bir yolu "inmedi" saymak devreden
    # kalemi `is-yok` yerine `kabul` ile kapatırdı. Dosya tabanı (`u["dosyalar"]`) da dosya başına
    # yazılır: inen dosyanın tabanı eski kalsaydı kalem yeniden önerildiğinde o dosya yeniden
    # YARGI vakası çıkarırdı (taban v3 ⇒ işlemsiz; ölçüldü).
    uygulanan_kalemler: set[str] = set()
    inen_kalemler: set[str] = set()
    for kalem in plan["kalemler"]:
        if kalem["id"] not in secili:
            continue
        hepsi = bool(kalem["dosyalar"])
        for d in kalem["dosyalar"]:
            kayit = durum["dosyalar"].get(d["yol"], {})
            if kayit.get("durum") == "dogrulandi":
                u["dosyalar"][kayit.get("hedef_yol", d["yol"])] = plan["yeni_etiket"]
                inen_kalemler.add(kalem["id"])
            else:
                hepsi = False
        if hepsi:
            uygulanan_kalemler.add(kalem["id"])
    for kalem in plan["kalemler"]:
        if kalem["id"] not in secili:
            continue
        uygulandi = kalem["id"] in uygulanan_kalemler
        muhur = {"etiket": plan["yeni_etiket"],
                 "durum": "uygulandi" if uygulandi else "atlandi", "zaman": _simdi()}
        if not uygulandi:
            muhur["neden"] = _atlandi_nedeni(kalem, durum, inen_kalemler, secili)
        u["kalemler"][kalem["id"]] = muhur
    _yaz_json(k.durum_dizini / "uygulanan.json", u)
    return kod


def komut_kapanis(b: Baglam, args) -> int:
    k, plan = b.k, plan_oku(b.k)
    durum = durum_oku(k)
    secili = secim_oku(k, plan)
    satirlar, eksikler = [], []
    durum_dustu = False

    for kalem in plan["kalemler"]:
        if kalem["id"] not in secili:
            continue
        for d in kalem["dosyalar"]:
            yol = d["yol"]
            kayit = durum["dosyalar"].get(yol, {})
            dv = kayit.get("durum", "bekliyor")
            karar = kayit.get("karar", "—")
            # §6: ajanın "yaptım" demesi durum değiştirmez — DİSKTEN yeniden doğrula
            # ⛔ Z61 (a): ölçüm tutmazsa KAYDIN KENDİSİ düşürülür, yalnız yerel `dv` değil. Aynı
            # `durum` sözlüğünü `_kapanis_git` (mühür + `uygulanan.json` dosya tabanı) ve
            # `_atlandi_nedeni` (devredilen yol "indi" mi) okur; kayıt `dogrulandi` kalınca
            # `--kabul`de kalem `uygulandi`, devreden kalem `is-yok` mühürleniyor, içerik diskte
            # yokken kalem bir daha önerilmiyordu (ölçüldü, `Z61KapanisDiskTutmazTest`).
            if dv == "dogrulandi":
                hedef = kayit.get("hedef_yol", yol)
                if k.disk_sha(hedef) != kayit.get("beklenen_sha"):
                    dv = "uygulandi"
                    kayit["not_"] = "kapanışta diskten doğrulanamadı"
                    eksikler.append(f"{yol}: durum.json 'dogrulandi' diyor ama disk farklı — kayıt geri 'uygulandi'ya alındı; düzelttikten sonra `isaretle`/`uygula` ile yeniden işaretle")
                else:
                    tam = k.kok / hedef
                    if tam.is_file():
                        metin = tam.read_text(encoding="utf-8", errors="replace")
                        y_sha_ref = k.blob_sha(plan["yeni_etiket"], hedef)
                        ref_metin = (k.blob(y_sha_ref).decode("utf-8", "replace")
                                     if y_sha_ref else None)
                        if cakisma_isaretleri(metin, ref_metin):
                            dv = "uygulandi"
                            kayit["not_"] = "kapanışta çakışma işareti bulundu"
                            eksikler.append(f"{yol}: çakışma işareti duruyor — kayıt geri 'uygulandi'ya alındı; düzelttikten sonra `isaretle`/`uygula` ile yeniden işaretle")
                if dv != "dogrulandi":
                    kayit["durum"] = dv
                    durum_dustu = True
            if dv in ("bekliyor", "uygulandi"):
                eksikler.append(f"{yol}: durum '{dv}' (dogrulandi ya da gerekçeli atlandi gerekir)")
                satirlar.append(f"[FAIL] {kalem['id']} {yol} {d['vaka']} {karar}")
            elif dv == "atlandi":
                satirlar.append(f"[WARN] {kalem['id']} {yol} {d['vaka']} atlandi"
                                f" ({kayit.get('gerekce', '—')})")
            else:
                satirlar.append(f"[PASS] {kalem['id']} {yol} {d['vaka']} {karar}")
    if durum_dustu:
        # Kalıcı: `durum` tablosu ve sonraki `uygula` da ölçülen hâli görsün (yargı vakası
        # `uygulandi` kaydında yeniden `bekliyor` açılır; otomatik vaka yeniden yazılır).
        durum_yaz(k, durum)

    # özel adımlar
    beklenen_ozel = sorted({a for kalem in plan["kalemler"] if kalem["id"] in secili
                            for a in kalem["ozel_adimlar"]})
    kosan = durum.get("ozel_adimlar", {})
    for ad in beklenen_ozel:
        if kosan.get(ad, {}).get("durum") not in ("kostu", "manuel"):
            eksikler.append(f"özel adım koşmadı: {ad} (§7 adım 9)")

    # ölçüm + bütünlük
    kirmizi = yeni_kirmizilar(k)
    for t in kirmizi:
        eksikler.append(f"sonra-ölçümde YENİ kırmızı: {t}")
    butunluk = _oku(k.durum_dizini / "butunluk.json", None)
    # ⛔ K2 (2026-09-20): eskiden BURADA yalnız "dosya var mı" soruluyordu. `durum_dizini`
    # döngüler arası temizlenmediği için ÖNCEKİ turdan kalan `butunluk.json` "bütünlük turu
    # koştu" sayılıyordu = SAHTE YEŞİL, üstelik NORMAL akışla tetikleniyordu (`%guncelle`'yi
    # ikinci kez koşmak). Artık damga bu turun plan kimliğine uymak ZORUNDA.
    bayat = _muhur_sorunu("butunluk.json", butunluk, plan)
    if butunluk is None:
        eksikler.append("bütünlük turu koşmadı (§7 adım 12)")
    elif bayat:
        eksikler.append(f"bütünlük turu BU TUR İÇİN ÖLÇÜLMEDİ — {bayat}. "
                        f"`butunluk` komutunu bu tur için yeniden koş (ölçülmedi ≠ temiz).")
    elif any(a.get("cikis") not in (0, None) for a in butunluk["adimlar"]):
        eksikler.append("bütünlük turunda FAIL var")

    d_bayat = _muhur_sorunu("durum.json", durum, plan)
    if d_bayat:
        eksikler.append(f"dosya yargıları BU TURA ait DEĞİL — {d_bayat}. "
                        f"`hazirla` bu turun damgasını basar; kapanışı ondan sonra koş.")

    kabul = bool(args.kabul)
    kod = 0 if not eksikler else (3 if kabul else 1)

    # ⚠ SIRA: git tarafı RAPORDAN ÖNCE koşar. Aksi hâlde `git add`/commit başarısızlığı
    # `eksikler`e girse bile RAPOR.md zaten yazılmış olur ve "KAPANMADI" bölümüne giremez.
    # `--kabul` bu başarısızlıkları ÖRTMEZ: kullanıcı açık FAIL'leri kabul eder, motorun
    # kendi alt-süreç çöküşünü değil ⇒ `_kapanis_git` başarısızlıkta koşulsuz 1 döndürür.
    if kod in (0, 3):
        kod = _kapanis_git(b, plan, durum, secili, eksikler, kod)

    rapor = [f"# Güncelleme raporu — {plan['yeni_etiket']}", "",
             f"Üretim: {_simdi()} · taban `{plan['taban_commit'][:10]}` · "
             f"seçili kalem: {len(secili)}", ""]
    rapor += satirlar or ["(seçili kalemde dosya yok)"]
    rapor += ["", "## Sayaçlar",
              ", ".join(f"{a}={c}" for a, c in plan["sayaclar"].items()),
              "", "## Yeni kırmızı testler",
              ("\n".join(f"- {t}" for t in kirmizi) if kirmizi else "yok")]
    # Z26 — ikame edilen tur KALICI raporda da görünmeli: "yok", "yerelde 0 test koştu" ile
    # karışmasın (ölçülemeyen/koşulmayan şey sessizce 'temiz' okunmaz).
    for asama in ("once", "sonra"):
        o = _oku(k.durum_dizini / f"olcum-{asama}.json", None) or {}
        if o.get("kaynak") == "ci":
            rapor += [f"- {asama}-ölçüm: yerelde test KOŞULMADI — {o.get('etiket')} CI hükmüyle "
                      f"ikame edildi. {o.get('gerekce', '')}"]
    rapor += ["", "## Bütünlük turu"]
    if butunluk:
        rapor += [f"- {a['ad']}: " + ("ÖLÇÜLEMEDİ" if a.get("cikis") is None
                                      else ("PASS" if a["cikis"] == 0 else "FAIL"))
                  for a in butunluk["adimlar"]]
        rapor += ["", "## Asgari güvence"] + [f"- {g}" for g in butunluk["asgari_guvence"]]
    else:
        rapor += ["- ÖLÇÜLEMEDİ (bütünlük turu koşmadı) — 'temiz' DEĞİL"]

    dv = etkin_davranis(None) if plan["yeniden_baslat"] == "gerekmez" else None
    if plan["yeniden_baslat"] == "gerekmez":
        rapor += ["", f"## aXet'i kapat-aç\ngerekmez ({dv['aciklama']})"]
    else:
        sebep = ", ".join(sorted({d["sinif"] or "sınıfsız" for kalem in plan["kalemler"]
                                  for d in kalem["dosyalar"]
                                  if d["etkin"] in ("yeni-oturum", "install-sonra-yeni-oturum")}))
        rapor += ["", f"## aXet'i kapat-aç\ngerekli — {plan['yeniden_baslat']} "
                      f"(neden: sınıf {sebep})"]

    if eksikler:
        rapor += ["", "## KAPANMADI — eksikler"] + [f"- {e}" for e in eksikler]
    # M-1: koşul `kod`dur, `kabul` bayrağı DEĞİL. `--kabul` + git hatasında `kod` 1'e düşer; eskiden
    # rapor hem "KAPANMADI" hem "onaylı açık FAIL ile kapandı" diyordu.
    if kod == 3:
        rapor += ["", f"## Kullanıcı onaylı açık FAIL ile kapandı\n{args.kabul}"]
    rapor += ["", "KAPSAM — bakılanlar: plandaki seçili dosyaların disk durumu ve çakışma "
                  "işareti · özel adımların koşumu · önce/sonra ölçümünün YENİ kırmızıları · "
                  "bütünlük turu çıkışları.",
              "KAPSAM — bakılmayanlar: değişikliğin ANLAMCA doğru olduğu (temiz birleşme yanlış "
              "olabilir) · aXet'in yeni bağlamı fiilen yüklediği · haritada test komutu olmayan "
              "sınıflar · kullanıcının kendi dosyaları (kapsam dışı, VKD) · canlı SAP."]
    (k.durum_dizini / "RAPOR.md").write_text("\n".join(rapor) + "\n", encoding="utf-8")

    for e in eksikler:
        print("EKSİK: " + e, file=sys.stderr)

    print((k.durum_dizini / "RAPOR.md").read_text(encoding="utf-8"))
    return kod


# =====================================================================================================
# DURUM TABLOSU
# =====================================================================================================
def komut_durum(b: Baglam, args) -> int:
    k = b.k
    plan = _oku(k.durum_dizini / "plan.json", None)
    durum = durum_oku(k)
    if plan is None:
        print("plan.json yok.")
        return 0
    print(f"{'KALEM':10s} {'VAKA':10s} {'DURUM':12s} {'KARAR':16s} YOL")
    for kalem in plan["kalemler"]:
        for d in kalem["dosyalar"]:
            s = durum["dosyalar"].get(d["yol"], {})
            print(f"{kalem['id']:10s} {d['vaka']:10s} {s.get('durum', 'bekliyor'):12s} "
                  f"{str(s.get('karar', '—')):16s} {d['yol']}")
    ozel = durum.get("ozel_adimlar", {})
    if ozel:
        print("\nÖzel adımlar: " + ", ".join(f"{a}={v.get('durum')}" for a, v in ozel.items()))
    return 0


# =====================================================================================================
# KART
# =====================================================================================================
def komut_kart(b: Baglam, args) -> int:
    """§5: ajan kartı YENİ sürümden okur (yerel kopya bozulmuş/eski olabilir)."""
    r = b.k.git("show", f"origin/main:guncelle/kartlar/{args.kod}.md")
    if r.returncode != 0:
        print(f"DUR: kart yok: guncelle/kartlar/{args.kod}.md (origin/main)", file=sys.stderr)
        return 2
    print(r.stdout)
    return 0


# =====================================================================================================
# ÖN KONTROL + HAZIRLA
# =====================================================================================================
KLON_KIMLIK_DOSYALARI = ["core/00-temel.md", "scripts/install.py"]
KLON_KIMLIK_DIZINLERI = ["skills-sap"]


def _kaynak_anahtari(k: str) -> str:
    """`kur.ps1` Kaynak-Anahtari ile aynı normalize: sondaki ayraç, `.git`, harf farkı."""
    s = (k or "").strip().rstrip("/\\")
    if s.lower().endswith(".git"):
        s = s[:-4]
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", s) and not re.match(r"^[^@/\\]+@[^:/\\]+:", s):
        try:
            s = str(Path(s).resolve()).rstrip("/\\")
        except (OSError, ValueError):
            pass
    return s.lower()


def komut_onkontrol(b: Baglam | None, args, klon: Klon) -> int:
    sorunlar, bilgi = [], []
    # 1 — klon kimliği (kur.ps1 Template-Eksikleri ile AYNI liste)
    for yol in KLON_KIMLIK_DOSYALARI:
        if not (klon.kok / yol).is_file():
            sorunlar.append(f"klon kimliği: {yol} yok")
    core = klon.kok / "core" / "00-temel.md"
    if core.is_file():
        if not any(s.startswith("CORE-ID: AXET-CORE-")
                   for s in core.read_text(encoding="utf-8", errors="replace").splitlines()):
            sorunlar.append("klon kimliği: core/00-temel.md içinde 'CORE-ID: AXET-CORE-' satırı yok")
    for d in KLON_KIMLIK_DIZINLERI:
        if not (klon.kok / d).is_dir():
            sorunlar.append(f"klon kimliği: {d}/ yok")

    # 2 — origin resmî template adresi mi (K4: fork'tan kod çalıştırılmaz)
    beklenen = os.environ.get("AXET_GUNCELLE_BEKLENEN_ORIGIN") or args.beklenen_origin
    gercek = klon.git("remote", "get-url", "origin").stdout.strip()
    if not gercek:
        sorunlar.append("origin uzağı tanımlı değil")
    elif _kaynak_anahtari(gercek) != _kaynak_anahtari(beklenen):
        sorunlar.append(f"origin resmî template adresi DEĞİL: {gercek} (beklenen: {beklenen}). "
                        "Fork'a çevrilmişse motor oradan çalıştırılmaz (K4).")
    else:
        bilgi.append(f"origin: {gercek}")

    # 3 — dal
    dal = klon.git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    bilgi.append(f"dal: {dal}")
    # 4 — git sürümü
    gs = _run(["git", "--version"], klon.kok)
    if gs.returncode != 0:
        sorunlar.append("git çalıştırılamadı")
    else:
        bilgi.append(gs.stdout.strip())
    # 5 — sığ klon
    sig = klon.git("rev-parse", "--is-shallow-repository")
    if sig.returncode != 0:
        sorunlar.append(f"sığ klon denetimi ÖLÇÜLEMEDİ (git rev-parse rc={sig.returncode}): "
                        f"{' '.join((sig.stderr or '').split())[:200]}")
    elif sig.stdout.strip() == "true":
        sorunlar.append("sığ klon (--depth) — taban commit'leri eksik, 3-yollu karşılaştırma "
                        "yapılamaz. `kur.cmd -Sifirla` ya da tam klon gerekir.")
    # 6 — aXet sürümü
    bilgi.append("aXet.code sürümü: ÖLÇÜLEMEDİ (okuma yöntemi DOĞRULANMADI — TASARIM §14)")
    # 7 — izole TMP repo dışı mı
    tmp = Path(tempfile.gettempdir()).resolve()
    try:
        tmp.relative_to(klon.kok)
        sorunlar.append(f"TMP dizini klonun İÇİNDE ({tmp}) — git testleri yanlış FAIL verir.")
    except ValueError:
        bilgi.append(f"TMP: {tmp} (klon dışı)")

    for s in bilgi:
        print("  " + s)
    for s in sorunlar:
        print("DUR: " + s, file=sys.stderr)
    return 2 if sorunlar else 0


def komut_hazirla(b: Baglam | None, args, klon: Klon) -> int:
    klon.durum_dizini.mkdir(parents=True, exist_ok=True)
    st = klon.git("status", "--porcelain", "--untracked-files=no")
    if st.returncode != 0:
        # Ölçülemeyen durum "temiz" sayılırsa anlık commit atlanır ve geri dönüş etiketi
        # kullanıcının izlenen değişikliğini İÇERMEZ (rc taraması 2026-09-18, ölçüldü).
        print(f"DUR: `git status` başarısız (rc={st.returncode}): {' '.join((st.stderr or '').split())[:300]} "
              f"— yerel durum ölçülemedi, geri dönüş noktası atılmadı.", file=sys.stderr)
        return 2
    kirli = st.stdout.strip()
    if kirli:
        klon.git("add", "-u", kontrol=True)
        r = klon.git("commit", "--no-verify", "-q", "-m",
                     f"guncelle: yerel anlık {datetime.date.today():%Y-%m-%d}", kimlik=True)
        if r.returncode != 0:
            print(f"DUR: yerel anlık commit atılamadı: {r.stderr.strip()}", file=sys.stderr)
            return 2
        print("Yerel anlık commit atıldı (izlenmeyen dosyalara DOKUNULMADI).")
    etiket = f"guncelle-oncesi-{datetime.datetime.now():%Y%m%d-%H%M%S}"
    r = klon.git("tag", etiket)
    if r.returncode != 0:
        print(f"DUR: etiket atılamadı: {r.stderr.strip()}", file=sys.stderr)
        return 2
    _yaz_json(klon.durum_dizini / "hazirla.json",
              {"etiket": etiket, "commit": klon.g("rev-parse", "HEAD"), "zaman": _simdi()})
    f = klon.git("fetch", "--tags", "origin")
    if f.returncode != 0:
        print(f"DUR: `git fetch --tags` başarısız: {f.stderr.strip()} "
              f"(ağ ya da depo sorunu → şimdi güncellenemez)", file=sys.stderr)
        return 2
    print(f"Geri dönüş noktası: {etiket}")
    return 0


# =====================================================================================================
# CLI
# =====================================================================================================
BAGLAMSIZ = {"onkontrol", "hazirla"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="guncelle.py",
        description="aXet tüketici güncelleme motoru (TASARIM §6 sözleşmesi)")
    ap.add_argument("--klon", type=Path, default=None,
                    help="tüketici klonunun kökü (varsayılan: bu betiğin repo kökü)")
    ap.add_argument("--harita", type=Path, default=None, help="harita.json yolu (test/teşhis)")
    ap.add_argument("--beklenen-origin", default=RESMI_ORIGIN,
                    help="onkontrol'ün beklediği resmî template adresi")
    alt = ap.add_subparsers(dest="altkomut", required=True)

    alt.add_parser("onkontrol", help="klon kimliği, origin, dal, sığ klon, TMP (§6)")
    alt.add_parser("hazirla", help="yerel anlık commit + geri dönüş etiketi + fetch")
    alt.add_parser("plan", help="plan.json üretir (0 plan var · 1 güncel · 2 hata)")

    p = alt.add_parser("sec", help="kalem/paket seçimi")
    p.add_argument("--hepsi", action="store_true")
    p.add_argument("--kalem", action="append")
    p.add_argument("--cikar", action="append")

    p = alt.add_parser("olc", help="seçili sınıfların test komutları")
    p.add_argument("--asama", required=True)

    p = alt.add_parser("uygula", help="otomatik vakaları yazar ve doğrular")
    p.add_argument("--otomatik", action="store_true")

    p = alt.add_parser("oneri", help="3-yollu birleşik öneri + iki fark + eşik")
    p.add_argument("yol")

    p = alt.add_parser("isaretle", help="kararı uygular, yazar, geri okur, doğrular")
    p.add_argument("yol")
    p.add_argument("--karar", required=True)
    p.add_argument("--gerekce")

    p = alt.add_parser("ozel-adim", help="sınıfın özel adımını koşar")
    p.add_argument("ad")

    alt.add_parser("butunluk", help="§8 araç sırası")

    p = alt.add_parser("geri-al", help="dosya ya da tümü geri dönüş etiketine")
    p.add_argument("yol", nargs="?")
    p.add_argument("--hepsi", action="store_true")

    p = alt.add_parser("kapanis", help="plan↔durum hükmü + RAPOR.md")
    p.add_argument("--kabul")

    alt.add_parser("durum", help="kalem × dosya × durum tablosu")

    p = alt.add_parser("kart", help="vaka kartını YENİ sürümden basar")
    p.add_argument("kod")

    args = ap.parse_args(argv)
    klon = Klon(args.klon or MOTOR_KOK)
    if not (klon.kok / ".git").exists():
        print(f"DUR: {klon.kok} bir git klonu değil.", file=sys.stderr)
        return 2
    klon.durum_dizini.mkdir(parents=True, exist_ok=True)

    try:
        if args.altkomut == "onkontrol":
            return komut_onkontrol(None, args, klon)
        if args.altkomut == "hazirla":
            return komut_hazirla(None, args, klon)
        b = Baglam(klon, harita_yukle(args.harita))
        return {
            "plan": komut_plan, "sec": komut_sec, "olc": komut_olc, "uygula": komut_uygula,
            "oneri": komut_oneri, "isaretle": komut_isaretle, "ozel-adim": komut_ozel_adim,
            "butunluk": komut_butunluk, "geri-al": komut_geri_al, "kapanis": komut_kapanis,
            "durum": komut_durum, "kart": komut_kart,
        }[args.altkomut](b, args)
    except Dur as e:
        print(f"DUR: {e}", file=sys.stderr)
        return e.kod
    except BilinmeyenEtkin as e:
        print(f"DUR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
