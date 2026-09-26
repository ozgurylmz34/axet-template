# -*- coding: utf-8 -*-
"""Aktivasyon ve sözdizimi hükmü — sahte-sonuç düzeltmelerinin çevrimdışı kontrol grubu.

Ölçülen sınıf: aktivasyon yanıt GÖVDESİ hüküm taşımadığında ("yalnız generation çalıştı" ya da
hiç bayrak yok) katmanlar birbirinden farklı ve kanıtsız karar veriyordu:
  · lib `activate_object`: yalnız-generation gövdesi → BAŞARI (obje worklist'te inaktif kalırken)
  · `rap_service._activation_failures`: bayraksız ADT gövdesi → BAŞARI
  · `syntax_check_via_activation`: boş/kısa gövde ve "kontrol koşmadı" gövdesi → `valid: True`
Tek sözleşme: `sap_adt_lib.aktivasyon_govde_hukmu` → True / False / None. None iken karar
BAĞIMSIZ worklist sondasınındır; sonda ölçemezse (HTTP hata, istisna, ioc olmayan ya da
ayrıştırılamayan gövde) sonuç ASLA başarı değildir.

Tablo (a)-(d), iki gövde (bayraksız · yalnız generation) × üç yol (lib · rap_service · ENQU):
  (a) gövde + sonda "listede değil" → başarı
  (b) gövde + sonda "listede"       → FAIL
  (c) gövde + sonda ölçemedi        → başarı DEĞİL (dört alt vaka)
  (d) kontrol: bayraklı başarı gövdesi → başarı · bayraklı hata gövdesi → FAIL

Gerçek SAP'ye bağlanılmaz: HTTP katmanı sahte oturumdur, mantık testte yeniden yazılmaz.
Canlı biçimli gövdeler nötr adlarla (ZBC000_*, ZCL_BC000_DEMO_*, TESTK9000xx) kısaltıldı.
"""
from __future__ import annotations

import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import _helpers as H

sys.dont_write_bytecode = True
LIB = H.SCRIPTS / "sapadt" / "lib"
for _p in (H.SCRIPTS, LIB):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import sapadt  # noqa: E402,F401  (lib yolunu hazırlar)
import sap_adt_lib as L  # noqa: E402
import rap_service as R  # noqa: E402

URL = "https://example.invalid:44300"
IOC = "http://www.sap.com/abapxml/inactiveCtsObjects"
CHKL = "http://www.sap.com/abapxml/checklist"
ADTCORE = "http://www.sap.com/adt/core"

SINIF_A = "ZCL_BC000_DEMO_A"
SINIF_A_URI = "/sap/bc/adt/oo/classes/zcl_bc000_demo_a"
KILIT = "EZBC000_DEMO"
KILIT_URI = "/sap/bc/adt/ddic/lockobjects/sources/ezbc000_demo"


def _chkl(ce=None, ae=None, ge=None, mesajlar=""):
    bayrak = "".join(' %s="%s"' % (ad, "true" if v else "false")
                     for ad, v in (("checkExecuted", ce), ("activationExecuted", ae),
                                   ("generationExecuted", ge)) if v is not None)
    ozellik = "<chkl:properties%s/>" % bayrak if bayrak else ""
    return ('<?xml version="1.0" encoding="utf-8"?><chkl:messages xmlns:chkl="%s">%s%s'
            '</chkl:messages>' % (CHKL, ozellik, mesajlar))


def _msg(tip, metin, attr="type"):
    return ('<msg objDescr="Sinif %s" %s="%s" line="1" href="%s/source/main#start=1,0">'
            '<shortText><txt>%s</txt></shortText></msg>' % (SINIF_A, attr, tip, SINIF_A_URI, metin))


# Canlı biçimli gövdeler (bayrak üçlüsü canlı yanıtlardan; ad/kullanıcı nötr).
GOVDE_TRUE = _chkl(ce=True, ae=True, ge=False)
GOVDE_HEPSI_TRUE = _chkl(ce=True, ae=True, ge=True)
GOVDE_YALNIZ_GENERATION = _chkl(ce=False, ae=False, ge=True)
GOVDE_BAYRAKSIZ = _chkl()
GOVDE_HATA = _chkl(ce=True, ae=False, ge=False, mesajlar=_msg("E", "Sozdizimi hatasi"))
GOVDE_AKTIVASYON_YOK = _chkl(ce=True, ae=False, ge=False)


def _worklist(*girdiler):
    """girdiler: (uri, tip, ad[, parent_uri]) → `ioc:inactiveObjects` gövdesi (bir transport girdisiyle)."""
    parca = ['<ioc:entry><ioc:object/><ioc:transport ioc:user="TESTUSER_B" ioc:linked="false">'
             '<ioc:ref adtcore:uri="/sap/bc/adt/cts/transportrequests/TESTK900001" adtcore:type="/RQ" '
             'adtcore:name="TESTK900001" xmlns:adtcore="%s"/></ioc:transport></ioc:entry>' % ADTCORE]
    for g in girdiler:
        uri, tip, ad = g[0], g[1], g[2]
        ebeveyn = (' adtcore:parentUri="%s"' % g[3]) if len(g) > 3 else ""
        parca.append('<ioc:entry><ioc:object ioc:user="TESTUSER_A" ioc:deleted="false"><ioc:ref '
                     'adtcore:uri="%s" adtcore:type="%s" adtcore:name="%s"%s xmlns:adtcore="%s"/>'
                     '</ioc:object><ioc:transport/></ioc:entry>' % (uri, tip, ad, ebeveyn, ADTCORE))
    return ('<?xml version="1.0" encoding="utf-8"?><ioc:inactiveObjects xmlns:ioc="%s">%s'
            '</ioc:inactiveObjects>' % (IOC, "".join(parca)))


