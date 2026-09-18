#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_ui_odata_refs.py — UI5 freestyle uygulamasının OData referanslarını KAYDEDİLMİŞ `$metadata` ile
statik karşılaştırır (ÇEVRİMDIŞI — ağa çıkmaz, kimlik kullanmaz).

Kopyalanan / uyarlanan UI'larda (özellikle klasik servisten RAP servisine göç) yanlış entity set, function
import ya da property adını tarayıcıda tek tek tıklamadan, tek seferde yakalar.

`$metadata` NASIL ALINIR: geliştirici tarayıcıda (ya da kendi oturumuyla) servisin
`/sap/opu/odata/sap/<SERVIS>/$metadata` adresini açıp dosyaya kaydeder. Bu script SAP'ye BAĞLANMAZ.

Kontroller (tek VE çift tırnak — açılış ve kapanış tırnağı AYNI olmalı):
  • callFunction("/X", {...})    → X function import mı? urlParameters anahtarları FI parametresi mi?
  • .read("/X") / path:"/X" / entitySet="X" → X entity set mi? (function import ise uyarı-kırmızı)
  • {m>/X} / path:"m>/X"          → m manifest'te bir OData modeli ise X, O servisin entity set'i mi?
  • var|let|const V = "/X"        → X entity set mi? Bulunamazsa KIRMIZI DEĞİL, [?] UYARI
  • new Filter("P") / $orderby / $select → P metadata property'si mi?

ÇOK SERVİS: manifest `sap.app.dataSources` + `sap.ui5.models` ile model adı → servis haritası kurulur. JS'te
referansın ALICI ifadesi çözülür (`getModel("x")` · `getModel()` · `this._yardimci()` [gövdesi `return
...getModel("x")`] · en yakın `oX = ...` ataması · diyalog için en yakın `oX.setModel(...)`). Modeli statik
çözülemeyen referans ANA servise karşı ölçülür ve sayısı beyan edilir.

