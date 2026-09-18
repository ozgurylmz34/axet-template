---
name: code-review
description: Use when the user asks for a review of a change, diff, file or pull request ("incele", "review et", "kod kontrolü", "gözden geçir"), or after a substantive code change before reporting it as done — runs an independent reviewer through the agent tool.
---

# Bağımsız kod incelemesi

## When to use this skill
- Kullanıcı inceleme istediğinde.
- Kayda değer bir değişikliği bitirdiğinde, `%verify-done`'dan önce (yazan ile inceleyen aynı bağlam olmasın diye).

## How to use this skill
1. **Kapsamı topla:** `git diff` (ya da ilgili dosyalar) + değişikliğin amacı. Değişen fonksiyonların başka nerede kullanıldığını (`grep`, `lsp_references`) listele.
2. **`agent` aracıyla bağımsız inceleyici çalıştır** (alt ajan konuşmayı görmez; kanıt kuralları ve engel/çıktı
   bölümleri için genel şablon: `skills/explore/references/brief-template.md`):

```
GÖREV (SALT-OKUMA İNCELEME): Aşağıdaki değişikliği incele. Hiçbir dosyayı değiştirme.
AMAÇ: <değişiklik ne yapmalı>
KAPSAM: <dosyalar / diff özeti>  ·  ETKİ ALANI: <kullanıldığı yerler>
KONTROL LİSTESİ:
- Doğruluk: mantık hatası, sınır durumları, boş/null, hata yönetimi, eşzamanlılık
- Güvenlik: kimlik bilgisi, enjeksiyon, yetki, hassas veri loglama
- Tutarlılık: çevredeki kodla adlandırma ve desen; gereksiz tekrar
- Etki: değişen davranış başka kullanıcıyı bozuyor mu
- Test: değişikliği doğrulayan test/çalıştırma var mı
KURAL: Her bulgu `dosya:satır` + somut hata senaryosu (girdi → yanlış sonuç) içermeli.
Senaryosu kurulamayan şüpheyi NOT olarak yaz, BLOCKER yapma.
ÇIKTI: Bulgular önem sırasıyla [BLOCKER | WARNING | NOTE] · sonunda tek karar: PASS / WARNING / BLOCKER
```

3. **Bulguları doğrula:** her BLOCKER'ı kendin okuyarak teyit et; kanıtlanamayanı düşür ya da NOT'a indir.
4. **Sun:** önem sırasıyla, her biri `dosya:satır` + senaryo. Kullanıcı düzeltme istemediyse düzeltmeden önce sor.

## SAP değişikliği
SAP skill'leri açıksa ve değişiklik SAP backend'iyse (ABAP, CDS, RAP, DDIC, klasik OData) bu akış yerine
`%sap-code-review` kullanılır: obje tipi kontrol listeleri, çevrimdışı kontroller ve SAP inceleyici brifingi oradadır.
UI5 uygulaması → `%sap-ui5-fiori` · FS/TS/kullanıcı dokümanı → `%sap-fs-ts-docs`.

## Rules
- İnceleyen değişiklik yapmaz; düzeltme ana oturumda yapılır.
- Spekülatif "blocker" üretme: doğrudan okunabilen bir iddia okunmadan bulgu olmaz.
- SAP paketi açıksa kontrol listesine SAP kesin yasaklarını ekle.
