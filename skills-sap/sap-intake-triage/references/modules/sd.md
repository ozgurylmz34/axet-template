# SD modül paketi — intake triage için

> **Ne bu:** SD (Satış ve Dağıtım) işi geldiğinde protokolün (`../protocol.md`) 2. adımında okunan
> **tetik haritası + zorunlu kontroller + soru şablonu + kaynak işaretçisi**.
> **Ne DEĞİL:** SD bilgi deposu. Domain olgusunu ezber sanma; paket seni doğru kaynağa (canlı sistem + resmi doküman + hafıza)
> yönlendirir. Uzmanlık kaynak zincirinden çıkar.
> **Nasıl büyür:** yeni bir SD tuzağı/dersi öğrenilince satır eklenir (`%remember` + template'e öneri).
>
> **Kod inceleme checklist referansları:** `BE-nn` / `FE-nn` kimlikleri ekip kod-inceleme checklist maddeleridir. `BE-nn`
> satırları `%sap-code-review` kontrol listelerinde, `FE-nn` satırları `%sap-ui5-fiori` → `references/checklists.md`'dedir;
> maddenin kısa anlamı burada da yanında yazılıdır.
>
> Aşağıdaki "SE" = örnek projedeki Z sevk emri belgesi (müşteri siparişinden teslimata giden ara Z belge). Kendi projende karşılığı
> yoksa bu satırları "Z ara belge" diye oku.

---

## ZORUNLU KONTROL (SD işi + kapsam ≥ S1)

| # | Kontrol | Kural |
|---|---|---|
| SD-K1 | **Standart objeleri where-used + CANLI oku, VARSAYMA** — VBAK/VBAP (sipariş), VBEP (termin), VBFA (belge akışı), LIKP/LIPS (teslimat), VBRK/VBRP (fatura), KONV/PRCD_ELEMENTS (fiyatlandırma), VTTK/VTTS (nakliye), VFKP (navlun) | TAHMİN YASAK (hafıza = hipotez, canlı = otorite; pull-before-edit) |
| SD-K2 | **Akış eksenini belirle** — sipariş → teslimat → fatura, hangisinde? (kopyalama kontrolü / belge akışı etkisi) | model bütünlüğü |
| SD-K3 | **Standart belgeye YAZMA yok** — LIKP/VTTK/VBRK/VBAK'a doğrudan yazım YASAK → released API → BAPI → RFC FM → BDC sırası — genel karar ağacı `%sap-dev` → `references/write-api-selection.md`; SD örnekleri: BAPI_OUTB_DELIVERY_CREATE_SLS, BAPI_SHIPMENT_CREATE (BAPI) · SD_SCDS_CREATE (resmi FM, RFC-enabled DEĞİL → ağacın ADIM 4'ü; RAP handler'dan Z RFC sarmalayıcıyla). Z katman işlem belgesi yazmaz, **doğru belirleyicilerle besler** | ⛔ Yasak A/B (SAP çekirdeği) |
| SD-K4 | **Müşteri/BP verisi released CDS'ten** — ham KNA1/KNVV/BUT000 yerine I_Customer / I_CustomerSalesArea / I_BusinessPartner / I_Supplier | ⛔ clean core · ⚠ released halefin `authorizationCheck`'ini canlı oku (DCL sessiz 0 satır riski) |
| SD-K5 | **Commit'li BAPI ayrı LUW** — SD belgesi yaratan commit'li FM (BAPI_SHIPMENT_CREATE, SD_SCDS_CREATE `i_opt_commit`) RAP handler'dan DOĞRUDAN çağrılamaz → RFC-FM ile ayrı LUW | `%sap-code-review` checklist-rap BE-26 |

---

## TETİK HARİTASI (ister/alan → domain konusu → araştır + mevcut sistemde bak + tuzak)

> Her anlamlı istek/alan bir domain konusu tetikler. Konuyu 3 eksende araştır, SONRA değerlendir/sor.
> Aşağıdakiler örnek katalogdur; talebe göre yenisini türet.

### T-SD-1 · "kullanılabilir stok / depo stoğu / ATP" → STOK + AVAILABILITY
- **ARAŞTIR:** EWM mi IM/MM mi? (gömülü EWM üretimde olabilir — LENVW='E' → EWM). Kaynak: EWM = `A_WarehouseAvailableStock`
  (depo numarası anahtarlı; plant/depo yeri YOK → lgnum↔lgort ters eşleme), MM = `I_MaterialStock` (InventoryStockType='01',
  SDDocument=''). ⚠ `I_MaterialStock` deprecated olabilir → halef / analitik küp DEV'de teyit.
- **MEVCUT SİSTEMDE BAK:** toplama view üçlüsü deseni (lokasyon bazında STOK + SEVK EDİLEN + TESLİM EDİLEN; Material + Plant +
  StorageLocation) + boş depo yeri (lgort='') → Plant toplamı yedeği. Böyle view'lar VARSA **reuse et**, yeni yazma.
- **FORMÜL DERSİ (kritik):** `Kullanılabilir = Stok − (SE tahsisi − mal çıkışı yapılmış teslimat)`. Naif `Stok − Sevk edilen`
  mal çıkışı sonrası stoğu OLDUĞUNDAN AZ gösterir (hata) → teslimatı geri ekleyen 3. terim ŞART.
- **TUZAK:** BE-44 — set tabanlı SUM'da örtük DISTINCT eksik sayım · BE-45 — kalem view'ında ilişki türevli join anahtarı → SDDL 515/061 (ileride eşlenecek).
- **SORU:** özel stok E (SDDocument≠'') dahil mi hariç mi? Plant mı Plant+depo yeri mi? (havuz semantiği çift sayım riski).

### T-SD-2 · "tutar / fiyat / döviz / bakiye" → FİYATLANDIRMA + PARA BİRİMİ
- **ARAŞTIR:** çok para birimli mi? Kur tipi parametreli mi? CDS `currency_conversion(p_kur_tipi)`.
- **MEVCUT SİSTEMDE BAK:** 3 katmanlı analitik CDS + currency_conversion deseni varsa reuse.
- **TUZAK:** `currency_conversion error_handling => #SET_TO_NULL` bazı derleyici sürümlerinde YOK → **TCURR kur bakımı operasyonel
  ön koşul** (yoksa çalışma zamanı dump'ı) · BE-32 — UNIT/CUKY kolonunda max/min/sum reddi → GROUP BY · BE-04 / FE-28 — decimal'i
  API gövdesine `WRITE ... TO` ile yazmak → Edm.Decimal 400 (ileride eşlenecek).
- **SORU:** hangi kur tipi? Bazı belge tiplerinde (parça siparişi / ihracat) FİYAT YOK → sipariş fiyatını kullanma; bakiye = sipariş miktarı − Σ sevk.

### T-SD-3 · "teslimat / mal çıkışı (GI) / sevkiyat" → TESLİMAT
- **ARAŞTIR:** SE kaynaklı teslimat ayracı (ZZ1 append alanı `<0>` değil) + mal çıkışı durumu `LIPS.wbsta='C'`; teslimat NET = ileri − iade.
- **MEVCUT SİSTEMDE BAK:** tipten bağımsız sevkiyat havuzu + teslimat API cephesi varsa reuse; teslimat yaratma released API → BAPI.
- **TUZAK:** teslimat partisi BOŞ çalışır (SAP belirler — güvenli) · standart kaydetme exit'i (MV50AFZZ) yalnız Z include ile (Yasak A) ·
  `MARM` alternatif ölçü birimi (ST↔PAK) eksikse teslimat OLUŞMAZ (test ön koşulu).
- **UYUYAN KONTROL uyarısı:** canlıda SE bağlı teslimat yoksa teslim miktarı=0 → kontrol uyur; spekülatif engelleyici YAPMA, veri gelince devreye girer.

### T-SD-4 · "ambalajlama / kasa / paketleme adedi" → AMBALAJ (LE-PAC)
- **ARAŞTIR:** ambalajlama talimatı içeriği vs belirlemesi; koşul tekniği. İçerik = released `I_PackingInstructionHeader/_Component`;
  belirleme = FM `VHUPIBAPI_PACK_INST_FIND` (KAPPL=PO).
- **MEVCUT SİSTEMDE BAK:** hibrit belirleme (FM → CreationDate MAX → boş) + BİR KEZ belirle (liste yüklemede tekilleştir + önbellek) deseni varsa reuse.
- **TUZAK:** koşul tekniğini CDS'te TAKLİT ETME (kırılgan) → FM · satış birimi ≠ temel birim → kasa boş (MARM çevrimi) ·
  FE-35 — miktar düz birleştirme QUAN sondaki sıfırlar "14.000 ADT" → birim-ondalık biçimleyici (ileride eşlenecek).

### T-SD-5 · "termin / açık miktar / sipariş bakiyesi" → TERMİNLEME
- **ARAŞTIR:** teslimat planı termin satırı (`I_SalesSchedgAgrmtSchedLine`), ETTYP filtresi (yalnız kesin?), FIFO tüketim MBDAT ≤ bugün+N.
- **MEVCUT SİSTEMDE BAK:** açık miktar motoru (`açık = max(0, sipariş miktarı − teslim − Σ SE açık)`) + RAP cephe function import varsa
  reuse; motor tip parametreli olmalı (sabit kodlama ETME).
- **TUZAK:** fazla teslimat toleransı → üst sınır = termin × (1 + UEBTO%) · BE-29 — açık miktar COLLECT hedefinde anahtar olmayan CHAR →
  aktivasyon reddi (ileride eşlenecek) · 30 gün mükerrer parti elemesi tipe özgü (genel varsayma).

### T-SD-6 · "konteyner / kapasite / brüt ağırlık" → KAPASİTE
- **ARAŞTIR:** konteyner tipi standart VTADD02'de → kapasite oraya KONAMAZ (Yasak A) → Z tabloya eşle.
- **MEVCUT SİSTEMDE BAK:** Z kapasite tablosu + Σ teslimat brüt (`LIKP.BTGEW`) GROUP BY (gewei) kıyası + yumuşak uyarı deseni varsa reuse.
- **TUZAK:** BE-32 — `max(gewei)` UNIT aggregate reddi → GROUP BY (ileride eşlenecek) · **blast-radius:** kapasite alanı eklemek =
  paketler arası where-used ŞART (net ağırlık/hacim tüketicileri).

### T-SD-7 · "müşteri blok / kredi / teslimat bloğu" → MUHATAP BLOK
- **ARAŞTIR:** blok bayrakları BUT000-XBLCK + KNA1/KNVV-AUFSD + LIFSD; muhataplar AG/WE/RE/RG tekil.
- **MEVCUT SİSTEMDE BAK:** yeniden kullanılabilir muhatap blok kontrolü (I_Customer / I_CustomerSalesArea / I_BusinessPartner) varsa reuse; ham tablo YASAK.
- **TUZAK:** **KNVV blokları bölüm anahtarlıdır** → çağıran spart'ı vermezse AUFSD/LIFSD SESSİZCE atlanır (bölüm = vbak.spart ZORUNLU) ·
  BE-19 — BU_PARTNER ≠ KUNNR (CVI) → genel BP ad join'i boş/yanlış; KUNNR → I_Customer (ileride eşlenecek) ·
  ⚠ blok kontrolünü `VBAK`'tan `#CHECK`'li bir released CDS'e taşımak DCL yüzünden 0 satır → "blok yok" = fail-open riski; geçmeden önce ölç.

---

## SORULACAK (belirsizse DUR — belirsizlikle orantılı; makul varsayılanda varsay ve bildir)
1. **Satış organizasyonu / dağıtım kanalı / bölüm (vkorg/vtweg/spart) + belge türü (auart) kırılımı?** — yapılandırma anahtarı buna bağlı;
   iki akış aynı vkorg+vtweg+auart'ı paylaşıp yalnız **SPART** ile ayrışabilir (yapılandırma çakışması tuzağı, BE-43 — ileride eşlenecek).
2. **Özel stok E dahil mi hariç mi?** — kullanılabilirlik formülünü değiştirir.
3. **Stok kırılımı Plant mı Plant+depo yeri mi? Boş depo yeri davranışı?**
4. **EWM mi IM/MM mi (depo yeri bazında)?** — stok CDS kaynağını belirler.
5. **Bakiye/açık miktar teslimat bazlı mı sipariş bazlı mı?** — CDS'ten teyitli al.
6. **Fazla teslimat toleransı (UEBTO) üst sınıra dahil mi?**
7. **Fiyat/tutar var mı (sipariş vs teslimat planı vs ihracat)?** — yoksa sipariş fiyatını kullanma.
8. **Çok para birimli mi + hangi kur tipi?** — TCURR bakım ön koşulu.
9. **Blok kontrolü hangi muhataplar + hangi kapılar (yaratma / teslimat)?**
10. **Değiştirmede kendini hariç tutma mantığı?** — bakiye/kapasitede düzenlenen belge kendisi hariç mi.

---

## KAYNAK İŞARETÇİSİ (3 eksen araştırmada nereye bakılır)
- **Domain / sözdizimi / annotation** → resmi ABAP/CDS referansı + released API taraması (kaynak yoksa "DOĞRULANMADI").
- **Canlı sistem** → `%sap-adt-foundation`: `adt_where_used` + `adt_package_contents` (harita) → `adt_get` (derin) + `adt_sql_query` / `adt_table_read` (KVKK kuralına dikkat).
- **Proje kuralı / istisna** → proje `AGENTS.md` + `.axet-code/memory/`.
- **Benzer çözülmüş iş (prior-art)** → proje hafızası + önceki `.axet-code/intake/` artefaktları + ekip `memory/` (Z obje ise CANLI DOĞRULA).
- **Teknik tip (RAP/klasik/UI5)** → ilgili SAP skill'leri (dik eksen).

---

## ÇIKARILAN DERSLER (SD'ye özgü)
Yukarıdaki tetiklere gömülü tuzaklar + kod inceleme checklist'inin SD domain maddeleri: BE-04, BE-19, BE-26, BE-29, BE-32, BE-43,
BE-44, BE-45, BE-46 ve FE-27, FE-28, FE-35 (hepsi **ileride eşlenecek**; şimdilik `%code-review`). Yeni SD dersi öğrenilince buraya
satır ekle. Standart belge yazımı daima released API → BAPI → RFC FM → BDC → manuel (`%sap-dev` → `references/write-api-selection.md`); RAP handler'da commit'li BAPI ayrı LUW (BE-26).
