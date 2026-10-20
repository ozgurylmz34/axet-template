# -*- coding: utf-8 -*-
"""ADT XML gövdesi için ortak kaçış ve `adtcore:responsible` çözümü (TEK KAYNAK).

NEDEN (Z194, 2026-10-19; kaynak çekirdek `scripts/utils/xml_kacis.py`): yaratma/yazma gövdeleri
kullanıcı metnini (açıklama, sorumlu, etiket) f-string ile XML'e koyuyordu. Kaçış yapan
yerler yedi ayrı kopyaydı (`_xml_escape`, iki `_att` lambda'sı, `esc`, `_xe`, araç
modüllerinde üç `_att`) ve her biri farklı karakter kümesi kaçışlıyordu: biri `"` işaretini
kaçırmıyordu (çıplak `xml.sax.saxutils.escape`), çoğu hiç kaçış yapmıyordu. `&`, `<` ya da
`"` içeren bir açıklama gövdeyi iyi biçimli olmaktan çıkarıyordu; sorumlu çözülemeyince
f-string `adtcore:responsible="None"` yazıyordu.

Kural:
  * ÖZNİTELİK değeri → `attr_escape` (`& < > "` + TAB/LF/CR).
  * ELEMAN metni     → `text_escape` (`& < >`).
  * Sorumlu          → `sorumlu_coz`; `None` dönerse çağıran AĞ ÇAĞRISINDAN ÖNCE durur.

Bu modülün yan etkisi yoktur (stdout'u sarmaz, ağ açmaz); her katman güvenle import eder.
"""
from __future__ import annotations

from xml.sax.saxutils import escape as _sax_escape

# `"` + satır/sekme karakterleri: XML öznitelik değeri NORMALLEŞTİRMESİ çıplak TAB/LF/CR'yi
# boşluğa çevirir ⇒ kaçışlanmazsa gönderilen metin SAP'de farklı okunur (ör. canlı bir mesaj
# metni geri gönderilince sessizce değişir). Tek tırnak kaçışlanmaz: tüm öznitelikler çift
# tırnakla yazılır.
_ATTR_KACIS = {'"': "&quot;", "\t": "&#9;", "\n": "&#10;", "\r": "&#13;"}


def _metin(v) -> str:
    return "" if v is None else str(v)


def attr_escape(v) -> str:
    """XML ÖZNİTELİK değeri kaçışı: `& < >` + ÇİFT TIRNAK + TAB/LF/CR. `None` → boş dize.

    ⛔ Çıplak `xml.sax.saxutils.escape()` `"` işaretini KAÇIRMAZ (`escape('a"b')` → `'a"b'`).
    """
    return _sax_escape(_metin(v), _ATTR_KACIS)


def text_escape(v) -> str:
    """XML ELEMAN metni kaçışı: `& < >`. `None` → boş dize."""
    return _sax_escape(_metin(v))


def sorumlu_coz(verilen, client) -> str | None:
    """`adtcore:responsible` değeri: verildiyse o, yoksa bağlantı kullanıcısı (`client.user`).

    İkisi de boşsa `None` döner; çağıran YAZMADAN ve ağa çıkmadan durur. Kaçış burada
    YAPILMAZ: değer ham döner, gövdeyi yazan yer `attr_escape` uygular (çift kaçış olmasın).
    """
    deger = verilen or getattr(client, "user", None)
    if not isinstance(deger, str) or not deger.strip():
        return None
    return deger


SORUMLU_YOK_MESAJI = (
    "adtcore:responsible ÇÖZÜLEMEDİ: sorumlu verilmedi ve bağlantı kullanıcısı (.conn_adt "
    "ADT_SAP_USER) boş. Yer tutucu yazılmaz; HİÇBİR İSTEK GÖNDERİLMEDİ. Bağlantı dosyasındaki "
    "kullanıcıyı düzelt ve tekrar dene.")
