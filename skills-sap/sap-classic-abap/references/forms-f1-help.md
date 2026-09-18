# Çıktı formları (Adobe Forms) ve klasik GUI F1 yardımı

> Kaynak: çıktı/form standardı · Adobe Forms kontrol listesi · klasik GUI F1/SE61 yardım standardı (canlı doğrulanmış
> yöntem). Ad desenleri: `%sap-dev` → `references/naming.md` §4.8 (form), §4.5 (sınıf).

---

## A. Adobe Forms

### A.1 İş bölümü (kritik)
| Parça | Kim | Araç |
|---|---|---|
| **Layout** (yerleşim, tasarım) | **Geliştirici/operatör** (SAP GUI) | SFP Form Builder + Adobe LiveCycle Designer — otomatlanamaz |
| **Interface** (context, import parametreleri, global data) | Geliştirici SFP'de yaratır; **model spesifikasyonu verir** (alanlar, tipler) | SFP |
| **Driver program** (veriyi topla → formu çağır → spool/PDF) | **Model** (Z program) | ABAP + `FP_*` API |
| Veriyi sağlayan SELECT / CDS / BAPI | Model | ilgili skill'ler |

- Yeni geliştirmede Adobe Forms; SmartForms/SAPscript eskidir.
- ADS bağlantısı (SFP/ADS yapılandırması), NAST/NACE çıktı ayarı = Basis/operatör; model dokunmaz.

### A.2 Driver program deseni
```abap
" 1. Formun üretilen FM adını bul
CALL FUNCTION 'FP_FUNCTION_MODULE_NAME'
  EXPORTING i_name     = 'ZSD001_AF_INVOICE'     " Adobe form adı (naming §4.8)
  IMPORTING e_funcname = lv_fm_name.

" 2. ADS işini aç
CALL FUNCTION 'FP_JOB_OPEN' CHANGING ie_outputparams = ls_outputparams.

" 3. Üretilen FM'i çağır (parametreler = interface)
CALL FUNCTION lv_fm_name
  EXPORTING /1bcdwb/docparams  = ls_docparams
            is_header          = ...
            it_items           = ...
  IMPORTING /1bcdwb/formoutput = ls_formoutput.   " PDF = ls_formoutput-pdf

" 4. İşi kapat
CALL FUNCTION 'FP_JOB_CLOSE'.
```
- Desen kaynaktan alındı; `EXCEPTIONS` blokları ve parametre tipleri sistemdeki FM imzasından doğrulanır (`adt_get func`).

### A.3 Kurallar ve kontrol listesi
| ID | Kontrol | Önem |
|---|---|---|
| AF-DIV-01 | Layout + interface **geliştiricinin** SAP GUI işi; model bunları yazmaz, tarif eder | BLOCKER |
| AF-DIV-02 | Model: driver program + interface **spesifikasyonu** (alan/tip listesi) | BLOCKER |
| AF-IF-01 | **Interface = sözleşme:** driver'ın geçtiği parametreler ↔ SFP interface birebir (ad/tip). Spesifikasyon netleşmeden driver yazılmaz | BLOCKER |
| AF-DRV-01 | `FP_JOB_OPEN` → `FP_FUNCTION_MODULE_NAME` → çağrı → `FP_JOB_CLOSE`; `ls_outputparams` / `ls_docparams` | WARNING |
| AF-DRV-02 | Dil/ülke `ls_docparams-langu` (proje dili), `-country`. Yasal çıktı (e-İrsaliye/e-Fatura) → SAP Document Compliance / eDocument; ayrı konu | WARNING |
| AF-DRV-03 | PDF `ls_formoutput-pdf` (XSTRING) → spool / e-posta eki (`email.md` §5) / indirme | WARNING |
| AF-ERR | `FP_JOB_OPEN/CLOSE` istisnaları + `cx_fp_runtime` yakalanır | WARNING |
| AF-NAM-01 | Driver `<GÖVDE>_P_<AD>`, include'lara bölünür (`programs-includes.md` §1) | BLOCKER |
| AF-005 | Z driver; standart çıktı objesine dokunulmaz (kesin yasak A) | BLOCKER |

---

## B. Klasik GUI F1 / SE61 kullanıcı yardımı

Klasik rapor/Dynpro/ALV uygulamasında kullanıcının **F1 / Git → Dokümantasyon** ile gördüğü sistem içi yardım.
RAP/Fiori uygulamalarında uygulanmaz. Repodaki markdown kullanıcı dokümanı yazım kaynağıdır; sistem içi yardım ondan
türetilir, içerik paralel tutulur.

### B.1 Teslim modeli — fihrist + bağlantılı detay sayfaları (tek düz sayfa yasak)
```
RE dokümanı  (obje = PROGRAM ADI)     = fihrist: kısa giriş + içindekiler; her madde bir bağlantı
  ├─ TX dokümanı  <GÖVDE>_KD_<KONU1>  = detay sayfası
  └─ TX dokümanı  <GÖVDE>_KD_<KONU2>
```
Önerilen bölümler: amaç ve kapsam · ön koşul ve yetki · seçim ekranı alanları (tip/değer tanımları dahil) · çıktı
tabloları ve kolonları · hesaplanan kolonlar/formüller · özel mantık · ipuçları ve SSS. Ton sade, jargonsuz.
⛔ Son kullanıcı dokümanında programı SA38/SE38/SE80 ile çalıştırma yolu **verilmez**: işlem kodu ya da "kurumunuzca
tanımlanan menü/rol"; erişemeyen kullanıcı yetkiliye yönlendirilir.

