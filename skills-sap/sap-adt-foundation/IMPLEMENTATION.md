# sap-adt-foundation — teknik not

SAP ADT araçlarının MCP'siz, tek komut satırı giriş noktası (`scripts/sap_adt_cli.py`), yazma kapısı
(`scripts/sapadt/gate.py`) ve çevrimdışı testleri. Kaynak: kaynak metodoloji deposu (`mcp_servers/sap_adt` + `scripts/`).
Çalışma zamanında kaynak depoya hiçbir bağımlılık yoktur; gereken kod kopyalanıp uyarlandı.

## 1. Ne kopyalandı (kaynak → hedef)

| Kaynak (kaynak metodoloji) | Hedef (`scripts/sapadt/`) | Not |
|---|---|---|
| `mcp_servers/sap_adt/_app.py` | `_app.py` | **Yeniden yazıldı**: MCP yok; `profil_tool` yalnız `REGISTRY`e yazar |
| `mcp_servers/sap_adt/server.py` | `tools/meta.py` (`ping`) | Sunucu döngüsü taşınmadı |
| `mcp_servers/sap_adt/_conn.py` | `_conn.py` | Proje-dizini bazlı; env tier fallback'i kaldırıldı (§3) |
| `mcp_servers/sap_adt/_profile.py` | `_profile.py` | `project.yaml` → `sap-project.json` |
| `mcp_servers/sap_adt/_reviewer.py` | `_reviewer.py` | Zincir yolu paket içi; alt süreç cwd/env = proje |
| `mcp_servers/sap_adt/guardrails.py`, `data_guard.py`, `_bos_sonuc.py` | aynı adlar | Mantık aynen; yalnız mesaj/yol metinleri |
| `mcp_servers/sap_adt/tools/{atom,composite,query}.py` | `tools/` | import yolları, `verify`, client/dil başlıkları, 2 kusur düzeltmesi (§4) |
| `scripts/sap_adt_lib.py`, `sap_client.py`, `object_types.py`, `auth/*` | `lib/` | Düz modüller; `sapadt` import'unda `lib/` `sys.path`'e eklenir |
| `scripts/create_rap_service.py` | `lib/rap_service.py` | **Kesit**: yalnız `csrf`, `activate_and_verify`, `publish_xml`, `publish_hukmu` (+yardımcılar) |
| `scripts/source_drift.py` | `lib/source_normalize.py` | Yalnız `normalize_source` |
| `scripts/utils/project_config.py` | `lib/utils/project_config.py` | **Yeniden yazıldı**: `sap-project.json`, `master_language()` |
| `scripts/utils/{kapsam,kaynak_tarama,ddic_semantics}.py` | `lib/utils/` | Aynen (kapsam: env metni) |
| `scripts/validators/run_review.py`, `_gate_status.py` + 19 validator | `lib/validators/` | Reviewer zinciri (§5) |
| `scripts/abaplint/abaplint.json`, `governance/reference/released_successors.json` | `lib/abaplint/`, `lib/data/` | Veri |
| `scripts/validators/check_itg_signoff.py` | `../sap-intake-triage/scripts/check_intake_signoff.py` | `denetle()` eklendi; mantık aynı (+1 düzeltme, §4) |
| `tests/fixtures/itg_alan_dolulugu/run.py` | `tests/test_intake_signoff.py` | Nötr adlar + N5 (başlık biçimi) |

Yeni yazılanlar: `sap_adt_cli.py`, `sapadt/{__init__,project,gate,redact}.py`, `tools/meta.py`, `tests/*`.
2026-09-13 ek (§14): `tools/shells.py` (tipe özel kabuk reçeteleri), `tools/screen.py` (`adt_screen_generate`),
taşınan validator'lar `lib/validators/check_{rap_readonly_consumption,reuse_gate,domain_output_length}.py` (uyarlandı),
`tests/test_new_write_tools.py`.
2026-09-13 ek-2 (§15): `tools/msgclass.py` (`adt_msgclass_write`), `lib/utils/ddic_domain.py` (domain çıktı uzunluğu — tek kaynak),
`tests/test_msgclass_domain.py`.

## 2. CLI sözleşmesi — uygulamadaki ayrıntılar

- Çıktı daima tek JSON nesnesi: `ok, tool, class, result, error{code,message}, gate{project_dir,tier,sap_write_optin,scope,reason,intake,review}`.
  `--list`te `tool/class/gate` null, `result = {tools:[{name,class,description,args,available_on[,write_when][,requires_transport]}], counts}`.
