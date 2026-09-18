# Kontrol listeleri — oluşturma (6 faz) ve inceleme (FE)

> Freestyle UI SAP'ye yazma değildir; SAP yazma öncesi inceleme kapısı UI'ı görmez. Bu listeler **elle** geçilir.
> "Otomatik" sütunu bu skill'in script'ini gösterir; `yok` = semantik inceleme ya da runtime ölçümü gerekir.
> Script'ler `<TEMPLATE>/skills-sap/sap-ui5-fiori/scripts/` altında; her biri KAPSAM satırı basar.

---

## A. Oluşturma — faz faz

Kullanım: Faz 1–2 **kod yazmadan**, 3–5 geliştirme sırasında, 6 kapanışta. BLOCKER varken ilerlenmez.

### Faz 1 — İskelet
| ID | Kontrol | Önem | Otomatik | Ref |
|---|---|---|---|---|
| UI-BOOT-01 | `index.html` UI5 sürümü sabit + `language=tr` | BLOCKER | yok | `app-skeleton.md` §7 |
| UI-BOOT-02 | Manifest modelleri `i18n` + `""` (TwoWay, `useBatch:false`, Inline) + `ui` JSON; `settings.data` çift sarmalama yok; Component bağımlılıkları tam | BLOCKER | yok | §8, §9 |
| UI-BOOT-03 | Etiket/buton/mesaj metinleri spesifikasyondan, TR; tahmin değil | BLOCKER | yok | — |
| UI-BOOT-04 | `ui/` npm workspace kökü; uygulama `package.json` minimal; kurulum kökte; uygulama başına lock yok | WARNING | yok | §2 |
| UI-BOOT-05 | Tüm `ui5*.yaml` aynı kanonik host | BLOCKER | yok (`grep url: ui5*.yaml`) | §6 |

### Faz 2 — Mimari karar
| ID | Kontrol | Önem | Otomatik | Ref |
|---|---|---|---|---|
| UI-ARCH-01 | Düzenlenebilir alt grid varsa JSON edit-buffer | BLOCKER | yok | `freestyle-odata-v2.md` §1.3 |
| UI-ARCH-02 | Düzenlenebilir grid V2 nav-binding + `createEntry` ile yapılmadı | BLOCKER | yok | §1 S3 |
| UI-ARCH-03 | Save şablonu: `isNew ? deepCreate : başlık MERGE + kalem C/U/D` → `_runSeq` sıralı → tek `_ok/_err` | BLOCKER | yok | §1 |
| UI-ARCH-04 | `hasPendingChanges()` ön kontrolü yok | WARNING | yok | §1 S9 |
| UI-ARCH-05 | Liste ekranı = grid + ALV paritesi | BLOCKER | `check_list_view_grid.py` (yalnız adı liste/rapor olan view) | `list-grid-alv.md` |

### Faz 3 — Save davranışı
| ID | Kontrol | Önem | Otomatik | Ref |
|---|---|---|---|---|
| UI-SAVE-01 | Deep nav yoluna `createEntry` yok; `create/update/remove` | BLOCKER | yok | §1 S3 |
| UI-SAVE-02 | Değişmiş mevcut kalem de UPDATE; anahtar gövdede yok | BLOCKER | yok | §1 S4–S5 |
| UI-SAVE-03 | İşlemler sıralı | BLOCKER | yok | §1 S2 |
| UI-SAVE-04 | Başarı `MessageBox.success` (+ `onClose` navigasyon); hata `_parseError` | WARNING | yok | §6 |
| UI-SAVE-05 | Commit bariyeri (`blur` + `setTimeout 0`) | HIGH | yok | §1.2 |

### Faz 4 — Binding / kontrol tipleri
| ID | Kontrol | Önem | Otomatik | Ref |
|---|---|---|---|---|
| UI-BIND-01 | Sayısal/tarih binding'lerde OData tipi | BLOCKER | yok | §5.1 |
| UI-BIND-02 | CHAR1 bayrak CheckBox deseni (Edm.Boolean değilse) | WARNING | yok | §5.2 |
| UI-BIND-03 | Navigation `to_X` | BLOCKER | `check_ui5_freestyle_traps.py` T1 | §2.1 |
| UI-BIND-04 | Düzenlenebilir sayısal Input `type="Text"` + `onNumericLiveChange` | WARNING | `check_ui5_freestyle_traps.py` T2 | §5.4 |

### Faz 5 — Value-help ve kişiselleştirme
| ID | Kontrol | Önem | Otomatik | Ref |
|---|---|---|---|---|
| UI-VH-01 | VH onayı değeri kontrole doğrudan + modele yazıyor | BLOCKER | yok | §3 C1 |
| UI-VH-02 | Kod + ad: `<X>Name` expose + `description` | WARNING | yok | §3 C2 |
| UI-VH-03 | Filtre ekranı MultiInput + ValueHelpDialog; `caseSensitive:false` yok | BLOCKER | `check_filter_search_pattern.py` | `list-grid-alv.md` §6 |
| UI-PERSO-01 | Kolon göster/gizle + varyant + Excel; `P13nDialog`/`TablePersoController` yok; sıfırdan sort/filtre/export yazılmadı | BLOCKER | yok | `list-grid-alv.md` §3 |

