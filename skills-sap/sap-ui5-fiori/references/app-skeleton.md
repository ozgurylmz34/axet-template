# Uygulama iskeleti — workspace, tooling, manifest, bootstrap

> Kapsam: yeni bir freestyle UI5 uygulamasının (OData V2) **kod yazmadan önceki** iskeleti. Save/binding/value-help
> mekaniği `freestyle-odata-v2.md`, liste ekranı `list-grid-alv.md`, çalıştırma ve deploy `deploy-and-local-run.md`.
> Örneklerdeki adlar demodur: servis `ZXX001_UI_ORDER_O2`, app ID `com.example.<alan>.<uygulama>`, sistem
> `<SAP_HOST>:<PORT>`, client `<CLIENT>`, UI5 sürümü `<UI5_VERSION>` (= backend'in UI5 sürümü, **ölçülür** — §7.1).
> **Yeni uygulama şablondan başlar:** `templates/ui5-freestyle/` (ortak gövde + 1.71 / 1.120 sürüm parçası; README
> §1 kopyalama sırası). Bu dosya şablonun dayandığı kuralları anlatır.

---

## 1. Adlandırma

| Öğe | Kural |
|---|---|
| App ID | `com.example.<alan>.<uygulama>` biçimi (proje kendi kök alanını kullanır) |
| BSP (ABAP repository) adı | müşteri ad alanında: `Z`/`Y` ya da projede bildirilmiş `/<NS>/` (`sap-project.json` → `customer_namespaces`); **en çok 15 karakter** (`ZXX001_ORDER` ✅, `ZXX001_ORDER_APPLICATION` ❌). `deploy_ui.py prepare` denetler (`deploy-and-local-run.md` §2) |
| CSS sınıf öneki | uygulama/paket koduna göre (`zxx001FieldDesc` gibi) |

App ID değişirse aynı değer şu yerlerde birlikte değişir: `manifest.json` `sap.app.id`, `index.html`
`data-sap-ui-resource-roots` + `data-name`, `ui5.yaml` `metadata.name`, tüm `controllerName`/`extend` çağrıları, i18n
`bundleName`. **Nokta biçimi (`com.x.y`) ile birlikte eğik çizgi biçimi (`com/x/y`) de aranır** — `sap.ui.define`
bağımlılık dizileri eğik çizgi kullanır; yalnız nokta biçimini değiştirmek "Component yüklenemedi: failed to resolve
'com/.../model/models'" hatası verir.

## 2. npm workspace — paket `ui/` kökü

Paketin `ui/` klasörü **ilk uygulamadan itibaren** npm workspace köküdür (uygulama sayısı baştan belli olmasa da çoklu
varsayılır; tek uygulamada maliyeti yoktur, ikinci uygulama gelince yeniden yapılandırma gerekmez).

```json
// <paket>/ui/package.json — workspace kökü
{ "private": true, "workspaces": ["*"], "devDependencies": { /* §3 ortak set */ } }
```

- Yeni uygulama `ui/<app>/` altına; uygulamanın `package.json`'u **sade**: `name` + `scripts` + `ui5*.yaml`'ların
  kullandığı middleware paketlerinin **adları** `devDependencies`'te (sürümleri kökteki §3 setiyle aynı):
  ```json
  { "name": "<app>", "private": true, "scripts": { /* §4 */ },
    "devDependencies": { "@sap/ux-ui5-tooling": "1", "@sap-ux/ui5-middleware-fe-mockserver": "2" } }
  ```
  Paketler yine yalnız kökte kurulur (hoist). **Neden adlar gerekli (ölçüldü, `@ui5/cli` 4.0.69 ·
  `@sap/ux-ui5-tooling` 1.32.0):** UI5 CLI `customMiddleware`'i (`fiori-tools-proxy`, `sap-fe-mockserver` …) yalnız
  **uygulamanın kendi** `package.json` bağımlılıklarından çözer; `devDependencies` boş uygulamada `start-noflp` ve
  `start-mock` açılmaz: `Could not find custom middleware fiori-tools-proxy`. Adlar eklenince, uygulama klasöründe
  kurulum yapılmadan sunucu açıldı (kontrol grubu). Aynı sonuç başka bir kurulumda `@ui5/cli` 4.0.57'de de görüldü.
  **Sınır:** UI5 CLI 3.x · build/deploy script'leri · adları ekledikten sonra kökte yeniden `npm install` gerekip
  gerekmediği **ÖLÇÜLMEDİ** — şüphede kurulumu kökte koş. Bin'in (`ui5`) bulunması middleware'in bulunması demek değildir.
  `%sap-ui5-user-guide` `kd_ortam.py check` de mockserver adını uygulamanın `package.json`'unda arar.
- **`npm install` yalnız `ui/` kökünde.** Uygulama klasöründe `npm install/ci/add` = gereksiz ikinci `node_modules`.
  Uygulamaya yeni bir middleware eklenince adı uygulamanın `package.json`'una elle yazılır, kurulum kökte koşar.
  `npm run start-noflp` bin'i üst klasördeki `ui/node_modules/.bin`'den çözer.
- `node_modules` git'e girmez; **yalnız kök `ui/package-lock.json`** izlenir, uygulama başına lock dosyası olmaz.
- ⚠ `npm install` global değil ama ağdan paket indirir: model bunu kullanıcıya söyleyip onayla koşar.

## 3. Ortak devDependencies

```json
{
  "devDependencies": {
    "@ui5/cli": "^4.0.33",
    "@sap/ux-ui5-tooling": "1",
    "@sap-ux/eslint-plugin-fiori-tools": "^9.0.0",
    "eslint": "^9",
    "@sap-ux/ui5-middleware-fe-mockserver": "2",
    "rimraf": "^5.0.5"
  },
  "sapuxLayer": "CUSTOMER_BASE"
}
```
**Kullanma:** `ui5-middleware-simpleproxy` → yerine `fiori-tools-proxy`.

## 4. Uygulama `package.json` scripts

```json
{
  "scripts": {
    "start":         "fiori run --open \"test/flp.html#app-preview\"",
    "start-local":   "fiori run --config ./ui5-local.yaml --open \"test/flp.html#app-preview\"",
    "start-noflp":   "fiori run --open \"/index.html?sap-ui-xx-viewCache=false\"",
    "start-mock":    "fiori run --config ./ui5-mock.yaml --open \"test/flp.html#app-preview\"",
    "build":         "ui5 build --config=ui5.yaml --clean-dest --dest dist",
    "lint":          "eslint ./",
    "deploy":        "npm run build && fiori deploy --config ui5-deploy.yaml",
    "deploy-config": "fiori add deploy-config",
    "undeploy":      "npm run build && fiori undeploy --config ui5-deploy.yaml",
    "deploy-test":   "npm run build && fiori deploy --config ui5-deploy.yaml --testMode true"
  }
}
```
- `deploy`/`undeploy` script'leri iskelette durur ama **model bunları koşmaz** — deploy akışı ve kapısı
  `deploy-and-local-run.md` §3.
- Backend'siz çalıştırmada `start-mock`'un `flp.html` yerine `index.html` açması önerilir (FLP ek flex çağrısı yapar;
  bkz. `deploy-and-local-run.md` §1). `start-mock`'un kullandığı `ui5-mock.yaml` backend'e bağlanmamalı (§7 notu).

## 5. `ui5.yaml` — proxy

```yaml
specVersion: "4.0"
metadata:
  name: com.example.<alan>.<uygulama>
type: application
server:
  customMiddleware:
    - name: fiori-tools-proxy
      afterMiddleware: compression
      configuration:
        ignoreCertErrors: true          # yalnız geliştirme sistemi sertifikası için; proje politikası belirler
        ui5:
          path: [/resources, /test-resources]
          url: https://ui5.sap.com
        backend:
          - path: /sap
            url: https://<SAP_HOST>:<PORT>   # KANONİK host — §6
            client: '<CLIENT>'
            authenticationType: basic
    - name: fiori-tools-appreload
      afterMiddleware: compression
      configuration: { port: 35729, path: webapp, delay: 300 }
    - name: fiori-tools-preview
      afterMiddleware: fiori-tools-appreload
      configuration:
        flp: { theme: sap_horizon }
```
- `ui5:` bloğu yalnız göreli `/resources` · `/test-resources` isteklerini CDN'e yönlendirir (bu yollardan
  yükleyen lokal sayfalar için). Uygulamanın `index.html` bootstrap'ı `/sap/public/bc/ui5_ui5/…` yolundan yüklenir ve `backend: /sap`
  proxy'sinden geçer (§7) — bu blok bootstrap'ın sürümünü belirlemez.

