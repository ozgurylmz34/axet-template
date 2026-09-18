# VTB — taban bilinmiyor

**Tek cümle:** Bu dosyanın "en son aldığın hâli"ni bulamıyoruz; üç yollu birleştirme yapılamaz,
otomatik birleştirme YASAK.

## Ne demek
Karşılaştırmanın üçüncü ayağı (taban) yok. İki sebebi vardır: ① yayın geçmişi yeniden yazılmış
(sır sızıntısı temizliği) ve taban commit'i artık yok · ② bir proje dosyasının hangi şablon
sürümünden türediği kayıtlı değil ve geçmişte eşleşen bir sürüm de bulunamadı.
Eksik geçmişin öbür sebebi olan `--depth` ile alınmış klonlar bu vakaya HİÇ ulaşmaz: `onkontrol`
onları akışın en başında çıkış 2 ile durdurur.

## Neden
Tabansız birleştirme = hangi değişikliğin kime ait olduğunu tahmin etmek. Tahminle birleştirilen
dosya sessizce yanlış olur; bu yüzden motor `oneri` komutunu bu vakada çalıştırmaz (çıkış 2).

## Adımlar
⛔ `oneri` bu vakada çalışmaz: taban olmadığı için çıkış 2 ile DUR der (motorun kendi kuralı).
1. Kullanıcıya iki içeriğin farkını göster (yerel ↔ yeni).
2. Üç seçeneği sun: **yeniyi al** (`--karar yeni`) · **yereli koru** (`--karar yerel`) ·
   **elle karşılaştır** (`--karar ertelendi --gerekce "..."`).
3. Sebep ① ise (geçmiş yeniden yazılmış) kalıcı çözümü söyle: `kur.cmd -Sifirla` ile temiz
   kuruluma dönmek. Aksi hâlde aynı dosya her yayında yeniden bu vakaya düşer.
4. Kararı işaretle.

## Örnek
Yayın geçmişi bir sır sızıntısı nedeniyle temizlenmiş; eski taban commit'i artık yok.

## Beklenen çıktı
Karar sonrası `İŞARETLENDİ: <yol> → yeni|yerel (dogrulandi)` ya da `ERTELENDİ: <yol> — <gerekçe>`.
(Yanlışlıkla `oneri` çalıştırılırsa: `DUR: <yol> için taban bilinmiyor (VTB) — otomatik
birleştirme YASAK …`, çıkış 2.)

## DUR
Taban uydurma: "muhtemelen şu sürümdendi" diyerek birleştirme yapma. Emin değilsen ertele ve
gerekçesini yaz.

## Geri alma
Bir şey ters giderse: `guncelle.py geri-al <yol>` o dosyayı güncelleme öncesi hâline döndürür
(`hazirla` adımında atılan `guncelle-oncesi-<tarih>` etiketi). Hepsini birden geri almak için
`guncelle.py geri-al --hepsi`. Durum kaydı `geri_alindi` olur; kapanış bunu görür.
