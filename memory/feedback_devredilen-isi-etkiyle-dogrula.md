---
name: devredilen-isi-etkiyle-dogrula
description: Alt göreve devredilen işi brifingde önerdiğin adı arayarak değil, değişen dosyalar ve istenen etki üzerinden doğrula; önerilen adla "0 eşleşme" "yapılmadı" demek değildir
type: feedback
---

Brifingde bir uygulama önerirsin (sınıf, fonksiyon, dosya adı). Doğrularken o adı arayıp 0 bulunca "yapılmamış" demek
yanlıştır: alt görev işi gerekçeli olarak başka, çoğu zaman daha doğru bir biçimde yapmış olabilir.

**Neden:** Bir vakada mevcut bir CSS sınıfının yeniden kullanılması önerildi. Alt görev o sınıfın istenen kombinasyonu
(hücre ve başlık için ayrı boyut) karşılamadığını görüp aynı desende yeni bir sınıf tanımladı ve gerekçesini yazdı. Önerilen
adla arama 0 döndü, iş "yapılmadı" sanıldı ve gereksiz bir "yaptım / yapmadın" turu döndü.
**Nasıl uygulanır:**
1. Önce `git status --short` ve `git diff --stat`: hangi dosyalar değişti. İş commit edilmemiş olabilir; `HEAD`'e karşı boş
   diff "yapılmadı" değildir, çalışma ağacına bak.
2. Adı değil **etkiyi** ara: kural eklendi mi, kolon bağlandı mı, dal açıldı mı, çıktı değişti mi.
3. Ancak sonra spesifik adı ara; 0 dönerse "başka nasıl yapılmış olabilir" diye sor ve raporun gerekçesini oku.
4. Ne etki ne gerekçe varsa eksik say ve yeni brifingle geri ver.
Ters yönü çekirdektedir: alt görevin "yapılamaz / yok" dönüşü de kanıtsız kabul edilmez (çekirdek §7).
Önceki kayıt: yok (aranan: `memory/`, `core/`, `skills/` — "önerdiği", "etkisine", "git status --short")
Son-doğrulama: 2026-09-13 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
Applies-to: tüm projeler — `agent` aracıyla devredilen iş ve başkasının yaptığı değişikliğin doğrulanması
