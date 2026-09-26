# SAP profil yetenek matrisi — rehber (canlı test gerekir)

> ⚠ **MATRİS REHBERDİR, KANIT DEĞİLDİR.** Bir hücreye dayanarak "bu profilde çalışır / çalışmaz" deme; iddiayı
> canlı testle doğrula (ders: sürüm numarasından çıkarım canlı aktivasyonla çürüyebilir). `ecc`, `s4_public`,
> `btp_abap` sütunları kaynakta **iskelettir** (ilk o profilli projede doldurulur); yalnız `s4_private` dolu
> ve mevcut kanıtlı deneyim bu profildendir.
>
> Kaynak: ekip metodolojisinin profil YAML'ları (`s4_private` "DOLU", diğer üçü "İSKELET — LAZY"). Profil
> `sap-project.json` → `sap_profile` alanından okunur; alan yok/geçersizse CLI fail-closed davranır.

## 1. Yetenekler (kaynak matris)

| Yetenek | `ecc` (iskelet) | `s4_private` (dolu) | `s4_public` (iskelet) | `btp_abap` (iskelet) |
|---|---|---|---|---|
| RAP | none (ECC'de yok) | preferred | required | required |
| ABAP Cloud | none | available (2022+) | only | only |
| Klasik Dynpro | primary | allowed (policy strict → yasak) | forbidden | forbidden |
| Klasik rapor | primary | allowed | forbidden | forbidden |
| SEGW OData | available (NW 7.31+) | allowed | forbidden | forbidden |
| CDS | by_release (7.31 yok · 7.40 sınırlı · 7.50 kullanılabilir) | full | cloud_flavor | cloud_flavor |
| AMDP | by_db (yalnız HANA) | available | restricted | — |
| Yalnız released API | false | false (tercih edilir) | true (platform zorlar) | true |
| Standart tabloya doğrudan yazma | forbidden (Yasak B) | forbidden (Yasak B) | platform_blocked | — |
| SAP GUI | available | available | none | none |
| Transport | cts | cts | cloud_ts (canlı doğrulanmadı) | gcts |
| ADT kimlik | basic | basic (+ kurumsal SAML/SSO) | sso | sso |
| Yerel S/4 nesnesi | — | — | var | none (yalnız remote released API) |

**Sürüm/politika farkları (yalnız `s4_private` ve `ecc`):**
- `s4_private` 1909 → `abap_cloud: none`, `rap: available`; 2020/2021 → `abap_cloud: none`; 2022+ fark yok.
- `s4_private` `cleancore_policy`: `strict` → klasik Dynpro yasak + yalnız released API · `balanced` → matris
  varsayılanı · `classic` → RAP tercih baskısı kalkar.
- `ecc` `db`: `hana` → AMDP var · `anydb` → AMDP yok (anyDB'de AMDP önermek hatadır).

## 2. CLI profil etiketleri (kod bu tabloyla test edilir)

CLI araçları `@profil_tool(available_on=…)` etiketi taşır; profil uymuyorsa çağrı ağdan önce
`tool_not_available_for_profile` (çıkış 2) ile reddedilir. Etiketsiz (`all`) araçlar her profilde açıktır —
bu, **o profilde çalıştığının kanıtı değildir**. Aşağıdaki blok `tests/test_conn_tools.py` tarafından koddaki
kayıt defteriyle (`REGISTRY`, `_profile.TIP_PROFIL_KISITI`) birebir kıyaslanır; kod değişirse test kırılır.

<!-- CLI-ETIKETLERI -->
| Araç / tip | Açık olduğu profiller | Dayanak |
|---|---|---|
| `adt_msgclass_write` | s4_private | reçetenin ölçüldüğü profil (`tools/msgclass.py`) |
| `adt_screen_generate` | ecc, s4_private | klasik Dynpro/CUA yalnız bu profillerde (matris §1) |
| `adt_set_description` | s4_private | envelope PUT reçetesinin kanıt profili; ölçüm yalnız DDLS (`tools/description.py`) |
| `adt_table_create` | s4_private | kabuk + kilitli DDL reçetesinin kaynak profili (`tools/ddic.py`); aXet'te canlı DOĞRULANMADI |
| `adt_textpool_read` | s4_private | yazma aracıyla aynı uç ve Accept reçetesi (`tools/textpool.py`, okuma; Z39 kalanı) |
| `adt_textpool_write` | s4_private | REPT kilidi + PX aktivasyonu reçetesinin kaynak profili (`tools/textpool.py`); canlı DOĞRULANMADI |
| `adt_ttyp_create` | s4_private | tablo tipi + DD40L readback reçetesinin kaynak profili (`tools/ddic.py`); canlı DOĞRULANMADI |
| `adt_transport_list` | ecc, s4_private, s4_public | `btp_abap` transport = gcts → CTS ucu yok |
| tip `functiongroup` | ecc, s4_private | klasik FUGR/FM ABAP Cloud profillerinde açılmaz (`adt_post_shell`, `adt_push_source`) |
| tip `function` | ecc, s4_private | aynı |
<!-- CLI-ETIKETLERI -->

## 3. Nasıl kullanılır

1. Bir iş türüne başlamadan önce §1'de profil hücresine bak → `forbidden`/`none` ise kullanıcıya söyle, alternatif öner
   (ör. `s4_public`'te klasik rapor yerine RAP + CDS).
2. Hücre `allowed`/`available` diyorsa bu **izin değil ön bilgidir**: ilk kullanımda küçük, geri alınabilir bir canlı
   denemeyle doğrula ve sonucu projenin notlarına yaz.
3. CLI bir aracı reddederse (`tool_not_available_for_profile` / `type_not_available_for_profile`) etiketi aşmaya çalışma;
   `sap-project.json` profili yanlışsa kullanıcıya düzelttir.

## 4. Doğrulanmamış / açık

- `ecc`, `s4_public`, `btp_abap` sütunlarının hiçbir hücresi aXet'te canlı test edilmedi (DOĞRULANMADI).
- `s4_public` `cloud_ts` taşıma akışı ve SSO kimlik yolu canlı doğrulanmadı; CLI'nin basic-auth dışı yolu bu profillerde
  denenmedi.
- Etiketsiz araçların `s4_public`/`btp_abap`'ta davranışı ölçülmedi (released-only kısıtları uçlarda farklı yanıt verebilir).
