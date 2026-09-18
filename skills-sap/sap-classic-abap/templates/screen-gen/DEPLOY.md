# Ekran üreteci kiti + ALV şablonları — kurulum sırası

> `ZBC000` nötr ortak paket gövdesidir; kendi ortak paketinin gövdesiyle değiştir (`%sap-dev` → `references/naming.md` §3).
> Adı değiştirirsen **tüm** kit dosyalarında aynı gövdeyi kullan (FM imzasındaki tablo tipi adları, FM içindeki şablon atfı,
> programların başlık yorumları). Kit ne işe yarar: `references/screen-gen-kit.md`.
>
> ⚠ **DOĞRULANMADI:** kit kaynakları (yapılar, FM, programlar) bu biçimleriyle SAP'de **derlenmedi ve canlı
> çalıştırılmadı**. Kaynak ekipte canlı çalışan sürümlerden ad, varsayılan donör, yorum ve şablon düzeltmeleriyle
> türetildi (farklar: `screen-gen-kit.md` §8 ve her programın başlık yorumu). Her adımın doğrulamasını atlama.

**Profil:** yalnız `ecc` / `s4_private` (klasik obje). `s4_public`/`btp_abap` → DUR, kullanıcıya bildir.
**Kullanıcıdan gelir, uydurulmaz:** paket (`_CLC`), transport, obje açıklamaları, ekran başlıkları, buton metinleri.
**CLI:** `python <TEMPLATE>/skills-sap/sap-adt-foundation/scripts/sap_adt_cli.py <araç> --args-json '{…}'` (uzun kaynakta
`--args-file`). Yazma araçları: `--sap-write --scope <S0|S1|S2> --reason "<gerekçe>"` (ya da `--intake …`); kapsam
`%sap-intake-triage` sınıfıdır. Aşağıda `sap_adt_cli.py` kısaltmadır.

