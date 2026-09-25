# CDS view (DDLS) — yaratma, güncelleme, sözdizimi ve aktivasyon tuzakları

> Kaynak: ekip ADT playbook'unun CDS bölümü + CDS kontrol listesi + ilgili ekip dersleri; aXet CLI'ye uyarlandı.
> ADT protokolünün geneli (pull-before-edit, yazma kapısı, 409, aktivasyon doğrulaması): `%sap-adt-foundation`.
> **Okuma kuralı:** "ÇALIŞAN" ve "DENENEN — BAŞARISIZ" satırları ölçülmüş deneyimdir. Parantez içindeki niteleyici
> ("bu sistemde", "iki biçim reddedildi") iddianın sınırıdır; genişletme. REST akışları teşhis ve araç aktarımı içindir.
> Örnek adlar nötr demodur (`ZSD001_*`); kaynak ölçümler S/4HANA (`s4_private`) sistemlerde yapıldı.

---

## 1. CLI yolu

### 1.1 Önce türe bak
- Kaynakta `as select from` / `union` var mı? → **view** (classic `define view` ya da `define [root] view entity`).
- SELECT yok (action parametresi/sonucu) → **abstract entity** (`define [root] abstract entity`).
- Aracı tahminle seçme; tür, hangi kurallar (§3) ve hangi doğrulama (§1.5) geçerli olduğunu belirler.

### 1.2 Yeni CDS — kabuk `adt_post_shell` `ddls`
**CLI yolu (2026-09-13; çevrimdışı test edildi, canlı DOĞRULANMADI):** `adt_post_shell` `object_type=ddls` yalnız **metadata
kabuğu** açar, kaynak gövdeye konmaz (§1.3 tuzağıyla uyumlu) → kaynak ayrı adımda yazılır (`%sap-adt-foundation` →
`tool-catalog.md` → `adt_post_shell`). Toplu yaratma aracı yoktur (önceki araç setindeki `populate_cds_views.py` alınmadı).

1. `cli adt_post_shell '{"object_type":"ddls","name":"ZSD001_I_ORDER","package":"<PAKET>","transport":"<TRANSPORT>","description":"<master_language metni>"}' --sap-write --scope S1 --reason "..."`
   → `ok:false` ise retry etmeden `exists_after`'a bak; `create_not_persisted` = 2xx döndü ama obje yok.
   Araç reddederse ya da canlıda düşerse ara yol: kullanıcı Eclipse ADT'de boş Data Definition'ı doğru pakette, doğru transportla,
   `master_language`'de açar.
2. `cli adt_get '{"name":"ZSD001_I_ORDER","object_type":"ddls"}'` → `exists:true`, `pull_state: kaydedildi`.
3. `cli adt_push_source '{"name":"ZSD001_I_ORDER","object_type":"ddls","source":"<tam kaynak>","transport":"<TRANSPORT>"}' --sap-write --scope S1 --reason "..."`
   (uzun kaynakta `--args-file`).
4. `cli adt_activate '{"name":"ZSD001_I_ORDER","object_type":"ddls"}' --sap-write ...` (bağımlılar `also` ile, §4 T11).
5. Doğrula (§1.5).

**DENENEN — BAŞARISIZ (tekrarlama):**

