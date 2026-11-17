# -*- coding: utf-8 -*-
"""Fonksiyon grubu include'u (FUGR/I) yazım + aktivasyon + kilit sorgusu (Q383; süreç içi, ağ yok).

Katmanlar ayrı ayrı ölçülür:
  · L — `object_types`: URL kurucusu, grup kanıtı (`programs/includes` contextRef), ad kuralı.
  · C — `SAPClient.push_fugr_include` / `activate_object(group=)`: grup kanıtı tutmazsa kilit/PUT/aktivasyon YOK.
  · T — araçlar (`adt_get` / `adt_push_source` / `adt_activate` / `adt_lock_check`): `group` sözleşmesi,
        sahte istemciyle çağrı listesi ("SAP'ye hiç gidilmedi" iddiası çağrı listesiyle kanıtlanır).
  · G — yazma kapısı (`gate.check_names`): include adı `L…` ⇒ kural GRUP üzerinden; grup yoksa RED.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _helpers as H

sys.dont_write_bytecode = True
if str(H.SCRIPTS) not in sys.path:
    sys.path.insert(0, str(H.SCRIPTS))

import sapadt  # noqa: E402,F401  (lib/ dizinini sys.path'e ekler)
import object_types as OT  # noqa: E402
from utils import ad_politikasi as ap  # noqa: E402

GRUP = "ZAXFG"
INCL = "LZAXFGF01"
KAYNAK = "FORM zaxet_olay.\n  WRITE 'eski'.\nENDFORM.\n"


def _progs_meta(ref_tip="FUGR/I", ref_ad="SAPLZAXFG", sayac="1", ek_ref=None):
    reflar = [f'<include:contextRef adtcore:uri="/sap/bc/adt/functions/groups/x" adtcore:type="{ref_tip}" '
              f'adtcore:name="{ref_ad}"/>']
    if ek_ref:
        reflar.append(f'<include:contextRef adtcore:type="{ek_ref[0]}" adtcore:name="{ek_ref[1]}"/>')
    return ('<include:include xmlns:include="http://www.sap.com/adt/programs/includes" '
            'xmlns:adtcore="http://www.sap.com/adt/core" '
            f'include:contextRefCount="{sayac}">' + "".join(reflar) + '</include:include>')


class _Yanit:
    def __init__(self, kod, metin=""):
        self.status_code, self.text = kod, metin


# ─────────────────────────── L — object_types ───────────────────────────
class L_ObjeTipleri(unittest.TestCase):
    def test_L1_url_z_ve_namespace_kodlama(self):
        u_z = OT.get_fugr_include_url(GRUP, INCL)
        u_ns = OT.get_fugr_include_url("/NSX/FG", "/NSX/LFGF01")
        ok = (u_z == "/sap/bc/adt/functions/groups/zaxfg/includes/lzaxfgf01"
              and u_ns == "/sap/bc/adt/functions/groups/%2Fnsx%2Ffg/includes/%2Fnsx%2Flfgf01")
        H.kaydet("FUGR L1 URL", "Z düz · /NS/ %2f kodlu", f"{u_z} · {u_ns}", ok)
        self.assertTrue(ok)
        with self.assertRaises(ValueError):
            OT.get_fugr_include_url("", INCL)
        with self.assertRaises(ValueError):
            OT.get_object_url(INCL, "fugr_include")   # tekil URL üretilemez (grup gerekir)

    def test_L2_grup_kaniti(self):
        k = OT.fugr_include_grup_kaniti
        vakalar = [
            ("doğru grup", _progs_meta(), GRUP, True),
            ("küçük harf/boşluklu doğru grup", _progs_meta(), "  zaxfg ", True),
            ("başka grup (önek kuralını geçen)", _progs_meta(), "ZAX", False),
            ("contextRefCount=2", _progs_meta(sayac="2"), GRUP, False),
            ("iki farklı FUGR bağlamı", _progs_meta(ek_ref=("FUGR/F", "ZBASKA")), GRUP, False),
            ("Z grupta FUGR/F kanıt DEĞİL", _progs_meta(ref_tip="FUGR/F", ref_ad=GRUP), GRUP, False),
            ("bozuk gövde", "<x", GRUP, False),
            ("boş grup", _progs_meta(), "", False),
        ]
        sonuc = [(ad, k(xml, g)[0]) for ad, xml, g, _ in vakalar]
        ok = all(s == v[3] for s, v in zip([x[1] for x in sonuc], vakalar))
        H.kaydet("FUGR L2 grup kanıtı", "8 vaka beklenen", str(sonuc), ok)
        self.assertTrue(ok, sonuc)

    def test_L3_ad_kurali(self):
        h = OT.fugr_include_ad_alani_hatasi
        std = h("SAPXFG", "LSAPXFGF01")
        onek = h(GRUP, "LZBASKAF01")
        dogru = h(GRUP, INCL)
        ok = bool(std and "ADR 0005-A" in std) and bool(onek and "oneki" in onek) and dogru is None
        H.kaydet("FUGR L3 ad kuralı", "standart grup red · önek red · doğru None", f"{std!r} · {onek!r} · {dogru!r}", ok)
        self.assertTrue(ok)


class L4_NamespaceGrup(unittest.TestCase):
    """Bildirilmiş namespace'li grupta FUGR/F <GRUP> kanıttır; bildirilmemişte DEĞİL (fail-closed)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="axet_fugrns_")
        self.kok = Path(self._tmp.name).resolve()
        (self.kok / ".conn_adt").write_text("ADT_SAP_URL=http://127.0.0.1:9\n", encoding="utf-8")
        self._y = [mock.patch.dict(os.environ, {"AXET_SAP_PROJECT_DIR": str(self.kok)}), mock.patch.dict(sys.modules)]
        for y in self._y:
            y.start()
        sys.modules.pop("sap_adt_lib", None)
        ap._ONBELLEK.clear()

    def tearDown(self):
        for y in reversed(self._y):
            y.stop()
        ap._ONBELLEK.clear()
        self._tmp.cleanup()

    def _ns(self, liste):
        (self.kok / "sap-project.json").write_text(json.dumps({**H.SAP_PROJECT_OK, "customer_namespaces": liste}),
                                                  encoding="utf-8")
        ap._ONBELLEK.clear()

    def test_L4_namespace(self):
        xml = _progs_meta(ref_tip="FUGR/F", ref_ad="/NSX/FG")
        self._ns(["/NSX/"])
        bildirilmis = OT.fugr_include_grup_kaniti(xml, "/NSX/FG")[0]
        ad_ok = OT.fugr_include_ad_alani_hatasi("/NSX/FG", "/NSX/LFGF01") is None
        self._ns([])
        bildirilmemis = OT.fugr_include_grup_kaniti(xml, "/NSX/FG")[0]
        ad_red = OT.fugr_include_ad_alani_hatasi("/NSX/FG", "/NSX/LFGF01")
        ok = bildirilmis is True and ad_ok and bildirilmemis is False and bool(ad_red)
        H.kaydet("FUGR L4 namespace grup", "bildirilmiş: kanıt+ad geçer · bildirilmemiş: ikisi red",
                 f"{bildirilmis} {ad_ok} · {bildirilmemis} {bool(ad_red)}", ok)
        self.assertTrue(ok)


