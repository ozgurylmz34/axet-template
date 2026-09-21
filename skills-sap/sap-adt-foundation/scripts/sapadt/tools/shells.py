# -*- coding: utf-8 -*-
"""Kabuk (boş Z/Y obje) yaratma reçeteleri — `adt_post_shell`in tipe özel yolları. TOOL DEĞİL.

Her reçetenin ucu, Content-Type/Accept'i ve gövdesi kaynak çekirdekte CANLI çalışmış bir
yoldan birebir alınmıştır (kaynak: aşağıdaki `kaynak` alanı; IMPLEMENTATION.md §14). Reçetesi
olmayan tip `unsupported_type` ile reddedilir — uç/gövde TAHMİN EDİLMEZ.

Ortak kurallar:
  • Tüm POST'lar `SAPADTClient._request_with_csrf_retry` + `_get_headers` ile gider (mevcut
    oturum/kimlik/CSRF/TLS altyapısı; yeni kimlik okuma yolu YOK).
  • Transport `corrNr` query parametresidir (reçetelerin hepsinde).
  • `adtcore:masterLanguage` reçetede varsa değeri `sap-project.json` `master_language`'dir
    (kaynakta sabit "TR"). Reçetede yoksa (MSAG, ENQU, TTYP) eklenmez: o reçetelerde dil oturum
    dilinden gelir ve yazma kapısı oturum dili == master_language şartını ağdan önce koşar.
  • Kaynak metni GÖVDEYE KONMAZ (DDLS inline-POST boş kaynak tuzağı): kabuk + ayrı push.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import quote
from xml.sax.saxutils import escape as _xml_escape

GENEL = "genel"   # sap_client.create_object yolu (class/interface/program/include) — değişmedi

_GENEL_TIPLER = frozenset({"class", "clas", "interface", "intf", "program", "prog", "report",
                           "include", "incl"})

TIP_ESANLAM = {
    "ddls": "ddls", "cds": "ddls", "ddl": "ddls", "cdsview": "ddls",
    "srvd": "srvd", "servicedefinition": "srvd", "srv": "srvd",
    "bdef": "bdef", "behaviordefinition": "bdef",
    "fugr": "fugr", "functiongroup": "fugr",
    "func": "func", "function": "func",
    "msag": "msag", "messageclass": "msag",
    "enqu": "enqu", "lock": "enqu", "lockobject": "enqu", "lockobjects": "enqu",
    "ttyp": "ttyp", "tabletype": "ttyp",
}

DESTEKLENMEYEN = {
    "ddlx": "DDLX (metadata extension) kabuğu için kaynakta CANLI çalışmış reçete yok (yalnız "
            "kütüphane kodu var, kaynağı kilitsiz ve hatasını yutan bir set_object_source ile yazıyor). "
            "Kabuğu kullanıcı ADT/Eclipse'te açar; sonra adt_get → adt_push_source.",
    "dcl": "DCL (access control) kabuğu için kaynakta CANLI çalışmış reçete yok (yalnız kütüphane "
           "kodu). Kabuğu kullanıcı ADT/Eclipse'te açar; sonra adt_get → adt_push_source.",
    "srvb": "SRVB (service binding) yaratma kaynakta REST'te BLOKE ölçüldü (POST → 400 Session "
            "Timed Out). Kullanıcı ADT/Eclipse'te yaratır; yayın için adt_publish_service.",
    "domain": "Domain için adt_domain_create composite aracını kullan.",
    "dataelement": "Data element için adt_dtel_create composite aracını kullan.",
    "structure": "Yapı için adt_struct_create composite aracını kullan.",
    "table": "Z tablo için adt_table_create composite aracını kullan (kabuk + kilitli DDL yazımı + aktivasyon + "
             "readback tek çağrıda). Tablo tasarımı (ad, alanlar, DTEL, anahtar) önce kullanıcıya gösterilip AÇIK "
             "onay alınır — sap-cds-ddic references/tables-structures.md §3.",
}
_DESTEKSIZ_ESANLAM = {
    "ddlx": "ddlx", "metadataextension": "ddlx", "mde": "ddlx",
    "dcl": "dcl", "dcls": "dcl", "accesscontrol": "dcl",
    "srvb": "srvb", "servicebinding": "srvb",
    "doma": "domain", "domain": "domain",
    "dtel": "dataelement", "dataelement": "dataelement",
    "structure": "structure", "struct": "structure",
    "tabl": "table", "table": "table",
}


class KabukHatasi(ValueError):
    """Kullanım hatası (ağa gidilmez). `code` CLI'de çıkış 3'e eşlenir."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def kabuk_tipi(object_type) -> str:
    """`GENEL` | yeni tip anahtarı (`ddls`, `srvd`, `bdef`, `fugr`, `func`, `msag`, `enqu`, `ttyp`).
    Desteklenmeyen tip → KabukHatasi(unsupported_type)."""
    t = str(object_type or "").strip().lower()
    if t in _GENEL_TIPLER:
        return GENEL
    if t in TIP_ESANLAM:
        return TIP_ESANLAM[t]
    if t in _DESTEKSIZ_ESANLAM:
        anahtar = _DESTEKSIZ_ESANLAM[t]
        raise KabukHatasi("unsupported_type", f"adt_post_shell '{object_type}' desteklenmiyor: "
                                              f"{DESTEKLENMEYEN[anahtar]}")
    desteklenen = sorted(_GENEL_TIPLER | set(TIP_ESANLAM))
    raise KabukHatasi("unsupported_type", f"adt_post_shell '{object_type}' tipini tanımıyor. "
                                          f"Desteklenen: {', '.join(desteklenen)}")


