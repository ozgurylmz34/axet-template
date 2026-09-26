# -*- coding: utf-8 -*-
"""Çıktı temizleyici — şifre / token / cookie değerleri stdout JSON'una ve loga SIZMASIN.

Savunma-derinliği katmanıdır: bilinen sızıntı noktaları kaynağında da maskelendi
(bkz. IMPLEMENTATION.md "Kimlik bilgisi yolları"). Burada son çıkıştan önce iki şey yapılır:
  1. BİLİNEN SIR DEĞERLERİ (etkin ADT_SAP_PASSWORD, `user:pass`, Basic başlığının base64'ü)
     metinde geçerse `***` ile değiştirilir.
  2. DESENLER: Authorization başlığı, X-CSRF-Token değeri, SAP oturum çerezleri
     (sap-contextid, SAP_SESSIONID_*, MYSAPSSO2), `access_token`/`client_secret` JSON alanları.
"""
from __future__ import annotations

import base64
import re

MASK = "***"

_DESENLER = [
    (re.compile(r"(?i)(authorization['\"]?\s*[:=]\s*['\"]?)(basic|bearer)\s+[A-Za-z0-9+/=._~-]+"),
     r"\1\2 " + MASK),
    (re.compile(r"(?i)(x-csrf-token['\"]?\s*[:=]\s*['\"]?)(?!fetch\b)[A-Za-z0-9+/=_-]{6,}"),
     r"\1" + MASK),
    (re.compile(r"(?i)\b(CSRF:\s*)[A-Za-z0-9+/=_-]{4,}(\.\.\.)?"), r"\1" + MASK),
    (re.compile(r"(?i)\b(sap-contextid|SAP_SESSIONID_[A-Z0-9_]+|MYSAPSSO2|sap-usercontext)"
                r"(\s*[=:]\s*)[^;\s'\"]+"), r"\1\2" + MASK),
    (re.compile(r"(?i)(['\"](?:access_token|refresh_token|client_secret|password)['\"]\s*:\s*['\"])"
                r"[^'\"]+"), r"\1" + MASK),
    # urllib3/requests bağlantı hatası: HTTPSConnectionPool(host='…', port=…) — canlı ölçümde host sızdı.
    (re.compile(r"(?i)\b(host\s*=\s*['\"])[^'\"]+"), r"\1" + MASK),
]


def host_sirlari(url: str | None) -> list[str]:
    """Bağlantı URL'sindeki host adı (ve host:port) çıktıya/loga SIZMASIN.

    Neden: aXet'te araç çıktıları kurumsal denetime gider; canlı ölçümde bağlantı ve sertifika hata
    mesajları SAP host adını olduğu gibi taşıdı. Yazıldığı harf biçimi ve küçük harfli hâli birlikte eklenir.
    """
    if not isinstance(url, str) or not url.strip():
        return []
    try:
        from urllib.parse import urlparse
        u = urlparse(url.strip())
        netloc = u.netloc.rsplit("@", 1)[-1]
    except ValueError:
        return []
    out = set()
    for host in {netloc.split(":", 1)[0], u.hostname or ""}:
        if host:
            out.add(host)
            out.add(host.lower())
    # Z118ⓐ (2026-09-26): `u.port` ÖZELLİĞİ ayrıştırmayı erteler — şablonda kalmış `<PORT>` burada ValueError atar
    # (`urlparse` değil). Önceden try dışındaydı → CLI `calistir` / `gate.log_write_attempt` / populate / screen
    # traceback veriyordu (log satırı yok). Port okunamazsa host yine maskelenir; ham `host:port` biçimi de eklenir
    # (hata metinleri URL'yi yazıldığı gibi taşır). Aynı sınır: `gate.check_target_system` / `check_connection`.
    try:
        port = u.port
    except ValueError:
        port = None
    if port:
        out |= {f"{h}:{port}" for h in list(out)}
    if netloc:
        out |= {netloc, netloc.lower()}
    return sorted({s for s in out if len(s) >= 4}, key=len, reverse=True)


def bilinen_sirlar(user: str | None, password: str | None) -> list[str]:
    out = []
    if password:
        out.append(password)
        if user:
            cift = f"{user}:{password}"
            out.append(cift)
            try:
                out.append(base64.b64encode(cift.encode("utf-8")).decode("ascii"))
            except Exception:  # noqa: BLE001
                pass
    # Kısa değerleri maskelemek metni anlamsızlaştırır (ör. "1"); 4 altı atlanır.
    return sorted({s for s in out if s and len(s) >= 4}, key=len, reverse=True)


def temizle_metin(metin: str, sirlar: list[str] | None = None) -> str:
    if not isinstance(metin, str) or not metin:
        return metin
    for s in sirlar or []:
        if s in metin:
            metin = metin.replace(s, MASK)
    for rx, yerine in _DESENLER:
        metin = rx.sub(yerine, metin)
    return metin


def temizle(obj, sirlar: list[str] | None = None):
    """dict/list/str içinde özyinelemeli temizlik (yeni nesne döner)."""
    if isinstance(obj, str):
        return temizle_metin(obj, sirlar)
    if isinstance(obj, dict):
        return {k: temizle(v, sirlar) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [temizle(v, sirlar) for v in obj]
    return obj
