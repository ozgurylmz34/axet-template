#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""deploy_ui.py: yaml okuyucu, prepare (+/-), verify (+/-/OK~/kimliksiz), deploy RED yolları.

Gerçek deploy, npm ya da build KOŞULMAZ: prepare `--no-build` ile, deploy yalnız ret dallarında test edilir.
"""
from __future__ import annotations

import importlib.util
import unittest

import _helpers as H

S = "deploy_ui.py"


def _modul(ad, dosya):
    spec = importlib.util.spec_from_file_location(ad, H.SCRIPTS / dosya)
    m = importlib.util.module_from_spec(spec)
    import sys
    sys.path.insert(0, str(H.SCRIPTS))
    spec.loader.exec_module(m)
    return m


B = _modul("_bspnet_t", "_bspnet.py")
D = _modul("deploy_ui_t", "deploy_ui.py")


def _canli_yol(name="ZXX001_ORDER"):
    return f"/sap/bc/ui5_ui5/sap/{name.lower()}/Component-preload.js"


class TestYaml(unittest.TestCase):
    def test_deploy_ayari(self):
        app = H.gecici_app(url="https://sap-demo.invalid:44300")
        try:
            a = B.deploy_ayari(app)
            ok = (a["gorev"] and a["url"] == "https://sap-demo.invalid:44300" and a["client"] == "100"
                  and a["name"] == "ZXX001_ORDER" and a["package"] == "ZXX001" and a["transport"] == "ZXXK900001"
                  and a["exclude"] == ["/test/"] and a["resources_excludes"] == ["/test/**", "/localService/**"])
            H.kaydet("yaml: 2. görevdeki deploy-to-abap + yorum/tırnak", "alanlar doğru", str(ok), ok)
            self.assertTrue(ok, a)
        finally:
            H.temizle(app)


class TestPreloadKiyas(unittest.TestCase):
    def test_siniflar(self):
        crlf = H.PRELOAD.replace(rb">\n<", rb">\r\n<")
        gercek_crlf = H.PRELOAD.replace(b"\n", b"\r\n")
        farkli = H.PRELOAD.replace(b"return 1;", b"return 2;")
        s1 = D.preload_karsilastir(H.PRELOAD, gercek_crlf)[0]
        s2 = D.preload_karsilastir(H.PRELOAD, crlf)[0]
        s3 = D.preload_karsilastir(H.PRELOAD, farkli)[0]
        ok = (s1, s2, s3) == ("AYNI", "SATIR_SONU", "FARKLI")
        H.kaydet("preload: gerçek CRLF=AYNI · kaçışlı=SATIR_SONU · JS=FARKLI", "AYNI/SATIR_SONU/FARKLI",
                 f"{s1}/{s2}/{s3}", ok)
        self.assertTrue(ok)


class TestPrepare(unittest.TestCase):
    def test_pozitif(self):
        app = H.gecici_app()
        try:
            rc, out = H.kos(S, "prepare", app, "--no-build")
            ok = rc == 0 and "[HAZIR] BSP=ZXX001_ORDER" in out and "DEPLOY KOMUTU (KOŞULMADI)" in out \
                and "[İHLAL]" not in out and ".eslintrc" not in out and "BAKILMAYANLAR" in out
            H.kaydet("prepare: temiz uygulama → HAZIR + komut basılır", "rc=0", f"rc={rc}", ok)
            self.assertTrue(ok, out)
        finally:
            H.temizle(app)

    def test_negatif(self):
        app = H.gecici_app(name="ZXX001_ORDER_APPLICATION", dist_taze=False)
        try:
            (app / "webapp" / ".axet-code").mkdir()
            (app / "webapp" / ".axet-code" / "notes.txt").write_text("x", encoding="utf-8")
            (app / "webapp" / "img").mkdir()
            (app / "webapp" / "img" / "logo.svg").write_text("<svg/>", encoding="utf-8")
            rc, out = H.kos(S, "prepare", app, "--no-build")
            beklenen = ["en çok 15", "gizli/stray dosya", "logo.svg: BSP bu uzantıyı tanımaz", "dist BAYAT",
                        "Deploy'a HAZIR DEĞİL"]
            eksik = [b for b in beklenen if b not in out]
            ok = rc == 1 and not eksik and "DEPLOY KOMUTU" not in out
            H.kaydet("prepare: uzun BSP adı + stray + .svg + bayat dist", "rc=1", f"rc={rc} eksik={eksik}", ok)
            self.assertTrue(ok, out)
        finally:
            H.temizle(app)

    def test_yaml_yok(self):
        app = H.gecici_app()
        try:
            (app / "ui5-deploy.yaml").unlink()
            rc, out = H.kos(S, "prepare", app, "--no-build")
            ok = rc == 1 and "ui5-deploy.yaml yok" in out
            H.kaydet("prepare: ui5-deploy.yaml yok → ihlal", "rc=1", f"rc={rc}", ok)
            self.assertTrue(ok, out)
        finally:
            H.temizle(app)


class TestVerify(unittest.TestCase):
    def _kos(self, canli: bytes | None, kimlik=True):
        dosyalar = {} if canli is None else {_canli_yol(): canli}
        with H.SahteSunucu(dosyalar) as srv:
            app = H.gecici_app(url=srv.url)
            try:
                return H.kos(S, "verify", app, kimlik=kimlik)
            finally:
                H.temizle(app)

    def test_pozitif_crlf(self):
        rc, out = self._kos(H.PRELOAD.replace(b"\n", b"\r\n"))
        ok = rc == 0 and "[OK]" in out and "CANLI == dist" in out and H.PAROLA not in out
        H.kaydet("verify: canlı (CRLF bayt) == dist → OK, parola basılmaz", "rc=0", f"rc={rc}", ok)
        self.assertTrue(ok, out)

    def test_ok_tilda(self):
        rc, out = self._kos(H.PRELOAD.replace(rb">\n<", rb">\r\n<"))
        ok = rc == 0 and "[OK~]" in out
        H.kaydet("verify: yalnız kaçışlı \\r\\n farkı → OK~", "rc=0 OK~", f"rc={rc}", ok)
        self.assertTrue(ok, out)

    def test_negatif_stale(self):
        rc, out = self._kos(H.PRELOAD.replace(b"return 1;", b"return 2;"))
        ok = rc == 1 and "[STALE]" in out and "Farklı modül" in out
        H.kaydet("verify: canlı JS farklı → STALE", "rc=1", f"rc={rc}", ok)
        self.assertTrue(ok, out)

    def test_canlida_yok(self):
        rc, out = self._kos(None)
        ok = rc == 2 and "[ÖLÇÜLEMEDİ]" in out and "HTTPError 404" in out
        H.kaydet("verify: canlıda dosya yok → ÖLÇÜLEMEDİ", "rc=2", f"rc={rc}", ok)
        self.assertTrue(ok, out)

    def test_kimliksiz(self):
        rc, out = self._kos(H.PRELOAD, kimlik=False)
        ok = rc == 2 and "set değil" in out
        H.kaydet("verify: env kimlik yok → ÖLÇÜM YOK", "rc=2", f"rc={rc}", ok)
        self.assertTrue(ok, out)

    def test_kati_mod_kacis_stale(self):
        H.proxy_bypass_surec_ici()
        with H.SahteSunucu({_canli_yol(): H.PRELOAD.replace(rb">\n<", rb">\r\n<")}) as srv:
            app = H.gecici_app(url=srv.url)
            try:
                durum, _ = D.canli_dogrula(app, B.deploy_ayari(app), (H.KULLANICI, H.PAROLA), False, kati=True)
            finally:
                H.temizle(app)
        ok = durum == "STALE"
        H.kaydet("deploy sonrası KATI kıyas: kaçış farkı da STALE", "STALE", durum, ok)
        self.assertTrue(ok)


class TestDeployRed(unittest.TestCase):
    def test_onaysiz_red(self):
        app = H.gecici_app()
        try:
            rc, out = H.kos(S, "deploy", app, kimlik=True)
            ok = rc == 3 and "[REDDEDİLDİ] --user-ok" in out and "build:" not in out
            H.kaydet("deploy: --user-ok yok → REDDEDİLDİ, build bile yok", "rc=3", f"rc={rc}", ok)
            self.assertTrue(ok, out)
        finally:
            H.temizle(app)

    def test_yer_tutucu_onay_red(self):
        app = H.gecici_app()
        try:
            rc, out = H.kos(S, "deploy", app, "--user-ok", "<kullanıcının onay cümlesi>", kimlik=True)
            ok = rc == 3 and "REDDEDİLDİ" in out
            H.kaydet("deploy: yer tutucu onay metni → REDDEDİLDİ", "rc=3", f"rc={rc}", ok)
            self.assertTrue(ok, out)
        finally:
            H.temizle(app)

    def test_kimliksiz_red(self):
        app = H.gecici_app()
        try:
            rc, out = H.kos(S, "deploy", app, "--user-ok", "Kullanıcı: lokal test tamam, deploy et")
            ok = rc == 3 and "set değil" in out and "build:" not in out
            H.kaydet("deploy: onay var, env kimlik yok → REDDEDİLDİ", "rc=3", f"rc={rc}", ok)
            self.assertTrue(ok, out)
        finally:
            H.temizle(app)


if __name__ == "__main__":
    unittest.main()
