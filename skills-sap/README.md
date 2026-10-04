# SAP skill'leri

`install.py --sap` bu klasörü `skills_paths`'e ekler. Her skill kendi klasöründe `<ad>/SKILL.md` olarak durur
(klasör adı = frontmatter `name`). `SKILL.md`'si olmayan klasör açılmaz (`doctor.py` FAIL verir); skill'ler arası
ortak referanslar yönlendirici skill'in `references/` klasöründedir.

| Skill | Ne zaman |
|---|---|
| `sap-intake-triage` | Yeni geliştirme / revizyon talebi: kapsam sınıfı S0/S1/S2, S2 intake artefaktı |
| `sap-dev` | Her SAP geliştirmesinin girişi: profil, paket, adlandırma (`references/naming.md`), ABAP desenleri (`references/coding-patterns.md`), standart veriye yazma API seçimi (`references/write-api-selection.md` — released RAP BO/EML → released BAPI → released OData → BAPI/RFC FM → BDC → manuel), ADT sırası |
| `sistem` | Projede aktif SAP sistemini gör / değiştir (DEV, QA, PRD — "client switch", "QA'ya geç"): `conn/` sistemlerini listeler, seçileni `switch_tier.py` ile etkinleştirir; dosya içeriği okumaz |
| `sap-adt-foundation` | SAP'de okuma, indirme, push, aktivasyon, silme, where-used, kilit, transport — tek CLI ve yazma kapısı |
| `sap-cds-ddic` | CDS view, domain, data element, structure, table, table type, lock object, mesaj sınıfı |
| `sap-rap` | RAP: view entity katmanları, BDEF, behavior sınıfı, servis tanımı/binding/publish, EML, draft ve kilit |
| `sap-classic-abap` | Klasik sınıf, program + include, fonksiyon grubu, rapor/ALV (şablonlarla), Dynpro, e-posta, form |
| `sap-odata-backend` | Klasik OData: SEGW, DPC_EXT/MPC_EXT, deep insert, function import, dış API çağrısı |
| `sap-code-review` | SAP backend değişikliğinin incelemesi: obje tipi kontrol listeleri, çevrimdışı kontroller (inceleme zinciri, abaplint, released halef haritası), bağımsız inceleyici brifingi |
| `sap-ui5-fiori` | UI5 freestyle (OData V2) ve Fiori elements ekranları: iskelet, grid/ALV paritesi, filtre, value-help, lokal çalıştırma, yalnız SAP'de duran uygulamanın kaynağını indirme + salt-okur yerel test, runtime doğrulama, BSP deploy (kullanıcı OK'u sonrası) |
| `sap-gui-scripting` | Veri yalnız SAP GUI ekranında görünüyorsa (ALV, tablo kontrolü, ekran alanı): model script yazar, geliştirici çalıştırır (ecc, s4_private) |
| `sap-abapgit-delivery` | Değişikliği abapGit ZIP olarak hazırla (kesin yasak + Yasak B taramasıyla); içe aktarımı geliştirici yapar |
| `sap-fs-ts-docs` | FS/TS/**KD (kullanıcı kılavuzu)** yazımı ve incelemesi — KD kuralları (`references/kd-authoring.md`) ve şablonu (`templates/KD-template.md`) burada; izlenebilirlik ve veri kaybı kontrolü, ekran görüntülü HTML/PDF, TS öncesi canlı teyit turu |
| `sap-ui5-user-guide` | Freestyle UI5 (OData V2) uygulamasının ekran görüntülü kullanıcı kılavuzu (KD): yalnız mock veri, Chrome'a sabit playwright-cli keşfi, çekim senaryosu, kare kare görsel kontrol; KD metni ve HTML + PDF `sap-fs-ts-docs` hattıyla |
| `sap-pdf-output` | SFP form objesi olmadan ABAP'ten PDF (yalnız `s4_private`): AI'ın yazdığı XFA XDP + `CL_FP_ADS_UTIL=>RENDER_PDF`, çok belge → tek PDF, CL_BCS mail eki; XDP denetçisi, bağlama simülasyonlu XDP → ABAP üreticisi, deneme sınıfı + base64 çözücü. SFP form, NAST/OM, yasal çıktı `sap-classic-abap`'ta |

**KD (kullanıcı kılavuzu) nerede?** Adı yalnız FS/TS'i ansa da KD'nin yazım kuralları, şablonu ve HTML/PDF üretimi
`sap-fs-ts-docs`'tadır (ad, mevcut atıflar bozulmasın diye korunur). Freestyle UI5 (OData V2) uygulamasında mock veriyle
ekran çekimi `sap-ui5-user-guide`'dadır ve KD'yi yine `sap-fs-ts-docs` şablonuyla yazar. Klasik GUI ekranı (Dynpro/ALV)
için KD: `sap-fs-ts-docs` + `sap-classic-abap`.

aXet.code yerel MCP yapılandırmasını yok sayar (ölçüldü). SAP işlemleri bu yüzden MCP ile değil,
`sap-adt-foundation` skill'indeki Python CLI ile yapılır.
