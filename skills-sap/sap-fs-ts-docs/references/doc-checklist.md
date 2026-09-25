# Doküman kontrol listesi — KD / FS / TS

> **Kim kullanır:** yazardan bağımsız, taze bağlamdaki inceleyici (`agent` aracı; brifing §E). KD/FS/TS **üretilince ya da
> değişince**, "bitti" denmeden önce doküman bu listeye karşı incelenir → hüküm **PASS / WARNING / BLOCKER**. Yazarın öz
> kontrolü yetmez.
> **Madde tipleri:** **HATA** (kural ihlali, düzeltme zorunlu) · **EKSİK** (zorunlu içerik yok) · **ÖNERİ** (bağlayıcı değil).
> **Kapsam:** dokümanın tam içeriği + üretilen artefaktlar (Markdown, HTML, PDF, ekran görüntüleri, uygulamaya bağlanan kopya).
> **Mekanik yardımcı** kolonu: bir script'in ölçebildiği kısım. Script sonucu inceleyici yargısının yerine geçmez; script'in
> KAPSAM satırında "bakmadıkları" okunur.

## İkinci kapı — düzeltme turu kendi kapısını koşmadan kapanmaz
`inceleme → düzeltme → (inceleme yok)` zinciri açık kaldıkça **düzeltmenin kendisi** bulgu üretir: kaynak vakada bir doküman
setinin inceleme turundaki orta/yüksek bulguların yaklaşık %40'ı önceki düzeltme turlarının kendi çıktısından doğdu (bir iş kuralı
kaldırıldı, üç yerde uygulandı, normatif sözde kodda kaldı).
**İkinci kapı dar kapsamlıdır**, tam yeniden okuma değildir; yalnız üç yüzey:
1. değişen satırlar
2. değişen her **sayının/adın** dokümandaki diğer geçtiği yerler (DOC-CR-02)
3. kararın **yayılım listesi** (`fs-authoring.md` İlke 2b)

İkinci kapıyı birinci kapıyı koşan bağlam koşamaz (yeni taze inceleyici). Dar kapsam kuralın parçasıdır: geniş tutulursa
inceleme yorgunluğu doğar ve kapı mekanik onaya döner.

