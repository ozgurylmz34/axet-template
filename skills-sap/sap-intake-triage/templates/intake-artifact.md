<!-- S2 intake artefakti. Proje kokunde .axet-code/intake/<id>.md olarak kaydet.
     Her alanin yer tutucusunu gercek icerikle DEGISTIR; yer tutucu birakilan alan bos sayilir.
     Mutabakat isaretini yalniz kullanicinin acik onayindan sonra koy. Sema ve kontrol kurallari
     sap-intake-triage references/s2-artifact-schema.md dosyasindadir; ad onerisi, surum, kural taramasi ve
     oz-tutarlilik kurallari references/protocol.md 6. adimdadir. Bu yorumu silebilirsin. -->
# INTAKE — <kısa-ad>  (<tarih>)
- Modül / iş-tipi / KAPSAM: SD / rapor / S2  (gerekçe: ...)
- Sistem sürümü: sap-project.json release = <değer> · canlı = <değer> (araç + argüman) · fark: <yok | var → kullanıcıya soruldu, cevap>
- İstenen (özet):
- Çıkan domain-konuları: [konu → araştırma özeti (a/b/c eksen)]
- Etkilenen objeler (canlı-doğrulanmış): [obje → reuse/yeni/değişir → blast-radius]
  | Obje (tip) | reuse / yeni / değişir | Ad önerisi (yeni Z ise; standarda + paket öneklerine uygun) | Canlı kontrol (araç + argüman → sonuç) | ONAY |
  |---|---|---|---|---|
  | <obje> | <durum> | <ad> | <ör. adt_search_objects → 0 sonuç> | ONAY: [ ] |
- Tablo yönetim alanları (yeni tablo varsa): created_by · created_at · last_changed_by · last_changed_at · local_last_changed_at (RAP ETag) → <her biri: alan adı + DTEL/tip>
- Prior-art: [bulundu: <ref> / yok]
- Kabul kriterleri (EARS): "<olay> olduğunda sistem <sonuç> yapmalı" / "<durum> ise ..."
- Kural taraması (kullanıcı onayından ÖNCE zorunlu): <okunan checklist'ler: dosya + bölüm>
  | Tasarım kararı | İlgili kural (dosya · satır/kod) | uyuyor / sapıyor | Sapıyorsa: gerekçe + kullanıcıya sorulan soru ve cevabı |
  |---|---|---|---|
  | <karar> | <kural> | <uyuyor> | <—> |
- Açık kararlar / riskler:
- Öz-tutarlılık (onaya sunmadan önce): [ ] değişen her karar riskler + kabul kriterleri + obje tablosuna işlendi · [ ] "yok / yapılamaz" diyen her madde TR+EN eş anlamlılarla ikinci aramadan geçti · [ ] ONAY kutusu boş yeni Z adı kalmadı
- MUTABAKAT: [ ] kullanıcı sign-off