### Faz 6 — Kapanış
| ID | Kontrol | Önem | Otomatik | Ref |
|---|---|---|---|---|
| UI-FIN-01 | Zararsız konsol uyarıları kovalanmadı | INFO | yok | `runtime-verification.md` §5 |
| UI-FIN-02 | Başlıktaki anahtar form alanı olarak tekrarlanmadı | INFO | yok | `fiori-elements-ux.md` §8 |
| UI-FIN-03 | Yeni bir UI tuzağı yaşandıysa `%remember` | WARNING | yok | — |
| UI-FIN-04 | BSP'nin tanımadığı dosya tipi (`.svg`/`.woff`) ve stray dosya yok | BLOCKER | `deploy_ui.py prepare` | `deploy-and-local-run.md` §4 |
| UI-FIN-05 | i18n anahtarları iki dosyada | WARNING | `check_i18n_keys.py` | `freestyle-odata-v2.md` §9 |
| UI-FIN-06 | Canlı `$metadata` çapraz kontrolü | BLOCKER | `check_ui_odata_refs.py` (çevrimdışı dosya) | §8 |
| UI-FIN-07 | Runtime smoke + tam kapsam | BLOCKER | `ui-smoke/run_ui_smoke.py` (Playwright proje içi kurulu ise) | `runtime-verification.md` §3 |

## B. İnceleme — FE kontrolleri (diff + etki alanı)

Her madde **HATA** (kod yanlış) ya da **EKSİK** (çalışıyor ama standart karşılanmamış); ikisi de düzeltilir. Kontrol
listesi dışı fikir `[ÖNERİ]`. Değişiklikle ilgisiz önceden var olan kritik bulgu ayrı işaretlenir, değişikliği bloklamaz.
Genel inceleme akışı `%code-review`; kanıt kuralı: her bulgu dosya:satır ya da ölçüm çıktısıyla.

