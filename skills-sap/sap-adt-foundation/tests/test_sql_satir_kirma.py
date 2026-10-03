# -*- coding: utf-8 -*-
"""ADT freestyle 255 karakter SATIR sınırı — çevrimdışı kontrol grubu (Z165).

ÖLÇÜLMÜŞ (kaynak çekirdek ölçümü 2026-10-03, DEV, T000, kontrol gruplu): SAP
`/datapreview/freestyle` sorgu metnini satır satır okur, 255 karakterden uzun satırın
devamını KESER. Token ortasında kesilirse 400; geçerli bir sınırda kesilirse kırpılmış
sorgu SESSİZCE koşar (`ok:true`, yanlış veri). Eski "5'ten fazla OR → 400" teşhisi bu
sınırın yansımasıydı (252 kr tek satırda 13 OR → 200).

Vakalar:
  K  `sql_satirlarini_kir` saf fonksiyon (K1–K13; kaynak fixture ile aynı adlar)
  R  `run_query` entegrasyonu (sahte HTTP; SAP'ye gidilmez) + 400 gövdesinin kırpılmadan
     taşınması (255-vakasının gerçek gövdesi 563 bayt — `[:500]` XML'i bozuyordu)
  S  SINIF: `scripts/` altında freestyle'a POST eden HER fonksiyon kırmadan geçer
  D  çürüyen teşhis ("5'ten fazla OR → 400") araç açıklamasından ve belgeden kalktı
Kontrol satırları (silinmez): K1 K2 K8 — "her şeyi kır" diyen bir düzeltme de geçerdi.
KAPSAM — BAKMADIKLARI: gerçek SAP · çok baytlı karakterde sınırın bayt mı karakter mi
olduğu (ölçülmedi) · GET `freestyle/{tablo}` (`sqlQuery` URL parametresi; kaynakta da
değişmedi).
"""
from __future__ import annotations

import ast
import re
import sys
import unittest

import _helpers as H

sys.dont_write_bytecode = True
LIB = H.SCRIPTS / "sapadt" / "lib"
for _p in (H.SCRIPTS, LIB):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import sap_adt_lib as L  # noqa: E402
import sap_client as SC  # noqa: E402

SINIR = L.SQL_SATIR_SINIRI
kir = L.sql_satirlarini_kir


def uzun_sorgu() -> str:
    terms = " OR ".join(f"mandt = '{i:03d}'" for i in range(13))
    return f"SELECT mandt, mtext FROM t000 WHERE {terms} OR mtext <> 'ZZZZZZZZZZZZZZZZZZZZ'"


Q6 = "SELECT mandt FROM t000 WHERE mtext <> '" + "a b " * 70 + "'"


