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
- İskelette paket workspace kökünün geliştirme bağımlılığıdır (`%sap-ui5-fiori` → `references/app-skeleton.md` §3:
  `@sap-ux/ui5-middleware-fe-mockserver`), `start-mock` uygulama `package.json`'ındadır (§4). `kd_ortam.py check`
  ikisine de bakar; eksikte kurulum komutunu yazar, ekleme kullanıcı onayıyla yapılır (README:
  `npm install --save-dev @sap-ux/ui5-middleware-fe-mockserver` — workspace'te `npm install` yalnız `ui/` kökünde).
- Eski freestyle uygulamalarda `webapp/localService/mockserver.js` (UI5'in kendi `MockServer`'ı) bulunabilir. Bu skill
  fe-mockserver yolunu izler; eski düzen varsa hangisinin kullanılacağı kullanıcıyla kararlaştırılır.

## 2. `ui5-mock.yaml` — doğru servis
README'deki biçim (yollar iskeletin düzenine uyarlandı):
```yaml
server:
  customMiddleware:
    - name: sap-fe-mockserver
      mountPath: /
      afterMiddleware: compression
      configuration:
        services:
          - urlPath: '/sap/opu/odata/sap/<SERVIS>'
            metadataPath: './webapp/localService/mainService/metadata.xml'
            mockdataPath: './webapp/localService/mainService/data'
            generateMockData: true
```
Kontroller (sırayla):
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
```
- ⛔ Sunucu yalnız `127.0.0.1`'e bağlanmalı (`akis.md` §2 madde 4, `tuzaklar.md` T5).
- Arayüz Türkçe: giriş adresinde `?sap-ui-language=tr`.
- Port logdan alınır; aynı anda başka bir mock açıksa port artar ve tarayıcı yanlış uygulamaya gidebilir (`tuzaklar.md` T4).
- Kapatırken başlattığın süreci kapat (arka plan görevi ya da PID); başka birinin sunucusunu kapatma.
