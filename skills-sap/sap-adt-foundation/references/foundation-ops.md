# ADT temel işlemleri — okuma, yaratma, push, aktivasyon, kilit, transport, paket, arama

> Kaynak: ekip ADT playbook'unun "foundation" bölümü (logon · download · push/activate · lock · paket ·
> transport · search) + araç semantiği notları; aXet CLI'ye uyarlandı.
> Sorgu/where-used/ATC/OData: `foundation-query.md` · hata indeksi: `known-errors-adt.md` ·
> araç argümanları: `tool-catalog.md` · CLI'nin gerçek argümanları için otorite: `sap_adt_cli.py --list`.
>
> **Okuma kuralı:** "ÇALIŞAN YÖNTEM" ve "DENENEN — BAŞARISIZ" satırları ölçülmüş deneyimdir; kısaltılmadı.
> Bölümlerdeki ham ADT REST akışları (endpoint, header, XML) **araç bakımı ve teşhis** içindir:
> aXet'te SAP'ye yazma yalnız CLI ile yapılır, ham REST ile yazan geçici script yazılmaz
> (SAP çekirdeği: "guard reddini aşmak için başka yol arama"). CLI bir akışı desteklemiyorsa DUR,
> kullanıcıya bildir.

CLI çağrı biçimi (aşağıda kısaca `cli <tool> '{…}'` diye yazılır):
```
python <TEMPLATE>/skills-sap/sap-adt-foundation/scripts/sap_adt_cli.py <tool> --args-json '{...}'
# yazma: ... --sap-write --scope S1 --reason "<gerekçe>"
```

---

## 1. Bağlantı kontrolü

| Adım | Çağrı | Başarı göstergesi |
|---|---|---|
| CLI ayakta mı | `cli ping` | `ok:true` |
| Bağlantı katmanları (tek komut) | `cli sap_doctor` (yerel: `'{"live":false}'`) | `verdict` PASS/WARN; FAIL satırı neyi düzelteceğini söyler; `not_checked` bakılmayanlar |
| Sistem gerçekten yanıt veriyor mu | `cli adt_get '{"name":"<BİLİNEN_OBJE>","object_type":"class","include_source":false}'` | `ok:true, exists:true` |
| ADT yetenekleri | `cli adt_feature_probe '{"filter":"datapreview"}'` | collection listesi |

- `ping` yalnız CLI'nin çalıştığını söyler, SAP'ye ulaşıldığını değil.
- `sap-project.json` yoksa CLI yalnız `ping` ve `sap_doctor` açar (fail-closed) → kullanıcıdan doldurmasını iste. `sap_doctor` bu durumda
  da çalışır ama yerel ön koşul FAIL iken SAP'ye gitmez.
- `.conn_adt` yoksa: geliştirici **kendi terminalinde** `python <foundation>/scripts/setup_credentials.py` çalıştırır (parola `getpass`,
  yankılanmaz; etkileşimsiz çağrıda hiçbir şey sormadan çıkış 3). Sen çalıştırmazsın, parolayı istemezsin. Örnek biçim:
  `assets/.conn_adt.example` (yalnız yer tutucu).
- ⚠ Ağ/DNS kesintisinde `adt_get` `ok:true` + `exists:false` dönebilir → "obje yok" ile "sunucuya
  ulaşamadım" aynı görünür. `exists:false` gördüğünde önce `client_log`'a bak (`NameResolutionError` vb.).
- Kimlik bilgisi değiştikten sonra ilk `401`'de şifreyi tekrar tekrar denetme (hesap kilidi riski):
  Önceki araç setinde uzun ömürlü araç süreci bağlantı dosyasını **başlangıçta** okuyup bellekte tuttuğu için
  dosya düzeltilse de eski şifre kullanılıyordu (çare: süreci yeniden başlatmak). aXet CLI her çağrıda
  yeni süreçtir; dosyayı her çağrıda okuyup okumadığı **DOĞRULANMADI** — 401 sürerse kullanıcıya bildir,
  körlemesine tekrar deneme (retry bütçesi tut).

---

## 2. Obje okuma / indirme

**ÇALIŞAN YÖNTEM:** `adt_get`
```
cli adt_get '{"name":"ZDEMO_C_SO_ITEM","object_type":"ddls"}'
cli adt_get '{"name":"ZCL_DEMO_CLASS","object_type":"class","include_source":false}'   # yalnız metadata
```
- Tipler: `class`, `interface`, `ddls` (CDS), `bdef`, `srvd`, `prog`, `include`, `fugr`, `func`, `doma`,
  `dtel`, `tabl`, `structure`, `ttyp`, `msag` (→ `adt_msgclass_read`), sınıf alt-include'u `ccimp`/`ccau`/`ccdef`/`ccmac`
  (`name` = ana sınıf) … (tam liste: `--list` + `tool-catalog.md`).
- `enqu` (kilit objesi): **yalnız varlık** — `include_source:false` şart (`true` → `unsupported_type`, ağa gidilmez). 200 → `exists:true` ·
  404 → `exists:false` · diğer kod/istisna → `ok:false` (ÖLÇÜLEMEDİ, "yok" değil). Salt GET; kilit açmaz, enqueue kilidi silmez.
- Dönen kaynağı dosyaya **sen** yazarsın. Klasör kuralı: paket adıyla eşleşen klasör, altında tipe göre
  `classes/`, `cds/`, `functions/`, `programs/`, `ddic/`.