class SaflikTest(unittest.TestCase):
    """K — saf fonksiyon."""

    def test_K1_kisa_sorgu_aynen(self):
        kisa = "SELECT mandt FROM t000 WHERE mandt = '000'"
        self.assertEqual(kir(kisa), kisa)

    def test_K2_kisa_crlf_aynen(self):
        q = "SELECT mandt\r\nFROM t000\r\nWHERE mandt = '000'"
        self.assertEqual(kir(q), q)

    def test_K3_uzun_tek_satir_kirilir(self):
        q = uzun_sorgu()
        r = kir(q)
        satirlar = r.split("\n")
        self.assertGreater(len(q), SINIR)
        self.assertGreaterEqual(len(satirlar), 2)
        self.assertTrue(all(len(s) <= SINIR for s in satirlar), [len(s) for s in satirlar])
        self.assertEqual(r.split(), q.split())

    def test_K4_bosluklu_literal_bolunmez(self):
        lit = "'" + " ".join(["kelime"] * 20) + "'"
        q = "SELECT mandt FROM t000 WHERE " + "mandt <> '999' AND " * 6 + "mtext <> " + lit
        r = kir(q).splitlines()
        self.assertGreater(len(q), SINIR)
        self.assertTrue(any(lit in s for s in r))
        self.assertTrue(all(len(s) <= SINIR for s in r))

    def test_K5_kacis_backtick_yorum_bolunmez(self):
        lit_k = "'it''s " + "a b " * 30 + "end'"
        bt = "`" + "x y " * 30 + "`"
        kom = "\"yorum metni bosluklu " + "z " * 10
        q = ("SELECT mandt FROM t000 WHERE " + "mandt <> '998' AND " * 5 + "mtext <> " + lit_k
             + " AND mtext <> " + bt + " " + kom)
        r = kir(q).splitlines()
        self.assertGreater(len(q), SINIR)
        self.assertTrue(any(lit_k in s for s in r))
        self.assertTrue(any(bt in s for s in r))
        self.assertTrue(any(kom in s for s in r))
        self.assertTrue(all(len(s) <= SINIR for s in r))

    def test_K6_uzun_literal_kirilamaz(self):
        with self.assertRaises(L.SQLSatirKirilamadi) as cm:
            kir(Q6)
        self.assertIsInstance(cm.exception, L.SAPADTError)
        self.assertIn("literal", str(cm.exception))

    def test_K7_crlf_uzun_girdi_crlf_ekler(self):
        q = "SELECT mandt, mtext\r\nFROM t000\r\nWHERE " + uzun_sorgu().split("WHERE ", 1)[1]
        r = kir(q)
        self.assertNotEqual(r, q)
        self.assertEqual(r.replace("\r\n", "").count("\n"), 0)
        self.assertTrue(all(len(s) <= SINIR for s in r.split("\r\n")))

    def test_K8_tam_255_dokunulmaz(self):
        q = "SELECT mandt FROM t000 WHERE mtext <> '" + "x" * (SINIR - 40) + "'"
        q = q + " " * (SINIR - len(q))
        self.assertEqual(len(q), SINIR)
        self.assertEqual(kir(q), q)

    def test_K9_girinti_ilk_parcada_korunur(self):
        r = kir("    " + uzun_sorgu()).split("\n")
        self.assertTrue(r[0].startswith("    SELECT"))
        self.assertGreaterEqual(len(r), 2)
        self.assertTrue(all(len(s) <= SINIR for s in r))

    def test_K10_devam_satiri_yildizla_baslamaz(self):
        on = "SELECT mandt,"
        on = on + " " * (SINIR - len(on) - len("COUNT(")) + "COUNT("
        q = on + " * ) AS cnt FROM t000 GROUP BY mandt"
        r = kir(q).splitlines()
        self.assertEqual(len(on), SINIR)
        self.assertGreaterEqual(len(r), 2)
        self.assertFalse(any(s.startswith("*") for s in r), [s[:4] for s in r])
        self.assertTrue(any(s.startswith(" * )") for s in r[1:]))
        self.assertTrue(all(len(s) <= SINIR for s in r))
        self.assertEqual(kir(q).split(), q.split())

    def test_K11_uzun_yildiz_yorum_satiri_kirilamaz(self):
        q = "SELECT mandt FROM t000\n* " + "yorum " * 50 + "\nWHERE mandt = '000'"
        with self.assertRaises(L.SQLSatirKirilamadi) as cm:
            kir(q)
        self.assertIn("tam-satır yorumu", str(cm.exception))

    def test_K12_girintisi_atilan_ilk_atom_yildiz_onek_alir(self):
        q = " " * 250 + "*abcdefgh FROM t000 WHERE mandt = '000' OR mandt = '001'"
        r = kir(q).splitlines()
        self.assertGreater(len(q), SINIR)
        self.assertFalse(any(s.startswith("*") for s in r), [s[:4] for s in r])
        self.assertTrue(r[0].startswith(" *abcdefgh"))
        self.assertTrue(all(len(s) <= SINIR for s in r))

    def test_K13_tam_255_yildiz_atomu_onekle_256(self):
        a = "*" + "x" * (SINIR - 1)
        with self.assertRaises(L.SQLSatirKirilamadi) as cm:
            kir("SELECT mandt FROM t000 WHERE mandt = " + a)
        self.assertEqual(len(a), SINIR)
        self.assertIn("önekiyle 256", str(cm.exception))


class _Yanit:
    def __init__(self, kod, govde):
        self.status_code, self.text = kod, govde


def _istemci(kod=200, govde="<ok/>"):
    c = object.__new__(L.SAPADTClient)
    c.url = "https://sahte.invalid"
    c._get_headers = lambda *a, **k: {}
    c.gonderilen = []

    def _istek(method, url, **kw):
        c.gonderilen.append(kw.get("data"))
        return _Yanit(kod, govde)
    c._request_with_csrf_retry = _istek
    return c


SEBEP = '"O" is invalid here (due to grammar).'
GOVDE400 = ('<?xml version="1.0" encoding="utf-8"?><exc:exception xmlns:exc="http://www.sap.com/'
            'abapxml/types/communicationframework"><namespace id="http://www.sap.com/adt/wda/'
            'dataPreview"/><type id="ExceptionDataPreviewSQLGeneration"/><message lang="EN">'
            + SEBEP + '</message><localizedMessage lang="EN">' + SEBEP + '</localizedMessage>'
            '<properties><entry key="T100KEY-ID">ADT_DATAPREVIEW_MSG</entry><entry key="T100KEY-NO">'
            '004</entry><entry key="T100KEY-V1">' + SEBEP + '</entry></properties></exc:exception>')


