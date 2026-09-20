# -*- coding: utf-8 -*-
"""`guncelle/kartlar/**` + `GUNCELLE.md` — vaka/sınıf kartlarının TAMLIĞI (TASARIM §5, P3 kabul ölçütü).

KABUL ÖLÇÜTÜ: **plana girebilen her vaka kodunun bir kartı vardır.** Kartı `scripts/guncelle.py kart
<KOD>` basar; kart yoksa komut çıkış 2 verir ve ajanın o vakada izleyeceği yordam YOKTUR.

Bu dosyanın değişmezi: **kart listesi burada ELLE YAZILMAZ.** Liste iki kaynaktan türetilir —
`scripts/guncelle.py` sabitleri (hangi kodlar plana girer) ve `guncelle/harita.json` (hangi üst
sınıflar var). Elle yazılan liste motor değişince sessizce bayatlar; `KartListesiTuretilmis` bu
dosyanın kendi kaynağını tarayarak o sapmayı kırmızıya çevirir.

KAPSAM — bakılanlar (2026-09-18'de eklenenler): kart metninin MOTORLA çelişmemesi (`KartMotorSozlesmesi`
— özel adımın koşulsuzluğu · adım-11 reçetesinin yapısal kartlarda durması · kapat-aç yönergesinin alt
sınıfa bağlanması · ortam-değişkeni öneklerinin PowerShell'de koşabilirliği) · kapsam tablosunun 4.
sütununun `ozel_adim`'a bağlanması · giriş beyanının commit atan komutları ADIYLA anması · `oneri`nin
akış tablosunda hiç emredilmemesi.
KAPSAM — bakılmayanlar: kartların İÇERİĞİNİN doğruluğu/anlaşılırlığı (doküman incelemesi işi; burada
yalnız iskelet başlıkları, başlık satırı ve asgari gövde ölçülür) · kartlarda anılan komutların canlı
koşumu (PowerShell öneki DIŞINDA — o elle koşuldu, 2026-09-18) · kapsam tablosunun `yok` kategorili
satırlarındaki 4. sütun (motorda karşılığı yok) · `harita.json` içeriğinin doğruluğu ve `guncelle.py`
motor kodunun doğruluğu (ayrı yüzeyler) · `kart` komutunun canlı koşumu
(kartı `origin/main`'den okur, yerel çalışma ağacından DEĞİL — dal merge edilene kadar mekanik olarak
ölçülemez; `tests/test_guncelle.py` sahte public depo ile o kablolamayı ayrıca ölçer) · GUNCELLE.md
metninin modele fiilen talimat olması (`_lab`, P9) · Linux/macOS.
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

BURASI = Path(__file__).resolve().parent
AXET_HOME = BURASI.parent

# Yayın anında ÜRETİLEN, kaynak depoda bulunmayan yollar. Tüketicinin klonunda VARDIR
# (yayın aracı yazar); kaynak depoda yoktur, çünkü hükmü yayın koşumu üretir.
YAYINDA_URETILEN = ("guncelle/ci-durum.json",)


def eksik_yollar(kaynaklar: dict, muafiyet: tuple | None = None) -> list:
    """Backtick içinde anılan repo yollarından diskte OLMAYANLAR. `## Örnek` bölümü ölçülmez.

    `muafiyet` yalnız kontrol grubu içindir: muafiyeti KAPATIP aynı girdinin yakalandığını
    göstermek, muafiyetin gerçekten bir iş yaptığını kanıtlar."""
    muaf = YAYINDA_URETILEN if muafiyet is None else muafiyet
    eksik = []
    for ad, metin in kaynaklar.items():
        metin = re.sub(r"^## Örnek\b.*?(?=^## |\Z)", "", metin, flags=re.M | re.S)
        for aday in re.findall(r"`([A-Za-z0-9_./-]+\.(?:py|md|json))`", metin):
            if aday.startswith(".axet-guncelleme") or "/" not in aday:
                continue  # koşum anında üretilen yol · örnek dosya adı (dizinsiz)
            if (AXET_HOME / aday).exists():
                continue
            if aday in muaf:
                # Muafiyet KENDİ KENDİNİ SINIRLAR: yol VARSA bir üstteki dal zaten geçirdi,
                # yani bu dal ancak yol gerçekten yokken çalışır. (Z17: gerekçesinden GENİŞ
                # yazılan muafiyet kör noktaya döner.)
                continue
            eksik.append(f"{ad}: {aday}")
    return eksik


if str(AXET_HOME / "scripts") not in sys.path:
    sys.path.insert(0, str(AXET_HOME / "scripts"))

import guncelle  # noqa: E402  (motor sözleşmesinin KENDİSİ kaynaktır)

MOTOR_KAYNAK = (AXET_HOME / "scripts" / "guncelle.py").read_text(encoding="utf-8")

# Bu dosyada geçmesine izin verilen TEK vaka-kodu dizgesi. Gerekçe (ölçüldü, guncelle.py
# `dosya_vakasi`): `vaka_kodu()` ara sonuç olarak bu kodu döndürür ve `dosya_vakasi` onu DAİMA
# alt koda (temiz/çakışmalı/eşik/ikili) çevirir; plana hiç yazılmaz, dolayısıyla kartı da yoktur.
ARA_KOD = "V" + "4"


def kart_dizini() -> Path:
    """Kart klasörünü MOTORDAN türet: `komut_kart` hangi yoldan okuyorsa kartlar oradadır."""
    m = re.search(r"origin/main:([\w\-/]+)/\{args\.kod\}\.md", MOTOR_KAYNAK)
    assert m, "guncelle.py `komut_kart` içindeki kart yolu bulunamadı (sözleşme değişmiş olabilir)"
    return AXET_HOME / m.group(1)


def sinif_kart_oneki() -> str:
    """Sınıf kartı adlandırmasını motorun KENDİ fonksiyonundan ölç (tahmin etme)."""
    kartlar = guncelle._kart_listesi({"vaka": "?"}, {"ust_sinif": "ORNEK"})
    aday = [k for k in kartlar if k.endswith("ORNEK")]
    assert aday, f"_kart_listesi sınıf kartı üretmedi: {kartlar}"
    return aday[0][: -len("ORNEK")]


def harita() -> dict:
    return json.loads((AXET_HOME / "guncelle" / "harita.json").read_text(encoding="utf-8"))


def beklenen_vaka_kartlari() -> set[str]:
    """Plana GİREN kodlar = otomatik uygulananlar ∪ yargı isteyenler (guncelle.py sabitleri)."""
    return set(guncelle.OTOMATIK_VAKALAR) | set(guncelle.YARGI_VAKALARI)


def beklenen_sinif_kartlari() -> set[str]:
    onek = sinif_kart_oneki()
    return {onek + u["id"] for u in harita()["ust_siniflar"]}


VAKA_BASLIKLARI = ("## Ne demek", "## Neden", "## Adımlar", "## Örnek", "## Beklenen çıktı", "## DUR")
SINIF_BASLIKLARI = ("## Tetik", "## Zorunlu ek adımlar", "## DUR")

ADIMLAR_BASLIGI = SINIF_BASLIKLARI[1]

# Akış adım 11 reçetesinin (hüküm karşılaştırması) TAŞIYICI izleri. Reçete silinirse bu izler de
# gider; tetik artık "hüküm" alt dizgesine bağlı DEĞİL — ölçüldü (mutasyon, 2026-09-18): Türkçede
# son derece doğal bir yeniden yazım ("hükmü karşılaştır") o alt dizgeyi içermez ve gate hiç
# uyanmadan reçetenin tamamı silinebiliyordu.
ADIM11_RECETE_IZLERI = (
    "Kontrol grubu kur",  # PATTERN #19: aynı girdi, önce ve sonra
    "run_review.py",      # zincir dosyası: PASS / WARNING / BLOCKER karşılaştırması
    "run_tests.py",       # fixture'ı olan validator: good/bad tarafları
    "[İHLAL]",            # fixture'ı olmayan validator: çıkış kodu + ihlal satırları
)

# Koşul bildiren Türkçe biçimler. `\w+[dt][iıuü]yse` → "eklendiyse", "değiştiyse", "geldiyse"…
KOSUL_IZLERI = (r"\w+[dt][iıuü]yse\b", r"\byalnız\w*\b", r"\bsadece\b",
                r"\bgerekirse\b", r"\bvarsa\b", r"\bise\b", r"\bdeğilse\b")

# POSIX ortam-değişkeni öneki (`VAR=deger komut`). Bu ev Windows/PowerShell-önceliklidir ve
# PowerShell bunu "The term 'VAR=deger' is not recognized" ile reddeder (ölçüldü 2026-09-18).
POSIX_ENV_ONEKI = re.compile(r"`[A-Z][A-Z0-9_]*=[^`]*`")


def bolum(metin: str, baslik: str) -> str:
    """`## <baslik>` bölümünün gövdesi (bir sonraki `## ` başlığına kadar); yoksa boş dizge."""
    if baslik not in metin:
        return ""
    return metin.split(baslik, 1)[1].split("\n## ", 1)[0]


def cumleler(metin: str) -> list[str]:
    """Metni cümlelere böl. Dosya uzantısındaki nokta cümle sonu SAYILMAZ (maskelenir)."""
    maske = re.sub(r"\.(py|md|json|ps1|cmd|txt|sh|ya?ml|diff)\b", "\x00\\1", metin)
    return [p.replace("\x00", ".").strip()
            for p in re.split(r"(?<=[.!?])\s+", maske) if p.strip()]


def _sabit_globlar(siniflar: list[dict]) -> set[str]:
    """Joker içermeyen glob'lar + dosya adları — "koşul sınıf üyeliğidir" muafiyetinin kanıtı."""
    out: set[str] = set()
    for s in siniflar:
        for g in s.get("glob", []):
            if any(j in g for j in "*?["):
                continue
            out.add(g)
            out.add(g.rsplit("/", 1)[-1])
    return out


