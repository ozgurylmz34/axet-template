# -*- coding: utf-8 -*-
"""quality_scorecard.py testleri — kapı defteri (append-only) + karne değişmezleri.

Her test bir DEĞİŞMEZİ çivilemek içindir; başlıklarda D1..D6 numaraları aşağıdaki listeye karşılık gelir:
  D1 `not-run` ayrı bir durumdur (sessizce `pass` sayılmaz)
  D2 artefaktsız / artefaktı diskte olmayan `pass` → karne GÜVENİLMEZ, çıkış 2
  D3 sıfır test ile koşmuş kapı `pass` olamaz → `warn`
  D4 dar/varsayılan kapsamla koşmuş kapı `pass` olamaz → `warn` + not
  D5 kapsam beyanı boş satır → karne bunu SÖYLER
  D6 arka durak: doğrulama yalnız yazma anında değil OKUMA anında da koşar (elle eklenen satır)

Kontrol grubu kuralı: her düşürme testinin yanında "çalıştığı bilinen" vaka da ölçülür
(ör. artefaktı DİSKTE OLAN `pass` gerçekten `pass` kalır) — yoksa test yalnız tek yönlü gözlemdir.

Testler SAP'ye bağlanmaz, ağ kullanmaz, repo içine yazmaz: her test kendi geçici dizinini alır.
"""
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
SKILLS_SAP = SKILL.parent
TEMPLATE = SKILLS_SAP.parent
SCRIPT = SKILL / 'scripts' / 'quality_scorecard.py'
GATE_STATUS = SKILLS_SAP / 'sap-adt-foundation' / 'scripts' / 'sapadt' / 'lib' / 'validators' / '_gate_status.py'
RUN_REVIEW = SKILLS_SAP / 'sap-adt-foundation' / 'scripts' / 'sapadt' / 'lib' / 'validators' / 'run_review.py'
GATE_PY = SKILLS_SAP / 'sap-adt-foundation' / 'scripts' / 'sapadt' / 'gate.py'
ABAPLINT_RUN = SKILL / 'scripts' / 'abaplint_run.py'


def _cli(*args, cwd=None):
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env.pop('AXET_SAP_PROJECT_DIR', None)
    r = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True,
                       encoding='utf-8', errors='replace', timeout=120, env=env, cwd=cwd)
    return r.returncode, r.stdout, r.stderr


def _karne_json(defter: Path, *extra, cwd=None):
    rc, out, err = _cli('karne', '--defter', str(defter), '--json', *extra, cwd=cwd)
    try:
        return rc, json.loads(out), err
    except json.JSONDecodeError as e:  # noqa: PERF203
        raise AssertionError(f'karne --json JSON üretmedi (rc={rc}): {e}\nSTDOUT:\n{out}\nSTDERR:\n{err}')


class DefterTestTemeli(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='axet-karne-test-')).resolve()
        self.defter = self.tmp / 'kapi-defteri.jsonl'
        self.kanit = self.tmp / 'kanit.txt'
        self.kanit.write_text('artefakt gövdesi\n', encoding='utf-8')

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def satir_ekle(self, **alanlar):
        """Deftere ELLE satır ekler (kapı yolundan geçmeden) — D6 arka durağı için."""
        kayit = {'ts': '2026-09-15T00:00:00+00:00', 'kapi': 'validator:check_abaplint',
                 'sonuc': 'pass', 'artefakt': None, 'kapsam': 'kapsam notu', 'test_sayisi': None,
                 'dar_kapsam': False, 'measured': None, 'measured_reason': None, 'komut': None,
                 'kosum': 'TEST-KOSUM'}
        kayit.update(alanlar)
        with open(self.defter, 'a', encoding='utf-8') as f:
            f.write(json.dumps(kayit, ensure_ascii=False) + '\n')
        return kayit

    def kaydet(self, *args, cwd=None):
        return _cli('kaydet', '--defter', str(self.defter), *args, cwd=cwd or self.tmp)


class D1NotRunAyriDurumTests(DefterTestTemeli):
    def test_not_run_pass_sayilmaz_ve_ayri_sayilir(self):
        self.satir_ekle(kapi='validator:check_abaplint', sonuc='pass', artefakt=str(self.kanit))
        self.satir_ekle(kapi='validator:check_bdef_backtick', sonuc='not-run', artefakt=None)
        rc, k, _ = _karne_json(self.defter)
        self.assertEqual(k['sayim']['not-run'], 1, 'not-run ayrı sayılmalı')
        self.assertEqual(k['sayim']['pass'], 1, 'not-run pass sayısına eklenmemeli')
        self.assertNotEqual(k['hukum'], 'PASS', 'not-run varken hüküm PASS olamaz')
        self.assertEqual(rc, 0)

    def test_not_run_satiri_artefakt_istemez(self):
        # Kontrol grubu: artefaktsızlık YALNIZ `pass` için güvenilmezlik üretir.
        self.satir_ekle(sonuc='not-run', artefakt=None)
        rc, k, _ = _karne_json(self.defter)
        self.assertEqual(rc, 0, f'not-run artefaktsız olabilir: {k}')
        self.assertFalse(k['guvenilmez'])

    def test_sayim_anahtarlari_ucunu_de_tasir(self):
        self.satir_ekle(sonuc='fail', artefakt=None)
        _, k, _ = _karne_json(self.defter)
        for anahtar in ('pass', 'fail', 'not-run', 'warn'):
            self.assertIn(anahtar, k['sayim'], f'{anahtar} sütunu karnede yok')


