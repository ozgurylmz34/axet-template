# SD derin dersleri (SD-D1…SD-D11) — standart SAP davranışı

> **Ne bu:** `sd.md` tetik haritasından işaret edilen, **standart SAP davranışı** olan SD dersleri (kimlikler kaynak çekirdekle
> aynıdır). Proje izi (sistem, ambar/tesis kodu, belge no, müşteri) ayıklanmıştır.
> **Kanıt düzeyi:** ölçülen kalemler **tek bir S/4 private DEV sisteminde** ölçüldü; satır içinde **DOĞRULANMADI / DENENMEDİ /
> ölçülmedi / "kod okumasından çıkarım"** etiketi taşıyan kısımlar ölçülmedi (ör. SD-D4 GUI menü yolu, SD-D5 hibrit köprü, SD-D7
> çağrısız SA, SD-D10 standart onay sınırı, SD-D11 tarih ofseti). Başka sistemde hepsi **hipotezdir** — kullanmadan önce canlıda
> doğrula (`sd.md` "Ne DEĞİL" notu). Sessiz hata üretenler ⚠ ile işaretli. aXet'te bu kalemlerin hiçbiri ayrıca ölçülmedi.

### SD-D1 ⚠ Embedded EWM: ERP ambar no ≠ EWM ambar no (stok sorgusu sessizce 0 satır) — T-SD-1
- Embedded EWM'de (ERP ile aynı istemci; `/SCWM/T300` dolu, `I_EWM_PLANTSTORLOCMAPTOWHSE.ERPLOGICALSYSTEM` kendi mantıksal
  sistemi) ERP `LGNUM` (3 karakter) ile EWM `LGNUM` (4 karakter) **farklı kodlardır**.
- `LIKP-LGNUM` **ERP** kodunu taşır; `/SCWM/*` ve `A_WarehouseAvailableStock` **EWM** kodunu ister. Çeviri
  **`I_EWM_PLANTSTORLOCMAPTOWHSE`** (plant + depo yeri → EWM ambarı); `T320` tek başına yetmez (yalnız ERP LGNUM).
- Çeviri atlanırsa sorgu **hata vermez, 0 satır döner** → "EWM'de stok yok" yanlış hükmü (sessiz boş sonuç sınıfı).
- Yardımcılar: `A_WarehouseAvailableStock.PRODUCT` = gerçek MATNR (GUID eşlemesi gerekmez) · `BATCH` = `LIPS-CHARG` · ERP teslimat ↔
  EWM belge köprüsü `/SCDL/DB_REFDOC` (`REFDOCCAT='ERP'`, `DOCCAT='PDO'`) ya da released `I_EWM_DELIVERYREFERENCEDOC` · klasik WM
  kullanılmıyorsa `LIKP-LVSTK` boştur, anlamlı olan `LIKP-VLSTK` (EWM dağıtım durumu).
- ⚠ Depo görevi belge anında henüz yoktur ⇒ göz bilgisi o anda **tahsis değil, bulunabilirliktir**.

### SD-D2 ⚠ Embedded EWM qRFC: iki yön de SMQ2'de; "dağıtıldı" ≠ EWM kabul etti — T-SD-3
- ERP→EWM ve EWM→ERP kuyruk kayıtlarının **ikisi de gelen kuyrukta (SMQ2 / `TRFCQIN`)**; SMQ1'de (`TRFCQOUT`) EWM kaydı beklenmez
  (oradaki `MCEX_UPDATE_*` kayıtları LO veri çıkarımıdır). Kullanıcı "SMQ1'de bekliyor" dese de **SMQ2'de ara**.
- Yön kuyruk adı önekinden değil **fonksiyon adından (`QRFCFNAM`)** okunur: `DLVS…` = `/SCWM/OUTB_DLV_SAVEREPLICA` (ERP→EWM, ODO
  kopyası) · `DLWS…` = `BAPI_OUTB_DELIVERY_CHANGE` / `…_CONFIRM_DEC` (EWM→ERP) · `WMDPPDO…` = `/SCWM/PPF_POST_GM` ·
  `EWMSGM_<LGNUM>…` = `/SPE/GOODSMVT_CREATE`. Hedef (`DEST`) bir uygulama sunucusu adı taşıyabilir — "ayrı sistem" belirtisi DEĞİL.
- Kuyruk FIFO'dur: baştaki SYSFAIL arkasındaki aynı adlı LUW'leri kilitler. İşlenen LUW silinir ⇒ "kuyrukta 0 satır" zaman bilgisi
  taşımaz (henüz gelmedi / işlendi ayırt edilemez).
