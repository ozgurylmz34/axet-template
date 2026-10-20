# SD — SPRO / uyarlama (referans)

> Uyarlama okuma / farkındalık içindir. Z geliştirme bu uyarlamaya dayanır; **değiştirmek danışman / operatör işidir** —
> önerilir, kullanıcı karar verir. Uyarlama değerinin kendisi iş listesine ya da hafızaya yazılmaz (ekip dersi
> `memory/feedback_uyarlama-verisi-acik-kalem-degil.md`).

## Satış
| IMG / işlem | Konu |
|---|---|
| VOV8 | Satış belge türleri |
| VOV7 | Kalem tipleri |
| VOV6 | Termin satırı tipleri |
| VOV4 | Kalem tipi belirleme |
| V/08, V/06 | Fiyatlandırma şeması / koşul türleri |

## Kopyalama kontrolü
| İşlem | Akış |
|---|---|
| VTAA | Satış belgesi → satış belgesi |
| VTLA | Satış belgesi → teslimat |
| VTFL | Teslimat → fatura |
| VTFA | Satış belgesi → fatura |
| VTAF | **Fatura → satış belgesi** (tablo `TVCPA`; faturaya referanslı borç/alacak dekontu talebi) |

⚠ **Referanslı talep tasarımında kopyalama kontrolü ÖLÇÜLÜR** (ekip dersi, 2026-10-16/17; aXet'te ayrıca ölçülmedi): belge
türünün TVAK'ta olması, faturalama türü / blok / şema tanımlı olması kopyalama kontrolünün varlığını **kanıtlamaz**. Ölçülen
vakada bir Z dekont talebi türü çiftinde `TVCPA` hedef kaydı **0** çıktı; kontrol grubu standart L2/G2 türleri ~1.200'er
kayıtla doluydu. Ölçüm: `TVCPA` WHERE `AUARN IN (<hedef türler>)` + aynı sorgu standart türle. Kayıt yoksa FS'e **ön koşul**
(VTAF uyarlaması) ve açık soru olarak yaz; API denemesini o tanımdan sonraya koy (yoksa referanslı yaratma reddedilir).

## Teslimat / sevkiyat
| IMG / işlem | Konu |
|---|---|
| 0VLK | Teslimat türleri |
| 0VLP | Teslimat kalem tipleri |
| Sevkiyat noktası belirleme | — |
| Rota belirleme | — |
| LE-TRA (VT) | Nakliye uyarlaması |

## Çıktı / yasal belge
| Konu | Not |
|---|---|
| NACE | Çıktı belirleme |
| SAP Document Compliance | Yerel yasal belgeler (ör. e-İrsaliye / e-Fatura) |

## Varyant konfigürasyonu — aynı belgede kalemi konfigürasyonuyla devretme (Mill hızlı giriş)
VA21/VA22'de kalemi karakteristik değerleriyle aynı belgedeki başka kaleme devretme (`VBAP-MILL_SE_GPOSN` "Genel kalem").
**VTAA DEĞİLDİR.** IMG düğümü "Satış belgelerinde karakteristik değerlerin hızlı girişi"nin beş aktivitesi, kullanım,
doğrulama, sorun giderme: `karakteristik-hizli-giris.md`.

| IMG / işlem | Alan | Değer |
|---|---|---|
| `ISMP/SAPMP/SD_TVAK1` | TVAK `/SAPMP/CEACT` | X (zorunlu) |
| ⭐ VOV8 | TVAK `UEVOR` "Genel bakış ekranı işlev kodu" | `MILL_SE_UE` (zorunlu — yoksa CEACT=X iken de alan AÇILMAZ) |
| `ISMP/SAPMP/SD_TVAK1` | TVAK `/SAPMP/PDACT` | X (mevcut kaleme "Aktarım" için) |
| `ISMP/SAPMP/V_VBMUEH` · `ISMP/SAPMP/SD_MUEBS` · kullanıcı parametresi `VAM` | `/SAPMP/VBMUEH` · VBMUE/VBMUEZ | isteğe bağlı değer sütunları |
