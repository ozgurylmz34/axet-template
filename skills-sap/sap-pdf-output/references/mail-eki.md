# PDF'i mail eki yapmak — `CL_BCS`

> **Kanıt düzeyi:** aşağıdaki desen **çekirdekte canlı ölçüldü (S/4 private 2025, 2026-10-04)**: HTM gövde + PDF eki,
> `&SO_FILENAME` ile dosya adı, `set_message_subject` (95 karakter, Türkçe), teknik adres gönderen, internet adresi alıcı,
> `set_send_immediately`. aXet'te canlı **DOĞRULANMADI**. Genel mail kuralları (alıcı tablosu, HTML gövde tuzakları,
> Excel eki) bu skill'in konusu değildir → `%sap-classic-abap` → `references/email.md`.

## 1. Desen

```abap
DATA(lo_req) = cl_bcs=>create_persistent( ).
DATA(lo_doc) = cl_document_bcs=>create_document( i_type = 'HTM' i_subject = lv_kisa_konu   " CHAR50 keser
                 i_text = cl_bcs_convert=>string_to_soli( iv_string = lv_html_govde ) ).
lo_doc->add_attachment( i_attachment_type    = 'PDF'
                        i_attachment_subject = CONV #( lv_ek_adi_uzantisiz )
                        i_attachment_size    = CONV #( xstrlen( lv_pdf ) )
                        i_att_content_hex    = cl_bcs_convert=>xstring_to_solix( iv_xstring = lv_pdf )
                        i_attachment_header  = VALUE soli_tab( ( line = |&SO_FILENAME={ lv_dosya_adi }.pdf| ) ) ).
lo_req->set_document( lo_doc ).
lo_req->set_message_subject( ip_subject = lv_uzun_konu ).          " > 50 karakter konu
lo_req->set_sender( cl_cam_address_bcs=>create_internet_address( i_address_string = lv_gonderen ) ). " §2
lo_req->add_recipient( i_recipient = cl_cam_address_bcs=>create_internet_address( i_address_string = lv_alici ) ).
lo_req->set_send_immediately( abap_true ).
IF lo_req->send( ) = abap_true.
  COMMIT WORK.        " RAP içindeysen BURADA DEĞİL — §4
ENDIF.
```
Hepsini tek `TRY … CATCH cx_bcs` içine al; hatayı logla, akışı kesme. `i_type = 'HTM'` — `RAW` istenmeyen satır sonu ekler.

## 2. Gönderen — önce kurumun gönderen POLİTİKASINI sor
Gönderen adresi kodun değil kurumun kuralıdır: kurumsal relay (ör. Microsoft 365) çoğu kez yalnız yetkili bir **teknik
adresten** gönderime izin verir. SAP kullanıcısı gönderen yapılınca relay reddeder; SOES'te `XS 812` +
`554 5.2.252 SendAsDenied; <kimliği doğrulanan hesap> not allowed to send as <From>` görünür (çekirdekte canlı; aylardır
biriken 812'ler "test sisteminden mail çıkmaz" diye normal sayılmıştı).
- İşe başlarken gönderen politikasını kullanıcıya/Basis'e **sor** ve SOES geçmişinde 812/SendAsDenied var mı **bak**.
- Teknik adres zorunluysa `set_sender( cl_cam_address_bcs=>create_internet_address( … ) )`; adres projenin belgelenmiş tek
  yerinden (kaynağı yorumda yazılı sabit ya da bakım tablosu). Değilse `cl_sapuser_bcs=>create( sy-uname )`.
  Sabit SAP kullanıcı adı gömülmez. Ayrıntı: `%sap-classic-abap` → `references/email.md`, "Gönderen" bölümü.

## 3. Teslim teşhisi — SOST / SOES
| Durum | Anlamı |
|---|---|
| `XS 718` tip `I` (MSGV'de `250 2.1.5 Recipient OK`) | Relay kabul etti → dışarı çıktı (✅ çekirdek) |
| `XS 812` + `554 5.2.252 SendAsDenied` | Gönderen adres relay'de yetkisiz (§2) (✅ çekirdek) |
| `W` (bekliyor) | ⚠ ölçülmedi — aylarca `W`'de kalan kayıt ayrı teşhis ister (SCOT işi, node/adres eşleşmesi) |

- "Test sisteminden mail çıkmaz" VARSAYMA: çıkabilir. Bakım tablolarındaki alıcıları kontrol et; deneme mailini **yalnız
  kendine** gönder.
- SOST'ta HTML eki açarken çıkan SO596 yalnız SAP GUI görüntüleyicisinin ayıklamasıdır — mail engeli değil.

## 4. RAP'tan gönderim — COMMIT ayrı LUW'da
RAP handler/saver'da `COMMIT WORK` yasaktır, CL_BCS ise COMMIT'siz göndermez. Kanonik desen aXet'te yazılı:
`%sap-rap` → `references/behavior-impl.md`, "Handler'da yasak deyimler" bölümü, "Commit gerektiren klasik BAPI'yi RAP'ten
çağırmak (ayrı LUW)" maddesi — Z RFC-enabled FM + `CALL FUNCTION '<Z_FM>' DESTINATION 'NONE'`; FM kendi LUW'unda render +
`send( )` + `COMMIT WORK` yapar, sonucu mesaj tablosuyla döner. Çekirdek ölçüm bağlamı: unmanaged, strict olmayan BDEF'te
static action içinden (✅) — ⚠ strict/managed saver bağlamında ölçülmedi. Klasik program/job'da doğrudan `COMMIT WORK`.

## 5. Deneme koşusunda mail — tek istek, tekrar YOK
- Deneme sınıfında mail **varsayılan kapalı** (`gc_mail_acik = abap_false`). Açmak için: alıcı yalnız kullanıcının kendi
  adresi, gönderen politikası soruldu, içerik kullanıcı onaylı.
- ⛔ **Tekrar koşma:** `adt_classrun` 200 dışı yanıtta ve zaman aşımında isteği artık yeniden GÖNDERMEZ; sonuç
  `islenmis_olabilir: true` taşır (`%sap-adt-foundation` → `known-errors-adt.md` K-28; önceki sürümler 500'de 2, 502/503/504
  ve okuma zaman aşımında 4 istek gönderiyordu — yerel sahte sunucuda ölçüldü, SAP'ye karşı DOĞRULANMADI). Bu işaret
  "koşmadı" DEMEK DEĞİLDİR: mail açıkken görürsen **TEKRAR KOŞMA**; önce SOST/SOOD'a bak, gönderimin olup olmadığını oradan oku.
- Deneme sınıfında `COMMIT WORK` RAP bağlamı değildir (classrun) — sınıfta gerekçesi yorumla yazılıdır (`%sap-code-review`
  BE-26 "gerçek RAP dışı sınıf istisnası gerekçesiyle yazılır").
