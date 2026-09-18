---
name: onboard
description: >
  Use when a new developer is setting up aXet.code with this template or asks what to do first:
  walks through machine prerequisites, the kur.cmd installer (clone, install, doctor), first-session
  verification (load canary, doctor), the first project via %yeni-proje, SAP credential setup done in
  the developer's own terminal, the first package, and daily use. Checks each step on the machine,
  reports the result and only then moves on. Triggers: "onboard", "yeni başladım", "kurulum nasıl",
  "ilk gün", "aXet'i kur", "kurulumu kontrol et", "neden AXET-CORE görünmüyor". Not for maintaining the
  template itself or troubleshooting a single SAP call (sap-adt-foundation).
---

# onboard — etkileşimli ilk gün rehberi

Kaynak belge: `<AXET_HOME>/docs/onboarding.md`. `<AXET_HOME>` = bu skill klasörünün iki üstü
(`<AXET_HOME>/skills/onboard/SKILL.md`); yolu buradan türet, varsayma.

## When to use this skill
- Geliştirici yeni, kurulum yarım ya da "çalışıyor mu" diye soruyor.
- **Kullanma:** template bakımı · tek bir SAP çağrısının hatası (`%sap-adt-foundation`) · yalnız proje kurulumu (`%yeni-proje`).

## How to use this skill
Her adımda döngü: **kontrol et → sonucu göster → eksikse açıkla ve öner → kullanıcı yaparsa yeniden kontrol et**.
Bir adım geçmeden sonrakine geçme; kullanıcı atlamak isterse atlanan adımı sonda "açık" olarak listele.

| # | Adım | Kontrol (model çalıştırır) | Geçti sayılır |
|---|---|---|---|
| 0 | Ön koşullar | `axet-code -v` · `git --version` · `python --version` · `rg --version` | ilk üçü sürüm basar (rg yoksa yalnız öneri) |
| 1 | Kurulum | `git -C <AXET_HOME> rev-parse --show-toplevel` · `python <AXET_HOME>/scripts/doctor.py` | klon yolu basılır · global config satırlarında FAIL yok |
| 2 | Yükleme | bu oturumun ilk satırı (kanarya) | `AXET-CORE-…` var; SAP işi yapılacaksa `SAP:` açık |
| 3 | Proje | proje kökünde `doctor.py` proje satırları · `session_brief.py --no-fetch` | 0 FAIL · hatasız özet · ilk satırda `proje: <ad>` |
| 3b | SAP bağlantısı | `git check-ignore .conn_adt` · `doctor.py` · `sap_adt_cli.py ping` | dosya adı basılır · PASS · ping başarılı |
| 3c | Paket | `new_package.py --index --check` | liste güncel |
| 4 | Günlük kullanım | — | `docs/onboarding.md` §4'ü özetle |

Eksik adımda yönlendirme:
- **1 eksik:** kurulum kullanıcının PowerShell'inde yapılır. `docs/onboarding.md` §1'deki başlatma satırını ver.
  Klon zaten varsa güncelleme komutu `& $HOME\axet\kur.cmd`.
- **3 eksik:** `%yeni-proje` skill'ine geç; proje kurulunca buraya dön.

Ayrıntılı komutlar ve beklenen çıktılar: `docs/onboarding.md` ilgili bölüm.

## Rules
- **Kimlik bilgisi:** `.conn_adt` dosyasını açma, okuma, listeleme. Şifre, kullanıcı, host ya da sistem bilgisi
  isteme ve yazdırma. Kimlik adımını kullanıcı kendi terminalinde yapar
  (`skills-sap/sap-adt-foundation/scripts/setup_credentials.py`, PowerShell'de; aXet kabuğundan çalıştırma, araç
  etkileşimsiz çağrıyı reddeder). Dosya biçimini uydurma: alan adları `skills-sap/sap-adt-foundation/assets/.conn_adt.example`'dadır.
- **Kurulum komutları:** `kur.cmd` önce `-DenemeModu` ile çalıştırılır. `new_project.py` ve `new_package.py` önce
  `--dry-run` ile çalıştırılır. Gerçek çalıştırma yalnız kullanıcının açık onayıyla yapılır; `kur.cmd` winget ile kurulum
  soruları sorduğu için kullanıcının kendi terminalinde çalıştırılmalıdır.
- `install.py --sap-write` **asla** model tarafından çalıştırılmaz ve önerilmez. Kullanıcı sorarsa: yalnız
  sandbox, ekip kararıyla, kendi terminalinde. `behavior_manifest.py generate` de yalnız kullanıcının terminalinde çalışır.
- **Paket bağımlılığı:** pip kurulumunu kullanıcı onaylamadan yapma; komutu öner.
- `doctor.py --live` bir model çağrısı yapar: çalıştırmadan önce sor.
- Kurulumdan sonra aynı oturum yeni ayarları görmez: kullanıcıdan yeni oturum açmasını iste, 2. adımı orada doğrula.
- SAP'de paket/transport yaratma ya da yazma adımı önerme: paket SE21 ile kullanıcıdan, teslim
  `%sap-abapgit-delivery` ile.

## Çıktı
Sonda tek tablo: adım · durum (GEÇTİ / EKSİK / ATLANDI / ÖLÇÜLEMEDİ) · kanıt (komut ve çıktı özeti) · sıradaki iş.
Ölçemediğin adımı "geçti" yazma.
