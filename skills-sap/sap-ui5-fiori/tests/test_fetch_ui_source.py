#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Z144: fetch_ui_source.py + _bspkaynak.py + ui_local_proxy.py — kaynağı yerelde olmayan UI5 uygulamasını SAP'den
salt-okuma indirme, kaynağı geri kurma, eşlik/drift ölçümü, tip-kapsamlı $metadata ve salt-okur yerel sunucu.

Ağ yalnız 127.0.0.1 sahte sunucusudur; npm/build KOŞULMAZ (`eslik --no-build`).
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

import _helpers as H

sys.path.insert(0, str(H.SCRIPTS))


def _modul(ad, dosya):
    spec = importlib.util.spec_from_file_location(ad, H.SCRIPTS / dosya)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


K = _modul("_bspkaynak_t", "_bspkaynak.py")
P = _modul("ui_local_proxy_t", "ui_local_proxy.py")
D = _modul("deploy_ui_fk_t", "deploy_ui.py")

BSP = "ZXX001_ORDER"
# Canlıda ölçülen BSP biçiminin küçük modeli: derlenmiş dist (küçültülmüş + -dbg + map + preload), CRLF saklanmış metin.
CANLI = {
    "manifest.json": b'{\r\n  "sap.app": {"id": "zxx001.order"}\r\n}\r\n',
    "index.html": b"<html>\r\n</html>\r\n",
    "Component.js": b"sap.ui.define([],function(){return 1});",
    "Component-dbg.js": b"sap.ui.define([], function () {\r\n  return 1;\r\n});\r\n",
    "Component.js.map": b'{"version":3,"sources":["Component-dbg.js"]}',
    "controller/List.controller.js": b"sap.ui.define([],function(){})",
    "controller/List-dbg.controller.js": b"sap.ui.define([], function () {\r\n});\r\n",
    "controller/List.controller.js.map": b'{"version":3,"sources":["List-dbg.controller.js"]}',
    "Component-preload.js": H.PRELOAD,
    "Component-preload.js.map": b"{}",
    "i18n/i18n.properties": b"a=b\r\n",
    "img/logo.png": b"\x89PNG\r\n\x1a\n\x00\r\n",
}


def _build_lf(d: dict) -> dict:
    """Build çıktısı taklidi: metin dosyası LF'ye iner, ikili (png) HAM kalır — gerçek build de ikiliyi kopyalar."""
    return {r: v.replace(b"\r\n", b"\n") if Path(r).suffix.lower() in K.METIN_UZANTI else v for r, v in d.items()}


def _atom(girdiler: list[tuple[str, bool]]) -> bytes:
    """ADT filestore Atom listesi: (id, klasör mü). id'ler canlıdaki gibi URL-kodlu."""
    parca = ['<feed xmlns="http://www.w3.org/2005/Atom">']
    for ad, klasor in girdiler:
        kod = ad.replace("/", "%2f")
        parca.append(f'<entry><id>{kod}</id><title>{ad}</title><category term="{"folder" if klasor else "file"}"/></entry>')
    parca.append("</feed>")
    return "".join(parca).encode()


class TestKaynakKur(unittest.TestCase):
    def test_dbg_geri_kurma(self):
        webapp, atilan, uyari = K.kaynak_kur(CANLI)
        ok = (webapp["Component.js"] == b"sap.ui.define([], function () {\n  return 1;\n});\n"
              and webapp["controller/List.controller.js"] == b"sap.ui.define([], function () {\n});\n"
              and "Component-dbg.js" not in webapp and "Component-preload.js" not in webapp
              and not any(r.endswith(".map") for r in webapp)
              and webapp["i18n/i18n.properties"] == b"a=b\n"
              and webapp["img/logo.png"] == CANLI["img/logo.png"]  # ikili dosyaya dokunulmaz
              and set(atilan) == {"Component.js", "Component.js.map", "controller/List.controller.js",
                                  "controller/List.controller.js.map", "Component-preload.js",
                                  "Component-preload.js.map"}
              and uyari == [] and K.uygulama_kimligi(webapp) == "zxx001.order")
        H.kaydet("kaynak_kur: -dbg → asıl ad, build ürünü atılır, metin LF", "8 kaynak, 6 atılan, 0 uyarı",
                 f"{len(webapp)} kaynak, {len(atilan)} atılan, {len(uyari)} uyarı", ok)
        self.assertTrue(ok, (sorted(webapp), atilan, uyari))

    def test_dbg_sonekleri_builder_kuralinin_tersi(self):
        """E: `@ui5/builder` minifier `-dbg`'i `.view/.fragment/.controller/.designtime/.support` sonekinin ÖNÜNE koyar.
        Her sonek için: `-dbg`'li dosya asıl adla yazılır, küçültülmüş karşılığı webapp'e GİRMEZ (atılır)."""
        sonekler = [".view", ".fragment", ".controller", ".designtime", ".support", ""]
        dist = {"manifest.json": b"{}"}
        for i, ek in enumerate(sonekler):
            dist[f"x/A{i}-dbg{ek}.js"] = f"// okunur {i}\n".encode()
            dist[f"x/A{i}{ek}.js"] = f"k{i}".encode()
            dist[f"x/A{i}{ek}.js.map"] = json.dumps({"sources": [f"A{i}-dbg{ek}.js"]}).encode()
        webapp, atilan, uyari = K.kaynak_kur(dist)
        yanlis = []
        for i, ek in enumerate(sonekler):
            asil = f"x/A{i}{ek}.js"
            if webapp.get(asil) != f"// okunur {i}\n".encode():
                yanlis.append(f"{ek or '(yalın)'}: asıl ad -dbg içeriğini taşımıyor")
            if f"x/A{i}-dbg{ek}.js" in webapp:
                yanlis.append(f"{ek or '(yalın)'}: -dbg adı webapp'e yazıldı")
            if asil not in atilan:
                yanlis.append(f"{ek or '(yalın)'}: küçültülmüş hâl atılmadı")
        if uyari:
            yanlis.append(f"uyarı: {uyari}")
        # Kontrol: ileri yön (builder'ın kendisi) aynı adları üretir.
        ileri = [K.dbg_adi(f"x/A{i}{ek}.js") for i, ek in enumerate(sonekler)]
        if ileri != [f"A{i}-dbg{ek}.js" for i, ek in enumerate(sonekler)]:
            yanlis.append(f"ileri yön: {ileri}")
        ok = not yanlis
        H.kaydet("kaynak_kur: 5 -dbg soneki (+yalın) builder kuralının tersiyle geri kurulur", "6/6 · 0 uyarı",
                 str(yanlis or "6/6"), ok)
        self.assertTrue(ok, yanlis)

    def test_adi_dbg_ile_biten_gercek_kaynak(self):
        """Tur 4 / 2: kaynakta adı `-dbg` ile biten dosya (`lib/util-dbg.js`, `view/Kart-dbg.view.js`) builder'da
        `util-dbg.js` + `util-dbg-dbg.js` + `util-dbg.js.map` olur → sonda 0 sapma, geri kurma asıl adı -dbg-dbg
        içeriğiyle yazar, küçük hâl atılır, 0 uyarı. Kontrol: aynı dosyanın TS izi (`util-dbg-dbg.js.map`) → sapma."""
        dist = {"manifest.json": b"{}",
                "lib/util-dbg.js": b"k", "lib/util-dbg-dbg.js": b"// util\n",
                "lib/util-dbg.js.map": b'{"sources":["util-dbg-dbg.js"]}',
                "view/Kart-dbg.view.js": b"k2", "view/Kart-dbg-dbg.view.js": b"// kart\n",
                "view/Kart-dbg.view.js.map": b'{"sources":["Kart-dbg-dbg.view.js"]}'}
        sapma, bakilan = K.harita_sondasi(dist)
        webapp, atilan, uyari = K.kaynak_kur(dist)
        ts = {**dist, "lib/util-dbg-dbg.js.map": b'{"sources":["util-dbg.ts"]}'}
        ts_sapma, _ = K.harita_sondasi(ts)
        sonuc = {
            "sonda 0 sapma / 2 harita": (sapma, bakilan) == ([], 2),
            "webapp asıl adlar": webapp == {"manifest.json": b"{}", "lib/util-dbg.js": b"// util\n",
                                            "view/Kart-dbg.view.js": b"// kart\n"},
            "küçükler atıldı": {"lib/util-dbg.js", "view/Kart-dbg.view.js"} <= set(atilan),
            "0 uyarı": uyari == [],
            "kontrol: TS izi sapma": len(ts_sapma) == 1 and "KENDİ haritası" in ts_sapma[0],
        }
        yanlis = [ad for ad, v in sonuc.items() if not v]
        ok = not yanlis
        H.kaydet("adı -dbg ile biten gerçek kaynak: varyant SAYILMAZ (ileri kural) · TS izi yine sapma", "5/5",
                 str(yanlis or "5/5"), ok)
        self.assertTrue(ok, (sapma, webapp, atilan, uyari, ts_sapma))

    def test_harita_sondasi_birim(self):
        """F birim: doğru → 0 sapma · `sources` dizge / null / fazla öğe / yol önekli → sapma · preload haritasına
        bakılmaz · hiç `-dbg` çifti ve harita yoksa ölçülecek iz yok (0/0 — KAPSAM bunu ayrıca söyler)."""
        dogru = {"a/B.view.js": b"k", "a/B-dbg.view.js": b"s", "a/B.view.js.map": b'{"sources":["B-dbg.view.js"]}',
                 "Component-preload.js.map": b"bozuk"}
        vakalar = {
            "doğru (+bozuk preload haritası yok sayılır)": (dogru, 0, 1),
            "sources dizge": ({**dogru, "a/B.view.js.map": b'{"sources":"B-dbg.view.js"}'}, 1, 1),
            "harita null": ({**dogru, "a/B.view.js.map": b"null"}, 1, 1),
            "fazla kaynak": ({**dogru, "a/B.view.js.map": b'{"sources":["B-dbg.view.js","x.ts"]}'}, 1, 1),
            "yol önekli kaynak": ({**dogru, "a/B.view.js.map": b'{"sources":["a/B-dbg.view.js"]}'}, 1, 1),
            "harita ve -dbg çifti yok": ({"a.js": b"x", "manifest.json": b"{}"}, 0, 0),
            "-dbg sonunda sourceMappingURL": ({**dogru, "a/B-dbg.view.js": b"s\n//# sourceMappingURL=B.view.ts.map\n"}, 1, 1),
            "-dbg ortada referans metni (kontrol)": ({**dogru, "a/B-dbg.view.js": b'var u="//# sourceMappingURL=x";\nf();\n'}, 0, 1),
        }
        yanlis = {}
        for ad, (d, beklenen_sapma, beklenen_bakilan) in vakalar.items():
            sapma, bakilan = K.harita_sondasi(d)
            if (len(sapma), bakilan) != (beklenen_sapma, beklenen_bakilan):
                yanlis[ad] = (sapma, bakilan)
        ok = not yanlis
        H.kaydet("harita_sondasi: 8 vaka (doğru/dizge/null/fazla/önekli/izsiz/-dbg ref/kontrol)", "8/8", str(yanlis or "8/8"), ok)
        self.assertTrue(ok, yanlis)

    def test_ts_ve_dbgsiz_uyari(self):
        dist = {"manifest.json": b"{}", "a.js": b"x", "b.js": b"y", "b-dbg.js": b"yy",
                "b.js.map": b'{"sources":["b.ts"]}'}
        _, _, uyari = K.kaynak_kur(dist)
        ok = len(uyari) == 2 and "TypeScript" in uyari[1] and "a.js" in uyari[0]
        H.kaydet("kaynak_kur: TS map + -dbg'siz js → uyarı", "2 uyarı", f"{len(uyari)}", ok)
        self.assertTrue(ok, uyari)


class TestKiyas(unittest.TestCase):
    def test_kovalar(self):
        a = {"x.js": b"1\r\n", "y": b"2", "z": b"3"}
        b = {"x.js": b"1\n", "y": b"22", "w": b"4"}
        k = K.kume_karsilastir(a, b)
        ok = (k["esit"] == ["x.js"] and k["farkli"] == ["y"] and k["yalniz_a"] == ["z"] and k["yalniz_b"] == ["w"]
              and not K.kume_esit_mi(k))
        H.kaydet("kume_karsilastir: eşit (CRLF≡LF)/farklı/yalnız-1/yalnız-2", "1/1/1/1", K.ozet(k), ok)
        self.assertTrue(ok, k)

    def test_ikili_dosya_ham_bayt(self):
        """G: satır sonu normalizasyonu YALNIZ metin uzantısında; ikili dosya ham baytla karşılaştırılır."""
        k = K.kume_karsilastir({"i/x.png": b"a\r\nb", "a.js": b"x\r\n", "i18n/i.properties": b"k=v\r\n"},
                               {"i/x.png": b"a\nb", "a.js": b"x\n", "i18n/i.properties": b"k=v\n"})
        ok = k["farkli"] == ["i/x.png"] and k["esit"] == ["a.js", "i18n/i.properties"]
        H.kaydet("kume_karsilastir: png CRLF≠LF (ham bayt) · .js/.properties CRLF≡LF (kontrol)",
                 "farkli png · esit 2", K.ozet(k), ok)
        self.assertTrue(ok, k)

    def test_preload_satir_sonu_ayri_kova(self):
        crlf = H.PRELOAD.replace(rb"\n<App", rb"\r\n<App")
        k = K.kume_karsilastir({"Component-preload.js": crlf}, {"Component-preload.js": H.PRELOAD},
                               D.preload_karsilastir)
        ok = k["satir_sonu"] == ["Component-preload.js"] and not K.kume_esit_mi(k)
        H.kaydet("kume_karsilastir: preload kaçışlı \\r\\n → ayrı kova, eşit DEĞİL", "satir_sonu 1", K.ozet(k), ok)
        self.assertTrue(ok, k)

    def test_deploy_haric_regex(self):
        ok = K._deploy_haric("test/x.js", ["/test/"]) and not K._deploy_haric("view/a.xml", ["/test/"])
        H.kaydet("deploy exclude regex: /test/ eşleşir, view/ eşleşmez", "True/False", str(ok), ok)
        self.assertTrue(ok)


class TestIndirmeYollari(unittest.TestCase):
    def test_odata_birincil(self):
        cagri = []

        def get(url, kimlik, s):
            cagri.append(url)
            return H.odata_zip(CANLI)

        d, bilgi, yol = K.canli_indir("https://h.invalid", "100", BSP, ("u", "p"), get=get)
        ok = (yol == "odata" and d == CANLI and bilgi["Package"] == "ZXX001" and len(cagri) == 1
              and "DownloadFiles='RUNTIME'" in cagri[0] and "sap-client=100" in cagri[0])
        H.kaydet("canli_indir: OData zip birincil yol, tek istek", "odata 1 istek", f"{yol} {len(cagri)}", ok)
        self.assertTrue(ok, cagri)

    def test_adt_yedek_klasor_ve_url_kodlu_id(self):
        agac = {
            BSP: _atom([(f"{BSP}/manifest.json", False), (f"{BSP}/i18n", True)]),
            f"{BSP}/manifest.json": b"{}",
            f"{BSP}/i18n": _atom([(f"{BSP}/i18n/i18n.properties", False)]),
            f"{BSP}/i18n/i18n.properties": b"a=b",
        }

        def get(url, kimlik, s):
            if "ABAP_REPOSITORY_SRV" in url:
                raise urllib.error.HTTPError(url, 404, "yok", {}, None)
            oge = urllib.request.unquote(url.split("/objects/", 1)[1].split("/content", 1)[0])
            return agac[oge]

        d, _, yol = K.canli_indir("https://h.invalid", "", BSP, ("u", "p"), get=get)
        ok = yol == "adt" and d == {"manifest.json": b"{}", "i18n/i18n.properties": b"a=b"}
        H.kaydet("canli_indir: OData 404 → ADT filestore (özyinelemeli, id çözülür)", "adt 2 dosya", f"{yol} {sorted(d)}", ok)
        self.assertTrue(ok, d)

    def test_iki_yol_duserse_hata(self):
        def get(url, kimlik, s):
            raise urllib.error.HTTPError(url, 403, "yasak", {}, None)

        with self.assertRaises(K.IndirmeHatasi) as c:
            K.canli_indir("https://h.invalid", "", BSP, ("u", "p"), get=get)
        ok = "OData" in str(c.exception) and "ADT" in str(c.exception)
        H.kaydet("canli_indir: iki yol da 403 → IndirmeHatasi (ölçüm yok)", "hata", str(c.exception)[:40], ok)
        self.assertTrue(ok)


