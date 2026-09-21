# -*- coding: utf-8 -*-
"""install.py — sahte (geçici) template klonunda: SAP yazma izni dosyası gerçek klona dokunmaz."""
from __future__ import annotations

import fnmatch
import json
import shutil
import subprocess
import sys
import unittest

from _helpers import AXET_HOME, GeciciTest

# Önceden kurulmuş makinelerin config'indeki template kuralları: 42b37b8'de yayımlanan config/permissions.json
# (bash). Git'ten okunmaz ki test sığ klonda da çalışsın ve RETIRED_RULES'tan türetilmez ki listeden eksik anahtar
# yakalansın. Geçmişle eşliği EmekliKuralTest denetler.
ESKI_BASH_42B37B8 = {
    "git push --force*": "deny", "git push -f*": "deny", "git push *--force*": "deny", "git push * -f*": "deny",
    "git reset --hard*": "deny", "git clean -f*": "deny", "*--no-verify*": "deny", "*install.py*--sap-write*": "deny",
    "*sap-write.local*": "deny", "*behavior_manifest.py*generate*": "deny", "*core.hooksPath*": "deny",
    "*fiori deploy*": "deny", "*fiori undeploy*": "deny", "*npm run deploy*": "deny",
    "*npm --prefix * run deploy*": "deny", "*deploy_ui.py*deploy *": "ask", "rm -rf *": "ask", "rm -r *": "ask",
    "Remove-Item *-Recurse*": "ask", "rd /s *": "ask", "del /s *": "ask",
}


def guncel_kurallar() -> dict:
    return json.loads((AXET_HOME / "config" / "permissions.json").read_text(encoding="utf-8"))["rules"]


# İzin-verici kararlar: uzunlukla bir deny'ı ezebilen her karar. 'ask' ÖLÇÜLDÜ 2026-09-14, 'allow' ÖLÇÜLDÜ
# 2026-09-17 (bkz. IzinDesenUzunlukTest.test_uzun_allow_yakalanir). Motor yeni bir izin-verici karar türü
# getirirse buraya eklenir — aksi hâlde o tür de sessizce denetim dışı kalır.
IZIN_VERICI_KARARLAR = ("ask", "allow")


def ask_deny_uzunluk_ihlalleri(kurallar: dict) -> list[str]:
    """Her araç için her IZIN-VERICI desen (ask/allow) her deny deseninden sabit karakterde VE toplam uzunlukta
    KESİN kısa olmalı.

    ⚠ KAPSAM — bu denetim EŞLEŞMEYE BAKMAZ: iki desenin aynı komut metnine uyup uymadığını hiç ölçmez, yalnız
    uzunlukları karşılaştırır (en kötü durumu varsayar: "uyarlarsa"). Eşleşme kapsamını `OlculmusDenyKapsamiTest`
    fnmatchcase ile simüle eder, canlı motor kapsamını da yalnız o tablo taşır.

    Gerekçe — iki ayrı ölçüm (aXet.code 1.3.0):
    · ask↔deny (2026-09-14, tek seri): aynı komuta bir ask ve bir deny uyunca uzun desen kazanır; run modunda ask
      sormadan onaylar. Ask deny'dan kısa değilse zincirli komutta ('echo x; git reset --hard; ... Remove-Item ...')
      deny'ı ezer ve komut sorulmadan çalışır (yaşanmış vaka: HEAD taşındı, kanarya dosyası silindi).
    · allow↔deny (2026-09-17, tek koşum, motor kanıtı = BgJob log satırı + işaret dosyası): aynı uzunluk kuralı
      allow için de işliyor — uzun allow kısa deny'ı EZDİ (komut çalıştı), uzun deny kısa allow'u ezdi.
      Şablonda bugün allow deseni YOK; kural gelecekte eklenecek olanı korur (bugün no-op, yarın tek savunma).

    İki ölçülmemiş nokta, ikisi de KATI tarafa yuvarlanır:
    · Uzunluğun '*' hariç sabit karakterle mi toplam uzunlukla mı sayıldığı DOĞRULANMADI → ikisi birden istenir.
    · EŞİTLİKTE kazananın kuralı ÖLÇÜLEMEDİ: 2026-09-14 ask/deny serisi "eşitlikte ask kazanır" dedi, ama
      2026-09-17 allow/deny ölçümünde eşit uzunlukta kazanan anahtar sırasıyla (ya da alfabetik sırayla — ikisi
      ayırt EDİLEMEDİ) DEĞİŞTİ; sonuç nondeterministik olabilir. Bu yüzden eşitlik de ihlal sayılır ve
      "izin-verici kazanır" VARSAYILMAZ.
    """
    ihlal = []
    for arac, desenler in kurallar.items():
        if not isinstance(desenler, dict):
            continue
        izin_vericiler = [(p, v) for p, v in desenler.items() if v in IZIN_VERICI_KARARLAR]
        denyler = [p for p, v in desenler.items() if v == "deny"]
        for a, karar in izin_vericiler:
            for d in denyler:
                sa, sd = len(a.replace("*", "")), len(d.replace("*", ""))
                if not (sa < sd and len(a) < len(d)):
                    ihlal.append(f"{arac}: {karar} {a!r} (sabit {sa}, toplam {len(a)}) deny {d!r} (sabit {sd}, "
                                 f"toplam {len(d)}) desenden kısa değil → ikisi aynı zincirli komuta uyarsa "
                                 f"{karar} kazanır ve komut run modunda sorulmadan çalışır")
    return ihlal


