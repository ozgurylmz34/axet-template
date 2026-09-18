# -*- coding: utf-8 -*-
"""İnceleme (reviewer) zincirinin SÜRE BÜTÇESİ — TEK KAYNAK (K10, kullanıcı kararı 2026-09-15).

Karar: **"Süreyi ÖLÇ + UZAT, sonra BLOCKER"**. Bu dosya kararın ② maddesidir: sabit 30 sn yerine
**ölçüme dayalı, yapılandırılabilir** bir bütçe. ③ maddesi (`zaman aşımı = BLOCKER`) `sapadt/_reviewer.py`de.

ÜÇ KATMAN — hangi sınırın kime ait olduğu (bunu bilmeden sayılar okunamaz):

    L1  sarmalayıcı   `_reviewer.run_reviewer` → `subprocess.run(run_review.py, timeout=L1)`
        = `reviewer_butce_sn()`   ← ENV `AXET_REVIEWER_BUTCE_SN` (TEK ayar düğmesi)
    L2  zincir        `run_review.main` → tek tek validator'lara dağıtılan TOPLAM süre
        = `zincir_butce_sn()` = L1 − `ZINCIR_PAYI_SN`   (pay: run_review açılışı + raporlama)
    L3  gate-içi      canlı gate'in (bugün `check_struct_field_dtel_active`) kendi ağ bütçesi
        = `gate_butce_sn()` = L2 × `GATE_ORANI`, ENV `AXET_DTEL_GATE_BUTCE_SN` ile değiştirilebilir
          ama **L2'yi AŞAMAZ** (yapısal: L3 < L2 < L1).

⛔ ÖNCEKİ KUSUR (ÖLÇÜLDÜ 2026-09-17, K10 turu): L1 = 30 sn sabit iken `run_review.run_validator`
   validator başına **60 sn** veriyordu ⇒ L2 > L1: iç zaman aşımı dalına HİÇ ULAŞILAMIYORDU (ölü dal),
   hükmü daima L1'in kör kesmesi veriyordu. Sıralama artık bu dosyada TEK yerde kurulur.

VARSAYILANIN DAYANAĞI (sahte ADT sunucusuyla, gerçek giriş noktasından `_reviewer.run_reviewer`):
  · hızlı SAP (0 sn/GET): en uzun zincir `table_update` = **1,45 sn** (5 validator, 10 GET)
  · 1 sn/GET (D12 "yavaş sistem"): `table_update` = **11,27 sn** · `struct_creation` (8 DTEL) = 8,95 sn
  · DTEL gate'in ölçülen işleme hızı ≈ **1 aday/sn** (1 sn/GET'te 15 sn bütçede 15 GET)
  ⇒ L3 = 28 sn ≈ 1 sn/GET'lik bir sistemde **~28 DTEL adayı** (eski 15 sn'de ~14 idi — D12'nin
    "14'ten fazla DTEL → yanlış BLOCKER" riski tam buradaydı; ÖLÇÜLDÜ: 16 adayda bütçe dolup
    ÖLÇÜLEMEDİ→BLOCKER çıkıyordu, SAP doğru cevap verdiği hâlde).
  ⇒ L1 = 60 sn: L3 (28) + ölçülen zincir artığı (~11) + pay ≈ 2× emniyet. Ayrıca 60, ESKİ iç
    zaman aşımına eşittir ⇒ hiçbir katman eskisinden DAHA AZ süre almaz.
  ⛔ ÖLÇÜLEMEDİ: gerçek SAP sistemine karşı süreler (bu turda canlı bağlantı YOKTU). Yukarıdaki
    sayılar 127.0.0.1'deki sahte ADT sunucusuna karşıdır; gecikme benzetimdir, ölçüm değil.
    Gerçek sisteminde yetmiyorsa **ENV ile uzat** — bütçe tam bu yüzden yapılandırılabilir.
"""
from __future__ import annotations

import os
import sys

REVIEWER_ENV = 'AXET_REVIEWER_BUTCE_SN'
GATE_ENV = 'AXET_DTEL_GATE_BUTCE_SN'

