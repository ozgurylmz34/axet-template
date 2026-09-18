# Lock object (ENQU/DL)

> Kaynak: ekip ADT playbook'unun lock object bölümü; aXet CLI'ye uyarlandı.
> Adlandırma: `E` + paket gövdesi (`EZSD001_ORDER`; `%sap-dev` → `naming.md` §4.7). Lock object'ler zorunlu `E` önekini alır.
> **Karıştırma:** lock object = DDIC tanımı (ENQUEUE/DEQUEUE fonksiyonlarını üretir). SM12'deki enqueue **kilit kaydı** ayrı şeydir;
> onu silmek kesin yasak C'dir ve kullanıcı işidir (`%sap-adt-foundation` → `foundation-ops.md` §5).
> Ölçümler S/4HANA (`s4_private`) sistemde yapıldı.

---

## 1. CLI durumu
**Yaratma + aktivasyon CLI'de var (2026-09-13; çevrimdışı test edildi, canlı DOĞRULANMADI)** — `%sap-adt-foundation` →
`tool-catalog.md` → `adt_post_shell` (`enqu`) ve `adt_activate`:
1. Tasarımı (§2) kullanıcıya göster, onay al.
2. `cli adt_post_shell '{"object_type":"enqu","name":"EZSD001_ORDER","package":"<PAKET>","transport":"<TRANSPORT>","description":"<metin>","extra":{"primary_table":"ZSD001_T_ORDER","lock_fields":["MANDT","ORDER_NO"],"lock_mode":"E","allow_rfc":false}}' --sap-write ...`
   — ad `E` + Z/Y (kapı kabul eder); `ok:false` → retry etmeden `exists_after`.
3. Yaratma aktive etmez (§3 nüansı) → `cli adt_activate '{"name":"EZSD001_ORDER","object_type":"enqu"}' --sap-write ...`
   (tek-obje yolu; `also` içinde `enqu` desteklenmez).
4. §4 doğrulaması (ENQUEUE_/DEQUEUE_ üretildiği araçça doğrulanmaz — DOĞRULANMADI).

**Hâlâ araç yok:** lock object okuma (`adt_get` `enqu` yolu yok), değiştirme ve silme (katalogda `enqu` için silme yolu
tanımlı değil) · `adt_push_source` `enqu` → `unsupported_type` (kaynak metni yok). Bunları ve araç canlıda düşerse yaratmayı
kullanıcı SE11'de yapar; sen §4 ile doğrularsın. Önceki araç setinde silme aracı `E` önekini standart obje sanıp reddediyordu
(yanlış pozitif); aXet kapısı `E` + Z/Y'yi meşru sayar.

## 2. Tasarım (kullanıcıya gösterilecek)
| Alan | Değer |
|---|---|
| Ad | `EZSD001_<AD>` (kullanıcı onaylı) |
| Açıklama | `master_language`'de, spesifikasyondan |
| Birincil tablo | `ZSD001_T_<AD>` |
| Kilit modu | `E` exclusive (yazma; en yaygın) · `S` shared (okuma, çoklu okumaya izin) · `X` exclusive non-cumulative |
| Kilit parametreleri | tablonun anahtar alanları (ör. `MANDT`, `ORDER_NO`) |
| RFC'ye izin | spesifikasyona göre (`false` varsayılan) |

## 3. Protokol notları (teşhis; CLI `enqu` yolunun dayandığı reçete)
- URL deseni tablodan/DTEL'den **farklıdır**, `sources` alt yolu şart:

  | İşlem | URL |
  |---|---|
  | Yaratma | `POST /sap/bc/adt/ddic/lockobjects/sources?corrNr=<TRANSPORT>` |
  | Okuma / silme | `/sap/bc/adt/ddic/lockobjects/sources/<ad>` |
  | Aktivasyon | `POST /sap/bc/adt/activation?method=activate&preauditRequested=true`, referans `uri=/sap/bc/adt/ddic/lockobjects/sources/<ad>`, `type=ENQU/DL` |

  `/sap/bc/adt/ddic/lockobjects/<ad>` (`sources` olmadan) → **404**.
