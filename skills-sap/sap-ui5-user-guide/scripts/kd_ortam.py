# -*- coding: utf-8 -*-
"""KD ortamı — ekran görüntülü kullanıcı kılavuzu için bağımlılık denetimi ve Playwright CLI yapılandırması.

Alt komutlar:
    python kd_ortam.py check  --proje <uygulama_dizini>
        Bağımlılık tablosunu basar (node · Chrome · yerel playwright-cli · playwright-core yolu · python
        `markdown` · uygulamada @sap-ux/ui5-middleware-fe-mockserver devDependency'si + `start-mock` script'i ·
        start-mock'un `--config` yaml'ında `backend:` satırı olmaması, webapp/index.html'in mutlak bootstrap
        yolunun yaml'ın `ui5:` path'lerinde eşli olması, yaml'daki bilinen custom middleware'lerin paket adlarının
        uygulama devDependencies'inde bulunması).
        Eksik olan için kurulum KOMUTUNU yazar, KENDİSİ KURMAZ. start-mock komutundaki host/bind bayraklarını
        raporlar (değiştirmez). Yerel sunucular 127.0.0.1'e bağlanmalı: 0.0.0.0'ı dinleyen süreç şirket
        makinesinde güvenlik duvarı izni ister.
        Çıkış: 0 hepsi tamam · 2 en az bir eksik ya da kullanım hatası.

    python kd_ortam.py config --proje <uygulama_dizini> [--kanal chrome|msedge] [--no-sandbox] [--zorla]
        <uygulama>/.playwright/cli.config.json dosyasını Chrome kanalına (ya da `--kanal msedge` ile Edge'e)
        sabitler. İdempotenttir. Farklı içerikli bir kullanıcı dosyası varsa `--zorla` verilmeden EZİLMEZ
        (--zorla eskisini .bak'a alır). Tek istisna: dosya zaten istenen kanala sabitse ve yalnız `--no-sandbox`
        eksikse, diğer anahtarlara dokunmadan `launchOptions.args`'a eklenir.
        `--no-sandbox`: aXet.code bash'inde config'siz ya da bu argümansız `playwright-cli open`
        "Session closed"/"Target crashed" ile düştü; `{"channel":"chrome"|"msedge","args":["--no-sandbox"]}` ile
        açıldı (ölçüldü 2026-09-22, playwright-cli 0.1.21; sebep DOĞRULANMADI). playwright-cli Windows'ta HER
        kanalda sandbox'ı AÇIK başlatır: playwright-core 1.64.0-alpha `validateBrowserConfig` kanala bağlı ifadeyi
        yalnız `process.platform === "linux"` dalında kullanır, Windows'ta koşulsuz `chromiumSandbox = true`
        (coreBundle.js). Normal kabukta (aXet DIŞINDA) chrome/msedge süreç komut satırında `--no-sandbox` yok
        (ölçüldü). Süreç izolasyonunu kapatır: yalnız yerel/güvenilir sayfa.
        Çıkış: 0 yazıldı / zaten uygun · 2 ezilmedi, kullanım hatası ya da yedek/yazma hatası (`HATA:` satırı;
        yedek alınamazsa asıl dosyaya dokunulmaz).

Şema kaynağı (tahmin değil, @playwright/cli 0.1.21 · playwright-core 1.64.0-alpha içinden okundu):
  - dosya yolu: çalışma dizininde `.playwright/cli.config.json`; ayrıca `~/.playwright/cli.config.json` GLOBAL
    olarak altına birleştirilir (playwright-core/lib/coreBundle.js, resolveCLIConfigForCLI).
  - anahtarlar: `browser.browserName` + `browser.launchOptions.channel` (aynı dosya, longhandTypes tablosu).
  - Chrome aranan yerler (Windows): %LOCALAPPDATA%, %PROGRAMFILES%, %PROGRAMFILES(X86)% altında
    `Google\\Chrome\\Application\\chrome.exe` (aynı dosya, chrome kanal tanımı).
Ölçüm (2026-09-21): bu dosyayla `playwright-cli open` edilen oturumda navigator.userAgentData.brands
"Google Chrome" döndü, süreç yolu `...\\Google\\Chrome\\Application\\chrome.exe`, tarayıcı indirmesi olmadı.
Kontrol: kanal `msedge` yapılınca brands "Microsoft Edge" döndü (dosya gerçekten okunuyor).
"""
import argparse
import errno
import fnmatch
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PLAYWRIGHT_CLI_SURUM = "0.1.21"  # ölçülen sürüm; kurulum komutu bunu sabitler
KANAL = "chrome"
KANALLAR = ("chrome", "msedge")
NO_SANDBOX = "--no-sandbox"


def hedef_config(kanal=KANAL, no_sandbox=False):
    lo = {"channel": kanal}
    if no_sandbox:
        lo["args"] = [NO_SANDBOX]
    return {"browser": {"browserName": "chromium", "launchOptions": lo}}


HEDEF_CONFIG = hedef_config()
CONFIG_GORELI = os.path.join(".playwright", "cli.config.json")
MOCKSERVER_PAKET = "@sap-ux/ui5-middleware-fe-mockserver"
# Mock yaml'daki custom middleware adı → paketi. UI5 CLI (4.0.69) custom middleware'i yalnız UYGULAMANIN kendi
# package.json bağımlılıklarından çözer: ad yokken `start-mock` "Could not find custom middleware fiori-tools-proxy"
# ile açılmadı, adlar devDependencies'e eklenince açıldı (ölçüldü 2026-09-25, npm workspace). Tabloda olmayan
# middleware adı denetlenmez (KAPSAM'da yazılı). Sürümler app-skeleton.md §2 örneğiyle aynı.
MIDDLEWARE_PAKETI = {"fiori-tools-proxy": "@sap/ux-ui5-tooling", "sap-fe-mockserver": MOCKSERVER_PAKET}
PAKET_SURUMU = {"@sap/ux-ui5-tooling": "1", MOCKSERVER_PAKET: "2"}
NODE_ASGARI = 18  # @playwright/cli package.json engines: node >=18

