---
name: sap-adt-foundation
description: >
  Use when working with SAP ABAP objects through ADT: reading or downloading source
  and metadata, pushing (uploading) source, activating, deleting, creating Z objects
  (shell, domain, data element, structure), where-used or blast-radius analysis,
  transport or lock questions, package contents, table read or SQL query on SAP,
  ATC or syntax check, inactive-object worklist, ABAP Unit, classrun, OData service
  publish. Triggers: "SAP'den çek", "kaynağı indir", "SAP'ye push et", "aktive et",
  "where-used", "nerede kullanılıyor (SAP)", "transport", "kilit", "SE11 tablosunu oku",
  "SQL at", "ATC", "paket içeriği", "inaktif obje". Do not use for triaging a NEW
  development request (use sap-intake-triage first) or for non-SAP code.
---

# SAP ADT temel işlemleri (CLI ile)

> Kesin yasaklar (A standart obje · B standart tablo verisi · C transport/paket/kilit · D Z obje dili ve
> etiketleri) SAP çekirdeğinde (`core/sap/00-sap.md`) yazılıdır ve her oturum yüklüdür. Burada
> tekrarlanmaz; her adımda geçerlidir.

## When to use this skill
- SAP'deki bir objeyi okumak, indirmek, değiştirmek, aktive etmek, silmek, aramak.
- Bir değişikliğin etki alanını (where-used / blast-radius) ölçmek.
- Transport, kilit, paket, aktive-bekleyen obje, SQL/tablo okuma, ATC, ABAP Unit.
- **Kullanma:** yeni bir geliştirme/revizyon talebinin ilk ele alınışı → önce `%sap-intake-triage`.

## Araç: tek CLI
Tüm SAP işlemleri tek script ile yapılır (`<TEMPLATE>` = bu template reposunun klonu):

```
python <TEMPLATE>/skills-sap/sap-adt-foundation/scripts/sap_adt_cli.py --list
python <TEMPLATE>/skills-sap/sap-adt-foundation/scripts/sap_adt_cli.py <tool> --args-json '{...}' [--project-dir <dir>]
# yazma sınıfı araçlarda ek olarak:
#   --sap-write --scope S0|S1|S2  (--reason "<gerekçe>" S0/S1 · --intake .axet-code/intake/<id>.md S2)
```

- **`--list` çıktısı otoritedir.** Araç adı, sınıfı ve argümanları için önce `--list`'e bak;
  bu dosya ya da `references/tool-catalog.md` ile çelişirse `--list` kazanır.
