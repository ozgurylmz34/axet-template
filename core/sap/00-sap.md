# SAP / ABAP Paketi — Kesin Kurallar
SAP-CORE-ID: AXET-SAP-0.5.0

> `scripts/install.py --sap` ile yüklenir. Sistem, `master_language`, paket ve transport bilgisi proje `AGENTS.md`'sindedir.

## ⛔ KESİN YASAKLAR — bypass yok, istisna yok

| Kategori | Yasak |
|---|---|
| **A — Standart SAP objeleri** (Z/Y ile başlamayan) | Hiçbir şekilde yaratılmaz/değiştirilmez/silinmez: append yapı, alan ekleme, standart FM/BAdI/program ve mesaj sınıfı değişikliği dahil. Bunu yapan script de çalıştırılmaz. **Standart objeye eklenecek append yapı / append alanı / DTEL adını sen önermezsin — kullanıcı belirler.** (Z DDIC adları — domain, DTEL, tablo, yapı, tablo tipi — bu yasağın dışındadır: önce hazır/standart DTEL'i değerlendir, değilse adlandırma standardına uygun ad öner, her adı canlı sistemde kontrol et (varsa başka ad), kullanıcının açık onayı olmadan yaratma.) |
| **B — Standart tablo verisi** | Doğrudan `INSERT/UPDATE/DELETE/MODIFY` yok (Z program içinde yazılan kodda bile). Sıra: BAPI → RFC FM → işlem kodu (BDC) → kullanıcıdan manuel. |
| **C — Sistem durumu** | Transport yaratma/release, paket yaratma, enqueue kilidi silme yok. |
| **D — Z obje yaratma** | Oturum dili = projenin `master_language`'i. 4 alan etiketi (kısa/orta/uzun/başlık) o dilde ve TAM yazılır; başlık/açıklama boş bırakılmaz; aktivasyon öncesi sistemden okunarak doğrulanır. |

**Yapılması gerekiyorsa:** DUR → AÇIKLA → ÖNERİ SUN → KULLANICIDAN İSTE → BEKLE → DEVAM. "Küçük dokunuş" istisnası yok.

**Örnek (A):** "standart tabloya/CDS'e alan ekle" → DUR. Append yapı ya da `EXTEND` önerme, DTEL adı önerme; Z adlı bir DDLS'e `extend view <standart CDS>` yazmak da standart objeyi genişletmektir. Clean-core yolu: Custom Fields (Fiori) — kullanıcı yapar.

## SAP çalışma disiplini
- **Tetik cümleleri (duyunca DUR, yasak tablosuna bak):** A — "standart tabloya alan ekle", "VBAK'a custom field", "append yarat" · B — "VBAK'a kayıt ekle", "T001'i güncelle" · C — "yeni transport aç", "transport release et", "yeni paket yarat", "kilidi sil" · D ihmali — Z obje etiketi başka dilde ya da boş.
- Transport ve paket kullanıcıdan gelir; yoksa sor. İş bir transporta bağlıysa aynısıyla devam et, yeni isteme.
- SAP'deki bir kaynağı değiştirmeden ÖNCE — analize başlamadan — güncel hâlini sistemden çek; yereldeki kopya bayat olabilir.
- Yükleme/aktivasyon "başarılı" dese de (HTTP 200 sahte-OK verebilir) sonucu sistemden tekrar okuyarak doğrula.
- Z obje açıklamalarını ve metinlerini tahmin etme; spesifikasyondan ya da eski sistemden al.
- Eski sistemden kopyalanan standart tablo/alan adlarını hedef sistemde teyit et.
- Clean core: released API/CDS varsa onu kullan (ör. `MARA` yerine `I_Product`).
- Yeni DDIC tablo öncesi alanları, veri elemanlarını ve anahtarı kullanıcıya göster, açık onay al.
- Paket klasörü `<source_root>/<MODÜL>/<PAKET>/` (`new_package.py` kurar). Pakette çalışmadan önce `.rules.md` ve `SESSION_NOTES.md`'nin son kaydını oku; oturum sonunda kayıt ekle; pakete özgü karar (ad istisnası, bağımlılık, transport) netleşince `.rules.md`'ye yaz. İndirilen objeler obje tipine göre alt klasöre konur (`classes/`, `cds/`, `functions/`, `programs/` …).
- Z obje adı (tablo, program, sınıf, CDS …) ÖNERMEDEN önce — yalnız öneri istense ve paket söylenmese de — paketin `.rules.md` önek/adlandırma kuralını oku: paket söylenmediyse proje `AGENTS.md` aktif paketi, o da yoksa `<source_root>/*/*/.rules.md` (tek paket varsa o). Hafızadaki proje kuralıyla çelişirse ikisini de göster, hangisinin geçerli olduğunu kullanıcıya sor; birden çok aday paket varsa hangisi olduğunu sor.
- SAP bağlantı bilgisi proje kökündeki gitignore'lu dosyadadır: içeriğini okuma, sohbete yazma; script'ler okur.
- Ayrıntılı ADT yöntemleri SAP skill'lerindedir (`skills-sap/`); işlemden önce ilgili skill'i oku.

## Yazma yolu, veri ve kimlik bilgisi
- **Yeni talep = önce intake:** yeni geliştirme, revizyon, rapor, alan ya da ekran talebinde önce `sap-intake-triage` skill'ini uygula; kapsamı S0/S1/S2 diye sınıfla ve gerekçesini yaz. SAP'ye her yazma çağrısında kapsam beyan edilir; S2'de mutabakatlı intake artefaktı olmadan araç yazmaz. Kapsamı küçük gösterme; iş büyürse yeniden sınıfla.
- **SAP'ye yazma varsayılan KAPALI.** Yazma yalnız SAP araç script'inin yazma modu açıkça verildiğinde ve bağlantı DEV/sandbox olarak tanımlıysa yapılır; sistem tipi okunamıyorsa yazma yok. Kontrol script'in içindedir. Bir guard reddini aşmak için komutu değiştirme ya da başka yol arama: DUR ve kullanıcıya bildir.
- **Hassas veri (KVKK):** QA/PRD sistemde kişisel/hassas veri (müşteri/satıcı/adres `KNA1` `LFA1` `ADRC`, personel `PA*`, muhasebe `BSEG` `BKPF` `ACDOCA`, banka/IBAN, TCKN/VKN) okunmadan önce hangi tablo/alanın neden okunacağını söyle ve açık onay iste ("onay" gibi net bir kelime; "dene", "çek" onay değildir). DEV muaftır. Okunan veriyi gerektiği kadar göster; dosyaya ve hafızaya yazma.
- **Kimlik bilgisi kodda:** script yazarken/değiştirirken şifre ya da token hiçbir yola yazılmaz: hata ve yedek akışlar, teşhis/listeleme çıktısı, log, dönüş değeri dahil. Gerekiyorsa maskelenir.
- **Liste ekranı = ALV paritesi:** klasik ya da UI5 her liste/rapor ekranı, kullanıcı ayrıca istemese bile sıralama, operatörlü filtre, kolon göster/gizle, varyant ve Excel'e aktarma (ekrandaki sayfa değil, filtreye uyan tüm satırlar) sunar. UI5'te `sap.ui.table.Table` (grid) kullanılır; `sap.m.Table` yalnız mobil öncelikli istisnadır.
