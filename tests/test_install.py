# -*- coding: utf-8 -*-
"""install.py — sahte (geçici) template klonunda: SAP yazma izni dosyası gerçek klona dokunmaz."""
from __future__ import annotations

import fnmatch
import json
import os
import shutil
import subprocess
import sys
import unittest

from _helpers import AXET_HOME, GeciciTest, rg_siz_path

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
      Statik dosyada allow deseni YOK; kural gelecekte eklenecek olanı korur. `install.py`'nin klon yolundan
      ÜRETTİĞİ jokersiz allow'lar (Z12, Z140) bu denetimin dışındadır → `uretilen_izin_ihlalleri` ayrıca bakar.

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
    komut = 'python "' + (klon / "scripts" / "session_brief.py").as_posix() + '"'
    # Z140ⓑ (2026-09-26): `%gun-sonu`/`%onboard` biçimi — AGENTS komutu + TEK ek ` --no-fetch`, jokersiz.
    return {**guncel_kurallar()["bash"], komut: "allow", komut + " --no-fetch": "allow"}


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
        cfg: dict = {}
        install.apply_ours(cfg, kurallar, sap=False)
        for desen in (install.session_brief_allow(), install.session_brief_allow("--no-fetch")):
            self.assertEqual(cfg["permissions"]["rules"]["bash"].get(desen), "allow", desen)
        install.strip_ours(cfg, kurallar)
        self.assertNotIn("permissions", cfg, "kaldırma sonrası üretilen desen config'te KALMAMALI")