class IzinDesenUzunlukTest(unittest.TestCase):
    def test_ask_desenleri_tum_denylardan_kisa(self):
        kurallar = guncel_kurallar()
        self.assertTrue(any(v == "ask" for d in kurallar.values() for v in d.values()), "ask kuralı yok; test boş geçer")
        self.assertTrue(any(v == "deny" for d in kurallar.values() for v in d.values()), "deny kuralı yok; test boş geçer")
        ihlal = ask_deny_uzunluk_ihlalleri(kurallar)
        self.assertEqual(ihlal, [], "\n".join(ihlal))

    # --- negatif ---
    def test_uzun_ask_yakalanir(self):
        kurallar = {"bash": {"*git push -f*": "deny", "*Remove-Item*-Recurse*": "ask", "*rm -rf *": "ask"}}
        ihlal = ask_deny_uzunluk_ihlalleri(kurallar)
        self.assertEqual(len(ihlal), 1, ihlal)
        self.assertIn("'*Remove-Item*-Recurse*'", ihlal[0])
        self.assertIn("'*git push -f*'", ihlal[0])
        # eşitlik de ihlaldir (eşitlikte kazanan ÖNGÖRÜLEMEZ, o yüzden eşitliğe hiç girilmez): 11=11, 13=13
        self.assertEqual(len(ask_deny_uzunluk_ihlalleri({"bash": {"*git push -f*": "deny", "*Remove-Item*": "ask"}})), 1)
        # yalnız bir ölçüt eşit/uzunsa da ihlal: sabit 6<11 ama toplam 13=13 · toplam 12<13 ama sabit 11=11
        self.assertEqual(len(ask_deny_uzunluk_ihlalleri({"bash": {"*git push -f*": "deny", "*R*e*m*o*v*e*": "ask"}})), 1)
        self.assertEqual(len(ask_deny_uzunluk_ihlalleri({"bash": {"*git push -f*": "deny", "Remove-Item*": "ask"}})), 1)
        # kısa ask ihlal değildir
        self.assertEqual(ask_deny_uzunluk_ihlalleri({"bash": {"*git push -f*": "deny", "*Remove-It*": "ask"}}), [])

    def test_uzun_allow_yakalanir(self):
        """`allow` de `ask` gibi izin-vericidir ve uzunlukla deny'ı ezer (ÖLÇÜLDÜ 2026-09-17).

        Ölçüm (nötr belirteçli lab config, tek koşum, motor kanıtı = BgJob log satırı + işaret dosyası):
        `*ZK1-uzun-allow-deseni*`=allow + `*ZK1*`=deny varken komut ÇALIŞTI → uzun allow kısa deny'ı ezdi.
        Ters kontrol: `*ZK6uzun-deny-deseni*`=deny + `*ZK6*`=allow → REDDEDİLDİ (uzunluk kuralı simetrik).
        Kontroller: yalnız-deny → reddedildi, kuralsız → çalıştı.
        Şablonda bugün `allow` deseni YOK; tam da bu yüzden biri eklerse sessizce geçer. DARALT: eşitlikte ne
        olduğu belirsizdir (ZK2/ZK5'te kazanan anahtar sırasıyla — ya da alfabetik sırayla — değişti, ikisi
        ayırt EDİLEMEDİ) → eşitlik de ihlal sayılır, "izin-verici kazanır" varsayılmaz.
        """
        kurallar = {"bash": {"*git push -f*": "deny", "*izin-verici-uzun-desen*": "allow"}}
        ihlal = ask_deny_uzunluk_ihlalleri(kurallar)
        self.assertEqual(len(ihlal), 1, f"uzun allow deseni yakalanmadı (ihlal={ihlal}) → şablona eklenecek bir "
                                        f"allow deseni deny'ı sessizce ezer")
        self.assertIn("'*izin-verici-uzun-desen*'", ihlal[0])
        self.assertIn("'*git push -f*'", ihlal[0])
        # eşitlik de ihlaldir: sabit 11=11, toplam 13=13
        self.assertEqual(len(ask_deny_uzunluk_ihlalleri({"bash": {"*git push -f*": "deny", "*allow-desen*": "allow"}})), 1)
        # kısa allow ihlal değildir (kontrol grubu — kural gereksiz yere katı olmasın)
        self.assertEqual(ask_deny_uzunluk_ihlalleri({"bash": {"*git push -f*": "deny", "*allow-d*": "allow"}}), [])
        # ask + allow birlikte: ikisi de denetlenir
        karisik = {"bash": {"*git push -f*": "deny", "*uzun-allow-desen*": "allow", "*uzun-ask-desen*": "ask"}}
        self.assertEqual(len(ask_deny_uzunluk_ihlalleri(karisik)), 2, ask_deny_uzunluk_ihlalleri(karisik))


def beklenen_klon_bash(klon) -> dict:
    """Kurulumun o klondan yazması BEKLENEN `bash` kuralları — statik dosya + Z12 üretilen deseni.

    ⛔ `guncel_kurallar()` tek başına artık YETMEZ: 2026-09-20'den beri bir kural klonun
    YOLUNDAN üretiliyor (`install.session_brief_allow`, Z12) ve `permissions.json`da durmaz.
    Beklentiyi statik dosyadan kuran test, kurulum DOĞRU çalışırken kırılır.
    ⛔ Ama beklenti `install.load_rules()`a da SORULMAZ: beklentiyi ürünün kendi fonksiyonundan
    almak testi totolojiye çevirir — fazladan ya da yanlış üretilmiş bir kuralı artık göremez
    (ölçüm aracı kendini kanıtlamasın). Bu yüzden desen BURADA yeniden türetilir; metnin
    ürünle eşliğini `OturumOzetiAllowTest.test_1/test_4` ayrıca ölçer.
    """
    return {**guncel_kurallar()["bash"],
            'python "' + (klon / "scripts" / "session_brief.py").as_posix() + '"': "allow"}


JOKERLER = ("*", "?", "[")


def uretilen_izin_ihlalleri(kurallar: dict) -> list[str]:
    """ÜRETİLEN (klon yoluna bağlı, permissions.json'da DURMAYAN) izin-verici desenlerin denetimi.

    ⛔ Neden ayrı bir denetim: `IzinDesenUzunlukTest` `guncel_kurallar()` ile YALNIZ statik
    dosyayı okur ⇒ `install.load_rules()`ın eklediği desenleri GÖRMEZ. Bu boşluk fark edilmeden
    kalsaydı, üretilen her yeni izin kuralı uzunluk denetiminin tamamen dışında yaşardı.

    Kural: üretilen izin-verici desen ya JOKERSİZDİR (o zaman tek bir komut metnine uyar; zincire
    uzatılmış metinle eşleşemez — CANLI ölçüldü, `install.session_brief_allow` docstring'i) ya da
    uzunluk kuralına uymak ZORUNDADIR. Joker girdiği anda muafiyetin dayanağı düşer.
    """
    statik = guncel_kurallar()
    ihlal: list[str] = []
    for alan, desenler in kurallar.items():
        for desen, karar in desenler.items():
            if karar not in ("allow", "ask") or desen in statik.get(alan, {}):
                continue
            if any(j in desen for j in JOKERLER):
                ihlal += [f"üretilen izin deseni JOKER içeriyor ({alan}:{desen!r}) → {m}"
                          for m in ask_deny_uzunluk_ihlalleri({alan: {**desenler, desen: karar}})
                          if repr(desen) in m]
    return ihlal


