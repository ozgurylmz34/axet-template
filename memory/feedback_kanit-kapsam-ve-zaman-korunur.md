---
name: kanit-kapsam-ve-zaman-korunur
description: Bir ölçümü aktarırken kapsam niteleyicisini ve birimi düşürme, gruplu sayıyı açıp say; iki çıktıyı kıyaslamadan önce zaman damgasına bak; ölçümü artefaktın kendi bağlamında (filtre/join/paket) yap; karar değişince üreticinin girdisini de düzelt
type: feedback
---

Doğru bir ölçüm, bir yerden başka bir yere (rapordan belgeye, incelemeden düzeltmeye) taşınırken sessizce yanlış bir
iddiaya dönüşebilir. Dört şey kaybolur:

1. **Kapsam ve birim.** "X koşulunda boş" ile "hepsinde boş" farklı cümlelerdir; genellemek yeni bir ölçüm ister, cümle
   kısaltması değil. Gruplu yazım (`ALAN1-6`) meşrudur ama "N/N tam" bir aritmetik iddiadır: grupları açıp say. Sayının
   birimini yaz: "5" yetmez — bulgu mu, nokta mı, satır mı, dosya mı?
2. **Zaman sırası.** İki çıktıyı "önce/sonra" diye kıyaslıyorsan önce zaman damgalarına ve boyutlarına bak: ikisi aynı
   anda üretildiyse kıyas kurulmamıştır ve boş `diff` hiçbir şey kanıtlamaz. "Otomatik oluşur" cümlesi de bir zamanlama
   iddiasıdır: "oluşuyor" ile "senin okuyacağın ANDA var" ayrı şeylerdir — tetikleyen ve türeyen kaydın oluşma zamanını
   karşılaştır (saat dilimlerini önce eşitle).
3. **Artefaktın kendi bağlamı.** Bir view/rapor/programın davranışını ham kaynakta değil, onun kendi join/WHERE/grup
   anahtarıyla ölç; ham sayım artefaktın hiç göremeyeceği satırları kümeye sokar ve olmayan bir kusur gösterir. Ayırt
   edici kolonu (ambar, tip, gösterge) seçmemek iki ayrı popülasyonu tek küme gibi gösterir. Dışarı gönderilen paket
   (zip/ek) de ayrı bir artefakttır: çalışma ağacındaki dosyayı doğrulamak paketi doğrulamaz.
4. **Üreticinin girdisi.** Bir karar değişince yalnız çıktıyı düzeltmek yetmez: çıktıyı üreten script eski değeri bir
   ara veri dosyasından (TSV/CSV/config) okuyorsa "baştan üret" hatayı geri getirir. Kodda `rg` ile değeri aramak bunu
   göstermez (değer kodda değil, veride); üreticinin okuduğu dosyada değerin dağılımını say.

**Neden:** Ekip derslerinde aynı gün beş aktarım hatası ölçüldü: "belirli seviyedeki segmentlerde boş" bulgusu "28
satırın tamamında boş" diye belgeye geçti, oysa 13 satır doluydu — düzeltme doğru bilgiyi yanlışla değiştirdi. Bir
"önce/sonra aynı" kanıtında iki dosya da aynı dakikada, aynı boyutta üretilmişti. Bir "regresyon" tablosu ambar kolonu
seçilmeden sayılmıştı; view'in kendi join'iyle ölçülünce regresyon yoktu ama yanlış kanıt kod yorumuna yazılmıştı.
Teslimattan hemen sonra var sanılan depo görevi ölçülen vakada 47 dakika sonra oluşmuştu. Gönderilmeye hazır bir zip,
düzeltmeden önceki dosyayı taşıyordu; eşlik eden not ise tersini söylüyordu.
**Nasıl uygulanır:**
- Kalıcı kayda sayı yazarken kapsamı, birimi ve ölçüm tarihini de yaz; aynı sayı iki yerde yaşıyorsa birini kaynak yap,
  ötekinden ona bağla ([[bayat-sayi-referans]]).
- İki dosya kıyası gördüğünde önce zaman damgası; asıl çözüm kıyası yeniden kurmaktır (düzeltmesi geri alınmış kopyayı
  kendin koş). Ayırt edici test: kaba vaka değişmemeli, ince vaka değişmeli.
- "Kusur var/yok" hükmünden önce artefaktın gerçek filtre ve join'lerini ölçüme koy; atladığın her kısıtın nedenini yaz.
- Paketi teslim anında yeniden kur, açıp üye üye hash'i çalışma ağacıyla karşılaştır.
- Karar çürütme turunda üç şeyi ayrı kapat: çıktı · kayıtlar · üreticinin girdisi.
- Türetilmiş çıktıda (HTML/PDF) metin ararken kısa, hücre düzeyinde bir çapa seç: markdown tablo satırı HTML'de birebir
  geçmez. Çapa 0 dönerse önce aramanın kendisini sına.
Önceki kayıt: bulundu [[bayat-sayi-referans]] (sayı/satır bayatlığı, önce/sonra iki sayı) — bu kayıt onun kapsam, zaman
sırası, artefakt bağlamı ve üretici girdisi boyutlarını ekler; aranan: `memory/` — kapsam, niteleyici, zaman damgası, paket, üretici
Son-doğrulama: 2026-09-25 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
Applies-to: tüm projeler — ölçüm sonucunu rapora, belgeye, kod yorumuna ya da teslim paketine aktaran her iş
