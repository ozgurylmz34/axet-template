# Dynpro ekranı + GUI status + başlık çubuğu

> Kaynak: ekip playbook'unun ekran/GUI status üretim kılavuzu ve FUGR bölümündeki üreteç iç mekaniği · klasik dialog
> kodlama standardı §4 · bilinen hatalar (klasik Dynpro/CUA tablosu). Kaynak ekip bu işi **projeye özgü bir Z RFC FM**
> ile otomatikleştirmişti; o FM her sistemde yoktur. Aşağıda yöntem standart API'lerle anlatılır, yardımcı FM adı
> `<EKRAN_URETECI_FM>` yer tutucusudur (template kiti: `ZBC000_FM_SCREEN_GEN`, `screen-gen-kit.md`; kurulum
> `templates/screen-gen/DEPLOY.md`).
> Tek kayıtlık, DDIC alanlı form ekranı → ayrıca `dynpro-dialog-fields.md`. Program tarafı PBO/PAI → `alv-report.md` §5.

## 0. Yol seçimi

```
Sistemde ekran + CUA üreten, RFC-enabled bir yardımcı Z FM var mı?
  (adt_search_objects ile ara, kullanıcıya sor; varsa kaynağını adt_get func ile OKU — imzasını tahmin etme)
  ├─ EVET → §3: model parametre yükünü (payload) hazırlar → imzası kit üreteciyle aynıysa adt_screen_generate
  │         ile çağırır; değilse ya da araç kullanılamıyorsa ÇAĞRIYI GELİŞTİRİCİ yapar (classrun bu FM'leri koşamaz — §1)
  └─ HAYIR → §2: model Screen Painter (SE51) + Menu Painter (SE41) adımlarını TARİF eder,
             geliştirici SAP GUI'de uygular; model sonra kaynağı/ekranı okuyarak doğrular
```
**CLI yolu — `adt_screen_generate` (2026-09-13; yazma sınıfı, READ modu dahil; yalnız `ecc`/`s4_private`; çevrimdışı test
edildi, canlı DOĞRULANMADI):** sistemdeki Z/Y üreteç RFC FM'ini SOAP-RFC (`/sap/bc/soap/rfc`, `sap-language` = `master_language`,
`TABLES` daima boş etiketle) üzerinden çağırır; FM'i kendisi yaratmaz, FM adı gömülü değildir (`fm_name`). Şart: FM imzası kit
üretecinin 16 parametresiyle aynı (`screen-gen-kit.md` §2). Argüman eşlemesi ve hüküm kodları: `screen-gen-kit.md` §6 ·
`%sap-adt-foundation` → `tool-catalog.md` → `adt_screen_generate`. Ham SOAP/REST ile SAP'ye yazan script yine yazılmaz.

## 1. Neden classrun değil — diyalog bağlamı
- `RPY_DYNPRO_INSERT` ve `RS_CUA_INTERNAL_WRITE` **diyalog bağlamı** ister → `adt_classrun` ile `400 "Session Timed Out"`
  (`%sap-adt-foundation` → `known-errors-adt.md` K-14).
- Kaynak ekipte çalışan kanal: RFC-enabled Z FM + `/sap/bc/soap/rfc` (`sap-language` = proje dili **şart**; yoksa GUI
  metinleri oturum varsayılan dilinde — ölçülen vakada Almanca — gelir).
- SOAP-RFC tuzağı: `TABLES` parametresi istekte **boş etiketle** yer almazsa cevapta dönmez → HTTP 200 + boş tablo
  (ölçüldü: etiketler eklenince 166 KB veri). *200 ≠ başarı.*
- Yardımcı FM'i geliştirici SE37 test ekranından çalıştırırsa diyalog bağlamı sağlanır mı: **DOĞRULANMADI.**

## 2. Elle yol — geliştiriciye verilecek tarif (Screen Painter + Menu Painter)
Model şu listeyi somut değerlerle (ekran no, adlar, metinler **spesifikasyondan**) hazırlar:

**Ekran (SE51, program = Z program):**
1. Ekran `0100`, tip "Normal"; kısa açıklama proje dilinde.
2. Akış mantığı yalnız iki modül (program tarafıyla aynı numara):
   ```
   PROCESS BEFORE OUTPUT.
     MODULE status_0100.
   PROCESS AFTER INPUT.
     MODULE user_command_0100.
   ```
3. Tam ekran ALV → docking container kullanılacaksa ekrana eleman koyma (container kodda). Belirli yer/boyutta ALV →
   bir **custom control** (`CC_ALV`), aşağıdaki §4 değerleriyle.
