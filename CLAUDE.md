# CLAUDE.md

Deterministic gamification engine (Python 3.11+; engine core stdlib-only).
Processes daily video-platform activity CSVs → user states, challenge rewards,
append-only points ledger, badges, leaderboard, notifications, JSON exports,
and a template-based Turkish explanation layer (optional LLM rephrasing).

**Faz 2 in progress** (`docs/v2_plan.md`, sprints 20-30, status table at
bottom): turning the batch demo into a live platform — FastAPI+SQLite backend
(`src/gamification_backend/`), React SPA (planned `frontend/`), live event
evaluation + nightly batch, JWT auth, SSE. Engine core stays the pure
deterministic library; backend deps live in the `backend` extra.

## Commands

```bash
python -m pip install -e ".[dev]"   # setup
pytest                              # tests + coverage gate (fail-under=85)
ruff check src tests                # lint (must be clean)
ruff format src tests               # format (CI checks with --check)
mypy                                # strict mode, must be clean
gamification-engine run --activities <csv> --challenges <csv> --output-dir <dir> --run-date YYYY-MM-DD
gamification-engine explain --user-id <id> --question "<tr question>" --output-dir <dir> --challenges <csv>
uvicorn gamification_backend.main:app --reload   # Faz 2 API (http://127.0.0.1:8000, Swagger at /docs)
```

CI: `.github/workflows/ci.yml` runs ruff check + format check + mypy + pytest on Python 3.11/3.12.

## Layout (src/gamification_engine/)

- `domain/` — models (frozen dataclasses), enums, errors. No business logic.
- `ingestion/` — CSV loaders + strict validators (csv_loader, validators, schemas).
- `state/` — DailyUserState builder, rolling 7d metrics, watch streaks.
- `rules/` — safe condition parser (NO eval), evaluator, challenge_repository, reward_selector (priority, tie-break: lower challenge_id).
- `ledger/` — append-only points ledger + JSON repository, duplicate guard.
- `badges/` — threshold-based (Bronze 500 / Silver 1500 / Gold 3000 in config/badge_config.py), duplicate guard, backfills missed tiers.
- `leaderboard/` — rank by points desc, tie-break alphabetical user_id, sequential ranks.
- `notifications/` — deterministic notification records + repository.
- `export/json_exporter.py` — all JSON outputs + RunSummary (indent=2, ensure_ascii=False, sorted deterministically).
- `orchestration/` — pipeline.py (no business logic) + run_context.py.
- `cli/main.py` — argparse subcommands `run` and `explain`.
- `ai/` — explanation_engine (keyword intent → template answers + evidence), templates, llm_adapter (LLMAdapter ABC, NoOp/Gemini/OpenAI adapters + factory; any failure → deterministic fallback), llm_client (pure HTTPS transport + prompt contract). Env vars read ONLY in config/llm_config.py: GEMINI_API_KEY (precedence), OPENAI_API_KEY, GAMIFICATION_LLM_ENABLED=0 kill switch. See docs/ai_layer.md.

## Layout (src/gamification_backend/) — Faz 2 service layer

- `config.py` — BackendSettings (pydantic-settings). Backend env vars read ONLY here, prefix `GAMIFICATION_BACKEND_` (DATABASE_URL, CHALLENGES_CSV, SEED_ON_STARTUP).
- `db/models.py` — SQLAlchemy 2.0 typed ORM: users, challenges, series, videos, watch_events, points_ledger, badges, notifications, runs. `db/base.py` — engine setup (SQLite FK pragma ON, StaticPool for in-memory) + `init_database` installs SQLite triggers making points_ledger append-only at DB level (UPDATE/DELETE → RAISE(ABORT), surfaces as IntegrityError). Unique guards: (user_id, source_ref) on ledger, (user_id, badge_type) on badges.
- `repositories/` — ledger (AppendOnlyLedgerRepository: insert-only by design, no update/delete methods), challenges (CSV seed via engine's strict loader; existing rows never overwritten).
- `security.py` — bcrypt hash/verify + HS256 JWT create/decode (TokenError, injectable `now`). No FastAPI imports.
- `api/` — routers (health, auth: register/login, me, admin: ping) + `deps.py` SessionDep/CurrentUserDep/AdminDep (use `Annotated[..., Depends]`, never `= Depends()` — ruff B008; missing/bad token → 401, non-admin → 403). `main.py` — `create_app()` factory, lifespan does schema+seed+admin bootstrap (ADMIN_USERNAME/_PASSWORD env); module-level `app` for uvicorn.
- Tests in `tests/backend/` (in-memory SQLite fixtures in conftest; UserFactory protocol fixture `make_user`).

Root extras: `index.html` (single-file GSAP/Lenis landing page) + `server.py` (stdlib dev server: serves index.html and bridges UI↔engine via GET /api/summary|leaderboard|badges|explain; reads data/output, never mutates). Run with `python server.py` → http://localhost:8000. Both outside ruff/mypy scope (src+tests only).

Tests mirror src under `tests/unit/` + `tests/integration/`; fixtures in `tests/fixtures/`. Golden regression scenario: `tests/fixtures/golden_inputs/` (2-day run) vs `golden_outputs/day1|day2/` — byte-compared in `tests/integration/test_golden_outputs.py`; regen process in docs/testing_and_determinism.md (update goldens only for intentional rule changes, same commit).

## Hard rules

- Determinism: same input + run_date ⇒ byte-identical output. No random, no system clock (use run_date), explicit tie-breaks everywhere, integers over floats.
- Ledger is append-only: never update/delete entries. Re-runs must be idempotent.
- Never use eval() for conditions; whitelist fields + operators (>=, >, <=, <, ==, !=).
- LLM never makes business decisions (points/badges/ranks); it only rephrases the deterministic answer.
- All code: type hints, docstrings, mypy strict clean, ruff clean, tests required.
- Line length 88 (ruff). Dates ISO YYYY-MM-DD.

## Ignore

- `turkcell-code-night-main/` at repo root = old prototype, gitignored, do not read or modify.
- Never read `__pycache__/`, `.mypy_cache/`, `.ruff_cache/`.
- `data/input/` = committed sample CSVs (6 users, 6 challenges); `data/output/` = committed sample outputs of a 3-day run (2026-06-29..07-01). Regenerate by re-running the CLI for those dates in order.
- Docs in `docs/` (sprint_*.md = per-sprint records; rule_engine/ai_layer/operations/testing_and_determinism/agent_guide/backlog = living design docs).

## Known quirks

- On Windows sandboxed runs, pytest tmp dir may hit WinError 5; pass
  `--basetemp=<writable dir>` and `-p no:cacheprovider` if that happens.
- Repo sprint numbering diverges from the original plan after Sprint 12
  (repo S13=CLI explain, S14=LLM layer). Gap-closure sprints start at 16
  (S16=quality gate+CI, S17=LLM adapter refactor, S18=determinism/golden
  tests, S19=sample data+docs — all done; gap-closure plan complete).
