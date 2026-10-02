# sinif-validator-ailesi — validator'lar, zincir ve gate motoru (kritik yol)

## Tetik
Plandaki dosya bir `check_*.py`, `run_review.py`, `_reviewer.py`, `gate.py` ya da `validator-map.md`. Bu sınıfın çoğu üyesi `kritik_yol`'dur.

## Kapsam (harita.json)
| Alt sınıf | `etkin` | Özel adım | Ne demek |
|---|---|---|---|
| `validator-kok-script` | `aninda` | yok | anında geçerli |
| `validator-zincir-map` | `skill-cagrisi` | yok | skill'in bir sonraki çağrısında |
| `validator-gate-motor` | `aninda` | yok | anında geçerli |
| `validator-runner` | `aninda` | yok | anında geçerli |
| `validator` | `aninda` | yok | anında geçerli |
| `validator-ui5` | `aninda` | yok | anında geçerli |
| `validator-diger-skill` | `aninda` | yok | anında geçerli |
| `guardrail-adr` | `aninda` | yok | anında geçerli |

## Zorunlu ek adımlar
1. Eş dosyalar aynı pakette gelmeli: plan onları birlikte seçer — seçimi bozma.
2. Testler: `python skills-sap/sap-adt-foundation/tests/run_tests.py` (uzun) — güncelleme içinde
   KOŞMA (Z162), adım 10'da test borcuna yazılır, kapanıştan sonra `%testler`.
   `python -m unittest discover -s skills-sap/sap-code-review/tests -t skills-sap/sap-code-review/tests`
   (zincir ↔ tablo eşitliği) hızlıdır ve bütünlük turunda (adım 12) koşar.
3. **Akış adım 11 zorunlu — hüküm karşılaştırması (somut ölçüm, "baktım" yetmez):**
   Kontrol grubu kur: **aynı girdi, önce ve sonra.**
   - **Fixture'ı olan validator:** fixture takımı (`python skills-sap/sap-adt-foundation/tests/run_tests.py -k validator_fixtures`)
     uzundur ve güncelleme içinde KOŞULMAZ (Z162): takım adım 10'da test borcuna yazılır, her
     validator için `bad` → FAIL / `good` → PASS kapanıştan sonra `%testler` ile ölçülür. Güncelleme
     İÇİNDEKİ hüküm karşılaştırmasını bu dosya için de aşağıdaki fixture'sız yöntemle yap.
   - **Fixture'ı olmayan validator:** taban sürümünü `git show <taban>:<yol>` ile geçici bir dosyaya
     al; iki sürümü de AYNI örnek proje kökünde koş. Ortam değişkenini PowerShell'de AYRI
     SATIR olarak ver — `$env:AXET_SAP_PROJECT_DIR = '<kök>'`, sonra `python <validator yolu>`.
     (Ölçüldü 2026-09-18: POSIX öneki *AXET_SAP_PROJECT_DIR=<kök> python …* bu evde birincil
     kabuk olan PowerShell'de koşMAZ — *The term 'AXET_SAP_PROJECT_DIR=…' is not recognized*.)
     Çıkış kodunu ve `[İHLAL]` satırlarını karşılaştır.
   - **Zincir dosyası** (`run_review.py`, `_reviewer.py`, `gate.py`): aynı örnek dosyayla
     `python skills-sap/sap-adt-foundation/scripts/sapadt/lib/validators/run_review.py --task <görev> --artifact <örnek> --cevrimdisi --json`
     komutunu önce ve sonra koş; hükmü (PASS / WARNING / BLOCKER) karşılaştır.
   Fark çıkarsa SEBEBİNİ açıkla; açıklayamıyorsan DUR — "karşılaştırdım, fark yok" tek başına ölçüm değildir.
4. Yerelde gevşetilmiş bir kontrol varsa asgari güvence raporuna satır olarak girer.

## DUR
Eşlerden biri yerelde değişmiş (V3, yeni sürüm gelmiyor) diğeri güncelleniyorsa (V1) zincir
ayrışabilir: kullanıcıya göster, kendi başına "nasılsa çalışır" deme. Açıklanamayan hüküm farkı =
DUR.
