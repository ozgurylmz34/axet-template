# Klasik program + include — yapı, seçim ekranı, metin havuzu

> Kaynak: klasik dialog kodlama standardı §1, §5, §6 · ekip ADT playbook'unun rapor (PROG/P) bölümü ·
> üreteç kılavuzunun "bilinen sınırlar" notu · hafıza dersi "klasik program include'lara bölünür".
> Include adı türetme ve TITLE sonekleri: `%sap-dev` → `references/naming.md` §4.1, §6 (burada tekrarlanmaz).
> Include + ana program **yaratma sırası** (include ucu, tek aktivasyon, `programType="I"` tuzağı):
> `%sap-adt-foundation` → `references/foundation-ops.md` §4.2 ve `known-errors-adt.md` K-11, K-12.

## 1. Yapı — tek gövde YAZILMAZ

Klasik program (rapor, module pool, Dynpro) tüm kodu tek `REPORT` gövdesinde tutmaz. **Ana program yalnız
`INCLUDE` satırları + olay blokları** (`INITIALIZATION`, `START-OF-SELECTION` …) içerir.

| Include (adı `naming.md` §4.1) | İçerik |
|---|---|
| `_T01` (TOP) | `TYPES`, `DATA`, `CONSTANTS`, `SELECT-OPTIONS`/`PARAMETERS`, yerel `CLASS … DEFINITION` |
| `_S01` (SEL, isteğe bağlı) | seçim ekranı olayları |
| `_C01` (CL) | yerel sınıf `IMPLEMENTATION` (`lcl_*`) |
| `_F01` (F01) | `FORM` rutinleri |
| `_O01` (O01) | PBO modülleri (`MODULE … OUTPUT`: `SET PF-STATUS` / `SET TITLEBAR`) |
| `_I01` (I01) | PAI modülleri (`MODULE … INPUT`: kullanıcı komutu) |

- Büyük include → `02`, `03`. Include'lar **PROG/I** objesidir (tek başına program değil).
- İş mantığı tercihen OO: `lcl_data` (okuma/hesap) · `lcl_alv` (grid kurulumu) · `lcl_event` (ALV olayları) ·
  gerekirse `lcl_app` (akış). ALV kurulumu template-first → `alv-report.md`.
- `templates/` altındaki şablonlar **bilerek tek gövdedir** (yalnız deseni gösterir); gerçek programda yukarıdaki gibi bölünür.
- Hafıza dersi: bu kural baştan konmuş olmasına rağmen uzun oturumda programlar tek gövde yazıldı ve kullanıcı
  düzeltti → yeni klasik program işine başlarken **ilk adım** yapıyı kurmaktır.
- Yerel iskelet üretici: `scripts/scaffold_classic_program.py` (SAP'ye yazmaz; include adlarını türetir, TITLE ister,
  CLI sırasını **yazdırır**). Kullanım `--help`.

## 2. Seçim ekranı kuralları (aktivasyon hataları)

| Kural | Sınır / hata | Doğrusu |
|---|---|---|
| `SELECT-OPTIONS` / `PARAMETERS` adı | **≤ 8 karakter** — "can be up to eight characters long" | `s_<ad>` · `p_<ad>` önekleri; `so_`/`pa_` 8'i kolay aşar (`so_docnum` = 9) |
| `RADIOBUTTON GROUP` adı | ≤ 4 karakter | |
| `BLOCK` adı · `SELECTION-SCREEN COMMENT` değişkeni | ≤ 8 karakter | yorum değişkenini `DATA` ile tekrar tanımlama (SAP örtük tanımlar) |
| Blok `TITLE` değişkeni | `DATA` ile tanımlanırsa "already declared" | `DATA` yok; yalnız `INITIALIZATION`'da ata |
| `TEXT-xxx = '…'` | "The field TEXT-B01 cannot be modified" | serbest değişken (`tit_flt`) + `INITIALIZATION` (K-21) |
| `SELECT-OPTIONS s FOR vbrp-vbeln` | S/4'te `TABLES` olmadan "Field VBRP-VBELN is unknown"; `TABLES` bildirimi eskimiş | önce `DATA gv_vbeln TYPE vbrp-vbeln.` sonra `FOR gv_vbeln` |
| `s_x = VALUE #( ( sign = 'I' … ) )` | bazı sürümlerde sözdizimi hatası | `INITIALIZATION`'da alan alan ata + `APPEND s_x` |
| `AT SELECTION-SCREEN OUTPUT`'ta `screen-text` | "SCREEN does not have a component called TEXT" | radyo düğmesi etiketi seçim metniyle verilir |

