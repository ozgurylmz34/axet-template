# BAdI enhancement spot (ENHS/XSB) + BAdI tanımı

> **Araçlar:** `adt_badi_spot_read` (okuma) · `adt_badi_spot_write` (yazma, transport zorunlu). Profil: yalnız `s4_private`.
> Lib: `sap_adt_lib` `get/create/write/activate_enhancement_spot` + `enhs_*` yardımcıları. Katalog: `tool-catalog.md`.
> **Ölçüm dayanağı:** kaynak çekirdek iki sürümde, `$TMP`'de sentetik spot'la ölçtü — **[758]** (SAP_BASIS 758) ·
> **[816]** (SAP_BASIS 816) · **[758+816]**; SAP kaynak okuması **[kaynak]**. İkisinde de ölçülmeyen **ÖLÇÜLMEDİ** yazılıdır.
> aXet araçları sahte sunucuyla test edildi (`tests/test_badi_spot.py`, fikstürler kaynak çekirdeğin canlı belgeleri);
> aXet'ten canlı koşu **ÖLÇÜLMEDİ**.

## 1. Akış

1. `adt_badi_spot_read(name)` → canlı model + pull kaydı. `standard:true` ya da `writable:false` ise DUR.
2. Değişikliği kullanıcıya göster (hangi tanım eklenecek / güncellenecek / kaldırılacak).
3. İsteğe bağlı `adt_badi_spot_write(..., dry_run=true)` → yazılacak belge döner, SAP'ye yazılmaz.
4. `adt_badi_spot_write(name, transport, definitions=[…], remove_badis=[…])`.
   Spot yoksa `package` + `description` ile boş kabuk yaratılır, sonra tanımlar yazılır.

Tanım biçimi (verilmeyen alan canlıdaki değeriyle kalır; listede olmayan tanım KORUNUR):

```json
{"badi": "ZSD001_BADI_ORNEK", "interface": "ZIF_SD001_BADI_ORNEK", "shorttext": "Örnek BAdI",
 "coklu_kullanim": "hayir", "fallback": "ZCL_SD001_BADI_ORNEK_FB", "ornek": ["ZCL_SD001_BADI_ORNEK_EX"],
 "filtreler": [{"ad": "ULKE", "tip": "C", "kisa": "Ülke", "dtel": "LAND"}]}
```

⚠ **`coklu_kullanim: evet` ⇒ `enhs:singleUse="false"`** (ters eşleme; `singleUse="true"` = tek kullanım **[758]**).
Var olan spot'ta `package` / `description` okunandan farklıysa araç reddeder (açıklama değişikliği ÖLÇÜLMEDİ).

## 2. Ölçülen uçlar ve sıra

| Adım | İstek | Ölçülen sonuç |
|---|---|---|
| Yaratma | `POST /sap/bc/adt/enhancements/enhsxsb?corrNr=<TR>` gövde `<enhs:badiDefinitions/>` | **[758+816]** 201 + `Location`. Araç boş kabuk + PUT kullanır |
| Kilit | nesne URL'i `?_action=LOCK&accessMode=MODIFY&corrNr=` | **[758+816]** 200 (`/locks` ve `/core/objectlock` 404) |
| Yazma | `PUT …/enhsxsb/<ad>?corrNr=&lockHandle=` TAM belge | **[758+816]** 200; **[758]** kilitsiz PUT → 400 |
| Kilit bırak | `POST …?_action=UNLOCK&lockHandle=` | 200 — PUT hatasında da bırakılır |
| Aktivasyon | `activate_object(..., object_type='ENHS/XSB')` | **[758]** 9/9 `success=true`; hüküm `success`'i okur, `activationExecuted`'ı DEĞİL |
| Spot adı | ad doğrulama ucu | **[758]** en çok 30 karakter (BAdI adı sınırı 30: şemadan, canlıda ÖLÇÜLMEDİ) |

İçerik tipi: `application/vnd.sap.adt.enh.enhs.v2+xml`. İlk yazmada `403 CSRF` + token yenileme + tekrar normaldir.

**Aktivasyon sırası:** ① BAdI arabirimi + fallback/örnek sınıflar ÖNCE aktif ② sonra spot ③ BAdI'ye atıf yapan sınıflar
(implementasyon, `GET BADI` çağıranı) EN SON. ①→② temiz aktive oldu **[758+816]**; ters sıra ÖLÇÜLMEDİ.

### 2a. Genel araçlarda ENHS (`object_type="enhs"`)

