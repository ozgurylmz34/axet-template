# SAP adlandırma standardı

> Kurumsal ABAP adlandırma standardının aXet'e uyarlanmış hâli. Paketin `.rules.md` dosyasındaki Naming tablosu
> bu dosyadan üretilir ve **pakete özgü istisnalarla birlikte önceliklidir**.
> Teknik ad İngilizce yazılır; açıklama, başlık ve etiketler projenin `master_language`'indedir.
> Obje adı en fazla 30 karakterdir; SAP uzun adı sessizce kesebilir.

Örneklerde `ZSD001` = paket gövdesi (Z + modül + 3 hane). `Y` önekli projede `Z` yerine `Y` yazılır.

## 1. Clean core seviyeleri

| Seviye | Tanım | Teknoloji |
|---|---|---|
| **A** (en temiz) | ABAP Cloud ile ya da BTP'de yan yana geliştirme | RAP, CAP, low-code, released API |
| **B** (temiz) | Klasik ABAP ve klasik API, SAP önerilerine uygun | klasik ABAP |
| **C** (koşullu) | SAP iç objelerini kullanır; yükseltme öncesi kontrol ister | rastgele SAP objeleri |
| **D** (temiz değil) | Modifikasyon, önerilmeyen obje, implicit enhancement | modifikasyon |

Standart objeye dokunmak (D) kesin yasak A kapsamındadır.

## 2. WRICEF kategorileri
**W**orkflow · **R**eport · **I**nterface · **C**onversion · **E**nhancement · **F**orm. Paket numarası WRICEF
tipini göstermez; yalnız sıradır.

## 3. Paket adı

- `Z` ya da `Y` + modül kodu + **3 haneli sıra numarası**, arada alt çizgi yok: `ZSD001` (`ZSD_001` değil).
- Varsayılan paket **cloud** paketidir (sonek yok): ABAP Cloud, yalnız released API, geliştirme aracı ADT.
- Klasik obje gerekiyorsa aynı numarayla **`_CLC`** soneki: `ZSD001_CLC` (tüm ABAP objeleri, SE80 + ADT).
- Hiyerarşi: `Z_ROOT` → modül ana paketi `ZSD` → iş paketleri `ZSD001`, `ZSD001_CLC`, `ZSD002` …
- **Paket ve transport yaratılmaz** (kesin yasak C); hangisinin kullanılacağı kullanıcıya sorulur.
- Yerel klasör: `<source_root>/<MODÜL>/<PAKET>/` (`new_package.py`).

## 4. Obje adları

Önek kuralı: `<PAKET GÖVDESİ>_<TİP>_<AD>` (ör. `ZSD001_T_ORDER`). `_CLC` paketinde de gövde `ZSD001`'dir.

### 4.1 Rapor ve include (klasik — yalnız `_CLC` paketinde)
| Obje | Tip | Örnek |
|---|---|---|
| Program (rapor) | `P` / `R` | `ZSD001_P_INVOICE_REPORT` |
| Include | `I` | `ZSD001_I_INVOICE_REPORT_T01` |

**Include adı program adından türer, kısaltma yok:** `ZSD001_P_<AD>` → `ZSD001_I_<AD>_<Tip><NN>`.
Tip: `T` top · `S` seçim ekranı · `C` sınıf · `O` PBO · `I` PAI · `F` form; NN 01'den artar.
`ZSD001_I_INVREP_T01` gibi kısaltma yanlıştır. Program adı **en fazla 26 karakter** (26 + `_T01` = 30).
Standart programa bağlı exit include'ları bu türetme kuralına tabi değildir.

### 4.2 Arayüz ve servis
| Obje | Tip | Örnek |
|---|---|---|
| OData servisi (klasik) | `ODS` | `ZSD001_ODS_CUSTOMER` |
| Service definition | `UI` / `API` | `ZSD001_UI_ORDER` · `ZSD001_API_ORDER` |
| Service binding | `UI` / `API` + OData sürüm soneki **zorunlu** | `ZSD001_UI_ORDER_O2` · `ZSD001_API_ORDER_O4` |
| Service consumption | `SC` | `ZSD001_SC_RATES` |
| Inbound / outbound service | `IS` / `OS` | `ZSD001_IS_ORDER` · `ZSD001_OS_ORDER` |

