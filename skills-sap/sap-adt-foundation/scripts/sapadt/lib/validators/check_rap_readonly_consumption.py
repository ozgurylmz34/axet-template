"""
check_rap_readonly_consumption.py — RAP read-only consumption/interface katmanı iki klasik
aktivasyon hatasını SAP'ye yazmadan yakalar. (aXet uyarlaması — değişenler aşağıda.)

Vaka (kaynak çekirdek, RAP read-only rapor tüketim katmanı):
  A) `define view entity` (projeksiyon DEĞİL) gövdesinde join/base olarak
     `Z<MOD><nnn>_C_*` (consumption projection) kullanımı → aktivasyon:
     "Projection Views are not allowed as base object for this entity type."
  B) Adı `Z<MOD><nnn>_C_*` + içerik `as projection on` ama bu entity'i referanslayan
     hiç `.bdef` yok → aktivasyon: "Transactional Projection View must be part of a
     business object." (read-only raporda C_ katmanı `as select from` olmalı.)

aXet DEĞİŞİKLİKLERİ (neden):
  • Rule A AYNEN.
  • Rule B'nin "paket kökü" araması: kaynakta `.rules.md` bulunamazsa `path.parent.parent`
    alınıyordu. aXet'te `adt_push_source` artefaktı sistem geçici dizinindedir ⇒ o geri dönüş
    `%TEMP%`'in üst dizinini özyinelemeli tarardı (yavaş + ilgisiz). Yeni sıra:
      1. `.rules.md` taşıyan üst dizin varsa → kaynaktaki davranış (yerel .bdef yoksa BLOCKER);
      2. yoksa `AXET_SAP_PROJECT_DIR` altındaki `.bdef` dosyaları taranır (sınırlı);
         referanslayan bulunursa Rule B temiz;
      3. bulunamazsa Rule B **ÖLÇÜLEMEDİ**: aXet projesinde yerel dosya ağacının SAP'deki BO'yu
         yansıttığı varsayılamaz (BDEF yalnız SAP'de olabilir) ⇒ "yerelde yok" kanıt DEĞİLDİR.
         BLOCKER üretilmez; stderr'e görünür `[ÖLÇÜLEMEDİ] Rule B` satırı basılır (run_review
         bunu `~` sessiz-bulgu olarak raporlar — verdict'e sayılmaz, okunur).

Kullanım:
    python check_rap_readonly_consumption.py <cds_path>

Exit kodu:
    0 — Temiz (Rule B ölçülemediyse stderr'de not)
    0 + `AXET-GATE-STATUS … measured=false reason=ad-cozulemedi` — `define view entity` VAR ama entity ya da
        base/join adı katı ad gramerine uymadı (ör. `/AB/X`) ⇒ ÖLÇÜLEMEDİ, "kapsam dışı" DEĞİL.
    0 + `… reason=namespace-kayitsiz` — katman adı (`/<NS>/<MOD><nnn>_C_*`) ama `/<NS>/` projede
        `customer_namespaces` ile bildirilmemiş: müşterinin mi SAP'nin mi bilinemez.
    1 — İhlal (BLOCKER)

AD (2026-11-17, kaynak çekirdek #402): yakalama + müşteri kararı `utils/ad_politikasi` (AD_ADAYI · ad_coz ·
musteri_karari); katman sözdizimi `<ad-alanı><MOD><nnn>_C_*`, ad-alanı = Z/Y ya da bildirilmiş namespace.
Eski yerel desen (`Z` + 2-4 harf + 3 rakam + `_C_`) yalnız Z'yi görüyordu. ⚠ SIKILAŞTIRMA: Y'li ad da artık denetlenir.
BDEF araması: düz `*.bdef` + abapGit `*.bdef.asbdef`.
"""
import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _gate_status import gate_status  # noqa: E402  — AXET-GATE-STATUS üretici ucu
from utils.ad_politikasi import (  # noqa: E402  — TEK ad grameri + müşteri kararı
    AD_ADAYI, ad_coz, ad_gecis_deseni, ad_namespace, musteri_karari)

if sys.platform == 'win32':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Ad yakalama `ad_politikasi.AD_ADAYI` + `ad_coz` — validator kendi ad desenini YAZMAZ.
ENTITY_RE = re.compile(
    r'\bdefine\s+(?:root\s+)?view\s+entity\s+(' + AD_ADAYI + r')', re.IGNORECASE)