# Config dosyasından SONRA birleştirilen ve kanalı ezebilen ortam değişkenleri (coreBundle.js configFromEnv).
EZEN_ORTAM = ("PLAYWRIGHT_MCP_BROWSER", "PLAYWRIGHT_MCP_EXECUTABLE_PATH", "PLAYWRIGHT_MCP_CONFIG",
              "PLAYWRIGHT_MCP_CDP_ENDPOINT")

KAPSAM_CHECK = ("KAPSAM (SCOPE): kd_ortam check — bakılanlar: node sürümü, Chrome yürütülebilir dosyası, uygulamada "
                "yerel ya da merkezi (<klon>/.araclar/playwright-cli) @playwright/cli ve playwright-core, python markdown, package.json'da %s devDependency'si ve "
                "start-mock script'i, start-mock komut metnindeki host/bind bayrakları (yalnız metin), "
                "start-mock'un --config yaml'ı (yoksa ui5.yaml): `backend:` satırı, webapp/index.html'deki mutlak "
                "bootstrap yolunun `ui5:` bloğunda path + `pathReplace: /resources` ile eşlenmesi, fiori-tools-proxy adının paketi "
                "devDependencies'te (yaml METİN olarak taranır, YAML ayrıştırılmaz; start-mock'ta --config/-c yoksa yalnız o eksik yazılır), "
                "<proje>/.playwright/cli.config.json'un chrome ya da msedge kanalına sabit olup olmadığı ve "
                "launchOptions.args'ta --no-sandbox bulunup bulunmadığı, ~/.playwright/cli.config.json'un aynı iki "
                "özelliği. "
                "Bakılmayanlar: Chrome'un gerçekten açılabildiği (config sonrası "
                "`playwright-cli open` ile ölçülür), mock sunucunun ayağa kalktığı ve bootstrap yolunun gerçekten 200 "
                "döndüğü (mock-ortam.md §6 curl), yaml'ın geçerli YAML olduğu, eşlemedeki `url`'nin doğru CDN olduğu, blok metin (`|`) içindeki `backend:` satırının yanlış alarm vermesi, workspace glob'larının `!` dışlamaları, tablodaki iki ad dışındaki custom "
                "middleware'ler, index.html dışındaki HTML'ler, mock veri dosyaları, npm ağ/proxy erişimi, global config'in diğer anahtarlarının etkisi (yalnız uyarılır)."
                % MOCKSERVER_PAKET)
KAPSAM_CONFIG = ("KAPSAM (SCOPE): kd_ortam config — yalnız <proje>/.playwright/cli.config.json dosyasının browser "
                 "anahtarlarına bakar. Bakılmayanlar: `playwright-cli open --browser <x>` bayrağı kanalı EZER "
                 "(launchOptions.args korunur — normal kabukta ölçüldü 2026-09-22, aXet içinde ölçülmedi) ve "
                 "PLAYWRIGHT_MCP_* ortam değişkenleri dosyayı EZER (yalnız uyarılır); `--no-sandbox`'ın aXet.code'da "
                 "yeterli olduğu yalnız playwright-cli `open` için ölçüldü; ~/.playwright global "
                 "config'inin kalan anahtarları; tarayıcının gerçekten açıldığı. İndirme riskini bu dosya "
                 "KAPATMAZ — izin kuralları (config/permissions.json) kapatır.")


def _cikti(*a):
    print(*a)
    sys.stdout.flush()


# --------------------------------------------------------------------------- denetimler

def chrome_yolu(env=None):
    """Playwright'ın `chrome` kanalı için baktığı yerlerden ilk bulunan chrome.exe (Windows) ya da PATH isabeti."""
    env = os.environ if env is None else env
    if os.name == "nt":
        ekler = [env.get("LOCALAPPDATA"), env.get("PROGRAMFILES"), env.get("PROGRAMFILES(X86)")]
        if env.get("HOMEDRIVE"):
            ekler += [env["HOMEDRIVE"] + "\\Program Files", env["HOMEDRIVE"] + "\\Program Files (x86)"]
        for on in ekler:
            if not on:
                continue
            aday = os.path.join(on, "Google", "Chrome", "Application", "chrome.exe")
            if os.path.isfile(aday):
                return aday
        return None
    for aday in ("/opt/google/chrome/chrome", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"):
        if os.path.isfile(aday):
            return aday
    return shutil.which("google-chrome") or shutil.which("google-chrome-stable")


def node_durumu():
    node = shutil.which("node")
    if not node:
        return None, None
    try:
        r = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL)
        surum = (r.stdout or "").strip()
    except Exception:
        surum = ""
    return node, surum


def _node_major(surum):
    m = re.match(r"v?(\d+)", surum or "")
    return int(m.group(1)) if m else None


# Merkezi kurulum (v0.5.4, Z60): install.py ve %guncelle `scripts/tarayici_hazirla.py` ile template klonuna kurar;
# proje başına kurulum gerekmez. Bu dosya <klon>/skills-sap/sap-ui5-user-guide/scripts/ altındadır → klon = parents[3].
MERKEZI_GORELI = os.path.join(".araclar", "playwright-cli")
MERKEZI_ORTAM = "AXET_MERKEZI_ARAC"  # merkezi dizini ezer (test ve ölçüm lab'ı için)


_KLON = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
HAZIRLA_BETIGI = os.path.join(_KLON, "scripts", "tarayici_hazirla.py")


def merkezi_dizin(env=None):
    env = os.environ if env is None else env
    return env.get(MERKEZI_ORTAM) or os.path.join(_KLON, MERKEZI_GORELI)


def playwright_cli_yolu(proje, env=None):
    """Önce projede (yerel kurulum), yoksa merkezi dizinde @playwright/cli: (paket dizini, sürüm) ya da (None, None)."""
    for kok in (proje, merkezi_dizin(env)):
        paket = os.path.join(kok, "node_modules", "@playwright", "cli", "package.json")
        if os.path.isfile(paket):
            break
    else:
        return None, None
    try:
        with open(paket, encoding="utf-8") as fh:
            surum = json.load(fh).get("version")
    except Exception:
        surum = None
    return os.path.dirname(paket), surum