## 6. Kanonik host — tüm `ui5*.yaml` dosyalarında aynı

`ui5.yaml`, `ui5-local.yaml`, `ui5-mock.yaml`, `ui5-deploy.yaml` **aynı kanonik host**'u kullanır: geliştiricinin SAP
bağlantısında (ADT) kullandığı sistem adresi. App generator'ın yazdığı kısa/alternatif DNS adı (alias):
- lokal çalıştırmada kimlik doğru olsa bile **sonsuz kullanıcı/parola popup'ı** (401 döngüsü) üretebilir,
- deploy'da yanlış sistemin repository'sine/transport'una gider.

Yeni uygulama üretilince ilk iş: `rg -n "url:" --max-depth 1 --glob "ui5*.yaml"` → hepsi aynı kanonik host mu? Kaynak ekipte iki ayrı
turda (bir deploy, bir lokal çalıştırma) yaşandı.

## 7. `index.html` — bootstrap

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{Uygulama Adı}}</title>
    <style>html, body, body > div, #container, #container-uiarea { height: 100%; }</style>
    <script
        id="sap-ui-bootstrap"
        src="/sap/public/bc/ui5_ui5/resources/sap-ui-core.js"
        data-sap-ui-theme="sap_horizon"
        data-sap-ui-language="tr"
        data-sap-ui-resource-roots='{ "com.example.<alan>.<uygulama>": "./" }'
        data-sap-ui-on-init="module:sap/ui/core/ComponentSupport"
        data-sap-ui-compat-version="edge"
        data-sap-ui-async="true"
        data-sap-ui-frame-options="trusted"
        data-sap-ui-flexibility-services="[]"
    ></script>
