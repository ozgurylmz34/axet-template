---
name: sap-classic-abap
description: >
  Use for classic ABAP with SAP GUI technology on ECC or S/4HANA on-premise: source-based classes
  (push, save-scan and unknown-comment errors), programs split into includes, selection screens and
  text pools, function groups and modules (signature, TABLES, RFC), classic reports and ALV
  (template-first), Dynpro screens with GUI status, e-mail from ABAP, Adobe Forms drivers and F1 or
  SE61 help. Triggers: "klasik rapor", "ALV raporu", "program yaz", "include'lara böl", "sınıf push
  400", "fonksiyon modülü", "dynpro ekranı", "GUI status", "mail gönder", "Adobe form", "F1 yardımı".
  Do not use for RAP, CDS or ABAP Cloud objects, SEGW or classic OData (use sap-odata-backend), UI5,
  triaging a new request (use sap-intake-triage first) or generic ADT read and push (use
  sap-adt-foundation).
---

# Klasik ABAP — sınıf, program, FM, rapor/ALV, Dynpro, e-posta, form

> **Profil:** klasik objeler (program, include, fonksiyon grubu, Dynpro, GUI status, SE61 dokümanı) yalnız `ecc` ve
> `s4_private` profillerinde vardır; **`s4_public` ve `btp_abap`'ta yoktur** → `sap-project.json` `sap_profile` bunlardan
> biriyse DUR, kullanıcıya bildir. Klasik obje yalnız `_CLC` paketinde (`%sap-dev` → `references/naming.md` §3).
> Kesin yasaklar (A/B/C/D) ve liste ekranı ALV paritesi SAP çekirdeğinde (`00-sap.md`) yüklüdür; burada tekrarlanmaz.
> ADT protokolü (kabuk/push/aktivasyon, kilit, transport, 412/423/409) → `%sap-adt-foundation` ve `references/*`.

## When to use this skill
- Klasik bir Z sınıfı, program, include, fonksiyon grubu/modülü yaratılacak ya da değiştirilecekken.
- Klasik rapor / ALV liste, seçim ekranı, Dynpro ekranı, GUI status, başlık çubuğu işi.
- ABAP'ten e-posta, Adobe Forms driver programı, klasik F1/SE61 kullanıcı yardımı.
- Sınıf push'unda satır numarasız 400, FM imzası/`TABLES`, `00256`/`00264` gibi klasik hatalar.
- **Kullanma:** RAP/CDS/ABAP Cloud · SEGW/klasik OData backend (`%sap-odata-backend`) · UI5 · yeni talebin ilk
  ele alınışı (`%sap-intake-triage`) · tek başına okuma/indirme/aktivasyon sorusu (`%sap-adt-foundation`).

## How to use this skill

### 0. Her işte ortak akış
1. Talep sınıflandı mı (S0/S1/S2) → değilse `%sap-intake-triage`. Obje/paket adı ve kodlama → `%sap-dev`.
2. Profil + paket kontrolü (yukarıdaki not). Paket `.rules.md` ve `SESSION_NOTES.md` son kaydı okunur.
3. **Kullanıcıdan gelir, uydurulmaz:** transport, paket, obje adı, TITLE/açıklama, metinler ve etiketler (spesifikasyondan).
4. CLI: `python <TEMPLATE>/skills-sap/sap-adt-foundation/scripts/sap_adt_cli.py --list` otoritedir; yazma çağrılarında
   `--sap-write --scope … --reason …` (ya da `--intake`). Uzun kaynakta `--args-file`.
5. SAP'deki kaynağı değiştirmeden önce `adt_get` (pull-before-edit). Push/aktivasyon mesajına güvenme:
   `adt_inactive_objects` + kaynak geri okuma; yeni objede `masterLanguage` metadata'dan.
6. aXet'te aracı olmayan adımı **SAP GUI işi olarak tarif et, geliştirici uygular** (ekranı açtırırken
   "aç → yap → KAPAT"); ham REST/SOAP ile yazan script yazma.
7. Kapanış: `references/checklists.md` ilgili fazlar → ATC (§Rules) → `%sap-code-review` → `%verify-done` → paket `SESSION_NOTES.md`.