class TestZipSlip(unittest.TestCase):
    """Sunucudan gelen ad (zip adı / ADT id) hedef klasörün dışına yazdıramaz."""
    KOTU = ["../kacis.txt", "a/../../kacis.txt", "..\\kacis.txt", "/mutlak.txt", "\\mutlak.txt", "C:/surucu.txt",
            "C:surucu.txt", "d:\\surucu.txt", "a/b:akis", ".."]

    def setUp(self):
        # `.resolve()`: TEMP 8.3 kısa adla gelebilir (CI Windows: `RUNNER~1`); kod kalan yolları çözülmüş uzun adla
        # döndürür ⇒ çözülmemiş kökle `relative_to` ValueError verir (ölçüldü: kısa adlı TEMP ile yerelde de).
        self.ust = Path(tempfile.mkdtemp(prefix="zipslip_")).resolve()
        self.kok = self.ust / "hedef"

    def tearDown(self):
        shutil.rmtree(self.ust, ignore_errors=True)

    def test_klasore_yaz_kok_disi_ad_yazmaz(self):
        yakalanan = 0
        for kotu in self.KOTU:
            with self.assertRaises(K.GuvensizYolHatasi, msg=kotu):
                K.klasore_yaz(self.kok, {"iyi.txt": b"1", kotu: b"x"})
            yakalanan += 1
        yazilan = sorted(p.relative_to(self.ust).as_posix() for p in self.ust.rglob("*") if p.is_file())
        # Kontrol grubu: iç içe klasör ve adında nokta olan (segment değil) dosya yazılır.
        K.klasore_yaz(self.kok, {"a/b/c.txt": b"1", "x..y.js": b"2", "./nokta.txt": b"3"})
        iyi = sorted(p.relative_to(self.kok).as_posix() for p in self.kok.rglob("*") if p.is_file())
        ok = yakalanan == len(self.KOTU) and yazilan == [] and iyi == ["a/b/c.txt", "nokta.txt", "x..y.js"]
        H.kaydet("klasore_yaz: kök dışı ad → hata, hiç dosya yok · iç ad yazılır",
                 f"{len(self.KOTU)} red · 0 · 3", f"{yakalanan} red · {len(yazilan)} · {len(iyi)}", ok)
        self.assertTrue(ok, (yazilan, iyi))

    def test_canli_indir_guvensiz_ad_yedege_gecmez(self):
        cagri = []

        def get(url, kimlik, s):
            cagri.append(url)
            return H.odata_zip({"manifest.json": b"{}", "../../kacis.js": b"x"})

        with self.assertRaises(K.GuvensizYolHatasi) as c:
            K.canli_indir("https://h.invalid", "", BSP, ("u", "p"), get=get)
        ok = len(cagri) == 1 and isinstance(c.exception, K.IndirmeHatasi) and "kacis.js" in str(c.exception)
        H.kaydet("canli_indir: zip'te ../ adı → GuvensizYolHatasi, ADT'ye geçmez", "hata · 1 istek",
                 f"{type(c.exception).__name__} · {len(cagri)} istek", ok)
        self.assertTrue(ok, (cagri, str(c.exception)))

    def test_anlik_yaz_hepsi_ya_hic_eski_bayt_bayt_kalir(self):
        """Tur 4 / 1: yazım ya da takas düşerse eski `.canli/` (dist + bilgi.json) BAYT BAYT yerinde, geçici ad kalmaz.
        Eskiden eski dist yeni yazımdan ÖNCE siliniyordu → `anlik_oku` = ({}, eski bilgi). Kontrol: başarılı yazım
        yeni içeriği koyar, `dist.eski`/`dist.yeni` bırakmaz; kesilmiş takas (`dist` yok, `dist.eski` var) kurtarılır."""
        from unittest import mock
        sonuc = {}
        app = self.ust / "app"
        K.anlik_yaz(app, {"eski.js": b"ESKI", "i/x.png": b"\x89\r\n"}, {"bsp": BSP})
        kok = app / K.ANLIK_KLASOR
        taban = K.anlik_ham(kok)
        # ① dist.yeni yazımı ortada düşer (`m` dosyasının altına yazma)
        with self.assertRaises(OSError):
            K.anlik_yaz(app, {"a.js": b"1", "m": b"dosya", "m/x.js": b"2"}, {"bsp": BSP})
        adlar = lambda: sorted(q.name for q in kok.iterdir())  # noqa: E731
        sonuc["yazım düşer"] = K.anlik_ham(kok) == taban and adlar() == ["bilgi.json", "dist"]
        # ② takasın ikinci adımı (bilgi.json değişimi) düşer → yeni dist geri çekilir, eski dist yerine konur
        with mock.patch.object(K, "_yer_degistir", side_effect=OSError(28, "benzetim")), self.assertRaises(OSError):
            K.anlik_yaz(app, {"a.js": b"YENI"}, {"bsp": BSP})
        sonuc["takas düşer"] = K.anlik_ham(kok) == taban and adlar() == ["bilgi.json", "dist"]
        # ③ takasın birinci adımı (dist.yeni → dist) düşer
        asil = Path.rename

        def yeni_tasinamaz(self_, hedef):
            if self_.name == "dist.yeni":
                raise OSError(13, "benzetim")
            return asil(self_, hedef)
        with mock.patch.object(Path, "rename", yeni_tasinamaz), self.assertRaises(OSError):
            K.anlik_yaz(app, {"a.js": b"YENI"}, {"bsp": BSP})
        sonuc["dist.yeni taşınamaz"] = K.anlik_ham(kok) == taban and adlar() == ["bilgi.json", "dist"]
        # Kontrol: başarılı yazım
        K.anlik_yaz(app, {"a.js": b"YENI"}, {"bsp": BSP, "k": 1})
        oku = K.anlik_oku(app)
        sonuc["kontrol: yeni yazılır, geçici ad yok"] = (
            oku is not None and oku[0] == {"a.js": b"YENI"} and oku[1].get("k") == 1
            and sorted(p.name for p in kok.iterdir()) == ["bilgi.json", "dist"])
        # Kesilmiş takas (dist yok + dist.eski var) ARDINDAN yazım düşer → eski görüntü `dist`'e geri konmuş olmalı
        # (kurtarma olmasa `dist.eski` bayat artık sayılıp SİLİNİRDİ — tek kopya kaybolurdu).
        taban2 = K.anlik_ham(kok)
        (kok / "dist").rename(kok / "dist.eski")
        with self.assertRaises(OSError):
            K.anlik_yaz(app, {"a.js": b"1", "m": b"dosya", "m/x.js": b"2"}, {"bsp": BSP})
        sonuc["kesilmiş takas + düşen yazım → eski geri"] = (K.anlik_ham(kok) == taban2
                                                             and adlar() == ["bilgi.json", "dist"])
        # Kesilmiş takas + bayat dist.yeni → kurtarılır, artık temizlenir, yeni yazılır
        (kok / "dist").rename(kok / "dist.eski")
        (kok / "dist.yeni").mkdir()
        (kok / "dist.yeni" / "artik.js").write_bytes(b"x")
        K.anlik_yaz(app, {"b.js": b"2"}, {"bsp": BSP})
        sonuc["kesilmiş takas kurtarılır"] = (K.anlik_oku(app)[0] == {"b.js": b"2"}
                                             and adlar() == ["bilgi.json", "dist"])
        yanlis = [ad for ad, v in sonuc.items() if not v]
        ok = not yanlis
        H.kaydet("anlik_yaz hepsi-ya-hiç: 3 hata noktası → eski bayt bayt · kontrol + kurtarma", "6/6",
                 str(yanlis or "6/6"), ok)
        self.assertTrue(ok, sonuc)

    def test_anlik_yaz_guvensiz_adda_eskisi_silinmez(self):
        app = self.ust / "app"
        K.anlik_yaz(app, {"a.js": b"eski"}, {"bsp": BSP})
        with self.assertRaises(K.GuvensizYolHatasi):
            K.anlik_yaz(app, {"a.js": b"yeni", "../../x.js": b"k"}, {"bsp": BSP})
        eski = (app / K.ANLIK_KLASOR / "dist" / "a.js").read_bytes()
        ok = eski == b"eski" and not (app / "x.js").exists() and not (self.ust / "x.js").exists()
        H.kaydet("anlik_yaz: güvensiz ad → eski anlık görüntü yerinde", "eski", eski.decode(), ok)
        self.assertTrue(ok)

    def test_bosluklu_ust_segment_hic_dosya_birakmaz(self):
        """Windows `.. ` segmentini `..`'ya kırpar: eskiden `a/f.js` yazılıp sonra OSError alınıyordu (ölçüldü)."""
        with self.assertRaises(K.GuvensizYolHatasi):
            K.klasore_yaz(self.kok, {"a/f.js": b"1", "a/.. /.. /x.js": b"2"})
        kalan = sorted(p.relative_to(self.ust).as_posix() for p in self.ust.rglob("*"))
        # Aynı aileden: sonu boşluk/nokta ile biten segment platforma göre farklı yola düşer → metin kuralı reddeder.
        aile = [".. /x.js", "a/.. /.. /x.js", "x.js.", "a. /b.js", "a /b.js"]
        metin_red = [r for r in aile if not K.yol_guvenli_mi(r)]
        ok = kalan == [] and metin_red == aile
        H.kaydet("klasore_yaz: `a/.. /.. /x.js` → hata, hiç dosya/klasör kalmaz · 5 sondan-boşluk/nokta adı red",
                 "[] · 5/5", f"{kalan} · {len(metin_red)}/5", ok)
        self.assertTrue(ok, (kalan, metin_red))

    def test_anlik_yaz_nokta_ve_bosluklu_ad_eskisi_kalir(self):
        app = self.ust / "app"
        K.anlik_yaz(app, {"a.js": b"eski"}, {"bsp": BSP})
        sonuc = {}
        for kotu in (".", ".. /x.js", "a\x00b.js"):
            try:
                K.anlik_yaz(app, {"a.js": b"yeni", kotu: b"k"}, {"bsp": BSP})
                sonuc[kotu] = "yazıldı"
            except K.GuvensizYolHatasi:
                sonuc[kotu] = "red"
            sonuc[kotu] += "/" + (app / K.ANLIK_KLASOR / "dist" / "a.js").read_bytes().decode()
        ok = set(sonuc.values()) == {"red/eski"} and not (app / "x.js").exists() and not (self.ust / "x.js").exists()
        H.kaydet("anlik_yaz: `.` / `.. /x.js` / NUL'lu ad → silmeden ÖNCE red, eski anlık görüntü yerinde",
                 "3× red/eski", str(sonuc), ok)
        self.assertTrue(ok, sonuc)

    def test_nul_adi_guvensiz_yol_hatasi(self):
        """`resolve()` NUL'da ValueError fırlatır — IndirmeHatasi yakalayan dallar bunu görmüyordu."""
        sonuc = []
        for cagri in (lambda: K.guvenli_hedef(self.kok, "a\x00b"),
                      lambda: K.klasore_yaz(self.kok, {"a\x00b": b"x"}),
                      lambda: K._adlari_dogrula({"a\x00b": b"x"})):
            try:
                cagri()
                sonuc.append("geçti")
            except K.GuvensizYolHatasi:
                sonuc.append("GuvensizYolHatasi")
            except Exception as exc:  # noqa: BLE001 — ölçülen şey tam olarak bu
                sonuc.append(type(exc).__name__)
        ok = sonuc == ["GuvensizYolHatasi"] * 3 and not self.kok.exists()
        H.kaydet("NUL'lu ad → GuvensizYolHatasi (ValueError sızmaz)", "3× GuvensizYolHatasi", str(sonuc), ok)
        self.assertTrue(ok, sonuc)

    def test_klasore_yaz_os_hatasinda_geri_alir(self):
        """Yazım ortasında OSError (dosya olan `b`'nin altına yazma): kök yoksa kök hiç yaratılmamış hâle döner;
        kök varsa bu çağrının yazdığı dosyalar/klasörler kaldırılır, üzerine yazılanın eski içeriği geri gelir."""
        bozuk = {"a/f.js": b"1", "b": b"dosya", "b/c.js": b"2"}
        with self.assertRaises(OSError) as c1:
            K.klasore_yaz(self.kok, bozuk)
        kok_yok = not self.kok.exists()
        self.kok.mkdir(parents=True)
        (self.kok / "eski.txt").write_bytes(b"E")
        (self.kok / "ust.js").write_bytes(b"ESKI")
        (self.kok / "var").mkdir()
        with self.assertRaises(OSError) as c2:
            K.klasore_yaz(self.kok, {"ust.js": b"YENI", "y/z.js": b"1", **bozuk})
        kalan = sorted(p.relative_to(self.kok).as_posix() for p in self.kok.rglob("*"))
        ok = (kok_yok and not isinstance(c1.exception, K.GuvensizYolHatasi)
              and not isinstance(c2.exception, K.GuvensizYolHatasi)
              and kalan == ["eski.txt", "ust.js", "var"] and (self.kok / "ust.js").read_bytes() == b"ESKI")
        H.kaydet("klasore_yaz: OSError → geri alma (kök yoksa kök yok · varsa önceki hâl)",
                 "kök yok · ['eski.txt', 'ust.js', 'var'] · ESKI", f"kök yok={kok_yok} · {kalan}", ok)
        self.assertTrue(ok, kalan)


    def test_klasore_yaz_geri_alma_kalanlari_olculur(self):
        """Bulgu 3 (birim): geri alma temizse `exc.kalanlar == []`; `_agac_sil` yarım kalırsa kalan dosya listelenir."""
        bozuk = {"a/f.js": b"1", "b": b"dosya", "b/c.js": b"2"}
        with self.assertRaises(OSError) as c1:
            K.klasore_yaz(self.kok, bozuk)
        temiz = c1.exception.kalanlar
        asil = K._agac_sil
        K._agac_sil = lambda p: None  # tutamaç benzetimi: silme hiç ilerlemez
        try:
            with self.assertRaises(OSError) as c2:
                K.klasore_yaz(self.kok, bozuk)
        finally:
            K._agac_sil = asil
        yarim = sorted(Path(x).relative_to(self.kok).as_posix() for x in c2.exception.kalanlar)
        # Kök ÖNCEDEN varken: temiz geri alma → []; dosya silme düşerse (unlink etkisiz) yazılanlar listelenir.
        from unittest import mock
        shutil.rmtree(self.kok, ignore_errors=True)
        (self.kok / "var").mkdir(parents=True)
        with self.assertRaises(OSError) as c3:
            K.klasore_yaz(self.kok, bozuk)
        var_temiz = c3.exception.kalanlar
        with mock.patch.object(Path, "unlink", lambda self, missing_ok=False: None), self.assertRaises(OSError) as c4:
            K.klasore_yaz(self.kok, bozuk)
        var_yarim = sorted(Path(x).relative_to(self.kok).as_posix() for x in c4.exception.kalanlar)
        ok = temiz == [] and yarim == ["a/f.js", "b"] and var_temiz == [] and var_yarim == ["a", "a/f.js", "b"]
        H.kaydet("klasore_yaz: geri alma ÖLÇÜLÜR (kök yok/var × temiz/yarım)",
                 "[] · [a/f.js, b] · [] · [a, a/f.js, b]", f"{temiz} · {yarim} · {var_temiz} · {var_yarim}", ok)
        self.assertTrue(ok, (temiz, yarim, var_temiz, var_yarim))

    def test_windows_aygit_adlari_guvensiz(self):
        """Bulgu 4: `CON/PRN/AUX/NUL/COM1-9/LPT1-9` (uzantılı, harfe duyarsız, her segmentte) → GuvensizYolHatasi,
        hiçbir dosya yazılmaz. Kontrol: aygıt adına BENZEYEN sıradan adlar yazılır."""
        kotu = ["a/NUL", "AUX.json", "con", "lpt9.txt", "Com1.js", "x/prn.txt/y.js", "nul .txt", "CONIN$", "COM¹.js"]
        red = []
        for ad in kotu:
            try:
                K.klasore_yaz(self.kok, {"iyi.txt": b"1", ad: b"x"})
            except K.GuvensizYolHatasi:
                red.append(ad)
        yazilan = sorted(p.name for p in self.ust.rglob("*") if p.is_file())
        iyi = ["CONSOLE.js", "nul2.txt", "COM10.js", "auxiliary.js", "a/lpt.js", "icon.png"]
        K.klasore_yaz(self.kok, {ad: b"1" for ad in iyi})
        yazildi = sorted(p.relative_to(self.kok).as_posix() for p in self.kok.rglob("*") if p.is_file())
        ok = red == kotu and yazilan == [] and yazildi == sorted(iyi)
        H.kaydet("yol_guvenli_mi: Windows aygıt adları red · benzer sıradan adlar yazılır",
                 f"{len(kotu)} red · 0 · {len(iyi)}", f"{len(red)} red · {len(yazilan)} · {len(yazildi)}", ok)
        self.assertTrue(ok, (red, yazilan, yazildi))


