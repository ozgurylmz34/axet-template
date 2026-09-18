#!/usr/bin/env python3
"""aXet.code template kurulum doğrulaması.

Kullanım:
  python <TEMPLATE>/scripts/doctor.py          statik kontroller (model çağrısı yok)
  python <TEMPLATE>/scripts/doctor.py --live   + aXet'e bağlamında gördüğü kimlik satırlarını sorar
                                               (bir model çağrısı yapar; kurumsal denetime kaydolur)
Bulunulan dizin bir projeyse proje iskeleti de kontrol edilir. Çıkış kodu: FAIL varsa 1.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install as inst  # noqa: E402  (aynı klasördeki kurulum sabitleri)
import sap_stamp  # noqa: E402  (kesin yasak damgası)
import new_package as npk  # noqa: E402  (paket katmanı)
import behavior_manifest as bm  # noqa: E402  (davranış yüzeyi)
import new_project as nprj  # noqa: E402  (proje şablonu sürüm kaydı — TASARIM §9 tetiği)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

results: list[tuple[str, str]] = []


def add(status: str, msg: str) -> None:
    results.append((status, msg))


def read_id(path: Path, key: str) -> str | None:
    if not path.exists():
        return None
    m = re.search(rf"^{re.escape(key)}:\s*(\S+)", path.read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else None


def contains(paths: list, target: Path) -> bool:
    return any(isinstance(p, str) and os.path.isabs(p) and inst._norm(p) == inst._norm(target) for p in paths)


def _kurallar(cfg: dict) -> dict:
    """`permissions.rules`; ara düzeylerden biri nesne değilse boş (çökmez)."""
    perms = cfg.get("permissions")
    rules = perms.get("rules") if isinstance(perms, dict) else None
    return rules if isinstance(rules, dict) else {}


def check_global() -> tuple[dict, bool]:
    cfg_file = inst.config_path()
    if not cfg_file.exists():
        add("FAIL", f"global config yok: {cfg_file} → python scripts/install.py")
        return {}, False
    veri, hata = _json_oku(cfg_file)
    if hata is not None:
        add("FAIL", f"global config geçerli JSON değil ya da okunamadı (UTF-8?): {cfg_file} ({hata})")
        return {}, False
    if not isinstance(veri, dict):
        add("FAIL", f"global config kök değeri nesne değil ({type(veri).__name__}): {cfg_file} → install.py ile yeniden kur")
        return {}, False
    cfg = veri
    add("PASS", f"global config okundu: {cfg_file}")
    opts = cfg.get("options") or {}
    if not isinstance(opts, dict):
        add("FAIL", f"global config 'options' nesne değil ({type(opts).__name__}) → context_paths/skills_paths ÖLÇÜLEMEDİ; "
                    "install.py ile düzelt")
        opts = {}
    ctx, skills = opts.get("context_paths") or [], opts.get("skills_paths") or []
    ctx, skills = (ctx if isinstance(ctx, list) else []), (skills if isinstance(skills, list) else [])
    for label, lst, target in (("context_paths", ctx, inst.CORE_FILE), ("context_paths", ctx, inst.TEAM_MEMORY),
                               ("skills_paths", skills, inst.SKILLS_DIR)):
        add("PASS" if contains(lst, target) else "FAIL", f"{label} içinde {target}")
    sap = inst.sap_enabled({"options": {"context_paths": ctx}})
    if sap:
        add("PASS" if contains(skills, inst.SAP_SKILLS_DIR) else "FAIL", f"SAP paketi AÇIK · skills_paths içinde {inst.SAP_SKILLS_DIR}")
    else:
        add("INFO", "SAP paketi KAPALI (açmak için: install.py --sap)")
    for p in [p for p in ctx + skills if inst.is_ours(p)]:
        if not Path(p).exists():
            add("FAIL", f"config'teki yol diskte yok: {p}")
    prules = _kurallar(cfg)
    missing = [f"{d}:{pat}" for d, pats in inst.load_rules().items() for pat, dec in pats.items()
               if not isinstance(prules.get(d), dict) or prules[d].get(pat) != dec]
    add("PASS" if not missing else "WARN", "izin kuralları eksiksiz" if not missing else f"eksik/farklı izin kuralı: {missing}")
    # K4b: install.py'yi yeniden koşmamış makinede önceki sürümün desenleri kalır; başa bağlı desen zincirli komutu
    # kaçırır, uzun ask aynı komuta uyan deny'ı ezer (ölçüldü 2026-09-14). Ölçüt install.strip_ours'un kendisi.
    emekli = emekli_izin_desenleri(cfg)
    if emekli["emekli_silinen"]:
        add("WARN", f"global config'te emekli template izin deseni kaldı ({len(emekli['emekli_silinen'])}): "
                    + ", ".join(emekli["emekli_silinen"])
                    + " — önceki sürümün kuralı; uzun ask yeni deny'ı ezebilir, başa bağlı desen zincirli komutu kaçırır → "
                    f"install.py'yi yeniden koş (SAP durumu korunur, önce yedek alır, yalnız template'in yazdığı kararı "
                    f"siler): python \"{(inst.AXET_HOME / 'scripts' / 'install.py').as_posix()}\"")
    for satir in emekli["emekli_korunan"]:
        add("INFO", f"global config'te emekli template izin deseni kullanıcı kararıyla duruyor, install.py dokunmaz: {satir}"
                    " — bilinçliyse sorun yok")
    ezme = ezebilen_izin_desenleri(cfg)
    for b in ezme[:EZME_EN_COK_SATIR]:
        gosterilen = b["denyler"][:EZME_EN_COK_DENY]
        fazla = len(b["denyler"]) - len(gosterilen)
        add("WARN", f"global config izin deseni template deny'ını uzunlukla ezebilir: {b['arac']}:{b['desen']} "
                    f"({b['karar']}; sabit {_sabit(b['desen'])}, toplam {len(b['desen'])}) → ezebileceği deny: "
                    + ", ".join(f"{d} (sabit {_sabit(d)}, toplam {len(d)})" for d in gosterilen)
                    + (f" ve {fazla} deny daha" if fazla else "")
                    + " — aynı komuta uyan iki desenden UZUN olan kazanır, eşitlikte ask (ölçüldü 2026-09-14, "
                      "aXet.code 1.3.0; sabit mi toplam mı DOĞRULANMADI) ve ask etkileşimsiz `run` kipinde SORMADAN "
                      "onaylar → deseni her deny'dan hem sabit hem toplam uzunlukta KESİN kısa yaz ya da bilinçliyse "
                      "yok say")
    if len(ezme) > EZME_EN_COK_SATIR:
        add("WARN", f"… ve {len(ezme) - EZME_EN_COK_SATIR} izin deseni daha template deny'ını uzunlukla ezebilir "
                    f"(yalnız ilk {EZME_EN_COK_SATIR} satır yazıldı)")
    return cfg, sap


def emekli_izin_desenleri(cfg: dict) -> dict:
    """Yeniden kurulumun sileceği (`emekli_silinen`) ve kullanıcı kararı olduğu için koruyacağı (`emekli_korunan`)
    emekli desenler. Liste (`install.RETIRED_RULES`) ve karar karşılaştırması install.py'de tek kopya: `strip_ours`
    config'in KOPYASINDA koşulur (kopyalanan ölçüt yok)."""
    return inst.strip_ours(copy.deepcopy(cfg), inst.load_rules())


# --- K12: canlı config'teki uzun `ask`/`allow` deseni template `deny`ını ezebilir ------------------------------------
# Ölçüldü (2026-09-14, aXet.code 1.3.0, tek ölçüm serisi): aynı komuta bir ask ve bir deny deseni birlikte uyunca UZUN
# desen kazanır, eşitlikte ask kazanır, kural sırası etkisizdir; ask etkileşimsiz `run` kipinde sormadan onaylar.
# Uzunluğun `*` hariç sabit karakterle mi toplam uzunlukla mı ölçüldüğü DOĞRULANMADI → ikisi birden denetlenir
# (tests/test_install.py `IzinDesenUzunlukTest` ile AYNI ölçüt). Fark: o test TEMPLATE dosyasına bakar, buradaki
# kontrol KULLANICININ CANLI config'ini okur — kullanıcının kendi yazdığı uzun ask/allow deseni başka hiçbir yerde
# görünmüyordu. Vaka: `*Remove-Item*-Recurse*` (ask) `*git reset --hard*` (deny) ile aynı zincirli komuta uydu,
# uzun olduğu için kazandı ve komut sorulmadan çalıştı. Karar (kullanıcı 2026-09-15): "Ekle, yalnız WARN" —
# rapor eder, engellemez (ADR 0019 gate moratoryumu).
EZME_EN_COK_SATIR = 10   # bundan fazlası tek özet satırına düşer (gürültü sınırı)
EZME_EN_COK_DENY = 3     # bir desenin ezebileceği deny'lardan satıra yazılan sayı
_KESISIM_DURUM_SINIRI = 20000  # çarpım otomatı bu kadar durumda bitmezse "çakışıyor" sayılır (sessiz kalmaktansa uyar)


def _sabit(desen: str) -> int:
    """Desenin `*` hariç karakter sayısı (ölçütlerden biri; hangisinin gerçek olduğu DOĞRULANMADI)."""
    return len(desen.replace("*", ""))


def _glob_kapanis(desen: str, konumlar) -> frozenset:
    """Glob NFA'sının epsilon-kapanışı. Durum = desendeki karakter indeksi; `*` boş dizgiye de uyabildiği için
    `i` durumundan `i+1`'e karakter tüketmeden geçilir. `len(desen)` = kabul durumu."""
    S = set(konumlar)
    yigin = list(S)
    while yigin:
        i = yigin.pop()
        if i < len(desen) and desen[i] == "*" and (i + 1) not in S:
            S.add(i + 1)
            yigin.append(i + 1)
    return frozenset(S)


def _glob_gecis(desen: str, S: frozenset, c: str) -> frozenset:
    yeni = set()
    for i in S:
        if i >= len(desen):
            continue
        if desen[i] == "*":
            yeni.add(i)          # `*` bu karakteri yutar, durum ilerlemez
        elif desen[i] == c:
            yeni.add(i + 1)
    return _glob_kapanis(desen, yeni)


