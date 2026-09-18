# KD-<MODÜL>-<NNN> — <Uygulamanın kullanıcı dostu adı> Kullanıcı Kılavuzu

> Şablon: `%sap-fs-ts-docs` → `references/kd-authoring.md`. Sade dil, teknik terim yok. Görüntüler gerçek arayüz + temiz örnek
> veriyle. Yer tutucu kod blokları `build_kd_pdf.py --map` ile görsellerle değiştirilir.

| Alan | Değer |
|---|---|
| Doküman no | KD-<MODÜL>-<NNN> |
| İlgili FS / TS | FS-<MODÜL>-<NNN> · TS-<MODÜL>-<NNN> |
| Nereden açılır | <launchpad grubu → kutucuk / işlem kodu> |
| Kimin için | <rol> |
| Hazırlayan | <rol ya da ad> |
| Tarih / versiyon | <GG.AA.YYYY> / v<1.0> |
| Durum | Taslak |

## İçindekiler
- [1. Bu kılavuz hakkında](#1-bu-kilavuz-hakkinda)
- [2. Genel bakış](#2-genel-bakis)
- [3. Başlamadan önce](#3-baslamadan-once)
- [4. Ekran tanıtımı](#4-ekran-tanitimi)
- [4-A. Liste ve tablo ekranı özellikleri](#4-a-liste-ve-tablo-ekrani-ozellikleri)
- [5. Adım adım iş akışları](#5-adim-adim-is-akislari)
- [6. Alan giriş rehberi](#6-alan-giris-rehberi)
- [7. Butonlar ve işlemler](#7-butonlar-ve-islemler)
- [8. Yapılması ve yapılmaması gerekenler](#8-yapilmasi-ve-yapilmamasi-gerekenler)
- [9. Hata ve mesajlar](#9-hata-ve-mesajlar)
- [10. Sık sorulan sorular](#10-sik-sorulan-sorular)
- [11. Terimler sözlüğü](#11-terimler-sozlugu)
- [12. Destek ve iletişim](#12-destek-ve-iletisim)
- [13. Onay](#13-onay)

> İçindekiler bağlantıları üreticinin Türkçe slug kuralıyla yazılır: Türkçe harf ASCII karşılığına döner, noktalama silinir,
> her boşluk bir tire olur ("4-A. Liste ve tablo" → `#4-a-liste-ve-tablo`). Üretimden sonra `verify_doc_html.py` ile doğrula;
> ölü bağlantıyı başlıktan değil href'ten düzelt.

## Hızlı başlangıç
1. <en sık iş, 3-5 adım>

## 1. Bu kılavuz hakkında
- **Ne anlatır:** <1 cümle>
- **Kimin için:** <rol>
- **Nasıl okunur:** yeni başlıyorsan baştan; deneyimliysen ilgili bölüme atla.
- **Takılırsan:** <destek kanalı — Bölüm 12>
- Bu kılavuzu kullanmak için teknik bilgi gerekmez.

## 2. Genel bakış
**Bu uygulama nedir?** <1-2 paragraf>

**Hangi işi kolaylaştırır?** Eskiden <…>; şimdi <…>.

**Arka planda ne olur?** <"Kaydet'e bastığında sistemde … oluşur; bundan sonra … yapılabilir.">

**Genel akış:**
1. <adım>

## 3. Başlamadan önce
- **Yetki:** <gerekli rol; yoksa kime başvurulur>
- **Elinde olması gerekenler:** <bilgi / ana veri>
- **Nereden açılır:** <yol; ilk giriş notları>

## 4. Ekran tanıtımı
```
[GÖRSEL: Ana ekran — işaretli bölümler]
```
| No | Bölüm | Ne işe yarar |
|---|---|---|
| 1 | <…> | <…> |

## 4-A. Liste ve tablo ekranı özellikleri
> Uygulamada liste/tablo ekranı yoksa bu bölüm "Bu uygulamada liste ekranı yoktur." yazılarak bırakılır.

| Özellik | Nerede | Ne işe yarar | Nasıl kullanılır |
|---|---|---|---|
| Sıralama | kolon başlığı | listeyi artan/azalan dizer | başlığa tıkla → Artan / Azalan sırala |
| Filtreleme | kolon başlığı | listeyi bir değere göre süzer | başlığa tıkla → Filtre → değeri yaz |
| Kolonlar | başlık çubuğu → Kolonlar | görünen kolonları seçer | listeden işaretle / kaldır |
| Varyant | başlık çubuğu → Varyant | düzeni kaydeder ve geri yükler | "Farklı kaydet" → ad ver → seç |
| Excel'e aktar | başlık çubuğu → Excel'e aktar | listeyi dosyaya indirir | tıkla → kapsamı seç → dosya iner |
| Yenile | başlık çubuğu → Yenile | güncel veriyi getirir | tıkla |
| Filtre çubuğu | listenin üstü | kriter girerek listeler | paneli aç → kriter gir → Listele |

```
[GÖRSEL: Liste araç çubuğu — işaretli]
```

## 5. Adım adım iş akışları

### 5.1 <Görev adı> yapmak için
1. <Tıkla / gir / seç>
2. <…>

```
[GÖRSEL: <görev> — adım 2]
```
Sonunda şu mesajı görürsün: "<birebir mesaj>".

### 5.2 <Alt ekran / diyalog adı>
<Ne zaman açılır, ne işe yarar>

```
[GÖRSEL: <diyalog adı>]
```
| Alan / buton | Ne işe yarar |
|---|---|
| <…> | <…> |

## 6. Alan giriş rehberi
| Alan (ekrandaki adı) | Ne girilir | Biçim / örnek | Zorunlu mu | Neden / boş bırakırsan | Otomatik mi |
|---|---|---|---|---|---|
| <…> | <…> | <…> | <Evet> | <…> | <Hayır> |

## 7. Butonlar ve işlemler
| Buton | Ne yapar | Ne zaman kullanılır | Arka planda sonuç |
|---|---|---|---|
| <…> | <…> | <…> | <…> |

## 8. Yapılması ve yapılmaması gerekenler
- ✅ <…>
- ⛔ <…>

## 9. Hata ve mesajlar
| Gördüğün mesaj (birebir) | Ne demek | Neden olur | Ne yapmalısın |
|---|---|---|---|
| <…> | <…> | <…> | <…> |

Hâlâ çözülmezse: mesajın tam metnini ve belge numarasını Bölüm 12'deki kanala ilet.

## 10. Sık sorulan sorular
**<Soru>?**
<Sade cevap>

## 11. Terimler sözlüğü
| Terim | Anlamı |
|---|---|
| <…> | <…> |

## 12. Destek ve iletişim
| Kanal | Nasıl ulaşılır | Çalışma saatleri |
|---|---|---|
| <anahtar kullanıcı / destek kanalı> | <…> | <…> |

## 13. Onay
| Rol | Ad | Tarih |
|---|---|---|
| Hazırlayan | | |
| Gözden geçiren anahtar kullanıcı | | |
| Süreç sahibi | | |
