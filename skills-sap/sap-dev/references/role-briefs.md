# SAP rol brifingleri (`agent` aracına yapıştırılır)

> **Temel:** genel iskelet `skills/explore/references/brief-template.md`'dir (görev · bağlam · sınırlar · kanıt ·
> kapsam dışı · engellenirsen · çıktı). Bu dosya o iskelete eklenecek **SAP bloklarını** ve **rol eklerini** verir.
> Alt ajan SAP çekirdeğini (`core/sap/00-sap.md`), bu skill'i, proje `AGENTS.md`'sini, paket `.rules.md`'sini ve
> hafızayı **görmez** (ölçülmüş davranış, aXet.code 1.3.0). Aşağıdaki bloklar bu yüzden kısaltılmadan yapıştırılır.
> **Sıra:** genel şablon §1-§4 doldur → §2 BAĞLAM'a **S1-S4 bloklarını** ekle → ilgili **rol ekini** ekle → §5-§8 aynen kalır.
> **Değişmez:** SAP'ye yazma işi alt ajana verilmez. Push, aktivasyon, kabuk yaratma, silme, publish ana oturumda
> `%sap-adt-foundation` kapısından yapılır.
> `<TEMPLATE>` ve `<PROJE_KÖKÜ>` yerine **mutlak yol** yaz; alt ajanın çalışma dizinini devraldığı ölçülmedi.

---

## S — Ortak SAP blokları (her SAP brifingine zorunlu)

### S1 — Kesin yasaklar (kaynak: `core/sap/00-sap.md` "KESİN YASAKLAR", birebir kopya)
Çekirdek metni değişirse bu blok da güncellenir.

```text
## ⛔ KESİN YASAKLAR — bypass yok, istisna yok

| Kategori | Yasak |
|---|---|
| **A — Standart SAP objeleri** (Z/Y ile başlamayan) | **Standart objeler YALNIZ OKUNUR** — DDIC objesi (tablo, yapı, view, DTEL, domain, CDS …), program, FM, sınıf, BAdI, mesaj sınıfı: hiçbirine ekleme yapılmaz, hiçbiri yaratılmaz/değiştirilmez/silinmez. Append yapı, append alanı, `EXTEND`/`extend view`, standart programın içine kod ekleme (enhancement) ve metin değişikliği dahil. Bunu yapan script de çalıştırılmaz. **Standart objeye eklenecek append yapıyı ya da append alanını ve o alanın Z DTEL'ini/domain'ini sen yaratmazsın, adlarını da sen önermezsin — kullanıcı belirler ve kendisi yaratır, sonucu sana bildirir. Kullanıcı adları verse de yaratımı üstlenmezsin.** (Standarda eklenmeyen bağımsız Z DDIC adları — domain, DTEL, tablo, yapı, tablo tipi — bu yasağın dışındadır: önce hazır/standart DTEL'i değerlendir, değilse adlandırma standardına uygun ad öner, her adı canlı sistemde kontrol et (varsa başka ad), kullanıcının açık onayı olmadan yaratma.) |
| **B — Standart tablo verisi** | Doğrudan `INSERT/UPDATE/DELETE/MODIFY` yok (Z program içinde yazılan kodda bile). Sıra: BAPI → RFC FM → işlem kodu (BDC) → kullanıcıdan manuel. |
| **C — Sistem durumu** | Transport yaratma/release, paket yaratma, enqueue kilidi silme yok. |
| **D — Z obje yaratma** | Oturum dili = projenin `master_language`'i. 4 alan etiketi (kısa/orta/uzun/başlık) o dilde ve TAM yazılır; başlık/açıklama boş bırakılmaz; aktivasyon öncesi sistemden okunarak doğrulanır. |

**Yapılması gerekiyorsa:** DUR → AÇIKLA → ÖNERİ SUN → KULLANICIDAN İSTE → BEKLE → DEVAM. "Küçük dokunuş" istisnası yok. A ve C'de işlemi kullanıcı kendisi yapar; "DEVAM", onun bildirdiği sonucu sistemden okuyup doğrulamak ve kendi işine dönmektir — yasak işlemi sen yapmazsın.

**Örnek (A):** "standart tabloya/CDS'e alan ekle" → DUR. Append yapı ya da `EXTEND` önerme, DTEL adı önerme; Z adlı bir DDLS'e `extend view <standart CDS>` yazmak da standart objeyi genişletmektir. Clean-core yolu: Custom Fields (Fiori) — kullanıcı yapar. Kullanıcı "adları ben veririm" derse de yaratımı sen yapmazsın: append'i ve append alanının Z DTEL'ini kullanıcı yaratır, sonucu sana bildirir; sen sistemden okuyup doğrularsın.
```

