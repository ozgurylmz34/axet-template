#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_gui_script.py — SAP GUI script'ini (VBScript, PowerShell, Python) ÇALIŞTIRMADAN tarar.

Neden: bu template'te model SAP GUI script'ini yazar, geliştirici kontrol edip kendisi çalıştırır. Uzun bir script'te
kesin yasağa değen ya da geri alınamaz bir satır insan gözünden kaçabilir; bu denetleyici bilinen kalıpları teslimden
önce yakalar. Dosyayı yalnız metin olarak okur: hiçbir şey çalıştırmaz, import etmez, ağa ya da SAP'ye çıkmaz.

Kullanım:
  python check_gui_script.py <dosya|klasör> [<dosya> ...] [--mode okuma|akis]
  --mode verilmezse her dosyanın başlığındaki `MOD:` satırı kullanılır.
Çıkış: 0 BLOCKER yok · 1 en az bir BLOCKER · 2 kullanım hatası (yol yok, desteklenmeyen uzantı, taranacak dosya yok)

Kural listesi (BAKILANLAR) ve BAKILMAYANLAR her koşuda, bulgu olmasa da, aşağıdaki tablolardan türetilerek basılır.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HEADER_TAG = "AXET-GUI-SCRIPT"
MODES = ("okuma", "akis")
LANG_BY_SUFFIX = {".vbs": "vbs", ".vb": "vbs", ".bas": "vbs", ".ps1": "ps", ".psm1": "ps", ".py": "py"}

# İşlem kodu listeleri TAM DEĞİLDİR: yalnız burada adı geçen kodlar yakalanır.
YASAK_C_TCODES = ("SM12", "SE01", "SE03", "SE09", "SE10", "STMS", "SE21", "SE80")
YASAK_B_TCODES = ("SM30", "SM31", "SE14")
YASAK_B_KOMUTLAR = ("&SAP_EDIT",)
TABLO_GORUNTU_TCODES = ("SE16", "SE16N", "SE17")
GELISTIRME_TCODES = ("SE11", "SE24", "SE37", "SE38", "SE41", "SE51", "SE93", "SMOD", "CMOD")

# Etkileşim: ekrana veri giren, işlem tetikleyen ya da pencere durumunu değiştiren metotlar. Adların kaynağı SAP GUI
# Scripting tip kütüphanesi (references/api-objects.md); listeye fazladan ad girmesi yalnız fazladan bulgu üretir.
ETKILESIM_METOT = (
    "press", "select", "sendvkey", "starttransaction", "sendcommand", "sendcommandasync", "sendmenu",
    "modifycell", "modifycheckbox", "insertrows", "deleterows", "duplicaterows", "moverows",
    "presstoolbarbutton", "presstoolbarcontextbutton", "pressbutton", "pressbuttoncurrentcell", "pressenter",
    "pressf1", "pressf4", "presscolumnheader", "presstotalrow", "presstotalrowcurrentcell", "pressheader", "presskey",
    "doubleclick", "doubleclickcurrentcell", "doubleclicknode", "doubleclickitem", "click", "clickcurrentcell",
    "clicklink", "selectall", "selectcolumn", "deselectcolumn", "unselectcolumn", "clearselection", "selectitem",
    "selectnode", "unselectnode", "unselectall", "expandnode", "collapsenode", "changecheckbox", "setcheckboxstate",
    "setcurrentcell", "selectcontextmenuitem", "selectcontextmenuitembytext", "selectcontextmenuitembyposition",
    "selecttoolbarmenuitem", "contextmenu", "showcontextmenu", "nodecontextmenu", "itemcontextmenu",
    "headercontextmenu", "triggermodified", "setunprotectedtextpart", "setselectionindexes", "closesession",
    "closeconnection", "showmessagebox", "maximize", "iconify", "restore", "setfocus", "setkeyspace",
)
ETKILESIM_OZELLIK = (
    "text", "key", "value", "selected", "selectednode", "selectedrows", "selectedcells", "selectedcolumns",
    "currentcellrow", "currentcellcolumn", "busy", "columnorder", "opened", "range",
)
KAYDIRMA_OZELLIK = ("firstvisiblerow", "firstvisiblecolumn", "firstvisibleline", "position", "topnode")
KIMLIK_OZELLIK = ("user", "client", "systemname", "systemnumber", "systemsessionid", "applicationserver",
                  "messageserver", "group")