# Tür anahtar sözcüğü (adsız): ENTITY_RE eşleşmeyip bu eşleşirse ad ÇÖZÜLEMEMİŞTİR.
ENTITY_KW_RE = re.compile(r'\bdefine\s+(?:root\s+)?view\s+entity\b', re.IGNORECASE)
_GATE = Path(__file__).stem
PROJECTION_RE = re.compile(r'\bas\s+projection\s+on\b', re.IGNORECASE)
SELECT_FROM_RE = re.compile(r'\bas\s+select\s+from\b', re.IGNORECASE)
# KATMAN ADI (adın ad-alanından SONRAKİ gövdesi): <MOD><nnn>_C_* (MOD 2-4 harf). Ad-alanı kararı (Z/Y ya da
# bildirilmiş `/<NS>/`) `ad_politikasi.musteri_karari`'dadır.
_KATMAN_C_GOVDE = re.compile(r'[A-Z]{2,4}\d{3}_C_[A-Z0-9_]+', re.IGNORECASE | re.ASCII)
JOIN_OR_BASE_RE = re.compile(r'\b(?:join|from)\s+(' + AD_ADAYI + r')', re.IGNORECASE)
_BDEF_UZANTILARI = ('.bdef', '.asbdef')


def _katman_govdesi(ad: str) -> str:
    """Ad-alanı önekini (namespace ya da Z/Y harfi) at: `/NSPC/SD001_C_X` → `SD001_C_X`."""
    ns = ad_namespace(ad)
    return ad[len(ns):] if ns else ad[1:]


def c_katmani(ad: str) -> str:
    """'evet' · 'hayir' · 'namespace-kayitsiz' (katman adı ama ad-alanı bildirilmemiş) · 'ad-cozulemedi'."""
    karar = musteri_karari(ad)
    if karar == 'ad-cozulemedi':
        return karar
    if not _KATMAN_C_GOVDE.fullmatch(_katman_govdesi(ad)):
        return 'hayir'
    if karar == 'musteri':
        return 'evet'
    return 'namespace-kayitsiz' if karar == 'namespace-kayitsiz' else 'hayir'

# aXet: proje taraması sınırı (reviewer alt süreci 30 sn bütçelidir).
_ATLA = {'.git', '.axet-code', 'node_modules', '__pycache__', '.venv', 'venv'}
_TARAMA_SINIRI = 5000


def _strip_comments(text: str) -> str:
    out = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith('//') or s.startswith('--'):
            continue
        out.append(line)
    return '\n'.join(out)


def _rules_kok(path: Path):
    for parent in path.resolve().parents:
        if (parent / '.rules.md').exists():
            return parent
    return None


def _bdef_dosyalari(kok: Path):
    """(dosyalar, sinir_asildi) — atlanan dizinler hariç, en fazla _TARAMA_SINIRI dosya gezilir."""
    bulunan, sayac = [], 0
    for dirpath, dirnames, filenames in os.walk(kok):
        dirnames[:] = [d for d in dirnames if d not in _ATLA]
        for f in filenames:
            sayac += 1
            if sayac > _TARAMA_SINIRI:
                return bulunan, True
            if f.lower().endswith(_BDEF_UZANTILARI):   # abapGit: `X.bdef.asbdef`
                bulunan.append(Path(dirpath) / f)
    return bulunan, False


