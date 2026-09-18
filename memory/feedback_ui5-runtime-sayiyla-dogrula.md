---
name: ui5-runtime-sayiyla-dogrula
description: UI5 davranışı gözle ya da click() sonucuyla değil model API'siyle sayı olarak doğrulanır; "backend doğru UI boş" durumunda iki taraf runtime'da yan yana okunur
type: feedback
---

Bir UI5 düzeltmesi "çalışmıyor" görünüyorsa sonuca hemen güvenilmez. Tarayıcı otomasyonunda `click()` bir
`sap.m.Button`'ın press handler'ını tetiklemeyebilir (overlay ya da koordinat artefaktı). `sap.ui.table` sanal satır
DOM'u da satır sayısında yanıltır.

**Neden:** Bir vakada "Temizle" düzeltmesi `click()` ile denendi ve grid dolu kaldı (5 satır). Aynı butona `firePress()`
ve controller metodunun doğrudan çağrısı 5 → 0 yaptı; düzeltme zaten doğruydu. Başka bir vakada iki SAP koleksiyonu
birleşince tüm miktar kolonları boştu. Backend doğru dönüyordu, kod doğru görünüyordu. Statik analiz yakalamadı;
runtime'da iki tarafın anahtarları yan yana okununca "10" ile "000010" dolgu farkı anında görüldü.
**Nasıl uygulanır:** Press için `Element.registry.get(id).firePress()` ya da `getController().<metot>()` kullanılır.
Durum `getModel(ad).getData()`, `getSelectedIndices().length` ve `getBoundingClientRect()` ile ölçülür. "Backend doğru,
UI boş/yanlış" durumunda model verisi ile OData sonucu aynı ölçümde karşılaştırılır; anahtarla birleştirilen dolgulu
alanlar (POSNR, VBELN, MATNR) iki tarafta normalize edilir. Ayrıntı: `%sap-ui5-fiori` → `references/runtime-verification.md` §4.
Önceki kayıt: yok
Son-doğrulama: 2026-09-14 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
