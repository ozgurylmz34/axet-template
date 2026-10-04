# -*- coding: utf-8 -*-
"""Mock sunucusunu (fe-mockserver, `npm run start-mock`) aXet'in arka plan işinden BAĞIMSIZ başlatır / durdurur (Z181).

Neden: aXet sunucuyu kendi arka plan işi olarak başlatınca Windows'ta `npm → cmd → fiori → npx → ui5 serve` zinciri
oluşur; `job_kill` yalnız en üst süreci öldürür, alttaki `node` süreçleri aXet'in çıktı borusunu açık tuttuğu için
motor "iş bitsin" diye SONSUZA DEK bekler (ölçüldü 2026-10-03: log her 5 sn "BgJob kill still waiting…", Esc de
çözmedi; 2026-09-25: süreç yaşadı, port dolu kaldı). Bu araç sunucuyu ayrı süreç grubunda, çıktısı DOSYAYA yönlenmiş
başlatır ve HAZIR olunca döner ⇒ aXet'in tuttuğu boru yoktur.

Kimlik modeli (bug gate 2026-10-03, 3 tur): `durdur` yalnız SOYU kanıtlanan süreçleri kapatır — kayıtlı ve hâlâ aynı
olan süreçler (PID + oluşturma zamanı) ve onlardan SONRA doğmuş torunları. Portu dinlemek kimlik sayılmaz (bayat kayıt,
paylaşılan port); port boşalmazsa ya da ölçülemezse "DURDU" denmez, çıkış 1.

Kullanım (aXet'te ÖN PLANDA koş — `run_in_background` YOK):
    python mock_sunucu.py baslat [--app <uygulama>] [--port N] [--zaman-asimi 90]
    python mock_sunucu.py durum  [--app <uygulama>]
    python mock_sunucu.py durdur [--app <uygulama>]
    python mock_sunucu.py yenile [--app <uygulama>] [--port N]     durdur + baslat (mock veri değişince)

Durum dosyası ve log uygulamaya YAZILMAZ: `<TEMP>/axet-mock/<anahtar>.json|.log` (anahtar = uygulama yolu özeti).
Çıkış: 0 tamam · 1 durdurulamadı / port hâlâ dolu · 2 başlamadı / ölçüm yok (log kuyruğu basılır).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

PENCERE = os.name == "nt"
# Yalnız sunucunun kendi `URL:` satırı (ui5 serve: "URL: http://localhost:<port>", ölçüldü 3/3). Log'da başka localhost
# adresleri de geçebilir (backend satırı) — ilk adresi almak yabancı bir sunucuyu "hazır" saydırıyordu (bug gate 4. tur).
URL_DESENI = re.compile(r"\bURL:\s*https?://(?:localhost|127\.0\.0\.1|\[::1\]|0\.0\.0\.0):(\d{2,5})")
KAPSAM = ("KAPSAM (SCOPE): mock_sunucu — bakılanlar: süreç canlılığı (PID + oluşturma zamanı), portun dinlenmesi, "
          "`/index.html` HTTP durumu, durdurmada portun boşalması. Bakılmayanlar: UI5 bootstrap ve `tr.json` (mock-ortam "
          "§6 ölçümü ayrıca yapılır), OData yanıtlarının doğruluğu, HAZIR portunu dinleyen sürecin soyu (port yalnız "
          "sunucunun log'daki `URL:` satırından alınır), başkasının başlattığı sunucular (yalnız bu aracın kayıtlı "
          "süreçleri ve onların soyu kapatılır; portu dinleyen ama soyu kanıtlanmayan süreç kapatılmaz).")


def _cikti_utf8():
    for akis in (sys.stdout, sys.stderr):
        try:
            akis.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass


def kayit_yollari(app: str) -> tuple[str, str]:
    anahtar = hashlib.sha1(os.path.normcase(os.path.abspath(app)).encode("utf-8")).hexdigest()[:12]
    dizin = os.path.join(tempfile.gettempdir(), "axet-mock")
    os.makedirs(dizin, exist_ok=True)
    return os.path.join(dizin, anahtar + ".json"), os.path.join(dizin, anahtar + ".log")


def kayit_oku(app: str):
    yol, _ = kayit_yollari(app)
    try:
        with open(yol, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def kayit_yaz(app: str, veri) -> None:
    yol, _ = kayit_yollari(app)
    gecici = yol + ".tmp"
    with open(gecici, "w", encoding="utf-8") as fh:
        json.dump(veri, fh, ensure_ascii=False, indent=1)
    os.replace(gecici, yol)


def kayit_sil(app: str) -> None:
    yol, _ = kayit_yollari(app)
    try:
        os.remove(yol)
    except OSError:
        pass


def port_dinleniyor(port: int) -> bool:
    for aile, adres in ((socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1")):
        try:
            with socket.socket(aile, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                if s.connect_ex((adres, port)) == 0:
                    return True
        except OSError:
            continue
    return False


def http_durum(port: int, yol: str = "/index.html") -> int | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{yol}", timeout=5) as r:
            return r.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except Exception:  # noqa: BLE001
        return None


# ───────────────────────── süreç tablosu (Windows: CIM · POSIX: ps) ─────────────────────────

def surec_tablosu() -> dict[int, dict]:
    """{pid: {"ebeveyn": ppid, "zaman": oluşturma, "komut": komut satırı}} — ölçülemezse {}."""
    try:
        if PENCERE:
            # OutputEncoding: PowerShell 5.1 boruya OEM kod sayfasıyla yazar; ASCII dışı komut satırları bozulurdu.
            betik = ("[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
                     "Get-CimInstance Win32_Process | ForEach-Object { [pscustomobject]@{p=$_.ProcessId;"
                     "e=$_.ParentProcessId;z=$(if($_.CreationDate){[string]$_.CreationDate.ToUniversalTime().Ticks}"
                     "else{''});k=$_.CommandLine} } | ConvertTo-Json -Compress")
            o = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", betik],
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
                               stdin=subprocess.DEVNULL).stdout
            veri = json.loads(o or "[]")
            veri = veri if isinstance(veri, list) else [veri]
            return {int(x["p"]): {"ebeveyn": int(x["e"] or 0), "zaman": x.get("z") or "", "komut": x.get("k") or ""}
                    for x in veri}
        o = subprocess.run(["ps", "-eo", "pid=,ppid=,lstart=,args="], capture_output=True, text=True, timeout=30,
                           env=dict(os.environ, LC_ALL="C")).stdout
        tablo = {}
        for satir in o.splitlines():
            parca = satir.split(None, 7)
            if len(parca) >= 7:
                try:  # lstart (C yerel ayarı) → epoch saniyesi: zamanlar sayı olarak karşılaştırılabilsin
                    z = str(int(time.mktime(time.strptime(" ".join(parca[2:7]), "%a %b %d %H:%M:%S %Y"))))
                except ValueError:
                    z = ""
                tablo[int(parca[0])] = {"ebeveyn": int(parca[1]), "zaman": z,
                                        "komut": parca[7] if len(parca) > 7 else ""}
        return tablo
    except Exception:  # noqa: BLE001
        return {}


def duvar_zamani(t: float) -> str:
    """time.time() → süreç tablosunun zaman biçimi (Windows: UTC .NET tick · POSIX: epoch saniyesi)."""
    return str(int(t * 10**7) + 621355968000000000) if PENCERE else str(int(t))


def _sayi(z: str):
    try:
        return int(z)
    except (TypeError, ValueError):
        return None


def sonra_dogmus(pid: int, kok_zaman: str, tablo: dict[int, dict]) -> bool:
    """`pid` kökten SONRA mı doğdu. Ölçülemiyorsa False (kimliği kanıtlanmayan süreç kapatılmaz)."""
    a, b = _sayi(kok_zaman), _sayi((tablo.get(pid) or {}).get("zaman"))
    return a is not None and b is not None and b >= a


def torunlar(kok: int, tablo: dict[int, dict], kok_zaman: str | None = None) -> list[int]:
    """Kökün alt süreçleri. Windows'ta ParentProcessId ebeveyn öldükten sonra YENİDEN KULLANILMIŞ bir PID'i gösterebilir
    ⇒ çocuk yalnız ebeveyninden sonra doğduysa (oluşturma zamanı) kabul edilir; zaman ölçülemiyorsa alınmaz.
    `kok_zaman`: kök tabloda yoksa (kapanmışsa) onun yerine kullanılan başlatma anı (`duvar_zamani`)."""
    cocuklar: dict[int, list[int]] = {}
    for pid, b in tablo.items():
        cocuklar.setdefault(b["ebeveyn"], []).append(pid)
    sonuc, yigin = [], [kok]
    while yigin:
        p = yigin.pop()
        for c in cocuklar.get(p, []):
            ebeveyn_zaman = (tablo.get(p) or {}).get("zaman") or (kok_zaman if p == kok else None)
            if c not in sonuc and c != kok and sonra_dogmus(c, ebeveyn_zaman, tablo):
                sonuc.append(c)
                yigin.append(c)
    return sonuc


def canli(kayit_pid: int, zaman: str, tablo: dict[int, dict]) -> bool:
    """PID hâlâ AYNI süreç mi (PID yeniden kullanılmış olabilir → oluşturma zamanı eşleşmeli; zaman kaydı yoksa kimlik
    kanıtlanamaz ⇒ False)."""
    b = tablo.get(kayit_pid)
    return bool(b) and bool(zaman) and b["zaman"] == zaman


# ───────────────────────── komutlar ─────────────────────────

def _baslat_komutu(port: int | None) -> list[str]:
    npm = "npm.cmd" if PENCERE else "npm"
    argv = [npm, "run", "start-mock"]
    if port:
        argv += ["--", "--port", str(port)]
    return argv


def _log_kuyrugu(log: str, n: int = 15) -> str:
    try:
        with open(log, encoding="utf-8", errors="replace") as fh:
            return "".join(fh.readlines()[-n:])
    except OSError:
        return "(log okunamadı)"


def baslat(app: str, port: int | None, zaman_asimi: float, komut: list[str] | None = None) -> int:
    app = os.path.abspath(app)
    onceki = kayit_oku(app)
    if onceki:
        tablo = surec_tablosu()
        if not tablo:
            print("[FAIL] süreç tablosu okunamadı — önceki kaydın süreçleri ÖLÇÜLEMEDİ; başlatılmadı")
            return 2
        kok_canli = canli(onceki["pid"], onceki.get("zaman", ""), tablo)
        if kok_canli and onceki.get("port") and port_dinleniyor(onceki["port"]):
            print(f"MOCK SUNUCU: ZATEN ÇALIŞIYOR · http://127.0.0.1:{onceki['port']}/index.html?sap-ui-language=tr "
                  f"· PID {onceki['pid']} · log {onceki['log']}")
            print(KAPSAM)
            return 0
        if kok_canli or any(canli(a["pid"], a.get("zaman", ""), tablo) for a in onceki.get("alt", [])):
            # Kaydı silmek yaşayan süreçleri araçla kapatılamaz hâle getirirdi (bug gate 2026-10-03).
            print("[FAIL] önceki başlatmanın süreçleri hâlâ yaşıyor ama sunucu hazır değil — önce `durdur`; başlatılmadı")
            return 2
        kayit_sil(app)
    if port and port_dinleniyor(port):
        print(f"[FAIL] port {port} zaten dolu (başka bir sunucu) — başka --port ver ya da onu kapat; başlatılmadı")
        return 2
    _, log = kayit_yollari(app)
    argv = komut or _baslat_komutu(port)
    bayrak = 0
    if PENCERE:
        bayrak = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    t0 = time.monotonic()
    baslama = duvar_zamani(time.time() - 1)  # kök kapanırsa çocuklarının kimliği buna göre (1 sn pay)
    with open(log, "w", encoding="utf-8") as fh:
        try:
            p = subprocess.Popen(argv, cwd=app, stdin=subprocess.DEVNULL, stdout=fh, stderr=subprocess.STDOUT,
                                 close_fds=True, creationflags=bayrak, start_new_session=not PENCERE)
        except OSError as exc:
            print(f"[FAIL] başlatılamadı ({type(exc).__name__}: {exc}) — komut: {' '.join(argv)}")
            return 2
    bulunan = None
    while time.monotonic() - t0 < zaman_asimi:
        if p.poll() is not None:
            # Kök kapandı ama başlattığı alt süreçler yaşıyor olabilir (Windows'ta ebeveyn PID'i kayıtlı kalır) —
            # yetim bırakılmaz; bu PID'ler kökten doğduğu için başkasının süreci değildir.
            # Windows: Popen kökün süreç tutamacını açık tuttuğu için PID'i yeniden dağıtılmaz (bug gate 2026-10-03).
            tablo = surec_tablosu()
            artik = torunlar(p.pid, tablo, baslama)
            _oldur(artik, None)
            if not PENCERE:  # POSIX: yetimler init'e devredilir (ppid 1) ⇒ ağaçtan değil süreç grubundan kapatılır
                _grubu_oldur(p.pid)
            sayi = len(artik) if tablo else "ÖLÇÜLEMEDİ (süreç tablosu okunamadı)"
            print(f"[FAIL] sunucu süreci kapandı (çıkış {p.returncode}; kapatılan alt süreç {sayi}) — log "
                  f"kuyruğu:\n{_log_kuyrugu(log)}")
            return 2
        if bulunan is None:
            # Port YALNIZ sunucunun kendi log'undaki adresten alınır: `--port` "dinleniyor" diye benimsenmez — o portu o
            # anda başka bir süreç dinliyor olabilir (bug gate 2026-10-03, 3. tur). fe-mockserver adresi basar
            # (`URL: http://localhost:<port>`, ölçüldü 3/3).
            bulunan = log_portu(log)
        if bulunan and port_dinleniyor(bulunan) and http_durum(bulunan) is not None:
            break
        time.sleep(0.5)
    else:
        # Zaman aşımında da kayıt TAM yazılır (alt süreçler + port): `durdur` onları kapatabilsin (bug gate 2026-10-03).
        kayit = _kayit_kur(app, p.pid, bulunan or log_portu(log) or port, log, argv)
        print(f"[FAIL] {int(zaman_asimi)} sn içinde hazır olmadı (port {kayit['port'] or 'bulunamadı'}) — süreç ayakta "
              f"bırakıldı (+{len(kayit['alt'])} alt süreç kayıtlı), `durdur` ile kapat. Log kuyruğu:\n{_log_kuyrugu(log)}")
        return 2
    alt = _kayit_kur(app, p.pid, bulunan, log, argv)["alt"]
    durum = http_durum(bulunan)
    print(f"MOCK SUNUCU: HAZIR · http://127.0.0.1:{bulunan}/index.html?sap-ui-language=tr · PID {p.pid} "
          f"(+{len(alt)} alt süreç) · {time.monotonic() - t0:.1f} sn · log {log}")
    if durum != 200:
        print(f"UYARI: /index.html → {durum} (200 bekleniyordu) — log'a bak")
    print(KAPSAM)
    return 0


def log_portu(log: str) -> int | None:
    m = URL_DESENI.search(_log_kuyrugu(log, 200))
    return int(m.group(1)) if m else None


def _kayit_kur(app: str, kok: int, port: int | None, log: str, argv: list[str]) -> dict:
    """Kök + kökten sonra doğmuş alt süreçleri (yalnız SOY) → kayıt. Portu dinleyen süreç kayda eklenmez: dinlemek
    kimlik değildir (bug gate 2026-10-03, 3 tur). Gerçek zincirde sunucu kökün soyundadır (ölçüldü 2026-10-04, 3/3:
    `npm → cmd → fiori → npx → ui5 serve`, 7 halka, köke ulaştı)."""
    tablo = surec_tablosu()
    kok_zaman = (tablo.get(kok) or {}).get("zaman", "")
    if not kok_zaman:
        print("UYARI: süreç kimliği (oluşturma zamanı) ÖLÇÜLEMEDİ — `durdur` süreçleri PID ile kapatmaz; port "
              "boşalmazsa elle kapat")
    alt = [{"pid": c, "zaman": tablo[c]["zaman"]} for c in torunlar(kok, tablo)]
    kayit = {"pid": kok, "zaman": kok_zaman, "port": port or 0, "app": app, "log": log, "alt": alt, "komut": argv}
    kayit_yaz(app, kayit)
    return kayit


def _grubu_oldur(pgid: int) -> None:
    try:
        os.killpg(pgid, signal.SIGKILL)
    except OSError:
        pass


def _oldur(pidler: list[int], kok: int | None) -> None:
    """Yalnız verilen PID'ler. Windows'ta `taskkill /T` KULLANILMAZ: ağacı ParentProcessId'den kurar ve yeniden
    kullanılmış PID'e işaret eden eski bir ebeveyn bağını da izler — kimlik filtresi `torunlar`dadır."""
    if PENCERE:
        for pid in ([kok] if kok else []) + list(pidler):
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, stdin=subprocess.DEVNULL)
        return
    if kok:
        try:
            os.killpg(os.getpgid(kok), signal.SIGKILL)
        except OSError:
            pass
    for pid in pidler:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass


def durdur(app: str, bekle: float = 15) -> int:
    app = os.path.abspath(app)
    k = kayit_oku(app)
    if not k:
        print("MOCK SUNUCU: kayıt yok — bu araçla başlatılmış sunucu bulunamadı (başkasının sunucusu kapatılmaz)")
        print(KAPSAM)
        return 0
    tablo = surec_tablosu()
    if not tablo:
        print("[FAIL] süreç tablosu okunamadı — hiçbir süreç kapatılmadı (ÖLÇÜLEMEDİ)")
        return 2
    # KİMLİK MODELİ (bug gate 2026-10-03, 2 tur): yalnız SOYU kanıtlanan süreç kapatılır — kayıtlı ve hâlâ AYNI olan
    # süreçler (PID + oluşturma zamanı) ve onlardan SONRA doğmuş torunları. Portu dinlemek kimlik DEĞİLDİR (bayat
    # kayıtta ya da paylaşılan portta başkasının sunucusu olabilir) ⇒ port sahibine bakarak süreç kapatılmaz.
    # Ağaç sonradan kopmuşsa (ara `cmd` kapanmış) kayıtlı alt süreçler ayrıca kapatılır. Soyu hiç kanıtlanamayan bir
    # sunucu kalırsa port boşalmaz ⇒ çıkış 1 (dürüst; kapatma kullanıcıya bırakılır).
    kok = k["pid"] if canli(k["pid"], k.get("zaman", ""), tablo) else None
    alt = [a["pid"] for a in k.get("alt", []) if canli(a["pid"], a.get("zaman", ""), tablo)]
    for dogrulanmis in ([kok] if kok else []) + list(alt):
        alt += [c for c in torunlar(dogrulanmis, tablo) if c not in alt and c != kok]
    # Zaman aşımı kaydında port 0 olabilir: sunucu adresi o arada log'a yazılmış olabilir (yalnız ÖLÇÜM için).
    port = k.get("port") or log_portu(k.get("log") or "")
    _oldur(alt, kok)
    t0 = time.monotonic()
    while time.monotonic() - t0 < bekle and port and port_dinleniyor(port):
        time.sleep(0.5)
    kapatilan = len(alt) + (1 if kok else 0)
    if not port:
        kayit_sil(app)
        print(f"[FAIL] kapatılan süreç {kapatilan}, ama sunucunun portu ÖLÇÜLEMEDİ (kayıtta da log'da da yok) — "
              f"boşaldığı doğrulanamadı; kendi terminalinde `netstat -ano` (aXet bash'inde netstat engelli) ile bak")
        return 1
    if port_dinleniyor(port):
        print(f"[FAIL] port {port} hâlâ dinleniyor — kayıtlı süreçler kapatıldı ama portu başka bir süreç tutuyor "
              f"(kendi terminalinde `netstat -ano` (aXet bash'inde netstat engelli) ile PID'e bak; komut satırında "
              f"bu uygulama yoksa o süreç senin değil)")
        return 1
    kayit_sil(app)
    print(f"MOCK SUNUCU: DURDU · kapatılan süreç {kapatilan} · port {port} boş")
    print(KAPSAM)
    return 0