def kosul_sinif_uyeligine_baglanmis(cumle: str, siniflar: list[dict]) -> bool:
    """Cümledeki koşul motorun GÖRDÜĞÜ bir şeye mi bağlı?

    Motor kalem kurarken yalnız şunu bilir: bu alt sınıfın bir dosyası planda mı (`sinif_bul`
    → `ozel_adim` / `etkin`). Dolayısıyla koşul ancak alt sınıf ADIYLA ya da o alt sınıfın
    sabit glob'uyla kurulursa motorla çelişmez; başka her koşul motorun okumadığı bir şeydir.
    """
    return (any(s["sinif"] in cumle for s in siniflar)
            or any(g in cumle for g in _sabit_globlar(siniflar)))


def kosullu_mu(cumle: str) -> list[str]:
    return [k for k in KOSUL_IZLERI if re.search(k, cumle, re.I)]


def ust_sinif_kartlari() -> dict[str, tuple[Path, list[dict]]]:
    """Üst sınıf id → (kart yolu, alt sınıf kayıtları) — harita.json'dan türetilir."""
    onek, h = sinif_kart_oneki(), harita()
    return {u["id"]: (kart_dizini() / f"{onek}{u['id']}.md",
                      [s for s in h["siniflar"] if s["ust_sinif"] == u["id"]])
            for u in h["ust_siniflar"]}


