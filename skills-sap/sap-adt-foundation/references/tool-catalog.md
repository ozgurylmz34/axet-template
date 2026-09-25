# SAP ADT araç kataloğu (CLI)

> **Otorite `sap_adt_cli.py --list` çıktısıdır.** Bu katalog araçların kaynak imzalarından ve açıklamalarından
> türetildi; CLI'nin argüman adı, varsayılanı ya da sınıfı bundan farklıysa `--list` kazanır ve bu dosya güncellenir.
> Çağrı: `python <TEMPLATE>/skills-sap/sap-adt-foundation/scripts/sap_adt_cli.py <tool> --args-json '{...}'`
> Yazma sınıfı: `--sap-write --scope S0|S1|S2` + (`--reason "<gerekçe>"` | `--intake .axet-code/intake/<id>.md`).

**Sınıf özeti (`--list` ile ölçüldü, 2026-09-13):** okuma 24 (`ping` + `sap_doctor` + 22 `adt_*`, `adt_unit_run` dahil) · yazma 13 · toplam 37.
**2026-09-21 eki (DDIC şeridi, Z38/Z39/Z40):** yazma +3 (`adt_table_create`, `adt_ttyp_create`, `adt_textpool_write`) → yazma 16 · toplam 40 (`--list`, çevrimdışı ölçüldü).
**2026-09-25 eki (Z128):** okuma +1 (`adt_pretty_print`) → okuma 25 · yazma 16 · toplam 41 (`--list`, çevrimdışı ölçüldü).
Profil etiketlerinin tamamı ve yetenek matrisi: `references/profiles.md` (rehber; etiket tablosu kodla test edilir).
`adt_set_description` yalnız `s4_private`'ta açıktır ve transport ister.
`adt_unit_run` `allow_risky_tests=true` verilirse yazma sınıfına geçer (`--list`: `write_when`).
`adt_transport_list` yalnız `ecc`, `s4_private`, `s4_public` profillerinde açıktır (`available_on`); `btp_abap`'ta yoktur.
`adt_screen_generate` yalnız `ecc`, `s4_private` profillerinde açıktır. `adt_msgclass_write`, `adt_table_create`, `adt_ttyp_create`, `adt_textpool_write` yalnız `s4_private`'ta açıktır
(kaynak reçetenin kanıtı yalnız bu profil; diğer profilde `tool_not_available_for_profile`, çıkış 2).
`adt_post_shell` / `adt_push_source` içinde `fugr` ve `func` tipleri yalnız `ecc`, `s4_private`'ta (`--list`: `object_type_available_on`;
diğer profilde `type_not_available_for_profile`, çıkış 2).
Transport zorunlu araçlar (`requires_transport`): `adt_post_shell`, `adt_domain_create`, `adt_dtel_create`, `adt_struct_create`,
`adt_msgclass_write`, `adt_set_description`, `adt_table_create`, `adt_ttyp_create` (`$TMP` paketinde muaf), `adt_textpool_write`, `adt_screen_generate` (`requires_transport_when`: mode WRITE/DELETE). `adt_push_source` `bdef`/`ccimp`/`ccau`/`ccdef`/`ccmac` tiplerinde de transport ister (araç katmanı).
Argümanları dosyadan vermek için `--args-json` yerine `--args-file <json dosyası>`.

**Ortak dönüş okuma kuralları**
- `ok:false` + `error:"guardrail_violation"` (ya da çıkış kodu 2) → SAP'ye gidilmedi. Guard'ı aşmaya çalışma; bildir.
- **Yönlendirme ipuçları (engellemez, 2026-09-13):** yazma sınıfı her yanıtta üst düzey `checklist_hint` (obje tipine göre okunacak
  skill referansları; `status: var|yazılıyor`) ve çıkış 1/2'de `known_errors_hint` (hata kodu + SAP mesaj sınıfı/numarası deseninden
  bilinen-hata maddesi, `sap_message_keys`) bulunabilir. Karar vermez, çıkış kodunu değiştirmez; eşleşme desen tabanlıdır, teşhis değildir.
- **Patinaj kesicisi (2026-09-24):** yazma sınıfı araçta aynı obje aynı hata koduyla art arda 3 kez başarısız olunca sonraki çağrı
  SAP'ye gidilmeden `repeated_failure` (çıkış 2) alır → DUR, kök sebebi kullanıcıyla konuş. Başarısız yanıtta `failure_streak: {code, count, limit}`.
  Başarı, farklı hata kodu ya da 2 saat seriyi sıfırlar; erken sıfırlama kullanıcının (`.axet-code/sap-write-failures.json`). Ayrıntı: `IMPLEMENTATION.md` §23.
- Üç değerli alanlar (`true` / `false` / `null`): `null` = **ÖLÇÜLEMEDİ**, "hayır" ya da "doğrulandı" değildir.
- `client_log` alt katmanın ham satırlarıdır; `exists:false` ya da boş sonuçta önce buna bak.
- Sayı döndüren her araçta limite eşit sonuç = kırpılmış olabilir.