</head>
<body class="sapUiBody sapUiSizeCompact" id="content">
    <div data-sap-ui-component
         data-name="com.example.<alan>.<uygulama>"
         data-id="container"
         data-settings='{"id" : "com.example.<alan>.<uygulama>"}'
         data-handle-validation="true"></div>
</body>
</html>
```

| Kural | Neden |
|---|---|
| UI5 **backend'in kendi kopyasından**, kök-göreli yolla (`/sap/public/bc/ui5_ui5/resources/sap-ui-core.js`); `manifest.json` `minUI5Version` = backend UI5 sürümü | Sürüm tanım gereği backend (ve FLP) ile aynıdır; dış CDN'in yaşam döngüsüne bağlı kalınmaz. İki ölçülmüş vaka: ① sürümsüz CDN (latest) core ↔ locale-data uyumsuzluğu — `tr` dilinde `this.oLocaleData.getDatePlaceholder is not a function` → `DateRangeSelection` çöker, beyaz ekran ② CDN'de **sabitlenmiş patch** bakım dışı kalınca silindi, silme yarımdı: `sap-ui-core.js` 200 ama `cldr/tr.json` 404 → UI5 hata vermeden `en`'e düştü, tarihler İngilizce basıldı ("Sep 21, 2026"). FLP backend'in UI5'ini kullandığı için canlı kullanıcı görmedi; yalnız doğrudan BSP adresi ve lokal testte çıktı ⇒ **CDN pin'i sabit değildir** |
| YASAK: `src="https://ui5.sap.com/<sürüm>/resources/…"` ve göreli `src="resources/sap-ui-core.js"` | CDN: patch'ler takvimle silinir (yukarıda ②). Göreli: deploy edilmiş BSP altında çözülmez |
| `data-sap-ui-language="tr"` | TR uygulama; i18n iki dosya kuralı (`freestyle-odata-v2.md` §9) buna bağlı |
| `data-sap-ui-libs` **yok** | Kütüphaneler manifest'te |
| Öznitelik adı biçimi **sürüme bağlı** | ≥ 1.120: kebab (`data-sap-ui-on-init`, `-resource-roots`, `-compat-version`, `-frame-options`). < 1.120: **tek kelime küçük harf** (`data-sap-ui-oninit`, `-resourceroots`, `-compatversion`, `-frameoptions`, `-flexibilityservices`) — 1.71.85–1.114.10'da kebab ad sessizce yok sayılır, beyaz ekran (§7.1 tablo) |
| `sapUiSizeCompact` body'de | Controller'da `addStyleClass` yapılmaz |
| `data-handle-validation="true"` | Validation framework |
| `data-sap-ui-flexibility-services="[]"` (< 1.120: `data-sap-ui-flexibilityservices`) | Lokal çalıştırmada `lrep`/flex çağrısını kapatır (401 popup döngüsünün bir kaynağı). Canlı FLP'de key-user adaptation isteniyorsa bu satırın kaldırılması **proje kararıdır** — DOĞRULANMADI: canlı FLP'deki etkisi kaynakta ölçülmedi |

> Not: iskelet üreticinin yazdığı göreli `src="resources/sap-ui-core.js"` biçimi `/sap/public/bc/ui5_ui5/…` ile
> değiştirilir.
> - **Deploy edilmiş BSP:** `/sap/public/bc/ui5_ui5/…` aynı host'ta çözülür (FLP'nin kullandığı UI5).
> - **Lokal çalıştırma (backend'li):** `ui5.yaml`'daki `backend: - path: /sap` proxy'si (§5) bu yolu backend'e taşır;
>   ek ayar gerekmez. `/test-resources` backend'de yoktur (404); yalnız lokal test/sandbox sayfaları CDN'de kalabilir
>   (canlıya gitmez).
> - **Mock çalıştırma (backend'siz — `start-mock`, KD ekran görüntüleri):** üretici `ui5-mock.yaml`'ı `ui5.yaml`'dan
>   KOPYALAR, `backend: /sap` bloğu da gelir ⇒ bootstrap mock'ta da SAP'ye gider: backend yoksa `sap-ui-core.js` **500**
>   ve sayfa boş kalır, varsa mock SAP'ye bağlanır (ölçüldü). `ui5-mock.yaml`'da `backend` bloğu silinir ve bootstrap
>   yolu CDN'e eşlenir — biçim ve ölçüm: `%sap-ui5-user-guide` → `references/mock-ortam.md` §2. `index.html` iki modda
>   da AYNI kalır.
> - **Doğrulama (runtime):** konsolda `sap.ui.version` = backend kopyasının core sürümü (CDN değil) · ağda
>   `…/resources/sap/ui/core/cldr/tr.json` **200** · bir tarih alanında ay adı Türkçe (ör. "23 Eyl 2026").
>   ⚠ `sap.ui.version` (core kütüphanesi) ile dağıtımın `sap-ui-version.json` → `version` değeri aynı sayı
>   olmayabilir (kaynak ekip ölçümü, ui5.sap.com 1.120.52: dağıtım `1.120.52`, `sap.ui.core` `1.120.50`).
>   `minUI5Version`'ın kaynağı `sap-ui-version.json`'dur (§7.1); `sap.ui.version` yalnız "UI5 backend'den mi geliyor"u
>   cevaplar.
> - ⚠ `ui5.yaml` `ui5:` proxy ayarını değiştirmek CDN bootstrap'ını düzeltmez: mutlak CDN adresi proxy'ye hiç uğramaz
>   ("proxy doğru dosyayı veriyor" ≠ "uygulama proxy'den yüklüyor").

### 7.1 UI5 sürümü + tema backend'den ÖLÇÜLÜR · sürüme bağlı kontroller (ZORUNLU)

1. `manifest.json` → `minUI5Version` = `GET <backend>/sap/public/bc/ui5_ui5/resources/sap-ui-version.json` →
   `version`. Bu skill'deki `1.120.23` gibi numaralar **örnektir**, kural değildir.
2. Tema: `…/resources/sap/ui/core/themes/sap_horizon/library.css` **200 VE md5'i `…/themes/base/library.css`'ten
   FARKLI** ise `sap_horizon`; değilse `sap_fiori_3`. ⛔ Yalnız 200'e bakma: 1.71.85'te olmayan tema `base`'e düşüp
   **200** döner (kaynak ekip ölçümü 2026-11-02, CDN; UI5 1.71.5 backend ICF'de aynı — tüketici ölçümü). Ölçülen
   tema adı geçtiği her yere aynı yazılır: `index.html` `data-sap-ui-theme` · tüm `ui5*.yaml` `flp.theme` ·
   test/sandbox sayfaları. Horizon'suz backend'de Horizon maddeleri `sap_fiori_3` ile uygulanır (ilke aynı).
3. Aşağıdaki tablodaki kontrol yalnız backend sürümü **≥ `@since`** ise kullanılır; altındaysa "eski sürümde"
   sütunu. **"1.71 hattı"** = backend < 1.120 (şablonun `surum/1.71/` parçası) · **"1.120 hattı"** = ≥ 1.120.
   "ölçüldü: … ✗ · … ✓" yazan satırda eşik tam bilinmez ⇒ 1.120 altındaki her backend'de "eski sürümde" sütunu.

```bash
B="https://<SAP_HOST>:<PORT>/sap/public/bc/ui5_ui5/resources"
curl -s "$B/sap-ui-version.json"                                  # → "version": "<X.Y.Z>" ⇒ minUI5Version
curl -s -o /dev/null -w "%{http_code}\n" "$B/sap/ui/core/themes/sap_horizon/library.css"
curl -s "$B/sap/ui/core/themes/sap_horizon/library.css" | md5sum
curl -s "$B/sap/ui/core/themes/base/library.css"        | md5sum
# 200 VE iki md5 FARKLI ⇒ sap_horizon · aksi hâlde ⇒ sap_fiori_3
```

| Kontrol / API | `@since` | Backend `< @since` ise | Şablondaki yeri |
|---|---|---|---|
| `sap.m.IllustratedMessage` (boş durum) | 1.98 | **Grid:** `noData` içinde `VBox` { `Text` + CTA `Button` } (`noData` tek kontrol alır). **`sap.m.Table`/`List` < 1.101:** `noData` aggregation'ı yok ⇒ tablonun yanında görünürlüğü "satır yok"a bağlı `VBox` { `Text` + `Button` } (1.98–1.100: o dış kontrol `IllustratedMessage`). CTA'lı boş durum ilkesi aynen geçerli | `SurumParca.bosDurum` |
| `sap.m.ListBase` `noData` aggregation'ı | 1.101 | `noDataText` + yukarıdaki dış `VBox` | — |
| `sap.ui.table.rowmodes.Auto` (`rowMode`) | 1.119 | `visibleRowCountMode="Auto"` + `minAutoRowCount` (≥ 1.119'da deprecated ⇒ orada KULLANILMAZ) | `SurumParca.satirModu` |
| `sap.m.Avatar` | 1.73 | `sap.f.Avatar` ya da başlıkta ikon | — |
| `sap.ui.core.IAsyncContentCreation` | 1.89 | arayüz bildirilmez; manifest `rootView.async` + `routing.config.async` (eşdeğerlik ÖLÇÜLMEDİ) | `SurumParca.bilesenArayuzleri` |
| `sap.m.VariantManagement` | 1.103 | kullanılmaz — varyant `TablePersonalizer`'ın servis-tabanlı varyantı | — |
| Bootstrap öznitelik adı (kebab) | ölçüldü: 1.71.85 · 1.84.62 · 1.96.51 · 1.108.57 · 1.114.10 ✗ · 1.120.52 ✓ | tek kelime küçük harf (`oninit`, `resourceroots`, `compatversion`, `frameoptions`, `flexibilityservices`) | `surum/<v>/webapp/index.html` |
| `sap.app.i18n` **nesne** biçimi (`bundleUrl`, `supportedLocales`, `fallbackLocale`) | ölçüldü: 1.71.85 ✗ · 1.84.62+ ✓ | **dizgi** `"i18n": "i18n/i18n.properties"`. ⚠ `supportedLocales`/`fallbackLocale` 1.71.85'te hiçbir yerde okunmaz (`models.i18n.settings`'e taşımak da etkisiz) | ortak gövde dizgi kullanır |
| `sap.ui.table.Table` `rowsUpdated` olayı | 1.86 | yok (yalnız iç `_rowsUpdated`) ⇒ satır binding'inin `dataReceived` olayı (`bindRows({events})`) | `List.controller.js` |
| `Column` `sortOrder` = `None` | 1.120 | 1.71'de varsayılan `Ascending`, `None` yok ⇒ "sıralı mı" = `getSorted()`; `Table#getSortedColumns()` tek başına yetmez (XML'de verilen sıralamayı yansıtmaz) | `SurumParca.siraliMi` |
| `ValueHelpDialog` · `sap.ui.export.Spreadsheet` | 1.24 · 1.50 | iki hedef sürümde de var | ortak |
| Spreadsheet `dataSource` = `ListBinding` | ölçüldü: 1.71.85 ✗ · 1.120.52 ✓ | `{ type: "odata", dataUrl: binding.getDownloadUrl(...), serviceUrl, count, useBatch: false, headers }` (iki sürümde geçerli) | `List.controller.js` `_doExport` |