- Ad uzunluğu hataları statik kontrollerden (lint, gömülü inceleme) **geçer**; yalnız canlı aktivasyon yakalar.
- Seçim tablosunu tipli bir range parametresine geçirirken alan alan kopyala (`sign/option/low/high`); imzada
  `RANGE OF` yok → `%sap-dev` → `references/coding-patterns.md` §1.
- Uzantı alanı (`ZZ1_*`) için tip: alanın data element adını `DD03L`'den oku, `_BDI` sonekli alan adını değil:
  `adt_sql_query {"query":"SELECT FIELDNAME, ROLLNAME, LENG, DATATYPE FROM DD03L WHERE TABNAME = '<TABLO>' AND FIELDNAME LIKE 'ZZ1%'"}`.
- `CL_SALV_TABLE=>FACTORY` parametresi `r_salv_table`'dır (`salv_table` → "formal parameter does not exist").

## 3. Metinler — metin havuzu (text pool)

- Seçim metinleri, `TEXT-xxx` sembolleri, GUI başlığı, status metni: `master_language`'de ve tam (kesin yasak D);
  kaynakta literal metin gömülmez, sabit ya da metin elemanı kullanılır.
- **İstisna:** kanonik ALV şablonundan türeyen programın iskelet etiketleri (field catalog başlıkları) satır içi kalabilir
  (kullanıcı kararıyla; şablon çalışan kanıtlı örnektir). **Seçim ekranı metinleri istisnaya dahil değildir.**
- `adt_push_source` **yalnız `source/main`**'i yazar; metin havuzu ayrı uç ve ayrı kilittir.

**ÇALIŞAN YÖNTEM (kaynak araç setinde ayrı script ile kanıtlı) — protokol notu:**
- Uçlar: `/sap/bc/adt/textelements/programs/<prog>` (kök, tip PROG/PX) · `…/source/symbols` · `…/source/selections` · `…/source/headings`.
- **symbols biçimi:** her kayıt için ayrı `@MaxLength:<metnin tam uzunluğu>` satırı + `B01=Seçim Kriterleri`; kayıtlar
  **boş satırla** ayrılır; son kayıttan sonra satır sonu **yok** (fazladan boş sembol → `406 DS512`).
- **selections biçimi:** ad 8 karaktere sola yaslı + `=metin` (`P_FILE  =…`, `RB_RAPOR=…`); kayıtlar boş satırla ayrılır.
  DDIC etiketini özel metinle ezmek için `@DDICReference` satırı yazılmaz.
- Altı zorunlu nokta: ① stateful oturum + CSRF (yoksa 403 + kilit kaybı) ② biçim (yoksa `406 DS512`) ③ PUT kilit
  handle'ı ister (`400 SADT_RESOURCE 017`) ④ doğru unlock (yanlışı kilidi sızdırır → sonraki tur `EU 510`) ⑤ kilit
  **metin elemanı** kaynağında alınır, program kaynağında değil (`423 SADT_RESOURCE 026`) ⑥ program zaten aktifse
  PROG/P aktivasyonu no-op olur ve metin havuzunu **aktive etmez** → PROG/PX'i ayrıca aktive et; doğrulama
  `?version=active` okumasıyla (çalışma sürümü PUT edileni gösterip yanıltır; aktifte `=?` ya da boş = aktive olmamış).
- Okuma: her alt kaynak kendi `Accept` tipini ister (kök `application/vnd.sap.adt.textelements.v1+xml`, symbols
  `…textelements.symbols.v1`, selections `…textelements.selections.v1`); `text/plain` → 406 ve sunucu doğru tipi
  gövdede yazar — tipi tahmin etme, 406 gövdesini oku.

**aXet'te araç yok: `push_textpool.py` (metin havuzu yazma) — script aktarımı bekliyor.** CLI'de bu uçlara yazan
araç yoktur; ham REST ile yazma. Seçenek: metinleri `master_language`'de hazırlayıp kullanıcıya ver, kullanıcı
SE38 → Git → Metin elemanları ekranında girer ve kaydeder/aktive eder; sonra ekranı KAPATIR.

## 4. Program açıklaması (TRDIRT) değişikliği
Kaynak araç setinde ADT'den değiştirilemedi (metadata PUT/kilit yolu 406/404/403; aynı objeye kaynak push'u
çalışıyordu) → açıklama değişikliği için **SE38 gerekir** (kullanıcı yapar). CLI'de açıklama değiştiren araç yoktur.
