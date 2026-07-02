# Sprint 0 Product Plan

## Product Vision

This project is a deterministic gamification engine for digital video
platforms such as TV+, Netflix-like services, Disney+, BluTV-like services,
and similar subscription video products.

The engine receives daily user activity data, computes user engagement state,
evaluates active challenges, awards points, assigns badges, builds a
leaderboard, generates notifications, and exports all results in stable output
formats.

The system must remain fully functional without an LLM. Any LLM integration is
limited to explanation wording and must never decide rewards, points, badges,
or leaderboard position.

## MVP Scope

The MVP includes:

- CSV-based input loading.
- Per-user daily state calculation.
- Rolling engagement metrics such as 7-day watch minutes.
- Watch streak calculation.
- Challenge evaluation from CSV definitions.
- Priority-based reward selection.
- Append-only points ledger.
- Badge assignment based on total points.
- Deterministic leaderboard.
- Notification record generation.
- JSON and CSV output.
- Deterministic explanation layer for user questions.
- Integrity validation before final output promotion.

## Out of Scope for MVP

The MVP does not include:

- Real-time event streaming.
- Web UI or admin panel.
- User authentication.
- External database persistence.
- Distributed job execution.
- Production observability stack.
- LLM-based business decisions.
- Personalized challenge generation by LLM.
- A/B testing framework.

## Domain Glossary

### User Activity

Raw engagement record for a user. Examples include watch minutes, completed
episodes, watched genres, watch party minutes, and ratings.

### Daily User State

Derived per-user state for a given run date. It contains daily metrics, rolling
metrics, streaks, and other values used by the rule engine.

### Challenge

A configured gamification task. Each challenge has an ID, name, type,
condition, reward points, priority, and active flag.

### Rule

A deterministic condition evaluated against a user's state. Example:

```text
watch_minutes_today >= 60
```

### Triggered Challenge

A challenge whose condition evaluates to true for a user.

### Selected Reward

The single challenge reward selected for a user after applying priority rules.

### Suppressed Challenge

A triggered challenge that did not receive a reward because another triggered
challenge had higher priority.

### Points Ledger Entry

Append-only record representing a point transaction. Ledger entries must never
be updated or deleted as part of normal engine behavior.

### Badge Award

Record showing that a user earned a badge such as Bronze, Silver, or Gold.
The same badge must not be awarded twice to the same user.

### Leaderboard Entry

Ranked user record based on total points. Sorting must be deterministic.

### Notification

Record generated from reward or badge events. Notification generation creates
data only; delivery to an external channel is out of scope.

### Explanation

Deterministic answer to a user question such as "Why did I win this reward?"
or "What should I do to reach Gold?"

## Target Users

### Product Manager

Uses the engine to define challenges, tune reward points, and understand user
engagement mechanics.

### Data or Growth Team

Analyzes challenge outcomes, leaderboard movement, and badge progression.

### Platform Engineer

Runs the batch pipeline, validates outputs, and integrates result files with
downstream services.

### End User

Receives rewards, badges, notifications, leaderboard position, and explanations.

## Product Principles

1. Deterministic by default.
2. Business rules are explicit and testable.
3. Ledger is append-only.
4. Every automated decision is explainable.
5. Outputs are stable and auditable.
6. Modules have single responsibility.
7. LLMs never own business logic.

## Existing Project Baseline

The current repository already contains a working batch-style structure:

- `main.py` orchestrates the full pipeline.
- `state_engine/` builds user state.
- `logic_engine/` contains rule, badge, notification, and leaderboard logic.
- `models/ledger.py` contains ledger behavior.
- `ai_layer/` contains deterministic and fallback explanation logic.
- `utils/` contains loading, schema validation, and integrity validation.
- `data/` and `output/` contain input and output files.

Sprint 0 does not rewrite code. It documents the intended professional product
direction and identifies decisions that later implementation sprints should
make explicit.

## Known Technical Gaps to Address Later

- Rule evaluation currently uses Python `eval()` and should be replaced with a
  safe parser in a future sprint.
- Some generated IDs use random UUIDs; deterministic or idempotent ID strategy
  should be defined for reproducible runs.
- Some timestamps use current system time; run-date-based or deterministic
  timestamp policy should be defined.
- Existing code is pandas-based; future architecture must decide whether to
  keep pandas or move toward typed domain models.
- Current documentation has encoding issues in some Turkish text and should be
  normalized.

## Success Metrics

The project is successful when:

- The same inputs produce the same outputs across repeated runs.
- Challenge decisions are explainable from state and challenge definitions.
- Ledger totals match leaderboard totals.
- Badge duplicate prevention is guaranteed.
- AI explanations can run without external API calls.
- A new challenge can be added by editing CSV/config rather than core logic.
- Critical modules are covered by automated tests.

## Sprint 0 Deliverables

This sprint produces:

- Product plan: `docs/product_plan.md`
- Architecture plan: `docs/architecture.md`
- Data flow plan: `docs/data_flow.md`
- Deterministic rules: `docs/deterministic_rules.md`

## Definition of Done

Sprint 0 is complete when:

- MVP scope and out-of-scope boundaries are documented.
- Domain glossary is documented.
- High-level architecture is documented.
- Data flow is documented from CSV input to exported output.
- Determinism rules are documented.
- Open design decisions are listed for future sprints.
