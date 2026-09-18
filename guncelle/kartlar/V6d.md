# V6d — template dosyayı emekliye ayırdı ama sende değişmiş

**Tek cümle:** Biz bu dosyayı kaldırdık, sende değiştirilmiş bir kopyası var; motor ona DOKUNMAZ.

## Ne demek
Dosya yeni sürümde yok, ama sendeki hâli tabandan farklı — yani üzerinde emek var. Otomatik silme
bu vakada yapılmaz; karar senindir.

## Neden
Silme geri alınması en pahalı işlemdir. Kullanıcının kendi eklediği kural/pattern sessizce
gitmemelidir; kalması da bir maliyet doğurmaz (yalnız bayat kalabilir).

## Adımlar
⛔ Bu vakada `oneri` KOŞULMAZ: birleştirilecek yeni sürüm yoktur. Yine de çalıştırılırsa motor
taban↔yerel farkından bir "çakışma önerisi" ya da eşik uyarısı üretebilir (ölçüldü 2026-09-18,
doküman gate'i) ve bu seni yanlış yola sokar — silme kararı YALNIZ kullanıcınındır.
1. Kullanıcıya durumu söyle: "template bu dosyayı emekliye ayırdı; sendeki değişmiş kopya duruyor".
2. Neden emekliye ayrıldığını kalem başlığından aktar (yerine ne geldi?).
3. Dosyayı olduğu gibi bırakmak kararıysa: `guncelle.py isaretle <yol> --karar yerel`.
4. Kullanıcı silmek isterse bunu KENDİ terminalinde yapar; sen de kalemi
   `--karar ertelendi --gerekce "kullanıcı elle silecek"` ile kapat.
5. Bütünlük turu bu dosyanın artık var olmayan bir şeye atıf yaptığını bulursa kullanıcıya bildir —
   yine de silme.

## Örnek
Emekli olmuş bir bakım script'i; sen içine kendi kısayolunu eklemiştin.

## Beklenen çıktı
`YEREL KORUNDU: <yol>` · durum `dogrulandi`, karar `yerel`.

## DUR
Kullanıcı istemeden silme. Dosya bir kural/gate dosyasıysa ve yerine yenisi geldiyse, ikisinin
birlikte çalışıp çalışmadığını (çelişen kural) mutlaka söyle.

## Geri alma
Bir şey ters giderse: `guncelle.py geri-al <yol>` o dosyayı güncelleme öncesi hâline döndürür
(`hazirla` adımında atılan `guncelle-oncesi-<tarih>` etiketi). Hepsini birden geri almak için
`guncelle.py geri-al --hepsi`. Durum kaydı `geri_alindi` olur; kapanış bunu görür.