class TestMetadataTipKapsamli(unittest.TestCase):
    META = (b'<edmx:Edmx xmlns:edmx="http://schemas.microsoft.com/ado/2007/06/edmx"><edmx:DataServices>'
            b'<Schema xmlns="http://schemas.microsoft.com/ado/2008/09/edm" xmlns:sap="http://www.sap.com/Protocols/SAPData">'
            b'<EntityType Name="SiparisType"><Property Name="Vbeln" Type="Edm.String" sap:label="Belge"/></EntityType>'
            b'<EntityType Name="SAP__Signature"><Property Name="Reason" Type="Edm.String"/></EntityType>'
            b"</Schema></edmx:DataServices></edmx:Edmx>")

    def test_alan_tipe_baglanir(self):
        t = K.metadata_tipleri(self.META)
        ok = ("Reason" in t["SAP__Signature"] and "Reason" not in t["SiparisType"]
              and t["SiparisType"]["Vbeln"]["label"] == "Belge")
        H.kaydet("metadata_tipleri: başka tipteki aynı adlı alan ana tipe SAYILMAZ", "tip-kapsamlı", str(ok), ok)
        self.assertTrue(ok, t)


class TestCliIndirEslik(unittest.TestCase):
    def setUp(self):
        self.kok = Path(tempfile.mkdtemp(prefix="ui5fetch_"))

    def tearDown(self):
        shutil.rmtree(self.kok, ignore_errors=True)

    def test_indir_iskelet_ve_ustune_yazmaz(self):
        with H.SahteSunucu({H.odata_yol(BSP): H.odata_zip(CANLI)}) as srv:
            app = self.kok / "order_app"
            rc, out = H.kos("fetch_ui_source.py", "indir", BSP, "--out", app, "--url", srv.url, "--client", "100",
                            kimlik=True)
            rc2, out2 = H.kos("fetch_ui_source.py", "indir", BSP, "--out", app, "--url", srv.url, "--client", "100",
                              kimlik=True)
        ayar = D.B.deploy_ayari(app) or {}
        bilgi = json.loads((app / ".canli" / "bilgi.json").read_text(encoding="utf-8"))
        ok = (rc == 0 and (app / "webapp" / "Component.js").is_file() and ayar.get("name") == BSP
              and ayar.get("package") == "ZXX001" and ayar.get("url") == srv.url and not ayar.get("transport")
              and not ayar.get("resources_excludes") and len(bilgi["dosyalar"]) == len(CANLI)
              and "dist/" in (app / ".gitignore").read_text(encoding="utf-8")
              and ".canli/" in (app / ".gitignore").read_text(encoding="utf-8")
              and rc2 == 1 and "YAZILMAZ" in out2 and H.PAROLA not in out)
        H.kaydet("fetch indir: webapp + iskelet + .canli; ikinci kez → üstüne yazmaz", "rc=0 / rc=1",
                 f"rc={rc} / rc={rc2}", ok)
        self.assertTrue(ok, out + out2)

    def test_kimliksiz_olcum_yok(self):
        rc, out = H.kos("fetch_ui_source.py", "indir", BSP, "--out", self.kok / "a", "--url", "http://127.0.0.1:9")
        ok = rc == 2 and "set değil" in out and not (self.kok / "a").exists()
        H.kaydet("fetch indir: env kimlik yok → ölçüm yok, klasör yok", "rc=2", f"rc={rc}", ok)
        self.assertTrue(ok, out)

    def test_indir_yazim_hatasi_temiz_hata_ve_yeniden_kosulur(self):
        """klasore_yaz OSError'ı traceback değil `[FAIL]` + exit 2; webapp/ geri alınır → düzgün ikinci koşum 0."""
        app = self.kok / "order_app"
        with H.SahteSunucu({H.odata_yol(BSP): H.odata_zip({**CANLI, "b": b"dosya", "b/c.js": b"2"})}) as srv:
            rc, out = H.kos("fetch_ui_source.py", "indir", BSP, "--out", app, "--url", srv.url, "--client", "100",
                            kimlik=True)
        webapp_yok = not (app / "webapp").exists()
        with H.SahteSunucu({H.odata_yol(BSP): H.odata_zip(CANLI)}) as srv:
            rc2, out2 = H.kos("fetch_ui_source.py", "indir", BSP, "--out", app, "--url", srv.url, "--client", "100",
                              kimlik=True)
        ok = (rc == 2 and "[FAIL]" in out and "geri alındı" in out and "Traceback" not in out and webapp_yok
              and rc2 == 0 and (app / "webapp" / "Component.js").is_file())
        H.kaydet("fetch indir: yazım OSError → [FAIL] exit 2, webapp yok · yeniden koşum rc=0",
                 "rc=2 · webapp yok · rc=0", f"rc={rc} · webapp yok={webapp_yok} · rc={rc2}", ok)
        self.assertTrue(ok, out + out2)

    # Hata YALNIZ `.canli/` altında: `m` (dosya) webapp'a da gider, `m/x.js.map` build ürünüdür → yalnız `.canli/dist`'e
    # yazılır ve orada `m` dosyasının altına yazmaya çalışır → OSError. webapp + iskelet o ana kadar yazılmış olur.
    CANLI_HATALI = {**CANLI, "m": b"dosya", "m/x.js.map": b"{}"}

    def test_indir_anlik_yaz_hatasi_kosumun_hepsini_geri_alir(self):
        """Bulgu 2: `.canli` yazımı düşerse bu koşumun yazdığı HER ŞEY (webapp, package.json, ui5.yaml,
        ui5-deploy.yaml, .gitignore, .canli) geri alınır → `[FAIL]` exit 2; ikinci koşum temiz başlar (rc=0 + .canli)."""
        app = self.kok / "order_app"
        with H.SahteSunucu({H.odata_yol(BSP): H.odata_zip(self.CANLI_HATALI)}) as srv:
            rc, out = H.kos("fetch_ui_source.py", "indir", BSP, "--out", app, "--url", srv.url, "--client", "100",
                            kimlik=True)
        kalan = sorted(p.relative_to(app).as_posix() for p in app.rglob("*")) if app.exists() else []
        with H.SahteSunucu({H.odata_yol(BSP): H.odata_zip(CANLI)}) as srv:
            rc2, out2 = H.kos("fetch_ui_source.py", "indir", BSP, "--out", app, "--url", srv.url, "--client", "100",
                              kimlik=True)
        ok = (rc == 2 and "[FAIL]" in out and "geri alındı" in out and "Traceback" not in out and kalan == []
              and rc2 == 0 and (app / "webapp" / "Component.js").is_file()
              and (app / ".canli" / "bilgi.json").is_file())
        H.kaydet("fetch indir: .canli yazımı düşer → koşumun hepsi geri alınır · ikinci koşum rc=0",
                 "rc=2 · kalan [] · rc=0", f"rc={rc} · kalan {kalan} · rc={rc2}", ok)
        self.assertTrue(ok, out + out2)

    def test_indir_canli_onceden_varken_duserse_eski_bayt_bayt_kalir(self):
        """Tur 4 / 1: `.canli/` ÖNCEDEN varken `indir`'in `.canli` yazımı düşer → eski anlık görüntü + kullanıcının
        package.json'u BAYT BAYT aynı, webapp yok, mesaj "geri alındı … bayt bayt aynı (ölçüldü)" · exit 2.
        Negatif: eski görüntüyü bozan bir hata (benzetim) → mesaj "KORUNAMADI" + "GERİ ALINAMADI", "geri alındı (" YOK."""
        import argparse
        import contextlib
        import io
        import os
        from unittest import mock
        app = self.kok / "order_app"
        K.anlik_yaz(app, {"eski.js": b"ESKI"}, {"bsp": BSP})
        (app / "package.json").write_bytes(b"KULLANICI")
        once = K.klasor_oku(app)
        with H.SahteSunucu({H.odata_yol(BSP): H.odata_zip(self.CANLI_HATALI)}) as srv:
            rc, out = H.kos("fetch_ui_source.py", "indir", BSP, "--out", app, "--url", srv.url, "--client", "100",
                            kimlik=True)
        sonra = K.klasor_oku(app)
        ok1 = (rc == 2 and sonra == once and "bayt bayt aynı (ölçüldü)" in out and "geri alındı (" in out
               and not (app / "webapp").exists())
        # Negatif: anlık görüntü yazımı eski dosyayı silip düşer → ölçüm bunu görmeli
        F = _modul("fetch_ui_source_t4", "fetch_ui_source.py")

        def bozan(app_, dosyalar, bilgi):
            (Path(app_) / K.ANLIK_KLASOR / "dist" / "eski.js").unlink()
            raise OSError(28, "benzetim")
        H.proxy_bypass_surec_ici()
        cikti = io.StringIO()
        with H.SahteSunucu({H.odata_yol(BSP): H.odata_zip(CANLI)}) as srv, \
                mock.patch.dict(os.environ, {"FIORI_TOOLS_USER": H.KULLANICI, "FIORI_TOOLS_PASSWORD": H.PAROLA}), \
                mock.patch.object(F.K, "anlik_yaz", bozan), contextlib.redirect_stdout(cikti):
            rc2 = F.komut_indir(argparse.Namespace(bsp=BSP, out=str(app), url=srv.url, client="100",
                                                   ignore_cert=False))
        out2 = cikti.getvalue()
        ok2 = rc2 == 2 and "KORUNAMADI" in out2 and "GERİ ALINAMADI" in out2 and "geri alındı (" not in out2
        # Kalan: `dist.yeni` silinemez (tutamaç benzetimi) → görüntü yerinde ama geçici yol kaldı → listelenir
        asil_sil = F.K._agac_sil

        def yeni_silinmez(p):
            return None if Path(p).name == "dist.yeni" else asil_sil(p)
        once3 = K.anlik_ham(app / K.ANLIK_KLASOR)
        cikti = io.StringIO()
        with H.SahteSunucu({H.odata_yol(BSP): H.odata_zip(self.CANLI_HATALI)}) as srv, \
                mock.patch.dict(os.environ, {"FIORI_TOOLS_USER": H.KULLANICI, "FIORI_TOOLS_PASSWORD": H.PAROLA}), \
                mock.patch.object(F.K, "_agac_sil", yeni_silinmez), contextlib.redirect_stdout(cikti):
            rc3 = F.komut_indir(argparse.Namespace(bsp=BSP, out=str(app), url=srv.url, client="100",
                                                   ignore_cert=False))
        out3 = cikti.getvalue()
        ok3 = (rc3 == 2 and "GERİ ALINAMADI" in out3 and "dist.yeni" in out3 and "KORUNAMADI" not in out3
               and K.anlik_ham(app / K.ANLIK_KLASOR) == once3)
        ok = ok1 and ok2 and ok3
        H.kaydet("fetch indir: .canli önceden VARKEN düşer → eski bayt bayt · bozulursa KORUNAMADI · artık listelenir",
                 "rc=2 aynı · KORUNAMADI · dist.yeni", f"rc={rc} aynı={sonra == once} · rc={rc2} · rc={rc3}", ok)
        self.assertTrue(ok, out + out2 + out3)

    def test_indir_geri_alma_yarim_kalirsa_kalanlari_soyler(self):
        """Bulgu 3: geri alma yarım kalırsa (açık dosya tutamacı — Windows'ta GERÇEK tutamaç açılır, POSIX'te
        tutamaç silmeyi engellemediği için aynı sonuç benzetilir) mesaj "geri alındı" DEMEZ: kalan yolları listeler
        ve exit 2. Kontrol: tutamaçsız aynı hata "geri alındı" der (bir önceki test)."""
        import argparse
        import contextlib
        import io
        import os
        from unittest import mock
        F = _modul("fetch_ui_source_t", "fetch_ui_source.py")
        asil = F.K._agac_sil

        def tutamacli_sil(p):
            tut = next((q for q in Path(p).rglob("Component.js")), None)
            if tut is None:
                return asil(p)
            if os.name == "nt":
                with open(tut, "rb"):
                    asil(p)
            else:
                for q in sorted(Path(p).rglob("*"), reverse=True):
                    if q != tut and q not in tut.parents:
                        q.unlink() if not q.is_dir() else q.rmdir()
        app = self.kok / "order_app"
        H.proxy_bypass_surec_ici()
        cikti = io.StringIO()
        try:
            with H.SahteSunucu({H.odata_yol(BSP): H.odata_zip(self.CANLI_HATALI)}) as srv, \
                    mock.patch.dict(os.environ, {"FIORI_TOOLS_USER": H.KULLANICI, "FIORI_TOOLS_PASSWORD": H.PAROLA}), \
                    contextlib.redirect_stdout(cikti):
                F.K._agac_sil = tutamacli_sil
                rc = F.komut_indir(argparse.Namespace(bsp=BSP, out=str(app), url=srv.url, client="100",
                                                      ignore_cert=False))
        finally:
            F.K._agac_sil = asil
        out = cikti.getvalue()
        ok = (rc == 2 and "GERİ ALINAMADI" in out and "Component.js" in out and "geri alındı (" not in out
              and (app / "webapp" / "Component.js").exists())
        H.kaydet("fetch indir: geri alma yarım (açık tutamaç) → 'geri alınamadı: <yollar>' · exit 2",
                 "rc=2 · kalan listelenir", f"rc={rc} · {'listelendi' if 'Component.js' in out else 'YOK'}", ok)
        self.assertTrue(ok, out)

    def test_eslik_esit_farkli_anliksiz(self):
        app = self.kok / "app"
        K.anlik_yaz(app, CANLI, {"bsp": BSP})
        K.klasore_yaz(app / "dist", _build_lf(CANLI))
        rc1, out1 = H.kos("fetch_ui_source.py", "eslik", app, "--no-build")
        (app / "dist" / "i18n" / "i18n.properties").write_bytes(b"a=c\n")
        rc2, out2 = H.kos("fetch_ui_source.py", "eslik", app, "--no-build")
        rc3, out3 = H.kos("fetch_ui_source.py", "eslik", self.kok / "yok", "--no-build")
        ok = rc1 == 0 and "EŞLİK:" in out1 and rc2 == 1 and "i18n/i18n.properties" in out2 and rc3 == 2
        H.kaydet("fetch eslik: eşit=0 · farklı=1 · anlık görüntü yok=2", "0/1/2", f"{rc1}/{rc2}/{rc3}", ok)
        self.assertTrue(ok, out1 + out2 + out3)

    def _eslik(self, ad: str, canli: dict, dist: dict | None = None) -> tuple[int, str]:
        app = self.kok / ad
        K.anlik_yaz(app, canli, {"bsp": BSP})
        K.klasore_yaz(app / "dist", _build_lf(dist or canli))
        return H.kos("fetch_ui_source.py", "eslik", app, "--no-build")

    def test_eslik_kaynak_haritasi_sondasi(self):
        """F: eşlik ÜÇÜNCÜ şartı — canlı haritanın `sources`'u beklenen `-dbg` dosyasını göstermeli. Vakaların çoğunda
        dist == canlı (dosyalar EŞİT): red YALNIZ harita sondasından gelir."""
        ts = {**CANLI, "Component.js.map": b'{"version":3,"sources":["Component.ts"]}'}
        bozuk = {**CANLI, "Component.js.map": b'{"version":3,"sources":'}
        kendi = {**CANLI, "Component-dbg.js.map": b'{"version":3,"sources":["Component.ts"]}'}
        haritasiz = {r: v for r, v in CANLI.items() if r != "Component.js.map"}
        # Yorum-yalnız fark: `-dbg`'deki yorum küçültmede kaybolur → preload EŞİT; iz yalnız haritada (canlının
        # haritası başka bir kaynağı gösterir, bizim build'imizinki `-dbg`'i).
        yorum_canli = {**CANLI, "Component.js.map": b'{"version":3,"sources":["Component-dbg.js","yorum.js"]}'}
        vakalar = {   # ad: (canlı, dist, beklenen rc, çıktıda aranan)
            "doğru harita (kontrol)": (CANLI, None, 0, "EŞLİK:"),
            "TS kaynaklı harita": (ts, None, 1, "sources=['Component.ts']"),
            "bozuk JSON harita": (bozuk, None, 1, "harita okunamadı"),
            "-dbg'in kendi haritası": (kendi, None, 1, "KENDİ haritası"),
            "harita yok (çift var)": (haritasiz, None, 1, "Component.js.map yok"),
            "yorum-yalnız fark (preload eşit, harita farklı)": (yorum_canli, CANLI, 1, "yorum.js"),
        }
        yanlis = []
        for i, (ad, (canli, dist, beklenen, aranan)) in enumerate(vakalar.items()):
            rc, out = self._eslik(f"h{i}", canli, dist)
            if rc != beklenen or aranan not in out or "KAPSAM:" not in out:
                yanlis.append(f"{ad}: rc={rc} (beklenen {beklenen}) · '{aranan}' {'var' if aranan in out else 'YOK'}")
            if beklenen == 1 and dist is None and "build == canlı AMA kaynak haritası sapması" not in out:
                yanlis.append(f"{ad}: red harita sondasından gelmedi")
        n = len(vakalar)
        ok = not yanlis
        H.kaydet("fetch eslik: kaynak haritası sondası (TS / bozuk / -dbg haritası / haritasız / yorum farkı → YOK)",
                 f"{n}/{n}", str(yanlis or f"{n}/{n}"), ok)
        self.assertTrue(ok, yanlis)

    def test_eslik_build_basarisiz_exit2(self):
        """Tur 4 / 4: build düşerse kıyas HİÇ yapılmadı → exit 2 (ölçüm yok; docstring ve KAPSAM 'build ÖLÇÜLEMEDİ'
        ile tutarlı), 1 DEĞİL. Build benzetimi: `deploy_ui.run` → rc 1 (npm koşmaz)."""
        import argparse
        import contextlib
        import io
        import types
        from unittest import mock
        F = _modul("fetch_ui_source_t4b", "fetch_ui_source.py")
        app = self.kok / "b_app"
        K.anlik_yaz(app, CANLI, {"bsp": BSP})
        sahte = types.SimpleNamespace(run=lambda cmd, cwd, env: (1, "npm ERR! benzetim"))
        cikti = io.StringIO()
        with mock.patch.dict(sys.modules, {"deploy_ui": sahte}), contextlib.redirect_stdout(cikti):
            rc = F.komut_eslik(argparse.Namespace(app=str(app), no_build=False))
        out = cikti.getvalue()
        ok = rc == 2 and "build başarısız" in out and "(exit 2)" in out and "build ÖLÇÜLEMEDİ" in out
        H.kaydet("fetch eslik: build başarısız → exit 2 (ölçüm yok) + KAPSAM 'build ÖLÇÜLEMEDİ'", "rc=2",
                 f"rc={rc}", ok)
        self.assertTrue(ok, out)

    def test_eslik_ve_drift_kapsam_beyani_her_kosumda(self):
        """H: `eslik` ve `drift` her çıkışta (EŞLİK / AYNI anında da) KAPSAM + BAKILMAYANLAR satırı basar."""
        rc_e, out_e = self._eslik("k0", CANLI)
        rc_y, out_y = H.kos("fetch_ui_source.py", "eslik", self.kok / "yok", "--no-build")
        app = self.kok / "order_app"
        with H.SahteSunucu({H.odata_yol(BSP): H.odata_zip(CANLI)}) as srv:
            rc_i, out_i = H.kos("fetch_ui_source.py", "indir", BSP, "--out", app, "--url", srv.url, "--client", "100",
                                kimlik=True)
            rc_d, out_d = H.kos("fetch_ui_source.py", "drift", app, kimlik=True)
        rc_k, out_k = H.kos("fetch_ui_source.py", "drift", app)
        kosumlar = {"eslik EŞLİK": (rc_e, 0, out_e), "eslik anlık yok": (rc_y, 2, out_y),
                    "drift AYNI": (rc_d, 0, out_d), "drift kimliksiz": (rc_k, 2, out_k)}
        yanlis = [f"{ad}: rc={rc}" + ("" if "KAPSAM" in out and "BAKILMAYANLAR:" in out else " · KAPSAM yok")
                  for ad, (rc, beklenen, out) in kosumlar.items()
                  if rc != beklenen or "KAPSAM" not in out or "BAKILMAYANLAR:" not in out]
        if rc_i != 0:
            yanlis.append(f"indir rc={rc_i}")
        ok = not yanlis
        H.kaydet("fetch eslik/drift: KAPSAM + BAKILMAYANLAR her çıkışta (EŞLİK/AYNI dahil)", "4/4",
                 str(yanlis or "4/4"), ok)
        self.assertTrue(ok, (yanlis, out_e, out_d))


