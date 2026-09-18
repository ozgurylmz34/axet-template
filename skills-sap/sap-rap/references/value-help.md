# Value-help CDS yerleşimi, muhatap alanları ve released CDS tercihi

> Kaynak: ekip ortak value-help CDS politikası, RAP standardı §9B/§9X, RAP backend tecrübe bankası (VH maddeleri) ve ekip hafıza
> dersleri (ortak VH'yi sor, released CDS proaktif); aXet'e uyarlandı. Ortak paket adı yer tutucudur: `<ORTAK_PKG>` (klasik
> projede ortak `_CLC` paketi olabilir; gerçek adı proje `AGENTS.md`'si ya da kullanıcı verir).

## 1. Ortak mı, paket-yerel mi — KULLANICIYA SOR

Generic value-help CDS'lerini her pakette kopyalamak çoğaltma, tutarsız metin/davranış ve bakım yükü üretir.

| Ortak `<ORTAK_PKG>_I_*` | İlgili pakette yerel |
|---|---|
| Standart master/org verisi (müşteri, satıcı, satış org., şirket kodu …) | Uygulamanın **Z tablosu** üzerinde VH |
| Uygulama mantığı / özel filtre yok | Uygulamaya özel filtre ya da iş kuralı var |
| En az iki geliştirmede makul | Tek programa özgü |

**Süreç (her geliştirmede):**
1. Tüm VH adaylarını listele.
2. Her biri için "ortak / yerel" önerini gerekçesiyle çıkar ve **kullanıcıya sor**; yerleşimi kullanıcı onaylar.
3. Ortakta zaten varsa (`cli adt_search_objects '{"query":"<ORTAK_PKG>_I_*VH*","object_type":"DDLS"}'`) **yeniden yaratma**:
   tüketen servis SRVD'de `expose` + interface/projection'da `association to <ORTAK_PKG>_I_<X>` ile kullanır.
4. AI paket ya da transport yaratmaz; ortak paketin kendisi yoksa DUR.

## 2. Muhatap alanı — generic Business Partner VH / ad çözümü YASAK

Bir muhatap alanının değeri **ya müşteri (KUNNR) ya satıcı (LIFNR)**'dır. Generic BusinessPartner (`BU_PARTNER`) arama yardımı ya da
ad çözümü (join/association) yaratılmaz: `BU_PARTNER ≠ KUNNR/LIFNR` (CVI) → generic join **sessizce boş ya da yanlış ad** döndürür
(ölçüldü; tarihsel generic ad view'ı silindi).

Her muhatap alanını sınıflandır:
- **Müşteri** → seçici: satış alanı bazlı müşteri VH (key `Kunnr`) ya da muhatap fonksiyonuna özgü VH; ad çözümü released
  **`I_Customer`** (`Customer` / `CustomerName`).
- **Satıcı** → seçici: `I_Supplier` tabanlı satıcı VH (key `Lifnr`); ad çözümü released **`I_Supplier`** (`Supplier` / `SupplierName`).

## 3. Released CDS tercihi — yazmadan ÖNCE

- Standart tablo okuyacaksan kod yazmaya başlamadan released successor'ı kontrol et: `MARA` → `I_Product`, `VBAP` →
  released satış belgesi kalem CDS'i, `LIPS` → released teslimat kalem CDS'i, `MARM` → `I_ProductUnitsOfMeasure` (adları
  `adt_search_objects` ile ara, `adt_get` ile oku; tahmin etme). Liste: `%sap-dev` → `coding-patterns.md` §7.
- Tüm tipler (sınıf/FM) için otorite ATC "Usage of APIs" kontrolüdür.
- Yazma kapısının CDS incelemesi released successor için **WARNING** verebilir. WARNING geçilebilir ama **sessiz geçilmez**: ya
  released'a çevir ya da bilinçli tablo kullanımının gerekçesini kullanıcıya bildir.
- **Kullanıcı "MARM kullan" dese bile** released successor işi görüyorsa onu kullan: kullanıcı veriyi kastediyor, released
  eşdeğeri yasaklamıyor. Released gerçekten yetmiyorsa (eksik alan) tabloya düş ve gerekçeyi bildir.
- Tuzak: released birim çevrim alanları (`QuantityNumerator` / `QuantityDenominator`) `@Semantics.quantity` taşır →
  aritmetik/`case`'te `Elements with required UNIT-reference are not supported` → `cast( … as abap.dec(n,m) )`.
- Okumak kesin yasak B'yi ihlal etmez; released CDS tercihi clean core seviye A içindir.
- DCL'li released CDS, kısıtlı kullanıcıda hata vermeden 0 satır döndürebilir → varlık guard'ında dikkat (`eml.md` §3).

## 4. VH tuzakları

- VH view aktivasyonu "HTTP 400 pre-audit" verdi → **ortamsal/geçici** olabilir (ölçülen vakada bir sonraki temiz denemede düz
  aktive oldu). Hemen silme: hata gövdesini oku, **tek** temiz deneme yap.
- Salt-okunur senaryoda "search help not inherited" uyarıları zararsız.
- Yeni VH entity'si servise eklenince: SRVD `expose` + aktivasyon + yeniden publish (`service-publish.md` §5).
