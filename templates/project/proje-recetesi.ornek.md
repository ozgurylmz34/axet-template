# Proje Reçetesi (ÖRNEK — doldurulmamış)

> **Bu dosya şablondur, doldurulmaz.** Doldurulmuş hâli proje kökünde `proje-recetesi.md`
> adıyla durur ve `.gitignore`'ludur (müşteri bilgisi taşıyabilir — bkz. §0).
>
> **Neden var:** `AGENTS.md` projenin *teknik* kimliğini taşır (komutlar, profil, paket).
> İşin *bağlamı* — hangi müşteri, hangi peyzaj, hangi arayüz, belgeler hangi dilde ve nasıl
> numaralanıyor — hiçbir yerde yazılı değilse ajan her oturum ya sorar ya da **uydurur**.
> İkincisi bu deponun çekirdek yasağıdır. Bu reçete o bağlamı tek dosyada, **uydurmadan**
> tutar.

## 0. Kullanım ve doldurma disiplini

1. Bu dosyayı **kopyala**: `proje-recetesi.ornek.md` → `proje-recetesi.md` (aynı klasör).
   Örneğin dosyasına dokunma; sonraki güncellemelerde o dosya yenilenebilir.
2. **Bilmediğin alanı doldurma, tahmin etme.** Değeri bilinmiyorsa alan `[BİLİNMİYOR]`
   olarak KALIR. Ajan `[BİLİNMİYOR]` gördüğünde o bilgiyi **kullanıcıya sorar**;
   boş alanı kendi kafasından tamamlaması YASAKTIR.
3. **Kaynağını yaz.** Her alanın yanındaki `kaynak:` kutucuğuna bilginin nereden geldiğini
   yaz (kick-off sunumu, müşteri e-postası, canlı sistemden ölçüm, sözlü bilgi). Kaynağı
   olmayan bir değer, doldurulmuş görünse de **doğrulanmamıştır**.
4. **Tarihini yaz.** Peyzaj, kişiler ve namespace zamanla değişir; tarihsiz bir satırın
   bugün hâlâ geçerli olup olmadığı ölçülemez.
5. **Kişisel veri asgari düzeyde.** Rol yazmak yeterliyse ad yazma. Bu dosya gitignore'lu
   olsa da yanlışlıkla paylaşılabilir; taşımadığı bilgi sızmaz.

> ⚠ **`proje-recetesi.md` commit EDİLMEZ.** `.gitignore` bunu zaten engelliyor. Projenin
> içeriği müşteri bilgisi taşımıyorsa ve ekip commit etmek istiyorsa, kararı ekip verir:
> `.gitignore`'daki satır elle kaldırılır. Varsayılan güvenli taraftadır.

---

## 1. Müşteri ve proje

| Alan | Değer | Kaynak / tarih |
|---|---|---|
| Müşteri (kısa ad) | `[BİLİNMİYOR]` | |
| Sektör | `[BİLİNMİYOR]` | |
| Proje adı / kodu | `[BİLİNMİYOR]` | |
| Proje türü (yeni kurulum · rollout · destek · tek geliştirme) | `[BİLİNMİYOR]` | |
| Başlangıç / hedef canlıya geçiş tarihi | `[BİLİNMİYOR]` | |

## 2. Ürün ve kapsam

| Alan | Değer | Kaynak / tarih |
|---|---|---|
| Ürün ve sürüm (ör. S/4HANA on-premise 2023, FPS02) | `[BİLİNMİYOR]` | |
| Kapsamdaki modüller | `[BİLİNMİYOR]` | |
| Kapsam DIŞI olduğu açıkça söylenenler | `[BİLİNMİYOR]` | |
| Metodoloji / faz modeli | `[BİLİNMİYOR]` | |

> Kapsam dışı satırı boş bırakma alışkanlığı pahalıdır: "konuşulmadı" ile "kapsam dışı"
> aynı şey değildir, ve ikisi karıştırılınca yapılan iş geri alınmak zorunda kalır.

## 3. Sistem peyzajı

| Sistem | SID / istemci | Rol | Erişim var mı | Kaynak / tarih |
|---|---|---|---|---|
| Geliştirme | `[BİLİNMİYOR]` | DEV | `[BİLİNMİYOR]` | |
| Test / kalite | `[BİLİNMİYOR]` | QA | `[BİLİNMİYOR]` | |
| Canlı | `[BİLİNMİYOR]` | PRD | `[BİLİNMİYOR]` | |

- Taşıma (transport) akışı: `[BİLİNMİYOR]`
- Taşıma talebini kim açar: `[BİLİNMİYOR]` *(bu depo taşıma talebi YARATMAZ — kullanıcıdan ister)*

## 4. Geliştirme kuralları

| Alan | Değer | Kaynak / tarih |
|---|---|---|
| Namespace / önek (ör. `Z...`, `/XXX/`) | `[BİLİNMİYOR]` | |
| Paket adlandırma kuralı | `[BİLİNMİYOR]` | |
| Clean core beklentisi (katı · dengeli · yok) | `[BİLİNMİYOR]` | |
| Kod inceleme / ATC beklentisi | `[BİLİNMİYOR]` | |
| Müşteriye özel kodlama standardı belgesi var mı | `[BİLİNMİYOR]` | |

## 5. Belgeler

| Alan | Değer | Kaynak / tarih |
|---|---|---|
| Belge dili (FS/TS metinleri) | `[BİLİNMİYOR]` | |
| SAP objelerinin metin dili (`master_language`) | `[BİLİNMİYOR]` | |
| FS numaralandırma biçimi | `[BİLİNMİYOR]` | |
| TS numaralandırma biçimi | `[BİLİNMİYOR]` | |
| Belge şablonu müşteriden mi geliyor | `[BİLİNMİYOR]` | |
| Belgeler nerede saklanıyor | `[BİLİNMİYOR]` | |

> Belge dili ile SAP obje metin dili **aynı olmak zorunda değildir** (belgeler İngilizce,
> obje metinleri Türkçe olan projeler yaygındır). İkisi ayrı alandır; birinden diğerini
> türetme.

## 6. Arayüzler ve bağımlılıklar

| Karşı sistem | Yön | Teknoloji | Sahibi | Durum | Kaynak / tarih |
|---|---|---|---|---|---|
| `[BİLİNMİYOR]` | | | | | |

- Dış bağımlılık / bekleyen karar: `[BİLİNMİYOR]`

## 7. Kişiler ve roller

> Ad yerine rol yazmak yeterliyse rol yaz (§0.5).

| Rol | Kim | İletişim kanalı | Kaynak / tarih |
|---|---|---|---|
| Müşteri tarafı karar verici | `[BİLİNMİYOR]` | | |
| Müşteri tarafı kilit kullanıcı | `[BİLİNMİYOR]` | | |
| Basis / yetki | `[BİLİNMİYOR]` | | |
| Proje yöneticisi | `[BİLİNMİYOR]` | | |

## 8. Açık kararlar

> Reçetedeki bir alan `[BİLİNMİYOR]` kaldıysa ve işi bloke ediyorsa buraya taşınır.
> Bu bölüm dolduğu sürece "kapsam netleşti" denmez.

| # | Soru | Kime soruldu | Tarih | Durum |
|---|---|---|---|---|
| 1 | | | | açık |
