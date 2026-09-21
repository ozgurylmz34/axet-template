# Mesaj sınıfı (MSAG)

> Kaynak: ekip ADT playbook'unun mesaj sınıfı bölümleri (yazma + okuma); aXet CLI'ye uyarlandı.
> Adlandırma: `ZSD001_MSG` (`%sap-dev` → `naming.md` §4.7; `_MSG` eksiz eski sınıflar ihlal sayılmaz, yeniden adlandırılmaz).
> Standart mesaj sınıfını değiştirmek kesin yasak A'dır. Ölçümler S/4HANA (`s4_private`) sistemlerde yapıldı.

---

## 1. Okuma — CLI
```
cli adt_msgclass_read '{"name":"ZSD001_MSG"}'
```
- Dönüş: `{ok, name, exists, master_language?, description?, count?, messages:[{no, text, selfexplanatory, documented}]}`; metin master dilde, `&` çözülmüş.
- `adt_get` `msag` bu araca yönlendirilir (CLI kodu). `adt_table_read` `T100`'ü filtreleyemez (WHERE yok, önizleme 400 verdi).
- **Kural:** bir Z mesaj sınıfına `MESSAGE` ile referans vermeden önce mevcut mesajları **oku** ve uygun numarayı yeniden kullan.
  Okuyamadın diye koda satır içi literal mesaj yazma. Uygun mesaj yoksa yeni mesaj eklenmesini kullanıcıya öner (§2) ya da sor.

## 2. Yaratma ve mesaj ekleme
**Kabuk CLI'de var (2026-09-13; çevrimdışı test edildi, canlı DOĞRULANMADI):**
`cli adt_post_shell '{"object_type":"msag","name":"ZSD001_MSG","package":"<geliştirme paketi>","transport":"<TRANSPORT>","description":"<metin>"}' --sap-write ...`
— yalnız kabuk, stateless POST (§3.2 kilit dersi) → `adt_msgclass_read` ile `exists` + `master_language`. `ok:false` → retry etmeden `exists_after`;
`create_not_persisted` = 2xx ama obje yok (§3.2 "yanlış paket" vakası). Önceki araç setinde `adt_post_shell` `msag` `Unsupported object type` veriyordu.

**Mesaj yazma: `adt_msgclass_write` (2026-09-13; yalnız `s4_private`; çevrimdışı test edildi, canlı DOĞRULANMADI).** Argümanlar ve
dönüş: `%sap-adt-foundation` → `tool-catalog.md`. Ham REST ile yazılmaz.
- **Yol:** kabuk yoksa `adt_post_shell` `msag` → `adt_msgclass_read` (canlı liste + pull kaydı; kayıt yoksa yazma reddedilir) → nihai tam
  mesaj listesini (numara · metin · kendi kendini açıklar mı) kullanıcıya göster → `adt_msgclass_write` → dönüşte `readback_verified` ve `plan`.
- **Birleştirme:** SAP PUT tüm listeyi değiştirir (§3.5); araç canlı listeyi okuyup birleştirir — verilmeyen mevcut mesajlar korunur. Mevcut
  numarayı değiştirmek `allow_overwrite=true`, silmek `delete_numbers` ister; ikisini de kullanıcı onayı olmadan verme.
- **Kilit:** araç yalnız kendi kilidini bırakır; kaynak reçetenin enqueue kilidi silen "güvenlik ağı" adımı alınmadı (kesin yasak C).
  `lock_conflict`/`lock_failed` → kullanıcı SM12'de kendi kilidini kontrol eder, açık SE91/ADT oturumunu kapatır; sonra yeniden oku ve dene.
- `s4_private` dışındaki profilde araç kapalıdır (`tool_not_available_for_profile`): mesajları kullanıcı SE91'de ekler, sen `adt_msgclass_read`
  ile numaraları, metinleri ve `master_language`'i doğrularsın.
- Metin sınırı: `T100` mesaj metni **≤ 73 karakter**. Metinler `master_language`'de ve spesifikasyondan.

## 3. Protokol notları (araç aktarımı / teşhis)

### 3.1 Okuma ucu
`GET /sap/bc/adt/messageclass/<ad>` + `Accept: application/vnd.sap.adt.mc.messageclass+xml` → 200.

| Denenen | Sonuç |
|---|---|
| `.../messageclass/<ad>/messages` alt yolu | 404 (bu sürümde yok) |
| `Accept: application/vnd.sap.adt.messageclass.v2+xml` (açık kaynak bir istemcinin başlığı) | 406 — sunucu doğru tipi gövdede bildirir |
| **`.../messageclass/<ad>` + `.mc.messageclass+xml`** | **200** |

Meta ders: ADT API'sini dokümandan ya da başka istemciden değil **sunucudan** doğrula; 406 gövdesi kabul edilen tipi söyler.

### 3.2 Kabuk önce
- Kabuk yoksa mesaj PUT'u **sahte-200** döner: `T100`'e hiçbir şey yazılmaz, okuma `exists:false`.
- Hedef paket bir **geliştirme paketi** olmalı; yapı/üst paket verilince yaratma sessizce `exists:false` + mesaj yazımı sahte-200 üretti.
- Yaratma POST'u stateful oturumla gidince yaratma anındaki enqueue kilidi istek sonunda bırakılmadı → sonraki yazma/silme `403 EU 510`
  (SM12 gerekti). Çare (canlı kanıtlı): yaratma çağrısında `x-sap-adt-sessiontype: stateless` → kilit istek sonunda düşer. Kendi kilidini
  "yeniden kilitle-bırak" ile temizleme denemesi yine 403 verdi.