# Sonda "listede DEĞİL": liste dolu ama hedef yok (ayırt edici ölçüm).
WL_HEDEF_YOK = _worklist(("/sap/bc/adt/oo/classes/zcl_bc000_demo_b", "CLAS/OC", "ZCL_BC000_DEMO_B"),
                         ("/sap/bc/adt/ddic/lockobjects/sources/ezbc000_diger", "ENQU/DL", "EZBC000_DIGER"))
# Sonda "listede": hedefler hâlâ inaktif.
WL_HEDEF_VAR = _worklist((SINIF_A_URI, "CLAS/OC", SINIF_A),
                         (KILIT_URI, "ENQU/DL", KILIT))

# FUGR canlı biçimi: 1. faz ioc yanıtında FF YOK (yalnız F iki kez); worklist'te FF parentUri'li.
FG = "ZBC000_FG_DEMO"
FG_URI = "/sap/bc/adt/functions/groups/zbc000_fg_demo"
FAZ1_IOC = ('<?xml version="1.0" encoding="utf-8"?><ioc:inactiveObjects xmlns:ioc="%s">'
            '<ioc:entry><ioc:object ioc:user="TESTUSER_A" ioc:deleted="false"><ioc:ref adtcore:uri="%s" '
            'adtcore:type="FUGR/F" adtcore:name="%s" xmlns:adtcore="%s"/></ioc:object><ioc:transport/></ioc:entry>'
            '<ioc:entry><ioc:object ioc:user="" ioc:deleted="false"><ioc:ref adtcore:uri="%s/source/main" '
            'adtcore:type="FUGR/F" adtcore:name="%s" adtcore:parentUri="%s" xmlns:adtcore="%s"/></ioc:object>'
            '<ioc:transport/></ioc:entry></ioc:inactiveObjects>'
            % (IOC, FG_URI, FG, ADTCORE, FG_URI, FG, FG_URI, ADTCORE))
WL_FUGR_FF = _worklist((FG_URI, "FUGR/F", FG),
                       (FG_URI + "/fmodules/zbc000_fm_demo_iki", "FUGR/FF", "ZBC000_FM_DEMO_IKI", FG_URI))
# Aynı adlı FM ve grup (canlıda ölçüldü): FUGR/F + FUGR/FF ikisi de ZBC000_FM_DEMO.
WL_AYNI_AD = _worklist(("/sap/bc/adt/functions/groups/zbc000_fm_demo", "FUGR/F", "ZBC000_FM_DEMO"),
                       ("/sap/bc/adt/functions/groups/zbc000_fm_demo/fmodules/zbc000_fm_demo", "FUGR/FF",
                        "ZBC000_FM_DEMO", "/sap/bc/adt/functions/groups/zbc000_fm_demo"))


class _Yanit:
    def __init__(self, status_code=200, text="", headers=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}
        self.content = text.encode("utf-8")


# (c) sonda ölçemedi — dört alt vaka
SONDA_OLCULEMEDI = (
    ("http_500", _Yanit(500, "Internal Server Error")),
    ("istisna", ConnectionError("ag yok")),
    ("ioc_olmayan_200", _Yanit(200, '<?xml version="1.0"?><root/>')),
    ("ayristirilamaz_200", _Yanit(200, "<<< ayristirilamaz govde")),
)


class _Oturum:
    """POST'lar sırayla yanıtlanır (liste biterse son yanıt tekrarlanır); GET = worklist."""

    def __init__(self, post_yanitlari, worklist):
        self._post = list(post_yanitlari)
        self._worklist = worklist
        self.postlar: list = []
        self.getler: list = []
        self.headers: dict = {}
        self.verify = False

    def request(self, method, url, headers=None, timeout=None, **kw):
        if method.lower() == "get":
            return self.get(url, headers=headers, **kw)
        return self.post(url, headers=headers, **kw)

    def post(self, url, headers=None, data=None, params=None, **kw):
        self.postlar.append({"url": url, "data": data if isinstance(data, str) else
                             (data or b"").decode("utf-8"), "params": dict(params or {})})
        return self._post[min(len(self.postlar), len(self._post)) - 1]

    def get(self, url, headers=None, params=None, **kw):
        self.getler.append(url)
        if isinstance(self._worklist, BaseException):
            raise self._worklist
        return self._worklist


def _lib_client(post_yanitlari, worklist):
    c = L.SAPADTClient.__new__(L.SAPADTClient)
    c.url = URL
    c.session = _Oturum(post_yanitlari, worklist)
    c.csrf_token = "TOKEN"
    c.timeout_default = 30
    c.timeout_short = 5
    c.debug_enabled = False
    c.user = "TESTUSER_A"
    c._update_cookies = lambda r: None
    c._get_headers = lambda *a, **k: {}
    c.fetch_csrf_token = lambda *a, **k: None
    return c


def _sessiz(fn, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **k)


# ── Yol koşucuları: her biri (başarı: bool, ayrıntı) döndürür ─────────────────────────────────
def _yol_lib(govde, worklist):
    c = _lib_client([_Yanit(200, govde)], worklist)
    sonuc = _sessiz(c.activate_object, SINIF_A, SINIF_A_URI)
    return sonuc.get("success") is True, sonuc


def _yol_rap(govde, worklist):
    c = _lib_client([_Yanit(200, govde)], worklist)
    try:
        donus = _sessiz(R.activate_and_verify, c, "TOKEN", [(SINIF_A_URI, SINIF_A)])
    except RuntimeError as exc:
        return False, str(exc)
    return donus is True, donus


def _yol_enqu(govde, worklist):
    from sapadt.tools import atom
    c = _lib_client([_Yanit(200, govde)], worklist)
    resp = atom._kilit_objesi_aktive_et(c, KILIT, "enqu")
    return (resp.get("ok") is True and resp.get("activated") is True), resp


