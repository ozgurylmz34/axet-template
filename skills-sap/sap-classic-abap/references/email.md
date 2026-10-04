# ABAP'ten e-posta — HTML gövde (+ ek dosya)

> Kaynak: ekip playbook'unun ABAP e-posta bölümü (her kural canlı yaşanmış bir hatadan). Profil: `ecc`, `s4_private`
> (klasik ABAP); `s4_public`'ta bu API'ler yoktur. **Yeni mail yazmadan §7 kontrol listesini oku.**
> E-posta göndermek dışa dönük bir iştir: test gönderimi dahil alıcı listesi ve içerik için kullanıcı onayı (çekirdek §3).

## 0. Yol seçimi
- **`SO_DOCUMENT_SEND_API1`** — çalışır, arka plan işinde (job) çalışır; mevcut çalışan kodu buna dokunmak için taşıma.
- **`CL_BCS`** — yeni işlerde, ek dosyada ve 50 karakterden uzun/Türkçe konuda önerilen modern yol (§6). **Kısmen canlı**
  (çekirdekte ölçüldü, S/4 private 2025 — neyin ölçüldüğü §6 listesinde; aXet'te ayrıca ölçülmedi).
- Gönderen adresi kodun değil kurumun kuralıdır: yeni mail işine **§1 gönderen politikası** ile başla.
- **PDF eki:** SFP form objesi varsa `forms-f1-help.md` §A.2 (`ls_formoutput-pdf`); form objesi yoksa `%sap-pdf-output`.
- İki çalışan desen: FORM tabanlı mail include'u (`<GÖVDE>_I_<AD>_F01`) ve sınıf tabanlı işçi (satır içi stil, parça
  ekleme, başarı/hata ayrımı, ABAP Unit ile test edilebilir) — uzun/tekrarlı mantıkta sınıf tercih edilir.
- ⚠ Anti-desen: 8+ kolonlu tabloyu doğrudan gövdeye basan eski mailler (aşağıdaki tuzakların çoğu buradan çıktı).

## 1. Gönderen — önce kurumun gönderen POLİTİKASINI öğren
> **Gönderen politikası (çekirdekte canlı ölçüldü, S/4 private 2025):** SAPconnect'in teslim ettiği kurumsal relay
> (ör. Microsoft 365 / Exchange Online) çoğu kez **yalnız yetkili bir teknik adresten** gönderime izin verir ("Send As"
> kısıtı). SAP kullanıcısı gönderen yapılınca relay maili reddeder; SOES'te `XS 812` +
> `554 5.2.252 SendAsDenied; <kimliği doğrulanan hesap> not allowed to send as <From>` görünür. Teşhiste asıl ipucu
> metnin ikinci yarısıdır: relay'in hangi hesapla bağlandığını ve hangi gönderene izin vermediğini söyler. Ölçülen vakada
> aylarca biriken yüzlerce 812 "test sisteminden mail çıkmaz" diye normal sayılmıştı; gönderen teknik adres yapılınca aynı
> sistemden mail dış posta kutusuna ulaştı (ekip hafızası: "'Bu ortamda normal' hükmünden önce hata metnini oku").
> - **Kural:** yeni mail işine başlarken gönderen politikasını kullanıcıya/Basis'e **sor** ve SOES geçmişinde
>   812/SendAsDenied var mı **baktır** (§1.1).
> - Teknik adres zorunluysa CL_BCS: `lo_send->set_sender( cl_cam_address_bcs=>create_internet_address(
>   i_address_string = <teknik-adres> ) )`. Adres projenin belgelenmiş **tek** yerinden gelir (kaynağı yorumunda yazılı
>   sabit ya da bakım tablosu); adresi kullanıcı verir, uydurulmaz.
> - Bu durumda "gönderene CC" gibi özellikler anlamını yitirir → yanıt alacak kişiyi gövdede adıyla belirt.

