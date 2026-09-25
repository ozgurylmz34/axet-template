#!/usr/bin/env python3
"""Sorarak SAP projesi kurar — `%yeni-proje` skill'i ve `yeni-proje.cmd` bu TEK script'i çağırır.

Adımlar: klasör (yoksa oluşturulur) → git reposu değilse `git init -b main` → `new_project.py <klasör> --sap --name <ad>`
→ `sap-project.json` alanları → `AGENTS.md` şablon satırları → doğrulama (`doctor.sap_proje_dogrula` geçerli, şablon
yer tutucusu kalmadı, AGENTS.md SAP satırı sap-project.json ile tutarlı, `core.hooksPath=.githooks`) → `doctor.py`.

Neden (ölçüldü 2026-09-14): git'siz klasörde pre-commit kablolanmıyordu; `sap-project.json` ve `AGENTS.md` yer
tutucuları doldurulmadan kalıyor, SAP araçları yalnız `--list`/`ping` açıyordu.

Var olan dosya ezilmez: `sap-project.json`'da yalnız yer tutuculu/boş alanlar doldurulur, farklı kullanıcı değeri
korunur. Korunan değer `sap_profile` ya da `master_language`'de istenenden farklıysa ÇELİŞKİ (çıkış 1): kesin yasak D
login dilini master_language'den alır, profil araç yüzeyini belirler. `AGENTS.md`'de yalnız şablondaki TAM satırlar
(`templates/project/AGENTS.md`) değişir; SAP satırı sap-project.json'un SON hâlinden üretilir; kesin yasak damgasına
dokunulmaz. Kimlik bilgisi sorulmaz; `setup_credentials.py` ve `behavior_manifest.py generate` ÇALIŞTIRILMAZ.
Başarılı kurulumun sonunda proje köküne `KURULUMU-TAMAMLA.cmd` kısayolu yazılır (varsa ezilmez): template kökündeki
`proje-tamamla.cmd`'yi çağırır; kalan kullanıcı adımları (bağlantı · onay · doctor · aXet'i aç) tek çift tıklamadır.

Kullanım:
  python <TEMPLATE>/scripts/yeni_proje.py                         etkileşimli (gerçek terminalde sorar)
  python <TEMPLATE>/scripts/yeni_proje.py <KLASÖR> --no-input --sap-profile s4_private --release 2023 \\
      --master-language TR --cleancore-policy balanced --purpose "Sevkiyat geliştirmeleri" [--dry-run]

Çıkış: 0 kuruldu ve doctor 0 FAIL (dry-run: plan sorunsuz) · 1 adım/doğrulama/doctor başarısız ya da ÇELİŞKİ
(dry-run: gerçek koşu 1 verecek) · 2 girdi hatası / eksik alan / iptal (hiçbir şey yazılmadı).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import doctor  # noqa: E402  (yer_tutucular, sap_proje_dogrula — doğrulama kuralı kopyalanmaz)
import new_project  # noqa: E402  (AXET_HOME, şablon yolları)
import sap_stamp  # noqa: E402  (damga işaretleri)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

AXET_HOME = new_project.AXET_HOME
SCRIPTS = AXET_HOME / "scripts"

# AGENTS.md SAP satırı ayrıştırması doctor.py'de TEK kopya (doctor da aynı satırı denetler); burada yalnız ad.
PROFILLER = doctor.PROFILLER  # project.py GECERLI_PROFILLER ile aynı küme (test eşitliği denetler)
# Kaynak: skills-sap/sap-code-review/references/clean-core.md §1 tablo (strict/balanced/classic; balanced = profil
# varsayılanı) · skills-sap/sap-adt-foundation/references/profiles.md "Sürüm/politika farkları": eksen YALNIZ s4_private
# (ecc'de kavram yok; s4_public/btp_abap'ta platform zorlar). Diğer profillerde verilen değer yok sayılır, boş yazılır.
POLITIKALAR = ("strict", "balanced", "classic")
POLITIKA_PROFILI = "s4_private"
# Korunan değer istenenden farklıysa çıkış 1 verilen alanlar (release/cleancore_policy/source_root/project → uyarı).
KRITIK_ALANLAR = ("sap_profile", "master_language")
VARSAYILAN_SOURCE_ROOT = "SOURCE_CODES"  # templates/project-sap/sap-project.json
TEKNOLOJI = {"ecc": "SAP ECC ABAP", "s4_private": "SAP S/4HANA ABAP",
             "s4_public": "SAP S/4HANA Cloud Public Edition ABAP", "btp_abap": "SAP BTP ABAP Environment"}
KOMUT_YOK = "henüz tanımlı değil"
KURAL_YOK = "Henüz projeye özel kural yok."
# session_brief.py `aktif_paket`: değerin ilk sözcüğü SAP paket adı biçimine (Z/Y… ya da /ADALANI/AD, büyük harf) uymazsa
# "aktif paket ÖLÇÜLEMEDİ"; boş, "<" ya da "—" ile başlayan değer → "AGENTS.md'de yazılı değil" dalı (testli).
AKTIF_PAKET_YOK = "— henüz seçilmedi"

# templates/project/AGENTS.md'de bu aracın doldurduğu satırları bulan işaretler; satırın TAMAMI şablondan okunur.
TEKNOLOJI_ISARETI = "<ör. SAP S/4HANA ABAP · Python · UI5>"
DEPO_ISARETI = '<remote adresi ya da "yerel">'
SABLON_ISARETLERI = {"amac": "<kısa açıklama>", "teknoloji": TEKNOLOJI_ISARETI, "sap": "master_language: <TR|EN>",
                     "depo": DEPO_ISARETI, "test": "- Test: <komut>", "calistirma": "- Çalıştırma / derleme: <komut>",
                     "dogrulama": "- Doğrulama / lint: <komut>", "kural": "- <projeye özel kural>"}
ETIKET = {"amac": "Amaç", "teknoloji": "Teknoloji", "sap": "SAP satırı", "depo": "Depo", "test": "Test",
          "calistirma": "Çalıştırma / derleme", "dogrulama": "Doğrulama / lint", "kural": "Proje kuralları"}

_AD = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_DIL = doctor._DIL
_WIN_AYRILMIS = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


class Kesinti(Exception):
    """Etkileşimli modda girdi bitti ya da cevaplar geçersiz kaldı."""


# --- git ---------------------------------------------------------------------------------------------------------
GIT_YONLENDIRME = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR")


def temiz_ortam() -> dict[str, str]:
    """Çocuk süreç ortamı: git'i başka repoya yönlendiren değişkenler atılır (yeniden inceleme E5 — GIT_DIR dışarıdan
    geliyorsa `git -C hedef` onu izler; init/hooksPath öteki repoya gider). git, new_project ve doctor bununla koşar."""
    return {k: v for k, v in os.environ.items() if k.upper() not in GIT_YONLENDIRME}


def git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *(["-C", str(cwd)] if cwd else []), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, env=temiz_ortam())


def git_durumu(hedef: Path) -> str:
    """'yok' (git reposu değil) · 'kok' (repo kökü) · 'alt:<kök>' (başka reponun alt klasörü) · 'hata:<mesaj>'.

    Klasör henüz yoksa en yakın VAR OLAN üst klasöre bakılır (test ölçümü: yalnız klasörün kendisine bakınca, var olan
    reponun altında yaratılacak klasör 'yok' sayılıp içine kuruluyordu). rev-parse başarısızsa: üst zincirde hiç `.git`
    yoksa 'yok'; `.git` varsa (bozuk gitfile, sahiplik reddi …) 'hata' — git mesajının diline bağlı kalmamak için
    stderr metni değil `.git` izi ölçülür (ölçüldü: bozuk `.git` dosyası → "fatal: invalid gitfile format")."""
    mevcut = hedef
    while not mevcut.is_dir() and mevcut.parent != mevcut:
        mevcut = mevcut.parent
    if not mevcut.is_dir():
        return "yok"
    r = git("rev-parse", "--show-toplevel", cwd=mevcut)
    if r.returncode != 0:
        iz = next((d / ".git" for d in (mevcut, *mevcut.parents) if (d / ".git").exists()), None)
        if iz is None:
            return "yok"
        return f"hata:{(r.stderr or r.stdout).strip() or f'git rev-parse çıkış {r.returncode}'} ({iz})"
    kok = Path(r.stdout.strip()).resolve()
    return "kok" if kok == hedef else f"alt:{kok}"


SIR_QUERY_ANAHTARLARI = frozenset({"token", "password", "private_token", "access_token"})


def http_kimlik(url: str) -> tuple[bool, str]:
    """(sır var mı, temiz adres). Denetimler:
    1. http(s) ve `+http(s)` şemaları (git+https): yetki (authority) ilk '/', '?' ya da '#'te biter (git credential.c ve
       curl ile aynı sınır). Yetkide '@' varsa yetkinin SON '@'ine kadarki kısım atılır, yol korunur (`kul:p@ss@host` ·
       `TOKEN@host/~u@x` — token kullanıcı adı yerine de yazılır). '@' yalnız yol/query/fragment'teyse kimlik YOKTUR
       (`https://host/~kul@ekip/r.git`). Fail-closed, son '@'e kadar her şey atılır: yetkideki ':' sonrası geçerli port
       değilse (`kul:ab/cd@host` · `kul:Pa#x@host` — parola '/', '?' ya da '#' içeriyor) ya da parolalı kimlikten
       sonra yine '@' varsa (`u:p@s/s@host` — parola '@'/'/' içeriyor olabilir).
    2. Diğer şemalarda (ssh, git+ssh …) yalnız PAROLA atılır, kullanıcı adı kalır (ssh://git@host sır değil).
    3. scp biçimi (`://` yok; git'in kuralı: ilk ':' ilk '/'ten önce, sürücü harfli yol değil): ilk '@'ten önce ':' ve
       sonra host:yol ayracı ':' varsa parola vardır (`u:p@host:yol` → `u@host:yol`; parolada '@' → son '@'e kadar atılır).
    4. Query'de ve fragment'te (`#access_token=…`) token/password/private_token/access_token anahtarları (büyük/küçük
       harf duyarsız) atılır.
    Ayrıştırılamayan adres (urlsplit ValueError, ör. `https://[::1/x`) FAIL-CLOSED: sır var sayılır (bug gate Y-b);
    `d_repo` bunu ayrı ve açık mesajla reddeder (`_kimlik_denetimi`'nin üçüncü değeri).
    Sınırlar — kimlik olarak TESPİT EDİLMEZ, reddedilmez: yalnız rakamlı parolada '/', '?' ya da '#'
    (`https://kul:12/x@host` host:port sayılır) · ':' içermeyen token'da '/', '?' ya da '#' (`https://TO/KEN@host`). Bu
    biçimlerde '@' yetkiden sonra kalır → `depo_uyarisi` açık UYARI basar (lider kararı 2026-09-14: kodlanmamış '/?#'
    git/curl'de zaten geçersiz yetki üretir, olasılık düşük; ret yok ama sessiz de değil). Uyarısız sınır: host:yol
    ayracı olmayan scp dizgesi (`u:p@host`)."""
    sir, temiz, _ = _kimlik_denetimi(url)
    return sir, temiz


def _normalize(url: str) -> str:
    """urlsplit'in yaptığı normalleştirme: baştaki C0 kontrol/boşluk atılır, \\t \\r \\n her yerden silinir."""
    return "".join(c for c in url.lstrip("".join(map(chr, range(0x21)))) if c not in "\t\r\n")


# _kimlik_denetimi'nin üçüncü değeri (sorun sınıfı; girdiden metin taşımaz).
_AYRISTIRILAMADI, _BELIRSIZ, _BELIRSIZ_SCP = "ayristirilamadi", "belirsiz", "belirsiz-scp"


def _http_semasi(sema: str) -> bool:
    return sema in ("http", "https") or sema.endswith(("+http", "+https"))


def _gecerli_host_port(yetki: str) -> bool:
    """Kimliksiz yetki `host`, `host:port` ya da `[ipv6]:port` biçiminde mi (port = en az bir rakam). Kapanmamış '['
    burada yargılanmaz (True): urlsplit ValueError verir, ayrıştırma hatası olarak fail-closed reddedilir."""
    if yetki.startswith("["):
        if "]" not in yetki:
            return True
        kalan = yetki.split("]", 1)[1]
        return not kalan or bool(re.fullmatch(r":[0-9]+", kalan))
    return ":" not in yetki or bool(re.fullmatch(r"[0-9]+", yetki.split(":", 1)[1]))


def _scp_denetimi(url: str) -> tuple[bool, str, str | None]:
    """`://`'siz adres: scp biçiminde (`[kul[:parola]@]host:yol`) parola var mı. Git'in scp tanımı: ilk ':' ilk '/'ten
    önce (connect.c url_is_local_not_ssh); `C:/…`, `C:\\…` yerel yoldur."""
    if re.match(r"[A-Za-z]:[\\/]", url):
        return False, url, None
    at, iki_nokta, bolu = url.find("@"), url.find(":"), url.find("/")
    if at < 0 or iki_nokta < 0 or iki_nokta > at or (0 <= bolu < iki_nokta) or ":" not in url[at + 1:]:
        return False, url, None
    kalan = url[at + 1:]
    if "@" in kalan:  # parola '@' içeriyor olabilir → fail-closed: son '@'e kadar (kullanıcı adı dahil) atılır
        return True, url.rsplit("@", 1)[1], _BELIRSIZ_SCP
    kullanici = url[:iki_nokta]
    # Gate F1: parola kısmında '/' varsa `u:p/q@host:yol` ile yolunda '@' ve ':' geçen `host:ekip/u@x:y` (a:b/c@d:e)
    # yapısal olarak aynıdır → kimlik var sayılır (fail-closed) ama temizlenen adres BELİRSİZ (öneri olarak kullanılmaz).
    return True, (f"{kullanici}@" if kullanici else "") + kalan, (_BELIRSIZ_SCP if "/" in url[iki_nokta + 1:at] else None)


def _kimlik_denetimi(url: str) -> tuple[bool, str, str | None]:
    """(sır var mı, temiz adres, sorun) — kurallar `http_kimlik` belgesinde. sorun: None (temiz adres güvenilir) ·
    _AYRISTIRILAMADI · _BELIRSIZ (fail-closed kesim: temiz adres host/yol kaybetmiş olabilir) · _BELIRSIZ_SCP. Sorunlu
    temiz adres origin önerisi olarak KULLANILMAZ (gate F1); sorun metni girdiden hiçbir parça taşımaz (gate F4)."""
    # Re-gate LOW-2: urlsplit baştaki C0 kontrol/boşluk karakterlerini atar (_WHATWG_C0_CONTROL_OR_SPACE) ve \t \r \n'yi her
    # yerden siler (_UNSAFE_URL_BYTES_TO_REMOVE) — ölçüldü, Python 3.14.4. Şema ham dizgeden okununca `\x1bhttps://TOKEN@host`
    # http sayılmıyor, token açıkta kalıyordu → önce aynı normalleştirme (derinlemesine savunma; kontrol karakterli girdi
    # ayrıca d_metin'de reddedilir).
    url = _normalize(url)
    if "://" not in url:
        return _scp_denetimi(url)
    bas = url.index("://") + 3
    sema = url[:bas - 3].lower()
    http_mi = _http_semasi(sema)

    def kimliksiz(u: str) -> str:
        return u[:bas] + u[bas:].rsplit("@", 1)[1] if "@" in u[bas:] else u

    govde = url[bas:]
    if http_mi and "@" in govde:
        # Kimlik kısmı HAM dizgede, urlsplit'ten ÖNCE atılır (bug gate BLOCKER-1): parola '#' ya da '?' içerirse urlsplit
        # parolanın geri kalanını fragment/query sayar; önce fragment/query temizlenince parolanın '#' öncesi parçası
        # adreste kalıyordu (`https://kul:Pa#password=x@host/r` → `https://kul:Pa`). Kalan adres token için yeniden denetlenir.
        yetki = re.split(r"[/?#]", govde, maxsplit=1)[0]
        if "@" in yetki:
            kullanici = yetki.rsplit("@", 1)[0]
            kalan = govde[len(kullanici) + 1:]
            if ":" in kullanici and "@" in kalan:
                return True, _kimlik_denetimi(kimliksiz(url))[1], _BELIRSIZ
            alt = _kimlik_denetimi(url[:bas] + kalan)
            return True, alt[1], (_BELIRSIZ if alt[2] else None)
        if not _gecerli_host_port(yetki):
            return True, _kimlik_denetimi(kimliksiz(url))[1], _BELIRSIZ
        # '@' yalnız yol/query/fragment'te: kimlik değil (adım 4 — tabanda son '@'e kadar kesiliyordu: https://host/a@b →
        # https://b). Query/fragment token denetimi aşağıda sürer.
    try:
        parca = urllib.parse.urlsplit(url)
        parola = parca.password
    except ValueError:
        # Gate F4: urlsplit hata metni girdiden parça taşır (`'SECRETTOKEN' does not appear to be an IPv4 or IPv6 address`)
        return True, kimliksiz(url), _AYRISTIRILAMADI
    if not http_mi and ("@" in parca.query or "@" in parca.fragment):
        # http dışı şemada kullanıcı adı (ssh://git@host) meşrudur; ama '@' query/fragment'e düştüyse parola '#'/'?' içeriyor
        # olabilir (`ssh://u:p#a@host` → netloc 'u:p', parola urlsplit'e görünmez; HEAD'de (False, parola açıkta) dönüyordu)
        # → fail-closed: sır var, kimlik kısmı tümüyle atılır.
        return True, kimliksiz(url), _BELIRSIZ
    if (not http_mi and "@" in govde and ":" in govde.split("@", 1)[0]
            and parca.netloc.rpartition("@")[0] != govde.rsplit("@", 1)[0]):
        # Re-gate 4: http dışı şemada parola '/' ya da '@' içerirse urlsplit netloc'u erken keser (`ssh://u:p/q@host` →
        # netloc 'u:p', parola görünmez · `ssh://u:p@s/s@host` → parola 'p', 's/s@host' yola kalır). Ham dizgede ilk '@'
        # öncesinde ':' var ve urlsplit'in gördüğü kimlik, son '@'e kadarki ham kısımla aynı değil → fail-closed: sır var,
        # son '@'e kadar her şey atılır. Sınır: kullanıcısız ama yolunda ':' ve '@' geçen adres de sır sayılır (ssh://h:22/a@b).
        return True, kimliksiz(url), _BELIRSIZ
    sir = False
    temiz = url
    if parca.query:
        kalan = [p for p in parca.query.split("&")
                 if urllib.parse.unquote_plus(p.split("=", 1)[0]).lower() not in SIR_QUERY_ANAHTARLARI]
        if len(kalan) != len(parca.query.split("&")):
            sir = True
            i = temiz.index("?")
            temiz = temiz[:i] + ("?" + "&".join(kalan) if kalan else "") + temiz[i + 1 + len(parca.query):]
    if parca.fragment:
        # urlsplit fragment'i İLK '#'ten ayırır ve query '#' içeremez → temizdeki ilk '#' fragment ayracıdır.
        parcalar = parca.fragment.split("&")
        kalan = [p for p in parcalar if urllib.parse.unquote_plus(p.split("=", 1)[0]).lower() not in SIR_QUERY_ANAHTARLARI]
        if len(kalan) != len(parcalar):
            sir = True
            temiz = temiz[:temiz.index("#")] + ("#" + "&".join(kalan) if kalan else "")
    if parola is not None:  # http(s) kimliği yukarıda atıldı; burada yalnız http dışı şemaların parolası
        kullanici, _, host = parca.netloc.rpartition("@")
        return True, temiz[:bas] + kullanici.split(":", 1)[0] + "@" + host + temiz[bas + len(parca.netloc):], None
    return sir, temiz, None


ORIGIN_UYARISI = "origin adresi güvenle temizlenemedi; --repo ile ver (öneri 'yerel'; adres gösterilmedi)"


def depo_onerisi_ve_uyari(hedef: Path) -> tuple[str, str | None]:
    """(öneri, uyarı ya da None). Repo kökünde `origin` varsa onun kimliksiz adresi, yoksa 'yerel'. Gate F1: temizleme
    belirsizse (fail-closed kesim, belirsiz scp, ayrıştırılamayan adres) bozulmuş olabilecek adres önerilmez → 'yerel' +
    adresi basmayan uyarı. Lider kararı (adım 4 fix EK): scp biçiminde (şemasız) git'in parola sözdizimi yoktur
    (`[user@]host:path`) → scp adresini DEĞİŞTİREN her temizleme tahmindir, önerilmez (`kul:gizli@host:yol`,
    `host:u@x:y.git` dahil). Değişmeyen scp aynen önerilir; https'teki kesin kimlik temizleme önerisi kalır. Açık --repo
    denetimi (d_repo) bundan etkilenmez."""
    if shutil.which("git") and git_durumu(hedef) == "kok":
        url = git("remote", "get-url", "origin", cwd=hedef).stdout.strip()
        if url:
            _, temiz, sorun = _kimlik_denetimi(url)
            normal = _normalize(url)
            scp_degisti = "://" not in normal and temiz != normal
            return ("yerel", ORIGIN_UYARISI) if sorun or scp_degisti else (temiz, None)
    return "yerel", None


def depo_onerisi(hedef: Path) -> str:
    return depo_onerisi_ve_uyari(hedef)[0]


# --- girdi doğrulama (hata metni ya da None) ---------------------------------------------------------------------
def _ad_sorunu(ad: str) -> str | None:
    if ad.endswith((".", " ")):
        return "nokta ya da boşlukla bitemez"
    if ad.split(".")[0].strip().upper() in _WIN_AYRILMIS:
        return "Windows'ta ayrılmış bir ad (CON, NUL, COM1 …)"
    return None


def d_klasor(s: str) -> str | None:
    """Klasör: ad güvenliği (son bileşen) · `.git` içi değil · dosya değil · template içi değil · başka reponun alt
    klasörü değil · git durumu okunabilir. Etkileşimli modda klasör sorusunun HEMEN ardından koşar."""
    if not s or not s.strip():
        return "zorunlu"
    parcalar = [x for x in re.split(r"[\\/]", s) if x]
    p = Path(s).expanduser().resolve()
    son = parcalar[-1] if parcalar else ""
    if son in ("", ".", "..") or re.fullmatch(r"[A-Za-z]:", son):
        son = p.name
    sorun = _ad_sorunu(son)
    if sorun:
        return f"klasör adı {son!r}: {sorun}"
    if any(x.lower() == ".git" for x in (*parcalar, *p.parts)):
        return "klasör bir .git klasörünün içinde olamaz"
    if p.exists() and not p.is_dir():
        return f"klasör değil (dosya var): {p}"
    if p == AXET_HOME or AXET_HOME in p.parents:
        return f"template reposunun içinde ({AXET_HOME}); proje ayrı bir klasörde olmalı"
    if shutil.which("git"):
        gd = git_durumu(p)
        if gd.startswith("alt:"):
            return (f"başka bir git reposunun alt klasörü ({gd[4:]}); pre-commit yalnız repo kökünde kablolanır → ayrı "
                    "bir klasör seç ya da o reponun kökünü hedef ver")
        if gd.startswith("hata:"):
            return f"git durumu okunamadı — {gd[5:]}"
    return None


def d_ad(s: str) -> str | None:
    if not s:
        return "zorunlu"
    if not _AD.match(s) or _ad_sorunu(s):
        return (f"proje adı dosya adı güvenli olmalı ({s!r}): harf/rakam ile başlar; yalnız harf, rakam, '.', '_', '-'; "
                "en çok 64 karakter; boşluk yok (PROJECT-ID satırı tek sözcük okunur); nokta ile bitmez; Windows "
                "ayrılmış adı değil")
    return None


def d_profil(s: str) -> str | None:
    return None if s in PROFILLER else f"sap_profile {s!r} geçersiz (geçerli: {', '.join(PROFILLER)})"


def d_release(s: str) -> str | None:
    if not s:
        return "zorunlu"
    if len(s) > 20 or any(c in s for c in '<>"`\n\r'):
        return f"release {s!r} geçersiz (en çok 20 karakter; < > \" ` yok; ör. 2023)"
    return None


def d_dil(s: str) -> str | None:
    return None if _DIL.match(s or "") else f"master_language {s!r} geçersiz (iki harfli dil anahtarı, ör. TR/EN)"


def d_politika(s: str) -> str | None:
    """Yalnız s4_private için çağrılır (zorunlu)."""
    if s in POLITIKALAR:
        return None
    return f"cleancore_policy {s!r} geçersiz{' (s4_private’ta zorunlu)' if not s else ''} (geçerli: {', '.join(POLITIKALAR)})"


def d_source_root(s: str) -> str | None:
    # new_package.source_root ile aynı ölçüt: proje içinde göreli klasör.
    p = Path(s)
    if not s.strip() or p.is_absolute() or p.drive or ".." in p.parts or any(c in s for c in "<>\"`\n\r"):
        return f"source_root {s!r} geçersiz (proje içinde göreli bir klasör, ör. {VARSAYILAN_SOURCE_ROOT})"
    return None


def d_metin(zorunlu: bool):
    def dogrula(s: str) -> str | None:
        if not s:
            return "zorunlu" if zorunlu else None
        if "\n" in s or "\r" in s or len(s) > 200:
            return "tek satır ve en çok 200 karakter olmalı"
        if any(ord(c) < 0x20 or ord(c) == 0x7f for c in s):
            # Re-gate LOW-2: ESC gibi kontrol karakterleri terminalde görünmez ve urlsplit'in şema okumasını saptırır.
            return "kontrol karakteri içeremez (ör. ESC, sekme); düz metin yaz"
        if doctor.yer_tutucular(s):
            return f"metin şablon yer tutucusuna benziyor ({', '.join(doctor.yer_tutucular(s))}); < > kullanmadan yaz"
        if sap_stamp._BASLA_ONEK in s or sap_stamp._BITIR_ONEK in s:
            return "metin kesin yasak damga işaretini içeremez"
        return None
    return dogrula


def d_repo(s: str) -> str | None:
    hata = d_metin(True)(s)
    if hata:
        return hata
    sir, _, sorun = _kimlik_denetimi(s)
    if sorun == _AYRISTIRILAMADI:
        # Y-b: fail-closed ret, ama sebep "parola var" değil — kimlik taşıyıp taşımadığı ölçülemedi. Gate F4: girdiden metin yok.
        return ("adres ayrıştırılamadı — kimlik bilgisi taşıyıp taşımadığı ölçülemediği için reddedildi; "
                "geçerli bir adresi kimlik kısmı olmadan ver (ör. https://host/ekip/proje.git) ya da 'yerel' yaz")
    if sorun == _BELIRSIZ_SCP:
        # Gate F1: ret kalır, sebep açık — parola mı yol mu ayırt edilemiyor.
        return ("scp biçimli adres belirsiz: '@' öncesinde '/' ya da birden çok '@' var; `kul:parola@host:yol` mu, yolunda "
                "'@' geçen `host:yol` mu ayırt edilemiyor — parola taşıyor olabileceği için reddedildi; parolasız adresi "
                "ssh:// biçiminde ver (ör. ssh://git@host/ekip/proje.git) ya da 'yerel' yaz")
    if sir:
        # Yalnız parola değil, her kullanıcı kısmı reddedilir: token kullanıcı adı yerine de yazılır (https://TOKEN@host).
        return ("adreste parola, http(s) kullanıcısı ya da token (query dahil) var — AGENTS.md repoya ve her oturuma "
                "girer; adresi kimlik kısmı olmadan ver (ör. https://host/ekip/proje.git · git@host:ekip/proje.git)")
    return None


YOLDA_AT_UYARISI = "adresin yol/sorgu kısmında '@' var; kimlik bilgisi değilse sorun yok, kimlik bilgisiyse adresten çıkar"


def depo_uyarisi(s: str) -> str | None:
    """d_repo'nun KABUL ettiği http(s) adreste yetkiden sonra (yol/sorgu/fragment) '@' varsa uyarı metni, yoksa None.
    Ret değil (lider kararı 2026-09-14): `https://host/~kul@ekip/r.git` meşrudur; ama kodlanmamış '/?#' içeren token ya
    da rakamlı parola (`https://TO/KEN@host`) yetki sınırı yüzünden kimlik sayılmaz, bu uyarı onu görünür kılar.
    Kabul edilen adreste yetkide '@' olamaz (varsa d_repo reddeder) → gövdedeki her '@' yetkiden sonradır."""
    if d_repo(s):
        return None
    url = _normalize(s)
    if "://" not in url or not _http_semasi(url[:url.index("://")].lower()):
        return None
    return YOLDA_AT_UYARISI if "@" in url[url.index("://") + 3:] else None


def d_komut(s: str) -> str | None:
    if s and ("\n" in s or "\r" in s or "`" in s or len(s) > 200):
        return "komut tek satır, en çok 200 karakter ve ` içermeden yazılmalı"
    return None


# --- ortam -------------------------------------------------------------------------------------------------------
def etkilesimli_mi() -> bool:
    """Gerçek terminal mi? Ölçülmüş mantık: skills-sap/sap-adt-foundation/scripts/setup_credentials.py `etkilesimli_mi`
    (Windows'ta stdin NUL'a yönlendirilince isatty() True döner → ek olarak GetConsoleMode istenir). Kimlik script'ini
    içe aktarmamak için burada tekrarlandı; ölçülemezse etkileşimsiz sayılır (soru sorulmaz)."""
    try:
        if sys.stdin is None or not sys.stdin.isatty():
            return False
        if os.name == "nt":
            import ctypes
            import msvcrt
            tutamac = msvcrt.get_osfhandle(sys.stdin.fileno())
            mod = ctypes.c_uint32()
            return bool(ctypes.windll.kernel32.GetConsoleMode(ctypes.c_void_p(tutamac), ctypes.byref(mod)))
        return True
    except Exception:  # noqa: BLE001
        return False


# --- sap-project.json (saf fonksiyonlar: dry-run da aynısını kullanır) ---------------------------------------------
def _yer_tutucu_deger(deger) -> bool:
    return deger is None or (isinstance(deger, str) and (not deger.strip() or re.fullmatch(r"<[^<>]*>", deger.strip())))


def sap_json_doldur(metin: str, istenen: dict, yeni: bool) -> tuple[str, list[str], list[tuple], dict]:
    """(yeni metin, rapor satırları, korunan [(alan, dosyadaki, istenen)], son veri).
    `yeni`=dosya bu koşuda şablondan kuruldu → tüm alanlar yazılır."""
    veri = json.loads(metin)
    if not isinstance(veri, dict):
        raise ValueError("kök bir JSON nesnesi değil")
    rapor, korunan = [], []
    for k, v in istenen.items():
        mevcut = veri.get(k)
        esit = (isinstance(mevcut, str) and (mevcut.strip().upper() == v.upper() if k == "master_language" else mevcut == v))
        if esit:
            rapor.append(f"  [aynı]        sap-project.json {k} = {mevcut!r}")
        elif yeni or _yer_tutucu_deger(mevcut):
            veri[k] = v
            rapor.append(f"  [dolduruldu]  sap-project.json {k} = {v!r}")
        else:
            korunan.append((k, mevcut, v))
            rapor.append(f"  [KORUNDU]     sap-project.json {k}: dosyada {mevcut!r} (istenen {v!r}) — kullanıcı değeri ezilmedi")
    return json.dumps(veri, indent=2, ensure_ascii=False) + "\n", rapor, korunan, veri


sap_degerleri = doctor.sap_degerleri  # AGENTS.md SAP satırının kaynağı: sap-project.json'un SON hâli

def celiski_ayir(korunan: list[tuple]) -> tuple[list[str], list[str]]:
    """(kritik → çıkış 1, uyarı → çıkış 0). Kritik: sap_profile, master_language."""
    kritik, uyari = [], []
    for k, mevcut, istenen in korunan:
        if k in KRITIK_ALANLAR:
            kritik.append(f"ÇELİŞKİ: sap-project.json {k}={mevcut!r} korundu ama istenen {istenen!r}. AGENTS.md dosyadaki "
                          f"değerle yazılır. {'Kesin yasak D login dilini master_language’den alır' if k == 'master_language' else 'Profil SAP araç yüzeyini belirler'}"
                          " → hangisi doğruysa sap-project.json'u ona göre düzelt ya da girdiyi dosyadaki değerle ver, "
                          "sonra aracı yeniden çalıştır")
        else:
            uyari.append(f"sap-project.json {k}: dosyadaki {mevcut!r} korundu (istenen {istenen!r}); AGENTS.md dosyadaki "
                         "değerle tutarlı yazıldı — bilinçli değilse dosyada düzelt")
    return kritik, uyari


# --- AGENTS.md ---------------------------------------------------------------------------------------------------
def sablon_satirlari() -> dict[str, str]:
    """templates/project/AGENTS.md'den bu aracın doldurduğu TAM satırlar. Şablon değişip işaret bulunamazsa hata."""
    satirlar = (new_project.TEMPLATE / "AGENTS.md").read_text(encoding="utf-8").splitlines()
    out = {}
    for anahtar, isaret in SABLON_ISARETLERI.items():
        bulunan = [s.rstrip() for s in satirlar if isaret in s]
        if len(bulunan) != 1:
            raise RuntimeError(f"templates/project/AGENTS.md'de {isaret!r} içeren {len(bulunan)} satır var (1 bekleniyordu) "
                               "— şablon değişmiş; yeni_proje.py SABLON_ISARETLERI güncellenmeli")
        out[anahtar] = bulunan[0]
    return out


_satirlar = doctor.damga_satirlari  # (satır, kesin yasak damga bloğunun içinde mi)


def sap_satiri(sablon: str, sap: dict) -> str:
    satir = sablon
    for eski, yeni in (("sistem profili <…>", f"sistem profili {sap['sap_profile']} · sürüm {sap['release']}"),
                       ("master_language: <TR|EN>", f"master_language: {sap['master_language']}"),
                       ("aktif paket: <…>", f"aktif paket: {AKTIF_PAKET_YOK}")):
        if eski not in satir:
            raise RuntimeError(f"şablon SAP satırında {eski!r} yok — templates/project/AGENTS.md değişmiş")
        satir = satir.replace(eski, yeni, 1)
    return satir


def agents_doldur(metin: str, v: dict, sap: dict | None) -> tuple[str, list[str]]:
    """Yalnız şablondaki TAM satırları değiştirir (kullanıcının yazdığı satırlara dokunmaz); SAP satırı `sap`
    (sap-project.json son hâli) ile üretilir, `sap` None ise SAP satırı doldurulmaz. Damga bloğu atlanır."""
    sab = sablon_satirlari()

    def komut(k: str) -> str:
        return f"`{k}`" if k else KOMUT_YOK

    uretilen = {"amac": sab["amac"].replace("<kısa açıklama>", v["purpose"]),
                "teknoloji": sab["teknoloji"].replace(TEKNOLOJI_ISARETI, v["tech"]),
                "depo": sab["depo"].replace(DEPO_ISARETI, v["repo"]),
                "test": sab["test"].replace("<komut>", komut(v["test_cmd"])),
                "calistirma": sab["calistirma"].replace("<komut>", komut(v["run_cmd"])),
                "dogrulama": sab["dogrulama"].replace("<komut>", komut(v["lint_cmd"]))}
    if sap is not None:
        uretilen["sap"] = sap_satiri(sab["sap"], sap)
    cikti, rapor = [], []
    for satir, damga_ici in _satirlar(metin):
        govde = satir.rstrip("\r\n")
        son = satir[len(govde):]
        # iki taraf da rstrip(): sablon_satirlari() şablonu rstrip() ile okur; sonda boşluk/sekme kalmış satır da
        # şablon satırıdır (yeniden inceleme YENİ-2 — yoksa doldurulmaz ve sablon_kalanlari sahte PASS verir)
        karsilastir = govde.rstrip()
        if not damga_ici and karsilastir == sab["kural"]:
            kurallar = v["rules"] or [KURAL_YOK]
            cikti.append((son or "\n").join(f"- {k}" for k in kurallar) + son)
            rapor.append(f"{ETIKET['kural']} ({len(v['rules'])} kural)" if v["rules"] else f"{ETIKET['kural']} (nötr varsayılan)")
            continue
        anahtar = None if damga_ici else next((a for a, s in sab.items() if a in uretilen and karsilastir == s), None)
        if anahtar:
            cikti.append(uretilen[anahtar] + son)
            rapor.append(ETIKET[anahtar])
        else:
            cikti.append(satir)
    return "".join(cikti), rapor


def sablon_kalanlari(metin: str) -> list[str]:
    """Bu aracın doldurması gereken şablon satırlarından AGENTS.md'de hâlâ duranlar (→ FAIL)."""
    sab = sablon_satirlari()
    ters = {s: a for a, s in sab.items()}
    return [ETIKET[ters[g]] for satir, ici in _satirlar(metin) if not ici and (g := satir.rstrip()) in ters]


def diger_yer_tutucular(metin: str) -> list[str]:
    """Şablon satırları dışındaki yer tutucular (kullanıcı metni) — uyarı; doctor da bunlara yalnız WARN verir."""
    sablon = set(sablon_satirlari().values())
    return doctor.yer_tutucular("".join(s for s, _ in _satirlar(metin) if s.rstrip() not in sablon))


sap_satiri_denetle = doctor.sap_satiri_denetle  # ('tutarli' | 'celiski' | 'olculemedi', ayrıntılar) — doctor ile aynı kopya


# --- girdi toplama -----------------------------------------------------------------------------------------------
SABLON_BOZUK = "şablon satırları bulunamadı (templates/project/AGENTS.md değişmiş olabilir)"
ZORUNLU_BAYRAK = {"target": "KLASÖR (konumsal)", "sap_profile": "--sap-profile", "release": "--release",
                  "master_language": "--master-language", "purpose": "--purpose"}


def sor(soru: str, dogrula, varsayilan: str | None = None, girdi=input) -> str:
    ek = f" [{varsayilan}]" if varsayilan else (" [boş geçilebilir]" if varsayilan == "" else "")
    for _ in range(3):
        try:
            cevap = girdi(f"{soru}{ek}: ").strip()
        except EOFError:
            raise Kesinti("girdi bitti (soru cevaplanmadı)") from None
        if not cevap and varsayilan is not None:
            cevap = varsayilan
        hata = dogrula(cevap)
        if not hata:
            return cevap
        print(f"  ! {hata}")
    raise Kesinti(f"3 kez geçersiz cevap: {soru}")


def etkilesimli_topla(ns: argparse.Namespace, girdi=input) -> None:
    """Bayrakla verilmemiş alanları tek tek sorar (öneri/varsayılanla). ns yerinde doldurulur."""
    print("Yeni aXet SAP projesi — sorular (Enter = köşeli parantezdeki öneri). Kimlik bilgisi SORULMAZ.\n")
    if not ns.target:
        ns.target = sor("Proje klasörü (tam yol; yoksa oluşturulur)", d_klasor, girdi=girdi)
    if not ns.name:
        ns.name = sor("Proje adı", d_ad, Path(ns.target).expanduser().resolve().name, girdi=girdi)
    if not ns.sap_profile:
        ns.sap_profile = sor(f"SAP profili ({' | '.join(PROFILLER)})", d_profil, girdi=girdi)
    if not ns.release:
        ns.release = sor("SAP sürümü (ör. 2023; ECC'de EHP)", d_release, girdi=girdi)
    if not ns.master_language:
        ns.master_language = sor("master_language — Z obje metinlerinin dili, 2 harf (ör. TR, EN; emin değilsen ekip "
                                 "sorumlusuna sor)", d_dil, girdi=girdi)
    if ns.cleancore_policy is None and ns.sap_profile == POLITIKA_PROFILI:
        ns.cleancore_policy = sor(f"cleancore_policy ({' | '.join(POLITIKALAR)})", d_politika, "balanced", girdi=girdi)
    if not ns.source_root:
        ns.source_root = sor("source_root (paket klasörlerinin kökü)", d_source_root, VARSAYILAN_SOURCE_ROOT, girdi=girdi)
    if not ns.purpose:
        ns.purpose = sor("Amaç (kısa açıklama)", d_metin(True), girdi=girdi)
    if not ns.tech:
        ns.tech = sor("Teknoloji", d_metin(True), TEKNOLOJI[ns.sap_profile], girdi=girdi)
    if not ns.repo:
        oneri, depo_notu = depo_onerisi_ve_uyari(Path(ns.target).expanduser().resolve())
        if depo_notu:
            print(f"  ! UYARI: {depo_notu}")
        ns.repo = sor("Depo (remote adresi ya da yerel)", d_repo, oneri, girdi=girdi)
    for alan, soru in (("test_cmd", "Test komutu"), ("run_cmd", "Çalıştırma / derleme komutu"),
                       ("lint_cmd", "Doğrulama / lint komutu")):
        if getattr(ns, alan) is None:
            setattr(ns, alan, sor(soru, d_komut, "", girdi=girdi))
    if not ns.rule:
        ns.rule = []
        while True:
            k = sor(f"Proje kuralı #{len(ns.rule) + 1} (boş = bitir)", d_metin(False), "", girdi=girdi)
            if not k:
                break
            ns.rule.append(k)


def dogrula_ve_normalize(ns: argparse.Namespace, etkilesimli: bool) -> tuple[dict | None, list[str], list[str]]:
    """(değerler, hatalar, uyarılar)."""
    eksik = [bayrak for alan, bayrak in ZORUNLU_BAYRAK.items() if not getattr(ns, alan)]
    if ns.sap_profile == POLITIKA_PROFILI and not ns.cleancore_policy:
        eksik.append("--cleancore-policy (s4_private)")
    if eksik and not etkilesimli:
        return None, [f"eksik zorunlu alan(lar): {', '.join(eksik)}"], []
    hatalar, uyarilar = [], []
    hedef_s = ns.target or ""
    hata = d_klasor(hedef_s)
    if hata:
        hatalar.append(f"klasör: {hata}")
    hedef = Path(hedef_s).expanduser().resolve() if hedef_s.strip() else None
    ad = ns.name or (hedef.name if hedef else "")
    profil = ns.sap_profile or ""
    politika = (ns.cleancore_policy or "").strip()
    if profil and profil != POLITIKA_PROFILI and politika:
        uyarilar.append(f"cleancore_policy={politika!r} yok sayıldı: politika ekseni yalnız s4_private'ta var "
                        f"(references/profiles.md); {profil} için boş yazılır")
        politika = ""
    repo, depo_notu = ns.repo or "", None
    if not repo:
        repo, depo_notu = depo_onerisi_ve_uyari(hedef) if hedef and not hata else ("yerel", None)
    if depo_notu:
        uyarilar.append(f"depo: {depo_notu}")
    v = {
        "name": ad, "sap_profile": profil, "release": (ns.release or "").strip(),
        "master_language": (ns.master_language or "").strip().upper(), "cleancore_policy": politika,
        "source_root": (ns.source_root or VARSAYILAN_SOURCE_ROOT).strip(),
        "purpose": (ns.purpose or "").strip(), "tech": (ns.tech or TEKNOLOJI.get(profil, "")).strip(),
        "repo": repo.strip(),
        "test_cmd": (ns.test_cmd or "").strip(), "run_cmd": (ns.run_cmd or "").strip(),
        "lint_cmd": (ns.lint_cmd or "").strip(), "rules": [r.strip() for r in (ns.rule or []) if r.strip()],
    }
    ad_hatasi = d_ad(ad)
    kontroller = [("proje adı", ad_hatasi and (ad_hatasi + ("" if ns.name else " → --name ile ver"))),
                  ("sap_profile", d_profil(profil)), ("release", d_release(v["release"])),
                  ("master_language", d_dil(v["master_language"])),
                  ("cleancore_policy", d_politika(politika) if profil == POLITIKA_PROFILI else None),
                  ("source_root", d_source_root(v["source_root"])), ("amaç", d_metin(True)(v["purpose"])),
                  ("teknoloji", d_metin(True)(v["tech"])), ("depo", d_repo(v["repo"]))]
    kontroller += [(alan, d_komut(v[alan])) for alan in ("test_cmd", "run_cmd", "lint_cmd")]
    kontroller += [(f"kural {n}", d_metin(True)(r)) for n, r in enumerate(v["rules"], 1)]
    hatalar += [f"{ad_}: {h}" for ad_, h in kontroller if h]
    if not shutil.which("git"):
        hatalar.append("git bulunamadı (PATH) — pre-commit kablolaması için git gerekli")
    if hatalar:
        return None, hatalar, uyarilar
    v["target"] = hedef
    v["depo_uyarisi"] = depo_uyarisi(v["repo"])
    if v["depo_uyarisi"]:
        uyarilar.append(f"depo: {v['depo_uyarisi']}")  # main ÖZET'ten sonra basar (dry-run ve gerçek koşu)
    return v, [], uyarilar


def istenen_sap(v: dict) -> dict:
    return {"project": v["name"], "sap_profile": v["sap_profile"], "release": v["release"],
            "master_language": v["master_language"], "cleancore_policy": v["cleancore_policy"],
            "source_root": v["source_root"]}


def ozet(v: dict) -> None:
    print("\nÖZET")
    for etiket, deger in (("klasör", v["target"]), ("proje adı", v["name"]), ("sap_profile", v["sap_profile"]),
                          ("release", v["release"]), ("master_language", v["master_language"]),
                          ("cleancore_policy", v["cleancore_policy"] or "(boş — bu profilde politika ekseni yok)"),
                          ("source_root", v["source_root"]), ("amaç", v["purpose"]), ("teknoloji", v["tech"]),
                          ("depo", v["repo"]), ("test", v["test_cmd"] or KOMUT_YOK),
                          ("çalıştırma", v["run_cmd"] or KOMUT_YOK), ("doğrulama", v["lint_cmd"] or KOMUT_YOK),
                          ("kurallar", " | ".join(v["rules"]) or KURAL_YOK)):
        print(f"  {etiket:<17} {deger}")


# --- akış --------------------------------------------------------------------------------------------------------
# --- KURULUMU-TAMAMLA.cmd kısayolu (Z70) ---------------------------------------------------------------------------
# Kullanıcının kalan adımları (SAP bağlantısı · davranış yüzeyi onayı · doctor · aXet'i aç) template kökündeki
# proje-tamamla.cmd'de TEK yerde durur (%guncelle ile güncellenir). Proje köküne yalnız onu çağıran ince kısayol
# yazılır. Bu araç (ve aXet oturumu) kısayolu ÇALIŞTIRMAZ: iki adım kullanıcının kendi onayıdır.
KISAYOL = "KURULUMU-TAMAMLA.cmd"
TAMAMLA_CMD = "proje-tamamla.cmd"
# Z79: resmi kısayolun İŞARETİ (ikinci satırın başı). `%guncelle-proje` yalnız bu işareti taşıyan dosyayı yeniden
# yazar; işaretsiz dosya (elle yazılmış / Z70 öncesi geçici sürüm) kullanıcınındır, ezilmez.
KISAYOL_ISARETI = "rem aXet kurulum kisayolu (yeni_proje.py yazdi)"


def kisayol_metni(axet_home: Path | None = None) -> str:
    """Kısayol içeriği (CRLF, ASCII yorum). Klonun MUTLAK yolunu taşır — makineye özgü; şablon .gitignore'u
    bu yüzden dosyayı git'e kapatır. Klon yoksa pencere sessizce kapanmasın diye hata + pause."""
    k = str((axet_home or AXET_HOME) / TAMAMLA_CMD).replace("%", "%%")
    satirlar = ["@echo off",
                f"{KISAYOL_ISARETI}: cift tikla. Asil mantik aXet klonundaki "
                f"{TAMAMLA_CMD} dosyasinda.",
                # `exit /b` kodsuz → `cmd /c` altında 0 döner (ölçüldü); `call exit /b %%errorlevel%%` çağrı SONRASI kodu taşır
                f'if exist "{k}" call "{k}" "%~dp0." & call exit /b %%errorlevel%%',
                f"echo HATA: aXet klonu bulunamadi: \"{k}\" - aXet'i kur.cmd ile kur, sonra bu dosyaya tekrar cift tikla."
                " & pause & exit /b 1"]
    return "\r\n".join(satirlar) + "\r\n"


def kisayol_bayt(axet_home: Path | None = None) -> bytes:
    """Diske yazılan bayt. cmd.exe toplu iş dosyasını konsolun OEM kod sayfasıyla okur; UTF-8 yazılırsa ASCII dışı
    klon yolu bozulur. Kodlanamayan yol UnicodeEncodeError yükseltir (çağıran yakalar)."""
    return kisayol_metni(axet_home).encode("oem" if os.name == "nt" else "utf-8")


def kisayol_resmi_mi(veri: bytes) -> bool:
    """İkinci satır resmi işaretle mi başlıyor (Z79). İşaret ASCII'dir; kod sayfasından bağımsız okunur."""
    satirlar = veri.decode("latin-1").splitlines()
    return len(satirlar) > 1 and satirlar[1].startswith(KISAYOL_ISARETI)


def kisayol_durumu(hedef: Path, axet_home: Path | None = None) -> str:
    """'yok' | 'guncel' (bayt bayt beklenen) | 'farkli' (resmi ama içerik eski, ör. klon yolu değişti) |
    'resmi-degil' (işaretsiz — kullanıcınındır). `%guncelle-proje` planı bu sınıflamayla kurulur (Z79)."""
    f = hedef / KISAYOL
    if not f.exists():
        return "yok"
    veri = f.read_bytes()
    if not kisayol_resmi_mi(veri):
        return "resmi-degil"
    return "guncel" if veri == kisayol_bayt(axet_home) else "farkli"


def kisayol_yaz(hedef: Path, axet_home: Path | None = None, guncelle: bool = False) -> tuple[str, str]:
    """('yazildi' | 'guncellendi' | 'korundu' | 'yazilamadi', açıklama). Var olan dosya EZİLMEZ (merge-safe, Z70).
    `guncelle=True` (yalnız `%guncelle-proje`, Z79): var olan dosya RESMİ işaretliyse yeniden yazılır; işaretsizse
    yine ezilmez. Yeni proje akışı varsayılan kipi kullanır — davranışı değişmedi."""
    f = hedef / KISAYOL
    try:
        veri = kisayol_bayt(axet_home)
        if f.exists():
            if not (guncelle and kisayol_resmi_mi(f.read_bytes())):
                return "korundu", f"{f} zaten var — ezilmedi"
            gecici = f.with_name(f.name + ".yeni")
            gecici.write_bytes(veri)
            os.replace(gecici, f)       # yarım yazılmış kısayol kalmasın
            return "guncellendi", str(f)
        with open(f, "xb") as fh:  # x: arada biri yazdıysa da ezme
            fh.write(veri)
    except (OSError, UnicodeEncodeError, LookupError) as exc:
        return "yazilamadi", f"{type(exc).__name__}: {exc}"
    return "yazildi", str(f)


def plan(v: dict) -> int:
    """--dry-run: hiçbir şey yazmaz; gerçek koşunun doldurma/denetim fonksiyonlarını bellekte koşar. Gerçek koşu
    çıkış 1 verecekse (JSON okunamaz, ÇELİŞKİ, şablon satırı kalır) 1 döner."""
    hedef: Path = v["target"]
    sorun = False
    print("\nPLAN (dry-run — hiçbir şey yazılmadı)")
    print(f"  1. klasör: {'var' if hedef.is_dir() else 'YOK → oluşturulacak'} ({hedef})")
    print(f"  2. git: {'repo kökü — dokunulmayacak' if git_durumu(hedef) == 'kok' else 'git reposu değil → git init -b main'}")
    print(f"  3. new_project.py \"{hedef}\" --sap --name {v['name']}  (var olan dosyalar ezilmez; pre-commit kablolanır)")
    sj = hedef / "sap-project.json"
    sap = None
    try:
        metin = (sj.read_text(encoding="utf-8-sig") if sj.is_file()
                 else new_project._doldur((new_project.TEMPLATE_SAP / "sap-project.json").read_text(encoding="utf-8"), v["name"]))
        _, rapor, korunan, veri = sap_json_doldur(metin, istenen_sap(v), yeni=not sj.is_file())
        print("  4. sap-project.json" + (" (var olan dosya)" if sj.is_file() else " (şablondan)"))
        print("\n".join("  " + r for r in rapor))
        kritik, uyari = celiski_ayir(korunan)
        for x in uyari:
            print(f"     ! UYARI: {x}")
        for x in kritik:
            print(f"     ! {x}")
        sorun |= bool(kritik)
        sap = sap_degerleri(veri)
    except (ValueError, OSError) as exc:
        print(f"  4. sap-project.json OKUNAMADI ({type(exc).__name__}: {exc}) — gerçek koşuda dokunulmaz, çıkış 1")
        sorun = True
    ag = hedef / "AGENTS.md"
    try:
        # gerçek koşuyla AYNI katılık: new_project.py AGENTS.md'yi katı UTF-8 okur (YENİ-3)
        metin = (ag.read_text(encoding="utf-8") if ag.is_file()
                 else new_project._doldur((new_project.TEMPLATE / "AGENTS.md").read_text(encoding="utf-8"), v["name"]))
        yeni, rapor = agents_doldur(metin, v, sap)
        print("  5. AGENTS.md" + (" (var olan dosya)" if ag.is_file() else " (şablondan)") + " doldurulacak: "
              + (", ".join(rapor) if rapor else "şablon satırı yok"))
        kalan = sablon_kalanlari(yeni)
        if kalan:
            print(f"     ! doldurulamayacak şablon satırı: {', '.join(kalan)} → gerçek koşuda FAIL")
            sorun = True
        diger = diger_yer_tutucular(yeni)
        if diger:
            print(f"     ! UYARI: kullanıcı satırlarında yer tutucu ({len(diger)}): {', '.join(diger[:5])} — dokunulmayacak")
        if sap:
            sd, ayrinti = sap_satiri_denetle(yeni, sap)
            if sd == "celiski":
                print(f"     ! AGENTS.md SAP satırı sap-project.json ile çelişiyor: {'; '.join(ayrinti)} → gerçek koşuda FAIL")
                sorun = True
            elif sd == "olculemedi":
                print(f"     ! AGENTS.md SAP satırı ↔ sap-project.json ÖLÇÜLEMEDİ: {'; '.join(ayrinti)} → gerçek koşuda FAIL")
                sorun = True
    except RuntimeError as exc:
        print(f"  5. AGENTS.md: {SABLON_BOZUK} — {exc}")
        sorun = True
    except (OSError, ValueError) as exc:
        print(f"  5. AGENTS.md OKUNAMADI ({type(exc).__name__}: {exc}) — UTF-8 değilse UTF-8 olarak kaydet; "
              "gerçek koşuda çıkış 1")
        sorun = True
    print("  6. doğrulama: sap-project.json geçerli · şablon satırı kalmadı · SAP satırı tutarlı · core.hooksPath=.githooks")
    print("  7. doctor.py (proje kökünde) — FAIL varsa çıkış 1")
    print(f"  8. {KISAYOL}: " + ("var — ezilmeyecek [KORUNDU]" if (hedef / KISAYOL).exists()
                                 else f"yazılacak (kurulum başarılıysa; {AXET_HOME / TAMAMLA_CMD} dosyasını çağırır)"))
    if sorun:
        print("PLAN SORUNLU — gerçek koşu çıkış 1 verir; önce yukarıdaki ! satırlarını çöz.")
        return 1
    print("Gerçek kurulum için aynı komutu --dry-run olmadan çalıştır.")
    return 0


def kur(v: dict) -> int:
    hedef: Path = v["target"]
    sorunlar: list[str] = []
    # depo uyarısı kurulum sonundaki UYARILAR bölümünde de tekrar edilir (uzun çıktıda ÖZET altındaki satır kaybolur)
    uyarilar: list[str] = [f"depo: {v['depo_uyarisi']}"] if v.get("depo_uyarisi") else []
    print("\nKURULUM")
    ag = hedef / "AGENTS.md"
    if ag.exists():
        # new_project.py var olan AGENTS.md'yi katı UTF-8 okur, çözemezse traceback ile düşer (yeniden inceleme E3b);
        # hiçbir şey yazmadan önce aynı katılıkla burada yakalanır.
        try:
            ag.read_text(encoding="utf-8")
        except (OSError, ValueError) as exc:
            print(f"HATA: AGENTS.md okunamadı ({type(exc).__name__}: {exc}) — dosyayı UTF-8 olarak kaydet, sonra aracı "
                  "yeniden çalıştır. Hiçbir şey yazılmadı, new_project.py çalıştırılmadı.")
            return 1
    try:
        if not hedef.is_dir():
            hedef.mkdir(parents=True)
            print(f"  [oluşturuldu] klasör {hedef}")
    except OSError as exc:
        print(f"HATA: klasör oluşturulamadı ({type(exc).__name__}: {exc})")
        return 1
    if git_durumu(hedef) == "yok":
        r = git("init", "-b", "main", cwd=hedef)
        if r.returncode != 0:
            print(f"HATA: git init başarısız: {r.stderr.strip()}")
            return 1
        print("  [git] git init -b main")
    else:
        print("  [git] zaten repo kökü — dokunulmadı")

    sj = hedef / "sap-project.json"
    sj_yeni = not sj.exists()
    print(f"\n  new_project.py --sap --name {v['name']}")
    # --no-next-steps: new_project'in "Sonraki adımlar" listesi burada otomatik yapılanları da içerir; kalanlar sonda
    # basılır. Liste bayrakla hiç üretilmez — çıktı metnini başlığından bölmeye (metin sözleşmesine) dayanılmaz.
    r = subprocess.run([sys.executable, str(SCRIPTS / "new_project.py"), str(hedef), "--sap", "--name", v["name"],
                        "--no-next-steps"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL,
                       env=temiz_ortam())
    print("  " + r.stdout.rstrip().replace("\n", "\n  ") + (r.stderr or ""))
    if r.returncode != 0:
        print(f"HATA: new_project.py çıkış {r.returncode} — yukarıdaki satırı düzelt, sonra aracı yeniden çalıştır "
              "(var olanı ezmez)")
        return 1

    print()
    sap = None
    try:
        eski = sj.read_text(encoding="utf-8-sig")
        yeni_json, rapor, korunan, veri = sap_json_doldur(eski, istenen_sap(v), sj_yeni)
        print("\n".join(rapor))
        if yeni_json != eski:
            sj.write_text(yeni_json, encoding="utf-8")
        sap = sap_degerleri(veri)  # yalnız yazma başarılıysa: AGENTS.md diskteki json'la aynı değeri taşısın
        kritik, uyari = celiski_ayir(korunan)
        for x in kritik:
            print(f"  ! {x}")
        sorunlar += kritik
        uyarilar += uyari
    except (ValueError, OSError) as exc:
        print(f"  [DOKUNULMADI] sap-project.json okunamadı/yazılamadı: {type(exc).__name__}: {exc}")
        sorunlar.append(f"sap-project.json okunamadı/yazılamadı ({type(exc).__name__}: {exc})")

    ag = hedef / "AGENTS.md"
    try:
        metin = ag.read_text(encoding="utf-8")
        yeni, rapor = agents_doldur(metin, v, sap)
        if yeni != metin:
            ag.write_text(yeni, encoding="utf-8")
        print("  [AGENTS.md] " + ("dolduruldu: " + ", ".join(rapor) if rapor else "şablon satırı yoktu — dokunulmadı")
              + ("" if sap else " (SAP satırı doldurulmadı: sap-project.json okunamadı)"))
    except RuntimeError as exc:
        print(f"  [YAZILAMADI] AGENTS.md: {SABLON_BOZUK} — {exc}")
        sorunlar.append(f"AGENTS.md: {SABLON_BOZUK} ({exc})")
    except (OSError, ValueError) as exc:
        print(f"  [YAZILAMADI] AGENTS.md: {type(exc).__name__}: {exc}")
        sorunlar.append(f"AGENTS.md okunamadı/yazılamadı ({type(exc).__name__}: {exc})")

    print("\nDOĞRULAMA")
    durum, mesaj = doctor.sap_proje_dogrula(hedef)
    print(f"  [{'PASS' if durum == 'gecerli' else 'FAIL'}] sap-project.json: {mesaj}")
    if durum != "gecerli":
        sorunlar.append(f"sap-project.json: {mesaj}")
    try:
        son_metin = ag.read_text(encoding="utf-8")
        kalan = sablon_kalanlari(son_metin)
        print(f"  [{'FAIL' if kalan else 'PASS'}] AGENTS.md şablon yer tutucusu: " + (", ".join(kalan) if kalan else "yok"))
        if kalan:
            sorunlar.append(f"AGENTS.md'de doldurulmamış şablon yer tutucusu: {', '.join(kalan)}")
        diger = diger_yer_tutucular(son_metin)
        if diger:
            print(f"  [WARN] kullanıcı satırlarında yer tutucu ({len(diger)}): {', '.join(diger[:5])} — dokunulmadı")
            uyarilar.append(f"AGENTS.md kullanıcı satırlarında yer tutucu: {', '.join(diger[:5])}")
        try:
            disk_sap = sap_degerleri(json.loads(sj.read_text(encoding="utf-8-sig")))
        except (OSError, ValueError):
            disk_sap = None
        sd, ayrinti = (sap_satiri_denetle(son_metin, disk_sap) if disk_sap
                       else ("olculemedi", ["sap-project.json okunamadı"]))
        if sd == "tutarli":
            print("  [PASS] AGENTS.md SAP satırı ↔ sap-project.json: tutarlı")
        elif sd == "celiski":
            print(f"  [FAIL] AGENTS.md SAP satırı ↔ sap-project.json: {'; '.join(ayrinti)}")
            sorunlar.append(f"AGENTS.md SAP satırı sap-project.json ile çelişiyor ({'; '.join(ayrinti)}) → hangisi doğruysa "
                            "diğerini elle düzelt (bu araç doldurulmuş satırı yeniden yazmaz)")
        else:
            print(f"  [FAIL] AGENTS.md SAP satırı ↔ sap-project.json ÖLÇÜLEMEDİ: {'; '.join(ayrinti)}")
            sorunlar.append(f"AGENTS.md SAP satırı ↔ sap-project.json ÖLÇÜLEMEDİ ({'; '.join(ayrinti)}) → satırı "
                            "`- SAP (varsa): sistem profili <profil> · … · master_language: <XX>` biçiminde yaz")
    except RuntimeError as exc:
        print(f"  [FAIL] AGENTS.md denetlenemedi: {SABLON_BOZUK} — {exc}")
        sorunlar.append(f"AGENTS.md denetlenemedi: {SABLON_BOZUK} ({exc})")
    except (OSError, ValueError) as exc:
        print(f"  [FAIL] AGENTS.md denetlenemedi: {type(exc).__name__}: {exc}")
        sorunlar.append(f"AGENTS.md denetlenemedi ({type(exc).__name__}: {exc})")
    hp = git("config", "--get", "core.hooksPath", cwd=hedef).stdout.strip()
    print(f"  [{'PASS' if hp.rstrip('/') == '.githooks' else 'FAIL'}] pre-commit: core.hooksPath={hp or '(ayarsız)'}")
    if hp.rstrip("/") != ".githooks":
        sorunlar.append(f"core.hooksPath {hp or 'ayarsız'} — pre-commit denetimi koşmaz")

    print("\nDOCTOR (proje kökünde)")
    sys.stdout.flush()
    rd = subprocess.run([sys.executable, str(SCRIPTS / "doctor.py")], cwd=str(hedef), capture_output=True, text=True,
                        encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, env=temiz_ortam())
    print(rd.stdout.rstrip() + (("\n" + rd.stderr.rstrip()) if rd.stderr.strip() else ""))
    if rd.returncode != 0:
        sorunlar.append(f"doctor.py çıkış {rd.returncode} (FAIL satırlarına bak)")

    if uyarilar:
        print("\nUYARILAR (çıkış kodunu etkilemez)\n" + "\n".join(f"  - {u}" for u in uyarilar))
    if sorunlar:
        print("\nSONUÇ: KURULUM EKSİK\n" + "\n".join(f"  - {s}" for s in sorunlar)
              + "\nDüzeltip aracı yeniden çalıştır (var olanı ezmez).")
        return 1
    durum, aciklama = kisayol_yaz(hedef)
    etiket = {"yazildi": "[yazıldı]", "korundu": "[KORUNDU]", "yazilamadi": "[YAZILAMADI]"}[durum]
    print(f"\n  {etiket} {KISAYOL}: {aciklama}")
    if durum != "yazilamadi" and git("check-ignore", "-q", KISAYOL, cwd=hedef).returncode != 0:
        # Var olan .gitignore'a new_project satır eklemez (ezmez) → bu projede kısayol git'e açık olabilir.
        print(f"  ! UYARI: {KISAYOL} git'e kapalı değil — makineye özgü mutlak yol taşır; .gitignore'a "
              f"`{KISAYOL}` satırını ekle, commit etme")
    tamamla = AXET_HOME / TAMAMLA_CMD
    print(f"\nSONUÇ: proje kuruldu ({hedef}) · doctor 0 FAIL")
    if durum == "yazilamadi":
        print(f"SON ADIM (SENDE): {TAMAMLA_CMD}'ye çift tıkla ya da kendi terminalinde çalıştır: \"{tamamla}\" \"{hedef}\"")
    else:
        print(f"SON ADIM (SENDE): proje klasöründeki {KISAYOL}'ye çift tıkla — pencere SAP bağlantı dosyalarını "
              "hazırlar (conn\\DEV.env zorunlu, conn\\QA.env isteğe bağlı) ve hangi dosyaya hangi alanları yazacağını "
              "tam yoluyla söyler (editör açmaz, soru sormaz). Dosyayı doldurup kaydet, tekrar çift tıkla: ayar onayı, "
              "kontrol ve aXet'i açma sırayla sorulur.")
    print(f"  Not: aXet oturumu bu adımları çalıştırmaz (parola ve onay sende kalır). Elle: \"{tamamla}\" \"{hedef}\"")
    return 0


def main(argv: list[str] | None = None, girdi=input) -> int:
    ap = argparse.ArgumentParser(description="Sorarak aXet SAP projesi kurar (new_project.py --sap + alan doldurma + doctor)")
    ap.add_argument("target", nargs="?", help="proje klasörü (yoksa oluşturulur)")
    ap.add_argument("--name", help="proje adı (varsayılan: klasör adı)")
    ap.add_argument("--sap-profile", help=" | ".join(PROFILLER))
    ap.add_argument("--release", help="SAP sürümü (ör. 2023)")
    ap.add_argument("--master-language", help="Z obje metin dili, 2 harf (ör. TR)")
    ap.add_argument("--cleancore-policy", help=f"{' | '.join(POLITIKALAR)} (yalnız s4_private; orada zorunlu)")
    ap.add_argument("--source-root", help=f"paket klasörlerinin kökü (varsayılan: {VARSAYILAN_SOURCE_ROOT})")
    ap.add_argument("--purpose", help="amaç (kısa açıklama)")
    ap.add_argument("--tech", help="teknoloji (varsayılan: profilden)")
    ap.add_argument("--repo", help="remote adresi ya da 'yerel' (varsayılan: origin, yoksa yerel; kimlik bilgisi reddedilir)")
    ap.add_argument("--test-cmd", help="test komutu (boş: 'henüz tanımlı değil')")
    ap.add_argument("--run-cmd", help="çalıştırma / derleme komutu")
    ap.add_argument("--lint-cmd", help="doğrulama / lint komutu")
    ap.add_argument("--rule", action="append", help="proje kuralı (tekrarlanabilir; yoksa nötr varsayılan)")
    ap.add_argument("--dry-run", action="store_true", help="hiçbir şey yazmadan planı göster")
    mod = ap.add_mutually_exclusive_group()
    mod.add_argument("--interactive", action="store_true", help="eksik alanları sor (terminal tespitini zorlar)")
    mod.add_argument("--no-input", action="store_true", help="asla soru sorma; eksik zorunlu alan → çıkış 2")
    ns = ap.parse_args(argv)

    etkilesimli = ns.interactive or (not ns.no_input and etkilesimli_mi())
    if etkilesimli:
        try:
            etkilesimli_topla(ns, girdi)
        except Kesinti as exc:
            print(f"\nHATA: {exc} — hiçbir şey yazılmadı")
            return 2
    v, hatalar, uyarilar = dogrula_ve_normalize(ns, etkilesimli)
    if hatalar:
        print("HATA: girdi geçersiz — hiçbir şey yazılmadı\n" + "\n".join(f"  - {h}" for h in hatalar))
        if not etkilesimli:
            print("Etkileşimsiz mod (terminal yok ya da --no-input). Örnek:\n  python yeni_proje.py <KLASÖR> --no-input "
                  "--sap-profile s4_private --release 2023 --master-language TR --cleancore-policy balanced "
                  "--purpose \"<amaç>\"")
        return 2
    ozet(v)
    for u in uyarilar:
        print(f"  ! UYARI: {u}")
    if ns.dry_run:
        return plan(v)
    if etkilesimli:
        try:
            onay = girdi("\nBu değerlerle kurulsun mu? [e/H]: ").strip().lower()
        except EOFError:
            onay = ""
        if onay not in ("e", "evet", "y", "yes"):
            print("İptal edildi — hiçbir şey yazılmadı.")
            return 2
    return kur(v)


if __name__ == "__main__":
    sys.exit(main())
