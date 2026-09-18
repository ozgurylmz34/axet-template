# abaplint — kod incelemesinde kullanım, kapsam ve okuma

> **Kaynak:** yazma kapısındaki `check_abaplint.py` ile paylaşılan ayar dosyası ve sürüm pini, ekip dersleri
> ("parser_error gerçek olabilir", abaplint'in yakalamadığı ölçülmüş sınıflar) ve bu skill'de yapılan ölçümler (tarih
> belirtilmiştir). abaplint açık kaynak bir ABAP statik analiz aracıdır; Node.js üzerinde `npx` ile koşar.

## 1. İki giriş noktası
| | Yazma kapısı: `check_abaplint.py` | İnceleme: `scripts/abaplint_run.py` |
|---|---|---|
| Ne zaman | `adt_push_source` öncesi, `class_push` zincirinde otomatik; ya da `run_review --task class_push` elle | İnceleme sırasında, değişen tüm ABAP dosyalarına tek koşum |
| Önem | WARNING (zinciri bloklamaz) | çıkış koduyla bildirir; önem ilgili liste satırından gelir |
| Dosya | tek artefakt | çok dosya ve klasör |
| Obje tipi | sınıf + program (içerikten tanır). Arayüz ve FM ölçülmez → durum satırında `measured=false` → `run_review` SKIP (WARNING) | sınıf, arayüz, program; içerikten tanınan `*.ccimp.abap` gibi dosyalar sınıf olarak. FM/FUGR, CDS, BDEF, XML ölçülmez ve listelenir |
| Ölçülmeyeni gösterir mi | durum satırı (`measured=false`) | `ÖLÇÜLMEDİ (N)` listesi + çıkış 4 |

Ölçüm (2026-09-13, bu skill yazılırken):
- `run_review --task class_push` bir arayüz dosyasında: abaplint gate'i SKIP (`unsupported-object-type`), diğer beş gate koştu.
- Aynı arayüz `abaplint_run.py --offline` ile ölçüldü (`0 issue(s) found, 1 file(s) analyzed`).
- Bir `.prog.abap` üzerinde `run_review --task class_push` koştu: altı gate de çalıştı, abaplint programı ölçtü.
  Buna karşın push eşlemesinde program ve arayüz için zincir yoktur (`_reviewer.py` `prog`, `intf` → `None`).
  Yani bu tiplerde kapı push anında hiçbir şey koşmaz; inceleme adımı bu boşluğu elle kapatır.

## 2. Ayar dosyası (tek kaynak)
Varsayılan: `<skills-sap>/sap-adt-foundation/scripts/sapadt/lib/abaplint/abaplint.json` — yazma kapısıyla aynı dosya.
Proje özel kural gerekiyorsa paylaşılan dosyayı değiştirme: projede ayrı bir dosya tut ve `--config` ile ver.
(`abaplint_run.py` yalnız `global.files` alanını geçici kopyada `/src/**/*.*` yapar; diğer ayarlara dokunmaz.)

| Kural | Durum | Neden (ayar dosyasındaki açıklama) |
|---|---|---|
| `check_syntax` | kapalı | izole dosyada ad/tip çözümlemesi gürültü üretir; otoriter sözdizimi SAP'dedir |
| `keyword_case`, `7bit_ascii` | kapalı | Türkçe metin ve karışık büyük/küçük harf meşru |
| `parser_error`, `unreachable_code`, `identical_conditions`, `identical_form_names`, `empty_statement`, `contains_tab`, `dangerous_statement` | açık | yapısal/mantık ve hijyen |
| `line_length` 255 · `sequential_blank` 5 | açık | hijyen |

`syntax.version: v757`, `errorNamespace: ^(Z|Y)`. Ölçüm notu (2026-09-13): abaplint 2.120.38 çıktısının başlık satırı
bu ayarla çalışırken `ABAP release: v789 (… on-premise 757 …)` basıyor. Ayrıştırıcının hangi sürüm kurallarını uyguladığı
DOĞRULANMADI; sürüme bağlı bir bulguda (yeni sözdizimi) kesin karar push/aktivasyondur.

## 3. Sürüm pini ve ağ
- Pin: `@abaplint/cli@2.120.38` — yazma kapısıyla aynı (eşitliği `tests/test_abaplint_run.py` zorlar). Pin değişikliği
  yazma kapısında bilinçli bir karardır; bu script onu izler, önde gitmez.
- Varsayılan koşum `npx --yes <pin>`: önbellekte yoksa npm kayıt defterinden indirir. Genel (global) kurulum yapmaz.
- `--offline`: `npx --no` + npm çevrimdışı ayarı; yalnız önbellekteki pin kullanılır, indirme yapılmaz.
  Ölçüm (2026-09-13): önbellekte pin varken 4 dosya ≈ 3 sn'de analiz edildi.
- `npx` yoksa (Node.js kurulu değil) çıkış 3 ve "temiz değildir" mesajı. Kurulum kullanıcı kararıdır.

## 4. Çıkış kodları ve durum satırı
| Çıkış | Anlam | Okuma |
|---|---|---|
| 0 | seçilen tüm dosyalar ölçüldü, bulgu yok | derleme/aktivasyon kanıtı DEĞİL (`check_syntax` kapalı) |
| 1 | en az bir bulgu | her bulgu ilgili liste satırıyla eşlenir ya da gerekçeyle geçilir |
| 2 | kullanım hatası (yol ya da ayar dosyası yok/bozuk) | düzelt, tekrar koş |
| 3 | ölçüm yapılamadı: `npx` yok, zaman aşımı, abaplint özet satırı yok, analiz edilen dosya ya da bulgu sayısı tutmuyor | "temiz" yazma; nedeni rapora yaz |
| 4 | ölçülen dosyalar temiz ama bazı dosyalar ölçülmedi (ya da hiçbiri desteklenmiyor) | ölçülmeyen listesi rapora girer |

Son satır: `ABAPLINT-RUN-STATUS: status=… measured=true|false reason=… files_measured=N files_unmeasured=M issues=K`.
Fail-open kilidi: abaplint'in kendi özet satırı (`N issue(s) found, M file(s) analyzed`) zorunlu kanıttır; M yazılan
dosya sayısına, N ayrıştırılan bulgu sayısına eşit olmalıdır. Ölçüm (2026-09-13): boş `src/` ile abaplint
`generic_error … 0 file(s) analyzed` basıp çıkış 1 veriyor. Script bunu bulgu değil çıkış 3 sayar.

## 5. Bulguları okuma
- `parser_error`: modern sözdiziminde (EML, RAP, source-based sınıf) ayrıştırıcı kayması olabilir; ama gerçek kaydetme
  hatalarını da gösterir (`checklist-abap.md` BE-36, BE-47, BE-48). Körü körüne yanlış pozitif sayma: çalışan bir
  referans kaynakla kıyasla, kesin kararı push/aktivasyona bırak.
- Ölçülmüş yanlış pozitifler (muafiyet değil, önce bunlara bak): CDS table function çağrısı `SELECT … FROM z…( )` →
  `parser_error`; klasik TOP include tek başına `Expected CLASSDEFINITION`.
- abaplint'in yakalamadığı ölçülmüş sınıflar (temiz sonuç bunları temize çıkarmaz): BE-10b yetim yorum, BE-22 generic tablo
  parametresinde WHERE/KEY, BE-51 bildirimden önce kullanım, BE-55 satır içi `TABLE OF` parametre, BE-69 FM `TABLES` tipi.
- `unreachable_code`, `identical_conditions`, `empty_statement`: çoğunlukla gerçek mantık kusurudur; bağlamı oku.

## 6. İncelemedeki yeri
1. `run_review` (yazma kapısıyla aynı zincir) → 2. `abaplint_run.py` değişen tüm ABAP dosyalarına → 3. çıktı olduğu gibi
   inceleyici brifingine (`reviewer-brief.md` §2) → 4. inceleyici bulguyu liste satırına bağlar.
- abaplint bulgusu tek başına karar belirlemez: bağlandığı liste satırının önemi geçerlidir. Bağlanamayan bulgu WARNING'dir.
- Çıkış 3 ya da 4'te ölçülmeyen dosyalar raporda "ÖLÇÜLMEDİ" olarak kalır; ilgili satırlar elle yürünür.

## Bu dosyada ÇIKARILAN / DEĞİŞTİRİLEN
- Yazma kapısındaki tek dosya modeli korunmuş, inceleme için çok dosyalı ayrı bir koşucu eklenmiştir; kapı değiştirilmedi.
- Fonksiyon grubu yerleşimi (abapGit fonksiyon grubu dosya düzeni) kurulmadı: FM/FUGR bugün ölçülmez (açık kalem).
- Kaynaktaki "abaplint sonrası canlı sözdizimi kontrolü" adımı alınmadı: CLI'de yazma sınıfıdır; kesin karar push/aktivasyon.
