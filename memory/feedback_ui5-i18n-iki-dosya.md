---
name: ui5-i18n-iki-dosya
description: TR çalışan UI5 uygulamasında etiket/metin değişikliği ve yeni anahtar hem i18n.properties hem i18n_tr.properties dosyasına yazılır
type: feedback
---

`data-sap-ui-language="tr"` ile çalışan uygulamada UI5 `i18n_tr.properties` dosyasını yükler ve varsayılan
`i18n.properties` üzerine yazar. Bir anahtarın metnini değiştirirken ya da yeni anahtar eklerken **iki dosya birlikte**
güncellenir. Ardından kullanıcıya hard refresh (Ctrl+F5) söylenir; bundle tarayıcıda önbelleklenir.

**Neden:** Bir ekipte etiket yalnız varsayılan dosyada düzeltildi. TR dosyası eski metni ezmeye devam etti ve kullanıcı
eski etiketi gördü (bir tur boşa gitti). Başka bir vakada TR dosyasında eksik kalan anahtar ASCII varsayılana düştü.
Kullanıcı diyakritiksiz metin gördü ("Secili"). Altı inceleme turu bunu yakalayamadı, ekranda görüldü.
**Nasıl uygulanır:** `grep -n "<anahtar>" webapp/i18n/i18n*.properties` ile bulunan tüm dosyalar güncellenir. Sonra
`%sap-ui5-fiori` → `scripts/check_i18n_keys.py <app>` çalıştırılır: kullanılan anahtar iki dosyada mı, yer tutucu
kümeleri eşit mi, yer tutuculu metinde tek kesme var mı. Kardeş uygulamadan metin kopyalamadan önce anlamı kontrol edilir.
Önceki kayıt: yok
Son-doğrulama: 2026-09-14 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