### 1. Sınıf (source-based)
- **Önce oku:** `references/classes.md` · `%sap-adt-foundation` → `foundation-ops.md` §4.6, `known-errors-adt.md` K-01/K-03/K-20.
- **Kullanıcıdan:** sınıf adı (`ZCL_<GÖVDE>_<AD>`), açıklama, transport.
- **CLI:** `adt_get` (exists:false) → `adt_post_shell class` → `adt_get` (kaynaklı) → `adt_push_source` → `adt_activate`.
- **Doğrula:** `adt_inactive_objects`, aktif kaynak kıyası. Satır numarasız 400 → `classes.md` §2 (bisect) / §3 (yetim yorum).
- Test include'u (`ccau`): `adt_get` → `adt_push_source` `ccau` (`name` = ana sınıf; çevrimdışı test edildi, canlı DOĞRULANMADI) → `classes.md` §5.

### 2. Program + include
- **Önce oku:** `references/programs-includes.md` · naming §4.1 (include adı), §6 (TITLE soneki) · `foundation-ops.md` §4.2 (sıra).
- **Kullanıcıdan:** TITLE (yoksa yaratma), program adı (≤ 26), transport.
- **Yerel iskelet:** `python <TEMPLATE>/skills-sap/sap-classic-abap/scripts/scaffold_classic_program.py <PROG> --title "…" --out <paket>/programs [--dialog] [--selscreen]`
  (SAP'ye yazmaz; include adlarını ve CLI sırasını yazdırır).
- **CLI sırası:** include kabukları (`include`) → program kabuğu (`prog`) → boş kaynak push → **tek** `adt_activate` + `also`
  (önce include'lar) → gerçek kaynaklar → tekrar aktivasyon. `programType="I"` ile include yaratma (K-11).
- **Metin havuzu** (seçim metinleri, `TEXT-xxx`): CLI'de araç yok → metinleri hazırla, kullanıcı SE38'de girer (`programs-includes.md` §3).
- **Doğrula:** inaktif 0; seçim ekranı adları ≤ 8 (yalnız aktivasyon yakalar).

### 3. Fonksiyon grubu + fonksiyon modülü
- **Önce oku:** `references/fugr-fm.md` (§0 aXet araç durumu) · `foundation-ops.md` §4.4 · K-15.
- **Kullanıcıdan:** grup/FM adı (genel araçsa amaca göre ad), açıklama, transport, yeni tablo tipi adı/metni.
- **CLI (yalnız `ecc`/`s4_private`; çevrimdışı test edildi, canlı DOĞRULANMADI):** kaynağı yerelde hazırla (imza satır içi,
  `TABLES … TYPE <tablo tipi>`), `%sap-code-review` → `adt_post_shell fugr` → `adt_activate fugr` → `adt_post_shell func`
  (`extra.function_group`, Z/Y) → `adt_get func` → `adt_push_source func` (FM'i araç kendisi aktive eder). **RFC işareti hâlâ
  kullanıcı işi (SE37)**. Araç düşerse kullanıcı SE80/SE37 ya da ADT'den yapar (`fugr-fm.md` §0).
- **Doğrula:** `adt_get {"object_type":"func"}` ile kaynak ve `function_group`; FM gövdesinde arama için `L<FG>U01…` include'larını oku.

### 4. Rapor / ALV liste (template-first)
- **Önce oku:** `references/alv-report.md` · şablon `templates/classic-alv-list.prog.abap`.
- **Kullanıcıdan:** field catalog yolu (DDIC yapısı mı manuel mi — **sor**), kolon başlıkları, seçim alanları.
- **Yap:** şablonu kopyala, §2'deki include yapısına dağıt; ALV kurulumu satır içi (ortak ALV sınıfı yok); satır kimliği `es_row_no-row_id`.
- **İki şablon türü — karıştırma:** `classic-alv-list.prog.abap` = gerçek programın iskeleti (kopyalanır, include'lara
  **bölünür**). `alv-temp1..4-*.prog.abap` (`ZBC000_P_ALV_TEMP1..4`) = ekranı üreteçle üretilmiş, **çalışır tek gövde demo**
  (docking · custom container · split master-detail · buton/alan/çok ekran); deseni ve üreteç çağrısını gösterir, gerçek
  programa tek gövde kopyalanmaz. Hangisinden başlanır → `references/screen-gen-kit.md` §5.
- Ekran/status → §5. **Doğrula:** ALV paritesinin beş maddesi + BACK/EXIT/CANCEL kullanıcı GUI testinde.

### 5. Dynpro ekranı + GUI status
- **Önce oku:** `references/dynpro-gui-status.md` (§0 yol seçimi). Tek kayıtlık form → ayrıca `references/dynpro-dialog-fields.md`
  + `templates/classic-dynpro-dialog.prog.abap`.
- **Yol:** sistemde ekran/CUA üreten yardımcı Z RFC FM varsa kaynağını oku, payload'ı hazırla → imzası kit üreteciyle aynıysa
  `adt_screen_generate` ile çağır (yazma sınıfı, READ dahil; yalnız `ecc`/`s4_private`; çevrimdışı test edildi, canlı DOĞRULANMADI);
  imza farklıysa ya da araç kullanılamıyorsa çağrıyı geliştirici yapar. `adt_classrun` bu API'leri koşamaz. Üreteç yoksa Screen
  Painter (SE51) + Menu Painter (SE41) adımlarını somut değerlerle tarif et.
- **Üreteç kiti:** sistemde üreteç yoksa ve ortak araç kurulması kullanıcıca onaylanırsa `templates/screen-gen/` (yapılar,
  tablo tipleri, fonksiyon grubu, `ZBC000_FM_SCREEN_GEN`) → sıra ve kim-ne-yapar `templates/screen-gen/DEPLOY.md` (yapılar, tablo
  tipi kabukları, FUGR/FM, programlar ve ekran üretimi CLI; paket ve RFC işareti kullanıcı). Parametreler, `EV_RC`/`nav_remap=ON`
  sinyali, şablon başına çağrı değerleri → `references/screen-gen-kit.md`. Kit SAP'de derlenmedi (DOĞRULANMADI).
- **Kullanıcıdan:** ekran numarası, başlık/status metinleri, buton fcode+metinleri, DDIC yapısı ve alan adları.
- **Doğrula:** program ↔ ekran numaraları (`STAT<n>`/`TIT<n>`/`status_<n>`) tutarlı; `act` korunmuş; runtime'da `00256`/`00264`
  yok, ESC çalışıyor (geliştirici çalıştırır); çok turlu işte `BUT` deltası yazımdan önce.

### 6. E-posta
- **Önce oku:** `references/email.md` (§7 kontrol listesi).
- **Kullanıcıdan:** alıcı bakım tablosu, konu/gövde metni, ek biçimi. Test gönderimi dışa dönük iştir → onay.
- **Yap:** gönderen `sy-uname`/`'B'`, satır içi stil, 255 parça, `commit_work`. **Doğrula:** SOST'ta çıkış kullanıcıya kontrol ettirilir.

### 7. Adobe Forms / F1 yardımı
- **Önce oku:** `references/forms-f1-help.md`.
- **Form:** layout + interface geliştiricinin SFP işi; model interface spesifikasyonu + driver program (`FP_*`) yazar.
- **F1:** ITF (≤ 72 karakter satır, `U1` başlık), RE fihrist + TX detay, `DOCU_UPDATE` çağıran Z koşucu `adt_classrun` ile
  (yazma sınıfı → onay). **Doğrula:** `DOCU_GET` geri okuma + kullanıcı F1 testi.

## Referanslar ve şablonlar
| Dosya | İçerik |
|---|---|
| `references/classes.md` | sınıf yaratma özeti, kaydetme taraması (bisect), yetim yorum konum tablosu, OSQLC çakışması, test include'u, classrun |
| `references/programs-includes.md` | include yapısı, seçim ekranı hataları, metin havuzu protokolü, program açıklaması |
| `references/fugr-fm.md` | aXet araç durumu, FUGR/FM protokolü, `TABLES` iki kısıt, `corrNr` otoritesi, RFC, SOAP-RFC LUW, FUGR arama körlüğü |
| `references/alv-report.md` | template-first kararı, SALV ↔ ALV grid, field catalog kararı, satır kimliği, navigasyon, split/upcast |
| `references/dynpro-gui-status.md` | yol seçimi, elle tarif, `RPY_DYNPRO_*` / `RS_CUA_INTERNAL_*` reçetesi, donör, container değerleri, doğrulama |
| `references/dynpro-dialog-fields.md` | DDIC'e bağlı alanlar, etiket kuralı, F4 dört mekanizma, SHLP sınırı, çok turlu CUA tuzakları |
| `references/email.md` | `SO_DOCUMENT_SEND_API1` / `CL_BCS`, HTML tuzakları, Excel eki, kontrol listesi |
| `references/forms-f1-help.md` | Adobe Forms iş bölümü + driver + kontrol listesi; F1/SE61 ITF standardı ve üretimi |
| `references/checklists.md` | klasik dialog programı ön kontrol listesi (5 faz) |
| `references/known-errors-classic.md` | belirti → dosya/bölüm indeksi |
| `references/screen-gen-kit.md` | ekran üreteci kiti: 16 parametre, `EV_RC` bantları + `nav_remap=ON` sinyali, dört şablonun üreteç çağrıları, hangi şablondan başla, kite özgü tuzaklar, kaynaktan fark |
| `templates/classic-alv-list.prog.abap` | ALV liste programı **iskeleti** (tek gövde gösterir; gerçek programda include'lara bölünür) |
| `templates/classic-dynpro-dialog.prog.abap` | tek kayıtlık modal diyalog ekranı şablonu |
| `templates/alv-temp1-docking.prog.abap` · `alv-temp2-custom-container` · `alv-temp3-split-master-detail` · `alv-temp4-screen-gen-demo` | `ZBC000_P_ALV_TEMP1..4`: ekranı üreteçle üretilmiş **çalışır tek gövde demolar** (docking · custom container · split · buton + alan + çok ekran) |
| `templates/screen-gen/` | kurulabilir üreteç kiti: iki yapı DDL, `table-types.md`, FUGR ana program + TOP, `ZBC000_FM_SCREEN_GEN.func.abap`, `DEPLOY.md` (sıra + CLI/kullanıcı dağılımı) |
| `scripts/scaffold_classic_program.py` | yerel program + include iskeleti ve CLI sırası (SAP'ye yazmaz) |

## Rules
- **Tahmin yok:** yöntem, alan adı, FM imzası, tip, metin; önce referans/çalışan artefakt, sonra sistemden okuma. Belirsizse DUR, sor.
  Tip playbook'u eksik görünüyorsa "yapılamaz" deme: paketteki çalışan `.abap` kaynaklarını ve benzer Z objeyi oku.
- Klasik program **tek gövde yazılmaz**; ALV kurulumu **programda satır içi**, ortak ALV sınıfı yaratılmaz.
- Yeniden kullanılacak araç objesine (FM, grup, sınıf) ilk kullanan programın adı verilmez; ad aracın amacını yansıtır — yaratmadan önce sor.
- `adt_classrun` ve `adt_syntax_check` **yazma sınıfıdır**. Diyalog bağlamı isteyen FM'ler classrun ile koşmaz.
- Standart programlar (ör. CUA donörü) yalnız **okunur**; standart program/status/ekran/exit yazılmaz (yasak A).
  Ekran/status üreteci hedef adı Z/Y olmalı; korumayı var olmayan bir adla dene.
- ATC: proje `AGENTS.md` politikası geçerli; yoksa öncelik 1 bulgular zorunlu düzeltilir, öncelik 2/3 kullanıcıya gösterilip
  **açık onayla** geçilir (sessiz geçiş yok).
- Bir çare ilk denemede tutmadıysa ikinci kez uygulama; dayandığı teşhisi sorgula. Tanıdık semptomda önce `%recall`.
- aXet'te karşılığı olmayan yöntemde ham REST/SOAP script'i yazılmaz; kullanıcıya "araç yok" diye bildirilir.
- Denemelerden sonra çalışan yöntem bulunduysa (çalışan + denenen başarısız yollar) `%remember`.
