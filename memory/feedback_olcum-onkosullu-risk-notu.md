---
name: olcum-onkosullu-risk-notu
description: Koda ya da belgeye "ölçülmeli / riskli olabilir" yazmak bir kayıt değil bir niyettir; aynı turda proje iş listesine kalem aç ya da cümleyi hiç yazma, bir kusuru düzeltmeden önce böyle bir şerh var mı diye ara
type: feedback
---

Bir kod/belge şerhinde "bu büyük yükte sınıra çarpabilir, ölçülmeli" gibi bir cümle haftalarca durabilir ve kimseyi
uyarmaz. Kusur patladığında kimse şerhi ARAMAZ, semptomu arar; şerh yalnız o dosyayı zaten başka bir iş için açan kişiye
görünür.

**Neden:** Ekip dersinde bir controller şerhinde günler önce "URL'e serileşiyor, büyük yükte sınıra çarpabilir" notu
vardı. Tam o kusur canlıda patladı (HTTP 414) ve sıfırdan teşhis edildi: sınırı koyan katman arandı, eşik ikili aramayla
bulundu, üç çözüm denendi. Sonradan yapılan arama şerhi buldu — daha önce hiç aranmamıştı, çünkü hiçbir iş listesinde
ya da kontrol listesinde yoktu.
**Nasıl uygulanır:**
- Koda "ölçülmeli / riskli olabilir" yazdığın anda AYNI turda proje iş listesine (`.axet-code/memory/project_is-listesi.md`)
  bir kalem aç ve şerhe o kalemin başlığını yaz.
- Kalıcı bir kalem açmayacaksan cümleyi öyle yazma: ya ölç, ya da "ölçülmedi, sınırı bilmiyoruz" diye açıkça bilgi olarak
  bırak (gizli risk iddiası değil).
- Bir kusuru düzeltmeden önce "böyle bir şerh zaten var mı" diye ilgili dosyada ve iş listesinde ara (çekirdek §2 önce
  ara); varsa üç deneme yerine doğrudan çözüme gidilir.
Önceki kayıt: yok (aranan: `memory/`, proje iş listesi şablonu — "ölçülmeli", risk şerhi, ertelenmiş iş)
Son-doğrulama: 2026-09-25 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
Applies-to: tüm projeler — kod/belge şerhi ve proje iş listesi disiplini