Tip değerleri — CLI tip tablosu (`lib/object_types.py`, kod okuması): `class`, `interface`, `program`, `include`,
`functiongroup`, `function`, `dataelement`, `domain`, `table`, `structure`, `tabletype`, `cds` (`ddls`), `metadataextension`,
`accesscontrol`, `servicedefinition`, `package`; eşanlamlılar (`ddls`, `doma`, `dtel`, `tabl`, `fugr`, `srvd` …) aynı tipe çözülür.
**Tabloda yok ama araçlarda özel yolu olan tipler (2026-09-13):** `bdef` (`adt_get` okur · `adt_post_shell` kabuk · `adt_push_source`
yazar · `adt_activate` aktive eder), `msag` (`adt_get`→`adt_msgclass_read` · `adt_post_shell` kabuk · `adt_msgclass_write` mesaj yazar), `enqu` (`adt_get` yalnız varlık — `include_source:false` · `adt_post_shell` kabuk ·
`adt_activate` aktive eder; kaynak okuma/yazma yok), `srvb` (`adt_activate` + `adt_publish_service`; yaratma/kaynak yok). Sınıf alt-include'ları
`ccimp`/`ccau`/`ccdef`/`ccmac` (`name` = ANA SINIF): `adt_get` dördünü okur, `adt_push_source` dördünü yazar (dördünün yazma yolu canlı ölçüldü — `ccdef`/`ccmac` 2026-09-21, DEV; yanıtta `write_path_measured:true`).
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
  **tip kaynaktan belirlenir (v0.5.1, Z53):** canlı SAP `/ddic/structures/<tablo>` ucundan da 200 + `define table …` döner (ve tersi
  olabilir) → uç 200 verse bile kaynağın ilk `define table|structure` anahtar sözcüğü istenen tiple uyuşmuyorsa yanıt `resolved_type`
  (gerçek tip) · `requested_endpoint` · `resolved_endpoint` · `canonical_endpoint` · `type_probe:"source_keyword"` · `warning:"TIP DUZELTMESI …"`
  taşır; pull kaydı kardeş-uç çözümündeki gibi iki tiple yazılır. `/* … */` ve `//` yorumları aranmadan önce atılır
  (yorumdaki eski `define structure` türü yanıltmaz; tırnak içi korunur). Anahtar sözcük bulunamazsa düzeltme yapılmaz (eski davranış) ·
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
- **Dönüş:** `{ok, name, type, object_url, versions_link_found, versions_link, versions_link_count, count, returned, revisions[{version, versionTitle, author, date, uri}], author_masked}`.
- **Uyarılar:** `versions_link_found:false` + `count:0` = uç sürüm linki sunmadı; "sürüm yok" kanıtı DEĞİL · obje okunamazsa (ör. 406) `revisions_unavailable`,
  feed okunamazsa `revisions_feed_failed` — ikisi de ok:false, boş liste dönmez · DEV dışı tier'da yazarlar (kullanıcı kimliği)
  `***` maskelenir, `acknowledge_risk=true` açar (engellemez).
