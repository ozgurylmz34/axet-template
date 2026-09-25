---
name: yesil-sinyal-kapsamini-sor
description: Yeşil bir sinyal (exit 0, OK, 0 bulgu, PASS, inceleme onayı) yalnız kendi kapsamı kadar şey söyler; kanıt çıktının kendisidir, kontrolün ters yönünü de koş, öneri ve onayı da iddia say
type: feedback
---

Yeşil bir sinyal — `exit 0`, "OK / yenilendi", doğrulayıcının "0 bulgu"su, geçen test takımı, bir incelemenin "doğru"
onayı, hiç ateşlenmemiş bir kod dalı — yalnız **baktığı yüzey** kadar şey söyler. Kapsamı sorulmayan yeşil kırmızıdan
tehlikelidir, çünkü aramayı durdurur.

1. **`exit 0` işin yapıldığının kanıtı değildir; kanıt çıktıdır.** Araç yalnız kendi adımının hata fırlatmadığını
   söyler. Ölçütü çıktıya bağla ve üç kademede incele: dosya değişti mi (içerik hash'i; zaman damgası yetmez) → doğru mu
   değişti → doğru şeyi mi gösteriyor (görselde son kademe gözle bakmaktır). "Aynı" iki anlama gelir: üretildi ve özdeş
   ya da hiç üretilmedi; aracın kendi günlüğünü oku. Sessizlik de üç anlamlıdır: olay yok · filtre tutmadı · üretici
   çalışamadı.
2. **Dar araç, geniş okuma.** Tek bir desenle ya da tek bir yardımcı fonksiyonla koşan kontrol, kontrolün tamamı hakkında
   hüküm vermez. Kontrolü kendi giriş noktasından (gerçek komut) koş, bilinen bir örnekle pozitif kontrol yap, neyi
   yakalamadığını yaz. Doğrulama ölçütüne yazılmış sabit bir sayı ("6 + 4 aktif") kapsam büyüyünce bayatlar ve eksik işi
   yeşil gösterir.
3. **Ters yön.** Her "kullanılan her şey tanımlı mı?" kontrolünün ikizi "tanımlı her şey kullanılıyor mu?"dur. İleri yön
   gürültülüdür (eksikse aktivasyon düşer); ters yön sessizdir ve yapılmış sanılan işi saklar — kasten aranmalıdır.
4. **Hiç ateşlenmemiş yol doğruluğun kanıtı değildir.** "Yıllardır sorun çıkmadı" yalnız o veriyle karşılaşılmadığını
   gösterir; kasıtlı hazırlanmış bir vakayla pozitif kontrol kur.
5. **Öneri ve onay da iddiadır.** Bir kaydın önerdiği düzeltme yönü ya da bir incelemenin "doğru" onayı kendi kanıtını
   ister: onay neyi ölçerek verildi — veriyi mi, mekanizmayı mı?
6. **Tarama çıktısı bir hipotezdir, iş listesi değil.** Eşleşen metin parçası ile aradığın sembol aynı şey değildir; her
   kalemi kendi anlamıyla doğrulamadan iş listesine yazma, mümkünse listeyi aracın kendi çıktısından türet.
7. **Mekanizma sorusu kaynak okumasıyla kapanmaz.** "Paylaşılıyor mu / önbellekten mi / aynı örnek mi?" sorusunda kaynak
   okuması hipotez verir; belirleyici olan çalışma anındaki anahtarın değeridir — ağ izi, örnek kimliği, sayaçla ölç.
   Kardeş bir artefaktta çalışan bir fonksiyon, senin kullandığın parametreyle de çalışıyor demek değildir.

**Neden:** Ekip derslerinde bir tutarlılık aracı "0 çelişki · 22 dosya" dedi ve belge doğru sanıldı; araç yalnız sayılara
bakıyordu, aynı gün kapsam dışı alanlardan 40'tan fazla bulgu çıktı. Bir PDF üretim script'i 18/18 "OK" dedi, PDF'lerin
yalnız 8'i üretilmişti. "Belgede anılan her mesaj katalogda mı?" kontrolü temizdi; ters yön ("katalogdaki her hata
mesajının üretim noktası var mı?") 4 bulgu verdi ve ikisinin arkasındaki iş kuralı hiç yazılmamıştı. Bir UI5 modelinin
metadata'yı paylaştığı kaynak okumasıyla iki kez "evet" diye cevaplandı; ağ izi ikinci bir `$metadata` isteği gösterdi.
**Nasıl uygulanır:**
- Yeşil gördüğünde sor: bu kontrol neye baktı, neye bakmadı? Cevabı raporda yaz; "0 bulgu" yalnız "baktığım yüzeyde
  bulgu yok" demektir ([[kontrol-yazarken-kor-nokta]]).
- Başarıyı araç mesajıyla değil çıktının içeriğiyle ve önce/sonra iki sayıyla kanıtla ([[bayat-sayi-referans]]).
- Her varlık kontrolünün ters yönünü de koş.
- İki bağımsız okuyucunun aynı sonuca varması yöntem aynıysa kanıt değildir: biri okusun, öteki ölçsün.
Önceki kayıt: bulundu [[kontrol-yazarken-kor-nokta]] (kontrol yazarken koştu ≠ baktı, fail-open) — bu kayıt yeşil
sinyali OKUMA tarafını ekler; aranan: `memory/`, `core/` — exit 0, OK, yeşil, ters yön, onay, paylaşım
Son-doğrulama: 2026-09-25 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
Applies-to: tüm projeler — araç çıktısı, test takımı, doğrulayıcı ya da inceleme sonucuna dayanarak "tamam" denen her iş