Kullanım:
  python check_ui_odata_refs.py --app <uygulama_klasörü> --metadata <ana_servis_metadata.xml>
         [--service <ANA_SERVIS>] [--metadata-for <SERVIS>=<dosya>]...
  (--service yoksa manifest `mainService` uri'sinden çıkarılır)

Çıkış: 0 KIRMIZI yok (hüküm satırını OKU: TEMİZ / eksen ÖLÇÜLMEDİ / UYARI)
       1 en az bir KIRMIZI (yapısal) uyumsuzluk
       2 ÖLÇEMEDİM (yol yok · taranacak dosya yok · servis adı çözülemedi · metadata dosyası yok/EDMX değil ·
         KIRMIZI yokken ikincil servis metadata'sı verilmedi)
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

JS_KEYS = {"method", "headers", "success", "error", "urlParameters", "filters", "sorters"}
KAPSANAN = ("webapp/controller/*.js", "webapp/view/*.xml", "webapp/fragment/*.xml")
BIRIM = "UI dosyası [" + " · ".join(KAPSANAN) + "]"

RE_CALLFN = re.compile(r'callFunction\(\s*(["\'])/([A-Za-z0-9_]+)\1\s*,\s*\{(.*?)\n\s*\}\s*\)', re.S)
RE_READ = re.compile(r'\.read\(\s*(["\'])/([A-Za-z0-9_]+)\1')
RE_PATH = re.compile(r'path:\s*(["\'])/([A-Za-z0-9_]+)\1')
RE_ENTITYSET = re.compile(r'(?:entitySet|EntitySet)=(["\'])([A-Za-z0-9_]+)\1')
RE_FILTER = re.compile(r'new Filter\(\s*(["\'])([A-Za-z_][A-Za-z0-9_]*)\1')
RE_ORDERBY = re.compile(r'\$orderby["\']?\s*:\s*(["\'])((?:(?!\1).)+)\1')
RE_SELECT = re.compile(r'\$select["\']?\s*:\s*(["\'])((?:(?!\1).)+)\1')
RE_DEGISKEN = re.compile(
    r'\b(?:var|let|const)\s+[A-Za-z_$][\w$]*\s*=\s*(["\'])/([A-Z][A-Za-z0-9_]*)\1\s*[;,\n]')
RE_ISIMLI_PATH = re.compile(r'path:\s*(["\'])([A-Za-z0-9_]+)>/([A-Za-z0-9_]+)\1')
RE_ISIMLI_SUSLU = re.compile(r'\{\s*([A-Za-z0-9_]+)>/([A-Za-z0-9_]+)\s*\}')
RE_FILTER_DEGISKEN = re.compile(r'new Filter\(\s*(?!["\'{])[A-Za-z_$][\w$.]*\s*,')
RE_LITERAL = re.compile(r'(["\'])/([A-Z][A-Za-z0-9_]*)\1')
RE_SERVIS_URI = re.compile(r'^/sap/opu/odata/sap/([^/"?]+)/?$', re.I)

ENTITY_DESENLERI = ".read('/X') · path: '/X' · entitySet='X' · var X = '/X' (tek/çift tırnak)"
ODATA_METOTLARI = {"read", "callFunction", "create", "update", "remove", "createKey"}
BAGLAMA_METOTLARI = {"bindAggregation", "bindRows", "bindItems", "bindList", "bindElement", "bindObject"}
RX_GETMODEL = re.compile(r'getModel\((?:(["\'])([A-Za-z0-9_]+)\1)?\)$')
RX_YARDIMCI = re.compile(r'(?:[A-Za-z_$][\w$]*\.)?([A-Za-z_$][\w$]*)\(\)')
RX_TANIMLAYICI = re.compile(r'(?:(?:this|that|me|self)\.)?[A-Za-z_$][\w$]*')


def metadata_oku(yol: str) -> tuple[str | None, str | None]:
    """(md, None) ya da (None, neden). EDMX olmayan içerik (giriş sayfası vb.) ölçüm DEĞİLDİR."""
    try:
        with open(yol, encoding="utf-8-sig", errors="replace") as f:
            md = f.read()
    except OSError as exc:
        return None, f"dosya okunamadı ({type(exc).__name__}): {yol}"
    if "<edmx:Edmx" not in md:
        return None, f"içerik EDMX değil (giriş/hata sayfası kaydedilmiş olabilir): {yol}"
    return md, None


def parse_metadata(md: str):
    entitysets = set(re.findall(r'<EntitySet Name="([^"]+)"', md))
    funcimports = {}
    for m in re.finditer(r'<FunctionImport Name="([^"]+)"(.*?)</FunctionImport>', md, re.S):
        funcimports[m.group(1)] = set(re.findall(r'<Parameter Name="([^"]+)"', m.group(2)))
    for m in re.finditer(r'<FunctionImport Name="([^"]+)"[^>]*/>', md):
        funcimports.setdefault(m.group(1), set())
    allprops = set(re.findall(r'<Property Name="([^"]+)"', md))
    return entitysets, funcimports, allprops


def model_haritasi(app: str):
    p = os.path.join(app, "webapp", "manifest.json")
    if not os.path.isfile(p):
        return {}, "manifest.json YOK"
    try:
        with open(p, encoding="utf-8-sig") as f:
            m = json.load(f)
    except (OSError, ValueError) as exc:
        return {}, f"manifest.json okunamadı ({type(exc).__name__})"
    servis_ds = {}
    for ad, d in ((m.get("sap.app") or {}).get("dataSources") or {}).items():
        if isinstance(d, dict) and (d.get("type") or "OData") == "OData":
            u = RE_SERVIS_URI.match(d.get("uri") or "")
            if u:
                servis_ds[ad] = u.group(1)
    harita = {}
    for ad, mdl in ((m.get("sap.ui5") or {}).get("models") or {}).items():
        if isinstance(mdl, dict) and mdl.get("dataSource") in servis_ds:
            harita[ad] = servis_ds[mdl["dataSource"]]
    return harita, ""


def maske(txt: str) -> str:
    """Aynı uzunlukta kopya: yorum ve string İÇERİĞİ boşluk (tırnaklar yerinde). Yalnız alıcı yapısı için."""
    out = list(txt)
    i, n, durum = 0, len(txt), None
    while i < n:
        c = txt[i]
        if durum is None:
            if c in "\"'`":
                durum = c
            elif c == "/" and i + 1 < n and txt[i + 1] in "/*":
                durum = "//" if txt[i + 1] == "/" else "/*"
                out[i] = out[i + 1] = " "
                i += 1
        elif durum == "//":
            if c == "\n":
                durum = None
            else:
                out[i] = " "
        elif durum == "/*":
            if c == "*" and i + 1 < n and txt[i + 1] == "/":
                out[i] = out[i + 1] = " "
                durum = None
                i += 1
            elif c != "\n":
                out[i] = " "
        else:
            if c == "\\" and i + 1 < n:
                out[i] = out[i + 1] = " "
                i += 1
            elif c == durum:
                durum = None
            elif c != "\n":
                out[i] = " "
        i += 1
    return "".join(out)


def _alici_basi(mk: str, bitis: int):
    j = bitis
    while True:
        while j > 0 and mk[j - 1].isspace():
            j -= 1
        while j > 0 and mk[j - 1] == ")":
            derin, k = 0, j
            while k > 0:
                k -= 1
                if mk[k] == ")":
                    derin += 1
                elif mk[k] == "(":
                    derin -= 1
                    if derin == 0:
                        break
            if derin != 0:
                return None
            j = k
            while j > 0 and mk[j - 1].isspace():
                j -= 1
        k = j
        while k > 0 and (mk[k - 1].isalnum() or mk[k - 1] in "_$"):
            k -= 1
        if k == j:
            return None if j == bitis else j
        j = k
        k = j
        while k > 0 and mk[k - 1].isspace():
            k -= 1
        if k > 0 and mk[k - 1] == ".":
            j = k - 1
            continue
        return j


def _ifade(txt: str, bas: int, bitis: int) -> str:
    return re.sub(r"\s+", "", txt[bas:bitis])


def _coz(ifade, txt, konum, derinlik=0):
    """Alıcı ifadesi → model adı ("" = varsayılan model) ya da None (statik çözülemedi)."""
    if derinlik > 3 or not ifade:
        return None
    m = RX_GETMODEL.search(ifade)
    if m:
        return m.group(2) or ""
    m = RX_YARDIMCI.fullmatch(ifade)
    if m:
        d = re.search(r'\b' + re.escape(m.group(1)) +
                      r'\s*(?::\s*function\s*)?\(\s*\)\s*\{\s*return\s+([^;{}]+?)\s*;?\s*\}', txt)
        return _coz(re.sub(r"\s+", "", d.group(1)), txt, d.start(), derinlik + 1) if d else None
    if RX_TANIMLAYICI.fullmatch(ifade):
        atamalar = [a for a in re.finditer(r'(?<![\w$.])' + re.escape(ifade) +
                                           r'\s*=(?![=>])\s*([^;\n]+)', txt) if a.start() < konum]
        if atamalar:
            a = atamalar[-1]
            return _coz(re.sub(r"\s+", "", a.group(1)), txt, a.start(), derinlik + 1)
    return None


def _setmodel_coz(alici, txt, konum):
    if not RX_TANIMLAYICI.fullmatch(alici):
        return None
    adaylar = [s for s in re.finditer(r'(?<![\w$.])' + re.escape(alici) + r'\.setModel\(([^,;]*?)\)\s*;', txt)
               if s.start() < konum]
    if not adaylar:
        return None
    s = adaylar[-1]
    return _coz(re.sub(r"\s+", "", s.group(1)), txt, s.start())


def cagri_modeli(txt, mk, konum):
    """`konum`daki referansı saran OData/binding çağrısının modeli (None = çözülemedi)."""
    derin = {")": 0, "]": 0, "}": 0}
    j = konum
    while j > 0:
        j -= 1
        c = mk[j]
        if c in ")]}":
            derin[c] += 1
        elif c in "([{":
            kapan = {"(": ")", "[": "]", "{": "}"}[c]
            if derin[kapan]:
                derin[kapan] -= 1
                continue
            if c == "{":
                k = j
                while k > 0 and mk[k - 1].isspace():
                    k -= 1
                if k == 0 or mk[k - 1] not in "(,[:=":
                    return None
                continue
            if c == "[":
                continue
            bas = _alici_basi(mk, j)
            if bas is None:
                return None
            ifade = _ifade(txt, bas, j)
            if "." not in ifade:
                continue
            alici, metot = ifade.rsplit(".", 1)
            if metot in ODATA_METOTLARI:
                return _coz(alici, txt, bas)
            if metot in BAGLAMA_METOTLARI:
                return _setmodel_coz(alici, txt, bas)
    return None


def dogrudan_model(txt, mk, nokta):
    bas = _alici_basi(mk, nokta)
    return None if bas is None else _coz(_ifade(txt, bas, nokta), txt, bas)


def scan_ui(app: str):
    """→ (callfn, reads, props, taranan_dosya, ek). Her referans MODEL etiketi taşır ("" / ad / None)."""
    wf = os.path.join(app, "webapp")
    files = sorted(glob.glob(os.path.join(wf, "controller", "*.js"))
                   + glob.glob(os.path.join(wf, "view", "*.xml"))
                   + glob.glob(os.path.join(wf, "fragment", "*.xml")))
    callfn, reads, props = {}, set(), set()
    ek = {"degisken": set(), "filtre_degisken": 0, "diger_literal": 0, "isimli": set()}
    for f in files:
        with open(f, encoding="utf-8", errors="replace") as fh:
            txt = fh.read()
        short = os.path.relpath(f, wf).replace(os.sep, "/")
        js = f.endswith(".js")
        mk = maske(txt) if js else ""

        def model(konum, dogrudan=False, _js=js, _txt=txt, _mk=mk):
            if not _js:
                return ""
            if dogrudan:
                k = konum
                while k > 0 and _mk[k - 1].isspace():
                    k -= 1
                return dogrudan_model(_txt, _mk, k - 1) if k > 0 and _mk[k - 1] == "." else None
            return cagri_modeli(_txt, _mk, konum)

        kapsanan_tirnak = set()
        for m in RE_CALLFN.finditer(txt):
            kapsanan_tirnak.add(m.start(1))
            up = re.search(r'urlParameters:\s*\{(.*?)\}', m.group(3), re.S)
            keys = set(re.findall(r'([A-Za-z_][A-Za-z0-9_]*)\s*:', up.group(1))) if up else set()
            anahtar = (model(m.start(), dogrudan=True), m.group(2))
            callfn.setdefault(anahtar, {"keys": set(), "where": short})["keys"].update(keys)
        for rx in (RE_READ, RE_PATH, RE_ENTITYSET):
            for m in rx.finditer(txt):
                kapsanan_tirnak.add(m.start(1))
                mdl = model(m.start() + 1, dogrudan=True) if rx is RE_READ else (
                    model(m.start()) if rx is RE_PATH else "")
                reads.add((mdl, m.group(2), short))
        for m in RE_DEGISKEN.finditer(txt):
            kapsanan_tirnak.add(m.start(1))
            ad = re.match(r'\b(?:var|let|const)\s+([A-Za-z_$][\w$]*)', m.group(0)).group(1)
            kullanim = tuple(sorted({model(u.start() + 1, dogrudan=True) for u in re.finditer(
                r'\.(?:read|createKey)\(\s*' + re.escape(ad) + r'\b', txt)} - {None})) if js else ()
            ek["degisken"].add((m.group(2), short, kullanim))
        for rx in (RE_ISIMLI_PATH, RE_ISIMLI_SUSLU):
            for m in rx.finditer(txt):
                g = m.groups()[-2:]
                ek["isimli"].add((g[0], g[1], short))
        for m in RE_FILTER.finditer(txt):
            props.add((model(m.start()), m.group(2)))
        ek["filtre_degisken"] += len(RE_FILTER_DEGISKEN.findall(txt))
        for m in RE_ORDERBY.finditer(txt):
            mdl = model(m.start())
            for tok in re.split(r'[ ,]+', m.group(2)):
                tok = tok.replace("desc", "").replace("asc", "").strip()
                if tok:
                    props.add((mdl, tok))
        for m in RE_SELECT.finditer(txt):
            mdl = model(m.start())
            for tok in m.group(2).split(","):
                if tok.strip():
                    props.add((mdl, tok.strip()))
        ek["diger_literal"] += sum(1 for m in RE_LITERAL.finditer(txt) if m.start(1) not in kapsanan_tirnak)
    return callfn, reads, props, len(files), ek


def main() -> int:
    for akis in (sys.stdout, sys.stderr):
        try:
            akis.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass
    ap = argparse.ArgumentParser(description="UI5 OData referansları ↔ kaydedilmiş $metadata (çevrimdışı)")
    ap.add_argument("--app", required=True, help="uygulama klasörü (webapp'in üst dizini)")
    ap.add_argument("--metadata", required=True, help="ana servisin kaydedilmiş $metadata XML dosyası")
    ap.add_argument("--service", help="ana OData servis adı (yoksa manifest'ten)")
    ap.add_argument("--metadata-for", action="append", default=[], metavar="SERVIS=DOSYA",
                    help="ikincil servis metadata dosyası (tekrarlanabilir)")
    a = ap.parse_args()

    if not os.path.isdir(a.app):
        print(f"[FAIL] --app yolu YOK: {a.app} (çözülen: {os.path.abspath(a.app)}) — ÖLÇÜM DEĞİL (exit 2)")
        return 2
    if not os.path.isdir(os.path.join(a.app, "webapp")):
        print(f"[FAIL] webapp/ yok: {os.path.join(a.app, 'webapp')} — --app webapp'in ÜST dizini olmalı (exit 2)")
        return 2

    callfn, reads, props, taranan, ek = scan_ui(a.app)
    if taranan == 0:
        print(f"KAPSAM: 0 {BIRIM} tarandı.")
        print("\nÖLÇÜM YOK — 'TEMİZ' DEĞİL: webapp/ var ama taranacak dosya bulunamadı (exit 2).")
        return 2

    service = a.service
    if not service:
        mani = os.path.join(a.app, "webapp", "manifest.json")
        if os.path.isfile(mani):
            with open(mani, encoding="utf-8-sig", errors="replace") as fh:
                m = re.search(r'"uri":\s*"/sap/opu/odata/sap/([^/"]+)/?"', fh.read(), re.I)
            service = m.group(1) if m else None
    if not service:
        print("[FAIL] servis adı çözülemedi (--service ver) — exit 2")
        return 2

    harita, harita_notu = model_haritasi(a.app)
    cozulemedi = 0

    def servis_of(mdl):
        nonlocal cozulemedi
        if mdl == "":
            return service
        if mdl is None or mdl not in harita:
            cozulemedi += 1
            return service
        return harita[mdl]

    reads = {(servis_of(mdl), ad, sh) for mdl, ad, sh in reads}
    reads |= {(harita[mdl], ad, sh) for mdl, ad, sh in ek["isimli"] if mdl in harita}
    birlesik = {}
    for (mdl, fn), info in callfn.items():
        hedef = birlesik.setdefault((servis_of(mdl), fn), {"keys": set(), "where": info["where"]})
        hedef["keys"].update(info["keys"])
    callfn = birlesik
    props = {(servis_of(mdl), p) for mdl, p in props}
    degisken = {(ad, sh, tuple(sorted({service} | {harita.get(k, service) for k in kull})))
                for ad, sh, kull in ek["degisken"]}

    md, neden = metadata_oku(a.metadata)
    if md is None:
        print(f"[FAIL] ÖLÇEMEDİM: ana servis {service} metadata'sı — {neden} (exit 2)")
        return 2
    meta = {service: parse_metadata(md)}
    dosyalar = {}
    for x in a.metadata_for:
        if "=" not in x:
            print(f"[FAIL] --metadata-for biçimi SERVIS=DOSYA olmalı: {x} (exit 2)")
            return 2
        s, yol = x.split("=", 1)
        dosyalar[s.strip()] = yol.strip()
    alinamayan = {}
    ikincil = sorted({s for s, _, _ in reads} | {s for s, _ in callfn} | {s for s, _ in props}
                     | {s for _, _, ss in degisken for s in ss})
    for s in ikincil:
        if s in meta:
            continue
        if s not in dosyalar:
            alinamayan[s] = "metadata dosyası verilmedi (--metadata-for)"
            continue
        md2, neden2 = metadata_oku(dosyalar[s])
        if md2 is None:
            alinamayan[s] = neden2
        else:
            meta[s] = parse_metadata(md2)

    entitysets, funcimports, allprops = meta[service]
    print(f"Servis {service}: {len(entitysets)} entitySet, {len(funcimports)} functionImport, {len(allprops)} property")
    ters = {}
    for mdl, s in harita.items():
        ters.setdefault(s, []).append(mdl)
    for s in ikincil:
        if s == service:
            continue
        adlar = ", ".join(f"'{x}'" for x in sorted(ters.get(s, [])))
        if s in meta:
            es2, fi2, ap2 = meta[s]
            print(f"Servis {s} (model {adlar}): {len(es2)} entitySet, {len(fi2)} functionImport, {len(ap2)} property")
        else:
            print(f"[FAIL] ÖLÇEMEDİM: servis {s} (model {adlar}) — {alinamayan[s]} — referansları ÖLÇÜLEMEDİ")
    ikinci_ad = sorted(f"'{mdl}' -> {s}" for mdl, s in harita.items() if s != service)
    if harita_notu:
        print(f"Model haritası: {harita_notu} — tüm referanslar ANA servise karşı ölçüldü")
    elif ikinci_ad:
        print(f"Model haritası (manifest): {' · '.join(ikinci_ad)} · modeli statik çözülemeyen {cozulemedi} referans ANA servise karşı ölçüldü")
    else:
        print("Model haritası (manifest): ikincil OData modeli yok — tüm referanslar ANA servise karşı ölçüldü")
    print(f"UI kapsamı: {taranan} {BIRIM} tarandı\n")

    red = uyari = olculemedi = 0
    n_entity = len(reads) + len(degisken)

    def etiket(s):
        return "" if s == service else f" (servis {s})"

    print(f"=== callFunction -> function import ===  ({len(callfn)} callFunction tarandı)")
    if not callfn:
        print("  (0 callFunction bulundu — bu eksende kıyaslanacak referans yok)")
    for (s, fn), info in sorted(callfn.items()):
        if s not in meta:
            print(f"  [--] ÖLÇÜLEMEDİ: {fn} [{info['where']}]{etiket(s)}")
            olculemedi += 1
            continue
        fis = meta[s][1]
        if fn not in fis:
            print(f"  [X] FUNC YOK: {fn} [{info['where']}]{etiket(s)}")
            red += 1
        else:
            bad = (info["keys"] - fis[fn] - JS_KEYS) - {""}
            if bad:
                print(f"  [!] {fn}: geçersiz parametre {sorted(bad)} [{info['where']}]{etiket(s)}")
                red += 1
            else:
                print(f"  [OK] {fn}{etiket(s)}")

    print(f"\n=== read/binding -> entity set ===  ({len(reads)} binding tarandı)")
    if n_entity == 0:
        print("  0 binding tarandı — entity ekseni ÖLÇÜLMEDİ")
        print(f"  aranan desenler: {ENTITY_DESENLERI}")
    elif not reads:
        print("  (0 doğrudan binding — entity ekseni yalnız değişken yollarıyla ölçüldü, aşağıda)")
    for s, name, short in sorted(reads, key=lambda r: (r[1], r[2], r[0])):
        if s not in meta:
            print(f"  [--] ÖLÇÜLEMEDİ: {name} [{short}]{etiket(s)}")
            olculemedi += 1
            continue
        es, fis = meta[s][0], meta[s][1]
        if name in es:
            print(f"  [OK] {name}{etiket(s)}")
        elif name in fis:
            print(f"  [!] {name}: function import (read değil callFunction olmalı) [{short}]{etiket(s)}")
            red += 1
        else:
            print(f"  [X] ENTITY SET YOK: {name} [{short}]{etiket(s)}")
            red += 1

    if degisken:
        print(f"\n=== değişkene atanmış yol (var X = '/Ad') -> entity set ===  ({len(degisken)} aday tarandı)")
        for name, short, servisler in sorted(degisken):
            sira = [service] + [x for x in servisler if x != service]
            bulunan = [s for s in sira if s in meta and name in meta[s][0]]
            if bulunan:
                print(f"  [OK] {name} [{short}]{etiket(bulunan[0])}")
            else:
                neden_d = "function import" if name in funcimports else "servis metadata'sında yok"
                print(f"  [?] UYARI {name}: {neden_d} — değişken başka modele gidiyor olabilir [{short}]")
                uyari += 1

    print(f"\n=== property (Filter/$orderby/$select) ===  ({len(props)} property tarandı)")
    unknown = sorted((p, s) for s, p in props if s in meta and p not in meta[s][2])
    kayip = sorted((p, s) for s, p in props if s not in meta)
    if not props:
        print("  0 property tarandı — property ekseni ÖLÇÜLMEDİ")
    elif unknown or kayip:
        for p, s in unknown:
            print(f"  [X] property YOK: {p}{etiket(s)}")
            red += 1
        for p, s in kayip:
            print(f"  [--] ÖLÇÜLEMEDİ: property {p}{etiket(s)}")
            olculemedi += 1
    else:
        print("  [OK] hepsi metadata'da")

    olculmeyen = [e for e, n in (("entity", n_entity), ("property", len(props))) if n == 0]
    print("\n=== BAKILMAYANLAR — bu araç aşağıdakileri ÖLÇMEZ ===")
    if olculmeyen:
        print(f"  · eksen: {' + '.join(olculmeyen)} — 0 referans görüldü (desen körlüğü olabilir)")
    print(f"  · {ek['filtre_degisken']} değişkenli new Filter(<değişken>, ...) çağrısı — property adı statik çözülmüyor")
    print("  · view/fragment {Prop} binding'leri — property ekseninde TARANMIYOR")
    print(f"  · {ek['diger_literal']} diğer '/Ad' literali (JSON model yolu · nesne alanı · fonksiyon argümanı) — entity sayılmadı")
    print(f"  · {' · '.join(KAPSANAN)} DIŞINDAKİ dosyalar (Component.js · model/* · util/* · alt klasörler)")
    print("  · kaydedilmiş $metadata dosyasının CANLI servisle güncelliği (dosyayı değişiklikten sonra yeniden kaydet)")
    if alinamayan:
        print(f"  · {olculemedi} referans ÖLÇÜLEMEDİ — ikincil servis metadata'sı yok: {', '.join(sorted(alinamayan))}")

    if red:
        hukum = f"{red} KIRMIZI uyumsuzluk" + (f" · {olculemedi} referans ÖLÇÜLEMEDİ" if olculemedi else "")
    elif olculemedi:
        hukum = f"ÖLÇEMEDİM (kısmi) — KIRMIZI YOK ama {olculemedi} referans ÖLÇÜLEMEDİ (ikincil servis metadata'sı yok)"
    elif olculmeyen:
        hukum = f"KIRMIZI YOK — TEMİZ DEĞİL: {' + '.join(olculmeyen)} ekseni ÖLÇÜLMEDİ"
    elif uyari:
        hukum = f"KIRMIZI YOK — {uyari} UYARI (değişken yolu servis metadata'sında yok)"
    else:
        hukum = "TEMİZ"
    print(f"\n{hukum} ({taranan} {BIRIM} tarandı)")
    return 1 if red else (2 if olculemedi else 0)


if __name__ == "__main__":
    raise SystemExit(main())
