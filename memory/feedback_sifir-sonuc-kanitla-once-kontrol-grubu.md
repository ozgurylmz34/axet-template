---
name: sifir-sonuc-kanitla-once-kontrol-grubu
description: Sıfır sonuçla "yok" hükmü kurmadan önce aramanın ya da taramanın GERÇEKTEN çalıştığını bilinen-pozitif bir örnekle göster; Türkçe karakter varyantı, ASCII'leştirilmiş kaynak, CRLF'li liste ya da hiç koşmamış bir komut sıfırı sahte yapar
type: feedback
---

Bir arama, tarama ya da toplu işlem "0 eşleşme" / hiç çıktı döndürdüğünde iki şey aynı görünür: (a) gerçekten yok,
(b) araç o girdiyle yapısal olarak hiçbir şey bulamazdı. Çekirdekteki kontrol grubu kuralı "X bozuk" iddiası içindir;
bu ders onun öbür yüzüdür: **aracın kendisi çalıştı mı?** Ayırmadan yazılan "yok" kalıcı bir yanlışa dönüşür.

**Bilinen nedenler:**
- **Türkçe karakter varyantı.** SAP metinlerinde ve belgelerde I/İ/ı, S/Ş, C/Ç, G/Ğ, O/Ö, U/Ü birlikte bulunur; tek
  varyantla `LIKE`/`rg` gerçek kaydı "yok" gösterir. Tersi de olur: kod yorumları, log ve test mesajları çoğu zaman
  ASCII'ye düzleştirilmiştir; diyakritikli desen onları hiç bulamaz. Kaynağın alfabesini varsayma, önce geniş bir
  desenle gör (`d[uü][sş]er` gibi).
- **Mojibake taraması çıplak karakter aramaz.** `â`, `Â` Türkçede meşrudur (`hâlâ`, `kâr`); bozuk kodlama bunların
  iki karakterlik dizi hâlidir. Çıplak karakter taraması doğru metni "bozuk" diye yakalar. Geri dönüş testi kullan:
  `s.encode('latin-1', 'ignore').decode('utf-8', 'ignore')` metni değiştiriyorsa çift kodlama vardır.
- **Windows'ta yazılan satır listesi CRLF taşır.** Python/PowerShell'in yazdığı ad listesi `git`/`xargs`'a beslenirse her
  adın sonunda `\r` kalır, hiçbiri eşleşmez; araç hatayı stderr'e yazıp devam eder. `2>&1 | wc -l` gibi bir sayım hata
  satırlarını da sayar ve başarı gibi görünür.
- **Komut hiç koşmamış olabilir.** Bir sarmalayıcı (`timeout`, alias, shim) aracı çalıştıramaz ve stderr yutulmuşsa
  (`2>/dev/null`) geriye boş çıktı kalır: "eşleşme yok" ile "komut koşmadı" ayırt edilemez. aXet'in `bash` aracında
  eksik komut ve desteklenmeyen bayrak da aynı sessiz boşluğu üretebilir (çekirdek §4 "Kabuk ortamı").

**Neden:** Ekip derslerinde ASCII `LIKE` araması Türkçe büyük İ ile yazılmış bir müşteri kaydını bulamadı ve "ana veri
yok" kararına gidiyordu. Bir kabul ölçütüne yazılan diyakritikli desen ASCII kaynakta "kalıntı 0" dedi; iki varyantlı
desen 4 eşleşme buldu, 3'ü gerçek kalıntıydı. 70 dal "silindi" diye raporlandı, hiçbiri silinmemişti (adlar `\r`
taşıyordu, sayılan 70 satır hata mesajıydı). `timeout … rg … 2>/dev/null` ile "koda referans 0" hükmü kuruldu; aynı soru
başka bir yolla 18 dosya verdi.
**Nasıl uygulanır:**
1. "Yok / 0 referans / kalıntı kalmadı" demeden önce aynı komutu **bulunduğunu bildiğin** bir örnekle koş; o da 0 veriyorsa
   bozuk olan araç ya da desendir, olgu değil.
2. Türkçe metinde her iki varyantı birlikte ara; küçük tabloda tam listeyle çapraz kontrol et.
3. Bir listeyi başka araca beslemeden önce satır sonuna bak (aXet `bash`'inde `head`/`cat -A` yok:
   `rg -c "\r$" liste` ya da `python -c "print(repr(open('liste','rb').read(200)))"`); yazarken `newline="\n"` ver. Sonucu "N satır işlendi" sayısıyla değil son durumu ölçerek doğrula.
4. Arama komutunu `2>/dev/null` ile susturma; çıkış kodunu da oku.
5. Desen bir kabul ölçütüne ya da inceleme kapısına dönüşecekse önce bilinen-doğru bir dosyada koşup sahte pozitif/negatif
   üretmediğini göster.
Önceki kayıt: yok (aranan: `memory/`, `core/` — varyant, mojibake, CRLF, xargs, "0 sonuç"; yakın ama farklı:
[[git-diff-ve-satir-sonu]] CRLF'in diff'i şişirmesi, [[kontrol-yazarken-kor-nokta]] fail-open kontrol)
Son-doğrulama: 2026-09-25 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
Applies-to: tüm projeler — "yok / bulunamadı / 0 kaldı" hükmüne dayanan arama, tarama ve toplu işlemler
