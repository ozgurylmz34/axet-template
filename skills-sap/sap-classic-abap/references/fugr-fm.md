# Fonksiyon grubu (FUGR) ve fonksiyon modülü (FM)

> Kaynak: ekip ADT playbook'unun FUGR/FM bölümü. FM kilit/PUT protokolünün kısa hâli ve FM hata kodları
> `%sap-adt-foundation` → `references/foundation-ops.md` §4.4 ve `known-errors-adt.md` K-15'te; burada yalnız
> ek ayrıntı ve aXet araç durumu var. Ad deseni: `%sap-dev` → `references/naming.md` §4.4 (yalnız `_CLC` paketi).
> **Okuma kuralı:** "ÇALIŞAN YÖNTEM" / "DENENEN — BAŞARISIZ" ölçülmüş deneyimdir.

## 0. aXet CLI'de ne var, ne yok

Kaynak: `--list` + `%sap-adt-foundation` → `tool-catalog.md` (2026-09-13). Yeni yazma yolları (FUGR/FM kabuğu, FM kaynağı)
**çevrimdışı sahte istemciyle test edildi, canlı DOĞRULANMADI**. `fugr`/`func` tipleri yalnız `ecc`/`s4_private`'ta açıktır
(başka profilde `type_not_available_for_profile`, çıkış 2).

| İş | CLI | Durum |
|---|---|---|
| FUGR kabuğu | `adt_post_shell` `object_type:"fugr"` | var → sonra `adt_activate` `fugr` |
| FM kabuğu | `adt_post_shell` `object_type:"func"` + `extra:{"function_group":"<Z/Y FUGR>"}` | var — grup kapıda Z/Y denetlenir (standart gruba FM = `ADR_0005_A`) |
| FM kaynağı (imza + gövde) | `adt_push_source` `object_type:"func"` | var — grup canlı okumadan çözülür (Z/Y şart), sıkı kilit PUT + **ayrı aktivasyon araç içinde**; aktivasyon düşerse `push_failed` + `activation_errors` (kaynak yüklenmiştir). Gömülü inceleme yok (`SKIP`) → `%code-review` şart. Yasak B taranır |
| FM okuma / varlık / where-used | `adt_get` / `adt_where_used` `object_type:"func"` | var — grup arama indeksinden çözülür (`resolved_uri`, `function_group`); yeni FM indekste henüz yoksa `exists:false` dönebilir (DOĞRULANMADI) |
| FUGR aktivasyonu | `adt_activate` `object_type:"fugr"` | var; canlı sonucu **DOĞRULANMADI** |
| FM aktivasyonu | `adt_activate` `func` | **yok** (generic URL yok) → `adt_push_source func` içinde yapılır |
| FM silme | `adt_delete` `func` | çalışmaz ("lock not supported") |
| RFC-enable (Remote-Enabled) | — | **yok** → kullanıcı SE37 (§3) |

- `extra` yalnız `func`'ta (`function_group`); `fugr`'da ya da tanınmayan alanla → `invalid_argument` (çıkış 3).
- **İnceleme kapsamı:** `adt_push_source fugr` yalnız FG ana include'unu (`/functions/groups/<fg>/source/main` =
  `FUNCTION-POOL` satırı) yazar; FM gövdesini kapsamaz. `func` push'unda gömülü inceleme yoktur (`SKIP`) → FM yazmadan
  önce elle `run_review --task class_push --artifact <fm>.abap` koş (`%sap-code-review` → `validator-map.md` §1).
  Kaynak ekipte 10 FM/FUGR artefaktında bu zincir BLOCKER 0, 10/10 WARNING verdi; abaplint'in `measured=false` WARNING'i
  FM'yi lintlemediği için beklenen gürültüydü, anlamlı tek sinyal `check_released_objects`'ti (bu zincirde DOĞRULANMADI).
- Bir tipin hangi araçta desteklendiğini `--list` ve `tool-catalog.md`'den kontrol et (`bdef`, `msag`, `enqu`, `srvb` genel tip
  tablosunda yok ama bazı araçlarda özel yolu var).

