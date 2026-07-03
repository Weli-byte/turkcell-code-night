# Sprint 13 CLI Explain Soru-Cevap Desteği

## Sprint Goal

Expose the deterministic AI explanation layer via the CLI using a new `explain`
subcommand, allowing users to query their gamification status.

## Deliverables

- Command-line `explain` subcommand.
- Private JSON data loaders inside `cli/main.py` for states, leaderboard, and reward event outputs.
- Formatting options: plain text and JSON.
- CLI unit tests.
- Sprint documentation.

## Created/Modified Files

### [MODIFY] `src/gamification_engine/cli/main.py`

Introduces the `explain` command:
```bash
gamification-engine explain \
  --user-id <user-id> \
  --question <Turkish question> \
  --output-dir <output-directory-with-json-files> \
  --challenges <challenges-csv-file> \
  [--format {text,json}]
```
Implements private JSON data loaders:
- `_load_states_json()`
- `_load_leaderboard_json()`
- `_load_rewards_json()`

Loads historical data, maps it to the domain models, calls `explain_user_query`,
and prints either plain text (`response.answer`) or fully detailed JSON outputs
to stdout.

### [MODIFY] `tests/unit/cli/test_main.py`

CLI unit tests for:
- Text formatting success path.
- JSON formatting success path (verifying nested evidence and values).
- Clean exit code 1 handling for unexpected loader/pipeline errors.

### [NEW] `docs/sprint_13_cli_explain.md`

Documentation of goals, command specifications, and deliverables.

## Definition of Done

- [x] CLI `explain` subcommand parses all necessary parameters.
- [x] CLI loads and maps states, ledger entries, badges, leaderboard, rewards, and challenges.
- [x] Output format choice (plain text and JSON) is supported.
- [x] CLI explain unit tests cover success and failure paths.
- [x] Code conforms to strict type checks and Ruff lint rules.
