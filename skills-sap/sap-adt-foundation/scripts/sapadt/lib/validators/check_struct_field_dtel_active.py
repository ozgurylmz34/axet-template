"""
check_struct_field_dtel_active.py — Struct/Table DDL'inde alan tipi olarak kullanılan
müşteri DTEL'lerinin (Z/Y ya da /ad-alanı/) SAP'de VAR ve AKTİF olup olmadığını kontrol eder.

Kritik: struct'ta kullanılan DTEL'ler aktif değilse aktivasyon fail eder + cascade fail
(dependent struct'lar/CDS'ler).

Kullanım:
    python scripts/validators/check_struct_field_dtel_active.py <artifact>

Exit kodu:
    0 — Tüm aday DTEL'ler aktif  (VEYA: kapsam dışı / ÖLÇÜLEMEDİ — ayrım exit kodunda DEĞİL,
        `AXET-GATE-STATUS` satırındadır; aşağıya bak)
    1 — En az 1 DTEL inactive veya yok

⛔ `exit 0` ÜÇ ANLAMLIDIR — makinece okunur ayrım (2026-08-28, B3-01):
Bu gate `run_review` zincirinde **BLOCKER**'dır (table_creation · table_update ·
struct_creation · struct_fields_dtel) ve SAP bağlantısı yokken `return 0` veriyordu ⇒ reviewer
bunu "temiz" sayıyordu (fail-open). Çıkış kodu DEĞİŞTİRİLMEDİ; her exit-0 yolu
`_gate_status.gate_status()` ile `measured=true|false` beyan eder. Tüketici `run_review.py`
`rc==0 && measured=false` gördüğünde `PASS` değil **`SKIP`** kaydeder ve SKIP kendi şiddetiyle
(burada BLOCKER) verdict'e sayılır.

aXet 2026-09-14 (D1, lider kararı):
  · Aday çıkarımı TEK KAYNAKTA: `lib/utils/ddic_dtel.py::dtel_adaylari` (artefaktsız
    `adt_struct_create` de aynı fonksiyonu kullanır). Eskiden regex yalnız `zsd[0-9_]*_e_*`
    yakalıyordu → `ZAXET_E_X` gibi var olmayan DTEL "kapsam dışı" PASS alıyordu (fail-open).
  · DTEL GET 404 → BLOCKER'dan ÖNCE ad yapı / tablo / tablo tipi olarak sorulur (Z tipli alan
    bileşen tipi olabilir). Varsa "kapsam dışı: DTEL değil" notuyla atlanır; hiçbirinde yoksa
    BLOCKER; sonda okunamazsa ÖLÇÜLEMEDİ.
  · Ad URL'de kodlanır (`/scwm/de_x` → `%2Fscwm%2Fde_x`; önek: `check_standard_table_fields.py`).
  · Standart DTEL'ler KONTROL EDİLMEZ (kapsam beyanı her koşumda basılır).

Bug gate 2026-09-14 (B1, lider kararı (b)): 404 sondası eksik DTEL başına 1+3 GET yapıyor ve her GET 10 sn
bekleyebiliyordu → zincir `_reviewer` 30 sn sarmalayıcısını aşıp WARNING'e (YAZMA) düşüyordu. Artık istemci kurulumu
ve tüm ağ okumaları TEK döngüde ve TEK toplam süre bütçesiyle koşar (`butce_sn()`); tekrar deneme ve paralel
istek YOK. Bütçe biterse denetlenemeyen adaylar ÖLÇÜLEMEDİ olur: bulgu yoksa `measured=false` (run_review → SKIP =
BLOCKER), bulgu varsa exit 1 + kalanlar adlarıyla basılır.

K10 (2026-09-17, kullanıcı kararı "Süreyi ölç + uzat, sonra BLOCKER"): bütçe artık SABİT 15 sn değil, TEK KAYNAKTAN
(`utils/butce.py`) gelir ve sarmalayıcı bütçesiyle ölçeklenir (varsayılanda 28 sn). `AXET_REVIEWER_BUTCE_SN` tüm
katmanları birlikte yükseltir/düşürür; yalnız bu gate'in payı için `AXET_DTEL_GATE_BUTCE_SN` — artık YÜKSELTEBİLİR de
(üst sınır sabit bir sayı değil, ZİNCİR bütçesidir). Geçersiz değer → varsayılan + uyarı satırı.

Re-gate 2026-09-15 (LOW): `timeout=min(10, kalan)` requests'te SOKET OKUMASI BAŞINA uygulanır → damlayan yanıtta
(1 bayt/1,5 sn) gate, bütçe 3 sn iken 90 sn'de bitmemişti (ölçüldü) ve istemci kurulumu bütçenin dışındaydı. Artık istemci
kurulumu ve her istek (gövde okuması dahil) bir iplikte koşar; ana akış yalnız KALAN bütçe kadar bekler (`_sureli`), süre
dolunca iplik terk edilir. Bütçenin DIŞINDA kalan: süreç açılışı + modül importları (yerel, ağsız). ÖLÇÜLDÜ (sahte sunucu,
bütçe 3 sn): 1 bayt/1,5 sn damlayan yanıt → gate süreci 3,3-3,4 sn; 30 sn asılı istemci kurulumu → 3,7 sn; ikisi de
measured=false (ÖLÇÜLEMEDİ → BLOCKER). Ayrıntı: IMPLEMENTATION §20.7.
"""
# ENFORCES: C-STR-FIELD-02, C-TBL-DTEL-01  (ADR 0019 coverage binding)
import argparse
import os
import re
import sys
import threading
import time
import urllib3
from pathlib import Path
from urllib.parse import quote

