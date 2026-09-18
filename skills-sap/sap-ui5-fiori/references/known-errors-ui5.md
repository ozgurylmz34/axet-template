# UI5 bilinen hatalar — belirti → bölüm

> Belirtiyi ara (konsol metni, HTTP kodu, kullanıcının cümlesi), ilgili bölümü oku. Tanıdık bir belirtide önce `%recall`.
> Backend kaynaklı belirtiler (RAP kilidi, validation mesajı kesilmesi, `$filter` 400'ün backend yarısı) ilgili skill'e yönlendirilir.

---

## Açılış / bootstrap

| Belirti | Sebep | Git |
|---|---|---|
| Beyaz ekran, `this.oLocaleData.getDatePlaceholder is not a function` | UI5 sürümü sabit değil (CDN latest) + `tr` | `app-skeleton.md` §7 |
| `Component yüklenemedi: failed to resolve 'com/.../model/models'` | Namespace'in eğik çizgi biçimi değişmemiş | `app-skeleton.md` §1 |
| Model `undefined`, binding çalışmıyor | Manifest modeli eksik / Component bağımlılığı eksik | `app-skeleton.md` §8–9 |
| `{ui>/busy}`, `{ui>/filter}` ölü; busy dönmüyor, filtre tutmuyor | Manifest JSONModel `settings.data` çift sarmalama | `app-skeleton.md` §8 |
| `$metadata` / annotation yüklemesi 400 | Kayıtsız annotation adresi manifest'te | `app-skeleton.md` §8.1 |
| `sap.f.DynamicSideContent` 404 | `sap.f` yüklenmiyor | `app-skeleton.md` §12 |
| TR'de eski etiket, İngilizce dosya doğru | `i18n_tr.properties` güncellenmemiş / tarayıcı önbelleği | `freestyle-odata-v2.md` §9 |
| Ekranda ham anahtar ("btn.cols") ya da boş etiket | i18n anahtarı tanımsız | `freestyle-odata-v2.md` §9 · `check_i18n_keys.py` |
| Diyakritiksiz metin ("Secili") | TR dosyasında anahtar yok, varsayılan dosya ASCII | `freestyle-odata-v2.md` §9 |
| Konsolda `Component-preload.js 404`, `favicon 404`, locale uyarısı | Dev modda normal | `runtime-verification.md` §5 |
| SmartFilterBar'da satış org./kanal/bölüm görünmüyor | CDS/SADL property'si filterable değil | `app-skeleton.md` §12 |

## Render

| Belirti | Sebep | Git |
|---|---|---|
| View render çöker "not valid for aggregation" | `core:Title` VBox/HBox çocuğu | `freestyle-odata-v2.md` §4 T3 |
| Dialog/view hiç açılmıyor, "Element sap.m.HBox is not a valid Form content" | Form/ColumnLayout içinde container | `freestyle-odata-v2.md` §4 T4 |
| `CheckBox "" is of type string, expected boolean` | CHAR1 bayrak doğrudan `selected` | `freestyle-odata-v2.md` §5.2 |
| Parse hatası (`CX_SXML_PARSE_ERROR`) sayı/tarih alanında | OData tipi yok | `freestyle-odata-v2.md` §5.1 |
| Miktar "14.000 ADT" | Formatter yok | `freestyle-odata-v2.md` §5.5 |
| Detay paneli seçim yapılmadan açık / seçince dolmuyor | `setData` eksik şekil | `freestyle-odata-v2.md` §2.2 |

## Save / OData

| Belirti | Sebep | Git |
|---|---|---|
| `Resource not found for segment '_Item'` / Create kaydı boş / `$expand` boş | V2 nav `_X` | `freestyle-odata-v2.md` §2.1 |
| Kaydet'e basınca tepki yok | Nav yoluna `createEntry` | §1 S3 |
| İlk Kaydet'te bir şey olmuyor, ikincide oluyor | `hasPendingChanges()` ön kontrolü / commit bariyeri yok | §1 S9, §1.2 |
| Busy sonsuz dönüyor, ne başarı ne hata | Callback garantisiz save karışımı | §1 (`_runSeq`), §1.4 |
| "Kaydedilemedi" / "bloke edildiği için düzenlenemez" ama işlem kısmen oluyor | Paralel işlem, BO kilidi | §1 S2 · `delete-flow-ui.md` §3 |
| Programatik atanan değer kaydedilmiyor | `setProperty` + `submitChanges` | §1 S1 |
| Kalem değişikliği kaydedince geri dönüyor | Mevcut kalem UPDATE'i yok | §1 S4 |
| Başlık kaydoluyor, kalem "Kaydedilemedi" | Payload'da canlı metadata'da olmayan property | §8 |
| MERGE 400 (tüm gövde) | Salt-okunur `*Name`/`*Text` gövdede / boş tarih `""` | §1 S6–S7 |
| `Conversion error for property '<X>' at offset N` | Tarih string gönderildi | §5.3 |
| `Failed to read property '<X>' at offset N` | Edm.Boolean'a `'X'` | §5.3 |
| `400 Invalid parameter` (function import) | Metadata'da olmayan parametre | §7.2 |
| `405 Method Not Allowed` | `read` beklenen yere `callFunction POST` (ya da tersi) | §7.2 |
| `oData.Field` undefined (FI sonucu) | `[1]` sonuç sarmalayıcısı | §7.1 |
| "Kaydedilemedi" ama neden yok | Generic hata metni, `_parseError` yok | §6.2 |
| İkinci hata satırı hiç görünmüyor | Parser yalnız `error.message.value` okuyor | §6.2 |
| Tekrar denemede 404, save kalıcı kilitli | Kısmi başarı sonrası resync yok | §1 S10 |
| Birden çok yeni kalem aynı anahtarla | Thunk kapanış tuzağı | §1 S11 · `delete-flow-ui.md` §3 |
| Toast görünmüyor ("mesaj gelmedi") | `MessageToast` + hemen `navTo` | §6.1 |
| İki koleksiyon birleşince tüm alanlar boş, hata yok | Sıfır dolgusu ("10" ↔ "000010") | §5.6 |

## Value-help / filtre / liste

| Belirti | Sebep | Git |
|---|---|---|
| F4 seçimi ekrana yansımıyor | Yalnız binding'e güven / 3 nokta uyumsuzluğu | `freestyle-odata-v2.md` §3 C1, C5 |
| F4 seçimi başka alana yazılıyor | Sabit yazma hedefi | §3 C4 |
| Kod görünüyor, ad yok | `<X>Name` expose değil | §3 C2 |
| VH dialog açılıyor, liste boş | VH entity set serviste expose değil | §3 C6 · `%sap-rap` |
| Geçersiz elle girilen kod kaydediliyor | Doğrulama + save guard yok | §3 C7 |
| Arama hiç sonuç vermiyor / `400 Function toupper/tolower is not supported` | `caseSensitive:false` | `list-grid-alv.md` §6.2 · `%sap-odata-backend` filter-search §1 |
| Filtre koşulu uygulanmıyor ("75 ile başlar") | `P13nDialog`/`P13nFilterPanel` | `list-grid-alv.md` §1 |
| Route'ta çökme (`t.done`) | `TablePersoController` | `list-grid-alv.md` §1 |
| Silme sonrası başka satır seçili görünüyor / yanlış kayıt silindi | Seçim bayatlaması | `delete-flow-ui.md` §1 |
| Scroll ederken seçim kayboluyor | Temizlik `rowsUpdated`'a bağlı | `delete-flow-ui.md` §1 |
| Başlık değişikliği silme sonrası kayboldu | Pending guard başlığı kapsamıyor | `delete-flow-ui.md` §2 |
| Ok tuşuyla gezinirken miktar değişiyor | `type="Number"` | `freestyle-odata-v2.md` §5.4 |
| Playwright `click()` sonrası hiçbir şey olmuyor | Harness artefaktı | `runtime-verification.md` §4.2 |
| Sanal grid'de DOM satır sayısı yanlış | Sanal satırlar | `runtime-verification.md` §4.3 |

## Lokal çalıştırma / deploy

| Belirti | Sebep | Git |
|---|---|---|
| Kullanıcı/parola popup döngüsü, logda `lrep`/varyant 401 | Flexibility + varyant servisi | `deploy-and-local-run.md` §1.1 (a) |
| Popup ısrarlı, logda yalnız `$metadata` 401 | **Hesap kilidi** — deneme yapma | §1.1 (b) |
| Doğru kimlikle sonsuz 401 | Alias host | `app-skeleton.md` §6 |
| "Deployment Successful" ama canlıda eski | Build'siz deploy / bayat `dist` | `deploy-and-local-run.md` §3.1 |
| Deploy 401 | CLI argümanıyla parola / sondaki `\r` / kilit | §3.3 |
| `400 "Type of file X is unknown"` | Stray/gizli dosya, `.svg`/`.woff` | §4 |
| `code 3221226505` (build başarılı, deploy çöker) | npm workspace + `npm run deploy` zinciri | §3.4 |
| "application name must be prefixed with [ZZ1_]" | Yumuşak uyarı (kaynak sistemde) | §2 |
| Kılavuz sayfası bayat ama `verify` OK | Statik varlık preload'da değil | §5 |
| Statik varlık kıyası 12/12 bayat | Enjekte meta, ham bayt kıyası | §5 |
| Başka süreçler de kapandı | `taskkill /IM node.exe` | §1.3 |

---

## Bu dosyada ÇIKARILAN / DEĞİŞTİRİLEN
- Kaynaktaki bilinen hatalar kaydının UI5 maddeleri (SmartFilterBar filterable, `sap.f` 404, annotation 400, i18n
  fallback) ve playbook semptom tabloları tek indekste birleştirildi; kaynaktaki "syntax check yanlış hata raporu" maddesi
  ADT konusudur, alınmadı.
- Her satır bu skill'in referanslarına işaret eder; dış bağlantı yok.
