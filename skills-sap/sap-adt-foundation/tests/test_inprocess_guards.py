# -*- coding: utf-8 -*-
"""Araç fonksiyonlarının KENDİ guard'ları istemci/ağ çağrısından ÖNCE çalışıyor mu (süreç içi).

CLI kapısı bu guard'ların önünde ikinci bir katmandır; bu test CLI'yi atlayıp araç fonksiyonunu
doğrudan çağırır ve `_get_client`'ı "çağrılırsa patla" ile değiştirir. Guard ağdan önce koşmasaydı
AssertionError yükselirdi (kontrol: `test_kontrol_istemci_cagrilir`).
"""
from __future__ import annotations

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


class _IstemciCagrildi(AssertionError):
    pass


def _patla(*_a, **_k):
    raise _IstemciCagrildi("istemci/ağ çağrıldı — guard ağdan ÖNCE koşmadı")


class AracGuardlari(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="axet_inproc_"))
        cls.dev = H.make_project(cls.root, "dev")
        cls.qa = H.make_project(cls.root, "qa", tier_lines=("ADT_SAP_TIER=QA",))
        cls._eski_env = {k: os.environ.get(k) for k in ("AXET_SAP_PROJECT_DIR", "ADT_SAP_TIER")}
        os.environ.pop("ADT_SAP_TIER", None)
        os.environ["AXET_SAP_PROJECT_DIR"] = str(cls.dev)
        from sapadt.tools import atom, composite, query  # noqa: F401
        cls.atom, cls.composite, cls.query = atom, composite, query
        cls._eski_client = atom._get_client
        atom._get_client = _patla

    @classmethod
    def tearDownClass(cls):
        cls.atom._get_client = cls._eski_client
        for k, v in cls._eski_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(cls.root, ignore_errors=True)

    def proje(self, p):
        os.environ["AXET_SAP_PROJECT_DIR"] = str(p)

    def bekle(self, ad, sonuc, kod):
        gercek = sonuc.get("code") if isinstance(sonuc, dict) else repr(sonuc)
        ok = isinstance(sonuc, dict) and sonuc.get("error") == "guardrail_violation" and gercek == kod
        H.kaydet(f"süreç-içi {ad}", kod, str(gercek), ok)
        self.assertTrue(ok, f"{ad}: {sonuc}")

    def test_dev_namespace_transport_labels(self):
        a, c, q = self.atom, self.composite, self.query
        self.proje(self.dev)
        self.bekle("adt_post_shell std", a.adt_post_shell("class", "MARA", "$TMP", "T", "d"), "ADR_0005_A")
        self.bekle("adt_post_shell transport boş", a.adt_post_shell("class", "ZAXET_X", "$TMP", "", "d"), "ADR_0005_C")
        self.bekle("adt_push_source std", a.adt_push_source("MARA", "class", "x"), "ADR_0005_A")
        self.bekle("adt_push_source Z sınıf + std tablo DML (Yasak B, 2. katman)",
                   a.adt_push_source("ZAXET_X", "class", "METHOD m.\n  DELETE FROM likp WHERE vbeln = lv.\nENDMETHOD."),
                   "ADR_0005_B")
        self.bekle("adt_delete std", a.adt_delete("MARA", "tabl"), "ADR_0005_A")
        self.bekle("adt_activate std", a.adt_activate("MARA"), "ADR_0005_A")
        self.bekle("adt_activate also std", a.adt_activate("ZAXET_X", also=[{"name": "MARA", "object_type": "tabl"}]), "ADR_0005_A")
        self.bekle("adt_publish_service std", a.adt_publish_service("API_X"), "ADR_0005_A")
        self.bekle("adt_classrun std", a.adt_classrun("CL_X"), "ADR_0005_A")
        self.bekle("adt_domain_create std", c.adt_domain_create("MATNR", "CHAR", 10, "d", "$TMP", "T"), "ADR_0005_A")
        self.bekle("adt_dtel_create std", c.adt_dtel_create("MATNR", "MATNR", "d", "$TMP", "T", "a", "b", "c", "d"), "ADR_0005_A")
        self.bekle("adt_dtel_create eksik label", c.adt_dtel_create("ZAXET_E", "ZAXET_D", "d", "$TMP", "T", "a", "", "c", "d"), "ADR_0005_D")
        self.bekle("adt_struct_create std", c.adt_struct_create("BAPIRET2", [{"name": "F", "type": "char10"}], "d", "$TMP", "T"), "ADR_0005_A")
        self.bekle("adt_syntax_check std", q.adt_syntax_check("SAPMV45A", "program"), "ADR_0005_A")
        self.bekle("adt_unit_run std", q.adt_unit_run("CL_X"), "ADR_0005_A")

    def test_qa_tier_and_pii(self):
        a, q = self.atom, self.query
        self.proje(self.qa)
        self.bekle("QA adt_activate Z", a.adt_activate("ZAXET_X"), "ADR_0010_TIER")
        self.bekle("QA adt_push_source Z", a.adt_push_source("ZAXET_X", "class", "x"), "ADR_0010_TIER")
        self.bekle("QA adt_table_read KNA1", q.adt_table_read("KNA1"), "ADR_0011_PII")
        self.bekle("QA adt_sql_query JOIN", q.adt_sql_query(
            "SELECT a~bankn FROM lfbk AS a JOIN lfa1 AS b ON a~lifnr = b~lifnr"), "ADR_0011_PII")

    def test_kontrol_istemci_cagrilir(self):
        """KONTROL GRUBU: guard'dan geçen çağrı istemciye ulaşır (yama gerçekten devrede)."""
        self.proje(self.dev)
        with self.assertRaises(_IstemciCagrildi):
            self.atom.adt_activate("ZAXET_X")
        H.kaydet("süreç-içi KONTROL geçerli çağrı istemciye ulaşır", "_IstemciCagrildi", "_IstemciCagrildi", True)


if __name__ == "__main__":
    unittest.main()
