# Belge ↔ canlı teyit turu (TS build'e girmeden önce)

> **Kural:** teknik tasarım dokümanı build'e girmeden önce içindeki her **"canlıda mevcut / kurulu / bağlı / zaten yapıldı /
> yapılacak"** iddiası **ölçülür**. Ölçülmemiş canlı iddia, dokümanın geri kalanı kusursuz olsa da build'i yanlış yöne sokar:
> geliştirici onu veri olarak okur.
> **Ne zaman:** TS mutabakatından sonra, build'den önce. **Çıktı:** ölçüm tablosu + çürüyen her iddia için doküman düzeltmesi +
> ikinci kapı (`doc-checklist.md`). Kontrol listesinde **DOC-CR-03**.

**Neden var:** kaynak vakada bir RAP TS'i için koşulan tur 7 bulgu üretti; üçü dokümanın normatif iddiasını çürüttü — yeniden
kullanılacak FM'in imzası dokümanın kendi kuralını ihlal ediyordu ve gövdesi boştu · "yapılacak" denen uyarlama adımlarının
dördü DEV'de zaten yapılmıştı · "geri dönüşün son noktası" denen eşik zaten geçilmişti. Hiçbiri dokümanı okuyarak görülemezdi.

## Kim koşar
- Yazardan bağımsız bir göz tercih edilir. aXet'te: ölçümü ana oturum koşar ya da `agent` aracına devreder; devirde brifinge
  `%sap-dev` → `references/role-briefs.md` **S1** (kesin yasaklar) + **S2** (yalnız okuma sınıfı CLI) + **S4** blokları ve bu dosyanın
  §1 tablosu **metin olarak** yapıştırılır. Alt ajanın `bash` ile CLI çağırabildiği bu template'te ölçülmedi (DOĞRULANMADI);
  çağıramıyorsa ölçümü ana oturum yapar, **değerlendirmeyi** taze inceleyici ölçüm çıktısı üzerinden yapar.
- Yalnız **okuma sınıfı** araçlar. Yazma sınıfı araç (`adt_syntax_check` ve `adt_classrun` dahil) bu turda çağrılmaz.
- SAP bağlantısı yoksa (`.conn` dosyası yok, `ping` başarısız) tur **koşulamaz**: rapora beş başlığın hepsi "ÖLÇÜLEMEDİ — bağlantı
  yok" yazılır ve TS durumu "canlı teyit bekliyor" olur. Build kapısı açılmaz.

Çağrı biçimi: `python <TEMPLATE>/skills-sap/sap-adt-foundation/scripts/sap_adt_cli.py <araç> --args-json '<json>'`
(araç adları ve argümanlar için otorite `--list` ve `references/tool-catalog.md`).

