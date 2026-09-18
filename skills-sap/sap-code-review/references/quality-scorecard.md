# Kod kalite karnesi ve kapı defteri

Bir SAP geliştirme işinin sonunda *"bu iş ne kadar güvence altında"* sorusunu **makinenin**
cevaplaması için iki artefakt: **kapı defteri** (ne koştu) ve **karne** (ne anlama geliyor).
Araç: `skills-sap/sap-code-review/scripts/quality_scorecard.py` · testler:
`skills-sap/sap-code-review/tests/test_quality_scorecard.py`.

---

## 1. ⛔ Bu bir GATE değil, RAPORDUR

| | |
|---|---|
| **Kablolanmaz** | Yazma kapısı (`gate.py`), reviewer zinciri (`run_review.py`) ve pre-commit bu aracı **çağırmaz**. Hiçbir akış onun çıkış koduna bakarak durmaz. |
| **Neden** | Yeni bir kapı/gate açmak **ayrı ve açık kullanıcı onayı** ister (gate moratoryumu). O onay YOK. Kural yazmak, kural doğurmasın: önce rapor, gerekirse sonra kapı. |
| **Kendi çıkış kodu** | Aracın kendi sözleşmesidir (aşağıda). Onu okuyup karar veren **insandır**, bir otomasyon değil. |
| **Ölçülür** | `GateDegilRaporTests` template'teki hiçbir **`.py` · `.yml` · `.yaml` · `guncelle/harita.json`** dosyasının bu script'in adını geçirmediğini her koşumda doğrular. Yani "kablolanmadı" bir niyet beyanı değil, **ölçülen** bir olgudur. **KAPSAM: `.md` talimat yüzeyi TARANMAZ** — bir markdown satırı mekanik olarak hiçbir şeyi bloklayamaz (ve `SKILL.md` bu script'i çalıştırmayı zaten tarif eder); tarama "bloklayıcı kablolama" arar, "anılma" değil. |

Birisi bu aracı bir akışa bağlamak isterse: önce kullanıcıdan açık onay, sonra kablolama — ve o
gün `GateDegilRaporTests` bilinçli olarak değiştirilir. Testin sessizce silinmesi = kapının
onaysız açılması.

---

## 2. Kapı defteri (append-only)

JSONL. Her kapı sonucu **bir satır**; satır hiçbir zaman güncellenmez/silinmez — dosya yalnız
`"a"` kipinde açılır (`satir_ekle` tek yazma yoludur; `AppendOnlyTests` bunu hem davranışta hem
kaynak metninde çiviler).

**Yazma kilit altındadır.** `open(…, "a")` Windows'ta süreçler arası atomik DEĞİLDİR: ölçüldü
(6 süreç × 25 `kaydet` = 150 satır, 6 koşum) → 6 koşumun 6'sında satır kayboldu (toplam 11),
**kaybolan çağrıların hepsi `rc=0` döndü** ve dosyada bozuk satır yoktu; yani kayıp hiçbir
kanaldan görünmüyordu ve kaybolan satır bir `fail` ise karne `FAIL` yerine `PASS` derdi. Artık
her yazma `<defter>.lock` üzerinde dışlayıcı bir kilit alır; **kilit alınamazsa yazma YAPILMAZ ve
çıkış kodu 3 döner** (sessiz devam yok). Aynı düzenekle kilit sonrası ölçüm: 6/6 koşumda 0 kayıp.
Kilit süresi `--kilit-saniye` ile ayarlanır. ⚠ `karne` kilit ALMAZ (salt-okur): yazma anında
okunursa yarım satır *bozuk satır* olarak görünür — yani gürültülü, sessiz değil.

Varsayılan yol: `<proje>/.axet-code/quality-gate-log.jsonl` (proje dizini: `AXET_SAP_PROJECT_DIR`
→ yoksa cwd). Proje iskeletinde `.axet-code/` zaten commit dışıdır.

| Alan | Anlamı |
|---|---|
| `ts` | UTC zaman damgası (saniye) |
| `kapi` | kapı adı — **namespace'li** (§4) |
| `sonuc` | `pass` · `fail` · `warn` · `not-run` |
| `artefakt` | **kanıt dosyasının yolu** — `pass` için ZORUNLU; dizin ya da 0 bayt kabul EDİLMEZ |
| `kapsam` | kapsam notu: neye bakıldı, neye **bakılmadı** |
| `test_sayisi` | koşan test sayısı (`0` → `pass` olamaz) · test saymayan kapıda `null` |
| `dar_kapsam` | varsayılan/dar kapsamla mı koşuldu |
| `measured` / `measured_reason` | aracın kendi ölçüm beyanı (§5) |
| `komut` | koşulan komut — kablolama kanıtı |
| `kosum` | koşum kimliği — `--kosum` → env `AXET_KARNE_KOSUM` → üretilir (§3 kapsam süzgeci) |

⛔ Alan adları **kapalı bir kümedir**. `"dar-kapsam"` gibi yanlış yazılmış bir ad düşürme
kurallarını sessizce atlatırdı (ölçüldü) — tanınmayan alan adı artık satırı **geçersiz** kılar.
Tipler de denetlenir: `"0"` (metin), `true` (bool) ve **negatif** `test_sayisi` geçersizdir.

**Defter bir OLAY kaydıdır:** sözleşmeye aykırı bir iddia (ör. artefaktsız `pass`) da yazılır ve
`kaydet` çıkış 2 ile uyarır. Tarih düzeltilmez; üstüne not düşülür.

---

## 3. Karnenin altı değişmezi

| # | Değişmez | Mekanizma | Testi |
|---|---|---|---|
| D1 | **`not-run` ayrı bir durumdur** — sessizce `pass` sayılmaz, karnede ayrı sütundur | `sayim` üç sonucu ayrı tutar; `not-run` varken hüküm `PASS` olamaz | `D1NotRunAyriDurumTests` |
| D2 | **Artefaktsız `pass` geçersizdir** — yol yoksa ya da yol diskte yoksa karne **GÜVENİLMEZ**, çıkış **2** | `_kural_artefakt` | `D2ArtefaktsizPassTests` |
| D3 | **Sıfır test = `warn`** — koşan test sayısı 0 olan kapı `pass` olamaz | `_kural_sifir_test` | `D3SifirTestWarnTests` |
| D4 | **Dar/varsayılan kapsam `pass`'ten `warn`'a düşer** + karneye not | `_kural_dar_kapsam` | `D4DarKapsamWarnTests` |
| D5 | **Boş kapsam beyanı söylenir** — boş beyan okuyucuya *"inceleme her şeyi gördü"* diye okunur | `_kural_kapsam_beyani` | `D5BosKapsamBeyaniTests` |
| D6 | **Arka durak** — doğrulama yalnız yazma anında değil **okuma anında da** koşar: kapı yolundan geçmeden elle eklenmiş satırlar da yakalanır | `karne_uret` her satırı yeniden değerlendirir | `D6OkumaAnindaDogrulamaTests` |

D2 tek başına yeterli değildir; D6 onun **arka durağıdır**: biri `kaydet`'i hiç kullanmadan
deftere satır yazarsa karne yine yakalar.

### Kapsam süzgeci — hangi satırlar okunuyor

Defter büyür ve **eski bir `fail` kalıcıdır**. Okuma tarafında daraltılabilir (defter DEĞİŞMEZ;
süzgeç yalnız okumadadır):

| Komut | Kapsam |
|---|---|
| `karne` | **TÜM DEFTER** — varsayılan bilerek değiştirilmedi (sessiz semantik kayması yok) |
| `karne --kosum <id>` | yalnız o koşumun satırları |
| `karne --since 2026-09-15` | o zaman damgasından itibaren |

Karne çıktısının ilk satırı hangi kapsamı kullandığını söyler (`KAPSAM: kosum=<id> (defterdeki N
satırın M'si)` ya da `KAPSAM: TÜM DEFTER (N satır)`); `--json` içinde `kapsam_suzgeci`,
`okunan_satir`, `toplam_satir` alanları vardır. ⛔ **Bozuk satırlar süzgece tabi değildir**:
ayrıştırılamayan bir satırın `kosum`u da okunamaz ve bütünlük bir koşumun değil, **dosyanın**
özelliğidir. `ts` alanı okunamayan satır `--since` süzgecinde dışarı atılmaz (kanıtı düşürmek,
kanıtı görmezden gelmekten tehlikelidir).

### `pass`'ten düşme sırası

```
sonuc → [şema: ad + tip + negatif] → [artefakt: yok / dosya değil / 0 bayt?]
      → [measured=false → not-run] → [0 test → warn] → [dar kapsam → warn] → [kapsam boş mu]
```
⛔ **Sıra yük taşır ve test edilir.** `artefakt` kuralı `measured`'dan ÖNCE koşar: tersi olursa
artefaktsız bir `pass`, `measured=false` düşürmesiyle `not-run`'a dönüşür ve D2'nin çıkış kodu 2'si
**tamamen baypas** edilir (`KuralSirasiTests` bunu çiviler).

---

## 4. Kapı adları — **koddan türetilir**

Elle tutulan bir kapı listesi bayatlar ve sahte güven üretir. Kayıt defteri her koşumda
diskten/koddan üretilir (`python quality_scorecard.py kapilar`):

| Namespace | Kaynak | Örnek |
|---|---|---|
| `review:<görev>` | `run_review.py` içindeki `TASK_VALIDATORS` anahtarları (dosya **import edilmeden**, `ast` ile okunur) | `review:class_push` |
| `validator:<ad>` | diskteki gerçek `check_*.py` dosyaları | `validator:check_abaplint` |
| `test:<takım>` | diskteki gerçek test takımı dizinleri | `test:skills-sap/sap-code-review/tests` |
| `sap:<araç>` | araç kataloğundaki `adt_*` araçları; `sinif` = okuma\|yazma (`gate.py` içindeki okuma allowlist'inden) | `sap:adt_atc_check` |

Defterde geçen ama kayıt defterinde **olmayan** bir ad karnede `bilinmeyen_kapi` olarak görünür ve
hüküm `PASS` olamaz — var olmayan bir kapı adı, olmayan bir güvencedir.

> ⚠ **`adt_syntax_check` bizde YAZMA sınıfıdır** (SAP'ye gider; okuma allowlist'inde değildir) —
> başka ekosistemlerdeki gibi ücretsiz bir ön kontrol **değildir**. Karne bu sınıftaki kapıları
> ayrıca işaretler (`yazma_sinifi_kapi`). Kapsam/erişim kararını buna göre ver.

Bir kaynak okunamazsa o namespace **sessizce boş kalmaz**: `olculemedi` listesine düşer ve
karnenin KAPSAM BEYANI'nda "ÖLÇÜLEMEDİ" olarak basılır. *Ölçülemedi ≠ temiz.*

---

## 5. `measured` sözleşmesi — icat edilmez, tüketilir

`--durum-ciktisi` ile verilen araç çıktısında
`AXET-GATE-STATUS: gate=… status=… measured=true|false reason=…` satırı aranır (üretici:
`_gate_status.py`). İkinci üretici `abaplint_run.py`'nin `ABAPLINT-RUN-STATUS: … measured=…`
satırıdır. Hükümler `run_review.py` tüketicisiyle **aynıdır** — ve bu eşlik çok-beyanlı iki
fixture ile test edilir (tek-beyanlı girdiler ayrışmayı GÖSTERMEZ):

* **V1 — çok beyan:** kendi gate'i `measured=false`, başka bir gate'in satırı `measured=true` ve
  sonda. `gate=` süzgeci olmadan `true` okunur ve `pass` sessizce ayakta kalırdı; ayrışma tam da
  **false-green** yönündeydi. Süzgeç taşındı: `--gate` verilmezse `--kapi`'nin namespace sonrası
  kullanılır (`validator:check_abaplint` → `check_abaplint`); eşleşme yoksa `run_review` gibi son
  beyana düşülür.
* **V2 — yabancı önek + ABAPLINT:** `<X>-GATE-STATUS: … measured=false` ile
  `ABAPLINT-RUN-STATUS: … measured=true` aynı çıktıda. Yabancı önek dalı artık ABAPLINT dalından
  ÖNCE koşar (fail-closed), yani bayat/yabancı bir kopya kendi `measured=false`'unu gizleyemez.

ABAPLINT dalı `run_review`'da **yoktur** (orası yalnız `-GATE-STATUS:` satırlarına bakar); burada
bilinçli bir genişletmedir ve YALNIZ hiçbir `-GATE-STATUS:` satırı yokken devreye girer — yani
`run_review`'ın hüküm verdiği hiçbir girdide ayrışma üretmez.

| Girdi | Sonuç |
|---|---|
| geçerli beyan, `measured=true` | `measured: true` — satır olduğu gibi kalır |
| geçerli beyan, `measured=false` | `measured: false` → satır **`not-run`**: "koşmadı" ≠ "temiz" |
| satır-başında `AXET-GATE-STATUS:` var ama biçim bozuk | `measured: false`, `reason=bicim-bozuk` (çelişkili beyan ölçüm kanıtı değildir) |
| tanınmayan `<X>-GATE-STATUS:` öneki | `measured: false`, `reason=taninmayan-onek-<X>` |
| **hiç beyan yok** | `measured: null` — varsayım YAPILMAZ ("beyan yok" ≠ "ölçülmedi") |

Ayrıştırıcının dayandığı iki üreticinin bu satırları **hâlâ bastığı** testte ölçülür
(kod ≠ kablolama).

---

## 6. Çıkış kodları

| Alt komut | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| `kaydet` | satır eklendi | — | satır eklendi **ama** sözleşmeye aykırı (kanıtsız `pass`) / deftere yazılamadı | **kilit alınamadı — YAZMA YAPILMADI** |
| `karne` | karne üretildi: `PASS` · `KISMI` · `WARN` · `OLCULMEDI` | defterde `fail` var | **KARNE GÜVENİLMEZ**: kanıtsız `pass` · okunamayan satır · defter yok | — |
| `kapilar` | kayıt defteri basıldı | — | — | — |

**Hüküm önceliği:** `GUVENILMEZ` > `FAIL` > `WARN` > `KISMI` > `PASS`.
`KISMI` = bulunan her şey temiz **ama kapsam eksik**: bilinen kapıların bir kısmı bu kapsamda HİÇ
kaydedilmemiş (`olculmemis=N` alanı sayıyı verir). Çıkış kodu **0 kalır** — eksik kapsam bir
başarısızlık değildir ve `fail`/güvenilmezlik kodlarıyla karışmamalıdır. Gerekçe: `--json`'dan
yalnız `hukum` alan ya da dipnotu okumayan bir tüketici, 90 kapının 1'i ölçülmüşken `PASS`
görmemeli — bu, "ölçülemedi ≠ temiz" kuralının doğrudan karşılığıdır.

Çıkış kodu insan kipinde de makine kipinde de **aynıdır**; fark yalnız görünürlüktedir (insan
kipinde tam genişlikte bir "KARNE GÜVENİLMEZ" bandı basılır). `OLCULMEDI` (defterde hiç satır
yok) bilinçli olarak `PASS` **değildir**: "hiç ölçülmedi" demektir.

---

## 7. Kullanım

```bash
# aynı işin tüm satırlarını GRUPLA — kabuğa bir kez yaz, her `kaydet` bunu alır
export AXET_KARNE_KOSUM="$(date -u +%Y%m%dT%H%M%S)-elle"

# bir kapı koştu, kanıtı dosyaya yazıldı
python -m unittest discover -s skills-sap/sap-code-review/tests > kanit/tests.txt 2>&1
# test sayısını ELLE yazma — bayatlar; koşumun kendi çıktısından türet:
N=$(grep -oE "Ran [0-9]+ tests" kanit/tests.txt | grep -oE "[0-9]+")
python skills-sap/sap-code-review/scripts/quality_scorecard.py kaydet \
    --kapi "test:skills-sap/sap-code-review/tests" --sonuc pass \
    --artefakt kanit/tests.txt --test-sayisi "$N" \
    --kapsam "sap-code-review takımı; canlı SAP ve tarayıcı HARİÇ" \
    --komut "python -m unittest discover -s skills-sap/sap-code-review/tests"

# ölçüm üretemeyen bir kapı (araç yok / bağlantı yok) — stdout'u ver, beyanı kendi okusun
python skills-sap/sap-code-review/scripts/quality_scorecard.py kaydet \
    --kapi validator:check_abaplint --sonuc pass --artefakt kanit/lint.txt \
    --kapsam "2 sınıf" --durum-ciktisi kanit/lint.txt        # measured=false ise satır not-run olur

# karne
python skills-sap/sap-code-review/scripts/quality_scorecard.py karne          # insan, TÜM defter
python skills-sap/sap-code-review/scripts/quality_scorecard.py karne --json   # makine
python skills-sap/sap-code-review/scripts/quality_scorecard.py karne --kosum "$AXET_KARNE_KOSUM"
python skills-sap/sap-code-review/scripts/quality_scorecard.py karne --since 2026-09-15

# hangi kapılar biliniyor (kaydedilmemişleri görmek için)
python skills-sap/sap-code-review/scripts/quality_scorecard.py kapilar
```

---

## 8. KAPSAM BEYANI — karne neye BAKMAZ

Karne her koşumda (özellikle **sıfır bulgu** anında) neye baktığını *ve neye bakmadığını* basar.
"Bakılanlar" listesi kural tablosundan **türetilir**, elle yazılmaz (test: kural sayısı ile beyan
sayısının eşitliği ölçülür). ⚠ "Bakılmayanlar" listesi ise **elle bakımlıdır** — yeni bir kör
nokta doğduğunda oraya yazılması insana kalmıştır; kod bunu zorlayamaz.

Bakmadıkları:

* **artefaktın içeriği** — yalnız yolun diskte **varlığı** ölçülür, gövdesi okunmaz;
* **kapının gerçekten koşup koşmadığı** — defter bir **beyan** kaydıdır, koşum kanıtı artefakttır;
* **`dar_kapsam` bayrağı verilmediyse** kapsam daralması (kapsam metni serbest metindir, ayrıştırılmaz);
* **canlı sistem durumu** — araç ağ kullanmaz, hiçbir şeyi yeniden koşmaz;
* **defterin tamlığı** — "kaydedilmemiş kapı" yalnız bilinen kapı listesine göre sayılır.

## 9. Bilinen sınırlar

* Defter **imzasızdır**: satırlar diskte elle düzenlenebilir. Değişmezler düzenlenmiş satırlarda da
  koşar (D6) ama bir satırın *silinmesi* tespit edilemez — bu araç bir bütünlük mührü değildir.
* **Artefakt yolu, karneyi koşan yorumlayıcının gördüğü biçimde olmalıdır.** Windows'ta bir
  kabuğun ürettiği `/tmp/...` biçimli yol Python'a görünmez → karne onu "artefakt diskte YOK"
  sayar (ölçüldü). Göreli yol yaz ya da `--artefakt-kok` ver.
* **Bayraksız `karne` TÜM geçmişi sayar**: eski bir koşumun `fail`i kalıcıdır. Kapsamı `--kosum`
  ya da `--since` ile daralt; hangi kapsamın kullanıldığı çıktının ilk satırındadır.
* Karne, kapıların **önem derecesini** (BLOCKER/WARNING) bilmez; `run_review.py` hükmü ayrı bir
  kanaldır ve bu araç onun yerine geçmez.
* Sıfır genişlikli/görünmez karakterlerden (ör. U+200B) oluşan bir `kapsam` notu D5'i atlatır —
  bugün yalnız boşluk kırpması yapılır. **AÇIK KALEM** (bilinçli, bu turda kapatılmadı).
* Kapı kayıt defteri **kısmen** küçülürse (bir `check_*.py` silinirse) bu sessizdir: kapı
  listesinden düşer ve "kaydedilmemiş" sayısı azalır. **AÇIK KALEM**.
* Kural imzalarındaki `kok` parametresini 6 kuralın 5'i kullanmıyor; **`_kural_artefakt` KULLANIYOR**
  (`quality_scorecard.py:261` — göreli artefakt yolunu `Path(kok) / yol` ile çözer, yukarıdaki
  `--artefakt-kok` maddesinin dayandığı davranış budur). Ölü parametre DEĞİLDİR: kaldırılırsa
  göreli artefakt çözümü ölür (ölçüldü — cwd değişince aynı defter `rc=0` yerine `rc=2` verir).
* `test_sayisi` ve `dar_kapsam` **kaydedene** güvenir; yanlış bildirilirse karne bunu göremez —
  yalnız **tipi** denetlenir (`"0"` metin olarak yazılıp D3'ün atlatılması şema ihlalidir ve
  satırı geçersiz kılar; ölçüldü).