### 4.3 CDS ve RAP
| Obje | Tip | Örnek |
|---|---|---|
| Interface view (kök ya da çocuk) | `I` | `ZSD001_I_ORDER` · `ZSD001_I_ORDERITEM` |
| Projection (consumption) view | `C` | `ZSD001_C_ORDER` |
| Root view (ayrı gerekirse) | `R` | `ZSD001_R_ORDER` |
| Extension view | `E` | `ZSD001_E_ORDER` |
| Data definition (DDL) | `DDL` | `ZSD001_DDL_CUSTOMER_LIST` |
| Behavior definition | **kök view ile aynı ad** (SAP zorunluluğu) | `ZSD001_I_ORDER` |
| Behavior implementation sınıfı | sınıf deseni (§4.5) | `ZCL_SD001_ORDER` (`ZBP_*` kullanılmaz) |
| Draft tablosu | `A` … `_D` | `ZSD001_A_ORDER_D` |

### 4.4 Fonksiyon grubu ve modül (klasik — yalnız `_CLC`)
| Obje | Tip | Örnek |
|---|---|---|
| Function group | `FG` | `ZSD001_FG_INVOICE` |
| Function module | `FM` | `ZSD001_FM_INVOICE_OUTPUT` |

Cloud geliştirmede yerine released API kullanan sınıf ya da RAP.

### 4.5 Sınıf ve arayüz
Rolü ne olursa olsun (iş mantığı, yardımcı, behavior implementation) tek desen:
| Obje | Desen | Örnek |
|---|---|---|
| Class | `ZCL_<gövde, Z'siz>_<AD>` | `ZCL_SD001_ORDER_HANDLER` |
| Interface | `ZIF_<gövde>_<AD>` | `ZIF_SD001_INVOICE_OUTPUT` |
| Exception class | `ZCX_<gövde>_<AD>` | `ZCX_SD001_PO_ERROR` |
| Test class | `ZCL_<gövde>_TC_<AD>` | `ZCL_SD001_TC_PO_TEST` |

`Y` önekli pakette: `YCL_SD001_…`. BAdI implementasyon sınıfları desene uymayabilir → paket `.rules.md`
"Bilinen istisnalar"a yazılır.

### 4.6 Özel alan ve genişletme
| Obje | Önek | Örnek |
|---|---|---|
| Custom field | `ZZ1_` | `ZZ1_DESC` |
| Enhancement implementation | `ENH` | `ZSD001_ENH_MV45AFZZ` |
| Customer exit include | paket gövdesi | `ZSD001_…` |
| Custom logic | `ZZ1_` | `ZZ1_LE_SHIP_MODIFY_ITEM` |
| BAdI implementation | `ZZ1_IMP_` | `ZZ1_IMP_PO_CUST` |
| Customizing include (`EEW*`, `CI_*`) alanı | `ZZ_` | `ZZ_…` |

Append yapı ve standart objeye alan ekleme kesin yasak A'dır; ad kullanıcıdan gelir.

### 4.7 Veri sözlüğü
| Obje | Tip | Örnek |
|---|---|---|
| Table | `T` | `ZSD001_T_DESC` |
| Table type | `TT` | `ZSD001_TT_INVOICE` |
| Structure | `S` | `ZSD001_S_REPORT` |
| Append structure | `ZZ` | `ZZMARA` (yalnız kullanıcı talebiyle) |
| View (klasik) | `V` | `ZSD001_V_SIZE` |
| Data element | **`E`** | `ZSD001_E_AMOUNT` |
| Domain | **`D`** | `ZSD001_D_AMOUNT` |
| Search help | `SH` | `ZSD001_SH_CUSTOMER` |
| Message class | **`MSG`** | `ZSD001_MSG` |
| Number range | `NR` | `ZSD001_NR` |
| Transaction code | paket gövdesi | `ZSD001` |
| Lock object | `E` + gövde | `EZSD001_ORDER` |
| Authorization object | `Z_` | `Z_PORGIN` |

Data element `E`, domain `D`'dir: `_DE_`, `_DTEL_`, `_DOM_` yanlıştır.

### 4.8 Form
| Obje | Tip | Örnek |
|---|---|---|
| Adobe form | `AF` | `ZSD001_AF_INVOICE` |
| Adobe interface | `IF` | `ZSD001_IF_INVOICE` |
| Smart form / style (klasik) | `SF` / `SS` | `ZSD001_SF_INVOICE` |