def glob_kesisir(a: str, b: str) -> bool:
    """İki izin deseni AYNI komut metnine uyabilir mi (kesişimleri boş değil mi)?

    İki glob NFA'sının çarpım otomatı gezilir; her ikisi de kabul durumundaysa ortak bir metin vardır. Alfabe
    sonlu tutulur: iki desende geçen sabit karakterler + ikisinde de geçmeyen TÜM karakterleri temsil eden tek
    nöbetçi (`\\x00`) — o karakterleri yalnız `*` yutabildiği için iki desen de onları ayırt edemez.

    Sınır: joker olarak YALNIZ `*` tanınır; `?` ve `[...]` düz harf sayılır (aXet izin desenlerinde kullanılmıyor).
    aXet'in gerçek eşleştiricisi ÇALIŞTIRILMAZ; bu, desen metinleri üzerinde yapılan bir üst-sınır hesabıdır.
    """
    alfabe = ((set(a) | set(b)) - {"*"}) | {"\x00"}
    basla = (_glob_kapanis(a, {0}), _glob_kapanis(b, {0}))
    gorulen, kuyruk = {basla}, [basla]
    while kuyruk:
        Sa, Sb = kuyruk.pop()
        if len(a) in Sa and len(b) in Sb:
            return True
        if len(gorulen) > _KESISIM_DURUM_SINIRI:
            return True  # ölçülemedi → sessiz kalma, uyar
        for c in alfabe:
            yeni = (_glob_gecis(a, Sa, c), _glob_gecis(b, Sb, c))
            if yeni[0] and yeni[1] and yeni not in gorulen:
                gorulen.add(yeni)
                kuyruk.append(yeni)
    return False


def _kesin_kisa(izin: str, deny: str) -> bool:
    """`izin` deseni `deny`dan HEM sabit HEM toplam uzunlukta kesin kısa mı (yani deny'ı ezemez)?"""
    return _sabit(izin) < _sabit(deny) and len(izin) < len(deny)


def ezebilen_izin_desenleri(cfg: dict, template_kurallari: dict | None = None) -> list[dict]:
    """Canlı config'teki `ask`/`allow` desenlerinden, AYNI araç alanındaki bir template `deny` desenini uzunlukla
    ezebilecek olanlar: `[{"arac", "desen", "karar", "denyler"}]`.

    Riskli sayılma koşulu: desen o deny ile çakışıyor (aynı komut metnine ikisi de uyabiliyor) VE deny'dan kesin
    kısa değil. Karşılaştırma yalnız TEMPLATE deny desenlerine karşı yapılır; kullanıcının kendi deny kuralları
    ölçüye girmez (bu kontrol template'in koruma katmanının delinip delinmediğini ölçer)."""
    kurallar = inst.load_rules() if template_kurallari is None else template_kurallari
    bulgular: list[dict] = []
    for arac, desenler in sorted(_kurallar(cfg).items()):
        if not isinstance(desenler, dict):
            continue
        denyler = [p for p, v in (kurallar.get(arac) or {}).items() if v == "deny" and isinstance(p, str)]
        for desen, karar in desenler.items():
            if karar not in ("ask", "allow") or not isinstance(desen, str):
                continue
            ezilen = [d for d in denyler if not _kesin_kisa(desen, d) and glob_kesisir(desen, d)]
            if ezilen:
                # en KISA deny önce: düzeltmede bağlayıcı kısıt odur (desen hepsinden kısa olmalı)
                bulgular.append({"arac": arac, "desen": desen, "karar": karar,
                                 "denyler": sorted(ezilen, key=lambda d: (_sabit(d), len(d), d))})
    return bulgular


def frontmatter_problems(text: str) -> list[str]:
    """SKILL.md frontmatter'ında aXet'in YAML ayrıştırıcısını bozan kalıpları bulur (pyyaml gerektirmez).

    Ölçülmüş vaka: tırnaksız tek satırlık değerde `: ` → aXet 'Failed to parse skill file' WARN'u yazıp
    skill'i sessizce düşürür. Kontrol bilinçli olarak dar tutuldu: yalnız üst seviye `anahtar: değer` satırları.
    """
    m = re.match(r"^---\r?\n(.*?)\r?\n---", text, re.S)
    if not m:
        return ["frontmatter bloğu yok (--- … ---)"]
    problems, keys = [], set()
    for line in m.group(1).splitlines():
        if not line.strip() or line[0] in " \t#":
            continue
        key, sep, value = line.partition(":")
        if not sep:
            problems.append(f"anahtar:değer biçiminde olmayan satır: {line[:60]!r}")
            continue
        keys.add(key.strip())
        value = value.strip()
        if value and value[0] not in ">|\"'" and (": " in value or " #" in value):
            problems.append(f"'{key.strip()}' tırnaksız değerde ': ' ya da ' #' var → `>` blok biçimi kullan")
    problems += [f"'{k}' alanı yok" for k in ("name", "description") if k not in keys]
    # Ölçüldü (aXet 1.3.0): açıklama 1024 karakteri aşarsa log'a 'description exceeds 1024 characters'
    # yazılır ve skill yüklenmez.
    desc = _yaml_deger(m.group(1), "description")
    if desc is not None and len(desc) > 1024:
        problems.append(f"'description' {len(desc)} karakter (aXet sınırı 1024 → skill yüklenmez)")
    return problems


def _yaml_deger(blok: str, anahtar: str) -> str | None:
    """Üst seviye bir anahtarın değeri; `>` (katlanmış) ve `|` blok biçimleri desteklenir (yaklaşık, pyyaml'sız)."""
    satirlar = blok.splitlines()
    for i, satir in enumerate(satirlar):
        if not satir.startswith(anahtar + ":"):
            continue
        deger = satir[len(anahtar) + 1:].strip()
        if deger[:1] in (">", "|"):
            govde = []
            for s in satirlar[i + 1:]:
                if s.strip() and s[0] not in " \t":
                    break
                govde.append(s.strip())
            return (" " if deger[0] == ">" else "\n").join(g for g in govde if g).strip()
        return deger.strip("\"'")
    return None


# --- skill envanteri (Y8): template skill'leri ↔ template dışı (marketplace/proje/ortam) skill'ler ---------------------
# Ölçüldü (aXet 1.3.0, _lab/y8, tek koşu): skill keşfi `options.skills_paths` (global + proje config birleşir) +
# `<proje>/.axet-code/skills` + `AXET_SKILLS_DIR`. Aynı adlı iki skill model listesine İKİSİ BİRDEN girer, log'da
# uyarı yok (M3). Marketplace `skill_install` kaydı `%LOCALAPPDATA%\axet-code\skills_manifest.json`'a düşer (M2).
# SAP konusu: güçlü terimler tek başına sayılır; `adt`/`transport`/`deploy` genel kelimeler (ör. "abstract data type")
# olduğu için yalnız güçlü bir terimle AYNI metinde geçerse eklenir (gitlab/CI skill'lerinde gürültü üretmesin).
# `SAP` yalnız BÜYÜK harfle güçlüdür (Türkçe "sap" = bıçak sapı); `SAP'ye` gibi ekli hâller \b ile yakalanır.
SAP_GUCLU_BUYUK = re.compile(r"\b(SAP)\b")
SAP_GUCLU = re.compile(r"\b(abap|abapgit|s/?4\s?hana)\b", re.I)
SAP_ZAYIF = re.compile(r"\b(adt|transport(?:s|ed|ing)?|deploy(?:s|ed|ing|ment)?)\b", re.I)
KAYNAK_TEMPLATE = "template"


def sap_konulari(metin: str) -> list[str]:
    guclu = {m.group(1).lower() for rx in (SAP_GUCLU_BUYUK, SAP_GUCLU) for m in rx.finditer(metin)}
    if not guclu:
        return []
    return sorted(guclu | {m.group(1).lower() for m in SAP_ZAYIF.finditer(metin)})


def _json_oku(yol: Path) -> tuple[object, str | None]:
    """(veri, hata). JSONDecodeError ve UnicodeDecodeError ValueError alt sınıfıdır; OSError okuma hatası."""
    try:
        return json.loads(yol.read_text(encoding="utf-8-sig")), None
    except (OSError, ValueError) as exc:
        return None, f"{type(exc).__name__}: {exc}"


def _gercek(yol: str | Path) -> str:
    """Tekilleştirme anahtarı: junction/symlink çözülür (realpath), büyük/küçük harf ve `/`↔`\\` eşitlenir."""
    try:
        return os.path.normcase(os.path.realpath(str(yol)))
    except (OSError, ValueError):
        return inst._norm(yol)


def _altinda(yol: str | Path, kok_gercek: str) -> bool:
    g = _gercek(yol)
    return g == kok_gercek or g.startswith(kok_gercek.rstrip(os.sep) + os.sep)


def _baska_template_klonu(yol: Path | None) -> Path | None:
    """Skill klasörü bu template'ten BAŞKA bir aXet template klonunun altındaysa o klonun kökü, değilse None.

    İmza (kur.ps1 Template-Eksikleri ile aynı): kökte `core/00-temel.md` içinde `CORE-ID: AXET-CORE-` satırı.
    Yalnız yakın üç üst dizine bakılır (`<klon>/skills/<ad>`, `<klon>/skills-sap/<ad>`)."""
    if yol is None:
        return None
    kendi = _gercek(inst.AXET_HOME)
    for kok in list(Path(yol).parents)[:3]:
        cekirdek = kok / "core" / "00-temel.md"
        try:
            if not cekirdek.is_file():
                continue
            if re.search(r"^CORE-ID:\s*AXET-CORE-", cekirdek.read_text(encoding="utf-8", errors="replace"), re.M):
                return None if _gercek(kok) == kendi else kok
        except OSError:
            continue
    return None


def _skill_dizinleri(yol: Path) -> list[Path]:
    """`yol` bir skill klasörüyse kendisi, değilse `SKILL.md` taşıyan alt klasörleri. Okuma hatası OSError olarak yükselir."""
    if not yol.is_dir():
        return []
    if (yol / "SKILL.md").is_file():
        return [yol]
    return sorted(p for p in yol.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())


def _skill_adi(dizin: Path, metin: str) -> str:
    m = re.match(r"^---\r?\n(.*?)\r?\n---", metin, re.S)
    ad = _yaml_deger(m.group(1), "name") if m else None
    return ad or dizin.name


def manifest_yolu(localappdata: str | None = None, env: dict | None = None) -> Path | None:
    base = localappdata if localappdata is not None else (os.environ if env is None else env).get("LOCALAPPDATA")
    return Path(base) / "axet-code" / "skills_manifest.json" if base else None


