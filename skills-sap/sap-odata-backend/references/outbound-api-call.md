# ABAP'tan SAP-içi OData API çağrısı

> Kaynak: RAP playbook'u "SAP-içi HTTP/OData servis çağrısı" bölümü (kanonik iç proxy + SM59 legacy), ekip hafızası
> "API call iç gateway proxy", OData servisleri playbook'u (standart fiyat simülasyonu ve BP API dersleri),
> backend hata kontrol listesi. Senaryo: ABAP (DPC_EXT, RAP handler, klasik sınıf, FM) aynı sistemdeki standart ya
> da Z bir OData servisini çağırır (fiyat simülasyonu, iş ortağı, vergi …).
> **Yer tutucular:** `<ORTAK_PKG>` = projede token/URL yardımcısını barındıran ortak paket, `ZCL_<ORTAK>_GET_TOKEN` =
> o yardımcı sınıf. Bu adlar projeye göre değişir; paket `.rules.md` ya da kullanıcıdan öğrenilir.

---

## 1. Kanonik yöntem — iç gateway proxy

**Neden SM59 değil:** SM59 host'u yapılandırmaya taşır ama `sap-client` kodda sabit kalır → QA/PRD istemci
değişiminde kırılır. İç proxy host'u ve istemciyi çalışma zamanında alır → sistem ve istemci bağımsız, kimliksiz.

**Üç parça:**
1. **Ortak token/URL yardımcısı** (`ZCL_<ORTAK>_GET_TOKEN`, `<ORTAK_PKG>`): başka bir ekibin/geliştiricinin paylaşılan
   objesiyse **değiştirilmez, yalnız kullanılır**.
   - `get_host( iv_method, iv_token )` → `https://<host>:<port>/sap/opu/odata/sap/<iv_method>?sap-client=<sy-mandt>`
     (host `TH_GET_VIRT_HOST_DATA`'dan, istemci `sy-mandt`'tan). `iv_token = abap_true` ise `&$top=1` ekler.
   - `get_token( iv_method )` → iç proxy GET ile `x-csrf-token` döndürür.
   - Projede böyle bir yardımcı **yoksa** yaratmak yeni ortak objedir: ad, paket ve sahiplik kullanıcı kararıdır;
     bu dosyadaki iç yapı ölçülmüş bir yardımcının davranışıdır, arayüzü tahmin etme.
2. **Motor:** `/iwfnd/cl_sutil_client_proxy=>get_instance( )->web_request( )` — SAP Gateway iç loopback. Harici HTTP,
   RFC destination, kimlik bilgisi yok. Tekil (singleton) oturum: token GET'i ile sonraki POST/PATCH aynı CSRF'i paylaşır.
3. **POST/PATCH çağrısı kendi paketinin sınıfında** yazılır; ortak yardımcıya genel POST eklenmez.
   `iv_method` biçimi: `'<SERVİS_SRV>/<Entity>'` (`get_host` `/sap/opu/odata/sap/` önekini ekler).

```abap
" 1) CSRF
DATA(lo_api)  = NEW zcl_<ortak>_get_token( ).
DATA(lv_csrf) = lo_api->get_token( iv_method = `API_X_SRV/A_Entity` ).

" 2) POST  (PATCH için request_method = 'PATCH' + ( name = 'if-match' value = '*' ))
/iwfnd/cl_sutil_client_proxy=>get_instance( )->web_request(
  EXPORTING
    it_request_header = VALUE #(
      ( name = if_http_header_fields_sap=>request_method value = 'POST' )
      ( name = if_http_header_fields_sap=>request_uri
        value = |{ lo_api->get_host( iv_method = `API_X_SRV/A_Entity` ) }&sap-language={ lc_language }| )
      ( name = if_http_header_fields=>content_type value = 'application/json' )
      ( name = if_http_header_fields=>accept       value = 'application/json' )
      ( name = 'x-csrf-token'                      value = lv_csrf ) )
    iv_request_body = cl_abap_codepage=>convert_to( lv_payload_json )
  IMPORTING
    ev_status_code     = DATA(lv_status)
    et_response_header = DATA(lt_hdr)
    ev_response_body   = DATA(lv_body_x)
  EXCEPTIONS OTHERS = 4 ).

DATA(lv_response) = cl_abap_conv_codepage=>create_in( )->convert( lv_body_x ).
DATA(lv_sap_msg)  = VALUE string( lt_hdr[ name = 'sap-message' ]-value OPTIONAL ).
```
- `sy-subrc` ve `lv_status` ayrı ayrı kontrol edilir; 2xx dışı yanıtta gövde + `sap-message` BAPIRET2'ye çevrilir
  (`references/serialization.md` §5).
