# Domain ve data element (DTEL)

> Kaynak: ekip ADT playbook'unun domain/DTEL bölümü + domain/DTEL kontrol listesi + ilgili ekip dersleri; aXet CLI'ye uyarlandı.
> ADT geneli: `%sap-adt-foundation` (`foundation-ops.md` §3.2 composite araçlar, §3.3 `master_language`).
> Adlandırma: domain `ZSD001_D_<AD>`, DTEL `ZSD001_E_<AD>` (`%sap-dev` → `naming.md` §4.7). **Ad önerisi kuralı:**
> önce yeniden kullanım; yeni Z domain/DTEL adını standarda uygun öner → canlıda kontrol et (varsa başka ad) → tablo hâlinde
> sun → kullanıcının açık onayı olmadan yaratma (`%sap-dev` §6). Standart objeye append alanı adı önerilmez (kesin yasak A).
> Alan tipleme sırası (released standart DTEL → mevcut Z DTEL → yeni Z DTEL → ilkel tip): `naming.md` §5.
> Ölçümler S/4HANA (`s4_private`) sistemlerde yapıldı.

---

## 1. CLI yolu

### 1.1 Domain yarat
```
cli adt_domain_create '{"name":"ZSD001_D_ORDNO","datatype":"CHAR","length":10,
  "description":"<master_language metni>","package":"<PAKET>","transport":"<TRANSPORT>",
  "decimals":0,"lowercase":false,
  "fixed_values":[{"value":"1","text":"<metin>"},{"value":"2","text":"<metin>"}]}' --sap-write --scope S1 --reason "..."
```
- Composite: guard → varlık ön kontrolü → create → activate → verify (`steps`). Otomatik geri alma yok.
- Readback: `cli adt_get '{"name":"ZSD001_D_ORDNO","object_type":"doma"}'` → tip, uzunluk, **çıktı uzunluğu** (§3), sabit değerler ve metinleri, `masterLanguage`.

### 1.2 Data element yarat
```
cli adt_dtel_create '{"name":"ZSD001_E_ORDNO","domain_name":"ZSD001_D_ORDNO",
  "description":"<metin>","package":"<PAKET>","transport":"<TRANSPORT>",
  "short_label":"<≤10>","medium_label":"<≤20>","long_label":"<≤40>","heading_label":"<≤55>"}' --sap-write ...
```
- 4 etiket dolu, `master_language`'de, **spesifikasyondan** (kesin yasak D). Uzunluk sınırları: kısa 10 · orta 20 · uzun 40 · başlık 55.
- Readback: `cli adt_get '{"name":"ZSD001_E_ORDNO","object_type":"dtel"}'` → `typeName` domain'e bağlı (boş değil), 4 etiket dolu,
  aktif sürüm, `masterLanguage`. Türkçe karakterleri UTF-8 çıktıyla kontrol et (Windows konsolu `cp1252`).

### 1.3 Güncelleme — aXet'te araç yok
**aXet'te araç yok:** mevcut DTEL'in domain bağını değiştirme ve mevcut domaine sabit değer ekleme (önceki araç setinde elle
REST akışı) — araç aktarımı bekliyor. Kullanıcı SE11/ADT'de yapar; sen §4 readback'ini koşarsın. Protokol notu §5.

---

## 2. Built-in tipli DTEL (DATS, TIMS, INT*)
SAP'de `BUILTIN` diye ayrı bir `typeKind` yok: built-in tip, **aynı adlı domain** gibi bağlanır.

| Tip | `typeName` | `dataType` | uzunluk |
|---|---|---|---|
| Tarih | `DATS` | `DATS` | `000008` |
| Saat | `TIMS` | `TIMS` | `000006` |
| INT1 / INT2 / INT4 / INT8 | aynı ad | aynı ad | `000003` / `000005` / `000010` / `000019` |

- DENENEN — BAŞARISIZ: `typeKind=BUILTIN` + boş `typeName` + `dataType=DATS` → aktivasyon `No domain or data type was defined`.
- ÇALIŞAN: `typeKind=domain` + `typeName=DATS` + `dataType=DATS` + `dataTypeLength=000008`.
- aXet: `adt_dtel_create` `domain_name:"DATS"` ile bu eşlemeyi yapıp yapmadığı **DOĞRULANMADI** → readback'te `typeName` kontrol et.

---

