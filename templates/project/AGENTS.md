# <PROJE_ADI> — Proje Talimatları (aXet.code)
PROJECT-ID: <PROJE_ADI>

> aXet.code bu dosyayı oturum başında otomatik yükler. Genel çalışma disiplini global çekirdekten
> (`AXET-CORE`) gelir; burada YALNIZ bu projeye özel bilgi durur. Kısa tut: her oturum yüklenir.

## Proje kimliği
- Amaç: <kısa açıklama>
- Teknoloji: <ör. SAP S/4HANA ABAP · Python · UI5>
- SAP (varsa): sistem profili <…> · master_language: <TR|EN> · aktif paket: <…> (tüm paketler: `<source_root>/PAKETLER.md`) · transport: kullanıcı verir
- Depo: <remote adresi ya da "yerel">
- İş bağlamı (müşteri, peyzaj, arayüz, belge dili, numaralandırma): `proje-recetesi.md` — yoksa `proje-recetesi.ornek.md`'yi kopyalayıp doldur. Dosyada `[BİLİNMİYOR]` yazan alanı ajan TAHMİN ETMEZ, kullanıcıya sorar.

## Komutlar
- Test: <komut>
- Çalıştırma / derleme: <komut>
- Doğrulama / lint: <komut>

## Proje kuralları
- <projeye özel kural>
- Projeye özel yöntem/standart: `.axet-code/skills/<ad>/SKILL.md` (kısa kural buraya, ayrıntı skill'e)

## Oturum
- Açılış özeti (her oturumun ilk işi): `python "<AXET_HOME>/scripts/session_brief.py"`
- Gün sonu: `%gun-sonu` · devir notu: `%handoff` · iş listesi: `.axet-code/memory/project_is-listesi.md`

## Açık işler
- Tek kanonik liste: `.axet-code/memory/project_is-listesi.md` (burada madde tutulmaz)

## Hafıza ve güvenlik
- Proje hafızası: `.axet-code/memory/MEMORY.md` (her oturum yüklenir; kayıt: `%remember`).
- Ajanın erişemeyeceği yollar: `.axetcode-denylist` (değişince yeni oturum aç).
- Kimlik bilgileri gitignore'lu dosyalarda durur; repoya ve sohbete girmez.
- Commit denetimi `.githooks/pre-commit` (kimlik dosyası, sır deseni, paket adları, `validators-local/`, SAP kaynak incelemesi): engellerse düzelt; atlatma kararı kullanıcınındır.
- Davranış yüzeyi (bu dosya, `.axet-code.json`, denylist, `.githooks/`, `validators-local/`) değişince onayı kullanıcı kendi terminalinde verir: `python "<AXET_HOME>/scripts/behavior_manifest.py" generate` — oturum çalıştırmaz.