⇒ **Akış:** kaynağı (satır içi imza + gövde, §2) yerelde hazırla, `%code-review` → grup yoksa `adt_post_shell fugr` →
`adt_activate fugr` → `adt_post_shell func` → `adt_get func` (pull kaydı) → `adt_push_source func` → `adt_get func` ile geri
okuyup yereldekiyle kıyasla + `adt_inactive_objects` → RFC gerekiyorsa kullanıcı SE37'de işaretler (§3). `adt_get func`
`exists:false` dönerse push `pull_before_edit_missing` ile reddeder → retry döngüsüne girme, `adt_search_objects` ile ölç,
kullanıcıya bildir. Araç reddederse ya da canlıda düşerse ham REST ile yazma; kullanıcı SE80/SE37 ya da ADT'den yapar.

## 1. FUGR yaratma — protokol notları
- Uç `POST /sap/bc/adt/functions/groups`, Content-Type/Accept `application/vnd.sap.adt.functions.groups.v2+xml`,
  transport `corrNr` query parametresi (zorunlu), gövdede `adtcore:masterLanguage` = proje dili.
- Tek atış POST bayat CSRF ile `403` yiyor → CSRF yenileyip bir kez yeniden deneyen yol gerekir.
- Grup zaten varsa ölçülen sistem `405 AlreadyExists` yerine **`400`** döndürdü → mevcut kabul (hata değil); yine de
  `adt_search_objects` ile objenin beklenen pakette olduğunu doğrula.
- **Genel araca program adı verme:** yeniden kullanılacak bir FM'in grubu da aracın amacıyla adlandırılır
  (`<GÖVDE>_FG_<AMAÇ>`), ilk kullanan programın adıyla değil. Vaka: genel bir üreteç FM'i ilk hedef programın adını
  taşıyan gruba kondu; FM adı sistemde tekil olduğu için düzeltme = yeni grup + eski FM sil + yeniden yarat/push/aktive
  + eski grubu sil (RFC işareti de sıfırlandı). Yaratmadan önce sor: "bu yalnız bu program için mi, araç mı?"

## 2. FM — kabuk + imza + gövde
- **Kabuk:** `POST …/functions/groups/<fg>/fmodules` — gövdede **yalnız** `name` + `description` + `masterLanguage`.
  "Zaten var" → `400 ExceptionResourceAlreadyExists` (mevcut kabul).
- **İmza SE37 tarzı `*"` yorum bloğu DEĞİL, satır içi ABAP deyimidir** (`*"` → `400 Parameter comment blocks are not allowed`).
  İmza kaynaktan kurulur → imza için SE37 gerekmez.

```abap
FUNCTION zsd001_fm_demo
  IMPORTING
    VALUE(iv_in) TYPE string
  EXPORTING
    VALUE(ev_out) TYPE i.

  ev_out = strlen( iv_in ).
ENDFUNCTION.
```

### 2.1 ⛔ `TABLES` parametresi — iki kısıt birlikte
| Kısıt | Kural | İhlal |
|---|---|---|
| ADT upload | `STRUCTURE` yazma, `TYPE` yaz | `400 FUNC_ADT 015 Parameter <P> declares no type` (upload anında) |
| ABAP | `TYPE`'tan sonra **tablo tipi** (TTYP) gelir | `FL 387 Type <X> is not a table type` |

```abap
  TABLES it_x TYPE zsd001_t_item.     " YANLIS — transparan tablo: push geçer, aktivasyon düşer (RFC'de)
  TABLES it_x STRUCTURE zsd001_t_item. " YANLIS — upload reddedilir
  TABLES it_x TYPE zsd001_tt_item.    " DOGRU — satır tipi zsd001_t_item olan tablo tipi
```
- **Sinsi yanı:** `processingType=normal` iken SAP yapı tipli `TABLES`'ı **tolere eder** (aktivasyon temiz); FM
  **Remote-Enabled** yapılınca hard error olur → "FM aktifti, sonra bozuldu" sanılır. Ölçüm: aynı kaynağın normal
  aktif sürümü 0 mesaj, RFC inaktif sürümü `FL 387`.
