# -*- coding: utf-8 -*-
"""KD ortamı — ekran görüntülü kullanıcı kılavuzu için bağımlılık denetimi ve Playwright CLI yapılandırması.

Alt komutlar:
    python kd_ortam.py check  --proje <uygulama_dizini>
        Bağımlılık tablosunu basar (node · Chrome · yerel playwright-cli · playwright-core yolu · python
        `markdown` · uygulamada @sap-ux/ui5-middleware-fe-mockserver devDependency'si + `start-mock` script'i).
        Eksik olan için kurulum KOMUTUNU yazar, KENDİSİ KURMAZ. start-mock komutundaki host/bind bayraklarını
        raporlar (değiştirmez). Yerel sunucular 127.0.0.1'e bağlanmalı: 0.0.0.0'ı dinleyen süreç şirket
        makinesinde güvenlik duvarı izni ister.
        Çıkış: 0 hepsi tamam · 2 en az bir eksik ya da kullanım hatası.

    python kd_ortam.py config --proje <uygulama_dizini> [--zorla]
        <uygulama>/.playwright/cli.config.json dosyasını Chrome kanalına sabitler. İdempotenttir.
        Farklı içerikli bir kullanıcı dosyası varsa `--zorla` verilmeden EZİLMEZ (--zorla eskisini .bak'a alır).
        Çıkış: 0 yazıldı / zaten uygun · 2 ezilmedi ya da kullanım hatası.

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
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PLAYWRIGHT_CLI_SURUM = "0.1.21"  # ölçülen sürüm; kurulum komutu bunu sabitler
KANAL = "chrome"
HEDEF_CONFIG = {"browser": {"browserName": "chromium", "launchOptions": {"channel": KANAL}}}
CONFIG_GORELI = os.path.join(".playwright", "cli.config.json")
MOCKSERVER_PAKET = "@sap-ux/ui5-middleware-fe-mockserver"
NODE_ASGARI = 18  # @playwright/cli package.json engines: node >=18

# Config dosyasından SONRA birleştirilen ve kanalı ezebilen ortam değişkenleri (coreBundle.js configFromEnv).
EZEN_ORTAM = ("PLAYWRIGHT_MCP_BROWSER", "PLAYWRIGHT_MCP_EXECUTABLE_PATH", "PLAYWRIGHT_MCP_CONFIG",
              "PLAYWRIGHT_MCP_CDP_ENDPOINT")

KAPSAM_CHECK = ("KAPSAM (SCOPE): kd_ortam check — bakılanlar: node sürümü, Chrome yürütülebilir dosyası, uygulamada "
                "yerel @playwright/cli ve playwright-core, python markdown, package.json'da %s devDependency'si ve "
                "start-mock script'i, start-mock komut metnindeki host/bind bayrakları (yalnız metin). "
                "Bakılmayanlar: Chrome'un gerçekten açılabildiği (config sonrası "
                "`playwright-cli open` ile ölçülür), mock sunucunun ayağa kalktığı, ui5-mock.yaml içeriği, mock veri "
                "dosyaları, npm ağ/proxy erişimi, ~/.playwright global config'inin etkisi (yalnız uyarılır)."
                % MOCKSERVER_PAKET)
KAPSAM_CONFIG = ("KAPSAM (SCOPE): kd_ortam config — yalnız <proje>/.playwright/cli.config.json dosyasının browser "
                 "anahtarlarına bakar. Bakılmayanlar: `playwright-cli open --browser <x>` bayrağı ve "
                 "PLAYWRIGHT_MCP_* ortam değişkenleri dosyayı EZER (yalnız uyarılır); ~/.playwright global "
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


def playwright_cli_yolu(proje):
    paket = os.path.join(proje, "node_modules", "@playwright", "cli", "package.json")
    if not os.path.isfile(paket):
        return None, None
    try:
        with open(paket, encoding="utf-8") as fh:
            surum = json.load(fh).get("version")
    except Exception:
        surum = None
    return os.path.dirname(paket), surum


def playwright_core_yolu(proje):
    for aday in (os.path.join(proje, "node_modules", "playwright-core"),
                 os.path.join(proje, "node_modules", "@playwright", "cli", "node_modules", "playwright-core")):
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


def global_config_uyarisi(env=None):
    """~/.playwright/cli.config.json varsa ve browser anahtarı taşıyorsa uyarı metni (proje dosyasının ALTINA birleşir:
    ör. executablePath orada kalırsa kanalın yerine geçer)."""
    env = os.environ if env is None else env
    ev = env.get("PWTEST_CLI_GLOBAL_CONFIG") or os.path.expanduser("~")
    yol = os.path.join(ev, ".playwright", "cli.config.json")
    if not os.path.isfile(yol):
        return None
    try:
        with open(yol, encoding="utf-8-sig") as fh:
            veri = json.load(fh)
    except Exception:
        return "global config okunamadı (%s) — içeriği elle incele" % yol
    if isinstance(veri, dict) and "browser" in veri:
        return "global config browser anahtarı taşıyor (%s) — proje dosyasının altına birleşir, incele" % yol
    return None


def ortam_uyarilari(env=None):
    env = os.environ if env is None else env
    return ["%s ortam değişkeni tanımlı — config dosyasındaki tarayıcı seçimini ezer" % k for k in EZEN_ORTAM if env.get(k)]


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

    cli_dizin, cli_surum = playwright_cli_yolu(proje)
    komut_cli = 'npm install --prefix "%s" --save-dev @playwright/cli@%s' % (proje, PLAYWRIGHT_CLI_SURUM)
    satirlar.append(("playwright-cli (yerel)", bool(cli_dizin),
                     ("%s (%s)" % (cli_surum, cli_dizin)) if cli_dizin else "YOK", None if cli_dizin else komut_cli))

    core = playwright_core_yolu(proje)
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
                         None if var else 'npm install --prefix "%s" --save-dev %s' % (proje, MOCKSERVER_PAKET)))
        scr = (pj.get("scripts") or {}).get("start-mock")
        satirlar.append(("start-mock script'i", bool(scr), scr or "YOK",
                         None if scr else "package.json → scripts.start-mock ekle (mockserver'lı yapılandırmayla "
                                          "`fiori run --config <mock-yaml>` çalıştıran script)"))
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
    cfg = config_durumu(proje)[0]
    cfg_metni = {
        "uygun": "Chrome kanalına sabit",
        "yok": "YOK → config yokken @playwright/cli varsayılanı zaten chromium + kanal chrome "
               "(validateBrowserConfig); sabitlemek için `python kd_ortam.py config --proje <dizin>` koş",
        "farkli": "Chrome'a sabit DEĞİL → `python kd_ortam.py config --proje <dizin>`",
        "bozuk": "okunamadı (JSON değil)"}
    _cikti("  %-5s %-26s %s" % ("BİLGİ", "cli.config.json (Chrome)", cfg_metni[cfg]))
    pj, _ = package_json_oku(proje)
    host_ozet, uzak = start_mock_host_tespiti(((pj or {}).get("scripts") or {}).get("start-mock"))
    _cikti("  %-5s %-26s %s" % ("UYARI" if uzak else "BİLGİ", "start-mock host/bind", host_ozet))
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

def _uygun_mu(veri):
    """Dosya zaten Chrome'a sabit mi: browserName chromium (ya da yok) + launchOptions.channel == chrome ve
    kanalı geçersiz kılan executablePath yok. Kullanıcının diğer anahtarları serbesttir."""
    if not isinstance(veri, dict):
        return False
    b = veri.get("browser")
    if not isinstance(b, dict):
        return False
    lo = b.get("launchOptions")
    if not isinstance(lo, dict):
        return False
    return (b.get("browserName", "chromium") == "chromium" and lo.get("channel") == KANAL
            and not lo.get("executablePath") and not b.get("cdpEndpoint") and not b.get("remoteEndpoint"))


def config_durumu(proje):
    """('yok'|'uygun'|'farkli'|'bozuk', yol, ham_metin)."""
    yol = os.path.join(proje, CONFIG_GORELI)
    if not os.path.isfile(yol):
        return "yok", yol, None
    with open(yol, encoding="utf-8-sig") as fh:
        ham = fh.read()
    try:
        veri = json.loads(ham)
    except ValueError:
        return "bozuk", yol, ham
    return ("uygun" if _uygun_mu(veri) else "farkli"), yol, ham


def _yaz(yol):
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    with open(yol, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(HEDEF_CONFIG, indent=2, ensure_ascii=False) + "\n")


def cmd_config(proje, zorla=False, env=None):
    _cikti(KAPSAM_CONFIG)
    if not os.path.isdir(proje):
        print("HATA: uygulama dizini yok: %s" % proje, file=sys.stderr)
        return 2
    durum, yol, ham = config_durumu(proje)
    for u in filter(None, [global_config_uyarisi(env)] + ortam_uyarilari(env)):
        _cikti("UYARI: " + u)
    if durum == "uygun":
        _cikti("ZATEN UYGUN (dokunulmadı): %s — kanal %s" % (yol, KANAL))
        return 0
    if durum == "yok":
        _yaz(yol)
        _cikti("YAZILDI: %s — kanal %s" % (yol, KANAL))
        return 0
    if not zorla:
        print("HATA: %s farklı içerikli (%s) bir kullanıcı dosyası; EZİLMEDİ. İncele, gerekiyorsa --zorla ile yeniden "
              "koş (eskisi .bak'a alınır)." % (yol, "JSON değil" if durum == "bozuk" else "Chrome'a sabit değil"),
              file=sys.stderr)
        return 2
    yedek = yol + ".bak"
    with open(yedek, "w", encoding="utf-8", newline="") as fh:
        fh.write(ham)
    _yaz(yol)
    _cikti("YAZILDI (--zorla): %s — kanal %s · eski içerik: %s" % (yol, KANAL, yedek))
    return 0


# --------------------------------------------------------------------------- CLI

def main(argv):
    p = argparse.ArgumentParser(prog="kd_ortam.py", description="KD ortamı denetimi ve Playwright CLI yapılandırması",
                                epilog=BIND_NOTU)
    alt = p.add_subparsers(dest="komut")
    c = alt.add_parser("check", help="bağımlılık tablosu (kurmaz)")
    c.add_argument("--proje", required=True, help="UI5 uygulama dizini (package.json içeren)")
    k = alt.add_parser("config", help=".playwright/cli.config.json'u Chrome kanalına sabitler")
    k.add_argument("--proje", required=True, help="UI5 uygulama dizini")
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
    return cmd_config(proje, a.zorla)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