**Relay serbest bırakıyorsa** varsayılan, job'u çalıştıranın gönderen olmasıdır:
```abap
sender_address      = CONV soextreci1-receiver( sy-uname ).
sender_address_type = 'B'.   " B = SAP iç kullanıcı
```
- ⛔ Sabit **SAP kullanıcı adı** gömme (`CONSTANTS gc_sender … VALUE '<SAP_USER>'`): job'u kim çalıştırıyorsa ondan gitmeli.
  Kurumun zorunlu kıldığı **teknik SMTP adresi** bu yasağın konusu değildir (yukarıdaki politika kutusu).
- ⛔ `type='U'` (SMTP) + değer olarak SAP kullanıcı adı → gönderen bozuk (canlı hata). SAP kullanıcısı → `'B'`; gerçek SMTP adresi → `'U'`.

### 1.1 Teslim teşhisi — SOST / SOES
| SOES / SOST durumu | Anlamı |
|---|---|
| `XS 718` tip `I` "Recipient Is Valid. Delivery Attempted" (MSGV'de `250 2.1.5 Recipient OK`) | Relay kabul etti → dışarı çıktı (çekirdekte canlı) |
| `XS 812` + `554 5.2.252 SendAsDenied` | Gönderen adres relay'de yetkisiz → §1 (çekirdekte canlı) |
| `W` (bekliyor) | ⚠ ölçülmedi. Aylarca `W`'de kalan kayıt "henüz koşmadı" demek DEĞİLDİR — ayrı teşhis ister (SCOT gönderim işi, node/adres eşleşmesi) |
- SOST'ta HTML eki açarken çıkan **SO596** ("güvenlik nedeniyle değiştirildi") yalnız SAP GUI görüntüleyicisinin
  `<style>`/SVG ayıklamasıdır — mail engeli DEĞİL.
- ⛔ **"Test sisteminden mail çıkmaz" VARSAYMA.** Çıkabilir: test alıcılarını kontrol et (bakım tablolarında gerçek
  müşteri/depo adresleri durabilir), deneme mailini yalnız kendine gönder.
- SOST kaydını kullanıcıya baktırırken durum kodunu değil **hata satırının tam metnini** birebir iste (sebebi çoğu kez o söyler).

## 2. Alıcılar — dinamik, pasifler hariç
```abap
APPEND VALUE #( receiver   = <eposta>  rec_type = 'U'
                copy       = COND #( WHEN typ = 'CC'  THEN abap_true )
                blind_copy = COND #( WHEN typ = 'BCC' THEN abap_true ) ) TO lt_reci.
```
- Alıcılar koda gömülmez; bir Z bakım tablosundan gelir (ör. `ZSD001_T_MAIL`; yeni tablo = alan/DTEL/anahtar onayı).
- Aktif/pasif: `WHERE pasif <> 'X'` (boş = aktif). Alıcı yoksa o kaydı atla (job log), akışı kesme.

## 3. HTML gövde — beş tuzak
**3.1 `<head><style>` sınıf CSS'i uygulanmaz → satır içi stil şart.** Outlook / Gmail / SAP mail görüntüleyici head
CSS'ini yok sayar (kenarlık, renk, hizalama gider). Stil elemana:
```abap
|<td style="width:160px;background:#f5faff;border:1px solid #ccc;padding:5px 8px;color:#555;">{ label }</td>|
```
**3.2 Tek atama sessizce keser → 255 karakterlik parçalar şart.** `solisti1-line` CHAR255; uzun satır kesilir, etiket
ortadan kopar (`</<tr>` gibi bozuk etiket) ve tablo bozulur.
```abap
FORM html_add USING iv_line TYPE string CHANGING ct TYPE soli_tab.
  DATA(lv_len) = strlen( iv_line ). DATA lv_off TYPE i.
  IF lv_len = 0. APPEND VALUE #( ) TO ct. RETURN. ENDIF.
  WHILE lv_off < lv_len.
    DATA(lv_take) = COND i( WHEN lv_len - lv_off > 255 THEN 255 ELSE lv_len - lv_off ).
    APPEND VALUE #( line = iv_line+lv_off(lv_take) ) TO ct.
    lv_off = lv_off + lv_take.
  ENDWHILE.
ENDFORM.
```
- Yorum "bu FORM böler" dese bile kaynağı doğrula (vaka: bölmüyordu). `SO_DOCUMENT_SEND_API1` HTM gövdeyi ara satır
  eklemeden birleştirir → bölme görüntüyü bozmaz.
- `soli_tab` tip adı burada örnek; kullandığın tabloyu API imzasından doğrula.

**3.3 Hizalı tablo = `<table><td>`** (div/span/class değil) + sabit etiket kolonu genişliği + satır içi kenarlık.

**3.4 Sayı biçimi — yerel ayardan bağımsız, birime uygun.**
- Adet: tam sayı `|{ val DECIMALS = 0 }|` (canlı hata: 10 adet → "10.000").
- Miktar/KG/tutar: ondalık `|{ val DECIMALS = 3 }|` (alanın ondalığına göre).
- ⛔ `WRITE … TO` kullanma: yerel ondalık ayracını bozar. String template varsayılanı (nokta ondalık, gruplamasız) kanoniktir.

**3.5 Türkçe karakter.** Gövdede `<meta http-equiv="Content-Type" content="text/html;charset=utf-8">` + `contents_txt`
+ gönderen tipi `'B'` → gövde içi Türkçe genelde çalışır. ⚠ Kullanıcı tam adı ya da malzeme adı gibi metinler SAPconnect
kod sayfası dönüşümünde bozulabilir (`ı/ş` → `?`). Tam UTF-8 gerekiyorsa veriyi **ikili UTF-8 ek** olarak üret (§5).

## 4. Konu (`sodocchgi1-obj_descr`, CHAR50)
- **50'den uzun ya da Türkçe karakterli konu → `CL_BCS` + `set_message_subject( ip_subject = <string> )`** (§6; çekirdekte
  canlı: 95 karakter, `– İ Ş` bozulmadan saklandı ve dış alıcıya ulaştı). Aşağıdaki CHAR50 ve "ASCII tut" kuralları **yalnız**
  `SO_DOCUMENT_SEND_API1` / `create_document( i_subject )` yolu içindir.
