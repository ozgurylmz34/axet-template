---
name: skill-frontmatter-yaml
description: SKILL.md description'ında tırnaksız ': ' YAML'ı bozar, aXet skill'i sessizce düşürür → '>' blok biçimi + doctor.py
type: feedback
---

SKILL.md frontmatter'ında `description` (ve diğer değerler) tırnaksız tek satır yazılıp içinde `: ` geçerse
(ör. `... Triggers: "araştır"`) YAML ayrıştırılamaz; aXet.code skill'i **sessizce listeden düşürür**.
Ekranda hata çıkmaz; yalnız `.axet-code/logs/axet-code.log`'da
`WARN Failed to parse skill file … mapping values are not allowed in this context` yazar.

**Neden:** 2026-09-13'te yazılan 7 skill'den `explore` bu yüzden `<available_skills>`'te hiç görünmedi; diğer 6
(kontrol grubu) göründü. Neden aXet logundaki uyarıyla kanıtlandı.
**İkinci sessiz düşme sebebi — uzunluk:** `description` 1024 karakteri aşarsa aXet skill'i yine yüklemez; logda
`WARN Skill validation failed … description exceeds 1024 characters`. 2026-09-13'te 7 SAP skill'inden 3'ü (1031-1129
karakter) böyle düştü, 673-958 karakterlik 4'ü göründü; `sap-intake-triage` bu yüzden bir parti boyunca hiç yüklenmemişti.
**Nasıl uygulanır:** `description`'ı daima `description: >` katlanmış blok biçiminde ve **≤ 900 karakter** yaz. Skill yazdıktan/değiştirdikten
sonra `python <template>/scripts/doctor.py` çalıştır (frontmatter kontrolü var) ve yeni oturumda skill'in listede
çıktığını gör. "Skill görünmüyor" durumunda ilk bakılacak yer aXet logudur.
Son-doğrulama: 2026-09-13
