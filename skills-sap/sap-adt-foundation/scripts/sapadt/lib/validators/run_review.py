"""
run_review.py — Reviewer Agent Orchestrator (Pre-Flight Quality Gate)

Coordinator SAP yazma işlemi yapmadan önce çağırır. Görev tipine göre ilgili
validator'ları sırayla çalıştırır, yapılandırılmış rapor üretir.

Mantık:
  - Görev tipi → checklist (playbook/checklists/<task>.md) + validator zinciri
  - Her validator deterministik (LLM-bağımsız)
  - Çıktı: PASS / WARNING / BLOCKER (verdict) + checklist results + blind spots
  - BLOCKER → coordinator yazma yapmadan düzeltmeli (exit 1)
  - WARNING → coordinator yazabilir ama kullanıcıya bildirmeli (exit 0)
  - ⊘ SKIP → o gate ÖLÇÜM ÜRETMEDİ. İKİ ayrı yol aynı sonuca çıkar:
      (a) script bulunamadı  → hiç koşmadı;
      (b) script koştu, `exit 0` döndü ama stdout'ta `AXET-GATE-STATUS ... measured=false`
          (2026-08-29, kayıt #5③): "koşturamadım" (config yok / obje tipi desteklenmiyor /
          araç yok) — `exit 0` görülse bile TEMİZ DEĞİL.
    "Koşmadı" ≠ "temiz": SKIP kendi şiddetiyle verdict'e SAYILIR (eksik BLOCKER →
    BLOCKER, eksik WARNING → WARNING). BOŞ ZİNCİL (dtel_update, rap_service_binding)
    bundan AYRIDIR: orada koşacak gate olmadığı BİLİNÇLİ karardır ve PASS kalır —
    kayıtsız eksiklik ile kayıtlı boşluk aynı şey değildir.
  - ~ SESSİZ BULGU (2026-09-04, Q239): gate KOŞTU, ÖLÇTÜ ve BULGU BASTI ama `exit 0`
    döndü (kendi sözleşmesi "yalnız WARNING → rc 0" diyor). Rapor bunu artık `~` ile
    işaretler ve bulgu metnini AYNEN basar. ⛔ Verdict aritmetiğine GİRMEZ — bu bir
    GÖRÜNÜRLÜK kalemidir; şiddet-etiketi ↔ çıkış-kodu hizalaması AYRI bir karardır.
  - ⊘ ZİNCİR YOK (2026-09-04, Q238): boş zincirde verdict `PASS` + exit 0 KALIR ama
    rapor GÖVDESİ (stdout) artık bunu söyler; eskiden yalnız stderr'de bir satır vardı
    ve stdout "✓ COORDINATOR: PASS" diyordu ⇒ iki akışı ayrı yakalayan okuyucu için
    "ölçüldü ve temiz" ile "ölçecek gate yok" AYNI görünüyordu.

Kullanım:
    # CDS yaratma öncesi
    python scripts/validators/run_review.py --task cds_creation --artifact <source_root>/SD/ZDEMO1_CLC/cds/ZDEMO1_DDL_X.cds

    # Tablo update öncesi
    python scripts/validators/run_review.py --task table_update --artifact <path>

    # Struct yaratma öncesi (Sprint 6)
    python scripts/validators/run_review.py --task struct_creation --artifact <path>

    # Output JSON (programatik kullanım)
    python scripts/validators/run_review.py --task cds_creation --artifact <path> --json

Exit kodu:
    0 — PASS veya WARNING (coordinator devam edebilir)
    1 — BLOCKER (coordinator durmalı)
    2 — Validator hatası (script çalışmadı)

Bkz. ADR 0006 — Reviewer Agent Pattern.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime

if sys.platform == 'win32':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

VALIDATORS_DIR = Path(__file__).parent
# `utils.butce` bir üst dizinde (lib/) — bu script alt süreç olarak da koşar, sys.path garanti değil.
if str(VALIDATORS_DIR.parent) not in sys.path:
    sys.path.insert(0, str(VALIDATORS_DIR.parent))
from utils import butce  # noqa: E402
# PROJE kökü (aXet): env AXET_SAP_PROJECT_DIR (CLI basar) → cwd.
# ⚠ Proje-lokal validator araması (`<proje>/scripts/validators-local/`) aXet'te KALDIRILDI:
# zincirdeki bir BLOCKER gate'in yerine proje dizinine konan aynı adlı bir dosya geçerdi —
# model proje dizinine yazabildiği için bu, reviewer'ı dosyayla atlatma yoluydu.
PROJ_ROOT = Path(os.environ.get("AXET_SAP_PROJECT_DIR") or os.getcwd())

# Görev tipi → validator zinciri
# Her validator: (script_name, severity_default, description)
TASK_VALIDATORS = {
    'cds_creation': [
        ('check_window_function_compatibility.py', 'BLOCKER',
         'Window function (OVER PARTITION BY) yok mu'),
        ('check_deprecated_annotations.py', 'WARNING',
         'preserveKey gibi deprecated annotation kontrolü'),
        ('check_cds_currency_reference.py', 'BLOCKER',
         'CURR/QUAN field annotation qualified format'),
        ('check_released_objects.py', 'WARNING',
         'Clean Core: non-released std tablo (FROM/JOIN) → released successor öner (MARA->I_Product)'),
        ('check_standard_table_fields.py', 'WARNING',
         'Std tablo alanları yeni sistemde gerçekten var mı (SAP GET; C-CDS-FROM-03)'),
    ],
    'cds_update': [
        ('check_window_function_compatibility.py', 'BLOCKER',
         'Window function yok mu'),
        ('check_deprecated_annotations.py', 'WARNING',
         'Deprecated annotation kontrolü'),
        ('check_cds_currency_reference.py', 'BLOCKER',
         'CURR/QUAN annotation kontrolü'),
        ('check_released_objects.py', 'WARNING',
         'Clean Core: non-released std tablo → released successor öner'),
    ],
    'table_creation': [
        ('check_struct_field_dtel_active.py', 'BLOCKER',
         'Kullanılan Z DTEL\'ler SAP\'de aktif mi (var olmayan/inaktif DTEL → aktivasyon fail)'),
        ('check_cds_currency_reference.py', 'BLOCKER',
         'CURR/QUAN field annotation qualified format (--type table)'),
        ('check_deprecated_annotations.py', 'WARNING',
         'Deprecated annotation'),
    ],
    'table_update': [
        ('check_struct_field_dtel_active.py', 'BLOCKER',
         'Kullanılan Z DTEL\'ler SAP\'de aktif mi (var olmayan/inaktif DTEL → aktivasyon fail)'),
        ('check_table_field_drop.py', 'BLOCKER',
         'Mevcut alan DROP / RENAME / TİP değişikliği (canlı SAP source diff — veri kaybı koruması)'),
        ('check_cds_currency_reference.py', 'BLOCKER',
         'Yeni eklenen CURR/QUAN field annotation kontrolü'),
        ('check_deprecated_annotations.py', 'WARNING',
         'Deprecated annotation'),
        ('check_standard_table_fields.py', 'WARNING',
         'Std tablo alanları yeni sistemde var mı (SAP GET; C-TBL-STD-01)'),
    ],
    'struct_creation': [
        ('check_struct_field_dtel_active.py', 'BLOCKER',
         'Kullanılan Z DTEL\'ler aktif mi'),
        ('check_cds_currency_reference.py', 'BLOCKER',
         'CURR/QUAN annotation kontrolü'),
        # aXet: `check_td_cancelled_fields.py` (WARNING) ÇIKARILDI — müşteri projesine özgü
        # (belirli bir teknik tasarımda iptal edilen alanlar) ve kaynak çekirdekte de yoktu
        # (yalnız proje-lokal kopyası vardı → orada her koşumda SKIP=WARNING üretiyordu).
        ('check_deprecated_annotations.py', 'WARNING',
         'Deprecated annotation'),
        ('check_standard_table_fields.py', 'WARNING',
         'Std tablo alanları yeni sistemde var mı (SAP GET; C-STR-FIELD-03)'),
    ],
    'struct_post_create': [
        ('check_sap_struct_consistency.py', 'BLOCKER',
         'SAP\'deki struct lokal artifact ile tutarlı mı (placeholder/field count diff)'),
        ('check_sap_active_version.py', 'BLOCKER',
         'SAP\'de version="active" mi'),
    ],
    'sap_active_check': [
        ('check_sap_active_version.py', 'BLOCKER',
         'SAP\'de version="active" mi'),
        ('check_sap_master_language.py', 'WARNING',
         'Z obje masterLanguage = sap-project.json master_language mı (post-create)'),
    ],
    'domain_creation_csv': [
        ('check_domain_output_length.py', 'BLOCKER',
         'Domain output length formula kontrolü'),
    ],
    # #30② (2026-08-29): `dtel_update` VARDI ama `dtel_creation` YOKTU → `--task
    # dtel_creation` argparse'ta exit 2 ile reddediliyordu, yani DTEL YARATIMI hiç
    # review edilemiyordu. ⛔ SIRA: önce GERÇEK kontrol (check_dtel_creation_labels.py)
    # yazıldı, görev SONRA bağlandı. Tersi (önce boş görev) exit 2'yi `PASS`+exit 0'a
    # çevirir ve sıfır kontrollü sahte-yeşil üretirdi — geçici bile olsa kabul edilemez.
    'dtel_creation': [
        ('check_dtel_creation_labels.py', 'BLOCKER',
         'DTEL yaratma CSV\'si: 4 label + description DOLU, uzunluklar sınırda, '
         'type_kind=domain ise domain bağı tam (ADR 0005-D / madde D)'),
    ],
    'dtel_update': [
        # DTEL update için spesifik validator henüz yok — manual review.
        # ⚠ BOŞ ZİNCİL BİLİNÇLİDİR (docstring'deki "kayıtlı boşluk" istisnası) ve
        # `dtel_creation` doldurulduğu için buraya OTOMATİK devralınmaz: update'in
        # kendi tuzağı AYRIDIR (adt-domain-dtel.md §3b: `adtcore:description` XML'de
        # İKİ yerde geçer, düz re.sub PAKET açıklamasını da ezer) — o ayrı bir kalem.
    ],
    'class_push': [
        ('check_method_param_type_c.py', 'BLOCKER',
         'Source-based class method-param TYPE c LENGTH n → save-scan kırar (satırsız 400, adt-rap §34-A); TYPE string kullan'),
        ('check_decimal_write_to.py', 'WARNING',
         'API-body sınıfında WRITE..TO → decimal locale tuzağı (binlik ayıraç, Edm.Decimal 400); direkt atama'),
        ('check_amdp_comment_apostrophe.py', 'BLOCKER',
         'AMDP SQLScript `--` yorumunda apostrof → aktivasyon "multi-line literal" FAIL (BE-28c; syntax_check/abaplint görmez, activation-only)'),
        ('check_docu_itf_line_width.py', 'BLOCKER',
         'DOCU/F1 runner ITF iv_line >72 ham char → F1/SE61 görüntülemede kuyruk KIRPILIR (std/08 §3; depolama≤132≠görüntüleme≤72; DOC-F1-01)'),
        ('check_released_objects.py', 'WARNING',
         'Clean Core: ABAP SELECT FROM non-released std tablo → released CDS successor öner'),
        ('check_abaplint.py', 'WARNING',
         'abaplint (tuned): yapısal/mantık+hijyen (parser/unreachable/identical/empty/tab) — class/program'),
        # ⛔ KATEGORİ B (std tablo direkt I/U/D) MCP server-side guardrail + manual review.
        # Otoriter syntax = adt_syntax_check (SAP inactive); abaplint = offline pre-push + clean-code.
    ],
    # ─── aXet 2026-09-14 K1 (kullanıcı kararı "Uyan kontrolleri bağla") ─────────
    # prog/include ve intf push'u eskiden `None` idi (SKIP + "PRE-FLIGHT KOŞMADI").
    # Yalnız bu tiplerin kaynağına UYAN class_push gate'leri bağlandı; önemler class_push ile AYNI
    # (tests/test_verdict_reviewer_k1_d1.py::K1b çiviler). Uymayanlar bilinçli dışarıda:
    # amdp_comment_apostrophe / docu_itf_line_width (sınıf kaynağına özgü), method_param_type_c
    # programda (METHODS imzası sınıf/arayüz ekseni), abaplint arayüzde (`detect()` desteklemiyor).
    # ÖLÇÜLDÜ (çevrimdışı, 2026-09-14): include ve `PROGRAM` satırlı modül havuzunda abaplint
    # `measured=false reason=unsupported-object-type` → SKIP = WARNING (engellemez, ÖLÇÜLEMEDİ görünür).
    'program_push': [
        ('check_abaplint.py', 'WARNING',
         'abaplint (tuned) — program; include ve REPORT satırsız program → measured=false (ÖLÇÜLEMEDİ)'),
        ('check_released_objects.py', 'WARNING',
         'Clean Core: ABAP SELECT FROM non-released std tablo → released CDS successor öner'),
        ('check_decimal_write_to.py', 'WARNING',
         'API gövdesi kuran kodda WRITE..TO → decimal locale tuzağı; direkt atama'),
    ],
    'interface_push': [
        ('check_method_param_type_c.py', 'BLOCKER',
         'Arayüz METHODS imzasında TYPE c LENGTH n → save-scan kırar; TYPE string kullan'),
        ('check_decimal_write_to.py', 'WARNING',
         'WRITE..TO → decimal locale tuzağı'),
        ('check_released_objects.py', 'WARNING',
         'Clean Core: non-released std tablo → released successor öner'),
    ],
    # ─── aXet 2026-09-14 D1 (kullanıcı kararı "Dosyasız çağrıda da koşsun") + bug gate B2 ──────
    # `adt_struct_create` HER çağrıda (artefakt verilsin verilmesin) SAP'ye yazılacak DDL
    # `utils.ddic_dtel.yapi_ddl_kaynagi` ile geçici dosyaya yazılır (`sap_adt_lib.create_structure`
    # aynı render'ı PUT eder) ve YALNIZ bu gate koşar (struct_creation'ın diğer gate'leri annotation/
    # standart alan ister; fields[] bunları taşımaz → sahte BLOCKER üretirdi). Artefakt verilirse
    # artefaktın `struct_creation` zinciri AYRICA koşar (`_reviewer.run_reviewer_struct`, hükümler birleşir).
    'struct_fields_dtel': [
        ('check_struct_field_dtel_active.py', 'BLOCKER',
         'adt_struct_create her çağrıda: fields[]\'ten kurulan (yazılacak) DDL\'deki Z/Y + /ns/ DTEL\'ler SAP\'de var ve aktif mi'),
    ],
    # ─── RAP (ilk kez — ORDER pilotu; standards/05-coding-rap.md) ──────────────
    'rap_cds_creation': [
        # RAP view entity de DDLS — klasik CDS validator zinciri geçerli.
        # FARK: view entity'de @AbapCatalog.sqlViewName YASAK (checklist C-RAP-VE-02).
        ('check_window_function_compatibility.py', 'BLOCKER',
         'Window function (OVER PARTITION BY) yok mu'),
        ('check_deprecated_annotations.py', 'WARNING',
         'preserveKey gibi deprecated annotation kontrolü'),
        ('check_cds_currency_reference.py', 'BLOCKER',
         'CURR/QUAN field annotation qualified format'),
        ('check_rap_readonly_consumption.py', 'BLOCKER',
         'Read-only consumption: C_ projection join/base + as-projection-without-BO (§32.6k)'),
        ('check_reuse_gate.py', 'WARNING',
         'CBO reuse gate: repo-local duplicate + ortak ZDEMO0 VH reuse (ADR 0009)'),
        ('check_released_objects.py', 'WARNING',
         'Clean Core: non-released std tablo → released successor öner (MARA->I_Product)'),
        ('check_standard_table_fields.py', 'WARNING',
         'Std tablo alanları yeni sistemde var mı (SAP GET; C-RAP-VE-03)'),
    ],
    'rap_bdef_creation': [
        # Managed BDEF — optimistic locking (etag) + lock master zorunlu (gap-analysis #16).
        ('check_rap_managed_etag.py', 'BLOCKER',
         'Managed RAP: lock master + etag master (LAST_CHANGED_AT) eksik mi'),
        ('check_audit_fields_autofill.py', 'WARNING',
         'Audit alanları (created/changed by-at) var ama setAdmin determination yok (std 05 §9A)'),
        ('check_bdef_backtick.py', 'BLOCKER',
         'bdef yorumunda ters-tırnak → SAP çoğaltıyor (repo 2→canlı 8); sessiz+büyüyen drift (BE-62)'),
        # Diğer BDEF kontrolleri (C-RAP-BD-*) checklist + manual.
    ],
    'rap_service_binding': [
        # Service Definition/Binding/Publish — make-or-break, deterministik
        # validator yok. Manual + checklist C-RAP-SB-* (publish AI-otonom kanıtı).
    ],
    # ─── ITG S2 sign-off (ADR 0022, Faz-1) ── artifact = intake-artefaktı .md ──
    'itg_s2_signoff': [
        ('check_itg_signoff.py', 'BLOCKER',
         'S2 kapsamlı iş: intake-artefaktı tam (KAPSAM/etkilenen-obje/prior-art/kabul-kriteri) '
         '+ kullanıcı MUTABAKAT [x] var mı (ADR 0022; SAP-yazma öncesi)'),
    ],
}

# Checklist dosyaları — aXet: kaynak çekirdekteki playbook checklist'leri taşınmadı
# (yollar bu repoda yok; var olmayan dosyaya atıf okuru boşa gönderir). Boş sözlük =
# `checklist_reference: null`.
TASK_CHECKLISTS: dict = {}


# Repo-geneli tarayıcılar: <source_root>/** üzerinde kendileri os.walk yapar, POZİSYONEL artifact
# KABUL ETMEZ (argparse yalnız --strict/--quick). run_validator bunlara artifact GEÇMEZ
# (yoksa "unrecognized arguments" → crash → sahte BLOCKER). Gate korunur: check yine
# repo-geneli (yeni artifact da ERP içinde olduğundan kapsanır) çalışır + gate'ler.
# aXet: zincirde adı geçen ama BU dizinde yaşamayan validator'lar → template içindeki GERÇEK yeri.
# `check_itg_signoff.py` (ITG S2 sign-off) aXet'te `sap-intake-triage` skill'ine taşındı ve adı
# `check_intake_signoff.py` oldu (aynı CLI: pozisyonel artefakt, bulgu → exit 1). Kopyalanmadı —
# tek kaynak orada kalır. Yol template-içidir (proje dizini DEĞİL: model proje dizinine yazabilir,
# oraya konan aynı adlı dosya BLOCKER gate'in yerine geçemesin). VALIDATORS_DIR.parents[4] = skills-sap/.
HARICI_VALIDATORLER = {
    'check_itg_signoff.py': (VALIDATORS_DIR.parents[4] / 'sap-intake-triage' / 'scripts'
                             / 'check_intake_signoff.py'),
}


def validator_yolu(script_name: str) -> Path:
    """Zincirdeki script adının çalıştırılacak dosyası (harici eşleme → bu dizin)."""
    return HARICI_VALIDATORLER.get(script_name, VALIDATORS_DIR / script_name)


REPO_WIDE_SCANNERS = {
    # (T1.12, 2026-07-31: check_amdp_comment_apostrophe ÇIKARILDI — artık pozisyonel
    #  tek-artifact kabul ediyor; push-anı yalnız push edilen dosyayı tarar, repo-geneli
    #  tarama run_all+CI katmanında sürer. Boş küme meşru — mekanizma yeni üye için durur.)
}


def sonuc_kaydi(validator: str, severity: str, status: str, description: str,
                stdout: str = '', stderr: str = '', message: str = '',
                olcum_yok: bool = False) -> dict:
    """Zincir-sonucu kaydını TEK yerden üret — her kayıt AYNI anahtar kümesini taşır.

    ⛔ SINIF-FIX (2026-08-01, KAYIT S1): SKIP dalı elle kurulmuş bir sözlük döndürüyordu
    ve `stdout`/`stderr` anahtarları YOKTU. Raporlama döngüsü (`elif r['stdout']`) o kaydı
    okuyunca `KeyError: 'stdout'` → süreç çöktü → **VERDICT satırı HİÇ BASILMADI** (exit 1
    ile ayırt edilemez bir "BLOCKER"). Kod yorumu "← KeyError fix" diyordu ama fix eksikti:
    kayda yalnız `description` eklenmişti. Tek-üretici kalıbı bu sınıfı yapısal kapatır —
    yeni bir durum eklendiğinde de anahtar kümesi bozulamaz.
    """
    return {
        'validator': validator,
        'severity': severity,
        'status': status,          # PASS | FAIL | SKIP
        'description': description,
        'stdout': stdout,
        'stderr': stderr,
        'message': message,        # SKIP sebebi (koşmadıysa NEDEN koşmadı)
        # ⛔ SKIP'in İKİ AYRI KÖKENİ VARDIR ve `--cevrimdisi` YALNIZ BİRİNİ indirir:
        #   olcum_yok=True  → gate KOŞTU, exit 0 verdi ama `measured=false` dedi
        #                     ("SAP'ye ulaşamadım") → çevrimdışı modda WARNING'e iner.
        #   olcum_yok=False → gate'in DOSYASI YOK (silinmiş/kurulmamış) → ASLA inmez.
        # İkisini birleştirmek 2026-08-01 S2 dersini geri açardı: "gate'i SİLMEK, onu
        # geçmenin en kolay yolu". Çevrimdışı olmak bir gate'in kaybolmasını affetmez.
        'olcum_yok': olcum_yok,
    }


# ── ZİNCİR SÜRE BÜTÇESİ (K10) ─────────────────────────────────────────────────────────────────────
# ⛔ ÖLÇÜLEN KUSUR (2026-09-17): buradaki validator-başı zaman aşımı SABİT 60 sn idi, sarmalayıcı
# (`_reviewer.run_reviewer`) ise tüm zinciri 30 sn'de kesiyordu ⇒ 60 sn'lik dala HİÇ ULAŞILAMIYORDU
# (ölü dal) ve hükmü daima sarmalayıcının KÖR kesmesi veriyordu: hangi validator'da takıldığı,
# kaçının koştuğu raporlanamıyordu. Artık sıra YAPISAL: L3 gate-içi < L2 (burası) < L1 sarmalayıcı.
# Tek ayar düğmesi `AXET_REVIEWER_BUTCE_SN`; dağıtım `utils/butce.py`de (dayanak + ölçümler orada).
_ZINCIR_SON: float | None = None      # monotonic deadline; main() kurar


def zincir_kalan_sn() -> float:
    """Zincire kalan süre. `main()` dışından çağrılırsa (tekil kullanım) tam zincir bütçesi."""
    if _ZINCIR_SON is None:
        return butce.zincir_butce_sn()
    return _ZINCIR_SON - time.monotonic()


def run_validator(script_path: Path, artifact: str | None, extra_args: list[str],
                  zaman_asimi_sn: float | None = None) -> tuple[int, str, str]:
    """Validator script'ini çalıştır, (exit_code, stdout, stderr) döner.

    artifact=None → pozisyonel artifact geçilmez (repo-geneli tarayıcılar için).
    zaman_asimi_sn=None → zincire KALAN süre (asla sarmalayıcı bütçesinden büyük olamaz)."""
    if zaman_asimi_sn is None:
        zaman_asimi_sn = zincir_kalan_sn()
    cmd = [sys.executable, str(script_path)] + ([artifact] if artifact else []) + extra_args
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8',
                           errors='replace', timeout=zaman_asimi_sn)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return 2, '', (f'TIMEOUT: {script_path.name} zincir süre bütçesini aştı '
                       f'({zaman_asimi_sn:.1f} sn). ÖLÇÜLEMEDİ — "temiz" DEĞİL. '
                       + butce.nasil_uzatilir())
    except Exception as e:
        return 2, '', f'EXCEPTION: {script_path.name}: {e}'


# ── AXET-GATE-STATUS SÖZLEŞMESİ — TÜKETİCİ UCU (2026-08-29, kayıt #5③) ──────────────
# ÜRETİCİ ucu AYRI dosyadadır (`check_abaplint.py`, 2026-08-29'da eklendi) ve şu tek
# satırı stdout'a basar:
#
#   AXET-GATE-STATUS: gate=<ad> status=<OK|FINDING|SKIPPED|FAIL> measured=<true|false> reason=<slug>
#
# SORUN (ölçüldü): burada `status = 'PASS' if rc == 0 else 'FAIL'` yazıyordu. Üretici
# tarafta `exit 0`'ın ÜÇ ayrı anlamı var — "ölçtüm, temiz" · "config yok" · "bu obje
# tipini koşturamıyorum" · "npx yok" — ve üçü de burada `PASS` olarak kaydediliyordu.
# Yani sözleşmenin iki ucu vardı ama BİRBİRİNE DEĞMİYORDU: "koşturamadım" ile "temiz"
# reviewer için AYNI olaydı ("gate'lenmemiş kural ≈ kuralsız").
#
# ⛔ ÇIKIŞ KODU DEĞİŞTİRİLMEDİ (ne burada ne üreticide): üreticinin `return 0`'ı
#    gerekçeli bir karardır (offline reviewer zinciri kırılmasın). Tek taraflı
#    değiştirmek her offline class push'unda yeni bir WARNING üretirdi. Ayırt
#    edilebilirlik ÇIKIŞ KODUNA değil, bu AYRI KANALA dayanır.
#
# SÖZLEŞME JENERİKTİR: `gate=` alanı vardır çünkü ileride başka gate'ler de aynı satırı
# basacak. Aynı aile ÖLÇÜLDÜ (2026-08-29): `check_cds_srvd_comment_syntax` ·
# `check_standard_table_fields` ("SAP bağlantısı kurulamadı → return 0"). Onlar bu turda
# DEĞİŞTİRİLMEDİ; satırı basmaya başladıkları gün bu ayrıştırıcı onları da karşılar.
# (`check_cds_currency_reference` zaten rc=2 sözleşmesi taşır — ayrı ve iyi bir örnek.)
#
# ⚠ MARKÖRÜ TARİF EDEN METİN BEYAN SAYILMAZ — iki ayrı çapa:
#   ① satır-başı çapası (`^`, re.M) → yorum/docstring içindeki girintili örnekler elenir;
#   ② `measured=(true|false)` TAM eşleşme → sözleşmeyi ANLATAN `measured=<true|false>`
#      şablon metni (üreticinin kendi docstring'i) beyan sanılmaz.
_GATE_DURUM_RE = re.compile(
    r'^AXET-GATE-STATUS:\s+gate=(?P<gate>\S+)\s+status=(?P<status>\S+)\s+'
    r'measured=(?P<measured>true|false)\s+reason=(?P<reason>\S+)\s*$', re.M)

# ⛔ YABANCI ÖNEK FAIL-CLOSED (2026-09-14, önek `AXET-` olarak yeniden adlandırıldı; geçiş
# dönemi YOK, eski ad KABUL EDİLMEZ). "Kabul etmemek" = yok saymak DEĞİLDİR: yok sayılan
# satır `beyan=None` → `rc == 0` → PASS olur (ÖLÇÜLDÜ) ve eski önekle `measured=false`
# basan bayat bir validator kopyası BLOCKER'ını sessizce gizlerdi. Bu yüzden geçerli bir
# `AXET-` beyanı yoksa ve stdout'ta satır-başında BAŞKA önekli bir `-GATE-STATUS:` satırı
# varsa, bu "ölçüm kanıtı yok" sayılır (measured=false, reason=taninmayan-onek-<önek>).
_YABANCI_GATE_DURUM_RE = re.compile(r'^(?P<onek>[^\s:]+)-GATE-STATUS:', re.M)

# ⛔ BİÇİMİ BOZUK `AXET-` SATIRI FAIL-CLOSED: satır-başında `AXET-GATE-STATUS:` var ama tam
# sözleşmeye uymuyor (ör. `measured=maybe`, boşluklu `reason`, eksik alan). Yok sayılsaydı
# `beyan=None` → `rc == 0` → PASS olurdu (ÖLÇÜLDÜ). Böyle bir satır "ölçüm kanıtı yok" sayılır
# (measured=false, reason=bicim-bozuk). Geçerli bir beyanla BİRLİKTE basılmışsa da bozuk satır
# kazanır: çelişkili beyan ölçüm kanıtı değildir. Girintili (tarif eden) metin çapaya takılmaz.
_AXET_GATE_SATIRI_RE = re.compile(r'^AXET-GATE-STATUS:.*$', re.M)


def gate_durum_beyani(stdout: str, script_name: str) -> dict | None:
    """stdout'taki AXET-GATE-STATUS beyanı (yoksa None → BUGÜNKÜ davranış korunur).

    Birden çok beyan varsa: önce `gate=` alanı KOŞAN script'in adıyla eşleşenler
    süzülür (bir validator başka bir gate'in çıktısını iletiyorsa yabancı beyan
    okunmasın), eşleşen yoksa SON beyan alınır (script'in nihai sözü). İki dal da
    korpusta ayrı ayrı ölçülür — ölü dal bırakılmaz.

    Geçerli beyan yok ama satır-başında `AXET-` dışı önekli bir durum satırı varsa
    (ör. yeniden adlandırma öncesi basılmış satır) → `measured=false` döner; asla None
    (= sessiz PASS) değil. Bkz. `_YABANCI_GATE_DURUM_RE` üstündeki gerekçe.

    Satır-başında `AXET-GATE-STATUS:` olup tam sözleşmeye uymayan bir satır varsa →
    `measured=false`, `reason=bicim-bozuk` (geçerli beyanlar olsa bile). Bkz.
    `_AXET_GATE_SATIRI_RE` üstündeki gerekçe.
    """
    if any(not _GATE_DURUM_RE.fullmatch(m.group(0)) for m in _AXET_GATE_SATIRI_RE.finditer(stdout or '')):
        return {'gate': Path(script_name).stem, 'status': 'SKIPPED', 'measured': 'false',
                'reason': 'bicim-bozuk'}
    beyanlar = [m.groupdict() for m in _GATE_DURUM_RE.finditer(stdout or '')]
    if not beyanlar:
        yabanci = [m.group('onek') for m in _YABANCI_GATE_DURUM_RE.finditer(stdout or '')
                   if m.group('onek') != 'AXET']
        if yabanci:
            return {'gate': Path(script_name).stem, 'status': 'SKIPPED', 'measured': 'false',
                    'reason': f'taninmayan-onek-{yabanci[-1]}'}
        return None
    kendi = [b for b in beyanlar if b['gate'] == Path(script_name).stem]
    return (kendi or beyanlar)[-1]


def main() -> int:
    parser = argparse.ArgumentParser(description='Reviewer Agent Orchestrator')
    parser.add_argument('--task', required=True, choices=list(TASK_VALIDATORS.keys()),
                        help='Görev tipi')
    parser.add_argument('--artifact', required=True, help='İncelenecek dosya path')
    parser.add_argument('--json', action='store_true', help='JSON çıktı (programatik)')
    parser.add_argument('--strict', action='store_true', help='WARNING\'i de BLOCKER say')
    parser.add_argument('--cevrimdisi', action='store_true',
                        help='BİLİNÇLİ ÇEVRİMDIŞI BEYANI: SAP\'ye ulaşamayan gate\'lerin '
                             '(measured=false) BLOCKER\'ı WARNING\'e iner. Gerçek bulgular '
                             've dosyası olmayan gate\'ler ETKİLENMEZ. (aXet: env karşılığı YOK)')
    parser.add_argument('--ack-drop', default='',
                        help='Onaylı tablo DROP alanları (virgülle) — check_table_field_drop\'a '
                             'iletilir. SADECE adı verilen alanlar ACK-WARNING; isimsiz drop/tip '
                             'değişikliği yine BLOCKER. Kullanıcı+lider bilinçli onayı (ADR 0005-B).')
    args = parser.parse_args()

    # ⛔ OTOMATİK ÇIKARIM YOK (bilinçli): `.conn_adt` yokluğuna BAKMIYORUZ. Kullanıcının
    # `.conn_adt`'si VARdır ve yalnız VPN kapalıdır; yokluktan çıkarım tam da TEHLİKELİ
    # vakayı ("bağlıyım sanıyorum ama ölçmedim") sessizce affederdi. Niyet AÇIK olmalı.
    # aXet: env ile açma KALDIRILDI — araç katmanı alt süreci ortamı miras alır; bir env
    # değişkeniyle BLOCKER'ı WARNING'e indirmek, modelin reviewer'ı sessizce gevşetmesi olurdu.
    cevrimdisi = args.cevrimdisi

    artifact_path = Path(args.artifact)
    if not artifact_path.exists():
        print(f'HATA: {artifact_path} bulunamadı', file=sys.stderr)
        return 2

    # K10 — zincir süre bütçesi burada başlar (sarmalayıcı bütçesi eksi run_review payı).
    global _ZINCIR_SON
    _ZINCIR_SON = time.monotonic() + butce.zincir_butce_sn()

    validators = TASK_VALIDATORS.get(args.task, [])
    # ⛔ Q238 (2026-09-04) — BOŞ ZİNCİR: HÜKÜM DEĞİŞMEDİ, GÖRÜNÜRLÜK EKLENDİ.
    # "Koşacak gate yok" BİLİNÇLİ ve KAYITLI bir boşluktur (modül docstring'i;
    # `dtel_update` · `rap_service_binding`) ⇒ verdict `PASS` + exit 0 BİT-BAZINDA
    # KORUNUR (`reviewer_skip_sozlesmesi` V6 bunu çiviler; bozmak meşru push'ları
    # bloklardı — "kayıtsız eksiklik ≠ kayıtlı boşluk").
    # KUSUR HÜKÜMDE DEĞİL, OKUNUŞTAYDI: bu uyarı YALNIZ stderr'e gidiyordu, `PASS`
    # hükmü ise stdout'a ⇒ iki akışı AYRI yakalayan okuyucu (ajan/log/rapor) yalnız
    # "VERDICT: PASS" + "✓ COORDINATOR: PASS" görüyordu (ölçüldü 2026-09-03: SRVD
    # `rap_service_binding` koşumu). Bayrak artık rapor GÖVDESİNE (stdout) da basılır
    # ve JSON'da `zincir_bos` alanı olarak taşınır.
    zincir_bos = not validators
    if zincir_bos:
        print(f'UYARI: {args.task} için validator zinciri tanımlı değil. '
              f'Manual review gereklidir.', file=sys.stderr)

    # Validator zincirini çalıştır
    results = []
    for script_name, default_severity, description in validators:
        # Arama sırası (2026-07-10 düzeltmesi): önce core VALIDATORS_DIR, sonra PROJE
        # scripts/validators-local/. Eskiden yalnız core'a bakılıyordu → proje-lokal
        # validator'lar (ör. check_td_cancelled_fields.py) HER ZAMAN 'bulunamadı' SKIP
        # veriyordu ve SKIP verdict'e sayılmadığı için sahte-PASS üretiyordu.
        script_path = validator_yolu(script_name)
        if not script_path.exists():
            results.append(sonuc_kaydi(
                script_name, default_severity, 'SKIP', description,
                message=f'PRE-FLIGHT KOŞMADI: {script_name} bulunamadı '
                        f'(aranan: {script_path.parent}) — PASS SANMA.'))
            continue

        # Tablo tipi için --type table extra arg
        extra_args = []
        if args.task in ('table_creation', 'table_update') and 'cds_currency' in script_name:
            extra_args = ['--type', 'table']
        # Onaylı DROP bayrağı yalnız drop-guard'a iletilir (hedefli ack)
        if script_name == 'check_table_field_drop.py' and args.ack_drop:
            extra_args = extra_args + ['--ack-drop', args.ack_drop]

        # Repo-geneli tarayıcılar (kendileri <source_root>/** os.walk eder) pozisyonel artifact KABUL ETMEZ
        # → artifact=None geç (yoksa "unrecognized arguments" → sahte BLOCKER).
        review_artifact = None if script_name in REPO_WIDE_SCANNERS else args.artifact
        # K10: bütçe bittiyse gate'i BAŞLATMA — 0 sn'lik bir koşum "temiz" üretemez, yalnız
        # gürültü ve belirsizlik üretir. Koşmayan gate SKIP + `olcum_yok` ⇒ KENDİ şiddetiyle
        # verdict'e sayılır (BLOCKER gate → BLOCKER). "Ölçülemedi ≠ temiz".
        if zincir_kalan_sn() <= 0:
            results.append(sonuc_kaydi(
                script_name, default_severity, 'SKIP', description,
                message=(f'PRE-FLIGHT KOŞMADI: zincir süre bütçesi '
                         f'({butce.zincir_butce_sn():g} sn) önceki gate\'lerde doldu — '
                         f'{script_name} hiç başlatılmadı. ÖLÇÜLEMEDİ, PASS SANMA. '
                         + butce.nasil_uzatilir()),
                olcum_yok=True))
            continue
        rc, out, err = run_validator(script_path, review_artifact, extra_args)
        # AXET-GATE-STATUS tüketimi (kayıt #5③) — YALNIZ `rc == 0` dalında sorulur.
        # Gerekçe (kapsam niteleyicisi): `rc != 0` zaten GÜRÜLTÜLÜ bir sonuçtur (FAIL,
        # verdict'e sayılır) — orada "ölçüldü mü" sorusu sessizlik üretmez. Sessiz olan
        # tek yol `exit 0`'dır ve düzeltilen sınıf odur. `rc != 0` davranışı BİT-BAZINDA
        # korunur; genişletmek ayrı bir karardır (ölçülmedi ⇒ yapılmadı).
        beyan = gate_durum_beyani(out, script_name) if rc == 0 else None
        if beyan is not None and beyan['measured'] == 'false':
            # "Koşmadı" ≠ "temiz" — S2 sözleşmesinin AYNISI, tek farkla: orada gate'in
            # DOSYASI yoktu, burada dosya vardı ama ÖLÇÜM yapılmadı. İkisi de SKIP'tir
            # ve SKIP kendi şiddetiyle verdict'e sayılır (bkz. modül docstring'i).
            # check_abaplint WARNING sınıfı olduğu için sonuç WARNING'dir, BLOCKER DEĞİL.
            status = 'SKIP'
            olcum_yok = True
            mesaj = (f"PRE-FLIGHT ÖLÇMEDİ: {script_name} koştu ve exit 0 döndü ama "
                     f"AXET-GATE-STATUS satırı `measured=false` diyor "
                     f"(status={beyan['status']}, reason={beyan['reason']}) — "
                     f"bu 'temiz' DEĞİLDİR, PASS SANMA.")
        else:
            status = 'PASS' if rc == 0 else 'FAIL'
            mesaj = ''
            olcum_yok = False
        results.append(sonuc_kaydi(script_name, default_severity, status, description,
                                   stdout=out.strip(), stderr=err.strip(), message=mesaj,
                                   olcum_yok=olcum_yok))

    # ── Verdict ───────────────────────────────────────────────────────────────
    # ⛔ SKIP VERDICT'E SAYILIR (2026-08-01, KAYIT S2 — S1 ile AYNI kök: SKIP yolunun
    # sözleşmesi). Eskiden yalnız 'FAIL' sayılıyordu: BLOCKER olarak sınıflandırılmış bir
    # gate'in DOSYASI YOKSA (silinmiş / proje-lokal ama kurulmamış / adı değişmiş) zincir
    # sessizce atlanıyor ve VERDICT 'PASS' + exit 0 → "✓ COORDINATOR: PASS, devam
    # edebilirsin" yazıyordu. Yani gate'i SİLMEK, onu geçmenin en kolay yoluydu.
    # "Koşmadı" ≠ "temiz" (bulunamadı ≠ yok): eksik BLOCKER = BLOCKER, eksik WARNING =
    # WARNING. blocker_count/warning_count TOPLAM'dır (FAIL + SKIP); ayrıntı için
    # skipped_* alanları eklendi (tüketiciler: MCP _reviewer → atom.py/composite.py rapor).
    failed_blocker = sum(1 for r in results if r['status'] == 'FAIL' and r['severity'] == 'BLOCKER')
    failed_warning = sum(1 for r in results if r['status'] == 'FAIL' and r['severity'] == 'WARNING')
    skipped_blocker = sum(1 for r in results if r['status'] == 'SKIP' and r['severity'] == 'BLOCKER')
    skipped_warning = sum(1 for r in results if r['status'] == 'SKIP' and r['severity'] == 'WARNING')
    # ── Q239 (2026-09-04) — SESSİZ BULGU: gate KOŞTU, ÖLÇTÜ, BULGU BASTI ama rc=0 ────
    # `status == 'PASS'` + `stderr` DOLU. Bu SKIP DEĞİLDİR (ölçüm yapıldı) ve FAIL de
    # değildir (gate kendi sözleşmesinde "sadece WARNING → rc 0" diyor). Bugüne kadar
    # raporlama döngüsü PASS dalında stderr'i HİÇ OKUMUYORDU ⇒ `✓ [BLOCKER] gate` satırı
    # altında 3 bulgu SESSİZCE yutuluyordu (ölçüldü: `check_cds_currency_reference`,
    # tüketici projede bir CDS → 3 ihlal, `run_review` çıktısında SIFIR satır).
    # ⛔ VERDICT ARİTMETİĞİNE GİRMEZ (bilinçli, ADR 0019 moratoryumu): şiddet-etiketi ile
    # çıkış-kodu sözleşmesini hizalamak AYRI bir karardır (Q239③). Burada YALNIZ bilgi
    # eklenir — hiçbir koşum sınıf değiştirmez, hiçbir exit kodu değişmez.
    sessiz_bulgular = [r for r in results if r['status'] == 'PASS' and r['stderr']]
    # ── ÇEVRİMDIŞI İNDİRİMİ (opt-in) ──────────────────────────────────────────
    # Yalnız ÖLÇÜM ÜRETMEYEN (measured=false) BLOCKER'lar iner. `failed_blocker`
    # (gate koştu, ÖLÇTÜ ve İHLAL BULDU) bu satırların HİÇBİRİNDE geçmez ⇒ gerçek
    # bulgu bayrakla asla WARNING'e düşemez. Sayaçlar KAYBOLMAZ: `skipped_blocker`
    # TOPLAM olarak JSON'da ve ekranda aynen kalır.
    indirilen = [r for r in results
                 if r['status'] == 'SKIP' and r['severity'] == 'BLOCKER'
                 and r.get('olcum_yok')] if cevrimdisi else []
    indirilen_ad = [r['validator'] for r in indirilen]

    blocker_count = failed_blocker + skipped_blocker - len(indirilen)
    warning_count = failed_warning + skipped_warning + len(indirilen)

    if blocker_count > 0:
        verdict = 'BLOCKER'
    elif warning_count > 0:
        verdict = 'WARNING'
    else:
        verdict = 'PASS'

    if args.strict and warning_count > 0:
        verdict = 'BLOCKER'

    # Checklist referansı
    checklist = TASK_CHECKLISTS.get(args.task)

    # JSON output (programatik)
    if args.json:
        output = {
            'timestamp': datetime.now().isoformat(),
            'task': args.task,
            'artifact': str(artifact_path),
            'verdict': verdict,
            # TOPLAM (FAIL + SKIP) — verdict'i süren sayılar. Ayrıntı aşağıda:
            'blocker_count': blocker_count,
            'warning_count': warning_count,
            'failed_blocker_count': failed_blocker,
            'failed_warning_count': failed_warning,
            'skipped_blocker_count': skipped_blocker,
            'skipped_warning_count': skipped_warning,
            # Çevrimdışı beyanı: tüketici kapsamın EKSİK olduğunu bilmeli.
            'cevrimdisi': cevrimdisi,
            'offline_downgraded_count': len(indirilen),
            'offline_downgraded_gates': indirilen_ad,
            # ⚠ KAPSAM GENİŞLETİLDİ (2026-09-04, Q238): boş zincir de "kapsam eksik"tir —
            # HİÇBİR gate koşmadıysa bu koşumun kapsamı sıfırdır. Alanın anlamı aynı
            # kalır ("bu koşum eksik ölçtü"), kaynağı `zincir_bos` ile ayırt edilir.
            'kapsam_eksik': bool(indirilen) or zincir_bos,
            # Q238 — bilinçli boşluk MAKİNECE de okunabilir olsun (verdict PASS kalır).
            'zincir_bos': zincir_bos,
            'kosan_gate_sayisi': len(results),
            # Q239 — rc=0 döndüğü için PASS sayılan ama BULGU BASAN gate'ler.
            # ⛔ Verdict'e SAYILMAZ (görünürlük kalemi); tüketici kendi kararını verir.
            'sessiz_bulgu_count': len(sessiz_bulgular),
            'sessiz_bulgu_gates': [r['validator'] for r in sessiz_bulgular],
            'checklist_reference': checklist,
            'results': results,
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        # Human-readable
        print(f'\n{"="*70}')
        print(f'REVIEWER REPORT — {args.task}')
        print(f'Artifact: {artifact_path}')
        print(f'Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        print(f'{"="*70}\n')

        # ⛔ GÖRÜNÜRLÜK SÖZLEŞMESİ (Q239, 2026-09-04): "bir gate'in ÜRETTİĞİ hiçbir metin
        # bu döngüde SESSİZCE DÜŞMEZ." Eski döngü ÜÇ yerde metin düşürüyordu:
        #   ① PASS + stderr DOLU        → stderr HİÇ okunmuyordu (Q239'un ölçülmüş vakası)
        #   ② FAIL + stderr BOŞ         → stdout'a düşülmüyordu ⇒ `✗` satırı GEREKÇESİZ
        #   ③ PASS + çok satırlı stdout → yalnız İLK satır (kapsam/paydaş satırları düşer)
        # Üçü de AYNI sınıf: "kapı konuştu, rapor duymadı". ⚠ Hiçbiri verdict/exit
        # değiştirmez — bilgi eklenir, hüküm eklenmez.
        for r in results:
            sessiz_bulgu = r['status'] == 'PASS' and bool(r['stderr'])
            # `~` = ÜÇÜNCÜ İŞARET: "koştu, ölçtü, BULGU var ama rc=0". `✓` (temiz) ile
            # `✗` (düştü) arasındaki bu boşluk okuyucuyu yanıltan tam yerdi.
            symbol = ('~' if sessiz_bulgu else
                      '✓' if r['status'] == 'PASS' else
                      ('✗' if r['status'] == 'FAIL' else '⊘'))
            print(f"{symbol} [{r['severity']}] {r['validator']}")
            print(f"  {r['description']}")
            if r['status'] == 'FAIL':
                # stderr ÖNCELİKLİ; BOŞSA stdout'a düş (② — gerekçesiz `✗` bırakma).
                for line in (r['stderr'] or r['stdout']).splitlines():
                    print(f"    {line}")
            elif r['status'] == 'SKIP':
                # Görünürlük şartı (B10 reçetesi): koşmayan gate SESSİZ kalmaz.
                print(f"    {r['message']}")
            else:
                if r['stdout']:
                    for line in r['stdout'].splitlines():   # ③ kırpma YOK
                        print(f"    {line}")
                if sessiz_bulgu:                            # ① asıl Q239 düzeltmesi
                    print(f"    ~ EXIT 0 AMA BULGU BASTI ({len(r['stderr'].splitlines())} "
                          f"satır, stderr) — bu 'temiz' DEĞİLDİR; verdict'e SAYILMAZ, "
                          f"OKU ve kendin karar ver:")
                    for line in r['stderr'].splitlines():
                        print(f"    {line}")
            print()

        if zincir_bos:
            # Q238 — hüküm (PASS/exit 0) korunur, SESSİZLİK kaldırılır.
            print(f'⊘ [KAPSAM] {args.task}: VALIDATOR ZİNCİRİ TANIMLI DEĞİL — '
                  f'bu koşumda HİÇBİR gate çalışmadı.')
            print('  Bu, KAYITLI ve bilinçli bir boşluktur (gate yok ⇒ verdict PASS '
                  'kalır), ama "PASS" burada "ölçüldü ve temiz" DEMEK DEĞİLDİR:')
            print('  "ölçülecek gate yok" demektir. Manuel review + checklist ZORUNLU.')
            print()

        print(f'{"="*70}')
        # Q238: hüküm satırı KENDİ kapsamını taşır (değer `PASS` olarak KALIR).
        print(f'VERDICT: {verdict}' + ('  (ZİNCİR YOK — hiçbir gate koşmadı; '
                                       'ölçüm YAPILMADI)' if zincir_bos else ''))
        # ⚠ Aritmetik GÖRÜNÜR olmalı: çevrimdışı indirimi BLOCKER'dan düşüp WARNING'e
        # eklediği için, indirimi yazmadan "BLOCKERS: 0 (… + KOŞMAYAN 1)" çelişkili okunur.
        _b_ek = ''
        if skipped_blocker:
            _b_ek = f'  (koşan-FAIL {failed_blocker} + KOŞMAYAN {skipped_blocker}'
            _b_ek += (f' − ÇEVRİMDIŞI-İNDİRİMİ {len(indirilen)})' if indirilen else ')')
        print(f'  BLOCKERS: {blocker_count}' + _b_ek)
        _w_ek = ''
        if skipped_warning or indirilen:
            _w_ek = f'  (koşan-FAIL {failed_warning} + KOŞMAYAN {skipped_warning}'
            _w_ek += (f' + ÇEVRİMDIŞI-İNDİRİMİ {len(indirilen)})' if indirilen else ')')
        print(f'  WARNINGS: {warning_count}' + _w_ek)
        if sessiz_bulgular:
            # Q239: sayaç `BLOCKERS/WARNINGS` satırlarına KARIŞMAZ — ayrı satır, ayrı
            # işaret. Karıştırmak verdict aritmetiğini değiştirmek olurdu.
            print(f'  ~ {len(sessiz_bulgular)} gate exit 0 döndü AMA BULGU BASTI '
                  f'(yukarıda `~` işaretli): '
                  f'{", ".join(r["validator"] for r in sessiz_bulgular)} — '
                  f'"exit 0" ≠ "temiz"; verdict\'e SAYILMAZ, sen oku.')
        if skipped_blocker or skipped_warning:
            print(f'  ⊘ {skipped_blocker + skipped_warning} gate ÖLÇÜM ÜRETMEDİ '
                  f'(script yok VEYA measured=false) — "koşmadı" ≠ "temiz". '
                  f'Sebep her ⊘ satırının altında yazılıdır.')
        if cevrimdisi:
            print(f'\n  ⚠⚠ ÇEVRİMDIŞI MOD (--cevrimdisi) — '
                  f'BU KOŞUMUN KAPSAMI EKSİKTİR.')
            if indirilen:
                print(f'     {len(indirilen)} BLOCKER gate ölçüm üretemedi ve '
                      f'BİLİNÇLİ olarak WARNING\'e indirildi:')
                for ad in indirilen_ad:
                    print(f'       - {ad}')
                print(f'     Bu gate\'ler SAP\'ye ulaşamadı; ihlal YOK demek DEĞİLDİR. '
                      f'Bağlantı gelince review\'i TEKRARLA.')
            else:
                print('     (indirilen gate yok — ölçüm üretemeyen BLOCKER bulunmadı)')
        if checklist:
            print(f'\nManuel checklist (ek kontrol için): {checklist}')
        print(f'{"="*70}\n')

        if verdict == 'BLOCKER':
            print('⛔ COORDINATOR: SAP yazma YASAK. Düzelt ve tekrar review iste.\n',
                  file=sys.stderr)
        elif verdict == 'WARNING':
            print('⚠ COORDINATOR: Yazabilirsin ama kullanıcıya bildir.\n', file=sys.stderr)
        elif zincir_bos:
            # Q238 — en yanıltıcı satır TAM BURASIYDI: ölçüm yokken "PASS, devam
            # edebilirsin" stdout'a basılıyordu. Hüküm (exit 0) aynı, cümle dürüst.
            print('⊘ COORDINATOR: ÖLÇÜM YAPILMADI (bu görev tipinde validator zinciri '
                  'yok) — devam edebilirsin ama bu bir "kapıdan geçti" DEĞİLDİR; '
                  'manuel review + checklist senin sorumluluğunda.\n')
        else:
            print('✓ COORDINATOR: PASS, devam edebilirsin.\n')

    return 1 if verdict == 'BLOCKER' else 0


if __name__ == '__main__':
    sys.exit(main())
