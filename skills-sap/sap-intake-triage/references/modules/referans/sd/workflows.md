# SD — iş akışları (referans)

## Siparişten tahsilata (genel)
```
Satış belgesi (VA01)  →  Teslimat (VL01N)  →  Toplama / WM (LT03)
   →  Mal çıkışı (VL02N)  →  Fatura (VF01)  →  Muhasebe (FI)
```
Belge akışı: `VBFA` (her adım öncülünün referansını taşır).

## Teslimat / sevkiyat
```
Teslimat (LIKP/LIPS)  →  Konteyner / HU (VEKP/VEPO)
   →  Nakliye (VTTK/VTTP, LE-TRA)  →  Çıktı (ör. e-İrsaliye — SAP Document Compliance)
```

## Önemli akış kuralları
- Sipariş → teslimat → fatura kopyalama kontrolü (VTLA/VTFL) tutarlı olmalı; faturadan referanslı talep VTAF ister
  (`spro.md`).
- Mal çıkışı stok + FI hareketi yaratır; geri alma VL09.
- Z katmandan teslimat yazımı: ⛔ kesin yasak B — LIKP/LIPS'e doğrudan SQL yok; released API / BAPI
  (`BAPI_OUTB_DELIVERY_*`) — yol seçimi `%sap-dev` → `references/write-api-selection.md`.
- Bir belgeye bağ alanıyla (VGBEL / AUBEL / hizmet tarihi) eşleştiren kural yazmadan önce o alanın **gerçek belgelerdeki
  doluluğu** ölçülür (ekip dersi, 2026-10-17: mevcut fark taleplerinin tamamı referanssızdı — VGBEL boş — ve kural hiçbir
  belgeyi yakalamıyordu). Boşsa eşleştirme anahtarı (org + müşteri + malzeme + dönem) yeniden kurulur.