def birlesik_oneri_ureten_vakalar() -> set[str]:
    """Ajanın KENDİ birleştirmesiyle yüzleştiği yargı vaka kodları — MOTORDAN ölçülür.

    `dosya_vakasi`, `birlestir()` çağrısından sonra alt kodu atar. Eşik dalı (`ESIK_…`
    sabitleriyle kurulan koşul) birleştirmeyi açıkça REDDEDER ⇒ o kod dışarıda kalır; ikili
    dal zaten `birlestir()`den öncedir. Geriye birleşik önerinin ajana sunulduğu kodlar kalır —
    akış adım 11 (hüküm karşılaştırması) tam olarak orada doğar.
    """
    govde = MOTOR_KAYNAK.split("\ndef dosya_vakasi", 1)[1].split("\ndef ", 1)[0]
    bolge = govde[govde.index("birlestir("):]
    kosul, out = "", set()
    for satir in bolge.splitlines():
        s = satir.strip()
        if re.match(r"^(if|elif|else)\b.*:$", s):
            kosul = s
        m = re.match(r'^alt\s*=\s*"([^"]+)"', s)
        if m and "ESIK_" not in kosul:
            out.add(m.group(1))
    assert out, "motorda birleşme alt kodu bulunamadı (sözleşme değişmiş olabilir)"
    return out


def adim11_recetesi_zorunlu_kartlar() -> set[str]:
    """Adım-11 reçetesini TAŞIMASI zorunlu kart adları — tamamı YAPIDAN türetilir.

    ① Sınıf kartı: akış adım 11'in ölçütü birebir "dosyanın sınıfı `validator` ya da
       `kritik_yol`" ⇒ `validator` alt sınıfının bağlı olduğu üst sınıfın kartı (harita.json).
    ② Vaka kartları: `birlesik_oneri_ureten_vakalar()` (motor kaynağından).
    """
    h = harita()
    ust = {s["ust_sinif"] for s in h["siniflar"] if s["sinif"] == "validator"}
    assert ust, "harita.json'da `validator` alt sınıfı yok (sözleşme değişmiş olabilir)"
    return {sinif_kart_oneki() + u for u in ust} | birlesik_oneri_ureten_vakalar()


class KartTamligi(unittest.TestCase):
    def setUp(self) -> None:
        self.dizin = kart_dizini()

    def test_dizin_var(self) -> None:
        self.assertTrue(self.dizin.is_dir(), f"kart klasörü yok: {self.dizin}")

    def test_her_plan_vaka_kodunun_karti_var(self) -> None:
        """KABUL ÖLÇÜTÜ. Liste guncelle.py sabitlerinden türetilir."""
        eksik = sorted(k for k in beklenen_vaka_kartlari()
                       if not (self.dizin / f"{k}.md").is_file())
        self.assertEqual([], eksik, f"kartı olmayan vaka kodları: {eksik}")

    def test_islemsiz_kodlarin_karti_yok(self) -> None:
        """TASARIM §5: işlem yok ⇒ 'Kart yok; plan bu kodları yalnız sayar'."""
        fazla = sorted(k for k in guncelle.ISLEMSIZ_VAKALAR if (self.dizin / f"{k}.md").is_file())
        self.assertEqual([], fazla, f"işlemsiz kodlara kart yazılmış (§5 ile çelişir): {fazla}")

    def test_her_ust_sinifin_karti_var(self) -> None:
        eksik = sorted(k for k in beklenen_sinif_kartlari()
                       if not (self.dizin / f"{k}.md").is_file())
        self.assertEqual([], eksik, f"kartı olmayan üst sınıflar: {eksik}")

    def test_yetim_kart_yok(self) -> None:
        """Klasörde ne varsa ya bir plan vaka kodudur ya bir üst sınıftır."""
        beklenen = beklenen_vaka_kartlari() | beklenen_sinif_kartlari()
        yetim = sorted(p.stem for p in self.dizin.glob("*.md") if p.stem not in beklenen)
        self.assertEqual([], yetim, f"hiçbir koda/sınıfa bağlanmayan kart: {yetim}")

    def test_kart_iskeleti(self) -> None:
        """Her kart: `# <ad> — <başlık>` ilk satırı + §5 iskelet başlıkları."""
        hatalar: list[str] = []
        for ad in sorted(beklenen_vaka_kartlari() | beklenen_sinif_kartlari()):
            p = self.dizin / f"{ad}.md"
            if not p.is_file():
                continue  # eksiklik ayrı testin işi
            satirlar = p.read_text(encoding="utf-8").splitlines()
            ilk = satirlar[0] if satirlar else ""
            if not re.match(rf"^# {re.escape(ad)} — \S.*", ilk):
                hatalar.append(f"{p.name}: ilk satır `# {ad} — <başlık>` değil: {ilk!r}")
            govde = "\n".join(satirlar)
            beklenen = SINIF_BASLIKLARI if ad.startswith(sinif_kart_oneki()) else VAKA_BASLIKLARI
            for b in beklenen:
                if b not in govde:
                    hatalar.append(f"{p.name}: eksik bölüm {b!r}")
        self.assertEqual([], hatalar, "kart iskeleti bozuk:\n" + "\n".join(hatalar))

    def test_kart_bos_degil(self) -> None:
        kisa = sorted(p.name for p in self.dizin.glob("*.md")
                      if len(p.read_text(encoding="utf-8").strip()) < 200)
        self.assertEqual([], kisa, f"gövdesi yok denecek kadar kısa kart: {kisa}")


