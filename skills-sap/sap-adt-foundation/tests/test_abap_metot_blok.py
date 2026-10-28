# -*- coding: utf-8 -*-
"""Z213 (2026-10-28; kaynak çekirdek #362) — METHOD blok SINIRI tek kaynak: `lib/utils/abap_metot_blok.py`.

İki tüketici aynı sınır kararını kullanır:
  · OKUMA  `tools/diag.py` `_metot_cikar` → `adt_get_method` (uçtan uca HTTP testi `test_checkrun_sozdizimi.py` C1-C14)
  · YAZMA  `lib/sap_client.py` `_push_method_includes` (metot include fallback'i — bulunan blok SAP'ye PUT edilir)

Ölçülen arıza (düzeltme öncesi, bu dosyanın W-vektörleri eski kodda): yazma yolunun satır-başı çapalı regex'i tek satırlık
`METHOD a. x = 1. ENDMETHOD.` ve satır ortasındaki `x = 1. ENDMETHOD.` bitişini kaçırıp SONRAKİ metodun gövdesini
a'nın include'una PUT ediyordu; araya METHOD giren blokta da a+b'yi PUT ediyordu.

Vektör adları kaynak çekirdeğin `tests/fixtures/mcp_salt_okur_araclar` G11–G34 / F1–F8c numaralarını korur (izlenebilirlik).
SAP'ye bağlanmaz; yazma yolu sahte ADT ile kilit/PUT çağrılarını sayar.
"""
from __future__ import annotations

import contextlib
import io
import sys
import unittest

import _helpers as H

sys.dont_write_bytecode = True
LIB = H.SCRIPTS / "sapadt" / "lib"
for _p in (H.SCRIPTS, LIB):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import sapadt  # noqa: E402,F401  (lib yolunu hazırlar)
from utils import abap_metot_blok as AMB  # noqa: E402
from sap_client import SAPClient  # noqa: E402
from sapadt.tools import diag  # noqa: E402

SB = AMB.SINIR_BELIRSIZ
BS = chr(92)   # ABAP şablon kaçışı `\` (kaynakta literal ters eğik çizgi kaçış kaybına bağışık)

TEK = "METHOD a. x = 1. ENDMETHOD.\nMETHOD b.\n  y = 2.\nENDMETHOD."
ESKI_PIPE = ("METHOD a.\n  r = |x" + BS + "|. ENDMETHOD. |.\n  z = 2.\nENDMETHOD.\n"
             "METHOD b.\nENDMETHOD.")
AMDP_ARA = ("METHOD a.\n  x = 1.\nMETHOD b\n  BY DATABASE PROCEDURE FOR HDB LANGUAGE SQLSCRIPT USING t.\n"
            "  select 1 from dummy;\nENDMETHOD.")
AMDP_HEDEF_COK = ("METHOD a\n  BY DATABASE PROCEDURE FOR HDB LANGUAGE SQLSCRIPT\n  USING t.\n"
                  "  lt = select t.method,\n    method,\n    x from t;\nENDMETHOD.")


class _Kayit(unittest.TestCase):
    def kaydet(self, ad, beklenen, gercek, ok):
        H.kaydet(f"Z213 {ad}", beklenen, str(gercek)[:160], ok)
        self.assertTrue(ok, f"{ad}: {gercek}")


