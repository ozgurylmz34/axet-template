# İzlenebilirlik, numaralandırma, değişiklik ve veri kaybı kontrolü

## 1. Numara, dosya adı, durum
```
No    : <TİP>-<MODÜL>-<SIRA>          FS-SD-001 ↔ TS-SD-001 ↔ KD-SD-001 = aynı geliştirme
Dosya : <TİP>-<MODÜL>-<SIRA>_<Ad>_v<Sürüm>.md   (PDF/HTML aynı gövde adıyla)
        FS-SD-001_Siparis_Onay_Ekrani_v1.0.md · TS-SD-001_<ANA_OBJE>_v1.0.md · KD-SD-001_Siparis_Kullanici_Kilavuzu_v1.0.md
F1    : DOCU-<MODÜL>-<SIRA>_<Uygulama>_GUI_Yardim.md   (yalnız klasik GUI KD'sinde)
Yer   : <source_root>/<MODÜL>/<PAKET>/docs/     (kaynak/dönüşüm belgeleri ref_docs/ altında; canlı teslimat değil)
```
- İlk `_` öncesi doküman kimliğidir; üretici (Mermaid PNG ön eki) buna dayanır. Aynı klasörde iki doküman aynı kimliği taşımaz.
- **Durum akışı:** `Taslak → İncelemede → Revize Gerekli → Onaylandı → Arşivlendi` (Revize Gerekli → İncelemede döngüsü).
- **Modül kodları:** SD · MM · FI · CO · PP · PM · QM · HR · WM/EWM · PS · BC (temel/modüller arası).
- **Teslim biçimi (varsayılan; proje başka karar verebilir):** FS ve TS için `.md` + `.pdf`. HTML yalnız PDF'e giden yolda
  **ara üründür**, sürüm kontrolüne alınmaz ve ayrıca güncellenmez; FS/TS için "HTML bayat" diye bulgu yazılmaz. KD için
  `.md` + `.pdf` + `.html`, çünkü KD'nin HTML'i uygulama içi yardım kopyası olarak kullanılır (`kd-authoring.md` §8).
  Gerekçe: kimsenin okumadığı üçüncü bir biçimi senkron tutmak her doküman turuna maliyet ekler.

## 2. İzlenebilirlik matrisi (TS'te zorunlu)
| FS gereksinim | FS açıklaması | TS bölümü | TS obje/metot | Test |
|---|---|---|---|---|
| FR-001 | <kısa> | §5.3 | `<SINIF>=>METOT` | UT-001, IT-001 |

- FS'teki **her** FR/KR bir satırdır; boş hücre = eksik TS (İlke 3).
- Kabul kriteri → test bağlantısı ters yönde de kontrol edilir: her test bir kabul kriterine, her kabul kriteri bir teste (DOC-CR-01 ④).
- Matris kaynağa bağlıdır: "N gereksinim karşılandı" yerine "FS §4.1'deki tüm FR'ler" yazılır (DOC-CR-02).
- KD tarafında: FS'teki her kullanıcıya görünen işlev (ekran, buton, mesaj) KD'de bir bölüme karşılık gelir.

