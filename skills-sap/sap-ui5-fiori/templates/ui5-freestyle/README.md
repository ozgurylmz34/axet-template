# Freestyle UI5 şablonu — seçim ekranı → grid liste → değişiklik ekranı (OData V2)

Yeni bir freestyle uygulama **bu şablondan kopyalanarak** başlar. Şablon bu skill'in referanslarındaki kuralların
(`references/app-skeleton.md`, `freestyle-odata-v2.md`, `list-grid-alv.md`, `checklists.md`) çalışan hâlidir;
parçalar çalışan uygulamalardan alınıp jenerikleştirildi. Hangi parçanın hangi UI5 sürüm API'sine dayandığı §4'te
kanıtıyla yazılıdır. Kod içindeki yorumlar kuralın yerini `references/<dosya>.md §<bölüm>` ve kontrol listesi
kimliğiyle (FE-xx, UI-xx) verir.

```
ui5-freestyle/
├── app/                     ORTAK GÖVDE — her sürümde aynı (sürüme bağlı API KULLANMAZ)
│   ├── package.json · ui5.yaml · ui5-deploy.yaml
│   └── webapp/  Component.js · manifest.json · controller/ · view/ · util/ · i18n/ · model/ · css/
├── surum/                   SÜRÜM PARÇASI — iki dosya: webapp/index.html + webapp/util/SurumParca.js
│   ├── 1.120/webapp/        backend UI5 >= 1.120 (bootstrap öznitelikleri kebab: on-init, resource-roots …)
│   └── 1.71/webapp/         backend UI5 < 1.120, ölçülen 1.71.x (bootstrap öznitelikleri tek kelime: oninit …)
└── backend-referans/        varyant servisi (RAP) kaynak kopyası + sözleşme
```

## 0. Bilinen sınırlar — ilk kullanımda ZORUNLU doğrulama

⛔ **Bu şablon gerçek bir backend'de tarayıcıda açılarak DENENMEDİ.** Kanıtı statiktir: skill'in statik kontrolleri,
şablon testi (`tests/test_ui5_sablon.py`) ve kaynak ekibin modüllerin ui5.sap.com'da (1.71.85 · 1.120.52) var
olduğunu ölçmesi. Bunlar ekranın çalıştığını göstermez. Şablondan üretilen ilk uygulama aşağıdaki adımlar koşulup
çıktıları kayda geçmeden **"çalışıyor" diye teslim edilmez**:

