#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`%guncelle-proje` motoru — bir PROJENİN template kaynaklı dosyalarını 3-yollu günceller.

TASARIM: `maintenance/guncelle-mimari/TASARIM.md` §2b (proje tabanı = şablon sürüm kaydı) ·
§4 (vaka kodları) · §9 (`%guncelle-proje`). `scripts/guncelle.py` KLONU günceller; bu dosya
PROJEYİ. İkisi aynı vaka tablosunu ve aynı 3-yollu birleştiriciyi kullanır.

⛔ YENİDEN YAZMA YOK — P2 ÇAĞRILIR (ÖNCE-ARA sonucu, prior-art: bulundu `scripts/guncelle.py`):
`vaka_kodu` (§4 tablosu), `birlestir` (`git merge-file`), `yerel_fark_orani`, `fark_metni`,
`_oku`/`_yaz_json`, `Dur`, eşikler ve karar adları oradan **import edilir**, kopyalanmaz.
Aynı kopyadan (`scripts/` kardeşi) import K4 ile çelişmez: K4 motorun KLONDAKİ ESKİ sürümü
import etmesini yasaklar; `%guncelle-proje`nin ön koşulu ise klonun zaten güncel olmasıdır
(§9) ve `onkontrol` bunu ölçer. Yerel-özgü olan tek şey taban kurulumudur: proje dosyası
git'te değildir, taban `git show <commit>:templates/project/<rel>` + `_doldur` ile ÜRETİLİR.

ÖLÇÜLEN TUZAK (2026-09-17): `new_project.py` proje dosyalarını platform satır sonuyla yazar
(Windows'ta CRLF; `.githooks/**` istisna, orada açıkça LF). Template blob'u LF'tir. Bu yüzden
karşılaştırma ve özet DAİMA `\r\n → \n` normalize edilmiş bayt üzerinden yapılır; ham bayt
kıyası her dosyayı "yerelde değişmiş" gösterir ve SHA'sız geri düşüşte hiçbir sürüm eşleşmez.

Kullanım:
    python scripts/guncelle_proje.py --proje <dizin> <altkomut> [...]

Alt komutlar: onkontrol · onay · plan · uygula · oneri · isaretle · durum · geri-al · kapanis

KAPSAM — bakılmayanlar (bu motor ÖLÇMEZ):
  · yeniden adlandırma (+R): proje kapsamında UYGULANMAZ. Template'te taşınan bir dosya
    kaynak yolda V6/V6d (silme ya da "sende değişmiş, duruyor"), hedef yolda V2 olarak görünür.
    Yerel değişiklik KAYBOLMAZ (V6d silmez), ama "taşındı" diye raporlanmaz.
  · `templates/package/**` (K5: kullanıcı doldurur, taban anlamsız) — yalnız bilgi satırı.
  · testler/bütünlük turu: proje şablonunun test komutu yoktur; ölçüm klon tarafının işidir.
  · değişikliğin ANLAMCA doğru olduğu · aXet'in yeni bağlamı fiilen yüklediği · canlı SAP.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass

BURASI = Path(__file__).resolve().parent
AXET_HOME = BURASI.parent
if str(BURASI) not in sys.path:
    sys.path.insert(0, str(BURASI))

import guncelle as g        # noqa: E402  — §4 vaka tablosu + 3-yollu birleştirici (kopyalanmaz)
import new_project as np_   # noqa: E402  — `_doldur`, şablon yolları, sürüm kaydı (tek kaynak)
import sap_stamp            # noqa: E402  — damga gövdesi + yeniden damgalama

DURUM_DIZIN = ".axet-code/.guncelle-proje"
PAKET_SABLONU = "templates/package"
GECMIS_AZAMI = 50           # SHA'sız geri düşüşte gezilecek en fazla şablon commit'i
Dur = g.Dur


def _simdi() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _git_deposu_mu(kok: Path) -> bool:
    """`git remote` rc≠0'ı iki sebepten ayırır: proje hiç git deposu değil (bilgi, gürültü değil)
    ↔ depo var ama okunamadı (ÖLÇÜLEMEDİ). rc tek başına ayırt etmez: bozuk `.git/config` de
    "not a git repository" gibi 128 döner. Ölçüt `.git`in kökte ya da bir üst dizinde varlığıdır."""
    return any((d / ".git").exists() for d in (kok, *kok.parents))


def _norm(veri: bytes | None) -> bytes | None:
    """CRLF **ve tek-başına CR** → LF. Proje dosyası platform satır sonuyla, blob LF ile
    yazılır (ölçülmüş tuzak).

    ⛔ K1 (2026-09-20): gövde `new_project.satir_sonu_normalize`e devredildi — normalizasyon
    artık TEK kaynak. Burası yalnız `CRLF` çeviriyordu, `new_project` ise tek-başına CR'yi de
    çeviriyordu ⇒ tek-başına CR içeren şablonda iki taraf ayrışıyor ve dosya, aynı olduğu
    hâlde "yerel değişmiş" (V3) sayılıyordu; V3 listelenmediği için güncelleme SESSİZCE
    kayboluyordu. Gerekçenin tamamı ve ikili-dosya uyarısı o fonksiyonun docstring'inde.
    """
    return None if veri is None else np_.satir_sonu_normalize(veri)


def _ozet(veri: bytes | None) -> str | None:
    n = _norm(veri)
    return None if n is None else hashlib.sha256(n).hexdigest()


def _yazilacak(rel: str, veri: bytes) -> bytes:
    """Diske yazılacak içerik: metin LF'e normalize edilir, İKİLİ dosya ASLA (bug gate 2026-09-19
    ikinci tur). `_norm` baytlardaki `\\r\\n`'yi siler — PNG başlığı bile `\\r\\n` içerir — ve doğrulama
    iki tarafı da normalize ettiği için bozulma SESSİZ geçerdi."""
    return veri if ikili_mi(rel, [veri]) else (_norm(veri) or b"")


def ikili_mi(yol: str, ornekler) -> bool:
    """`guncelle.IKILI_UZANTI` + NUL taraması. (P2'nin `check-attr` kolu burada UYGULANMAZ:
    proje dosyaları template deposunda değildir, `.gitattributes` beyanı onlara sorulamaz.)"""
    if Path(yol).suffix.lower() in g.IKILI_UZANTI:
        return True
    return any(b"\0" in (o or b"")[:8000] for o in ornekler)


# =====================================================================================================
# KLON (template deposu — salt okunur)
# =====================================================================================================
class Klon:
    """aXet template klonu üzerinde salt-okur git işlemleri."""

    def __init__(self, kok: Path) -> None:
        self.kok = kok.resolve()

    def git(self, *args: str, ikili: bool = False) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(self.kok), *args], capture_output=True,
                              stdin=subprocess.DEVNULL,
                              **({} if ikili else {"text": True, "encoding": "utf-8",
                                                   "errors": "replace"}))

    def git_var_mi(self) -> bool:
        return (self.kok / ".git").exists() and self.git("rev-parse", "--git-dir").returncode == 0

    def var_mi(self, ref: str) -> bool:
        return self.git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}").returncode == 0

    def ls_tree(self, ref: str, onek: str) -> set[str]:
        r = self.git("ls-tree", "-r", "--name-only", "-z", ref, "--", onek)
        return {y for y in r.stdout.split("\0") if y} if r.returncode == 0 else set()

    def icerik(self, ref: str, yol: str) -> bytes | None:
        r = self.git("show", f"{ref}:{yol}", ikili=True)
        return r.stdout if r.returncode == 0 else None

    def sablon_commitleri(self, yollar: list[str]) -> list[str]:
        r = self.git("log", f"-{GECMIS_AZAMI}", "--format=%H", "--", *yollar)
        return [s.strip() for s in r.stdout.splitlines() if s.strip()] if r.returncode == 0 else []

    def geride_mi(self) -> tuple[bool | None, str]:
        """Klonda uygulanmamış YAYIN KALEMİ var mı. (None, sebep) = ÖLÇÜLEMEDİ.

        ⛔ Commit sayısı (`HEAD..@{u}`) ölçü DEĞİLDİR (Z29, 2026-09-21 — canlıda ölçüldü): `%guncelle`
        yayınları merge etmez, kalemleri yerel commit'le uygular ⇒ güncellemeden sonra da sayı > 0
        kalır ve bu kontrol her seferinde "ÖNCE %guncelle" diye DURUYORDU. Ölçü `session_brief` ile
        aynıdır (Q4): `origin/main` kataloğundaki kalem ya yayını HEAD'de içerildiği için ya da
        `uygulanan.json`'da kayıtlı olduğu için tamamdır (motorun plan kuralı, guncelle.py:717).
        Katalog okunamazsa eski ölçüye düşülür (katalogsuz eski yayın)."""
        r = self.git("show", "origin/main:guncelle/yayinlar.json")
        katalog = None
        if r.returncode == 0:
            try:
                katalog = json.loads(r.stdout)
            except ValueError:
                return None, "yayın kataloğu ayrıştırılamadı"
        if isinstance(katalog, dict) and isinstance(katalog.get("yayinlar"), list):
            uygulanan: dict = {}
            f = self.kok / g.DURUM_DIZIN_ADI / "uygulanan.json"
            if f.is_file():
                try:
                    u = json.loads(f.read_text(encoding="utf-8"))
                except ValueError:
                    return None, f"{f} ayrıştırılamadı"
                if not isinstance(u, dict) or not isinstance(u.get("kalemler", {}), dict):
                    return None, f"{f} beklenen biçimde değil"
                uygulanan = u.get("kalemler") or {}
            bekleyen = []
            for yayin in katalog["yayinlar"]:
                if not isinstance(yayin, dict):
                    return None, "yayın kataloğunda beklenmeyen kayıt"
                etiket = str(yayin.get("etiket") or "")
                if g.yayin_durumu(lambda *a: self.git(*a).returncode, etiket) == "icerildi":
                    continue
                bekleyen += [k["id"] for k in yayin.get("kalemler") or []
                             if isinstance(k, dict) and k.get("id") and k["id"] not in uygulanan]
            if bekleyen:
                return True, f"{len(bekleyen)} yayın kalemi uygulanmamış ({', '.join(bekleyen[:6])})"
            return False, "bekleyen yayın kalemi yok"
        r = self.git("rev-list", "--count", "HEAD..@{u}")
        if r.returncode != 0:
            return None, "upstream tanımlı değil"
        try:
            return int(r.stdout.strip()) > 0, r.stdout.strip()
        except ValueError:
            return None, "sayılamadı"


