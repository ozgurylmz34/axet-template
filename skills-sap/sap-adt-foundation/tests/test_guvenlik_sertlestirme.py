# -*- coding: utf-8 -*-
"""Z118 ⓐⓑ — bağlantı URL'si ayrıştırılamadığında temiz hata + transport ipucu metnindeki araç adı (çevrimdışı).

ⓐ `.conn_adt` / ortamdaki `ADT_SAP_URL` şablonda kalmış `<PORT>` taşırsa `urlparse(...).port` ValueError atar.
   Önceden: `redact.host_sirlari` (CLI `calistir`, `gate.log_write_attempt`, populate, screen) ve `gate.check_connection`
   (`_norm_url`) bunu yakalamıyordu → traceback (rc=1, stdout JSON'suz, log satırı yok). Beklenen: host yine maskelenir,
   kapı fail-closed `conn_env_mismatch` verir (değer basılmaz — `check_target_system` ile aynı sınır), CLI tek JSON basar.
ⓑ `require_transport` reddinin yönlendirdiği araç adı araç kayıt tablosunda GERÇEKTEN bulunan ad olmalı
   (istemci metodu `list_user_transports` bir araç değildir).

KAPSAM / BAKILMAYANLAR: yalnız port ayrıştırma hatası (ValueError) ölçüldü; bozuk IPv6 köşeli parantezi de aynı
istisna sınıfıdır ama burada ayrıca koşulmadı. Gerçek SAP'ye gidilmez (sahte host `127.0.0.1`).
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

BOZUK_URL = "http://127.0.0.1:<PORT>"      # şablonda kalmış yer tutucu (ui5-deploy.yaml vakasıyla aynı sınıf)
BOZUK_HOST = "sap-yer-tutucu.example.invalid"
S1 = ["--sap-write", "--scope", "S1", "--reason", "Z118 port yer tutucusu kapı testi"]

ROOT: Path
HOME: Path


def setUpModule():
    global ROOT, HOME
    ROOT = Path(tempfile.mkdtemp(prefix="axet_z118_"))
    HOME = H.build_home(ROOT, optin=True)


def tearDownModule():
    shutil.rmtree(ROOT, ignore_errors=True)


_sayac = [0]


def _proje(**kw) -> Path:
    _sayac[0] += 1
    return H.make_project(ROOT / "projeler", f"p{_sayac[0]}", **kw)


class HostSirlari(unittest.TestCase):
    def setUp(self):
        from sapadt import redact
        self.redact = redact

    def test_A1_yer_tutucu_port_istisna_vermez_host_maskelenir(self):
        url = f"https://{BOZUK_HOST}:<PORT>/sap/bc/adt"
        try:
            sirlar, exc = self.redact.host_sirlari(url), None
        except Exception as e:  # noqa: BLE001
            sirlar, exc = [], e
        metin = f"HTTPSConnectionPool(host='x'): {BOZUK_HOST}:<PORT> ulaşılamadı; {BOZUK_HOST}"
        temiz = self.redact.temizle_metin(metin, sirlar)
        ok = (exc is None and BOZUK_HOST in sirlar and f"{BOZUK_HOST}:<PORT>" in sirlar
              and BOZUK_HOST.lower() not in temiz.lower())
        H.kaydet("Z118a A1 host_sirlari <PORT> → istisna yok · host + ham host:port sır", "istisna yok · maskeli",
                 f"exc={type(exc).__name__ if exc else None} sirlar={sirlar} temiz={temiz!r}", ok)
        self.assertTrue(ok, f"{exc!r} {sirlar} {temiz!r}")

    def test_A1k_kontrol_gecerli_port_host_port_sir(self):
        sirlar = self.redact.host_sirlari(f"https://{BOZUK_HOST}:44300")
        ok = f"{BOZUK_HOST}:44300" in sirlar and BOZUK_HOST in sirlar
        H.kaydet("Z118a A1k KONTROL geçerli port → host ve host:port sır", "ikisi de", str(sirlar), ok)
        self.assertTrue(ok, sirlar)


class CheckConnection(unittest.TestCase):
    def setUp(self):
        from sapadt import gate
        self.gate = gate
        self._eski = os.environ.pop("ADT_SAP_URL", None)

    def tearDown(self):
        os.environ.pop("ADT_SAP_URL", None)
        if self._eski is not None:
            os.environ["ADT_SAP_URL"] = self._eski

    def _kos(self, proj, env_url):
        os.environ["ADT_SAP_URL"] = env_url
        try:
            return self.gate.check_connection(proj), None
        except Exception as e:  # noqa: BLE001
            return None, e

    def test_A2_ortam_url_yer_tutucu_fail_closed(self):
        r, exc = self._kos(_proje(), BOZUK_URL)
        ok = (exc is None and isinstance(r, tuple) and r[0] == "conn_env_mismatch"
              and "<PORT>" not in r[1] and "127.0.0.1" not in r[1])
        H.kaydet("Z118a A2 env ADT_SAP_URL <PORT> → conn_env_mismatch (değer basılmaz)", "conn_env_mismatch",
                 f"exc={exc!r} r={r}", ok)
        self.assertTrue(ok, f"{exc!r} {r}")

    def test_A2b_conn_adt_url_yer_tutucu_env_gecerli_fail_closed(self):
        r, exc = self._kos(_proje(extra_lines=(f"ADT_SAP_URL={BOZUK_URL}",)), H.SAHTE_URL)
        ok = exc is None and isinstance(r, tuple) and r[0] == "conn_env_mismatch" and "<PORT>" not in r[1]
        H.kaydet("Z118a A2b .conn_adt <PORT>, env geçerli → conn_env_mismatch", "conn_env_mismatch",
                 f"exc={exc!r} r={r}", ok)
        self.assertTrue(ok, f"{exc!r} {r}")

    def test_A2k_kontrol_ayni_url_gecer(self):
        r, exc = self._kos(_proje(), H.SAHTE_URL)
        H.kaydet("Z118a A2k KONTROL env = .conn_adt → None", "None", f"exc={exc!r} r={r}", exc is None and r is None)
        self.assertTrue(exc is None and r is None, f"{exc!r} {r}")


class CliUcanUca(unittest.TestCase):
    """Gerçek giriş noktası: alt süreçte `sap_adt_cli.py` (kopya AXET_HOME)."""

    def _kos(self, ad, argv, proj, env=None):
        rc, data, out, err = H.run_cli(HOME, argv, project=proj, env_extra=env)
        return rc, data, out, err

    def test_A3_conn_adt_yer_tutucu_okuma_tek_json_traceback_yok(self):
        p = _proje(extra_lines=(f"ADT_SAP_URL={BOZUK_URL}",))
        rc, data, out, err = self._kos("A3", ["adt_get", "--args-json", json.dumps({"name": "ZAXET_X"})], p)
        ok = (data is not None and "Traceback" not in err and rc in (1, 2) and data.get("ok") is False
              and "127.0.0.1" not in out and "<PORT>" not in out)    # hata metnindeki ham host:port da maskeli
        H.kaydet("Z118a A3 CLI .conn_adt <PORT> okuma → tek JSON · traceback yok · host yok", "JSON · rc 1|2",
                 f"rc={rc} code={((data or {}).get('error') or {}).get('code')} tb={'Traceback' in err}", ok)
        self.assertTrue(ok, f"rc={rc}\n{out}\n{err[-1500:]}")

    def test_A3b_conn_adt_yer_tutucu_yazma_log_satiri_yazilir(self):
        p = _proje(extra_lines=(f"ADT_SAP_URL={BOZUK_URL}",))
        rc, data, out, err = self._kos("A3b", ["adt_activate", "--args-json", json.dumps({"name": "ZAXET_X"}), *S1], p)
        log = p / ".axet-code" / "sap-write-log.jsonl"
        satirlar = log.read_text(encoding="utf-8").splitlines() if log.is_file() else []
        ok = (data is not None and "Traceback" not in err and rc in (1, 2) and satirlar
              and all("<PORT>" not in s and "127.0.0.1" not in s for s in satirlar))
        H.kaydet("Z118a A3b CLI .conn_adt <PORT> yazma → tek JSON · log satırı var · host yok", "JSON · log ≥1",
                 f"rc={rc} code={((data or {}).get('error') or {}).get('code')} log={len(satirlar)} "
                 f"tb={'Traceback' in err}", ok)
        self.assertTrue(ok, f"rc={rc} log={satirlar}\n{out}\n{err[-1500:]}")

    def test_A3c_env_yer_tutucu_kapi_red(self):
        p = _proje()
        rc, data, out, err = self._kos("A3c", ["adt_get", "--args-json", json.dumps({"name": "ZAXET_X"})], p,
                                       env={"ADT_SAP_URL": BOZUK_URL})
        kod = ((data or {}).get("error") or {}).get("code")
        ok = rc == 2 and kod == "conn_env_mismatch" and "Traceback" not in err
        H.kaydet("Z118a A3c CLI env ADT_SAP_URL <PORT> → exit 2 conn_env_mismatch", "2 · conn_env_mismatch",
                 f"rc={rc} code={kod} tb={'Traceback' in err}", ok)
        self.assertTrue(ok, f"rc={rc}\n{out}\n{err[-1500:]}")


class TransportIpucu(unittest.TestCase):
    def test_B1_transport_reddi_kayitli_arac_adini_gosterir(self):
        from sapadt._app import load_all_tools
        from sapadt.guardrails import GuardrailViolation, require_transport
        try:
            require_transport(None, what="adt_activate")
            mesaj = None
        except GuardrailViolation as gv:
            mesaj = str(gv)
        araclar = set(load_all_tools())
        ok = (mesaj is not None and "adt_transport_list" in mesaj and "adt_transport_list" in araclar
              and "list_user_transports" not in mesaj)
        H.kaydet("Z118b B1 transport reddi → kayıtlı araç adı adt_transport_list", "adt_transport_list",
                 str(mesaj), ok)
        self.assertTrue(ok, mesaj)


if __name__ == "__main__":
    unittest.main()
