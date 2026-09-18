# V4B — ikili dosya, iki taraf da değişmiş

**Tek cümle:** Resim/PDF/arşiv gibi bir dosyada hem senin hem bizim sürümümüz var; birleştirme yok,
biri seçilecek.

## Ne demek
Dosya ikili (`.png`, `.jpg`, `.pdf`, `.zip`, `.xlsx`, `.docx` … ya da `.gitattributes`'ta binary
işaretli, ya da içinde NUL baytı olan). Metin birleştirmesi anlamsızdır.

## Neden
İkili içerikte satır yoktur; "birleştirilmiş" bir PNG bozuk bir PNG'dir.

## Adımlar
1. `guncelle.py oneri <yol>` bu dosyada birleştirme yapmaz, `V4B` satırını basar (çıkış 1).
2. Kullanıcıya iki tarafı tarif et: dosya adı, boyut, tarih; mümkünse ne olduğunu söyle
   (ör. "logo görseli"). İçeriği ekrana dökmeye çalışma.
3. Sor: "yereli koru / yeniyi al".
4. `guncelle.py isaretle <yol> --karar yerel|yeni`.

## Örnek
`docs/logo.png` — sen kurumsal logoyu koymuşsun, yayın da görseli yenilemiş.

## Beklenen çıktı
`V4B — ikili dosya, birleştirme yok: <yol>. Karar: …` · sonra
`İŞARETLENDİ: <yol> → yerel|yeni (dogrulandi)`.

## DUR
"Yeniyi al" senin ikili dosyanın üzerine yazar ve içeriği geri getirmenin tek yolu geri alma
etiketidir. Kullanıcı ne kaybedeceğini anlamadan işaretleme.

## Geri alma
Bir şey ters giderse: `guncelle.py geri-al <yol>` o dosyayı güncelleme öncesi hâline döndürür
(`hazirla` adımında atılan `guncelle-oncesi-<tarih>` etiketi). Hepsini birden geri almak için
`guncelle.py geri-al --hepsi`. Durum kaydı `geri_alindi` olur; kapanış bunu görür.