### 4.9 Workflow
| Obje | Tip | Örnek |
|---|---|---|
| Workflow template | `WF` | `ZSD001_WF_01` |
| Workflow task | `TS` | `ZSD001_TS_01` |
| Responsibility rule | `RL` | `ZSD001_RL_01` |
| E-posta şablonu | `EMT` | `ZSD001_EMT_NOTIFICATION` |

### 4.10 Public cloud objeleri
| Obje | Tip | Örnek |
|---|---|---|
| Communication scenario / system / arrangement / user | `CS` / `CSYS` / `CARR` / `CUSR` | `ZSD001_CS_SALES` |
| Business catalog / role | `BC` / `BR` | `ZSD001_BR_SALESREP` |
| App job catalog / template | `AJC` / `AJT` | `ZSD001_AJT_BILLING` |
| IAM app | `IAM` | `ZSD001_IAM_PORTAL` |

### 4.11 Önek çakışmaları
- `_I_` hem klasik include (`programs/`) hem CDS interface view (`cds/`).
- `_E_` hem data element hem CDS extension view.

Tip ve klasör ayırır; aynı kök adı iki tip için kullanma (`ZSD001_I_ORDER` hem include hem view olmaz).

### 4.12 Eski biçimler
Sistemde bu standarttan önce yaratılmış objeler olabilir (ör. `<GÖVDE>_CL_*` sınıf, `_MSG` eksiz mesaj sınıfı).
Bunlar ihlal sayılmaz ve yeniden adlandırılmaz; paket `.rules.md` "Bilinen istisnalar"a yazılır. **Yeni obje
yeni biçimle** yaratılır.

## 5. Alan tipleme sırası ve yeniden kullanım
Yeni alan tiplerken yeni obje yaratmadan önce mevcudu ara:
1. Released standart data element.
2. Mevcut Z data element (bu paket ya da ortak paket) — kopya yaratma.
3. Yoksa yeni Z data element: 4 etiket `master_language`'de ve tam (kesin yasak D). Adı bu standarda uygun
   **önerebilirsin**; canlıda kontrol et (varsa başka ad), kullanıcı açıkça onaylamadan yaratma (`SKILL.md` §6).
   Standart objeye append alanının adı ise önerilmez (§4.6, kesin yasak A).
4. Son çare ilkel tip (`abap.char(n)` …) — tercih edilmez.

Ortak master/value-help CDS için yerel kopya yaratılmaz: ortak view yeniden kullanılır, association kurulur.
Ortak mı yerel mi belirsizse kullanıcıya sor. Yeniden kullanım araması sistemde yapılır (`adt_search_objects`).

## 6. Include TITLE metni
Obje adındaki `_T01` soneki ile TITLE metni ayrı alanlardır. Ana program TITLE'ı: `"<Rapor adı>"`.
Include TITLE'ı: `"<Rapor adı> - <SONEK>"`.

| Include | TITLE soneki |
|---|---|
| Top (tanımlar) | `TOP` |
| Seçim ekranı | `SEL` |
| Modül / diyalog mantığı | `MDL` ya da `O01` / `I01` |
| Form rutinleri | `F01` (F02 …) |
| ALV mantığı | `ALV` |
| Yerel sınıf tanımları | `CL` ya da `CLD` |

TITLE boş ya da `master_language` dışında bırakılmaz (kesin yasak D).

## 7. Kontrol listesi
| Kontrol | Örnek |
|---|---|
| Z/Y öneki var | `ZSD001_C_ORDER` |
| Modül kodu doğru | `ZSD…`, `ZMM…`, `ZFI…` |
| Paket numarası sıralı, alt çizgisiz | `ZSD001` |
| Obje tipi öneki doğru | `CL` `IF` `T` `S` `C` `I` `R` `E` |
| Teknik ad İngilizce, metinler `master_language`'de | `ZCL_SD001_ORDER_HANDLER` |
| Klasik obje yalnız `_CLC` pakette | rapor `ZSD001_P_…` → `ZSD001_CLC` |
| Service binding'de `_O2` / `_O4` | `ZSD001_UI_ORDER_O2` |
| Ad ≤ 30 karakter (program ≤ 26) | |
| Clean core seviyesi değerlendirildi | A / B / C |