class D2ArtefaktsizPassTests(DefterTestTemeli):
    def test_artefaktsiz_pass_cikis_2(self):
        self.satir_ekle(sonuc='pass', artefakt=None)
        rc, k, _ = _karne_json(self.defter)
        self.assertEqual(rc, 2, f'artefaktsız pass çıkış 2 vermeli: {k}')
        self.assertTrue(k['guvenilmez'])
        self.assertEqual(k['hukum'], 'GUVENILMEZ')

    def test_diskte_olmayan_artefakt_yolu_cikis_2(self):
        self.satir_ekle(sonuc='pass', artefakt=str(self.tmp / 'yok.txt'))
        rc, k, _ = _karne_json(self.defter)
        self.assertEqual(rc, 2, f'diskte olmayan artefakt çıkış 2 vermeli: {k}')
        notlar = [n for s in k['satirlar'] for n in s['notlar']]
        self.assertTrue(any('artefakt' in n.lower() for n in notlar))
        # TESHIS METNI de civili: D2 uc katmanli fail-closed (exists -> is_file -> stat). Ust
        # katman sokulunce degismez (rc 2) korunur ama mesaj sessizce "dosya degil"e kayar ve
        # references/quality-scorecard.md'deki /tmp anlatimi yanlis mesaji tarif eder hale gelir.
        # Olculdu 2026-09-16: `if not yol.exists()` -> `if False` mutasyonu bu assert OLMADAN
        # YESIL kaliyordu.
        self.assertTrue(any('diskte YOK' in n for n in notlar),
                        f'diskte-olmayan artefakt icin teshis mesaji beklenen degil: {notlar}')

    def test_insan_kipinde_buyuk_uyari(self):
        self.satir_ekle(sonuc='pass', artefakt=None)
        rc, out, err = _cli('karne', '--defter', str(self.defter))
        self.assertEqual(rc, 2, 'insan kipi de aynı sözleşmeyi taşır')
        self.assertIn('GÜVENİLMEZ', (out + err).upper().replace('İ', 'İ'))

    def test_kontrol_grubu_artefakti_olan_pass_gecer(self):
        # ⚠ KISMI sözleşmesi geldikten SONRA tek satırlık bir defterin BÜTÜN hükmü `PASS` olamaz
        # (90 kapının 89'u kaydedilmemiş). Bu testin çivilediği şey bütün hüküm değil, SATIRIN
        # kendisidir: artefaktı diskte olan `pass` GEÇERLİDİR ve güvenilmezlik üretmez.
        self.satir_ekle(sonuc='pass', artefakt=str(self.kanit), test_sayisi=7)
        rc, k, _ = _karne_json(self.defter)
        self.assertEqual(rc, 0, f'artefaktı DİSKTE olan pass geçmeli (kontrol grubu): {k}')
        self.assertEqual(k['satirlar'][0]['etkin'], 'pass')
        self.assertEqual(k['satirlar'][0]['notlar'], [])
        self.assertFalse(k['guvenilmez'])
        self.assertEqual(k['sayim']['pass'], 1)
        self.assertIn(k['hukum'], ('PASS', 'KISMI'), 'satır temizse hüküm FAIL/WARN olamaz')

    def test_goreli_artefakt_yolu_cozulur(self):
        self.satir_ekle(sonuc='pass', artefakt='kanit.txt', test_sayisi=1)
        rc, k, _ = _karne_json(self.defter, cwd=self.tmp)
        self.assertEqual(rc, 0, f'göreli yol cwd\'ye göre çözülmeli: {k}')


class D3SifirTestWarnTests(DefterTestTemeli):
    def test_sifir_test_pass_olamaz(self):
        self.satir_ekle(sonuc='pass', artefakt=str(self.kanit), test_sayisi=0)
        rc, k, _ = _karne_json(self.defter)
        satir = k['satirlar'][0]
        self.assertEqual(satir['etkin'], 'warn', f'0 test pass kalamaz: {satir}')
        self.assertTrue(any('0 test' in n for n in satir['notlar']), satir['notlar'])
        self.assertEqual(k['sayim']['pass'], 0)
        self.assertEqual(k['sayim']['warn'], 1)
        self.assertEqual(rc, 0)

    def test_kontrol_grubu_pozitif_test_sayisi_pass_kalir(self):
        self.satir_ekle(sonuc='pass', artefakt=str(self.kanit), test_sayisi=5)
        _, k, _ = _karne_json(self.defter)
        self.assertEqual(k['satirlar'][0]['etkin'], 'pass')

    def test_tip_kacamagi_yakalanir(self):
        # D6 arka durağının tip ayağı: elle yazılmış `"0"` (metin) D3'ü atlatamaz — şema ihlali
        # olarak GEÇERSİZ sayılır. Kontrol grubu: gerçek int 0 zaten `warn`'a düşer.
        self.satir_ekle(sonuc='pass', artefakt=str(self.kanit), test_sayisi='0')
        rc, k, _ = _karne_json(self.defter)
        self.assertEqual(rc, 2, f'metin `test_sayisi` şema ihlalidir: {k}')
        self.assertTrue(k['satirlar'][0]['gecersiz'])

    def test_test_sayisi_yoksa_dusurulmez(self):
        # null = "bu kapı test saymaz" (ör. bir lint kapısı); 0 = "test koştu, sıfır test vardı".
        self.satir_ekle(sonuc='pass', artefakt=str(self.kanit), test_sayisi=None)
        _, k, _ = _karne_json(self.defter)
        self.assertEqual(k['satirlar'][0]['etkin'], 'pass')


class D4DarKapsamWarnTests(DefterTestTemeli):
    def test_dar_kapsam_pass_olamaz(self):
        self.satir_ekle(kapi='sap:adt_atc_check', sonuc='pass', artefakt=str(self.kanit),
                        dar_kapsam=True, kapsam='varsayılan ATC varyantı')
        rc, k, _ = _karne_json(self.defter)
        satir = k['satirlar'][0]
        self.assertEqual(satir['etkin'], 'warn')
        self.assertTrue(any('kapsam daraltılmış' in n for n in satir['notlar']), satir['notlar'])
        self.assertEqual(rc, 0)

    def test_kontrol_grubu_tam_kapsam_pass_kalir(self):
        self.satir_ekle(kapi='sap:adt_atc_check', sonuc='pass', artefakt=str(self.kanit),
                        dar_kapsam=False, kapsam='proje ATC varyantı, 12 obje')
        _, k, _ = _karne_json(self.defter)
        self.assertEqual(k['satirlar'][0]['etkin'], 'pass')

    def test_kaydet_dar_kapsam_bayragini_yazar(self):
        rc, out, err = self.kaydet('--kapi', 'sap:adt_atc_check', '--sonuc', 'pass',
                                   '--artefakt', str(self.kanit), '--kapsam', 'varsayılan varyant',
                                   '--dar-kapsam')
        self.assertEqual(rc, 0, err)
        kayit = json.loads(self.defter.read_text(encoding='utf-8').splitlines()[0])
        self.assertTrue(kayit['dar_kapsam'])


