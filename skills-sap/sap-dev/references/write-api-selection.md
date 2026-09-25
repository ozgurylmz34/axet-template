# Standart veriye yazma — API seçimi karar ağacı

> **Kapsam:** SAP **standart iş nesnesine** create / update / delete / action (satış belgesi, teslimat, fatura, iş ortağı,
> malzeme …). Z tabloya yazma kapsam DIŞI (managed RAP — `%sap-rap` layering-and-bdef.md). **Okuma kapsam DIŞI** — okumada
> released CDS tercih edilir: `%sap-code-review` clean-core.md §3 (`released_successors.py lookup` + `adt_search_objects` + `adt_get`).
>
> **Zemin — kesin yasak B** (SAP çekirdeği `core/sap/00-sap.md`, proje `AGENTS.md` damgası): standart tabloya doğrudan
> `INSERT/UPDATE/DELETE/MODIFY` yok; izinli yollar **sıralı** aranır. Bu dosya o sıranın ayrıntısıdır.
>
> **Neden ağaç:** yolları doğru sırada bilmek yetmiyor. Seçimi bozan tuzaklar (operasyon kapalı · metin kalıcı yazılmıyor ·
> handler'da commit dump'ı · key-user alanı sessizce düşüyor) **aktivasyonda ya da yalnız çalışma zamanında** görünür.
> Ağaç bunları seçim anına taşır. Komutlar: `cli <araç> '<json>'` =
> `python <TEMPLATE>/skills-sap/sap-adt-foundation/scripts/sap_adt_cli.py <araç> --args-json '<json>' --project-dir <PROJE_KÖKÜ>`.

## ADIM 0 — Kod hangi bağlamda koşuyor? *(seçimden ÖNCE; commit kuralını bu belirler)*

| Bağlam | Commit kimde | Ayrıntı |
|---|---|---|
| **RAP behavior handler / action** (kendi BO'n — managed, unmanaged, façade) | **Framework.** `COMMIT ENTITIES` · `COMMIT WORK` · `BAPI_TRANSACTION_COMMIT` · örtük commit (`WAIT UP TO`) yok → `BEHAVIOR_ILLEGAL_STATEMENT`. Commit'li BAPI/FM **ayrı LUW**'da (Z RFC-enabled sarmalayıcı) | `%sap-rap` behavior-impl.md §10 · `%sap-code-review` BE-26 / BE-76 |
| **Klasik rapor / dynpro / job** (RAP *tüketicisi*) | **Sende.** `COMMIT ENTITIES` (EML) ya da `BAPI_TRANSACTION_COMMIT` (BAPI) zorunlu; sonra okumadan önce görünürlük kapısı | `%sap-rap` eml.md §2 · BE-73 |
| **SEGW DPC_EXT** | DPC içinde BAPI + commit/rollback | `%sap-odata-backend` dpc-crud.md §3 |
| **Side-by-side** (`btp_abap`) | Uzak released API (communication arrangement) | `%sap-adt-foundation` profiles.md |

Aynı yöntem (ör. EML) iki bağlamda **farklı** commit kuralı taşır. Başka bağlamdan örnek taşırken tek anlamlı fark genellikle
budur — ADIM 0'ı atlama.

## ADIM 1 — Released RAP BO var mı? → **EML** *(clean core seviye A)*

Nesne + operasyon için released bir RAP BO (`I_*TP`) varsa **ilk aday** budur. "Var" demek **dört CANLI teyit** ister —
hafıza, doküman ya da SAP Help yetmez:

| # | Teyit | aXet'te nasıl | Tutmazsa |
|---|---|---|---|
| 1a | BDEF canlıda var, release durumu uygun | Ad: `cli adt_search_objects '{"query":"I_<NESNE>*TP"}'` · BDEF: `cli adt_get '{"name":"<BO>","object_type":"bdef"}'` · release durumunun otoritesi ATC **"Usage of APIs"** (`adt_atc_check` — kendi tüketici objende, derlendikten sonra; varyant bu kontrolü içermeli, `%sap-code-review` clean-core.md §5). Regex/ad benzerliğiyle taklit edilmez | ADIM 2 → yoksa ADIM 3 |
| 1b | **İstenen operasyon AÇIK** | Aynı BDEF'te `use create` / `use update` / `use association … { create; }` satırı. ⚠ Satır **gerekli ama yeterli değil**: operasyon sistemde yine kapalı olabilir (*"operation UPDATE/CREATE is not activated for entity"*) ve bu yalnız aktivasyonda/çalışma zamanında görünür — önceden tespit eden ölçülmüş bir yöntem YOK ⇒ ilk gerçek create/update denemesi teyidin parçasıdır | BE-24 → ADIM 2 (released BAPI) → yoksa ADIM 3 (released OData) — ikisi de released katman, ADIM 4'ten ÖNCE |
| 1c | Gereken alanlar **yazılabilir** | BDEF'te `field ( readonly )` / `field ( suppress )` + projeksiyon CDS kaynağında `@ObjectModel.editableFieldFor` / `readonly` (`cli adt_get '{"name":"<PROJEKSIYON>","object_type":"ddls"}'`) | `%sap-rap` eml.md §5 (key'in `…ForEdit` karşılığı) |
| 1d | Bilinen boşluklar kontrol edildi | **metin:** RAP handler bağlamında (ölçülen: unmanaged static action) `CREATE BY \_Text` tamponda başarılı ama **kalıcı yazılmaz**; **varsayılan `SAVE_TEXT` de kalıcı yazmaz** → `SAVE_TEXT … savemode_direct = 'X'` ZORUNLU (sessiz veri kaybı: `sy-subrc = 0`, metin yok) · **late numbering:** handler'da numara senkron dönmez; klasik tüketicide `COMMIT ENTITIES BEGIN … END` + `CONVERT KEY` · **muhatap:** standart muhataplar otomatik belirlenir, elle ekleme dump/`VPD 030` üretir; mevcut belgeye `CREATE BY \_assoc` rolü boş bırakabilir | `%sap-rap` eml.md §2 · §4-5 · §8 · BE-08 |