# ─────────────────────────── C — SAPClient ───────────────────────────
class _SahteAdt:
    """`SAPClient.adt_client` yerine: metadata GET + kilit/PUT/aktivasyon/okuma çağrılarını kaydeder."""

    url = "http://sahte.invalid"
    timeout_short = 5

    def __init__(self, meta_kod=200, meta=None, aktif=None):
        self.iz: list[str] = []
        self.meta_kod, self.meta = meta_kod, meta if meta is not None else _progs_meta()
        self.aktif = aktif
        self.yuklenen = None
        dis = self

        class _Oturum:
            def get(self, url, **kw):
                dis.iz.append("GET " + url.replace(dis.url, ""))
                return _Yanit(dis.meta_kod, dis.meta)
        self.session = _Oturum()

    def fetch_source_etag(self, url):
        self.iz.append("ETAG")
        return "e1"

    def lock_object(self, url, transport=None):
        self.iz.append("LOCK " + url)
        return "H1"

    def set_object_source(self, url, kaynak, handle, transport, etag=None):
        self.iz.append("PUT " + url)
        self.yuklenen = kaynak

    def unlock_object(self, url, handle):
        self.iz.append("UNLOCK")
        return True

    def activate_object(self, name, url, object_type=None):
        self.iz.append("ACT " + url)
        return {"success": True}

    def get_object_source(self, url, return_etag=False, version=None):
        self.iz.append("READ")
        return self.aktif if self.aktif is not None else self.yuklenen


