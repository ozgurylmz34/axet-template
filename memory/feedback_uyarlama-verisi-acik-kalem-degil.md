---
name: uyarlama-verisi-acik-kalem-degil
description: Uyarlama ve ana-veri tablolarındaki DEĞERLER (test değeri, geçici kayıt) açık iş listesine ya da hafızaya yazılmaz; doğru değeri kullanıcı bilir ve gerektiğinde kendisi girer
type: feedback
---

Bir uyarlama/ana-veri tablosunda bir değer gözlemlediğinde ("şu alan test değerinde kalmış, geri alınmalı") bunu açık
iş listesine, devir notuna ya da hafızaya YAZMA. Bu değerler kullanıcının alanıdır ve sürekli değişir; senin gördüğün an
bir fotoğraftır.

**Neden:** Kayda geçen değer (a) her oturumda "açık iş" gibi geri gelir, (b) kullanıcı çoktan düzeltmiş olsa bile liste
"açık" der, (c) sahiplik karışır — veri kullanıcının, kayıt AI'ın olur. Ekip dersinde bir test değeri "geri alınmalı"
diye hafızaya ve oturum notuna yazıldı, 16 gün açık kalem olarak taşındı; kullanıcı: "bu açık değil, doğrusu ne ise ben
yazarım zaten."
**Nasıl uygulanır:**
- Ayrım testi: "düzeltmesi bir uyarlama/bakım ekranından (SM30, SPRO) değer girmek mi?" → evet ise takip kalemi DEĞİL.
- Gerekiyorsa o anda SÖYLE (ölçüm sonucu olarak), ama kayda geçirme. Kayda geçen yalnız şunlardır: kod kusuru · eksik
  geliştirme · yapısal karar.
- Aynı sınıf: test verisi temizliği, koşul kaydı bakımı, yetki rolü ataması — hepsi kullanıcı alanı.
- FS'in açık kararlar bölümüne de uyarlama verisi sorusu yazma; oraya yalnız fonksiyonel karar girer.
- İstisna: kullanıcı açıkça "bunu bana hatırlat" derse.
Önceki kayıt: yok (aranan: `memory/`, `skills/gun-sonu`, `skills/remember` — uyarlama, ana veri, açık kalem, test değeri)
Son-doğrulama: 2026-09-25 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
Applies-to: tüm SAP projeleri — proje iş listesi (`.axet-code/memory/project_is-listesi.md`), devir notu ve hafıza kayıtları
