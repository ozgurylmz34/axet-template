# -*- coding: utf-8 -*-
"""K10 — sarmalayıcı zaman aşımı: ölç + uzat + BLOCKER (kullanıcı kararı 2026-09-15).

Kapsam (üç madde, kullanıcının verdiği SIRAYLA):
  ① ÖLÇÜLDÜ  → `maintenance/IS-LISTESI.md` K10 satırı + bu turun rapor tablosu (bu dosya ölçümü
                TEKRARLAMAZ; ölçümün KARARA dönüşmüş hâlini — bütçe sayılarını — çivirler).
  ② BÜTÇE YAPILANDIRILABİLİR → `utils/butce.py` TEK KAYNAK: `AXET_REVIEWER_BUTCE_SN` bütçeyi hem
                YÜKSELTİR hem DÜŞÜRÜR (eski `AXET_DTEL_GATE_BUTCE_SN` yalnız düşürebiliyordu →
                D12'nin "yavaş sistemde yanlış BLOCKER" riski yapılandırmayla karşılanamıyordu).
  ③ ZAMAN AŞIMI = BLOCKER → yalnız DTEL gate'li 4 zincirde değil, CANLI (SAP'ye bağlanan) BLOCKER
                validator taşıyan HER zincirde. Küme KODDAN türer (elle liste bayatlar).

Dayanak: "ölçülemedi ≠ temiz". Koşmayan kontrolün sonucu TEMİZ değil NOT MEASURED'dır.
Ağ: yalnız bu testin 127.0.0.1'de açtığı sahte ADT sunucusu (gerçek SAP yok).
"""
from __future__ import annotations

import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

import _helpers as H

sys.dont_write_bytecode = True
LIB = H.SCRIPTS / "sapadt" / "lib"
for _p in (H.SCRIPTS, LIB):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

VALIDATORS = LIB / "validators"
RUN_REVIEW = VALIDATORS / "run_review.py"


def _rr():
    import importlib.util
    spec = importlib.util.spec_from_file_location("_rr_k10", str(RUN_REVIEW))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── sahte ADT sunucusu: her GET `GECIKME` sn bekler (yavaş sistem benzetimi) ──────────────────────
