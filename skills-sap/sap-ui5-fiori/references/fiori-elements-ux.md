# UX kuralları, Fiori Elements (annotation) ve genel desenler

> Varsayılan yaklaşım **freestyle + OData V2**'dir; bu dosyadaki genel UX ilkeleri her uygulamada geçerlidir.
> Fiori Elements (annotation tabanlı) yalnız mevcut bir FE ekranına dokunulması gerektiğinde. Freestyle mekanik kurallar
> (`freestyle-odata-v2.md`, `list-grid-alv.md`) bu dosyadaki genel örneklerle çelişirse **onlar geçerlidir**; bilinen
> çelişkiler §8'de.

---

## 1. UI yaklaşımı kararı
İşin başında bir satırla yaz:
```
UI yaklaşımı: Freestyle | Fiori Elements | Hybrid
Gerekçe: <tek cümle>
OData servis / EntitySet: <ad>
```
Proje yaklaşımı sabitse (freestyle) soru tekrar sorulmaz. FE ekranı bu skill'in freestyle kurallarını değiştirmez.

## 2. Zorunlu UX kuralları

| # | Kural | Nasıl |
|---|---|---|
| L1 | **Hızlı filtre** her liste sayfasında | `IconTabBar` (sayaçlı `IconTabFilter`, `iconColor` Positive/Critical/Negative) ya da `SegmentedButton`; seçimde durum filtresi + mevcut arama filtresi AND |
| L2 | **İlk açılışta 6–8 kolon** | Sıra: tanımlayıcı → ana bilgi → durum → ana metrik (sağ) → ikincil → üçüncül; kalanı kolon göster/gizle (grid) |
| L3 | **Ham kod gösterme** | Formatter + i18n (`"A"` → "Aktif"); kod gerekiyorsa `ObjectIdentifier title="{Kod}" text="{Ad}"` ya da tooltip |
| L4 | **Boş durum yönlendirici** | `IllustratedMessage` (`sapIllus-EmptyList`) + eylem butonu; filtre sonucu boşsa `sapIllus-NoFilterResults` + "Filtreleri temizle" |
| L5 | **Satır içi düzenleme dikkatli** | Backend pessimistic kilit kullanıyorsa çok satırı düzenleme moduna açmak başka kullanıcıları kilitleyebilir → yalnız basit ana veri tablolarında ya da draft etkinse; aksi hâlde detay sayfası + Düzenle |
| L6 | **Uzun form** | Adım adım gösterim (`Wizard`); öneri listeli `Input` (`showSuggestion`) |
| L7 | **Yapma listesi** | aşağıda |

**L7 — asla:**
1. UI'ı bilgiyle boğma (6–8 kolon; detay ayrı sayfada).
2. Teknik alan gösterme (GUID, MANDT, iç kod, ham zaman damgası).
3. i18n'siz etiket (sabit metin çevrilemez).
4. Ham durum kodu.
5. **Tüm sayfayı busy yapma** — yalnız etkilenen bileşen (tablo, buton); `BusyDialog` yalnız kritik engellemede.
6. Tutarsız yerleşim (aynı entity = aynı kolon sırası; aynı aksiyon = aynı yer; aynı durum = aynı renk).
7. Eylemsiz boş durum.
8. Filtresiz liste sayfası.
9. Varsayılan tarayıcı stili — Horizon teması, özel CSS yalnız tema değişkenleriyle.
10. **Onaysız silme/iptal** — `MessageBox.confirm`; geri alınamaz işlemde uyarı tipi.

## 3. On ilke
1. Yoğunluk: masaüstünde compact (mobilde cozy).
2. Geri bildirim: her eylemde anında görsel tepki (busy).
3. Boş durum her tabloda.
4. Hata durumu anlamlı mesajla — ham teknik hata değil, ama **gerçek SAP mesajı yutulmadan** (`freestyle-odata-v2.md` §6.2).
5. Navigasyon: geri butonu her zaman çalışır; detay sayfasında breadcrumb.
6. Yükleme: tablo seviyesinde busy, sayfa değil.
7. Tipografi: yalnız Fiori font ölçeği.
8. Renk: yalnız tema değişkenleri.
9. İkon: yalnız `sap-icon://`.
10. Duyarlı: L/M/S kırılımları test edilir.

## 4. Mesajlar
- **Başarı** (save/create/aksiyon): `MessageBox.success(<belge no'lu metin>, { onClose })` — `freestyle-odata-v2.md` §6.1.
- **Doğrulama hataları** (form, çoklu): `MessagePopover` + mesaj modeli; footer'da sayaçlı buton (`type` Negative).
  ```javascript
  var oMM = sap.ui.getCore().getMessageManager();          // yeni sürümlerde Messaging modülü — sürüme göre doğrula
  this.getView().setModel(oMM.getMessageModel(), "message");
  oMM.registerObject(this.getView(), true);
  ```
  `sap.ui.getCore().getMessageManager()` yeni UI5 sürümlerinde deprecated olabilir — proje sürümünde API referansıyla
  DOĞRULANMADI.