# ══════════════════════════════════════════════════════════════════════════════════════════════
# G — sınır kararı (ortak modül)
# ══════════════════════════════════════════════════════════════════════════════════════════════
class SinirKarari(_Kayit):
    def test_G11_tek_satirlik_metot_yalniz_o_satir(self):
        b = AMB.metot_bloklari(TEK, "a")
        bb = AMB.metot_bloklari(TEK, "b")
        self.kaydet("G11 tek satır a → (1,1) yalnız o satır · G11b b → (2,4)", "[(1,1,a)] · (2,4)", (b, bb[:1]),
                    b == [(1, 1, "METHOD a. x = 1. ENDMETHOD.")] and bb and bb[0][:2] == (2, 4))

    def test_G12_G13_bos_ve_son_tek_satir(self):
        b12 = AMB.metot_bloklari("METHOD a. ENDMETHOD.\nMETHOD b.\nENDMETHOD.", "a")
        b13 = AMB.metot_bloklari("METHOD b.\n  y = 2.\nENDMETHOD.\n  METHOD a. ENDMETHOD.", "a")
        self.kaydet("G12 boş tek satır (1,1) · G13 son metot tek satır (4,4) — kapanmamış DEĞİL", "(1,1) · (4,4)",
                    (b12, b13), b12 == [(1, 1, "METHOD a. ENDMETHOD.")] and b13 == [(4, 4, "  METHOD a. ENDMETHOD.")])

    def test_G14_cok_satirli_kontrol(self):
        b = AMB.metot_bloklari("METHOD a.\n  x = 1.\nENDMETHOD.\nMETHOD b.\nENDMETHOD.", "a")
        self.kaydet("G14 çok satırlı kontrol (FP çapası) → (1,3)", "(1,3) tek blok", b,
                    len(b) == 1 and b[0][:2] == (1, 3))

    def test_G15_satir_ortasi_bitis(self):
        b = AMB.metot_bloklari("METHOD a.\n  x = 1. ENDMETHOD.\nMETHOD b.\n  y = 2.\nENDMETHOD.", "a")
        self.kaydet("G15 satır ortasındaki `ENDMETHOD.` bitiştir → (1,2), b'nin gövdesi YOK", "(1,2) · METHOD b yok",
                    b, b and b[0][:2] == (1, 2) and "METHOD b" not in b[0][2])

    def test_G16_G17_G30_sinir_belirsiz(self):
        b16 = AMB.metot_bloklari("METHOD a. ENDMETHOD. METHOD b. ENDMETHOD.", "a")
        b17 = AMB.metot_bloklari("METHOD a.\n  x = 1.\nMETHOD b.\n  y = 2.\nENDMETHOD.", "a")
        b30 = AMB.metot_bloklari("METHOD a.\n  x = 1.\nMETHOD b BY DATABASE PROCEDURE FOR HDB LANGUAGE SQLSCRIPT.\n"
                                 "ENDMETHOD.", "a")
        self.kaydet("G16 aynı satırda karışık · G17 ENDMETHOD'dan önce METHOD · G30 `METHOD b BY …` → SINIR_BELIRSIZ",
                    "3× tek blok, son=sinir_belirsiz", (b16, b17, b30),
                    all(len(b) == 1 and b[0][1] == SB for b in (b16, b17, b30)))

    def test_G18_G19_G20_literal_ve_yorum(self):
        b18 = AMB.metot_bloklari("METHOD a.\n  lv = 'x. ENDMETHOD.'.\n  lv2 = |y. ENDMETHOD.|.\n"
                                 "  lv3 = `z. ENDMETHOD.`.\nENDMETHOD.", "a")
        b19 = AMB.metot_bloklari("METHOD a.\n* x. ENDMETHOD.\n  WRITE 1.\nENDMETHOD.", "a")
        b20 = AMB.metot_bloklari("METHOD a.\n  WRITE 1. \" bitti. ENDMETHOD. degil\n  WRITE 2.\nENDMETHOD.", "a")
        self.kaydet("G18 literal (' ` |) · G19 sütun-1 `*` · G20 `\"` yorumundaki ENDMETHOD bitiş SAYILMAZ",
                    "(1,5) · (1,4) · (1,4)", (b18[:1], b19[:1], b20[:1]),
                    b18 and b18[0][:2] == (1, 5) and b19 and b19[0][:2] == (1, 4) and b20 and b20[0][:2] == (1, 4))

    def test_G24_sablon_kacisi(self):
        b = AMB.metot_bloklari(ESKI_PIPE, "a")
        self.kaydet("G24 `|x\\|. ENDMETHOD. |` şablon kaçışı → bitiş şablon içinde DEĞİL (1,4)", "(1,4) tek blok",
                    b, len(b) == 1 and b[0][:2] == (1, 4))

    def test_G25_G29_tanimlayici_deyim_degil(self):
        vakalar = (
            ("G25 method = 'GET'.", "METHOD a.\n  method = 'GET'.\n  x = 1.\nENDMETHOD.", (1, 4)),
            ("G26 çağrıda method = …",
             "METHOD a.\n  lo->call(\n    method = if_http_request=>co_request_method_post ).\nENDMETHOD.", (1, 4)),
            ("G27 x = 1.method = 2.", "METHOD a.\n  x = 1.method = 2.\nENDMETHOD.", (1, 3)),
            ("G28 AMDP select t.method", "METHOD a BY DATABASE PROCEDURE FOR HDB LANGUAGE SQLSCRIPT.\n"
                                         "  select t.method from ztab as t;\nENDMETHOD.", (1, 3)),
            ("G29 endmethod = 1.", "METHOD a.\n  endmethod = 1.\n  x = 2.\nENDMETHOD.", (1, 4)),
        )
        sonuc = {ad: AMB.metot_bloklari(k, "a")[:1] for ad, k, _b in vakalar}
        ok = all(len(sonuc[ad]) == 1 and sonuc[ad][0][:2] == bek for ad, _k, bek in vakalar)
        self.kaydet("G25–G29 `method`/`endmethod` tanımlayıcısı deyim SAYILMAZ", "hepsi beklenen sınır",
                    {a: (v[0][:2] if v else v) for a, v in sonuc.items()}, ok)

    def test_G31_G32_G34_amdp_basliklari(self):
        b31 = AMB.metot_bloklari(AMDP_ARA, "a")
        b32 = AMB.metot_bloklari(AMDP_HEDEF_COK, "a")
        b34 = AMB.metot_bloklari("METHOD a BY DATABASE PROCEDURE FOR HDB LANGUAGE SQLSCRIPT USING t.\n"
                                 "  select 1 from t; ENDMETHOD.\nMETHOD b\n"
                                 "  BY DATABASE PROCEDURE FOR HDB LANGUAGE SQLSCRIPT USING t.\n  select 2 from t;\n"
                                 "ENDMETHOD.", "a")
        self.kaydet("G31 araya bölünmüş `METHOD b`⏎`BY DATABASE` → belirsiz · G32 çok satırlı AMDP hedef (1,7) · "
                    "G34 `…; ENDMETHOD.` + bölünmüş b → belirsiz", "SB · (1,7) · SB",
                    (b31[:1] and b31[0][1], b32[:1] and b32[0][:2], b34[:1] and b34[0][1]),
                    len(b31) == 1 and b31[0][1] == SB and len(b32) == 1 and b32[0][:2] == (1, 7)
                    and len(b34) == 1 and b34[0][1] == SB)

    def test_G35_bitisten_sonra_kod_belirsiz(self):
        """aXet tur 7 bug-gate F1: bitiş satırı bloğa bütün girer ⇒ `ENDMETHOD. ENDCLASS.` bitiş SAYILMAZ."""
        cok = AMB.metot_bloklari("CLASS c IMPLEMENTATION.\nMETHOD a.\n  x = 1.\nENDMETHOD. ENDCLASS.\n", "a")
        tek = AMB.metot_bloklari("METHOD a. x = 1. ENDMETHOD. ENDCLASS.", "a")
        yorum = AMB.metot_bloklari("METHOD a.\n  x = 1.\nENDMETHOD.   \" son metot\nENDCLASS.", "a")
        bosluk = AMB.metot_bloklari("METHOD a. x = 1. ENDMETHOD.   ", "a")
        self.kaydet("G35 `ENDMETHOD. ENDCLASS.` (çok satırlı / tek satır) → SINIR_BELIRSIZ · FP: ardından yalnız "
                    "yorum ya da boşluk → normal bitiş", "SB · SB · (1,3) · (1,1)",
                    (cok, tek, yorum, bosluk),
                    len(cok) == 1 and cok[0][1] == SB and len(tek) == 1 and tek[0][1] == SB
                    and yorum and yorum[0][:2] == (1, 3) and bosluk and bosluk[0][:2] == (1, 1))

    def test_amdp_baslik_mi(self):
        ok = (AMB.amdp_baslik_mi("METHOD a BY DATABASE PROCEDURE FOR HDB LANGUAGE SQLSCRIPT USING t.\nENDMETHOD.")
              and AMB.amdp_baslik_mi(AMDP_HEDEF_COK)
              and not AMB.amdp_baslik_mi("METHOD a.\n  lv = 'BY DATABASE'.\nENDMETHOD.")
              and not AMB.amdp_baslik_mi("METHOD a.\n  x = 1.\nENDMETHOD."))
        self.kaydet("amdp_baslik_mi: tek satır/bölünmüş başlık True · gövdede 'BY DATABASE' literali False (FP)",
                    "True True False False", ok, ok)

    def test_cikar_esleme_aXet_sozlesmesi(self):
        """`diag._metot_cikar` modülün `SINIR_BELIRSIZ`'ini aXet'in 4'lü biçimine eşler: son=None + sebep metni."""
        b16 = diag._metot_cikar("METHOD a. ENDMETHOD. METHOD b. ENDMETHOD.", "a")
        b17 = diag._metot_cikar("METHOD a.\n  x = 1.\nMETHOD b.\n  y = 2.\nENDMETHOD.", "a")
        b11 = diag._metot_cikar(TEK, "a")
        kap = diag._metot_cikar("METHOD a.\n  x = 1.\n", "a")
        ec = diag._metot_cikar("METHOD a.\n  x = 1.\nENDMETHOD. ENDCLASS.", "a")
        ec1 = diag._metot_cikar("METHOD a. x = 1. ENDMETHOD. ENDCLASS.", "a")
        # birleşik: araya METHOD giren blok kendi sebebini korur (ENDCLASS sebebi YALNIZ saf durumda)
        bir1 = diag._metot_cikar("METHOD a.\n  x.\nMETHOD b. ENDMETHOD. ENDCLASS.", "a")
        bir2 = diag._metot_cikar("METHOD a. METHOD b. ENDMETHOD. ENDCLASS.", "a")
        ok = (bir1[0][1] is None and "yeni METHOD" in bir1[0][3] and "ENDCLASS" not in bir1[0][3]
              and bir2[0][1] is None and "METHOD satırında" in bir2[0][3] and "ENDCLASS" not in bir2[0][3]
              and ec[0][1] is None and "ENDCLASS" in ec[0][3] and "satır 3" in ec[0][3]
              and ec1[0][1] is None and "ENDCLASS" in ec1[0][3]
              and b16[0][1] is None and "METHOD satırında" in b16[0][3]
              and b17[0][1] is None and "yeni METHOD" in b17[0][3] and "satır 3" in b17[0][3]
              and b11 == [(1, 1, "METHOD a. x = 1. ENDMETHOD.", None)]
              and kap == [(1, None, "METHOD a.\n  x = 1.\n", None)])
        self.kaydet("_metot_cikar eşlemesi: belirsiz → (bas, None, metin, sebep) · tek satır → (1,1,…,None) · "
                    "kapanmamış → sebep None", "sebepli/sebepsiz ayrımı", (b16, b17, b11, kap), ok)


