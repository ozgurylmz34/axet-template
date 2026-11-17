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
- **Teknik şartlar da önce:** bir çözümün iki parçası varsa (düzeltme + onun mümkün kıldığı otomatik yol) ikisini birlikte
  sun; ikinci yarıyı sonradan getirmek kullanıcıya "madem çözüyordu neden yapmadın" dedirtti (ekip dersi). Alt göreve
  verilecek şartı brifin İÇİNE yaz: devirden sonra iletilen kısıt uygulanmayabilir ve rapor bunu söylemeyebilir. Bunun için
  devirden önce dokunulacak mevcut kodu oku.
Önceki kayıt: yok
Son-doğrulama: 2026-11-17 (ekip dersinden uyarlandı, teknik şartlar eklendi; aXet'te ayrıca ölçülmedi)