def skill_envanteri(cwd: Path | None, global_cfg: object, localappdata: str | None = None, env: dict | None = None) -> dict:
    """Saf envanter: dosya okur, hiçbir şey yazmaz. `cwd` None ise (template reposu / proje dışı) yalnız global kaynaklar.

    Dönüş: {"kayitlar": [{ad, kaynak, yol, marketplace, scope, metin, baska_proje}], "manifest": {durum, yol, hata, sayi},
            "taranan": [str], "olculemedi": [str], "template_adlari": set}
    kaynak: template · global-config · proje-config · proje · AXET_SKILLS_DIR · manifest
    """
    env = os.environ if env is None else env
    kayitlar: list[dict] = []
    anahtarlar: dict[str, dict] = {}
    taranan: list[str] = []
    olculemedi: list[str] = []

    def ekle(dizin: Path, kaynak: str) -> dict:
        anahtar = _gercek(dizin)
        if anahtar in anahtarlar:
            return anahtarlar[anahtar]
        try:
            metin = (dizin / "SKILL.md").read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            metin = ""
            olculemedi.append(f"{dizin / 'SKILL.md'} ({type(exc).__name__}: {exc})")
        kayit = {"ad": _skill_adi(dizin, metin), "kaynak": kaynak, "yol": dizin, "marketplace": False,
                 "scope": None, "metin": metin, "baska_proje": False, "scope_bilinmiyor": False}
        anahtarlar[anahtar] = kayit
        kayitlar.append(kayit)
        return kayit

    def tara(yol: Path, kaynak: str) -> None:
        taranan.append(f"{kaynak} {yol}")
        try:
            dizinler = _skill_dizinleri(yol)
        except OSError as exc:
            olculemedi.append(f"{yol} ({type(exc).__name__}: {exc})")
            return
        for d in dizinler:
            ekle(d, kaynak)

    for base in (inst.SKILLS_DIR, inst.SAP_SKILLS_DIR):
        tara(base, KAYNAK_TEMPLATE)

    def config_yollari(cfg: object, kaynak: str, kok: Path | None) -> None:
        if not isinstance(cfg, dict):
            olculemedi.append(f"{kaynak}: kök değeri nesne değil ({type(cfg).__name__})")
            return
        opts = cfg.get("options")
        if opts is None:
            return
        if not isinstance(opts, dict):
            olculemedi.append(f"{kaynak}: 'options' nesne değil ({type(opts).__name__})")
            return
        yollar = opts.get("skills_paths")
        if yollar is None:
            return
        if not isinstance(yollar, list):
            olculemedi.append(f"{kaynak}: 'skills_paths' liste değil ({type(yollar).__name__})")
            return
        for p in yollar:
            if not isinstance(p, str) or inst.is_ours(p):
                continue
            yol = Path(p) if os.path.isabs(p) else (kok / p if kok else None)
            if yol is None:
                taranan.append(f"{kaynak} göreli yol çözülemedi (proje dışı): {p}")
                continue
            tara(yol, kaynak)

    config_yollari(global_cfg if global_cfg is not None else {}, "global-config", cwd)
    if cwd is None:
        taranan.append("proje kaynakları yok (proje dışı ya da template reposu; template'in kendi .axet-code/skills'i taranmadı)")
    else:
        pcfg = cwd / ".axet-code.json"
        if pcfg.is_file():
            veri, hata = _json_oku(pcfg)
            if hata is not None:
                olculemedi.append(f"proje-config {pcfg} okunamadı ({hata})")
            else:
                config_yollari(veri, "proje-config", cwd)
        tara(cwd / ".axet-code" / "skills", "proje")
    ortam = env.get("AXET_SKILLS_DIR")
    if ortam:
        tara(Path(ortam), "AXET_SKILLS_DIR")

    myol = manifest_yolu(localappdata, env)
    manifest = {"durum": "olculemedi", "yol": myol, "hata": "LOCALAPPDATA ortam değişkeni yok", "sayi": 0}
    if myol is not None:
        taranan.append(f"manifest {myol}")
        if not myol.exists():
            manifest.update(durum="yok", hata=None)
        else:
            veri, hata = _json_oku(myol)
            skills = veri.get("skills") if isinstance(veri, dict) else None
            if hata is not None or not isinstance(skills, dict):
                manifest.update(durum="bozuk", hata=hata or "'skills' nesnesi yok")
            else:
                manifest.update(durum="okundu", hata=None, sayi=len(skills))
                # Ölçüldü (M2): scope=project kurulumu `<proje>/.axet-code/skills/<ad>`'a düşer → kök bu dizindir,
                # cwd'nin herhangi bir alt dizini değil (monorepo kökünden koşunca alt projeler başka projedir).
                proje_skills = _gercek(cwd / ".axet-code" / "skills") if cwd is not None else None
                for kayit in skills.values():
                    if not isinstance(kayit, dict):
                        continue
                    yol = kayit.get("path")
                    dizin = Path(yol) if isinstance(yol, str) and yol else None
                    scope = kayit.get("scope")
                    ad = str(kayit.get("name") or kayit.get("id") or "?")
                    hedef = anahtarlar.get(_gercek(dizin)) if dizin is not None else None
                    if hedef is None:
                        # Manifest kullanıcı düzeyindedir; taranan bir dizinle eşleşmeyen kayıt yalnız scope=global ya da
                        # bu projenin `.axet-code/skills`'i altındaki scope=project ise değerlendirilir.
                        taslak = {"ad": ad, "kaynak": "manifest", "yol": dizin, "marketplace": True, "scope": scope,
                                  "metin": "", "baska_proje": False, "scope_bilinmiyor": False}
                        if scope not in ("project", "global"):
                            kayitlar.append({**taslak, "scope_bilinmiyor": True})
                            continue
                        if scope == "project" and (proje_skills is None or dizin is None
                                                   or not _altinda(dizin, proje_skills)):
                            kayitlar.append({**taslak, "baska_proje": True})
                            continue
                        if dizin is not None and (dizin / "SKILL.md").is_file():
                            hedef = ekle(dizin, "manifest")
                        else:
                            hedef = taslak
                            kayitlar.append(hedef)
                    hedef["marketplace"] = True
                    hedef["scope"] = scope
    return {"kayitlar": kayitlar, "manifest": manifest, "taranan": taranan, "olculemedi": olculemedi,
            "template_adlari": {k["ad"] for k in kayitlar if k["kaynak"] == KAYNAK_TEMPLATE}}


def check_skills(cwd: Path | None, global_cfg: object, localappdata: str | None = None, env: dict | None = None) -> dict:
    """Envanter satırları. RAPOR üretir; commit'i/oturumu bloklamaz (FAIL yalnız doctor çıkış kodunu etkiler)."""
    inv = skill_envanteri(cwd, global_cfg, localappdata, env)
    sablon = inv["template_adlari"]
    dis = [k for k in inv["kayitlar"] if k["kaynak"] != KAYNAK_TEMPLATE]
    baska = [k for k in dis if k["baska_proje"]]
    bilinmeyen = [k for k in dis if k["scope_bilinmiyor"]]
    degerlendirilen = [k for k in dis if not k["baska_proje"] and not k["scope_bilinmiyor"]]
    sayac: dict[str, int] = {}
    for k in degerlendirilen:
        sayac[k["kaynak"]] = sayac.get(k["kaynak"], 0) + 1
    add("PASS", f"skill envanteri: template {len(inv['kayitlar']) - len(dis)} · template dışı {len(degerlendirilen)}"
        + (" (" + ", ".join(f"{a} {n}" for a, n in sorted(sayac.items())) + ")" if degerlendirilen else "")
        + (f" · başka projeye ait {len(baska)} (değerlendirilmedi)" if baska else "")
        + (f" · scope bilinmiyor {len(bilinmeyen)} (değerlendirilmedi)" if bilinmeyen else ""))
    for k in dis:
        etiket = f"'{k['ad']}' ({k['kaynak']}{' · marketplace' if k['marketplace'] else ''}"
        etiket += f"{' · scope=' + str(k['scope']) if k['scope'] else ''}) {k['yol'] if k['yol'] is not None else '(manifest kaydında yol yok)'}"
        if k["baska_proje"]:
            add("INFO", f"başka projeye ait marketplace kaydı (bu dizinde yüklenmez; değerlendirilmedi): {etiket}")
            continue
        if k["scope_bilinmiyor"]:
            add("WARN", f"manifest kaydında scope bilinmiyor ({k['scope']!r}) — ÖLÇÜLEMEDİ: bu dizinde yüklenip "
                        f"yüklenmediği belirlenemedi, değerlendirilmedi: {etiket}")
            continue
        if k["ad"] in sablon:
            klon = None if k["marketplace"] else _baska_template_klonu(k["yol"])
            if klon is not None:
                # Aynı adlı skill başka bir aXet template klonundan geliyor: çözüm o klonun kayıtlarını kaldırmak;
                # template skill'lerini yeniden adlandırmak yanlış yönlendirir (Y6-A gate 2 / Y1b).
                add("FAIL", f"skill ad çakışması: {etiket} template skill'iyle aynı ad — başka bir aXet template klonu da "
                            f"kayıtlı: {klon} → o klonda `install.py --uninstall` "
                            f"(python \"{klon / 'scripts' / 'install.py'}\" --uninstall); skill adlarını değiştirme")
            else:
                cozum = (f"`skill_uninstall {k['ad']}` ile kaldır ya da farklı adla yeniden kur" if k["marketplace"]
                         else "klasörü ve `name` alanını yeniden adlandır ya da kaynağından kaldır")
                add("FAIL", f"skill ad çakışması: {etiket} template skill'iyle aynı ad — aXet ikisini birden listeler, "
                            f"model yanlışını seçebilir (ölçüldü) → {cozum}")
        if k["metin"]:
            for problem in frontmatter_problems(k["metin"]):
                add("FAIL", f"template dışı skill frontmatter (aXet sessizce düşürür): {etiket} — {problem}")
            konular = sap_konulari(k["metin"])
            if konular:
                add("WARN", f"SAP işine dokunan dış skill: {etiket} (geçen: {', '.join(konular[:6])}) → `%skill-audit` "
                            "ile incele; çelişirse template skill'leri ve kesin yasaklar geçerlidir")
        elif k["yol"] is not None and not (k["yol"] / "SKILL.md").is_file():
            add("INFO", f"manifest kaydının SKILL.md'si diskte yok: {etiket}")
        if k["marketplace"] and k["scope"] == "global":
            add("WARN", f"global kapsamlı marketplace skill'i: {etiket} — yerleşim politikası: proje kapsamı; "
                        "globale yalnız `%skill-audit` sonrası")
    for neden in inv["olculemedi"]:
        add("WARN", f"skill envanteri ÖLÇÜLEMEDİ: {neden}")
    m = inv["manifest"]
    if m["durum"] == "yok":
        add("PASS", f"marketplace manifest'i yok (marketplace kurulumu yok): {m['yol']}")
    elif m["durum"] == "okundu":
        add("PASS", f"marketplace manifest'i okundu: {m['sayi']} kayıt ({m['yol']})")
    elif m["durum"] == "bozuk":
        add("WARN", f"marketplace manifest'i ÖLÇÜLEMEDİ — okunamadı/bozuk: {m['yol']} ({m['hata']}); marketplace ve "
                    "scope bilgisi yok, klasör taraması sürdü")
    else:
        add("WARN", f"marketplace manifest'i ÖLÇÜLEMEDİ — {m['hata']}")
    add("INFO", "skill envanteri KAPSAM — taranan: " + " · ".join(inv["taranan"])
        + ("" if not inv["olculemedi"] else " — ÖLÇÜLEMEDİ: " + " · ".join(inv["olculemedi"]))
        + " — bakılmayan: global skill_install kurulum dizini (konumu ölçülmedi; yalnız manifest'teki yollar) · "
          "başka projelerin scope=project kayıtlarının içeriği · üst dizinlerdeki .axet-code · skill içeriğinin "
          "doğruluğu (SAP konusu yalnız kelime eşleşmesi; adt/transport/deploy yalnız büyük harfli SAP, ABAP, abapGit ya da S/4HANA ile birlikte) · "
          "anlam çakışması (farklı adla aynı iş) · modelin hangi kopyayı seçtiği")
    return inv


