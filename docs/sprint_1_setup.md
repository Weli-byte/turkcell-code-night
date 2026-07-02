# Sprint 1 Project Setup

## Goal

Sprint 1 establishes the professional Python project skeleton used by the
future implementation sprints.

## Added Structure

```text
pyproject.toml
README.md
src/
  gamification_engine/
    __init__.py
    cli/
      __init__.py
      main.py
    domain/
      __init__.py
      errors.py
tests/
  unit/
    cli/
      test_main.py
    domain/
      test_errors.py
  integration/
  fixtures/
```

## Tooling

The project configuration defines:

- Python package metadata.
- Editable package discovery from `src/`.
- Console script entry point: `gamification-engine`.
- Pytest configuration.
- Ruff lint configuration.
- Mypy strict type checking configuration.
- Development extras for test, lint, coverage, and type checking tools.

## Current CLI Scope

The Sprint 1 CLI is intentionally minimal. It exposes package metadata only:

```bash
gamification-engine --version
```

The real batch pipeline command will be added after domain models, ingestion,
and orchestration are introduced in later sprints.

## Verification

Executed successfully:

```bash
$env:PYTHONPATH = 'src'; python -m pytest
$env:PYTHONPATH = 'src'; python -m mypy
```

Ruff was configured in `pyproject.toml`, but the current local Python
environment did not have the `ruff` package installed at verification time.

## Definition of Done

Sprint 1 is complete when:

- The `src/` package skeleton exists.
- The CLI entry point exists.
- The domain exception hierarchy exists.
- Unit, integration, and fixture test folders exist.
- Pytest runs successfully.
- Mypy runs successfully.
- Ruff configuration is present.