- En kritik bilgi ve durum ibaresi (BAŞARILI/HATALI) **başta**; taşarsa `COND #( WHEN strlen( s ) > 50 THEN s(50) ELSE s )`.
- `Ş/İ` konu alanında kod sayfası riski taşıyabilir → kritik değilse konuyu ASCII tut, tam Türkçe gövdede.
- ⚠ Sabit genişlikli alan + `ALPHA = OUT`: `|{ f ALPHA = OUT }|` alan genişliğini koruyup sondaki boşlukları üretir →
  konu 50'yi aşıp kırpılır. `condense( |{ f ALPHA = OUT }| )`.

## 5. Ek dosya — kısa gövde + dosya
**Ne zaman:** 8+ kolonlu geniş tablo çoğu gelen kutusunda taşar → kısa HTML gövde + ek. İşlenecek veri → Excel; resmî arşiv → PDF.
- **PDF eki:** SFP form objesi olmadan, modelin yazdığı yerleşimle → `%sap-pdf-output` (üretim + §6'daki CL_BCS deseniyle
  `i_attachment_type = 'PDF'`). SFP formu varsa `forms-f1-help.md` §A.2 (`ls_formoutput-pdf`).

**5.1 Excel eki — yöntem (Türkçe güvenliği sırasıyla)**
1. `ZCL_EXCEL` (abap2xlsx, açık kaynak, standart değil) sistemde **kuruluysa** gerçek `.xlsx` (en temiz). Kurulu değilse
   kurmak Basis onayı ister — kurma.
2. Yoksa **MHTML (`.xls` olarak HTML, UTF-8 + BOM)** — canlı kanıtlı, arka planda güvenli (saf string, GUI/OLE yok). Varsayılan.
3. CSV/TXT + UTF-8 BOM: düz `string_to_soli` yetmez (Excel ANSI sanar) → kod sayfası dönüşümü + başa
   `cl_abap_char_utilities=>byte_order_mark_utf8`; ayraç `;`.

