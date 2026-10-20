# Reçete — satış belgelerinde karakteristik değerlerin hızlı girişi (Mill Products)

> **Ne zaman açılır:** varyant konfigürasyonlu malzemelerle çalışan bir satış sürecinde kullanıcı şunlardan birini söylediğinde:
> *"VA21/VA22'de 10 nolu kalemi tüm karakteristik değerleriyle 20'ye kopyalamak istiyoruz"* · *"çok kalemli teklifte her
> kalemi tek tek konfigüre etmek çok uzun sürüyor"* · *"genel kalem / yerel kalem alanı açılmıyor"*. Modül paketinde tetik:
> `../../sd.md` T-SD-8.
> **Ne anlatır:** IMG düğümü **"Satış belgelerinde karakteristik değerlerin hızlı girişi"** altındaki aktivitelerin her biri
> (ne yapar, neden, hangi tabloya ne yazar, hangisi zorunlu), ardından kullanım, doğrulama, sorun giderme, teknik anatomi.
> **Kim yapar:** uyarlamayı danışman ya da operatör yapar. Bu dosya karar ve kontrol listesidir; aXet uyarlama yazmaz.
> **Kaynak:** ekip çekirdeğinin reçetesi — bir s4_private 2025 sisteminde ölçüldü (2026-10-19): IMG ağacı (`TNODEIMG` /
> `CUS_IMGACH` / `CUS_ACTOBJ`), SAP IMG ve alan F1 dokümantasyonu (`DOKTL`), kaynak okuması, kullanıcının GUI testi. **aXet'te
> ayrıca ölçülmedi.** Başka sürüm ya da sistemde her adımı canlıda teyit et; bu dosya hipotezdir, otorite değil.

## 1. Ne işe yarar — iş amacı
Standart varyant konfigürasyonunda her kalemin karakteristikleri **tek tek**, ayrı bir konfigürasyon ekranında girilir. Bir
teklifte aynı ürünün az farklı 20 varyantı varsa 20 kez aynı ekrana girilir. Mill Products'ın hızlı giriş işlevi bu yükü üç
yoldan azaltır:

| İşlev | Ne yapar | Kullanıcıya faydası |
|---|---|---|
| **Karakteristiklere genel bakış ekranı** | Kalemler satır, seçilen karakteristikler sütun olarak tek tabloda; değerler doğrudan tabloya girilir | Konfigürasyon ekranına girip çıkmadan çok kalemi hızlı doldurma ve karşılaştırma |
| **Genel kalem → yerel kalem devralma** | Bir kalem *genel kalem* olur; ona bağlanan *yerel kalemler* onun karakteristik değerlerini devralır | **Aynı belge içinde** kalemi konfigürasyonuyla "kopyalama"; yalnız farklı olan değer değiştirilir |
| **Müşteri malzemesi bilgi kaydından devralma** | Kalem tipine bağlı olarak bilgi kaydındaki karakteristikleri kaleme taşır | Müşteriye özel sabit değerlerin her siparişte yeniden girilmemesi |

