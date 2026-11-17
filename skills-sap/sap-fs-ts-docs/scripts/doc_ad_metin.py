# -*- coding: utf-8 -*-
"""doc_ad_metin — doküman üreticileri için CDS yorum ayıklayıcı + SAP ad grameri (yalnız stdlib).

NEDEN AYRI MODÜL
  `gen_field_table.py` ve `program_to_spec.py` SAP'ye bağlanmayan doküman üreticileridir. Ad grameri ve yorum ayıklama
  yazma kapısının bulunduğu `sap-adt-foundation` modüllerinden ALINMAZ: o modüller bağlantı/kimlik katmanını açılışta
  yükleyebilir ve üçüncü parti paket ister (kaynak ekipte ölçüldü: araç `requests`/`dotenv` olmadan açılmıyordu ve
  `.conn_adt` kimliklerini süreç ortamına yüklüyordu). Burada yalnız GRAMER vardır; "bu ad müşterinin mi" KARARI yoktur
  (karar yazma kapısında, proje yapılandırmasıyla verilir).
  ⛔ Bu modüle stdlib dışı import ya da proje yapılandırması okuma EKLEME — `test_field_table` bunu ölçer.

AD GRAMERİ
  Namespace'li ad `/<NS>/<ad>`; namespace gövdesi 3-8 karakter `[A-Za-z0-9_]` (SAP: eğik çizgiler dahil 5-10).
  `AD_ADAYI` metinden gevşek yakalar (`/` ile başlayan aday durak karakterine kadar), `ad_coz` katı grameri uygular.
  Dosya adı yönü: `/NS/X` → `#ns#x` (abapGit gösterimi). Dosya adında `/` olamaz: `os.path.join(kok, "/NS/X.cds")`
  kökü ATAR (ikinci parça mutlak yol sayılır).
"""
import re

NS_GOVDE = r"[A-Za-z0-9_]{3,8}"
AD_DESENI = r"(?a:(?:/" + NS_GOVDE + r"/)?[A-Za-z0-9_]+)"
_AD_DURAK = r"\s{}\[\]();,.:'\"<>=|`\-"
AD_ADAYI = r"(?a:/[^" + _AD_DURAK + r"]*|[A-Za-z0-9_]+)"
_AD_TAM = re.compile(r"\A" + AD_DESENI + r"\Z", re.IGNORECASE)
_AD_NS = re.compile(r"^(/" + NS_GOVDE + r"/)")


def ad_gecerli_mi(ad):
    """Ad katı gramere TAM uyuyor mu (`/NSPC/X` · `ZCA001_X` → True; `/AB/X` · `/NSPC/` · `` → False)."""
    return bool(ad) and _AD_TAM.match(str(ad)) is not None


def ad_coz(aday):
    """(ad, None) ya da ('', 'ad-cozulemedi'). Harf değiştirilmez."""
    a = "" if aday is None else str(aday)
    return (a, None) if ad_gecerli_mi(a) else ("", "ad-cozulemedi")


def ad_namespace(ad):
    """`/NS/X` → `/NS/` · namespace'siz ad → None."""
    m = _AD_NS.match(str(ad or "").strip().upper())
    return m.group(1) if m else None


def dosya_adi(ad):
    """SAP adı → yerel dosya adının ad parçası: `/NS/X` → `#ns#x` · `ZX` → `zx`.
    Dönüşümden sonra `/` ya da `\\` kalırsa ValueError (dosya adı yol ayıracı taşıyamaz)."""
    a = str(ad or "").strip().upper()
    ns = ad_namespace(a)
    if ns:
        a = "#" + ns[1:-1] + "#" + a[len(ns):]
    if "/" in a or "\\" in a:
        raise ValueError("dosya adına çevrilemez (yol ayıracı kalıyor): %r" % (ad,))
    return a.lower()


def yerel_ad(ad):
    """Komşu dosya aramasında kullanılan ad: namespace'siz ad AYNEN (harf değişmez) · `/NS/X` → `#ns#x`."""
    a = str(ad or "").strip()
    if "/" in a or "\\" in a:
        return dosya_adi(a)
    return a


def cds_kod_metni(metin, string_icerigini_koru=False):
    """CDS kaynağından yorumları atar: `//` ve `--` satır yorumları (satır sonu korunur) + `/* */` blok yorumu (tek boşluk
    olur). String ('..', `''` kaçışı) yorumdan ÖNCE tüketilir ⇒ string içindeki `//` / `--` / `/*` yorum SAYILMAZ.

    `string_icerigini_koru=False`: string yerine `''` bırakılır (anahtar sözcük araması yalnız kodda). `True`: string olduğu
    gibi kalır — `@EndUserText.label: '…'` metnine ihtiyaç duyan tüketici (gen_field_table) için.
    `--` tanınmazsa yorumdaki `'` string açar ve başlığı yutar (kaynak ekipte canlı bir CDS'te `-- 601'in …` satırı ölçüldü).
    """
    cikti = []
    i, n = 0, len(metin)
    while i < n:
        c = metin[i]
        if c == "'":
            j = i + 1
            while j < n:
                if metin[j] == "'":
                    if j + 1 < n and metin[j + 1] == "'":
                        j += 2
                        continue
                    break
                j += 1
            cikti.append(metin[i:j + 1] if string_icerigini_koru else "''")
            i = j + 1
        elif metin.startswith("//", i) or metin.startswith("--", i):
            j = metin.find("\n", i)
            i = n if j < 0 else j
        elif metin.startswith("/*", i):
            j = metin.find("*/", i + 2)
            cikti.append(" ")
            i = n if j < 0 else j + 2
        else:
            cikti.append(c)
            i += 1
    return "".join(cikti)
