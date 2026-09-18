---
name: explore
description: >
  Use when a question needs reading many files or a broad search (where is X defined,
  how does Y work across the codebase, which files use Z), or when a token-heavy
  investigation should be delegated to a sub-agent to keep the main conversation small.
  Triggers: "araştır", "nerede kullanılıyor", "kod tabanında bul", "incele ve özetle".
---

# Salt-okur araştırma (alt ajana devir)

## When to use this skill
- Cevap için çok sayıda dosya okumak ya da geniş arama yapmak gerekiyorsa.
- Tek bir dosya/sembol biliniyorsa **devretme**: doğrudan `grep` / `view` ile kendin bak (≤ 3 dosya kuralı).

## How to use this skill
1. **Soruyu netleştir:** tek cümlelik soru + neyin cevabı yeterli sayılır.
2. **`agent` aracıyla devret.** Alt ajan konuşmayı görmez; aşağıdaki brifingi eksiksiz doldur
   (bu kısa salt-okur biçimdir; yazma alanı, kapsam dışı bulgu, engel ve çıktı bölümlü tam şablon:
   `references/brief-template.md`):

```
GÖREV (SALT-OKUMA): <soru>
BAĞLAM: <bilinenler: dizinler, adlar, daha önce bakılan yerler>
KAPSAM: <aranacak dizinler / dosya türleri>  —  KAPSAM DIŞI: <bakılmayacak yerler>
KURALLAR:
- Hiçbir dosyayı değiştirme, yazma yapan komut çalıştırma.
- Tahmin yok: her iddia `dosya:satır` alıntısıyla. "Bulunamadı" dediğin her şey için
  hangi desenle nerede aradığını yaz; ikinci bir arama yöntemiyle teyit et.
- Kimlik bilgisi görürsen rapora yazma.
ÇIKTI (en fazla ~40 satır):
1. Sonuç (2-5 cümle)
2. Kanıtlar: `dosya:satır` — ne gösteriyor
3. Bulunamayanlar + arama kapsamı
4. DOĞRULANMADI kalanlar
```

3. **Sonucu denetle:** kanıtlardan en az birini kendin aç ve doğrula. "Yok / yapılamaz" hükmünü kanıtsız kabul etme; gerekirse ikinci bir aramayı kendin yap.
4. **Kullanıcıya aktar:** sonuç + kısa kanıt listesi. Alt ajanın ham çıktısını olduğu gibi yapıştırma.

## Rules
- Araştırma ajanına yazma işi verme; değişiklik ana oturumda, kullanıcının gördüğü yerde yapılır.
- Aynı araştırmayı hem devredip hem kendin yapma; sonucu bekle.
