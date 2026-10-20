---
name: diagnosing-bugs
description: >
  Disciplined root-cause loop for a defect whose CAUSE IS NOT YET KNOWN: build a red-capable
  feedback loop first, reproduce and minimise, rank 3-5 falsifiable hypotheses (RCA table with a
  refutation attempt each), probe one variable at a time, then fix at the unit where the defect
  lives. Covers SAP/ABAP (dumps, wrong data, OData/Gateway errors, slow reports), freestyle UI5
  and project scripts or this template's own tooling. Use when something that should work is
  broken, throwing, wrong, flaky or slow and nobody can yet say why. Triggers: "neden
  çalışmıyor", "hata veriyor ama sebebi belli değil", "dump alıyoruz", "ara ara bozuluyor",
  "yavaşladı", "debug et", "kök nedeni bul", "teşhis et". Do NOT use for a new development or a
  change whose cause and scope are already known (use sap-intake-triage), pure code-reading
  questions (use explore), or reviewing a finished diff (use code-review).
---

# Hata teşhisi — kök neden döngüsü

> **Özü (kırpılırsa bu kalsın):** ① Kırmızıya dönebilen bir **geri bildirim döngüsü** kurmadan hipotez kurma.
> ② Hatayı **küçült**. ③ **3-5 çürütülebilir hipotez** + her birine çürütme denemesi (tablo). ④ Her prob
> **tek değişken**. ⑤ Düzeltme hatanın **yaşadığı birimde**; yeni test **projenin test politikasına** göre.
> ⑥ Doğrulanan hipotezi kayda geçir.

**Kaynak ve lisans:** `mattpocock/skills` → `skills/engineering/diagnosing-bugs/SKILL.md` (commit `f3fc563`)
metninin Türkçe çeviri-uyarlaması; faz yapısı ve birçok madde oradan, araçlar ve kurallar aXet'e göre.
Upstream MIT, Copyright (c) 2026 Matt Pocock — lisans metni ve kayıt: `THIRD_PARTY_NOTICES.md` §4.

## When to use this skill
- Çalışması gereken bir şey bozuk, hata/dump veriyor, yanlış veri gösteriyor, ara ara bozuluyor ya da yavaşladı
  **ve sebebi henüz bilinmiyor**.
- **Kullanma:** sebebi ve kapsamı belli bir değişiklik/düzeltme talebi (→ `%sap-intake-triage`) · yalnız "bu kod ne
  yapıyor" (→ `%explore`) · bitmiş bir değişikliğin incelemesi (→ `%code-review`). Teşhis bitip düzeltme kapsamı
  belli olunca SAP düzeltmesi `%sap-intake-triage` → `%sap-dev` yolundan yürür.

## How to use this skill

### 0. Önce ara · gizlilik · otorite
- **Bu hata daha önce yaşandı mı?** Hipotezden önce `%recall` (hafıza + paket `.rules.md`), SAP'de
  `sap-adt-foundation/references/known-errors-adt.md`, ilgili paketin `SESSION_NOTES.md`'si. Tanıdık semptom bir
  sinyaldir; cevap yazılmış olabilir.
- **Gizli bilgi:** `.conn_adt` / `conn/*.env` içeriği okunmaz, basılmaz, loglanmaz. Bağlantı sorununun teşhisi
  `sap_adt_cli.py sap_doctor` ile yapılır (`%sap-adt-foundation` §1). Çıktıda parola/token/çerez yerine `<REDACTED>`
  yaz. Maskelenmiş çıktı yetmiyorsa bunu söyle, kullanıcıya sor.
- **Otorite kaynağını belirle:** DEV bir test sistemidir; eski denemelerden kalan veri yanlış olabilir. Doğruyu
  söyleyen belge/dosya hangisiyse döngü ona göre kurulur.

### 1. Geri bildirim döngüsü kur — işin özü bu
Hatayı **bu hataya özgü** biçimde kırmızıya çeviren, hızlı ve tekrarlanabilir bir komut bulursan sebebi de
bulursun. Döngü yoksa koda bakarak teori kurmak boşa zamandır. Bağlama göre döngü adayları (dump, yanlış veri,
sınıf davranışı, OData, UI5, script/araç, yakalanmış iz, regresyon): **`references/dongu-adaylari.md`**.