class OturumOzetiNoFetchAllowTest(unittest.TestCase):
    """Z140ⓑ (kullanıcı kararı 2026-09-26, AÇIK ONAY, DAR KAPSAM): `session_brief.py --no-fetch` biçimine JOKERSİZ,
    BİREBİR allow. Dayanak: `%gun-sonu` her gün sonu bu komutu koşuyor ve tam-eşleşme kuralı ona uymadığı için
    onay soruyordu (Z105'te ölçüldü). Güvenlik dayanağı Z12 ile aynı: joker yok ⇒ desen yalnız TEK bir komut
    metnine uyar; ek argüman ya da zincir (`&&`, `;`) eşleşmez ve SORULUR (fail-safe).
    ⛔ `--project-dir "<yol>"` biçimine kural YOK (bilinçli): yol değişkendir ⇒ birebir yazılamaz, joker gerekir
    (`--project-dir "*"`) ve joker `"x" && git reset --hard && echo "` zincirine de uyar. `test_4` bunu kilitler.
    Eşleşme simülasyonu `fnmatchcase` (ölçülmüş semantik: tam metne glob, harfe duyarlı) — canlı motor DEĞİL."""

    def setUp(self) -> None:
        import install
        self.install = install
        self.taban = install.session_brief_allow()
        self.desen = install.session_brief_allow("--no-fetch")
        self.kurallar = install.load_rules()
        self.izinliler = {p for p, k in self.kurallar["bash"].items() if k == "allow"}

    def _izin_alan(self, komut: str) -> list[str]:
        return [p for p in self.izinliler if fnmatch.fnmatchcase(komut, p)]

    def test_1_desen_BIREBIR_ve_JOKERSIZ(self):
        self.assertEqual(self.desen, self.taban + " --no-fetch")
        for j in JOKERLER:
            self.assertNotIn(j, self.desen, f"desen joker içeriyor ({j!r}) → uzunluk muafiyetinin dayanağı düşer")
        self.assertEqual(self.kurallar["bash"].get(self.desen), "allow")
        self.assertEqual(uretilen_izin_ihlalleri(self.kurallar), [])

    def test_2_KONTROL_iki_izinli_bicim_allow_alir(self):
        self.assertEqual(self._izin_alan(self.taban), [self.taban], "çıplak açılış komutu allow almalı")
        self.assertEqual(self._izin_alan(self.taban + " --no-fetch"), [self.desen], "--no-fetch biçimi allow almalı")

    def test_3_NEGATIF_komsu_bicimler_izin_ALMAZ(self):
        komsular = [
            self.taban + " --no-fetch --project-dir \"C:/p\"",          # ek argüman
            self.taban + " --no-fetch --json",                            # ek argüman
            self.taban + " --no-fetch ",                                  # sonda boşluk
            self.taban + " --no-fetchX",                                  # bitişik ek metin
            self.taban + "  --no-fetch",                                  # çift boşluk
            self.taban + " --no-fetch && git reset --hard HEAD~1",        # zincir &&
            self.taban + " --no-fetch; rm -rf /tmp/x",                    # zincir ;
            self.taban + " --no-fetch | tee x",                           # boru
            self.taban + " --no-fetch\ngit push -f",                      # satır sonu zinciri
            self.taban + " && git reset --hard",                          # çıplak biçimin zinciri
            "cd x && " + self.taban + " --no-fetch",                      # önden zincir
            self.taban.replace("python", "py") + " --no-fetch",           # farklı yorumlayıcı yazımı
        ]
        for komut in komsular:
            with self.subTest(komut=komut):
                self.assertEqual(self._izin_alan(komut), [], f"komşu biçim izin aldı: {komut!r}")

    def test_4_project_dir_bicimine_kural_YOK(self):
        """Bilinçli kapsam daralması (lider kararı 2026-09-26, AR-1 seçenek a): değişken yol → joker → zincir riski."""
        self.assertEqual([p for p in self.izinliler if "--project-dir" in p], [])
        self.assertEqual(self._izin_alan(self.taban + ' --project-dir "C:/proje"'), [])
        self.assertEqual(self._izin_alan(self.taban + ' --no-fetch --project-dir "C:/proje"'), [])

    def test_5_izin_verilmeyen_ek_REDDEDILIR(self):
        """Üretim fonksiyonu yalnız listelenmiş ekleri kabul eder — yeni ek sessizce kural doğurmasın."""
        for ek in ("--project-dir", "--no-fetch *", "*"):
            with self.subTest(ek=ek):
                with self.assertRaises(ValueError):
                    self.install.session_brief_allow(ek)

    def test_6_gun_sonu_ve_onboard_metni_izinli_bicimi_yaziyor(self):
        """Kablolama: skill metni bu biçimi TARİF etmezse model başka yazım üretir ve kural hiç eşleşmez."""
        for skill in ("gun-sonu", "onboard"):
            with self.subTest(skill=skill):
                metin = (AXET_HOME / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
                self.assertIn('session_brief.py" --no-fetch', metin)


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
        # diye örtmek yerine KİLİTLİYORUZ: risk gerçek ve docs/izin-kurallari.md'de yazılı. Denetim
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
# Kombinatoryal olduğu için desenle kapatılmadı (bkz. docs/izin-kurallari.md). Bu satırlar sınırı KİLİTLER:
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
# semantiği değişirse test FAIL verir ve docs/izin-kurallari.md/_aciklama'daki "bilinen sınır" metni güncellenmek zorunda kalır.
HALA_ACIK_KACIS_BICIMLERI = [
    'git -c core.pager=cat stash drop',          # `-c ayar=değer` biçimi: hiçbir desen tutmuyor
    # (`-c … branch -D` Z75'te `*git *branch* -D*` ile KAPANDI → Z75_ZORLA_DAL_SILME)
    'git -c user.name=x checkout -- .',
    'git checkout .',                            # `--` ayıraçsız nokta biçimi (aynı yıkıcılıkta)
    'git checkout -f .',
    'git restore .',                             # `checkout -- .`nın modern eşdeğeri
    'git restore --staged .',
]
# ⚠ `git --git-dir=<yol> …` bu listede YOK: yol `.git` ile bitiyorsa `*git branch -D*` KAZARA eşleşiyordu
# (tesadüf); Z75'ten beri dal silme ailesi `*git *branch* …*` biçimiyle global seçenekten bağımsız tutulur
# (`git --git-dir=/x/depo branch -D f` → Z75_ZORLA_DAL_SILME). Diğer alt komutlarda `--git-dir=` hâlâ açık.


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

        Kapanırsa bu test FAIL verir: o an docs/izin-kurallari.md ve `_aciklama` KAPSAM BEYANI metinleri
        de güncellenmek zorundadır, yoksa belge kapsamdan sessizce sapar (K11 gate'inin yakaladığı sınıf).
        """
        kapananlar = [f"{k!r} → {_eslesen_desenler(self.kurallar, k)}"
                      for k in HALA_ACIK_KACIS_BICIMLERI if _eslesen_desenler(self.kurallar, k)]
        self.assertEqual(kapananlar, [], "Bu biçimler artık kural alıyor; belgeler güncellenmeli:"
                                         + "\n" + ("\n").join(kapananlar))

    def test_bilinen_sinir_harf_duyarliligi_hala_acik(self):
        """Büyük harfli biçim bugün kuralsız (ölçüldü). Kapanırsa bu test FAIL verir → docs/izin-kurallari.md/_aciklama güncellenir."""
        kapananlar = [f"{k!r} → {_eslesen_desenler(self.kurallar, k)}"
                      for k in BILINEN_SINIR_HARF_DUYARLI if _eslesen_desenler(self.kurallar, k)]
        self.assertEqual(kapananlar, [], "Bilinen sınır kapanmış görünüyor; belgeyi (docs/izin-kurallari.md + "
                                         "permissions.json _aciklama) ve bu testi güncelle:\n" + "\n".join(kapananlar))


# Z75 — ZORLA DAL SİLME EŞDEĞERLERİ (2026-09-23). Önce yalnız `*git branch -D*` vardı; eşdeğer yazımlar hiçbir desene
# uymuyordu. GERÇEK gitte (scratch repo, birleşmemiş dal) ölçüldü: aşağıdaki yazımların HEPSİ birleşmemiş dalı SİLDİ,
# yalnız düz `-d` reddetti. Git seçenekleri dal adından SONRA da kabul eder (`-d x -f` sildi) ve uzun seçeneğin
# tekil önekini kabul eder (`--forc` sildi; `--for` belirsiz: --force/--format). Desenler bu yüzden bayrak sırasından
# bağımsız ve `*git *branch*` önekli: `-C <yol>`, `-c ayar=değer`, `--git-dir=` global seçenekleri de tutulur.
# Joker yalnız `*`, harfe duyarlı, tam metne glob (ölçülmüş semantik, yukarıya bkz.). Her satırın 2. alanı yalnız
# O desenin tuttuğu biçimdir → bir desen silinirse adıyla FAIL verir (mutasyonla doğrulandı).
Z75_ZORLA_DAL_SILME = [
    ('git branch -d -f b1',                     '*git *branch* -d* -f*'),
    ('git branch -d b1 -f',                     '*git *branch* -d* -f*'),       # bayrak dal adından sonra
    ('git -C /t/r branch -d -f b1',             '*git *branch* -d* -f*'),
    ('git branch -d --force b1',                '*git *branch* -d* --forc*'),
    ('git branch -d b1 --force',                '*git *branch* -d* --forc*'),
    ('git branch --delete -f b1',               '*git *branch* --d* -f*'),
    ('git branch --delete --force b1',          '*git *branch* --d* --forc*'),
    ('git branch --delete --forc b1',           '*git *branch* --d* --forc*'),  # tekil önek kısaltması
    ('git -C /t/r branch --delete --force b1',  '*git *branch* --d* --forc*'),
    ('git branch -f -d b1',                     '*git *branch* -f* -d*'),
    ('git branch -f --delete b1',               '*git *branch* -f* --d*'),
    ('git branch --force -d b1',                '*git *branch* --forc* -d*'),
    ('git branch --force --delete b1',          '*git *branch* --forc* --d*'),
    ('git branch -df b1',                       '*git *branch* -df*'),
    ('git -C /t/r branch -df b1',               '*git *branch* -df*'),
    ('git branch -fd b1',                       '*git *branch* -fd*'),
    ('git branch -fD b1',                       '*git *branch* -fD*'),
    ('git branch -Df b1',                       '*git *branch* -D*'),
    ('git -c core.pager=cat branch -D feature', '*git *branch* -D*'),
    ('git --git-dir=/x/depo branch -D f',       '*git *branch* -D*'),
]

# Yanlış pozitif kontrolü: HİÇBİR kurala uymamalı. Meşru dal silme (commit-pr adım 9: yalnız `git branch -d <dal>`,
# adında `-f`/`-d` geçen dallar dahil), okuma biçimleri ve adında/mesajında "branch" geçen başka git komutları.
Z75_KONTROL_GRUBU = [
    'git branch -d feature',
    'git branch -d fix/a-feature',
    'git branch -d z75-fix',
    'git branch --delete feature',
    'git -C /t/r branch -d feature',
    'git branch --list',
    'git branch -a',
    'git branch -v',
    'git branch -vv',
    'git branch -r',
    'git branch --merged',
    'git branch --show-current',
    'git branch --format=%(refname:short)',
    'git branch -m eski yeni',
    'git status --short --branch --untracked-files=all',
    'git log --branches',
    'git switch -c feature-branch-fix',
    'git checkout -b hotfix/branch-delete',
    'git commit -m "branch --force notu"',
    'git push -u origin my-branch',
    'git for-each-ref refs/heads',
    'git merge --no-ff fix-branch-d',
]

# BİLİNÇLİ AÇIK (kullanıcı/lider kararı 2026-09-23): zorla TAŞIMA silme değildir — dalın kendi reflog'u korunur
# (ölçüldü: `git branch -f t1 main` sonrası `t1@{1}` eski commit'i verdi), `-D` ise dalın reflog'unu da siler
# (ölçüldü: `git reflog show t2` → unknown revision; hiç checkout edilmemiş dalın commit'i yalnız fsck dangling).
# `-M` (zorla yeniden adlandırma) da silme ailesi dışında bırakıldı. Kapanırsa test FAIL → belge güncellenir.
Z75_BILINCLI_ACIK = [
    'git branch -f feature main',
    'git branch --force feature main',
    'git branch -M eski yeni',
]


class ZorlaDalSilmeTest(unittest.TestCase):
    """Z75: `git branch -D`in eşdeğer yazımları deny'a düşer; meşru `-d` ve okuma biçimleri düşmez."""

    def setUp(self):
        self.kurallar = guncel_kurallar()

    def test_esdeger_yazimlar_deny(self):
        eksik = []
        for komut, desen in Z75_ZORLA_DAL_SILME:
            if self.kurallar.get("bash", {}).get(desen) != "deny":
                eksik.append(f"{desen!r} config/permissions.json'da deny değil → {komut!r} birleşmemiş dalı siler")
                continue
            eslesen = _eslesen_desenler(self.kurallar, komut)
            if desen not in [p for p, _ in eslesen]:
                eksik.append(f"{desen!r} artık {komut!r} metnine uymuyor (eşleşenler: {eslesen})")
            if any(k != "deny" for _, k in eslesen):
                eksik.append(f"{komut!r} deny DIŞI bir desene de uyuyor: {eslesen}")
        self.assertEqual(eksik, [], "\n".join(eksik))

    def test_mesru_dal_silme_ve_okuma_dusmez(self):
        ihlal = [f"{k!r} → {_eslesen_desenler(self.kurallar, k)}" for k in Z75_KONTROL_GRUBU
                 if _eslesen_desenler(self.kurallar, k)]
        self.assertEqual(ihlal, [], "\n".join(ihlal))

    def test_bilincli_acik_zorla_tasima(self):
        kapanan = [f"{k!r} → {_eslesen_desenler(self.kurallar, k)}" for k in Z75_BILINCLI_ACIK
                   if _eslesen_desenler(self.kurallar, k)]
        self.assertEqual(kapanan, [], "Bilinçli açık biçim kural alıyor; docs/izin-kurallari.md/_aciklama güncellenmeli:\n"
                         + "\n".join(kapanan))


# Z106-EK — PAKET YÖNETİCİSİ İLE KAPISIZ DEPLOY/UNDEPLOY (2026-09-24, kullanıcı onayı). SAP'ye yazan tek meşru yol
# kapılı `deploy_ui.py deploy`dır (`*deploy_ui*` ask). İskelet package.json'da `deploy`/`undeploy`/`deploy-test`
# script'leri durur (skills-sap/sap-ui5-fiori/references/app-skeleton.md §4) ve eski 4 desen (`*fiori deploy*`,
# `*fiori undeploy*`, `*npm run deploy*`, `*npm --prefix * run deploy*`) şu biçimleri KAÇIRIYORDU (ölçüldü,
# fnmatchcase simülasyonu, eklemeden ÖNCE): `npm run undeploy`, `npm --prefix app run undeploy`, `npm run-script
# deploy`, `npm run --silent deploy`, `npm -w app run deploy`, `yarn deploy`, `yarn run undeploy`, `pnpm undeploy`,
# `bun run deploy`, `npm.cmd run deploy` (PowerShell'de npm.ps1 bloklanınca kullanılan biçim) ve
# `ui5 build --config ui5-deploy.yaml` (iskeletteki ui5-deploy.yaml'da `builder.customTasks: deploy-to-abap` var;
# UI5 CLI belgesi: özel görev "designated position"ında koşar, başvurduğu standart görev devre dışı olsa bile ·
# @sap-ux/deploy-tooling README: `deploy` komutu "the same functionality as the abap-deploy UI5 task independent of
# the ui5 build execution" ⇒ görev `ui5 build` İÇİNDE deploy eder — BELGE kanıtı, canlı ÖLÇÜLMEDİ).
# DESEN SEÇİMİ (ölçülerek karşılaştırıldı): ilk taslak `*npm*run* deploy*` / `*yarn* deploy*` / `*bun * deploy*`
# biçimindeydi; paket yöneticisi komutundan SONRA herhangi bir ` deploy` geçen metni tutuyordu ⇒ kapılı yolun
# kendisini (`npm run build && … deploy_ui.py deploy …` ve hatta ZİNCİRSİZ `deploy_ui.py deploy app --user-ok "npm run
# build tamam, deploy et"`) deny'a düşürüyordu. Seçilen setin `deploy` ailesi `run deploy` / `run-script deploy` /
# `yarn deploy` gibi BİTİŞİK metin taşır; `*` yalnız paket yöneticisi ile `run` arasında ya da `run -` bayrak aralığında
# durur. ⚠ `undeploy` ailesi BİTİŞİK DEĞİLDİR (`*npm*undeploy*`, `*yarn*undeploy*`, `*bun *undeploy*` araya `*` alır) →
# `yarn test undeploy` gibi metinler de düşer (aşağıda (d) sınıfı, kilitli). Ölçülen hedeflerin tamamı yine tutuldu.
# ⚠ Bu tablo SİMÜLASYONLA ölçüldü (fnmatchcase, ölçülmüş semantik: tam metne glob, harfe duyarlı). CANLI `axet-code run`
# (2026-09-24, lab config XDG_CONFIG_HOME, kanıt DB 'denied … rule bash:<desen>=deny' + işaret dosyası) ilk koşumda 4 desen
# ölçüldü ve reddetti: `*npm*undeploy*`, `*yarn deploy*`, `*ui5 build*ui5-deploy*`, `*npm*run -* deploy*` (ikinci
# koşumda `*npm*rum deploy*`, `*npm*urn deploy*`, `*npm*run "deploy*` de; `*npm*run 'deploy*` yalnız simülasyon); kontrol
# `npm run build`, `npm run lint && echo deploy`, `npm run build && python deploy_ui.py deploy app` çalıştı.
# Her satırın 2. alanı o biçimi tutan desenlerden biridir ve testte adıyla aranır → desen silinirse adıyla FAIL verir
# (mutasyonla doğrulandı). Yeni desen satırlarında başka desenle çakışmayan biçim seçildi; ⚠ sondaki "eski desenler"
# bloğundan 4 satır (`npm run deploy`, `npm run deploy-test`, `pnpm run deploy`, `npm --prefix app run deploy`) yeni
# `*npm*run deploy*` deseninin de alt kümesidir — eski desen silinirse satır yine adıyla FAIL verir ama komut deny'da kalır.
Z106_PAKET_YONETICISI_DEPLOY = [
    ('npm -w app run deploy',                              '*npm*run deploy*'),
    ('npm --workspace app run deploy',                     '*npm*run deploy*'),
    ('pnpm --filter app run deploy',                       '*npm*run deploy*'),
    ('npm.cmd run deploy',                                 '*npm*run deploy*'),
    ('npm run-script deploy',                              '*npm*run-script deploy*'),
    ('npm run --silent deploy',                            '*npm*run -* deploy*'),
    ('npm run -s deploy',                                  '*npm*run -* deploy*'),
    ('npm run -w app deploy',                              '*npm*run -* deploy*'),
    ('npm run --workspace=app deploy',                     '*npm*run -* deploy*'),
    ('npm run-script --silent deploy',                     '*npm*run-script -* deploy*'),
    # npm run-script takma adları (`npm run-script --help` → "aliases: run, rum, urn"; gate ölçümü: npm 10.9.3'te KOŞTU)
    ('npm rum deploy',                                     '*npm*rum deploy*'),
    ('npm.cmd rum deploy',                                 '*npm*rum deploy*'),
    ('npm urn deploy',                                     '*npm*urn deploy*'),
    ('npm rum undeploy',                                   '*npm*undeploy*'),
    ('npm urn undeploy',                                   '*npm*undeploy*'),
    # tırnaklı script adı (gate ölçümü: npm 10.9.3'te KOŞTU)
    ('npm run "deploy"',                                   '*npm*run "deploy*'),
    ("npm run 'deploy'",                                   "*npm*run 'deploy*"),
    ('npm run "undeploy"',                                 '*npm*undeploy*'),
    ('npm run undeploy',                                   '*npm*undeploy*'),
    ('npm --prefix app run undeploy',                      '*npm*undeploy*'),
    ('npm run-script undeploy',                            '*npm*undeploy*'),
    ('npm run --silent undeploy',                          '*npm*undeploy*'),
    ('cd ui/app && npm run undeploy',                      '*npm*undeploy*'),
    ('pnpm undeploy',                                      '*npm*undeploy*'),
    ('pnpm run undeploy',                                  '*npm*undeploy*'),
    ('yarn deploy',                                        '*yarn deploy*'),
    ('yarn deploy-test',                                   '*yarn deploy*'),
    ('cd app; yarn deploy',                                '*yarn deploy*'),
    ('yarn.cmd deploy',                                    '*yarn.cmd deploy*'),
    ('yarn run deploy',                                    '*yarn*run deploy*'),
    ('yarn --cwd app deploy',                              '*yarn --cwd * deploy*'),
    ('yarn workspace app deploy',                          '*yarn workspace * deploy*'),
    ('yarn undeploy',                                      '*yarn*undeploy*'),
    ('yarn run undeploy',                                  '*yarn*undeploy*'),
    ('bun deploy',                                         '*bun deploy*'),
    ('bun run deploy',                                     '*bun run deploy*'),
    ('bun run --silent deploy',                            '*bun run -* deploy*'),
    ('bun undeploy',                                       '*bun *undeploy*'),
    ('bun run undeploy',                                   '*bun *undeploy*'),
    ('ui5 build --config ui5-deploy.yaml',                 '*ui5 build*ui5-deploy*'),
    ('ui5 build --config=ui5-deploy.yaml',                 '*ui5 build*ui5-deploy*'),
    ('npx ui5 build -c ui5-deploy.yaml',                   '*ui5 build*ui5-deploy*'),
    ('npx ui5 build preload --clean-dest --config ui5-deploy.yaml --include-task=generateCachebusterInfo',
     '*ui5 build*ui5-deploy*'),
    # Eski desenlerin tuttuğu biçimler (regresyon kilidi; ilk 4'ü `*npm*run deploy*` ile de örtüşür):
    ('npm run deploy',                                     '*npm run deploy*'),
    ('npm run deploy-test',                                '*npm run deploy*'),
    ('pnpm run deploy',                                    '*npm run deploy*'),
    ('npm --prefix app run deploy',                        '*npm --prefix * run deploy*'),
    ('npx --no-install fiori undeploy --config ui5-deploy.yaml', '*fiori undeploy*'),
    ('npx fiori deploy --config ui5-deploy.yaml --yes',    '*fiori deploy*'),
]

DEPLOY_UI = 'python C:/x/skills-sap/sap-ui5-fiori/scripts/deploy_ui.py'

# Yanlış pozitif kontrolü: HİÇBİR kurala uymamalı (deny DE ask DA).
Z106_KONTROL_GRUBU = [
    'npm run build', 'npm run start', 'npm start', 'npm install', 'npm ci', 'npm test', 'npm run lint',
    'npm run start-noflp', 'npm run start-mock', 'npm --prefix app run build', 'npm -w app run start',
    'yarn build', 'yarn install', 'yarn run build', 'pnpm install', 'pnpm run build', 'bun run build',
    'ui5 build --config=ui5.yaml --clean-dest --dest dist',
    'cat ui5-deploy.yaml',
    'grep -n "url:" ui5*.yaml',
    'npm install -D @sap-ux/deploy-tooling',             # adında deploy geçen paket kurulumu
    'yarn add -D @sap-ux/deploy-tooling',
    'docker run ubuntu echo deploy',                     # "ubuntu" içindeki "bun" düşmemeli
    'git commit -m "deploy notu"',
    'git commit -m "npm run build sonrasi deploy notu"',
    # zincirde ` deploy` geçen ama deploy ETMEYEN biçimler (lider ölçüm listesi):
    'npm run lint && echo deploy',
    'npm run build -- --dest deploy',
    'npm run start:deploy-preview',
    'npm run test -- deploy.test.js',
    'yarn test deploy',
    # çıkış yolu: desen metnini ararken paket yöneticisi adını dışarıda bırak
    'rg -n "run deploy" .',
    'npm run "build"',
    "npm run 'lint'",
    'npm run build && return 0',
    # undeploy ailesi için SERBEST kalması gerekenler — `*bun*undeploy*`/`*npm*deploy*` gibi genişletmeleri öldürür
    'docker run ubuntu ls /srv/undeploy',                # "ubuntu" içindeki "bun" + undeploy
    'ubuntu-deploy undeploy.sh',
    'git log --grep undeploy',
    'rg -n undeploy package.json',
]

# Kapılı meşru yol: `deploy_ui.py` çağrıları YALNIZ `*deploy_ui*` ask'ına uymalı — yeni deny'lara TAKILMAMALI.
# Zincirli biçimler dahil (bayraksız paket yöneticisi komutu + deploy_ui) ve onay cümlesinde "npm run" geçse bile.
Z106_KAPILI_YOL = [
    f'{DEPLOY_UI} prepare app',
    f'{DEPLOY_UI} prepare app --no-build',
    f'{DEPLOY_UI} verify app',
    f'{DEPLOY_UI} deploy app --user-ok "OK deploy et"',
    f'{DEPLOY_UI} --help',
    f'{DEPLOY_UI} deploy app --user-ok "npm run build tamam, deploy et"',
    f'npm run build && {DEPLOY_UI} deploy app --user-ok "OK"',
    f'cd ui && npm run build && {DEPLOY_UI} deploy app --user-ok "OK"',
    f'npm install && {DEPLOY_UI} deploy app --user-ok "OK"',
    f'yarn install; {DEPLOY_UI} deploy app --user-ok "OK"',
    f'bun run build && {DEPLOY_UI} deploy app --user-ok "OK"',
    f'npm run build; {DEPLOY_UI} prepare app',
]

# BİLİNEN YANLIŞ POZİTİF (bilinçli, kilitli): deny ALIR ama deploy etmez. 2. alan komutun uyduğu desen kümesinin
# TAMAMIDIR — küme değişirse (daraltma ya da örtüşen yeni desen, ör. `*yarn * undeploy*` EKLE mutantı) test FAIL →
# docs/izin-kurallari.md/_aciklama güncellenir. Kaynakları: (a) bayrak aralığı `run -*` / `--cwd *` zincirde sonraki ` deploy`e uzanır;
# (b) desen metni argümanda/mesajda/aramada geçer (dosyanın genel yan etkisi); (c) `ui5 build` ile ui5-deploy aynı
# metinde; (d) `undeploy` ailesi BİTİŞİK DEĞİLDİR (`*npm*undeploy*`, `*yarn*undeploy*`, `*bun *undeploy*` araya `*`
# alır) → paket yöneticisi adından sonra herhangi bir yerde `undeploy` geçen metin düşer; (e) `*npm*urn deploy*`
# "return deploy" gibi metne de uyar; (f) `*npm*rum deploy*` Türkçe metinde sık geçen "-rum ile biten kelime + deploy" (durum/yorum/forum/spectrum)
# metnine de uyar — kapılı yol zincirinde onay cümlesinde geçerse deny (13 sabit karakter) `*deploy_ui*` ask'ını ezer.
Z106_BILINEN_YANLIS_POZITIF = [
    ('npm run deploy-config',                            ['*npm run deploy*', '*npm*run deploy*']),   # (b) eskiden de
    ('npm run "deploy-config"',                          ['*npm*run "deploy*']),                        # (b)
    ('npm run -s build && echo deploy',                  ['*npm*run -* deploy*']),                      # (a)
    (f'npm run -s build && {DEPLOY_UI} deploy app --user-ok "OK"', ['*deploy_ui*', '*npm*run -* deploy*']),  # (a)
    (f'yarn --cwd app build && {DEPLOY_UI} deploy app --user-ok "OK"', ['*deploy_ui*', '*yarn --cwd * deploy*']),
    (f'{DEPLOY_UI} deploy app --user-ok "npm run deploy yerine bunu kullan"',
     ['*deploy_ui*', '*npm run deploy*', '*npm*run deploy*']),                                          # (b)
    ('git commit -m "npm run deploy notu"',              ['*npm run deploy*', '*npm*run deploy*']),     # (b)
    ('rg "yarn deploy" .',                               ['*yarn deploy*']),                            # (b) → rg -n "run deploy"
    ('ui5 build --config ui5-deploy.yaml --exclude-task deploy-to-abap', ['*ui5 build*ui5-deploy*']),  # (c)
    ('ui5 build && cat ui5-deploy.yaml',                 ['*ui5 build*ui5-deploy*']),                   # (c)
    ('yarn test undeploy',                               ['*yarn*undeploy*']),                          # (d)
    ('npm run test -- --grep undeploy',                  ['*npm*undeploy*']),                           # (d)
    ('npm pkg get scripts.undeploy',                     ['*npm*undeploy*']),                           # (d)
    ('rg -n "npm.*undeploy" .',                          ['*npm*undeploy*']),                           # (d)
    ('npm run build && rg undeploy .',                   ['*npm*undeploy*']),                           # (d)
    ('bun test src/undeploy.test.ts',                    ['*bun *undeploy*']),                          # (d)
    ('npm ci && echo return deploy',                     ['*npm*urn deploy*']),                         # (e)
    ('npm run build && echo "durum deploy hazir"',       ['*npm*rum deploy*']),                         # (f)
    ('npm install && echo "spectrum deploy"',            ['*npm*rum deploy*']),                         # (f)
    ('npm run build && echo "yorum deploy"',             ['*npm*rum deploy*']),                         # (f)
    (f'npm run build && {DEPLOY_UI} deploy app --user-ok "forum deploy onayı"', ['*deploy_ui*', '*npm*rum deploy*']),  # (f)
]

# BİLİNEN AÇIK (bilinçli, kilitli): kapanırsa test FAIL → docs/izin-kurallari.md/_aciklama güncellenir.
Z106_BILINEN_ACIK = [
    'pnpm deploy',               # pnpm'in YERLEŞİK `deploy` komutu (paketi dizine kopyalar) script'i koşmaz (DOĞRULANMADI)
    'pnpm -C app deploy',
    'npx deploy',                # @sap-ux/deploy-tooling bin'i; iskelette doğrudan bağımlılık değil (registry:
    'npx undeploy',              #   @sap/ux-ui5-tooling 1.32.0 dependencies={}, bin yalnız `fiori`)
    './node_modules/.bin/deploy -c ui5-deploy.yaml',
    'node node_modules/@sap/ux-ui5-tooling/bin/fiori.cjs deploy',   # CLI dosyasının doğrudan çağrısı
    'npm run ship',              # package.json'a başka adla eklenmiş deploy script'i — desenle kapatılamaz
    'ui5 build --config my-deploy.yaml',                  # başka adlı deploy config'i
    'yarn --silent deploy',      # yarn'da script öncesi bayrak (`--cwd`/`workspace` dışı)
    'bun --cwd app deploy',
    'npm run  deploy',           # çift boşluk
    'NPM RUN DEPLOY',            # harf duyarlılığı (ölçülmüş semantik)
    'npm run Deploy',
    'yarn Deploy',
    'npm rum -s deploy',         # takma adın bayraklı biçimi (`run -*` karşılığı rum/urn için eklenmedi)
    'npm run-script "deploy"',   # tırnaklı biçim yalnız `run` için eklendi
    # kabuk dolaylaması — komut metninde script adı hiç geçmez, desenle kapatılamaz
    'X=deploy; npm run $X',
    'npm run $(echo deploy)',
    'Start-Process npm -ArgumentList "run","deploy"',   # PowerShell argüman listesi
    'npx @ui5/cli build --config ui5-deploy.yaml',      # `ui5 build` metni geçmez
    'bun --cwd app run deploy',  # bun'da `run` öncesi bayrak
    'bun.exe run deploy',
    'pnpm --dir app deploy',     # pnpm'in yerleşik deploy'u (DOĞRULANMADI) — `pnpm deploy` ile aynı sınıf
    'yarn.cmd --cwd app deploy', # `.cmd` + bayrak birlikte
    # SINIF (lider kararı 2026-09-24): takma ad / bayrak / tırnak BİRLEŞİMLERİ desenle kovalanmaz — izin kuralı güvenlik
    # sınırı değildir, SAP'ye yazmanın güvenli yolu deploy_ui.py kapısıdır. npm 10.9.3'te bu 6'sının deploy script'ini
    # ÇALIŞTIRDIĞI gate tarafından ölçüldü:
    'npm run -s "deploy"',
    'npm rum "deploy"',
    'npm urn "deploy"',
    'npm urn -s deploy',
    'npm rum --silent deploy',
    "npm run-script 'deploy'",
    # yarn/bun tırnaklı — araç kurulu değil, script'i çalıştırdığı DOĞRULANAMADI; desen yok:
    'yarn "deploy"',
    'yarn run "deploy"',
    'bun run "deploy"',
]


class PaketYoneticisiDeployTest(unittest.TestCase):
    """Z106-EK: paket yöneticisi ile kapısız deploy/undeploy deny'a düşer; kapılı `deploy_ui.py` ask'ta kalır."""

    def setUp(self):
        self.kurallar = guncel_kurallar()

    def test_paket_yoneticisi_deploy_bicimleri_deny(self):
        eksik = []
        for komut, desen in Z106_PAKET_YONETICISI_DEPLOY:
            if self.kurallar.get("bash", {}).get(desen) != "deny":
                eksik.append(f"{desen!r} config/permissions.json'da deny değil → {komut!r} SAP'ye kapısız deploy eder")
                continue
            eslesen = _eslesen_desenler(self.kurallar, komut)
            if desen not in [p for p, _ in eslesen]:
                eksik.append(f"{desen!r} artık {komut!r} metnine uymuyor (eşleşenler: {eslesen})")
            if any(k != "deny" for _, k in eslesen):
                eksik.append(f"{komut!r} deny DIŞI bir desene de uyuyor: {eslesen}")
        self.assertEqual(eksik, [], "\n".join(eksik))

    def test_kontrol_grubu_dusmez(self):
        ihlal = [f"{k!r} → {_eslesen_desenler(self.kurallar, k)}" for k in Z106_KONTROL_GRUBU
                 if _eslesen_desenler(self.kurallar, k)]
        self.assertEqual(ihlal, [], "\n".join(ihlal))

    def test_kapili_deploy_ui_yalniz_ask(self):
        ihlal = [f"{k!r} → {_eslesen_desenler(self.kurallar, k)}" for k in Z106_KAPILI_YOL
                 if _eslesen_desenler(self.kurallar, k) != [("*deploy_ui*", "ask")]]
        self.assertEqual(ihlal, [], "kapılı yol yalnız `*deploy_ui*` ask'ına uymalı:\n" + "\n".join(ihlal))

    def test_bilinen_yanlis_pozitif_hala_deny(self):
        degisen = []
        for k, beklenen in Z106_BILINEN_YANLIS_POZITIF:
            eslesen = _eslesen_desenler(self.kurallar, k)
            if "deny" not in [v for _, v in eslesen]:
                degisen.append(f"{k!r} artık deny almıyor → {eslesen}")
            elif sorted(p for p, _ in eslesen) != sorted(beklenen):
                degisen.append(f"{k!r} eşleşen desen kümesi değişti: beklenen {sorted(beklenen)}, "
                               f"gerçek {sorted(p for p, _ in eslesen)}")
        self.assertEqual(degisen, [], "Belgelenmiş yanlış pozitif artık deny almıyor; docs/izin-kurallari.md/_aciklama "
                                      "güncellenmeli:\n" + "\n".join(degisen))

    def test_bilinen_acik_hala_acik(self):
        kapanan = [f"{k!r} → {_eslesen_desenler(self.kurallar, k)}" for k in Z106_BILINEN_ACIK
                   if _eslesen_desenler(self.kurallar, k)]
        self.assertEqual(kapanan, [], "Bilinen açık biçim kural alıyor; docs/izin-kurallari.md/_aciklama güncellenmeli:\n"
                         + "\n".join(kapanan))


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


class OrtamRgBilgiTest(GeciciTest):
    """Kullanıcı kararı (2026-09-24): kullanıcıya ek uygulama önerilmez; rg bunlardan biri. rg yoksa install.py Ortam
    satırı UYARI değil BİLGİ'dir ve kurulum yeri/indirme adresi basmaz (eskiden "[UYARI] rg: YOK ... yazılım merkezinden
    ya da https://github.com/BurntSushi/ripgrep/releases" — aXet-Kur.cmd penceresinde görünüyordu). Kontrol grubu: rg
    varsa [OK] + yol. doctor karşılığı: test_doctor.DoctorTest.test_rg_yoksa_yalniz_bilgi_oneri_adres_yok."""

    def test_check_env_rg_yoksa_durum_none_bilgi(self):
        import install
        from unittest import mock
        sahte = subprocess.CompletedProcess([], 0, stdout="v 1\n", stderr="")
        with mock.patch.object(install.shutil, "which", side_effect=lambda ad: None if ad == "rg" else "arac"), \
                mock.patch.object(install.subprocess, "run", return_value=sahte):
            satir = {ad: (bilgi, ok) for ad, bilgi, ok in install.check_env()}
        self.assertEqual(satir["rg"], ("yok (isteğe bağlı)", None))
        self.assertIs(satir["git"][1], True)  # diğer araçlar etkilenmez

    def test_install_rg_yoksa_bilgi_satiri_oneri_adres_yok(self):
        self.env = rg_siz_path(self.env)
        r = self.calistir("install.py", "--dry-run")
        c = self.cikti(r)
        self.assertEqual(r.returncode, 0, c)
        self.assertIn("  [BİLGİ] rg: yok (isteğe bağlı)", c)
        for yasak in ("ripgrep", "yazılım merkez", "[UYARI] rg"):
            self.assertNotIn(yasak, c)
        # kontrol grubu: rg varsa [OK] + yolu
        bin_ = self.tmp / "_rg"
        bin_.mkdir()
        (bin_ / "rg.cmd").write_text("@echo off\r\nexit /b 0\r\n", encoding="ascii", newline="")
        self.env = rg_siz_path(self.env, bin_)
        c = self.cikti(self.calistir("install.py", "--dry-run"))
        self.assertIn(f"  [OK] rg: {bin_ / 'rg'}.", c)  # uzantı harfi PATHEXT'ten gelir (ölçüldü: rg.CMD)
        self.assertNotIn("[BİLGİ] rg", c)


class PythonAsgariTest(unittest.TestCase):
    """Z80 nit (2026-09-24): `check_env` Python eşiği 3.9'du, kur.ps1 tabanı 3.12 ⇒ doctor 3.9-3.11'i PASS sayıyordu.
    Eşik `install.PY_ASGARI`'dir; kur.ps1 `$script:PyAsgari` ve .cmd başlatıcılarındaki literal ile EŞİTLİĞİ burada
    zorlanır (parite = tek kaynak; biri değişip öbürü değişmezse kırmızı).
    .cmd davranışı GERÇEK koşumla ölçülür: PATH'in başına konan `python.cmd` gerçek yorumlayıcıyı çağırır, yalnız
    `sitecustomize` ile `sys.version_info`'yu 3.11'e çevirir ⇒ .cmd'deki kontrol satırı gerçekten değerlendirilir.
    KAPSAM — bakılmayan: gerçek bir 3.11 kurulumu (sürüm sahte, yorumlayıcı gerçek) · Windows dışı."""

    CMDLER = ("yeni-proje.cmd", "proje-tamamla.cmd")

    def _python_satiri(self, surum: tuple):
        import install
        from unittest import mock
        with mock.patch.object(install.sys, "version_info", surum), \
                mock.patch.object(install.sys, "version", ".".join(map(str, surum[:3])) + " (sahte)"), \
                mock.patch.object(install.shutil, "which", return_value=None):
            satir = [s for s in install.check_env() if s[0] == "python"]
        self.assertEqual(len(satir), 1)
        return satir[0][1], satir[0][2]

    def test_eski_python_gecmez_ve_gerekli_surum_yazilir(self):
        bilgi, ok = self._python_satiri((3, 11, 9, "final", 0))
        self.assertFalse(ok, bilgi)
        self.assertIn("3.11.9", bilgi)
        self.assertIn("3.12", bilgi)  # gerekli sürüm söylenir

    def test_kontrol_grubu_asgari_ve_ustu_gecer(self):
        for surum in ((3, 12, 0, "final", 0), (3, 13, 1, "final", 0)):
            with self.subTest(surum=surum):
                bilgi, ok = self._python_satiri(surum)
                self.assertTrue(ok, bilgi)

    def test_parite_kur_ps1_ve_cmd_baslaticilari(self):
        import re
        import install
        self.assertIsInstance(install.PY_ASGARI, tuple)
        m = re.search(r"^\$script:PyAsgari = \[version\]'(\d+)\.(\d+)'", (AXET_HOME / "kur.ps1").read_text(encoding="utf-8-sig"), re.M)
        self.assertIsNotNone(m, "kur.ps1'de $script:PyAsgari satırı bulunamadı")
        self.assertEqual((int(m.group(1)), int(m.group(2))), install.PY_ASGARI)
        etiket = "%d.%d+" % install.PY_ASGARI
        for ad in self.CMDLER:
            with self.subTest(cmd=ad):
                metin = (AXET_HOME / ad).read_text(encoding="utf-8")
                esik = re.findall(r"sys\.version_info>=\((\d+),(\d+)\)", metin)
                self.assertEqual(len(esik), 1, f"{ad}: sürüm kontrol satırı tam 1 kez olmalı")
                self.assertEqual(tuple(map(int, esik[0])), install.PY_ASGARI)
                self.assertIn(":python_eski", metin)
                self.assertIn(etiket, metin)  # kullanıcı mesajındaki sürüm de aynı

    def _eski_python_path(self, surum: str | None) -> dict:
        import os
        import tempfile
        from pathlib import Path
        d = Path(tempfile.mkdtemp(prefix="axet-pyeski-"))
        self.addCleanup(shutil.rmtree, d, True)
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
        if surum is not None:
            maj, mn = surum.split(".")
            (d / "site").mkdir()
            (d / "site" / "sitecustomize.py").write_text(
                f"import sys\nsys.version_info = ({maj}, {mn}, 9, 'final', 0)\n", encoding="utf-8")
            env["PYTHONPATH"] = str(d / "site")
        # Sahte python.cmd KULLANILMAZ (ölçüldü): .cmd içinden `call`sız çağrılan bir .cmd denetimi geri vermez,
        # başlatıcı sessizce rc 0 ile biter. Gerçek python.exe PATH'in başına konur; sürüm yalnız sitecustomize'la sahte.
        env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
        return env

    def _cmd(self, ad: str, env: dict, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["cmd", "/c", "call", str(AXET_HOME / ad), *args], env=env, capture_output=True,
                              text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=120)

    @unittest.skipUnless(sys.platform == "win32", ".cmd yalnız Windows'ta koşar")
    def test_cmd_eski_python_python_eski_yoluna_girer(self):
        env = self._eski_python_path("3.11")
        # enjeksiyon tuttu mu (tutmazsa test hiçbir şey ölçmez)
        dene = subprocess.run(["cmd", "/c", "python", "-c", "import sys;print(sys.version_info[:2])"], env=env,
                              capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60)
        self.assertIn("(3, 11)", dene.stdout, dene.stdout + dene.stderr)
        for ad, args in (("yeni-proje.cmd", ("--help",)), ("proje-tamamla.cmd", (str(AXET_HOME / "yok-klasor"),))):
            with self.subTest(cmd=ad):
                r = self._cmd(ad, env, *args)
                c = r.stdout + r.stderr
                self.assertEqual(r.returncode, 9009, c)
                self.assertIn("surumu yetersiz", c)
                self.assertNotIn("python bulunamadi", c)

    @unittest.skipUnless(sys.platform == "win32", ".cmd yalnız Windows'ta koşar")
    def test_cmd_kontrol_grubu_yeterli_python_devam_eder(self):
        env = self._eski_python_path(None)  # gerçek yorumlayıcı (>= PY_ASGARI; test ortamı)
        self.assertGreaterEqual(tuple(sys.version_info[:2]), __import__("install").PY_ASGARI)
        r = self._cmd("yeni-proje.cmd", env, "--help")
        c = r.stdout + r.stderr
        self.assertEqual(r.returncode, 0, c)
        self.assertNotIn("surumu yetersiz", c)
        # proje-tamamla: sürüm kapısını geçer, sonraki kapıda (klasör yok) durur
        r = self._cmd("proje-tamamla.cmd", env, str(AXET_HOME / "yok-klasor"))
        c = r.stdout + r.stderr
        self.assertNotIn("surumu yetersiz", c)
        self.assertIn("proje klasoru bulunamadi", c)

    # --- Z98: `python` çalışmıyorsa .cmd başlatıcıları `py -3` ile dener ------------------------------------------
    def _py_yedek_path(self, py_var: bool) -> dict:
        """PATH'te `python` YOK (yalnız geçici klasör + System32). py_var=True ise klasörde yalnız `-3`'ü tanıyan sahte
        bir py.cmd var ve gerçek yorumlayıcıya yönlendirir (başka argümanda rc 1). .cmd başlatıcı seçtiği yorumlayıcının
        TAM yolunu (sys.executable) kullanmalı: sahte py.cmd yalnız seçimde çağrılır, sonraki çağrılar gerçek exe'ye gider."""
        import os
        import tempfile
        from pathlib import Path
        d = Path(tempfile.mkdtemp(prefix="axet-pyyedek-"))
        self.addCleanup(shutil.rmtree, d, True)
        if py_var:
            (d / "py.cmd").write_text(
                '@echo off\r\nif not "%~1"=="-3" exit /b 1\r\n'
                f'"{Path(sys.executable).resolve()}" %2 %3 %4 %5 %6 %7 %8 %9\r\nexit /b %errorlevel%\r\n',
                encoding="ascii", newline="")
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
        for k in [k for k in env if k.upper() == "PATH"]:
            del env[k]
        sys32 = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"
        env["PATH"] = os.pathsep.join([str(d), str(sys32)])
        # enjeksiyon tuttu mu: bu PATH'le `python` çalışmamalı (yoksa test py kolunu hiç ölçmez)
        dene = subprocess.run(["cmd", "/c", "python", "--version"], env=env, capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, timeout=60)
        self.assertNotEqual(dene.returncode, 0, dene.stdout + dene.stderr)
        return env

    @unittest.skipUnless(sys.platform == "win32", ".cmd yalnız Windows'ta koşar")
    def test_cmd_python_yoksa_py_3_ile_devam_eder(self):
        env = self._py_yedek_path(True)
        r = self._cmd("yeni-proje.cmd", env, "--help")
        c = r.stdout + r.stderr
        self.assertEqual(r.returncode, 0, c)
        self.assertNotIn("python bulunamadi", c)
        r = self._cmd("proje-tamamla.cmd", env, str(AXET_HOME / "yok-klasor"))
        c = r.stdout + r.stderr
        self.assertNotIn("python bulunamadi", c)
        self.assertIn("proje klasoru bulunamadi", c)

    @unittest.skipUnless(sys.platform == "win32", ".cmd yalnız Windows'ta koşar")
    def test_cmd_python_da_py_da_yoksa_python_yok_mesaji(self):
        env = self._py_yedek_path(False)
        for ad, args in (("yeni-proje.cmd", ("--help",)), ("proje-tamamla.cmd", (str(AXET_HOME / "yok-klasor"),))):
            with self.subTest(cmd=ad):
                r = self._cmd(ad, env, *args)
                c = r.stdout + r.stderr
                self.assertEqual(r.returncode, 9009, c)
                self.assertIn("python bulunamadi", c)
                self.assertNotIn("surumu yetersiz", c)



# --- Z101: SAP bağlantısının ZORUNLU üçüncü-parti Python paketleri ------------------------------------------------
# Yeni makinede requests yoktu ⇒ `sap_adt_cli adt_get` "No module named 'requests'" ile düştü (ölçüldü 2026-09-24:
# PYTHONPATH'e konan engelleyici modülle requests/urllib3/dotenv'in HER BİRİ ayrı ayrı adt_get'i rc=1 düşürdü;
# kontrol grubu engelsiz → gerçek bağlantı hatası). Gerçek pip HİÇBİR testte çalışmaz, ağa çıkılmaz:
#   · "eksik" = PYTHONPATH başındaki ENGEL klasörü (import edilince ModuleNotFoundError fırlatan modüller)
#   · "kurulu" = PYTHONPATH başındaki SAHTE klasör (boş modüller — makinede gerçek paket olmasa da import olur)
#   · pip = AXET_PAKET_PIP ile verilen sahte betik: argümanlarını kayıt dosyasına yazar; kipine göre engeli kaldırır
#     ("kurmuş" olur), ağ hatası ya da "pip yok" basar.

SAHTE_PIP = (
    "import os, shutil, sys\n"
    "with open(os.environ['AXET_TEST_PIP_KAYIT'], 'a', encoding='utf-8') as fh:\n"
    "    fh.write(' '.join(sys.argv[1:]) + '\\n')\n"
    "kip = os.environ.get('AXET_TEST_PIP_KIP', 'basari')\n"
    "if kip == 'basari':\n"
    "    shutil.rmtree(os.environ['AXET_TEST_ENGEL'], ignore_errors=True)\n"
    "    print('Successfully installed (sahte)')\n"
    "    sys.exit(0)\n"
    "if kip == 'ag':\n"
    "    print(\"WARNING: Retrying ... ProxyError('Cannot connect to proxy.')\", file=sys.stderr)\n"
    "    print('ERROR: Could not find a version that satisfies the requirement requests', file=sys.stderr)\n"
    "    sys.exit(1)\n"
    "if kip == 'yarim':\n"
    "    sys.exit(0)\n"
    "if kip == 'izin':\n"
    "    print('ERROR: Could not install packages due to an OSError: [WinError 5] Access is denied', file=sys.stderr)\n"
    "    sys.exit(1)\n"
    "if kip == 'venv':\n"
    "    print('ERROR: Could not find an activated virtualenv (required).', file=sys.stderr)\n"
    "    sys.exit(3)\n"
    "if kip == 'pep668':\n"
    "    print('error: externally-managed-environment', file=sys.stderr)\n"
    "    sys.exit(1)\n"
    "if kip == 'turkce':\n"
    "    print('HATA: baglanti kurulamadi: \u015f\u011f\u00fc\u0130\u0131', file=sys.stderr)\n"
    "    sys.exit(1)\n"
    "if kip == 'olcumbozan':\n"
    "    with open(os.path.join(os.environ['AXET_TEST_ENGEL'], 'sitecustomize.py'), 'w', encoding='utf-8') as fh:\n"
    "        fh.write('import os\\nos._exit(3)\\n')\n"
    "    sys.exit(0)\n"
    "print(sys.executable + ': No module named pip', file=sys.stderr)\n"
    "sys.exit(1)\n"
)


def _paket_modulleri() -> list[str]:
    import install
    return [ithal for ithal, _ in install.ZORUNLU_PAKETLER]


class PaketAdimiTest(GeciciTest):
    """install.py → eksik zorunlu paketleri bulunan yorumlayıcının pip'iyle kurar; kurulumu DURDURMAZ."""

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
        self.engel = self.tmp / "_engel"
        self.kurulu = self.tmp / "_kurulu"
        self.kayit = self.tmp / "_pip_kayit.txt"
        pip = self.yaz(self.tmp / "_sahte_pip.py", SAHTE_PIP)
        self.env.pop("AXET_PAKET_KUR", None)  # _helpers testlerde kapatır; burada adım AÇIK ölçülür
        self.env.update({"AXET_PAKET_PIP": str(pip), "AXET_TEST_PIP_KAYIT": str(self.kayit),
                         "AXET_TEST_ENGEL": str(self.engel), "AXET_TEST_PIP_KIP": "basari"})

    def eksik(self, *moduller: str) -> None:
        self.engel.mkdir(exist_ok=True)
        for m in moduller or _paket_modulleri():
            self.yaz(self.engel / f"{m}.py", f"raise ModuleNotFoundError(\"No module named '{m}'\", name='{m}')\n")
        self.env["PYTHONPATH"] = str(self.engel)

    def hepsi_kurulu(self) -> None:
        for m in _paket_modulleri():
            self.yaz(self.kurulu / f"{m}.py", "")
        self.env["PYTHONPATH"] = str(self.kurulu)

    def install(self, *args: str):
        return self.calistir(self.klon / "scripts" / "install.py", *args)

    def pip_cagrilari(self) -> list[str]:
        return self.kayit.read_text(encoding="utf-8").splitlines() if self.kayit.exists() else []

    def test_eksik_paket_pip_ile_kurulur_ve_dogrulanir(self):
        import install
        self.eksik()
        r = self.install("--sap")
        self.assertEqual(0, r.returncode, self.cikti(r))
        cagri = self.pip_cagrilari()
        self.assertEqual(1, len(cagri), cagri)
        parca = cagri[0].split()
        self.assertEqual("install", parca[0])
        self.assertIn("--user", parca)
        for _, spec in install.ZORUNLU_PAKETLER:
            self.assertIn(spec, parca)
        self.assertIn("PAKETLER: KURULDU", r.stdout)

    def test_yalniz_eksik_olan_kurulur(self):
        import install
        self.eksik("dotenv")
        # engelsiz modüller gerçek makinede olmayabilir ⇒ sahte kurulu klasör de yola eklenir (engel önde)
        for m in _paket_modulleri():
            if m != "dotenv":
                self.yaz(self.kurulu / f"{m}.py", "")
        self.env["PYTHONPATH"] = str(self.engel) + os.pathsep + str(self.kurulu)
        r = self.install("--sap")
        self.assertEqual(0, r.returncode, self.cikti(r))
        cagri = self.pip_cagrilari()
        self.assertEqual(1, len(cagri), cagri)
        specler = dict(install.ZORUNLU_PAKETLER)
        self.assertIn(specler["dotenv"], cagri[0].split())
        self.assertNotIn(specler["requests"], cagri[0].split())

    def test_kontrol_grubu_hepsi_kuruluysa_pip_cagrilmaz(self):
        self.hepsi_kurulu()
        r = self.install("--sap")
        self.assertEqual(0, r.returncode, self.cikti(r))
        self.assertEqual([], self.pip_cagrilari())
        self.assertIn("PAKETLER: TAMAM", r.stdout)
        # tur 2 madde 1: sürüm DENETLENMEDİĞİ için TAMAM satırı sürüm belirtimi yazmaz, kapsamını söyler
        tamam = next(s for s in r.stdout.splitlines() if s.startswith("PAKETLER: TAMAM"))
        self.assertNotIn(">=", tamam)
        self.assertIn("sürüm alt sınırı denetlenmez", tamam)

    def test_ag_hatasi_kurulumu_durdurmaz_uyari_ve_yapilacak_yazilir(self):
        self.eksik()
        self.env["AXET_TEST_PIP_KIP"] = "ag"
        r = self.install("--sap")
        self.assertEqual(0, r.returncode, self.cikti(r))
        self.assertIn("PAKETLER: EKSİK", r.stdout)
        self.assertIn("UYARI", r.stdout)
        self.assertIn("proxy", r.stdout.lower())
        self.assertIn("requests", r.stdout)
        # config yine yazıldı: paket adımı kurulumun geri kalanını etkilemez
        self.assertTrue((self.xdg / "axet-code" / "axet-code.json").is_file())

    def test_pip_yoksa_ayri_mesaj_kurulum_durmaz(self):
        self.eksik()
        self.env["AXET_TEST_PIP_KIP"] = "pipyok"
        r = self.install("--sap")
        self.assertEqual(0, r.returncode, self.cikti(r))
        self.assertIn("PAKETLER: EKSİK", r.stdout)
        self.assertIn("pip bulunamadı", r.stdout)

    # --- tur 2 (bağımsız inceleme WARNING): hata sınıflandırması, ölçülemeyen sonuç, kodlama ---------------------
    def _hata(self, kip: str):
        self.eksik()
        self.env["AXET_TEST_PIP_KIP"] = kip
        r = self.install("--sap")
        self.assertEqual(0, r.returncode, self.cikti(r))
        return r.stdout

    def test_ag_disi_pip_hatasi_proxy_denmez(self):
        """Ölçülen iki ağ-dışı hata (require-virtualenv, WinError 5) eskiden "ağ/proxy" diye raporlanıyordu."""
        for kip in ("izin", "venv"):
            with self.subTest(kip=kip):
                out = self._hata(kip)
                self.assertIn("PAKETLER: EKSİK", out)
                self.assertNotIn("proxy", out.lower())
                self.assertIn("pip hata verdi", out)
                self.assertIn("pip çıktısının sonu", out)
                self.kayit.unlink(missing_ok=True)

    def test_pep668_ayri_aciklama(self):
        out = self._hata("pep668")
        self.assertIn("PAKETLER: EKSİK", out)
        self.assertIn("dışarıdan yönetilen", out)
        self.assertNotIn("proxy", out.lower())

    def test_yeniden_olcum_basarisizsa_olculemedi_denir(self):
        out = self._hata("olcumbozan")
        self.assertIn("PAKETLER: ÖLÇÜLEMEDİ", out)
        self.assertNotIn("PAKETLER: EKSİK", out)
        self.assertNotIn("PAKETLER: KURULDU", out)

    def test_pip_ciktisi_turkce_bozulmadan_gelir(self):
        """pip kendi ortam kodlamasıyla yazar (ölçüldü: bu makinede cp1252 → `\\u015f` kaçışları); install.py pip'i
        UTF-8 G/Ç ile çağırır. Değişkenler bu testte ortamdan KALDIRILIR ki düzeltme install.py'den gelsin."""
        self.env.pop("PYTHONIOENCODING", None)
        self.env.pop("PYTHONUTF8", None)
        out = self._hata("turkce")
        self.assertIn("\u015f\u011f\u00fc\u0130\u0131", out)

    def test_pip_basari_dese_de_import_olmuyorsa_eksik_sayilir(self):
        """pip rc=0 ≠ paket yüklenebilir: sonuç yeniden import edilerek ölçülür."""
        self.eksik()
        self.env["AXET_TEST_PIP_KIP"] = "yarim"
        r = self.install("--sap")
        self.assertEqual(0, r.returncode, self.cikti(r))
        self.assertIn("PAKETLER: EKSİK", r.stdout)
        self.assertNotIn("PAKETLER: KURULDU", r.stdout)

    def test_dry_run_yalniz_gosterir(self):
        self.eksik()
        r = self.install("--sap", "--dry-run")
        self.assertEqual(0, r.returncode, self.cikti(r))
        self.assertEqual([], self.pip_cagrilari())
        self.assertIn("PAKETLER: EKSİK", r.stdout)
        self.assertIn("kurulacaktı", r.stdout)

    def test_uninstall_ve_sap_kapaliyken_kurmaz(self):
        self.eksik()
        for args in (("--uninstall",), ("--no-sap",)):
            with self.subTest(args=args):
                r = self.install(*args)
                self.assertEqual(0, r.returncode, self.cikti(r))
                self.assertEqual([], self.pip_cagrilari())
        self.assertIn("PAKETLER: ATLANDI", r.stdout)  # --no-sap: SAP paketi kapalı

    def test_degisiklik_yok_dalinda_da_kurar(self):
        self.hepsi_kurulu()
        r = self.install("--sap")
        self.assertEqual(0, r.returncode, self.cikti(r))
        self.eksik()
        r2 = self.install("--sap")
        self.assertEqual(0, r2.returncode, self.cikti(r2))
        self.assertIn("Değişiklik yok", r2.stdout)
        self.assertEqual(1, len(self.pip_cagrilari()))

    # --- Z102: `--paketler` — %guncelle her güncellemede koşar; config'e YAZMAZ ---------------------------------------
    def _config_izi(self) -> dict:
        """Global config klasörünün tam izi: dosya adı → (sha256, mtime_ns). Yeni .bak ya da içerik değişimi görünür."""
        import hashlib
        kok = self.xdg / "axet-code"
        if not kok.exists():
            return {}
        return {f.name: (hashlib.sha256(f.read_bytes()).hexdigest(), f.stat().st_mtime_ns)
                for f in sorted(kok.iterdir()) if f.is_file()}

    def test_paketler_kipi_config_yazmaz_eksigi_kurar(self):
        self.hepsi_kurulu()
        r = self.install("--sap")  # SAP açık kurulum: config yazıldı
        self.assertEqual(0, r.returncode, self.cikti(r))
        once = self._config_izi()
        self.assertIn("axet-code.json", once)
        yazma = self.klon / "config" / "sap-write.local"
        self.eksik()
        r = self.install("--paketler")
        c = self.cikti(r)
        self.assertEqual(0, r.returncode, c)
        self.assertEqual(1, len(self.pip_cagrilari()))  # eksik paket kuruldu (install.py değişmemiş olsa da)
        self.assertIn("PAKETLER: KURULDU", r.stdout)
        self.assertEqual(once, self._config_izi(), "--paketler global config klasörüne yazdı (içerik/mtime/.bak)")
        self.assertFalse(yazma.exists(), "--paketler SAP yazma bayrağına dokundu")
        self.assertNotIn("Global config", r.stdout)  # kurulum kipinin çıktısı yok
        self.assertNotIn("Tarayıcı hazırlığı", r.stdout)  # tarayıcı adımı %guncelle'de ayrı adım

    def test_paketler_kipi_sap_kapaliysa_atlar_config_olusturmaz(self):
        self.eksik()
        r = self.install("--paketler")
        self.assertEqual(0, r.returncode, self.cikti(r))
        self.assertIn("PAKETLER: ATLANDI — SAP paketi kapalı", r.stdout)
        self.assertEqual([], self.pip_cagrilari())
        self.assertEqual({}, self._config_izi())  # config yoktu, yine yok

    def test_paketler_kipi_bozuk_config_olculemedi_rc0_dokunmaz(self):
        f = self.yaz(self.xdg / "axet-code" / "axet-code.json", "{bozuk")
        once = self._config_izi()
        self.eksik()
        r = self.install("--paketler")
        self.assertEqual(0, r.returncode, self.cikti(r))  # güncellemeyi bozmaz
        self.assertIn("PAKETLER: ÖLÇÜLEMEDİ", r.stdout)
        self.assertEqual([], self.pip_cagrilari())
        self.assertEqual(once, self._config_izi())
        self.assertEqual("{bozuk", f.read_text(encoding="utf-8"))

    def test_paketler_kipi_dry_run_kurmaz(self):
        self.hepsi_kurulu()
        self.assertEqual(0, self.install("--sap").returncode)
        self.eksik()
        r = self.install("--paketler", "--dry-run")
        self.assertEqual(0, r.returncode, self.cikti(r))
        self.assertEqual([], self.pip_cagrilari())
        self.assertIn("kurulacaktı", r.stdout)

    def test_paketler_baska_bayrakla_birlesmez(self):
        self.eksik()
        for ek in ("--sap", "--no-sap", "--sap-write", "--no-sap-write", "--uninstall"):
            with self.subTest(ek=ek):
                r = self.install("--paketler", ek)
                self.assertEqual(3, r.returncode, self.cikti(r))
                self.assertIn("--paketler yalnız başına", r.stdout)
        self.assertEqual([], self.pip_cagrilari())
        self.assertEqual({}, self._config_izi())
        self.assertFalse((self.klon / "config" / "sap-write.local").exists())

    def test_pip_mesaji_sade_ve_elle_komut_bt_etiketli(self):
        """Kullanıcıya dönük: önce sade Türkçe ne olduğu, tekrar deneme yolu %guncelle; elle komut yalnız BT için
        etiketli. Eski 'kur.cmd'yi yeniden çalıştır' (terminal komutu) ve etiketsiz 'Elle kurulum:' kalmadı."""
        out = self._hata("ag")
        self.assertIn("Paket internetten indirilemedi", out)
        self.assertIn("%guncelle", out)
        self.assertIn("BT için elle kurulum komutu (sen çalıştırma): ", out)
        self.assertNotIn("  Elle kurulum:", out)
        self.assertNotIn("kur.cmd'yi yeniden çalıştır", out)
        uyari = next(s for s in out.splitlines() if "UYARI:" in s)
        bt = next(i for i, s in enumerate(out.splitlines()) if "BT için elle kurulum komutu" in s)
        self.assertLess(out.splitlines().index(uyari), bt)  # önce açıklama, sonra BT komutu

    def test_kapatma_ortami_pip_cagirmaz(self):
        """Test takımının güvencesi: _helpers AXET_PAKET_KUR=0 verir → hiçbir install.py koşumu pip'e gitmez."""
        self.eksik()
        self.env["AXET_PAKET_KUR"] = "0"
        r = self.install("--sap")
        self.assertEqual(0, r.returncode, self.cikti(r))
        self.assertEqual([], self.pip_cagrilari())
        self.assertIn("PAKETLER: ATLANDI — AXET_PAKET_KUR=0", r.stdout)


class PaketKaynakTest(unittest.TestCase):
    """Zorunlu paket listesinin TEK kaynağı install.py'dir; diğer her yer oradan okur ya da eşitliği burada zorlanır."""

    def test_helpers_testlerde_paket_adimini_kapatir(self):
        import _helpers
        t = _helpers.GeciciTest("run")
        t.setUp()
        try:
            self.assertEqual("0", t.env.get("AXET_PAKET_KUR"))
        finally:
            t.tearDown()

    def test_requirements_txt_install_sabitiyle_ayni(self):
        import install
        dosya = AXET_HOME / "skills-sap" / "sap-adt-foundation" / "scripts" / "requirements.txt"
        satirlar = [s.strip() for s in dosya.read_text(encoding="utf-8").splitlines()
                    if s.strip() and not s.strip().startswith("#")]
        self.assertEqual(sorted(satirlar), sorted(spec for _, spec in install.ZORUNLU_PAKETLER),
                         "requirements.txt (CI) ile install.ZORUNLU_PAKETLER ayrıştı — birini değiştiren öbürünü de değiştirir")

    def test_guncelle_install_py_degisince_install_kosar(self):
        """%guncelle bağlaması: liste install.py'de durduğu için listeye eklenen paket install.py'yi değiştirir;
        harita o dosyanın özel adımında GERÇEK install.py'yi (yalnız --dry-run değil) koşar ⇒ mevcut kullanıcıda da
        kurulur. Liste başka dosyaya taşınırsa bu bağ kopar (requirements.txt → skill-script, özel adım yok)."""
        import re
        if str(AXET_HOME / "guncelle") not in sys.path:
            sys.path.insert(0, str(AXET_HOME / "guncelle"))
        import siniflandir
        harita = siniflandir.harita_yukle()
        sinif = siniflandir.siniflandir("scripts/install.py", harita)
        kayit = next(s for s in harita["siniflar"] if s["sinif"] == sinif)
        komutlar = [k.strip() for k in re.findall(r"python\s+[\w./\\-]+\.py[^,;\n]*", kayit["ozel_adim"] or "")]
        self.assertIn("python scripts/install.py", komutlar)
        kaynak = (AXET_HOME / "scripts" / "install.py").read_text(encoding="utf-8")
        self.assertIsNotNone(re.search(r"(?m)^ZORUNLU_PAKETLER\b", kaynak), "liste install.py'nin kendisinde tanımlı olmalı")
        req = siniflandir.siniflandir("skills-sap/sap-adt-foundation/scripts/requirements.txt", harita)
        req_kayit = next(s for s in harita["siniflar"] if s["sinif"] == req)
        self.assertFalse(req_kayit.get("ozel_adim"), "requirements.txt'in özel adımı yoksa tek kaynak o olamaz")

    def test_onboarding_paket_maddesi_guncelle_iddiasi_olculu(self):
        """Tur 2 madde 4: belge "%guncelle eksik olanı kurar" diyordu ama o zaman %guncelle install.py'yi yalnız
        install.py'nin DEĞİŞTİĞİ yayında koşuyordu. Z102 (2026-09-24) bu sınırı kaldırdı: %guncelle HER seferinde
        `install.py --paketler` koşar — iddia artık doğru VE mekanizmasıyla yazılı olmalı (GUNCELLE.md 17. adım ayrıca
        test_guncelle_her_seferinde_paket_adimini_kosar'da). Madde README'den onboarding "Sorun giderme"ye taşındı
        (README sadeleştirme); doctor'un gösterdiği ve kur.cmd yolu yine yazılı."""
        metin = (AXET_HOME / "docs" / "onboarding.md").read_text(encoding="utf-8")
        madde = next(m for m in metin.split("\n- ") if m.startswith("SAP bağlantısının Python paketleri"))
        self.assertIn("install.py", madde)
        self.assertIn("install.py --paketler", madde)  # iddianın mekanizması
        self.assertIn("%guncelle", madde)
        self.assertIn("doctor", madde)
        self.assertIn("kur.cmd", madde)
        self.assertIn("BT için elle kurulum komutu (sen çalıştırma)", madde)  # install.py'nin bastığı etiketle aynı
        self.assertNotIn("kurulum aracı ve `%guncelle`, eksik olanı", madde)
        self.assertNotIn("yalnız `scripts/install.py`'nin değiştiği", madde)  # Z102 öncesi sınır artık yanlış
        kaynak = (AXET_HOME / "scripts" / "install.py").read_text(encoding="utf-8")
        self.assertIn("BT için elle kurulum komutu (sen çalıştırma)", kaynak)

    def test_guncelle_her_seferinde_paket_adimini_kosar(self):
        """Z102: %guncelle install.py'yi yalnız install.py DEĞİŞİNCE koşuyordu (harita özel adımı) ⇒ paketi eksik
        kullanıcı, install.py'ye dokunmayan her yayında eksik kalıyordu. GUNCELLE.md'nin otomatik 17. adımı paket
        kipini HER güncellemede — klon güncel çıkıp 2/3/4'te bitse de — koşar; skill aynı adımı anar."""
        import re
        metin = (AXET_HOME / "GUNCELLE.md").read_text(encoding="utf-8")
        satirlar = {m.group(1): m.group(0) for m in re.finditer(r"^\|\s*(\d+)\s*\|.*$", metin, re.M)}
        adim = satirlar.get("17", "")
        self.assertIn('`python "<klon>/scripts/install.py" --paketler`', adim)
        self.assertIn("soru SORMA", adim)
        self.assertIn("BOZMAZ", adim)
        self.assertIn("çıkış daima 0", adim)
        self.assertEqual(6, adim.count("|"), "tablo hücresi içinde çıplak '|' var (satır bölünür)")
        for no in ("2", "3", "4"):  # "güncel → BİTİR" dalları paket adımını atlamaz
            self.assertIn("adım 17", satirlar[no], f"adım {no}")
        skill = (AXET_HOME / "skills" / "guncelle" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn('python "<KLON>/scripts/install.py" --paketler', skill)
        # belge ile motor aynı bayrağı konuşuyor (bayrak adı install.py'nin argparse'ında)
        self.assertIn('"--paketler"', (AXET_HOME / "scripts" / "install.py").read_text(encoding="utf-8"))

    def test_paketler_komutu_izin_desenlerine_takilmaz(self):
        """%guncelle `python "<klon>/scripts/install.py" --paketler` çağırır; bu metin template bash desenlerinden
        hiçbirine uymamalı (fnmatch simülasyonu; aXet eşleştiricisi değil — test_tarayici_hazirla ile aynı yöntem).
        Kontrol grubu: `--sap-write` çağrısı deny desenine UYAR (simülasyon kör değil)."""
        import fnmatch
        kurallar = json.loads((AXET_HOME / "config" / "permissions.json").read_text(encoding="utf-8"))["rules"]["bash"]
        for komut in ('python "C:/Users/x/axet/scripts/install.py" --paketler',
                      'python "C:/Users/x/axet/scripts/install.py" --paketler --dry-run'):
            with self.subTest(komut=komut):
                self.assertEqual([], [d for d in kurallar if fnmatch.fnmatchcase(komut, d)])
        kontrol = 'python "C:/Users/x/axet/scripts/install.py" --sap --sap-write'
        self.assertEqual(["deny"], [kurallar[d] for d in kurallar if fnmatch.fnmatchcase(kontrol, d)])

    def test_venv_icinde_user_verilmez(self):
        import install
        from unittest import mock
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AXET_PAKET_PIP", None)
            with mock.patch.object(install.sys, "prefix", "C:/venv"), \
                    mock.patch.object(install.sys, "base_prefix", "C:/Python312"):
                self.assertNotIn("--user", install.pip_komutu(["requests"]))
            with mock.patch.object(install.sys, "prefix", "C:/Python312"), \
                    mock.patch.object(install.sys, "base_prefix", "C:/Python312"):
                komut = install.pip_komutu(["requests"])
        self.assertEqual([sys.executable, "-m", "pip", "install"], komut[:4])
        self.assertIn("--user", komut)
        self.assertEqual("requests", komut[-1])
