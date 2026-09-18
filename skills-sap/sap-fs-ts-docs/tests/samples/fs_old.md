# FS-CA-000 — Demo Onay Ekranı

## 1. Doküman kontrolü
| Versiyon | Tarih | Değiştiren | Ne değişti |
|---|---|---|---|
| v1.0 | 01.03.2026 | Danışman | İlk sürüm |

## 4. Fonksiyonel gereksinimler
| No | Açıklama | Öncelik |
|---|---|---|
| FR-001 | Kullanıcı bekleyen demo onay kayıtlarını listeleyebilmelidir. | Yüksek |
| FR-002 | Günde yaklaşık 2500 kayıt işlenir ve liste üç saniyede açılmalıdır. | Yüksek |

KR-001: Onaylanan kaydın durumu ONAYLANDI olarak saklanır ve değiştiren kullanıcı kaydedilir.

v1.1 revizyonunda kullanıcı toplantısında yeni bir durum eklenmesine karar verildi, ilk turda yanlış okunmuştu.

## 5. Ekranlar
```
┌──────────────────────────────┐
│ Demo Onay Listesi             │
│ [Onayla] [Reddet]             │
└──────────────────────────────┘
```

Eşleştirme alanı `ZCA000_T_DEMO-REF_NO` üzerinden yapılır.
