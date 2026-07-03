# Test ve Determinizm Rehberi

Bu doküman test mimarisini, determinizm garantilerinin nasıl otomatik
doğrulandığını, golden file sürecini ve edge case test matrisini tanımlar.

## Test Yerleşimi

```text
tests/
  unit/                     # modül bazlı unit testler (src yapısını aynalar)
  integration/
    test_pipeline.py        # uçtan uca pipeline + CLI run
    test_golden_outputs.py  # golden file regresyon testleri
    test_determinism.py     # determinizm garantileri
    test_cli_explain_e2e.py # explain komutu, gerçek dosyalarla
  fixtures/
    golden_inputs/          # golden senaryonun girdi CSV'leri
    golden_outputs/         # gün bazlı beklenen JSON çıktıları (day1/, day2/)
```

Çalıştırma: `pytest` (coverage kapısı `--cov-fail-under=85` otomatik uygulanır).

## Determinizm Garantileri ve Testleri

| Garanti | Test |
|---|---|
| Aynı input + run_date ⇒ bayt düzeyinde aynı çıktı | `test_two_independent_runs_produce_identical_bytes` |
| CSV satır sırası çıktıyı etkilemez | `test_input_row_ordering_does_not_change_outputs` |
| Geçmiş bir günün tekrar çalıştırılması ledger/badge geçmişini bozmaz (idempotency) | `test_multi_day_rerun_is_idempotent` |
| Aynı çalıştırmanın tekrarı ledger'ı duplike etmez | `test_pipeline_integration_runs_successfully_and_is_idempotent` |
| Aynı soru her zaman aynı cevabı üretir | `test_explain_is_deterministic` |
| İş kuralları regresyonu | golden file testleri (aşağıda) |

Determinizmin kaynak garantileri: sistem saati ve `random` kullanılmaz
(`run_date` parametresi esastır), tüm ID'ler SHA-256 tabanlı deterministik
üretilir, tüm sıralamalarda açık tie-break vardır.

## Golden File Senaryosu

Golden senaryo (`tests/fixtures/golden_inputs/`) iki ardışık günü aynı
output dizini üzerinde çalıştırır ve şu davranışları bilinçli olarak içerir:

- **U1**: 7 günlük izleme birikimi ile `C-03 Weekly Binge` (380 puan) iki gün
  üst üste kazanır; 2. gün 760 puanla **Bronze rozet eşiğini geçer**.
  `C-01` her gün tetiklenir ama önceliğe göre **suppress** edilir.
- **U2**: 1. gün `C-01` (80), 2. gün `C-02` (140) kazanır — günler arası
  farklı challenge seçimi.
- **U3 / U4**: 2. gün ikisi de 80 puandadır — **eşit puan alfabetik
  tie-break** (rank 3 ve 4).
- **C-04**: `is_active=false` — hiçbir zaman değerlendirilmez.

Beklenen çıktılar `tests/fixtures/golden_outputs/day1/` ve `day2/` altında
7'şer JSON dosyası olarak saklanır ve testte bayt düzeyinde karşılaştırılır
(satır sonları normalize edilir).

### Golden Dosyaları Güncelleme Süreci

Golden testler kırıldığında iki olasılık vardır:

1. **İstenmeyen regresyon** — davranış yanlışlıkla değişti. Kodu düzelt;
   golden dosyalara dokunma.
2. **Bilinçli iş kuralı değişikliği** — çıktı bilerek değişti. Bu durumda:

```bash
# 1. Senaryoyu temiz bir dizine çalıştır (day1 sonrası snapshot al):
gamification-engine run --activities tests/fixtures/golden_inputs/user_activities.csv \
  --challenges tests/fixtures/golden_inputs/challenges.csv \
  --output-dir /tmp/golden --run-date 2026-03-08
# 7 dosyayı tests/fixtures/golden_outputs/day1/ altına kopyala
gamification-engine run --activities tests/fixtures/golden_inputs/user_activities.csv \
  --challenges tests/fixtures/golden_inputs/challenges.csv \
  --output-dir /tmp/golden --run-date 2026-03-09
# 7 dosyayı tests/fixtures/golden_outputs/day2/ altına kopyala
```

3. Diff'i gözden geçir: değişiklik yalnızca beklediğin alanlarda mı?
4. Golden güncellemesini davranış değişikliğiyle **aynı commit'te**, commit
   mesajında gerekçesiyle birlikte yap.

`test_golden_scenario_covers_key_behaviours` testi, senaryo güncellenirken
rozet geçişi / tie-break / çok günlü birikim davranışlarının fixture'dan
silinmesini engeller.

## Edge Case Test Matrisi

| Alan | Edge case | Durum |
|---|---|---|
| Ingestion | Eksik header, hatalı tip, negatif değer, duplicate challenge ID | ✅ `tests/unit/ingestion/` |
| Ingestion | Satır sırası bağımsızlığı | ✅ `test_determinism.py` |
| State | Boş aktivite listesi, çoklu kullanıcı/tarih, aynı gün duplicate satır aggregate | ✅ `tests/unit/state/` |
| State | 7 gün penceresi sınırı, streak kırılması | ✅ `tests/unit/state/` |
| Rules | Desteklenmeyen alan/operatör reddi, eşit priority tie-break, inactive challenge | ✅ `tests/unit/rules/` |
| Ledger | Duplicate reward guard, append-only, idempotent re-run, negatif puan reddi | ✅ `tests/unit/ledger/` + integration |
| Badges | Eşik tam eşitliği, duplicate guard, atlanan eşiklerin geri verilmesi (Bronze+Silver birlikte) | ✅ `tests/unit/badges/` |
| Leaderboard | Eşit puan alfabetik sıra, ardışık rank, boş liste | ✅ unit + golden |
| Notifications | Duplicate guard, deterministik ID | ✅ `tests/unit/notifications/` |
| Explain | Bilinmeyen soru fallback'i, eksik kullanıcı state'i, boş ledger, suppress açıklaması, inactive challenge, geçersiz ID, parse edilemeyen koşul, tüm rozetler kazanılmış | ✅ unit + e2e |
| CLI | Geçersiz run-date, eksik input dosyası, bozuk JSON, beklenmeyen hata | ✅ `tests/unit/cli/` + e2e |
| LLM | Kapalı mod, bağlantı hatası, bozuk payload, boş cevap, kill switch | ✅ `tests/unit/ai/test_llm_adapter.py` |

## Fixture İsimlendirme Standardı

- `valid_*.csv` / `invalid_*.csv` — unit ingestion fixture'ları
- `golden_inputs/` — golden senaryo girdileri (değiştirirken goldenları yenile)
- `golden_outputs/<day>/<output>.json` — beklenen çıktılar