## §A — Kullanıcı dokümanı (KD)
| ID | Kontrol | Önem | Mekanik yardımcı |
|---|---|---|---|
| DOC-KD-01 | **Ekran görüntüleri temiz örnek veriyle** — anlamlı, tutarlı uydurma kayıt; kirli/gerçek kayıt (test çöpü, gerçek müşteri/kişi verisi, tutarsız satır) = ihlal. Gerçek arayüz evet, gerçek veri hayır | **BLOCKER** (HATA) | yok — görüntü okunur |
| DOC-KD-02 | Gerçek arayüz kullanılmış (mockup değil); görüntüler işaretli/numaralı | HIGH (HATA) | yok |
| DOC-KD-03 | **Tüm alt ekranlar var** (diyalog, popover, F4, seçim penceresi, sihirbaz) — her biri ayrı bölüm + görüntü + alan/buton işlevi; ekran envanteri KD'ye eşlenmiş | **BLOCKER** (EKSİK) | yok — envanter eşleme tablosu istenir |
| DOC-KD-04 | Grid varsa Bölüm 4-A (sıralama, filtre, kolonlar, varyant, Excel, yenile, filtre çubuğu) | HIGH (EKSİK) | yok |
| DOC-KD-05 | Genel bakışta amaç + **arka plan sonucu** | HIGH (EKSİK) | yok |
| DOC-KD-06 | Her tipik görev adım adım + görüntü; emir kipi | HIGH (EKSİK) | yok |
| DOC-KD-07 | Alan rehberi (ne/biçim/zorunlu + neden/otomatik) + **her** buton/olay arka plan sonucuyla | HIGH (EKSİK) | yok |
| DOC-KD-08 | Hata/mesaj tablosu: birebir metin + anlam + **aksiyon** | HIGH (EKSİK) | yok |
| DOC-KD-09 | Teknik terim sızmamış; her terim sözlükte; SSS + destek var | MEDIUM (EKSİK) | yok |
| DOC-KD-10 | İçerik canlı arayüzle güncel (bayat ekran/akış yok); ön koşullar var | HIGH (HATA) | yok |
| DOC-KD-11 | **Üretim doğrulandı:** PDF oluştu, sayfa sayısı makul; tüm görseller HTML/PDF'te görünüyor (kırık görsel 0); uygulamaya bağlandıysa yardım düğmesi doğru dosyayı açıyor ve görseller orada da yükleniyor | HIGH (HATA) | kısmi: `verify_doc_html.py` görsel sayısı + eksik yerel dosya; tarayıcıda yüklenme ve uygulama içi açılış elle |
| DOC-KD-12 | Klasik GUI: SAP içi F1 yardımı fihrist + bağlantılı detay sayfaları (tek düz sayfa değil) | HIGH (EKSİK) | yok — `%sap-classic-abap` `forms-f1-help.md` §B.6 |
| DOC-KD-13 | F1 ITF biçimi (başlık satırı, kalın/bağlantı etiketleri, satır ≤ 72 görüntü, gerçek Türkçe, BOM'suz) | HIGH (HATA) | `%sap-classic-abap` tarafında |
| DOC-KD-14 | F1 içerik kaynağı canlı (domain sabit değerleri canlı okundu, kolon/formül FS + sınıftan); geri okuma doğrulandı | HIGH (HATA) | yok |
| DOC-KD-15 | **Ham diyagram kodu çıktıya sızmamış:** HTML/PDF/uygulama yardımında `language-mermaid` ve ham `flowchart`/`sequenceDiagram` metni 0; her diyagram görsel. Kırık görsel kontrolü bunu yakalamaz | HIGH (HATA) | `verify_doc_html.py` (HTML); PDF metni elle |
| DOC-KD-16 | **İçindekiler bağlantıları hedefli — ölü bağlantı 0** (HTML ve PDF). `{href#} \ ({id} ∪ {a name})` = boş (küme kıyası, sayı değil; `name=` çıpası da geçerli hedef). PDF'te tıklanabilir bağlantı sayısı ≈ iç bağlantı sayısı. İki kök sebep: üretici `toc` eklentisiz (tümü ölü) · elle yazılmış `#hedef` başlıkla uyuşmuyor (tek tük). Onarımda başlığı değil href'i düzelt | HIGH (HATA) | `verify_doc_html.py` (HTML kümesi; PDF bağlantı sayısı yaklaşık) |

## §B — Fonksiyonel spesifikasyon (FS)
| ID | Kontrol | Önem | Mekanik yardımcı |
|---|---|---|---|
| DOC-FS-01 | Gerçek ekran görüntüsü yok; ekran mockup + yapısal tablolarla | HIGH (HATA) | yok |
| DOC-FS-02 | Zorunlu bölümler tam (kapak, doküman kontrolü, giriş, iş süreci, gereksinim, ekran, veri, entegrasyon, yetki, raporlama, hata, test, 11-A, 11-B, onay) | HIGH (EKSİK) | yok |
| DOC-FS-03 | Ne/neden odaklı (nasıl değil); iş dili; gereksinimler numaralı ve izlenebilir; girdide olmayan olgu yok | MEDIUM (EKSİK) | yok |
| DOC-FS-04 | İç tutarlılık: FS↔TS↔KD no eşleşmesi; süreç adımı ↔ gereksinim ↔ ekran çelişkisiz | MEDIUM (EKSİK) | yok |
| DOC-FS-05 | **Gövde = kapanmış hedef durum, analiz günlüğü değil** (İlke 2b). Gövdede (§1.1, 11-A/11-B ve EK karar günlüğü hariç) 0: sürüm etiketi, inceleme bulgu numarası, araştırma/ölçüm süreci, kullanıcı alıntısı, "önceden→şimdi" anlatısı. Başlıklar da gövdedir (H1 hariç). Kural dışı: kapak versiyonu, §1.1 tablosu, ilgili doküman satırı, altbilgi, dokümanın kendi tanımladığı kimliklere atıf. İnceleyici üslup yargısı da yapar: paragraf bugünkü hâli mi, nasıl bulunduğunu mu anlatıyor? Belirsiz iki kalıba dikkat: çıplak "artık" (isim de olabilir) ve "bu turda" | HIGH (HATA) | kısmi: `check_fs_no_analysis_log.py <FS.md ya da paket klasörü>` A-E sınıflarını satır bazında sayar (uyarı, kapı değil; `--bulguda-exit1` ile çıkış 1). Üslup yargısı ve belirsiz kalıplar elle; KAPSAM satırındaki "bakmadıkları" okunur. Bölüm tanıma numara/başlık sezgisidir: "1.1"/"1.3" ile başlayan her başlık §1.1/§1.3 sayılır (ör. "1. Giriş" altındaki "1.1 Amaç"; "1.3.2" alt numaraları) ve Setext (`===`/`---` alt çizgili) başlıklar tanınmaz; bu durumlarda bölüm elle okunur |
| DOC-FS-06a | §1.1 versiyon satırı kısa: satır başına 1-2 satır "ne değişti"; **≤ 400 karakter** | MEDIUM (EKSİK) | `check_fs_no_analysis_log.py` (§1.1 ve kimlik satırlarında > 400 karakter) |
| DOC-FS-06b | 11-B birikmemiş; kapanan karar gövdeye sonuç olarak işlenmiş, satırı EK'e inmiş; **yayılım tablosu tam** (boş/eksik tablo = kayıt geçersiz) | MEDIUM (EKSİK) | yok — anlam yargısı |
| DOC-FS-07 | **Yeniden yazımda veri kaybı 0:** kimlik kümeleri, mockup blokları, sayısal/kod değerleri, cümleler yeni FS ∪ EK'te var. İnceleyici denklik raporunu kanıt olarak ister ("okudum, aynı" yetmez) | HIGH (HATA) | `doc_equivalence_check.py` (rapor + §6 "ölçmedikleri") |
| DOC-FS-08 | **Defter/havuz tasarımında üçlü tam:** FS bir defter, havuz ya da bakiye tasarlıyorsa **giriş** (kayıt hangi belge/kalemden ve ne zaman doğar, tarih kuralı, miktar, kaynak iptal/yeniden kesim, gecikmeli dış veri) + **tüketim** (sıra kuralı, tetik, anlık görüntü, kilit) + **düzeltme/istisna/geçiş** (elle düzeltme, açılış bakiyeleri, yetim kayıt) yazılı; senaryo → sonuç tablosu var. Yalnız tüketimi anlatmak = ihlal (`fs-authoring.md` §4) | HIGH (EKSİK) | yok |

## §C — Teknik spesifikasyon (TS)
| ID | Kontrol | Önem | Mekanik yardımcı |
|---|---|---|---|
| DOC-TS-01 | Gerçek ekran görüntüsü yok; §4.5 ayrıntılı mockup + yapısal tablolar | HIGH (HATA) | yok |
| DOC-TS-02 | Zorunlu bölümler tam (genel bakış, 2-A, obje listesi, veri sözlüğü, ekran tasarımı, program/sınıf, DB erişimi, iyileştirme, form, arayüz, hata, test, 11-A, transport, onay; standart nesneye yazma varsa **§6.4 API seçimi** — reddedilenler nedeniyle, `%sap-dev` `write-api-selection.md`) | HIGH (EKSİK) | yok |
| DOC-TS-03 | **Obje adları/alanlar canlı sistemle tutarlı** (uydurma değil) ve adlandırma kuralına uygun. Klasik program include adları program kökünden türer (`%sap-dev` → `references/naming.md` §4.1); genel `_TOP`/`_F01` gibi kökten bağımsız ad yok | HIGH (HATA) | yok — canlı teyit turu C-1/C-2 kanıtı |
| DOC-TS-04 | Clean core ve yasak farkındalığı: en düşük genişletme seviyesi, 4. seviyede istisna gerekçesi; standart tablo yerine released CDS; standart obje/tabloya yazan çözüm yok | MEDIUM (ÖNERİ; yasak ihlali varsa BLOCKER) | yok |
| DOC-TS-05 | **Mesaj envanteri tam (§10.1):** her mesaj; metin birebir **≤ 73 karakter**; numaralı `&1..&4` + her birinin anlamı; üretim noktası; `E`/`A`'da kullanıcı aksiyonu; metinleri kullanıcı vermiş; build'de doğan mesaj TS'e geri işlenmiş; uzun metin varsa "SE91" şerhi | HIGH (EKSİK) | yok — inceleyici yargısı |
| DOC-TS-06 | İlke 5: §11-A yalnız teknik teyit; fonksiyonel karar (eşleştirme, dönüşüm, birim, kenar durum, kilit) açık bırakılmamış; §2-A boş değil | HIGH (EKSİK) | yok |
| DOC-TS-07 | **Henüz var olmayan şeyin adı yer tutucudur.** TS paket yaratılmadan ÖNCE yazılır; gövdede somut bir paket adı geçiyorsa ve o paket canlıda YOKSA bu bir **uydurma**dır: `<ZPKG>` biçiminde yer tutucu kullanılır ve §2-A'ya "paket adı kullanıcıdan alınacak" satırı düşülür. Aynı kural transport numarası ve henüz yaratılmamış DTEL/domain adları için de geçerlidir. Gerekçe: uydurulan adı bu arada başkası alabilir; ayrıca yeni Z DDIC adı ancak kullanıcının açıkça onayladığı öneri olarak somutlaşır (`%sap-dev` §6: öneri + canlı kontrol + onay), standart objeye append alanı adını ise AI hiç önermez (kesin yasak A). Canlıda VAR olan bir paket adı elbette somut yazılır — ayrım "uydurma mı" sorusudur, "somut mu" sorusu değil | **BLOCKER** (HATA) | yok — canlı teyit turu C-4 (paket/inaktif) kanıtı istenir |
| DOC-TS-08 | **FM imzası ↔ doküman senkron (FM kaynağı varsa — build sonrası):** parametreleri listelenen ve kaynağı yazılmış her Z FM için liste `<!-- FM-IMZA: <FM> -->` bloğunda; imzadaki her parametre blokta var (EKSİK 0), blokta imzada olmayan parametre yok (HAYALET 0). **Build öncesi TS** (FM henüz yazılmamış): blok aranmaz, eksikliği bulgu değildir; parametre listesi TS'in kendi §5/§9 tanımıyla elle tutarlı mı bakılır, blok build sonrası eklenir. Bloksuz parametre listesi araçla ölçülemez → inceleyici elle karşılaştırır (`ts-authoring.md` §5.3) | MEDIUM (HATA) | kısmi: `check_fm_signature_doc_sync.py` (yalnız parametre adları; tip/varsayılan/istisna ve bloksuz doküman elle — KAPSAM çıktısı okunur; çıkış 2 = ÖLÇÜLEMEDİ, temiz değil) |

## §D — Çapraz kontroller (tipten bağımsız, EK'ler dahil)
| ID | Kontrol | Önem | Mekanik yardımcı |
|---|---|---|---|
| DOC-CR-01 | **Ters yön:** her "A→B" varlık kontrolünün ikizi koşulur ("B var, atıf alıyor mu?"). En az dört ikiz: ① mesaj kataloğundaki her mesaj (özellikle `E`) bir üretim noktasına bağlı mı ② onaylı ad listesindeki her ad planda/uygulamada geçiyor mu ③ her DDIC alanını kim yazar / kim okur (ikisi boşsa yetim alan) ④ her kabul kriteri bir teste bağlı mı. Tek yönün temiz olması yarım sonuçtur | HIGH (EKSİK) | yok |
| DOC-CR-02 | **Sabit sayı/ad bayatlaması:** ① değişen sayı/ad dokümanın diğer tüm geçtiği yerlerde güncellenmiş mi (eski değeri doküman genelinde ara) ② ölçüt sabit sayıya değil kaynağa bağlı mı ("6+4 aktif" değil "onay listesindeki tüm adlar aktif") ③ kapsama beyanı hangi kümeyi kapsadığını söylüyor mu ("T-01…T-40 karşılandı" test kimliği tamlığıdır, kabul kriteri kapsaması değil) | HIGH (HATA) | kısmi: `doc_equivalence_check.py --closed-decision <eski değer>` |
| DOC-CR-03 | **Belge ↔ canlı teyit turu koşuldu mu:** TS build'e girmeden önce her "canlıda mevcut/kurulu/bağlı/yapılacak" iddiası ölçüldü mü (ad çakışması pozitif kontrollü, reuse imza dahil, uyarlama durumu, paket/inaktif, transport `E070`/`E071`). Kanıt = ölçüm çıktısı | HIGH (EKSİK) | yok — `live-confirmation-tour.md` raporu istenir |
| DOC-CR-04 | **Tüketici doküman yalnız kendi yüzeyini anlatır:** rapor (tüketici) FS/TS/KD'sinde veriyi üreten başka uygulamanın kuralı (kilit, zorunluluk, muafiyet, iptal) iddia olarak yazılmamış; varsa tek cümle + hedef dokümanın adıyla yönlendirme (hedefte içerik var). Test beklentisi rapor kolonuyla, canlı örnek raporun kendisinden. Düzeltmede kural: rapordan gözlenemeyen cümle **çıkarılır**, nitelendirilerek kurtarılmaz (`fs-authoring.md` §5.7) | HIGH (HATA) | yok |
| DOC-CR-05 | **Veri garantisi cümlesi ölçülmüş:** "X boştur / X doludur / artık Y'de görünür" türü cümle için veri göçü kararı kontrol edilmiş ve eski tarihli kayıtla karşı örnek aranmış; göç yoksa cümle eski kayıtları kapsayacak biçimde daraltılmış. Dayanağı yalnız tasarım niyeti (kod yorumu, karar metni) olan garanti = ihlal (`kd-authoring.md` §7) | HIGH (HATA) | yok — ölçüm çıktısı istenir |
| DOC-CR-06 | **Koda çapa kaymaz:** değişebilecek koda atıf satır numarasıyla değil metot/FORM/dal adıyla; doküman turu kod donduktan sonra koşulmuş (doküman, dayandığı kod sürümünü kaydediyor). Satır numarası varsa ölçülür, kaymışsa ada çevrilir (`traceability.md` §3) | MEDIUM (HATA) | yok |
| DOC-CR-07 | **Teslim paketi = çalışma dosyası:** dışarı gönderilen paket (zip/ek/teslim klasörü) teslim anında güncel dosyalardan kurulmuş; üye özetleri çalışma ağacıyla eşit (ölçüm çıktısı); beklenen özetler eşlik eden notta; aynı yerde eski sürüm paket yok (`traceability.md` §3) | HIGH (HATA) | yok — özet karşılaştırması istenir |
| DOC-CR-08 | **Kayıp tablo 0 (Markdown → HTML/PDF):** kaynaktaki tablo ayraç satırı sayısı (yalnız dikey çizgi, tire, iki nokta ve boşluktan oluşan satır) ile HTML'deki `<table>` sayısı eşit. Render olmayan tablo hata vermez; ayraç satırı ekranda ham metin kalır. Üç tetikleyici: başlık satırından önce boş satır yok (ham metin `<p>` içine düşer) · tablo liste öğesi altında girintili (`<li>` içine düşer) · tablo `<details>` ham HTML bloğu içinde. Son ikisini "`<p>` içinde ayraç" desen araması **yakalamaz** (ekip dersi: "0 kırık" diyen desen taraması 7 kayıp tabloyu kaçırdı). Parser'a bağlıdır: PDF hattı python-markdown `tables` eklentisini kullanır ve girintili tabloyu kaybeder; GitHub'da görünmesi yeterli değildir. Toplu girinti düzeltmesinden önce ve sonra sayım yapılır; kötüleşiyorsa geri alınır | HIGH (HATA) | yok — `verify_doc_html.py` tablo saymaz; iki sayı elle karşılaştırılır (kod bloklarındaki örnek tablolar ayıklanır) |

## Hüküm
- **PASS** → bitti denebilir.
- **WARNING** → yayınlanır; bulgu kullanıcıya/rapora yansıtılır.
- **BLOCKER** (ya da açık HATA/EKSİK) → düzelt + tekrar kapı (ikinci kapı kuralıyla). En sık BLOCKER'lar: DOC-KD-01 ve DOC-KD-03.
- Kontrol listesi dışı iyileştirme `[ÖNERİ]` olarak yazılır (bağlayıcı değil). Tekrar eden yeni doküman tuzağı bulunursa buraya
  `DOC-XX-NN` maddesi önerilir (template değişikliği → kullanıcı onayı).

## §E — Bağımsız inceleme brifingi (`agent` aracına yapıştırılır)
Alt ajan bu dosyayı, skill'i, çekirdek kuralları ve konuşmayı **görmez**; aşağıdaki `<…>` yerlerine ilgili bölümlerin
**metnini** yapıştır. Genel kanıt ve çıktı bölümleri için `skills/explore/references/brief-template.md` §5/§7/§8 eklenebilir.

```text
GÖREV (SALT OKUMA — DOKÜMAN İNCELEMESİ): Aşağıdaki <FS|TS|KD> dokümanını kontrol listesine karşı incele.
Hiçbir dosyayı değiştirme, yazan komut çalıştırma, SAP'ye bağlanma.
DOKÜMAN: <md yolu>  ·  ÜRETİLEN: <html / pdf / screenshots klasörü yolları | yok>
İLGİLİ DOKÜMANLAR: <FS no/yolu ↔ TS no/yolu ↔ KD no/yolu | yok>
KANIT EKLERİ: <canlı teyit turu raporu | denklik raporu | ekran envanteri eşleme tablosu | yok>
BU TUR: <ilk inceleme | İKİNCİ KAPI — yalnız: değişen satırlar <liste>, değişen sayı/adlar <liste>, yayılım listesi <liste>>

KONTROL LİSTESİ (metin):
<doc-checklist.md: ilgili tip bölümü (§A/§B/§C) + §D + "İkinci kapı" metni — tablo satırlarıyla birlikte>

İNCELEME KURALLARI:
- Her bulgu: madde ID + doküman konumu (başlık/bölüm no ya da dosya:satır) + somut sorun (ne yazıyor → neden ihlal).
- Doğrudan okunabilen bir iddiayı okumadan bulgu yapma. Görsel maddelerde görüntü dosyasını aç.
- "Bulunamadı" demeden önce hangi başlık/deseni aradığını yaz. Bir script raporu verildiyse KAPSAM satırındaki
  "bakmadıkları"nı ayrıca kendin incele; script'in 0 bulgusu o yüzeyde temiz demek değildir.
- Ölçemediğin maddeye "ÖLÇÜLEMEDİ" yaz, geçme.
- Checklist dışı iyileştirme [ÖNERİ] olarak ayrı listelenir.
ENGEL: dosya okunamıyor ya da kapsam belirsizse o maddede ilerleme; yanıtın ilk satırına "ENGEL: <ne · neden>" yaz.
ÇIKTI (tek yanıt): 1) Bulgular önem sırasıyla [BLOCKER | HIGH | MEDIUM | ÖNERİ] + ID + konum + sorun
2) Madde bazında durum: her ID → UYGUN / BULGU / ÖLÇÜLEMEDİ / UYGULANMAZ (gerekçe)
3) Son satır tek hüküm: PASS / WARNING / BLOCKER
```
Dönen rapordaki her BLOCKER ana oturumda dokümandan okunarak doğrulanır; doğrulanamayan NOT'a indirilir.
