# KD yazımı — Kullanıcı Dokümanı (kullanıcı kılavuzu)

> KD, geliştirmeyi hiç bilmeyen son kullanıcıya "bu nedir, ne işe yarar, nasıl kullanırım" sorularını **adım adım** anlatır.
> Kullanıcının yalnız kendi günlük SAP ekranlarını bildiği varsayılır. Bir beşinci sınıf öğrencisinin anlayacağı sadelikte olur.
> Şablon: `templates/KD-template.md` · Üretim: `pdf-with-screenshots.md` · İnceleme: `doc-checklist.md` §A + §D.

**Altın kural:** teknik hiçbir şey yok (tablo, FM, BAPI, kod, işlem iç ayrıntısı). Geçen her terim sözlükte sade açıklanır.
Her mesajın yanında "ne yapmalısın" aksiyonu olur. Metnin çoğu **işaretli** (ok, daire, numara) ekran görüntüsüyle desteklenir.

## 1. Ne zaman
Geliştirme bittikten ve kullanıcı testinden geçtikten sonra; canlı geçiş eğitiminde ve sonrasında başucu kılavuzu olur.
Arayüz değiştiyse KD aynı revizyonda güncellenir (bayat ekran/akış kalmaz).

## 2. Bölüm yapısı (zorunlu)
| Bölüm | İçerik |
|---|---|
| Kapak | kullanıcı dostu ad · `KD-<MODÜL>-<NNN>` · ilgili FS/TS no · erişim adı (tile/işlem kodu) · hedef rol · hazırlayan · tarih/versiyon · durum |
| 1 Bu kılavuz hakkında | ne anlatır (1 cümle) · kimin için · nasıl okunur (yeni başlayan baştan, deneyimli ilgili bölüme) · takılınca kim (1 satır, en başta) · varsayım ("teknik bilgi gerekmez") |
| 2 Genel bakış | uygulama nedir (1-2 paragraf) · hangi işi kolaylaştırır (kullanıcı gözünden eskiden → şimdi) · **arka plan sonucu:** bu işlemi yapınca sistemde ne oluşur ("Kaydet'e basınca SAP'de gerçek bir satış siparişi oluşur; bundan teslimat ve fatura kesilebilir") · 3-5 maddelik üst akış |
| 3 Başlamadan önce | erişim/yetki (yoksa kime başvurulur) · elde olması gereken bilgi/ana veri · nereden açılır (launchpad grubu/tile ya da işlem kodu; ilk giriş notları) |
| 4 Ekran tanıtımı | ana ekranın işaretli görüntüsü + numaralı bölüm açıklamaları |
| 4-A Liste/tablo ekranı özellikleri | grid varsa **zorunlu ve sabit** (§4) |
| 5 Adım adım iş akışları | her tipik görev: "X yapmak için:" + numaralı adımlar (emir kipi: tıkla, gir, seç) + görüntü; sonunda görülen mesaj |
| 6 Alan giriş rehberi | alan (ekran etiketi) · ne girilir · biçim/örnek · zorunlu mu · **neden / boş bırakırsan** · otomatik mi |
| 7 Butonlar ve işlemler | olay tetikleyen **her** şey: ne yapar · ne zaman kullanılır · **arka planda sonuç** |
| 8 Yapılması ve yapılmaması gerekenler | ✅ / ⛔ listesi |
| 9 Hata ve mesajlar | gördüğün mesaj (**birebir**) · ne demek · neden olur · **ne yapmalısın**; sonunda "hâlâ çözülmezse: mesajın tam metni + belge no ile destek" |
| 10 SSS | sahadan gelen gerçek sorular + sade cevaplar |
| 11 Terimler sözlüğü | geçen her terim ve kısaltma sade dille |
| 12 Destek ve iletişim | anahtar kullanıcı / destek kanalı / çalışma saatleri (kişi adı yerine rol ya da kanal da yazılabilir) |
| 13 Onay | hazırlayan · gözden geçiren anahtar kullanıcı · süreç sahibi |

Başta kısa bir **hızlı başlangıç** önerilir. İçindekiler tıklanabilir olur (§5).