def _istemci(adt):
    from sap_client import SAPClient  # type: ignore
    s = SAPClient.__new__(SAPClient)
    s.adt_client = adt
    return s


class C_Istemci(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="axet_fugrc_"))
        self.dosya = self.tmp / "incl.abap"
        self.dosya.write_text(KAYNAK, encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_C1_kanit_tutmazsa_yazma_yok(self):
        adt = _SahteAdt(meta=_progs_meta(ref_ad="SAPLZBASKA"))
        s = _istemci(adt)
        r = s.push_fugr_include(INCL, GRUP, transport="DEVK900001", source_file=str(self.dosya))
        yazma = [x for x in adt.iz if not x.startswith("GET")]
        ok = r.get("success") is False and r.get("error_type") == "SAPValidationError" and yazma == []
        H.kaydet("FUGR C1 kanıt yok → kilit/PUT yok", "SAPValidationError · yazma=[]",
                 f"{r.get('error_type')} · {yazma}", ok)
        self.assertTrue(ok)
        # Kanıt kaynağı programs/includes'tur (FUGR/I ucu DEĞİL — SAP URL grubunu yansıtır)
        self.assertEqual(adt.iz, ["GET /sap/bc/adt/programs/includes/lzaxfgf01"])

    def test_C2_mutlu_yol_sira(self):
        adt = _SahteAdt()
        s = _istemci(adt)
        r = s.push_fugr_include(INCL, GRUP, transport="DEVK900001", source_file=str(self.dosya))
        u = "/sap/bc/adt/functions/groups/zaxfg/includes/lzaxfgf01"
        beklenen = ["GET /sap/bc/adt/programs/includes/lzaxfgf01", "ETAG", "LOCK " + u, "PUT " + u + "/source/main",
                    "UNLOCK", "ACT " + u, "READ"]
        ok = r.get("success") is True and r.get("readback_ok") is True and adt.iz == beklenen
        H.kaydet("FUGR C2 kanıt→kilit→PUT→unlock→akt→readback", "success · sıra", f"{r.get('success')} · {adt.iz}", ok)
        self.assertTrue(ok, r)

    def test_C3_readback_uyusmazligi_basari_degil(self):
        adt = _SahteAdt(aktif="FORM baska.\nENDFORM.\n")
        r = _istemci(adt).push_fugr_include(INCL, GRUP, transport="DEVK900001", source_file=str(self.dosya))
        ok = r.get("success") is False and r.get("readback_ok") is False
        H.kaydet("FUGR C3 readback farkı", "success False", f"{r.get('success')} {r.get('readback_ok')}", ok)
        self.assertTrue(ok)

    def test_C4_aktivasyon_kanitsiz_istek_yok(self):
        adt = _SahteAdt(meta_kod=404, meta="")
        r = _istemci(adt).activate_object(INCL, object_type="fugr_include", group=GRUP)
        ok = r is False and not any(x.startswith("ACT") for x in adt.iz)
        H.kaydet("FUGR C4 activate_object kanıtsız", "False · ACT yok", f"{r} · {adt.iz}", ok)
        self.assertTrue(ok)


# ─────────────────────────── T — araçlar ───────────────────────────
class _SahteIstemci:
    """atom/query araçlarının gördüğü SAPClient yüzü (FUGR/I yolu)."""

    def __init__(self, canli=KAYNAK, kanit_ok=True):
        self.cagri: list[str] = []
        self.canli = canli
        self.kanit_ok = kanit_ok
        dis = self

        class _Oturum:
            verify = False

            def get(self, url, **kw):
                dis.cagri.append("GET " + url.replace(_Adt.url, ""))
                return _Yanit(200, dis.canli)

        class _Adt:
            url = "http://sahte.invalid"
            session = _Oturum()

            def is_object_locked(self, url):
                dis.cagri.append("LOCKS " + url)
                return {"locked": False}
        self.adt_client = _Adt()

    def fugr_include_grubunu_dogrula(self, name, group):
        self.cagri.append(f"KANIT {name}/{group}")
        return {"ok": self.kanit_ok, "sebep": "sahte", "group": group,
                "object_url": OT.get_fugr_include_url(group, name)}

    def push_fugr_include(self, include_name, group, transport=None, source_file=None):
        self.cagri.append(f"PUSH {include_name}/{group}")
        if not self.kanit_ok:
            return {"success": False, "error": "kanıt yok", "error_type": "SAPValidationError",
                    "source_uploaded": False, "activated": False}
        self.canli = Path(source_file).read_text(encoding="utf-8")
        return {"success": True, "source_uploaded": True, "activated": True, "readback_ok": True}

    def activate_object(self, name, object_type="class", group=None):
        self.cagri.append(f"ACT {name}/{object_type}/{group}")
        return True

    def push_object(self, **kw):
        self.cagri.append("PUSH_OBJECT")
        return {"success": True}


class T_Araclar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="axet_fugrt_"))
        cls._eski_env = {k: os.environ.get(k) for k in ("AXET_SAP_PROJECT_DIR", "ADT_SAP_TIER")}
        os.environ.pop("ADT_SAP_TIER", None)
        from sapadt.tools import atom, query
        from sapadt import pull_state
        cls.atom, cls.query, cls.ps = atom, query, pull_state
        cls._eski = (atom._get_client, query._get_client)
        cls._n = 0

    @classmethod
    def tearDownClass(cls):
        cls.atom._get_client, cls.query._get_client = cls._eski
        for k, v in cls._eski_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(cls.root, ignore_errors=True)

    def setUp(self):
        type(self)._n += 1
        self.p = H.make_project(self.root, f"p{self._n}")
        os.environ["AXET_SAP_PROJECT_DIR"] = str(self.p)
        self.atom._LAST_PUSHED.clear()

    def ist(self, **kw):
        s = _SahteIstemci(**kw)
        self.atom._get_client = lambda: s
        self.query._get_client = lambda: s
        return s

    def test_T1_group_sozlesmesi_aga_gitmez(self):
        s = self.ist()
        r1 = self.atom.adt_push_source(INCL, "fugr_include", KAYNAK, transport="DEVK900001")
        r2 = self.atom.adt_push_source("ZAXET_P", "program", KAYNAK, group=GRUP)
        r3 = self.atom.adt_activate(INCL, "fugr/i")
        r4 = self.atom.adt_get(INCL, "fugr-include")
        r5 = self.query.adt_lock_check(INCL, "fugr_include")
        r6 = self.query.adt_lock_check("ZCL_X", "class", group=GRUP)
        kodlar = [r.get("error") for r in (r1, r2, r3, r4, r5, r6)]
        bek = ["group_required", "group_not_applicable", "group_required", "group_required", "group_required",
               "group_not_applicable"]
        ok = kodlar == bek and s.cagri == []
        H.kaydet("FUGR T1 group sözleşmesi", f"{bek} · çağrı=[]", f"{kodlar} · {s.cagri}", ok)
        self.assertTrue(ok)

    def test_T2_standart_grup_ve_onek_reddi(self):
        s = self.ist()
        r1 = self.atom.adt_push_source("LSAPXFGF01", "fugr_include", KAYNAK, transport="DEVK900001", group="SAPXFG")
        r2 = self.atom.adt_activate("LZBASKAF01", "fugr_include", group=GRUP)
        ok = r1.get("code") == "ADR_0005_A" and r2.get("code") == "ADR_0005_A" and s.cagri == []
        H.kaydet("FUGR T2 standart grup / önek reddi", "ADR_0005_A ×2 · çağrı=[]",
                 f"{r1.get('code')} {r2.get('code')} · {s.cagri}", ok)
        self.assertTrue(ok)

    def test_T3_get_push_akisi(self):
        s = self.ist()
        g = self.atom.adt_get(INCL, "fugr_include", group=GRUP)
        anahtar = self.ps.anahtar(INCL, "fugr/i")
        ok1 = (g.get("ok") is True and g.get("pull_state") == "kaydedildi"
               and s.cagri == ["GET /sap/bc/adt/functions/groups/zaxfg/includes/lzaxfgf01/source/main"]
               and anahtar == "fugr_include:LZAXFGF01")
        H.kaydet("FUGR T3a adt_get(group) + pull anahtarı", "GET grup URL · fugr_include:LZAXFGF01",
                 f"{g.get('pull_state')} · {s.cagri} · {anahtar}", ok1)
        self.assertTrue(ok1, g)
        s.cagri.clear()
        yeni = KAYNAK.replace("eski", "yeni")
        r = self.atom.adt_push_source(INCL, "fugr-include", yeni, transport="DEVK900001", group=GRUP.lower())
        ok2 = (r.get("ok") is True and r.get("group") == GRUP and "PUSH LZAXFGF01/zaxfg" in s.cagri
               and "PUSH_OBJECT" not in s.cagri and r.get("pull_state") == "guncellendi")
        H.kaydet("FUGR T3b push → push_fugr_include", "ok · group · pull güncel",
                 f"{r.get('ok')} {r.get('error')} {r.get('group')} · {s.cagri} · {r.get('pull_state')}", ok2)
        self.assertTrue(ok2, r)

    def test_T4_push_transport_zorunlu(self):
        s = self.ist()
        r = self.atom.adt_push_source(INCL, "fugr_include", KAYNAK, group=GRUP)
        ok = r.get("code") == "ADR_0005_C" and s.cagri == []
        H.kaydet("FUGR T4 transportsuz push", "ADR_0005_C · çağrı=[]", f"{r.get('code')} · {s.cagri}", ok)
        self.assertTrue(ok)

    def test_T5_push_kanit_tutmazsa_kod(self):
        s = self.ist(kanit_ok=False)
        self.atom.adt_get(INCL, "fugr_include", group=GRUP)
        r = self.atom.adt_push_source(INCL, "fugr_include", KAYNAK + "*\n", transport="DEVK900001", group=GRUP)
        ok = r.get("ok") is False and r.get("error") == "fugr_group_unverified" and r.get("pull_state", "").startswith("degismedi")
        H.kaydet("FUGR T5 push kanıt yok", "fugr_group_unverified · kayıt değişmedi",
                 f"{r.get('error')} · {r.get('pull_state')}", ok)
        self.assertTrue(ok, r)

    def test_T6_aktivasyon_kapilari(self):
        s = self.ist(kanit_ok=False)
        r1 = self.atom.adt_activate(INCL, "fugr_include", group=GRUP)
        r2 = self.atom.adt_activate(INCL, "fugr_include", group=GRUP,
                                    also=[{"name": "ZCL_X", "object_type": "class"}])
        self.atom._LAST_PUSHED[(INCL, "fugr_include")] = {"grup": "ZBASKA"}
        r3 = self.atom.adt_activate(INCL, "fugr_include", group=GRUP)
        act = [c for c in s.cagri if c.startswith("ACT")]
        ok = (r1.get("error") == "fugr_group_unverified" and r2.get("error") == "fugr_include_also_unsupported"
              and r3.get("error") == "fugr_group_mismatch" and act == [])
        H.kaydet("FUGR T6 aktivasyon kapıları", "unverified · also_unsupported · mismatch · ACT yok",
                 f"{r1.get('error')} {r2.get('error')} {r3.get('error')} · {act}", ok)
        self.assertTrue(ok)

    def test_T7_aktivasyon_kanitli_grupla(self):
        s = self.ist()
        r = self.atom.adt_activate(INCL, "fugr_include", group=GRUP)
        act = [c for c in s.cagri if c.startswith("ACT")]
        ok = act == [f"ACT {INCL}/fugr_include/{GRUP}"] and s.cagri.index(f"KANIT {INCL}/{GRUP}") < s.cagri.index(act[0])
        H.kaydet("FUGR T7 kanıt → aktivasyon (grupla)", "KANIT<ACT", f"{s.cagri} · ok={r.get('ok')}", ok)
        self.assertTrue(ok)

    def test_T8_lock_check(self):
        s = self.ist(kanit_ok=False)
        r1 = self.query.adt_lock_check(INCL, "fugr_include", group=GRUP)
        s.kanit_ok = True
        r2 = self.query.adt_lock_check(INCL, "fugr_include", group=GRUP)
        u = "/sap/bc/adt/functions/groups/zaxfg/includes/lzaxfgf01"
        ok = (r1.get("error") == "fugr_group_unverified" and r1.get("locked") is None
              and r2.get("ok") is True and r2.get("locked") is False and s.cagri.count("LOCKS " + u) == 1)
        H.kaydet("FUGR T8 lock_check", "kanıtsız: sonda yok · kanıtlı: FUGR/I URL", f"{r1.get('error')} · {s.cagri}", ok)
        self.assertTrue(ok)


