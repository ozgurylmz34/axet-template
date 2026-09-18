# Klasik OData backend inceleme satırları — SEGW, DPC_EXT, function import, dış API çağrısı

> **Kaynak:** ekibin backend kod-inceleme kontrol listesi (BE kimlikleri korunmuştur) + `%sap-odata-backend` referanslarındaki
> ölçülmüş kurallar (`OD-NN` = aXet'te satıra çevrilen kural). Önem eşlemesi, tip, otomasyon: `checklist-common.md` başlığı.
> DPC_EXT ve API çağıran sınıflar sınıf kaynağıdır → `checklist-abap.md` de yürünür.

| ID | Ne kontrol edilir | Nasıl | Önem | Otomasyon | Kaynak ders |
|---|---|---|---|---|---|
| BE-04 | Tutar/miktar dış API gövdesine `WRITE … TO` ile metne çevrilmiş → ≥ 1000 değerde binlik ayraç, `Edm.Decimal` 400 | JSON/URL/gövde kuran kodda `WRITE` + `TO` ara; doğrudan atama + `CONDENSE`; negatifte işaret başa | BLOCKER | `class_push` → `check_decimal_write_to.py` (WARNING — zincir bloklamaz; program/FM'de koşmaz) | Ekip dersi; `%sap-odata-backend` serialization §1 |
| BE-14 | SAP içi OData API çağrısı SM59 destination ile yapılmış (istemci kodda sabit, QA/PRD'de kırılır) ya da kaynakta kimlik bilgisi var | Çağrı yöntemi iç gateway proxy mi; kaynakta kullanıcı/şifre yok mu | WARNING | YOK | Ekip dersi; `%sap-odata-backend` outbound-api-call §1, §4, §5 |
| OD-01 | COMMIT bağlama uygun değil: DPC_EXT'te BAPI dönüşü E/A kontrol edilmeden commit; DPC'den çağrılan RFC FM içinde commit; function import içindeki EML'de `COMMIT ENTITIES` | `commit work`, `BAPI_TRANSACTION_COMMIT`, `COMMIT ENTITIES` ara ve bağlamı oku | BLOCKER | YOK | `%sap-odata-backend` dpc-crud §4 · deep-insert-function-import §4 |
| OD-02 | Function import içinden released BO'ya EML: ayrı ayrı `MODIFY ENTITIES` blokları, tekrarlanan `%cid`, dallar içinde `DATA(…)` bildirimi, `FOR … INDEX INTO` → commit ya da çalışma zamanı dump | Tek `MODIFY ENTITIES` bloğu; `%cid` benzersiz; `DATA` metot başında; tablo önce LOOP ile hazırlanmış | BLOCKER | YOK | `%sap-odata-backend` deep-insert-function-import §4 |
| OD-03 | İki koleksiyonu anahtar dizgesiyle birleştiren kodda anahtar biçimi (sıfır dolgusu) iki tarafta aynı değil → eşleşme sessizce boş | Dış kaynaktan gelen anahtar okumadan/birleştirmeden önce normalize ediliyor mu (`ALPHA = IN`); standart API'ye dolgulu değer gidiyor mu | BLOCKER | YOK | `%sap-odata-backend` serialization §3 |
| OD-04 | `Edm.DateTime` alanına `YYYY-MM-DD` gönderiliyor → 400; boş tarih `""` gönderiliyor | Tarih gövdesi `/Date(<ms>)/` biçiminde mi; boş tarih `null` mı | BLOCKER | YOK | `%sap-odata-backend` serialization §2 |
| OD-05 | Standart API POST/PATCH sonrası `sap-message` yanıt başlığı okunmuyor → uyarı ve bilgi mesajları kaybolur; mesajlar özel yapıyla taşınıyor | Yanıt başlığı okunuyor ve `BAPIRET2_T`'ye aktarılıyor mu | WARNING | YOK | `%sap-odata-backend` serialization §5 |

## Bu dosyada ÇIKARILAN / DEĞİŞTİRİLEN
- Ortak token yardımcısının gerçek sınıf adı ve paketi çıkarıldı (proje kararıdır).
- Conversion exit'li alanın OData'ya açılması yazma-öncesi listededir: `%sap-cds-ddic` CDS-CONVEXIT.