## 3. Ekran görüntüsü kuralları
- **Gerçek arayüz, mockup değil** (FS/TS'in tersine). Görüntü işaretli/numaralı olur; ham tek resim yetmez.
- **Veri temiz örnek veridir (zorunlu):** anlamlı, tutarlı, profesyonel örnek kayıtlar ("Örnek Müşteri A.Ş.", "Demo Malzeme 01").
  **Yasak:** test çöpü kayıtlar ("E2E Test", "otomatik test"), tutarsız/eksik satır, gerçek müşteri ya da kişi verisi, anlamsız
  kod yığını. Yöntem: canlı backend'e dokunmadan **istemci modeline temiz veri enjeksiyonu** (UI5 mock sunucu + model verisi;
  `pdf-with-screenshots.md` §A). Uygulamanın canlı çöp verisini ekrana basmak eksik KD'dir (inceleme BLOCKER).
- Klasik GUI ekranlarında aXet'te ekran çekme aracı yoktur: görüntüleri kullanıcı DEV'de temiz demo kayıtlarla çeker; yöntem
  kullanıcıyla kararlaştırılır (DOĞRULANMADI — kanıtlı bir aXet reçetesi yok).
- **Açılır/kapanır alanlar iki durumda** çekilir (paneller, satır detayları: kapalı ve açık).
- Sayılar görüntüler arasında tutarlı olur (toplamlar kalemlerin toplamına eşit).

## 4. Zorunlu kapsam kuralları
### 4.1 Tüm alt ekranlar
Uygulamada açılan **her** alt ekran — diyalog/açılır pencere, popover, değer yardımı (F4) penceresi, seçim penceresi, sihirbaz
adımı — KD'de **kendi görüntüsü + ne işe yaradığı + alan/kolon ve buton işlevleriyle** yer alır. Yalnız ana sayfaları anlatıp
modal pencereleri atlamak eksik KD'dir.
**Yöntem:** önce ekran envanteri çıkarılır (UI5: `webapp/view/*.xml` + `webapp/fragment/*.xml` içindeki `Dialog`/`Popover`/
`SelectDialog`/`ValueHelpDialog`; klasik: çağrılan ekran numaraları ve açılır pencereler) → her biri KD'de bir bölüme eşlenir →
eşleme tablosu inceleme kanıtı olarak saklanır.

### 4.2 Bölüm 4-A — liste/tablo ekranı araçları
Uygulamada standart liste/tablo ekranı (UI5 `sap.ui.table.Table` + kişiselleştirme; klasik ALV) varsa bu başlık **her zaman** yer
alır, atlanmaz, kısaltılmaz. Her araç **ne işe yarar + nasıl kullanılır + işaretli görüntü** ile:

| Özellik | Nerede | Ne işe yarar | Nasıl kullanılır |
|---|---|---|---|
| Sıralama | kolon başlığı | listeyi artan/azalan dizer | başlık → Artan/Azalan sırala |
| Filtreleme | kolon başlığı | operatörlü süzme (içerir/eşittir/arasında) | başlık → Filtre → değer; filtreli kolon belirginleşir |
| Kolonlar (göster/gizle) | başlık çubuğu → Kolonlar | görünen kolonları seçer | listeden işaretle/kaldır |
| Varyant | başlık çubuğu → Varyant | kolon/sıra/filtre düzenini kaydeder, geri yükler; varsayılan yapılabilir | "Farklı kaydet" → ad ver → seç / "Varsayılan yap" |
| Excel'e aktar | başlık çubuğu → Excel'e aktar | filtreye uyan satırları dosyaya indirir | tıkla → kapsam (görünür/tüm kolonlar) → dosya iner |
| Yenile | başlık çubuğu → Yenile | güncel veriyle tazeler | tıkla |
| Filtre çubuğu (varsa) | listenin üstünde panel | kriter girip listeleme | paneli aç → kriter → Listele; Temizle sıfırlar |

Uygulamaya özel akışlar Bölüm 5'te kalır. Grid dışı liste (mobil öncelikli istisna) kullanıyorsa bölüm o ekranın gerçek araçlarına göre uyarlanır.

## 5. Tıklanabilir içindekiler (zorunlu, sessiz kusur)
HTML/PDF üretiminde başlıklara kimlik verilmezse içindekiler bağlantılarının **tamamı ölü** olur; doküman açılır, görünüm
kusursuzdur, yalnız tıklama etkisizdir. Üretici (`build_doc_pdf.py`) Markdown'a `toc` eklentisini **Türkçe farkındalı slug** ile
verir (varsayılan slug `ı`/`İ` harflerini siler: "Kılavuz" → `klavuz`). Bitmiş saymadan önce **küme kontrolü:** her `href="#x"`
için `id="x"` **ya da** `<a name="x">` olmalı (`verify_doc_html.py`). Tek tük ölü bağlantıda **başlığı değil href'i** düzelt
(bölüm numarası önekiyle doğru başlığa eşlenir). Elle bağlantı yazılıyorsa hedef slug'ı üreticiyle aynı kuralla üret.