# ── extra (tipe özel alanlar) ────────────────────────────────────────────────────────────────
_EXTRA_SEMASI = {
    "func": {"function_group"},
    "enqu": {"primary_table", "lock_fields", "lock_mode", "allow_rfc"},
    "ttyp": {"row_type"},
}
_KILIT_MODLARI = ("E", "S", "X")   # adt-lock-objects §29.4


def _dolu_metin(v) -> bool:
    return isinstance(v, str) and bool(v.strip())


def extra_dogrula(tip: str, extra) -> dict:
    """`extra`yı tipe göre doğrula ve normalize et. Hata → KabukHatasi(invalid_argument)."""
    if extra is None:
        extra = {}
    if not isinstance(extra, dict):
        raise KabukHatasi("invalid_argument", "extra bir JSON nesnesi olmalı.")
    izinli = _EXTRA_SEMASI.get(tip, set())
    fazla = sorted(set(extra) - izinli)
    if fazla:
        raise KabukHatasi("invalid_argument",
                          f"extra bu tipte tanınmayan alan içeriyor: {', '.join(fazla)} "
                          f"(izinli: {', '.join(sorted(izinli)) or 'yok — extra verme'}).")
    if tip == "func":
        if not _dolu_metin(extra.get("function_group")):
            raise KabukHatasi("invalid_argument",
                              "func kabuğu extra.function_group ister (FM'in yaratılacağı MEVCUT Z/Y "
                              "fonksiyon grubu).")
        return {"function_group": extra["function_group"].strip().upper()}
    if tip == "enqu":
        if not _dolu_metin(extra.get("primary_table")):
            raise KabukHatasi("invalid_argument", "enqu kabuğu extra.primary_table ister.")
        alanlar = extra.get("lock_fields")
        if (not isinstance(alanlar, list) or not alanlar
                or not all(_dolu_metin(a) for a in alanlar)):
            raise KabukHatasi("invalid_argument",
                              "enqu kabuğu extra.lock_fields ister: boş olmayan METİN listesi "
                              "(ör. [\"MANDT\",\"BOOKING_NO\"]; nesne listesi DEĞİL).")
        mod = str(extra.get("lock_mode") or "E").strip().upper()
        if mod not in _KILIT_MODLARI:
            raise KabukHatasi("invalid_argument", f"extra.lock_mode {mod!r} — geçerli: E, S, X.")
        rfc = extra.get("allow_rfc", False)
        if not isinstance(rfc, bool):
            raise KabukHatasi("invalid_argument", "extra.allow_rfc true/false olmalı.")
        return {"primary_table": extra["primary_table"].strip().upper(),
                "lock_fields": [a.strip().upper() for a in alanlar], "lock_mode": mod, "allow_rfc": rfc}
    if tip == "ttyp":
        if not _dolu_metin(extra.get("row_type")):
            raise KabukHatasi("invalid_argument", "ttyp kabuğu extra.row_type ister (satır tipi: yapı/DTEL).")
        return {"row_type": extra["row_type"].strip().upper()}
    return {}


