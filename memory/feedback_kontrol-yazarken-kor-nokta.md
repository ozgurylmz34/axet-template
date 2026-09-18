---
name: kontrol-yazarken-kor-nokta
description: Doğrulayıcı, guard ya da yazma kapısı yazarken "koştu" ≠ "baktı"; metin ile hedefi, ikinci yüzeyi ve önkoşul yokken davranışı ayrıca test et, yeni kontrolü dar ve önce uyarı modunda aç
type: feedback
---

Bir kontrol yeşil verip hiçbir şeye bakmıyor olabilir; ya da ilk açılışta onlarca sahte bulgu döküp kuralın gevşetilmesine
yol açar. Her kontrolde üç soru:

1. **Neyi tarıyor — metni mi hedefi mi?** Komut/kaynak metnini düz desenle taramak, o deseni *içeren* zararsız veriyi (commit
   mesajı, yorum, dizge, yardım metni) bloklar; fiile bakıp hedefi çözmemek de gerçek yazmayı kaçırır (`2>&1`'deki `>` yazma
   sanılırken `python -c "open(f,'w')"` geçiyordu).
2. **Hangi yüzeylere bağlı?** Aynı işi yapan ikinci bir araç ya da yazım biçimi var mı (başka kabuk, takma adlı SQL). aXet
   örneği: hassas veri koruması `KNA1 AS K` ifadesini sessizce atlıyordu, düz `KNA1` bloklanıyordu
   (`skills-sap/sap-adt-foundation/scripts/sapadt/data_guard.py`, "NORMALİZE HEDEF" notu). Kontrolü doğrudan çağıran test,
   gerçek giriş noktasındaki bağlantıyı sınamaz.
3. **Önkoşul yoksa ne yapıyor?** Veri/harita/dış araç yoksa `return {}` / `except: return ""` → çıkış 0 → PASS = fail-open.
   "Bulgu satırı görmedim" ≠ "temiz"; aracın kendi özet satırı ya da açık bir `ÖLÇÜLEMEDİ` dalı zorunlu kanıttır.

**Neden:** Kaynak ekipte tek denetimde 3 guard kendi commit'ini blokladı, 4 kural daha aynı körlükteydi; ikinci kabuk yüzeyi
kodda "kapalı" sanılırken hiç bağlı değildi ve doğrudan çağıran test yeşildi. Başka bir vakada bir doğrulayıcı hiç
üretilmemiş boş bir haritayla aylarca PASS verdi. Bir liste ekranı detektörü ilk taramada 10 bulgu verdi, 10'u da sahteydi
(sezgisel eşik); detektör daraltılınca 0'a indi — gerçek iş yoktu.
**Nasıl uygulanır:**
- Kural başına üç eksenli test: ihlal → FAIL · aynı deseni içeren zararsız metin → PASS · ikinci yüzey/yazım → FAIL. Düzeltmeyi
  bilerek bozup testin FAIL verdiğini gör; aksi hâlde testin dişi kanıtlanmamıştır.
- Devreye alma sırası: detektörü dar yaz (sezgisel eşik yok) → önce uyarı modunda (çıkış 0) koş → bulguları ayır (sahte mi,
  gerçek eski ihlal mi; sahteyi muafiyete yazma, detektörü düzelt) → gerçek eski ihlalleri adıyla, gerekçe ve çıkış şartıyla
  ("yeniden adlandırılınca listeden sil") muafiyet listesine yaz → kural gevşetilmez, liste verilir; muafiyet kural metninde ilan
  edilir → iki test (muaf olmayan ihlal FAIL, muaf giriş PASS) → 0 bulgu olunca bloklayıcıya çevir.
- "Güvenli yön" tek başına tasarım ölçütü değildir: yanlış-pozitif üreten fail-closed kontrol atlatma alışkanlığı doğurur; onu da ölç.
- Çıktı neye bakmadığını da yazsın: "0 bulgu" yalnız "baktığım yüzeyde bulgu yok" demektir.
- Yeni kapı/doğrulayıcı altyapı değişikliğidir: önce uyar, bu değişiklik için ayrıca açık onay al (çekirdek §3).
Önceki kayıt: yok (aranan: `memory/`, `core/`, `skills/` — fail-open, guard, muafiyet, uyarı modu; yakın ama farklı: [[inceleme-bulgusu-kontrol-listesine]])
Son-doğrulama: 2026-09-13 (ekip dersinden uyarlandı; aXet örneği kaynak kod notundan okundu, canlı ölçülmedi)
Applies-to: tüm projeler — doğrulayıcı, guard, yazma kapısı ya da CI kontrolü yazan/değiştiren iş
