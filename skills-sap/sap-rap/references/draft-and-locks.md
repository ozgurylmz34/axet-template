# Belge kilidi — ETag, draft ya da uygulama-seviyesi kilit

> Kaynak: ekip "VA02 tarzı belge kilidi" nasıl-yapılır dokümanı, uygulama-seviyesi kilit mimari kararı ve RAP standardının kilit
> satırları; aXet'e uyarlandı. Ölçümler `s4_private`'ta. Ortak paket adları yer tutucudur (`<ORTAK_PKG>`); gerçek adlar proje
> `AGENTS.md`'sinden ya da kullanıcıdan gelir.

## 1. Karar: hangi katman

| Durum | Yaklaşım |
|---|---|
| Yalnız veri bütünlüğü yeter | RAP varsayılanı **ETag** (`etag master`): açılışta uyarı yok, çakışma save'de 412. Ek kod gerekmez. |
| "X düzenliyor" davranışı + draft uygun (Fiori Elements / OData V4, "kaldığın yerden devam" değerli) | **Draft** (`with draft` + `lock master total etag`) — framework yönetir. Greenfield + Fiori Elements için tercih edilen yol. |
| "X düzenliyor" + freestyle / OData V2 / draft'sız | **Uygulama-seviyesi kilit** (bu dosya §3–§5) + ETag birlikte |
| Belge gerçek SAP belgesi (klasik işlem kodu da açıyor) | Uygulama-seviyesi kilit + **`ENQUEUE_READ`** (§5) |

Neden stateless OData'da klasik enqueue yetmez: kilit her istek sonunda düşer; açma → kaydetme arasında tutulamaz (anti-pattern).
Draft'ın bedeli freestyle + V2 bağlamında büyüktür (Edit/Activate/Discard yaşam döngüsü, `IsActiveEntity` anahtarı, ön yüzde
yeniden yazım). Seçim ve gerekçe kullanıcıyla yazılır.

## 2. ETag ve kilit — managed BO'da zorunlu

- Yazma operasyonlu managed root: `lock master` + `etag master <LastChangedAt>`; alan root view'da
  `@Semantics.systemDateTime.lastChangedAt: true`. Child: `lock dependent by _Order` + `etag dependent`.
- Eksikse eşzamanlı güncelleme korunmaz; yazma kapısının BDEF incelemesi BLOCKER verebilir.
- Elle enqueue kurulmaz; framework optimistic kilidi kullanılır.

## 3. Draft

- BDEF'te `with draft`, root'ta `lock master total etag <alan>`, draft tablosu `ZSD001_A_ORDER_D`, `draft determine action
  Prepare` ve draft action'ları.
- Kaynak deneyim draft'sız ilerledi; draft reçetesi (sözdizimi, draft tablosu üretimi, aktivasyon sırası) **ölçülmedi** →
  **DOĞRULANMADI**. Draft seçildiyse önce sistemdeki çalışan bir draft'lı BO'yu oku, `%remember` ile kaydet.
- Teşhis ipucu (kontrol listesinden): draft tutarsızlığında draft tablosu (`_D`) eksik/uyumsuz ya da `Prepare` action'ı eksik.

## 4. Uygulama-seviyesi kilit — mimari

- **Tablo** `<ORTAK_PKG>_T_LOCK`: `mandt` + `lock_object` (CHAR30) + `lock_key` (CHAR10 genel belge no; satış siparişine bağlı
  değil) [key]; `locked_by` (`syuname`), `locked_at` (`timestampl`).
- **Sınıf** `<ORTAK_PKG>_CL_APP_LOCK` (static): `acquire(iv_object, iv_key) → {acquired, locked_by}` (boş / süresi dolmuş /
  aynı kullanıcı → kilitle; başkası → `locked_by`) · `release(iv_object, iv_key)` (kendi kilidi) · `check(iv_object, iv_key) →
  locked_by`. `c_timeout_seconds = 300`. Sınıfta `COMMIT WORK` yok → action'ın LUW'unu RAP commit eder.
- `lock_object` konvansiyonu `<PAKET>_<BELGE>`; `lock_key` = belge no.
- Mekanizma projede **zaten varsa yeniden yaratma**, kullan. Yoksa: yeni DDIC tablo + sınıf = alan/DTEL/anahtar tasarımını
  kullanıcıya göster, açık onay al; adları kullanıcı verir (SAP çekirdeği).
- İki katman: kilit (erken uyarı, best effort — milisaniye yarışında kaçabilir) + ETag (kesin bütünlük; ikinci kaydeden 412).

## 5. Backend reçetesi

**Managed BO — instance action (key = belge anahtarı):**
```
// interface BDEF                          // projection BDEF
action AcquireLock;                         use action AcquireLock;
action ReleaseLock;                         use action ReleaseLock;
```
```abap
METHODS AcquireLock FOR MODIFY IMPORTING keys FOR ACTION Order~AcquireLock.
METHOD AcquireLock.
  LOOP AT keys INTO DATA(k).
    DATA(r) = <ortak_pkg>_cl_app_lock=>acquire( iv_object = 'ZSD001_ORD' iv_key = CONV #( k-OrderId ) ).
    IF r-acquired = abap_false.
      APPEND VALUE #( %tky = k-%tky ) TO failed-order.
      APPEND VALUE #( %tky = k-%tky %msg = new_message_with_text(
        severity = if_abap_behv_message=>severity-error
        text     = |Belge { r-locked_by } tarafından düzenleniyor| ) ) TO reported-order.
    ENDIF.
  ENDLOOP.
ENDMETHOD.
" ReleaseLock → <ortak_pkg>_cl_app_lock=>release( … )
```
Başarı = kilit alındı; hata = kilitli (`%msg`). Mesaj metni `master_language`'de ve spesifikasyondan.

