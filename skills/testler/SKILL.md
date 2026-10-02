---
name: testler
description: >
  Runs the aXet template's own test suites on demand, separately from the update. %guncelle never
  runs long test suites; when CI cannot vouch for the clone's tree it records the affected suites as
  a test debt. Use this to pay that debt, to run one named suite, or all suites, and to get a fix
  plan for any red result (source file and release item, plus four options the user chooses from).
  Triggers: "testler", "%testler", "test borcu", "testleri kos", "test borcunu kapat",
  "doctor test borcu diyor", "run the tests", "pay the test debt".
  Do not use to test the user's own skills or project code (not covered), and do not run it in the
  middle of %guncelle (the update never runs suites; run this after it closes).
---

# `%testler` — template test takımlarını isteğe bağlı koş

> `%guncelle` uzun test takımı koşmaz (Z162). CI'nın kefil olamadığı ağaçta koşulmayan takımlar
> `<AXET_HOME>/.axet-guncelleme/test-borcu.json`a yazılır; `doctor.py` borç sürdükçe
> `WARN test borcu: N takım — %testler` basar. Bu skill o borcu öder.
> `<AXET_HOME>` = bu skill klasörünün iki üstü (`<AXET_HOME>/skills/testler/SKILL.md`) — yolu buradan
> türet, varsayma. Komutlardaki yolları `C:/Users/...` biçiminde yaz (Git Bash `/c/...` biçimi YASAK).

## When to use this skill
- Kullanıcı `%testler` yazdı, ya da doctor / güncelleme raporu "test borcu var" dedi ve kullanıcı koşmak istiyor.
- Kullanıcı belirli bir takımı (`kok`, `sap-adt-foundation` …) ya da tümünü koşmak istiyor.
- **Kullanma:** `%guncelle` akışının İÇİNDE (güncelleme test koşmaz; kapanıştan sonra) · kullanıcının
  kendi skill'lerini/proje kodunu test etmek için (haritada test tanımı yok, kapsam dışı).

## How to use this skill
1. **Önce listele ve süreyi söyle:** `python "<AXET_HOME>/scripts/testler.py" --liste`.
   Borçtaki takımları ve tahmini süreyi kullanıcıya göster. Tam kök takım ve `--hepsi` dakikalar sürer
   (liste tahmini basar); kullanıcı onaylamadan uzun koşumu başlatma.
2. **Koş** (kullanıcının seçtiği biçimde, AYNEN):
   - borç: `python "<AXET_HOME>/scripts/testler.py"`
   - tek takım: `python "<AXET_HOME>/scripts/testler.py" --takim <ad>` (adlar `--liste`'de)
   - tümü: `python "<AXET_HOME>/scripts/testler.py" --hepsi`
   Komut düşük öncelikte koşar ve her takım için `[i/N]` ilerleme satırı basar.
3. **Sonucu AYNEN aktar.** Rapor `<AXET_HOME>/.axet-guncelleme/test-raporu.md` dosyasına da yazılır.
   Çıkış 0 = koşulan her takım yeşil (borç kapandıysa "kapandı (borç yok)") · 1 = kırmızı ya da
   ÖLÇÜLEMEDİ var · 2 = kullanım hatası.
4. **Kırmızı varsa:** raporun "Giderme" bölümü her kırmızı takım için kaynağı (dosya + yayın kalemi)
   ve dört seçeneği yazar. Kullanıcıya bu seçenekleri AYNEN sun ve **seçmesini bekle**:
   ① dosyayı güncelleme öncesine al (`guncelle.py geri-al <yol>`) ·
   ② yerel değişikliği bırak, yayın sürümünü al ·
   ③ klonu yayına sıfırla (`kur.cmd -Sifirla` — kullanıcı kendi terminalinde) ·
   ④ hatayı bildir (`%hata-bildir`, `test-raporu.md` eklenir).
   Seçileni uyguladıktan sonra aynı takımı `--takim <ad>` ile yeniden koş; yeşilse borçtan düşer.

## Rules
- **Kendi başına düzeltme yapma.** Kırmızı, template'in kendi testidir: ya yerel değişiklik bir şeyi
  bozmuştur (①/②/③ ile çözülür) ya da yayının kendi hatasıdır (④). Template kodunu kullanıcı
  makinesinde yamamak klonu yayından saptırır ve bir sonraki güncellemede yargı vakası doğurur.
- Kırmızının kök nedenini tahminle anlatma; raporda yazanı (kırmızı test adları, kaynak dosya) aktar.
- `ÖLÇÜLEMEDİ` yeşil DEĞİLDİR (zaman aşımı, betik yok): borçta kalır, kullanıcıya öyle söyle.
- Testleri `tests/run_tests.py` ya da skill test betiklerini doğrudan çağırarak koşma; borç ve rapor
  yalnız `testler.py` üzerinden güncellenir.