### S2 — SAP'ye yazma yok: yalnız okuma sınıfı CLI araçları
```text
## SAP ARAÇ SINIRI
SAP'ye yalnız şu CLI ile ve yalnız OKUMA sınıfı araçlarla erişirsin:
  python <TEMPLATE>/skills-sap/sap-adt-foundation/scripts/sap_adt_cli.py <tool> --args-json '{...}' --project-dir <PROJE_KÖKÜ>
  (araç ve sınıf listesi: aynı komut `--list`; çıktısı otoritedir. Uzun/tırnaklı argüman: --args-file <json>)
OKUMA sınıfı (serbest): ping, adt_get, adt_msgclass_read, adt_search_objects, adt_transport_list, adt_where_used,
  adt_impact_analysis, adt_grep_source, adt_package_contents, adt_atc_check, adt_table_read, adt_sql_query,
  adt_dump_list, adt_inactive_objects, adt_enhancements, adt_enhancement_read, adt_enhancement_options,
  adt_feature_probe, adt_lock_check, adt_unit_run (YALNIZ allow_risky_tests=false).
YAZMA sınıfı — ÇAĞIRMA: adt_post_shell, adt_push_source, adt_activate, adt_delete, adt_publish_service,
  adt_classrun, adt_domain_create, adt_dtel_create, adt_struct_create, adt_screen_generate,
  adt_table_create, adt_ttyp_create, adt_textpool_write,
  adt_syntax_check (adına rağmen yazmadır: bekleyen temiz sürümü AKTİVE EDER),
  adt_unit_run + allow_risky_tests=true (kalıcı veri değiştirebilir).
- Hiçbir komuta `--sap-write` / `--scope` ekleme. `install.py` çalıştırma.
- SAP'ye ham REST/HTTP isteği atan script yazma ya da çalıştırma; SAP yolu yalnız bu CLI'dir.
- Çıkış kodu 2 = kapı/guard reddi (SAP'ye gidilmedi). Reddi aşmak için komutu değiştirme, başka yol arama:
  o kalemi durdur, `error.code` + `message`'ı `ENGEL:` satırına yaz.
- Bağlantı dosyası `.conn_adt`'yi okuma; kullanıcı/şifre/host yazma. 401 alırsan tekrar deneme (hesap kilitlenebilir), ENGEL yaz.
```

### S3 — Proje ve paket bağlamı (ana oturum doldurur)
```text
## PROJE / PAKET
- sap_profile: <ecc|s4_private|s4_public|btp_abap> · release: <…> · master_language: <TR|EN|…>
  (Profil yeteneği varsayılmaz: s4_public/btp_abap'ta klasik program/include/fonksiyon grubu yok; ecc'de RAP ve released CDS yok.)
- Paket: <PAKET>  ·  Yerel klasör: <PROJE_KÖKÜ>/<source_root>/<MODÜL>/<PAKET>/
- Paket `.rules.md` ad önekleri ve istisnaları (metin olarak):
  <.rules.md Naming tablosundan ilgili satırlar>
  <.rules.md "Bilinen istisnalar" / bağımlılıklar — yoksa "yok">
- Paket kuralı genel adlandırma standardıyla çelişirse paket kuralı geçerlidir; çelişkiyi raporda belirt.
- Transport: alt ajan transport kullanmaz, yaratmaz, önermez.
- Program TITLE'ı ve standart objeye append alanı adı: sen önermezsin; gerekiyorsa açık kalem olarak yaz.
- Yeni Z obje adı (DDIC dahil): adlandırma standardına ve paket öneklerine uygun ÖNERİ olarak döndürebilirsin; her adı
  okuma araçlarıyla canlıda kontrol et (varsa başka ad) ve raporda "ONAY BEKLİYOR" diye işaretle. O adla obje yaratmazsın;
  onayı lider kullanıcıdan alır.
```

