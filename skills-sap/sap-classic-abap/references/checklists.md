# Kontrol listesi — klasik dialog programı (rapor / module pool / Dynpro / ALV)

> Kaynak: ekibin klasik dialog oluşturma kontrol listesi (manuel ön kontrol). Klasik dialog için otomatik inceleme
> kuralı sınırlıdır → bu liste yazmaya başlamadan ve push öncesi **elle** geçilir; bitince `%code-review` ve `%verify-done`.
> Adobe Forms kontrol listesi: `forms-f1-help.md` §A.3 · e-posta: `email.md` §7.
> `templates/` altındaki şablonlar bilerek tek gövdedir; CLC-07 gerçek programlar içindir.

## Faz 1 — Yapı (kod yazmadan)
| ID | Kontrol | Önem | Ref |
|---|---|---|---|
| CLC-PRF | Profil `ecc` ya da `s4_private`; paket `_CLC` (değilse sor) | BLOCKER | `%sap-dev` naming §3 |
| CLC-07 | Tek gövde yok: ana program = `INCLUDE` + olay blokları; kod `_T01/_C01/_F01/_O01/_I01` include'larında (PROG/I) | BLOCKER | `programs-includes.md` §1 |
| CLC-NAM | Program `<GÖVDE>_P_<AD>` (≤ 26), include `<GÖVDE>_I_<AD>_<X>NN`, yerel sınıflar `lcl_*` | BLOCKER | naming §4.1 |
| CLC-TTL | TITLE kullanıcıdan; include açıklaması TITLE + sonek | BLOCKER | naming §6 |

## Faz 2 — ALV (template-first)
| ID | Kontrol | Önem | Ref |
|---|---|---|---|
| CLC-ALV1 | ALV kurulumu programda satır içi (`lcl_event` + `lvc_t_fcat`); ortak ALV sınıfı yok | BLOCKER | `alv-report.md` §1 |
| CLC-ALV2 | Kolon başlıkları `master_language`'de ve tam, spesifikasyondan | BLOCKER | kesin yasak D |
| CLC-ALV3 | ALV paritesi yerleşikten (`i_save = 'A'`) gerçekten çalışıyor | WARNING | SAP çekirdeği |
| CLC-ALV4 | Field catalog yolu (yapı / manuel) kullanıcıya soruldu ya da TS'te gerekçeli | WARNING | `alv-report.md` §3 |
| CLC-ALV5 | Olay işleyicide satır = `es_row_no-row_id` | BLOCKER | `alv-report.md` §4 |

## Faz 3 — Ekran + GUI status
| ID | Kontrol | Önem | Ref |
|---|---|---|---|
| CLC-SCR1 | Ekran + `STAT<n>` + `TIT<n>` üretildi (üreteç FM ya da elle); classrun ile denenmedi | BLOCKER | `dynpro-gui-status.md` §0–§2 |
| CLC-SCR2 | Container: ekran 200×255, `element_of` boş, `c_resize_v/h='X'`, min 1/1 | BLOCKER | §4 |
| CLC-SCR3 | Split = tek custom control + `cl_gui_splitter_container` | WARNING | `alv-report.md` §6 |
| CLC-SCR4 | Menü/toolbar temiz; `act` korundu (`00256`) | WARNING | §3 |
| CLC-SCR5 | BACK/EXIT/CANCEL + ESC çalışır; status üretildi (`00264`); BACK/CANCEL → `LEAVE TO SCREEN 0`, EXIT → `LEAVE PROGRAM` | BLOCKER | §3, `alv-report.md` §5 |
| CLC-SCR6 | Üreteç yolunda donör açıkça verildi ve tanı mesajında nav eşlemesi "açık" görüldü | BLOCKER | §3 |
| CLC-SCR7 | PAI'de `CLEAR` ok-code / `sy-ucomm`; her toolbar fcode'u için `CASE` dalı | BLOCKER | `alv-report.md` §5 |

## Faz 4 — Metin + kesin yasaklar
| ID | Kontrol | Önem | Ref |
|---|---|---|---|
| CLC-TXT | Seçim metinleri / `TEXT-xxx` / GUI başlığı `master_language`'de, metin havuzunda (push kaynağı metin havuzunu kapsamaz) | BLOCKER | `programs-includes.md` §3 |
| CLC-SEL | Seçim ekranı adları ≤ 8, radyo grubu ≤ 4; `TEXT-xxx = …` yok | BLOCKER | `programs-includes.md` §2 |
| CLC-005 | Standart tabloya doğrudan DML yok (BAPI/RFC); standart program/exit/ekran değişmez; transport kullanıcının | BLOCKER | SAP çekirdeği A/B/C |
| CLC-ATC | ATC: öncelik politikası (proje `AGENTS.md`; yoksa öncelik 1 zorunlu, 2/3 açık onayla) | BLOCKER | `alv-report.md` §8 |

## Faz 5 — Datafield diyalog ekranı (yalnız tek kayıtlık modal form)
| ID | Kontrol | Önem | Ref |
|---|---|---|---|
| CLC-DLG1 | Alanlar DDIC yapısına bağlı (`FROM_DICT='X'`, `MATCHCODE` boş); `gs_*` köprüsü yok | BLOCKER | `dynpro-dialog-fields.md` §1 |
| CLC-DLG2 | Dinamik alan kilidi PBO'da | BLOCKER | §3 |
| CLC-DLG3 | Her diyalog kendi kaydet/iptal fcode'unu taşıyor | BLOCKER | §3 |
| CLC-DLG4 | F4 mekanizması karar tablosuna göre; Z SHLP denenmedi | WARNING | §2 |
| CLC-DLG5 | Bağlama kullanılıyorsa `where` eşlemesi açık | BLOCKER | §2.2 |
| CLC-DLG6 | `BUT` deltası yazımdan önce hesaplandı; fonksiyon detay diff'i alındı | BLOCKER | §4 |
| CLC-DLG7 | DDIC yapısı değiştiyse ekranın yeniden üretimi planda | BLOCKER | §2.2 |
| CLC-DLG8 | Her giriş alanının ayrı `TYPE='TEXT'` etiket satırı var | BLOCKER | §1.1 |
