"""Atom tools — single ADT REST operation each.

- adt_get          : Read object source/metadata
- adt_post_shell   : Create empty Z shell (no source)
- adt_push_source  : Push source body to existing object
- adt_activate     : Activate object

All tools:
- Return structured JSON: {ok: bool, ...}
- Capture SAPClient stdout chatter into 'client_log' field (does not pollute MCP stdio)
- Apply ADR 0005 guardrails before any SAP HTTP call
- Map SAPADTError subclasses to error codes (auth/not_found/locked/exists/...)
"""
from __future__ import annotations

import contextlib
import io
import json
import re
import tempfile
import time
from pathlib import Path
from typing import Any, Optional

from sapadt._app import log, profil_tool
from sapadt._reviewer import (
    on_kontrol_ozeti,
    reject_payload,
    run_reviewer,
    task_for_push,
)
# Q293: post-check hükmü tek kaynakta (`_reviewer.py`); composite de aynısını kullanır.
from sapadt._reviewer import post_check_notice as _post_check_notice  # noqa: E402
from sapadt._reviewer import post_check_ozeti as _post_check_ozeti  # noqa: E402
from sapadt.guardrails import (
    GuardrailViolation,
    reject_standard_delete,
    require_customer_namespace,
    require_tr_text,
    require_transport,
    require_writable_tier,
)
from sapadt._conn import get_active_tier
from sapadt import pull_state as _pull_state

# Lazy import — SAPClient pulls auth + .conn_adt; defer until first call.
_client = None
_sap_client_sig0 = None        # yüklü sap_client modülünün (size, sha1) imzası — bayat-süreç backstop'u
_sap_client_mtime_seen = None  # son stat'lanan mtime; fast-path (mtime değişmedikçe hash atlanır)


# ADR 0016 REVİZE (2026-06-16): pre-push DRIFT GUARD (M1) + post-write REPO SYNC (M2)
# KALDIRILDI. Sebep: repo≠canlı symmetric kıyası KASITLI edit'leri de blokluyordu
# (working-tree ≠ live her edit'te doğal). Yeni model = PULL-BEFORE-EDIT: edit'ten ÖNCE
# güncel çekilir (PreToolUse Edit|Write hook, scripts/hooks/pull_before_edit.py + seans
# tazelik), böylece push'ta ayrıca kontrol gerekmez. Bkz. ADR 0016 + scripts/sap_sync_pull.py.

# ── READBACK-GATE (2026-06-21, onaylı) ──────────────────────────────────────
# Sorun (kanıt: ZDEMO1_I_SHIP_POOL `where` kaybı): yazım SAP'de TAM oturmayabilir
# (activate eksik/kısmi, ya da aktif sürüm push edilenden geride kalır) ama tool "ok"
# döner → sessizce drift. Çözüm: activate SONRASI aktif source'u çek + push edilenle
# normalize-compare; fark varsa BLOCKER (ok=False). Delete sonrası: obje hâlâ varsa BLOCKER.
# Maliyet ölçüldü ~50ms/obje (sıcak session). XML-DDIC source taşımaz → content-compare ATLA
# (composite create + _activate_and_verify alan-verify'i kapsar).
# NAME-COLLISION FIX (2026-06-21, canlı vaka kanıtı): ZDEMO1_I_SHIP_POOL hem DDLS (CDS) hem
# BDEF olabilir. Yalnız İSİMLE key'lersek BDEF push'u CDS kaydını EZER → BDEF aktive edilince
# readback CDS-source ile kıyaslayıp SAHTE-mismatch verir. Çözüm: (name.upper(), type_key) ile key.
#
# ⛔ Q271 (2026-09-09) — BAYAT BASELINE → **SAHTE `content_mismatch`** (sahte-negatif sınıfı).
# ÖLÇÜLEN KÖK: kayıt YALNIZ push TAM başarılıysa yazılıyordu (eski `:1074` → `if ok:`), oysa
# `push_object` başarısı `source_uploaded AND activated AND readback is not False`tir
# (`scripts/sap_client.py:1030`). AKTİF kaynağı belirleyen şey **UPLOAD**tur, aktivasyon değil:
# upload'ı geçip aktivasyonu patlayan bir push (T11 base↔consumption rename kilidi — canlı vaka
# `playbook/adt-cds.md:622` "T11-a content_mismatch false-alarm") kaydı GÜNCELLEMEZ. Sonraki
# `adt_activate` (ör. `also=` ile atomik co-activation) canlı YENİ kaynağı bir ÖNCEKİ push'un
# ESKİ kaynağıyla kıyaslar → "yazım oturmadı, re-push gerekli" diye SAHTE BLOCKER.
# Kaydın taşımadığı üç şey vardı: **kaynak** (hangi upload), **zaman** (ne kadar eski),
# **kapsam** (hangi SAP sistemi). Üçü de artık kayıtta ve kıyas anında değerlendirilir.
#   • baseline UPLOAD anında yazılır (aktivasyon başarısı ölçüt DEĞİL)
#   • push İSTİSNA ile biterse: yüklenen kaynak BİLİNMİYOR ⇒ kayıt "belirsiz" işaretlenir —
#     eşitlik hâlâ YEŞİL kanıttır, ama fark artık KIRMIZI İDDİA ETMEZ (⚠ bilinçli gevşetme)
#   • kayıt başka bir binding'e (host|client) aitse kıyas YAPILMAZ ("doğrulandı" da DEMEZ)
#   • `content_reason` artık künye (push sırası · yaş · aktive · sistem) + diff YÖNÜ taşır
_LAST_PUSHED: dict[tuple[str, str], dict] = {}
# kayıt şeması (değer): {"object_type", "source", "ts", "sira", "binding",
#                        "aktive": bool, "belirsiz": str|None, "dogrulandi_ts": float|None}
_PUSH_SIRA = 0   # süreç-içi monoton push sayacı (künye: "kaçıncı upload")
_TYPE_KEY_CANON = {
    "cds": "ddls", "cdsview": "ddls", "ddl": "ddls", "ddls": "ddls",
    "behaviordefinition": "bdef", "bdef": "bdef",
    "servicedefinition": "srvd", "srvd": "srvd",
    "clas": "class", "class": "class", "intf": "interface", "interface": "interface",
    "prog": "program", "program": "program",
}


def _type_key(t: str) -> str:
    """Tip eşanlamlılarını kanonikleştir (cds/ddl→ddls, behaviordefinition→bdef, ...)."""
    t = (t or "").lower().strip()
    return _TYPE_KEY_CANON.get(t, t)


_SOURCE_BASED_TYPES = {
    "ddls", "cds", "cdsview", "ddl", "bdef", "behaviordefinition",
    "srvd", "servicedefinition", "class", "clas", "program", "prog",
    "interface", "intf", "dcl", "dcls", "accesscontrol", "ddlx", "metadataextension",
}


def _binding_imzasi(client) -> str:
    """Client'in BAĞLI olduğu sistemin imzası: 'host|client-no'. Çözülemezse ''.

    Q271 KAPSAM boyutu: baseline hangi sisteme yazıldıysa kıyas ancak orada anlamlıdır
    (switch_tier + /mcp restart edilmemiş süreç → `_guard_binding_current` asıl katman;
    bu, kaydın KENDİ üzerinde taşıdığı ikinci kayıttır)."""
    try:
        from urllib.parse import urlparse
        adt = getattr(client, "adt_client", None) or client
        url = str(getattr(adt, "url", "") or "")
        host = (urlparse(url if "://" in url else "https://" + url).hostname or "").lower()
        return "%s|%s" % (host, getattr(adt, "client", "") or "")
    except Exception:  # noqa: BLE001 — künye üretimi ADT işlemini asla kırmaz
        return ""


def _baseline_yaz(client, name: str, object_type: str, source: str, *, aktive: bool) -> None:
    """Q271: readback baseline'ını YAZ — tetikleyici UPLOAD'dır, aktivasyon başarısı DEĞİL.

    Aktif sürümü belirleyen şey yüklenen kaynaktır; aktivasyon ayrı bir adımdır ve
    patlayabilir (T11 kilidi). Aktivasyon patladıysa kayıt yine yazılır ama `aktive=False`
    damgasıyla — böylece bir sonraki `adt_activate` GERÇEKTEN doğru baseline'la kıyaslar."""
    global _PUSH_SIRA
    _PUSH_SIRA += 1
    _LAST_PUSHED[(name.upper(), _type_key(object_type))] = {
        "object_type": object_type,
        "source": source,
        "ts": time.time(),
        "sira": _PUSH_SIRA,
        "binding": _binding_imzasi(client),
        "aktive": bool(aktive),
        "belirsiz": None,
        "dogrulandi_ts": None,
    }


def _baseline_belirsiz(name: str, object_type: str, sebep: str) -> None:
    """Q271: push İSTİSNA ile bitti → SAP'ye ne yüklendiği BİLİNMİYOR.

    Kayıt SİLİNMEZ (eşitlik hâlâ olumlu kanıttır) ama KIRMIZI iddia hakkı düşer:
    belirsiz baseline'la 'yazım oturmadı' demek, doğru işi yanlış sanmaktır."""
    rec = _LAST_PUSHED.get((name.upper(), _type_key(object_type)))
    if isinstance(rec, dict):
        rec["belirsiz"] = sebep


def _baseline_kunye(rec: dict) -> dict:
    """Kaydın KAYNAK/ZAMAN/KAPSAM künyesi — her content_* yanıtında görünür."""
    ts = rec.get("ts") or 0.0
    import datetime as _dt
    return {
        "push_sira": rec.get("sira"),
        "push_zaman": _dt.datetime.fromtimestamp(ts).isoformat(timespec="seconds") if ts else None,
        "yas_sn": round(max(0.0, time.time() - ts), 1) if ts else None,
        "push_aktive_etti": rec.get("aktive"),
        "binding": rec.get("binding") or None,
        "belirsiz": rec.get("belirsiz"),
        "onceden_dogrulandi": bool(rec.get("dogrulandi_ts")),
    }


def _kunye_metni(k: dict) -> str:
    return ("BASELINE: push#%s · %s (%s sn önce) · o push aktive etti mi=%s · sistem=%s%s"
            % (k.get("push_sira"), k.get("push_zaman"), k.get("yas_sn"),
               k.get("push_aktive_etti"), k.get("binding"),
               (" · BELİRSİZ=%s" % k["belirsiz"]) if k.get("belirsiz") else ""))


def _content_readback(client, name: str, object_type: str) -> dict:
    """Activate sonrası: AKTİF source'u çek + bu seansta YÜKLENEN kaynakla normalize-compare.

    Yalnız source-based tip + bu süreçte upload kaydı varsa çalışır (salt re-activate'te
    kayıt yok → atla). Fark = yazım tam oturmadı → blocker sinyali.

    ⛔ Q271: KIRMIZI iddia (content_mismatch) yalnız baseline'ın KAYNAĞI, ZAMANI ve KAPSAMI
    kıyasa uygunsa kurulur. Uygun değilse üçüncü değer (`content_verified: None`) döner —
    bu 'doğrulandı' DEĞİLDİR, 'ölçemedim'dir; ama sahte blocker da üretmez.

    ⭐ `content_probe` = MAKINE-OKUNUR ayirt edici. Uc `None` yolu ("olcemedim") aksi halde
    TEK bir degere coker ve kazanilan ayrim kaybolur (lider notu, 2026-09-09):
      esitlik · fark · baseline_belirsiz · baseline_baska_binding · url_cozulemedi ·
      okuma_hatasi   (sozlesme: `content_verified` NE ise `content_probe` NEDEN'i verir)

    Returns: {} (uygulanmaz) | {content_verified: True, content_probe: 'esitlik', content_baseline}
           | {content_verified: False, content_mismatch: True, content_probe: 'fark',
              content_reason, content_diff, content_baseline}
           | {content_verified: None, content_probe: <sebep-kodu>, content_reason,
              content_baseline[, content_diff, content_stale_baseline: True]}
    """
    t = (object_type or "").lower().strip()
    if t not in _SOURCE_BASED_TYPES:
        return {}
    rec = _LAST_PUSHED.get((name.upper(), _type_key(object_type)))
    if not rec:
        return {}
    pushed = rec.get("source") or ""
    kunye = _baseline_kunye(rec)

    # KAPSAM: kayıt başka bir sisteme yazıldıysa kıyas ANLAMSIZ (tier ayrışması).
    simdiki = _binding_imzasi(client)
    if rec.get("binding") and simdiki and rec["binding"] != simdiki:
        return {
            "content_verified": None,
            "content_probe": "baseline_baska_binding",
            "content_baseline": kunye,
            "content_reason": (
                "BASELINE BAŞKA SİSTEME AİT (%s ≠ %s) — içerik kıyası YAPILMADI. "
                "Bu 'doğrulandı' DEĞİLDİR; aynı sisteme push edip yeniden aktive et ya da "
                "`adt_get(version=active)` ile elle teyit et. %s"
                % (rec["binding"], simdiki, _kunye_metni(kunye))),
        }
    try:
        import sap_adt_lib as L  # type: ignore
        from source_normalize import normalize_source  # type: ignore
        adt = getattr(client, "adt_client", None) or client
        url = L._resolve_source_url(name, t)
        if not url:
            return {"content_verified": None, "content_probe": "url_cozulemedi",
                    "content_baseline": kunye,
                    "content_reason": f"source URL çözülemedi (type={t}) — content readback atlandı"}
        with _capture_stdout():   # SAPClient stdout chatter MCP stdio'yu kirletmesin
            live = adt.get_object_source(url, version="active")
    except Exception as exc:  # noqa: BLE001
        return {"content_verified": None, "content_probe": "okuma_hatasi",
                "content_baseline": kunye,
                "content_reason": f"content readback exception: {exc}"}

    n_pushed, n_live = normalize_source(pushed), normalize_source(live)
    if n_pushed == n_live:
        rec["dogrulandi_ts"] = time.time()
        return {"content_verified": True, "content_probe": "esitlik",
                "content_baseline": kunye}

    import difflib
    p_satir, l_satir = n_pushed.splitlines(), n_live.splitlines()
    diff = "\n".join(difflib.unified_diff(
        p_satir, l_satir, fromfile="pushed", tofile="active", lineterm="", n=1))[:1500]
    # YÖN (Q271): hangi tarafta fazlalık var? Yalnız-aktifte satır varsa aktif sürüm
    # baseline'ın BİLMEDİĞİ içerik taşıyor ⇒ ilk hipotez "push oturmadı" DEĞİL,
    # "baseline bayat" olmalıdır. Sayı vermeden "uyuşmuyor" demek teşhisi geciktirir.
    yalniz_push = len([s for s in p_satir if s not in set(l_satir)])
    yalniz_aktif = len([s for s in l_satir if s not in set(p_satir)])
    yon = ("YÖN: yalnız-push'ta %d satır · yalnız-aktifte %d satır (aktifte fazlalık varsa "
           "baseline bayat olabilir — aktif sürüm başka bir yazımdan gelmiş)"
           % (yalniz_push, yalniz_aktif))

    if rec.get("belirsiz"):
        # ⚠ GEVŞETME (bilinçli, Q271): baseline'ın KAYNAĞI belirsizken (push istisna ile
        # bitti → SAP'ye ne yüklendiği bilinmiyor) FARK bir blocker'a çevrilmez. Sebep:
        # bu durumda "re-push gerekli" iddiası DOĞRU İŞİ yanlış gösterebilir. Bilgi
        # kaybolmaz: diff + künye + uyarı yanıtta durur, yalnız `ok` düşmez.
        return {
            "content_verified": None,
            "content_probe": "baseline_belirsiz",
            "content_stale_baseline": True,
            "content_baseline": kunye,
            "content_diff": diff,
            "content_reason": (
                "AKTİF source baseline'la aynı DEĞİL — ama baseline GÜVENİLMEZ (%s) ⇒ "
                "'yazım oturmadı' İDDİA EDİLMEDİ (sahte blocker riski). Bu 'doğrulandı' da "
                "DEĞİLDİR: `adt_get(version=active)` ile kaynağı gözle teyit et. %s · %s"
                % (rec["belirsiz"], yon, _kunye_metni(kunye))),
        }

    return {
        "content_verified": False,
        "content_mismatch": True,
        "content_probe": "fark",
        "content_baseline": kunye,
        "content_reason": ("AKTİF source YÜKLENEN kaynakla EŞLEŞMİYOR — yazım SAP'de tam oturmadı "
                           "(activate eksik/kısmi ya da aktif sürüm geride; 'where'-kaybı sınıfı). "
                           "Re-push + re-activate gerekli; pull etmeden ÖNCE düzelt. %s · %s"
                           % (yon, _kunye_metni(kunye))),
        "content_diff": diff,
    }


def _exists_after_delete(client, name: str, object_type: str):
    """Delete sonrası varlık readback → (durum, sebep).

    durum: True = hâlâ var (silme oturmadı) · False = YOKLUĞU KANITLI (silme oturdu)
           · None = doğrulama KOŞAMADI (iddia yok).

    ⛔ 2026-08-01 bug-avı, "doğrulama koşamadı = doğrulandı" sınıfı: burada eskiden
    `return md is not None` yazıyordu. `get_object_metadata` HER istisnayı yutup `None`
    döndürdüğü için (sap_client.py: `except Exception: print("[ERROR]..."); return None`)
    aşağıdaki `except` dalı bu yolda HİÇ ateşlenmiyordu → HTTP 500 / 403-logon / timeout /
    bağlantı kopması hepsi `md=None` → `False` → **`delete_verified: True`**. Yani silmenin
    OTURDUĞUNA dair kanıt üretilemediği durum, "oturdu" diye raporlanıyordu (silme geri
    alınamaz ve bir sonraki adım bu iddiaya dayanır: yeniden yaratma / TR kapatma).
    Artık yokluk yalnız KANITLI ise (404 imzası ya da temiz-boş yanıt) beyan edilir.
    """
    log_buf = io.StringIO()
    try:
        with _capture_stdout() as out:   # SAPClient stdout chatter MCP stdio'yu kirletmesin
            md = client.get_object_metadata(name, object_type=object_type)
        log_buf.write(out.getvalue())
        if md is not None:
            return True, ""
        sinif = _bos_sonuc_sinifi(log_buf.getvalue())
        if sinif == "yok":
            return False, ""
        return None, (
            f"Silme sonrası varlık readback KOŞAMADI ({sinif}) — obje okunamadı ve sebep "
            f"BULUNAMADI-DEĞİL bir hata. Bu 'silindi' KANITI DEĞİLDİR; SE80/adt_get ile "
            f"elle teyit et. Log: {log_buf.getvalue().strip()[:200]}"
        )
    except Exception as exc:  # noqa: BLE001
        # NotFound/erişilemez → 'yok' iddiası etme; soft
        return None, f"Silme sonrası varlık readback yapılamadı ({type(exc).__name__}: {exc})."


# ── Q273 (2026-09-13) — POST-CHECK `ok` ETKİSİ: yalnız BLOCKER düşürür ─────────────────
# Q293 (2026-09-13): `_post_check_ozeti` / `_post_check_notice` TEK KAYNAĞA taşındı →
# `sapadt/_reviewer.py::post_check_ozeti|post_check_notice` (gerekçe + karar
# orada). Bu modüldeki adlar üstteki import takma adlarıdır (fixture mutasyonu atom
# ad alanından enjekte eder).


def _get_client():
    global _client, _sap_client_sig0, _sap_client_mtime_seen
    if _client is None:
        from sap_client import SAPClient  # type: ignore
        _client = SAPClient()
        _sap_client_sig0 = _module_file_sig("sap_client")     # yüklü sürümün imzası (bayat-süreç baz)
        _sap_client_mtime_seen = _module_file_mtime("sap_client")  # fast-path başlangıç mtime'ı
        _record_active_binding(_client)
        log.info("SAPClient initialised")
    else:
        _guard_binding_current(_client)  # cache'li client bağlantı-stale ise REDDET (backstop)
        _guard_module_current()          # sap_client.py disk'te değişti ise (bayat-süreç) REDDET
    return _client


def _module_file_mtime(modname: str):
    """Yüklü modülün disk dosyasının mtime'ı; bilinemezse None. (fast-path stat'ı.)"""
    try:
        import sys, os
        f = getattr(sys.modules.get(modname), "__file__", None)
        return os.path.getmtime(f) if f and os.path.isfile(f) else None
    except Exception:  # noqa: BLE001
        return None


