# aXet özel ajanları (aXet.code ≥ 1.5.1)

Bu klasördeki `sap-*.md` dosyaları aXet.code'un **kullanıcı ajanı** tanımlarıdır. `scripts/install.py --sap` bunları
motorun kullanıcı ajan dizinine yazar — sıra: `AXET_AGENTS_DIR` → `XDG_CONFIG_HOME/axet-code/agents` → Windows'ta
`%LOCALAPPDATA%\axet-code\agents` → (Windows dışı, XDG yoksa) `~/.config/axet-code/agents` (Windows sırası ölçüldü
1.5.1, `axet-code dirs`; global config dosyası `~/.config/axet-code`'da kalsa da Windows'ta ajanlar oradan okunmaz;
Windows dışı yol ölçülmedi, varsayımdır) — ve gövdedeki
`{{AXET_KLON}}` yer tutucusunu bu klonun mutlak yoluyla değiştirir. Dosyalar yalnız rol tanımıdır; rolün ayrıntılı
kuralları skill referanslarında durur (tek kaynak), ajan gövdesi oraya yönlendirir.

| Ajan | Kip | Ne zaman |
|---|---|---|
| `sap-arastirma` | alt ajan, dosya düzenleme araçları kapalı | canlı obje haritası, etki alanı, spesifikasyon/eski kaynak incelemesi |
| `sap-backend` | alt ajan | ABAP/CDS/RAP/DDIC kaynağını yerel dosyada hazırlama (SAP'ye yazmaz) |
| `sap-ui5` | alt ajan | freestyle UI5 kaynağını yerel dosyada hazırlama (deploy etmez) |
| `sap-inceleme` | alt ajan, dosya düzenleme araçları kapalı | değişikliğin bağımsız incelemesi (PASS / WARNING / BLOCKER) |
| `sap-gelistirme` | ana ajan, fazlı | her talepte önce kapsam sınıflaması (intake), sonra uygulama |

Ölçülen davranış (aXet.code 1.5.1, `docs/axet-davranis-olcumleri.md`): özel alt ajan, yerleşik `task` ajanından farklı
olarak çekirdek kuralları, ekip hafızasını ve proje `AGENTS.md`'sini **görür**; fazlı ana ajanın fazları her kullanıcı
mesajında baştan başlar. `sap-gelistirme` varsayılan ajan yapılmaz — kullanıcı `--agent sap-gelistirme` ile ya da
TUI'de ajan değiştirerek seçer. SAP'ye yazma her rolde ana oturumun `%sap-adt-foundation` yazma kapısından geçer.

**Eski konum (v0.5.22):** v0.5.22 Windows'ta ajanları `~/.config/axet-code/agents`'a yazıyordu; motor orayı okumadığı
için `agent list`'te görünmüyorlardı. Kurulum ve `%guncelle` o dizindeki **işaretli** kopyaları kaldırır, ajanları doğru
dizine yazar; doctor eski konumda kopya görürse uyarır.

**Motor sürümü:** kurulum `axet-code -v` ile motoru ölçer. 1.5.1'den eski motorda ajanlar **kurulmaz** (1.3.0'da
çalışmadıkları ölçüldü, aradaki sürümler ölçülmedi) ve `AJANLAR: ATLANDI — aXet.code <sürüm> < 1.5.1: … güncelle, sonra
aXet'te %guncelle yaz …` satırı basılır; doctor aynı durumda tek uyarı verir. Daha önce kurulmuş kopyalar diskte kalır,
motor onları kullanmaz. Motor güncellenince bir sonraki `%guncelle` ajanları kurar. Sürüm ölçülemezse
(motor PATH'te yok, çıktı çözülemedi) kurulum sürer, satırda "sürümü ölçülemedi" yazar. Kaldırma
(`--no-sap`/`--uninstall`) motor sürümüne bakmaz.

**Belge okuma izni:** dört alt ajanın (`sap-arastirma`, `sap-backend`, `sap-ui5`, `sap-inceleme`) frontmatter'ında
`permission:` altında `read_docx`, `read_xlsx` ve `read_pdf` `allow`'dur. Ölçüldü (aXet.code 1.5.1, `run` kipi): bu blok
yokken özel alt ajanın `read_docx` çağrısı ana ekranda görünmeyen izin sorusunda asılı kaldı (3/3, >290 sn zaman aşımı).
Kontrollü deney: aynı deneme ajanı blok olmadan 290 sn zaman aşımına düştü, blokla belgeyi okuyup 41 sn'de bitti.
Yazım, ölçülen deneydeki biçimdir (`<araç>: allow`). Motor referansına göre bu alan izin katmanlarının sonuncusudur; alt
ajanın kuralları üst oturumunkiyle kesiştirilir, iki taraftaki `deny` de geçerli kalır. `bash` ve yazma araçlarına izin
eklenmez. Ana ajan `sap-gelistirme` bu bloğu TAŞIMAZ: ölçülen sorun yalnız alt ajanın asılmasıydı; ana ajana `allow`
vermek kullanıcının config'teki `read_*` kuralını ezebilir (ölçülmedi).
⚠ **Bu izin yol sınırı taşımaz:** alt ajan proje dışındaki `.docx`/`.xlsx`/`.pdf`'i de sormadan okur (ölçüldü yalnız
`.docx` ile, `run` kipi: proje içi ve proje dışı belge okundu, soru gelmedi; `.xlsx`/`.pdf` ve TUI ölçülmedi).
Bilinçli: kullanıcı belgeleri çoğunlukla proje dışındadır (ör. İndirilenler) ve yol sınırı asılma sorununu geri
getirir; araçlar salt okur. Kimlik dosyası denemesinde (sahte `.conn_adt`) `read_docx` yalnız "zip: not a valid zip
file" hatası verdi, içerikten bayt dönmedi.
Yerleşik `task` ajanında `read_*` araçları hiç yoktur; ikili belgeyi alt ajana yol olarak verme (çekirdek §7).

**Sınırlar (bilinçli):** "dosya düzenleme araçları kapalı" = `disallowedTools: [edit, multiedit, write]`; `bash` açıktır,
yani salt okuma araçla değil istemle sağlanır. Sahiplik işareti hangi klonun kurduğunu ayırmaz: aynı makinede
ikinci bir klonda (ya da worktree'de) `install.py --sap` koşulursa ajanlar o klona yönlenir, `--no-sap`/`--uninstall`
işaretli ajanları hangi klon kurmuş olursa olsun kaldırır (global config ile aynı davranış). Ana klonda
`install.py --sap` (ya da `%guncelle`) ajanları geri yönlendirir.