def playwright_core_yolu(proje, env=None):
    merkez = merkezi_dizin(env)
    for aday in (os.path.join(proje, "node_modules", "playwright-core"),
                 os.path.join(proje, "node_modules", "@playwright", "cli", "node_modules", "playwright-core"),
                 os.path.join(merkez, "node_modules", "playwright-core"),
                 os.path.join(merkez, "node_modules", "@playwright", "cli", "node_modules", "playwright-core")):
        if os.path.isfile(os.path.join(aday, "package.json")):
            return aday
    return None


def package_json_oku(proje):
    yol = os.path.join(proje, "package.json")
    if not os.path.isfile(yol):
        return None, "package.json yok"
    try:
        with open(yol, encoding="utf-8-sig") as fh:
            return json.load(fh), None
    except Exception as exc:
        return None, "package.json okunamadı: %s" % exc


def global_ev(env=None):
    """playwright-cli'nin GLOBAL config için baktığı ev dizini: `PWTEST_CLI_GLOBAL_CONFIG` ya da `os.homedir()`
    (Windows'ta USERPROFILE). Kaynak: coreBundle.js resolveCLIConfigForCLI →
    `path.join(env.PWTEST_CLI_GLOBAL_CONFIG ?? os.homedir(), ".playwright", "cli.config.json")`. Global dosya bu
    dizinin altında proje dosyasıyla AYNI göreli yoldadır (CONFIG_GORELI) ⇒ config_durumu(global_ev(), …) çalışır.
    Paylaşılır: scripts/tarayici_hazirla.py (v0.5.4)."""
    env = os.environ if env is None else env
    return env.get("PWTEST_CLI_GLOBAL_CONFIG") or os.path.expanduser("~")


def global_config_uyarisi(env=None):
    """~/.playwright/cli.config.json varsa ve browser anahtarı taşıyorsa uyarı metni (proje dosyasının ALTINA birleşir:
    ör. executablePath orada kalırsa kanalın yerine geçer)."""
    yol = os.path.join(global_ev(env), CONFIG_GORELI)
    if not os.path.isfile(yol):
        return None
    try:
        with open(yol, encoding="utf-8-sig") as fh:
            veri = json.load(fh)
    except Exception:
        return "global config okunamadı (%s) — içeriği elle incele" % yol
    ev = global_ev(env)
    if any(config_durumu(ev, k, True)[0] == "uygun" for k in KANALLAR):
        return None  # tarayici_hazirla.py'nin yazdığı biçim (kanal chrome/msedge + --no-sandbox): beklenen durum
    if isinstance(veri, dict) and "browser" in veri:
        return "global config browser anahtarı taşıyor (%s) — proje dosyasının altına birleşir, incele" % yol
    return None


def ortam_uyarilari(env=None):
    env = os.environ if env is None else env
    return ["%s ortam değişkeni tanımlı — config dosyasındaki tarayıcı seçimini ezer" % k for k in EZEN_ORTAM if env.get(k)]


def sandbox_notu(kanal=None, zorla=False):
    """Önerilen komut, koşulunca GERÇEKTEN uygulanmalı (v0.5.3 bug gate): Edge'e sabit dosyada `--kanal msedge`
    verilmezse, hiçbir kanala sabit olmayan (kullanıcı) dosyada `--zorla` verilmezse `config` ezmeyi reddeder (rc 2)."""
    ek = (" --kanal %s" % kanal if kanal and kanal != KANAL else "") + (" --zorla" if zorla else "")
    return ("aXet.code bash'inde `open` %s olmadan düştü (ölçüldü, playwright-cli 0.1.21) → orada "
            "`python kd_ortam.py config --proje <dizin>%s --no-sandbox`; diğer kabuklarda gerekmez" % (NO_SANDBOX, ek))

# `config --zorla` okunamayan dosyayı da bayt bayt .bak'a alıp yeniden yazar (UTF-16 dahil; v0.5.3'te ölçüldü).
BOZUK_METNI = ("okunamadı (JSON değil ya da UTF-8 değil) → elle düzelt ya da ezmek için "
               "`python kd_ortam.py config --proje <dizin> [--kanal msedge] --zorla` (eskisi bayt bayt .bak'a alınır)")

BIND_NOTU = ("NOT: yerel sunucuyu 127.0.0.1'e bağla (ör. `python -m http.server <port> --bind 127.0.0.1`) — "
             "0.0.0.0'ı dinleyen bir süreç şirket makinesinde güvenlik duvarı izni ister (yaşandı 2026-09-21).")

# start-mock komut metninde host/bind'i etkileyen bayraklar. Yalnız METİN tespiti yapılır; `fiori run`/`ui5 serve`
# varsayılan bind adresi bu araçta DOĞRULANMADI (araç o paketlerin kaynağını okumaz).
_HOST_BAYRAK = re.compile(r"(--accept-remote-connections\b|--host(?:=|\s+)\S+|--bind(?:=|\s+)\S+|\s-h\s+\S+)")


def start_mock_host_tespiti(script):
    """start-mock komutunda host/bind bayrağı var mı: (özet metni, uzaktan_erisim_acik_mi)."""
    if not script:
        return "start-mock yok — tespit yapılmadı", False
    bulunan = [m.group(1).strip() for m in _HOST_BAYRAK.finditer(" " + script)]
    if not bulunan:
        return "host/bind bayrağı YOK (varsayılan bind adresi DOĞRULANMADI — sunucu açılınca `netstat -ano` ile bak)", False
    acik = any(b.startswith("--accept-remote-connections") or "0.0.0.0" in b for b in bulunan)
    return "bulunan: " + ", ".join(bulunan) + (" → UZAKTAN ERİŞİME AÇIK: güvenlik duvarı izni istenebilir" if acik else ""), acik


def workspace_koku(proje, derinlik=3):
    """Uygulamayı `workspaces` desenleriyle GERÇEKTEN kapsayan ilk üst dizin (en çok `derinlik` seviye) ya da None.
    Üyelik denetlenir: kapsamayan bir kökte kurulum uygulamayı okumaz (ör. ev dizinindeki ilgisiz package.json)."""
    uyg = os.path.abspath(proje)
    d = uyg
    for _ in range(derinlik):
        ust = os.path.dirname(d)
        if ust == d:
            break
        d = ust
        pj, _ = package_json_oku(d)
        ws = pj.get("workspaces") if isinstance(pj, dict) else None
        if isinstance(ws, dict):  # yarn biçimi: {"packages": [...]}
            ws = ws.get("packages")
        if isinstance(ws, list) and ws:
            goreli = os.path.relpath(uyg, d).replace(os.sep, "/")
            if any(isinstance(w, str) and fnmatch.fnmatchcase(goreli, w.strip("./").rstrip("/")) for w in ws):
                return d
    return None