def _module_file_sig(modname: str):
    """Yüklü modülün disk dosyasının (size, sha1) imzası; bilinemezse None.

    Yükleme anında çağrılır → o anki disk içeriği = belleğe yüklenen kod. Sonradan
    dosya değişirse imza ayrışır. (mtime DEĞİL hash: git checkout/CRLF mtime'ı değiştirip
    yanlış-pozitif yapabilir; içerik-hash yalnız gerçek kod değişiminde tetikler.)"""
    try:
        import sys, os, hashlib
        m = sys.modules.get(modname)
        f = getattr(m, "__file__", None)
        if not f or not os.path.isfile(f):
            return None
        data = open(f, "rb").read()
        return (len(data), hashlib.sha1(data).hexdigest())
    except Exception:  # noqa: BLE001
        return None


def _guard_module_current() -> None:
    """Backstop: MCP server uzun-ömürlü süreç → `sap_client.py` fix'ten ÖNCE yüklendiyse
    bellekte BAYAT kod çalıştırır (örn. classrun sahte 'does not implement if_oo_adt_classrun~main').

    On-disk `sap_client.py` yüklü sürümden FARKLI ise süreç bayat → ADT işlemini RED + actionable
    mesaj. `_guard_binding_current` (bağlantı-bayatlığı) ile paralel ikinci katman.

    PERF: normalde yalnız bir `stat()` (mtime). mtime değişmedikçe içerik HASH'lenmez (fast-path)
    → ADT çağrısı başına ek maliyet ≈ birkaç µs. Hash yalnız dosya gerçekten değişince (nadir) koşar.
    Check kendisi kırılırsa fail-open (yanlış-pozitif ADT'yi brick etmesin)."""
    global _sap_client_mtime_seen
    try:
        if _sap_client_sig0 is None:
            return
        mt = _module_file_mtime("sap_client")
        if mt is not None and mt == _sap_client_mtime_seen:
            return  # fast-path: dosya mtime'ı değişmemiş → hash gereksiz
        cur = _module_file_sig("sap_client")  # mtime değişti → içeriği hash'le (git-checkout no-op olabilir)
        _sap_client_mtime_seen = mt
        if cur is None:
            return
        stale = cur != _sap_client_sig0
    except Exception:  # noqa: BLE001
        return
    if stale:
        raise RuntimeError(
            "MCP SERVER BAYAT KOD: 'sap_client.py' disk'te güncellendi ama bu süreç eski sürümü "
            "bellekte çalıştırıyor (örn. adt_classrun sahte 'does not implement' hatası verebilir). "
            "ADT işlemi REDDEDİLDİ — '/mcp' ile yeniden bağlan ya da MCP server'ı restart et."
        )


def _guard_binding_current(client) -> None:
    """Backstop (ADR 0010): cache'li client'in BAGLI oldugu sistem .conn_adt ile ayni mi?

    switch_tier .conn_adt'yi degistirir ama bu surecin client'i eski sisteme bagli kalir
    (/mcp restart edilene dek). Ayrisirsa ADT islemini RED — yoksa istek eski sisteme
    gider ama tier guard yeni sistemi okur (write DEV der, ECC QA'ya gider → felaket).
    Hook (pre_tool_guard) asil katman; bu ikinci katman (bypass yok). Check kendisi
    kirilirsa fail-open (hook yakalar)."""
    try:
        from urllib.parse import urlparse
        from sapadt._conn import _conn_value
        adt = getattr(client, "adt_client", None)
        bound_url = getattr(adt, "url", "") or ""
        bound_cl = str(getattr(adt, "client", "") or "")
        cur_url = _conn_value("ADT_SAP_URL", "") or ""
        cur_cl = str(_conn_value("ADT_SAP_CLIENT", "") or "")
        bh = (urlparse(bound_url if "://" in bound_url else "https://" + bound_url).hostname or "").lower()
        ch = (urlparse(cur_url if "://" in cur_url else "https://" + cur_url).hostname or "").lower()
        differ = (bh and ch and bh != ch) or (bound_cl and cur_cl and bound_cl != cur_cl)
    except Exception:
        return  # guard'in kendi hatasi ADT'yi tamamen bricklemesin (hook authoritative)
    if differ:
        raise RuntimeError(
            f"BAĞLANTI TUTARSIZLIĞI (ADR 0010): MCP '{bh}' (client {bound_cl}) sistemine bağlı "
            f"ama .conn_adt artık '{ch}' (client {cur_cl}). switch_tier yapıldı, /mcp restart "
            f"EDİLMEDİ. ADT işlemi REDDEDİLDİ — önce '/mcp' ile yeniden bağlan."
        )


def _record_active_binding(client) -> None:
    """MCP'nin CANLI bagli oldugu sistemi .claude/.mcp_active_system'e yaz (fiili url/client ile).

    Asil yazici _conn.write_mcp_binding_state (acilista da kullanilir). Burada gercek
    bagli host/client gecilir → fiili hedef dogrulanir. Asla client yaratimini kirmaz."""
    try:
        from sapadt._conn import write_mcp_binding_state
        adt = getattr(client, "adt_client", None)
        write_mcp_binding_state(
            url=getattr(adt, "url", None),
            client=getattr(adt, "client", None),
        )
    except Exception:  # pragma: no cover - state yazimi asla baglanmayi kirmaz
        pass


def _err_from_exc(exc: Exception) -> dict:
    """Map SAPADTError subclasses (and generic Exception) to structured response."""
    from sap_adt_lib import (  # type: ignore
        SAPAuthenticationError,
        SAPConnectionError,
        SAPObjectNotFoundError,
        SAPObjectExistsError,
        SAPLockError,
        SAPActivationError,
        SAPValidationError,
        SAPADTError,
    )
    if isinstance(exc, SAPAuthenticationError):
        code = "auth_failed"
    elif isinstance(exc, SAPConnectionError):
        code = "connection_failed"
    elif isinstance(exc, SAPObjectNotFoundError):
        code = "not_found"
    elif isinstance(exc, SAPObjectExistsError):
        code = "already_exists"
    elif isinstance(exc, SAPLockError):
        code = "locked"
    elif isinstance(exc, SAPActivationError):
        code = "activation_failed"
    elif isinstance(exc, SAPValidationError):
        code = "validation_error"
    elif isinstance(exc, SAPADTError):
        code = "sap_error"
    else:
        code = "unexpected"
    out = {
        "ok": False,
        "error": code,
        "message": str(exc),
    }
    if isinstance(exc, SAPLockError) and getattr(exc, "lock_owner", None):
        out["lock_owner"] = exc.lock_owner
    if isinstance(exc, SAPActivationError) and getattr(exc, "errors", None):
        out["errors"] = exc.errors
    return out