## 1. Ölçüm başlıkları (beşi de koşulur; atlanan "ÖLÇÜLMEDİ" yazılır)
| # | Başlık | Ne ölçülür | Yöntem ve tuzak |
|---|---|---|---|
| C-1 | **Ad çakışması** | yaratılacak denen her ad canlıda gerçekten boş mu; mevcut denen her ad gerçekten var mı | `adt_search_objects {"query":"<AD veya ÖNEK*>","max_results":200,"object_type":"<CLAS/DDLS/TABL/…>"}` + `adt_package_contents {"package":"<PAKET>"}`. ⛔ **Pozitif kontrol zorunlu:** önce var olduğu bilinen bir adla aynı aramayı koş ve bulduğunu göster; yoksa "bulunamadı" "yok" değil "arama çalışmadı" olabilir. `count == max_results` → kırpılmış olabilir. `type_filter_dropped > 0` ya da `warning` varsa `count:0` kanıt değildir. Tablo/yapı için `adt_get` tek başına yeterli değil, arama ile çapraz kontrol |
| C-2 | **Reuse iddiaları** | "şu FM/sınıf/CDS yeniden kullanılacak" denen her obje: var mı · **imzası dokümanın kendi kuralına uyuyor mu** · **gövdesi dolu mu** | `adt_get {"name":"<AD>","object_type":"<tip>","include_source":true}` ile **kaynağı** oku (FM: `"object_type":"func"`; sınıf uygulaması `ccimp`). ⛔ Varlık ≠ kullanılabilirlik: obje aktif görünüp gövdesi boş olabilir. Tüketicisi varsa `adt_where_used` (FM çağıranı için `foundation-query.md` §3.3). Not: kaynak okuması yerel `.axet-code/sap-pull-state.json` kaydı yazar (yalnız yerel; SAP'ye yazma değildir) |
| C-3 | **Uyarlama durumu** | "yapılacak" denen her uyarlama adımı DEV'de zaten yapılmış olabilir; "hazır" denen yapılmamış olabilir | ilgili uyarlama tablosunu oku: `adt_sql_query {"query":"SELECT <alanlar> FROM <tablo> WHERE <anahtar>","row_limit":100}` (ya da `adt_table_read`). ⛔ İki yön de koşulur (eksik mi · zaten var mı). `truncated:true` → kırpılmış (alan kesindir; tam `row_limit` satır kırpık sayılmaz). Tablo/alan adı tahmin edilmez: dokümandan ya da sistemden okunur. QA/PRD'de hassas tablo → KVKK onayı (SAP çekirdeği) |
| C-4 | **Paket / inaktif** | objeler doğru pakette mi; sessiz inaktif obje var mı | `adt_package_contents {"package":"<PAKET>"}` (`package_verified:false` → ad desenli yedek arama, başka paket objeleri karışabilir) + `adt_inactive_objects {}` (`count_verified` alanına bak; `ok:false` → ÖLÇÜLEMEDİ). ⛔ "Aktif" metadata'sı ≠ kodun aktif sürümü |
| C-5 | **Transport** | açık istek var mı, hangi objeleri taşıyor | ⛔ `adt_transport_list` sıfırı kanıt değildir (`zero_verified` hiç `true` olmaz; açık kayıt varken 0 döndüğü ölçüldü). `adt_sql_query` ile `E070` (`TRKORR`, `TRSTATUS`, `TRFUNCTION`, `STRKORR`) ve içerik için `E071` (`TRKORR`, `PGMID`, `OBJECT`, `OBJ_NAME`); JOIN tek sorguda reddedilirse iki sorguya böl (`foundation-ops.md`). Transport **yaratılmaz**, "yok" okuması yeni transport açma refleksine götürmez (Yasak C). Kullanıcı adı kolonu kişisel veridir: rapora yazılmaz |

Her araç yanıtında `ok:false` ya da üç değerli alanda `null` → o iddia **ÖLÇÜLEMEDİ** (ne "doğru" ne "yanlış").

## 2. Rapor biçimi (TS'e EK olarak işlenir)
| İddia (TS §) | Başlık | Ölçüm (araç + argüman) | Dönen değer (özet) | Sonuç | Doküman etkisi |
|---|---|---|---|---|---|
| §3 "`ZCA000_CL_DEMO_ONAY` yeni yaratılacak" | C-1 | `adt_search_objects {"query":"ZCA000_CL_DEMO*"}` (pozitif kontrol: `ZCA000_CL_BILINEN` → count 1) | count 0 | DOĞRULANDI — ad boş | yok |
| §5.2 "reuse: `Z_DEMO_FM`" | C-2 | `adt_get {"name":"Z_DEMO_FM","object_type":"func","include_source":true}` | exists true, gövde boş | ÇÜRÜDÜ — gövde boş | §5.2 yeniden yazıldı, reuse iptal |

- "Doğrulandı" demek için **çıktı** gerekir: çağrı + dönen değer. "Okudum, doğru" kanıt değildir.
- Çürüyen iddia dokümanı düzeltir; düzeltme **ikinci kapıyı** tetikler (değişen satırlar + değişen ad/sayının diğer geçtiği yerler +
  kararın yayılım listesi).
- Ölçülemeyen başlık "ÖLÇÜLEMEDİ" yazılır, sessizce atlanmaz. Rapor tarih taşır; aradan zaman geçip build başlamadıysa C-1/C-4/C-5
  yeniden koşulur (canlı durum değişir).
- İlgili: TS İlke 5 (build-time teyit ≠ fonksiyonel karar) · `doc-checklist.md` DOC-CR-03.