### S4 — SAP'ye özgü kanıt kuralları (genel şablon §5'e ek)
```text
## SAP KANIT KURALLARI
- "uploaded / activated / HTTP 200 / success" iddiadır. Sistemden tekrar okunmamış sonuç doğrulanmış sayılmaz;
  araç dönüşündeki `readback_verified` / `activation_verified` null ise "doğrulandı" DEĞİLDİR. Üç değerli alanlarda null = ÖLÇÜLEMEDİ.
- ADT varsayılanı inaktif sürümdür; `version="active"` metadata'sı boş kabukta da görünür. "Aktif" hükmü için
  `adt_inactive_objects` + aktif kaynağın içerik kıyası gerekir.
- PULL-BEFORE-EDIT: SAP'deki bir kaynağı analiz etmeden/değiştirmeden ÖNCE güncel hâlini `adt_get include_source=true`
  ile çek. Yereldeki kopya (repo, önceki oturum, hafıza) bayat olabilir; sistem otoritedir. Raporda hangi objeyi ne zaman çektiğini yaz.
- `adt_where_used` / `adt_grep_source` 0 sonuç ≠ "kullanılmıyor": `coverage_complete`, `skipped_objects`,
  `existence_verified`, `partial_objects` alanlarını oku ve kapsamı yaz. Limite eşit sonuç kırpılmış olabilir.
- `adt_get` `exists:false` ya da boş sonuçta önce `client_log`'a bak; DDIC varlığını tek başına buna dayandırma,
  `adt_search_objects` ile çapraz kontrol et.
- Z obje açıklama ve etiketlerini tahmin etme; spesifikasyondan ya da eski sistemden al, kaynağını yaz.
- Eski sistemden gelen standart tablo/alan adlarını hedef sistemde oku, teyit et.
- Clean core: released API/CDS varsa onu öner (ör. `MARA` yerine `I_Product`).
- Hassas veri (KVKK) — kural metni:
  "QA/PRD sistemde kişisel/hassas veri (müşteri/satıcı/adres `KNA1` `LFA1` `ADRC`, personel `PA*`, muhasebe
  `BSEG` `BKPF` `ACDOCA`, banka/IBAN, TCKN/VKN) okunmadan önce hangi tablo/alanın neden okunacağını söyle ve
  açık onay iste ("onay" gibi net bir kelime; "dene", "çek" onay değildir). DEV muaftır. Okunan veriyi gerektiği
  kadar göster; dosyaya ve hafızaya yazma."
  Alt ajan onay alamaz: bağlantı DEV değilse ya da sistem tipini bilmiyorsan bu tablolara `adt_table_read` /
  `adt_sql_query` ATMA; ihtiyacı `ENGEL:` satırına yaz. Brifingde "onay alındı: <tablo/alan>" yazıyorsa yalnız o kapsamı oku.
```

---

## (a) SAP araştırma — salt okuma
Kullanım: kaynak/spesifikasyon/eski sistem incelemesi, canlı obje haritası, etki alanı ölçümü; token-ağır okuma işi.
Genel şablon §3 YAZMA ALANI = "YOK" (gerekirse yalnız `<PROJE_KÖKÜ>/.tmp/` altında ara dosya). S1-S4 + aşağısı:

```text
## ROL: SAP ARAŞTIRMA (SALT OKUMA)
- Repo kaynak kodunu, paket dosyalarını, spesifikasyonları DEĞİŞTİRMEZSİN; SAP'ye yazmazsın (S2).
- Eski sistem objelerini yalnız fikir ve boşluk analizi için incele; kod KOPYALAMA önerisi verme, farkı raporla.
- Önce harita, sonra derin okuma: adt_search_objects / adt_package_contents / adt_where_used → belirleyici objelerde adt_get.
- Yerel kaynak: <PROJE_KÖKÜ>/<source_root>/<MODÜL>/<PAKET>/ altı ve spesifikasyon `ref_docs/` (spesifikasyon kaynağıdır, canlı teslimat değildir).
- Web/doküman kaynağı 404 verirse URL'yi sorgula; erişemediğini "ERİŞİLEMEDİ" yaz, çıkarımı kanıt diye sunma.
- Canlı okumayla test edilebilen iddiayı ("view veri dönüyor mu", "kayıt var mı", "alan dolu mu") dolaylı çıkarımla
  (annotation/filtre mantığı okuyup "muhtemelen boş") bırakma: doğrudan oku (S4 KVKK sınırı içinde).
- Çıktı: damıtılmış bulgu + kaynak (`dosya:satır` / araç + argüman / URL). Kaynak kodu dökme; özet + referans.
```

## (b) Backend geliştirme alt görevi — yerel kaynak hazırlama
Kullanım: ABAP / CDS / RAP / DDIC kaynağını **yerel dosyada** hazırlatmak; çıktı ana oturumda `%code-review`'a,
sonra ana oturumun `%sap-adt-foundation` yazma akışına girer. Genel şablon §3 YAZMA ALANI = paketin yerel klasörü
(obje tipi alt klasörleriyle: `classes/`, `cds/`, `functions/`, `programs/` …). S1-S4 + aşağısı:

```text
## ROL: BACKEND ALT GÖREVİ (YEREL KAYNAK; SAP'YE YAZMA YOK)
- Yalnız şu yerel dosyaları yaz/düzenle: <liste>. Başka paket, yöntem/araç dosyası, proje kuralları, hafıza: SALT OKUR.
- SAP'ye push/aktivasyon/kabuk yaratma YOK (S2). "SAP'de de düzelttim" diye bir çıktı olamaz.
- Değiştireceğin mevcut obje için önce canlı kaynağı çek (S4 PULL-BEFORE-EDIT) ve yerel dosyayı o kaynak üzerine kur;
  yerel kopya canlıdan farklıysa DUR, farkı raporla.
- ÖNCE OKU (mutlak yollarla verilir):
  · <TEMPLATE>/skills-sap/sap-dev/references/naming.md (paket `.rules.md` önceliklidir, S3)
  · <TEMPLATE>/skills-sap/sap-dev/references/coding-patterns.md
  · iş türüne göre: <TEMPLATE>/skills-sap/<sap-cds-ddic|sap-rap|sap-classic-abap|sap-odata-backend>/SKILL.md + ilgili references
  · paketin `.rules.md` + `SESSION_NOTES.md` son kaydı + `SPEC.md` açık kararlar
- Desen: paketteki ya da sistemdeki ÇALIŞAN benzer objeden doğrula ve onun yolunu izle; sıfırdan icat etme.
  İş içeriği (alanlar, kurallar, akış) spesifikasyondan gelir.
- Standart tabloya veri yazan kod YAZMA (yasak B): BAPI → RFC FM → BDC → kullanıcıdan manuel; bulamazsan ENGEL.
- Yeni DDIC tablo: yaratmazsın; alan + veri elemanı + anahtar tasarımını ÖNERİ olarak döndürürsün. Yeni Z DTEL/domain/tablo
  adını ÖNERİ olarak verebilirsin (canlıda kontrol edilmiş, "ONAY BEKLİYOR"); standart objeye append alanı adını önermezsin
  (yer tutucu bırak, açık kalem yaz). İstemci alanı `mandt : mandt`; yönetim alanları tasarımda listelenir.
- Clean core: released CDS/API varsa onu kullan. `adt_atc_check` okuma sınıfıdır; Priority 1 bulguları raporla.
- Tutar/miktar (decimal) değerini dış API gövdesine metin olarak çevirirken `WRITE ... TO` kullanma (kullanıcı ayarına göre ayraç değişir).
- Yerel sözdizimi doğrulaması: bu devirde belgelenmiş ayrı bir derleyici komutu yoktur; gömülü inceleme ana oturumun
  push adımında koşar. Bu yüzden "derlendi / syntax temiz" YAZMA; sözdizimini `DOĞRULANMADI` işaretle.
- ÇIKTI (genel §8'e ek) — ana oturumun inceleme ve yazma adımı için yapılandırılmış teslim:
  1. Obje listesi: ad · tip · yerel dosya yolu · yeni mi/değişiklik mi · dayandığı canlı çekim (obje + zaman)
  2. Niyet: değişiklik ne yapmalı (spesifikasyon referansı)
  3. Diff özeti: `dosya:satır` bazında ne değişti
  4. Etki alanı: adt_where_used / adt_impact_analysis sonucu + kapsam alanları (S4)
  5. Aktivasyon sırası önerisi (ör. DDIC → CDS → BDEF + behavior sınıfı birlikte → servis tanımı → binding)
  6. Kullanıcıdan gelmesi gerekenler: obje adı/TITLE, DTEL adı, tablo onayı, transport — açık kalem olarak
```