@contextlib.contextmanager
def _capture_stdout():
    """SAPClient methods print to stdout. In MCP stdio mode stdout is the protocol channel.
    Capture it so client chatter does not break JSON-RPC framing."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        yield buf


# DDIC okuma-yolu TEK KAYNAKTAN gelir: `scripts/object_types.py` ->
# `DDIC_XML_ONLY_TYPES` / `DDIC_DDL_SOURCE_TYPES` / `ddic_read_mode()`.
# ⚠ Burada YEREL BIR KOPYA TUTMA. 2026-06-16'da bes DDIC tipi tek kume halinde
# XML-okuyucuya yonlendirilmisti; dogrusu ikiye ayriliyor:
#   * dataelement/domain/tabletype -> `/source/main` YOK (404) -> obje XML'i okunur.
#   * table/structure              -> GERCEK `/source/main` DDL ucu VAR (canli olculdu
#     2026-08-09; Z ve STANDART objelerde 200) -> duz DDL okunur.
# Ayni kural `scripts/sap_sync_pull.py`'de de gecerlidir; iki tuketici de ayni
# fonksiyonu cagirir (eskiden iki bagimsiz literal vardi ve ayrisiyordu).


def _ddic_read_mode(object_type: str) -> tuple[Optional[str], Optional[str]]:
    """`(mode, canonical)` — mode: 'ddl' | 'xml' | None. Tek kaynak: object_types.

    `(None, None)` DDIC-DEGIL demektir ve cagiran genel yola duser. Bu dal SESSIZ
    bir yanlis-cevap uretmez: genel yol `client.download_object` -> `get_source_url`
    zincirinden gecer, o da AYNI `object_types` modulunu kullanir. Yani modul
    gercekten yuklenemiyorsa `sap_client` import'u da coker ve `_get_client()`
    `ok:false` ile patlar; bilinmeyen tipte ise `get_source_url` ValueError atar ->
    `_err_from_exc` -> `ok:false`. Iki halde de sessiz `exists:false` YOKTUR.
    """
    try:
        from object_types import ddic_read_mode  # type: ignore
        mode, canonical = ddic_read_mode(object_type)
        return (mode, canonical)
    except Exception as exc:  # noqa: BLE001
        log.warning("object_types.ddic_read_mode yuklenemedi (%s) — DDIC ozel yolu atlandi", exc)
        return (None, None)


def _ddic_uri_seg(canonical_type: Optional[str]) -> Optional[str]:
    """Kanonik DDIC tipi -> ADT uc segmenti (ör. 'ddic/tables'); cozulemezse None.

    Yol tablosu object_types.OBJECT_TYPES'tadir — burada IKINCI bir kopya TUTULMAZ.
    """
    if not canonical_type:
        return None
    try:
        from object_types import OBJECT_TYPES  # type: ignore
        seg = OBJECT_TYPES[canonical_type]["url_path"]
    except Exception:
        return None
    return seg if isinstance(seg, str) and seg else None


# ⭐ TABLO <-> YAPI KARDES-UC ESLEMESI (2026-08-18 vakasi, kayit #8).
# Olculdu: `ZDEMO0_S_SCREEN_FIELD` / `ZDEMO0_S_SCREEN_BUTTON` (DDIC YAPI) CANLIDA VARDI,
# ama `adt_get(object_type="tabl")` `exists:false` dedi (`adt_search_objects` ikisini de
# buldu). Sebep: `tabl` `/ddic/tables/` ucuna gider, YAPILAR `/ddic/structures/` altinda
# yasar -> arac "YANLIS UCA SORDUM"u "OBJE YOK" diye raporluyordu.
# ⛔ NEDEN TEHLIKELI: "on kosul DDIC objesi yok" sonucu ya build'i durdurur ya da MUKERRER
# obje yaratma karari uretir (ADR 0005-D'ye kadar giden zincir).
# SINIF: `check_abaplint` SKIP=exit 0 ile AYNI aile -- "yok" ile "bakamadim" ayni cevaba
# dusuyor. Politika (bu evin kurali): YOKLUK IDDIASI KANIT ISTER.
# ⇒ Ilk uc 404 verirse KARDES uc de denenir; ikisi de 404 ise yokluk iddiasi GUCLENIR
# (`probed_endpoints` delili), kardes uc olculemezse yokluk BEYANI DARALTILIR
# (`sibling_probe: unavailable:...` + warning). Iki yon de kapsanir: bir GELISTIRICI
# `structure` tipiyle bir TABLOyu da sorabilir -- ayni kusur sinifinin diger yuzu.
_DDL_KARDES_SEG = {
    "ddic/tables": ("ddic/structures", "structure"),
    "ddic/structures": ("ddic/tables", "table"),
}

_DDL_TANIM = re.compile(r"^\s*define\s+(table|structure)\b", re.IGNORECASE | re.MULTILINE)


# Bug gate LOW (v0.5.1): tür aranmadan önce DDL yorumları atılır. Tek geçişli alternasyon: tırnaklı dizgi (olduğu gibi
# kalır — `'etiket /* x'` yorum başlatmaz) · `/* … */` blok yorum · `//` satır yorumu. Ölçülen kusur:
# `/*\ndefine structure old\n*/\ndefine table` → 'structure' dönüyordu.
# Düzeltme turu gate LOW-2: kapanmamış `/*` metin sonuna kadar yorum sayılır (`\Z`) — aksi hâlde her `/*` konumu metnin
# sonuna kadar taranıp geri çekiliyordu: 10.000 kapanmamış `/*` (30 KB) ≈ 1,4 sn, 100 KB ≈ 43 sn (ölçüldü).
_DDL_YORUM_YA_DA_DIZGI = re.compile(r"'[^'\n]*'|/\*.*?(?:\*/|\Z)|//[^\n]*", re.S)


def _ddl_yorumsuz(kaynak: str) -> str:
    return _DDL_YORUM_YA_DA_DIZGI.sub(lambda m: m.group(0) if m.group(0).startswith("'") else " ", kaynak)


def _ddl_kaynak_turu(kaynak) -> Optional[str]:
    """DDIC DDL kaynağının türü: ilk `define table|structure` satırı → 'table' | 'structure'; bulunamazsa None.

    Satır başı zorunlu (`^\\s*define`) ⇒ `// define …` yorum satırı ve `@EndUserText.label : 'define …'` ek açıklaması
    eşleşmez. Z53: türü uç değil KAYNAK söyler (structures ucu tablo için de 200 döner — canlı bulgu, v0.5.1 Z53)."""
    if not isinstance(kaynak, str):
        return None
    m = _DDL_TANIM.search(_ddl_yorumsuz(kaynak))
    return m.group(1).lower() if m else None


# "BULUNAMADI != YOK" (ölçüldü 2026-07-31, dört ayrı vaka aynı gün).
# adt_get, ulaşılamayan SAP'te de `ok:true, exists:false` döndürüyordu; obje CANLIDA
# VARDI ve client_log'da NameResolutionError yazıyordu. Bir ajan buna dayanıp
# "obje yok, yaratayım" derse ADR 0005-A sınırına dayanır. Bu yüzden ağ/erişim
# kaynaklı boş sonuç artık `exists:false` DEĞİL, açık HATA döner.
# _UNREACHABLE_MARKERS + _bos_sonuc_sinifi 2026-09-03'te BAĞIMLILIKSIZ modüle
# TAŞINDI (SDK'sız CLI araçları da kullanabilsin). Buradan re-export edilir:
# mevcut `from ...tools.atom import _bos_sonuc_sinifi` çağrıları AYNEN çalışır.
from sapadt._bos_sonuc import (  # noqa: E402
    _UNREACHABLE_MARKERS,
    _bos_sonuc_sinifi,
)

# FM (`func`/`function`) OKUMA KANALI — Q261 (2026-09-13).
# Eskiden burada FM için bir "exists:false burada 'yok' demek olmayabilir" ipucu
# sözlüğü vardı. Q221'den (2026-09-04) beri `func` akışı generic URL kapısında
# ValueError ile `_err_from_exc`'e gidiyordu, bu fonksiyona HİÇ düşmüyordu ⇒ ipucu
# ERİŞİLEMEZDİ (canlı ölçüldü: adt_get(func) → error:"unexpected", warning YOK).
# Artık `adt_get` FM'i `_read_function_module` ile grubu çözerek okur; `exists:false`
# yalnız başarılı bir aramanın KANITIYLA (`probe`) döner. İpucu kalsaydı kanıtlı bir
# yokluğa "bu uçtan okunamaz" diye YANLIŞ uyarı basacaktı — bu yüzden kaldırıldı.


def _miss_or_unreachable(name: str, object_type: str, log_text: str) -> dict:
    """Boş sonucu SINIFLANDIR: gerçekten 'obje yok' mu, yoksa 'ulaşamadım' mı?

    exists:false yalnızca SAP'ye ULAŞILDIĞI ve objenin gerçekten bulunmadığı
    durumda döner. Ağ/erişim izi varsa ok:false + unreachable döner -- çağıran
    bunu "yok" diye okuyamasın. (Sınıflandırma: `_bos_sonuc_sinifi`.)
    """
    _sinif = _bos_sonuc_sinifi(log_text)
    if _sinif == "ulasilamadi":
        return {
            "ok": False,
            "error": "unreachable",
            "name": name.upper(),
            "type": object_type,
            "message": (
                "SAP'ye ULAŞILAMADI — bu sonuç 'obje yok' DEĞİLDİR. Bağlantı/DNS/VPN "
                "kontrol et ve tekrar ölç. ⛔ Bu cevaba dayanıp obje YARATMA (ADR 0005-A)."
            ),
            "client_log": log_text,
        }
    # ⚠ YOKLUK İDDİASI KANIT İSTER (2026-08-01 bug-avı, W2-MCPT-01).
    # `_UNREACHABLE_MARKERS` yalnız AĞ katmanını tanır. Sunucu/yetki hataları (HTTP 500,
    # 502, 403 logon) o listeye girmez ve eskiden sessizce `exists:false`e düşerdi —
    # yani "sunucu patladı" ile "obje yok" AYNI cevabı veriyordu. Ölçüldü: 500/403/
    # timeout/bağlantı-kopması dördü de `ok:true, exists:false`.
    # Politika: log'da bir HATA izi varsa ve o iz KESİN bir bulunamadı imzası DEĞİLSE,
    # yokluk BEYAN EDİLMEZ → `ok:false` + belirsiz. Temiz-boş yanıt (hata izi yok) eskisi
    # gibi `exists:false` kalır; 404 imzası da öyle (kontrol grubu bunu doğrular).
    if _sinif == "belirsiz":
        return {
            "ok": False,
            "error": "belirsiz",
            "name": name.upper(),
            "type": object_type,
            "message": (
                "Obje okunamadı ve sebep BULUNAMADI-DEĞİL bir hata (ör. HTTP 500/403). "
                "Bu sonuç 'obje yok' DEĞİLDİR — sunucu/yetki hatası da olabilir. "
                "⛔ Bu cevaba dayanıp obje YARATMA ya da SİLME (ADR 0005-A). "
                "Hatayı gider, tekrar ölç."
            ),
            "client_log": log_text,
        }
    return {"ok": True, "name": name.upper(), "type": object_type, "exists": False,
            "client_log": log_text}


# =============================================================================
# adt_get
# =============================================================================

def _read_source_object(name: str, uri_seg: str, type_label: str) -> dict:
    """Kaynak-endpoint'li obje oku (`.../source/main`) — `download_object`'in desteklemediği
    tipler için (ör. BDEF). Raw GET (Accept text/plain), READ-ONLY. (private helper — tool DEĞİL)
    """
    client = _get_client()
    log_buf = io.StringIO()
    try:
        adt = getattr(client, "adt_client", None) or client
        from urllib.parse import quote
        url = (adt.url + "/sap/bc/adt/" + uri_seg + "/"
               + quote(name.lower(), safe="") + "/source/main")
        with _capture_stdout() as out:
            r = adt.session.get(url, headers={"Accept": "text/plain"}, verify=adt.session.verify, timeout=60)
        log_buf.write(out.getvalue())
        if r.status_code == 404:
            # ⚠ YOKLUK KANITI ACIK YAZILIR. Ham `requests` GET'i stdout'a hicbir sey
            # basmaz -> log BOS kalir -> `_bos_sonuc_sinifi("")` "temiz-bos yanit"
            # dalindan "yok" dondururdu; yani dogru sonuc KAZAYLA cikardi. Durum kodunu
            # log'a yazinca siniflandirma 404 KANITINA dayanir (kanit-zinciri gorunur).
            log_buf.write("[404] GET %s\n" % url)
            return _miss_or_unreachable(name, type_label, log_buf.getvalue().strip())
        if r.status_code != 200:
            return {"ok": False, "name": name.upper(), "type": type_label,
                    "error": "http_%d" % r.status_code, "message": (r.text or "")[:500],
                    "client_log": log_buf.getvalue().strip()}
        out_ok = {"ok": True, "name": name.upper(), "type": type_label, "exists": True,
                  "source": r.text, "client_log": log_buf.getvalue().strip()}
        if not (r.text or "").strip():
            # 200 ama GOVDE BOS: obje VAR fakat kaynagi yok (create-POST'un biraktigi
            # shell/placeholder — playbook adt-tables-structures §28.1). Sessizce bos
            # source dondurmek "obje bos" yanilgisi uretir ve pull yolunda repo dosyasini
            # bosaltmaya calisir (write_repo_from_live FIX-C shrink korumasi yakalar).
            out_ok["source_empty"] = True
            out_ok["warning"] = (
                "Uc 200 dondu ama SOURCE BOS. Obje VAR; kaynagi bos (shell/placeholder "
                "olabilir — create yapildi ama DDL PUT edilmedi ya da aktive edilmedi). "
                "Bu sonucu 'obje bos/silinebilir' diye OKUMA; once SE11/adt ile teyit et."
            )
        return out_ok
    except Exception as exc:
        return _err_from_exc(exc)


def _read_class_include(name: str, object_type: str) -> dict:
    """Sınıf alt-include'unu oku (READ-ONLY). `name` = ANA SINIF. (tool DEĞİL)

    Uç: `GET /sap/bc/adt/oo/classes/<cls>/includes/<segment>` (Accept text/plain) — segment
    adları `object_types.CLASS_INCLUDE_TYPES`'ta canlı GET ile ölçülmüş olarak beyanlıdır.
    404 → include KANITLI yok (`include_absent_proven: true`); başka kod → `http_<kod>` (yok DEĞİL).
    Log'a host YAZILMAZ (yalnız yol).
    """
    from object_types import get_class_include_url, normalize_class_include  # type: ignore
    try:
        kind = normalize_class_include(object_type)
        path = get_class_include_url(name, kind)
    except ValueError as exc:
        return {"ok": False, "error": "unsupported_type", "name": name.upper(), "type": object_type,
                "message": str(exc)}
    client = _get_client()
    try:
        adt = getattr(client, "adt_client", None) or client
        with _capture_stdout():
            r = adt.session.get(adt.url + path, headers={"Accept": "text/plain"},
                                verify=adt.session.verify, timeout=60)
        durum = int(getattr(r, "status_code", 0) or 0)
        if durum == 404:
            sonuc = _miss_or_unreachable(name, object_type, "[404] GET " + path)
            if sonuc.get("ok") is True and sonuc.get("exists") is False:
                sonuc["include"] = kind
                sonuc["include_absent_proven"] = True
            return sonuc
        if durum != 200:
            return {"ok": False, "name": name.upper(), "type": object_type, "include": kind,
                    "error": "http_%d" % durum, "message": (getattr(r, "text", "") or "")[:500]}
        return {"ok": True, "name": name.upper(), "type": object_type, "include": kind, "exists": True,
                "source": getattr(r, "text", "") or "", "resolved_uri": path}
    except Exception as exc:
        return _err_from_exc(exc)


def _read_function_module(name: str, object_type: str, include_source: bool) -> dict:
    """FM oku (Q261) — grubu `SAPClient.read_function_module` çözer. READ-ONLY. (tool DEĞİL)

    Üç ayrık sonuç (hiçbiri diğerine düşmez):
      · bulundu      → `exists:true` + `resolved_uri` + `function_group` (+ source/metadata)
      · kanıtlı yok  → `exists:false` + `probe` (hangi arama koşuldu)
      · bakamadım    → `ok:false` (arama/okuma istisnası) — 'yok' DEĞİLDİR
    """
    client = _get_client()
    log_buf = io.StringIO()
    try:
        with _capture_stdout() as out:
            try:
                r = client.read_function_module(name, include_source=include_source)
            finally:
                log_buf.write(out.getvalue())
    except Exception as exc:
        hata = _err_from_exc(exc)
        hata.setdefault("client_log", log_buf.getvalue().strip())
        return hata
    ortak = {"ok": True, "name": name.upper(), "type": object_type,
             "probe": r.get("probe"), "client_log": log_buf.getvalue().strip()}
    if r.get("status") != "found":
        return {**ortak, "exists": False}
    return {**ortak, "exists": True, "resolved_uri": r.get("uri"),
            "function_group": r.get("function_group"),
            "source": r.get("source"), "metadata": r.get("metadata")}


@profil_tool()
def adt_get(name: str, object_type: str = "class", include_source: bool = True) -> dict:
    """Get an SAP ADT object: existence, metadata, and (optionally) source (enqu: yalnız varlık, include_source=false).

    Kilit objesi (`enqu`, aXet 2026-09-14): generic ADT URL'i yok; yalnız salt-GET varlık sondası
    (`/ddic/lockobjects/sources/<ad>`: 200 → exists:true · 404 → exists:false · diğer → ok:false ÖLÇÜLEMEDİ).
    Kaynak metni olmadığı için `include_source=true` → `unsupported_type` (ağa gidilmez). Kilit (enqueue)
    açan/silen çağrı YAPMAZ.

    PULL-BEFORE-EDIT: kaynak başarıyla okunduğunda (`include_source=true`, `exists:true`, metin)
    canlı kaynağın özeti `<proje>/.axet-code/sap-pull-state.json`'a yazılır; yanıttaki
    `pull_state` alanı (`kaydedildi` | `yazilamadi: …`) sonucu söyler. `adt_push_source` bu kayıt
    olmadan yazmaz. Okuma ayrıntıları: `_adt_get_oku`.
    """
    if include_source and (object_type or "").lower().strip() in ("msag", "messageclass"):
        return adt_msgclass_read(name)   # aXet: mesaj listesi pull kaydı (adt_msgclass_write için)
    r = _adt_get_oku(name, object_type, include_source)
    if (include_source and isinstance(r, dict) and r.get("ok") is True and r.get("exists") is False
            and r.get("include_absent_proven") is True):
        # aXet: sınıf alt-include'u 404 ile KANITLI yok → "çekildiği anda yoktu" kaydı. İlk yaratım
        # push'u (POST-if-absent) ancak yazma anında da hâlâ yoksa geçer (IMPLEMENTATION.md §14.4).
        h = _pull_state.kaydet_yok(name, object_type)
        r["pull_state"] = "kaydedildi (include yok)" if h is None else f"yazilamadi: {h}"
        return r
    if (include_source and isinstance(r, dict) and r.get("ok") is True and r.get("exists") is True
            and isinstance(r.get("source"), str)):
        tipler = [object_type]
        if isinstance(r.get("resolved_type"), str) and r["resolved_type"] != object_type:
            tipler.append(r["resolved_type"])   # kardeş uçta bulunan tablo/yapı: iki tiple de push edilebilir
        hatalar = [h for h in (_pull_state.kaydet(name, t, r["source"]) for t in tipler) if h]
        r["pull_state"] = "kaydedildi" if not hatalar else "yazilamadi: " + "; ".join(hatalar)
    return r


def _adt_get_oku(name: str, object_type: str = "class", include_source: bool = True) -> dict:
    """adt_get'in okuma gövdesi — pull-state YAZMAZ (iç çağrılar ve push tazelik kontrolü için).

    Args:
        name: Object name (case-insensitive, normalised to upper on SAP side).
        object_type: ADT object type. Common: 'class', 'doma', 'dtel', 'tabl', 'view',
                     'ddls' (CDS), 'fugr', 'func', 'enqu', 'msag', 'prog'.
        include_source: If True, also fetches source text. Set False for fast metadata-only.

    Returns:
        {ok, name, type, exists, source?, metadata?, client_log}
        On miss:  {ok: true, exists: false, name, type}
        On error: {ok: false, error, message}

    ⭐ TABLO/YAPI KARDES-UC (2026-08-18 vakasi): `tabl` `/ddic/tables/`e, `structure`
    `/ddic/structures/`e sorar. Istenen uc 404 verirse KARDES uc de denenir:
      • kardeste BULUNURSA → `exists: true` + `resolved_type` / `resolved_endpoint` +
        `sibling_probe: "checked_found"` + tip duzeltmesi `warning`'i,
      • ikisi de 404 → `sibling_probe: "checked_absent"` + `probed_endpoints` (yokluk delili),
      • kardes uc OLCULEMEZSE → `sibling_probe: "unavailable:<sebep>"` + warning
        (yokluk beyani o uc ile SINIRLIDIR; "bakamadim" != "yok").
    ⛔ Bu fallback DDIC yapisi/tablosu icindir. DDIC objesinin varligini kritik bir kararda
    (obje YARATMA/SILME) `adt_get` ile TEK BASINA olcme — `adt_search_objects` ile capraz
    kontrol et (ADR 0005-A).
    """
    # Sınıf ALT-INCLUDE'u (ccimp/ccau/ccdef/ccmac): ad = ANA SINIF; uç `/oo/classes/<c>/includes/<seg>`
    # kaynak ucunun KENDİSİDİR (`/source/main` EKLENMEZ — object_types.get_class_include_url).
    from object_types import is_class_include as _sinif_include_mi  # type: ignore
    if _sinif_include_mi(object_type):
        return _read_class_include(name, object_type)
    # MSAG (mesaj sınıfı): adt_get msag tipini DESTEKLEMEZ → özel messageclass endpoint'i.
    if (object_type or "").lower().strip() in ("msag", "messageclass"):
        return _msgclass_disari(_msgclass_oku(name))   # iç okuma: pull kaydı YAZMAZ
    # ENQU (kilit objesi): generic URL YOK (object_types.OBJECT_TYPES'ta anahtar yok) → yalnız METADATA varlık
    # sondası (aXet 2026-09-14, toplu yazıcı için; kullanıcı onayı). Salt GET — kilit açmaz/silmez (ADR 0005-C).
    if (object_type or "").lower().strip() in _KILIT_OBJE_TIPLERI:
        return _enqu_varlik_oku(name, object_type, include_source)
    # BDEF (behavior definition): download_object DESTEKLEMEZ → source/main endpoint'i (raw GET).
    if (object_type or "").lower().strip() in ("bdef", "behaviordefinition"):
        return _read_source_object(name, "bo/behaviordefinitions", "bdef")
    # FM (func/function): generic URL YOK (grup adı FM adından türetilemez, Q221) →
    # grubu arama indeksinden çözen kanal (Q261). Generic kapı yerinde KALIR.
    from object_types import is_function_module_type  # type: ignore
    if is_function_module_type(object_type):
        return _read_function_module(name, object_type, include_source)

    client = _get_client()
    log_buf = io.StringIO()

    # DDIC tipleri IKI YOLA ayrilir (bkz. `_ddic_read_mode` notu):
    #   'ddl' (table/structure) -> GERCEK `/source/main` ucu var -> DUZ DDL oku.
    #   'xml' (dtel/doma/ttyp)  -> `/source/main` YOK -> obje XML'i oku.
    ddic_mode, ddic_canonical = _ddic_read_mode(object_type)
    if ddic_mode == "ddl":
        # Tablo/struct'un KAYNAGI DDL'dir: repo dosyalari da DDL tasir (bkz.
        # source_drift._TYPE_TO_EXTENSIONS) ve create yolu DDL'i `PUT /source/main`
        # ile yazar. XML zarfi dondurmek okuyucuyu (ve pull yolunu) DDL yerine
        # `<blue:blueSource>` govdesiyle besliyordu.
        seg = _ddic_uri_seg(ddic_canonical)
        if seg is None:
            # Sozlesme ihlali: mode='ddl' geldi ama uc segmenti cozulemedi. SESSIZCE
            # XML yoluna DUSMEK yasak — cagiran DDL bekliyor, XML zarfi alirdi ve bunu
            # fark etmezdi (§127 "dogrulama kosamadi = dogrulandi" sinifi). ACIK HATA.
            return {
                "ok": False,
                "error": "ddic_uri_unresolved",
                "name": name.upper(),
                "type": object_type,
                "message": (
                    f"DDIC tipi '{ddic_canonical}' icin ADT uc segmenti (url_path) "
                    "cozulemedi — kaynak OKUNMADI. Bu sonuc 'obje yok' ya da 'kaynak bos' "
                    "DEGILDIR. object_types.OBJECT_TYPES tablosunu kontrol et."
                ),
            }
        r = _read_source_object(name, seg, object_type)
        # ⛔ Z53 (canlı bulgu, v0.5.1): SAP `/ddic/structures/<TABLO>/source/main` isteğine şeffaf tablo için de 200 +
        # `define table …` döndürür ⇒ 404'e dayanan kardeş-uç yolu hiç koşmaz, tablo "structure" diye raporlanıyordu.
        # Tür, dönen kaynağın İLK tanım anahtar kelimesinden okunur (`define table` / `define structure`); uçla
        # çelişirse `resolved_type` + tip düzeltmesi uyarısı eklenir. Kaynak boş/tanımsızsa tür iddiası yapılmaz.
        if r.get("ok") is True and r.get("exists") is True and seg in _DDL_KARDES_SEG:
            gercek_tur = _ddl_kaynak_turu(r.get("source"))
            beklenen_tur = _DDL_KARDES_SEG[_DDL_KARDES_SEG[seg][0]][1]   # seg'in kendi türü
            if gercek_tur is not None and gercek_tur != beklenen_tur:
                r["requested_endpoint"] = seg
                r["resolved_endpoint"] = seg
                r["canonical_endpoint"] = _DDL_KARDES_SEG[seg][0]
                r["resolved_type"] = gercek_tur
                r["type_probe"] = "source_keyword"
                r["warning"] = (
                    "TIP DUZELTMESI: '%s' ucu 200 dondu ama kaynak 'define %s' ile tanimli — obje bir %s. "
                    "Sonraki cagrilarda object_type='%s' kullan."
                    % (seg, gercek_tur, "TABLO" if gercek_tur == "table" else "YAPI", gercek_tur)
                )
            return r
        # Kardes-uc fallback: tablo ucunda 404 -> YAPI ucunu da dene (ve tersi).
        # Bkz. `_DDL_KARDES_SEG` notu (kayit #8, 2026-08-18 ZDEMO0_S_SCREEN_* vakasi).
        if r.get("ok") is True and r.get("exists") is False and seg in _DDL_KARDES_SEG:
            kardes_seg, kardes_tip = _DDL_KARDES_SEG[seg]
            r2 = _read_source_object(name, kardes_seg, object_type)
            if r2.get("ok") is True and r2.get("exists") is True:
                # Obje VAR — yalnizca YANLIS UCA sorulmustu. `type` cagiranin verdigi
                # deger olarak KALIR (sozlesme sabit); dogru tip AYRI alanda bildirilir.
                r2["type"] = object_type
                r2["requested_endpoint"] = seg
                r2["resolved_endpoint"] = kardes_seg
                r2["resolved_type"] = kardes_tip
                r2["sibling_probe"] = "checked_found"
                r2["warning"] = (
                    "TIP DUZELTMESI: '%s' tipi '%s' ucuna sorar, ama bu obje '%s' "
                    "ucunda bulundu (kanonik tip: '%s'). Kaynak DOGRU objeden okundu. "
                    "Sonraki cagrilarda object_type='%s' kullan."
                    % (object_type, seg, kardes_seg, kardes_tip, kardes_tip)
                )
                return r2
            if r2.get("ok") is True and r2.get("exists") is False:
                # Iki ucta da 404 -> yokluk iddiasi GUCLENDI (delil listesi acik yazilir).
                r["sibling_probe"] = "checked_absent"
                r["probed_endpoints"] = [seg, kardes_seg]
            else:
                # Kardes uc OLCULEMEDI -> yokluk beyani DARALTILIR ("bakamadim" != "yok").
                r["sibling_probe"] = "unavailable:%s" % (r2.get("error") or "bilinmeyen")
                r["probed_endpoints"] = [seg]
                r["warning"] = (
                    "exists:false YALNIZ '%s' ucu icin KANITLIDIR. Kardes uc ('%s') "
                    "OLCULEMEDI (%s) — obje bir YAPI/TABLO olarak orada duruyor olabilir. "
                    "⛔ Bu cevaba dayanip obje YARATMA; adt_search_objects ile capraz kontrol et."
                    % (seg, kardes_seg, r2.get("error") or "bilinmeyen")
                )
        return r

    ddic_xml_type = ddic_canonical if ddic_mode == "xml" else None
    if ddic_xml_type is not None:
        try:
            with _capture_stdout() as out:
                xml = client.get_ddic_object(ddic_xml_type, name)
            log_buf.write(out.getvalue())
            if xml is None:
                # ⚠ "BULUNAMADI ≠ YOK" — DDIC dalı (2026-08-01 bug-avı, W2-MCPT-01).
                # Eskiden `exists: xml is not None` yazıyordu ve `None` gelen HER durum
                # "obje yok" sayılıyordu. Ama alt katman (`sap_client.get_ddic_object`)
                # **her istisnayı yutup None döndürür** → aşağıdaki `except` dalı bu tipler
                # için HİÇ ateşlenmez. Ölçüldü (stub'lu kontrol grubuyla):
                #   gerçek 404      → exists:false   ✔ doğru
                #   HTTP 500 / 403  → exists:false   ✘ ok:true ile, 404'ten AYIRT EDİLEMEZ
                #   ReadTimeout     → exists:false   ✘
                #   bağlantı kopuk  → exists:false   ✘
                # Sonuç: ajan "yok" sanıp yeniden YARATIR (ADR 0005-A sınırı) ya da mevcut
                # objeyi ezer. Aynı sınıf `class` yolunda 2026-07-31'de kapatılmıştı;
                # DDIC dalı geride kalmıştı.
                # POLİTİKA: yokluk iddiası KANIT ister. `exists:false` yalnız log'da KESİN
                # bir bulunamadı imzası varsa döner; aksi halde yokluk BEYAN EDİLMEZ.
                return _miss_or_unreachable(name, object_type, log_buf.getvalue().strip())
            return {
                "ok": True,
                "name": name,
                "type": object_type,
                "exists": True,
                "source": xml,
                "metadata": xml,
                "client_log": log_buf.getvalue().strip(),
            }
        except Exception as exc:
            from sap_adt_lib import SAPObjectNotFoundError, SAPADTError  # type: ignore
            if isinstance(exc, SAPObjectNotFoundError) or (
                isinstance(exc, SAPADTError) and getattr(exc, "status_code", None) == 404
            ):
                return _miss_or_unreachable(name, object_type, log_buf.getvalue().strip())
            return _err_from_exc(exc)

    try:
        with _capture_stdout() as out:
            source = None
            metadata = None
            if include_source:
                source = client.download_object(name, object_type=object_type, save_local=False)
            metadata = client.get_object_metadata(name, object_type=object_type)
        log_buf.write(out.getvalue())
        # Alt katman istisna ATMADAN None dönebiliyor (ör. ağ hatası yutulmuşsa). O hâlde
        # "obje yok" değil "ulaşamadım" olabilir -- sınıflandırmayı _miss_or_unreachable yapar.
        if source is None and metadata is None:
            return _miss_or_unreachable(name, object_type, log_buf.getvalue().strip())
        return {
            "ok": True,
            "name": name,
            "type": object_type,
            "exists": True,
            "source": source,
            "metadata": metadata,
            "client_log": log_buf.getvalue().strip(),
        }
    except Exception as exc:
        from sap_adt_lib import SAPObjectNotFoundError  # type: ignore
        if isinstance(exc, SAPObjectNotFoundError):
            return _miss_or_unreachable(name, object_type, log_buf.getvalue().strip())
        return _err_from_exc(exc)


# =============================================================================
# adt_msgclass_read  (mesaj sınıfı / MSAG okuma — adt_get msag DESTEKLEMEZ)
# =============================================================================
_MC_NS_MC = "http://www.sap.com/adt/MessageClass"
_MC_NS_AC = "http://www.sap.com/adt/core"


def _parse_msgclass_xml(xml_text: str) -> dict:
    """ADT `mc:messageClass` XML → {name, master_language, description, messages:[...]}.

    Kanıt (canlı MSAG doğrulaması, 2026-07-12): her mesaj `<mc:messages mc:msgno mc:msgtext
    mc:selfexplainatory mc:documented>` attribute'ları taşır; metin HTML-escape'li (ET çözer).
    """
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml_text)

    def _ac(a: str):
        return root.get("{%s}%s" % (_MC_NS_AC, a))

    messages = []
    for el in root.findall("{%s}messages" % _MC_NS_MC):
        def _g(a: str, _el=el):
            return _el.get("{%s}%s" % (_MC_NS_MC, a))
        # `mc:msgtext` özniteliği yoksa '' (None DEĞİL): kaynak çekirdek populate_message_class.py:462
        # `m.get(_NS_MC + 'msgtext', '')`. None kalırsa yazma aracı gövdeye `mc:msgtext="None"` yazardı (Z113 L1).
        metin = _g("msgtext")
        messages.append({
            "no": _g("msgno"),
            "text": "" if metin is None else metin,
            "selfexplanatory": (_g("selfexplainatory") == "true"),
            "documented": (_g("documented") == "true"),
        })
    paket = root.find("{%s}packageRef" % _MC_NS_AC)
    return {
        "name": _ac("name"),
        "master_language": _ac("masterLanguage"),
        "description": _ac("description"),
        "messages": messages,
        # aXet 2026-09-13 — yalnız İÇ kullanım (`adt_msgclass_write` tam-gövde PUT'u canlı değerleri korur);
        # `adt_msgclass_read` yanıtına `responsible` KONMAZ (SAP kullanıcı adı).
        "_responsible": _ac("responsible"),
        "_package": paket.get("{%s}name" % _MC_NS_AC) if paket is not None else None,
    }


# ── aXet 2026-09-13: mesaj listesi pull-before-edit özeti ────────────────────────────────────────
def msgclass_ozet_metni(messages) -> str:
    """Mesaj listesinin KANONİK metni (numaraya göre sıralı, tek satır JSON). `pull_state.kaydet/ozet` bunu
    `sha256(normalize_source(...))` ile özetler; tek satır olduğu için metin içindeki boşluklar da korunur."""
    satirlar = sorted(
        ([str(m.get("no") or ""), str(m.get("text") or ""), bool(m.get("selfexplanatory")),
          bool(m.get("documented"))] for m in (messages or []) if isinstance(m, dict)),
        key=lambda s: s[0])
    return json.dumps(satirlar, ensure_ascii=False, separators=(",", ":"))


def _msgclass_oku(name: str) -> dict:
    """Mesaj sınıfı okuma gövdesi — pull-state YAZMAZ (iç çağrılar: kabuk sondası, yazma öncesi/sonrası
    canlı okuma). İç alanlar (`_responsible`, `_package`) dönüşte durur; public araç bunları atar."""
    client = _get_client()
    log_buf = io.StringIO()
    try:
        adt = getattr(client, "adt_client", None) or client
        from urllib.parse import quote
        url = adt.url + "/sap/bc/adt/messageclass/" + quote(name.lower(), safe="")
        with _capture_stdout() as out:
            r = adt.session.get(
                url,
                headers={"Accept": "application/vnd.sap.adt.mc.messageclass+xml"},
                verify=adt.session.verify, timeout=60,
            )
        log_buf.write(out.getvalue())
        if r.status_code == 404:
            return {"ok": True, "name": name.upper(), "exists": False,
                    "client_log": log_buf.getvalue().strip()}
        if r.status_code != 200:
            return {"ok": False, "name": name.upper(), "error": "http_%d" % r.status_code,
                    "message": (r.text or "")[:500], "client_log": log_buf.getvalue().strip()}
        parsed = _parse_msgclass_xml(r.text)
        return {
            "ok": True,
            "name": parsed["name"] or name.upper(),
            "exists": True,
            "master_language": parsed["master_language"],
            "description": parsed["description"],
            "count": len(parsed["messages"]),
            "messages": parsed["messages"],
            "_responsible": parsed["_responsible"],
            "_package": parsed["_package"],
            "client_log": log_buf.getvalue().strip(),
        }
    except Exception as exc:
        return _err_from_exc(exc)


def _msgclass_disari(r: dict) -> dict:
    """İç alanları at (public yanıt). `package` zararsız ve yazma aracı için yol gösterici → korunur."""
    if not isinstance(r, dict):
        return r
    out = {k: v for k, v in r.items() if not k.startswith("_")}
    if r.get("exists") is True:
        out["package"] = r.get("_package")
    return out


@profil_tool()
def adt_msgclass_read(name: str) -> dict:
    """Read a message class (MSAG) and ALL its messages via ADT. READ-ONLY.

    Neden ayrı tool: `adt_get` msag tipini DESTEKLEMEZ ve `adt_table_read` T100'ü
    filtreleyemez (WHERE param yok; T100 preview 400 verir). Bu tool resmî ADT kaynağını
    kullanır: ham GET `/sap/bc/adt/messageclass/{name}`
    (Accept `application/vnd.sap.adt.mc.messageclass+xml`) → XML parse.

    Referans: marcellourbani/vscode_abap_remote_fs (Message Class Editor). CANLI-DOĞRULANDI
    (2026-07-12): `/messages` alt-path'i 404; kök `/messageclass/{name}` +
    `.mc.messageclass+xml` Accept çalışır (reference'ın `.v2+xml` header'ı 406 verir —
    sunucu kabul-tipini kendi bildirir).

    Args:
        name: Mesaj sınıfı adı (ör. 'ZDEMO1').

    Returns:
        {ok, name, exists, master_language?, description?, package?, count?, messages?, pull_state?, client_log}
        messages: [{no, text, selfexplanatory, documented}, ...] (text: '&' çözülmüş, master dil).
        On miss: {ok: true, exists: false, name}

    PULL-BEFORE-EDIT (aXet 2026-09-13): sınıf okununca mesaj listesinin kanonik özeti
    `.axet-code/sap-pull-state.json`'a `msag:<AD>` anahtarıyla yazılır (`pull_state`). `adt_msgclass_write`
    bu kayıt olmadan yazmaz ve yazma anında canlı listeyi bu özetle kıyaslar.
    """
    r = _msgclass_oku(name)
    out = _msgclass_disari(r)
    if isinstance(r, dict) and r.get("ok") is True and r.get("exists") is True:
        h = _pull_state.kaydet(name, "msag", msgclass_ozet_metni(r.get("messages")))
        out["pull_state"] = "kaydedildi" if h is None else f"yazilamadi: {h}"
    return out


# =============================================================================
# adt_post_shell
# =============================================================================

# ⛔ CREATE'IN "BASARISIZ" DONUSU DE KANIT DEGILDIR (kayitlar #20 + #49 — ayni kokun iki yuzu).
#
# Olculmus iki vaka:
#   2026-08-19 `ZCL_DEMO0_GET_IDOCDATA`: MCP **400** raporladi, obje FIILEN YARATILMISTI
#     (3. ve 4. denemede sunucu `ExceptionResourceAlreadyExists` dedi; TADIR'dan dogrulandi).
#     ⚠ AYNI turda GERCEK bir 400 da vardi: sinif kisa metni siniri
#     `adtcore:descriptionTextLimit="60"`, verilen aciklama 80 karakterdi. Yani iki AYRI 400:
#     (a) gercek (metin > sinir)  (b) sahte (create basarili ama 400 raporlandi).
#   2026-08-21 `A-13` (uc sinif): donus `[ERROR] [500] Failed to create CLAS/OC` -> `ok:false`,
#     ama kabuk UCUNDE DE GERCEKTEN YARATILDI (`adt_get exists=true` · TADIR DEVCLASS dolu,
#     DELFLAG bos).
#
# ⛔ NEDEN CIDDI — RETRY TUZAGI: `ok:false` gorunce dogal refleks TEKRAR DENEMEKTIR. Bir
# gateway bunu bilmeden yapti -> 400 ("zaten var") aldi; zarar OLMADI ama bu yalniz SAP'nin
# ikinci yaratmayi reddetmesi sayesinde. Idempotent OLMAYAN bir obje tipinde ayni refleks
# MUKERRER YARATMA uretirdi. ⇒ "exit 0 != kanit"in TERS YUZU: `ok:false` DA kanit degil.
#
# ⚠ MEKANIK SEBEP (olculdu, `sap_client.create_object`): o katman HER istisnayi YUTAR,
# sebebi yalnizca stdout'a `[ERROR] ...` diye basar ve `None` doner. Yani buradaki
# `except Exception` dali create hatalarinda HIC atesLENMEZ; tek sinyal `client_log`'tur.
# Bu, `_bos_sonuc_sinifi`nin cozdugu sinifin aynisidir -> sinyal LOG'DAN cikarilir.
_CREATE_HATA_IMZALARI = (
    # (imza (kucuk harf), donus kodu, aciklama)
    ("exceptionresourcealreadyexists", "already_exists",
     "SAP 'kaynak ZATEN VAR' dedi — obje mevcut. ⛔ TEKRAR YARATMAYA CALISMA."),
    ("resourcealreadyexists", "already_exists",
     "SAP 'kaynak ZATEN VAR' dedi — obje mevcut. ⛔ TEKRAR YARATMAYA CALISMA."),
    # aXet 2026-09-13: tipe özel kabuk reçeteleri 'zaten var'ı 400/405 + `AlreadyExists` gövdesiyle
    # alır (adt-fugr-functions.md:46,72 · create_rap_service.py:334,407 · adt-tables-structures.md:368).
    ("alreadyexists", "already_exists",
     "SAP 'zaten var' (AlreadyExists) dedi — obje mevcut. ⛔ TEKRAR YARATMAYA CALISMA."),
    ("descriptiontextlimit", "description_too_long",
     "GERCEK 400: kisa metin (description) SAP'nin tip-basina sinirini ASIYOR. "
     "Ham govdedeki `adtcore:descriptionTextLimit` degerine bak (sinif icin olculen: 60) "
     "ve aciklamayi KISALT. Bu bir sahte-400 DEGILDIR."),
)


def _create_hata_sinifi(log_text: str) -> tuple[str, str]:
    """create `None` dondugunde sebebi LOG'dan sinifla -> (kod, aciklama).

    Log'da tanidik bir imza yoksa `("create_failed", "")` doner — UYDURMA YOK.
    """
    dusuk = (log_text or "").lower()
    for imza, kod, aciklama in _CREATE_HATA_IMZALARI:
        if imza in dusuk:
            return kod, aciklama
    kodlar = sorted(set(re.findall(r"\[(\d{3})\]", log_text or "")))
    if kodlar:
        return "create_failed", "SAP HTTP durum(lari): %s (ham sebep client_log'da)." % ", ".join(kodlar)
    return "create_failed", ""


# ── aXet 2026-09-13: tipe özel kabuk yaratma (reçeteler `tools/shells.py`; IMPLEMENTATION.md §14) ──
_PAKET_TIPLERI = frozenset({"package", "devc", "devc/k"})

_KABUK_SONRAKI_ADIM = {
    "ddls": ("Kabuk BOŞ (kaynak gövdeye konmadı — inline-POST boş kaynak tuzağı). Sıradaki: "
             "adt_get(ddls) → adt_push_source(ddls) → adt_activate → adt_get readback."),
    "srvd": "Kabuk boş. Sıradaki: adt_get(srvd) → adt_push_source(srvd) → adt_activate(srvd).",
    "bdef": ("Kabuk boş. BDEF adı kök entity adıyla AYNI olmalı (SAP zorunlu; araç doğrulayamaz). Sıradaki: "
             "adt_get(bdef) → adt_push_source(bdef) (aktive ETMEZ) → adt_activate(<kök ddls>, "
             "also=[bdef, behavior class])."),
    "ddlx": ("Kabuk boş. Hedef CDS `@Metadata.allowExtensions: true` taşımalı. Sıradaki: adt_get(ddlx) → "
             "adt_push_source(ddlx) → adt_activate(ddlx)."),
    "dcls": ("Kabuk boş. Sıradaki: adt_get(dcls) → adt_push_source(dcls) (`define role <ad> { grant select on "
             "<cds> where … }`) → adt_activate(dcls). Rolün veriyi gerçekten süzdüğünü tüketici tarafında ayrıca "
             "test et (aktivasyon süzmeyi kanıtlamaz)."),
    "fugr": "Grup inaktif yaratılır. Sıradaki: adt_activate(fugr) → adt_post_shell(func, extra.function_group).",
    "func": ("FM kabuğu. İmza + gövde TEK kaynakta, satır-içi ABAP (`*\"` yorum bloğu DEĞİL): adt_get(func) → "
             "adt_push_source(func). RFC-enable SE37'de tek-tık (ADT create attribute'u değil). Yeni FM arama "
             "indeksinde henüz görünmüyorsa adt_get(func) exists:false dönebilir (DOĞRULANMADI)."),
    "msag": ("Yalnız kabuk. Sıradaki: adt_msgclass_read (doğrula + pull kaydı) → adt_msgclass_write "
             "(mesajları numaraya göre birleştirir; üzerine yazma/silme yalnız açık argümanla)."),
    "enqu": ("Kilit objesi İNAKTİF ve ENQUEUE_/DEQUEUE_ FM'leri üretilmemiş durumda. Sıradaki: "
             "adt_activate(object_type='enqu')."),
    "ttyp": ("Sıradaki: adt_activate(ttyp) → adt_sql_query ile DD40L.ROWTYPE dolu mu doğrula (ROWTYPE NULL "
             "kalabilir). Yeni tablo tipi için tercih: adt_ttyp_create (yaratma + aktivasyon + iki kanallı "
             "readback + boş satır tipi düzeltmesi tek çağrıda)."),
}


def _ham_varlik_get(path: str, accept: str) -> tuple[Optional[bool], str, Optional[str]]:
    """Salt-GET varlık sondası → (var_mi, sonda, gövde). 200 var · 404 yok · diğer ölçülemedi."""
    client = _get_client()
    adt = getattr(client, "adt_client", None) or client
    with _capture_stdout():
        r = adt.session.get(adt.url + path, headers={"Accept": accept},
                            verify=adt.session.verify, timeout=60)
    durum = int(getattr(r, "status_code", 0) or 0)
    if durum == 200:
        return True, "checked_found", getattr(r, "text", "") or ""
    if durum == 404:
        return False, "checked_absent", None
    return None, "unavailable:http_%d" % durum, None


def _enqu_varlik_oku(name: str, object_type: str, include_source: bool) -> dict:
    """`adt_get(enqu)` gövdesi: salt-GET varlık sondası (`_ham_varlik_get` yeniden kullanılır).

    200 → `ok:true exists:true` · 404 → `ok:true exists:false` · diğer kod / istisna → `ok:false` (ÖLÇÜLEMEDİ;
    "yok" DEĞİL). `include_source=true` → `unsupported_type`, AĞA GİDİLMEZ (kilit objesinin kaynak metni yok).
    """
    temel = {"name": name.upper(), "type": object_type}
    if include_source:
        return {"ok": False, "error": "unsupported_type", **temel,
                "message": "Kilit objesinin kaynak metni yok (XML tanım); adt_get(enqu) yalnız "
                           "include_source=false ile varlık söyler."}
    from urllib.parse import quote
    try:
        var, sonda, _metin = _ham_varlik_get("/sap/bc/adt/ddic/lockobjects/sources/" + quote(name.lower(), safe=""),
                                             "*/*")
    except Exception as exc:  # noqa: BLE001 — bağlantı istisnası = ölçülemedi
        out = _err_from_exc(exc)
        out.update(temel, exists_probe="unavailable:%s" % type(exc).__name__)
        return out
    if var is None:
        return {"ok": False, "error": sonda.split(":", 1)[-1], **temel, "exists_probe": sonda,
                "message": "Kilit objesi varlığı ÖLÇÜLEMEDİ (%s) — bu 'yok' DEĞİLDİR." % sonda}
    return {"ok": True, **temel, "exists": var, "exists_probe": sonda}


def _kabuk_sondasi(tip: str, name: str, ek: dict | None) -> dict:
    """Kabuk POST'u SONRASI varlık sondası → {var: True|False|None, sonda, ml, metin}.

    ⛔ `None` = ÖLÇÜLEMEDİ ("yok" DEĞİL). func için arama indeksi DEĞİL doğrudan FM ucu okunur
    (yeni FM indekste henüz olmayabilir): `Accept …fmodules.v3+xml` (object_types.py FM notu, Q261).
    """
    from urllib.parse import quote
    from sapadt.tools import shells as _shells
    bos = {"var": None, "sonda": "unavailable:sonda_yok", "ml": None, "metin": None}
    try:
        if tip in ("ddls", "srvd", "fugr", "ttyp"):
            p = _adt_get_oku(name, tip, tip == "ttyp")
        elif tip == "bdef":
            p = _read_source_object(name, "bo/behaviordefinitions", "bdef")
        elif tip == "ddlx":
            p = _read_source_object(name, "ddic/ddlx/sources", "ddlx")
        elif tip == "dcls":
            p = _read_source_object(name, "acm/dcl/sources", "dcls")
        elif tip == "msag":
            p = _msgclass_oku(name)   # iç sonda: pull kaydı yazmaz
        elif tip in ("func", "enqu"):
            if tip == "func":
                path = "/sap/bc/adt/functions/groups/%s/fmodules/%s" % (
                    quote(str((ek or {}).get("function_group", "")).lower(), safe=""), quote(name.lower(), safe=""))
                accept = "application/vnd.sap.adt.functions.fmodules.v3+xml"
            else:
                path = "/sap/bc/adt/ddic/lockobjects/sources/" + quote(name.lower(), safe="")
                accept = "*/*"
            var, sonda, metin = _ham_varlik_get(path, accept)
            return {"var": var, "sonda": sonda, "ml": _shells.master_language_oku(metin), "metin": metin}
        else:
            return bos
    except Exception as exc:  # noqa: BLE001 — teşhis bozulmasın
        return {**bos, "sonda": "unavailable:%s" % type(exc).__name__}
    if p.get("ok") is True and p.get("exists") is True:
        metin = p.get("metadata") if isinstance(p.get("metadata"), str) else p.get("source")
        ml = (p.get("master_language") or _shells.master_language_oku(p.get("metadata"))
              or _shells.master_language_oku(p.get("source")))
        return {"var": True, "sonda": "checked_found", "ml": ml, "metin": metin}
    if p.get("ok") is True and p.get("exists") is False:
        return {"var": False, "sonda": "checked_absent", "ml": None, "metin": None}
    return {**bos, "sonda": "unavailable:%s" % (p.get("error") or "bilinmeyen")}


def _yeni_kabuk(tip: str, object_type: str, name: str, package: str, transport: str,
                description: str, ek: dict | None) -> dict:
    """Tipe özel kabuk POST'u + sonda. Guard'lar çağıranda (adt_post_shell) AĞDAN ÖNCE koştu."""
    from sapadt.tools import shells as _shells
    client = _get_client()
    adt = getattr(client, "adt_client", None) or client
    ml = _master_language() or str(getattr(adt, "language", "") or "")
    ist = _shells.istek(tip, name, package, description, ml, ek or {})
    temel = {"name": name.upper(), "type": object_type, "recipe": ist.kaynak}
    try:
        with _capture_stdout() as out:
            durum, govde = _shells.gonder(adt, ist, transport)
    except Exception as exc:  # noqa: BLE001 — POST gitti mi bilinmiyor → sonda şart
        hata = _err_from_exc(exc)
        s = _kabuk_sondasi(tip, name, ek)
        hata.update(temel)
        hata.update(exists_after=s["var"], exists_probe=s["sonda"])
        return hata
    log_text = ("%s\n[%d] POST %s\n%s" % (out.getvalue().strip(), durum, ist.path, govde[:500])).strip()
    sinif = _shells.sonuc_sinifi(durum, govde)
    s = _kabuk_sondasi(tip, name, ek)
    if sinif == "created":
        resp = {"ok": True, **temel, "object_url": ist.object_url, "http_status": durum,
                "exists_after": s["var"], "exists_probe": s["sonda"], "master_language": s["ml"],
                "next_step": _KABUK_SONRAKI_ADIM.get(tip), "client_log": log_text}
        if s["var"] is False:
            resp.update(ok=False, error="create_not_persisted", message=(
                "SAP %d döndü ama varlık sondası objeyi BULAMADI (checked_absent). 2xx tek başına kanıt "
                "değildir (MSAG'de DEV olmayan paket verilince sessizce yaratılmadığı ölçülmüştü). Paketi/"
                "transportu kontrol et; körlemesine tekrar yaratma." % durum))
        elif s["var"] is None:
            resp["notice"] = ("Varlık sondası ÖLÇÜLEMEDİ (%s) — yaratma 'doğrulandı' DEĞİL; adt_get / "
                              "adt_search_objects ile elle doğrula." % s["sonda"])
        if s["ml"] and ml and s["ml"].upper() != ml.upper():
            resp["master_language_warning"] = (
                "Canlı masterLanguage=%s, sap-project.json master_language=%s — Yasak D. DUR, bildir "
                "(dil yerinde değişmez: sil + doğru dilde yeniden yarat kararı kullanıcının)." % (s["ml"], ml))
        if tip == "ttyp" and s["var"] is True:
            m = re.search(r"<ttyp:typeName>([^<]*)</ttyp:typeName>", s["metin"] or "")
            resp["row_type_live"] = m.group(1).strip() if m else None
            if not resp["row_type_live"]:
                resp["row_type_warning"] = ("Canlı XML'de satır tipi BOŞ/okunamadı — aktivasyon sonrası "
                                            "DD40L.ROWTYPE kontrolü ŞART.")
        return resp
    kod, aciklama = _create_hata_sinifi(log_text)
    if sinif == "already_exists":
        kod = "already_exists"
    if s["var"] is True:
        mesaj = ("⚠ CREATE HATA RAPORLADI **AMA OBJE SAP'DE VAR** (varlik sondasi). ⛔ TEKRAR YARATMAYA "
                 "CALISMA — kabuk hazir; adt_get ile devam et.")
    elif s["var"] is False:
        mesaj = "Obje yaratilmadi (varlik sondasi: yok)."
    else:
        mesaj = ("⚠ Obje yaratildi mi OLCULEMEDI (varlik sondasi: %s). Bu sonuc 'yaratilmadi' DEGILDIR — "
                 "⛔ KOR RETRY YAPMA." % s["sonda"])
    return {"ok": False, "error": kod, **temel, "http_status": durum,
            "message": (mesaj + (" " + aciklama if aciklama else "")).strip(),
            "exists_after": s["var"], "exists_probe": s["sonda"], "client_log": log_text}


def _varlik_olcumu(name: str, object_type: str) -> tuple[Optional[bool], str, dict]:
    """`_varlik_sondasi` + ham `adt_get` yanıtı (ör. tablo/yapı kardeş ucunda bulunduysa `resolved_type`).

    ⛔ Tablo/yapı kardeş ucu (2026-09-21): ilk uç 404 verip KARDEŞ uç ÖLÇÜLEMEDİYSE (`sibling_probe: unavailable:…`)
    `adt_get` `exists:false` döner ama yokluk yalnız ilk uç için kanıtlıdır → burada `None` (ÖLÇÜLEMEDİ). Eskiden
    `False` dönüyordu: aynı adlı tablo/yapı orada duruyor olabilirken yaratma kapısı "yok" okuyordu.
    """
    try:
        p = adt_get(name=name, object_type=object_type, include_source=False)
    except Exception as exc:  # noqa: BLE001 — teshis bozulmasin
        return None, "unavailable:%s" % type(exc).__name__, {}
    if p.get("ok") is True and p.get("exists") is True:
        return True, "checked_found", p
    if p.get("ok") is True and p.get("exists") is False:
        kardes = p.get("sibling_probe")
        if isinstance(kardes, str) and kardes.startswith("unavailable"):
            return None, "unavailable:sibling_%s" % kardes.split(":", 1)[-1], p
        return False, "checked_absent", p
    return None, "unavailable:%s" % (p.get("error") or "bilinmeyen"), p


def _varlik_sondasi(name: str, object_type: str) -> tuple[Optional[bool], str]:
    """Create hatasi SONRASI objenin GERCEKTEN var olup olmadigini olc.

    Uc-degerli: `True` (var) · `False` (yok) · `None` (OLCULEMEDI — "yok" DEGIL).
    ⛔ `None`'i "yaratilmadi" diye okuma; bu ayrimin kaybi kaydin ta kendisidir.
    Tablo/yapıda kardeş uç ölçülemezse de `None` (bkz. `_varlik_olcumu`).
    """
    var, sonda, _p = _varlik_olcumu(name, object_type)
    return var, sonda


@profil_tool()
def adt_post_shell(
    object_type: str,
    name: str,
    package: str,
    transport: str,
    description: str,
    extra: dict | None = None,
) -> dict:
    """Create an empty SAP object shell (inactive, no source yet).

    Use adt_push_source + adt_activate after this for atom flow.
    Composite tools (adt_*_create) chain these three atomically.

    Args:
        object_type: Genel yol (`SAPClient.create_object`): 'class', 'interface', 'program', 'include'.
            Tipe özel reçeteler (`tools/shells.py`): 'ddls' (boş CDS kabuğu — kaynak ayrı push),
            'srvd', 'bdef' (ad = kök entity adı), 'ddlx', 'dcls' (v0.5.2), 'fugr', 'func', 'msag'
            (yalnız kabuk; mesaj yazma desteklenmez), 'enqu' (ad E+Z/Y), 'ttyp'. 'srvb'/'doma'/'dtel'/
            'structure'/'tabl' → `unsupported_type` (gerekçe mesajda). Paket → ADR_0005_C.
        name: Customer-namespace name (Z*/Y*; lock object E+Z/Y).
        package: Target SAP package (mevcut; paket yaratılmaz).
        transport: Modifiable transport request number.
        description: Kısa metin — master_language'de, BOŞ OLAMAZ (ADR 0005 §D).
        extra: Tipe özel alanlar — func: {"function_group"} · enqu: {"primary_table",
            "lock_fields": [..], "lock_mode": "E|S|X", "allow_rfc": bool} · ttyp: {"row_type"}.
            Başka tipte ya da tanınmayan alanla verilirse `invalid_argument` (çıkış 3).

    ⛔ **`ok: false` "OBJE YARATILMADI" DEMEK DEGILDIR — RETRY ETMEDEN ONCE OKU.**
    Olculdu (2026-08-19 ve 2026-08-21, dort obje): arac `400` / `500` raporladi, kabuk
    **fiilen YARATILMISTI**. Bu yuzden hata donusune artik bir **VARLIK SONDASI** eklidir:
      • `exists_after: true`  → obje SAP'de VAR. ⛔ **TEKRAR YARATMAYA CALISMA** (mukerrer
        obje riski); `adt_push_source` ile devam et.
      • `exists_after: false` → obje yok, yeniden denenebilir.
      • `exists_after: null`  → **OLCULEMEDI** ("yok" DEGIL). `exists_probe`'a bak, elle dogrula.
    `error` degerleri: `already_exists` (SAP `ExceptionResourceAlreadyExists`) ·
    `description_too_long` (**GERCEK** 400 — kisa metin SAP sinirini asiyor, olculen sinif
    siniri 60) · `create_failed` (siniflanamadi; ham sebep `client_log`'da).
    ⇒ Yan kural (iki kez ise yaradi): ADT 400'lerinde **ham govdeyi oku** — sebep orada
    yazilidir (kolon adi · metin siniri · zaten var). Govdeyi okumadan "flakiness" deme.

    Returns:
        {ok, name, type, object_url?, result?, client_log}
        On failure: {ok: false, error, message, exists_after, exists_probe, client_log}
        On guardrail block: {ok: false, error: 'guardrail_violation', code, message}
    """
    try:
        require_writable_tier(get_active_tier(), what=f"{object_type} create")
        if str(object_type or "").strip().lower() in _PAKET_TIPLERI:
            raise GuardrailViolation("ADR_0005_C", f"Paket yaratma yasak (Kesin Yasak C): object_type={object_type}.")
        require_customer_namespace(name, what=object_type, object_type=object_type)
        require_transport(transport, what=f"{object_type} create", package=package)
        require_tr_text(description, what=f"{object_type} description")
    except GuardrailViolation as gv:
        return gv.as_dict()

    from sapadt.tools import shells as _shells
    try:
        kabuk_tipi = _shells.kabuk_tipi(object_type)
        if kabuk_tipi == _shells.GENEL:
            if extra:
                raise _shells.KabukHatasi("invalid_argument", f"extra '{object_type}' tipinde kabul edilmez "
                                                              "(genel yaratıcı ek alan almaz).")
            ek = None
        else:
            ek = _shells.extra_dogrula(kabuk_tipi, extra)
    except _shells.KabukHatasi as kh:
        return {"ok": False, "error": kh.code, "name": name, "type": object_type, "message": kh.message}
    if kabuk_tipi != _shells.GENEL:
        if kabuk_tipi == "func":
            try:   # standart FUGR içine FM = standart objeyi değiştirmek (Yasak A)
                require_customer_namespace(ek["function_group"], what="function_group",
                                           object_type="functiongroup")
            except GuardrailViolation as gv:
                return gv.as_dict()
        return _yeni_kabuk(kabuk_tipi, object_type, name, package, transport, description, ek)

    client = _get_client()
    try:
        with _capture_stdout() as out:
            result = client.create_object(
                object_type=object_type,
                name=name,
                package=package,
                description=description,
                transport=transport,
            )
        log_text = out.getvalue().strip()
        if result:
            # `create_object` basarida obje URL'ini (str) doner. Eskiden yalniz
            # `result if isinstance(result, dict)` yaziliydi -> str URL her zaman None'a
            # dusuyordu ve docstring'in vaat ettigi `object_url` HIC dolmuyordu.
            return {
                "ok": True,
                "name": name,
                "type": object_type,
                "object_url": result if isinstance(result, str) else None,
                "result": result if isinstance(result, dict) else None,
                "client_log": log_text,
            }

        # ── BASARISIZ GORUNEN DONUS: "olmadi" mi, "oldu ama hata raporlandi" mi? ──
        # (kayitlar #20 + #49 — retry tuzagi; gerekce icin yukaridaki blok notuna bak)
        kod, aciklama = _create_hata_sinifi(log_text)
        var_mi, sonda = _varlik_sondasi(name, object_type)
        if var_mi is True:
            mesaj = ("⚠ CREATE HATA RAPORLADI **AMA OBJE SAP'DE VAR** (varlik sondasi: "
                     "adt_get exists=true). ⛔ TEKRAR YARATMAYA CALISMA — mukerrer obje "
                     "riski. Kabuk hazir; `adt_push_source` ile devam et.")
        elif var_mi is False:
            mesaj = "Obje yaratilmadi (varlik sondasi: adt_get exists=false)."
        else:
            mesaj = ("⚠ Obje yaratildi mi OLCULEMEDI (varlik sondasi: %s). Bu sonuc "
                     "'yaratilmadi' DEGILDIR — ⛔ KOR RETRY YAPMA; once adt_get / TADIR ile "
                     "varligi ELLE olc." % sonda)
        return {
            "ok": False,
            "error": kod,
            "name": name,
            "type": object_type,
            "message": (mesaj + (" " + aciklama if aciklama else "")).strip(),
            "exists_after": var_mi,
            "exists_probe": sonda,
            "client_log": log_text,
        }
    except Exception as exc:
        return _err_from_exc(exc)


# =============================================================================
# adt_push_source
# =============================================================================

# ── aXet 2026-09-13: kaynak yazma — tipe özel yollar (IMPLEMENTATION.md §14.3) ─────────────────
_BDEF_TIPLERI = frozenset({"bdef", "behaviordefinition"})
# Yazılabilir alt-include segmentleri. Yazma yolu CANLI ölçülmüş: testclasses (adt-classes.md §24.8) ·
# implementations (adt-rap.md §32.6h + object_types Q283 PUT). Z41 (2026-09-21): definitions (CCDEF) ve
# macros (CCMAC) AYNI yoldan (`push_class_include`: yoksa POST iskelet → PUT gövde → bayt readback) açıldı.
# YAZMA yolu CANLI ÖLÇÜLDÜ (2026-09-21, DEV, bir Z sınıfı): PUT /includes/definitions ve /includes/macros →
# sınıf aktivasyonu → aktif readback eşit (bytes_live/verified); kontrol grubu aynı turda ccimp (implementations).
# ⇒ Ölçülmemiş yazma segmenti KALMADI; küme boş tutulur (yeni segment eklenirse ÖNCE buraya, ölçülünce çıkar).
_YAZILABILIR_INCLUDE = frozenset({"testclasses", "implementations", "definitions", "macros"})
_YAZMA_OLCULMEDI_INCLUDE: frozenset = frozenset()
_PUSH_DESTEKSIZ = {
    "srvb": "SRVB kaynak metni taşımaz; yayın için adt_publish_service.",
    "servicebinding": "SRVB kaynak metni taşımaz; yayın için adt_publish_service.",
    "msag": "Mesaj sınıfının kaynak metni yok; mesajlar için adt_msgclass_read → adt_msgclass_write.",
    "messageclass": "Mesaj sınıfının kaynak metni yok; mesajlar için adt_msgclass_read → adt_msgclass_write.",
    "enqu": "Kilit objesinin kaynak metni yok (XML tanım); yaratma adt_post_shell(enqu) + adt_activate(enqu).",
    "lock": "Kilit objesinin kaynak metni yok; adt_post_shell(enqu) + adt_activate(enqu).",
    "lockobject": "Kilit objesinin kaynak metni yok; adt_post_shell(enqu) + adt_activate(enqu).",
    "lockobjects": "Kilit objesinin kaynak metni yok; adt_post_shell(enqu) + adt_activate(enqu).",
}
_BDEF_KILIT_ACCEPT = "application/*,application/vnd.sap.as+xml;dataname=com.sap.adt.lock.result"


def _push_bdef_kaynak(client, name: str, source: str, transport: str) -> dict:
    """BDEF kaynağı: LOCK → PUT `/source/main` (text/plain, If-Match YOK) → UNLOCK → readback. AKTİVE ETMEZ.

    Reçete: kaynak çekirdek `scripts/push_bo_atomic.py:124-162` (canlı: 4 BDEF dahil 14 obje, adt-rap.md:208-232)
    + `scripts/create_rap_service.py:413-440`; If-Match YOK: `playbook/adt-rap.md:94`. Managed BDEF tek
    başına aktive edilemez (behavior class ile birlikte — adt-rap.md:199-206) ⇒ aktivasyon ayrı adımdır.
    Dönüş `push_object` sözleşmesiyle aynı anahtarları taşır (success/source_uploaded/activated/readback_ok).
    HTTP reddi (LOCK/PUT) istisna DEĞİL `success:false` döner; ağ istisnası yukarı çıkar (yükleme belirsiz).
    """
    from urllib.parse import quote
    from source_normalize import normalize_source  # type: ignore
    adt = getattr(client, "adt_client", None) or client
    obj = "/sap/bc/adt/bo/behaviordefinitions/" + quote(name.lower(), safe="")
    sistem = {"sap-client": str(getattr(adt, "client", "") or ""),
              "sap-language": str(getattr(adt, "language", "") or "")}
    sonuc = {"success": False, "error": "", "error_type": "", "source_uploaded": False,
             "activated": False, "readback_ok": None}
    handle = None
    try:
        lr = adt._request_with_csrf_retry(
            "post", adt.url + obj, headers={"X-sap-adt-sessiontype": "stateful", "Accept": _BDEF_KILIT_ACCEPT},
            params={"_action": "LOCK", "accessMode": "MODIFY", "corrNr": transport})
        m = re.search(r"<LOCK_HANDLE[^>]*>([^<]+)</LOCK_HANDLE>", getattr(lr, "text", "") or "")
        if not m:
            sonuc.update(error="BDEF LOCK başarısız (HTTP %s): %s" % (getattr(lr, "status_code", "?"),
                                                                     (getattr(lr, "text", "") or "")[:300]),
                         error_type="SAPLockError")
            return sonuc
        handle = m.group(1)
        pr = adt._request_with_csrf_retry(
            "put", adt.url + obj + "/source/main",
            headers={"Content-Type": "text/plain; charset=utf-8", "Accept": "*/*", **sistem},
            params={"corrNr": transport, "lockHandle": handle}, data=source.encode("utf-8"))
        if getattr(pr, "status_code", 0) not in (200, 201, 204):
            sonuc.update(error="BDEF PUT reddedildi (HTTP %s): %s" % (getattr(pr, "status_code", "?"),
                                                                     (getattr(pr, "text", "") or "")[:300]),
                         error_type="SAPADTError")
            return sonuc
        sonuc["source_uploaded"] = True
    finally:
        if handle:
            # Z50 ⓔ (v0.5.1): yanıt KODU da okunur (eskiden yalnız istisna uyarı üretiyordu; 403/500 sessizdi).
            # Sözleşme `create_table_with_ddl` ile aynı: unlock_ok True = 200/204 · False = başka kod / istisna.
            try:
                ur = adt._request_with_csrf_retry("post", adt.url + obj,
                                                  headers={"X-sap-adt-sessiontype": "stateful"},
                                                  params={"_action": "UNLOCK", "lockHandle": handle})
                u_kod = getattr(ur, "status_code", None)
                sonuc["unlock_ok"] = u_kod in (200, 204)
                if not sonuc["unlock_ok"]:
                    sonuc["unlock_warning"] = ("UNLOCK HTTP %s — kilit açılmamış olabilir (bayat kilit; kullanıcı "
                                               "SM12'de bakar; AI kilit SİLMEZ)." % u_kod)
            except Exception as u_exc:  # noqa: BLE001 — kilit bırakma hatası yazma sonucunu değiştirmez
                sonuc["unlock_ok"] = False
                sonuc["unlock_warning"] = ("UNLOCK başarısız (%s) — bayat kilit kalmış olabilir (kullanıcı SM12)."
                                           % type(u_exc).__name__)
    try:
        with _capture_stdout():
            rb = adt.session.get(adt.url + obj + "/source/main", headers={"Accept": "text/plain"},
                                 verify=adt.session.verify, timeout=60)
        if getattr(rb, "status_code", 0) == 200:
            sonuc["readback_ok"] = normalize_source(rb.text or "") == normalize_source(source)
            if not sonuc["readback_ok"]:
                sonuc["readback_reason"] = "canlı (inaktif) BDEF kaynağı gönderilenle AYNI DEĞİL"
        else:
            sonuc["readback_reason"] = "readback HTTP %s" % getattr(rb, "status_code", "?")
    except Exception as exc:  # noqa: BLE001
        sonuc["readback_reason"] = "readback okunamadı (%s)" % type(exc).__name__
    sonuc["success"] = sonuc["readback_ok"] is not False
    if sonuc["readback_ok"] is False:
        sonuc["error"] = "BDEF readback UYUŞMADI — kaynak SAP'de gönderildiği gibi durmuyor."
    sonuc["activation_note"] = ("BDEF aktive EDİLMEDİ (reçete gereği ayrı adım). adt_activate(name=<kök ddls>, "
                                "object_type='ddls', also=[{name:<bdef>, object_type:'bdef'}, "
                                "{name:<behavior class>, object_type:'class'}]).")
    return sonuc


def _push_fm_kaynak(client, name: str, fm_grubu: str, source: str, transport: str | None) -> dict:
    """FM kaynağı (imza satır-içi + gövde): `SAPADTClient.set_function_module_source(activate=False)`
    (sıkı stateful LOCK → PUT → UNLOCK, CORRNR otoritesi, yabancı transport kapısı) → ayrı aktivasyon
    `activate_object(FM, fm_url)`.

    Reçete: `playbook/adt-fugr-functions.md:74-169` + `adt-foundation.md:409-464`. Genel `set_object_source`
    FM'de 423 verdiği için KULLANILMAZ (adt-fugr-functions.md:308). Aktivasyon kütüphane içinde değil ayrı
    çağrılır: kütüphanenin `activate=True` dalı aktivasyon istisnasını PUT sonrası yükseltir ve "yüklendi mi"
    bilgisi kaybolurdu.
    """
    from sap_adt_lib import SAPADTError  # type: ignore
    adt = getattr(client, "adt_client", None) or client
    sonuc = {"success": False, "error": "", "error_type": "", "source_uploaded": False, "activated": False,
             "readback_ok": None,
             "readback_reason": "FM yolunda kütüphane readback yapmaz (yükleme sonrası canlı okuma pull_state'e yazılır)."}
    try:
        out = adt.set_function_module_source(name, fm_grubu, source, transport=transport, activate=False)
    except SAPADTError as exc:   # HTTP reddi (LOCK/PUT ya da yabancı transport) → yükleme YOK
        sonuc.update(error=str(exc)[:800], error_type=type(exc).__name__)
        if getattr(exc, "unlock_ok", None) is not None:   # Z50 ⓓ: kilit alındıysa UNLOCK sonucu görünür
            sonuc["unlock_ok"] = exc.unlock_ok
        if getattr(exc, "unlock_warning", None):
            sonuc["unlock_warning"] = exc.unlock_warning
        return sonuc
    if isinstance(out, dict):
        if out.get("unlock_ok") is not None:
            sonuc["unlock_ok"] = out["unlock_ok"]
        if out.get("unlock_warning"):
            sonuc["unlock_warning"] = out["unlock_warning"]
    if not (isinstance(out, dict) and out.get("success")):
        sonuc["error"] = "set_function_module_source başarı bildirmedi"
        return sonuc
    sonuc["source_uploaded"] = True
    fm_url = out.get("object_url")
    try:
        act = adt.activate_object(name.upper(), fm_url)
        sonuc["activated"] = bool(act.get("success")) if isinstance(act, dict) else bool(act)
        if isinstance(act, dict) and not sonuc["activated"]:
            sonuc["activation_errors"] = act.get("errors")
    except Exception as exc:  # noqa: BLE001 — yükleme OLDU; aktivasyon ayrı sonuç
        sonuc["activation_error"] = ("%s: %s" % (type(exc).__name__, exc))[:300]
    sonuc["success"] = sonuc["activated"]
    if not sonuc["activated"]:
        sonuc["error"] = ("FM kaynağı yüklendi ama aktivasyon başarısız — hatayı düzeltip adt_get + "
                          "adt_push_source ile yeniden push et (aktivasyon push içinde yapılır).")
    return sonuc


_SILME_ORNEK, _SILME_SATIR_KIRP = 5, 120


def _silinen_satir_uyarisi(canli_kaynak: str, yeni_kaynak: str):
    """Z87 ⓑ+: canlıda olup yeni kaynakta olmayan satırlar → uyarı alanları; silme yoksa None.

    İki taraf readback kıyasıyla AYNI normalize'dan geçer (CRLF / satır sonu boşluğu sahte silme üretmez).
    Uyarıdır, red değil: meşru düzenleme de satır siler; karar kullanıcıya satırlar gösterilerek verilir."""
    import difflib
    from source_normalize import normalize_source  # type: ignore
    eski = normalize_source(canli_kaynak or "").splitlines()
    yeni = normalize_source(yeni_kaynak or "").splitlines()
    silinen, eklenen = [], 0
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, eski, yeni, autojunk=False).get_opcodes():
        if op in ("delete", "replace"):
            silinen.extend(eski[i1:i2])
        if op in ("insert", "replace"):
            eklenen += j2 - j1
    if not silinen:
        return None
    ornek = [(x if len(x) <= _SILME_SATIR_KIRP else x[:_SILME_SATIR_KIRP] + "…") for x in silinen[:_SILME_ORNEK]]
    return {
        "removed_lines_warning": {"removed": len(silinen), "added": eklenen, "sample": ornek},
        "warning": (f"Canlıda olup yeni kaynakta olmayan {len(silinen)} satır var — yerel kopya `adt_get` "
                    "çıktısından türemediyse bu satırlar KAYBOLUR. Satırları (removed_lines_warning.sample) "
                    "kullanıcıya göster; kasıtlı değilse `adt_get` ile yeniden çekip düzenlemeyi onun üzerine "
                    "uygula, onaysız tekrar yazma."),
    }


def _include_sonucu_esle(result):
    """`SAPClient.push_class_include` sonucunu `adt_push_source` readback sözleşmesine eşle."""
    if not isinstance(result, dict):
        return result
    inc = result.get("include") if isinstance(result.get("include"), dict) else {}
    if inc.get("verified") is True:
        result.setdefault("readback_ok", True)
    elif "READBACK UYUŞMADI" in str(result.get("error") or ""):
        result.setdefault("readback_ok", False)
    else:
        result.setdefault("readback_ok", None)
        result.setdefault("readback_reason", "alt-include readback sonucu yok")
    if result.get("source_uploaded") and not result.get("activated"):
        result.setdefault("activation_note", (
            "Include yazıldı ve readback doğrulandı ama ANA SINIF aktivasyonu başarısız. RAP behavior "
            "pool'da BDEF ile birlikte aktive et: adt_activate(<kök ddls>, also=[bdef, class])."))
    return result


@profil_tool()
def adt_push_source(
    name: str,
    object_type: str,
    source: str,
    transport: str | None = None,
    skip_reviewer: bool = False,
    ack_drop: str = "",
) -> dict:
    """Push source text to an existing SAP object.

    The shell must exist (use adt_post_shell first, or composite tools).
    Activation is a separate step — call adt_activate after.

    Reviewer pre-flight (ADR 0006) runs automatically on the source text
    (written to a temp file, passed to scripts/validators/run_review.py).
    BLOCKER verdict rejects the push. Use skip_reviewer=True only for emergencies
    (and document why in the commit message).

    Args:
        name: Object name (Z*/Y*).
        object_type: 'class', 'ddls', 'prog', 'tabl', ... · aXet: 'bdef' (LOCK→PUT→UNLOCK, aktive
            ETMEZ; transport zorunlu) · 'ccimp'/'ccau'/'ccdef'/'ccmac' (sınıf alt-include'u — `name` = ANA SINIF;
            transport zorunlu; ana sınıf aktive edilir) · 'func' (FM kaynağı; fonksiyon grubu canlıdan
            çözülür ve Z/Y olmalı; aktive edilir). 'srvb'/'msag'/'enqu' → unsupported_type.
        source: Source body text (full content; partial diffs not supported).
        transport: Modifiable transport (optional if object already has assignment).
        skip_reviewer: Bypass reviewer pre-flight (NOT recommended).
        ack_drop: Comma-separated table field names whose DROP is explicitly
            approved (user+lead, ADR 0005-B). Forwarded to the embedded reviewer's
            --ack-drop → ONLY these named drops become ACK-WARNING; any un-named
            drop or any TYPE/RENAME change still BLOCKER. This is the targeted,
            auditable alternative to skip_reviewer for intentional table DROPs —
            the rest of the drop-guard (and all other checks) stay active.

    PULL-BEFORE-EDIT (iyimser eşzamanlılık): `adt_get` ile çekilmiş kayıt yoksa
    `pull_before_edit_missing`; yazmadan hemen önce canlı kaynak yeniden okunur ve özeti kayıttan
    farklıysa `source_changed_since_pull` (üzerine yazılmaz); canlı okuma başarısızsa
    `pull_live_read_failed`. Başarılı yüklemeden sonra kayıt canlıdan yeniden okunan özetle güncellenir.
    Z87 (uyarı, red değil): canlıda olup yeni kaynakta olmayan satırlar yazmadan önce hesaplanır →
    `removed_lines_warning {removed, added, sample}` + `warning`; yazma sürer (SKILL §2).

    Returns:
        {ok, name, type, result, client_log, reviewer?, pull_state?, removed_lines_warning?, warning?}
    """
    try:
        require_writable_tier(get_active_tier(), what=f"{object_type} push")
        require_customer_namespace(name, what=object_type, object_type=object_type)
    except GuardrailViolation as gv:
        return gv.as_dict()
    from object_types import (is_class_include, is_function_module_type,  # type: ignore
                              normalize_class_include)
    tip = (object_type or "").lower().strip()
    sinif_include = is_class_include(tip)
    include_kind = normalize_class_include(tip) if sinif_include else None
    fm_mi = is_function_module_type(tip)
    bdef_mi = tip in _BDEF_TIPLERI
    if sinif_include and include_kind not in _YAZILABILIR_INCLUDE:
        return {"ok": False, "error": "unsupported_type", "name": name, "type": object_type,
                "message": (f"'{include_kind}' alt-include'una YAZMA yolu canlı ölçülmedi (yalnız GET ölçüldü); "
                            f"desteklenen: {', '.join(sorted(_YAZILABILIR_INCLUDE))} (ccau/ccimp/ccdef/ccmac).")}
    if tip in _PUSH_DESTEKSIZ:
        return {"ok": False, "error": "unsupported_type", "name": name, "type": object_type,
                "message": f"adt_push_source '{object_type}' desteklenmiyor: {_PUSH_DESTEKSIZ[tip]}"}
    if sinif_include or bdef_mi:
        try:   # bu reçetelerde kilit corrNr ile alınır; kütüphane transportsuz kilidi reddeder
            require_transport(transport, what=f"{object_type} push")
        except GuardrailViolation as gv:
            return gv.as_dict()
    # Kesin Yasak B — İKİNCİ katman (birincisi `gate.check_std_dml`): kapıyı `tool_args`'sız
    # çağıran bir script de standart tabloya DML içeren kaynağı gönderemesin. Ağdan ÖNCE koşar.
    try:
        from sapadt.std_dml_scan import mesaj as _dml_mesaj, tara as _dml_tara
        _dml = _dml_tara(source, object_type)
    except Exception as exc:  # noqa: BLE001 — tarayıcı koşamadıysa GEÇMEZ (fail-closed)
        return {"ok": False, "error": "std_dml_scan_unavailable", "name": name, "type": object_type,
                "message": f"Kesin Yasak B taraması koşamadı ({type(exc).__name__}) — fail-closed."}
    if _dml:
        return GuardrailViolation("ADR_0005_B", _dml_mesaj(_dml),
                                  bulgular=[b.as_dict() for b in _dml]).as_dict()
    # Kesin Yasak A (Z104) — İKİNCİ katman (birincisi `gate.check_std_extension`): Z adlı obje kaynağında
    # standart objeyi genişletme (`extend type|view …`, `annotate …`, BDEF `extension`). Ağdan ÖNCE koşar.
    try:
        from sapadt import std_ext_scan as _ext
        _gen = _ext.tara(source, object_type)
    except Exception as exc:  # noqa: BLE001 — tarayıcı koşamadıysa GEÇMEZ (fail-closed)
        return {"ok": False, "error": "std_ext_scan_unavailable", "name": name, "type": object_type,
                "message": f"Kesin Yasak A genişletme taraması koşamadı ({type(exc).__name__}) — fail-closed."}
    if _gen:
        return GuardrailViolation("ADR_0005_A", _ext.mesaj(_gen),
                                  bulgular=[b.as_dict() for b in _gen]).as_dict()

    client = None   # PULL-BEFORE-EDIT: istemci kayıt kontrolünden SONRA alınır (kayıt yoksa ağa hiç gidilmez)
    tmp_file = None
    reviewer_warn = None
    push_denendi = False   # Q271: `client.push_object` çağrısına GİRİLDİ mi (belirsizlik sınırı)
    silme_uyarisi = None   # Z87 ⓑ+: canlıda olup yeni kaynakta olmayan satırlar (yazmadan önce hesaplanır)
    try:
        # Write source to temp file first — needed by both reviewer and SAPClient.push_object.
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=f".{object_type}.txt",
            delete=False,
        ) as f:
            f.write(source)
            tmp_file = Path(f.name)

        # Reviewer pre-flight (ADR 0006) — automatic, single point of enforcement.
        if not skip_reviewer:
            task = task_for_push(object_type, source)
            review = run_reviewer(task, str(tmp_file), ack_drop=ack_drop)
            if review.is_blocker:
                return reject_payload(name, object_type, review)
            # G2 (2026-07-31): SKIP artik SESSIZ degil — "PRE-FLIGHT KOSMADI" bilgisi
            # yanita girer (checklist!=wired sinifinin reviewer versiyonuna karsi).
            # Davranis DEGISMEZ (push yine gecer); yalniz gorunurluk.
            # aXet 2026-09-14 (K1): olculemeyen gate (measured=false; ör. include'da abaplint)
            # `unmeasured` + "ÖLÇÜLEMEDİ" notu ile yanita girer — verdict WARNING "temiz" okunmasin.
            reviewer_warn = on_kontrol_ozeti(review, skip_notice=(
                f"PRE-FLIGHT KOSMADI ({review.skip_reason}) — bu tip icin "
                "validator zinciri tanimli degil; 'reviewer PASS' SANMA."))

        # ADR 0016 REVİZE: pre-push DRIFT GUARD (M1) KALDIRILDI — kasıtlı edit'leri de
        # blokluyordu (repo≠canlı her meşru edit'te doğal). aXet'te hook yok; tazelik burada
        # İYİMSER EŞZAMANLILIK ile sağlanır: çekildiği andaki CANLI özet ↔ yazma anındaki CANLI özet.
        # "yerel dosya ≠ canlı" kıyası YAPILMAZ (her meşru düzenlemede doğal olarak farklıdır).
        kayit, pst_hata = _pull_state.kayit_al(name, object_type)
        if pst_hata:
            return {"ok": False, "error": "pull_state_unreadable", "name": name, "type": object_type,
                    "message": f"Pull-state okunamadı: {pst_hata}. `adt_get` ile kaynağı yeniden çek "
                               "(dosya yeniden yazılır); kayıt doğrulanmadan yazma yapılmaz.",
                    "reviewer": reviewer_warn}
        if kayit is None:
            return {"ok": False, "error": "pull_before_edit_missing", "name": name, "type": object_type,
                    "message": (f"PULL-BEFORE-EDIT: {_pull_state.anahtar(name, object_type)} için çekme kaydı yok. "
                                "Önce `adt_get` (include_source=true) ile güncel kaynağı çek, düzenlemeni o "
                                "kaynağın üzerine yap, sonra push et. Yeni yaratılan kabukta da önce adt_get."),
                    "reviewer": reviewer_warn}
        try:
            canli = _adt_get_oku(name, object_type, True)
        except Exception as exc:  # noqa: BLE001 — okuma istisnası da "okunamadı"dır, geçiş değil
            canli = _err_from_exc(exc)
        # Sınıf alt-include'u: 404 ile KANITLI yok. Kayıt da "yoktu" diyorsa ilk yaratım (POST-if-absent)
        # geçer; kayıt "vardı" diyorsa çekildikten sonra silinmiş demektir → değişti.
        include_yok = (sinif_include and isinstance(canli, dict) and canli.get("ok") is True
                       and canli.get("exists") is False and canli.get("include_absent_proven") is True)
        if include_yok and not kayit.get("absent"):
            return {"ok": False, "error": "source_changed_since_pull", "name": name, "type": object_type,
                    "message": ("PULL-BEFORE-EDIT: include çekildiğinde VARDI, şimdi SAP'de YOK — üzerine "
                                "yazılmadı. `adt_get` ile yeniden çek."),
                    "pulled_at": kayit.get("pulled_at"), "reviewer": reviewer_warn}
        if not include_yok and not (isinstance(canli, dict) and canli.get("ok") is True
                                    and canli.get("exists") is True and isinstance(canli.get("source"), str)):
            c = canli if isinstance(canli, dict) else {}
            return {"ok": False, "error": "pull_live_read_failed", "name": name, "type": object_type,
                    "message": ("PULL-BEFORE-EDIT: yazmadan önce canlı kaynak OKUNAMADI — çekildikten sonra "
                                "değişip değişmediği ölçülemedi, yazma yapılmadı. Bağlantıyı düzelt, tekrar dene."),
                    "live_read": {"error": c.get("error"), "exists": c.get("exists"),
                                  "message": str(c.get("message") or "")[:300]},
                    "reviewer": reviewer_warn}
        canli_ozet = kayit.get("sha256") if include_yok else _pull_state.ozet(canli["source"])
        if canli_ozet != kayit.get("sha256"):
            return {"ok": False, "error": "source_changed_since_pull", "name": name, "type": object_type,
                    "message": (f"PULL-BEFORE-EDIT: canlı kaynak {kayit.get('pulled_at')} tarihli çekmeden sonra "
                                "SAP'de DEĞİŞMİŞ — üzerine yazılmadı. `adt_get` ile yeniden çek, değişikliğini "
                                "yeni kaynağın üzerine yeniden uygula (başkasının değişikliğini ezme)."),
                    "pulled_at": kayit.get("pulled_at"), "pulled_sha256": str(kayit.get("sha256"))[:12],
                    "live_sha256": canli_ozet[:12], "reviewer": reviewer_warn}
        # Z87 ⓑ+ (2026-09-24): kıyas "canlı değişmedi" der ama yerel kopyanın çekilen kaynaktan TÜREDİĞİNİ
        # doğrulamaz — bayat bir kopya canlıdaki satırları sessizce geri alır. Zaten okunmuş canlı kaynak
        # (ek ağ çağrısı YOK) ile yeni kaynak kıyaslanır; silinen satır varsa YAZMADAN ÖNCE uyarı hazırlanır.
        # Yazma DEVAM eder (kullanıcı kararı: sert red yok). Dört push yolunun hepsi bu noktadan geçer.
        silme_uyarisi = None if include_yok else _silinen_satir_uyarisi(canli["source"], source)
        fm_grubu = None
        if fm_mi:
            # FUGR adı FM adından türetilemez → canlı okuma (arama indeksi) çözdü; TAHMİN yok.
            fm_grubu = str(canli.get("function_group") or "").strip().upper()
            try:   # standart FUGR içindeki FM'e yazmak = standart objeyi değiştirmek (Yasak A)
                require_customer_namespace(fm_grubu, what="function_group (canlıdan çözülen)",
                                           object_type="functiongroup")
            except GuardrailViolation as gv:
                return gv.as_dict()
        client = _get_client()
        push_denendi = True   # bundan sonra düşen bir istisna "ne yüklendi?" sorusunu AÇIK bırakır
        with _capture_stdout() as out:
            if sinif_include:
                result = _include_sonucu_esle(client.push_class_include(
                    class_name=name, include_kind=include_kind, transport=transport,
                    source_file=str(tmp_file)))
            elif bdef_mi:
                result = _push_bdef_kaynak(client, name, source, transport)
            elif fm_mi:
                result = _push_fm_kaynak(client, name, fm_grubu, source, transport)
            else:
                result = client.push_object(
                    object_name=name,
                    object_type=object_type,
                    transport=transport,
                    source_file=str(tmp_file),
                )
        ok = bool(result and (result.get("success") if isinstance(result, dict) else True))
        resp = {
            "ok": ok,
            "name": name,
            "type": object_type,
            "result": result if isinstance(result, dict) else None,
            "client_log": out.getvalue().strip(),
        }
        if reviewer_warn:
            resp["reviewer"] = reviewer_warn
        if silme_uyarisi:
            resp.update(silme_uyarisi)
        if (sinif_include or bdef_mi or fm_mi) and isinstance(result, dict):
            resp["activated"] = result.get("activated")
            for alan in ("activation_note", "activation_errors", "activation_error", "unlock_warning"):
                if result.get(alan):
                    resp[alan] = result[alan]
            if fm_mi:
                resp["function_group"] = fm_grubu
            if sinif_include:
                resp["include"] = include_kind
                resp["write_path_measured"] = include_kind not in _YAZMA_OLCULMEDI_INCLUDE
            if not resp["ok"] and result.get("error"):
                resp["error"] = "push_failed"
                resp["message"] = str(result.get("error"))[:800]

        # ── READBACK GÖRÜNÜRLÜĞÜ (2026-08-01 bug-avı, "doğrulama koşamadı = doğrulandı") ──
        # `push_object` aktivasyon sonrası AKTİF kaynağı yüklenenle kıyaslar. Bu kıyas
        # KOŞAMADIĞINDA (okuma hatası / tip kapsam dışı) eskiden yanıtta HİÇBİR iz kalmıyordu
        # → `ok:true` hem "doğrulandı" hem "doğrulanamadı" anlamına geliyordu. Artık üç değer
        # AÇIKÇA yüzeye çıkar. Davranış (ok) DEĞİŞMEZ — yalnız görünürlük (reviewer SKIP
        # görünürlüğüyle aynı desen, 2026-07-31).
        if isinstance(result, dict):
            rb = result.get("readback_ok")
            resp["readback_verified"] = rb if rb in (True, False) else None
            if resp["readback_verified"] is None:
                resp["readback_notice"] = (
                    "READBACK KOŞMADI/ÖLÇÜLEMEDİ — canlı aktif kaynak yüklenenle "
                    "KIYASLANAMADI. Bu 'yazım doğrulandı' DEĞİLDİR; kritik objede "
                    "adt_get(version=active) ile elle teyit et. "
                    + str(result.get("readback_reason", "")).strip()
                ).strip()

        # Aktivasyon-oncesi canli syntax-check (push_object icinde) basarisizsa yuzeye cikar:
        # push upload etti ama AKTIVE ETMEDI -> ok=False + hatalar (gateway net gorsun, nested kalmasin).
        if isinstance(result, dict) and result.get("syntax_precheck") == "failed":
            resp["ok"] = False
            resp["syntax_precheck"] = "failed"
            resp["syntax_errors"] = result.get("syntax_errors", [])
        # On-kontrol OLCULEMEDI -> push aktivasyona DEVAM etti (`ok` DEGISMEZ) ama cagiran bunu
        # ust seviyede gorsun (`readback_notice` deseni); nested `result` icinde de durur.
        elif isinstance(result, dict) and result.get("syntax_precheck") == "olculemedi":
            resp["syntax_precheck"] = "olculemedi"
            resp["syntax_precheck_notice"] = (
                "SOZDIZIMI ON-KONTROLU OLCULEMEDI — push aktivasyona devam etti; bu 'sozdizimi "
                "temiz' DEGILDIR (aktivasyon hukmu ve readback ayri kapidir). Sebep: "
                + str(result.get("sozdizimi_sebep") or "bildirilmedi"))

        # Readback-gate baseline'ı → adt_activate sonrası AKTİF source ile normalize-compare.
        # ⛔ Q271 (2026-09-09): tetikleyici **UPLOAD**, `ok` DEĞİL. Eskiden `if ok:` yazıyordu;
        # `ok` = upload AND activate AND readback (sap_client.py:1030) ⇒ aktivasyonu patlayan
        # bir push (T11 base↔consumption kilidi) SAP'deki inaktif sürümü DEĞİŞTİRDİĞİ hâlde
        # baseline'ı ESKİ kaynakta bırakıyordu → sonraki co-activation'da SAHTE mismatch.
        # `source_uploaded` False ise kayda DOKUNULMAZ: o zaman en son yüklenen kaynak hâlâ
        # eski kayıttır (silmek gerçek bir uyuşmazlığı görünmez yapardı).
        # ⭐ ÖLÇÜLDÜ (2026-09-09): `push_object` HER `Exception`ı yutar ve `result`ı DÖNER
        # (`sap_client.py` dış `except Exception as e: ... return result`). `source_uploaded`
        # upload'ın hemen ardından set edilir ⇒ istisna aktivasyonda düşse bile DOĞRUDUR.
        # Bu yüzden dict dönen yolda BELİRSİZLİK YOKTUR; üçüncü değere gerek yok.
        if isinstance(result, dict):
            if result.get("source_uploaded"):
                _baseline_yaz(client, name, object_type, source,
                              aktive=bool(result.get("activated")))
        elif ok:
            _baseline_yaz(client, name, object_type, source, aktive=True)
        else:
            # Beklenmedik dönüş şekli (dict değil + ok değil) → upload olup olmadığı BİLİNMİYOR.
            _baseline_belirsiz(name, object_type,
                               f"push beklenmedik dönüş şekli ({type(result).__name__})")

        # PULL-BEFORE-EDIT kaydını güncelle: yükleme olduysa canlı kaynak YENİDEN okunur ve o özet
        # yazılır (gönderilen metin DEĞİL — SAP biçimlendirmesi farkı sahte `source_changed_since_pull`
        # üretirdi). Okunamazsa kayıt SİLİNİR (sonraki push yeniden çekme ister: güvenli yön).
        if isinstance(result, dict):
            yuklendi, belirsiz = bool(result.get("source_uploaded")), False
        else:
            yuklendi, belirsiz = bool(ok), not ok
        if yuklendi:
            try:
                sonra = _adt_get_oku(name, object_type, True)
            except Exception as exc:  # noqa: BLE001
                sonra = _err_from_exc(exc)
            if (isinstance(sonra, dict) and sonra.get("ok") is True and sonra.get("exists") is True
                    and isinstance(sonra.get("source"), str)):
                h = _pull_state.kaydet(name, object_type, sonra["source"])
                resp["pull_state"] = "guncellendi" if h is None else f"yazilamadi: {h}"
            else:
                _pull_state.sil(name, object_type)
                resp["pull_state"] = ("silindi: yükleme sonrası canlı kaynak okunamadı — sonraki "
                                      "düzenlemeden önce adt_get ile yeniden çek")
        elif belirsiz:
            _pull_state.sil(name, object_type)
            resp["pull_state"] = "silindi: yükleme olup olmadığı belirsiz — adt_get ile yeniden çek"
        else:
            resp["pull_state"] = "degismedi: kaynak yüklenmedi"

        # Sprint 6 T10 — post-push consistency check.
        # Struct/table push'larda placeholder kalma veya version=inactive durumlarını
        # yakalamak için reviewer'ı tekrar (post-mode) çağır.
        # ⛔ Q273: `resp.ok` yalnız BLOCKER (ya da tanınmayan verdict) ile düşer; WARNING
        # görünür kalır (`post_check.unmeasured`/`warnings` + `post_check_notice`).
        if ok and not skip_reviewer:
            obj_lower = (object_type or "").lower()
            post_task = None
            if obj_lower in ("structure", "struct"):
                post_task = "struct_post_create"
            elif obj_lower in ("tabl", "ddls", "dtel", "doma"):
                # Generic active-version check via the same orchestrator.
                post_task = "sap_active_check"
            if post_task:
                post = run_reviewer(post_task, str(tmp_file))
                ozet, dusur = _post_check_ozeti(post)
                resp["post_check"] = ozet
                if dusur:
                    resp["ok"] = False
                elif ozet["verdict"] == "WARNING" or ozet.get("unmeasured"):
                    resp["post_check_notice"] = _post_check_notice(ozet)
        return resp
    except Exception as exc:
        # Q271 — BELİRSİZLİK SINIRI DAR TUTULDU (ölçüm sonrası daraltıldı, 2026-09-09):
        # istisna `client.push_object`ten KAÇTIYSA SAP'ye ne yüklendiği bilinmiyor → baseline
        # SİLİNMEZ (eşitlik hâlâ yeşil kanıttır) ama BELİRSİZ damgalanır (farktan blocker
        # üretilmez). Çağrıya HİÇ girilmediyse (reviewer / tempfile / `_get_client` hatası)
        # upload da olmamıştır ⇒ eski baseline HÂLÂ GEÇERLİDİR ve dokunulmaz — aksi hâlde
        # gerçek bir uyuşmazlığı görünmez yapan GEREKSİZ bir gevşetme olurdu.
        if push_denendi:
            _baseline_belirsiz(name, object_type,
                               f"push çağrısı istisna ile kaçtı ({type(exc).__name__})")
            _pull_state.sil(name, object_type)   # SAP'ye ne yüklendiği bilinmiyor → yeniden çekme şart
        hata = _err_from_exc(exc)
        if silme_uyarisi and isinstance(hata, dict):
            hata.update(silme_uyarisi)
        return hata
    finally:
        if tmp_file and tmp_file.exists():
            try:
                tmp_file.unlink()
            except OSError:
                pass


# =============================================================================
# adt_activate
# =============================================================================

@profil_tool()
def adt_delete(
    name: str,
    object_type: str,
    transport: str | None = None,
) -> dict:
    """Delete a Z/Y namespace SAP object.

    Hard guardrail (ADR 0005 §A): only Z*/Y* objects deletable. Standard SAP
    objects → reject. Caller bears responsibility for downstream impact;
    where-used analysis is the caller's job (not done here).

    Args:
        name: Object name (must be Z*/Y*).
        object_type: 'class', 'doma', 'dtel', 'tabl', 'ddls', 'msag', 'prog', ...
        transport: Modifiable transport for the delete entry.

    Returns:
        {ok, name, type, deleted, client_log}
    """
    try:
        require_writable_tier(get_active_tier(), what=f"{object_type} delete")
        reject_standard_delete(name, object_type)
    except GuardrailViolation as gv:
        return gv.as_dict()

    if (object_type or "").lower().strip() in _BDEF_TIPLERI:
        return _bdef_sil(name, transport)

    client = _get_client()
    try:
        with _capture_stdout() as out:
            deleted = client.delete_object(
                object_name=name,
                object_type=object_type,
                transport=transport,
                confirm=False,  # MCP context: no interactive prompt possible
            )
        resp = {
            "ok": bool(deleted),
            "name": name,
            "type": object_type,
            "deleted": bool(deleted),
            "client_log": out.getvalue().strip(),
        }
        # Readback-gate: silme GERÇEKTEN oturdu mu — obje hâlâ varsa BLOCKER.
        # ÜÇ-DEĞERLİ: True/False/None; None ASLA True'ya katlanmaz (bkz. _exists_after_delete).
        if resp["ok"]:
            still, sebep = _exists_after_delete(client, name, object_type)
            if still is True:
                resp["ok"] = False
                resp["deleted"] = False
                resp["delete_verified"] = False
                resp["delete_reason"] = ("Silme sonrası obje HÂLÂ mevcut (readback) — silme "
                                         "oturmadı. Lock/transport/bağımlılık kontrol et, tekrar dene.")
            elif still is False:
                resp["delete_verified"] = True
            else:
                resp["delete_verified"] = None
                resp["delete_reason"] = sebep or (
                    "Silme sonrası varlık readback yapılamadı (soft; manuel teyit).")
        # _LAST_PUSHED temizliği — silinen objenin bayat push kaydı kalmasın (tüm tip-varyantları).
        for _k in [k for k in _LAST_PUSHED if k[0] == name.upper()]:
            _LAST_PUSHED.pop(_k, None)
        return resp
    except Exception as exc:
        return _err_from_exc(exc)


def _bdef_sil(name: str, transport: str | None) -> dict:
    """BDEF silme (v0.5.2, Z35 canlı bulgusu 2026-09-22).

    Genel yol (`SAPClient.delete_object` → `get_object_url`) BDEF'i tip tablosunda bulamaz
    ("Unsupported object type: bdef") → kök DDLS silinse de BDEF artık kalıyordu. Aynı kütüphane
    adımları (kilit → DELETE → finally kilit aç) doğrudan BDEF ucuna uygulanır; canlıda ölçüldü
    (DEV, $TMP: silme başarılı, TADIR satırı düştü). Yokluk readback'i BDEF kaynak ucundan (404 = kanıt).
    """
    from urllib.parse import quote
    client = _get_client()
    adt = getattr(client, "adt_client", None) or client
    url = "/sap/bc/adt/bo/behaviordefinitions/" + quote(name.lower(), safe="")
    kilit = None
    try:
        with _capture_stdout() as out:
            try:
                kilit = adt.lock_object(url, transport=transport)
                if kilit == "NO_LOCK_SUPPORT":
                    kilit = None
                adt.delete_object(url, kilit or "NO_LOCK_SUPPORT", transport=transport)
            finally:
                if kilit:
                    try:
                        adt.unlock_object(url, kilit)
                    except Exception as uexc:  # noqa: BLE001 — silinen objenin kilidi açılamayabilir
                        print(f"     [WARNING] Unlock failed: {uexc}")
    except Exception as exc:
        return _err_from_exc(exc)
    resp = {"ok": True, "name": name, "type": "bdef", "deleted": True,
            "client_log": out.getvalue().strip()}
    geri = _read_source_object(name, "bo/behaviordefinitions", "bdef")
    # `_read_source_object`: var → {ok:True, exists:True} · kanıtlı yok → {ok:True, exists:False} (404 imzası).
    if geri.get("ok") is True and geri.get("exists") is False:
        resp["delete_verified"] = True
    elif geri.get("ok") is True:
        resp.update(ok=False, deleted=False, delete_verified=False,
                    delete_reason="Silme sonrası BDEF HÂLÂ mevcut (readback) — silme oturmadı. "
                                  "Lock/transport/bağımlılık kontrol et, tekrar dene.")
    else:
        resp["delete_verified"] = None
        resp["delete_reason"] = ("Silme sonrası BDEF readback KOŞAMADI "
                                 f"({geri.get('error') or 'bilinmiyor'}) — 'silindi' kanıtı DEĞİLDİR; elle teyit et.")
    for _k in [k for k in _LAST_PUSHED if k[0] == name.upper()]:
        _LAST_PUSHED.pop(_k, None)
    return resp


# Aktivasyon obje URI segmentleri (tip → ADT path; /source/main YOK). Çoklu-obje atomik
# aktivasyon (interface DDLS + BDEF + class aynı /activation POST'ta — ADIM-1 tipi RAP
# zincirleri) + activate_object'in bilmediği tipler (bdef/srvd) için.
_ACTIVATION_URI_SEG = {
    "ddls": "ddic/ddl/sources", "cds": "ddic/ddl/sources", "cdsview": "ddic/ddl/sources",
    "bdef": "bo/behaviordefinitions", "behaviordefinition": "bo/behaviordefinitions",
    "class": "oo/classes", "clas": "oo/classes",
    "srvd": "ddic/srvd/sources", "servicedefinition": "ddic/srvd/sources",
    "dcl": "acm/dcl/sources", "dcls": "acm/dcl/sources", "accesscontrol": "acm/dcl/sources",
    "ddlx": "ddic/ddlx/sources", "metadataextension": "ddic/ddlx/sources",
    "domain": "ddic/domains", "doma": "ddic/domains",
    "dataelement": "ddic/dataelements", "dtel": "ddic/dataelements",
    "table": "ddic/tables", "tabl": "ddic/tables", "structure": "ddic/structures",
    "program": "programs/programs", "prog": "programs/programs",
    # 2026-08-01 (T1.6 pilot bulgusu): klasik program+include co-activation'ı için include
    # tipi eksikti -> adt_activate(also=[{object_type:"include"}]) unsupported_type veriyordu.
    "include": "programs/includes", "prog/i": "programs/includes",
    "srvb": "businessservices/bindings", "servicebinding": "businessservices/bindings",
    # 2026-08-22 (kayit #70): `fugr` bu sozlukte HIC YOKTU -> `_activation_uri` None
    # donuyor, `also=[{object_type:"fugr"}]` atomik co-activate'i `unsupported_type` ile
    # reddediliyordu. Segment repoda zaten kanitli tek kaynakta: `scripts/object_types.py`
    # FUGR `url_path='functions/groups'` (kardes tuketici: `query.py` iki yerde ayni esleme).
    "fugr": "functions/groups", "functiongroup": "functions/groups",
}


# ⛔ AKTIVASYON READBACK'i (kayit #70, olculdu 2026-08-22 bir FUGR uzerinde; ornek ad
# `ZDEMO1_FG_ORNEK`):
#   `adt_activate(object_type='fugr')`      -> **`activated: true`**
#   ayni anda HAM `POST /activation`        -> **`activationExecuted="false"`**
#   `adt_inactive_objects`                  -> ayni FUGR (FUGR/F) **LISTEDE**
#   bagimsiz ucuncu kanit (ATC)             -> "The program SAPL<FUGR> contains
#                                              **inactive parts**"
# ⇒ SINIF: sessiz sahte-yesil. Arac "aktive ettim" diyor, obje INAKTIF kaliyor; yalniz
# `adt_activate` donusune bakan bir ajan YANLIS sonuca varir.
#
# ⚠ BUGUNKU BOSLUK YAPISALDIR: klasik yolun TEK dogrulamasi `_content_readback`'tir, o da
# (a) yalniz `_SOURCE_BASED_TYPES` icin ve (b) yalniz bu seansta `adt_push_source` kaydi
# varsa kosar. `fugr` (ve dtel/doma/tabl gibi XML-DDIC tipleri, ayrica salt re-activate)
# ⇒ **HIC dogrulanmiyor**. Bu sonda o bosluga, kaydin KENDI kullandigi bagimsiz sinyalle
# (aktive-bekleyen worklist'i) cevap verir.
#
# ⛔ NEDEN `activate_and_verify` YOLUNA (srvb gibi) TASINMADI: `srvb`'de gerekce
# "`activate_object` bu tipi DESTEKLEMIYOR"du. `fugr` DESTEKLENIYOR ve klasik yol FUGR icin
# GEREKLI olan iki-fazli pre-audit + `ioc:inactiveObjects` alt-obje toplamasini yapiyor
# (FUGR'un FF/I alt-objeleri tam da bu yolla aktive ediliyor). Tipi ref-yoluna tasimak bu
# mekanizmayi KAYBETTIRIR ve CALISAN aktivasyonlari bozabilir -> SAP'siz olculemez.
# ⇒ Dar ve olculebilir olan secildi: klasik yol KORUNDU, ustune BAGIMSIZ readback konuldu.
_AKTIVASYON_WORKLIST_UC = "/sap/bc/adt/activation/inactiveobjects"


def _aktivasyon_readback(client, adlar: list) -> tuple[Optional[bool], str, list]:
    """Aktivasyondan SONRA obje(ler) hala 'aktive bekliyor' listesinde mi?

    Uc-degerli: `True` (aktivasyon DOGRULANDI — listede yok) · `False` (hala INAKTIF) ·
    `None` (**OLCULEMEDI**; "dogrulandi" DEGIL — `sebep` alanina bak).
    ⛔ Olcum kurulamamasini "temiz" sayma: bu kaydin kok sinifi tam olarak odur.
    """
    # Eslestirme + ayristirma TEK KAYNAKTA: `sap_adt_lib.aktivasyon_worklist_sondasi`
    # (URI sinirli onek / parentUri / ad+tip). Eskiden burada yalniz AD eslemesi vardi ve
    # `ioc:inactiveObjects` OLMAYAN 200 govde "aktive bekleyen yok" sayilabiliyordu.
    # `adlar`: ad dizgesi ya da {name, uri, type} sozlugu.
    hedef: list = []
    for a in adlar or []:
        if isinstance(a, dict):
            if (a.get("name") or "").strip() or (a.get("uri") or "").strip():
                hedef.append(a)
        elif (a or "").strip():
            hedef.append({"name": a.strip()})
    if not hedef:
        return None, "unavailable:isim_yok", []
    try:
        from sap_adt_lib import aktivasyon_worklist_sondasi  # type: ignore
        adt = getattr(client, "adt_client", None) or client
        with _capture_stdout():
            ok, sebep, kalan = aktivasyon_worklist_sondasi(adt, hedef)
        hala: list = []
        for k in kalan:
            kayit = {"name": (k.get("name") or "").strip().upper(), "type": k.get("type") or "",
                     "uri": k.get("uri") or ""}
            if (kayit["name"], kayit["type"]) not in [(h["name"], h["type"]) for h in hala]:
                hala.append(kayit)
        return ok, sebep, hala
    except Exception as exc:  # noqa: BLE001 — teshis bozulmasin
        return None, "unavailable:%s" % type(exc).__name__, []


_KILIT_OBJE_TIPLERI = frozenset({"enqu", "lock", "lockobject", "lockobjects"})


def _kilit_objesi_aktive_et(client, name: str, object_type: str) -> dict:
    """ENQU/DL tek-obje aktivasyonu (aXet 2026-09-13).

    Reçete: kaynak çekirdek `playbook/adt-lock-objects.md:114-134` — `POST /sap/bc/adt/activation?method=activate
    &preauditRequested=true`, Content-Type `application/xml`, gövde `objectReference` uri
    `/sap/bc/adt/ddic/lockobjects/sources/<ad>` + `adtcore:type="ENQU/DL"`. Hüküm HTTP kodundan değil
    gövdeden: `rap_service._activation_failures` (tek kaynak `sap_adt_lib.aktivasyon_govde_hukmu`).
    Gövde hüküm taşımıyorsa (yalnız generation / bayraksız) karar `rap_service._hukmu_kesinlestir`
    ile BAĞIMSIZ worklist sondasınındır; sonda ölçemezse başarı SAYILMAZ. Ardından bağımsız
    worklist readback'i (`_aktivasyon_readback`).
    """
    from urllib.parse import quote
    try:
        from rap_service import _activation_failures, _hukmu_kesinlestir  # type: ignore
        adt = getattr(client, "adt_client", None) or client
        kilit_uri = "/sap/bc/adt/ddic/lockobjects/sources/%s" % quote(name.lower(), safe="")
        hedef = {"uri": kilit_uri, "name": name.upper(), "type": "ENQU/DL"}
        govde = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                 '<adtcore:objectReferences xmlns:adtcore="http://www.sap.com/adt/core">\n'
                 '  <adtcore:objectReference adtcore:uri="%s"\n'
                 '                            adtcore:type="ENQU/DL"\n'
                 '                            adtcore:name="%s"/>\n'
                 '</adtcore:objectReferences>') % (kilit_uri, name.upper())
        with _capture_stdout() as out:
            r = adt._request_with_csrf_retry(
                "post", adt.url + "/sap/bc/adt/activation", headers={"Content-Type": "application/xml"},
                params={"method": "activate", "preauditRequested": "true"}, data=govde.encode("utf-8"))
            durum = int(getattr(r, "status_code", 0) or 0)
            executed, errs = _activation_failures(getattr(r, "text", "") or "")
            govde_hukmu = executed
            if durum in (200, 202):
                executed, errs = _hukmu_kesinlestir(adt, executed, errs, [hedef], name.upper())
        resp = {"ok": False, "name": name, "type": object_type, "activated": False, "http_status": durum,
                "activation_executed": govde_hukmu, "client_log": out.getvalue().strip()}
        if durum not in (200, 202) or not executed or errs:
            resp.update(error="activation_failed", errors=list(errs)[:10],
                        message=("Kilit objesi aktivasyonu başarısız (HTTP %d, gövde activationExecuted=%s, "
                                 "kesin hüküm=%s)." % (durum, govde_hukmu, executed)))
            return resp
        resp.update(ok=True, activated=True)
        akt_ok, akt_sonda, akt_kalan = _aktivasyon_readback(client, [hedef])
        resp["activation_verified"] = akt_ok
        resp["activation_probe"] = akt_sonda
        if akt_ok is False:
            resp.update(ok=False, activated=False, error="activation_not_executed", still_inactive=akt_kalan,
                        message="SAHTE-OK: obje hâlâ aktive-bekleyen worklist'inde.")
        elif akt_ok is None:
            resp["warning"] = "Aktivasyon worklist ile DOĞRULANAMADI (%s)." % akt_sonda
        resp["notice"] = ("ENQUEUE_/DEQUEUE_ FM'leri aktivasyonla üretilir (reçete §29.7); üretildikleri "
                          "bu araçla ÖLÇÜLMEDİ — adt_search_objects ile doğrula.")
        return resp
    except Exception as exc:  # noqa: BLE001
        return _err_from_exc(exc)


def _activation_uri(name: str, object_type: str):
    from urllib.parse import quote
    seg = _ACTIVATION_URI_SEG.get((object_type or "").lower().strip())
    if not seg:
        return None
    return f"/sap/bc/adt/{seg}/{quote(name.lower(), safe='')}"


@profil_tool()
def adt_activate(name: str, object_type: str = "class", also: list | None = None) -> dict:
    """Activate an SAP object — single, OR multiple objects ATOMICALLY (one /activation POST).

    Atomik çoklu-obje aktivasyon (RAP zincirleri): birbirine bağımlı objeler (ör. interface
    DDLS + onun BDEF'i + behavior class) AYNI istekte aktive edilmeli → `also` ile ek objeleri
    ver, hepsi tek POST'ta aktive + doğrulanır (activationExecuted + type=E parse; sahte-OK
    imkansız). bdef/srvd gibi activate_object'in desteklemediği tipler de bu yolda çalışır.

    Args:
        name: Birincil obje adı (Z*/Y*).
        object_type: 'class', 'ddls', 'bdef', 'srvd', 'tabl', ...
        also: Atomik co-activate ek objeler: [{"name": "...", "object_type": "..."}, ...].
              None/boş → tek-obje aktivasyon (klasik yol).

    Returns:
        {ok, name, type, activated, errors?, warnings?, refs?, client_log}

    ⛔ **KLASIK YOLDA `ok` = `activated`.** Alt katmanin hukmu TEK KAYNAKTAN gelir
    (`sap_adt_lib.aktivasyon_govde_hukmu` + govde hukum tasimiyorsa worklist sondasi).

    ⛔ **KLASIK YOLDA AKTIVASYON READBACK'i** (kayit #70, olculmus sahte-OK vakasi — `fugr`).
    Obje **bagimsiz olarak** aktive-bekleyen worklist'inde (`/activation/inactiveobjects`)
    aranir; eslestirme URI siniri + ad+tip ile (`sap_adt_lib.aktivasyon_worklist_kalan`):
      • `activated: true` + `activation_verified: true`  → obje listede YOK, dogrulandi.
      • `activated: true` + `activation_verified: false` → obje HALA listede ⇒ **SAHTE-OK**:
        `ok=false`, `activated=false`, `error="activation_not_executed"`, `still_inactive=[...]`.
      • `activation_verified: null`  → sonda kosamadi ⇒ iddia **KANITLANMADI** (`warning`).
        Bu "dogrulandi" DEGILDIR.
      • `activated: false` → sonda YINE kosar ama YALNIZ BILGI tasir (`still_inactive`,
        `activation_probe`); `ok` false KALIR. Liste temizse `probe_note`: obje aktivasyondan
        ONCE listede degilse "temiz" ayirt edici DEGILDIR. SAP'ye ulasilamadiysa (`unreachable`)
        sonda kosmaz.
    ⚠ `also=` (atomik cok-obje) ve `srvb` yollari zaten `activate_and_verify` ile
    `activationExecuted` + `type=E` parse eder; readback onlarda TEKRARLANMAZ.
    """
    try:
        require_writable_tier(get_active_tier(), what=f"{object_type} activate")
        require_customer_namespace(name, what=object_type, object_type=object_type)
        for o in (also or []):
            require_customer_namespace(o.get("name", ""), what=o.get("object_type", "object"))
    except GuardrailViolation as gv:
        return gv.as_dict()

    client = _get_client()

    # --- ATOMİK ÇOKLU-OBJE AKTİVASYON (also verildiyse) ---
    if also:
        refs = []
        pairs = [(name, object_type)] + [(o.get("name"), o.get("object_type")) for o in also]
        for n, t in pairs:
            uri = _activation_uri(n, t)
            if not uri:
                return {"ok": False, "error": "unsupported_type",
                        "message": f"Aktivasyon URI çözülemedi: {n} (type={t}). "
                                   f"Desteklenen tipler: {sorted(set(_ACTIVATION_URI_SEG))}"}
            refs.append((uri, n))
        try:
            from rap_service import csrf, activate_and_verify  # type: ignore
            adt = getattr(client, "adt_client", None) or client
            with _capture_stdout() as out:
                tok = csrf(adt)
                activate_and_verify(adt, tok, refs)   # activationExecuted!=true / type=E → raises
            resp = {
                "ok": True,
                "name": name,
                "type": object_type,
                "activated": True,
                "refs": [n for _, n in refs],
                "client_log": out.getvalue().strip(),
            }
            # Readback-gate: her aktive edilen source-based obje için içerik doğrula.
            rb_all = {}
            for n, t in pairs:
                rb = _content_readback(client, n, t)
                if rb:
                    rb_all[n.upper()] = rb
                    if rb.get("content_verified") is False:
                        resp["ok"] = False
            if rb_all:
                resp["content_readback"] = rb_all
            return resp
        except Exception as exc:
            return _err_from_exc(exc)

    # --- TEK-OBJE AKTİVASYON ---
    # srvb gibi activate_object'in DESTEKLEMEDİĞİ tipler: kanonik /activation POST
    # (activation-ref, segment _ACTIVATION_URI_SEG'den) yoluyla aktive et — activationExecuted
    # + type=E parse → sahte-OK imkansız (gateway'in elle REST workaround'unu typed yapar,
    # ders 2026-06-22 SRVB). Çalışan/source-tabanlı tipler (class/tabl/...) klasik
    # activate_object yolunda kalır (içerik readback-gate'i korunur, regresyon yok).
    if (object_type or "").lower().strip() in _KILIT_OBJE_TIPLERI:
        return _kilit_objesi_aktive_et(client, name, object_type)
    _ref_only = {"srvb", "servicebinding"}
    if (object_type or "").lower().strip() in _ref_only:
        uri = _activation_uri(name, object_type)
        try:
            from rap_service import csrf, activate_and_verify  # type: ignore
            adt = getattr(client, "adt_client", None) or client
            with _capture_stdout() as out:
                tok = csrf(adt)
                activate_and_verify(adt, tok, [(uri, name)])   # !=true / type=E → raises
            return {
                "ok": True, "name": name, "type": object_type, "activated": True,
                "refs": [name], "client_log": out.getvalue().strip(),
                "note": "activation-ref yolu (activate_object bu tipi desteklemiyor). "
                        "OData $metadata tazelemek gerekiyorsa ayrıca adt_publish_service çağır.",
            }
        except Exception as exc:
            return _err_from_exc(exc)

    try:
        with _capture_stdout() as out:
            activated = client.activate_object(name, object_type=object_type)
        log_text = out.getvalue()

        # Parse a few signals from client log (best-effort; structured result is already in 'activated')
        errors: list[str] = []
        warnings: list[str] = []
        for line in log_text.splitlines():
            if line.startswith("  - ") and "warning" in log_text.lower():
                warnings.append(line[4:].strip())

        resp = {
            "ok": True,
            "name": name,
            "type": object_type,
            "activated": bool(activated),
            "client_log": log_text.strip(),
        }
        # aXet DÜZELTMESİ (ölçüldü, çevrimdışı test 6h): alt katman aktivasyon hatasını YUTUP
        # False döndürüyor (ör. bağlantı kurulamadı) ama bu dal `ok: true` + `activated: false`
        # dönüyordu ⇒ CLI başarısız bir yazmayı exit 0 ile raporlardı. Artık `activated` False ise
        # `ok` False'tur; sebep log'dan sınıflanır (ulaşılamadı ≠ aktivasyon reddedildi).
        akt_hedef = {"name": name, "uri": _activation_uri(name, object_type) or ""}
        try:
            from object_types import get_adt_type  # type: ignore
            akt_hedef["type"] = get_adt_type(object_type) or ""
        except Exception:  # noqa: BLE001 — tip yoksa URI/ad eslemesi yeter
            akt_hedef["type"] = ""
        if not activated:
            resp["ok"] = False
            if _bos_sonuc_sinifi(log_text) == "ulasilamadi":
                resp["error"] = "unreachable"
                resp["message"] = ("SAP'ye ULAŞILAMADI — aktivasyon YAPILMADI. Bağlantıyı kontrol et; "
                                   "bu sonuç 'aktivasyon hatası' da değildir.")
                return resp
            resp["error"] = "activation_failed"
            resp["message"] = ("Aktivasyon BAŞARISIZ ya da DOĞRULANAMADI (alt katman hükmü; SAP mesajları "
                               "client_log'da). Zincirin devamına (publish / bağımlı obje / test) GEÇME.")
            # Başarısız çağrı etkisiz çağrı DEMEK DEĞİL: bir aktivasyon "başarısız" dönerken bir
            # alt objeyi düşürmüş olabilir. Sonda burada YALNIZ BİLGİ taşır (`still_inactive`);
            # `ok`'u ASLA True'ya çevirmez. SAP'ye ulaşılamadıysa sonda koşmaz (ölçemez).
            akt_ok, akt_sonda, akt_kalan = _aktivasyon_readback(client, [akt_hedef])
            resp["activation_probe"] = akt_sonda
            resp["still_inactive"] = akt_kalan if akt_ok is not None else None
            if akt_ok is True:
                resp["probe_note"] = (
                    "Obje aktive-bekleyen listesinde YOK. ⚠ Bu ayırt edici DEĞİL: obje "
                    "aktivasyondan önce listede değilse de aynı sonuç çıkar. `ok` false KALIR.")
            return resp

        # Readback-gate: aktive edilen source-based obje için AKTİF source'u push edilenle
        # karşılaştır. Fark → yazım tam oturmadı → BLOCKER (ok=False). XML-DDIC/kayıtsız → no-op.
        rb = _content_readback(client, name, object_type)
        if rb:
            resp.update(rb)
            if rb.get("content_verified") is False:
                resp["ok"] = False

        # ⛔ AKTIVASYON READBACK'i (kayit #70 — sahte-OK). `_content_readback` KAYNAK
        # esitligini olcer; bu sonda AKTIVASYON DURUMUNU olcer ve kapsami farklidir
        # (fugr/XML-DDIC + salt re-activate icin TEK dogrulama). Gerekce: `_aktivasyon_readback`.
        # `activated` FALSE iken sonda yukaridaki erken donuste YALNIZ BILGI icin kosar.
        if resp.get("activated") is True:
            akt_ok, akt_sonda, akt_kalan = _aktivasyon_readback(client, [akt_hedef])
            resp["activation_verified"] = akt_ok
            resp["activation_probe"] = akt_sonda
            if akt_ok is False:
                # SAHTE-OK yakalandi: obje HALA aktive-bekleyen worklist'inde.
                resp["ok"] = False
                resp["activated"] = False
                resp["still_inactive"] = akt_kalan
                resp["error"] = "activation_not_executed"
                resp["message"] = (
                    "⛔ SAHTE-OK YAKALANDI: alt katman 'aktive edildi' dedi ama obje HALA "
                    "aktive-bekleyen worklist'inde (%s). Aktivasyon GERCEKLESMEDI — bu "
                    "sonuca dayanip zincirin devamina (publish / bagimli obje / test) GECME. "
                    "Ham yaniti gor: POST /sap/bc/adt/activation -> `activationExecuted`."
                    % ", ".join("%s (%s)" % (h["name"], h["type"]) for h in akt_kalan)
                )
            elif akt_ok is None:
                resp["warning"] = (
                    "Aktivasyon DOGRULANAMADI (sonda: %s) — 'aktive edildi' iddiasi bu "
                    "cagride KANITLANMADI. Kritik zincirde `adt_inactive_objects` ile elle olc."
                    % akt_sonda
                )

        # ADR 0016 REVİZE: post-write REPO SYNC (M2) KALDIRILDI — gereksiz (push edince repo
        # zaten ≈ canlı; tazelik bir sonraki edit'te pull-before-edit hook ile sağlanır).
        return resp
    except Exception as exc:
        return _err_from_exc(exc)


# ── Q278 (2026-09-13) — PUBLISH HÜKMÜ GÖVDEDEN KURULUR, HTTP KODUNDAN DEĞİL ─────────────
# Q292 (2026-09-13): hüküm TEK KAYNAĞA taşındı → `scripts/create_rap_service.py::publish_hukmu`
# (CLI `--step publish` birebir aynı kusuru taşıyordu; gerekçe + karar orada). Buradaki ad
# yalnız ince sarmalayıcıdır — modül her çağrıda okunur (fixture mutasyonu tek noktadan).
def _publish_hukmu(status_code, body: str) -> dict:
    import rap_service as _crs  # type: ignore
    return _crs.publish_hukmu(status_code, body)


def _master_language() -> Optional[str]:
    """sap-project.json → master_language (çözülemezse None)."""
    try:
        from sapadt.project import load_sap_project
        cfg, _hata = load_sap_project()
        return (cfg or {}).get("master_language")
    except Exception:  # noqa: BLE001
        return None


@profil_tool()
def adt_publish_service(name: str, version: str = "0001") -> dict:
    """(Re)publish an OData V2 service binding (SRVB) — refreshes the OData $metadata.

    SRVD expose / underlying CDS değişince, yayınlanmış OData metadata'sının (entity set +
    property) yeni hâli yansıtması için SRVB republish gerekir. Bu, raw `/businessservices/
    odatav2/publishjobs` POST'unun TYPED, guardrailed muadili (raw-Bash classifier bloğunu
    önler). Sonuç doğrulaması = `GET /sap/opu/odata/sap/<NAME>/$metadata` (çağıran yapar).

    Args:
        name: Service binding (SRVB) adı, ör. ZDEMO1_UI_BOOKING_O2.
        version: Servis sürümü (default '0001').

    ⛔ Q278: `ok`/`published` HTTP kodundan DEĞİL gövdedeki SAP `SEVERITY`'sinden kurulur.
    `published` ÜÇ DEĞERLİDİR: True (SEVERITY=OK) · False (HTTP hata ya da SEVERITY=ERROR) ·
    None (gövde hüküm taşımıyor / tanınmayan değer ⇒ ÖLÇÜLEMEDİ, `ok` yine False).

    Returns:
        {ok, name, status_code, published, severity, sap_message, publish_probe,
         [publish_notice], body, client_log}
    """
    try:
        require_writable_tier(get_active_tier(), what="service publish")
        require_customer_namespace(name, what="service binding")
    except GuardrailViolation as gv:
        return gv.as_dict()

    client = _get_client()
    try:
        from rap_service import csrf, publish_xml, PUBLISH_V2  # type: ignore
        adt = getattr(client, "adt_client", None) or client
        with _capture_stdout() as out:
            tok = csrf(adt)
            r = adt.session.post(
                adt.url + PUBLISH_V2,
                params={"servicename": name, "serviceversion": version},
                headers={"X-CSRF-Token": tok, "Content-Type": "application/xml",
                         "Accept": "application/xml, application/vnd.sap.as+xml;charset=UTF-8;"
                                   "dataname=com.sap.adt.StatusMessage",
                         # aXet: client bağlantıdan; dil = sap-project.json master_language
                         # (gate, bağlantı dili ≠ master_language ise bu çağrıyı zaten reddeder).
                         "sap-client": str(adt.client or ""),
                         "sap-language": _master_language() or str(adt.language or "")},
                data=publish_xml(name).encode("utf-8"), verify=adt.session.verify, timeout=120,
            )
        govde = r.text or ""
        hukum = _publish_hukmu(r.status_code, govde)
        resp = {
            "ok": hukum["ok"],
            "name": name,
            "status_code": r.status_code,
            "published": hukum["published"],
            "severity": hukum["severity"],
            "sap_message": hukum["sap_message"],
            "publish_probe": hukum["publish_probe"],
            "body": govde[:900],
            "client_log": out.getvalue().strip(),
        }
        if hukum.get("publish_notice"):
            resp["publish_notice"] = hukum["publish_notice"]
        return resp
    except Exception as exc:
        return _err_from_exc(exc)


# =============================================================================
# adt_classrun  (gap-analysis C1 — ABAP çalıştırma kanalı)
# =============================================================================

@profil_tool()
def adt_classrun(name: str) -> dict:
    """Bir IF_OO_ADT_CLASSRUN sınıfını çalıştır (ADT classrun, F9-run muadili).

    ADT-only ABAP execute kanalı. RFC FM (RPY_DYNPRO_INSERT/RS_CUA_*) çağıran generator
    sınıflarını çalıştırmak için (ekran/GUI status üretimi — C1). Kod ÇALIŞTIRIR (yazma
    yapabilir) → ADR 0010 tier guard: yalnızca DEV.

    ⛔ **PUSH+ACTIVATE SONRASI ÇIKTI BAYAT OLABİLİR — TEK BAŞINA KANIT DEĞİLDİR.**
    Ölçülmüş vaka (2026-08-19, `ZCL_DEMO0_GET_IDOCDATA`): sınıfa `c_docnum = '<IDoc no>'`
    sabiti eklenip push+activate edildi; `adt_classrun` **HTTP 200 + dolu, akla yatkın**
    çıktı verdi — ama **eski kodun** çıktısı (sabit sanki BOŞ). **İkinci çağrı da aynı bayat
    sonucu** verdi ⇒ tek seferlik aksaklık DEĞİL, tekrarlanabilir. Kaynak tarafı dört
    bağımsız okumayla temiz ölçüldü (`source/main` default = `?version=active` =
    `?version=inactive`, aynı sha, sabit VAR; `adt_inactive_objects` count 0).
    **Kök sebep kaynakta değil, ÇALIŞTIRAN OTURUMDA:** MCP sunucusu tek uzun-ömürlü ABAP
    oturumu kullanır (`sap-contextid` çerezi) ve **sınıf load'u o oturumda bayat kalır;
    aktivasyon onu tazelemez.** Kanıt: TAZE oturumdan (yeni logon, kendi süreç,
    `SAPClient().run_classrun(...)`) aynı sınıf DOĞRU çalıştı.
    ⚠ Bu, *"araç başarısız"* değil **"araç başarılı görünerek yanlış söylüyor"** sınıfıdır —
    `adt_transport_list` sahte-sıfırı ve `adt_post_shell` sahte-400'ü ile aynı raf.

    aXet NOTU: bu vaka uzun-ömürlü MCP sürecine özgüdür. `sap_adt_cli.py` her çağrıda YENİ
    süreç + yeni HTTP oturumu açar (DOĞRULANMADI: canlı sistemde ölçülmedi). Yine de
    ⛔ `SAPClient`'ı CLI dışından doğrudan çağırma — yazma kapısını atlar (IMPLEMENTATION.md).

    ✅ **DOĞRU YÖNTEM:** **Çıktıyı kaynakla ÇAPRAZ KONTROL et** — çıktıda yeni koda ÖZGÜ bir
    imza (yeni başlık satırı, yeni sabitin değeri) görünüyor mu? Görünmüyorsa sonucu
    "davranış yanlış" diye RAPORLAMA; önce bayatlığı ele.

    ⚠ Bu tool dönüşünde bayatlık ölçmez (`session_age`/`context_reused` alanı YOK).
    Yani aşağıdaki `Returns` sözleşmesinde **tazelik kanıtı yoktur**; kanıtı çağıran üretir.

    Args:
        name: Sınıf (Z*/Y*, if_oo_adt_classrun~main implement etmeli).

    Returns:
        {ok, class, status, output} — output = out->write konsol çıktısı.
        ⚠ `ok: true` çıktının GÜNCEL olduğunu KANITLAMAZ (yukarıdaki bayatlık şerhi).
    """
    try:
        require_writable_tier(get_active_tier(), what="classrun execute")
        require_customer_namespace(name, what="class")
    except GuardrailViolation as gv:
        return gv.as_dict()

    client = _get_client()
    try:
        with _capture_stdout() as out:
            res = client.run_classrun(name)
        if isinstance(res, dict):
            res.setdefault("client_log", out.getvalue().strip())
        return res
    except Exception as exc:
        return _err_from_exc(exc)