# Sözleşme yardımcısı script'in KENDİ dizinindedir; `utils` bir üst dizinde (lib/).
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _gate_status import gate_status, sap_baglanti_yok  # noqa: E402
from utils import butce as _butce  # noqa: E402
from utils.ddic_dtel import KAPSAM_BEYANI, dtel_adaylari  # noqa: E402

_GATE = Path(__file__).stem
# DTEL 404 aldığında adın DTEL dışı bir bileşen tipi olarak var olup olmadığı bu uçlarda sorulur.
_BILESEN_UCLARI = ('structures', 'tables', 'tabletypes')

# B1 + re-gate 2026-09-15: istemci kurulumu + tüm ağ okumalarının GERÇEK toplam bütçesi (`_sureli`).
# ⭐ K10 (2026-09-17): bu gate'in payı artık SABİT 15 sn DEĞİL — sarmalayıcı bütçesiyle birlikte
# ölçeklenir (`utils/butce.py` L3 = L2 × %50; varsayılanda 28 sn). Eski sabit 15 sn, D12'nin ölçülmüş
# riskini taşıyordu: 1 sn/GET yanıt veren bir sistemde 16 geçerli Z DTEL'li yapı bütçeye sığmıyor ve
# SAP DOĞRU cevap verdiği hâlde ÖLÇÜLEMEDİ → yanlış BLOCKER çıkıyordu (ÖLÇÜLDÜ: 14 aday = son geçen,
# 16 aday = BLOCKER). Bütçe yapılandırılabilir olduğu için bu risk artık ayarla karşılanır.
BUTCE_ENV = _butce.GATE_ENV
_ISTEK_ZAMAN_ASIMI_SN = 10.0
# İstek bütçe kısıtlı zaman aşımıyla koparsa kalan süre bu eşiğin altındadır → "bütçe doldu" sayılır.
_BUTCE_ESIK_SN = 0.5

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

if sys.platform == 'win32':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')


def butce_sn() -> float:
    """Bu gate'in toplam ağ bütçesi — TEK KAYNAK `utils/butce.py` (K10).

    ⛔ ESKİ KURAL ("env bütçeyi yalnız DÜŞÜREBİLİR, üst sınır sabit 15 sn") KALDIRILDI. Gerekçe:
    bütçeyi YÜKSELTMEK bir gevşetme değildir — daha uzun bütçe DAHA ÇOK adayın ÖLÇÜLMESİ demektir;
    kısa bütçe ise ölçülemeyeni (ve dolayısıyla BLOCKER'ı) artırır. Üst sınır artık sabit bir sayı
    değil ZİNCİR bütçesidir (L3 < L2 < L1 yapısal olarak korunur). Geçersiz env → varsayılan + uyarı.
    """
    return _butce.gate_butce_sn()