## 6. Klasik GUI programında ikinci ayak — F1 yardımı
İşlem koduyla açılan klasik GUI programının (Dynpro, ALV, module pool, rapor) KD'si **iki ayaklıdır**:
1. **Repo Markdown/PDF KD** — otorite ve yazım kaynağı, çevrimdışı başucu kılavuzu.
2. **SAP içi F1 yardımı** — KD içeriğinden **türetilen**, kullanıcının programın içinden (Yardım → Uygulama yardımı) açtığı
   fihrist + bağlantılı detay sayfaları.

İkinci ayak klasik GUI KD'sinde **varsayılan teslimattır**; kullanıcı ayrıca istemese de planlanır. İçerik kuralları: her ana KD
bölümü bir detay sayfasına eşlenir; tip/değer tanımları domain sabit değerlerinden canlı okunur, kolon/formül FS ve sınıf
mantığından gelir (uydurma yok); erişim adımında son kullanıcıya program çalıştırma işlem kodu (SA38/SE38/SE80) verilmez;
KD değişince F1 yardımı aynı revizyonda güncellenir. F1 kaynak metni ayrı dosyada tutulur: `docs/DOCU-<MODÜL>-<NNN>_<Uygulama>_GUI_Yardim.md`.
**SAP'ye yazım** (ITF biçimi, satır ≤ 72 karakter, çalıştırıcı sınıf, `adt_classrun` yazma sınıfı ve onay) bu skill'in işi değildir:
`%sap-classic-abap` → `references/forms-f1-help.md` §B.
**İstisna:** RAP + Fiori/UI5 uygulamasında F1 ayağı yoktur (yardım arayüz içinde/launchpad'de yaşar).

## 7. Yazım kuralları
**Yapılır:** sade dil, kısaltmalar açılır · çoğunluk işaretli görüntü, metin duvarı yerine numaralı adımlar · emir kipi, kısa
etken cümle · görev bazlı ("X yapmak için") · rol bazlı gruplama · her mesajın yanında aksiyon, metin birebir (aranabilir) ·
sözlük + destek bölümü.
**Yapılmaz:** teknik ayrıntı · kullanıcıyı suçlama ("yanlış girdin" değil "şunu yap") · BÜYÜK HARF/ünlem yığma · tek genel
mesaj (her duruma ayrı açıklama + aksiyon) · görüntüsüz uzun anlatım · "herkes bilir" varsayımı · mockup/temsili çizim.

## 8. Uygulama içi yardım kopyası
UI5 uygulaması bir "Kullanıcı kılavuzu" düğmesiyle KD HTML'ini açıyorsa (`webapp/help/…`), KD her üretildiğinde kopya ve
görselleri de güncellenir (`build_kd_pdf.py --help-dir`); aksi hâlde uygulamadaki kopya bayatlar. Kopyanın canlıda görünmesi
yeniden deploy ister; deploy kullanıcı yerel testte onay verdikten sonra yapılır.

## 9. KD kalite listesi (yazar öz kontrolü — inceleme ayrıca `doc-checklist.md` §A)
```
[ ] İlk sayfa: ne / kimin için / takılınca kim net
[ ] Genel bakış: amaç + ARKA PLAN SONUCU (ne oluşur)
[ ] Ön koşullar (yetki / ana veri / erişim yolu)
[ ] Ekran tanıtımı işaretli görüntüyle
[ ] TÜM görüntüler temiz örnek veriyle; gerçek/kirli kayıt yok
[ ] Grid varsa Bölüm 4-A var
[ ] TÜM alt ekranlar ayrı bölüm + görüntü + işlevle; ekran envanteri eşleme tablosu hazır
[ ] Her tipik görev adım adım + görüntü
[ ] Alan rehberi: ne / biçim / zorunlu + NEDEN / otomatik
[ ] HER buton ve olay tetikleyen işlem arka plan sonucuyla
[ ] Yapılması / yapılmaması listesi
[ ] Hata/mesaj tablosu: birebir metin + anlam + AKSİYON
[ ] SSS + sözlük + destek
[ ] Teknik terim sızmamış
[ ] İçindekiler bağlantıları ölü değil (küme kontrolü); ham diyagram kodu yok; tüm görseller görünüyor
[ ] Klasik GUI ise F1 ayağı planlandı ve KD ile senkron; Fiori/UI5 ise muaf
[ ] Anahtar kullanıcı onayı
```
