---
name: spec-mutabakat-once-build
description: Yeni program ya da ekran geliştirmesi, sentezlenen spec kullanıcıyla madde madde onaylanmadan başlamaz
type: feedback
---

Her yeni program/ekran geliştirmesi backend ya da frontend koduna başlamadan önce şu adımlardan geçer:
1. **İste:** ekran görüntüleri ve kullanıcının fonksiyonel spec'i. Basit iş olsa bile istek adımı atlanmaz
   (kullanıcı kısa verebilir).
2. **Sentezle:** kullanıcı spec'i + ekran görüntüleri + varsa eski sistemin kaynak kodu + mevcut obje/alan
   tanımları → alan listesi, davranış, iş kuralları ve **açık kararlar tablosu**.
3. **Mutabakat:** spec kullanıcıyla madde madde gözden geçirilir, açık kararlar kapatılır.
4. Ancak bundan sonra backend → frontend.

**Neden:** Spec belirsizliğiyle başlanan geliştirmede patinaj yaşandı. Açık kararlar önceden taahhüt edilmez,
mutabakatta çözülür.
**Nasıl uygulanır:** Açık kararlar tablosunda kesin yasaklara (standart obje ya da standart tablo verisi yazımı)
dokunan maddeler ayrıca işaretlenir. Alan adları ve açıklamalar tahmin edilmez; spec ya da eski kaynaktan alınır.
Önceki kayıt: yok
Son-doğrulama: 2026-09-13 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
