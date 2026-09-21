# Yazmadan önce kontrol listeleri — CDS ve DDIC

> Kaynak: ekibin reviewer kontrol listeleri (CDS, domain/DTEL, yapı, tablo güncelleme, ambalajlama tüketimi); aXet'e uyarlandı.
> Kullanım: SAP'ye yazmadan önce ilgili bölümü madde madde geç; her madde için kanıt (dosya satırı, `adt_get` çıktısı, sorgu sonucu) yaz.
> **Seviye:** `BLOCKER` = karşılanmadan yazma · `WARNING` = yaz ama kullanıcıya raporla · `INFO` = tetikleyici.
> "Sanırım uygun" / "genelde böyle yapılır" kabul edilmez; kanıt yoksa madde karşılanmamıştır.
> ⚠ CLI yazma kapısının gömülü incelemesi bu listelerin **hepsini koşmaz** (hangi maddeleri koştuğu DOĞRULANMADI). Liste senin kontrolündür;
> önemli değişiklikten sonra `%code-review`. Bir kapının "PASS"i, arkasında o maddeyi ölçen bir kontrol olduğunu kanıtlamaz.

---

## 1. CDS (DDLS) — yaratma / güncelleme
| ID | Kontrol | Seviye | Referans |
|---|---|---|---|
| CDS-NAME | Ad paket `.rules.md` / `naming.md` §4.3 biçiminde | BLOCKER | `cds.md` §3.2 |
| CDS-TYPE | Tür belirlendi (classic / view entity / abstract entity) ve kural dalı ona göre | BLOCKER | `cds.md` §1.1 |
| CDS-SQLV-1 | Classic view'da `@AbapCatalog.sqlViewName` var; view entity'de **yok** | BLOCKER | `cds.md` §3.2 |
| CDS-SQLV-2 | `sqlViewName` biçimi `<GÖVDE>_V_<1-5>` ve ≤ 14 karakter; ilk aktivasyonda doğru (sonradan yeniden adlandırılamaz) | BLOCKER | `cds.md` §3.2 |
| CDS-LABEL | `@EndUserText.label` var, `master_language`'de, spesifikasyondan | BLOCKER | kesin yasak D |
| CDS-AUTH-1 | `@AccessControl.authorizationCheck` var | BLOCKER | `cds.md` §3.1 |
| CDS-AUTH-2 | Kaynaktaki standart view'lara **doğrudan** erişim var mı, `#CHECK` mi? Varsa çare/gerekçe | BLOCKER | `cds.md` §2 DCL-01 |
| CDS-DEPR | `@AbapCatalog.preserveKey` yok | WARNING | `cds.md` §3.1 |
| CDS-WIN | `OVER (PARTITION BY …)` yok (ölçülen sistemde aktive olmadı → ABAP'a al) | BLOCKER | `cds.md` §4 T9 |
| CDS-FROM-1 | Kaynak tablo/view'lar sistemde var; Z kaynak view'lar aktif | BLOCKER | `adt_get` |
| CDS-FROM-2 | Standart tablo alan adları hedef sistemde teyitli (eski sistemden kopya değil; alan adı ≠ DTEL adı) | BLOCKER | `cds.md` §3.3 |
| CDS-FROM-3 | Standart tablo yerine released CDS arandı; kullanılmıyorsa gerekçe kullanıcıya bildirildi; halef `#CHECK` + guard ise geçilmedi | WARNING | `cds.md` §2 DCL-02, §5 |
| CDS-FROM-4 | Classic view'da replacement tablosu (`DD02L-VIEWREF` dolu: `MSEG`, `MKPF`, `MBEW` …) yok → `nsdm_e_*` | BLOCKER | `cds.md` §2 NSDM-01 |
| CDS-CUR | CURR/QUAN alanlarında `@Semantics.amount.currencyCode` / `quantity.unitOfMeasure` doğru referansla | BLOCKER | `tables-structures.md` §3.3 |
| CDS-NS | Eski sistemden taşındıysa namespace ve alan rename'leri regex/kontrolle uygulandı; spesifikasyonda silinen alanlar kaynaktan çıkarıldı | BLOCKER | `cds.md` §3.4 |
| CDS-KEY | En az bir `key` alan | WARNING | `cds.md` §3.1 |
| CDS-AGG | `sum`/`count`/`max` varsa `group by`; UNIT/CUKY alanı aggregate edilmiyor, `group by`'da | BLOCKER | `cds.md` §4 |
| CDS-UNION | `union all` view entity: `EXISTS` yok · `@Semantics` yalnız ilk dalda · `@Metadata.ignorePropagatedAnnotations: true` · dallar tip/sıra hizalı | BLOCKER | `cds.md` §4 T4 |
| CDS-CONVEXIT | Conversion exit'li alan OData'ya açılıyorsa: salt-okunur → cast; yazılabilir → exit'siz Z DTEL (kullanıcı kararı) | BLOCKER | `cds.md` §4 T5 |
| CDS-QTYEXPR | Quantity/amount alanı ifadede cast ile semantiği sıyrılmış | BLOCKER | `cds.md` §4 |
| CDS-CONSUME | BO'suz salt-okunur tüketim view'ı `as select from`; `as projection on`, `root`, `redirected to` yok | BLOCKER | `cds.md` §4 T3 |
| CDS-FIELDRM | Alan kaldırma/rename: tüketiciler ölçüldü; sıra (tüketici önce) ya da `also` ile atomik aktivasyon ya da ekle→çevir→sil planı yazılı | BLOCKER | `cds.md` §4 T6/T11 |
| CDS-2PHASE | Alt view key değişimi + tüketici JOIN değişimi aynı turda değil (iki faz) | BLOCKER | `cds.md` §4 T6 |
| CDS-JOINCAST | JOIN ON'da cast/fonksiyon yok (köprü view); `numc` uzunluk değişimi `lpad` + eşit uzunluk cast | BLOCKER | `cds.md` §4 T8 |
| CDS-CONCAT | Ayraçlı birleştirmede `concat_with_space`; ifade çıktısıyla doğrulanacak | WARNING | `cds.md` §4 T12 |
| CDS-CURRCONV | `currency_conversion` DDIC-based view'da: `amount` kolon, kur tipi literal/parametre | BLOCKER | `cds.md` §4 T14 |
| CDS-CAPA | Kullanılan CDS fonksiyonunun desteği çalışan bir örnekle ya da canlı aktivasyonla kanıtlı (sürüm çıkarımı değil) | BLOCKER | `cds.md` §4 T9 |
| CDS-VERIFY | Yazma sonrası plan: `adt_get` içerik kıyası + `adt_inactive_objects` + (classic) satır sayımı | BLOCKER | `cds.md` §1.5 |

Bilinen kör noktalar: özyinelemeli CDS bağımlılığı (A → B → C → A) · çok dilli etiket tutarlılığı · analitik view'larda `@VDM` eksikleri.

---

## 2. Domain / data element
| ID | Kontrol | Seviye | Referans |
|---|---|---|---|
| DE-REUSE-1 | Önce released standart DTEL arandı; varsa yeni yaratılmıyor | BLOCKER | `naming.md` §5 |
| DE-REUSE-2 | Aynı işi gören mevcut Z DTEL/domain arandı (`adt_search_objects`); kopya yok | BLOCKER | `naming.md` §5 |
| DE-NAME | Domain `…_D_…`, DTEL `…_E_…`; ad önerisi canlıda kontrol edildi (varsa başka ad) ve **kullanıcı açıkça onayladı** (`%sap-dev` §6) | BLOCKER | `naming.md` §4.7 |
| DE-LANG | Oturum dili = `master_language`; yaratma sonrası metadata'dan `masterLanguage` okunacak | BLOCKER | kesin yasak D |
| DE-LABEL | 4 etiket (kısa ≤10 · orta ≤20 · uzun ≤40 · başlık ≤55) tam ve dolu | BLOCKER | `domain-dtel.md` §1.2 |
| DE-TEXT | Açıklama/etiket spesifikasyondan ya da eski sistemden; tahmin yok | BLOCKER | SAP çekirdeği |
| DE-DOM | Tip/uzunluk/ondalık doğru; sabit değer / değer tablosu gerekiyorsa tanımlı; çıktı uzunluğu formülü kontrol edilecek | WARNING | `domain-dtel.md` §3 |
| DE-BUILTIN | Built-in tipli DTEL'de `typeName` = tip adı (`DATS` …) | BLOCKER | `domain-dtel.md` §2 |
| DE-VERIFY | Aktivasyon öncesi/sonrası okuma: `typeName`, etiketler, tip | BLOCKER | `domain-dtel.md` §4 |
| DE-STD | Standart DTEL/domain'e dokunulmuyor; append alanı/DTEL adı önerilmiyor | BLOCKER | kesin yasak A |

---

## 3. Structure
| ID | Kontrol | Seviye | Referans |
|---|---|---|---|
| STR-NAME | `…_S_…` biçimi, ≤ 30 karakter | BLOCKER | `naming.md` §4.7 |
| STR-LABEL | `@EndUserText.label` var, `master_language`'de, dolu | BLOCKER | kesin yasak D |
| STR-FIELD-1 | Alanlar mümkünse DTEL'e bağlı (ilkel tip değil) | INFO | `naming.md` §5 |
| STR-FIELD-2 | Alan tipi Z/Y ya da `/ad-alanı/` ile başlayan tüm DTEL'ler sistemde var ve aktif (standart DTEL'ler bu satırın kapsamı dışında → STR-FIELD-3; Z tipli alan yapı/tablo tipiyse DTEL sayılmaz) | BLOCKER | yazma kapısı `check_struct_field_dtel_active.py` (artefaktlı ve artefaktsız `adt_struct_create`) · elle `adt_get` `dtel` |
| STR-FIELD-3 | Standart DTEL adları (`MANDT`, `ERNAM`, `ERDAT` …) doğru | BLOCKER | `adt_get` |
| STR-FIELD-4 | Büyük/küçük harf duyarsız mükerrer alan adı yok | BLOCKER | — |
| STR-CUR | CURR alanında nitelenmiş `@Semantics.amount.currencyCode`, referans alan aynı yapıda ve `@Semantics.currencyCode : true` işaretli | BLOCKER | `tables-structures.md` §3.3 |
| STR-UNIT | QUAN alanında nitelenmiş `@Semantics.quantity.unitOfMeasure`, referans alan `@Semantics.unitOfMeasure : true` işaretli | BLOCKER | `tables-structures.md` §3.3 |
| STR-DEPR | `@AbapCatalog.preserveKey` yok | WARNING | `cds.md` §3.1 |
| STR-COMMENT | DDL'de `//` yorum yok | BLOCKER | `tables-structures.md` §1.3 ③ |
| STR-SPEC | Spesifikasyonda silinen alanlar çıkarıldı, rename'ler uygulandı | BLOCKER | — |
| STR-VERIFY | Yazma sonrası yer tutucu kontrolü + `DD03L` alan sayısı planlı | BLOCKER | `tables-structures.md` §1.4 |

