---
name: office-excel
description: >
  Use when the user wants to inspect, profile, convert, filter, clean, group, sort or compare Excel, CSV
  or JSON tables, or pull embedded pictures out of an .xlsx: profiling an SAP or ALV export before
  analysis, turning CSV/JSON into a styled .xlsx, a before/after or migration delta between two
  extracts, a formatted report with number formats and a chart. Triggers: "Excel'i oku", "bu tabloda
  ne var", "CSV'yi Excel yap", "filtrele", "grupla", "topla", "iki Excel'i karşılaştır", "fark
  raporu", "mutabakat", "Excel'deki resimleri çıkar", "biçimli Excel raporu". Do not use for Word or
  PDF documents (office-docs) or slide decks (office-slides).
---

# office-excel — tablo profilleme, dönüştürme, karşılaştırma

## When to use this skill
- Kullanıcı bir Excel/CSV/JSON dosyasının içeriğini anlamak, temizlemek, özetlemek, başka biçime çevirmek istiyor.
- İki dışa aktarım arasındaki farkı (eklenen/silinen/değişen) görmek istiyor — ör. geçiş öncesi/sonrası.
- Biçimli bir rapor dosyası (başlık, sayı biçimi, grafik) ya da `.xlsx` içindeki resimler isteniyor.
- **Kullanma:** Word/PDF → `%office-docs` · sunum → `%office-slides`.

## Araç
Tek script, alt komutlar (`<TEMPLATE>` = template klonu):
```
python <TEMPLATE>/skills/office-excel/scripts/office_excel.py <alt komut> --help
```
| Alt komut | Ne yapar | Bağımlılık |
|---|---|---|
| `profile DOSYA` | sayfalar, kolon tipi, dolu/boş, farklı değer, min/max/toplam, uyarılar, örnek satırlar | yok |
| `convert GİRDİ ÇIKTI` | csv/tsv/json/xlsx → xlsx/csv/tsv/json (xlsx: biçimli başlık, dondurma, filtre) | yok |
| `transform GİRDİ ÇIKTI` | `--where` → `--dedupe` → `--group-by/--agg` → `--sort` → `--rename` → `--keep/--drop` (bu sırayla) | yok |
| `compare ESKİ YENİ --key K` | anahtar(lar)la eklenen / silinen / değişen hücre; `--output fark.xlsx` | yok |
| `images DOSYA.xlsx` | gömülü resimleri `Sayfa_Hücre_n.png` adıyla çıkarır | yok |
| `report GİRDİ ÇIKTI.xlsx` | başlık, `--number-format`, zebra satır, `--chart bar|line` | **openpyxl** |

Çıkış kodu: `0` başarı · `1` veri hatası · `3` kullanım hatası · `4` isteğe bağlı bağımlılık yok.
Ortak seçenekler: `--sheet` (ad ya da 1'den başlayan sıra), `--header-row N`, `--json-key`, `--force`.

## How to use this skill
1. **Önce profille.** Her işe `profile` ile başla; kolon adlarını ve tiplerini çıktıdan al, tahmin etme.
   Kolonların yarısından fazlası boş uyarısı gelirse başlık 1. satırda değildir (SAP BEx/ALV dışa aktarımı) →
   `--header-row N` ile yeniden profille. Birden çok sayfa varsa hangisi olduğunu kullanıcıya sor.
2. **Hassas veri:** dosya kişisel veri içeriyorsa (müşteri/personel/banka, TCKN/VKN) örnek değerleri bağlama
   dökme: `profile --no-samples`, `compare --summary-only`. Çıktı dosyasını repoya değil kullanıcının verdiği
   yere ya da `.tmp/`'ye yaz. SAP'den çekilen veride SAP paketindeki KVKK kuralı ayrıca geçerlidir.
3. **Dönüştür / süz:** `transform` her zaman YENİ dosyaya yazar; girdinin üzerine yazmaz.
   ```
   ... transform satis.xlsx ozet.xlsx --where "Tutar|gt|1000" --group-by Bölge --agg "Toplam=sum:Tutar" --sort "Toplam:desc"
   ```
   `--where` biçimi `Kolon|op|değer` (op: `eq ne gt ge lt le contains startswith empty notempty`; `contains`
   Türkçe büyük/küçük harf duyarsız). Sonuçtaki satır önce→sonra sayısını kullanıcıya bildir.
4. **Karşılaştır:** anahtar kolonu kullanıcıya DOĞRULAT ("her satırı tekil tanımlayan kolon hangisi?").
   - SAP numaraları baştaki sıfırla gelebilir (`000010` ↔ `10`): gerekiyorsa `--key-mode number`.
   - "Tekrarlanan anahtar" uyarısı → bileşik anahtar (`--key A --key B`); tekrarlarda yalnız ilk satır kıyaslanır.
   - Değerler varsayılan olarak sayıca eşitse aynıdır (`1` = `1.0`); birebir metin için `--strict`.
   - Raporda eklenen/silinen/değişen sayıları + beklenmeyen kolon farkı.
5. **Rapor:** `report` openpyxl ister. Yoksa script `4` döner; kurmayı kullanıcıya öner ve onayını bekle
   (`python -m pip install --user openpyxl`) — kendiliğinden kurma.
6. **Doğrula:** çıktıyı `profile` ile yeniden oku ve satır/kolon sayısını kullanıcıya aktar.

## Rules
- Girdi dosyası değiştirilmez; var olan çıktı yalnız kullanıcı isterse `--force` ile ezilir.
- Script'in basmadığı bir değeri/kolonu uydurma; sonuçları script çıktısından aktar.
- Dosya Excel'de açıksa yazma `PermissionError` verir → kullanıcıdan dosyayı kapatmasını iste.

## Sınırlar (ölçülmüş / bilinen)
- Stdlib okuyucu: formülün yalnız dosyada kayıtlı sonucu okunur (yeniden hesaplanmaz); birleştirilmiş hücre,
  hücre biçimi, pivot okunmaz; tarih biçimli sayılar ISO metne çevrilir. Eski `.xls` desteklenmez.
- CSV: UTF-8 (BOM'lu/BOM'suz), olmazsa cp1254 denenir; ayraç `, ; tab |` içinden sezilir. Binlik ayraçlı sayı
  (`1.234,56`) sayıya çevrilmez.
- Stdlib ile yazılan `.xlsx` openpyxl ile doğrulandı (değer, dondurma, filtre, kalın başlık); **Excel
  uygulamasında açılışı DOĞRULANMADI**.
- Resimler: yalnız eklenmiş resimler (`xl/media`) çıkar; grafik ve koşullu biçim resim değildir.