class TestSaltOkurProxy(unittest.TestCase):
    def test_izin_tablosu(self):
        vakalar = [
            (("GET", "/sap/opu/odata/sap/X/Set"), True),
            (("HEAD", "/sap/opu/odata/sap/X/"), True),
            (("POST", "/sap/opu/odata/sap/X/$batch", self.V2_OKUMA, self.MP), True),
            (("POST", "/sap/opu/odata/sap/X/$batch", b"--batch\r\nContent-Type: multipart/mixed; boundary=ChangeSet_1"), False),
            (("POST", "/sap/opu/odata/sap/X/Set", b"{}"), False),
            (("POST", "/sap/opu/odata/sap/X/Onayla?Id='1'", b""), False),
            (("PUT", "/sap/opu/odata/sap/X/Set('1')"), False),
            (("MERGE", "/sap/opu/odata/sap/X/Set('1')"), False),
            (("PATCH", "/sap/opu/odata/sap/X/Set('1')"), False),
            (("DELETE", "/sap/opu/odata/sap/X/Set('1')"), False),
        ]
        yanlis = [(g, b) for g, b in vakalar if P.izin_ver(*g)[0] != b]
        ok = not yanlis
        H.kaydet("proxy izin_ver: okuma geçer, 7 yazma biçimi 403", "10/10", f"{len(vakalar) - len(yanlis)}/10", ok)
        self.assertTrue(ok, yanlis)

    # Standart UI5 V2 ODataModel okuma batch'i (yalnız GET parçaları, boundary `batch_…`) — kontrol grubu.
    V2_OKUMA = (b"--batch_a1b2-c3d4\r\nContent-Type: application/http\r\nContent-Transfer-Encoding: binary\r\n\r\n"
                b"GET Orders?$skip=0&$top=20 HTTP/1.1\r\nsap-cancel-on-close: true\r\nAccept: application/json\r\n"
                b"DataServiceVersion: 2.0\r\nMaxDataServiceVersion: 2.0\r\n\r\n\r\n"
                b"--batch_a1b2-c3d4\r\nContent-Type: application/http\r\nContent-Transfer-Encoding: binary\r\n\r\n"
                b"GET Orders/$count HTTP/1.1\r\nAccept: text/plain\r\n\r\n\r\n--batch_a1b2-c3d4--\r\n")
    MP = "multipart/mixed; boundary=batch_a1b2-c3d4"
    # UI5 V4 biçiminde okuma batch'i: boşluksuz `Ad:değer` başlıkları + kapanıştan sonra epilog (`Group ID: …`).
    # Bayt bayt canlı UI5 çıktısı DEĞİL (DOĞRULANMADI) — biçim kontrol grubudur.
    V4_OKUMA = (b"--batch_id-1719387000000-12\r\nContent-Type:application/http\r\nContent-Transfer-Encoding:binary\r\n\r\n"
                b"GET Products?$select=ID,Name&$skip=0&$top=20 HTTP/1.1\r\n"
                b"Accept:application/json;odata.metadata=minimal;IEEE754Compatible=true\r\nAccept-Language:tr\r\n"
                b"Content-Type:application/json;charset=UTF-8;IEEE754Compatible=true\r\n\r\n\r\n"
                b"--batch_id-1719387000000-12--\r\nGroup ID: $auto\r\n")
    MP4 = "multipart/mixed;boundary=batch_id-1719387000000-12"
    # Negatif vakalar için GEÇERLİ zarf: her vaka yalnız bir noktada bozulur (red, zarfın kendisinden gelmesin).
    MP1 = "multipart/mixed; boundary=batch_1"
    PB = b"Content-Type: application/http\r\nContent-Transfer-Encoding: binary\r\n\r\n"
    GET_P = PB + b"GET Orders HTTP/1.1\r\nAccept: application/json\r\n\r\n"

    @staticmethod
    def zarf(*parcalar: bytes, prolog: bytes = b"", epilog: bytes = b"") -> bytes:
        g = prolog
        for p in parcalar:
            g += b"--batch_1\r\n" + p + b"\r\n"
        return g + b"--batch_1--\r\n" + epilog

    def test_batch_okuma_kontrol_grubu_gecer(self):
        vakalar = [
            ("POST", "/sap/opu/odata/sap/ZXX001_SRV/$batch", self.V2_OKUMA, self.MP),
            ("POST", "/sap/opu/odata/sap/ZXX001_SRV/$batch", self.V2_OKUMA, None),
            ("POST", "/sap/opu/odata/sap/ZXX001_SRV;o=LOCAL/$batch?sap-client=000", self.V2_OKUMA, self.MP),
            ("POST", "/sap/opu/odata4/sap/zxx001_ui/srvd/sap/zxx001_ui/0001/$batch", self.V2_OKUMA, self.MP),
            ("POST", "/sap/opu/odata4/sap/zxx001_ui/srvd/sap/zxx001_ui/0001/$batch", self.V4_OKUMA, self.MP4),
            ("POST", "/sap/opu/odata/sap/X/$batch", self.zarf(self.GET_P, self.GET_P, prolog=b"serbest prolog\r\n",
                                                              epilog=b"serbest epilog\r\n"), self.MP1),
            ("POST", "/sap/opu/odata/sap/X/$batch", self.zarf(self.GET_P), 'multipart/mixed; boundary="batch_1"'),
        ]
        yanlis = [v[1] for v in vakalar if not P.izin_ver(*v)[0]]
        n = len(vakalar)
        ok = not yanlis
        H.kaydet("proxy $batch kontrol grubu: V2/V4(+epilog)/zarf GET-yalnız batch geçer", f"{n}/{n}",
                 f"{n - len(yanlis)}/{n}", ok)
        self.assertTrue(ok, yanlis)

    # UI5 1.120.23'ün GERÇEK tarayıcıda ürettiği okuma $batch gövdeleri (XHR send() yakalaması, 2026-09-26). Yol elle
    # birleştirilince (`"/Items('" + id + "')"`) UI5 hedefi KODLAMAZ: boşluk ve UTF-8 olduğu gibi gider.
    GERCEK_V4 = ("--batch_id-1790435372243-11\r\nContent-Type:application/http\r\nContent-Transfer-Encoding:binary\r\n\r\n"
                 "GET Items?$filter=Name%20eq%20'%C3%96%20%C5%9F%20x'&$skip=0&$top=5 HTTP/1.1\r\n"
                 "Accept:application/json;odata.metadata=minimal;IEEE754Compatible=true\r\nAccept-Language:en-US\r\n"
                 "Content-Type:application/json;charset=UTF-8;IEEE754Compatible=true\r\n\r\n\r\n"
                 "--batch_id-1790435372243-11\r\nContent-Type:application/http\r\nContent-Transfer-Encoding:binary\r\n\r\n"
                 "GET Items('Ö ş') HTTP/1.1\r\n"
                 "Accept:application/json;odata.metadata=minimal;IEEE754Compatible=true\r\nAccept-Language:en-US\r\n"
                 "Content-Type:application/json;charset=UTF-8;IEEE754Compatible=true\r\n\r\n\r\n"
                 "--batch_id-1790435372243-11--\r\nGroup ID: $auto").encode("utf-8")
    GERCEK_V2 = ("\r\n--batch_de13-ec17-b0e3\r\nContent-Type: application/http\r\nContent-Transfer-Encoding: binary\r\n\r\n"
                 "GET Items('A 1') HTTP/1.1\r\n"
                 "sap-cancel-on-close: true\r\nsap-contextid-accept: header\r\nAccept: application/json\r\n"
                 "Accept-Language: en-US\r\nDataServiceVersion: 2.0\r\nMaxDataServiceVersion: 2.0\r\n"
                 "X-Requested-With: XMLHttpRequest\r\n\r\n\r\n"
                 "--batch_de13-ec17-b0e3\r\nContent-Type: application/http\r\nContent-Transfer-Encoding: binary\r\n\r\n"
                 "GET Items('Ğİ') HTTP/1.1\r\n"
                 "sap-cancel-on-close: true\r\nsap-contextid-accept: header\r\nAccept: application/json\r\n"
                 "Accept-Language: en-US\r\nDataServiceVersion: 2.0\r\nMaxDataServiceVersion: 2.0\r\n"
                 "X-Requested-With: XMLHttpRequest\r\n\r\n\r\n"
                 "--batch_de13-ec17-b0e3--\r\n").encode("utf-8")

    def test_gercek_ui5_okuma_batchi_gecer_hedefte_bosluk_ve_utf8(self):
        v4 = ("/sap/opu/odata4/sap/ztest/srvd/sap/ztest/0001/$batch", "multipart/mixed; boundary=batch_id-1790435372243-11")
        v2 = ("/sap/opu/odata/sap/ZTEST_SRV/$batch", "multipart/mixed;boundary=batch_de13-ec17-b0e3")
        gecmeli = {"gerçek V4 (hedefte boşluk + UTF-8)": (v4[0], self.GERCEK_V4, v4[1]),
                   "gerçek V2 (hedefte boşluk + UTF-8)": (v2[0], self.GERCEK_V2, v2[1])}
        # Gevşeme yeni kapı açmasın: hedef boşlukla başlamaz, kontrol baytı / DEL taşımaz, yöntem yalnız `GET `.
        asil = "GET Items('A 1') HTTP/1.1".encode("utf-8")
        bozuk = [("hedef boşlukla başlar", "GET  Items('A 1') HTTP/1.1"), ("hedefte sekme", "GET Items('A	1') HTTP/1.1"),
                 ("hedefte DEL", "GET Items('A1') HTTP/1.1"), ("hedefte VT", "GET Items('A1') HTTP/1.1"),
                 ("NBSP ayraçlı DELETE", "DELETE Items('A 1') HTTP/1.1"),
                 ("GET yerine DELETE", "DELETE Items('A 1') HTTP/1.1")]
        yanlis = [ad for ad, v in gecmeli.items() if not P.izin_ver("POST", v[0], v[1], v[2])[0]]
        for ad, satir in bozuk:
            govde = self.GERCEK_V2.replace(asil, satir.encode("utf-8"))
            if govde == self.GERCEK_V2 or P.izin_ver("POST", v2[0], govde, v2[1])[0]:
                yanlis.append(ad)
        n = len(gecmeli) + len(bozuk)
        ok = not yanlis
        H.kaydet("proxy $batch gerçek UI5 1.120 gövdesi geçer; hedef gevşemesi yeni kapı açmaz", f"{n}/{n}",
                 f"{n - len(yanlis)}/{n}", ok)
        self.assertTrue(ok, yanlis)

    def test_hedefte_unicode_satir_kontrol_ve_gecersiz_utf8_red(self):
        """Tur 4 / 3: hedef KATI UTF-8 çözülmeli, Cc/Zl/Zp karakteri içermemeli. Bayt kuralı ASCII kontrolünü yakalar;
        NEL (U+0085, `\\xc2\\x85`), C1 (`\\xc2\\x9b`), LS/PS (U+2028/2029), ham `\\x85` / `\\xff`, yarım UTF-8 dizisi eskiden
        geçiyordu. Kontrol: gerçek UI5 gövdeleri (`Ö ş`, `Ğİ`) ve NBSP'li hedef (Zs — satır karakteri değil) geçer."""
        v2 = ("/sap/opu/odata/sap/ZTEST_SRV/$batch", "multipart/mixed;boundary=batch_de13-ec17-b0e3")
        asil = "GET Items('A 1') HTTP/1.1".encode("utf-8")
        bozuk = {"NEL U+0085": b"GET Items('A\xc2\x85DELETE Items') HTTP/1.1",
                 "C1 U+009B": b"GET Items('A\xc2\x9bx') HTTP/1.1",
                 "LS U+2028": b"GET Items('A\xe2\x80\xa8x') HTTP/1.1",
                 "PS U+2029": b"GET Items('A\xe2\x80\xa9x') HTTP/1.1",
                 "ham 0x85": b"GET Items('A\x85x') HTTP/1.1",
                 "ham 0xff": b"GET Items('A\xffx') HTTP/1.1",
                 "yarım UTF-8 (\\xc3 sonu)": b"GET Items('A\xc3') HTTP/1.1"}
        yanlis = []
        for ad, satir in bozuk.items():
            govde = self.GERCEK_V2.replace(asil, satir)
            if govde == self.GERCEK_V2 or P.izin_ver("POST", v2[0], govde, v2[1])[0]:
                yanlis.append(ad)
        kontrol = {"gerçek V2 (Ğİ)": self.GERCEK_V2,
                   "NBSP (Zs)": self.GERCEK_V2.replace(asil, "GET Items('A 1') HTTP/1.1".encode("utf-8"))}
        yanlis += [f"kontrol {ad}" for ad, g in kontrol.items() if not P.izin_ver("POST", v2[0], g, v2[1])[0]]
        if not P.izin_ver("POST", "/sap/opu/odata4/sap/ztest/srvd/sap/ztest/0001/$batch", self.GERCEK_V4,
                          "multipart/mixed; boundary=batch_id-1790435372243-11")[0]:
            yanlis.append("kontrol gerçek V4 (Ö ş)")
        n = len(bozuk) + len(kontrol) + 1
        ok = not yanlis
        H.kaydet("proxy $batch hedef: NEL/C1/LS/PS/geçersiz UTF-8 → 403 · gerçek UI5 + NBSP geçer", f"{n}/{n}",
                 str(yanlis or f"{n}/{n}"), ok)
        self.assertTrue(ok, yanlis)

    def test_batch_yazma_atlatmalari_reddedilir(self):
        z, PB, GET_P, MP1 = self.zarf, self.PB, self.GET_P, self.MP1
        v2 = "/sap/opu/odata/sap/X/$batch"
        gecerli = z(GET_P)
        vakalar = {   # ad: (yol, gövde, istek Content-Type)
            "a iç multipart parça": (v2, z(b"Content-Type: multipart/mixed; boundary=abc\r\n\r\n--abc\r\n" + PB
                                          + b"POST Orders HTTP/1.1\r\n\r\n{}\r\n--abc--\r\n"), MP1),
            "b changeset'siz DELETE parçası": (v2, z(GET_P, PB + b"DELETE Orders(1) HTTP/1.1\r\n\r\n"), MP1),
            "c SOAP RFC yolu": ("/sap/bc/soap/rfc/$batch", gecerli, MP1),
            "küçük harf delete": (v2, z(PB + b"delete Orders(1) HTTP/1.1\r\n\r\n"), MP1),
            "küçük harf get": (v2, z(PB + b"get Orders HTTP/1.1\r\n\r\n"), MP1),
            "baştaki boşluklu GET": (v2, z(PB + b" GET Orders HTTP/1.1\r\n\r\n"), MP1),
            "sürümsüz MERGE": (v2, z(PB + b"MERGE Orders(1)\r\n\r\n"), MP1),
            "PURGE": (v2, z(PB + b"PURGE Orders(1) HTTP/1.1\r\n\r\n"), MP1),
            "HTTP/1.0": (v2, z(PB + b"GET Orders HTTP/1.0\r\n\r\n"), MP1),
            "GET parçası gövdesinde DELETE": (v2, z(PB + b"GET Orders HTTP/1.1\r\n\r\nDELETE Orders(1) HTTP/1.1\r\n"), MP1),
            "iç istek başlığında multipart": (v2, z(PB + b"GET X HTTP/1.1\r\ncontent-type:multipart/mixed;boundary=q\r\n\r\n"), MP1),
            "parça Content-Type yok": (v2, z(b"Content-Transfer-Encoding: binary\r\n\r\nGET Orders HTTP/1.1\r\n\r\n"), MP1),
            "parça Content-Type çift": (v2, z(b"Content-Type: application/http\r\n" + GET_P), MP1),
            "parça Content-Type application/json": (v2, z(GET_P.replace(b"application/http", b"application/json", 1)), MP1),
            "X-HTTP-Method (iç istek)": (v2, z(PB + b"GET Orders(1) HTTP/1.1\r\nX-HTTP-Method: DELETE\r\n\r\n"), MP1),
            "X-HTTP-Method-Override (parça)": (v2, z(b"X-HTTP-Method-Override: DELETE\r\n" + GET_P), MP1),
            "base64 aktarım": (v2, z(GET_P.replace(b"binary", b"base64")), MP1),
            "F2 katlanmış CTE": (v2, z(b"Content-Type: application/http\r\nContent-Transfer-Encoding:\r\n base64\r\n\r\n"
                                       b"GET Orders HTTP/1.1\r\n\r\n"), MP1),
            "F2 yalnız \\r ile ayrılmış DELETE parçası": (v2, z(GET_P, b"Content-Type: application/http\r\r"
                                                              b"DELETE Orders(1) HTTP/1.1\r\r"), MP1),
            "F2 DELETE\\x0b": (v2, z(PB + b"DELETE\x0bOrders(1) HTTP/1.1\r\n\r\n"), MP1),
            "F2 \\x0cDELETE": (v2, z(PB + b"\x0cDELETE Orders(1) HTTP/1.1\r\n\r\n"), MP1),
            "F2 DELETE\\xa0": (v2, z(PB + b"DELETE\xa0Orders(1) HTTP/1.1\r\n\r\n"), MP1),
            "hedefte kontrol baytı \\x1f": (v2, z(PB + b"GET Ord\x1fers HTTP/1.1\r\n\r\n"), MP1),
            "hedefte DEL \\x7f": (v2, z(PB + b"GET Ord\x7fers HTTP/1.1\r\n\r\n"), MP1),
            "parça başlığında ASCII dışı bayt": (v2, z(b"X-Not: \xc3\xbc\r\n" + GET_P), MP1),
            "F1 BOM'lu JSON (tip yok)": (v2, b'\xef\xbb\xbf{"requests":[{"method":"DELETE","url":"Orders(1)"}]}\n'
                                             b"GET x HTTP/1.1\n", None),
            "F1 BOM'lu JSON (tip MP)": (v2, b'\xef\xbb\xbf{"requests":[{"method":"DELETE","url":"Orders(1)"}]}\n'
                                            b"GET x HTTP/1.1\n", MP1),
            "BOM'lu zarf": (v2, b"\xef\xbb\xbf" + gecerli, MP1),
            "JSON gövde (tip MP)": (v2, b'{"requests":[{"method":"GET","url":"Orders"}]}', MP1),
            "JSON dizi (tip yok)": (v2, b'  [{"method":"DELETE"}]', None),
            "NUL baytı": (v2, gecerli.replace(b"Orders", b"Ord\x00ers", 1), MP1),
            "yalnız LF satır sonu": (v2, gecerli.replace(b"\r\n", b"\n"), MP1),
            # Genel bayt kuralları prolog/epilog'da da geçerli (tek başına yakalayan katman bunlar — başka kural görmez):
            "prolog'da kontrol baytı \\x0b": (v2, z(GET_P, prolog=b"a\x0bDELETE b\r\n"), MP1),
            "epilog'da DEL \\x7f": (v2, z(GET_P, epilog=b"a\x7f\r\n"), MP1),
            "prolog'da tek \\r": (v2, z(GET_P, prolog=b"a\rDELETE b\r\n"), MP1),
            "prolog'da tek \\n": (v2, z(GET_P, prolog=b"a\nDELETE b\r\n"), MP1),
            "epilog'da UTF-8 BOM": (v2, z(GET_P, epilog=b"\xef\xbb\xbf\r\n"), MP1),
            "kapanış sınırı yok": (v2, gecerli[:-len(b"--batch_1--\r\n")], MP1),
            "sınıra benzeyen satır (sonda boşluk)": (v2, z(GET_P, prolog=b"--batch_1 \r\n"), MP1),
            "kapanıştan sonra DELETE parçası": (v2, z(GET_P, epilog=b"--batch_1\r\n" + PB
                                                      + b"DELETE Orders(1) HTTP/1.1\r\n\r\n--batch_1--\r\n"), MP1),
            "parçasız zarf": (v2, b"--batch_1--\r\n", MP1),
            "boş parça": (v2, z(b""), MP1),
            "boş gövde": (v2, b"", MP1),
            "tip application/json": (v2, gecerli, "application/json"),
            "tip yok (boş dize)": (v2, gecerli, ""),
            "tip text/plain": (v2, gecerli, "text/plain"),
            "tip multipart/mixed sınırsız": (v2, gecerli, "multipart/mixed"),
            "tip ek parametreli": (v2, gecerli, "multipart/mixed; boundary=batch_1; charset=utf-8"),
            "tip multipart/related": (v2, gecerli, "multipart/related; boundary=batch_1"),
            "tip geçersiz sınır": (v2, gecerli, 'multipart/mixed; boundary="batch 1"'),
            "tip 71 karakter sınır": (v2, gecerli, "multipart/mixed; boundary=" + "b" * 71),
            "tip sınır gövdeyle uyuşmuyor": (v2, gecerli, "multipart/mixed; boundary=batch_2"),
            # Gövde de AYNI geçersiz sınırla kurulur — red, sınır biçim kuralından gelmeli (gövde uyuşmazlığından değil):
            "sınır 71 karakter (gövde uyumlu)": (v2, gecerli.replace(b"batch_1", b"b" * 71),
                                                  "multipart/mixed; boundary=" + "b" * 71),
            "sınırda izinsiz karakter (gövde uyumlu)": (v2, gecerli.replace(b"batch_1", b"batch*1"),
                                                         "multipart/mixed; boundary=batch*1"),
            "yol .. ile kaçış": ("/sap/opu/odata/../../bc/soap/rfc/$batch", gecerli, MP1),
            "yol % kodlu": ("/sap/opu/odata/sap/X%2F..%2F/$batch", gecerli, MP1),
            "odata dışı ICF yolu": ("/sap/bc/ui2/$batch", gecerli, MP1),
            "F3 yol ..; segmenti": ("/sap/opu/odata/..;/..;/bc/soap/rfc/$batch", gecerli, MP1),
            "F3 yol .; segmenti": ("/sap/opu/odata/sap/X/.;/$batch", gecerli, MP1),
            "yol boş matris segmenti": ("/sap/opu/odata/sap/;x=1/$batch", gecerli, MP1),
        }
        yanlis = [ad for ad, (yol, g, tip) in vakalar.items() if P.izin_ver("POST", yol, g, tip)[0]]
        # Başka bir kural da aynı sonuca vardığı için bool'un ölçemediği katmanlar: red NEDENİ de ölçülür
        # (mutasyonda katlanma / kapanış-sonrası sınır / parçasız kapanış kuralı silinince sonuç değişmiyordu).
        nedenler = {"F2 katlanmış CTE": "katlanmış", "kapanıştan sonra DELETE parçası": "kapanış sınırından sonra",
                    "parçasız zarf": "parçasız", "sınır 71 karakter (gövde uyumlu)": "multipart/mixed; boundary",
                    "sınırda izinsiz karakter (gövde uyumlu)": "multipart/mixed; boundary"}
        for ad, parca in nedenler.items():
            yol, g, tip = vakalar[ad]
            if parca not in P.izin_ver("POST", yol, g, tip)[1]:
                yanlis.append(f"NEDEN: {ad}")
        # Zarfın kendisi geçerli olmalı — yoksa negatif vakalar YANLIŞ sebeple geçer (kontrol ikizi).
        if not P.izin_ver("POST", v2, gecerli, MP1)[0]:
            yanlis.append("KONTROL: geçerli zarf reddedildi")
        n = len(vakalar)
        ok = not yanlis
        H.kaydet("proxy $batch: parça bazlı beyaz liste — atlatmalar 403", f"{n}/{n} · zarf geçer",
                 f"{n - len(yanlis)}/{n}", ok)
        self.assertTrue(ok, yanlis)

    def test_uctan_uca_cift_content_type_403(self):
        """F1: çift Content-Type (hangi sırada olursa) → 403 + SAP'ye 0 POST; tek başlıkta SAP'ye giden Content-Type
        istemcinin değeri DEĞİL, proxy'nin kurduğu kanonik gövdenin tipidir (tek kaynak — yeniden kurma)."""
        import http.client
        import ssl
        H.proxy_bypass_surec_ici()
        kok = Path(tempfile.mkdtemp(prefix="ui5proxy_"))
        (kok / "index.html").write_bytes(b"<html/>")
        giden = []
        try:
            with H.SahteSunucu({}) as sap:
                def _post(h):
                    h.rfile.read(int(h.headers.get("Content-Length") or 0))
                    sap.istekler.append("POST " + h.path.split("?", 1)[0])
                    giden.append(h.headers.get_all("Content-Type"))
                    h.send_response(202)
                    h.send_header("Content-Length", "0")
                    h.end_headers()
                sap.httpd.RequestHandlerClass.do_POST = _post
                srv = P.Sunucu(("127.0.0.1", 0), P.isleyici_sinifi(kok, sap.url, "100", (H.KULLANICI, H.PAROLA),
                                                                     ssl.create_default_context()))
                threading.Thread(target=srv.serve_forever, daemon=True).start()
                port = srv.server_address[1]

                def gonder(tipler):
                    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
                    try:
                        c.putrequest("POST", "/sap/opu/odata/sap/X/$batch")
                        for t in tipler:
                            c.putheader("Content-Type", t)
                        c.putheader("Content-Length", str(len(self.V2_OKUMA)))
                        c.endheaders(self.V2_OKUMA)
                        r = c.getresponse()
                        r.read()
                        return r.status
                    finally:
                        c.close()
                try:
                    cift1 = gonder([self.MP, "application/json"])
                    cift2 = gonder(["application/json", self.MP])
                    cift3 = gonder([self.MP, self.MP])
                    sonra = len(sap.istekler)
                    tek = gonder([self.MP])
                finally:
                    srv.shutdown()
                    srv.server_close()
        finally:
            shutil.rmtree(kok, ignore_errors=True)
        gercek = (cift1, cift2, cift3, sonra, tek, giden)
        ok = (gercek[:5] == (403, 403, 403, 0, 202) and len(giden) == 1 and len(giden[0]) == 1
              and giden[0][0].startswith("multipart/mixed; boundary=batch_axet_"))
        H.kaydet("proxy uçtan uca F1: çift Content-Type 403 · SAP'ye 0 · tek başlıkta kanonik tip gider",
                 "403/403/403 · 0 · 202 · [kanonik]", str(gercek), ok)
        self.assertTrue(ok, gercek)

    # --- Tur 3: AYRIŞTIR + YENİDEN KUR. SAP'ye istemcinin baytları değil proxy'nin kurduğu kanonik gövde gider. ---
    @staticmethod
    def _get_satirlari(govde: bytes, sinir: str) -> list:
        istekler, neden = P.batch_coz(govde, sinir)
        return [i[1] for i in istekler] if istekler is not None else [f"RED: {neden}"]

    def test_yeniden_kurma_gercek_ui5_kanonik(self):
        """(1) Gerçek UI5 V2/V4 gövdeleri → kanonik gövde: yeni sınır, prolog/epilog yok, GET satırları + sırası aynı."""
        vakalar = {"V2": ("/sap/opu/odata/sap/ZTEST_SRV/$batch", self.GERCEK_V2,
                          "multipart/mixed;boundary=batch_de13-ec17-b0e3", "batch_de13-ec17-b0e3"),
                   "V4": ("/sap/opu/odata4/sap/ztest/srvd/sap/ztest/0001/$batch", self.GERCEK_V4,
                          "multipart/mixed; boundary=batch_id-1790435372243-11", "batch_id-1790435372243-11")}
        yanlis = []
        for ad, (yol, govde, tip, eski_sinir) in vakalar.items():
            k, ktip, neden = P.batch_yeniden_kur(yol, govde, tip)
            if k is None:
                yanlis.append(f"{ad}: red {neden}")
                continue
            sinir = P.sinir_al(ktip) or ""
            parca_n = len(self._get_satirlari(govde, eski_sinir))
            kosullar = {
                "tip biçimi": ktip == f"multipart/mixed; boundary={sinir}" and sinir.startswith("batch_axet_")
                and len(sinir) == len("batch_axet_") + 32,
                "GET satırları+sıra": self._get_satirlari(k, sinir) == self._get_satirlari(govde, eski_sinir),
                "prolog yok": k.startswith(b"--" + sinir.encode() + b"\r\n"),
                "epilog yok": k.endswith(b"\r\n--" + sinir.encode() + b"--\r\n") and b"Group ID" not in k,
                "eski sınır yok": eski_sinir.encode() not in k,
                "GET'teki Content-Type taşınmadı": k.count(b"Content-Type") == parca_n
                and b"application/json;charset" not in k,
                "istemci baytı değil": k != govde,
            }
            yanlis += [f"{ad}: {kosul}" for kosul, v in kosullar.items() if not v]
        # Kanonik biçimin TAM baytları (sabit sınırla) — biçim sessizce kaymasın.
        k, _t, _n = P.batch_yeniden_kur("/sap/opu/odata/sap/X/$batch", self.V2_OKUMA, self.MP, sinir="batch_axet_T")
        beklenen = (b"--batch_axet_T\r\nContent-Type: application/http\r\nContent-Transfer-Encoding: binary\r\n\r\n"
                    b"GET Orders?$skip=0&$top=20 HTTP/1.1\r\nsap-cancel-on-close: true\r\nAccept: application/json\r\n"
                    b"DataServiceVersion: 2.0\r\nMaxDataServiceVersion: 2.0\r\n\r\n\r\n"
                    b"--batch_axet_T\r\nContent-Type: application/http\r\nContent-Transfer-Encoding: binary\r\n\r\n"
                    b"GET Orders/$count HTTP/1.1\r\nAccept: text/plain\r\n\r\n\r\n--batch_axet_T--\r\n")
        if k != beklenen:
            yanlis.append(f"kanonik baytlar: {k!r}")
        # Sınır her istekte yeni (tahmin edilemez) üretilir.
        s1 = P.batch_yeniden_kur("/sap/opu/odata/sap/X/$batch", self.V2_OKUMA, self.MP)[1]
        s2 = P.batch_yeniden_kur("/sap/opu/odata/sap/X/$batch", self.V2_OKUMA, self.MP)[1]
        if s1 == s2:
            yanlis.append("sınır rastgele değil")
        ok = not yanlis
        H.kaydet("proxy yeniden kurma: gerçek UI5 V2/V4 → kanonik (yeni sınır, prolog/epilog yok, sıra aynı)",
                 "0 sapma", str(yanlis or 0), ok)
        self.assertTrue(ok, yanlis)

    def test_kanonik_oz_denetim_bozuk_kurmayi_reddeder(self):
        """Son emniyet: kurulan gövde kendi denetiminden geçmez ya da GET satırı/sırası kayarsa → red (fail-closed).
        Kurucu bilerek bozulur (parça düşürme · sıra çevirme · DELETE ekleme); kontrol: bozulmamış kurucu geçer."""
        asil = P.kanonik_batch
        bozuklar = {
            "son parça düşer": lambda ist, s=None: asil(ist[:-1], s),
            "sıra ters": lambda ist, s=None: asil(list(reversed(ist)), s),
            "DELETE eklenir": lambda ist, s=None: (lambda g, t: (g.replace(b"GET Orders/$count", b"DELETE Orders(1)"),
                                                                 t))(*asil(ist, s)),
        }
        sonuc = {}
        try:
            for ad, f in bozuklar.items():
                P.kanonik_batch = f
                sonuc[ad] = P.batch_yeniden_kur("/sap/opu/odata/sap/X/$batch", self.V2_OKUMA, self.MP)[0] is None
        finally:
            P.kanonik_batch = asil
        kontrol = P.batch_yeniden_kur("/sap/opu/odata/sap/X/$batch", self.V2_OKUMA, self.MP)[0] is not None
        ok = all(sonuc.values()) and kontrol
        H.kaydet("proxy yeniden kurma öz-denetimi: bozuk kurulum → red · sağlam kurulum geçer", "3/3 red · geçer",
                 f"{sum(sonuc.values())}/3 red · {'geçer' if kontrol else 'RED'}", ok)
        self.assertTrue(ok, (sonuc, kontrol))

    def test_bulgu1_atlatmalari_403_ve_kanonikte_delete_yok(self):
        """(2) Bulgu 1'in her varyantı İKİ BAĞIMSIZ katmanda ölçülür: (i) kapı 403 verir; (ii) kapının o savunması
        (sınır taraması / sınır parametresi kuralı) OLMASA bile yeniden kurulan gövdede DELETE yoktur."""
        z, PB, GET_P, MP1 = self.zarf, self.PB, self.GET_P, self.MP1
        v2 = "/sap/opu/odata/sap/X/$batch"
        dp = PB + b"DELETE Orders(1) HTTP/1.1\r\n\r\n"

        def gizli(s: bytes) -> bytes:  # `s` sınırıyla kurulmuş, içinde DELETE parçası olan gizli batch
            return s + b"\r\n" + dp + b"\r\n" + s + b"--\r\n"
        vakalar = {   # ad: (gövde, istek tipi, eski/gevşek ayrıştırıcının kullanacağı sınır)
            "prolog satır ortası x--B + DELETE": (z(GET_P, prolog=b"x--batch_1\r\n" + dp + b"\r\n"), MP1, "batch_1"),
            "prolog büyük harfli sınır": (z(GET_P, prolog=gizli(b"--BATCH_1")), MP1, "batch_1"),
            "epilog büyük harfli sınır": (z(GET_P, epilog=gizli(b"--Batch_1")), MP1, "batch_1"),
            "sınır satırında sondaki boşluk (padding)": (z(GET_P, prolog=gizli(b"--batch_1  ")), MP1, "batch_1"),
            "boundary='B' (tek tırnak)": (gizli(b"--batch_1") + z(GET_P).replace(b"--batch_1", b"--'batch_1'"),
                                          "multipart/mixed; boundary='batch_1'", "'batch_1'"),
            "boundary = B (boşluklu)": (z(GET_P, prolog=gizli(b"-- batch_1")), "multipart/mixed; boundary = batch_1",
                                        "batch_1"),
            "BOUNDARY=B": (z(GET_P, prolog=gizli(b"-- batch_1")), "multipart/mixed; BOUNDARY=batch_1", "batch_1"),
        }
        red_olmayan, delete_tasiyan, ikinci_katman_kurdu = [], [], 0
        for ad, (g, tip, gevsek) in vakalar.items():
            if P.batch_yeniden_kur(v2, g, tip)[0] is not None or P.izin_ver("POST", v2, g, tip)[0]:
                red_olmayan.append(ad)
            istekler, _ = P.batch_coz(g, gevsek, sinir_taramasi=False)
            if istekler is not None:
                ikinci_katman_kurdu += 1
                if b"DELETE" in P.kanonik_batch(istekler)[0]:
                    delete_tasiyan.append(ad)
        n = len(vakalar)
        ok = not red_olmayan and not delete_tasiyan and ikinci_katman_kurdu >= 5
        H.kaydet("proxy Bulgu 1: gizli/harf/padding/tırnak/boşluklu sınır → 403 · savunmasız kurulumda da DELETE yok",
                 f"{n}/{n} 403 · 0 DELETE · ≥5 kuruldu",
                 f"{n - len(red_olmayan)}/{n} 403 · {len(delete_tasiyan)} DELETE · {ikinci_katman_kurdu} kuruldu", ok)
        self.assertTrue(ok, (red_olmayan, delete_tasiyan, ikinci_katman_kurdu))

    def test_beyaz_liste_disi_ic_baslik_iletilmez(self):
        """(3) İç istekte beyaz liste dışı başlık (X-Method-Override, GET'te Content-Length / Content-Type, If-Match,
        Prefer …) ve parça düzeyindeki bilinmeyen başlık kanonik gövdeye TAŞINMAZ; beyaz listedekiler taşınır."""
        parca = (b"Content-Type: application/http\r\nContent-Transfer-Encoding: binary\r\nContent-ID: 7\r\n"
                 b"X-Parca-Ek: 1\r\n\r\nGET Orders(1) HTTP/1.1\r\n"
                 b"Accept: application/json\r\nX-Method-Override: DELETE\r\nX-Method: DELETE\r\nContent-Length: 0\r\n"
                 b"Content-Type: application/json\r\nIf-Match: *\r\nPrefer: return=minimal\r\nOData-Version: 4.0\r\n"
                 b"odata-maxversion: 4.0\r\nsap-contextid-accept: header\r\nX-CSRF-Token: Fetch\r\n\r\n")
        k, _t, neden = P.batch_yeniden_kur("/sap/opu/odata/sap/X/$batch", self.zarf(parca), self.MP1,
                                           sinir="batch_axet_T")
        k = (k or b"").lower()
        yasak = [b"x-method-override", b"x-method:", b"content-length", b"application/json\r\ncontent-type",
                 b"if-match", b"prefer", b"x-parca-ek", b"x-csrf-token", b"content-type: application/json"]
        tasinmali = [b"accept: application/json", b"odata-version: 4.0", b"odata-maxversion: 4.0",
                     b"sap-contextid-accept: header", b"content-id: 7", b"get orders(1) http/1.1"]
        sizan = [y.decode() for y in yasak if y in k]
        eksik = [t.decode() for t in tasinmali if t not in k]
        ok = bool(k) and not sizan and not eksik
        H.kaydet("proxy yeniden kurma: beyaz liste dışı iç başlık SAP'ye gitmez", "0 sızan · 0 eksik",
                 f"{len(sizan)} sızan {sizan} · {len(eksik)} eksik {eksik} · {neden}", ok)
        self.assertTrue(ok, (sizan, eksik, neden))

    def test_uctan_uca_kanonik_govde_ve_yanit_eslemesi(self):
        """(4) Uçtan uca: SAP'ye giden Content-Type kanonik sınırı, gövde kanonik biçimi taşır (bağımsız bir
        ayrıştırıcıyla — `email` — okunur); sahte SAP her GET parçasına SIRAYLA 200 + JSON yanıt parçası döner, yanıt
        istemciye olduğu gibi gelir ve istemci onu YANITIN Content-Type sınırıyla ayrıştırır (UI5'in yaptığı gibi) →
        yanıt parçaları istek sırasıyla eşleşir. Gerçek UI5 V2 (prolog'lu) ve V4 (epilog'lu) gövdeleriyle."""
        import email
        import email.policy
        import http.client
        import ssl

        def coz(tip: str, govde: bytes) -> list:
            m = email.message_from_bytes(b"Content-Type: " + tip.encode() + b"\r\n\r\n" + govde,
                                         policy=email.policy.HTTP)
            return [p.get_payload(decode=True) for p in m.iter_parts()]
        H.proxy_bypass_surec_ici()
        kok = Path(tempfile.mkdtemp(prefix="ui5proxy_"))
        (kok / "index.html").write_bytes(b"<html/>")
        sapa = []
        try:
            with H.SahteSunucu({}) as sap:
                def _post(h):
                    g = h.rfile.read(int(h.headers.get("Content-Length") or 0))
                    tip = h.headers.get("Content-Type")
                    satirlar = [p.split(b"\r\n", 1)[0] for p in coz(tip, g)]
                    sapa.append((tip, g, satirlar))
                    yb = b"batchresponse_sahte-1"
                    yanit = b"".join(b"--" + yb + b"\r\nContent-Type: application/http\r\nContent-Transfer-Encoding: "
                                     b"binary\r\n\r\nHTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n"
                                     + json.dumps({"sira": i, "istek": s.decode("utf-8")}).encode() + b"\r\n"
                                     for i, s in enumerate(satirlar)) + b"--" + yb + b"--\r\n"
                    h.send_response(202)
                    h.send_header("Content-Type", "multipart/mixed; boundary=" + yb.decode())
                    h.send_header("Content-Length", str(len(yanit)))
                    h.end_headers()
                    h.wfile.write(yanit)
                sap.httpd.RequestHandlerClass.do_POST = _post
                srv = P.Sunucu(("127.0.0.1", 0), P.isleyici_sinifi(kok, sap.url, "100", (H.KULLANICI, H.PAROLA),
                                                                     ssl.create_default_context()))
                threading.Thread(target=srv.serve_forever, daemon=True).start()
                port = srv.server_address[1]

                def gonder(yol, tip, govde):
                    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
                    try:
                        c.request("POST", yol, body=govde, headers={"Content-Type": tip})
                        r = c.getresponse()
                        return r.status, r.getheader("Content-Type") or "", r.read()
                    finally:
                        c.close()
                try:
                    sonuc = {
                        "V2": (self.GERCEK_V2, gonder("/sap/opu/odata/sap/ZTEST_SRV/$batch",
                                                      "multipart/mixed;boundary=batch_de13-ec17-b0e3", self.GERCEK_V2),
                               "batch_de13-ec17-b0e3"),
                        "V4": (self.GERCEK_V4, gonder("/sap/opu/odata4/sap/ztest/srvd/sap/ztest/0001/$batch",
                                                      "multipart/mixed; boundary=batch_id-1790435372243-11",
                                                      self.GERCEK_V4), "batch_id-1790435372243-11")}
                finally:
                    srv.shutdown()
                    srv.server_close()
        finally:
            shutil.rmtree(kok, ignore_errors=True)
        yanlis = []
        for i, (ad, (istemci_govde, (durum, ytip, ygovde), eski_sinir)) in enumerate(sonuc.items()):
            tip, g, satirlar = sapa[i] if i < len(sapa) else ("", b"", [])
            beklenen = self._get_satirlari(istemci_govde, eski_sinir)
            yanitlar = [json.loads(p.split(b"\r\n\r\n", 1)[1]) for p in coz(ytip, ygovde)] if durum == 202 else []
            kosullar = {
                "SAP'ye kanonik tip": tip.startswith("multipart/mixed; boundary=batch_axet_"),
                "SAP'ye kanonik gövde": g.startswith(b"--" + tip.split("=", 1)[-1].encode() + b"\r\n")
                and eski_sinir.encode() not in g and b"Group ID" not in g,
                "SAP'nin gördüğü GET'ler = istemcininki": satirlar == beklenen,
                "yanıt olduğu gibi (202 + kendi sınırı)": durum == 202 and ytip.endswith("batchresponse_sahte-1"),
                "yanıt eşlemesi sıra ile": [y["istek"].encode("utf-8") for y in yanitlar] == beklenen
                and [y["sira"] for y in yanitlar] == list(range(len(beklenen))),
            }
            yanlis += [f"{ad}: {k}" for k, v in kosullar.items() if not v]
        ok = not yanlis and len(sapa) == 2
        H.kaydet("proxy uçtan uca: SAP'ye kanonik tip+gövde · yanıt aynen döner, parçalar istek sırasıyla eşleşir",
                 "2/2 · 0 sapma", f"{len(sapa)}/2 · {yanlis or 0}", ok)
        self.assertTrue(ok, yanlis)

    def test_host_basligi(self):
        vakalar = [
            (("localhost:8484", 8484), True), (("127.0.0.1:8484", 8484), True), (("LOCALHOST:8484", 8484), True),
            (("saldirgan.example:8484", 8484), False), (("localhost:9999", 8484), False), (("localhost", 8484), False),
            ((None, 8484), False), (("", 8484), False), (("127.0.0.1.saldirgan.example:8484", 8484), False),
            (("localhost", 80), True),
        ]
        yanlis = [(g, b) for g, b in vakalar if P.host_gecerli(*g) != b]
        ok = not yanlis
        H.kaydet("proxy host_gecerli: yalnız localhost/127.0.0.1:<port>", "10/10", f"{10 - len(yanlis)}/10", ok)
        self.assertTrue(ok, yanlis)

    def test_uctan_uca_host_ve_icerik_tipi(self):
        """Kablolama: yabancı Host → 403 + SAP'ye 0 istek; do_POST istek Content-Type'ını izin_ver'e iletir."""
        H.proxy_bypass_surec_ici()
        kok = Path(tempfile.mkdtemp(prefix="ui5proxy_"))
        (kok / "index.html").write_bytes(b"<html/>")
        try:
            with H.SahteSunucu({"/sap/opu/odata/sap/X/Set": b'{"d":[]}'}) as sap:
                import ssl
                srv = P.Sunucu(("127.0.0.1", 0), P.isleyici_sinifi(kok, sap.url, "100", (H.KULLANICI, H.PAROLA),
                                                                     ssl.create_default_context()))
                threading.Thread(target=srv.serve_forever, daemon=True).start()
                port = srv.server_address[1]
                taban = f"http://127.0.0.1:{port}"

                # SahteSunucu POST işlemez (501 + gövde okunmadan kapanış → proxy'de ara sıra 502: ölçüldü 1/8).
                # Deterministik olsun: gövdeyi okuyan, isteği kaydeden 202 yanıtçısı.
                def _post(h):
                    h.rfile.read(int(h.headers.get("Content-Length") or 0))
                    sap.istekler.append("POST " + h.path.split("?", 1)[0])
                    h.send_response(202)
                    h.send_header("Content-Length", "0")
                    h.end_headers()
                sap.httpd.RequestHandlerClass.do_POST = _post

                def kod(yol, host=None, yontem="GET", govde=None, tip=None):
                    h = {}
                    if host:
                        h["Host"] = host
                    if tip:
                        h["Content-Type"] = tip
                    req = urllib.request.Request(taban + yol, method=yontem, data=govde, headers=h)
                    try:
                        return urllib.request.urlopen(req, timeout=10).status
                    except urllib.error.HTTPError as e:
                        return e.code
                try:
                    yabanci = kod("/sap/opu/odata/sap/X/Set", host=f"saldirgan.example:{port}")
                    sonra_sap = len(sap.istekler)
                    dogru = kod("/sap/opu/odata/sap/X/Set", host=f"localhost:{port}")
                    # İletilen batch 202 döner (= SAP'ye GİTTİ); reddedilen 403 ve SAP'de iz bırakmaz.
                    json_tip = kod("/sap/opu/odata/sap/X/$batch", yontem="POST", govde=self.V2_OKUMA,
                                   tip="application/json")
                    mp_tip = kod("/sap/opu/odata/sap/X/$batch", yontem="POST", govde=self.V2_OKUMA, tip=self.MP)
                finally:
                    srv.shutdown()
                    srv.server_close()
                post_iz = [i for i in sap.istekler if i.startswith("POST ")]
        finally:
            shutil.rmtree(kok, ignore_errors=True)
        gercek = (yabanci, sonra_sap, dogru, json_tip, mp_tip, post_iz)
        ok = gercek == (403, 0, 200, 403, 202, ["POST /sap/opu/odata/sap/X/$batch"])
        H.kaydet("proxy uçtan uca: yabancı Host 403/0 istek · JSON tip 403", "403/0/200/403/202 · 1 POST",
                 str(gercek[:5]) + f" · {len(post_iz)} POST", ok)
        self.assertTrue(ok, gercek)

    def test_uctan_uca_yazma_sapye_gitmez(self):
        H.proxy_bypass_surec_ici()
        kok = Path(tempfile.mkdtemp(prefix="ui5proxy_"))
        (kok / "index.html").write_bytes(b"<html/>")
        try:
            with H.SahteSunucu({"/sap/opu/odata/sap/X/Set": b'{"d":[]}'}) as sap:
                import ssl
                srv = P.Sunucu(("127.0.0.1", 0), P.isleyici_sinifi(kok, sap.url, "100", (H.KULLANICI, H.PAROLA),
                                                                     ssl.create_default_context()))
                threading.Thread(target=srv.serve_forever, daemon=True).start()
                taban = f"http://127.0.0.1:{srv.server_address[1]}"
                try:
                    kodlar = {}
                    for yontem, yol in (("GET", "/sap/opu/odata/sap/X/Set"), ("DELETE", "/sap/opu/odata/sap/X/Set"),
                                        ("POST", "/sap/opu/odata/sap/X/Set"), ("GET", "/index.html")):
                        req = urllib.request.Request(taban + yol, method=yontem, data=b"{}" if yontem == "POST" else None)
                        try:
                            kodlar[(yontem, yol)] = urllib.request.urlopen(req, timeout=10).status
                        except urllib.error.HTTPError as e:
                            kodlar[(yontem, yol)] = e.code
                finally:
                    srv.shutdown()
                    srv.server_close()
                sap_istek = list(sap.istekler)
        finally:
            shutil.rmtree(kok, ignore_errors=True)
        degerler = list(kodlar.values())
        ok = degerler == [200, 403, 403, 200] and sap_istek == ["/sap/opu/odata/sap/X/Set?sap-client=100"]
        H.kaydet("proxy uçtan uca: GET iletilir (auth'lu), DELETE/POST 403 + SAP'ye 0 istek", "200/403/403/200 · 1",
                 f"{degerler} · {len(sap_istek)}", ok)
        self.assertTrue(ok, (kodlar, sap_istek))


