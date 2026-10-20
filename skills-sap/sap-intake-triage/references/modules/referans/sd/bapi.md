# SD — BAPI / RFC FM (referans)

> ⛔ Kesin yasak B: standart belgeye (VBAK/LIKP …) doğrudan `INSERT/UPDATE/MODIFY` yok. Yazma yolu sırası ve karar ağacı
> **tek yerde** yaşar: `%sap-dev` → `references/write-api-selection.md` (released API → BAPI → RFC FM → BDC → manuel).
> Aşağıdaki adların o sistemde released olup olmadığını teyit et (clean core). RAP handler'dan commit'li BAPI ayrı LUW ister
> (modül paketi SD-K5, `%sap-code-review` BE-26).

## Satış siparişi
| BAPI | İş |
|---|---|
| BAPI_SALESORDER_CREATEFROMDAT2 | Sipariş yarat |
| BAPI_SALESORDER_CHANGE | Sipariş değiştir |
| BAPI_SALESORDER_SIMULATE | Sipariş simülasyonu (fiyat / ATP) |
| BAPI_TRANSACTION_COMMIT / _ROLLBACK | LUW kapanışı |

## Teklif + varyant konfigürasyonu (klasik LO-VC)
| BAPI | İş |
|---|---|
| BAPI_QUOTATION_CREATEFROMDATA2 | Teklif yarat (FG SAPL2031). ⚠ Yalnız `BAPI_CUSTOMERQUOTATION%` deseniyle aranırsa bulunmaz |
| BAPI_CUSTOMERQUOTATION_CHANGE | Teklif değiştir; `CFGS_*` tablolarıyla konfigürasyon değeri — motoru koşturur. ⚠ POSEX boş/eşleşmez = SESSİZ ATLAMA · tam kullanıcı kümesi gönder · türetilmiş değeri gönderme: `lovc-belge-konfigurasyonu.md` §5 |

## Teslimat
| BAPI / FM | İş |
|---|---|
| BAPI_OUTB_DELIVERY_CREATE_SLS | Satıştan çıkış teslimatı |
| BAPI_OUTB_DELIVERY_CREATE_STO | Depolar arası nakil siparişinden teslimat |
| BAPI_OUTB_DELIVERY_CHANGE | Teslimat değiştir (mal çıkışı, toplama, yük) |
| BAPI_OUTB_DELIVERY_CONFIRM_DEC | Merkezi olmayan depo teyidi |
| GN_DELIVERY_CREATE | Klasik teslimat yaratma (eski; ECC dönemi kodda görülür) |
| WS_DELIVERY_UPDATE | Klasik teslimat güncelleme |

⚠ Teslimat yaratan **yol** genişletmenin koşup koşmadığını belirler: OData `API_OUTBOUND_DELIVERY_SRV` deep-create, VL01N'in
geçtiği noktadan geçmez (`enhancements.md` "Teslimat yaratma yolları").

## Faturalama
| BAPI | İş |
|---|---|
| BAPI_BILLINGDOC_CREATEMULTIPLE | Fatura yarat |

## Nakliye (LE-TRA)
| BAPI | İş |
|---|---|
| BAPI_SHIPMENT_CREATE / _CHANGE | Nakliye belgesi |

## Released / RAP (S/4 — tercih)
- `I_SalesOrderTP` (RAP BO), `API_SALES_ORDER_SRV` (OData).
- `I_OutboundDelivery*` released CDS — okuma / dışa açma.
- Released kontrolü: `%sap-adt-foundation` (released ardıl tablosu, `adt_get`) — ad benzerliğine bakıp "released" yazma.