Bilinen kör noktalar: append yapı varlığı · pool/cluster ayrımı · çok dilli etiket tutarlılığı.

---

## 4. Z tablo — yeni ve güncelleme
| ID | Kontrol | Seviye | Referans |
|---|---|---|---|
| TBL-APPROVAL | (Yeni) alanlar + DTEL + anahtar + uzunluk + delivery class + data maintenance kullanıcıya gösterildi, **açık onay** alındı | BLOCKER | `tables-structures.md` §3.1 |
| TBL-NAME | `…_T_…` biçimi, ≤ 16 karakter | BLOCKER | `tables-structures.md` §3.1 |
| TBL-SOURCE | (Güncelleme) güncel DDL `adt_get` ile çekildi | BLOCKER | pull-before-edit |
| TBL-MANDT | `key mandt : mandt not null;` | BLOCKER | `tables-structures.md` §3.3 |
| TBL-ENH | `@AbapCatalog.enhancement.category` var | BLOCKER | `tables-structures.md` §3.3 |
| TBL-NOTNULL | `not null` yalnız anahtar alanlarda | WARNING | `tables-structures.md` §3.3 |
| TBL-DTEL | Yeni alanların DTEL'leri aktif; standart DTEL adları doğru; namespace'li DTEL tırnaksız küçük harf | BLOCKER | `tables-structures.md` §3.3 |
| TBL-CUR | CURR → CUKY referansı tabloda; nitelenmiş annotation + işaret | BLOCKER | `tables-structures.md` §3.3 |
| TBL-QUAN | QUAN → UNIT referansı tabloda; nitelenmiş annotation + işaret; miktar/tutar ayrımı DTEL veri tipinden | BLOCKER | `tables-structures.md` §3.3 |
| TBL-DROP | Mevcut alan siliniyor / rename / tip değişiyor mu? Evetse yazma yolu analizi + etki listesi + kullanıcı kararı | BLOCKER | `tables-structures.md` §3.4 |
| TBL-APPEND | Standart tabloya append eklenmiyor | BLOCKER | kesin yasak A |
| TBL-DLVCLASS | Delivery class değişiyor mu (genelde sabit kalmalı) | WARNING | — |
| TBL-MAINT | Data maintenance değişiyor mu | INFO | — |
| TBL-ORDER | Yeni iş alanı audit bloğunun üstünde; audit bloğu en sonda | WARNING | `tables-structures.md` §3.4 |
| TBL-SPEC | Spesifikasyondaki alan listesiyle (sayı, sıra) uyumlu | BLOCKER | — |
| TBL-VERIFY | Yazma sonrası içerik kıyası + `DD03L` alan sayısı + (yeniden yaratmada) `E071` silme kalıntısı planlı | BLOCKER | `tables-structures.md` §3.5 |

