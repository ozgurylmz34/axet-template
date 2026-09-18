# V4c — çakışmalı birleşme (yargı gerekir)

**Tek cümle:** Sen de biz de aynı yerlere dokunmuşuz; git tek bir doğru cevap üretemedi, birleşmeyi
sen önereceksin, kullanıcı onaylayacak.

## Ne demek
Üç sürüm var: **taban** (en son aldığın hâl), **yerel** (senin değiştirdiğin hâl), **yeni** (bu
yayındaki hâl). Git üçünü birleştirmeye çalıştı ve bazı bölgelerde iki tarafın satırları
kesiştiği için karar veremedi. O bölgeleri işaretledi:

```
<<<<<<< YEREL:<yol>
senin satırın
||||||| TABAN:<yol>
eski satır
=======
bizim satırımız
>>>>>>> YENİ:<yol>
```
(Etiketler motorun `git merge-file --diff3 -L YEREL/TABAN/YENİ` çağrısından gelir; ortadaki
`|||||||` bloğu TABAN'dır — neyin değiştiğini oradan okursun.)

**Bu en sık görülen yargı vakasıdır** ve çoğu zaman tehlikeli değildir: git **bitişik** satır
değişikliklerini de çakışma sayar (ölçüldü 2026-09-17 — 4. satır bizden, 5. satır senden ⇒ çakışma).
Yani "çakışma" çoğu kez "iki değişiklik yan yana düştü, insan baksın" demektir. Kullanıcıya bunu
böyle anlat; "bir şey bozuldu" izlenimi verme.

## Neden
Yerel değişikliğin bilinçlidir (bir kuralı gevşetmiş, bir eşiği değiştirmiş, kendi önekini
eklemiş olabilirsin) ve yeni sürüm de bir nedenle geldi. Varsayılan cevap çoğunlukla
**ikisini de koru**'dur; birini atmak sessiz bir kayıptır.

## Adımlar
1. `guncelle.py oneri <yol>` → çakışma işaretli dosya `.axet-guncelleme/oneri/<yol>`, ekranda
   iki fark + çakışma bloğu sayısı + yerel fark oranı.
2. Her çakışma bloğu için üç sürümü (taban / yerel / yeni) yan yana göster.
3. Kendi birleştirme önerini yaz ve **neden öyle birleştirdiğini** söyle. Varsayılan tutum:
   iki tarafın da niyetini koru; ancak gerçekten çelişiyorlarsa birini seç ve gerekçelendir.
4. Kullanıcı onaylarsa öneri dosyasını işaretsiz hâle getir (tüm `<<<<<<<`, `|||||||`,
   `=======`, `>>>>>>>` satırları gidecek).
5. `guncelle.py isaretle <yol> --karar birlesik` — motor çakışma işareti kalmadığını ve diske
   yazılanın geri okunduğunda aynı olduğunu doğrular.
6. Dosyanın sınıfı `validator` ya da `kritik_yol` ise **akış adım 11 zorunludur** — hüküm
   karşılaştırmasını şöyle ÖLÇ:
   Kontrol grubu kur: **aynı girdi, önce ve sonra.**
   - **Fixture'ı olan validator:** `python skills-sap/sap-adt-foundation/tests/run_tests.py -k validator_fixtures`
     — adım 6 (önce-ölçüm) ve adım 10 (sonra-ölçüm) çıktılarını karşılaştır; her validator için
     `bad` tarafı FAIL, `good` tarafı PASS olmalı ve bu İKİSİNDE DE tutmalı.
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

## Örnek
`check_x.py` — sen bir kontrolü BLOCKER'dan WARNING'e düşürmüşsün; biz aynı fonksiyondaki ayrı bir
mantık hatasını düzeltmişiz. Doğru birleşme: **ikisi de kalır** (senin gevşetmen + bizim
düzeltmemiz) ve asgari güvence raporuna "yerelde gevşetilmiş validator" satırı girer.

## Beklenen çıktı
`oneri` çıkışı 1 (çakışma var) · sonra `İŞARETLENDİ: <yol> → birlesik (dogrulandi)`.
İşaret kalmışsa: `FAIL <yol>: öneri dosyasında çakışma işareti duruyor …` ve çıkış 1 — durum
`bekliyor` kalır, kapanış bu dosyayla 0 dönmez.

## DUR
- Çakışma bloğu 3'ten fazlaysa ya da yerel fark oranı %50'yi aşıyorsa motor vakayı
  **V4c+ESIK** olarak işaretler: birleştirmeyi DENEME, o kartı oku.
- Tahminle birleştirme. Bir bloğun ne işe yaradığını anlamıyorsan kullanıcıya sor ya da
  `--karar ertelendi --gerekce ...` ile o dosyayı açıkta bırak.
- Kullanıcı onaylamadan öneri dosyasını işaretleme.

## Geri alma
Bir şey ters giderse: `guncelle.py geri-al <yol>` o dosyayı güncelleme öncesi hâline döndürür
(`hazirla` adımında atılan `guncelle-oncesi-<tarih>` etiketi). Hepsini birden geri almak için
`guncelle.py geri-al --hepsi`. Durum kaydı `geri_alindi` olur; kapanış bunu görür.