class _ButceDoldu(Exception):
    pass


class _Butce:
    def __init__(self, sn: float):
        self.sn = sn
        self._son = time.monotonic() + sn

    def kalan(self) -> float:
        return self._son - time.monotonic()

    def doldu_mu(self) -> bool:
        return self.kalan() <= _BUTCE_ESIK_SN


def _sureli(butce: _Butce, fn, *args):
    """`fn(*args)`'ı bir iplikte koşar; ana akış yalnız KALAN bütçe kadar bekler → bütçe gerçek toplam sınırdır.

    Re-gate 2026-09-15: requests `timeout`'u soket okuması başına uygular; damlayan yanıt ya da asılı istemci kurulumu onu
    hiç doldurmaz. Süre dolarsa iplik terk edilir (daemon) ve `_ButceDoldu` fırlar. `fn`'in istisnası ana akışa taşınır.
    ÖLÇÜLDÜ (Windows, Python 3.14, damla sunucu, bütçe 3 sn): terk edilen iplik süreç çıkışını bekletmiyor — normal
    `sys.exit` ile 3,4 sn (2/2), `os._exit` ile de 3,3-3,4 sn → ayrıca zorla çıkış gerekmedi."""
    kalan = butce.kalan()
    if kalan <= 0:
        raise _ButceDoldu()
    kutu = {}

    def is_():
        try:
            kutu['sonuc'] = fn(*args)
        except BaseException as e:  # noqa: BLE001 — ana akışa aynen taşınır
            kutu['hata'] = e

    iplik = threading.Thread(target=is_, name='dtel-gate-istek', daemon=True)
    iplik.start()
    iplik.join(kalan)
    if iplik.is_alive():
        raise _ButceDoldu()
    if 'hata' in kutu:
        raise kutu['hata']
    return kutu['sonuc']


def _istemci_kur(sinif):
    client = sinif()
    _tekrar_denemeyi_kapat(client)
    return client


def _tekrar_denemeyi_kapat(client) -> None:
    """Bu gate'in oturumunda tekrar denemeyi kapat (yalnız bu validator sürecinde; paylaşılan kütüphane değişmez).

    ÖLÇÜLDÜ (2026-09-14, asılı sahte SAP): `sap_adt_lib._build_session` adaptörü `Retry(total=3)` taşır → bütçe kısıtlı
    zaman aşımına düşen GET 4 kez denendi, gate 15 sn bütçe yerine 42,7 sn sürdü (4 istek) ve zincir 30 sn'yi aştı.
    Tek geçiş = tekrar deneme YOK; 429/502/503 gibi geçici cevaplar da ÖLÇÜLEMEDİ olur (fail-closed, BLOCKER).
    Havuz boyutları kaynak adaptörle aynı; kimlik bilgisi oturum başlıklarında durduğu için adaptör değişimi etkilemez."""
    from requests.adapters import HTTPAdapter
    adaptor = HTTPAdapter(pool_connections=4, pool_maxsize=10, max_retries=0)
    client.session.mount('https://', adaptor)
    client.session.mount('http://', adaptor)


def _get(client, uc: str, ad: str, butce: _Butce):
    # stream=False: gövde `session.get` içinde, yani İPLİKTE okunur (ayrı `r.content` okuması gereksiz — mutasyonla ölçüldü).
    def istek():
        return client.session.get(
            client.url + f'/sap/bc/adt/ddic/{uc}/{quote(ad.lower(), safe="")}',
            params={'sap-client': str(client.client or '')}, verify=False,
            timeout=min(_ISTEK_ZAMAN_ASIMI_SN, max(butce.kalan(), 0.01)))
    return _sureli(butce, istek)


