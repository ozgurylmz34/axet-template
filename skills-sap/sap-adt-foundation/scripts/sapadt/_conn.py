# -*- coding: utf-8 -*-
"""Aktif bağlantı tier'ını okuma — tier-bazlı salt-okunur guard (kaynak çekirdek `_conn.py`).

`.conn_adt` içindeki `ADT_SAP_TIER` satırı sistemin tier'ını belirler:
  DEV → mutasyon serbest · QA/PRD → salt-okunur · çözülemedi → UNKNOWN (mutasyon YOK)

KORUNAN kararlar (kaynak çekirdekten aynen):
  • FAIL-CLOSED: tier çözülemezse DEV VARSAYILMAZ → `TIER_UNKNOWN`.
  • TAM ANAHTAR: `ADT_SAP_TIER_OLD=DEV` gibi önek satırları sayılmaz.
  • SON-KAZANIR + ÇAKIŞMA: aynı anahtar farklı değerlerle birden çok kez geçerse UNKNOWN
    (istemci dotenv ile SON değeri kullanır; guard ile bağlantı ayrışmasın).
  • BOM: `utf-8-sig`.

⛔ BİLİNÇLİ DEĞİŞİKLİK (aXet): kaynak çekirdek `.conn_adt`'de satır yoksa `os.environ
['ADT_SAP_TIER']`e düşüyordu. aXet modeli komutları `bash` ile çalıştırır ve bir ortam
değişkenini tek satırla basabilir (`ADT_SAP_TIER=DEV python sap_adt_cli.py ...`) ⇒ env
fallback'i yazma kapısını dosyasız açan bir yan kapıdır. Burada KALDIRILDI: tier YALNIZ
proje kökündeki `.conn_adt`'den okunur.
"""
from __future__ import annotations

import logging

from sapadt import project as _project

log = logging.getLogger("sap-adt")

_TIER_ALIASES = {
    "DEVELOPMENT": "DEV", "DEV": "DEV", "SANDBOX": "DEV", "SBX": "DEV",
    "QUALITY": "QA", "QA": "QA", "QAS": "QA", "TEST": "QA",
    "INTEGRATION": "QA", "STAGING": "QA", "TRAINING": "QA",
    "PRODUCTION": "PRD", "PRD": "PRD", "PROD": "PRD", "P": "PRD",
}

TIER_UNKNOWN = "UNKNOWN"


def _normalize_tier(raw: str | None) -> str | None:
    if not raw:
        return None
    return _TIER_ALIASES.get(raw.strip().upper(), raw.strip().upper())


def _conn_line_value(line: str, key: str) -> str | None:
    return _project.conn_line_value(line, key)


def get_active_tier(proj=None) -> str:
    """Aktif sistemin tier'ı (DEV/QA/PRD). Çözülemezse `TIER_UNKNOWN` (fail-closed)."""
    try:
        p = _project.conn_path(proj)
        if p.is_file():
            degerler = [t for t in (_normalize_tier(v)
                                    for v in _project.conn_file_values("ADT_SAP_TIER", proj)) if t]
            if degerler:
                if len(set(degerler)) > 1:
                    log.warning(
                        "ADT_SAP_TIER .conn_adt'de ÇAKIŞIK tanımlı (%s) → tier=UNKNOWN "
                        "(fail-closed). Fazla satırı SİL.", " ≠ ".join(dict.fromkeys(degerler)))
                    return TIER_UNKNOWN
                return degerler[-1]
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("tier: .conn_adt okunamadı (%s) → UNKNOWN", exc)
        return TIER_UNKNOWN
    # DEBUG seviyesi: bu fonksiyon okuma çağrılarında da (gate.tier alanı için) koşar; yazma
    # reddinde kapı zaten `tier_not_writable` + açıklama döndürür (sessiz değil).
    log.debug("ADT_SAP_TIER çözülemedi → tier=UNKNOWN; MUTASYON REDDEDİLİR (fail-closed).")
    return TIER_UNKNOWN


def _conn_value(key: str, default: str, proj=None) -> str:
    """`.conn_adt`'den bir değer — istemcinin FİİLEN kullanacağı değer (env önce, bkz.
    `project.effective_conn_value`), yoksa default."""
    v = _project.effective_conn_value(key, None, proj)
    return v if v else default


def get_atc_variant(proj=None) -> str:
    """Sistemin ATC check variant'ı — .conn_adt ADT_ATC_VARIANT; tanımlı değilse 'DEFAULT'."""
    return _conn_value("ADT_ATC_VARIANT", "DEFAULT", proj)


def write_mcp_binding_state(url: str | None = None, client: str | None = None) -> None:
    """aXet'te NO-OP. Kaynak çekirdekte statusline için `.claude/.mcp_active_system`
    yazıyordu; aXet'te ne statusline ne `.claude/` vardır — proje dizinine yan-etki yazılmaz."""
    return None