class _Isleyici(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        self.server.kayit.append(self.path)
        time.sleep(self.server.gecikme)
        veri = ('<blue:blueSource xmlns:blue="http://www.sap.com/wbobj/blue" '
                'xmlns:adtcore="http://www.sap.com/adt/core" adtcore:version="active"/>').encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/xml")
        self.send_header("Content-Length", str(len(veri)))
        self.end_headers()
        self.wfile.write(veri)

    def log_message(self, *_a):
        pass


class _Taban(unittest.TestCase):
    ETIKET = "K10"

    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="axet_k10_"))
        izlenen = [k for k in os.environ if k.upper().startswith(("ADT_", "AXET_"))] + [
            "AXET_SAP_PROJECT_DIR", "NO_PROXY", "no_proxy"]
        cls._eski_env = {k: os.environ.get(k) for k in set(izlenen)}
        for k in [k for k in os.environ if k.upper().startswith("ADT_")]:
            os.environ.pop(k, None)
        os.environ["NO_PROXY"] = os.environ["no_proxy"] = "127.0.0.1,localhost"
        cls.sunucu = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Isleyici)
        cls.sunucu.kayit = []
        cls.sunucu.gecikme = 0.0
        cls.sunucu.handle_error = lambda *_a, **_k: None
        cls.port = cls.sunucu.server_address[1]
        threading.Thread(target=cls.sunucu.serve_forever, daemon=True).start()
        cls._sayac = 0
        from sapadt import _reviewer
        cls.rv = _reviewer

    @classmethod
    def tearDownClass(cls):
        cls.sunucu.shutdown()
        cls.sunucu.server_close()
        for k, v in cls._eski_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(cls.root, ignore_errors=True)

    @staticmethod
    def _adt_env_temizle():
        for k in [k for k in os.environ if k.upper().startswith("ADT_")]:
            os.environ.pop(k, None)

    def setUp(self):
        self._adt_env_temizle()
        self._butce_env = {k: os.environ.get(k) for k in
                           ("AXET_REVIEWER_BUTCE_SN", "AXET_DTEL_GATE_BUTCE_SN")}
        for k in self._butce_env:
            os.environ.pop(k, None)
        type(self)._sayac += 1
        self.p = self.root / f"p{self._sayac}"
        self.p.mkdir(parents=True)
        (self.p / ".conn_adt").write_text(
            f"ADT_SAP_URL=http://127.0.0.1:{self.port}\nADT_SAP_USER={H.KULLANICI}\n"
            f"ADT_SAP_PASSWORD={H.PAROLA}\nADT_SAP_CLIENT=100\nADT_SAP_LANGUAGE=TR\n"
            f"ADT_SAP_TIER=DEV\n", encoding="utf-8")
        (self.p / "sap-project.json").write_text(json.dumps(H.SAP_PROJECT_OK), encoding="utf-8")
        os.environ["AXET_SAP_PROJECT_DIR"] = str(self.p)
        self.sunucu.kayit.clear()
        self.sunucu.gecikme = 0.0

    def tearDown(self):
        self._adt_env_temizle()
        for k, v in self._butce_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.sunucu.gecikme = 0.0

    def kaydet(self, ad, beklenen, gercek, ok):
        H.kaydet(f"{self.ETIKET} {ad}", beklenen, str(gercek)[:160], ok)
        self.assertTrue(ok, f"{ad}: beklenen={beklenen} gerçek={gercek}")

    def struct_yaz(self, n: int) -> Path:
        ddl = ("define structure zaxet_s_k10 {\n"
               + "".join(f"  f{i} : zaxet_e_k10_{i};\n" for i in range(n)) + "}\n")
        yol = self.p / "zaxet_s_k10.ddls.asddls"
        yol.write_text(ddl, encoding="utf-8")
        return yol


