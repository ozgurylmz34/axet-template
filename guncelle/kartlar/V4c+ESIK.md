# V4c+ESIK — ayrışma çok büyük, birleştirme denenmez

**Tek cümle:** Bu dosyada senin değişikliğin çok geniş (ya da çok fazla çakışma var); model
tahminiyle birleştirmek yerine karşılaştırmayı insana bırakıyoruz.

## Ne demek
Motor eşiği ölçtü: **3'ten fazla çakışma bloğu** YA DA **yerel fark oranı %50'den büyük**.
Bu eşiği aşan dosyada birleşik öneri üretilmez; iki fark ayrı dosyalara yazılır.

## Neden
Büyük ayrışmada birleştirme artık "satır taşımak" değil, dosyanın niyetini yeniden kurmaktır.
Orada üretilen öneri kulağa doğru gelir ama sessizce yanlış olabilir — en pahalı hata sınıfı budur.

## Adımlar
1. `guncelle.py oneri <yol>` (çıkış 3) → `.axet-guncelleme/elle/<yol>.yerel.diff` ve
   `.axet-guncelleme/elle/<yol>.yeni.diff` yazılır.
2. Kullanıcıya iki farkın YOLUNU ver ve açıkça söyle: "bu dosyayı elle karşılaştırman gerekiyor".
3. Kullanıcı elle birleştirmek istemiyorsa seçenekleri sun: yereli koru (`--karar yerel`) ya da
   yeniyi al (`--karar yeni`, kendi değişikliğin gider).
4. Şimdi karar vermek istemiyorsa: `guncelle.py isaretle <yol> --karar ertelendi --gerekce "..."`.
   Gerekçe zorunludur ve kapanış raporunda görünür.

## Örnek
Kendi kurumsal kurallarınla baştan yazdığın bir referans dosyası; yayın da aynı dosyayı geniş
çapta güncellemiş.

## Beklenen çıktı
`V4c+ESIK — ayrışma eşiği aşıldı, birleştirme DENENMEDİ. Farklar: …` (çıkış 3) ·
karar sonrası `ERTELENDİ: <yol> — <gerekçe>` ya da `İŞARETLENDİ: <yol> → yerel|yeni (dogrulandi)`.

## DUR
Eşiği aşan dosyada kendi birleştirme önerini yazma — kart bunu açıkça yasaklar. Kullanıcı
"sen birleştir" derse bile önce iki farkı göster ve riski söyle; kararı o versin.

## Geri alma
Bir şey ters giderse: `guncelle.py geri-al <yol>` o dosyayı güncelleme öncesi hâline döndürür
(`hazirla` adımında atılan `guncelle-oncesi-<tarih>` etiketi). Hepsini birden geri almak için
`guncelle.py geri-al --hepsi`. Durum kaydı `geri_alindi` olur; kapanış bunu görür.