**5.2 MHTML `.xls` deseni (canlı kanıtlı)** — MHTML'de Excel head `<style>`'ı **okur** (3.1'in istisnası):
```html
<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:x="urn:schemas-microsoft-com:office:excel">
<head><meta http-equiv="Content-Type" content="text/html; charset=utf-8">
<style> .txt{mso-number-format:"\@";} .int{mso-number-format:"0";} .dec{mso-number-format:"0\.000";} </style></head>
<body><table>
  <tr><td class="txt" x:str="10000123">10000123</td>   <!-- metin: baştaki sıfır korunur -->
      <td class="int" x:num="492">492</td>              <!-- adet -->
      <td class="dec" x:num="3.000">3.000</td></tr>     <!-- KG -->
</table></body></html>
```
- HTML kaçışı şart (`& < > "`), önce `&`; malzeme adındaki inç işareti (`3/4"`) kaçışsız `x:str` özniteliğini kırar.
- Sayılar string template ile (§3.4). Gövde başına UTF-8 BOM (`EFBBBF`): `CONCATENATE lv_bom lv_body_x IN BYTE MODE`.

**5.3 `SO_DOCUMENT_SEND_API1` — `packing_list` ikinci satırı (canlı kanıtlı)**
```abap
DATA(lv_xstr) = <bom + mhtml → xstring>.
DATA(lt_hex)  = cl_bcs_convert=>xstring_to_solix( lv_xstr ).
APPEND |&SO_FILENAME=Stok_Listesi_{ sy-datum }.xls| TO lt_objhead.
APPEND VALUE #( transf_bin = space     head_num = 0  body_start = 1  body_num = lv_bodyln
                doc_type = 'HTM' ) TO lt_pack.
APPEND VALUE #( transf_bin = abap_true head_start = 1 head_num = 1  body_start = 1  body_num = lines( lt_hex )
                doc_size = xstrlen( lv_xstr ) doc_type = 'XLS'
                obj_descr = 'Stok Listesi' ) TO lt_pack.
CALL FUNCTION 'SO_DOCUMENT_SEND_API1'
  EXPORTING document_data = ls_hdr  commit_work = abap_true
            sender_address = CONV #( sy-uname ) sender_address_type = 'B'
  TABLES    packing_list = lt_pack  object_header = lt_objhead
            contents_txt = lt_body  contents_hex = lt_hex  receivers = lt_reci.
```
- `doc_type` CHAR3 → `.xlsx` sığmaz; MHTML'de `'XLS'` + `.xls` dosya adı.
- `doc_size = xstrlen( )` (gerçek bayt) → son SOLIX satırının dolgusu kırpılır (yoksa ek sonunda çöp bayt).
- ⛔ `commit_work = abap_true` yoksa "gönderildi" görünür ama hiç çıkmaz (en sık hata).

## 6. `CL_BCS` (yeni işler; kısmen canlı — çekirdekte ölçüldü, S/4 private 2025; kapsam aşağıda)
Kazanç: `packing_list` yok, tek `TRY … CATCH cx_bcs`, `cl_bcs_convert=>string_to_soli( )` 255'lik satırlara böler
(⚠ bölme ayrıca test edilmedi — uzun HTML gövde bu yoldan geçip doğru açıldı). Mevcut çalışan `SO_DOCUMENT_SEND_API1`
kodunu buna taşımak için dokunma.
```abap
TRY.
    DATA(lo_send) = cl_bcs=>create_persistent( ).
    DATA(lo_doc)  = cl_document_bcs=>create_document(
      i_type = 'HTM'                                   " RAW değil — istenmeyen satır sonu ekler
      i_text = cl_bcs_convert=>string_to_soli( iv_html )  i_subject = CONV #( iv_subject ) ).  " burada CHAR50
    lo_doc->add_attachment( i_attachment_type = 'XLS' i_attachment_subject = 'Rapor.xls'
                            i_att_content_hex = cl_bcs_convert=>xstring_to_solix( lv_xstr ) ).
    lo_send->set_document( lo_doc ).
    lo_send->set_sender( cl_sapuser_bcs=>create( sy-uname ) ).    " relay izin veriyorsa; teknik adres zorunluysa §1
    lo_send->set_message_subject( ip_subject = iv_long_subject ). " > 50 karakter / Türkçe konu (§4)
    lo_send->add_recipient( cl_cam_address_bcs=>create_internet_address( iv_email ) ).
    lo_send->send( ).
    COMMIT WORK.                                       " şart
  CATCH cx_bcs INTO DATA(lx).                          " job log; akışı kesme
ENDTRY.
```
- **Çekirdekte canlı ölçülenler:** HTM gövde + `PDF` eki (dosya adı `i_attachment_header = VALUE soli_tab(
  ( line = |&SO_FILENAME=<ad>.pdf| ) )` ile) · `set_message_subject` · teknik adres gönderen · `cl_sapuser_bcs` alıcı
  (SAP gelen kutusu) + internet adresi alıcı · `set_send_immediately( abap_true )`. Tam ekli örnek: `%sap-pdf-output`.
- ⚠ **Ölçülmeyen:** örnekteki `XLS` eki (o turda yalnız HTM gövde + PDF eki koştu). aXet'te hiçbiri ayrıca ölçülmedi.

Türkçe için en güvenli ek: `.xlsx` ya da BOM'lu ikili dosya — kodlama dosyanın içindedir, SAPconnect kod sayfasından bağımsızdır.

### 6.1 RAP içinden gönderim — `COMMIT` ayrı LUW'da
RAP handler/saver içinde `COMMIT WORK` yasaktır (`%sap-code-review` BE-26) ama `CL_BCS` `COMMIT`'siz göndermez. Kanonik
desen zaten yazılı: `%sap-rap` → `behavior-impl.md` §10 "Commit gerektiren klasik BAPI'yi RAP'ten çağırmak (ayrı LUW)"
(Remote-Enabled Z FM + `CALL FUNCTION '<Z_FM>' DESTINATION 'NONE'`; tuzakları orada). Mail için de aynısı: FM kendi
LUW'unda `send( )` + `COMMIT WORK` yapar, sonucu (mesaj tablosu) döner. FM `TABLES` parametresi → `fugr-fm.md` §2.1.
- Ölçüm bağlamı (çekirdek): unmanaged, strict olmayan BDEF'te static action (interaction phase) içinden. ⚠ strict/managed
  saver bağlamında ölçülmedi.

## 7. Kontrol listesi
- [ ] Gönderen politikası soruldu (§1): relay teknik adres istiyor mu? SOES'te 812/SendAsDenied geçmişi var mı?
- [ ] Gönderen `sy-uname` / tip `'B'` **ya da** zorunlu teknik adres (sabit SAP kullanıcısı yok, tip-değer uyumlu)
- [ ] Test maili yalnız kendine — test sisteminden de dışarı çıkabilir (§1.1)
- [ ] Alıcılar dinamik tablodan, `pasif <> 'X'`; alıcı yoksa atla + log
- [ ] Gövdede satır içi stil (head CSS sınıfı yok)
- [ ] `html_add` 255 karakter parçalı (tek atama yok)
- [ ] Hizalı tablo `<table><td>` + sabit etiket kolonu
- [ ] Adet tam sayı / KG ondalık; `WRITE … TO` yok
- [ ] Konu: `CL_BCS` `set_message_subject` (uzun/Türkçe serbest) **ya da** API1 yolunda ≤ 50 + ASCII; kritik bilgi + durum
      başta; `ALPHA = OUT` → `condense`
- [ ] RAP içinden gönderim → Remote-Enabled Z FM `DESTINATION 'NONE'` (§6.1)
- [ ] Gövde `charset=utf-8`; kritik metin bozuluyorsa ikili ek
- [ ] 8+ kolonlu tablo → gövde yerine ek dosya (§5); PDF eki → `%sap-pdf-output` ya da SFP formu (§5)
- [ ] `commit_work = abap_true` / `COMMIT WORK`
