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
- Hata düzeltmesiyse: yama kusurun ASIL yaşadığı birimde mi, yoksa semptomun göründüğü yerde mi? O birimin kardeş
  çağıranları (aynı kusura açık başka kullanım) da düzeltildi mi; gerekçesiz dışarıda kalan kardeş = WARNING.
  Düzeltmenin yerini sorgulamak (mimari tercih) yalnız NOTE'tur.
KURAL: Her bulgu `dosya:satır` + somut hata senaryosu (girdi → yanlış sonuç) içermeli.
Senaryosu kurulamayan şüpheyi NOT olarak yaz, BLOCKER yapma.
KANIT TİPİ: her bulgu kanıtının kaynağını taşır — `canlı` (çalışan sistemden bu incelemede okundu) · `kaynak` (kod,
diff, yerelde koşulan test/araç çıktısı) · `doküman` (spesifikasyon, yorum, README'deki DAVRANIŞ anlatımı). Kural
metninin (kontrol listesi, standart) ihlali kodda görünüyorsa kanıt `kaynak`tır. Kodun ya da sistemin ne yaptığına
dair iddia yalnız dokümanda duruyorsa bulgu BLOCKER olamaz: en fazla WARNING + aşağıdaki doğrulama listesine madde.
ÇIKTI:
1. Bulgular önem sırasıyla: B<n> [BLOCKER | WARNING | NOTE · canlı | kaynak | doküman] dosya:satır — sorun — senaryo — öneri
2. KAPSAMA TABLOSU: yukarıdaki kontrol listesinin her maddesi bir satır — UYGUN | İHLAL→B<n> | UYGULANMAZ (gerekçe) |
   DOĞRULANAMADI (neden) — kanıt. Kanıtsız UYGUN yazma.
3. SİSTEMDE KALAN DOĞRULAMALAR (yoksa "yok"): burada kanıtlanamayan, çalıştırarak ya da hedef sistemde doğrulanması
   gereken her kontrol — madde · neden kanıtlanamadı · kim doğrular.
4. Tek karar: PASS / WARNING / BLOCKER. PASS = "baktığım yüzeyde bulgu yok"; 3. liste boş değilse "kanıtlandı" deme.
```

3. **Bulguları doğrula:** her BLOCKER'ı kendin okuyarak teyit et; kanıtlanamayanı düşür ya da NOT'a indir. `doküman`
   kanıtlı BLOCKER'ı WARNING'e indir. Kapsama tablosunda atlanan madde varsa rapor eksiktir: o maddeler için yeniden devret.
4. **Sun:** önem sırasıyla, her biri `dosya:satır` + senaryo + kanıt tipi; sistemde kalan doğrulamaları ayrı yaz ve
   ya kendin ölç ya da kullanıcıya açık kalem olarak bildir. Kullanıcı düzeltme istemediyse düzeltmeden önce sor.

## SAP değişikliği
SAP skill'leri açıksa ve değişiklik SAP backend'iyse (ABAP, CDS, RAP, DDIC, klasik OData) bu akış yerine
`%sap-code-review` kullanılır: obje tipi kontrol listeleri, çevrimdışı kontroller ve SAP inceleyici brifingi oradadır.
UI5 uygulaması → `%sap-ui5-fiori` · FS/TS/kullanıcı dokümanı → `%sap-fs-ts-docs`.

## Rules
- İnceleyen değişiklik yapmaz; düzeltme ana oturumda yapılır.
- Spekülatif "blocker" üretme: doğrudan okunabilen bir iddia okunmadan bulgu olmaz.
- SAP paketi açıksa kontrol listesine SAP kesin yasaklarını ekle.
- Kural ya da talimat metni inceleniyorsa (skill, kontrol listesi, `AGENTS.md`), `%write-skill` "Kural yazarken"
  bölümündeki alanlar ve testler de kontrol listesine girer.
