#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Freestyle UI5 şablonu (`templates/ui5-freestyle/`) — kopya + sürüm parçası sözleşmesi (çevrimdışı, statik).

Her sürüm (1.120 · 1.71) için `app/` geçici bir klasöre kopyalanır, `surum/<v>/webapp/` üstüne bindirilir ve kopya
üzerinde ölçülür (README §4 · §6):
  V1  skill'in statik kontrolleri kopyayı tarar (KAPSAM sayısı = kopyadaki dosya sayısı > 0) ve temiz der
  V2  ortak gövdede (parçanın GETİRMEDİĞİ dosyalar) sürüme bağlı API adı YOK (yorumlar hariç)
  V3  ortak gövdenin çağırdığı her `SurumParca` üyesi parçada var (+ bilinen sekiz üye)
  V4  rota hedefi → view · view → controller · `.onX` işleyicisi → controller · uygulama-içi define → dosya
  V5  kullanılan i18n anahtarları (+ dinamik önek) iki dilde var; EN/TR anahtar kümesi aynı
  V6  `index.html` parçadan gelir; bootstrap özniteliği 1.71'de tek kelime, 1.120'de kebab
  V7  manifest `sap.app.i18n` dizgi · V8 Spreadsheet `dataSource` `dataUrl`'li nesne değişmezi
  V9  tarih `strictParsing: true` · sayı `parseAsString: true` · V10 kolon kutusu düz arama + Filtre… penceresi
  N1-N3 bilinen kusur kopyaya sokulunca ilgili kontrol ISIRIR (kontrol grubu)
  SIZINTI şablonda kaynak çekirdek / iç yol / iç kayıt numarası izi YOK