class KartListesiTuretilmis(unittest.TestCase):
    """MUTASYON KALKANI: bu test dosyası kart listesini elle sabitlerse kırmızı olur."""

    def test_kart_listesi_elle_sabitlenmemis(self) -> None:
        kaynak = Path(__file__).read_text(encoding="utf-8")
        kodlar = set(re.findall(r"""["'](V[0-9][A-Za-z0-9+]*)["']""", kaynak))
        self.assertEqual(
            set(), kodlar - {ARA_KOD},
            "vaka kodu bu test dosyasına ELLE yazılmış: %s — liste guncelle.py sabitlerinden "
            "TÜRETİLMELİ (elle liste motor değişince sessizce bayatlar)."
            % sorted(kodlar - {ARA_KOD}))
        sinif_kodlari = set(re.findall(r"""["'](sinif-[a-z0-9\-]+)["']""", kaynak))
        self.assertEqual(set(), sinif_kodlari,
                         "sınıf kartı adı elle yazılmış: %s — harita.json'dan türetilmeli."
                         % sorted(sinif_kodlari))

    def test_ara_kodun_karti_yok(self) -> None:
        """Ara kod plana hiç yazılmaz (dosya_vakasi onu daima alt koda çevirir) ⇒ kartı da olmaz."""
        self.assertNotIn(ARA_KOD, beklenen_vaka_kartlari())
        self.assertFalse((kart_dizini() / f"{ARA_KOD}.md").is_file())


class GuncelleMd(unittest.TestCase):
    """`GUNCELLE.md` — ajanın akış belgesi; özet tablosu haritadan türer (TASARIM §7 + §3)."""

    def setUp(self) -> None:
        self.yol = AXET_HOME / "GUNCELLE.md"
        if not self.yol.is_file():
            self.fail(f"GUNCELLE.md yok: {self.yol}")
        self.metin = self.yol.read_text(encoding="utf-8")

    def test_tum_alt_komutlar_anilir(self) -> None:
        komutlar = set(re.findall(r'add_parser\(\s*"([a-z\-]+)"', MOTOR_KAYNAK))
        self.assertTrue(komutlar, "guncelle.py'de alt komut bulunamadı (regex bayat?)")
        eksik = sorted(k for k in komutlar if f"`{k}`" not in self.metin
                       and f"guncelle.py {k}" not in self.metin)
        self.assertEqual([], eksik, f"GUNCELLE.md'de anılmayan alt komutlar: {eksik}")

    def test_tum_ust_siniflar_anilir(self) -> None:
        eksik = sorted(u["id"] for u in harita()["ust_siniflar"] if u["id"] not in self.metin)
        self.assertEqual([], eksik, f"GUNCELLE.md özet tablosunda eksik üst sınıflar: {eksik}")

    def test_kart_dizini_anilir(self) -> None:
        self.assertIn(kart_dizini().name, self.metin)


def akis_satirlari() -> dict[str, str]:
    """`GUNCELLE.md` akış tablosunun satırları: adım numarası → satırın tam metni."""
    metin = (AXET_HOME / "GUNCELLE.md").read_text(encoding="utf-8")
    return {m.group(1): m.group(0)
            for m in re.finditer(r"^\|\s*(\d+)\s*\|.*$", metin, re.M)}


def commit_atan_komutlar() -> set[str]:
    """MOTORDAN ölç: hangi alt komutun gövdesi `git commit` çalıştırıyor?"""
    out = set()
    for blok in MOTOR_KAYNAK.split("\ndef komut_")[1:]:
        ad = blok.split("(", 1)[0].strip().replace("_", "-")
        govde = blok.split("\ndef ", 1)[0]
        if re.search(r'git\(\s*"commit"', govde):
            out.add(ad)
    return out


