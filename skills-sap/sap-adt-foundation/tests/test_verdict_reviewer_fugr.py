# -*- coding: utf-8 -*-
"""Reviewer haritasının FUGR/FM ekseni — `None` ölçülmüş bir karardır (pin).

  R1  `fugr`/`functiongroup` anahtarı VAR ve değeri None (kayıtlı boşluk; eksik anahtar = sessiz atlama).
  R2  `func`/`function` anahtarı VAR ve değeri None: FM gövdesi push'unda gömülü inceleme yok, inceleme elle koşulur.
  R3  `SAPClient.push_object(.., 'func'|'function')` ValueError atar ve adt_client'e HİÇ dokunmaz
      (generic FM ucu yok; MCP `func` yolu grubu ayrıca çözer).
  R4  KONTROL GRUBU: aynı sahte istemciyle `fugr` push'u istemciye ULAŞIR (R3 boş geçmesin).
  R5  `fugr` kaynak ucu = FG ANA INCLUDE (`/functions/groups/<fg>/source/main`), `fmodules` DEĞİL ⇒
      `fugr` anahtarını doldurmak FM gövdesini kapsamazdı.
Davranış değiştirilmedi, yalnız pinlendi; karşıtlık mutasyondan gelir.
"""
from __future__ import annotations

import io
import sys
import tempfile
import unittest
from pathlib import Path

import _helpers as H

sys.dont_write_bytecode = True
LIB = H.SCRIPTS / "sapadt" / "lib"
for _p in (H.SCRIPTS, LIB):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import sapadt  # noqa: E402,F401
from sapadt import _reviewer as RV  # noqa: E402
import object_types as OT  # noqa: E402
import sap_client as SC  # noqa: E402


class _Dur(Exception):
    pass


class _SahteAdt:
    """adt_client'e yapılan HER erişimi kaydeder ve ilk çağrıda durdurur (SAP isteği yok)."""

    def __init__(self):
        self.cagri: list = []

    def __getattr__(self, ad):
        def _f(*a, **kw):
            self.cagri.append(ad)
            raise _Dur(ad)
        return _f


class ReviewerFugrEkseni(unittest.TestCase):
    def kaydet(self, ad, beklenen, gercek, ok):
        H.kaydet(f"REVIEWER-FUGR {ad}", beklenen, str(gercek)[:160], ok)
        self.assertTrue(ok, f"{ad}: {gercek}")

    def _push(self, ad, tip):
        stub = _SahteAdt()
        c = object.__new__(SC.SAPClient)
        c.adt_client = stub
        c.debug_enabled = False
        with tempfile.TemporaryDirectory(prefix="axet_rv_fugr_") as d:
            kaynak = Path(d) / f"{ad}.abap"
            kaynak.write_text("FUNCTION zbc000_fm_demo.\nENDFUNCTION.\n", encoding="utf-8")
            yedek, sys.stdout = sys.stdout, io.StringIO()
            try:
                c.push_object(object_name=ad, object_type=tip, transport=None, source_file=str(kaynak))
                hata = None
            except _Dur:
                hata = "_Dur"
            except Exception as exc:  # noqa: BLE001
                hata = type(exc).__name__
            finally:
                sys.stdout = yedek
        return hata, stub.cagri

    def test_R1_fugr_anahtari_var_deger_none(self):
        harita = RV.OBJECT_TYPE_TO_TASK
        ok = all(k in harita and harita[k] is None for k in ("fugr", "functiongroup"))
        self.kaydet("R1 fugr/functiongroup", "anahtar var, None", {k: harita.get(k, "<YOK>") for k in ("fugr", "functiongroup")}, ok)

    def test_R2_func_anahtari_var_deger_none(self):
        harita = RV.OBJECT_TYPE_TO_TASK
        ok = all(k in harita and harita[k] is None for k in ("func", "function"))
        self.kaydet("R2 func/function", "anahtar var, None", {k: harita.get(k, "<YOK>") for k in ("func", "function")}, ok)

    def test_R3_generic_func_push_istemciye_dokunmaz(self):
        sonuc = {t: self._push("ZBC000_FM_DEMO", t) for t in ("func", "function")}
        ok = all(h == "ValueError" and not c for h, c in sonuc.values())
        self.kaydet("R3 push_object func", "ValueError + 0 çağrı", sonuc, ok)

    def test_R4_kontrol_fugr_push_istemciye_ulasir(self):
        h, c = self._push("ZBC000_FG_DEMO", "fugr")
        self.kaydet("R4 KONTROL fugr push", "_Dur + çağrı var", (h, c), h == "_Dur" and bool(c))

    def test_R5_fugr_kaynak_ucu_ana_include(self):
        u = OT.get_source_url("ZBC000_FG_DEMO", "fugr")
        ok = u == "/sap/bc/adt/functions/groups/zbc000_fg_demo/source/main" and "fmodules" not in u
        self.kaydet("R5 fugr kaynak ucu", "FG ana include", u, ok)


if __name__ == "__main__":
    unittest.main()
