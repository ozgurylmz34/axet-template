# -*- coding: utf-8 -*-
"""Aktivasyon / publish yardımcıları — kaynak çekirdekteki `create_rap_service.py`'den KESİT.

Yalnız araç katmanının (tools/atom.py, tools/query.py) kullandığı fonksiyonlar taşındı:
`csrf`, `activate_and_verify` (+ `_activation_failures`, `_aktivasyon_yaniti_ok`),
`publish_xml`, `PUBLISH_V2`, `publish_hukmu` (+ gövde okuyucu).

Bilinçli olarak TAŞINMAYANLAR: `step_*` adımları ve modül sabitleri (paket/servis/CDS adları
belirli bir müşteri projesine gömülüydü) ve `__main__` CLI'si. aXet'te SRVD/SRVB/BDEF yaratma
akışı bu CLI'nin kapsamında değildir.

DEĞİŞİKLİKLER (kaynağa göre):
  • `csrf`: `sap-client` sabit "100" ve `sap-language` sabit "TR" yerine bağlantının kendi
    client/language değeri (yazma çağrılarında gate, bağlantı dili == master_language'i zorlar).
  • `csrf`: token'ın ilk 20 karakterini stdout'a basıyordu (araçlar stdout'u `client_log`
    alanına topluyor ⇒ token çıktıya sızıyordu) → maskelendi.
  • `verify=False` → `verify=client.session.verify` (ADT_SAP_SSL_VERIFY tek yerden geçerli;
    varsayılan false olduğundan varsayılan davranış AYNI).
"""
from __future__ import annotations

import re

from sap_adt_lib import (SAPADTError, aktivasyon_govde_hukmu, aktivasyon_hedefleri_govdeden,
                         aktivasyon_worklist_sondasi)

SRVB_BASE = "/sap/bc/adt/businessservices/bindings"
PUBLISH_V2 = "/sap/bc/adt/businessservices/odatav2/publishjobs"
ACTIVATION = "/sap/bc/adt/activation"


def csrf(client):
    """CSRF token al. Alınamazsa SAPADTError (SystemExit DEĞİL — araçlar `except Exception`
    ile yapılandırılmış `{ok:false}` döndürebilsin)."""
    client._invalidate_csrf_cache()
    r = client.session.get(
        client.url + "/sap/bc/adt/discovery",
        params={"sap-client": str(client.client or ""), "sap-language": str(client.language or "")},
        headers={"X-CSRF-Token": "Fetch"}, verify=client.session.verify, timeout=30,
    )
    tok = r.headers.get("X-CSRF-Token", "")
    if not tok:
        raise SAPADTError(
            "CSRF token alınamadı (discovery yanıtında X-CSRF-Token yok) — aktivasyon/"
            "publish/unit-run ÇALIŞTIRILAMADI. Bu 'başarısız oldu' değil 'hiç koşmadı'dır.",
            status_code=getattr(r, "status_code", None),
            response_text=(getattr(r, "text", "") or "")[:300],
        )
    print("[OK] CSRF token alındı (değer maskelendi)")
    return tok


def publish_xml(binding):
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<adtcore:objectReferences xmlns:adtcore="http://www.sap.com/adt/core">\n'
        f'  <adtcore:objectReference adtcore:uri="{SRVB_BASE}/{binding.lower()}"\n'
        f'      adtcore:name="{binding.upper()}"/>\n'
        '</adtcore:objectReferences>'
    )


def _activation_failures(resp_text):
    """Aktivasyon yanıtından gerçek durum. HTTP 200 KANIT DEĞİL.
    Döner (executed: True|False|None, errors: list[str]). Aktif = executed True ve errors boş.

    Hüküm TEK KAYNAKTAN gelir: `sap_adt_lib.aktivasyon_govde_hukmu`. Bu dosya eskiden kendi
    kopya sözleşmesini taşıyordu ve lib'le ayrışmıştı (bayraksız ADT gövdesi burada BAŞARI,
    lib'de BAŞARISIZ; yalnız-generation gövdesi burada BAŞARISIZ, lib'de BAŞARI).
    `None` = gövde hüküm taşımıyor → çağıran BAĞIMSIZ worklist sondası koşar
    (`_hukmu_kesinlestir`); sonda ölçemezse başarı SAYILMAZ. Korunan kurallar kanonik
    sözleşmenin içindedir: `activationExecuted=false` → başarısız · tanınmayan/boş gövde =
    kanıt yok = başarısız.
    """
    hk = aktivasyon_govde_hukmu(resp_text)
    errs = [(e.get("message") or f"(metinsiz {e.get('type')} mesajı)") for e in hk["errors"]]
    if hk["hukum"] is False and not errs and hk["sebep"] != "activation_not_executed":
        errs = [f"aktivasyon yanıtı kanıt taşımıyor ({hk['sebep']})"]
    return hk["hukum"], errs


