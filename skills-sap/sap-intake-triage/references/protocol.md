# Intake triage — tam protokol

> Kaynak: ekip playbook'undaki intake-triage protokolü + karar kaydı (intake triage kapısı) + S2 inceleme checklist'i;
> tek kullanıcı + tek model + `agent` aracı düzenine uyarlandı.

## Amaç ve ilke
- Bir geliştirme talebini **kapsamına orantılı**, **kişiden bağımsız tutarlı** ve **kanıtlı** biçimde almak — hızı öldürmeden.
- Model her domain'i ezbere bilmez; beklenti bu değil. İş gelince: **sınıflar → isterlerden bilmesi gereken konuları çıkarır →
  hedefli araştırır → ancak bilgilendikten SONRA** değerlendirir, doğru soruları sorar, aksiyon alır.
- **Persona ≠ "act as X".** Serbest "SAP SD danışmanı gibi davran" yönlendirmesi olgusal doğruluğu güvenilir biçimde artırmaz,
  düşürebilir. Değer, yapılandırılmış prosedürden (kontrol listesi + kaynak işaretçisi) gelir. Modül paketleri bu yüzden
  bilgi deposu değil, **tetik haritası + araştırma protokolü + kaynak işaretçisidir**.
- Tutarlılık serbest prompt'la değil, **sabit şemalı artefakt + kontrol** ile gelir (S2).

## 1. Sınıfla (iki dik eksen + kapsam) — gerekçeyle
- **① Fonksiyonel modül (NE iş?):** SD / MM / FI / CO / PP / QM / PM / WM-EWM … Modülü sen belirle; paket varsa oku (adım 2).
- **② Teknik tip (NASIL?):** klasik ABAP / RAP / UI5 / CDS / DDIC … Bu eksen modül değildir; teknik tipe özgü kurallar ilgili SAP
  skill'lerinde ve SAP çekirdeğindedir.
- Örnek: "SD'de yeni RAP raporu" → ① SD paketi (availability/pricing araştır, satış organizasyonu sor) + ② RAP kuralları. Birbirini tamamlar.

**Kapsam (en kritik):**

| Sınıf | Nedir | Örnek | Akış ağırlığı |
|---|---|---|---|
| **S0 · nokta-düzeltme** | tek alan/etiket/mesaj/kozmetik; davranış değişmez | "şu kolon başlığı yanlış", "mesaj metnini düzelt" | HAFİF: where-used → düzelt → doğrula (`%code-review` gerekirse). Soru yok, artefakt yok |
| **S1 · lokalize** | tek uygulama/rapor/CDS içinde davranış değişimi | "bu rapora X kolonu ekle", "bu ekranda hesap yanlış" | ORTA: kısa etki analizi + hedefli soru(lar) + düzelt + bağımsız inceleme |
| **S2 · kapsamlı** | yeni program / çok obje / çok katman (BE+UI) / yeni iş akışı | "yeni sipariş-kalem raporu", "yeni belge tipi" | TAM: aşağıdaki zincir + intake artefaktı + mutabakat |

- Sınır belirsizse bir üst sınıfa yuvarlama — **en makul sınıfı gerekçele**, kullanıcı düzeltebilir. Over-triage (küçük işe ağır süreç) de anti-pattern'dir.
- Sınıf ve gerekçe kullanıcıya görünür biçimde yazılır (tek cümle). Görünürlük yanlış sınıflamayı dizginler.
- **Yeniden sınıflama tetikleri:** yeni obje ya da paket, yeni katman, yeni tüketici/uygulama, standart nesneye dokunma ihtiyacı,
  kabul kriteri sayısının artması. Tetik görülünce dur, sınıfı güncelle; S2'ye çıkılırsa artefakt + mutabakat olmadan yazma yok.

## 2. Modül paketini oku (varsa)
`references/modules/<modül>.md` = o modülün **tetik haritası + zorunlu kontroller + soru şablonu + kaynak işaretçisi**. Paket
"şuna bak, şunu araştır, şunu sor" der; domain olgusunu ezber sanma. Paket yoksa (`references/modules/README.md`) paket uydurma,
genel protokolle ilerle.

## 3. İsterlerden konu çıkar
İsterleri/alanları tara; her anlamlı alan bir **domain konusu** doğurabilir. Önden liste gerekmez, talepten türet:
- "kullanılabilir stok" → availability check / ATP
- "kredi durumu" → kredi yönetimi
- "teslim tarihi / backorder" → scheduling
- "döviz / tutar" → para birimi dönüşümü
Modül paketinin tetik haritası bu çıkarımı hızlandırır.

