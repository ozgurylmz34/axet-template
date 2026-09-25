---
name: paylasilan-modulun-desenini-yeniden-turetme
description: Tek seferlik tarama/dönüştürme script'i yazarken deseni sıfırdan türetme — aynı işi yapan paylaşılan modülü kullan ya da en azından yorumlarını oku; iki koruma katmanı aynı girdide körse redundans yoktur (çoğunlukla bakım ve script yazan iş)
type: feedback
---

Bir kerelik bir tarama ya da dönüştürme script'i (genericize, sızıntı taraması, toplu yeniden adlandırma) yazarken deseni
yeniden türetme: projede o işi yapan paylaşılan bir modül varsa onu import et; yoksa bile önce yorumlarını oku. Gerekçe kod
tekrarı değildir — o modülün yorumları daha önce düşülmüş tuzakların kaydıdır.

**Asıl kural:** redundans, katmanlar bağımsız değilse redundans değildir. İki koruma katmanın varsa ikisinin aynı girdi
sınıfında kör olup olmadığını ölç; "iki kapı var" cümlesi güvence değil hipotezdir. Bir katmanı düzeltmek öbürünün körlüğünü
meşrulaştırmaz, görünmez kılar.

**Neden:** Ekip dersinde tek seferlik bir genericize script'i kelime sınırı (`\b`) ile yazıldı; alt çizgi kelime karakteri
olduğu için `ONEK_<ad>` biçimli her varyant sessizce kaçtı ve firma unvanları dışa açık bir repoya girdi. Aynı tuzak paylaşılan
genericize modülünün kendi yorumunda yazılıydı; modül hiç açılmamıştı. İkinci katman (kimlik listesi kontrolü) da aynı sınıfı
içermiyordu: her biri "öbürü yakalar" varsayımıyla yazılmıştı. İkinci vakada bir katmanın dosya bazlı muafiyeti daraltıldı;
yazım anındaki öbür katmanın aynı muafiyeti geniş kaldı ve "öbür katman yakalıyor" cümlesiyle kabul edildi — ilk vakanın
cümlesinin aynısı. Dışa açık repoya yayın geri alınamaz; geçmiş temizlenmedi.
**Nasıl uygulanır:**
- Script yazmadan önce sor: bu işi yapan paylaşılan modül var mı (`rg` ile ara)? Varsa import et.
- Deseni kendin yazmak zorundaysan paylaşılan kontrolden dar olmadığını bilinen örneklerle ölç (ön ekli, alt çizgili,
  büyük/küçük harf, Türkçe karakter varyantı — [[sifir-sonuc-kanitla-once-kontrol-grubu]]).
- İki katmanlı korumada ikisini aynı negatif vakayla sına; ikisi de kaçırıyorsa koruma tek katmanlıdır.
- Bir katmanı daralttığında kardeş yüzeyleri aynı turda ara; kapatmasan bile hangi katmana yaslandığını kayda yaz
  ([[muafiyet-gerekcesinden-genis-olmasin]]).
Önceki kayıt: bulundu [[kontrol-yazarken-kor-nokta]] madde 2 (ikinci yüzey) — bu kayıt paylaşılan modülün tuzak kaydını ve
katman bağımsızlığını ekler; aranan: `memory/`, `core/` — paylaşılan modül, redundans, katman, genericize
Son-doğrulama: 2026-09-25 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
Applies-to: tüm projeler — tarama/dönüştürme script'i ya da çok katmanlı kontrol yazan iş
