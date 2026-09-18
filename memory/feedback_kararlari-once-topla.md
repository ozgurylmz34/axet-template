---
name: kararlari-once-topla
description: Uzun bir işe ya da alt ajana devretmeden önce kullanıcıya ait tüm kararları tek seferde topla; iş ortasında soru trafiği açma
type: feedback
---

Bir iş birimine (çok adımlı değişiklik, `agent` ile devredilen görev) başlamadan önce kullanıcıya ait kararların
HEPSİ toplanır; iş ancak ondan sonra, kararları netleşmiş tek bir planla/brifingle yürütülür.

**Neden:** "karar → başla → iş ortasında yeni açık nokta → tekrar sor → yeniden başla" döngüsü hem kullanıcıyı hem
işi iki yönlü bekletir ve patinaj üretir. Kararları öne almak döngüyü kaldırır.
**Nasıl uygulanır:** Önce salt-okur keşif yap. Çıkan açık noktaları ayır: teknik kararları kendin ver (gerekçesini
raporda yaz), yalnız iş/kullanıcı kararlarını sor — tek seferde, seçenekli, önerinle (`ask_user`). Keşifte
görünmeyen yeni bir karar sonradan çıkarsa yalnız onu sor, geri kalan işi sürdür.
Önceki kayıt: yok
Son-doğrulama: 2026-09-13 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
