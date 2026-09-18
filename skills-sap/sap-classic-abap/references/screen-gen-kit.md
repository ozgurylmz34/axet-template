# Ekran üreteci kiti (`ZBC000_FM_SCREEN_GEN`) ve dört ALV şablonu

> `ZBC000` nötr ortak paket gövdesidir; kendi ortak paketinin gövdesiyle değiştir (`%sap-dev` → `references/naming.md` §3).
> Kaynak: kaynak ekibin canlı ortak paketindeki ekran üreteci FM'i, fonksiyon grubu, iki yapı, iki tablo tipi ve dört şablon
> programı (salt okunur indirildi) · üreteç kullanım kılavuzu (imza, TEMP ailesi donör reçetesi, çalışan emsal, tuzaklar) ·
> FUGR bölümündeki iç mekanik · ortak paket kurulum script'inin sırası.
> Yöntemin standart API tarafı (neden diyalog bağlamı, status reçetesi, container değerleri, doğrulama sayaçları) →
> `dynpro-gui-status.md`; burada tekrarlanmaz. Kurulum → `templates/screen-gen/DEPLOY.md`.
> ⚠ **DOĞRULANMADI:** kit dosyaları bu biçimleriyle SAP'de derlenmedi / canlı çalıştırılmadı.

## 1. Kit nedir
Klasik bir Z programına tek RFC çağrısıyla **Dynpro ekranı + GUI status `STAT<n>` + başlık `TIT<n>`** ve isteğe bağlı
**uygulama toolbar butonları** ile **ekran alanları** üreten, yalnız standart API çağıran bir Z RFC FM ve bağımlılıkları.
Çağrılan standart API'ler: `RPY_DYNPRO_INSERT` / `RPY_DYNPRO_READ`, `RS_SCRP_DELETE`, `RS_CUA_INTERNAL_FETCH` / `_WRITE`,
`RS_CUA_GENERATE`; tek DB erişimi `TADIR` okumasıdır (yazma yok). Standart donör programı yalnız **okunur**; yazılan tek obje hedef Z programdır.

| Obje | Dosya (`templates/`) | Tip | Kim yaratır |
|---|---|---|---|
| `ZBC000_S_SCREEN_BUTTON` | `screen-gen/ZBC000_S_SCREEN_BUTTON.structure.ddl` | yapı (5 alan) | CLI |
| `ZBC000_S_SCREEN_FIELD` | `screen-gen/ZBC000_S_SCREEN_FIELD.structure.ddl` | yapı (19 alan, adlar = `RPY_DYFATC`) | CLI |
| `ZBC000_TT_SCREEN_BUTTON` / `_FIELD` | `screen-gen/table-types.md` | tablo tipi | CLI (`adt_post_shell ttyp`); satır tipi düzeltmesi kullanıcı (SE11) |
| `ZBC000_FG_SCREEN_GEN` | `screen-gen/ZBC000_FG_SCREEN_GEN.fugr-main.abap`, `LZBC000_FG_SCREEN_GENTOP.abap` | fonksiyon grubu (SAP üretir; dosyalar karşılaştırma) | CLI (`adt_post_shell fugr`) |
| `ZBC000_FM_SCREEN_GEN` | `screen-gen/ZBC000_FM_SCREEN_GEN.func.abap` | RFC FM | CLI (`adt_post_shell func` + `adt_push_source func`) + **kullanıcı** SE37 RFC işareti |

CLI yolları 2026-09-13'te eklendi: çevrimdışı test edildi, canlı DOĞRULANMADI; ayrıntı ve ara yollar `DEPLOY.md`.
| `ZBC000_P_ALV_TEMP1..4` | `alv-temp1-docking` · `alv-temp2-custom-container` · `alv-temp3-split-master-detail` · `alv-temp4-screen-gen-demo` (`.prog.abap`) | program | CLI |