- `REPORTED`'daki **tüm** hata mesajları yüzeye çıkarılır (BE-53).
- Tampon başarısı (`FAILED` boş, `sy-subrc = 0`, HTTP 200) **kalıcılık kanıtı DEĞİLDİR** → geri oku (READ ENTITIES ya da işlem kodu).

## ADIM 2 — Released klasik API: **BAPI / FM** *(seviye B)*

EML yoksa ya da 1a-1d'den biri tutmadıysa. Sınıflandırmanın otoritesi yine ATC "Usage of APIs".
- İpucu (otorite değil): `python <TEMPLATE>/skills-sap/sap-code-review/scripts/released_successors.py lookup <BAPI_ADI>` —
  haritada varsa release edilmemiş ve halefi yazılıdır; **haritada yok ≠ released**.
- Key-user (özel alan) alanları → `CL_CFD_BAPI_MAPPING` (BE-37). Ham yapı imajı **sessizce yok sayılır**: belge yaratılır, alan boş kalır.
- `RETURN` (`BAPIRET2`) içindeki **tüm** E/A/X satırları yüzeye çıkar; kimlik taşıyan satır çözülür (BE-74).
- Boş göndermek ≠ hiç göndermemek: X-bayraklı yapılarda yalnız değişen alan işaretlenir.

## ADIM 3 — Released OData API (`API_*_SRV`) — **yalnız şu durumlarda**

Kesin yasak B'deki "released API" katmanının üçüncü biçimidir (EML ve released BAPI ile birlikte); iş mantığından geçer.
Released RAP BO (EML) ve **released** BAPI'nin ardından, **release edilmemiş** BAPI/FM'den (ADIM 4) ÖNCE gelir:
- ADIM 1 teyitlerinden biri tutmazsa (1a-1d: BO yok · operasyon kapalı · alan yazılamıyor · boşluk çözülemiyor) **VE**
  released BAPI yoksa (ADIM 2) — ya da uzak tüketimde.
- Aynı sistemde iç çağrı **iç gateway proxy** ile yapılır; SM59/RFC destination eski yoldur (`%sap-odata-backend` outbound-api-call.md §1).
- Yerel bağlamda (klasik GUI, job, SEGW DPC_EXT, RAP handler) EML ya da **released** BAPI varken **seçilmez** — aynı BO'ya HTTP
  katmanı eklemek gereksiz karmaşadır. Release edilmemiş bir BAPI OData'nın önüne **geçmez** (o ADIM 4'tür): elde yalnız release
  edilmemiş BAPI + released OData varsa OData seçilir; "HTTP katmanı karmaşası" bu durumda gerekçe DEĞİLDİR.
