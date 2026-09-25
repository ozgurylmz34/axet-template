# Mock ortamı — freestyle SAPUI5 + OData V2 (RAP backend)

> **Hedef uygulama:** `%sap-ui5-fiori` ile kurulmuş freestyle uygulama (RAP servisinin OData V2 UI binding'ini tüketir;
> `ui/` npm workspace, `ui5-mock.yaml`, `webapp/localService/mainService/`). Fiori elements (V4) uygulaması bu skill'in
> kapsamı dışıdır.
> **Kaynak:** `@sap-ux/ui5-middleware-fe-mockserver` README'si ve `open-ux-odata` depo dokümanları (DefiningMockdata,
> core-concepts, value-help, MockserverAPI; 2026-09-21'de okundu) + aynı gün yapılan V2 ölçümü (aşağıda "ölçüldü").
> Paket sürümü değişince önce onun README'sine bak.

## 1. Paket ve script var mı
- Middleware OData **V2** isteklerini de karşılar (README: "OData v2/v4 requests"). **Ölçüldü (2026-09-21, ayrı ölçüm turu,
  V2 servis metadata'sı + kurgusal veri; bu dosyanın yazarı tekrarlamadı):** başlık ve kalem entity set'leri ile değer yardımı set'i HTTP 200 döndü, başlıktan
  kaleme navigasyon 2 kalem getirdi.
- İskelette paket workspace kökünde KURULUR (`%sap-ui5-fiori` → `references/app-skeleton.md` §3), ADI uygulamanın
  `package.json` `devDependencies`'inde de durur (§2 — UI5 CLI middleware'i yalnız uygulamanın kendi bağımlılıklarından
  çözer, ad yoksa `start-mock` açılmaz; ölçüldü). `start-mock` uygulama `package.json`'ındadır (§4). `kd_ortam.py check`
  ikisine de bakar; eksikte ne yapılacağını yazar, ekleme kullanıcı onayıyla yapılır (ad uygulamanın `package.json`'una
  yazılır, `npm install` yalnız `ui/` kökünde koşar).
- Eski freestyle uygulamalarda `webapp/localService/mockserver.js` (UI5'in kendi `MockServer`'ı) bulunabilir. Bu skill
  fe-mockserver yolunu izler; eski düzen varsa hangisinin kullanılacağı kullanıcıyla kararlaştırılır.

