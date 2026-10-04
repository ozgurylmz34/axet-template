# -*- coding: utf-8 -*-
"""xdp_abap_uret.py: bağlama simülasyonu (çözülen/çözülemeyen/bağlanmayan), ABAP üretimi (ters tırnak, ≤ 255),
işaretli blok yazımı ve `--check` (güncel/bayat)."""
import os
import re
import shutil
import unittest

import _common as c
import _xdp_ortak as ortak
import xdp_abap_uret as u

ALAN = '<field name="%s" w="10mm"><ui><textEdit/></ui><font typeface="Arial"/><bind match="dataRef" ref="%s"/></field>'

SABLON = c.xdp(
    '<subform name="HDR" layout="lr-tb" w="192mm"><bind match="dataRef" ref="$record.HDR"/>'
    + ALAN % ("NO", "$.NO")
    + '<subform layout="lr-tb" w="192mm">' + ALAN % ("AD", "$.AD") + '</subform>'          # adsız: bağlam aynı
    + '<subform name="GRP" layout="tb"><bind match="none"/>' + ALAN % ("TR", "$.TARIH") + '</subform>'
    + '</subform>'
    + '<subform name="ITEMS" layout="tb"><bind match="dataRef" ref="$record.ITEMS"/>'
    + '<subform name="ROW" layout="lr-tb"><occur min="0" max="-1"/><bind match="dataRef" ref="$.ROW[*]"/>'
    + ALAN % ("M", "$.MATNR") + ALAN % ("N", "$.NOT") + '</subform></subform>')

VERI = ("<data><HDR><NO>1</NO><AD>x</AD><TARIH>t</TARIH></HDR>"
        "<ITEMS><ROW><MATNR>a</MATNR></ROW><ROW><MATNR>b</MATNR><NOT>yalnız ikinci örnekte</NOT></ROW></ITEMS></data>")


def _sim(sablon, veri):
    return u.bagla_simule(ortak.sablonu_bul(ortak.ayristir(sablon)), ortak.ayristir(veri))[0]


def _abap_coz(satirlar):
    """Üretilen metodu küçük bir ABAP yorumlayıcısıyla geri kurar (gidiş-dönüş kanıtı)."""
    out = []
    for s in satirlar:
        t = s.strip()
        if t == "rv_xml = rv_xml && nl.":
            out.append("\n")
            continue
        m = re.match(r"^rv_xml = rv_xml && `(.*)`( && nl)?\.$", t)
        if m:
            govde = m.group(1)
            # literal içinde tek başına ters tırnak OLAMAZ (ABAP'ta literal'i bitirir)
            assert "`" not in govde.replace("``", ""), t
            out.append(govde.replace("``", "`") + ("\n" if m.group(2) else ""))
    return "".join(out)


class BaglamaSimulasyonu(unittest.TestCase):
    def test_cozulen_baglar_temiz(self):
        b = _sim(SABLON, VERI)
        self.assertEqual([], b.hata)
        self.assertEqual([], b.uyari, "mutlak, göreli, adsız, match=none ve [*] bağları çözülmeli")

    def test_cozulemeyen_ref_hata(self):
        b = _sim(SABLON.replace("$.MATNR", "$.MATNR_YOK"), VERI)
        self.assertEqual(1, len(b.hata))
        self.assertIn("MATNR_YOK", b.hata[0])
        self.assertIn("ÇÖZÜLEMEDİ", b.hata[0])

    def test_cozulemeyen_subform_hata_ve_alt_bag_denetlenmez(self):
        b = _sim(SABLON.replace("$record.ITEMS", "$record.KALEMLER"), VERI)
        self.assertEqual(1, len(b.hata))
        self.assertIn("alt bağlar denetlenmedi", b.hata[0])

    def test_adsiz_subform_baglami_degistirmez(self):
        # adsız subform içindeki $.AD, HDR bağlamında çözülür; HDR yerine kökte arasaydı hata verirdi
        self.assertEqual([], _sim(SABLON, VERI).hata)
        b = _sim(SABLON, VERI.replace("<AD>x</AD>", "").replace("</data>", "<AD>kök</AD></data>"))
        self.assertTrue(any("$.AD" in h for h in b.hata), b.hata)

    def test_baglanmayan_veri_yapragi_uyari(self):
        b = _sim(SABLON, VERI.replace("</HDR>", "<FAZLA>z</FAZLA></HDR>"))
        self.assertEqual([], b.hata)
        self.assertEqual(1, len(b.uyari))
        self.assertIn("data/HDR/FAZLA", b.uyari[0])

    def test_tekrar_tum_ornekleri_gezer(self):
        """NOT yalnız 2. ROW'da: tüm örnekler gezilmezse 'bağlanmayan' ya da 'çözülemedi' çıkardı."""
        b = _sim(SABLON, VERI)
        self.assertFalse(any("NOT" in x for x in b.hata + b.uyari))

    def test_kok_ad_uyusmazligi(self):
        b = _sim(SABLON, VERI.replace("<data>", "<veri>").replace("</data>", "</veri>"))
        self.assertTrue(any("kök subform adı" in h for h in b.hata))

    def test_adli_bindsiz_subform_uyari(self):
        b = _sim(SABLON.replace('<bind match="none"/>', ""), VERI)
        self.assertTrue(any("adlı subform bind'siz" in x for x in b.uyari), b.uyari)

    def test_yildiz_occursuz_uyari(self):
        b = _sim(SABLON.replace('<occur min="0" max="-1"/>', ""), VERI)
        self.assertTrue(any("occur" in x for x in b.uyari), b.uyari)

    def test_desteklenmeyen_ref_simule_edilmedi(self):
        b = _sim(SABLON.replace("$.MATNR", "$data.ITEMS.ROW.MATNR"), VERI)
        self.assertTrue(any("SİMÜLE EDİLMEDİ" in x for x in b.uyari), b.uyari)


