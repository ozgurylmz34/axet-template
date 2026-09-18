# Klasik ABAP hata indeksi — belirti → nereye bak

> Kaynak: ekip playbook'unun bilinen hatalar dosyasının klasik ABAP (sınıf/program/FM/Dynpro) maddeleri + obje tipi
> bölümlerindeki hata tabloları. ADT protokol hataları (412/423/409/400 corrNr, kilit, aktivasyon kanıtı) tekrar yazılmaz:
> `%sap-adt-foundation` → `references/known-errors-adt.md` (K-xx). **Kör retry yok**; önce maddeyi oku.

| Belirti / kod | Tip | Bak |
|---|---|---|
| `ResourceScanDuringSaveFailure` (400, satır yok) | sınıf | `classes.md` §2 · K-20 |
| `OO_SOURCE_BASED 012` "unknown comments which can't be stored" | sınıf | `classes.md` §3 |
| `"LS" was already declared with the type "%_##OSQLC_…"` / FOR değişkeni tip çakışması | sınıf/program | `classes.md` §4 |
| "maximum possible number of places … 34 places" (`SUM` tutar) | sınıf/program | `classes.md` §4 |
| Test include'u boş, `adt_unit_run method_count:0` | sınıf | `classes.md` §5 |
| `ED 170` "… CCAU does not have any inactive version" (500) | sınıf | `classes.md` §5 |
| classrun "does not implement if_oo_adt_classrun~main" | sınıf | K-13 |
| classrun `400 Session Timed Out` | ekran/CUA üretimi | `dynpro-gui-status.md` §1 · K-14 |
| `423` class push, obje transportta kayıtlı | sınıf | K-03 (412 ise K-01) |
| "The REPORT/PROGRAM statement is missing, or the program type is INCLUDE" | include | K-11 · `%sap-adt-foundation` foundation-ops §4.2/§4.3 |
| `Include not found` | program | K-12 |
| "The SELECT-OPTION name … can be up to eight characters long" | program | `programs-includes.md` §2 |
| "Field VBRP-VBELN is unknown" (`SELECT-OPTIONS … FOR tablo-alan`) | program | `programs-includes.md` §2 |
| "The field TEXT-B01 cannot be modified" | program | `programs-includes.md` §2 · K-21 |
| "The data object SCREEN does not have a component called TEXT" | program | `programs-includes.md` §2 |
| "The formal parameter SALV_TABLE does not exist" | program | `programs-includes.md` §2 |
| "already declared" blok `TITLE` değişkeni | program | `programs-includes.md` §2 |
| Seçim metni/blok başlığı ekranda yok, aktif sürümde `=?` | metin havuzu | `programs-includes.md` §3 |
| `406 DS512 "Text elements contain errors"` · `400 SADT_RESOURCE 017` · `423 SADT_RESOURCE 026` | metin havuzu | `programs-includes.md` §3 |
| `400 Parameter comment blocks are not allowed` | FM | `fugr-fm.md` §2 · K-15 |
| `400 FUNC_ADT 015 Parameter <P> declares no type` | FM | `fugr-fm.md` §2.1 |
| `FL 387 Type <X> is not a table type` (RFC işaretlenince) | FM | `fugr-fm.md` §2.1 |
| `500 CTS_WBO_API 020` "… talebinde bloke edildi" (FM push) | FM | `fugr-fm.md` §2.2 (görev yerine istek numarası) |
| FM push `423 InvalidLockHandle` | FM | `fugr-fm.md` §2.2 · K-15 |
| `400 "Unexpected Case in Branch"` (FM yaratma) | FM | `fugr-fm.md` §3 |
| BAPI CREATE numara döndü, COMMIT 200, tabloda satır yok | SOAP-RFC | `fugr-fm.md` §3.1 |
| SOAP-RFC cevabında `RETURN` yok, "hatasız" | SOAP-RFC | `fugr-fm.md` §3.2 |
| FUGR hedefinde `adt_grep_source match_count:0` | FM | `fugr-fm.md` §4.1 |
| `00256 "Geçerli bir işlev seçin"` | GUI status | `dynpro-gui-status.md` §3 |
| `00264 "GUI status … not generated"` | GUI status | `dynpro-gui-status.md` §3 |
| RABAX `mandatory parameter BIV` | GUI status | `dynpro-gui-status.md` §3 |
| Butonlar/F3 tepkisiz, ekranda `&F2..&F5` | GUI status | `dynpro-gui-status.md` §3 |
| Başka ekranın status/başlığı kayboldu | GUI status | `dynpro-gui-status.md` §3 (CUA merge) |
| Toolbar butonu kayboldu / etiketi değişti | GUI status | `dynpro-gui-status.md` §5.1, §5.2 |
| ALV pencereyi doldurmuyor | ekran | `dynpro-gui-status.md` §4 |
| rc=6 `illegal_field_value` | ekran | `dynpro-gui-status.md` §4 · `dynpro-dialog-fields.md` §1.2 |
| Alan etiketsiz | diyalog ekranı | `dynpro-dialog-fields.md` §1.1 |
| F4 yanlış alanı dolduruyor / F4 değişikliği ekrana inmiyor | diyalog ekranı | `dynpro-dialog-fields.md` §2.2 |
| "actual parameter incompatible" (`FORM … USING` container) | program | `alv-report.md` §6 |
| ALV'de çift tık/hotspot yanlış satırı okuyor | ALV | `alv-report.md` §4 |
| Önceki komut PAI'de tekrar tetikleniyor | ekran | `alv-report.md` §5 |
| Mail "gönderildi" ama çıkmadı | e-posta | `email.md` §5.3 (`commit_work`) |
| Mail tablosu bozuk (`</<tr>`) / stil yok | e-posta | `email.md` §3.1, §3.2 |
| F1 satır sonu kırpılıyor / başlık boş | F1 yardımı | `forms-f1-help.md` §B.2, §B.5 |
| GUI metinleri yanlış dilde | ekran/CUA | `dynpro-gui-status.md` §1 |
| syntax check hata dedi, aktivasyon geçti | genel | K-26 |

**Genel:** "araç bozuk" demeden kontrol grubu kur (çalışan obje ↔ patlayan obje; ekseni doğru seç) ve tanıdık semptomda
önce `%recall` + paket notları — `%sap-adt-foundation` → `known-errors-adt.md` G-1…G-6.
