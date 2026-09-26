#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""deploy_ui.py: yaml okuyucu, prepare (+/-), verify (+/-/OK~/kimliksiz), deploy RED yolları.

Gerçek deploy, npm ya da build KOŞULMAZ: prepare `--no-build` ile, deploy yalnız ret dallarında test edilir.
"""
from __future__ import annotations

import importlib.util
import unittest

import _helpers as H

S = "deploy_ui.py"


def _modul(ad, dosya):
    spec = importlib.util.spec_from_file_location(ad, H.SCRIPTS / dosya)
    m = importlib.util.module_from_spec(spec)
    import sys
    sys.path.insert(0, str(H.SCRIPTS))
    spec.loader.exec_module(m)
    return m


B = _modul("_bspnet_t", "_bspnet.py")
D = _modul("deploy_ui_t", "deploy_ui.py")
K = D.K  # deploy_ui'nin kullandığı _bspkaynak modülünün KENDİSİ
CANLI_VARSAYILAN = {"Component-preload.js": H.PRELOAD}  # sahte dist ile aynı ⇒ tam liste OK


def _canli_yol(name="ZXX001_ORDER"):
    return f"/sap/bc/ui5_ui5/sap/{name.lower()}/Component-preload.js"


class TestYaml(unittest.TestCase):
    def test_deploy_ayari(self):
        app = H.gecici_app(url="https://sap-demo.invalid:44300")
        try:
            a = B.deploy_ayari(app)
            ok = (a["gorev"] and a["url"] == "https://sap-demo.invalid:44300" and a["client"] == "100"
                  and a["name"] == "ZXX001_ORDER" and a["package"] == "ZXX001" and a["transport"] == "ZXXK900001"
                  and a["exclude"] == ["/test/"] and a["resources_excludes"] == ["/test/**", "/localService/**"])
            H.kaydet("yaml: 2. görevdeki deploy-to-abap + yorum/tırnak", "alanlar doğru", str(ok), ok)
            self.assertTrue(ok, a)
        finally:
            H.temizle(app)


class TestYamlNullYorum(unittest.TestCase):
    """Z106 bug gate: tırnaksız null/~ ve yalnız-yorum değer BOŞ okunmalı (PyYAML: None); tırnaklı hâli dizedir."""

    def _transport(self, ham: str) -> str:
        sk, _ = B.yaml_duzlestir(f"app:\n  transport: {ham}\n  package: ZXX001\n")
        return sk.get("app.transport", "")

    def test_yorum_todo_bos(self):
        deger = self._transport("# TODO transport gir")
        H.kaydet("yaml: `transport: # TODO` → boş", "''", repr(deger), deger == "")
        self.assertEqual(deger, "")

    def test_null_bos(self):
        sonuc = {v: self._transport(v) for v in ("null", "Null", "NULL")}
        ok = all(x == "" for x in sonuc.values())
        H.kaydet("yaml: null/Null/NULL → boş", "hepsi ''", str(sonuc), ok)
        self.assertTrue(ok, sonuc)

    def test_tilde_bos(self):
        deger = self._transport("~")
        H.kaydet("yaml: `~` → boş", "''", repr(deger), deger == "")
        self.assertEqual(deger, "")

    def test_kontrol_grubu_tirnakli_ve_satir_sonu_yorumu(self):
        sonuc = (self._transport("'null'"), self._transport('"~"'), self._transport("ZXXK900001   # yorum"),
                 self._transport("nullable"))
        ok = sonuc == ("null", "~", "ZXXK900001", "nullable")
        H.kaydet("yaml: tırnaklı null/~ dize kalır, satır sonu yorumu düşer", "null/~/ZXXK900001/nullable",
                 str(sonuc), ok)
        self.assertTrue(ok, sonuc)

    def test_yorumlu_ust_anahtar_alt_eslemeyi_bozmaz(self):
        """`app:   # açıklama` → alt anahtarlar yine app.* altında okunur (skaler '# açıklama' sanılmaz)."""
        app = H.gecici_app()
        try:
            y = app / "ui5-deploy.yaml"
            y.write_text(y.read_text(encoding="utf-8").replace("        app:\n", "        app:   # kullanıcı verir\n"),
                         encoding="utf-8")
            a = B.deploy_ayari(app)
            ok = a["name"] == "ZXX001_ORDER" and a["package"] == "ZXX001" and a["transport"] == "ZXXK900001"
            H.kaydet("yaml: yorumlu üst anahtar altındaki alanlar okunur", "ad/paket/transport dolu", str(ok), ok)
            self.assertTrue(ok, a)
        finally:
            H.temizle(app)


class TestPreloadKiyas(unittest.TestCase):
    def test_siniflar(self):
        crlf = H.PRELOAD.replace(rb">\n<", rb">\r\n<")
        gercek_crlf = H.PRELOAD.replace(b"\n", b"\r\n")
        farkli = H.PRELOAD.replace(b"return 1;", b"return 2;")
        s1 = D.preload_karsilastir(H.PRELOAD, gercek_crlf)[0]
        s2 = D.preload_karsilastir(H.PRELOAD, crlf)[0]
        s3 = D.preload_karsilastir(H.PRELOAD, farkli)[0]
        ok = (s1, s2, s3) == ("AYNI", "SATIR_SONU", "FARKLI")
        H.kaydet("preload: gerçek CRLF=AYNI · kaçışlı=SATIR_SONU · JS=FARKLI", "AYNI/SATIR_SONU/FARKLI",
                 f"{s1}/{s2}/{s3}", ok)
        self.assertTrue(ok)


class TestPrepare(unittest.TestCase):
    def test_pozitif(self):
        app = H.gecici_app()
        try:
            rc, out = H.kos(S, "prepare", app, "--no-build")
            ok = rc == 0 and "[HAZIR] BSP=ZXX001_ORDER" in out and "DEPLOY KOMUTU (KOŞULMADI)" in out \
                and "[İHLAL]" not in out and ".eslintrc" not in out and "BAKILMAYANLAR" in out
            H.kaydet("prepare: temiz uygulama → HAZIR + komut basılır", "rc=0", f"rc={rc}", ok)
            self.assertTrue(ok, out)
        finally:
            H.temizle(app)

    def test_negatif(self):
        app = H.gecici_app(name="ZXX001_ORDER_APPLICATION", dist_taze=False)
        try:
            (app / "webapp" / ".axet-code").mkdir()
            (app / "webapp" / ".axet-code" / "notes.txt").write_text("x", encoding="utf-8")
            (app / "webapp" / "img").mkdir()
            (app / "webapp" / "img" / "logo.svg").write_text("<svg/>", encoding="utf-8")
            rc, out = H.kos(S, "prepare", app, "--no-build")
            beklenen = ["en çok 15", "gizli/stray dosya", "logo.svg: BSP bu uzantıyı tanımaz", "dist BAYAT",
                        "Deploy'a HAZIR DEĞİL"]
            eksik = [b for b in beklenen if b not in out]
            ok = rc == 1 and not eksik and "DEPLOY KOMUTU" not in out
            H.kaydet("prepare: uzun BSP adı + stray + .svg + bayat dist", "rc=1", f"rc={rc} eksik={eksik}", ok)
            self.assertTrue(ok, out)
        finally:
            H.temizle(app)

    def _prepare(self, paket, transport):
        app = H.gecici_app()
        try:
            _paket_tr(app, paket, transport)
            return H.kos(S, "prepare", app, "--no-build")
        finally:
            H.temizle(app)

    def test_kucuk_tmp_uyari_deploy_reddeder(self):
        """prepare kanonik kurala hizalı: `$tmp` + transport yok → UYARI 'deploy bunu REDDEDER'."""
        rc, out = self._prepare("$tmp", None)
        ok = rc == 0 and "[UYARI] app.transport boş" in out and "REDDEDER" in out and "TAM `$TMP` değil" in out
        H.kaydet("prepare: $tmp + transport yok → 'deploy REDDEDER' uyarısı", "rc=0 UYARI", f"rc={rc}", ok)
        self.assertTrue(ok, out)

    def test_buyuk_tmp_uyari_yok(self):
        """KONTROL GRUBU: `$TMP` + transport yok → transport uyarısı YOK."""
        rc, out = self._prepare("$TMP", None)
        ok = rc == 0 and "app.transport boş" not in out and "[HAZIR]" in out
        H.kaydet("prepare: $TMP + transport yok → uyarı yok", "rc=0 HAZIR", f"rc={rc}", ok)
        self.assertTrue(ok, out)

    def test_paket_yalniz_bosluk_ihlal(self):
        rc, out = self._prepare('" "', "ZXXK900001")
        ok = rc == 1 and "alanı boş: package" in out
        H.kaydet("prepare: package ' ' → İHLAL", "rc=1", f"rc={rc}", ok)
        self.assertTrue(ok, out)

    def test_yaml_yok(self):
        app = H.gecici_app()
        try:
            (app / "ui5-deploy.yaml").unlink()
            rc, out = H.kos(S, "prepare", app, "--no-build")
            ok = rc == 1 and "ui5-deploy.yaml yok" in out
            H.kaydet("prepare: ui5-deploy.yaml yok → ihlal", "rc=1", f"rc={rc}", ok)
            self.assertTrue(ok, out)
        finally:
            H.temizle(app)


class TestVerify(unittest.TestCase):
    def _kos(self, canli: bytes | None, kimlik=True):
        dosyalar = {} if canli is None else {_canli_yol(): canli}
        with H.SahteSunucu(dosyalar) as srv:
            app = H.gecici_app(url=srv.url)
            try:
                return H.kos(S, "verify", app, kimlik=kimlik)
            finally:
                H.temizle(app)

    def test_pozitif_crlf(self):
        rc, out = self._kos(H.PRELOAD.replace(b"\n", b"\r\n"))
        ok = rc == 0 and "[OK]" in out and "CANLI == dist" in out and H.PAROLA not in out
        H.kaydet("verify: canlı (CRLF bayt) == dist → OK, parola basılmaz", "rc=0", f"rc={rc}", ok)
        self.assertTrue(ok, out)

    def test_ok_tilda(self):
        rc, out = self._kos(H.PRELOAD.replace(rb">\n<", rb">\r\n<"))
        ok = rc == 0 and "[OK~]" in out
        H.kaydet("verify: yalnız kaçışlı \\r\\n farkı → OK~", "rc=0 OK~", f"rc={rc}", ok)
        self.assertTrue(ok, out)

    def test_negatif_stale(self):
        rc, out = self._kos(H.PRELOAD.replace(b"return 1;", b"return 2;"))
        ok = rc == 1 and "[STALE]" in out and "Farklı modül" in out
        H.kaydet("verify: canlı JS farklı → STALE", "rc=1", f"rc={rc}", ok)
        self.assertTrue(ok, out)

    def test_canlida_yok(self):
        rc, out = self._kos(None)
        ok = rc == 2 and "[ÖLÇÜLEMEDİ]" in out and "HTTPError 404" in out
        H.kaydet("verify: canlıda dosya yok → ÖLÇÜLEMEDİ", "rc=2", f"rc={rc}", ok)
        self.assertTrue(ok, out)

    def test_kimliksiz(self):
        rc, out = self._kos(H.PRELOAD, kimlik=False)
        ok = rc == 2 and "set değil" in out
        H.kaydet("verify: env kimlik yok → ÖLÇÜM YOK", "rc=2", f"rc={rc}", ok)
        self.assertTrue(ok, out)

    def test_kati_mod_kacis_stale(self):
        H.proxy_bypass_surec_ici()
        with H.SahteSunucu({_canli_yol(): H.PRELOAD.replace(rb">\n<", rb">\r\n<")}) as srv:
            app = H.gecici_app(url=srv.url)
            try:
                durum, _ = D.canli_dogrula(app, B.deploy_ayari(app), (H.KULLANICI, H.PAROLA), False, kati=True)
            finally:
                H.temizle(app)
        ok = durum == "STALE"
        H.kaydet("deploy sonrası KATI kıyas: kaçış farkı da STALE", "STALE", durum, ok)
        self.assertTrue(ok)


class TestDeployRed(unittest.TestCase):
    def test_onaysiz_red(self):
        app = H.gecici_app()
        try:
            rc, out = H.kos(S, "deploy", app, kimlik=True)
            ok = rc == 3 and "[REDDEDİLDİ] --user-ok" in out and "build:" not in out
            H.kaydet("deploy: --user-ok yok → REDDEDİLDİ, build bile yok", "rc=3", f"rc={rc}", ok)
            self.assertTrue(ok, out)
        finally:
            H.temizle(app)

    def test_yer_tutucu_onay_red(self):
        app = H.gecici_app()
        try:
            rc, out = H.kos(S, "deploy", app, "--user-ok", "<kullanıcının onay cümlesi>", kimlik=True)
            ok = rc == 3 and "REDDEDİLDİ" in out
            H.kaydet("deploy: yer tutucu onay metni → REDDEDİLDİ", "rc=3", f"rc={rc}", ok)
            self.assertTrue(ok, out)
        finally:
            H.temizle(app)

    def test_kimliksiz_red(self):
        app = H.gecici_app()
        try:
            rc, out = H.kos(S, "deploy", app, "--user-ok", "Kullanıcı: lokal test tamam, deploy et")
            ok = rc == 3 and "set değil" in out and "build:" not in out
            H.kaydet("deploy: onay var, env kimlik yok → REDDEDİLDİ", "rc=3", f"rc={rc}", ok)
            self.assertTrue(ok, out)
        finally:
            H.temizle(app)


# ── Z106: SAP YAZMA KAPISI (sap_adt_cli ile AYNI `gate.check_write`) ──────────────────────────────
# Gerçek `<repo>/config/` altına dosya YAZILMAZ: kapı AXET_HOME'u kendi konumundan türettiği için alt süreç
# testleri script ağaçlarını geçici bir AXET_HOME'a kopyalar (sap-adt-foundation testleriyle aynı yöntem).
# Süreç içi testler `gate.optin_file`'ı geçici dosyaya yönlendirir (test_populate_hat.py:158 ile aynı yöntem).
# `.conn_adt` fixture'ları sahte, çalışma anında tempfile altında üretilir; SAP yerine 127.0.0.1 sahte sunucusu.

import argparse  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402
from pathlib import Path  # noqa: E402
from unittest import mock  # noqa: E402

SKILLS_SAP = H.SKILL.parent
FOUNDATION_SCRIPTS = SKILLS_SAP / "sap-adt-foundation" / "scripts"
ONAY = "Kullanıcı: lokal test tamam, deploy et"
GEREKCE = "Birim test: deploy yazma kapısı ölçümü"
_YOKSAY = shutil.ignore_patterns("__pycache__", "*.pyc", "node_modules")


def _home(kok: Path, optin: bool, foundation: bool = True) -> Path:
    """Geçici AXET_HOME. `foundation=False` → sap-adt-foundation KOPYALANMAZ (kapı yüklenemez senaryosu)."""
    home = kok / (("home_acik" if optin else "home_kapali") + ("" if foundation else "_kapisiz"))
    skiller = ("sap-ui5-fiori", "sap-adt-foundation", "sap-intake-triage") if foundation else ("sap-ui5-fiori",)
    for skill in skiller:
        shutil.copytree(SKILLS_SAP / skill / "scripts", home / "skills-sap" / skill / "scripts", ignore=_YOKSAY)
    (home / "config").mkdir(parents=True, exist_ok=True)
    if optin:
        (home / "config" / "sap-write.local").write_text("test opt-in\n", encoding="utf-8")
    return home


def _proje(kok: Path, ad: str, url: str, *, tier=("ADT_SAP_TIER=DEV",), client="100", sap_project=True) -> Path:
    p = kok / ad
    p.mkdir(parents=True)
    satirlar = ["# test fixture — sahte sistem", f"ADT_SAP_URL={url}", "ADT_SAP_USER=AXETTEST",
                "ADT_SAP_PASSWORD=S3cr3t-Parola!9", f"ADT_SAP_CLIENT={client}", "ADT_SAP_LANGUAGE=TR", *tier]
    (p / ".conn_adt").write_text("\n".join(satirlar) + "\n", encoding="utf-8")
    if sap_project:
        (p / "sap-project.json").write_text(json.dumps({"sap_profile": "s4_private", "release": "2025",
                                                        "master_language": "TR"}), encoding="utf-8")
    return p


def _ortam(kimlik: bool = True) -> dict:
    # PYTHONPATH da düşülür: gerçek sap-adt-foundation'a giden bir yol "kapı yüklenemez" senaryosunu sessizce bozardı.
    return {k: v for k, v in H.ortam(kimlik).items()
            if not k.upper().startswith(("ADT_", "AXET_")) and k.upper() != "PYTHONPATH"}


def _kos_home(home: Path, *args, cwd=None, kimlik: bool = True) -> tuple[int, str]:
    betik = home / "skills-sap" / "sap-ui5-fiori" / "scripts" / "deploy_ui.py"
    p = subprocess.run([sys.executable, str(betik), *map(str, args)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=_ortam(kimlik), timeout=180,
                       cwd=str(cwd) if cwd else None, stdin=subprocess.DEVNULL)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


_PAKET_TR_SATIRLARI = "          package: ZXX001\n          transport: ZXXK900001\n"


def _paket_tr(app: Path, paket: str, transport: str | None) -> None:
    """ui5-deploy.yaml `app.package`/`app.transport`'u değiştirir; transport=None → satır HİÇ yok."""
    y = app / "ui5-deploy.yaml"
    metin = y.read_text(encoding="utf-8")
    assert _PAKET_TR_SATIRLARI in metin, "fixture değişti: paket/transport satırları bulunamadı"
    yeni = f"          package: {paket}\n" + (f"          transport: {transport}\n" if transport is not None else "")
    y.write_text(metin.replace(_PAKET_TR_SATIRLARI, yeni), encoding="utf-8")