class D5BosKapsamBeyaniTests(DefterTestTemeli):
    def test_bos_kapsam_karnede_gorunur(self):
        self.satir_ekle(sonuc='pass', artefakt=str(self.kanit), kapsam='')
        rc, k, _ = _karne_json(self.defter)
        self.assertEqual(k['kapsam_beyani_bos'], 1)
        self.assertNotEqual(k['hukum'], 'PASS', 'boş kapsam beyanı sessizce PASS olamaz')
        self.assertEqual(rc, 0)

    def test_kontrol_grubu_dolu_kapsam_uyari_uretmez(self):
        self.satir_ekle(sonuc='pass', artefakt=str(self.kanit), kapsam='3 sınıf, 1 CDS; canlı SAP HARİÇ')
        _, k, _ = _karne_json(self.defter)
        self.assertEqual(k['kapsam_beyani_bos'], 0)
        self.assertEqual(k['satirlar'][0]['notlar'], [], 'dolu kapsam not üretmemeli')
        # KISMI sözleşmesi nedeniyle bütün hüküm `KISMI` olabilir; çivilenen şey WARN OLMAMASIDIR.
        self.assertNotEqual(k['hukum'], 'WARN')


class D6OkumaAnindaDogrulamaTests(DefterTestTemeli):
    def test_elle_eklenen_artefaktsiz_pass_yakalanir(self):
        # Kapı yolundan (kaydet) GEÇMEDEN elle eklenmiş satır — arka durak.
        with open(self.defter, 'a', encoding='utf-8') as f:
            f.write('{"ts":"2026-09-15T00:00:00+00:00","kapi":"validator:check_abaplint",'
                    '"sonuc":"pass","kapsam":"elle eklendi"}\n')
        rc, k, _ = _karne_json(self.defter)
        self.assertEqual(rc, 2, f'elle eklenmiş artefaktsız pass da yakalanmalı: {k}')

    def test_bozuk_satir_guvenilmez(self):
        self.defter.write_text('bu JSON değil\n', encoding='utf-8')
        rc, k, _ = _karne_json(self.defter)
        self.assertEqual(rc, 2)
        self.assertEqual(k['bozuk_satir_sayisi'], 1)

    def test_taninmayan_sonuc_degeri_guvenilmez(self):
        self.satir_ekle(sonuc='yesil', artefakt=str(self.kanit))
        rc, k, _ = _karne_json(self.defter)
        self.assertEqual(rc, 2, f'sözleşme dışı sonuç değeri güvenilmezdir: {k}')

    def test_kaydet_artefaktsiz_passi_da_bildirir(self):
        rc, out, err = self.kaydet('--kapi', 'validator:check_abaplint', '--sonuc', 'pass',
                                   '--kapsam', 'x')
        self.assertEqual(rc, 2, 'yazma anında da uyarır (satır YİNE de deftere düşer)')
        self.assertEqual(len(self.defter.read_text(encoding='utf-8').splitlines()), 1,
                         'defter bir OLAY kaydıdır: reddedilen iddia da yazılır')


class AppendOnlyTests(DefterTestTemeli):
    def test_ikinci_kayit_ilkini_degistirmez(self):
        self.kaydet('--kapi', 'validator:check_abaplint', '--sonuc', 'fail', '--kapsam', 'ilk')
        ilk = self.defter.read_text(encoding='utf-8').splitlines()[0]
        self.kaydet('--kapi', 'validator:check_bdef_backtick', '--sonuc', 'not-run', '--kapsam', 'ikinci')
        satirlar = self.defter.read_text(encoding='utf-8').splitlines()
        self.assertEqual(len(satirlar), 2)
        self.assertEqual(satirlar[0], ilk, 'ilk satır BİT-BAZINDA değişmemeli')

    def test_karne_deftere_yazmaz(self):
        self.satir_ekle(sonuc='pass', artefakt=str(self.kanit))
        once = hashlib.sha256(self.defter.read_bytes()).hexdigest()
        _karne_json(self.defter)
        self.assertEqual(hashlib.sha256(self.defter.read_bytes()).hexdigest(), once)

    def test_kaynakta_defteri_ezen_kip_yok(self):
        kaynak = SCRIPT.read_text(encoding='utf-8')
        kipler = set(re.findall(r'open\([^)]*?["\'](r?[wxa]\+?b?)["\']', kaynak))
        self.assertFalse({'w', 'w+', 'x', 'wb'} & kipler,
                         f'defter yalnız "a" kipiyle açılmalı; bulunan kipler: {sorted(kipler)}')