def _hukmu_kesinlestir(client, executed, errs, hedefler, etiket):
    """Gövde hüküm TAŞIMIYORSA (executed None, hata yok) BAĞIMSIZ worklist sondası karar verir.

    Döner (executed: bool, errs). Sonda ölçemezse (HTTP hata, istisna, ioc olmayan ya da
    ayrıştırılamayan gövde) `False` + DOĞRULANAMADI mesajı — "ölçemedim" asla "aktive
    edildi"ye katlanmaz. Sınır: obje aktivasyondan ÖNCE worklist'te değilse "listede yok"
    ayırt edici değildir (`sap_adt_lib.aktivasyon_worklist_sondasi`).
    """
    if executed is not None or errs:
        return executed is True, errs
    dog, sonda, kalan = aktivasyon_worklist_sondasi(client, hedefler)
    if dog is True:
        print(f"   [DOGRULANDI] {etiket}: gövde hüküm taşımıyordu; worklist sondası aktif gördü ({sonda})")
        return True, errs
    if dog is False:
        return False, ["aktivasyon GERÇEKLEŞMEDİ — worklist'te hâlâ inaktif: "
                       + ", ".join(f"{k['name']} ({k['type']})" for k in kalan)]
    return False, [f"aktivasyon DOĞRULANAMADI — gövde hüküm taşımıyordu, worklist sondası ölçemedi ({sonda})"]


def _aktivasyon_yaniti_ok(r, client=None, istek_govdesi=None):
    """Aktivasyon POST yanıtının TEK karar noktası (bool döner, exception atmaz).

    Gövde hüküm taşımıyorsa hedefler gönderilen istek gövdesinden türetilir ve worklist
    sondası koşar; `client` ya da hedef yoksa sonda ölçemez ⇒ başarı DEĞİL.
    """
    executed, errs = _activation_failures(r.text)
    if r.status_code in (200, 202):
        executed, errs = _hukmu_kesinlestir(client, executed, errs,
                                            aktivasyon_hedefleri_govdeden(istek_govdesi), "aktivasyon")
    ok = r.status_code in (200, 202) and executed is True and not errs
    if not ok and errs:
        for e in errs[:6]:
            print("   E: " + e)
    return ok


def activate_and_verify(client, tok, refs):
    """Çoklu obje aktivasyonu + ZORUNLU doğrulama. refs: [(uri, NAME), ...].
    HTTP 2xx değil / activationExecuted!="true" / type=E mesajı → RuntimeError."""
    body = ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<adtcore:objectReferences xmlns:adtcore="http://www.sap.com/adt/core">\n'
            + "".join(f'  <adtcore:objectReference adtcore:uri="{u}" adtcore:name="{n.upper()}"/>\n'
                      for u, n in refs)
            + '</adtcore:objectReferences>')
    r = client.session.post(
        client.url + ACTIVATION,
        params={"method": "activate", "preauditRequested": "false"},
        headers={"X-CSRF-Token": tok, "Content-Type": "application/xml", "Accept": "application/xml"},
        data=body.encode("utf-8"), verify=client.session.verify, timeout=120,
    )
    names = ", ".join(n for _, n in refs)
    if not (200 <= int(getattr(r, "status_code", 0) or 0) < 300):
        raise RuntimeError(
            f"AKTİVASYON BAŞARISIZ ({names}): HTTP {getattr(r, 'status_code', '?')} — "
            f"bu bir aktivasyon yanıtı DEĞİL. Gövde: {(r.text or '')[:200]}")
    executed, errs = _activation_failures(r.text)
    govde_hukmu = executed
    executed, errs = _hukmu_kesinlestir(client, executed, errs,
                                        [{"uri": u, "name": n.upper()} for u, n in refs], names)
    if not executed or errs:
        raise RuntimeError(
            f"AKTİVASYON BAŞARISIZ ({names}): activationExecuted={govde_hukmu}; hatalar={errs[:6]}")
    kanit = "activationExecuted=true" if govde_hukmu is True else "worklist sondası"
    print(f"[OK] activate+verify: {names} ({kanit}, hata yok)")
    return True


