# ATC bulgusu düzeltme kalıpları (önce iç içe okuma / `FOR ALL ENTRIES`)

> **Ne:** sık ATC bulgu sınıfları için gözden geçirilmiş düzeltme kalıbı + "düzeltmeden önce neyi okumadan emin
> olamazsın" listesi + "bu kalıbın yanlış olabileceğini gösteren işaretler".
> **Ne değil:** kapı ya da otomatik düzeltici değildir. Kalıp **öneridir**; her düzeltme bağımsız inceleme (SKILL §4)
> + ATC yeniden koşumuyla (`adt_atc_check`) kanıtlanır.
> **Kaynak:** ekip çekirdeğinin ATC düzeltme reçetesi; o reçete de dış bir ATC kalıp kataloğundan yalnız **yapıyı**
> almıştı (kalıp / gerekli bağlam / düşük güven işareti) — kontrol kimliği listeleri ve güven oranları alınmadı.

## 0. Genel kurallar (her bulgu sınıfı)
- **Öncelik 1 zorunlu düzeltilir;** öncelik 2/3 ancak açık kullanıcı onayıyla geçilir (`clean-core.md` §5).
- **Bulgunun YAZILDIĞI sınıfı doğru oku:** "iç içe veritabanı okuması" ailesi bulguyu döngüyü içeren sınıfa değil
  **`SELECT`'i içeren metodun sınıfına** yazar ⇒ önce/sonra sayımını orada yap.
- **Sınıflandırma kimlikle yapılır, metinle değil:** ATC sonucunda kontrol kimliği (`checkId`) bir GUID'dir; "metinde
  `FOR ALL ENTRIES` geçiyor mu" türü arama kümelemeyi bozar ⇒ kimlik + mesaj metni birlikte.
- **Önce/sonra karşılaştırmasında satır numarası kullanma:** bir satır kaydırması her bulguyu "yeni" gösterir. Parmak
  izi = obje + birim (metot/include) + kontrol kimliği + mesaj.
- **Pseudo-comment / pragma ile muafiyet** yalnız kullanıcı onayıyla ve satır üstünde gerekçe yorumuyla. Muafiyet adı
  tahmin edilmez — denetim sınıfının kaynağında `#EC` sabiti aranır. Ekip dersi (bir müşteri projesi, 2026-09-28):
  S/4 alan uzunluğu genişletme bulgusu için `"#EC CI_FLDEXT_OK[<not no>]` biçimi çalıştı (bulgu push sonrası kalktı) —
  köşeli parantezde **not numarası** şarttır. ⚠ Pseudo-comment **sessizce yok sayılıyorsa** ilk bakılacak yer:
  denetlenen sistemde ve merkezi ATC sisteminde ilgili SAP notunun uygulanmış olması (dış kaynak SAP Note 2754597 /
  KBA 3624162'yi gösteriyor — numaralar DOĞRULANAMADI, uygulamadan önce SAP'de oku).
- **Pseudo-comment yerleşimi (canlı ATC ile ölçüldü, ekip dersi 2026-10-15):**
  1. **Satır başına tek `"#EC`.** `… "#EC CI_NESTED "#EC CI_STDSEQ` yazılırsa yalnız İLKİ tutar, ikinci bulgu sessizce
     kalır (ABAP belgesi ABENPSEUDO_COMMENT: "Only one pseudo comment can be specified per program line"). Birden çok
     muafiyet gereken ifadeyi satırlara böl, her satır sonunda tek `"#EC`.
  2. **Bulgunun ATC'de gösterildiği satıra koy.** Düz `LOOP … WHERE`'de ifadenin herhangi bir satır sonu tutar; ama
     `VALUE …( FOR x IN t WHERE ( … ) … )` içindeki bulguda `"#EC` FOR satırında tutmadı, WHERE satırına taşınınca tuttu.
  3. **Ad kaynağı:** bulgunun ATC sonucundaki belge bağlantısı (`rel="documentation"`) "Finding can be suppressed with
     pseudo comment …" der; aynı belge muafiyet edilemeyen bulguyu da söyler ("Cannot be suppressed …").
  Denetim sınıfının kaynağından "aynı satırda iki tane olur" diye çıkarım yapılmıştı, canlı ATC çürüttü: hüküm kaynak
  okuması değil push + ATC ölçümüdür. Push sonrası "0 bulgu" görünce koşunun tam olduğunu (`objectSetIsComplete="true"`) ve
  aynı koşuda başka bir kontrolün bulgu raporladığını doğrula ("koşmadı" olasılığı).
- **"Incorrect Pretty Print state"** birim başına yalnız İLK farkı bildirir — satırı düzeltmek kapatmaz; birimi bütün
  olarak biçimle: `%sap-classic-abap` `references/classes.md` §7.1.

## 1. İç içe veritabanı okuması (döngü içinde `SELECT`) — en sık öncelik 1
**Kalıp:** döngüden ÖNCE tek toplu okuma → bellekte erişim.

