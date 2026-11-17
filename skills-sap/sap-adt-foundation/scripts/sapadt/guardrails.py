"""ADR 0005 hardcoded guardrails — bypass-free.

Each guard raises GuardrailViolation with an ADR_0005_<cat> error code.
Tools call validate_* functions before issuing any HTTP request.

Reference: governance/decisions/0005-sap-standart-obje-koruma-ve-sistem-state-yasaklari.md
ADR:       governance/decisions/0007-sap-adt-mcp-server.md §Server-Side Guardrails

Implementation status:
- v1 (Task #4): Z/Y prefix check (2026-11-17: + bildirilmiş /<NS>/ — ad_politikasi), transport non-empty, basic TR text presence
- v2 (Task #7): Full TR character validation, 4-label completeness, std object delete reject
"""
from __future__ import annotations

import re
from typing import Iterable


class GuardrailViolation(Exception):
    """Raised when an ADR 0005 rule is violated. Tool returns this to caller."""

    def __init__(self, code: str, message: str, **context):
        self.code = code
        self.context = context
        super().__init__(f"[{code}] {message}")

    def as_dict(self) -> dict:
        return {
            "ok": False,
            "error": "guardrail_violation",
            "code": self.code,
            "message": str(self),
            "context": self.context,
        }


# Müşteri ad alanı kararı TEK KAYNAKTADIR: `lib/utils/ad_politikasi.py` (ADR 0005 A-EK).
# Z/Y · kilit nesnesi (ENQU) için E+Z/Y · projede `sap-project.json` `customer_namespaces` ile bildirilmiş
# `/<NS>/`. Desenler (`\Z`) ve fail-closed yapılandırma kuralları orada; burada yeniden YAZILMAZ.
# (`sapadt` import'u `lib/`i sys.path'e ekler — bkz. sapadt/__init__.py.)
from utils import ad_politikasi as _ad  # noqa: E402

_LOCK_TYPES = _ad.KILIT_TIPLERI


def _is_customer_namespace(name: str, object_type: str | None = None, *, root=None) -> bool:
    """Müşteri ad alanı mı? (Z/Y · ENQU için E+Z/Y · bildirilmiş `/<NS>/`) — `ad_politikasi`."""
    return _ad.musteri_adi_mi(name, object_type, root=root)


def require_customer_namespace(name: str, *, what: str = "object", object_type: str | None = None,
                               root=None) -> None:
    """ADR 0005 §A: standart obje yaratma/değiştirme yasak.

    Müşteri ad alanı zorunlu: Z/Y önek (lock objeleri için E+Z/Y) ya da projede `customer_namespaces` ile
    bildirilmiş namespace (`/<NS>/…`; ADR 0005 A-EK). `root`: namespace listesinin okunacağı proje kökü
    (bağlantı dosyasının dizininden farklıysa namespace kabulü kapalıdır — fail-closed).
    """
    if not name:
        raise GuardrailViolation(
            "ADR_0005_A",
            f"{what} adı boş olamaz",
        )
    if not _is_customer_namespace(name, object_type, root=root):
        raise GuardrailViolation(
            "ADR_0005_A",
            f"Standart obje yaratma yasak — {what} '{name}' Z/Y (lock için E+Z/Y) ya da projede "
            f"bildirilmiş müşteri namespace'i (/<NS>/) ile başlamalı (customer namespace)"
            f"{_ad.red_gerekcesi(name, root=root)}",
            name=name,
        )


YEREL_PAKET = "$TMP"
# `package=` yalnız bu yaratma araçlarından geçirilir (K-M, kullanıcı kararı 2026-09-18). İçlerinde
# transport isteyen başka adım YOK (ölçüldü: yalnız `corrNr` sorgu parametresi, transport boşsa
# gönderilmez). `adt_struct_create` BİLEREK dışarıda: `create_structure` yaratmadan sonra
# `lock_object(transport=)` çağırır ve o kilit transportsuz reddeder ⇒ yarım obje kalırdı.
# Düzenleme araçları (push/description/msgclass) paketi bilmez — transport ister.
# 2026-09-21: `adt_ttyp_create` eklendi (POST + aktivasyon + gerekirse If-Match PUT; kilit YOK, corrNr yalnız
# transport verilirse gider — `adt_post_shell(ttyp)` ile aynı POST). `adt_table_create` BİLEREK dışarıda:
# DDL yazımı stateful kilit ister, transportsuz kilit canlı ÖLÇÜLMEDİ (yapı aracıyla aynı gerekçe).
TMP_MUAF_ARACLAR = frozenset({"adt_post_shell", "adt_domain_create", "adt_dtel_create", "adt_ttyp_create"})


def require_transport(transport: str | None, *, what: str = "operation",
                      package: str | None = None) -> None:
    """ADR 0005 §C: transport zorunlu, asla varsayma.

    Tek istisna: `package` TAM OLARAK `$TMP` (yerel obje — SAP transport numarasını yok sayar,
    ölçüldü: E071 kaydı 0). `$tmp`, `$TMP2`, `" $TMP"` istisna DEĞİLDİR (fail-closed).
    """
    if package == YEREL_PAKET:
        return
    if not transport or not transport.strip():
        # Z118ⓑ: ipucu ARAÇ adını verir (`adt_transport_list`); `list_user_transports` istemci metodudur
        # (lib/sap_client.py), model onu çağıramaz. Ad araç kayıt tablosunda testle bağlı (test_guvenlik_sertlestirme B1).
        raise GuardrailViolation(
            "ADR_0005_C",
            f"{what} için transport zorunlu — adt_transport_list ile aktif transportları sor ve kullanıcıya doğrulat",
        )