# ── istek kurucuları ─────────────────────────────────────────────────────────────────────────
def _att(v) -> str:
    return _xml_escape(str(v), {'"': "&quot;"})


def _paket_ref_tam(package: str) -> str:
    return (f'  <adtcore:packageRef adtcore:uri="/sap/bc/adt/packages/{quote(package.lower(), safe="")}"\n'
            f'                      adtcore:type="DEVC/K"\n'
            f'                      adtcore:name="{_att(package.upper())}"/>\n')


@dataclass
class KabukIstegi:
    tip: str
    path: str
    content_type: str
    accept: str
    govde: str
    object_url: str
    kaynak: str
    ek_basliklar: dict = field(default_factory=dict)


def istek(tip: str, name: str, package: str, description: str, master_language: str,
          extra: dict) -> KabukIstegi:
    ad = name.upper()
    ad_url = quote(name.lower(), safe="")
    d = _att(description)
    ml = _att(str(master_language or "").upper())
    if tip == "ddls":
        govde = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                 '<ddl:ddlSource xmlns:ddl="http://www.sap.com/adt/ddic/ddlsources"\n'
                 '                xmlns:adtcore="http://www.sap.com/adt/core"\n'
                 f'                adtcore:name="{_att(ad)}"\n'
                 f'                adtcore:description="{d}"\n'
                 f'                adtcore:masterLanguage="{ml}">\n'
                 + _paket_ref_tam(package) + '</ddl:ddlSource>')
        return KabukIstegi(tip, "/sap/bc/adt/ddic/ddl/sources",
                           "application/vnd.sap.adt.ddlSource+xml; charset=utf-8",
                           "application/vnd.sap.adt.ddlSource+xml", govde,
                           f"/sap/bc/adt/ddic/ddl/sources/{ad_url}",
                           "kaynak çekirdek scripts/populate_cds_views.py:291-302,366-378 (yalnız metadata kabuk) · "
                           "playbook/adt-cds.md:196-199,239-257")
    if tip == "srvd":
        govde = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                 '<srvd:srvdSource xmlns:srvd="http://www.sap.com/adt/ddic/srvdsources"\n'
                 '                 xmlns:adtcore="http://www.sap.com/adt/core"\n'
                 f'                 adtcore:name="{_att(ad)}"\n'
                 f'                 adtcore:description="{d}"\n'
                 '                 adtcore:type="SRVD/SRV"\n'
                 '                 srvd:srvdSourceType="S"\n'
                 f'                 adtcore:masterLanguage="{ml}">\n'
                 + _paket_ref_tam(package) + '</srvd:srvdSource>')
        return KabukIstegi(tip, "/sap/bc/adt/ddic/srvd/sources",
                           "application/vnd.sap.adt.ddic.srvd.v1+xml; charset=utf-8",
                           "application/vnd.sap.adt.ddic.srvd.v1+xml", govde,
                           f"/sap/bc/adt/ddic/srvd/sources/{ad_url}",
                           "kaynak çekirdek scripts/create_rap_service.py:113-127,320-333 · playbook/adt-rap.md:157-163")
    if tip == "bdef":
        govde = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                 '<blue:blueSource xmlns:blue="http://www.sap.com/wbobj/blue"\n'
                 '                 xmlns:adtcore="http://www.sap.com/adt/core"\n'
                 f'                 adtcore:name="{_att(ad)}"\n'
                 f'                 adtcore:description="{d}"\n'
                 '                 adtcore:type="BDEF/BDO"\n'
                 f'                 adtcore:masterLanguage="{ml}">\n'
                 + _paket_ref_tam(package) + '</blue:blueSource>')
        return KabukIstegi(tip, "/sap/bc/adt/bo/behaviordefinitions",
                           "application/vnd.sap.adt.blues.v1+xml; charset=utf-8",
                           "application/vnd.sap.adt.blues.v1+xml", govde,
                           f"/sap/bc/adt/bo/behaviordefinitions/{ad_url}",
                           "kaynak çekirdek scripts/create_rap_service.py:372-406 ('blues' reçetesi) · "
                           "playbook/adt-rap.md:90-97,190-197")
    if tip == "fugr":
        govde = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                 '<group:abapFunctionGroup xmlns:group="http://www.sap.com/adt/functions/groups"\n'
                 '                         xmlns:adtcore="http://www.sap.com/adt/core"\n'
                 f'                         adtcore:name="{_att(ad)}"\n'
                 f'                         adtcore:description="{d}"\n'
                 f'                         adtcore:masterLanguage="{ml}">\n'
                 + _paket_ref_tam(package) + '</group:abapFunctionGroup>')
        return KabukIstegi(tip, "/sap/bc/adt/functions/groups",
                           "application/vnd.sap.adt.functions.groups.v2+xml",
                           "application/vnd.sap.adt.functions.groups.v2+xml", govde,
                           f"/sap/bc/adt/functions/groups/{ad_url}",
                           "playbook/adt-fugr-functions.md:27-47")
    if tip == "func":
        fg_url = quote(extra["function_group"].lower(), safe="")
        govde = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                 '<fmodule:abapFunctionModule xmlns:fmodule="http://www.sap.com/adt/functions/fmodules"\n'
                 '                            xmlns:adtcore="http://www.sap.com/adt/core"\n'
                 f'                            adtcore:name="{_att(ad)}"\n'
                 f'                            adtcore:description="{d}"\n'
                 f'                            adtcore:masterLanguage="{ml}">\n'
                 '</fmodule:abapFunctionModule>')
        return KabukIstegi(tip, f"/sap/bc/adt/functions/groups/{fg_url}/fmodules",
                           "application/vnd.sap.adt.functions.fmodules+xml",
                           "application/vnd.sap.adt.functions.fmodules.v2+xml", govde,
                           f"/sap/bc/adt/functions/groups/{fg_url}/fmodules/{ad_url}",
                           "playbook/adt-fugr-functions.md:51-72")
    if tip == "msag":
        govde = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                 '<mc:messageClass xmlns:mc="http://www.sap.com/adt/MessageClass"\n'
                 '                 xmlns:adtcore="http://www.sap.com/adt/core"\n'
                 f'                 adtcore:name="{_att(ad)}"\n'
                 f'                 adtcore:description="{d}">\n'
                 f'    <adtcore:packageRef adtcore:name="{_att(package.upper())}"/>\n'
                 '</mc:messageClass>')
        return KabukIstegi(tip, "/sap/bc/adt/messageclass",
                           "application/vnd.sap.adt.messageclass.v2+xml", "*/*", govde,
                           f"/sap/bc/adt/messageclass/{ad_url}",
                           "lib/sap_client.py:2590-2661 (create_message_class; stateless POST) · "
                           "kaynak çekirdek playbook/adt-message-class.md:24-38",
                           ek_basliklar={"x-sap-adt-sessiontype": "stateless"})
    if tip == "enqu":
        tablo = _att(extra["primary_table"])
        param = "".join(
            '\n            <enqu:lockParameter>\n'
            '                <enqu:parameterWanted>true</enqu:parameterWanted>\n'
            f'                <enqu:parameterName>{_att(a)}</enqu:parameterName>\n'
            f'                <enqu:tableName>{tablo}</enqu:tableName>\n'
            f'                <enqu:fieldName>{_att(a)}</enqu:fieldName>\n'
            '            </enqu:lockParameter>' for a in extra["lock_fields"])
        govde = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                 '<enqu:lockobject xmlns:enqu="http://www.sap.com/adt/ddic/enqu"\n'
                 '                 xmlns:adtcore="http://www.sap.com/adt/core"\n'
                 f'                 adtcore:name="{_att(ad)}"\n'
                 f'                 adtcore:description="{d}">\n'
                 f'    <adtcore:packageRef adtcore:name="{_att(package.upper())}"/>\n'
                 '    <enqu:content>\n'
                 f'        <enqu:allowRFC>{"true" if extra["allow_rfc"] else "false"}</enqu:allowRFC>\n'
                 '        <enqu:primaryTable>\n'
                 f'            <enqu:tableName>{tablo}</enqu:tableName>\n'
                 f'            <enqu:lockMode>{_att(extra["lock_mode"])}</enqu:lockMode>\n'
                 '        </enqu:primaryTable>\n'
                 '        <enqu:secondaryTables/>\n'
                 f'        <enqu:lockParameters>{param}\n'
                 '        </enqu:lockParameters>\n'
                 '    </enqu:content>\n'
                 '</enqu:lockobject>')
        return KabukIstegi(tip, "/sap/bc/adt/ddic/lockobjects/sources",
                           "application/vnd.sap.adt.lockobjects.v1+xml", "*/*", govde,
                           f"/sap/bc/adt/ddic/lockobjects/sources/{ad_url}",
                           "lib/sap_client.py:2663-2756 (create_lock_object) · kaynak çekirdek "
                           "playbook/adt-lock-objects.md:33-43,90-94 (canlı doğrulandı 2026-06-18)")
    if tip == "ttyp":
        govde = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                 '<ttyp:tableType xmlns:ttyp="http://www.sap.com/dictionary/tabletype"\n'
                 '                xmlns:adtcore="http://www.sap.com/adt/core"\n'
                 f'                adtcore:name="{_att(ad)}"\n'
                 f'                adtcore:description="{d}">\n'
                 f'    <adtcore:packageRef adtcore:name="{_att(package.upper())}"/>\n'
                 '    <ttyp:rowType>\n'
                 '        <ttyp:typeKind>dictionaryType</ttyp:typeKind>\n'
                 f'        <ttyp:typeName>{_att(extra["row_type"])}</ttyp:typeName>\n'
                 '        <ttyp:builtInType><ttyp:dataType/><ttyp:length>000000</ttyp:length>'
                 '<ttyp:decimals>000000</ttyp:decimals></ttyp:builtInType>\n'
                 '        <ttyp:rangeType/>\n'
                 '    </ttyp:rowType>\n'
                 '    <ttyp:initialRowCount>00000</ttyp:initialRowCount>\n'
                 '    <ttyp:accessType>standard</ttyp:accessType>\n'
                 '    <ttyp:primaryKey>\n'
                 '        <ttyp:definition>standard</ttyp:definition>\n'
                 '        <ttyp:kind>nonUnique</ttyp:kind>\n'
                 '        <ttyp:components/>\n'
                 '        <ttyp:alias/>\n'
                 '    </ttyp:primaryKey>\n'
                 '</ttyp:tableType>')
        return KabukIstegi(tip, "/sap/bc/adt/ddic/tabletypes",
                           "application/vnd.sap.adt.tabletype.v1+xml",
                           "application/vnd.sap.adt.tabletype.v1+xml, */*", govde,
                           f"/sap/bc/adt/ddic/tabletypes/{ad_url}",
                           "kaynak çekirdek playbook/adt-tables-structures.md:254-293,359-370")
    raise KabukHatasi("unsupported_type", f"kabuk reçetesi yok: {tip}")


def gonder(adt, ist: KabukIstegi, transport: str) -> tuple[int, str]:
    """POST'u gönder → (HTTP durum, gövde). Ağ istisnası yukarı çıkar (çağıran belirsiz sayar)."""
    basliklar = adt._get_headers(ist.accept, ist.content_type)
    basliklar.update(ist.ek_basliklar)
    r = adt._request_with_csrf_retry("post", adt.url + ist.path, headers=basliklar,
                                     params={"corrNr": transport} if transport else {}, data=ist.govde.encode("utf-8"))
    return int(getattr(r, "status_code", 0) or 0), str(getattr(r, "text", "") or "")


def sonuc_sinifi(status: int, govde: str) -> str:
    """`created` | `already_exists` | `failed`."""
    if status in (200, 201):
        return "created"
    if "alreadyexists" in (govde or "").lower():
        return "already_exists"
    return "failed"


_ML = re.compile(r'masterLanguage="(\w+)"')


def master_language_oku(metin) -> str | None:
    m = _ML.search(metin or "") if isinstance(metin, str) else None
    return m.group(1).upper() if m else None
