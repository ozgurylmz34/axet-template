---
name: sap-intake-triage
description: >
  Use BEFORE any SAP build starts, whenever the user asks for new development or a change to
  existing SAP behavior (report, program, screen, app, field, column, calculation, message,
  interface, revision, fix, enhancement), or requirements arrive as a prompt, Excel sheet or
  functional spec (FS). Classifies scope (S0 point-fix, S1 localized, S2 comprehensive),
  identifies module and work type, researches domain, live system and memory, and evaluates
  with evidence. Triggers: "bu ekrana kolon koyalım", "rapora şu alanı getir", "yeni rapor
  lazım", "şu alan yanlış geliyor", "revize edelim", "FS geldi". Do NOT use for pure research,
  documentation-only work, changes to this template's own tooling, or a request already
  triaged in this session (re-classify only if the scope grew).
---

# SAP intake triage — geliştirme talebi alım protokolü

> **Profil:** sınıflama (S0/S1/S2) profilden bağımsızdır; önerilen çözüm yolu `sap-project.json` `sap_profile`'ın sunduğu
> obje tipleriyle sınırlıdır (`%sap-dev` §2). Modül paketlerindeki deneyim `s4_private` sistemlerden gelir; başka profilde canlı okumayla doğrula.

> **Özü (kırpılırsa bu kalsın):** KAPSAMI sınıfla (S0/S1/S2 + gerekçe) → modülü belirle → isterlerden
> konu çıkar → 3 eksende araştır → KANITLI değerlendir → kapsamla orantılı soru + aksiyon.
> Hafıza = hipotez, canlı sistem = otorite. **TAHMİN YASAK.**

## When to use this skill
- Yeni geliştirme / revizyon / rapor / alan / kolon / ekran / hesap / mesaj talebi — kelimeler ne olursa olsun
  (anlamca tanı: "müşteri adını da görelim" bir kolon talebidir).
- İsterler prompt, Excel ya da fonksiyonel spesifikasyon (FS) olarak geldiğinde.
- SAP'ye yazma yapacak bir işe başlamadan önce (yazma CLI'si kapsam beyanı ister).
- **Kullanma:** yalnız "bu kod ne yapıyor / nerede kullanılıyor" soruları (→ `%explore`, `%sap-adt-foundation`),
  yalnız doküman işi, bu template'in kendi araçları, bu oturumda zaten sınıflanmış talep.

## How to use this skill
Tam protokol, kriterler ve örnekler: `references/protocol.md` — ilk kullanımda oku.

1. **Sınıfla — gerekçeyle.** İki dik eksen + kapsam:
   - Fonksiyonel modül (NE iş?): SD / MM / FI / CO / PP / QM / PM / EWM …
   - Teknik tip (NASIL?): klasik ABAP / RAP / CDS / UI5 / DDIC … (ABAP/RAP/UI5 modül değildir).
   - **Kapsam:** S0 nokta-düzeltme · S1 lokalize · S2 kapsamlı. Gerekçeyi **bir cümleyle yaz**; kullanıcı görür, yanlışsa düzeltir.
2. **Modül paketini oku (varsa):** `references/modules/<modül>.md` (bugün yalnız `sd.md`). Paket yoksa uydurma; genel protokolle ilerle.
3. **İsterlerden konu çıkar:** her anlamlı alan/gereksinim bir domain konusu doğurabilir ("kullanılabilir stok" → ATP; "kredi durumu" → kredi yönetimi).
4. **3 eksende araştır** (kapsamla orantılı derinlik):
   - (a) **Domain:** nasıl çalışır — resmi kaynak; sözdizimi/annotation tahmin edilmez.
   - (b) **Canlı sistem + ilgili kod:** `%sap-adt-foundation` CLI okuma araçlarıyla önce harita
     (`adt_where_used`, `adt_package_contents`, `adt_search_objects`), sonra belirleyici objeleri derin oku (`adt_get`).
     Reuse mı yeni mi · kim tüketiyor (blast-radius) · mevcut mantıkla tutarlılık. Bu eksen aksiyonu değiştirir.
   - (c) **Kurumsal hafıza:** ekip `memory/` + proje `.axet-code/memory/` + proje `AGENTS.md` + önceki intake artefaktları
     (`.axet-code/intake/`). Hafızanın işaret ettiği Z obje **canlı doğrulanmadan** kullanılmaz.
   - Token-ağır araştırmayı `agent` aracına devredebilirsin: brifing `%explore` biçiminde, **yalnız okuma sınıfı CLI araçları**,
     "SAP'ye yazma yok", kanıt = `dosya:satır` / araç çıktısı. Dönen "yok/yapılamaz"ı kanıtsız kabul etme.