class _Kayit(unittest.TestCase):
    def kaydet(self, ad, beklenen, gercek, ok):
        H.kaydet(f"HÜKÜM {ad}", beklenen, str(gercek)[:160], ok)
        self.assertTrue(ok, f"{ad}: {gercek}")

    def basari(self, ad, yol, govde, worklist):
        ok, ayrinti = yol(govde, worklist)
        self.kaydet(ad, "başarı", ayrinti, ok)

    def fail(self, ad, yol, govde, worklist):
        ok, ayrinti = yol(govde, worklist)
        self.kaydet(ad, "FAIL", ayrinti, not ok)

    def olculemedi_basari_degil(self, ad, yol, govde):
        for alt, worklist in SONDA_OLCULEMEDI:
            with self.subTest(alt=alt):
                ok, ayrinti = yol(govde, worklist)
                self.kaydet(f"{ad} [{alt}]", "başarı DEĞİL", ayrinti, not ok)


# ══════════════════════════════════════════════════════════════════════════════════════════════
# TABLO (a)-(d) — lib `SAPADTClient.activate_object`
# ══════════════════════════════════════════════════════════════════════════════════════════════
class TabloLib(_Kayit):
    def test_lib_bayraksiz_a_sonda_listede_degil_basari(self):
        self.basari("lib bayraksız (a)", _yol_lib, GOVDE_BAYRAKSIZ, _Yanit(200, WL_HEDEF_YOK))

    def test_lib_bayraksiz_b_sonda_listede_fail(self):
        self.fail("lib bayraksız (b)", _yol_lib, GOVDE_BAYRAKSIZ, _Yanit(200, WL_HEDEF_VAR))

    def test_lib_bayraksiz_c_sonda_olculemedi_basari_degil(self):
        self.olculemedi_basari_degil("lib bayraksız (c)", _yol_lib, GOVDE_BAYRAKSIZ)

    def test_lib_generation_a_sonda_listede_degil_basari(self):
        self.basari("lib yalnız-generation (a)", _yol_lib, GOVDE_YALNIZ_GENERATION, _Yanit(200, WL_HEDEF_YOK))

    def test_lib_generation_b_sonda_listede_fail(self):
        self.fail("lib yalnız-generation (b)", _yol_lib, GOVDE_YALNIZ_GENERATION, _Yanit(200, WL_HEDEF_VAR))

    def test_lib_generation_c_sonda_olculemedi_basari_degil(self):
        self.olculemedi_basari_degil("lib yalnız-generation (c)", _yol_lib, GOVDE_YALNIZ_GENERATION)

    def test_lib_d_bayrakli_basari_govdesi_basari(self):
        self.basari("lib bayraklı başarı (d)", _yol_lib, GOVDE_TRUE, _Yanit(200, WL_HEDEF_YOK))

    def test_lib_d_bayrakli_hata_govdesi_fail(self):
        self.fail("lib bayraklı hata (d)", _yol_lib, GOVDE_HATA, _Yanit(200, WL_HEDEF_YOK))


# ══════════════════════════════════════════════════════════════════════════════════════════════
# TABLO (a)-(d) — `rap_service.activate_and_verify` (atom `also=` ve `srvb` yolu)
# ══════════════════════════════════════════════════════════════════════════════════════════════
class TabloRap(_Kayit):
    def test_rap_bayraksiz_a_sonda_listede_degil_basari(self):
        self.basari("rap bayraksız (a)", _yol_rap, GOVDE_BAYRAKSIZ, _Yanit(200, WL_HEDEF_YOK))

    def test_rap_bayraksiz_b_sonda_listede_fail(self):
        self.fail("rap bayraksız (b)", _yol_rap, GOVDE_BAYRAKSIZ, _Yanit(200, WL_HEDEF_VAR))

    def test_rap_bayraksiz_c_sonda_olculemedi_basari_degil(self):
        self.olculemedi_basari_degil("rap bayraksız (c)", _yol_rap, GOVDE_BAYRAKSIZ)

    def test_rap_generation_a_sonda_listede_degil_basari(self):
        self.basari("rap yalnız-generation (a)", _yol_rap, GOVDE_YALNIZ_GENERATION, _Yanit(200, WL_HEDEF_YOK))

    def test_rap_generation_b_sonda_listede_fail(self):
        self.fail("rap yalnız-generation (b)", _yol_rap, GOVDE_YALNIZ_GENERATION, _Yanit(200, WL_HEDEF_VAR))

    def test_rap_generation_c_sonda_olculemedi_basari_degil(self):
        self.olculemedi_basari_degil("rap yalnız-generation (c)", _yol_rap, GOVDE_YALNIZ_GENERATION)

    def test_rap_d_bayrakli_basari_govdesi_basari(self):
        self.basari("rap bayraklı başarı (d)", _yol_rap, GOVDE_TRUE, _Yanit(200, WL_HEDEF_YOK))

    def test_rap_d_bayrakli_hata_govdesi_fail(self):
        self.fail("rap bayraklı hata (d)", _yol_rap, GOVDE_HATA, _Yanit(200, WL_HEDEF_YOK))