class OturumOzetiAllowTest(unittest.TestCase):
    """Z12 (karar 2026-09-20): her oturum sorulan açılış özeti komutuna joker-siz allow.

    Muafiyet bilinçli: desen tüm deny'lardan UZUN (uzunluk kuralının ihlali gibi görünür) ama
    JOKERSİZ olduğu için yalnız TEK bir komut metnine uyar ⇒ "uzun allow kısa deny'ı ezer"
    tırmanışı yapısal olarak kapalı. Canlı ölçüm (S0-S4) `install.session_brief_allow`
    docstring'inde. Muafiyetin bedeli `test_2`dir: joker girerse muafiyet düşer.
    """

    def _kurallar(self) -> dict:
        import install
        return install.load_rules()

    def test_1_desen_JOKERSIZ(self):
        import install
        desen = install.session_brief_allow()
        for j in JOKERLER:
            self.assertNotIn(j, desen, f"desen joker içeriyor ({j!r}) → uzunluk muafiyetinin dayanağı düşer")
        self.assertEqual(self._kurallar()["bash"].get(desen), "allow")

    def test_2_joker_giren_uretilen_izin_deseni_YAKALANIR(self):
        """Negatif test: muafiyet sessizce genişlemesin."""
        sahte = {"bash": {"*git push -f*": "deny", "python */session_brief.py*": "allow"}}
        self.assertTrue(uretilen_izin_ihlalleri(sahte), "jokerli üretilen allow yakalanmadı")
        # KONTROL: jokersiz desen, deny'lardan UZUN olsa bile ihlal DEĞİL (muafiyetin kendisi)
        temiz = {"bash": {"*git push -f*": "deny", 'python "C:/a/scripts/session_brief.py"': "allow"}}
        self.assertEqual(uretilen_izin_ihlalleri(temiz), [])

    def test_3_uretilen_kurallarin_TAMAMI_denetimden_geciyor(self):
        self.assertEqual(uretilen_izin_ihlalleri(self._kurallar()), [])

    def test_4_desen_AGENTS_md_komutuyla_AYNI(self):
        """Kablolama: kural, şablonun gerçekten yazdığı komuta uymazsa hiçbir işe yaramaz."""
        import install
        import new_project
        metin = (AXET_HOME / "templates" / "project" / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("session_brief.py", metin, "şablon ön koşulu")
        self.assertIn(install.session_brief_allow(), new_project._doldur(metin, "PROJE"),
                      "izin deseni AGENTS.md'nin yazdığı komutla birebir AYNI değil → kural hiç eşleşmez")

    def test_5_yasam_dongusu_apply_sonra_strip(self):
        import install
        kurallar = self._kurallar()
        desen = install.session_brief_allow()
        cfg: dict = {}
        install.apply_ours(cfg, kurallar, sap=False)
        self.assertEqual(cfg["permissions"]["rules"]["bash"].get(desen), "allow")
        install.strip_ours(cfg, kurallar)
        self.assertNotIn("permissions", cfg, "kaldırma sonrası üretilen desen config'te KALMAMALI")


class EmekliKuralTest(unittest.TestCase):
    """install.RETIRED_RULES ↔ güncel permissions.json ↔ git geçmişi."""

    def test_emekli_desen_guncel_dosyada_yok(self):
        import install
        guncel = guncel_kurallar()
        cakisan = [f"{d}:{p}" for d, ps in install.RETIRED_RULES.items() for p in ps if p in guncel.get(d, {})]
        self.assertEqual(cakisan, [], "RETIRED_RULES'taki desen güncel config/permissions.json'da da var → kurulum onu "
                                      "hem yazar hem emekli sayar; birinden çıkar")

    def _gecmis(self, *args: str) -> str:
        r = subprocess.run(["git", "-C", str(AXET_HOME), *args], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", stdin=subprocess.DEVNULL, timeout=60)
        if r.returncode != 0:
            self.skipTest(f"git geçmişi okunamadı (sığ klon ya da git yok): git {' '.join(args)} → {r.stderr.strip()}")
        return r.stdout

    def test_gecmiste_yayimlanip_cikan_her_desen_emekli_listesinde(self):
        import install
        guncel = guncel_kurallar()
        commitler = self._gecmis("log", "--format=%h", "--", "config/permissions.json").split()
        self.assertTrue(commitler, "permissions.json için commit bulunamadı")
        # Yayımlanan tek commit'lik kopyada (yayin_hazirla.py) ve sığ klonda eski sürümler yoktur: tek commit güncel
        # dosyaya eşittir ve karşılaştırma boş geçerdi. Sessiz "ok" yerine atla; eski sürüm kapsamı orada
        # git'siz InstallTest (ESKI_BASH_42B37B8 fixture'ı) ile korunur.
        if len(commitler) < 2:
            self.skipTest(f"permissions.json geçmişinde {len(commitler)} commit var (yayın kopyası ya da sığ klon); "
                          "eski sürümlerle karşılaştırma yapılamadı")
        eksik = set()
        for h in commitler:
            eski = json.loads(self._gecmis("show", f"{h}:config/permissions.json"))["rules"]
            for d, ps in eski.items():
                for p, karar in ps.items():
                    if p not in guncel.get(d, {}) and install.RETIRED_RULES.get(d, {}).get(p) != karar:
                        eksik.add(f"{d}:{p}={karar} ({h})")
        self.assertEqual(sorted(eksik), [], "geçmişte yayımlanıp dosyadan çıkan desen RETIRED_RULES'ta yok (ya da karar "
                                            "farklı) → önceden kurulmuş makinelerde yetim kalır")

    def test_eski_fixture_gecmisle_ayni(self):
        eski = json.loads(self._gecmis("show", "42b37b8:config/permissions.json"))["rules"]["bash"]
        self.assertEqual(eski, ESKI_BASH_42B37B8)


class InstallTest(GeciciTest):
    def setUp(self) -> None:
        super().setUp()
        self.klon = self.tmp / "klon"
        for rel in ("scripts/install.py", "config/permissions.json", "core/00-temel.md", "core/sap/00-sap.md",
                    "memory/MEMORY.md"):
            hedef = self.klon / rel
            hedef.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(AXET_HOME / rel, hedef)
        (self.klon / "skills").mkdir()
        (self.klon / "skills-sap").mkdir()
        self.cfg = self.xdg / "axet-code" / "axet-code.json"

    def install(self, *args: str):
        return self.calistir(self.klon / "scripts" / "install.py", *args)

    def oku(self) -> dict:
        return json.loads(self.cfg.read_text(encoding="utf-8"))

    def eski_kurulum(self, kullanici: dict | None = None) -> None:
        """42b37b8 permissions.json'la kurulmuş makineyi taklit eder: klon kopyasına eski dosya konur, install koşulur,
        sonra güncel dosya geri konur. Gerçek global config'e dokunulmaz (XDG geçici)."""
        dosya = self.klon / "config" / "permissions.json"
        yeni = dosya.read_text(encoding="utf-8")
        dosya.write_text(json.dumps({"rules": {"bash": ESKI_BASH_42B37B8}}), encoding="utf-8")
        if kullanici is not None:
            self.cfg.parent.mkdir(parents=True, exist_ok=True)
            self.cfg.write_text(json.dumps(kullanici), encoding="utf-8")
        r = self.install()
        self.assertEqual(r.returncode, 0, self.cikti(r))
        dosya.write_text(yeni, encoding="utf-8")
        bash = self.oku()["permissions"]["rules"]["bash"]
        self.assertTrue(all(bash.get(k) == v for k, v in ESKI_BASH_42B37B8.items()), "eski kurulum taklidi kurulmadı")

    @staticmethod
    def emekli_beklenen() -> set:
        """Eski kurulumda olup güncel dosyada olmayan desenler (RETIRED_RULES'tan bağımsız hesap)."""
        return set(ESKI_BASH_42B37B8) - set(guncel_kurallar()["bash"])

    def test_eski_kurulumdan_guncelleme_emekli_desenleri_siler(self):
        self.eski_kurulum({"permissions": {"rules": {"bash": {"*benim-aracim*": "allow"}}}})
        r = self.install()
        self.assertEqual(r.returncode, 0, self.cikti(r))
        emekli = self.emekli_beklenen()
        self.assertTrue(emekli, "eski ve güncel dosya aynı; test bir şey ölçmez")
        kurallar = self.oku()["permissions"]["rules"]
        self.assertEqual(sorted(emekli & set(kurallar["bash"])), [], "emekli desen config'te kaldı")
        self.assertEqual(kurallar["bash"], {**beklenen_klon_bash(self.klon), "*benim-aracim*": "allow"})
        # Uzunluk denetimi BİRLEŞİK config'te iki farklı şeyi ölçer; ikisi karıştırılmamalı:
        # (a) BİZİM kontrolümüzdeki desenler — kurulum bunların arasında bir ezme üretmemeli. Zorunlu.
        bizim = set(guncel_kurallar()["bash"])
        sadece_bizim = {"bash": {p: k for p, k in kurallar["bash"].items() if p in bizim}}
        ihlal = ask_deny_uzunluk_ihlalleri(sadece_bizim)
        self.assertEqual(ihlal, [], "\n".join(ihlal))
        # (b) KULLANICININ kendi kuralı — template bunu düzeltemez, yalnız belgeleyebilir. Buradaki kullanıcı
        # kuralı ('*benim-aracim*'=allow, sabit 12) birkaç template deny'ından uzun; ÖLÇÜLDÜ (2026-09-17) ki
        # uzun bir allow kısa bir deny'ı gerçekten ezer ⇒ bu birleşimde koruma fiilen delinir. Bunu "ihlal yok"
        # diye örtmek yerine KİLİTLİYORUZ: risk gerçek ve README "Bilinen sınırlar"da yazılı. Denetim
        # izin-verici kararları görmeyi bırakırsa (regresyon) bu assert FAIL verir.
        kullanici_ihlali = [i for i in ask_deny_uzunluk_ihlalleri(kurallar) if "'*benim-aracim*'" in i]
        self.assertTrue(kullanici_ihlali, "kullanıcının uzun 'allow' kuralı template deny'larıyla çakışıyor ama "
                                          "denetim bunu görmedi → izin-verici karar kapsamı kayboldu "
                                          "(IZIN_VERICI_KARARLAR)")
        self.assertIn(f"Eski template kuralları kaldırıldı ({len(emekli)})", r.stdout)

    def test_eski_kurulumdan_kaldirma_emekli_desen_birakmaz(self):
        self.eski_kurulum({"model": "m1", "permissions": {"rules": {"bash": {"*benim-aracim*": "allow"}}}})
        r = self.install("--uninstall")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        cfg = self.oku()
        self.assertEqual(cfg["model"], "m1")
        self.assertEqual(cfg["permissions"], {"rules": {"bash": {"*benim-aracim*": "allow"}}})

    def test_kullanicinin_degistirdigi_emekli_desen_korunur(self):
        self.eski_kurulum()
        cfg = self.oku()
        cfg["permissions"]["rules"]["bash"]["rm -rf *"] = "deny"
        self.cfg.write_text(json.dumps(cfg), encoding="utf-8")
        r = self.install()
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertEqual(self.oku()["permissions"]["rules"]["bash"].get("rm -rf *"), "deny")
        self.assertIn("UYARI", r.stdout)
        self.assertIn("bash:rm -rf *", r.stdout)
        r = self.install("--uninstall")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertEqual(self.oku()["permissions"], {"rules": {"bash": {"rm -rf *": "deny"}}})

    # --- negatif ---
    def test_emekli_listeden_eksik_desen_yakalanir(self):
        yol = self.klon / "scripts" / "install.py"
        metin = yol.read_text(encoding="utf-8")
        satir = '        "*deploy_ui.py*deploy *": "ask",\n'
        self.assertEqual(metin.count(satir), 1, "negatif test hedef satırı bulamadı")
        yol.write_text(metin.replace(satir, ""), encoding="utf-8")
        self.eski_kurulum()
        self.assertEqual(self.install().returncode, 0)
        kurallar = self.oku()["permissions"]["rules"]
        self.assertEqual(kurallar["bash"].get("*deploy_ui.py*deploy *"), "ask", "eksik liste emekli deseni yine sildi")
        self.assertTrue(any("'*deploy_ui.py*deploy *'" in i for i in ask_deny_uzunluk_ihlalleri(kurallar)))

    def test_bos_configde_kurulum(self):
        r = self.install()
        self.assertEqual(r.returncode, 0, self.cikti(r))
        cfg = self.oku()
        self.assertIn((self.klon / "core" / "00-temel.md").as_posix(), cfg["options"]["context_paths"])
        self.assertIn((self.klon / "skills").as_posix(), cfg["options"]["skills_paths"])
        self.assertEqual(cfg["permissions"]["rules"]["bash"]["*--no-verify*"], "deny")
        # A3 (2026-09-18): CLONE_PROTECTED kaldirildi -> kurulum artik HIC `edit` kurali yazmiyor.
        self.assertNotIn("edit", cfg["permissions"]["rules"], "klon edit deny'lari geri geldi")
        self.assertNotIn((self.klon / "core" / "sap").as_posix(), cfg["options"]["context_paths"])

    def test_kullanici_ayari_korunur_ve_kaldirma(self):
        self.cfg.parent.mkdir(parents=True)
        self.cfg.write_text(json.dumps({"model": "m1", "options": {"context_paths": ["D:/benim.md"]}}), encoding="utf-8")
        self.assertEqual(self.install().returncode, 0)
        cfg = self.oku()
        self.assertEqual(cfg["model"], "m1")
        self.assertIn("D:/benim.md", cfg["options"]["context_paths"])
        self.assertTrue(list(self.cfg.parent.glob("axet-code.json.bak-*")), "yedek alınmadı")
        self.assertEqual(self.install("--uninstall").returncode, 0)
        cfg = self.oku()
        self.assertEqual(cfg["options"]["context_paths"], ["D:/benim.md"])
        self.assertNotIn("permissions", cfg)

    def test_sap_ac_kapa(self):
        self.assertEqual(self.install("--sap").returncode, 0)
        self.assertIn((self.klon / "core" / "sap").as_posix(), self.oku()["options"]["context_paths"])
        self.assertEqual(self.install().returncode, 0)  # durum korunur
        self.assertIn((self.klon / "core" / "sap").as_posix(), self.oku()["options"]["context_paths"])
        self.assertEqual(self.install("--no-sap").returncode, 0)
        self.assertNotIn((self.klon / "core" / "sap").as_posix(), self.oku()["options"]["context_paths"])

    # --- negatif ---
    def test_bozuk_json_dokunulmaz(self):
        self.cfg.parent.mkdir(parents=True)
        self.cfg.write_text("{bozuk", encoding="utf-8")
        r = self.install()
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertEqual(self.cfg.read_text(encoding="utf-8"), "{bozuk")

    def test_sap_write_sap_kapaliyken_reddedilir(self):
        r = self.install("--sap-write")
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertFalse((self.klon / "config" / "sap-write.local").exists())
        self.assertFalse(self.cfg.exists())

    def test_dry_run_yazmaz(self):
        r = self.install("--dry-run")
        self.assertEqual(r.returncode, 0)
        self.assertIn("dry-run", r.stdout)
        self.assertFalse(self.cfg.exists())

    def test_eksik_template_dosyasi(self):
        (self.klon / "core" / "00-temel.md").unlink()
        r = self.install()
        self.assertEqual(r.returncode, 2)
        self.assertFalse(self.cfg.exists())


# ---------------------------------------------------------------------------
# K11 — canlı ölçülmüş deny kapsamı (2026-09-17)
# ---------------------------------------------------------------------------
# Eşleştirmeyi BU REPO YAPMAZ: desen→karar eşleşmesi aXet.code (axet-code.exe) içindedir; bu repo yalnız
# config/permissions.json'u install.py ile kullanıcının global config'ine (permissions.rules) birleştirir.
# Aşağıdaki tablo bu yüzden bir SİMÜLASYONDUR: motor tarafındaki gerçek karar 2026-09-17'de canlı
# `axet-code run` ile (aXet.code 1.3.0, lab projesi, kurallar XDG_CONFIG_HOME ile proje dışında) ayrıca
# ölçüldü; kanıt motor tarafından alındı (.axet-code/logs/axet-code.log "BgJob started" satırı + işaret
# dosyası varlığı). Model beyanı kanıt SAYILMADI — ilk koşumda model hiç araç çağırmadan "RED" uydurmuştu.
# Testin işi: ölçümle korunduğu KANITLANMIŞ bir desen sessizce dosyadan düşerse ya da bir desen ölçülmüş
# kontrol grubunu kapsayacak kadar genişlerse FAIL vermek.
#
# Ölçülen semantik: desen komut metninin TAMAMINA glob olarak uyar (yalnız '*'), eşleşme büyük/küçük harfe
# DUYARLIDIR. fnmatchcase bu semantiği taklit eder. Önceliği (uzun desen kazanır; EŞİTLİKTE KAZANAN
# ÖNGÖRÜLEMEZ — bkz. ask_deny_uzunluk_ihlalleri docstring'i, "eşitlikte ask kazanır" iddiası 2026-09-17
# allow↔deny ölçümüyle çürütüldü) ayrıca IzinDesenUzunlukTest kilitler: her izin-verici desen her deny'dan
# KESİN kısa olduğu için eşleşen bir deny daima kazanır — eşitlik hiç oluşmaz, belirsizliğe girilmez.

CANLI_OLCULEN_ESLESME = [
    # (komut metni, eşleşen desen, dosyadaki karar)
    # deny satırları: 2026-09-17 canlı koşumda REDDEDİLDİ (motor kanıtı: BgJob satırı yok + işaret dosyası yok).
    # ask satırları: dosyada 'ask'tır; run modunda ask SORMADAN onaylanır ve logda iz bırakmaz, bu yüzden
    #   EŞLEŞMELERİ lab config'inde geçici olarak deny yapılarak ölçüldü. DARALT: ölçülen şey "bu desen bu
    #   komut metnine uyuyor"dur — "ask kararı ne yapar" DEĞİL (o ayrı ve zaten ölçülü).
    ('echo "git clean -xdf ." > a01.txt', "*git clean -xdf*", "deny"),
    ('echo "git clean -df ." > a03.txt', "*git clean -df*", "deny"),
    ('echo "git clean -fdx ." > a04.txt', "*git clean -fdx*", "deny"),
    ('echo "git clean -d -f ." > a06.txt', "*git clean -d -f*", "deny"),
    ('echo "git clean --force ." > a07.txt', "*git clean *--force*", "deny"),
    ('echo "git -C /tmp/x push --force" > a09.txt', "*git *push*--force*", "deny"),
    ('echo "rm -fr /tmp/x" > b02.txt', "*rm -fr*", "ask"),
    ('echo "rm -R /tmp/x" > b03.txt', "*rm -R*", "ask"),
    ('echo "del /q /s x" > b05.txt', "*del /q /s*", "ask"),
    ('echo "rmdir /s x" > b06.txt', "*rmdir /s*", "ask"),
    ('echo "rd /s x" > b08.txt', "*rd /s *", "ask"),
]

# 2026-09-17 canlı koşumda bu biçimler ÇALIŞTI (hiçbir kurala uymuyordu) → lider onayıyla dar desen eklendi
# (S1: eşdeğer-yıkıcı biçimler · S2: 4 aday). Eklendikten SONRA motor tarafında yeniden ölçüldü
# (2026-09-17, tek toplu koşum): 8'i de REDDEDİLDİ, kontrol grubunun 8'i de ÇALIŞTI.
K11_EKLENEN_DENY = [
    ('echo "git -C /tmp/x push -f" > c02.txt', "*git -C * push -f*", "deny"),
    ('echo "git push origin +main" > c03.txt', "*git push origin +*", "deny"),
    ('echo "git reset HEAD~1 --hard" > c04.txt', "*git reset *--hard*", "deny"),
    ('echo "rm --recursive --force /tmp/x" > c05.txt', "*rm --recursive*", "deny"),
    ('echo "git stash drop" > c08.txt', "*git stash drop*", "deny"),
    ('echo "gh repo delete org/repo" > c09.txt', "*gh repo delete*", "deny"),
    ('echo "git branch -D feature" > d08.txt', "*git branch -D*", "deny"),
    # DAR desen bilinçli: yalnız TÜM ağacı geri alan nokta-biçimini yakalar. Bilinen yanlış pozitif
    # (gizlenmiyor): 'git checkout -- .gitignore' ve 'git checkout -- ./src/x' de bu desene uyar.
    ('echo "git checkout -- ." > d09.txt', "*git checkout -- .*", "deny"),
]

# Kontrol grubu: HİÇBİR kurala uymamalı (yanlış pozitif ölçümü). İlk 5'i 2026-09-17 canlı koşumda ÇALIŞTI.
KONTROL_GRUBU_IZINLI = [
    'echo "git clean --dry-run" > a02.txt',      # canlı: çalıştı
    'echo "git push origin main" > a10.txt',     # canlı: çalıştı
    'echo "git status --short" > a08.txt',       # canlı: çalıştı
    'echo "rm -i /tmp/x" > b04.txt',             # canlı: çalıştı
    'echo "rmdir empty" > b07.txt',              # canlı: çalıştı
    'git -C /tmp/x push',                        # canlı: çalıştı — düz push bloklanmamalı
    'git reset --soft HEAD~1',                   # canlı: çalıştı — --soft bloklanmamalı
    'rm --interactive /tmp/x',                   # canlı: çalıştı
    'git stash list',                            # canlı: çalıştı
    'gh repo view org/repo',                     # canlı: çalıştı
    'git branch -d feature',                     # canlı: çalıştı — güvenli dal silme bloklanmamalı
    'git checkout -- src/foo.py',                # canlı: çalıştı — TEK DOSYA geri alma bloklanmamalı
    # `git -C` desenleri eklendikten sonraki yanlış-pozitif kontrolü (simülasyon, 2026-09-17):
    'git -C /t/r status --short',
    'git -C /t/r log --oneline',
    'git -C /t/r push',
    'git -C /t/r push origin main',
    'git -C /t/r branch -d feature',             # güvenli dal silme `-D` deseniyle karışmamalı
    'git -C /t/r checkout -- src/foo.py',        # tek dosya geri alma `checkout -- .` ile karışmamalı
    'git -C /t/r checkout main',
    'git -C /t/r stash list',
    'git -C /t/r stash pop',                     # `stash drop` ile karışmamalı
    'git -C /t/r reset --soft HEAD~1',
    'git -C /t/r clean -n',                      # kuru koşum `clean -*f*` ile karışmamalı
    'git -C /t/r clean --dry-run',
]

# BİLİNEN SINIR (ölçüldü 2026-09-17): eşleşme büyük/küçük harfe duyarlı → büyük harfli biçim deny'ı ATLAR.
# Kombinatoryal olduğu için desenle kapatılmadı (bkz. README "Bilinen sınırlar"). Bu satırlar sınırı KİLİTLER:
# motor bir gün harf-duyarsız olursa ya da biri kombinatoryal varyant eklerse test FAIL verip kararı geri getirir.
BILINEN_SINIR_HARF_DUYARLI = [
    'echo "RD /S x" > b09.txt',                  # canlı: ÇALIŞTI (kontrol: 'rd /s x' reddedildi)
    'echo "RM -RF /tmp/x" > c10.txt',            # canlı: ÇALIŞTI
]

# Kullanıcı kararı 2026-09-17: 'git branch -D' ve 'git checkout -- .' EKLENDİ. Gerekçe (kayda geçsin):
# commit'siz iş için reflog YOKTUR ⇒ 'git checkout -- .' bu setin EN GERİ ALINAMAZ olanıdır;
# 'git branch -D' ve 'git stash drop' reflog/fsck ile kurtarılabilir. Seçim 'daha tehlikeli olan'
# ölçütüne göre yapıldı, yanlış-pozitif konforuna göre DEĞİL.


# `git -C <yol> …` KAÇIŞI (2026-09-17, kullanıcı kararı). `git` ile alt-komut arasına giren global seçenek
# `*git <altkomut>…*` kalıbını ATLATIYORDU: ölçüldü, bu altı biçimin hiçbiri kurala uymuyordu (kontrol: `-C`siz
# `git branch -D f` → deny). Altı DAR desen eklendi. ⚠ Bu tablo SİMÜLASYONLA ölçüldü (fnmatchcase), canlı
# `axet-code run` ile DOĞRULANMADI — kardeşi `*git -C * push -f*` canlı ölçülmüştü, biçim birebir aynı.
GIT_C_SIMULASYONLA_OLCULEN = [
    ('git -C /t/r branch -D feature',   '*git -C * branch -D*',     'deny'),
    ('git -C /t/r checkout -- .',       '*git -C * checkout -- .*', 'deny'),
    ('git -C /t/r stash drop',          '*git -C * stash drop*',    'deny'),
    ('git -C /t/r push origin +main',   '*git -C * push origin +*', 'deny'),
    ('git -C /t/r reset --hard HEAD~1', '*git -C * reset *--hard*', 'deny'),
    ('git -C /t/r reset HEAD~1 --hard', '*git -C * reset *--hard*', 'deny'),  # bayrak sonda da olabilir
    ('git -C /t/r clean -f',            '*git -C * clean -*f*',     'deny'),
    ('git -C /t/r clean -df',           '*git -C * clean -*f*',     'deny'),
    ('git -C /t/r clean -xdf',          '*git -C * clean -*f*',     'deny'),
    ('git -C /t/r clean -fdx',          '*git -C * clean -*f*',     'deny'),
    ('git -C /t/r clean -d -f',         '*git -C * clean -*f*',     'deny'),
    ('git -C /t/r clean --force',       '*git -C * clean -*f*',     'deny'),
]

# HÂLÂ AÇIK (ölçüldü 2026-09-17) — bilinçli olarak kapatılMADI, çünkü her yeni desen uzunluk-ezme yüzeyini
# büyütür ve `-c ayar=değer` kombinatoryaldır. Bu satırlar açıklığı KİLİTLER: biri desen eklerse ya da motor
# semantiği değişirse test FAIL verir ve README/_aciklama'daki "bilinen sınır" metni güncellenmek zorunda kalır.
HALA_ACIK_KACIS_BICIMLERI = [
    'git -c core.pager=cat branch -D feature',   # `-c ayar=değer` biçimi: hiçbir desen tutmuyor
    'git -c user.name=x checkout -- .',
    'git checkout .',                            # `--` ayıraçsız nokta biçimi (aynı yıkıcılıkta)
    'git checkout -f .',
    'git restore .',                             # `checkout -- .`nın modern eşdeğeri
    'git restore --staged .',
]
# ⚠ `git --git-dir=<yol> …` bu listede YOK ve olmamalı: yol `.git` ile bitiyorsa metinde `.git branch -D`
# geçtiği için `*git branch -D*` KAZARA eşleşir (ölçüldü). Bu koruma değil, tesadüftür —
# `git --git-dir=/x/depo branch -D f` (yol `.git` ile bitmiyor) yine açıktır.


# PLAYWRIGHT TARAYICI İNDİRMESİ (2026-09-21, canlı `axet-code run`, aXet.code 1.3.0, lab config XDG_CONFIG_HOME ile).
# Kanıt motor tarafından: `.axet-code/axet-code.db` araç sonucu "denied by agent permission ruleset (rule
# bash:"<desen>"=deny)" + BgJob satırı yok + işaret dosyası yok. Pozitif kontrol aynı koşumda reddedildi.
PLAYWRIGHT_INDIRME_CANLI = [
    ('echo "npx playwright-cli install-browser chromium" > t1.txt', "*install-browser*", "deny"),
    ('echo "npx playwright install chromium" > t2.txt', "*playwright install*", "deny"),
    ('echo "npx playwright-core install chrome" > t3.txt', "*playwright-core install*", "deny"),
    ('echo "npx playwright@1.64.0 install" > t4.txt', "*playwright@* install*", "deny"),
    ('echo "playwright-cli install-browser" > t5.txt', "*install-browser*", "deny"),
    # GERÇEK komut (echo değil): reddedildi, %LOCALAPPDATA%\ms-playwright öncesi/sonrası aynı kaldı.
    ("npx playwright-cli install-browser chromium", "*install-browser*", "deny"),
]
# Kontrol grubu — hiçbir kurala uymamalı. İlk dördü aynı canlı koşumlarda ÇALIŞTI (BgJob + işaret dosyası).
PLAYWRIGHT_KONTROL_GRUBU = [
    "npx playwright-cli --version > k1.txt",                              # canlı: çalıştı (gerçek komut, 0.1.21)
    'echo "npm install --save-dev @playwright/cli@0.1.21" > k2.txt',       # canlı: çalıştı
    'echo "npx playwright-cli install" > k3.txt',                          # canlı: çalıştı — skill kurulumu, indirme yok
    'echo "npx playwright-cli screenshot --filename=kurulum.png" > k4.txt',  # canlı: çalıştı
    "npx playwright-cli open http://localhost:8080/ --browser chrome",
    "npx playwright-cli -s=kd goto http://localhost:8080/index.html",
    "node capture_kd_screens.js kd.json",
]


def _eslesen_desenler(kurallar: dict, komut: str) -> list[tuple[str, str]]:
    """Komut metnine uyan (desen, karar) çiftleri. Ölçülen semantik: tam metne glob, harfe DUYARLI."""
    return [(p, karar) for p, karar in kurallar.get("bash", {}).items() if fnmatch.fnmatchcase(komut, p)]


class OlculmusDenyKapsamiTest(unittest.TestCase):
    """Canlı ölçülmüş deny kapsamı dosyadan sessizce düşmesin; kontrol grubu da genişlemeyle kapılmasın."""

    def setUp(self):
        self.kurallar = guncel_kurallar()

    def test_olculmus_desenler_duruyor_ve_esliyor(self):
        eksik = []
        for komut, beklenen, karar in (CANLI_OLCULEN_ESLESME + K11_EKLENEN_DENY + GIT_C_SIMULASYONLA_OLCULEN
                                       + PLAYWRIGHT_INDIRME_CANLI):
            gercek = self.kurallar.get("bash", {}).get(beklenen)
            if gercek != karar:
                eksik.append(f"{beklenen!r} config/permissions.json'da {karar!r} değil ({gercek!r}) — canlı ölçümde "
                             f"{komut!r} bu desenle eşleşmişti; koruma sessizce düştü ya da karar değişti")
                continue
            eslesen = _eslesen_desenler(self.kurallar, komut)
            if beklenen not in [p for p, _ in eslesen]:
                eksik.append(f"{beklenen!r} artık {komut!r} metnine uymuyor (eşleşenler: {eslesen})")
        self.assertEqual(eksik, [], "\n".join(eksik))

    def test_kontrol_grubu_hicbir_kurala_uymuyor(self):
        """Yanlış pozitif ölçümü: bu komutlar deny DE ask DA almamalı (ask = TUI'de gereksiz soru)."""
        ihlal = [f"{k!r} → {_eslesen_desenler(self.kurallar, k)}"
                 for k in KONTROL_GRUBU_IZINLI + PLAYWRIGHT_KONTROL_GRUBU if _eslesen_desenler(self.kurallar, k)]
        self.assertEqual(ihlal, [], "\n".join(ihlal))

    def test_git_c_disi_kacis_bicimleri_hala_acik(self):
        """`-c ayar=değer` ve ayıraçsız `checkout .`/`restore .` bugün KURALSIZ (ölçüldü) — bilinçli karar.

        Kapanırsa bu test FAIL verir: o an README "Bilinen sınırlar" ve `_aciklama` KAPSAM BEYANI metinleri
        de güncellenmek zorundadır, yoksa belge kapsamdan sessizce sapar (K11 gate'inin yakaladığı sınıf).
        """
        kapananlar = [f"{k!r} → {_eslesen_desenler(self.kurallar, k)}"
                      for k in HALA_ACIK_KACIS_BICIMLERI if _eslesen_desenler(self.kurallar, k)]
        self.assertEqual(kapananlar, [], "Bu biçimler artık kural alıyor; belgeler güncellenmeli:"
                                         + "\n" + ("\n").join(kapananlar))

    def test_bilinen_sinir_harf_duyarliligi_hala_acik(self):
        """Büyük harfli biçim bugün kuralsız (ölçüldü). Kapanırsa bu test FAIL verir → README/_aciklama güncellenir."""
        kapananlar = [f"{k!r} → {_eslesen_desenler(self.kurallar, k)}"
                      for k in BILINEN_SINIR_HARF_DUYARLI if _eslesen_desenler(self.kurallar, k)]
        self.assertEqual(kapananlar, [], "Bilinen sınır kapanmış görünüyor; belgeyi (README 'Bilinen sınırlar' + "
                                         "permissions.json _aciklama) ve bu testi güncelle:\n" + "\n".join(kapananlar))


class KlonKorumasiKaldirildiTest(GeciciTest):
    """A3 — `CLONE_PROTECTED` kaldırıldı (TASARIM §"7 karar" / §13 P4).

    Bu bir KORUMA KALDIRMA'dır: ölçülen, kaldırmanın (a) yeni kurulumda hiç `edit` kuralı üretmediği,
    (b) ESKİ kurulumdaki klon `edit` deny'larını yeniden kurulumda TEMİZLEDİĞİ (aksi hâlde kullanıcıda
    ölü kural kalır ve `%guncelle` klona yazamaz), (c) `bash` deny katmanına DOKUNMADIĞI.
    """

    def setUp(self) -> None:
        super().setUp()
        self.klon = self.tmp / "klon"
        for rel in ("scripts/install.py", "config/permissions.json", "core/00-temel.md", "memory/MEMORY.md"):
            hedef = self.klon / rel
            hedef.parent.mkdir(parents=True, exist_ok=True)
            hedef.write_bytes((AXET_HOME / rel).read_bytes())
        (self.klon / "skills").mkdir()
        (self.klon / "skills-sap").mkdir()
        self.cfg = self.xdg / "axet-code" / "axet-code.json"

    def install(self, *args: str):
        return self.calistir(self.klon / "scripts" / "install.py", *args)

    def oku(self) -> dict:
        return json.loads(self.cfg.read_text(encoding="utf-8"))

    def eski_edit_kurallari(self) -> dict:
        """Kaldırmadan ÖNCEKİ sürümün yazdığı desenler — üretici `clone_rules()`'un o günkü gövdesinin
        (04c3bd9^ · scripts/install.py:102-108) AYNISI, yalnız kökü klon fixture'ına bağlanmış.

        ⚠ Bu döngü `{yol, yol.lower()}` kümesinin HER İKİ üyesine sürücü-harfi swapcase'i uygular →
        **4** varyant (× 6 klasör = 24 desen). Elle yazılmış eski 3'lü küme `C:` + tamamen küçük harfli
        yol varyantını kaçırıyordu; göç yolunun gerçek yüzeyinin 1/4'ü ölçülmüyordu
        (bug-gate 2026-09-18: ürün 24, fixture 18)."""
        home = self.klon.as_posix()
        varyantlar = set()
        for base in {home, home.lower()}:
            varyantlar.add(base)
            if len(base) > 1 and base[1] == ":":
                varyantlar.add(base[0].swapcase() + base[1:])
        return {f"{v}/{d}/*": "deny" for v in sorted(varyantlar)
                for d in ("core", "skills", "skills-sap", "scripts", "config", "templates")}

    def test_sabit_ve_uretici_kaldirildi(self):
        import install as yerel_install
        self.assertFalse(hasattr(yerel_install, "CLONE_PROTECTED"), "CLONE_PROTECTED hâlâ tanımlı")
        self.assertFalse(hasattr(yerel_install, "clone_rules"), "clone_rules() hâlâ tanımlı")
        self.assertNotIn("edit", yerel_install.load_rules(), "load_rules hâlâ edit kuralı üretiyor")

    def test_yeni_kurulumda_edit_alani_hic_olusmaz(self):
        """İddia SADECE `edit`in yokluğu. 'alan listesi tam olarak ["bash"]' demiyoruz: başka bir lane
        yeni bir izin ALANI eklerse bu test davranış doğruyken kırılırdı (K11×K12 sınıfı kırılganlık)."""
        self.assertEqual(self.install().returncode, 0)
        kurallar = self.oku()["permissions"]["rules"]
        self.assertNotIn("edit", kurallar, kurallar)
        self.assertIn("bash", kurallar, kurallar)

    def test_kontrol_grubu_bash_deny_katmani_duruyor(self):
        """Kaldırma YALNIZ `edit` alanını etkiledi: `bash` deny'ları (asıl koruma katmanı) aynen duruyor."""
        self.assertEqual(self.install().returncode, 0)
        bash = self.oku()["permissions"]["rules"]["bash"]
        # Beklenti klonun KENDİ `load_rules()`undan gelir; statik dosya üretilen deseni taşımaz (Z12).
        beklenen = beklenen_klon_bash(self.klon)
        self.assertEqual(bash, beklenen)
        self.assertTrue([p for p, k in bash.items() if k == "deny"], "hiç deny kalmadı")

    def test_eski_kurulumun_edit_denyleri_yeniden_kurulumda_temizlenir(self):
        """Göç: kaldırma ölü kural bırakmamalı (klonun içine yazmayı fiilen engellemeye devam ederdi)."""
        eski = self.eski_edit_kurallari()
        self.assertTrue(eski)
        self.cfg.parent.mkdir(parents=True, exist_ok=True)
        self.cfg.write_text(json.dumps({"permissions": {"rules": {"edit": {**eski, "D:/benim/*": "deny"}}}}),
                            encoding="utf-8")
        self.assertEqual(self.install().returncode, 0)
        kurallar = self.oku()["permissions"]["rules"]
        self.assertEqual(kurallar.get("edit"), {"D:/benim/*": "deny"},
                         "klon edit deny'ları silinmedi ya da kullanıcının kendi kuralı da silindi")

    def test_eski_kurulumun_edit_denyleri_uninstall_da_da_temizlenir(self):
        """install.py:106-108 yorumu göçün `--uninstall`'da DA işlediğini söylüyor; hiçbir test bu yolu
        koşmuyordu (bug-gate 2026-09-18). `--uninstall` `apply_ours`'u atlar, yalnız `strip_ours` koşar →
        ayrı bir yürütme yolu. Ölçülen ikisi birden: (a) klon `edit` deny'ları gider, (b) kullanıcının
        kendi kuralları (edit + bash) KALIR — "hepsini sil" de testi geçerdi, o yüzden (b) şart."""
        eski = self.eski_edit_kurallari()
        self.assertTrue(eski)
        self.cfg.parent.mkdir(parents=True, exist_ok=True)
        self.cfg.write_text(json.dumps({"permissions": {"rules": {
            "edit": {**eski, "D:/benim/*": "deny"},
            "bash": {"Bash(benim-komutum:*)": "allow"}}}}), encoding="utf-8")
        r = self.install("--uninstall")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        kurallar = self.oku()["permissions"]["rules"]
        self.assertEqual(kurallar.get("edit"), {"D:/benim/*": "deny"},
                         "--uninstall klon edit deny'larını silmedi ya da kullanıcının kendi kuralını da sildi")
        self.assertEqual(kurallar.get("bash"), {"Bash(benim-komutum:*)": "allow"},
                         "--uninstall kullanıcının kendi bash kuralına dokundu")


class OrtamDenetimiRcTest(unittest.TestCase):
    """rc taraması 2026-09-18 (Z15): `check_env` araç çağrısının rc'sini okumuyordu ⇒ PATH'te
    bulunan ama çalışmayan git (ölçüldü: bozuk XDG_CONFIG_HOME ile rc=128) `[PASS] git: ?` çıkıyordu.
    Gerçek arıza ortamı yerine `subprocess.run` taklidi kullanılır (deterministik).
    KAPSAM — bakılmayan: zaman aşımı/OSError dalı (değişmedi)."""

    def _kos(self, rc: int, stdout: str, stderr: str = ""):
        import install
        from unittest import mock
        sahte = subprocess.CompletedProcess([], rc, stdout=stdout, stderr=stderr)
        with mock.patch.object(install.shutil, "which", return_value="arac"), \
                mock.patch.object(install.subprocess, "run", return_value=sahte):
            return {ad: (bilgi, ok) for ad, bilgi, ok in install.check_env()}

    def test_rc_sifirdan_farkliysa_gecmez(self):
        sonuc = self._kos(128, "", "fatal: unable to access config")
        bilgi, ok = sonuc["git"]
        self.assertFalse(ok, bilgi)
        self.assertIn("ÇALIŞMIYOR (rc=128)", bilgi)
        self.assertIn("fatal: unable to access config", bilgi)

    def test_bos_cikti_gecmez(self):
        bilgi, ok = self._kos(0, "")["git"]
        self.assertFalse(ok, bilgi)

    def test_kontrol_grubu_calisan_arac_gecer(self):
        bilgi, ok = self._kos(0, "git version 2.55.0\n")["git"]
        self.assertTrue(ok, bilgi)
        self.assertEqual(bilgi, "git version 2.55.0")