class TestAnlikKur(unittest.TestCase):
    """Z160 `anlik-kur`: kaynağı yerelde olan uygulama için `.canli/` — yerel dist ↔ canlı tam liste.
    Kontrol grubu: eşit → yazılır; negatifler: fark (yazılmaz) · zaten var · canlıda yok · ölçülemez."""

    def _kos(self, sunulan, *ek, kullanici=H.KULLANICI, onceden_anlik=False):
        with H.SahteSunucu(sunulan, kullanici=kullanici) as srv:
            app = H.gecici_app(url=srv.url)
            try:
                if onceden_anlik:
                    K.anlik_yaz(app, {"Component-preload.js": H.PRELOAD}, {"bsp": BSP})
                rc, out = H.kos("fetch_ui_source.py", "anlik-kur", app, "--no-build", *ek, kimlik=True)
                anlik = K.anlik_oku(app)
                gi = (app / ".gitignore").read_text(encoding="utf-8") if (app / ".gitignore").is_file() else ""
                return rc, out, anlik, gi, list(srv.istekler)
            finally:
                H.temizle(app)

    def test_esit_yazilir_ve_gitignore(self):
        rc, out, anlik, gi, _ = self._kos({H.odata_yol(BSP): H.odata_zip({"Component-preload.js": H.PRELOAD})})
        ok = (rc == 0 and anlik is not None and anlik[0] == {"Component-preload.js": H.PRELOAD}
              and anlik[1].get("kaynak") == "anlik-kur" and ".canli/" in gi.splitlines() and "KAPSAM" in out)
        H.kaydet("anlik-kur: yerel dist == canlı → .canli yazılır + .gitignore", "rc=0 yazıldı", f"rc={rc}", ok)
        self.assertTrue(ok, out)

    def test_fark_yazilmaz(self):
        canli = {"Component-preload.js": H.PRELOAD, "localService/metadata.xml": b"<x/>"}
        rc, out, anlik, gi, _ = self._kos({H.odata_yol(BSP): H.odata_zip(canli)})
        ok = rc == 1 and anlik is None and ".canli" not in gi and "Hiçbir şey yazılmadı" in out
        H.kaydet("anlik-kur: canlıda yerelde olmayan dosya → yazılmaz", "rc=1 yok", f"rc={rc} anlik={anlik is not None}", ok)
        self.assertTrue(ok, out)

    def test_fark_kabul_ile_yazilir(self):
        canli = {"Component-preload.js": H.PRELOAD, "localService/metadata.xml": b"<x/>"}
        rc, out, anlik, gi, _ = self._kos({H.odata_yol(BSP): H.odata_zip(canli)}, "--kabul")
        ok = (rc == 0 and anlik is not None and set(anlik[0]) == set(canli) and "--kabul" in anlik[1].get("kaynak", "")
              and "EZER" in out)
        H.kaydet("anlik-kur: fark + --kabul → şimdiki canlı yazılır, uyarı", "rc=0 canlı", f"rc={rc}", ok)
        self.assertTrue(ok, out)

    def test_zaten_var_dokunmaz(self):
        rc, out, anlik, gi, istek = self._kos({H.odata_yol(BSP): H.odata_zip({"x.js": b"1"})}, onceden_anlik=True)
        ok = rc == 1 and "YAZILMAZ" in out and anlik[0] == {"Component-preload.js": H.PRELOAD} and istek == []
        H.kaydet("anlik-kur: .canli zaten var → dokunmaz, ağ yok", "rc=1 istek=0", f"rc={rc} istek={len(istek)}", ok)
        self.assertTrue(ok, out)

    def test_bozuk_anlik_cikmaz_degil_yol_gosterir(self):
        """`.canli/` var ama bilgi.json yok → deploy YOK sayar; anlik-kur "zaten var" deyip çıkmaz ÜRETMEZ: rc 2 +
        silme talimatı, ağ yok, klasöre dokunulmaz."""
        with H.SahteSunucu({H.odata_yol(BSP): H.odata_zip({"x.js": b"1"})}) as srv:
            app = H.gecici_app(url=srv.url)
            try:
                (app / ".canli" / "dist").mkdir(parents=True)
                rc, out = H.kos("fetch_ui_source.py", "anlik-kur", app, "--no-build", kimlik=True)
                kalan = (app / ".canli" / "dist").is_dir()
                istek = list(srv.istekler)
            finally:
                H.temizle(app)
        ok = rc == 2 and "eksik/bozuk" in out and kalan and istek == []
        H.kaydet("anlik-kur: bozuk .canli → rc 2 + yol gösterir, dokunmaz", "rc=2 istek=0", f"rc={rc} istek={len(istek)}", ok)
        self.assertTrue(ok, out)

    def test_canlida_yok_yazmaz(self):
        rc, out, anlik, gi, istek = self._kos({})
        ok = rc == 0 and anlik is None and "ilk deploy" in out and len(istek) == 2
        H.kaydet("anlik-kur: canlıda BSP yok (OData+ADT 404) → yazacak şey yok", "rc=0 yok istek=2",
                 f"rc={rc} istek={len(istek)}", ok)
        self.assertTrue(ok, out)

    def test_olculemez_yazmaz(self):
        """Yetki reddi (401) "yok" SAYILMAZ → ölçülemedi, exit 2."""
        rc, out, anlik, gi, _ = self._kos({H.odata_yol(BSP): H.odata_zip({"x.js": b"1"})}, kullanici="baska")
        ok = rc == 2 and anlik is None and "ölçülemedi" in out
        H.kaydet("anlik-kur: 401 → ölçülemedi, yazılmaz", "rc=2", f"rc={rc}", ok)
        self.assertTrue(ok, out)