- **Z132 (2026-09-25, canlı ölçüm DEV; sınıf · include · arayüz):** obje isteği `Accept: */*` (objectstructure → 406 idi, araç bu üç tipte sürüm
  okuyamıyordu); bağlantı `<atom:link …>` ve href GÖRELİ (obje URL'inin altına eklenir); sınıfta ilk bağlantı `includes/definitions`, araç ana kaynağın
  akışını (`includes/main/versions`; include/arayüzde `source/main/versions`) seçer, yoksa ilk bağlantıyı; okunan akış `versions_link`'te. Tanım/implementasyon
  include'larının geçmişi okunmaz. Düzeltme aXet CLI ile DEV'de canlı yeniden ölçüldü (2026-09-25): sınıf 2 kayıt, include 2, arayüz 1; var olmayan ad `not_found`. Ayrıntı: `known-errors-adt.md` K-27.

### `adt_object_structure`
- **Amaç:** obje yapısı (metot, attribute, include … bileşenleri).
- **Argümanlar:** `name` · `object_type="class"` · `version="active"` (`inactive`).
- **Dönüş:** `{ok, name, type, object_url, version, exists, component_count, components[{name,type,uri,description}]}`; 404 → `ok:true, exists:false`;
  ayrıştırılamayan yanıt → `structure_unparseable`.

### `adt_system_info`
- **Amaç:** bağlı sistemin ADT discovery servis kataloğu.
- **Dönüş:** `{ok, service_count, available_services[{title,href}], logon_language, tier, profile, withheld_fields}`. Bağlantı URL'si, client, kullanıcı
  ve sistem kimliği bilinçli olarak **çıktıya konmaz** (`withheld_fields`). Discovery okunamazsa `discovery_unavailable` → `sap_doctor`.

### `adt_pretty_print`
- **Amaç:** obje kaynağını SAP Pretty Printer'dan geçirip biçimlenmiş metni döndürür ya da **yerel dosyaya** yazar. **SAP'de hiçbir şey
  değişmez:** kaydetme, kilit, aktivasyon, transport yok; yanıtta `server_modified:false`. Biçimli metni sisteme almak ayrı adımdır:
  `adt_get` (taban) → dosyayı düzenle → `adt_push_source` (yazma kapısı) → `adt_activate`.
- **Argümanlar:** `name` (sınıf alt-include'unda ANA SINIF) · `object_type="class"` — `class`, `interface`, `program`, `include`,
  `ccimp`/`ccau`/`ccdef`/`ccmac` (eşanlamlılar kabul) · `output_path=null` · `overwrite=false`.
- **Dönüş:** `{ok, name, type, object_url, server_modified:false, changed, changed_line_count, line_count_before, line_count_after,
  diff_preview, output_path, written, notice}`; `output_path` verilmezse biçimli metin `source` alanında döner.
- **Çağrı:** SAP'ye iki istek gider — `GET <kaynak ucu>` (`adt_get` ile aynı uç, sürüm verilmez = son sürüm) ve
  `POST /sap/bc/adt/abapsource/prettyprinter` (gövde = kaynak, parametre yok). Satır sonları LF'e çevrilir.
- **Yerel dosya kuralları:** `output_path` proje kökü içinde (göreli yol köke göre), `.abap` uzantılı ve `.axet-code/` dışında olmalı; aksi
  `invalid_argument` (çıkış 3). Böylece `.conn_adt`, `sap-project.json`, `.rules.md` ya da kapı kayıtları bu araçla ezilemez. Var olan dosya
  `overwrite=false` iken `output_exists` (çıkış 1). Yol ve tip denetimleri SAP'ye gitmeden yapılır.
- **Uyarılar:** pull kaydı (`sap-pull-state.json`) YAZMAZ, push'tan önce taban için `adt_get` şart · hata kodları ayrı: `not_found` (404),
  `sap_error` (kaynak okunamadı), `pretty_print_failed` (biçimleyici HTTP hatası), `pretty_print_empty` (boş metin — dosya yazılmaz, push
  edilseydi kaynağı silerdi), `source_empty` · desteklenmeyen tip (`func`, CDS/DDIC/BDEF …) `unsupported_type`, çıkış 3 · `changed:false`
  yalnız "bu servis, bu ayarlarla fark üretmedi" demektir. Servis çağrısı biçim ayarı (büyük/küçük harf, girinti) göndermez; hangi ayarla
  biçimlediği (oturum kullanıcısının ADT biçim ayarı olduğu varsayılıyor) canlı **ÖLÇÜLMEDİ**. ATC'nin Pretty Print kontrolü ATC varyantının
  parametreleriyle biçimler: iki ayar farklıysa sonuç ATC'ninkiyle uyuşmayabilir. Sınıf `class` tipinde yalnız ana kaynak
  (`/source/main`) biçimlenir, alt-include'lar ayrı çağrılır. Kullanım: `sap-classic-abap` → `references/classes.md` §7.1.

## Yazma sınıfı
Hepsi: `install.py --sap-write` (kullanıcı çalıştırır) · tier DEV · `--sap-write` · kapsam beyanı. Guard'lar ağdan önce.

### `adt_post_shell`
- **Amaç:** boş Z obje kabuğu (inaktif, kaynaksız).
- **Argümanlar:** `object_type` · `name` (Z/Y; lock object E+Z/Y) · `package` (mevcut) · `transport` · `description` (`master_language`'de, **boş olamaz** → `ADR_0005_D`) ·
  `extra` (yalnız aşağıdaki tiplerde; başka tipte ya da tanınmayan alanla → `invalid_argument`, çıkış 3).
- **Desteklenen tipler (çevrimdışı sahte istemciyle test edildi; canlı ÖLÇÜLEN 2026-09-22, DEV `$TMP`: `class`, `ddls`, `bdef` (Z35 RAP ölçümü), `ddlx`, `dcls` (Z42) — kabuk → push → aktivasyon → silme; diğer tipler canlı DOĞRULANMADI):**

  | Tip | Yol | `extra` | Sonraki adım |
  |---|---|---|---|
  | `class`, `interface`, `program`/`prog`, `include` | genel yaratıcı (değişmedi) | — | `adt_get` → `adt_push_source` → `adt_activate` |
  | `ddls` | yalnız-metadata kabuk (kaynak gövdeye konmaz) | — | `adt_get` → `adt_push_source(ddls)` → `adt_activate` → readback |
  | `srvd` | `srvdSourceType="S"` kabuk | — | `adt_get` → `adt_push_source(srvd)` → `adt_activate(srvd)` |
  | `bdef` | "blues" kabuk; **ad = kök entity adı** (SAP zorunlu, araç doğrulayamaz) | — | `adt_get` → `adt_push_source(bdef)` → `adt_activate(<kök ddls>, also=[bdef, class])` |
  | `fugr` | fonksiyon grubu | — | `adt_activate(fugr)` |
  | `func` | FM kabuğu (grup içinde) | `{"function_group":"<Z/Y FUGR>"}` zorunlu | `adt_get(func)` → `adt_push_source(func)`; RFC-enable SE37'de |
  | `msag` | mesaj sınıfı kabuğu (stateless POST) | — | `adt_msgclass_read` → `adt_msgclass_write` |
  | `ddlx` (`metadataextension`) | metadata extension; **canlı ölçüldü 2026-09-22** (DEV, `$TMP`) — Content-Type `application/vnd.sap.adt.ddic.ddlx.v1+xml` (ADT discovery; eski `ddlxSource+xml` → 415) | — | `adt_get(ddlx)` → `adt_push_source(ddlx)` → `adt_activate(ddlx)`; hedef CDS `@Metadata.allowExtensions: true` |
  | `dcls` (`dcl`, `accesscontrol`) | erişim kontrolü (rol); **canlı ölçüldü 2026-09-22** — `application/vnd.sap.adt.dclSource+xml` | — | `adt_get(dcls)` → `adt_push_source(dcls)` → `adt_activate(dcls)`; süzmenin kendisini tüketicide ayrıca test et |
  | `enqu` | kilit objesi | `{"primary_table", "lock_fields":["MANDT",…], "lock_mode":"E|S|X", "allow_rfc":false}` | `adt_activate(object_type="enqu")` |
  | `ttyp` | tablo tipi | `{"row_type":"<yapı/DTEL>"}` | `adt_activate(ttyp)` → `DD40L.ROWTYPE` dolu mu (`adt_sql_query`) |

  **Desteklenmez (`unsupported_type`, çıkış 3, gerekçe mesajda):** `srvb` (REST'te bloke) ·
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
- **Dönüş:** `{ok, name, type, result, readback_verified, readback_notice?, syntax_precheck?, syntax_precheck_notice?, syntax_errors?, reviewer?, post_check?, removed_lines_warning?, warning?}`.
  `removed_lines_warning: {removed, added, sample}` (2026-09-24): canlıda olup yeni kaynakta olmayan satırlar — yazma DURMAZ; yerel kopya
  `adt_get` çıktısından türemediyse bu satırlar kaybolur → satırları kullanıcıya göster, onaysız tekrar yazma (SKILL §2).
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
  **Kesin Yasak A (Z104):** kaynak standart objeyi genişletiyorsa (`extend type|view [entity]|custom|abstract entity <std>`, `annotate view|entity <std>`, BDEF `extension` — `using interface <Z…>` yoksa hedef kanıtlanamaz) → `ADR_0005_A` (çıkış 2, mesajda satır + hedef; kaynak taranamazsa `std_ext_scan_unavailable`; `adt_struct_create`'te yazılacak DDL de taranır) ·
  **pull-before-edit:** önce `adt_get` şart — kayıt yok `pull_before_edit_missing` (2) · çekildikten sonra SAP'de değişmiş `source_changed_since_pull` (2) ·
  canlı okuma başarısız `pull_live_read_failed` (1) · durum dosyası bozuk `pull_state_unreadable` (2); başarılı push kaydı günceller (`pull_state: guncellendi`).
- **Tipe özel yazma (2026-09-13; çevrimdışı test edildi, canlı DOĞRULANMADI):**
  - `bdef`: LOCK → PUT (If-Match YOK) → UNLOCK → readback (v0.5.1: UNLOCK yanıtı 200/204 değilse ya da istisnaysa `unlock_ok:false` + `unlock_warning` — SM12, AI kilit silmez; önceden durum kodu okunmuyordu); **aktive ETMEZ** (`activated:false` + `activation_note`) → `adt_activate(<kök ddls>, also=[bdef, behavior class])`. Transport zorunlu. Yasak B taraması uygulanmaz (ABAP değil). Reviewer `rap_bdef_creation`.
  - `ccimp` / `ccau`: `name` = **ana sınıf** (`{"name":"ZBP_X","object_type":"ccimp",…}`); include yoksa önce iskelet (POST) sonra PUT; bayt readback; ana sınıf aktive edilir — RAP behavior pool'da BDEF inaktifse aktivasyon düşer (`push_failed` + `activation_note`) → `also` ile birlikte aktive et. Transport zorunlu. Yasak B taranır. Reviewer `class_push`. `ccdef` / `ccmac` (2026-09-21, Z41): aynı yol (`push_class_include` → `definitions` / `macros` segmenti); segment adları GET ile ölçüldü; **yazma yolu canlı ÖLÇÜLDÜ (2026-09-21, DEV)**: PUT `/includes/definitions` ve `/includes/macros` → sınıf aktivasyonu → aktif readback eşit (kontrol grubu aynı turda ccimp) → yanıtta `write_path_measured:true` (dördünde de); bayt readback her yazımda koşar.
  - `func`: fonksiyon grubu canlı okumadan çözülür (`function_group` yanıtta) ve **Z/Y olmalı** (değilse `ADR_0005_A`, yazma yok); sıkı kilit PUT + ayrı aktivasyon (v0.5.1: UNLOCK sonucu yanıtta — `unlock_ok` + gerekirse `unlock_warning`; PUT hatasında da istisnaya taşınır; önceden UNLOCK hatası `except: pass` ile yutuluyordu); aktivasyon düşerse `push_failed` + `activation_errors` (kaynak yüklendi, kayıt güncellendi). İmza satır-içi ABAP (`*"` blok 400 verir, K-15). Yasak B taranır. Reviewer yok (SKIP görünür).
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
  **`bdef` (v0.5.2, Z35 canlı bulgusu):** genel tip tablosu BDEF'i tanımadığı için eskiden `Unsupported object type: bdef` dönüyordu (kök DDLS silinse de BDEF kalıyordu); artık kilit → DELETE → kilit aç BDEF ucuna uygulanır, yokluk BDEF kaynak ucundan (404) doğrulanır (`delete_verified`). Canlı ölçüldü 2026-09-22 (DEV, `$TMP`): `ddlx`/`dcls`/`ddls` ile birlikte dört silmenin dördü `delete_verified: true`, TADIR 5 → 0.

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
- **Varlık ön kontrolü + üzerine yazma kapısı (v0.5.1, Z51 ⓐ / Z52):** ön kontrol ÜÇ DEĞERLİDİR (`adt_get(doma)` ile): var → `already_exists` ·
  ölçülemedi (5xx/403/istisna/ağ — 404 dışı her şey) → `exists_unmeasured`, **POST atılmaz** · 404 → yaratılır; `steps.pre_check` =
  `checked_found` | `checked_absent` | `unavailable:<sebep>`. Ön kontrol "yok" deyip SAP POST'u 400/405 `AlreadyExists` ile reddederse
  kütüphane artık başarı DÖNMEZ (`SAPObjectExistsError`) → `already_exists`, **aktivasyon yapılmaz**. POST'tan önce 5xx/zaman aşımı/bağlantı hatası yüzünden
  sessiz yeniden deneme olduysa (kütüphanenin `ÖNCEKİ DENEME` eki; yedek: `[RETRY]` 5xx/zaman aşımı/bağlantı hatası satırı) → `already_exists_after_retry` + `own_shell_possible:true`: obje büyük olasılıkla önceki
  denemenin yarattığı kabuktur (başkasının olduğu kanıtlanmadı) → `adt_get` ile bak, kör tekrar yok. Önceden: ön kontrol hata/None'da "yok"
  diyordu ve POST 405 başarı sayılıp aktivasyon çağrılıyordu (aynı adlı ikinci çağrı var olan objeyi "yaratıldı" diye raporlayabiliyordu).
  **Kodlar:** `preflight_blocker` · `reviewer_blocker` · `already_exists` · `already_exists_after_retry` · `exists_unmeasured` · yaratma
  reddinde `_create_hata_sinifi` kodu (ör. `create_failed`) · aktivasyon/doğrulama düşerse ayrı kod YOK: `ok:false` + `steps.activate` / `steps.verify`.

### `adt_dtel_create`
- **Amaç:** data element yarat + aktive et + doğrula.
- **Argümanlar:** `name` · `domain_name` (Z domain ya da `CHAR1` gibi standart tip) · `description` · `package` · `transport` ·
  `short_label` · `medium_label` · `long_label` · `heading_label` (4'ü de dolu, `master_language`'de) · `artifact_path`.
- **Uyarılar:** DTEL adı kullanıcı onaylıdır (standarda uygun öneri + canlı kontrol + açık onay — `%sap-dev` §6); metinler spesifikasyondan (tahmin yasak) ·
  ağdan önce tier, Z/Y, transport, açıklama dolu, 4 etiket dolu ve **etiket uzunlukları ≤ 10/20/40/55** (kısa/orta/uzun/başlık; kenar boşluğu
  kırpılıp karakter sayılır) denetlenir → aşım `ADR_0005_D` (çıkış 2, mesaj `short=11>10` biçiminde). Sınırlar DTEL CSV validator'ıyla aynı
  tablodan (2026-09-13; önceden artefaktsız çağrıda uzunluk denetlenmiyordu) · kullanılan domain'in varlığı ağdan önce **denetlenmez** (açık kalem) ·
  **varlık/üzerine yazma (v0.5.1):** `adt_domain_create` ile aynı üç değerli ön kontrol (`adt_get(dtel)`) ve aynı kodlar — `already_exists` ·
  `exists_unmeasured` (POST yok) · `already_exists_after_retry` (5xx/zaman aşımı/bağlantı hatası yeniden denemesinden sonra `AlreadyExists`) — aktivasyon hiçbirinde yapılmaz.

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
  **Doğrulama adresi (düzeltme 2026-09-21, canlı bulgu):** varlık sondası, metadata doğrulaması (`steps.verify.endpoint: ddic/structures`)
  ve `content_verify` yapıyı `/ddic/structures/` ucundan okur. Önceden `tabl` → `/ddic/tables/` ucuna soruluyordu: canlıda yapı AKTİF
  yaratıldığı hâlde (DD02L INTTAB/A, DD03L 2 satır) araç `ok:false` + `verify.reason: metadata_not_found` dönüyordu ve ön kontrol mevcut
  yapıyı "yok" görüyordu (kusur ilk sürümden beri `main`'de). Aktivasyon adresi değişmedi (`tabl` — canlıda çalıştı). Yanıttaki `type` hâlâ `tabl`.
  ⚠ **Düzeltme sonrası `/ddic/structures/` yolu (varlık sondası, metadata doğrulaması, `content_verify`) canlıda henüz ÖLÇÜLMEDİ** — canlı kanıt
  yalnız "yapı aktifti, eski `tables` ucu bulamadı" yönündedir; yeni yolun `ok:true` verdiği sahte istemci testleriyle gösterildi.
  **Üzerine yazma kapısı (2026-09-21, bug gate):** ön kontrol ÜÇ DEĞERLİDİR — yapı ucu (`/ddic/structures/<ad>/source/main`) 200 ya da 404 sonrası
  kardeş `/ddic/tables/` ucu 200 → `already_exists` (`existing_kind: structure|table`; aynı adlı şeffaf tablo da çakışmadır) · uç ölçülemedi
  (5xx/403/istisna/ağ; kardeş uç ölçülemedi) → `exists_unmeasured`, **POST atılmaz** · iki uç da 404 → yaratılır. Ön kontrol "yok" deyip SAP POST'u
  400/405 `AlreadyExists` ile reddederse kütüphane artık kaynağı PUT ETMEZ (`SAPObjectExistsError`) → `already_exists`, kilit/PUT/aktivasyon yok.
  Önceden: ön kontrol hata/None'da "yok" diyordu ve POST 405'ten sonra LOCK → PUT → aktivasyon yapılıyordu ⇒ mevcut yapı yeni alanlarla ezilebiliyordu
  (15f9716'dan beri tüm sürümlerde). `steps.pre_check` = `checked_found` | `checked_absent` | `unavailable:<sebep>`.
  **Tablo/yapı ayrımı (v0.5.1, Z53, canlı bulgu):** canlı SAP var olan bir TABLOYU `/ddic/structures/` ucundan da 200 + `define table …` ile
  döndürür → önceden `existing_kind: structure` deniyordu. Artık tür kaynağın ilk `define table|structure` anahtar sözcüğünden belirlenir
  (`existing_kind: table`, mesaj "TABLO"). **Yeniden deneme sonrası çakışma (v0.5.1, Z52):** POST 5xx/zaman aşımı/bağlantı hatası → kütüphanenin sessiz
  yeniden denemesi → 400/405 `AlreadyExists` ise `already_exists_after_retry` + `own_shell_possible:true` (kabuğu büyük olasılıkla önceki deneme
  yarattı; `adt_get(structure)` ile bak). **Paket (v0.5.1, Z50 ⓕ):** boş ya da yalnız boşluk `package` → `validation_error`, SAP'ye gidilmez.
  **Hatalar (başarısız yanıtta `error`, 2026-09-21):** `validation_error` · `reviewer_blocker` · `already_exists` · `already_exists_after_retry` · `exists_unmeasured` · `description_too_long` · `create_failed` · `activation_failed` ·
  `verify_failed` (metadata okunamadı ya da sürüm `active` değil) · `content_verify_failed` (yer tutucu kabuk / alan yok / kaynak okunamadı) ·
  `post_check_blocker`. Obje hiçbir durumda silinmez.
  **Satır sonu yasağı (2026-09-15):** `description` ile her alanın `description`/`name`/`type` değeri tek satır olmalı — CR, LF, U+2028, U+2029 ya da U+0085 varsa ağa ve reviewer'a gitmeden `validation_error` (mesaj yeri ve karakter kodunu söyler, ör. `fields[0].description … U+000A`); aynı kural render'da `ValueError` → gate'te `reviewer_blocker` (`ddl_render_hatasi`).

### `adt_msgclass_write` (mesaj sınıfına mesaj yazma — YAZMA)
- **Amaç:** mevcut Z/Y mesaj sınıfına mesaj eklemek; açık izinle mevcut mesajı değiştirmek ya da silmek. Profil: yalnız `s4_private`.
- **Sıra:** kabuk yoksa `adt_post_shell(object_type="msag")` → `adt_msgclass_read` (canlı liste + pull kaydı) → nihai listeyi kullanıcıya göster → `adt_msgclass_write`.
- **Argümanlar:** `name` (Z/Y) · `transport` (zorunlu) · `messages=[{"no":"001","text":"<master_language metni, ≤ 73>","selfexplanatory":false}]` ·
  `delete_numbers=["005"]` · `allow_overwrite=false` · `package` (yalnız canlı okumada paket yoksa; farklıysa red).
- **Semantik:** araç önce canlı listeyi okur ve tam gövdeyi **birleştirerek** kurar: yeni numara eklenir, verilmeyen mevcut mesajlar
  **korunur** (`documented` bayrağı dahil). Mevcut numaraya farklı metin/bayrak → `allow_overwrite=true` yoksa `msgclass_overwrite_not_allowed` (çıkış 2,
  `plan.overwritten` önce/sonra). Değişiklik yoksa kilit alınmaz (`changed:false`).
- **Silme (Z113):** ⛔ SAP tam PUT'tan **çıkarılan mesajı SİLMEZ** (kaynak ölçümü 229→229 no-op). Silme yalnız `delete_numbers` ile ve **ayrı çağrıda**
  (`messages` ile birlikte → `invalid_argument`): gövdeye kalanlar canlı öznitelikleriyle + `<mc:deletedmessages mc:msgno="NNN"/>` yazılır, gövde öz-denetimi
  (bozuksa `delete_body_selfcheck_failed`, kilit yok), LOCK → **kilit altında canlı yeniden okunur** (farklı → `source_changed_since_pull`, okunamadı →
  `pull_live_read_failed`, ikisinde `phase:"under_lock"`, PUT YOK) → PUT → UNLOCK → **önce/sonra kapısı** `delete_gate`. Korumalar (ağ/kilit öncesi): canlıda
  olmayan numara ya da tüm sınıf → `invalid_argument`; oturum (logon) dili ≠ sınıfın master dili → `ADR_0005_D` (yarım silme riski).
  Canlı aXet ölçümü YOK (`sap-cds-ddic/references/message-class.md` §3.7).
- **Dönüş:** `{ok, name, changed, plan{added, overwritten[{no,before,after}], deleted[{no,text}], unchanged, preserved_count}, message_count_before,
  message_count_after, readback_verified, pull_state, http{lock,put,unlock}, unlock_warning?, delete_gate?}` — `delete_gate` yalnız silmede:
  `{ok: true|false|null, errors, gone, not_deleted, unexpectedly_gone, appeared, changed, scope_checked, scope_not_checked}`; `ok:null` = **ÖLÇÜLEMEDİ**
  (silme gerçekleşmiş olabilir; `note` okunur). `scope_not_checked` (T100 çeviri satırları, T100U/DOKHL, E071) kullanıcıya aktarılır.
- **Kilit:** kendi aldığı kilidi kendisi bırakır; enqueue kilidi **silmez**. Kilit alınamazsa `lock_conflict` (403/409/423 ya da gövdede kilit izi) /
  `lock_failed` (çıkış 1) → kullanıcı SM12'de kendi kilidini kontrol eder, SE91/ADT'de açık sınıfı kapatır; sonra `adt_msgclass_read` → tekrar.
  `unlock_warning` görürsen aynı yönlendirmeyi kullanıcıya ilet.
- **Doğrulama:** yazmadan sonra canlı liste beklenen tam listeyle kıyaslanır: fark → `readback_mismatch` (`ok:false`, `readback_diff`), okunamadı →
  `readback_failed`; ikisinde de pull kaydı silinir (yeniden oku).
- **Red kodları:** `ADR_0005_A` (standart sınıf) · `ADR_0005_C` (transport) · `ADR_0005_D` (boş metin; sınıfın master dili ≠ `master_language`;
  silmede oturum dili ≠ master dil) ·
  `invalid_argument` (numara 3 haneli metin değil, metin > 73, tekrar eden numara, yaz+sil aynı çağrıda, silinecek numara canlıda yok, tüm sınıfı silme,
  `documented` alanı, boş istek — çıkış 3) · `delete_body_selfcheck_failed` (1) ·
  `pull_before_edit_missing` / `source_changed_since_pull` / `pull_state_unreadable` (2) · `pull_live_read_failed` · `master_language_unresolved` ·
  `msgclass_live_incomplete` (canlıda paket/açıklama/sorumlu yok; tahmin edilmez) · `push_failed` (1).
- **Uyarı:** canlı davranış **DOĞRULANMADI** (çevrimdışı sahte istemciyle test edildi). Uzun metin (`documented`) bu araçla yazılmaz.

> **Kilit yanıtında CORRNR (canlı 2026-09-21, DEV, `$TMP`):** tablo, yapı, program, metin havuzu ve sınıf kilitlerinin HİÇBİRİ `CORRNR` döndürmedi
> (`[INFO] SAP did not return CORRNR in lock response`) — `$TMP`'de bu beklenen; etkin transport verilen değere düşer, transport ataması doğrulanamaz.

### `adt_table_create` (Z şeffaf tablo — YAZMA, 2026-09-21)
- **Amaç:** Z/Y şeffaf tablo (TABL/DT) yarat + DDL'i yaz + aktive et + aktif kaynağı geri oku. Profil: yalnız `s4_private`.
- **Ön kapı (araçta değil, skill akışında):** ad, alanlar, DTEL'ler ve anahtar kullanıcıya gösterilir, AÇIK onay alınır (`sap-cds-ddic` → `tables-structures.md` §3).
- **Argümanlar:** `name` (≤ 16) · `description` · `fields=[{"name":"MANDT","type":"mandt","key":true}, {"name":"BELGE","type":"<DTEL>","key":true}, {"name":"MIKTAR","type":"<DTEL>","unit_field":"BIRIM","unit_kind":"quantity"}, …]` ·
  `package` · `transport` (**`$TMP` dahil zorunlu**) · `delivery_class="A"` · `data_maintenance="RESTRICTED"`.
- **Akış:** ağsız ön kontrol (T1 ad ≤ 16 · T2 ilk alan `MANDT`/`mandt`/anahtar · T3 alan biçimi · T4 tekil ad · T5/T6 teslimat sınıfı / veri bakımı · T7 birim referansı ·
  T8 satır sonu · T9 `key` bool) → DDL render (`#NOT_EXTENSIBLE`, anahtarlarda `not null`, nitelikli `'tablo.alan'` birim/para referansı) → reviewer `table_creation` **yazılacak DDL'in kendisi** üzerinde →
  varlık sondası (ölçülemezse `exists_unmeasured`, yaratma yok; tablo ucu 404 verip kardeş `/ddic/structures/` ucu ölçülemezse de `exists_unmeasured` — aynı adlı yapı orada olabilir, `pre_check: unavailable:sibling_…`) → kabuk POST (**DDL'siz**) → aynı stateful oturumda LOCK → PUT `source/main` (**If-Match yok**; corrNr = kilit yanıtındaki CORRNR) → UNLOCK (finally) →
  aktivasyon + `version=active` → aktif DDL readback (alan/anahtar dizisi).
- **Dönüş:** `{ok, name, type:'table', ddl, fields_count, reviewer, steps:{pre_flight, reviewer, pre_check, create, activate, verify, readback}, unlock_warning?}` — `steps.create.unlock_ok:false` (UNLOCK yanıtı 200/204 değil) → `unlock_warning`; `ok`'u bozmaz, kullanıcıya ilet (SM12; AI kilit silmez).
- **Hatalar:** `preflight_blocker` · `reviewer_blocker` · `already_exists` · `exists_unmeasured` · `validation_error` (ad/paket kütüphane doğrulaması; boş ya da yalnız boşluk `package` v0.5.1'den beri araç kapısında — SAP'ye gidilmedi) · `create_failed` · **`partial_shell`** (kabuk VAR, DDL yazılamadı — kilit/PUT reddi, kilit öncesi CSRF/ağ istisnası ya da yabancı transport; silinmez, kullanıcı karar verir; **v0.5.1:** LOCK ya da PUT isteği gönderildikten sonra HTTP yanıtı yerine ağ istisnası geldiyse `outcome_uncertain: "lock"|"put"` + mesaj "kilidin alınıp alınmadığı / DDL'in yazılıp yazılmadığı BELİRSİZ" — `put` → `adt_get(tabl)` ile bak, `lock` → SM12) ·
  `activation_failed` · `verify_failed` (aktive oldu ama metadata `active` doğrulanamadı) · `readback_mismatch` (`default_shell_client_field` = varsayılan `client : abap.clnt` kabuğu duruyor, DDL sessizce kaybolmuş).
- **Kapsam:** mevcut tabloyu DEĞİŞTİRMEZ. Canlı 2026-09-21 (DEV): yaratma `ok:true` — aktif, aktif DDL readback 3/3 alan. Ölçülmeyen dallar
  (`partial_shell`, yabancı transport, `exists_unmeasured`, UNLOCK hatası) yalnız çevrimdışı sahte istemci testleriyle gösterildi. `adt_push_source(tabl)` ile DDL yazma kaynak çekirdekte "invalid lock handle" verdi — bu araç kilidi kendi içinde tutar.

### `adt_ttyp_create` (tablo tipi — YAZMA, 2026-09-21)
- **Amaç:** DDIC tablo tipi (TTYP) yarat + aktive et + **iki kanallı** doğrula; satır tipi boş ya da tanım istenenden farklı kaldıysa bir kez düzelt. Profil: yalnız `s4_private`. Ayrıntı: `sap-cds-ddic/references/table-types.md`.
- **Argümanlar:** `name` · `description` · `package` · `transport` (`$TMP`'de muaf) · satır tipi **tam olarak biri**: `row_type` (yapı/tablo/DTEL) ya da
  `builtin={"data_type":"CHAR|NUMC","length":N}` · `{"data_type":"DEC","length":N,"decimals":D}` · `{"data_type":"STRING|INT4|DATS"}` ·
  `access_type="standard|sorted|hashed"` · `key_definition="standard|rowType|keyComponents"` · `key_kind="nonUnique|unique"` (varsayılan: hashed → unique, diğerleri nonUnique) · `key_components=[..]`.
- **Desteklenmeyen:** aralık tablosu, referans satır, iç içe tablo tipi, boş/genel anahtar, ikincil anahtar → `preflight_blocker`.
- **Akış:** ön kontrol → varlık sondası → POST `/ddic/tabletypes` (`application/vnd.sap.adt.tabletype.v1+xml`, corrNr sorgu parametresi) → aktivasyon → readback: ADT XML (`rowType/typeName`|`dataType`, erişim, anahtar) + DD40L (ROWTYPE/DATATYPE, ACCESSMODE, KEYDEF, KEYKIND) →
  **iki kanal da boş YA DA tanım istenenden farklı** → aynı XML (istenen tam tanım) ile If-Match PUT → yeniden aktivasyon → yeniden iki kanal (tek sefer; `steps.repair.trigger` = `bos`|`uyumsuz`);
  onarım sonrası nihai `ok` ikinci aktivasyonun doğrulamasından gelir (`steps.verify_2`). Reviewer zinciri yok (`reviewer.verdict:"SKIP"`); doğrulama canlı readback'tir.
- **Hatalar:** `preflight_blocker` · `validation_error` (v0.5.1: boş ya da yalnız boşluk `package`; SAP'ye gidilmedi) · `already_exists` · `exists_unmeasured` · `create_uncertain` (POST istisna verdi — `exists_after` sondasına bak, kör tekrar yok) · `create_failed` · `activation_failed` ·
  `row_type_empty_repair_failed` (boş satır için düzeltme PUT'u düştü ya da ETag yok) · `readback_mismatch_repair_failed` (farklı tanım için düzeltme PUT'u düştü ya da ETag yok) — ikisinde de v0.5.1: PUT'a HTTP yanıtı yerine ağ istisnası geldiyse `steps.repair.outcome_uncertain:true` + mesaj "yazıldığı BELİRSİZ … `adt_get(ttyp)` ile bak" · `activation_failed_after_repair` ·
  **`row_type_empty_after_repair`** (FAIL — asla OK) · `readback_channels_disagree` (biri dolu biri boş) · `readback_unmeasured` (DD40L/XML okunamadı; ölçülemedi ≠ doğru) ·
  `readback_mismatch` (erişim/anahtar/satır tipi/ilkel uzunluk-ondalık farklı — onarım denendiyse mesaj bunu söyler) · `verify_failed` (readback doğru ama metadata `active` doğrulanamadı).
- **Kapsam (canlı 2026-09-21, DEV):** yapı satırlı üç kombinasyon (standart · sıralı + anahtar bileşenli + tekil) canlıda `ok:true` — üçünde de POST satır tanımını
  düşürdü (`bos`), If-Match PUT onarımı erişim/anahtar dahil tanımı kabul ettirdi. İlkel satır (CHAR 10, DEC 15,2) canlıda POST sonrası SAP varsayılanı
  `CHAR · 000001` kaldı; onarım o sürümde `uyumsuz` için denenmiyordu → düzeltildi, **ilkel satırda PUT onarımı canlıda henüz ÖLÇÜLMEDİ**.

### `adt_textpool_write` (klasik program metin havuzu — YAZMA, 2026-09-21)
- **Amaç:** Z/Y programın metin sembollerini (`TEXT-xxx`) ve seçim metinlerini yazmak; `adt_push_source` bunları TAŞIMAZ (yalnız `source/main`). Profil: yalnız `s4_private`.
- **Argümanlar:** `name` · `transport` (zorunlu) · `symbols=[{"key":"B01","text":"…","max_length"?:N}]` · `selections=[{"name":"P_BUKRS","text":"…"}]` · `allow_remove=false`.
- **Akış:** ağsız ön kontrol (sembol 3 karakter · seçim adı ≤ 8 · metin boş değil · metin ≤ `max_length` → aksi SAP DS512) → her alt kaynağı canlı oku (ETag;
  canlıda olup girdide olmayan giriş SİLİNECEKSE `allow_remove=true` olmadan `would_remove_entries`, yazma yok) → metin öğeleri kaynağını kilitle (program değil) →
  PUT (CRLF, giriş başına `@MaxLength`, boş satır ayraç, sonda satır sonu yok; If-Match + lockHandle + corrNr) → UNLOCK → PROG/P + **açık PROG/PX** aktivasyonu →
  PX sonrası bağımsız worklist sondası (`steps.activation_final`) → `?version=active` readback (eksik / farklı / `=?` / `allow_remove` ile silinmesi onaylanan giriş hâlâ duruyor (`remove_not_applied`) → `readback_mismatch`).
- **`steps.activate_prog`:** program zaten aktifse SAP yalnız generation koşar ve metin havuzunu terfi ettirmez (canlı 2026-09-21: her çağrıda) —
  bu BEKLENEN durumdur: `outcome:"generation_only"`, `ok` = `activation_final.ok`. Gövdede gerçek hata varsa `outcome:"failed"` + `errors`.
  `ok` = aktif readback doğru **ve** PX sonrası worklist'te program/metin havuzu kalmadı; sonda ölçülemezse yalnız readback + `activation_notice`
  (program aktivasyonu gerçek hata verdiyse ölçülemeyen sonda başarı sayılmaz → `activation_unverified`).
  `written` yalnız PUT'u başarılı alt kaynakları listeler (yazılmadıysa `[]`).
- **Hatalar:** `preflight_blocker` · `not_found` · `read_failed` · `would_remove_entries` · `lock_failed` (gerçek tutamaç yoksa yazmaz) · `put_failed` · `readback_mismatch` ·
  (v0.5.1: LOCK ya da PUT isteğine HTTP yanıtı yerine ağ istisnası geldiyse `lock_failed`/`put_failed` + `outcome_uncertain: "lock"|"put"`,
  `steps.put[<alt>] = {ok:null, outcome_uncertain:true}` ve mesaj "kilit durumu / yazıldığı BELİRSİZ" — HTTP ret kodlu yanıtlar eskisi gibi) ·
  `activation_incomplete` (metinler aktif ama PX sonrası worklist program/metin havuzunu hâlâ inaktif gösteriyor) ·
  `activation_unverified` (program aktivasyonu gerçek hata verdi — `activate_prog.outcome:"failed"` — ve PX sonrası worklist sondası ölçülemedi;
  metinler aktif görünse de `ok:false`, mesaj program hatasını taşır) · `unlock_warning`.
- **Kapsam:** liste başlıkları (headings) yazılmaz (biçim belgelenmedi). Canlı 2026-09-21 (DEV): yazma + PX terfisi + aktif readback `ok:true`, `would_remove_entries` yazmadan döndü;
  `activation_final` ve `generation_only` sınıflaması bu turda eklendi — canlıda henüz ÖLÇÜLMEDİ.

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
Ayrıca (2026-09-13): mesaj sınıfı **uzun metni** (`documented`) yazma yok · ~~DDLX/DCL kabuğu yok~~ (v0.5.2: var, canlı ölçüldü) · SRVB yaratma yok (REST'te bloke) ·
tablo tipi satır tipi düzeltme (PUT) yok · FM RFC-enable yok (SE37) · program/SRVB/DTEL açıklaması değiştirme yok (`adt_set_description` bu tipleri
kanıtla reddeder) · kaynak-sapma (source drift) aracı yok (pull-before-edit kaydı + `adt_get` yeterli sayıldı). Mesaj yazma artık `adt_msgclass_write`'tadır; kaynak reçetenin enqueue kilidi
silen "güvenlik ağı" adımı bilinçli olarak alınmadı (Yasak C).
2026-09-21 güncellemesi: tablo tipi satır tipi düzeltmesi artık `adt_ttyp_create` içindedir (yalnız kendi yarattığı tipte, bir kez); mevcut tablo tipini
değiştiren araç hâlâ yok. Z tablo kabuğu `adt_table_create` ile gelir. Metin havuzu başlıkları (headings) yazma yok.