- Yaratmada master dil = oturum (logon) dili.

### 3.3 Mesaj yazma — çalışan akış
1. Taze CSRF (`/sap/bc/adt/discovery`, `sap-language` = master dil).
2. Kilit: `POST <sınıf>?_action=LOCK&accessMode=MODIFY&corrNr=<TRANSPORT>`, stateful,
   `Accept: application/*,application/vnd.sap.as+xml;dataname=com.sap.adt.lock.result` → `LOCK_HANDLE`.
3. PUT: **tüm sınıf gövdesi**, `lockHandle` + `corrNr` + `accessMode=MODIFY` query, `Content-Type: application/vnd.sap.adt.mc.messageclass+xml; charset=utf-8`,
   **`If-Match` GÖNDERME**. → 200.
4. Kilidi bırak — `try/finally` içinde garantili (yoksa SM12'de bayat kilit kalır).
5. Readback: `adt_msgclass_read`. Ayrı aktivasyon genelde gerekmez (yazım `T100`'e kaydeder) — readback ile doğrula.

Gövde:
```xml
<mc:messageClass adtcore:responsible="<SAP_USER>" adtcore:masterLanguage="<ML>" adtcore:name="ZSD001_MSG"
                 adtcore:type="MSAG/N" adtcore:description="<metin>" adtcore:language="<ML>"
                 xmlns:mc="http://www.sap.com/adt/MessageClass" xmlns:adtcore="http://www.sap.com/adt/core">
  <adtcore:packageRef adtcore:uri="/sap/bc/adt/packages/<paket>" adtcore:type="DEVC/K" adtcore:name="<PAKET>"/>
  <mc:messages mc:msgno="001" mc:msgtext="<metin>" mc:selfexplainatory="false" mc:documented="false" adtcore:name=""/>
</mc:messageClass>
```

| Öğe / öznitelik | Doğrusu | Yaygın yanlış |
|---|---|---|
| mesaj öğesi | `<mc:messages>` (çoğul) | `<mc:message>` → 400 |
| numara | `mc:msgno`, 3 hane sıfır dolgulu | `mc:number` → 400 |
| metin | `mc:msgtext` | `mc:text` → 400 |
| kendi kendini açıklar | `mc:selfexplainatory` (SAP'deki yazım hatasıyla) | `mc:selfExplanatory` |
| uzun metin | `mc:documented="false"` | — |
| `adtcore:name` | `""` | — |

Metin XML kaçışlı (`&` `<` `>` `"`).

### 3.4 Neden `If-Match` gönderilmez
Arka uç iki yol izliyor: `If-Match` varsa ETag karşılaştırması açılır ve ardından enqueue yeniden kontrol edilir; kontrol kendi kilidimizi
"başka oturum" sayar (**self-collision** → 403). `If-Match` yoksa ETag kontrolü atlanır ve yalnız query'deki `lockHandle` doğrulanır.
Eclipse ADT RFC üzerinden konuştuğu için bu HTTP yolunu görmez. Aynı kural DTEL güncellemesi (`domain-dtel.md` §5.3) ve Z tablo
kaynak PUT'unda (`tables-structures.md` §3.2) geçerlidir; **table type PUT'u istisnadır** (`table-types.md` §4.3). Genelleme yapma.

### 3.5 Yerine yazma semantiği
PUT gövdesindeki mesaj listesi mevcut listenin **yerine geçer**: 5 mesaj varken 3 mesajlık PUT → 3 mesaj kalır. Mesaj eklemek =
mevcutları okuyup (`adt_msgclass_read`) **tam listeyi** göndermek. Kullanıcıya gösterilen liste de bu yüzden nihai tam listedir.

### 3.6 DENENEN — BAŞARISIZ (50+ varyant denendi; tekrar deneme)
| Yöntem | Sonuç |
|---|---|
| PUT + `If-Match: <etag>` | 403 self-collision |
| PUT + `If-Match: *` | 412 (mesaj başına) ya da 403 (sınıf) |
| Mesaj başına `PUT .../messages/<no>` | 423 invalid lock handle |
| `POST` koleksiyona | 201 ama mesajlar sessizce düşer |
| `X-HTTP-Method-Override: PUT` | 201 ama mesajlar sessizce düşer |
| `Sap-Lock-Handle` benzeri başlık adları | 403 |
| `_action=UPDATE/REPLACE/UPSERT` | 400 URI mapping error |
| `accessMode=stateless/READ` | 400 invalid value |
| `forceLock=true`, `overwrite=true` | tanınmıyor, 403 |

## Bu dosyada ÇIKARILAN / DEĞİŞTİRİLEN
- Python REST kodu, script komutları ve CSV biçimi → protokol notu ve kullanıcıya gösterilecek liste biçimi.
- Kullanıcı adı, sistem client'ı, ortak paket ve gerçek sınıf adları → yer tutucu / nötr demo. Açık kaynak referans istemci adı → genel ifade.
