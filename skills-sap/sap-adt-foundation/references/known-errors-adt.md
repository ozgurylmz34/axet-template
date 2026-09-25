# Bilinen ADT hataları — kilit, transport, aktivasyon, CSRF, yaratma

> Kaynak: ekip playbook'unun "bilinen hatalar" dosyası (ADT maddeleri), foundation bölümündeki hata notları,
> araç semantiği notları ve tekrarlanan hata kataloğundaki ADT teşhis dersleri. UI5 maddeleri bu dosyada YOK.
> Kullanım: hata kodu ya da belirtiyle aşağıdaki indekste ara → maddeyi oku → **kör retry yapmadan** uygula.
> Madde bir ham REST akışı anlatıyorsa bu teşhis/araç bakımı bilgisidir; aXet'te yazma yalnız CLI iledir.

## İndeks

| Belirti / kod | Madde |
|---|---|
| `412 PreconditionFailed` / `Client ETag … does not match` | K-01, K-19 |
| `423 InvalidLockHandle` — başka objeler geçiyor, bu obje geçmiyor | K-02 |
| `423` class push, obje transportta kayıtlı | K-03 |
| Kilit yanıtında `NoModification`, boş `CORRNR` | K-04 |
| `409 Conflict` | K-05 |
| `400 Parameter corrNr not found` | K-06 |
| `EU 510` "Kullanıcı X zaten Y öğesini düzenliyor" | K-07 |
| `adt_lock_check` `locked:null` / kilit ucu 404 | K-08 |
| SM12'de kendi kullanıcında bayat kilit, `E_ABAP_GENPH` | K-09 |
| "activated" dedi ama kod eski / `version="active"` boş kabuk | K-10 |
| `REPORT/PROGRAM statement is missing, or the program type is INCLUDE` | K-11 |
| `Include not found` | K-12 |
| classrun `does not implement if_oo_adt_classrun~main` / bayat çıktı | K-13 |
| classrun `400 Session Timed Out` | K-14 |
| FM push `423` · `400 Parameter comment blocks are not allowed` | K-15 |
| `adt_post_shell` `ok:false` | K-16 |
| Yeni Z obje EN dilinde | K-17 |
| `/cts/*` ucunda `403` · CSRF'siz istek `200` + yanıltıcı gövde | K-18 |
| açıklama (envelope) değişikliği sonrası obje inaktif · `adt_set_description` `activation_required` / `put_precondition_failed` | K-19 |
| `ResourceScanDuringSaveFailure` (satır numarasız) | K-20 |
| `TEXT-xxx cannot be modified` | K-21 |
| `adt_transport_list count:0` | K-22 |
| `adt_get exists:false` ama obje var | K-23 |
| kimlik bilgisi değişti, hâlâ `401` | K-24 |
| inaktif listede silinmiş obje | K-25 |
| sözdizimi kontrolü hata dedi, aktivasyon geçti | K-26 |
| "araç bozuk" hissi · aynı hata tekrar tekrar | G-1 … G-6 |
| "obje ne zaman değişti" — `E070-AS4DATE` her objede aynı tarih · sürüm geçmişi ucu `406` | K-27 |

---

## K-01 · `412 PreconditionFailed` — yanlış ETag
- Program/include push'unda: **obje ETag'i değil `source/main` ETag'i** kullanılır.
- Sınıf push'unda doğru ayrım "obje yeni mi" değil, **"bekleyen inaktif sürüm var mı"**:

| Obje durumu | Bekleyen inaktif sürüm | ETag nereden |
|---|---|---|
| Hiç aktive edilmemiş kabuk (ilk push) | var | `version` parametresiz GET |
| Aktive edilmiş ama son push'u aktive **edilememiş** (retry ediyorsun) | var | `version` parametresiz GET |
| Aktive edilmiş, bekleyen sürüm yok | yok | `?version=active` |

- `?version=active` bayat ETag verir → PUT 412 (ölçüm: A/B yalnız son hanelerde ayrışıyordu). Aktivasyonu düşen bir
  push'tan sonra retry yapan herkes bu 412'ye çarpar. Şüphede `adt_inactive_objects` ile bak.
- Ayrım: `423` = yanlış/ölü kilit handle'ı · `412` = yanlış ETag. İki ayrı sebep.
- aXet: CLI push'u 412 dönerse bu tabloyla birlikte kullanıcıya bildir; kaynağı değiştirip körlemesine tekrar gönderme.

## K-02 · `423` — obje o transporta kayıtlı değil
- **Belirti:** kilit başarılı görünür, handle döner, PUT reddedilir; aynı oturumda başka objeler sorunsuz geçer
  ("araç bozuk" sanılır).
- **Kök sebep:** objeyi kayıtlı olmadığı bir transportla değiştirmek. Sık senaryo: elde bir görev (S) numarası var,
  obje üst istek (K) altında ya da başka bir görevde kayıtlı.
- **Tek kesin teşhis:**
  ```sql
  SELECT trkorr, pgmid, object, obj_name FROM e071 WHERE obj_name = '<OBJE>'
  ```
  Kullandığın transport listede yoksa sebep budur. (Ölçülmüş: aynı oturum, aynı araç, iki sınıf — kayıtlı olan geçti,
  yalnız üst istek + başka görevde kayıtlı olan 423 aldı.)
