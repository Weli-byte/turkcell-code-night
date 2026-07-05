# DGE — Deterministik Oyunlaştırma Platformu

Gerçek zamanlı çalışan bir video platformu + **deterministik** oyunlaştırma
motoru. Kullanıcılar kayıt olur, tarayıcıda gerçekten video izler; izlenen
her saniye ölçülür, challenge eşiği aşıldığı **anda** puan, rozet ve canlı
bildirim düşer. Tüm iş kararları (puan/rozet/sıralama) deterministik bir
kural motorunda alınır — `random` yok, `eval()` yok, LLM iş kararı veremez.

## Hızlı Başlangıç

### Docker ile (önerilen)

```bash
docker compose up --build
# SPA  → http://localhost:8080
# API  → http://localhost:8000 (Swagger: /docs)
# Admin: admin / change-me-admin-1 (docker-compose.yml'de değiştir)
```

### Manuel (geliştirme)

```bash
python -m pip install -e ".[dev]"
uvicorn gamification_backend.main:app        # API → :8000
cd frontend && npm install && npm run dev    # SPA → http://localhost:5173
```

Admin hesabı için API'yi şu env'lerle başlat:
`GAMIFICATION_BACKEND_ADMIN_USERNAME` + `GAMIFICATION_BACKEND_ADMIN_PASSWORD`.

## Neler Var?

- **Video platformu** — açık lisanslı katalog (Blender filmleri + kısa
  diziler); player gerçek izleme süresini ölçer (seek/pause sayılmaz),
  15 sn'de bir motora raporlar.
- **Canlı değerlendirme** — her event'te kural motoru çalışır: eşik
  aşıldığı anda ödül + SSE bildirimi. Günde tek ödül kuralı **veritabanı
  kısıtıyla** garantilidir.
- **Dashboard** — puanlar, rozetler (Bronze 500 / Silver 1500 / Gold 3000),
  challenge ilerleme çubukları, bildirim merkezi, append-only puan geçmişi.
- **Canlı leaderboard** — puan azalan + alfabetik tie-break; kendi satırın
  vurgulu; botlar 🤖 etiketli.
- **AI Asistan** — "Kaç puanım var?", "Neden bu sıradayım?" gibi sorulara
  deterministik motor kanıtıyla (evidence) cevap verir; LLM (Gemini/OpenAI
  anahtarı varsa) yalnızca dili cilalar, karar veremez.
- **Admin paneli** — challenge CRUD (koşullar güvenli parser'dan geçmeden
  yazılmaz), kullanıcılar, batch geçmişi, trafik simülatörü kontrolü.
- **Trafik simülatörü** — persona botları (binge'çi / gündelik / eleştirmen)
  gerçek ingestion yolundan event üretir; kotalar onlara da uygulanır;
  seed'li rastgelelik → aynı seed aynı trafik.
- **Gün sonu batch** — her gece 23:55 UTC'de tüm kullanıcıları
  deterministik sırayla yeniden değerlendirir; idempotent şema sayesinde
  canlı sonuçlarla asla çelişemez, yalnızca boşluk doldurur.

## Mimari

```text
React SPA (frontend/)                    FastAPI (src/gamification_backend/)
  katalog · player · dashboard    HTTP     api/ → services/ → repositories/
  leaderboard · admin · SSE      ─────►         │
                                                ▼ saf fonksiyon çağrıları
                                  Deterministik motor (src/gamification_engine/)
                                    rules (eval'siz parser) · reward_selector
                                    badges · leaderboard · ai/explanation
                                                │
                                                ▼
                                  SQLite: users, watch_events, challenges,
                                  reward_events (günde tek ödül UNIQUE),
                                  points_ledger (INSERT-ONLY, trigger korumalı),
                                  badges, notifications, runs
```

Motor (`gamification_engine`) bağımsız ve saf kalır: v1'in batch CLI'ı
(`gamification-engine run/explain`) aynen çalışır, golden-file regresyon
testleriyle korunur.

## Mühendislik Garantileri

- **Determinizm** — aynı event seti ⇒ aynı sonuç; testler bunu iki bağımsız
  veritabanında ters event sırasıyla doğrular.
- **Append-only ledger** — UPDATE/DELETE veritabanı trigger'ıyla engellenir;
  ham SQL bile puan geçmişini değiştiremez.
- **Anti-abuse** — event tarihi sunucu atar (UTC); kullanıcı yalnızca kendi
  adına event atabilir (token'dan); günlük izleme kotası video süresi × 3.
- **Güvenli kurallar** — koşullar `alan operatör tamsayı` sözdiziminde,
  whitelist'li parser ile; admin bile geçersiz/`eval` benzeri koşul giremez.

## Geliştirme

```bash
pytest              # 323 test + coverage kapısı (fail-under=85)
ruff check src tests && ruff format src tests
mypy                # strict
cd frontend && npm run build   # tsc strict + vite
```

CI her push'ta Python 3.11/3.12 üzerinde lint + format + type-check + test
çalıştırır.

## v1 Batch Motoru (korunuyor)

CSV → JSON çalışan orijinal batch hattı ve tanıtım sayfası:

```bash
gamification-engine run --activities data/input/user_activities.csv \
  --challenges data/input/challenges.csv --output-dir data/output \
  --run-date 2026-07-01
gamification-engine explain --user-id u001 --question "Kaç puanım var?" \
  --output-dir data/output --challenges data/input/challenges.csv
python server.py   # v1 landing page → http://localhost:8000
```

## Dokümantasyon

| Doküman | İçerik |
|---|---|
| [docs/v2_plan.md](docs/v2_plan.md) | Faz 2 mimarisi ve sprint kayıtları (20-30) |
| [docs/architecture.md](docs/architecture.md) | Motor mimarisi ve modül sorumlulukları |
| [docs/rule_engine.md](docs/rule_engine.md) | Koşul sözdizimi, tie-break, yeni challenge ekleme |
| [docs/ai_layer.md](docs/ai_layer.md) | Açıklama katmanı, LLM adapter, prompt contract |
| [docs/operations.md](docs/operations.md) | Batch akışı, hata kodları |
| [docs/testing_and_determinism.md](docs/testing_and_determinism.md) | Determinizm garantileri, golden file süreci |
| [docs/backlog.md](docs/backlog.md) | Teknik borç ve gelecek özellikler |
