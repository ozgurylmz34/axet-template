---
name: skill-audit
description: >
  Dışarıdan gelen içeriği kurmadan ya da çalıştırmadan önce inceler. Marketplace'ten skill_install
  yapmadan, başka bir repodan/gist'ten skill, komut, script ya da talimat dosyası kopyalamadan ve
  tanımadığın bir projede aXet oturumu açmadan önce kullan. Kurulum öncesi skill adını template skill
  adlarıyla karşılaştırır, kurulum sonrası skill envanterini doctor ile denetler. Kullanıcı %skill-audit
  yazarsa da çalıştır.
---

# skill-audit — dış içerik gümrüğü

## Neden
aXet bir klasörde açılınca oradaki talimat dosyaları (`AGENTS.md`, `CLAUDE.md` …) otomatik yüklenir.
Projenin `.axet-code.json` dosyası, şablonun izin kuralıyla **birebir aynı deseni** farklı kararla yazarsa o
kuralı ezer (ölçüldü). Skill ve komut metinleri modelin çalıştıracağı komutları taşır. Yani dış içerik,
onaysız komut çalıştırma ve kural gevşetme yüzeyidir.
Template skill'iyle **aynı adlı** bir skill kurulursa aXet ikisini birden listeler, uyarı vermez; hangisinin
okunacağı modele kalır (ölçüldü, tek koşu).

## Nasıl
1. **Çalıştırma, import etme, kurma.** Hedef henüz yalnız okunacak bir klasördür. Tanımadığın bir proje söz
   konusuysa taramayı o projenin DIŞINDAN yap (içinde aXet açma).
2. **Marketplace skill'i ise önce ad denetimi:** `skill_search` sonucundaki adı template skill adlarıyla
   karşılaştır (aynı envanter fonksiyonu; `<template>` = bu klasörün iki üstü):
   ```
   python "<template>/scripts/doctor.py" --skills --ad "<skill adı>"
   ```
   `FAIL … template skill adıyla AYNI` → kurma; kullanıcıya bildir (farklı adlı sürüm ya da hiç almamak).
3. **Yüzeyi tara** (bu `SKILL.md`'nin klasöründeki script):
   ```
   python "<bu klasör>/scripts/audit_surface.py" "<hedef klasör>" --deep
   ```
4. **Oku.** Script'in eşleşmesi ipucudur, karar değildir: her `SKILL.md`'yi, komut dosyasını ve çalıştırılabilir
   dosyayı baştan sona oku. Ağa çıkıyor mu, dosya siliyor mu, kimlik dosyası okuyor mu, kodlanmış komut var mı,
   izin kuralı değiştiriyor mu?
5. **Kaynak ve lisans:** nereden geldi, kim yazdı, yeniden dağıtıma uygun mu?
6. **Kurallarla karşılaştır:** kimlik bilgisi kuralları (çekirdek §11), SAP kesin yasakları, template skill'leri.
   SAP'ye yazan bir script tek yazma kapısından geçmiyorsa alınmaz. Çelişkide template skill'i ve kesin yasaklar
   geçerlidir.
7. **Kullanıcıya sun:** bulgular + önerin (al / uyarlayarak al / alma). YÜKSEK bulgu varsa onaysız ilerleme;
   onay isterken 5 unsur (çekirdek §3).
8. **Onay sonrası:** önce tek bir projede **proje kapsamında** (`skill_install` scope=project) kur ve dene;
   global kurulum ancak bu inceleme ve kullanıcı kararıyla. Genel şablona almak ayrı bir karardır.
   Kişi/müşteri/sistem izlerini temizle. Şablona girecekse şablon uyarlama kurallarını (bakımcı notları) uygula.
9. **Kurulumdan sonra doctor** (proje kökünde): `python "<template>/scripts/doctor.py"`. Skill envanteri satırları:
   template adıyla aynı ad ve bozuk frontmatter / 1024 karakteri aşan açıklama **FAIL**; SAP/ABAP konulu dış
   skill ve global kapsamlı marketplace kaydı **WARN**; başka projeye ait `scope=project` kaydı yalnız **INFO**;
   manifest (`%LOCALAPPDATA%\axet-code\skills_manifest.json`) ya da bir skill dizini okunamazsa **ÖLÇÜLEMEDİ**.
   Bayraksız tam koşum şablon kuralını ezen proje izin kuralını da FAIL olarak gösterir. `--skills` kipi YALNIZ
   envanteri koşar; izin kuralı, config ve proje iskeleti denetimleri o kipte yapılmaz.

## Kurallar
- "0 bulgu" güvenli demek değildir; script ve doctor yalnız bilinen desenlere bakar (KAPSAM satırını oku).
- Marketplace'teki içerik de dış içeriktir; şirket içi olması inceleme gereğini kaldırmaz.
- İncelenmemiş içerik için `-y`/`--yolo` ile oturum açılmaz.
- **İsteğe bağlı kilit (varsayılan DEĞİL):** proje `.axet-code.json` →
  `{"permissions":{"rules":{"skill_install":{"*":"deny"}}}}` aracı modelin araç setinden tamamen çıkarır; kurulum
  olmaz (ölçüldü, tek koşu, yalnız proje config'i ve `deny`; `ask` kararı ve global config ölçülmedi). Ekip
  kararıyla kullanılır; doctor bu kilidi aramaz.