# ══════════════════════════════════════════════════════════════════════════════════════════════
# TABLO (a)-(d) — atom ENQU yolu `_kilit_objesi_aktive_et`
# ══════════════════════════════════════════════════════════════════════════════════════════════
class TabloEnqu(_Kayit):
    def test_enqu_bayraksiz_a_sonda_listede_degil_basari(self):
        self.basari("enqu bayraksız (a)", _yol_enqu, GOVDE_BAYRAKSIZ, _Yanit(200, WL_HEDEF_YOK))

    def test_enqu_bayraksiz_b_sonda_listede_fail(self):
        self.fail("enqu bayraksız (b)", _yol_enqu, GOVDE_BAYRAKSIZ, _Yanit(200, WL_HEDEF_VAR))

    def test_enqu_bayraksiz_c_sonda_olculemedi_basari_degil(self):
        self.olculemedi_basari_degil("enqu bayraksız (c)", _yol_enqu, GOVDE_BAYRAKSIZ)

    def test_enqu_generation_a_sonda_listede_degil_basari(self):
        self.basari("enqu yalnız-generation (a)", _yol_enqu, GOVDE_YALNIZ_GENERATION, _Yanit(200, WL_HEDEF_YOK))

    def test_enqu_generation_b_sonda_listede_fail(self):
        self.fail("enqu yalnız-generation (b)", _yol_enqu, GOVDE_YALNIZ_GENERATION, _Yanit(200, WL_HEDEF_VAR))

    def test_enqu_generation_c_sonda_olculemedi_basari_degil(self):
        self.olculemedi_basari_degil("enqu yalnız-generation (c)", _yol_enqu, GOVDE_YALNIZ_GENERATION)

    def test_enqu_d_bayrakli_basari_govdesi_basari(self):
        self.basari("enqu bayraklı başarı (d)", _yol_enqu, GOVDE_TRUE, _Yanit(200, WL_HEDEF_YOK))

    def test_enqu_d_bayrakli_hata_govdesi_fail(self):
        self.fail("enqu bayraklı hata (d)", _yol_enqu, GOVDE_HATA, _Yanit(200, WL_HEDEF_YOK))


# ══════════════════════════════════════════════════════════════════════════════════════════════
# A — gövde hükmü tablosu (tek kaynak)
# ══════════════════════════════════════════════════════════════════════════════════════════════
class GovdeHukmu(_Kayit):
    def test_A_govde_hukmu_tablosu(self):
        hukum = getattr(L, "aktivasyon_govde_hukmu", None)
        self.kaydet("A0 tek kaynak fonksiyon var", "callable", hukum, callable(hukum))
        satirlar = (
            ("A1 boş gövde", "", False, "govde_bos"),
            ("A2 HTML gövde", "<html><body>Logon</body></html>", False, "govde_taninmadi"),
            ("A3 ioc:inactiveObjects", FAZ1_IOC, False, "ioc_inaktif_liste"),
            ("A4 activationExecuted=true", GOVDE_TRUE, True, "activation_executed"),
            ("A5 üç bayrak true", GOVDE_HEPSI_TRUE, True, "activation_executed"),
            ("A6 yalnız generation", GOVDE_YALNIZ_GENERATION, None, "yalniz_generation"),
            ("A7 bayraksız ADT gövdesi", GOVDE_BAYRAKSIZ, None, "bayrak_yok"),
            ("A8 E mesajı", GOVDE_HATA, False, "hata_mesaji"),
            ("A9 activationExecuted=true + E mesajı",
             _chkl(ce=True, ae=True, ge=False, mesajlar=_msg("E", "x")), False, "hata_mesaji"),
            ("A10 severity=A mesajı", _chkl(mesajlar=_msg("A", "iptal", attr="severity")), False, "hata_mesaji"),
            ("A11 activationExecuted=false, generation yok", GOVDE_AKTIVASYON_YOK, False,
             "activation_not_executed"),
            ("A12 ayrıştırılamayan gövdede E işareti",
             '<chkl:messages activationExecuted="true"><msg type="E"><txt>kirpik', False, "hata_mesaji"),
        )
        for ad, govde, beklenen, sebep in satirlar:
            with self.subTest(ad=ad):
                hk = hukum(govde)
                self.kaydet(ad, "%s/%s" % (beklenen, sebep), "%s/%s" % (hk["hukum"], hk["sebep"]),
                            hk["hukum"] is beklenen and hk["sebep"] == sebep)


