# Sprint 30 — Paketleme, E2E ve Dokümantasyon (Faz 2 Kapanışı)

Faz 2'nin son sprinti: platform tek komutla ayağa kalkar, tam kullanıcı
yolculuğu tek testte doğrulanır, README gerçek durumu anlatır.

## Docker paketleme

- `deploy/Dockerfile.backend` — python:3.11-slim, `.[backend]` kurulumu,
  uvicorn; SQLite `/data` volume'ünde kalıcı.
- `deploy/Dockerfile.frontend` — çok aşamalı: node:22 build → nginx:1.27.
- `deploy/nginx.conf` — SPA fallback + API reverse proxy; `/sse/` için
  `proxy_buffering off` (bildirimler anında akar).
- `docker-compose.yml` — `docker compose up --build` → SPA :8080, API
  :8000; admin bootstrap + JWT secret env'leri örnekli (değiştir uyarılı).
- **Not**: bu makinede Docker kurulu olmadığından imajlar build edilerek
  test edilemedi; compose/nginx/Dockerfile'lar elle doğrulandı ve CI build
  adımı backlog'a eklendi.

## Bug fix

Vite dev proxy'sinde `/explain` yolu eksikti (S29'da eklenen endpoint) —
dev ortamında AI Asistan 404 alırdı. `vite.config.ts` + nginx.conf her API
yolunu içerir durumda.

## Uçtan uca senaryo testi (`test_e2e_scenario.py`)

Tek testte tam yolculuk: iki kullanıcı kaydı → katalog → veli 300 dk izler
(CH-004 800p + **anında BRONZE**) → ayse 60 dk (CH-001 80p) → complete
dedupe + rating kuralları → leaderboard sırası ve rozetler → kalıcı
bildirimler → `/explain` canlı veriden 800 puanı kanıtıyla açıklar →
admin batch **hiçbir şeyi değiştirmeden** mühürler → append-only geçmiş
tutarlı.

## Dokümantasyon

- README v2: Docker + manuel hızlı başlangıç, özellik listesi, mimari
  diyagram, mühendislik garantileri; v1 batch CLI "korunuyor" bölümüne
  taşındı.
- `docs/backlog.md`: Faz 2'nin teslim ettikleri işaretlendi; yeni teknik
  borç tablosu (Redis pub/sub, PostgreSQL, frontend testleri, CI'da Docker
  build, canlı ödül zamanlaması notu).

## Kalite kapıları

ruff + mypy strict + `npm run build` temiz; **323 test passed, coverage
%94.50**.

## Faz 2 Özeti (Sprint 20-30, tamamı tamamlandı)

| Sprint | Teslimat |
|---|---|
| 20 | FastAPI + SQLAlchemy iskeleti, append-only trigger'lı şema |
| 21 | JWT auth + admin bootstrap |
| 22 | Video kataloğu + anti-abuse'lu event ingestion |
| 23 | Canlı değerlendirme + SSE bildirimleri |
| 24 | Gün sonu batch + scheduler + canlı leaderboard |
| 25 | React SPA + gerçek izleme ölçümlü player |
| 26 | Dashboard + bildirim merkezi + leaderboard sayfası |
| 27 | Admin paneli (challenge CRUD, güvenli koşul editörü) |
| 28 | Persona botlu canlı trafik simülatörü |
| 29 | AI açıklama entegrasyonu (canlı veriden, kanıtlı) |
| 30 | Docker, e2e senaryo, README v2 |