- **Navigasyonsuz anlık bilgi** (kopyalandı, satır seçildi, silindi ve liste yerinde): `MessageToast`.
- Kaydedilmemiş değişiklik varken çıkış → uyarı (navigation guard).

## 5. Durum gösterimi
Durum alanı düz metin değil: renk + ikon + metin.
```xml
<ObjectStatus text="{StatusText}"
              state="{ path: 'Status', formatter: '.formatter.statusState' }"
              icon="{ path: 'Status', formatter: '.formatter.statusIcon' }"/>
```
`state`: Success / Warning / Error / Information / None. Başlık KPI'ında `inverted="true"`. m.Table satırında `highlight`.
Kod → state/ikon eşlemesi uygulamaya özeldir (durum kodları backend'den).

## 6. Tema ve CSS
- Sabit hex/rgb yok; `var(--sapBrandColor)`, `--sapPositiveColor`, `--sapNegativeColor`, `--sapCriticalColor`,
  `--sapInformativeColor`, `--sapTile_Background`, `--sapList_BorderColor`, `--sapContent_Shadow0..3`,
  `--sapElement_BorderCornerRadius`, `--sapFontSmallSize` gibi tema değişkenleri.
- Morning ve Evening Horizon'da bakılır.
- CSS sınıfları uygulama önekiyle (`.zxx001…`), kök sınıf altında.

## 7. Erişilebilirlik
- İkon butonlarda `tooltip` + gerekirse `ariaLabelledBy` → `InvisibleText`.
- `Label labelFor="<inputId>"`.
- Klavye: Tab/Enter/Escape çalışır. Global kısayol (Ctrl+S) eklenirse `onExit`'te kaldırılır:
  ```javascript
  onInit: function () { $(document).on("keydown.zxx001", function (e) { if (e.ctrlKey && e.key === "s") { e.preventDefault(); this.onSave(); } }.bind(this)); },
  onExit: function () { $(document).off("keydown.zxx001"); }
  ```

## 8. Detay sayfası ve yerleşim — bilinen çelişkiler

| Konu | Durum | Bu skill'in tavrı |
|---|---|---|
| **`sap.f.DynamicPage` şablonu** | Kaynak UI standardının genel şablonu `sap.f` kullanıyor; aynı standart ve bilinen hatalar kaydı `sap.f`'yi (DynamicSideContent 404) yasaklıyor | Proje UI5 sürümünde `sap.f` yüklenmesi ölçülmeden kullanılmaz. Varsayılan: `sap.m.Page` + toolbar, ya da `sap.uxap.ObjectPageLayout`. `sap.f.DynamicPage`'in 404 verip vermediği **DOĞRULANMADI** (kaynaktaki 404 `DynamicSideContent` içindi) |
| **Form yerleşimi** | Kaynak standart başlık alanları için "SimpleForm/ResponsiveGridLayout kullanma, HBox/VBox kullan" diyor; kaynağın UI araç notu "SimpleForm değil `Form` + `ColumnLayout`" diyor; kaynak playbook "SimpleForm compact ayarı" öneriyor | Başlık/filtre alanları: **HBox > VBox (Label + Input + açıklama Text)**. Detay formu: `sap.ui.layout.form.Form` + `ColumnLayout` (içine container konmaz — T4). `SimpleForm` yeni ekranda kullanılmaz. HBox/VBox ile Form **karıştırılmaz** |
| **`MessageToast` + navigasyon** | Kaynak playbook save kutusu ve oluşturma kontrol listesi toast diyor; kaynak standart ve hata listesi yasaklıyor | `MessageBox.success` (§4) |
| **`_handleODataError` / `_parseError`** | İki isim, aynı fikir | Tek isim `_parseError` |
| **Hızlı silme ("optimistic UI")** | Genel örnek satırı önce gizleyip sonra `remove` yapıyor | Silme onaylı (L7-10), seçim ve pending guard kuralları (`delete-flow-ui.md`) önce gelir |

Başlık alanı deseni:
```xml
<HBox alignItems="Start" class="sapUiSmallMarginBeginEnd sapUiTinyMarginTop">
  <VBox class="sapUiSmallMarginEnd">
    <Label text="{i18n>filter.customer}" required="true" design="Bold" labelFor="inpCustomer"/>
    <Input id="inpCustomer" value="{v>/header/Customer}" width="9em" showValueHelp="true" valueHelpRequest=".onVH"/>
    <Text text="{v>/header/CustomerName}" tooltip="{v>/header/CustomerName}" class="zxx001FieldDesc"/>
  </VBox>
</HBox>
```
- Salt-okunur başlık bilgisi toolbar'da `VBox (Label + Text)` çiftleriyle; `ObjectStatus title+text` yapışık görünür.
- Sayfa başlığında görünen anahtar (belge no) ayrıca form alanı yapılmaz.
- Aynı belge ailesi (liste + filtre → başlık + kalem) uygulamaları aynı yerleşimi paylaşır.

## 9. Fiori Elements (annotation) — yalnız mevcut FE ekranına dokunurken

```xml
<Annotations Target="ZXX001_UI_ORDER_O2.OrderType">
  <Annotation Term="UI.SelectionFields">
    <Collection><PropertyPath>Customer</PropertyPath><PropertyPath>Status</PropertyPath></Collection>
  </Annotation>
  <Annotation Term="UI.LineItem">
    <Collection>
      <Record Type="UI.DataField"><PropertyValue Property="Value" Path="OrderId"/></Record>
      <Record Type="UI.DataField">
        <PropertyValue Property="Value" Path="Description"/>
        <PropertyValue Property="Importance" EnumMember="UI.ImportanceType/High"/>
      </Record>
    </Collection>
  </Annotation>
  <Annotation Term="UI.HeaderInfo">
    <Record>
      <PropertyValue Property="TypeName" String="Order"/><PropertyValue Property="TypeNamePlural" String="Orders"/>
      <PropertyValue Property="Title"><Record Type="UI.DataField"><PropertyValue Property="Value" Path="Description"/></Record></PropertyValue>
    </Record>
  </Annotation>
  <Annotation Term="Common.ValueList" Qualifier="Status">
    <Record Type="Common.ValueListType">
      <PropertyValue Property="CollectionPath" String="StatusVHSet"/>
      <PropertyValue Property="Parameters"><Collection>
        <Record Type="Common.ValueListParameterInOut">
          <PropertyValue Property="LocalDataProperty" PropertyPath="Status"/>
          <PropertyValue Property="ValueListProperty" String="StatusCode"/>
        </Record>
      </Collection></PropertyValue>
    </Record>
  </Annotation>
</Annotations>
```
- Etiketler sabit string yerine i18n'e bağlanır (L7-3).
- RAP tabanlı serviste annotation'lar metadata extension (DDLX) ile backend'de. DDLX kabuğu v0.5.2'den beri CLI'de var
  (`adt_post_shell` `ddlx` → `adt_push_source` → `adt_activate`, canlı ölçüldü 2026-09-22; hedef CDS
  `@Metadata.allowExtensions: true`) → `%sap-rap`.
- Annotation dataSource'u manifest'e eklerken `app-skeleton.md` §8.1.

## 10. Kalite kontrol listesi (tasarım)
- **Yerleşim:** compact; sayılar sağa hizalı; yapışkan kolon başlıkları.
- **Görsel:** durum renk + ikon; header KPI'ları (detay sayfası); geri navigasyon çalışır.
- **Geri bildirim:** her buton busy; başarı `MessageBox.success`; boş durum; doğrulama `MessagePopover`; kaydedilmemiş değişiklik uyarısı.
- **Duyarlı:** L/M/S; masaüstü compact.
- **Tema:** sabit renk yok; iki Horizon varyantında bakıldı.
- **Erişilebilirlik:** tooltip, label ilişkisi, klavye.
- **Veri:** 6–8 kolon; teknik alan gizli; ham kod yok; tüm etiketler i18n.
- **Tutarlılık:** aynı entity/aksiyon aynı yerde; hızlı filtre; boş durumda eylem.

---

## Bu dosyada ÇIKARILAN / DEĞİŞTİRİLEN
- Kaynak standardın genel UI bölümündeki uzun örnekler (tam Object Page, KPI kartları, m.Table desen koleksiyonu, `$batch`
  örneği, filtre API tablosu) özetlendi; m.Table desenleri `list-grid-alv.md` §7 istisnasına, `$batch`
  `freestyle-odata-v2.md` §10'a, filtre `list-grid-alv.md` §6'ya taşındı.
- `sap.f.DynamicPage` şablonu alınmadı (§8 çelişki). Genel controller iskeletindeki `callFunction method:"POST"` örneği
  alınmadı (`freestyle-odata-v2.md` §7.2 — yöntem metadata'dan).
- Genel F4 örneğindeki "ValueHelpDialog'u JSON modelle doldur" deseni alınmadı; freestyle VH kuralları `freestyle-odata-v2.md` §3.
- Kaynaktaki "optimistic delete" ve toast örnekleri silme kurallarıyla çeliştiği için alınmadı.
