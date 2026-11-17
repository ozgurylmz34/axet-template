---
name: deploy-kullanici-testi-sonrasi
description: Uygulamayı SAP'ye (BSP) ya da ortak bir sisteme deploy etmeden önce kullanıcı yerelde test edip açıkça OK demeli
type: feedback
---

Geliştirme bitince sıra: kendi doğrulaman (test, `%code-review`) → uygulamayı yerelde çalıştır → kullanıcıya
"yerelde hazır, test edebilirsin" de → BEKLE. Kullanıcıdan "OK / deploy et" gelmeden deploy yapılmaz; proaktif
ya da "zaten hazırdı" gerekçeli deploy yoktur.

**Neden:** UI5 yerel sunucusu canlı backend'e bağlanır; kullanıcı değişikliği gerçek veriyle yerelde görebilir.
Erken deploy, yanlışsa ortak sistemi kirletir. Testin sahibi kullanıcıdır, deploy onayı da onundur.
**Nasıl uygulanır:** Frontend özelliği yeni bir backend alanına (CDS alanı vb.) bağlıysa yerel test ancak backend
sistemde aktifse çalışır; backend aktivasyonu da SAP'ye yazmadır → ayrıca açıkla, ayrıca onay al. Yalnız frontend
değişikliğinde backend aktivasyonu gerekmez.
- **Deploy kapsamı = çalışma ağacı, onay değil:** UI deploy aracı uygulamanın klasörünü o anki hâliyle paketler. Onay bir
  işe verilir, deploy bir uygulamaya yapılır; aynı uygulamada paralel yürüyen başka bir işin değişikliği de birlikte gider
  (ekip dersinde ölçüldü: deploy edilen paketin içinde öbür işin fonksiyonları ve 9 i18n anahtarı vardı). Onay istemeden önce
  `git status -- <uygulama yolu>` ile başka iş var mı bak; varsa "bu deploy şu işi de taşır" diye fiili kapsamı söyle.
  Listede olmayan uygulama deploy edilmez ve canlıda eski kalır — bunu da söyle. Deploy'dan sonra "deploy edilmedi" diyen
  kayıtları aynı turda güncelle.
- **Yazma brifine deploy adımı koyma:** backend yazımı onaylıyken UI deploy'u henüz onaylı değildir. Ekip dersinde 11
  adımlı bir yazma listesinin son adımı UI deploy'uydu; liste sırayla koşuldu ve uygulama kullanıcı test etmeden canlıya çıktı.
  Deploy ayrı bir adımdır ve kullanıcının "OK / deploy et"inden sonra yazılır. Backend'e bağlı FE için sıra: backend yaz →
  yerelde sun → kullanıcı test eder → "deploy et" → ayrı deploy.
Önceki kayıt: yok
Son-doğrulama: 2026-11-17 (ekip dersinden uyarlandı, deploy kapsamı ve brif vakası eklendi; aXet'te ayrıca ölçülmedi)
