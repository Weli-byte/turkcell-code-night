# Faz 2 Planı — Gerçek Çalışan Sistem (v2)

Amaç: Batch CSV → JSON üreten mevcut deterministik motoru, **gerçek
kullanıcıların gerçekten video izleyip anlık ödül kazandığı** canlı bir
platforma dönüştürmek. Motorun deterministik çekirdeği (rules, ledger
mantığı, badges, leaderboard, ai) **iş mantığı kütüphanesi olarak aynen
korunur**; etrafına servis katmanı örülür.

## Mimari kararlar (kullanıcı onaylı, 2026-07-04)

| Karar | Seçim |
|---|---|
| Veri kaynağı | Mini video platformu (gerçek player event'leri) **+** canlı trafik simülatörü (bot kullanıcılar) |
| Backend | FastAPI + SQLAlchemy 2.0 + SQLite (PostgreSQL'e geçişe hazır) |
| Frontend | React 18 + Vite SPA |
| İşleme modu | Canlı değerlendirme (event anında) + gün sonu batch (tutarlılık mührü) |
| Bildirim | SSE (Server-Sent Events) |
| Auth | JWT (kayıt/giriş), bcrypt parola hash |
| Zamanlayıcı | APScheduler (gün sonu batch) |

## Hedef mimari

```text
React SPA (frontend/)
  ├─ Video platformu: katalog + player (heartbeat/complete/rating event'leri)
  ├─ Dashboard: puanlarım, rozetlerim, challenge ilerlemesi, bildirimler (SSE)
  ├─ Leaderboard (canlı)
  └─ Admin: challenge CRUD, kullanıcılar, run geçmişi, simülatör kontrolü
        │ REST + SSE
        ▼
FastAPI (backend/app/)
  ├─ api/: auth, catalog, events, me, leaderboard, explain, admin, sse
  ├─ services/: live_evaluator (event → state → rules → ledger → badge → notif)
  │             daily_batch (gün sonu, deterministik mühür)
  │             simulator (bot trafik üreticisi)
  ├─ db/: SQLAlchemy modelleri + repository'ler (ledger tablosu APPEND-ONLY)
  └─ core motor: src/gamification_engine (değişmeden, saf fonksiyonlar)
        │
        ▼
SQLite (gamification.db)
  users, videos, series, watch_events, daily_states, rewards,
  points_ledger (insert-only), badges, notifications, runs, challenges
```

## Korunacak ilkeler

- Ledger tablosu insert-only; UPDATE/DELETE yok (uygulama katmanı + test garantisi).
- `eval()` yok; koşullar mevcut güvenli parser'dan geçer.
- Gün sonu batch deterministik: aynı event seti + aynı gün ⇒ aynı sonuç.
- LLM yalnızca açıklamayı yeniden ifade eder; iş kararı vermez.
- Canlı değerlendirme idempotent: aynı gün aynı challenge ikinci kez ödül veremez
  (duplicate guard DB unique constraint ile).

## Sprint planı

### Sprint 20 — Backend iskeleti + veritabanı
- `backend/` paketi: FastAPI app factory, ayar yönetimi (pydantic-settings).
- SQLAlchemy 2.0 modelleri: users, challenges, videos/series, watch_events,
  points_ledger (insert-only + unique guard), badges, notifications, runs.
- Ledger repository: yalnızca insert; update/delete API'si hiç yazılmaz;
  unique constraint (user_id, source_ref) idempotency.
- Challenge seed: mevcut 6 challenge DB'ye taşınır.
- `GET /health`; pytest + httpx test altyapısı.
- Çıktı: `uvicorn backend.app.main:app` ayağa kalkar, testler yeşil.

### Sprint 21 — Auth ve kullanıcı yönetimi
- `POST /auth/register`, `POST /auth/login` (JWT), `GET /me`.
- bcrypt parola hash, token doğrulama dependency'si, admin rolü.
- Testler: kayıt/giriş/yetki senaryoları.

### Sprint 22 — İçerik kataloğu + event ingestion
- Video/dizi kataloğu: açık lisanslı örnek videolar (Blender filmleri vb.)
  seed script ile; tür (genre) etiketleri.
- `GET /catalog`, `GET /catalog/{id}`.
- `POST /events/heartbeat` (izlenen saniyeler), `POST /events/complete`
  (bölüm bitti), `POST /events/rating`, `POST /events/watch-party`.
- Event doğrulama (negatif süre, gelecek tarih, aşırı heartbeat reddi).

### Sprint 23 — Canlı değerlendirme motoru
- Event geldiğinde: kullanıcının bugünkü `DailyUserState`'i DB'den yeniden
  hesaplanır → mevcut rule engine ile challenge'lar değerlendirilir →
  reward_selector → ledger insert (idempotent) → badge kontrolü → notification.
- Mevcut `src/gamification_engine` fonksiyonları saf çekirdek olarak çağrılır.
- `GET /me/points`, `GET /me/badges`, `GET /me/challenges` (ilerleme yüzdesiyle).
- SSE endpoint'i `GET /sse/notifications` (ödül/rozet anında düşer).

### Sprint 24 — Gün sonu batch + scheduler + leaderboard
- APScheduler gece koşusu: günü mühürler, leaderboard snapshot üretir,
  run kaydı yazar. Canlı değerlendirmeyle çakışmayan idempotent tasarım.
- `GET /leaderboard` (canlı toplamlardan), run geçmişi endpoint'i.
- DB üzerinde determinizm testleri (aynı event seti ⇒ aynı gün sonu sonucu).

### Sprint 25 — React temeli + video platformu
- `frontend/` Vite + React + React Router + TanStack Query kurulumu;
  mevcut landing estetiği (koyu tema, yeşil aksan) taşınır.
- Auth ekranları (kayıt/giriş), korumalı rotalar.
- Katalog sayfası + video player sayfası: HTML5 player, izleme süresi
  ölçümü, periyodik heartbeat, bölüm tamamlama, yıldızla puanlama.

### Sprint 26 — Kullanıcı dashboard'u
- "Profilim": toplam puan, rozetler, puan geçmişi grafiği.
- Aktif challenge kartları + canlı ilerleme çubukları.
- Bildirim merkezi: SSE ile anlık toast ("🏆 Bronze kazandın!").
- Canlı leaderboard sayfası (kendi satırın vurgulu).

### Sprint 27 — Admin paneli
- Challenge CRUD (koşul editörü mevcut parser ile ön-doğrulamalı).
- Kullanıcı listesi, run geçmişi, manuel batch tetikleme.
- Simülatör kontrol ekranının iskeleti.

### Sprint 28 — Canlı trafik simülatörü
- Bot kullanıcılar (farklı persona: binge'çi, gündelik izleyici, puanlayıcı).
- Ayarlanabilir yoğunluk; admin panelden başlat/durdur.
- Botlar gerçek API üzerinden event atar → leaderboard sende canlı akar.

### Sprint 29 — AI açıklama entegrasyonu
- `POST /explain`: DB'den beslenen mevcut explanation engine + LLM adapter.
- Dashboard'da "Neden bu puandayım?" sohbet kutusu.

### Sprint 30 — Paketleme, e2e, dokümantasyon
- Dockerfile'lar + docker-compose (backend + frontend + seed).
- Uçtan uca senaryo testi: kayıt → izle → ödül → rozet → leaderboard.
- README v2, mimari dokümanı güncelleme, eski `server.py`/`index.html`
  landing'in "tanıtım sayfası" olarak konumlandırılması.

## Sprint durumu

| Sprint | Durum |
|---|---|
| 20 | **tamamlandı** (docs/sprint_20.md) |
| 21 | **tamamlandı** (docs/sprint_21.md) |
| 22 | **tamamlandı** (docs/sprint_22.md) |
| 23 | bekliyor |
| 24 | bekliyor |
| 25 | bekliyor |
| 26 | bekliyor |
| 27 | bekliyor |
| 28 | bekliyor |
| 29 | bekliyor |
| 30 | bekliyor |
