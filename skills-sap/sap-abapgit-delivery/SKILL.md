---
name: sap-abapgit-delivery
description: >
  Use when an ABAP change must reach SAP as an abapGit offline ZIP that the developer imports
  (read-only SAP model): unpacking a package ZIP the developer exported from SAP, editing the
  serialized files, checking them against the hard prohibitions (standard objects, direct standard
  table writes, package creation, language and texts), building the import ZIP, and recording the
  import or activation result the developer brings back. Triggers: "abapGit", "ZIP ile teslim",
  "SAP'ye ZIP hazırla", "içe aktarma paketi", "offline repo", "SAP'den dışa aktardım", "aktivasyon
  hatası geldi". Not for reading objects directly from SAP (sap-adt-foundation), request scoping
  (sap-intake-triage) or opt-in sandbox writes through the CLI.
---

# sap-abapgit-delivery — abapGit ZIP ile teslim

> **Profil:** araç çevrimdışı çalışır. abapGit'in hedef sistemde kurulu ve içe aktarıma açık olduğu varsayılmaz: geliştiriciden
> teyit al. Profil başına kullanılabilirlik DOĞRULANMADI.

## When to use this skill
- Projenin SAP modeli salt-okurdur: model SAP'ye yazmaz, değişiklik geliştiricinin içe aktardığı abapGit ZIP'i
  ile gider.
- Geliştirici paketi SAP'de abapGit ile dışa aktardı ve ZIP'i verdi; ya da içe aktarım/aktivasyon sonucunu getirdi.
- **Kullanma:** SAP'den doğrudan nesne okuma → `%sap-adt-foundation` · işin kapsamı belirsiz → `%sap-intake-triage`
  · CLI ile sandbox yazma (makinede `--sap-write` açık ve `.conn_adt` DEV) → foundation yazma kapısı.

## Araç
`scripts/abapgit_zip.py` (yalnız standart kütüphane; B taraması `sap-adt-foundation` tarayıcısını kullanır):

| Komut | Ne yapar |
|---|---|
| `unpack EXPORT.zip --root WS` | ZIP'i çalışma alanına açar, `.abapgit-baseline.json` taban çizgisi yazar; güvensiz yol (zip-slip) → RED; yerel değişikliği ezmez (`--force`) |
| `check --root WS --all` ya da `--files …` | denetler, ZIP üretmez |
| `pack --root WS --all --project-dir <PROJE>` | denetler; FAIL yoksa `WS/dist/<ad>-<UTC>.zip` üretir, geliştirici adımlarını basar |
| `status-in ÇIKTI.txt\|.zip --root WS` | SAP'den gelen içe aktarım/aktivasyon çıktısını `.abapgit-status/` altına saklar |

Çıkış: `0` tamam · `1` hata · `2` RED (FAIL ya da güvensiz ZIP) · `3` kullanım. Her denetim çıktısı sonunda
**KAPSAM** satırı basar: neye bakılmadığını kullanıcıya aktar ("0 FAIL" ≠ "SAP'de çalışır").

## How to use this skill
1. **Çalışma alanı:** önerilen `<source_root>/<MODÜL>/<PAKET>/abapgit/`. Geliştiriciden SAP'de abapGit ile
   paketin **güncel** ZIP'ini iste (adımlar: `references/abapgit-delivery.md` §2) ve `unpack` ile aç.
2. **Düzenle:** yalnız çalışma alanındaki dosyalar. Yeni nesne gerekiyorsa meta dosyasını (`<ad>.<tip>.xml`) aynı
   tipte SAP'den gelmiş bir nesneden kopyala; alan adı ya da değer uydurma. Standart objeye append alanı adı önerme; yeni Z DDIC adı
   (DTEL, domain …) yalnız `%sap-dev` §6 kuralıyla: standarda uygun öneri + canlı kontrol + kullanıcının açık onayı.
3. **Denetle ve paketle:** `pack --root WS --all --project-dir <PROJE_KÖKÜ>`. FAIL varsa ZIP üretilmez; FAIL'i
   atlatmak için dosya adını/klasörü değiştirme, sebebini kullanıcıya açıkla.
4. **Teslim et:** ZIP yolunu, dosya listesini, WARN satırlarını ve scriptin bastığı geliştirici adımlarını ver.
   İçe aktarımı geliştirici yapar; transport'u o seçer.
5. **Dönüş:** geliştirici aktivasyon/hata çıktısını metin olarak getirir → `status-in` ile sakla, hataları dosyalara
   eşle, düzeltmeyi yeni `pack` ile ver. "İçe aktarıldı" mesajına güvenme: aktif sürümü geliştiriciye SAP'de
   kontrol ettir ya da foundation ile salt-okur `adt_get` ile doğrula.

## Rules (Kesin Yasaklar ile eşleşme)
- **A:** Z/Y dışı nesne dosyası teslime giremez (kilit nesnesi EZ/EY; ad alanı `/Z…/`, `/Y…/`). → `ADR_0005_A`
- **B:** `.abap` kaynağında standart tabloya doğrudan `INSERT/UPDATE/DELETE/MODIFY` → `ADR_0005_B`; tarayıcı
  yüklenemezse teslim üretilmez (`std_dml_scan_unavailable`).
- **C:** paket tanımı (`*.devc.xml`) ve taban çizgisinde olmayan yeni klasör (abapGit alt paket yaratır) → FAIL.
  Alt paketi geliştirici SAP'de açtıysa `--subpackages-exist`. Transport yaratma/release yok.
- **D:** `.abapgit.xml` dili ile proje `master_language` uyuşmalı; boş başlık/açıklama ve eksik DTEL etiketleri FAIL.
- Taban çizgisi 7 günden eskiyse (WARN) güncel ZIP'i yeniden iste: başkasının SAP'deki değişikliği ezilebilir.
- Silme ZIP ile yapılmaz: silinecek nesneyi geliştiriciye listele.
- SAP'den gelen dosyaların adını ve klasörünü değiştirme (abapGit dokümantasyonu; FAIL'i atlatma yolu da değildir).
- `.abapgit-status/` ve `dist/` içeriği sistem ayrıntısı taşıyabilir; commit edilmez.

## Sınırlar
- Sözdizimi, aktivasyon, bağımlılık ve XML şeması denetlenmez; JSON biçimli nesnelerde metin/dil bakılmaz.
- DTEL etiket alan adları (`REPTEXT`, `SCRTEXT_S/M/L`) ve ZIP içe aktarımının silme davranışı DOĞRULANMADI
  (ayrıntı `references/abapgit-delivery.md` §5).
- Dil kodu eşlemesi yalnız EN→E, TR→T; başka dilde `--main-language-letter` ver.