**İki şablon türü — karıştırma:**
- `templates/classic-alv-list.prog.abap` = **gerçek program iskeleti**: kopyalanır, include'lara bölünür (`programs-includes.md` §1).
- `templates/alv-temp1..4` = **üreteçle ekranı üretilmiş, çalışır tek gövde demo**: deseni ve üreteç çağrısını çalışırken
  gösterir; gerçek programa tek gövde olarak kopyalanmaz.

## 2. FM imzası — 16 parametre
Doğruluk kaynağı FM'in kendi kaynağıdır (`ZBC000_FM_SCREEN_GEN.func.abap:1-20`); sistemdeki bir üretecin imzası farklıysa **onun kaynağı kazanır**
ve `adt_screen_generate` (bu 16 parametreyi gönderir) o üreteçle kullanılmaz.

| Parametre | Tip | Varsayılan | Anlam |
|---|---|---|---|
| `IV_PROGRAM` | `SCRHPROG` | — | hedef program; **Z\*/Y\* şart** (değilse hiçbir şey yazmadan `EV_RC=301`) |
| `IV_DYNPRO` | `SCRFDYNNR` | `'0100'` | ekran no, **tam 4 hane rakam** (değilse `EV_RC=300`); ekran, modül, status, başlık, set kodları buna göre adlanır |
| `IV_TRANSPORT` | `TRKORR` | opsiyonel | kullanıcının transportu (yeni transport açılmaz) |
| `IV_TITLE` | `RSMPE_TITT-TEXT` | `'Liste'` | başlık çubuğu + ekran açıklaması; metin kullanıcıdan |
| `IV_SCREEN_TYPE` | `CHAR10` | `'DOCKING'` | `DOCKING` (ekranda container yok) · `CONTAINER` (tek custom control, 200×255, resize açık). Split = `CONTAINER` + programda splitter |
| `IV_CC_NAME` | `SCRCNAME` | `'CC_ALV'` | custom control adı (`CONTAINER`'da); programdaki `container_name` ile aynı |
| `IV_MODE` | `CHAR10` | `'WRITE'` | `WRITE` üret · `READ` yazmadan döküm · `DELETE` ekranı siler (geri alınamaz) |
| `IV_RECREATE` | `CHAR1` | `' '` | `'X'` → önce sil, sonra yarat (INSERT var olan ekranın üzerine yazmaz); INSERT düşerse ekran kaybolur |
| `IV_SRC_PROG` | `SCRHPROG` | opsiyonel → `SAPLKKBL` | CUA donör programı (yalnız okunur) |
| `IV_SRC_STATUS` | `RSMPE_STA-CODE` | `'STANDARD'` | donör status; program+status tutmazsa `EV_RC=120..130`, CUA'ya hiçbir şey yazılmaz |
| `IV_CUA_MERGE` | `CHAR1` | `'X'` | `'X'` diğer status/başlıklar **korunur** · `' '`/`'-'` **siler** · tanınmayan değer açık bırakır + `DIKKAT` |
| `IV_NAV_REMAP` | `CHAR1` | `' '` | `' '` otomatik (yalnız `SAPLKKBL`/`STANDARD` donöründe açılır) · `'X'` zorla aç · `'-'` zorla kapa |
| `EV_RC` | `I` | — | sonuç kodu (§3) |
| `EV_MESSAGE` | `STRING` | — | tanı metni; **kırpma** (uyarılar sondadır) |
| `IT_BUTTONS` | `ZBC000_TT_SCREEN_BUTTON` (TABLES) | opsiyonel | `FCODE`, `TEXT`, `ICON`, `QUICKINFO`, `FKEY` |
| `IT_FIELDS` | `ZBC000_TT_SCREEN_FIELD` (TABLES) | opsiyonel | `RPY_DYFATC` alan adlarıyla ekran alanları; **`DOCKING` şart** |

## 3. Sonucu okuma — `EV_RC` ve `EV_MESSAGE` sinyalleri
| `EV_RC` | Anlam |
|---|---|
| `0` | ekran + status + generate başarılı (yine de §3 sinyallerine bak) |
| `1..18` | bileşik: ekran `RPY_DYNPRO_INSERT` rc (0-10; `2` = ekran zaten var) + status WRITE rc (0-3) + generate rc (0-5) |
| `5` | `IT_FIELDS` ön doğrulaması: konum boş / `TEMPLATE`'te `LENGTH` ve `FROM_DICT` yok / olmayan container — **hiçbir şey yazılmadı**, kusurlu alan adları mesajda |
| `101..113` | donör CUA okunamadı (`100+rc` + ekran rc) |
| `120..130` | donör status satırı yok — CUA'ya hiçbir şey yazılmadı |
| `202..213` | hedef programın mevcut CUA'sı okunamadı — yazılmadı (yazılsaydı tüm CUA silinirdi) |
| `300` | `IV_DYNPRO` 4 hane rakam değil |
| `301` | `IV_PROGRAM` Z/Y değil |
Bantlar **aralıktır**: sonuç her zaman ekran rc'si ile toplanır. `2` gibi küçük bir değer "ekran vardı, status yazıldı" olabilir.

**Her koşumda `EV_MESSAGE`'da bak:**
| Sinyal | Doğru | Yanlışsa |
|---|---|---|
| `donor=<prog>/<status>` | `SAPLKKBL/STANDARD` (TEMP ailesi) | yanlış donör gitmiş |
| `nav_remap=ON(F3/Sh+F3/F12->BACK/EXIT/CANCEL)` | PAI'si `BACK`/`EXIT`/`CANCEL` bekleyen programda şart | `nav_remap=OFF…` → çağrı yanlış; **ekranı kullanmadan** düzelt |
| `cua_merge=ok kept_status=N kept_title=M` / `cua_merge=none(…ilk uretim…)` | normal | `cua_merge=KAPALI(…)` → diğer status'ler **silindi**; `KOSMADI` → status adımına girilmedi |
| `fields=N io_default=M` | alan verildiyse; `M` = giriş+çıkışa açılan alan sayısı | salt okunur isteniyorsa `OUTPUT_FLD='X'` |
| `DIKKAT: …` | yok | tanınmayan anahtar değeri · donör set kodu yok · `CONTAINER` + alan · `devclass=COZULEMEDI` |

## 4. Dört şablon — neyi gösterir, hangi çağrıyla üretilir
Ortak değerler (her satırda): `IV_PROGRAM=<program>`, `IV_MODE='WRITE'`, `IV_SRC_PROG='SAPLKKBL'`, `IV_SRC_STATUS='STANDARD'`
(kitte varsayılan da budur; **açıkça vermek** sistemdeki farklı sürümlü bir üreteçte de doğru donörü garanti eder),
`IV_NAV_REMAP=' '`, `IV_CUA_MERGE` verilmez (`'X'`), `IV_RECREATE=' '`, `IV_TRANSPORT=<kullanıcı>`, `IV_TITLE=<kullanıcı>`.

| Program | Gösterdiği | `IV_DYNPRO` | `IV_SCREEN_TYPE` | `IV_CC_NAME` | `IT_BUTTONS` | `IT_FIELDS` | Beklenen sinyal |
|---|---|---|---|---|---|---|---|
| `ZBC000_P_ALV_TEMP1` | docking tam ekran ALV, hotspot/çift tık | `0100` | `DOCKING` | — | boş | boş | `nav_remap=ON` · `cua_merge=none` (ilk) |
| `ZBC000_P_ALV_TEMP2` | custom control içinde ALV | `0100` | `CONTAINER` | `CC_ALV` | boş | boş | `nav_remap=ON` |
| `ZBC000_P_ALV_TEMP3` | tek container + splitter master-detail (VBAK → VBAP) | `0200` | `CONTAINER` | `CC_ALV` | boş | boş | `nav_remap=ON` |
| `ZBC000_P_ALV_TEMP4` | ① docking ekranı | `0100` | `DOCKING` | — | boş | boş | `cua_merge=none` (ilk yazım) |
| | ② container + uygulama toolbar butonu | `0200` | `CONTAINER` | `CC_ALV` | 1 satır: `FCODE='REFRESH'`, `TEXT`/`QUICKINFO` kullanıcıdan, `ICON` ör. `ICON_REFRESH` (ICON tablosunda doğrula), `FKEY` boş | boş | `cua_merge=ok kept_status=1` |
| | ③ DDIC alan ekranı (ALV yok) | `0300` | `DOCKING` | — | boş | örnek aşağıda | `cua_merge=ok kept_status=2` · `fields=4` |

TEMP4 sırası önemlidir: merge açık olduğu için her yazım öncekileri korur; `kept_status` sayısı bunun kanıtıdır. Status'ün
toolbar'ı her yazımda baştan kurulur → 0200'ü yeniden üretirken butonların **tamamı** yeniden verilir (`dynpro-gui-status.md` §5.1).

**TEMP4 / 0300 `IT_FIELDS` örneği** (kaynak şablon 0300'ün payload'ını taşımıyordu; bu satırlar kaynak ekibin ölçtüğü etiket
kuralına göre kurulmuş **örnektir, DOĞRULANMADI**; konumlar serbest):
| `NAME` | `TYPE` | `FROM_DICT` | `TEXT` | `LINE` | `COLUMN` | Not |
|---|---|---|---|---|---|---|
| `VBAK-VBELN` | `TEXT` | `X` | boş | 2 | 2 | etiket DDIC'ten |
| `VBAK-VBELN` | `TEMPLATE` | `X` | — | 2 | 25 | giriş alanı; uzunluk/F4 DDIC'ten |
| `VBAK-ERDAT` | `TEXT` | `X` | boş | 3 | 2 | |
| `VBAK-ERDAT` | `TEMPLATE` | `X` | — | 3 | 25 | |
Programda bu alanlar `DATA vbak TYPE vbak.` global work area'sına bağlanır (TEMP4 kaynağında var). Etiket ile giriş alanının
aynı `NAME`'i taşıması bu kitte ölçülmedi; `EV_RC` 6/7 gelirse kullanıcıyla ele al.
`MATCHCODE` boş bırakılır; `CONT_NAME`/`CONT_TYPE` boş → FM kök container'a bağlar.

## 5. Hangi şablondan başla
| İhtiyaç | Başlangıç | Üreteç çağrısı |
|---|---|---|
| Gerçek rapor programı | `classic-alv-list.prog.abap` + `scripts/scaffold_classic_program.py` (include'lara böl) | TEMP1 satırı |
| Tam ekran tek liste, önce çalışır örnek görmek | TEMP1 | `DOCKING` |
| Liste belirli yer/boyutta, başlık alanları + liste | TEMP2 | `CONTAINER` + `IV_CC_NAME` |
| Master-detail (üst/alt) | TEMP3 | `CONTAINER`; bölme programda |
| Uygulama toolbar butonu, aynı programda birden çok ekran, DDIC alan ekranı | TEMP4 | `IT_BUTTONS` / merge / `IT_FIELDS` + `DOCKING` |
| Tek kayıtlık modal form (kaydet/iptal) | `classic-dynpro-dialog.prog.abap` + `dynpro-dialog-fields.md` | `DOCKING` + `IT_FIELDS` + ekrana özel fcode |

## 6. Yeni programda kullanım
1. Sistemde üreteç var mı → `DEPLOY.md` Adım 0. Varsa kaynağını `adt_get func` ile oku; imzayı bu dosyadan varsayma.
2. Karar tablosundan başlangıcı seç; programı yaz (gerçek programda include'lar), `CALL SCREEN <n>` / `SET PF-STATUS 'STAT<n>'`
   / `SET TITLEBAR 'TIT<n>'` / `MODULE status_<n>` / `user_command_<n>` numaraları aynı olmalı.
3. PAI: `sy-ucomm`'u oku, `CLEAR`; `BACK`/`CANCEL` → `LEAVE TO SCREEN 0`, `EXIT` → `LEAVE PROGRAM`; her `IT_BUTTONS` fcode'u için
   bir `WHEN` dalı; `exit_command_<n>` yazma (`alv-report.md` §5). Donör fcode'u gelirse görünür mesaj (TEMP4 `handle_ucomm`).
4. Programı CLI ile yarat/push/aktive et (`DEPLOY.md` Adım 7 sırası).
5. Çağrı parametrelerini hazırla (§4 tablosu) → **`adt_screen_generate`** ile çağır (yazma sınıfı, READ dahil: `--sap-write` +
   kapsam + onay; yalnız `ecc`/`s4_private`; çevrimdışı test edildi, canlı DOĞRULANMADI). Şablon başına hazır argümanlar:
   `DEPLOY.md` Adım 8 Yol 0. Araç kullanılamıyorsa (profil, farklı imzalı üreteç, canlı hata) çağrıyı kullanıcı yapar (Yol A/B).
   Aynı programda ikinci ekran: merge açık kalsın; önce `mode:"READ"` ile tur öncesi sayaçları al.

   **Parametre ↔ araç argümanı** (`tool-catalog.md` → `adt_screen_generate`; araç kaynağında `IV_*` eşlemesi):
   | FM parametresi | Argüman | Not |
   |---|---|---|
   | (FM adı) | `fm_name` | Z/Y zorunlu; araç FM'i yaratmaz |
   | `IV_PROGRAM` · `IV_DYNPRO` · `IV_TITLE` · `IV_TRANSPORT` | `program` · `dynpro` · `title` · `transport` | `title` WRITE'ta, `transport` WRITE/DELETE'te zorunlu |
   | `IV_SCREEN_TYPE` · `IV_CC_NAME` · `IV_MODE` | `screen_type` · `cc_name` · `mode` | `fields` + `CONTAINER` kapıda reddedilir |
   | `IV_SRC_PROG` · `IV_SRC_STATUS` | `src_prog` · `src_status` | §4 değerleriyle **açıkça** ver |
   | `IV_CUA_MERGE` · `IV_NAV_REMAP` · `IV_RECREATE` | `cua_merge` · `nav_remap` · `recreate` | verilmezse gönderilmez → FM varsayılanı; `cua_merge` `" "`/`"-"` ve `recreate:"X"` `warnings`'e yazılır |
   | `IT_BUTTONS` · `IT_FIELDS` | `buttons` · `fields` | satırda verilmeyen alan boş gider, tanınmayan alan reddedilir; tablolar boşken de boş etiketle gider |
   | `EV_RC` · `EV_MESSAGE` | `ev_rc` (+ `ev_rc_band`) · `ev_message` (kırpılmaz), `signals` | `ok` = `EV_RC == 0` ve (WRITE'ta) `nav_remap≠OFF` |

   Hata kodları: `screen_gen_rc` (`EV_RC≠0`; rc=2 "ekran zaten var" dahil — karar kullanıcıyla) · `nav_remap_off` (çağrı yanlış,
   ekranı kullanmadan düzelt) · `soap_fault` · `ev_rc_missing`.
6. `EV_RC` + §3 sinyalleri + `adt_inactive_objects`; GUI testini kullanıcı yapar (`DEPLOY.md` Adım 9).

## 7. Tuzaklar
Üretecin standart API tuzakları `dynpro-gui-status.md`'dedir: `act` korunmazsa `00256` (§3) · `RS_CUA_GENERATE` yoksa `00264` (§3) ·
`biv` WRITE'ta zorunlu (§3) · merge kapalı yazım siler (§3) · container değerleri ve `element_of` (§4) · toolbar her yazımda baştan
kurulur (§5.1) · donörle çakışan fcode etiketi geri döner (§5.2) · ESC ve `exit_command` (§5.3) · sayaçlar etiket kaybını görmez (§6) ·
SOAP-RFC'de boş `TABLES` etiketi (§1, §8). Diyalog ekranı tarafı: etiket ayrı `TEXT` satırıdır (`dynpro-dialog-fields.md` §1.1),
alan ekranı docking ister (§1.2), üreteç POV üretmez (§2.4), çok turlu `BUT` deltası (§4).

Kite özgü, yukarıda olmayanlar:
| Belirti / risk | Sebep → çare |
|---|---|
| `EV_RC=300` | `IV_DYNPRO='300'` gibi sola dayalı değer → butcode `B00 ` olur ve başka ekranın toolbar'ıyla çakışırdı; FM reddeder → `'0300'` ver |
| `0300` ile `1300` aynı toolbar | butcode `B` + son 3 hane (alan 4 karakter) → aynı programda bu iki numarayı birlikte kullanma |
| `IV_SRC_PROG=<hedefin kendisi>` → `EV_RC=120` | üretilen status adı `STAT<n>`, donör status adı tutmaz → hiçbir şey yazılmaz; kaynak dururken kopyadan kopyalama |
| Başka bir ekranın buton ikonu kayboldu | fonksiyon tanımı program geneli; bir fcode'u ikinci status'e `ICON` boş verilerek eklemek diğer ekranın ikonunu siler → önce `IV_MODE='READ'` `[FN:` dökümünden ikonu oku, aynısını ver |
| Etiketsiz alan, uyarı yok | `TYPE='TEXT'` satırı unutuldu (FM sessiz kalır) → etiket/alan çiftlerini say |
| `IV_MODE='READ'` bile `301` | Z/Y koruması tüm modlardan önce; ad alanlı `/ABC/…` programlar da takılır |
| Koruma testi | var olmayan bir adla dene (`XX_GUARD_PROBE`), gerçek standart programla değil |
| Opsiyonel parametre boş etiketle gönderildi | RFC'de "gönderilmiş boş değer" varsayılanı uygulamayabilir → `IV_SRC_STATUS` boş gider, `EV_RC=120`. **DOĞRULANMADI**; varsayılana güvenme, değeri açıkça ver |
| ATC / clean-core: `TADIR` okuması | bilinçli: önerilen `I_CustABAPObjDirectoryEntry` müşteri paketlerini JOIN'le eliyordu (kaynak ekipte ölçüldü) → kullanıcıya göster, gerekçeyle geç |
| Kaynak ekip belgelerinde "varsayılan donör `&F2..&F5` üretir" | o **kaynak** FM'in varsayılanıydı; kitte varsayılan `SAPLKKBL`/`STANDARD` (§8). Sistemdeki bir üreteçte hangisinin geçerli olduğunu `c_def_src_prog` sabitinden oku |

## 8. Kaynaktan fark — FM
Kod değişikliği (yorum hariç; `ZBC000_FM_SCREEN_GEN.func.abap`):
| Satır | Önce (kaynak) | Sonra (kit) | Neden |
|---|---|---|---|
| 1 | `FUNCTION <kaynak gövde>_fm_screen_gen` | `FUNCTION zbc000_fm_screen_gen` | obje adı |
| 12 | `… iv_src_status … DEFAULT 'STATUS_0100'` | `… DEFAULT 'STANDARD'` | varsayılan donör status |
| 19-20 | `TYPE <kaynak gövde>_tt_screen_button/_field` | `TYPE zbc000_tt_screen_button/_field` | obje adları |
| 125 | `c_def_src_prog … VALUE '<müşteri raporu>'` | `… VALUE 'SAPLKKBL'` | varsayılan donör her sistemde bulunmalı |
| 259 | mesaj metni: `… ADR 0005 Kategori A ihlalidir …` | `… kesin yasak A ihlalidir …` | kaynak ekibin karar numarası aXet'te anlamsız; yalnız metin |
Başka mantık değişikliği yok (yorum/boş satır dışı kod satırları, ad normalizasyonu sonrası kaynakla satır satır kıyaslandı).

**Donör tutarlılık analizi (kod okuması):**
- `:314-315` `IV_SRC_PROG` boşsa `c_def_src_prog` atanır → artık `SAPLKKBL`.
- `:317` `l_legacy_donor = (iv_src_prog = c_legacy_prog 'SAPLKKBL' AND iv_src_status = c_legacy_status 'STANDARD')`
  (`:120-121`) → parametresiz çağrıda **`true`** (kaynakta `false`'tu).
- `:328-331` `IV_NAV_REMAP=' '` → `ELSE l_legacy_donor` → remap **açık**; `:854` pfk `03/15/12 → BACK/EXIT/CANCEL`,
  `:885` fonksiyonlar yoksa eklenir ve tipleri normal'e zorlanır; `:1266` mesaj `nav_remap=ON(…)`.
  ⇒ Parametresiz çağrı artık kaynak kılavuzunun **kanıtlı TEMP reçetesiyle** (legacy donör + otomatik remap) birebir aynı yoldan geçer; PAI'si
  `BACK`/`EXIT`/`CANCEL` bekleyen dört şablonla tutarlı. Ek değişiklik gerekmedi.
- Yan etkiler (davranış farkı, bilinçli): (a) `IV_SRC_PROG='SAPLKKBL'` verip status'ü vermeyen çağrı kaynakta `STATUS_0100` arayıp
  `EV_RC=120` alırdı, kitte doğru status'ü bulur. (b) Kendi donörünü verip status'ü **vermeyen** çağrı artık `STANDARD` arar →
  o donörde yoksa `EV_RC=120..130` + "CUA'ya hiçbir şey yazılmadı" (`:725-759`, gürültülü, yıkıcı değil) → donörü veren status'ü de verir.
  (c) `&F2..&F5` bekleyen bir program için donörü ve status'ü açıkça vermek gerekir; `l_legacy_donor=false` olduğundan remap otomatik kapalı kalır.
- `c_def_src_prog` ile `c_legacy_prog` artık aynı değeri taşır; ikisi farklı anlam (seçim / tespit) için korundu.
- Kaynak ekipte **ölçülmemiş** alternatif (minimal donör + `IV_NAV_REMAP='X'`) kitte varsayılan olmadığı için kapsam dışı kaldı.

Yorum temizliği: kişi adları, müşteri program/paket adları, ölçüm tarihleri, kaynak ekibin karar/klasör/doğrulayıcı atıfları
çıkarıldı ya da genel ifadeye çevrildi; derslerin kendisi (neden-sonuç, standart kaynak satır kanıtları) korundu.

## 9. DOĞRULANMADI
- Kit kaynaklarının hiçbiri SAP'de derlenmedi / çalıştırılmadı (yapı DDL'leri, FM, dört program).
- DDIC yapı DDL'inde `//` yorum satırlarının kabulü (DEPLOY'da push öncesi silinmesi istenir).
- `adt_struct_create` + `adt_push_source structure` + `adt_activate structure` sırasının bu yapılarda sonucu.
- `adt_screen_generate`'in canlı davranışı: gerçek FM yanıt biçimi, `sap-language` etkisi, `nav_remap` token biçimi (araç yalnız çevrimdışı test edildi).
- SE37 test ekranından çağrıda diyalog bağlamı ve transport sorgusu (`DEPLOY.md` Adım 8 Yol A).
- TEMP4/0300 `IT_FIELDS` örnek satırları; etiket ve giriş alanının aynı `NAME`'i taşıması.
- TEMP4'teki `free_controls` ve `DATA vbak TYPE vbak.`; TEMP3'teki `ELSE` refresh dalı (kaynakta olmayan, nav düzeltmesinin gerektirdiği kod).
- RFC'de boş etiketle gönderilen opsiyonel parametrenin varsayılanı ezmesi.
