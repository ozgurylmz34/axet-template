# Klasik rapor / ALV — template-first

> Kaynak: klasik ALV template-first kararı (+ 2026-07 field catalog rafinasyonu) · klasik dialog kodlama standardı
> §2, §3, §4 · kanonik ALV şablonu · üreteç kılavuzundaki çalışan emsal notları · hafıza dersleri (template-first,
> liste ekranı ALV paritesi — klasik taraf).
> ALV paritesi kuralı (sıralama, operatörlü filtre, kolon göster/gizle, varyant, Excel) SAP çekirdeğinde (`00-sap.md`)
> yazılıdır; burada tekrarlanmaz. Clean core (`CL_GUI_ALV_GRID` ↔ `CL_SALV_TABLE`): `%sap-dev` → `references/coding-patterns.md` §7.

## 1. Karar: ALV kurulumu programa satır içi (reusable sınıf YOK)

- Field catalog (başlıklar, hotspot kolonları), layout, olay işleyici ve özel toolbar **her programda satır içi** kodlanır:
  programa yerel `lcl_event` (+ gerekirse `lcl_data`/`lcl_alv`) + `lvc_t_fcat` + `set_table_for_first_display` + `SET HANDLER`.
- Instantiate edilen ortak ALV sınıfı (`<ORTAK_PKG>_CL_ALV_*` türü) **kullanılmaz / yaratılmaz.**
- **Gerekçe (kullanıcı kararı):** başlık/hotspot/olay/toolbar programdan programa tamamen farklı; bunları ortak sınıfa
  taşımak dışarıdan çok sayıda programa özgü parametre geçirmeyi gerektirir → arayüz şişer, satır içinden çirkin olur.
  Böyle bir ortak sınıf bir kez yazılıp **silindi**. ALV paritesi zaten `CL_GUI_ALV_GRID` +
  `set_table_for_first_display( i_save = 'A' )` yerleşiğinden gelir.
- Tutarlılık **şablonla** sağlanır: `templates/classic-alv-list.prog.abap` kopyalanır, özelleştirilir.
- Ağaç liste gerekirse o da satır içi (`lcl_tree` + `CL_SALV_TREE` / ALV tree), ortak sınıf değil.

## 2. Hangi ALV
| Senaryo | Araç |
|---|---|
| Salt okunur, basit liste | `CL_SALV_TABLE` (factory) — az kod (`r_salv_table` parametresi, `programs-includes.md` §2) |
| Düzenlenebilir / özel toolbar / hücre olayı / kolon kişiselleştirme | `CL_GUI_ALV_GRID` + `CL_GUI_DOCKING_CONTAINER` (ya da custom container) |

⚠ Kanonik şablon `CL_GUI_ALV_GRID` üzerinedir. `CL_SALV_*` ailesine geçersen metot ve parametre adlarını şablondan
DEĞİL SALV API'sinden doğrula (davranış testi 2026-09-18: var olmayan bir `SET_SAVE` metodu yazıldı, ancak
aktivasyonda yakalandı).

## 3. Field catalog — DDIC yapısı mı, manuel mi? (ÖNCE SOR)

İkisi de template-first'e uygundur; hangisinin kullanılacağı **bir karardır, sessizce seçilmez**: kurmadan önce
kullanıcıya sor ya da teknik spesifikasyonda gerekçesiyle yaz.

| Yol | Ne zaman |
|---|---|
| **Yapıdan birleştirme** (tercih): programa özel çıktı yapısı `<GÖVDE>_S_<AD>` → `set_table_for_first_display( i_structure_name = … )` ya da `LVC_FIELDCATALOG_MERGE` → sonra yalnız başlık/hotspot/`no_out`/edit ayarı | tipli/karmaşık grid: miktar + birim ondalığı, tutar + para birimi, çok kolon, kod → açıklama kolonları, tekrar kullanım |
| **Manuel `lvc_t_fcat`** | basit / geçici rapor, az kolon, hesaplanan alanlar |

- Manuel fcat'in sessiz hataları (hepsi ölçülmüş): miktarın yanlış ondalıkla gösterilmesi, kod alanlarının açıklama
  kolonunun eksik kalması, içeriğe göre kısa kolon genişliği. Yapıdan birleştirmede tip, uzunluk, QUAN birim referansı
  ve CURR para referansı DDIC'ten gelir.
- Yeni DDIC yapısı = yeni obje → alanlar, data element'ler ve ad kullanıcıya gösterilir, onay alınır (SAP çekirdeği).
- "Her zaman yapı" bir otomatik kapıyla dayatılmaz (basit raporda yanlış olur).
- Kolon başlıkları (`coltext`) `master_language`'de ve tam; metinler spesifikasyondan, tahmin edilmez.

## 4. ALV olaylarında satır kimliği = `es_row_no-row_id` (MUST)

- `hotspot_click` / `double_click` işleyicisinde iç tablo `READ TABLE … INDEX es_row_no-row_id` ile okunur;
  `e_row-index` / `e_row_id-index` **kullanılmaz**.