def paket_kurulum_onerisi(proje, paket):
    """npm workspace'te uygulamaya ayrı kurulum yapılmaz (uygulama başına lock/node_modules oluşur — app-skeleton.md
    §2): ad uygulamanın devDependencies'ine yazılır, kurulum workspace kökünde koşar. Workspace yoksa eski komut."""
    kok = workspace_koku(proje)
    if kok:
        return ('uygulama package.json → devDependencies\'e "%s": "%s" adını ekle, sonra workspace kökünde '
                '`npm install --prefix "%s"` (uygulamaya ayrı kurulum YOK — app-skeleton.md §2)'
                % (paket, PAKET_SURUMU.get(paket, "<sürüm>"), kok))
    return 'npm install --prefix "%s" --save-dev %s' % (proje, paket)


# `fiori run` yalnız `--config <yol>` ve `-c <yol>` biçimini okur, yoksa `ui5.yaml` (ölçüldü: @sap/ux-ui5-tooling
# dist/cli getYamlFile — `FileName.Ui5Yaml`); `ui5` CLI'de `-c` `--config`'in kısaltması (@ui5/cli lib/cli/base.js).
_CONFIG_BAYRAK = re.compile(r"""(?<!\S)(?:--config|-c)(?:=|\s+)(?:"([^"]+)"|'([^']+)'|(\S+))""")
_SUNUCU_KOMUTU = re.compile(r"\b(?:fiori\s+run|ui5\s+serve)\b")
_BOOTSTRAP = re.compile(r"""<script\b[^>]*\bid\s*=\s*["']sap-ui-bootstrap["'][^>]*>""", re.I | re.S)
_SRC = re.compile(r"""\bsrc\s*=\s*["']([^"']+)["']""", re.I)
_BACKEND_ANAHTARI = re.compile(r"""(?:^\s*-?\s*|[{,]\s*)["']?backend["']?\s*:""")


def mock_yaml_yolu(proje, script):
    """start-mock'un sunucuyu başlatan parçasındaki (`fiori run`/`ui5 serve`; `&&` zincirinde) `--config`/`-c` değeri:
    (yol ya da None, bayrak_var_mi). Bayrak yoksa sunucu canlı `ui5.yaml`'la açılır — yol None döner."""
    parcalar = [s for s in re.split(r"&&|\|\||;|\|", script or "") if s.strip()]
    sunucu = [s for s in parcalar if _SUNUCU_KOMUTU.search(s)] or parcalar
    m = _CONFIG_BAYRAK.search(sunucu[-1]) if sunucu else None
    if not m:
        return None, False
    goreli = next(g for g in m.groups() if g)
    return os.path.normpath(os.path.join(proje, goreli)), True


def yaml_tara(metin):
    """YAML METİN taraması (ayrıştırıcı yok, stdlib): (backend satır no'ları, `ui5:` bloğundaki (path, pathReplace)
    çiftleri, `name:` değerleri). Yorumlar (#) atılır; `ui5:` bloğu girintiyle izlenir; `pathReplace` en son görülen
    `path` öğesine bağlanır. Akış biçimi (`{backend: …}`) ve tırnaklı anahtar da backend sayılır."""
    backend, yollar, adlar, ui5_girinti = [], [], [], None
    for no, satir in enumerate(metin.splitlines(), 1):
        kod = satir.split("#", 1)[0].rstrip()
        if not kod.strip():
            continue
        girinti = len(kod) - len(kod.lstrip())
        if ui5_girinti is not None and girinti <= ui5_girinti:
            ui5_girinti = None
        if _BACKEND_ANAHTARI.search(kod):
            backend.append(no)
        m = re.match(r"""\s*-?\s*name\s*:\s*["']?([^"'\s]+)""", kod)
        if m:
            adlar.append(m.group(1))
        if re.match(r"""\s*["']?ui5["']?\s*:\s*$""", kod):
            ui5_girinti = girinti
            continue
        if ui5_girinti is None:
            continue
        m = re.match(r"\s*-?\s*path\s*:\s*(.+)$", kod)
        if m:
            deger = m.group(1).strip()
            parcalar = deger[1:-1].split(",") if deger.startswith("[") and deger.endswith("]") else [deger]
            yollar.extend([p.strip().strip("\"'").rstrip("/"), None] for p in parcalar if p.strip())
            continue
        m = re.match(r"""\s*-?\s*pathReplace\s*:\s*["']?([^"'\s]+)""", kod)
        if m and yollar:
            yollar[-1][1] = m.group(1).rstrip("/")
    return backend, [tuple(y) for y in yollar], adlar


def bootstrap_eslesmesi(dizin, yollar):
    """Bootstrap dizinini CDN'e doğru taşıyan `ui5:` öğesi: ya dizinin KENDİSİ + `pathReplace: /resources`
    (mock-ortam.md §2 biçimi), ya da dizin zaten `/resources…` ise onu önekle kapsayan pathReplace'siz öğe.
    Başka biçim (ör. `/sap` öneki, pathReplace'siz `/sap/public/…`) CDN'de 404 verir → eşleme sayılmaz."""
    for p, repl in yollar:
        if p == dizin and repl == "/resources":
            return p, repl
        if repl is None and dizin.startswith("/resources") and (dizin == p or dizin.startswith(p + "/")):
            return p, repl
    return None


def bootstrap_src(proje):
    """webapp/index.html'deki sap-ui-bootstrap src'si: (src ya da None, hata metni ya da None)."""
    try:
        with open(os.path.join(proje, "webapp", "index.html"), encoding="utf-8-sig", errors="replace") as fh:
            html = fh.read()
    except OSError:
        return None, "webapp/index.html yok"
    m = _BOOTSTRAP.search(html)
    s = _SRC.search(m.group(0)) if m else None
    return (s.group(1), None) if s else (None, "index.html'de sap-ui-bootstrap src'si bulunamadı")


