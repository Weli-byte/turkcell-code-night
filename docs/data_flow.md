# Sprint 0 Data Flow

## Overview

The system runs as a daily batch pipeline. It reads CSV inputs, computes
gamification state and outcomes, validates consistency, and writes stable
outputs.

## Input Files

The current repository uses these data files:

```text
data/activity_events.csv
data/challenges.csv
data/users.csv
data/shows.csv
data/episodes.csv
data/points_ledger.csv
data/badge_awards.csv
data/challenge_awards.csv
data/challenge_decisions.csv
data/notifications.csv
data/leaderboard.csv
data/user_state.csv
```

The primary MVP runtime inputs are:

```text
data/activity_events.csv
data/challenges.csv
```

Existing persisted outputs may also be read for idempotency:

```text
output/points_ledger.csv
output/badge_awards.csv
output/challenge_awards.csv
output/notifications.csv
output/leaderboard.csv
```

## Activity Data Contract

The final contract should contain at least:

```text
user_id
event_date or date
watch_minutes
episodes_completed
genre or genre_count
watch_party_minutes
ratings_given
```

Current sprint goal is not to change the schema. Later sprints should document
the exact current columns and normalize them into a stable contract.

## Challenge Data Contract

The current challenge file includes:

```text
challenge_id
challenge_name
challenge_type
condition
reward_points
priority
is_active
```

Example condition:

```text
watch_minutes_today >= 60
```

## Main Processing Flow

```text
1. Load activity CSV
2. Load challenge CSV
3. Validate input schemas
4. Build user state for run date
5. Evaluate active challenge conditions
6. Resolve challenge priority per user
7. Generate challenge award records
8. Append points ledger records
9. Calculate total points from ledger
10. Assign new badges
11. Generate notifications
12. Build leaderboard
13. Validate output consistency
14. Write output files to temporary directory
15. Promote temporary files to output directory
```

## State Data Flow

Raw events are transformed into per-user state.

```text
activity_events.csv
  -> group by user and date
  -> aggregate daily metrics
  -> compute rolling metrics
  -> compute streak metrics
  -> user_state
```

Expected state fields include:

```text
user_id
watch_minutes_today
watch_minutes_7d
episodes_completed_today
episodes_completed_7d
unique_genres_today
watch_party_minutes_today
ratings_7d
watch_streak_days
```

## Challenge Evaluation Flow

```text
user_state + active challenges
  -> evaluate each condition
  -> collect triggered challenges
  -> resolve priority
  -> produce one selected challenge award per user
```

Important rule:

Only one challenge reward should be awarded to a user per run after priority
resolution, unless a future product decision changes this.

## Points Ledger Flow

```text
selected challenge awards
  -> duplicate check
  -> create point ledger entries
  -> append to existing ledger
  -> calculate total points by user
```

The ledger is the source of truth for total points.

## Badge Flow

```text
total points + existing badge awards
  -> compare with badge thresholds
  -> create missing badge awards
  -> preserve previous badge awards
```

The same user cannot receive the same badge twice.

## Leaderboard Flow

```text
total points
  -> sort by total_points descending
  -> tie-break by user_id ascending
  -> assign consecutive rank
  -> export leaderboard
```

## Notification Flow

```text
new challenge awards + new badge awards
  -> generate notification records
  -> duplicate guard
  -> export notifications
```

Notifications are records only. Delivery is not part of the MVP.

## AI Explanation Flow

The AI layer should read already-computed deterministic data:

```text
user question
  + user state
  + ledger history
  + badge awards
  + challenge decisions
  + leaderboard
  -> deterministic explanation
```

Optional LLM flow:

```text
deterministic explanation
  -> LLM wording adapter
  -> enhanced natural-language answer
```

The LLM must not receive authority to change values, ranks, rewards, or badges.

## Output Files

The current output directory includes:

```text
output/challenge_awards.json
output/badge_awards.json
output/badge_awards.csv
output/notifications.json
output/notifications.csv
output/points_ledger.json
output/points_ledger.csv
output/leaderboard.json
output/leaderboard.csv
```

Future output should also consider:

```text
output/user_state.json
output/challenge_decisions.json
output/run_summary.json
```

## Integrity Validation

Before final output promotion, the system should validate:

- Award points match ledger points.
- Leaderboard totals match ledger aggregation.
- Badge awards are not duplicated.
- Challenge references exist.
- Notification references point to valid events.
- Required output files are complete.

## Failure Behavior

Recommended default behavior:

- Invalid input: fail run.
- Invalid challenge condition: fail run.
- Integrity validation failure: do not promote outputs.
- Missing optional previous output file: treat as empty history.
- Unexpected exception: fail run and preserve previous output.

## Data Flow Open Questions

- Should malformed input rows be skipped or fail the entire run?
- Should `data/points_ledger.csv` or `output/points_ledger.csv` be the source
  of previous ledger state?
- Should the pipeline export user state every run?
- Should challenge decisions include non-winning triggered challenges?
- Should suppressed challenges be exported separately for explanations?
- Should dates be timezone-aware or pure local dates?

## Sprint 0 Data Flow Definition of Done

Data flow work is complete when:

- Main input and output files are identified.
- Pipeline stages are documented.
- State, challenge, ledger, badge, leaderboard, notification, and AI flows are
  documented.
- Validation and failure behavior are documented.
- Open data contract questions are listed.
