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
- `ai/` — explanation_engine (keyword intent → template answers + evidence), templates, llm_client (optional; GEMINI_API_KEY / OPENAI_API_KEY env vars; returns None on any failure → deterministic fallback).

Tests mirror src under `tests/unit/` + `tests/integration/`; fixtures in `tests/fixtures/`.

## Hard rules

- Determinism: same input + run_date ⇒ byte-identical output. No random, no system clock (use run_date), explicit tie-breaks everywhere, integers over floats.
- Ledger is append-only: never update/delete entries. Re-runs must be idempotent.
- Never use eval() for conditions; whitelist fields + operators (>=, >, <=, <, ==, !=).
- LLM never makes business decisions (points/badges/ranks); it only rephrases the deterministic answer.
- All code: type hints, docstrings, mypy strict clean, ruff clean, tests required.
- Line length 88 (ruff). Dates ISO YYYY-MM-DD.

## Ignore

- `turkcell-code-night-main/` at repo root = old prototype, gitignored, do not read or modify.
- Never read `__pycache__/`, `.mypy_cache/`, `.ruff_cache/`, `output/` artifacts.
- Docs in `docs/` (sprint_*.md = per-sprint records; architecture/data_contracts/deterministic_rules = design).

## Known quirks

- On Windows sandboxed runs, pytest tmp dir may hit WinError 5; pass
  `--basetemp=<writable dir>` and `-p no:cacheprovider` if that happens.
- Repo sprint numbering diverges from the original plan after Sprint 12
  (repo S13=CLI explain, S14=LLM layer). Gap-closure sprints start at 16
  (S16=quality gate+CI done; S17=LLM adapter refactor; S18=determinism/golden
  tests; S19=sample data+docs).