## 4. 3 eksende araştır — bilgilen, sonra değerlendir
Her konu için hedefli ve ucuz (kapsamla orantılı derinlik):

**(a) Domain bilgisi** — nasıl çalışır? Resmi referans (SAP dokümantasyonu, released API açıklaması). Sözdizimi ve annotation
tahmin edilmez; kaynaktan doğrulanır. (aXet'te web araması aracı yoktur: kaynak kullanıcıdan istenebilir ya da model bilgisi
"DOĞRULANMADI" etiketiyle kullanılır.)

**(b) Canlı sistem ve ilgili kod** — bu sistemde şu an ne var? `%sap-adt-foundation` CLI'nin **okuma** araçlarıyla:
1. Harita: `adt_search_objects` (ad deseni), `adt_package_contents` (paket), `adt_where_used` / `adt_impact_analysis` (tüketiciler).
2. Derin okuma: belirleyici objeler için `adt_get` (kaynak + metadata); veri gerekiyorsa `adt_sql_query` (KVKK kuralı SAP çekirdeğinde).
3. Sorular: ilgili CDS/sınıf/tablo/rapor var mı → **reuse** mu yeni mi · kim tüketiyor → **blast-radius** · mevcut mantıkla **tutarlılık**.
Bu eksen süs bilgi değildir; reuse ve tutarlılık kararı buradan çıkar. Yerel repo (`grep`) ikinci kaynaktır, canlıyı temsil etmez.

**(c) Kurumsal hafıza / prior-art** — biz bunu ya da benzerini yaptık mı, ne öğrendik?
- Ekip hafızası: template `memory/` (indeks her oturum yüklü; ilgili kaydı `view` ile aç).
- Proje hafızası: `.axet-code/memory/` + proje `AGENTS.md` + `.axet-code/intake/` altındaki önceki artefaktlar.
- SAP skill referansları (bilinen hatalar, modül paketi dersleri).
- İki değer: işi tekrar etmemek (deseni reuse et) + hatayı tekrar etmemek (dersi uygula).

**Alt görev devri (token-ağır araştırma):** `agent` aracıyla, `%explore` brifing biçiminde. Brifinge açıkça yaz:
- Görev salt-okumadır; yalnız okuma sınıfı CLI araçları; `--sap-write` içeren hiçbir komut çalıştırılmaz; `.conn_adt` okunmaz.
- Her iddia için kanıt: araç çıktısı (araç + argüman + ilgili alan) ya da `dosya:satır`; "bulunamadı" için arama kapsamı.
- `0` sonuç ≠ yok (aracın kapsam alanlarını raporla: `coverage_complete`, `existence_verified` …).
- Çıktı: eksen başına bulgular + DOĞRULANMADI listesi.
Dönen "yok / yapılamaz / blocker"ı kanıtsız kabul etme; kanıtlardan en az birini kendin doğrula.

### ⛔ Kalite kilidi (enine kesen, atlanamaz)
- **TAHMİN YASAK / kanıt çıpası:** her eksenin çıktısı kanıtlı olmalı; kanıtsız bulgu aksiyonu belirlemez. "activated/çalıştı dedi" kanıt değildir.
- **Z obje hatırlanıyorsa CANLI DOĞRULA:** hafıza yazıldığı anın gerçeğini taşır; Z objeler değişir. Hafıza = **nereye bakacağın**,
  canlı sistem = **ne olduğu**. (c) bir Z objeyi işaret ediyorsa (b) ile teyit zorunlu.
- **Prior-art "sanırım yaptık" değildir:** referansı bul ve doğrula; bulamazsan `yok` say (yanlış-pozitif kopyalamayı önler).
- **"Araç / yöntem / tarif yok" demeden önce ikinci arama:** ilk arama 0 döndüyse **TR + EN eş anlamlılarla, büyük/küçük harf
  duyarsız** ikinci arama yap (ör. numara → "number range|numara aralığı|NR objesi|SNRO|NRIV|NUMBER_GET_NEXT|early numbering";
  salt-okunur → "feature control|read-only|salt okunur"). Skill içeriğinde `rg -i "<desen>" <klasör>`; ikinci arama da 0 ise
  "yok" yaz ve iki aramanın desenini kanıt olarak ekle. ⚠ `bash` içindeki `find` Go tabanlıdır: `-iname` ve `-maxdepth`
  desteklenmez (ölçüldü: `flag provided but not defined`) — bu hata çıktısını "dosya yok" sanma; dosya adı aramasında
  `rg --files --iglob "*desen*"` (büyük/küçük harf duyarsız) kullan.