- `lc_language`: 2 harfli dil kodu sabiti (ör. `CONSTANTS lc_language TYPE string VALUE 'TR'.`, projenin
  `master_language`'i). Ölçülen vakada sabit `TR` ile çalıştı. Dili kullanıcı oturumundan (`sy-langu`, 1 karakterli iç
  kod) türetmek ölçülmedi — **DOĞRULANMADI**; gerekiyorsa ISO'ya çevirip canlı ölç.
- **Canlı durum (ölçüldü):** proxy RAP behavior handler bağlamında sorunsuz çalıştı (dump yok); klasik sınıftan
  4 HTTP metoduyla (GET/POST/PATCH + URL kurucu) çalışan bir iş ortağı bakım sınıfı da canlı test edildi.

## 2. Tuzaklar

### 2.1 Dil — kritik
- `get_host` URL'ye yalnız `sap-client` koyar, **`sap-language` koymaz**. Eski SM59 kodu bunu başlıkta veriyordu.
  Vermezsen servis EN'de işler → birim/metin araması patlar:
  `HTTP 400: Unit <BİRİM> is not created in language EN`.
- **ÇALIŞAN YÖNTEM:** `request_uri`'ye `&sap-language=<dil>` ekle (hem token GET'inde hem POST'ta dil tutarlı olmalı).

