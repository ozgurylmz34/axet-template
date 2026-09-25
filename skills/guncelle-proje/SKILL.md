---
name: guncelle-proje
description: >
  Use when the user wants to bring ONE open project's aXet template files (AGENTS.md, .axet-code.json,
  .gitignore, .githooks, sap-project.json, validators-local) up to date with the template clone, or when
  doctor / the session brief says "proje şablonu eski" or "proje şablon sürümü kayıtlı değil". Runs
  scripts/guncelle_proje.py step by step: onkontrol, per-project approval, plan, apply automatic cases,
  ask the user about merge cases, close with a report. Triggers: "%guncelle-proje", "proje şablonu eski",
  "proje şablonunu güncelle", "AGENTS.md şablonu güncellensin". Not for updating the template clone itself
  (that is %guncelle), not for creating a project (%yeni-proje), not for a package (new_package.py).
---

# guncelle-proje — bir projenin şablon dosyalarını 3-yollu güncelleme

Tek kod yolu: `<AXET_HOME>/scripts/guncelle_proje.py`. `<AXET_HOME>` = bu skill klasörünün iki üstü
(`<AXET_HOME>/skills/guncelle-proje/SKILL.md`); yolu buradan türet, varsayma, kullanıcıya özel yol yazma.
Hükmü ve raporu SCRIPT verir; sen yalnız yargı gereken yerde kullanıcıya sorar ve kararı işaretlersin.

## When to use this skill
- `doctor.py` ya da oturum özeti "proje şablonu eski" / "proje şablon sürümü kayıtlı değil" dedi.
- Kullanıcı açık projenin template dosyalarını güncellemek istiyor.
- **Kullanma:** template klonunu güncellemek (`%guncelle`) · yeni proje (`%yeni-proje`) ·
  paket (`new_package.py`) · `templates/package/**` (kapsam dışı, K5).

## ⛔ Değişmezler
1. **Her proje AYRI onaylanır.** Toplu tarama YOKTUR. Onay tek proje yoluna ve tek şablon sürümüne
   bağlanır; script bunu zorlar (`onay.json`). Başka projede "zaten onaylamıştı" diye devam etme.
   Onay kesin yasak kanoniğine de bağlıdır: onaydan sonra kanonik değişirse onay düşer (yeni
   damga kalemi eski onayla yazılmaz) → yeniden planla, yeniden onay iste.
2. **Önce klon güncel olmalı** (`%guncelle`). `onkontrol` ölçer; DUR derse önce onu çöz.
3. **Taban uydurma YASAK.** `VTB` (taban bilinmiyor) dosyada otomatik birleştirme yapılmaz;
   kullanıcı "yeniyi al / yereli koru / elle" seçer.
4. **Commit ajanın işi değil.** Proje reposuna commit KULLANICININ onayıyla atılır; `push` asla.
5. Script'in çıktısını **aynen** göster; raporu sen yazma.

## How to use this skill