## 5. Kanıtlı değerlendir
Domain + canlı sistem + prior-art birlikte → aksiyon: reuse mı yeni mi · mevcutla tutarlılık · uygulanacak geçmiş ders ·
blast-radius / risk. Kanıtsız ilerleme yok.

## 6. Kapsamla orantılı soru + aksiyon
- **S0:** soru yok. Makul varsayılanla yap; tek satır "şöyle anladım, yapıyorum". SAP yazmasında `--scope S0 --reason "…"`.
- **S1:** yalnız kritik/belirsiz noktayı sor; makul varsayılan varsa varsay ve bildir. Soruyu adım 4 araştırmasıyla **bilgilenmiş**
  sor (`ask_user`: tek seferde, seçenekli, önerini belirterek). SAP yazmasında `--scope S1 --reason "…"`.
  `ask_user` biçimi (ölçüldü, aXet araç hataları): `options` bir JSON **dizisi**dir (`[{"label":"…","description":"…"}, …]`),
  metin/XML değil; **en az 2** seçenek; her seçenekte `label` dolu. Serbest metin gereken soruda (ör. transport numarası)
  ikinci seçenek olarak "Başka değer yazacağım" ver.
- **S2:**
  1. Artefaktı `.axet-code/intake/<id>.md` olarak üret (`templates/intake-artifact.md`; şema ve kontrol: `s2-artifact-schema.md`).
     Şablondaki yeni bölümler (script bakmaz, manuel kontrol):
     - **Sistem sürümü:** `sap-project.json` `release` ile canlı sistemin sürümünü karşılaştır. `adt_system_info` sürüm
       **döndürmez** (`%sap-adt-foundation` → `tool-catalog.md`); okuma yolu: `adt_sql_query` ile `CVERS` (ör. bileşen
       `S4CORE` / `SAP_BASIS`, alan `RELEASE`) — bu sorgu biçimi canlı **DOĞRULANMADI**, ilk kullanımda sonucu göster. Fark
       varsa (ya da okunamadıysa) kullanıcıya sor; profil/sürüme bağlı kararlar buna göre verilir.
     - **Etkilenen objeler tablosu:** her yeni Z obje için ad önerisi · canlı kontrol sonucu · `ONAY: [ ]`. Ad kuralı
       `%sap-dev` §6: önce yeniden kullanım (standart/released/mevcut Z) → değilse standarda + paket `.rules.md` öneklerine
       uygun ad (tablo ≤ 16, NR objesi ≤ 10, genel ≤ 30) → her adı canlıda kontrol et (`adt_search_objects` / `adt_get`;
       varsa başka ad) → tabloyu sun → **ad başına açık onay**. Genel mutabakat ad onayı sayılmaz. Standart objeye append
       alanı adı önerilmez (kesin yasak A).
     - **Tablo yönetim alanları:** yeni tablo varsa oluşturan/zaman, son değiştiren/zaman ve RAP ETag alanı (yerel son
       değişiklik zamanı) tasarımda alan adı + tipiyle listelenir (`%sap-rap` → `behavior-impl.md` §5, `draft-and-locks.md`).
     - **Kural taraması (onaydan ÖNCE zorunlu):** iş tipine göre ilgili checklist'lerin **BLOCKER** satırlarını oku ve her
       tasarım kararını *uyuyor / sapıyor (gerekçe)* diye işle. RAP → `%sap-rap` `references/checklists.md` §A (+ gerekiyorsa
       `feature-control.md` §5); DDIC → `%sap-cds-ddic` `references/checklists.md`; UI5 → `%sap-ui5-fiori`
       `references/checklists.md`; klasik → `%sap-classic-abap` `references/checklists.md`. Okunan dosyaları bölümüyle yaz.
     - **Sapma kuralı:** standarttan sapan sadeleştirme (ör. numara aralığı yerine MAX+1, feature control yerine yalnız UI,
       draft kararı) "risk" diye yazılıp geçilmez — kullanıcıya **sorulur** (`ask_user`, seçenekli, önerili); cevap
       kural taraması tablosuna yazılır.
     - **Öz-tutarlılık (onaya sunmadan önce):** bir karar değiştiyse riskler, kabul kriterleri ve obje tablosu da aynı turda
       güncellenir (vaka 2026-09-21: karar değişti, riskler bölümü eski adları ve eski kararı taşımaya devam etti); "yok /
       yapılamaz" diyen her madde ikinci aramadan geçmiş olmalı; `ONAY` kutusu boş yeni Z adı kalmamalı.
  2. Kabul kriterlerini EARS kalıbında yaz; her gereksinim test edilebilir olmadan build başlamaz (INVEST / Definition of Ready).
     Backend ve frontend için ayrı hazır-olma tanımı.
  3. Yeni programda ekran + fonksiyonel spesifikasyonu iste, eski sistem/uygulama ile sentezle.
  4. Kullanıcıyla **madde madde mutabakat**; işareti ancak açık onaydan sonra koy.
  5. Kontrolü koş (şema dosyasındaki komut); geçmeden SAP'ye yazma. SAP yazmasında `--scope S2 --intake .axet-code/intake/<id>.md`.

