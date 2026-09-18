# SAP ADT araç kataloğu (CLI)

> **Otorite `sap_adt_cli.py --list` çıktısıdır.** Bu katalog araçların kaynak imzalarından ve açıklamalarından
> türetildi; CLI'nin argüman adı, varsayılanı ya da sınıfı bundan farklıysa `--list` kazanır ve bu dosya güncellenir.
> Çağrı: `python <TEMPLATE>/skills-sap/sap-adt-foundation/scripts/sap_adt_cli.py <tool> --args-json '{...}'`
> Yazma sınıfı: `--sap-write --scope S0|S1|S2` + (`--reason "<gerekçe>"` | `--intake .axet-code/intake/<id>.md`).

**Sınıf özeti (`--list` ile ölçüldü, 2026-09-13):** okuma 24 (`ping` + `sap_doctor` + 22 `adt_*`, `adt_unit_run` dahil) · yazma 13 · toplam 37.
Profil etiketlerinin tamamı ve yetenek matrisi: `references/profiles.md` (rehber; etiket tablosu kodla test edilir).
`adt_set_description` yalnız `s4_private`'ta açıktır ve transport ister.
`adt_unit_run` `allow_risky_tests=true` verilirse yazma sınıfına geçer (`--list`: `write_when`).
`adt_transport_list` yalnız `ecc`, `s4_private`, `s4_public` profillerinde açıktır (`available_on`); `btp_abap`'ta yoktur.
`adt_screen_generate` yalnız `ecc`, `s4_private` profillerinde açıktır. `adt_msgclass_write` yalnız `s4_private`'ta açıktır
(kaynak reçetenin kanıtı yalnız bu profil; diğer profilde `tool_not_available_for_profile`, çıkış 2).
`adt_post_shell` / `adt_push_source` içinde `fugr` ve `func` tipleri yalnız `ecc`, `s4_private`'ta (`--list`: `object_type_available_on`;
diğer profilde `type_not_available_for_profile`, çıkış 2).
Transport zorunlu araçlar (`requires_transport`): `adt_post_shell`, `adt_domain_create`, `adt_dtel_create`, `adt_struct_create`,
`adt_msgclass_write`, `adt_set_description`, `adt_screen_generate` (`requires_transport_when`: mode WRITE/DELETE). `adt_push_source` `bdef`/`ccimp`/`ccau` tiplerinde de transport ister (araç katmanı).
Argümanları dosyadan vermek için `--args-json` yerine `--args-file <json dosyası>`.

**Ortak dönüş okuma kuralları**
- `ok:false` + `error:"guardrail_violation"` (ya da çıkış kodu 2) → SAP'ye gidilmedi. Guard'ı aşmaya çalışma; bildir.
- **Yönlendirme ipuçları (engellemez, 2026-09-13):** yazma sınıfı her yanıtta üst düzey `checklist_hint` (obje tipine göre okunacak
  skill referansları; `status: var|yazılıyor`) ve çıkış 1/2'de `known_errors_hint` (hata kodu + SAP mesaj sınıfı/numarası deseninden
  bilinen-hata maddesi, `sap_message_keys`) bulunabilir. Karar vermez, çıkış kodunu değiştirmez; eşleşme desen tabanlıdır, teşhis değildir.
- Üç değerli alanlar (`true` / `false` / `null`): `null` = **ÖLÇÜLEMEDİ**, "hayır" ya da "doğrulandı" değildir.
- `client_log` alt katmanın ham satırlarıdır; `exists:false` ya da boş sonuçta önce buna bak.
- Sayı döndüren her araçta limite eşit sonuç = kırpılmış olabilir.

Tip değerleri — CLI tip tablosu (`lib/object_types.py`, kod okuması): `class`, `interface`, `program`, `include`,
`functiongroup`, `function`, `dataelement`, `domain`, `table`, `structure`, `tabletype`, `cds` (`ddls`), `metadataextension`,
`accesscontrol`, `servicedefinition`, `package`; eşanlamlılar (`ddls`, `doma`, `dtel`, `tabl`, `fugr`, `srvd` …) aynı tipe çözülür.
**Tabloda yok ama araçlarda özel yolu olan tipler (2026-09-13):** `bdef` (`adt_get` okur · `adt_post_shell` kabuk · `adt_push_source`
yazar · `adt_activate` aktive eder), `msag` (`adt_get`→`adt_msgclass_read` · `adt_post_shell` kabuk · `adt_msgclass_write` mesaj yazar), `enqu` (`adt_get` yalnız varlık — `include_source:false` · `adt_post_shell` kabuk ·
`adt_activate` aktive eder; kaynak okuma/yazma yok), `srvb` (`adt_activate` + `adt_publish_service`; yaratma/kaynak yok). Sınıf alt-include'ları
`ccimp`/`ccau`/`ccdef`/`ccmac` (`name` = ANA SINIF): `adt_get` dördünü okur, `adt_push_source` yalnız `ccimp`/`ccau` yazar.
Genel tablo `supports_create` bayrağı yalnız genel yaratıcının tiplerinde (class/interface/program/include) True'dur.

---

## Okuma sınıfı

### `ping`
- **Amaç:** CLI'nin çalıştığını doğrular. SAP'ye ulaşıldığını KANITLAMAZ.
- **Argüman:** yok.

### `adt_get`
- **Amaç:** obje var mı, metadata, (isteğe bağlı) kaynak.
- **Argümanlar:** `name` (zorunlu) · `object_type="class"` · `include_source=true`.
- **Dönüş:** `{ok, name, type, exists, source?, metadata?, client_log}`; yoksa `{ok:true, exists:false}`.
- **Uyarılar:** tablo/yapı için kardeş uç denenir (`sibling_probe`: `checked_found` / `checked_absent` / `unavailable:<sebep>`) ·
  yaratma/silme kararında DDIC varlığını tek başına buna dayandırma, `adt_search_objects` ile çapraz kontrol ·
  `func` grubu arama indeksinden çözer (yeni FM henüz indekste değilse `exists:false` dönebilir — DOĞRULANMADI) ·
  ağ hatasında `exists:false` yerine `ok:false` (`unreachable`/`belirsiz`) · MSAG → `adt_msgclass_read`'e delege ·
  **`enqu` (kilit objesi, 2026-09-14):** yalnız varlık sondası (salt GET `/ddic/lockobjects/sources/<ad>`): 200 `exists:true` · 404 `exists:false` ·
  diğer kod/istisna `ok:false` + `exists_probe` (ÖLÇÜLEMEDİ) · `include_source:true` → `unsupported_type` (ağa gidilmez) · kilit açmaz/silmez ·
  **sınıf alt-include'u:** `{"name":"ZCL_X","object_type":"ccimp"}` (ya da `ccau`/`ccdef`/`ccmac`) include ucunu okur; include 404 ise
  `exists:false` + `include_absent_proven:true` ve pull kaydı "yok" olarak yazılır (`pull_state: kaydedildi (include yok)`) → ilk yaratım push'u için ·
  `version="active"` metadata'sı boş kabukta da görünür ·
  **pull-before-edit:** kaynak okununca (`include_source=true`, `exists:true`) canlı özet `.axet-code/sap-pull-state.json`'a yazılır;
  yanıttaki `pull_state` (`kaydedildi` | `yazilamadi: …`) — `adt_push_source` bu kayıt olmadan yazmaz.

