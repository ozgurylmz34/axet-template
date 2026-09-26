# -*- coding: utf-8 -*-
"""Proje kökü + `sap-project.json` + `.conn_adt` okuma — TEK kaynak.

Proje kökü: `AXET_SAP_PROJECT_DIR` (CLI `--project-dir`/cwd'den kendisi basar) → cwd.
`sap-project.json` proje kökündedir:
    {"sap_profile": "ecc|s4_private|s4_public|btp_abap", "release": "...",
     "master_language": "TR|EN|...", "cleancore_policy": "..."}

FAIL-CLOSED: dosya yok / JSON değil / nesne değil / `sap_profile` enum dışı /
`master_language` iki harf değil → `load_sap_project` hata döner; çağıran (CLI/gate)
yalnız `--list` ve `ping`e izin verir.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

PROJECT_ENV = "AXET_SAP_PROJECT_DIR"
SAP_PROJECT_FILE = "sap-project.json"
CONN_FILE = ".conn_adt"

GECERLI_PROFILLER = ("ecc", "s4_private", "s4_public", "btp_abap")
_DIL = re.compile(r"^[A-Za-z]{2}$")


def project_dir(explicit: str | os.PathLike | None = None) -> Path:
    """Proje kökü: açık parametre → env AXET_SAP_PROJECT_DIR → cwd."""
    if explicit:
        return Path(explicit).resolve()
    env = os.environ.get(PROJECT_ENV)
    return Path(env).resolve() if env else Path.cwd().resolve()


def conn_path(proj: str | os.PathLike | None = None) -> Path:
    return project_dir(proj) / CONN_FILE


def load_sap_project(proj: str | os.PathLike | None = None) -> tuple[dict | None, str | None]:
    """(config, hata). Hata varsa config None'dır (fail-closed)."""
    p = project_dir(proj) / SAP_PROJECT_FILE
    if not p.is_file():
        return None, f"{SAP_PROJECT_FILE} yok ({p})"
    try:
        # utf-8-sig: PowerShell'in eklediği BOM ilk anahtarı bozmasın.
        data = json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception as exc:  # noqa: BLE001
        return None, f"{SAP_PROJECT_FILE} geçersiz JSON ({type(exc).__name__}: {exc})"
    if not isinstance(data, dict):
        return None, f"{SAP_PROJECT_FILE} geçersiz: kök bir JSON nesnesi değil"
    profil = data.get("sap_profile")
    if not isinstance(profil, str) or profil not in GECERLI_PROFILLER:
        return None, (f"{SAP_PROJECT_FILE} geçersiz: sap_profile={profil!r} "
                      f"(geçerli: {', '.join(GECERLI_PROFILLER)})")
    dil = data.get("master_language")
    if not isinstance(dil, str) or not _DIL.match(dil.strip()):
        return None, (f"{SAP_PROJECT_FILE} geçersiz: master_language={dil!r} "
                      "(iki harfli dil anahtarı bekleniyor, ör. TR/EN)")
    for anahtar in ("release", "cleancore_policy"):
        if anahtar in data and not isinstance(data[anahtar], str):
            return None, f"{SAP_PROJECT_FILE} geçersiz: {anahtar} metin olmalı"
    out = dict(data)
    out["master_language"] = dil.strip().upper()
    return out, None


def conn_line_value(line: str, key: str) -> str | None:
    """`.conn_adt` satırından değer — TAM anahtar eşleşmesi (önek gaspı yok)."""
    s = line.strip()
    if not s or s.startswith("#") or "=" not in s:
        return None
    k, v = s.split("=", 1)
    if k.strip() != key:
        return None
    return v.strip()


def conn_file_values(key: str, proj: str | os.PathLike | None = None) -> list[str]:
    """`.conn_adt` içinde `key`in TÜM (boş olmayan) değerleri, dosya sırasıyla."""
    p = conn_path(proj)
    if not p.is_file():
        return []
    out = []
    for ln in p.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        v = conn_line_value(ln, key)
        if v:
            out.append(v)
    return out


def conn_file_last(key: str, proj: str | os.PathLike | None = None) -> str | None:
    """SON-KAZANIR (istemcinin dotenv okumasıyla aynı politika)."""
    vals = conn_file_values(key, proj)
    return vals[-1] if vals else None


