---
name: recall
description: >
  Ekip ve proje hafızasında (indeks + kayıt gövdeleri), paket .rules.md kurallarında ve skill açıklamalarında
  işe ilgili ders ve kayıt arar. Çok adımlı bir işe
  başlarken, tanıdık görünen bir hata ya da tuzakla karşılaşınca, yeni bir kural/ders/hafıza kaydı
  yazmadan önce ve "bu yapılamaz" demeden önce kullan. Kullanıcı %recall yazarsa da çalıştır.
---

# recall — işe başlamadan önce ne biliyoruz?

## Ne zaman
- Çok adımlı bir işe başlarken (plan yapmadan önce).
- Bir hata, uyarı ya da tuhaf davranış tanıdık geldiğinde: cevap zaten yazılmış olabilir.
- `%remember` ile yeni kayıt yazmadan ve "bu bozuk / yapılamaz" demeden önce (çekirdek §2 "önce ara").

## Nasıl
1. Görevi 1-2 cümleyle, anahtar terimleriyle özetle (teknoloji, obje tipi, hata metni, araç adı).
2. Bu skill'in klasöründeki script'i çalıştır (yol: bu `SKILL.md`'nin bulunduğu klasör):
   ```
   python "<bu klasör>/scripts/recall.py" "<özet ve anahtar terimler>" --project-dir "<proje kökü>"
   ```
3. Çıkan kayıtların alakalı olanlarını `view` ile aç ve uygula. Skill çıktıysa önce o skill'i oku.
4. Sonuç yoksa terimleri değiştirip bir kez daha dene (eş anlamlı, İngilizce karşılık, hata kodu).
5. Raporda ya da yeni kayıtta sonucu yaz: `önceki kayıt: bulundu <yol>` ya da `önceki kayıt: yok (aranan: …)`.

## Kurallar
- Çıkan kayıt hipotezdir: içindeki dosya/komut/obje hâlâ var mı, kullanmadan önce doğrula.
- "Eşik üstü kayıt yok" ≠ "ilgili ders yok": script hafıza kaydı gövdelerini ve `<source_root>` altındaki `.rules.md`'leri de tarar ama skill gövdelerine, paket `SESSION_NOTES`/`SPEC`'ine ve kaynak koda bakmaz; gövde eşleşmesi indeks eşleşmesinden düşük puanlıdır; eşik altı kalan gövde eşleşmeleri ayrı "düşük güven" listesinde çıkar — göreve dokunuyorsa aç (çıktıdaki `KAPSAM` satırı neye bakılmadığını söyler).
- Eşik sorgunun terim sayısına göre ayarlanır: 1 terim → 1, 2 terim → 3, 3 ve daha çok terim → 5. Sayılan terimler, 3 harften kısa sözcükler, dolgu sözcükleri (`ve`, `ile`, `için` …) ve çok kayıtta geçtiği için genel sayılan sözcükler çıkarıldıktan SONRA kalanlardır (ör. "ABAP class yarat": `abap` genel sayılırsa 2 terim kalır → eşik 3; çıktıdaki `KAPSAM` satırı genel sayılanları ve etkin eşiği yazar). Terimin çoğul/ekli biçimi de eşleşir (5+ harfli terimde önek: `transport` ↔ `transports`). Eşik ölçeklendiğinde yalnız gövdesiyle eşleşen kayıt yine 5 ister; `--esik N` verilirse ölçekleme yapılmaz ve bu kayıt için de eşik N olur. `UYARI: … genel sayıldı` çıkarsa terim çok kayıtta geçtiği için puana katılmamıştır: daha belirli bir terim ekle.
- Script hiçbir şey yazmaz, ağa çıkmaz; güvenle her işte çalıştırılabilir.