| ID | Kontrol | Önem | Otomatik | Ref |
|---|---|---|---|---|
| FE-01 | V2 navigation `_X` | BLOCKER | `check_ui5_freestyle_traps.py` T1 | `freestyle-odata-v2.md` §2.1 |
| FE-02 | Save `setProperty` + `submitChanges` | HIGH | yok | §1 S1 |
| FE-03 | Eşzamanlı `update` aynı BO'da | BLOCKER | yok | §1 S2 |
| FE-04 | MERGE'de boş tarih `""` | BLOCKER | yok | §1 S7 |
| FE-05 | `setData` eksik şekil | HIGH | yok | §2.2 |
| FE-06 | `core:Title` VBox/HBox/CSSGrid çocuğu | BLOCKER | `check_ui5_freestyle_traps.py` T3 (WARN) | §4 |
| FE-07 | Düzenlenebilir miktar `type="Number"` | WARNING | `check_ui5_freestyle_traps.py` T2 | §5.4 |
| FE-08 | Seçim bayatlaması → yanlış kayıt silme; temizlik tek giriş noktasında, `rowsUpdated`'da değil, `success`'te | HIGH | yok | `delete-flow-ui.md` §1 |
| FE-09 | MERGE payload'ında salt-okunur `*Name`/`*Text` | HIGH | yok | §1 S6 |
| FE-10 | Plumbing sıfırdan yazılmış | HIGH | yok | §1–2 |
| FE-11 | Referans edilen i18n anahtarı tanımsız (iki dosya) | WARNING | `check_i18n_keys.py` (değişken anahtarlar hariç) | §9 |
| FE-12 | Spesifikasyondaki kural UI'da uygulanmamış | BLOCKER | yok | `runtime-verification.md` §3 |
| FE-13 | Liste/rapor grid değil | HIGH | `check_list_view_grid.py` | `list-grid-alv.md` §1 |
| FE-14 | Denetim alanları (oluşturan/değiştiren, tarih/saat) otomatik doldurulmuyor | HIGH | yok | backend sözleşmesi `%sap-rap` / `%sap-cds-ddic` |
| FE-15 | Belge/uygulama kilidi eksik ya da yanlış (salt okunur mod, heartbeat, `beforeunload`) | HIGH | yok | kilit sözleşmesi `%sap-rap` |
| FE-16 | Kontrol API'si / navigation adı tahmin edilmiş | HIGH | kısmen `check_ui_odata_refs.py` | §8 |
| FE-17 | "Done" runtime'da doğrulanmamış | HIGH | yok | `runtime-verification.md` §3 |
| FE-18 | VH alanında alt tanım gösterilmiyor | HIGH (EKSİK) | yok | §3 C8 |
| FE-19 | Belge ailesinin ortak yerleşimi karşılanmamış | MEDIUM (EKSİK) | yok | `fiori-elements-ux.md` §8 |
| FE-20 | Binding/payload property adı canlı `$metadata`'da yok | BLOCKER | `check_ui_odata_refs.py` (Filter/select/orderby yolları; payload nesne anahtarları yok) | §8 |
| FE-21 | Generic hata yutma (`_parseError` yok) | HIGH (EKSİK) | yok | §6.2 |
| FE-22 | Commit bariyeri yok | HIGH | yok | §1.2 |
| FE-23 | Create/Change ikiz controller'da düzeltme paritesi yok | MEDIUM | yok | §1 S12 |
| FE-24 | Başarı geri bildirimi yok ya da toast + navigasyon | HIGH | yok | §6.1 |
| FE-25 | VH seçimi alana yazılmıyor (3 nokta eşleşmesi) | HIGH | yok | §3 C5 |
| FE-26 | Manifest isimli JSONModel `settings.data` çift sarmalama | HIGH | yok | `app-skeleton.md` §8 |
| FE-27 | `Edm.DateTime` payload'ında string | BLOCKER | yok | §5.3 |
| FE-28 | Payload Edm tipi canlı metadata ile uyuşmuyor (Boolean `'X'` vb.); mock metadata'ya güvenilmiş | BLOCKER | yok | §5.3 |
| FE-29 | Save callback garantisiz → busy sonsuz | BLOCKER | yok | §1 (`_runSeq`) |
| FE-30 | İstemci `_` alanı OData context'ine stamp + aynı model submit | MEDIUM | yok | §2.5 |
| FE-31 | VH listesi boş: VH entity set tüketen serviste expose değil | HIGH | `check_ui_odata_refs.py` (VH set adı statikse) | §3 C6 |
| FE-32 | Filtre/VH/grid arama: `caseSensitive:false`; MultiInput değil; wildcard; `defaultOp` | BLOCKER | `check_filter_search_pattern.py` (a, b); c–e yok | `list-grid-alv.md` §6 |
| FE-33 | `f:Form`/`SimpleForm` + `ColumnLayout` içinde layout container | BLOCKER | `check_ui5_freestyle_traps.py` T4 (yalnız `<f:fields>` içi; `SimpleForm` doğrudan içeriği yok) | §4 |
| FE-34 | Elle girilen VH değeri doğrulanmıyor, save bloklanmıyor | BLOCKER | yok | §3 C7 |
| FE-35 | Miktar düz birleştirme, formatter yok | MEDIUM | yok | §5.5 |
| FE-36 | Ön yüz kapısı backend karşılığı ölçülmeden kaldırılmış | BLOCKER | yok | `%sap-rap` delete-guard §3 |
| FE-37 | Anında silmeye geçişte pending detektör ≠ `onSave` payload'ı (başlık dahil) | HIGH | yok | `delete-flow-ui.md` §2 |
| FE-38 | Paralel `remove/update` (`Promise.all`) + thunk kapanış tuzağı | HIGH | yok | `delete-flow-ui.md` §3 |
| FE-39 | Görev diff'inde kapsam dışı paylaşılan altyapı değişikliği (script, kural, ortak util) | HIGH | yok | kapsam dışı bulgu: kullanıcıya bildir |
| FE-40 | Rapordaki sayılar içerik çapalı değil (çıplak sayı) | MEDIUM | yok | `%verify-done` |
| FE-41 | "0 sonuç" iddiası kontrol grupsuz | MEDIUM | yok | `%verify-done` |
| FE-42 | İki koleksiyon anahtar birleşiminde sıfır dolgusu normalize değil | HIGH | yok | §5.6 |
| FE-43 | `index.html` sürümsüz UI5 ya da `minUI5Version` farklı | BLOCKER | yok | `app-skeleton.md` §7 |

Ağırlıklar: FE-01..09, 20, 22, 25–29, 31, 33, 34, 42, 43 çoğunlukla **HATA**; FE-13, 14, 15, 18, 19, 21, 23 **EKSİK**.

---

## Bu dosyada ÇIKARILAN / DEĞİŞTİRİLEN
- Kaynaktaki inceleme ajanı rolü ve "önce deterministik kontrolü koş" talimatı aXet'te ajan tanımı olmadığı için genel
  inceleme kuralına çevrildi (`%code-review`).
- "Otomatik" sütunu kaynak doğrulayıcı adlarından aXet script'lerine eşlendi; karşılığı olmayanlar `yok`. Kaynakta "aday"
  olarak listelenen i18n tamlık kontrolü aXet'te `check_i18n_keys.py` olarak var; FE-33 (T4) aXet trap script'inde ERROR.
- Kaynaktaki FE-36/37 kimlik çakışması (iki farklı tanım) giderildi: sayı içerik çapası ve sıfır sonuç kontrolleri
  FE-40/41'de.
- Yeni satırlar: UI-BOOT-05 (kanonik host, kaynakta playbook ön kontrol maddesiydi), UI-ARCH-05, UI-SAVE-05, UI-BIND-04,
  UI-VH-03, UI-FIN-05..07, FE-42 (sıfır dolgusu, kaynakta hafıza dersiydi), FE-43 (sürüm sabitleme, kaynakta playbook
  satırıydı).
- UI-SAVE-04 kaynakta `MessageToast` diyordu; kaynak standart ve FE-24 ile hizalandı.
- Müşteri uygulama adları, tarihli vaka referansları ve belge uygulamalarının müşteriye özgü şablon adı çıkarıldı.
