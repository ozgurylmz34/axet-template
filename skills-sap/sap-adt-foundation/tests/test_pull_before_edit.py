# -*- coding: utf-8 -*-
"""PULL-BEFORE-EDIT (süreç içi, istemci yamalı; ağ yok).

`atom._get_client` sahte bir istemciyle değiştirilir. İstemci hangi çağrıların yapıldığını
kaydeder → "push'a hiç gidilmedi" iddiası çağrı listesiyle kanıtlanır.
"""
from __future__ import annotations

import json
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

AD = "ZAXET_PBE"
TIP = "program"          # reviewer zinciri yok (SKIP) → test hızlı; tip ABAP → Yasak B taraması koşar
KAYNAK = "REPORT zaxet_pbe.\nWRITE 'eski'.\n"


class Sahte:
    def __init__(self, canli: str | None, okuma_hatasi: Exception | None = None):
        self.canli = canli
        self.okuma_hatasi = okuma_hatasi
        self.cagri: list[str] = []

    def download_object(self, name, object_type=None, save_local=False):
        self.cagri.append("download")
        if self.okuma_hatasi:
            raise self.okuma_hatasi
        return self.canli

    def get_object_metadata(self, name, object_type=None):
        self.cagri.append("metadata")
        return "<meta/>"

    def push_object(self, object_name, object_type="class", transport=None, source_file=None):
        self.cagri.append("push")
        self.canli = Path(source_file).read_text(encoding="utf-8")
        return {"success": True, "source_uploaded": True, "activated": True, "readback_ok": True}

    def create_object(self, **kw):
        self.cagri.append("create")
        return "/sap/bc/adt/programs/programs/zaxet_yeni"


class PullBeforeEdit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="axet_pbe_"))
        cls._eski_env = {k: os.environ.get(k) for k in ("AXET_SAP_PROJECT_DIR", "ADT_SAP_TIER")}
        os.environ.pop("ADT_SAP_TIER", None)
        from sapadt.tools import atom
        from sapadt import pull_state
        cls.atom, cls.ps = atom, pull_state
        cls._eski_client = atom._get_client
        cls._sayac = 0

    @classmethod
    def tearDownClass(cls):
        cls.atom._get_client = cls._eski_client
        for k, v in cls._eski_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(cls.root, ignore_errors=True)

    def setUp(self):
        type(self)._sayac += 1
        self.p = H.make_project(self.root, f"p{self._sayac}")
        os.environ["AXET_SAP_PROJECT_DIR"] = str(self.p)

    def istemci(self, sahte: Sahte):
        self.atom._get_client = lambda: sahte
        return sahte

    def durum(self) -> dict:
        f = self.p / ".axet-code" / "sap-pull-state.json"
        return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}

    def kaydet(self, ad, beklenen, gercek, ok):
        H.kaydet(f"PBE {ad}", beklenen, gercek, ok)
        self.assertTrue(ok, f"{ad}: {gercek}")

    def test_1_kayit_yok_red(self):
        s = self.istemci(Sahte(KAYNAK))
        r = self.atom.adt_push_source(AD, TIP, KAYNAK + "WRITE 'yeni'.\n")
        self.kaydet("kayıt yok → red, istemciye hiç gidilmedi", "pull_before_edit_missing · çağrı=[]",
                    f"{r.get('error')} · çağrı={s.cagri}", r.get("error") == "pull_before_edit_missing" and s.cagri == [])

    def test_2_kayit_var_canli_ayni_gecer_ve_kayit_guncellenir(self):
        s = self.istemci(Sahte(KAYNAK.replace("\n", "\r\n")))     # CRLF canlı ↔ LF kıyas normalize
        g = self.atom.adt_get(AD, TIP)
        k = self.durum().get(f"{TIP}:{AD}") or {}
        self.kaydet("adt_get kaynağı okuyunca kayıt yazılır", "pull_state=kaydedildi + sha",
                    f"{g.get('pull_state')} · sha={str(k.get('sha256'))[:12]}",
                    g.get("pull_state") == "kaydedildi" and k.get("sha256") == self.ps.ozet(KAYNAK))
        s.cagri.clear()
        yeni = KAYNAK + "WRITE 'yeni'.\n"
        r = self.atom.adt_push_source(AD, TIP, yeni)
        k2 = self.durum().get(f"{TIP}:{AD}") or {}
        ok = (r.get("ok") is True and s.cagri[:1] == ["download"] and "push" in s.cagri
              and s.cagri.index("download") < s.cagri.index("push"))
        self.kaydet("kayıt var + canlı aynı → push geçer (önce canlı okuma)", "ok · download<push",
                    f"ok={r.get('ok')} err={r.get('error')} çağrı={s.cagri}", ok)
        self.kaydet("push sonrası kayıt yeni canlı özetle güncellendi", "pull_state=guncellendi · sha=yeni",
                    f"{r.get('pull_state')} · eşit={k2.get('sha256') == self.ps.ozet(yeni)}",
                    r.get("pull_state") == "guncellendi" and k2.get("sha256") == self.ps.ozet(yeni))
        g2 = self.atom.adt_get(AD, TIP, include_source=False)
        self.assertNotIn("pull_state", g2)

    def test_3_kayit_var_canli_farkli_red(self):
        s = self.istemci(Sahte(KAYNAK))
        self.atom.adt_get(AD, TIP)
        s.canli = KAYNAK + "WRITE 'başkası değiştirdi'.\n"
        s.cagri.clear()
        r = self.atom.adt_push_source(AD, TIP, KAYNAK + "WRITE 'benim'.\n")
        self.kaydet("kayıt var + canlı farklı → red, push YOK", "source_changed_since_pull · push yok",
                    f"{r.get('error')} · çağrı={s.cagri}",
                    r.get("error") == "source_changed_since_pull" and "push" not in s.cagri)

    def test_4_canli_okuma_basarisiz_red(self):
        s = self.istemci(Sahte(KAYNAK))
        self.atom.adt_get(AD, TIP)
        s.okuma_hatasi = ConnectionError("bağlantı yok")
        s.cagri.clear()
        r = self.atom.adt_push_source(AD, TIP, KAYNAK + "WRITE 'x'.\n")
        self.kaydet("canlı okuma başarısız → sessiz geçiş YOK", "pull_live_read_failed · push yok",
                    f"{r.get('error')} · çağrı={s.cagri}",
                    r.get("error") == "pull_live_read_failed" and "push" not in s.cagri)

    def test_5_bozuk_durum_dosyasi(self):
        s = self.istemci(Sahte(KAYNAK))
        (self.p / ".axet-code").mkdir(exist_ok=True)
        (self.p / ".axet-code" / "sap-pull-state.json").write_text("{bozuk", encoding="utf-8")
        r = self.atom.adt_push_source(AD, TIP, KAYNAK)
        self.kaydet("bozuk pull-state dosyası → red", "pull_state_unreadable · çağrı=[]",
                    f"{r.get('error')} · çağrı={s.cagri}", r.get("error") == "pull_state_unreadable" and s.cagri == [])

    def test_6_post_shell_etkilenmez(self):
        s = self.istemci(Sahte(None))
        r = self.atom.adt_post_shell("program", "ZAXET_YENI", "$TMP", "TESTK900001", "Test programı")
        self.kaydet("adt_post_shell pull kontrolüne girmez", "ok · çağrı=[create]",
                    f"ok={r.get('ok')} · çağrı={s.cagri}", r.get("ok") is True and s.cagri == ["create"])


if __name__ == "__main__":
    unittest.main()
