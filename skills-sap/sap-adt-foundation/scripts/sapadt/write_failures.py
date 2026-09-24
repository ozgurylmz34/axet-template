# -*- coding: utf-8 -*-
"""SAP yazma PATİNAJ KESİCİSİ — `<proje>/.axet-code/sap-write-failures.json` (Z90).

Aynı obje + aynı hata koduyla art arda `ESIK` (3) başarısız yazmadan SONRAKİ yazma çağrısı SAP'ye
gidilmeden `repeated_failure` (çıkış 2) ile reddedilir: "dur, kök sebebi kullanıcıyla konuş".
Hook'taki "aynı objede EN ÇOK 3 deneme" kuralının CLI karşılığıdır (3 deneme serbest, 4.'sü durur).

Sayılan: yazma sınıfı bir aracın GERÇEKTEN çağrıldığı ve sonucun başarısız olduğu deneme (çıkış ≠ 0).
Sayılmayan: araçtan önce düşen kapı reddi (`on_kontrol`) ve bu kesicinin kendi reddi (yazma denenmedi).
Sıfırlama: başarılı yazma (kayıt silinir) · farklı hata kodu (seri 1'den yeniden başlar) · son başarısızlıktan
bu yana `PENCERE` (2 saat) geçmesi. Elle sıfırlama: KULLANICI kaydı ya da dosyayı siler.

Pencere gerekçesi (2 saat): patinaj tek bir iş oturumunun içinde, dakikalar ölçeğinde art arda gelen denemedir;
2 saat bir oturumun tamamını kapsar (aynı seri yarım saat ara ile sürse de yakalanır) ama ertesi güne / kullanıcıyla
konuşulup kök sebep düzeltildikten sonraki meşru bir denemeye bayat bir kilit olarak taşınmaz.

⚠ Bu bir FRENDİR, güvenlik kapısı DEĞİL: dosya okunamaz/bozuksa ya da yazılamazsa yazma ENGELLENMEZ
(fail-open) — çağıran stderr'e tek satır uyarı basar. Host/kullanıcı/client YAZILMAZ.
Kayıt şeması: {"<tip>:<AD>": {"code": <hata kodu>, "count": <int>, "last_at": <ISO-8601 UTC>}}
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import tempfile
from pathlib import Path

from sapadt import project as _project

FAILURES_REL = Path(".axet-code") / "sap-write-failures.json"
ESIK = 3
PENCERE = _dt.timedelta(hours=2)
KOD = "repeated_failure"


def dosya(proj=None) -> Path:
    return _project.project_dir(proj) / FAILURES_REL


def anahtar(obje, object_type) -> str | None:
    """Pull-state ile aynı anahtar (tip eşanlamlıları tek anahtara iner). Obje adı yoksa None → sayaç yok."""
    if not isinstance(obje, str) or not obje.strip():
        return None
    from sapadt import pull_state as _ps
    return _ps.anahtar(obje, object_type or "")


def _simdi() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


def _oku(proj) -> tuple[dict, str | None]:
    p = dosya(proj)
    if not p.is_file():
        return {}, None
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception as exc:  # noqa: BLE001
        return {}, f"{FAILURES_REL.as_posix()} okunamadı ({type(exc).__name__})"
    if not isinstance(data, dict):
        return {}, f"{FAILURES_REL.as_posix()} geçersiz: kök bir JSON nesnesi değil"
    return data, None


def _yaz(proj, data: dict) -> str | None:
    p = dosya(proj)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        fd, gecici = tempfile.mkstemp(prefix=".sap-write-failures.", suffix=".tmp", dir=str(p.parent))
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
        os.replace(gecici, p)
        return None
    except OSError as exc:
        return f"{FAILURES_REL.as_posix()} yazılamadı ({type(exc).__name__})"


def _taze(rec, simdi) -> bool:
    try:
        son = _dt.datetime.fromisoformat(str(rec.get("last_at")))
    except (TypeError, ValueError):
        return False
    if son.tzinfo is None:
        son = son.replace(tzinfo=_dt.timezone.utc)
    return simdi - son <= PENCERE


def kontrol(obje, object_type, proj=None) -> tuple[dict | None, str | None]:
    """Yazmadan ÖNCE: (engel|None, uyarı|None). Engel = {code, count, last_at, key} (seri ESIK'e ulaşmış)."""
    k = anahtar(obje, object_type)
    if k is None:
        return None, None
    data, hata = _oku(proj)
    if hata:
        return None, hata
    rec = data.get(k)
    if not isinstance(rec, dict) or not isinstance(rec.get("count"), int):
        return None, None
    if rec["count"] >= ESIK and _taze(rec, _simdi()):
        return {"key": k, "code": rec.get("code"), "count": rec["count"], "last_at": rec.get("last_at")}, None
    return None, None


def kaydet(obje, object_type, hata_kodu: str | None, proj=None) -> tuple[dict | None, str | None]:
    """Yazma SONRASI: hata_kodu None = başarı (kayıt silinir). Dönüş: (seri|None, uyarı|None).

    Seri = {code, count, limit} — yalnız başarısızlıkta; çağıran yanıta ekler."""
    k = anahtar(obje, object_type)
    if k is None:
        return None, None
    data, hata = _oku(proj)   # bozuk dosya yeni kayıtla ONARILIR (diğer seriler düşer → fren gevşer, fail-open)
    if hata_kodu is None:
        if data.pop(k, None) is None and not hata:
            return None, None
        return None, _yaz(proj, data) or hata
    simdi = _simdi()
    rec = data.get(k)
    if (isinstance(rec, dict) and rec.get("code") == hata_kodu and isinstance(rec.get("count"), int)
            and _taze(rec, simdi)):
        sayi = rec["count"] + 1
    else:
        sayi = 1
    data[k] = {"code": hata_kodu, "count": sayi, "last_at": simdi.isoformat(timespec="seconds")}
    return {"code": hata_kodu, "count": sayi, "limit": ESIK}, _yaz(proj, data) or hata


def red_mesaji(engel: dict) -> str:
    return (f"PATİNAJ KESİCİSİ: {engel['key']} için aynı hata kodu ({engel['code']}) ile art arda {engel['count']} "
            f"başarısız yazma (son: {engel['last_at']}). Bu yazma DENENMEDİ. DUR — aynı çağrıyı tekrarlama; kök "
            "sebebi kullanıcıyla konuş (ham hata + denenenler + bulgu). Seri başarılı bir yazmayla, farklı bir hata "
            f"koduyla ya da son başarısızlıktan {int(PENCERE.total_seconds() // 3600)} saat sonra sıfırlanır; erken "
            f"sıfırlama kararı KULLANICININDIR ({FAILURES_REL.as_posix()} içindeki kaydı kullanıcı siler).")
