---
name: isaret-onermeden-once-prior-art
description: Kaynak dosyanın içine konacak bir işaret/sözdizimi (yorum işareti, pragma, anahtar sözcük) önermeden önce o dosya tipinin skill referansında ara — öneri "bu dosya tipi bunu taşır ve SAP gidiş-dönüşünde korunur" diyen bir sınıf iddiasıdır
type: feedback
---

Bir kural ya da denetim tasarlarken kaynağın içinde yaşayacak bir işaret önermek (`// istisna:` yorumu, pragma, özel anahtar)
bir sınıf iddiasıdır: "bu dosya tipi bu sözdizimini taşır ve SAP'ye yazılıp geri okunduğunda korunur". Öneri kullanıcıya
gitmeden önce bu iddia aranır ve ölçülür.

**Neden:** Ekip dersinde DTEL'siz alan istisnası için `// dtel-istisna: <gerekçe>` işareti önerildi, kullanıcı onayladı ve
uygulandı. Bağımsız inceleme yakaladı: yapı DDL kaynağı `//` yorumunu kabul etmiyor (push HTTP 400) ve SAP yorumları
normalleştirip siliyor — ikisi de yöntem dokümanında yazılıydı. Hedeflenen alanların tamamı yapılardaydı; işaret tam
hedeflediği yerde kullanılamazdı. Dokümanın kendi pratik kuralı hazırdı: gerekçe kardeş `<AD>.README.md` dosyasında.
Kullanıcı onayı yanlış dayanağı düzeltmez; onaylanan öneri kod, test, doküman ve PR'a yayılır ve tam bir düzeltme turu doğurur.
**Nasıl uygulanır:** Kaynağa yazılacak her işaret/sözdizimi önerisinden önce o obje tipinin skill referansında (ör.
`%sap-cds-ddic` referansları) "yorum", "//", "comment", "normaliz" ara ve "SAP geri okumada korunuyor mu?" sorusunu cevapla.
Cevap yoksa öneriyi `DOĞRULANMADI` etiketiyle sun.
Önceki kayıt: yok (aranan: `memory/`, `skills-sap/` — işaret, yorum, pragma, istisna işareti)
Son-doğrulama: 2026-11-17 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
Applies-to: denetim/kural tasarımı, DDIC/CDS kaynağına konan işaretler
