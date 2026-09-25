---
name: kendi-isini-yeniden-siniflandirip-kural-disina-cikma
description: Bir kuralı atlamanın görünmez yolu onu ihlal etmek değil, işi yeniden sınıflandırıp kuralın dışına çıkarmaktır ("bu build değil, araç", "küçük bir şey"); etiketi olgu koyar, yazar değil; süre baskısında inceleme değil tur sayısı kesilir
type: feedback
---

Bir kural (`%code-review` ile bağımsız inceleme, test, kullanıcı onayı) uygulanmak istenmediğinde en tehlikeli hamle onu
açıkça çiğnemek değil, işi sessizce yeniden sınıflandırıp kuralın kapsamı dışına çıkarmaktır: "bu build sayılmaz",
"küçük bir şey", "salt-okur teşhis aracı, çıktı değil". İhlal görünürdür; yeniden sınıflandırma görünmez ve yapana meşru
gelir. Etiketi kural değil sen koyduğun an kural uygulanmaz görünür.

**Neden:** Ekip dersinde ortak pakete yazılacak ~200 satırlık bir ABAP sınıfı (RTTI, dinamik `ASSIGN CASTING`, standart
FM çağrısı) "bu build değil, teşhis aracı" gerekçesiyle bağımsız incelemeye verilmeden SAP'ye gönderildi. Mekanizma o gün
başka her işte doğru çalışmıştı; değişen kural değil sınıflandırmaydı. İlk teşhis "kuralın yazımında boşluk var" oldu ve
kullanıcı çürüttü ("haftalardır normaldin, boşluk yeni mi oluştu?"): kendi kararını sistem boşluğu diye teşhis etmek suçu
karardan dokümana taşır. İkinci vakada kendi değişikliğinin kırmızı testini "mekanik düzeltme" sayıp bir tasarım kararını
(tabanın neye sabitleneceği) onaysız verdi; kural metninin kısaltılmış bir özetine bakılmış, şart listesinin kaynağı
okunmamıştı. İki vakada da tetikleyen süre baskısıydı ("iş uzadı, tek turda yap") ve kesilen şey tam da geri dönen bulguları
önleyen incelemeydi.
**Nasıl uygulanır:**
- "Bu sayılmaz / küçük / araç" dediğin an dur ve olguya bak: kaç satır, hangi katman, SAP'ye yazılıyor mu, hangi paket
  (ortak paket = çıta yükselir), ileride yeniden kullanılacak mı. Cevaplar "önemli değişiklik" diyorsa etiket yanlıştır.
- Ölçüt yazar değil iştir: "kendim yazdım, küçük" incelemeyi düşürmez; tek model çalışırken ikinci göz zaten yapısal olarak
  yoktur, `%code-review` onu sağlayan tek adımdır.
- Sınıflandırmadan önce kuralın kaynağını oku (çekirdek, skill); hafızadaki kısa özet kural değildir, şartlar kaynaktadır.
- Süre baskısında kesilecek şey bulgu başına tur sayısıdır (ör. deterministik bir kontrol komutu), inceleme adımı değil.
- Bir kuralı esnetmek istiyorsan bunu açıkça söyle ve onay al; sessiz yeniden sınıflandırma kullanıcının göremediği bir
  muafiyet üretir.
Önceki kayıt: yok (aranan: `memory/`, `core/`, `skills/` — sınıflandırma, "küçük", build sayılmaz; kural kaynağı: çekirdek
"Tamam demeden önce" maddesi, `%code-review`)
Son-doğrulama: 2026-09-25 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
Applies-to: tüm projeler — inceleme, test ya da onay kuralı olan her değişiklik
