# -*- coding: utf-8 -*-
"""Z195 ③ (2026-10-19) — kilit BIRAKILAMADI dürüst bildirimi + CORRNR uyuşmazlığında istek sahibi metni.

Ölçülen sınıf (düzeltme öncesi, aXet):
  · `_release_lock_after_failure` `unlock_object` dönüşünü okumuyordu → `False`'ta da "Lock released" basıyordu.
  · FOREIGN (IS_LINK_UP=X) ve IS_LINK_UP=boş CORRNR uyuşmazlığı metinleri istek SAHİBİNİ söylemiyordu; boş dal
    "The object is in your own transport" diyordu (IS_LINK_UP=boş yalnız "altında GÖREVİN var" demektir).
  · Beş metin SM12'de kilidi SİLMEYİ/BIRAKMAYI öneriyordu (Kesin Yasak C: ajan kilit silmez, yalnız "kontrol et").
  · `adt_push_source` `lock_released=False`'u yalnız nested `result` içinde taşıyordu.
Kaynak çekirdekle aynı tasarım (tek kaynak uyarı `kilit_birakilamadi_uyarisi`, `_istek_sahibi_metni` istisna atmaz).
aXet'in 2026-09-14 push davranışı (aktivasyon öncesi unlock False → handle tutulur, finally 2 kez dener)
KORUNDU — `test_kilit_politikasi` S4/S6. Süreç içi, SAHTE oturum (ağ yok); aXet'te canlı ölçülmedi.
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
LIB = H.SCRIPTS / "sapadt" / "lib"
for _p in (H.SCRIPTS, LIB):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import sapadt  # noqa: E402,F401
import sap_adt_lib as L  # noqa: E402
import sap_client as SC  # noqa: E402
from test_kilit_politikasi import _LibAdt, _PushAdt, _Y, _sessiz_uyku, KAYNAK as KP_KAYNAK  # noqa: E402
from test_verdict_push_precheck import (_SahteAdt, _SozSunucu, GOVDE_TRUE, AD as PUSH_AD,  # noqa: E402
                                        KAYNAK as PUSH_KAYNAK)

OBJ_URL = "/sap/bc/adt/oo/classes/zcl_ca000_kilit"
ISTENEN = "NPLK900001"   # TRKORR biçimi 10 karakter (E070 sorgusu biçimsizi reddeder)
ATANAN = "NPLK900333"
SAHIP = "BASKA_GELISTIRICI"
SILME_ONERISI = ("release enqueue", "delete the enqueue", "Release lock in SM12", "use SM12 to", "clean up",
                 "unlock it manually")


def _e070(sahip=SAHIP):
    ns = "http://www.sap.com/adt/dataPreview"
    return (f'<dataPreview:tableData xmlns:dataPreview="{ns}"><dataPreview:columns>'
            f'<dataPreview:metadata dataPreview:name="AS4USER"/><dataPreview:dataSet>'
            f'<dataPreview:data>{sahip}</dataPreview:data></dataPreview:dataSet></dataPreview:columns>'
            f'</dataPreview:tableData>')


def _yonlendir(is_link_up, e070=None, unlock_kod=200):
    def y(c):
        aksiyon = c["params"].get("_action")
        if aksiyon == "LOCK":
            if "/sap/bc/adt/locks" in c["url"] or "objectlock" in c["url"]:
                return _Y(404, "")
            return _Y(200, f"<DATA><LOCK_HANDLE>HX</LOCK_HANDLE><CORRNR>{ATANAN}</CORRNR>"
                           f"<IS_LINK_UP>{is_link_up}</IS_LINK_UP></DATA>")
        if aksiyon == "UNLOCK":
            return _Y(unlock_kod, "")
        if "datapreview/freestyle" in c["url"]:
            return e070 if isinstance(e070, Exception) else (e070 or _Y(200, _e070()))
        return _Y(599, "beklenmeyen")
    return y


class _Kayit(unittest.TestCase):
    def kaydet(self, ad, beklenen, gercek, ok):
        H.kaydet(f"Z195③ {ad}", beklenen, str(gercek)[:160], ok)
        self.assertTrue(ok, f"{ad}: {gercek}")


class TekKaynakUyari(_Kayit):
    def test_U1_metin_kontrol_et_der_silme_onermez(self):
        m = L.kilit_birakilamadi_uyarisi("ZCL_X")
        ok = (L.KILIT_BIRAKILAMADI_IMZA in m and "ZCL_X" in m and "KONTROL ET" in m and "lock_released=False" in m
              and not any(s.lower() in m.lower() for s in SILME_ONERISI))
        self.kaydet("U1 tek kaynak uyarı", "imza · ad · KONTROL ET · silme önerisi yok", m[:120], ok)

    def test_U2_release_after_failure_donusu_okur(self):
        sonuc = {}
        for ad, kod in (("False", 500), ("True", 200)):
            adt = _LibAdt(lambda c, k=kod: _Y(k, ""))
            tampon = io.StringIO()
            with contextlib.redirect_stdout(tampon):
                adt._release_lock_after_failure(OBJ_URL, "H1", "[OK] Lock released (test)")
            sonuc[ad] = tampon.getvalue()
        ok = (L.KILIT_BIRAKILAMADI_IMZA in sonuc["False"] and "[OK] Lock released" not in sonuc["False"]
              and "[OK] Lock released" in sonuc["True"] and L.KILIT_BIRAKILAMADI_IMZA not in sonuc["True"])
        self.kaydet("U2 _release_lock_after_failure: unlock False → uyarı, 'released' YALANI yok · True → ok mesajı",
                    "False: imza · True: ok", {k: v.strip()[:70] for k, v in sonuc.items()}, ok)

    def test_U3_safe_unlock_durust(self):
        adt = _LibAdt(lambda c: _Y(500, ""))
        with contextlib.redirect_stdout(io.StringIO()):
            r = adt.safe_unlock(OBJ_URL, "H1")
        adt2 = _LibAdt(lambda c: _Y(200, ""))
        r2 = adt2.safe_unlock(OBJ_URL, "H1")
        self.kaydet("U4 safe_unlock: tüm stratejiler düşerse False (eskisi True) · 200 → True", "False · True",
                    (r, r2), r is False and r2 is True)


class IstekSahibi(_Kayit):
    def _kilit(self, is_link_up, **kw):
        adt = _LibAdt(_yonlendir(is_link_up, **kw))
        tampon = io.StringIO()
        with contextlib.redirect_stdout(tampon), self.assertRaises(L.SAPLockError) as ctx:
            adt.lock_object(OBJ_URL, transport=ISTENEN)
        return adt, str(ctx.exception), ctx.exception

    def _sira(self, adt):
        unlock = [i for i, c in enumerate(adt.session.cagri) if c["params"].get("_action") == "UNLOCK"]
        sorgu = [i for i, c in enumerate(adt.session.cagri) if "datapreview/freestyle" in c["url"]]
        return unlock, sorgu

    def test_S1_foreign_sahibi_adlandirir(self):
        adt, m, exc = self._kilit("X")
        unlock, sorgu = self._sira(adt)
        ok = (f"Istek {ATANAN} (sahibi {SAHIP})" in m and "KONTROL ET" in m
              and not any(s.lower() in m.lower() for s in SILME_ONERISI)
              and exc.status_code == 409 and unlock and sorgu and unlock[0] < sorgu[0]
              and adt._last_lock_istek_sahibi == SAHIP)
        self.kaydet("S1 FOREIGN (IS_LINK_UP=X) → sahibi adıyla · KONTROL ET · kilit sorgudan ÖNCE bırakıldı",
                    "sahibi · 409 · unlock<sorgu", (m.splitlines()[1] if "\n" in m else m[:80], unlock, sorgu), ok)

    def test_S2_bos_link_up_senin_istegin_demez(self):
        adt, m, exc = self._kilit("")
        ok = (f"(sahibi {SAHIP})" in m and "senin istegin' demek DEGILDIR" in m
              and "your own transport" not in m and "AS4USER FROM E070" in m
              and not any(s.lower() in m.lower() for s in SILME_ONERISI) and exc.status_code == 409)
        self.kaydet("S2 IS_LINK_UP boş → 'senin isteğin' DEMEZ, sahibi adıyla", "sahibi · 'your own' yok",
                    m.splitlines()[2] if m.count("\n") > 2 else m[:80], ok)

    def test_S3_sahip_okunamazsa_dal_aynen(self):
        vakalar = (("http_500", _Y(500, "iç hata")), ("istisna", ConnectionError("ag yok")),
                   ("bozuk_xml", _Y(200, "<<< x")), ("as4user_yok", _Y(200, _e070("").replace("AS4USER", "X"))))
        gercek = {}
        for ad, yanit in vakalar:
            adt, m, exc = self._kilit("X", e070=yanit)
            gercek[ad] = ("sahip okunamadı" in m, exc.status_code, adt._last_lock_istek_sahibi)
        ok = all(v == (True, 409, None) for v in gercek.values())
        self.kaydet("S3 E070 okunamaz (500 · istisna · bozuk · alan yok) → 'sahip okunamadı', aynı istisna/kod",
                    "hepsi (True, 409, None)", gercek, ok)

    def test_S6_onceki_objenin_sahibi_tasinmaz(self):
        adt, _m, _e = self._kilit("X")
        once = adt._last_lock_istek_sahibi
        adt.session.yonlendir = lambda c: (_Y(404, "") if "/sap/bc/adt/locks" in c["url"] or "objectlock" in c["url"]
                                           else _Y(200, f"<DATA><LOCK_HANDLE>HY</LOCK_HANDLE><CORRNR>{ISTENEN}</CORRNR>"
                                                        f"<IS_LINK_UP></IS_LINK_UP></DATA>"))
        with contextlib.redirect_stdout(io.StringIO()):
            h = adt.lock_object(OBJ_URL + "_ikinci", transport=ISTENEN)
        self.kaydet("S6 önceki objenin istek sahibi sonraki kilide TAŞINMAZ", f"önce {SAHIP} · sonra None",
                    (once, h, adt._last_lock_istek_sahibi), once == SAHIP and h == "HY"
                    and adt._last_lock_istek_sahibi is None)

    def test_S4_bicimsiz_istek_sorgu_atmaz(self):
        adt = _LibAdt(lambda c: _Y(599, ""))
        m = adt._istek_sahibi_metni("X'; DROP")
        ok = m.startswith("sahip okunamadı") and not adt.session.cagri
        self.kaydet("S4 biçimsiz istek no → sorgu YOK", "0 istek", (m, len(adt.session.cagri)), ok)

    def test_S5_bug11_uyarisi_sahibi_adlandirir(self):
        T_SAP = ATANAN

        def hedef_y(c):
            aksiyon = c["params"].get("_action")
            if aksiyon == "LOCK":
                if "/sap/bc/adt/locks" in c["url"] or "objectlock" in c["url"]:
                    return _Y(404, "")
                h = "HB" if c["params"].get("corrNr") == T_SAP else "HX"
                return _Y(200, f"<DATA><LOCK_HANDLE>{h}</LOCK_HANDLE><CORRNR>{T_SAP}</CORRNR>"
                               f"<IS_LINK_UP></IS_LINK_UP></DATA>")
            if "datapreview/freestyle" in c["url"]:
                return _Y(200, _e070())
            return _Y(200, "")
        from test_kilit_politikasi import _GercekKilitAdt
        root = Path(tempfile.mkdtemp(prefix="axet_kilit_b11_"))
        try:
            dosya = root / "ZCA000_KILIT_PROG.prog.abap"
            dosya.write_text(KP_KAYNAK, encoding="utf-8")
            adt = _GercekKilitAdt(hedef_y)
            ist = object.__new__(SC.SAPClient)
            ist.adt_client = adt
            ist.debug_enabled = False
            ist.local_base = root
            ist._find_existing_transport = lambda name, otype, transport: transport
            tampon = io.StringIO()
            with _sessiz_uyku(), contextlib.redirect_stdout(tampon):
                ist.push_object("ZCA000_KILIT_PROG", object_type="prog", transport=ISTENEN, source_file=str(dosya))
            log = tampon.getvalue()
        finally:
            shutil.rmtree(root, ignore_errors=True)
        ok = (f"sahibi {SAHIP}" in log and "aynı kullanıcı, CORRNR" not in log
              and f"BAŞKA kullanıcıya ait ({SAHIP})" in log and adt.put_kayit == [("HB", T_SAP)])
        self.kaydet("S5 Bug-11 kurtarması sahibi adlandırır + başka kullanıcıysa DİKKAT; PUT davranışı aynı",
                    "sahibi · DİKKAT · PUT HB", (f"sahibi {SAHIP}" in log, "DİKKAT" in log, adt.put_kayit), ok)


class PushYuzeyi(_Kayit):
    def test_P1_push_object_tek_kaynak_uyari(self):
        root = Path(tempfile.mkdtemp(prefix="axet_kilit_p1_"))
        try:
            dosya = root / "ZCA000_KILIT_PROG.prog.abap"
            dosya.write_text(KP_KAYNAK, encoding="utf-8")
            adt = _PushAdt(unlock_donus=False)
            ist = object.__new__(SC.SAPClient)
            ist.adt_client = adt
            ist.debug_enabled = False
            ist.local_base = root
            ist._find_existing_transport = lambda name, otype, transport: transport
            tampon = io.StringIO()
            with _sessiz_uyku(), contextlib.redirect_stdout(tampon):
                r = ist.push_object("ZCA000_KILIT_PROG", object_type="prog", transport=ISTENEN,
                                    source_file=str(dosya))
            log = tampon.getvalue()
        finally:
            shutil.rmtree(root, ignore_errors=True)
        ok = (r.get("lock_released") is False and L.KILIT_BIRAKILAMADI_IMZA in log
              and len(adt.adimlar("UNLOCK")) >= 2 and not any(s.lower() in log.lower() for s in SILME_ONERISI))
        self.kaydet("P1 push_object unlock False → lock_released False + tek kaynak uyarı (2-deneme korundu)",
                    "False · imza · UNLOCK ≥2", (r.get("lock_released"), L.KILIT_BIRAKILAMADI_IMZA in log,
                                                 len(adt.adimlar("UNLOCK"))), ok)


class _KilitDusenAdt(_SahteAdt):
    def unlock_object(self, url, lock):
        return False


class McpUstSeviye(_Kayit):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="axet_kilit_mcp_"))
        cls.dev = H.make_project(cls.root, "dev")
        cls._eski_env = {k: os.environ.get(k) for k in ("AXET_SAP_PROJECT_DIR", "ADT_SAP_TIER")}
        os.environ.pop("ADT_SAP_TIER", None)
        os.environ["AXET_SAP_PROJECT_DIR"] = str(cls.dev)
        from sapadt.tools import atom
        cls.atom = atom
        ps = atom._pull_state
        cls._eski = (atom._get_client, atom._adt_get_oku, ps.kayit_al, ps.kaydet, ps.sil)
        ozet = ps.ozet(PUSH_KAYNAK)
        atom._adt_get_oku = lambda name, object_type, *a, **k: {"ok": True, "exists": True, "source": PUSH_KAYNAK}
        ps.kayit_al = lambda name, object_type: ({"sha256": ozet, "pulled_at": "test"}, None)
        ps.kaydet = lambda *a, **k: None
        ps.sil = lambda *a, **k: None

    @classmethod
    def tearDownClass(cls):
        atom, ps = cls.atom, cls.atom._pull_state
        atom._get_client, atom._adt_get_oku, ps.kayit_al, ps.kaydet, ps.sil = cls._eski
        for k, v in cls._eski_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(cls.root, ignore_errors=True)

    def _mcp(self, sinif):
        ist = object.__new__(SC.SAPClient)
        ist.adt_client = sinif(_SozSunucu(200, GOVDE_TRUE))
        ist.debug_enabled = False
        ist.local_base = self.root
        ist._find_existing_transport = lambda name, otype, transport: transport
        self.atom._get_client = lambda: ist
        with _sessiz_uyku():
            return self.atom.adt_push_source(name=PUSH_AD, object_type="class", source=PUSH_KAYNAK,
                                             transport=ISTENEN, skip_reviewer=True)

    def test_M1_lock_released_ust_seviyede(self):
        r = self._mcp(_KilitDusenAdt)
        ok = (r.get("ok") is True and r.get("lock_released") is False
              and "KONTROL ET" in str(r.get("lock_notice") or "")
              and not any(s.lower() in str(r.get("lock_notice")).lower() for s in SILME_ONERISI))
        self.kaydet("M1 adt_push_source unlock False → ok DEĞİŞMEZ · üst seviye lock_released False + lock_notice",
                    "ok True · False · notice", (r.get("ok"), r.get("lock_released"), bool(r.get("lock_notice"))), ok)

    def test_M2_kontrol_kilit_birakildi_alan_yok(self):
        r = self._mcp(_SahteAdt)
        ok = r.get("ok") is True and "lock_released" not in r and "lock_notice" not in r
        self.kaydet("M2 KONTROL unlock True → üst seviyede alan YOK", "ok True · alan yok",
                    (r.get("ok"), r.get("lock_released", "YOK")), ok)


class StatikSm12(_Kayit):
    def test_T1_uretimde_sm12_silme_onerisi_yok(self):
        """Üretim .py'lerinde (testler hariç) SM12/kilit için silme-bırakma ÖNERİSİ kalmadı (Kesin Yasak C)."""
        kok = H.SCRIPTS / "sapadt"
        bulgu = []
        for p in kok.rglob("*.py"):
            if "__pycache__" in p.parts:
                continue
            for i, satir in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                if satir.lstrip().startswith("#"):   # eski metni anan yorumlar öneri değildir
                    continue
                if any(s.lower() in satir.lower() for s in SILME_ONERISI) and "SM12" in satir:
                    bulgu.append(f"{p.name}:{i}")
        self.kaydet("T1 üretimde 'SM12 → release/delete/clean up' önerisi", "0", bulgu, not bulgu)


if __name__ == "__main__":
    unittest.main(verbosity=2)