# ───────────────────────── Z168: metadata --kaydet + kimlik sırası (env → .conn_adt → pencere) ─────────────────────────

F = _modul("fetch_ui_source_t", "fetch_ui_source.py")
MD_SERVIS = "ZXX001_UI_ORDER_O2"
MD_YOL = f"/sap/opu/odata/sap/{MD_SERVIS}/$metadata"
MD1 = TestMetadataTipKapsamli.META
MD2 = MD1.replace(b'sap:label="Belge"/>', b'sap:label="Belge"/><Property Name="YeniAlan" Type="Edm.String"/>')
GIRIS_HTML = b"<!DOCTYPE html><html><head><title>Logon</title></head><body><form>&nbsp;</form></body></html>"
GIRIS_XHTML = (b'<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Logon</title></head>'
               b'<body><form action="/sap/bc/x"><input name="sap-user"/></form></body></html>')
CONN_KULLANICI, CONN_PAROLA = "connkul", "conn#Parola!9"  # SAHTE .conn_adt kimliği — gerçek değil


def _manifest(kaynaklar: dict) -> str:
    return json.dumps({"sap.app": {"id": "zxx001.order", "dataSources": kaynaklar}})


def _app_kur(kok: Path, kaynaklar: dict | None = None, mock_yaml: str | None = None) -> Path:
    app = kok / "order_app"
    (app / "webapp").mkdir(parents=True)
    kaynaklar = kaynaklar if kaynaklar is not None else {
        "mainService": {"uri": f"/sap/opu/odata/sap/{MD_SERVIS}/", "type": "OData", "settings": {"odataVersion": "2.0"}}}
    (app / "webapp" / "manifest.json").write_text(_manifest(kaynaklar), encoding="utf-8")
    if mock_yaml is not None:
        (app / "ui5-mock.yaml").write_text(mock_yaml, encoding="utf-8")
    return app


