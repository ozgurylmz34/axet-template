# TS yazımı — Teknik Spesifikasyon

> TS, FS'teki gereksinimlerin SAP'de **nasıl** gerçekleştirileceğini tanımlar; geliştirici TS'i okuyarak tahmin etmeden
> kodlayabilmelidir. **FS olmadan TS yazılmaz.** Şablon: `templates/TS-template.md` · İnceleme: `doc-checklist.md` §C + §D ·
> Build öncesi: `live-confirmation-tour.md`.

## 1. Yazım zihniyeti — geliştirici gözü (önce oku)
TS'i **bu TS'le sen build edeceksin** gibi yaz. Satır 1'den önce geliştiricinin soracağı her soruyu şimdi cevapla.

### İlke 3 — FS kaynak otoritedir
TS'in birincil görevi FS'teki **her** FR/KR'ye teknik çözüm üretmektir. Hiçbir FS maddesi çözümsüz kalmaz: izlenebilirlik
matrisi her FR/KR'yi bir TS bölümüne ve obje/metoda bağlar (boş satır = eksik TS). İyileştirme meşrudur ama (a) FS tam
karşılandıktan sonra, üstüne eklenir; (b) FS'i değiştiriyorsa TS'e gömülmez → FS §11-A'ya öneri olarak döner, onaydan sonra girer.

### İlke 4 — TS, FS'i denetler
Bir FS isteği fizibil olmayabilir, istendiği gibi yapılınca hataya yol açabilir, başka bir yeri bozabilir, alternatif yol
gerektirebilir ya da yanlış olabilir. Değerlendirme TS'ten önce/sırasında yapılır ve **§2-A FS Denetimi**'ne yazılır.
Sorunlu istek körü körüne build edilmez: **DUR → bulgu → alternatif öner → onay → sonra çözüm.** Etki alanı iddiası
kanıtla kurulur (`%sap-adt-foundation` → `adt_where_used`, `adt_impact_analysis`, `foundation-query.md` §3).