Karakteristik görüntüleri satış belgeleri dışında (Enjoy satınalma siparişi, mal hareketi, üretim siparişi ve teyidi; ticari
sözleşme yalnız `/SAPMP/GEN_01_TRADE_CM_COMBI` switch'i açıksa) da kullanılır. Bu dosya **satış belgesi** tarafını kapsar.

### Yanlış yollar — önce bunları ele
| Yanlış yol | Neden değil |
|---|---|
| Kopyalama kontrolü (VTAA) | Belgeden belgeye kopyalar; **aynı belge içinde** kalemden kaleme devralma yapmaz |
| IMG'de "kopyala / copy" araması | Düğüm adında bu kelime geçmez; arama **bulamaz** |
| Standart kalem genel bakışında "Genel kalem" sütunu aramak | Sütun orada yoktur; yalnız "Karakteristiklere genel bakış" ekranındadır |
| Varyant konfigürasyon modelini (CU41/CT04) değiştirmek | Devralma modelle değil, satış belgesi uyarlamasıyla açılır |

## 2. Ön koşul — switch / business function
Ölçülen sistemde `/SAPMP/*` switch'leri zaten açıktı; ek business function **gerekmedi**. Başka sistemde ilk iş SFW5'te
Mill Products / `/SAPMP/` switch'lerinin durumunu canlıda görmektir. Kapalıysa IMG düğümü ve alanlar görünmez, bu reçete de o
sistemde geçerli olmaz. Business function açmak **geri alınamaz** bir sistem kararıdır; kullanıcıya ayrıca sunulur.
Konfigüre edilebilir malzeme, sınıf (sınıf türü 300) ve karakteristikler hazır olmalıdır: bu işlev konfigürasyonu kolaylaştırır,
modelin yerine geçmez.

## 3. IMG yapısı (ölçüldü)
Düğüm bir *referans* düğümdür (`TNODEIMG` `NODE_TYPE = REF`): ayrı bir ağaçtaki **"Satış belgelerinde kalem
konfigürasyonu"** düğümünü gösterir; iki ad da aynı içeriğe çıkar. Altında 5 aktivite vardır:

| Aktivite (TR metin) | Aktivite | IMG işlem kodu | Bakım nesnesi | Yazdığı yer |
|---|---|---|---|---|
| Karakteristik değerleri için özellikler belirle | `ISMP/SAPMP/SD_TVAK1` | `S_KA5_12001198` | görünüm `/SAPMP/SD_TVAK_1` | TVAK (belge türü) |
| Genel/yerel grubu kaldır | `ISMP/SAPMP/SD_TVAK_2` | `S_KA5_12001199` | görünüm `/SAPMP/SD_TVAK_2` | TVAK |
| Karakteristik görüntüsü için uygulama grubu tanımla | `ISMP/SAPMP/V_VBMUEH` | `S_KA5_12001201` | görünüm `/SAPMP/V_VBMUEH` | `/SAPMP/VBMUEH` |
| Genel bakış ekranı için karakteristik görüntüsünü tanımla | `ISMP/SAPMP/SD_MUEBS` | `S_KA5_12001200` | görünüm kümesi `/SAPMP/SD_MUEBERSICHT` (SM34) | VBMUE / VBMUET / VBMUEZ |
| Müşteri malzemesi bilgi kaydından karakteristik değerleri devral | `MPWSD_MILL_GPOSTYP` | `S_KM5_93000007` | görünüm `V_MILL_TVAP_SE` | TVAP (kalem tipi) |

**Bu düğümde OLMAYAN ama zorunlu adım:** VOV8'deki belge türü alanı `TVAK-UEVOR` (§4.2). Düğüm tek başına tamamlanırsa
"uyarlama tamam ama alan açılmıyor" tablosu çıkar.

## 4. Aktiviteler — ne yapar, neden, ne zaman
Alan adları DDIC TR etiketidir; "SAP açıklaması" alanın F1 ya da IMG dokümantasyonunun özetidir (sistemde yalnız İngilizce bulundu).

### 4.1 `SD_TVAK1` — Karakteristik değerleri için özellikler belirle *(temel aktivite — ZORUNLU)*
Belge türü bazında karakteristiklerin genel kalemden yerel kalemlere **devralınmasını** açar ve devralmanın ek işlevlerini seçer.

| Alan (TVAK) | TR etiket | SAP açıklaması | Değer · ne zaman |
|---|---|---|---|
| `/SAPMP/CEACT` | Konfigürasyonu etkinleştir | Belge türü için hızlı girişin etkin olup olmadığı | **X — zorunlu**; bütün mantığın ana anahtarı |
| `/SAPMP/PDACT` | Aktarımı etkinleştir | Genel kalem değerlerinin bağlı yerel kalemlere devralınıp devralınamayacağı | **X**: mevcut kalemlere sonradan "Aktarım" yapılacaksa |
| `/SAPMP/PUSER` | Aktarım: kullanıcı değerlerinin üzerine yaz | Devralmada genel kalem değerleri, yerel kaleme **elle girilmiş** değerleri ezsin mi | X: genel kalem kazanır · boş: elle değişiklik korunur |
| `/SAPMP/PPROT` | Günlük aktarımı | Devralma hata günlüğü **otomatik** gösterilsin mi | Günlük her zaman oluşur ("Inheritance Log" düğmesi); **veritabanına kaydedilmez**, belge kapanınca silinir |
| `/SAPMP/PAUSW` | Karakteristik seçim listesinin aktarımı | Devralmada seçim listesi sunulsun mu | X: yalnız seçilen karakteristikler kopyalanır |
| `MILL_SE_ATNAM` | Karakteristik adı | Karakteristik görüntüsünün **varsayılanını** tutan karakteristik | İsteğe bağlı; sınıf türü 300'deki bir varyant sınıfına atanmış olmalı |

**Neden:** CEACT olmadan hızlı giriş hiç çalışmaz. PDACT / PUSER / PPROT / PAUSW "devralma ne kadar serbest, ne kadar kontrollü
olsun" sorusunun cevabıdır — **iş kararıdır**, kullanıcıyla konuşulur.

### 4.2 VOV8 `TVAK-UEVOR` — genel bakış ekranı için işlev kodu *(ZORUNLU — düğümde yok)*
Satış belgesinin ilk ekranından sonra hangi **genel bakış ekranına** gidileceğini belirler. **Değer: `MILL_SE_UE`** → belge
açılınca "Karakteristiklere genel bakış" ekranı gelir (SAPMV45A ekran 4001 + alt ekran 4434). "Genel kalem" sütunu ve
karakteristik değer sütunları **yalnız bu ekrandadır**.
**Neden zorunlu (ölçülen vaka):** CEACT, PDACT, PPROT, PUSER ve PAUSW X iken alan **açılmadı**; `UEVOR = MILL_SE_UE` girilince
açıldı ve kopyalama çalıştı (kullanıcı GUI testi).

### 4.3 `V_VBMUEH` — karakteristik görüntüsü için uygulama grubu *(isteğe bağlı)*
İşlemlere *uygulama grubu* atar; grup, hangi işlemde hangi görüntülerin seçilebileceğini süzer.

| Alan (`/SAPMP/VBMUEH`) | TR etiket | Anlamı |
|---|---|---|
| `/SAPMP/ANWID` | İşlem | Hızlı girişi olan işlem (satış belgesi, satınalma siparişi, mal hareketi …) |
| `/SAPMP/ZUORD` | Uygulama grubu | Grup kodu; birden çok işleme atanabilir. `*` = o işlemde **bütün** görüntüler |

Hiç kayıt girilmezse hızlı girişi olan bütün işlemlerde bütün görüntüler seçilebilir. Süzmek yalnız çok sayıda görüntü varken
ve süreçler ayrışıyorsa anlamlıdır (ör. satınalma görüntüleri satışta görünmesin).

### 4.4 `SD_MUEBS` — genel bakış ekranı için karakteristik görüntüsü *(isteğe bağlı, pratikte gerekli)*
Hızlı giriş ekranında hangi karakteristiklerin, hangi sırayla ve hangi genişlikte **sütun** olacağını tanımlar. Adımlar:
görüntüye ad ve açıklama ver → gerekirse uygulama grubu ata (§4.3) → "Karakteristik ataması"nı seç → karakteristikleri sırayla gir.

| Tablo · alan | TR etiket | Anlamı |
|---|---|---|
| VBMUE `MUEBS` · `/SAPMP/ZUORD` | Karakteristik görüntüsü · Uygulama grubu | Görüntü başlığı ve geçerli olduğu işlem grubu |
| VBMUET | — | Görüntü metni |
| VBMUEZ `FOLGE` · `ATNAM` · `CLENG` | Sıra · Karakteristik adı · Görüntülenen sütun genişliği | Sütunlar (pratikte ≤ 10 karakteristik) |

Görüntü tanımlanmazsa ekranda değer sütunu olmaz: kalemler ve "Genel kalem" sütunu yine görünür, devralma çalışır ama tabloda
hızlı giriş yapılamaz. Görüntü **"Genel kalem" sütununun varlığını etkilemez.** Kullanıcıya özel varsayılan: kullanıcı
parametresi `VAM` (SU3); belge türü varsayılanı `MILL_SE_ATNAM` (§4.1).

### 4.5 `SD_TVAK_2` — genel/yerel grubu kaldır *(isteğe bağlı)*
| Alan (TVAK) | TR etiket | SAP açıklaması |
|---|---|---|
| `/SAPMP/GAUF` | Genel/yerel grup kaldırma olanaklı | Bağ kaldırılınca yerel kalem **normal kalem** gibi işlenir |

Kalem yanlışlıkla bağlandıysa ya da artık bağımsız yaşayacaksa gerekir. Boş bırakılırsa bağ kalıcıdır.

### 4.6 `MPWSD_MILL_GPOSTYP` — müşteri malzemesi bilgi kaydından devralma *(isteğe bağlı)*
Kalem tipi bazında bilgi kaydındaki karakteristik konfigürasyonunun kaleme devralınıp devralınmayacağını ve çakışmada hangisinin
kazanacağını belirler; yalnız malzemenin konfigürasyonunda var olan karakteristikler devralınır.

| Alan (TVAP) | TR etiket | Değerler |
|---|---|---|
| `MILL_SE_KKNMT` | Müşteri malzemesinden karakteristiklerin devralımı için gös. | ` ` devralınmaz · `1` devralınır, çakışmada **bilgi kaydı** kazanır · `2` devralınır, çakışmada **genel kalem** kazanır |

**DOĞRULANMADI:** bilgi kaydında konfigürasyonun nerede tutulduğu — `KNMT`'de `CUOBJ`/`MILL_SE*` alanı yok (ölçüldü); büyük
olasılıkla `IBINOWN` üzerinden bağlanıyor. Kullanılacaksa önce canlıda ölç.

## 5. Asgari set — hangi ihtiyaç hangi adımları ister
| İhtiyaç | Gerekli adımlar |
|---|---|
| Yeni kalemi mevcut kalemin konfigürasyonuyla yaratmak (aynı belgede) | §4.1 `CEACT` + §4.2 `UEVOR` |
| Mevcut kaleme sonradan devralma ("Aktarım") | + §4.1 `PDACT` |
| Karakteristikleri tabloda hızlı girmek / karşılaştırmak | + §4.4 görüntü (+ gerekirse §4.3) |
| Devralmayı kontrollü yapmak | + §4.1 `PUSER` / `PAUSW` / `PPROT` (iş kararı) |
| Bağı sonradan koparabilmek | + §4.5 `GAUF` |
| Müşteri bilgi kaydından değer almak | + §4.6 `MILL_SE_KKNMT` |

**Taşıma notu:** hepsi client'a bağlı uyarlamadır. QA/PRD'ye giderken §4.1 ve **§4.2 (VOV8 `UEVOR`) aynı pakette** gitmelidir;
ölçülen vakada ikisi ayrı zamanlarda yapıldı — biri unutulursa hedef sistemde aynı arıza tekrar eder. Uyarlama isteğini
taşımadan önce içeriğini gözle kontrol et (ilgisiz kayıt girmiş olabilir). Transport kararı kullanıcınındır.

## 6. Kullanım (VA21 / VA22)
1. Belgeyi aç; genel bakış "Karakteristiklere genel bakış" olarak gelir (§4.2'nin etkisi).
2. Gerekirse karakteristik görüntüsünü seç (§4.4).
3. Ekrandaki **kapsam** listesinde **"Tüm kalemler"**i seç. Kod davranışı (`conf_field_control_pbo`): "Yalnız genel" seçilirse
   "Genel kalem" sütunu gizlenir; "Genel + yerel" seçilirse alan kilitli gelir.
4. Kaynak kalemi (örn. 10) konfigüre et; bu kalem **genel kalem** olur.
5. **Yeni kalemde devralma:** yeni satırda "Genel kalem" alanına `10` yaz; değerler kalem yaratılırken devralınır.
6. **Mevcut kaleme sonradan devralma:** genel kalemi işaretle, "Aktarım"ı seç (§4.1 `PDACT` şart, işlev kodu `/SAPMP/PROP`).
   `PAUSW` açıksa seçim listesi, `PPROT` açıksa günlük otomatik gelir.
7. Yalnız farklı olan değerleri değiştir, kaydet.

Devralma kuralları: yalnız **aynı adlı** karakteristikler devralınır (farklı sınıftaki malzemede ortak olmayan karakteristik boş
kalır). Yerel kalem **kendi** konfigürasyon nesnesini (`VBAP-CUOBJ`) taşır — devralma bir kopyalamadır, canlı bağ değildir;
genel kalemi sonradan değiştirmek yerel kalemi güncellemez, yeniden "Aktarım" gerekir.

Sistem mesajları (`/SAPMP/PUR`, TR metinleri T100'den):

| No | Metin | Anlamı |
|---|---|---|
| 015 | Yerel kalem &1 genel kalem olarak kullanılamaz | Zincir kurulamaz: yerel kalem başka kalemin genel kalemi olamaz |
| 022 | Kalem &1 genel kalemdir; buraya genel kalem girmeyin. | Genel kaleme genel kalem girilmiş |
| 023 | Genel kalem olarak &1 kaleminden farklı olarak bir kalem numarası girin | Kalem kendini göstermiş |

## 7. Doğrulama — ölç, varsayma (salt-okur, `adt_sql_query`)
```sql
-- belge türü: iki zorunlu alan + devralma ayarları (beklenen: UEVOR = 'MILL_SE_UE' ve CEACT = 'X')
SELECT auart, uevor, /sapmp/ceact, /sapmp/pdact, /sapmp/puser, /sapmp/pprot, /sapmp/pausw, /sapmp/gauf, mill_se_atnam
  FROM tvak WHERE auart = '<BELGE_TURU>'
-- kalem tipi: müşteri bilgi kaydından devralma
SELECT pstyv, mill_se_kknmt FROM tvap WHERE pstyv = '<KALEM_TIPI>'
-- görüntüler ve uygulama grupları
SELECT * FROM vbmue      -- görüntü başlıkları
SELECT * FROM vbmuez     -- görüntü sütunları
SELECT * FROM /sapmp/vbmueh
-- kaydedilmiş devralma: yerel kalemde MILL_SE_GPOSN = genel kalem no; her kalemin kendi CUOBJ'u
SELECT vbeln, posnr, mill_se_gposn, cuobj FROM vbap WHERE vbeln = '<BELGE>'
```
Ölçülen vakada kullanıcı devralmanın GUI'de çalıştığını gördü, ama aynı sistemde `MILL_SE_GPOSN` dolu VBAP kaydı **0** çıktı
(deneme kaydedilmemiş olabilir). Kaydedilmiş devralmanın VBAP'ta nasıl göründüğü **DOĞRULANMADI** — ilk kayıtlı devralmada son
sorguyla ölç.
**Raporlama:** değerler `VBAP-CUOBJ → IBINOWN → IBIN → IBINVALUES` (+ `IBSYMBOL`) zinciriyle okunur
(`lovc-belge-konfigurasyonu.md` §2.2). Yerel kalem kendi CUOBJ'unu taşıdığı için rapor genel kalemi ayrıca çözmek zorunda
değildir; "hangi kalemden devralındı" gerekiyorsa `MILL_SE_GPOSN` ayrı kolon olur.

## 8. Sorun giderme
| Belirti | Bak | Çare |
|---|---|---|
| Uyarlama tamam ama "Genel kalem" alanı / sütunu hiç yok | TVAK `UEVOR` | `MILL_SE_UE` (⭐ en sık; ölçülen vakanın kök nedeni) |
| Hızlı giriş ekranı hiç gelmiyor | TVAK `UEVOR` + `CEACT` | §4.1 + §4.2 |
| Ekran geliyor ama sütun gizli | Kapsam listesi | "Tüm kalemler" |
| Alan görünüyor ama kilitli | Kapsam listesi; satırda genel kalem zaten dolu olabilir | "Tüm kalemler"; alan doluysa giriş kapalıdır (kod davranışı) |
| "Aktarım" düğmesi yok | TVAK `/SAPMP/PDACT` | X |
| Devralmada elle girilmiş değer ezildi / ezilmedi | TVAK `/SAPMP/PUSER` | İş kararına göre |
| Bazı karakteristikler devralınmadı | Ad eşleşmesi; `PAUSW` seçim listesi | Aynı adlı mı, listede seçildi mi |
| Değer sütunları boş ya da yok | VBMUE/VBMUEZ, `/SAPMP/VBMUEH`, `VAM`, `MILL_SE_ATNAM` | §4.3 – §4.4 (sütunun varlığını etkilemez) |
| Bağ koparılamıyor | TVAK `/SAPMP/GAUF` | §4.5 |
| Hiçbir Mill işlevi / IMG düğümü yok | SFW5 `/SAPMP/` switch'leri | §2 (kullanıcı kararı) |
| Uyarlamadan önce açılmış VA22 oturumu | Tampon | İşlemden çıkıp yeniden gir |

## 9. Teknik anatomi — kod okuması neden yanılttı
- FM `MILL_SE_ACTIVATE` yalnız `TVAK-/SAPMP/CEACT`'a bakar; kodu okuyan *"kapı bu"* sanar.
- Çağrı yerleri SAPMV45A include'larıdır: `MILL_SE_MV45A_O01` (PBO `set_item_configuration_active`), `MILL_SE_MV45A_I01`,
  `MILL_SE_MV45A_FCODE_POCO`. Alan kontrolü `MILL_SE_MV45A_F01` → `conf_field_control_pbo` (`*VBAP-MILL_SE_GPOSN` sütunu);
  mantık aktif değilse sütunu gizler.
- Ama bu modüller yalnız **4001/4434 ekranının akışında** koşar. O ekrana ulaştıran şey belge türünün genel bakış işlev kodudur
  (`TVAK-UEVOR`); `CEACT = X` iken bile ekran çağrılmazsa alan görünmez.
- **Ders:** bir PBO kapısını okumak o ekranın çağrıldığını kanıtlamaz; ekrana giden işlev kodu ya da navigasyon ayrıca ölçülür.

## 10. Kapsam beyanı
- **Ölçülenler (kaynakta):** IMG ağacı ve aktiviteler · IMG ve alan dokümantasyonu (yalnız EN) · DDIC TR etiketleri ve T100
  mesajları · Mill include kaynakları · `UEVOR` etkisi (kullanıcı GUI testi).
- **Ölçülmeyenler:** kaydedilmiş devralmanın VBAP görünümü · `MILL_SE_KKNMT` bilgi kaydı tarafı · `GAUF` ile bağı kaldırmanın
  GUI yolu · satınalma, mal hareketi ve üretim tarafı · S/4 2025 dışındaki sürümler · aXet içinde hiçbir adım.
- Kısa referans satırı: `spro.md` "Varyant konfigürasyonu".