def effective_conn_value(key: str, default: str | None = None,
                         proj: str | os.PathLike | None = None) -> str | None:
    """İstemcinin FİİLEN kullanacağı değer.

    ÖLÇÜLDÜ (lib/sap_adt_lib.py modül gövdesi): `.conn_adt` `load_dotenv(override=False)` ile
    yüklenir ⇒ ortamda ANAHTAR ZATEN VARSA (boş dize dahil) dosyadaki değer onu EZMEZ.
    Bu fonksiyon o kuralı taklit eder: env'de anahtar varsa env, yoksa dosyanın son değeri.
    """
    if key in os.environ:
        return os.environ[key]
    v = conn_file_last(key, proj)
    return v if v is not None else default


# ═════════════════════ Yerel kaynak dosyası yolu (Z128 → Z142, TEK kaynak) ═════════════════════
# `adt_pretty_print(output_path)` (Z128) kuralları buraya taşındı ve genelleştirildi; `adt_get(output_path)` ve
# `adt_push_source(source_path)` (+ kapının kaynak taraması, gate.py) AYNI kuralı kullanır:
#   · yol proje kökünün İÇİNDE (göreli yol köke göre çözülür; `resolve` bağlantıyı izler ⇒ kök dışına çıkan
#     junction/symlink de reddedilir),
#   · uzantı çağıranın izin listesinde (yapılandırma dosyaları — `.conn_adt`, `sap-project.json`, `.rules.md` —
#     bu yollarla yazılamaz/okunamaz),
#   · `.axet-code/` altında DEĞİL (kapı kayıtlarının dizini; büyük/küçük harf duyarsız),
#   · proje kökündeki `.axetcode-denylist`'te yazan bir yol ya da onun ALTINDA değil (aXet'in dosya araçları o
#     yolları okumaz/yazmaz; `adt_get`/`adt_push_source` betik içinden bu korumayı delmesin — `conn/`, `secrets`).
# Üzerine yazma kararı (`overwrite`) çağıranındır.
#: Kaynak dosyası uzantıları — emsal: `scripts/project_precommit.py` "abap_benzeri" listesi (SAP kaynak
#: incelemesine giren uzantılar) + `object_types` `file_extension` son ekleri (.asddlxs, .asdcls).
KAYNAK_UZANTILARI = (".abap", ".asddls", ".asddlxs", ".asdcls", ".asbdef", ".bdef", ".cds", ".ddl",
                     ".srvd", ".srvdsrv", ".xml")
#: Okunan kaynak dosyası üst sınırı (bayt). SAP kaynak objeleri bunun çok altındadır; sınırsız okuma kapıyı
#: yavaşlatır ve yanlış dosyanın (döküm, arşiv) kaynak diye gönderilmesini kolaylaştırır.
KAYNAK_OKUMA_SINIRI = 5 * 1024 * 1024


DENYLIST_FILE = ".axetcode-denylist"


def _gecersiz(mesaj: str) -> dict:
    return {"ok": False, "error": "invalid_argument", "message": mesaj}


def denylist_yollari(proj: str | os.PathLike | None = None) -> tuple[list[tuple[str, Path]], str | None]:
    """Proje kökündeki `.axetcode-denylist` → ([(satır, mutlak yol)], hata). Dosya yoksa ([], None).

    Biçim (aXet belgesi — `docs/axet-davranis-olcumleri.md`; şablon `templates/project/.axetcode-denylist`): satır
    başına bir yol, `#` ile başlayan satır yorum, `~` ev dizinine genişler, göreli yol proje köküne göre. Glob
    DESTEKLENMEZ (aXet'te ölçülmedi — şablon "tam ad yaz" diyor): satır düz yol olarak alınır; sondaki `/` atılır.
    Dosya VAR ama okunamıyorsa hata döner — çağıran fail-closed davranır ("okunamadı" ≠ "liste boş")."""
    kok = project_dir(proj)
    p = kok / DENYLIST_FILE
    if not p.is_file():
        return [], None
    try:
        satirlar = p.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        return [], f"{DENYLIST_FILE} okunamadı ({type(exc).__name__})"
    yollar = []
    for satir in satirlar:
        s = satir.strip()
        if not s or s.startswith("#"):
            continue
        s = s.rstrip("/\\") or s
        ham = Path(os.path.expanduser(s))
        yollar.append((s, (ham if ham.is_absolute() else kok / ham).resolve()))
    return yollar, None


def _altinda_mi(yol: Path, ust: Path) -> bool:
    """`yol` == `ust` ya da onun altında mı? Windows'ta büyük/küçük harf duyarsız (`normcase`)."""
    a, b = os.path.normcase(str(yol)), os.path.normcase(str(ust))
    return a == b or a.startswith(b.rstrip("\\/") + os.sep)