def mock_yaml_denetle(proje, pj):
    """start-mock yaml'ının satırları (denetle() biçimi) + BİLGİ metinleri. Kök neden (ölçüldü 2026-09-25):
    mockserver-config-writer ui5-mock.yaml'ı ui5.yaml'dan kopyalar, `backend:` bloğu da gelir → mock SAP'ye bağlanmaya
    çalışır ve /sap/public/... bootstrap'ı 500 döner; `ui5:` path'lerinde eşlemesi olmayan mutlak bootstrap yolu da
    backend'siz mock'ta yüklenmez."""
    script = ((pj or {}).get("scripts") or {}).get("start-mock")
    if not script:
        return [], []
    yol, bayrak = mock_yaml_yolu(proje, script)
    if not bayrak:
        # Bayrak yoksa `fiori run` canlı ui5.yaml'la açılır (backend'li) — onu "mock yaml" sanıp backend'ini
        # kaldırmayı önermek canlı `start`/`start-noflp`'u bozar (bug gate 2026-09-25).
        return [("mock yaml", False, "start-mock'ta --config YOK → sunucu canlı ui5.yaml'la (backend'li) açılır",
                 "start-mock'a `--config ./ui5-mock.yaml` ekle (app-skeleton.md §4)")], []
    try:
        etiket = os.path.relpath(yol, proje)
    except ValueError:  # farklı sürücü (Windows)
        etiket = yol
    try:
        with open(yol, encoding="utf-8-sig", errors="replace") as fh:
            metin = fh.read()
    except OSError:
        return [("mock yaml", False, "YOK: %s" % etiket,
                 "start-mock'un --config ile gösterdiği yaml'ı oluştur (mock-ortam.md §2)")], []
    backend, yollar, adlar = yaml_tara(metin)
    satirlar = [("mock yaml backend'siz", not backend,
                 ("%s: `backend:` YOK" % etiket) if not backend else
                 "%s satır %s: `backend:` VAR → mock SAP'ye bağlanır (bootstrap 500)"
                 % (etiket, ", ".join(map(str, backend))),
                 None if not backend else "%s'dan fiori-tools-proxy `backend:` bloğunu kaldır (mock-ortam.md §2)"
                 % etiket)]
    bilgi = []
    src, hata = bootstrap_src(proje)
    if src is None:
        bilgi.append("bootstrap eşlemesi ÖLÇÜLEMEDİ: %s" % hata)
    elif not src.startswith("/") or src.startswith("//"):
        bilgi.append("bootstrap göreli ya da CDN (%s) → yaml eşlemesi denetlenmedi" % src)
    else:
        dizin = src.split("?", 1)[0].rsplit("/", 1)[0]
        eslesen = bootstrap_eslesmesi(dizin, yollar)
        satirlar.append(("mock yaml bootstrap yolu", bool(eslesen),
                         ("%s → ui5 path %s%s" % (dizin, eslesen[0], " + pathReplace %s" % eslesen[1] if eslesen[1]
                                                   else "")) if eslesen else
                         "%s için `ui5:` bloğunda doğru eşleme YOK (path + pathReplace: /resources)" % dizin,
                         None if eslesen else "%s → fiori-tools-proxy ui5.paths'e `- path: %s` + `url: "
                         "https://ui5.sap.com` + `pathReplace: /resources` ekle (mock-ortam.md §2)" % (etiket, dizin)))
    dev = (pj or {}).get("devDependencies") or {}
    for ad in sorted(set(adlar) & set(MIDDLEWARE_PAKETI)):
        paket = MIDDLEWARE_PAKETI[ad]
        if paket == MOCKSERVER_PAKET:
            continue  # "mockserver devDependency" satırı zaten denetliyor
        satirlar.append(("middleware paketi: %s" % ad, paket in dev, dev.get(paket, "YOK (%s)" % paket),
                         None if paket in dev else paket_kurulum_onerisi(proje, paket)))
    return satirlar, bilgi


def denetle(proje, env=None):
    """Satır listesi döner: (ad, tamam: bool, değer, kurulum_komutu)."""
    satirlar = []
    node, surum = node_durumu()
    major = _node_major(surum)
    if not node:
        satirlar.append(("node", False, "YOK", "Node.js %d+ kurulmalı" % NODE_ASGARI))
    elif major is not None and major < NODE_ASGARI:
        satirlar.append(("node", False, "%s (%s)" % (surum, node), "Node.js %d+ kurulmalı" % NODE_ASGARI))
    else:
        satirlar.append(("node", True, "%s (%s)" % (surum or "sürüm okunamadı", node), None))

    chrome = chrome_yolu(env)
    satirlar.append(("Chrome", bool(chrome), chrome or "YOK",
                     None if chrome else "Google Chrome kurulmalı (sistem kurulumu; Playwright ile İNDİRİLMEZ)"))

    cli_dizin, cli_surum = playwright_cli_yolu(proje, env)
    komut_cli = ('python "%s"  (merkezi kurulum @playwright/cli@%s; install.py ve %%guncelle zaten koşar, proje başına '
                 'kurulum gerekmez)' % (HAZIRLA_BETIGI, PLAYWRIGHT_CLI_SURUM))
    satirlar.append(("playwright-cli", bool(cli_dizin),
                     ("%s (%s)" % (cli_surum, cli_dizin)) if cli_dizin else "YOK", None if cli_dizin else komut_cli))

    core = playwright_core_yolu(proje, env)
    satirlar.append(("playwright-core", bool(core),
                     ("%s  → capture_kd_screens.js için PLAYWRIGHT_CORE_PATH=%s" % (core, core)) if core else "YOK",
                     None if core else komut_cli + "  (playwright-core bağımlılık olarak gelir)"))

    md = importlib.util.find_spec("markdown") is not None
    satirlar.append(("python markdown", md, "kurulu" if md else "YOK",
                     None if md else "python -m pip install markdown"))

    pj, hata = package_json_oku(proje)
    if pj is None:
        satirlar.append(("mockserver devDependency", False, hata, "uygulama klasörünü doğru ver (package.json içeren)"))
        satirlar.append(("start-mock script'i", False, hata, "uygulama klasörünü doğru ver (package.json içeren)"))
    else:
        dev = pj.get("devDependencies") or {}
        var = MOCKSERVER_PAKET in dev
        satirlar.append(("mockserver devDependency", var, dev.get(MOCKSERVER_PAKET, "YOK"),
                         None if var else paket_kurulum_onerisi(proje, MOCKSERVER_PAKET)))
        scr = (pj.get("scripts") or {}).get("start-mock")
        satirlar.append(("start-mock script'i", bool(scr), scr or "YOK",
                         None if scr else "package.json → scripts.start-mock ekle (mockserver'lı yapılandırmayla "
                                          "`fiori run --config <mock-yaml>` çalıştıran script)"))
        satirlar.extend(mock_yaml_denetle(proje, pj)[0])
    return satirlar


