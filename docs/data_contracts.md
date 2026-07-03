# Data Contracts

## Purpose

Typed domain models live under `src/gamification_engine/domain/`.

These models define stable data contracts and validation rules. They do not
execute business workflows: rule evaluation, state calculation, ledger
updates, badge assignment, leaderboard generation, notifications and
explanations are implemented in their own modules.

## Modeling Decision

The project uses standard-library `dataclass` models.

Rationale:

- No runtime dependency is required.
- Models are easy for AI coding agents to inspect and extend.
- Validation stays explicit.
- JSON serialization can be controlled deterministically.

The project can still migrate to Pydantic later if stronger parsing and schema
generation become necessary.

## Enumerations

Defined in `src/gamification_engine/domain/enums.py`.

### ChallengeType

```text
DAILY
WEEKLY
STREAK
```

### BadgeType

```text
BRONZE
SILVER
GOLD
```

### RewardReason

```text
CHALLENGE_COMPLETED
MANUAL_ADJUSTMENT
```

### NotificationType

```text
CHALLENGE_REWARD
BADGE_EARNED
```

### NotificationChannel

```text
IN_APP
BIP
EMAIL
```

### ChallengeStatus

```text
TRIGGERED
SELECTED
SUPPRESSED
NOT_TRIGGERED
```

## UserActivity

Represents one raw activity record after ingestion parsing.

Fields:

```text
event_id: str | None
user_id: str
activity_date: date
watch_minutes: int
episodes_completed: int
unique_genres: int
watch_party_minutes: int
ratings_given: int
shows_watched: tuple[str, ...]
```

Validation:

- `user_id` must not be empty.
- `event_id`, when present, must not be empty.
- Numeric metrics must be non-negative.
- Empty show identifiers are removed from `shows_watched`.

## ChallengeDefinition

Represents a configured challenge loaded from challenge input.

Fields:

```text
challenge_id: str
name: str
challenge_type: ChallengeType
condition: str
reward_points: int
priority: int
is_active: bool
```

Validation:

- `challenge_id`, `name`, and `condition` must not be empty.
- `reward_points` must be positive.
- `priority` must be positive.

## DailyUserState

Represents computed user state for a run date.

Fields:

```text
user_id: str
state_date: date
watch_minutes_today: int
watch_minutes_7d: int
episodes_completed_today: int
episodes_completed_7d: int
unique_genres_today: int
watch_party_minutes_today: int
ratings_today: int
ratings_7d: int
watch_streak_days: int
```

Validation:

- `user_id` must not be empty.
- All metrics must be non-negative.

Rule context fields:

```text
watch_minutes_today
watch_minutes_7d
episodes_completed_today
episodes_completed_7d
unique_genres_today
watch_party_minutes_today
ratings_today
ratings_7d
watch_streak_days
```

## ChallengeDecision

Represents a challenge evaluation result for one user.

Fields:

```text
user_id: str
challenge_id: str
status: ChallengeStatus
evaluated_at: date
reason: str
```

## RewardEvent

Represents the selected reward after priority resolution.

Fields:

```text
reward_id: str
user_id: str
challenge_id: str
reward_points: int
reward_date: date
reason: RewardReason
suppressed_challenge_ids: tuple[str, ...]
```

Validation:

- `reward_points` must be positive.
- Identifiers must not be empty.

## PointsLedgerEntry

Represents one append-only point transaction.

Fields:

```text
ledger_id: str
user_id: str
points_delta: int
source: RewardReason
source_ref: str
created_at: datetime
```

Validation:

- `points_delta` must be positive.
- Identifiers must not be empty.

## BadgeAssignment

Represents an awarded badge.

Fields:

```text
user_id: str
badge_type: BadgeType
awarded_at: date
badge_id: str | None
```

Validation:

- `user_id` must not be empty.
- `badge_id`, when present, must not be empty.

## LeaderboardEntry

Represents a ranked leaderboard row.

Fields:

```text
rank: int
user_id: str
total_points: int
badges: tuple[BadgeType, ...]
```

Validation:

- `rank` must be positive.
- `total_points` must be non-negative.
- `user_id` must not be empty.

## Notification

Represents a generated notification record.

Fields:

```text
notification_id: str
user_id: str
notification_type: NotificationType
channel: NotificationChannel
message: str
created_at: datetime
source_ref: str
```

Validation:

- Identifiers, message, and source reference must not be empty.

## ExplanationResponse

Represents a deterministic answer from the explanation layer.

Fields:

```text
user_id: str
question: str
answer: str
evidence: dict[str, Any]
```

Validation:

- `user_id`, `question`, and `answer` must not be empty.
- Evidence is serialized into JSON-compatible primitive values.

## Serialization Rules

Every model exposes `to_dict()`.

Serialization guarantees:

- Dates use ISO format.
- Datetimes use ISO format.
- Enums use their string values.
- Tuples are converted to lists.
- Evidence values are converted recursively.

## CSV Column Mapping

The activity CSV header is:

```text
event_id,user_id,date,shows_watched,unique_genres,watch_minutes,
episodes_completed,watch_party_minutes,ratings
```

Ingestion (`src/gamification_engine/ingestion/`) maps `date` to
`activity_date`, `ratings` to `ratings_given`, and splits `shows_watched`
on `|`. The challenge CSV header is:

```text
challenge_id,challenge_name,challenge_type,condition,reward_points,
priority,is_active
```

Sample input files live under `data/input/`; expected JSON output shapes
can be inspected under `data/output/` and
`tests/fixtures/golden_outputs/`.
