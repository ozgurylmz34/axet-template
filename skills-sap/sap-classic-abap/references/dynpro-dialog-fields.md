# Datafield'lı diyalog ekranı — DDIC'e bağlı tek kayıtlık form, arama yardımı, çok turlu CUA

> Kaynak: ekip playbook'unun datafield diyalog ekranı kılavuzu (bir stok hareketi takip programının 3 modal diyaloğu;
> her satır canlı ölçülmüş vakaya dayanır) · klasik dialog kodlama standardı §9 · kanonik diyalog şablonu.
> Ekran/CUA üretiminin temeli `dynpro-gui-status.md`'dedir; burada tekrarlanmaz. Şablon: `templates/classic-dynpro-dialog.prog.abap`.

## 0. Karar ağacı
```
Ekran çok satır mı gösteriyor (rapor/liste/bakım grid)?
  ├─ EVET → LİSTE → templates/classic-alv-list.prog.abap + alv-report.md
  └─ HAYIR, tek kayıtlık form (birkaç alan, kaydet/iptal) → DİYALOG → bu dosya
Diyalog bir listenin satırından mı açılıyor?  → modal: çağıran CALL SCREEN <n>, PAI'de LEAVE TO SCREEN 0 ile döner
Aynı programda liste + ondan açılan diyaloglar → normal (canlı örnek: ana grid 0100/0200 + 3 diyalog 0300/0400/0500)
```
Fark: liste ekranı üretiminde yalnız toolbar butonu verilir (kolonlar ALV'den gelir); diyalog ekranında **her alan DDIC
yapısına bağlı** verilir. Bu fark anlaşılmayınca programa özel `gs_*` yapılar + köprü koduna dönülür.

## 1. DDIC yapısına bağlama (`FROM_DICT`)
- Ekran alanı: `NAME = '<YAPI>-<ALAN>'`, `TYPE = 'TEMPLATE'`, `FROM_DICT = 'X'`, `MATCHCODE` **boş**.
  (`TEMPLATE` bir alan değil `TYPE` değeridir; canlıda koşmuş örnek: `NAME='ZSD001_S_DLG-MATNR' TYPE='TEMPLATE' FROM_DICT='X' CONV_EXIT='MATN1'`.)
- Program tarafı: global work area'nın adı **yapı adıyla aynı** (`DATA zsd001_s_dlg TYPE zsd001_s_dlg.`).
- DDIC'ten gelen (ölçüldü): **uzunluk** (payload'da kısa gönderilen QUAN/DATS alanı canlıda `DD04L.OUTPUTLEN`'e çıktı) ·
  `CONV_EXIT` · **F4** (`VBAK-VBELN` alanında F4 kayıt listesi açıldı).
- ⚠ Eskimiş gerekçe: "ekran alanları program yapısına bağlı olduğu için `FROM_DICT` kullanılamaz" iddiası **döngüseldi**
  (seçimin sonucunu sebep gibi sunuyordu; hiç denenmemişti). Programa özel `gs_*` yapı + `MOVE-CORRESPONDING` köprüsü bir
  geçiş borcudur: DDIC yapısına geçilince köprü **tamamen** silinir (referans sayısı 0), yarım bırakılmaz.
- Yeni DDIC yapısı = alan + data element + ad onayı (SAP çekirdeği); DTEL adı önerilmez.

### 1.1 ⭐ Etiket kuralı — giriş alanı kendi etiketini getirmez (kontrollü sonda, ölçüldü)
| Gönderilen | Sonuç |
|---|---|
| `NAME='VBAK-ERDAT' TYPE='TEMPLATE' FROM_DICT='X'`, `TEXT` satırı yok | yalnız giriş alanı — **etiket yok** |
| `NAME='VBAK-ERNAM' TYPE='TEXT' FROM_DICT='X'`, `TEXT` **boş** | etiket metni DDIC'ten geldi |
- Her etiket **ayrı** bir `TYPE='TEXT'` satırıdır; `TEXT` boş + `FROM_DICT='X'` → metin DDIC'ten (metin uydurulmaz — kesin yasak D dostu).
- TEXT satırını unutmak **sessiz** kusurdur (etiketsiz giriş alanı meşru kullanım, uyarı yok) → alan sayısını değil **etiket/alan çiftlerini** say.

### 1.2 Alan satırı ayrıntıları
- Geçerli `TYPE`: `TEXT` `TEMPLATE` `RADIO` `CHECK` `FRAME` `FRAME_TMPL` `PUSH` `PUSH_TMPL` `INFOBUTTON` `OKCODE`; boş → `TEMPLATE`.
- `TEMPLATE` + `INPUT_FLD`/`OUTPUT_FLD` ikisi boşsa kaynak ekibin üreteci alanı giriş+çıkış açıyordu; salt okunur için `OUTPUT_FLD='X'` tek başına ya da `REQU_ENTRY='N'`.
- `RPY_DYNPRO_INSERT` davranışları (ölçüldü): `LINE`/`COLUMN` boş → gürültülü red ama **hangi alan** olduğunu söylemez ·
  `TEMPLATE`'te ne `LENGTH` ne `FROM_DICT` → **sessizce 0 genişlikli**, kullanılamaz alan · var olmayan container'a bağlı
  alan → **tamamen sessiz** yutulur, rc=0 (sahte OK). Yazmadan önce bu üç sınıfı payload'da kontrol et.
- Ekrandaki bir `SELECT-OPTIONS` 6 ayrı alan-container satırı ister (`TEXT`/`OPTI_PUSH`/`LOW`/`TO_TEXT`/`HIGH`/`VALU_PUSH`).
- Alan ekranı **docking** ister (container modunda `CC_ALV` tüm ekranı kaplar → rc=6).

## 2. ⭐ Arama yardımı (F4) — dört mekanizma
| # | Mekanizma | Ne zaman | Maliyet |
|---|---|---|---|
| ① | Data element'e bağlı standart arama yardımı | alanın DTEL'i zaten bir standart SHLP'ye bağlı | bedava — `FROM_DICT` yeter |
| ② | **Yapı bileşenine `with value help` bağlama** | DTEL'de SHLP yok ama standart bir SHLP mantıksal uyuyor | düşük — DDIC yapı değişikliği + ekranın **yeniden üretimi** |
| ③ | Buton + popup (`REUSE_ALV_POPUP_TO_SELECT`) | süzgeç gerekli ve Z SHLP gerekirdi | orta — program içinde birkaç FORM |
| ④ | POV modülü (`PROCESS ON VALUE-REQUEST`) | veriye bağlı süzgeç | kaynak ekibin üretecinde **yoktu** (§2.4) |

### 2.1 Z arama yardımı (SHLP) bu araç setiyle yaratılamaz (üç bağımsız kanıt, kontrol gruplu)
1. `adt_get object_type="shlp"` desteklenmiyor. 2. ADT discovery iki filtreyle tam tarandı (118 + 71 koleksiyon):
`searchhelp`/`shlp` koleksiyonu **yok**; aramanın döndürdüğü `/sap/bc/adt/vit/wb/object_type/shlpdh/…` URI'si Eclipse'e gömülü
SE11 ekranının köprüsüdür, POST edilebilir kaynak değil ("bulunan URI ≠ yazılabilir uç"). 3. `DDIF_SHLP_PUT/GET/ACTIVATE`
RFC-enabled değil (`TFDIR-FMODE` boş; kontrol: `RFC_READ_TABLE`, `BAPI_MATERIAL_GET_DETAIL` → `R`).
⇒ Süzgeçli F4 → ③. Z SHLP gerçekten şartsa: geliştirici SE11'de elle, kullanıcı onayıyla (ortak mı yerel mi sorulur). aXet CLI'de de araç yoktur.

### 2.2 Mekanizma ② — bağlama ALAN ADINA değil BİLEŞENE yapılır
```abap
define structure zsd001_s_dlg {
  ver_lgort  : lgort_d
    with value help h_t001l
      where lgort = zsd001_s_dlg.ver_lgort
        and werks = zsd001_s_dlg.ver_werks;
  alan_lgort : lgort_d                        " aynı yapıda ikinci lgort_d — bağlama tek ayırt edici yoldur
    with value help h_t001l
      where lgort = zsd001_s_dlg.alan_lgort
        and werks = zsd001_s_dlg.ver_werks;
}
```
| Çürütülmüş iddia (iki kez tekrarlandı) | Neden yanlış |
|---|---|
| "Aynı yapıda iki `lgort_d` var ⇒ bağlama yolu kapalı" | bağlama yapı **bileşenine** yapılır; iki bileşen aynı SHLP'ye bağlanabilir (ölçüm: 7 alanın tümü `MATCHCODE` boş + `FROM_DICT`, ikisi `H_T001L`'e bağlı) |
| "DDIC'e bağlı alanda F4 parametre karışması olmaz" | **ölçüm çürüttü**: eşleme kurulmazsa F4 seçilen satırın yanlış alanını (ör. üretim yeri) yazar; `FROM_DICT` eşlemeyi kendiliğinden kurmaz → `where` açıkça yazılır |
- ⚠ Ekrandaki elle `MATCHCODE` DDIC bağlamasının **önüne geçer** → ekran tarafı `MATCHCODE` boş.
- ⚠ **Obje aktif ≠ tüketici güncel:** klasik Dynpro DDIC bilgisini (arama yardımı dahil) **üretildiği anda gömer**. Yapıya
  bağlama eklemek ekrana kendiliğinden inmez → ekranın yeniden üretilmesi (regen) **baştan plana** konur.