def _conn_yaz(proje: Path, url: str, kullanici: str = CONN_KULLANICI, parola: str = CONN_PAROLA) -> None:
    proje.mkdir(parents=True, exist_ok=True)
    (proje / ".conn_adt").write_text(f"ADT_SAP_URL={url}\nADT_SAP_CLIENT=100\nADT_SAP_USER={kullanici}\n"
                                     f"ADT_SAP_PASSWORD={parola}\nADT_SAP_TIER=DEV\n", encoding="utf-8")


class TestMetadataKaydet(unittest.TestCase):
    """C1 — `metadata --kaydet`: tam yanıt bayt bayt yazılır, önce/sonra özeti, EDMX olmayan yanıt yazılmaz."""

    def setUp(self):
        self.kok = Path(tempfile.mkdtemp(prefix="ui5md_"))

    def tearDown(self):
        shutil.rmtree(self.kok, ignore_errors=True)

    def test_md_kaydet_yeni_ustune_ve_ayni(self):
        app = _app_kur(self.kok)
        hedef = app / "webapp" / "localService" / "mainService" / "metadata.xml"
        cikti = []
        for govde in (MD1, MD2, MD2):
            with H.SahteSunucu({MD_YOL: govde}) as srv:
                cikti.append(H.kos("fetch_ui_source.py", "metadata", MD_SERVIS, "--kaydet", "--app", app,
                                   "--url", srv.url, "--client", "100", "--alan", "YeniAlan", "--tip", "SiparisType",
                                   kimlik=True))
            if govde is MD1:
                ilk = hedef.read_bytes() if hedef.is_file() else None
        (rc1, o1), (rc2, o2), (rc3, o3) = cikti
        ok = (ilk == MD1 and rc1 == 1 and "dosya yoktu" in o1 and "[YOK] YeniAlan" in o1
              and "kimlik: env" in o1 and "varsayılan (mainService)" in o1
              and hedef.read_bytes() == MD2 and rc2 == 0 and "Property +1 eklenen / -0 kalkan" in o2
              and "+ SiparisType.YeniAlan" in o2 and "[VAR] SiparisType.YeniAlan" in o2
              and rc3 == 0 and "bayt bayt aynı" in o3 and not list(hedef.parent.glob("*.yeni"))
              and all(H.PAROLA not in o for o in (o1, o2, o3)))
        H.kaydet("metadata --kaydet: yeni → üstüne (+1 Property) → aynı (yazmaz)", "rc 1/0/0",
                 f"rc {rc1}/{rc2}/{rc3}", ok)
        self.assertTrue(ok, o1 + o2 + o3)

    def test_md_html_reddi(self):
        """Giriş sayfası: XML değil (HTML) ya da XML olarak ayrışan XHTML → exit 2, dosya YOK; --alan ile de "alan yok"
        (exit 1) hükmü verilmez (XHTML 0 EntityType'ı yanlış negatif üretiyordu)."""
        app = _app_kur(self.kok)
        hedef = app / "webapp" / "localService" / "mainService" / "metadata.xml"
        sonuc = []
        for govde in (GIRIS_HTML, GIRIS_XHTML):
            with H.SahteSunucu({MD_YOL: govde}) as srv:
                sonuc.append(H.kos("fetch_ui_source.py", "metadata", MD_SERVIS, "--kaydet", "--app", app,
                                   "--url", srv.url, "--client", "100", kimlik=True))
                sonuc.append(H.kos("fetch_ui_source.py", "metadata", MD_SERVIS, "--alan", "Vbeln",
                                   "--url", srv.url, "--client", "100", kimlik=True))
        ok = (all(rc == 2 and "EDMX değil" in o for rc, o in sonuc) and not hedef.exists()
              and "dosya YAZILMADI" in sonuc[0][1] and "kök <html>" in sonuc[2][1]
              and not any("[YOK]" in o for _, o in sonuc))
        H.kaydet("metadata: HTML/XHTML giriş sayfası → exit 2, dosya yok, alan hükmü yok", "4×rc=2",
                 str([rc for rc, _ in sonuc]), ok)
        self.assertTrue(ok, "\n".join(o for _, o in sonuc))

    def test_md_kayit_yolu_sirasi(self):
        """① ui5-mock.yaml metadataPath ② manifest localUri ③ mainService varsayılanı ④ başka servis → yazmaz;
        ①≠② → UYARI; türetilen yol uygulama dışına çıkamaz; açık yol aynen."""
        import argparse
        mock_yaml = ("server:\n  customMiddleware:\n    - name: sap-fe-mockserver\n      configuration:\n"
                     "        services:\n          - urlPath: '/sap/opu/odata/sap/ZBASKA_SRV'\n"
                     "            metadataPath: './webapp/localService/baska/metadata.xml'\n"
                     f"          - urlPath: '/sap/opu/odata/sap/{MD_SERVIS}'\n"
                     "            metadataPath: './webapp/localService/mock/metadata.xml'\n")
        ana = {"uri": f"/sap/opu/odata/sap/{MD_SERVIS}/", "settings": {"localUri": "localService/lu/metadata.xml"}}
        vh = {"uri": "/sap/opu/odata/sap/ZVH_SRV/", "settings": {}}
        durumlar = {
            "mock+localUri farklı": ({"mainService": ana}, mock_yaml, MD_SERVIS),
            "yalnız localUri": ({"mainService": ana}, None, MD_SERVIS),
            "mainService varsayılan": ({"mainService": {"uri": f"/sap/opu/odata/sap/{MD_SERVIS}/"}}, None, MD_SERVIS),
            "vh localUri yok": ({"mainService": ana, "vhService": vh}, None, "ZVH_SRV"),
            "manifest'te yok": ({"mainService": ana}, None, "ZYOK_SRV"),
            "dışarı kaçan localUri": ({"mainService": {"uri": f"/sap/opu/odata/sap/{MD_SERVIS}/",
                                                       "settings": {"localUri": "../../../kacis.xml"}}}, None, MD_SERVIS),
        }
        sonuc = {}
        for i, (ad, (ks, my, servis)) in enumerate(durumlar.items()):
            app = _app_kur(self.kok / str(i), ks, my)
            yol, notlar = F._kayit_yolu(argparse.Namespace(kaydet="", app=str(app)), servis)
            sonuc[ad] = (yol.relative_to(app.resolve()).as_posix() if yol else None, " ".join(notlar))
        acik, _ = F._kayit_yolu(argparse.Namespace(kaydet=str(self.kok / "x.xml"), app=None), MD_SERVIS)
        yolsuz, nt = F._kayit_yolu(argparse.Namespace(kaydet="", app=None), MD_SERVIS)
        ok = (sonuc["mock+localUri farklı"][0] == "webapp/localService/mock/metadata.xml"
              and "[UYARI]" in sonuc["mock+localUri farklı"][1]
              and sonuc["yalnız localUri"] == ("webapp/localService/lu/metadata.xml", sonuc["yalnız localUri"][1])
              and "[UYARI]" not in sonuc["yalnız localUri"][1]
              and sonuc["mainService varsayılan"][0] == "webapp/localService/mainService/metadata.xml"
              and sonuc["vh localUri yok"][0] is None and "vhService" in sonuc["vh localUri yok"][1]
              and sonuc["manifest'te yok"][0] is None
              and sonuc["dışarı kaçan localUri"][0] is None and "DIŞINDA" in sonuc["dışarı kaçan localUri"][1]
              and acik == self.kok / "x.xml" and yolsuz is None and "--app" in nt[0])
        H.kaydet("metadata --kaydet yol sırası ①–④ + uyarı + kaçış reddi", "6 kol", str(sonuc), ok)
        self.assertTrue(ok, sonuc)