- **OData teyidi (1b/1c karşılığı):** `$metadata`'da EntitySet üzerinde `sap:creatable="false"` / `sap:updatable="false"` **YOKSA**
  operasyon açıktır (varsayılan true; `="true"` diye aranmaz); gereken alan için aynı öznitelik `Property` üzerinde aranır.
  Kaynakta ölçüldü (bir S/4 private DEV, `API_SALES_ORDER_SRV`): `="true"` 0 kez, `="false"` 250+ kez. ⚠ **aXet CLI'de `$metadata`
  okuma aracı YOK** → kullanıcı tarayıcıda açar, ilgili `EntitySet` / `EntityType` bloğunu paylaşır; arama tip-kapsamlı yapılır
  (`%sap-adt-foundation` foundation-query.md §5.1). Metadata açık ≠ yazıyor: ilk gerçek çağrı + geri okuma teyidin parçasıdır.
- ADIM 4'e yalnız OData'nın kendi teyidi tutmazsa inilir; iniş TS'e yazılır (aşağıda).

## ADIM 4 — Released OLMAYAN ama resmi BAPI / FM — RFC-enabled ya da değil *(seviye C)*

- Gerekçe TS'e yazılır. `cleancore_policy: strict` ve `s4_public`'te **kapalı**.
- ⛔ **İç FM API değildir.** Tanım (ölçülebilir): ATC "Usage of APIs"ta released/klasik API olarak sınıflandırılmamış **VE** aynı işi
  yapan bir BAPI'nin altında çağrılan FM. BAPI'nin kontrollerinin bir kısmını atlayabilir → seçilmez; üstündeki BAPI kullanılır.
  Üstünde BAPI var mı: `cli adt_where_used '{"name":"<FM>","object_type":"func"}'` + `CROSS` sorgusu (pozitif kontrollü —
  `%sap-adt-foundation` foundation-query.md §3.3). Örnek `SD_SALESDOCUMENT_CREATE` (`BAPI_SALESORDER_CREATEFROMDAT2`'nin altında) —
  sınıflandırması **DOĞRULANMADI** (bir proje araştırmasının değerlendirmesi; ATC ile ölçülmedi). Üstünde BAPI olmayan resmi FM'ler
  bu tanıma girmez; ADIM 4'ün asıl konusudur — sınıfı ATC ile ölçülür.
- **Update modülü** (`IN UPDATE TASK` için yazılmış; FM metadata'sında `processingType="update"`) resmi FM sayılmaz → seçilmez.
- **RFC-enabled OLMAYAN resmi FM de ADIM 4'tedir.** Ayrı LUW / commit gerekiyorsa (RAP handler — BE-26) **Z RFC-enabled
  sarmalayıcı** ile çağrılır; `DESTINATION 'NONE'` ile doğrudan çağrılamaz (remote-enabled değil → çalışma zamanında
  `CALL_FUNCTION_NOT_REMOTE`; ekip kaydı: `%sap-rap` → `references/behavior-impl.md` §10 tuzak (a), bu FM ile ayrıca ölçülmedi). Örnek `SD_SCDS_CREATE` — kaynakta canlı ölçüm (bir S/4 private DEV): `processingType="normal"`
  (RFC değil), `releaseState="notReleased"`; where-used'da üstünde BAPI yok; ATC sınıfı ölçülmedi.
- FM'in `processingType` / `releaseState` değeri: `cli adt_get '{"name":"<FM>","object_type":"function","include_source":false}'` →
  yanıttaki `metadata` ham XML'inde okunur (aXet'te bu özniteliklerin döndüğü canlı **ÖLÇÜLMEDİ** — yoksa "ölçülemedi" yaz, uydurma).
  ⚠ SE37'deki `releaseState="external"` ≠ ATC/ARS released: yalnız `external` bayrağı bir FM'i ADIM 2 yapmaz.

## ADIM 5 — BDC (işlem kodu) · ADIM 6 — kullanıcıdan manuel

BDC ekran bağımlıdır, yavaştır, hata yakalaması zordur → son çare. ADIM 6'ya gelindiyse **akış dışı çözüm icat edilmez**
(doğrudan SQL, iş mantığını atlayan yol) — kullanıcıya bildir, manuel yapmasını iste.

### ⛔ HİÇBİR ZAMAN
- Standart tabloya SQL (`INSERT/UPDATE/DELETE/MODIFY`) — Z'li programda bile (yazma kapısı `ADR_0005_B` ile reddeder).
- Standart tabloya managed Z BO üzerinden `MODIFY ENTITIES`.
- İş mantığını atlayan iç FM (ADIM 4 ⛔).
- Standart update modülünü doğrudan `CALL FUNCTION … IN UPDATE TASK` ile çağırmak.

## Profil ayarı *(`sap-project.json` → `sap_profile` + `cleancore_policy`; matris rehberdir, hücreler canlı testle doğrulanır)*

| `sap_profile` / `cleancore_policy` | Uygulanan adımlar | Durum |
|---|---|---|
| `s4_private` + `balanced` / `classic` | 1 · 2 · 3 · 4 · 5 · 6 (tam zincir) | ADIM 1 kaynakta ölçüldü (satış siparişi, `balanced`); BAPI yolu (`BAPI_SALESORDER_CREATEFROMDAT2`) canlı çalıştı ama sınıfı — ADIM 2 mi 4 mü — ATC ile ölçülmedi (⚠ SE37 `external` ≠ released); ADIM 3-6 ve `classic` ölçülmedi |
| `s4_private` + `strict` | 1 · 2 (yalnız released) · 3 · 6 — **4 kapalı**; 5 (BDC) matriste açıkça yok → kullanmadan önce sor | matristen (yalnız released API), ölçülmedi |
| `s4_public` | 1 · 2 (yalnız released) · 3 · 6 — **4 ve 5 kapalı** (klasik rapor/batch-input yasak) | matristen (platform zorlar), ölçülmedi |
| `btp_abap` | 3 (uzak released API) · 6 — yerel S/4 objesi yok, klasik yollar kapalı | matristen, ölçülmedi |
| `ecc` | 2 (BAPI) · 4 · 5 · 6 — released kavramı yok | matristen, ölçülmedi |
| alan boş / tanımsız | ÖLÇÜLEMEZ → kullanıcıya sor, adım seçme | — |

## Gerekçenin yazılacağı yer (MUST)

Standart nesneye yazan her geliştirmenin TS'inde **"API seçimi"** alt bölümü bulunur (`%sap-fs-ts-docs` TS şablonu §6.4):

| Yöntem | Sistemde? (canlı) | Released? | Commit (ADIM 0 bağlamında) | Hata yönetimi | Karar |
|---|---|---|---|---|---|
| EML `I_…TP` | 1a-1d sonucu | … | … | … | ★ seçilen / reddedildi: neden |
| BAPI `BAPI_…` | … | … | … | … | … |
| OData / FM / BDC | … | … | … | … | … |

Ek olarak clean core seviyesi (A/B/C/D — `%sap-code-review` clean-core.md §2). **Reddedilen alternatif ve nedeni yazılmadan
seçim tamamlanmış sayılmaz** — sonraki geliştirici aynı araştırmayı baştan yapar. TS yoksa (S0/S1) aynı tablo kullanıcıya
sunulur ve paket `SESSION_NOTES.md`'ye yazılır.

## Sınırlar (kapsam beyanı)

- "EML önce" sırasının canlı kanıtı **satış siparişidir** (`I_SalesOrderTP` ile gerçek belge yaratıldı; aynı iş için BAPI da
  canlı çalıştı). Teslimat, fatura, MM, FI nesnelerinde released BO'nun operasyon/alan kapsamının eksiksiz olduğu **ölçülmedi** ⇒
  ağaç *"önce EML'i TEYİT et"* der, *"EML zorunlu"* demez. Teyit tutmazsa ADIM 2'ye inmek kural ihlali değil, kuralın kendisidir.
- Bu ağaç yeni bir kapı açmaz. Zorlama: TS şablonu + `%sap-code-review` yargısı (BE-24 · BE-26 · BE-37 · BE-79). Yazma kapısı
  yalnız doğrudan standart tablo DML'ini yakalar (`ADR_0005_B`); **yanlış API seçimini yakalamaz**.
- aXet'te karşılığı olmayan teyitler: OData `$metadata` okuma (kullanıcıdan) · 1b "operasyon açık mı"nın önceden ölçümü (yöntem yok;
  ilk deneme) · ATC "Usage of APIs" ancak derlenmiş tüketici objede koşar (yazmadan önce ad düzeyinde otorite yok).

## İlgili
- `%sap-rap` — eml.md (I_SalesOrderTP reçetesi: tüketici bağlamında COMMIT, `CONVERT KEY`, iki aşamalı FAILED kontrolü, muhatap,
  metin) · behavior-impl.md §10-11 (ayrı LUW, handler'dan OData) · layering-and-bdef.md (şekil seçimi)
- `%sap-odata-backend` — dpc-crud.md §3 (klasik DPC_EXT'te yazma) · outbound-api-call.md (iç gateway proxy)
- `%sap-code-review` — checklist-rap.md (BE-08 · BE-24 · BE-26 · BE-53) · checklist-abap.md (BE-37 · BE-73 · BE-74 · BE-76 · BE-79) · clean-core.md
- `%sap-intake-triage` — references/modules/sd.md SD-K3/K5 (SD'ye özgü BAPI örnekleri)