Bilinen kör noktalar: yabancı anahtar değişikliği etkisi · indeks/tamponlama değişikliği · append içeren tablo değişikliği.

---

## 5. Table type
*(Kaynakta ayrı liste yok; `tables-structures.md` §2'den türetildi.)*
| Kontrol | Seviye |
|---|---|
| Ad `…_TT_…`; satır tipi (yapı) sistemde aktif | BLOCKER |
| Yaratma sonrası `DD40L.ROWTYPE` dolu ve doğru yapı | BLOCKER |
| RFC/`TABLES` parametresinde yapı değil table type kullanılıyor | BLOCKER |
| Ek (2026-09-21, `table-types.md`): önce hazır standart tip arandı (ör. `BAPIRET2_T`); yeni tip gerçekten gerekli | WARNING |
| Ek: ad canlıda `exists:false` ölçüldü; ad, kısa metin, satır tipi, erişim türü ve anahtar kullanıcıya gösterilip açık onay alındı | BLOCKER |
| Ek: iki kanal readback — `DD40L` (ROWTYPE/DATATYPE, ACCESSMODE, KEYDEF, KEYKIND) **ve** ADT XML aynı şeyi söylüyor; biri boş biri dolu = FAIL | BLOCKER |
| Ek: `adt_ttyp_create` `ok:false` (ör. `row_type_empty_after_repair`, `readback_unmeasured`) "tamam" diye raporlanmadı | BLOCKER |
| Ek: tipi `TABLES` üzerinden içeride tam tipli parametreye devreden FM'e veren çağıran `WITH EMPTY KEY` değil `WITH DEFAULT KEY` kullanıyor (DDIC standart anahtar = `DEFAULT KEY`) | BLOCKER |

## 6. Lock object
*(Kaynakta ayrı liste yok; `lock-objects.md`'den türetildi.)*
| Kontrol | Seviye |
|---|---|
| Ad `E` + gövde; birincil tablo aktif; kilit parametreleri tablonun anahtarı | BLOCKER |
| Açıklama `master_language`'de | BLOCKER |
| Aktivasyon sonrası ENQUEUE_/DEQUEUE_ fonksiyonları var (aktivasyonsuz obje kullanılamaz) | BLOCKER |
| Kullanan kodda `foreign_lock` hatası ele alınıyor, DEQUEUE çağrılıyor | WARNING |

## 7. Mesaj sınıfı
*(Kaynakta ayrı liste yok; `message-class.md`'den türetildi.)*
| Kontrol | Seviye |
|---|---|
| `MESSAGE` yazmadan önce mevcut mesajlar okundu; uygun numara yeniden kullanıldı; satır içi literal yok | BLOCKER |
| Yeni mesaj metni ≤ 73 karakter, `master_language`'de, spesifikasyondan | BLOCKER |
| Yazılacak liste **nihai tam liste** (yerine yazma semantiği) | BLOCKER |
| Standart mesaj sınıfına dokunulmuyor | BLOCKER |

---

## 8. Ambalajlama talimatı tüketimi
| ID | Kontrol | Seviye | Referans |
|---|---|---|---|
| PACK-01 | Talimat içeriği released CDS ile okunuyor; `PACKKP`/`PACKPO`'ya ham SELECT yok | BLOCKER | `packing-instruction.md` PC-1 |
| PACK-02 | Belirleme standart FM ile (sarmalayıcı sınıf içinde); kendi condition tablosu okuması yok | BLOCKER | PC-2 |
| PACK-03 | Belirleme mantığı CDS'te yeniden yazılmamış | BLOCKER | PC-3 |
| PACK-04 | Kademe doğru: ① FM (malzeme + teslim alan, bugün) → ② en son oluşturulan talimat → ③ boş | BLOCKER | PC-4 |
| PACK-05 | Kasa malzemesi `LoadCarrierSystUUID` ile; "ilk P kalemi" gibi heuristik yok | BLOCKER | PC-5 |
| PACK-06 | Kasa-içi adet = kategori `I` ve malzeme eşleşen bileşenin hedef miktarı | BLOCKER | PC-6 |
| PACK-07 | Kasa sayısı `CEIL`; kasa-içi adet 0/boş → sonuç boş | BLOCKER | PC-7 |
| PACK-08 | Temel birim ≠ tüketen birim ise birim çevrimi CEIL'den önce | WARNING | PC-8 |
| PACK-09 | Belirleme liste yüklenirken bir kez (tekilleştirme + önbellek); miktar değişiminde yeniden okuma yok | BLOCKER | PC-9 |
| PACK-10 | Talimat numarası alfanümerik güvenli; "en son" tarihle, string sıralamayla değil | WARNING | PC-10 |
| PACK-11 | Yalnız görüntüleme; belge tablosuna yazma yok | BLOCKER | PC-11 |
| PACK-12 | FM imzası ve belirleme şeması canlı okundu | BLOCKER | PC-2 |
| PACK-13 | Z objeler adlandırma + `master_language` metin; standart obje değişmemiş | BLOCKER | PC-12 |

## Bu dosyada ÇIKARILAN / DEĞİŞTİRİLEN
- Validator/script adları, reviewer çıktı YAML şablonu, zincir/wiring durumu notları → alınmadı (aXet'te karşılığı yok); "kapı PASS'i ≠ madde ölçüldü" dersi başlıkta kaldı.
- Müşteri paketine özgü ad desenleri, teknik tasarım dokümanı araçları, ekran/kolon yerleşimi maddeleri (PACK-14) → genelleştirildi ya da çıkarıldı.
