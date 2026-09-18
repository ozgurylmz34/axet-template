---
name: remember
description: Use when a durable lesson, decision, user correction or project fact is learned that future sessions must know, or when the user says "bunu hatırla", "not al", "kaydet", "unutma", "hafızaya yaz".
---

# Hafızaya kaydet

## When to use this skill
- Kullanıcı bir çalışma biçimini düzeltti ya da açıkça onayladı ("bunu böyle yapma", "evet, böyle devam").
- Birden çok denemeden sonra çalışan yöntem bulundu: kayda **çalışan yöntem + denenen başarısız yollar ve nedenleri** girer.
- Daha önce kayıtlı olmayan bir obje tipi ya da senaryo ilk kez başarıyla yapıldı (yöntemi ilgili skill referansına önermek de dahil).
- Bir hata/patinaj yakalandı ve düzeltildi: kaydın yanında "inceleme bunu yakalar mıydı?" sorusunu cevapla; yakalamazdı → ilgili kontrol listesine satır öner (`%code-review`).
- Aynı tuzak ikinci kez yaşandı: hafıza notu tek başına yetmez → skill kuralı, kontrol listesi satırı ya da doğrulayıcı öner (yeni kapı kullanıcı onayı ister).
- Projede koddan/git geçmişinden çıkarılamayan bir karar, kısıt, tarih ya da dış kaynak öğrenildi.
- Kullanıcı açıkça "hatırla / kaydet" dedi.

**Kaydedilmez:** koddan veya git geçmişinden okunabilen şeyler · yalnız bu oturumu ilgilendiren ayrıntılar · kullanıcı adı, şifre, token, müşteri kişisel verisi.

## How to use this skill
1. **Kapsamı seç**
   - Her projede geçerli çalışma dersi → template reposunun `memory/` klasörü (çekirdek dosyasının bulunduğu repo). Bu değişiklik tüm ekibe gider: kullanıcıya commit/PR gerektiğini söyle.
   - Bu projeye özel → proje kökünde `.axet-code/memory/`. Klasör yoksa oluşturmadan önce kullanıcıya sor.
2. **Önce ara:** `grep` ile hafıza klasöründe anahtar kelimeleri ara. Aynı konuyu kapsayan kayıt varsa onu güncelle, yeni dosya açma. Yanlış çıkan kaydı sil ve indeksten çıkar.
3. **Kayıt dosyasını yaz:** `<hafıza klasörü>/<tip>_<kisa-ad>.md`

   ```markdown
   ---
   name: <kisa-ad>
   description: <tek satır; ileride "bu kayıt işime yarar mı" kararını verdirecek özet>
   type: feedback | project | reference
   ---

   <kural ya da bilgi — tek konu>

   **Neden:** <gerekçe ya da yaşanan olay>
   **Nasıl uygulanır:** <hangi durumda ne yapılacak>
   Son-doğrulama: <YYYY-AA-GG>
   Applies-to: <geçerli bağlam: tüm projeler | SAP profili (ecc/s4_private/…) | obje tipi | proje adı>
   ```

   - Yeni yazılan ya da içeriğine dokunulan kayda `Son-doğrulama` ve `Applies-to` eklenir; eski kayıtlar toplu güncellenmez.
   - Kayıt her projede geçerli bir yöntem/kural ise hafıza notu hatırlatıcıdır, kanonik yer ilgili skill ya da çekirdektir: kullanıcıya oraya taşımayı öner.

   - Göreli tarihleri mutlak tarihe çevir ("dün" → gerçek tarih).
   - İlgili kayıtlara `[[kisa-ad]]` ile bağlantı ver.
4. **İndekse tek satır ekle:** aynı klasördeki `MEMORY.md`'de ilgili tip başlığının altına `- [Başlık](dosya.md) — kısa özet`. "(henüz kayıt yok)" satırını sil.
5. **Doğrula:** kayıt dosyasını ve indeks satırını tekrar oku; kullanıcıya hangi dosyaya ne yazdığını söyle.

## Rules
- Hatırlanan bir dosya/fonksiyon/komut adını kullanmadan önce hâlâ var olduğunu doğrula; hafıza hipotezdir, dosya ve çıktı otoritedir.
- İndeks her oturum yüklenir: satırları kısa tut; 150 satırı aşarsa birleştirme öner.
- Kullanıcı bir kaydın yanlış olduğunu söylerse düzelt ya da sil; iki çelişen kayıt bırakma.
