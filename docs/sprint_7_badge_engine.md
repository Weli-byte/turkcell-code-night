# Sprint 7 Badge Engine

## Goal

Sprint 7 adds deterministic badge assignment to the new production package.

The badge engine receives total points from the points ledger and assigns
missing earned badge tiers. It does not calculate points itself.

## Added Modules

```text
src/gamification_engine/config/
  __init__.py
  badge_config.py

src/gamification_engine/badges/
  __init__.py
  badge_engine.py
  badge_repository.py
```

## Badge Thresholds

MVP thresholds:

```text
Bronze: 500
Silver: 1500
Gold: 3000
```

Thresholds are ordered from lowest to highest. A user earns every missing badge
tier whose threshold has been reached.

Example:

```text
current badges: none
total points: 3200
new badges: BRONZE, SILVER, GOLD
```

## Duplicate Guard

The same user cannot receive the same badge twice.

Duplicate key:

```text
user_id + badge_type
```

Existing badge assignments are preserved.

## Deterministic ID Strategy

Badge IDs are generated with SHA-256:

```text
badge_id = badge-{sha256(user_id|badge_type)[:16]}
```

This makes repeated runs produce the same badge ID for the same logical badge.

## Input

```python
user_total_points: dict[str, int]
existing_badges: Iterable[BadgeAssignment]
run_date: date
```

## Output

```python
new_badges: list[BadgeAssignment]
all_badges: list[BadgeAssignment]
```

## Sorting

Badge assignments are sorted by:

```text
awarded_at ascending
user_id ascending
badge tier order
badge_id ascending
```

## Persistence

`badge_repository.py` provides JSON helpers:

- Missing file means empty history.
- Top-level JSON must be a list.
- Invalid badge payloads raise `IngestionError`.
- Output JSON is pretty-printed with UTF-8 encoding.

## Definition of Done

Sprint 7 is complete when:

- Badge thresholds are configurable in a dedicated config module.
- Users receive all missing badges they qualify for.
- Existing badges are not duplicated.
- Badge IDs are deterministic.
- Badge JSON repository can load and write assignments.
- Unit tests cover threshold behavior, duplicate guard, determinism, and
  repository behavior.
