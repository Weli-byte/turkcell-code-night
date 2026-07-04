# Sprint 24 — Gün Sonu Batch + Zamanlayıcı + Leaderboard (Faz 2)

Gün sonu mührü ve canlı sıralama. Batch, canlı değerlendirmeyle asla
çelişmez: tüm yazma yolları idempotent olduğundan yalnızca boşluk doldurur.

## Gün sonu batch (`services/daily_batch.py`)

- Tüm kullanıcılar **user_id sırasıyla** (determinizm) `evaluate_user_live`
  ile yeniden değerlendirilir; kaçan ödül/rozet varsa tamamlanır.
- Çelişememe garantisi kod değil, şema: `UNIQUE(user_id, reward_date)`
  (günde tek ödül), `UNIQUE(user_id, source_ref)` (ledger),
  `UNIQUE(user_id, badge_type)`, deterministik notification id'leri.
- Her koşu `runs` tablosuna kayıt yazar: `DailyBatchSummary`
  (users_processed, new_rewards, new_badges, new_notifications,
  leaderboard_size) JSON olarak.

## Zamanlayıcı (`services/scheduler.py`)

- **APScheduler yerine bilinçli olarak stdlib asyncio**: yeni bağımlılık
  yok, mypy strict tam tip güvenli, job enjekte edilebilir → test edilebilir.
- `DailyJobScheduler`: her gün `batch_hour:batch_minute` (UTC, default
  23:55) çalışır; job hatası loglanır, döngü ölmez.
- Lifespan'de start/stop; `GAMIFICATION_BACKEND_SCHEDULER_ENABLED=0` ile
  kapatılabilir (testler kapalı çalışır).

## Leaderboard

- `repositories/leaderboard.py` — ledger'dan canlı toplam; puan azalan,
  eşitlikte **username alfabetik** (deterministik tie-break), ardışık
  rank'ler; yalnızca puanı olan kullanıcılar.
- `GET /leaderboard` (auth) — `limit` parametresi; satırlar rozet listesi
  ve `is_bot` bayrağı taşır (S28 simülatör botları işaretlenecek).

## Admin uçları

- `GET /admin/runs` — koşu geçmişi (en yeni önce).
- `POST /admin/batch-run` — manuel tetikleme (`run_date` opsiyonel,
  default bugün UTC).

## Testler (17 yeni; toplam 292, coverage %93.90)

- batch: canlı değerlendirilmemiş event'lere gün sonunda ödül; iki koşu
  idempotent; canlı ödülden sonra batch 0 yeni ödül; run kaydı + JSON özet.
- **DB determinizmi**: iki bağımsız veritabanına aynı event seti ters
  sırayla → leaderboard/rozet/puan bire bir aynı
  (`test_same_events_produce_identical_results`).
- leaderboard: sıralama + alfabetik tie-break, puansızlar hariç, limit,
  bot bayrağı, auth 401.
- scheduler: `seconds_until_next_run` (aynı gün / yarına devir / tam anında
  yarın), döngünün job'ı çalıştırması ve durması, job hatasında hayatta
  kalması, app wiring (kapalı → None, açık → start/stop temiz).

## Kalite kapıları

ruff + mypy strict temiz. Canlı smoke: 60 dk izleme (canlı ödül) → admin
`POST /admin/batch-run` → `new_rewards=0` (çelişki yok) → leaderboard
"#1 veli 80p" → `GET /admin/runs` 1 kayıt success.