KURALLAR = {
    "BASLIK": ("BLOCKER", f"{HEADER_TAG} başlığı + MOD ({'|'.join(MODES)}) + GERI-ALINAMAZ satırı; okuma modunda GERI-ALINAMAZ=yok"),
    "BAGLANMA": ("BLOCKER", 'mevcut oturuma bağlanma: GetObject("SAPGUI") ya da GetROTEntry("SAPGUI") + GetScriptingEngine'),
    "BAGLANTI": ("BLOCKER", "yeni bağlantı/giriş: OpenConnection, OpenConnectionByConnectionString, saplogon, sapshcut; metinde IP adresi ya da /H/ router dizesi"),
    "KIMLIK": ("BLOCKER", "şifre/kullanıcı/client alanına ya da değişkenine sabit metin atanması"),
    "YASAK_C": ("BLOCKER", "işlem kodu: " + ", ".join(YASAK_C_TCODES)),
    "YASAK_B": ("BLOCKER", "işlem kodu: " + ", ".join(YASAK_B_TCODES) + " · komut: " + ", ".join(YASAK_B_KOMUTLAR)),
    "ETKILESIM": ("okuma=BLOCKER · akis=WARN", f"{len(ETKILESIM_METOT)} metot çağrısı + {len(ETKILESIM_OZELLIK)} özellik ataması (+ pencere Close)"),
    "KIMLIK_OKU": ("WARN", "oturum kimlik/sistem bilgisi okuma: Info." + ", Info.".join(KIMLIK_OZELLIK)),
    "TABLO_GORUNTU": ("WARN", "tablo görüntüleme işlem kodu (ADT okuması tercih + hassas veri kuralı): " + ", ".join(TABLO_GORUNTU_TCODES)),
    "GELISTIRME": ("WARN", "geliştirme işlem kodu (yasak A riski, yalnız Z obje + onay): " + ", ".join(GELISTIRME_TCODES)),
    "YENI_OTURUM": ("WARN", "CreateSession (yeni SAP GUI penceresi)"),
    "OBFUSKASYON": ("WARN", "Chr()/ChrW()/[char] ile metin kurma (içerik denetlenemez)"),
    "KAYDIRMA": ("INFO", "kaydırma özelliği ataması: " + ", ".join(KAYDIRMA_OZELLIK) + " (sunucu turu; teslim notunda 'Ekranda değişiklik: kaydırma')"),
}

BAKILMAYANLAR = [
    "İşlem kodu listeleri tam değildir; listede olmayan standart ya da Z işlem kodunun (ör. standart bakımı saran Z kodu) ne yaptığı.",
    "Çalışma zamanında üretilen değerler: dosyadan/argümandan okunan işlem kodu, değişkenlerle parça parça kurulan element ID'si; karışık tırnakla birleştirilen metin.",
    "Bir element ID'sinin hangi düğmeye/alana karşılık geldiği (bir Press kaydet mi, geri mi) ve SendVKey tuş numaralarının anlamı.",
    "Script'in çağırdığı başka dosyalar, include/dot-source edilen script'ler.",
    "Script'in gerçekten çalışıp çalışmadığı (sözdizimi, COM davranışı, doğru ekranı okuyup okumadığı): canlı çalıştırmanın yerine geçmez.",
    "Çıktı dosyasına hangi iş verisinin yazıldığı (hassas veri kararı insanda).",
]


@dataclass
class Finding:
    level: str
    rule: str
    line: int | None
    msg: str


