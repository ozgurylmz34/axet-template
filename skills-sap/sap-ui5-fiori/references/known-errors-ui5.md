# UI5 bilinen hatalar — belirti → bölüm

> Belirtiyi ara (konsol metni, HTTP kodu, kullanıcının cümlesi), ilgili bölümü oku. Tanıdık bir belirtide önce `%recall`.
> Backend kaynaklı belirtiler (RAP kilidi, validation mesajı kesilmesi, `$filter` 400'ün backend yarısı) ilgili skill'e yönlendirilir.

---

## Açılış / bootstrap

| Belirti | Sebep | Git |
|---|---|---|
| Beyaz ekran, `this.oLocaleData.getDatePlaceholder is not a function` | UI5 bootstrap sürümsüz CDN'den (latest) + `tr`: core ↔ locale-data uyumsuz | `app-skeleton.md` §7 |
| Tarih/ay adları İngilizce ("Sep 21, 2026"), konsolda anlamlı hata yok; aynı uygulama FLP'den açılınca doğru | `index.html` UI5'i dış CDN'de sabitlenmiş bir patch'ten yüklüyor; patch bakım dışı kalınca silinmiş, silme yarım: `sap-ui-core.js` 200 ama `cldr/<dil>.json` 404 → UI5 sessizce `en`'e düşer. Bölge ayarı / tarayıcı önbelleği / `ui5.yaml` proxy'si değil (mutlak CDN adresi proxy'ye uğramaz). Kanıt: kaynak dosyaları tek tek HTTP ile yokla (CDN'de `cldr/<dil>.json` 404 ↔ backend'de 200) | `app-skeleton.md` §7 · `checklists.md` FE-46 |
| Sayfa boş, konsolda `sap-ui-core.js` **500** (ya da zaman aşımı); `start-mock` ya da VPN kapalıyken `start-noflp` | `index.html` UI5'i backend'in kendi yolundan (`/sap/public/bc/ui5_ui5/…`) yükler; bu yol `ui5*.yaml`'daki `backend: /sap` proxy'siyle SAP'ye gider — backend'e ulaşılamıyorsa UI5 hiç yüklenmez. Mock'ta: üretici `ui5-mock.yaml`'ı `ui5.yaml`'dan kopyaladığı için `backend` bloğu da gelmiştir (ölçüldü). Kanıt: `curl -s -o NUL -w "%{http_code}" http://127.0.0.1:<port>/sap/public/bc/ui5_ui5/resources/sap-ui-core.js` | mock: `%sap-ui5-user-guide` → `mock-ortam.md` §2 (`backend` yok + CDN eşlemesi) · canlı: VPN/backend erişimi · `app-skeleton.md` §7 |
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
| TR/DE yerelde `Edm.Decimal` "14.000" → **14000**, "0.500" → boş, "-5.000" → -5000; konsolda `grouping and decimal separator both have the same value '.'`; İngilizce yerelde (mock varsayılanı) görünmez | `sap.ui.model.type.Float` + `formatOptions.source` içinde `decimalSeparator: '.'` var, `groupingSeparator` yok → eksik seçenek yerelden gelir, ikisi de `.` olur | `source: {}` (boş) ya da ikisi birden (`groupingSeparator: ','` + `decimalSeparator: '.'`) ya da `sap.ui.model.odata.type.Decimal` + constraints (`freestyle-odata-v2.md` §5.1); biçim testini `data-sap-ui-language="tr"` ile kesirli + 0 + eksi değerle yap |
| Dar ekranda m.Table kolonu harf harf kırılıyor, satır uzuyor | genişliksiz "esnek" kolon sabit toplam aşınca 0 px | `list-grid-alv.md` §7 |
| Detay paneli seçim yapılmadan açık / seçince dolmuyor | `setData` eksik şekil | `freestyle-odata-v2.md` §2.2 |
| Metindeki `{AD}` gibi yer tutucu ekranda boş ("ör. , ."), hata yok | Yapıcı ayarına verilen dize (`new Text({ text: s })`) **bağlama** olarak ayrıştırılır; `{…}` model yolu sanılır | Çalışma anında üretilen / i18n'den gelen ve `{` içerebilen metni setter'la ver (`new Text().setText(s)`); paylaşılan metin yardımcısının testine `{` içeren metin koy |
| Onay diyaloğu Esc ile kapatılınca ekran kilitli kalıyor (meşgul bayrağı inmiyor), konsolda `TypeError` | Promise sarmalı onay yardımcısında `afterClose` önce `destroy()` sonra sözü sonuçlandırıyor → kapanmış diyalogda `getOpenState`, söz hiç sonuçlanmaz | `afterClose`: önce `bitir(false)` sonra `destroy()`; `bitir` tek girişli ve `close()`'u yalnız `!bIsDestroyed && isOpen()` iken çağırır. Üç kapanış yolunu (düğme · Esc · programla) test et: söz tam bir kez sonuçlanır, bayrak iner |
| UI5 sürümüne bağlı kontrol açılmıyor (modül 404), ya da tema düz/stilsiz | Kontrolün `@since`'ı backend'den büyük · yalnız 200'e bakılarak seçilen sahte `sap_horizon` | `app-skeleton.md` §7.1 · FE-53 |
| Toplu (script/regex) düzenlemeden sonra view/fragment render'da bozuk, git diff küçük görünüyor | "Etiket sonuna kadar" deseni binding'deki `>`'de (`{model>/yol}`) erken kapandı; yeni attribute değerin ortasına yazıldı | `runtime-verification.md` §2 |

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
| Geri tuşu uygulamadan çıkmıyor, aynı sayfaya dönüyor (guard yönlendirmesi) | BaseController `navTo` sarmalayıcısı `bReplace`'i iletmiyor | `app-skeleton.md` §9 |
| İki koleksiyon birleşince tüm alanlar boş, hata yok | Sıfır dolgusu ("10" ↔ "000010") | §5.6 |
| İki client aynı tarayıcıda açıkken bir sekmede yanlış veri (varyant listesi, yükleme, kaydet öbür client'a gidiyor); tek sekmede sorun yok; hata yok | Elle kurulan model/istek `sap-client` taşımıyor, tarayıcının tek `sap-usercontext` çerezine göre yönleniyor. Kanıt: iki client + ayırıcı veri + ağ izinde `sap-client` | §7.4 · `checklists.md` FE-48 |
| Belge kilidi sayfadan ayrılınca bırakılmıyor, başkası zaman aşımına kadar bekliyor; konsolda hata yok | Bırakma unload'da senkron XHR ile gidiyor (Chromium göndermez, `try/catch` yutar) ya da URL'de `/` eksik (307 → 403) | §7.5 · FE-49 |

## Value-help / filtre / liste

| Belirti | Sebep | Git |
|---|---|---|
| F4 seçimi ekrana yansımıyor | Yalnız binding'e güven / 3 nokta uyumsuzluğu | `freestyle-odata-v2.md` §3 C1, C5 |
| F4 seçimi başka alana yazılıyor | Sabit yazma hedefi | §3 C4 |
| Kod görünüyor, ad yok | `<X>Name` expose değil | §3 C2 |
| VH dialog açılıyor, liste boş | VH entity set serviste expose değil | §3 C6 · `%sap-rap` |
| Geçersiz elle girilen kod kaydediliyor | Doğrulama + save guard yok | §3 C7 |
| Arama hiç sonuç vermiyor / `400 Function toupper/tolower is not supported` | `caseSensitive:false` | `list-grid-alv.md` §6.2 · `%sap-odata-backend` filter-search §1 |
| Uzun terimde arama "bulunamadı", kısa terimde çalışıyor (ağda 400) | OR zincirinde terim bir alanın `MaxLength`'inden uzun | `list-grid-alv.md` §6.2 |
| Türkçe ad (i/ı/İ) aranınca bulunmuyor | Sunucu harf sınıfı tam Türkçe değil | `list-grid-alv.md` §6.2 |
| Elle yazılan filtre değeri yok sayılıyor, rapor daha geniş sonuç döndürüyor | `MultiInput`'ta validator yok, token oluşmuyor | `list-grid-alv.md` §6.1 |
| VH koşul sekmesinde küçük harfli değer → 0 satır, hata yok | Range değeri büyük harfe çevrilmiyor | `list-grid-alv.md` §6.1 |
| "Hariç tut" ile girilen değer sonuçta duruyor | `exclude` aralığı seçim kurucuda sessizce atlanıyor | `list-grid-alv.md` §6.1 |
| Tarih aralığı "12 ayı aşıyor" hatası 01.01–31.12'de | `secondDateValue` gün sonu (23:59:59) | `list-grid-alv.md` §6.1 |
| Filtre girilmeden (doğrudan URL / F5) liste filtresiz istek atıyor | `suspended: true` binding render'da yine okur | `list-grid-alv.md` §2 |
| Filtre koşulu uygulanmıyor ("75 ile başlar") | `P13nDialog`/`P13nFilterPanel` | `list-grid-alv.md` §1 |
| Route'ta çökme (`t.done`) | `TablePersoController` | `list-grid-alv.md` §1 |
| Silme sonrası başka satır seçili görünüyor / yanlış kayıt silindi | Seçim bayatlaması | `delete-flow-ui.md` §1 |
| Scroll ederken seçim kayboluyor | Temizlik `rowsUpdated`'a bağlı | `delete-flow-ui.md` §1 |
| Başlık değişikliği silme sonrası kayboldu | Pending guard başlığı kapsamıyor | `delete-flow-ui.md` §2 |
| Ok tuşuyla gezinirken miktar değişiyor | `type="Number"` | `freestyle-odata-v2.md` §5.4 |
| Playwright `click()` sonrası hiçbir şey olmuyor | Harness artefaktı | `runtime-verification.md` §4.2 |
| Otomasyonda Ctrl+A seçim olayı üretmiyor | Hücreye tık yolu; odak (`focus()`) yolu olay üretir | `runtime-verification.md` §4.2 |
| Playwright doğrudan BSP adresinde 401, kimlik doğru | `httpCredentials` önden göndermiyor | `runtime-verification.md` §4.6 |
| Sanal grid'de DOM satır sayısı yanlış | Sanal satırlar | `runtime-verification.md` §4.3 |
| Kolon filtre kutusuna `>100` / `75*` yazılınca filtre uygulanmıyor, uyarı çıkıyor | Tasarım gereği: kutu düz arama; koşul **Filtre…** penceresinden seçilir | `list-grid-alv.md` §6.4 |
| Arama/öneri listesinde aranan kayıt "yok", backend'de var | Sunucu `$top`suz okumada sayfalar (ölçülen 100), istemci yalnız ilk sayfada aradı | FE-54 · `$top`/`$skip` ya da `d.__next` |
| Instance action **428** (`SADL_ENTITY_RUNTIME/006`), MERGE geçiyor | `callFunction` `If-Match`'i yalnız `mParameters.eTag` verilirse ekler | FE-55 |
| Mükerrer anahtarla yaratmada genel hata şeridi ("kayıt zaten var" değil) | Çakışma dalı yalnız 409'a bakıyor; managed BO 400 `MC_CSP_USR_RUNTIME/006` döndü | FE-56 |
| Çok alanlı arama custom entity'de 500 | Alanlar arası `or` + sağlayıcıda `get_as_ranges` | FE-57 · `%sap-code-review` BE-89 |
| `MessageBox` butonunda `firePress()` sonrası diyalog açık kalıyor, akış ilerlemiyor | MessageBox'ta `firePress` `onClose`'u tetiklemedi (normal butonun tersi) | `runtime-verification.md` §4.2 |
| Mock'ta If-Match'li `$batch` isteği sahte **412** | UI5 MockServer `$batch` başlığını `:`'dan böler; `:` içeren ETag kesilir (gerçek Gateway değil) | Mock ETag'ini `:`'sız üret (ör. yalnız rakam); 412'de önce başlığın kesilip kesilmediğine bak |
| UI testi yeşil, ekranda öğe görünmüyor / filtre çalışmıyor | DOM varlığı ≠ görünürlük · olay parametre adı tahmin · test düzeneği üretim kodunu kopyalıyor · son kontrol kirli modeli okuyor | `runtime-verification.md` §4.3 |
| `AnalyticalTable` boşalıyor / grup ara toplamları kayboldu / Excel filtresiz | 1.120 analitik binding tuzakları | `list-grid-alv.md` §4.1 |

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
| Deploy yarıda durduruldu, "hiçbir şey yazılmadı" sanıldı | BSP (`WAPA`) + ICF düğümleri yaratılmış, nesne transport görevine yazılmış olabilir | `deploy-and-local-run.md` §4 |
| Maket/yerel çalıştırmada CDN sürümü "var" (`sap-ui-version.json` 200) ama kütüphaneler 404 | Sürüm dosyası kütüphanelerin dağıtıldığını kanıtlamaz | Kullanılacak kütüphane dosyasını (`sap/m/library.js`) ölç, tarayıcıda 404 say. Teslim edilen uygulama CDN kullanmaz (`app-skeleton.md` §7) |

---

## Bu dosyada ÇIKARILAN / DEĞİŞTİRİLEN
- Kaynaktaki bilinen hatalar kaydının UI5 maddeleri (SmartFilterBar filterable, `sap.f` 404, annotation 400, i18n
  fallback) ve playbook semptom tabloları tek indekste birleştirildi; kaynaktaki "syntax check yanlış hata raporu" maddesi
  ADT konusudur, alınmadı.
- Her satır bu skill'in referanslarına işaret eder; dış bağlantı yok.
- 2026-09-25 eşitleme (ekip dersi): Render tablosuna toplu XML düzenleme satırı eklendi; kaynaktaki dosya/ekran adları alınmadı.
- 2026-10-19 eşitleme (ekip dersleri): Float source, m.Table esnek kolon, `navTo` sarmalayıcısı, arama `MaxLength`/Türkçe
  harf sınıfı, MultiInput validator, VH küçük harf, "hariç tut" düşmesi, tarih aralığı gün sonu, askıdaki binding, Ctrl+A ve
  BSP 401 satırları eklendi; kaynaktaki uygulama/dosya adları alınmadı.
- 2026-11-17 (uyum turu 8, ekip dersleri + FE-53..57): yapıcıda `{…}` bağlaması, onay diyaloğu Esc kilidi, sürüme bağlı
  kontrol/tema, kolon filtre kutusu reddi, sunucu sayfalaması, action 428, mükerrer anahtar 400, alanlar arası `or` 500,
  MessageBox `firePress`, MockServer ETag `:`, test kör noktaları, AnalyticalTable, kesilen deploy ve CDN maket sürümü
  satırları eklendi. Kaynak derslerdeki Git Bash `kill` / `rg` yan notları UI konusu olmadığı için alınmadı.
