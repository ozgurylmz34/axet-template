# Üçüncü taraf bildirimleri

Bu depodaki bazı kodlar ve veriler aşağıdaki açık kaynak projelere dayanır. Her birinin lisans metni aşağıdadır.

## 1. abap-adt-api (MIT)

- **Kaynak:** https://github.com/marcellourbani/abap-adt-api
- **Kullanım yeri:** `skills-sap/sap-adt-foundation/scripts/sapadt/lib/sap_adt_lib.py` ve `sap_client.py`. ADT REST çağrı desenleri (kilit/kilit açma, revizyonlar, nesne oluşturma) bu projeye göre Python'da yeniden yazıldı.

```
MIT License

Copyright (c) 2019 Marcello Urbani

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## 2. mcp-abap-adt (MIT)

- **Kaynak:** https://github.com/mario-andreschak/mcp-abap-adt ve onun devamı olan https://github.com/fr0ster/mcp-abap-adt
- **Kullanım yeri:** `skills-sap/sap-adt-foundation/scripts/sapadt/lib/auth/`. Kimlik doğrulama sağlayıcı arayüzü ("mcp-abap-adt reference implementation") Python'da yeniden yazıldı.
- **Sürüm notu:** Hangi deponun hangi sürümüne dayandığı kayıtlı değil. Kod bu depoya 2026-07-08'den önce aktarıldı. O tarihte iki depo da MIT lisanslıydı. İkinci depo 2026-09-03'ten sonra lisansını değiştirdi. Bu değişiklik, daha önce MIT ile alınan sürümleri etkilemez. İki telif bildirimi de aşağıda korunur.

```
MIT License

Copyright (c) 2025 mario-andreschak
Copyright (c) 2025 Oleksii Kyslytsia

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## 3. SAP abap-atc-cr-cv-s4hc (Apache-2.0)

- **Kaynak:** https://github.com/SAP/abap-atc-cr-cv-s4hc (`src/objectReleaseInfo_PCELatest.json`)
- **Kullanım yeri:** `skills-sap/sap-adt-foundation/scripts/sapadt/lib/data/released_successors.json`. Bu dosya kaynak JSON'dan üretildi. Tablo, sınıf, fonksiyon ve arayüz nesneleri için halef listesi, durum, sınıflandırma ve uygulama bileşeni alanları alındı; biçim değiştirildi. Kaynak adresi ve üretim tarihi dosyanın `_meta` alanında yazılıdır.
- **Telif:** Copyright 2020-2025 SAP SE or an SAP affiliate company and abap-atc-cr-cv-s4hc contributors.
- **Lisans metni:** [`LICENSES/Apache-2.0.txt`](LICENSES/Apache-2.0.txt)