- Kural **yalnız `TABLES`'a** özgü: aynı imzada `IMPORTING VALUE(is_x) TYPE <transparan tablo>` hata üretmedi.
- Standart tablo tipleri hazırdır (ör. `BAPIRET2_T`); mesaj tablosu için yeni tip yaratma. Yeni tablo tipi = yeni
  DDIC objesi → ad ve kısa metin **kullanıcıdan**.
- `TABLES … LIKE <yapı>`: normal FM'de ADT push'u ve aktivasyonu **geçti** (ölçüldü); **RFC işaretli hâli ÖLÇÜLMEDİ**.
  `LIKE` eskimiştir (ATC gürültüsü) → çalışır ama önerilmez; TTYP yolu kanıtlı ve tercih edilir.

### 2.2 Push mekaniği (protokol — araç bakımı/teşhis için)
1. Oturum stateful, CSRF zorla yenilenmiş.
2. **Kilit:** `POST …/fmodules/<fm>?_action=LOCK&accessMode=MODIFY` — transport **header** `X-sap-adt-corrNr`;
   yanıttan `LOCK_HANDLE` **ve** `CORRNR`. Kilit ucu `…/fmodules/<fm>` (`/source/main` değil); FM adı URL'de küçük harf.
3. **PUT** `…/fmodules/<fm>/source/main?lockHandle=<h>&corrNr=<kilit yanıtındaki CORRNR>`, `text/plain; charset=utf-8`.
4. **Unlock** (finally) → aktivasyon ayrı çağrı, **taze CSRF** ile (kilit oturumunun token'ı → `403`), tip `FUNC/FF`.

**`corrNr` otoritesi = kilit yanıtındaki `CORRNR`, verdiğin numara değil:**

| Verilen | PUT `corrNr` | Sonuç (ölçüldü) |
|---|---|---|
| Görev (S) numarası | verilen | `500 CTS_WBO_API 020` "… talebinde bloke edildi" — aynı bayt ikinci denemede de aynı 500 (içerikten bağımsız) |
| Görev (S) numarası | kilit `CORRNR` | 200 + aktivasyon |
| İstek (K) numarası | aynı | 200 |

⇒ Araca **istek (K)** verilir. Görevi isteğe çevirmek: `E070.STRKORR` (görev satırının üst isteği) — `adt_sql_query`.
Kilit yanıtında `IS_LINK_UP='X'` = obje başka geliştiricinin transportunda → dur, kullanıcıya sor. FM kilit yanıtında
`IS_LINK_UP`'ın gerçekten dönüp dönmediği **DOĞRULANMADI**.

## 3. RFC-enable (Remote-Enabled Module)
- ⛔ Yaratma XML'ine `fmodule:processingType="remoteEnabled"` → `400 ExceptionInvalidData "Unexpected Case in Branch"`.
- ✅ Bilinen çalışan yol: kullanıcı SE37'de "Remote-Enabled Module" seçer (tek seferlik). Sonra metadata `processingType="rfc"`.
- Yaratma sonrası metadata PUT (`…fmodules.v3+xml`) ile RFC-enable **DENENMEDİ**.
- RFC işaretlemeden önce `TABLES` tiplerini §2.1'e göre kontrol et (latent hata).

### 3.1 SOAP-RFC stateless'tır — `COMMIT` isteyen BAPI zinciri o kanaldan koşmaz
- `TFDIR-FMODE='R'` yalnız **çağrılabilirlik** söyler; iki çağrının aynı LUW'u paylaşıp paylaşmadığını söylemez.
- `/sap/bc/soap/rfc` ölçülen sistemde her HTTP çağrısında ayrı LUW → `BAPI_…_CREATE` + `BAPI_TRANSACTION_COMMIT`
  zinciri **çalışmaz**. Sinsi yanı: CREATE belge numarası döndürür, COMMIT HTTP 200 döner, **belge tablosunda satır yoktur**.
  Doğrulama = geri okuma (kesin yasak B: yazan hâlâ BAPI; okuma SELECT'i ile teyit).
- Elenen çareler (tekrar deneme): `sap-sessioncmd=open` (URL ve header), `sap-contextid=NEW`, `sap-sessiontype=stateful`,
  SOAP session header (`mustUnderstand="1"` → 500; olmadan sessizce yok sayılır).
- ✅ Çalışan yol: küçük bir Z koşucu sınıf + `adt_classrun` — CREATE → RETURN kontrolü → `COMMIT AND WAIT` tek ABAP
  oturumunda. `adt_classrun` yazma sınıfıdır → kapsam beyanı + onay.
- SOAP-RFC'nin hâlâ uygun olduğu yer: commit istemeyen, tek çağrılık RFC FM (ör. diyalog bağlamı isteyen ekran
  üreteçleri → `dynpro-gui-status.md`). **aXet CLI'de SOAP-RFC yalnız `adt_screen_generate` (ekran üreteci FM'i) içindir;
  genel bir RFC FM çağırma aracı yoktur.**