### İlke 5 — "Ertelenebilir mi?" ayrımı
| Meşru build-time teyit (ertelenebilir) | Fonksiyonel karar (TS'te kapanır) |
|---|---|
| Tasarımı değiştirmez, canlıda doğrulanır | Yanlışsa tasarım/sonuç yanlış olur |
| DTEL / append adı (kullanıcı verir) | eşleştirme mantığı + **çoklu eşleşme** çözümü |
| sürüme bağlı teknik alan adı (ör. anahtar dönüşümünde ön anahtar alanı) | anahtar çözümü **tüm** anahtar alanlarıyla |
| kütüphane alt metot sözdizimi | veri dönüşümü: tarih / ondalık / önde sıfır (ALPHA) / dolgu |
| aktivasyonun sahte "OK" vermesi | ölçü birimi dönüşümü ve karşılaştırma |
| mesaj numarasının kesin sırası | hangi varlık/alt kalem hangi alanı taşır |
| | kenar durumlar: boş / mükerrer / en çok / sıfır |
| | kilit / eşzamanlılık, hata birleştirme kuralı |

**§11-A Build-Time Doğrulanacaklar** yalnız sol sütunu içerir. Denetim sorusu: "bu madde yanlış çıkarsa tasarım ya da
sonuç değişir mi?" → evet ise §11-A'ya ait değildir; TS gövdesinde çözülür ya da FS §11-B'ye döner.

### Geliştirici geri-soru simülasyonu
"Bu TS elime geçti, kodu yazacağım; satır 1'den önce neyi bilmem gerekir?" Tipik sorular: mevcut kaydı hangi koşulla
bulacağım · iki eşleşme olursa hangisi · alan hangi tabloda/alt kalemde · dış veri hangi biçimde gelir, nasıl çeviririm ·
birim farkında karşılaştırma · boş/mükerrer/en çok girdide ne olur · kilit. Her soru TS'te cevaplı ya da (yalnız meşruysa) §11-A'da.

## 2. FS → TS adımları
1. **Girdiyi oku.** FS PDF ise metni çıkarılmış hâli istenir (aXet `view` aracının PDF okuduğu DOĞRULANMADI).
2. **Genel bilgiler + izlenebilirlik listesi:** geliştirme kimliği ve başlık, geliştirme tipi (rapor, iyileştirme, arayüz,
   dönüşüm, form, iş akışı), modül; her FR/KR bir satır; FS'te "açık konu / TBD / ?" kalan her nokta ayrıca listelenir.
   Kısa özet kullanıcıya gösterilir.
3. **FS denetimi (§2-A)** — İlke 4.
4. **Genişletme seviyesi** her madde için (§4).
5. **Açık kararları topla ve sor:** FS'te cevabı olmayan ya da varsayıma dayanan her nokta somut soruya çevrilir: hedef sistem
   profili ve ABAP Cloud durumu · zorunlu/opsiyonel alanlar, veri hacmi, mevcut Z objeler · entegrasyon (released API/BAPI/CDS,
   senkron/asenkron) · arayüz tipi (Fiori elements / freestyle / yalnız backend) · yetki (yeni yetki nesnesi / mevcut rol) ·
   iyileştirme ayrıntısı (hangi BAdI/enhancement spot, filtreli mi) · performans, zamanlama · FS açık konularının her biri
   (çözüldü / varsay / engel). **Önce araştır** (canlı okuma, çalışan artefakt), kalan iş kararlarını **tek seferde,
   seçenekli ve önerili** `ask_user` ile sor ve **yanıtı bekle**. Yanıtlanmayan nokta TS'te açıkça `[Varsayım]` olur;
   fonksiyonel karar varsayımla kapatılmaz (İlke 5) — FS §11-B'ye döner.
6. **TS'i yaz** (tek dosya ya da §6 beş parça).
7. **Canlı teyit turu** (`live-confirmation-tour.md`) → düzeltme varsa ikinci kapı.
8. **Kontrol listesi + bağımsız inceleme** (`doc-checklist.md`) → teknik onay.

## 3. Profil ve araç gerçekleri (TS yazarken)
- `sap-project.json` `sap_profile`: `s4_public` ve `btp_abap`'ta klasik obje (program, include, fonksiyon grubu, Dynpro) yoktur;
  `ecc`'de RAP ve released CDS yoktur. TS profilin sunmadığı objeyi öneremez; emin olunmayan yetenek canlı okumayla doğrulanır.
- aXet CLI'sinde aracı olmayan adımlar (ör. RFC işareti, metin havuzu, bazı obje tipleri) TS'te "kullanıcı SAP GUI/ADT'de yapar"
  diye yazılır; hangi adımın araçla yapılacağı `%sap-adt-foundation` → `references/tool-catalog.md` otoritesindedir.

## 4. Genişletme seviyesi karar ağacı (clean core)
Her FR/KR için seviyeler **sırayla** değerlendirilir ve **uygun olan en düşük** seçilir; karar ve gerekçe §2.1 ve §2-A tablosuna yazılır.

| Seviye | Ad | Ne zaman |
|---|---|---|
| 1 | Anahtar kullanıcı genişletmesi (özel alan, iş kuralı aracı, Fiori uyarlama) | kodsuz çözülebiliyorsa |
| 2 | Geliştirici genişletmesi / uygulama içi (RAP, released API, ABAP Cloud) | released API/CDS varsa |
| 3 | Yan uygulama (BTP üzerinde uygulama/entegrasyon) | arayüz ya da entegrasyon ağırlıklıysa |
| 4 | Klasik genişletme (BAdI, user exit, enhancement, klasik program) | üsttekiler yetmiyorsa |

Kurallar: daima en düşük uygun seviye · 4. seviye seçildiyse **istisna gerekçesi** yazılır · standart objeyi değiştiren
çözüm **hiçbir seviyede** önerilmez (Yasak A) · standart tabloya doğrudan yazan çözüm yazılmaz (Yasak B: released API (released RAP BO/EML · released BAPI ·
released OData) → BAPI → RFC FM → BDC → manuel; seçim §6.4'e — `%sap-dev` → `references/write-api-selection.md`) · bir API/CDS'in released olduğu **canlıda doğrulanır**, hatırlanmaz (`%sap-dev` → `references/coding-patterns.md` §7).
Profil sınırı seviyeyi kısıtlar: `ecc`'de 2. seviye yok; `s4_public`/`btp_abap`'ta 4. seviyenin klasik obje yolu yok.

## 5. Bölüm yapısı (zorunlu)
| Bölüm | İçerik ve kural |
|---|---|
| Kapak | teknik başlık · `TS-<MODÜL>-<NNN>` · **ilgili FS no (zorunlu)** · proje · SAP sistemi/profil · geliştirme tipi · hazırlayan · tarih · versiyon · transport (kullanıcıdan; uydurulmaz, yoksa "atanacak") |
| 1 Doküman kontrolü | FS ile aynı yapı; ilgili dokümanlarda FS referansı zorunlu |
| 2 Teknik genel bakış | 2.1 geliştirme tipi, modül, etkilenen süreç, yeni/mevcut üzerine, clean core uyumu ve seviye · 2.2 teknik mimari (akış diyagramı) |
| 2-A FS denetimi | her FR/KR: ✅ uygulanabilir / ⚠ alternatif gerek / ⛔ fizibil değil / 💥 başka yeri bozar / ✗ FS hatalı · bulgu + kanıt · aksiyon. **Boş bırakılmaz** ("denetlendi, temiz" de sonuçtur) |
| 3 Geliştirme nesneleri | tip · ad · paket · açıklama · durum (yeni/değişen). Adlar `%sap-dev` → `references/naming.md` + paket `.rules.md`; listedeki her obje sonraki bölümlerde ayrıntılanır |
| 4 Veri sözlüğü | 4.1 domain (tip, uzunluk, sabit değerler) · 4.2 data element (4 etiket: kısa/orta/uzun/başlık, `master_language`'de TAM; metin spesifikasyondan) · 4.3 tablo (alan, DTEL, anahtar, istemci alanı) · 4.4 index. DTEL/append adını kullanıcı verir |
| 4.5 Ekran/UI tasarımı | 4.5.1 ekran/view listesi · 4.5.2 her ekran: (a) alan tablosu (b) buton/aksiyon tablosu (c) grid kolon tablosu (d) açıklama kolonu kararı (e) klasik ALV alan kataloğu kararı · 4.5.3 etkileşim matrisi · 4.5.4 kullanılan API/BAPI/OData ve test yöntemi |
| 5 Program/sınıf tasarımı | 5.1 program yapısı (klasik program include'lara bölünür, `%sap-classic-abap`) · 5.2 sınıf: metot, tip (statik/örnek/özel), parametre adları ve tipleri, dönüş · 5.3 **numaralı sözde kod** (metot başına; gerçek kod değil) |
| 6 Veritabanı erişimi | 6.1 kullanılan standart tablolar/CDS ve erişim tipi (yalnız okuma; S/4'te released CDS tercih) · 6.2 kritik okumalar · 6.3 performans (gereken alanlar, WHERE'siz okuma yok, döngü içinde okuma yok, büyük veride paketleme) · **6.4 API seçimi** — standart nesneye create/update/delete/action varsa ZORUNLU: değerlendirilen **her** yöntem (EML `I_…TP` · BAPI · OData · RFC FM · BDC) için sistemde var mı (canlı) · released mı · ADIM 0 bağlamının commit kuralı · hata yönetimi · karar ve **reddedilenlerin nedeni** + clean core seviyesi (`%sap-dev` → `references/write-api-selection.md`) |
| 7 İyileştirmeler | BAdI / enhancement spot / exit adı, implementasyon adı (kullanıcı onaylı), sözde kod |
| 8 Form/çıktı (varsa) | form tipi, driver, çıktı tipi, yapı |
| 9 Arayüz/RFC (varsa) | FM imzası, parametreler, hata durumları; senkron/asenkron |
| 10 Hata yönetimi | 10.1 **mesaj envanteri** (aşağıda) · 10.2 istisna sınıfları ve yakalama deseni |
| 11 Test | 11.1 birim test (sınıf/metot/koşul/beklenen) · 11.2 entegrasyon testi; her kabul kriteri bir teste bağlı |
| 11-A Build-time doğrulanacaklar | yalnız İlke 5 sol sütun: madde · yöntem · neden ertelenebilir |
| 12 Transport stratejisi | sıra: DDIC → mesaj sınıfı → program/sınıf/fonksiyon → işlem kodu/yetki → uyarlama. Transport numarası kullanıcıdan; yaratılmaz |
| 13 Onay | hazırlayan · teknik lider · mimar |
| Diyagramlar | mimari akış zorunlu; kapsamlı (S2) işte ayrıca veri modeli, ana işlem sırası, varsa durum makinesi ve hata akışı (Mermaid; `pdf-with-screenshots.md` §D) |
| İzlenebilirlik matrisi | FR/KR → TS bölümü → obje/metot → test (`traceability.md` §2) |

### 5.1 §4.5 kuralları
- **Kolon tamlığı (zorunlu):** ekrandaki her grid/tablonun **tüm kolonları ve her kolonun başlık metni** listelenir; DDIC
  varsayılan etiketine bırakılmaz. Gerekçe: yapıdan birleştirilen alan kataloğunda başlık alanın DTEL'inden gelir; aynı
  genel DTEL farklı roller için aynı/yanıltıcı başlık üretir (sipariş veren, malı teslim alan, ek muhatap hepsi "Müşteri").
  Rol özel standart DTEL varsa o kullanılır; yoksa başlık metni TS'te açıkça yazılır ve kodda kolon metniyle verilir
  (ya da kullanıcının adlandırdığı bir Z DTEL).
- **(a) Alan tablosu:** teknik ad · ekran etiketi · tip/uzunluk · zorunlu · varsayılan · değer yardımı · düzenlenebilirlik (oluştur/değiştir ayrı) · doğrulama.
  CDS'ten türetilebiliyorsa `gen_field_table.py` ile üretilir, elle yazılmaz.
- **Değer yardımı (F4) mekanizması TS'te alan alan kurgulanır, build'e bırakılmaz (ekip dersi).** (a) tablosundaki "değer
  yardımı" hücresi yalnız var/yok değil: mekanizma (DTEL'e bağlı ya da yapı bileşenine `with value help` ile bağlanan DDIC
  arama yardımı · FM/açılır pencere · POV modülü · ALV alan kataloğu · domain sabit değerleri) × veri kaynağı × filtre/parametre
  eşlemesi. Mekanizma alan tipine ve veri kaynağına bağlıdır; sonradan seçilirse ekran alanı tipi ve parametre eşlemesi de
  değişmek zorunda kalır (vakada build'e ertelenen F4 tasarımı bir günlük düzeltme turuna döndü). Her F4 için ortak mı
  pakete özel mi olacağını kullanıcıya sor. Klasik ekranda mekanizmalar ve sınırları (Z arama yardımı bu araç setiyle
  yaratılamaz): `%sap-classic-abap` `dynpro-dialog-fields.md` §2.
- **(b) Buton tablosu:** buton · etiket · olay · etkin olma koşulu · çağırdığı servis (API/BAPI/OData fonksiyonu).
- **(c) Grid tablosu:** kolon · etiket · tip · düzenlenebilir · sıralama/filtre · hesaplama/biçim. Liste ekranında ALV paritesi (SAP çekirdeği) sağlanır.
- **(d) Açıklama kolonu kararı (zorunlu):** kod olarak listelenen her alan (müşteri, sipariş tipi, malzeme, birim, üretim yeri,
  depo, koşullar) için açıklama metninin ayrı kolon olup olmayacağı **karara bağlanır**: eklenirse kaynak (tablo-alan ya da
  released CDS + dil) yazılır; eklenmezse gerekçesi. Kaynak adı canlıda doğrulanır.
- **(e) Klasik ALV alan kataloğu kararı (zorunlu):** DDIC yapısından birleştirme mi, elle katalog mu — gerekçeyle. Yapı tercih
  edilir: miktar+birim, tutar+para birimi, çok kolon, kod→açıklama kolonları, tekrar kullanım. Elle katalog: basit, az kolonlu
  rapor. Yapı seçildiyse yapı adı (kullanıcı onaylı) + alan→DTEL eşlemesi §4'te verilir.
- Ham ekran görüntüsü tasarım yerine geçmez; görsel eklenecekse işaretli olur ve tabloları tamamlar.

### 5.2 §10.1 Mesaj envanteri (zorunlu)
Geliştirmenin üreteceği **her** mesaj listelenir — bu bir **envanterdir, örnek tablo değildir**. Mesaj metnini yalnız
kullanıcı verir; TS'te eksik kalan her mesaj build ortasında bloke eden bir onay turu açar.

| Kolon | Kural |
|---|---|
| Mesaj sınıfı · No · Tip | `E`/`W`/`S`/`I`/`A` |
| Metin (birebir) | **≤ 73 karakter** (T100 kısa metin sınırı; aşan metin kırpılır ya da yazma reddedilir) → aşan metin TS'e yazılmaz, kısa hâli kullanıcıdan istenir |
| Yer tutucular | **numaralı** `&1 &2 &3 &4` (çıplak `&` değil) + her birinin taşıdığı değer |
| Üretim noktası | sınıf/metot ya da RAP doğrulama/belirleme adı (çapraz kontrol DOC-CR-01 bu kolonu okur) |
| Kullanıcı aksiyonu | `E`/`A`'da zorunlu; `S`/`I`'da `—` |

- Uzun metin isteğe bağlıdır; istenirse "SE91'de elle girilir" şerhi yazılır (aXet mesaj yazma aracı uzun metin yazmaz).
- Build sırasında yeni mesaj ihtiyacı doğarsa **TS revize edilir**: metin kullanıcıdan alınır, tabloya işlenir, sonra kodlanır.
  "Şimdilik geçici metin" yazılmaz.
- Mesajların SAP'ye yazımı `%sap-cds-ddic` / `adt_msgclass_write` işidir (yalnız `s4_private`; araç 73 karakteri reddeder).

### 5.3 FM imzası ↔ doküman senkronu (§9 ve kullanım kılavuzları)
Bir Z fonksiyon modülünün parametreleri dokümanda (TS §9 arayüz bölümü, paylaşılan bir FM'in kullanım kılavuzu)
listeleniyorsa ve FM'in kaynağı yazılmışsa (build sonrası) liste **makine-okunur blok** içine alınır:
```
<!-- FM-IMZA: Z_DEMO_FM -->
| Parametre | Tip | Anlam |
|---|---|---|
| `IV_BIR` | … | … |
<!-- /FM-IMZA -->
```
FM'in imzası değişince doküman aynı revizyonda güncellenir. Sapmayı `check_fm_signature_doc_sync.py` ölçer: blokları
bulur, FM kaynağını proje kaynak kökünde (`sap-project.json` `source_root`) `FUNCTION <ad>` satırından bulur ve iki
yönde raporlar. **EKSİK** imzada olup blokta olmayan parametredir; bayat doküman, bir sonraki geliştiricinin "FM bunu
yapamıyor" sanmasına yol açar. **HAYALET** blokta olup imzada olmayan parametredir.
```
python <TEMPLATE>/skills-sap/sap-fs-ts-docs/scripts/check_fm_signature_doc_sync.py [<doküman ya da klasör> …] [--kaynak-kok <klasör>] [--bulguda-exit1]
```
Çıkış kodları: `0` temiz ya da uyarı · `1` sapma var ve `--bulguda-exit1` verildi · `2` ÖLÇÜLEMEDİ. ÖLÇÜLEMEDİ şu
durumlarda döner: kaynak bulunamadı ya da birden çok dosyada tanımlı · imza ayrıştırılamadı · blok kapanmamış.
ÖLÇÜLEMEDİ "temiz" demek **değildir**. Sıfır blok da "senkron" demek değildir; blok eklenmemiş dokümana araç hiç bakmaz.
Blok yalnız FM kaynağı var olduğunda eklenir (build öncesi TS'te FM henüz yazılmadıysa blok build sonrasına kalır).
Araç yerel kaynağı okur; yerel kaynak bayatsa önce sistemden çekilir. Aracın bakmadıkları KAPSAM çıktısında listelenir
(tip/varsayılan/istisnalar karşılaştırılmaz).

## 6. Beş parçalı üretim (büyük TS)
Büyük TS'i tek seferde üretmek yerine beş parça yazılıp teslimde birleştirilebilir. Bölüm numaraları bu dokümanın numaralarıdır.

| Parça | Dosya | Bölümler |
|---|---|---|
| 1 Başlık ve bağlam | `TS-<MOD>-<NNN>_part1-header.md` | kapak, 1, 2, 2-A (clean core değerlendirmesi, varsayımlar ve kullanıcı cevapları, bağımlılıklar) |
| 2 Çözüm | `…_part2-solution.md` | 3, 4, 4.5 (metot imzaları §5.2 tablosuyla birlikte bu parçada da verilebilir) |
| 3 Mantık | `…_part3-logic.md` | 5, 6, 7, 8, 9, 10 (tam mesaj metinleri) |
| 4 Test ve dağıtım | `…_part4-test.md` | 11, 11-A, 12, izlenebilirlik matrisi |
| 5 Diyagramlar ve kapanış | `…_part5-diagrams.md` | diyagramlar, bitti tanımı kontrol listesi, özet, 13 onay |

Birleştirme ve PDF: `python <TEMPLATE>/skills-sap/sap-fs-ts-docs/scripts/build_doc_pdf.py part1.md TS.html "Başlık" --also part2.md --also part3.md --also part4.md --also part5.md --pdf`.
Teslim edilen tek dokümandır; parçalar çalışma dosyasıdır. Birleşik dokümanda aynı bölüm numarası iki kez geçmemeli.

## 7. TS kalite listesi (yazar öz kontrolü — inceleme ayrıca `doc-checklist.md` §C)
```
[ ] FS referansı var; tüm nesneler listeli ve sonraki bölümlerde ayrıntılı; adlar adlandırma kuralına uygun
[ ] DDIC nesneleri tam (4 etiket TAM, master_language); sözde kod metot başına numaralı
[ ] Performans noktaları, iyileştirme yaklaşımı, transport stratejisi yazılı
[ ] §4.5 kolon tamlığı + (d) açıklama kolonu kararı + (e) alan kataloğu kararı
[ ] §10.1 mesaj envanteri TAM (≤ 73, &1..&4 + anlam, üretim noktası, aksiyon; metinler kullanıcıdan)
[ ] FM kaynağı varsa (build sonrası): parametreleri listelenen her Z FM için FM-IMZA bloğu var ve `check_fm_signature_doc_sync.py` sapma göstermiyor; build öncesi TS'te liste elle karşılaştırılır, blok build sonrası eklenir (§5.3)
[ ] Birim ve entegrasyon testleri; izlenebilirlik matrisi FS'e bağlı, boş satır yok (İlke 3)
[ ] §2-A FS denetimi dolu; sorunlu maddeler bilgilendirildi (İlke 4)
[ ] §11-A yalnız teknik teyit; fonksiyonel kararlar kapalı: eşleştirme + çoklu eşleşme · tüm anahtar · dönüşüm · birim · alan taşıma · kenar durumlar · kilit · hata birleştirme (İlke 5)
[ ] Genişletme seviyesi her madde için en düşük uygun; 4. seviyede istisna gerekçesi; standart obje/tablo yazımı yok
[ ] Standart nesneye yazma varsa §6.4 API seçimi — EML teyitleri canlı, reddedilenler nedeniyle yazılı
[ ] Geliştirici geri-soru simülasyonu yapıldı
[ ] Canlı teyit turu koşuldu (ya da "canlı teyit bekliyor" açıkça yazılı)
[ ] Teknik lider onayı
```

## 8. TS'te sık hatalar
| Hata | Doğrusu |
|---|---|
| FS'siz TS | FS onaylanmadan başlama |
| Döngü içinde okuma | toplu okuma / join / tüm girdiler için tek okuma |
| Standart tabloya doğrudan yazma | BAPI / released API (Yasak B) |
| Kodda sabit değer | uyarlama tablosu ya da sabit tanımı |
| Eksik istisna yönetimi | kritik işlem yakalama bloğuyla |
| Transport sırası hatası | önce DDIC, sonra program |
| FS'i kör uygulama | §2-A denetim + alternatif (İlke 4) |
| Fonksiyonel kararı erteleme | §11-A yalnız teknik teyit (İlke 5) |
| Çözümsüz FS maddesi | matriste her FR/KR bağlı (İlke 3) |
| Örnek mesaj tablosu | tam envanter, metin kullanıcıdan |
| Uydurma obje/transport | ad kullanıcı onaylı, transport kullanıcıdan |
