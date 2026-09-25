# aXet.code Template Reposu — Bakım Talimatları
PROJECT-ID: axet-template

> Bu dosya yalnız bu template reposunun KENDİSİ üzerinde çalışırken yüklenir (repo kökünde aXet açıldığında).
> Kullanıcı projelerine giden içerik `core/`, `skills/`, `skills-sap/`, `memory/`, `templates/` altındadır.

## Yapı
- `core/00-temel.md` — her oturum yüklenen çekirdek (hedef ≤ 150 satır; aşarsa ayrıntıyı skill'e taşı)
- `core/sap/` — SAP paketi kuralları (`install.py --sap`)
- `skills/`, `skills-sap/` — `<ad>/SKILL.md` klasörleri (klasör adı = frontmatter `name`)
- `memory/` — ekip hafızası (indeks + kayıtlar)
- `templates/project/` — `new_project.py`'nin kopyaladığı proje iskeleti
- `scripts/` — `install.py` · `yeni_proje.py` · `new_project.py` · `doctor.py` (tam liste README "Yapı")
- `aXet-Kur.cmd` — ilk kurulum (çift tık; `kur.ps1`'i yayın deposundan indirip çalıştırır)
- `kur.ps1` — kurulum motoru · `kur.cmd` — terminal yolu: yeniden kurulum, `-Sifirla`, `-Kaldir`, `-DenemeModu`
  (`kur.ps1` UTF-8 **BOM'lu** kalmalı: PS 5.1 BOM'suz dosyada Türkçeyi bozar; `.cmd` satır sonu CRLF — `.gitattributes`)
- `yeni-proje.cmd` — `%yeni-proje`'nin terminal yedeği (aynı `scripts/yeni_proje.py`) · `proje-tamamla.cmd` — projedeki
  `KURULUMU-TAMAMLA` kısayolunun hedefi (bağlantı şablonu · ayar onayı · doctor · aXet'i aç)
- `GUNCELLE.md` + `guncelle/` — `%guncelle` akışı ve yayın kataloğu (`guncelle/yayinlar.json`); `CHANGELOG.md` her
  yayında katalogdan üretilir, elle düzenlenmez
- `.axetcode-denylist` — aXet'in okumadığı dosyalar (klonda da bağlantı/gizli dosya koruması)
- `docs/` — onboarding rehberi ve tasarım notları
- `LICENSE` · `NOTICE` · `THIRD_PARTY_NOTICES.md` — izinle eklenen bölüm ya da açık kaynaktan türetilen kod eklenince aynı değişiklikte güncellenir
- `_lab/` — deneme alanı (repoya girmez)

## Bakım kuralları
- Metin Türkçe; skill, dosya ve frontmatter adları İngilizce.
- aXet davranışına dair her iddia `_lab/`'da canlı ölçülür (rastgele işaret + negatif kontrol). Upstream Crush belgesi kanıt değildir; sonuç bakımcı notlarındaki ölçüm kaydına yazılır.
- `axet-code run` betikten çağrılırken stdin kapatılır (bash: `</dev/null`, PowerShell: `$null | axet-code run …`); aksi hâlde askıda kalır.
- Çekirdekteki kimlik satırlarından (CORE-ID, SAP-CORE-ID) biri değişirse sürümü artır ve sıradaki yayının kataloğunda (`guncelle/yayinlar.json`) beyan et; README değişiklik notu yeni kayıt almaz.
- Kimlik bilgisi, müşteri verisi, kişisel ad/e-posta repoya girmez.
- Yapı değişince README ve bu dosya aynı değişiklikte güncellenir.
- Yeni bir gate / validator / deny kuralı eklemeden önce beş şartın hepsi aranır: hata gerçekten yaşandı · sonucu geri alınamaz ya da sessiz · başka bir katman zaten yakalamıyor · önce doküman/skill hatırlatması denendi ve yetmedi · kullanıcıya gerekçesiyle anlatılıp açık onay alındı.
- Bir iş sırasında template altyapısında (script, izin kuralı, skill) sorun görülürse: işi dondur, sorunu sınıfla (işi bloke ediyor mu, kritik mi). Bloke ediyorsa kök düzeltme ayrı ve onaylı yapılır; etmiyorsa açık kalem yazılır, iş içinde gizlice düzeltilmez.
- Kural maddeleri değişince bakımcı notlarındaki kural kapsama tablosu aynı değişiklikte güncellenir.
- Kaynak metodolojiden içerik aktarıldığında bakımcı notlarındaki aktarım haritası aynı değişiklikte güncellenir (karar, hedef, durum). KURALSIZ kaynak dosya kalırken parti kapanmaz.
