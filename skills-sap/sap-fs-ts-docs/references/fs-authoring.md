# FS yazımı — Fonksiyonel Spesifikasyon

> FS, bir iş gereksiniminin SAP'de **ne** yapılacağını ve **neden** gerektiğini iş diliyle anlatır. Anahtar kullanıcı
> okuyup onaylayabilmelidir. Teknik çözüm (kod, tablo, FM, BAdI adı) TS'e aittir.
> Şablon: `templates/FS-template.md` · İnceleme: `doc-checklist.md` §B + §D.

## 1. Doküman hiyerarşisi ve farklar

```
İş gereksinimi → FS (NE / NEDEN) → TS (NASIL) → Geliştirme → Test & kullanıcı kabul → KD (NASIL KULLANILIR) → Canlı + eğitim
```

| Özellik | FS | TS | KD |
|---|---|---|---|
| Hedef kitle | anahtar kullanıcı, iş analisti, proje yöneticisi | ABAP geliştirici, teknik mimar | işlemi yapan son kullanıcı |
| Hazırlayan | anahtar kullanıcı ↔ danışman | modül danışmanı / teknik danışman | danışman / anahtar kullanıcı |
| Dil | iş dili, teknik değil | teknik, sözde kod | sade gündelik dil, teknik sıfır |
| Soru | "Ne istiyorum?" | "Nasıl kodlarım?" | "Bunu nasıl kullanırım?" |
| Ekran | mockup + yapısal tablo | ayrıntılı mockup + alan/buton/kolon tabloları | gerçek ekran + temiz örnek veri |
| Onaylayan | anahtar kullanıcı / proje yöneticisi | teknik lider / mimar | anahtar kullanıcı |
| Ne zaman | geliştirme öncesi | FS sonrası, geliştirme öncesi | geliştirme ve kullanıcı testi sonrası |

## 2. Kapsamla orantılı derinlik

| Kapsam (`%sap-intake-triage`) | FS beklentisi |
|---|---|
| **S0** nokta düzeltme | FS yok — tek satır "ne değişti + neden" (değişiklik notu) |
| **S1** lokalize | hafif FS: etkilenen alan/ekran + kabul kriteri + varsa risk (yarım sayfa) |
| **S2** kapsamlı | tam FS: intake artefaktına bağlanır + **EARS** kabul kriterleri + her gereksinim test edilebilir ve kabul kriterli (hazır tanımı) + backend ve frontend için ayrı hazır tanımı |

Geliştirme tipi (rapor, iyileştirme, arayüz, form, iş akışı) bu eksene diktir: S2 bir rapor da olabilir, bir arayüz de.
Kapsam derinliği belirler, tip hangi bölümlerin ağırlıklı dolacağını belirler.

EARS kalıpları (kabul kriteri yazımı): **Olay** "kullanıcı X'i kaydettiğinde sistem Y yapmalı" · **İstenmeyen durum**
"miktar kapasiteyi aşarsa sistem uyarmalı" · **Durum** "sipariş onay beklerken sistem düzenlemeyi kapatmalı" ·
**Her zaman** "sistem her kayıtta değiştiren kullanıcıyı saklamalı".

## 3. Ekran görseli ilkesi (FS, TS ve KD için ortak)
- **FS ve TS** geliştirme henüz yazılmamış gibi hazırlanır: **gerçek ekran görüntüsü konmaz**; ekran mockup + yapısal
  tablolarla (alan, buton, grid, etkileşim) tanımlanır. Geliştirme bitmiş olsa bile ham ekran resmi tasarım kararını gizler.
- **KD** geliştirme bittikten sonra yazılır: gerçek uygulama ekranının görüntüsü kullanılır, **işaretli/numaralı** olur
  ve içindeki veri **temiz örnek veridir** (`kd-authoring.md` §3).

## 4. Yazım zihniyeti — kullanıcı gözü (önce oku)

FS'i bu uygulamayı **her gün sen kullanacakmışsın** gibi yaz. Bölüm başlıklarını doldurmak yetmez: ekranda ne
görünür/görünmez, hangi alan varsayılan gelir, boş/hatalı/sıfır kayıtta ne olur, toplu işlem, teyit ve geri alma
var mı, "Kaydet'e basınca arka planda ne oluşur" kullanıcıya görünür mü, çok kayıtta performans nasıl olur.

### İlke 1 — Kullanıcı isteği kanondur
Kullanıcının açıkça yazdığı hiçbir istek atlanamaz, gölgelenemez, sessizce yeniden yorumlanamaz. Her istek gereksinim
listesinde **izlenebilir ve karşılanmış** olur. Danışman katkıları isteğin **etrafında** durur, yerine geçmez. Öneri
istekle çelişiyorsa: isteği uygula, çelişkiyi soru olarak getir.