⛔ SAP'ye **yazan** her şey (geçici sınıf, iz satırı, test verisi, `adt_classrun`) yazma sınıfındadır:
`--sap-write --scope … --reason …` + kullanıcı onayı (`%sap-adt-foundation` §4) ve SAP kesin yasaklarına tabidir.
Standart veriye yazma yasağı teşhiste de geçerlidir. **Yazmayan döngü varken yazan döngü kurma.**

**Döngüyü sıkılaştır:** daha hızlı mı (kapsamı daralt) · sinyal daha keskin mi ("çökmedi" değil, **kullanıcının
gördüğü semptom**) · daha deterministik mi (tarih, sayaç, kilit, önbellek sabitlensin).
**Ara ara çıkan hata:** hedef temiz bir tekrar değil, **tekrar oranını yükseltmek**tir — döngüyü çok kez koş,
eşzamanlılığı artır, zaman penceresini daralt.

**Döngü kurulamıyorsa DUR:** ne denendiğini listele; kullanıcıdan erişim, maskelenmiş bir artefakt (log, IDoc
numarası, ekran kaydı) ya da **iş gerçeğini** iste. Ayrım: **kullanıcının bildiği/yaptığı** (deneme sonucu,
izlediği adımlar) → önce sor · **verinin/kodun davranışı** (alan dolu mu, kaç kayıt, hangi dal koşuyor) → ölç.

**Faz 1 bitti mi?** Adını verebileceğin, **en az bir kez koştuğun** (komut + maskelenmiş çıktı) tek bir komut var:
- [ ] **kırmızıya dönebilir:** gerçek kod yolunu sürer, kullanıcının tam semptomunu doğrular
- [ ] **deterministik** (ara ara çıkan hatada sabitlenmiş, yüksek tekrar oranı)
- [ ] **hızlı:** saniyeler
- [ ] **senin tek başına koşabileceğin** türde (kullanıcı adımı gerektirmez)

### 2. Yeniden üret + küçült
- [ ] Döngü **kullanıcının anlattığı** hatayı üretiyor, yanındaki başka bir hatayı değil.
- [ ] Birden çok koşuda tekrarlanıyor.
- [ ] Tam semptom (mesaj no + metin, yanlış değer, süre) yakalandı; düzeltme buna göre doğrulanacak.
- [ ] **Kontrol grubu** var: aynı döngü **çalıştığı bilinen** vakada yeşil. Kontrol grubu yoksa elindeki tek
  cümle "bu vakada çalışmadı"dır, "X bozuk" değil.

**Küçült:** girdiyi, çağıranı, ayarı, veriyi ve adımları **teker teker** çıkar; her kesimden sonra döngüyü yeniden
koş. Kalan her öğe hatayı taşıyorsa (hangisi çıkarılsa döngü yeşile dönüyorsa) küçültme biter.

### 3. Hipotez — RCA tablosu
Test etmeden önce **3-5 sıralı hipotez** üret; tek hipotez ilk akla gelene çakılır. Her hipotez **çürütülebilir**
olmalı: *"Sebep X ise, Y'yi değiştirince hata kaybolur / Z'yi değiştirince kötüleşir."* Tahmin yazılamıyorsa o
bir sezgidir: keskinleştir ya da at.

| # | Hipotez | Tahmin (bunu değiştirirsem …) | Çürütme denemesi (komut/ölçüm) | Sonuç |
|---|---|---|---|---|
| 1 | … | … | … | ÇÜRÜTÜLDÜ · AYAKTA · ÖLÇÜLEMEDİ |