# --- bağlam boyutu (D6): oturum başında modele giden bağlam dosyalarının toplam baytı ---------------------------------
# Ölçüldü (aXet 1.3.0, 2026-09-14, D6 ölçümü — maintenance/IS-LISTESI.md:118): context_paths dosyası KESİLMEZ, tamamı
# gönderilir; 1M token aşılınca oturum uyarısız hatayla biter; iç satır geri çağırma ~738K token doğru, ~943K token yanlış;
# Türkçe markdown ≈0,51 token/bayt. Eşikler kullanıcı kararı (2026-09-14, aynı satır): WARN 200 KiB, FAIL 1 MiB.
# YALNIZ rapor: yazma/pre_tool/push kapısı DEĞİL. Token sayılmaz; eşik bayt üzerindedir.
# Kanıt: otomatik yüklenen 6 kök dosya docs/axet-davranis-olcumleri.md:10 · context_paths göreli/mutlak/dizin
# docs/axet-davranis-olcumleri.md:12 (dizin denemesi yalnız doğrudan içteki tek .md: _lab/t1/extra/ctxdir/a.md;
# global config'te yalnız mutlak yol denendi: _lab/xdg/axet-code/axet-code.json) · global + proje birleşir
# docs/axet-davranis-olcumleri.md:15.
BAGLAM_WARN = 200 * 1024
BAGLAM_FAIL = 1024 * 1024
BAGLAM_OTOMATIK = ("AGENTS.md", "CLAUDE.md", "CLAUDE.local.md", "GEMINI.md", ".cursorrules", ".github/copilot-instructions.md")
BAGLAM_ETIKETI = "bağlam boyutu"
# Bir dizin girdisinde yürünen en çok dosya; aşılırsa yürüme kesilir ve ÖLÇÜLEMEDİ yazılır (bug gate LOW-3 ölçümü:
# 20 000 dosyalı dizin ≈ 35 sn). Sınır dizin girdisi başınadır.
BAGLAM_DOSYA_SINIRI = 5000
_ONEM = {"PASS": 0, "WARN": 1, "FAIL": 2}
_GENISLETME = re.compile(r"[*?\[]|^~|\$|%")


def baglam_onemi(bayt: int) -> str:
    return "FAIL" if bayt >= BAGLAM_FAIL else "WARN" if bayt >= BAGLAM_WARN else "PASS"


def _kib(bayt: int) -> str:
    return f"{bayt / 1024:.1f}".replace(".", ",") + " KiB"


def baglam_olcumu(cwd: Path | None, cfg_file: Path) -> dict:
    """Saf ölçüm: dosya okur (stat + açılabilirlik), hiçbir şey yazmaz.

    Dönüş: {"dosyalar": [{yol, bayt, kaynak}] (yüklendiği ölçülmüş), "belirsiz": [{yol, bayt, kaynak, neden}] (boyutu
    bilinen ama yüklendiği ölçülmemiş → yalnız üst sınıra girer), "olculemedi": [str] (boyutu bilinmeyen), "taranan": [str]}
    Yol biçimleri (ölçülen): mutlak dosya · proje config'inde cwd'ye göreli dosya · dizinin doğrudan içindeki .md dosyası.
    Ölçülmeyen: dizinde alt klasör ya da .md dışı dosya → belirsiz · glob/~/ortam değişkeni ve global config'te göreli
    yol → ÖLÇÜLEMEDİ · aynı dosyanın ikinci kez listelenmesi (aXet'in tekilleştirdiği ölçülmedi) → belirsiz."""
    adaylar: list[tuple[Path, str, str | None]] = []  # (yol, kaynak, belirsizlik nedeni ya da None)
    olculemedi: list[str] = []
    taranan: list[str] = []

    def dizin(yol: Path, kaynak: str) -> None:
        def hata(exc: OSError) -> None:
            olculemedi.append(f"{kaynak} {exc.filename or yol} ({type(exc).__name__}: {exc})")
        sayac = 0
        for kok, altlar, adlar in os.walk(yol, onerror=hata):
            altlar.sort()
            for ad in sorted(adlar):
                sayac += 1
                if sayac > BAGLAM_DOSYA_SINIRI:
                    olculemedi.append(f"{kaynak} {yol} ÖLÇÜLEMEDİ (dosya sayısı sınırı aşıldı: > {BAGLAM_DOSYA_SINIRI} dosya, "
                                      "yürüme kesildi)")
                    return
                dogrudan_md = Path(kok) == yol and ad.endswith(".md")
                adaylar.append((Path(kok) / ad, kaynak, None if dogrudan_md else
                                "dizindeki alt klasör ya da .md dışı dosya — yüklendiği ölçülmedi"))

    def girdi(p: object, kaynak: str, kok: Path | None) -> None:
        if not isinstance(p, str) or not p.strip():
            olculemedi.append(f"{kaynak} girdisi yol değil: {p!r}")
            return
        if _GENISLETME.search(p):
            olculemedi.append(f"{kaynak} {p} (glob/~/ortam değişkeni genişletmesi ölçülmedi)")
            return
        if os.path.isabs(p):
            yol = Path(p)
        elif kok is None:
            olculemedi.append(f"{kaynak} göreli yol {p} (global config'te göreli yolun neye göre çözüldüğü ölçülmedi)")
            return
        else:
            yol = kok / p
        if yol.is_dir():
            dizin(yol, kaynak)
        else:
            adaylar.append((yol, kaynak, None))

    def config(veri: object, kaynak: str, kok: Path | None) -> None:
        if not isinstance(veri, dict):
            olculemedi.append(f"{kaynak}: kök değeri nesne değil ({type(veri).__name__})")
            return
        opts = veri.get("options")
        if opts is None:
            return
        if not isinstance(opts, dict):
            olculemedi.append(f"{kaynak}: 'options' nesne değil ({type(opts).__name__})")
            return
        ctx = opts.get("context_paths")
        if ctx is None:
            return
        if not isinstance(ctx, list):
            olculemedi.append(f"{kaynak}: 'context_paths' liste değil ({type(ctx).__name__})")
            return
        for p in ctx:
            girdi(p, kaynak, kok)

    taranan.append(f"global-config {cfg_file}")
    if not cfg_file.exists():
        taranan.append("global config yok (global context_paths yok)")
    else:
        veri, hata = _json_oku(cfg_file)
        if hata is not None:
            olculemedi.append(f"global-config {cfg_file} okunamadı ({hata})")
        else:
            config(veri, "global-config", None)
    if cwd is not None:
        taranan.append(f"otomatik kök dosyalar {cwd} ({', '.join(BAGLAM_OTOMATIK)})")
        for ad in BAGLAM_OTOMATIK:
            yol = cwd / ad
            try:
                yol.stat()
            except FileNotFoundError:
                continue  # yoksa aXet yüklemez (ölçülen davranış)
            except OSError as exc:
                olculemedi.append(f"otomatik {yol} ({type(exc).__name__}: {exc})")
                continue
            adaylar.append((yol, "otomatik", None))
        pcfg = cwd / ".axet-code.json"
        taranan.append(f"proje-config {pcfg}")
        if pcfg.is_file():
            veri, hata = _json_oku(pcfg)
            if hata is not None:
                olculemedi.append(f"proje-config {pcfg} okunamadı ({hata})")
            else:
                config(veri, "proje-config", cwd)

    dosyalar: list[dict] = []
    belirsiz: list[dict] = []
    gorulen: set[str] = set()
    # Yüklendiği ölçülmüş adaylar önce: aynı dosya hem kesin hem belirsiz listelenirse kesin sayılır.
    for yol, kaynak, neden in sorted(adaylar, key=lambda a: a[2] is not None):
        try:
            if not yol.is_file():
                raise FileNotFoundError(2, "dosya yok ya da dosya değil", str(yol))
            bayt = yol.stat().st_size
            if neden is None:
                # Yüklendiği ölçülen dosyada açılabilirlik de denetlenir; yalnız üst sınıra giren adayda stat yeter
                # (bug gate LOW-3: büyük dizinde her dosyayı açmak gereksiz yavaşlık).
                with yol.open("rb"):
                    pass
        except OSError as exc:
            olculemedi.append(f"{kaynak} {yol} ({type(exc).__name__}: {exc})")
            continue
        anahtar = _gercek(yol)
        kayit = {"yol": yol, "bayt": bayt, "kaynak": kaynak}
        if anahtar in gorulen:
            belirsiz.append({**kayit, "neden": "birden fazla kez listelenmiş — aXet'in tekilleştirdiği ölçülmedi"})
            continue
        gorulen.add(anahtar)
        (belirsiz.append({**kayit, "neden": neden}) if neden else dosyalar.append(kayit))
    return {"dosyalar": dosyalar, "belirsiz": belirsiz, "olculemedi": olculemedi, "taranan": taranan}