@dataclass
class Result:
    path: str
    lang: str
    mode: str | None
    findings: list[Finding] = field(default_factory=list)

    def add(self, level: str, rule: str, line: int | None, msg: str) -> None:
        f = Finding(level, rule, line, msg)
        if not any((x.level, x.rule, x.line, x.msg) == (f.level, f.rule, f.line, f.msg) for x in self.findings):
            self.findings.append(f)

    def count(self, level: str) -> int:
        return sum(1 for f in self.findings if f.level == level)


# ---------------------------------------------------------------- metin işleme

def read_text(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16", errors="replace")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1254", errors="replace")


def strip_comments(text: str, lang: str) -> str:
    """Yorumları boşlukla değiştirir; satır sayısı korunur (satır numaraları geçerli kalır)."""
    out: list[str] = []
    in_block = False
    for line in text.splitlines():
        if lang == "ps" and in_block:
            end = line.find("#>")
            if end < 0:
                out.append("")
                continue
            line = " " * (end + 2) + line[end + 2:]
            in_block = False
        res: list[str] = []
        quote: str | None = None
        i = 0
        while i < len(line):
            ch = line[i]
            if quote:
                res.append(ch)
                if ch == quote:
                    if lang == "vbs" and line[i + 1:i + 2] == quote:  # "" = kaçışlı tırnak
                        res.append(quote)
                        i += 2
                        continue
                    quote = None
                i += 1
                continue
            if lang == "vbs":
                if ch == '"':
                    quote = ch
                elif ch == "'":
                    break
                elif not "".join(res).strip() and re.match(r"(?i)rem\b", line[i:]):
                    break
            else:
                if ch in "\"'":
                    quote = ch
                elif lang == "ps" and line.startswith("<#", i):
                    end = line.find("#>", i + 2)
                    if end < 0:
                        in_block = True
                        break
                    res.append(" " * (end + 2 - i))
                    i = end + 2
                    continue
                elif ch == "#":
                    break
            res.append(ch)
            i += 1
        out.append("".join(res))
    return "\n".join(out)


def join_concatenations(code: str, lang: str) -> str:
    """"SM" & "12" → "SM12" (VBScript &, +; PowerShell/Python +). Satır devamı (_) VBScript'te birleştirilir."""
    if lang == "vbs":
        code = re.sub(r'"\s*[&+]\s*(?:_\s*\n\s*)?"', "", code)
    else:
        code = re.sub(r'"\s*\+\s*"', "", code)
        code = re.sub(r"'\s*\+\s*'", "", code)
    return code


def literals(code: str, lang: str):
    """(satır_no, içerik) — tırnak içindeki metinler."""
    pat = r'"((?:[^"\n]|"")*)"' if lang == "vbs" else r'"([^"\n]*)"|\'([^\'\n]*)\''
    for m in re.finditer(pat, code):
        content = next((g for g in m.groups() if g is not None), "")
        yield code.count("\n", 0, m.start()) + 1, content.replace('""', '"')


def statements(code: str, lang: str):
    """(satır_no, deyim): tırnak dışındaki ':' (VBScript) / ';' (PowerShell, Python) ve VBScript Then/Else böler."""
    for no, line in enumerate(code.splitlines(), 1):
        parts: list[str] = []
        buf: list[str] = []
        quote: str | None = None
        i = 0
        while i < len(line):
            ch = line[i]
            if quote:
                buf.append(ch)
                if ch == quote:
                    quote = None
                i += 1
                continue
            if ch == '"' or (ch == "'" and lang != "vbs"):
                quote = ch
                buf.append(ch)
                i += 1
                continue
            if (ch == ":" and lang == "vbs") or (ch == ";" and lang != "vbs"):
                parts.append("".join(buf))
                buf = []
                i += 1
                continue
            if lang == "vbs":
                m = re.match(r"(?i)(then|else)\b", line[i:])
                if m and (i == 0 or not (line[i - 1].isalnum() or line[i - 1] == "_")):
                    parts.append("".join(buf))
                    buf = []
                    i += m.end()
                    continue
            buf.append(ch)
            i += 1
        parts.append("".join(buf))
        for p in parts:
            if p.strip():
                yield no, p.strip()


