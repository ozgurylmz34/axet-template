# -*- coding: utf-8 -*-
"""Z194 (2026-10-19) — yaratma/yazma gövdelerinde XML kaçışı TEK KAYNAK + sorumlu çözülemezse istek yok.

Kaynak çekirdek kuralı (`scripts/utils/xml_kacis.py`): `adtcore:description` / `adtcore:responsible` öznitelikleri ve DTEL
etiketleri kaçışsız yazılıyordu; `&`, `<` ya da `"` içeren metin gövdeyi iyi biçimli olmaktan çıkarıyordu.
Sorumlu çözülemeyince f-string `adtcore:responsible="None"` yazıyordu.

Testler gerçek kütüphane metodunu sahte bir oturuma (istekleri kaydeden `session`) karşı koşar ve
gönderilen gövdeyi XML ayrıştırıcısından geçirir: değer AYNEN geri okunmalı. SAP'ye bağlanmaz.
"""
from __future__ import annotations

import sys
import unittest
import xml.etree.ElementTree as ET

import _helpers as H

sys.dont_write_bytecode = True
LIB = H.SCRIPTS / "sapadt" / "lib"
for _p in (H.SCRIPTS, LIB):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import sapadt  # noqa: E402,F401  (lib yolunu hazırlar)
import sap_adt_lib  # noqa: E402
from sap_adt_lib import SAPADTClient, SAPValidationError  # noqa: E402
from utils import xml_kacis  # noqa: E402

NS_AC = "http://www.sap.com/adt/core"
NS_DTEL = "http://www.sap.com/adt/dictionary/dataelements"
ZOR = 'Ür & <b> "tırnak" \'tek\' >son'      # öznitelik + eleman metni için zor vektör
ZOR_SORUMLU = 'AX&<"\'U'


class _Yanit:
    def __init__(self, kod=201, metin="", basliklar=None):
        self.status_code = kod
        self.text = metin
        self.content = metin.encode("utf-8")
        self.headers = basliklar or {}


class _SahteOturum:
    """Gönderilen her isteği kaydeder; plan boşsa 201 döner."""

    def __init__(self):
        self.cagri: list[dict] = []
        self.plan: list = []

    def _kaydet(self, method, url, data=None, params=None, headers=None, **kw):
        govde = data.decode("utf-8") if isinstance(data, bytes) else data
        self.cagri.append({"method": method, "url": url, "data": govde, "params": dict(params or {})})
        if self.plan:
            kod, metin = self.plan.pop(0)
            return _Yanit(kod, metin)
        return _Yanit(201, "", {"Location": "/x"})

    def post(self, url, **kw):
        return self._kaydet("POST", url, **kw)

    def get(self, url, **kw):
        return self._kaydet("GET", url, **kw)

    def request(self, method, url, **kw):
        return self._kaydet(method.upper(), url, **kw)


def _istemci(user="AXETTEST", csrf="T") -> SAPADTClient:
    c = SAPADTClient.__new__(SAPADTClient)
    c.url = "http://127.0.0.1:9"
    c.client = "100"
    c.language = "TR"
    c.user = user
    c.csrf_token = csrf
    c.timeout_default = 5
    c.debug_enabled = False
    c.session = _SahteOturum()
    c.csrf_cagrisi = 0

    def _fetch(force_refresh=False):
        c.csrf_cagrisi += 1
        c.csrf_token = "T"
    c.fetch_csrf_token = _fetch
    c._get_headers = lambda accept_type=None, content_type=None: {"Accept": accept_type or "x"}
    c._get_auth_header = lambda: "Basic x"
    c._retry_request = lambda f, operation="": f()
    c._son_yeniden_denemeler = []
    c._request_with_csrf_retry = lambda method, url, headers=None, timeout=None, **kw: getattr(
        c.session, method.lower())(url, headers=headers, **kw)
    return c