def _son_log(proj: Path) -> dict | None:
    f = proj / ".axet-code" / "sap-write-log.jsonl"
    if not f.is_file():
        return None
    satirlar = [s for s in f.read_text(encoding="utf-8").splitlines() if s.strip()]
    return json.loads(satirlar[-1]) if satirlar else None


class TestDeployYazmaKapisi(unittest.TestCase):
    """Alt süreç (GERÇEK giriş noktası): kapı reddinde build de deploy da koşmaz.

    NE ÖLÇÜLÜR (dürüst kapsam): asıl sinyal ① çıktıda `build:` satırı YOK (build adımı `hazirla` içinde basılır,
    kapıdan sonra gelir) ② rc=3 + red kodu ③ write-log'daki sonuç kodu. `istekler == []` bu sınıfta ZAYIF bir
    sinyaldir: sahte sunucu yalnız `do_GET` sayar ve test ortamında `ui5`/`fiori` kurulu olmadığından kapı açık
    olsa bile build düşer, deploy (POST/PUT — sayılmaz) ve canlı doğrulama GET'i hiç olmaz ⇒ burada boş liste
    kapının kanıtı DEĞİLDİR. "Kapı reddinde hiçbir alt süreç koşmadı" kanıtı süreç içi sınıftadır
    (`TestDeployKapiSurecIci`: `run` sahte, `cagrilar == []`; kontrol grubunda istek sayısı 1)."""

    @classmethod
    def setUpClass(cls):
        cls.kok = Path(tempfile.mkdtemp(prefix="ui5kapi_"))
        cls.kapali = _home(cls.kok, optin=False)
        cls.acik = _home(cls.kok, optin=True)
        cls.kapisiz = _home(cls.kok, optin=True, foundation=False)
        cls.sayac = 0

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.kok, ignore_errors=True)

    def _deploy(self, home, *, tier=("ADT_SAP_TIER=DEV",), conn_url=None, client="100", sap_write=True,
                sap_project=True, ek=(), app_url=None, paket_tr=None):
        type(self).sayac += 1
        with H.SahteSunucu({_canli_yol(): H.PRELOAD}) as srv:
            app = H.gecici_app(url=app_url or srv.url)
            if paket_tr:
                _paket_tr(app, *paket_tr)
            proj = _proje(self.kok, f"proje{self.sayac}", conn_url or srv.url, tier=tier, client=client,
                          sap_project=sap_project)
            try:
                argv = ["deploy", app, "--user-ok", ONAY, "--scope", "S1", "--reason", GEREKCE,
                        "--project-dir", proj, *ek]
                if sap_write:
                    argv.insert(4, "--sap-write")
                rc, out = _kos_home(home, *argv)
                return rc, out, list(srv.istekler), proj
            finally:
                H.temizle(app)

    def _red(self, ad, home, kod, **kw):
        rc, out, istekler, proj = self._deploy(home, **kw)
        log = _son_log(proj) or {}
        ok = (rc == 3 and "[REDDEDİLDİ] SAP yazma kapısı" in out and kod in out and "build:" not in out
              and istekler == [] and log.get("tool") == "deploy_ui" and log.get("result") == kod)
        H.kaydet(f"deploy kapı: {ad}", f"rc=3 {kod} istek=0", f"rc={rc} istek={len(istekler)} log={log.get('result')}", ok)
        self.assertTrue(ok, f"rc={rc} istekler={istekler} log={log}\n{out}")

    def test_kapi_anahtar_kapali(self):
        self._red("anahtar (sap-write.local) yok → red", self.kapali, "write_not_optin_global")

    def test_kapi_sap_write_bayragi_yok(self):
        self._red("--sap-write yok → red", self.acik, "write_flag_missing", sap_write=False)

    def test_kapi_tier_qa(self):
        self._red("tier QA → red", self.acik, "tier_not_writable", tier=("ADT_SAP_TIER=QA",))

    def test_kapi_tier_prd(self):
        self._red("tier PRD → red", self.acik, "tier_not_writable", tier=("ADT_SAP_TIER=PRD",))

    def test_kapi_tier_okunamaz(self):
        self._red("tier satırı yok (UNKNOWN) → red", self.acik, "tier_not_writable", tier=())

    def test_kapi_tier_cakisik(self):
        self._red("tier çakışık DEV+PRD → red", self.acik, "tier_not_writable",
                  tier=("ADT_SAP_TIER=DEV", "ADT_SAP_TIER=PRD"))

    def test_kapi_sap_project_yok(self):
        self._red("sap-project.json yok → red", self.acik, "sap_project_missing", sap_project=False)

    def test_kapi_hedef_url_farkli(self):
        self._red("ui5-deploy.yaml url ≠ .conn_adt → red", self.acik, "write_target_mismatch",
                  conn_url="http://127.0.0.1:9")

    def test_kapi_hedef_client_farkli(self):
        self._red("ui5-deploy.yaml client ≠ .conn_adt → red", self.acik, "write_target_mismatch", client="200")

    def test_kapi_hedef_port_yer_tutucu(self):
        """Şablondaki `<PORT>` kalmış → urlparse ValueError. Traceback (rc=1, logsuz) DEĞİL: fail-closed red + log."""
        rc, out, istekler, proj = self._deploy(self.acik, app_url="https://127.0.0.1:<PORT>")
        log = _son_log(proj) or {}
        ok = (rc == 3 and "[REDDEDİLDİ] SAP yazma kapısı (write_target_mismatch)" in out
              and "ayrıştırılamadı" in out and "Traceback" not in out and "build:" not in out
              and log.get("tool") == "deploy_ui" and log.get("result") == "write_target_mismatch"
              and log.get("exit_code") == 3)
        H.kaydet("deploy kapı: ui5-deploy.yaml url'de <PORT> → red (traceback yok)", "rc=3 write_target_mismatch",
                 f"rc={rc} log={log.get('result')}", ok)
        self.assertTrue(ok, f"rc={rc} log={log}\n{out}")

    def test_kapi_yuklenemez_gate_unavailable(self):
        """AXET_HOME'da sap-adt-foundation YOK → kapı import edilemez → fail-closed red (rc=3), build yok.
        Log yazıcısı kapı modülünde olduğundan bu red write-log'a DÜŞMEZ (dokümanda yazılı istisna) — ölçülür."""
        rc, out, istekler, proj = self._deploy(self.kapisiz)
        log = _son_log(proj)
        ok = (rc == 3 and "[REDDEDİLDİ] SAP yazma kapısı (gate_unavailable)" in out and "build:" not in out
              and "Traceback" not in out and log is None)
        H.kaydet("deploy kapı: foundation yok → gate_unavailable (fail-closed)", "rc=3 gate_unavailable log=yok",
                 f"rc={rc} log={log}", ok)
        self.assertTrue(ok, f"rc={rc} log={log}\n{out}")

    # ── Transport zorunluluğu (Kesin Yasak C; kanonik `guardrails.require_transport`, kod ADR_0005_C) ──
    def test_transport_z_paket_transport_yok_red(self):
        self._red("Z paket + app.transport satırı yok → red", self.acik, "ADR_0005_C", paket_tr=("ZXX001", None))

    def test_transport_z_paket_transport_bos_red(self):
        self._red("Z paket + app.transport '' → red", self.acik, "ADR_0005_C", paket_tr=("ZXX001", "''"))

    def test_transport_z_paket_yer_tutucu_red(self):
        """`<TRANSPORT_NO>` şablondan kalmış: require_transport yalnız boşluğa bakar → deploy_ui yer tutucuyu yok sayar."""
        self._red("Z paket + app.transport <TRANSPORT_NO> → red", self.acik, "ADR_0005_C",
                  paket_tr=("ZXX001", "<TRANSPORT_NO>"))

    def test_transport_kucuk_tmp_red(self):
        """`$tmp` istisna DEĞİL (kanonik kural `$TMP` TAM eşleşme; test_cli_gate.py:224 ile aynı yön, fail-closed)."""
        self._red("paket $tmp (küçük harf) + transport yok → red", self.acik, "ADR_0005_C", paket_tr=("$tmp", None))

    def test_transport_yorum_todo_red(self):
        self._red("Z paket + `transport: # TODO transport gir` → red", self.acik, "ADR_0005_C",
                  paket_tr=("ZXX001", "# TODO transport gir"))

    def test_transport_null_red(self):
        self._red("Z paket + `transport: null` → red", self.acik, "ADR_0005_C", paket_tr=("ZXX001", "null"))

    def test_transport_tilde_red(self):
        self._red("Z paket + `transport: ~` → red", self.acik, "ADR_0005_C", paket_tr=("ZXX001", "~"))

    def test_transport_yalniz_bosluk_red(self):
        self._red("Z paket + `transport: \" \"` → red", self.acik, "ADR_0005_C", paket_tr=("ZXX001", '" "'))

    def test_paket_yalniz_bosluk_red(self):
        """Bug gate (fail-OPEN, rc=0 ölçüldü): `package: " "` + geçerli transport → kapıda red, build yok."""
        self._red("`package: \" \"` + transport var → red", self.acik, "ADR_0005_C", paket_tr=('" "', "ZXXK900001"))

    def test_paket_bos_red(self):
        """Tamamen boş paket de KAPIDA red (eskiden build SONRASI prepare_failed idi)."""
        self._red("`package:` boş + transport var → red", self.acik, "ADR_0005_C", paket_tr=("", "ZXXK900001"))

    def test_paket_null_red(self):
        self._red("`package: null` + transport var → red", self.acik, "ADR_0005_C", paket_tr=("null", "ZXXK900001"))

    def test_paket_yer_tutucu_red(self):
        self._red("`package: <SAP_PAKET>` + transport var → red", self.acik, "ADR_0005_C",
                  paket_tr=("<SAP_PAKET>", "ZXXK900001"))

    def test_transport_red_kodu_bir_kez(self):
        rc, out, istekler, proj = self._deploy(self.acik, paket_tr=("ZXX001", None))
        ok = rc == 3 and "SAP yazma kapısı (ADR_0005_C): " in out and "[ADR_0005_C]" not in out
        H.kaydet("deploy kapı: red satırında kod bir kez", "(ADR_0005_C) var, [ADR_0005_C] yok", f"rc={rc}", ok)
        self.assertTrue(ok, out)

    def test_transport_red_mesaji_nereye_yazilacagini_soyler(self):
        rc, out, istekler, proj = self._deploy(self.acik, paket_tr=("ZXX001", None))
        ok = rc == 3 and "app.transport" in out and "ui5-deploy.yaml" in out and "KULLANICI verir" in out
        H.kaydet("deploy kapı: transport reddi ne eksik/nereye yazılır söyler", "app.transport + ui5-deploy.yaml",
                 f"rc={rc}", ok)
        self.assertTrue(ok, out)

    def test_kapi_salt_okur_etkilenmez(self):
        """prepare (ağsız) ve verify (salt GET) kapıdan GEÇMEZ: anahtar kapalı + proje yokken de çalışır."""
        bos = self.kok / "projesiz_cwd"
        bos.mkdir(exist_ok=True)
        with H.SahteSunucu({_canli_yol(): H.PRELOAD}) as srv:
            app = H.gecici_app(url=srv.url)
            try:
                rc1, out1 = _kos_home(self.kapali, "prepare", app, "--no-build", cwd=bos, kimlik=False)
                rc2, out2 = _kos_home(self.kapali, "verify", app, cwd=bos)
            finally:
                H.temizle(app)
        ok = (rc1 == 0 and "[HAZIR]" in out1 and "--sap-write" in out1 and rc2 == 0 and "[OK]" in out2
              and "REDDEDİLDİ" not in out1 + out2)
        H.kaydet("deploy kapı: prepare/verify kapıdan etkilenmez", "rc=0/0", f"rc={rc1}/{rc2}", ok)
        self.assertTrue(ok, out1 + "\n" + out2)


