# -*- coding: utf-8 -*-
"""Z111ⓕ — `sap_adt_cli.py --list --grep <desen>`: araç listesini SÜZER (alt süreç, gerçek giriş noktası; çevrimdışı).

Gerekçe (canlı test T11): model `--list` çıktısını süzmek için proje köküne geçici dosya yazdı ve bıraktı. Süzme CLI'da olunca
dosyaya gerek kalmaz. Sözleşme: çıktı ŞEMASI değişmez (`result.tools` öğeleri süzmesiz `--list`'tekiyle BİREBİR aynı,
`result.counts` aynı anahtarlar — süzülen kümeden sayılır); araç kayıt tablosu değişmez. Eşleşme: araç adı + açıklama
(ilk satır) içinde büyük/küçük harf duyarsız ALT DİZE (regex değil).

KAPSAM / BAKILMAYANLAR: argüman adları (`args`) eşleşmeye dahil DEĞİL; Türkçe İ/ı büyük-küçük harf eşlemesi ayrıca ölçülmedi
(araç adları ASCII).
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import _helpers as H

ROOT: Path
HOME: Path


def setUpModule():
    global ROOT, HOME
    ROOT = Path(tempfile.mkdtemp(prefix="axet_list_suz_"))
    HOME = H.build_home(ROOT, optin=False)


def tearDownModule():
    shutil.rmtree(ROOT, ignore_errors=True)


class ListeSuzme(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rc, data, out, err = H.run_cli(HOME, ["--list"])
        assert rc == 0 and data is not None, f"süzmesiz --list koşmadı: {rc}\n{out}\n{err[-800:]}"
        cls.tam = {t["name"]: t for t in data["result"]["tools"]}

    def kos(self, argv):
        return H.run_cli(HOME, argv)

    def _sayim(self, tools):
        return {"read": sum(1 for t in tools if t["class"] == "read"),
                "write": sum(1 for t in tools if t["class"] == "write"), "total": len(tools)}

    def test_F1_desen_suzer_sema_ayni(self):
        rc, data, out, err = self.kos(["--list", "--grep", "msgclass"])
        tools = ((data or {}).get("result") or {}).get("tools") or []
        adlar = [t["name"] for t in tools]
        beklenen = sorted(n for n, t in self.tam.items()
                          if "msgclass" in n.lower() or "msgclass" in (t.get("description") or "").lower())
        ok = (rc == 0 and data is not None and data.get("ok") is True and adlar == beklenen
              and {"adt_msgclass_read", "adt_msgclass_write"} <= set(adlar)
              and len(adlar) < len(self.tam)
              and all(t == self.tam[t["name"]] for t in tools)                  # öğe biçimi BİREBİR
              and set(data["result"]) == {"tools", "counts"}
              and data["result"]["counts"] == self._sayim(tools))
        H.kaydet("Z111f F1 --list --grep msgclass → yalnız eşleşenler · öğe biçimi aynı", "msgclass araçları",
                 f"rc={rc} adlar={adlar} counts={((data or {}).get('result') or {}).get('counts')}", ok)
        self.assertTrue(ok, f"rc={rc} {adlar} / beklenen {beklenen}\n{err[-800:]}")

    def test_F2_buyuk_kucuk_harf_duyarsiz(self):
        _rc, d1, _o, _e = self.kos(["--list", "--grep", "msgclass"])
        rc, d2, _o, _e = self.kos(["--list", "--grep", "MSGCLASS"])
        a1 = [t["name"] for t in d1["result"]["tools"]]
        a2 = [t["name"] for t in (d2 or {}).get("result", {}).get("tools", [])]
        H.kaydet("Z111f F2 --grep MSGCLASS = --grep msgclass", "aynı küme", f"{a2}", rc == 0 and a1 == a2 and a1)
        self.assertTrue(rc == 0 and a1 == a2 and a1, f"{a1} ≠ {a2}")

    def test_F3_eslesme_yok_bos_liste_rc0(self):
        rc, data, out, err = self.kos(["--list", "--grep", "zz_hic_yok_zz"])
        ok = (rc == 0 and data is not None and data["result"]["tools"] == []
              and data["result"]["counts"] == {"read": 0, "write": 0, "total": 0})
        H.kaydet("Z111f F3 eşleşme yok → rc 0 · tools [] · counts 0", "0 · []", f"rc={rc} {out[:120]}", ok)
        self.assertTrue(ok, out)

    def test_F4_kullanim_hatalari(self):
        vakalar = (("--grep --list'siz", ["--grep", "msgclass"]),
                   ("--grep boş", ["--list", "--grep", ""]),
                   ("--grep yalnız boşluk", ["--list", "--grep", "   "]),
                   ("--grep + araç adı", ["adt_get", "--grep", "x"]))
        for ad, argv in vakalar:
            rc, data, out, err = self.kos(argv)
            kod = ((data or {}).get("error") or {}).get("code")
            mesaj = str(((data or {}).get("error") or {}).get("message"))
            ok = rc == 3 and kod == "usage_error" and "--grep" in mesaj and "unrecognized" not in mesaj  # bizim red
            H.kaydet(f"Z111f F4 {ad} → exit 3 usage_error", "3 · usage_error", f"rc={rc} code={kod}", ok)
            self.assertTrue(ok, f"{ad}: rc={rc} {out}")

    def test_F5_kontrol_suzmesiz_liste_degismez(self):
        rc, data, out, err = self.kos(["--list"])
        tools = data["result"]["tools"]
        ok = (rc == 0 and {t["name"]: t for t in tools} == self.tam
              and data["result"]["counts"] == self._sayim(tools) and len(tools) > 20)
        H.kaydet("Z111f F5 KONTROL süzmesiz --list tam liste", "tam", f"rc={rc} total={len(tools)}", ok)
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
