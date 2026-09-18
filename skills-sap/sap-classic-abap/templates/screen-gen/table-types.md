# Ekran üreteci kiti — tablo tipleri (CLI kabuk + aktivasyon; satır tipi düzeltmesi kullanıcı)

> `ZBC000` nötr ortak paket gövdesidir; kendi ortak paketinin gövdesiyle değiştir (`%sap-dev` → `references/naming.md` §3).
> **CLI yolu (2026-09-13; çevrimdışı test edildi, canlı DOĞRULANMADI):** `adt_post_shell` `object_type=ttyp` + `extra.row_type`
> → `adt_activate` `ttyp` (`%sap-adt-foundation` → `references/tool-catalog.md`). **Hâlâ araç yok:** satır tipini düzeltme
> (`ROWTYPE` boş kalırsa kullanıcı SE11'de düzeltir). Ham REST ile yaratılmaz. Yeni DDIC objesi = ad + kısa metin
> **kullanıcı onayıyla** (kesin yasak D: `master_language`'de, boş değil — boş açıklama `ADR_0005_D` ile reddedilir).

## Neden tablo tipi şart
FM imzasındaki `TABLES it_buttons TYPE …` / `TABLES it_fields TYPE …` satırları **tablo tipi** ister. Yapı adı yazılırsa
normal FM'de tolere edilir, FM **Remote-Enabled** yapılınca `FL 387 Type <X> is not a table type` olur; `STRUCTURE` yazımı ise
ADT upload'unda `FUNC_ADT 015` ile reddedilir (`references/fugr-fm.md` §2.1).

## Yaratılacak iki tip
| Tablo tipi | Satır tipi (önce yaratılmış olmalı) | Kısa açıklama (TR) | Kaynak |
|---|---|---|---|
| `ZBC000_TT_SCREEN_BUTTON` | `ZBC000_S_SCREEN_BUTTON` | `Ekran üreteci: app-toolbar buton listesi` | kaynak ekibin canlı objesindeki açıklama |
| `ZBC000_TT_SCREEN_FIELD` | `ZBC000_S_SCREEN_FIELD` | **kullanıcı belirler** — kaynak objede açıklama BOŞTU. Kardeş objelere paralel bir öneri: `Ekran üreteci: dynpro alan listesi` (öneridir, onaysız kullanılmaz) | — |

Teknik ayarlar (kaynak ekibin canlı objesinden okunan değerler; ikisinde de aynı). CLI `ttyp` kabuk gövdesi bu değerleri sabit
gönderir (erişim standart, anahtar standart/benzersiz değil, başlangıç satırı 0 — araç kaynağının kod okuması, canlı DOĞRULANMADI):
| Ayar | Değer |
|---|---|
| Satır tipi türü | Veri tipi (sözlük yapısı) |
| Erişim | Standart tablo |
| Birincil anahtar | Standart anahtar · benzersiz değil |
| İkincil anahtar | belirtilmedi |
| Başlangıç satır sayısı | 0 |

## CLI adımları (her tip için)
Satır tipi yapıları (`DEPLOY.md` Adım 2) aktif olmadan başlanmaz. Paket (kullanıcının `_CLC` ortak paketi) ve transport kullanıcıdan
(yeni transport açılmaz — kesin yasak C).
```text
sap_adt_cli.py adt_post_shell --sap-write --scope <S> --reason "ekran üreteci tablo tipi" --args-json '{"object_type":"ttyp","name":"ZBC000_TT_SCREEN_BUTTON","package":"<PAKET>","transport":"<TR>","description":"<kullanıcının onayladığı metin>","extra":{"row_type":"ZBC000_S_SCREEN_BUTTON"}}'
sap_adt_cli.py adt_activate --sap-write --scope <S> --reason "tablo tipi aktivasyonu" --args-json '{"name":"ZBC000_TT_SCREEN_BUTTON","object_type":"ttyp"}'
```
`ZBC000_TT_SCREEN_FIELD` için aynısı (`row_type` = `ZBC000_S_SCREEN_FIELD`).
- `ok:false` "yaratılmadı" değildir → retry etmeden `exists_after` (`true`: tekrar yaratma). Yanıttaki `row_type_live` canlı satır tipidir.
- `adt_post_shell` `description` en fazla 60 karakter (`description_too_long`).

## Ara yol — SE11 (araç reddederse, canlıda düşerse ya da satır tipi düzeltilecekse; kullanıcı)
1. SE11 → **Veri tipi** → ad (`ZBC000_TT_SCREEN_BUTTON`) → Yarat (ya da Değiştir) → **Tablo tipi**.
2. Kısa açıklama (yukarıdaki tablo; proje dilinde). **Satır tipi** sekmesi → "Veri tipi" → satır tipi adı.
3. Kaydet → paket + transport (kullanıcıdan).
4. Aktive et → ekranı **KAPAT** (açık editör kilidi sonraki ADT işlemini `EU 510` ile bloklar).

## Doğrulama (CLI, okuma)
```text
sap_adt_cli.py adt_get --args-json '{"name":"ZBC000_TT_SCREEN_BUTTON","object_type":"tabletype","include_source":false}'
sap_adt_cli.py adt_get --args-json '{"name":"ZBC000_TT_SCREEN_FIELD","object_type":"tabletype","include_source":false}'
sap_adt_cli.py adt_inactive_objects
```
- Beklenen: `exists:true`; metadata'da satır tipi ve `masterLanguage`. Tablo tipinin kaynak (`source/main`) ucu yoktur (yalnız XML).
- Zorunlu: `sap_adt_cli.py adt_sql_query --args-json '{"query":"SELECT typename, rowtype FROM dd40l WHERE typename LIKE '"'"'ZBC000_TT_SCREEN_%'"'"'","row_limit":5}'`
  → iki satır, `ROWTYPE` = ilgili yapı (`%sap-cds-ddic` → `tables-structures.md` §2.2: satır tipi sessizce boş kalabilir).
- Metadata satır tipini göstermiyorsa bu **ölçülemedi** demektir, "doğru" değil → kullanıcıya SE11'de satır tipini teyit ettir.
- `adt_get` DDIC varlığında tek başına karar dayanağı değildir → `adt_search_objects {"query":"ZBC000_TT_SCREEN_*"}` ile çapraz kontrol.
