# Modül referans katmanı — `referans/<modül>/`

> **Ne bu:** SAP fonksiyonel modüllerinin standart **referansı** — kilit tablolar, BAPI/FM, genişletme noktaları, uyarlama
> (SPRO), işlem kodları, iş akışları ve modüle özgü derin reçeteler. Modül paketi (`../<modül>.md`) bir tetikte
> "nereye bak" dediğinde gideceğin yer burasıdır.
> **Ne DEĞİL:** modül paketi. Paket (`../sd.md`) *ne sorulur, neye bakılır, hangi tuzak var* der (tetik haritası + kontrol +
> soru); bu klasör *standart SAP'de ne nerede* der. İkisi ayrı amaçlıdır, birbirinin yerine geçmez.
> **Kaynak:** ekip çekirdeğinin modül referans katmanı (SD) + iki SD reçetesi; aXet'e uyarlandı, proje izleri ayıklandı.
> **Profil:** içerik `s4_private` (2025) üzerinde derlendi; başka profilde (ECC, public cloud) her satır hipotezdir — canlıda teyit et.

## Şablon (her modül altı temel dosya + gerekirse reçete)
`tables.md` · `bapi.md` · `enhancements.md` · `spro.md` · `tcodes.md` · `workflows.md`

Bir konu tek satıra sığmayan ölçülmüş bir yöntem istiyorsa (okuma zinciri, yazma tarifi, uyarlama adımları) aynı klasörde
ayrı **reçete** dosyası açılır ve ilgili temel dosyadan + modül paketinin tetiğinden bağlanır.

## Mevcut modüller
| Modül | Klasör | Reçeteler |
|---|---|---|
| SD (Satış ve Dağıtım) | `sd/` | `sd/lovc-belge-konfigurasyonu.md` · `sd/karakteristik-hizli-giris.md` |

**Başka modül referansı YOKTUR** (MM, FI, CO, PP, QM, PM …). Modül işi başlayınca **artımlı** yazılır; olmayan bir modülün
referansı uydurulmaz (`../README.md` "Paket yoksa" kuralı burada da geçerlidir).

## Kurallar
- İçerik standart SAP **referans** bilgisidir: **otorite değil, hipotezdir.** Bir alan/tablo/BAPI adını koda ya da spec'e
  yazmadan önce o sistemde varlığını ve released durumunu canlıda teyit et (`%sap-adt-foundation`: `adt_get`,
  `adt_sql_query`). Alan adları sürüme ve sisteme bağlıdır; S/4'te bazı tablolar gömülüdür.
- ⛔ Kesin yasak A: buradaki standart objelere dokunulmaz (yalnız okuma kaynağı + alan adı referansı).
- ⛔ Kesin yasak B: standart tabloya doğrudan `INSERT/UPDATE/DELETE/MODIFY` yok. Yazma yolu sırası tek yerde yaşar:
  `%sap-dev` → `references/write-api-selection.md` (released API → BAPI → RFC FM → BDC → kullanıcıdan manuel).
- Standart nesne adları (tablo, CDS, BAPI, FM, işlem kodu) aynen yazılır; müşteri Z objesi, kişi, firma, sistem adı yazılmaz
  (`ZSD_…` gibi nötr yer tutucu).
- Her tuzak satırı ölçülmüş olmalı ve kanıt düzeyini taşımalı; "olabilir" satırı eklenmez.
