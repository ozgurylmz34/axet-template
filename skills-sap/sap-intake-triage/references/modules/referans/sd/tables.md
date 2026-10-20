# SD — kilit tablolar (referans)

> Standart SD tabloları — **okuma / farkındalık**. ⛔ Kesin yasak A/B: bu tablolara dokunulmaz, doğrudan yazılmaz; yalnız
> okuma kaynağı ve alan adı referansıdır. Liste hipotezdir: alanın o sistemde varlığını canlıda teyit et. Okumada released
> CDS tercih edilir (modül paketi SD-K4).

## Satış
| Tablo | İçerik |
|---|---|
| VBAK / VBAP | Satış belgesi başlık / kalem |
| VBEP | Kalem termin satırları |
| VBKD | Satış — ticari veriler |
| VBPA | Belge muhatapları (partner rolleri) |
| VBFA | Belge akışı |
| VBUK / VBUP | Durum başlık / kalem (S/4'te VBAK/VBAP'a gömülü — teyit et) |
| KONV / PRCD_ELEMENTS | Fiyatlandırma koşulları (S/4 = PRCD_ELEMENTS) |
| IBINOWN → IBIN → IBINVALUES → IBSYMBOL | Kalem varyant konfigürasyonu değerleri (`VBAP-CUOBJ`'tan; INOB DEĞİL; ATINN `IBSYMBOL`'dedir) — zincir: `lovc-belge-konfigurasyonu.md` §2.2 |

## Teslimat
| Tablo | İçerik |
|---|---|
| LIKP / LIPS | Teslimat başlık / kalem |
| VBFA | Sipariş → teslimat → fatura akışı |
| VEKP / VEPO | Elleçleme birimi (HU) başlık / kalem |

## Sevkiyat / taşıma
| Tablo | İçerik |
|---|---|
| VTTK / VTTP | Nakliye başlık / kalem (LE-TRA) |
| VTSP / VTPA | Nakliye aşaması / muhatabı |

## Faturalama
| Tablo | İçerik |
|---|---|
| VBRK / VBRP | Fatura başlık / kalem |

## Ana veri / uyarlama
| Tablo | İçerik |
|---|---|
| KNA1 / KNVV | Müşteri genel / satış alanı (⚠ kişisel veri; okumada `I_Customer` / `I_CustomerSalesArea`) |
| MARA / MARC / MVKE | Malzeme genel / üretim yeri / satış |
| TVAK / TVAP | Satış belge türü / kalem tipi uyarlaması |
| TVLK | Teslimat türü uyarlaması |
| TVCPA | Faturadan satış belgesine kopyalama kontrolü (VTAF) — kaynak fatura türü → hedef satış belge türü (`AUARN`) kaydı. Referanslı talep tasarımında önce ölçülür: `modules/sd.md` SD-K2 notu |
