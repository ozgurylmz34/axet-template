---
name: sap-pdf-output
description: >
  Use to produce a PDF from ABAP without an SFP form object on S/4HANA on-premise (s4_private): the
  model writes an XFA 3.3 XDP layout plus sample XML data, a script embeds it into an ABAP method with
  a binding simulation, CL_FP_ADS_UTIL=>RENDER_PDF renders it, a classrun trial class prints the PDF as
  base64 for a local decode and visual check, optionally sent as a CL_BCS mail attachment; usable from
  classic programs and RAP. Triggers: "PDF üret", "PDF mail eki", "form olmadan PDF", "XDP", "toplu
  PDF", "sevk belgesi PDF". Do not use for SFP form or Adobe Designer maintenance, NAST or Output
  Management printing or legal output such as e-Fatura and e-İrsaliye (sap-classic-abap forms), or a
  plain HTML mail without a PDF (sap-classic-abap email).
---

# PDF çıktısı — form objesi olmadan (XDP + `RENDER_PDF`, + mail eki)

> **Profil:** yalnız `s4_private` (çekirdek `applies_to`). `sap-project.json` `sap_profile` başka bir değerse (`ecc`,
> `s4_public`, `btp_abap`) **DUR**, kullanıcıya bildir: `CL_FP_ADS_UTIL` erişimi orada ölçülmedi.
> Kesin yasaklar (A/B/C/D) SAP çekirdeğinde (`00-sap.md`) yüklüdür. Bu yolda SFPF/SFPI yaratılmaz, standart tabloya yazılmaz.
> ADT protokolü (kabuk, push, aktivasyon, silme, transport) → `%sap-adt-foundation`.

> **Özü (kırpılırsa bu kalsın):** ① Yol D **kullanıcının açık seçimi**dir (Designer bakımı yok, yasal çıktı değil)
> ② yerleşim `.xdp`, veri `.xml` dosyası repoda kaynaktır; ABAP kopyası **elle değil** `xdp_abap_uret.py` ile üretilir
> ③ render'dan önce `xdp_denetle.py` + bağlama simülasyonu ④ deneme koşusunda `ev_pages` + bayt + **PDF'i açıp gözle
> okumak** — "render başarılı" yerleşim kusurunu söylemez ⑤ mail dışa dönük iştir: varsayılan kapalı, deneme yalnız
> kullanıcının kendi adresine, zaman aşımında **tekrar koşma** ⑥ iş bitince deneme sınıfı ve script çıktıları silinir.

## When to use this skill
- Bir belge (sevk belgesi, sipariş özeti, iç rapor) **PDF** olarak üretilecek — çoğu kez mail eki — ve SFP form objesi yok,
  Designer'da layout çizecek operatör de yok.
