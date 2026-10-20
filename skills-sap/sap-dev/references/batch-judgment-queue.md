# Yargı kuyruğu sözleşmesi — toplu model yargısını kodla dikmek

> **Ne:** çok sayıda kalem için *hesaplanamayan* bir yargının (ör. bir ATC bulgusu nasıl düzeltilmeli, bir eşleme
> satırı hangi hedef alana gider, bir kalemin etkisi ne) modelden alınıp deterministik bir betik zincirine **güvenli**
> bağlanması için yazılı desen.
> **Ne değil:** kapı, araç ya da yeni bir kayıt yeri değildir. Bir toplu iş (betik + model) tasarlanırken bu sayfadaki
> beş madde **tasarım kontrol listesi** olarak kullanılır.
> **Neden `%sap-dev`'de:** desen tek bir obje tipine ait değil; ilk kullanım toplu ATC düzeltmesi (`%sap-code-review`
> `references/atc-fix-patterns.md` §5), ama eşleme tablosu (`%sap-fs-ts-docs` entegrasyon sayfası) ve etki analizi
> gibi işlerde de geçerli — giriş noktası olan `%sap-dev` hepsine yönlendirir. Profilden bağımsızdır.
> **Kaynak:** ekip çekirdeğinin "kuyruk-dikiş sözleşmesi" reçetesi; o da dış bir toplu analiz hattındaki yargı kuyruğu
> yapısından yalnız **deseni** almıştı (kodu, şemaları, güven eşikleri alınmadı).

## 1. Sözleşme — beş madde
| # | Madde | Neden |
|---|---|---|
| **KDS-1** | **Yargı dosyada yaşar.** Betik önce cevaplanacak kalemleri bir kuyruk dosyasına (JSON/CSV) yazar; model cevabını **o dosyaya** yazar; betik ikinci adımda dosyayı okur. Sohbet metni girdi değildir. | Cevap denetlenebilir, tekrar üretilebilir ve git diff'iyle gözden geçirilebilir olur. |
| **KDS-2** | **Doğrulama kodda yapılır.** Her cevap alanı izin verilen değer kümesine / tipe / kimliğe karşı **kodla** denetlenir (kuyrukta olmayan kimlik, bilinmeyen karar değeri, boş zorunlu alan). Modelin "kontrol ettim" demesi doğrulama değildir. | Model beyanı kanıt değildir; deterministik kontrol sessiz kaymayı yakalar. |
| **KDS-3** | **Bozuk girdi DURDURUR ve adlandırır.** Doğrulanamayan kalemde betik sessizce atlamaz, varsayılan değer uydurmaz; **hangi kalem, hangi alan, neden** bilgisini basıp sıfırdan farklı çıkış koduyla durur. | Kısmi işlenmiş toplu iş, hiç işlenmemişten daha tehlikelidir (hangi kalemin işlendiği belirsizleşir). |
| **KDS-4** | **Cevapsız alan BOŞ kalır.** Model bir kalem için yargı veremiyorsa alan boş bırakılır; betik bunu "açık" sayar ve çıktısında **ayrı sayı** olarak basar. Tahmini doldurma yasaktır. | Bulunamadı ≠ yok: boş, "karar verilmedi" demektir; doldurulmuş tahmin, kararla ayırt edilemez. |
| **KDS-5** | **Yeniden koşum verilmiş cevapları korur.** Kuyruk yeniden üretildiğinde (yeni kalem eklendi, kaynak değişti) mevcut cevaplar kimlikle eşlenip taşınır; yalnız yeni/değişen kalem boş gelir. Kimliği değişen kalemin eski cevabı **taşınmaz**, raporlanır. | Tekrarlı turda emek kaybolmaz, ama bayat cevap yeni kaleme yapışmaz. |

**Kalem kimliği** kaynakta kararlı olmalıdır: satır numarası, dizi sırası ya da zaman damgası kimlik olamaz (bir kaydırma
her kalemi "yeni" yapar). ATC için örnek kimlik: obje + birim + kontrol kimliği + mesaj (`atc-fix-patterns.md` §0).

## 2. Kapsam beyanı (betik her koşumda basar)
En az: `toplam kalem · cevaplı · boş (açık) · reddedilen (KDS-3) · taşınan eski cevap (KDS-5) · düşen eski cevap`.
Sıfır sonuç anı en kritik andır: "0 reddedilen" yalnız betiğin baktığı alanlar için geçerlidir.

## 3. Diğer kurallarla ilişki
- **Kuyruk dosyası bir çalışma girdisidir, iş listesi değildir.** Kuyruktaki "karar/not" sütunları paket `SPEC.md` açık
  kararlarına ya da proje iş listesine paralel ikinci bir açık madde listesine dönüşmez; iş bitince açık kalanlar kanonik
  yerine taşınır.
- **SAP'ye yazan** bir toplu işte bu sözleşme yazma kapısı (`%sap-adt-foundation` §4: `--sap-write` + kapsam beyanı +
  onay), pull-before-edit ve bağımsız inceleme şartlarının **yerine geçmez**; onlara ek olarak uygulanır.
- Betik template'e girecekse testleri en az şu vektörleri içerir: geçerli kuyruk · bilinmeyen kimlik (KDS-3) · boş alan
  (KDS-4) · yeniden koşumda taşıma ve kimlik değişimi (KDS-5).
