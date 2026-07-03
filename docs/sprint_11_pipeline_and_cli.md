# Sprint 11 Pipeline Orchestration and CLI

## Sprint Goal

Create an end-to-end batch pipeline orchestrator that coordinates all stages
of the gamification run, and expose it via the CLI using a new `run` subcommand.

## Deliverables

- `RunContext` parameter configuration model.
- Pipeline orchestration implementation.
- Command-line `run` subcommand.
- Unit and integration tests covering the pipeline and CLI.
- Sprint documentation.

## Created/Modified Files

### [NEW] `src/gamification_engine/orchestration/run_context.py`

Holds execution parameters (`activities_csv_path`, `challenges_csv_path`,
`output_dir`, `run_date`) and automatically resolves default paths for
historical data files (`existing_ledger_path`, `existing_badges_path`,
`existing_notifications_path`).

### [NEW] `src/gamification_engine/orchestration/pipeline.py`

Sequential pipeline orchestrator that coordinates:
1. Loading raw inputs (activities, challenges)
2. Loading historical records (ledger, badges, notifications)
3. Building daily user states for `run_date`
4. Evaluating rules and selecting reward candidates
5. Appending point awards to the ledger (with duplicate prevention)
6. Calculating point totals
7. Assigning badges
8. Creating deterministic leaderboard
9. Generating notifications
10. Producing the final run summary
11. Exporting all outputs to JSON

### [MODIFY] `src/gamification_engine/cli/main.py`

Introduces the `run` command:
```bash
gamification-engine run \
  --activities <path-to-csv> \
  --challenges <path-to-csv> \
  --output-dir <path-to-output-dir> \
  --run-date <YYYY-MM-DD>
```
Supports optional flags `--existing-ledger`, `--existing-badges`,
`--existing-notifications`.

### [NEW] `tests/unit/orchestration/test_pipeline.py`

Tests for `RunContext` path resolution, successful orchestrator runs,
and pipeline error propagation/wrapping.

### [MODIFY] `tests/unit/cli/test_main.py`

CLI parser verification tests, mock execution runs, date formatting error tests,
and pipeline failure checks.

### [NEW] `tests/integration/test_pipeline.py`

Integration tests utilizing CSV fixtures to verify:
- End-to-end correctness of the pipeline and output formats.
- Determinisitic tie-breaks and priority suppression (e.g. C-02 suppressing C-01).
- Idempotency over multiple consecutive runs.
- CLI end-to-end execution.

## Design Decisions

- **Error Handling Strategy**: Any failure in the pipeline terminates the batch execution immediately (fail-fast), propagating the error with a wrapped `GamificationEngineError`.
- **Run Summary Counts**: Aggregates processed counts for users, rewards, ledger entries, badges, notifications, and leaderboard size.
- **Convenient Defaults**: Command-line historical parameters are optional and default to files located in `output-dir` (e.g., `output-dir/ledger.json`).

## Definition of Done

- [x] Command-line runner (`run` subcommand) parses and validates inputs.
- [x] Execution context (`RunContext`) properly maps configurations and resolves paths.
- [x] Pipeline sequentially processes all gamification logic.
- [x] Resulting artifacts are correctly written to the output directory via `export_all`.
- [x] Unit and integration tests cover success, failure, and idempotency paths.
- [x] Type hints and docstrings are provided on all public functions/models.
- [x] Code passes Mypy and Ruff validation checks.
