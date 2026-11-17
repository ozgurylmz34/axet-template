# -*- coding: utf-8 -*-
"""Uyum turu 8 — bağımsız inceleme (bug gate) bulgularının düzeltme testleri (ağsız).

  · YRM — tablo/yapı validator'ları yorum satırını ALAN ADI ADAYI sanıyordu: `//old_fld : zde_old;` ve
          `/*fld : x;*/` `AD_ADAYI`'nin `/…` koluna takılıp `ad_coz` reddiyle `SKIPPED measured=false
          reason=ad-cozulemedi` üretiyordu (run_review BLOCKER — Z/Y projede de). Düzeltme: alan taraması
          `utils/ddl_yorum.yorumlari_maskele` ile maskelenmiş metinde.
  · STF — `check_standard_table_fields` `TABLE_FIELD_PATTERN` alan kısmında association (`_Item`) ve rakamla
          başlayan (`1x`) adayı alıyordu ⇒ yanlış WARNING.
  · DEL — `sap_client.delete_object`: yerel dosya adı SAP DELETE'ten SONRA hesaplanıyordu; ad çevrilemezse
          `False` dönüyordu oysa obje SAP'de silinmişti.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest

import _helpers as H
from test_validator_ad_grameri import _Proje, _durum  # noqa: F401 — geçici proje kökü + durum ayrıştırıcı

sys.dont_write_bytecode = True
VAL = H.SCRIPTS / "sapadt" / "lib" / "validators"
LIB = H.SCRIPTS / "sapadt" / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))


def _modul(ad: str):
    spec = importlib.util.spec_from_file_location(f"_tbg_{ad}", VAL / f"{ad}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# Yorumlu tablo kaynağı: boşluklu/boşluksuz `//`, satır içi `/* */`, çok satırlı blok (içinde gramere
# UYMAYAN `/xx/y` + gramere UYAN `gizli_fld`), tırnak içinde `//` taşıyan annotation, satır sonu yorumu + gerçek namespace'li alan.
_YORUMLU_GOVDE = (
    "  key id : abap.int4;\n"
    "//old_fld : zde_old;\n"
    "  // eski_fld : zde_old;\n"
    "/*fld : x;*/\n"
    "  /* blok\n"
    "/xx/y : abc;\n"
    "gizli_fld : abap.char(1);\n"
    "  */\n"
    "  @EndUserText.label : 'http://ornek//yol'\n"
    "  note : abap.char(10); // satır sonu yorumu\n"
    "  /nspc/fld : abap.char(2);\n"
    "}\n")
_YORUMLU_TABLO = "define table ztab_x {\n" + _YORUMLU_GOVDE
_YORUMLU_YAPI = "define structure ZSTR_X {\n" + _YORUMLU_GOVDE.replace("  key id", "  id")


class YRM_YorumMaskesi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tfd = _modul("check_table_field_drop")
        cls.scs = _modul("check_sap_struct_consistency")

    def test_YRM1_maske_satir_no_ve_tirnak_korunur(self):
        from utils.ddl_yorum import yorumlari_maskele
        girdi = "a : b; // x\n/*c : d;*/\ne : 'u//v';\r\n  /* m\nn : o;\n*/ p : q;\n"
        cikti = yorumlari_maskele(girdi)
        self.assertEqual(cikti.count("\n"), girdi.count("\n"))
        self.assertEqual(cikti.split("\n"), ["a : b; ", " " * 10, "e : 'u//v';\r", "      ", "      ",
                                             "   p : q;", ""])

    def test_YRM2_ccr_yardimcilari_tek_kaynaktan(self):
        from utils import ddl_yorum
        ccr = _modul("check_cds_currency_reference")
        self.assertIs(ccr.yorumu_kirp, ddl_yorum.yorumu_kirp)
        self.assertIs(ccr.blok_yorumu_maskele, ddl_yorum.blok_yorumu_maskele)

    def test_YRM3_tablo_yorum_alan_sayilmaz_namespace_olculur(self):
        self.assertEqual(self.tfd.cozulemeyen_alanlar(_YORUMLU_TABLO), [])
        h = self.tfd.parse_fields(_YORUMLU_TABLO)
        self.assertEqual(h, {"id": "abap.int4", "note": "abap.char(10)", "/nspc/fld": "abap.char(2)"})
        # yorum dışındaki gerçek bozuk ad hâlâ yakalanır
        self.assertEqual(self.tfd.cozulemeyen_alanlar(_YORUMLU_TABLO.replace("}\n", "  /ab/f : abap.char(1);\n}\n")),
                         ["/ab/f"])
        H.kaydet("TFD yorum satırı alan adayı değil", "[] + 3 alan", str(sorted(h)), True)

    def test_YRM4_yapi_yorum_alan_sayilmaz_namespace_olculur(self):
        self.assertEqual(self.scs.cozulemeyen_alanlar(_YORUMLU_YAPI), [])
        self.assertEqual(self.scs.extract_fields(_YORUMLU_YAPI), {"id", "note", "/nspc/fld"})
        self.assertEqual(self.scs.cozulemeyen_alanlar(_YORUMLU_YAPI.replace("}\n", "  /ab/f : abap.char(1);\n}\n")),
                         ["/ab/f"])
        H.kaydet("SCS yorum satırı alan adayı değil", "[] + 3 alan", "eşit", True)


class YRM_AdYorumdanOkunmaz(unittest.TestCase):
    """R3 bug gate F1: tablo/yapı ADI da yorum maskeli metinden okunur (yorumdaki eski ad → yanlış obje → sahte temiz)."""

    @classmethod
    def setUpClass(cls):
        cls.tfd = _modul("check_table_field_drop")
        cls.scs = _modul("check_sap_struct_consistency")

    def test_YRM7_tablo_adi_yorumdan_okunmaz(self):
        metin = ("// eski ad: define table zsd001_t_old {\n/* define table zsd001_t_eski { */\n"
                 "define table zsd001_t_new {\n  key id : abap.int4;\n}\n")
        self.assertEqual(self.tfd.tablo_adi(metin), "zsd001_t_new")
        self.assertEqual(self.tfd.tablo_adi("define table zsd001_t_new {\n}\n"), "zsd001_t_new")  # kontrol grubu
        H.kaydet("TFD tablo adı yorumdan okunmaz", "zsd001_t_new", "eşit", True)

    def test_YRM8_yapi_adi_yorumdan_okunmaz(self):
        metin = ("/* define structure zsd001_s_old { */\n// define structure zsd001_s_eski\n"
                 "define structure zsd001_s_new {\n  id : abap.int4;\n}\n")
        self.assertEqual(self.scs.extract_struct_name(metin), "ZSD001_S_NEW")
        self.assertIsNone(self.scs.extract_struct_name("// define structure zsd001_s_old {\n"))
        H.kaydet("SCS yapı adı yorumdan okunmaz", "ZSD001_S_NEW", "eşit", True)


class YRM_UctanUca(_Proje):
    """Validator alt süreçle (ağsız, sahte URL): yorumlu kaynak `ad-cozulemedi` ile SKIPPED olmaz."""

    def test_YRM5_tablo_validator_ad_cozulemedi_demez(self):
        rc, o = self.kos("check_table_field_drop", "t.asddls", _YORUMLU_TABLO)
        self.assertEqual(rc, 0, o)
        self.assertNotIn("reason=ad-cozulemedi", _durum(o), o)
        self.assertNotIn("alan adı çözülemedi", o)

    def test_YRM6_yapi_validator_ad_cozulemedi_demez(self):
        rc, o = self.kos("check_sap_struct_consistency", "s.asddls", _YORUMLU_YAPI)
        self.assertEqual(rc, 0, o)
        self.assertNotIn("reason=ad-cozulemedi", _durum(o), o)


class STF_AlanKismiSuzme(_Proje):
    """`tablo._Assoc` / `tablo.1x` alan kısmı standart tablo alanı ADAYI değildir (eski `[a-z]…` deseni de almıyordu).

    Ağsız ayrım: aday yoksa validator SAP'ye hiç gitmez ⇒ `reason=kapsam-disi-std-tablo-yok`; aday varsa bağlantı
    dalına düşer (sahte URL) ⇒ bu reason ÇIKMAZ (kontrol grubu `mara.matnr`)."""
    V = "check_standard_table_fields"

    def test_STF1_association_ve_rakam_basli_alan_aday_degil(self):
        for kaynak in ("define view entity ZCA001_I_X as select from mara {\n  mara._Item as Kalem\n}\n",
                       "define view entity ZCA001_I_X as select from mara {\n  mara.1x as Sayi\n}\n"):
            with self.subTest(kaynak=kaynak.splitlines()[1]):
                rc, o = self.kos(self.V, "x.asddls", kaynak)
                self.assertEqual(rc, 0, o)
                self.assertIn("reason=kapsam-disi-std-tablo-yok", _durum(o), o)
        H.kaydet("STF `_Assoc`/`1x` alan adayı değil", "kapsam-disi", "eşit", True)

    def test_STF2_kontrol_grubu_gercek_alan_aday(self):
        rc, o = self.kos(self.V, "x.asddls",
                         "define view entity ZCA001_I_X as select from mara {\n  mara.matnr as Malzeme\n}\n")
        self.assertNotIn("reason=kapsam-disi-std-tablo-yok", _durum(o), o)


class DEL_SilmeSonucu(unittest.TestCase):
    """SAP DELETE başarılıysa sonuç True — yerel dosya adı çevrilemese de (yerel temizlik ikincil iştir)."""

    def setUp(self):
        import tempfile
        from pathlib import Path
        self._tmp = tempfile.TemporaryDirectory(prefix="axet_t8del_")
        self.kok = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _sil(self, ad):
        import contextlib
        import io
        from test_tur8_tamamlama import _sc
        c = _sc(self.kok)
        cikti = io.StringIO()
        with contextlib.redirect_stdout(cikti):
            ok = c.delete_object(ad, "program", transport="SAHK900001", confirm=False)
        return ok, c.adt_client.silinen, cikti.getvalue()

    def test_DEL1_yerel_ad_cevrilemezse_sap_silmesi_true(self):
        # `/AB/` namespace biçimine uymaz ⇒ `yerel_ad` ValueError; SAP tarafı (sahte) silmeyi kabul eder.
        ok, silinen, cikti = self._sil("/AB/ZPROG")
        self.assertEqual(len(silinen), 1, cikti)          # SAP DELETE gerçekten çağrıldı
        self.assertTrue(ok, cikti)                          # sonuç SAP silmesini doğru raporlar
        self.assertIn("Local file", cikti)                  # yerel temizlik sorunu SESSİZ değil
        H.kaydet("DEL yerel ad çevrilemez, SAP silindi", "True", str(ok), ok is True)

    def test_DEL2_kontrol_grubu_z_adi(self):
        ok, silinen, cikti = self._sil("ZCA001_PROG")
        self.assertTrue(ok, cikti)
        self.assertEqual(len(silinen), 1)


if __name__ == "__main__":
    unittest.main()
