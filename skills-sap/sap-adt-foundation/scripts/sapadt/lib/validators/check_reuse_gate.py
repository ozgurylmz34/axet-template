"""
check_reuse_gate.py — reuse gate: yeni bir CDS view entity'nin ADI projede başka bir yerel
dosyada zaten tanımlı mı? (aXet uyarlaması — değişenler aşağıda.)

Amaç: duplicate obje yaratımını ve "var olanı tekrar üretme" hatasını SAP'ye yazmadan önce
hatırlatmak. Severity: WARNING (false-positive riski; karar geliştiricinin).

aXet DEĞİŞİKLİKLERİ (neden):
  • Tarama kökü: kaynakta repo kökü (`CLAUDE.md`/`.git` taşıyan üst dizin) + `<source_root>`
    idi. aXet'te artefakt sistem geçici dizinindedir ⇒ kök `AXET_SAP_PROJECT_DIR` (CLI basar);
    yoksa artefaktın dizini. `.git`, `.axet-code`, `node_modules` atlanır; en fazla 5000 dosya
    gezilir — sınır aşılırsa `AXET-GATE-STATUS measured=false` (ölçülemedi ≠ temiz).
  • KALDIRILDI: müşteri projesine özgü "ortak master/VH adları" listesi ve kaynak çekirdeğin
    `governance/cbo-inventory.json` envanteri (aXet projesinde yok; ölü atıf bırakılmadı).
  • Uyarılar stdout yerine STDERR'e basılır (çıkış 0): run_review bunları `~` sessiz-bulgu olarak
    görünür kılar. Kaynakta stdout'a basılıyor ve rapor döngüsünde "PASS" satırının altında
    kalıyordu.
  • Güncelleme push'unda aynı adın yerel kaynak dosyasında bulunması BEKLENEN durumdur; mesaj
    bunu söyler (yaratma mı güncelleme mi ayrımı bu validator'da ölçülemez).

Kullanım:
    python check_reuse_gate.py <artifact_path>

Exit: 0 (bu validator BLOCKER üretmez).
      0 + `AXET-GATE-STATUS … measured=false reason=ad-cozulemedi` — `define view entity` VAR ama entity adı
      katı ad gramerine uymadı (ör. `/AB/X`, `/NSPC X`): ÖLÇÜLEMEDİ, "kapsam dışı" DEĞİL (kaynak çekirdek #402).
      Namespace'li ad (`/NSPC/…`) `ad_politikasi` gramerince AYRIŞTIRILIR ve denetlenir.
"""
import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.ad_politikasi import AD_ADAYI, ad_coz  # noqa: E402  — tek ad grameri

if sys.platform == 'win32':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Ad yakalama `ad_politikasi.AD_ADAYI` (gevşek) + `ad_coz` (katı) — validator kendi ad desenini YAZMAZ.
ENTITY_RE = re.compile(
    r'\bdefine\s+(?:root\s+)?view\s+entity\s+(' + AD_ADAYI + r')', re.IGNORECASE)
# Tür anahtar sözcüğü (adsız): ENTITY_RE eşleşmeyip bu eşleşirse ad ÇÖZÜLEMEMİŞTİR.
ENTITY_KW_RE = re.compile(r'\bdefine\s+(?:root\s+)?view\s+entity\b', re.IGNORECASE)
UZANTILAR = ('.cds', '.asddls', '.ddls')
_ATLA = {'.git', '.axet-code', 'node_modules', '__pycache__', '.venv', 'venv'}
_TARAMA_SINIRI = 5000


def durum_beyani(status: str, measured: bool, reason: str) -> None:
    print(f'AXET-GATE-STATUS: gate=check_reuse_gate status={status} '
          f'measured={"true" if measured else "false"} reason={reason}')


def _envanter(kok: Path, haric: Path):
    """(ad → dosya, sinir_asildi)."""
    inv: dict = {}
    sayac = 0
    haric_r = haric.resolve()
    for dirpath, dirnames, filenames in os.walk(kok):
        dirnames[:] = [d for d in dirnames if d not in _ATLA]
        for f in filenames:
            sayac += 1
            if sayac > _TARAMA_SINIRI:
                return inv, True
            if not f.lower().endswith(UZANTILAR):
                continue
            p = Path(dirpath) / f
            if p.resolve() == haric_r:
                continue
            try:
                txt = p.read_text(encoding='utf-8', errors='replace')
            except OSError:
                continue
            for m in ENTITY_RE.finditer(txt):
                ad, _neden = ad_coz(m.group(1))
                if ad:      # şekli bozuk ad envantere girmez (yeni nesnenin adı ayrıca denetlenir)
                    inv.setdefault(ad.upper(), p)
    return inv, False


def main() -> int:
    parser = argparse.ArgumentParser(description='Reuse gate (yerel duplicate)')
    parser.add_argument('artifact')
    parser.add_argument('--strict', action='store_true',
                        help='(uyumluluk; NO-OP — şiddeti DEĞİŞTİRMEZ)')
    args = parser.parse_args()

    path = Path(args.artifact)
    if not path.exists():
        print(f'HATA: {path} bulunamadı', file=sys.stderr)
        return 1

    text = path.read_text(encoding='utf-8', errors='replace')
    m = ENTITY_RE.search(text)
    ad, _neden = ad_coz(m.group(1)) if m else ('', None)
    if not ad:
        if ENTITY_KW_RE.search(text):
            # Tür anahtar sözcüğü VAR ama ad çözülemedi: eski hâl "kapsam dışı" diyordu (kontrol koşmadan temiz).
            print(f'ÖLÇÜLEMEDİ — {path.name} `define view entity` içeriyor ama entity adı '
                  f'çözülemedi → reuse-gate KOŞMADI; "temiz" anlamına GELMEZ.')
            durum_beyani('SKIPPED', False, 'ad-cozulemedi')
            return 0
        print(f'OK — {path.name} view entity değil, reuse-gate kapsamı dışı')
        return 0
    yeni = ad.upper()

    proje = os.environ.get('AXET_SAP_PROJECT_DIR')
    kok = Path(proje) if proje and Path(proje).is_dir() else path.resolve().parent
    inv, asildi = _envanter(kok, path)
    if asildi:
        print(f'reuse-gate: tarama sınırı ({_TARAMA_SINIRI} dosya) aşıldı — yerel duplicate '
              f'kontrolü TAMAMLANMADI.')
        durum_beyani('SKIPPED', False, 'scan_limit_exceeded')
        return 0

    if yeni in inv:
        try:
            yer = inv[yeni].relative_to(kok)
        except ValueError:
            yer = inv[yeni]
        print(f"[WARNING] reuse-gate: '{yeni}' yerel dosyada da tanımlı: {yer}. Bu push YENİ bir "
              f"obje yaratıyorsa duplicate riski — mevcut objeyi kullan/incele. Mevcut objenin "
              f"GÜNCELLEMESİ ise beklenen durumdur.", file=sys.stderr)
        durum_beyani('FINDING', True, 'name_defined_locally')
        return 0

    print(f'OK — {path.name} ({yeni}) yerel duplicate yok (kök: proje dizini)')
    durum_beyani('OK', True, 'no_local_duplicate')
    return 0


if __name__ == '__main__':
    sys.exit(main())
