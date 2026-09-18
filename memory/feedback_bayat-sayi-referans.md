---
name: bayat-sayi-referans
description: Yorumdaki ve belgedeki sayılar ile dosya:satır referansları kod kadar hızlı bayatlar; içerik çapası kullan, başarıyı iddiayla değil önce/sonra ölçümüyle kanıtla
type: feedback
---

Yorum ya da belge "N obje", "N metot", "dosya:satır", "canlıda X yok" der; ölçülünce yanlış çıkar. Hiçbir
doğrulayıcı yorumdaki sayıya bakmaz.

**Neden:** Tek bir turda 6 vaka: "7 obje" (gerçek 9), "10 doğrulama metodu" (gerçek 13), "canlıda bağlı teslimat
yok" (sorguda 26 satır vardı; iki ayrı alt ajan bunu kanıt sanıp aktardı), düzeltmenin kendisi satırları kaydırdığı
için iki kez üst üste bayatlayan `dosya:satır`, dar desenli bir aramayla verilmiş "0 bayat referans kaldı" iddiası.
En öğreticisi: "satır no yazma" diyen yorum bloğunun kendisi 3 bayat satır numarası taşıyordu.
**Nasıl uygulanır:**
- Kalıcı metne (kod yorumu, belge, hafıza) sayı yazarken ölçüm tarihini de yaz; sayıyı tazelemek sınıfı çözmez.
- Aynı dosyada satır numarası yerine içerik çapası kullan (başlık, fonksiyon adı); dosyalar arası referansı sembol
  adına bağla ("şu adla ara: `<sembol>`").
- Yorumdaki veri iddiasını (canlıda X var/yok) ölçmeden aktarma.
- Bir işlemin başarısını `rc=0` / `HTTP 200` / `[OK]` ile değil iki sayıyla kanıtla: işlemden önce taban, sonra
  hedef ölç; kanıt ikisinin farkıdır (ör. buton sayısı 0→5).
- Sohbet içi anlık raporda `dosya:satır` kullanılabilir (anlık ve doğrulanabilir); kural kalıcı metin içindir.
- Aynı sayı iki yerde yaşıyorsa (düzyazı ↔ tablo satırı, rapor ↔ belge) birini güncellediğin turda öteki bayatlar:
  yeni sayıyı yazdıktan sonra **eski sayıyı** belge genelinde ara; 0 sonuç almadan "güncelledim" deme. Ölçüm büyüyünce
  yalnız rakamı değil onaylanan kümeyi (hangi vakalar geçiyor) de yeniden ölç.
Önceki kayıt: yok
Son-doğrulama: 2026-09-13 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