`object_types` girdisi **işlem-izinlidir**: `get_object_url(ad, "enhs", islem=…)` yalnız `silme` · `kilit` · `metadata` için URL üretir;
başka işlem ya da işlemsiz çağrı `ValueError` (fail-closed). Gerekçe: genel aktivasyon yolunun worklist sondası `ENHS/XSB` ile sorar,
worklist `ENHS/XS` listeler (§3.4) ⇒ inaktif spot "doğrulandı" görünürdü.

| Araç | ENHS'te |
|---|---|
| `adt_delete` | kilit → DELETE → UNLOCK → yokluk doğrulaması (kaynak çekirdekte **[758+816]** ölçüldü) |
| `adt_lock_check` | spot'u tanır; kilit ucu bu sistemlerde her tipte 404 ⇒ `locked:null` (ÇÖZÜLEMEDİ) |
| `adt_atc_check` | istek GÖNDERİLMEZ: `atc_kapsam_disi` — ENHS'te "0 bulgu" yokluktan ayırt edilemiyor **[758]** |
| `adt_get` | yalnız `include_source=false` (metadata/varlık; `Accept: */*`); içerik için `adt_badi_spot_read` |
| `adt_activate` · `adt_push_source` · `adt_syntax_check` · `adt_where_used` | kapalı (işlem izin kümesi dışında) |

## 3. ⛔ Tuzaklar

1. **PUT TAM BELGEDİR.** **[758]** iki filtreli tanıma tek filtreli belge gönderildi → ikinci filtre SİLİNDİ. **[kaynak]** sunucu önce
   tüm tanımları silip gövdedekileri ekler ⇒ gövdede olmayan BAdI tanımı da silinir. Araç belgeyi **daima taze GET'ten** kurar; kaldırma
   yalnız `remove_badis`. Belge aracın modellemediği alan taşıyorsa (bilinmeyen eleman/öznitelik, Dictionary dışı filtre kontrolü, dolu
   `documentationId`) araç **yazmaz** (`unmodelled_fields`). Lib bu denetimi **kilit altında yeniden** koşar: okunan tabandan farklıysa
   PUT gitmez (`taban_degisti`), kilit bırakılır → yeniden oku.
2. **Gövde sırası.** **[kaynak]** gövdenin İLK tanımı canlıda yoksa yeni tanım son eski tanımın bazı alanlarını devralabilir. Araç gövdede
   önce canlıda var olan tanımları (canlı sırasıyla), yenileri SONA koyar. Canlıda tanım varken gövdedekilerin hiçbiri canlıda yoksa araç
   **reddeder** (`sira_tuzagi`) → iki adımda yap: önce yenileri ekle, sonra eskileri `remove_badis` ile kaldır.
3. **Aktiflik = aktivasyon `success` + worklist + sürümsüz GET.** `?version=active` AKTİFLİK KANITI DEĞİL: aktivasyondan önce de
   `adtcore:version="active"` + inaktif içerik döner **[758+816]**. Okuma aracındaki `spot.version` da kanıt değildir.
4. **Worklist spot'u başka adla listeler** **[758+816]**: `ENHS/XS` + `…/enhsxs/<ad>`. URI ya da tam tiple eşleyen sonda inaktif spot'u
   GÖREMEZ — `activate_enhancement_spot` kendi sondasını ad + `ENHS` ile koşar.
5. **Sunucu eklentileri** (`usages`, `customLogicRegistered`, boş `documentationId`, `atom:link`): yazmada gönderilmez, readback kıyasına
   girmez (`server_extras`).

## 4. Koruma (Yasak A — yeni kural değil)

- Spot adı ve her BAdI adı (`definitions[].badi`, `remove_badis`) müşteri adı olmalı: Z/Y ya da projede `customer_namespaces` ile
  bildirilmiş `/NS/` (tek kaynak `lib/utils/ad_politikasi.py`). Yazma kapısı (`gate.check_names` + `arg_adlari`) ve araç ikisi de
  denetler; standart ad → `ADR_0005_A`, SAP'ye istek gitmez.
- İkinci katman: araç ve lib yazmadan önce GET eder — `adtcore:masterSystem="SAP"` olan belgeye kilit bile alınmaz.

## 5. Sınırlar / ÖLÇÜLMEDİ

- Birden çok BAdI'li gövde canlıda ÖLÇÜLMEDİ (iki sürümde de tek tanım); sıra tuzağı canlıda tetiklenmedi.
- Fallback / örnek sınıf kaldırma, son tanımı kaldırma, filtre tipini değiştirme, `contextMode` S/Y, ProgramCheck / DOMA kontrollü filtre,
  çeviri, transport'lu pakette kabuk POST'u **ÖLÇÜLMEDİ** (araç modellemediği biçime yazmaz).
- BAdI implementasyonu (ENHO), `CL_ENH_*` API'leri bu araçların kapsamı dışında.
