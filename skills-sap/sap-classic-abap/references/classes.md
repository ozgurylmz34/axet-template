# ABAP sınıfı (source-based) — yaratma, push, kaydetme taraması tuzakları

> Kaynak: ekip ADT playbook'unun sınıf bölümü + iki hafıza dersi (yetim yorum, `TYPE c LENGTH n`).
> ADT protokolü (kabuk → push → aktivasyon, ETag/kilit akışı, 412/423) burada **tekrarlanmaz**:
> `%sap-adt-foundation` → `references/foundation-ops.md` §3.1, §4.1, §4.6 ve `references/known-errors-adt.md`
> K-01, K-03, K-10, K-13, K-20. Sınıf adı deseni: `%sap-dev` → `references/naming.md` §4.5.
> **Okuma kuralı:** "ÇALIŞAN YÖNTEM" ve "DENENEN — BAŞARISIZ" satırları ölçülmüş deneyimdir.

## 1. Yeni sınıf — CLI sırası (özet)

1. Ad (`ZCL_<GÖVDE>_<AD>`), açıklama (`master_language`, spesifikasyondan) ve transport **kullanıcıdan**.
2. `adt_get {"name":"<SINIF>","object_type":"class","include_source":false}` → `exists:false` bekle.
3. `adt_post_shell` (`object_type:"class"`) → `ok:false` ise retry etmeden `exists_after`'a bak (K-16).
4. `adt_get` (kaynaklı) → pull kaydı oluşur; kabuğun kaynağını al.
5. Tam kaynağı `adt_push_source` ile gönder (`--args-file`). Sınıf/arayüzde aktivasyon öncesi sözdizimi
   kontrolü koşar; `syntax_precheck:"failed"` → düzelt, tekrar gönder.
6. `adt_activate` → `adt_inactive_objects` + aktif kaynak kıyası (K-10). Yeni objede `masterLanguage` metadata'dan okunur.

- Önceki araç setinde yaratma sonrası SAP'nin otomatik kilit koyup handle vermediği ve SM12 temizliği
  gerektiği görüldü; bugünkü CLI'de bunun tekrarlanıp tekrarlanmadığı **DOĞRULANMADI**. `409`/`EU 510`
  görürsen retry etme; kilit adımları `known-errors-adt.md` K-05, K-07, K-09 (kilidi **kullanıcı** siler).

## 2. `ResourceScanDuringSaveFailure` (400, satır numarası yok) — kaydetme taraması

SAP kaydetmeden önce kaynağı tarar; bazı tip kullanımlarını reddeder ve **hangi satır olduğunu söylemez**.

**Ölçülmüş suçlular (metot imzası — IMPORTING/EXPORTING/RETURNING):**

| Kullanım | Sonuç | Yerine |
|---|---|---|
| Parametrede `TYPE c LENGTH n` (ör. `LENGTH 100`) | 400 | `TYPE string` ya da data element. Aynı `TYPE c LENGTH 220` **yapı/TYPES bileşeninde sorunsuz** — yalnız metot imzasında kırar |
| `RETURNING VALUE(...) TYPE netwr` (CURR tipli data element) | 400 | CURR olmayan parasal data element (ör. `wrbtr`) — `CONV`/`COND` içinde de aynı |
| Özel `ZZ1_*` data element'i parametre tipi ya da `RANGE OF` hedefi olarak | 400 (bir projede ölçüldü) | Aynı uzunlukta yerleşik tip; range parametresi için `%sap-dev` → `references/coding-patterns.md` §1 (table type yolu) |
| `TYPE f`, `TYPE p` gibi yerleşik tip parametrede | kaynak "data element ver" diyor | adlandırılmış data element |

**Niteleyici:** tablo tek bir projede ve belirli sistemde ölçüldü; "hangi DTEL taramayı geçer" genel kuralı
kanıtlanmadı. Yeni bir tipte 400 alırsan aşağıdaki bisect ile ölç, tabloya güvenip tahmin yürütme.

