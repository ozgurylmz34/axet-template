# -*- coding: utf-8 -*-
"""xdp_denetle.py: her kural için doğru-pozitif VE doğru-negatif (denetçi kendini kanıtlamasın)."""
import os
import unittest

import _common as c
import _xdp_ortak as ortak
import xdp_denetle as d


def _kolonlar(n, w, kap="192mm", ek=""):
    alanlar = "".join('<field name="K%d" w="%s" minH="5mm"><ui><textEdit/></ui><font typeface="Arial"/></field>'
                      % (i, w) for i in range(n))
    return '<subform name="SATIR" layout="lr-tb" w="%s">%s%s</subform>' % (kap, ek, alanlar)


def _bul(govde, kok='name="data" layout="tb" locale="tr_TR"', **kw):
    return d.denetle(ortak.ayristir(c.xdp(govde, kok)), **kw)[0]


def _kural(bulgular, kural, sev=None):
    return [b for b in bulgular if b[1] == kural and (sev is None or b[0] == sev)]


class Xdp03KolonToplami(unittest.TestCase):
    def test_sekiz_kolon_esit_uyari(self):
        b = _bul(_kolonlar(8, "24mm"))
        self.assertEqual(1, len(_kural(b, "XDP-03", "UYARI")), b)
        self.assertIn("8 eleman", _kural(b, "XDP-03")[0][3])
        self.assertIn("8 ve 11 elemanlı satırda son kolon alt satıra kaydı", _kural(b, "XDP-03")[0][3])

    def test_on_bir_kolon_bir_mm_icinde_uyari(self):
        # 10 × 17.4 + 17.5 = 191.5 > 191 → hâlâ uyarı bölgesi
        alanlar = "".join('<draw w="17.4mm"><value><text>a</text></value><font typeface="Arial"/></draw>' for _ in range(10))
        govde = '<subform layout="lr-tb" w="192mm">%s<draw w="17.5mm"><value><text>b</text></value>' \
                '<font typeface="Arial"/></draw></subform>' % alanlar
        self.assertEqual(1, len(_kural(_bul(govde), "XDP-03", "UYARI")))

    def test_bes_yedi_kolon_esik_olculmedi_uyari(self):
        b = _kural(_bul(_kolonlar(6, "32mm")), "XDP-03", "UYARI")
        self.assertEqual(1, len(b))
        self.assertIn("eşik", b[0][3])

    def test_sekiz_kolon_191_temiz(self):
        govde = _kolonlar(7, "24mm").replace("</subform>", '<field name="S" w="23mm"><ui><textEdit/></ui>'
                                                         '<font typeface="Arial"/></field></subform>')
        self.assertEqual([], _kural(_bul(govde), "XDP-03"))

    def test_dort_kolon_esit_yalniz_bilgi(self):
        b = _bul(_kolonlar(4, "48mm"))
        self.assertEqual([], _kural(b, "XDP-03", "UYARI"))
        self.assertEqual(1, len(_kural(b, "XDP-03", "BİLGİ")))

    def test_toplam_buyuk_sarilan_satir_bilgi(self):
        b = _bul(_kolonlar(8, "48mm"))
        self.assertEqual([], _kural(b, "XDP-03", "UYARI"))
        self.assertIn("sarılır", _kural(b, "XDP-03", "BİLGİ")[0][3])

    def test_tekrarli_cocuk_kart_izgarasi_bilgi(self):
        kart = '<subform name="KART" layout="tb" w="24mm"><occur min="0" max="-1"/></subform>'
        b = _bul(_kolonlar(7, "24mm", ek=kart))
        self.assertEqual([], _kural(b, "XDP-03", "UYARI"))
        self.assertIn("tekrarlı", _kural(b, "XDP-03", "BİLGİ")[0][3])

    def test_izgara_bayragi(self):
        b = _bul(_kolonlar(8, "24mm"), izgara=("SATIR",))
        self.assertEqual([], _kural(b, "XDP-03", "UYARI"))
        b2 = _bul(_kolonlar(8, "24mm"), izgara=("BASKA",))
        self.assertEqual(1, len(_kural(b2, "XDP-03", "UYARI")))

    def test_gizli_cocuk_sayilmaz(self):
        gizli = '<field name="G" w="1mm" presence="hidden"><ui><textEdit/></ui><font typeface="Arial"/></field>'
        govde = _kolonlar(7, "24mm", ek=gizli).replace(
            "</subform>", '<field name="S" w="23mm"><ui><textEdit/></ui><font typeface="Arial"/></field></subform>')
        self.assertEqual([], _kural(_bul(govde), "XDP-03"))

    def test_genisliksiz_cocuk_olculemedi(self):
        govde = _kolonlar(7, "24mm").replace("</subform>", '<field name="X"><ui><textEdit/></ui>'
                                                         '<font typeface="Arial"/></field></subform>')
        b = _kural(_bul(govde), "XDP-03")
        self.assertEqual(["BİLGİ"], [x[0] for x in b])
        self.assertIn("ÖLÇÜLEMEDİ", b[0][3])

    def test_birim_cevirimi(self):
        self.assertAlmostEqual(25.4, ortak.mm("1in"))
        self.assertAlmostEqual(10.0, ortak.mm("1cm"))
        self.assertIsNone(ortak.mm("12"))


