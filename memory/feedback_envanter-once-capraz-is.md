---
name: envanter-once-capraz-is
description: Birden çok katmana ya da uygulamaya yayılan bir değişiklik "küçük düzeltme" gibi tek tek yapılmaz; önce tüm yüzeyin envanteri çıkarılır
type: feedback
---

Belirti: iş küçük sanılır, her düzeltme bir sonraki eksiği doğurur, kapsam yol boyunca büyür ve kullanıcı "neden
tek tek yapıyorsun" der. Kök neden: davranış çapraz kesendir (backend kuralı + frontend akışı + mesaj + veri, ya
da birden çok uygulama), ama yüzeyin tamamı hiçbir noktada taranmamıştır.

**Neden:** Bir silme kontrolü işi "3 uygulamalık frontend düzeltmesi" sanıldı; tam tarama sonrası 7 uygulama +
2 backend boşluğu + canlıda yetim veri çıktı, silme yolu 14 değil 24'tü, aynı hata sınıfının 7 varyantı vardı ve
6 inceleme turu gerekti. Bir uygulama hiçbir incelemenin kapsamına girmediği için neredeyse gözden kaçıyordu.
**Nasıl uygulanır:** Sıra: davranışı çalışır sistemde teyit et → envanter/matris çıkar (hangi uygulama, katman,
yol, veri) → tek iş listesi + tahmin → kapsam kararını kullanıcıyla toplu al → deseni tek yerde dondur → diğer
yerlere çoğalt → tek inceleme turu → çalışır sistemde kabul. Envanteri `todos` ve rapora koy; "hepsi bu" demeden
aramanın kapsamını yaz.
Önceki kayıt: yok
Son-doğrulama: 2026-09-13 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
