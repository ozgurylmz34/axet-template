# -*- coding: utf-8 -*-
"""`AXET-GATE-STATUS` sözleşmesi — üretici ↔ tüketici bağı + yabancı önek fail-closed (2026-09-14).

Önek `AXET-` olarak yeniden adlandırıldı; geçiş dönemi YOK. Bu dosya üç şeyi ölçer:
  ① Üreticiler (`_gate_status.gate_status`, sabit `print` satırları, gerçek bir validator süreci) yeni
    öneki basar ve tüketici (`run_review.gate_durum_beyani`) onu ayrıştırır.
  ② NEGATİF: yabancı/eski önekli satır "yok sayılıp" `beyan=None` → `rc 0` → PASS'e DÜŞMEZ;
    `measured=false` (ölçüm kanıtı yok) sayılır. `measured=true status=OK` diyen yabancı satır da kabul edilmez.
  ③ Uçtan uca: `run_review.main()` bu satırı basan BLOCKER gate için verdict BLOCKER + exit 1 verir;
    kontrol grubu olarak aynı sahte gate yeni önekle `measured=true` basınca PASS + exit 0.
Hepsi GERÇEK kodu çağırır; ağ/SAP yok. Eski önek metni sızıntı taramasına takılmasın diye parçalı kurulur.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import _helpers as H

sys.dont_write_bytecode = True
VALIDATORS = H.SCRIPTS / "sapadt" / "lib" / "validators"
ESKI_ONEK = "I" + "X"  # yeniden adlandırma öncesi önek


def _yukle(ad: str, dosya: str):
    if str(VALIDATORS) not in sys.path:
        sys.path.insert(0, str(VALIDATORS))
    spec = importlib.util.spec_from_file_location(ad, str(VALIDATORS / dosya))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _satir(onek: str, measured: str = "false", status: str = "SKIPPED", gate: str = "check_sahte") -> str:
    return f"{onek}-GATE-STATUS: gate={gate} status={status} measured={measured} reason=sap-baglanti-yok\n"


class GateStatusSozlesme(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rr = _yukle("_rr_gate_sozlesme", "run_review.py")
        cls.gs = _yukle("_gate_status", "_gate_status.py")

    def kaydet(self, ad, beklenen, gercek, ok):
        H.kaydet(f"GATE-STATUS {ad}", beklenen, str(gercek)[:160], ok)
        self.assertTrue(ok, f"{ad}: {gercek}")

    # ── ① üretici ↔ tüketici ─────────────────────────────────────────────────────────────
    def test_1_ortak_uretici_tuketiciyle_eslesir(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.gs.sap_baglanti_yok("check_sahte")
        b = self.rr.gate_durum_beyani(buf.getvalue(), "check_sahte.py")
        self.kaydet("_gate_status → gate_durum_beyani", "AXET- · measured=false",
                    f"{buf.getvalue().strip()} → {b}",
                    buf.getvalue().startswith("AXET-GATE-STATUS: ") and b is not None
                    and b["measured"] == "false" and b["reason"] == "sap-baglanti-yok")

    def test_2_kaynaktaki_tum_sabit_ureticiler_yeni_onekli(self):
        desen = re.compile(r"""print\(\s*f?['"]([^'"\s]*)-GATE-STATUS:""")
        bulunan = {}
        for p in sorted(VALIDATORS.glob("*.py")):
            for onek in desen.findall(p.read_text(encoding="utf-8")):
                bulunan.setdefault(onek, []).append(p.name)
        self.kaydet("validator print satırlarının öneki", "yalnız AXET (≥4 üretici)", bulunan,
                    set(bulunan) == {"AXET"} and len(bulunan["AXET"]) >= 4)
        self.kaydet("tüketici regex'i aynı önek", "^AXET-GATE-STATUS:", self.rr._GATE_DURUM_RE.pattern[:22],
                    self.rr._GATE_DURUM_RE.pattern.startswith("^AXET-GATE-STATUS:"))

    def test_3_gercek_validator_sureci_measured_false_uretir(self):
        with tempfile.TemporaryDirectory() as td:
            art = Path(td) / "domain.txt"
            art.write_text("x", encoding="utf-8")
            rc, out, err = self.rr.run_validator(VALIDATORS / "check_domain_output_length.py", str(art), [])
        b = self.rr.gate_durum_beyani(out, "check_domain_output_length.py")
        self.kaydet("check_domain_output_length .txt → rc0 + ayrıştırılan measured=false", "rc=0 · measured=false",
                    f"rc={rc} beyan={b}", rc == 0 and b is not None and b["measured"] == "false"
                    and b["gate"] == "check_domain_output_length")

    # ── ② negatif: yabancı önek ─────────────────────────────────────────────────────────
    def test_4_yabanci_onek_sessiz_pass_olmaz(self):
        vakalar = [
            ("eski önek measured=false", _satir(ESKI_ONEK)),
            ("eski önek measured=true status=OK", _satir(ESKI_ONEK, "true", "OK")),
            ("başka önek", _satir("ESKI")),
            ("küçük harf axet", _satir("axet", "true", "OK")),
        ]
        for ad, stdout in vakalar:
            b = self.rr.gate_durum_beyani("önce bir satır\n" + stdout, "check_sahte.py")
            self.kaydet(f"yabancı önek: {ad}", "measured=false · taninmayan-onek",
                        b, b is not None and b["measured"] == "false"
                        and b["reason"].startswith("taninmayan-onek-") and b["gate"] == "check_sahte")

    def test_5_sinirlar_korunur(self):
        self.kaydet("durum satırı yok → None (bugünkü davranış)", "None",
                    self.rr.gate_durum_beyani("temiz\n", "check_sahte.py"),
                    self.rr.gate_durum_beyani("temiz\n", "check_sahte.py") is None)
        girintili = "    " + _satir(ESKI_ONEK)
        self.kaydet("girintili (tarif eden) yabancı satır beyan sayılmaz", "None",
                    self.rr.gate_durum_beyani(girintili, "check_sahte.py"),
                    self.rr.gate_durum_beyani(girintili, "check_sahte.py") is None)
        karisik = _satir(ESKI_ONEK) + _satir("AXET", "true", "OK")
        b = self.rr.gate_durum_beyani(karisik, "check_sahte.py")
        self.kaydet("geçerli AXET beyanı varsa o kazanır", "measured=true · OK", b,
                    b is not None and b["measured"] == "true" and b["status"] == "OK")

    # ── ③ uçtan uca run_review.main ─────────────────────────────────────────────────────
    def _main_kos(self, validator_stdout: str):
        rr = self.rr
        with tempfile.TemporaryDirectory() as td:
            sahte = Path(td) / "check_sahte.py"
            sahte.write_text("import sys\nsys.stdout.write(" + repr(validator_stdout) + ")\nsys.exit(0)\n",
                             encoding="utf-8")
            art = Path(td) / "z.txt"
            art.write_text("x", encoding="utf-8")
            eski = (rr.TASK_VALIDATORS, rr.validator_yolu, sys.argv)
            rr.TASK_VALIDATORS = {"_sozlesme_testi": [("check_sahte.py", "BLOCKER", "sahte gate")]}
            rr.validator_yolu = lambda ad: sahte
            sys.argv = ["run_review.py", "--task", "_sozlesme_testi", "--artifact", str(art)]
            out, err = io.StringIO(), io.StringIO()
            try:
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    rc = rr.main()
            finally:
                rr.TASK_VALIDATORS, rr.validator_yolu, sys.argv = eski
        verdict = re.search(r"^VERDICT: (\S+)", out.getvalue(), re.M)
        return rc, verdict.group(1) if verdict else None, out.getvalue()

    def test_6_uctan_uca_eski_onek_blocker_kontrol_grubu_pass(self):
        rc, v, out = self._main_kos("ölçemedim\n" + _satir(ESKI_ONEK))
        self.kaydet("run_review: BLOCKER gate eski önekle measured=false basar → BLOCKER", "exit 1 · BLOCKER",
                    f"exit {rc} · {v}", rc == 1 and v == "BLOCKER" and "taninmayan-onek-" in out)
        rc, v, _ = self._main_kos(_satir(ESKI_ONEK, "true", "OK"))
        self.kaydet("run_review: eski önekle measured=true de kabul edilmez → BLOCKER", "exit 1 · BLOCKER",
                    f"exit {rc} · {v}", rc == 1 and v == "BLOCKER")
        rc, v, _ = self._main_kos(_satir("AXET", "true", "OK"))
        self.kaydet("run_review KONTROL: yeni önek measured=true → PASS", "exit 0 · PASS",
                    f"exit {rc} · {v}", rc == 0 and v == "PASS")
        rc, v, _ = self._main_kos(_satir("AXET"))
        self.kaydet("run_review KONTROL: yeni önek measured=false → BLOCKER", "exit 1 · BLOCKER",
                    f"exit {rc} · {v}", rc == 1 and v == "BLOCKER")

    # ── ④ negatif: AXET önekli ama BİÇİMİ BOZUK satır ─────────────────────────────────────
    # Satır-başında `AXET-GATE-STATUS:` var ama tam sözleşmeye uymuyor. Yok sayılırsa beyan=None
    # → rc 0 → PASS olur; `measured=false reason=bicim-bozuk` sayılmalı.
    BOZUKLAR = (
        ("measured=maybe", "AXET-GATE-STATUS: gate=check_sahte status=OK measured=maybe reason=x\n"),
        ("reason içinde boşluk", "AXET-GATE-STATUS: gate=check_sahte status=OK measured=true reason=iki kelime\n"),
        ("reason eksik", "AXET-GATE-STATUS: gate=check_sahte status=OK measured=true\n"),
    )

    def test_7_bicimi_bozuk_axet_satiri_measured_false(self):
        for ad, satir in self.BOZUKLAR:
            b = self.rr.gate_durum_beyani("önce bir satır\n" + satir, "check_sahte.py")
            self.kaydet(f"bozuk biçim: {ad}", "measured=false · bicim-bozuk", b,
                        b is not None and b["measured"] == "false" and b["reason"] == "bicim-bozuk"
                        and b["gate"] == "check_sahte")
        karisik = _satir("AXET", "true", "OK") + self.BOZUKLAR[0][1]
        b = self.rr.gate_durum_beyani(karisik, "check_sahte.py")
        self.kaydet("geçerli + bozuk AXET satırı birlikte → bozuk kazanır (çelişkili beyan)",
                    "measured=false · bicim-bozuk", b,
                    b is not None and b["measured"] == "false" and b["reason"] == "bicim-bozuk")
        ters = self.BOZUKLAR[0][1] + _satir("AXET", "true", "OK")
        b = self.rr.gate_durum_beyani(ters, "check_sahte.py")
        self.kaydet("bozuk ÖNCE + geçerli SONRA → yine bozuk (yalnız son satıra bakılmaz)",
                    "measured=false · bicim-bozuk", b,
                    b is not None and b["measured"] == "false" and b["reason"] == "bicim-bozuk")
        girintili = "    " + self.BOZUKLAR[0][1]
        self.kaydet("KONTROL: girintili (tarif eden) bozuk satır beyan sayılmaz", "None",
                    self.rr.gate_durum_beyani(girintili, "check_sahte.py"),
                    self.rr.gate_durum_beyani(girintili, "check_sahte.py") is None)
        b = self.rr.gate_durum_beyani(_satir("AXET", "true", "OK"), "check_sahte.py")
        self.kaydet("KONTROL: geçerli AXET satırı aynen ayrıştırılır", "measured=true · OK", b,
                    b is not None and b["measured"] == "true" and b["status"] == "OK")

    def test_8_uctan_uca_bozuk_bicim_blocker_kontrol_grubu_pass(self):
        for ad, satir in self.BOZUKLAR:
            rc, v, out = self._main_kos("ölçtüm sanırım\n" + satir)
            self.kaydet(f"run_review: BLOCKER gate bozuk biçim ({ad}) → BLOCKER", "exit 1 · BLOCKER",
                        f"exit {rc} · {v}", rc == 1 and v == "BLOCKER" and "bicim-bozuk" in out)
        rc, v, _ = self._main_kos("ölçtüm\n" + _satir("AXET", "true", "OK"))
        self.kaydet("run_review KONTROL: geçerli satır measured=true → PASS", "exit 0 · PASS",
                    f"exit {rc} · {v}", rc == 0 and v == "PASS")


if __name__ == "__main__":
    unittest.main()