### İlke 2 — Öneri ve soru isteği netleştirmek içindir
- Danışman katkısı `[Öneri]` olarak işaretlenir ve **§11-A Danışman Önerileri**'nde toplanır; onaylanınca ilgili FR/KR'ye
  taşınır ve 11-A'da "taşındı" işaretlenir. Gereksinim listesine sessizce gömülmez.
- Karar verilemeyen, isteği **onun yönünde** derinleştiren her nokta **§11-B Açık Kararlar**'a seçenekler + önerilen
  seçenekle yazılır.
- **Hiçbir fonksiyonel açık nokta "geliştirmede netleşir"e ertelenmez.** FS mutabakatı 11-A boşalıp 11-B kapanınca olur.

### İlke 2b — Üç katman, üç yer
1. **FS gövdesi = yalnız kapanmış hedef durum.** Ne yapılacak, iş kuralı, ekran, hata, kabul kriteri; her satır bugün
   geçerli hâli anlatır. Gövdede **olmaz:** sürüm etiketi ("v1.5'te eklendi", "(YENİ)"), inceleme bulgu numarası,
   araştırma/ölçüm süreci ("canlıda ölçüldü", "ilk turda yanlış okunmuştu"), kullanıcı/toplantı alıntısı,
   "önceden şöyleydi → şimdi böyle" anlatısı ("artık … değil", "bu revizyonla"). **Başlıklar da gövdedir** (H1 hariç):
   süreç izi başlık parantezine saklanmaz. Gerekçe gerekiyorsa gereksinime bağlı tek kısa `Kaynak/Gerekçe` atfı yazılır
   (ör. "kullanıcı isteği K-1", "karar K-07") — paragraf değil.
   *Kural dışı kimlik satırları:* kapak `Versiyon`, §1.1 versiyon tablosu (yalnız uzunluk ölçütüne tabi), §1.3 ilgili
   doküman satırı, altbilgi ve dokümanın kendi tanımladığı kimliklere atıf.
2. **Karar günlüğü = §11-A/§11-B (açık olanlar) + EK "Karar ve Kanıt Günlüğü" (kapananlar).** Karar no · seçenekler ·
   kim/ne zaman · kısa gerekçe · kanıt atfı. Kapanan 11-B kararı gövdeye **sonuç** olarak işlenir ve satırı EK'e iner;
   reddedilen seçenek "neden dışlandı" ile EK'te kalır (aynı talep yeniden açılmasın).
   - **Yayılım tablosu (zorunlu):** her karar kaydı dokümanda **dokunulacak yerlerin listesini** taşır; liste tamamlanmadan
     karar kapanmış sayılmaz. Bir karar tipik olarak birden çok yerde yaşar (gövde kuralı, ekran tablosu, sözde kod, test,
     ek belge) ve düzeltme turu çoğu zaman birini atlar. **Boş ya da eksik yayılım tablosu = kayıt geçersiz** (boş tablo
     "yayılım denetlendi" sanısı üretir, tablosuzdan kötüdür). Kolonlar: `Karar no | Dokunulacak yer (doküman §/dosya) | Durum | Kim / ne zaman`.
3. **Analiz süreci FS'e hiç girmez.** Canlı ölçüm dökümleri, deneme-yanılma, ham veri profili, inceleme raporları paket
   `ref_docs/RESEARCH-*.md` ya da `SESSION_NOTES.md`'de durur; FS yalnız vardığı sonucu ve dosya atfını taşır.
- **§1.1 versiyon geçmişi kısa:** satır başına 1-2 satır "ne değişti" (madde/§ atfı), satır ≤ 400 karakter; "neden/nasıl
  bulundu" EK karar günlüğüne.
- **Yeniden yazımda veri kaybı yok:** gövdeden çıkan her bilgi EK'e taşınır; denklik `doc_equivalence_check.py` ile ölçülür
  (`traceability.md` §5).

### Kullanıcı gözü tamlık — FS'i bitirmeden sor
- Boş dosya / 0 kayıt / mükerrer / en çok kayıtta ekran ne yapar?
- Her alanın varsayılanı, zorunluluğu, "boş bırakırsam ne olur"u yazılı mı?
- Hata nasıl gösterilir (satır mı, toplu mu, birebir metin mi), kullanıcı ne yapacağını biliyor mu?
- İşlem geri alınabilir mi, teyit isteniyor mu, yarım iş kalır mı?
- "Kaydet/İşle" sonrası sistemde ne oluştuğu kullanıcıya görünür mü?
- Kullanıcının yazdığı her istek FS'te gereksinim ya da kural olarak var mı?

