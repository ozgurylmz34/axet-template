---
name: ui5-plumbing-reuse-runtime-done
description: Freestyle UI5 + OData V2'de save/nav/setData mekaniği kanonik desenden alınır, sıfırdan yazılmaz; "done" statik kontrol + runtime ölçümüyle
type: feedback
---

UI5 ekranının **mekaniği** (save = sıralı `oModel.update(merge)` / nav yoluna `create`, navigation adı `to_X`,
`setData` tam şekil, master-detail seçim bağlantısı, MERGE'de boş tarih `null`) her uygulamada aynıdır →
`%sap-ui5-fiori` → `references/freestyle-odata-v2.md` §1–2'den alınır. Entity, alan listesi, yerleşim, iş kuralları,
value-help hedefleri ve etiketler her ekranda ayrıca yazılır; hiçbir ekran başka ekranın kopyası değildir.

**Neden:** Bir ekip bir UI'ın mekaniğini çalışan desenden almayıp sıfırdan yazdı. Başka ekranlarda çoktan çözülmüş altı
hata geri geldi: `_X` navigation, `core:Title` render çökmesi, programatik değerin kaydedilmemesi, eşzamanlı update
kilidi, boş tarih 400, eksik `setData`. Bu hatalar yalnız kullanıcı test edince çıktı. "Kod geçerli / XML geçerli / done"
raporu runtime doğrulaması olmadan kabul edilmişti.
**Nasıl uygulanır:** "Tamam" demeden önce statik kontrol script'leri çalışır ve KAPSAM satırları okunur. Ardından
runtime smoke gelir: uygulama açılır, konsolda sıfır gerçek hata, ana akış en az bir kez. Spesifikasyondaki her kuralın
UI'da gerçekten kodlandığı tek tek kontrol edilir. Opak "Kaydedilemedi"de önce gerçek HTTP yanıtı alınır, sonra tek
düzeltme yapılır.
Önceki kayıt: yok
Son-doğrulama: 2026-09-14 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