- Sınıflandırma kod seviyesinde **salt-okur allowlist**tir (`gate.READ_TOOLS`, 20 araç, `ping` dahil); listede olmayan HER araç yazma kapısından geçer.
  `adt_unit_run`: `allow_risky_tests` truthy ise yazma (araç `if allow_risky_tests:` ile okur — `"false"` dizesi de truthy'dir; sınıflandırma araçla aynı kuralı kullanır).
- Çıkış kodu: `0` başarı · `2` kapı/guard reddi (SAP'ye gidilmedi) · `1` araç/bağlantı hatası · `3` kullanım hatası.
  Araç sonucundaki hata → exit 2: `guardrail_violation` (kod = `ADR_0005_A|C|D`, `ADR_0010_TIER`, `ADR_0011_PII`), `reviewer_blocker`, `tier_pii_guard`, `not_select`, `write_keyword`, `gecersiz_tablo_adi`, `gecersiz_kolon_adi`,
  `std_dml_scan_unavailable` (§12), `pull_before_edit_missing`, `pull_state_unreadable`, `source_changed_since_pull` (§13),
  `preflight_blocker`, `msgclass_overwrite_not_allowed` (§15).
  `pull_live_read_failed` (§13: yazma öncesi canlı okuma başarısız) → exit 1. §15'te eklenen exit 1: `lock_conflict`, `lock_failed`,
  `readback_mismatch`, `readback_failed`, `msgclass_live_incomplete`.
  → exit 3: `unsupported_type`, `bad_regex`, `no_scope`, `invalid_argument` (§14). Diğer `ok:false` → exit 1
  (§14'te eklenenler: `create_not_persisted`, `push_failed`, `activation_failed`, `screen_gen_rc`, `nav_remap_off`,
  `soap_fault`, `ev_rc_missing`, `master_language_unresolved`).
- Kapı sırası (`gate.check_write`, ilk red döner, her red ayrı kod):
  0 `sap_project_missing|sap_project_invalid` → 1 `write_not_optin_global` → 2 `write_flag_missing` → 3 `tier_not_writable`, `conn_env_mismatch`
  → 4 `scope_missing|scope_invalid|reason_missing|intake_missing|intake_invalid` → 5 `ADR_0005_A` (Z/Y; silmede standart obje; §14: `name` dışındaki ad argümanları — `adt_screen_generate` `fm_name`+`program`, `adt_post_shell(func)` `extra.function_group`; argüman kapıya verilmezse fail-closed), `ADR_0005_B` / `std_dml_scan_unavailable` (kaynakta standart tabloya doğrudan DML — §12), `ADR_0005_C` (paket tipi; transport: post_shell + 3 composite + `adt_msgclass_write` + `adt_screen_generate` mode≠READ), `language_mismatch`, `reviewer_bypass_forbidden`
  → 6 `write_log_unavailable`. Ardından (CLI) profil denetimi: `tool_not_available_for_profile`, `type_not_available_for_profile` (§14.2). Sonra araç fonksiyonunun kendi guard'ları ve reviewer'ı koşar (ikinci katman).
- Okuma çağrıları (`ping` hariç): `sap_project_*`, `conn_env_mismatch`, `tool_not_available_for_profile` (bugün `adt_transport_list` ∉ `btp_abap`; yazma aracı `adt_screen_generate` yalnız `ecc`/`s4_private`).
- Ek kullanım kodları: `usage_error`, `unknown_tool`, `invalid_args`, `args_invalid_json`, `args_not_object`, `args_file_unreadable`, `project_dir_invalid`.
- `sap-project.json` geçerlilik: JSON nesnesi · `sap_profile` ∈ {ecc, s4_private, s4_public, btp_abap} · `master_language` iki harf · `release`/`cleancore_policy` varsa metin.
- Kapsam: S0/S1 gerekçesi boş, çok satırlı ya da <15 karakter → `reason_missing`. S2 intake: proje-göreli, `.axet-code/intake/` altında (`..` ile kaçış çözümlenip reddedilir), `.md`, var olmalı ve `check_intake_signoff.denetle()` geçmeli; bulgular mesaja yazılır. Denetleyici bulunamaz/koşamazsa fail-closed.
- `gate.review`: okumada `null`; yazmada reviewer sonucu ya da açık metin (`NOT_RUN: …`, `NONE: bu araçta reviewer ön kontrolü tanımlı değil`, `BLOCKER (…)`, `SKIP (sebep)`).
- Deneme logu `<proje>/.axet-code/sap-write-log.jsonl` (reddedilen dahil her yazma denemesi): `ts, tool, class-yazma, object, object_type, scope, reason, intake, result, exit_code`. Host/şifre/token yazılmaz; `reason` metni bilinen sırlardan temizlenir.
- TLS: etkin `ADT_SAP_SSL_VERIFY` true değilse her araç çağrısında stderr'e TEK satır: `UYARI: TLS sertifika doğrulaması kapalı (ADT_SAP_SSL_VERIFY)` (`--list`te basılmaz; bağlantı yüklenmez).

### İçe aktarılabilir kapı (toplu/push script'leri için)
`from sapadt import gate` → `check_write(tool, proj, obje_adi=, object_type=, ek_obje_adlari=, transport=, require_transport_flag=, scope=, reason=, intake=, sap_write_flag=, tool_args=, log=True) -> GateResult`
(`allowed, code, message, gate_dict()`), `log_write_attempt(...)`, `check_read`, `check_data_access` (PII), `review_preflight(task, artifact)`, `tool_class`.
Red kararını `log=True` iken kapı kendisi loglar; izin verilen işlemin sonucunu çağıran loglar.

### KURAL — kapısız yazma yok
`sapadt` içindeki yazma metodlarını (`create_*`, `push_object`, `activate_object`, `delete_object`, `lock_object/unlock_object`, `set_object_source`, `run_classrun`, `syntax_check`) ya da yazma araçlarını (`adt_post_shell`, `adt_push_source`, `adt_delete`, `adt_activate`, `adt_publish_service`, `adt_classrun`, `adt_*_create`, `adt_syntax_check`, `adt_unit_run`, `adt_screen_generate`, `adt_msgclass_write`) **`gate.check_write`'tan geçmeden çağıran script repoya girmez.**
Statik kontrol: `tests/test_static.py::gate_atlatan_mi` — AST ile çağrı düğümlerini tarar; yazma çağrısı olup `check_write(...)` çağrısı olmayan dosya testi kırar. İstisna: yazma metodlarını tanımlayan/içeriden bağlayan `lib/sap_adt_lib.py`, `lib/sap_client.py`, `lib/rap_service.py`, `lib/auth/`, `tools/` ve `tests/`. Tarayıcının kendisi pozitif/negatif örnekle sınanır.

## 3. Ne değişti ve NEDEN

| Değişiklik | Neden |
|---|---|
| `.conn_adt` yalnız proje kökünde (`AXET_SAP_PROJECT_DIR` → cwd); IDE env'leri/üst dizin/PWD araması kaldırıldı (`lib/sap_adt_lib.py::find_conn_file`) | Yanlış dizindeki bağlantı dosyasını sessizce seçmek, tier guard'ının başka projeye bakması demek |
| Tier için `os.environ['ADT_SAP_TIER']` fallback'i kaldırıldı (`_conn.get_active_tier`) | Model `ADT_SAP_TIER=DEV python …` ile dosyasız yazma açabilirdi |
| `conn_env_mismatch` (gate) | ÖLÇÜLDÜ: `.conn_adt` `load_dotenv(override=False)` ile yüklenir (`lib/sap_adt_lib.py:438`) ⇒ ortamdaki `ADT_SAP_URL/CLIENT` dosyayı ezer; tier dosyadan okunur. Ayrışma = "DEV" onaylı kapı başka sisteme yazar |
| `language_mismatch` (gate, yazma) | Yasak D: Z obje yaratan/yazan çağrıda oturum dili `master_language` olmalı; sessiz eşitleme yok. Okumada bağlantı dili serbest |
| `master_language` sabit `TR` yerine `sap-project.json` (`tools/composite.py::_activate_and_verify`, `tools/atom.py::adt_publish_service`, `lib/validators/check_sap_master_language.py`) | Proje profili |
| `sap-client` sabit `"100"` → bağlantının client'ı (`tools/atom.py` publish, `tools/query.py` unit_run, `lib/rap_service.py::csrf`, 5 canlı validator); `sap-language` sabit `"TR"` → bağlantı/master dili | Başka client'lı sistemde yanlış mandanta istek |
| Araç katmanındaki 10 + rap_service'teki 2 `verify=False` → `verify=<session>.verify` | `ADT_SAP_SSL_VERIFY` tek yerden geçerli olsun; varsayılan `false` olduğundan varsayılan davranış AYNI |
| `skip_reviewer=true` ve boş olmayan `ack_drop` → `reviewer_bypass_forbidden` | Aşağıda (ack_drop) |
| `run_review.py`: kaynak çekirdekteki `…_CEVRIMDISI` ortam değişkeniyle BLOCKER→WARNING indirimi kaldırıldı (yalnız açık `--cevrimdisi` bayrağı kaldı); proje-lokal `scripts/validators-local/` araması kaldırıldı | Alt süreç ortamı miras alır / model proje dizinine yazabilir → ikisi de reviewer'ı atlatma yoluydu |
| `validate_sap_config` şablon `.conn_adt` yaratmıyor | Okuma aracının proje dizinine yer-tutucu parolalı dosya yazması istenmeyen yan etki |
| CSRF disk önbelleği kapalı (`_csrf_cache_path` → None; bilinçli deney için `AXET_SAP_CSRF_DISK_CACHE=1` → `.axet-code/tmp/`) | CLI her çağrıda yeni oturum açar; CSRF oturuma bağlı → önbellek fayda sağlamaz, diske token bırakır |
| `write_mcp_binding_state` no-op | aXet'te `.claude/`/statusline yok |
| Proje-dizini `.claude`, `project.yaml`, `CLAUDE_PROJECT_DIR` ve kaynak çekirdeğin önekli ortam değişkeni bağımlılıkları kaldırıldı | Bağımsız template |

**`ack_drop` ne yapıyor, atlatabiliyor mu?** ÖLÇÜLDÜ (`lib/validators/check_table_field_drop.py:143-153`): `table_update` zincirindeki DROP-guard, adı `--ack-drop` ile verilen alanların DROP'unu BLOCKER yerine `[ACK-WARNING]` + exit 0 (`onayli-drop-ack`) sayar. Adsız DROP ve tip/rename değişikliği yine BLOCKER; guard'lar (tier/namespace) reviewer'dan önce koştuğu için onları atlatmaz. Yani `ack_drop` **tek bir veri-kaybı BLOCKER sınıfını atlatır** → aXet yolunda kaldırıldı: boş olmayan `ack_drop` kapıda `reviewer_bypass_forbidden` ile reddedilir. Testler: `6g2` (window-function BLOCKER + ack_drop → exit 2), `6g3` (tablo push + ack_drop → exit 2). Bilinçli alan silme kullanıcının CLI dışında yaptığı ayrı bir işlemdir.

## 4. Taşınırken düzeltilen kaynak kusurları (bu işi etkiliyordu)

1. `tools/atom.py::adt_activate` (klasik yol): alt katman aktivasyon hatasını yutup `False` döndürdüğünde yanıt `ok:true, activated:false` idi ⇒ başarısız yazma exit 0 olurdu. ÖLÇÜLDÜ (test 6h, sahte host): artık `ok:false` + `error: unreachable|activation_failed`.
2. `check_intake_signoff.py`: `KAPSAM` başlığı yalnız `kapsam:` biçiminde tanınıyordu; `## 1. KAPSAM` biçimi için yazılmış değer okuyucusu erişilemezdi. Başlık yazımı toleransı eklendi, doluluk denetimi aynen (P1 boş şablon yine düşer; N5 fixture'ı).
3. `check_amdp_comment_apostrophe.py`: raw olmayan docstring'de `\s` → Python 3.12 `SyntaxWarning` (ileride hata). `r"""` yapıldı.
4. `check_intake_signoff.py`: `sap-intake-triage/references/s2-artifact-schema.md` şablonu yer-tutucuları `<…>` ile yazıyor; kaynaktaki birebir yer-tutucu kümesi bunları tanımıyordu ve harf içerdikleri için "dolu" sayılıyordu ⇒ şablon doldurulmadan `[x]` ile kapıdan geçiyordu (ölçüldü: test P6). Değerde `<yer-tutucu>` kalmışsa alan boş sayılır; karşılaştırma işleçleri (`<>`, `a < b … c > d`) etkilenmez (test N6).
5. Canlı validator'larda (`check_sap_active_version`, `check_sap_struct_consistency`, `check_standard_table_fields`, `check_struct_field_dtel_active`, `check_table_field_drop`) sabit `sap-client=100` / `sap-language=TR` → bağlantının değerleri.

⚠ `s2-artifact-schema.md` (başka skill'in dosyası) "KAPSAM başlık biçiminde iki nokta ister" ve "ilk başarısızlıkta durur" diyor; 4.2 düzeltmesinden sonra başlık biçimi de kabul ediliyor ve `denetle()` tüm bulguları birlikte raporluyor (çıkış kodu aynı). Belge daha katı olduğu için yanlış yönlendirmez; yine de o dosyanın sahibi günceller.

## 5. Reviewer zinciri

Araçlardan erişilen görevlerin (`cds_update`, `table_update`, `class_push`, `rap_bdef_creation`, `rap_service_binding`, `struct_creation`, `struct_post_create`, `sap_active_check`, `dtel_creation`) validator'ları taşındı (19): window_function, deprecated_annotations, cds_currency_reference, released_objects, standard_table_fields, struct_field_dtel_active, table_field_drop, sap_struct_consistency, sap_active_version, sap_master_language, dtel_creation_labels, method_param_type_c, decimal_write_to, amdp_comment_apostrophe, docu_itf_line_width, abaplint, rap_managed_etag, audit_fields_autofill, bdef_backtick.

- **Düşürülen validator: `check_td_cancelled_fields.py`** (`struct_creation`, WARNING) — müşteri projesine özgü; kaynak çekirdekte de yoktu (orada her koşum SKIP=WARNING).
- **SKIP kalan / ölçüm üretemeyebilen zincirler** (kaynak metodoloji davranışı: `None` → SKIP ve görünür):
  - Eşlemesi `None` olan tipler (`doma/dtel/msag/dcl/ddlx/srvb/tabletype/fugr/func/enqu` push) → `reviewer.notice` + `gate.review = "SKIP (no_reviewer_task_for_this_operation)"`. `prog/program/report/include/incl` → `program_push`, `intf/interface` → `interface_push` (2026-09-14, §20). Composite'lerde `artifact_path` yoksa `SKIP (no_artifact_path_provided)` — istisna `adt_struct_create`: artefaktsız çağrıda `struct_fields_dtel` koşar (§20). `adt_domain_create` 2026-09-13'ten beri `domain_creation_csv`'ye bağlı (§15.1).
  - §14.6: `ddls` push'u kaynağına göre ayrılır (view entity / projection → `rap_cds_creation`); `ccimp`/`ccau` → `class_push` (ölçüldü); zincirlerde adı geçen eksik validator'lar taşındı/eşlendi.
  - `rap_service_binding`, `dtel_update`: boş zincir (bilinçli) → PASS + `zincir_bos`.
  - `check_abaplint`: `npx` yoksa `measured=false` → SKIP → WARNING (tüketici makinede Node beklenmez).
  - Canlı SAP'ye giden 6 validator (standard_table_fields W, struct_field_dtel_active B, table_field_drop B, sap_struct_consistency B, sap_active_version B, sap_master_language W): SAP'ye ulaşamazsa `measured=false` → SKIP; BLOCKER şiddetlilerde verdict BLOCKER.
  - ~~Taşınmayan ve araçlardan ERİŞİLMEYEN görev zincirleri~~ (2026-09-13 kapandı, §14.6): `check_domain_output_length`, `check_rap_readonly_consumption`, `check_reuse_gate` taşındı (uyarlandı); `check_itg_signoff.py` → `sap-intake-triage/scripts/check_intake_signoff.py` harici eşlemesi (`run_review.HARICI_VALIDATORLER`). `tests/test_new_write_tools.py::test_E2` zincirdeki her adın dosyasının var olduğunu zorlar.
- `TASK_CHECKLISTS` boşaltıldı (kaynaktaki playbook yolları bu repoda yok).

## 6. Kimlik bilgisi yolları (bulunan · yapılan)

| `dosya:fonksiyon` | Bulgu | Yapılan |
|---|---|---|
| `create_rap_service.py:csrf` → `lib/rap_service.py:csrf` | CSRF token'ın ilk 20 karakteri stdout'a; araçlar stdout'u `client_log`a toplar ⇒ JSON çıktıya sızıyordu | Maskelendi |
| `lib/sap_adt_lib.py:SAPADTClient._apply_saml_cookies` | Debug logunda `SAP_SESSIONID` çerezinin son 20 karakteri | Maskelendi |
| `lib/sap_adt_lib.py:_csrf_cache_path/_save_csrf_to_cache` | CSRF token proje köküne `.csrf_token.json` | Önbellek kapalı (§3) |
| `lib/sap_adt_lib.py:validate_sap_config → create_conn_template` | Proje dizinine yer-tutucu parolalı `.conn_adt` yazıyordu | Yaratma kaldırıldı |
| `lib/sap_adt_lib.py:debug_conn_discovery` | Parola `***`; URL/kullanıcı döner | Araçlardan çağrılmıyor; değişmedi |
| `lib/sap_adt_lib.py:check_sap_config` | Parolayı iç sözlükte tutar, dönüşe koymaz | Değişmedi |
| `lib/sap_adt_lib.py:create_conn_file`, `set_session_credentials` | Parolayı `.conn_adt`/ortama yazar (amaçlı) | CLI yolunda çağrılmıyor (ölçüldü: yalnız docstring örnekleri) |
| `lib/sap_client.py:SAPClient.__init__` (`ADT_SAP_DEBUG=1`) | `sap_adt_debug.log`'a URL/client/kullanıcı (parola yok) | Değişmedi |
| `lib/auth/jwt_auth_provider.py:refresh_credentials` | `client_secret` token ucuna POST gövdesi (amaçlı) | Değişmedi |
| Tüm çıktı | Savunma katmanı | `sapadt/redact.py`: etkin parola, `user:pass`, Basic base64, Authorization/Bearer, X-CSRF-Token, SAP oturum çerezleri, `password/access_token/client_secret` JSON alanları → `***` (stdout JSON + log `reason`) |

## 7. TLS / ortam önceliği (canlı ölçüm için)

- Varsayılan: `ADT_SAP_SSL_VERIFY` yoksa `false` (`lib/sap_adt_lib.py:_build_session`, `sess.verify`, satır ~927).
- `InsecureRequestWarning` susturması import anında YALNIZ ortama bakar (`:54-55`), `.conn_adt` yüklenmeden önce.
- `.conn_adt` modül import'unda `load_dotenv(dotenv_path=conn_path)` ile (**override=False**, `:438`) yüklenir ⇒ **ortam değişkeni `.conn_adt`'deki değeri EZER** (ADT_SAP_SSL_VERIFY dahil; anahtar ortamda boş dize olarak bile varsa). `override=True` kullanan `set_explicit_working_dir` / `create_conn_file` CLI yolunda çağrılmaz.
- Doğrulama AÇIKKEN bile TLS doğrulamasız kalan yollar (kaynakla aynı, değiştirilmedi): `lib/auth/i_auth_provider.py:get_csrf_token` (`:99`), `lib/auth/jwt_auth_provider.py:refresh_credentials` (`:99`) ve canlı validator'lar (`check_sap_active_version` ×2, `check_sap_struct_consistency` ×2, `check_standard_table_fields`, `check_struct_field_dtel_active`, `check_table_field_drop`).

## 8. Nötrleştirme (grep sayıları, taşınan dosya kümesi)

| İz | Önce | Sonra |
|---|---|---|
| `ZSD0*` obje adları (→ `ZDEMO0/ZDEMO1`) | 142 | 0 |
| Gerçek transport numaraları (3 sistem öneki) | 13 | 0 |
| Gerçek bulut kiracı host'u | 2 | 0 |
| Sisteme özgü ATC variant adı | 2 | 0 |
| Kaynak çekirdek adı / MCP paket yolu / IDE proje env'i (`.py`) | 7 / 45 / 9 | 0 / 0 / 0 |
| `project.yaml` | 9 | 2 (değişikliği anlatan docstring) |
| `create_rap_service.py`'deki müşteri sabitleri (19 satır) | — | taşınmadı (kesit) |

Kalan tek eşleşme `TESTK900001`: testlerdeki sahte transport.

## 9. Bilinçli dışarıda kalanlar

MCP sunucu döngüsü · `create_rap_service` adımları ve CLI'si · `source_drift` senkronu, `detect_source_drift`, `sync_repo_from_live` · statusline bağlantı durumu · checklist dosyaları · kaynak metodolojinin diğer fixture'ları · proje-lokal validator'lar · `check_td_cancelled_fields`.

## 10. Bilinen sınırlar

- Kapı YALNIZ `sap_adt_cli.py` (ya da `gate.check_write` çağıran kod) yolunda garantidir. `lib/` (sap_adt_lib, sap_client) guard bilmez; doğrudan çağrı kapıyı atlar. Model `bash` ile keyfi Python da çalıştırabilir — kapı kaza/kısayolu önler, kararlı bir aktörü değil.
- `--project-dir` serbesttir; tier/opt-in o projenin `.conn_adt`'sine ve makinenin `config/sap-write.local`'ına göre değerlendirilir.
- Her CLI çağrısı yeni süreç + yeni HTTP oturumu + yeni CSRF alımıdır. CSRF disk önbelleği kapalı olduğundan kaynak metodolojideki önbellek (ve onun "cache poison self-heal" düzeltmesi) burada devrede değil: çağrı başına ek bir CSRF GET'i ve oturum açma maliyeti vardır (**ölçülmedi**).
- `adt_unit_run` okuma sınıfında olsa da araç kendi içinde DEV tier ister (kaynakla aynı) → QA/PRD'de `ADR_0010_TIER` (exit 2). `adt_dump_list` DEV dışında `acknowledge_risk` ister.
- `adt_push_source` reviewer'a geçici dosya (`tmpXXXX.<tip>.txt`) verir; adını dosya adından türeten canlı validator'ların (ör. master language) gerçek objeyi bulup bulmadığı **DOĞRULANMADI** (canlı SAP yok).
- `check_intake_signoff._YER_TUTUCULAR` kaynak çekirdeğin intake şablonunu tanır; `sap-intake-triage` skill şablonu farklıysa bu küme güncellenmeli.
- Ağ yolu (push/activate/create/publish/okuma araçlarının SAP'ye giden kısmı) bu partide yalnız "bağlantı hatası → exit 1" düzeyinde sınandı; canlı davranış **DOĞRULANMADI**.

## 11. Testler

`python tests/run_tests.py` (stdlib unittest; ağ yok). Fixture'lar `tempfile` altında üretilir; yazma opt-in testleri `scripts/` ağacını geçici bir AXET_HOME'a kopyalar (env kancası yok → model env ile opt-in atlatamaz). Kapsam: `--list` sınıfları · sap-project.json fail-closed · opt-in/bayrak/tier (eksik, çakışık, önek, env, QA) · kapsam/gerekçe/intake · 10 yazma aracının tamamında Z/Y reddi (liste ile eşitlik zorlanır) · transport · dil · env ezmesi · reviewer BLOCKER + bypass reddi · PII (QA JOIN/takma ad, DEV kontrol) · log + sır sızıntısı · TLS uyarısı · kullanım hataları · süreç-içi araç guard'ları (istemci çağrılırsa patlayan yama + kontrol grubu) · derleme · yasak dizgeler · gate-atlatma taraması · intake fixture'ı ·
Yasak B tarayıcısı (`test_std_dml_scan.py`: 14 pozitif / 22 negatif / tip kapsamı / mesaj; CLI `6j`; süreç-içi 2. katman) ·
PULL-BEFORE-EDIT (`test_pull_before_edit.py`: sahte istemci + çağrı listesi; CLI `6k`) ·
yeni yazma yolları (`test_new_write_tools.py`: sahte ADT oturumu her HTTP çağrısını kaydeder — uç/Content-Type/gövde/corrNr;
CLI `test_cli_gate.py::test_10`, §14.9).
Ölçüm (2026-09-13): `python tests/run_tests.py` → **242/242 senaryo satırı OK · 55 unittest, 0 failure, 0 error** (önce 153/153 · 30).
Ölçüm (2026-09-13, ek-2 §15): **323/323 senaryo satırı OK · 70 unittest, 0 failure, 0 error** (+ `test_msgclass_domain.py` 14 unittest, CLI `test_11`, `test_01` 1d, `test_05` msgclass).

## 12. Kesin Yasak B tarayıcısı (`sapadt/std_dml_scan.py`)

Amaç: `adt_push_source` ile gönderilen ABAP kaynağında standart (Z/Y dışı) tabloya **doğrudan** veritabanı yazımı varsa
yazmayı reddetmek (kullanıcı kararı 2026-09-13: doğrudan BLOCKER). Doğru yol BAPI → RFC FM → işlem kodu (BDC) → kullanıcıdan manuel.

### 12.1 Nerede koşar
- **Kapı** (`gate.check_std_dml`, `check_write` içinde isim kontrolünden hemen sonra, transport/dil/reviewer'dan önce): bulgu → exit 2 `ADR_0005_B`,
  mesajda ilk 5 bulgu `satır N: <ifade> → hedef <TAB> (<kural>)` + yönlendirme. `result` null (araca girilmedi).
- **Araç** (`tools/atom.py::adt_push_source`, tier/namespace guard'ından sonra, ağ ve reviewer'dan önce): ikinci katman —
  kapıyı `tool_args`'sız çağıran script de kaynağı gönderemez (`guardrail_violation` + `ADR_0005_B`).
- Kaynak taşıyan araçlar `gate.SOURCE_ARG_TOOLS` (bugün yalnız `adt_push_source.source`; ölçüldü: `adt_post_shell` kaynak almaz,
  composite'lerin `artifact_path`'i DDIC reviewer girdisi, `adt_activate`/`adt_syntax_check`/`adt_classrun` kaynak metni almaz).

### 12.2 Kaynağa ulaşılamazsa — FAIL-CLOSED (seçilen)
`source` yok / metin değil / tarayıcı istisna attı → **exit 2 `std_dml_scan_unavailable`**. Gerekçe: "mevcut davranışı koru" seçeneği,
`check_write`'ı `tool_args` vermeden çağıran bir script'in BLOCKER'ı sessizce atlaması demekti; kaynak metni push'un zorunlu argümanı
olduğundan meşru çağrıda bu kod hiç görülmez.

### 12.3 Tarama kuralları
Önişleme (karakter düzeyinde lexer, satır numarası her karaktere taşınır):
- ABAP kipi: 1. sütunda `*` satırı ve literal dışındaki `"` sonrası atılır; `'…'` (`''` kaçışı), `` `…` `` ve `|…|` (gömülü `{ }` dahil) yer tutucuya çevrilir; ifade `.` ile biter; zincir ifadesi `A: p1, p2.` → `A p1` · `A p2` (parantez dışı virgül).
- SQL kipi: `EXEC SQL … ENDEXEC.` ve AMDP gövdesi (`METHOD … BY DATABASE PROCEDURE|FUNCTION … .` → `ENDMETHOD.`): `--`, `/* */`, 1. sütun `*` atılır, `'…'` yer tutucu, `"…"` tanımlayıcı olarak korunur, ifade `;` ile biter.

| Biçim (ifade başına çapalı, büyük/küçük harf duyarsız) | Karar |
|---|---|
| `INSERT INTO <t> VALUES` · `INSERT <t> FROM [TABLE]` | DB |
| `UPDATE <t> SET` · `UPDATE <t> FROM` · `UPDATE <t>.` (kısa biçim) | DB |
| `MODIFY <t> FROM TABLE` · `DELETE <t> FROM TABLE` · `DELETE FROM <t> …` (MEMORY/SHARED/DATABASE hariç) | DB |
| `MODIFY <ad> FROM <wa>` (INDEX / TRANSPORTING / USING KEY yoksa) · `MODIFY <ad>.` · `DELETE <ad> FROM <wa>` (TO / WHERE / USING KEY / sayı yoksa) · `DELETE <ad>.` | **belirsiz → bildirim kuralı** (aşağıda) |
| Hedef dinamik `(<değişken>)` | DB — BLOCKER, mesaj "dinamik tablo adı" (hedef bilinemez) |
| Hedef literal `('ZTAB')` | literal çözülür, ad kuralı uygulanır |
| `<t>` sonrası `CLIENT SPECIFIED` / `USING CLIENT[S] …` / `USING ALL CLIENTS` / `CONNECTION …` | ad çözümüne engel değil |
| SQL kipi: `INSERT INTO` · `UPDATE <t> [alias] SET` · `DELETE [HISTORY] FROM` · `MERGE INTO` · `UPSERT` · `REPLACE <t> (…|VALUES|SELECT|WITH)` · `TRUNCATE TABLE` | DB; hedef = son noktalı parça, tırnaksız; `:tablo_değişkeni` DB değil |
| `INSERT … INTO TABLE` · `INSERT … INTO <itab> INDEX` · `INSERT LINES OF` · `MODIFY TABLE` · `MODIFY <itab> … INDEX|TRANSPORTING` · `DELETE <itab> WHERE|INDEX|FROM n TO m` · `DELETE TABLE` · `DELETE ADJACENT DUPLICATES` · `DELETE DATASET` · `DELETE FROM MEMORY|SHARED MEMORY|SHARED BUFFER` · `MODIFY/READ/COMMIT ENTITIES` · `CALL FUNCTION … IN UPDATE TASK` · UPDATE'in ifade başında olmadığı her durum · yorum/literal içi | yakalanmaz |

**İzinli hedef:** `Z…`/`Y…` ya da `/Z…/…`, `/Y…/…`. Başka her `/NS/` (ör. `/SCWM/`, müşterinin `/ABC/`'si) **yasaklı** —
standart SAP namespace'i ile müşteri namespace'i koddan ayırt edilemez; `gate.check_names` ile aynı fail-closed ilke (onaylandı 2026-09-13).

**Belirsiz biçim — bildirim kuralı (bilinçli karar):** aynı kaynakta `<ad>` için
1. iç tablo bildirimi (`DATA|STATICS|CLASS-DATA <ad> TYPE [STANDARD|SORTED|HASHED] TABLE OF` · `LIKE TABLE OF` · `TYPE <…_t|…_tt|tt_…>` · `OCCURS` · `WITH HEADER LINE` · `BEGIN OF <ad> OCCURS` · `INTO [CORRESPONDING FIELDS OF] TABLE @DATA(<ad>)`) → iç tablo, izinli;
2. değilse `TABLES <ad>` → DB;
3. değilse ad `lt_ gt_ ls_ t_ it_ et_ ct_` önekli → iç tablo;
4. değilse → DB. Bulgunun `neden` metni hangi adımın karar verdiğini yazar.

**Tip kapsamı** (`abap_kaynagi_mi`, `lib/object_types.py`'den türetilir): kanonik tipin `file_extension`'ı `.abap` (class, interface, program, include, functiongroup, function) ya da sınıf alt-include'u → taranır. CDS/DDLX/DCL/SRVD/DDIC/package taranmaz; object_types'ın tanımadığı BDEF/SRVB/MSAG/ENQU açık listeyle taranmaz; bunun dışındaki bilinmeyen tip ve tipsiz çağrı **taranır**.

### 12.4 Mutasyon kontrolü (2026-09-13, elle, geri alındı)
`gate.check_write` içindeki `check_std_dml` çağrısı `None` yapıldı → CLI `6j2` **FAIL** (`kapida=False`: red araç katmanından geldi, `result` dolu).
Geri alınınca 3/3 OK. Araç katmanı süreç-içi testle (`test_inprocess_guards`: `adt_push_source Z sınıf + std tablo DML`) ayrıca sınanır.

### 12.5 Bilinen sınırlar (yakalayamadıkları)
- Dize içindeki SQL: ADBC (`cl_sql_statement->execute_update( 'UPDATE …' )`), dinamik SQL metni — literaller taranmaz.
- `DELETE FROM DATABASE` / `EXPORT … TO DATABASE` (INDX cluster): SAP'nin cluster API'si, doğrudan SQL değil → işaretlenmez (onaylandı 2026-09-13).
- Standart tabloya yazan FM/BAPI dışı rutin çağrıları (`CALL FUNCTION 'X' IN UPDATE TASK` içinde ne yapıldığı), `PERFORM … ON COMMIT`, makro (`DEFINE`) gövdeleri, `INCLUDE` edilen başka objeler.
- SAP'de zaten bulunan kod: `adt_activate`, `adt_syntax_check` (bekleyen sürümü aktive eder), `adt_classrun` kaynak metni almaz → taranmaz.
- Bildirim başka include'daysa (TOP include) yalnız önek kuralı kalır → öneksiz iç tablo adı yanlış pozitif verir (mesaj satırı gösterir).
- Müşterinin `/Z`,`/Y` dışı kendi namespace'i BLOCKER alır; desteklemek yapılandırma değişikliği ister — bugün desteklenmiyor.
- **DOĞRULANMADI** (SAP dokümanı/canlı derleyiciyle teyit edilmedi): `EXEC SQL` içinde `"` ABAP yorumu mu tanımlayıcı mı (tanımlayıcı sayıldı → `"` yorumundaki SQL yanlış pozitif olabilir); AMDP gövdesinde 1. sütun `*` (yorum sayıldı; DML `*` ile başlayamayacağı için kaçırma üretmez); `|…|` şablonunun gömülü ifade dışında satır aşamayacağı varsayımı; HANA `INSERT` INTO'suz biçimi tanınmaz.
- Zincir ifadede virgül SET listesini de böler; tespit ilk parçada hedef bulunduğu için etkilenmez, ancak mesajdaki ifade metni kısalır.
- Kapı yalnız `sap_adt_cli.py` / `check_write` yolunda garantidir (§10).

## 13. PULL-BEFORE-EDIT (`sapadt/pull_state.py`)

### 13.1 Tasarım — iyimser eşzamanlılık
- `adt_get` (`include_source=true`, `ok`, `exists:true`, `source` metin) → `<proje>/.axet-code/sap-pull-state.json`:
  `{"<tip>:<AD>": {"sha256", "pulled_at" (UTC ISO), "object_type"}}`. Tip anahtarı eşanlamlıları birleştirir (`object_types.normalize_object_type`,
  sınıf alt-include'u, `behaviordefinition→bdef`). Kardeş uçta çözülen tablo/yapı (`resolved_type`) iki tiple de yazılır. Yanıtta `pull_state: kaydedildi | yazilamadi: …`.
- `adt_push_source` (araç içinde; Yasak B taraması ve reviewer'dan SONRA, istemci alınmadan önce):
  1. kayıt dosyası bozuk → exit 2 `pull_state_unreadable` · kayıt yok → exit 2 `pull_before_edit_missing` (ağa gidilmez);
  2. canlı kaynak `_adt_get_oku` ile okunur (kapının TEK ağ çağrısı) — okunamazsa exit 1 `pull_live_read_failed` (sessiz geçiş yok);
  3. canlı özet ≠ kayıt → exit 2 `source_changed_since_pull` (push yapılmaz; mesaj: yeniden çek, değişikliği yeni kaynağa uygula);
  4. push; kaynak yüklendiyse canlı **yeniden okunur** ve o özet yazılır (`pull_state: guncellendi`). Okunamazsa kayıt silinir; yükleme belirsizse (istisna / beklenmedik dönüş) kayıt silinir → sonraki push yeniden çekme ister.
- **"yerel dosya ≠ canlı" kıyası YAPILMAZ** — kaynak çekirdekte her meşru düzenlemeyi bloklayan eski kontrol bu yüzden kaldırılmıştı. Kıyas çekme anındaki canlı ↔ yazma anındaki canlıdır.
- `adt_post_shell` bu kontrole girmez. Yeni kabuğa ilk push'tan önce de `adt_get` gerekir (boş kabuk kaynağı kaydedilir).
- İç okumalar kayıt yazmaz: `_adt_get_oku` (push kontrolü, `adt_grep_source`, `adt_post_shell` varlık sondası `include_source=false`).

### 13.2 Neden bu hash/normalize
`sha256(normalize_source(text))` — CRLF→LF + satır sonu boşlukları + baştaki/sondaki boş satırlar (readback kıyasıyla aynı fonksiyon). Görevde "CRLF-normalize" istendi;
seçilen daha geniştir çünkü yalnız boşluk/boş satır farkı eşzamanlı bir düzenleme sayılmaz (ezilse içerik kaybı yok) ve iletim katmanındaki boşluk farkları sahte red üretmesin.
Push sonrası gönderilen metin DEĞİL canlı okunan metin kaydedilir: `push_object` readback'i biçim farkını (`format_only`) kabul eder, gönderilen metnin özeti sonraki push'ta sahte `source_changed_since_pull` verirdi.
Kayıt host/client taşımaz: kıyas içerik tabanlıdır; başka sistemden çekilmiş kayıt yalnız içerik aynıysa geçer (ki o durumda ezilecek bir şey yoktur).

### 13.3 Sınırlar
- Canlı okuma ile push arasında (saniyeler) başka birinin yazması yakalanmaz (TOCTOU); `push_object`'in SAP kilidi özete bağlı değil.
- Kontrol "SAP çekildikten sonra değişmedi"yi kanıtlar; düzenlemenin gerçekten çekilen metin üzerinde yapıldığını kanıtlamaz.
- Paralel CLI süreçleri dosyayı aynı anda yazarsa bir kayıt kaybolabilir → o obje `pull_before_edit_missing` alır (güvenli yön). Yazma atomiktir (geçici dosya + `os.replace`).
- Model durum dosyasını elle yazabilir; bu bir güvenlik sınırı değil, kaza/kısayol önleyicidir (§10).
- Push başına ek maliyet: öncesinde 1 okuma (class/program yolunda kaynak + metadata GET), sonrasında 1 okuma — **ölçülmedi**.
- **DOĞRULANMADI** (canlı SAP yok): `download_object` ile okunan sürümün (aktif/inaktif) çekme ve push anında aynı kuralla seçildiği; aktivasyonu başarısız push sonrası inaktif sürümün canlı okunmasıyla kaydın doğru güncellendiği.
- Composite araçlar, `adt_activate`, `adt_delete` bu kontrole girmez (kaynak metni yazmazlar).

## 14. Yeni yazma yolları (2026-09-13)

Amaç: kaynak çekirdekte canlı çalışmış reçeteleri olan ama CLI'de aracı olmayan yazma işlerini **mevcut yazma
kapısının arkasında** açmak. Kural: uç/Content-Type/gövde kaynak reçeteden birebir; reçetesi olmayan tip
`unsupported_type`. Aşağıdaki "kaynak" yolları kaynak çekirdeğe (salt-okur) göredir; `lib/…` bu paket içidir.

### 14.1 Destek tablosu — önce → sonra

| Araç · tip | Önce (kod okuması) | Sonra | Reçete (dosya:satır) |
|---|---|---|---|
| `adt_post_shell` class/interface/program/include | genel yaratıcı | **değişmedi** (yalnız `extra` → `invalid_argument`, boş açıklama → `ADR_0005_D`) | `lib/sap_adt_lib.py:4182-4359` |
| `adt_post_shell` ddls | alt katman `Unsupported object type` | yalnız-metadata kabuk POST (kaynak gövdeye KONMAZ) | `scripts/populate_cds_views.py:291-302,366-378` · `playbook/adt-cds.md:196-199,239-257` |
| · srvd | Unsupported | `srvd:srvdSource` + `srvdSourceType="S"` | `scripts/create_rap_service.py:113-127,320-333` · `playbook/adt-rap.md:157-163` |
| · bdef | tip tablosunda yok | `blue:blueSource` (`BDEF/BDO`, blues.v1) | `scripts/create_rap_service.py:372-406` · `playbook/adt-rap.md:90-97,190-197` |
| · fugr | Unsupported | `group:abapFunctionGroup` (groups.v2) | `playbook/adt-fugr-functions.md:27-47` |
| · func | `supports_create` False | `fmodule:abapFunctionModule` → `groups/<fg>/fmodules`; `extra.function_group` zorunlu ve Z/Y | `playbook/adt-fugr-functions.md:51-72` |
| · msag | tip yok | `mc:messageClass`, POST **stateless** (yalnız kabuk) | `lib/sap_client.py:2590-2661` · `playbook/adt-message-class.md:24-38` |
| · enqu | tip yok | `enqu:lockobject` (`extra`: primary_table, lock_fields[str], lock_mode, allow_rfc) | `lib/sap_client.py:2663-2756` · `playbook/adt-lock-objects.md:33-43,90-94` (canlı doğrulandı) |
| · ttyp | Unsupported | `ttyp:tableType` (`extra.row_type`) + canlı `typeName` okuması | `playbook/adt-tables-structures.md:254-293,359-370` |
| · ddlx / dcl | `supports_create` True (yanıltıcı) → Unsupported | `unsupported_type` + gerekçe | yalnız kütüphane kodu var (kaynağı kilitsiz, hatası yutulan `set_object_source`); canlı reçete YOK |
| · srvb | yok | `unsupported_type` | `playbook/adt-rap.md:169-179` (REST POST → 400 Session Timed Out, bloke) |
| · doma/dtel/structure/tabl | Unsupported | `unsupported_type` → composite araçlara yönlendirme | — |
| `adt_push_source` bdef | tip çözülemez | LOCK → PUT `/source/main` (text/plain, **If-Match YOK**) → UNLOCK → readback; **aktive ETMEZ**; transport zorunlu | `scripts/push_bo_atomic.py:124-162` · `scripts/create_rap_service.py:413-440` · `playbook/adt-rap.md:94,208-232` |
| · ccimp / ccau (`name` = ana sınıf) | araç yok | `SAPClient.push_class_include` (varlık sondası → POST-if-absent → PUT → bayt readback → ana sınıf aktivasyonu); transport zorunlu | `playbook/adt-classes.md:193-249` · `playbook/adt-rap.md:367-388` · `lib/sap_adt_lib.py:3162-3310` |
| · ccdef / ccmac | araç yok | `unsupported_type` (yazma yolu ölçülmedi) | `lib/object_types.py` CLASS_INCLUDE_TYPES notu (yalnız GET ölçüldü) |
| · func | generic URL ValueError | fonksiyon grubu canlı okumadan (`read_function_module`) → Z/Y guard → `set_function_module_source(activate=False)` → `activate_object(FM, fm_url)` | `playbook/adt-fugr-functions.md:74-169` · `playbook/adt-foundation.md:409-464` |
| · srvb / msag / enqu | alt katman hatası | `unsupported_type` (kaynak metni yok; MSAG mesajları `adt_msgclass_write`, §15.3) | — |
| `adt_get` ccimp/ccau/ccdef/ccmac | ValueError | `GET /oo/classes/<c>/includes/<seg>` (`/source/main` eklenmez); 404 → `include_absent_proven` | `lib/object_types.py` `get_class_include_url`/`ensure_source_url` |
| `adt_activate` enqu | `unsupported_type` | `ENQU/DL` referansı, `preauditRequested=true`, hüküm `activationExecuted`+`type=E`, worklist readback | `playbook/adt-lock-objects.md:114-134` |
| `adt_screen_generate` | **araç yok** | SOAP-RFC (§14.5) | `playbook/howto-dynpro-gui-status-generation.md:39-96 (§1), 98-125 (§2), 156-166 (§2.1), 176-192 (§2.2), 194-205 (§2.3), 207-220 (§2.4), 222-234 (§3), 275-288 (§4.4), 374-381 (§9)` · `playbook/adt-fugr-functions.md:191-235, 349-358` |

`lib/object_types.py` `supports_create`: yalnız genel yaratıcının gerçekten yaratabildiği `class/interface/program/include`
True (önce ddls/dtel/doma/tabl/fugr/srvd/ttyp/ddlx/dcl/package da True'ydu ve bayrak geçip alt katmanda düşüyordu).

### 14.2 Kapı ve profil
- **Ad argümanları** (`gate.arg_adlari`): `adt_screen_generate` → `fm_name` + `program`; `adt_post_shell(object_type=func)` →
  `extra.function_group`. Hepsi Z/Y (`ADR_0005_A`). Argüman kapıya verilmezse ad boş sayılır → red (script `check_write`'ı
  `tool_args`'sız çağırırsa denetim sessizce atlanmaz; test E3).
- **Transport:** `REQUIRES_TRANSPORT` + koşullu `TRANSPORT_KOSULLU` (`adt_screen_generate` mode≠READ). `--list`:
  `requires_transport_when`. Araç katmanı ayrıca: `adt_push_source` bdef/ccimp/ccau transport ister (kilit corrNr'sız alınmaz).
- **Obje tipi profili** (`_profile.TIP_PROFIL_KISITI`, CLI, kapıdan sonra): `adt_post_shell`/`adt_push_source` için
  `fugr`/`func` yalnız `ecc`,`s4_private` → aksi `type_not_available_for_profile` (çıkış 2). `adt_screen_generate` araç düzeyinde
  `available_on=(ecc, s4_private)` → diğer profillerde `tool_not_available_for_profile`. **Kaynak:** lider kararı (görev E) —
  profil matrisinin canlı kanıtı değildir. Okuma araçları daraltılmadı. `--list`: `object_type_available_on`.
- **Araç katmanı (ikinci guard, ağdan önce):** `adt_post_shell` paket tipi → `ADR_0005_C`; boş açıklama → `ADR_0005_D`
  (**sıkılaştırma**: önceden genel tipler boş açıklamayla geçiyordu); lock object adı E+Z/Y (guardrails `object_type` artık iletilir —
  önceden araç katmanı `enqu` adını reddederdi); func `function_group` Z/Y. Hiçbir mevcut red kodu gevşetilmedi.

### 14.3 Kaynak yazma — Yasak B ve reviewer
- Yasak B kapsamı (`std_dml_scan.abap_kaynagi_mi`, değişmedi): `func` (`.func.abap`) ve sınıf alt-include'ları **taranır**; `bdef`
  **taranmaz** (açık liste). CLI testleri 10o/10p/10q.
- Yanıt: yeni tiplerde `activated`, `activation_note`, (ccimp/ccau) `include`, (func) `function_group`; `ok:false` + yükleme hatası →
  `error: push_failed` + `message` (çıkış 1). BDEF yanıtında `activated:false` beklenir (aktivasyon ayrı adım).

### 14.4 Pull-before-edit genişlemesi
- `adt_get(name=<sınıf>, object_type=ccimp|ccau|…)` kaynağı okur ve `implementations:<SINIF>` / `testclasses:<SINIF>` anahtarıyla kaydeder.
- Include **404 ile kanıtlı yoksa** `pull_state.kaydet_yok` → `{"sha256": ozet(""), "absent": true}` ("çekildiği anda yoktu").
  Push anında: canlı hâlâ yok → ilk yaratım geçer (lib POST-if-absent); canlı artık dolu → özet tutmaz → `source_changed_since_pull`;
  kayıt "vardı" ama canlı yok → `source_changed_since_pull`. Yalnız sınıf alt-include'ları için (diğer tiplerde yeni kabuk
  `adt_post_shell` ile açılır ve `adt_get` boş kaynağı kaydeder).
- FM: pull kontrolünün canlı okuması fonksiyon grubunu da verir; push o grubu kullanır (grup adı FM adından türetilmez).

### 14.5 Ekran üreteci (`adt_screen_generate`)
- İstek: `POST <url>/sap/bc/soap/rfc?sap-client=<bağlantı client>&sap-language=<sap-project.json master_language>`,
  `Content-Type: text/xml; charset=utf-8`, `SOAPAction: ""`, zarf ns `urn:sap-com:document:sap:rfc:functions`, gövde `<urn:<FM>>`
  skaler `IV_*` + **daima** `<IT_FIELDS>…</IT_FIELDS><IT_BUTTONS>…</IT_BUTTONS>` (boşken de — istekte olmayan TABLES cevapta dönmez).
  `<item>` alan sırası reçetedekiyle aynı. Oturum/kimlik/TLS mevcut `SAPADTClient.session`'dan; yeni kimlik okuma yolu yok. FM adı gömülü değil.
- Ağ öncesi: tier DEV · `fm_name`/`program` Z/Y · mode ∈ WRITE/READ/DELETE · WRITE/DELETE transport · WRITE `title` (Yasak D) ·
  `dynpro` 4 hane · `screen_type` DOCKING/CONTAINER · `recreate` X/␠ · `cua_merge` X/␠/- · `nav_remap` ␠/X/- · `fields`+CONTAINER yasak ·
  tanınmayan `fields`/`buttons` alanı yasak → `invalid_argument` (çıkış 3) ya da guardrail (çıkış 2).
- Yıkıcı yollar yalnız açık argümanla gönderilir (`recreate`, `cua_merge`, `mode=DELETE` verilmezse istekte yok) ve `warnings`'e yazılır;
  hedef Z/Y şartı her modda (kapı + araç).
- Yanıt: `EV_RC`, `EV_MESSAGE` (**kırpılmaz**), `signals` (`nav_remap` ON/OFF, `cua_merge=…`, `fields=…`, `donor=…`, `DIKKAT:` satırları).
  `ok` = HTTP 200 ∧ fault yok ∧ `EV_RC == 0` ∧ (WRITE ise `nav_remap≠OFF`). Bantlar: `bilesik` (1-18; 5+fields → `fields_invalid`) ·
  `donor_fetch` 101-113 · `donor_status_missing` 120-130 · `merge_fetch` 202-213 · `dynpro_invalid` 300 · `zy_guard` 301 → `screen_gen_rc`.
  `nav_remap=OFF` → `nav_remap_off`; sinyal yoksa `warnings` ("ÖLÇÜLEMEDİ"). EV_RC yok → `ev_rc_missing`.
- **Karar — `EV_RC≠0` daima `ok:false`:** bileşik bantta rc=2 "ekran zaten var" olabilir ve kaynak kılavuz bunu normal akışta gösterir;
  araç yine başarı saymaz (bant + not döner, karar kullanıcının). Gevşek yön seçilmedi.
- Sınıf: **yazma** (READ modu dahil; FM yazabilen bir üreteçtir).
- Sızıntı: yanıt ve istisna mesajları `redact.temizle(bilinen_sirlar + host_sirlari(.conn_adt URL + istemci URL))` ile arındırılır; CLI de ayrıca arındırır.

### 14.6 Reviewer — eksik validator ölçümü ve düzeltme
**Ölçüm (önce, 2026-09-13, çevrimdışı `run_review.py --json`):** eksik dosya → `SKIP` + kendi şiddeti verdict'e sayılır
(`run_review.py` "koşmadı ≠ temiz" kuralı) ⇒ **sessiz PASS değil, fail-closed ve görünür** ("PRE-FLIGHT KOŞMADI … bulunamadı"):
`rap_cds_creation` (temiz view entity) → **BLOCKER** (readonly_consumption B SKIP) · `domain_creation_csv` → BLOCKER · `itg_s2_signoff` → BLOCKER.
Sonuç: RAP CDS push'unu `rap_cds_creation`'a bağlamak her RAP CDS push'unu sahte-BLOCKER'lardı → önce validator'lar taşındı.

**Düzeltme:**
| Validator | Durum | aXet değişikliği (neden) |
|---|---|---|
| `check_rap_readonly_consumption.py` (B) | taşındı | Rule A aynen. Rule B'nin kök araması: `.rules.md` → yoksa `AXET_SAP_PROJECT_DIR` altındaki `.bdef`'ler (sınırlı). Referans yoksa **ÖLÇÜLEMEDİ** (stderr, `~` sessiz bulgu; BLOCKER değil): aXet'te yerel ağaç SAP'deki BO'yu yansıtmak zorunda değil; kaynaktaki `path.parent.parent` geri dönüşü `%TEMP%` üstünü tarardı |
| `check_reuse_gate.py` (W) | taşındı | kök = proje dizini (atlanan dizinler + 5000 dosya sınırı → `AXET-GATE-STATUS measured=false`); müşteri master adları + `cbo-inventory.json` kaldırıldı; uyarılar stderr'e (görünür) |
| `check_domain_output_length.py` (B) | taşındı | desteklenmeyen uzantıda `measured=false` (önce exit 0 + uyarı = "temiz" ile aynı çıkış) |
| `check_itg_signoff.py` (B) | **harici eşleme** | `run_review.HARICI_VALIDATORLER` → `skills-sap/sap-intake-triage/scripts/check_intake_signoff.py` (kopyalanmadı; aynı CLI) |
| `check_standard_table_fields.py` (W, canlı GET) | değişmedi | SAP'ye ulaşamayınca zaten `measured=false` basıyor → SKIP=WARNING, zinciri bloklamaz (ölçüldü) |

**Ölçüm (sonra):** temiz view entity → WARNING (yalnız standard_table_fields ölçülemedi) · Rule A ihlali → BLOCKER · `as projection on`
yerel BDEF'siz → PASS + `sessiz_bulgu_gates=[check_rap_readonly_consumption.py]` · domain CSV → PASS · imzasız intake → BLOCKER ·
imzalı intake → PASS. CLI 10s: RAP view entity push'u gerçekten `rap_cds_creation` zincirini koşturdu (validator adları yanıtta).

**Eşleme:** `_reviewer.task_for_push(object_type, source)` — `ddls`/`cds`/`ddl`/`cdsview` kaynağı (yorumlar atılarak) `define [root] view entity`
ya da `as projection on` içeriyorsa `rap_cds_creation`, yoksa `cds_update`. `ccimp/implementations/ccau/testclasses` → `class_push`:
**ölçüldü** (örnek RAP CCIMP; 6 validator içerikten tanıyıp koştu, verdict WARNING = gerçek released_objects bulgusu, sahte BLOCKER yok).
`func/function`, `enqu`, `ttyp` → `None` (kaynakta zincir yok; SKIP görünür).

**Ek ölçüm (lider (d)) — composite araçların reviewer görevi** (`COMPOSITE_TOOL_TO_TASK`, çağrı `tools/composite.py::_maybe_reviewer`):
| Araç | Görev | Eşleme | Çağrı |
|---|---|---|---|
| `adt_struct_create` | `struct_creation` | `scripts/sapadt/_reviewer.py:126` | `scripts/sapadt/tools/composite.py:498` |
| `adt_domain_create` | ~~`None` — reviewer YOK~~ → **`domain_creation_csv`** (2026-09-13, §15.1) | `scripts/sapadt/_reviewer.py` `COMPOSITE_TOOL_TO_TASK` | `scripts/sapadt/tools/composite.py::adt_domain_create` |
| `adt_dtel_create` | `dtel_creation` | `scripts/sapadt/_reviewer.py:142` | `scripts/sapadt/tools/composite.py:390` |

⇒ "eksik BLOCKER validator her domain yaratmayı bloklar" kusuru bugün **yok** (domain `domain_creation_csv`'ye bağlı değil). Ama bunun
tersi bir **kapsam boşluğu** var: `adt_domain_create` hiçbir reviewer zinciri koşturmaz → her çağrıda `gate.review =
"SKIP (no_reviewer_task_for_this_operation)"` ve yanıtta `reviewer.notice` ("PRE-FLIGHT KOŞMADI"). Domain yaratma için reviewer
**ÖLÇÜLEMEDİ/yok**. `check_domain_output_length.py` artık taşındı ama CSV/XML artefaktı ister; tek-domain aracına bağlanması (girdi biçimi +
test) lider kararıdır — bu partide **bağlanmadı**. → **KAPANDI 2026-09-13 (§15.1):** eşleme yapıldı + artefakt beklemeyen argüman ön kontrolü.

### 14.7 ~~Neden mesaj yazma (MSAG mesajları) eklenmedi~~ → §15.3
İlk partide iki gerekçeyle eklenmemişti: kaynak reçetenin kilit silen güvenlik ağı (Kesin Yasak C) ve tam liste PUT'unun pull kaydı olmadan
güvensiz olması. İkinci partide (kullanıcı isteği) ağ **alınmadan**, canlı liste birleştirme + mesaj listesi pull kaydıyla eklendi: §15.3.

### 14.8 DOĞRULANMADI (canlı SAP yok; yalnız çevrimdışı sahte istemci)
- Tüm yeni uçların canlı davranışı: 201/200 dönüşleri, `AlreadyExists` gövde biçimleri, DDLS yalnız-metadata kabuğunun (sourceMainArtifact'sız)
  bu CLI yolunda kabul edildiği, MSAG/ENQU/TTYP'de `masterLanguage` özniteliği olmadan objenin master dilde yaratıldığı.
- `_request_with_csrf_retry` + `_get_headers` başlıklarıyla gönderimin reçetelerdeki ham `session.post` + discovery CSRF ile eşdeğer olduğu.
- Yeni FM'in arama indeksinde görünme gecikmesi (`adt_get(func)` yeni FM için `exists:false` dönebilir → pull kaydı alınamaz).
- Varlık sondalarının Accept başlıkları: ENQU `*/*` (reçetede Accept yok), TTYP/MSAG okuma yolu.
- ENQU aktivasyonunun ENQUEUE_/DEQUEUE_ FM'lerini ürettiği; `_aktivasyon_readback`'in ENQU/DL girdisini tanıdığı.
- BDEF `/source/main` GET'inin push sonrası inaktif sürümü döndürdüğü (readback kıyası buna dayanır).
- CCIMP readback uyuşmazlığında (lib istisnası) `source_uploaded` False raporlanır — yazma olmuş olabilir; sonraki push canlı özeti kayıtla kıyaslayıp reddeder (güvenli yön).
- Ekran üreteci: gerçek FM yanıt biçimi (`EV_RC`/`EV_MESSAGE` etiket adları kılavuzdan), `sap-language` query parametresinin oturum başlığıyla birlikte etkisi, `nav_remap` token biçimi.
- `rap_cds_creation` zincirinin canlı bağlantılı push'ta 30 sn reviewer bütçesine sığdığı (canlı `check_standard_table_fields` GET'leri; aşarsa `reviewer_timeout` → WARNING, zincirin BLOCKER'ları kaybolur — mevcut tasarım).

### 14.9 Testler ve mutasyon kontrolleri
- `tests/test_new_write_tools.py` (24 unittest, sahte ADT oturumu): 8 kabuk tipi uç/CT/Accept/gövde/corrNr/sonda · already_exists · 201+yok
  → `create_not_persisted` · 11 ağ-öncesi red · bdef push çağrı sırası (If-Match yok, aktivasyon yok) · ccimp/ccau (kayıt anahtarı, ilk yaratım,
  arada yaratılmış) · func (grup canlıdan, std grup reddi, DML, değişti, aktivasyon düştü) · enqu aktivasyon · ekran (zarf, TABLES boş etiket,
  EV_MESSAGE uzunluğu, bantlar, nav_remap OFF, fault, EV_RC yok, 10 ağ-öncesi red, QA tier, host/parola sızıntısı) · reviewer eşlemesi ·
  zincir dosyaları · kapı birim.
- `tests/test_cli_gate.py::test_10` (19 CLI senaryosu) + `test_01`/`test_05` güncellendi (yazma aracı kümesi, `--list` alanları); `test_static`
  gate-atlatma taraması `adt_screen_generate`'i de yazma aracı sayar.
- **Mutasyon (elle betik, 2026-09-13; her biri geri alındı ve test tekrar OK):** M1 kapıdan `arg_adlari` çıkarıldı → 2 FAIL · M2 TABLES boş
  etiketleri yalnız doluysa → FAIL · M3 `nav_remap=OFF` kontrolü çıkarıldı → FAIL · M4 FM canlı grup Z/Y guard'ı çıkarıldı → FAIL ·
  M5 RAP view entity eşlemesi çıkarıldı → FAIL · M6 BDEF PUT'a If-Match eklendi → FAIL.

### 14.10 Açık kalemler
- ~~MSAG mesaj yazma (§14.7)~~ (§15.3'te kapandı) · DDLX/DCL kabuk (canlı reçete yok) · SRVB yaratma (REST'te bloke) · ccdef/ccmac yazma (ölçülmedi) ·
  TTYP satır tipi düzeltme PUT'u (If-Match'li; reçete var: `playbook/adt-tables-structures.md:322-355`, bu partide yok) ·
  FM RFC-enable (SE37) · ekran üreteci FM'inin kendisinin yaratılması (kullanıcının sisteminde Z FM olmalı; bu araç yalnız çağırır).
- `sapadt/tools/screen.py` istemci istisnasında (`requests.ConnectionError`) `error: unexpected` döner (`_err_from_exc` yalnız `SAPADTError`
  alt sınıflarını eşler) — çıkış kodu doğru (1), kod adı genel.

## 15. Domain ön kontrolü + mesaj sınıfına mesaj yazma (2026-09-13, ek-2)

Kullanıcı isteği: (1) domain yaratmayı incelemeye bağla, (2) mesaj sınıfına mesaj yazma. Canlı SAP'ye yazılmadı; tüm ölçümler kod okuması +
çevrimdışı sahte istemci. Kaynak yolları kaynak çekirdeğe (salt-okur) göredir.

### 15.1 Domain — ölçüm ve düzeltme
- **Ölçüm (kod okuması, önce):** `lib/sap_adt_lib.py::create_domain` `<doma:outputInformation><doma:length>` alanına **girdi uzunluğunu**
  (`length_str`) yazıyordu ⇒ INT1/2/4/8 ve DEC/QUAN/CURR'da yanlış (ör. QUAN(15,3) → 15; doğrusu 19). Kaynak kural:
  `playbook/adt-domain-dtel.md:123-140` (§26.1.1: yanlış değer = aktivasyon uyarısı + ekranda kesilme) · `scripts/populate_domains.py:169-191,202-203`.
  Ayrıca açıklama / sabit değer `low` / `text` XML kaçışsızdı (kaynak `populate_domains.py:213-214,229` kaçışlıyor) ve `text` yoksa değer metin
  olarak yazılıyordu. Composite araç hiçbir reviewer zinciri koşturmuyordu (`COMPOSITE_TOOL_TO_TASK["adt_domain_create"] = None`).
- **Düzeltme:** formül **tek kaynağa** taşındı: `lib/utils/ddic_domain.py` (`expected_output_length`, `FORMUL_TIPLERI`). Kullananlar:
  `check_domain_output_length.py` (içe aktarır; eski yerel tanım kaldırıldı), `sap_adt_lib.create_domain` (gövdeye yazılan değer),
  `tools/composite.py::_domain_on_kontrol` (ön kontrol). Gövde kaçışlı; `text` yoksa boş gider (ön kontrol zaten reddeder).
- **Argüman ön kontrolü** (`steps.pre_flight`, artefakt beklemez, ağdan ÖNCE; BLOCKER → `preflight_blocker`, çıkış 2):
  | Kural | Kaynak |
  |---|---|
  | R1 `datatype` ∈ CHAR, NUMC, DATS, TIMS, CLNT, INT1, INT2, INT4, INT8, DEC, QUAN, CURR | `check_domain_output_length.py` CSV kuralı ("Bilinmeyen datatype" BLOCKER) · `playbook/adt-domain-dtel.md:133-140` |
  | R2 `length` pozitif tamsayı | formül girdisi · `lib/sap_adt_lib.py::_validate_datatype` (CHAR/NUMC pozitif) |
  | R3 `decimals` ≥ 0 tamsayı | `lib/sap_adt_lib.py::_validate_datatype` |
  | R4 `lowercase` bool | araç `"true" if lowercase` ile okur (`"false"` dizesi truthy) |
  | R5 `fixed_values[]` dolu `value` + dolu `text` (`ADR_0005_D`), tanınmayan alan yok | `playbook/adt-domain-dtel.md:246-263` ("low=değer, text=TR açıklama") · Kesin Yasak D |
  **Sıkılaştırma:** R1 önceden kütüphanenin kabul ettiği FLTP/RAW/LANG/ACCP/LCHR/STRG/D16D34… tiplerini artık reddeder (formülleri kaynakta yok).
  **Eklenmeyen (kaynakta kanıt yok):** lowercase yalnız CHAR · decimals yalnız sayısal tip · tipe sabit uzunluk (DATS=8 … — `adt-domain-dtel.md:416-423`
  tablosu DTEL bağlamında) · sabit değer metni uzunluğu · açıklama uzunluğu. Yanıtta `pre_flight.not_checked` bunları listeler (kapsam beyanı).
- **Artefaktlı zincir:** `COMPOSITE_TOOL_TO_TASK["adt_domain_create"] = "domain_creation_csv"`. CSV/XML → `check_domain_output_length.py`;
  desteklenmeyen uzantı → `measured=false` → run_review SKIP'i şiddetiyle sayar ⇒ **BLOCKER** (ölçüldü, test D3). CSV satırının ada/argümanlara
  eşitliği denetlenmez (validator bunu yapmıyor; açık kalem).
- **Görünürlük:** reviewer sonucu (SKIP dahil) üst düzey `reviewer` + `steps.reviewer`; `already_exists`, create hatası ve istemci kurulamaması
  dönüşlerinde de yanıtta. `gate.review`: `SKIP (no_artifact_path_provided)` · ön kontrol reddinde `NOT_RUN: argüman ön kontrolü BLOCKER (N bulgu; …)`.

### 15.2 DTEL / struct — artefakt verilmediğinde ne koşuyor (ölçüldü, süreç içi sahte istemci)
| Araç | Ağdan önce koşan | Koşmayan (yalnız `artifact_path` ile) | Ölçüm |
|---|---|---|---|
| `adt_dtel_create` | tier · Z/Y · transport · açıklama dolu · 4 etiket dolu (`require_all_labels`, `ADR_0005_D`) | etiket uzunlukları ≤ 10/20/40/55 (`check_dtel_creation_labels.py` R4), domain bağı | 24 karakterlik kısa etiket → `create_dataelement` çağrıldı; boş etiket → `ADR_0005_D`, ağ yok |
| `adt_struct_create` | tier · Z/Y · transport · açıklama · `fields[]` her öğede `name`+`type` · ~~DTEL denetimi yok~~ → 2026-09-14'ten beri `fields[]`'teki Z/Y + /ns/ DTEL var/aktif (§20) | CURR/QUAN anotasyonu | (2026-09-13) var olmayan DTEL'li alan → `create_structure` çağrıldı; `type`'sız alan → `validation_error`, ağ yok · (2026-09-14) var olmayan DTEL → `reviewer_blocker`, istemci çağrılmadı |
Yeni zincir icat edilmedi (görev sınırı). İki araçta da create hatası dönüşünde `reviewer` alanı yok (domain'de düzeltildi, bunlarda açık kalem).

### 15.3 Mesaj yazma — `adt_msgclass_write` (`tools/msgclass.py`)
- **Reçete (alınan):** `playbook/adt-message-class.md:66-137` (LOCK stateful + lock Accept → PUT `?corrNr&lockHandle&accessMode=MODIFY`,
  `Content-Type: application/vnd.sap.adt.mc.messageclass+xml; charset=utf-8`, **If-Match YOK** → UNLOCK) · `:139-150` (If-Match self-collision kök sebebi) ·
  `:152-165` (`mc:messages` çoğul, `mc:msgno` 3 hane, `mc:msgtext`, `mc:selfexplainatory`, `mc:documented`, `adtcore:name=""`, kaçış) ·
  `:167-191` (try/finally UNLOCK) · `:200-205` (tam liste değiştirme) · `:232` + `scripts/populate_message_class.py:68-79` (T100 metni ≤ 73 karakter) ·
  `populate_message_class.py:179-201` (gövde: responsible, masterLanguage, name, `MSAG/N`, description, language, packageRef uri/type/name).
- **Bilinçli farklar:** (1) `clear_enqueue_lock` güvenlik ağı (`adt-message-class.md:136,193-197`, `populate_message_class.py:305-310`) **alınmadı** —
  Kesin Yasak C; yalnız aracın kendi LOCK handle'ı UNLOCK edilir. Kilit alınamazsa DUR: HTTP 403/409/423 ya da gövdede `EU 510|locked|gesperrt|
  currently being edited|enqueue` → `lock_conflict`, aksi `lock_failed` (ikisi çıkış 1) + SM12 yönlendirmesi; PUT ve UNLOCK gönderilmez.
  (2) Tam liste PUT'u sarmalandı: yazmadan önce canlı liste okunur (okunamazsa `pull_live_read_failed`, yazma yok); **varsayılan birleştirme**
  (yeni numara eklenir, verilmeyen mevcutlar `documented` bayrağıyla korunur); mevcut numaranın metni/bayrağı farklıysa `allow_overwrite=true`
  yoksa `msgclass_overwrite_not_allowed` (çıkış 2, `plan.overwritten` önce/sonra); silme yalnız `delete_numbers` (canlıda yoksa `invalid_argument`).
  Değişiklik yoksa kilit alınmaz. (3) `responsible`/`description`/paket CLI argümanı değil, canlı okumadan (yoksa `package` argümanı / bağlantı kullanıcısı;
  paket ya da açıklama hiç yoksa `msgclass_live_incomplete`). (4) `masterLanguage`/`language`/`sap-language` = `sap-project.json` master_language
  (kaynakta sabit TR); canlı sınıfın master dili farklıysa `ADR_0005_D`, çözülemezse `master_language_unresolved`. (5) İstek
  `_request_with_csrf_retry` ile (kaynakta ham `session` + discovery CSRF). (6) Metin `strip` edilir (`populate_message_class.py:122`), numara
  dolgusu **tahmin edilmez** (kaynak `zfill(3)` yapıyordu; araç `"001"` biçimini ister).
- **Pull-before-edit:** `adt_msgclass_read` (ve `adt_get(msag, include_source=true)`) mesaj listesinin kanonik metnini (numaraya göre sıralı tek satır JSON:
  no, text, selfexplanatory, documented) `pull_state.kaydet(name, "msag", …)` ile yazar; `adt_msgclass_write` kayıt yok →
  `pull_before_edit_missing`, bozuk → `pull_state_unreadable`, yazma anındaki canlı özet farklı / sınıf silinmiş → `source_changed_since_pull`.
  İç okumalar (`_msgclass_oku`: kabuk sondası, `_adt_get_oku`, yazma öncesi/sonrası) kayıt yazmaz (§13.1 ile aynı ilke).
- **Geri okuma:** yazma sonrası canlı liste (no, text, selfexplanatory) beklenen tam listeyle kıyaslanır → eşit: `readback_verified:true`, kayıt
  güncellenir · farklı: `readback_mismatch` (`ok:false`, `readback_diff{missing,unexpected}`) · okunamadı: `readback_failed`; ikisinde kayıt silinir.
  PUT sırasında istisna → kayıt silinir (yazılıp yazılmadığı belirsiz).
- **Kapı/profil:** `REQUIRES_TRANSPORT` (kapıda `ADR_0005_C`); `name` Z/Y (kapı + araç `ADR_0005_A`); tier DEV; kapsam beyanı; bağlantı dili
  (`language_mismatch`). Araç katmanı (ağdan önce): boş metin `ADR_0005_D`; numara `^\d{3}$` metin, metin ≤ 73, tekrar eden numara, yaz+sil çakışması,
  `documented`/tanınmayan alan, bool olmayan bayrak, boş istek → `invalid_argument` (çıkış 3). `available_on=("s4_private",)`: reçetenin tek kanıtı
  (`adt-message-class.md:2` `applies_to`, `populate_message_class.py:8` "S/4 1909"); genişletme kanıt ister.
- **Sızıntı:** yanıtlar `redact.temizle(screen._sirlar(adt))` ile arındırılır (SAP hata gövdesi `sap_body` 300 karakter); `adt_msgclass_read` yanıtına
  `responsible` konmaz (iç alanlar `_` önekli ve atılır).
- `adt_push_source(msag)` ve `adt_post_shell(msag)` sonraki adım metinleri yeni araca yönlendirir.

### 15.4 Red kodları (yeni)
| Kod | Çıkış | Nerede |
|---|---|---|
| `preflight_blocker` | 2 | `adt_domain_create` argüman ön kontrolü |
| `msgclass_overwrite_not_allowed` | 2 | mevcut mesaj değişirdi, `allow_overwrite` yok |
| `lock_conflict` · `lock_failed` | 1 | mesaj sınıfı kilidi alınamadı (silme yok) |
| `readback_mismatch` · `readback_failed` | 1 | yazma sonrası canlı liste beklenenle aynı değil / okunamadı |
| `msgclass_live_incomplete` | 1 | canlıda paket/açıklama/sorumlu yok |
Yeniden kullanılan: `ADR_0005_A|C|D`, `ADR_0010_TIER`, `invalid_argument` (3), `pull_before_edit_missing`, `pull_state_unreadable`,
`source_changed_since_pull` (2), `pull_live_read_failed`, `master_language_unresolved`, `push_failed` (1). Hiçbir mevcut kod gevşetilmedi.

### 15.5 Testler ve mutasyonlar
- `tests/test_msgclass_domain.py` (14 unittest): D1 12 tip ailesinde POST gövdesi çıktı/girdi uzunluğu (gerçek `SAPADTClient.create_domain` gövde kurucusu,
  sahte ağ) · D2 11 ön kontrol reddi ağsız + gate.review + çıkış 2 · D3 eşleme + composite eşleme tazeliği (görev var, zincir boş değil) + kirli CSV
  BLOCKER ağsız + temiz CSV PASS + `.txt` BLOCKER · D4 artefaktsız SKIP görünür + istemci kurulamadığında izler · D5 XML kaçışı + formülün tek kaynak
  olduğu (validator fonksiyonu `utils.ddic_domain`'dakiyle aynı nesne) · M1 birleştirme (mevcutlar + `documented` korunur, LOCK/PUT/UNLOCK
  parametre-başlık-sıra, If-Match yok, kütüphane kilit yöntemleri çağrılmaz) · M2 üzerine yazma yalnız bayrakla · M3 silme yalnız listeyle + olmayan
  numara + değişiklik yok → kilit yok · M4 okuma 500 → yazma yok · M5 kilit çakışması: `lock_conflict` + SM12, PUT/UNLOCK/`clear_enqueue_lock`
  çağrısı YOK (sahte ADT bu yöntemi tanımlar ve çağrılırsa kaydeder) + `lock_failed` · M6 geri okuma farkı → `ok:false` + PUT 400 → UNLOCK yine
  gönderilir · M7 13 ağ öncesi red + QA tier + dil çözülemedi · M8 sınıf master dili EN · okumadan sonra mesaj eklendi · sınıf silindi · paket yok ·
  bozuk pull-state · M9 hata gövdesinde host/parola yanıtta yok + iç okumalar kayıt yazmaz + `adt_get(msag)` kaydeder, `responsible` dışarı çıkmaz.
- CLI: `test_01` 1d (`--list`: write · `s4_private` · transport · argüman adları), `test_05` (standart sınıf adı `ADR_0005_A`),
  `test_11` (transport kapıda, s4_public profil, numara kullanım hatası, boş metin, pull kaydı yok + `gate.review` NONE, kapsam yok, domain FLTP
  `preflight_blocker` araç katmanında, KONTROL: geçerli QUAN ağa gider ve ağ hatasında da reviewer SKIP + `pre_flight.output_length=19`, sızıntı yok).
- `test_static` gate-atlatma regex'i `adt_msgclass_write`'ı yazma aracı sayar.
- Ölçüm: `python tests/run_tests.py` → **323/323 senaryo satırı OK · 70 unittest, 0 failure, 0 error** (önce 242/242 · 55).
- **Mutasyon (betik, 2026-09-13; her biri geri alındı, dosya özeti doğrulandı, hedef test tekrar OK):** M-a gövdede çıktı uzunluğu = girdi → D1 FAIL ·
  M-b ön kontrol datatype kuralı kapalı → D2 FAIL · M-c birleştirme kaldırıldı (nihai liste yalnız verilenler) → M1 FAIL · M-d kilit çakışmasında
  `clear_enqueue_lock` eklendi → M5 FAIL · M-e geri okuma kıyası kapalı → M6 FAIL · M-f üzerine yazma bayrak kontrolü kapalı → M2 FAIL ·
  M-g pull özeti kıyası kapalı → M8 FAIL · M-h domain eşlemesi `None` → D3 FAIL.

### 15.6 DOĞRULANMADI (canlı SAP yok)
- Düzeltilmiş çıktı uzunluğuyla domain aktivasyonunun uyarısız geçtiği; DEC/QUAN/CURR'da `signExists=false` ile birlikte `length+4`'ün SAP önerisiyle
  aynı olduğu (formül kaynakta ölçülmüş, bu gövdeyle ölçülmedi).
- MSAG GET yanıtında `adtcore:responsible` ve `adtcore:packageRef` bulunduğu (yoksa araç `msgclass_live_incomplete` / bağlantı kullanıcısı).
- PUT'ta `mc:documented="true"` göndermenin uzun metni koruduğu (kaynak reçete hep `false` gönderiyordu; araç canlı değeri yansıtır).
- `_request_with_csrf_retry` ile LOCK/PUT/UNLOCK'un reçetedeki ham `session` + discovery CSRF ile eşdeğer olduğu; kilit çakışmasının 403 +
  `EU 510` gövdesiyle döndüğü (kaynak ölçümü `adt-message-class.md` §27 / `message-class.md` §3.2: create sonrası 403 EU 510).
- SAP'nin metni kırpıp/boşluk normalize edip etmediği (ederse `readback_mismatch` — güvenli yön).
- `sap-language` başlığı ile oturum dilinin birlikte etkisi (kapı oturum dilini `master_language`'e eşit ister).

### 15.7 Açık kalemler
- ~~DTEL etiket uzunlukları artefaktsız koşmuyor~~ → §16.8 (ADR_0005_D ön kontrolü genişletildi). Struct DTEL aktifliği artefaktsız hâlâ koşmuyor
  (§15.2); dtel/struct create hatası dönüşünde `reviewer` alanı yok.
- `domain_creation_csv` CSV satırının araç argümanlarıyla (ad/tip/uzunluk) aynı olduğunu denetlemiyor.
- Composite create hatasında üst düzey `error` kodu yok (CLI `tool_failed` basar; önceden de böyleydi).
- Mesaj uzun metni (`documented`, SE91 dokümantasyon) yazımı · `adt_msgclass_write` diğer profillere genişletme (kanıt yok).

## 16. Tanı araçları · açıklama yazımı · ipuçları · çoklu sistem (2026-09-13, ek-3)

Bu turda SAP'ye hiç bağlanılmadı; her şey sahte istemci/alt süreçle çevrimdışı test edildi. Kanıt dosya:satır referansları kod
docstring'lerindedir (kaynak çekirdek dosyaları salt-okur okundu, repoya kopyalanmadı).

### 16.1 Yeni okuma araçları (`sapadt/tools/diag.py`)
| Araç | Sınıf · profil | Ne yapar | Bilinçli fark |
|---|---|---|---|
| `adt_revisions` | okuma · all | yapı GET → versions linki → feed GET → sürümler | kütüphane `get_object_revisions` hataları `[]` ile yutuyordu; araç aynı iki GET'i yapar ve `not_found` / `revisions_unavailable` / `revisions_feed_failed` / link yok (ok, kanıt değil) ayırır. DEV dışında yazar maskelenir (ret değil; kapı moratoryumu) |
| `adt_object_structure` | okuma · all | `get_object_structure` + `sap_client.get_structure` ile aynı bileşen ayrıştırma | `sap_client` sarmalayıcısı istisnayı yutuyordu → doğrudan kütüphane; 404 → `exists:false` |
| `adt_system_info` | okuma · all | discovery servis kataloğu | kütüphane URL/client/kullanıcı/SID toplar → çıktı **allowlist** (`withheld_fields`) |
| `sap_doctor` | okuma · all | yerel 9 katman + canlı logon/CSRF, PASS/WARN/FAIL/SKIP + `not_checked` | URL/client/kullanıcı basılmaz; probe objesi katmanı yok |

**Kapı:** `gate.PRECHECK_EXEMPT_TOOLS = {"ping", "sap_doctor"}` — CLI bu iki araçta okuma kapısını ve profil kontrolünü atlar. Gerekçe: doctor'ın asıl
işi `sap-project.json` / bağlantı dosyası bozukken ne eksik olduğunu söylemektir. Gevşeme değildir: doctor aynı `load_sap_project` +
`check_connection`'ı kendisi koşar ve `sap_project`/`profile`/`conn_file`/`conn_keys`/`env_override`'dan biri FAIL ise canlı katmanları SKIP eder
(SAP'ye gitmez) — test D11/D12/D13 + CLI 12a (ağsız, exit 1).

### 16.2 `adt_set_description` (`sapadt/tools/description.py`, yazma · `s4_private` · transport zorunlu)
Reçete ve bilinçli farklar dosya docstring'inde. Özet: desteklenen tipler class/bdef/srvd/ddls/ddlx/dcl (canlı ölçüm yalnız DDLS); `srvb`/`prog`/`dtel`
kanıtla `unsupported_type`. Kilit obje URL'ine `_action=LOCK` (msgclass ile aynı yol), `CORRNR` ≠ istenen → PUT yok + kilit bırakılır. UNLOCK `finally`'de;
enqueue kilidi silinmez. 412'de envelope bayt bayt aynıysa yeni kilit döngüsünde TEK retry. Otomatik aktivasyon yalnız PUT öncesi aktive-bekleyen listesi
objenin temiz olduğunu kanıtladıysa; aksi `activation_required`. Pull kaydı varsa canlı özet kıyaslanır, yazımdan sonra silinir.
**Ek düzeltme (bu turda bulundu):** PUT isteği sırasında istisna gelirse "sonuç belirsiz" notu düşmüyordu (bayrak PUT dönüşünden sonra kuruluyordu) →
bayrak PUT gönderilmeden hemen önce kurulur (test A09).

### 16.3 `checklist_hint` ve `known_errors_hint` (`sapadt/hints.py`, CLI `bitir()`)
- Kaynak çekirdekteki iki oturum kancasının (iş türü ipucu, araç hatası sonrası ipucu) aXet karşılığı: aXet'te kanca olmadığı için ipucu **CLI yanıtında**
  üst düzey alan olarak taşınır. Engellemez, çıkış kodunu değiştirmez, `try/except` içinde (ipucu hatası sözleşmeyi bozmaz), yanıtla birlikte arındırılır.
- `checklist_hint`: yalnız yazma sınıfında; tip → grup eşlemesi kaynak kancanın sırasıyla aynı (cds · rap · ddic-dd · ddic-st · classic) + aXet grupları
  (class · fugr · msag · enqu · screen). Hedef dosyası yoksa ve "yazılıyor" listesindeyse `status: yazılıyor` (`sap-ui5-fiori/SKILL.md`, `sap-code-review/SKILL.md`).
- `known_errors_hint`: çıkış 1/2'de; hata kodu kümeleri + metin desenleri (SADT_RESOURCE 043, 412/423/409, EU 510, OO_SOURCE_BASED 012, FUNC_ADT 015,
  DS 512, 00256/00264 …) → `known-errors-adt.md` K-xx ya da `known-errors-classic.md` bölümü; eşleşme yoksa iki indeks. `sap_message_keys` mesaj sınıfı+numara.
- Test H03/H05 her hedef dosyanın ve bölüm başlığının var olduğunu doğrular (başlık değişirse test kırılır).

### 16.4 Çoklu sistem bağlantısı
- `scripts/switch_tier.py`: `conn/<SISTEM_ADI>.env` → `.conn_adt` (+ `conn/.conn_adt.bak`), tier kısaltmasıyla tek sistemse çözülür, birden çoksa `ambiguous_tier`.
  Çıktı tek JSON, dosya içeriği/URL basılmaz. Tam anahtar, çakışan tier → UNKNOWN, parola dışı `<...>` → geçiş yok. Kayıtlı araç DEĞİL (kayıtlı olsaydı
  yazma sınıfı ve kapı gerekirdi; dosya işlemidir, SAP'ye gitmez).
- `scripts/setup_credentials.py`: yalnız etkileşimli terminal; parola `getpass` ×2; değer basmaz; `--slot`; doğrulama (URL, client 3 hane, dil =
  master_language, tier, ad); POSIX'te 0600. Kaynaktaki `input()` ile parola ve `--json` parola argümanı alınmadı.
  **Ölçülen tuzak (bu turda):** Windows'ta stdin NUL'a yönlendirilince `isatty()` True döndü → etkileşimsiz çağrı soruları okumaya başladı (EOFError).
  Windows'ta ek `GetConsoleMode` kontrolü eklendi (test C06 alt süreçte `stdin=DEVNULL` ile 3 döner).
- `assets/.conn_adt.example`: yalnız yer tutucu; `test_static` artık `.conn*.example`'a izin verir ama değer satırlarının `<...>` olduğunu (sır olmayan
  `ADT_SAP_SSL_VERIFY`/`ADT_SAP_TIER` hariç) ve repoda `*.env` olmadığını denetler. Anahtar sırası `setup_credentials.ANAHTARLAR` ile test edilir.

### 16.5 Profil matrisi (`references/profiles.md`)
Kaynak profil YAML'larından rehber tablo (dolu yalnız `s4_private`) + CLI etiket bloğu. Etiket bloğu `REGISTRY` ve `TIP_PROFIL_KISITI` ile birebir
test edilir (C-PROFİL); matris hücreleri test edilemez → "rehber, canlı test gerekir".

### 16.6 Kütüphane regresyon testleri (`tests/test_lib_regressions.py`)
Kaynak çekirdekteki üç ağsız test aXet yollarına uyarlandı: CSRF soğuk oturum enjeksiyonu (5), push readback biçim/içerik ayrımı + kablolama (2 test,
6+5 iddia), arama tip filtresi sunucuya + tavan 550 + kablolama + kırpma uyarısı (2). Kaynaktaki iki test (ifadeyi testte yeniden yazıp doğruluyordu)
bilinçli alınmadı. `adt_search_objects` bilinen sınırı `tool-catalog.md`'ye yazıldı (yanıtta `truncated` alanı yok).

### 16.7 `test_static` gate-atlatma taraması — yanlış pozitif
Tarama başka bir skill'in `ssl.create_default_context()` çağrısını `create_*` yazma metodu saydı (9d FAIL). Dar stdlib istisnası (`create_default_context`,
`create_connection`, `create_unverified_context`) + pozitif/negatif kontrol eklendi; `create_domain` hâlâ yakalanır.

### 16.8 DTEL etiket uzunluğu
`guardrails.require_label_lengths` (mevcut `ADR_0005_D` ön kontrolünün genişletmesi, yeni kapı değil): kırpılmış etiket > 10/20/40/55 → `ADR_0005_D`
(çıkış 2, ağdan önce). Sınır tablosu DTEL CSV validator'ının `_MAX`'ıyla eşitliği testle zorlanır. Struct → DTEL varlık kontrolü YOK (açık kalem).

### 16.9 Kaynak çekirdek script aileleri — karar
| Aile | Karar | Gerekçe | Tetik (yeniden değerlendirme) |
|---|---|---|---|
| `scripts/cloud/*` (BTP servis anahtarı OAuth) | alınmaz | aXet kütüphanesinde `lib/auth/service_key_auth_provider.py` zaten var; CLI basic-auth dışı yolu kanıtsız | ilk `s4_public`/`btp_abap` projesi (SSO/XSUAA) |
| `scripts/session/lock_manager.py`, `session_manager.py` | alınmaz | uzun ömürlü sunucu için bellek içi oturum/kilit kaydı; aXet CLI çağrı başına süreç. `force_unlock` Yasak C riski | aXet'te kalıcı süreç (daemon) tasarımı |
| `scripts/workflows/write_workflow.py` | alınmaz | Lock→Create→Activate→Unlock sarmalayıcısı; yalnız kendi paketinden kullanılıyor; aXet araçları bu akışı araç içinde uygular | kapısı olan ortak yazma iş akışı ihtiyacı |
| `scripts/utils/console.py` | telafi | UTF-8 akış yeniden yapılandırması CLI başında satır içi var | — |
| `scripts/utils/ddic_aktivasyon.py` | alınmaz | yalnız toplu `populate_*` script'lerinden kullanılıyor. 2026-09-14: toplu yazıcı taşındı (§19) ama bu modül yine alınmadı — aktivasyonu satır başına `adt_activate` / composite araçları yapar (ikinci yazma yolu yok) | toplu (çok-objeli tek istek) DDIC aktivasyonu ihtiyacı |
| `scripts/utils/drift_imzasi.py` | alınmaz | IDE ayar dosyası sapma imzası — aXet'te karşılığı yok | — |
| `scripts/utils/send_mail.py` | alınmaz | e-posta gönderici; SAP temeliyle ilgisiz, ortam değişkenine bağlı | ayrı bildirim ihtiyacı (başka skill) |

### 16.10 Testler ve mutasyonlar
- Yeni: `test_set_description.py` (24) · `test_diag_tools.py` (13) · `test_hints_labels.py` (7) · `test_lib_regressions.py` (9) · `test_conn_tools.py` (11) ·
  `test_cli_gate.py` 1e + `test_12` (12a-12h) · `test_static` 9c2 + stdlib kontrolleri.
- Ölçüm: `python tests/run_tests.py` → **401/401 senaryo satırı OK · 135 unittest, 0 failure, 0 error** (önce 323/323 · 70). `python -m compileall -q scripts` OK.
  `--list` → okuma 24 · yazma 13 · toplam 37.
- **Mutasyon (betik, 2026-09-13; 22/22 — her biri anahtar satırı bozdu, hedef test FAIL oldu, geri alındı, sha256 aynı, hedef test tekrar OK):**
  M01 UNLOCK `finally` kapalı → A09 · M02 kök etiket koruması kapalı → A19 · M03 PUT öncesi inaktifte oto-aktivasyon koruması kapalı → A11 ·
  M04 412 retry öncesi envelope bayt kıyası kapalı → A04 · M05 PUT gönderildi izi yok → A09 · M06 kilit çakışması sınıflaması kapalı → A06 ·
  M07 revisions maske kapalı → D04 · M08 doctor yerel FAIL'de canlı atlama kapalı → D11 · M09 system_info allowlist delindi → D07 ·
  M10 feed hatası ayrımı kapalı → D03 · M11 etiket sınırı +100 → E02 · M12 ddls→classic → H01 · M13 `known_errors_hint` başarıda üretiyor → H04
  (ilk koşuda HAYATTA KALDI: başarı vakası desen metni taşımıyordu; test "412 … EU 510" metinli başarıyla güçlendirildi, sonra FAIL) ·
  M14 switch_tier yer tutucu kontrolü kapalı → C03 · M15 çakışan tier → UNKNOWN kapalı → C04 · M16 Windows konsol kontrolü kapalı → C06 ·
  M17 örnek dosyada gerçek değer → 9c2 · M18 kütüphane soğuk oturum CSRF enjeksiyonu kapalı → LIB CSRF-1 · M19 profiles.md etiketi saptı → PROFİL ·
  M20 `PRECHECK_EXEMPT_TOOLS`'tan `sap_doctor` çıkarıldı → CLI 12a · M21 composite `require_label_lengths` çağrısı kaldırıldı → CLI 12g ·
  M22 CLI `checklist_hint` eklenmiyor → CLI 12d.

### 16.11 DOĞRULANMADI (canlı SAP yok)
- `adt_revisions`: kütüphanenin `<link … rel=".../versions">` deseni gerçek objectstructure yanıtında eşleşiyor mu (yanıt `atom:link` önekli dönerse
  `versions_link_found:false` görünür — araç bunu "kanıt değil" diye işaretler ama sürümleri göstermez); feed `<atom:entry>` önekli mi.
- `adt_object_structure`: bileşen öznitelikleri `adtcore:` ad alanında mı; `version=inactive` parametresinin uçta kabulü.
- `adt_system_info`: discovery `collection` öğeleri; `language` alanı dolu mu.
- `sap_doctor`: `check_logon` 200 + HTML ayrımı gerçek SSO sayfasında; `fetch_csrf_token(force_refresh=True)` gerçek oturumda.
- `adt_set_description`: DDLS dışı tiplerde envelope biçimi (açıklama kök etikette mi), Content-Type, kilit yanıtında `CORRNR`, 412 gövdesi;
  class/bdef/srvd/ddlx/dcl'de PUT sonrası inaktife düşme; `activate_object(name, url)` envelope URL'iyle; `?version=active` readback'in envelope'ta
  açıklamayı taşıması; `descriptionTextLimit` özniteliği.
- `switch_tier`/`setup_credentials`: gerçek PowerShell konsolunda `getpass` + `GetConsoleMode` davranışı (test sahte girdiyle koşar).
- Profil matrisi hücrelerinin tamamı.

### 16.12 Açık kalemler
- İş türü alt-tür ayrımı (abstract entity, custom entity vb.) ve ATC Prio-1 ipucu ekseni kaynak kancadan alınmadı.
- `adt_search_objects` yanıtına `truncated` alanı eklenmedi (yalnız `client_log`); araç sözleşme değişikliği ayrı karar.
- Struct → DTEL varlık kontrolü (artefaktsız) yok.
- `tests/test_cli_gate.py` 10s senaryosunda müşteri önekli demo adı (`ZSD001_*`) duruyor (bu turdan önce) → nötr `ZCA000_*`'a çevrilmeli.
- `adt_revisions` link deseni canlı ölçümden sonra `atom:link` biçimini de kapsayacak şekilde genişletilmeli mi — ölçüm bekliyor (tahminle eklenmedi).

## 17. Hüküm dürüstlüğü taşıması (2026-09-14)

### 17.1 Ne değişti
| Konu | Nerede | Davranış |
|---|---|---|
| Aktivasyon hükmü tek kaynak | `lib/sap_adt_lib.py`, `lib/rap_service.py`, `tools/atom.py` | Gövde hükmü True/False/None. Bayraksız ya da yalnız `generation` taşıyan gövde = None → ayırt edici worklist sondası; sonda ölçemezse `success:false` + `dogrulanamadi:true` (ölçemeyen sonda asla başarı değil). FUGR faz-2 FF girdisi `parentUri` ile. |
| `syntax_check` | `lib/sap_adt_lib.py`, `lib/sap_client.py` | Kontrol koşmadıysa `valid:None` (NOT MEASURED); "hata var" uydurulmaz. |
| Push ön kontrolü | `lib/sap_client.py`, `tools/atom.py` | Sözdizimi ön kontrolü ölçülemediyse `syntax_precheck:"olculemedi"` + `sozdizimi_sebep`; araç yanıtı `syntax_precheck_notice`. |
| Sorgu araçları | `tools/query.py`, `lib/sap_client.py` | SAP hata gövdesi (`sap_error`); `truncated` kesin (`row_limit+1` sondası); TADIR 5'li parça (ölçülemeyen ad `tadir_deleted:null` + `ok:false`, sayım yok); FM arama takma adı (`FUNC`→`FUGR/FF`, `type_filter_dropped`); where-used paket ayrımı (`where_used_belirsiz`); kanonik worklist ayrıştırma (`worklist_govdesi_degil`). |
| Reviewer FUGR/FM | `_reviewer.py` | `fugr`/`func` → None bilinçli; pinlendi. |
| Gate durum satırı | `lib/validators/run_review.py`, `_gate_status.py` | Satır-başı `AXET-GATE-STATUS:` olup biçime uymayan satır → `measured=false reason=bicim-bozuk` (geçerli satırla birlikte olsa bile). |
| Test yalıtımı | `tests/test_new_write_tools.py` | `YeniYazmaYollari` sınıfı ADT_* ortam değişkenlerini kaldırır; cwd'deki bağlantı dosyası kapı birim testini etkilemez. |

GEVŞETME NOTU: TADIR parçalama ölçülen yüzeyi genişletir ve fail-closed kalır (ölçülmeyen ad hiçbir zaman "silinmemiş" sayılmaz).

### 17.2 Testler ve ölçüm
- Yeni: `test_verdict_activation.py` (49) · `test_verdict_push_precheck.py` (11) · `test_verdict_query_tools.py` (36) · `test_verdict_reviewer_fugr.py` (5) · `test_gate_status_sozlesme.py` test_7/test_8.
- Kontrol grubu (önce → sonra): push ön kontrolü 5 FAIL → 11/11 · sorgu araçları 26/36 FAIL → 36/36 · gate satırı test_7/test_8 FAIL (BLOCKER gate `exit 0 · PASS`) → 8/8 · E3 sahte bağlantı kökünde FAIL (`conn_env_mismatch`) → OK.
- `python tests/run_tests.py` (sahte bağlantı dosyalı kökten, izole TMP): **575/575 senaryo · 244 unittest, 0 failure**. İzole TMP'de kalan tek girdi `node-compile-cache` (Node çalışma zamanı), test kumu 0.

### 17.3 Mutasyonlar (hepsi yakalandı, sha256 geri yükleme eşit)
Aktivasyon M1 · M2a · M2b · M3 · M4 · sorgu MQ1-MQ5 · MS1-MS4 · MU1-MU2 · MV1-MV3 · MX1 · reviewer MR1-MR3 · gate satırı MG1-MG3.

### 17.4 Alınmayanlar
~~Toplu `populate_*` `--force-recreate`~~ (2026-09-14 taşındı → §19) · `where_used`/`worklist_audit`/`push_object`/`syntax_check` CLI satırları (CLI yok) · proje açılış `[ATLA]` notu (`new_project.py` zaten `--force` önermiyor) · pre-commit onarım metni (bağımlı imza aracı yok) · fixture kum temizliği (`tests/_helpers.py` zaten salt-okur dosyayı siliyor; ölçüm §17.2).

### 17.5 DOĞRULANMADI
- Canlı SAP: worklist sondası gövde biçimi, FUGR faz-2 FF, `sap_error` gövdeleri (400 XML / 500 HTML), TADIR parça boyutu, FM takma adı sunucu yanıtı.
- `rap_service._aktivasyon_yaniti_ok` ayrı birim testi yok.
- TADIR satırı olmayan ad `tadir_deleted:false` kalır (davranış değişmedi; açık kalem).
- `adt_search_objects` yanıtında `truncated` hâlâ yok (§16.12 açık).

### 17.6 Bağımsız inceleme sonrası test boşlukları (2026-09-14)
İnceleme iki parçada WARNING verdi (fail-open yok); bulguların hepsi kaçan mutasyonlu test boşluğuydu. Önce/sonra aynı betikle ölçüldü:
önce 5/5 mutasyon kaçtı → sonra X1 · G1 · B4 · B3 · E3M yakalandı.

| Boşluk | Yeni test | Yakalayan mutasyon |
|---|---|---|
| HTTP hata sonucu (anahtarsız sözlük) sondalanıp temiz worklist'le başarıya dönmemeli | `test_verdict_activation` K1 (POST 500) · K2 (POST 403) · K3 kontrol | X1 (`'yok'` varsayılanı kaldırıldı) → K1, K2 |
| Biçimi bozuk satır ÖNCE, geçerli SONRA | `test_gate_status_sozlesme` test_7 ters sıra | G1 (yalnız son satır) → test_7 |
| `rap_service._aktivasyon_yaniti_ok` karar tablosu | `test_verdict_activation` L1 (11 satır) | X3b → L1c · X3c → L1d/L1i · X3d → L1k |
| TADIR ad süzgeci dalı | `test_verdict_query_tools` T7 kontrol (boş liste) · T8 (yalnız süzgeç) · T9 (karışık) · T10 (boş 200 gövde) | B4 → T8 |
| `body_excerpt` 500 bayt sınırı | `test_verdict_query_tools` S10 · S10b kontrol | B3 → S10 |
| E3 yalıtımı koşum kipine bağlıydı | `test_new_write_tools` E3b (kirli ADT_* ortamı belirlenimli kurulur; temizliksiz kontrol `conn_env_mismatch`) | E3M (temizlik kapatıldı) → E3b dört kipte de FAIL |

- **Eşdeğer mutasyonlar (öldürülemez, kanıtlı):** X3 (`executed is True` → `is not False`) ve X3e (`_hukmu_kesinlestir` `return executed is True, errs` → `return executed, errs`). `_hukmu_kesinlestir` 200/202'de her dalda bool döner; None yalnız hata mesajıyla birlikte geçebilir ve o durumda `not errs` kararı zaten False yapar. Diğer HTTP durumlarında durum koşulu False'tur.
- **E3 ölçümü:** döngüsüz testte "önce FAIL" yalnız `run_tests.py -k` (tüm modüller aynı süreçte keşfedilir, `sap_adt_lib` cwd `.conn_adt`'sini yükler) + sahte bağlantı dosyalı kökte görülür; tek modül koşumunda görülmez. E3b bu bağımlılığı kaldırır.
- ENQU aktivasyon hata mesajı artık gövde bayrağını ve kesin hükmü ayrı yazar (`atom.py`).

### 17.7 Açık kalemler (incelemeden; düzeltilmedi)
- `adt_search_objects` FM takma adında `/fmodules/` URI koruması yok (canlı ölçülemedi).
- `run_review`: küçük harfli önek ya da girintili `measured=false` satırı → beyan None → rc 0 iken PASS (bu taşımadan önce de böyleydi).
- BOM ile başlayan geçerli satır sahte SKIP üretir.
- Karışık worklist'te süzgece takılan adın süzgeç sebebi çıktıya yazılmıyor.
- Worklist kullanıcı başına kapsam ve tip dizesi eşliği canlıda doğrulanmalı.

## 18. Kilit politikası — otomatik kilit temizleme kaldırıldı (2026-09-14)

Tek politika: araç/model kilit TEMİZLEMEZ; yalnız KENDİ aldığı handle'ı her yolda bırakır; çakışmada durur ve SM12
tarifi verir (`lib/sap_adt_lib.py` `KILIT_CAKISMA_TARIFI`, dil `tools/msgclass.py`/`tools/description.py` `_SM12` ile hizalı).

### 18.1 Gerekçe ve kaynaklar
- Kesin Yasak C (enqueue kilidi silme) — `core/sap/00-sap.md` Yasak C · kaynak çekirdek ADR 0005 C4.
- aXet kendi içinde tutarsızdı: mesaj sınıfı aracı temizleme yardımcısını bu gerekçeyle almamıştı (§15.3), genel akışta
  iki otomatik çağrı duruyordu.
- Çare işe yaramıyordu: aynı kullanıcı kilidi varken yeniden kilit `403` alır, lock→unlock döngüsü tamamlanmaz — yalnız
  mesaj sınıfında kayıtlı (`lib/sap_client.py` `create_message_class` notu 2026-07-15 · `sap-cds-ddic/references/message-class.md`
  §3.2), diğer tiplerde canlıda doğrulanmadı; `EU 510`'un ölçüldüğü çağrı aktivasyondur (K-07; §18.8 L4) · süreç ölümünden kalan kilidi kurtaramaz
  (kaynak çekirdek lessons-learned PATTERN #13) · istisnayı yutup `False` döndüğü için başarısızlık görünmezdi (kaynak
  çekirdek known-errors). Çevrimdışı ölçüm (bu tur, `test_kilit_politikasi` L2 eski kod): aktivasyon 403'ünde yardımcı 3
  LOCK POST'u gönderdi, hepsi düştü, sonuç yalnız "Failed to clear" metniydi.

### 18.2 Ne değişti (davranış)
| Yol | Önce | Sonra |
|---|---|---|
| `sap_client.push_object` kilit öncesi | `is_object_locked` "kendi kilidim" derse lock→unlock temizleme döngüsü | ön adım yok; çakışma `lock_object`'te dürüst hata |
| `sap_adt_lib._handle_activation_403` aynı kullanıcı | temizle + aktivasyonu 1 kez yeniden dene | HTTP çağrısı YOK, yeniden deneme YOK; `success:false` + sahip + tarif |
| `sap_adt_lib.lock_object` aynı kullanıcı 403 | handle'SIZ `_action=UNLOCK` + relock; tutmazsa `NO_LOCK_SUPPORT` → KİLİTSİZ PUT | `SAPLockError` (`lock_owner`, 403, tarif). `adt_push_source` düz yolunda iç içe: `result.error_type:"SAPLockError"` + `result.error`; üst seviye `error:"locked"`/`lock_owner` yok (§18.8 L2) |
| `lock_object` başka kullanıcı 403 | `SAPLockError` ("SM12'de EADT_LOCK'u bırak") | `SAPLockError` + tarif (başkasının kilidini bırakma önerisi yok) |
| `lock_object` tüm stratejiler 404 / 200 handle'sız | `NO_LOCK_SUPPORT` / `IMPLICIT_LOCK` | **değişmedi** (kontrol testleri L1n, L1i) |
| `unlock_object` tüm stratejiler düştü | `True` | `False` (istisna yok). Ölçüldü: hiçbir çağıran dönüş değerini kullanmıyordu |
| `push_object` yükleme hatası | UNLOCK iki kez (hata dalı + `finally`) | tek UNLOCK (handle bırakılınca `None`) |
| `push_object` UNLOCK düşerse | `lock_released` hep `True` | `lock_released:false` + SM12 uyarısı |
| `push_object` kilit hatası mesajı | koşulsuz "Source was uploaded successfully" | `source_uploaded`'a göre dürüst metin + tarif |
| temizleme yardımcısı | vardı | silindi; `allow_no_transport` yorumu güncellendi (parametre API için kaldı) |

### 18.3 Kilit alan yollar — envanter (yol × başarıda bırakır × hata/istisnada bırakır)
| Yol | Başarı | Hata/istisna |
|---|---|---|
| `lib/sap_client.py` `_push_method_includes` :377 | `finally` :398 | `finally` :398 |
| `lib/sap_client.py` `push_class_include` :692 | aktivasyon öncesi :704 | `except` :726 (`finally` yok; açık kalem) |
| `lib/sap_client.py` `push_object` :880/:899 | aktivasyon öncesi :970 | hata dalı :942 + `finally` :1266 (önce: çift UNLOCK) |
| `lib/sap_client.py` `push_object` B.5 :1142 | :1147 | iç `finally` :1159 |
| `lib/sap_client.py` `delete_object` :1378 | `finally` :1427 | `finally` :1427 |
| `lib/sap_adt_lib.py` `_verify_and_return_lock` CORRNR uyuşmazlığı | — | `_release_lock_after_failure` :2660 |
| `lib/sap_adt_lib.py` `create_structure` :5792 | `finally` :5809 | `finally` :5809 |
| `lib/sap_adt_lib.py` `set_function_module_source` :6633 | `finally` :6715 | `finally` :6715 |
| `lib/sap_adt_lib.py` `create_behavior_definition` :7312 | `finally` :7334 | `finally` :7334 |
| `tools/atom.py` `_push_bdef_kaynak` :1468 | `finally` :1491 | `finally` :1491 (test A1) |
| `tools/description.py` `tur` :287 | `finally` :318 | `finally` :318 (test_set_description 09) |
| `tools/msgclass.py` `adt_msgclass_write` :327 | `finally` :362 | `finally` :362 (M5) |
| `lib/sap_adt_lib.py` `object_lock` → `lock_object_with_retry` :3508 | `finally` | — **üretimde çağıranı yok** |

`NO_LOCK_SUPPORT` üreten: yalnız `lock_object` tüm-404 dalı (aynı kullanıcı 403 üreticisi kaldırıldı). `IMPLICIT_LOCK`
üreten: `_verify_and_return_lock` (200 + handle yok). Tüketenler (değişmedi): `set_object_source`, `delete_object`,
`unlock_object` (bu değerlerde istek göndermez), `push_object`, `delete_object` (sap_client). Obje tipine bağlı bir dal
yok; değer sistemin kilit ucuna bağlıdır.

### 18.4 Süreç modeli (kapsam beyanı)
- Kalıcı ADT oturumu tutan sunucu yok: `_app.py` MCP kurmaz; `sap_adt_cli.py` `main` çağrı başına TEK araç koşar ve
  çıkar. `tools/atom.py` `_get_client` istemciyi süreç-global önbellekte tutar (:328) → aynı süreçte birden çok yazma
  (ör. toplu satır işleyen bir araç) aynı stateful oturumu paylaşır. Bayat handle sınıfı bu yüzden önemlidir: başarısız
  yazmanın kendi kilidini bırakması (18.3) bunu tek araç çağrısı içinde kapatır; satırlar arası davranış populate
  tarafında ayrıca test edilmeli (lider D3'e iletti).
- Kilit tutarken sürecin öldürülmesi (PATTERN #13) **kodla önlenemez**; çare kullanıcının SM12'si (K-09). Çare uydurulmadı.

### 18.5 Testler ve mutasyonlar
- Yeni: `tests/test_kilit_politikasi.py` (15 test). Fail-first eski kodda **8 FAIL** (T0, L1, L2, L3, S1, S2, S4, S5) ·
  7 kontrol OK (L1k, L1n, L1i, L2k, L3k, S3, A1). Yeni kodda 15/15.
- Hedefli yeşil (sahte bağlantı dosyalı kökten, izole TMP): `DomainVeMesajSinifi` 14 (M5 dahil) · `AciklamaAraci` 24
  (EU 510 vakası dahil) · `PushOnKontrol` 11 · `LibAktivasyon` 5 · `LibRegresyon` 9 · `Statik` 3 · `Ipuclari` 5.
  Tam takım koşulmadı (lider merge sonrası).
- Mutasyonlar (7/7 yakalandı, sha256 geri yükleme eşit): M1 push'a temizleme çağrısı → T0,S1,S2,S5 · M2 `finally`
  UNLOCK kapalı → S3,S4 · M3 aktivasyon 403'e handle'sız UNLOCK → T0,L2 · M4 `unlock_object` hep True → L3 · M5
  handle `None`'a çekilmiyor → S1 · M6 atom BDEF `finally` kapalı → A1 · M7 aynı kullanıcıda `NO_LOCK_SUPPORT` → L1.
- Sınır: M5'i yalnız S1 yakalar; hata dalındaki UNLOCK tek başına kaldırılırsa `finally` bıraktığı için test geçer
  (bilinçli çift savunma, eşdeğer davranış).

### 18.6 DOĞRULANMADI
- Canlı SAP: aynı kullanıcı kilidinde kilit ucunun gerçek 403 gövdesi (sahip deseni eşleşmesi, `EU 510` kodu taşıyıp
  taşımadığı) · aktivasyon 403 gövdesi · UNLOCK stratejilerinin hepsinin düştüğü gerçek durum.
- Sahip okunamayan 403 hâlâ "yetki" sayılıp sonraki stratejiye geçer ve sonunda `LOCK_FAILED_NOT_404` `SAPLockError` olur
  (davranış değişmedi).

### 18.7 Açık kalemler
- `lock_object_with_retry` / `object_lock`: üretimde çağıranı yok; `object_lock` transport vermediği için her zaman
  `TRANSPORT REQUIRED` ile düşer ve kör 3 deneme + bekleme yapar (kilit çakışmasını da geçici sayar). Dokunulmadı (lider kararı).
- `push_class_include` ve `delete_object` `unlock_object`'in `False` dönüşünü okumuyor ("Object unlocked" yine basılır).
- `lock_object` 409 mesajı kullanıcıya "SM12 → enqueue lock'u sil" diyor (kullanıcıya yönelik; K-05 ile uyumlu, değiştirilmedi).
- **`unlock_object` `False` dönüşünü okumayan diğer yollar (bug gate L3; kayıt, bu dalda kod değişikliği YOK; satırlar 18.8 sonrası
  koddan doğrulandı).** Regresyon değil — önceden `unlock_object` hiç `False` dönemiyordu:
  - `lib/sap_client.py` `_push_method_includes` `finally` :398-400 — dönüş okunmaz, koşulsuz `[FALLBACK] Unlocked.` basar.
  - `lib/sap_client.py` `push_object` B.5 başarı :1157-1158 — dönüş okunmaz, `fb_lock2=None` → iç `finally` (:1169) tekrar
    denemez; iç `finally` :1169 da dönüşü okumaz.
  - `lib/sap_adt_lib.py` `_release_lock_after_failure` :2660-2661 — dönüş okunmaz, `ok_message`'ı (`[OK] Lock released to
    prevent ghost transport.` :2731) koşulsuz basar.
  - `lib/sap_adt_lib.py` `create_structure` `finally` :5829 · `create_behavior_definition` `finally` :7354 — dönüş okunmaz.
  - `lib/sap_adt_lib.py` `set_function_module_source` `finally` :6735 — ham `session.post` UNLOCK (handle'lı), durum kodu okunmaz.

### 18.8 Bug gate WARNING düzeltmeleri (2026-09-14, `4bc95a5` üstüne)
Girdi: bug gate raporu (M1, M2, L1-L4 + öneri). Bu bölümdeki satır numaraları düzeltme SONRASI koddandır; §18.3 envanterinin
satırları `4bc95a5`'e göredir (`push_object` bloğu Bug-11 yorumuyla ~+9 kaydı).

**M1 · Bug-11 bayat transportla otomatik ikinci kilit.**
- Kod: `lib/sap_client.py:883-893` Bug-11 yalnız `lock_owner is None and status_code == 409` (= `_verify_and_return_lock`'un
  sahipsiz CORRNR uyuşmazlığı) iken koşar · `lib/sap_adt_lib.py:2841-2847` `lock_object` başında `_last_lock_corrnr`,
  `_last_lock_is_link_up`, `_last_lock_effective_transport` = `None` · docstring (:2807-2825) koda eşitlendi ("kilitsiz devam" yok).
- Blast radius (grep): okuyanlar `sap_client.py:378` (`_push_method_includes`), `:694` (`push_class_include`), `:890-891`
  (Bug-11), `:926` (`push_object` etkin transport), `:1153` (B.5). Bug-11 dışındakilerin hepsi `lock_object` BAŞARILI
  döndükten sonra okur ve `or transport` ile düşer. Yazanlar: `_verify_and_return_lock` :2713-2715 (200) ve
  `set_function_module_source` :6694-6696 (kendi LOCK'u, `lock_object`'i çağırmaz → sıfırlamadan etkilenmez).
- Kırmızı → yeşil (`.tmp/kilit-fix/01_failfirst.txt` → `06_yesil.txt`, gerçek `lock_object` + gerçek `push_object`, aynı
  süreçte önce `TESTK900222` ile başarılı kilit):
  - M1a aynı kullanıcı 403: LOCK corrNr `[900001×3, 900222×3]` + sahte "İSTENEN TRANSPORT KABUL EDİLMEDİ" → `[900001×3]`, uyarı yok, etkin alan `None`.
  - M1b başka kullanıcı 403: aynı kırmızı → yeşil.
  - M1c HTTP 409 (sahipsiz): `[.., 900222×3]` → yalnız `900001` (bunu koşul değil sıfırlama kapatır).
  - M1d tüm stratejiler 404 (`NO_LOCK_SUPPORT`): PUT `TESTK900222` ile gidiyordu → istenen `TESTK900001` ile (aynı kök, bu işi etkiliyor → düzeltildi).
  - M1e `push_object` sözleşmesi, sıfırlamayan sahte kilit + 403 sahipli: LOCK 1 (koşulun tek başına kanıtı; mutasyon N1 bununla yakalanır).
  - M1k KONTROL meşru Bug-11 (200 + CORRNR `TESTK900333` ≠ istenen): önce ve sonra yeşil — LOCK `[900001, 900333]`, PUT `HB/900333`, uyarı basılır, tüm UNLOCK'lar handle'lı.

**M2 · hata dalında UNLOCK False → handle tutulur.** Kod doğruydu, test eksikti. `tests/test_kilit_politikasi.py` S6:
`put_istisnasi` + `unlock_donus=False` → `lock_released is False`, UNLOCK 3 (hepsi `LOCK1`). Mevcut kodda yeşil; kırmızısı
MU8 mutasyonunda (aşağıda).

**L1 · URL sorgu dizesiyle handle'sız UNLOCK.** `_Oturum._k` URL sorgusunu `params`'a katar (açık `params` ezer; T0k) ·
`kilit_ihlalleri` `lockHandle`'sız `_action=UNLOCK` içeren dize sabiti ve f-string'i (sabit parçaları birleşik) bulgu sayar;
docstring/belge satırı ve yorum sayılmaz (negatif kontroller T0 içinde). Fail-first: T0 pozitif kontrolü `[]`, T0k
`[None, 'LOCK']` → yeşil. Üretim taraması: 92 dosya, 0 bulgu. Kapsam dışı: parçalara bölünmüş sabit (`"_action=" + "UNLOCK"`),
çalışma anında üretilen dize.

**L2 · belge ↔ kod.** Belge koda eşitlendi (`known-errors-adt.md` K-09 "Araç çıktısı", `foundation-ops.md` §5). Koddan doğrulanan
yerler: düz `adt_push_source` (`push_object` istisnayı yutar, `sap_client.py` dış `except`) → `ok:false` ·
`result.error_type:"SAPLockError"` · `result.error` · `result.source_uploaded:false`; üst seviyede `error`/`lock_owner` yok
(`tools/atom.py` üst `error:"push_failed"`'ı yalnız include/BDEF/FM dalında yazar); `error:"locked"` + üst `lock_owner` yalnız
`_err_from_exc` (atom :448-484) yolunda. `result.lock_released:false` `ok:true` ile yan yana: ÖLÇÜLDÜ
(`.tmp/kilit-fix/07_ok_true_lock_released_false.txt`: `success=True activated=True lock_released=False`).

**L4 · K-07 ↔ yeni EU 510 metinleri.** Prior-art: K-07 (aktivasyonda ölçüldü) · `sap-cds-ddic/references/message-class.md` §3.2 ve
kaynak çekirdek `adt-message-class.md` §27 başı (MSAG: create sonrası yazma/silme `403 EU 510`, yeniden kilitle-bırak yine
403; hangi çağrının döndürdüğü ayrı yazılmamış) · `sap_client.py:2789` notu · `adt-programs.md:190` (textpool, "EU 510
same-user" — gövde ölçümü yazılı değil). Metinler daraltıldı: `sap_adt_lib.py:3058-3071` (yorum + mesaj "aynı kullanıcı
kilidi (403)"), modül yorumu, `_handle_activation_403` docstring'i, `sap_client.py:822-823`, K-07, K-09, `foundation-ops` §5, §18.1.
- **Yan etki bulundu ve düzeltildi (bu işten doğdu):** düz push yanıtında üst seviye `error` olmadığı için `known_errors_hint`
  kilit çakışmasını yalnız `client_log`'daki "EU 510" metninden K-07'ye bağlıyordu; daraltma bunu düşürdü (ÖLÇÜLDÜ
  `.tmp/kilit-fix/04_hints_olcum.txt`: eski → K-07, yeni → yalnız İndeks, başka kullanıcı → hiç yoktu). `scripts/sapadt/hints.py:135`
  tarif metni (`enqueue kilidini SİLMEZ`) → K-09. H1 (gerçek push log'u, aynı + başka kullanıcı): `İndeks` → `K-09`.

**Öneri (aktivasyon öncesi unlock False).** Ölçüldü (`.tmp/kilit-fix/03_probe_aktivasyon.txt`): unlock False dönünce aktivasyon
YİNE koşuyor; aktivasyon 403 verirse mesaj "SENİN kullanıcınla kilitli … açık düzenlemeyi kapat" diyor, oysa kilit aracın kendi
tutulan handle'ı olabilir. Tek satırlık güvenli kısım yapıldı: `sap_client.py:985-986` uyarı metni bunu söyler. Aktivasyonu
atlamak davranış değişikliği (sonuç alanları + mesaj) → açık kalem.

**Mutasyonlar** (`.tmp/kilit-fix/mutasyon_kilit_fix.py`, taze kopya üzerinde, her birinde sha256 geri yükleme eşit; mutasyonsuz kopya 24/24):
| Mutasyon | Yakalayan |
|---|---|
| MU1 aynı kullanıcı 403'te URL-sorgulu handle'sız UNLOCK | T0, L1, L1k |
| MU2 aktivasyon 403'te lock→unlock | L2 |
| MU3 push öncesi lock→unlock | S1, S2, S3, M1k |
| MU6 aynı kullanıcıda IMPLICIT_LOCK | L1, M1a, H1 |
| MU8 hata dalında unlock False'a rağmen handle None | S6 |
| MU9 aktivasyon öncesi unlock False'a rağmen handle None | S4 |
| M1 push'a temizleme çağrısı | T0, S1, S2, S5, M1a-d, M1k, H1 |
| M2 `finally` UNLOCK kapalı | S3, S4, S6 |
| M3 aktivasyon 403'e handle'sız UNLOCK | T0, L2 |
| M4 `unlock_object` hep True | L3 |
| M5 hata dalında handle None'a çekilmiyor | S1 |
| M6 atom BDEF `finally` kapalı | A1 |
| M7 aynı kullanıcıda NO_LOCK_SUPPORT | L1, M1a, H1 |
| N1 Bug-11 koşulu geri | M1e |
| N2 `_last_lock_*` sıfırlaması yok | M1a, M1c, M1d |
| N3 N1+N2 (gate M1 hâli) | M1a, M1b, M1c, M1d, M1e |
| N4 hints K-09 kuralı yok | H1 |

**Davranış değişiklikleri:** (1) Bug-11 ikinci kilidi yalnız sahipsiz 409'da · (2) `lock_object` sonrası `_last_lock_*` yalnız
BU çağrının 200 yanıtından gelir; `NO_LOCK_SUPPORT`/hata sonrası çağıranlar istenen transport'a düşer · (3) aynı kullanıcı kilit
mesajı "EU 510 sınıfı" demez · (4) kilit çakışması metni bilinen-hata ipucunda K-09'a düşer (başka kullanıcı dahil) · (5) aktivasyon
öncesi unlock uyarı metni · (6) test düzeneği: sahte oturum URL sorgusunu kaydeder, T0 dize/f-string tarar. `tests/test_kilit_politikasi.py`
15 → 24 test (yeni: T0k, S6, M1a, M1b, M1c, M1d, M1e, H1, M1k).

**DOĞRULANMADI:** canlı SAP'de meşru Bug-11 vakası (yalnız sahte oturum) · kilit adımında aynı kullanıcı 403 gövdesi ve kodu ·
`known_errors_hint`'in CLI giriş noktasından (`sap_adt_cli.py:243`) tetiklendiği — H1 fonksiyonu doğrudan, çıkış kodu 1 ile çağırır ·
aynı süreçte iki kilit alan gerçek araç akışı (D3 populate; gate: tek CLI çağrısında tetiklenmez).

**Açık kalemler:** (1) push kilit alanlarını üst seviyeye taşıma (`error:"locked"`, `lock_owner`, `lock_released`; `push_object`
`SAPLockError.lock_owner`'ı `result`'a yazmıyor) — yanıt sözleşmesi değişikliği, dal kapsamı dışı; `ok:true` + `result.lock_released:false`
hâlinde üst `ok`'a bakan çağıran kalan kilidi görmez · (2) aktivasyon öncesi unlock False iken aktivasyonu koşmama · (3) 18.7'deki
L3 kaydı ve önceki kalemler.

## 19. Toplu yazıcı (`populate`) + `adt_get(enqu)` + domain tip bilgisi fail-closed (2026-09-14, D3)

### 19.1 Ne geldi
| Dosya | Ne |
|---|---|
| `scripts/sap_adt_populate.py` (yeni) | ince giriş: UTF-8, `sys.path`, `sapadt.populate.main` |
| `scripts/sapadt/populate.py` (yeni) | CSV/`.cds` yükleyiciler (fail-closed, tüm bulgular birlikte) · satır planı · ön geçiş · yürütücü · çıkış kodları |
| `scripts/sap_adt_cli.py` | `main` gövdesi `on_kontrol` + `calistir`'a çıkarıldı (bayt-eşit davranış, §19.3) |
| `scripts/sapadt/tools/atom.py` | `adt_get` enqu dalı `_enqu_varlik_oku` (salt GET, üç değerli) + docstring |
| `scripts/sapadt/lib/sap_adt_lib.py` | `DomainTipBilgisiHatasi` / `DomainBulunamadi` / `DomainTipBilgisiOlculemedi` + `_get_domain_typeinfo` fail-closed |
| `scripts/sapadt/lib/sap_client.py` | `create_dataelement` domain tip hatasını yutmaz, yeniden fırlatır |
| `tests/test_populate.py`, `tests/test_populate_hat.py` (yeni) | orkestra (sahte `cagir`) + gerçek hat (`calistir` → kapı → araç → reviewer → sahte SAP) |

### 19.2 Tasarım
- **İkinci yazma yolu yok.** Her adım `sap_adt_cli.calistir(tool, args, proj, sap_write, scope, reason, intake)` — CLI'nin tek araç çağrısıyla aynı
  kapı (`gate.check_write`), profil, reviewer, istisna eşlemesi ve denetim logu.
- **Ön geçiş:** koşumdan önce her satırın her planlı çağrısı `on_kontrol`'den geçer (`--force-recreate` varsa `adt_delete` dahil). Tek red →
  tüm satırlar `islenmedi`, SAP'ye 0 çağrı, red logda, çıkış 2 `prepass_gate_rejected`. `--dry-run` burada durur (çıkış 0).
- **Üç değerli varlık:** sonda `True`/`False`/ölçülemedi. Ölçülemedi → satır HATA, yazma yok. Var → `atlandi` (+ tek-ad force önerisi);
  `enqu` varsa her koşulda `atlandi` (güncelleme/silme yolu yok).
- **Force:** yalnız `domain`/`dtel`/`cds` + `--only <TEK AD>`. `delete_verified` True → devam · exit 0 ama doğrulanamadı → koşum DURUR ·
  kapı reddi → satır HATA · başarısız DELETE → yeniden sonda: var → HATA, yok → HATA (tutarsız), ölçülemedi → koşum DURUR.
- **Satır hatası ≠ koşum durması:** yazma adımında sonucu bilinmeyen hata (araç istisnası `calistir` içinde `unexpected`e çevrilir;
  bağlantı/zaman aşımı; HTTP 502/503/504; composite `steps.*` ve `push_object` `error_type` dahil), kimlik reddi (hesap kilidi riski),
  çağrı hattının kendisinin istisnası ya da silme sonucu bilinmiyor → DUR, kalanlar `islenmedi`, `result.stop` nerede/hangi kod/hangi
  gerekçe. Bilinen red satırda kalır, koşum sürer. Sınıflandırma tablosu ve kanıt: §19.10.
- **Çıkış:** 0 · 1 (`partial_failure`/`run_stopped`; atlanan ≠ başarı, kısmi başarı 0 değil) · 2 · 3 · 4 (`--fail-on-skip` + atlanan).
- **Geçici reviewer CSV'leri** `tempfile.mkdtemp` altında; `finally` ile silinir, `temp_dir_removed` yanıtta.
- **Kilit:** populate kilit almaz/bırakmaz/temizlemez (statik test T3). Kilit çakışması mesajı → satır HATA + SM12 tarifi, koşum devam.
  Kilit alan araçların hata dalı: `push_object` yükleme hatası unlock (`sap_client.py` ~941-946) + dış `finally` (~1247-1266);
  `msgclass_write` ve `delete_object` `finally`.

### 19.3 `calistir` çıkarımı — bayt kıyası
13 senaryo (liste, bilinmeyen araç, bozuk JSON, imza, okuma/yazma ağsız, opt-in yok, bayrak yok, std ad, profil, preflight, QA tier, araç
usage hatası) önce/sonra stdout + çıkış kodu: **13/13 bayt-eşit** (rc 0/3/3/3/1/2/2/1/2/2/2/2/3). `test_cli_gate` 118/118 · `test_inprocess_guards` 20/20.

### 19.4 `adt_get(enqu)`
Kullanıcı onayı (seçenek A). `include_source:true` → `unsupported_type` (ağ yok) · 200 → `exists:true` · 404 → `exists:false` · diğer/istisna →
`ok:false` + `exists_probe`. Salt GET; ADR 0005-C: kilit açan/silen yol yok. Araç sayısı değişmedi (`--list` okuma 24 · yazma 13 · toplam 37;
yalnız `adt_get` açıklaması değişti). Önceki kapsam beyanı "enqu için bağımsız okuma sondası yok" bununla kapandı.

### 19.5 Davranış değişikliği — domain tip bilgisi (lider kararı)
Eskiden `_get_domain_typeinfo` okuyamadığı domain'de sessizce `('CHAR','0','0')` dönüyor, DTEL POST'u yanlış tiple gidiyordu. Şimdi:
404 → `DomainBulunamadi` ("domain bulunamadı: <AD> … domain adı verin") · istisna / 404 dışı kod / eksik alan / sayı olmayan uzunluk →
`DomainTipBilgisiOlculemedi` ("ÖLÇÜLEMEDİ … bu 'domain yok' demek değildir"). İkisinde de POST gönderilmez. `adt_dtel_create` bunu
`steps.create = {error: validation_error, message}` olarak görür. Yerleşik tip (DATS/TIMS) desteği EKLENMEDİ.
Etki alanı (grep, tüm worktree): `_get_domain_typeinfo` ← `lib.create_dataelement` ← `SAPClient.create_dataelement` ← yalnız `composite.adt_dtel_create`.

### 19.6 Kaynaktan bilinçli sapmalar
Tablo türü yok (tablo kabuğu reçetesi yok — D2 ile birlikte, ilk canlı başarıdan sonra değerlendirilir) · CDS ad ön-ek whitelist / sprint gate /
TD spec ön kontrolü alınmadı · msgno `zfill` yok (3 hane zorunlu) · DTEL `datatype/length/decimals` kolonları yok sayılır (tip domain'den) ·
`type_kind` yalnız `domain` · etiket/açıklama üretilmez (4 etiket boşsa çıkış 3) · force yalnız tek ad · enqu/msag için force yok ·
CSV sıkı (bilinmeyen kolon/fazla alan/yinelenen başlık reddedilir; UTF-8 dışı kodlama `csv_unreadable`) · `--fail-on-skip` çıkışı 4 (kaynakta 3 = kullanım ile çakışıyordu) · transport yaratılmaz.

### 19.7 Testler ve mutasyonlar
- `tests/test_populate.py` (orkestra, sahte `cagir`) + `tests/test_populate_hat.py` (gerçek hat: `KapiReddi` K1-K8 · `ReviewerVeMesaj` R1-R2 ·
  `EnquSondasi` E1-E5 · `DomainTipBilgisi` L1-L4 · `KilitSirasi` T1-T3 · `AltSurecCLI` C1-C3).
- Kilit sırası (T1, gerçek `SAPClient.push_object`): LOCK H1 → PUT hata → UNLOCK H1 → LOCK H2 → PUT OK → UNLOCK H2; `clear_enqueue_lock` 0.
  Satır 2 çevrimdışı `yazildi` olamaz: push sonrası `sap_active_check` reviewer'ı canlı SAP ister → ölçemez → `ok:false` (doğru, fail-closed).
- Mutasyonlar (betik; değiştir → hedef test → geri yükle → sha256 eşit; 22/22 geri yükleme eşit):
  M01 ön geçiş reddi yutuldu → K* · M02 başarısız DELETE kabul → 16/19 · M03 `delete_verified=None` devam → 14 (ilk koşuda yalnız TypeError ile
  düşüyordu; test 14 iddiayla düşecek biçimde sağlamlaştırıldı, yeniden koşuldu → FAIL) · M04 atlanan=yazıldı → 10 · M05 force tek-ad kuralı yok → 05 ·
  M06 sonda None=yok → 09/24a · M07 kısmi hata exit 0 → 09/16/19/22b · M08 DTEL artefaktı yok → R1 · M09 overwrite zorla → R2 · M10 lib 404→ölçülemedi →
  L1/L4 · M11 lib sessiz CHAR → L2/L4 · M12 client domain hatasını yutar → L4 · M13 enqu None=yok → E3/E5 · M14 enqu var ters → E1/E2/E5 ·
  M15 enqu kaynak koruması yok → E4 · L3 iki hata-dalı unlock'u birlikte kaldırıldı → T1 · L4 SM12 tarifi yok → T2 · L5 satır hatasında koşum durur → T2 ·
  L6 client her zaman `clear_enqueue_lock` → T1/T2.
  **Hayatta kalan (eşdeğer, kanıtlı):** L1 (yalnız yükleme-hatası unlock'u) ve L2 (yalnız `finally` unlock'u) — ikisi birbirini örter, UNLOCK(H1) yine
  LOCK(H2)'den önce gelir; birlikte kaldırılınca (L3) yakalanır.
  **Ölçüm (mutasyon değil):** L7 sahte ADT kendi kullanıcısının bayat kilidini döndürünce bugünkü `push_object` `clear_enqueue_lock` çağırır → T1/T2 FAIL
  (§19.9 açık kaleminin kanıtı).
- Tam takım (`python tests/run_tests.py`, sahte bağlantı dosyalı kök, izole TMP, tek koşum): **677/677 senaryo satırı OK · 304 unittest, 0 failure,
  0 error** (423 sn; önce §17.2: 575 · 244). İzole TMP'de koşum öncesi/sonrası liste farkı yok.

### 19.8 DOĞRULANMADI (canlı SAP yok)
Tüm akışların canlı davranışı · `domain_creation_csv` reviewer'ının tek satırlık geçici CSV'yi canlı projede kabulü · gerçek domain XML'inde
`doma:datatype/length/decimals` alanlarının varlığı (playbook dışı) · enqu GET ucunun (`/ddic/lockobjects/sources/<ad>`) 200/404 ayrımı ·
kilit çakışmasında kütüphanenin gerçek hata metni (SM12 tarifi eşleşmesi metin/sınıf tabanlı).

### 19.9 Açık kalemler
- `sap_client.push_object` ön kontrolündeki kendi kullanıcısının bayat kilidi → `clear_enqueue_lock` çağrısı (bu dalda ~820-825) populate cds'ten
  erişilebilir; ayrı ajan kendi dalında kaldırdı. **Kapandı (merge 2026-09-15):** kilit dalı önce merge edildi (`56db2f3`); birleşik kodda
  `clear_enqueue_lock` çağrısı yok (`grep` yalnız yorum satırları). Birleşik tam takım sonucu kurulum dalı iş listesinde.
- Force tek ad zorunlu olduğu için "`delete_verified=None` → kalan satırlar `islenmedi`" force yolunda oluşamaz; kalanların `islenmedi` olması
  sonucu bilinmeyen yazma hatasıyla (test_12, gerçek hat U1-U3/U6) ve çağrı hattı istisnasıyla (test_12c) gösterildi (§19.10).

### 19.10 Bug gate WARNING düzeltmeleri (2026-09-14, D3-fix)
Kapsam: yalnız `populate.py`, iki test dosyası, `foundation-ops.md` §9, bu bölüm. `sap_client.py` / `sap_adt_lib.py` / `atom.py` /
`sap_adt_cli.py` diff'i boş (`git diff 4ceed2f --quiet` ölçüldü). Kilit silen/açan yol eklenmedi.

**Değişen yerler (`scripts/sapadt/populate.py`):** docstring 24-45 · sabitler 66-84 (`BILINMIYOR_MESAJ`, `KIMLIK_MESAJ`, `SILME_ONEKI`,
`INAKTIF_NOTU`, `READBACK_MESAJ`, kod kümeleri, `_HTTP_ONEKI = ^\[(\d{3})\] `) · `_KosumDurdu` 100 (kod/sınıf/adım/araç) · `_csv_oku` 123
(yinelenen başlık), 146 (`UnicodeDecodeError`), 150 (`csv.Error`) · `_hata_adaylari` 452 · `_yazma_hata_sinifi` 473 · `_aktivasyon_hatasi_mi` 489 ·
`_Yurutucu`: 502/568/583 `silme_oneki`, 513 `step_exception`, 533/546 silme durması ayrıntısı, 548-563 `_yaz_ya_da_hata`, 594 cds pull öneki ·
`kos` 726-728 `result.stop` + `stopped` metni.

**Sınıflandırma (koddan):** HTTP durumu yalnız `sap_error`/`SAPADTError` kodunda ve yalnız mesajın EN BAŞINDAN okunur
(`SAPADTError.__str__` = `"[{status_code}] {message}"`, `sap_adt_lib.py:72-75`); gövdedeki `[502]` eşleşmez.
| Sınıf | Kodlar / koşul | Sonuç |
|---|---|---|
| DUR · `sonuc_bilinmiyor` | `unexpected` (`sap_adt_cli.calistir` istisna; `atom._err_from_exc` SAPADTError dışı) · `connection_failed` (`SAPConnectionError`: zaman aşımı/bağlantı) · `unreachable` (`adt_activate`) · `sap_error` + `[502]`/`[503]`/`[504]` · `push_failed` + `error_type` SAP ağacı dışı ya da `SAPConnectionError` · aynı kodlar `steps.*` içinde · `step_exception` (çağrı hattının kendisi) · `delete_verified=None` · başarısız DELETE + sonda ölçülemedi | kalanlar `islenmedi`, çıkış 1 `run_stopped`, satır mesajı "sonuç BİLİNMİYOR, SAP'de durumu kontrol et" |
| DUR · `hesap_kilidi_riski` | `auth_failed` · `error_type` `SAPAuthenticationError` · `sap_error` + `[401]` | aynı; mesaj "kimlik reddedildi, koşum durduruldu, hesap kilidi riskine karşı kalan satırlar denenmedi" |
| SATIR HATASI · koşum sürer | kapı kodları · `guardrail_violation` · `reviewer_blocker` · `preflight_blocker` · `msgclass_overwrite_not_allowed` · `pull_*` · `source_changed_since_pull` · `std_dml_scan_unavailable` · `unsupported_type` · `invalid_argument(s)` · `not_found` · `already_exists` · `already_exists_after_retry` (v0.5.1) · `exists_unmeasured` · `locked` · `lock_conflict`/`lock_failed` · `validation_error` · `sap_error` diğer/durumsuz (403, 500 dahil) · `create_failed` · `description_too_long` · `activation_not_executed` · `activation_failed` (+ İNAKTİF notu) · `push_failed` (SAP ağacı istisnası) · `readback_failed` (yeni mesaj) · `readback_mismatch` · `master_language_unresolved` · `msgclass_live_incomplete` · `pull_live_read_failed` · `tool_failed` | çıkış 1 `partial_failure` (değişmedi) |
Gri alan varsayılanları (lider onaylı): `readback_failed` bilinen red (mesaj "PUT kabul edildi, geri okuma doğrulanamadı; SAP'de kontrol et") ·
`adt_delete` yolu değişmedi (sonda) · `_get_client` istisnası → DUR (`unexpected`) · `push_object` yerel `ValueError`/`FileNotFoundError` `error_type` → DUR.
Durma çıktısı: `result.stop = {name,row,step,tool,code,class}` + `error.message`/`stopped` = "satır N · adım/araç · kod=… · gerekçe=…: …".

**Kırmızı → yeşil:**
| Bulgu | Eski kodda (FAIL) | Yeni kodda |
|---|---|---|
| 1 sonucu bilinmeyen → DUR | test_12/12c/12d 3 FAIL (`partial_failure · hata,yazildi,yazildi`) · hat U1/U2/U3/U5/U6 5 FAIL; 12b ve U4 (kontroller) eski kodda da yeşil | yeşil; probe A rc1 `run_stopped` hata/islenmedi/islenmedi, create 1 kez; A2 `step_exception` |
| 2 yinelenen başlık | test_25 FAIL (`0 · {}`: son kolon kazanıyordu) | rc 3 `csv_invalid` |
| 3 force SİLİNDİ öneki | test_26 FAIL (mesaj "adt_domain_create başarısız …", önek yok) | domain/dtel/cds kabuk/pull/push/aktive önekli; bilinmeyen dal DUR |
| 4 okunamaz CSV | test_27 FAIL (`İSTİSNA UnicodeDecodeError`) · C4 FAIL (alt süreç rc 1, JSON yok) | cp1254 / UTF-16 rc 3 `csv_unreadable`; BOM+CRLF kontrolü geçer |
| lider 3/4 | test_28 FAIL (readback mesajı yok) · test_29 FAIL (İNAKTİF notu yok) | yeşil |
Hedefli: taban `-k populate` 79/79 · 49 test → yeşil **151/151 · 64 test, 0 failure** (rc 0).

**Mutasyonlar** (değiştir → hedef test → geri yükle → sha256 eşit; hepsinde eşit):
| Id | Mutasyon | Sonuç (düşüren) |
|---|---|---|
| N01 | bilinmeyen kod durdurmaz | ÖLDÜ (12, U1/U2/U6) |
| N02 | `steps.*` okunmaz | ÖLDÜ (12 iç içe, U2) |
| N03 | `error_type` okunmaz | ÖLDÜ (12 push) |
| N04 | kimlik sınıfı yok | ÖLDÜ (12 auth, U6) |
| N05 | 502-504 kümesi boş | ÖLDÜ (12 [502], U6) |
| N06 | gevşek desen `.*?\[(\d{3})\]` | ÖLDÜ (12b baştaki boşluk) |
| N06b | açgözlü `.*\[(\d{3})\] ` (gövdedeki son kod) | ÖLDÜ (12b gövde `[502]`) |
| N07 | `SAPConnectionError` bilinen sayılır | ÖLDÜ (12 push, U5) |
| N08 / N09 | yinelenen başlık kontrolü yok / ham adla | ÖLDÜ (25) |
| N10 / N11 | `UnicodeDecodeError` / `csv.Error` yakalanmaz | ÖLDÜ (27 + C4 / 27) |
| N12 / N13 | silme öneki kurulmaz / cds pull öneki yok | ÖLDÜ (26) |
| N14 | `result.stop` yazılmaz | ÖLDÜ (12/12c/12d) |
| N15 / N16 / N17 | readback mesajı / İNAKTİF notu / kimlik mesajı yok | ÖLDÜ (28 / 29 / 12 auth, U6) |
| M01-M15 (§19.7, yeniden) | — | 15/15 ÖLDÜ |
| L3-L7 (§19.7, yeniden) | — | ÖLDÜ (L7 ölçüm, beklendiği gibi) |
| L1, L2 | — | YAŞADI — §19.7'deki eşdeğerlik aynen (değişmedi) |

**Tam takım** (`python tests/run_tests.py`, sahte kök, izole TMP): **Senaryo satırı: 749/749 OK · unittest: 319 test, 0 failure, 0 error**
(6 dk 43 sn; taban 677 · 304 → fark +72 / +15 = populate farkıyla birebir).

**Davranış değişiklikleri:** sonucu bilinmeyen/kimlik yazma hatası artık koşumu durdurur (eskiden satır hatası, kalanlar deneniyordu; çıkış
kodu 1 aynı, `error.code` `partial_failure` → `run_stopped`) · yeni alan `result.stop` · yinelenen başlık rc 3 (eskiden sessizce son kolon) ·
UTF-8 dışı CSV rc 3 `csv_unreadable` (eskiden yakalanmamış istisna) · force'ta silme sonrası hata mesajı öneki · `readback_failed` ve
`activation_failed` satır mesajları.

**DOĞRULANMADI (canlı SAP yok):** gerçek 502/503/504'ün her yolda `SAPADTError(status_code=…)` olarak geldiği (48 `raise SAPADTError(`
çağrısının 35'i durum taşır) · canlı `push_object` hata yolunun gerçek `error_type` değerleri · `activation_failed` sonrası objenin gerçekten
inaktif var olduğu · tam takım sonrası izole TMP'de kalan `node-compile-cache` dizininin kaynağı (testlerde `node` çağrısı grep'te yok; silme izni verilmedi).

**Açık kalemler:**
- `status_code` `_err_from_exc` çıktısında yapısal alan değil; populate `str(exc)` önekinden okur. Alanı eklemek ~50 çağrı yerini ve 6 modülün
  çıktı sözleşmesini etkiler → yapılmadı.
- Durum taşımayan 13 `SAPADTError` fırlatması 502-504 olsa bile satır hatası kalır.
- Öneri 5 (uygulanmadı): ön geçiş yalnız kapıdır; araç içi ön kontrol ve reviewer yürütmede koşar, önceki satırlar yazılmış olabilir (`foundation-ops.md` §9'a yazıldı).
- §19.9 kilit dalı merge sırası aynen açık.

## 20. K1 + D1 — prog/intf inceleme zinciri, artefaktsız struct DTEL denetimi (2026-09-14)

Kullanıcı kararları: K1 "Uyan kontrolleri bağla" · D1 "Dosyasız çağrıda da koşsun". Lider ek kararı (D1): artefaktlı yol da aynı çıkarımla
genişletilir (sabit müşteri öneki taşımadan kalan kusurdu; iki yol aynı yapıya farklı hüküm veriyordu).

### 20.1 Ne değişti
| Tip / yol | Önce | Sonra |
|---|---|---|
| `prog`/`program`/`report`/`include`/`incl` push | `None` → SKIP + "PRE-FLIGHT KOŞMADI", yazma | `program_push`: abaplint W · released_objects W · decimal_write_to W |
| `intf`/`interface` push | `None` → SKIP, yazma | `interface_push`: method_param_type_c **B** · decimal_write_to W · released_objects W |
| `msag` push | `unsupported_type` (reviewer'a ulaşmaz) | değişmedi |
| include / `PROGRAM` modül havuzu abaplint | — | `measured=false unsupported-object-type` → SKIP = WARNING; yanıtta `reviewer.unmeasured` + `notice` + `gate.review` "ÖLÇÜLEMEDİ" |
| `adt_struct_create` artefaktsız | SKIP (`no_artifact_path_provided`) + yazma, DTEL denetimi yok | `struct_fields_dtel`: `fields[]` → `utils.ddic_dtel.alanlardan_ddl` → `check_struct_field_dtel_active.py`; yok/inaktif → `reviewer_blocker`; ölçülemedi → `reviewer_blocker` + ÖLÇÜLEMEDİ |
| `adt_struct_create` / `tabl` push artefaktlı | yalnız `zsd[0-9_]*_e_*` adları; `ZAXET_E_X` gibi var olmayan DTEL "kapsam dışı" PASS | aynı çıkarım (Z/Y + `/ad-alanı/` tip belirteci); `include`/`abap.*`/standart hariç |
| DTEL GET 404 | doğrudan BLOCKER | önce `structures`/`tables`/`tabletypes` sondası: varsa "DTEL değil, kapsam dışı"; hiçbirinde yoksa BLOCKER; sonda okunamazsa ÖLÇÜLEMEDİ |
| Ad-alanlı DTEL URL | `dataelements//scwm/de_x` (kodlanmamış) | `quote(safe="")` → `%2Fscwm%2Fde_x` (önek: `check_standard_table_fields.py`) |
| BLOCKER red mesajı | "N blocker" (ölçülemeyen gate ihlal gibi okunuyordu) | ölçülemeyen gate varsa `unmeasured` + "ÖLÇÜLEMEDİ: … ihlal bulunduğu anlamına gelmez; PASS da sayılmaz" |
| `adt_struct_create` `already_exists` / create hatası | `reviewer` alanı yok | `reviewer` alanı var |

Tek kaynaklar: tip çevirisi `sap_adt_lib.SAPADTClient._field_type_to_ddl` → `utils/ddic_dtel.field_type_to_ddl` (yazma yolu ile denetim aynı çeviriyi
kullanır) · aday çıkarımı `utils/ddic_dtel.dtel_adaylari` · görünürlük `_reviewer.on_kontrol_ozeti` / `olculemeyenler` (atom + composite + `reject_payload`).
Hüküm aritmetiği (`run_review`) değişmedi.

Ölçüm (önce, çevrimdışı, geçici `.prog.txt`/`.include.txt`/`.intf.txt`, 4 validator doğrudan): `REPORT` programında abaplint ölçtü (bu makinede npx var),
released_objects MARA bulgusu verdi; include, `PROGRAM` modül havuzu ve arayüzde abaplint `measured=false`; arayüzde method_param_type_c `TYPE c LENGTH`
ihlalini buldu. Kök pre-commit etkilenmez: `project_precommit.obje_tipi` prog/intf/include için `None` döner; struct DTEL gate'i orada ağ gate'i olarak atlanır.

### 20.2 Testler
`tests/test_verdict_reviewer_k1_d1.py` (14 test, 31 senaryo satırı; sahte ADT sunucusu 127.0.0.1'de, gerçek SAP yok):
K1a eşlemeler · K1b zincir + önem = class_push · K1c intf BLOCKER ağdan önce + temiz kontrol · K1d include ÖLÇÜLEMEDİ (PASS görünmez) · K1e prog 3 gate ·
K1f msag pin · D1a DDL çıkarımı · D1b fields[] aynı çıkarım + `sap_adt_lib` çevirisi eşit · D1c yok → BLOCKER (1 DTEL + 3 sonda GET) · D1d aktif +
iç içe yapı + tablo tipi + `/ns/` kodlanmış, standart sorulmadı · D1e inaktif · D1f ölçülemedi (DTEL 500 · sonda 500 · kapalı port · bağlantı bilgisiz
`.conn_adt`) → BLOCKER + ÖLÇÜLEMEDİ · D1g aday yok → ağ yok + kapsam beyanı · D1h artefaktlı genişletme + iç içe yapı kontrolü.
- Fail-first: eski kodda 14 testin 13'ü kırmızı (11 failure + 2 error; K1f pin yeşil). D1h eski kodda artefaktlı yolun var olmayan DTEL'e PASS verdiğini gösterdi.
- `.conn_adt` HİÇ yokken araç reviewer'a ulaşmaz: kapı `ADR_0010_TIER` ile önce reddeder (ölçüldü); validator'ın bağlantı dalı yalnız tier satırlı dosyayla sınandı.
- Bug gate düzeltmeleri (§20.6) aynı dosyaya eklendi: `B1ZamanButcesi` (a-e) · `B1fButceEnvGecersiz` · `B2ArtefaktliYolFields` (a-d) · `B3BelgeKodEsit` ·
  `B4CikarimDaralmasi`; `sap-code-review/tests/test_checklists.py::test_k1_push_keys_listed` (B5). Modül artık 26 test, 60 senaryo satırı.
  Fail-first (düzeltmeden önce, `-k B`): 9 failure + 1 error, kontrol B1c yeşil; B5 testi `['prog/i']` ile kırmızı; tekrar deneme alt bulgusu için
  B1a istek sayısı 4 (≤ 2 bekleniyordu) ile kırmızı. B2d (boş `fields[]` + artefakt → `validation_error`) mevcut davranışın pinidir, fail-first değil.
- Tam takım (düzeltme sonrası, 2026-09-14): foundation 281 test, 658/658 senaryo satırı, 0 failure / 0 error (rc=0) · sap-code-review 45 test OK, 1 skip.
- Dar re-gate düzeltmeleri (§20.7) aynı dosyaya eklendi: `B1g` · `B1hGercekToplamSure` (a-d) · `B3b` · `B6BirlestirNormalize` · `B7TekRender` (a-b);
  `_Taban` her testte ADT_* temizler. Modül 35 test, 78 senaryo satırı.

### 20.3 Mutasyonlar (hepsi yakalandı, sha256 geri yükleme eşit)
M1 bağlantı yok → measured=true (D1f) · M2a `struct_fields_dtel` BLOCKER→WARNING (D1c/e/f) · M2b interface_push method_param_type_c BLOCKER→WARNING (K1b/c) ·
M3 çıkarım boş (D1a/b/c/d/e/f/h) · M4 404 sondası yok (D1c/d/f/h) · M5 URL kodlama yok (D1d) · M6 artefaktsız yol kapalı (D1c/d/e/f/g) ·
M7 `unmeasured` düşürüldü (K1d) · M8 include eşlemesi `None` (K1a/d).

### 20.4 DOĞRULANMADI (canlı SAP yok)
- ADT'nin yapı adına `dataelements/<ad>` GET'inde 404 döndüğü ve `structures/`/`tables/`/`tabletypes/<ad>` GET'lerinin (kaynak ucu olmadan) 200 verdiği.
- `%2F` kodlanmış ad-alanlı adın ADT tarafından çözüldüğü.
- Gerçek SAP gecikmesinin 15 sn gate bütçesini / 30 sn zincir süresini ne sıklıkla aştığı (sahte sunucuyla ölçüldü, §20.6; canlıda ölçülmedi).
- Tekrar deneme kapalıyken canlıda geçici 429/502/503/504 cevaplarının sıklığı (gelirse aday ÖLÇÜLEMEDİ → BLOCKER; yanlış BLOCKER oranı ölçülmedi).

### 20.5 Açık kalemler
- Standart DTEL (Z/Y/ad-alanı dışı) varlığı bu gate'in kapsamı dışında (STR-FIELD-3; `check_standard_table_fields.py` yalnız WARNING ve struct alan tipine bakmıyor — ölçülmedi).
- `run_reviewer` sarmalayıcısının kendi SKIP'leri (`run_review_script_missing`, `reviewer_exception`) struct yolunda da yazmayı durdurmaz (mevcut sözleşme; görünür not ile).
- Sarmalayıcı zaman aşımında Windows'ta yalnız `run_review` süreci öldürülür; o anda koşan validator alt süreci kendi süresi bitene kadar yaşar
  (DTEL gate'i için artık bütçeyle sınırlı; `check_standard_table_fields.py` gibi bütçesiz ağ validator'ları için sınırsız — önceden var, ölçülmedi).
- (a)'nın diğer canlı BLOCKER validator'lara genelleştirilmesi KULLANICI KARARI bekliyor (§20.6 listesi).
- `check_standard_table_fields.py` (WARNING) süre bütçesi taşımaz ve oturumun tekrar denemesini kullanır: asılı SAP'de tek başına > 120 sn (ölçüldü,
  §20.6). DTEL gate'li zincirde (`struct_creation`, `table_update`) bu yavaşlık 30 sn'yi aşırıp (a) ile BLOCKER üretir. SAP yanıt vermiyorsa yazmanın
  durması doğru; bu validator'a bütçe eklemek bu dalın kapsamı dışında (lider kararı) — açık.
- 1 sn/istek gecikmede ~14'ten fazla Z DTEL'li geçerli yapı ÖLÇÜLEMEDİ → BLOCKER alır (§20.6 ölçümü; lider kararı (b)'nin bilinçli sonucu). Canlı
  gecikme dağılımı bilinmiyor; bütçe/eşik ayarı gerekirse ayrı karar.
- Önceden var (bu dalın dokunmadığı dosyalar): `check_decimal_write_to.py:33` ve `check_method_param_type_c.py:38` tarama etiketi `.prog.txt`
  için de `.clas/.intf.abap` yazar (taban `e0e0b13`'ten; `git diff 0087228` bu iki dosyada boş) — düzeltilmedi.
- `validator-map.md` §1'de, eşleme `None` olmayan 6 eşanlamlı daha tabloda yok (`behaviordefinition`, `servicedefinition`, `cdsview`, `ddl`,
  `implementations`, `testclasses`); bu dal yalnız kendi eklediği `prog/i`'yi ekledi ve K1 anahtarları için kod→tablo testini koydu.

### 20.6 Bug gate düzeltmeleri (2026-09-14, taze bug-expert BLOCKER → B1-B5)
Prior-art: kaynak çekirdek `playbook/checklists/table-update.md` "Önemli Vakalar" 7 ("checklist satırı ≠ çalıştırılan validator" — reviewer-kör
vakası) · kaynak çekirdek `struct-creation.md` C-STR-FIELD-02 (BLOCKER) · template `sap-cds-ddic/references/checklists.md:70` (STR-FIELD-2).

| Bulgu | Önce (ölçülen) | Sonra |
|---|---|---|
| B1 (b) DTEL gate süresi | eksik DTEL başına 1+3 GET, her GET 10 sn; oturum `Retry(total=3)` her GET'i 4 kez deniyordu | tek döngü, tek toplam bütçe (`VARSAYILAN_BUTCE_SN=15`; GET zaman aşımı = min(10, kalan)); gate sürecinde tekrar deneme yok (`_tekrar_denemeyi_kapat`); bütçe dolunca denetlenemeyen adaylar `[ÖLÇÜLEMEDİ: süre bütçesi (N sn) doldu, M aday denetlenmedi] denetlenen K/T` → bulgu yoksa measured=false (SKIP = BLOCKER), bulgu varsa exit 1 + kalanlar adlarıyla |
| B1 env | — | `AXET_DTEL_GATE_BUTCE_SN` yalnız düşürür; geçersiz (sayı değil, ≤ 0, NaN, > 15) → varsayılan + `UYARI:` satırı; bütçe her koşumda `SÜRE BÜTÇESİ: N sn` ile basılır |
| B1 (a) sarmalayıcı zaman aşımı | her zincirde WARNING (yazma) | `ZAMAN_ASIMI_BLOCKER_GATELERI` kümesindeki gate'i BLOCKER önemle taşıyan zincirde BLOCKER (`reviewer_timeout — zaman aşımı → BLOCKER (ÖLÇÜLEMEDİ)`); görevler AST ile `TASK_VALIDATORS`'tan türer: `table_creation`, `table_update`, `struct_creation`, `struct_fields_dtel`. Diğer zincirlerde WARNING değişmedi (test pini). `TASK_VALIDATORS` okunamazsa fail-closed BLOCKER |
| B2 artefaktlı struct | `artifact_path` verilince `fields[]` denetlenmiyordu; olmayan yol SKIP = yazma (0,0 sn) | `_reviewer.run_reviewer_struct`: yol yoksa `artifact_not_found` → BLOCKER (ağsız) · `fields[]` (SAP'ye yazılan yük, `sap_adt_lib.create_structure`) DAİMA `struct_fields_dtel` · BLOCKER değilse artefaktın `struct_creation` zinciri de koşar, hüküm birleşir (en ağır verdict; `results[].girdi` = fields/artifact) |
| B3 belgeler | `foundation-ops.md` / `tool-catalog.md` / `composite.py` yorumu fail-closed vaat ediyor, kod WARNING'e düşüyordu | üçü de yukarıdaki davranışa eşitlendi; `B3BelgeKodEsit` testi üç terimi (artifact_not_found, reviewer_timeout, bütçe) arar |
| B4 çıkarım | aynı satırda anotasyon+alan · string içinde `/*` · iki satıra bölünmüş alan → aday kaçıyordu | string+yorum tek taramada atılır (string önce), anotasyon (nesne/dizi değerli dahil) atılır, metin yalnız `;{}` ile bölünür, alan `search` ile bulunur |
| B5 validator-map | §1'de `prog/i` yok, test yalnız tablo→kod yönünde | satır eklendi; `test_k1_push_keys_listed` K1 anahtarlarını kod→tablo yönünde de zorlar |

Red mesajı (lider şartı 1): ölçülemeyen gate'in `stderr`'indeki `ÖLÇÜLEMEDİ` satırı `unmeasured[].reason` ve `reject_payload` mesajına
("Ayrıntı: …") taşınır → "DTEL yok" ile karışmaz. Sarmalayıcı hükmü (zaman aşımı, artefakt yok) `gate="reviewer"` olarak `unmeasured`'a girer.

**(a) genelleşirse etkilenecekler** (koddan türetildi: SAP ağ okuması yapan validator'lar × `run_review.py` `TASK_VALIDATORS` önemi):
- `check_table_field_drop.py` (ağ: `:102`) — BLOCKER: `table_update` (`run_review.py:108`) [zaten DTEL gate'i nedeniyle kapsamda]
- `check_sap_struct_consistency.py` (ağ: `:113`) — BLOCKER: `struct_post_create` (`run_review.py:131`)
- `check_sap_active_version.py` (ağ: `:201`) — BLOCKER: `struct_post_create` (`run_review.py:133`), `sap_active_check` (`run_review.py:137`)
- `check_standard_table_fields.py` (ağ: `:111`) — yalnız WARNING (`cds_creation :84`, `table_update :114`, `struct_creation :127`, `rap_cds_creation :227`) → "canlı BLOCKER" kümesine girmez;
  AMA bütçesiz olduğu için (a) altında zaten etkili: DTEL gate'li zincirde yavaşlığı zaman aşımına → BLOCKER'a dönüşür (ölçüldü, aşağıda). Genelleştirmede
  `cds_creation` / `rap_cds_creation` zincirlerine de aynı etki taşınır (zincirde canlı BLOCKER yoksa taşınmaz — küme tanımına bağlı)
- `check_itg_signoff.py` (BLOCKER, `itg_s2_signoff :246`) ağ gate'i değil (intake dosyası; `run_review.py:263-270` → `sap-intake-triage`)
Genelleşince yeni etkilenen görevler: `struct_post_create`, `sap_active_check` (post-check yolları: `atom.py:1873`, `composite.py` `struct_post_create`).
Değişecek tek yer: `_reviewer.ZAMAN_ASIMI_BLOCKER_GATELERI`. Dikkat: post-check'te BLOCKER yazmayı değil `ok`'u düşürür (yazma zaten olmuştur).
Ölçülen yan etki (aşağıdaki tablo): `check_standard_table_fields.py` bütçesiz ve tekrar denemeli; asılı SAP'de tek başına > 120 sn sürdü → WARNING
validator'ının yavaşlığı `struct_creation`/`table_update` zincirini 30 sn'nin üstüne taşır ve (a) ile BLOCKER'a döner (SAP yanıt vermiyorsa yazmanın
durması doğru; bu validator'a süre bütçesi eklemek bu dalın kapsamı dışında — açık kalem, §20.5).

#### Ölçümler (sahte ADT sunucusu 127.0.0.1; gerçek SAP yok; aynı makinede başka ajanların testleri koşarken — CPU yükü her satırda)
Uçtan uca `adt_struct_create` (gerçek `_reviewer` sarmalayıcısı; bug gate'in sahte gecikmeli sunucu sondası). ÖNCE = `0f18b30`, SONRA = düzeltme (tek başına koşum):

| Vaka | ÖNCE | SONRA | CPU yükü (SONRA, önce/sonra %) |
|---|---|---|---|
| artefaktlı, 8 eksik DTEL + 1 sn gecikme | 30,0 sn zaman aşımı → **YAZMA** | 16,4 sn BLOCKER, yazma yok | 72/73 |
| artefaktlı, 25 eksik + 0,3 sn | 30,0 sn → **YAZMA** | 16,3 sn BLOCKER | 73/69 |
| artefaktlı, kontrol 8 eksik + 0,3 sn | 12,1 sn BLOCKER | 11,5 sn BLOCKER | 58/49 |
| artefaktsız, 8 eksik + 1 sn | 30,0 sn → **YAZMA** | 15,9 sn BLOCKER | 63/76 |
| artefaktsız, 25 eksik + 0,3 sn | 30,0 sn → **YAZMA** | 16,7 sn BLOCKER | 65/46 |
| artefaktsız, kontrol 8 eksik + 0,3 sn | 11,0 sn BLOCKER | 12,3 sn BLOCKER | 72/80 |
| asılı SAP (her istek 60 sn), artefaktsız / artefaktlı | — | 15,5 / 15,9 sn BLOCKER (ÖLÇÜLEMEDİ, 2 istek) | 10/39 · 50/41 |
| kapalı port | — | 5,0 sn BLOCKER (ÖLÇÜLEMEDİ) | 37/54 |
| olmayan `artifact_path` + eksik DTEL | 0,0 sn → **YAZMA** | 0,0 sn BLOCKER (`artifact_not_found`, 0 istek) | 66/88 |

Tekrar deneme bulgusu (ara ölçüm, adaptör düzeltmesinden önce): asılı SAP'de DTEL gate'i 42,7 sn / 4 istek (oturum `Retry(total=3)`); sonra 16,1 sn / 2 istek.

Zincir süreleri (lider şartı 2; `run_review` doğrudan + her validator ayrı süreçte; yerel ölçüm betiği, repoya girmez; `struct_creation`
artefaktı standart tablo.alan referansı taşır → `check_standard_table_fields` ağa çıkar):

| Görev · koşul | DTEL gate | std_table_fields | diğer | zincir toplam · verdict | CPU % |
|---|---|---|---|---|---|
| `struct_fields_dtel` · asılı | 16,1 sn (ÖLÇÜLEMEDİ, bütçe) | — | — | 15,5 sn · BLOCKER | ölçülmedi |
| `struct_creation` · asılı | 15,7 sn | > 120 sn (ölçüm sınırı; 8 istek) | 0,2 sn | 75,7 sn · BLOCKER (`run_review` validator başına 60 sn) → sarmalayıcıda 30 sn → (a) BLOCKER | ölçülmedi |
| `table_update` · asılı | 15,9 sn | > 120 sn | drop 0,8 · 0,5 sn | 77,2 sn · BLOCKER | ölçülmedi (başka koşuyla çakıştı) |
| `struct_creation` · 8 eksik + 1 sn | 15,8 sn (3 eksik, 6 denetlenmedi) | 8,8 sn | 0,4 sn | **25,5 sn** · BLOCKER (çakışmalı önceki ölçümler 24,5 · 26,3) | 75/76 |
| `struct_creation` · 25 eksik + 1 sn | 15,6 sn (3 eksik, 23 denetlenmedi) | 8,8 sn | 0,4 sn | **24,8 sn** · BLOCKER (önceki 25,1 · 25,4) | 34/57 |
| `struct_creation` · 9 GEÇERLİ DTEL + 1 sn | 9,8 sn temiz | 8,9 sn | 0,4 sn | 19,6 sn · PASS | 59/82 |
| `struct_creation` · 26 GEÇERLİ DTEL + 1 sn | 15,6 sn (14 denetlendi, 12 denetlenmedi) | 8,8 sn | 0,2 sn | **24,8 sn · BLOCKER (yanlış BLOCKER)** (önceki 24,9) | 36/39 |
| `struct_creation` · 26 GEÇERLİ DTEL + 0,3 sn | 8,9 sn temiz | 3,2 sn | 0,4 sn | 13,4 sn · PASS | 45/55 |

Sonuç: 1 sn/istek gecikmede `struct_creation` en kötü ~25-26 sn (30 sn'nin altında ama eşiğe yakın; artefaktlı araç çağrısında `fields[]` zinciri
ayrı sarmalayıcı çağrısıdır, toplam araç süresi ikisinin toplamıdır). Asılı SAP'de 30 sn aşılır → (a) BLOCKER (kabul edildi).
**Davranış değişikliği (bilinçli, lider kararı (b)):** GET başına ~1 sn yanıt veren sistemde ~14'ten fazla Z DTEL'li GEÇERLİ yapı artık
ÖLÇÜLEMEDİ → BLOCKER alır (yanlış BLOCKER). Tabanda aynı vaka (26 GET × 1 sn + std_table_fields) 30 sn'yi aşıp WARNING → yazma olurdu
(hesap; tabanda ölçülmedi). 0,3 sn/istekte 26 geçerli DTEL PASS.

#### Mutasyonlar (12/12 yakalandı; her birinde sha256 geri yükleme eşit)
MB1a bütçe yok (B1a) · MB1b tekrar deneme açık (B1a istek sayısı) · MB1c (a) zaman aşımı yine WARNING (B1d) · MB1d (a) kümesi koddan türemez (B1e) ·
MB1e geçersiz env sessizce kabul (B1f) · MB1f bütçe mesajında sayılar yok (B1a mesaj) · MB2a olmayan artefakt BLOCKER değil (B2a) ·
MB2b artefakt verilince fields denetlenmez (B2b/B2c, 3 failure) · MB4a satır sonu yine böler (B4) · MB4b string yorumdan önce atılmaz (B4) ·
MB4c anotasyon atılmaz (B4 nesne değerli anotasyon) · MB5 `prog/i` satırı yok (`test_k1_push_keys_listed`).

### 20.7 Dar re-gate düzeltmeleri (2026-09-15, taze bug-expert WARNING → 5 madde)
| Madde | Önce (ölçülen) | Sonra |
|---|---|---|
| MEDIUM belge | `validator-map.md` §1/§2, `run_review.py` `struct_fields_dtel` açıklaması (rapora basılır), `run_reviewer_struct_alanlari` docstring'i "artefaktsız / artefakt verilmezse" diyordu | dördü "her çağrıda" (+ §1'de `artifact_not_found`); `B3b` dördünü okur |
| LOW bütçe | `timeout=min(10, kalan)` soket okuması başınaydı: damla yanıt (1 bayt/1,5 sn), bütçe 3 sn → gate testte 40 sn zaman aşımı (gate sondasında 90 sn); istemci kurulumu bütçe dışıydı: 30 sn asılı kurulum → 30,6 sn | `_sureli`: istemci kurulumu ve her GET bir iplikte, ana akış yalnız KALAN bütçe kadar bekler; damla → gate süreci 3,3-3,9 sn, asılı kurulum → 3,5-3,8 sn (bütçe 3 sn, süreç açılışı dahil; CPU %6-72); ikisi de measured=false → BLOCKER. Retry'sız adaptör korunur (503 → tek istek) |
| ÖNERİ `_birlestir` | tanınmayan verdict metni aynen dönüyordu (`X` + `BLOCKER` → `X`, `is_blocker` False) | önce `BLOCKER`'a normalize |
| Önceden var #1 D1f sırası | modül sırasında 2/2, `D1StructDtel` tek başına 1/1 FAIL: D1b'nin süreç içi `import sap_adt_lib`'i `.conn_adt`'yi `os.environ`'a yükleyip bırakıyor, "kapalı port" alt süreci eski URL'yi miras alıp PASS alıyordu | `_Taban` her testin başında ve sonunda ADT_* temizler; modül sırası 3/3, sınıf sırası 3/3 yeşil |
| Önceden var #2 açıklama | gate DDL'i açıklamasızdı: alan açıklaması `"x\n  b : zaxet_e_yok_desc;"` → gate adayı `[]`, yazılan DDL adayı `['ZAXET_E_YOK_DESC']` | tek render `utils/ddic_dtel.yapi_ddl_kaynagi` (gövde `create_structure`'dan aynen taşındı); `create_structure` ve `run_reviewer_struct_alanlari` onu çağırır, `adt_struct_create` `description` geçirir; render hatası → BLOCKER |

Ölçüm notları: terk edilen iplik süreç çıkışını bekletmedi (`sys.exit` 3,4 sn 2/2) → `os._exit` eklenmedi. `B1g` önce 1 sn bütçeyle yazılmıştı ve eski
kodda da geçiyordu (soket başı zaman aşımı damla aralığından küçük) → bütçe 3 sn yapıldı, mutasyonla kırmızı gösterildi. Gövde ayrıca okunmaz: `stream=False`
gövdeyi `session.get` içinde (iplikte) okur (ayrı okuma satırını kaldıran mutasyon eşdeğer çıktı). D1f sıra bağımlılığı `run_tests.py -k` altında GÖRÜNMEZ:
keşif başka test modüllerini de import eder ve `sap_adt_lib` önceden yüklenir → D1b'nin import'u env'e yazmaz; bu yüzden tam takım bağımlılığı saklıyordu.

Testler: `B1g` (uçtan uca damla, bütçe 3 sn, < 12 sn) · `B1hGercekToplamSure` a damla / b asılı istemci kurulumu / c kontrol hızlı SAP / d 503 tek istek ·
`B3b` · `B6BirlestirNormalize` · `B7TekRender` a açıklama enjeksiyonu gate'te görünür / b gate DDL'i = `create_structure`'ın PUT ettiği DDL (3 vaka).
Fail-first (düzeltmeden önce, modül): 6 failure (B1h a, B1h b, B3b, B6, B7a, B7b). `B1g` ve `B1h d` eski kodda yeşildir (pin); kırmızıları mutasyonla gösterildi.
Tam takım (2026-09-15, düzeltme sonrası, CPU %59→54): foundation `Senaryo satırı: 676/676 OK · unittest: 290 test, 0 failure, 0 error` (rc=0, 246 sn) ·
sap-code-review `Ran 45 tests in 3.943s` / `OK (skipped=1)` (rc=0).

Mutasyonlar (12 anlamlı mutasyonun 12'si yakalandı, sha256 geri yükleme eşit): MR1a validator-map §2 bayat (B3b) · MR1b run_review açıklaması bayat (B3b) ·
MR2a istek iplikte değil (B1h a) · MR2a' aynısı uçtan uca (B1g) · MR2b istemci kurulumu bütçe dışı (B1h b) · MR2d tekrar deneme açık (B1h d) · MR2e bütçe
kurulumdan sonra başlar (B1h b) · MR3 normalize yok (B6) · MR4' ADT_* temizliği yok (sınıf sırası; `-k D1` altında kaçtı, neden yukarıda) · MR5a gate eski
render (B7a/b) · MR5b composite açıklamayı geçirmez (B7b) · MR5c yazma yolu render'dan sapar (B7b).

DOĞRULANMADI: canlı SAP'nin `// …` satırındaki satır sonunu ve etiketteki satır sonunu nasıl ayrıştırdığı (gate artık yazılan metnin aynısını denetler; SAP'nin
kabul edip etmediği ölçülmedi) · SAML/JWT istemci kurulumunun ağa çıkıp çıkmadığı (kurulum artık bütçe içinde) · iplik terkinin Windows dışı davranışı ·
ağır yükte süreç açılışı + import süresinin pay (2 sn) içinde kalması.

Açık kalemler (düzeltilmedi):
- **Süreç içi ADT_* env mirası (ürün etkisi, ölçüldü):** aynı süreçte `atom._get_client()` sonrası `.conn_adt` başka sisteme dönerse reviewer alt süreci
  eski `ADT_*`'yi miras alır (`sap_adt_lib.py:437-438` `load_dotenv(override=False)`): sahte A/B sunucusunda denetim A'ya gitti ve PASS verdi (B'de kontrol
  BLOCKER). Yazma da A'ya gitti; süreç içi bağlantı guard'ı (`atom._guard_binding_current`) reddetmedi, çünkü `_conn._conn_value` →
  `project.effective_conn_value` (`project.py:106-107`) önce env'i okur. Bu, env'i yine env ile karşılaştırmak demek. Pratik yüzey (kod okunarak DOĞRULANDI):
  aXet'te uzun yaşayan sunucu yok (`git ls-files` mcp 0, `FastMCP|mcp.server|stdio_server` eşleşmesi 0); `sap_adt_cli.py` her süreçte tek araç çağırır
  (`main` :180, `spec.fn` :277); populate/toplu koşum dosyası yok. Yüzey: tek süreçte birden çok istemci/araç çağrısı yapan yollar (ör. `tools/diag.py`) ve
  çağrı sürerken `.conn_adt`'nin değişmesi. Aynı guard sınıfı IX tarafındaki uzun yaşayan MCP sunucusunda da olabilir — ayrı kalem, burada ölçülmedi.
- Sarmalayıcı SKIP'leri yazmayı durdurmaz (önceden var #3; lider kararı: dokunulmadı).

### 20.8 Serbest metinde satır sonu yasağı (2026-09-15, 3. dar gate WARNING → tek MEDIUM)
**Bulgu (gerileme, ölçüldü):** §20.7'deki tek render alan açıklamalarını `// …` satırı olarak gate'e de taşıdı. Çıkarıcı (`ddic_dtel.dtel_adaylari`)
`--`'yı tanımıyor ve `/*` görünce blok yorum sanıyor. Açıklama `"x\n-- /*"` + eksik DTEL'li alan + açıklama `"*/"` → gate adayları HEAD c9b5538'de
`['ZAXET_E_OK','ZAXET_E_OK2','ZAXET_E_YOK']` (BLOCKER), yeni ağaçta `['ZAXET_E_OK2']` (`status=OK measured=true`, PASS). Aynı sınıf alan adı ve tipinde de
ölçüldü (ad `"a : zaxet_e_ok;\n  /* "` ya da tip `"char10;\n  -- /*"` → `ZAXET_E_YOK` gizlendi).

**Düzeltme (lider kararı, kök sınıf "serbest metinde satır sonu"):** `utils/ddic_dtel.py` `SATIR_SONU_KARAKTERLERI` (CR, LF, U+2028, U+2029,
U+0085) ve `satir_sonu_ihlali(fields, description)` tek kaynaktır. Bakılan yerler: yapı açıklaması, her alanın `description`, `name` ve `type` değeri
(yalnız `str`). `yapi_ddl_kaynagi` ihlalde `ValueError` verir (mesaj yeri + kodu söyler). Böylece gate (`ddl_render_hatasi` → BLOCKER),
`create_structure` ve render'ı çağıran her yol kapanır. `adt_struct_create` aynı kontrolü alan doğrulamasının hemen ardından, reviewer'dan ve ağdan
önce yapar ve `validation_error` döndürür. Satır sonu içermeyen girdide PUT DDL'i HEAD ile bayt bayt aynıdır (pin `B7g`, 2 vaka).
Alan adı/tipi de kapsama alındı: brifing "render'a giren tüm serbest metinler" diyor ve ikisinde de gizleme ölçüldü.

Testler (`B7TekRender`): a açıklamada satır sonu → `validation_error`, 0 istek · c gate probe girdisi → `validation_error`, mesajda
`fields[0].description` + `U+000A`, 0 istek · d render 5 karakter × 4 yer `ValueError` · e composite 5 × 4, reviewer çağrılmaz, 0 istek · f
`run_reviewer_struct` doğrudan → BLOCKER `ddl_render_hatasi` · g pin. Fail-first (düzeltmesiz ağaç): 5 failure (B7a, c, d, e, f), pin yeşil.
Mutasyonlar (8/8 yakalandı, sha256 geri yükleme eşit): render reddi yok (B7d 20 vaka + B7f) · composite ön kontrolü yok (B7a, B7c, B7e 20 vaka) · kümeden
tek tek CR, LF, U+2028, U+2029, U+0085 çıkarıldı (her birinde yalnız o karakterin B7d 4 + B7e 4 vakası; LF'de ayrıca B7a/c/f).

DOĞRULANMADI: canlı SAP'nin `--`, çok satırlı etiket ya da U+2028/U+0085 içeren DDL'i nasıl ayrıştırdığı (artık gönderilmiyor) · Windows dışı davranış.
Açık kalemler (dokunulmadı): artefaktlı yolda `--` kör noktası (`ddic_dtel.py` `_STRING_YORUM`; artefakt metni kullanıcıdan gelir, bu kural onu kapsamaz) ·
POST XML kaçışı (`sap_adt_lib.create_structure` POST gövdesi) · ADT_* env mirası · sarmalayıcı SKIP.

### 20.9 K10 — inceleme zincirinin süre bütçesi: ölç → uzat → BLOCKER (2026-09-17)

Kullanıcı kararı (2026-09-15, `maintenance/IS-LISTESI.md` K10): **"Süreyi ölç + uzat, sonra BLOCKER"**.
Dayanak: *"ölçülemedi ≠ temiz"* — bir kontrol koşmadıysa sonucu TEMİZ değil **NOT MEASURED**'dır.
⚠ Bu bölüm §20.6'daki B1 (a)/(b) satırlarını ve "(a) genelleşirse etkilenecekler" listesini **GÜNCELLER**
(o satırlar tarihçedir; bugünkü davranış burasıdır).

**① ÖLÇÜM** — gerçek giriş noktası `_reviewer.run_reviewer`, sahte ADT sunucusu (127.0.0.1), gerçek SAP YOK.

| görev | validator | canlı | canlı BLOCKER | 0 sn/GET | 1 sn/GET | GET |
|---|---|---|---|---|---|---|
| table_update | 5 | 3 | 2 | 1,45 sn | **11,27 sn** | 10 |
| struct_creation (8 DTEL) | 4 | 2 | 1 | 0,94 | 8,95 | 8 |
| struct_fields_dtel (8 DTEL) | 1 | 1 | 1 | 0,56 | 8,53 | 8 |
| table_creation (8 DTEL) | 3 | 1 | 1 | 0,66 | 8,72 | 8 |
| struct_post_create | 2 | 2 | 2 | 0,83 | 4,80 | 4 |
| sap_active_check | 2 | 1 | 1 | 0,73 | 3,83 | 3 |
| rap_cds_creation | 7 | 1 | 0 | 1,06 | 1,84 | 1 |
| class_push | 6 | 0 | 0 | 0,77 | 0,67 | 0 |
| (ağsız zincirler: cds_update, program_push, interface_push, rap_bdef_creation, dtel_*, domain_creation_csv, itg_s2_signoff) | | 0 | 0 | 0,09-0,48 | aynı | 0 |

Ölçek eğrisi (`struct_creation`, 1 sn/GET, eski 15 sn gate bütçesi) — **D12 iddiası doğrulandı ve sayısallaştı**:
2/5/8/12/**14** aday → PASS (2,94 / 5,97 / 9,16 / 13,14 / **15,03** sn) · **16/20/30 aday → BLOCKER** (bütçe dolar, 15 GET,
~15,7 sn). Yani 1 sn/GET yanıt veren bir sistemde 15 geçerli Z DTEL'den sonrası **SAP doğru cevap verdiği hâlde**
yanlış BLOCKER'dı. Gate'in ölçülen işleme hızı ≈ **1 aday/sn**.
⛔ **ÖLÇÜLEMEDİ:** gerçek SAP'ye karşı süreler (canlı bağlantı yoktu). Gecikmeler benzetimdir.

**② YAPILANDIRILABİLİR BÜTÇE** — TEK KAYNAK `scripts/sapadt/lib/utils/butce.py`, üç katman **yapısal** olarak sıralı:

| katman | nerede | varsayılan | ayar |
|---|---|---|---|
| L1 sarmalayıcı | `_reviewer.run_reviewer` → `subprocess.run(timeout=…)` | **60 sn** | `AXET_REVIEWER_BUTCE_SN` (5-900; **yükseltir de düşürür de**) |
| L2 zincir | `run_review.main` → validator'lara dağıtılan toplam | **56 sn** (= L1 − 4) | L1'den türer |
| L3 gate-içi | `check_struct_field_dtel_active` ağ bütçesi | **28 sn** (= L2 × %50) | `AXET_DTEL_GATE_BUTCE_SN` (üst sınır artık sabit değil, **L2**) |

Varsayılanın dayanağı: L3 28 sn ≈ 28 aday (ölçülen 1 aday/sn) — eski 15 sn'de ~14 idi, D12 riski tam oradaydı ·
L1 60 = L3 28 + ölçülen zincir artığı ~11 + ≈2× emniyet · **ayrıca 60 = ESKİ iç zaman aşımı ⇒ hiçbir katman
eskisinden DAHA AZ süre almaz** (yükseltme bir gevşetme değil, daha ÇOK ölçüm demektir).
Geçersiz env (sayı değil, aralık dışı, NaN) → varsayılan + görünür `UYARI:` satırı.

**③ ZAMAN AŞIMI = BLOCKER** — kapsam sınırı kaldırıldı. Küme **koddan türer**: bir validator "CANLI"dır ⇔
GERÇEK dosyasında `SAPADTClient` geçer. Ad→yol çözümü `HARICI_VALIDATORLER`i de okur (AST ile), çünkü
`check_itg_signoff.py` zincirde bu adla geçer ama dosyası `sap-intake-triage/scripts/check_intake_signoff.py`dir.
Canlı küme (ölçüldü): `check_struct_field_dtel_active` · `check_sap_struct_consistency` · `check_sap_active_version` ·
`check_table_field_drop` · `check_standard_table_fields` (sonuncusu hiçbir zincirde BLOCKER değil).
**BLOCKER görevleri 4 → 6:** eski `table_creation`, `table_update`, `struct_creation`, `struct_fields_dtel`
**+ YENİ** `struct_post_create`, `sap_active_check`. Kapsam DIŞI (kontrol grubu, WARNING kalır):
`cds_creation`, `cds_update`, `rap_cds_creation`, `class_push`, `program_push`, `interface_push`,
`rap_bdef_creation`, `itg_s2_signoff` (ağ gate'i değil), boş zincirler.
Mesaj süreyi uzatma yolunu **açıkça** söyler (`butce.nasil_uzatilir()`: env adı + güncel süre + geçerli aralık).
Fail-closed: `TASK_VALIDATORS` okunamazsa · dosya yolu çözülemezse · dosya okunamazsa → **canlı/BLOCKER sayılır**.

**Katman hizası (yan kusur, aynı turda düzeltildi):** `run_validator` validator başına SABİT **60 sn** veriyordu ama
sarmalayıcı zinciri **30 sn**'de kesiyordu ⇒ iç dal **ULAŞILAMAZDI** (ölü dal) ve hükmü daima sarmalayıcının KÖR
kesmesi veriyordu (hangi gate'te takıldığı raporlanamıyordu). Artık L3 < L2 < L1 ve `run_validator` zincire KALAN
süreyi kullanır; bütçe bittiyse sıradaki gate **hiç başlatılmaz** → `SKIP` + `olcum_yok=True` (kendi şiddetiyle sayılır).
Bu, §20.6'da "açık kalem" bırakılan *"`check_standard_table_fields` bütçesiz"* maddesini de **zincir katmanında**
kapatır (gate'in kendi içine bütçe eklenmedi — bu ayrım bilinçlidir).

**Testler** `tests/test_k10_zaman_asimi_butce.py` (14 test / 28 senaryo satırı) — fail-first: düzeltmesiz ağaçta
2 failure + 9 error. **Mutasyonlar (5/5 yakalandı):** M1 canlı küme yerine eski elle-liste → K10b2+b3 · M2 sarmalayıcı
`timeout` sabit 30 → K10b5 · M3 `run_validator` sabit 60 → K10c1 · M4 gate bütçesi sabit 15 → K10a4+K10c2 ·
M5 `HARICI_VALIDATORLER` okunmuyor → K10b1+b1b+b2+b3.
Eski pinler silinmedi, gerekçeleriyle güncellendi: `test_verdict_reviewer_k1_d1.py::B1d` (kapsam K10 ile GENİŞLETİLDİ,
B1'in 4 zinciri artık ALT KÜME) · `B1e` (elle-liste → koddan türeyen küme) · `B1f` ("99" hâlâ geçersiz ama artık
"15'ten büyük" diye değil, **L2'yi aştığı** için).

**DOĞRULANMADI:** gerçek SAP'ye karşı hiçbir süre · 900 sn üst sınırın pratikte anlamlılığı · Windows dışı davranış ·
canlı gate'lerin (`check_table_field_drop`, `check_sap_active_version`, `check_sap_struct_consistency`,
`check_standard_table_fields`) KENDİ içlerine bütçe eklenmesinin etkisi (eklenmedi; zincir katmanı kesiyor).

## 21. DDIC şeridi — Z tablo, tablo tipi, metin havuzu, `ccdef`/`ccmac` (2026-09-21, Z38-Z41)

Kaynak reçeteler (çekirdek playbook: Z tablo bölümü, tablo tipi bölümü, metin havuzu "6 zorunlu cephe"; ilgili ders + kontrol
listesi maddeleri) okundu, genelleştirilerek taşındı. **Hiçbiri canlı SAP'de yazılarak ölçülmedi** (şerit brifinginde canlı yazma onayı yok);
yalnız okuma kalibrasyonu canlı yapıldı (DD40L kolonları + XML ↔ DD40L eşlemesi, standart tablo tipinde).

| Dosya | Ne |
|---|---|
| `tools/ddic.py` | `adt_table_create`, `adt_ttyp_create` (`available_on=("s4_private",)`) |
| `tools/textpool.py` | `adt_textpool_write` (`s4_private`) |
| `lib/utils/ddic_tablo.py` | tablo ön kontrolü (T1-T9) · DDL render · aktif DDL readback kıyası (varsayılan `client : abap.clnt` kabuğunu yakalar) |
| `lib/utils/ddic_ttyp.py` | tablo tipi ön kontrolü (Y1-Y6) · POST/düzeltme XML'i · XML okuyucu · DD40L sorgusu · iki kanal kıyası |
| `lib/utils/textpool.py` | metin havuzu ön kontrolü (P1-P7) · CRLF yük üretimi · ayrıştırma · silinecek giriş · aktif readback kıyası |
| `lib/sap_adt_lib.py` | `create_table_with_ddl`: kabuk POST (DDL'siz) → stateful LOCK → PUT (If-Match yok, corrNr = kilit CORRNR) → UNLOCK finally; hata `stage` taşır |
| `_reviewer.py` | `run_reviewer_tablo` + `COMPOSITE_TOOL_TO_TASK["adt_table_create"] = "table_creation"` |
| `gate.py` / `guardrails.py` / `hints.py` / `tools/shells.py` / `tools/atom.py` | transport listesi, reviewer listesi, `TMP_MUAF_ARACLAR += adt_ttyp_create`, ipucu tipleri, `table` desteksiz metni, ttyp sonraki adım, `_YAZILABILIR_INCLUDE += definitions, macros` + `write_path_measured` |

Kararlar: `adt_table_create` `$TMP`'de de transport ister (transportsuz kilit ölçülmedi; yapı aracıyla aynı gerekçe — canlı ölçüm planında ayrı
adım, sonuca göre lider açar) · tablo tipinde birincil ölçü DD40L, iki kanal çelişkisi FAIL, düzeltme tek sefer · metin havuzunda başlıklar
desteklenmez, canlıdaki girişi silecek PUT `allow_remove` olmadan yazılmaz · `ccdef`/`ccmac` yazma yolu ölçülmediği için yanıt beyan eder.

Testler: `tests/test_ddic_textpool.py` (19) + `test_new_write_tools.py` B2 güncellendi, B2b eklendi. Red-first: taban kopyada `ImportError`
(ddic) ve B2/B2b FAIL. Mutasyonlar (repo dışı kopya) ve kırılan testler: düzeltme dalı silindi → Y2 + Y3 · kanal çelişkisi dalı → Y4 ·
tablo PUT'a If-Match → T1 · varsayılan kabuk tespiti → T2 · `=?` kontrolü → P3 · PROG/PX aktivasyonu → P1 · silme koruması → P2 ·
ccdef/ccmac çıkarıldı → B2 + B2b.

**DOĞRULANMADI:** üç aracın canlı yazma yolu · `ccdef`/`ccmac` PUT · tablo tipi düzeltme PUT'u · `keyComponents` POST biçimi · transportsuz tablo kilidi.

## 22. v0.5.1 DDIC sağlamlaştırma — varlık üç değerli, `AlreadyExists` başarı değil, belirsiz sonuç açık (Z50-Z53)

### 22.1 Yeni / değişen hata kodları (Z51 ⓒ)
| Kod | Araç | Anlam | Çıkış |
|---|---|---|---|
| `exists_unmeasured` | `adt_domain_create`, `adt_dtel_create` (yeni; struct/table/ttyp'de zaten vardı) | varlık ön kontrolü ölçülemedi (404 dışı hata/istisna) — POST atılmadı | 1 |
| `already_exists` | domain · dtel · struct | ön kontrol "var" dedi ya da POST 400/405 `AlreadyExists` döndü — kaynak yazılmadı, aktivasyon yok | 1 |
| `already_exists_after_retry` | domain · dtel · struct | POST 5xx/zaman aşımı/bağlantı hatası → kütüphanenin sessiz yeniden denemesi → `AlreadyExists`; `own_shell_possible:true` (kabuğu büyük olasılıkla önceki deneme yarattı — kanıtlanmadı) → `adt_get` ile bak | 1 |
| `validation_error` (paket) | struct · table · ttyp | boş ya da yalnız boşluk `package` araç kapısında reddedilir, ağ çağrısı sıfır | 1 |
| `outcome_uncertain` alanı | table (`partial_shell`) · ttyp (onarım) · textpool (`lock_failed`/`put_failed`) | istek gönderildi, HTTP yanıtı yerine ağ istisnası geldi → yazıldığı / kilit durumu BELİRSİZ | 1 |
| `unlock_ok` / `unlock_warning` | `adt_push_source` `func` ve `bdef` | UNLOCK 200/204 değil ya da istisna → uyarı (SM12; AI kilit silmez) | `ok`'u bozmaz |
CLI eşlemesi (`sap_adt_cli._sonuc_hatasi`): yeni kodlar `GATE_RESULT_ERRORS`/`USAGE_RESULT_ERRORS`'ta yok → çıkış 1, `already_exists` ile aynı.
`populate`: bilinmeyen kod satır hatasıdır (koşum sürer) — §19 sınıflandırma tablosuna eklendi.

### 22.2 Kütüphane: `AlreadyExists` artık başarı değil (kardeş taraması)
`sap_adt_lib.py`'de 400/405 + `AlreadyExists` gövdesine bakan dallar (ortak yardımcılar `_zaten_var_mi`, `_zaten_var_hatasi`, `_yeniden_denendi_mi`):
| Metot | Önce | Şimdi | Çağıran (aXet) |
|---|---|---|---|
| `create_dataelement` | `True` (başarı) → composite aktive ediyordu | `SAPObjectExistsError` | `adt_dtel_create` |
| `create_domain` | `True` → aktivasyon | `SAPObjectExistsError` | `adt_domain_create` |
| `create_structure` | 2026-09-21'de düzeltilmişti (`SAPObjectExistsError`) | aynı + yeniden deneme eki | `adt_struct_create` |
| `create_cds_view` | başarı sözlüğü | `SAPObjectExistsError` | yok (lib dışı çağıran bulunmadı) |
| `create_function_group` | başarı | `SAPObjectExistsError` | yok |
| `create_function_module` | başarı | `SAPObjectExistsError` | yok |
| `create_behavior_definition` (Z51 ⓑ) | `not in [200,201]` kontrolünden önce ayrım yoktu | `SAPObjectExistsError` (201 kontrolünden ÖNCE) | yok |
`_retry_request` her istekte `_son_yeniden_denemeler`'i sıfırlar; CSRF dışı yeniden deneme sebeplerini (5xx/zaman aşımı/bağlantı
hatası — `_should_retry` + iki istisna dalının kaydettiği küme) ekler ⇒ istisna `after_retry` taşır ve mesaj eki `ONCEKI_DENEME_IZI`
("ÖNCEKİ DENEME …", sebeplerle) ile başlar. Composite (`_yeniden_deneme_izi`) sap_client sarmalayıcıları istisnayı yutup yalnız
`[ERROR] <mesaj>` bastığı için kararı log'dan okur: ① BİRİNCİL kütüphane hükmü (`ONCEKI_DENEME_IZI` — kayıt listesinden türetilir)
② YEDEK `[RETRY] … Server error 5xx|Timeout|Connection error` satırı (aynı üç sebep; CSRF hariç — istek işlenmedi).
**Bug gate düzeltmesi (v0.5.1):** ilk sürüm yalnız `[RETRY] … 5xx|Timeout` regex'ine bakıyordu → bağlantı kopması sonrası
yeniden deneme 405 alınca log "ÖNCEKİ DENEME" derken kod düz `already_exists` dönüyordu (çelişki). Neden kayıt listesine doğrudan
(`client.adt_client._son_yeniden_denemeler`) bakılmadı: sarmalayıcı istisnayı yuttuktan sonra listenin son POST'a ait olduğu
yalnız "arada başka istek yok" varsayımıyla doğru olur; hüküm istisna ANINDA mesaja gömüldüğü için bu varsayım gerekmez.
Testler: D9 (domain, bağlantı → retry → 405 · kontrol: retry'sız, yalnız CSRF) · S9b (yapı, bağlantı kolu) · S9c (iki iz ayrı
ayrı + kütüphane eki yalnız liste doluyken).
**ÖLÇÜLMEDİ:** var olan objenin başkasına ait inaktif sürümünün eski yolda aktive edilip edilmediği (canlı yok) — kanıtlanan yalnız çevrimdışı:
eski kodda POST 405 → `ok:true` + aktivasyon çağrısı 1 (test D7 eski koda karşı).

### 22.3 Diğer düzeltmeler
- **Z53:** `atom._adt_get_oku` DDL tip düzeltmesi (`_ddl_kaynak_turu`, ilk `define table|structure`); `adt_struct_create` ön kontrolü bunu kullanır.
  Bug gate düzeltmesi (v0.5.1): arama öncesi `/* … */` blok ve `//` satır yorumları atılır, tırnaklı dizgi korunur (`_ddl_yorumsuz`;
  ölçülen kusur `/*\ndefine structure old\n*/\ndefine table` → structure). Test S6c. `--` yorum biçimi ele alınmadı (DDL'de
  geçerliliği bu turda doğrulanmadı).
  Sahte istemci S6 canlı davranışa çekildi (yapı ucu da 200 + `define table`) — eski kodda `existing_kind: structure` ile FAIL.
- **Z50 ⓒ:** `create_table_with_ddl` gönderilen son isteği (`lock`/`put`) izler, genel istisnaya `outcome_uncertain` koyar.
- **Z50 ⓓ/ⓔ:** FM UNLOCK `except: pass` kaldırıldı; BDEF UNLOCK durum kodu okunur — `unlock_ok`/`unlock_warning` deseni (tablo aracındaki gibi).
- **Z50 ⓐ / ⓑ-ttyp:** `main`'de zaten kapalıydı (ttyp onarım `t2` doğrulaması Y17; katalog hata listesi) — yalnız mutasyonla kalibre edildi.

### 22.4 Testler
`tests/test_ddic_textpool.py` S6 (yeniden yazıldı) · S6b · S9 (gerçek `_retry_request`) · S10 (6 metot × 405/400/201) · S11 (paket 3 araç × 2) ·
S12 (FM unlock 4 durum) · S13 (BDEF unlock) · S14 (belirsiz mesajlar + HTTP-ret kontrol grupları) · `tests/test_msgclass_domain.py` D6-D8.
`tests/test_populate_hat.py` U2 / L4: sahte istemcilere `get_ddic_object` (404) eklendi — ön kontrol artık `adt_get` üzerinden ölçtüğü için bu
yöntemi taşımayan sahte `exists_unmeasured` üretip yaratma yoluna hiç girmiyordu (testlerin amacı değişmedi).
Canlı SAP'de ölçülmedi.