class AkisSozlesmesi(unittest.TestCase):
    """`GUNCELLE.md` akış tablosunun kartlarla ve motorla çelişmediğini ölçer.

    KAPSAM — bakılanlar: adım satırlarının hangi komutu emrettiği · commit beyanı ·
    yeniden başlatma ölçütünün adının yazılı olması. Bakılmayanlar: ajanın metni fiilen
    izlemesi (`_lab`, P9) · adım sırasının doğruluğu.
    """

    def setUp(self) -> None:
        self.satirlar = akis_satirlari()
        self.metin = (AXET_HOME / "GUNCELLE.md").read_text(encoding="utf-8")
        if not self.satirlar:
            self.fail("GUNCELLE.md'de akış tablosu satırı bulunamadı")

    def _adim(self, no: str) -> str:
        self.assertIn(no, self.satirlar, f"akış tablosunda {no}. adım satırı yok")
        return self.satirlar[no]

    def test_yargi_adimi_komut_secimini_karta_birakir(self) -> None:
        """Yargı adımı `oneri`yi KOŞULSUZ emretmez: hangi komutun koşacağını kart söyler.

        Gerekçe (ölçüldü): `oneri` taban gerektirir ve taban yoksa DUR (çıkış 2); ayrıca
        silme/ad-çakışması vakalarında birleştirme önerisi ÜRETMEK yanlış yönlendirir.
        Yargı vakalarının hepsi `oneri` istemez — kart isteyenlerde onu kendi 1. adımında çağırır.
        """
        yargi = [s for n, s in self.satirlar.items()
                 if "kart" in s and "isaretle" in s]
        self.assertTrue(yargi, "akış tablosunda `kart` + `isaretle` içeren adım satırı yok")
        hatali = [s for s in yargi if "oneri" in s]
        self.assertEqual(
            [], hatali,
            "akış adımı `oneri`yi zincire koşulsuz koymuş — komut kararı KARTA aittir: %s" % hatali)

    def test_oneri_akis_tablosunun_hicbir_adiminda_emredilmez(self) -> None:
        """`oneri` akış tablosunun HİÇBİR satırında emredilmez — yeri KARTIN 1. adımıdır.

        Üstteki test yalnız yargı satırına (`kart` + `isaretle`) bakıyordu; ölçüldü
        (mutasyon MÖ2, 2026-09-18): `oneri` OTOMATİK adıma konunca o satırda "isaretle"
        geçmediği için test hiç bakmadı ve YEŞİL kaldı. Oysa belge bunu kendi metninde
        şöyle bağlar: "Hangi komutun koşacağına KART karar verir, akış tablosu değil" —
        ve `oneri` silme/ad-çakışması/tabansız vakalarda ÇALIŞTIRILMAMALIDIR.
        """
        komut = "oneri"
        self.assertIn(komut, MOTOR_KAYNAK, "motorda `oneri` alt komutu yok (sözleşme değişmiş?)")
        hatali = [f"adım {no}: {s}" for no, s in sorted(self.satirlar.items())
                  if re.search(rf"guncelle\.py\s+{komut}\b|`{komut}`", s)]
        self.assertEqual(
            [], hatali,
            "akış tablosu `oneri`yi emrediyor — komut kararı KARTA aittir (V6d/V7/VTB "
            "vakalarında bu komut yanıltıcı öneri ya da yanlış vaka etiketi üretir): %s"
            % hatali)

    def test_otomatik_adiminda_da_kart_okunur(self) -> None:
        """`uygula --otomatik` satırı da kart okumayı emreder (sınıf kartlarının ek adımları)."""
        otomatik = [s for s in self.satirlar.values() if "--otomatik" in s]
        self.assertTrue(otomatik, "akış tablosunda `uygula --otomatik` satırı yok")
        eksik = [s for s in otomatik if "kart" not in s]
        self.assertEqual(
            [], eksik,
            "otomatik uygulama adımı kart okumayı emretmiyor ⇒ sınıf kartının zorunlu "
            "ek adımları sessizce atlanır: %s" % eksik)

    def test_commit_atan_her_komut_beyan_edilmis(self) -> None:
        """Motorda `git commit` çalıştıran her alt komutun satırı bunu SÖYLER (klonda commit oluşur)."""
        komutlar = commit_atan_komutlar()
        self.assertTrue(komutlar, "motorda commit atan alt komut bulunamadı (regex bayat?)")
        eksik = []
        for ad in sorted(komutlar):
            satir = next((s for s in self.satirlar.values() if ad in s), None)
            if satir is None or "commit" not in satir.lower():
                eksik.append(ad)
        self.assertEqual([], eksik,
                         f"akış tablosunda commit'i beyan etmeyen komutlar: {eksik}")
        # Giriş beyanı: yalnız "commit" sözcüğünü aramak YETMEZ — ölçüldü (mutasyon MÖ4,
        # 2026-09-18): beyanın yerine konan YANLIŞ bir cümle ("Hiçbir şeyi commit etmez.")
        # testi yeşil bırakıyordu. Beyanın motorla bağını kuran şey, commit ATAN alt
        # komutların ADININ commit cümlesinde geçmesidir.
        giris = self.metin.split("## Akış")[0]
        beyansiz = [ad for ad in sorted(komutlar)
                    if not any(ad in c and "commit" in c.lower() for c in cumleler(giris))]
        self.assertEqual(
            [], beyansiz,
            "'ne yapar / ne yapmaz' bölümü klonda commit atan alt komutu adıyla beyan "
            f"etmiyor: {beyansiz} — kullanıcıya BAŞTAN söylenecek şey budur")

    def test_yeniden_baslatma_olcutu_adiyla_yazili(self) -> None:
        """"Kapat-aç gerekli mi" sorusunun ölçütü planın alanıdır; adı belgede geçmeli."""
        alan = "yeniden_baslat"
        self.assertIn(alan, MOTOR_KAYNAK, "motorda `yeniden_baslat` alanı yok (sözleşme değişmiş?)")
        self.assertIn(alan, self.metin,
                      "GUNCELLE.md 'gerekiyorsa kapat-aç' diyor ama ölçütün adını "
                      f"(`{alan}`) yazmıyor — ajan tahmin eder")