**EARS kalıpları:**
- Olay güdümlü: "Kullanıcı VA01'de belgeyi kaydettiğinde sistem X yapmalı."
- İstenmeyen durum: "Miktar kapasiteyi aşarsa sistem uyarı vermeli."
- Durum güdümlü: "Belge bloklu iken sistem teslimat oluşturulmasına izin vermemeli."
- Her zaman geçerli: "Rapor her satırda para birimini göstermeli."

## 7. Çıkışta öğrenileni kaydet
Yeni ders/desen → `%remember` (projeye özel → `.axet-code/memory/`; her projede geçerli → ekip hafızasına öneri, commit/PR ile).
Modüle özgü yeni tuzak → modül paketine satır önerisi. Döngü: girişte prior-art oku ↔ çıkışta yaz.

## S2 manuel kontroller (şema kontrolüne ek)
| Kontrol | Nasıl | Önem |
|---|---|---|
| Etkilenen Z objeler canlı doğrulandı mı (hafızadan değil)? | artefakttaki her obje için araç çıktısı referansı | engelleyici |
| Kabul kriterleri EARS kalıbında ve test edilebilir mi? | her kriter için "nasıl test edilir" cevaplanabiliyor mu | uyarı |
| Yeni Z obje adları önerildi + canlı kontrol edildi + ad başına ONAY alındı mı? | obje tablosunda araç çıktısı ve işaretli `ONAY` | engelleyici |
| Kural taraması yapıldı mı; sapmalar soruldu mu? | okunan checklist'ler + karar tablosu | engelleyici |
| Artefakt kendi içinde tutarlı mı? | Öz-tutarlılık satırı; riskler bölümü son kararları taşıyor | engelleyici |

## Değerlendirme — protokol gerçek katkı mı, plasebo mu?
Değer iddia değil ölçümle doğrulanır: **protokol var / yok masa testi.** Aynı temsili talep (ör. "satış siparişi kalem raporu +
kullanılabilir stok kolonu") iki koşulda çalıştırılır, çıktı rubrikle kıyaslanır:
- **A (protokol yok):** bu skill ve modül paketi devre dışı, ham prompt.
- **B (protokol var):** bu skill + SD paketi.

**Rubrik (her madde 0/1):**
1. Doğru modül + kapsam sınıflandı mı?
2. "Kullanılabilir stok" → ATP konusu çıkarıldı mı?
3. Canlı sistemde mevcut stok view'ları arandı, reuse kararı verildi mi (eksen b)?
4. Prior-art tarandı mı (eksen c)?
5. SD'ye özgü doğru soru(lar) soruldu mu (satış organizasyonu / özel stok E / üretim yeri-depo yeri)?
6. Havuz semantiği / set-tabanlı SUM eksik sayımı gibi tuzak yakalandı mı?
7. Kanıtsız varsayım YOK mu?

**Ölçüt:** B'nin toplamı A'dan belirgin yüksekse protokol katkı üretiyor; eşitse plasebo. Yöntem: iki ayrı yeni aXet oturumunda
elle masa testi; sonuç `%remember` ile ekip hafızasına.

---
**Kaynağa göre çıkarılan:** kullanıcı prompt'una bağlı regex hook'u, SAP araç sınırındaki deterministik geri-ağ, obje-tipi
checklist enjektörü (aXet'te hook yok — tetik skill `description`'ı ve SAP çekirdeğidir) · lider/uzman ajan/bug-gate rolleri
(→ tek model + `agent` + `%code-review`) · docs-MCP (aXet'te yerel MCP ve web araması yok) · paket `SESSION_NOTES` (→ proje hafızası)
· gün-sonu terfi / T-tetikleri (→ `%remember`) · reviewer script çağrısı (→ `s2-artifact-schema.md` kontrol komutu).
