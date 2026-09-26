#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test yardımcıları: script'i ayrı süreçte koşma, sahte BSP/proxy HTTP sunucusu, geçici deploy uygulaması.

Hiçbir test gerçek SAP'ye, internete ya da npm'e gitmez. Ağ yalnız 127.0.0.1 üzerindeki sahte sunucudur.
"""
from __future__ import annotations

import base64
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import zipfile
from pathlib import Path

BURASI = Path(__file__).resolve().parent
SKILL = BURASI.parent
SCRIPTS = SKILL / "scripts"
FIXTURES = BURASI / "fixtures"
KULLANICI = "demo"
PAROLA = "gizli!parola"  # sahte sunucunun beklediği SAHTE kimlik — gerçek değil

SONUCLAR: list[tuple[str, str, str, bool]] = []

_KALDIRILAN = {"FIORI_TOOLS_USER", "FIORI_TOOLS_PASSWORD", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"}


def kaydet(ad: str, beklenen: str, gercek: str, ok: bool) -> None:
    SONUCLAR.append((ad, beklenen, gercek, ok))


def ortam(kimlik: bool = False) -> dict:
    """Alt süreç ortamı: gerçek kimlik/proxy temizlenir; urllib'in 127.0.0.1'e proxy'siz gitmesi zorlanır."""
    env = {k: v for k, v in os.environ.items() if k.upper() not in _KALDIRILAN}
    env.update(http_proxy="http://127.0.0.1:9", https_proxy="http://127.0.0.1:9", no_proxy="*",
               PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    if kimlik:
        env["FIORI_TOOLS_USER"] = KULLANICI
        env["FIORI_TOOLS_PASSWORD"] = PAROLA
    return env


def proxy_bypass_surec_ici() -> None:
    """Aynı süreçte urllib çağıran testler için (Windows registry proxy'sini devre dışı bırakır)."""
    for k in list(os.environ):
        if k.upper() in {"HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"}:
            del os.environ[k]
    os.environ.update(http_proxy="http://127.0.0.1:9", https_proxy="http://127.0.0.1:9", no_proxy="*")


def kos(script_rel: str, *args, kimlik: bool = False, zaman: int = 120) -> tuple[int, str]:
    p = subprocess.run([sys.executable, str(SCRIPTS / script_rel), *map(str, args)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=ortam(kimlik), timeout=zaman)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


class SahteSunucu:
    """127.0.0.1 üzerinde yol → gövde servis eden, Basic auth bekleyen sahte sunucu."""

    def __init__(self, dosyalar: dict[str, bytes], kullanici: str | None = KULLANICI, parola: str = PAROLA):
        self.dosyalar = dict(dosyalar)
        self.auth = ("Basic " + base64.b64encode(f"{kullanici}:{parola}".encode()).decode()) if kullanici else None
        self.istekler: list[str] = []

    def __enter__(self):
        dis = self

        class H(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                dis.istekler.append(self.path)
                if dis.auth and self.headers.get("Authorization") != dis.auth:
                    self.send_response(401)
                    self.send_header("WWW-Authenticate", 'Basic realm="demo"')
                    self.end_headers()
                    return
                govde = dis.dosyalar.get(self.path.split("?", 1)[0])
                if govde is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Length", str(len(govde)))
                self.end_headers()
                self.wfile.write(govde)

            def log_message(self, *a):  # noqa: D401
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *a):
        self.httpd.shutdown()
        self.httpd.server_close()


DEPLOY_YAML = """specVersion: "4.0"
metadata:
  name: zxx001.order
type: application
builder:
  resources:
    excludes:
      - /test/**
      - /localService/**
  customTasks:
    - name: ui5-task-zipper
      afterTask: generateCachebusterInfo
      configuration:
        archiveName: demo
    - name: deploy-to-abap
      afterTask: generateCachebusterInfo
      configuration:
        ignoreCertErrors: true   # sertifika notu
        target:
          url: {url}   # kanonik host
          client: '100'
        app:
          name: {name}
          description: Demo siparis uygulamasi
          package: ZXX001
          transport: ZXXK900001
        exclude:
          - /test/
"""

PRELOAD = (rb"//@ui5-bundle zxx001/order/Component-preload.js" b"\n"
           rb"sap.ui.require.preload({" b"\n"
           rb"	" rb'"zxx001/order/Component.js":function(){sap.ui.define([],function(){return 1;});},' b"\n"
           rb"	" rb'"zxx001/order/view/App.view.xml":' rb"'<mvc:View xmlns:mvc=" rb'"sap.ui.core.mvc"' rb">\n<App id=" rb'"app"' rb"/>\n</mvc:View>'" b"\n"
           rb"});" b"\n")


def gecici_app(url: str = "http://127.0.0.1:1", name: str = "ZXX001_ORDER", dist_taze: bool = True) -> Path:
    """app_good kopyası + ui5-deploy.yaml + package.json + dist/Component-preload.js (geçici klasörde)."""
    kok = Path(tempfile.mkdtemp(prefix="ui5test_")) / "order_app"
    shutil.copytree(FIXTURES / "app_good", kok)
    (kok / "ui5-deploy.yaml").write_text(DEPLOY_YAML.format(url=url, name=name), encoding="utf-8")
    (kok / "package.json").write_text('{"name":"order_app","scripts":{"build":"ui5 build --clean-dest --dest dist"}}',
                                      encoding="utf-8")
    (kok / "webapp" / "test").mkdir(parents=True, exist_ok=True)
    (kok / "webapp" / "test" / ".eslintrc").write_text("{}", encoding="utf-8")  # excludes kapsamında: işaretlenmemeli
    dist = kok / "dist"
    dist.mkdir()
    (dist / "Component-preload.js").write_bytes(PRELOAD)
    simdi = time.time()
    for p in (kok / "webapp").rglob("*"):
        if p.is_file():
            os.utime(p, (simdi - 100, simdi - 100))
    t = simdi if dist_taze else simdi - 1000
    os.utime(dist / "Component-preload.js", (t, t))
    return kok


def odata_yol(name: str = "ZXX001_ORDER") -> str:
    """Sahte sunucu anahtarı: UI5 repository OData servisi (sorgu dizesi sunucuda atılır)."""
    return f"/sap/opu/odata/UI5/ABAP_REPOSITORY_SRV/Repositories('{name}')"


def odata_zip(dosyalar: dict, name: str = "ZXX001_ORDER", package: str = "ZXX001",
              description: str = "Demo siparis uygulamasi") -> bytes:
    """`ABAP_REPOSITORY_SRV` JSON yanıtı: `d.ZipArchive` = base64 zip (canlıda ölçülen biçim)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for rel, icerik in dosyalar.items():
            z.writestr(rel, icerik)
    return json.dumps({"d": {"Name": name, "Package": package, "Description": description, "Info": "",
                             "ZipArchive": base64.b64encode(buf.getvalue()).decode()}}).encode()


def temizle(app: Path) -> None:
    shutil.rmtree(app.parent, ignore_errors=True)