class TestMetadataKimlikSirasi(unittest.TestCase):
    """C2 — kimlik sırası env → .conn_adt (yalnız aynı sistem) → pencere. Süreç İÇİNDE koşar: pencere fonksiyonu mock'tur,
    GERÇEK pencere açılmaz. Her kolda sahte parolaların çıktıda geçmediği ölçülür."""

    def setUp(self):
        self.kok = Path(tempfile.mkdtemp(prefix="ui5mdk_"))

    def tearDown(self):
        shutil.rmtree(self.kok, ignore_errors=True)

    def _kos(self, argv, env_kimlik=False, pencere=None):
        import contextlib
        import io
        import os
        from unittest import mock
        cagri = []

        def sahte_pencere(servis, url, client, calistir=None):
            cagri.append(servis)
            return (pencere, None) if pencere else (None, "test: pencere kapalı")

        env = {k: v for k, v in os.environ.items()
               if k.upper() not in {"FIORI_TOOLS_USER", "FIORI_TOOLS_PASSWORD", "AXET_SAP_PROJECT_DIR",
                                    "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "ADT_SAP_USER", "ADT_SAP_PASSWORD"}}
        env.update(http_proxy="http://127.0.0.1:9", https_proxy="http://127.0.0.1:9", no_proxy="*")
        if env_kimlik:
            env.update(FIORI_TOOLS_USER=H.KULLANICI, FIORI_TOOLS_PASSWORD=H.PAROLA)
        o, e = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(F, "_pencere_kimlik", sahte_pencere), \
                contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
            rc = F.main(["metadata", MD_SERVIS, *map(str, argv)])
        return rc, o.getvalue() + e.getvalue(), cagri

    @staticmethod
    def _sizinti(out: str) -> bool:
        return any(s in out for s in (H.PAROLA, CONN_PAROLA))

    def test_md_kimlik_env_once(self):
        """env varken .conn_adt (yanlış kimlikli) ve pencere hiç kullanılmaz."""
        with H.SahteSunucu({MD_YOL: MD1}) as srv:
            _conn_yaz(self.kok, srv.url, "yanlis", "yanlis-parola")
            rc, out, cagri = self._kos(["--project-dir", self.kok], env_kimlik=True)
        ok = rc == 0 and "kimlik: env" in out and not cagri and not self._sizinti(out) and "yanlis-parola" not in out
        H.kaydet("metadata kimlik ①: env önce", "rc=0 env pencere=0", f"rc={rc} pencere={len(cagri)}", ok)
        self.assertTrue(ok, out)

    def test_md_kimlik_conn_adt(self):
        """env yok → .conn_adt (hedef .conn_adt'nin kendi sistemi) kullanılır, pencere açılmaz."""
        with H.SahteSunucu({MD_YOL: MD1}, kullanici=CONN_KULLANICI, parola=CONN_PAROLA) as srv:
            _conn_yaz(self.kok, srv.url + "/")  # sondaki `/` aynı sistem sayılır
            rc, out, cagri = self._kos(["--project-dir", self.kok])
        ok = rc == 0 and "kimlik: .conn_adt" in out and not cagri and not self._sizinti(out)
        H.kaydet("metadata kimlik ②: .conn_adt", "rc=0 .conn_adt pencere=0", f"rc={rc} pencere={len(cagri)}", ok)
        self.assertTrue(ok, out)

    def _kos_sertifika(self, conn_ssl=None, env_ssl=None):
        """http_get'i yakalar: hangi ignore_cert değeriyle çağrıldı (sahte sunucu HTTP; SSL'i gerçekten ölçmez)."""
        import os
        from unittest import mock
        gorulen = []

        def sahte_get(url, kimlik, ignore_cert):
            gorulen.append(ignore_cert)
            return MD1.encode("utf-8") if isinstance(MD1, str) else MD1
        _conn_yaz(self.kok, "https://sap.ornek.invalid:44300/")
        if conn_ssl is not None:
            with open(self.kok / ".conn_adt", "a", encoding="utf-8") as fh:
                fh.write(f"\nADT_SAP_SSL_VERIFY={conn_ssl}\n")
        ek = {"ADT_SAP_SSL_VERIFY": env_ssl} if env_ssl is not None else {}
        with mock.patch.object(F.B, "http_get", sahte_get), mock.patch.dict(os.environ, ek):
            if env_ssl is None:
                os.environ.pop("ADT_SAP_SSL_VERIFY", None)
            rc, out, _ = self._kos(["--project-dir", self.kok])
        return rc, out, gorulen

    def test_md_conn_adt_sertifika_adt_kurali(self):
        """.conn_adt kolu ADT kütüphanesinin kuralını izler: ayar yok/false → doğrulama kapalı; true → açık; env > dosya."""
        rc, out, g = self._kos_sertifika()
        self.assertEqual((0, [True]), (rc, g), out)
        self.assertIn("sertifika doğrulaması: kapalı", out)
        rc, out, g = self._kos_sertifika(conn_ssl="true")
        self.assertEqual((0, [False]), (rc, g), out)
        self.assertNotIn("sertifika doğrulaması: kapalı", out)
        rc, out, g = self._kos_sertifika(conn_ssl="true", env_ssl="false")
        self.assertEqual((0, [True]), (rc, g), out)
        # dotenv biçimleri: satır sonu yorumu · export · tekrar eden anahtarda son kazanır → doğrulama AÇIK kalır
        for bicim in ("true  # yorum", "false\nexport ADT_SAP_SSL_VERIFY=true", "false\nADT_SAP_SSL_VERIFY=true"):
            rc, out, g = self._kos_sertifika(conn_ssl=bicim)
            self.assertEqual((0, [False]), (rc, g), (bicim, out))

    def test_yonlendirme_baska_hosta_kimlik_tasimaz(self):
        """302 başka hosta (127.0.0.1 → 127.0.0.2) → Authorization düşer; aynı köken yönlendirmesinde korunur."""
        import http.server
        import threading
        gorulen = []

        class H2(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                gorulen.append((self.server.server_address[0], self.path, "Authorization" in self.headers))
                if self.path == "/baska":
                    self.send_response(302)
                    self.send_header("Location", f"http://127.0.0.2:{hedef.server_address[1]}/son")
                elif self.path == "/ayni":
                    self.send_response(302)
                    self.send_header("Location", "/son")
                else:
                    self.send_response(200)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"ok")

            def log_message(self, *a):
                pass
        try:
            hedef = http.server.HTTPServer(("127.0.0.2", 0), H2)
        except OSError as exc:
            self.skipTest(f"127.0.0.2 bağlanamadı: {exc}")
        kaynak = http.server.HTTPServer(("127.0.0.1", 0), H2)
        for s in (hedef, kaynak):
            threading.Thread(target=s.serve_forever, daemon=True).start()
        try:
            F.B.http_get(f"http://127.0.0.1:{kaynak.server_address[1]}/baska", ("u", "p"))
            F.B.http_get(f"http://127.0.0.1:{kaynak.server_address[1]}/ayni", ("u", "p"))
        finally:
            for s in (hedef, kaynak):
                s.shutdown()
                s.server_close()
        self.assertEqual([("127.0.0.1", "/baska", True), ("127.0.0.2", "/son", False),
                          ("127.0.0.1", "/ayni", True), ("127.0.0.1", "/son", True)], gorulen)

    def test_sistem_anahtari_gecersiz_port_traceback_vermez(self):
        self.assertNotEqual(F._sistem_anahtari("https://h:abc", "100"), F._sistem_anahtari("https://h", "100"))

    def test_md_ag_hatasi_host_maskelenir(self):
        import urllib.error
        from unittest import mock

        def hata(url, kimlik, ignore_cert):
            raise urllib.error.URLError("certificate is not valid for 'SAPHOST01.SAP.ORNEK.COM.TR'. (_ssl.c:1010)")
        _conn_yaz(self.kok, "https://sap.ornek.invalid:44300/", )
        with mock.patch.object(F.B, "http_get", hata):
            rc, out, _ = self._kos(["--project-dir", self.kok])
        self.assertEqual(2, rc, out)
        self.assertNotIn("SAPHOST01", out)
        self.assertIn("<host>", out)
        self.assertIn("_ssl.c", out)

    def test_md_kimlik_baska_host(self):
        """--url .conn_adt'den BAŞKA bir sistem → .conn_adt parolası oraya GÖNDERİLMEZ, pencereye geçilir."""
        with H.SahteSunucu({MD_YOL: MD1}) as srv:
            _conn_yaz(self.kok, "http://127.0.0.1:9")
            rc, out, cagri = self._kos(["--project-dir", self.kok, "--url", srv.url, "--client", "100"],
                                       pencere=(H.KULLANICI, H.PAROLA))
        ok = (rc == 0 and "kimlik: pencere" in out and cagri == [MD_SERVIS] and "başka sisteme gönderilmez" in out
              and not self._sizinti(out))
        H.kaydet("metadata kimlik: başka host → .conn_adt kullanılmadı → pencere", "rc=0 pencere=1",
                 f"rc={rc} pencere={len(cagri)}", ok)
        self.assertTrue(ok, out)

    def test_md_kimlik_hicbiri(self):
        """env yok · .conn_adt yok · pencere iptal → exit 2, SAP'ye istek YOK."""
        with H.SahteSunucu({MD_YOL: MD1}) as srv:
            rc, out, cagri = self._kos(["--project-dir", self.kok / "bos", "--url", srv.url, "--client", "100"])
            istek = list(srv.istekler)
        ok = rc == 2 and "[FAIL] kimlik yok" in out and cagri == [MD_SERVIS] and not istek and ".conn_adt yok" in out
        H.kaydet("metadata kimlik: hiçbiri → exit 2, istek 0", "rc=2 istek=0", f"rc={rc} istek={len(istek)}", ok)
        self.assertTrue(ok, out)

    def test_md_kimlik_401_sizdirmaz(self):
        """Pencereden gelen kimlik sunucuca reddedilir (401) → exit 2; parola çıktıda yok."""
        with H.SahteSunucu({MD_YOL: MD1}) as srv:
            rc, out, _ = self._kos(["--project-dir", self.kok / "bos", "--url", srv.url, "--client", "100"],
                                   pencere=("baska", CONN_PAROLA))
        ok = rc == 2 and "okunamadı" in out and not self._sizinti(out) and "kimlik: pencere" in out
        H.kaydet("metadata kimlik: 401 → exit 2, parola çıktıda yok", "rc=2", f"rc={rc}", ok)
        self.assertTrue(ok, out)


class TestPencereKimlik(unittest.TestCase):
    """`_pencere_kimlik`: PowerShell çağrısı SAHTE (`calistir`) — gerçek pencere açılmaz. Sır yalnız stdout borusunda
    base64 gelir; komut satırında, neden metninde (iptal / bozuk yanıt / zaman aşımı) GEÇMEZ."""
    SIR = "gizli!parola ğüş"

    def _kos(self, sahte, ps=("C:/Windows/powershell.exe", None)):
        from unittest import mock
        cagri = []

        def calistir(komut, **kw):
            cagri.append((komut, kw))
            return sahte(komut, **kw)

        with mock.patch.object(F, "_powershell_yolu", lambda: ps):
            sonuc = F._pencere_kimlik(MD_SERVIS, "http://127.0.0.1:1", "100", calistir=calistir)
        return sonuc, cagri

    @staticmethod
    def _b64(s: str) -> str:
        import base64
        return base64.b64encode(s.encode("utf-8")).decode()

    def test_pencere_basari_ve_komut_satiri(self):
        import base64
        import subprocess
        yanit = f"{self._b64('demo')} {self._b64(self.SIR)}".encode()
        (k, neden), cagri = self._kos(lambda komut, **kw: subprocess.CompletedProcess(komut, 0, yanit, b""))
        komut, kw = cagri[0]
        betik = base64.b64decode(komut[komut.index("-EncodedCommand") + 1]).decode("utf-16-le")
        ok = (k == ("demo", self.SIR) and neden is None and "Get-Credential" in betik
              and MD_SERVIS not in betik and MD_SERVIS in kw.get("env", {}).get(F._PS_MESAJ_ENV, "")
              and all(self.SIR not in x for x in komut) and kw.get("stdin") == subprocess.DEVNULL
              and kw.get("capture_output") is True and "-NoProfile" in komut)
        H.kaydet("pencere: base64 boru → kimlik; parola komut satırında yok", "ok", str(ok), ok)
        self.assertTrue(ok, (k, neden, komut))

    def test_pencere_iptal_bozuk_zaman_asimi_sizdirmaz(self):
        import subprocess
        sir_b = self.SIR.encode("utf-8")

        def iptal(komut, **kw):
            return subprocess.CompletedProcess(komut, 1, f"{self._b64('demo')} {self._b64(self.SIR)}".encode(),
                                               b"Get-Credential: " + sir_b)

        def bozuk(komut, **kw):
            return subprocess.CompletedProcess(komut, 0, b"demo " + sir_b, b"")

        def zaman(komut, **kw):
            raise subprocess.TimeoutExpired(komut, 300, output=sir_b)

        def bos(komut, **kw):
            return subprocess.CompletedProcess(komut, 0, f"{self._b64('demo')} ".encode(), b"")

        sonuc = {ad: self._kos(f)[0] for ad, f in (("iptal", iptal), ("bozuk", bozuk), ("zaman", zaman), ("bos", bos))}
        windows_degil, cagri = self._kos(lambda *a, **k: None, ps=(None, "Windows değil — giriş penceresi yok"))
        # Sırrın HER biçimi aranır: düz, ASCII parçası (repr/kaçış ASCII dışını gizler — mutasyon M4 bunu gösterdi),
        # stdout'taki base64'ü.
        yasak = (self.SIR, "gizli!parola", "ğüş", self._b64(self.SIR))
        ok = (all(k is None for k, _ in sonuc.values())
              and all(y not in n for _, n in sonuc.values() for y in yasak)
              and "rc=1" in sonuc["iptal"][1] and "zaman" not in sonuc["iptal"][1]
              and "300 sn" in sonuc["zaman"][1] and windows_degil == (None, "Windows değil — giriş penceresi yok")
              and not cagri)
        H.kaydet("pencere: iptal/bozuk/zaman aşımı/boş → None, neden metninde sır yok", "ok", str(sonuc), ok)
        self.assertTrue(ok, sonuc)


if __name__ == "__main__":
    unittest.main()