Kaynak: `@since` değerleri UI5 1.120.52 `-dbg.js` başlıklarından; "ölçüldü" satırları ui5.sap.com CDN'de
(2026-11-02, kaynak ekip). Tabloda olmayan bir kontrolü eklerken `@since`'ını API referansından doğrula.
Manifest `_version` ayrı eksendir (descriptor şema sürümü): 1.71 hattında şablonun `surum/1.71/README.md` değeri
(`1.12.0`), 1.120 altı başka backend'de ÖLÇÜLMEDİ. ⚠ 1.71 sütunundaki boş durum `VBox` ve `visibleRowCountMode`
1.71 çalışma zamanında ÖLÇÜLMEDİ (yalnız API metadata'sı) — şablon README §0 adım 3.

**Neden:** hiçbir kontrol `minUI5Version`'ı denetlemez ⇒ örnekteki sabit sürüm sessizce kopyalanır; `@since`'ı
backend'den büyük bir kontrolün modülü o backend'de yoktur (açılmaz).

## 8. `manifest.json` — şablon

```json
{
  "_version": "1.60.0",
  "sap.app": {
    "id": "com.example.<alan>.<uygulama>",
    "type": "application",
    "i18n": "i18n/i18n.properties",
    "applicationVersion": { "version": "0.0.1" },
    "title": "{{appTitle}}",
    "description": "{{appDescription}}",
    "resources": "resources.json",
    "dataSources": {
      "mainService": {
        "uri": "/sap/opu/odata/sap/ZXX001_UI_ORDER_O2/",
        "type": "OData",
        "settings": { "localUri": "localService/mainService/metadata.xml", "odataVersion": "2.0" }
      }
    }
  },
  "sap.ui": { "fullWidth": true, "technology": "UI5", "deviceTypes": { "desktop": true, "tablet": true, "phone": false } },
  "sap.ui5": {
    "flexEnabled": true,
    "dependencies": {
      "minUI5Version": "<UI5_VERSION>",
      "libs": { "sap.m": {}, "sap.ui.core": {}, "sap.ui.comp": {}, "sap.ui.layout": {}, "sap.ui.unified": {} }
    },
    "contentDensities": { "compact": true, "cozy": false },
    "resources": { "css": [{ "uri": "css/style.css" }] },
    "models": {
      "i18n": { "type": "sap.ui.model.resource.ResourceModel",
                "settings": { "bundleName": "com.example.<alan>.<uygulama>.i18n.i18n" } },
      "": { "dataSource": "mainService", "preload": true,
            "settings": { "defaultBindingMode": "TwoWay", "defaultCountMode": "Inline", "useBatch": false } },
      "ui": { "type": "sap.ui.model.json.JSONModel", "settings": { "busy": false, "filter": {} } }
    },
    "routing": {
      "config": { "routerClass": "sap.m.routing.Router", "type": "View", "viewType": "XML",
                  "path": "com.example.<alan>.<uygulama>.view", "viewPath": "com.example.<alan>.<uygulama>.view",
                  "controlId": "app", "controlAggregation": "pages", "transition": "show", "async": true },
      "routes": [ { "name": "list", "pattern": "", "target": "list" } ],
      "targets": { "list": { "id": "List", "name": "List", "viewLevel": 1 } }
    },
    "rootView": { "viewName": "com.example.<alan>.<uygulama>.view.App", "type": "XML", "id": "App", "async": true }
  }
}
```

| Kural | Açıklama |
|---|---|
| `_version` ≥ `1.60.0` | 1.59 ve altı kullanılmaz |
| `resources: "resources.json"` | BSP deploy için |
| `flexEnabled: true` | UI adaptation; lokal 401 popup'ını tek başına **durdurmaz** (bkz. `deploy-and-local-run.md` §1) |
| `minUI5Version` = backend UI5 sürümü (`index.html` onu yükler) | ölçülür, örnekten alınmaz — §7.1 |
| `sap.app.i18n` **dizgi** (iki hatta da çalışır) | Nesne biçimi (`{ "bundleUrl": …, "supportedLocales": ["", "tr"], "fallbackLocale": "" }`) yalnız 1.120 hattında (1.71.85 nesneyi desteklemez — §7.1). Nesne biçim kullanılıyorsa: boş string = varsayılan `i18n.properties`; `fallbackLocale` başka bir değer olunca dil yüklemesi bozuldu. 1.71.85'te `supportedLocales`/`fallbackLocale` okunmaz |
| `useBatch: false` | Kaynak ekibin V2 servislerinde üretim standardı; `$batch` yalnız bilinçli istisna (`freestyle-odata-v2.md` §10) |
| `controlId: "app"` | `App.view.xml` `<App id="app"/>` ile aynı (`appContainer` değil) |
| `routing.config.type: "View"` + `path` + `viewPath` | ikisi de yazılır; her target'ta ayrıca `"id"` |
| **İsimli JSONModel başlangıç verisi `settings`'in DOĞRUDAN içinde** | `"settings": { "data": {...} }` yazılırsa UI5 tüm `settings` nesnesini veri olarak verir → veri `/data/...` altına düşer, `{ui>/busy}`, `{ui>/filter}` gibi kök binding'ler **sessizce undefined** (busy dönmez, filtre tutmaz, F4 seçimi yansımıyor gibi görünür). Kontrol: `settings.data` var mı ve uygulama `{model>/data/...}` kullanıyor mu; kullanmıyorsa hata. Runtime kanıt: `getModel("ui").getData()` |
| Liste ekranı varsa libs'e `sap.ui.table` + `sap.ui.export` | `list-grid-alv.md` §2 |

### 8.1 Annotation dataSource
- Freestyle uygulama annotation'a bağlı değilse **annotation dataSource koyma**: SAP'de kayıtlı olmayan bir annotation
  adresi manifest'te durursa `$metadata` yüklemesi **HTTP 400** ile düşer; çözüm dataSource'u ve
  `settings.annotations` dizisini kaldırmaktı.
- Annotation gerçekten gerekiyorsa servis URL'si (`/sap/opu/odata/SAP/<SERVIS>_VAN` gibi) değil **katalog servisi**
  üzerinden:
  ```json
  "ZXX001_ORDER_ANNO_MDL": {
    "uri": "/sap/opu/odata/IWFND/CATALOGSERVICE;v=2/Annotations(TechnicalName='ZXX001_ORDER_ANNO_MDL',Version='0001')/$value/",
    "type": "ODataAnnotation",
    "settings": { "localUri": "localService/mainService/ZXX001_ORDER_ANNO_MDL.xml" }
  }
  ```
  ve `mainService.settings.annotations: ["ZXX001_ORDER_ANNO_MDL"]`. Adın sistemde kayıtlı olduğunu önce tarayıcıda
  ölç (200 mü).

## 9. `Component.js`

```javascript
sap.ui.define([
    "sap/ui/core/UIComponent",
    "com/example/<alan>/<uygulama>/model/models"
], (UIComponent, models) => {
    "use strict";
    return UIComponent.extend("com.example.<alan>.<uygulama>.Component", {
        metadata: { manifest: "json", interfaces: ["sap.ui.core.IAsyncContentCreation"] },
        init() {
            UIComponent.prototype.init.apply(this, arguments);
            this.setModel(models.createDeviceModel(), "device");
            this.getRouter().initialize();
        }
    });
});
```
- `sap.ui.core.IAsyncContentCreation` zorunlu — **backend ≥ 1.89** (`@since 1.89`); altında arayüz bildirilmez, async
  içerik manifest `rootView.async` + `routing.config.async` ile (§7.1; şablonda `SurumParca.bilesenArayuzleri`).
- ODataModel Component'te kurulmaz, manifest yönetir.
- Kullanılan her sınıf (`JSONModel` vb.) `sap.ui.define` bağımlılığıdır; global `sap.ui.model.json.JSONModel`
  kullanımı async/strict'te fırlatır.
- **BaseController `navTo` sarmalayıcısı üçüncü argümanı düşürür:** şablonlardaki yaygın
  `navTo: function (sRoute, oParams) { this.getRouter().navTo(sRoute, oParams); }` yalnız iki argüman iletir;
  `this.navTo("filter", {}, true)` yazınca `bReplace` sessizce düşer ve geçmişe kayıt eklenir. Yönlendirme (guard)
  senaryosunda geri tuşu korunan sayfayı açar, guard yine yönlendirir ⇒ geri tuşuyla uygulamadan çıkılamaz. Çare:
  `this.getRouter().navTo("filter", {}, true)` ya da sarmalayıcıyı `navTo(sRoute, oParams, bReplace)` diye genişlet.
  Argüman sayısı uyuşmazlığı hata vermez — replace isteyen her yönlendirmede sarmalayıcının imzasını oku (ekip dersi,
  2026-10-05, Router 1.120.23 kaynağıyla; kod yorumu "replace" diyordu, davranış ekleme idi).

`model/models.js`:
```javascript
sap.ui.define(["sap/ui/model/json/JSONModel", "sap/ui/Device"], function (JSONModel, Device) {
    "use strict";
    return { createDeviceModel: function () { var o = new JSONModel(Device); o.setDefaultBindingMode("OneWay"); return o; } };
});
```

## 10. `App.view.xml`

```xml
<mvc:View xmlns:mvc="sap.ui.core.mvc" xmlns="sap.m" displayBlock="true"
          controllerName="com.example.<alan>.<uygulama>.controller.App">
    <App id="app"/>
</mvc:View>
```

## 11. `localService/`

```
webapp/localService/mainService/metadata.xml      ← servisin $metadata'sı (tarayıcıdan kaydedilir)
webapp/localService/mainService/<ANNO_MDL>.xml    ← yalnız annotation kullanılıyorsa
```
- `GET /sap/opu/odata/sap/<SERVIS>/$metadata` tarayıcıda açılıp kaydedilir. Mock server ve Fiori tools bu dosyayı kullanır.
- ⚠ **Bu dosya bayatlar.** Projeksiyonda alan yeniden adlandırılınca yerel kopya eski adla kalır. Alan adı / Edm tipi
  doğrulaması **canlı `$metadata`**'ya karşı yapılır (`freestyle-odata-v2.md` §8, `scripts/check_ui_odata_refs.py`).

## 12. CSS, kütüphaneler, yerleşim

- Özel CSS yalnız tema değişkenleriyle (`var(--sapXxx)`); sabit hex/rgb renk yok (`fiori-elements-ux.md` §6).
- Alan altı kısa açıklama sınıfı (kod + ad deseni, value-help alanlarında):
  ```css
  .zxx001FieldDesc { font-size: .75rem; color: var(--sapContent_LabelColor); max-width: 9em; overflow: hidden;
                     text-overflow: ellipsis; white-space: nowrap; line-height: 1.2; margin-top: .125rem; }
  ```
  (Kaynakta renk sabit `#6a6d70` yazılmıştı; tema değişkeni kuralıyla çeliştiği için değişkene çevrildi —
  `sapContent_LabelColor` adı DOĞRULANMADI, `get_api_reference`/tema dokümanından teyit et.)
- **`sap.f` kütüphanesi eklenmez:** kaynak sistemde (UI5 1.120 hattı) `sap.f.DynamicSideContent` **404** verdi. Yan
  panel için `sap.ui.layout.Splitter` (yatay, 70%/30%). `sap.ushell` de eklenmez (launchpad bağımlılığı).
- `SplitterLayoutData` `<layoutData>` aggregation'ı içinde yazılır:
  ```xml
  <l:Splitter orientation="Horizontal" height="100%">
    <l:contentAreas>
      <VBox><layoutData><l:SplitterLayoutData size="70%" resizable="true"/></layoutData> ... </VBox>
    </l:contentAreas>
  </l:Splitter>
  ```
- Klasik `SmartFilterBar`'da CDS/SADL kaynaklı property'ler SEGW'den `filterable` yapılamadı (satış org./kanal/bölüm
  görünmedi). Çözüm A: MPC_EXT `DEFINE`'da `set_filterable( iv_filterable = abap_true )` (`%sap-odata-backend`);
  Çözüm B: SmartFilterBar kaldırılıp freestyle filtre ekranı (`list-grid-alv.md` §6).