class Xdp04BuyukHarfI(unittest.TestCase):
    def _metin(self, t):
        return _bul('<draw w="50mm"><value><text>%s</text></value><font typeface="Arial"/></draw>' % t)

    def test_booking_yakalanir(self):
        b = _kural(self._metin("BOOKİNG NO"), "XDP-04")
        self.assertEqual(1, len(b))
        self.assertIn("BOOKİNG", b[0][3])

    def test_sozcuk_basi_i_yakalanir(self):
        self.assertEqual(1, len(_kural(self._metin("İNCOTERMS"), "XDP-04")))

    def test_ascii_buyuk_harf_temiz(self):
        self.assertEqual([], _kural(self._metin("BOOKING NO"), "XDP-04"))

    def test_karma_harf_temiz(self):
        self.assertEqual([], _kural(self._metin("İzmir şubesi"), "XDP-04"))


class Xdp05FontLocale(unittest.TestCase):
    def test_arial_disi(self):
        b = _bul('<field name="A" w="10mm"><ui><textEdit/></ui><font typeface="Helvetica"/></field>')
        self.assertEqual(1, len(_kural(b, "XDP-05")))

    def test_typeface_yok(self):
        b = _bul('<field name="A" w="10mm"><ui><textEdit/></ui><font size="8pt"/></field>')
        self.assertEqual(1, len(_kural(b, "XDP-05")))

    def test_font_ogesi_yok(self):
        b = _bul('<draw w="10mm"><value><text>x</text></value></draw>')
        self.assertEqual(1, len(_kural(b, "XDP-05")))

    def test_arial_temiz(self):
        b = _bul('<field name="A" w="10mm"><ui><textEdit/></ui><font typeface="Arial" size="8pt"/></field>')
        self.assertEqual([], _kural(b, "XDP-05"))

    def test_barkod_ve_metinsiz_draw_muaf(self):
        b = _bul('<field name="B" w="60mm"><ui><barcode type="code3Of9"/></ui></field>'
                 '<draw w="10mm"><value><rectangle/></value></draw>')
        self.assertEqual([], _kural(b, "XDP-05"))

    def test_locale_yok(self):
        b = _bul("", kok='name="data" layout="tb"')
        self.assertEqual(1, len(_kural(b, "XDP-05")))

    def test_locale_farkli(self):
        b = _bul("", kok='name="data" layout="tb" locale="en_US"', locale="tr_TR")
        self.assertEqual(1, len(_kural(b, "XDP-05")))
        self.assertEqual([], _kural(_bul("", locale="tr_TR"), "XDP-05"))


class R37LayoutReady(unittest.TestCase):
    def _olay(self, oz):
        return _bul('<field name="S" w="10mm"><ui><textEdit/></ui><font typeface="Arial"/>'
                    '<event %s><script>1</script></event></field>' % oz)

    def test_layout_ready_hata(self):
        self.assertEqual(1, len(_kural(self._olay('activity="layout:ready"'), "R-3.7", "HATA")))

    def test_dogru_bicim_temiz(self):
        self.assertEqual([], _kural(self._olay('activity="ready" ref="$layout"'), "R-3.7"))

    def test_baska_iki_noktali_uyari(self):
        self.assertEqual(1, len(_kural(self._olay('activity="form:ready"'), "R-3.7", "UYARI")))

    def test_main_cikis_1(self):
        with c.gecici_dizin() as td:
            yol = c.yaz(os.path.join(td, "x.xdp"), c.xdp(
                '<field name="S"><ui><textEdit/></ui><font typeface="Arial"/>'
                '<event activity="layout:ready"><script>1</script></event></field>'))
            rc, out, _ = c.call_main(d.main, [yol])
        self.assertEqual(1, rc)
        self.assertIn("KAPSAM BEYANI", out)
        self.assertIn("BAKILMAYANLAR", out)


class R33SabitYukseklik(unittest.TestCase):
    def _alan(self, oz, ml=True):
        return _bul('<field name="M" w="50mm" %s><ui><textEdit%s/></ui><font typeface="Arial"/></field>'
                    % (oz, ' multiLine="1"' if ml else ""))

    def test_multiline_sabit_h_uyari(self):
        self.assertEqual(1, len(_kural(self._alan('h="5mm"'), "R-3.3")))

    def test_multiline_minh_temiz(self):
        self.assertEqual([], _kural(self._alan('minH="5mm"'), "R-3.3"))

    def test_tek_satir_sabit_h_temiz(self):
        self.assertEqual([], _kural(self._alan('h="5mm"', ml=False), "R-3.3"))


class SablonlarVeGirdi(unittest.TestCase):
    def test_sablonlar_kendi_kurallarina_uyar(self):
        """Gönderilen şablonlar HATA 0 ve XDP-03/05, R-3.3 UYARI 0 (XDP-04 Türkçe etiketleri listeler — okunacak)."""
        for ad in ("tek-belge.xdp", "cok-belge.xdp"):
            with self.subTest(ad=ad):
                b, say = d.denetle(ortak.oku(os.path.join(c.TEMPLATES, ad)), locale="tr_TR")
                self.assertEqual([], [x for x in b if x[0] == "HATA"])
                self.assertEqual([], [x for x in b if x[0] == "UYARI" and x[1] != "XDP-04"])
                self.assertGreaterEqual(say["lr-tb satırı"], 4)
                self.assertEqual(0, say["XDP-03 ölçülemedi"])

    def test_bozuk_xml_cikis_2(self):
        with c.gecici_dizin() as td:
            yol = c.yaz(os.path.join(td, "x.xdp"), "<xdp><template>")
            rc, _, err = c.call_main(d.main, [yol])
        self.assertEqual(2, rc)
        self.assertIn("ayrıştırılamadı", err)

    def test_template_yok_cikis_2(self):
        with c.gecici_dizin() as td:
            yol = c.yaz(os.path.join(td, "x.xdp"), "<xdp/>")
            rc, _, err = c.call_main(d.main, [yol])
        self.assertEqual(2, rc)
        self.assertIn("template", err)


if __name__ == "__main__":
    unittest.main()
