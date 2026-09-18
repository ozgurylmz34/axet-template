# CDS ve DDIC inceleme satırları — CDS view, tablo, yapı, DTEL

> **Kaynak:** ekibin backend kod-inceleme kontrol listesi (kimlikler korunmuştur) + CDS dersleri; aXet'e uyarlandı.
> Önem eşlemesi, tip, otomasyon: `checklist-common.md` başlığı.
> **Önce yazma-öncesi liste:** `%sap-cds-ddic` references/checklists.md §1-§8 değişen objeler için yürünür (kimlikleri `CDS-…`,
> `DE-…`, `STR-…`, `TBL-…`). Yazma kapısının otomatik koştuğu maddeler: `validator-map.md` §2. Aşağıdakiler inceleme anında eklenir.

| ID | Ne kontrol edilir | Nasıl | Önem | Otomasyon | Kaynak ders |
|---|---|---|---|---|---|
| BE-27 | CDS fonksiyonu/özelliği desteği sürüm numarasından çıkarılmış (ör. `string_agg` view entity'de yok) | Sistemde aynı özelliği kullanan aktif bir örnek (`adt_grep_source`) ya da canlı aktivasyon kanıtı iste; sürüm çıkarımını kabul etme | BLOCKER | YOK | Ekip dersi; `%sap-cds-ddic` CDS-CAPA |
| BE-32 | `max`/`min`/`sum` UNIT ya da CUKY tipli alanda → aktivasyon reddi | Aggregate argümanları birim/para birimi alanı mı; alan `group by`'a alınır (UNION'da iki dal aynı) | BLOCKER | YOK | Ekip dersi; `%sap-cds-ddic` CDS-AGG |
| BE-33 | `union` içeren view entity başlığında `@Metadata.ignorePropagatedAnnotations: true` yok | `union` var ve annotation yok mu | WARNING | YOK | Ekip dersi; `%sap-cds-ddic` CDS-UNION |
| BE-38 | Klasik `define view` (sqlViewName) içinde view entity sözdizimi: `in (liste)`, aggregate içinde `cast`, UNION ikinci dalda `key`, `$projection` / `_assoc.alan` | DDL'de bu kalıpları ara; klasik görünümde `<>` zinciri, cast aggregate dışında, iki katlı view | WARNING | YOK | Ekip dersi |
| BE-45 | Association ON koşulunda başka association türevi (`_X.alan`) ya da association'dan türeyen bir `$projection` alanı → SDDL 515 / 061 | ON'daki her alan base tablo alanı mı; değilse ara view (base alan) ya da LEFT OUTER JOIN | BLOCKER | YOK — yalnız aktivasyon yakalar | Ekip dersi (başka view'dan kopyalanan desen kaynak farklıyken taşınmaz) |
| BE-59 | Ayraçlı iç içe `concat` → birinci argümanın sondaki boşluğu silinir, ayraç bozulur | Boşluklu literal ayraçla `concat` ara; `concat_with_space( …, 1 )` kullanılmalı; ifade çıktısıyla doğrula | WARNING | YOK | Ekip dersi; `%sap-cds-ddic` CDS-CONCAT |
| BE-61 | CDS DDL'de `"` ile yorum (SAP almaz, push "OK" der, canlı değişmez) ya da SRVD'de yorum (kaydederken silinir, repo canlıdan sapar) | CDS'te `"` yorum satırı; SRVD'de her türlü yorum; kanıt = yazma sonrası kaynak eşitliği | BLOCKER | YOK — kaynaktaki yorum sözdizimi doğrulayıcısı aXet'e taşınmadı | Ekip dersi (beş kontrol birden yeşil verdi) |
| BE-05 | Namespace'li DTEL (`/xyz/…`) DDL'de tek tırnaklı → sessizce düşer, "active differs" | Tablo/yapı DDL'inde tırnaklı DTEL adı ara; tırnaksız küçük harf; yazma sonrası `adt_get` | BLOCKER | YOK | Ekip dersi; `%sap-cds-ddic` TBL-DTEL |
| BE-07 | Satır içi kaynakla yaratılan CDS'in kaynağı boş kalmış (yaratma sonrası kaynak doğrulanmamış) | `adt_get include_source=true` ile kaynak içeriği | BLOCKER | YOK (BE-15 readback ile birlikte) | Ekip dersi |
| BE-13 | Yeni Z tablo, alan + DTEL + anahtar tasarımı gösterilip açık onay alınmadan yaratılmış | Raporda onay izi (kullanıcı mesajı) | BLOCKER | YOK | Ekip dersi; `%sap-cds-ddic` TBL-APPROVAL |
| BE-16 | Mevcut tablo alanı silinmiş, yeniden adlandırılmış ya da tipi değişmiş; tüketiciler ve veri kaybı ölçülmemiş | Diff'te alan kaybı/tip değişimi; where-used + etki listesi + kullanıcı kararı | BLOCKER | `table_update` → `check_table_field_drop.py` (BLOCKER; canlı SAP okur, bağlantısız ölçülemez) | Ekip dersi; `%sap-cds-ddic` TBL-DROP |
| BE-43 | Konfigürasyon/eşleme tablosuna join'de anahtarın ayırt edici bir alanı atlanmış (iki kayıt yalnız o alanla ayrışıyor) → çapraz kirlenme, sessiz yanlış veri | Konfigürasyon tablosunun anahtarı ↔ join ON alanları; canlı konfigürasyonda yalnız o alanla ayrışan kayıt var mı (`adt_table_read`) | BLOCKER | YOK — aktivasyon geçer, yanlış veri olarak çıkar | Ekip dersi (genelleştirildi) |

## Bu dosyada ÇIKARILAN / DEĞİŞTİRİLEN
- BE-43 müşteriye özgü konfigürasyon tablosu vakasından genel kurala çevrildi.
- AMDP gövdesi satırı (BE-28) sınıf kaynağında incelendiği için `checklist-abap.md` §F'dedir.
- Clean core ve yetki (DCL) satırları: `checklist-clean-core.md`.