KONTROL_BASI = re.compile(r"(?i)^(?:if|elseif|elif|while|until|do|loop|case|select|return|and|or|not|for|foreach|assert)\b")
ATAMA = re.compile(r"(?i)^(?:set\s+)?([^=]*?)\.(\w+)\s*=(?!=)")
SIFRE_ADI = r"(?:pass(?:word|wd)?|pwd|kennwort|sifre|şifre|parola|bcode)"
KULLANICI_ADI = r"(?:user(?:name)?|kullanici|kullanıcı|uname|bname)"
CLIENT_ADI = r"(?:client|mandt|mandant)"
LHS = r"^(?:set\s+|\$)?([\w.$\[\]()\"'/\-]*?{ad}[\w.$\[\]()\"'/\-]*)\s*=(?!=)\s*"


def tcode_in(literal: str, codes: tuple[str, ...]) -> str | None:
    s = literal.strip().upper()
    m = re.fullmatch(r"(?:/[NO])?\s*([A-Z0-9_]+)", s)
    if m and m.group(1) in codes:
        return m.group(1)
    for m in re.finditer(r"/[NO]\s*([A-Z0-9_]+)", s):
        if m.group(1) in codes:
            return m.group(1)
    return None


# ---------------------------------------------------------------- denetim

def check_text(text: str, lang: str, mode_override: str | None = None, path: str = "<metin>") -> Result:
    head = "\n".join(text.splitlines()[:60])
    tag = re.search(rf"(?im)^\W*{re.escape(HEADER_TAG)}\b", head)
    mod_m = re.search(r"(?im)^\W*MOD:\s*(\S+)", head)
    geri_m = re.search(r"(?im)^\W*GERI-ALINAMAZ:[ \t]*(.*)$", head)
    header_mode = mod_m.group(1).strip().lower() if mod_m else None
    mode = mode_override or (header_mode if header_mode in MODES else None)
    res = Result(path, lang, mode)

    if not tag:
        res.add("BLOCKER", "BASLIK", 1, f"'{HEADER_TAG}' başlık satırı yok (şablon başlığını kullan)")
    if header_mode is None and not mode_override:
        res.add("BLOCKER", "BASLIK", 1, "MOD satırı yok")
    elif header_mode is not None and header_mode not in MODES:
        res.add("BLOCKER", "BASLIK", 1, f"MOD değeri geçersiz: {header_mode!r} (okuma|akis)")
    if mode_override and header_mode in MODES and header_mode != mode_override:
        res.add("INFO", "BASLIK", 1, f"--mode {mode_override} başlıktaki MOD {header_mode} değerini ezdi")
    geri = geri_m.group(1).strip() if geri_m else None
    if geri is None or geri == "":
        res.add("BLOCKER", "BASLIK", 1, "GERI-ALINAMAZ satırı yok ya da boş (yok | <adımlar>)")
    elif mode == "okuma" and geri.lower() != "yok":
        res.add("BLOCKER", "BASLIK", 1, f"okuma modunda geri alınamaz adım olamaz: GERI-ALINAMAZ: {geri}")

    code = strip_comments(text, lang)
    joined = join_concatenations(code, lang)
    low = code.lower()

    # Bağlanma / bağlantı
    attach = re.search(r"(?i)(getobject|getrotentry)\(\s*[\"']sapgui[\"']\s*\)", code) and "getscriptingengine" in low
    if not attach:
        res.add("BLOCKER", "BAGLANMA", None, 'mevcut oturuma bağlanma bloğu yok (GetObject("SAPGUI") / GetROTEntry("SAPGUI") + GetScriptingEngine)')
    for no, line in enumerate(code.splitlines(), 1):
        if re.search(r"(?i)\bopenconnection(?:byconnectionstring)?\b", line):
            res.add("BLOCKER", "BAGLANTI", no, "yeni bağlantı açma: script geliştiricinin açık oturumuna bağlanmalı")
        if re.search(r"(?i)\b(saplogon|sapshcut)\b", line):
            res.add("BLOCKER", "BAGLANTI", no, "SAP Logon/kısayol başlatma: giriş geliştiricinin işidir")
        if re.search(r"(?i)\.createsession\b", line):
            res.add("WARN", "YENI_OTURUM", no, "CreateSession: yeni pencere açar; gerekçeyi teslim notuna yaz")
        if re.search(r"(?i)\bchrw?\s*\(|\[char\]", line):
            res.add("WARN", "OBFUSKASYON", no, "Chr()/[char] ile metin kuruluyor: içerik denetlenemez, düz metin kullan")
        for m in re.finditer(r"(?i)\.info\.(\w+)\b", line):
            if m.group(1).lower() in KIMLIK_OZELLIK:
                res.add("WARN", "KIMLIK_OKU", no, f"Info.{m.group(1)} okunuyor: kimlik/sistem bilgisi çıktıya yazılmaz")

    # Metinler: işlem kodu, komut, IP, router
    for src in (code, joined):
        for no, lit in literals(src, lang):
            ln = no if src is code else None
            for rule, codes, why in (("YASAK_C", YASAK_C_TCODES, "kilit/transport/paket işlemleri kesin yasak C"),
                                     ("YASAK_B", YASAK_B_TCODES, "tablo verisi bakımı kesin yasak B"),
                                     ("TABLO_GORUNTU", TABLO_GORUNTU_TCODES, "tablo okuması ADT CLI ile yapılır; hassas veri kuralı"),
                                     ("GELISTIRME", GELISTIRME_TCODES, "standart obje değişikliği riski (yasak A); yalnız Z obje + onay")):
                hit = tcode_in(lit, codes)
                if hit:
                    level = "BLOCKER" if rule in ("YASAK_C", "YASAK_B") else "WARN"
                    where = "" if ln else " (birleştirilmiş metinde)"
                    res.add(level, rule, ln, f"işlem kodu {hit}{where}: {why}")
            for kom in YASAK_B_KOMUTLAR:
                if kom.lower() in lit.lower():
                    res.add("BLOCKER", "YASAK_B", ln, f"komut {kom}: tablo verisini düzenleme modu (kesin yasak B)")
            if re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", lit):
                res.add("BLOCKER", "BAGLANTI", ln, "metinde IP adresi: sistem adresi script'e yazılmaz")
            if "/h/" in lit.lower():
                res.add("BLOCKER", "BAGLANTI", ln, "metinde /H/ router dizesi: bağlantı bilgisi script'e yazılmaz")

    # Deyimler: kimlik ataması, etkileşim, kaydırma
    for no, st in statements(joined if lang == "vbs" else code, lang):
        if KONTROL_BASI.match(st):
            continue
        for ad, msg in ((SIFRE_ADI, "şifre"), (KULLANICI_ADI, "kullanıcı")):
            m = re.match(LHS.format(ad=ad), st, re.I)
            if m and re.match(r"[\"']", st[m.end():]):
                res.add("BLOCKER", "KIMLIK", no, f"{msg} alanına/değişkenine sabit metin atanıyor: kimlik bilgisi script'e yazılmaz")
        m = re.match(LHS.format(ad=CLIENT_ADI), st, re.I)
        if m and re.match(r"[\"']\d{3}[\"']", st[m.end():]):
            res.add("BLOCKER", "KIMLIK", no, "client numarası sabit yazılıyor")
        m = ATAMA.match(st)
        if m:
            prop = m.group(2).lower()
            if prop in ETKILESIM_OZELLIK:
                res.add("BLOCKER" if mode != "akis" else "WARN", "ETKILESIM", no, f"özellik ataması .{m.group(2)} = … (ekrana veri girer)")
            elif prop in KAYDIRMA_OZELLIK:
                res.add("INFO", "KAYDIRMA", no, f".{m.group(2)} ataması: ekranda kaydırma (sunucu turu)")
        for mm in re.finditer(r"(?i)\.(\w+)\b(?!\s*=(?!=))", st):
            if mm.group(1).lower() in ETKILESIM_METOT:
                res.add("BLOCKER" if mode != "akis" else "WARN", "ETKILESIM", no, f"etkileşim metodu .{mm.group(1)}")
        if re.search(r"(?i)(activewindow|wnd\[\d+\]|findbyid|\bsession\b|\bses\b)\S*\.close\b", st):
            res.add("BLOCKER" if mode != "akis" else "WARN", "ETKILESIM", no, "pencere/oturum kapatma (.Close)")
        for mm in re.finditer(r"(?i)invokemember\(\s*[\"'](\w+)[\"']\s*,\s*([^,]*)", st):
            name, flags = mm.group(1).lower(), mm.group(2).lower()
            if "setproperty" in flags and name in ETKILESIM_OZELLIK or "invokemethod" in flags and name in ETKILESIM_METOT:
                res.add("BLOCKER" if mode != "akis" else "WARN", "ETKILESIM", no, f"InvokeMember ile etkileşim: {mm.group(1)}")
    return res