class AbapUretimi(unittest.TestCase):
    def test_ters_tirnak_ve_gidis_donus(self):
        metin = 'a`b ``c` sonda`\nİkinci satır ğüşöç\n\nson\n'
        self.assertEqual(metin, _abap_coz(u.abap_blok(metin, "get_xdp", "x.xdp")))

    def test_sonda_satir_sonu_yoksa_eklenmez(self):
        metin = "tek satır"
        self.assertEqual(metin, _abap_coz(u.abap_blok(metin, "get_xdp", "x.xdp")))

    def test_uzun_satir_255_parcalanir(self):
        for metin in ("x" * 1000 + "\n", "`" * 300 + "\n", ("ab`" * 200) + "\n", "ş" * 600):
            with self.subTest(uzunluk=len(metin), ilk=metin[0]):
                satirlar = u.abap_blok(metin, "get_xdp", "x.xdp")
                self.assertTrue(all(u._abap_uzunluk(s) <= 255 for s in satirlar),
                                max(u._abap_uzunluk(s) for s in satirlar))
                self.assertEqual(metin, _abap_coz(satirlar))

    def test_uzun_kaynak_adi_basligi_tasirmaz(self):
        satirlar = u.abap_blok("x\n", "get_xdp", "a" * 400 + ".xdp")
        self.assertTrue(all(u._abap_uzunluk(s) <= 255 for s in satirlar))

    def test_isaretler_ve_metot(self):
        s = u.abap_blok("x\n", "get_xdp", "x.xdp")
        self.assertRegex(s[0], r'^\s*" >>> URETILDI: get_xdp ')
        self.assertEqual("METHOD get_xdp.", s[1].strip())
        self.assertEqual('" <<< URETILDI: get_xdp', s[-1].strip())