def cmd_check(proje, env=None):
    _cikti(KAPSAM_CHECK)
    if not os.path.isdir(proje):
        print("HATA: uygulama dizini yok: %s" % proje, file=sys.stderr)
        return 2
    satirlar = denetle(proje, env)
    _cikti("== KD ortamı: %s ==" % proje)
    for ad, tamam, deger, _ in satirlar:
        _cikti("  %-5s %-26s %s" % ("OK" if tamam else "EKSİK", ad, deger))
    cfg, kanal = config_kanali(proje)
    cfg_metni = {
        "uygun": "%s kanalına sabit" % {"chrome": "Chrome", "msedge": "Edge"}.get(kanal, kanal),
        "yok": "YOK → config yokken @playwright/cli varsayılanı zaten chromium + kanal chrome "
               "(validateBrowserConfig); global ~/.playwright/cli.config.json %s (install.py/%%guncelle yazar: "
               "tarayici_hazirla.py). Proje dosyası yalnız proje-düzeyi istisna için: "
               "`python kd_ortam.py config --proje <dizin>`" % global_ozet(env),
        "farkli": "Chrome'a da Edge'e de sabit DEĞİL (kullanıcı dosyası) → ezmek için "
                  "`python kd_ortam.py config --proje <dizin> [--kanal msedge] --zorla` (eskisi .bak'a alınır)",
        "bozuk": BOZUK_METNI}
    _cikti("  %-5s %-26s %s" % ("BİLGİ", "cli.config.json kanalı", cfg_metni[cfg]))
    # `zorla`, önerilen komutun kendisinin göreceği durumdan hesaplanır (v0.5.4 Z59): kanal uygun görünse de
    # launchOptions.args liste değilse `config --no-sandbox` dosyayı 'farkli' sayar ve --zorla'sız ezmez.
    zorla = config_durumu(proje, kanal or KANAL, True)[0] == "farkli"
    _cikti("  %-5s %-26s %s" % ("BİLGİ", "cli.config.json sandbox", sandbox_metni(proje, kanal, zorla=zorla, env=env)))
    pj, _ = package_json_oku(proje)
    host_ozet, uzak = start_mock_host_tespiti(((pj or {}).get("scripts") or {}).get("start-mock"))
    _cikti("  %-5s %-26s %s" % ("UYARI" if uzak else "BİLGİ", "start-mock host/bind", host_ozet))
    for b in mock_yaml_denetle(proje, pj)[1]:
        _cikti("  %-5s %-26s %s" % ("BİLGİ", "mock yaml", b))
    for u in filter(None, [global_config_uyarisi(env)] + ortam_uyarilari(env)):
        _cikti("  UYARI " + u)
    _cikti(BIND_NOTU)
    eksik = [s for s in satirlar if not s[1]]
    if eksik:
        _cikti("KURULUM KOMUTLARI (bu araç KURMAZ; sırayla elle çalıştır):")
        for ad, _, _, komut in eksik:
            _cikti("  - %s: %s" % (ad, komut))
        _cikti("SONUÇ: %d eksik / %d bileşen" % (len(eksik), len(satirlar)))
        return 2
    _cikti("SONUÇ: tamam (%d bileşen)" % len(satirlar))
    return 0


# --------------------------------------------------------------------------- config

def _uygun_mu(veri, kanal=KANAL, no_sandbox=False):
    """Dosya zaten istenen kanala sabit mi: browserName chromium (ya da yok) + launchOptions.channel == kanal ve
    kanalı geçersiz kılan executablePath yok; `no_sandbox` istendiyse launchOptions.args '--no-sandbox' içerir.
    Kullanıcının diğer anahtarları (fazladan args dahil) serbesttir."""
    if not isinstance(veri, dict):
        return False
    b = veri.get("browser")
    if not isinstance(b, dict):
        return False
    lo = b.get("launchOptions")
    if not isinstance(lo, dict):
        return False
    temel = (b.get("browserName", "chromium") == "chromium" and lo.get("channel") == kanal
             and not lo.get("executablePath") and not b.get("cdpEndpoint") and not b.get("remoteEndpoint"))
    return temel and (not no_sandbox or _sandbox_kapali(lo))


def _sandbox_kapali(lo):
    args = lo.get("args") if isinstance(lo, dict) else None
    return isinstance(args, list) and NO_SANDBOX in args


def config_durumu(proje, kanal=KANAL, no_sandbox=False):
    """('yok'|'uygun'|'eksik-sandbox'|'farkli'|'bozuk', yol, ham_metin).
    'eksik-sandbox' = kanal uygun, yalnız istenen '--no-sandbox' yok (güvenle eklenebilir)."""
    yol = os.path.join(proje, CONFIG_GORELI)
    if not os.path.isfile(yol):
        return "yok", yol, None
    try:
        with open(yol, encoding="utf-8-sig") as fh:
            ham = fh.read()
        veri = json.loads(ham)
    except UnicodeDecodeError:  # UTF-8 olmayan dosya (ör. UTF-16) — çökme değil 'bozuk' (v0.5.3 bug gate açık kalemi)
        return "bozuk", yol, None
    except ValueError:
        return "bozuk", yol, ham
    if _uygun_mu(veri, kanal, no_sandbox):
        return "uygun", yol, ham
    if no_sandbox and _uygun_mu(veri, kanal):
        args = veri["browser"]["launchOptions"].get("args")
        if args is None or isinstance(args, list):
            return "eksik-sandbox", yol, ham
    return "farkli", yol, ham


