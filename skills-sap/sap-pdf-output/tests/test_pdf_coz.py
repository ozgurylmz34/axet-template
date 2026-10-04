# -*- coding: utf-8 -*-
"""pdf_coz.py: işaretli base64 → PDF, bayt/sayfa kıyası, anlamlı hata. Gerçek pypdf GEREKMEZ: yokluğu zorlanır
(ÖLÇÜLEMEDİ dalı), sayma dalı sahte modülle sınanır."""
import base64
import json
import os
import sys
import types
import unittest
from unittest import mock

import _common as c
import pdf_coz as p

# İçinde ham '/Type /Page' geçen sahte PDF: regex sayımı 2 derdi — araç bunu hüküm olarak KULLANMAMALI.
SAHTE_PDF = b"%PDF-1.7\n1 0 obj << /Type /Page >> endobj\n2 0 obj << /Type /Page >> endobj\n" + bytes(range(256)) * 3 + b"%%EOF\n"


def _cikti(pdf=SAHTE_PDF, ev_pages="1", bayt=None, satir=76, bas=p.BASLA, son=p.BITTI, govde=None):
    b64 = base64.b64encode(pdf).decode("ascii")
    satirlar = govde if govde is not None else [b64[i:i + satir] for i in range(0, len(b64), satir)]
    ust = ["EV_PAGES=%s" % ev_pages, "PDF_BAYT=%s" % (len(pdf) if bayt is None else bayt), "ADS_IZ_BASI=iz"]
    return "\n".join(ust + ([bas] if bas else []) + satirlar + ([son] if son else [])) + "\n"


def _sahte_pypdf(sayfa):
    mod = types.ModuleType("pypdf")

    class PdfReader:  # noqa: D401 - sahte
        def __init__(self, _f):
            self.pages = [object()] * sayfa
    mod.PdfReader = PdfReader
    return mod


class PdfCoz(unittest.TestCase):
    def setUp(self):
        self._td = c.gecici_dizin()
        self.td = self._td.name
        self.pdf = os.path.join(self.td, "x.pdf")

    def tearDown(self):
        self._td.cleanup()

    def _kos(self, metin, pypdf=None):
        girdi = c.yaz(os.path.join(self.td, "cikti.txt"), metin)
        with mock.patch.dict(sys.modules, {"pypdf": pypdf}):
            return c.call_main(p.main, [girdi, "--pdf", self.pdf])

    def test_pypdf_yokken_olculemedi_ve_regex_hukum_degil(self):
        rc, out, err = self._kos(_cikti())
        self.assertEqual(0, rc, out + err)
        with open(self.pdf, "rb") as fh:
            self.assertEqual(SAHTE_PDF, fh.read())
        self.assertIn("ÖLÇÜLEMEDİ", out)
        self.assertNotRegex(out, r"SAYFA: \d")
        self.assertIn("BAYT: eşit", out)

    def test_pypdf_esit(self):
        rc, out, _ = self._kos(_cikti(ev_pages="1"), pypdf=_sahte_pypdf(1))
        self.assertEqual(0, rc)
        self.assertIn("SAYFA KIYASI: eşit", out)

    def test_pypdf_farkli_cikis_1(self):
        rc, out, _ = self._kos(_cikti(ev_pages="1"), pypdf=_sahte_pypdf(2))
        self.assertEqual(1, rc)
        self.assertIn("UYUŞMAZLIK: pypdf 2", out)

    def test_bayt_farkli_cikis_1(self):
        rc, out, _ = self._kos(_cikti(bayt=12))
        self.assertEqual(1, rc)
        self.assertIn("UYUŞMAZLIK: PDF_BAYT=12", out)

    def test_isaretsiz_anlamli_hata(self):
        rc, _, err = self._kos(_cikti(bas=None, son=None))
        self.assertEqual(2, rc)
        self.assertIn("işaretleri", err)
        self.assertFalse(os.path.exists(self.pdf))

    def test_tek_isaret_hata(self):
        rc, _, err = self._kos(_cikti(son=None))
        self.assertEqual(2, rc)
        self.assertIn("tek değil", err)

    def test_iki_kosu_birlesmis_hata(self):
        rc, _, err = self._kos(_cikti() + _cikti())
        self.assertEqual(2, rc)
        self.assertIn("tek değil", err)

    def test_bozuk_base64_hata(self):
        b64 = base64.b64encode(SAHTE_PDF).decode("ascii")
        # 4 alfabe dışı karakter: gevşek çözücü bunları sessizce atıp "başarılı" derdi (uzunluk 4'ün katı kalır)
        rc, _, err = self._kos(_cikti(govde=[b64[:76], "!!!!" + b64[76:152]]))
        self.assertEqual(2, rc)
        self.assertIn("base64 çözülemedi", err)
        self.assertFalse(os.path.exists(self.pdf))

    def test_pdf_olmayan_veri_hata(self):
        rc, _, err = self._kos(_cikti(pdf=b"<html>hata sayfasi</html>"))
        self.assertEqual(2, rc)
        self.assertIn("PDF değil", err)

    def test_bos_govde_hata(self):
        rc, _, err = self._kos(_cikti(govde=[]))
        self.assertEqual(2, rc)
        self.assertIn("base64 yok", err)

    def test_tutarsiz_satir_uzunlugu_uyari(self):
        b64 = base64.b64encode(SAHTE_PDF).decode("ascii")
        govde = [b64[:76], b64[76:100], b64[100:]]
        rc, out, _ = self._kos(_cikti(govde=govde))
        self.assertEqual(0, rc)
        self.assertIn("satır uzunlukları tutarsız", out)

    def test_cli_json_girdi(self):
        rc, out, err = self._kos(json.dumps({"ok": True, "class": "ZCL_X", "status": 200, "output": _cikti()}))
        self.assertEqual(0, rc, out + err)

    def test_json_output_yok_hata(self):
        rc, _, err = self._kos(json.dumps({"ok": False, "error": "x"}))
        self.assertEqual(2, rc)
        self.assertIn("output", err)


if __name__ == "__main__":
    unittest.main()
