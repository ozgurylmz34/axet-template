# -*- coding: utf-8 -*-
"""Kaynak metin normalizasyonu — kaynak çekirdekteki `source_drift.normalize_source`'un AYNI kopyası.

Yalnız bu fonksiyon taşındı: `tools/atom.py::_content_readback` push edilen kaynağı canlı AKTİF
kaynakla kıyaslarken kullanır. `source_drift`'in geri kalanı (repo ↔ canlı dosya senkronu,
git geçmişi taraması) aXet'te kullanılmaz ve bilinçli olarak taşınmadı.
"""
from __future__ import annotations


def normalize_source(text: str) -> str:
    """Source'u kıyas için normalize et.

    CRLF↔LF + satır-sonu trailing whitespace + baştaki/sondaki boş satır farkını
    YOK SAY. Yoksa SAHTE drift olur (raw diff her satırı CRLF↔LF farkıyla sayar).
    İç boşlukları/içerik farkını KORUR — gerçek drift yine yakalanır.
    """
    if text is None:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln.rstrip() for ln in text.split("\n")]
    while lines and lines[0] == "":
        lines.pop(0)
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)