def config_kanali(proje):
    """check için: ('uygun', kanal) dosya KANALLAR'dan birine sabitse (config --kanal ile yazılabilen her kanal
    geçerli seçimdir); aksi halde (config_durumu durumu, None)."""
    durum = "yok"
    for kanal in KANALLAR:
        durum = config_durumu(proje, kanal)[0]
        if durum == "uygun":
            return "uygun", kanal
    return durum, None


def global_ozet(env=None):
    """Global dosyanın durumu (check metni için): chrome/msedge'e sabit ve --no-sandbox'lı mı."""
    ev = global_ev(env)
    durum = "yok"
    for kanal in KANALLAR:
        durum = config_durumu(ev, kanal, True)[0]
        if durum == "uygun":
            return "VAR (kanal %s · %s)" % (kanal, NO_SANDBOX)
    return {"yok": "YOK", "eksik-sandbox": "var ama %s eksik" % NO_SANDBOX, "bozuk": "okunamadı (JSON değil)"}.get(
        durum, "farklı içerikli (kullanıcı dosyası)")


def sandbox_metni(proje, kanal=None, zorla=False, env=None):
    """check için: dosyadaki launchOptions.args'ta '--no-sandbox' olup olmadığını (sabit metin değil) yazar."""
    yol = os.path.join(proje, CONFIG_GORELI)
    if not os.path.isfile(yol):
        g = global_ozet(env)
        if g.startswith("VAR"):
            return ("config YOK → global dosya geçerli: %s — aXet.code'da yeterli (ölçüldü 2026-09-22, Z60)" % g)
        durum = "config YOK → %s yok" % NO_SANDBOX
    else:
        try:
            with open(yol, encoding="utf-8-sig") as fh:
                veri = json.load(fh)
        except ValueError:  # UnicodeDecodeError dahil
            return "okunamadı (JSON değil ya da UTF-8 değil) — %s" % sandbox_notu(kanal, zorla=True)
        b = veri.get("browser") if isinstance(veri, dict) else None
        if _sandbox_kapali(b.get("launchOptions") if isinstance(b, dict) else None):
            return "launchOptions.args'ta %s VAR (süreç izolasyonu kapalı: yalnız yerel/güvenilir sayfa)" % NO_SANDBOX
        durum = "launchOptions.args'ta %s YOK" % NO_SANDBOX
    return "%s — %s" % (durum, sandbox_notu(kanal, zorla))


# Z64 L4 (v0.5.5): Windows'ta os.replace, hedefi FILE_SHARE_DELETE'siz açık tutan bir süreç varken PermissionError
# verir (Python'un kendi open()'ı, çoğu editör, virüs tarayıcı/indeksleyici böyle açar; eski open(yol, "w") geçerdi).
# Kısa tekrar denemeler geçici tutucuyu bekler; kalıcı tutucuda metin dönülür (yarım dosya riski yerine).
YAZ_BEKLEMELERI = (0.1, 0.2)  # saniye; toplam 3 deneme
# os.replace yeni dosyanın özniteliklerini taşır → hedefin Hidden/System/NotContentIndexed'i düşerdi (ölçüldü).
_KORUNAN_OZNITELIK = 0x2 | 0x4 | 0x2000  # FILE_ATTRIBUTE_HIDDEN | SYSTEM | NOT_CONTENT_INDEXED


def _win_oznitelik(yol, yeni=None):
    """Yalnız Windows: yeni None → dosya öznitelikleri (okunamazsa None); değilse yazar (başarı bool). POSIX'te None."""
    if os.name != "nt":
        return None
    import ctypes  # noqa: PLC0415 — yalnız Windows yolunda
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    if yeni is None:
        k32.GetFileAttributesW.restype = ctypes.c_uint32
        ozn = k32.GetFileAttributesW(str(yol))
        return None if ozn == 0xFFFFFFFF else ozn
    return bool(k32.SetFileAttributesW(str(yol), ctypes.c_uint32(yeni)))


def _yaz(yol, veri=None):
    """Başarıda None; OSError'da kullanıcıya basılacak metin (v0.5.4 Z59: traceback yerine HATA satırı).
    ATOMİK (v0.5.4 bug gate madde 3): aynı dizinde geçici dosyaya yazılır, fsync, sonra os.replace. Hangi adımda
    düşerse düşsün asıl dosyaya dokunulmamıştır (yarım dosya kalmaz) ve geçici dosya silinir. Salt-okunur hedef
    önceden reddedilir: os.replace POSIX'te salt-okunur dosyanın üstüne de yazabilirdi (dizin izni yeter); eski
    `open(yol, "w")` davranışı korunur. Hedef bir sembolik bağsa bağın işaret ettiği dosya değiştirilir, bağ kalır.
    Windows (Z64 L4): hedefi başka bir süreç silme-paylaşımsız açık tutuyorsa os.replace YAZ_BEKLEMELERI ile tekrar
    denenir; tutucu bırakmazsa metin döner (eski open("w") bu durumda yazardı — atomiklik uğruna bilinçli fark).
    Hedefin Hidden/System/NotContentIndexed öznitelikleri yeni dosyaya taşınır; ReadOnly hedef zaten reddedilir."""
    metin = json.dumps(HEDEF_CONFIG if veri is None else veri, indent=2, ensure_ascii=False) + "\n"
    hedef = os.path.realpath(yol)
    dizin = os.path.dirname(hedef)
    gecici = None
    try:
        if os.path.isdir(hedef):
            raise IsADirectoryError(errno.EISDIR, "hedef bir dizin", hedef)
        if os.path.exists(hedef) and not os.access(hedef, os.W_OK):
            raise PermissionError(errno.EACCES, "salt-okunur dosya", hedef)
        os.makedirs(dizin, exist_ok=True)
        fd, gecici = tempfile.mkstemp(prefix="." + os.path.basename(hedef) + ".", suffix=".tmp", dir=dizin)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(metin)
            fh.flush()
            os.fsync(fh.fileno())
        if os.path.exists(hedef):
            shutil.copymode(hedef, gecici)  # mkstemp 0600 açar; kullanıcının dosya izni korunur
            eski_ozn = _win_oznitelik(hedef)
            if eski_ozn and eski_ozn & _KORUNAN_OZNITELIK:
                yeni_ozn = _win_oznitelik(gecici)
                if yeni_ozn is not None:
                    _win_oznitelik(gecici, yeni_ozn | (eski_ozn & _KORUNAN_OZNITELIK))
        else:
            um = os.umask(0)
            os.umask(um)
            os.chmod(gecici, 0o666 & ~um)
        for bekle in YAZ_BEKLEMELERI + (None,):
            try:
                os.replace(gecici, hedef)
                break
            except PermissionError:
                if bekle is None or os.name != "nt":
                    raise
                time.sleep(bekle)
        gecici = None
    except OSError as exc:
        return "%s yazılamadı (%s: %s); dosyaya dokunulmadı." % (yol, type(exc).__name__, exc)
    finally:
        if gecici is not None:
            try:
                os.remove(gecici)
            except OSError:
                pass
    return None


