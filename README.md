# Deterministic Gamification Engine

Professional Python project for a modular, deterministic gamification engine
designed for digital video platforms.

## Current Status

The repository is being migrated sprint by sprint toward a clean `src/`
package architecture. The original prototype remains under:

```text
turkcell-code-night-main/
```

The new production package skeleton starts under:

```text
src/gamification_engine/
```

## Development Setup

Recommended Python version:

```text
Python 3.11+
```

Install the project in editable mode with development tools:

```bash
python -m pip install -e ".[dev]"
```

Run tests:

```bash
pytest
```

Run lint:

```bash
ruff check .
```

Run type checks:

```bash
mypy
```

Run the new CLI placeholder:

```bash
gamification-engine --version
```

## Sprint Documentation

Sprint 0 planning documents are available under:

```text
docs/
```

Key documents:

- `docs/product_plan.md`
- `docs/architecture.md`
- `docs/data_flow.md`
- `docs/deterministic_rules.md`

## Engineering Principles

- Deterministic outputs.
- Append-only points ledger.
- Explicit business rules.
- No LLM-based business decisions.
- Modular components with single responsibility.
- Type hints, docstrings, tests, linting, and static analysis.

