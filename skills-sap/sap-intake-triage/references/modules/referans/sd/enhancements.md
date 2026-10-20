# SD — genişletme noktaları (referans)

> ⛔ Kesin yasak A: standart kod değiştirilmez. Standart exit/BAdI'nin **uygulaması** kullanıcı kararıdır ve Z ad alanında
> yapılır (Z include / Z uygulama sınıfı). Mevcut Z exit/BAdI uygulaması varsa yeni açmadan önce reuse et (where-used).

## Klasik kullanıcı exit'i (SMOD/CMOD — include'lar)
| Include | Alan |
|---|---|
| MV45AFZZ / MV45AFZB / MV45AFZA | Satış belgesi (VA01/02) |
| RV60AFZZ / RV60AFZC | Faturalama (VF01) |
| MV50AFZ1 (`userexit_save_document` vb.) | Teslimat (VL01N) |
| RV_PRICE_* (USEREXIT_PRICING_*) | Fiyatlandırma |

## BAdI (SE18/SE19)
| BAdI | Alan |
|---|---|
| BADI_SD_SALES_BASIC, BADI_SD_SALES | Satış |
| LE_SHP_DELIVERY_PROC | Teslimat süreci |
| BADI_SD_BILLING | Faturalama |

## Çıktı
- NACE (çıktı koşulu), NAST tablosu, işleme programı + FORM rutini.
- S/4: Output Management (BRF+) · SAP Document Compliance (ör. e-İrsaliye / e-Fatura).

## VOFM
- Kopyalama gereksinimleri / veri aktarım rutinleri (VTLA/VTFL kopyalama kontrolü), fiyatlandırma gereksinim formülleri.

## BTE (Business Transaction Events)
- FIBF — açık FI/SD olay noktaları.

---

## Teslimat yaratma yolları — genişletme her yolda koşmaz
**Ölçüldü** (ekip dersi, bir müşteri projesi, s4_private 2025, 2026-09-30; aXet'te ayrıca ölçülmedi):
- OData `A_OutbDeliveryHeader` deep-create zinciri: `CL_API_OUTBOUND_DEL_02_DPC_EXT` → `CL_OD_CREATE_FROM_SD_DOC` →
  `RV_DELIVERY_CREATE` → `LV50SF0S` FORM `deliver_single_order_item` (toplu yol). VL01N'in geçtiği `SAPFV50C`
  `VORLAGE_KOPIEREN` **atlanır** ⇒ VL01N'de doğrulanmış genişletme API'de çalışmaz.
- İki yolun ikiz noktaları: `VORLAGE_KOPIEREN_01` ↔ `ES_SAPLV50S DELIVER_SINGLE_ORDER_ITEM_02` (ikisi de `get_ship_to_data`'dan
  hemen önce).
- Farklı boşaltma noktası yüzünden teslimat bölünmesinde karar LIKP-ABLAD'da değil `SHP_COMPARE_DELIVERY_PARTNERS`'ta,
  VBPA (WE) ABLAD farkıyla verilir (koşulsuz; `LE_SHP_SUPPRESS_DEL_SPLIT` yalnız TRAGR'ye bakar). LIKP-ABLAD'ı temizlemek
  etkisizdir (tamamlamada XVBPA'dan yeniden dolar). Vakada çare, bellekteki `CVBPA` WE ABLAD'ını her iki noktada boşaltmaktı.
- **Uygula:** teslimat yaratan her müdahalede önce hangi yolun koştuğunu belirle (dialog / API / BAPI / VL10) ve kontrol
  grubu olarak iki yolu ayrı ölç. API çağrısı başka kullanıcıyla (HTTP) koşabilir — debug için o kullanıcıya harici kesme noktası.

## Exit'te yeni satıra `UPDKZ = 'U'` → SM13'te V1 hatası, ST22'de dump YOK
**Ölçüldü** (ekip dersi, 2026-09-23, kullanıcı canlı teyidi; aXet'te ayrıca ölçülmedi):
- Belge exit'i (ör. VI01 navlun maliyeti exit'inin Z include'u, iç tablo `VFKN`) **yeni eklenen** satırlara `UPDKZ = 'U'`
  verirse standart güncelleme (`LV54UF01` db_update) o satırlar için `UPDATE … FROM TABLE` koşar; satır DB'de olmadığı için
  RC 4 → `MESSAGE A` **VY 701** → güncelleme görevi **SM13'te V1 "güncellenemez"**. Kullanıcı "dump" der ama ST22 boştur;
  SM13'teki kayıt kurtarılamaz, belge yeniden yaratılır.
- Düzeltme: `IF <fs>-updkz IS INITIAL. <fs>-updkz = 'U'. ENDIF.` — yalnız DB'de var olan (UPDKZ boş) satır `U` olur, yeni
  satırın `I`'sı korunur.
- **Uygula:** SM13 V1 + VY 701 + ST22 boş üçlüsünü görünce önce ilgili exit'lerde UPDKZ atamalarını ara; yeni satır mı mevcut
  satır mı ayrımına bak (UPDKZ: `I` ekle · `U` güncelle · `D` sil).
