# Sprint 20 — Backend İskeleti + Veritabanı (Faz 2)

Faz 2'nin ilk sprinti: deterministik motorun etrafına gerçek bir servis
katmanı örülmeye başlandı. Plan: `docs/v2_plan.md`.

## Yapılanlar

### Yeni paket: `src/gamification_backend/`

| Modül | Sorumluluk |
|---|---|
| `config.py` | `BackendSettings` (pydantic-settings). Backend env değişkenleri **yalnızca burada** okunur; `GAMIFICATION_BACKEND_` öneki motor LLM değişkenleriyle çakışmayı önler. |
| `db/models.py` | SQLAlchemy 2.0 typed ORM: `users`, `challenges`, `series`, `videos`, `watch_events`, `points_ledger`, `badges`, `notifications`, `runs`. |
| `db/base.py` | Engine kurulumu (SQLite pragma `foreign_keys=ON`, in-memory için `StaticPool`), `init_database` = şema + append-only trigger'lar. |
| `repositories/ledger.py` | `AppendOnlyLedgerRepository` — yalnızca insert; update/delete metodu tasarımda yok. |
| `repositories/challenges.py` | CSV'den challenge seed (motorun strict loader'ı ile) + deterministik sıralı aktif liste. |
| `api/health.py`, `api/deps.py` | `GET /health` + session dependency (`Annotated[..., Depends]`). |
| `main.py` | `create_app()` fabrikası; lifespan'de şema + seed. `uvicorn gamification_backend.main:app`. |

### Append-only garanti artık veritabanı seviyesinde

- SQLite trigger'ları `points_ledger` üzerinde her `UPDATE`/`DELETE`'i
  `RAISE(ABORT)` ile durdurur — ham SQL bile geçemez (testli).
- `UNIQUE(user_id, source_ref)` → aynı ödülün tekrar teslimi idempotent.
- `CHECK(points_delta > 0)`, `UNIQUE(user_id, badge_type)`,
  pozitif puan/priority check'leri.

### Seed davranışı

Başlangıçta `data/input/challenges.csv` motorun loader'ından geçirilerek
DB'ye eklenir; **var olan satırlara dokunulmaz** (admin düzenlemeleri seed'i
ezer, tersi değil). Tekrarlı açılış güvenlidir.

## Testler

`tests/backend/` — 25 yeni test: ledger append/idempotency/pozitiflik,
trigger'ların ham UPDATE/DELETE'i engellemesi, şema round-trip, unique ve
FK kısıtları, seed idempotency + sıralama, app factory + `/health` + seed
kapatma, settings env override.

## Kalite kapıları

- ruff check + format: temiz
- mypy strict (56 dosya): temiz
- pytest: 218 passed, coverage %94.42 (kapı %85)
- Smoke test: `uvicorn gamification_backend.main:app` → `/health` 200,
  `/docs` (Swagger) 200

## Notlar

- `pyproject.toml`: yeni `backend` extra'sı (fastapi, uvicorn, sqlalchemy,
  pydantic-settings); `dev` bunu içerir. Coverage ve mypy kapsamına
  `gamification_backend` eklendi. Motor çekirdeği bağımlılıksız kaldı.
- `*.db` gitignore'a eklendi.
- SQLite `RAISE(ABORT)` Python'da `IntegrityError` olarak yüzeye çıkar;
  trigger testleri `DatabaseError` bekler.
