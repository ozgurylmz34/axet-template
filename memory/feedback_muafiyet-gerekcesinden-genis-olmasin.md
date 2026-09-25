---
name: muafiyet-gerekcesinden-genis-olmasin
description: Bir kontrolün bilinçli muafiyeti gerekçesinden GENİŞ yazılmışsa (gerekçe dosyanın bir bölümü için, muafiyet dosyanın tamamı için) muafiyet kör noktaya döner ve dokunulmazlığı yüzünden en uzun yaşayan kör nokta olur; muafiyeti gerekçenin kapsadığı en dar birime indir
type: feedback
---

Bir kontrol bir dosyayı ya da yolu bilerek muaf tutuyorsa iki kapsamı ayrı ayrı sor: gerekçe NERESİ için geçerli, muafiyet
NERESİNİ kapsıyor? Gerekçe çoğu zaman bir alt küme içindir (ör. desen tanımlayan satırlar), muafiyet ise dosyanın tamamına
yazılır. Aradaki fark kör noktadır ve gerekçesi yazılı olduğu için okuyan "bilerek böyle" deyip geçer.

**Neden:** Ekip dersinde bir kimlik-sızıntı kontrolü kendi desen sözlüğü dosyalarını "kendileri desen tanımlar" gerekçesiyle
taramadan muaf tutuyordu. Gerekçe desen satırları için doğruydu; muafiyet yorumları ve açıklama metinlerini de kapsıyordu.
Ölçümde o dosyaların yorumlarında 8 gerçek kimlik izi çıktı, en eskisi 38 gündür yayındaydı. Dördü bir sızıntı temizliğinin
ertesinde, "bu adı izin listesine almadım çünkü gerçek bir müşteri adı" diyen gerekçe yorumlarının içinde girmişti: karar
doğruydu, kararı anlatan metin sızıntıydı. Bulguyu denetim değil, kapanış kaydı yazılırken yapılan ölçüm yakaladı.
**Nasıl uygulanır:**
- Muafiyet satırı gördüğünde (izin listesi, `# noqa`, `exclude:`, lint-ignore, `.gitignore` istisnası, izin kuralı glob'u)
  gerekçe ile muafiyet kapsamını karşılaştır; fark varsa muaf yüzeyi kontrolün kendi fonksiyonuyla elle tara ve bilinen
  sentetik bir vakayla pozitif kontrol koy — yoksa "0 bulgu" kör taramadan ayırt edilemez.
- Muafiyeti satır/token bazlı yap, dosya bazlı değil; ya da kaldırıp gerçek değerleri gerekçeli olarak var olan izin
  listesine ekle.
- Bir düzeltmenin açıklaması da taranan yüzeydir: gerçek adı anlatmak için yazma, tarif et.
- Yeni muafiyetin devreye alınma sırası: [[kontrol-yazarken-kor-nokta]]; iki katmanlı korumada ikisinin aynı muafiyete
  yaslanıp yaslanmadığı: [[paylasilan-modulun-desenini-yeniden-turetme]].
Önceki kayıt: bulundu [[kontrol-yazarken-kor-nokta]] (muafiyet listesinin nasıl kurulacağı) — bu kayıt muafiyetin
gerekçesinden geniş olmasını ekler; aranan: `memory/`, `core/`, `skills/` — muafiyet, muaf, izin listesi
Son-doğrulama: 2026-09-25 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
Applies-to: tüm projeler — doğrulayıcı, tarama kontrolü ya da izin kuralı yazan/değiştiren iş (çoğunlukla bakım işi)