# ═══════════════════════ ② yapılandırılabilir bütçe (TEK KAYNAK) ═════════════════════════════════
class K10ButceKaynagi(_Taban):
    ETIKET = "K10a"

    def _butce(self):
        import importlib
        import utils.butce as b
        return importlib.reload(b)

    def test_K10a1_varsayilan_katmanlar_tutarli(self):
        b = self._butce()
        r, z, g = b.reviewer_butce_sn(), b.zincir_butce_sn(), b.gate_butce_sn()
        # Katman sırası YAPISAL olmalı: gate < zincir < sarmalayıcı. (Bugünkü kusur: iç 60 sn >
        # sarmalayıcı 30 sn ⇒ iç dal ULAŞILAMAZ.)
        ok = 0 < g < z < r and r == b.VARSAYILAN_SN
        self.kaydet("1 varsayılan: gate < zincir < sarmalayıcı", "g<z<r", f"{g:g} < {z:g} < {r:g}", ok)
        # Ölçüme dayanak: 1 sn/GET'lik sistemde DTEL gate ~1 GET/sn işler; 28 sn ≈ 28 aday.
        self.kaydet("1 sarmalayıcı varsayılanı ölçüme dayalı (>= eski iç zaman aşımı 60 sn)",
                    ">= 60", r, r >= 60)

    def test_K10a2_env_hem_yukseltir_hem_dusurur(self):
        for deger, bekle in (("120", 120.0), ("10", 10.0)):
            os.environ["AXET_REVIEWER_BUTCE_SN"] = deger
            b = self._butce()
            self.kaydet(f"2 env {deger} → bütçe {bekle:g}", bekle, b.reviewer_butce_sn(),
                        b.reviewer_butce_sn() == bekle)
        os.environ.pop("AXET_REVIEWER_BUTCE_SN", None)

    def test_K10a3_gecersiz_env_varsayilana_duser_ve_uyarir(self):
        b0 = self._butce()
        for deger in ("abc", "0", "-5", "99999", ""):
            os.environ["AXET_REVIEWER_BUTCE_SN"] = deger
            b = self._butce()
            uyari = []
            with mock.patch.object(b, "_uyar", uyari.append):
                sonuc = b.reviewer_butce_sn()
            ok = sonuc == b0.VARSAYILAN_SN and (bool(uyari) or deger == "")
            self.kaydet(f"3 geçersiz env {deger!r} → varsayılan + uyarı", "varsayılan",
                        f"{sonuc:g} · uyarı={len(uyari)}", ok)
        os.environ.pop("AXET_REVIEWER_BUTCE_SN", None)

    def test_K10a4_gate_payi_sarmalayiciyla_olceklenir(self):
        os.environ["AXET_REVIEWER_BUTCE_SN"] = "120"
        b = self._butce()
        buyuk = b.gate_butce_sn()
        os.environ["AXET_REVIEWER_BUTCE_SN"] = "20"
        b = self._butce()
        kucuk = b.gate_butce_sn()
        self.kaydet("4 gate payı sarmalayıcıyla ölçeklenir (120 sn → 20 sn)", "buyuk > kucuk",
                    f"{buyuk:g} > {kucuk:g}", buyuk > kucuk)
        os.environ.pop("AXET_REVIEWER_BUTCE_SN", None)

    def test_K10a5_gate_env_zincir_butcesini_asamaz(self):
        os.environ["AXET_REVIEWER_BUTCE_SN"] = "20"
        os.environ["AXET_DTEL_GATE_BUTCE_SN"] = "999"
        b = self._butce()
        ok = b.gate_butce_sn() <= b.zincir_butce_sn()
        self.kaydet("5 gate env zincir bütçesini AŞAMAZ (999 sn istendi)", "<= zincir",
                    f"{b.gate_butce_sn():g} <= {b.zincir_butce_sn():g}", ok)
        os.environ.pop("AXET_DTEL_GATE_BUTCE_SN", None)
        os.environ.pop("AXET_REVIEWER_BUTCE_SN", None)


