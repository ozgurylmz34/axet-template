# validators-local — projeye özel commit denetimleri

Bu klasördeki `*.py` dosyaları her commit'te `.githooks/pre-commit` tarafından çalıştırılır
(template'in genel denetimlerinden sonra; SAP projesinde SAP incelemesi bunlardan SONRA koşar. Genel denetimlerin
yerine geçmez, onları kapatamaz).

## Sözleşme
- Çalıştırılan: yalnız bu klasörün **doğrudan** içindeki `*.py`; alt klasördeki dosyalar çalıştırılmaz
  (alt çizgiyle başlayanlar `_yardimci.py` çalıştırılmaz, içe aktarılabilir).
- Sıra: dosya adına göre (Python `sorted` — büyük harfle başlayan ad önce gelir). Her script bağımsız koşar: birinin ihlal vermesi sonrakileri durdurmaz,
  hepsinin sonucu rapora yazılır.
- Çalışma dizini: proje kökü. Süre sınırı: 120 sn (script başına).
- Ortam değişkenleri:
  - `AXET_PRECOMMIT=1`
  - `AXET_PROJECT_DIR` — proje kökü
  - `AXET_STAGED_FILES` — listenin kendisi DEĞİL, listeyi içeren **geçici dosyanın yolu**. Dosya UTF-8; satır başına
    bir staged yol (proje köküne göreli, `/` ayraçlı). Yalnız eklenen/değişen/kopyalanan/yeniden adlandırılan
    dosyalar listelenir, silinenler yoktur. Staged dosya yoksa dosya boştur.
    ⚠ Değişkeni doğrudan bölmek (`os.environ["AXET_STAGED_FILES"].splitlines()`) tek bir geçici dosya yolu verir;
    hiçbir staged yol eşleşmez ve denetim **sessizce hep geçer**. Dosyayı aç ve oku (aşağıdaki örnek).
- Çıkış kodu: `0` geçti · `1` ihlal → commit engellenir · başka her çıkış ya da zaman aşımı "çalıştırılamadı"
  sayılır → commit engellenir.
- Çıktının son satırları pre-commit raporuna yazılır: ihlali ve düzeltmeyi tek satırda söyle.
- Staged içeriği okumak için `git show :<yol>` kullan; çalışma ağacındaki dosya staged hâlden farklı olabilir.
  `git show` içeriği **ham bayt** verir: kodlama dönüştürülmez, aXet de bir kodlama belirlemez. Çıktıyı bayt olarak
  al (`subprocess.run([...], capture_output=True)`, `text=True` verme) ve çözmeyi kendin yap
  (ör. `.decode("utf-8", "replace")`). Satır sonları index'teki hâldir (`core.autocrlf` açıksa LF).

## Yazmadan önce
- Yeni bir engelleyici denetim, gerçekten yaşanmış ve başka katmanın yakalamadığı bir hata için yazılır;
  hatırlatma yeterliyse `AGENTS.md` ya da proje skill'i önce denenir.
- Kimlik bilgisi okuyan, ağa çıkan ya da SAP'ye bağlanan denetim buraya konmaz (commit anı çevrimdışıdır).
- Bu klasör davranış yüzeyidir: değişiklik `behavior_manifest.py` ile onaylanana kadar `doctor.py` FAIL verir.

## Örnek iskelet
```python
import os, sys
from pathlib import Path

staged = Path(os.environ["AXET_STAGED_FILES"]).read_text(encoding="utf-8").splitlines()
ihlal = [y for y in staged if y.lower().endswith(".tmp")]
if ihlal:
    print("geçici dosya staged: " + ", ".join(ihlal) + " → git rm --cached")
    sys.exit(1)
sys.exit(0)
```