- Her hipoteze onu **yanlışlamaya** çalışan bir deneme yazılır; doğrulamaya çalışan değil.
- "AYAKTA" kanıt değildir. Kanıt, tahmini yapılmış bir değişikliğin döngüyü yeşile çevirmesidir.
- **Tabloyu test etmeden önce kullanıcıya göster.** Kullanıcı sıralamayı bilgiyle değiştirebilir ("dün #3'e
  transport geldi") ya da elenmiş hipotezi söyleyebilir. Kullanıcı yanıt vermiyorsa kendi sıranla devam et.
- **Bulgu doğru, mekanizma yanlış olabilir:** semptomu açıklayan ilk mekanizmaya kilitlenme; aynı semptomu
  üreten diğer mekanizmayı da tabloya koy.

### 4. Prob — tek değişken
- Her prob Faz 3'teki **bir tahmine** karşılık gelir. **Aynı anda tek değişken** değiştirilir.
- Tercih sırası: salt-okur ölçüm (`adt_sql_query`, `adt_dump_read`, `adt_get`; OData'da `$metadata` için
  `%sap-ui5-fiori` `fetch_ui_source.py metadata`, entity okuması için kullanıcının tarayıcısı — kimlik bilgisiyle
  istek atan betik YAZMA) → sınır noktalarında hedefli iz → asla "her şeyi logla, sonra ara".
- Geçici iz **etiketli** olur (ör. `DEBUG-a4f2`); temizlik tek aramayla yapılır. SAP'deki iz bir **SAP
  yazmasıdır**: yazma kapısı + aynı etiket + Faz 6'da geri alma.
- **Performans dalı:** iz değil **ölçüm**. Önce taban ölçülür (çalışma süresi, SQL izi, süre ölçen betik), sonra
  bisection. Maliyetin nerede olduğu ölçülmeden kaldıraç önerilmez.

### 5. Düzeltme + regresyon kilidi
- **Düzeltme yeri:** semptomun göründüğü yer değil, **hatanın yaşadığı birim**. Aynı birimi çağıran **kardeş
  çağıranlar** taranır (`adt_where_used`); gerekçesiz dışarıda bırakılan kardeş, eksik düzeltmedir.
- Yeni test (ABAP Unit / karakterizasyon / script testi) **projenin test politikasına** göre yazılır; politikayı
  bilmiyorsan sor. Test **doğru dikişte** yazılır (hatanın gerçek çağrı zincirini sürdüğü yer); daha sığ dikiş
  sahte güven verir. **Doğru dikiş yoksa bu da bir bulgudur**; kaydet.
- SAP kaynağını düzenlemeden önce `adt_get` ile güncel hâli çek (pull-before-edit, `%sap-adt-foundation` §2);
  esaslı düzeltmeden sonra `%code-review`.
- Sıra: küçültülmüş tekrar → kırmızı → düzeltme → yeşil → **orijinal, küçültülmemiş** senaryo Faz 1 döngüsüyle
  yeniden koşulur. Kırmızıyı bir mutasyonla zorladıysan, mutasyonun gerçekten uygulandığını temiz kopyayla
  karşılaştırarak göster.
- SAP'ye yazılan düzeltme: yazma kapısı → **canlı geri okuma** ("aktive edildi" mesajı kanıt değildir).
- Hata aXet template'inin kendi aracındaysa (doctor, kurulum, skill script'i) düzeltmeyi kullanıcı projesinde
  yamama; `%hata-bildir` ile bildir.

### 6. Temizlik + kayıt
- [ ] Orijinal tekrar artık hata üretmiyor (Faz 1 döngüsü yeniden koşuldu, çıktısı var)
- [ ] Regresyon kilidi yeşil, **ya da** neden yok yazıldı (test politikası/onay gereği yazılmadı · doğru dikiş yok)
- [ ] Tüm `DEBUG-…` izleri kaldırıldı (etiketle arandı; SAP'deki iz yazma kapısıyla geri alındı)
- [ ] Geçici prototip/test objeleri silindi ya da açıkça işaretlendi
- [ ] **Doğrulanan hipotez** ve çürütülenler `SESSION_NOTES.md`'ye ve commit/PR mesajına yazıldı
- [ ] Tekrar edebilecek bir tuzaksa `%remember` ile ders (önce `%recall`: zaten yazılı mı?)

## Rules
- Döngü olmadan hipotez yok; hipotez tablosu olmadan prob yok; ölçüm olmadan "sebep bu" yok.
- Teşhis sırasında da SAP kesin yasakları ve yazma kapısı geçerlidir; teşhis yazmayı meşrulaştırmaz.
- Rapor: döngü komutu + çıktı · RCA tablosu (sonuç sütunu dolu) · düzeltme yeri + kardeş çağıran taraması ·
  orijinal senaryonun yeniden koşum çıktısı · ölçülemeyenler "ÖLÇÜLEMEDİ" diye ayrı satırda.
