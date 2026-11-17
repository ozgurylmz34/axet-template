# -*- coding: utf-8 -*-
"""ddl_yorum — DDL (tablo / yapı / CDS) kaynağında yorum maskelemenin TEK KAYNAĞI (yalnız stdlib).

NEDEN AYRI MODÜL (aXet tur 8 bug-gate, 2026-11-17)
  `check_table_field_drop` ve `check_sap_struct_consistency` alan taramasını HAM metinde yapıyordu.
  Ad grameri namespace'i tanımak için `/` ile başlayan adayı da aldığından (`AD_ADAYI`'nin `/…` kolu)
  `//old_fld : zde_old;` ve `/*fld : x;*/` yorum satırları "alan adı adayı" sanılıyor, `ad_coz`
  reddediyor ⇒ `SKIPPED measured=false reason=ad-cozulemedi` ⇒ run_review BLOCKER — Z/Y projede de
  (eski `[a-z]…` deseni yorumu görmüyordu = gerileme). Aynı iki yardımcı `check_cds_currency_reference`
  içinde zaten vardı; kopyalamak yerine buraya taşındı (davranış BİREBİR aynı), üç validator buradan
  import eder. `check_cds_currency_reference.yorumu_kirp` / `.blok_yorumu_maskele` adları geriye uyum
  için o modülde yeniden dışa açıktır.
  ⛔ Bu modüle stdlib dışı import EKLEME.

Kardeş (farklı amaç): `utils/cds_metin.cds_kod_metni` yorumu ATAR ve string'i `''` yapar (satır yapısı
blok yorumda değişir); buradaki işlevler satır numarasını KORUR (hata satırı raporlanabilsin).
"""


def yorumu_kirp(line: str) -> str:
    """Satır-sonu `//` yorumunu kırpar — TIRNAK İÇİ `//` KORUNUR.

    NEDEN (2026-08-01 bug-avı, V1): alan deseni `;\\s*$` ile ANCHOR'lı; gerçek DDL'de
    yaygın olan `netwr : netwr;  // tutar` satırı desene UYMAZ → alan hiç kaydedilmez →
    eksik CURR-annotation ihlali SESSİZCE kaybolur (gate yeşil yanar, "0 alan bulundu"
    ile "0 ihlal" ayırt edilemez — run_all'ın "dizin-yok → 0 dosya → OK" sınıfının
    satır-içi ikizi).

    Aynı sınıfın ikinci yüzü annotation DEĞERİdir: `@Semantics.amount.currencyCode :
    'ztab.waers'  // para birimi` satırında değer `ztab.waers' // para birimi` olarak
    okunuyor, `split('.')[-1]` → `waers' // para birimi` → "CUKY tabloda yok" YANLIŞ-
    POZİTİF'i basılıyordu. Tek kırpma iki yüzü birden kapatır.

    Tırnak-duyarlılık ZORUNLU: `@EndUserText.label : 'http://x'` gibi meşru değerler
    kırpılırsa annotation bozulur (kaba `split('//')` bu FP'yi üretir).
    """
    q = None
    i, n = 0, len(line)
    while i < n:
        c = line[i]
        if q is not None:
            if c == q:
                q = None
        elif c in "'\"":
            q = c
        elif c == '/' and i + 1 < n and line[i + 1] == '/':
            return line[:i]
        elif c == '-' and i + 1 < n and line[i + 1] == '-':
            # kaynak çekirdek #402 (Y3 kardeşi, ölçüldü f15becb): `rate : netwr; -- tutar` satırı
            # alan desenine (`;$`) uymuyordu ⇒ CURR alanı HİÇ kaydedilmiyor, "annotation
            # eksik" BLOCKER'ı sessizce kayboluyordu (aynı satır `//` ile BLOCKER veriyordu).
            # `parse_source` ve `_ustteki_annotasyonlar` `--`'yı zaten yorum sayıyordu.
            return line[:i]
        i += 1
    return line


def blok_yorumu_maskele(text: str) -> str:
    """`/* … */` blok yorumlarını BOŞLUKLA maskeler; satır sonları korunur (satır no aynı kalır).

    Tırnak içi `/*` korunur. Kapanmayan blok dosya sonuna kadar yorumdur.
    NEDEN (bug-gate F4, 2026-11-08): `kaynak_adi` yorumdaki `define table eski_ad {` satırını
    başlık sanıyordu ⇒ gerçek ada yapılan başvuru "başka tablo" sayılıp denetimden kaçıyordu.
    """
    out, i, n, q, blok = [], 0, len(text), None, False
    while i < n:
        c = text[i]
        if blok:
            if c == '*' and i + 1 < n and text[i + 1] == '/':
                out.append('  ')
                i += 2
                blok = False
                continue
            out.append('\n' if c == '\n' else ' ')
        elif q is not None:
            out.append(c)
            if c == q or c == '\n':
                q = None
        elif c in "'\"":
            q = c
            out.append(c)
        elif (c == '/' and i + 1 < n and text[i + 1] == '/') or (
                c == '-' and i + 1 < n and text[i + 1] == '-'):
            # satır yorumu (`//` ya da `--`): satır sonuna kadar olduğu gibi bırak (yorumu_kirp
            # keser). kaynak çekirdek #402 Y3: `--` tanınmıyordu ⇒ `-- not: /* eski` satırındaki `/*`
            # blok maskeyi AÇIYOR, dosyanın geri kalanı maskeleniyordu (yerleşik `abap.cuky`
            # alanı görünmez ⇒ sahte "tabloda yok" BLOCKER; aynı satır `//` ile temizdi).
            j = text.find('\n', i)
            j = n if j < 0 else j
            out.append(text[i:j])
            i = j
            continue
        elif c == '/' and i + 1 < n and text[i + 1] == '*':
            out.append('  ')
            i += 2
            blok = True
            continue
        else:
            out.append(c)
        i += 1
    return ''.join(out)


def yorumlari_maskele(text: str) -> str:
    """Blok (`/* */`) + satır sonu (`//`, `--`) yorumlarını atar; satır SAYISI ve numaraları korunur.

    Tırnak içindeki `//` / `--` / `/*` korunur (`yorumu_kirp` / `blok_yorumu_maskele` sözleşmesi).
    Alan taraması (`ad : tip;`) bu metin üzerinde yapılır ⇒ yorumdaki `old_fld : zde_old;` alan sayılmaz.
    Satır sonu karakteriyle bölünür/birleştirilir (`splitlines` DEĞİL) ⇒ sondaki satır sonu ve CR aynen kalır.
    """
    return "\n".join(yorumu_kirp(s) for s in blok_yorumu_maskele(text).split("\n"))
