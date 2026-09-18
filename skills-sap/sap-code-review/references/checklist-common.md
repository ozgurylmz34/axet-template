# Ortak SAP inceleme satırları — her SAP değişikliğinde

> **Kaynak:** ekibin backend kod-inceleme kontrol listesi (kimlikler korunmuştur: `BE-NN`) ve bağımsız inceleme ajanının
> yöntemi; aXet'e uyarlandı. `SR-NN` = aXet'te eklenen inceleme satırı.
> **Önem:** kaynaktaki BLOCKER/HIGH → `BLOCKER` · MEDIUM/LOW → `WARNING`.
> **Tip:** HATA (kod ya da obje yanlış) · EKSİK (çalışıyor ama zorunlu madde karşılanmamış). İkisi de düzeltilir.
> **Otomasyon:** yalnız adı geçen validator/araç vardır (`validator-map.md`); `YOK` = elle incelenir.
> Yeni satır: `SKILL.md` §6.

| ID | Ne kontrol edilir | Nasıl | Önem | Otomasyon | Kaynak ders |
|---|---|---|---|---|---|
| SR-01 | Etki alanı ölçülmeden paylaşılan obje (sınıf, CDS, FM, tablo, yapı) değişmiş | Değişen her obje için `adt_where_used` (FM çağıranı: `CROSS`), dolaylı etki için `adt_impact_analysis`; yerel `grep -rn`. 0 sonuç yalnız `coverage_complete: true` ve `truncated: false` iken "kullanılmıyor" demektir | BLOCKER | YOK | İnceleme yöntemi "kapsam = diff + etki alanı"; ekip dersi "düzeltme öncesi where-used" |
| SR-02 | Değişiklik güncel canlı kaynağın üzerine kurulmamış (düzenlemeden önce çekme yok) | Raporda obje + `adt_get include_source=true` çekim zamanı var mı; yerel dosya ile canlı kaynak farkı | BLOCKER | Kısmi: CLI `adt_push_source` önceden `adt_get` çekimi olmadan yazmaz | `%sap-dev` role-briefs S4; template değişiklik notu 0.2.0 |
| SR-03 | Profil yeteneği varsayılmış: `s4_public`/`btp_abap`'ta klasik program, include, fonksiyon grubu; `ecc`'de RAP ya da released CDS | `sap-project.json` `sap_profile` ↔ değişen obje tipi | BLOCKER | YOK | `%sap-dev` §2 profil |
| BE-01 | Z/Y dışı obje yaratılmış/değiştirilmiş ya da standart tabloya doğrudan `INSERT`/`UPDATE`/`DELETE`/`MODIFY` var (kesin yasak A/B) | Diff'teki obje adları Z/Y mi; kaynakta ifade başında `insert`, `update`, `delete`, `modify` + hedef tablo adı; iç tablo mu veritabanı mı ayırt et | BLOCKER | Kısmi (incelemenin yerine geçmez): yazma kapısı kaynak taraması `sapadt/std_dml_scan.py` (standart tabloya doğrudan DML) + Z/Y önek guardrail'i `sapadt/guardrails.py` | Kesin yasaklar A/B |
| BE-02 | DTEL, append alanı, domain ya da obje adı AI tarafından önerilmiş; Z obje açıklaması/etiketi tahmin edilmiş | Yeni her ad ve metnin kaynağı yazılı mı: kullanıcı mesajı, spesifikasyon `dosya:satır`, eski sistem okuması | BLOCKER | YOK | Kesin yasaklar A/D; ekip dersi "Z obje metni tahmin edilmez" |
| BE-15 | Yazma sonrası sistemden okuma yok; "uploaded / activated" mesajına güvenilmiş | Araç dönüşünde `readback_verified`, `activation_verified` `true` mu (`null` = ÖLÇÜLEMEDİ); DDIC XML alanları `adt_get` ile; paket bazında `adt_inactive_objects` | BLOCKER | Kısmi: `adt_push_source` içerik geri okuması (`tools/atom.py` `_content_readback`); tablo alan kaybı `table_update` → `check_table_field_drop.py` (BLOCKER) | Ekip dersi "yazma sonrası readback"; `%sap-adt-foundation` known-errors K-10 |
| BE-18 | Spesifikasyondaki iş kuralı (validation, determination, yetki, eşik) belgede var, kodda uygulanmamış | `SPEC.md` / FS kural listesi → her kural için uygulandığı `dosya:satır`; eşleşmeyen kural = EKSİK | BLOCKER | YOK | Ekip dersi "tamam demeden tam kapsam doğrula" |
| BE-66 | Görev kapsamı dışında paylaşılan araç, kural, skill ya da şablon dosyası değişmiş | `git diff --name-only` ↔ görevin yazma alanı; dışındaysa ayrı onay ve ayrı commit izi; kural gevşetmesi varsa kullanıcı onayı | BLOCKER | YOK | Ekip dersi "altyapı düzeltme prosedürü" |
| BE-64 | "Bulunamadı / 0 sonuç / yok" iddiası kapsam kanıtı ve pozitif kontrol örneği olmadan yazılmış | Raporda arama deseni + dizin/araç + kapsam alanları + bilinen bir pozitif örnekle aynı aramanın sonucu | WARNING | YOK | Ekip denetim dersi (boş liste iki ayrı gerçeği aynı görünüme indirir) |
| BE-70 | Rapordaki sayı ya da konum iddiası içerik çapasız (yalnız satır no ya da çıplak sayı) | Her sayı/konum için başlık, imza ya da alıntıyla doğrula; bayat sayı ara | WARNING | YOK | Ekip denetim dersi (bayat sayı tekrarı) |
| BE-65 | İş alt ajanla yapıldıysa brifing zorunlu bölümleri (görev, sınırlar, kanıt kuralları, engel, çıktı) taşımıyor | Brifing metni ↔ `skills/explore/references/brief-template.md` | WARNING | YOK | Ekip denetim dersi (süreç sinyali; build'i bloklamaz) |

## Bu dosyada ÇIKARILAN / DEĞİŞTİRİLEN
- Kaynaktaki alt ajan mesajlaşma ve ajan-takımı dili çıkarıldı; BE-65 aXet brifing şablonuna bağlandı.
- SR-01…SR-03 kaynak inceleme yönteminden ve `%sap-dev` kurallarından satıra çevrildi.
