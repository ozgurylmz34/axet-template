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
| DOC-KD-03 | **Tüm alt ekranlar var** (diyalog, popover, F4, seçim penceresi, sihirbaz, koddan açılan onay/uyarı kutusu `MessageBox`) — her biri ayrı bölüm + görüntü + alan/buton işlevi; ekran envanteri KD'ye eşlenmiş | **BLOCKER** (EKSİK) | yok — envanter eşleme tablosu istenir |
| DOC-KD-04 | Grid varsa Bölüm 4-A (sıralama, filtre, kolonlar, varyant, Excel, yenile, filtre çubuğu) | HIGH (EKSİK) | yok |
| DOC-KD-05 | Genel bakışta amaç + **arka plan sonucu** | HIGH (EKSİK) | yok |
| DOC-KD-06 | Her tipik görev adım adım + görüntü; emir kipi | HIGH (EKSİK) | yok |
| DOC-KD-07 | Alan rehberi (ne/biçim/zorunlu + neden/otomatik) + **her** buton/olay arka plan sonucuyla | HIGH (EKSİK) | yok |
| DOC-KD-08 | Hata/mesaj tablosu: birebir metin + anlam + **aksiyon** | HIGH (EKSİK) | yok |
| DOC-KD-09 | Teknik terim sızmamış; her terim sözlükte; SSS + destek var | MEDIUM (EKSİK) | yok |
| DOC-KD-10 | İçerik canlı arayüzle güncel (bayat ekran/akış yok); ön koşullar var | HIGH (HATA) | yok |
| DOC-KD-11 | **Üretim doğrulandı:** PDF oluştu, sayfa sayısı makul; tüm görseller HTML/PDF'te görünüyor (kırık görsel 0); uygulamaya bağlandıysa yardım düğmesi doğru dosyayı açıyor ve görseller orada da yükleniyor | HIGH (HATA) | kısmi: `verify_doc_html.py` görsel sayısı + eksik yerel dosya; tarayıcıda yüklenme ve uygulama içi açılış elle |
| DOC-KD-12 | Klasik GUI: SAP içi F1 yardımı fihrist + bağlantılı detay sayfaları (tek düz sayfa değil) | HIGH (EKSİK) | yok — `%sap-classic-abap` `forms-f1-help.md` §B.6 |
| DOC-KD-13 | **F1 ITF biçimi:** her sayfa ilk satır `U1` başlık; kalın `<ZH>…</>` (etiket içinde etiket yok); gerçek Türkçe, UTF-8 BOM'suz, markdown/HTML varlığı yok. **Her ITF satırı ≤ 72 ham karakter, etiketler dahil:** 73 ve üstü kesilir; 71–72 geçer ve ihlal DEĞİLDİR; ≤ 70 hedef paydır. Ölçü karakter sayısıdır, bayt değil; uzun cümle kelime sınırında bölünür, `<ZH>…</>`/`<DS:…>` etiketi iki satıra bölünmez. Sınır F1/SE61 **görüntüleme** genişliğidir (aşan kuyruk kaybolur); `DOKTL-TDLINE` ≤ 132 **depolama** sınırıdır, bu maddenin ölçütü DEĞİLDİR (kaynakta "≤ 132" bir brife yanlış sınır olarak geçti, doküman kapısı 3 BLOCKER verdi). Tetik: F1 metni yazarken ve bu sınırı bir brife/talimata aktarırken | HIGH (HATA) | satır genişliği: `check_docu_itf_line_width.py` (yazma kapısı `class_push`, > 72 BLOCKER); biçimin geri kalanı `%sap-classic-abap` `forms-f1-help.md` |
| DOC-KD-14 | F1 içerik kaynağı canlı (domain sabit değerleri canlı okundu, kolon/formül FS + sınıftan); geri okuma doğrulandı | HIGH (HATA) | yok |
| DOC-KD-15 | **Ham diyagram kodu çıktıya sızmamış:** HTML/PDF/uygulama yardımında `language-mermaid` ve ham `flowchart`/`sequenceDiagram` metni 0; her diyagram görsel. Kırık görsel kontrolü bunu yakalamaz | HIGH (HATA) | `verify_doc_html.py` (HTML); PDF metni elle |
| DOC-KD-16 | **İçindekiler bağlantıları hedefli — ölü bağlantı 0** (HTML ve PDF). `{href#} \ ({id} ∪ {a name})` = boş (küme kıyası, sayı değil; `name=` çıpası da geçerli hedef). PDF'te tıklanabilir bağlantı sayısı ≈ iç bağlantı sayısı. İki kök sebep: üretici `toc` eklentisiz (tümü ölü) · elle yazılmış `#hedef` başlıkla uyuşmuyor (tek tük). Onarımda başlığı değil href'i düzelt | HIGH (HATA) | `verify_doc_html.py` (HTML kümesi; PDF bağlantı sayısı yaklaşık) |
| AX-DOC-KD-01 | **Yer tutucu kalmamış:** görünür metinde (kod blokları dahil) `[EKRAN GÖRÜNTÜSÜ …]`, `[GÖRSEL: …]`, "… eklenecek" ertelemesi, `[AÇIKLAMA YAZILMADI]`, TODO/TBD/FIXME = 0. `[Açık Konu]` meşrudur (sayılır, bulgu değil). Beklenen görsel sayısı araç hata verdi diye düşürülmez; düşürülecekse kullanıcıya gerekçeyle sorulur | HIGH (HATA) | `verify_doc_html.py` (kalıp listesi KAPSAM satırında; ölçüldü 2026-10-03: beklenti 11→9 düşürülüp 2 yer tutucuyla teslim) |

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
| DOC-FS-08 | **Gereksinim izlenebilirliği — yetim gereksinim yok:** her FR/KR en az bir **süreç adımında** (§3 İş süreci) ve en az bir **test senaryosunda** (§11 Test) görünür; tersine her süreç adımı ve her test bir gereksinime bağlıdır. Kimlik numaraları (FR/KR/TC/ERR/EXC) **tekildir** — aynı numara iki farklı maddeyi taşımaz. *(Test ↔ kabul kriteri yönü DOC-CR-01 ④'tedir; bu madde gereksinim ↔ süreç ↔ test zincirini kapsar.)* | MEDIUM (EKSİK) | yok — reviewer yargısı; TS'teki karşılığı izlenebilirlik matrisi (`traceability.md` §2) |
| AX-DOC-FS-01 | **Defter/havuz tasarımında üçlü tam:** FS bir defter, havuz ya da bakiye tasarlıyorsa **giriş** (kayıt hangi belge/kalemden ve ne zaman doğar, tarih kuralı, miktar, kaynak iptal/yeniden kesim, gecikmeli dış veri) + **tüketim** (sıra kuralı, tetik, anlık görüntü, kilit) + **düzeltme/istisna/geçiş** (elle düzeltme, açılış bakiyeleri, yetim kayıt) yazılı; senaryo → sonuç tablosu var. Yalnız tüketimi anlatmak = ihlal (`fs-authoring.md` §4) | HIGH (EKSİK) | yok |

## §C — Teknik spesifikasyon (TS)
| ID | Kontrol | Önem | Mekanik yardımcı |
|---|---|---|---|
| DOC-TS-01 | Gerçek ekran görüntüsü yok; §4.5 ayrıntılı mockup + yapısal tablolar | HIGH (HATA) | yok |
| DOC-TS-02 | Zorunlu bölümler tam (genel bakış, 2-A, obje listesi, veri sözlüğü, ekran tasarımı, program/sınıf, DB erişimi, iyileştirme, form, arayüz, hata, test, 11-A, transport, onay; standart nesneye yazma varsa **§6.4 API seçimi** — reddedilenler nedeniyle, `%sap-dev` `write-api-selection.md`) | HIGH (EKSİK) | yok |
| DOC-TS-03 | **Obje adları/alanlar canlı sistemle tutarlı** (uydurma değil) ve adlandırma kuralına uygun. Klasik program include adları program kökünden türer (`%sap-dev` → `references/naming.md` §4.1); genel `_TOP`/`_F01` gibi kökten bağımsız ad yok | HIGH (HATA) | yok — canlı teyit turu C-1/C-2 kanıtı |
| DOC-TS-04 | Clean core ve yasak farkındalığı: en düşük genişletme seviyesi, 4. seviyede istisna gerekçesi; standart tablo yerine released CDS; standart obje/tabloya yazan çözüm yok; kullanılan genişletme tekniği projenin `cleancore_policy` satırıyla uyumlu ve gerekçe **seviye harfi + politika** ile yazılı (`%sap-code-review` `clean-core.md` §2.1) | MEDIUM (ÖNERİ; yasak ihlali varsa BLOCKER) | yok |
| DOC-TS-05 | **Mesaj envanteri tam (§10.1):** her mesaj; metin birebir **≤ 73 karakter**; numaralı `&1..&4` + her birinin anlamı; üretim noktası; `E`/`A`'da kullanıcı aksiyonu; metinleri kullanıcı vermiş; build'de doğan mesaj TS'e geri işlenmiş; uzun metin varsa "SE91" şerhi | HIGH (EKSİK) | yok — inceleyici yargısı |
| DOC-TS-06 | **Eski sistem izi mi, S/4 standardı mı?** Geliştirme eski (ECC) bir çözümün yeniden yazımıysa TS'teki her tasarım kararı (Z tablo/alan, arayüz temel tipi, çağrı zinciri, ekran yapısı) **neden** böyle: S/4 standardı / genel kabul gören çözüm mü, yoksa "eski sistemde böyleydi" mi? İkincisi tek başına gerekçe değildir (kullanıcının açık isteği hariç). "ECC ile aynı" ifadesi görülünce ayrım yazılı mı: **iş kuralı** (kalır) / **teknik seçim** (yeniden değerlendirildi) | MEDIUM (EKSİK) | yok — `%sap-dev` `ecc-to-s4-rewrite.md` §2 |
| DOC-TS-07 | **Obje listesi ↔ tasarım iki yönlü kapalı:** §3 Geliştirme nesneleri listesindeki **her** obje sonraki bölümlerde (veri sözlüğü · program/sınıf · veritabanı erişimi · ekran · arayüz) tasarlanmıştır — listede olup tasarımı olmayan obje **yetimdir**; tersine, tasarım bölümlerinde geçen her Z obje listededir. Her FS gereksinimi en az bir obje/metoda bağlıdır (izlenebilirlik matrisi, İlke 3). | HIGH (EKSİK) | yok — reviewer yargısı; yazım kuralı `ts-authoring.md` §5 (Bölüm 3) · `traceability.md` §2 |
| DOC-TS-08 | **Arayüz geliştirmesinde entegrasyon sayfası var ve TS ile çelişmiyor:** mesaj tabanlı / dış sistem arayüzü içeren geliştirmede entegrasyon sayfası (`templates/integration-sheet-template.md`) doldurulmuş; kaynak/hedef sistem, yön, senkron/asenkron ve eşleme tablosu TS'in arayüz bölümüyle (§9) **aynı** (iki belge iki farklı şey söylerse iki ekip iki farklı şey kurar). Örnek yük, uç nokta ya da ekran görüntüsünde **gerçek parola, token ya da kişisel veri** yok | MEDIUM (EKSİK) · gizli bilgi: HIGH (HATA) | yok |
| AX-DOC-TS-01 | İlke 5: §11-A yalnız teknik teyit; fonksiyonel karar (eşleştirme, dönüşüm, birim, kenar durum, kilit) açık bırakılmamış; §2-A boş değil | HIGH (EKSİK) | yok |
| AX-DOC-TS-02 | **Henüz var olmayan şeyin adı yer tutucudur.** TS paket yaratılmadan ÖNCE yazılır; gövdede somut bir paket adı geçiyorsa ve o paket canlıda YOKSA bu bir **uydurma**dır: `<ZPKG>` biçiminde yer tutucu kullanılır ve §2-A'ya "paket adı kullanıcıdan alınacak" satırı düşülür. Aynı kural transport numarası ve henüz yaratılmamış DTEL/domain adları için de geçerlidir. Gerekçe: uydurulan adı bu arada başkası alabilir; ayrıca yeni Z DDIC adı ancak kullanıcının açıkça onayladığı öneri olarak somutlaşır (`%sap-dev` §6: öneri + canlı kontrol + onay), standart objeye append alanı adını ise AI hiç önermez (kesin yasak A). Canlıda VAR olan bir paket adı elbette somut yazılır — ayrım "uydurma mı" sorusudur, "somut mu" sorusu değil | **BLOCKER** (HATA) | yok — canlı teyit turu C-4 (paket/inaktif) kanıtı istenir |
| AX-DOC-TS-03 | **FM imzası ↔ doküman senkron (FM kaynağı varsa — build sonrası):** parametreleri listelenen ve kaynağı yazılmış her Z FM için liste `<!-- FM-IMZA: <FM> -->` bloğunda; imzadaki her parametre blokta var (EKSİK 0), blokta imzada olmayan parametre yok (HAYALET 0). **Build öncesi TS** (FM henüz yazılmamış): blok aranmaz, eksikliği bulgu değildir; parametre listesi TS'in kendi §5/§9 tanımıyla elle tutarlı mı bakılır, blok build sonrası eklenir. Bloksuz parametre listesi araçla ölçülemez → inceleyici elle karşılaştırır (`ts-authoring.md` §5.3) | MEDIUM (HATA) | kısmi: `check_fm_signature_doc_sync.py` (yalnız parametre adları; tip/varsayılan/istisna ve bloksuz doküman elle — KAPSAM çıktısı okunur; çıkış 2 = ÖLÇÜLEMEDİ, temiz değil) |

## §D — Çapraz kontroller (tipten bağımsız, EK'ler dahil)
| ID | Kontrol | Önem | Mekanik yardımcı |
|---|---|---|---|
| DOC-CR-01 | **Ters yön:** her "A→B" varlık kontrolünün ikizi koşulur ("B var, atıf alıyor mu?"). En az dört ikiz: ① mesaj kataloğundaki her mesaj (özellikle `E`) bir üretim noktasına bağlı mı ② onaylı ad listesindeki her ad planda/uygulamada geçiyor mu ③ her DDIC alanını kim yazar / kim okur (ikisi boşsa yetim alan) ④ her kabul kriteri bir teste bağlı mı. Tek yönün temiz olması yarım sonuçtur | HIGH (EKSİK) | yok |
| DOC-CR-02 | **Sabit sayı/ad bayatlaması:** ① değişen sayı/ad dokümanın diğer tüm geçtiği yerlerde güncellenmiş mi (eski değeri doküman genelinde ara) ② ölçüt sabit sayıya değil kaynağa bağlı mı ("6+4 aktif" değil "onay listesindeki tüm adlar aktif") ③ kapsama beyanı hangi kümeyi kapsadığını söylüyor mu ("T-01…T-40 karşılandı" test kimliği tamlığıdır, kabul kriteri kapsaması değil) | HIGH (HATA) | kısmi: `doc_equivalence_check.py --closed-decision <eski değer>` |
| DOC-CR-03 | **Belge ↔ canlı teyit turu koşuldu mu:** TS build'e girmeden önce her "canlıda mevcut/kurulu/bağlı/yapılacak" iddiası ölçüldü mü (ad çakışması pozitif kontrollü, reuse imza dahil, uyarlama durumu, paket/inaktif, transport `E070`/`E071`). Kanıt = ölçüm çıktısı | HIGH (EKSİK) | yok — `live-confirmation-tour.md` raporu istenir |
| DOC-CR-04 | **Muğlak ifade kararı gizler:** "gerekirse", "uygun şekilde", "vb.", "hızlı", "büyük veri", "ileride" gibi ölçütsüz ifadeler ve **aktörsüz edilgen** ("kontrol edilir" — kim, ne zaman, başarısızsa ne olur?) somut bir ifadeye ya da **açık bir soruya** (11-B) çevrilmiş mi. Bilgi taşımayan dolgu cümleleri ve bölümler arası tekrar da bulgudur — okunamayacak kadar uzun belge bir kusurdur. | MEDIUM (EKSİK) | yok — reviewer yargısı; yazım kuralı `fs-authoring.md` §7 |
| DOC-CR-05 | **Zorunlu kesitler sessizce yok olamaz:** yetkilendirme · veri güvenliği / kişisel veri · loglama ve denetim izi · hata davranışı · iş istisnaları ve eşzamanlılık — her biri ya **tanımlı**, ya **"Yok — gerekçe"** yazılı, ya da **açık karar** (11-B) olarak işaretli mi. Bölüm başlığının var olması yetmez; boş ya da "TBD" bırakılmış kesit EKSİK'tir. | HIGH (EKSİK) | yok — reviewer yargısı; yazım kuralı `fs-authoring.md` §5 madde 6 · FS §8/§10 · TS §10 |
| DOC-CR-06 | **Kaynak izi — etiketsiz varsayım yok:** belgede adı geçen her SAP/Z objesi ya bir girdiye (gereksinim notu, canlı ölçüm, kanonik kaynak) dayanır ya da açıkça **öneri/varsayım** etiketi taşır; etiketsiz varsayım ve kaynağı belirsiz obje adı bulgudur. Satır içi açık/öneri etiketi taşıyan her yer 11-A/11-B listesinde bir satıra sahiptir ve tersi (DOC-CR-01 ters yön ilkesi). *(Etiket kaynak izidir, onay kuyruğu değildir — alıntı yeni onay turu açmaz.)* Girdi belgeleri reviewer'a verilmediyse "kaynak izi kısmen ölçüldü" yazılır, hüküm uydurulmaz. | MEDIUM (EKSİK) | yok — reviewer yargısı; etiketler `fs-authoring.md` §5 |
| AX-DOC-CR-01 | **Tüketici doküman yalnız kendi yüzeyini anlatır:** rapor (tüketici) FS/TS/KD'sinde veriyi üreten başka uygulamanın kuralı (kilit, zorunluluk, muafiyet, iptal) iddia olarak yazılmamış; varsa tek cümle + hedef dokümanın adıyla yönlendirme (hedefte içerik var). Test beklentisi rapor kolonuyla, canlı örnek raporun kendisinden. Düzeltmede kural: rapordan gözlenemeyen cümle **çıkarılır**, nitelendirilerek kurtarılmaz (`fs-authoring.md` §5.7) | HIGH (HATA) | yok |
| AX-DOC-CR-02 | **Veri garantisi cümlesi ölçülmüş:** "X boştur / X doludur / artık Y'de görünür" türü cümle için veri göçü kararı kontrol edilmiş ve eski tarihli kayıtla karşı örnek aranmış; göç yoksa cümle eski kayıtları kapsayacak biçimde daraltılmış. Dayanağı yalnız tasarım niyeti (kod yorumu, karar metni) olan garanti = ihlal (`kd-authoring.md` §7) | HIGH (HATA) | yok — ölçüm çıktısı istenir |
| AX-DOC-CR-03 | **Koda çapa kaymaz:** değişebilecek koda atıf satır numarasıyla değil metot/FORM/dal adıyla; doküman turu kod donduktan sonra koşulmuş (doküman, dayandığı kod sürümünü kaydediyor). Satır numarası varsa ölçülür, kaymışsa ada çevrilir (`traceability.md` §3) | MEDIUM (HATA) | yok |
| AX-DOC-CR-04 | **Teslim paketi = çalışma dosyası:** dışarı gönderilen paket (zip/ek/teslim klasörü) teslim anında güncel dosyalardan kurulmuş; üye özetleri çalışma ağacıyla eşit (ölçüm çıktısı); beklenen özetler eşlik eden notta; aynı yerde eski sürüm paket yok (`traceability.md` §3) | HIGH (HATA) | yok — özet karşılaştırması istenir |
| AX-DOC-CR-05 | **Kayıp tablo 0 (Markdown → HTML/PDF):** kaynaktaki tablo ayraç satırı sayısı (yalnız dikey çizgi, tire, iki nokta ve boşluktan oluşan satır) ile HTML'deki `<table>` sayısı eşit. Render olmayan tablo hata vermez; ayraç satırı ekranda ham metin kalır. Üç tetikleyici: başlık satırından önce boş satır yok (ham metin `<p>` içine düşer) · tablo liste öğesi altında girintili (`<li>` içine düşer) · tablo `<details>` ham HTML bloğu içinde. Son ikisini "`<p>` içinde ayraç" desen araması **yakalamaz** (ekip dersi: "0 kırık" diyen desen taraması 7 kayıp tabloyu kaçırdı). Parser'a bağlıdır: PDF hattı python-markdown `tables` eklentisini kullanır ve girintili tabloyu kaybeder; GitHub'da görünmesi yeterli değildir. Toplu girinti düzeltmesinden önce ve sonra sayım yapılır; kötüleşiyorsa geri alınır | HIGH (HATA) | yok — `verify_doc_html.py` tablo saymaz; iki sayı elle karşılaştırılır (kod bloklarındaki örnek tablolar ayıklanır) |
| AX-DOC-CR-06 | **İkili kaynaktan yazılan belgede kaynak izi tam:** girdi `.docx`/`.xlsx` ise belge mekanik kaynak paketinden yazılmış (`INDEX.md` DOĞRULAMA PASS) ve kaynak maddesi → belge kimliği iz tablosu `kaynak_paketi.py iz` ile **PASS** (eksik/hayalet/boş/belgede olmayan kimlik 0). BİLGİ ve KAPSAM-DIŞI işaretli her satırın kaynak metni `metin.md`'de okunmuş: gerçekten gereksinim değil mi, dışlama gerekçesi kullanıcı isteğiyle çelişiyor mu (İlke 1). Kaynak `.pdf` ise paket yoktur: inceleyici "kaynak izi ÖLÇÜLEMEDİ" yazar (`traceability.md` §2-B) | HIGH (EKSİK) | kısmi: `kaynak_paketi.py iz` (madde ↔ kimlik eşleşmesinin varlığı; anlamca doğruluk ve BİLGİ/KAPSAM-DIŞI haklılığı elle) |
| AX-DOC-CR-07 | **Kaynaktaki görseller okunmuş:** kaynak paketinde görsel (KG ya da görsel içerikli KN) varsa her biri `view` aracıyla açılmış ve `gorsel-notlari.md`'de notu o görselin işaret satırlarının (`<!-- gorulen:KG-nn -->` … `<!-- /gorulen:KG-nn -->`) arasına yazılmış (ekran adı, alanlar, düğmeler, değerler, okunabilen metin); görselden türeyen her öğe belgede bir kimliğe bağlı ve notta `→ <kimlik>` ile, iz tablosunda o görselin satırında anılıyor. İnceleyici her görseli kendisi `view` ile açar ve notu görselle karşılaştırır: görselde olup notta ya da belgede olmayan alan/düğme/değer = bulgu. GÖRÜNTÜLENEMEZ biçimin (ör. `emf`) okunabilir kopyası `media/<kimlik>.kullanici.png` varsa inceleyici o PNG'yi açar ve notun dönüştürülmüş/kullanıcı PNG'sinden okunduğunun yazılıp yazılmadığını denetler; kopya yoksa "ÖLÇÜLEMEDİ — biçim" yazar; PNG yedeği olan SVG o PNG'den okunur, SVG dosyası `view` ile açılmaz (SVG'de `view` ölçülmedi) (`traceability.md` §2-B "Görsel okuma"). Ekran görüntüsü okunmadan yazılan FS, görseldeki istekleri sessizce düşürür (kullanıcı geri bildirimi) | HIGH (EKSİK) | kısmi: `kaynak_paketi.py iz` (yalnız işaretler arası okunur; boş not = GÖRSEL OKUNMADI FAIL, kullanıcı PNG'si olan görselde de; işareti eksik/bozuk not = GÖRSEL NOTU BOZUK FAIL; notta olup iz satırında olmayan kimlik = UYARI; notun görselle uyumu elle) |

## Hüküm
- **PASS** → bitti denebilir.
- **WARNING** → yayınlanır; bulgu kullanıcıya/rapora yansıtılır.
- **BLOCKER** (ya da açık HATA/EKSİK) → düzelt + tekrar kapı (ikinci kapı kuralıyla). En sık BLOCKER'lar: DOC-KD-01 ve DOC-KD-03.
- Kontrol listesi dışı iyileştirme `[ÖNERİ]` olarak yazılır (bağlayıcı değil). Tekrar eden yeni doküman tuzağı bulunursa buraya
  satır **önerilir**: aXet'e özgü yeni madde `AX-DOC-<tip>-<nn>` alır (sıradaki: KD `AX-DOC-KD-02`, FS `AX-DOC-FS-02`,
  TS `AX-DOC-TS-04`, CR `AX-DOC-CR-08`); çekirdek `DOC-*` ailesinde numara verilmez (kök test takımındaki kimlik hizası
  testi zorlar). Template değişikliği → kullanıcı onayı.