# ══════════════════════════════════════════════════════════════════════════════════════════════
# B — worklist eşleşmesi ve sonda
# ══════════════════════════════════════════════════════════════════════════════════════════════
class WorklistEslesme(_Kayit):
    def _kalan(self, govde, hedefler):
        return L.aktivasyon_worklist_kalan(L.aktivasyon_worklist_ayristir(govde), hedefler)

    def test_B1_ayni_adli_ff_hedefi_f_girdisini_yakalamaz(self):
        kalan = self._kalan(WL_AYNI_AD, [{"name": "ZBC000_FM_DEMO", "type": "FUGR/FF"}])
        self.kaydet("B1 alt tipli hedef tam tip", "yalnız FUGR/FF", [k["type"] for k in kalan],
                    [k["type"] for k in kalan] == ["FUGR/FF"])

    def test_B2_ana_tipli_hedef_iki_girdiyi_yakalar(self):
        kalan = self._kalan(WL_AYNI_AD, [{"name": "ZBC000_FM_DEMO", "type": "FUGR"}])
        self.kaydet("B2 ana tipli hedef", "2 girdi", len(kalan), len(kalan) == 2)

    def test_B3_uri_yol_siniri(self):
        govde = _worklist(("/sap/bc/adt/functions/groups/zbc000_fg_ab", "FUGR/F", "ZBC000_FG_AB"))
        kalan = self._kalan(govde, [{"uri": "/sap/bc/adt/functions/groups/zbc000_fg_a"}])
        self.kaydet("B3 zbc000_fg_a zbc000_fg_ab'yi yakalamaz", "0", len(kalan), kalan == [])

    def test_B4_parenturi_ile_alt_obje(self):
        kalan = self._kalan(WL_FUGR_FF, [{"uri": FG_URI}])
        self.kaydet("B4 grup URI'si FF'yi parentUri ile yakalar", "F+FF",
                    sorted(k["type"] for k in kalan), sorted(k["type"] for k in kalan) == ["FUGR/F", "FUGR/FF"])

    def test_B5_urili_tipsiz_hedef_ciplak_adla_eslesmez(self):
        govde = _worklist(("/sap/bc/adt/bo/behaviordefinitions/zbc000_r_demo", "BDEF/BDO", "ZBC000_R_DEMO"))
        kalan = self._kalan(govde, [{"uri": "/sap/bc/adt/ddic/ddl/sources/zbc000_r_demo",
                                     "name": "ZBC000_R_DEMO"}])
        self.kaydet("B5 URI'li tipsiz hedef + aynı adlı başka tip", "0", len(kalan), kalan == [])

    def test_B6_transport_girdisi_hedef_sayilmaz(self):
        kalan = self._kalan(WL_HEDEF_YOK, [{"name": "TESTK900001"}])
        self.kaydet("B6 /RQ girdisi atlanır", "0", len(kalan), kalan == [])

    def test_B7_ioc_olmayan_govde_valueerror(self):
        try:
            L.aktivasyon_worklist_ayristir('<?xml version="1.0"?><root/>')
            gercek = "istisna yok"
        except ValueError as exc:
            gercek = "ValueError:%s" % exc
        self.kaydet("B7 ioc olmayan gövde 'boş liste' sayılmaz", "ValueError", gercek,
                    gercek.startswith("ValueError"))

    def test_B8_sonda_olculemedi_uc_deger(self):
        for alt, worklist in SONDA_OLCULEMEDI:
            with self.subTest(alt=alt):
                c = _lib_client([], worklist)
                ok, sebep, kalan = L.aktivasyon_worklist_sondasi(c, [{"uri": SINIF_A_URI, "name": SINIF_A}])
                self.kaydet("B8 sonda %s" % alt, "None/unavailable", "%s/%s" % (ok, sebep),
                            ok is None and sebep.startswith("unavailable:") and kalan == [])

    def test_B9_sonda_hedefsiz_olculemedi(self):
        c = _lib_client([], _Yanit(200, WL_HEDEF_YOK))
        ok, sebep, _k = L.aktivasyon_worklist_sondasi(c, [])
        self.kaydet("B9 hedefsiz sonda", "None", "%s/%s" % (ok, sebep), ok is None)

    def test_B10_hedefler_istek_govdesinden(self):
        istek = ('<adtcore:objectReferences xmlns:adtcore="%s"><adtcore:objectReference adtcore:uri="%s" '
                 'adtcore:type="CLAS/OC" adtcore:name="%s"/></adtcore:objectReferences>' % (ADTCORE, SINIF_A_URI, SINIF_A))
        h = L.aktivasyon_hedefleri_govdeden(istek)
        self.kaydet("B10 istek gövdesinden hedef", "1 hedef", h,
                    h == [{"uri": SINIF_A_URI, "name": SINIF_A, "type": "CLAS/OC"}])
        self.kaydet("B10b ayrıştırılamayan istek", "[]", L.aktivasyon_hedefleri_govdeden("<<"),
                    L.aktivasyon_hedefleri_govdeden("<<") == [])


# ══════════════════════════════════════════════════════════════════════════════════════════════
# C — lib aktivasyon ayrıntıları: FUGR 2. faz, 1. faz boş gövde, FM push kablolaması
# ══════════════════════════════════════════════════════════════════════════════════════════════
class LibAktivasyon(_Kayit):
    def test_C1_fugr_faz2_ff_parenturi_ve_preaudit(self):
        c = _lib_client([_Yanit(200, FAZ1_IOC), _Yanit(200, GOVDE_TRUE)], _Yanit(200, WL_FUGR_FF))
        sonuc = _sessiz(c.activate_object, FG, FG_URI)
        faz2 = c.session.postlar[-1] if len(c.session.postlar) >= 2 else {"data": "", "params": {}}
        ff_var = ('adtcore:type="FUGR/FF"' in faz2["data"] and
                  'adtcore:parentUri="%s"' % FG_URI in faz2["data"])
        self.kaydet("C1 FUGR faz-2 gövdesi FF+parentUri", "FF parentUri'li", faz2["data"][-260:], ff_var)
        self.kaydet("C1b FUGR faz-2 preauditRequested=true", "true", faz2["params"],
                    faz2["params"].get("preauditRequested") == "true")
        self.kaydet("C1c FUGR sonucu", "success True", sonuc.get("success"), sonuc.get("success") is True)

    def test_C2_fugr_disi_faz2_govdesi_degismez(self):
        c = _lib_client([_Yanit(200, _worklist((SINIF_A_URI, "CLAS/OC", SINIF_A))), _Yanit(200, GOVDE_TRUE)],
                        _Yanit(200, WL_HEDEF_YOK))
        _sessiz(c.activate_object, SINIF_A, SINIF_A_URI)
        faz2 = c.session.postlar[-1]
        self.kaydet("C2 sınıf faz-2: parentUri yok, preaudit yok", "eski gövde",
                    (faz2["params"], "parentUri" in faz2["data"]),
                    faz2["params"] == {"method": "activate"} and "parentUri" not in faz2["data"])

    def test_C3_faz1_bos_govde_basari_sayilmaz(self):
        c = _lib_client([_Yanit(200, "")], _Yanit(200, WL_HEDEF_YOK))
        sonuc = _sessiz(c.activate_object, SINIF_A, SINIF_A_URI)
        self.kaydet("C3 boş aktivasyon gövdesi", "success False", sonuc.get("success"),
                    sonuc.get("success") is False)

    def test_C4_sonda_kalan_listesi_ve_dogrulanamadi_isareti(self):
        c = _lib_client([_Yanit(200, GOVDE_YALNIZ_GENERATION)], _Yanit(200, WL_HEDEF_VAR))
        sonuc = _sessiz(c.activate_object, SINIF_A, SINIF_A_URI)
        kalan = (sonuc.get("aktivasyon_dogrulama") or {}).get("kalan_inaktif") or []
        self.kaydet("C4 kalan_inaktif görünür", SINIF_A, kalan, [k.get("name") for k in kalan] == [SINIF_A])
        c2 = _lib_client([_Yanit(200, GOVDE_YALNIZ_GENERATION)], _Yanit(500, "x"))
        s2 = _sessiz(c2.activate_object, SINIF_A, SINIF_A_URI)
        self.kaydet("C4b sonda ölçemedi → dogrulanamadi", "True", s2.get("dogrulanamadi"),
                    s2.get("dogrulanamadi") is True and s2.get("success") is False)

    def test_C5_fm_push_aktivasyon_basarisi_varsayilmaz(self):
        kaynak = (LIB / "sap_adt_lib.py").read_text(encoding="utf-8")
        self.kaydet("C5 FM push: act.get('success', True) yok", "yok",
                    "act.get('success', True)" in kaynak, "act.get('success', True)" not in kaynak)
        self.kaydet("C5b FM push: success is True şartı", "var",
                    "act.get('success') is True" in kaynak, "act.get('success') is True" in kaynak)