# ══════════════════════════════════════════════════════════════════════════════════════════════
# W — YAZMA yolu: `SAPClient._push_method_includes` (kaynak çekirdek F1–F8c)
# ══════════════════════════════════════════════════════════════════════════════════════════════
class _SahteAdt:
    _last_lock_effective_transport = None

    def __init__(self):
        self.kilit, self.put, self.birak = [], [], []

    def lock_object(self, url, transport=None):
        self.kilit.append(url)
        return "KILIT-1"

    def set_include_source(self, url, govde, kilit, transport):
        self.put.append((url, govde))

    def unlock_object(self, url, kilit):
        self.birak.append(url)
        return True


def _kos(kaynak, metotlar):
    ist = object.__new__(SAPClient)
    ist.adt_client = _SahteAdt()
    ist.debug_enabled = False
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        r = ist._push_method_includes("/sap/bc/adt/oo/classes/zsd001_cl_ornek", "ZSD001_CL_ORNEK", kaynak, metotlar,
                                      "<TRANSPORT>")
    return r, ist.adt_client, buf.getvalue()


class YazmaYolu(_Kayit):
    def test_W1_tek_satir_yalniz_a_put(self):
        r, adt, _l = _kos(TEK, ["A"])
        self.kaydet("W1 (F1) tek satırlık a → 1 PUT, gövde YALNIZ a (b'nin gövdesi YAZILMAZ)",
                    "True · 1 PUT · 'METHOD a. x = 1. ENDMETHOD.\\n'", (r, adt.put),
                    r is True and len(adt.put) == 1 and adt.put[0][1] == "METHOD a. x = 1. ENDMETHOD.\n"
                    and adt.put[0][0].endswith("/includes/implementations/A"))

    def test_W2_W3_W5_belirsiz_ya_da_kapanmamis_kilit_ve_put_yok(self):
        sonuc = {}
        for ad, kaynak in (("F2 karışık", "METHOD a. ENDMETHOD. METHOD b. ENDMETHOD."),
                           ("F3 ENDMETHOD'dan önce METHOD", "METHOD a.\n  x = 1.\nMETHOD b.\n  y = 2.\nENDMETHOD."),
                           ("F5 kapanmamış", "METHOD a.\n  x = 1.\n")):
            r, adt, log = _kos(kaynak, ["A"])
            sonuc[ad] = (r, len(adt.kilit), len(adt.put), "PUT YAPILMADI" in log)
        self.kaydet("W2/W3/W5 (F2 F3 F5) belirsiz/kapanmamış sınır → kilit 0 + PUT 0 + False + log 'PUT YAPILMADI'",
                    "hepsi (False, 0, 0, True)", sonuc, all(v == (False, 0, 0, True) for v in sonuc.values()))

    def test_W4_cok_satirli_kontrol_iki_put(self):
        r, adt, _l = _kos("METHOD a.\n  x = 1.\nENDMETHOD.\nMETHOD b.\nENDMETHOD.", ["A", "B"])
        self.kaydet("W4 (F4) çok satırlı kontrol (FP çapası) → 2 PUT, gövdeler doğru", "True · a, b", (r, adt.put),
                    r is True and [p[1] for p in adt.put] == ["METHOD a.\n  x = 1.\nENDMETHOD.\n",
                                                              "METHOD b.\nENDMETHOD.\n"])

    def test_W6_sablon_kacisi_tam_govde(self):
        r, adt, _l = _kos(ESKI_PIPE, ["A"])
        beklenen = "\n".join(ESKI_PIPE.split("\n")[:4]) + "\n"
        self.kaydet("W6 (F6) şablon kaçışlı metot → PUT edilen gövde TAM blok (kesik gövde YAZILMAZ)", "4 satır",
                    (r, adt.put), r is True and len(adt.put) == 1 and adt.put[0][1] == beklenen)

    def test_W7_bolunmus_amdp_baslik_araya_girer(self):
        r, adt, _l = _kos("METHOD a.\n  x = 1.\nENDMETHOD ##NEEDED.\nMETHOD b\n"
                          "  BY DATABASE PROCEDURE FOR HDB LANGUAGE SQLSCRIPT USING t.\n  select 1 from t;\nENDMETHOD.",
                          ["A"])
        r2, adt2, _l2 = _kos("METHOD a.\n  x = 1.\nENDMETHOD ##NEEDED.\nMETHOD b.\n  y = 2.\nENDMETHOD.", ["A"])
        self.kaydet("W7 (F7/F7b) `ENDMETHOD ##P.` + araya `METHOD b`⏎`BY …` ya da `METHOD b.` → kilit 0 + PUT 0",
                    "(False,0,0) ×2", (r, len(adt.kilit), len(adt.put), r2, len(adt2.kilit), len(adt2.put)),
                    r is False and not adt.kilit and not adt.put and r2 is False and not adt2.kilit and not adt2.put)

    def test_W8_amdp_hedef_put_edilmez_fp_capasi(self):
        r, adt, log = _kos("METHOD a BY DATABASE PROCEDURE FOR HDB LANGUAGE SQLSCRIPT USING t.\n  select 1 from t;\n"
                           "ENDMETHOD.", ["A"])
        rb, adtb, _lb = _kos(AMDP_HEDEF_COK, ["A"])
        rc, adtc, _lc = _kos("METHOD a.\n  lv = 'BY DATABASE'.\nENDMETHOD.", ["A"])
        self.kaydet("W8 (F8/F8b) AMDP hedef (tek satır / bölünmüş başlık) → kilit 0 + PUT 0 · F8c FP: gövdede "
                    "'BY DATABASE' literali → 1 PUT", "0/0 · 0/0 · 1 PUT",
                    (r, len(adt.put), rb, len(adtb.put), rc, len(adtc.put)),
                    r is False and not adt.kilit and not adt.put and "AMDP" in log
                    and rb is False and not adtb.kilit and not adtb.put
                    and rc is True and len(adtc.put) == 1)

    def test_W10_bitis_satirinda_endclass_put_edilmez(self):
        """aXet tur 7 bug-gate F1: eski regex `ENDMETHOD.`'da keserdi; ortak modül satırı bütün alıyordu ⇒
        `ENDCLASS.` metot include'una PUT ediliyordu (ölçüldü). Artık kilit ve PUT yok."""
        sonuc = {}
        for ad, kaynak in (("çok satırlı", "CLASS c IMPLEMENTATION.\nMETHOD a.\n  x = 1.\nENDMETHOD. ENDCLASS.\n"),
                           ("tek satır", "METHOD a. x = 1. ENDMETHOD. ENDCLASS.")):
            r, adt, log = _kos(kaynak, ["A"])
            sonuc[ad] = (r, len(adt.kilit), len(adt.put), "PUT YAPILMADI" in log)
        self.kaydet("W10 `ENDMETHOD. ENDCLASS.` → kilit 0 + PUT 0 + False + log 'PUT YAPILMADI'",
                    "hepsi (False, 0, 0, True)", sonuc, all(v == (False, 0, 0, True) for v in sonuc.values()))

    def test_W9_coklu_eslesmede_ilk_blok(self):
        r, adt, _l = _kos("METHOD a.\n  x = 1.\nENDMETHOD.\nCLASS lcl IMPLEMENTATION.\nMETHOD a.\n  x = 2.\n"
                          "ENDMETHOD.\nENDCLASS.", ["A"])
        self.kaydet("W9 korunan eksen: aynı adlı iki blokta İLK blok PUT edilir (eski davranış)", "x = 1 gövdesi",
                    adt.put, r is True and len(adt.put) == 1 and "x = 1." in adt.put[0][1]
                    and "x = 2." not in adt.put[0][1])


if __name__ == "__main__":
    unittest.main()
