# V4R — dosya taşındı VE iki taraf da değişmiş

**Tek cümle:** Biz dosyayı yeni bir yola taşıdık, sen de içeriğini değiştirmişsin; değişikliğin
yeni yola taşınacak.

## Ne demek
İki iş bir arada: yeniden adlandırma (+R) ve içerik birleştirme. Motor yol değişimini içerikten
BAĞIMSIZ değerlendirir; birleşmenin sonucu ayrıca hesaplanır ve plan sana hangi alt vakanın
geçerli olduğunu söyler: temiz (V4t gibi), çakışmalı (V4c gibi), eşik aşıldı ya da ikili.

## Neden
Yol değişimi tek başına bir eylemdir; içerik aynı olsa bile dosya taşınmalıdır. Aynı anda içerik de
değiştiyse, birleştirme HEDEF yolda yapılır ve eski yol silinir.

## Adımlar
1. Plandaki kayda bak: `kart` alanı `V4R` ile birlikte birleşme kartını da verir — önce onu oku
   (`guncelle.py kart V4t` / `V4c` / `V4c+ESIK` / `V4B`) ve adımlarını uygula.
2. `guncelle.py oneri <eski yol>` — öneri ve farklar eski yol adıyla üretilir.
3. `guncelle.py isaretle <eski yol> --karar birlesik|yerel|yeni` — motor sonucu YENİ yola yazar,
   eski yolu siler.
4. Kullanıcıya iki yolu birlikte söyle; raporda kalem "taşındı" olarak görünür.

## Örnek
`docs/tasinacak.md` → `docs/yeni/tasinacak.md`, üstelik sen dosyaya kendi notunu eklemişsin.

## Beklenen çıktı
`İŞARETLENDİ: <eski yol> → birlesik (dogrulandi)`; diskte yalnız yeni yol var, eski yol yok.

## DUR
Hedef yolda zaten senin başka bir dosyan varsa vaka **V7**'dir. Ayrıca `--karar yerel` bu vakada
dosyayı ESKİ yolda bırakır: taşımayı bilinçli olarak reddetmiş olursun; kullanıcıya bunu söyle.

## Geri alma
Bir şey ters giderse: `guncelle.py geri-al <yol>` o dosyayı güncelleme öncesi hâline döndürür
(`hazirla` adımında atılan `guncelle-oncesi-<tarih>` etiketi). Hepsini birden geri almak için
`guncelle.py geri-al --hepsi`. Durum kaydı `geri_alindi` olur; kapanış bunu görür.
