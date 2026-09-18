# Aylık Stok Raporu

Bu belge **örnek** amaçlıdır: *İstanbul* deposu, `ZCA000_CLC` paketi ve [abapGit](https://docs.abapgit.org/) bağlantısı.

## Özet

- Toplam malzeme: 3
  - Çelik vida
  - Şaft ğ ü ş ı İ ö ç
- Açık kalem: 0

1. Profille
2. Karşılaştır

| Malzeme | Açıklama | Miktar |
|:--------|:--------:|-------:|
| 000010 | Vida \| M8 | 12,5 |
| 000020 | Somun | 3 |

> Not: müşteri TCKN 10000000146, VKN: 1234567890 ve IBAN TR33 0006 1005 1978 6457 8413 26 maskelenmelidir; belge no 0080001234 kalmalıdır.

```abap
SELECT matnr FROM mara INTO TABLE @DATA(lt_mara) UP TO 5 ROWS.
```

![Ekran görüntüsü](ekran.png)

<!-- pagebreak -->

## Ek

---

Son satır \*yıldız\* kaçışı ve snake_case_ad.