VARSAYILAN_SN = 60.0
ALT_SINIR_SN = 5.0
UST_SINIR_SN = 900.0
# run_review süreç açılışı + JSON raporlaması için L1'den ayrılan pay. ÖLÇÜLDÜ: boş zincir
# (`dtel_update`, 0 validator) uçtan uca 0,11 sn ⇒ 4 sn ≈ 36× emniyet.
ZINCIR_PAYI_SN = 4.0
# Zincir bütçesinin canlı gate'e ayrılan payı. Kalanı (%50) zincirin DİĞER validator'larına:
# ÖLÇÜLDÜ (1 sn/GET): `table_update`te DTEL gate dışı kısım ≈ 2,5 sn + süreç açılışları.
GATE_ORANI = 0.5
GATE_ASGARI_SN = 0.5


def _uyar(mesaj: str) -> None:
    """Uyarı kanalı TEK yerde (test bunu yakalar; sessiz düşen bütçe = sessiz gevşeme)."""
    print(mesaj, file=sys.stderr)


def _env_sn(ad: str, varsayilan: float, alt: float, ust: float) -> float:
    ham = os.environ.get(ad)
    if ham is None or not ham.strip():
        return varsayilan
    try:
        deger = float(ham)
    except ValueError:
        deger = float('nan')
    if not (alt <= deger <= ust):          # NaN karşılaştırması da False
        _uyar(f'UYARI: {ad}={ham!r} geçersiz ({alt:g} <= değer <= {ust:g} olmalı) → '
              f'varsayılan {varsayilan:g} sn kullanıldı')
        return varsayilan
    return deger


def reviewer_butce_sn() -> float:
    """L1 — sarmalayıcının tüm `run_review` zincirine verdiği süre (sn).

    ⭐ ENV bütçeyi hem YÜKSELTİR hem DÜŞÜRÜR. Yükseltmek bir GEVŞETME DEĞİLDİR: daha uzun bütçe
    = daha ÇOK kontrol ölçülür. Kısaltmak ise ölçülemeyeni artırır ve (canlı BLOCKER zincirinde)
    daha çok BLOCKER üretir — yani iki yön de fail-closed'dır.
    """
    return _env_sn(REVIEWER_ENV, VARSAYILAN_SN, ALT_SINIR_SN, UST_SINIR_SN)


def zincir_butce_sn() -> float:
    """L2 — `run_review`in validator'lara dağıtacağı TOPLAM süre (< L1, yapısal)."""
    return max(reviewer_butce_sn() - ZINCIR_PAYI_SN, ALT_SINIR_SN / 2)


def gate_butce_sn() -> float:
    """L3 — canlı gate'in kendi ağ bütçesi (< L2, yapısal; ENV ile ayarlanır ama L2'yi aşamaz)."""
    zincir = zincir_butce_sn()
    varsayilan = max(round(zincir * GATE_ORANI, 1), GATE_ASGARI_SN)
    # ⛔ ÜST SINIR L2'dir, sabit bir sayı DEĞİL: sarmalayıcı bütçesi yükseldiğinde gate payı da
    # yükselebilsin (K10 ②). Eskiden üst sınır sabit 15 sn'di ⇒ "yavaş sistem" riski (D12)
    # yapılandırmayla karşılanamıyordu.
    return _env_sn(GATE_ENV, varsayilan, GATE_ASGARI_SN, zincir)


def nasil_uzatilir() -> str:
    """Zaman aşımı mesajlarına AYNEN gömülen 'süreyi nasıl uzatırım' cümlesi (K10 ③ şartı)."""
    return (f'SÜREYİ UZATMAK İÇİN: ortam değişkeni {REVIEWER_ENV}=<saniye> '
            f'(şu an {reviewer_butce_sn():g} sn; geçerli aralık {ALT_SINIR_SN:g}-{UST_SINIR_SN:g}; '
            f'canlı gate payı otomatik ölçeklenir — yalnız o payı ayarlamak için {GATE_ENV}).')
