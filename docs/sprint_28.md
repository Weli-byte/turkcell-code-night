# Sprint 28 — Canlı Trafik Simülatörü (Faz 2)

Persona botları platformu gerçek kullanıcılar gibi kullanır; leaderboard
gözünün önünde akar.

## Tasarım (`services/simulator.py`)

- **Personalar**: `binge` (her tur izler, 180-300 sn, %50 bölüm bitirir),
  `gundelik` (%60 izler, 30-120 sn), `elestirmen` (%40 izler, %60 puanlar).
  Botlar personalar arasında sırayla dağıtılır (`sim-binge-1`,
  `sim-gundelik-2`, ...), `is_bot=True`, parolasız (login edilemez).
- **Gerçek ingestion yolu**: botlar `EventRepository` + `evaluate_user_live`
  üzerinden akar — günlük kotalar, dedupe kuralları ve canlı ödüller
  onlara da birebir uygulanır. Bot hile yapamaz.
- **Seed'li rastgelelik**: motor iş kararlarında rastgelelik yasak; trafik
  *üretici* doğası gereği rastgele, bu yüzden izole `random.Random(seed)`
  kullanır — aynı seed aynı trafiği üretir (testli). Motor çıktıları verilen
  event seti için deterministik kalır.
- Tick döngüsü asyncio task'i; tick hatası loglanır, döngü ölmez;
  lifespan kapanışında otomatik durdurulur.

## API

- `GET /admin/simulator` — running, bot_count, tick_seconds,
  ticks_completed, events_recorded.
- `POST /admin/simulator/start` — `{bot_count: 1-50, tick_seconds: 0.5-60}`;
  botları oluşturur/yeniden kullanır; zaten çalışıyorsa 409.
- `POST /admin/simulator/stop` — idempotent.

## Frontend (Admin → Simülatör sekmesi)

Bot sayısı + tur aralığı girişleri, ▶ Başlat / ■ Durdur, 3 sn'de bir
tazelenen canlı sayaçlar (tur/event). Leaderboard sayfası zaten 15 sn'de
bir yenilendiğinden botların yükselişi canlı izlenir (🤖 etiketli).

## Testler (8 yeni; toplam 315, coverage %94.14)

Bot oluşturma (bayraklar + parolasız + idempotent + persona dağılımı);
10 tick → event'ler kaydedildi + bot leaderboard'a girdi; **aynı seed aynı
trafik** (iki bağımsız DB'de event sayısı eşit); döngü başlat/durdur +
çifte start reddi; API start/stop/409/422 (sınır aşımı) + admin-only.

## Kalite kapıları

ruff + mypy strict + `npm run build` temiz. Canlı smoke: 6 bot, 1 sn tick →
8 saniyede 8 tur / 39 event; `sim-binge-1` CH-002 kazanıp 150p ile
leaderboard #1; stop temiz.