# ── PUBLISH HÜKMÜ — gövdedeki SAP SEVERITY'sinden kurulur, HTTP kodundan DEĞİL ─────────────
# published üç değerlidir: True (SEVERITY=OK) · False (HTTP hata / SEVERITY=ERROR) ·
# None (gövde hüküm taşımıyor / tanınmayan değer ⇒ ÖLÇÜLEMEDİ; ok yine False).
PUBLISH_SEVERITY_BASARI = frozenset({"OK"})
PUBLISH_SEVERITY_HATA = frozenset({"ERROR"})
_PUBLISH_MESAJ_ETIKETLERI = ("LONG_TEXT", "SHORT_TEXT", "TEXT", "MESSAGE")
_SEVERITY_RE = re.compile(r"<(?:[\w.-]+:)?SEVERITY\b[^>]*>\s*([^<]*?)\s*</", re.IGNORECASE)
_MESAJ_RE = re.compile(r"<(?:[\w.-]+:)?(LONG_TEXT|SHORT_TEXT)\b[^>]*>\s*([^<]*?)\s*</",
                       re.IGNORECASE)


def _publish_govdesi_oku(body: str) -> tuple:
    """Publish yanıt gövdesinden (SEVERITY değerleri, mesajlar, okuma yolu) çıkar."""
    severities: list = []
    mesajlar: list = []
    metin = body or ""
    if not metin.strip():
        return severities, mesajlar, "bos"
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(metin)
        for el in root.iter():
            yerel = str(el.tag).rsplit("}", 1)[-1].split(":")[-1].upper()
            deger = (el.text or "").strip()
            if yerel == "SEVERITY":
                severities.append(deger.upper())
            elif yerel in _PUBLISH_MESAJ_ETIKETLERI and deger:
                mesajlar.append(deger)
        return severities, mesajlar, "xml"
    except Exception:  # noqa: BLE001 — kırpılmış/XML-olmayan gövde: regex yolu
        severities = [m.group(1).strip().upper() for m in _SEVERITY_RE.finditer(metin)]
        mesajlar = [m.group(2).strip() for m in _MESAJ_RE.finditer(metin) if m.group(2).strip()]
        return severities, mesajlar, "regex"


def publish_hukmu(status_code, body: str) -> dict:
    """Publish sonucunu HTTP kodu + GÖVDEDEKİ SAP hükmünden kur.

    Returns: {ok, published (True|False|None), severity (list), sap_message (str|None),
              body_parse, publish_probe (str)[, publish_notice (str)]}
    """
    severities, mesajlar, yol = _publish_govdesi_oku(body)
    mesaj = " | ".join(dict.fromkeys(mesajlar)) or None
    out: dict = {"severity": severities, "sap_message": mesaj, "body_parse": yol}
    if status_code not in (200, 201, 202):
        out.update(ok=False, published=False, publish_probe="http_hata")
        out["publish_notice"] = "PUBLISH BAŞARISIZ — HTTP %s. %s" % (status_code, mesaj or "")
        return out
    if any(s in PUBLISH_SEVERITY_HATA for s in severities):
        out.update(ok=False, published=False, publish_probe="severity_error")
        out["publish_notice"] = (
            "PUBLISH BAŞARISIZ — HTTP %s ama gövdede SEVERITY=ERROR: %s. HTTP kodu başarı "
            "KANITI DEĞİLDİR. SRVB adını ölç (SRVD adı ≠ SRVB adı olabilir; binding aktif mi?)."
            % (status_code, mesaj or "mesaj yok"))
        return out
    if severities and all(s in PUBLISH_SEVERITY_BASARI for s in severities):
        out.update(ok=True, published=True, publish_probe="severity_ok")
        return out
    if not severities:
        out.update(ok=False, published=None, publish_probe="severity_yok")
        out["publish_notice"] = (
            "PUBLISH ÖLÇÜLEMEDİ — HTTP %s ama gövde SEVERITY taşımıyor (okuma yolu: %s). "
            "Bu 'publish edildi' DEĞİLDİR: `GET /sap/opu/odata/sap/<SRVB>/$metadata` ile teyit et."
            % (status_code, yol))
        return out
    out.update(ok=False, published=None, publish_probe="severity_taninmadi")
    out["publish_notice"] = (
        "PUBLISH ÖLÇÜLEMEDİ — gövdede TANINMAYAN SEVERITY %s (tanınan: OK/ERROR). Başarı "
        "SAYILMADI: `$metadata` ile teyit et. %s" % (severities, mesaj or ""))
    return out
