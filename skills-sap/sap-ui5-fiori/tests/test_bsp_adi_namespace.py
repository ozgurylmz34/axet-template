#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BSP adı + müşteri namespace'i (deploy_ui `prepare`/`verify`, `_bspnet.bsp_icf_yolu`, yinelenen anahtar).

Sözleşme (kaynak çekirdekteki `bsp_adi_namespace` vakasının aXet karşılığı):
  · BSP adı = ilk `deploy-to-abap` görevinin `configuration.app.name`'i; karar foundation `ad_politikasi`'ndan:
    Z/Y ya da projede `sap-project.json` → `customer_namespaces` ile bildirilmiş `/<NS>/` (+ `.conn_adt`).
  · Bildirilmemiş `/<NS>/` ve SAP adı RED · politika yüklenemezse RED (fail-closed) · harf duyarsız.
  · Canlı yol: Z/Y → `/sap/bc/ui5_ui5/sap/<bsp>/` · `/NS/APP` → `/sap/bc/ui5_ui5/<ns>/<app>/`; biçimsiz
    eğik çizgili ad → ValueError (sahte `…/sap//x/app/` yolu kurulmaz).
  · Görev bloğunda yinelenen anahtar → İHLAL (hangi değerin geçerli olduğu belirsiz).

Gerçek SAP'ye, npm'e ya da build'e GİTMEZ (prepare `--no-build`; verify 127.0.0.1 sahte sunucu).
KAPSAM — bakılmayan: namespace'li gerçek bir BSP'nin ICF yolu (aXet'te ÖLÇÜLMEDİ) · `deploy` yazma kapısının
namespace kabulü (foundation `gate.check_write` testlerinde) · namespace'li adda SAP'nin uzunluk sınırı.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _helpers as H

S = "deploy_ui.py"


def _modul(ad, dosya):
    spec = importlib.util.spec_from_file_location(ad, H.SCRIPTS / dosya)
    m = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(H.SCRIPTS))
    spec.loader.exec_module(m)
    return m


B = _modul("_bspnet_ns", "_bspnet.py")
D = _modul("deploy_ui_ns", "deploy_ui.py")


def _proje(namespaces=("/NSPC/",), conn=True) -> Path:
    """Geçici proje kökü: `sap-project.json` (+ istenirse boş `.conn_adt` — politika yalnız varlığına bakar)."""
    kok = Path(tempfile.mkdtemp(prefix="ui5proj_"))
    (kok / "sap-project.json").write_text(json.dumps({"customer_namespaces": list(namespaces)}), encoding="utf-8")
    if conn:
        (kok / ".conn_adt").write_text("", encoding="utf-8")
    return kok


class TestIcfYolu(unittest.TestCase):
    def test_zy_ve_namespace_yolu(self):
        sonuc = (B.bsp_icf_yolu("ZXX001_ORDER"), B.bsp_icf_yolu("YXX001_ORDER"), B.bsp_icf_yolu("/NSPC/ORDER"),
                 B.bsp_icf_yolu("/nspc/order"))
        beklenen = ("/sap/bc/ui5_ui5/sap/zxx001_order/", "/sap/bc/ui5_ui5/sap/yxx001_order/",
                    "/sap/bc/ui5_ui5/nspc/order/", "/sap/bc/ui5_ui5/nspc/order/")
        ok = sonuc == beklenen
        H.kaydet("ICF yolu: Z/Y sap düğümü · /NS/APP kardeş düğüm", "4 yol", str(sonuc), ok)
        self.assertEqual(sonuc, beklenen)

    def test_bicimsiz_egik_cizgi_fail_closed(self):
        reddedilen = []
        for ad in ("/X/APP", "/NSPC/", "/NSPC/A/B", "/TOOLONGNS/APP", "NS/APP"):
            try:
                B.bsp_icf_yolu(ad)
            except ValueError:
                reddedilen.append(ad)
        ok = len(reddedilen) == 5
        H.kaydet("ICF yolu: biçimsiz eğik çizgili ad → ValueError", "5/5", f"{len(reddedilen)}/5 {reddedilen}", ok)
        self.assertTrue(ok, reddedilen)

    def test_bsp_url_namespace_dali(self):
        url = B.bsp_url({"url": "https://sap-demo.invalid:44300/", "client": "100", "name": "/NSPC/ORDER"},
                        "Component-preload.js")
        ok = url.startswith("https://sap-demo.invalid:44300/sap/bc/ui5_ui5/nspc/order/Component-preload.js"
                            "?sap-client=100&cb=")
        H.kaydet("bsp_url: namespace'li ad kardeş düğüme gider", "…/nspc/order/…", url, ok)
        self.assertTrue(ok, url)