# ══════════════════════════════════════════════════════════════════════════════════════════════
# J — `syntax_check_via_activation` üç değerli `valid`
# ══════════════════════════════════════════════════════════════════════════════════════════════
class SozdizimiHukmu(_Kayit):
    def _sc(self, yanit):
        c = _lib_client([yanit], _Yanit(200, WL_HEDEF_YOK))
        return _sessiz(c.syntax_check_via_activation, SINIF_A, SINIF_A_URI)

    def test_J1_sozdizimi_tablosu(self):
        satirlar = (
            ("J1 boş gövde", _Yanit(200, ""), None),
            ("J2 50 karakterden kısa gövde", _Yanit(200, "<a/>"), None),
            ("J3 yalnız generation (kontrol koşmadı)", _Yanit(200, GOVDE_YALNIZ_GENERATION), None),
            ("J4 bayraksız gövde", _Yanit(200, GOVDE_BAYRAKSIZ), None),
            ("J5 ioc:inactiveObjects", _Yanit(200, FAZ1_IOC), None),
            ("J6 activationExecuted=true", _Yanit(200, GOVDE_TRUE), True),
            ("J7 checkExecuted=true, hata yok", _Yanit(200, GOVDE_AKTIVASYON_YOK), True),
            ("J8 SAP E mesajı", _Yanit(200, GOVDE_HATA), False),
            ("J9 ayrıştırılamayan uzun gövde", _Yanit(200, '<chkl:messages xmlns:chkl="x">' + "kirpik " * 10), False),
            ("J10 HTTP 403 kilit", _Yanit(403, '<entry key="T100KEY-V1">TESTUSER_B</entry>'), False),
        )
        for ad, yanit, beklenen in satirlar:
            with self.subTest(ad=ad):
                sonuc = self._sc(yanit)
                self.kaydet(ad, "valid=%s" % beklenen, "valid=%s sebep=%s" % (
                    sonuc.get("valid"), sonuc.get("sozdizimi_sebep")), sonuc.get("valid") is beklenen)