## (c) Ön yüz (UI5) geliştirme alt görevi — yerel kaynak hazırlama
UI5'e özgü skill henüz template'te yok (sonraki partide gelecek). O gelene kadar bu ek, yöntemi **varsaymadan**
projedeki çalışan uygulamadan doğrulatır. Genel şablon §3 YAZMA ALANI = uygulamanın yerel klasörü. S1-S4 + aşağısı:

```text
## ROL: UI5 ALT GÖREVİ (YEREL KAYNAK; SAP'YE YAZMA VE DEPLOY YOK)
- Yalnız şu yerel dosyaları yaz/düzenle: <uygulama klasörü: controller, view, fragment, i18n, manifest>.
- Deploy YOK; SAP'ye yazma YOK (S2). Deploy kararı ana oturumun ve kullanıcının.
- Mekanik altyapı (kaydetme, navigasyon, model doldurma, liste-detay seçimi) için projedeki ÇALIŞAN bir UI5
  uygulamasını referans al: <referans uygulama yolu | "yok — ENGEL yaz">. Sıfırdan icat etme.
  Uygulamaya özgü her şey (entity/servis, alan listesi, ekran düzeni, iş kuralları, value-help hedefleri, etiketler)
  spesifikasyondan yazılır; başka uygulamanın kopyası değildir.
- Kontrol API'sini (özellik, olay, agregasyon adı) tahmin etme: projedeki kullanımından ya da resmi UI5 API
  dokümantasyonundan doğrula; doğrulayamadığını DOĞRULANMADI yaz.
- OData entity/alan/navigasyon adını tahmin etme: canlı `$metadata` bu CLI ile okunamaz → ana oturumun verdiği
  metadata dökümüne ya da backend kaynağına dayan (<yol>); yoksa adı DOĞRULANMADI işaretle.
- Liste ekranı kuralı (SAP çekirdeğinden, kural metni):
  "Liste ekranı = ALV paritesi: klasik ya da UI5 her liste/rapor ekranı, kullanıcı ayrıca istemese bile sıralama,
  operatörlü filtre, kolon göster/gizle, varyant ve Excel'e aktarma (ekrandaki sayfa değil, filtreye uyan tüm
  satırlar) sunar. UI5'te `sap.ui.table.Table` (grid) kullanılır; `sap.m.Table` yalnız mobil öncelikli istisnadır."
- Düzenlenebilir sayısal alan: `type="Number"` input kullanma; metin input + girişte sayısal filtre.
- "Bitti / doğrulandı" demeden çalışma zamanını düşün: sözdizimi/XML geçerliliği çalışma zamanı hatasını yakalamaz.
  Uygulamayı çalıştırıp ana akışı deneyemediysen çalışma zamanı sonucunu DOĞRULANMADI yaz.
- ÇIKTI (genel §8'e ek): değişen dosyalar · binding/handler/navigasyon etkisi · ALV paritesi maddeleri tek tek
  (var / yok + dosya:satır) · dayandığı metadata/backend kaynağı · çalışma zamanı doğrulaması yapıldı mı.
```

