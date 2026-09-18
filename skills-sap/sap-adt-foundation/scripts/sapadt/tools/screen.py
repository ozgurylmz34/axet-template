# -*- coding: utf-8 -*-
"""adt_screen_generate — klasik Dynpro ekranı + GUI status üreten Z/Y RFC FM'ini SOAP-RFC ile çağırır.

Reçete (kaynak çekirdek, salt-okur):
  • playbook/howto-dynpro-gui-status-generation.md §1 (tam zarf, `/sap/bc/soap/rfc`, `sap-language`,
    TABLES boş etiket tuzağı), §2 (imza), §2.1 (nav_remap doğrulama sinyali), §2.2 (EV_MESSAGE
    KIRPILMAZ), §2.3 (Z/Y guard), §2.4 (EV_RC bantları), §3 (IT_BUTTONS), §4 (IT_FIELDS; §4.4 DOCKING
    şartı), §9 (READ/RECREATE/DELETE), §12 (tuzaklar).
  • playbook/adt-fugr-functions.md §3.1-§3.2 (SOAP-RFC stateless; TABLES istekte yoksa cevapta yok),
    §6 (neden classrun değil: dialog context).

Sabit FM adı GÖMÜLMEZ: `fm_name` zorunlu argümandır ve Z/Y olmalıdır (yazma kapısı + araç guard'ı).
Kimlik bilgisi/host HİÇBİR çıktıya girmez: yanıt `redact.temizle` ile bilinen sırlar + host'tan arındırılır.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from sapadt._app import profil_tool
from sapadt._conn import get_active_tier
from sapadt.guardrails import (
    GuardrailViolation,
    require_customer_namespace,
    require_tr_text,
    require_transport,
    require_writable_tier,
)

SOAP_RFC_UC = "/sap/bc/soap/rfc"
# howto §1 — canlıda koşmuş çağrının satır alanı sırası (TABLES `<item>` sarmalı).
FIELD_ORDER = ("CONT_TYPE", "CONT_NAME", "NAME", "TYPE", "FORMAT", "LENGTH", "VISLENGTH",
               "LINE", "COLUMN", "TEXT", "FROM_DICT", "INPUT_FLD", "OUTPUT_FLD",
               "REQU_ENTRY", "POSS_ENTRY", "MATCHCODE", "CONV_EXIT", "REF_FIELD", "GROUP1")
BUTTON_ORDER = ("FCODE", "TEXT", "ICON", "QUICKINFO", "FKEY")
MODLAR = ("WRITE", "READ", "DELETE")               # howto §2 #7
EKRAN_TIPLERI = ("DOCKING", "CONTAINER")            # howto §2 #5
_TEK_KARAKTER = {                                   # howto §2 #8, #11, #12 (+ §2.2 polarite)
    "recreate": ("X", " "),
    "cua_merge": ("X", " ", "-"),
    "nav_remap": (" ", "X", "-"),
}
_DYNPRO = re.compile(r"^\d{4}$")                    # howto §2.4 rc=300


def _esc(v) -> str:
    """howto §1 `esc` lambda'sı ile aynı: & < > kaçışı."""
    return str(v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def zarf(fm_name: str, skaler: list, fields: list, buttons: list) -> str:
    """SOAP zarfı. TABLES parametreleri (`IT_FIELDS`, `IT_BUTTONS`) DAİMA — boş da olsa — gönderilir
    (howto §1: istekte olmayan TABLES cevapta dönmez; adt-fugr-functions §3.2)."""
    inner = "".join(f"<{k}>{_esc(v)}</{k}>" for k, v in skaler)
    alanlar = "".join("<item>" + "".join(f"<{k}>{_esc(f.get(k, ''))}</{k}>" for k in FIELD_ORDER)
                      + "</item>" for f in fields)
    butonlar = "".join("<item>" + "".join(f"<{k}>{_esc(b.get(k, ''))}</{k}>" for k in BUTTON_ORDER)
                       + "</item>" for b in buttons)
    fm = _esc(fm_name)
    return ('<?xml version="1.0" encoding="utf-8"?>'
            '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"'
            ' xmlns:urn="urn:sap-com:document:sap:rfc:functions"><soapenv:Body>'
            f'<urn:{fm}>{inner}'
            f'<IT_FIELDS>{alanlar}</IT_FIELDS><IT_BUTTONS>{butonlar}</IT_BUTTONS>'
            f'</urn:{fm}></soapenv:Body></soapenv:Envelope>')


def _yerel_ad(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def yanit_ayristir(metin: str) -> dict:
    """SOAP yanıtı → {ev_rc: int|None, ev_message: str|None, fault: str|None, parse_error: bool}."""
    out = {"ev_rc": None, "ev_message": None, "fault": None, "parse_error": False}
    try:
        kok = ET.fromstring(metin or "")
    except ET.ParseError:
        out["parse_error"] = True
        return out
    for el in kok.iter():
        ad = _yerel_ad(el.tag)
        if ad == "EV_RC" and out["ev_rc"] is None:
            try:
                out["ev_rc"] = int((el.text or "").strip())
            except ValueError:
                out["ev_rc"] = None
        elif ad == "EV_MESSAGE" and out["ev_message"] is None:
            out["ev_message"] = el.text or ""
        elif ad == "faultstring" and out["fault"] is None:
            out["fault"] = (el.text or "").strip()
    return out


def rc_bandi(rc: int | None, alan_verildi: bool) -> tuple[str, str]:
    """howto §2.4 bantları → (kod, açıklama). Bantlar ARALIKTIR; sonuç screen rc ile toplanır."""
    if rc is None:
        return "olculemedi", "EV_RC yanıtta yok — sonuç ÖLÇÜLEMEDİ (başarı sayılmaz)."
    if rc == 0:
        return "ok", "Tüm adımlar 0."
    if rc == 5 and alan_verildi:
        return "fields_invalid", ("IT_FIELDS ön-doğrulaması — ekran YARATILMADI; kusurlu alan adları "
                                  "EV_MESSAGE'da (howto §4.5).")
    if 1 <= rc <= 18:
        return "bilesik", ("Bileşik kod: screen rc (0-10; 2 = ekran zaten var → alan/flow değişiminde "
                           "recreate='X') + status (0-3) + generate (0-5). EV_MESSAGE'ı oku (howto §2.4).")
    if 101 <= rc <= 113:
        return "donor_fetch", "Donör CUA fetch hatası (100+subrc) + screen rc (howto §2.4)."
    if 120 <= rc <= 130:
        return "donor_status_missing", ("Donör status satırı yok — CUA'ya hiçbir şey yazılmadı; "
                                        "src_prog/src_status ikilisini düzelt (howto §2.1, §2.4).")
    if 202 <= rc <= 213:
        return "merge_fetch", "CUA merge fetch hatası (200+rc) (howto §2.4)."
    if rc == 300:
        return "dynpro_invalid", "IV_DYNPRO 4 hane rakam değil — hiçbir adım koşmadı (howto §2.4)."
    if rc == 301:
        return "zy_guard", "FM'in Z/Y guard'ı: hedef program Z/Y değil — hiçbir adım koşmadı (howto §2.3)."
    return "bilinmeyen", "Belgelenmiş bant dışında EV_RC — EV_MESSAGE'ı oku."


_NAV = re.compile(r"nav_remap=(ON|OFF)\b[^\s;]*", re.I)
_TOKENLER = {"cua_merge": re.compile(r"cua_merge=\S+"), "fields": re.compile(r"fields=\d+(?:\s+io_default=\d+)?"),
             "donor": re.compile(r"donor=\S+")}


def mesaj_sinyalleri(mesaj: str | None) -> dict:
    """EV_MESSAGE'dan doğrulama sinyalleri (howto §10 tur sonu kontrol listesi). Mesaj KIRPILMAZ."""
    m = mesaj or ""
    nav = _NAV.search(m)
    out = {"nav_remap": nav.group(1).upper() if nav else None,
           "nav_remap_token": nav.group(0) if nav else None,
           "dikkat": [s.strip() for s in re.split(r"(?=DIKKAT:)", m) if s.strip().startswith("DIKKAT:")]}
    for ad, rx in _TOKENLER.items():
        t = rx.search(m)
        out[ad] = t.group(0) if t else None
    return out


def _satirlar(ad: str, veri, sira: tuple) -> list:
    if veri is None:
        return []
    if not isinstance(veri, list) or not all(isinstance(x, dict) for x in veri):
        raise ValueError(f"{ad} bir nesne listesi olmalı.")
    izinli = set(sira)
    out = []
    for i, satir in enumerate(veri):
        norm = {str(k).strip().upper(): ("" if v is None else v) for k, v in satir.items()}
        fazla = sorted(set(norm) - izinli)
        if fazla:
            raise ValueError(f"{ad}[{i}] tanınmayan alan: {', '.join(fazla)} (izinli: {', '.join(sira)}).")
        out.append(norm)
    return out


def _gecersiz(mesaj: str) -> dict:
    return {"ok": False, "error": "invalid_argument", "message": mesaj}


def _sirlar(adt) -> list:
    from sapadt import project, redact
    sirlar = (redact.bilinen_sirlar(project.effective_conn_value("ADT_SAP_USER", None),
                                    project.effective_conn_value("ADT_SAP_PASSWORD", None))
              + redact.host_sirlari(project.effective_conn_value("ADT_SAP_URL", None)))
    sirlar += redact.host_sirlari(getattr(adt, "url", None))
    sirlar += redact.bilinen_sirlar(getattr(adt, "user", None), getattr(adt, "password", None))
    return sorted(set(sirlar), key=len, reverse=True)


@profil_tool(available_on=("ecc", "s4_private"))
def adt_screen_generate(
    fm_name: str,
    program: str,
    title: str | None = None,
    dynpro: str = "0100",
    screen_type: str | None = None,
    cc_name: str | None = None,
    buttons: list | None = None,
    fields: list | None = None,
    src_prog: str | None = None,
    src_status: str | None = None,
    cua_merge: str | None = None,
    nav_remap: str | None = None,
    mode: str = "WRITE",
    recreate: str | None = None,
    transport: str | None = None,
) -> dict:
    """Generate a classic Dynpro screen + GUI status via a Z/Y screen-generator RFC FM (SOAP-RFC).

    YAZMA sınıfı (READ modu dahil — FM yazabilen bir üreteçtir). Hedef program ve FM Z/Y olmalı;
    WRITE/DELETE transport ister; WRITE `title` ister (master_language metni, kullanıcıdan).
    Varsayılanlar yıkıcı değildir: `cua_merge`/`recreate` verilmezse FM varsayılanı (merge AÇIK,
    recreate yok) geçerlidir. `cua_merge=' '|'-'` diğer status/titlebar'ları SİLER; `recreate='X'`
    ve `mode='DELETE'` ekranı siler — yalnız açıkça verildiğinde gönderilir.

    Argümanlar (howto §2): fm_name · program · title · dynpro (4 hane) · screen_type
    (DOCKING|CONTAINER) · cc_name · buttons[{FCODE,TEXT,ICON,QUICKINFO,FKEY}] ·
    fields[{CONT_TYPE…GROUP1}] (yalnız DOCKING) · src_prog/src_status (donör; salt okunur) ·
    cua_merge (X| |-) · nav_remap ( |X|-) · mode (WRITE|READ|DELETE) · recreate (X| ) · transport.

    Dönüş: {ok, fm_name, program, dynpro, mode, http_status, ev_rc, ev_rc_band, ev_rc_note,
    ev_message (KIRPILMAMIŞ), nav_remap (ON|OFF|null), signals{…}, warnings[]}.
    `ok` = EV_RC 0 VE (WRITE ise) nav_remap OFF değil. `nav_remap=OFF` → ok:false + error
    `nav_remap_off` (howto §2.1: çağrı yanlış, ekranı kullanmadan düzelt).
    """
    try:
        require_writable_tier(get_active_tier(), what="screen generate")
        require_customer_namespace(fm_name, what="fm_name (ekran üreteci FM)", object_type="function")
        require_customer_namespace(program, what="program (hedef)", object_type="program")
    except GuardrailViolation as gv:
        return gv.as_dict()

    kip = str(mode or "").strip().upper()
    if kip not in MODLAR:
        return _gecersiz(f"mode {mode!r} geçersiz — geçerli: {', '.join(MODLAR)}.")
    try:
        if kip in ("WRITE", "DELETE"):
            require_transport(transport, what=f"screen generate mode={kip}")
        if kip == "WRITE":
            require_tr_text(title, what="title (titlebar + dynpro açıklaması)")
    except GuardrailViolation as gv:
        return gv.as_dict()

    dyn = str(dynpro or "").strip()
    if not _DYNPRO.match(dyn):
        return _gecersiz(f"dynpro {dynpro!r} geçersiz — tam 4 hane rakam olmalı (howto §2.4 rc=300).")
    ekran = None
    if screen_type is not None:
        ekran = str(screen_type).strip().upper()
        if ekran not in EKRAN_TIPLERI:
            return _gecersiz(f"screen_type {screen_type!r} geçersiz — geçerli: {', '.join(EKRAN_TIPLERI)}.")
    tek = {}
    for ad, deger in (("recreate", recreate), ("cua_merge", cua_merge), ("nav_remap", nav_remap)):
        if deger is None:
            continue
        d = str(deger).upper() if str(deger).strip() else " "
        if d not in _TEK_KARAKTER[ad]:
            return _gecersiz(f"{ad} {deger!r} geçersiz — geçerli: "
                             + ", ".join(repr(x) for x in _TEK_KARAKTER[ad]) + " (howto §2.2).")
        tek[ad] = d
    try:
        alanlar = _satirlar("fields", fields, FIELD_ORDER)
        butonlar = _satirlar("buttons", buttons, BUTTON_ORDER)
    except ValueError as exc:
        return _gecersiz(str(exc))
    if alanlar and (ekran or "DOCKING") == "CONTAINER":
        return _gecersiz("fields yalnız screen_type=DOCKING ile verilir (CONTAINER'da CC_ALV tüm ekranı "
                         "kaplar → rc=6; howto §4.4).")

    uyarilar = []
    if tek.get("cua_merge") in (" ", "-"):
        uyarilar.append("cua_merge KAPALI verildi — programın DİĞER status/titlebar'ları SİLİNİR (howto §5).")
    if tek.get("recreate") == "X":
        uyarilar.append("recreate='X' — mevcut ekran silinip yeniden kurulur (howto §9).")
    if kip == "DELETE":
        uyarilar.append("mode=DELETE — ekran silinir (RS_SCRP_DELETE; howto §9).")
    if any(str(b.get("FKEY", "")).strip() for b in butonlar):
        uyarilar.append("FKEY dolu verildi — howto §3 boş bırakmayı önerir (donör pfk çakışması denenmedi).")
    if kip == "WRITE" and not (src_prog and str(src_prog).strip()):
        uyarilar.append("src_prog verilmedi → FM'in varsayılan (minimal) donörü; PAI'si BACK/EXIT/CANCEL "
                        "bekleyen programda butonlar tepkisiz kalabilir (howto §2.1).")

    skaler = [("IV_PROGRAM", str(program).strip().upper()), ("IV_DYNPRO", dyn)]
    if title is not None:
        skaler.append(("IV_TITLE", title))
    if ekran is not None:
        skaler.append(("IV_SCREEN_TYPE", ekran))
    if cc_name is not None:
        skaler.append(("IV_CC_NAME", str(cc_name).strip().upper()))
    skaler.append(("IV_MODE", kip))
    if "recreate" in tek:
        skaler.append(("IV_RECREATE", tek["recreate"]))
    if src_prog is not None:
        skaler.append(("IV_SRC_PROG", str(src_prog).strip().upper()))
    if src_status is not None:
        skaler.append(("IV_SRC_STATUS", str(src_status).strip().upper()))
    if "cua_merge" in tek:
        skaler.append(("IV_CUA_MERGE", tek["cua_merge"]))
    if "nav_remap" in tek:
        skaler.append(("IV_NAV_REMAP", tek["nav_remap"]))
    if transport is not None:
        skaler.append(("IV_TRANSPORT", str(transport).strip().upper()))
    fm = str(fm_name).strip().upper()
    govde = zarf(fm, skaler, alanlar, butonlar)

    from sapadt import redact
    from sapadt.tools.atom import _capture_stdout, _err_from_exc, _get_client, _master_language
    adt = None
    try:
        client = _get_client()
        adt = getattr(client, "adt_client", None) or client
        dil = _master_language()
        if not dil:
            return {"ok": False, "error": "master_language_unresolved",
                    "message": "sap-project.json master_language okunamadı — sap-language belirlenemedi; "
                               "çağrı yapılmadı (howto §1: sap-language şart)."}
        with _capture_stdout():
            r = adt.session.post(
                adt.url + SOAP_RFC_UC,
                params={"sap-client": str(getattr(adt, "client", "") or ""), "sap-language": dil},
                data=govde.encode("utf-8"),
                headers={"Content-Type": "text/xml; charset=utf-8", "SOAPAction": ""},
                verify=adt.session.verify, timeout=300,
            )
    except Exception as exc:  # noqa: BLE001 — ağ/istemci hatası: yapılandırılmış, sırsız
        return redact.temizle({**_err_from_exc(exc), "fm_name": fm, "program": str(program).upper()},
                              _sirlar(adt))

    durum = int(getattr(r, "status_code", 0) or 0)
    ayr = yanit_ayristir(getattr(r, "text", "") or "")
    sinyal = mesaj_sinyalleri(ayr["ev_message"])
    band, not_ = rc_bandi(ayr["ev_rc"], bool(alanlar))
    resp = {
        "ok": False, "fm_name": fm, "program": str(program).strip().upper(), "dynpro": dyn, "mode": kip,
        "http_status": durum, "ev_rc": ayr["ev_rc"], "ev_rc_band": band, "ev_rc_note": not_,
        "ev_message": ayr["ev_message"], "nav_remap": sinyal["nav_remap"], "signals": sinyal,
        "request": {"scalar_params": [k for k, _v in skaler], "fields": len(alanlar),
                    "buttons": len(butonlar), "tables_sent_empty_when_none": True},
        "warnings": uyarilar,
    }
    if durum != 200 or ayr["fault"]:
        resp["error"] = "soap_fault" if ayr["fault"] else f"http_{durum}"
        resp["message"] = (ayr["fault"] or (getattr(r, "text", "") or "")[:500]) or f"HTTP {durum}"
        return redact.temizle(resp, _sirlar(adt))
    if ayr["ev_rc"] is None:
        resp["error"] = "ev_rc_missing"
        resp["message"] = ("Yanıtta EV_RC yok — sonuç ÖLÇÜLEMEDİ"
                           + (" (yanıt XML değil)" if ayr["parse_error"] else "") + "; başarı sayılmadı.")
        return redact.temizle(resp, _sirlar(adt))
    if ayr["ev_rc"] != 0:
        resp["error"] = "screen_gen_rc"
        resp["message"] = f"EV_RC={ayr['ev_rc']} ({band}): {not_}"
        return redact.temizle(resp, _sirlar(adt))
    if kip == "WRITE":
        if sinyal["nav_remap"] == "OFF":
            resp["error"] = "nav_remap_off"
            resp["message"] = ("EV_MESSAGE nav_remap=OFF — howto §2.1: çağrı YANLIŞ (donör parametreleri "
                               "gitmemiş olabilir). Üretilen ekranı KULLANMADAN çağrıyı düzelt "
                               "(src_prog/src_status/nav_remap).")
            return redact.temizle(resp, _sirlar(adt))
        if sinyal["nav_remap"] is None:
            resp["warnings"].append("EV_MESSAGE'da nav_remap sinyali YOK — nav remap durumu ÖLÇÜLEMEDİ "
                                    "(howto §2.1); ekranı çalıştırıp BACK/EXIT/CANCEL'i doğrula.")
    resp["ok"] = True
    resp["notice"] = ("Runtime davranışı (buton tepkisi, 00256/00264) yalnız ekran çalıştırılınca görünür; "
                      "mode='READ' ile [FN: dökümünü tur öncesi/sonrası kıyasla (howto §10).")
    return redact.temizle(resp, _sirlar(adt))
