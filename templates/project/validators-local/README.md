# validators-local — projeye özel commit denetimleri

Bu klasördeki `*.py` dosyaları her commit'te `.githooks/pre-commit` tarafından çalıştırılır
(template'in genel denetimlerinden SONRA; onların yerine geçmez, onları kapatamaz).

## Sözleşme
- Çalıştırılan: bu klasördeki `*.py` (alt çizgiyle başlayanlar `_yardimci.py` çalıştırılmaz, içe aktarılabilir).
- Çalışma dizini: proje kökü. Süre sınırı: 120 sn.
- Ortam değişkenleri:
  - `AXET_PRECOMMIT=1`
  - `AXET_PROJECT_DIR` — proje kökü
  - `AXET_STAGED_FILES` — staged dosya yollarının listesi (satır başına bir yol, proje köküne göreli, `/` ayraçlı)
- Çıkış kodu: `0` geçti · `1` ihlal → commit engellenir · başka her çıkış ya da zaman aşımı "çalıştırılamadı"
  sayılır → commit engellenir.
- Çıktının son satırları pre-commit raporuna yazılır: ihlali ve düzeltmeyi tek satırda söyle.
- Staged içeriği okumak için `git show :<yol>` kullan; çalışma ağacındaki dosya staged hâlden farklı olabilir.

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