**ÇALIŞAN YÖNTEM — baseline + tek tek ekleme (bisect):**
1. `adt_get` ile aktif kaynağı çek, yerel kopyayı **birebir** ona eşitle, push et → temiz taban doğrulanır.
2. Değişiklikleri **tek tek** ekle, her birinde push → kıran değişiklik bulunur.
3. Her adımda `adt_get` ile persist'i kıyasla ("uploaded" mesajı yeterli değil; kaynak persist olmamış olabilir).
4. Tüm metotlar bisect'te düşüyorsa sorun IMPLEMENTATION'da değil DEFINITION'dadır → DEFINITION'ı böl.

**DENENEN — BAŞARISIZ:** hatayı kullanılan bir özelliğe (ör. metin kaydetme çağrısı) yıkıp tahminle
değiştir-push etmek — saatler gitti, suçlu parametre tipiydi.

## 3. `OO_SOURCE_BASED 012` "unknown comments which can't be stored" (400) — yetim yorum

Mesaj **literal doğrudur**: bir kod öğesine bağlanamayan yorum saklanamaz. Satır numarası yoktur.

| Yorumun konumu | Sonuç (ölçüldü) |
|---|---|
| `CLASS … DEFINITION` bölümü (`METHODS`↔`METHODS` arası dahil; 73 satırlık bant denendi) | serbest — 200 |
| Metot gövdesi içi (`METHOD x.` satırının altı, `TRY.` öncesi dahil) | serbest — 200 |
| `CLASS … IMPLEMENTATION.` ↔ ilk `METHOD` arası | **400** |
| `ENDMETHOD.` ↔ sonraki `METHOD` arası | **400** |
| `ENDCLASS.` sonrası | yetim (hafıza dersinde ölçülmüş konum) |

- **En sık sebep:** metot/alan silinip üstündeki yorum (ABAP Doc dahil) bırakılmış.
- **Çare:** yorumu SİL ya da `METHOD x.` satırının **altına, gövdeye** taşı.
- ⛔ **DENENEN — BAŞARISIZ:** "yorumu sonraki öğeye bitişikle" (boş satırı silmek) → sonuç değişmez; belirleyici **konum**.
- ⛔ **Confound listesi (12+ tur patinaj):** `"!` ABAP Doc, emoji/ok karakterleri, Türkçe `İ/ı`, kaynak boyutu,
  `TYPES FOR CREATE`… hepsi "düzeldi" sanıldı çünkü minimal testler yetim yorum içermiyordu.
- **Teşhis yöntemi (satır vermeyen her 400 için):** ① kaynağın **yorumsuz** sürümünü push et → 200 ise suçlu
  yorumlardadır ② yorum bloklarını **tek tek** geri koy → 400 veren bloğun konumuna bak. Hata metnini
  kırpmadan tam oku.
- Yerel statik kontroller (lint, gömülü inceleme) bu tuzağı **yakalamadı** (ölçüldü): hata yalnız canlı PUT'ta çıkar.
- Garanti yedek (hafıza dersi): SAP GUI'de SE24 (form tabanlı editör) ile aynı içeriği kullanıcıya denetmek —
  geçerse kod sağlam, sorun kaynak-tabanlı kaydetmededir. Ekranı açtırırken "aç → yap → KAPAT" de (K-07).

## 4. Aynı sınıfta satır içi tip çakışmaları (aktivasyon hatası)

**`%_##OSQLC_1` / `%_##OSQLC_2`:** `"LS" was already declared with the type "%_##OSQLC_1" …`
- Sebep: farklı metotlarda aynı adla `SELECT … INTO TABLE @DATA(lt_raw)`; SAP iç tip adlarını sınıf kapsamında çakıştırır.
- Çare: her satır içi `@DATA(...)` değişkenine sınıf içinde benzersiz ad (`lt_customer_raw`, `lt_delivery_raw`).

**`FOR` döngü değişkeni:** aynı metotta `VALUE #( FOR ls IN lt_a … )` ve `VALUE #( FOR ls IN lt_b … )`
farklı tiplerle → çakışır. Her döngüde farklı değişken (`la`, `lb`, …).

**CDS tutar alanı toplamı:** `The maximum possible number of places … 34 places with 2 decimal places …`
- Sebep: released CDS'teki tutar CURR(34,2); `SUM(...)` sonucu `wrbtr` (13,2) ya da `p LENGTH 16 DECIMALS 2`'ye sığmaz.
- Çare: `SUM` yerine ham satırları çek, ABAP'ta topla (`%sap-dev` → `references/coding-patterns.md` §2 Yol B).