- Birden çok belge **tek PDF**'te gidecek (toplu PDF: belge başına yeni sayfa, belge içi "Sayfa n / N").
- Var olan bir XDP şablonunda kolon kayması, kesik metin, Türkçe glif, büyük harf `İ` sorunu.
- Çağıran klasik program/job ya da RAP olabilir (RAP'tan gönderimde ayrı LUW: `references/mail-eki.md` §4).
- **Kullanma:** SFP form/interface, Adobe Designer bakımı, NAST/Output Management'tan basım, yasal çıktı
  (e-Fatura/e-İrsaliye) → `%sap-classic-abap` (`references/forms-f1-help.md`) ·
  PDF'siz düz HTML mail → `%sap-classic-abap` (`references/email.md`) · yeni talebin ilk ele alınışı → `%sap-intake-triage`.

## How to use this skill
Yollar: `S=<TEMPLATE>/skills-sap/sap-pdf-output/scripts`, `T=<TEMPLATE>/skills-sap/sap-pdf-output/templates`, `P=<paket klasörü>`.
Bir adımın çıkış ölçütü tutmadan sonrakine geçilmez.

1. **Yol kararı + kapsam (kullanıcıyla).** Yol D seçimini kullanıcının cümlesiyle kaydet (AF-XDP-01): Designer bakımı
   olmayacak, yasal çıktı değil, NAST/OM yok. Kapsam: beklenen sayfa sayısı, barkod, Türkçe, tekrarlı bloklar, tek/çok
   belge, mail var mı. ADS ayakta mı (`references/recete.md` §1 ön koşul). Obje/paket/transport adı kullanıcıdan (`%sap-dev`).
2. **XDP + örnek veri.** `$T/tek-belge.xdp` ya da `$T/cok-belge.xdp` + eşleşen veri XML'inden başla, `P/` altına kopyala
   (repoda kaynak). Örnek veri gerçek veri biçiminde ve **en kötü durumda**: uzun ad, çok satır, Türkçe glif, en uzun numara.
   Kurallar: `references/recete.md` §3 (bağlama), §4 (çok belge), §5 (tuzaklar).
3. **Denetim.** `python $S/xdp_denetle.py <x.xdp> --locale tr_TR` → HATA 0; her UYARI ya düzeltilir ya gerekçesi
   kullanıcıya yazılır; XDP-04 listesi tek tek okunur; BİLGİ satırları okunur (kasıtlı sarılan satır mı?).
   Çıktının KAPSAM BEYANI neye bakmadığını söyler (render, sayfa kırılımı, barkod).
4. **ABAP'a göm + deneme sınıfı.** `$T/deneme-classrun.clas.abap`'ı kopyala, `ZCL_<GÖVDE>_PDF_DENEME` adını kullanıcıdan al →
   `python $S/xdp_abap_uret.py --xdp <x.xdp> --veri <x.xml> --abap <sınıf dosyası> --veri-gom` (bağlama hatası varken
   yazmaz). Push'tan önce şablondaki ölçülmemiş imzaları (`encode_x_base64`, `ev_trace_string`) `adt_get` ile oku →
   `%sap-adt-foundation` ile kabuk → push → aktivasyon → `adt_inactive_objects` + geri okuma.
5. **Tek koşu.** `adt_classrun` çıktısını dosyaya kaydet → `python $S/pdf_coz.py <çıktı> --pdf <x.pdf>` → bayt ve sayfa
   kıyası (`pypdf` yoksa sayfa "ÖLÇÜLEMEDİ"; ham `/Type /Page` sayımı hüküm değildir). **PDF'i aç ve gözle oku:** sayfa
   sayısı, kolon kayması, kesik metin, glifler, barkod, büyük harf `İ`. Bulgu listesini kullanıcıya göster.
6. **Düzeltme turları (v2, v3 …)** aynı sınıfla: `.xdp`'yi düzelt → 3 → `xdp_abap_uret.py` (yeniden üret) → push → 5.
   Her turda `--check` güncel (üretimdeki bayraklarla — veri gömülüyse `--veri-gom --check`; atlanan blok DENETLENMEDİ = çıkış 1). Kullanıcı PDF'i onaylar.
7. **Mail (varsa).** `references/mail-eki.md`: gönderen politikasını **sor**, alıcı/içerik onayı al, deneme yalnız
   kullanıcının kendi adresine (`gc_mail_acik`, `gc_test_alici`). Koşu zaman aşımı/500 verirse **TEKRAR KOŞMA** → SOST/SOOD.
8. **Ürünleştirme tasarımı (kullanıcıyla).** XDP'nin yeri (sınıf metodu ölçüldü; MIME / Z tablo ölçülmedi), gerçek veri →
   veri XML eşlemesi (`ALPHA = OUT` tuzağı), çok belge, hata yolu (ADS kapalıysa ne olur), RAP'tan çağrıda ayrı LUW.
   Ürün sınıfında `get_xdp` yine üreticiyle yazılır; `--veri-gom` kullanılmaz.
9. **Temizlik + kapanış.** Deneme sınıfı silinir (kişisel test adresi taşıyabilir), yereldeki deneme `.pdf` ve classrun
   çıktıları silinir. `references/kontrol-listesi.md` satır satır → `%sap-code-review` → `%verify-done` → paket `SESSION_NOTES.md`.

## Önce oku — referanslar, şablonlar, script'ler
| Dosya | Ne zaman | İçerik |
|---|---|---|
| `references/recete.md` | her işte | yol seçimi, API, XDP iskeleti ve bağlama kuralları, çok belge, tuzaklar, ölçülmemişler |
| `references/mail-eki.md` | adım 7, RAP'tan çağrı | CL_BCS PDF eki, gönderen politikası, SOST/SOES teşhisi, ayrı LUW, tek istek kuralı |
| `references/kontrol-listesi.md` | adım 1, 9 | AF-005 + AF-XDP-01..07 ve her satırın nasıl ölçüldüğü |
| `templates/tek-belge.xdp` · `templates/tek-belge-veri.xml` | adım 2 | tek belge iskeleti (başlık, Code39, kalem tablosu 191/192, toplam, sayfa no) + kurgusal veri |
| `templates/cok-belge.xdp` · `templates/cok-belge-veri.xml` | adım 2 | `DOC` sarmalayıcı, belge başına yeni sayfa, belge içi "Sayfa n / N" + 2 belgelik veri |
| `templates/deneme-classrun.clas.abap` | adım 4 | `IF_OO_ADT_CLASSRUN` deneme sınıfı: render, `EV_PAGES`/`PDF_BAYT`/iz, işaretli base64, mail (kapalı) |
| `scripts/xdp_abap_uret.py` | adım 4, 6, 8 | bağlama simülasyonu + XDP/veri → ABAP metodu (ters tırnak, ≤ 255) · `--check` |
| `scripts/xdp_denetle.py` | adım 3 | XDP-03 kolon toplamı · XDP-04 `İ` · XDP-05 font/locale · R-3.7 `layout:ready` · R-3.3 sabit `h` |
| `scripts/pdf_coz.py` | adım 5 | işaretler arası base64 → PDF, bayt ve `pypdf` sayfa kıyası |
| `%sap-classic-abap` → `references/email.md` | adım 7 | genel mail kuralları, "Gönderen" ve "`CL_BCS`" bölümleri |
| `%sap-rap` → `references/behavior-impl.md` | RAP'tan çağrı | "Handler'da yasak deyimler" — ayrı LUW deseni (RFC FM + `DESTINATION 'NONE'`) |
| `tests/test_skill_structure.py` | skill değişince | frontmatter, atıfların varlığı, iz taraması |

Şablonlar SAP'de **derlenmedi / render edilmedi** (aXet'te ölçülmedi); çekirdekte canlı ölçülen desenden türetildi.
Script'ler SAP'ye bağlanmaz, yalnız Python standart kütüphanesini kullanır (`pypdf` isteğe bağlı), her koşuda KAPSAM basar.