## §E — Bağımsız inceleme brifingi (`agent` aracına yapıştırılır)
Alt ajan bu dosyayı, skill'i, çekirdek kuralları ve konuşmayı **görmez**; aşağıdaki `<…>` yerlerine ilgili bölümlerin
**metnini** yapıştır. Genel kanıt ve çıktı bölümleri için `skills/explore/references/brief-template.md` §5/§7/§8 eklenebilir.

**İkili kaynak brife YOL olarak verilmez.** Girdi `.docx`/`.xlsx`/`.pdf` ise yolu verilmez: `view` ikili `.docx`'i açmadı
("File appears to be binary"), alt ajan okuyamadı ve ~20 dk dolambaçlı aramayla okumaya çalıştı (ölçüldü — aXet.code
1.5.1, 2026-11-19, iki koşu: talimatsız ve "read_docx kullan" denince; yerleşik görev alt ajanının araç kümesi glob, grep,
ls, sourcegraph, view — read_docx, read_xlsx, read_pdf ve kabuk yok; `.xlsx`/`.pdf` denenmedi). Proje dışındaki yol izin sorusunda asılı
kalabilir. Brife **kaynak paketinin** proje içindeki yolu verilir (`.axet-code/tmp/<id>/INDEX.md`,
`kaynak_paketi.py cikar` — `traceability.md` §2-B). Kaynak metnini kendin yazıp dosyaya koyma: model yeniden yazınca
kısaltır (ölçüldü: 21 test satırı → 13, bir başlık düştü). Brife kaynak paketi yalnız `.docx`/`.xlsx` için verilir.
Paket `.pdf` için üretilemez (`kaynak_paketi.py` çıkış 3): kullanıcıdan `.docx`/`.xlsx` hâlini iste ya da metni çıkarıp
dosyaya yaz, o dosyanın yolunu ver (metni modelle yeniden yazma) ve brife "kaynak: PDF, paket yok, kaynak izi ÖLÇÜLEMEDİ"
yaz.