```abap
" ÖNCE: LOOP AT lt_items INTO ls_item. SELECT SINGLE … WHERE key = ls_item-key. … ENDLOOP.
TYPES tt_lookup TYPE HASHED TABLE OF ty_lookup WITH UNIQUE KEY key.   " erişim anahtarıyla tipli
DATA lt_lookup TYPE tt_lookup.
IF lt_items IS NOT INITIAL.                        " ⛔ boş sürücü tablo = TÜM tabloyu okur
  SELECT key, field1, field2
    FROM <tablo_ya_da_released_cds>
    FOR ALL ENTRIES IN @lt_items
    WHERE key = @lt_items-key
    INTO TABLE @lt_lookup.
ENDIF.
LOOP AT lt_items INTO DATA(ls_item).
  READ TABLE lt_lookup INTO DATA(ls_hit) WITH TABLE KEY key = ls_item-key.
  IF sy-subrc <> 0.
    CONTINUE.                                      " ⛔ bulunamadıysa ls_hit ÖNCEKİ turun değerini taşır
  ENDIF.
  " … ls_hit kullanımı …
ENDLOOP.
" Standart tablo kalacaksa: okumadan sonra SORT lt_lookup BY key + BINARY SEARCH + aynı sy-subrc kontrolü (§4).
" Anahtar tekil değilse HASHED UNIQUE yerine SORTED NON-UNIQUE KEY seç: UNIQUE tabloya yinelenen anahtar
" SELECT … INTO TABLE'da çalışma zamanı hatasıdır (istisna adı ölçülmedi).
```

**Okumadan emin olamazsın (gerekli bağlam):**
- Sürücü tablo **boş olabilir mi?** Boşsa `FOR ALL ENTRIES` koşulsuz okur — `%sap-dev` `references/coding-patterns.md` §3.
- Okunan değer **toplanıyor mu?** `FOR ALL ENTRIES` sonuç kümesine örtük `DISTINCT` uygular; SELECT listesinde kaynağın tam
  tekil anahtarı yoksa eşit değerli satırlar teke iner, toplam eksik çıkar (`checklist-abap.md`: döngü içi `SELECT SUM` satırı).
- `GROUP BY` / aggregate gerekiyor mu? `FOR ALL ENTRIES` ile birlikte yazılamaz — `%sap-dev` `references/coding-patterns.md` §2.
- Okuma bir **standart CDS**'ten mi? Yetki reddi hata değil 0 satır döner — `%sap-cds-ddic` cds.md CDS-DCL-01.

**Bu kalıbın YANLIŞ olabileceğini gösteren işaretler (düşük güven):**
- Döngü içindeki okuma **önceki turun yazdığı** veriyi görmek zorunda (aynı LUW'da sıralı bağımlılık).
- Sürücü tablo çok büyük ve okunan tablo küçük — tamamını bir kez okumak daha doğru olabilir.
- Okuma bir metot çağrısının arkasında — düzeltme çağrılanın sınıfında yapılır; döngüyü taşımak bulguyu taşımaz.

## 2. `SELECT *`
**Kalıp:** açık alan listesi. **Gerekli bağlam:** okunan yapının **tüm tüketicileri** — yapı bir metottan dönüyor ya da
başka bir rutine aktarılıyorsa hangi alanların kullanıldığı oradan okunur (`adt_where_used`). **Düşük güven:** hedef
`CORRESPONDING`/dinamik atama ile dolduruluyor ya da yapı bir arayüz parametresi (tüketiciler paket dışında).

## 3. Alan uzunluğu genişletmesi (ör. malzeme numarası)
**Kalıp:** sabit uzunluklu yardımcı değişken yerine veri elemanı tipi; `+off(len)` alt dize ve `WRITE … TO` ile kesmeyi
kaldır. **Gerekli bağlam:** değer gerçekten genişletilmiş uzunlukta taşınıyor mu (yoksa bulgu kullanıcı onayıyla muaf
tutulabilir — §0). **Düşük güven:** değer bir dış arayüzde (IDoc/dosya) sabit genişlikli alana yazılıyor — kesme orada
**sözleşmenin** parçası olabilir; sessiz kesilme yerine açık kontrol + hata mesajı.

## 4. Sıralama varsayımı
**Kalıp:** `SELECT SINGLE`'ı tam anahtarla yaz; çok satırlı okumada sıra gerekiyorsa `ORDER BY`; `BINARY SEARCH` öncesi
aynı anahtarla `SORT`. **Gerekli bağlam:** tablonun anahtarı (DDIC) ve `READ TABLE … BINARY SEARCH` çağrılarının
kullandığı anahtar. **Düşük güven:** `WITH EMPTY KEY` tabloda ölçütsüz `SORT` / `DELETE ADJACENT DUPLICATES`.

## 5. Toplu düzeltme yapılacaksa
Çok sayıda bulgunun model yardımıyla toplu düzeltilmesi planlanıyorsa iş **yargı kuyruğu sözleşmesiyle** yürür:
`%sap-dev` `references/batch-judgment-queue.md` — model kararları dosyada, doğrulama kodda, cevapsız bulgu açık kalır.
Yazma kapısı (`%sap-adt-foundation` §4), pull-before-edit ve bağımsız inceleme şartları aynen geçerlidir.

## Bu dosyada ÇIKARILAN / DEĞİŞTİRİLEN
- Ekip kontrol listesi kimlikleri metne yazılmadı; ilgili `checklist-abap.md` satırı konusuyla anıldı.
- Müşteri/proje adı çıkarıldı; pseudo-comment ölçümü "ekip dersi" olarak, SAP not numaraları DOĞRULANAMADI etiketiyle aktarıldı.
