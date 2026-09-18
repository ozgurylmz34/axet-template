# RAP inceleme satırları — BDEF, behavior pool, EML, servis

> **Kaynak:** ekibin backend kod-inceleme kontrol listesi (kimlikler korunmuştur) + RAP dersleri; aXet'e uyarlandı.
> Önem eşlemesi, tip, otomasyon: `checklist-common.md` başlığı.
> **Önce yazma-öncesi liste:** `%sap-rap` references/checklists.md §A-§C. Behavior pool'un ana kaynağı managed senaryoda boştur;
> handler'lar CCIMP'tedir → incelemeden önce CCIMP çekilir ve BDEF ↔ `lhc_*` metotları eşlenir.
> Behavior pool sınıf kaynağı olduğu için `checklist-abap.md` de yürünür.

| ID | Ne kontrol edilir | Nasıl | Önem | Otomasyon | Kaynak ders |
|---|---|---|---|---|---|
| BE-26 | RAP handler (CCIMP) ya da ondan çağrılan yardımcı sınıf/FM'de `COMMIT WORK`, `ROLLBACK WORK`, `BAPI_TRANSACTION_COMMIT`/`ROLLBACK`, `COMMIT ENTITIES`, commit'li BAPI (`i_opt_commit`) → çalışma zamanında `BEHAVIOR_ILLEGAL_STATEMENT` dump; sözdizimi, ATC, aktivasyon geçer | Handler ve çağrılan sınıflarda (where-used zinciri) büyük/küçük harf duyarsız `commit work`, `rollback work`, `bapi_transaction_`, `commit entities` ara. Commit gereken BAPI → Z RFC FM + `DESTINATION 'NONE'` (ayrı LUW). Gerçek RAP dışı sınıf istisnası gerekçesiyle yazılır | BLOCKER | YOK — kaynaktaki deterministik commit doğrulayıcısı aXet'e taşınmadı | Ekip dersi (üç statik kontrolden geçip ilk çalıştırmada dump); `%sap-odata-backend` dpc-crud §4 |
| BE-20 | `READ ENTITIES … BY \_assoc FROM <key>` ile anahtar olmayan alan okunuyor → yalnız anahtarlar döner, diğer alanlar boş; validation/determination sessizce yanlış | `BY \_` + `FROM` kalıbını ara; anahtar dışı alan gerekiyorsa `ALL FIELDS WITH` ya da `FIELDS ( … ) WITH` | BLOCKER | YOK — kaynaktaki doğrulayıcı aXet'e taşınmadı | Ekip dersi |
| BE-60 | `validation … on save { delete; }` içinde `READ ENTITIES` → silinen örnek tamponda yok, okuma boş döner, kural hiç koşmaz, silme geçer | Delete tetikli validation gövdesinde `READ ENTITIES` ara; doğrudan `keys` tablosuyla çalışılmalı. Ayrıca `delete;` açık olup delete validation'ı olmayan entity'leri listele | BLOCKER | YOK | Ekip dersi (on validation'dan dokuzu yanlıştı); `%sap-rap` delete-guard.md §4 ve §7 |
| BE-62 | BDEF yorumunda ters tırnak (U+0060) → SAP her turda çoğaltır; sessiz ve büyüyen fark | BDEF kaynağında U+0060 ara | BLOCKER | `rap_bdef_creation` → `check_bdef_backtick.py` (BLOCKER) | Ekip dersi (iki kez yaşandı) |
| BE-11 | Audit alanları (created/changed by-at) var ama doldurma determination'ı yok ya da idempotent değil (yaratmada hepsi, güncellemede yalnız changed alanları) | BDEF'te determination + CCIMP'te guard'lı `IN LOCAL MODE` doldurma; root ve child | BLOCKER | `rap_bdef_creation` → `check_audit_fields_autofill.py` (WARNING — zincir bloklamaz, inceleme BLOCKER sayar) | Ekip dersi; `%sap-rap` behavior-impl §5 |
| BE-06 | BDEF'te alan eşlemesi (`mapping for`) eksik → interface/consumption aktivasyonu "mapped field" hatası | BDEF mapping ↔ CDS alanları | BLOCKER | YOK | Ekip dersi |
| BE-21 | Sonuç parametresi abstract entity olan action'da sonuç alanları `%param` altına yazılmamış → "No component exists" (aktivasyonda çıkar) | `RESULT` tanımı ↔ `APPEND VALUE #( %cid = … %param = … )` yapısı | BLOCKER | YOK | Ekip dersi |
| BE-24 | Released BO'ya `MODIFY ENTITIES … UPDATE/CREATE` yazılmadan önce operasyonun o BO'da açık olduğu doğrulanmamış ("operation is not activated", aktivasyonda çıkar) | Released BDEF'i `adt_get` ile oku; kapalıysa released OData API ya da released BAPI | BLOCKER | YOK | Ekip dersi; `%sap-odata-backend` outbound-api-call §2.4 |
| BE-08 | Unmanaged / statik action ile yazılan uzun metin kalıcı değil (tampon başarısı ≠ kayıt) | Yazma save aşamasında mı; kaydet → geri oku | BLOCKER | YOK | Ekip dersi |
| BE-09 | Released BO'da `CREATE BY \_assoc` ile semantik anahtar set edilmeye çalışılmış (salt okunur) → `<Key>ForEdit` alanı | Released projeksiyon CDS'ini `adt_get` ile oku, `editableFieldFor` alanını bul | BLOCKER | YOK | Ekip dersi |
| BE-17 | Released BO action / `editableFieldFor` çözümü aranmadan BAPI'ye ya da kapsam dışı yola kaçılmış | Projeksiyon CDS kaynağı okundu mu (rapor izi) | WARNING | YOK | Ekip dersi |
| BE-53 | EML tüketiminde `REPORTED` / `FAILED` mesajları tek genel mesaja indirgenmiş ya da yalnız ilk mesaj gösteriliyor; erken (MODIFY) ve geç (COMMIT) mesajlar ayrı toplanmamış | Hata tipli (E/A/X) tüm mesajlar toplanıp gösteriliyor mu | WARNING | YOK | Ekip dersi |
| BE-42 | Sanal element + SADL hesap çıkışı: `get_calculation_info` element adları büyük harf değil; `abap.string` cast; metin okuması çalışan bir okumadan alınmamış. Statik kontroller geçer | Kod okuması + canlı OData denemesi: CLI'de OData çağrı aracı yok → kullanıcı tarayıcıda `$select` ile dener; dump varsa `adt_dump_list` | BLOCKER | YOK | Ekip dersi |

## Bu dosyada ÇIKARILAN / DEĞİŞTİRİLEN
- Özel sınıf/servis adları ve vaka tarihleri çıkarıldı; OData canlı doğrulaması aXet araç sınırına göre kullanıcıya bağlandı.
- Managed ETag / lock master kuralı yazma-öncesi listededir (`%sap-rap` §B) ve yazma kapısında `rap_bdef_creation` → `check_rap_managed_etag.py` ile koşar (`validator-map.md` §2).