# ─────────────────────────── G — yazma kapısı ───────────────────────────
class G_Kapi(unittest.TestCase):
    def test_G1_check_names_fugr_include(self):
        from sapadt import gate
        r_yok = gate.check_names("adt_push_source", INCL, "fugr_include")
        r_std = gate.check_names("adt_push_source", "LSAPXFGF01", "fugr/i", grup="SAPXFG")
        r_onek = gate.check_names("adt_activate", "LZBASKAF01", "fugr-include", grup=GRUP)
        r_ok = gate.check_names("adt_push_source", INCL, "fugr_include", grup=GRUP)
        r_klasik = gate.check_names("adt_push_source", INCL, "program")   # include adı L… → klasik kural RED
        ok = (r_yok and r_yok[0] == "ADR_0005_A" and r_std and r_std[0] == "ADR_0005_A"
              and r_onek and r_onek[0] == "ADR_0005_A" and r_ok is None and r_klasik and r_klasik[0] == "ADR_0005_A")
        H.kaydet("FUGR G1 kapı ad kuralı", "grupsuz/standart/önek RED · doğru None · klasik tip RED",
                 f"{r_yok and r_yok[0]} {r_std and r_std[0]} {r_onek and r_onek[0]} {r_ok} {r_klasik and r_klasik[0]}", ok)
        self.assertTrue(ok)

    def test_G2_yazma_sinifi(self):
        from sapadt import gate
        ok = (gate.tool_class("adt_push_source") == "write" and gate.tool_class("adt_activate") == "write"
              and gate.tool_class("adt_lock_check") == "read")
        H.kaydet("FUGR G2 sınıf", "push/activate write · lock_check read", str(ok), ok)
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
