# V4i — yerel değişiklik yeni sürümde zaten var (otomatik)

**Tek cümle:** Bu dosyayı sen (ya da önceki bir ara sürüm) değiştirmişsin, ama yaptığın değişikliğin
tamamı yeni sürümde zaten var; motor yeni sürümü yazdı, kaybolan bir şey yok.

## Ne demek
Dosyanın sendeki hâli ne en son aldığın sürümle ne de yeni sürümle birebir aynı. Ama üç sürüm
(taban / senin hâlin / yeni sürüm) birleştirildiğinde sonuç yeni sürümün **aynısı** çıkıyor: senin
değiştirdiğin her satır yeni sürümde de aynı biçimde değişmiş. Birleştirme sorusu sormak gereksiz;
motor yeni sürümü doğrudan aldı.

## Neden
Sık görülen kaynak: bir önceki güncellemede ara bir sürümü elle almışsın ya da aynı düzeltmeyi
kendin yapmışsın. Bu dosya yargı vakası (V4t) sayılsaydı CI'nın yeşil hükmü kullanılamaz ve dosya
gereksiz yere kullanıcı kararına düşerdi (Z162, ölçülmüş vaka). Motor bu kodu yalnız çakışmasız
birleşmenin sonucu yeni sürüme **bayt bayt** (satır sonları hariç) eşitse verir.

## Adımlar
1. `guncelle.py uygula --otomatik` bu dosyayı zaten yazdı — elle bir şey yapma.
2. Kullanıcıya tek satırla söyle: hangi dosya, hangi kalem; "yerel değişikliğin yeni sürümde zaten
   vardı, kaybolan bir şey yok".
3. Dosyanın sınıfı için ayrı bir kart varsa (`sinif-...`) onun ek adımlarını da uygula.

## Örnek
`skills-sap/sap-dev/SKILL.md` — klonda bir ara sürümün metni duruyordu; yeni yayın aynı metni
içeriyor ve üstüne ekleme yapıyor.

## Beklenen çıktı
`ALINDI: skills-sap/sap-dev/SKILL.md (V4i — yerel değişikliğin tamamı yeni sürümde zaten vardı)` ·
`guncelle.py durum` tablosunda `dogrulandi`.

## DUR
`dosya plan üretildikten sonra değişmiş` hatası çıktıysa motor dosyaya DOKUNMADI: plan üretildikten
sonra dosya yeniden değişmiş. `guncelle.py plan` ile planı yeniden üret ve yeni vakaya göre ilerle;
eski planla `isaretle` çalıştırma.

## Geri alma
`guncelle.py geri-al <yol>` dosyayı güncelleme öncesi hâline (senin hâline) döndürür.