### 2.3 Tanıdık F4 semptomunda önce ara
Vaka: elle `MATCHCODE` geri konup "çözüldü" dendi; oysa üç gün önceki teşhis notu kusurun parametre eşlemesinin yokluğu
olduğunu yazmıştı → aynı deney tekrar kuruldu ve tekrar çürüdü. Önce `%recall` + paket `SESSION_NOTES.md`, sonra deney.

### 2.4 Veriye bağlı F4 (POV)
- Üreteç akışı sabit iki modül yazıyordu, `PROCESS ON VALUE-REQUEST` üretmiyordu; elle eklenen POV ekran yeniden
  üretildiğinde **silinir**.
- Telafi: `Bakiye`/`Listele` butonu + salt görüntüleme popup'ı; kullanıcı değeri görüp elle yazar (bilgi erişimi kaybolmaz).
- Paylaşılan bir aracı genişletmeden önce sorunun kendi katmanında (DDIC) çözümü var mı sor: vakada POV planı iptal edildi,
  aynı ihtiyaç mekanizma ② ile çözüldü.

## 3. Program tarafı desenleri (şablonda hazır)
- **Dinamik alan kilidi:** kapsam içi kayıt otomatik dolduruluyorsa `LOOP AT SCREEN … screen-input = 0 … MODIFY SCREEN`;
  kapsam dışıysa giriş açık kalır (regresyon yok). Çağrı **PBO'da** olmak zorunda — PAI'de sessizce uygulanmaz.