1. **Sürüm + tema backend'den ölçüldü** (§1 adım 1 · §3) — ölçüm çıktısı (sürüm + iki md5) kayıtta.
2. **Tarayıcı turu, kimlikli yerel sunucuda** (`npm run start-noflp`, `references/deploy-and-local-run.md` §1 —
   kimliksiz sunucu `busy`de asılı kalıp sahte hata üretir): seçim ekranı → Listele → grid dolu · **boş sonuç** → CTA'lı
   boş durum görünür · satır modu ekran yüksekliğine uyar · kolon sırala/filtre/gizle + varyant kaydet/yükle ·
   değişiklik ekranında kaydet → başarı mesajı + listeye dönüş · konsolda hata yok ·
   **tarih aralığı:** kaydı OLAN günü ve ERTESİ günü ayrı ayrı seç → ertesi gün o kaydı getirmemeli (FE-45 kontrol
   grubu; ağ sekmesinde `$filter` sınırı `…T00:00:00` olmalı, `…T21:00:00` değil) · kolon başlığından sırala →
   Listele'yi yeniden çalıştır → sıralama korunur, sıralanmamış kolon sıralayıcı almaz ·
   **tarih kolonu başlık filtresi:** gridde görünen biçimle yaz → yalnız o günün kayıtları (`$filter=… eq
   datetime'…T00:00:00'`, ay/gün yer değiştirmemiş) · olmayan gün (`31.11.2026`) ya da anlamsız metin → filtre
   uygulanmaz + mesaj (bir sonraki aya KAYMAZ) · **sayı kolonu başlık filtresi:** oturum dilinin biçimiyle yaz (TR
   `1.250` / `1.250,5`) → `$filter=… eq 1250m` (`1.250m` DEĞİL) · TR'de `1.25` → filtre uygulanmaz + mesaj ·
   **geçersiz metin, kolonda geçerli bir filtre varken:** önceki filtre etkin KALIR, mesaj bunu söyler, ağda yeni
   istek YOK · **kolon filtresi penceresi:** kolon menüsünde kutunun altında **Filtre…** görünür (her kolon türünde) →
   koşul listesi türe uyar (metin 13 · sayı/tarih 7 · saat yalnız Eşittir) → koşul + değer → Uygula → ağda `$filter`
   seçilen koşulu taşır · geçersiz değerde pencere KAPANMAZ · dolu açılış + **Filtreyi Kaldır** · **kutuya koşul
   yazımı** (`x*`, `!=x`, `>5`, `a..b`) → filtre UYGULANMAZ, uyarı + önceki filtre korunur, ağda yeni istek YOK ·
   konsolda `Log.error` "'Filtre…' öğesi YOK/KURULAMADI" ÇIKMAMALI (çıkarsa backend sürümünde menünün özel metodu
   değişmiştir — `SurumParca.filtreMenusuneEkle`) · **Excel:** kolon filtresi + sıralama aktifken "Tüm kolonlar" →
   dosyadaki satır sayısı ve sırası grid başlığıyla aynı (Excel isteğinin URL'inde `$filter` + `$orderby` + `sap-client`).
3. **1.71 parçası kullanıldıysa:** grid boş durumunun `noData` içinde `VBox`{`Text` + CTA `Button`} olarak göründüğü
   ve `visibleRowCountMode="Auto"` satır sayısının ekrana uyduğu **gözle** doğrulanır — bu iki davranış 1.71 çalışma
   zamanında ÖLÇÜLMEDİ (yalnız API metadata'sı ölçüldü).
4. **Varyant servisi:** servis varsa varyant kaydı tabloya yazılır (servis GET ile görülür); servis yoksa konsolda
   `Log.warning` görülür ve varyant yalnız tarayıcıda saklanır — **sessiz düşme kabul edilmez**.

**Doğrulanamayan / ölçülmeyen kalemler** (kendi sisteminde ölç; sonuç buradakinden farklıysa kullanıcıya söyle ve
`%remember` ile kaydet):

| Kalem | Durum | Ayrıntı |
|---|---|---|
| 1.72–1.119 arası backend'de 1.71 parçası (bant: < 1.120 → 1.71 · ≥ 1.120 → 1.120) | parçanın dayandığı sekiz davranış 1.84.62 · 1.96.51 · 1.108.57 · 1.114.10'da ölçüldü: 1.84.62 · 1.96.51 · 1.114.10'da sekizi, 1.108.57'de yedisi 1.71.85 ile AYNI; **validator metni 1.108.57'de KAÇIŞLI** (`{`·`}` içeren yazılı değer token'a kaçışlı geçer). Diğer ara sürümler ve uygulamanın bütün olarak açılması ÖLÇÜLMEDİ | `surum/1.71/README.md` §Ara sürümler |
| 1.71 için manifest `_version` | `1.12.0` — 1.71.85 demokit örnekleriyle aynı; çalışma zamanı okumuyor (ölçüldü) | `surum/1.71/README.md` |
| 1.120 altı backend'de manifest `_version` | ÖLÇÜLMEDİ | `surum/1.120/README.md` |
| Backend ICF'nin olmayan temayı `base`'e düşürmesi | UI5 1.71.5 backend ICF'de ölçüldü (CDN 1.71.85 ile aynı); diğer backend sürümleri ÖLÇÜLMEDİ | §3 |
| Varyant servisinin SRVD/SRVB adları + yayınlama | DOĞRULANMADI | `backend-referans/README.md` |
| ECC / SEGW ile varyant servisi | DOĞRULANMADI | `backend-referans/README.md` |
| View özniteliklerinin 1.71'de özellik düzeyinde varlığı | yalnız modül düzeyi ölçüldü (§4'te adı geçen olay/özellikler tek tek) | §4 |
| Kayıt sayısı başlığı (`dataReceived`) · tarih sınırı (`utcGun`) · kısmi kaydetme sonrası yeniden okuma · varsayılan varyant sırası · grid hata süzgeci · sıralı kolon yüklemi · validator metni | mantık sahte modüllerle ölçüldü, **tarayıcıda ÖLÇÜLMEDİ** | §5 |
| Kolon tarih/sayı filtresinin kabul ettiği metinler | `util/Tarih` + `util/Sayi` + kolon filtresi tarayıcıda (CDN 1.71.85 · 1.120.52; `tr` ve `en`; gerçek grid) ölçüldü. Gerçek backend'e giden `$filter` ÖLÇÜLMEDİ (literal `ODataUtils.formatValue` ile ölçüldü) | §0 adım 2 |
| Kolon filtresi penceresi (`util/KolonFiltrePenceresi` + `util/ColumnFilterParser` + menü öğesi) | tarayıcıda ölçüldü (CDN 1.71.85 · 1.120.52; `tr`; gerçek grid + menü kutusu; binding `JSONModel`): öğe dört kolon türünde görünür, pencere koşul listesi/ikinci değer/hata/dolu açılış/kaldır, kutuda koşul yazımı reddi + önceki filtre korunur, iki sürümde AYNI. **OData `$filter` metni ve gerçek backend ÖLÇÜLMEDİ**; 1.72–1.119 ve `AnalyticalTable` menüsü ÖLÇÜLMEDİ | §0 adım 2 · §4 `_addFilterMenuItem` |
| Excel dışa aktarımının 1.71'de ve 1.120'de dosya üretmesi | yalnız kaynak okundu, **çalışma zamanında ÖLÇÜLMEDİ** | §0 adım 2 |
| Sürüm yüzeyi testinin kapsamı | test bir **ad listesidir**: yalnız bir sürümde VAR OLMAYAN API adlarını yakalar; iki sürümde de var olan bir API'nin farklı girdi kabul etmesini / farklı varsayılanını göremez (`Spreadsheet` `dataSource: <binding>` bu yüzden ayrı kuralla denetlenir). Bilinen vakalara ayrı kural var (`getSortOrder() "None"`, `_addFilterMenuItem`, Spreadsheet `dataSource`, kolon kutusu = düz arama). Yeni bir ortak API kullanırken iki sürümdeki **gövdesini** oku | §4 |

