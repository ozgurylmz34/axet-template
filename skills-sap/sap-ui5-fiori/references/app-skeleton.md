# Uygulama iskeleti — workspace, tooling, manifest, bootstrap

> Kapsam: yeni bir freestyle UI5 uygulamasının (OData V2) **kod yazmadan önceki** iskeleti. Save/binding/value-help
> mekaniği `freestyle-odata-v2.md`, liste ekranı `list-grid-alv.md`, çalıştırma ve deploy `deploy-and-local-run.md`.
> Örneklerdeki adlar demodur: servis `ZXX001_UI_ORDER_O2`, app ID `com.example.<alan>.<uygulama>`, sistem
> `<SAP_HOST>:<PORT>`, client `<CLIENT>`, UI5 sürümü `<UI5_VERSION>` (kaynak projede `1.120.x` hattıydı).

---

## 1. Adlandırma

| Öğe | Kural |
|---|---|
| App ID | `com.example.<alan>.<uygulama>` biçimi (proje kendi kök alanını kullanır) |
| BSP (ABAP repository) adı | `Z` ile başlar, **en çok 15 karakter** (`ZXX001_ORDER` ✅, `ZXX001_ORDER_APPLICATION` ❌) |
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

- Yeni uygulama `ui/<app>/` altına; uygulamanın `package.json`'u **minimal**: `name` + `scripts` (devDependencies yok,
  kökten gelir).
- **`npm install` yalnız `ui/` kökünde.** Uygulama klasöründe `npm install/ci/add` = gereksiz ikinci `node_modules`.
  Uygulamayı çalıştırmak için uygulama klasöründe kurulum gerekmez: `npm run start-noflp` bin'i üst klasördeki
  `ui/node_modules/.bin`'den çözer.
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
  bkz. `deploy-and-local-run.md` §1).

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

## 6. Kanonik host — tüm `ui5*.yaml` dosyalarında aynı

`ui5.yaml`, `ui5-local.yaml`, `ui5-mock.yaml`, `ui5-deploy.yaml` **aynı kanonik host**'u kullanır: geliştiricinin SAP
bağlantısında (ADT) kullandığı sistem adresi. App generator'ın yazdığı kısa/alternatif DNS adı (alias):
- lokal çalıştırmada kimlik doğru olsa bile **sonsuz kullanıcı/parola popup'ı** (401 döngüsü) üretebilir,
- deploy'da yanlış sistemin repository'sine/transport'una gider.

Yeni uygulama üretilince ilk iş: `grep -n "url:" ui5*.yaml` → hepsi aynı kanonik host mu? Kaynak ekipte iki ayrı
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
        src="https://ui5.sap.com/<UI5_VERSION>/resources/sap-ui-core.js"
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
| UI5 sürümü **sabit** (`.../<UI5_VERSION>/resources/...`), `manifest.json` `minUI5Version` ile aynı | Sürümsüz CDN (latest) core ↔ locale-data uyumsuzluğu: `tr` dilinde `this.oLocaleData.getDatePlaceholder is not a function` → `DateRangeSelection` çöker, beyaz ekran. Sürüm sabitlenince çözüldü |
| `data-sap-ui-language="tr"` | TR uygulama; i18n iki dosya kuralı (`freestyle-odata-v2.md` §9) buna bağlı |
| `data-sap-ui-libs` **yok** | Kütüphaneler manifest'te |
| `data-sap-ui-on-init` camelCase | `data-sap-ui-oninit` değil |
| `sapUiSizeCompact` body'de | Controller'da `addStyleClass` yapılmaz |
| `data-handle-validation="true"` | Validation framework |
| `data-sap-ui-flexibility-services="[]"` | Lokal çalıştırmada `lrep`/flex çağrısını kapatır (401 popup döngüsünün bir kaynağı). Canlı FLP'de key-user adaptation isteniyorsa bu satırın kaldırılması **proje kararıdır** — DOĞRULANMADI: canlı FLP'deki etkisi kaynakta ölçülmedi |

> Not: iskelet üreticinin yazdığı yerel `src="resources/sap-ui-core.js"` biçimi proxy üzerinden sürümsüz yükler; sabit
> sürüm kuralı gereği CDN adresi + sürüm yazılır.

## 8. `manifest.json` — şablon

```json
{
  "_version": "1.60.0",
  "sap.app": {
    "id": "com.example.<alan>.<uygulama>",
    "type": "application",
    "i18n": { "bundleUrl": "i18n/i18n.properties", "supportedLocales": ["", "tr"], "fallbackLocale": "" },
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
| `minUI5Version` = `index.html` sürümü | §7 |
| `supportedLocales ["", "tr"]` + `fallbackLocale ""` | Boş string = varsayılan `i18n.properties`. `fallbackLocale` başka bir değer olunca dil yüklemesi bozuldu |
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
- `sap.ui.core.IAsyncContentCreation` zorunlu.
- ODataModel Component'te kurulmaz, manifest yönetir.
- Kullanılan her sınıf (`JSONModel` vb.) `sap.ui.define` bağımlılığıdır; global `sap.ui.model.json.JSONModel`
  kullanımı async/strict'te fırlatır.

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
- [ ] `ui/` workspace kökü; uygulama `package.json` minimal; kurulum yalnız kökte
- [ ] `sapuxLayer: CUSTOMER_BASE`, standart scripts, `fiori-tools-proxy`
- [ ] Tüm `ui5*.yaml` aynı kanonik host
- [ ] `ui5-deploy.yaml` `deploy-to-abap` görevi + BSP adı/paket/transport (`deploy-and-local-run.md` §2) — `python scripts/deploy_ui.py prepare <app> --no-build`
- [ ] `index.html` sabit UI5 sürümü + `language=tr` + `sapUiSizeCompact` + `data-sap-ui-libs` yok + `data-handle-validation`
- [ ] `manifest.json`: `_version ≥ 1.60.0`, `resources.json`, `flexEnabled`, `minUI5Version` = index, i18n locales, `useBatch:false`, `controlId:"app"`, routing `type:"View"` + target `id`
- [ ] İsimli JSONModel'de `settings.data` çift sarmalama yok
- [ ] Annotation dataSource ya yok ya katalog servisi üzerinden ve 200 ölçülmüş
- [ ] `Component.js` `IAsyncContentCreation`; tüm sınıflar define bağımlılığı
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
- Uygulama klasöründe `npm install`'ı engelleyen otomatik kapı aXet'te yok; kural metin olarak kaldı.