class XmlKacis(unittest.TestCase):
    def kaydet(self, ad, beklenen, gercek, ok):
        H.kaydet(f"XML-KACIS {ad}", beklenen, str(gercek)[:160], ok)
        self.assertTrue(ok, f"{ad}: {gercek}")

    # ── birim: ortak yardımcı ───────────────────────────────────────────────────────────────
    def test_xml_kacis_yardimci_oznitelik_ve_metin(self):
        a = xml_kacis.attr_escape('a&<>"\t\n\r\'')
        m = xml_kacis.text_escape('a&<>"')
        kok = ET.fromstring(f'<k x="{a}">{m}</k>')
        ok = (kok.get("x") == 'a&<>"\t\n\r\'' and kok.text == 'a&<>"'
              and xml_kacis.attr_escape(None) == "" and xml_kacis.text_escape(None) == "")
        self.kaydet("yardımcı: öznitelik + eleman metni geri okunur · None → boş", "aynen", [a, m], ok)

    def test_xml_kacis_sorumlu_coz(self):
        class _C:
            user = "  "
        sonuc = (xml_kacis.sorumlu_coz("U1", _C()), xml_kacis.sorumlu_coz(None, _C()),
                 xml_kacis.sorumlu_coz(None, object()), xml_kacis.sorumlu_coz("", type("C", (), {"user": "B"})()))
        self.kaydet("sorumlu_coz: verilen > bağlantı · boş/yok → None", "('U1', None, None, 'B')", sonuc,
                    sonuc == ("U1", None, None, "B"))

    def test_xml_kacis_dort_kopya_tek_kaynaga_indi(self):
        """Eski yerel kaçış kopyaları ortak yardımcıya bağlı (kimlik karşılaştırması)."""
        from sapadt.tools import msgclass, shells
        from utils import ddic_ttyp
        kaynak = (H.SCRIPTS / "sapadt" / "lib" / "sap_adt_lib.py").read_text(encoding="utf-8")
        yerel = [s for s in ("_att = lambda", "esc = lambda", "escape as _xe", "escape as _xml_escape")
                 if s in kaynak]
        ok = (msgclass._att is xml_kacis.attr_escape and shells._att is xml_kacis.attr_escape
              and ddic_ttyp._att is xml_kacis.attr_escape
              and SAPADTClient._xml_escape('a"<') == xml_kacis.attr_escape('a"<') and not yerel)
        self.kaydet("yerel kaçış kopyaları → utils.xml_kacis", "tek kaynak · yerel kopya 0", yerel, ok)

    # ── create_object (CLAS/INTF/PROG/INCL) ─────────────────────────────────────────────────
    def test_xml_kacis_create_object_govde_ayristirilir(self):
        sonuc = {}
        for tip in ("CLAS/OC", "INTF/OI", "PROG/P", "PROG/I"):
            c = _istemci()
            c.create_object(tip, "ZCL_X", "ZPKG", ZOR, "/sap/bc/adt/packages/zpkg", responsible=ZOR_SORUMLU)
            post = [x for x in c.session.cagri if x["method"] == "POST"]
            kok = ET.fromstring(post[0]["data"].encode("utf-8"))
            sonuc[tip] = (len(post), kok.get(f"{{{NS_AC}}}description") == ZOR,
                          kok.get(f"{{{NS_AC}}}responsible") == ZOR_SORUMLU)
        ok = all(v == (1, True, True) for v in sonuc.values())
        self.kaydet("create_object 4 tip: açıklama + sorumlu aynen geri okunur", "(1, True, True)", sonuc, ok)

    def test_xml_kacis_create_object_sorumlu_bos_istek_gitmez(self):
        c = _istemci(user="", csrf=None)
        try:
            c.create_object("CLAS/OC", "ZCL_X", "ZPKG", "Açıklama", "/sap/bc/adt/packages/zpkg")
            hata = None
        except SAPValidationError as e:
            hata = str(e)
        ok = (hata is not None and "responsible" in hata and len(c.session.cagri) == 0
              and c.csrf_cagrisi == 0 and "None" not in (hata or "").split("ÇÖZÜLEMEDİ")[0])
        self.kaydet("create_object sorumlu boş → SAPValidationError · 0 istek · CSRF yok", "0 istek",
                    [hata, len(c.session.cagri), c.csrf_cagrisi], ok)

    def test_xml_kacis_sap_client_create_object_hatayi_yutmaz(self):
        """SAPClient.create_object genel `except` ile yutsaydı araç katmanı varlık sondası için ağa çıkardı."""
        from sap_client import SAPClient
        s = SAPClient.__new__(SAPClient)
        s.adt_client = _istemci(user="", csrf=None)
        s.debug_enabled = False
        try:
            s.create_object("class", "ZCL_X", "ZPKG", "Açıklama")
            sonuc = "yutuldu"
        except SAPValidationError:
            sonuc = "SAPValidationError"
        self.kaydet("SAPClient.create_object sorumlu boş → hata yükselir (yutulmaz)", "SAPValidationError",
                    [sonuc, len(s.adt_client.session.cagri)], sonuc == "SAPValidationError"
                    and len(s.adt_client.session.cagri) == 0)

    # ── DTEL: öznitelik + dört etiket (eleman metni) ────────────────────────────────────────
    def test_xml_kacis_dtel_govde_ayristirilir(self):
        c = _istemci(user=ZOR_SORUMLU)
        c._get_domain_typeinfo = lambda d: ("CHAR", "000010", "000000")
        etiket = 'A&<"b'
        c.create_dataelement("ZDE_X", "ZDO_X", ZOR, "ZPKG", short_label=etiket, medium_label=etiket,
                             long_label=etiket, heading_label=etiket)
        post = [x for x in c.session.cagri if x["method"] == "POST"]
        kok = ET.fromstring(post[0]["data"].encode("utf-8"))
        de = kok.find(f"{{{NS_DTEL}}}dataElement")
        etiketler = [de.find(f"{{{NS_DTEL}}}{e}FieldLabel").text for e in ("short", "medium", "long", "heading")]
        uzunluk = de.find(f"{{{NS_DTEL}}}shortFieldLength").text
        ok = (kok.get(f"{{{NS_AC}}}description") == ZOR and kok.get(f"{{{NS_AC}}}responsible") == ZOR_SORUMLU
              and etiketler == [etiket] * 4 and uzunluk == str(len(etiket)))
        self.kaydet("DTEL: açıklama + sorumlu + 4 etiket aynen · uzunluk ham metinden", "aynen",
                    [etiketler, uzunluk], ok)

    def test_xml_kacis_dtel_sorumlu_bos_istek_gitmez(self):
        c = _istemci(user=None, csrf=None)
        c._get_domain_typeinfo = lambda d: self.fail("domain okuması da ağa çıkar — olmamalı")
        with self.assertRaises(SAPValidationError):
            c.create_dataelement("ZDE_X", "ZDO_X", "Açıklama", "ZPKG")
        self.kaydet("DTEL sorumlu boş → 0 istek · CSRF yok", "0", [len(c.session.cagri), c.csrf_cagrisi],
                    len(c.session.cagri) == 0 and c.csrf_cagrisi == 0)

    # ── tek satırlık açıklama gövdeleri (FUGR / FM) ─────────────────────
    def test_xml_kacis_diger_yaratma_govdeleri(self):
        sonuc = {}
        c = _istemci()
        c.create_function_group("ZFG_X", ZOR, "ZPKG", transport="TRK900001")
        c.create_function_module("ZFM_X", "ZFG_X", ZOR, transport="TRK900001")
        for x in c.session.cagri:
            if x["method"] != "POST":
                continue
            try:
                kok = ET.fromstring(x["data"].encode("utf-8"))
                sonuc[x["url"].rsplit("/", 2)[-2] + "/" + x["url"].rsplit("/", 1)[-1]] = \
                    kok.get(f"{{{NS_AC}}}description") == ZOR
            except ET.ParseError as e:
                sonuc[x["url"]] = f"ParseError {e}"
        ok = len(sonuc) == 2 and all(v is True for v in sonuc.values())
        self.kaydet("FUGR + FM gövdesi ayrıştırılır, açıklama aynen", "2 × True", sonuc, ok)

    def test_xml_kacis_transport_tablosu_yerel_xml(self):
        """E070 yedeği: SAP'den gelen AS4TEXT `&` içerse bile üretilen yerel XML ayrıştırılır."""
        dp = "http://www.sap.com/adt/dataPreview"
        kolon = {"TRKORR": "TRK900001", "AS4USER": "U&1", "AS4TEXT": 'İş & "test" <x>', "TRFUNCTION": "K",
                 "TRSTATUS": "D", "AS4DATE": "2026-10-19", "AS4TIME": "10:00:00", "TARSYSTEM": "Q<1"}
        govde = f'<dp:tableData xmlns:dp="{dp}">' + "".join(
            f'<dp:columns><dp:metadata dp:name="{k}"/><dp:dataSet><dp:data>{xml_kacis.text_escape(v)}</dp:data>'
            f'</dp:dataSet></dp:columns>' for k, v in kolon.items()) + "</dp:tableData>"
        c = _istemci(user='A"B')
        c.session.plan = [(200, govde)]
        xml = c.user_transports_from_table()
        kok = ET.fromstring(xml.encode("utf-8"))
        istek = kok.find(".//{http://www.sap.com/cts/adt/tm}request")
        tm = "{http://www.sap.com/cts/adt/tm}"
        ok = (istek is not None and istek.get(f"{tm}desc") == kolon["AS4TEXT"]
              and istek.get(f"{tm}owner") == "U&1" and istek.get(f"{tm}target") == "Q<1"
              and kok.get(f"{{{NS_AC}}}name") == 'A"B')
        self.kaydet("E070 yedeği yerel XML: desc/owner/target/kullanıcı aynen", "aynen",
                    None if istek is None else istek.attrib, ok)


if __name__ == "__main__":
    unittest.main()