class MeasuredSozlesmesiTests(DefterTestTemeli):
    """`AXET-GATE-STATUS` ÜRETİCİSİ gerçek modülden çağrılır — paralel bir sözleşme icat edilmez."""

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('gate_status_under_test', GATE_STATUS)
        cls.gs = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.gs)

    def _uretici_satiri(self, gate, status, measured, reason):
        import io
        from contextlib import redirect_stdout
        tampon = io.StringIO()
        with redirect_stdout(tampon):
            self.gs.gate_status(gate, status, measured, reason)
        return tampon.getvalue()

    def test_measured_false_pass_olamaz(self):
        ciktı = self.tmp / 'gate.out'
        ciktı.write_text('bulgu yok\n' + self._uretici_satiri(
            'check_abaplint', 'SKIPPED', False, 'npx yok'), encoding='utf-8')
        rc, out, err = self.kaydet('--kapi', 'validator:check_abaplint', '--sonuc', 'pass',
                                   '--artefakt', str(self.kanit), '--kapsam', 'tek sınıf',
                                   '--durum-ciktisi', str(ciktı))
        self.assertEqual(rc, 0, err)
        kayit = json.loads(self.defter.read_text(encoding='utf-8').splitlines()[0])
        self.assertIs(kayit['measured'], False)
        self.assertEqual(kayit['measured_reason'], 'npx-yok')
        _, k, _ = _karne_json(self.defter)
        self.assertEqual(k['satirlar'][0]['etkin'], 'not-run',
                         'measured=false "temiz" DEĞİLDİR (run_review ile aynı hüküm)')

    def test_kontrol_grubu_measured_true_pass_kalir(self):
        ciktı = self.tmp / 'gate.out'
        ciktı.write_text(self._uretici_satiri('check_abaplint', 'OK', True, 'temiz'), encoding='utf-8')
        self.kaydet('--kapi', 'validator:check_abaplint', '--sonuc', 'pass',
                    '--artefakt', str(self.kanit), '--kapsam', 'tek sınıf', '--test-sayisi', '3',
                    '--durum-ciktisi', str(ciktı))
        _, k, _ = _karne_json(self.defter)
        self.assertIs(k['satirlar'][0]['measured'], True)
        self.assertEqual(k['satirlar'][0]['etkin'], 'pass')

    def test_bicimi_bozuk_axet_satiri_olculmemis_sayilir(self):
        ciktı = self.tmp / 'gate.out'
        ciktı.write_text('AXET-GATE-STATUS: gate=check_abaplint status=OK measured=maybe reason=x\n',
                         encoding='utf-8')
        self.kaydet('--kapi', 'validator:check_abaplint', '--sonuc', 'pass',
                    '--artefakt', str(self.kanit), '--kapsam', 'x', '--durum-ciktisi', str(ciktı))
        kayit = json.loads(self.defter.read_text(encoding='utf-8').splitlines()[0])
        self.assertIs(kayit['measured'], False)
        self.assertEqual(kayit['measured_reason'], 'bicim-bozuk')

    def test_beyan_yoksa_measured_null(self):
        ciktı = self.tmp / 'gate.out'
        ciktı.write_text('hiçbir sözleşme satırı yok\n', encoding='utf-8')
        self.kaydet('--kapi', 'validator:check_abaplint', '--sonuc', 'pass',
                    '--artefakt', str(self.kanit), '--kapsam', 'x', '--durum-ciktisi', str(ciktı))
        kayit = json.loads(self.defter.read_text(encoding='utf-8').splitlines()[0])
        self.assertIsNone(kayit['measured'], 'beyan yoksa "ölçülmedi" DİYE VARSAYILMAZ, null kalır')

    def test_v1_cok_beyanli_cikti_kendi_gate_satirini_secer(self):
        """V1: kendi gate'i measured=false, BASKA bir gate'in satiri measured=true ve SONDA.

        `run_review.gate_durum_beyani` burada `false` der (`gate=` suzgeci). Suzgec olmadan `true`
        okunur ve `pass` sessizce ayakta kalir - ayrisma false-green yonundedir.
        """
        cikti = self.tmp / 'gate.out'
        cikti.write_text(self._uretici_satiri('check_abaplint', 'SKIPPED', False, 'npx yok')
                         + self._uretici_satiri('check_released_objects', 'OK', True, 'temiz'),
                         encoding='utf-8')
        self.kaydet('--kapi', 'validator:check_abaplint', '--sonuc', 'pass',
                    '--artefakt', str(self.kanit), '--kapsam', 'tek sinif',
                    '--durum-ciktisi', str(cikti))
        kayit = json.loads(self.defter.read_text(encoding='utf-8').splitlines()[0])
        self.assertIs(kayit['measured'], False, 'kendi gate satiri (check_abaplint) secilmeli')
        self.assertEqual(kayit['measured_reason'], 'npx-yok')
        _, k, _ = _karne_json(self.defter)
        self.assertEqual(k['satirlar'][0]['etkin'], 'not-run')

    def test_v1_esleseni_yoksa_son_beyana_duser(self):
        # Kontrol grubu: run_review'in ikinci dali - `gate=` eslesmesi YOKSA SON beyan alinir.
        cikti = self.tmp / 'gate.out'
        cikti.write_text(self._uretici_satiri('check_x', 'OK', True, 'temiz')
                         + self._uretici_satiri('check_y', 'SKIPPED', False, 'baglanti yok'),
                         encoding='utf-8')
        self.kaydet('--kapi', 'validator:check_abaplint', '--sonuc', 'pass',
                    '--artefakt', str(self.kanit), '--kapsam', 'x', '--durum-ciktisi', str(cikti))
        kayit = json.loads(self.defter.read_text(encoding='utf-8').splitlines()[0])
        self.assertIs(kayit['measured'], False)

    def test_v2_yabanci_onek_abaplint_satirini_yener(self):
        """V2: taninmayan `<X>-GATE-STATUS:` + `ABAPLINT-RUN-STATUS ... measured=true`.

        `run_review` yabanci oneki fail-closed okur (`measured=false`). ABAPLINT dali yabanci-onek
        kontrolunden ONCE kosarsa `true` cikar - bayat/yabanci bir gate kopyasi kendi
        `measured=false`'unu gizler.
        """
        cikti = self.tmp / 'gate.out'
        cikti.write_text('NDBS-GATE-STATUS: gate=check_abaplint status=SKIPPED measured=false reason=x\n'
                         'ABAPLINT-RUN-STATUS: status=ok measured=true reason=temiz '
                         'files_measured=2 files_unmeasured=0 issues=0\n', encoding='utf-8')
        self.kaydet('--kapi', 'validator:check_abaplint', '--sonuc', 'pass',
                    '--artefakt', str(self.kanit), '--kapsam', 'x', '--durum-ciktisi', str(cikti))
        kayit = json.loads(self.defter.read_text(encoding='utf-8').splitlines()[0])
        self.assertIs(kayit['measured'], False, 'yabanci onek ABAPLINT dalini YENMELI (fail-closed)')
        self.assertTrue(str(kayit['measured_reason']).startswith('taninmayan-onek-'),
                        kayit['measured_reason'])

    def test_gate_bayragi_kapi_adindan_turetilir_ve_ezilebilir(self):
        cikti = self.tmp / 'gate.out'
        cikti.write_text(self._uretici_satiri('check_abaplint', 'SKIPPED', False, 'npx yok')
                         + self._uretici_satiri('check_released_objects', 'OK', True, 'temiz'),
                         encoding='utf-8')
        self.kaydet('--kapi', 'validator:check_abaplint', '--sonuc', 'pass', '--gate',
                    'check_released_objects', '--artefakt', str(self.kanit), '--kapsam', 'x',
                    '--durum-ciktisi', str(cikti))
        kayit = json.loads(self.defter.read_text(encoding='utf-8').splitlines()[0])
        self.assertIs(kayit['measured'], True, "--gate acikca verilince o gate'in satiri okunur")

    def test_uretici_dosyalari_hala_bu_onekleri_basiyor(self):
        # Kod ≠ kablolama: ayrıştırıcının dayandığı iki üreticinin hâlâ bu satırları bastığı ÖLÇÜLÜR.
        self.assertIn('AXET-GATE-STATUS:', GATE_STATUS.read_text(encoding='utf-8'))
        self.assertIn('ABAPLINT-RUN-STATUS:', ABAPLINT_RUN.read_text(encoding='utf-8'))

    def test_abaplint_run_durum_satiri_da_okunur(self):
        ciktı = self.tmp / 'lint.out'
        ciktı.write_text('ABAPLINT-RUN-STATUS: status=unmeasured measured=false reason=npx-yok '
                         'files_measured=0 files_unmeasured=3 issues=0\n', encoding='utf-8')
        self.kaydet('--kapi', 'validator:check_abaplint', '--sonuc', 'pass',
                    '--artefakt', str(self.kanit), '--kapsam', 'x', '--durum-ciktisi', str(ciktı))
        kayit = json.loads(self.defter.read_text(encoding='utf-8').splitlines()[0])
        self.assertIs(kayit['measured'], False)