class KartIddiaTutarliligi(unittest.TestCase):
    """Kart metinlerinin diskteki ve motordaki gerçekle çelişmediğini ölçer.

    KAPSAM — bakılanlar: zorunlu kılınan ölçümün somut komut içermesi · anılan repo
    yollarının var olması · ön kontrolün blokladığı bir durumun vaka sebebi sayılmaması.
    Bakılmayanlar: komutun gerçekten o sonucu ürettiği (canlı koşum yok).
    """

    def setUp(self) -> None:
        self.kartlar = {p.name: p.read_text(encoding="utf-8")
                        for p in sorted(kart_dizini().glob("*.md"))}
        self.assertTrue(self.kartlar, "hiç kart yok")

    def test_zorunlu_hukum_karsilastirmasi_somut_komut_verir(self) -> None:
        """"Hüküm karşılaştırması ZORUNLU" diyen kart, KOŞULACAK komutu da verir.

        "Somut komut" = backtick içinde `python <yol>.py …` biçiminde KOŞULABİLİR bir satır.
        Çıplak dosya adı (`run_review.py`) sayılmaz — ölçüldü (mutasyon M11, 2026-09-18):
        gevşek biçim, gerçek komutlar silindiği hâlde testi yeşil bırakıyordu.
        """
        eksik = []
        for ad, metin in self.kartlar.items():
            if "hüküm" not in metin.lower():
                continue
            komutlar = re.findall(r"`(python\s[^`]*\.py[^`]*)`", metin)
            if not any("run_review.py" in k or "run_tests.py" in k for k in komutlar):
                eksik.append(ad)
        self.assertEqual(
            [], eksik,
            "hüküm karşılaştırmasını zorunlu kılan ama komutu yazmayan kartlar: %s — "
            "ölçütsüz zorunluluk 'baktım, fark yok' ile geçilir" % eksik)

    def test_anilan_repo_yollari_diskte_var(self) -> None:
        """Kartların İŞLEM bölümlerinde backtick içinde anılan repo yolları gerçekten var.

        `## Örnek` bölümü ÖLÇÜLMEZ: örnekler kurgusal bir yayını anlatır (`docs/tasinacak.md`
        gibi) ve var olmaları beklenmez — ölçülen şey, ajanın KOŞACAĞI/AÇACAĞI yolların
        gerçekliğidir.
        """
        kaynaklar = dict(self.kartlar)
        kaynaklar["GUNCELLE.md"] = (AXET_HOME / "GUNCELLE.md").read_text(encoding="utf-8")
        eksik = eksik_yollar(kaynaklar)
        self.assertEqual([], eksik, f"diskte olmayan yol anılmış: {eksik}")

    def test_KONTROL_uretilen_muafiyeti_baska_yolu_KAPSAMAZ(self) -> None:
        """Kontrol grubu: muafiyet YAYINDA_URETILEN ile SINIRLI mı, yoksa "üretilmiş gibi
        duran" her yolu mu yutuyor? Üçüncü iddia muafiyeti KAPATIP aynı girdinin yakalandığını
        ölçer — o olmadan bu test, muafiyet tümden genişlese bile yeşil kalırdı."""
        self.assertEqual([], eksik_yollar({"sahte": "`guncelle/ci-durum.json`"}),
                         "muaf yol yakalanmamalıydı")
        self.assertEqual(["sahte: guncelle/olmayan-uretilmis.json"],
                         eksik_yollar({"sahte": "`guncelle/olmayan-uretilmis.json`"}),
                         "muafiyet listede OLMAYAN yolu da yutuyor — kör nokta (Z17)")
        self.assertEqual(["sahte: guncelle/ci-durum.json"],
                         eksik_yollar({"sahte": "`guncelle/ci-durum.json`"}, muafiyet=()),
                         "muafiyetsiz kolda yakalanmıyor ⇒ test hiçbir şey ölçmüyor")

    def test_onkontrolun_durdurdugu_durum_vaka_sebebi_gosterilmez(self) -> None:
        """Ön kontrol sığ klonu DURDURUYORSA, hiçbir kart onu kendi vakasının sebebi sayamaz."""
        if "is-shallow-repository" not in MOTOR_KAYNAK:
            self.skipTest("motor sığ klon kontrolü yapmıyor — iddia ölçülemez")
        suclu = sorted(ad for ad, metin in self.kartlar.items() if "sığ klon" in metin)
        self.assertEqual(
            [], suclu,
            "ön kontrol (`onkontrol`) sığ klonda çıkış 2 ile durdurur ⇒ o durum plana hiç "
            "ulaşmaz; kart onu yaşayan bir sebep gibi anlatmamalı: %s" % suclu)


