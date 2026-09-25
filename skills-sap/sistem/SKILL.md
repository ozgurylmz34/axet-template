---
name: sistem
description: >
  Use when the user wants to see or switch the active SAP system of this project (DEV, QA, PRD client):
  lists the systems defined in conn/ with scripts/conn_sablon.py ozet --json (name, tier, fill status only),
  offers them as choices with ask_user, activates the chosen one with switch_tier.py and reports the result
  (QA/PRD are read-only). Triggers: "%sistem", "client switch", "sistem değiştir", "sisteme bağlan",
  "QA'ya geç", "QA'ya bağlan", "DEV'e geç", "DEV'e dön", "hangi sisteme bağlıyım". Not for creating or
  editing connection files (the user fills conn\DEV.env and conn\QA.env via KURULUMU-TAMAMLA.cmd) and not
  for testing the connection (sap_doctor).
---

# sistem — projede aktif SAP sistemini seç

`<AXET_HOME>` = bu skill klasörünün iki üstü (`<AXET_HOME>/skills-sap/sistem/SKILL.md`); yolu buradan türet.
`<FOUND>` = `<AXET_HOME>/skills-sap/sap-adt-foundation/scripts`. `<proje>` = oturumun proje kökü.

## When to use this skill
- Kullanıcı aktif SAP sistemini görmek ya da DEV/QA/PRD arasında geçmek istiyor ("QA'ya geç", "client switch").
- **Kullanma:** bağlantı dosyası yaratmak/düzenlemek (kullanıcı `KURULUMU-TAMAMLA.cmd`'nin gösterdiği `conn\*.env` dosyasını kendisi doldurur) ·
  bağlantıyı test etmek (`sap_adt_cli.py sap_doctor`, `%sap-adt-foundation`).

## How to use this skill
1. **Listele:** `python "<AXET_HOME>/scripts/conn_sablon.py" ozet --json --project-dir "<proje>"`.
   Çıktı tek JSON: `aktif` (sistem + tier ya da null) ve `systems` (her biri `system`, `tier`, `file`, `durum`:
   `gecerli` · `hatali` · `doldurulmamis`). Değer içermez.
2. **Sistem yoksa ya da hiçbiri `gecerli` değilse dur:** "Proje klasöründeki `KURULUMU-TAMAMLA.cmd`'ye çift tıkla,
   açılan `conn\DEV.env` / `conn\QA.env` dosyalarını doldur, sonra tekrar çift tıkla" de. Hatalı dosyanın adını
   söyle; hangi alanın hatalı olduğunu `KURULUMU-TAMAMLA.cmd` gösterir.
3. **Kullanıcı hedefi zaten söylediyse** ("QA'ya geç") ve o tier'da tek `gecerli` sistem varsa sormadan 4'e geç.
   Değilse `ask_user` ile sor: her `gecerli` sistem bir seçenek (`label` = sistem adı, `description` = tier; aktif
   olanı "(aktif)" diye işaretle). `options` JSON **dizisi**dir, en az 2 seçenek; tek geçerli sistem varsa ikinci
   seçenek "Vazgeç". `hatali`/`doldurulmamis` sistemleri seçenek yapma, ayrıca "doldurulmamış: …" diye listele.
4. **Etkinleştir:** `python "<FOUND>/switch_tier.py" <SISTEM_ADI> --project-dir "<proje>"` (tier değil sistem adı
   ver: aynı tier'da birden çok sistem varsa tier belirsizdir).
5. **Raporla** (JSON'dan): yeni aktif sistem + tier. `tier` QA ya da PRD ise: "Bu sistem salt-okunur; SAP'ye yazma
   araçları reddeder. Yazmak için DEV'e dön." `ok: false` ise `error.code` + `error.message`'ı aynen aktar
   (`placeholder_values` → dosya doldurulmamış; `copy_failed` → dosya yazılamadı, aşağıdaki kurala bak).

## Rules
- `conn/` altındaki dosyaları ve `.conn_adt`'yi **okuma, listeleme, basma**; yalnız iki betiğin JSON çıktısını kullan.
  Değer (URL, kullanıcı, client, parola) sorma, yazma.
- Bağlantı testi yapma, SAP'ye bağlanma; kullanıcı isterse ayrı adım olarak `sap_doctor` öner.
- Dosya yaratma/düzeltme önerme: şablonu kullanıcı doldurur. `switch_tier.py` kopyalama hatası (`copy_failed`)
  verirse düzeltmeyi deneme; hatayı aynen raporla ve kullanıcıya `KURULUMU-TAMAMLA.cmd`'yi öner.