### 3.2 SOAP-RFC `TABLES` tuzağı
- İstekte yer almayan `TABLES` parametresi **cevapta hiç dönmez**: `<RETURN></RETURN>` göndermezsen uydurma bir değer bile
  "hatasız" görünür. Okumak istediğin her tablo parametresini **boş etiketle** gönder.
- Kanalı negatif kontrolle aç: bilerek geçersiz bir değer gönder, hata döndüğünü gör; gelmiyorsa kanal hata raporlamıyor olabilir.

## 4. Okuma ve arama
- `adt_get {"name":"<FM>","object_type":"func"}` → `exists`, `resolved_uri`, `function_group`, kaynak, metadata.
  Arama/okuma hatasında `ok:false` ("yok" değil).
- Elle arama yapılacaksa `objectType=FUNC` filtresi var olan FM için 0 dönebilir; `FUGR/FF` ya da filtresiz tam ad kullan.
  Çıplak FM ucunu okurken Accept `application/vnd.sap.adt.functions.fmodules.v3+xml` (başkası → 406).
- `adt_lock_check` / `adt_atc_check` için FM kanalı yok (ATC gerekiyorsa `adt_search_objects` ile gerçek URI'yi al;
  CLI'nin bunu kabul edip etmediği **DOĞRULANMADI**).

### 4.1 ⚠ FUGR'da kaynak araması FM gövdesini görmez
- `adt_grep_source` FUGR için yalnız iskelet ana include'u (`INCLUDE l<fg>top.` / `INCLUDE l<fg>uxx.`) okur; FM gövdesi
  `L<FG>U01`, `U02` … include'larındadır. CLI bunu `partial_objects: fugr_skeleton_only` + `coverage_complete:false`
  ile işaretler → FUGR hedefinde `match_count:0` bir **kapsam** sonucudur, varlık sonucu değil.
- `adt_where_used` FM'i listeliyor ama grep 0 diyorsa **where-used haklıdır** (bağımlılık indeksini okur).
- Çalışan yöntem: ana include'u oku (`adt_get` `object_type:"include"`, ad `L<FG>UXX`) → listelenen `U01…` include'larını
  tek tek oku ve ara. Grup adı uzunsa SAP include adını kısaltır → adı `UXX` içeriğinden **oku, türetme**.

## 5. DENENEN VE BAŞARISIZ (özet)
| Deneme | Hata | Doğru yol |
|---|---|---|
| FUGR/FM yaratmada tek atış POST | 403 | CSRF yenile + 1 retry |
| FM yaratma XML'inde `processingType="remoteEnabled"` | 400 "Unexpected Case in Branch" | SE37 tek tık (§3) |
| İmzayı `*"` yorum bloğuyla push | 400 "Parameter comment blocks are not allowed" | satır içi imza |
| FM'i genel kaynak-yazma yoluyla (4 transport biçimi + ETag GET retry) push | 423 InvalidLockHandle | sıkı kilit → PUT → unlock tek oturum (§2.2); aynı kök sınıf push'unda da ölçüldü (K-03) |
| Aktivasyonu kilit oturumunun CSRF token'ıyla yapmak | 403 | ayrı çağrı, taze CSRF |
| FM şablonu boş diye "pattern yok / yapılamaz" demek | saatlerce patinaj | çalışan yöntem genel ADT notlarında ve repodaki çalışan `.abap` kaynaklarındaydı → önce onları oku |
| Paket grep'i ile FM gövdesinde alan/tablo aramak | sessiz `match_count:0` | include indir (§4.1) |