KAPSAM — bakılmayan: tarayıcıda çalışma (README §0 — ÖLÇÜLMEDİ) · gerçek backend · 1.72–1.119 ara sürümleri ·
iki sürümde de var olan bir API'nin farklı davranışı (V2 bir AD listesidir).
"""
from __future__ import annotations

import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

import _helpers as H

SABLON = H.SKILL / "templates" / "ui5-freestyle"
SURUMLER = ("1.120", "1.71")
NS_YOL = "com/example/alan/uygulama/"
NS_NOKTA = "com.example.alan.uygulama."
YASAK = tuple((d, re.compile(re.escape(d))) for d in (
    "IllustratedMessage", "rowmodes", "sap/m/VariantManagement", "sap.m.VariantManagement",
    "IAsyncContentCreation", "addValidateToken", "_validateOnPaste",
    "data-sap-ui-", '"bundleUrl"', "rowsUpdated", "_addFilterMenuItem")) + (
    ('getSortOrder() == "None"', re.compile(r"""getSortOrder\(\)\s*[!=]==?\s*["']None["']""")),)
PARCA_UYELERI = ("surum", "satirModu", "bosDurum", "yapistirmaBagla", "bilesenArayuzleri", "siraliMi",
                 "dogrulayiciMetni", "filtreMenusuneEkle")
KOSUL_YAZIMI_SATIRI = r"var KOSUL_YAZIMI = /^[=!<>*]|\.\.|\*/;"
BOOT_ZORUNLU = {"1.71": {"oninit", "resourceroots", "compatversion"},
                "1.120": {"on-init", "resource-roots", "compat-version"}}
# Şablon public bir depoya gider: kaynak çekirdeğin adı/yolları ve iç kayıt numaraları YAZILMAZ.
# Dizgeler parçalanarak yazılır: bu dosyanın kendisi depo genelindeki yasak dizge taramasında eşleşmesin.
SIZINTI = re.compile("DEV" + "_CORE" + r"|\bPRO" + r"VA\b|TD_" + r"S4HANA|core/scripts|std/03|playbook[/ §]"
                     r"|Issue #\d|\bADR \d{4}|SOURCE_CODES|CLAU" + "DE")


def oku(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def yorumsuz(p: Path) -> str:
    """Yorumsuz metin: kurallar KODU ölçer (şablon yorumları sürüm API'lerini bilerek ADIYLA anar)."""
    s = oku(p)
    if p.suffix == ".js":
        s = re.sub(r"/\*.*?\*/", "", s, flags=re.S)
        s = re.sub(r"(?m)(^|\s)//.*$", r"\1", s)
    elif p.suffix in {".xml", ".html"}:
        s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    elif p.suffix in {".yaml", ".properties"}:
        s = re.sub(r"(?m)^\s*#.*$", "", s)
    return s


def parca_kumesi(surum: str) -> set[str]:
    kok = SABLON / "surum" / surum
    return {p.relative_to(kok).as_posix() for p in (kok / "webapp").rglob("*") if p.is_file()}


def kur(kok: Path, surum: str) -> Path:
    hedef = kok / f"sablon_{surum.replace('.', '_')}"
    shutil.copytree(SABLON / "app", hedef)
    shutil.copytree(SABLON / "surum" / surum / "webapp", hedef / "webapp", dirs_exist_ok=True)
    return hedef


def nesne_degismezi(s: str, i: int) -> str | None:
    if i >= len(s) or s[i] != "{":
        return None
    derinlik, tirnak = 0, None
    for j in range(i, len(s)):
        c = s[j]
        if tirnak:
            if c == tirnak and s[j - 1] != "\\":
                tirnak = None
            continue
        if c in "\"'":
            tirnak = c
        elif c == "{":
            derinlik += 1
        elif c == "}":
            derinlik -= 1
            if derinlik == 0:
                return s[i:j + 1]
    return None


def i18n_anahtarlari(p: Path) -> set[str]:
    return {ln.split("=", 1)[0].strip() for ln in oku(p).splitlines()
            if ln.strip() and not ln.strip().startswith("#") and "=" in ln}


def kullanilan_anahtarlar(webapp: Path) -> set[str]:
    out: set[str] = set()
    for p in webapp.rglob("*"):
        if p.suffix == ".xml":
            out |= set(re.findall(r"i18n>([\w.]+)", oku(p)))
        elif p.suffix == ".js":
            s = oku(p)
            out |= set(re.findall(r'(?:i18n|_txt|getText)\(\s*"([\w.]+)"', s))
            out |= set(re.findall(r'\b(?:i18n|lbl)\s*:\s*"([\w.]+)"', s))
        elif p.name == "manifest.json":
            out |= set(re.findall(r"\{\{(\w+)\}\}", oku(p)))
    return out


def sayi(kok: Path, suz) -> int:
    return sum(1 for p in kok.rglob("*") if p.is_file() and suz(p))


class _SablonTaban(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kok = Path(tempfile.mkdtemp(prefix="ui5sablon_"))
        cls.app = {v: kur(cls.kok, v) for v in SURUMLER}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.kok, ignore_errors=True)

    def sonuc(self, ad, ok, detay=""):
        H.kaydet(ad, "OK", "OK" if ok else str(detay)[:60], ok)
        self.assertTrue(ok, f"{ad}: {detay}")


class TestSablonYapisi(_SablonTaban):
    def test_V0_sablon_ve_parcalar_var(self):
        eksik = [str(p) for p in [SABLON / "app" / "webapp" / "manifest.json", SABLON / "README.md"]
                 + [SABLON / "surum" / v / "webapp" / f for v in SURUMLER for f in ("index.html", "util/SurumParca.js")]
                 if not p.is_file()]
        self.sonuc("şablon: app/ + iki sürüm parçası + README var", not eksik, eksik)

    def test_V1_statik_kontroller_kopyayi_tarar_ve_temiz(self):
        sayicilar = {
            "check_ui5_freestyle_traps.py": lambda p: "webapp" in p.parts and p.suffix in {".js", ".xml"},
            "check_list_view_grid.py": lambda p: p.name.endswith(".view.xml"),
            "check_filter_search_pattern.py": lambda p: "webapp" in p.parts and p.suffix in {".js", ".xml"},
            "check_i18n_keys.py": None,
        }
        hata = []
        for v, app in self.app.items():
            for betik, suz in sayicilar.items():
                rc, out = H.kos(betik, app)
                m = re.search(r"KAPSAM: (\d+) ", out)
                n = int(m.group(1)) if m else None
                beklenen = sayi(app / "webapp", suz) if suz else 1
                temiz = rc == 0 and "[İHLAL]" not in out and "BLOCKER" not in out.replace("0 BLOCKER", "")
                if not temiz or n != beklenen or not n:
                    hata.append(f"{v}/{betik}: rc={rc} KAPSAM={n} beklenen={beklenen} · {out.strip()[-160:]}")
        self.sonuc("şablon V1: 4 statik kontrol iki kopyada temiz + KAPSAM eşit", not hata, hata)

    def test_SIZINTI_kaynak_izi_yok(self):
        bulgu = []
        for p in SABLON.rglob("*"):
            if p.is_file():
                for no, ln in enumerate(oku(p).splitlines(), 1):
                    if SIZINTI.search(ln):
                        bulgu.append(f"{p.relative_to(SABLON).as_posix()}:{no}")
        self.sonuc("şablon: kaynak çekirdek/iç kayıt izi YOK", not bulgu, bulgu[:5])

    def test_satir_sonu_lf(self):
        crlf = [p.relative_to(SABLON).as_posix() for p in SABLON.rglob("*") if p.is_file() and b"\r\n" in p.read_bytes()]
        self.sonuc("şablon: tüm dosyalar LF", not crlf, crlf[:5])


class TestSablonSurumYuzeyi(_SablonTaban):
    def _her_surum(self, fn):
        hatalar = []
        for v, app in self.app.items():
            h = fn(v, app, app / "webapp", parca_kumesi(v))
            hatalar += [f"[{v}] {x}" for x in h]
        return hatalar

    def test_V2_ortak_govdede_surume_bagli_api_yok(self):
        def f(v, app, w, parca):
            out, n = [], 0
            for p in app.rglob("*"):
                if not p.is_file() or p.relative_to(app).as_posix() in parca \
                        or p.suffix not in {".js", ".xml", ".json", ".html", ".yaml", ".properties"}:
                    continue
                n += 1
                s = yorumsuz(p)
                out += [f"{p.relative_to(app).as_posix()}:{d}" for d, rx in YASAK if rx.search(s)]
            return out if n else ["ortak gövdede dosya yok"]
        h = self._her_surum(f)
        self.sonuc("şablon V2: ortak gövdede sürüme bağlı API yok", not h, h[:6])

    def test_V3_parca_uyeleri_tam(self):
        def f(v, app, w, parca):
            js = oku(w / "util" / "SurumParca.js")
            uyeler = set(re.findall(r"^\s{4}(\w+)\s*:", js[js.find("return {"):], re.M))
            cagrilan = set()
            for p in w.rglob("*.js"):
                if p.name != "SurumParca.js":
                    cagrilan |= set(re.findall(r"SurumParca\.(\w+)", yorumsuz(p)))
            eksik = sorted((cagrilan | set(PARCA_UYELERI)) - uyeler)
            return ([f"eksik üye: {eksik}"] if eksik else []) + ([] if cagrilan else ["çağrı yok"])
        h = self._her_surum(f)
        self.sonuc("şablon V3: SurumParca üyeleri iki parçada tam", not h, h)

    def test_V4_rota_view_controller_isleyici_bagimlilik(self):
        def f(v, app, w, parca):
            h = []
            man = json.loads(oku(w / "manifest.json"))
            for t in man["sap.ui5"]["routing"]["targets"].values():
                if not (w / "view" / f"{t['name']}.view.xml").is_file():
                    h.append(f"hedef view yok: {t['name']}")
            kok_view = man["sap.ui5"]["rootView"]["viewName"].replace(NS_NOKTA, "").replace(".", "/") + ".view.xml"
            if not (w / kok_view).is_file():
                h.append(f"rootView yok: {kok_view}")
            taban = oku(w / "controller" / "BaseController.js")
            for vw in (w / "view").glob("*.view.xml"):
                m = re.search(r'controllerName="([^"]+)"', oku(vw))
                c = w / ((m.group(1).replace(NS_NOKTA, "").replace(".", "/") + ".controller.js") if m else "_")
                if m and not c.is_file():
                    h.append(f"controller yok: {vw.name}")
                govde = (oku(c) if c.is_file() else "") + taban
                for isl in sorted(set(re.findall(r'="\.(\w+)"', yorumsuz(vw)))):
                    if not re.search(r"\b" + isl + r"\s*:\s*function", govde):
                        h.append(f"işleyici yok: {vw.name}:{isl}")
            n_dep = 0
            for p in w.rglob("*.js"):
                m = re.search(r"sap\.ui\.define\(\s*\[(.*?)\]", oku(p), re.S)
                for d in (re.findall(r'"([^"]+)"', m.group(1)) if m else []):
                    if d.startswith(NS_YOL):
                        n_dep += 1
                        if not (w / (d[len(NS_YOL):] + ".js")).is_file():
                            h.append(f"bağımlılık yok: {p.name}→{d}")
                    elif d.startswith("./"):
                        n_dep += 1
                        if not (p.parent / (d[2:] + ".js")).is_file():
                            h.append(f"bağımlılık yok: {p.name}→{d}")
            return h + ([] if n_dep else ["uygulama-içi bağımlılık sayısı 0"])
        h = self._her_surum(f)
        self.sonuc("şablon V4: rota/view/controller/işleyici/define çözülür", not h, h[:6])

    def test_V5_i18n_iki_dilde(self):
        def f(v, app, w, parca):
            en = i18n_anahtarlari(w / "i18n" / "i18n.properties")
            tr = i18n_anahtarlari(w / "i18n" / "i18n_tr.properties")
            kul_ham = kullanilan_anahtarlar(w)
            onekler = {k for k in kul_ham if k.endswith(".")}
            kul = kul_ham - onekler
            h = [f"EN eksik: {sorted(kul - en)[:5]}"] if kul - en else []
            h += [f"TR eksik: {sorted(kul - tr)[:5]}"] if kul - tr else []
            h += [f"önek eksik: {o}" for o in onekler
                  if not any(k.startswith(o) for k in en) or not any(k.startswith(o) for k in tr)]
            h += [f"EN/TR farkı: {sorted(en ^ tr)[:5]}"] if en != tr else []
            return h + ([] if kul else ["kullanılan anahtar yok"])
        h = self._her_surum(f)
        self.sonuc("şablon V5: i18n anahtarları iki dilde, kümeler aynı", not h, h)

    def test_V6_index_parcadan_ve_bicim_surume_uyar(self):
        def f(v, app, w, parca):
            if "webapp/index.html" not in parca:
                return ["index.html sürüm parçasında değil"]
            adlar = set(re.findall(r"\bdata-sap-ui-([a-z][a-z-]*)\s*=", yorumsuz(w / "index.html")))
            hata = sorted(BOOT_ZORUNLU[v] - adlar)
            if v == "1.71":
                hata += sorted(a for a in adlar if "-" in a)
            return [f"uymayan/eksik öznitelik: {hata}"] if hata or not adlar else []
        h = self._her_surum(f)
        self.sonuc("şablon V6: index.html parçadan, öznitelik biçimi sürüme uyar", not h, h)

    def test_V7_manifest_i18n_dizgi(self):
        h = self._her_surum(lambda v, app, w, parca: [] if isinstance(
            json.loads(oku(w / "manifest.json"))["sap.app"].get("i18n"), str) else ["sap.app.i18n dizgi değil"])
        self.sonuc("şablon V7: manifest sap.app.i18n dizgi", not h, h)

    def test_V8_spreadsheet_datasource_nesne(self):
        def f(v, app, w, parca):
            h, n = [], 0
            for p in app.rglob("*.js"):
                if p.relative_to(app).as_posix() in parca:
                    continue
                s = yorumsuz(p)
                if "Spreadsheet" not in s:
                    continue
                for m in re.finditer(r"\bdataSource\s*:\s*", s):
                    n += 1
                    lit = nesne_degismezi(s, m.end())
                    if lit is None or not re.search(r"\bdataUrl\s*:", lit):
                        h.append(f"{p.name}: dataSource: {s[m.end():m.end() + 24]!r}")
            return h if n else ["Spreadsheet dataSource bulunamadı"]
        h = self._her_surum(f)
        self.sonuc("şablon V8: Spreadsheet dataSource dataUrl'li nesne", not h, h)

    def test_V9_tarih_siki_sayi_dizgi(self):
        def f(v, app, w, parca):
            h, n_dt, n_fl = [], 0, 0
            for p in app.rglob("*.js"):
                if p.relative_to(app).as_posix() in parca:
                    continue
                s = yorumsuz(p)
                for m in re.finditer(r"\bgetDateInstance\(", s):
                    n_dt += 1
                    if not re.search(r"\bstrictParsing\s*:\s*true\b", s[m.end():s.find(")", m.end())]):
                        h.append(f"{p.name}: getDateInstance strictParsing'siz")
                for m in re.finditer(r"\bgetFloatInstance\(", s):
                    n_fl += 1
                    if not re.search(r"\bparseAsString\s*:\s*true\b", s[m.end():s.find(")", m.end())]):
                        h.append(f"{p.name}: getFloatInstance parseAsString'siz")
            return h + ([] if n_dt else ["getDateInstance yok"]) + ([] if n_fl else ["getFloatInstance yok"])
        h = self._her_surum(f)
        self.sonuc("şablon V9: tarih strictParsing, sayı parseAsString", not h, h)

    def test_V10_kolon_kutusu_duz_arama_pencere_kablolu(self):
        def f(v, app, w, parca):
            tp = yorumsuz(w / "util" / "TablePersonalizer.js")
            i0 = tp.find("_onColumnFilter:")
            i1 = tp.find("_applyAllFilters:", i0)
            govde_cf = tp[i0:i1] if 0 <= i0 < i1 else ""
            cfp = yorumsuz(w / "util" / "ColumnFilterParser.js")
            k0 = cfp.find("function kutuDugumu(")
            k1 = cfp.find("function imza(", k0)
            govde_kd = cfp[k0:k1] if 0 <= k0 < k1 else ""
            i_red = govde_kd.find('if (KOSUL_YAZIMI.test(s)) { return hata("kosulYazimi"); }')
            i_coz = govde_kd.find("degerCoz(")
            h = []
            if "ColumnFilterParser.kutuDugumu(" not in govde_cf or "_parseSearchTerm" in tp:
                h.append("kutu kutuDugumu ile ayrıştırılmıyor ya da _parseSearchTerm var")
            if not (0 <= i_red < i_coz) or KOSUL_YAZIMI_SATIRI not in cfp:
                h.append(f"koşul yazımı değer ayrıştırmadan önce reddedilmiyor (red@{i_red} coz@{i_coz})")
            h += [f"eksik kablo: {c}" for c in ("attachColumnMenuOpen(", "SurumParca.filtreMenusuneEkle(",
                                                 "KolonFiltrePenceresi.ac(") if c not in tp]
            return h
        h = self._her_surum(f)
        self.sonuc("şablon V10: kutu düz arama, koşul reddi, Filtre… kablolu", not h, h)


class TestSablonKontrolGrubu(unittest.TestCase):
    """N1-N3: bilinen kusur 1.120 kopyasına sokulunca ilgili statik kontrol ISIRIR (V1'in körleşmediği)."""

    def _neg(self, ad, betik, dosya, degistir):
        kok = Path(tempfile.mkdtemp(prefix="ui5sablon_neg_"))
        try:
            app = kur(kok, "1.120")
            p = app / "webapp" / dosya
            eski = oku(p)
            yeni = degistir(eski)
            self.assertNotEqual(eski, yeni, f"{ad}: kusur sokulamadı ({dosya})")
            p.write_text(yeni, encoding="utf-8", newline="\n")
            rc, out = H.kos(betik, app)
        finally:
            shutil.rmtree(kok, ignore_errors=True)
        ok = rc != 0 and "Traceback" not in out
        H.kaydet(ad, "rc≠0", f"rc={rc}", ok)
        self.assertTrue(ok, f"{ad}: rc={rc}\n{out}")

    def test_N1_case_sensitive_false(self):
        self._neg("şablon N1: caseSensitive:false → filtre kontrolü ısırır", "check_filter_search_pattern.py",
                  "controller/List.controller.js", lambda s: s.replace(
                      "return new Filter(sProp, sOp, v1);",
                      "return new Filter({ path: sProp, operator: sOp, value1: v1, caseSensitive: false });", 1))

    def test_N2_liste_sap_m_table(self):
        def degistir(s):
            s = re.sub(r"<table:Table\b.*?</table:Table>",
                       '<Table id="listTable" items="{/ZSD001_C_LIST}"><columns>'
                       + "".join(f'<Column><Text text="k{i}"/></Column>' for i in range(7))
                       + "</columns></Table>", s, count=1, flags=re.S)
            return s.replace('xmlns:table="sap.ui.table"', "")
        self._neg("şablon N2: liste sap.m.Table → grid kontrolü ısırır", "check_list_view_grid.py",
                  "view/List.view.xml", degistir)

    def test_N3_v2_nav_alt_cizgi(self):
        self._neg("şablon N3: '/_Item' V2 nav → traps T1 ısırır", "check_ui5_freestyle_traps.py",
                  "controller/Change.controller.js", lambda s: s.replace(
                      'mParams["$expand"] = C.nav;', 'mParams["$expand"] = C.nav; var sYanlis = "/_Item";', 1))


class TestSablonAnahtarKacisi(unittest.TestCase):
    """Change.controller.js `_rootPath` / `_childPath`: OData V2 anahtar dizgisindeki `'` → `''` (HER anahtar parçası).

    aXet tur 8 bug-gate: `_childPath` `sKey`'i kaçırıyor `sItem`'ı kaçırmıyordu ⇒ `'` taşıyan kalem anahtarı bozuk
    URL üretir. Ölçüm controller'ı node'da `sap.ui.define` taklidiyle YÜKLEYİP işlevi çağırır (metin araması değil)."""

    KOS = r"""
var fs = require("fs");
var f;
global.sap = { ui: { define: function (d, g) { f = g; } } };
eval(fs.readFileSync(process.argv[2], "utf8"));
var C = { root: "/Root", child: "/Child", key: "K", childKey: "I", nav: "to_Item" };
var o = f({ extend: function (n, m) { return m; } }, { CHANGE: C }, function () {}, {});
process.stdout.write(JSON.stringify([o._rootPath("a'b"), o._childPath("a'b", "x'y")]));
"""

    def test_K1_kalem_anahtari_da_kacirilir(self):
        import subprocess
        node = shutil.which("node")
        if not node:
            self.skipTest("node yok — anahtar kaçışı ÖLÇÜLEMEDİ")
        kok = Path(tempfile.mkdtemp(prefix="ui5sablon_kacis_"))
        try:
            betik = kok / "kos.js"
            betik.write_text(self.KOS, encoding="utf-8")
            for surum in SURUMLER:
                with self.subTest(surum=surum):
                    ctrl = kur(kok, surum) / "webapp" / "controller" / "Change.controller.js"
                    r = subprocess.run([node, "--check", str(ctrl)], capture_output=True, text=True,
                                       encoding="utf-8", errors="replace", timeout=60)
                    self.assertEqual(r.returncode, 0, r.stderr)
                    r = subprocess.run([node, str(betik), str(ctrl)], capture_output=True, text=True,
                                       encoding="utf-8", errors="replace", timeout=60)
                    self.assertEqual(r.returncode, 0, r.stderr)
                    kok_yol, cocuk_yol = json.loads(r.stdout)
                    self.assertEqual(kok_yol, "/Root('a''b')")
                    self.assertEqual(cocuk_yol, "/Child(K='a''b',I='x''y')")
        finally:
            shutil.rmtree(kok, ignore_errors=True)
        H.kaydet("şablon K1: _childPath kalem anahtarı `'` kaçışı", "x''y", "eşit", True)


if __name__ == "__main__":
    unittest.main()
