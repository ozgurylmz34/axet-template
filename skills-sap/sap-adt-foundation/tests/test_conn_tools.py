# -*- coding: utf-8 -*-
"""Çoklu sistem bağlantısı (2026-09-13): switch_tier.py · setup_credentials.py · .conn_adt.example. Ağ yok.

Sahte slot değerleri test anında tempfile altında üretilir; repoya `.env`/`.conn*` dosyası konmaz.
"""
from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import _helpers as H

sys.dont_write_bytecode = True
if str(H.SCRIPTS) not in sys.path:
    sys.path.insert(0, str(H.SCRIPTS))

import setup_credentials as SC  # noqa: E402
import switch_tier as ST  # noqa: E402

SAHTE_URL = "https://sahte-slot.example:44300"


def slot_yaz(proj: Path, ad: str, tier_satirlari=("ADT_SAP_TIER=DEV",), ek=()):
    (proj / "conn").mkdir(exist_ok=True)
    satir = [f"ADT_SAP_URL={SAHTE_URL}", f"ADT_SAP_USER={H.KULLANICI}", f"ADT_SAP_PASSWORD={H.PAROLA}",
             "ADT_SAP_CLIENT=100", "ADT_SAP_LANGUAGE=TR", *tier_satirlari, f"ADT_SAP_SYSTEM_NAME={ad}", *ek]
    (proj / "conn" / f"{ad}.env").write_text("\n".join(satir) + "\n", encoding="utf-8")


