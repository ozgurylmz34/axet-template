# V4t — iki taraf da değişmiş, git temiz birleştirdi

**Tek cümle:** Sen de biz de bu dosyayı değiştirmişiz; satırlar çakışmadı, ama karar yine senin.

## Ne demek
Taban, yerel ve yeni üç ayrı içerik. `git merge-file` üçünü birleştirdi ve çakışma işareti
üretmedi. Öneri dosyası hazır; ama otomatik uygulanmaz.

## Neden
Temiz birleşme "doğru birleşme" demek DEĞİLDİR: iki değişiklik ayrı satırlarda olup anlamca
birbirini bozabilir. Bu yüzden karar kullanıcınındır.

**Kalibrasyon (ölçüldü 2026-09-17):** git BİTİŞİK satır değişikliklerini de çakışma sayar —
4. satırı biz, 5. satırı sen değiştirdiysek sonuç V4t değil **V4c**'dir. Yani V4t pratikte
beklenenden NADİRDİR; çoğu iki-taraflı değişiklik V4c olarak gelir. Kullanıcıya "çakışma çıktı"
derken bunu ekle: çakışma işareti kusur değil, git'in ihtiyat payıdır.

## Adımlar
1. `guncelle.py oneri <yol>` → birleşik öneri `.axet-guncelleme/oneri/<yol>` altına yazılır,
   ekrana iki fark basılır (T→L "senin değişikliğin", T→Y "bizim değişikliğimiz").
2. İki farkı kullanıcıya AYRI AYRI, birer cümleyle özetle: "senin değişikliğin: … · bizim
   değişikliğimiz: …".
3. Sor: "birleşik hâli uygula / yereli koru / yeniyi al".
4. Cevaba göre: `guncelle.py isaretle <yol> --karar birlesik|yerel|yeni`.

## Örnek
`skills-sap/sap-dev/references/naming.md` — sen kendi önekini eklemişsin, biz yeni bir kural
eklemişiz; ikisi de kalmalı.

## Beklenen çıktı
`oneri` çıkışı 0 (çakışma yok) · `İŞARETLENDİ: <yol> → birlesik (dogrulandi)`.

## DUR
Kullanıcı cevap vermeden `isaretle` çalıştırma. Dosyanın sınıfı `validator` ya da `kritik_yol` ise
akışın 11. adımı (hüküm karşılaştırması) ZORUNLUDUR ve şöyle ÖLÇÜLÜR:
   Kontrol grubu kur: **aynı girdi, önce ve sonra.**
   - **Fixture'ı olan validator:** fixture takımı (`python skills-sap/sap-adt-foundation/tests/run_tests.py -k validator_fixtures`)
     uzundur ve güncelleme içinde KOŞULMAZ (Z162): takım adım 10'da test borcuna yazılır, her
     validator için `bad` → FAIL / `good` → PASS kapanıştan sonra `%testler` ile ölçülür. Güncelleme
     İÇİNDEKİ hüküm karşılaştırmasını bu dosya için de aşağıdaki fixture'sız yöntemle yap.
   - **Fixture'ı olmayan validator:** taban sürümünü `git show <taban>:<yol>` ile geçici bir dosyaya
     al; iki sürümü de AYNI örnek proje kökünde koş. Ortam değişkenini PowerShell'de AYRI
     SATIR olarak ver — `$env:AXET_SAP_PROJECT_DIR = '<kök>'`, sonra `python <validator yolu>`.
     (Ölçüldü 2026-09-18: POSIX öneki *AXET_SAP_PROJECT_DIR=<kök> python …* bu evde birincil
     kabuk olan PowerShell'de koşMAZ — *The term 'AXET_SAP_PROJECT_DIR=…' is not recognized*.)
     Çıkış kodunu ve `[İHLAL]` satırlarını karşılaştır.
   - **Zincir dosyası** (`run_review.py`, `_reviewer.py`, `gate.py`): aynı örnek dosyayla
     `python skills-sap/sap-adt-foundation/scripts/sapadt/lib/validators/run_review.py --task <görev> --artifact <örnek> --cevrimdisi --json`
     komutunu önce ve sonra koş; hükmü (PASS / WARNING / BLOCKER) karşılaştır.
   Fark çıkarsa SEBEBİNİ açıkla; açıklayamıyorsan DUR — "karşılaştırdım, fark yok" tek başına ölçüm değildir.

## Geri alma
Bir şey ters giderse: `guncelle.py geri-al <yol>` o dosyayı güncelleme öncesi hâline döndürür
(`hazirla` adımında atılan `guncelle-oncesi-<tarih>` etiketi). Hepsini birden geri almak için
`guncelle.py geri-al --hepsi`. Durum kaydı `geri_alindi` olur; kapanış bunu görür.
