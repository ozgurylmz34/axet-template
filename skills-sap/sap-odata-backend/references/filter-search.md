# Filtre ve arama — Gateway (`/IWBEP`) davranışı

> Kaynak: ekip hafızası "rapor filtre = select-options + contains" dersinin backend yarısı, UI kodlama standardının
> harf-duyarsız arama bölümü, OData servisleri playbook'u (`$filter ... and` notu), backend standardı
> (`get_filter_select_options`). UI5 kontrol seçimi (MultiInput, ValueHelpDialog) UI5 skill'inin konusudur.

---

## 1. Desteklenen / desteklenmeyen `$filter` fonksiyonları (SAP Gateway V2)

| İfade | Gateway (`/IWBEP`) | Ölçüm |
|---|---|---|
| `toupper( … )` / `tolower( … )` | **Desteklenmez** → `HTTP 400 "Function toupper/tolower is not supported"` (SAP Note 1797736) | canlı |
| `substringof( 'x', Alan )` (Contains) | desteklenir | canlı |
| `startswith( Alan, 'x' )` | desteklenir | canlı probe |
| `endswith( Alan, 'x' )` | desteklenir | canlı probe |

- **Tuzak:** UI5 V2 modelinde `Filter`'a `caseSensitive: false` verilince istemci `$filter`'a `toupper()`/`tolower()`
  enjekte eder → servis 400 → kullanıcıya "arama sonuç vermiyor" gibi görünür. Backend'de bunun çaresi yok;
  istemci `caseSensitive` parametresini **hiç vermez**.
- **Harf duyarsızlığı:** düz `substringof` ölçülen sistemde harf-duyarsız çalıştı (küçük harfli terim, büyük harfle kayıtlı adı buldu, 200). Kaynak bunu
  DB collation'ına bağlıyor. Sınır: tek sistem; başka DB/collation ya da ABAP'ta süzme yapan DPC için
  **DOĞRULANMADI** (§3).

## 2. Wildcard sözleşmesi (UI ↔ backend)
Ekip standardındaki arama terimi yorumlaması (istemci tarafında yapılır, backend'e fonksiyon olarak gelir):

| Kullanıcı yazar | Gönderilen |
|---|---|
| `x` ya da `*x*` | `substringof` (Contains) |
| `x*` | `startswith` |
| `*x` | `endswith` |

Literal yıldız aranmaz. Backend bu üç fonksiyonu desteklemelidir; kendi DPC_EXT'inde filtreyi elle işliyorsan (§3)
üçünü de ele al.

## 3. DPC_EXT'te filtreyi okumak
```abap
DATA(lt_filters) = io_tech_request_context->get_filter( )->get_filter_select_options( ).
DATA(lt_name)    = VALUE #( lt_filters[ property = 'CustomerName' ]-select_options DEFAULT VALUE #( ) ).
SELECT … FROM … WHERE customer_name IN @lt_name INTO TABLE @DATA(lt_result).
```
- Filtreler `WHERE`'e verilir; veriyi çekip ABAP'ta süzme yok (`references/backend-coding.md` §1).
- `substringof`/`startswith`/`endswith`'in select options'a hangi `OPTION`/`LOW` biçimiyle (ör. `CP` + `*x*`)
  çevrildiği ve bu durumda harf duyarlılığının ne olduğu kaynaklarda **ölçülmedi** → yeni DPC'de bir kez canlı ölç
  (aynı terimi küçük ve büyük harfle ara, sonuç sayılarını karşılaştır) ve `%remember` ile kaydet.
- ABAP'ta `CP` karşılaştırması ve `IN` range'i Unicode büyük/küçük harfe duyarlıdır; harf-duyarsız arama isteniyorsa
  bu yolda ayrıca ele alınmalıdır — **DOĞRULANMADI**, ölç.
- Özellik adı `property` alanında ABAP adı değil **OData property adıyla** gelir (örnekte `CustomerName`). Hangi
  adla geldiğini ilk kullanımda debug/log ile doğrula — **DOĞRULANMADI**.

## 4. ABAP'tan başka bir OData servisine `$filter` gönderirken
- `$filter=… and …` içeren URL, ABAP HTTP istemcisinden gönderilince `&` / boşluk kodlaması sorun çıkarabildi.
- **Tercih edilen:** anahtarla doğrudan okuma ya da navigation property:
  ```abap
  " TERCİH: anahtarla doğrudan GET
  lv_path = |/sap/opu/odata/sap/API_BUSINESS_PARTNER/A_BusinessPartnerTaxNumber(BusinessPartner='{ iv_bp }',BPTaxType='{ lv_tax_type }')?$select=BPTaxType&$format=json|.
  " SORUN ÇIKABİLİR: $filter … and …
  ```
- Filtre kaçınılmazsa değerleri URL-encode et ve sonucu canlı ölç. Proxy ile URL kurma: `references/outbound-api-call.md` §2.

---

## Bu dosyada ÇIKARILAN / DEĞİŞTİRİLEN
- UI5 kontrol kuralları (MultiInput + ValueHelpDialog, `_parseSearchTerm` yardımcısı, grid kolon filtresi) ve
  kanonik UI referans uygulaması alınmadı (UI5 skill'i).
- Kaynaktaki UI doğrulayıcısı (`check_filter_search_pattern`) aXet'te yok; backend tarafında karşılığı gerekmiyor.
