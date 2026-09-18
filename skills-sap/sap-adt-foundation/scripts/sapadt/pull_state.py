# -*- coding: utf-8 -*-
"""PULL-BEFORE-EDIT durumu — `<proje>/.axet-code/sap-pull-state.json`.

İYİMSER EŞZAMANLILIK: `adt_get` canlı kaynağı başarıyla okuduğunda kaynağın özeti kaydedilir;
`adt_push_source` yazmadan hemen önce canlı kaynağı YENİDEN okur ve özeti kayıtla kıyaslar.
Karşılaştırma **çekildiği andaki canlı ↔ yazma anındaki canlı**dır; "yerel dosya ↔ canlı" DEĞİL
(her meşru düzenlemede yerel dosya zaten farklıdır — kaynak çekirdekte o kontrol bu yüzden kaldırıldı).

Kayıt şeması: {"<tip>:<AD>": {"sha256": <64 hex>, "pulled_at": <ISO-8601 UTC>, "object_type": <verilen tip>}}
Host/kullanıcı/client YAZILMAZ. Tasarım ve sınırlar: IMPLEMENTATION.md §13.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

from sapadt import project as _project

PULL_STATE_REL = Path(".axet-code") / "sap-pull-state.json"
_TIP_ESANLAM = {"behaviordefinition": "bdef", "servicebinding": "srvb", "messageclass": "msag"}
_SHA = re.compile(r"^[0-9a-f]{64}$")


def dosya(proj=None) -> Path:
    return _project.project_dir(proj) / PULL_STATE_REL


def tip_anahtari(object_type) -> str:
    """Tip eşanlamlıları tek anahtara iner (clas→class, ddls→cds, ccimp→implementations …)."""
    t = str(object_type or "").strip().lower()
    if t in _TIP_ESANLAM:
        return _TIP_ESANLAM[t]
    try:
        import object_types as _ot  # type: ignore
        if _ot.is_class_include(t):
            return _ot.normalize_class_include(t)
        return _ot.normalize_object_type(t)
    except Exception:  # noqa: BLE001 — tanınmayan tip kendi adıyla anahtarlanır
        return t


def anahtar(name, object_type) -> str:
    return f"{tip_anahtari(object_type)}:{str(name or '').strip().upper()}"


def ozet(source: str) -> str:
    """sha256(normalize_source(source)). Normalize: CRLF→LF + satır sonu boşlukları + baş/son boş satır
    (readback kıyasıyla AYNI fonksiyon). Gerekçe: IMPLEMENTATION.md §13.2."""
    from source_normalize import normalize_source  # type: ignore
    return hashlib.sha256(normalize_source(source).encode("utf-8")).hexdigest()


def _oku(proj) -> tuple[dict, str | None]:
    p = dosya(proj)
    if not p.is_file():
        return {}, None
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception as exc:  # noqa: BLE001
        return {}, f"{PULL_STATE_REL.as_posix()} okunamadı ({type(exc).__name__})"
    if not isinstance(data, dict):
        return {}, f"{PULL_STATE_REL.as_posix()} geçersiz: kök bir JSON nesnesi değil"
    return data, None


def kayit_al(name, object_type, proj=None) -> tuple[dict | None, str | None]:
    """(kayıt|None, hata|None). Dosya yok / anahtar yok → (None, None)."""
    data, hata = _oku(proj)
    if hata:
        return None, hata
    rec = data.get(anahtar(name, object_type))
    if rec is None:
        return None, None
    if not isinstance(rec, dict) or not _SHA.match(str(rec.get("sha256") or "")):
        return None, f"{PULL_STATE_REL.as_posix()} içinde {anahtar(name, object_type)} kaydı geçersiz"
    return rec, None


def _yaz(proj, data: dict) -> str | None:
    p = dosya(proj)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        fd, gecici = tempfile.mkstemp(prefix=".sap-pull-state.", suffix=".tmp", dir=str(p.parent))
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
        os.replace(gecici, p)
        return None
    except OSError as exc:
        return f"{PULL_STATE_REL.as_posix()} yazılamadı ({type(exc).__name__})"


def kaydet(name, object_type, source: str, proj=None) -> str | None:
    """Canlı kaynağın özetini yaz. Bozuk dosya yeni kayıtla ONARILIR (diğer kayıtlar düşer →
    onların push'u `pull_before_edit_missing` alır: güvenli yön)."""
    data, _hata = _oku(proj)
    data[anahtar(name, object_type)] = {
        "sha256": ozet(source),
        "pulled_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "object_type": str(object_type or ""),
    }
    return _yaz(proj, data)


def kaydet_yok(name, object_type, proj=None) -> str | None:
    """Obje (bugün yalnız SINIF ALT-INCLUDE'u) 404 ile KANITLI yokken çekme kaydı.

    `sha256` = boş kaynağın özeti, `absent: true`. Push anında canlı hâlâ yoksa ilk yaratım geçer;
    canlıda artık varsa ve içerik boş değilse özet tutmaz → `source_changed_since_pull` (IMPLEMENTATION.md §14.4)."""
    data, _hata = _oku(proj)
    data[anahtar(name, object_type)] = {
        "sha256": ozet(""),
        "pulled_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "object_type": str(object_type or ""),
        "absent": True,
    }
    return _yaz(proj, data)


def sil(name, object_type, proj=None) -> str | None:
    data, hata = _oku(proj)
    if hata:
        return hata
    if data.pop(anahtar(name, object_type), None) is None:
        return None
    return _yaz(proj, data)