### `adt_msgclass_read`
- **Amaç:** mesaj sınıfı ve tüm mesajları (master dilde).
- **Argüman:** `name`.
- **Dönüş:** `{ok, name, exists, master_language?, description?, package?, count?, messages:[{no,text,selfexplanatory,documented}], pull_state?}`.
- **Uyarı:** okununca mesaj listesinin kanonik özeti `.axet-code/sap-pull-state.json`'a `msag:<AD>` anahtarıyla yazılır
  (`pull_state: kaydedildi`); `adt_msgclass_write` bu kayıt olmadan yazmaz. `adt_get(object_type="msag")` aynı yolu kullanır.

### `adt_search_objects`
- **Amaç:** ad/joker ile obje arama.
- **Argümanlar:** `query` (joker serbest, ör. `ZDEMO*`) · `max_results=50` (önerilen üst sınır 500) · `object_type` (ADT kodu: `CLAS`, `INTF`, `DOMA`, `DTEL`, `TABL`, `DDLS`, `PROG`).
- **Dönüş:** `{ok, count, results:[{name,type,uri,description}], object_type, object_type_sent, server_hit_count,
  type_filter_dropped, truncated, max_results, truncated_notice?, warning?}`.
- **`truncated` (K3, 2026-09-15):** sunucu isabet sayısı `max_results` tavanına dayandıysa `true` ve `truncated_notice`
  basılır. `adt_sql_query` / `adt_table_read` ile aynı çıktı sözleşmesi — ⚠ ama ölçüt AYNI DEĞİL: orada araç
  `row_limit + 1` isteyip fazlasını atarak **kesin** ölçer; burada ölçüt sunucu isabetinin tavana **dayanması**dır,
  yani tam olarak `max_results` kadar obje varsa `truncated: true` çıkar (yanlış-pozitif mümkün, yanlış-negatif değil).
  `truncated: true` iken `count` bir sayım DEĞİLDİR ve "listede yok" ⇒ "sistemde yok" çıkarımı geçersizdir.
- **FM tipi:** quickSearch sunucusu `FUNC`/`FUNC/FF` filtresine FM'i `FUGR/FF` tipiyle döndürür; istemci tip süzgeci eskiden bu isabeti
  eliyordu (var olan FM için `count:0`). FM takma adları (`FUNC`, `FUNC/FF`, `FUNCTION`, `func`, `function`) sunucuya `FUGR/FF` olarak
  gider (`object_type_sent`). Başka bir takma adda sunucu isabetleri süzgeçte elenirse `type_filter_dropped > 0` + `warning` döner →
  o `count:0` kanıt değildir (`tests/test_verdict_query_tools.py` U1-U6). En tehlikeli bileşim **tip süzgeci + kırpılmış sayfa**dır:
  ikisi birlikteyken `warning` ve `truncated_notice` AYNI ANDA döner (U9).
- **Bilinen sınır (kod okundu 2026-09-13):** uç sonuçları alfabetik döndürür ve üst sınırı **550**'dir (`MAX_SEARCH_RESULTS`); `object_type`
  sunucuya `objectType` olarak gider (istemci tarafında kırpılmış sayfa süzülmez — `tests/test_lib_regressions.py` SEARCH-1/2).
  ⚠ **2026-09-15'e kadar** yanıtta ayrı bir `truncated` alanı YOKTU ve kırpma yalnız `client_log` metninde görünürdü; yapılandırılmış
  sonucu okuyan bir ajan kırpılmış listeyi tam liste sanabiliyordu. **K3 ile düzeltildi** (yukarıdaki `truncated` maddesi). `count:0`
  ya da `count == max_results` yine "obje yok / hepsi bu" kanıtı değildir → deseni daralt, tip ver, gerekirse `adt_get` ile adı
  doğrudan oku.

### `adt_transport_list`
- **Amaç:** kullanıcının transport istekleri.
- **Argüman:** `user` (varsayılan bağlantıdaki kullanıcı).
- **Dönüş:** `{ok, count, transports, shape_recognized, zero_verified, zero_notice}`.
- **Uyarılar:** ⛔ `count:0` kanıt değildir; `zero_verified` hiçbir zaman `true` olmaz → `E070`/`E071` ile çapraz kontrol.
  Transport uydurulmaz; "yok" okuması yeni transport açma refleksine götürmemeli (Yasak C).

### `adt_where_used`
- **Amaç:** objeyi referanslayan objeler (etki analizi, silmeden önce kontrol).
- **Argümanlar:** `name` · `object_type="class"`.
- **Dönüş:** `{ok, name, type, count, references:[…], package_count, package_references:[…]}`; obje yoksa `{ok:false, error_code:"OBJECT_NOT_FOUND"}`
  ve `count` hiç yok. Yanıtta paket düğümü var ama tek obje referansı yoksa `{ok:false, error:"where_used_belirsiz", package_count, …}` — `count` basılmaz.
- **Uyarılar:** FM (`func`) için üç ayrık sonuç: yok → `OBJECT_NOT_FOUND`+`probe` · var ama çağıransız → `count:0, existence_verified:true` ·
  uç hatası → `ok:false`. usageReferences bir ağaçtır: `DEVC/K` düğümleri çağıranların paket atalarıdır, `count`'a girmez (`package_count`
  ayrı). FM çağıranında kanonik ölçüm `CROSS` (`foundation-query.md` §3.3).

### `adt_impact_analysis`
- **Amaç:** özyinelemeli where-used (kim dolaylı etkilenir).
- **Argümanlar:** `name` · `object_type="ddls"` · `max_depth=2` · `max_nodes=150`.
- **Dönüş:** `{ok, impacted_count, truncated, packages_skipped, by_depth:[{depth,count,objects}]}`. `truncated:true` → eksik.
  Paket (`DEVC/K`) düğümleri etkilenen sayılmaz ve özyinelemeye girmez; sayıları `packages_skipped`'tadır.

### `adt_grep_source`
- **Amaç:** paket ya da obje listesinde kaynak metninde regex arama.
- **Argümanlar:** `pattern` (Python regex) · `package` **veya** `objects` (`"AD"` ya da `"AD:tip"` virgüllü liste / liste) ·
  `object_types="CLAS,PROG,INTF,DDLS"` (paket taramasında filtre; FUGR varsayılanda YOK) · `max_objects=80` · `ignore_case=true`.
- **Dönüş:** `{ok, scanned_objects, match_count, matches:[{object,type,line,text,include?}], truncated_object_scope, truncated_matches,
  scope_verified, coverage_complete, skipped_objects, partial_objects, …}`.
- **Uyarılar:** `match_count:0` yalnız `coverage_complete:true` iken "geçmiyor". `skipped_objects[].reason`:
  `type_filtered` · `type_unsupported` · `max_objects` · `read_failed` · `not_readable` · `source_empty`.
  `partial_objects`: `fugr_skeleton_only` (FM gövdesi TARANMADI) · `class_includes_not_scanned`. Toplam 500 eşleşme sınırı.
  `scope_verified` paket ucunun doğruluğu, `coverage_complete` taramanın tamlığıdır — ayrı eksenler.

