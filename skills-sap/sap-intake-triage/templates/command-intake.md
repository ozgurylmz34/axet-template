SAP geliştirme talebi alımı (intake triage) başlatıyoruz.

1. `sap-intake-triage` skill'inin `SKILL.md` dosyasını skill listesindeki konumundan `view` ile oku; ardından
   `references/protocol.md`'yi oku. Okumadan işe başlama.
2. Kullanıcının talebini al: bu komutla birlikte bir talep yazılmadıysa `ask_user` ile iste (talep metni, varsa Excel/FS dosya yolu).
   Talep bir dosyadaysa dosyayı oku.
3. Protokolü uygula:
   - Kapsamı S0 / S1 / S2 diye sınıfla, modülü ve teknik tipi belirle; gerekçeyi tek cümleyle kullanıcıya yaz.
   - Modül paketi varsa (`references/modules/`) oku; yoksa uydurma, genel protokolle ilerle.
   - İsterlerden domain konularını çıkar; 3 eksende araştır (domain · canlı sistem ve ilgili kod — yalnız `sap-adt-foundation`
     CLI okuma araçları · ekip `memory/` + proje `.axet-code/memory/` + önceki `.axet-code/intake/` artefaktları).
   - Kanıtlı değerlendir; kapsamla orantılı soru sor.
4. Sınıf S2 ise:
   - `templates/intake-artifact.md`'yi temel alarak `.axet-code/intake/<YYYYMMDD-kisa-ad>.md` dosyasını oluştur ve tüm alanları
     araştırma sonuçlarıyla doldur (şema: `references/s2-artifact-schema.md`). Sistem sürümü, yeni Z adları (öneri + canlı
     kontrol + ad başına ONAY), tablo yönetim alanları, kural taraması ve öz-tutarlılık bölümlerini `references/protocol.md`
     §6 S2 adım 1'e göre doldur; standarttan sapan her kararı kullanıcıya sor.
   - Artefaktı kullanıcıyla madde madde gözden geçir; mutabakat işaretini yalnız kullanıcının açık onayından sonra koy.
   - Şema dosyasındaki kontrol komutunu çalıştır ve sonucunu göster.
5. SAP'ye yazma bu komutun parçası DEĞİLDİR. Build aşamasına geçerken `sap-dev` skill'ini oku ve §3'ü (paket bağlamı,
   paket klasörü, değiştirilecek objeleri klasöre indirme) build planının ilk adımı yap. Yazma aşamasında her CLI yazma
   çağrısı kapsam beyanı taşır (S0/S1: `--scope` + `--reason`; S2: `--scope S2 --intake <artefakt yolu>`). Kapsam
   büyürse yeniden sınıfla.
6. Sonunda raporla: sınıf + gerekçe · bulunan/reuse edilecek objeler (kanıtla) · sorulan ve cevaplanan sorular ·
   artefakt yolu (S2) · açık kararlar · DOĞRULANMADI kalanlar.