class KapiKayitDefteriTests(DefterTestTemeli):
    """Kapı adları KODDAN türetilir — elle tutulan liste yok (bayatlar, sahte güven üretir)."""

    def test_kapilar_koddan_turetilir(self):
        rc, out, err = _cli('kapilar', '--json')
        self.assertEqual(rc, 0, err)
        kap = json.loads(out)
        adlar = set(kap['kapilar'])
        self.assertIn('review:class_push', adlar, 'run_review TASK_VALIDATORS anahtarları')
        self.assertIn('validator:check_abaplint', adlar, 'gerçek check_*.py dosyaları')
        self.assertIn('sap:adt_atc_check', adlar, 'araç kataloğundaki adt_* araçları')
        self.assertIn('test:skills-sap/sap-code-review/tests', adlar, 'gerçek test takımları')
        self.assertNotIn('review:asla_olmayan_gorev', adlar)

    def test_adt_syntax_check_yazma_sinifi_isaretlenir(self):
        _, out, _ = _cli('kapilar', '--json')
        kap = json.loads(out)
        self.assertEqual(kap['kapilar']['sap:adt_syntax_check']['sinif'], 'yazma',
                         'bizde adt_syntax_check SAP\'ye YAZAR — ücretsiz ön kontrol değildir')
        self.assertEqual(kap['kapilar']['sap:adt_atc_check']['sinif'], 'okuma')

    def test_yazma_sinifi_kapi_karnede_isaretlenir(self):
        self.satir_ekle(kapi='sap:adt_syntax_check', sonuc='pass', artefakt=str(self.kanit),
                        kapsam='tek sınıf', test_sayisi=None)
        _, k, _ = _karne_json(self.defter)
        self.assertIn('sap:adt_syntax_check', k['yazma_sinifi_kapi'])

    def test_kayit_defteri_olculemezse_sessiz_kalmaz(self):
        # Kontrol grubu: kaynaklar YOKKEN (boş kök) kayıt defteri boş DÖNMEZ, "ÖLÇÜLEMEDİ" der ve
        # hiçbir kapı adını haksız yere "bilinmeyen" ilan etmez (ölçülemedi ≠ temiz, ölçülemedi ≠ yanlış).
        bos_kok = self.tmp / 'bos-kok'
        bos_kok.mkdir()
        self.satir_ekle(kapi='validator:check_abaplint', sonuc='pass', artefakt=str(self.kanit))
        rc, k, _ = _karne_json(self.defter, '--kok', str(bos_kok))
        self.assertEqual(len(k['kapilar']['olculemedi']), 4, k['kapilar']['olculemedi'])
        self.assertEqual(k['bilinmeyen_kapi'], [], 'ölçülemeyen namespace "bilinmeyen" üretmez')
        self.assertNotEqual(k['hukum'], 'PASS', 'kapsamı ölçülemeyen bir karne PASS diyemez')
        rc2, out, _ = _cli('karne', '--defter', str(self.defter), '--kok', str(bos_kok))
        self.assertIn('ÖLÇÜLEMEDİ', out)

    def test_bilinmeyen_kapi_adi_karnede_gorunur(self):
        self.satir_ekle(kapi='validator:check_olmayan_kapi', sonuc='pass', artefakt=str(self.kanit))
        _, k, _ = _karne_json(self.defter)
        self.assertIn('validator:check_olmayan_kapi', k['bilinmeyen_kapi'])
        self.assertNotEqual(k['hukum'], 'PASS')

    def test_kaydedilmemis_kapilar_kapsam_olarak_raporlanir(self):
        self.satir_ekle(kapi='validator:check_abaplint', sonuc='pass', artefakt=str(self.kanit))
        _, k, _ = _karne_json(self.defter)
        self.assertGreater(k['kapilar']['bilinen'], 20)
        self.assertEqual(k['kapilar']['defterde'], 1)
        self.assertIn('validator:check_bdef_backtick', k['kapilar']['kaydedilmemis'])