## Dağılım özeti
| # | Adım | Kim | Araç |
|---|---|---|---|
| 0 | Sistemde zaten var mı? | CLI (okuma) | `adt_search_objects`, `adt_get` |
| 1 | Paket | **kullanıcı** | SE80/SE21 (kesin yasak C: paket yaratılmaz) · CLI okuma `adt_package_contents` |
| 2 | İki DDIC yapı | CLI (yazma) | `adt_struct_create` → `adt_get` → `adt_push_source` → `adt_activate` |
| 3 | İki tablo tipi | CLI (yazma) · satır tipi düzeltmesi **kullanıcı** | `adt_post_shell` `ttyp` → `adt_activate` → `DD40L.ROWTYPE` (`table-types.md`) · düzeltme SE11 |
| 4 | Fonksiyon grubu + FM kabuğu + FM kaynağı | CLI (yazma) | `adt_post_shell` `fugr` → `adt_activate` `fugr` → `adt_post_shell` `func` → `adt_get` → `adt_push_source` `func` |
| 5 | Remote-Enabled Module | **kullanıcı** | SE37 (CLI'de RFC-enable aracı yok) |
| 6 | Aktivasyon doğrulaması | CLI (okuma) | `adt_get`, `adt_sql_query`, `adt_inactive_objects` |
| 7 | Dört şablon program | CLI (yazma) | `adt_post_shell` → `adt_get` → `adt_push_source` → `adt_activate` |
| 8 | Ekranları üretme | CLI (yazma) · ara yol **kullanıcı** | Yol 0 `adt_screen_generate` · Yol A SE37 test (DOĞRULANMADI) · Yol B SE51 + SE41 |
| 9 | Çalıştırıp doğrulama | **kullanıcı** (GUI) + CLI | SE38 · `adt_inactive_objects` · `adt_screen_generate` `mode:"READ"` |

Adım 3, 4 ve 8'deki CLI yolları 2026-09-13'te eklendi: **çevrimdışı test edildi, canlı DOĞRULANMADI**. Araç reddederse ya da
canlıda düşerse o adımın kullanıcı ara yoluna geç; ham REST/SOAP ile yazılmaz. `fugr`/`func` tipleri ve `adt_screen_generate`
yalnız `ecc`/`s4_private`'ta açıktır (aksi `type_not_available_for_profile` / `tool_not_available_for_profile`).

---

## Adım 0 — Sistemde ortak bir ekran üreteci / şablon ailesi zaten var mı? (EN BAŞTA)
```text
sap_adt_cli.py adt_search_objects --args-json '{"query":"*_FM_SCREEN_GEN","max_results":50}'
sap_adt_cli.py adt_search_objects --args-json '{"query":"*_FG_SCREEN_GEN","max_results":50}'
sap_adt_cli.py adt_search_objects --args-json '{"query":"*_P_ALV_TEMP*","max_results":50,"object_type":"PROG"}'
sap_adt_cli.py adt_search_objects --args-json '{"query":"*_TT_SCREEN_*","max_results":50}'
```
- FM aramasında `object_type` filtresi **verme**: `FUNC` filtresi var olan FM için 0 dönebilir (`references/fugr-fm.md` §4).
- **Varsa YENİDEN KURMA, onu kullan:** `adt_get {"name":"<bulunan FM>","object_type":"func"}` ile kaynağını ve imzasını OKU
  (imzayı bu kitten varsayma — sürümü farklı olabilir); `adt_sql_query` ile RFC işaretini ölç (Adım 6). Adım 8'e geç.
  Mevcut şablon programlar varsa onları referans al; kopya aile kurmadan önce kullanıcıya sor.
- Sonuç 0 ise "yok" demeden önce `count`/`ok` alanlarına bak (`ok:false` = ölçülemedi). Kararı kullanıcıyla ver:
  ortak araç kurmak ortak pakete yeni obje demektir.

## Adım 1 — Paket (kullanıcı)
- Kullanıcı ortak `_CLC` paketini verir (yoksa **o** yaratır; model paket yaratmaz — kesin yasak C).
- Doğrula: `sap_adt_cli.py adt_package_contents --args-json '{"package":"<PAKET>"}'` → `package_verified:true` bekle.
- Transport kullanıcıdan; iş bir transporta bağlıysa hep aynısı.

## Adım 2 — Yapılar `ZBC000_S_SCREEN_BUTTON`, `ZBC000_S_SCREEN_FIELD` (CLI)
`adt_struct_create` imzası uygun (`name`, `fields=[{name,type}]`, `description`, `package`, `transport`); ama araç alanları
tek başına yazmayabilir (ölçülmüş yer tutucu vakası, `%sap-adt-foundation` → `references/foundation-ops.md` §3.2) → tam DDL
ayrıca gönderilir.
1. Yokluk: `adt_get {"name":"ZBC000_S_SCREEN_BUTTON","object_type":"structure","include_source":false}` + `adt_search_objects`.
2. Yarat (yazma):
   ```text
   sap_adt_cli.py adt_struct_create --sap-write --scope <S> --reason "ekran üreteci kiti yapısı" --args-file btn.json
   ```
   `btn.json`: `{"name":"ZBC000_S_SCREEN_BUTTON","description":"<kullanıcının onayladığı metin>","package":"<PAKET>","transport":"<TR>",
   "fields":[{"name":"FCODE","type":"GUI_FUNC"},{"name":"TEXT","type":"GUI_TEXT"},{"name":"ICON","type":"ICON_D"},
   {"name":"QUICKINFO","type":"GUI_INFO"},{"name":"FKEY","type":"CUA_PFNO"}]}`.
   Alan yapısı için alanlar ve tipler `ZBC000_S_SCREEN_FIELD.structure.ddl`'den (19 alan) aynı biçimde.
   Açıklama önerisi DDL'deki `@EndUserText.label` metnidir (kaynak ekibin metni) — kullanıcı onaylar.
3. Pull: `adt_get {"name":"…","object_type":"structure","include_source":true}` (push'un ön şartı).
4. Tam DDL (yazma): `adt_push_source {"name":"…","object_type":"structure","source":"<.ddl dosyası, baştaki // satırları SİLİNMİŞ>"}`.
5. `adt_activate {"name":"…","object_type":"structure"}` (push aktive ettiyse no-op olabilir).
6. **Doğrula:** `adt_get` (aktif kaynak) → BUTTON **5**, FIELD **19** alan, adlar DDL ile birebir (FM `MOVE-CORRESPONDING`
   ile `RPY_DYFATC`'ye aktarır, ad sapması **sessizce** veri kaybettirir) · metadata `masterLanguage` = proje dili ·
   `adt_inactive_objects` bu iki objeyi içermez.

## Adım 3 — Tablo tipleri (CLI; satır tipi düzeltmesi kullanıcı)
`table-types.md` → `adt_post_shell` `ttyp` + `adt_activate` + `DD40L.ROWTYPE` doğrulaması. Yapılar (Adım 2) aktif olmadan başlanmaz.
`ROWTYPE` boşsa ya da araç düşerse aynı dosyadaki SE11 ara yolu (kullanıcı).

## Adım 4 — Fonksiyon grubu + FM (CLI)
Yollar: `references/fugr-fm.md` §0. Kaynağı önce yerelde `%code-review` ile inceletin (FM push'unda gömülü inceleme yok, `SKIP`).
Açıklamalar kullanıcı onaylı, proje dilinde, ≤ 60 karakter (boş → `ADR_0005_D`). Tablo tipleri (Adım 3) aktif değilse imza derlenmez.
1. **Fonksiyon grubu** `ZBC000_FG_SCREEN_GEN` (Adım 0'da yokluğu ölçüldü):
   ```text
   sap_adt_cli.py adt_post_shell --sap-write --scope <S> --reason "ekran üreteci fonksiyon grubu" --args-json '{"object_type":"fugr","name":"ZBC000_FG_SCREEN_GEN","package":"<PAKET>","transport":"<TR>","description":"<kullanıcının onayladığı metin>"}'
   sap_adt_cli.py adt_activate --sap-write --scope <S> --reason "fonksiyon grubu aktivasyonu" --args-json '{"name":"ZBC000_FG_SCREEN_GEN","object_type":"fugr"}'
   ```
   Açıklama önerisi (kaynak ekibin metni): `Ekran + GUI status üreteci` — kullanıcı onaylar.
   Grubu yaratınca SAP ana programı ve TOP include'u **kendisi** üretir → `ZBC000_FG_SCREEN_GEN.fugr-main.abap` ve
   `LZBC000_FG_SCREEN_GENTOP.abap` yalnız karşılaştırma içindir (TOP'ta `FUNCTION-POOL` satırı dışında içerik yok).
2. **FM kabuğu** `ZBC000_FM_SCREEN_GEN` bu grupta:
   ```text
   sap_adt_cli.py adt_post_shell --sap-write --scope <S> --reason "ekran üreteci FM kabuğu" --args-json '{"object_type":"func","name":"ZBC000_FM_SCREEN_GEN","package":"<PAKET>","transport":"<TR>","description":"<kullanıcının onayladığı metin>","extra":{"function_group":"ZBC000_FG_SCREEN_GEN"}}'
   ```
   Açıklama önerisi (kaynak ekibin metni): `Dynpro ekranı + GUI status üreteci (RFC)` — kullanıcı onaylar.
   `ok:false` "yaratılmadı" değildir → retry etmeden `exists_after`.
3. **Kaynak** (`ZBC000_FM_SCREEN_GEN.func.abap` dosyasının **tamamı**; imza satır içi `FUNCTION … IMPORTING … TABLES …`, `*"` yorum bloğu yok):
   ```text
   sap_adt_cli.py adt_get --args-json '{"name":"ZBC000_FM_SCREEN_GEN","object_type":"func","include_source":true}'   # pull-before-edit kaydı
   sap_adt_cli.py adt_push_source --sap-write --scope <S> --reason "ekran üreteci FM kaynağı" --args-file fm.json      # {"name":"ZBC000_FM_SCREEN_GEN","object_type":"func","source":<dosya içeriği>,"transport":"<TR>"}
   ```
   - Araç grubu canlıdan çözer (Z/Y şart), kaynağı yükler ve FM'i **kendisi aktive eder** (`adt_activate` FM'i aktive edemez).
     Aktivasyon düşerse `push_failed` + `activation_errors` (kaynak yüklenmiştir) → hata satırlarını `%code-review` ile düzelt;
     kodu tahminle değiştirme.
   - Yeni FM arama indeksinde henüz yoksa `adt_get func` `exists:false` dönebilir → pull kaydı alınamaz, push
     `pull_before_edit_missing` verir (DOĞRULANMADI). Retry döngüsüne girme; `adt_search_objects` ile ölç, kullanıcıya bildir.
4. **Ara yol (kullanıcı; araç reddi ya da canlı hata):** ADT *New → ABAP Function Group* / *New → ABAP Function Module* (ya da
   SE80) → dosyanın tamamını ADT FM editörüne yapıştır → kaydet → aktive et → editörü KAPAT. SE37 klasik editöründe imza
   sekmelerden girilir; satır içi imzanın SE37'ye yapıştırılması **DOĞRULANMADI** → ADT tercih.

## Adım 5 — Remote-Enabled Module (kullanıcı)
SE37 → `ZBC000_FM_SCREEN_GEN` → Değiştir → **Özellikler** → İşleme tipi **Uzaktan erişilebilen modül (Remote-Enabled)** →
kaydet → aktive et → KAPAT. Yaratma XML'inde RFC bayrağı `400` verir; bilinen çalışan yol bu tek tıktır (`fugr-fm.md` §3).
aXet CLI'de RFC-enable aracı yoktur (`tool-catalog.md` "Olmayan araçlar").

## Adım 6 — Aktivasyon doğrulaması (CLI, okuma)
```text
sap_adt_cli.py adt_get --args-json '{"name":"ZBC000_FM_SCREEN_GEN","object_type":"func"}'
sap_adt_cli.py adt_sql_query --args-json '{"query":"SELECT FUNCNAME, FMODE, PNAME FROM TFDIR WHERE FUNCNAME = '"'"'ZBC000_FM_SCREEN_GEN'"'"'"}'
sap_adt_cli.py adt_inactive_objects
```
- `adt_get func`: `exists:true`, `function_group` = `ZBC000_FG_SCREEN_GEN`, kaynak yereldeki dosyayla aynı (boşluk/satır sonu
  normalize ederek kıyasla). `adt_get` `func` için güvenilmez olabilir → okunamazsa `adt_where_used {"object_type":"func"}`
  ya da ana include `LZBC000_FG_SCREEN_GENUXX` → `…U01` okuması (`fugr-fm.md` §4.1).
- `TFDIR.FMODE = 'R'` → RFC işareti var. Boş → Adım 5 yapılmamış.
- `adt_inactive_objects`: kit objelerinin hiçbiri listede değil (`count_verified:true` iken).

## Adım 7 — Dört şablon program (CLI)
Dosyalar: `templates/alv-temp1-docking.prog.abap` → `ZBC000_P_ALV_TEMP1`, `alv-temp2-custom-container` → `…TEMP2`,
`alv-temp3-split-master-detail` → `…TEMP3`, `alv-temp4-screen-gen-demo` → `…TEMP4`. Tek gövde demo (include yok).
Yasak B: programlar standart tabloyu yalnız okur (`SELECT`); push kapısı doğrudan DML'i zaten reddeder.

Her program için sırayla (kapsam beyanı her yazma çağrısında):
```text
sap_adt_cli.py adt_get --args-json '{"name":"ZBC000_P_ALV_TEMP1","object_type":"program","include_source":false}'   # exists:false beklenir
sap_adt_cli.py adt_post_shell --sap-write --scope <S> --reason "ALV şablonu" --args-json '{"object_type":"program","name":"ZBC000_P_ALV_TEMP1","package":"<PAKET>","transport":"<TR>","description":"<kullanıcının onayladığı metin>"}'
sap_adt_cli.py adt_get --args-json '{"name":"ZBC000_P_ALV_TEMP1","object_type":"program","include_source":true}'    # pull-before-edit kaydı
sap_adt_cli.py adt_push_source --sap-write --scope <S> --reason "ALV şablonu kaynağı" --args-file temp1.json            # {"name":…,"object_type":"program","source":<dosya içeriği>}
sap_adt_cli.py adt_activate --sap-write --scope <S> --reason "ALV şablonu aktivasyonu" --args-json '{"name":"ZBC000_P_ALV_TEMP1","object_type":"program"}'
sap_adt_cli.py adt_inactive_objects
```
- `adt_post_shell` `ok:false` "yaratılmadı" değildir → `exists_after`'a bak (`true`: tekrar yaratma).
- Açıklama ≤ 60 karakter, proje dilinde. Kaynak ekibin açıklamaları (öneri, kullanıcı onaylar): TEMP1 `ALV şablonu - Docking`,
  TEMP2 `ALV şablonu - Custom Container`, TEMP3 `ALV şablonu - Split (Master-Detail)`; TEMP4 için kaynakta açıklama kaydı yok → kullanıcı belirler.
- Yaratma sonrası metadata'dan `masterLanguage` = proje dili (`known-errors-adt.md` K-17).
- `activation_verified:false` / `readback_verified:null` "tamam" değildir → `adt_inactive_objects` + aktif kaynak okuması.
- Programlar ekran olmadan da aktive olur (ekran/status çalışma anında aranır) → aktif program ≠ çalışır program; Adım 8–9 şart.
- **Seçim metinleri** (`S_VBELN`, TEMP4'te `P_DYNNR`): CLI'de metin havuzu aracı yok → kullanıcı SE38 → Metin elemanları →
  Seçim metinleri → **Sözlük referansı** işaretler (metin DDIC'ten gelir, uydurulmaz) → kaydet → aktive et → KAPAT.

## Adım 8 — Ekranları ve GUI status'ları üretme (CLI; ara yol kullanıcı)
Çağrı değerleri (ekran başına): `references/screen-gen-kit.md` §4; parametre ↔ argüman eşlemesi ve hata kodları §6.
Başlık/buton metinleri kullanıcıdan. Ham SOAP/REST ile SAP'ye yazan script yazılmaz; `adt_classrun` bu FM'i koşamaz
(diyalog bağlamı → `400 Session Timed Out`, K-14). Önkoşul: Adım 5 (RFC işareti) + Adım 6 (`TFDIR.FMODE='R'`) + Adım 7.

**Yol 0 — `adt_screen_generate` (CLI, yazma; yalnız `ecc`/`s4_private`; çevrimdışı test edildi, canlı DOĞRULANMADI).**
Araç FM'i SOAP-RFC ile çağırır (`sap-language` = `master_language`, `TABLES` daima boş etiketle); FM'i yaratmaz. `mode` READ dahil
her çağrı yazma sınıfıdır (`--sap-write` + kapsam + onay); `transport` WRITE/DELETE'te, `title` WRITE'ta zorunlu.
İlk çağrıyı TEMP1 (tek ekran, buton/alan yok) ile yap, sonucu `%remember` ile kaydet.
```text
sap_adt_cli.py adt_screen_generate --sap-write --scope <S> --reason "TEMP1 ekranı ve GUI status" --args-file t1.json
```
Her çağrıda ortak argümanlar: `"fm_name":"ZBC000_FM_SCREEN_GEN"`, `"mode":"WRITE"`, `"src_prog":"SAPLKKBL"`, `"src_status":"STANDARD"`,
`"nav_remap":" "`, `"transport":"<TR>"`, `"title":"<kullanıcıdan>"`. `cua_merge` ve `recreate` **verilmez** (araç yalnız açıkça
verilince gönderir → FM varsayılanı: merge açık, yeniden kurma yok).

| Program / ekran | Çağrıya özel argümanlar | Beklenen |
|---|---|---|
| TEMP1 | `"program":"ZBC000_P_ALV_TEMP1","dynpro":"0100","screen_type":"DOCKING"` | `ok:true` · `nav_remap=ON` · `cua_merge=none` |
| TEMP2 | `"program":"ZBC000_P_ALV_TEMP2","dynpro":"0100","screen_type":"CONTAINER","cc_name":"CC_ALV"` | `ok:true` · `nav_remap=ON` |
| TEMP3 | `"program":"ZBC000_P_ALV_TEMP3","dynpro":"0200","screen_type":"CONTAINER","cc_name":"CC_ALV"` | `ok:true` · `nav_remap=ON` |
| TEMP4 ① | `"program":"ZBC000_P_ALV_TEMP4","dynpro":"0100","screen_type":"DOCKING"` | `cua_merge=none` (ilk yazım) |
| TEMP4 ② | `"program":"ZBC000_P_ALV_TEMP4","dynpro":"0200","screen_type":"CONTAINER","cc_name":"CC_ALV","buttons":[{"FCODE":"REFRESH","TEXT":"<kullanıcıdan>","ICON":"ICON_REFRESH","QUICKINFO":"<kullanıcıdan>","FKEY":""}]` (ikon adını ICON tablosunda doğrula) | `cua_merge=ok kept_status=1` |
| TEMP4 ③ | `"program":"ZBC000_P_ALV_TEMP4","dynpro":"0300","screen_type":"DOCKING","fields":[{"NAME":"VBAK-VBELN","TYPE":"TEXT","FROM_DICT":"X","LINE":"2","COLUMN":"2"},{"NAME":"VBAK-VBELN","TYPE":"TEMPLATE","FROM_DICT":"X","LINE":"2","COLUMN":"25"}, …]` (4 satır: `screen-gen-kit.md` §4 örneği, DOĞRULANMADI) | `cua_merge=ok kept_status=2` · `fields=4` |

Sonucu okuma:
- `ok:true` yalnız `ev_rc == 0` ve (WRITE'ta) `nav_remap≠OFF`. `ev_message` kırpılmaz; `signals` altındaki `nav_remap`, `cua_merge`,
  `fields`, `donor`, `dikkat[]` değerlerini `screen-gen-kit.md` §3 tablosuyla kıyasla.
- `error: screen_gen_rc` → `ev_rc_band` + `ev_rc_note` (`bilesik` 1-18: rc=2 "ekran zaten var" olabilir, karar kullanıcıyla ·
  `fields_invalid` 5 · `donor_fetch` 101-113 · `donor_status_missing` 120-130 · `merge_fetch` 202-213 · `dynpro_invalid` 300 · `zy_guard` 301).
- `error: nav_remap_off` → çağrı yanlış; ekranı kullanmadan düzelt. `error: soap_fault` → mesajı oku, Adım 5-6 ölçümünü tekrarla.
  `error: ev_rc_missing` → yanıtta `EV_RC` yok; FM imzasını kaynağından kıyasla (Adım 0).
- `warnings` → ölçülemeyen sinyal ya da açıkça verilmiş yıkıcı argüman; "tamam" sayma.
- TEMP4'te her yazımdan önce/sonra aynı araçla `"mode":"READ"` (transport ve title gerekmez) → `[FN:` dökümünü diff'le.

**Yol A — SE37 test ekranı (kullanıcı; araç kullanılamıyorsa; DOĞRULANMADI):** SE37 → `ZBC000_FM_SCREEN_GEN` → Test (F8) → parametreleri gir (tabloları
tablo editöründen) → çalıştır → `EV_RC` + `EV_MESSAGE`'ı **tamamını** kopyala. Diyalog bağlamının SE37 testinde sağlanıp
`RPY_DYNPRO_INSERT`/`RS_CUA_INTERNAL_WRITE`/`RS_CUA_GENERATE`'in çalıştığı, `IV_TRANSPORT` boşken transport sorgu penceresi
çıkıp çıkmadığı **ölçülmedi** → ilk denemeyi TEMP1 (tek ekran, buton/alan yok) ile yap, sonucu `%remember` ile kaydet.
Kontrol: `EV_RC` bandı + `nav_remap=ON(…)` + `cua_merge=…` (`screen-gen-kit.md` §3).

**Yol B — Screen Painter + Menu Painter (elle, üreteçsiz):** `references/dynpro-gui-status.md` §2 tarifini ekran başına
somut değerlerle ver: ekran no, tip Normal, akış `MODULE status_<n>` / `user_command_<n>`, CONTAINER ekranında custom
control `CC_ALV` (satır/sütun 1/1, boy 200×255, yeniden boyutlanma dikey+yatay açık), status `STAT<n>` (F3 `BACK`,
Shift+F3 `EXIT`, F12 `CANCEL`, normal tip), başlık `TIT<n>`; TEMP4/0200'de uygulama toolbar'ına `REFRESH`; TEMP4/0300'de
alanlar (`screen-gen-kit.md` §4). Kaydet → üret → KAPAT.

**Başka bir RFC test yolu** (sistemde çalışan başka bir RFC istemcisi) kullanıcıda varsa aynı parametrelerle kullanılabilir —
bu kitte **denenmedi**.

⛔ `IV_CUA_MERGE` / `cua_merge`'i boş/`-` gönderme (diğer ekranların status'ünü **siler**) · `IV_RECREATE='X'` / `recreate:"X"` ve
`IV_MODE='DELETE'` / `mode:"DELETE"` ekranı siler (INSERT düşerse ekran kaybolur) · `IV_PROGRAM` Z/Y dışı → FM'de `EV_RC=301`
(korumayı **var olmayan** adla dene); Yol 0'da Z/Y dışı `program`/`fm_name` zaten kapıda `ADR_0005_A` ile reddedilir.

## Adım 9 — Çalıştırıp doğrulama
- Üretim sonrası CLI: `adt_inactive_objects` (ekran/status yazımı programı inaktif bırakmamalı).
- Üreteç yolu: `adt_screen_generate` `"mode":"READ"` (Yol A'da `IV_MODE='READ'`) → `ev_message` / `EV_MESSAGE`'da `HEADER lines=200 cols=255` (CONTAINER) · container `CUST_CTRL CC_ALV …
  rvX rhX` · `TITLES=… TIT<n>` · `FLOW: / PROCESS BEFORE OUTPUT. / MODULE status_<n>. …` · `[FN:` dökümü (buton metin/ikon).
  Çok ekranlı TEMP4'te her yazımdan önce/sonra `[FN:` dökümünü diff'le (`dynpro-gui-status.md` §6).
- **GUI (kullanıcı çalıştırır, statik okumayla kanıtlanamaz):**
  | Program | Kontrol |
  |---|---|
  | hepsi | F3/F12/ESC → seçim ekranına döner · Shift+F3 → programdan çıkar · `00256` / `00264` yok · başlık proje dilinde |
  | hepsi | ALV paritesi: sıralama, operatörlü filtre, kolon göster/gizle, varyant kaydet (`i_save='A'`), Excel'e aktarma (filtreye uyan tüm satırlar) |
  | TEMP1/2 | hotspot/çift tık doğru belgeyi gösterir — **sıralı ve toplamlı** gridde de |
  | TEMP2/3 | ALV pencereyi dolduruyor (pencere boyutu değişince de) |
  | TEMP3 | üst gridi sırala → çift tık → alt gridde doğru belgenin kalemleri; geri dönüp yeni seçimle çalıştırınca eski kalemler yok |
  | TEMP4 | `P_DYNNR` 0100 / 0200 / 0300 üçü de açılır; 0200'de `REFRESH` butonu tepki verir; 0300'de alanlar etiketli; geri dönüp başka `P_DYNNR` ile çalıştırınca ALV görünür; `NAV REMAP YOK` mesajı **çıkmamalı** |
- ATC: `adt_atc_check` her program için; öncelik politikası proje `AGENTS.md`'sinde (yoksa öncelik 1 zorunlu düzeltilir,
  2/3 kullanıcıya gösterilip açık onayla geçilir). FM'deki `TADIR` okuması clean-core önerisi üretebilir → gerekçe FM
  yorumunda (`I_CustABAPObjDirectoryEntry` bu amaçla ölçülüp elendi); kullanıcıya göster.
- Kapanış: `%code-review` → `%verify-done` → paket `SESSION_NOTES.md`. Çalışan yöntem (özellikle Adım 8 Yol A sonucu) → `%remember`.