def _yazma_hatasi(hata, ek=""):
    print("HATA: %s%s" % (hata, ek), file=sys.stderr)
    return 2


def sandbox_ekle(yol, ham):
    """config_durumu 'eksik-sandbox' dediği dosyaya YALNIZ launchOptions.args'a '--no-sandbox' ekler; diğer anahtarlar
    (kullanıcının fazladan args'ı dahil) korunur. Dönüş _yaz'ınki: başarıda None, hatada metin (Z59). Paylaşılır: scripts/tarayici_hazirla.py global config için (v0.5.4)."""
    veri = json.loads(ham)
    lo = veri["browser"]["launchOptions"]
    lo["args"] = list(lo.get("args") or []) + [NO_SANDBOX]
    return _yaz(yol, veri)


def _ozet(kanal, no_sandbox):
    return "kanal %s%s" % (kanal, " · %s" % NO_SANDBOX if no_sandbox else "")


def cmd_config(proje, zorla=False, env=None, kanal=KANAL, no_sandbox=False):
    _cikti(KAPSAM_CONFIG)
    if not os.path.isdir(proje):
        print("HATA: uygulama dizini yok: %s" % proje, file=sys.stderr)
        return 2
    durum, yol, ham = config_durumu(proje, kanal, no_sandbox)
    for u in filter(None, [global_config_uyarisi(env)] + ortam_uyarilari(env)):
        _cikti("UYARI: " + u)
    if no_sandbox:
        _cikti("NOT: %s süreç izolasyonunu kapatır — yalnız yerel/güvenilir sayfalarda kullan." % NO_SANDBOX)
    if durum == "uygun":
        _cikti("ZATEN UYGUN (dokunulmadı): %s — %s" % (yol, _ozet(kanal, no_sandbox)))
        return 0
    if durum == "yok":
        hata = _yaz(yol, hedef_config(kanal, no_sandbox))
        if hata:
            return _yazma_hatasi(hata)
        _cikti("YAZILDI: %s — %s" % (yol, _ozet(kanal, no_sandbox)))
        return 0
    if durum == "eksik-sandbox":
        hata = sandbox_ekle(yol, ham)
        if hata:
            return _yazma_hatasi(hata)
        _cikti("EKLENDİ: %s — launchOptions.args'a %s (diğer anahtarlara dokunulmadı)" % (yol, NO_SANDBOX))
        return 0
    if not zorla:
        print("HATA: %s farklı içerikli (%s) bir kullanıcı dosyası; EZİLMEDİ. İncele, gerekiyorsa --zorla ile yeniden "
              "koş (eskisi .bak'a alınır)." % (yol, "JSON değil" if durum == "bozuk" else "%s'a sabit değil" % kanal),
              file=sys.stderr)
        return 2
    yedek = yol + ".bak"
    # Bayt bayt kopya: UTF-8 olmayan dosyada `ham` None'dır (config_durumu) — metin olarak yazmak çöküp 0 baytlık .bak
    # bırakıyordu (v0.5.3 bug gate).
    try:
        shutil.copyfile(yol, yedek)
    except OSError as exc:  # shutil.SameFileError (hard link), .bak dizin, salt-okunur .bak, izin
        print("HATA: yedek alınamadı (%s → %s: %s: %s); asıl dosyaya dokunulmadı. .bak yolunu serbest bırak ya da "
              "dosyayı elle düzelt." % (yol, yedek, type(exc).__name__, exc), file=sys.stderr)
        return 2
    hata = _yaz(yol, hedef_config(kanal, no_sandbox))
    if hata:
        return _yazma_hatasi(hata, " Eski içerik yedekte: %s" % yedek)
    _cikti("YAZILDI (--zorla): %s — %s · eski içerik: %s" % (yol, _ozet(kanal, no_sandbox), yedek))
    return 0


# --------------------------------------------------------------------------- CLI

def main(argv):
    p = argparse.ArgumentParser(prog="kd_ortam.py", description="KD ortamı denetimi ve Playwright CLI yapılandırması",
                                epilog=BIND_NOTU)
    alt = p.add_subparsers(dest="komut")
    c = alt.add_parser("check", help="bağımlılık tablosu (kurmaz)")
    c.add_argument("--proje", required=True, help="UI5 uygulama dizini (package.json içeren)")
    k = alt.add_parser("config", help=".playwright/cli.config.json'u Chrome (ya da Edge) kanalına sabitler")
    k.add_argument("--proje", required=True, help="UI5 uygulama dizini")
    k.add_argument("--kanal", choices=KANALLAR, default=KANAL, help="kurulu tarayıcı kanalı (varsayılan chrome)")
    k.add_argument("--no-sandbox", action="store_true",
                   help="launchOptions.args'a --no-sandbox (aXet.code bash'i için; yalnız yerel/güvenilir sayfa)")
    k.add_argument("--zorla", action="store_true", help="farklı içerikli dosyayı ez (eskisi .bak'a)")
    try:
        a = p.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    if not a.komut:
        p.print_usage(sys.stderr)
        return 2
    proje = os.path.abspath(a.proje)
    if a.komut == "check":
        return cmd_check(proje)
    return cmd_config(proje, a.zorla, kanal=a.kanal, no_sandbox=a.no_sandbox)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