class Baglanti(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="axet_conn_"))
        self.p = self.root / "proje"
        self.p.mkdir()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def kaydet(self, ad, beklenen, gercek, ok):
        H.kaydet(f"BAĞLANTI {ad}", beklenen, str(gercek)[:160], ok)
        self.assertTrue(ok, f"{ad}: {gercek}")

    def st(self, *argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            kod = ST.main([*argv, "--project-dir", str(self.p)])
        out = buf.getvalue()
        return kod, json.loads(out), out

    # ── switch_tier ──────────────────────────────────────────────────────────────────────
    def test_01_ad_ile_gecis_yedek_ve_sizinti_yok(self):
        slot_yaz(self.p, "DEMO_DEV")
        slot_yaz(self.p, "DEMO_QA", ("ADT_SAP_TIER=QA",))
        (self.p / ".conn_adt").write_text("ADT_SAP_TIER=QA\n", encoding="utf-8")
        kod, d, out = self.st("demo_dev")
        from sapadt._conn import get_active_tier
        ok = (kod == 0 and d["system"] == "DEMO_DEV" and d["tier"] == "DEV" and d["backup"] == "conn/.conn_adt.bak"
              and (self.p / "conn" / ".conn_adt.bak").read_text(encoding="utf-8") == "ADT_SAP_TIER=QA\n"
              and get_active_tier(self.p) == "DEV"
              and all(s not in out for s in (H.PAROLA, H.KULLANICI, "sahte-slot", "100")))
        self.kaydet("01 ad ile geçiş → .conn_adt DEV, eski dosya yedeklendi, değer basılmadı", "0 · DEV · bak",
                    f"{kod} {d.get('tier')} {d.get('backup')}", ok)

    def test_02_tier_ile_tek_ve_belirsiz(self):
        slot_yaz(self.p, "DEMO_DEV")
        slot_yaz(self.p, "DEMO_QA", ("ADT_SAP_TIER=QA",))
        slot_yaz(self.p, "DEMO2_QA", ("ADT_SAP_TIER=QAS",))
        k1, d1, _ = self.st("DEV")
        k2, d2, _ = self.st("QA")
        k3, d3, _ = self.st("YOK_BOYLE")
        ok = (k1 == 0 and d1["system"] == "DEMO_DEV" and k2 == 2 and d2["error"]["code"] == "ambiguous_tier"
              and len(d2["systems"]) == 2 and k3 == 2 and d3["error"]["code"] == "system_not_found")
        self.kaydet("02 DEV tek → geçer · QA iki sistem → belirsiz (2) · bilinmeyen → 2", "0 · 2 ambiguous · 2",
                    f"{k1} {k2} {d2.get('error', {}).get('code')} {k3}", ok)

    def test_03_yer_tutucu_ve_qa_uyarisi(self):
        slot_yaz(self.p, "DEMO_PH", ek=("ADT_SAP_CLIENT=<CLIENT>",))
        slot_yaz(self.p, "DEMO_PRD", ("ADT_SAP_TIER=PRD",), ek=("ADT_SAP_PASSWORD=<a<b",))
        k1, d1, out1 = self.st("DEMO_PH")
        k2, d2, _ = self.st("DEMO_PRD")
        ok = (k1 == 1 and d1["error"]["code"] == "placeholder_values" and "<CLIENT>" not in out1
              and k2 == 0 and d2["tier"] == "PRD" and "SALT-OKUNUR" in d2["warnings"][0])
        self.kaydet("03 <...> yer tutucu → geçiş yok (1) · parolada '<' yer tutucu sayılmaz · PRD uyarısı", "1 · 0 PRD",
                    f"{k1} {k2} {d2.get('warnings')}", ok)

    def test_04_tier_yok_cakisan_onek(self):
        slot_yaz(self.p, "DEMO_YOK", tier_satirlari=())
        slot_yaz(self.p, "DEMO_CAK", ("ADT_SAP_TIER=DEV", "ADT_SAP_TIER=PRD"))
        slot_yaz(self.p, "DEMO_ONEK", ("ADT_SAP_TIER_OLD=DEV",))
        tierler = {ad: t for ad, _y, t in ST.registry(self.p / "conn")}
        k, d, _ = self.st("DEMO_CAK")
        ok = (tierler == {"DEMO_CAK": "UNKNOWN", "DEMO_ONEK": "UNKNOWN", "DEMO_YOK": "UNKNOWN"}
              and k == 0 and d["tier"] == "UNKNOWN" and "fail-closed" in d["warnings"][0])
        self.kaydet("04 tier yok / çakışan iki satır / önek satırı → UNKNOWN (sessiz DEV yok)", "UNKNOWN × 3",
                    tierler, ok)

    def test_05_liste_ve_kullanim(self):
        slot_yaz(self.p, "DEMO_DEV")
        k, d, out = self.st("--list")
        buf = io.StringIO()
        with redirect_stdout(buf):
            k2 = ST.main(["--project-dir", str(self.p)])
        ok = (k == 0 and d["systems"] == [{"system": "DEMO_DEV", "tier": "DEV", "file": "conn/DEMO_DEV.env"}]
              and H.PAROLA not in out and k2 == 3)
        self.kaydet("05 --list yalnız ad+tier · hedefsiz çağrı kullanım (3)", "0 · 3", f"{k} {k2}", ok)

    # ── setup_credentials ────────────────────────────────────────────────────────────────
    def test_06_etkilesimsiz_red_alt_surec(self):
        r = subprocess.run([sys.executable, str(H.SCRIPTS / "setup_credentials.py"), "--project-dir", str(self.p)],
                           stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8",
                           env=H.clean_env(), timeout=60)
        ok = r.returncode == 3 and "etkileşimli" in r.stderr and not (self.p / ".conn_adt").exists() and r.stdout == ""
        self.kaydet("06 stdin terminal değil → 3, soru yok, dosya yok", "3 · dosya yok", f"{r.returncode} {r.stderr[:80]}", ok)

    def _sc(self, cevaplar, parolalar, *argv, sap_project=True):
        if sap_project:
            (self.p / "sap-project.json").write_text(json.dumps(H.SAP_PROJECT_OK), encoding="utf-8")
        cv, pw = list(cevaplar), list(parolalar)
        o, e = io.StringIO(), io.StringIO()
        with redirect_stdout(o), redirect_stderr(e):
            kod = SC.main(["--project-dir", str(self.p), *argv], girdi=lambda _m: cv.pop(0),
                          parola=lambda _m: pw.pop(0), tty=True)
        return kod, o.getvalue() + e.getvalue()

    def test_07_yazar_degerleri_basmaz(self):
        cev = [SAHTE_URL, H.KULLANICI, "100", "", "", "DEV", "DEMO_DEV"]
        kod, out = self._sc(cev, [H.PAROLA, H.PAROLA], "--slot", "DEMO_DEV")
        hedef = self.p / "conn" / "DEMO_DEV.env"
        metin = hedef.read_text(encoding="utf-8") if hedef.is_file() else ""
        ok = (kod == 0 and f"ADT_SAP_PASSWORD={H.PAROLA}" in metin and "ADT_SAP_LANGUAGE=TR" in metin
              and "ADT_SAP_SSL_VERIFY=false" in metin and "ADT_SAP_TIER=DEV" in metin
              and all(s not in out for s in (H.PAROLA, H.KULLANICI, "sahte-slot")) and "sap_doctor" in out)
        k2, d2, _ = self.st("DEMO_DEV")
        self.kaydet("07 slot yazıldı (dil master_language'den) · değer basılmadı · switch_tier ile etkinleşir",
                    "0 · 0 DEV", f"{kod} {k2} {d2.get('tier')}", ok and k2 == 0 and d2["tier"] == "DEV")

    def test_08_dogrulama_ve_eslesmeyen_parola(self):
        k1, out1 = self._sc([SAHTE_URL, H.KULLANICI, "100", "", "", "DEV", "X"], [H.PAROLA, "farkli"])
        k2, out2 = self._sc(["ftp://x", H.KULLANICI, "10", "EN", "belki", "PROD", "a b"], [H.PAROLA, H.PAROLA])
        ok = (k1 == 1 and "eşleşmiyor" in out1 and k2 == 1 and not (self.p / ".conn_adt").exists()
              and all(k in out2 for k in ("ADT_SAP_URL", "ADT_SAP_CLIENT", "ADT_SAP_SSL_VERIFY", "ADT_SAP_TIER",
                                          "ADT_SAP_SYSTEM_NAME", "master_language"))
              and H.PAROLA not in out2 and "ftp://x" not in out2)
        self.kaydet("08 parola eşleşmez → 1 · geçersiz URL/client/TLS/tier/ad/dil → 1, dosya yok, değer basılmadı",
                    "1 · 1", f"{k1} {k2}", ok)

    def test_09_var_olan_dosya_onaysiz_yazilmaz(self):
        (self.p / ".conn_adt").write_text("ESKI=1\n", encoding="utf-8")
        kod, out = self._sc(["h"], [])
        ok = kod == 1 and (self.p / ".conn_adt").read_text(encoding="utf-8") == "ESKI=1\n"
        self.kaydet("09 var olan .conn_adt → onay 'h' → dokunulmadı", "1 · aynı", kod, ok)

    def test_10_ornek_anahtarlar_yazici_ile_ayni(self):
        ornek = H.FOUNDATION / "assets" / ".conn_adt.example"
        anahtar = [ln.split("=", 1)[0] for ln in ornek.read_text(encoding="utf-8").splitlines()
                   if ln.strip() and not ln.startswith("#") and "=" in ln]
        ok = tuple(anahtar) == SC.ANAHTARLAR
        self.kaydet("10 .conn_adt.example anahtarları == setup_credentials.ANAHTARLAR", "aynı sıra", anahtar, ok)


class ProfilMatrisi(unittest.TestCase):
    def test_profiles_md_cli_etiketleriyle_tutarli(self):
        from sapadt._app import load_all_tools
        from sapadt._profile import TIP_PROFIL_KISITI
        md = (H.FOUNDATION / "references" / "profiles.md").read_text(encoding="utf-8")
        kayit = load_all_tools()
        bolum = md.split("<!-- CLI-ETIKETLERI -->", 2)
        self.assertEqual(len(bolum), 3, "profiles.md CLI-ETIKETLERI işaretleri eksik")
        satirlar = {}
        for ln in bolum[1].splitlines():
            m = __import__("re").match(r"^\| `([a-z_]+)` \| ([^|]+) \|", ln)
            if m:
                satirlar[m.group(1)] = sorted(x.strip() for x in m.group(2).split(","))
        beklenen = {ad: sorted(s.available_on) for ad, s in kayit.items() if tuple(s.available_on) != ("all",)}
        tip = {}
        for ln in bolum[1].splitlines():
            m = __import__("re").match(r"^\| tip `([a-z]+)` \| ([^|]+) \|", ln)
            if m:
                tip[m.group(1)] = sorted(x.strip() for x in m.group(2).split(","))
        ok = satirlar == beklenen and tip == {t: sorted(p) for t, p in TIP_PROFIL_KISITI.items()}
        H.kaydet("PROFİL profiles.md kısıtlı araç + tip etiketleri == REGISTRY/TIP_PROFIL_KISITI", "eşit",
                 f"md={satirlar} tip={tip}", ok)
        self.assertTrue(ok, f"md={satirlar} beklenen={beklenen} tip={tip}")


if __name__ == "__main__":
    unittest.main()