### B.2 ITF biçimi (zorunlu; markdown/HTML değil)
| Amaç | `TDFORMAT` / etiket |
|---|---|
| Sayfa başlığı — **her sayfanın ilk satırı** | `U1` |
| Paragraf / standart paragraf | `/` · `AS` |
| Vurgu (terim, sütun adı) | satır içi `<ZH>metin</>` |
| Bağlantı | satır içi `<DS:TX.<DOKÜMAN>>görünen metin</>` |

- Bağlantı ve vurgu biçimi standart dokümanlarda canlı teyit edildi (`<ZH>`/`<zh>` kabul, kapanış `</>`). Yeni sistemde
  **varsayma**: önce link/vurgu içeren bir standart dokümanı `DOCU_GET` ile okuyup ham satırları bas (PROBE).
- Etiket içinde etiket yok; etiket dışında literal `<…>` yazma ("FN + tarih" gibi yaz). HTML entity/markdown yok.
- ⚠ İki ayrı sınır: depolama `DOKTL-TDLINE` ≤ 132 · **F1/SE61 görüntüleme ≤ 72 ham karakter (etiketler dahil)** —
  aşan satırın kuyruğu **kırpılır** (sarılmaz; canlı teyitli). Her satırı ≤ 70 tut, kelime sınırında böl, etiketi iki satıra bölme.
- Gerçek Türkçe karakter, UTF-8 (BOM yok), oturum dili = `master_language`.

### B.3 Adlandırma
| Obje | Ad |
|---|---|
| Fihrist (RE) | program adı |
| Detay (TX) | `<GÖVDE>_KD_<KONU>` |
| Ortak yazıcı sınıf (proje geneli) | `ZCL_<ORTAK_GÖVDE>_DOCU` (adı kullanıcı onaylar) |
| Programa özel koşucu (`if_oo_adt_classrun`) | `ZCL_<GÖVDE>_<AD>_DOCU_RUN` (adı kullanıcı onaylar) |

### B.4 Üretim — tek çalışan yol
- ADT/REST klasik RE/TX dokümanını **yazamaz** (Eclipse ADT'de editörü de yok). Yol: arka uç FM `DOCU_UPDATE` (yaz) /
  `DOCU_GET` (oku), ITF/TLINE biçimi. Emsal: abapGit'in doküman objesi sınıfı.
- `DOCU_UPDATE` standart bir FM API'sidir (tabloya doğrudan DML değil). Released değildir → ATC cloud-readiness bulgusu
  verir; geliştirme aracı olarak ve kendi Z objemizin dokümanı için kabul edildi (öncelik 1 değil, 2/3 → açık onayla geçilir).
1. **Ortak yazıcı sınıf:** `write_object_doc( id, object, langu, title, it_itf )` → THEAD (`tdform = 'S_DOCU_SHOW'`,
   `tdstyle = 'S_DOCUS1'`, `state = 'A'`, `typ = 'E'`) → `DOCU_UPDATE` → `COMMIT WORK`. `read_object_doc( … )` → `DOCU_GET`.
2. **Programa özel koşucu:** ITF satırları burada. `main()` sırası: **PROBE → TX detay sayfaları → RE fihrist → `DOCU_GET` geri okuma**
   (bağlantı hedefleri önce var olsun).
3. Koşucu `adt_classrun` ile çalıştırılır (**yazma sınıfı** → `--sap-write` + kapsam + onay; oturum dili = proje dili).
   Güncelleme = içeriği değiştir + yeniden push/aktive + yeniden classrun.
- **İçerik kaynağı (uydurma yok):** tip/değer tanımları domain sabit değer etiketlerinden canlı (`adt_get doma`); kolon/formül
  fonksiyonel spesifikasyon + sınıf mantığından; kaynak yetmezse dur, sor.

### B.5 Bilinen tuzaklar (canlı yaşanmış)
| Tuzak | Çözüm |
|---|---|
| Doküman kabuğu `adt_post_shell`/`adt_push_source` ile yaratılamaz (CLI'nin kabuk ve push tiplerinde doküman objesi yok — `tool-catalog.md`) | gerek yok — `DOCU_UPDATE` dokümanı yaratır |
| Başlık (`tdtitle`): obje adı > 20 karakterse `DSYST DOKNAME C(20)` sınırı yüzünden başlık yazılmaz, `DOCU_GET` boş döner | kozmetik — SE61/F1 başlığı gövdenin ilk `U1` satırından alır → her sayfanın ilk satırı `U1` |
| classrun "does not implement if_oo_adt_classrun~main" | ayrıştırma hatası değil: koşucu aktive edilmemiş ya da oturum bayat → `%sap-adt-foundation` K-13; taze sınıf adı açma |
| `DOCU_UPDATE` transport kaydı ister | kullanıcının verdiği açık transport (yeni transport yaratma yok — kesin yasak C) |

### B.6 Bitti tanımı
1. Geri okuma: her doküman `DOCU_GET` ile var, `DOKHL-DOKSTATE = 'A'`, doğru dil.
2. Vurgu/bağlantı biçimi PROBE çıktısıyla teyitli.
3. **Kullanıcı F1 testi:** işlem kodu → F1 → fihrist açılır → bağlantı detay sayfasını açar → Türkçe karakterler düzgün, satır kırpılması yok.
4. ATC öncelik 1 = 0 (her iki sınıf).