## 3. Domain çıktı uzunluğu (output length) ≠ giriş uzunluğu
Yanlış değer aktivasyonda uyarı verir (`Output length (15) is less than the calculated output length (19)`), aktivasyon geçer
ama **ekranda değer kesilir** (özellikle ALV/Dynpro'da QUAN/DEC).

| Tip | Çıktı uzunluğu | Örnek |
|---|---|---|
| `CHAR`, `NUMC`, `DATS`, `TIMS`, `CLNT` | `length` | CHAR(10) → 10 |
| `INT1` / `INT2` / `INT4` / `INT8` | 4 / 6 / 11 / 20 (sabit) | INT4 → 11 |
| `DEC`, `QUAN`, `CURR` | `length + 4` (işaret + ondalık ayırıcı + 2 binlik ayırıcı) | QUAN(15,3) → 19 · QUAN(13,3) → 17 |

- `DEC/QUAN/CURR` gerekçesi: QUAN(15,3) gösterimi `-1.234.567.890,123` = 15 hane + 4 karakter (TR yerel ayarında ondalık virgül).
- aXet: `adt_domain_create` çıktı uzunluğunu bu formülle hesaplayıp gönderir (2026-09-13 düzeltmesi; önceden girdi uzunluğu gidiyordu) ve
  ağdan önce `steps.pre_flight` ile tip/uzunluk/ondalık/sabit değer metnini denetler (`preflight_blocker`). Formül dışı tipler (FLTP, RAW, LANG …)
  reddedilir. Canlı aktivasyonda uyarısız geçtiği **DOĞRULANMADI** → readback'te çıktı uzunluğunu oku, aktivasyon uyarısını geçiştirme.
- Reviewer: `artifact_path` (domain CSV/XML) verilirse `domain_creation_csv` zinciri koşar; verilmezse `reviewer.verdict:"SKIP"` görünür.
- Yanlış çıktı uzunluğunun çaresi (önceki ölçüm, 5 domain): bağımlı DTEL yokken sil + doğru değerle yeniden yarat.
  Silme where-used temiz + kullanıcı onayıyla (`%sap-adt-foundation` → `adt_delete`).

---

## 4. Doğrulama kontrol listesi
1. `adt_get` `dtel`: `typeName` dolu ve beklenen domain · `dataType`/uzunluk domain'le uyumlu · 4 etiket dolu · aktif · `masterLanguage` doğru.
2. `adt_get` `doma`: tip/uzunluk/ondalık · çıktı uzunluğu §3 · sabit değerler (eski + yeni) ve metinleri · `masterLanguage`.
3. `adt_inactive_objects`: domain ve DTEL listede değil.
4. Domain değiştiyse bağımlılar (tablo, CDS, yapı) "inconsistent in active version" olabilir → `tables-structures.md` §1.5 sırası.

---

## 5. Protokol notları (araç aktarımı / teşhis; aXet'te ham REST yazma yok)

### 5.1 Yaratma
- Domain: `POST /sap/bc/adt/ddic/domains?corrNr=<TRANSPORT>`, `Content-Type: application/vnd.sap.adt.domains.v2+xml; charset=utf-8`;
  gövde `<doma:domain adtcore:type="DOMA/DD" adtcore:masterLanguage="…">` + `doma:typeInformation` (uzunluk 6 haneli sıfır dolgulu
  `000010`, ondalık `000000`) + `doma:outputInformation/doma:length` (**çıktı uzunluğu**, §3) + `doma:valueInformation/doma:fixValues`
  (`doma:fixValue` → `position` 0001.., `low`, `high`, `text`). `201` = OK; `AlreadyExists` = var.
- DTEL: `POST /sap/bc/adt/ddic/dataelements?corrNr=<TRANSPORT>`, `application/vnd.sap.adt.dataelements.v2+xml`.
  Kök **`<blue:wbobj xmlns:blue="http://www.sap.com/wbobj/dictionary/dtel">`** + iç içe
  **`<dtel:dataElement xmlns:dtel="http://www.sap.com/adt/dictionary/dataelements">`** (`typeKind`, `typeName`, `dataType`,
  `dataTypeLength`, `dataTypeDecimals`, 4 etiket + uzunluk + max uzunluk). Kökte **`adtcore:responsible`, `adtcore:abapLanguageVersion="standard"`,
  `adtcore:language`** zorunlu.
- `sap-language` hem query parametresi hem header'da; UTF-8 gövde + `charset=utf-8`.

### 5.2 DENENEN — BAŞARISIZ (yaratma)
| Yöntem | Sonuç | Neden |
|---|---|---|
| Yalnız eski kök `dtel:wbobj` (`http://www.sap.com/wbobj/dictionary/dtel`) | `201` ama domain bağı kaybolur (`typeName/` boş) | eski namespace içeriği yok sayılıyor |
| Yeni kök ama `responsible` / `abapLanguageVersion` / `language` eksik | `201` ama 4 etiket boş | SAP etiket içeriğini sessizce siliyor |
| DTEL için kaynak ucuna yazma (`/source/main`) | `404` | DTEL yalnız metadata objesidir, kaynak ucu yok |
| Önceki composite DTEL aracı (eski namespace + eksik öznitelik + yanlış `dataType` sarmalayıcısı) | create `201`, activate `No domain or data type was defined` | kök sebep düzeltildi; ders: araç "OK" dese de readback |
| Eski yaratma script'leri | `CSRF token expired` (3 retry) | retry'da bayat token yeniden gönderiliyordu; düzeltildi |

- Okuma tarafı dersi: DTEL/domain/table type'ın **kaynak ucu yoktur**; okuma obje XML'inden yapılır. Önceki araç seti kaynak ucuna
  sorduğu için canlı objeye `exists:false` diyordu → "yok sanıp yeniden yaratma" riski. aXet `adt_get` bu tiplerde XML okur (kod);
  yine de yaratma/silme kararında `adt_search_objects` ile çapraz kontrol et.

### 5.3 Güncelleme (DTEL domain bağı · domaine sabit değer ekleme)
Sıra: güncel XML'i GET → XML'de değiştir → kilit → PUT → kilidi bırak (`finally`) → aktivasyon → readback.
- Kilit: `POST <obje>?_action=LOCK&accessMode=MODIFY&corrNr=<TRANSPORT>`, `X-sap-adt-sessiontype: stateful`,
  `Accept: application/*,application/vnd.sap.as+xml;dataname=com.sap.adt.lock.result` (anahtar başlık; yanlışında 406).
- PUT: `lockHandle` + `corrNr` query, **`If-Match` GÖNDERME** (ETag yolu kilit kontrolünde kendi kilidini yabancı sayar;
  mesaj sınıfı ve Z tablo kaynağıyla aynı sınıf — `message-class.md` §4).
- Domain PUT'unda **hem `Accept` hem `Content-Type`** = `application/vnd.sap.adt.domains.v2+xml`; `Accept` varsayılanda kalırsa `406 ResourceNotAcceptable`
  (DTEL'de kilitteki `Accept` yetiyordu).
- ⛔ **Açıklama tuzağı:** XML'de `adtcore:description` **iki yerde** geçer — kökte (objenin açıklaması) ve `adtcore:packageRef`'te
  (paketin açıklaması). Düz metin değiştirme ikisini birden değiştirir → paket açıklaması sessizce ezilir ve DTEL readback'i
  bunu görmez. Yalnız kökteki tek eşleşmeyi değiştir; eşleşme sayısı 2 değilse yazma; paketin eski açıklaması hâlâ duruyor mu kontrol et.
- Sabit değer eklemek bağımlılar için kırıcı değildir; aktivasyonda bağlı tablolar için "dönüştürülmeli" bilgi (type `I`) dönebilir — hata değil.
- Etiketler XML'de kalır; yalnız değiştirilen alan değişir. Eski "DTEL PUT sorunlu → sil + yeniden yarat" notu bu desenle
  geçersizleşti; sil + yarat yine gerekiyorsa where-used + onay + dil yeniden yaratmada doğru mu kontrolü.

---

## 6. Yazmadan önce
`checklists.md` §2 (yeniden kullanım önce, ad önerisi canlı kontrollü + kullanıcı onaylı, 4 etiket tam, metin spesifikasyondan, aktivasyon öncesi okuma).

- **Eski sistemden taşınan projede önce tam döküm, sonra kapsam kararı:** "bu eski Z objesi alınacak mı?" kararından ÖNCE ilgili
  eski sistem objelerini tam indir — yapı → DTEL → domain → (Z ise) değer tablosu, özyinelemeli. Hangisinin alınacağı sonra,
  kullanım analiziyle (spesifikasyonda ve hangi objelerde geçiyor) kullanıcıyla kararlaştırılır.
  Neden: kapsam dışı sanılan obje sonradan gerekebilir; kanonik kaynak elde yoksa açıklama/etiket tahmin edilir (kesin yasak D).
  İndirme ucuzdur, tahminle yaratılan objenin düzeltmesi pahalıdır.
  Sınır: aXet CLI projenin bağlantısındaki sisteme okur; eski sistem ayrı bir sistemse erişim yolunu kullanıcıyla belirle,
  bağlantıyı kendin değiştirme (ekip dersi; aXet'te DOĞRULANMADI).

## Bu dosyada ÇIKARILAN / DEĞİŞTİRİLEN
- Tam Python REST şablonları (oturum, CSRF, XML kodu) → protokol notu (§5); sistem client numarası, kullanıcı adı, gerçek obje adları → yer tutucu.
- Toplu yaratma script'leri (`populate_domains.py`, `populate_dataelements.py`) → alınmadı (aXet'te yok; composite araçlar tek tek).
- Araç düzeltme tarihçesi → yalnız "denenen-başarısız" satırı ve readback dersi kaldı.