## 2-B. Kaynak paketi ve kaynak → belge iz tablosu (FS ikili bir istek belgesinden yazılıyorsa)
Kullanıcının isteği `.docx`/`.xlsx` olarak geldiyse oturumun **ilk** işi kaynak paketidir; intake, FS yazımı ve
inceleyici aynı paketi okur. Kaynak metni model yeniden yazmaz, özetini kaynağın yerine koymaz.
```
python <TEMPLATE>/skills-sap/sap-fs-ts-docs/scripts/kaynak_paketi.py cikar <istek.docx|.xlsx>
      → <proje>/.axet-code/tmp/<ad>-<özet8>/  INDEX.md · metin.md · gorsel-notlari.md · media/ · gomulu/ · paket.json   (git dışı)
python <TEMPLATE>/skills-sap/sap-fs-ts-docs/scripts/kaynak_paketi.py iz <paket> \
      --tablo <source_root>/<MODÜL>/<PAKET>/ref_docs/iz-<belge no>.md --belge <FS.md>
```
- **Paket:** `metin.md` kaynağın **çıkarım kapsamındaki** metnidir, sırası korunur; her başlık, paragraf ve metinli
  tablo satırı bir **kaynak maddesi** `KM-nnnn`. Metin kutusunun paragraf ve tabloları bulunduğu paragrafın satırına,
  iç içe tablo hücre metnine düzleşir; denklem metni satır içinde `⟦denklem⟧` işaretiyle durur. SmartArt (`D01`) ve
  grafik (`G01`; başlık, seri, kategori ve değer metni, ChartEx kategorileri dahil) kendi KM satırındadır; xlsx'te
  çizimdeki metin kutuları (`K01`) de. Her görsel `KG-nn`, her gömülü nesne `KN-nn` (OLE paket nesnesinin asıl
  dosyası — ör. danışmanın HTML ekran prototipi —, OLE içindeki Excel/Word, altChunk; tanınmayan ya da bozuk nesne ham
  kopyalanır ve INDEX'te "TANINMADI" yazar; 100 MiB'ı ya da görsel/gömülü toplamını (1 GiB) aşan görsel/gömülü nesne
  çıkarılmaz, yerinde not dosyası ve INDEX'te "ÖLÇÜLEMEDİ — boyut" durur; metin korunur). XML olmayan diğer zip üyeleri
  (ör. `.docm`'deki makro kodu `vbaProject.bin`, düz metin dosyası, belge küçük resmi) metne çıkmaz ama sessizce de
  kaybolmaz: INDEX ve `paket.json` (`xml_disi`) adını, boyunu ve notunu yazar — makro kodu "okunmadı, iş kuralı
  içerebilir" notuyla; kullanıcıya sor.
- **Geri düşüş:** yapılandırılmış çıkarımın kapsamadığı her XML parçasının metni (üst/altbilgi, dipnot, yorum,
  grafiğin üstündeki metin kutusu, tanınmayan parçalar) ve yapılandırılmış parçalarda satıra girmeyen metin,
  `metin.md` sonundaki **"Yapılandırılmamış parça metni"** bölümüne ham yazılır: `[KM-nnnn] ⟦P01 parça: <zip
  parçası>⟧ | metin |` (paragraf altında birleşik; sayfa/hücre yapısı yoktur). Bunlar da kaynak maddesidir, iz
  tablosunda yer alır. INDEX hangi parçaların geri düştüğünü listeler — okurken bu parçaları ayrıca değerlendir.
- **Doğrulama:** `INDEX.md` kaynağın ayrı kodla yapılan sayımını (madde, başlık, tablo, satır, karakter, denklem,
  SmartArt, grafik, metin kutusu, görsel, gömülü nesne; xlsx'te karakter yalnız metin hücrelerinden) diskteki
  paketle karşılaştırır. Ayrıca **parça hesabı**: zip'teki HER XML parçasının metni, çıkarımın parça listesinden
  bağımsız taranır ve parça başına `evren − yok sayılan = yapılandırılmış + geri düşüş` aranır; muaf (yapısal)
  parçalar listesi SCOPE'ta basılır, her muaf parça INDEX'te metin karakteriyle görünür. Yok sayılan sınıflar dardır
  ve her biri DOĞRULAMA satırında karakter sayısıyla basılır: metni (boşluksuz) Choice'unkiyle AYNI `mc:Fallback`
  (karakter sayısı eşitliği yetmez), alan kodu (`instrText`; alan sonucu alınır), silinen metin, formül/başvuru (`f`
  yalnız sayfa ve grafik parçalarında, `definedName` yalnız `xl/workbook.xml`'de), sayı biçim kodu (yalnız grafikte),
  konum/ölçü değeri (yalnız değeri sayı ya da hizalama sözcüğüyse; Excel VML açıklama kutusunun `x:Row`/`x:Column`/
  `x:Anchor` sayıları dahil), mürekkep koordinatı (`inkml:trace`, yalnız `ink/` parçasında), fonetik okunuş. Aynı
  yerel ad başka parçada ya da metin değeriyle geçerse geri düşüşe gider. xlsx sayfa ve paylaşılan dizge
  parçalarında **"yapılandırılmış (kaynaktan; pakette yalnız metin hücresi ölçülür)"**: bu parçaların payı hücre
  tanımından hesaplanır; paket satırı hücrenin biçimli gösterimini taşıdığından sayı/tarih hücresinin pakete doğru
  yazıldığını parça hesabı ölçmez (metin hücrelerinin karakteri ayrıca pakete karşı ölçülür).
  **DOĞRULAMA FAIL olan paket kullanılmaz.** Çıkış `2` = okunamadı (bozuk zip, başlıktaki boy/CRC içerikle
  uyuşmuyor) ya da boyut sınırı (metin parçası 100 MiB, açılmış metin üyeleri toplamı 512 MiB — görsel/gömülü
  üyeler bu toplama sayılmaz; her üye gerçekten açılarak sayılır) aşıldı; çıkış `3` = biçim desteklenmiyor (`.pdf`, `.doc`, `.xls`):
  kullanıcıdan `.docx`/`.xlsx` hâlini iste ya da metni çıkarıp dosyaya yaz, o dosyanın yolunu ver; kaynak izi
  "ÖLÇÜLEMEDİ" kalır, metni modelle yeniden yazıp paket gibi sunma.
- **Kapsam dışı (INDEX'te yazar):** öznitelikteki metin (görsel alternatif metni, veri doğrulama istemi, köprü
  ipucu, içerik denetimi açılır liste seçenekleri `w:listItem` ve adı `w:alias`), XML olmayan üyelerin içeriği
  (makro kodu dahil), Word'ün otomatik numaraları, gömülü dosyanın ve görselin içindeki metin, xlsx'te sayı/tarih hücresinin
  biçimli gösterimi (satırda durur, karakter sayımına girmez) ve nesnenin hangi hücrede durduğu. Gömülü HTML prototip
  tarayıcıda açılır; ekranı `capture_kd_screens.js` `file://` adresinden çeker.
- **Görsel okuma (zorunlu adım — model okur, `iz` sayar):** mekanik çıkarım görselin içindeki metni almaz (yukarıdaki
  kapsam dışı satırı bu yüzden doğrudur); ekran görüntüsündeki alan, düğme ve değerler ise çoğu zaman gereksinimdir.
  Paket her `KG-nn` için ve içeriği görsel olan her `KN-nn` için (ör. OLE paketindeki `.png`) `gorsel-notlari.md`'de bir
  bölüm üretir: dosya yolu, kaynak parçası, konum (işaretin durduğu `KM` satırı; xlsx'te ve başvurusuz görselde
  "konumu yok"), biçim ve arası boş bir **işaret çifti** (`<!-- gorulen:KG-nn -->` … `<!-- /gorulen:KG-nn -->`). Model
  her görseli **`view` aracıyla açar** ve gördüğünü — ekran ya da pencere adı, alanlar, düğmeler, tablo sütunları,
  değerler, okunabilen metin; madde listesi ve tablo da olur — **yalnız o görselin işaretlerinin arasına** yazar;
  **görsel başına bir `edit`** (uzun içerik bölüm bölüm). FS'e giren her öğenin yanına belge kimliği yazılır
  (`→ FR-003`) ve o görselin iz tablosu satırı aynı kimliği taşır; logo ya da süsleme gibi gereksinim taşımayan
  görsel `BİLGİ`'ye bağlanır, notu yine yazılır. Aynı kaynak, aynı km şeması ve aynı not biçimiyle yeniden `cikar`
  yazılmış notları silmez. Kaynak, km şeması ya da not biçimi değiştiyse ya da imza satırı silindiyse eski notlar
  `gorsel-notlari.<özet8|özet8-sema<n>|özet8-bicim<n>|imzasiz>.md` adıyla, o anki `media/<kimlik>.kullanici.png`
  kopyaları da (ad harfe duyarsız tanınır, `.PNG` dahil; ad korunur) `kenar/<aynı ad>/` altına kenara alınır — kullanıcı PNG'si kaynağa bağlıdır, başka kaynağın aynı
  kimlikli görseli onunla açılmaz. Var olan kenar kaydı ezilmez (sıra numarası eklenir) ve aynı kaynak yeniden
  çıkarılınca o kaynağın kenardaki notları PNG kopyalarıyla birlikte geri yüklenir; okunamayan (UTF-8 olmayan) kenar
  dosyası atlanır ve UYARI yazılır. Not dosyası silinip aynı kaynak yeniden çıkarılırsa `media/`'daki kullanıcı PNG'si
  `kenar/kullanici-png.sahipsiz/` altına alınır ve kendiliğinden geri gelmez — PNG'yi elle `media/`'ya geri koy. Eski işaretsiz not biçimi dönüştürülmez, kenara alınır (notu yeni iskelette
  işaretlerin arasına taşı). **Not sınırı açık işarettir:** `iz` notu YALNIZ işaret çiftinin arasından okur; Markdown
  biçimine (başlık, yatay çizgi, alıntı, paragraf) bakılmaz. Bir görsel bölümünde işaretlerin dışında kalan metin
  sayılmaz ve UYARI'dır; yinelenen işaret çifti UYARI'dır (ilki sayılır); açılışı ya da kapanışı eksik, sırası bozuk
  ya da başka kimliğin kapanışıyla biten not **GÖRSEL NOTU BOZUK** = FAIL. Harf ya da rakam içermeyen not ("-", "?")
  ve TODO, "(boş)", "doldurulacak", "n/a", "tbd", "yok", "none", yalnız x'lerden oluşan dizgi gibi yer tutucular boş
  sayılır; notun TAMAMI "okunamadı", "görülmedi", "henüz yok", "görsel açılamadı" gibi bir ifade ya da yalnız bir kimlikse
  ("KG-02") not boştur (cümle içinde geçmesi notu boşaltmaz); işaretlerin arasına düşmüş iskelet satırı ("## KG-nn", "- Dosya: …", Görülen satırı), başlık, kapanmamış
  yorum (`<!--`), boş kod çiti, HTML boşluğu/etiketi (`&nbsp;`, `<br>`) ve Markdown görsel bağlantısı not sayılmaz.
  **Görüntülenebilir biçimler** betikte tek listededir: görüntülenebilir biçim (`GORUNTULENEBILIR`); belge listeyi
  kopyalamaz, güncel liste INDEX'in "Görsel okuma" bölümündedir. Ölçüldü (aXet.code 1.5.1, 2026-11-19/20): `view`
  EMF/WMF/BMP açmaz; Word ekran görüntülerini sık sık EMF/WMF olarak gömer. Listede olmayan biçim INDEX'te ve notta
  **"GÖRÜNTÜLENEMEZ (emf)"** yazar. Okunabilir kopyanın tek bir sabit adı vardır: `media/<kimlik>.kullanici.png`.
  Pillow kuruluysa paket klasöründe `python -c "from PIL import Image; Image.open('<görsel>').save('media/<kimlik>.kullanici.png')"`
  ile çevir ve PNG'yi `view` ile aç; olmazsa kullanıcıdan PNG iste ve aynı ada kaydet (Pillow'la EMF çevirisi yalnız
  Windows'ta ölçüldü). Kopya varken boş not FAIL'dir; notta PNG'den okunduğunu belirt. Paketin kendisi dönüştürmez:
  standart kütüphane EMF/WMF'yi PNG'ye çeviremez ve betiğe bağımlılık eklenmez. Word SVG'yi PNG yedeğiyle birlikte
  saklar (`svgBlip`): yedek pakette varsa SVG ÖLÇÜLEMEDİ değildir, o PNG'nin bölümünde okunur (SVG dosyası `view`
  ile açılmaz — SVG'de `view` ölçülmedi). Sözlük/yapı taşı belgesinin görselleri (`word/glossary/`), gövde parçaları
  (belge, üst/altbilgi …) başvurmadıkça belge gövdesinde görünmez: KG sayılmaz, not istenmez, INDEX'in XML dışı üye listesinde bu notla durur. Görsel, klasör adından
  değil görsel ilişkisinden ve uzantısından tanınır; dosyaya bağlanamayan başvuru (`⟦… başvurusu çözülemedi⟧`) ve dışa
  bağlı görsel (`⟦harici görsel bağlantısı — pakette yok⟧`) INDEX'te ve `iz`'de UYARI'dır.
- **İz tablosu** git'te izlenen yerde durur: kaynak paketinin yanında değil, FS'in SAP paket klasöründe
  `ref_docs/iz-<belge no>.md` (kaynak ve dönüşüm belgelerinin yeri; FS gövdesine girmez — İlke 2b). Ölçüldü: proje
  şablonunun `.gitignore`'larıyla `git check-ignore` bu yolu izler, `.axet-code/tmp/**`'yu yok sayar. Kaynak paketi
  git dışıdır; kimlikleri yeniden üretmek için **kaynak ikili dosya** da saklanır — iz tablosunun yanında,
  `ref_docs/` altında (müşteri belgesiyse projenin kaynak belge kuralına göre). Aynı kaynaktan **aynı betik
  sürümüyle** (aynı `km şeması`) `cikar` aynı kimlikleri yeniden üretir; betik numaralandırmayı değiştirdiyse şema
  artar ve eski tablo yeni pakete karşı `iz`'de **FAIL** verir ("NUMARALANDIRMA ŞEMASI FARKLI — paketi yeniden
  çıkar, tabloyu yeniden eşle"). Bu yüzden tablonun ilk satırı kaynağı ve şemayı adlandırır:
  `Kaynak: <dosya adı> · sha256 <ilk 16 hane> · km şeması <n>` (`iz` çıktısının `kaynak:` satırından kopyalanır).
  Her kaynak maddesi bir satırda; aralık yazılabilir (`KM-0004..KM-0009`):

| Kaynak | Belge kimliği | Not |
|---|---|---|
| KM-0001..KM-0006 | BİLGİ | kapak, doküman kontrolü |
| KM-0007 | FR-001, KR-002 | |
| KM-0021 | TC-01 | kaynaktaki test satırı 1 |
| KM-0022 | TC-02 | (belge kimliği aralıkla yazılmaz; her biri ayrı) |
| KM-0042 | KAPSAM-DIŞI | standart nesne değişikliği — kesin yasak A, kullanıcıya soruldu (S-03) |
| KN-01 | SCR-001, SCR-002 | HTML prototip |
| KG-03 | SCR-001, FR-004 | sipariş giriş ekranı görüntüsü (gorsel-notlari.md) |

  `BİLGİ` = gereksinim taşımayan madde · `KAPSAM-DIŞI` = bilerek alınmayan madde, gerekçe zorunlu. Geri kalan her
  satır belgede gerçekten geçen kimlik(ler)e bağlanır. `iz` denetimi: tabloda olmayan madde · pakette olmayan madde ·
  boş eşleme · belgede olmayan kimlik · gerekçesiz KAPSAM-DIŞI · tablodaki sha256'nın ya da km şemasının paketinkiyle
  uyuşmaması · notu (işaretler arası) boş görüntülenebilir görsel (`GÖRSEL OKUNMADI: 2 — KG-02, KG-05`), işareti
  eksik ya da bozuk not (`GÖRSEL NOTU BOZUK`) ya da eksik `gorsel-notlari.md` = **FAIL**; görüntülenemeyen biçimin boş notu = **ÖLÇÜLEMEDİ** (FAIL değil; SONUÇ satırı PASS'in
  bu görselleri kapsamadığını yazar); aynı madde iki satırda, belgede olup tabloda anılmayan FR/KR, görsel notunda
  anılıp o görselin iz satırında olmayan kimlik, not dosyasında işaret dışında kalan metin ya da yinelenen işaret
  çifti, boş paket (0 madde), sha256'sız ya da km şemasız tablo = UYARI.
  **Ölçmedikleri:** eşlemenin anlamca doğruluğu, BİLGİ/KAPSAM-DIŞI işaretinin haklılığı ve görsel notunun görseli
  doğru anlatıp anlatmadığı (`iz` yalnız notun dolu olduğunu sayar) — inceleyici bunları okur, görselleri `view` ile
  açar (`doc-checklist.md` §E "İZ TABLOSUNA DAYALI İNCELEME", AX-DOC-CR-06, AX-DOC-CR-07).
- TS için kaynak FS'in kendisidir: §2 matrisi FS'in her FR/KR'sini satır olarak taşır, iz tablosu yerine geçer.

## 3. Değişiklik kuralları
- FS değişirse → TS güncellenir → versiyon artar → yeniden onay.
- TS değişirse → FS değişikliği gerekmeyebilir → teknik lider onayı yeter; FS'i etkiliyorsa FS §11-A/§11-B'ye döner.
- Arayüz değişirse → KD aynı revizyonda güncellenir; klasik GUI'de F1 yardımı da.
- Build sırasında yeni mesaj ya da alan doğarsa TS **önce** revize edilir, sonra kodlanır.
- Belgeler proje kapanışına kadar güncel tutulur.
- **Doküman turu donmuş kod ister.** TS/KD, ekran görüntüleri ve PDF kodun o anki hâline bağlıdır: satır referansları,
  mesaj metinleri, görüntüler. Kod düzeltme turu sürerken doküman turu **başlatılmaz**; sıra seridir: kod donar (dosya
  özeti/commit kaydedilir) → doküman turu. Paralel koşturmak zaman kazandırmaz: referanslar kayar, görüntüler yeniden
  çekilir ve kusur **sessizdir** (doküman derlenir, inceleme geçer, yanlışlık ancak satır açılınca görülür). Tur yine de
  çakışmak zorundaysa doküman yazarına sabit bir dosya özeti verilmez; yazar başlarken kendisi ölçer, tutmuyorsa durur
  ve sorar. Aynı turda dosya sahipliği açıkça bölünür (bir dokümana tek yazar).
- **Koda çapa ad ile atılır, satır numarasıyla değil.** Doküman değişebilecek koda metot/FORM/dal adıyla bağlanır (ad
  da yazılmadan önce kaynakta doğrulanır); satır numarası ilk düzeltmede kayar (AX-DOC-CR-03).
- **Dışarı gönderilen paket ayrıca ölçülür.** Zip, e-posta eki ya da teslim klasörü çalışma dosyasının bir kopyasıdır ve
  hiçbir inceleme onu görmez: kaynak dosya düzeltilince paket sessizce bayatlar. Paket **teslim anında** güncel dosyalardan
  yeniden kurulur ("zaten kurmuştum"a güvenilmez) · açılıp üye üye özet (md5/sha) alınır ve çalışma ağacındaki dosyayla
  eşitliği ölçülür (boyut yetmez) · beklenen özetler eşlik eden nota yazılır ki alıcı doğrulayabilsin · eski sürüm
  paketler aynı klasörde bırakılmaz (yanlışının gönderilme riski) (AX-DOC-CR-04).

## 4. Karar yayılımı ve ikinci kapı
Bir karar birden çok yerde yaşar (gövde kuralı, ekran tablosu, sözde kod, test, ek belge, onay listesi). Her karar kaydında
**yayılım tablosu** tutulur: `Karar no | Dokunulacak yer | Durum | Kim / ne zaman`. Liste tamamlanmadan karar kapanmış sayılmaz;
boş tablo kayıt geçersizdir. Düzeltme turu **ikinci kapıdan** geçer (`doc-checklist.md` — değişen satırlar, değişen sayı/adın
diğer geçtiği yerler, yayılım listesi; başka taze inceleyici).
Değişen bir sayı/adın eski değeri teslimden önce doküman **genelinde** aranır (`grep` ya da `doc_equivalence_check.py --closed-decision`).

## 5. Yeniden yazımda veri kaybı — `doc_equivalence_check.py`
FS gövdesi temizlenirken (İlke 2b) ya da doküman yeniden düzenlenirken çıkan her bilgi EK'e taşınır; kayıp ölçülür:
```
python <TEMPLATE>/skills-sap/sap-fs-ts-docs/scripts/doc_equivalence_check.py --old ESKI.md --new YENI.md --new EK-KARAR.md \
       [--closed-decision <kapanmış kararın eski değeri> …] [--report RAPOR.md]
```
| Ölçüm | Ne | Geçme koşulu |
|---|---|---|
| 0 Kapsam | taranan dosyalar + aynı klasörde **taranmayan** `.md` uyarısı | paket dosyaları eksiksiz verildi |
| 1 Kimlikler | FR-/BR-/AC-/TC-/SCR-/S-/K… kimlik kümeleri | eski \ yeni = boş |
| 2 Mockup/kod blokları | eski bloğun satırlarının ≥ %90'ı yeni kümede | kayıp blok yok |
| 3 Değerler | BÜYÜK_HARF obje/alan adları, 4+ haneli sayılar, tarihler, `kod` tokenları | eski \ yeni = boş (harf duyarsız) |
| 4 Cümleler | eski her cümle (≥ 40 karakter) yeni kümede bulanık eşleşmeyle | kayıp oranı ≤ eşik (varsayılan %3) |
| 5 Ters yön | `--closed-decision` değeri yeni pakette hâlâ geçiyor mu | geçiş yok ya da her geçiş "reddedilen alternatif" diye açıkça yazılı |

Çıkış: `0` denk · `1` kayıp var ya da kapanmış karar yaşıyor · `2` girdi okunamadı (bu "denk" **değildir**).
Rapor inceleyiciye kanıttır. **Aracın ölçmedikleri** (rapor §6): yeni içeriğin doğruluğu, belgeler arası tutarlılık, korunmuş ama
geçersiz değer (`--closed-decision` verilmezse), kapsam seçimi. Yeşil = "kayıp yok", "doküman doğru" değil.

## 6. Mevcut kaynaktan taslak spesifikasyon — `program_to_spec.py`
Eski ya da mevcut bir ABAP/CDS kaynağından yalnız **kaynakta gerçekten olan** teknik olguları (tablolar, seçim parametreleri,
çağrılan FM/BAPI, FORM/METHOD, ekran numaraları, sınıf/CDS varlıkları) çıkarır; anlatı bölümlerini `<TODO: …>` bırakır.
```
python <TEMPLATE>/skills-sap/sap-fs-ts-docs/scripts/program_to_spec.py <kaynak.abap> [<kaynak2.abap> …] [--out docs/TASLAK_<ad>.md]
```
- Kaynak yerelde yoksa önce `%sap-adt-foundation` ile okunur (`adt_get … include_source=true`); sistemden okunan kaynak taze kabul edilir.
- Çıktı **taslaktır**: `<TODO>`'lar kullanıcı spesifikasyonu ve çalışan uygulama davranışından doldurulur (tahmin yok), sonra
  şablona taşınır ve **spec mutabakatı** yapılır; mutabakatsız build yok.
- Regex tabanlıdır: yorum satırları (`*`) atılır, satır içi `"` yorumları ve makro/dinamik çağrılar ayrıştırılmaz; standart tablo
  listesi "Z/Y ile başlamayan" ipucudur, sistemde varlığı teyit edilir. "Tespit edilemedi" = "yok" değildir.