**Unmanaged + gerçek SAP belgesi — static action + parametre entity:**
```
// define abstract entity ZSD001_I_LOCK_P { IvSalesOrder : vbeln_va; }
static action AcquireLock parameter ZSD001_I_LOCK_P;   // result yok (başarı/hata semantiği)
static action ReleaseLock parameter ZSD001_I_LOCK_P;
```
```abap
METHOD AcquireLock.
  LOOP AT keys INTO DATA(k).
    DATA(lv_vbeln) = CONV vbeln_va( k-%param-IvSalesOrder ).
    DATA lt_enq TYPE STANDARD TABLE OF seqg3.
    DATA lv_subrc TYPE sy-subrc.
    CALL FUNCTION 'ENQUEUE_READ'
      EXPORTING gclient = sy-mandt gname = 'VBAK' guname = ' '
      IMPORTING subrc = lv_subrc
      TABLES    enq = lt_enq.
    DELETE lt_enq WHERE garg NS lv_vbeln.          " garg belge no'yu içerir (biçimden bağımsız filtre)
    IF lt_enq IS NOT INITIAL.
      " failed + "Belge { lt_enq[ 1 ]-guname } tarafından düzenleniyor"
    ENDIF.
    " sonra uygulama↔uygulama: <ortak_pkg>_cl_app_lock=>acquire( 'ZSD001_SO', lv_vbeln )
  ENDLOOP.
ENDMETHOD.
```
- `gname` = kilit objesinin tablosu (satış siparişi `VBAK`, teslimat `LIKP` …).
- Kilit okumak (`ENQUEUE_READ`) yasak değildir; enqueue kilidi **silmek** kesin yasak C'dir.
- Sert garanti: save'de BAPI kendi enqueue'sunu alır, çakışmada düşer.

**Klasik işlem kodu → uygulama kilidini görsün:** ilgili user-exit/BAdI içine yalnız **okuyan** `check()` çağrısı eklenir
(kilit tablosuna yazmaz). Bu standart tarafa dokunur → AI yazmaz; öneriyi hazırlar, yetkili kullanıcı ekler (kesin yasak A).

| Yön | Mekanizma |
|---|---|
| klasik ↔ klasik | SAP enqueue |
| uygulama ↔ uygulama | kilit tablosu |
| klasik → uygulama | `ENQUEUE_READ` |
| uygulama → klasik | user-exit `check()` |

Çapraz yönde **aynı kullanıcı istisnası yok** (uygulama otoriter): klasik işlemde ETag yoktur; kilit kaçarsa BAPI bayat okumayı
güncel duruma uygular. Yan fayda: tek kullanıcıyla test edilebilir. Aynı araç içinde (uygulama↔uygulama, klasik↔klasik) aynı
kullanıcı serbesttir.

## 6. Ön yüzün uyması gereken sözleşme (ayrıntı UI skill'inde)

Açarken önce salt-okunur, `AcquireLock` başarılıysa düzenlenebilir; başarısızsa salt-okunur + `locked_by` uyarısı · kaydet ve
geri dönüşte `ReleaseLock` · sayfa kapanışında senkron `ReleaseLock` · heartbeat aralığı kilit zaman aşımından kısa (kaynakta
2 dk / 5 dk) · listeden silmeden önce `AcquireLock`.

| # | Senaryo | Sonuç |
|---|---|---|
| S1 | kullanıcı-1 içeride, kullanıcı-2 giriyor | kullanıcı-2 salt-okunur + uyarı; heartbeat kullanıcı-1'i korur |
| S2 | aynı kullanıcı başka tarayıcıda | izin (ETag/BAPI korur) |
| S3 | kapatıp tekrar giriyor | kapanışta bırakıldı; bırakılmadıysa `sahibi = sen` → girer |
| S4 | kapattı, başkası giriyor | kapanışta anında; çökmede zaman aşımı sonrası |

## 7. Tuzaklar

- `Lock` / `Unlock` rezerve action adları → `AcquireLock` / `ReleaseLock`.
- Parametre abstract entity'si: kabuktan sonra kaynak **ayrıca** yazılır (`layering-and-bdef.md` §5).
- CCIMP kaynağı `includes/implementations` ucundadır, `source/main` değil (CLI: `adt_get`/`adt_push_source` `object_type=ccimp`, `name` = ana sınıf — `behavior-impl.md` §1).
- DDIC tabloyu kaynaklı tek POST ile yaratmak yalnız `mandt` getirdi → tam DDL ayrıca yazılır (`%sap-cds-ddic`).
- Handler'da `COMMIT WORK` yok.
- Profil: `ENQUEUE_READ` ve user-exit yalnız `s4_private`; `s4_public`/`btp_abap`'ta draft tercih edilir, alternatif **DOĞRULANMADI**.