def check_baglam_boyutu(cwd: Path | None, cfg_file: Path | None = None) -> dict:
    """Bağlam dosyalarının toplam baytı: ≥ 1 MiB FAIL · ≥ 200 KiB WARN · altı PASS. Ölçülemeyen girdi PASS SAYILMAZ:
    ölçülen toplam bir eşiği zaten aşıyorsa o önem, aşmıyorsa WARN "toplam ölçülemedi". RAPOR üretir, kapı değildir."""
    olc = baglam_olcumu(cwd, cfg_file if cfg_file is not None else inst.config_path())
    toplam = sum(d["bayt"] for d in olc["dosyalar"])
    ust = toplam + sum(d["bayt"] for d in olc["belirsiz"])
    kesin = baglam_onemi(toplam)
    ust_onem = "FAIL" if olc["olculemedi"] else baglam_onemi(ust)
    eksik = _ONEM[ust_onem] > _ONEM[kesin]
    durum = ("WARN" if kesin == "PASS" else kesin) if eksik else kesin
    en_buyuk = sorted(olc["dosyalar"], key=lambda d: (-d["bayt"], str(d["yol"])))[:3]
    kaynaklar = []
    for kaynak in ("global-config", "proje-config", "otomatik"):
        secili = [d for d in olc["dosyalar"] if d["kaynak"] == kaynak]
        kaynaklar.append(f"{kaynak} {_kib(sum(d['bayt'] for d in secili))}/{len(secili)} dosya")
    msg = (f"{BAGLAM_ETIKETI}: {_kib(toplam)} toplam, {len(olc['dosyalar'])} dosya (eşik: WARN ≥ {_kib(BAGLAM_WARN)} · "
           f"FAIL ≥ {_kib(BAGLAM_FAIL)}; token değil bayt) · kaynağa göre: {' · '.join(kaynaklar)} · en büyük: "
           + (", ".join(f"{d['yol']} {_kib(d['bayt'])} ({d['kaynak']})" for d in en_buyuk) if en_buyuk else "yok"))
    if olc["belirsiz"]:
        msg += (f" · üst sınır (ölçülmemiş davranış): {len(olc['belirsiz'])} dosya {_kib(ust - toplam)}, dahil toplam {_kib(ust)}: "
                + "; ".join(f"{d['yol']} {_kib(d['bayt'])} — {d['neden']}" for d in olc["belirsiz"][:3])
                + (" …" if len(olc["belirsiz"]) > 3 else ""))
    if olc["olculemedi"]:
        msg += f" · ÖLÇÜLEMEDİ ({len(olc['olculemedi'])}): " + "; ".join(olc["olculemedi"][:3]) + (
            " …" if len(olc["olculemedi"]) > 3 else "")
    if eksik:
        msg += (" → toplam ÖLÇÜLEMEDİ: " + ("ölçülen kısım WARN eşiğinde, eksik kısım FAIL eşiğini aşırabilir" if kesin == "WARN"
                                          else "ölçülemeyen/belirsiz kısım eşiği aşırabilir") + "; girdileri düzelt ya da çıkar")
    elif durum == "FAIL":
        msg += (" → context_paths'ten çıkar ya da kısalt: ölçülen 1M token sınırında oturum uyarısız hatayla biter, "
                "iç satır geri çağırma ondan önce bozulur")
    elif durum == "WARN":
        msg += " → büyüyen bağlam dosyalarını kısalt ya da context_paths'ten çıkar (token bütçesi ve satır geri çağırma)"
    add(durum, msg)
    add("INFO", f"{BAGLAM_ETIKETI} KAPSAM — taranan: " + " · ".join(olc["taranan"])
        + " — bakılmayan: token sayısı (ölçülmez; eşik bayt üzerinden, token bayttan çıkarım) · TUI oturumunun bağlamı · "
          "aXet'in sabit sistem prompt'u, araç tanımları, skill listesi ve konuşma geçmişi · üst dizinlerdeki .axet-code.json · "
          "dizinde alt klasör/.md dışı dosyaların ve yinelenen girdilerin gerçekten yüklenip yüklenmediği (üst sınır "
          "(ölçülmemiş davranış) olarak ayrı yazılır, toplama girmez) · glob/~/ortam değişkenli ve global config'te göreli "
          "girdiler (ÖLÇÜLEMEDİ; toplam PASS sayılmaz) · symlink'li alt klasörler izlenmez (os.walk followlinks=False; "
          "alt klasördeki junction'ın izlenip izlenmediği ölçülmedi) · dizin girdisi başına en çok "
          f"{BAGLAM_DOSYA_SINIRI} dosya yürünür (aşan kısım ÖLÇÜLEMEDİ) · üst sınır adaylarının açılabilirliği (yalnız stat)"
        + ("" if not olc["belirsiz"] else f" — bu koşuda üst sınır (ölçülmemiş davranış): {len(olc['belirsiz'])} dosya")
        + ("" if not olc["olculemedi"] else " — bu koşuda ÖLÇÜLEMEDİ: " + " · ".join(olc["olculemedi"])))
    return olc


def check_template() -> None:
    lines = len(inst.CORE_FILE.read_text(encoding="utf-8").splitlines())
    add("PASS" if lines <= 150 else "WARN", f"çekirdek {lines} satır (hedef ≤ 150)")
    for base in (inst.SKILLS_DIR, inst.SAP_SKILLS_DIR):
        if not base.exists():
            continue
        for d in sorted(p for p in base.iterdir() if p.is_dir()):
            skill = d / "SKILL.md"
            if not skill.exists():
                add("FAIL", f"skill klasöründe SKILL.md yok: {d}")
                continue
            text = skill.read_text(encoding="utf-8")
            m = re.search(r"^name:\s*(\S+)", text, re.M)
            if not m or m.group(1) != d.name:
                add("FAIL", f"skill adı klasör adıyla aynı değil: {skill} (name={m.group(1) if m else 'YOK'})")
            for problem in frontmatter_problems(text):
                add("FAIL", f"skill frontmatter (aXet sessizce düşürür): {skill} — {problem}")
    add("PASS", "skill klasör/ad eşleşmesi ve frontmatter biçimi tarandı")
    ok, bilgi = sap_stamp.kanonik_denetle()
    add("PASS" if ok else "FAIL", f"SAP kanonik kesin yasak bölümü okundu, A-D kategorileri tam (damga sürümü {bilgi})"
        if ok else f"SAP kanonik kesin yasak bölümü BOZUK — damga üretilemez ya da eksik basılır: {bilgi}")
    for durum, msg in template_bulgulari(bm.template_sinifla()):
        add(durum, msg)


def _kisalt(yollar: list[str], sinir: int = 8) -> str:
    return "; ".join(yollar[:sinir]) + (" …" if len(yollar) > sinir else "")


def template_bulgulari(olc: dict) -> list[tuple[str, str]]:
    """`bm.template_sinifla()` çıktısını doctor satırlarına çevirir. Saf fonksiyon (test edilebilirlik: git'e bakmaz).

    Yönlendirme kararı (Z5 + P4, 2026-09-18):
      · **WARN (değişmedi)** — çalışma ağacındaki commit'siz değişiklikler ve `%guncelle` dışı bir yazarın
        upstream'e gitmemiş commit'leri. Açıklanmamış sapma budur.
      · **INFO** — `%guncelle`'nin kendi git kimliğiyle attığı commit'ler. Klon `origin`'e push EDİLMEZ
        (motor `origin/main`'den geçici kopyaya çekilir) → bu satırlar yapısal olarak hiçbir zaman
        temizlenemez. Her oturumda temizlenemeyen bir WARN, TÜM WARN'ları değersizleştirir.
        Bilgi kaybı yok: dosya yolları satırda aynen listelenir.
      · Hiçbir sınıf FAIL üretmez → doctor'ın çıkış kodu değişmez (yeni kapı açılmadı; ADR 0019).
    """
    out: list[tuple[str, str]] = []
    if olc["durum"] == "olculemedi":
        out.append(("INFO", "template davranış yüzeyi: " + "; ".join(olc["notlar"])))
    elif olc["durum"] == "sapma":
        k = olc["kullanici"]
        out.append(("WARN", f"template davranış yüzeyinde onaysız (commit'siz/upstream'e gitmemiş) değişiklik ({len(k)}): "
                            + _kisalt(k) + " → bakımcı değilsen: git -C <template> status / git diff"))
    else:
        out.append(("PASS", "template davranış yüzeyinde kullanıcı kaynaklı sapma yok"
                    + (f" ({'; '.join(olc['notlar'])})" if olc["notlar"] else "")))
    if olc["durum"] == "sapma" and olc["notlar"]:
        out.append(("INFO", "template davranış yüzeyi notları: " + "; ".join(olc["notlar"])))
    if olc["guncelle_anlik"]:
        out.append(("INFO", f"`%guncelle` anlık commit'indeki template dosyaları ({len(olc['guncelle_anlik'])} dosya) — "
                            "İÇERİK KULLANICININ, commit'i `%guncelle` attı (engellemez): " + _kisalt(olc["guncelle_anlik"])
                            + " → incelemek için: git -C <template> log -p --author=" + bm.GUNCELLE_EPOSTA))
    if olc["guncelle_uygulama"]:
        out.append(("INFO", f"`%guncelle`'nin uyguladığı template güncellemesi ({len(olc['guncelle_uygulama'])} dosya) — "
                            "beklenen, engellemez: " + _kisalt(olc["guncelle_uygulama"])))
    out.append(("INFO", "template yüzeyi KAPSAM — bakılanlar: "
                + " · ".join(bm.TEMPLATE_DOSYALAR + [d + "/**" for d in bm.TEMPLATE_DIZINLER])
                + " (git status + `@{u}...HEAD` farkı) — bakılmayanlar: değişikliğin İÇERİĞİ (yalnız hangi dosya) · "
                  "memory/ scripts/ templates/ tests/ · klonun `origin` adresinin doğruluğu · "
                  f"'{bm.GUNCELLE_EPOSTA}' kimliği TAKLİT EDİLEBİLİR (gürültü ayıklaması, güvenlik sınırı DEĞİL) · "
                  "merge commit'iyle gelen dosya atfedilemez, temkinli olarak kullanıcı sayılır · "
                  "upstream tanımsızsa commit dalı hiç ÖLÇÜLMEZ"))
    return out


# Şablon yer tutucusu: `<kısa açıklama>`, `<komut>`, `<…>`. HTML yorumu (`<!--`), kapanış etiketi ve autolink sayılmaz.
_YER_TUTUCU = re.compile(r"<(?![!/]|https?:)[^<>\n`]{1,60}>")


def yer_tutucular(metin: str) -> list[str]:
    """Doldurulmamış şablon yer tutucuları. HTML yorumları ve `kod` içindekiler (ör. `<source_root>/…`) bilinçli örnektir, sayılmaz."""
    temiz = re.sub(r"<!--.*?-->", "", metin, flags=re.S)
    temiz = re.sub(r"`[^`\n]*`", "", temiz)
    return _YER_TUTUCU.findall(temiz)