## 2. `ui5-mock.yaml` — SAP'ye bağlanmayan proxy + doğru servis
```yaml
server:
  customMiddleware:
    - name: fiori-tools-proxy
      afterMiddleware: compression
      configuration:
        ui5:
          paths:
            - path: /resources
              url: https://ui5.sap.com
            - path: /test-resources
              url: https://ui5.sap.com
            - path: /sap/public/bc/ui5_ui5/resources   # index.html bootstrap yolu → CDN
              url: https://ui5.sap.com
              pathReplace: /resources
        # backend: bloğu YOK — mock SAP'ye bağlanmaz
    - name: sap-fe-mockserver
      beforeMiddleware: csp
      configuration:
        mountPath: /
        services:
          - urlPath: '/sap/opu/odata/sap/<SERVIS>'
            metadataPath: './webapp/localService/mainService/metadata.xml'
            mockdataPath: './webapp/localService/mainService/data'
            generateMockData: true
```
(`fiori-tools-appreload` / `fiori-tools-preview` blokları `ui5.yaml`'daki gibi kalır.)

**Proxy kısmı neden böyle (ölçüldü 2026-09-25 · `@sap/ux-ui5-tooling` 1.32.0 · `@ui5/cli` 4.0.69 · fe-mockserver
2.4.17 · Chrome; iskelet `index.html`'i + çözülemeyen sahte backend adresiyle):**
- Üretici (`@sap-ux/mockserver-config-writer`) `ui5-mock.yaml`'ı `ui5.yaml`'ı KOPYALAYARAK yazar ⇒ `backend: /sap` bloğu
  gelir. `index.html`'in bootstrap'ı `/sap/public/bc/ui5_ui5/resources/sap-ui-core.js`'tir
  (`%sap-ui5-fiori` → `references/app-skeleton.md` §7) ⇒ bu blokla mock'ta istek SAP'ye gider: backend yokken `sap-ui-core.js` **500**,
  UI5 hiç yüklenmez, sayfa boş (kontrol grubu); backend erişilebilirken ise mock akışı SAP'ye bağlanır ve proxy SAP
  parolasını Windows kimlik deposunda arar. **`backend` bloğu silinir.**
- Yukarıdaki biçimle: `sap-ui-core.js` + `cldr/tr.json` **200**, `sap.ui.version` CDN'in güncel sürümü (ölçümde 1.152.0),
  tarih ve `DatePicker`/`DateRangeSelection` yer tutucusu Türkçe ("23 Eyl 2026", "Örneğin 22 Ara 2026-31 Ara 2026"),
  SAP'ye ve tarayıcıdan dışarıya istek **0**, mock OData 200.
- **Sürüm bilinçli olarak güncel sürümdür** (kullanıcı kararı 2026-09-25): `pathReplace` proxy'nin `version`
  ayarını yok sayar. Güncel sürüm CDN'den hiç silinmez; KD kareleri backend'den daha yeni UI5 ile çekilir (tema aynı,
  küçük görsel fark olabilir). Denenip elenenler: `pathReplace: /1.120/resources` (CDN'in minor takma adı) → core
  yüklendi ama kaynak kökünü yanlış hesapladı (`…/sap-ui-core.js/sap/ui/core/library.js` 404), sayfa boş · proxy
  `directLoad: true` → servis edilen `index.html`'deki bu `src`'yi DEĞİŞTİRMEDİ · tam patch (`/1.120.50/resources`)
  çalıştı ama CDN o patch'i silince sessizce İngilizceye düşme riski taşır (`%sap-ui5-fiori` → `app-skeleton.md` §7 ②).
- Kontrol: `grep -n "backend:" ui5-mock.yaml` → boş olmalı · `kd_ortam.py check` `backend:` satırını ve eşlemenin biçimini (path + `pathReplace: /resources`) METİN olarak denetler; `url`'nin doğru CDN olduğuna ve yolun gerçekten 200 döndüğüne bakmaz → §6 curl.

Servis kontrolleri (sırayla):
1. `urlPath` = `manifest.json` → `sap.app.dataSources.mainService.uri` (sondaki `/` dahil birebir). Kopyalanmış
   uygulamalarda eski servise bakması sık görülür → hiçbir istek mock'a düşmez ya da yanlış veri gelir.
2. `metadata.xml` **güncel** servisin metadata'sı mı: uygulamanın bağladığı entity set adları dosyada var mı
   (`grep 'EntitySet Name=' metadata.xml`). Dosya bayatlar (`%sap-ui5-fiori` → `references/app-skeleton.md` §11);
   güncel metadata'yı geliştirici tarayıcıdan kaydeder — bu akış SAP'ye bağlanmaz.
3. `mockdataPath` klasörü var mı. Yoksa `mock_veri.py --cikti` o klasörü hedefler.
4. `generateMockData: true` elle/`mock_veri.py` ile doldurulmayan varlıklar için genel veri üretir ("Sample Text",
   "Item 1" türü — core-concepts). Bu değerler **kareye girmemeli** (`gorsel-kontrol.md` G5): kareye giren her
   varlığın `<EntitySet>.json`'u olsun.
5. İsteğe bağlı: `watch: true` (veri/metadata değişince servis yeniden yüklenir), `logRequests: true` (hangi isteğin
   geldiğini görmek için; `?logs=true` ile de açılır). `watch` yoksa veri değişikliğinden sonra mock yeniden başlatılır.

## 3. Veri dosyaları
- Ad kuralı (core-concepts): `<EntitySetAdı>.json` — **entity type değil entity set adı**, büyük/küçük harf birebir.
  V2'de çoğunlukla `...Set` ile biter (`SalesOrderSet.json`). Yanlış ad = boş liste, hata mesajı yok.
- Biçim: JSON dizisi; alan adları metadata'daki `Property Name`'lerle birebir. Navigasyon (başlık → kalem) için kalem
  kayıtları başlığın anahtarını taşır; metadata'da `ReferentialConstraint` yoksa mock sunucu eşleştirmeyi gevşek yapar
  (README: `strictKeyMode`).
- `python <TEMPLATE>/skills-sap/sap-ui5-user-guide/scripts/mock_veri.py --metadata <metadata.xml> --cikti <mockdataPath>`
  her EntitySet için kurgusal Türkçe veri üretir: anahtarlar tekil, `ReferentialConstraint` varsa yabancı anahtarlar
  tutarlı, aynı `--tohum` aynı veriyi verir, var olan dosya `--zorla` olmadan ezilmez (elle düzeltilmiş dosya korunur).
  Üretilen veri **gözden geçirilir**: iş anlamı taşıyan alanlar (durum kodu, birim, para birimi) uygulamanın beklediği
  değerlerle eşleşmeli; eşleşmeyen değer ekranda boş metin ya da hata olarak görünür.
- Üretilen biçim: V2 tarihleri `/Date(<ms>)/`; `Edm.Decimal` JSON'a **sayı** olarak yazılır (V2 sunucusu string
  döndürür — ekranda biçim farkı görülürse değeri string'e çevir). Araç, `MaxLength`'e sığmadığı için kestiği
  değer yardımı / yabancı anahtar değerlerini raporda **KESİLEN** satırında `Set.Alan` olarak listeler — o alanları
  elle gözden geçir.
- Davranış değiştirmek gerekiyorsa aynı adla `.js` dosyası (MockserverAPI). V2'de entity set'e bağlı function import
  o set'in dosyasında `executeAction` olarak yazılır (DefiningMockdata). KD için çoğunlukla gerekmez — dolu durumu
  model verisi enjeksiyonuyla kurmak daha az iştir (`tuzaklar.md` T17).

## 4. Değer yardımı (F4 / VH) verisi
- Freestyle uygulamada F4 çoğunlukla aynı servisteki bir VH entity set'ine bağlıdır
  (`%sap-ui5-fiori` → `references/freestyle-odata-v2.md` §3). O set'e de veri dosyası konmazsa F4 penceresi **boş** açılır.
- Hangi set olduğunu view/fragment'taki binding yolu ya da controller'daki `read` çağrısı söyler; metadata'da
  `Common.ValueList` annotation'ı varsa `CollectionPath`'i.
- VH başka bir serviste ise `services` altına ikinci giriş (kendi `urlPath`, `metadataPath`, `mockdataPath`) —
  value-help dokümanındaki biçim.
- VH verisi ile ana varlıktaki değerler **aynı kodları** kullanır (F4'te seçilen kod listede görünen kayıtla eşleşsin).

## 5. Draft — yalnız servis draft'lıysa
Ekip standardında varsayılan **draft'sızdır** (freestyle V2 + JSON edit-buffer + sıralı update; karar
`%sap-rap` → `references/draft-and-locks.md`). Bu bölüm yalnız tüketilen servis draft'lıysa uygulanır:
- Metadata'da `IsActiveEntity`, `HasActiveEntity`, `HasDraftEntity` alanları görünür; her veri kaydı bunları taşır
  (core-concepts: etkin kayıtlar `IsActiveEntity: true`; taslağı gösterilecekse aynı anahtarla `false` olan ikinci kayıt).
- Ölçüldü (fe-mockserver 2.4.17, 2026-09-21): V2'de draft `Edit` function import'u mock'ta **simüle edilmiyor**;
  draft'sız V2 yolunda `MERGE` (güncelleme) çalışıyor. Draft'lı bir ekranın "düzenleme" karesi bu yüzden model verisi
  enjeksiyonuyla kurulur (`tuzaklar.md` T17); diğer draft aksiyonları **DOĞRULANMADI** — `logRequests` ile gözle.

## 6. Başlatma ve duman testi
```
npm run start-mock          # uygulama klasöründe, arka planda; portu logdan oku
curl -s "http://127.0.0.1:<port>/sap/opu/odata/sap/<SERVIS>/<EntitySet>?\$top=1&\$format=json"
curl -s -o NUL -w "%{http_code}\n" "http://127.0.0.1:<port>/sap/public/bc/ui5_ui5/resources/sap-ui-core.js"
curl -s -o NUL -w "%{http_code}\n" "http://127.0.0.1:<port>/sap/public/bc/ui5_ui5/resources/sap/ui/core/cldr/tr.json"
```
- İki bootstrap satırı da **200** olmalı; değilse kare çekilmez (§2). 500 = `ui5-mock.yaml`'da `backend` bloğu duruyor ya da
  eşleme yok; `tr.json` 404 = UI5 sessizce İngilizceye düşer, KD'deki tarih/ay adları İngilizce basılır.
- ⛔ Sunucu yalnız `127.0.0.1`'e bağlanmalı (`akis.md` §2 madde 4, `tuzaklar.md` T5).
- Arayüz Türkçe: giriş adresinde `?sap-ui-language=tr`.
- Port logdan alınır; aynı anda başka bir mock açıksa port artar ve tarayıcı yanlış uygulamaya gidebilir (`tuzaklar.md` T4).
- Kapatırken başlattığın süreci kapat (arka plan görevi ya da PID); başka birinin sunucusunu kapatma. ⚠ Arka plan
  görevini durdurmak yalnız kabuğu kapatabilir, `node` sunucusu yaşamaya devam eder (ölçüldü 2026-09-25: port hâlâ
  LISTENING, sonraki mock `EADDRINUSE` verdi ve ölçüm ESKİ sunucuya gitti). Kapattıktan sonra `netstat -ano` ile portun
  boşaldığına bak; doluysa oradaki PID'nin komut satırında kendi uygulama klasörün geçiyorsa o PID'yi kapat.
