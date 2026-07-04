# CLAUDE.md

Deterministic gamification engine (Python 3.11+, stdlib-only runtime deps).
Processes daily video-platform activity CSVs → user states, challenge rewards,
append-only points ledger, badges, leaderboard, notifications, JSON exports,
and a template-based Turkish explanation layer (optional LLM rephrasing).

## Commands

```bash
python -m pip install -e ".[dev]"   # setup
pytest                              # tests + coverage gate (fail-under=85)
ruff check src tests                # lint (must be clean)
ruff format src tests               # format (CI checks with --check)
mypy                                # strict mode, must be clean
gamification-engine run --activities <csv> --challenges <csv> --output-dir <dir> --run-date YYYY-MM-DD
gamification-engine explain --user-id <id> --question "<tr question>" --output-dir <dir> --challenges <csv>
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
