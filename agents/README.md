# aXet özel ajanları (aXet.code ≥ 1.5.1)

Bu klasördeki `sap-*.md` dosyaları aXet.code'un **kullanıcı ajanı** tanımlarıdır. `scripts/install.py --sap` bunları
kullanıcı ajan dizinine (`<config tabanı>/axet-code/agents`; `AXET_AGENTS_DIR` tanımlıysa orası) yazar ve gövdedeki
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

**Sınırlar (bilinçli):** "dosya düzenleme araçları kapalı" = `disallowedTools: [edit, multiedit, write]`; `bash` açıktır,
yani salt okuma araçla değil istemle sağlanır. Sahiplik işareti hangi klonun kurduğunu ayırmaz: aynı makinede
ikinci bir klonda (ya da worktree'de) `install.py --sap` koşulursa ajanlar o klona yönlenir, `--no-sap`/`--uninstall`
işaretli ajanları hangi klon kurmuş olursa olsun kaldırır (global config ile aynı davranış). Ana klonda
`install.py --sap` (ya da `%guncelle`) ajanları geri yönlendirir.