def _bilesen_tipi(client, ad: str, butce: _Butce):
    """(uç, None) → ad bu uçta VAR · (None, None) → hiçbirinde yok · (None, sebep) → ölçülemedi.
    Bütçe biterse `_ButceDoldu` fırlatır."""
    for uc in _BILESEN_UCLARI:
        try:
            r = _get(client, uc, ad, butce)
        except _ButceDoldu:
            raise
        except Exception as e:  # noqa: BLE001
            if butce.doldu_mu():
                raise _ButceDoldu() from e
            return None, f'{uc} hata: {e}'
        if r.status_code == 200:
            return uc, None
        if r.status_code != 404:
            return None, f'{uc} GET {r.status_code}'
    return None, None


def main() -> int:
    parser = argparse.ArgumentParser(description='Z/Y + /ns/ DTEL varlık ve aktivasyon kontrolü')
    parser.add_argument('artifact')
    parser.add_argument('--strict', action='store_true',
                       help='(uyumluluk; NO-OP — şiddeti DEĞİŞTİRMEZ, run_all --strict kazara terfi ettirmesin; ADR 0019 §54)')
    args = parser.parse_args()

    path = Path(args.artifact)
    if not path.exists():
        print(f'HATA: {path} bulunamadı', file=sys.stderr)
        return 1

    text = path.read_text(encoding='utf-8', errors='replace')
    dtels = dtel_adaylari(text)
    print(KAPSAM_BEYANI)
    butce_suresi = butce_sn()
    print(f'SÜRE BÜTÇESİ: {butce_suresi:g} sn (istemci kurulumu + tüm SAP okumalarının gerçek toplamı; biterse '
          f'denetlenemeyen adaylar ÖLÇÜLEMEDİ → BLOCKER). {_butce.nasil_uzatilir()}')

    if not dtels:
        print(f'OK — {path.name} Z/Y ya da /ad-alanı/ DTEL adayı yok')
        # ÖLÇÜLDÜ: dosya okundu, aday yok ⇒ denetlenecek bir şey YOK → measured=true.
        gate_status(_GATE, 'OK', True, 'kapsam-disi-z-dtel-yok')
        return 0

    try:
        from sap_adt_lib import SAPADTClient
    except Exception as e:
        print(f'UYARI: SAP bağlantısı kurulamadı, validator atlandı: {e}', file=sys.stderr)
        sap_baglanti_yok(_GATE)
        return 0

    inactive = []
    missing = []
    kapsam_disi = []
    # KISMİ KÖRLÜK (B3-01): okunamayan aday "hepsi aktif" cümlesine karışmaz.
    okunamayan = []
    # B1: süre bütçesi dolduğu için HİÇ ya da TAM denetlenemeyen adaylar (okunamayan'dan ayrı sayılır).
    denetlenmeyen = []
    # Re-gate 2026-09-15: bütçe istemci kurulumundan ÖNCE başlar — kurulum da bütçe içindedir.
    butce = _Butce(butce_suresi)
    client = None
    try:
        client = _sureli(butce, _istemci_kur, SAPADTClient)
    except _ButceDoldu:
        print('  UYARI: SAP istemcisi süre bütçesi içinde kurulamadı', file=sys.stderr)
        denetlenmeyen = list(dtels)
    except Exception as e:  # noqa: BLE001
        print(f'UYARI: SAP bağlantısı kurulamadı, validator atlandı: {e}', file=sys.stderr)
        sap_baglanti_yok(_GATE)
        return 0

    if client is not None:
        print(f'{path.name} — {len(dtels)} DTEL adayı kontrol ediliyor...')
    for i, dtel in enumerate(dtels if client is not None else []):
        if butce.kalan() <= 0:
            denetlenmeyen.extend(dtels[i:])
            break
        try:
            r = _get(client, 'dataelements', dtel, butce)
            if r.status_code == 404:
                uc, sebep = _bilesen_tipi(client, dtel, butce)
                if sebep:
                    print(f'  UYARI: {dtel} DTEL değil ama bileşen sondası ölçülemedi ({sebep})', file=sys.stderr)
                    okunamayan.append(dtel)
                elif uc:
                    kapsam_disi.append((dtel, uc))
                else:
                    missing.append(dtel)
                continue
            if r.status_code != 200:
                print(f'  UYARI: {dtel} GET {r.status_code}', file=sys.stderr)
                okunamayan.append(dtel)
                continue
            m = re.search(r'adtcore:version="(\w+)"', r.text)
            version = m.group(1) if m else '?'
            if version != 'active':
                inactive.append((dtel, version))
        except _ButceDoldu:
            denetlenmeyen.extend(dtels[i:])
            break
        except Exception as e:  # noqa: BLE001
            if butce.doldu_mu():
                denetlenmeyen.extend(dtels[i:])
                break
            print(f'  UYARI: {dtel} hata: {e}', file=sys.stderr)
            okunamayan.append(dtel)

    for d, uc in kapsam_disi:
        print(f'  NOT: {d} DTEL değil ({uc} olarak var) — kapsam dışı, atlandı')

    denetlenen = len(dtels) - len(denetlenmeyen) - len(okunamayan)
    butce_slug = ''
    if denetlenmeyen:
        # Lider şartı 1: "DTEL yok" ile karışmasın — sayılar ve adlar görünür.
        print(f'[ÖLÇÜLEMEDİ: süre bütçesi ({butce.sn:g} sn) doldu, {len(denetlenmeyen)} aday denetlenmedi] '
              f'denetlenen {denetlenen}/{len(dtels)} · denetlenmeyen: {", ".join(denetlenmeyen)} — '
              f'bu "DTEL yok" DEMEK DEĞİL; TEMİZ de denemez. {_butce.nasil_uzatilir()}', file=sys.stderr)
        butce_slug = f'sure-butcesi-{butce.sn:g}sn-doldu-{len(denetlenmeyen)}-aday-denetlenmedi-{denetlenen}-denetlendi'

    if not missing and not inactive:
        if okunamayan or denetlenmeyen:
            if okunamayan:
                # "Bulunamadı ≠ yok": okunamayan DTEL inactive OLABİLİR. Yeşil demek yasak.
                print(f'[ÖLÇÜLEMEDİ] {len(okunamayan)}/{len(dtels)} DTEL adayı okunamadı '
                      f'({", ".join(okunamayan)}) — TEMİZ denemez.', file=sys.stderr)
            gate_status(_GATE, 'SKIPPED', False, butce_slug or 'kismi-okunamadi')
            return 0
        print(f'OK — {len(dtels)} DTEL adayı: aktif ya da DTEL dışı bileşen tipi')
        gate_status(_GATE, 'OK', True, 'temiz')
        return 0

    if missing:
        print(f'\n[BLOCKER] {len(missing)} DTEL SAP\'de bulunamadı (yapı/tablo/tablo tipi olarak da yok):',
              file=sys.stderr)
        for d in missing:
            print(f'  {d}', file=sys.stderr)
        print('  Çözüm: DTEL\'i önce yarat ve aktive et, sonra struct\'ı yarat.', file=sys.stderr)

    if inactive:
        print(f'\n[BLOCKER] {len(inactive)} DTEL inactive:', file=sys.stderr)
        for d, v in inactive:
            print(f'  {d} (version: {v})', file=sys.stderr)
        print('  Çözüm: DTEL\'i önce aktive et (adt_activate, type dtel)', file=sys.stderr)

    if okunamayan:
        print(f'  Ayrıca okunamayan: {", ".join(okunamayan)}', file=sys.stderr)
    if denetlenmeyen:
        print(f'  Ayrıca süre bütçesi dolduğu için denetlenmeyen: {", ".join(denetlenmeyen)}', file=sys.stderr)

    gate_status(_GATE, 'FINDING', True, f'{len(missing)}-eksik-{len(inactive)}-inaktif'
                + (f'-{len(denetlenmeyen)}-denetlenmedi-butce' if denetlenmeyen else ''))
    return 1


if __name__ == '__main__':
    sys.exit(main())