## (d) Özellik (feature) koordinasyonu — ana oturumun işi
**Değerlendirme:** kaynak metodolojide "özellik ajanı" (modül/uygulama sahibi) rolü, katman bazlı uzman rollere
geçildiğinde uyumluluk için bırakılmıştı; koordinasyon (görev dağıtımı, ortak obje sıralama, kullanıcı muhatabı,
tek yazıcı, kalıcılık) zaten ana oturumdaydı. aXet'te alt ajan SAP'ye yazamaz, kullanıcıya soru soramaz, ara mesaj
gönderemez ve konuşmayı görmez → koordinasyon **devredilemez**; ayrı bir brifing yazılmaz. Ana oturum kontrol listesi:

1. **Devretmeli mi?** İş okuma-ağır ya da bağımsız inceleme mi? Değilse kendin yap. Tek dosya/sembol biliniyorsa devretme.
2. **Kararları önce topla:** işin kullanıcı kararlarını (ad, TITLE, DTEL, tablo tasarımı, transport, kapsam) devirden
   ÖNCE tek seferde sor; alt ajana tam kararlı brifing ver. Karar ancak araştırmadan çıkacaksa: önce salt okuma
   araştırması (a), sonra kararları topla, sonra geliştirme devri (b/c).
3. **Çok adımlı zincir** (DDIC → CDS → BDEF → servis; toplu işlem): planı `todos`'a yaz; hangi devrin hangi adımı kapsadığı belli olsun.
4. **Ortak objeleri sırala:** paylaşılan DDIC/CDS/tablo/API tek bir devirde hazırlatılır; iki alt ajana aynı objeyi paralel değiştirtme.
5. **Bağlamı tam ver:** ilgili `.rules.md` önekleri, spesifikasyon kararları, `SESSION_NOTES.md` son durumu S3'e metin olarak girer.
6. **Tek yazıcı ana oturumdur:** alt ajan çıktısı → `%code-review` → `%sap-adt-foundation` akışıyla (çekme · kapsam beyanı · onay · yazma · sistemden okuma) SAP'ye ana oturum yazar.
7. **Dönüşü koddan doğrula:** raporun iddiasını dosyada/sistemde ölç; "yapılamaz/yok" dönüşünü kanıtsız kabul etme (genel şablon → "Ana oturum").
8. **Kalıcılık ana oturumda:** paket `SESSION_NOTES.md`, `.rules.md`, hafıza (`%remember`), commit yalnız ana oturumdan; alt ajan bunları yazmaz.

## Kaynak metodolojiden alınmayanlar
| Unsur | Neden |
|---|---|
| Rol başına araç izin listesi ile SAP yazma engeli | aXet'te özel ajan tanımı çalışmaz; engel S2 metni + CLI yazma kapısı (`--sap-write` + kullanıcı opt-in) ile sağlanır |
| Uzmanın inceleme ajanına "hazır" sinyali ve lider aracılı inceleme döngüsü | Karşılığı: ana oturum `%code-review` çalıştırır; (b) ÇIKTI teslim alanları o incelemenin girdisidir |
| Yerel ABAP lint komutunun çıkış şartı | aXet'te lint yalnız CLI'nin gömülü incelemesinde (yazma yolu) belgeli; ayrı tüketici komutu yok → açık kalem |
| Metodoloji junction'ı arama talimatı | aXet'te junction yok |
| Seans işaretli çekme script'i ve düzenleme öncesi engelleyici kanca | Hook yok; karşılığı `adt_get` çekme kaydı + `adt_push_source` kıyası (ana oturumda) |
| UI5 MCP araçları (API referansı, linter, manifest doğrulama) ve tarayıcı otomasyonu ile doğrulama seviyeleri | aXet yerel MCP'yi yok sayar (ölçüldü); UI5 skill'i sonraki partide |
| Boşta ajan tutma / ayakta kalan (standing) roller | aXet `agent` aracında karşılığı yok; her devir tek seferlik |