**Brif yalnız metin ve görsel yolu taşır; betik koşturma adımı içermez.** `agent` çağrısında ajan türü verilmezse yerleşik
görev ajanı açılır; kabuk ve `read_docx`/`read_xlsx` yoktur. Ölçüldü (aXet.code 1.5.1, 2026-11-19): yerleşik görev
alt ajanının araç kümesi glob, grep, ls, sourcegraph, view (motor logu tools=5); `.docx`'i iki koşuda da okuyamadı
(talimatsız ve "read_docx kullan" denince); paket yolları verilince (`INDEX.md`, `metin.md`, `media/KG-01.png`) tablo
değerini ve görseldeki kodu 45 sn'de doğru okudu. Bu yüzden `kaynak_paketi.py iz`'i ana oturum koşar ve çıktısını brife
yapıştırır. İnceleyici `metin.md`, `INDEX.md`, `gorsel-notlari.md` ve `media/` ile `gomulu/` altındaki görüntülenebilir
biçimdekileri (varsa `media/<kimlik>.kullanici.png` kopyalarını da) `view` ile açar; bunun için görev ajanı da yeter.
Şablonun salt-okur `sap-inceleme` ajanı kuruluysa (`agents/sap-inceleme.md`) o da kullanılabilir.

```text
GÖREV (SALT OKUMA — DOKÜMAN İNCELEMESİ): Aşağıdaki <FS|TS|KD> dokümanını kontrol listesine karşı incele.
Hiçbir dosyayı değiştirme, yazan komut çalıştırma, SAP'ye bağlanma.
DOKÜMAN: <md yolu>  ·  ÜRETİLEN: <html / pdf / screenshots klasörü yolları | yok>
İLGİLİ DOKÜMANLAR: <FS no/yolu ↔ TS no/yolu ↔ KD no/yolu | yok>
KAYNAK PAKETİ: <proje içi .axet-code/tmp/<id>/INDEX.md (metin.md · gorsel-notlari.md · media/ · gomulu/) | kaynak md yolu | yok>
İZ TABLOSU: <<source_root>/<MODÜL>/<PAKET>/ref_docs/iz-<belge no>.md + ana oturumun koştuğu `kaynak_paketi.py iz` çıktısı (aynen) | yok>
KANIT EKLERİ: <canlı teyit turu raporu | denklik raporu | ekran envanteri eşleme tablosu | yok>
BU TUR: <ilk inceleme | İZ TABLOSUNA DAYALI İNCELEME | İKİNCİ KAPI — yalnız: değişen satırlar <liste>,
        değişen sayı/adlar <liste>, yayılım listesi <liste>>

KONTROL LİSTESİ (metin):
<doc-checklist.md: ilgili tip bölümü (§A/§B/§C) + §D + "İkinci kapı" metni — tablo satırlarıyla birlikte>

İNCELEME KURALLARI:
- Her bulgu: madde ID + doküman konumu (başlık/bölüm no ya da dosya:satır) + somut sorun (ne yazıyor → neden ihlal).
- Doğrudan okunabilen bir iddiayı okumadan bulgu yapma. Görsel maddelerde görüntü dosyasını aç.
- KAYNAK PAKETİ varsa gorsel-notlari.md'deki her görseli (KG/KN) `view` aracıyla AÇ ve notu doğrula (AX-DOC-CR-07):
  not görseldeki ekran adını, alanları, düğmeleri, değerleri ve okunabilen metni karşılıyor mu; görselde olup notta ya
  da belgede olmayan alan/düğme var mı. GÖRÜNTÜLENEMEZ yazan görselin `media/<kimlik>.kullanici.png` kopyası varsa onu
  aç ve notta PNG'den okunduğunun yazılıp yazılmadığına bak; kopya yoksa açmayı deneme, "ÖLÇÜLEMEDİ — biçim" yaz.
- "Bulunamadı" demeden önce hangi başlık/deseni aradığını yaz. Bir script raporu verildiyse KAPSAM satırındaki
  "bakmadıkları"nı ayrıca kendin incele; script'in 0 bulgusu o yüzeyde temiz demek değildir.
- Ölçemediğin maddeye "ÖLÇÜLEMEDİ" yaz, geçme.
- Checklist dışı iyileştirme [ÖNERİ] olarak ayrı listelenir.
- İZ TABLOSUNA DAYALI İNCELEME'de belgeyi baştan sona okuma. Sıra: ① iz çıktısı FAIL ise BLOCKER (AX-DOC-CR-06), dur
  ② her eşleme satırında kaynak maddesinin metin.md metnini ve eşlenen kimliğin belgedeki satırını yan yana oku:
  istek karşılanmış mı, kısaltılmış/değiştirilmiş mi ③ BİLGİ ve KAPSAM-DIŞI işaretli her maddeyi metin.md'de oku
  ④ belgede tabloda anılmayan gereksinim (iz çıktısındaki UYARI) kaynaksız mı, öneri olarak işaretli mi ④b her
  görseli `view` ile aç, notunu ve iz satırını görselle karşılaştır (AX-DOC-CR-07) ⑤ kontrol
  listesinin yalnız yargı isteyen maddeleri (mekanik yardımcısı "yok" olanlar) için ilgili bölümü oku.
  Okumadığın bölümü madde durumunda "ÖLÇÜLEMEDİ — iz kipinde okunmadı" diye yaz.
ENGEL: dosya okunamıyor ya da kapsam belirsizse o maddede ilerleme; yanıtın ilk satırına "ENGEL: <ne · neden>" yaz.
ÇIKTI (tek yanıt): 1) Bulgular önem sırasıyla [BLOCKER | HIGH | MEDIUM | ÖNERİ] + ID + konum + sorun
2) Madde bazında durum: her ID → UYGUN / BULGU / ÖLÇÜLEMEDİ / UYGULANMAZ (gerekçe)
3) Son satır tek hüküm: PASS / WARNING / BLOCKER
```
Dönen rapordaki her BLOCKER ana oturumda dokümandan okunarak doğrulanır; doğrulanamayan NOT'a indirilir.
