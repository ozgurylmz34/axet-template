---
name: verify-done
description: Use before saying a task is done, complete or ready, before reporting success, before a commit, or when the user asks "bitti mi", "tamam mı", "kontrol et", "doğrula".
---

# "Tamam" demeden önce doğrula

## When to use this skill
Bir işi bitirdiğini söylemeden, başarı raporlamadan ya da commit önermeden önce. "Çalışması lazım" bir doğrulama değildir.

## How to use this skill
1. **İstek listesini çıkar.** Kullanıcının ilk mesajı + sonradan eklenen/değişen istekler. Her madde için "karşılandı mı, kanıtı ne?" sorusunu cevapla.
2. **Değişen dosyaları gör.** `git status` ve `git diff` (repo yoksa değiştirdiğin dosyaları listele). Beklenmeyen değişiklik, geçici dosya, kimlik bilgisi var mı?
3. **Çalıştır ve çıktıyı oku.** Projenin test / derleme / lint / doğrulama komutları (`AGENTS.md` → Komutlar). Çıktıdaki hata ve uyarı sayısını yaz. Komut yoksa en küçük gerçekçi çalıştırmayı yap.
4. **Gerçek giriş noktasından doğrula.** Fonksiyonu elle çağırmak, kablolamayı kanıtlamaz: kullanıcının kullanacağı yol (komut, ekran, API, script) üzerinden dene.
5. **En az bir olumsuz durum dene.** Hatalı girdi, boş değer, yetkisiz durum — sessizce yanlış sonuç vermiyor mu?
6. **Aracın kapsamını yaz.** "0 hata" yalnız aracın baktığı yüzey içindir; neye bakılmadığını belirt.
7. **Ertelenenleri açıkça yaz.** Yapılamayan ya da sonraya bırakılan her alt madde raporda görünür olmalı.
8. **Eylem beyanını çıktıyla göster.** "Commit edildi / push edildi / aktive edildi"yi komut çıktısı olmadan
   (`git log -1 --oneline`, push çıktısı, sistemden okuma) rapora yazma; koşulmadıysa "koşulmadı" de.

**Değişiklik birden çok katmanı ya da kardeş uygulamayı kesiyorsa** (silme/iptal, yetki, audit alanı, mesaj biçimi, kilit):
işe başlarken ve "tamam" demeden önce `references/cok-katmanli-degisiklik.md` — kullanıcı gözünden kabul ölçütü, önce
envanter, hata sınıfının tüm yüzeyde taranması, toplu kapsam kararı, deseni dondurup çoğaltma, tek inceleme turu.

## Rapor biçimi
```
Yapılan: <madde madde>
Doğrulama: <komut> → <sonuç / sayı>
Yapılmayan / ertelenen: <madde + neden>
Açık soru: <varsa>
Kural değişikliği: <dosya: eski → yeni · onay var/yok | yok>
```

## Rules
- Başarısız ya da koşulmamış bir testi başarılı gibi sunma; "koşmadım" de.
- Araç hatasını "zararsız" sayma; nedeni bulunmadan "tamam" denmez.
- Doğrulayamadığın iddiayı `DOĞRULANMADI` diye etiketle.