# ═══════════════════════ ③ zaman aşımı = BLOCKER (tüm canlı BLOCKER zincirlerinde) ═══════════════
class K10ZamanAsimiBlocker(_Taban):
    ETIKET = "K10b"

    _CANLI_IMI = re.compile(r"\bSAPADTClient\b")

    def _bagimsiz_canli_kume(self) -> set:
        """KONTROL: testin KENDİ taraması — ad→yol çözümü `run_review.validator_yolu()` ile yapılır.

        Bu BAĞIMSIZ bir yoldur: ürün (`_reviewer`) eşlemeyi AST ile okur, test ise run_review'in
        KENDİ çözücüsünü çağırır. İki ayrı uygulama aynı sonucu vermek zorundadır.
        ⚠ Zincirde adı geçen HER script'e bakılır — yalnız `VALIDATORS` dizinindekilere değil
        (harici eşlemeli `check_itg_signoff.py` tam da bu yüzden gözden kaçıyordu).
        """
        rr = _rr()
        adlar = {s for ogeler in rr.TASK_VALIDATORS.values() for s, _sv, _d in ogeler}
        canli = set()
        for s in adlar:
            yol = rr.validator_yolu(s)
            if not yol.exists():
                canli.add(s)          # fail-closed: çözülemeyen/bulunamayan canlı sayılır
            elif self._CANLI_IMI.search(yol.read_text(encoding="utf-8", errors="replace")):
                canli.add(s)
        return canli

    def test_K10b1_canli_kume_koddan_turer(self):
        urun = set(self.rv.canli_validatorler())
        kontrol = self._bagimsiz_canli_kume()
        self.kaydet("1 canlı validator kümesi koddan türer (elle liste değil)", sorted(kontrol),
                    sorted(urun), urun == kontrol)
        self.kaydet("1 küme boş değil (tarama sessizce boş dönmüyor)", ">0", len(urun), len(urun) > 0)
        # Lider düzeltmesi 2026-09-17: harici eşlemeli gate AĞ GATE'İ DEĞİLDİR (gerçek dosya
        # sap-intake-triage/check_intake_signoff.py; import'ları argparse/re/sys/pathlib).
        # Ad→yol çözümü yapılmazsa "bulunamadı ⇒ canlı" kısayolu onu YANLIŞ sınıflar.
        self.kaydet("1 harici eşlemeli check_itg_signoff.py CANLI DEĞİL (ad→yol çözülüyor)",
                    "canlı değil", "canlı" if "check_itg_signoff.py" in urun else "canlı değil",
                    "check_itg_signoff.py" not in urun)

    def test_K10b1b_harici_esleme_sentetik_kontrol_grubu(self):
        """REGRESYON (lider şartı): harici eşlemeli bir validator hem AĞLI hem AĞSIZ hâliyle
        doğru sınıflanmalı. Bugün tek harici gate ağsız; yarın ağa çıkan biri eklenirse aynı
        boşluk TERS yönde ısırır. Sentetik iki dosya = kontrol grubu."""
        agli = self.p / "check_sahte_agli.py"
        agli.write_text("from sap_adt_lib import SAPADTClient\nc = SAPADTClient()\n", encoding="utf-8")
        agsiz = self.p / "check_sahte_agsiz.py"
        agsiz.write_text("import argparse, re, sys\n", encoding="utf-8")
        sahte = {"check_sahte_agli.py": agli, "check_sahte_agsiz.py": agsiz,
                 "check_sahte_cozulemeyen.py": None}
        beklenen = {"check_sahte_agli.py": True, "check_sahte_agsiz.py": False,
                    "check_sahte_cozulemeyen.py": True}   # çözülemeyen → fail-closed canlı
        with mock.patch.object(self.rv, "_harici_yollar", lambda: sahte):
            gercek = {ad: self.rv.canli_mi(ad) for ad in sahte}
        self.kaydet("1b harici eşleme: ağlı=canlı · ağsız=değil · çözülemeyen=fail-closed canlı",
                    beklenen, gercek, gercek == beklenen)

    def _bagimsiz_blocker_gorevleri(self) -> list:
        """KONTROL: beklenen görev kümesini ÜRÜNDEN BAĞIMSIZ hesapla (tautoloji olmasın)."""
        rr = _rr()
        canli = self._bagimsiz_canli_kume()
        return sorted(g for g, ogeler in rr.TASK_VALIDATORS.items()
                      if any(sv == "BLOCKER" and s in canli for s, sv, _d in ogeler))

    def test_K10b2_blocker_gorevleri_canli_x_blocker(self):
        beklenen = self._bagimsiz_blocker_gorevleri()
        urun = sorted(self.rv.zaman_asimi_blocker_gorevleri())
        self.kaydet("2 BLOCKER görevleri = canlı ∩ BLOCKER (konumu çözülemeyen = fail-closed)",
                    beklenen, urun, urun == beklenen)
        # K10 ÖNCESİ kapsam yalnız DTEL gate'liydi; bu iki görev O ZAMAN dışarıdaydı.
        yeni = {"struct_post_create", "sap_active_check"}
        self.kaydet("2 K10 ile kapsama giren canlı BLOCKER zincirleri", sorted(yeni),
                    sorted(yeni & set(urun)), yeni <= set(urun))
        # Kapsam DARALTMA kanıtı: küme "tüm BLOCKER zincirleri" DEĞİL — ağ gate'i olmayan
        # BLOCKER zinciri (itg_s2_signoff) dışarıda kalır (lider ölçümü 2026-09-17).
        self.kaydet("2 küme 6 görev (eski 4 + 2); ağsız BLOCKER zinciri itg_s2_signoff DIŞARIDA",
                    "6 · itg_s2_signoff yok", f"{len(urun)} · {'var' if 'itg_s2_signoff' in urun else 'yok'}",
                    len(urun) == 6 and "itg_s2_signoff" not in urun)

    def _zaman_asimi(self, *_a, **_k):
        raise subprocess.TimeoutExpired(cmd="run_review", timeout=1)

    def test_K10b3_zaman_asimi_hukmu_ve_kontrol_grubu(self):
        yol = self.struct_yaz(1)
        rr = _rr()
        # ⛔ Beklenti ÜRÜNDEN DEĞİL, testin kendi taramasından gelir (yoksa tautoloji: ürün
        #    kümeyi daraltsa test de daralır ve mutasyon yakalanmaz — mutasyon M1 ile ölçüldü).
        blocker_bekleyen = set(self._bagimsiz_blocker_gorevleri())
        # KONTROL GRUBU: canlı BLOCKER taşımayan zincirler WARNING kalır (kapsam DARALTMA kanıtı —
        # "hepsi BLOCKER" ile "canlı BLOCKER'lılar BLOCKER" ayırt edilebilsin).
        kontrol = {"cds_update", "class_push", "interface_push", "program_push", "rap_bdef_creation"}
        with mock.patch.object(self.rv.subprocess, "run", side_effect=self._zaman_asimi):
            hukum = {t: self.rv.run_reviewer(t, str(yol)).verdict
                     for t in sorted(set(rr.TASK_VALIDATORS) )}
        beklenen = {t: ("BLOCKER" if t in blocker_bekleyen else "WARNING") for t in hukum}
        self.kaydet("3 zaman aşımı hükmü: canlı BLOCKER → BLOCKER, diğerleri WARNING",
                    f"{len(blocker_bekleyen)} BLOCKER", {k: v for k, v in hukum.items() if v == "BLOCKER"},
                    hukum == beklenen)
        self.kaydet("3 KONTROL: canlı BLOCKER'sız zincirler WARNING kalır", "hepsi WARNING",
                    {t: hukum[t] for t in sorted(kontrol)},
                    all(hukum[t] == "WARNING" for t in kontrol))

    def test_K10b4_mesaj_uzatma_yolunu_soyler(self):
        yol = self.struct_yaz(1)
        import utils.butce as b
        with mock.patch.object(self.rv.subprocess, "run", side_effect=self._zaman_asimi):
            blk = self.rv.run_reviewer("struct_creation", str(yol))
            wrn = self.rv.run_reviewer("class_push", str(yol))
        for ad, r in (("BLOCKER", blk), ("WARNING", wrn)):
            m = r.skip_reason
            ok = (b.REVIEWER_ENV in m and "ÖLÇÜLEMEDİ" in m
                  and re.search(r"\d", m) is not None)
            self.kaydet(f"4 {ad} mesajı süreyi UZATMA yolunu açıkça söyler ({b.REVIEWER_ENV})",
                        f"{b.REVIEWER_ENV} + süre + ÖLÇÜLEMEDİ", m[-150:], ok)

    def test_K10b5_sarmalayici_gercek_butceyi_kullanir(self):
        """Sabit 30 DEĞİL: `subprocess.run`'a giden `timeout` env ile ölçeklenir (kablolama kanıtı)."""
        yol = self.struct_yaz(1)
        yakalanan = {}

        def sahte_run(*a, **k):
            yakalanan["timeout"] = k.get("timeout")
            raise subprocess.TimeoutExpired(cmd="run_review", timeout=k.get("timeout") or 0)

        import utils.butce as b
        import importlib
        for deger in ("90", "15"):
            os.environ["AXET_REVIEWER_BUTCE_SN"] = deger
            importlib.reload(b)
            with mock.patch.object(self.rv.subprocess, "run", side_effect=sahte_run):
                self.rv.run_reviewer("struct_creation", str(yol))
            self.kaydet(f"5 sarmalayıcı timeout env {deger} ile ölçeklenir", float(deger),
                        yakalanan.get("timeout"), yakalanan.get("timeout") == float(deger))
        os.environ.pop("AXET_REVIEWER_BUTCE_SN", None)
        importlib.reload(b)