class DosyaVeCheck(unittest.TestCase):
    def setUp(self):
        self._td = c.gecici_dizin()
        self.td = self._td.name
        self.xdp = c.yaz(os.path.join(self.td, "s.xdp"), SABLON)
        self.veri = c.yaz(os.path.join(self.td, "v.xml"), VERI)
        self.abap = os.path.join(self.td, "z.clas.abap")

    def tearDown(self):
        self._td.cleanup()

    def _kos(self, *ek):
        return c.call_main(u.main, ["--xdp", self.xdp, "--veri", self.veri, "--abap", self.abap, *ek])

    def test_yeni_dosya_ve_check_guncel(self):
        rc, out, _ = self._kos("--veri-gom")
        self.assertEqual(0, rc, out)
        self.assertIn("METHOD get_veri.", c.oku(self.abap))
        rc, out, _ = self._kos("--veri-gom", "--check")
        self.assertEqual(0, rc, out)
        self.assertEqual(2, out.count("GÜNCEL:"))

    def test_check_bayat(self):
        self._kos()
        c.yaz(self.xdp, SABLON.replace('w="10mm"', 'w="11mm"', 1))
        rc, out, _ = self._kos("--check")
        self.assertEqual(1, rc)
        self.assertIn("BAYAT: get_xdp", out)

    def test_check_blok_yok_bayat(self):
        self._kos()
        rc, out, _ = self._kos("--veri-gom", "--check")
        self.assertEqual(1, rc)
        self.assertIn("'get_veri' bloğu yok", out)

    def test_check_dosya_yok_cikis_2(self):
        rc, _, err = self._kos("--check")
        self.assertEqual(2, rc)

    def test_check_veri_gomsuz_uretilmis_veri_blogu_denetlenmedi(self):
        # --veri-gom ile üretilmiş dosyada --veri-gom'suz --check: get_veri sessizce "güncel" sayılmaz
        rc, out, _ = self._kos("--veri-gom")
        self.assertEqual(0, rc, out)
        c.yaz(self.veri, "<!-- degisti -->\n" + VERI)  # get_veri artık bayat
        rc, out, _ = self._kos("--check")
        self.assertEqual(1, rc, out)
        self.assertIn("GÜNCEL: get_xdp", out)
        self.assertIn("DENETLENMEDİ: get_veri", out)
        # kontrol grubu: veri bloğu hiç yoksa (--veri-gom'suz üretim) aynı komut temiz
        os.remove(self.abap)
        self.assertEqual(0, self._kos()[0])
        rc, out, _ = self._kos("--check")
        self.assertEqual(0, rc, out)
        self.assertNotIn("DENETLENMEDİ", out)

    def test_utf8_olmayan_abap_cikis_2(self):
        with open(self.abap, "wb") as fh:
            fh.write(b'" >>> URETILDI: get_xdp\n\xff\xfe\x80 bozuk\n')
        rc, _, err = self._kos("--check")
        self.assertEqual(2, rc)
        self.assertIn("UTF-8", err)
        with open(self.abap, "wb") as fh:
            fh.write(b'\xff\xfe\x80 bozuk\n')
        rc, _, err = self._kos()
        self.assertEqual(2, rc)
        self.assertIn("UTF-8", err)

    def test_255_asan_metot_adi_cikis_2(self):
        rc, _, err = self._kos("--xdp-metot", "m" * 300)
        self.assertEqual(2, rc)
        self.assertIn("ABAP üretilemedi", err)
        self.assertFalse(os.path.exists(self.abap))

    def test_var_olan_dosyada_yalniz_blok_degisir(self):
        shutil.copy(os.path.join(c.TEMPLATES, "deneme-classrun.clas.abap"), self.abap)
        once = c.oku(self.abap)
        rc, out, _ = self._kos("--veri-gom")
        self.assertEqual(0, rc, out)
        sonra = c.oku(self.abap)
        disari = lambda t: re.sub(r'(?s)" >>> URETILDI: (\S+).*?" <<< URETILDI: \1', "<BLOK>", t)  # noqa: E731
        self.assertEqual(disari(once), disari(sonra))
        self.assertNotEqual(once, sonra)
        self.assertEqual(0, self._kos("--veri-gom", "--check")[0])

    def test_isaretsiz_var_olan_dosya_ezilmez(self):
        c.yaz(self.abap, "CLASS x DEFINITION.\nENDCLASS.\n")
        rc, _, err = self._kos()
        self.assertEqual(2, rc)
        self.assertIn("işaretli blok yok", err)
        self.assertEqual("CLASS x DEFINITION.\nENDCLASS.\n", c.oku(self.abap))

    def test_baglama_hatasinda_yazilmaz(self):
        c.yaz(self.xdp, SABLON.replace("$.MATNR", "$.YOK"))
        rc, out, _ = self._kos()
        self.assertEqual(1, rc)
        self.assertIn("HATA bağlama", out)
        self.assertFalse(os.path.exists(self.abap))

    def test_kapsam_basilir(self):
        _, out, _ = self._kos()
        self.assertIn("KAPSAM:", out)
        self.assertIn("BAKILMAYANLAR", out)

    def test_sablonlar_hatasiz_baglanir(self):
        for x, v in (("tek-belge.xdp", "tek-belge-veri.xml"), ("cok-belge.xdp", "cok-belge-veri.xml")):
            with self.subTest(x=x):
                b = _sim(c.oku(os.path.join(c.TEMPLATES, x)), c.oku(os.path.join(c.TEMPLATES, v)))
                self.assertEqual(([], []), (b.hata, b.uyari))


if __name__ == "__main__":
    unittest.main()