| Deneme | Sonuç | Neden |
|---|---|---|
| Push, kabuk yokken | `[423] not locked` | push mevcut obje ister |
| `adt_post_shell` `ddls` (önceki araç seti) | `Unsupported object type: DDLS/DF` | kabuk aracı DDLS yaratmıyordu (aXet CLI'de yalnız-metadata yolu eklendi, §1.2) |
| Eski `create_cds_view` yardımcı fonksiyonu | CSRF "Unknown error" · gövdedeki kaynak yok sayıldı | bu sistemde gövde kaynağı işlenmiyor (§1.3) |

**Protokol notu (araç aktarımı / teşhis):** kabuk `POST /sap/bc/adt/ddic/ddl/sources?corrNr=<TRANSPORT>`
(`/ddlsources` → 404), `Content-Type: application/vnd.sap.adt.ddlSource+xml` (v2 değil), gövdede `adtcore:masterLanguage`,
`adtcore:packageRef`, `ddl:sourceMainArtifact`; taze CSRF. Kaynak ayrı adımda: kilit → `PUT .../ddl/sources/<ad>/source/main`
(`text/plain`) → kilidi bırak → `POST /sap/bc/adt/activation` (`DDLS/DF`). `201` = kabuk var; `409`/`AlreadyExists` = obje var, push'a geç.

### 1.3 Inline kaynaklı POST yalnız KABUK sayılır
- Kabuk POST'unun XML'ine `<ddl:source>` gömülse bile kaynağın dolduğunu varsayma.
  Ölçüm (S/4HANA 2025, 11 obje): gömülü kaynakla `201 CREATED`, aktif kaynak **0 karakter**; toplu aktivasyon
  `SDDL_PARSER_MSG 013 "The DDIC source code does not contain a valid definition"` ile düştü. Kontrol grubu: aynı turda
  inline POST tek başına 0/11 doldurdu, ayrı kaynak yazımıyla 11/11 doldu ve sha256 eşitliği doğrulandı.
  Sınır: önceki bir turun hangi sistemde koştuğu kayıtlı değil → "davranış değişti" mi "hep böyleydi" mi ayırt edilemedi; iddia ölçülen sisteme dairdir.
- Çoklu (kök + çocuk) CDS'te çocuklar `source=""` kalabilir; `200` = "obje var", "kaynak dolu/geçerli" değildir.
  Boş çocuk aktif görünür, bağımlı behavior definition saatler sonra `Type <X> is unknown` ile patlar.

### 1.4 XML kaçışı ve opak hata
- Kaynağı kabuk XML'ine kaçışsız gömmek `<>`, `<`, `&` içeren kaynakta XML'i bozar → SAP reddeder → retry sarmalayıcısı
  gerçek hatayı "Request failed after 3 retries: Unknown error" diye gizler → obje yaratılmaz → push `[423] not locked`.
  `<>` içermeyen view'lar bu yüzden "çalışıyordu". Kaynak ucu (`text/plain`) bu sorunu yaşamaz.
- **Opak hatada yöntem değiştirme:** önce ham durum kodunu ve gövdeyi oku (CLI'de `client_log`, `error.message`).
  Kabuk → minimal kabuk → başka araç diye dolaşmak zaman kaybıydı; gerçek sebep gövdede yazıyordu.

### 1.5 Doğrulama
1. `cli adt_get '{"name":"<AD>","object_type":"ddls"}'` → kaynak dolu, `define` satırı var, beklenen tür
   (abstract entity'de `abstract entity` geçmeli), gönderilenle içerik eşit (CRLF/son satır sonu normalize).
2. `cli adt_inactive_objects` → obje ve bağımlıları (üst view, BDEF, servis bağlaması) listede değil.
3. Classic view'da da view entity'de de `adt_sql_query` ile `SELECT COUNT(*) AS cnt FROM <SQL_VIEW>` → veri olan kapsamda 0
   değil; view miktar okuyorsa ayrıca aynı süzgeçli Open SQL kontrol grubuyla **miktar toplamını** kıyasla (§2 NSDM — satır
   var ama miktar 0 biçimi `COUNT(*)`'ı geçer).
4. Toplu bir araç "zaten var, atlandı" deyip çıkış kodu 0 verebilir (önceki araç setinde ölçüldü: "1 başarılı, 0 hatalı",
   hiçbir şey yazılmamıştı) → çıkış kodu değil **readback** kanıttır.

---

## 2. Sessiz-yanlış-sonuç sınıfı (aktivasyon geçer, veri yanlış)

### CDS-DCL-01 · Standart CDS'ten doğrudan okuma: yetki reddi 0 satır döner, hata vermez (S/4)
- `@AccessControl.authorizationCheck: #CHECK` taşıyan **standart** view'a **doğrudan** erişimde (ABAP `SELECT`,
  `READ ENTITIES`, service definition `expose`, OData `$expand`) yetkisiz kullanıcıda DCL sorguya
  `N'CDS_Access_Control' = N'DENY'` ekler → **0 satır**. `sy-subrc` "veri yok" der, exception yoktur; geniş yetkili
  geliştiricide hiç görünmez.
- **Sınır:** implicit access control yalnız **doğrudan erişimde** çalışır. Bir Z view'ın `FROM`/`JOIN`/`ASSOCIATION`'ında
  `#CHECK` standart view kullanmak tek başına risk değildir.
- **Çare — Open SQL (canlı derleyicide kanıtlandı):** kloz alias'tan ÖNCE gelir.
  ```abap
  SELECT ... FROM i_packinginstructioncomponent WITH PRIVILEGED ACCESS AS comp
         INNER JOIN i_packinginstructionheader WITH PRIVILEGED ACCESS AS hdr
                 ON hdr~packinginstruction = comp~packinginstruction
  " YANLIŞ: FROM i_packinginstructioncomponent AS comp WITH PRIVILEGED ACCESS  → parser_error / 400
  ```
- **Uygulanamadığı yerler (ölçüldü):** `READ ENTITIES` → böyle bir kloz yok · `@ObjectModel.virtualElement` alanları →
  privileged okuma BOŞ getirir (değer SQL'den değil hesaplama çıkışından gelir). Doğru yol: DCL taşımayan kaynak
  (DDIC tabloları DCL taşımaz; metin için `STXH`/`STXL` + `READ_TEXT`).
- "Hepsine toplu privileged" önerilmez: kontrolü kapatmak güvenlik kararıdır. Meşru olduğu tek durum: aynı veri zaten
  korunmasız başka yoldan okunuyorsa — iddia etme, **ölç**, gerekçeyi koda yaz.
- Doğrulama: aynı sorguyu kloz'lu/kloz'suz koş; **yetkili** kullanıcıda sonuç kümesi değişmemeli.

### CDS-DCL-02 · Released halefe geçiş fail-open üretebilir (karar kuralı)
- Ham DDIC tablo DCL taşımaz; released halefi taşıyabilir. Geçiş, DCL'siz okumayı DCL'li okumaya çevirir.
- Okunan veri bir **kontrol/guard** besliyorsa 0 satır "kontrol maddesi yok" okunur → **fail-open** (güvenlik kusuru).
  Ölçülmüş vaka: teslimat öncesi partner blok kontrolü ham satış belgesi tablosundan okuyordu; halef `I_SalesDocument`
  `#CHECK` taşıyordu (canlı okundu) → geçilseydi dar yetkili kullanıcıda bloklu partnere teslimat oluşurdu.
- **Sıra:** ① halefin `authorizationCheck` değerini canlı oku ② veri karar mı besliyor, görüntü mü ③ 0 satırda davranış
  fail-open mı fail-closed mı. `#CHECK` + guard ⇒ **geçme**, gerekçeyi koda yaz. `#NOT_REQUIRED` ise geçiş güvenli ve tercih edilir.
- Released disiplini **proaktiftir** (yazılan koda uygulanır); mevcut koddaki ham tablo kullanımı otomatik iş kalemi değildir —
  migrasyon proje politikası kararıdır.

### CDS-NSDM-01 · Replacement tablosu üzerine view: 0 satır ya da 0 miktar (S/4) — classic view VE view entity
- `@AbapCatalog.sqlViewName`'li classic view ya da SE11 view'ın `FROM`/`JOIN`'inde `DD02L-VIEWREF`'i dolu bir tablo
  (`MSEG`, `MKPF`, stok `MSSA` `MSSL` `MSSQ` `MSCD` `MSFD` `MSID` `MSKU` `MSLB` `MSPR`, değerleme `MBEW` `EBEW` `OBEW` `QBEW`
  `VMBEW` + tarihsel `*H`, `MARCH` `MARDH` `MCHBH` `MKOLH` …) **hatasız aktive olur ve 0 satır ya da 0 miktar döner** (biçim tabloya göre değişir — aşağıda).
- Neden: veri `MATDOC`'ta; Open SQL yönlendirmesi classic DB view'da çalışmaz, yönlendirme view'ın `DD25L-VIEWREF`'ine
  bağlıdır ve bu yalnız SAP'nin kendi view'larında doludur.
- ⛔ **View entity de bu tuzağa düşer** (eski metin "view entity'de bu sorun yoktur" diyordu; canlı ölçüm çürüttü):
  `MSKU` üzerine kurulu bir Z view entity `COUNT(*)=0` döndü; aynı süzgeçli Open SQL `msku` 3 satır getirdi; fiziksel
  tabloda anahtarlar vardı ama tüm miktarlar 0'dı ⇒ view entity de **fiziksel tabloyu** okur, Open SQL yönlendirmesinden
  geçmez.
- **Tuzağın biçimi tabloya göre değişir:** `MSEG`/`MKPF`'te fiziksel tablo **boş** (0 satır); `MSKU` gibi stok
  tablolarında **satırlar/anahtarlar var, miktar alanları 0** ⇒ `kulab > 0` gibi bir süzgeç sessizce 0 satır, süzgeçsiz
  okuma "stok 0" gösterir (daha sinsi).
- `MARA`/`MAKT` replacement değildir. ⛔ **`MARC` replacement'tır** (`DD02L-VIEWREF` dolu; eski metin "değildir" diyordu,
  canlı ölçümle çürüdü) — yalnız **stok/miktar alanları** etkilenir; ana veri alanları (ör. `STAWN`) fiziksel tabloda
  doğru okundu. Kural: replacement tablodan **miktar** okuyorsan aşağıdaki yola geç; ana veri okuyorsan satır kıyasıyla
  kanıtla, varsayma.
- **Yerine (classic view):** uyumluluk CDS'i — `mseg` → `nsdm_e_mseg` · `mkpf` → `nsdm_e_mkpf` (alan adları aynı;
  `sqlViewName`, alan listesi, key, WHERE değişmez → DB view yaşar → `USING` ile tüketen AMDP bozulmaz). View entity'ye
  çevirmek çözüm DEĞİLDİR: tuzak orada da var; üstelik view entity DB view üretmez, AMDP `USING` zincirini kırar.
- **Yerine (view entity):** released stok görünümü **`I_MaterialStock_2`** (hareket düzeyi ⇒ `group by` +
  `sum(MatlWrhsStkQtyInMatlBaseUnit)`; `InventorySpecialStockType`/`InventoryStockType` ile süz — ör. müşteri konsinyesi
  serbest = `'W'` + `'01'`) ya da `nsdm_e_*` (released DEĞİL — projenin clean core politikasına bak). Alan adlarını ve
  süzgeç değerlerini hedef sistemde `adt_get` / canlı veriyle teyit et.
- Tam liste: `SELECT tabname, viewref FROM dd02l WHERE as4local = 'A' AND viewref <> ''`.
- Teşhis: ① `dd02l` → replacement mı ② (yalnız classic view) `SELECT viewname, viewref FROM dd25l WHERE viewname = '<SQL_VIEW>'` → boşsa kusur bu
  ③ aynı tabloyu taşıyan tüm view'larda `COUNT(*)` + `DD25L-VIEWREF`. ⚠ Kontrol grubunda `VIEWREF`'i de ölç: "standart bir
  view satır döndürüyor" demek yanlış elemedir — onun `VIEWREF`'i doludur.
- Neden geç patlar: veri kapsamı boşken 0 doğru görünür; ilk gerçek veride çıkar. Aktivasyon, ATC, inaktif liste yakalamaz —
  tek kanıt satır saymak ve miktar okuyan view'da Open SQL kontrol grubuyla miktar toplamını kıyaslamak. Boş view'a `NOT EXISTS`/anti-join yapan sayaç ise **şişer**.

### CDS-NSDM-01 ek · Bilinen tuzak: çözüm seçimi ve etki taraması
- **Belirti:** replacement kusuru bulunduktan sonra ya veri doğrudan hedef tabloya inilerek okunur ya da "başka etkilenen Z view yok" denir.
- **Kök neden:** ① `matdoc`'u kayıt tipi / başlık sayacı alanlarıyla doğrudan okumak çalışır ama SAP'nin uyumluluk semantiğini
  elle taklit eder; SAP tabloyu genişletince sessizce kayar. ② Z view taraması `DD26S`'te tek `viewname LIKE 'Z%'` sorgusuyla
  yapılırsa satır sınırına `ZZ1_*` uzantı view'larıyla dayanır; kırpılmış tarama "başka yok" der.
- **Doğru yol:** uyumluluk CDS'i (`nsdm_e_*`, yukarıda). Taramayı tablo önekine göre böl (`tabname LIKE 'MS%'`, `'MB%'` …),
  `row_limit`'i açık ver ve her dilimde `row_count < row_limit` olduğunu göster (`%sap-adt-foundation` → `foundation-query.md` §1.1).
- Kaynak vaka: 2026-08-03.

### CDS-DCL-03 · Bilinen tuzak: DCL boşluğunu ölçerken ve düzeltirken gözden kaçanlar (S/4)
- **Belirti:** okuma hatasız; yetkili kullanıcıda dolu, dar yetkilide eksik. Üstelik bir kaydetmeden sonra dolu olan alan boşalmış.
- **Kök neden 1 — yazma yoluna bulaşma:** "oku → kullanıcı başka alanı değiştirir → hepsini geri yaz" deseninde okuma DCL yüzünden
  sessizce boş döndüyse geri yazma gerçek verinin üstüne boş yazar = geri alınamaz veri kaybı. Aynı sonucu frontend'deki bir
  `MERGE` de üretebilir (dolu alanı boş dizgeyle ezme).
- **Kök neden 2 — ölçüm tuzağı:** "boşluk kimde gerçek" sorusu test kullanıcısı gerektirmez: ilgili rollerin yetki değerleri ile veride
  görünen değerlerin kesişimi alınır. Org düzeyi alanlar (`VKORG`/`VTWEG`/`SPART`/`BUKRS` …) `AGR_1251`'de `$VKORG` gibi **yer tutucu**
  olarak durur; gerçek değer `AGR_1252`'dedir. Yalnız `AGR_1251` okunursa ölçüm "kısıt yok" ya da anlamsız çıkar ve yanlış kapanış
  verir. Rol tanımı ≠ atama: `AGR_PROF` + `UST04` ile profilin kullanıcıya fiilen atandığını da doğrula. Bu tablolar kullanıcı
  kimliği döndürür → QA/PRD'de hassas veri gibi davran (neden okunacağını söyle, onay al; kullanıcı adlarını rapora/hafızaya yazma).
- **Kök neden 3 — kırıklığın sınıfı:** tam red (yetki hiç yok → hep boş) ↔ kısmî red (org bazlı: bazı satırlar gelir, bazıları gelmez).
  Kısmî red tek kullanıcıyla yapılan testte yakalanmaz; "bazılarında veri yok" normal karşılanır.
- **Doğru yol:** ① doğrudan erişim noktalarını çıkar (ABAP `SELECT` · `READ ENTITIES` · SRVD `expose` · OData `$expand`) ② her birinde
  0 satır dalının ne yaptığını oku (sessizce mi geçiyor, ayırt edilebiliyor mu) ③ oku → geri yaz deseni var mı bak ④ çareyi noktasal
  seç (CDS-DCL-01), gerekçeyi koda yaz ⑤ kontrol grubuyla doğrula (CDS-DCL-01 son madde). `CATCH cx_root` ile sarıp "hata olmadı"
  sanma: DCL reddi exception atmaz.
- Kaynak vaka: 2026-08-11 (ambalajlama: mal çıkışında ambalaj hata vermeden oluşmadı; ST05 + SU53 ile ölçüldü) · 2026-08-14 (sevkiyat
  süreci: 5 doğrudan erişim noktası; sipariş notları okuma → geri yazma).

---

## 3. Başlık, adlandırma ve taşıma kuralları

### 3.1 Classic view başlığı
```
@AbapCatalog.sqlViewName: 'ZSD001_V_ORDDS'
@AbapCatalog.compiler.compareFilter: true
@AccessControl.authorizationCheck: #NOT_REQUIRED   // ya da #CHECK — §2
@EndUserText.label: '<master_language metni, spesifikasyondan>'
define view zsd001_ddl_order_destination as select from ...
```
- `@AbapCatalog.preserveKey` S/4'te deprecated (uyarı: `Annotation 'AbapCatalog.preserveKey' is deprecated`) → yeni view'da kullanma, taşırken kaldır.
- Diğer info seviyesindeki aktivasyon uyarıları normaldir.
- En az bir `key` alan; `sum()`/`count()` varsa `group by`.

### 3.2 `sqlViewName` ve view adı (ekibin kuralı; paket `.rules.md` farklıysa paket kazanır)
- `sqlViewName` = `<GÖVDE>_V_<1-5 büyük harf/rakam>`, **toplam ≤ 14 karakter** (`ZSD001_V_ORDDS`). Ön ek hedef paketten
  türer (`ZSD001_CLC` → `ZSD001_V_`); sabit değildir.
- Classic view adı `zsd001_ddl_<ad>`; view entity adı `Z<MOD><nnn>_<I|C|R|E>_<AD>` (`%sap-dev` → `naming.md` §4.3) ve
  **view entity'de `@AbapCatalog.sqlViewName` yasak** (view entity SQL view taşımaz).
- Eski kısaltma stili (`ZSD01SHTYP`, eski namespace ön eki) yasak. Pozitif kural yaz (tek doğru biçim), yasak listesi değil:
  negatif ifade edilen kural iki kez ihlal edildi.
- Abstract entity'de ad ile `{` arasına boşluk/satır sonu koy (`... entity ZSD001_I_PRM {`): bitişik yazımda ad kontrolü `{`'yi adın parçası sayar.
- ⛔ **İlk aktivasyonda doğru `sqlViewName`.** Aktive edilmiş `sqlViewName` yeniden adlandırılamaz (SAP Note 2710405).
  Kaynak düzeltilse de DB kataloğunda eski SQL view **yetim** kalır; aynı DDL'i yeni adla aktive etmek
  `SQL view <X> cannot be renamed` ile düşer. Workbench DELETE yetmez; temizlik DB seviyesindedir (SE14 "Delete from database"
  ya da `RSDDDDCDELOLD`) ve transport işlemi gerektirir → **tamamen kullanıcı işi** (kesin yasak C: model transport
  yaratmaz/release etmez). Ölçülen maliyet: 9 yetim view, saatlerce geriye dönük temizlik. "Sonra düzeltirim" diye geçici adla aktive etme.

### 3.3 Alan adı ≠ DTEL adı
Eski kaynaklarda alan adı DTEL adıyla karışmış olabilir: `T173.versart` ❌ (DTEL) · `T173.vsart` ✅ (alan). Şüphede tablo
yapısını `adt_get` `tabl` ile oku; eski sistemden kopyalanan standart alan adlarını hedef sistemde teyit et.

### 3.4 Eski sistemden taşıma
- Namespace dönüşümünü **regex ile** yap (`re.sub(r"\b<eski_ns>_ddl_", "zsd001_ddl_", src, flags=re.I)`); elle sözlük
  (`{'ESKİ_A': 'YENİ_A', ...}`) yanlıştır — atlanan girdi eski ön eki bırakır.
- Kontrol: `sqlViewName` biçim dışı dosya · view adı biçim dışı dosya · gövdede eski namespace literal'i → üçü de boş çıkmalı.
- Standart tablolara eski sistemde eklenmiş append alanlarının yeni adlarını **AI önermez**; kullanıcı verir (kesin yasak A).

---

## 4. Sözdizimi ve aktivasyon tuzakları

> Ortak ders: bu hataların çoğu statik incelemede ve `adt_syntax_check`'te görünmez, **yalnız aktivasyonda** çıkar.
> Aktivasyon ilk hatada durur → her tur tek bilinmezi kapatır; "diğerleri temiz" iddia edilemez.

**T3 · Salt-okunur tüketim = `as select from`, `as projection on` DEĞİL.**
`define view entity … as projection on <I_view>` → `Transactional Projection View must be part of a business object`
(projection = RAP transactional, BDEF ister). `define root … as projection on <kök olmayan>` → `ROOT keyword not valid`.
BO'suz lookup/rapor view'ında `root` ve `redirected to` da yok; çocuk `$expand` = yeniden bildirilen association.
`@Semantics` ve `@Metadata.allowExtensions` tüketim view'ında tekrar bildirilir.

**T4 · `union all` view entity — üç kuralı baştan uygula** (her biri ayrı aktivasyon turu yedirdi):
(a) WHERE'de `EXISTS`/`NOT EXISTS` alt sorgusu yok (`Unexpected keyword "exists"`) → `LEFT OUTER JOIN` + `WHERE <join>.key IS NULL`;
(b) element seviyesinde `@Semantics.*` **yalnız ilk dalda** (`Annotations are not allowed in this branch`);
(c) yayılabilir quantity/amount semantiği varsa başlıkta `@Metadata.ignorePropagatedAnnotations: true`.
Dallar alan sayısı/sıra/tip bakımından birebir (literal cast'lerle hizala).

**T5 · Conversion exit'li alan OData'ya açılınca yayın düşer.**
`Do not use conversion exit <EXIT> for property <FIELD>` (ör. `/scwm/de_huident`, kur alanları). **Salt-okunur** alanda
`cast( <alan> as abap.char(<n>) )` ile exit düşer (union'da iki dalda da). **Yazılabilir** alanda cast yasak (cast'li element
hesaplanmış olur, eşlenemez/yazılamaz) → tek temiz yol alanın exit'siz Z DTEL'e çevrilmesi (tablo değişikliği + kullanıcı onaylı DTEL adı — `%sap-dev` §6).

**T6 · JOIN'de kullanılan alanı silme/rename → üç adımlı geçiş.**
Belirti: `Field <SQLVIEW>-X is still being used in join of <TÜKETİCİ>`; atomik ortak aktivasyon da `column <Y> is unknown`.
Çare (her adım tek obje aktivasyonu): ① A'ya yeni alan Y'yi **ekle** (X kalır) ② tüketici B'nin JOIN'ini Y'ye çevir
③ A'dan X'i sil. Aynı sınıf: alt view'ın **key**'ini değiştirip tüketici JOIN'ini aynı turda değiştirmek atomik
aktive edilemez → iki faz (ekle+aktive → tüketiciyi çevir+aktive → ayrı turda eskiyi kaldır).

**T7 · `CASE WHEN`'de sol taraftaki aritmetik parantezle sarılmaz.**
`when ( a - b ) <= 0` → aktivasyonda `Unexpected word ')'` (`adt_syntax_check` `valid:true` dediği hâlde) · `when a - b <= 0` → çalışır.

**T8 · JOIN ON'da `cast()`/fonksiyon → ön-cast köprü view + `lpad`.**
Sol operandda cast: `Expression type FUNCTION not allowed in expression context COMPARISON, clause type COMP_LEFT`; sağ operandda
da garanti değil (çevrilmiş biçim canlı ölçülmedi). Çalışan: alt view değeri hazır kolon olarak versin, ana view düz join etsin.
İkinci tuzak: `numc(4)` → `numc(6)` cast'i `CAST NUMC ... lengths must match` → `cast( lpad( <alan>, 6, '0' ) as abap.numc(6) )`
(önce eşit uzunluk karakter, sonra cast). Eski sistemdeki SE11 view çevrimi CDS cast'i olarak kopyalanamaz.

**T9 · `string_agg` view entity derleyicisinde desteklenmedi (ölçülen sistem).**
`Column <col> is not contained in the GROUP BY list`. Sürüm numarasına bakıp "destekli" varsaymak aktivasyonla çürüdü.
Çalışan: `count(*)` / `count(distinct …)` + `max(…)` temsilci; tam virgüllü liste gerekiyorsa AMDP/table function.
Liste isteğini "adet + temsilci"ye indirmek bir iş kararıdır → spesifikasyona not düş, sessizce düşürme.
Aynı sınıf: `OVER (PARTITION BY …)` pencere fonksiyonu ölçülen sistemde aktive olmadı → ABAP tarafına al.

**T10 · Sanal element + SADL hesaplama çıkışı** (join'lenemeyen kaynaktan görüntü kolonu, ör. uzun metin).
- CDS (`as select from`): `@ObjectModel.virtualElement: true` + `@ObjectModel.virtualElementCalculatedBy: 'ABAP:ZCL_…'` +
  `cast( '' as abap.char( N ) )`. Çıkışın ihtiyaç duyduğu kaynak alan view'da bulunmalı.
- `abap.string` CAST'te geçersiz (yalnız düz tip); üst sınır `abap.char(1333)`. `virtual <ad> : abap.string` yalnız projection/abstract entity'de.
- Sınıf `IF_SADL_EXIT_CALC_ELEMENT_READ`: `get_calculation_info` içinde istenen element adları **BÜYÜK HARF**
  (`'ORDERNO'`, `'OrderNo'` değil) → aksi `CX_SADL_EXIT_WRONG_ELMENT` kısa dump (hesaplamadan önce). Standart örnek:
  `CL_SDBIL_PBD_VIRTUAL_ELEMENT`. `calculate` girdi/çıktı tablosu 1:1 indeks; eşleşme yoksa `READ TABLE` (tablo ifadesi dump atar).
- Metin okuma: `READ_TEXT`'te `TDNAME` yazıcıyla birebir olmalı (gereksiz `ALPHA_INPUT` 70 haneye doldurur) ve OData çalışma
  anında `sy-langu` beklenen dil olmayabilir. Aynı değer başka bir ekranda zaten okunuyorsa **o okumayı yeniden kullan**.
- Statik inceleme/ATC geçer ama çalışma anında dump/boş dönebilir → canlı doğrula: OData sonucunu kullanıcıdan tarayıcıda
  açmasını iste (kimlik bilgili script yazma), HTTP 500'de `cli adt_dump_list` ile exception adı ve satırı. Tahmin etme, dump'a bak.

**T11 · Kök alan rename + tüketici o alanı seçiyor → atomik ortak aktivasyon.**
Tek tek aktivasyon iki yönlü kilitlenir: kök → `Field … is still being used in view <TÜKETİCİ>`; tüketici → `column … is unknown`.
Çare: iki düzeltilmiş kaynağı push et, sonra **tek istekte**
`cli adt_activate '{"name":"ZSD001_I_ORDER","object_type":"ddls","also":[{"name":"ZSD001_C_ORDER","object_type":"ddls"}]}'`.
Bu tuzak yazılıyken ikinci kez yaşandı: plan kuran üç ayrı rol de obje-tipi tuzak listesini okumadan "önce kök, sonra tüketici"
dedi → **alan rename/silme içeren her push planından önce §4'ü tara.** Alan **kaldırmada** sıra ters: önce tüketici (ve onu
açan servis) yeniden aktive, sonra arayüz view; eklemede normal sıra. Ortak aktivasyon sonrası `content_verified: null`
"doğrulandı" değildir → `adt_get` ile gözle teyit et.

**T12 · `concat` birinci argümanın sondaki boşluklarını kırpar.**
`concat( a, concat( ' · ', b ) )` → `"A ·B"`; literali dışa almak da kurtarmaz (`concat( concat( a, ' · ' ), b )` aynı sonuç,
ölçüldü). Çalışan: `concat_with_space( concat_with_space( a, '·', 1 ), b, 1 )` → `"A · B"` (view entity'de aktivasyon +
readback ile kanıtlı). Aktivasyon/ATC geçer; yalnız çıktıya bakınca görülür. Taşınan ifadeyi **çıktısıyla** doğrula.
SQL/önizleme ucu `CAST( concat_with_space(…) AS CHAR(n) )`'i 400'lüyor — uç sınırı, dil sınırı değil.

**T13 · Veri önizleme boş CHAR'ı `null` gösterir.**
Ölçüm (aynı tablo): `WHERE col IS NULL` → 0 satır · `WHERE col = ''` → 17 satır. NULL'lığı ekrandan okuma, `IS NULL` ile ölç
(gerçek NULL çoğunlukla LEFT JOIN eşleşmemesinden). CASE'in NULL davranışına güveniyorsan kaynağa not yaz.
SQL ucunun 400 verdiği ölçülmüş biçimler (dil sınırı değil): `IN ( … )` listesi · 8+ kolonlu `GROUP BY`/`ORDER BY` ·
join + çok `WHEN`'li `CASE` · adlandırılmış parametreli `currency_conversion( amount => … )` (iki biçim denendi, kontrol
grubunda fonksiyonsuz aynı sorgu 15 satır döndü; başka çağrı biçimleri denenmedi). PB dönüşümünü CDS'in kendi kolonundan oku;
elle çarpımla doldurma (ters kotasyon, bkz. T14).

**T14 · `currency_conversion` DDIC-based view'da ayna kısıtlar taşır; view entity'de bu kısıtlar yok.**

| Parametre | Kabul | Ret | Ham hata (`DDLS 373`) |
|---|---|---|---|
| `AMOUNT` | kolon, path, parametre | ifade, cast | `For parameter AMOUNT only Columns,Paths,Parameters can be passed` |
| `EXCHANGE_RATE_TYPE` | ifade, literal, parametre | **kolon** | `For parameter EXCHANGE_RATE_TYPE only Expressions,Literals,Parameters can be passed` |

- Çalışan örneği kopyalamadan önce **view tipine** bak: aynı sistemde view entity'ler kur tipine kolon verip aktif olabilir.
- Toplam doğrudan çevrilemez → bileşenleri ayrı çevir, dışarıda topla (her çağrı yuvarlar → ≤ 0,01 sapma; kaynağa yaz).
- Kur tipi veriden türetilemez (DDIC-based'de literal ya da parametre); parametre eklemek classic tüketiciyi kırar → iş kararı, kullanıcıya sor.
- DDIC-based'de çalışan (aynı turda ölçüldü): `error_handling => 'SET_TO_NULL'` (view entity'de `SD_EXPRESSION 146` — ters
  asimetri) · DTEL cast (`cast('TRY' as waers)`) · dış `cast( case … end as <CURR_DTEL> )` · `coalesce`. Built-in `abap.cuky`/`abap.curr` denenmedi.
  ```
  cast( case when <src_cuky> = '<HEDEF>' then <col_a> + <col_b>
             when <src_cuky> <> '' and <src_cuky> is not null
               then coalesce( currency_conversion( amount => <col_a>, source_currency => <src_cuky>,
                                target_currency => cast( '<HEDEF>' as waers ), exchange_rate_date => <tarih_kolonu>,
                                exchange_rate_type => 'M', error_handling => 'SET_TO_NULL' ), 0 )
                  + coalesce( currency_conversion( amount => <col_b>, … ), 0 )
             else 0 end as <CURR_DTEL> )
  ```
- DENENEN — BAŞARISIZ: `amount => cast( (a+b) as <DTEL> )` · `amount => (a+b)` · `exchange_rate_type => case when <kolon> <> '' then <kolon> else 'M' end`.
- Ters kotasyon: `TCURR`'da bir yön negatif `UKURS` ile saklanabilir; `currency_conversion` çözer, elle çarpım çözmez
  (ölçülmüş: işaret ve büyüklük yanlış çıktı). Bir kur tipi yalnız tek yönde bakımlı olabilir → (tip × yön) çiftini `TCURR`'dan ölç.
- Classic ALV yan etkisi: her çevrilmiş tutar `@Semantics.amount.currencyCode` için sabit PB kolonu ister; `SELECT *` +
  alan kataloğu birleştirmeyle beslenen ALV'de bu kolonlar görünür → kullanıcıya önceden söyle, tutarların ardına koy.

**Quantity/amount alanı ifadede.** `@Semantics.quantity`/`amount` taşıyan alan `a - b`, `a * b` gibi ifadede →
`Amounts and quantities are not allowed in expression`. Önce `cast( <alan> as abap.dec(<n>,<m>) )` ile semantiği sıyır, sonra
hesapla, dışta tipi sabitle. Released birim çevrim alanları (ör. `I_ProductUnitsOfMeasure` pay/payda) da birim referanslıdır →
`Elements with required UNIT-reference are not supported`; aynı cast çaresi.

**Birim/para birimi alanında aggregation.** `max`/`min`/`sum` bir UNIT ya da CUKY alanına → `Function MAX: Type UNIT of
Parameter 1 not supported`. Bu alanlar referanstır → aggregate etme, `group by`'a koy.

---

## 5. Clean core — kaynak seçimi
- Standart tablo okumadan **önce** released CDS halefini ara (`MARA` → `I_Product`, `LIPS` → `I_DeliveryDocumentItem`,
  `VBAP` → `I_SalesDocumentItem`); adı tahmin etme, `adt_search_objects` + `adt_get` ile doğrula (`%sap-dev` → `coding-patterns.md` §7).
- Kullanıcı "`MARM` kullan" dese bile bu **veriyi** kasteder; released eşdeğeri (`I_ProductUnitsOfMeasure`) işi yapıyorsa onu kullan.
  Released gerçekten yetmiyorsa (eksik alan) ham tabloya düş ve **gerekçeyi bildir**; uyarıyı sessiz geçme.
- Geçişten önce CDS-DCL-02 karar kuralı (§2). Profil: released CDS `ecc`'de yoktur.

---

## Bu dosyada ÇIKARILAN / DEĞİŞTİRİLEN (kaynağa göre)
- Toplu CDS script'lerinin komutları, iç fonksiyon kodu (whitelist doğrulayıcı gövdesi), proje yapılandırma anahtarları → alınmadı; kuralın kendisi (§3.2) kaldı.
- Tarihli vaka anlatıları, önceki ajan ortamının rol ve iterasyon dili, gerçek müşteri obje ve süreç adları → çıkarıldı ya da nötr demoya çevrildi.
- Kimlik bilgili `curl` ile OData/dump okuma → kullanıcıya tarayıcıda açtırma + `adt_dump_list`.
- Kontrol listesindeki CDS maddeleri → `checklists.md` §1.
