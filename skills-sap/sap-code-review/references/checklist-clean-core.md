# Clean core inceleme satırları — released CDS/API, yetki kontrolü, ATC

> **Kaynak:** ekibin backend kod-inceleme kontrol listesi (BE kimlikleri korunmuştur), clean core dersleri ve SAP profil
> matrislerinin politika ekseni; `CC-NN` = aXet'te eklenen satır. Önem eşlemesi, tip, otomasyon: `checklist-common.md` başlığı.
> Yönlendirme, karar akışı ve harita bakımı: `clean-core.md`.
>
> **Profil kapsamı:** `ecc` → released CDS/API kavramı yok, bu dosya uygulanmaz · `s4_public`, `btp_abap` → released API
> zorunlu ve platform reddeder (satırlar erken yakalama içindir) · `s4_private` → `cleancore_policy`'ye göre.
> **Önem sütunu** `WARNING · strict: BLOCKER` ise `cleancore_policy: strict` projede BLOCKER'dır. Politika boşsa önem DOĞRULANMADI yazılır ve kullanıcıya sorulur.

| ID | Ne kontrol edilir | Nasıl | Önem | Otomasyon | Kaynak ders |
|---|---|---|---|---|---|
| BE-03 | Yeni ya da değişen okumada released halef varken ham standart tablo (`FROM` / `JOIN`) kullanılmış ve gerekçe kullanıcıya bildirilmemiş. Mevcut/eski koddaki ham tablo tek başına bulgu değildir (envanter; migrasyon proje kararı) | `released_successors.py lookup <TABLO>` + `adt_search_objects` / `adt_get` ile halefi oku; gerekçe raporda mı | WARNING · strict: BLOCKER | `cds_creation` → `check_released_objects.py` (WARNING); `cds_update` → `check_released_objects.py`; `rap_cds_creation` → `check_released_objects.py`; `class_push` → `check_released_objects.py` | Ekip dersi "released CDS proaktif"; profil politika ekseni |
| BE-68 | Ham tablo released halefe çevrilmiş; halefin `@AccessControl.authorizationCheck` değeri canlı okunmamış. `#CHECK` halef bir kontrolü/guard'ı besliyorsa yetki reddi 0 satır döner → kontrol fail-open. Tersi de bulgu: halef `#NOT_REQUIRED` ve guard beslemiyorsa "geçilmedi" savunması yetersiz | Halefi `adt_get` ile oku; okunan veri karar/guard besliyor mu; 0 satırda davranış ne | BLOCKER | YOK | Ekip dersi; `%sap-cds-ddic` cds.md CDS-DCL-02 |
| BE-67 | `#CHECK` taşıyan standart CDS'ten doğrudan okuma (ABAP `SELECT`, `READ ENTITIES`, SRVD `expose`): 0 satır dalı sessiz mi, guard fail-open mu, "oku → geri yaz" zinciri veriyi eziyor mu. Z view'in `FROM`/`JOIN`/association'ında kullanım tek başına bulgu değildir | Doğrudan okuma noktaları + `sy-subrc` / boş sonuç dalı + zincirin yazma adımı | BLOCKER | YOK | Ekip dersi; `%sap-cds-ddic` cds.md CDS-DCL-01 |
| BE-25 | Released CDS alan adı hatırdan yazılmış, canlı view kaynağıyla doğrulanmamış → "Unknown column" (aktivasyonda çıkar) | Kullanılan her released alan adını `adt_get` ile halef kaynağında bul | BLOCKER | YOK | Ekip dersi "eski sistem alan adları sistem bağımlı" |
| BE-31 | İş ortağı modeli tablolarına (`KNA1`, `LFA1` …) ham `SELECT` → ATC öncelik 1; salt okuma raporda da geçerli | Ham okuma ara; `I_Customer` / `I_Supplier` gibi halef; `adt_atc_check` sonucu | BLOCKER | Kısmi: `adt_atc_check` okuma aracı (zincirde değil, elle) | Ekip dersi "ATC öncelik 1 zorunlu" |
| CC-01 | Sınıf, arayüz ya da FM kullanımında released durumu yalnız tablo haritasına dayanılarak "temiz" sayılmış; tüm obje tipleri için otorite ATC "Usage of APIs" kontrolüdür | Değişen obje için `adt_atc_check`; `lookup` classes/functions/interfaces bölümü yalnız ipucu; ATC koşmadıysa DOĞRULANMADI | WARNING · strict: BLOCKER | Kısmi: `adt_atc_check` okuma aracı; `released_successors.py lookup` ipucu | Yazma kapısı validator'ının kapsam notu (yalnız tablo → CDS) |
| CC-02 | `cleancore_policy: strict` projede yeni klasik Dynpro ya da released olmayan API kullanımı | `sap-project.json` politikası ↔ değişen obje tipi ve çağrılan API'ler | BLOCKER | YOK | Profil politika ekseni (`strict`: klasik Dynpro politika gereği yasak, yalnız released API) |
| CC-03 | Halef haritası bayat (90 günden eski ya da S/4 sürüm yükseltmesinden sonra yenilenmemiş) ya da boş → validator eski bilgiyle öneri verir ya da hiç bakmadan geçer | `released_successors.py status` (çıkış 1 = bayat, 2 = veri hatası) | WARNING | Kısmi: `released_successors.py status` | Ekip dersi "boş haritayla aylarca sessiz geçiş"; kaynak yenileme tetiği |

## Bu dosyada ÇIKARILAN / DEĞİŞTİRİLEN
- Kaynakta HIGH olan BE-03 politikaya bağlandı: profil matrisi `s4_private`'ta released'ı tercih sayar, `strict`'te zorunlu kılar.
- Müşteri vakaları ve ATC varyant adı çıkarıldı (varyant proje bağlantısındadır).
