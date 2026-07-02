# Sprint 4 User State Engine

## Goal

Sprint 4 adds the typed user state engine for the new production package.

The state engine receives `list[UserActivity]` from Sprint 3 ingestion and
produces deterministic `list[DailyUserState]` records for a given `run_date`.

## Added Modules

```text
src/gamification_engine/state/
  __init__.py
  metrics.py
  streaks.py
  state_builder.py
```

## Responsibilities

### metrics.py

Aggregates raw activity records into daily user/date metrics.

Responsibilities:

- Sum duplicate activity rows for the same user and date.
- Return sorted user IDs.
- Retrieve metrics for one user/date.
- Sum metrics over an inclusive rolling window.

### streaks.py

Calculates watch streak length.

Default rule:

```text
A day qualifies for streak when watch_minutes >= 30.
```

The streak is counted backward from `run_date`. Missing days and low-watch days
break the streak.

### state_builder.py

Builds `DailyUserState` records.

Responsibilities:

- Aggregate activity rows.
- Calculate today metrics.
- Calculate 7-day rolling metrics.
- Calculate watch streak days.
- Return state rows in deterministic `user_id` order.

## Input

```python
activities: Iterable[UserActivity]
run_date: date
```

## Output

```python
list[DailyUserState]
```

Output order:

```text
user_id ascending
```

## Metric Rules

Today metrics are calculated only for `run_date`:

```text
watch_minutes_today
episodes_completed_today
unique_genres_today
watch_party_minutes_today
ratings_today
```

7-day metrics use an inclusive window:

```text
run_date - 6 days <= activity_date <= run_date
```

7-day metrics:

```text
watch_minutes_7d
episodes_completed_7d
ratings_7d
```

## Empty and Missing Data Behavior

- Empty activity input returns an empty list.
- A user with activity in the 7-day window but no activity on `run_date` gets
  zero today metrics.
- A user without qualifying activity on `run_date` gets `watch_streak_days = 0`.
- Activity after `run_date` is ignored by rolling and today metrics.

## Determinism

The state engine is deterministic because:

- It does not use system time.
- It accepts explicit `run_date`.
- It aggregates by stable keys.
- It emits states sorted by `user_id`.
- It uses integer arithmetic only.

## Definition of Done

Sprint 4 is complete when:

- `build_daily_user_states()` produces typed `DailyUserState` rows.
- Duplicate same-day activities are aggregated.
- 7-day rolling metrics are calculated inclusively.
- Watch streak is calculated from `run_date` backward.
- Empty input is handled.
- Unit tests cover metrics, streaks, and state builder.