class KartMotorSozlesmesi(unittest.TestCase):
    """Kart METNİ ile motorun ÖLÇÜLMÜŞ davranışı arasındaki çelişkileri yakalar.

    Neden ayrı sınıf: `KartIddiaTutarliligi` kartın kendi içindeki iddiayı ölçer; burada
    ölçülen şey kartın MOTORLA çelişip çelişmediğidir — ajan karta uyup motorun zorunlu
    tuttuğu bir adımı atlarsa `kapanis` 0 dönmez ve sebebini kartta BULAMAZ.

    KAPSAM — bakılanlar: ① özel adımın koşulsuzluğu ② adım-11 reçetesinin yapısal olarak
    zorunlu kartlarda durması ③ yeniden başlatma yönergesinin alt sınıfa bağlanması
    ④ ortam değişkeni öneklerinin PowerShell'de koşabilirliği. Bakılmayanlar: kart
    metninin anlaşılırlığı · komutların canlı koşumu · `harita.json` içeriğinin doğruluğu
    (P1 yüzeyi) · motor kodunun doğruluğu (P2 yüzeyi).
    """

    def setUp(self) -> None:
        self.kartlar = ust_sinif_kartlari()

    def _adim_cumleleri(self, yol: Path) -> list[str]:
        return cumleler(bolum(yol.read_text(encoding="utf-8"), ADIMLAR_BASLIGI))

    def test_ozel_adim_kosulsuz_anlatilir(self) -> None:
        """`ozel_adim`'ı olan sınıfın kartı o adımı KOŞULSUZ emreder.

        Motorda ölçüldü (`scripts/guncelle.py`, kalem kurulumu): sınıfın `ozel_adim` alanı
        doluysa adım plana KOŞULSUZ girer; `kapanis` onu şart koşar ve koşmadıysa
        "özel adım koşmadı" yazıp çıkış 1 verir. Kart, motorun okumadığı bir koşul
        ("… eklendiyse", "yalnızca …") koyarsa ajan adımı atlar ve kapanışı kilitler.

        Tek meşru koşul, motorun GÖRDÜĞÜ koşuldur: hangi alt sınıf planda. O yüzden alt
        sınıf adını (ya da alt sınıfın sabit glob'unu) anan cümle muaftır.
        """
        hatalar = []
        for uid, (yol, siniflar) in self.kartlar.items():
            ozelli = [s for s in siniflar if s.get("ozel_adim")]
            if not ozelli or not yol.is_file():
                continue
            cs = self._adim_cumleleri(yol)
            cagri = [c for c in cs if "ozel-adim" in c]
            if not cagri:
                hatalar.append(f"{yol.name}: `ozel-adim` çağrısı '{ADIMLAR_BASLIGI}' içinde hiç geçmiyor")
                continue
            for c in cagri:
                izler = kosullu_mu(c)
                if izler and not kosul_sinif_uyeligine_baglanmis(c, ozelli):
                    hatalar.append(f"{yol.name}: özel adım koşula bağlanmış {izler}: {c!r}")
        self.assertEqual(
            [], hatalar,
            "kart özel adımı koşullu anlatıyor ama motor onu KOŞULSUZ listeliyor "
            "(kapanış şart koşar):\n" + "\n".join(hatalar))

    def test_adim11_recetesi_yapisal_kartlarda_duruyor(self) -> None:
        """Hüküm karşılaştırması reçetesi, YAPIDAN türetilen kartların hepsinde durur.

        Tetik metin dizgisi DEĞİL yapıdır: sınıf kartı harita.json'daki `validator` alt
        sınıfından, vaka kartları motorun birleşme dallarından gelir. Böylece kartın kendi
        sözcüklerini değiştirmek (ör. "hüküm" → "hükmü") tetiği KAÇIRAMAZ.
        """
        eksik = []
        for ad in sorted(adim11_recetesi_zorunlu_kartlar()):
            p = kart_dizini() / f"{ad}.md"
            if not p.is_file():
                eksik.append(f"{ad}.md: kart yok")
                continue
            metin = p.read_text(encoding="utf-8")
            yok = [iz for iz in ADIM11_RECETE_IZLERI if iz not in metin]
            if yok:
                eksik.append(f"{p.name}: reçetenin eksik parçaları {yok}")
        self.assertEqual(
            [], eksik,
            "akış adım 11 (hüküm karşılaştırması) reçetesi eksik — ajan 'baktım, fark yok' "
            "ile geçer:\n" + "\n".join(eksik))

    def test_yeniden_baslatma_yonergesi_alt_sinifa_bagli(self) -> None:
        """Alt sınıfların `etkin` değeri FARKLIYSA kart kapat-aç'ı koşulsuz emredemez.

        `etkin = null` olan alt sınıfta "ayrı etkinleşme anı yok"tur; kartın o alt sınıf
        için de kapat-aç istemesi kullanıcıya gereksiz bir kesinti yaptırır ve kartın kendi
        kapsam tablosuyla çelişir.
        """
        hatalar = []
        for uid, (yol, siniflar) in self.kartlar.items():
            if len({str(s["etkin"]) for s in siniflar}) < 2 or not yol.is_file():
                continue
            for c in self._adim_cumleleri(yol):
                if not re.search(r"kapat|yeni oturum", c, re.I):
                    continue
                if not kosul_sinif_uyeligine_baglanmis(c, siniflar):
                    hatalar.append(f"{yol.name}: kapat-aç alt sınıfa bağlanmamış: {c!r}")
        self.assertEqual(
            [], hatalar,
            "kartın `etkin` değerleri alt sınıfa göre değişiyor ama yeniden başlatma "
            "yönergesi koşulsuz:\n" + "\n".join(hatalar))

    def test_recete_komutlari_powershell_de_kosar(self) -> None:
        """Hiçbir kart POSIX ortam-değişkeni öneki (`VAR=deger komut`) vermez.

        Ölçüldü 2026-09-18: `powershell -NoProfile -Command "AXET_SAP_PROJECT_DIR=C:\\tmp
        python --version"` → *The term 'AXET_SAP_PROJECT_DIR=C:\\tmp' is not recognized*.
        Bu ev PowerShell-önceliklidir ⇒ o önek ajana kendi kabuğunda KOŞMAYAN bir komut verir.
        Doğrusu ayrı satır: `$env:VAR = '<deger>'`.
        """
        kaynaklar = {p.name: p.read_text(encoding="utf-8")
                     for p in sorted(kart_dizini().glob("*.md"))}
        kaynaklar["GUNCELLE.md"] = (AXET_HOME / "GUNCELLE.md").read_text(encoding="utf-8")
        suclu = [f"{ad}: {m.group(0)}" for ad, metin in kaynaklar.items()
                 for m in POSIX_ENV_ONEKI.finditer(metin)]
        self.assertEqual(
            [], suclu,
            "POSIX ortam-değişkeni öneki PowerShell'de koşmaz — `$env:VAR = '…'` ayrı "
            "satır olmalı: %s" % suclu)


