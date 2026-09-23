# V1R — dosya yeni bir yola taşındı (otomatik)

**Tek cümle:** Biz dosyanın adını/yerini değiştirdik, sen içeriğine dokunmamıştın; motor taşıdı.

## Ne demek
Yeni yayında bu dosya yeniden adlandırıldı. Sendeki içerik ya tabanla ya yeni sürümle aynı
olduğundan birleştirilecek bir şey yok: motor yeni yola yazar, eski yolu siler. Plandan
sonra eski yolu düzenlediysen içerik `<eski yol>.yerel` olarak saklanır.

## Neden
Yol değişimi başlı başına bir eylemdir. İçerik hiç değişmemiş olsa bile dosya taşınmalıdır —
aksi hâlde kalem "değişiklik yok" sanılıp plandan düşer ve klonda eski yol kalır.

## Adımlar
1. Motor taşımayı zaten yaptı.
2. Kullanıcıya eski ve yeni yolu birlikte söyle; kendi notlarında/kısayollarında eski yola atıf
   varsa güncellemesi gerektiğini ekle.
3. Sınıf kartı varsa onun ek adımlarını uygula.

## Örnek
`docs/tasinacak.md` → `docs/yeni/tasinacak.md`.

## Beklenen çıktı
`TAŞINDI: <eski yol> → <yeni yol>` · durum `dogrulandi`, `hedef_yol` yeni yol.

## DUR
Yeni yolda zaten senin bir dosyan varsa vaka **V7**'dir; motor üzerine yazmaz. İçerikte de kendi
değişikliğin varsa vaka **V4R**'dir (birleştirme gerekir).

## Geri alma
Bir şey ters giderse: `guncelle.py geri-al <yol>` o dosyayı güncelleme öncesi hâline döndürür
(`hazirla` adımında atılan `guncelle-oncesi-<tarih>` etiketi). Hepsini birden geri almak için
`guncelle.py geri-al --hepsi`. Durum kaydı `geri_alindi` olur; kapanış bunu görür.