def require_tr_text(text: str | None, *, what: str = "label") -> None:
    """ADR 0005 §D: Z'li obje metni (master_language dilinde) zorunlu, boş bırakılamaz.

    aXet: ad kaynakla uyum için korundu; dil denetimi yazma kapısındadır (bağlantı dili ==
    sap-project.json master_language, aksi `language_mismatch`). Bu fonksiyon doluluğa bakar.
    """
    if not text or not text.strip():
        raise GuardrailViolation(
            "ADR_0005_D",
            f"master_language dilinde metin zorunlu — {what} boş bırakılamaz",
        )


def require_all_labels(labels: dict, expected: Iterable[str]) -> None:
    """ADR 0005 §D: DTEL 4 label (short/medium/long/heading) dolu zorunlu."""
    missing = [k for k in expected if not labels.get(k, "").strip()]
    if missing:
        raise GuardrailViolation(
            "ADR_0005_D",
            f"4 label zorunlu — eksik: {', '.join(missing)}",
            missing=missing,
        )


# aXet 2026-09-13: DTEL etiket uzunluğu — mevcut ADR_0005_D ön kontrolünün genişletmesi (yeni kapı DEĞİL).
# Kanıt: lib/validators/check_dtel_creation_labels.py:67 `_MAX` (kural R4, :27) ve aynı dosya :125-131
# (`len()` kırpılmış değer üzerinde). Değerler orada tek kaynak; eşitlik test_set_description_labels'ta zorlanır.
DTEL_LABEL_MAX = {"short": 10, "medium": 20, "long": 40, "heading": 55}


def require_label_lengths(labels: dict) -> None:
    """ADR 0005 §D: DTEL etiketi SAP alan uzunluğunu aşamaz (kırpılır/yarım metin kalır)."""
    asan = {k: len((labels.get(k) or "").strip()) for k, m in DTEL_LABEL_MAX.items()
            if len((labels.get(k) or "").strip()) > m}
    if asan:
        raise GuardrailViolation(
            "ADR_0005_D",
            "DTEL etiket uzunluğu aşıldı — " + ", ".join(f"{k}={n}>{DTEL_LABEL_MAX[k]}" for k, n in asan.items())
            + " (sınırlar short 10 · medium 20 · long 40 · heading 55; metni kısaltmayı kullanıcıya sor)",
            too_long=asan,
        )


def reject_standard_delete(name: str, object_type: str | None = None, *, root=None) -> None:
    """ADR 0005 §A: standart obje delete yasak. Lock objeleri (ENQU) E+Z/Y ve bildirilmiş /<NS>/ meşru."""
    if not _is_customer_namespace(name or "", object_type, root=root):
        raise GuardrailViolation(
            "ADR_0005_A",
            f"Standart obje sil yasak — '{name}' Z/Y (lock için E+Z/Y) ya da bildirilmiş "
            f"müşteri namespace'i ile başlamıyor{_ad.red_gerekcesi(name or '', root=root)}",
            name=name,
        )


# ADR 0010 — yalnızca DEV tier'da mutasyon serbest. QA/PRD salt-okunur.
_WRITABLE_TIERS = frozenset({"DEV"})


def require_writable_tier(tier: str | None, *, what: str = "mutasyon") -> None:
    """ADR 0010: create/push/activate/delete yalnızca DEV tier'da serbest.

    QA/PRD salt-okunur → yazma reddedilir. "Safety is not memory, it is code":
    tier .conn_adt'den okunur (sapadt._conn.get_active_tier), agent
    hatırlamasına bırakılmaz.

    ⚠ FAIL-CLOSED (2026-08-01 KAYIT-1): tier None/boş/UNKNOWN ise DEV VARSAYILMAZ —
    reddedilir. Eski `(tier or "DEV")` İKİNCİ bir fail-open katmanıydı: _conn
    fail-closed'a çevrilse bile buradaki varsayılan korumayı yeniden kapatırdı.
    """
    t = (tier or "").strip().upper() or "UNKNOWN"
    if t == "UNKNOWN":
        raise GuardrailViolation(
            "ADR_0010_TIER",
            f"{what} reddedildi — aktif sistemin tier'ı ÇÖZÜLEMEDİ (fail-closed). "
            f"Bilinmeyen tier DEV sayılmaz (PRD'de olup DEV sanma riski). Düzelt: "
            f".conn_adt'ye 'ADT_SAP_TIER=DEV|QA|PRD' satırını ekle (TAM anahtar — "
            f"'ADT_SAP_TIER_OLD=...' sayılmaz). Ortam değişkeni SAYILMAZ. "
            f"Salt-okuma serbesttir.",
            tier=t,
        )
    if t not in _WRITABLE_TIERS:
        raise GuardrailViolation(
            "ADR_0010_TIER",
            f"{what} reddedildi — aktif sistem tier={t} (salt-okunur). "
            f"Mutasyon (create/push/activate/delete) yalnızca DEV'de serbest. "
            f".conn_adt tier'ını doğrula (yazma yalnız DEV bağlantısında).",
            tier=t,
        )