### 2.2 Query'li URL (`?$filter`, `?$select`)
- `get_host( iv_method )` sonuna `?sap-client=…` eklediği için query içeren yolu `iv_method` olarak **verme**: çift `?` oluşur.
- **ÇALIŞAN YÖNTEM:** host:port'u boş method'la al, yolu kendin kur:
  ```abap
  DATA(lv_base) = NEW zcl_<ortak>_get_token( )->get_host( iv_method = `` ).
  DATA lv_hostport TYPE string.
  FIND REGEX `^(https?://[^/]+)` IN lv_base SUBMATCHES lv_hostport.
  DATA(lv_sep) = COND string( WHEN iv_path CS `?` THEN `&` ELSE `?` ).
  rv_url = |{ lv_hostport }{ iv_path }{ lv_sep }sap-client={ sy-mandt }|.
  ```
- `$filter … and …` yerine anahtarla doğrudan okuma tercih edilir (`references/filter-search.md` §4).

### 2.3 CSRF
- Yazma isteği CSRF ister: önce GET + `X-CSRF-Token: Fetch`. Entity yalnız POST destekliyorsa GET 404 dönebilir
  **ama token yine gelir** → token GET'inde durum koduna değil başlığa bak.

### 2.4 Released BO EML kapalıysa
Released BO'da `UPDATE/CREATE` EML operasyonu sistemde kapalıysa standart OData API'sine MERGE/PATCH bu proxy ile
yapılır; ilgili özel alanların (custom field) servise açılmış ve yayınlanmış olması gerekir. Önce operasyonun kapalı
olduğunu canlı ölç (`references/deep-insert-function-import.md` §4).

---

## 3. Standart API'lerde ölçülmüş payload dersleri
Tek bir S/4HANA sisteminde ölçüldü; sürüm/yapılandırmaya göre değişebilir → yeni sistemde `$metadata` ile yeniden doğrula.

### 3.1 `API_SALES_ORDER_SIMULATION_SRV` — fiyat simülasyonu
- Uç: `POST /A_SalesOrderSimulation`; **GET desteklenmez**.
- `"SalesOrder": ""` gövdede **zorunlu** (yoksa 400).
- `"to_Pricing": { "TotalNetAmount": null }` **zorunlu** — yoksa toplam net tutar deferred gelir, okunamaz.
- Kalemler `"to_Item": { "results": [ … ] }` sarmalayıcısıyla; kalem no dolgulu (`"000010"`), miktar string (`"10.000"`,
  `references/serialization.md` §1).
- Özel alan (`ZZ1_…`) yalnız o sistemin API metadata'sında **varsa** gönderilir; metadata'da olmayan alan → `400 Property is invalid`.
  Bir sistemde var olan özel alan diğerinde olmayabilir.
- `PricingDate` gibi `Edm.DateTime` alan → `/Date(ms)/` (`references/serialization.md` §2).
- Yanıtta kalem no **sıfırsız** döner (`"10"`) → istekteki `"000010"` ile birleştirirken normalize et.
- Başarılı ama tutar `0.00` → çoğunlukla fiyat koşulu tanımlı değil (SD yapılandırması); kod hatası sanma.
- Birim: simülasyona belgedeki **orijinal satış birimi** gönderilir; UI'da yapılan birim dönüşümü simülasyona
  uygulanınca `Satış ölçü birimi … kalem için tanımlanmadı` hatası alındı.

### 3.2 `API_BUSINESS_PARTNER` — iş ortağı yaratma/bakım
- `A_BusinessPartner` POST'unda `to_BusinessPartnerAddress` içinde `"Language"` verilmezse, sonraki müşteri rol
  ataması `Standart adresin dili yok` hatası verir → adres dilini gönder.
- Rol sırası: satış alanı görünümünden önce `A_BusinessPartnerRole` POST ile `FLCU01`; muhasebe görünümünden önce `FLCU00`.
- Rol ataması `409` (zaten var) dönerse akış durdurulmaz; hata sayılmaz.
- `A_CustomerSalesArea` yaratılınca SAP standart muhatap fonksiyonlarını (ölçülen TR oturumunda `SV/RG/WE/RE/AG`,
  sayaç 0) **otomatik** yaratır;
  aynı muhatap fonksiyonunu tekrar eklemeye çalışma.
- Test verisi (ödeme koşulu, mutabakat hesabı, org birimleri) sistemden okunur (`T052U`, `SKB1` …); hatırdan yazılmaz.

---

## 4. SM59 destination yöntemi — LEGACY (yeni kodda kullanma)
Mevcut kodda SM59 görürsen bilgi için; yeni çağrı §1 ile yazılır. SM59 destination'ı **kullanıcı/Basis yaratır**
(sistem yapılandırması); model yalnız aşağıdaki spesifikasyonu verir.

```abap
cl_http_client=>create_by_destination(
  EXPORTING destination = CONV rfcdest( '<HTTP_DEST>' )
  IMPORTING client      = lo_client
  EXCEPTIONS OTHERS = 4 ).
```

| # | Belirti | Kök sebep | Çözüm |
|---|---|---|---|
| 1 | `Client connection to http://<host>:443xx broken` | SSL kapalı → düz HTTP HTTPS portuna gidiyor | SM59 → Logon & Security → **SSL Active** |
| 2 | 401 (SSL sonrası) | logon kimlik göndermiyor | kimlik **SM59'da saklı** teknik kullanıcı (yapılandırmada, kaynakta değil) |
| 3 | 403 `/IWFND/MED/170 service 'sap' not found` / 404 `segment 'sap'` | `create_by_destination` Path Prefix'i **her zaman** URI'nin önüne ekler; kod tam yol verince çiftlenir | **Path Prefix BOŞ**, kod tam yol verir (`/sap/opu/odata/sap/<SRV>/<entity>`) → tek destination tüm aynı-sistem servislerine hizmet eder |
| 4 | POST CSRF hatası | token alınmadı | §2.3 |
| 5 | assertion ticket (current user) denemesi | aynı-sistem güven ACL'i ve RAP fazında ticket belirsiz | gerçek kullanıcı kimliği gerekmedikçe kullanma |
| 6 | `HTTP 403 CSRF token validation failed` | `refresh_request` SSL oturumunu sıfırlıyor | aynı istek nesnesiyle devam et, `refresh_request` kullanma |
| 7 | `SHTTP 852 cannot be processed in plugin mode HTTPS` | ICM HTTPS bağlamından SM59 HTTPS destination çağrısı | ölçülen ortamda başka destination ile oluşmadı; tekrar ederse §1 |
| 8 | `E 00 001 cannot be processed in plugin mode HTTPS` | `create_by_url` ile sistem kendi URL'ine HTTPS loopback yapamadı | §1 iç proxy |

**Ölçülmüş çalışan SM59 ayarları (legacy):** tip G (ya da aynı sistem için H) · hedef host = sistemin kendi host'u ·
port = HTTPS portu · **Path Prefix boş** · SSL Active · SSL istemci sertifikası standart (yoksa anonim) · logon
prosedürü "SAP RFC Logon" · kullanıcı/şifre/dil/istemci **SM59'da saklı**.

### 4.1 `MESSAGE` RAP handler'da dump eder
- `BEHAVIOR_ILLEGAL_STATEMENT · CL_HTTP_CLIENT · "Statement MESSAGE_E is not allowed"`: RAP handler `MESSAGE` deyimini
  yasaklar; `cl_http_client` **iletişim koptuğunda** (SSL/logon/erişilemez) içeride `MESSAGE` verir → dump.
- Mutlu yolda (200, hatta geçerli 4xx/5xx yanıtı) sorun yok. Klasik SEGW/DPC normal bağlamda koşar, orada dump etmez.
- Yerel `CALL FUNCTION` (destination'sız) etkilenmez.
- §1 iç proxy RAP handler'da bu dump'ı ölçülen vakada vermedi.

### 4.2 Teşhis — classrun probe
Bağlantıyı handler'a gömmeden önce `IF_OO_ADT_CLASSRUN` uygulayan geçici bir Z sınıfla dene: classrun RAP bağlamı
**dışında** koşar, gerçek HTTP durumu/istisnası görünür. CLI: `adt_post_shell` → `adt_push_source` → `adt_activate`
→ `adt_classrun` (hepsi yazma sınıfı: kapsam beyanı + onay).
- "Düzenledim ama eski çıktı geliyor": sınıf aktive edilmemiş ya da oturum bayat → `adt_inactive_objects` ile doğrula,
  çıktıda yeni koda özgü imza ara. ⛔ Yeni probe adıyla yeniden yaratma (denendi, çözmedi, çöp obje bıraktı).
  Ayrıntı: `%sap-adt-foundation` → `references/known-errors-adt.md` K-13.
- İş bitince probe sınıfı silinir (where-used + onay) ve kaynakta kimlik bilgisi kalmadığı doğrulanır.

---

## 5. Kimlik bilgisi kaynağa yazılmaz
- Eski kodda sık görülen `lo_client->authenticate( username = '…' password = '…' )` **kopyalanmaz**, yeni koda taşınmaz.
  Kimlik ya hiç yoktur (§1 iç proxy) ya SM59 yapılandırmasındadır (§4).
- Kaynak koda, test script'ine, loga, hafızaya kullanıcı adı/şifre/token yazılmaz (SAP çekirdeği "Kimlik bilgisi kodda").
- `$metadata` ya da test isteği için kimlik bilgili Python/HTTP script'i **yazılmaz**; kullanıcı tarayıcıda açar
  (`%sap-adt-foundation` → `references/foundation-query.md` §5).

---

## Bu dosyada ÇIKARILAN / DEĞİŞTİRİLEN
- Ortak token yardımcısının müşteri paket/sınıf adları, uygulayan müşteri sınıfları, host/port/istemci/kullanıcı,
  destination adları → yer tutucu.
- Simülasyon test değerleri (sipariş türü, satış org., müşteri, malzeme, tesis, birim), ölçülen tutarlar, müşteri
  özel alan adları çıkarıldı.
- `create_by_url` + `authenticate( password )` çalışan-yöntem örneği **alınmadı**: kodda kimlik bilgisi taşıyordu;
  yerine §1 kanonik yol.
- Güncelleme işleminde UI'da yapılan birim eşleme tablosu (müşteriye özgü) alınmadı.
