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

## 4. mattpocock/skills — diagnosing-bugs (MIT)

- **Kaynak:** https://github.com/mattpocock/skills (`skills/engineering/diagnosing-bugs/SKILL.md`, commit `f3fc5632f401156837ee3872f14fe33ccf1024ea`)
- **Kullanım yeri:** `skills/diagnosing-bugs/SKILL.md` ve `skills/diagnosing-bugs/references/dongu-adaylari.md`. Kaynak metnin Türkçe çeviri-uyarlamasıdır: faz yapısı ve birçok madde çevrildi; aXet'in SAP araçları, yazma kapısı, SAP kesin yasakları, kanıt kuralları ve kök neden (RCA) hipotez tablosu eklendi. Yalnız `SKILL.md` metni alındı; kaynak dizindeki betikler ve ajan tanımları alınmadı. Alınan metin düz markdown'dır; çalıştırılabilir parça, ağ çağrısı ya da gizli veri okuma içermez.

```
MIT License

Copyright (c) 2026 Matt Pocock

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

## 5. SAP/styleguides — Clean ABAP (CC BY 3.0)

- **Kaynak:** https://github.com/SAP/styleguides (*Clean ABAP*)
- **Kullanım yeri:** `skills-sap/sap-dev/references/clean-abap.md`. Rehberden seçilmiş kuralların kendi cümlelerimizle yazılmış, değiştirilmiş özetidir: metin kopyalanmadı; bu template'in kurallarıyla çelişen öneriler ayıklandı ya da daraltıldı (dosyanın §1 tablosu değişiklikleri listeler). Rehberin tamamı ve özgün metin için kaynağa bakın.
- **Telif:** Copyright 2019-2021 SAP SE or an SAP affiliate company and styleguides contributors. (Kaynak: deponun REUSE kaydı `.reuse/dep5`, `Files: *` — https://github.com/SAP/styleguides/blob/main/.reuse/dep5; 2026-10-19'da okundu.)
- **Lisans:** Creative Commons Attribution 3.0 — https://creativecommons.org/licenses/by/3.0/