- Neden: `LVC_S_ROW` (`e_row`, `e_row_id`) = `INDEX` + `ROWTYPE`; ara toplam/toplam satırında ya da `do_sum`, sıralama,
  filtre etkinken `INDEX` iç tablo indeksi değildir → yanlış satır okunur ya da toplam satırında sessiz no-op.
  `LVC_S_ROID` (`es_row_no`) = `ROW_ID` = çıktı tablosu satır numarası.
- İşleyici imzasına `es_row_no`'yu eklemeyi unutma. Sözdizimi doğru olduğundan aktivasyon/ATC/lint geçer; hata yalnız
  sıralı/toplamlı gridde görünür.
- **Hotspot / çift tıkla belge açma:** `SET PARAMETER ID '<PID>' FIELD <değer>.` ardından
  `CALL TRANSACTION '<TCODE>' AND SKIP FIRST SCREEN.` (ör. satış belgesi görüntüleme için ilgili işlem kodu ve parametre
  ID'si sistemde doğrulanır). İşlem kapanınca rapora geri dönülür. Yetki kontrolünün (`WITH AUTHORITY-CHECK`) gerekip
  gerekmediğini ATC ile ölç — DOĞRULANMADI.

## 5. Ekran akışı (ALV bir Dynpro'da)

- Ekran `0100` + GUI status `STAT0100` + başlık `TIT0100` ayrıca üretilir → `dynpro-gui-status.md` (üreteç `<EKRAN_URETECI_FM>`;
  template kiti: `ZBC000_FM_SCREEN_GEN`, `screen-gen-kit.md`). Üreteçle ekranı üretilmiş çalışır demolar:
  `templates/alv-temp1..4-*.prog.abap` (tek gövde demo; gerçek program iskeleti `classic-alv-list.prog.abap`).
- PBO: `SET PF-STATUS` / `SET TITLEBAR`; grid ilk seferde kurulur, sonra `refresh_table_display( )`.
- PAI: `CASE sy-ucomm` (ya da ok-code alanı) ile dağıt; **değerlendirmeden sonra `CLEAR`** zorunlu — atlanırsa önceki
  komut sonraki PAI'de tekrar tetiklenir (yapışkan komut).
- **Navigasyon (MUST):** BACK (F3) / CANCEL (F12) → seçim ekranına dön (`LEAVE TO SCREEN 0`); EXIT (Shift+F3) →
  `LEAVE PROGRAM`. BACK/CANCEL'da `LEAVE PROGRAM` = ana menüye atlama tuzağı, yasak.
- Nav fonksiyonları **normal tip**; `user_command_<n>` yakalar; ESC = F12 = CANCEL. `exit_command_<n>` modülü
  **yazma**: üretilen akışta `AT EXIT-COMMAND` satırı yoksa hiç çağrılmaz (ölü kod).
- Her özel toolbar fcode'u için PAI'de bir `CASE` dalı olmalı; yoksa ekranda tepkisiz buton kalır.

## 6. Container ve alt-sınıf referansı

- Klasik `FORM … USING` alt sınıf referansını **kabul etmez** (ölçüldü: `cl_gui_docking_container` →
  `TYPE REF TO cl_gui_container` "actual parameter incompatible"). Upcast **atama** ile yapılır:
  ```abap
  DATA: go_docking TYPE REF TO cl_gui_docking_container,
        go_cc      TYPE REF TO cl_gui_custom_container,
        go_parent  TYPE REF TO cl_gui_container.   " ortak üst sınıf
  go_parent = go_docking.                           " sonra PERFORM show_alv USING go_parent
  ```
- **Split (master-detail) ayrı ekran tipi değildir:** tek custom control + programda `cl_gui_splitter_container`:
  ```abap
  go_split = NEW cl_gui_splitter_container( parent = go_cc rows = 2 columns = 1 ).
  go_top   = go_split->get_container( row = 1 column = 1 ).
  go_bot   = go_split->get_container( row = 2 column = 1 ).
  ```
  Ekrana ikinci container koyma. Satır oranı: `set_row_height`.
- Butonun etkin/pasif koşulu varsa ALV toolbar yerine uygulama toolbar'ı (`SET PF-STATUS … EXCLUDING`).
- Teşhis kolaylığı: PAI'nin `WHEN OTHERS` dalında donör fcode'u gelirse görünür mesaj bas (nav eşlemesi çalışmadıysa bir turda anlaşılır).

## 7. Metin istisnası
Şablondan türeyen programın iskelet etiketleri (fcat başlıkları) satır içi kalabilir (kullanıcı kararı; tek dilli
proje). Seçim ekranı metinleri istisna değildir → `programs-includes.md` §3.

## 8. Kapanış kontrolleri
- `adt_atc_check` — öncelik politikası proje `AGENTS.md`'sindedir. Politika yoksa kaynak ekipteki uygulama: **öncelik 1
  bulgular zorunlu düzeltilir; öncelik 2/3 kullanıcıya gösterilir ve açık onayla geçilir** (sessiz geçiş yok).
- Liste ekranı: ALV paritesinin beş maddesi gerçekten çalışıyor mu (kullanıcı GUI'de dener; `i_save = 'A'` varyant kaydı dahil).
- `%code-review` → `%verify-done`.
