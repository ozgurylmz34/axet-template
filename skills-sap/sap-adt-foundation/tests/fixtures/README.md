# Validator bad/good fixture çiftleri

Her validator için `<validator_adı>/{bad,good}/` altında gerçekçi bir mini **proje kökü** durur
(`SOURCE_CODES/...`). Bu dizin validator alt sürecine `AXET_SAP_PROJECT_DIR` ile verilir; validator
böylece kendi normal (argümansız, proje geneli tarama) kipinde koşar:

- `bad/`  → validator **FAIL** vermeli (exit 1) ve çıktısında `[İHLAL]` satırı olmalı
- `good/` → validator **PASS** vermeli (exit 0), `[İHLAL]` satırı olmamalı

Koşucu: `tests/test_validator_fixtures.py` (foundation takımının parçası).

**Neden ikisi birden:** yalnız `good` koşmak validator'ın hiçbir şey yapmadığını da "geçti" sayar;
yalnız `bad` koşmak da her girdiye FAIL diyen bir validator'ı yakalamaz. Çift, kontrol grubudur.

**İçerik kuralı:** fixture'lar gerçek sistem/kullanıcı/müşteri adı İÇERMEZ — jenerik `ZSD001` /
`ZTEST` ad alanı kullanılır.

Kaynak: bu çiftler kaynak çekirdeğin `tests/fixtures/<validator>/{bad,good}` korpusundan aXet
yerleşimine uyarlandı (yol düzeni ve `AXET_SAP_PROJECT_DIR` env adı aXet'inkidir).