class KapsamBeyaniVeHukumTests(DefterTestTemeli):
    def test_sifir_bulguda_da_kapsam_beyani_basilir(self):
        self.satir_ekle(sonuc='pass', artefakt=str(self.kanit), test_sayisi=2)
        rc, out, err = _cli('karne', '--defter', str(self.defter))
        self.assertEqual(rc, 0, err)
        metin = out.upper()
        self.assertIn('KAPSAM', metin)
        self.assertIn('BAKILMAYAN', metin, '"0 bulgu" ≠ "doğru": neye BAKILMADIĞI her koşumda yazılır')

    def test_bakilanlar_kurallardan_turetilir(self):
        # `bakilanlar` elle yazilirsa bayatlar: kural sayisi ile beyan sayisi ESIT olmali.
        self.satir_ekle(sonuc='pass', artefakt=str(self.kanit), test_sayisi=1)
        _, k, _ = _karne_json(self.defter)
        kaynak = SCRIPT.read_text(encoding='utf-8')
        kural_sayisi = len(re.findall(r'^\s+\("[a-z-]+", ".*", _kural_\w+\),$', kaynak, re.M))
        self.assertGreaterEqual(kural_sayisi, 6)
        self.assertEqual(len(k['kapsam_beyani']['bakilanlar']), kural_sayisi,
                         'KAPSAM BEYANI "bakilanlar" kural tablosundan turetilmeli')

    def test_defter_yoksa_karne_uretilemez(self):
        rc, out, err = _cli('karne', '--defter', str(self.tmp / 'yok.jsonl'))
        self.assertEqual(rc, 2, 'defter yoksa "temiz" değil, "karne üretilemedi"')

    def test_bos_defter_pass_degildir(self):
        self.defter.write_text('', encoding='utf-8')
        rc, k, _ = _karne_json(self.defter)
        self.assertEqual(k['hukum'], 'OLCULMEDI')
        self.assertNotEqual(k['hukum'], 'PASS')

    def test_fail_satiri_cikis_1(self):
        self.satir_ekle(sonuc='fail', artefakt=str(self.kanit), kapsam='1 sınıf')
        rc, k, _ = _karne_json(self.defter)
        self.assertEqual(rc, 1)
        self.assertEqual(k['hukum'], 'FAIL')

    def test_guvenilmezlik_faili_ezer(self):
        self.satir_ekle(sonuc='fail', artefakt=str(self.kanit), kapsam='x')
        self.satir_ekle(sonuc='pass', artefakt=None, kapsam='x')
        rc, k, _ = _karne_json(self.defter)
        self.assertEqual(rc, 2, 'güvenilmez karne, FAIL hükmünden önce gelir')


class H2EszamanliYazimTests(DefterTestTemeli):
    """Kilit MEKANIZMASI civilenir, istatistiksel yaris DEGIL.

    Kayip orani olasiliksaldir (olculdu: 6x25'te 6/6 kosumda kayip, 6x10'da 3/3 kosumda kayip YOK)
    => takima konan bir yaris testi KOR olurdu. Civilenen degismez: kilit alinamiyorsa yazma
    YAPILMAZ ve cagri rc!=0 ile DURUR - sessiz devam yok. Kayip orani takim DISI duzenekle olculur.
    """

    def test_kilit_dosyasi_defterin_yaninda_yaratilir(self):
        self.kaydet('--kapi', 'validator:check_abaplint', '--sonuc', 'not-run', '--kapsam', 'x')
        self.assertTrue((self.defter.parent / (self.defter.name + '.lock')).exists(),
                        'kilit dosyasi yaratilmali (harici arac da ayni kilidi alabilsin)')

    def test_kilit_alinamazsa_yazma_yok_ve_rc_sifir_degil(self):
        import msvcrt
        kilit = self.defter.parent / (self.defter.name + '.lock')
        kilit.parent.mkdir(parents=True, exist_ok=True)
        with open(kilit, 'a+b') as lf:
            lf.seek(0)
            msvcrt.locking(lf.fileno(), msvcrt.LK_NBLCK, 1)
            try:
                rc, out, err = self.kaydet('--kapi', 'validator:check_abaplint', '--sonuc', 'pass',
                                           '--artefakt', str(self.kanit), '--kapsam', 'x',
                                           '--kilit-saniye', '1')
            finally:
                lf.seek(0)
                msvcrt.locking(lf.fileno(), msvcrt.LK_UNLCK, 1)
        self.assertEqual(rc, 3, 'kilit alinamadi: ayri ve sessiz olmayan bir cikis kodu (3)')
        mesaj = (out + err).lower()
        self.assertTrue('kilid' in mesaj or 'kilit' in mesaj, mesaj)
        self.assertIn('.lock', mesaj, 'mesaj hangi kilidin alinamadigini SOYLEMELI')
        icerik = self.defter.read_text(encoding='utf-8') if self.defter.exists() else ''
        self.assertEqual(icerik.strip(), '', 'kilit alinamamisken deftere satir yazilmamali')

    def test_kontrol_grubu_kilit_serbestken_yazar(self):
        rc, out, err = self.kaydet('--kapi', 'validator:check_abaplint', '--sonuc', 'pass',
                                   '--artefakt', str(self.kanit), '--kapsam', 'x',
                                   '--kilit-saniye', '1')
        self.assertEqual(rc, 0, err)
        self.assertEqual(len(self.defter.read_text(encoding='utf-8').splitlines()), 1)