- **Çözüm (araç tarafı):** transport'u sabit yazma, kilit yanıtının döndürdüğü **etkin transport**'u kullan. Sabit
  `corrNr = TRANSPORT` yazan her akış bu hataya açıktır (iki kez ısırdı).
- ⛔ **Yanlış teşhis (iki kez düşüldü):** semptomu transport kaydı fonksiyonunun CSRF ön-alımına yıkmak. O ön-alım
  kasıtlıdır (K-18) ve fonksiyonun kendisi "her include için ayrı K+S transport açılıyordu" hatasının düzeltmesidir —
  kaldırmak o hatayı geri getirir.
- Kontrol grubu doğru eksende: "sınıf ↔ include" değil **"çalışan sınıf ↔ patlayan sınıf"**. Yanlış eksen kök sebebi 10 gün gizledi.
- Transport ataması kullanıcı işidir (SE10); model transport yaratmaz/değiştirmez (Yasak C).

## K-03 · `423` class push'ta — sebep transport değil, PUT'un ilk denemesi
- **Belirti:** kilit 200 + handle, PUT 4/4 yaklaşımda 423 ("Resource CLASS X is not locked (invalid lock handle)").
  `E071` objeyi kullanılan transportta **kayıtlı** gösterir. K-02 teşhisi burada saatler kaybettirdi.
- **Kök sebep (kod kanıtlı):** genel yazma yolu PUT'u sırayla 4 biçimde deniyordu; **1. biçim** (transport header'da,
  `corrNr` query parametresi yok) reddediliyor **ve kilit handle'ını yakıyordu**; sonraki biçimler ölü handle ile 423.
  Aynı istek biçimi (`corrNr` query) taze kilitle ilk seferde 200.
- **ÇALIŞAN YÖNTEM:** tek oturumda sıkı kilit → PUT → unlock → ayrı aktivasyon (`foundation-ops.md` §4.6).
- **DENENEN — BAŞARISIZ:** genel push yolu (423 ×4) · PUT'u yalnız header'daki transportla göndermek (423 + handle yanar) ·
  kilit kontrol aracıyla teşhis (uç 404, K-08).
- **İddianın sınırı:** 1. biçimin handle'ı yaktığı güçlü çıkarımdır, tek başına izole edilmedi (sıkı yol ETag'i de
  farklı seçiyordu). 423 vakası için ETag hipotezi zayıf ama çürütülmedi; 412'nin ayrı sebep olduğu ise ölçüldü.
