# -*- coding: utf-8 -*-
"""Z90 — SAP yazma PATİNAJ KESİCİSİ (süreç içi, GERÇEK hat: `sap_adt_cli.calistir` → kapı → araç; ağ yok).

Araç (`adt_push_source`) REGISTRY'de sahte bir fonksiyonla değiştirilir ve her çağrıyı kaydeder ⇒
"yazma DENENMEDİ" iddiası çağrı sayısıyla kanıtlanır. Opt-in dosyası repoya yazılmaz (`gate.optin_file` yamalı).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import _helpers as H

AD = "ZAXET_PATINAJ"
TIP = "program"
KAYNAK = "REPORT zaxet_patinaj.\nWRITE 'x'.\n"
BAYRAK = dict(sap_write=True, scope="S1", reason="Patinaj kesicisi birim testi gerekçesi")


class PatinajKesici(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="axet_patinaj_"))
        cls._eski_env = {"AXET_SAP_PROJECT_DIR": os.environ.get("AXET_SAP_PROJECT_DIR")}
        for k in [k for k in os.environ if k.upper().startswith("ADT_")]:
            cls._eski_env.setdefault(k, os.environ.get(k))
            os.environ.pop(k, None)
        from sapadt import gate
        from sapadt._app import REGISTRY, load_all_tools
        import sap_adt_cli
        load_all_tools()
        cls.gate, cls.REG, cls.cli = gate, REGISTRY, sap_adt_cli
        cls._eski_optin = gate.optin_file
        optin = cls.root / "home" / "config" / "sap-write.local"
        optin.parent.mkdir(parents=True)
        optin.write_text("test opt-in\n", encoding="utf-8")
        gate.optin_file = lambda axet_home=None: optin
        cls._n = 0

    @classmethod
    def tearDownClass(cls):
        cls.gate.optin_file = cls._eski_optin
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
        orj = self.REG["adt_push_source"].fn
        self.addCleanup(setattr, self.REG["adt_push_source"], "fn", orj)
        self.cagri: list = []
        self.sonuclar: list = []   # sıradaki çağrının dönüşü (boşsa başarı)

        def sahte(**kw):
            self.cagri.append(kw.get("name"))
            return self.sonuclar.pop(0) if self.sonuclar else {"ok": True, "name": kw.get("name")}
        self.REG["adt_push_source"].fn = sahte

    def push(self, ad=AD, tip=TIP):
        return self.cli.calistir("adt_push_source", {"name": ad, "object_type": tip, "source": KAYNAK},
                                 self.p, tls_uyarisi=False, **BAYRAK)

    @staticmethod
    def hata(kod):
        return {"ok": False, "error": kod, "message": f"sahte {kod}"}

    def kod(self, payload):
        return (payload.get("error") or {}).get("code")

    def kaydet(self, ad, beklenen, gercek, ok):
        H.kaydet(f"PATINAJ {ad}", beklenen, str(gercek)[:200], ok)
        self.assertTrue(ok, f"{ad}: {gercek}")

    def durum(self):
        f = self.p / ".axet-code" / "sap-write-failures.json"
        return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}

    def test_P1_uc_ayni_hata_sonraki_yazma_denenmez(self):
        self.sonuclar = [self.hata("push_failed")] * 3
        kodlar = [self.push() for _ in range(3)]
        n3 = len(self.cagri)
        payload, kod = self.push()
        log = [json.loads(s) for s in (self.p / ".axet-code" / "sap-write-log.jsonl")
               .read_text(encoding="utf-8").splitlines()]
        self.kaydet("P1 3 ardışık aynı kod → 4. çağrı repeated_failure (çıkış 2), araç ÇAĞRILMADI, log'da iz",
                    "ilk3 exit1 · araç=3 · exit 2 repeated_failure · araç hâlâ 3 · log son=repeated_failure",
                    f"ilk3={[k for _p, k in kodlar]} · araç={n3} · exit {kod} {self.kod(payload)} · "
                    f"araç={len(self.cagri)} · log={log[-1].get('result')}",
                    [k for _p, k in kodlar] == [1, 1, 1] and n3 == 3 and kod == 2
                    and self.kod(payload) == "repeated_failure" and len(self.cagri) == 3
                    and log[-1].get("result") == "repeated_failure")
        seri = kodlar[-1][0].get("failure_streak") or {}
        self.kaydet("P1b 3. başarısızlık yanıtı seriyi görünür kılar", "failure_streak count=3 limit=3",
                    seri, seri.get("count") == 3 and seri.get("limit") == 3 and seri.get("code") == "push_failed")

    def test_P2_KONTROL_farkli_hata_seriyi_sifirlar(self):
        self.sonuclar = [self.hata("push_failed"), self.hata("push_failed"), self.hata("activation_failed"),
                         self.hata("push_failed")]
        for _ in range(4):
            self.push()
        payload, kod = self.push()   # başarı döner
        self.kaydet("P2 KONTROL: farklı kod araya girince engel YOK (5 çağrının 5'i araca ulaştı)",
                    "araç=5 · son exit 0", f"araç={len(self.cagri)} · exit {kod} {self.kod(payload)}",
                    len(self.cagri) == 5 and kod == 0)

    def test_P3_KONTROL_basari_seriyi_sifirlar(self):
        self.sonuclar = [self.hata("push_failed"), self.hata("push_failed"), {"ok": True},
                         self.hata("push_failed"), self.hata("push_failed")]
        for _ in range(5):
            self.push()
        payload, kod = self.push()
        self.kaydet("P3 KONTROL: araya giren başarı seriyi sıfırlar (6 çağrı araca ulaştı, kayıt silindi)",
                    "araç=6 · exit 0 · kayıt yok", f"araç={len(self.cagri)} · exit {kod} · durum={self.durum()}",
                    len(self.cagri) == 6 and kod == 0 and self.durum() == {})

    def test_P4_KONTROL_tek_basarisizlik_engellemez_ve_obje_ayrimi(self):
        self.sonuclar = [self.hata("push_failed")] * 3
        for _ in range(3):
            self.push()
        payload, kod = self.push(ad="ZAXET_BASKA")
        self.kaydet("P4 KONTROL: A'nın serisi B'yi engellemez", "araç=4 · exit 0",
                    f"araç={len(self.cagri)} · exit {kod} {self.kod(payload)}", len(self.cagri) == 4 and kod == 0)

    def test_P5_pencere_dolunca_seri_duser(self):
        self.sonuclar = [self.hata("push_failed")] * 3
        for _ in range(3):
            self.push()
        d = self.durum()
        eski = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=2, minutes=1)).isoformat(timespec="seconds")
        for rec in d.values():
            rec["last_at"] = eski
        (self.p / ".axet-code" / "sap-write-failures.json").write_text(json.dumps(d), encoding="utf-8")
        payload, kod = self.push()
        self.kaydet("P5 son başarısızlık 2 saatten eski → engel yok, araca gidildi", "araç=4 · exit 0",
                    f"araç={len(self.cagri)} · exit {kod} {self.kod(payload)}", len(self.cagri) == 4 and kod == 0)

    def test_P6_bozuk_dosya_fail_open(self):
        f = self.p / ".axet-code" / "sap-write-failures.json"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("{bozuk", encoding="utf-8")
        payload, kod = self.push()
        self.kaydet("P6 bozuk sayaç dosyası yazmayı ENGELLEMEZ (fren, kapı değil) + dosya onarıldı",
                    "araç=1 · exit 0 · dosya JSON", f"araç={len(self.cagri)} · exit {kod} · {f.read_text(encoding='utf-8')[:40]}",
                    len(self.cagri) == 1 and kod == 0 and json.loads(f.read_text(encoding="utf-8")) == {})

    def test_P7_kapi_reddi_sayilmaz(self):
        # Kapı reddi (araçtan önce) seriye girmez: kapsam beyanı eksik → scope_missing, araç çağrılmaz.
        for _ in range(4):
            payload, kod = self.cli.calistir("adt_push_source", {"name": AD, "object_type": TIP, "source": KAYNAK},
                                             self.p, tls_uyarisi=False, sap_write=True)
        self.kaydet("P7 kapı reddi (scope_missing) sayaca girmez", "exit 2 scope_missing · araç=0 · kayıt yok",
                    f"exit {kod} {self.kod(payload)} · araç={len(self.cagri)} · {self.durum()}",
                    kod == 2 and self.kod(payload) == "scope_missing" and not self.cagri and self.durum() == {})


if __name__ == "__main__":
    unittest.main()