# ══════════════════════════════════════════════════════════════════════════════════════════════
# H + J (araç katmanı) — atom `adt_activate` klasik yol ve MCP `adt_syntax_check`
# ══════════════════════════════════════════════════════════════════════════════════════════════
class AracYolu(_Kayit):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="axet_hukum_"))
        cls.dev = H.make_project(cls.root, "dev")
        cls._eski_env = {k: os.environ.get(k) for k in ("AXET_SAP_PROJECT_DIR", "ADT_SAP_TIER")}
        os.environ.pop("ADT_SAP_TIER", None)
        os.environ["AXET_SAP_PROJECT_DIR"] = str(cls.dev)
        from sapadt.tools import atom, query
        cls.atom, cls.query = atom, query
        cls._eski_client = atom._get_client

    @classmethod
    def tearDownClass(cls):
        cls.atom._get_client = cls._eski_client
        for k, v in cls._eski_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(cls.root, ignore_errors=True)

    def _istemci(self, post, worklist):
        from sap_client import SAPClient
        s = SAPClient.__new__(SAPClient)
        s.adt_client = _lib_client(post, worklist)
        self.atom._get_client = lambda: s
        return s

    def test_H1_basarisiz_aktivasyonda_sonda_kalanlari_bildirir(self):
        self._istemci([_Yanit(200, GOVDE_HATA)], _Yanit(200, WL_HEDEF_VAR))
        r = self.atom.adt_activate(SINIF_A, "class")
        adlar = [k.get("name") for k in (r.get("still_inactive") or [])]
        self.kaydet("H1 activated:false → ok false", "ok False", r.get("ok"), r.get("ok") is False)
        self.kaydet("H1b başarısız çağrıda sonda bilgisi", "still_inactive=[A]", (adlar, r.get("activation_probe")),
                    adlar == [SINIF_A] and r.get("activation_probe") == "checked_inactive")

    def test_H2_basarisiz_ve_liste_temiz_ok_false_kalir(self):
        self._istemci([_Yanit(200, GOVDE_HATA)], _Yanit(200, WL_HEDEF_YOK))
        r = self.atom.adt_activate(SINIF_A, "class")
        self.kaydet("H2 liste temiz ama activated:false", "ok False + probe_note",
                    (r.get("ok"), bool(r.get("probe_note"))), r.get("ok") is False and bool(r.get("probe_note")))

    def test_H3_basarisiz_ve_sonda_olculemedi(self):
        self._istemci([_Yanit(200, GOVDE_HATA)], _Yanit(500, "x"))
        r = self.atom.adt_activate(SINIF_A, "class")
        self.kaydet("H3 sonda ölçemedi", "ok False, still_inactive None",
                    (r.get("ok"), r.get("still_inactive"), r.get("activation_probe")),
                    r.get("ok") is False and r.get("still_inactive") is None
                    and str(r.get("activation_probe", "")).startswith("unavailable:"))

    def test_H4_kontrol_basari_iddiasi_listede_sahte_ok(self):
        self._istemci([_Yanit(200, GOVDE_TRUE)], _Yanit(200, WL_HEDEF_VAR))
        r = self.atom.adt_activate(SINIF_A, "class")
        self.kaydet("H4 başarı iddiası + listede", "activation_not_executed", (r.get("ok"), r.get("error")),
                    r.get("ok") is False and r.get("error") == "activation_not_executed")

    def test_H5_yalniz_generation_listede_degil_dogrulandi(self):
        self._istemci([_Yanit(200, GOVDE_YALNIZ_GENERATION)], _Yanit(200, WL_HEDEF_YOK))
        r = self.atom.adt_activate(SINIF_A, "class")
        self.kaydet("H5 yalnız generation + listede değil", "ok True verified True",
                    (r.get("ok"), r.get("activation_verified")),
                    r.get("ok") is True and r.get("activation_verified") is True)

    # ── Z147 (2026-09-26): her aktivasyon yanıtında yazılan objenin inaktif kayıt sayısı (`inactive_count`).
    # Sözleşme: aktivasyon iddiası + sayı>0 → ok:false `activation_not_executed` · ölçülemezse null + uyarı.
    def test_Z147_1_klasik_yol_sayi(self):
        sonuc = {}
        for ad, govde, wl in (("temiz", GOVDE_TRUE, _Yanit(200, WL_HEDEF_YOK)),
                              ("listede", GOVDE_TRUE, _Yanit(200, WL_HEDEF_VAR)),
                              ("olculemedi", GOVDE_TRUE, _Yanit(500, "x")),
                              ("basarisiz+listede", GOVDE_HATA, _Yanit(200, WL_HEDEF_VAR))):
            self._istemci([_Yanit(200, govde)], wl)
            r = self.atom.adt_activate(SINIF_A, "class")
            sonuc[ad] = (r.get("ok"), r.get("inactive_count"), bool(r.get("inactive_warning")))
        self.kaydet("Z147 adt_activate klasik: temiz=0 · listede=1(ok false) · ölçülemedi=null+uyarı · başarısız=1",
                    "(T,0,F)(F,1,F)(T,None,T)(F,1,F)", sonuc,
                    sonuc == {"temiz": (True, 0, False), "listede": (False, 1, False),
                              "olculemedi": (True, None, True), "basarisiz+listede": (False, 1, False)})

    def _rap_istemci(self, post, worklist_metni, wl_durum=200):
        s = self._istemci(post, _Yanit(wl_durum, worklist_metni, headers={"X-CSRF-Token": "TOKEN"}))
        a = s.adt_client
        a.client, a.language = "100", "TR"
        a._invalidate_csrf_cache = lambda: None
        return s

    def test_Z147_2_also_ve_srvb_yolu_sayi(self):
        sonuc = {}
        for ad, wl, durum in (("temiz", WL_HEDEF_YOK, 200), ("listede", WL_HEDEF_VAR, 200), ("olculemedi", "x", 500)):
            self._rap_istemci([_Yanit(200, GOVDE_TRUE)], wl, durum)
            r = self.atom.adt_activate(SINIF_A, "class", also=[{"name": "ZBC000_I_DEMO", "object_type": "ddls"}])
            sonuc["also-" + ad] = (r.get("ok"), r.get("inactive_count"), r.get("error"))
        srvb_wl = _worklist(("/sap/bc/adt/businessservices/bindings/zbc000_ui_demo_o2", "SRVB/SVB", "ZBC000_UI_DEMO_O2"))
        self._rap_istemci([_Yanit(200, GOVDE_TRUE)], srvb_wl)
        r = self.atom.adt_activate("ZBC000_UI_DEMO_O2", "srvb")
        sonuc["srvb-listede"] = (r.get("ok"), r.get("inactive_count"), r.get("error"))
        beklenen = {"also-temiz": (True, 0, None), "also-listede": (False, 1, "activation_not_executed"),
                    "also-olculemedi": (True, None, None), "srvb-listede": (False, 1, "activation_not_executed")}
        self.kaydet("Z147 adt_activate also=/srvb: activationExecuted=true ama listede → ok false", str(beklenen),
                    sonuc, sonuc == beklenen)

    def test_Z147_3_kilit_yolu_sayi(self):
        c = _lib_client([_Yanit(200, GOVDE_TRUE)], _Yanit(200, WL_HEDEF_YOK))
        r = self.atom._kilit_objesi_aktive_et(c, KILIT, "enqu")
        self.kaydet("Z147 kilit objesi yolu inactive_count=0", "ok · 0", (r.get("ok"), r.get("inactive_count")),
                    r.get("ok") is True and r.get("inactive_count") == 0)

    def test_J11_sap_client_olculmedi_satiri(self):
        s = self._istemci([_Yanit(200, GOVDE_YALNIZ_GENERATION)], _Yanit(200, WL_HEDEF_YOK))
        tampon = io.StringIO()
        with contextlib.redirect_stdout(tampon):
            s.syntax_check(SINIF_A, "class")
        cikti = tampon.getvalue()
        self.kaydet("J11 SAPClient.syntax_check ölçülmedi satırı", "[UNVERIFIED], [OK]/[FAIL] yok", cikti.strip()[-160:],
                    "[UNVERIFIED]" in cikti and "[OK] Syntax check passed" not in cikti
                    and "[FAIL] Syntax errors found" not in cikti)

    def test_J12_mcp_adt_syntax_check_belirsiz(self):
        self._istemci([_Yanit(200, GOVDE_YALNIZ_GENERATION)], _Yanit(200, WL_HEDEF_YOK))
        r = self.query.adt_syntax_check(SINIF_A, "class")
        self.kaydet("J12 MCP adt_syntax_check kontrol koşmadı", "ok False sozdizimi_belirsiz valid None",
                    (r.get("ok"), r.get("error"), r.get("valid")),
                    r.get("ok") is False and r.get("error") == "sozdizimi_belirsiz" and r.get("valid") is None)

    def test_J13_mcp_adt_syntax_check_kontrol_grubu_hata(self):
        self._istemci([_Yanit(200, GOVDE_HATA)], _Yanit(200, WL_HEDEF_YOK))
        r = self.query.adt_syntax_check(SINIF_A, "class")
        self.kaydet("J13 MCP SAP E mesajı", "ok True valid False", (r.get("ok"), r.get("valid")),
                    r.get("ok") is True and r.get("valid") is False)