4. OK-code alanı tanımlanacaksa adı programdaki değişkenle aynı (şablon hem ok-code değişkenini hem `sy-ucomm`'u okur).
5. Kaydet → aktive et → **ekranı KAPAT** (açık editör kilidi sonraki ADT turunu `EU 510` ile bloklar — K-07).

**GUI status (SE41):**
1. Status `STAT0100`, tip "Diyalog status"; başlık çubuğu `TIT0100` (metin proje dilinde).
2. Fonksiyon tuşları: F3 → `BACK`, Shift+F3 → `EXIT`, F12 → `CANCEL` — fonksiyon tipi **normal** (tip `E` değil; §5.3).
3. Uygulama toolbar'ı: her buton için fcode + metin + ikon + quickinfo; programın PAI'sinde her fcode'a bir `CASE` dalı.
4. Kaydet → üret/aktive et (üretilmemiş status runtime'da `00264` verir) → **KAPAT**.

Sonra model `adt_get` (program + include'lar) ile `SET PF-STATUS 'STAT0100'` / `SET TITLEBAR 'TIT0100'` / `CALL SCREEN 0100`
numaralarının ekranla tuttuğunu kontrol eder; runtime davranışını (§7) geliştirici dener.

## 3. Yardımcı üreteç FM varsa — standart API akışı ve payload

**Ekran:** `RPY_DYNPRO_INSERT` — başlık `rpy_dyhead` (tip `N`, sonraki ekran = kendisi), akış `rpy_dyflow` (PBO/PAI
`MODULE` satırları), container'lar `DYCATT_TAB` (satır `RPY_DYCATT`), alanlar `fields_to_containers` `DYFATC_TAB`
(satır `RPY_DYFATC`). Okuma `RPY_DYNPRO_READ`.
- `RPY_DYNPRO_INSERT` var olan ekranın **üzerine yazmaz** (`already_exists`, rc=2). `RPY_DYNPRO_DELETE` **yoktur** →
  `RS_SCRP_DELETE` (`with_popup = space`, `suppress_checks = 'X'`, `corrnum = <transport>`) + INSERT.
- ⚠ DELETE sonrası INSERT düşerse ekran **kaybolur** → INSERT değerlerini önce doğru bil (ör. `element_of` §4).

**GUI status:** `RS_CUA_INTERNAL_FETCH` (donör) → sadeleştir/yeniden adlandır → `RS_CUA_INTERNAL_WRITE` (hedef Z program,
`tr_key`: `obj_type='PROG'`, `obj_name=<prog>`, `sub_type='CUAD'`, `sub_name=<prog>`, `devclass=<paket>`) →
**`RS_CUA_GENERATE`** (`objectname=<prog>`). Donör standart program **yalnız okunur**; yazılan tek obje hedef Z programdır.

**Status reçetesi (ölçülmüş, sırayla):**
| Adım | Kural |
|---|---|
| `sta`/`set` | donör status dışındaki satırları sil; status kodunu `STAT<n>` olarak yeniden adlandır |
| `tit` | tamamen boşalt, yalnız `TIT<n>` (başlıklar status'tan bağımsız → güvenli; yapılmazsa donörün başlıkları programa sızar — ölçülen donörde 16) |
| `men`/`mtx` (menü) + `but` (toolbar) | boşalt (görünür menü/toolbar gider); `adm-mencode`, `sta-butcode` temizle |
| **`act`/`actcode`** | ⛔ **KORU.** Temizlenirse BACK/EXIT/CANCEL geçersiz olur → runtime `00256 "Geçerli bir işlev seçin"` (3-4 tur patinaj) |
| `pfk` | yalnız nav eşlemesi açıkken: `03`→`BACK`, `15`→`EXIT`, `12`→`CANCEL` |
| `fun` | BACK/EXIT/CANCEL yoksa ekle; tiplerini **normal**e zorla (donörde `EXIT` tip `E` gelir; `AT EXIT-COMMAND` yoksa işlenmez) |
| WRITE | `biv` FETCH'te isteğe bağlı ama WRITE'ta **zorunlu** → FETCH'ten geleni geçir (yoksa RABAX "mandatory parameter BIV") |
| GENERATE | WRITE yalnız tanımı yazar; **`RS_CUA_GENERATE` şart** (yoksa runtime `00264 "GUI status … not generated"`) |

**CUA program geneline aittir:** `RS_CUA_INTERNAL_WRITE` programın **tüm** CUA'sını değiştirir (delta değil). Aynı
programda birden çok ekran varsa önce mevcut CUA okunur, yeni status yanına eklenir (merge). Merge kapalı yazım diğer
status/başlıkları **siler** — kontrollü karşıt testle ölçüldü (`FUN 186→185`, `BUT 1→0`). Her ekran kendi set kodlarını alır.

**Donör seçimi:**
- Standart `SAPLKKBL` / `STANDARD` ("Standard for General List Output"): BACK/EXIT içerir, ama büyük bir fonksiyon havuzu
  getirir (`FUN≈185`, `PFK≈865`); nav eşlemesi uygulanınca `BACK/EXIT/CANCEL` bekleyen PAI ile çalışır (ölçüldü).
- Minimal bir müşteri donörü `&F2..&F5` fcode'ları getirir → `WHEN 'BACK'` bekleyen PAI **yakalamaz** (buton görünür, tepkisiz).
  Aynı donörde `ACT` tablosu boşken status alanı dolu olabilir → uyarı vermeden `00256` riski; runtime sonucu **ÖLÇÜLMEDİ**.
- Hedef programın kendisini donör yapmak: üretilen status adı ile donör status adı tutmaz → hiçbir şey yazılmaz.
- Template kitindeki `ZBC000_FM_SCREEN_GEN`'de varsayılan donör `SAPLKKBL`/`STANDARD`'dır (nav eşlemesi otomatik açılır);
  yukarıdaki minimal müşteri donörü kaynak ekibin FM'inin varsayılanıydı. Sistemdeki üreteçte hangisinin geçerli olduğunu
  kaynağındaki varsayılan donör sabitinden oku (`screen-gen-kit.md` §8).

**Kaynak ekibin üreteç FM'inin arayüzü (örnek bir uygulama — sistemindeki FM'in imzasını kaynağından oku):**
hedef program (**Z/Y koruması**: değilse hiçbir şey yazmadan döner; korumayı **var olmayan** bir adla dene, gerçek standart
programla değil) · ekran no (**tam 4 hane**, değilse hiçbir adım koşmaz) · transport · başlık metni · ekran tipi
(`DOCKING` / `CONTAINER`) · custom control adı · mod (`WRITE` / `READ` / `DELETE`) · yeniden kur bayrağı · donör program +
status · CUA merge bayrağı (**tanınmayan değer açık bırakır + uyarır**; boş/`-` gerçekten siler) · nav eşlemesi (otomatik /
zorla aç / zorla kapa) · dönüş kodu + tanı mesajı · toolbar buton tablosu (`FCODE`, `TEXT`, `ICON`, `QUICKINFO`, `FKEY`) ·
alan tablosu (`RPY_DYFATC` ile aynı alan adları).
- Tanı mesajını **kırpma**: uyarı satırları mesajın sonundadır (ölçülen uzunluk 559 karaktere çıktı).
- Buton `FKEY`'ini boş bırak (üreteç çakışmayan slot seçer; sabit tuş denenmedi).
- Her koşumda mesajdaki nav eşlemesi sinyaline bak: "kapalı" görünüyorsa donör parametreleri gitmemiştir → ekranı kullanmadan düzelt.
- Ekran/status/başlık/set kodları ekran numarasına göre dinamik: `STAT<n>`, `TIT<n>`, `MODULE status_<n>` / `user_command_<n>`.

## 4. Layout tipleri ve kanıtlı container değerleri
| Tip | Ne zaman | Nasıl |
|---|---|---|
| Docking | tam ekran tek ALV; alan ekranı | ekranda container yok; programda `cl_gui_docking_container` |
| Container | ALV belirli yer/boyutta, başlık alanları + liste, çoklu kontrol | 1 custom control (`CC_ALV`); programda `cl_gui_custom_container( container_name = 'CC_ALV' )` |
| Split | master-detail | ayrı tip değil: Container + programda `cl_gui_splitter_container` (`alv-report.md` §6) |

| Alan | Değer | Neden (ölçüldü) |
|---|---|---|
| Ekran `lines` / `columns` | **200 / 255** | küçük boyutta (20×120) ALV kırpıldı |
| Custom control `element_of` | **boş** | açıkça `'SCREEN'` → `illegal_field_value` (rc=6); okumada `SCREEN` görünmesi SAP'nin kendi ataması |
| `line`/`column` · `height`/`length` | `1`/`1` · **200/255** | tam ekran |
| `c_resize_v` / `c_resize_h` | **`'X'` / `'X'`** | zorunlu — yoksa kontrol sabit boyutta kalır, ALV pencereyi doldurmaz |
| `c_line_min` / `c_coln_min` | `1` / `1` | resize ile birlikte |

Container tipleri (`SCRCTYPE`): `CUST_CTRL`, `SUBSCREEN`, `TABLE_CTRL`, `STRIP_CTRL`, `RADIOGROUP`, `LOOP`. Container
modunda ekrana ayrıca alan konursa `CC_ALV` tüm ekranı kapladığı için çakışır (rc=6) → alan ekranı docking ister.

## 5. Tuzaklar
### 5.1 Toolbar her yazımda baştan kurulur
Hedef status yazılırken toolbar (`but`) koşulsuz boşaltılır ve **yalnız o çağrıda verilen** butonlarla kurulur; "yeniden
kur" bayrağı bunu değiştirmez (yalnız Dynpro'yu etkiler). ⇒ O status'ün **tüm** butonları her yazımda verilir. Fonksiyon
tanımları (`fun`/`pfk`/`act`) ise yalnız eklenir, silinmez. (Eski "yalnız ekler" iddiası yan bir sayacın değişmemesinden
genellenmişti; davranışı üreten deney yapılmamıştı.)

### 5.2 Donörle çakışan fcode etiketi geri döner
Bir fcode donörde de varsa ve o yazımda payload'da yoksa metin/quickinfo'su **donörünkine döner** — üstelik o turda
dokunulmayan başka ekranda da görünür (fonksiyon tanımı program geneli). Sayaçlar değişmez. Çare: donörle çakışan
fcode'ları her yazıma koy ya da ekrana özel ayrı fcode ver ("genel etiket" uzlaşması denendi, geri alındı).

### 5.3 ESC / çıkış
Nav fonksiyonları normal tip + `user_command_<n>`; ESC = F12 = CANCEL. Tip `E` + `AT EXIT-COMMAND` yolu **denendi, başarısız**
(üretilen ekranda OK alanı yoktu). `exit_command_<n>` modülü yazılmaz (akışta çağrılmıyorsa ölü kod).

## 6. Doğrulama protokolü
| Sayaç | Kapsam |
|---|---|
| `TITLES`, `FUN`, `PFK`, `BUT`, `MEN` | **program geneli** (farklı ekranlarda aynı çıkması normaldir) |
| Alan-container eşleme sayısı | ekran bazlı |

1. Tur öncesi sayaçları oku → 2. beklenen `BUT` deltasını **yazmadan önce** hesapla (Σ gönderilecek buton − mevcut) → 3. yaz →
4. final sayaçları beklentiyle **birebir** kıyasla → 5. **fonksiyon detay dökümünü (kod + metin + ikon + quickinfo) diff'le**
— `FUN` sayacı etiket kaybını **görmez** → 6. değişmeyen ekranların alan/akış/başlığı aynı mı → 7. `adt_inactive_objects` 0 →
8. GUI-only maddeleri kullanıcıya sor (§7).
- CUA içeriği RFC ile **okunabilir**: `RS_CUA_INTERNAL_FETCH` `TFDIR-FMODE='R'` (ölçüldü) — `STA FUN MEN MTX ACT BUT PFK SET DOC TIT BIV`
  11 tablo etiketi boş olarak gönderilmek şartıyla. `RS_CUA_INTERNAL*` ailesinde RFC-enabled olan **yalnız `_FETCH`** →
  RFC'den CUA okunur, yazılamaz. (aXet CLI'de genel SOAP-RFC çağrı aracı yok — `adt_screen_generate` yalnız üreteç FM'ini çağırır;
  üreteçte `mode="READ"` dökümü kullanılabilir; `adt_sql_query` ile `TFDIR` okunabilir.)
- Beklenmeyen sayı çıkınca ilk soru "ne değişti?" değil "**bu sayı neyi sayıyor?**".

## 7. Runtime — yalnız çalıştırarak görülür
Buton tepkisi, BACK/EXIT/CANCEL/ESC, `00256`, `00264`, toolbar etiketi/quickinfo, alanın giriş/salt okuma hissi, Türkçe
karakter (ç/ğ/ı/İ/ö/ş/ü) görünümü statik okumayla kanıtlanamaz → geliştirici programı çalıştırıp dener.

## 8. Hata → çare
| Belirti | Sebep / çare |
|---|---|
| `400 Session Timed Out` (classrun) | diyalog bağlamı yok → RFC FM + SOAP-RFC (`adt_screen_generate`) ya da elle yol |
| `00256 Geçerli bir işlev seçin` | `act` temizlenmiş / donör `ACT` boş |
| `00264 GUI status … not generated` | `RS_CUA_GENERATE` çağrılmamış (elle yolda: status üretilmemiş) |
| RABAX `mandatory parameter BIV` | FETCH'ten gelen `biv` WRITE'a geçirilmemiş |
| GUI metinleri başka dilde | SOAP-RFC çağrısında `sap-language` yok |
| Geri/Çıkış çalışmıyor, ekranda `&F…` fcode'ları | donör fcode'ları; `pfk` eşlemesi / donör seçimi (§3) |
| Diğer ekranların status/başlığı gitti | CUA merge kapalı yazıldı (§3) |
| ALV pencereyi doldurmuyor | custom control resize bayrakları yok (§4) |
| Alan ekranında rc=6 | container modu + alan → docking; ya da `element_of='SCREEN'` verilmiş |
| SOAP cevabında tablo boş, HTTP 200 | `TABLES` etiketleri boş olarak gönderilmemiş |