def yerel_kaynak_yolu(deger, arg_adi: str = "output_path",
                      uzantilar: tuple[str, ...] = KAYNAK_UZANTILARI) -> tuple[Path | None, dict | None]:
    """`deger` → (mutlak yol, None) | (None, invalid_argument sözlüğü). Hedefin varlığına bakılmaz; diskten yalnız
    `.axetcode-denylist` okunur (yoksa bugünkü davranış)."""
    if not (isinstance(deger, str) and deger.strip()):
        return None, _gecersiz(f"{arg_adi} boş olamaz (ya da hiç verme).")
    kok = project_dir()
    ham = Path(deger.strip())
    yol = (ham if ham.is_absolute() else kok / ham).resolve()
    try:
        goreli = yol.relative_to(kok)
    except ValueError:
        return None, _gecersiz(f"{arg_adi} proje kökünün İÇİNDE olmalı (göreli yol proje köküne göre çözülür).")
    if yol.suffix.lower() not in uzantilar:
        return None, _gecersiz(f"{arg_adi} uzantısı {', '.join(uzantilar)} olmalı "
                               "(yapılandırma dosyaları bu araçla yazılamaz/okunamaz).")
    if goreli.parts and goreli.parts[0].lower() == ".axet-code":
        return None, _gecersiz(f"{arg_adi} .axet-code/ altında olamaz (kapı kayıtlarının dizini).")
    yasakli, hata = denylist_yollari(kok)
    if hata:
        return None, _gecersiz(f"{arg_adi} doğrulanamadı: {hata} — yol denylist'e karşı ölçülemedi, işlem yapılmadı.")
    for satir, d in yasakli:
        if _altinda_mi(yol, d):
            return None, _gecersiz(f"{arg_adi} {DENYLIST_FILE}'teki '{satir}' yolunun altında — bu yol "
                                   "okunamaz/yazılamaz (kimlik/gizli dosya koruması).")
    return yol, None


def yerel_dosyaya_yaz(yol: Path, metin: str) -> str | None:
    """UTF-8 bayt olarak ATOMİK yaz (geçici dosya + `os.replace`; satır sonu çevrilmez). Hata metni ya da None."""
    try:
        yol.parent.mkdir(parents=True, exist_ok=True)
        gecici = yol.with_name(yol.name + ".tmp")
        gecici.write_bytes(metin.encode("utf-8"))
        os.replace(gecici, yol)
    except OSError as exc:
        return f"{type(exc).__name__}: {exc}"
    return None


def yerel_kaynak_oku(deger, arg_adi: str = "source_path") -> tuple[str | None, Path | None, dict | None]:
    """`deger` yolundaki kaynak dosyasını oku → (metin, yol, None) | (None, None, hata sözlüğü).

    Yol kuralı `yerel_kaynak_yolu` ile AYNI. FAIL-CLOSED: dosya yok / dizin / sınırdan büyük / UTF-8 değil / boş
    → hata (çağıran yazmaz). UTF-8 BOM atılır (editörün eklediği BOM SAP kaynağına girmesin)."""
    yol, hata = yerel_kaynak_yolu(deger, arg_adi)
    if hata:
        return None, None, hata
    if not yol.is_file():
        return None, None, {"ok": False, "error": "source_file_missing",
                            "message": f"{arg_adi} dosyası yok ya da dosya değil: {yol.relative_to(project_dir()).as_posix()}"}
    try:
        boy = yol.stat().st_size
        if boy > KAYNAK_OKUMA_SINIRI:
            return None, None, _gecersiz(f"{arg_adi} {boy} bayt — sınır {KAYNAK_OKUMA_SINIRI} bayt (kaynak dosyası mı?).")
        metin = yol.read_bytes().decode("utf-8-sig")
    except UnicodeDecodeError:
        return None, None, _gecersiz(f"{arg_adi} UTF-8 değil — kaynak dosyasını UTF-8 kaydet.")
    except OSError as exc:
        return None, None, {"ok": False, "error": "source_file_unreadable",
                            "message": f"{arg_adi} okunamadı ({type(exc).__name__}: {exc})."}
    if not metin.strip():
        return None, None, _gecersiz(f"{arg_adi} boş — boş kaynak göndermek objeyi siler; yazılmadı.")
    return metin, yol, None