- Çıktı stdout'a tek JSON: `{"ok","tool","class","result","error":{"code","message"},"gate":{...}}`.
- Çıkış kodu: `0` başarı · `2` guard/kapı reddi (SAP'ye gidilmedi) · `1` araç/bağlantı hatası · `3` kullanım hatası.
- Kaynak kodu gibi uzun ya da tırnaklı argümanlarda `--args-json` yerine `--args-file <json dosyası>` kullan
  (PowerShell gömülü çift tırnak dersi: ekip hafızası "PowerShell BOM ve tırnak"). Geçici JSON dosyası `.tmp/`'ye.
- Araç kataloğu (37 giriş, argümanlar, uyarılar): `references/tool-catalog.md`.
- Yazma sınıfı yanıtlarında engellemeyen `checklist_hint` (bu iş türünün kontrol listesi) ve hatada `known_errors_hint` (bilinen hata maddesi)
  gelebilir → önce onları oku; karar ve çıkış kodu değişmez.

## Proje kökünde neler var
| Dosya | Ne | Kural |
|---|---|---|
| `.conn_adt` | SAP bağlantı + sistem tipi (tier) | gitignore'lu. **`view` ile OKUMA**, içeriğini sohbete yazma; CLI okur. Yoksa geliştirici kendi terminalinde `scripts/setup_credentials.py` çalıştırır (sen çalıştırmazsın) |
| `conn/<SISTEM_ADI>.env` | çoklu sistem slotları | gitignore'lu; `scripts/switch_tier.py <AD>` seçileni `.conn_adt` yapar (`references/foundation-ops.md` §10) |
| `sap-project.json` | `sap_profile`, `release`, `master_language`, `cleancore_policy` | yoksa CLI yalnız `ping` ve `sap_doctor` açar → kullanıcıdan doldurmasını iste |
| `.axet-code/intake/<id>.md` | S2 intake artefaktları | `%sap-intake-triage` üretir |
| `.axet-code/sap-write-log.jsonl` | her yazma denemesinin kaydı | inceleme için okunabilir, elle düzenlenmez |

## How to use this skill

### 1. Bağlam
1. `sap-project.json`'u oku: profil, `master_language`. Yoksa DUR, kullanıcıya bildir.
2. `sap_doctor` → bağlantı katmanları (proje dosyası, anahtarlar, tier, dil, canlı kimlik + CSRF); FAIL satırını kullanıcıya
   aktar, `not_checked` listesini "doğrulandı" sayma. Ardından hedef objeye bir okuma çağrısı (`adt_get include_source=false`)
   → obje erişimi ve yetki gerçekten çalışıyor mu.
3. Paket ve transport **kullanıcıdan** gelir. Transport numarası uydurulmaz; `adt_transport_list`
   `count:0` dönerse bu "transport yok" kanıtı DEĞİLDİR (`references/tool-catalog.md` → `adt_transport_list`).
   "Yeni transport açayım" refleksi yasak C'dir.

### 2. Önce oku — pull-before-edit
- SAP'deki bir kaynağı değiştirmeden ÖNCE, analize başlamadan, güncel hâlini `adt_get` ile çek.
  Yereldeki kopya (repo, önceki oturum, hafıza) **bayat olabilir**; hafıza hipotezdir, sistem otoritedir.
- CLI bunu zorlar (iyimser eşzamanlılık): `adt_get` kaynağı okuyunca canlı kaynağın özetini
  `.axet-code/sap-pull-state.json`'a yazar (`pull_state: kaydedildi`). `adt_push_source` yazmadan hemen önce
  canlı kaynağı yeniden okur ve bu özetle kıyaslar; başarılı push'tan sonra kaydı yeni canlı özetle günceller.
  Kıyaslanan yerel dosya DEĞİL, çekme anındaki canlı ↔ yazma anındaki canlıdır.
  | Kod | Anlamı → ne yapılır |
  |---|---|
  | `pull_before_edit_missing` (çıkış 2) | bu obje için çekme kaydı yok → `adt_get` ile çek, düzenlemeyi o kaynağa uygula, sonra push |
  | `source_changed_since_pull` (çıkış 2) | çektikten sonra SAP'de biri değiştirmiş → üzerine YAZMA; yeniden çek, değişikliği yeni kaynağa uygula, kullanıcıya bildir |
  | `pull_live_read_failed` (çıkış 1) | yazma öncesi canlı okuma başarısız → bağlantıyı düzelt; kontrolsüz yazma yok |
  | `pull_state_unreadable` (çıkış 2) | durum dosyası bozuk → `adt_get` ile yeniden çek (dosya yeniden yazılır); dosyayı elle düzenleme |
- Düzenlemeyi DAİMA `adt_get` çıktısının üzerine yap; eski yerel kopyayı (repo, önceki oturum) taban alma. Kıyas "SAP
  değişmedi"yi kanıtlar, yerel kopyanın çekilen kaynaktan türediğini kanıtlamaz: bayat kopya canlıdaki satırları sessizce geri alır.
  Bu yüzden push, zaten okuduğu canlı kaynakla yeni kaynağı yazmadan önce kıyaslar; canlıda olup yeni kaynakta olmayan satır varsa
  yanıta `removed_lines_warning: {removed, added, sample}` + `warning` konur. Yazma DURMAZ. Bu alanı görünce silinen satırları
  kullanıcıya göster; kasıtlı değilse `adt_get` ile yeniden çekip düzenlemeyi onun üzerine uygula, kullanıcı onayı olmadan tekrar yazma.
- `adt_post_shell` bu kontrole girmez; ama yeni kabuğa ilk `adt_push_source`'tan önce de `adt_get` çalıştır.
- Mesaj sınıfında aynı kural mesaj listesine uygulanır: `adt_msgclass_read` kaydeder, `adt_msgclass_write` yazma anındaki canlı listeyi kıyaslar
  (aynı dört kod).
- İndirilen kaynağı paket adıyla eşleşen klasöre, obje tipine göre alt klasöre koy
  (`classes/`, `cds/`, `functions/`, `programs/` …).
- Aktif mi inaktif mi önemliyse ayrımı bil: ADT varsayılanı **inaktif sürümdür**; `adtcore:version="active"`
  metadata'sı boş kabuk için de "active" der. Aktivasyon kanıtı = `adt_inactive_objects` + aktif kaynağın
  içerik kıyası (`references/known-errors-adt.md` → K-10).

### 3. Etki alanı (where-used)
- Değişen obje başka nerede kullanılıyor: `adt_where_used`, çok katmanlı yığında `adt_impact_analysis`,
  metin araması için `adt_grep_source`.
- **`0` sonuç "kullanılmıyor" değildir.** Aracın kapsamını oku (`coverage_complete`, `skipped_objects`,
  `existence_verified`); FM çağıranı için kanonik ölçüm `CROSS` tablosudur + pozitif kontrol
  (`references/foundation-query.md` §3).
- Paylaşılan bir objeyi bozacaksan DUR ve sor (çekirdek §4).

### 4. Yazma ön koşulları ve kapsam beyanı
Yazma sınıfı bir araç (katalogda `class: write`) ancak **hepsi** sağlanınca SAP'ye gider:
1. Kullanıcı kendi terminalinde `install.py --sap-write` çalıştırmıştır. **Bunu sen çalıştırmazsın**;
   gerekiyorsa ne işe yaradığını ve nasıl çalıştırılacağını kullanıcıya açıklarsın.
2. `.conn_adt`'de sistem tipi DEV'dir (tier okunamıyorsa yazma yok; CLI fail-closed).
3. Komutta `--sap-write` vardır.
4. **Kapsam beyanı** vardır: S0/S1 → `--scope S0|S1 --reason "<tek satır gerekçe>"`;
   S2 → `--scope S2 --intake .axet-code/intake/<id>.md` (artefakt dolu + kullanıcı mutabakatı işaretli).
   Beyanı işi küçük göstermek için düşürmek yasaktır; iş büyüdüyse yeniden sınıfla (`%sap-intake-triage`).
5. Yazma "geri alınamaz/paylaşılan sistemde yazma" sınıfındadır → çekirdek §3 onayı: ne yapılacak,
   hangi obje/transport, ne yapılmayacak.

Guard'lar (Z/Y öneki, transport, `master_language` metin, 4 etiket, standart obje silme, KVKK) SAP'ye
ağ çağrısından **önce** çalışır. CLI'nin yazma kapısı sırası ve red kodları (çıkış 2; ilk red döner):

| Kod | Anlamı → ne yapılır |
|---|---|
| `sap_project_missing` / `sap_project_invalid` | `sap-project.json` yok/bozuk → kullanıcı doldurur |
| `write_not_optin_global` | kullanıcı `install.py --sap-write` çalıştırmamış → kullanıcıya açıkla |
| `write_flag_missing` | `--sap-write` yok |
| `tier_not_writable` · `conn_env_mismatch` | bağlantı DEV değil / ortam değişkeni `.conn_adt`'yi eziyor → kullanıcı düzeltir |
| `scope_missing` · `scope_invalid` · `reason_missing` | kapsam beyanı eksik; gerekçe tek satır ve en az 15 karakter |
| `intake_missing` · `intake_invalid` | S2 artefaktı yok/yanlış yerde/eksik/işaretsiz → `%sap-intake-triage` |
| `ADR_0005_A` · `ADR_0005_C` | Z/Y dışı ad (`name` yanında `adt_screen_generate` `fm_name`/`program`, `adt_post_shell(func)` `extra.function_group`; eksikse de red) ya da standart obje silme · paket tipi ya da transport eksik (`adt_screen_generate`'de mode WRITE/DELETE; `deploy_ui.py deploy`'da — çıkış 3 — `ui5-deploy.yaml` `app.package` boş/yer tutucu ya da paket `$TMP` değilken `app.transport` boş ya da yer tutucu) |
| `ADR_0005_A` (genişletme) · `std_ext_scan_unavailable` | Z adlı objenin kaynağı standart objeyi genişletiyor: `extend type <std>` (append), `extend view [entity] <std>`, `extend custom\|abstract entity <std>`, `annotate view\|entity <std>`, BDEF `extension` (genişletilen BDEF kaynakta yazmaz → `using interface <Z…>` yoksa red). Yazma anahtarı açık + DEV olsa da red. Standart objeler yalnız okunur → DUR, append/extend'i kullanıcı yaratır, sonucu sana bildirir, sen okuyup doğrularsın; ad önerme. Kaynak taranamadıysa yazma yok |
| `ADR_0005_B` · `std_dml_scan_unavailable` | kaynakta standart tabloya doğrudan INSERT/UPDATE/DELETE/MODIFY (mesaj satır no + hedef tabloyu gösterir) → BAPI → RFC FM → BDC → kullanıcıdan manuel; kaynak taranamadıysa yazma yok. Bilinen sınır: `/Z…/`, `/Y…/` dışındaki müşteri namespace'i de yasaklı sayılır — kendi namespace'i olan proje yapılandırma değişikliği ister, bugün desteklenmiyor |
| `language_mismatch` | bağlantı dili ≠ `master_language` → kullanıcı `.conn_adt`'yi düzeltir (dil sessizce eşitlenmez) |
| `reviewer_bypass_forbidden` | `skip_reviewer` ya da `ack_drop` verildi → aXet'te kabul edilmez, argümanı kaldır |
| `write_log_unavailable` | yazma logu yazılamıyor → iz bırakmadan yazma yok |
| `write_target_mismatch` | (yalnız `deploy_ui.py deploy`, çıkış 3) `ui5-deploy.yaml` target.url/client ≠ `.conn_adt` → tier başka sistemi doğrulamış olurdu; kullanıcı hedefi eşitler |
| `gate_unavailable` | (yalnız `deploy_ui.py deploy`, çıkış 3) kapı modülü yüklenemedi → fail-closed, deploy ve build koşmaz; log yazıcısı da kapıdadır ⇒ write-log'a DÜŞMEZ, yalnız ekrana basılır; kurulum bozuk, kullanıcıya bildir |
| `reviewer_blocker` | gömülü inceleme BLOCKER → kaynağı düzelt |
| `preflight_blocker` | `adt_domain_create` argüman ön kontrolü BLOCKER (formülsüz datatype, geçersiz length/decimals/lowercase, boş sabit değer metni) → `result.steps.pre_flight.findings` |
| `msgclass_overwrite_not_allowed` | `adt_msgclass_write` mevcut mesajı değiştirirdi → `plan.overwritten`'i (önce/sonra) kullanıcıya göster; açık onay gelirse `allow_overwrite=true` |
| `repeated_failure` | patinaj kesicisi: aynı obje aynı hata koduyla art arda 3 kez başarısız oldu, bu yazma denenmedi → DUR; aynı çağrıyı tekrarlama, ham hata + denenenlerle kök sebebi kullanıcıyla konuş. Seri başarılı yazma, farklı hata kodu ya da 2 saat sonra sıfırlanır; erken sıfırlama kararı kullanıcının (`.axet-code/sap-write-failures.json`) — dosyayı sen silme |
| `tool_not_available_for_profile` · `type_not_available_for_profile` | araç ya da obje tipi bu `sap_profile`'da kapalı (ör. `adt_screen_generate`, `adt_set_description`, `fugr`/`func`; tablo: `references/profiles.md`) → başka yol yok, kullanıcıya bildir |

Kullanım/araç kodları (çıkış 3, SAP'ye gidilmedi): `invalid_argument` (argüman biçimi — ör. dynpro 4 hane değil, `extra` bu tipte geçersiz) ·
`unsupported_type` (tip bu araçta desteklenmiyor; mesaj yolu söyler). Çıkış 1 (SAP'ye gidildi ya da sonuç ölçülemedi): `create_not_persisted`
(2xx ama obje yok) · `push_failed` · `screen_gen_rc` · `nav_remap_off` · `soap_fault` · `ev_rc_missing` · `master_language_unresolved` ·
`lock_conflict` / `lock_failed` (mesaj sınıfı ya da açıklama kilidi alınamadı — **kilidi silmeye çalışma**; kullanıcı SM12'de kendi kilidini kontrol eder, açık
SE91/ADT ekranını kapatır) · `readback_mismatch` / `readback_failed` (yazma doğrulanmadı → ilgili okuma aracıyla yeniden oku, kullanıcıya bildir) ·
`msgclass_live_incomplete` (canlıda paket/açıklama yok; tahmin etme) · `transport_mismatch` (obje başka transportta; PUT yapılmadı) ·
`activation_required` / `activation_failed` / `activation_not_verified` / `activation_state_unknown` (açıklama yazıldı ama obje inaktif ya da ölçülemedi —
kullanıcıyla `adt_inactive_objects` → `adt_activate`) · `doctor_fail` (`sap_doctor` FAIL satırı var).

**Guard reddini (çıkış kodu 2) aşmak için komutu değiştirme, argümanı
eğip bükme, başka yol (ham REST script'i, başka araç) arama.** DUR, reddin `error.code` + `message`'ını
kullanıcıya aktar, ne gerektiğini söyle.

### 5. Yaz
- **Zorunlu ön adım (kilit):** çok objeli yazma turundan önce her obje için `adt_lock_check` (`locked:null` = ölçülemedi, kilitsiz değil); kilit çakışmasında kilidi silmeye/tekrar denemeye çalışma, kullanıcı açık düzenlemeyi kapatır ve SM12'ye bakar (`references/known-errors-adt.md` K-09).
- Tek obje, atomik adımlar: `adt_post_shell` → `adt_get` → `adt_push_source` → `adt_activate`; DDIC için composite
  araçlar (`adt_domain_create`, `adt_dtel_create`, `adt_struct_create` — struct uyarısına bak).
  `adt_post_shell` kabuk tipleri: class/interface/program/include + `ddls`, `srvd`, `bdef`, `fugr`, `func`, `msag`, `enqu`, `ttyp`.
  Mesaj sınıfı mesajları: `adt_msgclass_read` → `adt_msgclass_write` (birleştirir; mevcut mesajı değiştirme/silme yalnız açık argümanla, `s4_private`).
  `adt_push_source` ek tipleri: `bdef` (aktive etmez), `ccimp`/`ccau` (`name` = ana sınıf), `func`. Klasik ekran: `adt_screen_generate`.
  Kısa açıklama değişikliği: `adt_set_description` (class/bdef/srvd/ddls/ddlx/dcl, `s4_private`; obje inaktife düşer → dönüşteki `state`'e bak).
  2026-09-21 (yalnız `s4_private`; canlı DEV 2026-09-21: tablo yaratma `ok` — aktif, readback 3/3 · tablo tipi yapı satırlı onarım yolu `ok` ·
  metin havuzu yazma `ok`; ilkel satırlı ttyp onarımı ve metin havuzu `activation_final` henüz ÖLÇÜLMEDİ): Z tablo `adt_table_create` · tablo tipi `adt_ttyp_create` · metin havuzu `adt_textpool_write` ·
  `adt_push_source` `ccdef`/`ccmac` (yazma yolu canlı ölçüldü 2026-09-21 → yanıtta `write_path_measured:true`). Ayrıntı: `references/tool-catalog.md`.
  Program açıklaması ADT ile değişmez → kullanıcı SE38'de değiştirir.
  CSV / `.cds` klasöründen çok obje (domain, dtel, cds, enqu, msag): `scripts/sap_adt_populate.py` — aynı kapı + reviewer hattından geçer,
  önce `--dry-run`; tablo türü yok (`references/foundation-ops.md` §9).
  Ayrıntı + desteklenmeyenler: `references/tool-catalog.md`.
- Z obje yaratmada: başlık/açıklama ve 4 etiket `master_language`'de, TAM ve **spesifikasyondan**;
  tahmin edilmez. Yeni program/obje adı ve TITLE kullanıcıdan gelir.
- `adt_post_shell` `ok:false` dönerse **retry etmeden önce** `exists_after`'a bak: obje yaratılmış olabilir.
- `409` → ASLA retry yok (her retry boş transport yaratabilir). Kilit/transport hatası → `references/known-errors-adt.md`.

### 6. Sistemden tekrar okuyarak doğrula
- "uploaded / activated / HTTP 200" iddiadır. Doğrulama:
  1. `adt_get` ile kaynağı/metadata'yı geri oku, gönderdiğinle kıyasla (yazma persist oldu mu).
  2. Yeni Z objede `master_language` ve açıklamanın sistemde doğru durduğunu metadata'dan oku.
  3. Dönüşteki `readback_verified` / `activation_verified` alanları `null` ise "doğrulandı" DEĞİLDİR.

### 7. Aktivasyon durumunu doğrula
- `adt_inactive_objects` → bu işin bıraktığı inaktif obje var mı (bağımlı objeler dahil: ör. kök CDS'e alan
  eklenince ona bağlı behavior definition sessizce inaktif kalabilir).
- İş bitti demeden önce taban-sonra ölçümü: işlemden önceki ve sonraki sayı (inaktif sayısı, alan sayısı…).
- Rapor: yapılan · doğrulama komutu + sonucu · yapılmayan · açık sorular (çekirdek §4, `%verify-done`).

### Hata olursa
1. Hata gövdesini/`message`'ı oku — ADT 400'lerinde sebep gövdededir.
2. Yanıtta `known_errors_hint` varsa gösterdiği maddeyi oku; yoksa `references/known-errors-adt.md`'de ara (kod ve belirti bazlı indeks).
3. Tanıdık semptomda önce proje hafızası + ekip hafızası + bu referanslar; sonra deney.
4. "Araç bozuk" demek için kontrol grubu kur (çalıştığı bilinen bir obje). Aynı girdiyle tekrar deneme kanıt değildir.
5. Pahalı bir çare ilk denemede tutmadıysa ikinci kez uygulama; dayandığı teşhisi sorgula.

## Referanslar
| Dosya | İçerik |
|---|---|
| `references/tool-catalog.md` | 37 araç: sınıf, amaç, argüman, uyarı |
| `references/profiles.md` | SAP profil yetenek matrisi (rehber, canlı test gerekir) + CLI profil etiketleri |
| `references/foundation-ops.md` | Okuma/indirme, yaratma, push, aktivasyon, include+program akışı, FM/CDS/class protokol notları, kilit, transport, paket, arama |
| `references/foundation-query.md` | SQL ve tablo okuma, where-used/blast-radius (`CROSS`), ATC, OData `$metadata` doğrulama |
| `references/known-errors-adt.md` | 412/423/409/400/403, kilit, aktivasyon, classrun, transport hataları + genel teşhis dersleri |

## Rules
- Kimlik bilgisi: `.conn_adt`'yi okuma; şifre/kullanıcı/host sohbete, script'e, loga, hafızaya yazılmaz.
  Bağlantı hatasında (401) şifreyi tekrar tekrar denetme — hesap kilitlenebilir; kullanıcıya bildir.
- Ham ADT REST ile SAP'ye yazan geçici script yazılmaz: yazma yolu yalnız CLI'dir (kapılar orada).
  Referanslardaki REST akışları teşhis ve araç bakımı içindir.
- QA/PRD'de hassas veri okuma (KVKK) açık onay ister; DEV muaftır (SAP çekirdeği). Onay kelimesi
  net olmalı ("onay"); "dene", "çek" onay değildir.
- `adt_syntax_check` salt-okuma DEĞİLDİR: temiz bekleyen sürümü aktive eder → yazma sınıfı.
- Alt ajana (`agent`) SAP yazma işi verilmez; alt ajan yalnız okuma sınıfı araçlarla araştırır ve
  brifinge "yazma sınıfı araç çağırma" kuralı açıkça yazılır.
- Yeni bir ADT yöntemi başarısız denemelerden sonra çalıştıysa: çalışan yöntem + denenen başarısız yollar
  `%remember` ile proje hafızasına; her projede geçerliyse template'e öneri olarak.