- `Content-Type: application/vnd.sap.adt.lockobjects.v1+xml; charset=utf-8`; `sap-language` = `master_language`.
- Gövde:
  ```xml
  <enqu:lockobject xmlns:enqu="http://www.sap.com/adt/ddic/enqu" xmlns:adtcore="http://www.sap.com/adt/core"
                   adtcore:name="EZSD001_ORDER" adtcore:description="<metin>" adtcore:masterLanguage="<ML>">
    <adtcore:packageRef adtcore:uri="/sap/bc/adt/packages/<paket>" adtcore:type="DEVC/K" adtcore:name="<PAKET>"/>
    <enqu:content>
      <enqu:allowRFC>false</enqu:allowRFC>
      <enqu:primaryTable>
        <enqu:tableName>ZSD001_T_ORDER</enqu:tableName>
        <enqu:lockMode>E</enqu:lockMode>
      </enqu:primaryTable>
      <enqu:secondaryTables/>
      <enqu:lockParameters>
        <enqu:lockParameter>
          <enqu:parameterWanted>true</enqu:parameterWanted>
          <enqu:parameterName>MANDT</enqu:parameterName>
          <enqu:tableName>ZSD001_T_ORDER</enqu:tableName>
          <enqu:fieldName>MANDT</enqu:fieldName>
        </enqu:lockParameter>
        <!-- ORDER_NO için aynı blok -->
      </enqu:lockParameters>
    </enqu:content>
  </enqu:lockobject>
  ```
- Aktivasyon başarısı (HTTP koduna bakma): hüküm tek kaynaktan, `sap_adt_lib.aktivasyon_govde_hukmu` → `True` yalnız
  `activationExecuted="true"` ve E/A mesajı yokken. Dizi araması yetmez: aynı gövdede `type="E"` olsa da
  `activationExecuted="true"` geçebilir. Gövde hüküm taşımıyorsa (`None`: yalnız generation ya da bayraksız gövde) bağımsız
  worklist sondası (`aktivasyon_worklist_sondasi`, hedef `ENQU/DL`) karar verir; sonda ölçemezse sonuç başarı DEĞİLDİR.
  Araç yolu (`adt_activate` kilit objesi dalı) bunu kendisi yapar (`tests/test_verdict_activation.py` `TabloEnqu`).
- **Ölçülmüş nüans (yarat → sil denemesiyle canlı doğrulandı):** yaratma çağrısı `200` yazdı, `masterLanguage` doğruydu, ama
  yaratma **aktive etmez** → obje `version="inactive"`, `<enqu:lockModules/>` **boş**, ENQUEUE_/DEQUEUE_ fonksiyonları **üretilmemiş**
  = kullanılamaz. Yaratmadan sonra ayrı aktivasyon şart. Bayat CSRF önbelleği 403 verdi.

## 4. Doğrulama
1. Aktivasyon sonrası üretilen fonksiyonlar var mı: `cli adt_search_objects '{"query":"ENQUEUE_EZSD001_ORDER","max_results":5}'`
   ve `DEQUEUE_…` (tip filtresi vermeden; hangi ADT tip koduyla döndüğü DOĞRULANMADI). `count:0` "yok" kanıtı değildir → kullanıcıdan SE11/SE37 teyidi.
2. `adt_inactive_objects` → lock object listede değil.
3. Kullanıcıya SE11 açtırdıysan: "aç → yap → **KAPAT**" (açık ekran düzenleme kilidi bırakır, sonraki yazmayı bloklar).

## 5. Üretilen fonksiyonların kullanımı
Aktivasyonla SAP `ENQUEUE_<AD>` ve `DEQUEUE_<AD>` fonksiyonlarını yaratır. Parametre adları kilit parametrelerinden, mod parametresi
birincil tablodan türer (imzayı kullanmadan önce sistemde oku, tahmin etme):
```abap
CALL FUNCTION 'ENQUEUE_EZSD001_ORDER'
  EXPORTING
    mode_zsd001_t_order = 'E'
    mandt               = sy-mandt
    order_no            = lv_order_no
  EXCEPTIONS
    foreign_lock        = 1
    system_failure      = 2
    OTHERS              = 3.
IF sy-subrc <> 0.
  " kilit alınamadı: kullanıcıya mesaj (mesaj sınıfından), işlemi durdur
ENDIF.

" ... değişiklik ...

CALL FUNCTION 'DEQUEUE_EZSD001_ORDER'
  EXPORTING
    mode_zsd001_t_order = 'E'
    mandt               = sy-mandt
    order_no            = lv_order_no.
```

## Bu dosyada ÇIKARILAN / DEĞİŞTİRİLEN
- Toplu CSV script komutu, Python aktivasyon kodu → alınmadı; uç, tip kodu, gövde ve ölçülmüş aktivasyon nüansı kaldı. `extra` argüman biçimi (`lock_fields` dahil) `tool-catalog.md`'dedir.
- Deneme objesi adı, ortak paket adı, sistem client'ı → nötr demo/yer tutucu.