- Boş `<CORRNR/>` sebep değil sonuçtur: başarılı push'tan sonraki temiz kilit aynı objede dolu döndü.
- Kilit hijyeni: kilit kontrol ucu yoksa pozitif kanıt = taze kilit dene → 200 ise yabancı kilit yok (olsaydı `EU 510`/409) → hemen bırak. (CLI'de bu işlem için araç yoksa kullanıcıya bırak.)

## K-04 · `NoModification` normal değerdir — kilit yanıtı alanlarına bakma
- Sınıf (CLAS) kilitlerinde `MODIFICATION_SUPPORT=NoModification` **5/5 sağlıklı sınıfta** döndü; DDLS'de boş (3/3).
  Değerin ayırt edici gücü yoktur. Bu değere göre kurulan bir koruma **tüm class push yolunu kapattı**, üstelik mesajı
  transport'u işaret ettiği için teşhis yanlış yere saptı.
- Değer dış dokümandan varsayılmış, canlıda ölçülmemişti ⇒ **Ölçülmemiş bir değere göre kapı kurma.** Kaydet, yaz, ama akışı ona bağlama.
- `IS_LINK_UP='X'` → obje, kullanıcının görevi olmayan yabancı bir isteğe kayıtlı; SAP'nin döndürdüğü `CORRNR` otoritedir.
- **Bir obje yazılamıyorsa merdiven (ucuzdan pahalıya):**
  1. Bu obje tipi **daha önce yazılabiliyor muydu?** Evetse regresyon ara (araç tarafında `git log -S '<sembol>'`,
     objenin `changedAt`'i) — SAP'yi kovalama. (Vakayı çözen soru buydu: regresyonu ayıran tip değil **tarih**ti.)
  2. Aynı anda başka tip yazılabiliyor mu? (CLAS ↔ DDLS) → tipe bağlı bir korumayı ele verir.
  3. `E071` sorgusu → K-02.
  4. `EU 510` → editör/enqueue kilidi (K-07).
- Sessiz ikinci yüz: kilit temizleme yardımcısı istisnayı yutup `False` döndüğü için aynı regresyonda hiç görünmeden başarısız oluyordu (yardımcı 2026-09-14'te kaldırıldı, K-09).

## K-05 · `409 Conflict`
- **ASLA retry.** Her retry SAP'de yeni boş K-tipi transport yaratabilir.
- Sıra: kullanıcıya bildir → kullanıcı SM12'den kendi bayat kilidini temizler → kullanıcı SE10'dan objeyi doğru
  transporta atar → tek retry. Model kilit silmez (Yasak C).

## K-06 · `400 Parameter corrNr not found`
- `corrNr` header'da değil **query parametresi** olarak gönderilir (FM kilit isteği istisna: `X-sap-adt-corrNr` header, `foundation-ops.md` §4.4).

## K-07 · `EU 510` — editör kilidi
- Ölçülen: **aktivasyon** çağrısından döndü (açık bırakılan SE24 düzenleme kilidi).
- Kilit (LOCK) çağrısında aynı kullanıcı `403`'ü yalnız mesaj sınıfı için kayıtlı (`sap-cds-ddic/references/message-class.md`
  §3.2: create sonrası yazma/silme `403 EU 510`, yeniden kilitle-bırak yine `403`; hangi çağrının `EU 510` gövdesi
  döndürdüğü ayrı yazılmamış). Diğer tiplerde kilit adımının gövdesi canlıda **doğrulanmadı** → araç kilit adımındaki
  çakışmayı "EU 510" diye adlandırmaz, "aynı kullanıcı kilidi (403)" der.
- Sık sebep: kullanıcıya teşhis için bir ekran (SE24 vb.) açtırıldı ve kapatılmadı. Ekran açmak kilit yaratır →
  talimatı "aç → yap → KAPAT → SM12'ye bak" diye ver.

## K-08 · `adt_lock_check` kilit göremiyor
- Ölçülen sistemde `GET /sap/bc/adt/locks` → `404`. Eski sürüm bu durumda sessizce `locked:false` diyordu ve "kilit yok"
  diye okundu. Bugünkü sözleşme: uç yanıt vermezse `locked:null` + `ok:false` = **ÇÖZÜLEMEDİ**, "hayır" değil.
- Eski bir kilit tespit stratejisi ("metadata oku, kilit hatası gelirse kilitlidir") ölü daldı: okuma kilit hatası üretmez.
- `locked:null` alınan bir obje, çok objeli yazma turunda "kilitsiz" varsayılarak listeye alınmaz; kullanıcıya "ölçülemedi" diye bildirilir (K-09).

## K-09 · Kilit sızıntısı (bayat enqueue) · aynı kullanıcı kilidi (kilitte `403`, aktivasyonda `EU 510`)
- Belirti: SM12'de kendi kullanıcının üstünde kilit; mesaj sınıfında `EU 510`, sınıf üretiminde `E_ABAP_GENPH`, silinmiş geçici objede yetim kilit.
- Sebep: kilit alan süreç yarıda öldü (401, zaman aşımı, kesinti, süreç öldürüldü) → `finally` çalışmadı. Bu kodla
  önlenemez: süreç öldürülünce hiçbir bırakma satırı koşmaz.
- **Araç politikası (2026-09-14):** araç ve model kilit TEMİZLEMEZ; yalnız KENDİ aldığı handle'ı bırakır (başarıda da
  hata dalında da); çakışmada durur. Eski kilit temizleme yardımcısı (lock→unlock döngüsü) ve iki otomatik çağıranı
  (push öncesi "kendi bayat kilidini temizle", aktivasyon 403'ünde temizle + yeniden dene) ile kilitleme adımının aynı
  kullanıcı 403'ünde handle'sız UNLOCK gönderip kilitsiz devam eden dalı **kaldırıldı**. Neden: Yasak C · aynı
  kullanıcı kilidi varken yeniden kilit `403` alır, döngü tamamlanmıyordu (mesaj sınıfında kayıtlı; diğer tiplerde
  canlıda doğrulanmadı — K-07) · bayat kilidi kurtaramıyordu (bırakmak için önce almak gerekir) · hatayı yutup `False`
  döndüğü için başarısızlık görünmüyordu.
- Araç çıktısı (koddan, 2026-09-14; alan yolları yanıttaki tam yerleridir):
  - `adt_push_source` düz yolu (`push_object`: class, prog, ddls …): `push_object` istisnayı yutar → `ok:false` ·
    `result.error_type:"SAPLockError"` · `result.error` (sahip adı + tarif metinde) · `result.source_uploaded:false`.
    Üst seviyede `error` ve `lock_owner` **yok**; tarif `client_log`'da (`[KİLİT]`). Bilinen-hata ipucu bu metinden
    K-09'a düşer.
  - `adt_push_source` alt-include / BDEF / FM yolları: üst seviyede `error:"push_failed"` + `message`, ayrıntı `result.*`.
  - `error:"locked"` + üst seviyede `lock_owner` yalnız istisna araç katmanına kaçtığında (`tools/atom.py` `_err_from_exc`);
    yaratma bileşiklerinde iç içe (`steps.create.error:"locked"`).
  - Aktivasyon 403'ü: aktivasyon hatası metninde sahip + aynı tarif. Mesaj sınıfı/açıklama araçları: `lock_conflict`.
  - UNLOCK düşerse: düz yolda `result.lock_released:false` (bırakma `finally`'de yazıldığı için `ok:true` ile yan yana
    olabilir) · BDEF yolunda `unlock_warning`.
- **Yapılacaklar:**
  1. Çok objeli bir yazma turundan **önce** her obje için `adt_lock_check`. `locked:null` = **ölçülemedi** (K-08),
     "kilitsiz" diye okunmaz; kullanıcıya böyle bildir.
  2. Aynı kullanıcı kilidi (kilitte `403`, aktivasyonda `EU 510`) / kilit çakışması: otomatik temizleme ve otomatik
     yeniden deneme **yok**. DUR → kullanıcıya:
     SAP GUI/Eclipse'te bu objede açık düzenleme varsa kapat → SM12'de kendi kilidini kontrol et (bayatsa **kullanıcı**
     siler) → tek sefer tekrar.
  3. Kullanıcıya teşhis için SAP GUI ekranı açtırırsan talimat "aç → yap → **KAPAT** → SM12'ye bak" (K-07).
- **Canlı mı bayat mı:** başka bir yazma işlemi şu an çalışıyorsa canlıdır, dokunma. Geçici obje `adt_get` ile
  `exists:false` ise yetim kilittir.
- Kurtarma: **kullanıcı** SM12'den kendi kilidini siler. Model enqueue kilidi silmez (Yasak C).

## K-10 · "Aktive edildi" ama değil
- `adtcore:version="active"` metadata'sı **boş kabuk için de "active" der** → tek başına aktivasyon kanıtı değildir.
- ADT'de parametresiz kaynak GET'i **inaktif** sürümü döndürür (aynı sınıf: parametresiz 10.659 bayt kod, `version=active` 192 bayt boş kabuk).
- Güvenilir kanıt: `adt_inactive_objects` (bu obje listede yok) + aktif kaynağın içerik/bayt kıyası.
- Aktivasyon hükmü tek kaynaktandır: `sap_adt_lib.aktivasyon_govde_hukmu` (True/False/None). `None` (yalnız generation ya da
  bayraksız gövde) → bağımsız worklist sondası; sonda ölçemezse `success:false` + `dogrulanamadi:true` (başarı değil).
  `version="active"` metadata kontrolü bunun üstüne ek şarttır, tek başına kanıt değildir.
- `adt_syntax_check` salt-okuma değildir: bekleyen **temiz** sürümü aktive eder (ölçüm: inaktif sayısı 1 → 0; aktif kaynak
  push edilene eşitlendi); hatalıysa etmez. Araç kod göndermez — sunucuda **o an bekleyen** sürümü aktive eder; bilinçli
  bekletilen bir aktivasyon sırasını bozar. Aracın kendi `activationExecuted:false` dönüşü bu vakada yanıltıcıydı.
- Bağımlı obje: kök CDS'e alan eklemek bağlı behavior definition'ı sessizce inaktif bırakabilir; doğrulama HTTP 200'e
  bakıyordu ("obje var") ve yanlış "bitti" teste sızdı.

## K-11 · `REPORT/PROGRAM statement is missing, or the program type is INCLUDE`
- (a) Include program ucuyla `programType="I"` gönderilerek yaratıldı → SAP sessizce yürütülebilir program yaptı → sil,
  include ucuyla yeniden yarat (`foundation-ops.md` §4.2).
- (b) Include doğru tipte ama standart bir programın exit'ine bağlı → include tek başına derlenmez; bağlam programı
  üzerinden aktive edilir, standart obje aktivasyonu olduğu için kullanıcı onayıyla (`foundation-ops.md` §4.3).
  "Include doğası, zararsız" diye geçiştirmek YANLIŞ (push ≠ aktif).

## K-12 · `Include not found`
- Ana program aktivasyonunda include'lar aynı aktivasyon listesine konmadı → hepsini tek istekte aktive et (önce include'lar).

## K-13 · classrun: `does not implement if_oo_adt_classrun~main` / bayat çıktı
- Mesaj **doğrudur**, araç bozuk değildir. İki sebep:
  1. Sınıf **aktive edilmemiş** → aktif sürüm boş kabuk (classrun aktif sürümü koşar). Aktive et + `adt_inactive_objects` doğrula.
  2. Çalıştıran **oturum bayat:** obje başka bir süreçte aktive edildi, uzun ömürlü oturum eski sınıf yüküne bağlı kaldı.
     Süreç içi retry çözmedi (aynı oturumda iki POST, ikisi de aynı hata); **taze oturum** anında çalıştı.
- **Bayat çıktı (HTTP 200):** push+activate sonrası `adt_classrun` eski kodun çıktısını verdi; ikinci çağrı da aynı. Kaynak
  dört bağımsız okumayla temizdi. `ok:true` çıktının güncel olduğunu kanıtlamaz → çıktıda **yeni koda özgü bir imza**
  (yeni başlık satırı, yeni sabitin değeri) ara; yoksa sonucu "davranış yanlış" diye raporlama, önce bayatlığı ele.
  aXet CLI her çağrıda yeni süreç açıyorsa oturum bayatlığı azalır — **DOĞRULANMADI**; imza kontrolü yine yapılır.
- ⛔ **DENENEN — BAŞARISIZ:** "taze (hiç kullanılmamış) sınıf adıyla yeniden yarat" — iki kez uygulandı, çözmedi,
  iki gereksiz obje bıraktı. Kök neden: teşhis fonksiyonu kaynağı `version` vermeden (inaktif sürüm) okuyup
  "sınıf sağlam" diyordu.
- İlgili CSRF vakası: istek CSRF'siz gidince SAP 403 yerine **200 + yanıltıcı gövde** döndü (K-18).

## K-14 · classrun `400 Session Timed Out`
- Dialog context isteyen FM'ler (ekran/GUI status üretimi: `RPY_DYNPRO_INSERT`, `RS_CUA_INTERNAL_*`) classrun ile koşmaz.
  Önceki araç setinde çalışan kanal: RFC-enabled FM + `/sap/bc/soap/rfc`. aXet CLI'de bu kanal yok → kullanıcıya bildir.

## K-15 · FM push hataları
- `423 InvalidLockHandle`: genel kaynak-yazma yolu (retry/ETag'li stateful kilit) FM kilidini bozar → sıkı
  kilit → PUT → aktivasyon → bırak (`foundation-ops.md` §4.4).
- `400 Parameter comment blocks are not allowed`: imza `*"` yorum bloğuyla gönderildi → satır-içi ABAP imza.
- `400 FUNC_ADT 015 Parameter <P> declares no type`: `STRUCTURE` yazımı upload anında reddedilir → `TYPE <tablo_tipi>`.
- `FL 387 Type <X> is not a table type` (RFC işaretlenince): `TABLES p TYPE <yapı>` latent hatası → tablo tipi kullan (yeni DDIC = ad + metin kullanıcıdan).

## K-16 · `adt_post_shell` `ok:false` — obje yine de yaratılmış olabilir
- Ölçüldü (4 obje): araç 400/500 raporladı, kabuk fiilen yaratılmıştı. `exists_after`'a bak: `true` → tekrar yaratma
  (mükerrer risk), push ile devam · `false` → yeniden denenebilir · `null` → ölçülemedi, elle doğrula.
- `description_too_long` gerçek 400'dür (ölçülen sınır 60 karakter).

## K-17 · Z obje EN master language ile yaratıldı (Yasak D)
- Yaratma gövdesindeki `masterLanguage` tek başına yetmeyebilir; logon dili belirleyicidir. Kök vaka: istemci oturum
  header'larında `sap-client` vardı, `sap-language` yoktu → ilk logon EN → tüm yaratmalar EN.
- **EN-yapışkan isim:** EN yaratılıp silinmiş isim doğru yöntemle bile tekrar EN gelebilir → farklı isimle doğrula; asıl isim
  için kullanıcı/operatör kararı.
- Dil yerinde değişmez → sil + doğru dilde yeniden yarat. Her yaratmadan sonra metadata'dan `masterLanguage` oku.
  SE24 gibi ekranlar yeniden yaratma sonrası eski tamponu gösterebilir → yenilet.

## K-18 · CSRF
- CTS uçları (`/cts/*`) `/discovery`'den alınan token'ı **yanıltıcı bir 403** ile reddeder → o uç için ayrı token ön-alımı kasıtlı ve zorunludur.
- İstek başlıkları CSRF yenileme/retry mantığından **önce** kurulursa soğuk oturumda token hiç yazılmaz; SAP 403 yerine
  `200` + yanıltıcı gövde dönebilir (classrun vakası). Belirti: "başarılı" HTTP kodu + anlamsız hata metni.
- Eski bir CDS yaratma script'i "CSRF token expired" veriyordu; çare obje yaratmayı ayrı, taze token'lı adımda yapmaktı.

## K-19 · Açıklama (envelope) PUT'u → `412` ve obje inaktife düşer
- Obje açıklamasını değiştirmek objenin ana envelope'unu PUT eder; envelope ETag'i `source/main` ETag'inden farklıdır.
  Ölçülen (bir DDLS): bekleyen inaktif sürüm yokken bile GET'ten gelen ETag beklenen değil → `412 SADT_RESOURCE 043`.
  Gövdedeki `T100KEY-V2` (= sunucunun ETag'i) ile yeni bir kilit döngüsünde tek retry → 200.
- Başarılı envelope PUT'u objeyi **hemen** aktive-bekleyen listesine düşürür → açıklama değişikliği kozmetik değildir:
  aktivasyon + inaktif listenin yeniden okunması + aktif sürüm readback şart.
- Sınır: tek tip (DDLS) ölçüldü. Sunucu ETag'iyle retry kayıp-güncelleme korumasını atlar → yalnız envelope ilk okumadan
  beri aynıysa yapılır.
- **CLI (2026-09-13):** `adt_set_description` bu reçeteyi uygular (tek retry, envelope bayt kıyası, UNLOCK `finally`, kilit silinmez). PUT öncesi obje
  zaten inaktifse otomatik aktivasyon YAPMAZ → `activation_required`; aksi hâlde aktive eder ve listeyi + aktif sürümü yeniden okur. Yalnız
  class/bdef/srvd/ddls/ddlx/dcl; `srvb`/`prog`/`dtel` → `unsupported_type`. DDLS dışı tiplerde canlı ölçüm yok (`live_evidence: not_measured`).

## K-20 · `ResourceScanDuringSaveFailure` (satır numarası yok)
- **Yanlış yol:** hatayı kullanılan bir özelliğe (ör. metin kaydetme) yıkıp tahminle defalarca değiştir-push et (saatler gitti).
  Gerçek suçlu metot parametresinde `TYPE c LENGTH 100` idi. Ayrıca "uploaded/activated" mesajına güvenildi; kaynak persist olmamıştı.
- **ÇALIŞAN YÖNTEM (bisect):** ① `adt_get` ile aktif kaynağı çek, yereli **birebir** ona eşitle, push → temiz taban
  ② değişiklikleri **tek tek** ekle + push → kıranı bul ③ her adımda `adt_get` diff ile persist'i doğrula.
- Kaynak tabanlı sınıfta metot parametresinde `TYPE c LENGTH n` kullanma → `TYPE string`.
- İlgili: `OO_SOURCE_BASED 012 unknown comments` = yetim yorum; metot silinince üstündeki ABAP Doc yorumu da silinir.

## K-21 · `TEXT-xxx cannot be modified`
- Kaynakta `TEXT-xxx = '...'` yazılmaz; seçim ekranı başlık/yorumu için `tit1`, `com01` gibi değişken + `INITIALIZATION`.

## K-22 · `adt_transport_list count:0`
- Kanıt değildir, `shape_recognized:true` olsa bile (3 ölçümde E070'te 1, 2 ve 4 açık kayıt vardı).
- Neden ciddi: "transport yok" okuması **yeni transport açma** refleksine götürür = Yasak C ihlali.
- Çapraz kontrol: `E070` (`TRSTATUS`, `AS4USER`, `TRFUNCTION`, `STRKORR`) + içerik için `E071`; JOIN'i iki sorguya böl.

## K-23 · `adt_get exists:false` ama obje var
- Ağ/DNS kesintisi → `client_log`'da bağlantı hatası; varlık kanıtı değil, tekrar ölç.
- `object_type="func"` → grup çözümlemesi yok; `adt_search_objects` kullan.
- Tablo ↔ yapı karışıklığı → kardeş uç denemesi (`sibling_probe`); yaratma/silme kararında `adt_search_objects` ile çapraz kontrol.
- **Include objesi `prog` tipiyle sorgulandı → 404 / `exists:false` (sahte negatif, ekip dersi).** Obje canlıdaydı
  (`TRDIR` `SUBC='I'`); aynı obje `object_type:"include"` ile okundu. aXet'te kardeş uç denemesi yalnız tablo ↔ yapı için
  vardır, `prog` → `include` için yoktur. Include'u `include` tipiyle sor; "yok" demeden önce
  `SELECT name, subc FROM trdir WHERE name = '<AD>'` (ya da `TADIR`) ile çapraz kontrol et. Yanlış tiple alınan 404 objenin
  durumu hakkında hiçbir şey söylemez; üstüne yeniden yaratma/"push edilmemiş" kararı kurulmaz. `adt_lock_check`'in
  include için `locked:null` dönmesi "kilitsiz" değil ölçülemedi demektir (K-08).

## K-24 · Kimlik bilgisi değişti, hâlâ `401`
- Uzun ömürlü bir araç süreci bağlantı dosyasını başlangıçta okuyup tutuyorsa dosya düzeltmesi yetmez, süreç yeniden başlatılmalı.
- 401'de şifreyi tekrar tekrar denetme: hesap kilidi eşiği gerçek bir kaynaktır. Kullanıcıya bildir; gerekiyorsa
  kullanıcı SU01'den kilidi açtırır. Model şifreyi görmez, yazmaz.

## K-25 · İnaktif listede silinmiş obje
- `/activation/inactiveobjects` silinmiş objeleri de listeler; `ioc:deleted="false"` bunu ele vermez (ölçüm: TADIR
  `DELFLAG='X'` iki sınıf). Araç TADIR ile çapraz kontrol eder; ölçülemezse `count` basmaz (bkz. `foundation-query.md` §6).
- TADIR'daki `DELFLAG='X'` satırları silinmez (silmenin transportla taşınması için gerekir).

## K-26 · Sözdizimi kontrolü hata dedi, aktivasyon başarılı
- Sözdizimi kontrolü CDS/sınıf etkileşiminde ve SADL ile üretilen entity tiplerinde yanlış hata raporlayabilir → aktivasyon
  ile çapraz doğrula, SAP GUI'den kontrol ettir. Ama `parser_error`'ı körü körüne yanlış-pozitif sayma: çalışan referansla kıyasla.
- **Ayırt et — "hata" ile "ölçülemedi" aynı şey değildir:** `valid:false` (+ `errors`) = SAP bir hata döndürdü.
  `valid:null` = kontrol **ölçülemedi** (SAP kontrolü koşmadı: boş/kısa gövde, yalnız generation); MCP `adt_syntax_check`
  bunu `ok:false, error:"sozdizimi_belirsiz"` + `valid_reason` ile verir, `SAPClient.syntax_check`
  `[UNVERIFIED] Syntax NOT measured (OLCULEMEDI): <sebep>` basar. İkincisi "kod hatalı" demek değildir, "geçerli" de değildir;
  sebebi oku. Push'un aktivasyon öncesi ön-kontrolü ölçülemezse push durmaz ama `syntax_precheck:"olculemedi"` taşır.

## K-27 · "Obje ne zaman değişti" — `E070-AS4DATE` objenin değil isteğin tarihidir
- **Belirti:** bir objenin değişim tarihi `E071 × E070` join'iyle ölçüldü; aynı transporttaki tüm objeler aynı tarihi
  gösteriyor ya da tarih hiçbir değişiklikle örtüşmüyor.
- **Kök sebep:** `E070-AS4DATE` İSTEĞİN tarihidir. Aylarca açık kalan bir istekte bağlı tüm objeler aynı tarihi taşır.
  `E070`/`E071` yalnız "bu obje hangi transportta" sorusunu cevaplar (K-02, K-22).
- **ÇALIŞAN YÖNTEM:** ADT sürüm geçmişi — `adt_revisions` (her sürümde tarih, yazar, transport). Ekip dersinde ham uç
  (ör. sınıf implementasyon include'unun `…/versions` ucu) gerçek değişim damgası + satır sayısı + transport döndürdü.
- ⚠ **`Accept` başlığı (canlı ölçüldü 2026-09-25, DEV, salt-okur GET; sınıf · program include'u · arayüz):** obje
  isteği `Accept: */*` ile 200, `application/vnd.sap.adt.objectstructure+xml` ve `application/xml` ile **406**. Sürüm
  akışı (`…/versions`) `application/atom+xml;type=feed` ve `*/*` ile 200, `application/xml` ve
  `application/vnd.sap…versions.v1+xml` ile **406**. Z132 öncesi `adt_revisions` obje isteğinde objectstructure
  gönderdiği için bu üç tipte 406 → `revisions_unavailable` dönüyordu (kütüphanedeki `get_object_revisions` aynı hatayı
  sessizce boş listeye çeviriyordu). Düzeltildi: obje isteği `*/*`, akış isteği değişmedi (`atom+xml;type=feed`);
  kütüphane artık hatayı istisna olarak fırlatır. Düzeltme aXet CLI ile DEV'de canlı yeniden ölçüldü (2026-09-25): sınıf 2 kayıt, include 2, arayüz 1; var olmayan ad `not_found`
  (birim testleri ölçülen gövde biçimiyle taklitli).
- ⚠ **Bağlantı biçimi (aynı ölçüm):** sürüm bağlantısı `<atom:link href="…" rel="http://www.sap.com/adt/relations/versions" …/>`
  biçimindedir ve href GÖRELİDİR (obje URL'inin altına eklenir). Sınıfta birden çok bağlantı vardır, ilki
  `includes/definitions/versions`; ana kaynağın akışı `includes/main/versions` (sınıfta `source/main/versions` → 404).
  Include ve arayüzde `source/main/versions`. Araç ana kaynağın akışını seçer (yoksa ilk bağlantıyı) ve hangisini
  okuduğunu `versions_link` alanında yazar; sınıfın tanım/implementasyon include'larının geçmişi ayrı akıştır, araç
  bugün onları okumaz. `revisions_unavailable` ya da `revisions_feed_failed` "sürüm yok" demek DEĞİLDİR.
- Vakadaki kazanç: dump'ı doğuran ifade iki sürümde de birebir aynı çıktı ⇒ kırılma kod değil VERİ regresyonuydu;
  düzeltmenin yeri tamamen değişti.
- Bir tarih ölçtüysen raporda **objeye mi isteğe mi ait** olduğunu yaz; aksi hâlde ölçüm doğru, hüküm yanlış olur.

---

## Genel teşhis dersleri (tüm maddelerin ortak çekirdeği)

**G-1 · "Araç bozuk" karşılaştırmalı bir iddiadır.** Yalnız sorunlu obje üzerinde 5 başarısız varyant hipotezi test etmez,
güveni haksız büyütür. İki ölçüm gerekir: sorunlu vaka + çalıştığı bilinen vaka. Kontrol grubunu **yan etkisine bakarak** seç
(adı "runner/test/probe" diye masum sayılmaz; gövdesini oku); yan etkisiz aday yoksa `$TMP`'de en basit hâlini yarat-koş-sil
(yazma sınıfı → onay). Kontrol grubunun sağlam olduğunu da ölç. Kontrol edilen değişkeni ölçmeden kurulan kontrol grubu
tersini kanıtlıyor gibi görünür.

**G-2 · Tanıdık semptomda önce hafızayı ara.** Bayat oturum vakası bir ay önce çözülmüş ve kayda geçmişti; kayıt
okunmadı, sıfırdan hipotez kuruldu ve doğru bilginin üstüne yanlışı yazıldı. Sıra: proje hafızası + ekip hafızası + bu
referanslar → kontrol grubu → hipotez → "araç" sonucu.

**G-3 · Teşhisin kendisi kanıt gerektirir.** Aracın hata mesajının yanında gelen hazır "çözüm önerisi" hatanın kendisi kadar
şüphelidir. Hangi veriyi, hangi sürümünü, hangi parametreyle okuduğunu sor (tek eksik `version=active` parametresi →
6 dokümana yanlış bilgi, 2 gereksiz obje). Pahalı bir çare ilk denemede tutmadıysa ikinci kez uygulama.

**G-4 · Yetki sınırını ad ve doküman değil ölçüm belirler.** `*_check`, `*_get`, "preaudit", "dry-run" adı salt-okuma
garantisi değildir. Ölçüm: **taban ölç → aracı çağır → tekrar ölç** (araçtan bağımsız sayaç: inaktif obje sayısı, aktif
kaynak bayt kıyası). Aracın kendi dönüş bayrağını kanıt sayma.

**G-5 · `0` "yok" değildir, `>0` "var" değildir.** Boş sonuçta sorunun önkoşulunu doğrula (obje var mı, araç o kaynağı
gerçekten okudu mu). Eşleşmede token'ın sözdizimsel bağlamını sor (yorum, dizge, olumsuzlama). İki araç çelişirse
farklı mekanizmalı üçüncü ölçüm yap.

**G-6 · İddiadan önce sisteme sor.** Uzun oturumda "tamamlandı" listesine güvenme; kullanıcının "sildim/yaptım"
iddiasından sonraki ilk SAP işleminden önce de `adt_get` ile doğrula. Başarıyı iki sayıyla kanıtla (önce/sonra).

---

## Kaynağa göre alınan / bırakılan maddeler

**Bilinen hatalar dosyasından ALINAN:** syntax_check yanlış hata (→ K-26) · Dynpro/GUI-status tablosundan yalnız ADT maddeleri:
classrun `Session Timed Out` (K-14), classrun `does not implement` (K-13), FM push 423 (K-15), FM `comment blocks` 400 (K-15) ·
423 transport kaydı (K-02) · `NoModification` + kilit merdiveni + `adt_lock_check` 404 + ekran-kilit + `IS_LINK_UP` (K-04, K-07, K-08) ·
423 class PUT ilk denemesi + ETag sürüm tablosu + kilit hijyeni (K-03, K-01) · envelope PUT 412 + inaktife düşme (K-19).

**Bilinen hatalar dosyasından BAŞKA SKILL'E ALINAN:** SmartFilterBar filtre alanları · `sap.f.DynamicSideContent` 404 · manifest
annotation URL 400 · i18n dil ayarı → `%sap-ui5-fiori` (`references/known-errors-ui5.md`, `app-skeleton.md`) · GUI status
`00264 not generated`, `mandatory parameter BIV`, GUI status Almanca (SOAP-RFC dili), Geri/Çıkış fcode eşlemesi →
`%sap-classic-abap` (`references/dynpro-gui-status.md`, `known-errors-classic.md`).
**BIRAKILAN:** fixture/test çapası adları ve iç kütüphane satır referansları (aXet'te karşılığı yok).

**Foundation bölümünden eklenen:** 412/423/400 corrNr/`TEXT-xxx` (K-01, K-06, K-21) · 409 (K-05) · include hataları (K-11, K-12) · CDS CSRF expired (K-18).

**Araç semantiği notlarından eklenen:** `func` güvenilmezliği ve ağ hatasında `exists:false` (K-23) · `adt_delete func` çalışmaz (`foundation-ops.md` §4.4) · classrun maddeleri.

**Tekrarlanan hata kataloğundan ALINAN (ADT temel işlem dersleri):** #3 hafıza kayması ve #5 doğrulamadan güven (G-6) · #9 satırsız save-scan bisect (K-20) ·
#11 where-used `count=0` (G-5, `foundation-query.md` §3) · #13 kilit sızıntısı (K-09) · #16 arama kapsamı + teşhisin kanıtı + `>0` ayna hâli (G-3, G-5, K-13) ·
#18(f) taban-sonra ölçüm (G-6) · #19 kontrol grubu + önce hafıza (G-1, G-2) · #20 salt-okur sanılan araç (G-4, K-10) · #24 kimlik bilgisi ve süreç tazeliği (K-24) ·
#25 `$metadata` tip-kapsamlı doğrulama (`foundation-query.md` §5.1) · #26 kopya silmeden referans (`foundation-query.md` §3.4) · #33 `TABLES` latent hata (K-15).

**Tekrarlanan hata kataloğundan BIRAKILAN:** #4, #6, #10, #12, #14, #15, #27–#31 ve talimat-bakımı dersleri (önceki ajan ortamının hook/guard/junction/ajan/git
araçlarına özgü; genel olanları ekip hafızasında zaten var: git diff, PowerShell tırnak, bayat sayı, envanter) · #7 placeholder
tuzağı ve #8 klasik program include bölme (obje-tipi/kodlama standardı partisi) · #17 çapraz-kesen envanter (ekip hafızasında var) ·
#21 S/4 classic view + replacement tablo, #32 standart CDS DCL sessiz 0 satır → `%sap-cds-ddic` `references/cds.md` (CDS-NSDM-01,
CDS-DCL-01/02) · #22, #23 klasik Dynpro üretimi → `%sap-classic-abap` `references/dynpro-gui-status.md`.

**2026-09-25 eşitlemesinde eklenen (ekip dersi):** K-23'e include `prog` tipiyle 404 sahte negatifi; K-27 (`E070-AS4DATE` ≠ obje değişim tarihi, sürüm geçmişi ucu ve
`Accept` başlığı). Kaynaktaki transport/obje adları ve ham GET kod deseni alınmadı.