## 5. Test include'u (`ccau` / `testclasses`) ilk kez ekleniyorsa — yaratma ≠ içerik

Yalnız sınıfta test include'u **henüz yokken** geçerlidir; var olanı güncellemek sıradan yazmadır.

**ÇALIŞAN YÖNTEM (protokol):** ① `POST …/oo/classes/<c>/includes/testclasses` → 201 (include'u yaratır)
② `PUT` aynı uca → 200 (içeriği yazar).
- ⚠ POST gövdeyi **yok sayar**: 11.639 bayt gönderildi, SAP'nin 56 baytlık boş iskeleti yazıldı. 201'de durursan include boş kalır.

**DENENEN — BAŞARISIZ:**

| Deneme | Sonuç |
|---|---|
| Include yokken `PUT …/includes/testclasses` | 500 — `ED 170` "… does not have any inactive version" |
| Aynı PUT `?version=inactive` ile | 500 |
| `POST …/includes` + `classincludes` XML gövdesi | 500 "could not be created" |

**Sahte yeşil:** include boş kalırsa `adt_unit_run` `method_count:0` döner, HTTP 200, hatasız. Kabul ölçütüne
"`method_count` = beklenen test sayısı" yaz; `0` = FAIL. Aktivasyondan sonra `adt_get` ile include listesinde
`testclasses` var mı ve içerik bayt olarak yereldeki ile aynı mı bak.

**aXet'te araç durumu (2026-09-13; çevrimdışı test edildi, canlı DOĞRULANMADI):** `adt_push_source` `object_type=ccau`
(ve `ccimp`) sınıf alt-include'unu yazar — `name` = **ana sınıf**; include yoksa önce iskelet (①) sonra PUT (②), bayt readback,
ardından ana sınıf aktivasyonu; transport zorunlu (`%sap-adt-foundation` → `tool-catalog.md` → `adt_push_source`).
1. `cli adt_get '{"name":"ZCL_X","object_type":"ccau"}'` → include 404 ise `exists:false` + `include_absent_proven:true`, pull kaydı "yok" yazılır.
2. `cli adt_push_source '{"name":"ZCL_X","object_type":"ccau","source":"<test include>","transport":"<TRANSPORT>"}' --sap-write ...`
3. `adt_unit_run` → `method_count` = beklenen; `adt_get ccau` ile içerik yereldekiyle bayt olarak aynı mı.
`ccdef`/`ccmac` yazılamaz (`unsupported_type`). Araç canlıda düşerse ham REST ile yazma; kullanıcı test include'unu ADT/SE24'ten
ekler, sonra CLI ile okunur.

## 6. `adt_classrun` notları
- `adt_classrun` **yazma sınıfıdır** (kod çalıştırır). "does not implement if_oo_adt_classrun~main" mesajı doğrudur:
  sınıf aktive edilmemiş ya da oturum bayat → `known-errors-adt.md` K-13. ⛔ "Taze sınıf adıyla yeniden yarat"
  reçetesi iki kez denendi, çözmedi, çöp obje bıraktı.
- Kontrol grubu seçerken yan etkiye bak: bir sistemde aday 13 classrun sınıfının hepsi yazma yapıyordu (metin
  üretimi, `DELETE`+`COMMIT`). Yan etkisiz aday yoksa `$TMP`'de `out->write( 'OK' )` kadar basit bir sınıf
  (yazma sınıfı → onay) — G-1.
- Diyalog bağlamı isteyen FM'ler (`RPY_DYNPRO_INSERT`, `RS_CUA_INTERNAL_WRITE`) classrun ile koşmaz (K-14) →
  `dynpro-gui-status.md` §1.

## 7. Sunucu tarafı biçimlendirme (Pretty Printer)
Kaynak araç setindeki script SAP'nin biçimlendirme ucuna metni gönderip **biçimlenmiş metni döndürüyordu; sistemde
kaydetmiyordu** (kaydetmek ayrı bir push adımıdır; kaynak playbook'taki "kaynağı değiştirir" notu bununla çelişir).
aXet CLI'de biçimlendirme aracı yok; zorunlu adım değildir. Gerekiyorsa kullanıcı ADT/SE80'de uygular, ardından kaynak
`adt_get` ile yeniden çekilir (yerel kopya bayatlar).