### `adt_package_contents`
- **Amaç:** paketteki objeler.
- **Argüman:** `package`.
- **Dönüş:** `{ok, package, count, objects:[…], package_verified, description_verified:false, warning?}`.
- **Uyarılar:** `package_verified:false` → ad-desenli arama fallback'i, başka paket objeleri karışabilir ·
  `description` doğrulanmaz (büyük pakette bir satır kayma ölçüldü) → obje kimliğini açıklamadan çıkarma.

### `adt_atc_check`
- **Amaç:** ATC statik kontrol (Clean ABAP, performans, güvenlik).
- **Argümanlar:** `name` · `object_type="class"` · `variant` (yoksa bağlantıdaki ATC varyantı, o da yoksa `DEFAULT`) · `max_verdicts=100`.
- **Dönüş:** `{ok, variant, finding_count, findings:[…]}`. Sayının doğrulanamadığı durum için ayrı alan olabilir (`finding_count_unverified`).

### `adt_table_read`
- **Amaç:** tablo verisi (data preview; WHERE yok).
- **Argümanlar:** `table` · `row_limit=100` · `columns` (`"A,B"` ya da liste; yoksa `SELECT *`) · `acknowledge_risk=false` · `approval_text`.
- **Dönüş:** `{ok, table, row_limit, truncated, data:{rows_labeled, columns}}`; okuma koşmadıysa `{ok:false, error:"tablo_okunmadi", sap_error?}`.
  `truncated` kesindir: araç `row_limit + 1` satır ister, fazlası gelirse `true` (tam `row_limit` satır kırpık sayılmaz).
- **Uyarılar:** ⚠ KVKK: QA/PRD'de hassas tablo/alan için kullanıcıdan net onay + `acknowledge_risk=true` + onay kelimeli
  `approval_text`; DEV muaf; tier çözülemezse muafiyet yok · satırları `rows_labeled`'dan oku · LCHR alanlarda düşer (`SELECT *`).