class M1ArtefaktNiteligiTests(DefterTestTemeli):
    def test_dizin_kanit_sayilmaz(self):
        self.satir_ekle(sonuc='pass', artefakt=str(self.tmp), test_sayisi=1)
        rc, k, _ = _karne_json(self.defter)
        self.assertEqual(rc, 2, 'dizin bir kanit DOSYASI degildir')
        self.assertTrue(any('dosya degil' in n.lower() or 'dosya \u011fegil' in n.lower()
                            or 'dosya de' in n.lower() for n in k['satirlar'][0]['notlar']),
                        k['satirlar'][0]['notlar'])

    def test_sifir_bayt_artefakt_warn(self):
        bos = self.tmp / 'bos.txt'
        bos.write_text('', encoding='utf-8')
        self.satir_ekle(sonuc='pass', artefakt=str(bos), test_sayisi=1)
        rc, k, _ = _karne_json(self.defter)
        self.assertEqual(k['satirlar'][0]['etkin'], 'warn', '0 baytlik kanit `pass` tasimaz')
        self.assertTrue(any('0 bayt' in n for n in k['satirlar'][0]['notlar']),
                        k['satirlar'][0]['notlar'])

    def test_kontrol_grubu_dolu_dosya_pass(self):
        self.satir_ekle(sonuc='pass', artefakt=str(self.kanit), test_sayisi=1)
        _, k, _ = _karne_json(self.defter)
        self.assertEqual(k['satirlar'][0]['etkin'], 'pass')


class M2M3SemaKacamaklariTests(DefterTestTemeli):
    def test_negatif_test_sayisi_gecersiz(self):
        self.satir_ekle(sonuc='pass', artefakt=str(self.kanit), test_sayisi=-7)
        rc, k, _ = _karne_json(self.defter)
        self.assertEqual(rc, 2, 'negatif test sayisi D3-u bedelsiz atlatamaz')

    def test_bool_test_sayisi_gecersiz(self):
        # Hayatta kalan mutasyon (1): bool korumasi kalkinca `true` bir test sayisi saniliyordu.
        self.satir_ekle(sonuc='pass', artefakt=str(self.kanit), test_sayisi=True)
        rc, k, _ = _karne_json(self.defter)
        self.assertEqual(rc, 2, '`true` bir test sayisi DEGILDIR')

    def test_ad_kacamagi_yakalanir(self):
        # `dar-kapsam` (tire) yazilirsa D4 sessizce atlaniyordu - ANAHTARLAR artik kablolu.
        with open(self.defter, 'a', encoding='utf-8') as f:
            f.write(json.dumps({'ts': '2026-09-15T00:00:00+00:00', 'kapi': 'sap:adt_atc_check',
                                'sonuc': 'pass', 'artefakt': str(self.kanit),
                                'kapsam': 'varsayilan varyant', 'dar-kapsam': True},
                               ensure_ascii=False) + '\n')
        rc, k, _ = _karne_json(self.defter)
        self.assertEqual(rc, 2, 'taninmayan alan adi sema ihlalidir')
        self.assertTrue(any('dar-kapsam' in n for n in k['satirlar'][0]['notlar']),
                        k['satirlar'][0]['notlar'])

    def test_kontrol_grubu_dogru_ad_warn_uretir(self):
        self.satir_ekle(kapi='sap:adt_atc_check', sonuc='pass', artefakt=str(self.kanit),
                        dar_kapsam=True, kapsam='varsayilan varyant')
        _, k, _ = _karne_json(self.defter)
        self.assertEqual(k['satirlar'][0]['etkin'], 'warn')


class KuralSirasiTests(DefterTestTemeli):
    def test_artefakt_kurali_measured_kuralindan_once_kosar(self):
        # Hayatta kalan mutasyon (2): sira ters cevrilince `pass`+measured=false+artefaktsiz satir
        # `not-run`'a dusuyor ve D2 (cikis 2) TAMAMEN baypas ediliyordu.
        self.satir_ekle(sonuc='pass', artefakt=None, measured=False, measured_reason='baglanti-yok')
        rc, k, _ = _karne_json(self.defter)
        self.assertEqual(rc, 2, 'artefaktsizlik measured dusurmesiyle ortulemez')
        self.assertTrue(k['satirlar'][0]['gecersiz'])

    def test_warn_satiri_da_measured_false_ile_not_run_olur(self):
        # Hayatta kalan mutasyon (3): `etkin in ("pass","warn")` -> `== "pass"` yapilinca `warn`
        # satiri `warn` kaliyordu; olcum uretmeyen bir kapi `warn` bile diyemez.
        self.satir_ekle(sonuc='warn', artefakt=None, kapsam='x', measured=False,
                        measured_reason='arac-yok')
        _, k, _ = _karne_json(self.defter)
        self.assertEqual(k['satirlar'][0]['etkin'], 'not-run')