## 1. Kopyalama (sıra önemli)

1. Backend UI5 sürümünü **ölç**: `GET https://<DEV_HOST>:<PORT>/sap/public/bc/ui5_ui5/resources/sap-ui-version.json`
   → `version` (komutlar: `references/app-skeleton.md` §7.1). Tahmin etme; bootstrap backend'den yapılır.
2. `app/` içeriğini paketin `ui/<uygulama>/` klasörüne kopyala.
3. Sürüme uyan `surum/<v>/webapp/` içeriğini kopyanın `webapp/` dizininin **üstüne** kopyala (iki dosya: `index.html`
   + `util/SurumParca.js`). Bu adım atlanırsa `index.html` hiç olmaz ve uygulama `util/SurumParca` modülünü bulamaz —
   açılmaz. `index.html` sürüme bağlıdır çünkü bootstrap öznitelik adlarının yazımı sürüme bağlıdır: 1.71.85 adı
   yalnız küçük harfe çevirir ⇒ `data-sap-ui-on-init` 1.71'de TANINMAZ; 1.120.52 tireli adı camelize eder ve küçük
   harf takma adı da tanır. Bant: backend < 1.120 → `surum/1.71` · ≥ 1.120 → `surum/1.120`. 1.72–1.119 arasında
   kendi sürümünü `surum/1.71/README.md` §Ara sürümler tablosuyla karşılaştır.
4. Yer tutucuları değiştir (§2) ve `util/Config.js`'i servisin entity/alan adlarıyla doldur (canlı `$metadata`'dan —
   `scripts/fetch_ui_source.py metadata`).
5. Ekran alanlarını (kolonlar, seçim alanları, değişiklik ekranı alanları) uygulamanın kendi tasarımına göre yeniden
   yaz — şablondaki alanlar örnektir. Tekrar kullanılan şey **akış ve altyapıdır**, alan kümesi değil.

## 2. Yer tutucular