class RunQueryTest(unittest.TestCase):
    """R — run_query entegrasyonu (sahte HTTP)."""

    def test_R1_gonderilen_govde_satirlari_255_alti(self):
        c = _istemci()
        c.run_query(uzun_sorgu(), row_number=5)
        self.assertEqual(len(c.gonderilen), 1)
        govde = (c.gonderilen[0] or b"").decode("utf-8")
        self.assertTrue(all(len(s) <= SINIR for s in govde.splitlines()),
                        [len(s) for s in govde.splitlines()])
        self.assertEqual(govde.split(), uzun_sorgu().split())

    def test_R2_kirilamayan_sorgu_istek_gitmez(self):
        c = _istemci()
        with self.assertRaises(L.SQLSatirKirilamadi):
            c.run_query(Q6, row_number=5)
        self.assertEqual(c.gonderilen, [])

    def test_R3_400_govdesi_kirpilmadan_tasinir(self):
        self.assertGreater(len(GOVDE400), 500)
        c = _istemci(400, GOVDE400)
        with self.assertRaises(L.SAPADTError) as cm:
            c.run_query("SELECT mandt FROM t000", row_number=5)
        h = SC.sap_hata_govdesi(cm.exception) or {}
        self.assertEqual(h.get("message"), SEBEP)
        self.assertLessEqual(len(h.get("body_excerpt") or ""), SC.SAP_HATA_GOVDE_SINIRI)


def _freestyle_post_fonksiyonlari(kaynak: str):
    """(fonksiyon_adi, kirma_cagiriyor_mu) — yalnız POST eden + URL'i KOD olarak taşıyan."""
    agac = ast.parse(kaynak)
    sonuc = []
    for fn in ast.walk(agac):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        doc = (fn.body[0].value if fn.body and isinstance(fn.body[0], ast.Expr)
               and isinstance(getattr(fn.body[0], "value", None), ast.Constant) else None)
        url_var = post_var = kirma = False
        for d in ast.walk(fn):
            if isinstance(d, ast.Constant) and isinstance(d.value, str) and d is not doc:
                if ("/datapreview/freestyle" in d.value
                        and "{" not in d.value.split("freestyle", 1)[1][:2]):
                    url_var = True
                if d.value == "post":
                    post_var = True
            if isinstance(d, ast.Call):
                ad = (d.func.attr if isinstance(d.func, ast.Attribute)
                      else d.func.id if isinstance(d.func, ast.Name) else "")
                if ad == "post":
                    post_var = True
                if ad == "sql_satirlarini_kir":
                    kirma = True
        if url_var and post_var:
            sonuc.append((fn.name, kirma))
    return sonuc


class SinifTest(unittest.TestCase):
    """S — freestyle'a POST eden HER fonksiyon kırmadan geçer (yeni çağrı noktası da)."""

    def test_S1_tum_freestyle_post_fonksiyonlari_kirili(self):
        bulunan = []
        for p in sorted(H.SCRIPTS.rglob("*.py")):
            if "__pycache__" in p.parts:
                continue
            for ad, ok in _freestyle_post_fonksiyonlari(p.read_text(encoding="utf-8",
                                                                     errors="replace")):
                bulunan.append((p.relative_to(H.SCRIPTS).as_posix(), ad, ok))
        eksik = [f"{r}::{a}" for r, a, ok in bulunan if not ok]
        # Taban (2026-10-03): sap_adt_lib.py'de 3 POST noktası. Sayı düşerse tarayıcı körleşmiş
        # olabilir — sessizce "0 eksik" demesin.
        self.assertGreaterEqual(len(bulunan), 3, bulunan)
        self.assertEqual(eksik, [], bulunan)


class BelgeTest(unittest.TestCase):
    """D — çürüyen "5'ten fazla OR → 400" teşhisi ajana öğretilmiyor."""

    def test_D1_curuyen_teshis_kalkti(self):
        kaynaklar = [
            H.SCRIPTS / "sapadt" / "tools" / "query.py",
            H.FOUNDATION / "references" / "foundation-query.md",
        ]
        for p in kaynaklar:
            metin = p.read_text(encoding="utf-8")
            m = re.search(r"5'ten fazla `?OR`?\*{0,2}\s*(→|->)\s*400", metin)
            self.assertIsNone(m, "%s: %r" % (p.name, m.group(0) if m else ""))
            self.assertNotIn("5'erli parçalara böl", metin, p.name)
            self.assertIn("255", metin, p.name)


if __name__ == "__main__":
    unittest.main()