def durum_goster(app: str) -> int:
    app = os.path.abspath(app)
    k = kayit_oku(app)
    if not k:
        print("MOCK SUNUCU: kayıt yok (çalışmıyor ya da bu araçla başlatılmadı)")
        return 0
    tablo = surec_tablosu()
    print(f"MOCK SUNUCU: {'ÇALIŞIYOR' if canli(k['pid'], k.get('zaman', ''), tablo) else 'süreç YOK'} · port "
          f"{k.get('port')} {'dinleniyor' if k.get('port') and port_dinleniyor(k['port']) else 'boş'} · PID {k['pid']} "
          f"· log {k.get('log')}")
    return 0


def main(argv=None) -> int:
    _cikti_utf8()
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("komut", choices=["baslat", "durum", "durdur", "yenile"])
    ap.add_argument("--app", default=".", help="uygulama klasörü (package.json + ui5-mock.yaml; vars. bulunulan dizin)")
    ap.add_argument("--port", type=int, help="sabit port (vars. sunucunun seçtiği; log'dan okunur)")
    ap.add_argument("--zaman-asimi", type=float, default=90)
    ap.add_argument("--komut-json", help=argparse.SUPPRESS)  # testler: başlatılacak komut (JSON dizi)
    a = ap.parse_args(argv)
    if a.komut in ("baslat", "yenile") and not a.komut_json and not os.path.isfile(os.path.join(a.app, "package.json")):
        print(f"[FAIL] {os.path.abspath(a.app)} içinde package.json yok — --app uygulama klasörü olmalı")
        return 2
    komut = json.loads(a.komut_json) if a.komut_json else None
    if a.komut == "durum":
        return durum_goster(a.app)
    if a.komut == "durdur":
        return durdur(a.app)
    if a.komut == "yenile":
        rc = durdur(a.app)
        if rc:
            return rc
    return baslat(a.app, a.port, a.zaman_asimi, komut)


if __name__ == "__main__":
    sys.exit(main())
