# Çok katmanlı (çapraz kesen) davranış değişikliği

> **Ne zaman oku:** bir davranış birden çok katmanda (backend kuralı + ekran akışı + mesaj + veri) ya da birden çok
> uygulama/obje üzerinde aynı anda doğru olmak zorundaysa. Örnekler: silme/iptal kontrolü, yetkilendirme, audit
> alanları, mesaj biçimi, zorunlu alan doğrulaması, kilit davranışı, toplu işlem.
> **Kaynak:** gerçek bir iş turu — "3 uygulamalık küçük düzeltme" diye başlayan iş 2 gün, 7 uygulama, 13 backend
> kuralı ve 6 inceleme turu sürdü. Aşağıdaki her madde o turda yaşanmış bir hatanın karşılığıdır.

**Tek cümle:** iş teknik olarak zor değildi; uzamasının sebebi yüzeyin tamamının hiçbir noktada taranmadan katman katman
keşfedilmesiydi. Her düzeltme bir sonraki eksiği doğurdu.

| | İlk varsayım | Tam tarama sonrası |
|---|---|---|
| Kapsam | 3 uygulamalık ekran düzeltmesi | 7 uygulama + 2 backend boşluğu + canlıda yetim veri |
| Silme yolu | 14 (kısmi tarama) | 24 |
| Hata sınıfı varyantı | 1 | 7 |
| İnceleme turu | 1 beklenirdi | 6 |

## 1. Baştan nasıl engellenir

### 1.1 Kabul ölçütü kullanıcı gözünden yazılır
Backend'e 13 doğrulama kuralı yazıldı, hepsi çalıştı — ama kullanıcı hiçbirinde sebebi göremiyordu, çünkü ekran o yola
hiç gitmiyordu. Kural teknik olarak "tamam", işlevsel olarak ölü koddu.

| Yanlış kabul ölçütü | Doğru kabul ölçütü |
|---|---|
| "Kontrol yazıldı ve aktive edildi" | "Kullanıcı silemediğinde sebebi belge numarasıyla görüyor" |
| "Doğrulama kablolu" | "Ekranda şu metin çıkıyor, ≤ 50 karakter, numara görünür" |
| "Birim test yeşil" | "Çalışır sistemde gözlendi; ekran görüntüsü ya da ham yanıt kanıtı var" |

Kabul ölçütü gözlenebilir kullanıcı davranışı olarak yazılmadıysa iş bitmiş sayılmaz. İlk gün 10 dakikalık bir çalışır
sistem denemesi turun tamamını farklı yönetirdi.

### 1.2 Kardeş uygulamalarda desen kopya değil, sahipli referanstır
Aynı işi yapan 5 kardeş uygulama birbirinden sapmıştı (biri paralel kaydediyor, diğerleri sıralı; bekleyen değişiklik
kontrolü birinde 3, diğerinde 4 alana bakıyor). Her sapma ayrı bir hata yüzeyi üretti.
- Ortak davranış için **kanonik referans** belirle (hangi uygulama örnek?).
- Yeni uygulama = kanonikten kopya + **fark testi** ("nesi farklı, neden?").
- Bilinçli sapma yoruma gerekçesiyle yazılır; yazılmamış sapma gelecekteki hatadır.
- Ortak davranış değişince kardeşlerin **tamamı** aynı turda güncellenir.

### 1.3 Platform sınırı tasarımdan önce ölçülür
Mesaj biçimi tasarlandıktan sonra canlıda 50 karakterde sessizce kesildiği görüldü; biçim baştan yazıldı. Çıktı bir
platform yüzeyinden geçiyorsa (OData mesajı, IDoc segmenti, ekran alanı, e-posta konusu) önce uzunluk, kodlama ve kırpma
davranışını ölç, sonra biçimi tasarla.

### 1.4 Çapraz kesen davranışta ilk adım envanterdir
"Silme yolu" envanteri ikinci günün ortasında çıkarıldı; 14 sanılan sayı 24, "3 uygulama" 7 oldu. İlk iş:
*bu davranışı hangi entity / uygulama / yol taşıyor?* → matris. Envanter bir turdur; envantersiz ilerlemek her katmanda
bir turdur.

### 1.5 Bir hata sınıfı bulununca sınıf tüm yüzeyde aranır
"Liste daralınca seçim bayatlıyor → yanlış kayıt siliniyor" sınıfı bulundu. Her inceleme kendi dar kapsamına baktı;
hiçbiri tüm yüzeye bakmadı ve bir uygulama hiçbir incelemenin kapsamına girmedi. Sınıf bulunduğu anda sınıf taraması aç
(*bu desen hangi dosyalarda var?* → liste → her biri kapsandı mı işaretle). İnceleme kapsamı dar kalır; **kapsama listesi
işi yürütende** durur.

## 2. Sonradan yakalandıysa düzeltme sırası

```
1. ÇALIŞIR SİSTEMDE TEYİT ET  → gerçek semptom ne? (10 dk; en pahalı bilgiyi en ucuza verir)
2. ENVANTER / YÜZEY TARAMASI  → matris; iki listeyi birleştirecek anahtarı (entity/uygulama adı) belirle
3. TEK İŞ LİSTESİ + TAHMİN    → kullanıcıya sun: kapsam, sıra, büyüklük, risk
4. KAPSAM KARARI              → "hepsi mi, bir kısmı mı?" — tek sefer, toplu
5. DESENİ DONDUR              → kanonik uygulamayı bitir + incelemeden geçir
6. ÇOĞALT                     → dondurulmuş deseni diğerlerine uygula
7. TEK İNCELEME TURU          → toplu, dar kapsamlı, sınıf kapsama listesiyle
8. KULLANICI KABULÜ           → kullanıcının gördüğü davranış
```
O turda 1 atlandı → 2 gecikti → 3/4 hiç yapılmadı (kapsam 5 kez ayrı ayrı genişledi) → 5/6 sırası bozuldu → 7, 6 tura bölündü.