# ═══════════════════════ iç ↔ dış katman hizası + uçtan uca yapılandırma etkisi ═══════════════════
class K10KatmanHizasi(_Taban):
    ETIKET = "K10c"

    def test_K10c1_ic_zaman_asimi_sarmalayicidan_kucuk_ve_ULASILABILIR(self):
        """Bugünkü kusur: `run_validator(timeout=60)` > sarmalayıcı 30 ⇒ iç dal hiç koşamaz (ölü dal)."""
        rr = _rr()
        import utils.butce as b
        uyuyan = self.p / "uyu.py"
        uyuyan.write_text("import time\ntime.sleep(60)\n", encoding="utf-8")
        os.environ["AXET_REVIEWER_BUTCE_SN"] = "10"
        import importlib
        importlib.reload(b)
        rr2 = _rr()
        t0 = time.monotonic()
        rc, _out, err = rr2.run_validator(uyuyan, None, [])
        sure = time.monotonic() - t0
        ok = rc == 2 and "TIMEOUT" in err and sure < b.zincir_butce_sn() + 3
        self.kaydet("1 iç zaman aşımı ULAŞILABİLİR: 60 sn uyuyan validator zincir bütçesinde kesilir",
                    f"rc=2 · < {b.zincir_butce_sn() + 3:g} sn", f"rc={rc} · {sure:.1f} sn · {err[:40]}", ok)
        self.kaydet("1 zincir bütçesi < sarmalayıcı bütçesi (katman hizası)", "zincir < sarmalayıcı",
                    f"{b.zincir_butce_sn():g} < {b.reviewer_butce_sn():g}",
                    b.zincir_butce_sn() < b.reviewer_butce_sn())
        os.environ.pop("AXET_REVIEWER_BUTCE_SN", None)
        importlib.reload(b)
        del rr

    def test_K10c2_butceyi_uzatmak_D12_yanlis_BLOCKERini_kapatir(self):
        """D12 (ÖLÇÜLDÜ 2026-09-17): 1 sn/GET sistemde 16 Z DTEL'li yapı 15 sn bütçeye sığmıyor →
        SAP doğru cevap verdiği hâlde ÖLÇÜLEMEDİ → yanlış BLOCKER. Kullanıcı kararı: bütçe
        yapılandırılabilir olsun. KONTROL GRUBU: aynı artefakt, aynı sunucu, YALNIZ bütçe değişir."""
        self.sunucu.gecikme = 0.5
        yol = self.struct_yaz(10)          # 10 aday × 0,5 sn ≈ 5 sn ağ
        os.environ["AXET_REVIEWER_BUTCE_SN"] = "8"      # gate payı ≈ 2 sn → yetmez
        dar = self.rv.run_reviewer("struct_creation", str(yol))
        os.environ["AXET_REVIEWER_BUTCE_SN"] = "30"     # gate payı ≈ 13 sn → yeter
        genis = self.rv.run_reviewer("struct_creation", str(yol))
        os.environ.pop("AXET_REVIEWER_BUTCE_SN", None)
        g_dar = next((x for x in dar.results if x["validator"] == "check_struct_field_dtel_active.py"), {})
        g_genis = next((x for x in genis.results if x["validator"] == "check_struct_field_dtel_active.py"), {})
        ok = (dar.verdict == "BLOCKER" and g_dar.get("status") == "SKIP"
              and g_genis.get("status") == "PASS")
        self.kaydet("2 dar bütçe → ÖLÇÜLEMEDİ=BLOCKER · geniş bütçe → aynı artefakt ÖLÇÜLDÜ=PASS",
                    "BLOCKER/SKIP → PASS", f"{dar.verdict}/{g_dar.get('status')} → "
                    f"{genis.verdict}/{g_genis.get('status')}", ok)


if __name__ == "__main__":
    unittest.main(verbosity=2)