# =====================================================================================================
# PROJE
# =====================================================================================================
class Proje:
    def __init__(self, kok: Path, ad: str | None = None) -> None:
        self.kok = kok.resolve()
        if not self.kok.is_dir():
            raise Dur(f"proje dizini yok: {self.kok}")
        self.durum_dizini = self.kok / DURUM_DIZIN
        self.kayit = np_.surum_kaydi_oku(self.kok)
        self.sap = (self.kok / "sap-project.json").is_file()
        # `<PROJE_ADI>` yer tutucusu bu adla dolduruldu; taban da bu adla ÜRETİLİR.
        # Kayıt yoksa ad da bilinmiyor demektir: `new_project.py` varsayılanı dizin adıdır
        # (`new_project.py:70-71` `--name` yoksa `target.name`), ama kullanıcı `--name` vermiş
        # olabilir. O yüzden `--ad` ile açıkça verilebilir ve varsayım çıktıda GÖRÜNÜR.
        self.ad_kaynagi = ("parametre" if ad else ("kayit" if (self.kayit or {}).get("ad")
                                                   else "dizin-adi-varsayimi"))
        self.ad = ad or (self.kayit or {}).get("ad") or self.kok.name
        self.agents = self.kok / "AGENTS.md"
        metin = self.agents.read_text(encoding="utf-8", errors="replace") if self.agents.is_file() else ""
        self.damga_vardi = sap_stamp._BASLA_ONEK in metin or sap_stamp._BITIR_ONEK in metin
        self.damga_gerekli = self.sap or self.damga_vardi

    # --- dosya I/O (new_project.py ile AYNI yazım sözleşmesi) --------------------------------------
    def oku(self, rel: str) -> bytes | None:
        tam = self.kok / rel
        return tam.read_bytes() if tam.is_file() else None

    def yaz(self, rel: str, veri_lf: bytes) -> None:
        tam = self.kok / rel
        tam.parent.mkdir(parents=True, exist_ok=True)
        if rel == "AGENTS.md" and self.damga_gerekli:
            veri_lf = self._damgala(veri_lf)
        # İkili ölçütü `ikili_mi` (uzantı + NUL) — yalnız UnicodeDecodeError DEĞİL: geçerli UTF-8 olan
        # ikili dosya metin sayılıp `write_text` ile satır sonu çevrilerek BOZULUYORDU (bug gate
        # 2026-09-19 ikinci tur, ölçüldü: LF satır sonu CRLF'e döndü). new_project ile aynı ölçüt.
        if ikili_mi(rel, [veri_lf]):
            tam.write_bytes(veri_lf)
            return
        try:
            metin = veri_lf.decode("utf-8")
        except UnicodeDecodeError:
            tam.write_bytes(veri_lf)
            return
        if rel.startswith(".githooks/"):
            # git hook'u her platformda LF olmalı (new_project.py:114-118 ile aynı gerekçe).
            with open(tam, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(metin)
            tam.chmod(0o755)
        else:
            tam.write_text(metin, encoding="utf-8")

    def _damgala(self, govde_lf: bytes) -> bytes:
        """§2b: gövde birleştirildikten SONRA damga yeniden basılır (gövde damgayı taşımaz)."""
        metin = govde_lf.decode("utf-8", "replace")
        yeni, _onceki = sap_stamp.damgala(metin)
        return yeni.encode("utf-8")

    def sil(self, rel: str) -> None:
        tam = self.kok / rel
        if tam.is_file():
            tam.unlink()
        ana = tam.parent
        while ana != self.kok and ana.is_dir() and not any(ana.iterdir()):
            ana.rmdir()
            ana = ana.parent

    def damga_denetle(self) -> None:
        """Bozuk damga: `new_project.py:132` ile aynı hüküm — DUR, dokunma."""
        if not self.damga_vardi:
            return
        st, ayrinti = sap_stamp.denetle(self.agents.read_text(encoding="utf-8", errors="replace"))
        if st == "bozuk":
            raise Dur(f"AGENTS.md damgası BOZUK ({ayrinti}) — tek BASLA/BITIR bloğu bırak, "
                      f"sonra yeniden çalıştır. Güncelleme başlatılmadı.")
        if st == "kanonik_yok":
            raise Dur(f"kanonik kesin yasak metni okunamadı, damga denetlenemedi: {ayrinti}")


# =====================================================================================================
# BAĞLAM — taban + kapsam (TASARIM §2b)
# =====================================================================================================
class Baglam:
    def __init__(self, proje: Proje, klon: Klon) -> None:
        self.p = proje
        self.k = klon
        if not klon.git_var_mi():
            raise Dur(f"template klonu bir git deposu değil: {klon.kok} — taban kurulamaz.")
        self.sablon_yollari = np_.sablon_yollari(proje.sap)
        self.yeni_commit = np_.sablon_commit(proje.sap, klon.kok)
        if not self.yeni_commit:
            raise Dur("template klonunda şablon commit'i okunamadı "
                      f"(`git log -1 -- {' '.join(self.sablon_yollari)}` boş).")
        kayitli = (proje.kayit or {}).get("template_commit")
        self.kayit_axet_home = Path((proje.kayit or {}).get("axet_home") or klon.kok)
        if proje.kayit is None:
            self.taban_commit, self.taban_kaynagi = None, "eslesme"
        elif kayitli and klon.var_mi(kayitli):
            self.taban_commit, self.taban_kaynagi = kayitli, "kayit"
        else:
            # Kayıt var ama commit klonda YOK (force-push / sığ klon / başka klon) → taban uydurulmaz.
            self.taban_commit, self.taban_kaynagi = None, "cozulemedi"
        self.adaylar = (klon.sablon_commitleri(self.sablon_yollari)
                        if self.taban_kaynagi == "eslesme" else [])

    # --- yol eşlemesi ------------------------------------------------------------------------------
    def proje_yolu(self, klon_yolu: str) -> str | None:
        for onek in self.sablon_yollari:
            if klon_yolu.startswith(onek + "/"):
                return klon_yolu[len(onek) + 1:]
        return None

    def kaynak_yollari(self, rel: str) -> list[str]:
        return [f"{onek}/{rel}" for onek in self.sablon_yollari]

    # --- içerik ------------------------------------------------------------------------------------
    def icerik(self, commit: str, rel: str, axet_home: Path) -> bytes | None:
        """Şablon dosyasının o commit'teki, `_doldur` uygulanmış hâli (= projedeki beklenen içerik)."""
        for kaynak in self.kaynak_yollari(rel):
            ham = self.k.icerik(commit, kaynak)
            if ham is None:
                continue
            if ikili_mi(rel, [ham]):
                return ham          # ikili: yer tutucu ikame edilmez (new_project ile aynı ölçüt)
            try:
                metin = ham.decode("utf-8")
            except UnicodeDecodeError:
                return ham          # ikili: yer tutucu ikame edilemez
            return np_._doldur(metin, self.p.ad, axet_home).encode("utf-8")
        return None

    def yeni_icerik(self, rel: str) -> bytes | None:
        return self.icerik(self.yeni_commit, rel, self.k.kok)

    def taban_icerik(self, commit: str, rel: str) -> bytes | None:
        return self.icerik(commit, rel, self.kayit_axet_home)

    def govde(self, rel: str, veri: bytes | None) -> bytes | None:
        """AGENTS.md'de damga bloğu üç sürümden de ÇIKARILIR (§2b).

        ⚠ ÖNCE normalize: yerel dosya CRLF'tir; ham CRLF metinde blok sonrası boş satırlar
        `\\r` bırakır ve dosya "değişmiş" görünür (ölçüldü 2026-09-17 → AGENTS.md V4t çıkıyordu).
        """
        if veri is None or rel != "AGENTS.md":
            return _norm(veri)
        try:
            return sap_stamp.govde((_norm(veri) or b"").decode("utf-8")).encode("utf-8")
        except UnicodeDecodeError:
            return _norm(veri)

    # --- kapsam ------------------------------------------------------------------------------------
    def kapsam(self) -> list[str]:
        yollar: set[str] = set()
        commitler = [self.yeni_commit] + ([self.taban_commit] if self.taban_commit else self.adaylar)
        for c in commitler:
            for onek in self.sablon_yollari:
                for klon_yolu in self.k.ls_tree(c, onek):
                    rel = self.proje_yolu(klon_yolu)
                    if rel:
                        yollar.add(rel)
        return sorted(yollar)

    # --- taban (dosya başına) ----------------------------------------------------------------------
    def taban_bul(self, rel: str, l: bytes | None) -> tuple[str | None, bytes | None, bool]:
        """Döner: (taban_commit, taban_icerigi, taban_biliniyor).

        `taban_biliniyor=False` → VTB (§4): otomatik işlem YOK, taban uydurulmaz.
        """
        if self.taban_kaynagi == "cozulemedi":
            return None, None, False
        if self.taban_commit:
            return self.taban_commit, self.govde(rel, self.taban_icerik(self.taban_commit, rel)), True
        # SHA'sız geri düşüş (§2b): `_doldur` uygulanmış hâli proje dosyasıyla birebir eşleşen
        # EN YENİ commit taban sayılır. Eşleşme yoksa kullanıcı değiştirmiştir → VTB.
        l_ozet = _ozet(self.govde(rel, l))
        eski_surumde_vardi = False
        for c in self.adaylar:
            t = self.govde(rel, self.taban_icerik(c, rel))
            if t is None:
                continue
            # ⚠ HEDEF commit'in kendisi "geçmişte vardı" SAYILMAZ: bu yayında EKLENEN bir dosya
            # yalnız orada görünür ve sayılsaydı her yeni dosya V2 yerine VTB olurdu
            # (ölçüldü 2026-09-17: `validators-local/README.md`).
            if c != self.yeni_commit:
                eski_surumde_vardi = True
            if l_ozet is not None and _ozet(t) == l_ozet:
                return c, t, True
        if l is None and not eski_surumde_vardi:
            # Eski hiçbir sürümde olmayan yol: taban BİLİNİYOR ve dosya tabanda YOK → V2.
            return None, None, True
        return None, None, False


# =====================================================================================================
# DURUM DOSYALARI
# =====================================================================================================
def plan_oku(p: Proje) -> dict:
    veri = g._oku(p.durum_dizini / "plan.json", None)
    if veri is None:
        raise Dur("plan.json yok — önce `guncelle_proje.py plan` çalıştır.")
    return veri


def durum_oku(p: Proje) -> dict:
    return g._oku(p.durum_dizini / "durum.json", {"surum": 1, "dosyalar": {}})


def durum_kaydet(p: Proje, rel: str, **alanlar) -> None:
    d = durum_oku(p)
    kayit = d["dosyalar"].setdefault(rel, {})
    kayit.update(alanlar)
    kayit["zaman"] = _simdi()
    g._yaz_json(p.durum_dizini / "durum.json", d)


def _plan_kaydi(plan: dict, rel: str) -> dict:
    for d in plan["dosyalar"]:
        if d["yol"] == rel:
            return d
    raise Dur(f"{rel} planda yok — kartta olmayan bir dosyaya dokunulmaz (§7).")


# =====================================================================================================
# ONAY — "HER PROJE AYRI ONAYLANIR" (kullanıcı kararı Q1, 2026-09-15)
# =====================================================================================================
# Toplu tarama YOKTUR: onay TEK bir proje yoluna ve TEK bir hedef şablon commit'ine bağlanır.
# Kopyalanan bir onay dosyası başka projeyi açmaz; şablon ilerlerse onay kendiliğinden düşer.
def onay_yolu(p: Proje) -> Path:
    return p.durum_dizini / "onay.json"


def komut_onay(b: Baglam, args) -> int:
    p = b.p
    if (args.kabul or "").strip() != p.ad:
        print(f"DUR: onay için projenin ADINI yazman gerekiyor. Beklenen: {p.ad!r}, "
              f"gelen: {(args.kabul or '').strip()!r}. Her proje AYRI onaylanır (Q1).",
              file=sys.stderr)
        return 2
    g._yaz_json(onay_yolu(p), {"surum": 1, "proje": p.kok.as_posix(), "ad": p.ad,
                               "hedef_commit": b.yeni_commit, "zaman": _simdi()})
    print(f"ONAY: {p.ad} ({p.kok}) → şablon {b.yeni_commit[:10]}. "
          f"Bu onay YALNIZ bu projeyi ve bu şablon sürümünü kapsar.")
    return 0


def onay_dogrula(b: Baglam) -> None:
    p = b.p
    kayit = g._oku(onay_yolu(p), None)
    if not kayit:
        raise Dur(f"proje onayı YOK. Her proje ayrı onaylanır (Q1): "
                  f"`guncelle_proje.py --proje <dizin> onay --kabul \"{p.ad}\"`")
    if kayit.get("proje") != p.kok.as_posix():
        raise Dur(f"onay BAŞKA bir projeye ait ({kayit.get('proje')}) — bu proje: {p.kok.as_posix()}. "
                  f"Her proje ayrı onaylanır (Q1).")
    if kayit.get("hedef_commit") != b.yeni_commit:
        raise Dur(f"onay {str(kayit.get('hedef_commit'))[:10]} şablon sürümü için verilmişti; "
                  f"klondaki şablon {b.yeni_commit[:10]} oldu. Yeniden planla ve yeniden onayla.")


# =====================================================================================================
# PLAN
# =====================================================================================================
def dosya_vakasi(b: Baglam, rel: str) -> dict:
    l_ham = b.p.oku(rel)
    l = b.govde(rel, l_ham)
    taban_commit, t, taban_biliniyor = b.taban_bul(rel, l_ham)
    y = b.govde(rel, b.yeni_icerik(rel))

    if not taban_biliniyor:
        kayit = {"yol": rel, "vaka": "VTB", "taban": None}
        return kayit
    kod = g.vaka_kodu(_ozet(t), _ozet(l), _ozet(y), taban_var=True)
    kayit = {"yol": rel, "vaka": kod, "taban": taban_commit}
    if kod == "V4":
        if ikili_mi(rel, [t, l, y]):
            kayit["vaka"] = "V4B"
        else:
            _birlesik, cakisma = g.birlestir(None, rel, _norm(t) or b"", _norm(l) or b"",
                                             _norm(y) or b"")
            oran = g.yerel_fark_orani(_norm(t) or b"", _norm(l) or b"")
            kayit["cakisma"] = cakisma
            kayit["yerel_fark_orani"] = round(oran, 3)
            if cakisma > g.ESIK_CAKISMA_BLOGU or oran > g.ESIK_YEREL_FARK:
                kayit["vaka"] = "V4c+ESIK"
            else:
                kayit["vaka"] = "V4c" if cakisma else "V4t"
    return kayit


def _paket_sablonu_satiri(b: Baglam) -> str:
    """K5: `templates/package/**` kapsam DIŞI — yalnız bilgi satırı."""
    if not b.taban_commit:
        return "paket şablonu: taban bilinmiyor, karşılaştırılmadı (K5: kapsam dışı)"
    r = b.k.git("diff", "--name-only", b.taban_commit, b.yeni_commit, "--", PAKET_SABLONU)
    if r.returncode != 0:
        # rc≠0 "değişiklik yok" demek değildir (rc taraması 2026-09-18).
        return (f"paket şablonu: karşılaştırma ÖLÇÜLEMEDİ (git diff rc={r.returncode}) "
                "(K5: kapsam dışı)")
    degisen = [s.strip() for s in r.stdout.splitlines() if s.strip()]
    if not degisen:
        return "paket şablonu: değişiklik yok (K5: kapsam dışı)"
    return ("paket şablonunda değişiklik var (K5 — kapsam DIŞI, dokunulmadı): "
            + ", ".join(degisen))


def komut_plan(b: Baglam, args) -> int:
    p = b.p
    p.damga_denetle()
    sayaclar: dict[str, int] = {}
    dosyalar = []
    for rel in b.kapsam():
        kayit = dosya_vakasi(b, rel)
        sayaclar[kayit["vaka"]] = sayaclar.get(kayit["vaka"], 0) + 1
        if kayit["vaka"] not in g.ISLEMSIZ_VAKALAR:
            dosyalar.append(kayit)

    paket_satiri = _paket_sablonu_satiri(b)
    if not dosyalar:
        print(f"Proje şablonu güncel: işlem gerektiren dosya yok "
              f"(şablon {b.yeni_commit[:10]}, sayaçlar: "
              + ", ".join(f"{k}={v}" for k, v in sorted(sayaclar.items())) + ")")
        print("  " + paket_satiri)
        return 1

    plan = {
        "surum": 1, "proje": p.kok.as_posix(), "ad": p.ad, "sap": p.sap,
        "taban_kaynagi": b.taban_kaynagi, "taban_commit": b.taban_commit,
        "yeni_commit": b.yeni_commit, "sablon_yollari": b.sablon_yollari,
        "damgali": p.damga_gerekli, "ad_kaynagi": p.ad_kaynagi, "dosyalar": dosyalar,
        "sayaclar": dict(sorted(sayaclar.items())),
        "paket_sablonu": paket_satiri, "uretim": _simdi(),
    }
    g._yaz_json(p.durum_dizini / "plan.json", plan)
    _plan_tablosu(plan)
    return 0


def _plan_tablosu(plan: dict) -> None:
    taban = {"kayit": f"sürüm kaydı ({str(plan['taban_commit'])[:10]})",
             "eslesme": "SHA'sız geri düşüş (içerik eşleştirmesi)",
             "cozulemedi": "kayıttaki commit klonda YOK → hepsi VTB"}[plan["taban_kaynagi"]]
    ad_notu = {"kayit": "ad kaynağı: sürüm kaydı",
               "parametre": "ad kaynağı: --ad parametresi",
               "dizin-adi-varsayimi": "⚠ ad kaynağı: DİZİN ADINDAN VARSAYILDI (kayıt yok) — "
                                      "proje `--name` ile başka bir adla kurulduysa taban YANLIŞ "
                                      "üretilir; doğrula ya da `--ad <AD>` ver"}[plan["ad_kaynagi"]]
    print(f"Proje planı: {plan['ad']} ({ad_notu}) → şablon {plan['yeni_commit'][:10]} · "
          f"taban: {taban}")
    for d in plan["dosyalar"]:
        print(f"  {d['vaka']:9s} {d['yol']}")
    print("Sayaçlar: " + ", ".join(f"{k}={v}" for k, v in plan["sayaclar"].items()))
    print("  " + plan["paket_sablonu"])
    if plan["taban_kaynagi"] != "kayit":
        print("  NOT: VTB dosyalarında otomatik birleştirme YASAKTIR (taban uydurulmaz); "
              "kullanıcı 'yeniyi al / yereli koru / elle' seçer.")
        if plan["ad_kaynagi"] == "dizin-adi-varsayimi" and plan["sayaclar"].get("VTB"):
            print("  İPUCU: proje adı DİZİN ADINDAN varsayıldı. `--name` ile başka bir ad "
                  "verilmişse taban hiçbir sürümle eşleşmez ve her şey VTB görünür → "
                  "`--ad <GERÇEK_AD>` ile yeniden planla.")


# =====================================================================================================
# UYGULA (otomatik vakalar)
# =====================================================================================================
def _yedekle(p: Proje, rel: str) -> None:
    kaynak = p.kok / rel
    hedef = p.durum_dizini / "yedek" / rel
    hedef.parent.mkdir(parents=True, exist_ok=True)
    if kaynak.is_file():
        shutil.copy2(kaynak, hedef)
    else:
        (hedef.parent / (hedef.name + ".YOKTU")).write_text("", encoding="utf-8")


def komut_uygula(b: Baglam, args) -> int:
    p, plan = b.p, plan_oku(b.p)
    if not args.otomatik:
        print("DUR: `uygula` yalnız `--otomatik` ile çalışır (yargı vakaları `isaretle` ile).",
              file=sys.stderr)
        return 2
    onay_dogrula(b)
    hata = 0
    for d in plan["dosyalar"]:
        rel, kod = d["yol"], d["vaka"]
        if kod not in g.OTOMATIK_VAKALAR:
            durum_kaydet(p, rel, vaka=kod, durum="bekliyor")
            continue
        _yedekle(p, rel)
        if kod == "V6":
            p.sil(rel)
            beklenen = None
        else:
            y = b.yeni_icerik(rel)
            if y is None:
                print(f"FAIL {rel}: yeni sürümde içerik okunamadı.", file=sys.stderr)
                durum_kaydet(p, rel, vaka=kod, durum="bekliyor", not_="yeni içerik yok")
                hata = 1
                continue
            p.yaz(rel, _yazilacak(rel, y))
            beklenen = _ozet(b.govde(rel, y))
        gercek = _ozet(b.govde(rel, p.oku(rel)))
        if gercek != beklenen:
            print(f"FAIL {rel}: yazıldı ama doğrulanamadı.", file=sys.stderr)
            durum_kaydet(p, rel, vaka=kod, durum="uygulandi", beklenen_ozet=beklenen,
                         not_="doğrulanamadı")
            hata = 1
            continue
        durum_kaydet(p, rel, vaka=kod, durum="dogrulandi", beklenen_ozet=beklenen, karar="otomatik")
        if kod == "V5":
            print(f"GERİ GETİRİLDİ: {rel} — yerelde silinmişti, bu sürümde güncellendi; "
                  f"istemiyorsan tekrar sil")
        elif kod == "V6":
            print(f"SİLİNDİ: {rel} — şablon emekliye ayırdı, sende değişmemişti")
        else:
            print(f"ALINDI: {rel} ({kod})")
    return hata


# =====================================================================================================
# ÖNERİ / İŞARETLE
# =====================================================================================================
def _uc_surum(b: Baglam, rel: str) -> tuple[bytes, bytes, bytes]:
    l_ham = b.p.oku(rel)
    l = b.govde(rel, l_ham)
    taban_commit, t, taban_biliniyor = b.taban_bul(rel, l_ham)
    if not taban_biliniyor:
        raise Dur(f"{rel} için TABAN bilinmiyor (VTB) — otomatik birleştirme YASAK (§4). "
                  f"Farkı göster; kullanıcı 'yeniyi al / yereli koru / elle' seçsin.")
    y = b.govde(rel, b.yeni_icerik(rel))
    return _norm(t) or b"", _norm(l) or b"", _norm(y) or b""


def komut_oneri(b: Baglam, args) -> int:
    p, plan = b.p, plan_oku(b.p)
    rel = args.yol.replace("\\", "/")
    _plan_kaydi(plan, rel)
    t, l, y = _uc_surum(b, rel)
    if ikili_mi(rel, [t, l, y]):
        print(f"V4B — ikili dosya, birleştirme yok: {rel}. Karar: "
              f"`isaretle {rel} --karar yerel|yeni`.")
        return 1
    birlesik, cakisma = g.birlestir(None, rel, t, l, y)
    oran = g.yerel_fark_orani(t, l)
    print(f"--- T→L (senin değişikliğin) ---\n"
          f"{g.fark_metni(t, l, 'TABAN', 'YEREL') or '(fark yok)'}")
    print(f"--- T→Y (bizim değişikliğimiz) ---\n"
          f"{g.fark_metni(t, y, 'TABAN', 'YENİ') or '(fark yok)'}")
    print(f"Çakışma bloğu: {cakisma} · yerel fark oranı: {oran:.0%} "
          f"(eşik: >{g.ESIK_CAKISMA_BLOGU} blok ya da >%{int(g.ESIK_YEREL_FARK * 100)})")
    if cakisma > g.ESIK_CAKISMA_BLOGU or oran > g.ESIK_YEREL_FARK:
        elle = p.durum_dizini / "elle"
        for ad, metin in ((f"{rel}.yerel.diff", g.fark_metni(t, l, "TABAN", "YEREL")),
                          (f"{rel}.yeni.diff", g.fark_metni(t, y, "TABAN", "YENİ"))):
            h = elle / ad
            h.parent.mkdir(parents=True, exist_ok=True)
            h.write_text(metin, encoding="utf-8")
        print(f"V4c+ESIK — ayrışma eşiği aşıldı, birleştirme DENENMEDİ. Farklar: {elle}")
        return 3
    hedef = p.durum_dizini / "oneri" / rel
    hedef.parent.mkdir(parents=True, exist_ok=True)
    hedef.write_bytes(birlesik)
    print(f"Öneri yazıldı: {hedef}")
    return 1 if cakisma else 0


def komut_isaretle(b: Baglam, args) -> int:
    p, plan = b.p, plan_oku(b.p)
    rel = args.yol.replace("\\", "/")
    if args.karar not in g.GECERLI_KARARLAR:
        print(f"DUR: geçersiz karar {args.karar!r}. Geçerli: {', '.join(g.GECERLI_KARARLAR)}",
              file=sys.stderr)
        return 2
    d = _plan_kaydi(plan, rel)
    if args.karar == "ertelendi" and not args.gerekce:
        print("DUR: `--karar ertelendi` GEREKÇE ister (§6 `atlandi(gerekce)`).", file=sys.stderr)
        return 2
    onay_dogrula(b)

    if args.karar == "ertelendi":
        durum_kaydet(p, rel, vaka=d["vaka"], durum="atlandi", karar="ertelendi",
                     gerekce=args.gerekce)
        print(f"ERTELENDİ: {rel} — {args.gerekce}")
        return 0

    if args.karar == "yerel":
        durum_kaydet(p, rel, vaka=d["vaka"], durum="dogrulandi", karar="yerel",
                     beklenen_ozet=_ozet(b.govde(rel, p.oku(rel))))
        print(f"YEREL KORUNDU: {rel}")
        return 0

    if args.karar in ("yeni", "yeniden-adlandir"):
        y = b.yeni_icerik(rel)
        if y is None:
            print(f"DUR: {rel} yeni sürümde yok — `--karar {args.karar}` uygulanamaz.",
                  file=sys.stderr)
            return 2
        _yedekle(p, rel)
        if args.karar == "yeniden-adlandir" and (p.kok / rel).is_file():
            tam = p.kok / rel
            shutil.move(str(tam), str(tam.with_name(tam.name + ".yerel")))
            print(f"Senin dosyan korundu: {rel}.yerel")
        p.yaz(rel, _yazilacak(rel, y))
        return _dogrula_ve_kaydet(b, rel, d["vaka"], args.karar, _ozet(b.govde(rel, y)))

    # birlesik
    oneri = p.durum_dizini / "oneri" / rel
    if not oneri.is_file():
        print(f"DUR: öneri dosyası yok — önce `guncelle_proje.py oneri {rel}`.", file=sys.stderr)
        return 2
    veri = oneri.read_bytes()
    kalanlar = g.cakisma_isaretleri(veri.decode("utf-8", "replace"))
    if kalanlar:
        print(f"FAIL {rel}: öneri dosyasında çakışma işareti duruyor ({', '.join(kalanlar)}). "
              f"Çakışmaları çöz, sonra yeniden işaretle.", file=sys.stderr)
        durum_kaydet(p, rel, vaka=d["vaka"], durum="bekliyor", karar="birlesik",
                     not_="çakışma işareti kaldı")
        return 1
    _yedekle(p, rel)
    p.yaz(rel, _norm(veri) or b"")
    return _dogrula_ve_kaydet(b, rel, d["vaka"], "birlesik", _ozet(veri))


def _dogrula_ve_kaydet(b: Baglam, rel: str, vaka: str, karar: str, beklenen: str | None) -> int:
    gercek = _ozet(b.govde(rel, b.p.oku(rel)))
    if gercek != beklenen:
        print(f"FAIL {rel}: yazıldı ama geri okunduğunda farklı.", file=sys.stderr)
        durum_kaydet(b.p, rel, vaka=vaka, durum="uygulandi", karar=karar, beklenen_ozet=beklenen,
                     not_="doğrulanamadı")
        return 1
    durum_kaydet(b.p, rel, vaka=vaka, durum="dogrulandi", karar=karar, beklenen_ozet=beklenen)
    print(f"İŞARETLENDİ: {rel} → {karar} (dogrulandi)")
    return 0


# =====================================================================================================
# GERİ AL
# =====================================================================================================
def komut_geri_al(b: Baglam, args) -> int:
    p = b.p
    yedek = p.durum_dizini / "yedek"
    if args.hepsi:
        yollar = [d["yol"] for d in plan_oku(p)["dosyalar"]]
    elif args.yol:
        yollar = [args.yol.replace("\\", "/")]
    else:
        print("DUR: `geri-al` bir yol ya da `--hepsi` ister.", file=sys.stderr)
        return 2
    hata = 0
    for rel in sorted(set(yollar)):
        kaynak = yedek / rel
        yoktu = kaynak.parent / (kaynak.name + ".YOKTU")
        if kaynak.is_file():
            hedef = p.kok / rel
            hedef.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(kaynak, hedef)
            print(f"GERİ ALINDI: {rel}")
        elif yoktu.is_file():
            p.sil(rel)
            print(f"GERİ ALINDI (silindi): {rel} — güncellemeden önce yoktu")
        else:
            continue
        durum_kaydet(p, rel, durum="geri_alindi")
    return hata


# =====================================================================================================
# KAPANIŞ
# =====================================================================================================
def komut_kapanis(b: Baglam, args) -> int:
    p, plan = b.p, plan_oku(b.p)
    onay_dogrula(b)
    durum = durum_oku(p)
    satirlar, eksikler = [], []

    for d in plan["dosyalar"]:
        rel = d["yol"]
        kayit = durum["dosyalar"].get(rel, {})
        dv = kayit.get("durum", "bekliyor")
        karar = kayit.get("karar", "—")
        # §6 atlanamazlık: ajanın "yaptım" demesi durum değiştirmez — DİSKTEN yeniden doğrula.
        if dv == "dogrulandi":
            if _ozet(b.govde(rel, p.oku(rel))) != kayit.get("beklenen_ozet"):
                dv = "uygulandi"
                eksikler.append(f"{rel}: durum.json 'dogrulandi' diyor ama disk farklı")
            else:
                ham = p.oku(rel)
                if ham and g.cakisma_isaretleri(ham.decode("utf-8", "replace")):
                    dv = "uygulandi"
                    eksikler.append(f"{rel}: çakışma işareti duruyor")
        if dv in ("bekliyor", "uygulandi"):
            eksikler.append(f"{rel}: durum '{dv}' (dogrulandi ya da gerekçeli atlandi gerekir)")
            satirlar.append(f"[FAIL] {rel} {d['vaka']} {karar}")
        elif dv == "atlandi":
            satirlar.append(f"[WARN] {rel} {d['vaka']} atlandi ({kayit.get('gerekce', '—')})")
        elif dv == "geri_alindi":
            satirlar.append(f"[WARN] {rel} {d['vaka']} geri_alindi")
        else:
            satirlar.append(f"[PASS] {rel} {d['vaka']} {karar}")

    # damga: gövde birleşiminden SONRA yeniden basılır ve denetlenir (§2b + §9)
    damga_satiri = "damga: proje SAP değil ve damga yok — ilgisiz"
    if p.damga_gerekli:
        try:
            p.damga_denetle()
            metin = p.agents.read_text(encoding="utf-8", errors="replace") if p.agents.is_file() else ""
            yeni, onceki = sap_stamp.damgala(metin)
            if onceki != "guncel":
                p.agents.write_text(yeni, encoding="utf-8")
            st, ayrinti = sap_stamp.denetle(
                p.agents.read_text(encoding="utf-8", errors="replace"))
            damga_satiri = f"damga: {st} {ayrinti}".strip()
            if st != "guncel":
                eksikler.append(f"kesin yasak damgası güncel değil: {st} {ayrinti}")
        except Dur as e:
            damga_satiri = f"damga: DUR — {e}"
            eksikler.append(str(e))

    kabul = bool(args.kabul)
    kod = 0 if not eksikler else (3 if kabul else 1)

    rapor = [f"# Proje güncelleme raporu — {plan['ad']}", "",
             f"Üretim: {_simdi()} · proje: `{plan['proje']}` · şablon: "
             f"`{plan['yeni_commit'][:10]}` · taban kaynağı: {plan['taban_kaynagi']}", ""]
    rapor += satirlar or ["(planda dosya yok)"]
    rapor += ["", "## Sayaçlar", ", ".join(f"{a}={c}" for a, c in plan["sayaclar"].items()),
              "", "## Damga", damga_satiri,
              "", "## Paket şablonu", plan["paket_sablonu"]]
    ekip = subprocess.run(["git", "-C", str(p.kok), "remote"], capture_output=True, text=True,
                          stdin=subprocess.DEVNULL, encoding="utf-8", errors="replace")
    if ekip.returncode != 0 and not _git_deposu_mu(p.kok):
        rapor += ["", "## Ekip reposu", "Proje bir git deposu değil — ekip reposu yok."]
    elif ekip.returncode != 0:
        rapor += ["", "## Ekip reposu",
                  f"ÖLÇÜLEMEDİ (git remote rc={ekip.returncode}) — proje bir ekip reposuysa bu "
                  "değişiklikler commit'le ekip arkadaşlarına gider; commit KULLANICININ onayıyla atılır."]
    elif ekip.stdout.strip():
        rapor += ["", "## Ekip reposu",
                  "Bu değişiklikler proje reposuna commit edilecek; ekip arkadaşların pull edince "
                  "onlara da gelir. Commit KULLANICININ onayıyla atılır; push asla."]
    rapor += ["", "## Kullanıcının kendi terminalinde",
              f"Davranış yüzeyi değiştiyse: python \"{AXET_HOME / 'scripts' / 'behavior_manifest.py'}\" generate"]
    if eksikler:
        rapor += ["", "## KAPANMADI — eksikler"] + [f"- {e}" for e in eksikler]
    if kabul:
        rapor += ["", f"## Kullanıcı onaylı açık FAIL ile kapandı\n{args.kabul}"]
    rapor += ["", "KAPSAM — bakılanlar: plandaki dosyaların disk durumu (yeniden özetlendi) · "
                  "çakışma işareti · kesin yasak damgası.",
              "KAPSAM — bakılmayanlar: değişikliğin ANLAMCA doğru olduğu (temiz birleşme yanlış "
              "olabilir) · aXet'in yeni bağlamı fiilen yüklediği · `templates/package/**` (K5) · "
              "yeniden adlandırma (+R proje kapsamında uygulanmaz) · proje reposunun commit'i · "
              "canlı SAP."]
    p.durum_dizini.mkdir(parents=True, exist_ok=True)
    (p.durum_dizini / "RAPOR.md").write_text("\n".join(rapor) + "\n", encoding="utf-8")

    for e in eksikler:
        print("EKSİK: " + e, file=sys.stderr)
    if kod in (0, 3):
        np_.surum_kaydi_yaz(p.kok, p.ad, p.sap, plan["yeni_commit"], "guncelle-proje", b.k.kok)
        print(f"Şablon sürüm kaydı güncellendi: {plan['yeni_commit'][:10]}")
    print((p.durum_dizini / "RAPOR.md").read_text(encoding="utf-8"))
    return kod


# =====================================================================================================
# DURUM / ÖN KONTROL
# =====================================================================================================
def komut_durum(b: Baglam, args) -> int:
    p = b.p
    plan = g._oku(p.durum_dizini / "plan.json", None)
    if plan is None:
        print("plan.json yok.")
        return 0
    durum = durum_oku(p)
    print(f"{'VAKA':10s} {'DURUM':12s} {'KARAR':16s} YOL")
    for d in plan["dosyalar"]:
        s = durum["dosyalar"].get(d["yol"], {})
        print(f"{d['vaka']:10s} {s.get('durum', 'bekliyor'):12s} "
              f"{str(s.get('karar', '—')):16s} {d['yol']}")
    return 0


def komut_onkontrol(b: Baglam, args) -> int:
    p, k = b.p, b.k
    bilgi, sorunlar = [], []
    bilgi.append(f"proje: {p.kok} (ad: {p.ad}, SAP: {'evet' if p.sap else 'hayır'})")
    bilgi.append(f"template klonu: {k.kok}")
    bilgi.append(f"şablon commit'i (hedef): {b.yeni_commit[:10]}")

    geride, ayrinti = k.geride_mi()
    if geride is None:
        bilgi.append(f"klon güncelliği: ÖLÇÜLEMEDİ ({ayrinti}) — önce `%guncelle` çalıştırıldığını varsayma")
    elif geride:
        sorunlar.append(f"template klonu güncel değil: {ayrinti} — ÖNCE `%guncelle` (§9 ön koşulu)")
    else:
        bilgi.append(f"klon güncelliği: {ayrinti}")

    if p.kayit is None:
        bilgi.append("şablon sürüm kaydı YOK → taban içerik eşleştirmesiyle bulunacak "
                     "(eşleşmeyen dosyalar VTB)")
    elif b.taban_kaynagi == "cozulemedi":
        sorunlar.append(f"sürüm kaydındaki commit klonda YOK "
                        f"({str((p.kayit or {}).get('template_commit'))[:10]}) — tüm dosyalar VTB olur")
    else:
        bilgi.append(f"şablon sürüm kaydı: {str(b.taban_commit)[:10]} ({p.kayit.get('kaynak')})")

    try:
        p.damga_denetle()
        if p.damga_gerekli:
            bilgi.append("damga: okunabilir (kapanışta yeniden basılacak)")
    except Dur as e:
        sorunlar.append(str(e))

    r = subprocess.run(["git", "-C", str(p.kok), "remote"], capture_output=True, text=True,
                       stdin=subprocess.DEVNULL, encoding="utf-8", errors="replace")
    if r.returncode != 0 and not _git_deposu_mu(p.kok):
        bilgi.append("ekip reposu: proje bir git deposu değil")
    elif r.returncode != 0:
        bilgi.append(f"ekip reposu denetimi ÖLÇÜLEMEDİ (git remote rc={r.returncode}) — proje bir "
                     "ekip reposuysa değişiklikler commit'le ekibe gider.")
    elif r.stdout.strip():
        bilgi.append("EKİP REPOSU UYARISI: bu değişiklikler proje reposuna commit edilecek; "
                     "ekip arkadaşların pull edince onlara da gelir. Commit kullanıcının "
                     "onayıyla atılır; push asla.")

    onay = g._oku(onay_yolu(p), None)
    bilgi.append("proje onayı: " + ("var" if onay and onay.get("proje") == p.kok.as_posix()
                                    else "YOK — her proje ayrı onaylanır (Q1)"))
    for s in bilgi:
        print("  " + s)
    for s in sorunlar:
        print("DUR: " + s, file=sys.stderr)
    return 2 if sorunlar else 0


# =====================================================================================================
# CLI
# =====================================================================================================
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="guncelle_proje.py",
        description="aXet proje şablonu güncelleme motoru (TASARIM §2b/§9)")
    ap.add_argument("--proje", type=Path, default=Path.cwd(), help="proje kökü")
    ap.add_argument("--ad", default=None,
                    help="proje adı (`<PROJE_ADI>` yer tutucusu bununla dolduruldu). Sürüm kaydı yoksa taban bu adla üretilir; verilmezse dizin adı VARSAYILIR.")
    ap.add_argument("--klon", type=Path, default=AXET_HOME, help="template klonu (varsayılan: bu betiğin kökü)")
    alt = ap.add_subparsers(dest="altkomut", required=True)

    alt.add_parser("onkontrol", help="proje/klon/kayıt/damga ön kontrolü")
    q = alt.add_parser("onay", help="BU projeyi BU şablon sürümü için onayla (Q1)")
    q.add_argument("--kabul", required=True, help="projenin adı (onay için aynen yazılır)")
    alt.add_parser("plan", help="plan.json üretir (0 plan var · 1 güncel · 2 hata)")
    q = alt.add_parser("uygula", help="otomatik vakaları yazar ve doğrular")
    q.add_argument("--otomatik", action="store_true")
    q = alt.add_parser("oneri", help="3-yollu birleşik öneri + iki fark + eşik")
    q.add_argument("yol")
    q = alt.add_parser("isaretle", help="kararı uygular, yazar, geri okur, doğrular")
    q.add_argument("yol")
    q.add_argument("--karar", required=True)
    q.add_argument("--gerekce")
    q = alt.add_parser("geri-al", help="dosya ya da tümü güncelleme öncesi hâline")
    q.add_argument("yol", nargs="?")
    q.add_argument("--hepsi", action="store_true")
    q = alt.add_parser("kapanis", help="plan↔durum hükmü + damga + RAPOR.md + sürüm kaydı")
    q.add_argument("--kabul")
    alt.add_parser("durum", help="dosya × durum tablosu")

    args = ap.parse_args(argv)
    try:
        proje = Proje(Path(args.proje), args.ad)
        proje.durum_dizini.mkdir(parents=True, exist_ok=True)
        b = Baglam(proje, Klon(Path(args.klon)))
        return {
            "onkontrol": komut_onkontrol, "onay": komut_onay, "plan": komut_plan,
            "uygula": komut_uygula, "oneri": komut_oneri, "isaretle": komut_isaretle,
            "geri-al": komut_geri_al, "kapanis": komut_kapanis, "durum": komut_durum,
        }[args.altkomut](b, args)
    except Dur as e:
        print(f"DUR: {e}", file=sys.stderr)
        return e.kod


if __name__ == "__main__":
    raise SystemExit(main())
