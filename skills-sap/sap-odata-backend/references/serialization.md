# Serileştirme — decimal, tarih, anahtar dolgusu, mesaj başlığı

> Kaynak: ekip hafızası (decimal → OData `WRITE ... TO` tuzağı; iki koleksiyon birleştirmede anahtar dolgusu),
> OData servisleri playbook'u (`Edm.DateTime` biçimi, `sap-message` başlığı, BAPIRET2), CDS playbook'u (conversion
> exit), backend hata kontrol listesi.

---

## 1. Decimal / miktar / tutar → JSON veya OData gövdesi

- **Tuzak:** paketli (packed) bir değeri dış bir API gövdesine string olarak yazarken `WRITE lv_num TO lv_char
  DECIMALS n` **kullanma**. `WRITE … TO` kullanıcının sayı biçimini uygular ve **binlik ayıracı ekler**:
  - `< 1000` → gruplama yok, tesadüfen geçerli (`999` → `"999.000"`)
  - `≥ 1000` → binlik ayıraç ondalık noktasıyla çakışır: `1111` → `"1.111.000"` → geçersiz `Edm.Decimal` →
    `HTTP 400: Property … has invalid value '1.111.000'` (ölçüldü: 4 haneli miktarda simülasyon çağrısı)
- **DENENEN — YARIM ÇÖZÜM:** `REPLACE ',' WITH '.'` yalnız ondalık virgülünü düzeltir, binlik noktayı bırakır;
  `≥ 1000`'de yine kırılır.
- **ÇALIŞAN YÖNTEM:** packed → karakter **doğrudan atama**, sonra `CONDENSE`:
  ```abap
  DATA lv_str TYPE string.
  lv_str = lv_quantity.          " kullanıcı ayarından bağımsız: '.' ondalık, binlik ayıraç yok
  CONDENSE lv_str NO-GAPS.
  ```
  - Negatif değerde işaret sona gelir (`'12.500-'`). `Edm.Decimal` öne işaret bekler → negatif olabilecek alanda
    (tutar, fark) işareti başa taşı.
  - Aynı kural tutar (amount) alanları için de geçerli.
- **Hatayı yakalamak:** hata yalnız `≥ 1000` değerle çıkar → test verisinde en az bir 4+ haneli değer kullan.
- CLI'nin yazma öncesi incelemesi sınıf push'unda bu tuzağı **WARNING** olarak işaretler (`check_decimal_write_to`);
  bloklamaz ve program/FM kaynağında çalışmaz. JSON/URL/gövde kuran kodda `WRITE … TO` görürsen uyarıyı beklemeden düzelt.

## 2. `Edm.DateTime` alanına tarih gönderme (dış OData API'si)
- Ölçülen alan: `Edm.DateTime` (`Precision=0`, `sap:display-format="Date"`).
- `"YYYY-MM-DD"` → **HTTP 400** `Conversion error for property '<Alan>'`.
- **ÇALIŞAN BİÇİM (JSON):** `"/Date(<ms>)/"`, ms = (tarih − 1970-01-01) gün × 86 400 000.
  ```abap
  DATA lv_days  TYPE i.
  DATA lv_epoch TYPE d VALUE '19700101'.
  DATA lv_ms    TYPE decfloat34.
  DATA lv_date_str TYPE string.
  lv_days = lv_date - lv_epoch.
  lv_ms   = lv_days * 86400000.
  lv_date_str = |/Date({ lv_ms })/|.
  REPLACE ALL OCCURRENCES OF '.' IN lv_date_str WITH ''.   " decfloat ondalık izi kalırsa temizle
  ```
  Kaynaktaki `&&` birleştirmesi `decfloat34`'ü dizgeye örtük çevirir; biçimi (ör. `1.7E+12`) üretmediğini ilk
  kullanımda gözle doğrula — **DOĞRULANMADI**. Tamsayı tipi (`int8`) kullanmak alternatif adaydır.
- İstemciden gelen yazma isteğinde boş tarih `""` → `Edm.DateTime` 400; boş tarih `null` gönderilir (UI tarafı kuralı;
  backend hata mesajı bu belirtiyi verir).

## 3. Anahtar sıfır dolgusu (POSNR, VBELN, MATNR …)
- **Belirti:** iki koleksiyonu anahtar dizgesiyle birleştiren kod (istemci ya da ABAP) hiçbir satırı eşleştirmiyor;
  hata yok, alanlar sessizce boş/null.
- **Kök sebep (ölçüldü):** aynı sistemden gelen iki kaynak farklı biçim döndürdü:
  - OData entity okuması conversion exit uyguladı → kalem no `"10"` (sıfırsız)
  - ham CDS/RAP façade okuması exit uygulamadı → kalem no `"000010"` (6 hane dolgulu)
- **Backend kuralı:**
  1. Aynı istemcinin birlikte kullandığı entity/FI sonuçlarında anahtar alanlar **aynı biçimde** dönsün; biçim
     farkı kaçınılmazsa `$metadata`/dokümanda belirt.
  2. ABAP'ta dışarıdan gelen anahtarla okuma/birleştirme öncesi iki tarafı aynı biçime getir
     (`ALPHA = IN` / `CONVERSION_EXIT_ALPHA_INPUT` ya da sayısal normalize).
  3. Standart API'ye müşteri numarası gibi dolgulu alan gönderirken dolgulu (ör. 10 haneli) gönder; dolgusuz değer
     ölçülen vakada sessizce boş partner üretti.
- İstemci tarafı normalize (ör. `parseInt`) UI5 skill'inin konusudur. "Backend doğru, UI boş" raporunda tahmin etme:
  iki kaynağın gerçek anahtar değerlerini yan yana oku, karşılaştır.

## 4. Conversion exit'li alan
OData V2 / SADL property'de conversion exit reddedilir → CDS'te düz tipe `cast`: `references/segw-service.md` §5.

## 5. Mesajlar — BAPIRET2 ve `sap-message` başlığı
- Hata/uyarı taşımak için özel Z mesaj yapısı değil standart `BAPIRET2` / `BAPIRET2_T`:
  ```abap
  DATA lt_msgs TYPE bapiret2_t.
  APPEND VALUE #( type = 'E' id = 'ZSD001_MSG' number = '001' message = '…' ) TO lt_msgs.
  ```
- Standart SAP OData API'leri ek uyarı/bilgi mesajlarını gövdede değil **`sap-message` yanıt başlığında** döndürür.
  POST/PATCH sonrası başlık okunmazsa bu mesajlar kaybolur:
  ```abap
  DATA(lv_sap_msg) = VALUE string( lt_response_header[ name = 'sap-message' ]-value OPTIONAL ).
  " JSON içindeki severity / message / code / target alanlarını ayrıştır → BAPIRET2_T'ye ekle
  ```
- Kendi DPC_EXT'inden istemciye birden fazla mesaj dönmek: message container (`references/dpc-crud.md` §6).

---

## Bu dosyada ÇIKARILAN / DEĞİŞTİRİLEN
- Müşteri paket/sınıf adları ve iş süreci ayrıntısı (belirli ekran/uygulama adları, test belge numaraları) çıkarıldı.
- Hafıza dersindeki playwright ile istemci modelini okuma yöntemi alınmadı (UI/test aracı; aXet'te bu araç yok).