## 5. Kaynağa bağlılık — uydurma yok
1. **Sıkı dayanak:** her iş kuralı, süreç akışı, gereksinim ve doğrulama verilen girdilerden (istek, intake artefaktı,
   analiz notu, `ref_docs/`) türer. Deneyim yalnız girdiyi **yapılandırmak** için kullanılır, olgu **eklemek** için değil.
2. **Eksik veri → dur ve sor.** İstenen süreç girdide yoksa ya da çok zayıfsa uydurma içerikle doldurulmaz; eksik açıkça
   söylenir. Sorular araştırmayla bilgilendirilmiş, **tek seferde, seçenekli ve önerili** sorulur (`ask_user`).
3. **Taslak modu:** kullanıcı eksik bilgiye rağmen "taslak" isterse boşluklar makul varsayımla doldurulur ve her biri etiketlenir.
4. **Standart SAP objesi uydurulmaz:** girdide olmayan tablo, işlem kodu, BAdI, API, IDoc, CDS adı FS'e yazılmaz.
5. **Etiketler ve yerleri:**

   | Etiket | Anlam | Yaşadığı yer |
   |---|---|---|
   | `[Öneri]` | danışmanın önerisi, onay bekler | §11-A |
   | `[Açık Konu]` · `[Netleştirilmesi Gereken Nokta]` | karar bekleyen nokta | §11-B (seçenek + öneri) |
   | `[Varsayım]` | doğrulanmamış kabul | §2.3 Varsayımlar (mutabakatta ya doğrulanır ya 11-B'ye döner) |
   | `[Bağımlılık]` | başka geliştirme/sistem/karar | §2.3 Bağımlılıklar |

   Mutabakatta gövdede etiketli satır kalmaz: her etiket ya kapanıp sonuca dönüşür ya da ait olduğu bölümde durur.
6. **Her FS'te düşünülür:** yetkilendirme, veri güvenliği ve kişisel veri, loglama, hata yönetimi, denetim izi. Girdi
   sessizse eksik olarak işaretlenir (11-B), varsayılmaz.

## 6. Bölüm yapısı (zorunlu)
Şablon tüm bölümleri taşır; burada her bölümün kuralı var.

| Bölüm | İçerik ve kural |
|---|---|
| Kapak | başlık · doküman no `FS-<MODÜL>-<NNN>` · proje · müşteri · hazırlayan · tarih · versiyon · durum |
| 1 Doküman kontrolü | 1.1 versiyon geçmişi (kısa, ≤ 400 karakter/satır) · 1.2 dağıtım listesi · 1.3 ilgili dokümanlar (TS no burada) |
| 2 Giriş | 2.1 amaç (hangi iş problemi) · 2.2 kapsam İÇİ ve **DIŞI** (dışı zorunlu) · 2.3 varsayımlar ve bağımlılıklar · 2.4 referanslar |
| 3 İş süreci | 3.1 mevcut durum (numaralı adım + sorumlu, sorunlar) · 3.2 hedef durum (değişen roller, fayda) · 3.3 fark analizi (mevcut/hedef/fark/çözüm yöntemi) |
| 4 Fonksiyonel gereksinimler | 4.1 FR tablosu: `No · Açıklama · Öncelik · Kategori · Kaynak/Gerekçe (kısa)`; **hacim/performans beklentisi satırı zorunlu** ("günde ~N kayıt / eşzamanlı K kullanıcı") · 4.2 iş kuralları `KR-nnn`, açık ve test edilebilir |
| 5 Ekranlar | 5.1 ekran listesi `SCR-nnn` · 5.2 mockup + alan tablosu (etiket, tip/uzunluk iş anlamında, zorunlu, açıklama) + buton/aksiyon + doğrulama kuralları |
| 6 Veri | 6.1 alan eşleştirme (kaynak alan/sistem → hedef, dönüşüm kuralı) · 6.2 veri kalitesi (zorunlu alan, format, doğrulama) |
| 7 Entegrasyon | 7.1 modüller arası (yön, otomatik/manuel) · 7.2 dış sistemler (tip, protokol) |
| 8 Yetkilendirme | roller ve izinler (iş anlamında); teknik yetki nesnesi TS'e |
| 9 Raporlama | rapor adı, seçim kriterleri, çıktı biçimi |
| 10 Hata yönetimi | durum · kullanıcıya görünen mesaj (iş dili) · kullanıcı aksiyonu |
| 11 Test | senaryo: ön koşul · adımlar · beklenen sonuç; her kabul kriteri bir teste bağlı |
| 11-A Danışman önerileri | `Ö-nn · [Öneri] · fayda · etki/maliyet · karar (onay/ret)`; mutabakatta boş |
| 11-B Açık kararlar | `S-nn · hangi isteği netleştiriyor · seçenekler · öneri · karar`; mutabakatta yalnız bloke etmeyenler |
| 12 Onay | hazırlayan · gözden geçiren · anahtar kullanıcı · proje yöneticisi |
| EK Karar ve Kanıt Günlüğü | kapanan kararlar + yayılım tablosu + reddedilen seçenekler |

Liste/rapor ekranı tanımlanıyorsa SAP çekirdeğindeki **ALV paritesi** (sıralama, operatörlü filtre, kolon göster/gizle,
varyant, Excel'e aktarma) FS'te gereksinim olarak yazılır; kullanıcı ayrıca istemese de.

## 7. Yazım kuralları
**Yapılır:** her gereksinim test edilebilir · iş kuralı açık ve ölçülebilir ("10.000 kayıtta 3 saniye") · mockup eklenir ·
kapsam dışı açıkça yazılır · onaysız geliştirme başlatılmaz · gövde = kapanmış hedef durum.
**Büyük/küçük harf:** başlık, menü, içindekiler metinlerinde cümle düzeni; durum/aşama adları başlıkta Baş Harfleri Büyük;
vurgu amaçlı BÜYÜK sözcük başlıkta yok; gövde ve tablolarda BÜYÜK HARF yalnız ekranda görülen sistem değeri için
(`DURUM = BEKLEMEDE`). `## BÖLÜM N:` düzeyi büyük, `### x.y` cümle düzeni. Üreteçle yazılan eklerde bu tek bir başlık
normalleştirme fonksiyonuyla uygulanır, elle değil.
**Yapılmaz:** teknik ayrıntı (kod, tablo adı, FM adı) · belirsiz ifade ("yaklaşık", "genellikle", "bazen") · varsayımı
belirtmeden yazma · kapsam kayması (her kapsam değişikliği ayrı değişiklik talebi) · fark raporu biçiminde yazma.

## 8. FS kalite listesi (yazar öz kontrolü — inceleme ayrıca `doc-checklist.md` §B)
```
[ ] Zorunlu bölümler var; kapsam içi ve dışı açık
[ ] Mevcut ve hedef süreç (akış) var; fark analizi dolu
[ ] Her iş kuralı numaralı ve test edilebilir; hacim/performans satırı var
[ ] Ekran mockup'ları + alan listesi; gerçek ekran görüntüsü yok
[ ] Entegrasyon, yetki, test senaryoları yazılı; her kabul kriteri teste bağlı
[ ] Varsayımlar ve bağımlılıklar belirtilmiş
[ ] (İlke 1) Kullanıcının yazdığı her istek izlenebilir ve karşılanmış
[ ] (İlke 2) Öneriler 11-A'da, karara bağlı; açık noktalar 11-B'de seçenek + öneriyle; ertelenen fonksiyonel nokta yok
[ ] (İlke 2b) Gövdede sürüm etiketi / süreç anlatısı / alıntı / "önceden→şimdi" yok; §1.1 satırları kısa; yayılım tabloları dolu
[ ] Girdide olmayan olgu yok; etiketler ait oldukları bölümde
[ ] Kullanıcı gözü tamlık soruları cevaplı (boş/mükerrer/en çok/sıfır, varsayılan, teyit/geri alma, hata, kaydet sonrası)
[ ] Anahtar kullanıcı onayı
```

## 9. FS'te sık hatalar
| Hata | Örnek | Doğrusu |
|---|---|---|
| Belirsiz gereksinim | "Sistem hızlı çalışmalı" | "10.000 kayıtta 3 saniyede sonuç" |
| Teknik ayrıntı | tablo/FM adı, SQL | TS'e bırak |
| Kapsam kayması | her yeni istek FS'e ekleniyor | değişiklik talebi süreci |
| Test edilemez kural | "kullanıcı dostu olmalı" | ölçülebilir kriter |
| Onaysız geliştirme | imza öncesi başlamak | önce mutabakat |
| İsteği gölgeleme | öneri açık isteğin yerine geçiyor | istek kanon; öneri 11-A'da |
| Açık noktayı erteleme | "build'de netleştiririz" | 11-B'de kapanır |
| Uydurma olgu | girdide olmayan süreç adımı | sor ya da `[Açık Konu]` |
