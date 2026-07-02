# Sprint 0 Architecture Plan

## Architectural Goal

The engine should be a modular, deterministic, testable Python application that
processes batch user activity data and produces gamification outcomes.

The architecture should support incremental migration from the current
repository layout to a more explicit domain-driven package structure without
breaking the existing working pipeline unnecessarily.

## Current Repository Architecture

```text
turkcell-code-night-main/
  main.py
  chat.py
  ai_layer/
  data/
  logic_engine/
  models/
  output/
  state_engine/
  utils/
```

### Current Responsibilities

`main.py`

Full pipeline orchestration. It loads inputs, invokes engines, validates
integrity, writes temporary outputs, and promotes them to the final output
directory.

`state_engine/`

Builds user engagement state from activity events.

`logic_engine/rule_engine.py`

Evaluates challenge conditions, resolves priority conflicts, and generates
challenge awards.

`logic_engine/badge_engine.py`

Assigns badges based on total points.

`logic_engine/notification_engine.py`

Creates notification records from awards and badges.

`logic_engine/leaderboard_engine.py`

Builds deterministic leaderboard rankings.

`models/ledger.py`

Handles points ledger updates and point totals.

`ai_layer/`

Provides deterministic and fallback explanation behavior.

`utils/`

Provides loading, exporting, schema validation, and integrity validation.

## Target Architecture

The long-term target is a package-oriented architecture:

```text
src/
  gamification_engine/
    config/
    domain/
    ingestion/
    state/
    rules/
    ledger/
    badges/
    leaderboard/
    notifications/
    ai/
    export/
    orchestration/
    cli/
```

The current project does not need to jump to this layout immediately. A
controlled migration can happen after the product behavior is locked with
tests.

## Proposed Component Boundaries

### Ingestion

Responsible for:

- Loading CSV files.
- Validating headers.
- Parsing field types.
- Normalizing input order.
- Reporting validation errors.

Not responsible for:

- State calculation.
- Challenge evaluation.
- Reward or badge decisions.

### State Engine

Responsible for:

- Grouping activities by user and date.
- Calculating daily metrics.
- Calculating rolling metrics.
- Calculating watch streak.
- Producing one state object or row per user for a run date.

Not responsible for:

- Challenge priority.
- Points ledger updates.
- Badge assignment.

### Rule Engine

Responsible for:

- Parsing challenge conditions.
- Validating allowed state fields and operators.
- Evaluating active challenges against user state.
- Returning triggered challenges.

Not responsible for:

- Writing ledger entries.
- Generating notifications.
- Calling LLMs.

### Reward Selector

Responsible for:

- Applying priority rules to triggered challenges.
- Selecting one reward candidate per user.
- Returning suppressed challenge metadata for explanation.

Priority policy should be explicit and tested.

### Points Ledger

Responsible for:

- Appending point transactions.
- Preventing duplicate reward transactions.
- Calculating total points from ledger history.
- Preserving audit trail.

Not responsible for:

- Deciding whether a challenge was won.
- Assigning badges directly.

### Badge Engine

Responsible for:

- Reading total user points.
- Comparing totals with badge thresholds.
- Producing new badge awards.
- Preventing duplicate badge awards.

### Leaderboard Engine

Responsible for:

- Sorting users by total points descending.
- Applying deterministic tie-break by `user_id` ascending.
- Assigning consecutive ranks.

### Notification Engine

Responsible for:

- Creating notification records from reward and badge events.
- Applying deterministic notification IDs or duplicate keys.
- Producing notification payloads.

Not responsible for:

- Sending push notifications or messages.

### AI Explanation Layer

Responsible for:

- Answering user questions from existing deterministic state.
- Explaining points, badges, leaderboard rank, and reward decisions.
- Returning evidence with answers.

Not responsible for:

- Creating rewards.
- Modifying ledger.
- Changing leaderboard.
- Making rule decisions.

## High-Level Pipeline

```text
CSV Inputs
  -> Ingestion and Validation
  -> User State Engine
  -> Rule Engine
  -> Reward Selector
  -> Points Ledger
  -> Badge Engine
  -> Leaderboard Engine
  -> Notification Engine
  -> Integrity Validation
  -> JSON/CSV Export
  -> AI Explanation Layer reads outputs as context
```

## Dependency Direction

Dependencies should flow inward toward stable domain models:

```text
CLI / Main
  depends on Orchestration
Orchestration
  depends on Engines and Repositories
Engines
  depend on Domain Models and Config
Domain Models
  depend on standard library or validation library only
```

Business logic modules should not depend on CLI, filesystem paths, or output
formatting.

## Error Handling Strategy

The application should distinguish:

- Input validation errors.
- Configuration errors.
- Rule parsing errors.
- Integrity validation errors.
- Storage/export errors.
- Unexpected internal errors.

Batch execution should fail fast for invalid input or invalid rules, unless a
future product decision explicitly supports partial processing.

## Testing Strategy

### Unit Tests

Each engine should have direct tests for normal behavior and edge cases.

### Integration Tests

The pipeline should be tested from fixture CSV inputs to output files.

### Determinism Tests

The same input should be executed twice and outputs should match exactly, after
excluding any explicitly documented non-deterministic operational metadata.

### Golden Output Tests

Stable fixture outputs should be used for critical flows.

## Migration Strategy

Recommended migration path:

1. Freeze current behavior with tests.
2. Replace unsafe rule evaluation with safe parser.
3. Make generated IDs and timestamps deterministic or idempotent.
4. Introduce typed domain models.
5. Move modules gradually into `src/gamification_engine/`.
6. Keep CLI behavior stable.
7. Update docs and examples after each sprint.

## Open Architecture Decisions

- Keep pandas as the internal processing layer or move to typed dataclasses?
- Should output include both CSV and JSON permanently?
- Should existing `data/` files remain canonical fixtures?
- Should challenge priority treat lower number or higher number as higher
  priority?
- Should all timestamps be generated from `run_date`?
- Should deterministic IDs be hash-based?
- Should AI explanation read in-memory objects or exported output files?

## Sprint 0 Architecture Definition of Done

Architecture work is complete when:

- Current and target architecture are documented.
- Component responsibilities are separated.
- Dependency direction is clear.
- Migration risks are identified.
- Future design decisions are listed.