class M4KosumKapsamiTests(DefterTestTemeli):
    def test_kosum_kimligi_satira_yazilir(self):
        self.kaydet('--kapi', 'validator:check_abaplint', '--sonuc', 'not-run', '--kapsam', 'x',
                    '--kosum', 'KOSUM-A')
        kayit = json.loads(self.defter.read_text(encoding='utf-8').splitlines()[0])
        self.assertEqual(kayit['kosum'], 'KOSUM-A')

    def test_kosum_verilmezse_uretilir(self):
        self.kaydet('--kapi', 'validator:check_abaplint', '--sonuc', 'not-run', '--kapsam', 'x')
        kayit = json.loads(self.defter.read_text(encoding='utf-8').splitlines()[0])
        self.assertTrue(kayit.get('kosum'), 'kosum kimligi bos birakilmamali')

    def test_kosum_suzgeci_eski_faili_saymaz(self):
        self.satir_ekle(sonuc='fail', artefakt=str(self.kanit), kapsam='eski', kosum='ESKI')
        self.satir_ekle(sonuc='pass', artefakt=str(self.kanit), kapsam='yeni', test_sayisi=3,
                        kosum='YENI')
        rc, k, _ = _karne_json(self.defter, '--kosum', 'YENI')
        self.assertEqual(k['sayim']['fail'], 0, 'suzgec eski kosumun failini saymamali')
        self.assertEqual(k['okunan_satir'], 1)
        self.assertEqual(k['toplam_satir'], 2)
        self.assertNotEqual(k['hukum'], 'FAIL')

    def test_kontrol_grubu_bayraksiz_karne_tum_defteri_okur(self):
        # Bu kontrol olmadan "suzgeci HEP uygula" diyen bir duzeltme de gecerdi.
        self.satir_ekle(sonuc='fail', artefakt=str(self.kanit), kapsam='eski', kosum='ESKI')
        self.satir_ekle(sonuc='pass', artefakt=str(self.kanit), kapsam='yeni', test_sayisi=3,
                        kosum='YENI')
        rc, k, _ = _karne_json(self.defter)
        self.assertEqual(k['sayim']['fail'], 1, 'bayraksiz karne TUM defteri okur (varsayilan degismez)')
        self.assertEqual(k['hukum'], 'FAIL')
        self.assertEqual(rc, 1)

    def test_since_suzgeci(self):
        self.satir_ekle(sonuc='fail', artefakt=str(self.kanit), kapsam='eski',
                        ts='2026-09-01T00:00:00+00:00')
        self.satir_ekle(sonuc='pass', artefakt=str(self.kanit), kapsam='yeni', test_sayisi=1,
                        ts='2026-09-15T00:00:00+00:00')
        _, k, _ = _karne_json(self.defter, '--since', '2026-09-10')
        self.assertEqual(k['okunan_satir'], 1)
        self.assertEqual(k['sayim']['fail'], 0)

    def test_kapsam_satiri_ciktida_ve_jsonda(self):
        self.satir_ekle(sonuc='pass', artefakt=str(self.kanit), test_sayisi=1, kosum='K1')
        _, k, _ = _karne_json(self.defter, '--kosum', 'K1')
        self.assertEqual(k['kapsam_suzgeci']['kosum'], 'K1')
        rc, out, err = _cli('karne', '--defter', str(self.defter), '--kosum', 'K1')
        self.assertIn('kosum=K1', out)
        rc2, out2, _ = _cli('karne', '--defter', str(self.defter))
        self.assertIn('TUM DEFTER', out2.upper().replace('\u00dc', 'U'))


class KismiHukumTests(DefterTestTemeli):
    def test_kaydedilmemis_kapi_varken_pass_olmaz(self):
        self.satir_ekle(sonuc='pass', artefakt=str(self.kanit), test_sayisi=3)
        rc, k, _ = _karne_json(self.defter)
        self.assertEqual(k['hukum'], 'KISMI', '90 kapinin 1-i olculduyse bu PASS degildir')
        self.assertEqual(rc, 0, 'eksik kapsam bir basarisizlik DEGILDIR (cikis 0)')
        self.assertGreater(k['olculmemis'], 80)

    def test_kontrol_grubu_tum_kapilar_kayitliysa_pass(self):
        rc0, out, _ = _cli('kapilar', '--json')
        kapilar = sorted(json.loads(out)['kapilar'])
        for ad in kapilar:
            self.satir_ekle(kapi=ad, sonuc='pass', artefakt=str(self.kanit), test_sayisi=1,
                            kapsam='tam kapsam')
        rc, k, _ = _karne_json(self.defter)
        self.assertEqual(k['olculmemis'], 0)
        self.assertEqual(k['hukum'], 'PASS', 'tum kapilar kayitli ve pass ise hukum PASS')
        self.assertEqual(rc, 0)

    def test_fail_kismiyi_ezer(self):
        self.satir_ekle(sonuc='fail', artefakt=str(self.kanit), kapsam='x')
        rc, k, _ = _karne_json(self.defter)
        self.assertEqual(k['hukum'], 'FAIL')
        self.assertEqual(rc, 1)


class GateDegilRaporTests(unittest.TestCase):
    """⛔ Bu araç bir GATE DEĞİLDİR: hiçbir mevcut akış onu çağırmamalı (ADR 0019 moratoryumu)."""

    def test_hicbir_akis_karneyi_cagirmiyor(self):
        # KAPSAM: bu repoda komut kablolamasi YALNIZ .py uzerinden yapilmiyor - CI is akisi (.yml)
        # ve mimari haritasinin `test.komut` dizeleri de fiilen komut calistirir. Tarama uc yuzeyi
        # de kapsar; dar kume uzerinden "hicbir akis cagirmiyor" genellemesi yapilamaz.
        # BAKILMAYAN (bilincli): `.md` talimat yuzeyi. Bir markdown satiri mekanik olarak hicbir
        # seyi bloklayamaz ve SKILL.md bu script'i calistirmayi zaten tarif eder. Bu test
        # "bloklayici kablolama" arar, "anilma" degil - negatif testle olculdu 2026-09-16:
        # tuzak .yml -> KIRMIZI, tuzak harita.json -> KIRMIZI, tuzak .md -> YESIL (beklenen).
        yuzeyler = (list(TEMPLATE.rglob('*.py')) + list(TEMPLATE.rglob('*.yml'))
                    + list(TEMPLATE.rglob('*.yaml')) + [TEMPLATE / 'guncelle' / 'harita.json'])
        cagiranlar = []
        for p in yuzeyler:
            if not p.is_file() or '__pycache__' in p.parts or '.git' in p.parts:
                continue
            if p == SCRIPT or p.name == Path(__file__).name:
                continue
            if 'quality_scorecard' in p.read_text(encoding='utf-8', errors='replace'):
                cagiranlar.append(p.relative_to(TEMPLATE).as_posix())
        self.assertEqual(cagiranlar, [], f'karne bloklayıcı olarak kablolanmış: {cagiranlar}')

    def test_taranan_yuzeyler_gercekten_var(self):
        # Kontrol grubu: tarama bos kumede kosup "temiz" demesin (yuzeylerin varligi olculur).
        self.assertTrue((TEMPLATE / '.github' / 'workflows' / 'testler.yml').is_file())
        self.assertTrue((TEMPLATE / 'guncelle' / 'harita.json').is_file())

    def test_yazma_kapisi_ve_reviewer_dokunulmadi(self):
        for p in (RUN_REVIEW, GATE_PY):
            self.assertNotIn('quality_scorecard', p.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