- ⚠ **Repo canlıdan İLERİ olabilir (ekip dersi):** SAP'ye henüz push edilmemiş yerel iş (commit'li ya da değil) varken
  "canlı daima güncel" varsayımı yanlıştır; `adt_get` çıktısını izlenen yerel dosyanın ÜZERİNE yazmak o işi siler (vakada
  tek oturumda 3 kez oldu; iş commit'li olduğu için git'ten geri alındı — commit'siz olsaydı kayıp kalıcıydı). Üzerine
  yazmadan önce bir **çapa** ölç: yerelde olup canlıda olmaması gereken bir sembol seç, `adt_get` çıktısında say
  (canlıda 0 ↔ yerelde N ⇒ repo ileri). Repo ileriyse canlıyı AYRI bir dosyaya yaz, `git diff --no-index <yerel> <canlı>`
  ile kıyasla ve yerel işi canlı tabanın üzerine yeniden uygula (taban daima canlıdır — SKILL §2). Beklenmedik bir
  değişiklik gördüysen önce `git diff`'e bak; "araç çekti, demek ki canlı doğru" deme. Bir objede sapma bulursan aynı
  commit'teki diğer objeleri de tara (push yarım kalmış olabilir).
- **DENENEN — BAŞARISIZ:** eski `download_object.py --type` seçenekleri `ddls`/`cds` içermiyordu; dokümandaki
  `--object-type DDLS` örneği iki kez yanlıştı (bayrak adı da tip de yoktu). Ders: var olmayan bir
  yeteneği vaat eden doküman eksik dokümandan beterdir → argümanı `--list`'ten doğrula.
- Mesaj sınıfı (MSAG): `adt_get` desteklemez → `adt_msgclass_read`.
- Tablo/yapı: `tabl` `/ddic/tables/`e, `structure` `/ddic/structures/`e sorar; biri 404 verirse kardeş uç
  da denenir (`sibling_probe`). DDIC objesinin varlığını yaratma/silme kararında `adt_get` ile TEK BAŞINA
  ölçme → `adt_search_objects` ile çapraz kontrol.
- FM (`func`): generic URL yoktur; `adt_get`/`adt_lock_check` `func` için güvenilmez (grup çözümleme).
  Varlık için `adt_search_objects`. FM gövdesi fonksiyon grubunun `L<FG>U01` benzeri include'larındadır.
- **Sürüm tuzağı:** `source/main` parametresiz GET ADT'de **inaktif** sürümü döndürür. Aynı sınıf aynı anda:
  parametresiz → 10.659 bayt gerçek kod · `version=active` → 192 bayt boş kabuk (ölçüm). "Aktif kod ne?"
  sorusunda hangi sürümü okuduğunu bil; araç dönüşünde bunu açıkça göremiyorsan `adt_inactive_objects`
  ile çapraz kontrol et.
- Legacy `.txt` / eski sistemden kopya: eski sistemdeki standart tablo/alan adlarını hedef sistemde teyit et.

---

## 3. Z obje yaratma

### 3.1 Genel akış (atom araçlar)
```
1. cli adt_transport_list            → kullanıcı transport numarasını verir/teyit eder (uydurma yok)
2. cli adt_get '{"name":"ZDEMO_X","object_type":"class","include_source":false}'   → exists:false bekle
3. cli adt_post_shell '{"object_type":"class","name":"ZDEMO_X","package":"ZDEMO_PKG",
                        "transport":"<TRANSPORT>","description":"<master_language metni>"}'  --sap-write ...
4. cli adt_push_source '{"name":"ZDEMO_X","object_type":"class","source":"...","transport":"<TRANSPORT>"}' --sap-write ...
5. cli adt_activate '{"name":"ZDEMO_X","object_type":"class"}' --sap-write ...
6. cli adt_get (tekrar) + cli adt_inactive_objects   → doğrula
```
- `adt_post_shell` `ok:false` **"yaratılmadı" demek değildir** (ölçüldü, 4 obje: araç 400/500 dedi, kabuk
  yaratılmıştı). `exists_after: true` → tekrar yaratma, push ile devam · `false` → yeniden denenebilir ·
  `null` → ÖLÇÜLEMEDİ, elle doğrula. `error`: `already_exists` · `description_too_long` (gerçek 400,
  ölçülen sınıf sınırı 60 karakter) · `create_failed` (ham sebep `client_log`'da).
- ADT 400'lerinde **ham gövdeyi oku** — sebep orada yazılıdır (kolon adı · metin sınırı · zaten var).
- **Tipe özel kabuklar (2026-09-13, çevrimdışı test edildi, canlı DOĞRULANMADI):** `adt_post_shell` artık `ddls`, `srvd`, `bdef`, `fugr`,
  `func` (`extra.function_group`), `msag` (yalnız kabuk), `enqu` (`extra.primary_table`+`lock_fields`), `ttyp` (`extra.row_type`) kabuğu açar;
  tablo + reçete kaynakları: `tool-catalog.md` → `adt_post_shell`. Başarıdan sonra da varlık sondası koşar: 2xx ama obje yok →
  `create_not_persisted` (MSAG'de DEV olmayan paketle ölçülmüş sahte-200 sınıfı). `ddlx`/`dcls` kabuğu v0.5.2'den beri var (canlı ölçüldü
  2026-09-22); `srvb` → `unsupported_type` (kabuğu kullanıcı ADT/Eclipse'te açar). Açıklama boşsa `ADR_0005_D`.
- **Mesaj sınıfına mesaj yazma (2026-09-13, çevrimdışı test edildi, canlı DOĞRULANMADI):** `adt_msgclass_read` (canlı liste + pull kaydı) →
  nihai listeyi kullanıcıya göster → `adt_msgclass_write`. Araç canlı listeyi okuyup **birleştirir** (verilmeyen mesajlar korunur), mevcut mesajı
  değiştirmek `allow_overwrite=true` ister; yazma sonrası canlı liste beklenenle kıyaslanır. ⛔ Gövdeden çıkarmak mesajı SİLMEZ (SAP no-op); silme
  yalnız ayrı çağrıda `delete_numbers` ile (`<mc:deletedmessages>` + kilit altı yeniden okuma + `delete_gate`; `sap-cds-ddic` message-class §3.7).
  Kaynak reçetenin kilit silen "güvenlik ağı" alınmadı (Yasak C): kilit alınamazsa `lock_conflict` → kullanıcı SM12'de kendi kilidini kontrol eder
  (§5). Metin ≤ 73 karakter, `master_language`'de. Ayrıntı: `tool-catalog.md` → `adt_msgclass_write`.

### 3.2 Composite DDIC araçları
`adt_domain_create`, `adt_dtel_create`, `adt_struct_create`: guard → varlık ön-kontrolü → create → activate
→ verify; sonuç `steps` alanında.
2026-09-21 eki: `adt_table_create` (kabuk + kilitli DDL + aktif DDL readback) ve `adt_ttyp_create` (iki kanallı readback + boş satır tipinde
bir kez düzeltme) aynı politikayla (atomik yaratma, geri alma yok) — `tool-catalog.md`; `s4_private`, canlı DOĞRULANMADI.
- Otomatik geri alma YOK (bilinçli): aktivasyon düşerse obje inaktif kalır; kullanıcı düzelt-aktive-et ya da sil kararı verir.
- **Domain (2026-09-13):** `adt_domain_create` ağdan önce argümanları denetler (`steps.pre_flight`; BLOCKER → `preflight_blocker`) ve çıktı uzunluğunu
  formülle gönderir: CHAR/NUMC/DATS/TIMS/CLNT = length · INT1 4 · INT2 6 · INT4 11 · INT8 20 · DEC/QUAN/CURR = length+4. Yanlış çıktı uzunluğu
  aktivasyonda "Output length (15) is less than the calculated output length (19)" uyarısı ve ekranda kesilme üretir; önceki araç setinde düzeltme
  sil + doğru uzunlukla yeniden yarat oldu (DTEL bağlanmadan önce). Domain CSV/XML'i `artifact_path` olarak verilirse `domain_creation_csv` incelemesi de koşar.
- **DTEL etiket uzunlukları (2026-09-13):** `adt_dtel_create` artefakt olmasa da ağdan önce ≤ 10/20/40/55 (kısa/orta/uzun/başlık) denetler →
  aşım `ADR_0005_D`. Metni kısaltmak onaylı metni değiştirir → kullanıcıya sor.
- **Struct DTEL denetimi (2026-09-14):** SAP'ye yazılan yük `fields[]`'tir; yazmadan önce `fields[]`'teki Z/Y ve `/ad-alanı/` tiplerinin SAP'de
  DTEL olarak var ve aktif olduğu **her çağrıda** denetlenir (`check_struct_field_dtel_active.py`, görev `struct_fields_dtel`). `artifact_path`
  verilirse artefaktın `struct_creation` zinciri de koşar ve hükümler birleşir; yol bulunamazsa `artifact_not_found` → `reviewer_blocker` (ağa
  gidilmez). DTEL değil de yapı/tablo/tablo tipi olan alan atlanır. Yazmayı durduran ölçülemeyen dallar: SAP okunamadı · gate'in süre bütçesi
  (istemci kurulumu + tüm SAP okumaları için gerçek toplam, varsayılan **28 sn** — damlayan/asılı yanıtta da; tekrar deneme yok) doldu → ÖLÇÜLEMEDİ, denetlenen/denetlenmeyen aday sayısıyla · zincir
  sarmalayıcı bütçesini (varsayılan **60 sn**) aştı → `reviewer_timeout` → BLOCKER (ÖLÇÜLEMEDİ; **canlı — SAP'ye bağlanan — BLOCKER gate taşıyan HER zincirde**: `table_creation`, `table_update`,
  `struct_creation`, `struct_fields_dtel`, `struct_post_create`, `sap_active_check`; canlı BLOCKER taşımayan zincirlerde WARNING). Bütçe YAPILANDIRILABİLİR: `AXET_REVIEWER_BUTCE_SN` üç katmanı
  birlikte yükseltir/düşürür (5-900 sn), yalnız gate payı için `AXET_DTEL_GATE_BUTCE_SN`; zaman aşımı mesajı bu yolu kendisi yazar (K10 — IMPLEMENTATION §20.9). Standart DTEL'ler
  denetlenmez — onları `adt_get` ile doğrula.
- DTEL: 4 etiket (kısa/orta/uzun/başlık) `master_language`'de, dolu. Metinler spesifikasyondan; tahmin yok.
  **Standart objeye append: adı AI önermez, append'i ve append alanının Z DTEL'ini AI yaratmaz — kullanıcı yaratır (kesin yasak A; standart objeler yalnız okunur).** Yeni bağımsız Z DTEL
  adı `%sap-dev` §6 kuralıyla: standarda uygun öneri + canlı kontrol + kullanıcının açık onayı.
- ⚠ **`adt_struct_create` tek başına alanları YAZMAYABİLİR** (ölçülmüş: SAP'de
  `component_to_be_changed : abap.string(0)` yer tutucusu kaldı, araç create+activate OK dedi).
  Önceki araç setinde çalışan yol: struct'ı composite ile kabuk olarak yarat → tam DDL'i
  `adt_push_source(object_type="structure")` ile gönder → aktif sürümde alanları oku.
  - DENENEN — BAŞARISIZ: `adt_push_source(object_type="tabl")` ile struct → `423 Invalid lock handle`
  - DENENEN — BAŞARISIZ: `adt_post_shell` ile struct → `Unsupported object type: TABL/DS`
  - Struct aktive olmuyor + `X and Y point to different domains` → kullanılan Z DTEL'lerin domain'i yabancı
    anahtar hedef alanıyla uyumsuz; DTEL tasarımını kullanıcıyla düzelt.
- Yeni DDIC tablo öncesi alan + DTEL + anahtar tasarımını göster, açık onay al (SAP çekirdeği).

### 3.3 `master_language` (Yasak D) — ölçülmüş tuzaklar
- SAP, yaratma gövdesindeki `adtcore:masterLanguage` özniteliğini ve `sap-language` header'ını **tek başına
  görmezden gelebilir**. Önceki araç setinde çalışan yöntem: logon isteğinde (`/sap/bc/adt/discovery`)
  `sap-client` ve `sap-language` birlikte query parametresi olarak + oturumun varsayılan header'larında
  `sap-language`. Kök sebep: istemci oturumunda `sap-client` vardı, `sap-language` yoktu → ilk logon EN.
  aXet CLI yazma kapısı, bağlantı dilinin (`.conn_adt` `ADT_SAP_LANGUAGE`, varsayılan EN) `sap-project.json`
  `master_language` ile aynı olmasını ağdan önce ister; farklıysa `language_mismatch` (çıkış 2) ve dil sessizce
  eşitlenmez → kullanıcı `.conn_adt`'yi düzeltir. Bu kontrol **oturum dilini** denetler; SAP'nin objeyi gerçekten o dilde
  yarattığını kanıtlamaz → her yaratmadan sonra metadata'dan `masterLanguage`'i oku; beklenen değil ise DUR ve bildir.
- **EN-yapışkan isim:** daha önce EN yaratılıp silinmiş bir isim, doğru yöntemle bile tekrar EN gelebilir
  (metadata önbelleği). İsim zehirlendiyse: farklı isimle doğrula; asıl isim için operatör (TADIR dil
  sıfırlama) ya da yeni isim — karar kullanıcının.
- Aynı oturumda art arda yaratılan objelerde ilki TR, sonrakiler EN olabilir; önceki araç setinde her obje için
  ayrı oturum en güvenli yoldu. CLI her çağrıda yeni süreç açıyorsa bu risk azalır — **DOĞRULANMADI**.
- Dil yaratma anında set edilir, yerinde değişmez → düzeltme = sil + doğru dilde yeniden yarat
  (RAP'ta bağımlılarla birlikte yeniden aktivasyon). TR'yi **ilk yaratımda** yakala.

---

## 4. Kaynak push ve aktivasyon

### 4.1 Genel
```
cli adt_push_source '{"name":"ZDEMO_C_SO_ITEM","object_type":"ddls","source":"<tam kaynak>","transport":"<TRANSPORT>"}' --sap-write ...
cli adt_activate    '{"name":"ZDEMO_C_SO_ITEM","object_type":"ddls"}' --sap-write ...
```
- `source` **tam içeriktir**; kısmi diff desteklenmez. Önce `adt_get` ile güncel kaynağı çek (pull-before-edit).
- Push, alt katmanda kilit → yükleme → (class/interface'te aktivasyon öncesi sözdizimi kontrolü) → aktivasyon
  → kilidi bırak → readback dener. Sözdizimi hatalıysa **aktive etmez**, `syntax_precheck:"failed"` +
  `syntax_errors` (satır/kolon) döner. Bu kontrol `prog`/`fugr`/`include` için koşmaz.
  Kontrol **ölçülemezse** (SAP kontrolü koşmadı, kontrol ya da çağrı istisnası) push engellenmez, aktivasyona devam eder;
  yanıt `syntax_precheck:"olculemedi"` + `syntax_precheck_notice` taşır. Bu "sözdizimi temiz" değildir.
  (Aracın açıklaması "aktivasyon ayrı adım" der; alt katman aktive etmeyi dener → sonucu her durumda
  `adt_inactive_objects` ile doğrula, gerekiyorsa `adt_activate` çağır.)
- Doğru sıra: **push → (hata varsa dur, düzelt) → `adt_activate` → readback**. Araya elle
  `adt_syntax_check` turu koyma: gereksizdir ve yan etkilidir (bekleyen temiz sürümü aktive eder).
- **"activated" ≠ içerik canlıya indi (ekip dersi).** Push'un başarılı dönmesi, sözdizimi kontrolü ve incelemenin PASS
  vermesi kaynağın canlıya indiğini kanıtlamaz: bir CDS'teki ABAP tarzı `"` yorumu SAP tarafından sessizce reddedildi, beş
  kontrol yeşildi, canlı hiç değişmedi. Tek kanıt readback içerik eşitliğidir (`readback_verified:true`, ya da `adt_get`
  ile geri okuyup kıyasla). Fark varsa biçim mi içerik mi ayır: SAP bazı tiplerde pretty-print eder; tüm boşluklar
  atıldığında hâlâ farklıysa içerik uyuşmazlığıdır ve push başarısızdır (araçta `readback_verified:false`, `ok:false`).
  Katman yorum sözdizimi: CDS `//` ve `/* */` (`"` değil) · SRVD'de yorum kaydedilirken silinir · ABAP `"` ve `*`
  (`sap-code-review` BE-61).
- **Readback'i ELLE kıyaslıyorsan** (yerel dosya hash'i ↔ `adt_get` çıktısı): ADT'nin döndürdüğü kaynak dosyanın kapanış
  `\n`'ini taşımaz → ham hash farkı "bayat" değil "kıyas tanımı yanlış" olabilir. Önce CRLF→LF, sonra disk metnine
  `rstrip("\n")`, SONRA hash'le (ekip dersi: 7 readback hash'inin 7'si bu kuralla tuttu, ham hash ile 0/7). Tutmuyorsa
  önce kıyas tanımını sorgula, dosyayı değil. Aracın kendi readback kıyası satır sonunu ve baştaki/sondaki boşluğu zaten
  yok sayar; bu kural elle yapılan kıyas içindir.
- Çoklu bağımlı obje (interface CDS + BDEF + behavior class): `adt_activate` `also` ile **tek istekte**:
  `{"name":"ZDEMO_I_X","object_type":"ddls","also":[{"name":"ZDEMO_I_X","object_type":"bdef"}]}`.
- `adt_activate` tek-obje yolunda `activation_verified`: `true` doğrulandı · `false` sahte-OK (obje hâlâ
  inaktif listede, `ok:false`) · `null` kanıtlanmadı.
- Sınıf push'unda tarihsel kural: önce LOCAL TYPES, sonra PUBLIC/PROTECTED/PRIVATE section sırası (bölümlü
  push yapan eski araç içindir; tam kaynak push'unda geçerliliği **DOĞRULANMADI**).
- Aktivasyon sonrası OData kullanan bir servis varsa `$metadata`'yı tazele (`adt_publish_service`, bkz. `foundation-query.md` §5).
- Kaynakta `TEXT-xxx = '...'` yazma → `TEXT-xxx cannot be modified`. Seçim ekranı başlık/yorumu için
  `tit1`, `com01` gibi değişken kullan, `INITIALIZATION`'da ata.

### 4.2 Include + ana program (PROG/I + PROG/P) — ZORUNLU SIRA
**YANLIŞ YÖNTEM:** program ucuna `programType="I"` göndermek. SAP parametreyi sessizce yok sayar, obje
yürütülebilir program olarak yaratılır; aktivasyonda `The REPORT/PROGRAM statement is missing, or the
program type is INCLUDE`.

**TITLE kuralı:** yeni program öncesi kullanıcıdan TITLE iste. Ana programın açıklaması = TITLE; her
include'un açıklaması = TITLE + sonek (`- TOP`, `- SEL`, `- F01`, `- ALV`). TITLE yoksa yaratma.

**DOĞRU SIRA:**
1. TITLE al.
2. Tüm include'ları **include ucu** ile boş yarat (`adt_post_shell object_type="include"`; açıklama TITLE+sonek).
3. Ana programı program ucu ile boş yarat (`object_type="prog"`; açıklama TITLE).
4. Include'lara boş kaynak push et (`*<INCLUDE_ADI>` tek satır yorum yeter).
5. Ana programa boş kaynak push et (`REPORT <prog_adi>.` tek satır).
6. Hepsini **tek aktivasyon** isteğinde aktive et (önce include'lar, sonra ana program): `adt_activate` + `also`.
7. Başarılıysa gerçek kaynakları push et, tekrar aktive et.

Bilinen hatalar:
- `REPORT/PROGRAM statement missing` include aktivasyonunda → include yanlış tipte yaratılmış; sil, include ucu ile yeniden yarat.
- Ana program aktivasyonunda include'ları listeye koymazsan → `Include not found`.
- `contextRef` (include ↔ ana program bağı) **yaratma XML'inde taşınmaz**; ana programdaki `INCLUDE <ad>.`
  satırından doğar ve **aktivasyonda** kurulur. Yaratma gövdesine alan eklemeye çalışma.

Protokol (araç bakımı/teşhis için): include yaratma `POST /sap/bc/adt/programs/includes` (Content-Type
`application/vnd.sap.adt.programs.include.v2+xml`), program `POST /sap/bc/adt/programs/programs`
(`...programs.program.v2+xml`), transport `corrNr` **query parametresi**; aktivasyon
`POST /sap/bc/adt/activation?method=activate&preauditRequested=true`, gövde `adtcore:objectReferences`
(her obje için `uri`, `type` = `PROG/I` / `PROG/P`, `name`); yanıtta `type="E"` hata demektir.

### 4.3 Standart programa bağlı EXIT/CUSTOMER include
Senaryo: include doğru tipte (`PROG/I`) ve standart bir programın user-exit'ine INCLUDE edilmiş
(metadata: `include:contextRef ... type="PROG/P"` standart program). Belirti: include'u aktive etmek
`REPORT/PROGRAM statement is missing` verir. **Bu sil-yeniden-yarat vakası DEĞİL** ve "include doğası,
zararsız" diye geçiştirmek de yanlış (push ≠ aktif). Include tek başına derlenemez.
- Kaynak PUT'u kalıcıdır; "aktif sürüm" = bağlam programının yeniden derlenmesi. Önceki araç setinde çalışan yol:
  aktivasyon referansını **bağlam programına** vermek (`adt_activate name=<STANDART_PROG> object_type=prog`).
- ⛔ **Yasak A gri bölgesi:** standart programın kaynağına yazılmıyor ama standart obje aktive ediliyor.
  Sessiz otomasyon YOK: DUR → açıkla → kullanıcıdan açık onay iste. CLI Z/Y guard'ı bunu reddederse
  guard'ı aşmaya çalışma; kullanıcı bağlam programını SE80/ADT GUI'den aktive edebilir (kanıtlı çözüm).
- Tek-obje yolu (include URI'si, `also` olmadan) bağlam programını çözmez → kullanma.

### 4.3b Z adlı genişletme objesi — standart hedef kapıda reddedilir (Yasak A, Z104)
Genişletme objesinin KENDİ adı Z'lidir (`ZZAVBAK`, `ZE_I_SO`); genişlettiği standart obje kaynağın İÇİNDE yazar. Bu yüzden
ad denetimi yetmez; yazma kapısı (`gate.check_std_extension`, adım 5) ve `adt_push_source` (ikinci katman) kaynağı
`sapadt/std_ext_scan.py` ile tarar. Yazma anahtarı açık + DEV olsa da red:
- `extend type <std> with <append>` (DDIC append) · `extend view [entity] <std> with` · `extend custom|abstract entity <std> with`
  · `annotate view|entity <std> with` (metadata extension) → `ADR_0005_A`, mesajda satır + hedef.
- BDEF `extension …;`: genişletilen BDEF kaynakta YAZMAZ (ADT metadata'sı; `extend behavior for <X>`'teki X alias olabilir —
  SAP örneği `extend behavior for Shop`). Hedef yalnız `extension using interface <I>` ile görünür; yoksa fail-closed red.
- Hedef Z/Y ya da `/Z…/`, `/Y…/` ise serbest (Z objeyi Z extend ile genişletmek). Yorum (`//`, `/* */`) ve `'…'` içindeki metin
  taranmaz; baştaki BOM (U+FEFF) atılır. SAP'nin CDS/BDL'de `--`'yı yorum sayıp saymadığı DOĞRULANMADI ⇒ kaynak **üç
  görünümde** taranır ve bulgular birleştirilir: (a) `--` satırı tüketilir, silinmez (içindeki `/*` blok açmaz) · (b) `--`
  satır yorumu (SAP yorum sayıyorsa gerçek kod) · (c) `--` özel değil, içindeki `/*` blok açar (SAP saymıyorsa gerçek kod).
  Herhangi bir görünüm standart hedef çözerse red; hiçbiri standart çözmez ama biri hedefi çözemezse `?` red; genişletmeyi
  gören tüm görünümler yalnız Z/Y çözdüyse serbest. Tek görünüm yetmedi (ölçülen iki kaçak, 2026-09-24): `--` içindeki `/*`
  blok açınca `-- /*` … `-- */` arasındaki gerçek kod siliniyordu; `--` metni korununca da BDEF başlığı `--` içindeki `;`'da
  bitip `--` içindeki yem Z arayüzünü topluyordu (`extension -- using interface ZI_X ;` + alt satırda standart arayüz → `[]`).
  Güvenlik, iki SAP davranışının (b)/(c) ile doğru modellenmesine dayanır — SAP'nin gerçek davranışı ölçülmedi.
- Bilinen yanlış pozitifler (fail-closed yönü, kod değiştirilmez): ① `--` yorumunda standart hedefli genişletme metni geçerse
  red. ② Alan/alias adı tam olarak `extend` / `annotate` ise hedef çözülemez → `?` red (ölçüldü:
  `{ key extend, extend_flag as Extend }` → 2 bulgu `?`; `note as Annotate` → `?`; `extend_flag` tek başına serbest).
  Çare: alanı/alias'ı yeniden adlandır.
- Kaynak yok / tarayıcı koşamadı → `std_ext_scan_unavailable`. ABAP kaynak tipleri (class, program, FM…) taranmaz.
- Ne yapılır: DUR → kullanıcıya açıkla. Append/extend'i kullanıcı yaratır, sonucu sana bildirir; sen `adt_get` ile okuyup
  doğrularsın. Append/DTEL adı önerme.

### 4.4 Function module (FUNC/FF) — protokol notları
- DENENEN — BAŞARISIZ: genel kaynak-yazma yolu (ETag/retry'lı stateful kilit) FM'de `423 InvalidLockHandle` verdi.
- ÇALIŞAN (önceki araç setinin yardımcı fonksiyonu): **sıkı** kilit → PUT → aktivasyon → kilidi bırak, tek oturum.
  - FM adı URL'de küçük harf; kilit ucu `.../functions/groups/<fg>/fmodules/<fm>` (`source/main` değil).
  - Kilit isteğinde transport **header** `X-sap-adt-corrNr`; PUT'ta `lockHandle` + `corrNr` query parametresi.
  - Aktivasyon tipi `FUNC/FF`.
- İmza **satır-içi ABAP deyimleriyle** yazılır; `*"` yorum-bloğu imza reddedilir
  (`400 Parameter comment blocks are not allowed`).
- `TABLES p TYPE x`'te `x` tablo tipi (TTYP) olmalı: yapı/transparan tablo verilirse normal FM'de tolere
  edilir, RFC işaretlenince `FL 387 Type <X> is not a table type` ile patlar (latent). Yeni tablo tipi = yeni
  DDIC objesi ⇒ ad + metin kullanıcıdan.
- `adt_delete object_type=func` çalışmaz ("lock not supported").
- **aXet CLI yolu (2026-09-13, kod + çevrimdışı test; canlı DOĞRULANMADI):** `adt_post_shell(object_type="func", extra={"function_group":"<Z/Y FUGR>"})`
  kabuğu açar; `adt_get(func)` (grup arama indeksinden çözülür, pull kaydı) → `adt_push_source(func)` yukarıdaki **sıkı kilit** yolunu
  (`set_function_module_source`, CORRNR otoritesi, yabancı transport kapısı) `activate=False` ile çağırır, ardından `activate_object(FM, fm_url)`.
  Canlıdan çözülen fonksiyon grubu Z/Y değilse yazma yapılmaz (`ADR_0005_A`). Genel kaynak-yazma yolu FM'de kullanılmaz.
  FM push'unda 423 alırsan retry etme, K-15 ile birlikte kullanıcıya bildir. `adt_activate(func)` çalışmaz (generic URL yok).
- Klasik ekran/GUI status üretimi: `adt_screen_generate` (Z/Y üreteç FM'i SOAP-RFC ile; `tool-catalog.md`).

### 4.5 CDS (DDLS) yaratma — protokol notları
- Uç: `POST /sap/bc/adt/ddic/ddl/sources` (`/ddlsources` → 404). Content-Type `application/vnd.sap.adt.ddlSource+xml`
  (v2 değil). Kaynak XML içinde `saxutils.escape()` ile kaçışlanmalı.
- Create `201` başarılı; `409`/`AlreadyExists` → obje var, push'a geç.
- Eski script (`create_cds_view.py`) CSRF token expired veriyordu; genel push yolu DDLS'i yalnız obje
  SAP'de **varsa** güncelliyordu → yeni obje için önce create, sonra push.
- Kaynak-içi yaratma (inline source ile POST) çocuk içerikleri boş bırakabilir → create sonrası kaynağı oku.
- **CLI yolu (2026-09-13, çevrimdışı test edildi, canlı DOĞRULANMADI):** `adt_post_shell(object_type="ddls")` yukarıdaki uç +
  Content-Type ile **yalnız metadata** kabuğu açar (kaynak gövdeye konmaz — inline POST boş kaynak tuzağı; toplu yaratıcının kabuk
  gövdesiyle aynı) → `adt_get` (boş kaynak kaydı) → `adt_push_source(ddls)` → `adt_activate` → `adt_get` readback.
  Kaynak `define [root] view entity` / `as projection on` içeriyorsa gömülü inceleme `rap_cds_creation` zincirini koşar
  (RAP read-only consumption BLOCKER + yerel reuse uyarısı); klasik `define view` → `cds_update`.
- SRVD ve BDEF aynı iki adımlıdır (`adt_post_shell` `srvd`/`bdef` → `adt_push_source`); BDEF push'u aktive etmez →
  `adt_activate(<kök ddls>, also=[bdef, behavior class])`. Behavior class'ın CCIMP'i: `adt_push_source(name=<sınıf>, object_type="ccimp")`.

### 4.6 Class push — sıkı kilit akışı (protokol notu; ayrıntı `known-errors-adt.md` K-03/K-01)
1. Oturum stateful, CSRF taze.
2. ETag'i KİLİTTEN ÖNCE al: bekleyen inaktif sürüm varsa (yeni kabuk ya da aktivasyonu düşmüş push) **parametresiz**
   GET; yoksa `?version=active`.
3. `POST .../oo/classes/<c>?_action=LOCK&accessMode=MODIFY&corrNr=<TR>` → `LOCK_HANDLE`.
4. `PUT .../oo/classes/<c>/source/main?lockHandle=<h>&corrNr=<TR>` + `If-Match: <etag>` + `text/plain; charset=utf-8` → 200.
5. `POST ...?_action=UNLOCK&lockHandle=<h>` → sonra aktivasyon (ayrı çağrı).

---

## 5. Kilit (lock / unlock)

- Push sırasında kilit araç tarafından alınır ve bırakılır.
- **Kilit politikası (2026-09-14):** araç kilit TEMİZLEMEZ; yalnız kendi aldığı handle'ı bırakır (başarıda ve hata
  dalında); kilit çakışmasında durur, sahibi ve SM12 tarifini döner (`known-errors-adt.md` K-09).
  1. Çok objeli bir yazma turundan **önce** her obje için `adt_lock_check`. `locked:null` = **ölçülemedi**, "kilitsiz" değil.
  2. Aynı kullanıcı kilidi (kilit adımında `403`; aktivasyonda `EU 510` — K-07): otomatik temizleme ve otomatik yeniden
     deneme yok. Kullanıcı SAP GUI/Eclipse'teki açık düzenlemeyi kapatır, SM12'de kendi kilidini kontrol eder; sonra tek
     sefer tekrar.
  3. Kullanıcıya teşhis ekranı açtırırsan: "aç → yap → **KAPAT** → SM12'ye bak".
  - `adt_push_source` düz yolunda (`push_object`) kilit alanları yanıtın **iç içe `result`** nesnesindedir, üst seviyede
    değil: kilit çakışması `ok:false` + `result.error_type:"SAPLockError"` + `result.error` (sahip adı metinde) +
    `result.source_uploaded:false`; üst seviyede `error:"locked"` ve `lock_owner` **yoktur**, tarif `client_log`'dadır.
    UNLOCK düşerse `result.lock_released:false` — `ok:true` ile yan yana görülebilir (bırakma `finally`'de, `ok`
    hesaplandıktan sonra yazılır); kilit kalmış olabilir → kullanıcıya bildir. Ayrıntı: `known-errors-adt.md` K-09.
- **`409 Conflict` → ASLA retry.** Her retry SAP'de yeni boş bir K-tipi transport yaratabilir. Yapılacaklar:
  1. Kullanıcıya bildir.
  2. Kullanıcı SM12'den kendi eski kilidini temizler (Yasak C: **model enqueue kilidi silmez, silmeyi otomatikleştirmez**).
  3. Kullanıcı SE10'dan objeyi doğru transporta atar.
  4. Sonra **tek** retry.
- Program yaratıldığında SAP otomatik enqueue kilidi koyup handle'ı dışarı vermeyebilir (eski program-yaratma
  yolunda ölçüldü: `create_object`/`push_object` PROG/P için 403/404, ham POST sonrası push `423`) →
  kullanıcı SM12'den kendi kilidini siler, sonra push. Hemen push'a geçme.
- **Kilit sızıntısı:** kilit alan akış süreç ortasında ölürse (401, zaman aşımı, kesilme) `finally` çalışmaz,
  kilit kalır (belirtiler: mesaj sınıfında `EU 510`, sınıf üretiminde `E_ABAP_GENPH`, silinmiş geçici objede
  yetim kilit). Önce **canlı mı bayat mı** ayırt et: başka bir yazıcı şu an çalışıyorsa kilit canlıdır, dokunma.
  Bayatsa **kullanıcı** SM12'den kendi kilidini siler.
- `adt_lock_check`: kilit ucu (`GET /sap/bc/adt/locks`) ölçülen sistemde `404` verdi → `locked:null`
  "kilitli değil" DEĞİLDİR. Kilit teşhisi merdiveni: `known-errors-adt.md` K-04.
- Kullanıcıya bir SAP ekranı açtırırken kapanışı da söyle: "aç → yap → **KAPAT** → SM12'ye bak". Ekran açmak
  düzenleme kilidi yaratır ve sonraki turu bloklar (`EU 510` ölçüldü).

---

## 6. Paket içeriği
```
cli adt_package_contents '{"package":"ZDEMO_PKG"}'
```
- `package_verified:false` → liste paket ucundan değil ad-desenli aramadan geldi; başka paketlerin objeleri
  karışabilir. "Bu paketin içeriği" diye kullanma.
- `objects[].description` doğrulanmaz: büyük bir pakette sunucu yanıtı bir hata düğümü taşıdı ve açıklamalar
  **bir satır kaydı** (120/120 yanlış); hata vermez, makul görünür. Açıklama gerekiyorsa `adt_search_objects`
  ya da `adt_get` metadata'sından oku; obje kimliğini bu alandan çıkarma.

## 7. Transport
- Aktif transport kullanıcıdan gelir. **Yeni transport yaratma/release yasaktır (C);** gerekiyorsa kullanıcıdan numara iste.
- `cli adt_transport_list` → `count:0` kanıt değildir (`shape_recognized:true` olsa bile; 3 ayrı ölçümde
  E070'te açık kayıt vardı). Sıfırı `adt_sql_query` ile `E070` (+ içerik için `E071`) üzerinden çapraz kontrol et:
  `TRSTATUS`, `AS4USER`, `TRFUNCTION`, `STRKORR`. `E070×E071` JOIN + `E07T` tek sorguda 400 → iki sorguya böl;
  `IN ('a','b')` 400 verebilir → `OR` zinciri.
- Obje hangi transportta: `SELECT trkorr, pgmid, object, obj_name FROM e071 WHERE obj_name = '<OBJE>'`.
- **Araca İSTEK (`TRFUNCTION='K'`) numarası verilir, GÖREV (`'S'`) değil (ekip dersi, aynı hata 3 kez).** Objenin hangi
  göreve düşeceği SAP'nin işidir; sen kabı söylersin. Görev verirsen kilit `409` + CORRNR uyuşmazlığı doğar; push aracı
  aynı kullanıcıda SAP'nin atadığı isteğe geçip `[WARN] İSTENEN TRANSPORT KABUL EDİLMEDİ` basar — bu bir kurtarmadır,
  girdinin doğru olduğunun kanıtı değildir. Emin değilsen tek sorgu:
  `SELECT trkorr, trfunction, strkorr FROM e070 WHERE trkorr = '<N>'` → `S` ise `STRKORR`'daki isteği kullan.
- Numaranın otorite sırası: paketin `.rules.md` transport kaydı → canlı `E070` ölçümü → (ikisi de yoksa) devir notu /
  oturum notu. Notlar çalışma anının numarasını yazar (çoğu zaman görevi); araca verilecek olan istektir.
  ⛔ `409` görünce yeni istek/görev AÇMA (Yasak C) — numarayı düzelt ya da kullanıcıya sor.

## 8. Obje arama
```
cli adt_search_objects '{"query":"ZDEMO*","object_type":"CLAS","max_results":50}'
```
- Joker serbest. Tip filtresi ADT tip kodlarıyla (`CLAS`, `INTF`, `DOMA`, `DTEL`, `TABL`, `DDLS`, `PROG`).
- `count == max_results` ise liste kırpılmış olabilir → daralt ya da limiti büyüt (uç tavanı 550; sonuçlar alfabetik).
- Yanıtta `truncated` alanı yok; kırpma uyarısı yalnız `client_log`'da. Tip verildiğinde filtre sunucuda uygulanır. `count:0` "yok" kanıtı değildir
  → `adt_get` ile adı doğrudan oku (`tool-catalog.md` → `adt_search_objects` bilinen sınır).

## 9. Toplu işler
**ÇALIŞAN YÖNTEM (çevrimdışı test edildi; canlı SAP DOĞRULANMADI):** `scripts/sap_adt_populate.py` — CSV / `.cds` klasöründen
satır satır yaratır. Ayrı yazma yolu **değildir**: her satırın her adımı CLI'nin kapı + reviewer + araç hattından
(`sap_adt_cli.calistir`) geçer.
```
python <foundation>/scripts/sap_adt_populate.py domain --csv domains.csv --package <PAKET> --transport <K-İSTEK> \
    --sap-write --scope <KAPSAM> --reason "<en az 15 karakter gerekçe>" --dry-run      # önce plan + kapı ön geçişi
python <foundation>/scripts/sap_adt_populate.py dtel --csv dataelements.csv  ...          # aynı bayraklar
python <foundation>/scripts/sap_adt_populate.py cds  --source-dir cds/ ...                # <AD>.cds, dosya adı = tanım adı
python <foundation>/scripts/sap_adt_populate.py enqu --csv lockobjects.csv ...
python <foundation>/scripts/sap_adt_populate.py msag --name <ZMSG> --description "<metin>" --csv messages.csv ...
```
| Tür | CSV kolonları | Satır akışı |
|---|---|---|
| `domain` | `name,datatype,length,decimals,description,fixed_values` (`A=Açık;K=Kapalı`) | `adt_get` → yoksa `adt_domain_create` (reviewer `domain_creation_csv`) |
| `dtel` | `name,type_kind,type_name,description,short,medium,long,heading` (4 etiket DOLU; `type_kind=domain`) | `adt_get` → yoksa `adt_dtel_create` (reviewer `dtel_creation`; tip domain'den okunur) |
| `cds` | — (`@EndUserText.label` zorunlu) | `adt_get` → yoksa `adt_post_shell(ddls)` → `adt_get` (çekme kaydı) → `adt_push_source` → `adt_activate` |
| `enqu` | `name,description,primary_table,lock_mode,allow_rfc,field_names` (`MANDT;ALAN`) | `adt_get(enqu)` → yoksa `adt_post_shell(enqu)` → `adt_activate`; varsa atlanır |
| `msag` | `msgno,msgtext[,selfexplainatory]` (msgno 3 hane, metin ≤ 73) | `adt_msgclass_read` → yoksa kabuk → `adt_msgclass_write` (mevcut metni değiştirmek `--allow-overwrite` ister) |

- **Ön geçiş:** SAP'ye ilk çağrıdan önce TÜM satırların TÜM planlı adımları kapıdan geçer; tek red → hiçbir şey yazılmaz, çıkış 2, red
  denetim logunda. `--dry-run` yalnız girdi doğrulaması + ön geçiş (SAP çağrısı yok).
  ⚠ **Ön geçiş yalnız kapı (`check_write`) denetimidir.** Araç içi ön kontrol (ör. domain `preflight_blocker`) ve reviewer satır
  YÜRÜTÜLÜRKEN koşar; bu yüzden bir satır orada düştüğünde **önceki satırlar yazılmış olabilir**. `--dry-run` bu ikisini kapsamaz.
- **CSV:** UTF-8 olmalı (BOM'lu ya da BOM'suz; CRLF serbest). UTF-8 dışı (Excel ANSI/cp1254, UTF-16) ya da ayrıştırılamayan dosya →
  `csv_unreadable`, çıkış 3. Eksik, tanınmayan ya da **yinelenen** başlık → `csv_invalid`, çıkış 3. İkisinde de çağrı yapılmaz.
- **Varlık:** sonda ÖLÇÜLEMEZSE satır HATA (asla "yok" sayılmaz). Varsa satır `atlandi` + tek-ad `--force-recreate` önerisi.
- **Koşumu durduran yazma hataları** (kalanlar `islenmedi`, çıkış 1 `run_stopped`):
  - *Sonuç bilinmiyor* — `unexpected` (araç istisnası), `connection_failed`, `unreachable`, `sap_error` HTTP 502/503/504,
    `push_failed` içinde bağlantı ya da SAP dışı istisna; composite araçlarda `steps.*` içindeki aynı kodlar da. Satır mesajı:
    "sonuç BİLİNMİYOR, SAP'de durumu kontrol et".
  - *Hesap kilidi riski* — `auth_failed`, `sap_error` HTTP 401. Kalan satırlar aynı kimlikle denenmez.
  - Nerede, hangi kodla ve hangi gerekçeyle durduğu `result.stop` alanındadır (`name`, `row`, `step`, `tool`, `code`, `class`).
  - Bilinen red koşumu durdurmaz (4xx, `reviewer_blocker`, `preflight_blocker`, kapı reddi, kilit çakışması): satır HATA, koşum sürer.
    `activation_failed` mesajı objenin SAP'de inaktif olarak var olabileceğini söyler; msag `readback_failed` mesajı "PUT kabul edildi,
    geri okuma doğrulanamadı; SAP'de kontrol et" der.
- **`--force-recreate`:** yalnız `domain`/`dtel`/`cds` ve yalnız `--only <TEK AD>` ile; DELETE de kapıdan geçer ve `delete_verified` okunur:
  doğrulanamazsa koşum DURUR (kalanlar `islenmedi`). Silme doğrulandıktan sonra yeniden yaratmanın bir adımı düşerse satır mesajı
  `obje SİLİNDİ (delete_verified); yeniden yaratma başarısız:` ile başlar. Tüketicisi olan objede kullanma — içerik değişikliği için `adt_push_source`.
- **Çıkış:** 0 hepsi yazıldı/atlandı · 1 en az bir HATA ya da `islenmedi` (kısmi başarı 0 DEĞİLDİR) · 2 ön geçiş reddi · 3 kullanım/CSV hatası ·
  4 `--fail-on-skip` verildi ve satır atlandı.
- **Yapmaz:** paket/transport yaratmaz, tablo kabuğu yaratmaz, etiket/açıklama üretmez, enqueue kilidi silmez/temizlemez (kilit çakışması →
  satır HATA + SM12 tarifi, koşum devam). Geçici reviewer CSV'leri sistem TMP'sinde açılır ve koşum sonunda silinir (`temp_dir_removed`).

## 10. Çoklu sistem ve tier
**Konvansiyon:** proje kökünde tek aktif dosya `.conn_adt`; birden çok sistem varsa her biri `conn/<SISTEM_ADI>.env` slotunda (aynı anahtarlar,
`ADT_SAP_SYSTEM_NAME` = slot adı). Proje şablonunun `.gitignore`'u `.conn*` ve `conn/*`'ı dışarıda tutar (yalnız `*.example` / `conn/README.md` girer).

| Adım | Kim · nasıl | Sonuç |
|---|---|---|
| Slot oluştur (şablonla) | geliştirici: proje klasöründeki `KURULUMU-TAMAMLA.cmd` (→ `<TEMPLATE>/proje-tamamla.cmd` → `scripts/conn_sablon.py hazirla/dogrula`); `conn/DEV.env` + `conn/QA.env` şablonunu kullanıcı doldurur (pencere tam yolu + alanları söyler, editör açmaz) | denetim alan adı + kural basar, değer basmaz; parola dahil `<...>` yer tutucu reddedilir |
| Slot oluştur | geliştirici, kendi terminalinde: `python <foundation>/scripts/setup_credentials.py --slot <SISTEM_ADI> --project-dir <proje>` | `conn/<SISTEM_ADI>.env` (değer basılmaz) |
| Slotları gör | `python <foundation>/scripts/switch_tier.py --list --project-dir <proje>` | JSON: yalnız ad + tier + aktif sistem |
| Sistemi seç (aXet) | `%sistem` skill'i: `conn_sablon.py ozet --json` (ad + tier + durum) → seçim → `switch_tier.py <AD>` | canlı ölçüldü 2026-09-23 (sahte slotlar): QA'ya geçiş ve DEV'e dönüş `.conn_adt`'yi değiştirdi, sandbox engellemedi |
| Sistemi seç | `python <foundation>/scripts/switch_tier.py <SISTEM_ADI \| DEV \| QA \| PRD> --project-dir <proje>` | slot → `.conn_adt`; eski dosya `conn/.conn_adt.bak` |
| Doğrula | `cli sap_doctor` | bağlantı + tier + dil |

- **Tier fail-closed kalır:** tier satırı yok, iki farklı değer ya da önekli anahtar (`ADT_SAP_TIER_OLD=`) → `UNKNOWN` → yazma `tier_not_writable`.
  `switch_tier` QA/PRD/UNKNOWN geçişini yapar ama JSON `warnings`'e yazar; yazma kapısı reddeder.
- Tier kısaltmasıyla seçimde o tier'da birden çok sistem varsa `ambiguous_tier` (çıkış 2) → sistem adıyla seç. Bilinmeyen ad `system_not_found` (2).
- Slotta doldurulmamış `<...>` değer (parola hariç) → geçiş yapılmaz, `placeholder_values` (1).
- `conn/` aXet ajanına kapalıdır (proje `.axetcode-denylist` satırı `conn`; ÖLÇÜLDÜ 2026-09-23: satır yokken ajan `conn/QA.env`'i okuyabildi). Betikler (`switch_tier.py`, `conn_sablon.py`) çalışmaya devam eder.
- Çıkış: 0 geçildi/listelendi · 1 yer tutucu/dosya hatası · 2 çözülemedi/belirsiz · 3 kullanım. Çıktı dosya içeriğini, URL'yi, kullanıcıyı basmaz.
- aXet CLI her çağrıda yeni süreçtir → geçişten sonra yeniden başlatma adımı yok; sonraki çağrı yeni `.conn_adt`'yi okur.
- Ortamda `ADT_SAP_URL`/`ADT_SAP_CLIENT` varsa `.conn_adt`'yi ezer → yazma `conn_env_mismatch`, `sap_doctor` `env_override` FAIL.
- `setup_credentials.py` Windows'ta gerçek konsol ister (PowerShell/cmd); Git Bash/mintty borusu konsol değildir → `winpty python …` ya da PowerShell.
- Git Bash (MSYS), `.exe`'ye komut satırı argümanı olarak verilen ve `/` ile başlayan değeri Windows yoluna çevirir:
  `/sap/bc/adt/...` betiğe `C:/Program Files/Git/sap/bc/adt/...` olarak ulaşır ve `InvalidURL` / "obje yok" gibi okunur
  (ekip dersi; SAP'ye istek gitmez). Git Bash'te ADT URI'sini argüman veren komutun başına `MSYS_NO_PATHCONV=1` koy ya da
  URI'yi betiğin içinde sabit ver. aXet'in kendi `bash` aracı Go tabanlıdır (çekirdek §4 "Kabuk ortamı"); orada bu
  dönüşüm ÖLÇÜLMEDİ.

---

## Bu dosyada ÇIKARILAN / DEĞİŞTİRİLEN (kaynağa göre)
- Yerel script komutları (`run_check_logon.py`, `download_object.py`, `push_object.py`, `activate_object.py`,
  `run_sql_query.py`, `list_package_contents.py`, `list_transports.py`, `search_objects.py`, `where_used.py`,
  `run_atc_check.py`) → CLI araç çağrılarına çevrildi.
- Tam Python REST şablonları (session/CSRF/XML kodu) çıkarıldı; endpoint/header/sıra bilgisi protokol notu olarak kaldı
  (aXet'te ham REST yazma yolu yok).
- Kişisel/sistem izleri (kullanıcı adı, host, client, gerçek obje/paket adları, düz metin şifre) nötr yer tutuculara çevrildi.
- `--cwd` backslash tuzağı, `TempScripts` klasörü, MCP/gateway/ajan-takımı dili, SE80 dışı iç araç adları çıkarıldı.
- 2026-09-25 eşitleme (ekip dersleri): §2 "repo ileri" çapası, §4.1 readback içerik eşitliği + elle hash kıyası, §7 istek/görev
  ayrımı eklendi; kaynaktaki obje/sistem adları, gate adları ve ajan-brif dili alınmadı.