class TestDeployKapiSurecIci(unittest.TestCase):
    """Süreç içi: build/deploy alt süreci SAHTE (`run` kaydedilir), canlı doğrulama 127.0.0.1 sahte sunucusu.
    Kapı reddinde `run` çağrı sayısı 0 ve sahte SAP'ye istek 0; kapı açık + DEV'de mevcut akış uçtan uca geçer.
    Burada `istekler == []` ANLAMLIDIR: `run` sahte "Deployment Successful" döndüğü için kapı açık olsaydı canlı
    doğrulama GET'i atılırdı — kontrol grubu (`test_kapi_acik_dev_akis_calisir`) bunu istek=2 ile ölçer
    (preload + Z144 tam liste OData zip'i).
    Ölçülmeyen: gerçek `fiori deploy`'un POST/PUT'u (sahte sunucu yalnız GET sayar; deploy alt süreci sahte)."""

    def setUp(self):
        H.proxy_bypass_surec_ici()
        self.kok = Path(tempfile.mkdtemp(prefix="ui5kapi_ic_"))
        if str(FOUNDATION_SCRIPTS) not in sys.path:
            sys.path.insert(0, str(FOUNDATION_SCRIPTS))
        from sapadt import gate
        self.gate = gate
        self.optin = self.kok / "config" / "sap-write.local"
        self.eski_optin = gate.optin_file
        gate.optin_file = lambda axet_home=None: self.optin
        temiz = {k: v for k, v in os.environ.items() if not k.upper().startswith(("ADT_", "AXET_"))}
        temiz.update(FIORI_TOOLS_USER=H.KULLANICI, FIORI_TOOLS_PASSWORD=H.PAROLA)
        self.env = mock.patch.dict(os.environ, temiz, clear=True)
        self.env.start()
        self.cagrilar: list[str] = []

    def tearDown(self):
        self.env.stop()
        self.gate.optin_file = self.eski_optin
        shutil.rmtree(self.kok, ignore_errors=True)

    def _sahte_run(self, cmd, cwd, env):
        self.cagrilar.append(cmd)
        if cmd == D.DEPLOY_KOMUTU:
            return 0, "info deploy-to-abap Deployment Successful.\n"
        return 0, "build ok\n"

    def _kos(self, *, optin: bool, tier=("ADT_SAP_TIER=DEV",), paket_tr=None, canli=CANLI_VARSAYILAN, anlik=None,
             kontrol=None):
        """canli: sahte OData zip'inin dosyaları (None → servis yok, 404) · anlik: `.canli/` anlık görüntüsü
        (None → yok) · kontrol(app): uygulama silinmeden önce çağrılır (anlık görüntü güncellendi mi ölçmek için)."""
        if optin:
            self.optin.parent.mkdir(parents=True, exist_ok=True)
            self.optin.write_text("x", encoding="utf-8")
        sunulan = {_canli_yol(): H.PRELOAD}
        if canli is not None:
            sunulan[H.odata_yol()] = H.odata_zip(canli)
        with H.SahteSunucu(sunulan) as srv:
            app = H.gecici_app(url=srv.url)
            if paket_tr:
                _paket_tr(app, *paket_tr)
            if anlik is not None:
                K.anlik_yaz(app, anlik, {"bsp": "ZXX001_ORDER"})
            proj = _proje(self.kok, "proje", srv.url, tier=tier)
            a = argparse.Namespace(app=str(app), user_ok=ONAY, ignore_cert=False, sap_write=True, scope="S1",
                                   reason=GEREKCE, intake=None, project_dir=str(proj))
            try:
                with mock.patch.object(D, "run", self._sahte_run):
                    rc = D.komut_deploy(a)
                if kontrol:
                    kontrol(app)
            finally:
                H.temizle(app)
            return rc, list(srv.istekler), proj

    def test_kapi_kapali_run_ve_istek_sifir(self):
        rc, istekler, proj = self._kos(optin=False)
        ok = rc == 3 and self.cagrilar == [] and istekler == []
        H.kaydet("deploy kapı (süreç içi): anahtar kapalı → run=0 istek=0", "rc=3 0/0",
                 f"rc={rc} run={len(self.cagrilar)} istek={len(istekler)}", ok)
        self.assertTrue(ok, f"rc={rc} run={self.cagrilar} istek={istekler}")

    def test_kapi_tier_prd_run_ve_istek_sifir(self):
        rc, istekler, proj = self._kos(optin=True, tier=("ADT_SAP_TIER=PRD",))
        ok = rc == 3 and self.cagrilar == [] and istekler == []
        H.kaydet("deploy kapı (süreç içi): tier PRD → run=0 istek=0", "rc=3 0/0",
                 f"rc={rc} run={len(self.cagrilar)} istek={len(istekler)}", ok)
        self.assertTrue(ok, f"rc={rc} run={self.cagrilar} istek={istekler}")

    def test_kapi_acik_dev_akis_calisir(self):
        """KONTROL GRUBU: anahtar açık + DEV + hedef == .conn_adt → build + deploy + canlı doğrulama (rc 0)."""
        rc, istekler, proj = self._kos(optin=True)
        log = _son_log(proj) or {}
        ok = (rc == 0 and self.cagrilar == [D.BUILD_KOMUTU, D.DEPLOY_KOMUTU] and len(istekler) == 2
              and log.get("tool") == "deploy_ui" and log.get("result") == "ok" and log.get("exit_code") == 0)
        H.kaydet("deploy kapı (süreç içi): açık + DEV → akış çalışır", "rc=0 build+deploy",
                 f"rc={rc} run={len(self.cagrilar)} istek={len(istekler)} log={log.get('result')}", ok)
        self.assertTrue(ok, f"rc={rc} run={self.cagrilar} istek={istekler} log={log}")

    def test_transport_tmp_transportsuz_akis_calisir(self):
        """KONTROL GRUBU (transport): paket `$TMP` + transport satırı yok → kapıdan geçer, build + deploy koşar."""
        rc, istekler, proj = self._kos(optin=True, paket_tr=("$TMP", None))
        log = _son_log(proj) or {}
        ok = (rc == 0 and self.cagrilar == [D.BUILD_KOMUTU, D.DEPLOY_KOMUTU] and len(istekler) == 2
              and log.get("result") == "ok")
        H.kaydet("deploy kapı (süreç içi): $TMP + transport yok → akış çalışır", "rc=0 build+deploy",
                 f"rc={rc} run={len(self.cagrilar)} log={log.get('result')}", ok)
        self.assertTrue(ok, f"rc={rc} run={self.cagrilar} istek={istekler} log={log}")

    def test_paket_yalniz_bosluk_run_ve_istek_sifir(self):
        rc, istekler, proj = self._kos(optin=True, paket_tr=('" "', "ZXXK900001"))
        log = _son_log(proj) or {}
        ok = rc == 3 and self.cagrilar == [] and istekler == [] and log.get("result") == "ADR_0005_C"
        H.kaydet("deploy kapı (süreç içi): package ' ' → run=0 istek=0", "rc=3 0/0 ADR_0005_C",
                 f"rc={rc} run={len(self.cagrilar)} istek={len(istekler)} log={log.get('result')}", ok)
        self.assertTrue(ok, f"rc={rc} run={self.cagrilar} istek={istekler} log={log}")

    def test_yerel_paket_sabiti_kanonikle_ayni(self):
        """prepare uyarısındaki `$TMP` sabiti foundation'ın kanonik `guardrails.YEREL_PAKET`'i ile aynı."""
        from sapadt import guardrails
        ok = D.YEREL_PAKET == guardrails.YEREL_PAKET
        H.kaydet("deploy_ui.YEREL_PAKET == guardrails.YEREL_PAKET", guardrails.YEREL_PAKET, D.YEREL_PAKET, ok)
        self.assertTrue(ok)

    # ── Z144: deploy SONRASI tam liste + deploy ÖNCESİ drift ─────────────────────────────────────
    def test_tam_liste_fark_stale(self):
        """Canlı preload == dist ama canlıda dist'te olmayan dosya var (ör. dışlanan localService) → rc 1."""
        rc, istekler, proj = self._kos(optin=True, canli={"Component-preload.js": H.PRELOAD,
                                                          "localService/metadata.xml": b"<x/>"})
        log = _son_log(proj) or {}
        ok = rc == 1 and log.get("result") == "verify_stale_files"
        H.kaydet("deploy tam liste: canlıda fazla dosya → STALE", "rc=1 verify_stale_files",
                 f"rc={rc} log={log.get('result')}", ok)
        self.assertTrue(ok, f"rc={rc} istek={istekler} log={log}")

    def test_tam_liste_olculemedi_preload_hukmu_kalir(self):
        """Repo servisi yok (OData + ADT 404) → tam liste ÖLÇÜLEMEDİ uyarısı; preload OK hükmü korunur (rc 0)."""
        rc, istekler, proj = self._kos(optin=True, canli=None)
        log = _son_log(proj) or {}
        ok = rc == 0 and log.get("result") == "ok" and len(istekler) == 3
        H.kaydet("deploy tam liste: servis yok → uyarı, rc 0", "rc=0 istek=3", f"rc={rc} istek={len(istekler)}", ok)
        self.assertTrue(ok, f"rc={rc} istek={istekler} log={log}")

    def test_drift_degisti_build_yok(self):
        """Anlık görüntü ≠ şimdiki canlı → build/deploy KOŞMAZ (rc 1, log drift)."""
        rc, istekler, proj = self._kos(optin=True, anlik={"Component-preload.js": b"// eski canli\n"})
        log = _son_log(proj) or {}
        ok = rc == 1 and self.cagrilar == [] and log.get("result") == "drift" and len(istekler) == 1
        H.kaydet("deploy drift: canlı değişmiş → build/deploy yok", "rc=1 run=0 drift",
                 f"rc={rc} run={len(self.cagrilar)} log={log.get('result')}", ok)
        self.assertTrue(ok, f"rc={rc} run={self.cagrilar} istek={istekler} log={log}")

    def test_drift_olculemedi_build_yok(self):
        """Anlık görüntü var ama canlı okunamıyor → DUR (rc 2); "aynı" SAYILMAZ."""
        rc, istekler, proj = self._kos(optin=True, canli=None, anlik={"Component-preload.js": H.PRELOAD})
        log = _son_log(proj) or {}
        ok = rc == 2 and self.cagrilar == [] and log.get("result") == "drift_unmeasured"
        H.kaydet("deploy drift: canlı okunamaz → DUR", "rc=2 run=0", f"rc={rc} run={len(self.cagrilar)}", ok)
        self.assertTrue(ok, f"rc={rc} run={self.cagrilar} istek={istekler} log={log}")

    def test_drift_ayni_akis_ve_anlik_guncellenir(self):
        """KONTROL GRUBU (drift): anlık görüntü == canlı → build + deploy; sonra anlık görüntü yeni canlıyla yazılır."""
        durum = {}

        def kontrol(app):
            anlik = K.anlik_oku(app)
            durum["guncellendi"] = bool(anlik and anlik[1].get("guncellendi"))

        rc, istekler, proj = self._kos(optin=True, anlik={"Component-preload.js": H.PRELOAD}, kontrol=kontrol)
        ok = (rc == 0 and self.cagrilar == [D.BUILD_KOMUTU, D.DEPLOY_KOMUTU] and len(istekler) == 3
              and durum.get("guncellendi"))
        H.kaydet("deploy drift: aynı → akış + anlık görüntü güncellenir", "rc=0 istek=3 güncel",
                 f"rc={rc} istek={len(istekler)} güncel={durum.get('guncellendi')}", ok)
        self.assertTrue(ok, f"rc={rc} run={self.cagrilar} istek={istekler} durum={durum}")

    def _kos_anlik_hatali(self, hata_yaz):
        """Deploy akışı; `.canli/` yazımının İKİNCİ çağrısında (deploy sonrası güncelleme) `hata_yaz` devreye girer
        (ilk çağrı `_kos`'un anlık görüntü kurulumudur). → (rc, log, çıktı, .canli durumu)."""
        import contextlib
        import io
        asil = K.anlik_yaz
        sayac = {"n": 0}

        def sarici(app, dosyalar, bilgi):
            sayac["n"] += 1
            return asil(app, dosyalar, bilgi) if sayac["n"] == 1 else hata_yaz(asil, app, dosyalar, bilgi)
        durum = {}

        def kontrol(app):
            kok = app / K.ANLIK_KLASOR
            oku = K.anlik_oku(app)
            durum["dist"] = oku[0] if oku else None
            durum["guncellendi"] = bool(oku and oku[1].get("guncellendi"))
            durum["adlar"] = sorted(p.name for p in kok.iterdir()) if kok.is_dir() else None
        cikti = io.StringIO()
        with mock.patch.object(K, "anlik_yaz", sarici), contextlib.redirect_stdout(cikti):
            rc, istekler, proj = self._kos(optin=True, anlik={"Component-preload.js": H.PRELOAD}, kontrol=kontrol)
        return rc, (_son_log(proj) or {}), cikti.getvalue(), durum

    def test_anlik_guncellenemez_eski_yerinde_deploy_basarili(self):
        """Tur 4 / 1: deploy + tam liste OK, `.canli/` güncellemesi takasta düşer (gerçek `anlik_yaz`, hata
        `_yer_degistir`'de) → eski görüntü BAYT BAYT yerinde (ölçüldü) → exit 0 + açık UYARI, log
        `ok_snapshot_not_updated`, traceback yok."""
        def takas_duser(asil, app, dosyalar, bilgi):
            with mock.patch.object(K, "_yer_degistir", side_effect=OSError(28, "benzetim")):
                return asil(app, dosyalar, bilgi)
        rc, log, out, durum = self._kos_anlik_hatali(takas_duser)
        ok = (rc == 0 and log.get("result") == "ok_snapshot_not_updated" and "GÜNCELLENEMEDİ" in out
              and "eski görüntü bayt bayt yerinde" in out and "Traceback" not in out
              and durum.get("dist") == {"Component-preload.js": H.PRELOAD} and not durum.get("guncellendi")
              and durum.get("adlar") == ["bilgi.json", "dist"])
        H.kaydet("deploy: .canli güncellemesi düşer, eski yerinde → rc 0 + UYARI (ok_snapshot_not_updated)",
                 "rc=0 · eski · uyarı", f"rc={rc} · {log.get('result')} · {durum}", ok)
        self.assertTrue(ok, (rc, log, durum, out))

    def test_anlik_bozulursa_exit2_tekrar_deploy_etme(self):
        """Negatif: güncelleme eski görüntüyü bozup düşer (benzetim) → ölçüm görür → exit 2, log `ok_snapshot_broken`,
        mesaj deploy'un DOĞRULANDIĞINI ve tekrar edilmemesini söyler."""
        def bozan(asil, app, dosyalar, bilgi):
            (Path(app) / K.ANLIK_KLASOR / "dist" / "Component-preload.js").unlink()
            raise OSError(28, "benzetim")
        rc, log, out, durum = self._kos_anlik_hatali(bozan)
        ok = (rc == 2 and log.get("result") == "ok_snapshot_broken" and "KORUNAMADI" in out
              and "TEKRAR DEPLOY ETME" in out and "[OK] deploy doğrulandı" not in out)
        H.kaydet("deploy: .canli güncellemesi eskiyi bozar → rc 2 (ok_snapshot_broken)", "rc=2 KORUNAMADI",
                 f"rc={rc} · {log.get('result')}", ok)
        self.assertTrue(ok, (rc, log, out))

    def test_anlik_gecici_yol_kalirsa_exit2_listeler(self):
        """Görüntü yerinde ama `dist.yeni` silinemedi (tutamaç benzetimi) → ölçülen kalan listelenir, exit 2
        (`ok_snapshot_broken`); "bayt bayt yerinde" + exit 0 DENMEZ."""
        asil_sil = K._agac_sil

        def yeni_silinmez(p):
            return None if Path(p).name == "dist.yeni" else asil_sil(p)

        def takas_duser_artik_kalir(asil, app, dosyalar, bilgi):
            with mock.patch.object(K, "_yer_degistir", side_effect=OSError(28, "benzetim")), \
                    mock.patch.object(K, "_agac_sil", yeni_silinmez):
                return asil(app, dosyalar, bilgi)
        rc, log, out, durum = self._kos_anlik_hatali(takas_duser_artik_kalir)
        ok = (rc == 2 and log.get("result") == "ok_snapshot_broken" and "geçici yollar kaldı" in out
              and "dist.yeni" in out and durum.get("dist") == {"Component-preload.js": H.PRELOAD})
        H.kaydet("deploy: .canli geçici yol kalır → rc 2, kalan listelenir", "rc=2 dist.yeni",
                 f"rc={rc} · {log.get('result')}", ok)
        self.assertTrue(ok, (rc, log, out, durum))

    def test_transport_z_paket_transport_yok_run_ve_istek_sifir(self):
        rc, istekler, proj = self._kos(optin=True, paket_tr=("ZXX001", None))
        log = _son_log(proj) or {}
        ok = (rc == 3 and self.cagrilar == [] and istekler == [] and log.get("result") == "ADR_0005_C"
              and log.get("exit_code") == 3)
        H.kaydet("deploy kapı (süreç içi): Z paket + transport yok → run=0 istek=0", "rc=3 0/0 ADR_0005_C",
                 f"rc={rc} run={len(self.cagrilar)} istek={len(istekler)} log={log.get('result')}", ok)
        self.assertTrue(ok, f"rc={rc} run={self.cagrilar} istek={istekler} log={log}")


if __name__ == "__main__":
    unittest.main()