def check_file(path: Path, mode_override: str | None = None) -> Result:
    lang = LANG_BY_SUFFIX[path.suffix.lower()]
    return check_text(read_text(path), lang, mode_override, str(path))


# ---------------------------------------------------------------- çıktı

def print_result(res: Result) -> None:
    print(f"\n== {res.path} · dil={res.lang} · mod={res.mode or 'BELİRSİZ'}")
    order = {"BLOCKER": 0, "WARN": 1, "INFO": 2}
    for f in sorted(res.findings, key=lambda x: (order.get(x.level, 9), x.line or 0, x.rule)):
        yer = f"satır {f.line}" if f.line else "dosya"
        print(f"  {f.level:<7} {f.rule:<13} {yer:<10} {f.msg}")
    print(f"  ÖZET: BLOCKER={res.count('BLOCKER')} WARN={res.count('WARN')} INFO={res.count('INFO')}")


def print_scope() -> None:
    print("\nBAKILANLAR (kural · seviye · kapsam):")
    for rule, (level, desc) in KURALLAR.items():
        print(f"  {rule:<13} {level:<24} {desc}")
    print("BAKILMAYANLAR:")
    for item in BAKILMAYANLAR:
        print(f"  - {item}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="SAP GUI script'ini çalıştırmadan tarar.")
    ap.add_argument("paths", nargs="+", help="script dosyası ya da klasör")
    ap.add_argument("--mode", choices=MODES, help="başlıktaki MOD yerine bu modu kullan")
    args = ap.parse_args(argv)

    files: list[Path] = []
    for p in map(Path, args.paths):
        if p.is_dir():
            files += sorted(f for f in p.rglob("*") if f.is_file() and f.suffix.lower() in LANG_BY_SUFFIX)
        elif p.is_file():
            if p.suffix.lower() not in LANG_BY_SUFFIX:
                print(f"HATA: desteklenmeyen uzantı: {p} (desteklenen: {', '.join(sorted(LANG_BY_SUFFIX))})")
                return 2
            files.append(p)
        else:
            print(f"HATA: yol yok: {p}")
            return 2
    if not files:
        print("HATA: taranacak script yok")
        return 2

    blockers = 0
    for f in files:
        res = check_file(f, args.mode)
        print_result(res)
        blockers += res.count("BLOCKER")
    print(f"\nTOPLAM: {len(files)} dosya · BLOCKER={blockers}")
    print_scope()
    return 1 if blockers else 0


if __name__ == "__main__":
    sys.exit(main())
