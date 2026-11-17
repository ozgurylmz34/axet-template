# -*- coding: utf-8 -*-
"""Uyum turu 8 tamamlama — süreç içi, ağ YOK (sahte istemciler).

  · W — `adt_where_used(object_type='bdef')` (kaynak çekirdek c457161 #434): genel tip tablosunda BDEF yok ⇒
        dar uç `/sap/bc/adt/bo/behaviordefinitions/<url_segmenti(ad)>`; varlık AYNI uçtan (yalnız 404 = yok;
        500 yükselir, "yok" sayılmaz); diğer tipler eski yoldan (`object_exists`).
  · Y — yerel dosya adı (kaynak çekirdek ce8a124 G1): `SAPClient.download_object` / `delete_object` namespace'li
        adı `#ns#x` dosyasına çevirir; eski `f"{object_name}.abap"` `/NS/X`'te sürücü köküne kaçardı
        (`delete_object` orada `unlink` ederdi).
  · P — `adt_publish_service` yanıtında `metadata_path` (kaynak çekirdek e52ad6f/ce8a124 G3): Z/Y
        `/sap/opu/odata/sap/<AD>/$metadata`, `/NS/X` → `/sap/opu/odata/ns/X/$metadata`.
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
if str(H.SCRIPTS) not in sys.path:
    sys.path.insert(0, str(H.SCRIPTS))

import sapadt  # noqa: E402,F401
import sap_adt_lib as L  # noqa: E402
import sap_client as SC  # noqa: E402


class _Proje:
    """`AXET_SAP_PROJECT_DIR` → geçici sahte proje (127.0.0.1:9; ağa gidilmez)."""

    def __enter__(self):
        self.kok = Path(tempfile.mkdtemp(prefix="axet_t8t_"))
        self.eski = {k: os.environ.get(k) for k in ("AXET_SAP_PROJECT_DIR", "ADT_SAP_TIER")}
        os.environ.pop("ADT_SAP_TIER", None)
        os.environ["AXET_SAP_PROJECT_DIR"] = str(H.make_project(self.kok, "p"))
        return self

    def __exit__(self, *a):
        for k, v in self.eski.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.kok, ignore_errors=True)


# ─────────────────────────── W — BDEF where-used ───────────────────────────
class _WAdt:
    def __init__(self, yapi_hatasi=None):
        self.yapi_hatasi = yapi_hatasi
        self.yapi_url, self.wu_url = [], []

    def get_object_structure(self, url, version="active"):
        self.yapi_url.append(url)
        if self.yapi_hatasi is not None:
            raise self.yapi_hatasi
        return "<ok/>"

    def where_used(self, url):
        self.wu_url.append(url)
        return [{"name": "ZSD001_C_X", "type": "BDEF/BDO", "uri": "/sap/bc/adt/bo/behaviordefinitions/zsd001_c_x"},
                {"name": "ZSD001_I_X", "type": "BDEF/BDO", "uri": "/sap/bc/adt/bo/behaviordefinitions/zsd001_i_x"}]


class _WIstemci:
    def __init__(self, adt):
        self.adt_client = adt
        self.exists_cagri = []

    def object_exists(self, name, object_type="class"):
        self.exists_cagri.append((name, object_type))
        return True

    def resolve_function_module(self, name):  # pragma: no cover — bu testlerde çağrılmamalı
        raise AssertionError("FM yolu çağrılmamalı")


def _where_used(istemci, name, tip):
    from sapadt.tools import query
    eski = query._get_client
    try:
        query._get_client = lambda: istemci
        with _Proje():
            return query.adt_where_used(name, tip)
    finally:
        query._get_client = eski


class BdefWhereUsed(unittest.TestCase):
    def test_W1_bdef_dar_uc_varlik_ve_referans_ayni_uctan(self):
        adt = _WAdt()
        ist = _WIstemci(adt)
        r = _where_used(ist, "ZSD001_I_X", "bdef")
        beklenen = "/sap/bc/adt/bo/behaviordefinitions/zsd001_i_x"
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(adt.yapi_url, [beklenen])
        self.assertEqual(adt.wu_url, [beklenen])
        self.assertEqual(ist.exists_cagri, [], "bdef genel tabloya (object_exists) düşmemeli")
        self.assertEqual(r.get("count"), 2, "BDEF'in kendisi de referans olarak sayılır (süzülmez)")

    def test_W2_bdef_namespace_url_kodlu(self):
        adt = _WAdt()
        r = _where_used(_WIstemci(adt), "/NSX/I_X", "BDEF")
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(adt.wu_url, ["/sap/bc/adt/bo/behaviordefinitions/%2Fnsx%2Fi_x"])

    def test_W3_bdef_404_obje_yok_where_used_kosmaz(self):
        adt = _WAdt(yapi_hatasi=L.SAPADTError("yok", status_code=404))
        r = _where_used(_WIstemci(adt), "ZSD001_I_YOK", "bdef")
        self.assertFalse(r.get("ok"))
        self.assertEqual(r.get("error_code"), "OBJECT_NOT_FOUND")
        self.assertNotIn("count", r)
        self.assertEqual(adt.wu_url, [])

    def test_W4_bdef_500_yok_sayilmaz(self):
        adt = _WAdt(yapi_hatasi=L.SAPADTError("sunucu", status_code=500))
        r = _where_used(_WIstemci(adt), "ZSD001_I_X", "bdef")
        self.assertFalse(r.get("ok"))
        self.assertNotEqual(r.get("error_code"), "OBJECT_NOT_FOUND", r)
        self.assertNotIn("count", r)
        self.assertEqual(adt.wu_url, [])

    def test_W5_kontrol_class_eski_yoldan(self):
        adt = _WAdt()
        ist = _WIstemci(adt)
        r = _where_used(ist, "ZCL_SD001_X", "class")
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(ist.exists_cagri, [("ZCL_SD001_X", "class")])
        self.assertEqual(adt.yapi_url, [])
        self.assertEqual(adt.wu_url, ["/sap/bc/adt/oo/classes/zcl_sd001_x"])


# ─────────────────────────── Y — yerel dosya adı ───────────────────────────
class _YAdt:
    url = "http://sahte.invalid"

    def __init__(self):
        self.silinen = []

    def get_object_source(self, url):
        return "REPORT x.\r\n"

    def lock_object(self, url, transport=None):
        return "NO_LOCK_SUPPORT"

    def delete_object(self, url, lock_handle, transport):
        self.silinen.append(url)


def _sc(kok: Path):
    c = SC.SAPClient.__new__(SC.SAPClient)
    c.adt_client = _YAdt()
    c.local_base = kok / ".tmp" / "sap_scratch" / "classes"
    c.debug_enabled = False
    return c


class YerelDosyaAdi(unittest.TestCase):
    def setUp(self):
        self.kok = Path(tempfile.mkdtemp(prefix="axet_t8y_"))

    def tearDown(self):
        shutil.rmtree(self.kok, ignore_errors=True)

    def test_Y1_download_namespace_dosyasi_kok_altinda(self):
        c = _sc(self.kok)
        with contextlib.redirect_stdout(io.StringIO()):
            c.download_object("/NSX/ZPROG", "program", save_local=True)
        yazilan = [p for p in self.kok.rglob("*.abap")]
        self.assertEqual([p.name for p in yazilan], ["#nsx#zprog.abap"], yazilan)

    def test_Y2_kontrol_z_adi_aynen(self):
        c = _sc(self.kok)
        with contextlib.redirect_stdout(io.StringIO()):
            c.download_object("ZSD001_PROG", "program", save_local=True)
        self.assertEqual([p.name for p in self.kok.rglob("*.abap")], ["ZSD001_PROG.abap"])

    def test_Y3_delete_yalniz_kok_altindaki_dosyayi_siler(self):
        c = _sc(self.kok)
        with contextlib.redirect_stdout(io.StringIO()):
            c.download_object("/NSX/ZPROG", "program", save_local=True)
        hedef = next(self.kok.rglob("*.abap"))
        silinen = []
        gercek = Path.unlink
        kok = self.kok.resolve()

        def _kayitli_unlink(p, *a, **k):
            silinen.append(Path(p))
            if kok in Path(p).resolve().parents:   # yalnız geçici kökün içi gerçekten silinir
                return gercek(p, *a, **k)
            return None
        Path.unlink = _kayitli_unlink
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                ok = c.delete_object("/NSX/ZPROG", "program", transport="SAHK900001", confirm=False)
        finally:
            Path.unlink = gercek
        self.assertTrue(ok)
        self.assertEqual(silinen, [hedef], silinen)
        self.assertFalse(hedef.exists())

    def test_Y4_kablolama_ad_tureten_uc_yer(self):
        metin = (H.SCRIPTS / "sapadt" / "lib" / "sap_client.py").read_text(encoding="utf-8")
        kod = [s for s in metin.splitlines() if 'f"{object_name}.abap"' in s and not s.strip().startswith("#")]
        self.assertEqual(kod, [], kod)
        self.assertEqual(metin.count('f"{_yerel_ad_dosya(object_name)}.abap"'), 3)


# ─────────────────────────── P — publish metadata_path ───────────────────────────
class _PYanit:
    status_code = 200
    text = ('<?xml version="1.0"?><asx:abap xmlns:asx="http://www.sap.com/abapxml"><asx:values><DATA>'
            '<SEVERITY>OK</SEVERITY><SHORT_TEXT>ok</SHORT_TEXT></DATA></asx:values></asx:abap>')


class _PSession:
    verify = False

    def __init__(self):
        self.postlar = []

    def post(self, url, **k):
        self.postlar.append((url, k.get("params")))
        return _PYanit()


class _PAdt:
    url = "http://sahte.invalid"
    client = "100"
    language = "TR"

    def __init__(self):
        self.session = _PSession()


class _PIstemci:
    def __init__(self):
        self.adt_client = _PAdt()


def _publish(name):
    import rap_service
    from sapadt.tools import atom
    ist = _PIstemci()
    eski = (atom._get_client, atom.require_writable_tier, atom.require_customer_namespace, rap_service.csrf)
    try:
        atom._get_client = lambda: ist
        atom.require_writable_tier = lambda *a, **k: None
        atom.require_customer_namespace = lambda *a, **k: None
        rap_service.csrf = lambda adt: "T"
        with _Proje():
            return atom.adt_publish_service(name), ist
    finally:
        atom._get_client, atom.require_writable_tier, atom.require_customer_namespace, rap_service.csrf = eski


class PublishMetadataYolu(unittest.TestCase):
    def test_P1_z_servis(self):
        r, _ = _publish("ZSD001_UI_X_O2")
        self.assertEqual(r.get("metadata_path"), "/sap/opu/odata/sap/ZSD001_UI_X_O2/$metadata", r)

    def test_P2_namespace_servis(self):
        r, ist = _publish("/NSX/UI_X_O2")
        self.assertEqual(r.get("metadata_path"), "/sap/opu/odata/nsx/UI_X_O2/$metadata", r)
        self.assertEqual(len(ist.adt_client.session.postlar), 1)


if __name__ == "__main__":
    unittest.main()