- **Ekrana özel fcode:** fonksiyon metni + quickinfo program genelidir → iki diyalog aynı kaydet fcode'unu paylaşırsa biri
  yanlış etiket gösterir. Her diyalog kendi fcode'unu taşır (ör. `DLGKAY`, `TRFKAY`).
- **PAI:** fcode'u normalize et, `CLEAR` ok-code ve `sy-ucomm` (yapışkan komut); `WHEN OTHERS` boş (tanımsız fcode'da hiçbir şey).
- **Buton + popup F4:** hedef alanı **fcode** belirler, `GET CURSOR` değil (imleç başka alanda olabilir → sessiz yanlış yazım/no-op).
  `REUSE_ALV_POPUP_TO_SELECT` tercih; `F4IF_INT_TABLE_VALUE_REQUEST` değil (PAI'den adresleme gereksiz; tek seçimde birden çok
  alan yazılacaksa `RETFIELD` modeli ifade edemez). Açıklama join'i `LEFT OUTER` (açıklaması olmayan kayıt listeden düşmesin).
  Clean core: ham `MARA/MAKT` yerine released ürün CDS'i (adı sistemde `adt_search_objects` ile doğrulanır).
- **Kaydetme sırası:** ① saf girdi kontrolü (DB'ye bakmaz) → ② kilit → ③ DB'ye bakan kontrol (bakiye/çakışma — kilit alındıktan
  sonra, yarış koşulu) → ④ yaz (BAPI ya da iş mantığı sınıfı; standart tabloya doğrudan DML yasak — kesin yasak B) →
  ⑤ commit/unlock (`TRY … CATCH`; unlock her koşulda).

## 4. Çok turlu ekran/CUA — ölç → payload → yaz → doğrula
0. Donör ve davranış anahtarlarını kararlaştır (`dynpro-gui-status.md` §3). Varsayılan donör üretece göre değişir: kaynak
   ekibin üretecinde minimal donör `&F2..&F5` üretiyordu; template kitinde (`ZBC000_FM_SCREEN_GEN`) varsayılan `SAPLKKBL/STANDARD`
   ve nav-remap açık (`references/screen-gen-kit.md`). Sistemdeki üretecin varsayılanını kaynağından oku; her durumda donörü
   **açıkça** ver.
1. Mevcut ekranı/CUA'yı oku (tur öncesi sayaçlar).
2. Payload'ı **canlıyı üreten kaynak payload'dan** kur, üzerine değişiklik ekle.
   ⚠ Okuma dökümünden yeniden kurma: döküm `FROM_DICT` bayrağını **taşımaz** → DDIC bağı sessizce silinir.
   ⚠ Repodaki payload dosyası bayat olabilir (vaka: dosyada 2 butonlu sanılan status'ün canlıda 3 butonu vardı; kayıp bir tur
   sonra `BUT` deltası 1 fazla çıkınca geriye doğru teşhis edildi).
3. `BUT` deltasını **yazmadan önce** hesapla ve tur öncesi sayaçla kıyasla; tutmuyorsa gönderilecek set yanlıştır.
4. Yaz; final sayaçları + fonksiyon detay dökümünü diff'le; `adt_inactive_objects` 0.
5. GUI'de kullanıcıya sor: her diyaloğun kendi kaydet fcode'u doğru etiket/quickinfo'da mı · dinamik kilitli alan kapsam
   içi/dışı doğru mu · yeni metinlerde Türkçe karakterler doğru mu.
- Bir kontrolün (ATC, lint) bulduğu sayı **alt sınırdır**; kapsamı koddan çıkar.

## 5. Tuzak → aksiyon
| Tuzak | Aksiyon |
|---|---|
| Programa özel `gs_*` yapı + köprü | DDIC yapısına bağla, köprüyü tamamen sil |
| "Aynı tipte ikinci alan var, bağlama kapalı" | bağlama bileşene yapılır |
| "DDIC'e bağlı alanda F4 karışmaz" | `where` eşlemesini açıkça yaz |
| Elle `MATCHCODE` + bağlama | `MATCHCODE`'u boşalt |
| DDIC değişti, ekran eski | yeniden üretim zorunlu adım |
| Z SHLP yaratmayı denemek | yapılamaz (§2.1) → buton + popup |
| Veriye bağlı F4 için POV | üreteç/regen siler → buton + popup |
| Payload'ı okuma dökümünden kurmak | kaynak payload'ı kullan |
| Status'e eksik buton listesi | tüm butonlar her yazımda |
| Donörle çakışan fcode'u payload'a koymamak | koy ya da ayrı fcode |
| Birden çok status aynı fcode'u farklı quickinfo ile bekliyor | ekran başına ayrı fcode |
| Sayaç kontrolünü yazımdan sonra yapmak | `BUT` deltası yazımdan önce |
| Giriş alanı verip etiketi DDIC'ten beklemek | ayrı `TYPE='TEXT'` satırı |
| Alan ekranını container moduyla üretmek | docking |
| Tanı mesajını kırpmak | tam oku (uyarılar sonda) |