## Rules
- **Tahmin yok:** XFA öğesi/özniteliği, ABAP imzası, alan adı reçeteden, şablondan ya da sistemden okunur; şablonda
  "ölçülmedi" denen imza push'tan önce hedef sistemde okunur. Çekirdeğin "⚠ ölçülmedi" işaretleri genişletilmez.
- Yol D yalnız kullanıcının açık seçimiyle açılır; SFPF/SFPI programatik yaratılmaz (Yol A kullanıcı kararıdır, denenmedi).
- XDP'nin ABAP kopyası elle düzenlenmez; `.xdp` değişince üretici yeniden koşar, `--check` güncel değilse push yok.
- "Render başarılı" / "classrun ok" kanıt değildir: `ev_pages` beklenenle aynı **ve** PDF açılıp okunmadan "bitti" denmez.
- Mail: varsayılan kapalı; alıcı/içerik kullanıcı onaylı; deneme yalnız kullanıcının kendi adresine; gönderen politikası
  önce sorulur; zaman aşımı/500 sonrası tekrar koşu yok (önce SOST/SOOD). Adres ve kişisel veri repoya yazılmaz.
- RAP handler/saver'da `COMMIT WORK` yok — gönderim ayrı LUW'da (`references/mail-eki.md` §4).
- `adt_classrun` yazma sınıfıdır (kod çalıştırır); deneme sınıfı iş bitince silinir.
- Yeni tuzak ya da çalışan yöntem bulunursa (çalışan + denenen başarısız yollar) `%remember`.