| # | Adım | Komut | Beklenen | FAIL'de |
|---|---|---|---|---|
| 1 | Ön kontrol | `guncelle_proje.py --proje <dizin> onkontrol` | 0 | 2 → sebebi aynen göster, DUR |
| 2 | Plan (salt-okur, onaysız çalışır) | `… plan` | 0 plan var (dosya ve/veya `DAMGA` kalemi) · 1 güncel: ne dosya ne damga işi var (bitir) | 2 → DUR |
| 3 | Onay — kullanıcı projenin ADINI yazar | `… onay --kabul "<PROJE_ADI>"` | 0 | 2 → ad yanlış, yeniden sor |
| 4 | Otomatik vakalar (V1/V2/V5/V6) | `… uygula --otomatik` | 0 | 1 → `durum` göster, DUR |
| 5 | Yargı vakaları (V4t/V4c/V4B/V7/VTB) | `… oneri <yol>` → sor → `… isaretle <yol> --karar …` | her biri 0 | aşağıdaki karar tablosu |
| 6 | Kapanış | `… kapanis` | 0 | 1 → raporu göster, seçenek sun |
| 7 | Açılış brief'i | kapanış 0 ise proje `AGENTS.md` "Oturum" bölümündeki `session_brief.py` komutu — `.axet-code/acilis-brief.md`'yi güncel şablonla yeniler (git'e girmez). Bulunulan dizin `--proje` dizini değilse komuta `--project-dir "<dizin>"` ekle (izin sorulur) | 0 | son satır "açılış brief'i yazıldı" değilse o satırı ya da yokluğunu aynen bildir |
| 8 | Son | `RAPOR.md`'yi aynen göster | — | — |

**Adım 3 neden 2. adımdan sonra:** plan görülmeden onay istemek, kullanıcıya ne onayladığını
söylemeden onay istemektir. Önce planı göster, sonra onayı iste.

### Yargı vakaları (adım 5)
| Vaka | Ne demek | Ne yap |
|---|---|---|
| `V4t` | İki taraf da değişmiş, git temiz birleştirdi | İki farkı AYRI AYRI tek cümleyle özetle → "birleşik / yereli koru / yeniyi al" sor → `isaretle --karar birlesik\|yerel\|yeni` |
| `V4c` | Çakışma var | Her çakışma bloğu için T/L/Y'yi göster, kendi önerini ve GEREKÇENİ yaz, onay al, öneri dosyasını işaretsiz bırak, sonra `isaretle --karar birlesik` |
| `V4c+ESIK` | Ayrışma eşiği aşıldı (>3 blok ya da yerel fark >%50) | Birleştirme DENEME. `.axet-code/.guncelle-proje/elle/` altındaki iki farkı göster, "elle karşılaştırman gerekiyor" de, `isaretle --karar ertelendi --gerekce …`. **`.axet-code.json`** küçük dosya olduğu için özelleştirilince hep buraya düşer: "yereli koru, yeni `context_paths` girdisini (ör. `.axet-code/acilis-brief.md`) elle ekle" öner; kullanıcı onaylarsa yalnız o girdiyi ekle, sonra `isaretle --karar yerel` |
| `V4B` | İkili dosya | Birleştirme yok: "yereli koru / yeniyi al" sor |
| `V7` | Kullanıcının kendi dosyası, şablonun yeni dosyasıyla aynı yolda | "seninkini `<ad>.yerel` yap ve şablonunkini al (önerilen) / seninkini koru" → `isaretle --karar yeniden-adlandir\|yerel` |
| `VTB` | Taban bilinmiyor | Otomatik birleştirme YASAK. Farkı göster, `isaretle --karar yeni\|yerel\|ertelendi` |

### Kayıtsız (eski) projeler — SHA'sız geri düşüş
Sürüm kaydı (`.axet-code/sablon-surumu.json`) yoksa script tabanı **içerik eşleştirmesiyle** arar:
şablon geçmişindeki hangi sürüm, projedeki dosyayla birebir aynı? Bulursa taban odur; bulamazsa `VTB`.
⚠ Kayıt yoksa **proje adı da bilinmiyordur** (`<PROJE_ADI>` onunla dolduruldu). Script dizin adını
VARSAYAR ve bunu "ad kaynağı: dizin-adi-varsayimi" diye basar. Her şey `VTB` çıkıyorsa ad yanlıştır:
kullanıcıya projenin gerçek adını sor ve `--ad <AD>` ile yeniden planla. **Adı tahmin etme, sor.**

### SAP projesi (damga)
`AGENTS.md`'deki kesin yasak damgası karşılaştırmaya GİRMEZ: üç sürümden de çıkarılır, gövde
birleştirilir, damga sonra yeniden basılır. Damga BOZUKSA (birden fazla BASLA/BITIR) script DURUR —
kullanıcı tek blok bırakmadan güncelleme başlamaz.

Damga, şablon dosyalarından BAĞIMSIZ ölçülür. `%guncelle` kanonik yasak metnini yükseltmiş ama
şablon dosyaları aynı kalmış olabilir. O durumda plan `DAMGA` kalemini gösterir ve 0 döner; adımlar
normal akar (onay → `uygula --otomatik` boş geçer → `kapanis` damgayı basar). *(Z55: v0.5.0'da
plan bu vakada 1 dönüyordu ve damga eski kalıyordu.)* Kapanış raporundaki "Davranış yüzeyi
DEĞİŞTİ" bölümünde tam komut yazar; kullanıcıya AYNEN ver.

### SAP projesi: `KURULUMU-TAMAMLA.cmd` kısayolu (Z79)
Kısayol şablon ağacında DEĞİLDİR (makineye özgü klon yolu taşır, git'e kapalı); `%yeni-proje` yalnız
yeni projeye yazar. Eski SAP projesine de ulaşsın diye plan onu ayrı bir `KISAYOL` kalemi olarak gösterir
(damga gibi: tek başına da plan 0 döner):
- **yok** → "kısayol yazılacak" · **resmi ama eski** (ikinci satırda `rem aXet kurulum kisayolu
  (yeni_proje.py yazdi)` işareti var, içerik farklı; ör. klon yolu değişti) → "kısayol güncellenecek".
  İkisini de onaydan sonra `uygula --otomatik` yazar; eski hâl yedeklenir (`geri-al KURULUMU-TAMAMLA.cmd`),
  `kapanis` diskten doğrular.
- **İşaretsiz** (elle yazılmış / eski geçici sürüm) → EZİLMEZ. Planda ve raporda `BİLGİ` satırı çıkar;
  kullanıcıya AYNEN ilet: dosyayı silip `%guncelle-proje`'yi tekrar çalıştırması önerilir. Dosyayı sen silme.
- SAP dışı projede kalem yoktur. Kısayol davranış yüzeyi değildir, manifest onayı gerektirmez.
**Z48 kararı:** `guncelle-proje` behavior manifest'i KENDİSİ yenilemez. Davranış yüzeyi onayı
bilinçli olarak kullanıcının kendi terminalinde kalır; sen `behavior_manifest.py generate`
KOŞMAZSIN.

### Sonda kullanıcıya söylenecekler
- Rapordaki "aXet'i kapat-aç" satırı ve "Kullanıcının kendi terminalinde" bölümü. SAP projesinde
  (kısayol varsa) bölüm önce çift tık yolunu verir: kullanıcıya **"proje klasöründeki
  KURULUMU-TAMAMLA'ya çift tıkla"** de — onayı o pencere sorar. Kısayol yoksa bölümdeki TAM komutu
  (`behavior_manifest.py generate --project-dir "<proje>"`) AYNEN ver. Bölüm "GEREKLİ" diyorsa onay
  verilmeden `doctor` onaysız değişiklik gösterir. Kısayolu/komutu sen çalıştırma.
- Proje bir ekip reposuysa: "bu değişiklikler commit edilince ekip arkadaşlarına da gider".
- Commit kararı kullanıcınındır; sen commit/push YAPMAZSIN.

## Yapmayacakların
`git reset --hard` · `git push` · `--force` · `git clean` · `plan.json`/`durum.json`/`onay.json`'u elle
düzenlemek · `.conn_adt` okumak · onay olmadan dosya yazmak · planda olmayan bir dosyaya dokunmak ·
raporu kendin yazmak · "tamam" demeden önce `kapanis` çıkışını görmemek.