## 13. Yeni uygulama kontrol listesi (iskelet)

- [ ] App ID biçimi; BSP adı `Z…` ≤ 15
- [ ] `ui/` workspace kökü; uygulama `package.json` sade + middleware paket adları `devDependencies`'te; kurulum yalnız kökte
- [ ] `ui5-mock.yaml`'da `backend:` bloğu YOK + bootstrap yolu CDN'e eşli (`%sap-ui5-user-guide` → `references/mock-ortam.md` §2)
- [ ] `sapuxLayer: CUSTOMER_BASE`, standart scripts, `fiori-tools-proxy`
- [ ] Tüm `ui5*.yaml` aynı kanonik host
- [ ] `ui5-deploy.yaml` `deploy-to-abap` görevi + BSP adı/paket/transport (`deploy-and-local-run.md` §2) — `python scripts/deploy_ui.py prepare <app> --no-build`
- [ ] Backend UI5 sürümü + tema ölçüldü (`sap-ui-version.json` + iki md5; §7.1) → `minUI5Version`, `data-sap-ui-theme`, `flp.theme` aynı; kullanılan her kontrolün `@since`'ı ≤ backend
- [ ] `index.html` bootstrap backend UI5'i (`/sap/public/bc/ui5_ui5/resources/…`; CDN/göreli değil) + `language=tr` + `sapUiSizeCompact` + `data-sap-ui-libs` yok + `data-handle-validation`
- [ ] `manifest.json`: `_version ≥ 1.60.0`, `resources.json`, `flexEnabled`, `minUI5Version` = ölçülen backend sürümü, `sap.app.i18n` dizgi, `useBatch:false`, `controlId:"app"`, routing `type:"View"` + target `id`
- [ ] İsimli JSONModel'de `settings.data` çift sarmalama yok
- [ ] Annotation dataSource ya yok ya katalog servisi üzerinden ve 200 ölçülmüş
- [ ] `Component.js` `IAsyncContentCreation` (backend ≥ 1.89); tüm sınıflar define bağımlılığı
- [ ] `<App id="app"/>`; `localService/mainService/metadata.xml`
- [ ] i18n iki dosya (`python scripts/check_i18n_keys.py <app>`)
- [ ] Liste ekranı varsa grid (`python scripts/check_list_view_grid.py <app>`)

