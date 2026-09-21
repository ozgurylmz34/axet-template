# -*- coding: utf-8 -*-
"""doc_tools tarayıcı seçimi: genel varsayılan Chrome, marp için Edge (kayıtlı tuzak), DOC_TOOLS_BROWSER ezer.

Makinedeki gerçek kurulumdan bağımsız: `os.path.exists` ve `shutil.which` sahtelenir.
"""
import os
import unittest
from unittest import mock

import doc_tools

CHROME = os.path.join("C:\\PF", "Google", "Chrome", "Application", "chrome.exe")
EDGE = os.path.join("C:\\PF", "Microsoft", "Edge", "Application", "msedge.exe")


def kurulu(*yollar):
    """Yalnız verilen tarayıcı dosyaları 'var'; kök dizin C:\\PF, PATH boş."""
    env = {"PROGRAMFILES": "C:\\PF", "PROGRAMFILES(X86)": "", "LOCALAPPDATA": "", "DOC_TOOLS_BROWSER": ""}
    return [mock.patch.dict(os.environ, env),
            mock.patch("doc_tools.os.path.exists", side_effect=lambda p: p in yollar),
            mock.patch("doc_tools.shutil.which", return_value=None)]


class DocToolsTarayiciTest(unittest.TestCase):
    def _kos(self, yollar, fn):
        yamalar = kurulu(*yollar)
        for y in yamalar:
            y.start()
        try:
            return fn()
        finally:
            for y in reversed(yamalar):
                y.stop()

    def test_genel_varsayilan_chrome_ikisi_de_kuruluyken(self):
        self.assertEqual(CHROME, self._kos([CHROME, EDGE], doc_tools.find_browser))

    def test_marp_edge_ikisi_de_kuruluyken(self):
        self.assertEqual(EDGE, self._kos([CHROME, EDGE], lambda: doc_tools.find_browser(prefer="edge")))
        self.assertEqual("edge", self._kos([CHROME, EDGE], doc_tools._browser_for_marp))

    def test_tek_tarayici_varsa_o_secilir(self):
        self.assertEqual(EDGE, self._kos([EDGE], doc_tools.find_browser))
        self.assertEqual(CHROME, self._kos([CHROME], lambda: doc_tools.find_browser(prefer="edge")))
        self.assertEqual("chrome", self._kos([CHROME], doc_tools._browser_for_marp))
        self.assertIsNone(self._kos([], doc_tools.find_browser))

    def test_env_ezer(self):
        ozel = os.path.join("C:\\X", "tarayici.exe")
        with mock.patch.dict(os.environ, {"DOC_TOOLS_BROWSER": ozel}), \
                mock.patch("doc_tools.os.path.exists", side_effect=lambda p: p in (ozel, CHROME, EDGE)):
            self.assertEqual(ozel, doc_tools.find_browser())
            self.assertEqual(ozel, doc_tools.find_browser(prefer="edge"))

    def test_path_sirasi_chrome_once(self):
        adlar = []

        def which(n):
            adlar.append(n)
            return None
        with mock.patch.dict(os.environ, {"PROGRAMFILES": "", "PROGRAMFILES(X86)": "", "LOCALAPPDATA": "",
                                          "DOC_TOOLS_BROWSER": ""}), \
                mock.patch("doc_tools.os.path.exists", return_value=False), \
                mock.patch("doc_tools.shutil.which", side_effect=which):
            doc_tools.find_browser()
        self.assertLess(adlar.index("chrome"), adlar.index("msedge"), adlar)


if __name__ == "__main__":
    unittest.main()