class TestPrepareAdPolitikasi(unittest.TestCase):
    def _prepare(self, ad, proje=None, yaml_degistir=None):
        app = H.gecici_app(name=ad)
        try:
            if yaml_degistir:
                y = app / "ui5-deploy.yaml"
                y.write_text(yaml_degistir(y.read_text(encoding="utf-8")), encoding="utf-8")
            args = [S, "prepare", app, "--no-build"] + (["--project-dir", proje] if proje else [])
            return H.kos(*args)
        finally:
            H.temizle(app)

    def test_y_adi_kabul(self):
        rc, out = self._prepare("YXX001_ORDER")
        ok = rc == 0 and "[HAZIR] BSP=YXX001_ORDER" in out and "[İHLAL]" not in out
        H.kaydet("prepare: Y önekli BSP adı kabul (eski kural yalnız Z)", "rc=0 HAZIR", f"rc={rc}", ok)
        self.assertTrue(ok, out)

    def test_kucuk_harf_z_kabul(self):
        rc, out = self._prepare("zxx001_order")
        ok = rc == 0 and "[İHLAL]" not in out
        H.kaydet("prepare: küçük harfli z adı kabul (karar büyük harfle)", "rc=0", f"rc={rc}", ok)
        self.assertTrue(ok, out)

    def test_bildirilmis_namespace_kabul(self):
        proje = _proje()
        try:
            rc, out = self._prepare("/NSPC/ORDER", proje)
        finally:
            shutil.rmtree(proje, ignore_errors=True)
        ok = rc == 0 and "[HAZIR] BSP=/NSPC/ORDER" in out and "[İHLAL]" not in out
        H.kaydet("prepare: bildirilmiş /NSPC/ adı kabul", "rc=0 HAZIR", f"rc={rc}", ok)
        self.assertTrue(ok, out)

    def test_bildirilmemis_namespace_red(self):
        proje = _proje()
        try:
            rc, out = self._prepare("/OTHR/ORDER", proje)
        finally:
            shutil.rmtree(proje, ignore_errors=True)
        ok = rc == 1 and "[İHLAL] BSP adı '/OTHR/ORDER'" in out and "bildirilmemiş" in out and "[HAZIR]" not in out
        H.kaydet("prepare: bildirilmemiş /OTHR/ RED (negatif)", "rc=1 İHLAL", f"rc={rc}", ok)
        self.assertTrue(ok, out)

    def test_namespace_baglanti_dosyasi_yoksa_red(self):
        proje = _proje(conn=False)
        try:
            rc, out = self._prepare("/NSPC/ORDER", proje)
        finally:
            shutil.rmtree(proje, ignore_errors=True)
        ok = rc == 1 and "[İHLAL] BSP adı '/NSPC/ORDER'" in out and "KAPALI" in out
        H.kaydet("prepare: .conn_adt yok → namespace kabulü kapalı (fail-closed)", "rc=1 İHLAL", f"rc={rc}", ok)
        self.assertTrue(ok, out)

    def test_project_dir_yok_namespace_red(self):
        rc, out = self._prepare("/NSPC/ORDER")
        ok = rc == 1 and "[İHLAL] BSP adı '/NSPC/ORDER'" in out
        H.kaydet("prepare: --project-dir yok (cwd'de bildirim yok) → /NSPC/ RED", "rc=1", f"rc={rc}", ok)
        self.assertTrue(ok, out)

    def test_standart_ad_red(self):
        rc, out = self._prepare("SAPORDER")
        ok = rc == 1 and "[İHLAL] BSP adı 'SAPORDER'" in out and "müşteri ad alanı" in out
        H.kaydet("prepare: SAP adı (Z/Y/NS değil) RED", "rc=1 İHLAL", f"rc={rc}", ok)
        self.assertTrue(ok, out)

    def test_yinelenen_anahtar_red(self):
        rc, out = self._prepare("ZXX001_ORDER", yaml_degistir=lambda t: t.replace(
            "          name: ZXX001_ORDER\n", "          name: ZXX001_ORDER\n          name: SAPORDER\n"))
        ok = rc == 1 and "YİNELENEN anahtar" in out and ".app.name" in out
        H.kaydet("prepare: görev bloğunda yinelenen app.name → İHLAL", "rc=1", f"rc={rc}", ok)
        self.assertTrue(ok, out)

    def test_yinelenen_kontrol_grubu_baska_gorev(self):
        """Başka görevdeki (`ui5-task-zipper`) yinelenen anahtar deploy görevini ETKİLEMEZ."""
        rc, out = self._prepare("ZXX001_ORDER", yaml_degistir=lambda t: t.replace(
            "        archiveName: demo\n", "        archiveName: demo\n        archiveName: demo2\n"))
        ok = rc == 0 and "YİNELENEN" not in out
        H.kaydet("prepare: başka görevde yinelenen anahtar → işaretlenmez", "rc=0", f"rc={rc}", ok)
        self.assertTrue(ok, out)

    def test_politika_yuklenemezse_fail_closed(self):
        with mock.patch.object(D.B, "ad_politikasi", side_effect=ImportError("yok")):
            sonuc = D.bsp_adi_denetimi("ZXX001_ORDER")
        ok = len(sonuc) == 1 and "denetlenemedi" in sonuc[0] and "fail-closed" in sonuc[0]
        H.kaydet("prepare: ad politikası yüklenemezse Z adı da RED", "1 ihlal", str(sonuc)[:60], ok)
        self.assertTrue(ok, sonuc)


