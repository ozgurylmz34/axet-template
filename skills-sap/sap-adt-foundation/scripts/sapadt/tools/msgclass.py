# -*- coding: utf-8 -*-
"""adt_msgclass_write — Z/Y mesaj sınıfına (MSAG) mesaj yazma (aXet 2026-09-13). YAZMA sınıfı.

REÇETE (kaynak çekirdek, salt-okur; canlı çalışmış yol):
  · `playbook/adt-message-class.md:66-137` (§27.1 çalışan akış) · `:139-150` (§27.2 If-Match kök sebebi) ·
    `:152-165` (§27.3 XML şeması) · `:167-198` (§27.4 try/finally kilit bırakma) · `:200-205` (§27.5 tam liste
    değiştirme) · `:207-225` (§27.6 50+ başarısız varyant) · `:232` (T100 metin ≤ 73)
  · `scripts/populate_message_class.py:179-201` (gövde) · `:204-312` (LOCK → PUT → UNLOCK) · `:68-79,96-176` (73 karakter
    sınırı, yarım satır reddi, metin `strip`)
  Uç: `/sap/bc/adt/messageclass/<ad>` · LOCK `POST ?_action=LOCK&accessMode=MODIFY&corrNr=<TR>` (stateful,
  Accept `application/*,application/vnd.sap.as+xml;dataname=com.sap.adt.lock.result`) → `<LOCK_HANDLE>` ·
  PUT `?corrNr&lockHandle&accessMode=MODIFY`, `Content-Type: application/vnd.sap.adt.mc.messageclass+xml; charset=utf-8`,
  `Accept: */*`, stateful, `sap-client`, `sap-language`, **If-Match YOK** · UNLOCK `POST ?_action=UNLOCK&lockHandle` (finally).

KAYNAKTAN BİLİNÇLİ FARKLAR:
  1. `clear_enqueue_lock` "güvenlik ağı" (adt-message-class.md:136,193-197; populate_message_class.py:305-310) ALINMADI —
     enqueue kilidi silmek Kesin Yasak C. Yalnız bu çağrının KENDİ aldığı LOCK handle'ı UNLOCK edilir. Kilit alınamazsa
     DUR: `lock_conflict` / `lock_failed` (çıkış 1) + "SM12'de kendi kilidini kendin kontrol et".
  2. Tam liste PUT'u (listede olmayan mesaj SİLİNİR, §27.5) güvenli sarmalandı: önce canlı liste okunur (okunamazsa
     yazma yok); varsayılan mod BİRLEŞTİR — verilmeyen mevcut mesajlar korunur. Mevcut mesajın metnini/bayrağını
     değiştirmek yalnız `allow_overwrite=true`, silmek yalnız `delete_numbers=[…]` ile; ikisi de yanıtta listelenir.
  3. PULL-BEFORE-EDIT: `adt_msgclass_read` mesaj listesinin kanonik özetini kaydeder; yazma anındaki canlı özet
     farklıysa `source_changed_since_pull` (başkası arada değiştirdi → üzerine yazılmaz).
  4. Yazma sonrası canlı geri okuma beklenen tam listeyle kıyaslanır (`readback_verified`); fark → `ok:false`.
  5. `responsible` / `description` / paket canlı okumadan korunur (kaynakta CLI argümanıydı); `masterLanguage` ve
     `language` = `sap-project.json` master_language (kaynakta sabit "TR") ve canlı sınıfın master dili ile aynı olmalı.
  6. İstek `SAPADTClient._request_with_csrf_retry` ile gider (mevcut oturum/CSRF/TLS; kaynakta ham `session` + discovery
     CSRF) — eşdeğerliği canlı DOĞRULANMADI (IMPLEMENTATION.md §14.8 ile aynı sınıf).
Profil: `available_on=("s4_private",)` — reçetenin kanıtı yalnız bu profil (adt-message-class.md:2 `applies_to`,
populate_message_class.py:8 "S/4 1909"). Genişletme kanıt ister.
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote
from xml.sax.saxutils import escape as _xml_escape

from sapadt import pull_state as _pull_state
from sapadt._app import profil_tool
from sapadt._conn import get_active_tier
from sapadt.guardrails import (
    GuardrailViolation,
    require_customer_namespace,
    require_transport,
    require_writable_tier,
)

T100_TEXT_MAXLEN = 73   # populate_message_class.py:68-79 (DD03L ölçümü; KARAKTER sayılır)
_NO = re.compile(r"^\d{3}$")   # adt-message-class.md:159 (3 hane sıfır dolgulu)
_MESAJ_ALANLARI = frozenset({"no", "text", "selfexplanatory"})
_KILIT_ACCEPT = "application/*,application/vnd.sap.as+xml;dataname=com.sap.adt.lock.result"
_PUT_CT = "application/vnd.sap.adt.mc.messageclass+xml; charset=utf-8"
_KILIT_CAKISMA = re.compile(r"EU\s*510|locked|gesperrt|currently being edited|enqueue", re.I)
_SM12 = ("Araç enqueue kilidini SİLMEZ (Kesin Yasak C). SM12'de kendi kilidini kendin kontrol et; SE91/ADT'de sınıf "
         "açıksa kapat; başka biri düzenliyorsa bitmesini bekle. Sonra adt_msgclass_read → adt_msgclass_write ile tekrar dene.")


def _att(v) -> str:
    return _xml_escape(str(v), {'"': "&quot;"})


def _hata(kod: str, mesaj: str, **ek) -> dict:
    return {"ok": False, "error": kod, "message": mesaj, **ek}


def _master_language() -> str | None:
    try:
        from sapadt.project import load_sap_project
        cfg, _h = load_sap_project()
        ml = (cfg or {}).get("master_language")
        return ml.strip().upper() if isinstance(ml, str) and ml.strip() else None
    except Exception:  # noqa: BLE001
        return None


def _temizle(resp: dict, adt) -> dict:
    from sapadt import redact
    from sapadt.tools.screen import _sirlar
    try:
        return redact.temizle(resp, _sirlar(adt))
    except Exception:  # noqa: BLE001 — arındırma koşamazsa ham SAP gövdesi dönmesin
        resp = dict(resp)
        resp.pop("sap_body", None)
        return resp


def _dogrula(messages, delete_numbers, allow_overwrite, package) -> tuple[dict | None, list, list]:
    """Ağ ÖNCESİ argüman denetimi → (hata|None, normalize mesajlar, silinecek numaralar)."""
    if not isinstance(allow_overwrite, bool):
        return _hata("invalid_argument", "allow_overwrite true/false olmalı."), [], []
    if package is not None and not (isinstance(package, str) and package.strip()):
        return _hata("invalid_argument", "package verilecekse boş olmayan metin olmalı."), [], []
    if messages is None:
        messages = []
    if not isinstance(messages, list):
        return _hata("invalid_argument", "messages bir liste olmalı: [{\"no\":\"001\",\"text\":\"…\"}]."), [], []
    norm, gorulen = [], set()
    for i, m in enumerate(messages):
        if not isinstance(m, dict):
            return _hata("invalid_argument", f"messages[{i}] nesne değil."), [], []
        fazla = sorted(set(m) - _MESAJ_ALANLARI)
        if fazla:
            return _hata("invalid_argument",
                         f"messages[{i}] tanınmayan alan: {', '.join(fazla)} (izinli: no, text, selfexplanatory; "
                         "`documented`/uzun metin bu araçla yazılmaz)."), [], []
        no = m.get("no")
        if not (isinstance(no, str) and _NO.match(no)):
            return _hata("invalid_argument",
                         f"messages[{i}].no 3 haneli metin olmalı (ör. \"001\"; verilen: {no!r}). Numara dolgusu "
                         "tahmin edilmez."), [], []
        if no in gorulen:
            return _hata("invalid_argument", f"messages içinde {no} numarası iki kez var."), [], []
        gorulen.add(no)
        metin = m.get("text")
        if not (isinstance(metin, str) and metin.strip()):
            return GuardrailViolation(
                "ADR_0005_D", f"messages[{i}] ({no}) metni boş — mesaj metni master_language'de ve dolu olmalı.",
                no=no).as_dict(), [], []
        metin = metin.strip()   # populate_message_class.py:122 (metin strip edilir)
        if len(metin) > T100_TEXT_MAXLEN:
            return _hata("invalid_argument",
                         f"messages[{i}] ({no}) metni {len(metin)} karakter > T100 sınırı {T100_TEXT_MAXLEN} "
                         "(SAP ya reddeder ya sessizce kırpar; kısaltma onaylı metni değiştirir — metin sahibine sor)."), [], []
        se = m.get("selfexplanatory")
        if se is not None and not isinstance(se, bool):
            return _hata("invalid_argument", f"messages[{i}].selfexplanatory true/false olmalı."), [], []
        norm.append({"no": no, "text": metin, "selfexplanatory": se})
    if delete_numbers is None:
        delete_numbers = []
    if not isinstance(delete_numbers, list):
        return _hata("invalid_argument", "delete_numbers bir liste olmalı: [\"005\", …]."), [], []
    silinecek = []
    for n in delete_numbers:
        if not (isinstance(n, str) and _NO.match(n)):
            return _hata("invalid_argument", f"delete_numbers öğesi 3 haneli metin olmalı (verilen: {n!r})."), [], []
        if n in silinecek:
            return _hata("invalid_argument", f"delete_numbers içinde {n} iki kez var."), [], []
        silinecek.append(n)
    cakisan = sorted(gorulen & set(silinecek))
    if cakisan:
        return _hata("invalid_argument", f"Aynı numara hem yazılıyor hem siliniyor: {', '.join(cakisan)}."), [], []
    if not norm and not silinecek:
        return _hata("invalid_argument", "Yazılacak mesaj ya da silinecek numara verilmedi."), [], []
    return None, norm, silinecek


def _govde(name: str, aciklama: str, ml: str, sorumlu: str, paket: str, liste: list) -> str:
    """populate_message_class.py:179-201 / adt-message-class.md:105-118 ile aynı şema; öznitelikler kaçışlı
    (adt-message-class.md:165: & < > " ). `mc:documented` canlı değerle korunur (yeni mesajda false)."""
    msgs = "\n".join(
        f'  <mc:messages mc:msgno="{_att(m["no"])}" mc:msgtext="{_att(m["text"])}" '
        f'mc:selfexplainatory="{"true" if m["selfexplanatory"] else "false"}" '
        f'mc:documented="{"true" if m.get("documented") else "false"}" adtcore:name=""/>'
        for m in liste)
    return (f'<?xml version="1.0" encoding="utf-8"?>\n'
            f'<mc:messageClass adtcore:responsible="{_att(sorumlu)}"\n'
            f'                 adtcore:masterLanguage="{_att(ml)}"\n'
            f'                 adtcore:name="{_att(name)}"\n'
            f'                 adtcore:type="MSAG/N"\n'
            f'                 adtcore:description="{_att(aciklama)}"\n'
            f'                 adtcore:language="{_att(ml)}"\n'
            f'                 xmlns:mc="http://www.sap.com/adt/MessageClass"\n'
            f'                 xmlns:adtcore="http://www.sap.com/adt/core">\n'
            f'  <adtcore:packageRef adtcore:uri="/sap/bc/adt/packages/{quote(paket.lower(), safe="")}"\n'
            f'                      adtcore:type="DEVC/K"\n'
            f'                      adtcore:name="{_att(paket.upper())}"/>\n'
            + (msgs + "\n" if msgs else "") +
            '</mc:messageClass>')


def _kiyas_listesi(liste) -> list:
    return sorted((str(m.get("no")), str(m.get("text")), bool(m.get("selfexplanatory"))) for m in (liste or []))


@profil_tool(available_on=("s4_private",))
def adt_msgclass_write(
    name: str,
    transport: str,
    messages: list | None = None,
    delete_numbers: list | None = None,
    allow_overwrite: bool = False,
    package: str | None = None,
) -> dict:
    """Write messages into an existing Z/Y message class (merge by number; overwrite/delete only explicitly).

    Önce `adt_msgclass_read(name)` (canlı liste + pull kaydı) şarttır. Kabuk yoksa önce
    `adt_post_shell(object_type="msag")` (kabuksuz PUT sahte-200 döner, adt-message-class.md:21).

    Args:
        name: Mesaj sınıfı (Z*/Y*; standart sınıf Kesin Yasak A).
        transport: Değiştirilebilir transport (zorunlu; kilit corrNr ile alınır).
        messages: [{"no":"001","text":"<master_language metni, ≤73>","selfexplanatory":false}] — yeni numara
            eklenir; mevcut numara aynıysa değişmez, farklıysa yalnız `allow_overwrite=true` ile değişir.
            `selfexplanatory` verilmezse mevcut mesajda canlı değer, yeni mesajda false.
        delete_numbers: Silinecek MEVCUT numaralar (["005"]). Verilmeyen hiçbir mesaj silinmez.
        allow_overwrite: Mevcut mesajın metnini/bayrağını değiştirmeye açık izin.
        package: Canlı okumada paket yoksa kullanılır; canlıdakiyle farklıysa red.

    Returns:
        {ok, name, changed, plan{added, overwritten[{no,before,after}], deleted[{no,text}], unchanged, preserved_count},
         message_count_before, message_count_after, readback_verified, pull_state, http{lock,put,unlock}, unlock_warning?}
    """
    try:
        require_writable_tier(get_active_tier(), what="msag write")
        require_customer_namespace(name, what="msag")
        require_transport(transport, what="msag write")
    except GuardrailViolation as gv:
        return gv.as_dict()
    hata, mesajlar, silinecek = _dogrula(messages, delete_numbers, allow_overwrite, package)
    if hata:
        return hata
    ml = _master_language()
    if not ml:
        return _hata("master_language_unresolved",
                     "sap-project.json master_language çözülemedi — mesaj metninin dili doğrulanamaz, yazma yapılmadı.")
    kayit, pst_hata = _pull_state.kayit_al(name, "msag")
    if pst_hata:
        return _hata("pull_state_unreadable", f"Pull-state okunamadı: {pst_hata}. adt_msgclass_read ile yeniden çek.")
    if kayit is None:
        return _hata("pull_before_edit_missing",
                     f"PULL-BEFORE-EDIT: {_pull_state.anahtar(name, 'msag')} için çekme kaydı yok. Önce "
                     "adt_msgclass_read ile canlı mesaj listesini oku; yazma o listeyle birleştirilir.")

    from sapadt.tools import atom as _atom
    adt = None
    try:
        client = _atom._get_client()
        adt = getattr(client, "adt_client", None) or client
        canli = _atom._msgclass_oku(name)
    except Exception as exc:  # noqa: BLE001 — okuma istisnası "okunamadı"dır, geçiş değil
        canli = _atom._err_from_exc(exc)
    if not (isinstance(canli, dict) and canli.get("ok") is True and canli.get("exists") in (True, False)):
        c = canli if isinstance(canli, dict) else {}
        return _temizle(_hata("pull_live_read_failed",
                              "Yazmadan önce canlı mesaj listesi OKUNAMADI — tam liste PUT'u mevcut mesajları "
                              "silebileceği için yazma yapılmadı. Bağlantıyı düzelt, tekrar dene.",
                              live_read={"error": c.get("error"), "message": str(c.get("message") or "")[:300]}), adt)
    if canli.get("exists") is False:
        return _hata("source_changed_since_pull",
                     "PULL-BEFORE-EDIT: mesaj sınıfı çekildiğinde VARDI, şimdi SAP'de YOK — yazılmadı "
                     "(kabuksuz PUT sahte-200 döner). adt_msgclass_read ile yeniden kontrol et.",
                     pulled_at=kayit.get("pulled_at"))
    canli_ozet = _pull_state.ozet(_atom.msgclass_ozet_metni(canli.get("messages")))
    if canli_ozet != kayit.get("sha256"):
        return _hata("source_changed_since_pull",
                     f"PULL-BEFORE-EDIT: mesaj listesi {kayit.get('pulled_at')} tarihli okumadan sonra SAP'de DEĞİŞMİŞ — "
                     "üzerine yazılmadı. adt_msgclass_read ile yeniden oku, değişikliğini yeni listeye göre yeniden ver.",
                     pulled_at=kayit.get("pulled_at"), pulled_sha256=str(kayit.get("sha256"))[:12],
                     live_sha256=canli_ozet[:12])
    canli_ml = str(canli.get("master_language") or "").strip().upper()
    if not canli_ml:
        return _hata("master_language_unresolved",
                     "Canlı mesaj sınıfının masterLanguage'i okunamadı — metin dili doğrulanamaz, yazma yapılmadı.")
    if canli_ml != ml:
        return GuardrailViolation(
            "ADR_0005_D", f"Mesaj sınıfının master dili {canli_ml} ≠ sap-project.json master_language {ml}. Metinler "
                          "yanlış dile yazılırdı; yazma yapılmadı (dil yerinde değişmez).").as_dict()
    paket = canli.get("_package")
    if package and paket and package.strip().upper() != str(paket).upper():
        return _hata("invalid_argument", f"package {package!r} canlı sınıfın paketiyle ({paket}) aynı değil.")
    paket = paket or (package.strip() if package else None)
    aciklama = canli.get("description")
    sorumlu = canli.get("_responsible") or getattr(adt, "user", None)
    eksik = [ad for ad, v in (("paket (package)", paket), ("açıklama", aciklama), ("sorumlu", sorumlu))
             if not (isinstance(v, str) and v.strip())]
    if eksik:
        return _hata("msgclass_live_incomplete",
                     f"Tam gövde PUT'u için canlı okumada eksik: {', '.join(eksik)}. Tahmin edilmez; "
                     "paket eksikse `package` argümanı ver, açıklama eksikse kullanıcı SE91'de doldurur.")

    # ── plan ─────────────────────────────────────────────────────────────────────────────────
    mevcut = {str(m.get("no")): m for m in canli.get("messages") or []}
    yok = [n for n in silinecek if n not in mevcut]
    if yok:
        return _hata("invalid_argument", f"Silinecek numara canlı listede yok: {', '.join(yok)} (silme yapılmadı).")
    eklenen, ustune, degismeyen = [], [], []
    for m in mesajlar:
        eski = mevcut.get(m["no"])
        se = m["selfexplanatory"] if m["selfexplanatory"] is not None else bool(eski and eski.get("selfexplanatory"))
        if eski is None:
            eklenen.append({"no": m["no"], "text": m["text"], "selfexplanatory": se})
        elif eski.get("text") == m["text"] and bool(eski.get("selfexplanatory")) == se:
            degismeyen.append(m["no"])
        else:
            ustune.append({"no": m["no"],
                           "before": {"text": eski.get("text"), "selfexplanatory": bool(eski.get("selfexplanatory"))},
                           "after": {"text": m["text"], "selfexplanatory": se}})
    plan: dict[str, Any] = {
        "added": eklenen, "overwritten": ustune,
        "deleted": [{"no": n, "text": mevcut[n].get("text")} for n in silinecek],
        "unchanged": degismeyen,
        "preserved_count": len([n for n in mevcut if n not in silinecek and n not in {x["no"] for x in ustune}
                                and n not in degismeyen]),
    }
    if ustune and not allow_overwrite:
        return _hata("msgclass_overwrite_not_allowed",
                     "Mevcut mesaj(lar) değişirdi: " + ", ".join(u["no"] for u in ustune)
                     + ". Üzerine yazma yalnız allow_overwrite=true ile; önce plan.overwritten'i kullanıcıya göster.",
                     name=name.upper(), plan=plan)
    nihai = {n: {"no": n, "text": m.get("text"), "selfexplanatory": bool(m.get("selfexplanatory")),
                 "documented": bool(m.get("documented"))} for n, m in mevcut.items()}
    for n in silinecek:
        nihai.pop(n, None)
    for e in eklenen:
        nihai[e["no"]] = {**e, "documented": False}
    for u in ustune:
        nihai[u["no"]] = {"no": u["no"], **u["after"], "documented": nihai[u["no"]]["documented"]}
    liste = [nihai[n] for n in sorted(nihai)]
    temel = {"name": name.upper(), "plan": plan, "message_count_before": len(mevcut),
             "message_count_after": len(liste)}
    if not (eklenen or ustune or silinecek):
        return {"ok": True, **temel, "changed": False, "readback_verified": None,
                "notice": "Değişiklik yok — kilit alınmadı, PUT gönderilmedi."}

    # ── LOCK → PUT (If-Match YOK) → UNLOCK (yalnız kendi handle'ı) ─────────────────────────────
    obj = "/sap/bc/adt/messageclass/" + quote(name.lower(), safe="")
    govde = _govde(name.upper(), aciklama, ml, sorumlu, paket, liste)
    http: dict[str, Any] = {}
    resp: dict[str, Any] = {"ok": False, **temel, "changed": False, "http": http, "readback_verified": None}
    handle = None
    put_gonderildi = False
    yazildi = False
    try:
        lr = adt._request_with_csrf_retry(
            "post", adt.url + obj, headers={"X-sap-adt-sessiontype": "stateful", "Accept": _KILIT_ACCEPT},
            params={"_action": "LOCK", "accessMode": "MODIFY", "corrNr": transport})
        http["lock"] = int(getattr(lr, "status_code", 0) or 0)
        lt = str(getattr(lr, "text", "") or "")
        m = re.search(r"<LOCK_HANDLE[^>]*>([^<]+)</LOCK_HANDLE>", lt)
        if not m:
            cakisma = http["lock"] in (403, 409, 423) or bool(_KILIT_CAKISMA.search(lt))
            resp.update(error="lock_conflict" if cakisma else "lock_failed",
                        message=(f"Mesaj sınıfı kilidi alınamadı (HTTP {http['lock']}). " + _SM12),
                        sap_body=lt[:300])
            return _temizle(resp, adt)
        handle = m.group(1)
        put_gonderildi = True
        pr = adt._request_with_csrf_retry(
            "put", adt.url + obj,
            headers={"Content-Type": _PUT_CT, "Accept": "*/*", "X-sap-adt-sessiontype": "stateful",
                     "sap-client": str(getattr(adt, "client", "") or ""), "sap-language": ml},
            params={"corrNr": transport, "lockHandle": handle, "accessMode": "MODIFY"},
            data=govde.encode("utf-8"))
        http["put"] = int(getattr(pr, "status_code", 0) or 0)
        if http["put"] in (200, 201, 204):
            yazildi = True
        else:
            resp.update(error="push_failed", message=f"Mesaj sınıfı PUT reddedildi (HTTP {http['put']}).",
                        sap_body=str(getattr(pr, "text", "") or "")[:300])
    except Exception as exc:  # noqa: BLE001
        e = _atom._err_from_exc(exc)
        resp.update(error=e.get("error"), message=e.get("message"))
        if put_gonderildi:
            _pull_state.sil(name, "msag")
            resp["pull_state"] = "silindi: PUT sırasında istisna — yazılıp yazılmadığı belirsiz, adt_msgclass_read ile yeniden oku"
    finally:
        if handle:
            try:
                ur = adt._request_with_csrf_retry("post", adt.url + obj,
                                                  headers={"X-sap-adt-sessiontype": "stateful"},
                                                  params={"_action": "UNLOCK", "lockHandle": handle})
                http["unlock"] = int(getattr(ur, "status_code", 0) or 0)
                if http["unlock"] not in (200, 204):
                    resp["unlock_warning"] = f"UNLOCK HTTP {http['unlock']}. " + _SM12
            except Exception:  # noqa: BLE001 — kilit bırakma hatası yazma sonucunu değiştirmez
                resp["unlock_warning"] = "UNLOCK başarısız. " + _SM12
    if not yazildi:
        return _temizle(resp, adt)

    # ── canlı geri okuma: beklenen TAM liste ile kıyas ────────────────────────────────────────
    resp["changed"] = True
    try:
        sonra = _atom._msgclass_oku(name)
    except Exception as exc:  # noqa: BLE001
        sonra = _atom._err_from_exc(exc)
    if not (isinstance(sonra, dict) and sonra.get("ok") is True and sonra.get("exists") is True):
        _pull_state.sil(name, "msag")
        resp.update(error="readback_failed", pull_state="silindi: geri okuma başarısız — adt_msgclass_read ile yeniden oku",
                    message="PUT kabul edildi ama canlı geri okuma yapılamadı — yazım DOĞRULANMADI.")
        return _temizle(resp, adt)
    beklenen, gercek = _kiyas_listesi(liste), _kiyas_listesi(sonra.get("messages"))
    if beklenen != gercek:
        _pull_state.sil(name, "msag")
        b, g = set(beklenen), set(gercek)
        resp.update(error="readback_mismatch", readback_verified=False,
                    readback_diff={"missing": [list(x) for x in sorted(b - g)],
                                   "unexpected": [list(x) for x in sorted(g - b)]},
                    pull_state="silindi: geri okuma beklenen listeyle uyuşmadı — adt_msgclass_read ile yeniden oku",
                    message="PUT kabul edildi ama canlı mesaj listesi beklenen tam listeyle AYNI DEĞİL (kabuk yoksa "
                            "sahte-200 olabilir). Kullanıcıyla SE91'de kontrol et.")
        return _temizle(resp, adt)
    h = _pull_state.kaydet(name, "msag", _atom.msgclass_ozet_metni(sonra.get("messages")))
    resp.update(ok=True, readback_verified=True, pull_state="guncellendi" if h is None else f"yazilamadi: {h}")
    resp.pop("error", None)
    resp.pop("message", None)
    return _temizle(resp, adt)