---

## Bu dosyada ÇIKARILAN / DEĞİŞTİRİLEN
- Kaynak şablondaki gerçek sistem adı, müşteri paket/uygulama adları, "referans uygulama klasörünü kopyala" adımı ve
  per-app `RUN.md` yolları alınmadı (müşteriye özel). Örnek adlar demo adlarla (`ZXX001`, `ZCA000`) değiştirildi.
- `sourceTemplate` bloğu şablondan çıkarıldı (üretecin yazdığı meta; kural değil).
- Manifest şablonundaki annotation dataSource zorunluluğu **opsiyonele** çevrildi: kaynak standart "annotation yoksa da
  localUri ile tanımla" derken bilinen hatalar kaydı kayıtsız annotation adresinin 400 verdiğini ve kaldırılarak
  çözüldüğünü söylüyor — freestyle uygulamada koymamak güvenli yol.
- Kaynak manifestte isimli model `settings: { data: {} }` biçimindeydi; aynı kaynağın hata kontrol listesi bu biçimi
  sessiz binding hatası olarak işaretliyor → şablon düz `settings` biçimine çevrildi.
- `index.html` şablonuna `data-sap-ui-flexibility-services="[]"` eklendi (kaynakta ayrı bir lokal çalıştırma dersiydi).
- Bootstrap kaynağı CDN sürüm pin'inden backend'in kendi UI5'ine (`/sap/public/bc/ui5_ui5/…`) çevrildi: kaynak standart
  güncellendi (sabitlenen CDN patch'i silinip `tr` locale verisi 404 verince UI5 sessizce İngilizceye düştü, §7).
  Kaynağın kapsamadığı backend'siz mock modu aXet'te ölçülerek eklendi (§7 notu; `mock-ortam.md` §2).
- Kaynak "uygulama `package.json`'unda devDependencies yok" diyordu; aXet'te ölçüldü: UI5 CLI 4.0.69 middleware'i
  uygulamanın kendi bağımlılıklarından çözdüğü için bu biçimde sunucu açılmadı → adlar eklendi (§2). Kaynak da sonradan
  aynı ölçümle (UI5 CLI 4.0.57 ve 4.0.69) bu kurala hizalandı; önceki "8 uygulamalı workspace'te çalıştı" kaydının
  neden farklı olduğu (UI5 CLI sürümü mü, uygulamaların gerçekte ad taşıması mı) DOĞRULANMADI.
- 2026-11-17 (uyum turu 8): kaynak standarda eklenen "sürüm + tema backend'den ölçülür, sürüme bağlı kontroller" kuralı
  §7.1 olarak alındı; manifest `sap.app.i18n` dizgi biçimine çevrildi (nesne biçim 1.71.85'te desteklenmiyor), bootstrap
  öznitelik biçimi sürüme bağlandı, BSP adı müşteri namespace'ini kabul eder. Kaynağın kanonik uygulama kopyası
  `templates/ui5-freestyle/` olarak geldi.
- Uygulama klasöründe `npm install`'ı engelleyen otomatik kapı aXet'te yok; kural metin olarak kaldı.