- ⚠ Teslimat `VLSTK` ile "dağıtıldı" görünürken EWM kopyayı reddetmiş olabilir (SYSFAIL; ör. EWM'de kalem türü uyarlaması eksik) ⇒
  ODO **asenkron** doğar ya da hiç doğmaz; bekleme/poll kalıcı yokluğu çözmez.
- Tasarım: birincil kapı released CDS (`I_EWM_OutbDelivOrdHdr`); `TRFCQIN` released değil (ham Basis tablosu) — en fazla
  best-effort teşhis. Teşhis (`adt_sql_query`): `SELECT qname, qstate, qrfcfnam, qrfcdatum, errmess FROM trfcqin WHERE qname LIKE
  '%<teslimat>%'` (`TRFCQOUT`'ta `qrfcfnam` kolonu 500 verdi — çıkar). Kuyruk işlemleri (yeniden çalıştır/sil) operasyonun işidir, AI yapmaz.

### SD-D3 ⚠ Üçüncü parti e-irsaliye BAdI'si teslimat silmede popup açar → BAPI/RFC ile silme kırılır — T-SD-3
- Türkiye e-dönüşüm eklentisi kurulu sistemde (partner ad alanlı bir eklenti) `LE_SHP_DELIVERY_PROC~DELIVERY_DELETION` uygulaması,
  teslimatın e-irsaliye kaydı varsa `POPUP_TO_CONFIRM` açar. Metin T100'de değil **metin sembolünde** — mesaj aramasında çıkmaz.
- RFC/OData oturumunda `CX_SY_SEND_DYNPRO_NO_RECEIVER` (SAPLSPO1 0500); cevap '1' değilse `MESSAGE a…` oturumu keser. `sy-batch`
  RFC/OData'da **boştur** ⇒ "BAPI'den mi geldi" ayrımında işe yaramaz; doğru ayraç `GUI_IS_AVAILABLE` (FUGR SFES, released).
- Partner ad alanı müşteri ad alanı değildir → kesin yasak A kapsamında, dokunulmaz; düzeltmeyi eklentinin sahibi yapar. Program
  içinden teslimat silme/değiştirme "dynpro no receiver" ile düşerse önce bu BAdI'ye bak; geçici yol VL02N'den manuel silme.

### SD-D4 SD GOS kalem bazında ek TUTMAZ — kalem için DMS bağlantısı ya da Z geliştirme
- `CL_SD_SLS_GOS` → `SD_OBJECT_TYPE_DETERMINE` kalem nesnesini (VBAP) de döndürür ama `gos_publish_object` yalnız başlık BOR'unu
  (BUS2031/BUS2032) `CL_GOS_MANAGER`'a verir; `SRGBTBREL-INSTID_A` = VBELN. Uyarlama anahtarı **yok**.
- Kalem BOR'u var (TOJTB `VBAP` "SalesItem", anahtar VBELN+POSNR). DMS kalem bağlantısı uyarlamayla mümkün: TDWO `DOKOB=VBAP` ×
  belge türü (ekran 0215); SAPMV45A `MV45AF0D_DOKUMENTE_PFLEGEN` → `DOCUMENT_ASSIGNMENT`. GUI menü yolu DOĞRULANMADI.
- ArchiveLink TOAOM `VBAP` boş; Attachment Service `SAO_TYPE_DEF` yalnız başlık düğümleri (VBAP eklemek = standart tabloya yazma →
  kesin yasak B). Geliştirme yolu: Z uygulama + `CL_GOS_MANAGER`/`CL_GOS_API` ile `VBAP` anahtarı (released değil).

### SD-D5 VF04 (fatura vade listesi) genişletme: Custom Fields GUI'ye gelmez
- VF04 = SDBILLDL; liste yapısı `VKDFIF` (= `VKDFI` + birkaç alan), ALV `VKDFS_ALV_DISPLAY` (SAPLV60P).
- **GUI kolonu:** CMOD `V60P0001` → `EXIT_SAPLV60P_008` (`TABLES c_vkdfif`, ALV'den hemen önce) + `VKDFIF`'e append (standart DDIC —
  kesin yasak A; append adı **kullanıcıdan**). `VKDFIZ` "customer reserve" include'u da standarttır. `VKDFIF` VF24'te de kullanılır
  (kolon orada boş görünür).
- **Custom Fields:** context `SD_BILLINGINDEX` persistence'ı yalnız **VKDFS** tablosunda; kullanımı Fiori `C_BILLINGDUELISTITEM_F0798`
  + OData `SD_CUSTOMER_INVOICES_CREATE`; **GUI kullanımı 0** (`CFD_W_GUI_CTXT`) ⇒ VF04 GUI'ye saf Custom Fields yolu YOK. Hibrit köprü
  (VKDFS Custom Field'ı ile aynı adlı VKDFI append'i) **DENENMEDİ**.
- Seçim ekranı: exit yetmez → `ENHANCEMENT-POINT sdbilldl_10` + implicit `FO:VKDFS_DATA_COLLECT\SE:END`. Önce "GUI mi Fiori mi" sor.

### SD-D6 Satış belgesi kalemi maliyet yapısı (VA22 ağacı) okuma
- Ağaç bağı: üst kalemin CKIS satırında `UKALN` doluysa alt maliyet hesaplamasına bağlanır; montaj işareti `BAUGR` (CDS'te
  `CostingItemIsAssembly`). Alt seviye KEKO (B tipi) kayıtları **aynı satış belgesi kalemine** yazılır ⇒ kalem başına **iki toplu okuma**
  yeter (KEKO: belge+kalem · CKIS: FAE); seviye başına döngüde okuma gerekmez.
- ATC: `DO` döngüsü içindeki FAE okuması da P1 "Local Nested Reading DB OP" sayılır (`%sap-code-review` BE-12; DO aynı sınıf).
- `I_SalesDocCostEstimateItem` / `I_SalesDocumentCostEstimate` **released değil**. CKIS `TYPPS` metinleri DD07T domain `TYPPS`'ten.

### SD-D7 ⚠ Teslimat planında (SA, `VBTYP='E'`) VBEP açık miktar için GÜVENİLMEZ — T-SD-5
- **VBEP'in VARLIĞI açık miktar kanıtı değildir:** tamamı sevk edilip kapanmış SA'da da termin satırları durur. **YOKLUĞU tek yönlü
  sağlamdır:** satır yoksa sevk edilecek şey de yoktur. Veri bozuk değil, **semantik farklı**.
- Ölçülen dağılım (tek DEV sistemi): SA belgelerinin ~%45'inde hiç VBEP satırı yoktu.
- Çağrılı SA'da (VBEP-ABART '1'/'2') teslim havuzu `LV45EU11` / `RV_SCHEDULE_CHECK_DELIVERIES` içinde **`S073-LIEFFZ` (kümülatif, yıl
  kuralı) − `VBLB-ABEFZ` (ABRLI='0000')** ile kurulur (`SD_DELIVERY_CUMULATIVE_DETERM`); VBEP yalnız havuzun satırlara dağıtıldığı
  yerdir ⇒ **VBFA üzerine konan süzgeçler SA'da NO-OP'tur**.
- Modellenmeyen sınır: çağrısız SA (ABART başka) FM'de VBFA-RFMNG yoluna düşer — ölçülmedi.

### SD-D8 ⚠ SA çağrı geçmişi (VBLB/VBEH/VBEP) okuma tuzakları — T-SD-5
1. Çağrı sırası = `VBLB-ABRLI`: `0000` güncel; geçmişte **küçük ABRLI daha yeni**, `9999` en eski. Geçmiş termin satırları VBEH'te
   (`0000` yok), güncel olanlar VBEP'te.
2. `ABRLI=9999` ("yaratım kaydı") **içerikli olabilir** — başlığa göre elersen gerçek çağrı düşer; içerik tabanlı süz.
3. Ay satırının (PRGRS=3) `EDATU`'su ayın 1'i olmak zorunda değil.
4. **VBEP'te VBTYP kolonu YOK** — SA süzgeci VBAK join'iyle. Miktar = `WMENG` (`BMENG` farklı olabilir).
5. `ABRDT` kirli olabilir — sıralama/varsayılan seçimi bozar.
6. Malzeme değer yardımı CDS'inin anahtarı yalnız `Matnr` ama satırı MVKE satırıysa join'i `Matnr + Vkorg + Vtweg` ile yap (aksi hâlde
   OData anahtar çakışması + şişen sayım).
7. Belge türü released başlıkta `I_SalesSchedgAgrmt.SalesSchedgAgrmtType`; standart DCL (`V_VBAK_AAT` + `V_VBAK_VKO`) Z görünüm
   üzerinden okumada değerlendirilmez ⇒ Z DCL şart (`%sap-code-review` BE-67 ailesi).

### SD-D9 Müşteri konsinye stoğunda (SOBKZ=W, `MSKU`) depo yeri boyutu YOK
- `MSKU` anahtarı MATNR/WERKS/CHARG/SOBKZ/KUNNR; LGORT'un anlamı yoktur. Konsinye siparişinde, teslimatta ve mal çıkışında (633) LGORT
  **boştur** ⇒ stok kontrolünü depo yeri bazlı kurma, teslimat/MÇ BAPI'lerine LGORT gönderme.

### SD-D10 Standart satış fiyatı onayı yalnız anahtarında `KFRST` olan koşul tablolarında çalışır — T-SD-2
- S/4 satış fiyatı onayı (`COND_WORKFLOW`, `KONH-PRICEAPPROVALREQUEST`, `KONP-KFRST`) onay sınıfı yalnız anahtarında `KFRST` olan
  koşul tablolarını işler ⇒ erişim sırası tabloları `KFRST` içermiyorsa standart onay devreye giremez [kod okumasından çıkarım, canlı
  denenmedi]. Önce sistemde üçüncü parti bir fiyat onay eklentisi kurulu mu bak.
- Koşul kaydı yazma: released `CL_PRCG_CNDNRECORD_API_FACTORY` → `IF_SLSPRCG_CNDNRECD_API`; RAP `I_SlsPrcgConditionRecordTP_2` yazma
  BDEF'te kapalı; `BAPI_PRICES_CONDITIONS` notReleased. Release kanıtı `ARS_W_API_STATE` (`adt_sql_query`) ile okunabilir.
- ⚠ **Hata dalı tasarımı — sessiz yanlış fiyat, görünür fiyat eksikliğinden AĞIRDIR** (SD uzmanı kullanıcı düzeltmesi): fiyatsız kalan
  sipariş fark edilir; yanlış fiyat sessizce faturaya gider. Kısmi yazım / geri alma / sıra seçeneklerinde her dalı "görünür mü, sessiz
  mi" diye sınıfla; "fiyatsız kalmak yanlış fiyattan kötüdür" gerekçesi yanlıştır.
- ⚠ **Canlı test ölçütü standart kayıttır:** koşul kaydı yazan bir ürünün testinde başarı uygulamanın kendi durum alanı değil, test
  anahtarlarına ait `A<nnn>`/`KONH`/`KONP` (+ iş kullanıcısına göre `CDHDR`) satırlarının eylem öncesi/sonrası farkıdır. Ekip vakası:
  simülasyon adımı standart API'yi çağırıp `ROLLBACK` ediyordu; API varsayılanı (`IV_SYNC = abap_true`, güncelleme görevinde kaydet)
  kaydı yine kalıcı yazdı → onaysız fiyat SAP'ye gitti; yüzlerce taklit (mock/TEST-SEAM) testi bunu göremedi. Taklit edilen standart
  API'nin commit/rollback/senkronluk davranışı gerçek API'ye karşı bir kez ölçülür; ölçülmeyen varsayım TS'te DOĞRULANMADI kalır.

### SD-D11 ⚠ VDA 4905 (çağrı/teslimat planı EDI'si) parse: sabit 128 karakter + KARIŞIK KODLAMA
- Bazı OEM'ler EDIFACT değil **VDA 4905** gönderir: 128 karakterlik sabit kayıtlar, kayıt tipi ilk 3 karakterde (`511`, `512`, …).
- ⚠ **Aynı klasörde karışık kodlama** olabilir (ölçülen korpus: 17 dosya EBCDIC `cp500` + 465 dosya ASCII). Klasöre tek kodlama
  uygulayan parser sessizce çöp üretir ⇒ **dosya başına tespit**: `raw=open(p,'rb').read(); enc='ascii' if raw[:3]==b'511' else 'cp500'`.
- Ampirik ofsetler (bir OEM korpusunda ölçüldü, dokümandan değil — kendi korpusunda yeniden ölç): `511 [5:14]` müşteri no ·
  `511 [14:23]` tedarikçi no · `512 [5:8]` fabrika → `KNREF` · `512 [38:60]` müşteri parça no (22 kr.) → `E1EDP10/IDNKD` ·
  `512 [82:92]` `BSTKD` · `512 [94:98]` boşaltma noktası → `ABLAD`. `511 [23:29]` tarih ofseti DOĞRULANMADI.
- ⚠ **Parça no dolgu varyantı:** 22 karakterlik alan = 11 parça no + 11 ek alan; aynı parça iki farklı dolgu karakteriyle (sıfır /
  boşluk) gelebilir. Ara katman ham alanı normalize etmiyorsa `KNMT`'de **her yazım için ayrı satır** gerekir; eksik `KNMT` `V4 035`
  verir. Otorite = orijinal mesaj dosyası, DEV IDoc'u değil.
