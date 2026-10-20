# ECC (eski sistem) geliştirmesini S/4'te yeniden yazmak

> **Ne zaman:** bir ECC / eski sistem programı, raporu ya da arayüzü S/4'te karşılanacak; eski kaynak kod, tablo dökümü
> ya da üretim verisi referans olarak elde.
> **Temel ilke:** eski sistem **iş anlayışının** kaynağıdır, **tasarım şablonu DEĞİLDİR**. Neyin alınıp neyin
> alınmayacağı ve her tasarım kararındaki üç soru: `%sap-intake-triage` `references/protocol.md` §5 ("Eski sistem
> referansı") — burada tekrarlanmaz. Bu sayfa o ilkeyi TS'e girmeden önce **kontrol edilebilir** hâle getirir.
> **Profil:** hedef `s4_private` için yazıldı; `s4_public` / `btp_abap`'ta hedef zaten yalnız released API'dir.

## 1. Kaynak ≠ hedef
Eski kod sözdizimi bakımından modern görünebilir (yeni release, satır içi bildirim, CDS). Asıl kısıt **sözdizimi değil,
kullanılabilir API ve deyim yüzeyidir**: hedefte hangi standart obje released, hangi iş nesnesi hangi yolla yazılır
(`write-api-selection.md`), hangi klasik yapı bu projede kabul edilmiş bir yoldur (`%sap-classic-abap`).
"Derleniyor" ≠ "hedefe uygun".

Belgede ya da talepte "ECC ile aynı" / "eskisi gibi" ifadesi bir sinyaldir: bu bir **iş kuralı** mı (kalır) yoksa
**teknik seçim** mi (yeniden değerlendirilir)? Ayrım TS'te yazılı olmalıdır.

## 2. Yeniden yazım ön kontrolü (TS'e girmeden)
| ID | Kontrol | Not |
|---|---|---|
| **C-PORT-01** | Hedef **dil sürümü / katman** yazılı mı (klasik ABAP mı, ABAP Cloud mu) ve `sap-project.json` `cleancore_policy` ile uyumlu mu? | `%sap-code-review` `references/clean-core.md` §2.1 |
| **C-PORT-02** | Kullanılacak **her standart API/obje**nin released durumu **canlı ya da ATC ile** ölçüldü mü (doküman/hafıza tek başına yetmez)? | ATC "Usage of APIs" otoritedir (`clean-core.md` §5); ölçülmediyse TS'te `ölçülmedi` yazılır |
| **C-PORT-03** | Eski sistemdeki Z view/sınıf **kopyalanmadan** S/4 veri modeline göre yeniden modellendi mi (ör. replacement tablolar)? | Replacement tabloda sessiz 0 satır / 0 miktar: `%sap-cds-ddic` `references/cds.md` CDS-NSDM-01 |
| **C-PORT-04** | Released karşılığı **bulunamayan** her ihtiyaç, kod yazılmadan **açık boşluk** olarak FS/TS'e yazıldı mı (sessizce iç objeye düşülmedi)? | Karar kullanıcıyla verilir; standart objeye dokunma kesin yasak A |
| **C-PORT-05** | Paket ve transport **kullanıcıdan** alındı mı? | Kesin yasak C — AI yaratmaz, seçmez |

⚠ ABAP Cloud katmanına özgü kontroller (yasak deyim taraması, Cloud readiness ATC varyantı) yalnız hedef ABAP Cloud ise
koşulur; `s4_private`'ta klasik yol meşrudur (`clean-core.md` §7).

## Bu dosyada ÇIKARILAN / DEĞİŞTİRİLEN
- Kaynak: ekip çekirdeğinin ECC→S/4 yeniden yazım reçetesi. "Alınır / alınmaz" tablosu ve üç soru aXet'te intake
  protokolünde zaten vardı → oraya bağlandı, çoğaltılmadı; burada yalnız ön kontrol listesi yeni.
- Belge kapısı maddesi (TS'te eski sistem izi mi, S/4 standardı mı) `%sap-fs-ts-docs` kontrol listesi için ayrı öneridir; o listeye bu dosyayla birlikte eklenmedi.