### `adt_sql_query`
- **Amaç:** OpenSQL SELECT (WHERE/JOIN/GROUP BY/COUNT).
- **Argümanlar:** `query` · `row_limit=100` · `acknowledge_risk=false` · `approval_text`.
- **Dönüş:** `{ok, row_count, row_limit, total_rows, truncated, truncated_notice?, columns, rows:[{KOLON:değer}]}`;
  koşmadıysa `{ok:false, error:"sorgu_kosmadi", message, sap_error?}` (`sap_error` = `{status_code, message, body_excerpt}`, SAP'nin kendi gövdesi).
- **Uyarılar:** yalnız SELECT/WITH; `INTO`/`UP TO` yazma · ⚠ KVKK (table_read ile aynı; FROM/JOIN tabloları, alan listesi, released CDS normalize edilir) ·
  `truncated` kesindir (`row_limit + 1` sonda satırı); `total_rows` SAP `totalRows`'tur ve aggregate'de alttaki satır sayısıdır → kırpma ondan
  okunmaz · 400'de önce `sap_error.message` · 400 sebepleri ve çareleri `foundation-query.md` §1.2.

### `adt_dump_list`
- **Amaç:** ST22 kısa dump listesi.
- **Argümanlar:** `limit=20` · `from_ts` / `to_ts` (ör. `20260710154122`) · `acknowledge_risk=false`.
- **Dönüş:** `{ok, count, dumps:[{error_type,program,user,timestamp,title,id,dump_uri}]}`.
- **Uyarılar:** kullanıcı adı taşır → DEV dışında `acknowledge_risk` (KVKK).

### `adt_inactive_objects`
- **Amaç:** aktive-bekleyen obje listesi.
- **Argüman:** yok.
- **Dönüş (ölçüldü):** `{ok:true, count, count_verified:true, inactive_objects, stale_deleted_count, stale_deleted}`.
  **Ölçülemedi:** `{ok:false, error:"tadir_kontrolu_belirsiz", confirmed_live_count, unverified_count, …}` — `count` basılmaz.
  Worklist gövdesi `ioc:inactiveObjects` değilse `{ok:false, error:"worklist_govdesi_degil"}`.
- **Uyarılar:** silinmiş objeler TADIR `DELFLAG` ile elenir · aktivasyon doğrulamasının ana aracı. TADIR en fazla 5 adlık parçalarla
  sorulur; başarısız ya da `truncated` parçanın adları `tadir_deleted:null` olur ve sonuç `ok:false` döner. Uzun worklist tüm parçalar
  ölçülürse artık `ok:true` dönebilir (ölçülen yüzey genişledi; ölçülemeyen ad "silinmemiş" sayılmaz). TADIR'da hiç satırı olmayan ad
  bugün `tadir_deleted:false` alır.

### `adt_enhancements`
- **Amaç:** objeye bağlı enhancement implementasyonları ve enjeksiyon noktaları (standart objeyi OKUR).
- **Argümanlar:** `name` · `object_type="program"` (`program|class|include|functiongroup`) · `include_source=false`.
- **Dönüş:** `{ok, exists, count, enhancements:[{name,type,version,enhanced_object,sites:[…]}]}`.

### `adt_enhancement_read`
- **Amaç:** ENHO/BAdI implementasyonunun kaynağını adla okumak.
- **Argümanlar:** `name` · `enh_type="enhoxhh"` (`enhoxhh` source-plugin · `enhoxh` impl · `enhoxhb` BAdI impl).
- **Dönüş:** `{ok, name, type, exists, source}`.

### `adt_enhancement_options`
- **Amaç:** objenin sunduğu exit/point/BAdI seçenekleri.
- **Argümanlar:** `name` · `object_type="program"` · `name_filter` (ör. `EX:`) · `max_results=100`.
- **Uyarı:** yanıt MB'larca olabilir → filtre + limit. `truncated` alanına bak.

### `adt_feature_probe`
- **Amaç:** sistemde hangi ADT yetenek uçlarının açık olduğu (discovery). Profil matrisini canlı kanıta çevirir.
- **Argüman:** `filter` (isteğe bağlı).

### `adt_lock_check`
- **Amaç:** obje kilitli mi.
- **Argümanlar:** `name` · `object_type="class"`.
- **Dönüş:** `{ok, locked: true|false|null, lock_owner?, exists}`.
- **Uyarı:** kilit ucu 404 verebilir (ölçüldü) → `locked:null` = ÇÖZÜLEMEDİ, "kilitli değil" değil (`known-errors-adt.md` K-08).

### `adt_unit_run` (varsayılan: okuma)
- **Amaç:** Z objenin ABAP Unit testleri.
- **Argümanlar:** `name` (Z/Y; standart reddedilir) · `object_type="class"` (`class|program|functiongroup`) · `allow_risky_tests=false`.
- **Dönüş:** `{ok, method_count, failed_count, passed, risk_levels, classes:[…]}`.
- **Uyarılar:** varsayılan yalnız `harmless` testler. ⚠ `allow_risky_tests=true` `dangerous`/`critical` testleri de koşar,
  **kalıcı veri değiştirebilir** → yazma sınıfı (`--sap-write` + kapsam) + onay · `method_count:0` → `risk_notice`'u oku.

---

### `sap_doctor` (bağlantı tanısı)
- **Amaç:** tek komutla bağlantı katmanlarını sınamak; `PASS/WARN/FAIL/SKIP` + **kapsam beyanı** (`not_checked`).
- **Argüman:** `live=true` (false → yalnız yerel katmanlar).
- **Katmanlar:** `sap_project` · `profile` · `conn_file` (varlık) · `conn_keys` (URL/USER/PASSWORD/CLIENT dolu mu, `<...>` yer tutucu var mı — değer
  okunmaz/basılmaz, parolada yalnız doluluk) · `env_override` (ortam `ADT_SAP_URL`/`ADT_SAP_CLIENT` dosyayı eziyorsa FAIL) · `tier` (DEV PASS · QA/PRD WARN ·
  UNKNOWN FAIL) · `language` (≠ `master_language` WARN) · `tls` (doğrulama kapalı WARN) · `tool_layer` · canlı: `logon` (erişim + kimlik; 401/403, SSO
  sayfası, ulaşılamaz ayrı mesajlar) · `csrf` (token alınabildi mi; değer basılmaz).
- **Dönüş:** `{ok, verdict, summary{pass,warn,fail,skip}, checks[{id,status,detail}], not_checked[]}`. FAIL varsa `ok:false`, `error:"doctor_fail"`, çıkış 1.
- **Kural:** `sap-project.json` yokken de çalışır (CLI okuma kapısından muaf) ama yerel ön koşullardan biri FAIL ise **SAP'ye gitmez** (canlı katmanlar SKIP)
  — okuma kapısıyla aynı sonuç. URL/host, kullanıcı, client, parola, token, sistem kimliği çıktıya konmaz.
- **Bakmadıkları:** obje/paket yetkisi, transport, TLS sertifika geçerliliği, yazma uçlarında CSRF kabulü, SSO çerez ömrü, profil matrisinin canlı
  doğruluğu, ATC variant (`not_checked`'te yazılı). "PASS" = bağlantı + kimlik + token alındı; yazabileceğin anlamına gelmez.

### `adt_revisions`
- **Amaç:** obje sürüm geçmişi (versions feed).
- **Argümanlar:** `name` · `object_type="class"` (`object_types` tipi; FM generic URL taşımaz → `unsupported_type`) · `limit=20` (1-200) · `acknowledge_risk=false`.
- **Dönüş:** `{ok, name, type, object_url, versions_link_found, count, returned, revisions[{version, versionTitle, author, date, uri}], author_masked}`.
- **Uyarılar:** `versions_link_found:false` + `count:0` = uç sürüm linki sunmadı; "sürüm yok" kanıtı DEĞİL · yapı okunamazsa `revisions_unavailable`,
  feed okunamazsa `revisions_feed_failed` (kütüphane metodu bu durumları `[]` ile yutuyordu; araç ayırır) · DEV dışı tier'da yazarlar (kullanıcı kimliği)
  `***` maskelenir, `acknowledge_risk=true` açar (engellemez) · link deseni kütüphanedeki `<link … rel=".../versions">` desenidir; SAP'nin bu biçimi
  döndürdüğü canlı **DOĞRULANMADI**.

### `adt_object_structure`
- **Amaç:** obje yapısı (metot, attribute, include … bileşenleri).
- **Argümanlar:** `name` · `object_type="class"` · `version="active"` (`inactive`).
- **Dönüş:** `{ok, name, type, object_url, version, exists, component_count, components[{name,type,uri,description}]}`; 404 → `ok:true, exists:false`;
  ayrıştırılamayan yanıt → `structure_unparseable`.

### `adt_system_info`
- **Amaç:** bağlı sistemin ADT discovery servis kataloğu.
- **Dönüş:** `{ok, service_count, available_services[{title,href}], logon_language, tier, profile, withheld_fields}`. Bağlantı URL'si, client, kullanıcı
  ve sistem kimliği bilinçli olarak **çıktıya konmaz** (`withheld_fields`). Discovery okunamazsa `discovery_unavailable` → `sap_doctor`.

## Yazma sınıfı
Hepsi: `install.py --sap-write` (kullanıcı çalıştırır) · tier DEV · `--sap-write` · kapsam beyanı. Guard'lar ağdan önce.

### `adt_post_shell`
- **Amaç:** boş Z obje kabuğu (inaktif, kaynaksız).
- **Argümanlar:** `object_type` · `name` (Z/Y; lock object E+Z/Y) · `package` (mevcut) · `transport` · `description` (`master_language`'de, **boş olamaz** → `ADR_0005_D`) ·
  `extra` (yalnız aşağıdaki tiplerde; başka tipte ya da tanınmayan alanla → `invalid_argument`, çıkış 3).
- **Desteklenen tipler (çevrimdışı sahte istemciyle test edildi; canlı DOĞRULANMADI):**

  | Tip | Yol | `extra` | Sonraki adım |
  |---|---|---|---|
  | `class`, `interface`, `program`/`prog`, `include` | genel yaratıcı (değişmedi) | — | `adt_get` → `adt_push_source` → `adt_activate` |
  | `ddls` | yalnız-metadata kabuk (kaynak gövdeye konmaz) | — | `adt_get` → `adt_push_source(ddls)` → `adt_activate` → readback |
  | `srvd` | `srvdSourceType="S"` kabuk | — | `adt_get` → `adt_push_source(srvd)` → `adt_activate(srvd)` |
  | `bdef` | "blues" kabuk; **ad = kök entity adı** (SAP zorunlu, araç doğrulayamaz) | — | `adt_get` → `adt_push_source(bdef)` → `adt_activate(<kök ddls>, also=[bdef, class])` |
  | `fugr` | fonksiyon grubu | — | `adt_activate(fugr)` |
  | `func` | FM kabuğu (grup içinde) | `{"function_group":"<Z/Y FUGR>"}` zorunlu | `adt_get(func)` → `adt_push_source(func)`; RFC-enable SE37'de |
  | `msag` | mesaj sınıfı kabuğu (stateless POST) | — | `adt_msgclass_read` → `adt_msgclass_write` |
  | `enqu` | kilit objesi | `{"primary_table", "lock_fields":["MANDT",…], "lock_mode":"E|S|X", "allow_rfc":false}` | `adt_activate(object_type="enqu")` |
  | `ttyp` | tablo tipi | `{"row_type":"<yapı/DTEL>"}` | `adt_activate(ttyp)` → `DD40L.ROWTYPE` dolu mu (`adt_sql_query`) |

  **Desteklenmez (`unsupported_type`, çıkış 3, gerekçe mesajda):** `ddlx`, `dcl` (canlı reçete yok) · `srvb` (REST'te bloke) ·
  `doma`/`dtel`/`structure` (composite araçlar) · `tabl` · paket (`ADR_0005_C`, çıkış 2).
- **Dönüş:** `{ok, name, type, object_url?, http_status?, exists_after?, exists_probe?, master_language?, next_step?, recipe?}`;
  hata: `{ok:false, error, message, exists_after, exists_probe}`. Tipe özel yollarda başarıdan sonra da **varlık sondası** koşar:
  2xx ama obje yok → `error: create_not_persisted` (`ok:false`); sonda ölçülemedi → `notice`. `ttyp`'te `row_type_live`.
- **Uyarılar:** ⛔ `ok:false` "yaratılmadı" değildir → `exists_after` (`true`: tekrar yaratma · `false`: yeniden denenebilir · `null`: elle doğrula) ·
  `error`: `already_exists` · `description_too_long` (60) · `create_failed` · `create_not_persisted` · `master_language_warning` görürsen DUR (`known-errors-adt.md` K-17) ·
  include için include tipi, program için `prog` (K-11) · FM'in fonksiyon grubu kapıda Z/Y denetlenir (standart FUGR içine FM = Yasak A).

### `adt_push_source`
- **Amaç:** mevcut objeye tam kaynak gönderme.
- **Argümanlar:** `name` (Z/Y) · `object_type` · `source` (tam içerik) · `transport` (obje zaten atanmışsa isteğe bağlı) ·
  `skip_reviewer=false` · `ack_drop=""` (ikisi de aXet yazma kapısında **yasak**: verilirse `reviewer_bypass_forbidden`, çıkış 2).
- **Dönüş:** `{ok, name, type, result, readback_verified, readback_notice?, syntax_precheck?, syntax_precheck_notice?, syntax_errors?, reviewer?, post_check?}`.
  `syntax_precheck:"olculemedi"` → aktivasyon öncesi sözdizimi ön-kontrolü **ölçülemedi** (`valid:null`, kontrol istisnası
  ya da çağrı istisnası); push aktivasyona devam etti, `ok` değişmez, `syntax_precheck_notice` sebebi yazar — "sözdizimi temiz" DEĞİLDİR.
- **Uyarılar:** açıklama "aktivasyon ayrı adım" der, alt katman kilit→yükleme→aktivasyon→readback dener → sonucu
  `adt_inactive_objects` ile doğrula · `syntax_precheck:"failed"` → yüklendi ama aktive edilmedi (class/interface'te koşar;
  prog/fugr/include'da koşmaz) · `readback_verified:null` "doğrulandı" değildir · gömülü inceleme (reviewer) yalnız bazı tiplerde
  tanımlıdır; `SKIP` "PASS" değildir · ölçüm üretmeyen gate `reviewer.unmeasured` + `notice`/`gate.review` "ÖLÇÜLEMEDİ" yazar (WARNING'i
  "temiz" okuma; BLOCKER önemli gate ölçülemezse yazma durur) · BLOCKER → `reviewer_blocker` (kaynağı düzelt) · incelemeyi atlatmak
  (`skip_reviewer`) ve Z tablo alanı silme BLOCKER'ını onaylı geçirmek (`ack_drop`) aXet'te kapıda reddedilir — alan silme
  gerekiyorsa DUR, veri kaybı riskini kullanıcıya açıkla · 412/423 → `known-errors-adt.md` K-01…K-03 ·
  **Kesin Yasak B:** kaynakta standart tabloya doğrudan DML → `ADR_0005_B` (çıkış 2, mesajda satır + hedef; kaynak taranamazsa `std_dml_scan_unavailable`) ·
  **pull-before-edit:** önce `adt_get` şart — kayıt yok `pull_before_edit_missing` (2) · çekildikten sonra SAP'de değişmiş `source_changed_since_pull` (2) ·
  canlı okuma başarısız `pull_live_read_failed` (1) · durum dosyası bozuk `pull_state_unreadable` (2); başarılı push kaydı günceller (`pull_state: guncellendi`).
- **Tipe özel yazma (2026-09-13; çevrimdışı test edildi, canlı DOĞRULANMADI):**
  - `bdef`: LOCK → PUT (If-Match YOK) → UNLOCK → readback; **aktive ETMEZ** (`activated:false` + `activation_note`) → `adt_activate(<kök ddls>, also=[bdef, behavior class])`. Transport zorunlu. Yasak B taraması uygulanmaz (ABAP değil). Reviewer `rap_bdef_creation`.
  - `ccimp` / `ccau`: `name` = **ana sınıf** (`{"name":"ZBP_X","object_type":"ccimp",…}`); include yoksa önce iskelet (POST) sonra PUT; bayt readback; ana sınıf aktive edilir — RAP behavior pool'da BDEF inaktifse aktivasyon düşer (`push_failed` + `activation_note`) → `also` ile birlikte aktive et. Transport zorunlu. Yasak B taranır. Reviewer `class_push`. `ccdef`/`ccmac` → `unsupported_type` (yazma yolu ölçülmedi).
  - `func`: fonksiyon grubu canlı okumadan çözülür (`function_group` yanıtta) ve **Z/Y olmalı** (değilse `ADR_0005_A`, yazma yok); sıkı kilit PUT + ayrı aktivasyon; aktivasyon düşerse `push_failed` + `activation_errors` (kaynak yüklendi, kayıt güncellendi). İmza satır-içi ABAP (`*"` blok 400 verir, K-15). Yasak B taranır. Reviewer yok (SKIP görünür).
  - `ddls`: kaynak `define [root] view entity` / `as projection on` içeriyorsa reviewer `rap_cds_creation` (RAP read-only consumption BLOCKER + reuse WARNING dahil), yoksa `cds_update`.
  - `prog` / `program` / `include` (2026-09-14): reviewer `program_push` — abaplint, released_objects, decimal_write_to (üçü WARNING). abaplint
    include'u ve `PROGRAM` satırlı modül havuzunu ölçemez → SKIP = WARNING + ÖLÇÜLEMEDİ; engellemez. Önceden reviewer yoktu (SKIP).
  - `intf` / `interface` (2026-09-14): reviewer `interface_push` — `TYPE c LENGTH n` metot parametresi BLOCKER (`reviewer_blocker`),
    decimal_write_to ve released_objects WARNING. Önceden reviewer yoktu (SKIP).
  - `srvb`, `msag`, `enqu` → `unsupported_type` (kaynak metni yok; mesajlar için `adt_msgclass_write`).

### `adt_activate`
- **Amaç:** tek obje ya da `also` ile atomik çoklu aktivasyon.
- **Argümanlar:** `name` · `object_type="class"` · `also=[{"name":"…","object_type":"…"}]`.
- **Dönüş:** `{ok, activated, errors?, warnings?, refs?, activation_verified?, still_inactive?}`.
- **Uyarılar:** tek-obje yolunda `activation_verified` (`false` = sahte-OK, `ok:false`, `error:"activation_not_executed"`; `null` = kanıtlanmadı) ·
  bağımlı zincirlerde (CDS + BDEF + behavior class, include + program) `also` kullan · standart bağlam programını aktive
  etmek Yasak A gri bölgesi → kullanıcı onayı (`foundation-ops.md` §4.3) ·
  **`enqu` (kilit objesi, 2026-09-13):** tek-obje yolu `ENQU/DL` referansıyla aktive eder (`activation_executed` + worklist readback);
  `also` içinde `enqu` desteklenmez · ENQUEUE_/DEQUEUE_ FM'lerinin üretildiğini ayrıca doğrula (`adt_search_objects`) — DOĞRULANMADI ·
  FM (`func`) bu araçla aktive EDİLEMEZ (generic URL yok) → FM aktivasyonu `adt_push_source(func)` içindedir.

### `adt_delete`
- **Amaç:** Z/Y objeyi silmek.
- **Argümanlar:** `name` (Z/Y; standart reddedilir) · `object_type` · `transport`.
- **Dönüş:** `{ok, name, type, deleted}`.
- **Uyarılar:** where-used araç tarafından yapılmaz → önce `adt_where_used` (+ `CROSS`) · geri alınamaz → açık onay ·
  `func` için çalışmaz ("lock not supported") · silme sonrası `adt_get` ile yokluğu doğrula.

### `adt_publish_service`
- **Amaç:** OData V2 service binding'i (SRVB) yeniden yayınlayıp `$metadata`'yı tazelemek.
- **Argümanlar:** `name` (SRVB) · `version="0001"`.
- **Dönüş:** `{ok, status_code, published: true|false|null, severity, sap_message, …}` — hüküm HTTP kodundan değil gövdedeki `SEVERITY`'den.
- **Uyarı:** doğrulama `$metadata` okumaktır (tip-kapsamlı, `foundation-query.md` §5.1).

### `adt_classrun`
- **Amaç:** `IF_OO_ADT_CLASSRUN` sınıfını çalıştırmak (F9 muadili). Kod çalıştırır, yazma yapabilir.
- **Argüman:** `name` (Z/Y).
- **Dönüş:** `{ok, class, status, output}`.
- **Uyarılar:** ⚠ `ok:true` çıktının güncel olduğunu kanıtlamaz (bayat oturum vakası) → çıktıda yeni koda özgü imza ara ·
  "does not implement" = aktive edilmemiş ya da bayat oturum; taze adla yeniden yaratma YANLIŞ (K-13) ·
  dialog context FM'leri çalıştıramaz (`400 Session Timed Out`, K-14).

### `adt_domain_create`
- **Amaç:** domain yarat + aktive et + doğrula.
- **Argümanlar:** `name` · `datatype` (`CHAR`, `NUMC`, `INT4`, `CURR`, `QUAN`, `DATS`, `TIMS`, `DEC` …) · `length` · `description` · `package` ·
  `transport` · `decimals=0` · `lowercase=false` · `fixed_values=[{"value":"A","text":"…"}]` · `artifact_path`.
- **Dönüş:** `{ok, type:"doma", output_length, reviewer, steps:{pre_flight, reviewer, pre_check, create, activate, verify}}`. Otomatik geri alma yok.
- **Argüman ön kontrolü (2026-09-13; artefakt beklemez, ağdan önce) → `steps.pre_flight`:** `datatype` ∈ CHAR, NUMC, DATS, TIMS, CLNT, INT1, INT2,
  INT4, INT8, DEC, QUAN, CURR (çıktı uzunluğu formülü yalnız bunlar için tanımlı) · `length` pozitif tamsayı · `decimals` ≥ 0 · `lowercase` true/false ·
  `fixed_values` her öğede dolu `value` + dolu `text` (`master_language` metni; metin değerle doldurulmaz). BLOCKER → `error: preflight_blocker`
  (çıkış 2, `steps.pre_flight.findings[]` kuralı ve kaynağı söyler). `pre_flight.not_checked` bakılmayanları listeler (lowercase yalnız CHAR, tipe sabit uzunluk …).
- **Çıktı uzunluğu:** araç hesaplar ve gönderir — CHAR/NUMC/DATS/TIMS/CLNT = length · INT1 4 · INT2 6 · INT4 11 · INT8 20 · DEC/QUAN/CURR = length+4
  (`output_length`). Önceden gövdeye girdi uzunluğu yazılıyordu (düzeltildi; canlı aktivasyon uyarısıyla DOĞRULANMADI).
- **Reviewer:** `artifact_path` (domain CSV `name,datatype,length,decimals,description,fixed_values` ya da domain XML) verilirse `domain_creation_csv`
  zinciri (BLOCKER → `reviewer_blocker`; desteklenmeyen uzantı ölçülemez → BLOCKER). Verilmezse `reviewer.verdict:"SKIP"` +
  `skip_reason:"no_artifact_path_provided"` yanıtta ve `gate.review`'da görünür — "reviewer PASS" değildir; argüman kuralları yine `pre_flight`'ta koşar.

### `adt_dtel_create`
- **Amaç:** data element yarat + aktive et + doğrula.
- **Argümanlar:** `name` · `domain_name` (Z domain ya da `CHAR1` gibi standart tip) · `description` · `package` · `transport` ·
  `short_label` · `medium_label` · `long_label` · `heading_label` (4'ü de dolu, `master_language`'de) · `artifact_path`.
- **Uyarılar:** DTEL adı kullanıcıdan gelir; metinler spesifikasyondan (tahmin yasak) ·
  ağdan önce tier, Z/Y, transport, açıklama dolu, 4 etiket dolu ve **etiket uzunlukları ≤ 10/20/40/55** (kısa/orta/uzun/başlık; kenar boşluğu
  kırpılıp karakter sayılır) denetlenir → aşım `ADR_0005_D` (çıkış 2, mesaj `short=11>10` biçiminde). Sınırlar DTEL CSV validator'ıyla aynı
  tablodan (2026-09-13; önceden artefaktsız çağrıda uzunluk denetlenmiyordu) · kullanılan domain'in varlığı ağdan önce **denetlenmez** (açık kalem).

### `adt_struct_create`
- **Amaç:** DDIC yapı yarat + aktive et + doğrula.
- **Argümanlar:** `name` · `fields=[{"name":"FIELD1","type":"char10"},{"name":"CUST","type":"<DTEL>"}]` · `description` · `package` · `transport` · `artifact_path`.
- **Uyarılar:** ⚠ tek başına alanları yazmayıp yer tutucu bırakabilir (ölçüldü) → kabuk + `adt_push_source(object_type="structure")` ile tam DDL + aktif sürüm readback
  (`foundation-ops.md` §3.2) · `artifact_path` ile gömülü inceleme önceki araç setinde 120 sn zaman aşımına düştü ·
  **yazma öncesi DTEL denetimi (2026-09-14'ten beri, artefakt verilsin verilmesin):** tier, Z/Y, transport, açıklama ve her alanda `name`+`type`
  denetimine ek olarak, SAP'ye yazılacak `fields[]`'teki Z/Y ve `/ad-alanı/` tipleri çıkarılır ve `check_struct_field_dtel_active.py` koşar
  (`struct_fields_dtel`): DTEL yok ya da inaktif → `reviewer_blocker`; ad DTEL değil ama yapı/tablo/tablo tipi olarak varsa kapsam dışı; SAP okunamazsa
  ÖLÇÜLEMEDİ → yine `reviewer_blocker` (PASS sayılmaz). Gate'in istemci kurulumu ve tüm SAP okumaları tek, gerçek toplam süre bütçesiyle (varsayılan 28 sn; istek bir iplikte koşar, ana akış
  yalnız kalan süre kadar bekler → damlayan ya da asılı yanıt bütçeyi aşamaz — ölçüldü, bütçe 3 sn: 1 bayt/1,5 sn damlayan yanıt ve 30 sn asılı
  istemci kurulumu → gate süreci 3,3-3,7 sn, süreç açılışı dahil; tekrar deneme yok; yapı ve alan açıklamaları dahil yazılacak DDL'in aynısı
  denetlenir; K10'dan beri bütçe YAPILANDIRILABİLİR: `AXET_REVIEWER_BUTCE_SN` üç katmanı birlikte yükseltir/düşürür,
  `AXET_DTEL_GATE_BUTCE_SN` yalnız gate payını ayarlar — üst sınırı artık sabit değil zincir bütçesi; geçersiz değer → varsayılan + uyarı) koşar; bütçe dolarsa denetlenemeyen adaylar ÖLÇÜLEMEDİ →
  `reviewer_blocker` ("süre bütçesi (N sn) doldu, M aday denetlenmedi"). Zincir sarmalayıcı bütçesini (varsayılan 60 sn) aşarsa `reviewer_timeout` → `reviewer_blocker`
  (ÖLÇÜLEMEDİ; canlı — SAP'ye bağlanan — BLOCKER gate taşıyan HER zincirde: `table_creation`, `table_update`, `struct_creation`, `struct_fields_dtel`,
  `struct_post_create`, `sap_active_check`; canlı BLOCKER taşımayanlarda WARNING). Ayrıntı + ölçümler: IMPLEMENTATION §20.9.
  `artifact_path` verilirse: yol bulunamazsa `artifact_not_found` → `reviewer_blocker` (ağa gidilmez); varsa `fields[]` denetimi BLOCKER değilse
  artefaktın `struct_creation` zinciri de koşar, hükümler birleşir (`reviewer.results[].girdi` = `fields` | `artifact`). Boş `fields[]` →
  `validation_error` (reviewer'dan önce). Standart DTEL'ler (ör. MATNR) denetlenmez. Önceden (2026-09-13 ölçümü) artefaktsız çağrıda bu denetim yoktu;
  artefaktlı çağrıda `fields[]` hiç denetlenmiyordu ve olmayan artefakt yolu SKIP ile yazıyordu (bug gate 2026-09-14). Yaratma sonrası içerik
  doğrulaması (`content_verify`) artefakttan bağımsız koşar. `already_exists` ve create hatası dönüşleri de `reviewer` alanını taşır.
  **Satır sonu yasağı (2026-09-15):** `description` ile her alanın `description`/`name`/`type` değeri tek satır olmalı — CR, LF, U+2028, U+2029 ya da U+0085 varsa ağa ve reviewer'a gitmeden `validation_error` (mesaj yeri ve karakter kodunu söyler, ör. `fields[0].description … U+000A`); aynı kural render'da `ValueError` → gate'te `reviewer_blocker` (`ddl_render_hatasi`).

### `adt_msgclass_write` (mesaj sınıfına mesaj yazma — YAZMA)
- **Amaç:** mevcut Z/Y mesaj sınıfına mesaj eklemek; açık izinle mevcut mesajı değiştirmek ya da silmek. Profil: yalnız `s4_private`.
- **Sıra:** kabuk yoksa `adt_post_shell(object_type="msag")` → `adt_msgclass_read` (canlı liste + pull kaydı) → nihai listeyi kullanıcıya göster → `adt_msgclass_write`.
- **Argümanlar:** `name` (Z/Y) · `transport` (zorunlu) · `messages=[{"no":"001","text":"<master_language metni, ≤ 73>","selfexplanatory":false}]` ·
  `delete_numbers=["005"]` · `allow_overwrite=false` · `package` (yalnız canlı okumada paket yoksa; farklıysa red).
- **Semantik:** SAP tarafında PUT tüm listeyi değiştirir; araç önce canlı listeyi okur ve **birleştirir**: yeni numara eklenir, verilmeyen mevcut mesajlar
  **korunur** (`documented` bayrağı dahil). Mevcut numaraya farklı metin/bayrak → `allow_overwrite=true` yoksa `msgclass_overwrite_not_allowed` (çıkış 2,
  `plan.overwritten` önce/sonra). Silme yalnız `delete_numbers` ile; canlıda olmayan numara → `invalid_argument`. Değişiklik yoksa kilit alınmaz (`changed:false`).
- **Dönüş:** `{ok, name, changed, plan{added, overwritten[{no,before,after}], deleted[{no,text}], unchanged, preserved_count}, message_count_before,
  message_count_after, readback_verified, pull_state, http{lock,put,unlock}, unlock_warning?}`.
- **Kilit:** kendi aldığı kilidi kendisi bırakır; enqueue kilidi **silmez**. Kilit alınamazsa `lock_conflict` (403/409/423 ya da gövdede kilit izi) /
  `lock_failed` (çıkış 1) → kullanıcı SM12'de kendi kilidini kontrol eder, SE91/ADT'de açık sınıfı kapatır; sonra `adt_msgclass_read` → tekrar.
  `unlock_warning` görürsen aynı yönlendirmeyi kullanıcıya ilet.
- **Doğrulama:** yazmadan sonra canlı liste beklenen tam listeyle kıyaslanır: fark → `readback_mismatch` (`ok:false`, `readback_diff`), okunamadı →
  `readback_failed`; ikisinde de pull kaydı silinir (yeniden oku).
- **Red kodları:** `ADR_0005_A` (standart sınıf) · `ADR_0005_C` (transport) · `ADR_0005_D` (boş metin; sınıfın master dili ≠ `master_language`) ·
  `invalid_argument` (numara 3 haneli metin değil, metin > 73, tekrar eden numara, yaz+sil çakışması, `documented` alanı, boş istek — çıkış 3) ·
  `pull_before_edit_missing` / `source_changed_since_pull` / `pull_state_unreadable` (2) · `pull_live_read_failed` · `master_language_unresolved` ·
  `msgclass_live_incomplete` (canlıda paket/açıklama/sorumlu yok; tahmin edilmez) · `push_failed` (1).
- **Uyarı:** canlı davranış **DOĞRULANMADI** (çevrimdışı sahte istemciyle test edildi). Uzun metin (`documented`) bu araçla yazılmaz.

### `adt_syntax_check` (adına rağmen YAZMA)
- **Amaç:** sözdizimi kontrolü — gerçek semantik "temizse aktive et".
- **Argümanlar:** `name` (Z/Y) · `object_type="class"`.
- **Dönüş:** `{ok, valid: true|false|null, errors, warnings}`; koşmadıysa `{ok:false, error:"sozdizimi_belirsiz", valid:null, valid_reason}`.
- **Uyarılar:** ⚠ bekleyen temiz sürümü AKTİVE EDER (ölçüm: inaktif 1→0), kod göndermez → sunucudaki bekleyen sürüm devreye girer;
  bilinçli bekletilen aktivasyon sırasını bozar · push zaten aktivasyon öncesi kontrol içerir → ayrı tur gereksiz ·
  `valid:false` yalnız `ok:true` iken "hatalı".

### `adt_screen_generate` (klasik Dynpro + GUI status üreteci — YAZMA)
- **Amaç:** projede bulunan **Z/Y ekran üreteci RFC FM'ini** (imzası kaynak kılavuzdaki 16 parametrelik üreteçle aynı) SOAP-RFC
  (`/sap/bc/soap/rfc`, dialog context) üzerinden çağırıp hedef Z/Y programa ekran + GUI status + titlebar (+ buton/alan) üretmek.
  FM adı gömülü değildir; FM'in kendisini bu araç yaratmaz. Profil: yalnız `ecc`, `s4_private`.
- **Argümanlar:** `fm_name` (Z/Y, zorunlu) · `program` (hedef Z/Y, zorunlu) · `title` (WRITE'ta zorunlu, `master_language` metni, kullanıcıdan) ·
  `dynpro="0100"` (4 hane) · `screen_type` (`DOCKING`|`CONTAINER`) · `cc_name` · `buttons=[{FCODE,TEXT,ICON,QUICKINFO,FKEY}]` (FKEY boş bırak) ·
  `fields=[{CONT_TYPE,CONT_NAME,NAME,TYPE,FORMAT,LENGTH,VISLENGTH,LINE,COLUMN,TEXT,FROM_DICT,INPUT_FLD,OUTPUT_FLD,REQU_ENTRY,POSS_ENTRY,MATCHCODE,CONV_EXIT,REF_FIELD,GROUP1}]`
  (yalnız `DOCKING`) · `src_prog`/`src_status` (donör, salt okunur; BACK/EXIT/CANCEL bekleyen PAI için `SAPLKKBL`/`STANDARD`) ·
  `cua_merge` (`X`|` `|`-`) · `nav_remap` (` `|`X`|`-`) · `mode="WRITE"` (`WRITE`|`READ`|`DELETE`) · `recreate` (`X`|` `) · `transport` (WRITE/DELETE'te zorunlu).
- **Dönüş:** `{ok, fm_name, program, dynpro, mode, http_status, ev_rc, ev_rc_band, ev_rc_note, ev_message (kırpılmamış), nav_remap, signals{nav_remap, cua_merge, fields, donor, dikkat[]}, warnings[], request{…}}`.
- **Hüküm:** `ok` = `EV_RC == 0` ve (WRITE'ta) `nav_remap≠OFF`. `EV_RC≠0` → `error: screen_gen_rc` + bant (`bilesik` 1-18 — rc=2 "ekran zaten var" olabilir;
  `fields_invalid` 5 · `donor_fetch` 101-113 · `donor_status_missing` 120-130 · `merge_fetch` 202-213 · `dynpro_invalid` 300 · `zy_guard` 301) ·
  `nav_remap=OFF` → `error: nav_remap_off` (çağrı yanlış; ekranı kullanmadan düzelt) · sinyal yok → `warnings` (ölçülemedi) · SOAP fault → `soap_fault` · EV_RC yok → `ev_rc_missing`.
- **Uyarılar:** ⛔ `cua_merge=" "`/`"-"` programın **diğer status/titlebar'larını siler**; `recreate="X"` ve `mode="DELETE"` ekranı siler —
  bu argümanlar yalnız açıkça verilirse gönderilir ve `warnings`'e yazılır · READ modu da yazma sınıfındadır (`--sap-write` + kapsam) ·
  `TABLES` (`IT_FIELDS`/`IT_BUTTONS`) istekte daima boş etiketle gider · runtime davranışı (buton tepkisi, `00256`/`00264`) yalnız ekran çalıştırılınca
  görünür → `mode="READ"` dökümünü önce/sonra kıyasla · canlı davranış **DOĞRULANMADI** (çevrimdışı test).

### `adt_set_description` (obje kısa açıklamasını değiştirme — YAZMA)
- **Amaç:** mevcut Z/Y objenin `adtcore:description`'ını değiştirmek; kaynağa dokunmaz. Profil: yalnız `s4_private`. Transport zorunlu.
- **Tipler:** `class`, `bdef`, `srvd`, `ddls` (`cds`), `ddlx`, `dcl`. Canlı ölçüm yalnız **DDLS** (`live_evidence: measured_ddls`; diğerleri `not_measured`).
  `srvb` (REST'te LOCK 200 → PUT 423), `prog` (program açıklaması TRDIRT ADT ile değişmez → kullanıcı SE38'de değiştirir), `dtel` (envelope'ta açıklama iki
  kez geçer, ayrı PUT reçetesi; ölçülmedi) ve diğerleri → `unsupported_type` (çıkış 3).
- **Argümanlar:** `name` · `object_type` · `description` (tek satır, `master_language` metni, kullanıcıdan/spesifikasyondan; sınıfta ≤ 60) · `transport`.
- **Akış:** (çekme kaydı varsa canlı kaynak özeti kıyası) → envelope GET → açıklama KÖK öğede mi + `masterLanguage` = `master_language` mı +
  `descriptionTextLimit` → aynıysa NOOP (`changed:false`, kilit yok) → aktive-bekleyen listesi (PUT öncesi) → LOCK (`corrNr`) → PUT (If-Match) →
  UNLOCK (`finally`) → `412 SADT_RESOURCE 043`'te envelope bayt bayt aynıysa yeni kilit döngüsünde TEK retry → PUT sonrası liste → yalnız PUT öncesi
  liste temizse otomatik aktivasyon → liste tekrar → aktif sürüm readback.
- **Dönüş:** `{ok, name, type, object_url, live_evidence, changed, description_before, description_after, state: active|inactive|unknown, readback_verified,
  activation{pre_put_inactive, post_put_inactive, activated, post_activation_inactive}, etag_retry, http{…}, pull_state, unlock_warning?, notice?}`.
- **Hata kodları:** `lock_conflict` / `lock_failed` (kilit silinmez; SM12 yönlendirmesi) · `transport_mismatch` (kilit başka transporta bağlandı, PUT yok) ·
  `put_precondition_failed` · `envelope_changed_since_read` · `put_failed` (+ `diagnosis_423`) · `activation_required` (obje PUT öncesi zaten inaktifti ya
  da liste okunamadı → bekleyen başka sürüm habersiz aktive edilmez; kullanıcıyla `adt_activate`) · `activation_failed` · `activation_not_verified` ·
  `activation_state_unknown` · `readback_mismatch` · `envelope_unrecognized` · `envelope_read_failed` · `description_too_long` · `master_language_unresolved` ·
  `ADR_0005_A/C/D` · `source_changed_since_pull` / `pull_state_unreadable` (2) · `pull_live_read_failed`.
- **Uyarılar:** başarılı PUT objeyi **inaktife düşürür** (K-19) → `state:"inactive"` görürsen iş bitmedi · PUT sırasında istisna → `notice` "BELİRSİZ" → `adt_get`
  ile oku · yazma sonrası çekme kaydı silinir (kaynağı push etmeden önce `adt_get`) · canlı davranış DDLS dışında **DOĞRULANMADI**.

---

## Olmayan araçlar (bilinçli)
Transport yaratma/release, paket yaratma, enqueue kilidi silme **araç listesinde yoktur** (Yasak C). Standart obje yaratma/değiştirme/silme
guard'la reddedilir (Yasak A). Standart tabloya veri yazan araç yoktur (Yasak B).
Ayrıca (2026-09-13): mesaj sınıfı **uzun metni** (`documented`) yazma yok · DDLX/DCL kabuğu yok (canlı reçete yok) · SRVB yaratma yok (REST'te bloke) ·
tablo tipi satır tipi düzeltme (PUT) yok · FM RFC-enable yok (SE37) · program/SRVB/DTEL açıklaması değiştirme yok (`adt_set_description` bu tipleri
kanıtla reddeder) · kaynak-sapma (source drift) aracı yok (pull-before-edit kaydı + `adt_get` yeterli sayıldı). Mesaj yazma artık `adt_msgclass_write`'tadır; kaynak reçetenin enqueue kilidi
silen "güvenlik ağı" adımı bilinçli olarak alınmadı (Yasak C).