class TestVerifyNamespace(unittest.TestCase):
    def test_namespace_canli_yolu(self):
        with H.SahteSunucu({"/sap/bc/ui5_ui5/nspc/order/Component-preload.js": H.PRELOAD}) as srv:
            app = H.gecici_app(url=srv.url, name="/NSPC/ORDER")
            try:
                rc, out = H.kos(S, "verify", app, kimlik=True)
            finally:
                H.temizle(app)
        ok = rc == 0 and "CANLI == dist" in out
        H.kaydet("verify: /NSPC/ORDER canlı preload kardeş düğümden okunur", "rc=0 OK", f"rc={rc}", ok)
        self.assertTrue(ok, out)

    def test_bicimsiz_ad_olculemedi(self):
        with H.SahteSunucu({"/sap/bc/ui5_ui5/sap//x/order/Component-preload.js": H.PRELOAD}) as srv:
            app = H.gecici_app(url=srv.url, name="/X/ORDER")
            try:
                rc, out = H.kos(S, "verify", app, kimlik=True)
            finally:
                H.temizle(app)
        ok = rc == 2 and "ValueError" in out and "CANLI == dist" not in out
        H.kaydet("verify: biçimsiz /X/ORDER → ÖLÇÜLEMEDİ (sahte yol kurulmaz)", "rc=2", f"rc={rc}", ok)
        self.assertTrue(ok, out)


if __name__ == "__main__":
    unittest.main()
