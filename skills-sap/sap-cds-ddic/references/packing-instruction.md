# Ambalajlama talimatı (packing instruction) tüketimi — S/4

> Kaynak: ekibin ambalajlama talimatı tüketim standardı + operasyonel reçetesi (canlı okuma ile doğrulanmış veri modeli); aXet'e uyarlandı.
> **Kapsam:** LE-PAC ambalajlama talimatlarının (POP1/2/3) ve belirleme kayıtlarının (POF1/2/3) **salt-okunur** tüketimi — bir malzemenin
> hangi kasaya konduğu ve kasa başına kaç adet olduğu. Talimat tanımlama/değiştirme (POP/POF yazma) kapsam dışıdır.
> **Profil:** `s4_private`'ta ölçüldü. Released CDS varlığı **sistem bağımlıdır** — ölçülen sistemde vardı; web kaynakları "yok" diyebilir →
> `adt_get` ile canlı teyit et. `ecc`'de released CDS yoktur.
> Kontrol listesi: `checklists.md` §8.

---

## 1. Kurallar
| # | Kural | Güç |
|---|---|---|
| PC-1 | Talimat **içeriğini** (kasa + adet) released CDS `I_PackingInstructionHeader` / `I_PackingInstructionComponent` ile oku. `PACKKP`/`PACKPO`'ya ham SELECT yazma. | yasak (ham SELECT) |
| PC-2 | Talimat **belirlemesini** (malzeme [+ teslim alan] → talimat) standart FM `VHUPIBAPI_PACK_INST_FIND` ile yap (released sarmalayıcı sınıf içinde). Belirleme için released CDS/OData yok. | zorunlu |
| PC-3 | Belirleme mantığını (condition technique: erişim sırası + tarih geçerliliği) CDS'te yeniden yazma — kırılgan. | yasak |
| PC-4 | **Kademe:** ① FM (malzeme + teslim alan, tarih = bugün) → varsa o talimat; ② yoksa malzemenin **en son oluşturulan** (`CreationDate` en büyük) talimatı; ③ o da yoksa **boş**. | zorunlu |
| PC-5 | **Kasa malzemesi** = başlıktaki `LoadCarrierSystUUID` (ana ambalaj / yük taşıyıcı) ile eşleşen bileşenin `Material`'ı. "İlk kalem", "hedef = 1" gibi heuristik yok — SAP zaten işaretliyor. | zorunlu |
| PC-6 | **Kasa-içi adet** = `PackingInstructionItemCategory = 'I'` (ürün) **ve** `Material = <malzeme>` olan bileşenin `PackingInstructionItmTargetQty`'si. | zorunlu |
| PC-7 | **Kasa sayısı** = `CEIL(miktar / kasa-içi adet)`, küsürat yok. Kasa-içi adet 0/boş → sonuç boş (bölme hatası yok). | zorunlu |
| PC-8 | Kasa-içi adet **temel birimdedir** (`BaseUnitofMeasure`). Tüketen miktar farklı birimdeyse önce birim çevrimi (released birim CDS'i ya da `MARM` faktörü), sonra CEIL. | zorunlu |
| PC-9 | Belirlemeyi liste/kalem yüklenirken **bir kez** yap (farklı malzeme + teslim alan tekilleştirme + önbellek). Miktar değişiminde yeniden okuma yok, yalnız istemci aritmetiği. | yasak (her tuşta belirleme) |
| PC-10 | Talimat numarası (`POBJID`) **alfanümerik olabilir**. Sayısal varsayma; baştaki sıfırları yalnız saf sayısal olanlarda at; "en son" için string sıralama değil **tarih**. | zorunlu |
| PC-11 | Yalnız görüntüleme; belge tablolarına yazma yok. Yazma gerekiyorsa ayrı karar + kesin yasak B sırası. | zorunlu |
| PC-12 | Standart FM **çağırmak** serbest (okuma); standart obje değiştirmek yasak; Z objeler adlandırma + `master_language` metin. | zorunlu |

## 2. Veri modeli (canlı okuma ile doğrulandı)
| Katman | Nesne | Anahtar alanlar |
|---|---|---|
| İçerik başlık | `I_PackingInstructionHeader` (ham `PACKKP`; sözleşme `#PUBLIC_LOCAL_API`, association hedefi) | `PackingInstructionSystemUUID` (= `packnr`, anahtar) · `PackingInstructionNumber` (= `pobjid`) · **`LoadCarrierSystUUID`** (ana kasa bileşeni) · `CreationDate` · `LastChangeDate` · `_PackingInstructionComponent` |
| İçerik kalem | `I_PackingInstructionComponent` (ham `PACKPO`) | `PackingInstructionSystemUUID` · `PackingInstructionItemSystUUID` (= `packitemid`) · **`PackingInstructionItemCategory`** (`P` ambalaj/kasa, `I` ürün) · `Material` · **`PackingInstructionItmTargetQty`** · `BaseUnitofMeasure` |
| Belirleme | condition technique (released CDS yok) | `KAPPL = 'PO'` · `KSCHL = <projenin belirleme koşul türü — customizing'den oku>` · erişim ① `KOTP100` (`MATNR` + `KUNWE` teslim alan — sipariş veren değil — + `DATAB`/`DATBI`) ② `KOTP001` (`MATNR`; tesis yok) · `KNUMH` → `KONDP.PACKNR` (+ `PACKNR1..4` alternatif kademeler) · FM `VHUPIBAPI_PACK_INST_FIND` (grup `VHUPIBAPI`; çekirdek motor `VHUPOSEL_PACK_INST_DETERMINE`) |

- FM girdisi `I_KOMGP` (malzeme / teslim alan) + tarih + şema → çıktı `E_KONDP` (içinde `PACKNR`). **Tam imzayı ve belirleme şeması
  kimliğini build sırasında sistemden oku** (SE37/ADT, customizing `POF3`/`T682`); tahmin etme. CLI'de standart FM okuma sınırlı olabilir →
  `adt_search_objects` ile bul, gerekirse kullanıcıdan SE37 ekranını iste.
- Ölçülen örüntü: aynı malzeme, teslim alana göre **farklı** kasa-içi adet verdi (teslim alana özel kayıt 40, genel kayıt 100) → erişim sırası
  gereklidir; her talimatta iki `P` kalemi (kasa + ara ayraç) bulunabildi → "ilk P" yanlış kasa verir.

## 3. Uçtan uca okuma yolu
```
(malzeme, teslim alan, tarih = bugün)
 ① VHUPIBAPI_PACK_INST_FIND → PACKNR ?
      var → içerik
      yok → ② I_PackingInstructionComponent[ItemCategory = 'I', Material = malzeme]
              → başlıklardan CreationDate en büyük olan → PACKNR
      yok → boş (kasa yok)
 İçerik (PACKNR ile, released CDS):
   kasa-içi adet  = Component[ItemCategory = 'I', Material = malzeme].PackingInstructionItmTargetQty
   kasa malzemesi = Component[ItemSystUUID = Header.LoadCarrierSystUUID].Material
   kasa adı       = kasa malzemesinin metni (released ürün metni CDS'i)
   birim          = BaseUnitofMeasure
 Tüketen:
   kasa sayısı = CEIL( temel birime çevrilmiş miktar / kasa-içi adet )
```

## 4. Build reçetesi (öneri — tasarımda kesinleşir)
1. Sarmalayıcı sınıf (ör. `ZCL_SD001_PACK_SRC`): `get_packing( matnr, kunwe, date ) → { pobjid, crate_mat, crate_name, in_crate_qty, base_uom, source }`.
   İçeride FM → boşsa released CDS kademesi; farklı anahtarlar için iç tablo önbelleği (N+1 önle).
2. Tüketim view/entity (ör. `ZSD001_I_ITEM_PACKING`) → belge kalemine association; FM gerektiği için ABAP destekli (custom entity ya da function import).
3. Belirleme liste yüklenince bir kez; kasa sayısı istemcide `CEIL`.
Adlar paket `.rules.md`'ye göre kesinleşir; Z obje adını kullanıcı onaylar.

## 5. Tuzaklar
- **T1** Belirleme CDS'te taklit edilmez (erişim önceliği + tarih geçerliliği + `PACKNR1..4` kademesi) → FM (PC-3).
- **T2** Kasa ≠ ilk `P` (PC-5).
- **T3** `POBJID` alfanümerik; "en son"u string sıralama ile bulma (PC-4/PC-10).
- **T4** Hedef miktar temel birimde; çevir, sonra CEIL (PC-8).
- **T5** Her tuş vuruşunda belirleme yok (PC-9).
- **T6** Standart FM imzası build'de canlı okunur; şema kimliği customizing'den.
- **T7** Released CDS varlığı sistem bağımlı → `adt_get` ile teyit; olumsuz dönüşü kanıtsız kabul etme.
- Released CDS `#CHECK` taşıyorsa doğrudan okumada yetkisiz kullanıcıda 0 satır → `cds.md` §2 (CDS-DCL-01 örneği tam bu view'larla).

## Bu dosyada ÇIKARILAN / DEĞİŞTİRİLEN
- Sistem kimliği/client, projenin koşul türü adı, gerçek talimat numaraları, kasa/ürün malzeme numaraları, müşteri numarası → çıkarıldı ya da yer tutucu.
- Müşteriye özgü ekran, kolon ve servis yerleşimi (belge ekranı adları, kolon konumu, istemci kontrol adları) → çıkarıldı; genel build reçetesi kaldı.
- Gate adayı/validator önerileri → alınmadı.