| Yer tutucu | Nerede | Değer |
|---|---|---|
| `com.example.alan.uygulama` / `com/example/alan/uygulama` | tüm `webapp/`, `package.json`, `ui5*.yaml` | uygulama namespace'i (`references/app-skeleton.md` §1). Noktalı ve eğik çizgili iki biçimin İKİSİ de değiştirilir |
| `<TEMA>` | `index.html`, `ui5.yaml` | §3 tema kuralı |
| `<UYGULAMA_BASLIGI>` | `index.html` `<title>` | tarayıcı sekmesi başlığı (i18n `appTitle`'dan ayrı, düz metin) |
| `<MANIFEST_SURUMU>` | `manifest.json` `_version` | `surum/<v>/README.md` |
| `<BACKEND_UI5_SURUMU>` | `manifest.json` `minUI5Version` | 1. adımda ölçülen `version` |
| `<SERVIS_ADI>` | `manifest.json` `dataSources` | OData V2 servis adı (kullanıcıdan) |
| `<DEV_HOST>` · `<PORT>` · `<CLIENT>` | `ui5.yaml`, `ui5-deploy.yaml` | `.conn_adt` ile birebir aynı host (`references/app-skeleton.md` §6) |
| `<BSP_ADI>` · `<SAP_PAKET>` · `<TRANSPORT_NO>` · `<UYGULAMA_ACIKLAMASI>` | `ui5-deploy.yaml`, `package.json` | deploy hedefi — **kullanıcı verir**; deploy yalnız `scripts/deploy_ui.py` ile (`references/deploy-and-local-run.md` §3). Yer tutucu kalırsa `deploy_ui.py prepare` hata verir |
| `ZSD001_*` adları | `util/Config.js`, `view/*.xml`, `controller/List.controller.js` | demo entity/VH adları — servisin gerçek adlarıyla değişir |
| `ZSD000_UI_VARIANT_O2` · `ZSD000_C_UI_VARIANT` | `util/Config.js` `VARIANT` | varyant servisi demo adı (`backend-referans/`); servis yoksa `VARIANT: null` |

Değiştirme sonrası kontrol: kopyada `<[A-Z_]+>` ve `com.example` araması **0 sonuç** vermeli.

## 3. Tema kuralı

`GET <backend>/sap/public/bc/ui5_ui5/resources/sap/ui/core/themes/sap_horizon/library.css` **200 döner VE içeriği
`.../themes/base/library.css` ile aynı DEĞİLSE** (md5 farklı) → `sap_horizon`; değilse → `sap_fiori_3`.

Neden yalnız "200" yetmez (kaynak ekip ölçümü 2026-11-02, CDN): 1.71.85'te `sap_horizon/library.css` **200** döner ama
md5'i `base/library.css` ile **aynıdır** (tema yok, temel stile düşüyor); 1.120.52'de farklıdır. Backend ICF'de de aynı
davranış ölçüldü (UI5 1.71.5, tüketici ölçümü): `sap_horizon` md5'i `base` ile aynı, `sap_fiori_3` farklı ⇒ kural
`sap_fiori_3` verir. Diğer backend sürümleri ÖLÇÜLMEDİ — kural iki durumu da kapsar.

## 4. Sürüm yüzeyi — hangi API nerede (kanıt)

Kural: **ortak gövde (`app/`) yalnız 1.71.85'te DE var olan public API'yi kullanır.** Sürüme bağlı ya da UI5-özel
(alt çizgili) API `surum/<v>/webapp/util/SurumParca.js`'te yaşar. Ölçüm kaynağı:
`https://ui5.sap.com/<sürüm>/resources/<modül>-dbg.js` (1.71.85 ve 1.120.52, 2026-11-02).

| API | 1.71.85 | 1.120.52 | Yer |
|---|---|---|---|
| `sap.ui.table.rowmodes.Auto` · `Table.rowMode` | modül 404; aggregation `hidden` | var (`@since 1.119`) | `SurumParca.satirModu` |
| `Table.visibleRowCountMode` + `minAutoRowCount` | var | deprecated (1.119) | `SurumParca.satirModu` (yalnız 1.71) |
| `sap.m.IllustratedMessage` | 404 | var (`@since 1.98`) | `SurumParca.bosDurum` |
| `sap.ui.core.IAsyncContentCreation` | yok | var (`@since 1.89`) | `SurumParca.bilesenArayuzleri` |
| `MultiInput.addValidateToken` (public) | yok (yalnız iç `_tokenizer._addValidateToken`) | var | **kullanılmaz** — ortak gövde `addValidator` + `addToken` |
| MultiInput `_validateOnPaste` olayı (özel) | var | var | `SurumParca.yapistirmaBagla` (alt çizgili ⇒ ortakta değil) |
| Bootstrap öznitelik adları (`data-sap-ui-…`) | yalnız küçük harfe çevrilir — `oninit`, `resourceroots` | tireli ad camelize + küçük harf takma ad | `surum/<v>/webapp/index.html` |
| Manifest `sap.app.i18n` nesne (`bundleUrl`…) | YOK (`Manifest-dbg.js` `new URI(sI18n)`) | var | ortak gövde DİZGİ kullanır |
| ResourceModel `supportedLocales` · `fallbackLocale` | YOK (yok sayılır) | var | ortak (`models.i18n.settings`, 1.71'de etkisiz) |
| `Table` olayı `rowsUpdated` | YOK (yalnız özel `_rowsUpdated`) | var (`@since 1.86`) | **kullanılmaz** — kayıt sayısı satır binding'inin `dataReceived` olayından (`bindRows({events})`) |
| `Column` sıralı mı | `sorted` varsayılan `false`, `sortOrder` varsayılan `Ascending`, enum'da `None` YOK | `sortOrder` varsayılan `None`, `sorted` deprecated | `SurumParca.siraliMi` |
| MultiInput validator'ına gelen yazılı metin | HAM | KAÇIŞLI (`escapeSettingsValue`) | `SurumParca.dogrulayiciMetni` → ortak gövde HAM metinle çalışır |
| `MultiInput.addValidator` · `Token` `setKey`/`setText` · `Component.getOwnerComponentFor` · ODataModel `metadataUrlParams` · `Table` `getSortedColumns`/`attachFilter`/`enableColumnFreeze`/`threshold`/`extension`/`noData` · `ValueHelpDialog` · `sap.ui.export.Spreadsheet` (`worker:false`) | var | var | ortak |
| Spreadsheet `dataSource` kabul ettiği girdi | URL dizgisi · dizi · `{dataUrl, …}` nesnesi — ListBinding dalı YOK | + `ListBinding`/`TreeBinding` | ortak gövde iki sürümde geçerli biçimi kurar: `{type:"odata", dataUrl: binding.getDownloadUrl("json"), headers, count, useBatch:false}` |
| `ODataListBinding.getDownloadUrl(sFormat)` | var — `$format` + aktif `$orderby`/`$filter` + model URL parametreleri | var — aynı + `Filter.NONE`'da `null` | ortak (`null` korumalı) |
| `DateFormat.getDateInstance({strictParsing: true})` | var; `strictParsing` yedek biçimlere de geçer | aynı | ortak (`util/Tarih.metindenGun`). Tarayıcıda ölçüldü (`tr`): `strictParsing`'siz `31.11.2026`→1 Ara · `29.02.2026`→1 Mar; sıkı ayrıştırmada `null` |
| `NumberFormat.getFloatInstance({parseAsString: true})` | var; gruplama ayırıcısının YERİ denetlenmez, `strictGroupingValidation` YOK | aynı + `strictGroupingValidation` | ortak (`util/Sayi.metindenSayi` — gruplamayı aynı biçimle yeniden yazıp karşılaştırır). Tarayıcıda (`tr`): `1.250`→`1250` · `1.250,5`→`1250.5`; `1.25` · `1.2.3` · `12%` → `null` |
| V2 `$filter` sayı literali (`ODataUtils.formatValue`) | dizgi birleştirme: Decimal `v+"m"` … | aynı | ortak gövde kanonik dizgi (`"1250"`) verir; ham TR metni `"1.250"` → `1.250m` olurdu |
| Kolon menüsü `ColumnMenu._addFilterMenuItem` (ÖZEL) — "Filtre…" öğesi | var | var (menü adaptörü farklı modülde) | `SurumParca.filtreMenusuneEkle` (alt çizgili ⇒ ortakta DEĞİL). Metot bulunamazsa öğe eklenmez, `Log.error`, kutu düz arama çalışmaya devam eder |
| `ListBinding.getCount()` | YOK (`@since 1.93`) | var | **kullanılmaz** — ortak `isLengthFinal() ? getLength()` |

**Ortak gövdede bulunmaması gereken desenler** (`tests/test_ui5_sablon.py` zorlar; yorumlar hariç):
`IllustratedMessage` · `rowmodes` · `sap/m/VariantManagement` · `sap.m.VariantManagement` · `IAsyncContentCreation` ·
`addValidateToken` · `_validateOnPaste` · `data-sap-ui-` · `"bundleUrl"` · `rowsUpdated` · `getSortOrder()` ile
`"None"` karşılaştırması · `_addFilterMenuItem`. Test ayrıca `index.html`'in sürüm parçasından geldiğini ve öznitelik
biçiminin sürüme uyduğunu, `sap.app.i18n`'in dizgi olduğunu, Spreadsheet `dataSource`'unun `dataUrl` anahtarlı nesne
olduğunu ve kolon kutusunun koşul yazımını reddedip pencereye kablolu olduğunu (sözdizimsel) zorlar.

**Bilinçli istisna (ortakta kalan UI5-özel alan):** `util/TablePersonalizer.js` ana modelin `aUrlParams` /
`mMetadataUrlParams` alanlarını okur (sap-client'ı varyant servisine taşımak için, `references/freestyle-odata-v2.md`
§7.4). Alanlar tip korumalı okunur; yoksa çereze düşer, patlamaz. İki sürümde de var.

## 5. Şablonun taşıdığı kurallar (nerede)

| Davranış | Dosya | Kural |
|---|---|---|
| Liste = `sap.ui.table.Table` grid, native kolon menüsü | `view/List.view.xml` | `references/list-grid-alv.md` §2 · `check_list_view_grid.py` |
| SELECT-OPTIONS paritesi, harf duyarsız arama, `caseSensitive` YOK | `controller/Filter.controller.js`, `util/TokenValidator.js` | `list-grid-alv.md` §6 · `check_filter_search_pattern.py` |
| Yazılı metin token'a dönüşmeden Listele YOK | `Filter.controller.js` `_untokenizedFields` | `list-grid-alv.md` §6.1 · FE-50 |
| Kolon kişiselleştirme + kullanıcı varyantı (servis yoksa uyarı + yerel) | `util/TablePersonalizer.js` | `list-grid-alv.md` §3 · UI-PERSO-01 |
| sap-client'ın varyant servisine taşınması | `util/TablePersonalizer.js` | `freestyle-odata-v2.md` §7.4 · FE-48 |
| Grid veri hatası görünür (sessiz boş liste YOK); yalnız grid'in kendi GET isteği | `List.controller.js` `_gridIstegiMi` · `_onRequestFailed` | `freestyle-odata-v2.md` §6.2 |
| Tarih-yalnız alan: takvim gününün UTC gece yarısı (seçim sınırları, kolon tarih filtresi SIKI ayrıştırma, gönderilen gövde) | `util/Tarih.js` (`BaseController.utcGun` · `TablePersonalizer` · `Change._pick`) | FE-45 |
| Sayı kolonu filtresi oturum dilinin biçimiyle ayrıştırılır, OData'ya kanonik dizgi gider | `util/Sayi.js` · `ColumnFilterParser.degerCoz` | §4 `NumberFormat` |
| Kolon filtresi = **Filtre… penceresi** (koşul listeden SEÇİLİR) + menüdeki **kutu yalnız düz arama**; kutuya koşul yazımı reddedilir, önceki filtre korunur | `util/KolonFiltrePenceresi.js` · `util/ColumnFilterParser.js` · `TablePersonalizer._onMenuAc` / `_onColumnFilter` · `SurumParca.filtreMenusuneEkle` | `list-grid-alv.md` §6.4 · FE-32 (e) |
| Kaydetme: JSON tampon, sıralı çağrılar, gerçek SAP mesajı, `MessageBox.success` sonrası navigasyon; yarıda kalan kaydetmede kayıt yeniden okunur | `controller/Change.controller.js` `_runSeq` · `_err` · `_load` | `freestyle-odata-v2.md` §1 · §6 · FE-29 · FE-38 |
| Excel: filtreye uyan tüm satırlar (aktif seçim + kolon filtresi + sıralama, `getDownloadUrl`), kapsam sorusu; URL üretilemezse `Log.warning` + mesaj | `List.controller.js` `onExportExcel` · `_doExport` | `list-grid-alv.md` §3 |
| Varsayılan varyant değişimi SIRALI (önce eski kapatılır, sonra yeni açılır) | `util/TablePersonalizer.js` `_setVariantAsDefault` | FE-38 |

## 6. Kopyadan sonra ölçüm

```bash
S=<TEMPLATE>/skills-sap/sap-ui5-fiori/scripts
python $S/check_ui5_freestyle_traps.py <app>
python $S/check_list_view_grid.py <app>
python $S/check_filter_search_pattern.py <app>
python $S/check_i18n_keys.py <app>
python $S/check_ui_odata_refs.py --app <app> --metadata <kaydedilen $metadata>
python $S/deploy_ui.py prepare <app> --no-build
```

Her çıktının **KAPSAM** satırını oku — `0 dosya` görürsen kopya yanlış yerdedir, sonuç okunamaz. `check_ui_odata_refs`
canlı servisin kaydedilmiş `$metadata`'sına karşı entity/alan adlarını doğrular. Kontrol listesi:
`references/checklists.md` (Faz 1–6 + FE). Şablonun kendi testi: `tests/test_ui5_sablon.py` (iki sürüm parçasıyla
geçici bir uygulama kopyası kurar, statik kontrolleri koşar, sürüm yüzeyi kuralını zorlar).
