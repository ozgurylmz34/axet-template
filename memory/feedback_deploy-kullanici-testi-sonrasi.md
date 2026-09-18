---
name: deploy-kullanici-testi-sonrasi
description: Uygulamayı SAP'ye (BSP) ya da ortak bir sisteme deploy etmeden önce kullanıcı yerelde test edip açıkça OK demeli
type: feedback
---

Geliştirme bitince sıra: kendi doğrulaman (test, `%code-review`) → uygulamayı yerelde çalıştır → kullanıcıya
"yerelde hazır, test edebilirsin" de → BEKLE. Kullanıcıdan "OK / deploy et" gelmeden deploy yapılmaz; proaktif
ya da "zaten hazırdı" gerekçeli deploy yoktur.

**Neden:** UI5 yerel sunucusu canlı backend'e bağlanır; kullanıcı değişikliği gerçek veriyle yerelde görebilir.
Erken deploy, yanlışsa ortak sistemi kirletir. Testin sahibi kullanıcıdır, deploy onayı da onundur.
**Nasıl uygulanır:** Frontend özelliği yeni bir backend alanına (CDS alanı vb.) bağlıysa yerel test ancak backend
sistemde aktifse çalışır; backend aktivasyonu da SAP'ye yazmadır → ayrıca açıkla, ayrıca onay al. Yalnız frontend
değişikliğinde backend aktivasyonu gerekmez.
Önceki kayıt: yok
Son-doğrulama: 2026-09-13 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