# ══════════════════════════════════════════════════════════════════════════════════════════════
# K — lib kesinleştirme kilidi: HTTP hatasında sonda KOŞMAZ (temiz worklist başarıya çevirmez)
# ══════════════════════════════════════════════════════════════════════════════════════════════
class KesinlestirmeHttpHata(_Kayit):
    """`_aktivasyon_hukmunu_kesinlestir` yalnız gövdesi hüküm taşımayan 200 yanıtı sondalar.

    HTTP hata sonucunda `aktivasyon_hukmu` anahtarı hiç yoktur; anahtarsız sözlük sondalanırsa
    temiz bir worklist 500'ü ya da başka kullanıcının kilidini (403) başarıya çevirir.
    """

    def _kos(self, post):
        c = _lib_client(post, _Yanit(200, WL_HEDEF_YOK))
        sonuc = _sessiz(c.activate_object, SINIF_A, SINIF_A_URI)
        return sonuc, len(c.session.getler)

    def test_K1_post_500_temiz_worklist_basari_degil(self):
        sonuc, get = self._kos([_Yanit(500, "Internal Server Error")])
        self.kaydet("K1 POST 500 + temiz worklist", "success False · sonda koşmadı",
                    (sonuc.get("success"), get, "aktivasyon_dogrulama" in sonuc),
                    sonuc.get("success") is False and get == 0 and "aktivasyon_dogrulama" not in sonuc)

    def test_K2_post_403_baska_kilit_temiz_worklist_basari_degil(self):
        sonuc, get = self._kos([_Yanit(403, '<entry key="T100KEY-V1">TESTUSER_B</entry>')])
        self.kaydet("K2 POST 403 başka kilit + temiz worklist", "success False · sonda koşmadı",
                    (sonuc.get("success"), get, "aktivasyon_dogrulama" in sonuc),
                    sonuc.get("success") is False and get == 0 and "aktivasyon_dogrulama" not in sonuc)

    def test_K3_kontrol_hukumsuz_200_sondalanir(self):
        sonuc, get = self._kos([_Yanit(200, GOVDE_YALNIZ_GENERATION)])
        self.kaydet("K3 KONTROL yalnız generation 200 + temiz worklist", "success True · sonda 1 kez",
                    (sonuc.get("success"), get), sonuc.get("success") is True and get == 1)


# ══════════════════════════════════════════════════════════════════════════════════════════════
# L — `rap_service._aktivasyon_yaniti_ok`: POST yanıtının tek karar noktası (bool)
# ══════════════════════════════════════════════════════════════════════════════════════════════
ISTEK_SINIF_A = ('<adtcore:objectReferences xmlns:adtcore="%s"><adtcore:objectReference adtcore:uri="%s" '
                 'adtcore:type="CLAS/OC" adtcore:name="%s"/></adtcore:objectReferences>'
                 % (ADTCORE, SINIF_A_URI, SINIF_A))


class RapYanitKarari(_Kayit):
    def test_L1_yanit_karari_tablosu(self):
        # (ad, HTTP yanıtı, worklist | None=istemci yok, istek gövdesi, beklenen)
        satirlar = (
            ("L1a executed True", _Yanit(200, GOVDE_TRUE), _Yanit(200, WL_HEDEF_YOK), ISTEK_SINIF_A, True),
            ("L1b executed False (E mesajı)", _Yanit(200, GOVDE_HATA), _Yanit(200, WL_HEDEF_YOK), ISTEK_SINIF_A, False),
            ("L1c executed False (aktivasyon yok)", _Yanit(200, GOVDE_AKTIVASYON_YOK), _Yanit(200, WL_HEDEF_YOK),
             ISTEK_SINIF_A, False),
            ("L1d None + sonda listede değil", _Yanit(200, GOVDE_BAYRAKSIZ), _Yanit(200, WL_HEDEF_YOK), ISTEK_SINIF_A, True),
            ("L1e None + sonda listede", _Yanit(200, GOVDE_BAYRAKSIZ), _Yanit(200, WL_HEDEF_VAR), ISTEK_SINIF_A, False),
            ("L1f None + sonda HTTP 500", _Yanit(200, GOVDE_BAYRAKSIZ), _Yanit(500, "x"), ISTEK_SINIF_A, False),
            ("L1g None + istemci yok", _Yanit(200, GOVDE_BAYRAKSIZ), None, ISTEK_SINIF_A, False),
            ("L1h None + istek gövdesi yok (hedef yok)", _Yanit(200, GOVDE_BAYRAKSIZ), _Yanit(200, WL_HEDEF_YOK),
             None, False),
            ("L1i yalnız generation + sonda listede değil", _Yanit(200, GOVDE_YALNIZ_GENERATION),
             _Yanit(200, WL_HEDEF_YOK), ISTEK_SINIF_A, True),
            ("L1j boş gövde (bayrak eksik)", _Yanit(200, ""), _Yanit(200, WL_HEDEF_YOK), ISTEK_SINIF_A, False),
            ("L1k HTTP 500 + başarı gövdesi", _Yanit(500, GOVDE_TRUE), _Yanit(200, WL_HEDEF_YOK), ISTEK_SINIF_A, False),
        )
        for ad, yanit, worklist, istek, beklenen in satirlar:
            with self.subTest(ad=ad):
                istemci = None if worklist is None else _lib_client([], worklist)
                gercek = _sessiz(R._aktivasyon_yaniti_ok, yanit, istemci, istek)
                self.kaydet(ad, beklenen, gercek, gercek is beklenen)