5. **Kanıtlı değerlendir:** reuse/yeni · tutarlılık · uygulanacak geçmiş ders · risk. Kanıtsız bulgu aksiyonu belirlemez.
6. **Kapsamla orantılı soru + aksiyon:**
   - **S0:** soru yok, artefakt yok. Tek satır "şöyle anladım, şunu yapıyorum" + etki kontrolü → düzelt → doğrula.
   - **S1:** yalnız kritik/belirsiz noktayı, araştırmayla bilgilenmiş olarak sor (`ask_user`, tek seferde, seçenekli, önerili).
   - **S2:** `.axet-code/intake/<id>.md` artefaktını üret (şablon: `templates/intake-artifact.md`, şema: `references/s2-artifact-schema.md`)
     → kabul kriterleri EARS → sistem sürümü karşılaştırması → yeni Z adları (öneri + canlı kontrol + ad başına ONAY) →
     **kural taraması** (ilgili checklist'lerin BLOCKER satırları; sapma kullanıcıya SORULUR) → öz-tutarlılık → kullanıcıyla
     **madde madde MUTABAKAT** → işareti kullanıcı onayından sonra koy → ancak sonra build (ayrıntı: `references/protocol.md` §6).
   - "Araç / yöntem yok" demeden önce TR + EN eş anlamlılarla büyük/küçük harf duyarsız ikinci arama (`protocol.md` §4 kalite kilidi).
7. **Çıkışta:** öğrenilen ders/desen `%remember` ile (projeye özelse proje hafızası, her projede geçerliyse ekip hafızası önerisi).
8. **Build'e geçiş (S0/S1/S2) → `%sap-dev` ZORUNLU:** build planından ve ilk SAP yazmasından önce `%sap-dev`'i yükle ve
   §3'ü uygula (aktif paket · `.rules.md` · `SESSION_NOTES` · paket klasörü yoksa `new_package.py` · değiştirilecek
   objeleri paket klasörüne indir). Build planının ilk adımı paket klasörüdür, son adımı değil.

## ⛔ Kapsam beyanı — SAP'ye her yazmada zorunlu (kullanıcı kararı)
- SAP'ye yazan **her** CLI çağrısında kapsam beyan edilir:
  - **S0 / S1:** `--scope S0|S1 --reason "<tek satır gerekçe>"`.
  - **S2:** `--scope S2 --intake .axet-code/intake/<id>.md`. Artefakt **dolu** ve kullanıcı **mutabakatı işaretli**
    olmalı; aksi hâlde araç yazmaz (kontrol: `references/s2-artifact-schema.md`).
- **Beyanı işi küçük göstermek için düşürmek yasaktır** (S2 işe `--scope S1` yazmak, artefaktı atlamak için kapsamı eğmek).
- **Kapsam sonradan büyürse yeniden sınıfla:** yeni obje, yeni katman (ör. BE'ye UI eklendi), yeni tüketici çıktıysa dur,
  sınıfı ve gerekçeyi güncelle, S2'ye çıktıysa artefaktı üret ve mutabakat al; ondan sonra yazmaya devam et.
- Mutabakat işaretini (`[x]`) model **kendi başına koymaz**; kullanıcının açık onayından sonra, onayın kaydıyla koyar.
  Artefakt değişirse (kapsam/obje/kriter) mutabakat yenilenir.

## Rules
- Over-triage da hatadır: küçük işe ağır süreç hız öldürür. Sınır belirsizse "bir üst sınıfa yuvarla" değil, **en makul sınıfı gerekçele**.
- Persona "SAP danışmanı gibi davran" demek değildir; değer, kontrol listesi + kaynak işaretçisinden gelir.
- Kesin yasaklar (SAP çekirdeği) triage sırasında da geçerlidir: standart obje/tablo verisi talebi gelirse DUR → açıkla →
  alternatif (BAPI/released API/Z katman) öner → kullanıcıdan iste.
- Prior-art "sanırım yapmıştık" değildir: referansı bul ve doğrula; bulamazsan `yok` yaz.
- S2'de yeni program için ekran + fonksiyonel spesifikasyon iste; sentezle; madde madde onay (ekip hafızası: "Spec mutabakatı build'den önce").
- Projeye özel slash-komut: `templates/command-intake.md` → proje `.axet-code/commands/intake.md` olarak kopyalanır (TUI ctrl+p).
