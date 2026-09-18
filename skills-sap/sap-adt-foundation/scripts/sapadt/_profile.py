# -*- coding: utf-8 -*-
"""Profil-bazlı araç yüzeyi (kaynak çekirdekteki `_profile.py`'nin uyarlaması).

Fark: profil `project.yaml` yerine proje kökündeki `sap-project.json`'dan okunur ve
uygunluk import anında değil ÇAĞRI anında denetlenir (bkz. `_app.py`).

Kanıt disiplini aynen: bugün tek matris-kanıtlı daraltma `adt_transport_list` ∉ `btp_abap`
(gCTS'te klasik CTS ucu yok). Diğer araçlar `("all",)` — kanıtsız daraltma yapılmaz.

FAIL-CLOSED: profil çözülemezse HİÇBİR araç uygun değildir (`ping` hariç; o CLI'de ayrıca açıktır).
"""
from __future__ import annotations

from sapadt.project import GECERLI_PROFILLER, load_sap_project

HEPSI = ("all",)


def aktif_profil(proj=None) -> str | None:
    """`sap-project.json` → `sap_profile`. Geçersiz/eksikse None (fail-closed sinyali)."""
    cfg, _hata = load_sap_project(proj)
    if not cfg:
        return None
    p = cfg.get("sap_profile")
    return p if p in GECERLI_PROFILLER else None


def uygun_mu(available_on: tuple, profil: str | None) -> bool:
    """Profil bilinmiyor VEYA enum-dışıysa HİÇBİR araç uygun değildir (fail-closed)."""
    if profil is None or profil not in GECERLI_PROFILLER:
        return False
    return "all" in available_on or profil in available_on


# ── OBJE TİPİ düzeyinde daraltma (aXet 2026-09-13) ──────────────────────────────────────────
# Genel yazma araçları (`adt_post_shell`, `adt_push_source`) birden çok obje tipi alır; araç
# düzeyindeki `available_on` tipi ayırt edemez. Klasik FUGR/FM yaratma/yazma `s4_public` ve
# `btp_abap` (ABAP Cloud) profillerinde kapalıdır — KAYNAK: lider kararı (görev E, 2026-09-13);
# profil matrisinin canlı kanıtı DEĞİLDİR. Klasik dynpro üreteci ise araç düzeyinde daraltılır
# (`tools/screen.py` `available_on`). Okuma araçları daraltılmaz.
TIP_PROFIL_KISITI = {
    "functiongroup": ("ecc", "s4_private"),
    "function": ("ecc", "s4_private"),
}
TIP_KISITLI_ARACLAR = frozenset({"adt_post_shell", "adt_push_source"})


def tip_kanonik(object_type) -> str | None:
    t = str(object_type or "").strip().lower()
    if not t:
        return None
    try:
        import object_types as _ot  # type: ignore
        if _ot.is_class_include(t):
            return _ot.normalize_class_include(t)
        return _ot.normalize_object_type(t)
    except Exception:  # noqa: BLE001 — tanınmayan tip kısıt tablosunda da yoktur
        return t


def tip_uygun_mu(tool: str, object_type, profil: str | None) -> tuple[bool, tuple | None]:
    """(uygun, izinli_profiller|None). Kısıt tablosunda olmayan tip daima uygundur."""
    if tool not in TIP_KISITLI_ARACLAR:
        return True, None
    izinli = TIP_PROFIL_KISITI.get(tip_kanonik(object_type) or "")
    if izinli is None:
        return True, None
    return (profil in izinli), izinli
