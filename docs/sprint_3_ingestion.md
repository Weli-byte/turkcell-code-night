# Sprint 3 CSV Ingestion

## Goal

Sprint 3 adds the CSV ingestion layer for the new production package.

The ingestion layer reads raw CSV files, validates required headers, parses
primitive values, normalizes current prototype field names, and returns typed
domain models from Sprint 2.

## Added Modules

```text
src/gamification_engine/ingestion/
  __init__.py
  csv_loader.py
  schemas.py
  validators.py
```

## Responsibilities

### schemas.py

Defines expected CSV headers for:

- User activity input.
- Challenge definition input.

### validators.py

Parses and validates individual CSV rows.

Responsibilities:

- Required text parsing.
- ISO date parsing.
- Integer parsing.
- Boolean parsing.
- Challenge type parsing.
- Duplicate challenge ID validation.
- Conversion into Sprint 2 domain models.

### csv_loader.py

Reads CSV files from disk and returns typed model lists.

Responsibilities:

- File existence checks.
- UTF-8-SIG CSV reading.
- Header validation.
- Row normalization.
- Deterministic output ordering.

## User Activity CSV Contract

Required headers:

```text
user_id
date
shows_watched
unique_genres
watch_minutes
episodes_completed
watch_party_minutes
ratings
```

Optional headers:

```text
event_id
```

Mapping:

```text
date -> UserActivity.activity_date
ratings -> UserActivity.ratings_given
shows_watched -> tuple split by "|"
```

## Challenge CSV Contract

Required headers:

```text
challenge_id
challenge_name
challenge_type
condition
reward_points
priority
is_active
```

Mapping:

```text
challenge_name -> ChallengeDefinition.name
challenge_type -> ChallengeType
reward_points -> positive int
priority -> positive int
is_active -> bool
```

## Deterministic Ordering

Activity output is sorted by:

```text
activity_date ascending
user_id ascending
event_id ascending
```

Challenge output is sorted by:

```text
challenge_id ascending
```

## Validation Behavior

The MVP behavior is fail-fast:

- Missing file fails ingestion.
- Missing required headers fail ingestion.
- Invalid row values fail ingestion.
- Duplicate challenge IDs fail ingestion.
- Extra columns are tolerated and ignored.

## Fixtures

Sprint 3 adds CSV fixtures under:

```text
tests/fixtures/
  valid_user_activities.csv
  valid_challenges.csv
  invalid_user_activities.csv
  invalid_challenges.csv
```

## Verification

Expected commands:

```bash
$env:PYTHONPATH = 'src'; python -m pytest
$env:PYTHONPATH = 'src'; python -m mypy
```

## Definition of Done

Sprint 3 is complete when:

- Activity CSV can be loaded into `list[UserActivity]`.
- Challenge CSV can be loaded into `list[ChallengeDefinition]`.
- Required headers are validated.
- Invalid rows fail with `IngestionError`.
- Duplicate challenge IDs fail with `IngestionError`.
- Output ordering is deterministic.
- Unit tests cover validators and loaders.