class SinifKartiKapsamTablosu(unittest.TestCase):
    """Her sınıf kartı, kapsadığı alt sınıfları harita.json'daki GERÇEK değerleriyle listeler.

    Neden tablo: sınıf kartının düz metni kolayca aşırı genelleşir ("install.py koş",
    "kapat-aç") oysa üst sınıfın bazı alt sınıflarında o adım YOKTUR. Tablo, iddiayı
    alt sınıf başına bağlar ve harita değişince bu test bayatlığı kırmızıya çevirir.

    KAPSAM — bakılanlar: satır kümesi + `etkin` + özel adım KATEGORİSİ + **`komut`/`manuel`
    satırlarında 4. sütun** ("Ne demek" = koşulacak adımın insan-okur hâli; harita.json'daki
    `ozel_adim` metnine bağlanır). Bakılmayanlar: `yok` satırlarının 4. sütunu (motorda
    karşılığı olan bir metin değil, serbest etkinleşme açıklaması) · kartın düz metninin
    tabloyla uyumu (onu `KartMotorSozlesmesi` ayrıca ölçer).

    4. sütun neden bağlandı (ölçüldü, mutasyon MÖ9 2026-09-18): sütun serbest bırakılınca
    oraya yazılan **tehlikeli bir komut** (`doctor.py --hepsini-sil` gibi) takımı YEŞİL
    bırakıyordu — oysa ajanın koşacağı şeyi anlattığı yer tam da bu sütun.
    """

    BASLIK = "## Kapsam (harita.json)"

    def _ozel_kategori(self, ozel) -> str:
        """Motorun `ozel-adim` kuralı: komut içeriyorsa koşar, içermiyorsa MANUEL basar."""
        if not ozel:
            return "yok"
        return "komut" if guncelle._PY_KOMUT.search(ozel) else "manuel"

    def test_kapsam_tablosu_haritayla_birebir(self) -> None:
        h = harita()
        onek = sinif_kart_oneki()
        hatalar = []
        for u in h["ust_siniflar"]:
            p = kart_dizini() / f"{onek}{u['id']}.md"
            if not p.is_file():
                continue  # eksiklik ayrı testin işi
            metin = p.read_text(encoding="utf-8")
            if self.BASLIK not in metin:
                hatalar.append(f"{p.name}: '{self.BASLIK}' bölümü yok")
                continue
            bolum = metin.split(self.BASLIK, 1)[1].split("\n## ", 1)[0]
            bulunan = {(m.group(1), m.group(2), m.group(3).strip(),
                        m.group(4).strip() if m.group(3).strip() != "yok" else None)
                       for m in re.finditer(
                           r"^\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|([^|]*)\|([^|]*)\|",
                           bolum, re.M)}
            beklenen = {(s["sinif"], "null" if s["etkin"] is None else s["etkin"],
                         self._ozel_kategori(s["ozel_adim"]),
                         s["ozel_adim"].strip() if s["ozel_adim"] else None)
                        for s in h["siniflar"] if s["ust_sinif"] == u["id"]}
            if bulunan != beklenen:
                hatalar.append(f"{p.name}: fazla={sorted(bulunan - beklenen)} "
                               f"eksik={sorted(beklenen - bulunan)}")
        self.assertEqual([], hatalar, "sınıf kartı kapsam tablosu haritayla uyuşmuyor:\n"
                         + "\n".join(hatalar))


if __name__ == "__main__":
    unittest.main()