| Yap | Yapma |
|---|---|
| Önce semptomu çalışır sistemde gör | Kaynağı okuyup semptomu varsay |
| Yüzeyin tamamını tara, matris çıkar | Katmanları sırayla keşfet |
| İki taramayı ortak anahtarla birleştir | Birleşmeyen iki ayrı liste üret |
| Kapsam kararını bir kez, toplu al ve kullanıcıya sun | Yol boyunca "şunu da ekleyelim" (o turda 5 kez) |
| Deseni dondur, sonra çoğalt | Desen değişirken çoğaltmaya başla |
| İnceleme kapsamını dar tut, kapsama listesini kendinde tut | Her incelemenin "her şeye baktığını" varsay |
| İnceleme ya da alt görev koşarken kaynağa dokunma | İnceleme sürerken dosyayı düzenle (o turda 3 kez → bayat inceleme) |
| Biten işi WIP commit ile koru | İşi commit'siz beklet (oturum düşerse gider) |
| Uzun alt görev çıktısını artımlı olarak diske yazdır | Sonda tek seferde yazdır (o turda 3 görev düştü, iş kayboldu) |
| "DOĞRULANMADI (sebep)" yaz | Kanıtsız PASS yaz |
| Sayı ve satır referansına ölçüm tarihi + içerik çapası ekle | Yoruma çıplak `dosya:satır` yaz (o turda 6 kez bayatladı) |

### Kapsam genişletme — tek kural
Kapsam 5 kez genişledi ve her genişleme haklıydı; sorun dağınık olmasıydı: kullanıcı her seferinde yeni bir "şunu da
yapalım" duydu ve işin ne zaman biteceğini göremedi. Genişleme kararı **envanterden sonra, toplu** verilir; sonradan çıkan
bulgu park edilir, mevcut parti bitirilir. İstisna: veri kaybı ya da geri alınamaz risk → yine kullanıcıya "kapsam büyüyor,
sebebi bu" denir, sessizce büyütülmez.

### İnceleme ekonomisi
Ölçülen israf: kaynak inceleme sürerken 3 kez değişti (yeniden okuma) · 5 dosya 3 ayrı turda incelendi · her tur aynı
sınıfın yeni bir varyantını buldu. Önceki bir ölçümde inceleme süresinin %92'si model düşünmesi, %8'i araçtı: darboğaz
araç hızı değil **tur sayısı** → düzenlemeleri topla, sonra incelemeye ver.

### Kullanıcıya görünürlük
İş beklenenden büyük çıktığı **anda** kullanıcıya şunlar sunulur: (a) yeni kapsam (b) neden büyüdüğü (c) tahmini kalan iş
(d) kesme seçeneği. "Şunu da buldum" mesajlarının toplamı durum raporu değildir. "Şu an ne kaldı, ne zaman biter?" sorusu
her an cevaplanabilmeli; cevaplanamıyorsa iş listesi yok demektir → adım 3'e dön.

## 3. Alt görev (`agent`) ve inceleme işletimi
- Aktarılan kullanıcı onayı niyet taşır, izin taşımaz: izin katmanı bir çağrıyı reddettiyse talimatı tekrarlamak yeni
  deneme gerekçesi değildir.
- Alt görevin işi yürüteni düzeltmesi normaldir: brifinge "itiraz et, kanıt getir" yaz; kanıtsız "yapılamaz"ı kabul etme,
  kanıtlı itirazı tartışma.
- Araç sınırı ≠ yokluk: bir araç boş döndüğünde önce aracın kapsamını doğrula (boş ana include → "metot yok" sanıldı;
  tipi desteklemeyen kilit kontrolü → "kilit yok" sanıldı; dar arama deseni → "referans kalmadı" sanıldı).
- Şiddeti dayandıran gerekçe çökerse şiddet yükselir ("kardeşte de var, kabul edilmiş desen" savunması git geçmişiyle
  çürütüldü → orta → yüksek).
- "Öncesi neydi" git ile kanıtlanır (`git show <commit>^`): bulgu bu değişikliğin ürünü mü, önceden mi vardı.
- Geri alınamaz bir denemeden önce ön koşulu kanıtla (gerçek silme denemesinden önce koruyucu kontrolün güncel ve kablolu
  olduğu ayrıca doğrulandı).

## 4. Tura başlarken 2 dakikalık kontrol
- [ ] Kabul ölçütünü kullanıcının göreceği davranış olarak yazdım mı?
- [ ] Semptomu çalışır sistemde gördüm mü, yoksa kaynaktan mı varsaydım?
- [ ] Davranış çapraz kesen mi? Öyleyse envanterim var mı?
- [ ] Kardeş uygulama/obje var mı? Kanonik referansı belirledim mi?
- [ ] Platform sınırlarını (uzunluk, kodlama, kırpma) ölçtüm mü?
- [ ] Kullanıcıya tek iş listesi + tahmin sundum, kapsam kararını aldım mı?
- [ ] Desen donduktan sonra mı çoğaltıyorum?
- [ ] İncelemeye vermeden önce düzenlemeleri topladım mı?
- [ ] "Şu an ne kaldı?" sorusuna şu anda cevap verebiliyor muyum?