def _referans_var_mi(dosyalar, entity: str) -> bool:
    for bdef in dosyalar:
        try:
            btxt = bdef.read_text(encoding='utf-8', errors='replace')
        except OSError:
            continue
        # `\b` namespace'li adda `/` önünde tutmaz ⇒ sınır `ad_gecis_deseni`'nden
        if re.search(ad_gecis_deseni(entity), btxt, re.IGNORECASE):
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description='RAP read-only consumption/interface katman kontrolü')
    parser.add_argument('artifact')
    parser.add_argument('--strict', action='store_true',
                        help='(uyumluluk; NO-OP — şiddeti DEĞİŞTİRMEZ)')
    args = parser.parse_args()

    path = Path(args.artifact)
    if not path.exists():
        print(f'HATA: {path} bulunamadı', file=sys.stderr)
        return 1

    raw = path.read_text(encoding='utf-8', errors='replace')
    text = _strip_comments(raw)

    em = ENTITY_RE.search(text)
    entity, _neden = ad_coz(em.group(1)) if em else ('', None)
    if not entity:
        if ENTITY_KW_RE.search(text):
            # `define view entity` VAR ama ad çözülemedi ⇒ ÖLÇÜLEMEDİ (eski hâl "kapsam dışı" + rc 0 idi).
            print(f'ÖLÇÜLEMEDİ — {path.name} `define view entity` içeriyor ama entity adı '
                  f'çözülemedi → Rule A/B KOŞMADI; "temiz" anlamına GELMEZ.')
            gate_status(_GATE, 'SKIPPED', False, 'ad-cozulemedi')
            return 0
        print(f'OK — {path.name} view entity değil, kapsam dışı')
        return 0
    is_projection = bool(PROJECTION_RE.search(text))
    is_select = bool(SELECT_FROM_RE.search(text))

    violations = []
    notlar = []
    # Kural koşamayan ad: katı gramere uymayan base/join adı ya da bildirilmemiş namespace'te katman adı.
    olculemeyen: list[tuple[str, str]] = []

    # Rule A — düz view entity, base/join'de C_ projection
    if is_select and not is_projection:
        for m in JOIN_OR_BASE_RE.finditer(text):
            kaynak = m.group(1)
            durum = c_katmani(kaynak)
            if durum == 'evet':
                violations.append(
                    ('A', kaynak,
                     f"'{kaynak}' bir consumption projection (<ad-alanı><MOD><nnn>_C_); "
                     f"düz 'define view entity' base/join kaynağı OLAMAZ. "
                     f"Interface (<ad-alanı><MOD><nnn>_I_*) view'a geç."))
            elif durum != 'hayir':
                olculemeyen.append((kaynak, durum))

    # Rule B — C_ adlı + 'as projection on' ama referanslayan .bdef yok
    entity_katman = c_katmani(entity) if is_projection else 'hayir'
    if entity_katman == 'namespace-kayitsiz':
        olculemeyen.append((entity, entity_katman))
    if is_projection and entity_katman == 'evet':
        kok = _rules_kok(path)
        if kok is not None:
            dosyalar, _asildi = _bdef_dosyalari(kok)
            if not _referans_var_mi(dosyalar, entity):
                violations.append(
                    ('B', entity,
                     f"'{entity}' 'as projection on' kullanıyor (transactional "
                     f"projection = BO/BDEF zorunlu) ama paket altında ({kok.name}) onu "
                     f"referanslayan .bdef yok. Read-only ise 'as select from' "
                     f"düz consumption view entity yap."))
        else:
            proje = os.environ.get('AXET_SAP_PROJECT_DIR')
            dosyalar, asildi = (_bdef_dosyalari(Path(proje))
                                if proje and Path(proje).is_dir() else ([], False))
            if not _referans_var_mi(dosyalar, entity):
                notlar.append(
                    f"[ÖLÇÜLEMEDİ] Rule B — '{entity}' 'as projection on' kullanıyor; onu "
                    f"referanslayan BDEF yerel dosyalarda bulunamadı "
                    f"({'proje dizini yok' if not proje else f'{len(dosyalar)} .bdef tarandı'}"
                    f"{', tarama sınırı aşıldı' if asildi else ''}). aXet'te yerel ağaç SAP'deki "
                    f"BO'yu yansıtmak zorunda değil ⇒ bu 'BDEF yok' KANITI DEĞİLDİR ve BLOCKER "
                    f"üretilmedi. Read-only rapor ise 'as select from' kullan; transactional ise "
                    f"BDEF'in SAP'de var olduğunu adt_get(object_type='bdef') ile doğrula.")

    for n in notlar:
        print(n, file=sys.stderr)

    if not violations and olculemeyen:
        # İhlal bulunmadı ama en az bir ad DENETLENEMEDİ ⇒ "temiz" yazılmaz.
        print(f'ÖLÇÜLEMEDİ — {path.name}: '
              + ', '.join(f"'{a}' ({d})" for a, d in olculemeyen)
              + ' → katman kuralı bu adlar için KOŞMADI; "temiz" anlamına GELMEZ. '
                'namespace-kayitsiz: ad-alanı müşterinin ise sap-project.json customer_namespaces.')
        gate_status(_GATE, 'SKIPPED', False, olculemeyen[0][1])
        return 0

    if not violations:
        print(f'OK — {path.name} RAP read-only consumption/interface: Rule A temiz'
              + ('; Rule B ÖLÇÜLEMEDİ (stderr)' if notlar else ''))
        return 0

    print(f'\n[BLOCKER] {path.name} — {len(violations)} ihlal', file=sys.stderr)
    for rule, _obj, msg in violations:
        print(f"  [Rule {rule}] {msg}", file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main())