def sap_proje_dogrula(cwd: Path) -> tuple[str, str]:
    """('gecerli' | 'gecersiz' | 'olculemedi', mesaj). SAP CLI'nin kullandığı doğrulamanın kendisi
    (skills-sap/sap-adt-foundation/scripts/sapadt/project.py `load_sap_project`) — kopya kural yok."""
    import importlib.util
    yol = inst.AXET_HOME / "skills-sap" / "sap-adt-foundation" / "scripts" / "sapadt" / "project.py"
    try:
        spec = importlib.util.spec_from_file_location("_axet_sap_project", yol)
        if spec is None or spec.loader is None:
            raise ImportError(f"yüklenemedi: {yol}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        cfg, hata = mod.load_sap_project(cwd)
    except Exception as exc:  # noqa: BLE001 — doğrulayıcının çökmesi FAIL değil, ÖLÇÜLEMEDİ
        return "olculemedi", f"sap-project.json doğrulaması ÖLÇÜLEMEDİ ({type(exc).__name__}: {exc})"
    if hata:
        return "gecersiz", hata
    return "gecerli", f"profil {cfg['sap_profile']} · master_language {cfg['master_language']}"


# --- AGENTS.md `- SAP` satırı ↔ sap-project.json — TEK kopya: yeni_proje.py bunları `doctor.` üzerinden kullanır ---------
# (yeni_proje.py zaten `import doctor` yapar; ters yön döngüsel import olurdu.)
# skills-sap/sap-adt-foundation/scripts/sapadt/project.py GECERLI_PROFILLER ile aynı küme (test_yeni_proje eşitliği denetler).
PROFILLER = ("ecc", "s4_private", "s4_public", "btp_abap")
_DIL = re.compile(r"^[A-Za-z]{2}$")
# Satır ayrıştırma (` ve ** önceden soyulur): anahtar harf duyarsız, `_` ile boşluk eşit.
_SAP_SATIRI = re.compile(r"^-\s*SAP\b", re.I)
# Bug gate MEDIUM-2: anahtar yalnız kelime sınırıyla başlayıp biterse eşleşir ("profilini" anahtar değil) ve değeri ancak
# (a) anahtar biçimindeyse (`:` / `=` ayracı — değer bozuksa yine alınır → ÖLÇÜLEMEDİ korunur) ya da (b) kendi başına
# geçerliyse sayılır: profil PROFILLER'da; dil BÜYÜK iki harf. (b)'de dil için büyük harf şartı: "master language ve …"
# gibi iki harfli Türkçe sözcük dil sanılmasın. Aksi hâlde eşleşme serbest metin sayılıp atlanır (satırdaki sonraki
# eşleşmeye bakılır). group(1) ayraç, group(2) değer.
_PROFIL_ANAHTARI = re.compile(r"(?<!\w)(?:sistem[ _]+profili|sap[ _]+profile?|profile?|profili)\b\s*([:=])?\s*([^\s·,;()|]+)",
                              re.I)
_DIL_ANAHTARI = re.compile(r"(?<!\w)master[ _]+language\b\s*([:=])?\s*([^\s·,;()|]+)", re.I)
_SERBEST_DIL = re.compile(r"^[A-Z]{2}$")
# Re-gate MEDIUM-1: serbest biçimde geçersiz ama DEĞER GİBİ görünen değer ATLANMAZ, sayılır: farklıysa satırlar arası
# çakışma → ÖLÇÜLEMEDİ; tek başına geçersizse "okunamadı" → ÖLÇÜLEMEDİ. Atlamak, kanonik satırın yanındaki
# "master language en" / "sistem profili ecc." gibi ikinci beyanı görünmez kılıp sahte PASS veriyordu (kesin yasak D ekseni).
# Değer benzeri: profil — s4/ecc/btp ile başlayan belirteç (Türkçe sözcük böyle başlamaz); dil — iki harf (büyüklük
# serbest) VE maddenin/cümlenin sonunda (ardından satır sonu ya da · , ; | ( )). Dil için stopword listesi yerine bu
# AYRAÇ kuralı seçildi: "de", "da" gibi Türkçe sözcükler aynı zamanda ISO dil kodudur (DE, DA) — liste ya gerçek kodu
# yutar ya eksik kalır; "master language ve login dili …" gibi cümle içindeki sözcük ise değer sayılmaz. Değerin
# sonundaki . ! ? atılır ("EN." → "EN").
_PROFIL_BENZERI = re.compile(r"^(?:s4|ecc|btp)", re.I)
_DIL_BENZERI = re.compile(r"^[A-Za-z]{2}$")
_DEGER_SONU = re.compile(r"\s*(?:$|[·,;|()])")
# Yalnız doctor WARN'ı: `sürüm` (yeni_proje.py satıra `sürüm <release>` yazar) ve satırda yazılmışsa cleancore_policy.
_SURUM_ANAHTARI = re.compile(r"\b(?:sürüm|release)\s*:?\s*([^\s·,;()|]+)", re.I)
_POLITIKA_ANAHTARI = re.compile(r"\bcleancore[ _]+policy\s*:?\s*([^\s·,;()|]+)", re.I)
SAP_SATIRI_ETIKETI = "AGENTS.md SAP satırı ↔ sap-project.json"


def damga_satirlari(metin: str):
    """(satır, kesin yasak damga bloğunun içinde mi)."""
    i, j = metin.find(sap_stamp.BASLA), metin.find(sap_stamp.BITIR)
    konum = 0
    for satir in metin.splitlines(keepends=True):
        bas, konum = konum, konum + len(satir)
        yield satir, (0 <= i < j and i <= bas <= j)


def sap_degerleri(veri) -> dict:
    """AGENTS.md SAP satırının kaynağı/karşılaştırma değeri: sap-project.json (kök nesne)."""
    if not isinstance(veri, dict):
        raise ValueError("kök bir JSON nesnesi değil")
    return {"sap_profile": str(veri.get("sap_profile", "")).strip(), "release": str(veri.get("release", "")).strip(),
            "master_language": str(veri.get("master_language", "")).strip().upper()}


def _anahtar_degeri(rx: re.Pattern, metin: str, serbest_gecerli, deger_benzeri) -> str | None:
    """Satırdaki ilk SAYILAN eşleşmenin değeri (sondaki . ! ? atılmış): anahtar biçimli (ayraçlı), serbest biçimde geçerli
    ya da serbest biçimde değer benzeri (bkz. regex notları). `deger_benzeri(değer, madde_sonu_mu)`."""
    for m in rx.finditer(metin):
        deger = m.group(2).rstrip(".!?") or m.group(2)
        if (m.group(1) or serbest_gecerli(deger)
                or deger_benzeri(deger, _DEGER_SONU.match(metin, m.end(2)) is not None)):
            return deger
    return None


def sap_satiri_ayristir(metin: str) -> dict | None:
    """Damga bloğu dışındaki `- SAP` satırlarının değerleri {profil, dil, surum, politika, cakisma}. Satır yoksa None.

    Bug gate Y-a: sistem profili ya da master_language anahtarı TAŞIMAYAN `- SAP…` maddeleri (ör. "- SAP'ye yazmadan
    önce onay al") atlanır; hiçbir satır anahtar taşımıyorsa ilk satırın (boş) değerleri döner → ÖLÇÜLEMEDİ. Anahtar
    taşıyan satırlarda her anahtarın İLK yazılan değeri alınır; aynı anahtar (profil/dil) satırlar arasında farklıysa
    `cakisma` dolar → ÖLÇÜLEMEDİ: hangi satırın geçerli olduğu bilinemez; biri json'la tutsa bile PASS sahte olur,
    çelişki demek de yanlış satırı suçlayabilir."""
    satirlar = []
    for satir, ici in damga_satirlari(metin):
        temiz = satir.replace("`", "").replace("**", "").strip()
        if ici or not _SAP_SATIRI.match(temiz):
            continue
        out = {"profil": _anahtar_degeri(_PROFIL_ANAHTARI, temiz, lambda v: v.lower() in PROFILLER,
                                         lambda v, son: bool(_PROFIL_BENZERI.match(v))),
               "dil": _anahtar_degeri(_DIL_ANAHTARI, temiz, lambda v: bool(_SERBEST_DIL.match(v)),
                                      lambda v, son: son and bool(_DIL_BENZERI.match(v)))}
        for ad, rx in (("surum", _SURUM_ANAHTARI), ("politika", _POLITIKA_ANAHTARI)):
            m = rx.search(temiz)
            out[ad] = m.group(1) if m else None
        satirlar.append(out)
    if not satirlar:
        return None
    anahtarli = [s for s in satirlar if s["profil"] is not None or s["dil"] is not None]
    if not anahtarli:
        return {**satirlar[0], "cakisma": []}
    birlesik: dict = {"cakisma": []}
    for ad, etiket, norm in (("profil", "sistem profili", str.lower), ("dil", "master_language", str.upper),
                             ("surum", None, None), ("politika", None, None)):
        degerler = [s[ad] for s in anahtarli if s[ad] is not None]
        birlesik[ad] = degerler[0] if degerler else None
        if norm is not None and len({norm(v) for v in degerler}) > 1:
            birlesik["cakisma"].append(f"{etiket} {' | '.join(degerler)}")
    return birlesik


def sap_satiri_denetle(metin: str, sap: dict) -> tuple[str, list[str]]:
    """AGENTS.md `- SAP` satırı ↔ sap-project.json: ('tutarli' | 'celiski' | 'olculemedi', ayrıntılar).

    Esnek ayrıştırma: ` ve ** soyulur, anahtar harf duyarsız (`_` = boşluk), değerler harf duyarsız karşılaştırılır.
    Satır yoksa, profil PROFILLER dışındaysa ya da dil iki harf değilse ÖLÇÜLEMEDİ (yeniden inceleme YENİ-1: ayrıştırılamayan
    satır önceden sahte PASS veriyordu — kesin yasak D ekseni). Yalnız sap_profile ve master_language karşılaştırılır."""
    s = sap_satiri_ayristir(metin)
    if s is None:
        return "olculemedi", ["AGENTS.md'de `- SAP` satırı yok"]
    if s["cakisma"]:
        return "olculemedi", [f"anahtar taşıyan birden fazla `- SAP` satırı farklı değer veriyor ({'; '.join(s['cakisma'])})"]
    profil, dil = s["profil"], s["dil"]
    olcum = []
    if profil is None or profil.lower() not in PROFILLER:
        olcum.append(f"sistem profili okunamadı ({profil!r})")
    if dil is None or not _DIL.match(dil):
        olcum.append(f"master_language okunamadı ({dil!r}; iki harf bekleniyor)")
    if olcum:
        return "olculemedi", olcum
    celiski = []
    if profil.lower() != sap["sap_profile"].lower():
        celiski.append(f"sistem profili {profil} ≠ sap-project.json {sap['sap_profile']}")
    if dil.upper() != sap["master_language"].upper():
        celiski.append(f"master_language {dil} ≠ sap-project.json {sap['master_language']}")
    return ("celiski" if celiski else "tutarli"), celiski


def check_sap_satiri(cwd: Path, agents_var: bool, agents_metni: str, json_durum: str, json_mesaj: str) -> None:
    """AGENTS.md `- SAP` satırı ↔ sap-project.json. YALNIZ doctor raporu (kullanıcı onayı 2026-09-14, ADR 0019
    değerlendirildi): SAP yazma yolu, pre_tool ya da push kapısı DEĞİL. Kararlar yeni_proje.py ile aynı:
    sap_profile/master_language çelişkisi ya da ölçülemedi → FAIL · release/cleancore_policy farkı → WARN."""
    if json_durum != "gecerli":
        # sap-project.json tarafı yoksa karşılaştırma anlamsız; önem P4 satırını izler (geçersiz FAIL, doğrulayıcı yok WARN).
        add("FAIL" if json_durum == "gecersiz" else "WARN",
            f"{SAP_SATIRI_ETIKETI} ÖLÇÜLEMEDİ: sap-project.json doğrulanmadı ({json_mesaj})")
        return
    if not agents_var:
        add("FAIL", f"{SAP_SATIRI_ETIKETI} ÖLÇÜLEMEDİ: AGENTS.md yok")
        return
    veri, hata = _json_oku(cwd / "sap-project.json")
    if hata is not None or not isinstance(veri, dict):
        add("FAIL", f"{SAP_SATIRI_ETIKETI} ÖLÇÜLEMEDİ: sap-project.json okunamadı ({hata or 'kök nesne değil'})")
        return
    sap = sap_degerleri(veri)
    durum, ayrinti = sap_satiri_denetle(agents_metni, sap)
    if durum == "olculemedi":
        add("FAIL", f"{SAP_SATIRI_ETIKETI} ÖLÇÜLEMEDİ: {'; '.join(ayrinti)} → satırı `- SAP (varsa): sistem profili "
                    "<profil> · sürüm <sürüm> · master_language: <XX>` biçiminde yaz")
        return
    if durum == "celiski":
        add("FAIL", f"{SAP_SATIRI_ETIKETI}: ÇELİŞKİ — {'; '.join(ayrinti)} → hangisi doğruysa diğerini düzelt (kesin yasak D "
                    "login dilini master_language'den alır; profil SAP araç yüzeyini belirler)")
    else:
        add("PASS", f"{SAP_SATIRI_ETIKETI}: tutarlı (sistem profili {sap['sap_profile']} · master_language "
                    f"{sap['master_language']})")
    s = sap_satiri_ayristir(agents_metni) or {}
    for etiket, anahtar, json_anahtari in (("sürüm", "surum", "release"), ("cleancore_policy", "politika", "cleancore_policy")):
        satirda, dosyada = s.get(anahtar), str(veri.get(json_anahtari, "")).strip()
        if satirda is not None and satirda.lower() != dosyada.lower():
            add("WARN", f"{SAP_SATIRI_ETIKETI}: {etiket} {satirda} ≠ sap-project.json {json_anahtari} {dosyada or '(boş)'} "
                        "— bilinçli değilse birini düzelt")


def check_project(cwd: Path, sap_global: bool = False) -> None:
    if cwd == inst.AXET_HOME or inst.AXET_HOME in cwd.parents:
        add("INFO", "bulunulan dizin template reposu; proje kontrolleri atlandı")
        return
    agents = cwd / "AGENTS.md"
    add("PASS" if agents.exists() else "WARN", f"proje AGENTS.md {'var' if agents.exists() else 'yok → new_project.py'}")
    if agents.exists():
        brief = "session_brief.py" in agents.read_text(encoding="utf-8", errors="replace")
        add("PASS" if brief else "WARN", "AGENTS.md oturum açılış komutu (session_brief.py) var" if brief
            else "AGENTS.md'de oturum açılış komutu yok → templates/project/AGENTS.md 'Oturum' bölümünü ekle")
        eksik = yer_tutucular(agents.read_text(encoding="utf-8", errors="replace"))
        if eksik:
            add("WARN", f"AGENTS.md'de doldurulmamış yer tutucu ({len(eksik)}): " + ", ".join(eksik[:5])
                + (" …" if len(eksik) > 5 else "") + " → proje bilgisiyle doldur")
        else:
            add("PASS", "AGENTS.md yer tutucuları doldurulmuş")
    check_sablon_surumu(cwd)
    is_listesi = cwd / ".axet-code" / "memory" / "project_is-listesi.md"
    add("PASS" if is_listesi.exists() else "WARN", "proje iş listesi var" if is_listesi.exists()
        else "proje iş listesi (.axet-code/memory/project_is-listesi.md) yok → new_project.py (var olanı ezmez)")
    try:
        git_repo = subprocess.run(["git", "-C", str(cwd), "rev-parse", "--is-inside-work-tree"],
                                  capture_output=True, text=True, stdin=subprocess.DEVNULL).returncode == 0
        if git_repo:
            gizli = subprocess.run(["git", "-C", str(cwd), "check-ignore", "-q", "--no-index", ".conn_adt"],
                                   capture_output=True, stdin=subprocess.DEVNULL).returncode == 0
            add("PASS" if gizli else "FAIL", ".conn_adt git'e kapalı (.gitignore)" if gizli
                else ".conn_adt .gitignore'da DEĞİL — kimlik bilgisi commit edilebilir → templates/project/.gitignore satırlarını ekle")
            check_precommit(cwd)
        else:
            # Ölçüldü 2026-09-14: bu dal yokken git'siz projede pre-commit satırı hiç basılmıyor, doctor "0 FAIL" diyordu.
            add("WARN", "proje git reposu değil — .conn_adt gitignore ve pre-commit denetimi YOK → "
                        "git init -b main, sonra new_project.py'yi yeniden çalıştır (var olanı ezmez; core.hooksPath'i ayarlar)")
    except OSError:
        add("INFO", "git bulunamadı: .conn_adt gitignore ve pre-commit kablolama kontrolü yapılmadı")
    agents_metni = agents.read_text(encoding="utf-8", errors="replace") if agents.exists() else ""
    damga_var = sap_stamp._BASLA_ONEK in agents_metni or sap_stamp._BITIR_ONEK in agents_metni
    if (cwd / "sap-project.json").exists():
        if not agents.exists():
            add("FAIL", "SAP projesi ama AGENTS.md yok → new_project.py --sap")
        else:
            check_stamp(agents_metni, sap_proje=True)
        # Ölçüldü 2026-09-14: yer tutuculu profil doctor'da görünmüyordu, SAP CLI ise yalnız --list/ping açıyordu.
        durum_sp, mesaj_sp = sap_proje_dogrula(cwd)
        if durum_sp == "gecerli":
            add("PASS", f"sap-project.json geçerli ({mesaj_sp})")
        elif durum_sp == "gecersiz":
            add("FAIL", f"{mesaj_sp} → sap-project.json alanlarını doldur; doldurulmazsa SAP araçları yalnız --list ve ping çalıştırır")
        else:
            add("WARN", mesaj_sp)
        check_sap_satiri(cwd, agents.exists(), agents_metni, durum_sp, mesaj_sp)
        root, err = npk.source_root(cwd)
        if err:
            add("FAIL", err)
        elif root.is_dir() and npk.paketler(root):
            eksik = npk.eksik_kurallar(root)
            add("FAIL" if eksik else "PASS", f".rules.md eksik paketler: {eksik} → templates/package/.rules.md.tmpl" if eksik
                else f"{len(npk.paketler(root))} paketin hepsinde .rules.md var")
            add("PASS" if npk.index_guncel(root) else "WARN",
                f"{npk.INDEX_FILE} güncel" if npk.index_guncel(root) else f"{npk.INDEX_FILE} bayat ya da yok → new_package.py --index")
        if not sap_global:
            add("WARN", "global SAP paketi kapalı: kesin yasaklar yalnız proje damgasından yüklenir; SAP skill'leri ve diğer SAP kuralları için install.py --sap")
    elif damga_var:
        check_stamp(agents_metni, sap_proje=False)
    durum, satirlar = bm.proje_denetle(cwd)
    komut = f"python \"{Path(bm.__file__).resolve().as_posix()}\" generate"
    if durum == "es":
        add("PASS", f"davranış yüzeyi onaylı manifest'le eş ({satirlar[0]})")
    elif durum == "yok":
        add("WARN", f"davranış yüzeyi manifest'i yok ({bm.MANIFEST.as_posix()}) — yüzeyi gözden geçirip KENDİ terminalinde: {komut}")
    elif durum == "bozuk":
        add("FAIL", f"davranış yüzeyi manifest'i okunamadı: {satirlar[0]} → dosyayı sil ve yüzeyi gözden geçirip yeniden onayla")
    else:
        add("FAIL", f"davranış yüzeyinde ONAYSIZ değişiklik ({len(satirlar)}): " + "; ".join(satirlar[:8])
            + (" …" if len(satirlar) > 8 else "") + f" → incele; bilinçliyse KENDİ terminalinde: {komut} --only <yol>")
    gi = cwd / ".axet-code" / ".gitignore"
    if gi.exists() and gi.read_text(encoding="utf-8", errors="replace").strip() == "*":
        add("WARN", ".axet-code/.gitignore aXet varsayılanı (`*`): proje skill/hafızası repoya girmez → new_project.py")
    cfg = cwd / ".axet-code.json"
    if cfg.exists():
        data, hata = _json_oku(cfg)
        if hata is not None:
            add("FAIL", f".axet-code.json geçerli JSON değil ya da okunamadı (UTF-8?) ({hata})")
        elif not isinstance(data, dict):
            add("FAIL", f".axet-code.json kök değeri nesne değil ({type(data).__name__}) → proje hafızası ve izin "
                        "kuralı ezme denetimi ÖLÇÜLEMEDİ")
        else:
            opts = data.get("options") or {}
            if not isinstance(opts, dict):
                # Global config'le aynı önem: yollar okunamaz (aXet'in bu değeri nasıl ele aldığı ölçülmedi).
                add("FAIL", f".axet-code.json 'options' nesne değil ({type(opts).__name__}) → context_paths/skills_paths "
                            "ÖLÇÜLEMEDİ; nesneye çevir")
                opts = {}
            ctx = opts.get("context_paths") or []
            ctx = ctx if isinstance(ctx, list) else []
            add("PASS" if ".axet-code/memory/MEMORY.md" in ctx else "WARN", "proje config'i proje hafızasını yüklüyor")
            # Ölçüldü (aXet 1.3.0): aynı desen projede farklı kararla yazılırsa global kuralı ezer.
            perms = data.get("permissions")
            rules = perms.get("rules") if isinstance(perms, dict) else None
            if (perms is not None and not isinstance(perms, dict)) or (rules is not None and not isinstance(rules, dict)):
                bozuk = "permissions" if not isinstance(perms, dict) else "permissions.rules"
                add("WARN", f".axet-code.json '{bozuk}' nesne değil → izin kuralı ezme denetimi ÖLÇÜLEMEDİ")
            else:
                prules = _kurallar(data)
                ezen = [f"{d}:{p} ({prules[d][p]} ≠ {v})" for d, pats in inst.load_rules().items() for p, v in pats.items()
                        if isinstance(prules.get(d), dict) and p in prules[d] and prules[d][p] != v]
                add("FAIL" if ezen else "PASS", f"proje config'i şablon izin kuralını EZİYOR: {ezen}" if ezen
                    else "proje config'i şablon izin kurallarını ezmiyor")
    else:
        add("WARN", "proje .axet-code.json yok (proje hafızası yüklenmez)")
    add("INFO", f".axetcode-denylist {'var' if (cwd / '.axetcode-denylist').exists() else 'yok'}")


def check_sablon_surumu(cwd: Path) -> None:
    """Proje şablonu klondakiyle aynı sürümde mi (TASARIM §9 tetiği → `%guncelle-proje`).

    Ölçüm `new_project.sablon_surumu_durumu`'ndadır; `session_brief.py` de AYNI fonksiyonu
    çağırır (iki ayrı ölçüm yazılırsa biri bayatlar). Damga ayrıca `check_stamp` ile ölçülür.
    """
    durum, mesaj = nprj.sablon_surumu_durumu(cwd)
    add({"guncel": "PASS", "eski": "WARN", "kayitsiz": "WARN",
         "cozulemedi": "WARN", "olculemedi": "INFO"}[durum], mesaj)


def check_stamp(agents_metni: str, sap_proje: bool) -> None:
    """Proje AGENTS.md kesin yasak damgası ↔ core/sap/00-sap.md kanonik bölümü (sap_stamp.denetle)."""
    st, ayrinti = sap_stamp.denetle(agents_metni)
    if st == "guncel":
        add("PASS" if sap_proje else "INFO", "kesin yasak damgası güncel (AGENTS.md)"
            + ("" if sap_proje else " — SAP projesi değil (sap-project.json yok) ama damga var"))
    elif st == "farkli":
        add("FAIL", f"kesin yasak damgası kanonik metinden FARKLI — {ayrinti} → new_project.py --sap ile yeniden damgala")
    elif st == "bozuk":
        add("FAIL", f"kesin yasak damgası BOZUK — {ayrinti} → AGENTS.md'de tek BASLA/BITIR bloğu bırak, sonra new_project.py --sap")
    elif st == "kanonik_yok":
        add("FAIL", f"kesin yasak damgası denetlenemedi — kanonik metin okunamadı: {ayrinti}")
    else:
        add("FAIL", "SAP projesi ama AGENTS.md'de kesin yasak damgası YOK → new_project.py --sap")


def check_precommit(cwd: Path) -> None:
    """Git reposunda pre-commit kablolaması: `.githooks/pre-commit` var mı, core.hooksPath onu gösteriyor mu, runner yolu diskte mi."""
    hook = cwd / ".githooks" / "pre-commit"
    r = subprocess.run(["git", "-C", str(cwd), "config", "--get", "core.hooksPath"], capture_output=True, text=True,
                       stdin=subprocess.DEVNULL)
    hp = r.stdout.strip()
    hedef = (Path(hp) if os.path.isabs(hp) else cwd / hp).resolve() if hp else None
    if not hook.exists():
        add("WARN", "pre-commit şablonu (.githooks/pre-commit) yok — commit anında denetim yok → new_project.py (var olanı ezmez)")
    elif hedef != (cwd / ".githooks").resolve():
        add("WARN", f"core.hooksPath {'ayarlı değil' if not hp else repr(hp)} — pre-commit denetimi KOŞMAZ → "
                    "git config core.hooksPath .githooks")
    else:
        m = re.search(r'^RUNNER="([^"]+)"', hook.read_text(encoding="utf-8", errors="replace"), re.M)
        if m and not Path(m.group(1)).is_file():
            add("WARN", f"pre-commit runner yolu diskte yok ({m.group(1)}) — her commit ENGELLENİR (template klonu taşındı mı?) "
                        "→ .githooks/pre-commit içindeki RUNNER yolunu düzelt")
        else:
            add("PASS", "pre-commit kablolu (core.hooksPath=.githooks)")


def check_live(sap: bool, cwd: Path) -> None:
    exe = shutil.which("axet-code")
    if not exe:
        add("FAIL", "--live: axet-code PATH'te yok")
        return
    prompt = ("BU BIR KURULUM DOGRULAMASIDIR. HICBIR ARAC KULLANMA. Sistem baglaminda gecen 'CORE-ID:', "
              "'SAP-CORE-ID:', 'SAP-STAMP-ID:', 'MEMORY-ID:', 'PROJECT-ID:' ve 'PROJECT-MEMORY-ID:' satirlarini AYNEN yaz; "
              "olmayan icin '<anahtar>: YOK' yaz. Baska bir sey yazma.")
    try:
        out = subprocess.run([exe, "run", "--quiet", prompt], capture_output=True, text=True, timeout=300,
                             stdin=subprocess.DEVNULL, cwd=cwd, encoding="utf-8", errors="replace").stdout
    except subprocess.TimeoutExpired:
        add("FAIL", "--live: axet-code run 300 sn içinde bitmedi")
        return
    expected = {"CORE-ID": read_id(inst.CORE_FILE, "CORE-ID"), "MEMORY-ID": read_id(inst.TEAM_MEMORY, "MEMORY-ID")}
    if sap:
        expected["SAP-CORE-ID"] = read_id(inst.SAP_CORE_DIR / "00-sap.md", "SAP-CORE-ID")
    project_id = read_id(cwd / "AGENTS.md", "PROJECT-ID")
    if project_id:
        expected["PROJECT-ID"] = project_id
    project_memory_id = read_id(cwd / ".axet-code" / "memory" / "MEMORY.md", "PROJECT-MEMORY-ID")
    if project_memory_id:
        expected["PROJECT-MEMORY-ID"] = project_memory_id
    stamp_id = read_id(cwd / "AGENTS.md", "SAP-STAMP-ID")
    if stamp_id:
        expected["SAP-STAMP-ID"] = stamp_id
    for key, val in expected.items():
        add("PASS" if val and val in out else "FAIL", f"--live: bağlamda {key} {val}")
    add("INFO", "--live model çıktısı: " + " | ".join(line.strip() for line in out.strip().splitlines()[:6]))


def main() -> int:
    ap = argparse.ArgumentParser(description="aXet.code template kurulum doğrulaması")
    ap.add_argument("--live", action="store_true", help="aXet'e bağlamını sor (model çağrısı yapar)")
    ap.add_argument("--skills", action="store_true", help="yalnız skill envanteri (%%skill-audit için)")
    ap.add_argument("--ad", action="append", default=[], metavar="AD",
                    help="kurulum öncesi: bu skill adı template skill adıyla çakışıyor mu (tekrarlanabilir; --skills kipini açar)")
    args = ap.parse_args()
    cwd = Path.cwd().resolve()
    proje = None if (cwd == inst.AXET_HOME or inst.AXET_HOME in cwd.parents) else cwd
    yalniz_skill = args.skills or bool(args.ad)

    if yalniz_skill:
        cfg_file = inst.config_path()
        cfg: object = {}
        if not cfg_file.exists():
            add("INFO", f"global config yok: {cfg_file} (global skills_paths taranmadı)")
        else:
            cfg, hata = _json_oku(cfg_file)
            if hata is not None:
                cfg = {}
                add("WARN", f"global config okunamadı ({hata}) → global skills_paths ÖLÇÜLEMEDİ")
        inv = check_skills(proje, cfg)  # nesne olmayan cfg/options/skills_paths → envanterde ÖLÇÜLEMEDİ
        for ad in args.ad:
            add("FAIL" if ad in inv["template_adlari"] else "PASS",
                f"kurulum öncesi ad denetimi: '{ad}' template skill adıyla AYNI → kurma; farklı adlı sürüm ara ya da "
                "kullanıcıya bildir" if ad in inv["template_adlari"] else f"kurulum öncesi ad denetimi: '{ad}' template skill adlarıyla çakışmıyor")
        add("INFO", "template skill adları: " + ", ".join(sorted(inv["template_adlari"])))
    else:
        cfg, sap = check_global()
        check_template()
        check_project(cwd, sap)
        check_skills(proje, cfg)
        check_baglam_boyutu(cwd)
        for name, info, ok in inst.check_env():
            add("PASS" if ok else "WARN", f"{name}: {info}")
        if args.live:
            check_live(sap, cwd)

    for status, msg in results:
        print(f"[{status}] {msg}")
    if yalniz_skill:
        print("\nKAPSAM — yalnız skill envanteri koştu (global config, template, proje ve ortam kontrolleri koşmadı)")
    else:
        print("\nKAPSAM — bakılmayanlar: skill içeriklerinin doğruluğu · izin kurallarının fiilen blokladığı · "
              "denylist davranışı · model seçimi · pre-commit'in fiilen koştuğu (yalnız kablolaması) · "
              "davranış yüzeyi değişikliğinin içeriği (yalnız onaylı olup olmadığı) · "
              "AGENTS.md SAP satırında yalnız anahtar taşıyan `- SAP` satırlarının profil/master_language'i (FAIL) ile "
              "yazılmışsa sürüm/cleancore_policy'si (WARN; ilk yazan satırdan) karşılaştırılır — anahtar biçimi (`:`/`=`) "
              "ya da geçerli değer taşımayan `- SAP…` maddeleri (serbest metin) atlanır; aktif paket, transport ve `- SAP` ile başlamayan satırlardaki SAP ifadeleri bakılmaz · "
              "bağlam boyutu yalnız dosya baytıdır (token sayısı ölçülmez, bayttan çıkarılır; TUI bağlamı ve aXet'in sabit "
              "sistem prompt'u ölçülmez) · "
              "emekli izin deseni yalnız global config'te aranır (proje .axet-code.json'da aranmaz) · "
              "izin deseni uzunluk-önceliği yalnız global config'te aranır (proje .axet-code.json ve "
              "AXET_* ortam ayarları ÖLÇÜLMEDİ) ve yalnız TEMPLATE deny desenlerine karşı ölçülür (kullanıcının "
              "kendi deny kuralları karşılaştırmaya girmez); çakışma desen METİNLERİNDEN hesaplanır (joker yalnız "
              "`*`; aXet'in gerçek eşleştiricisi çalıştırılmaz, komut fiilen denenmez) ve uzunluk ölçütünün sabit "
              "karakter mi toplam uzunluk mu olduğu DOĞRULANMADI → ikisi birden riskli sayılır"
              + ("" if args.live else " · bağlamın fiilen yüklendiği (--live ile ölçülür)"))
    fails = sum(1 for s, _ in results if s == "FAIL")
    print(f"SONUÇ: {fails} FAIL · {sum(1 for s, _ in results if s == 'WARN')} WARN")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
