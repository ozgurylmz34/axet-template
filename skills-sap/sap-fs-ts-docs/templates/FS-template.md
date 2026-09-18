# FS-<MODÜL>-<NNN> — <Geliştirme adı>

> Şablon: `%sap-fs-ts-docs` → `references/fs-authoring.md`. Köşeli parantezli yer tutucular doldurulur; boş bırakılan zorunlu
> bölüm "Uygulanmaz — <gerekçe>" yazılır, silinmez. Gövde yalnız kapanmış hedef durumu anlatır (İlke 2b).

| Alan | Değer |
|---|---|
| Doküman no | FS-<MODÜL>-<NNN> |
| Proje | <proje> |
| Müşteri | <müşteri / birim> |
| Hazırlayan | <rol ya da ad> |
| Tarih | <GG.AA.YYYY> |
| Versiyon | v<1.0> |
| Durum | Taslak |
| Kapsam sınıfı | <S1 / S2> (intake: `.axet-code/intake/<id>.md`) |

## 1. Doküman kontrolü

### 1.1 Versiyon geçmişi
| Versiyon | Tarih | Değiştiren | Ne değişti (≤ 400 karakter, madde/§ atfı) |
|---|---|---|---|
| v1.0 | <tarih> | <rol> | İlk sürüm |

### 1.2 Dağıtım listesi
| Ad / rol | Görev | Onay gerekli mi |
|---|---|---|
| <anahtar kullanıcı> | <görev> | Evet |

### 1.3 İlgili dokümanlar
| Doküman | No | Not |
|---|---|---|
| Teknik spesifikasyon | TS-<MODÜL>-<NNN> | <hazırlanacak> |

## 2. Giriş

### 2.1 Amaç
<Bu geliştirme hangi iş problemini çözer?>

### 2.2 Kapsam
**Kapsam içi:**
- <madde>

**Kapsam dışı:**
- <madde>

### 2.3 Varsayımlar ve bağımlılıklar
| No | Tür | Açıklama | Doğrulama durumu |
|---|---|---|---|
| V-01 | [Varsayım] | <açıklama> | <doğrulanacak / doğrulandı> |
| B-01 | [Bağımlılık] | <başka geliştirme / sistem / karar> | <durum> |

### 2.4 Referanslar
- <intake artefaktı, toplantı notu, ref_docs dosyası>

## 3. İş süreci

### 3.1 Mevcut durum
1. <adım> — <sorumlu>

**Sorunlar:** <madde>

### 3.2 Hedef durum
1. <adım> — <sorumlu>

**Değişen roller / fayda:** <madde>

### 3.3 Fark analizi
| Mevcut | Hedef | Fark | Çözüm yöntemi |
|---|---|---|---|
| <…> | <…> | <…> | <geliştirme / uyarlama / süreç> |

## 4. Fonksiyonel gereksinimler

### 4.1 Gereksinim listesi
| No | Açıklama | Öncelik | Kategori | Kaynak / gerekçe |
|---|---|---|---|---|
| FR-001 | <test edilebilir ifade> | Yüksek | <kategori> | <kullanıcı isteği K-1> |
| FR-002 | Hacim/performans: <günde ~N kayıt, eşzamanlı K kullanıcı, yanıt süresi> | Yüksek | Performans | <kaynak> |

### 4.2 İş kuralları
| No | Kural | Kabul kriteri (EARS) |
|---|---|---|
| KR-001 | <açık, ölçülebilir kural> | <kullanıcı X yaptığında sistem Y yapmalı> |

## 5. Ekranlar

### 5.1 Ekran listesi
| No | Ekran adı | Amaç |
|---|---|---|
| SCR-001 | <ad> | <amaç> |

### 5.2 SCR-001 — <ekran adı>
```
┌────────────────────────────────────────────┐
│ <mockup: alanlar, butonlar, liste>          │
└────────────────────────────────────────────┘
```
| Alan etiketi | Tip / uzunluk (iş anlamında) | Zorunlu | Varsayılan | Açıklama / boş bırakılırsa |
|---|---|---|---|---|
| <etiket> | <metin 40> | Evet | <—> | <…> |

| Buton / aksiyon | Ne yapar | Sonuç (kullanıcıya görünen) |
|---|---|---|
| <Kaydet> | <…> | <…> |

**Doğrulama kuralları:** <madde>

## 6. Veri

### 6.1 Alan eşleştirme
| Kaynak alan / sistem | Hedef | Dönüşüm kuralı |
|---|---|---|
| <…> | <…> | <…> |

### 6.2 Veri kalitesi
- <zorunlu alan, format, doğrulama>

## 7. Entegrasyon

### 7.1 Modüller arası
| Kaynak modül | Hedef modül | Yön | Otomatik / manuel |
|---|---|---|---|
| <…> | <…> | <…> | <…> |

### 7.2 Dış sistemler
| Sistem | Tip | Protokol | Açıklama |
|---|---|---|---|
| <Uygulanmaz — gerekçe> | | | |

## 8. Yetkilendirme
| Rol | İzin (iş anlamında) | Kısıt |
|---|---|---|
| <rol> | <görüntüle / oluştur / onayla> | <organizasyon birimi> |

Kişisel veri, loglama ve denetim izi: <gereksinim ya da "girdi sessiz → 11-B S-nn">

## 9. Raporlama
| Rapor | Seçim kriterleri | Çıktı biçimi |
|---|---|---|
| <Uygulanmaz — gerekçe> | | |

## 10. Hata yönetimi
| Durum | Kullanıcıya görünen mesaj (iş dili) | Kullanıcı aksiyonu |
|---|---|---|
| <…> | <…> | <…> |

## 11. Test senaryoları
| No | Senaryo | Ön koşul | Adımlar | Beklenen sonuç | Bağlı kabul kriteri |
|---|---|---|---|---|---|
| TC-01 | <…> | <…> | <…> | <…> | KR-001 |

## 11-A. Danışman önerileri
| No | [Öneri] | Fayda | Etki / maliyet | Karar |
|---|---|---|---|---|
| Ö-01 | <öneri> | <…> | <…> | <onay / ret / bekliyor> |

## 11-B. Açık kararlar
| No | Netleştirdiği istek | Seçenekler | Öneri | Karar |
|---|---|---|---|---|
| S-01 | <K-1> | a) <…> · b) <…> | <a, çünkü …> | <bekliyor> |

## 12. Onay
| Rol | Ad | Tarih | İmza |
|---|---|---|---|
| Hazırlayan | | | |
| Gözden geçiren | | | |
| Anahtar kullanıcı | | | |
| Proje yöneticisi | | | |

---

## EK — Karar ve kanıt günlüğü
| Karar no | Konu | Seçenekler | Seçilen / reddedilen ve kısa gerekçe | Kim / ne zaman | Kanıt atfı |
|---|---|---|---|---|---|
| K-01 | <…> | <…> | <…> | <…> | <ref_docs/RESEARCH-….md> |

### Yayılım tablosu
| Karar no | Dokunulacak yer (§ / dosya) | Durum | Kim / ne zaman |
|---|---|---|---|
| K-01 | <§4.2 KR-001 · §5.2 alan tablosu · §11 TC-01> | <yapıldı / bekliyor> | <…> |
