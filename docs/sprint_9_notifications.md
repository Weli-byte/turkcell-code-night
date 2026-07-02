# Sprint 9 Notification Engine

## Goal

Sprint 9 adds deterministic notification record generation to the new
production package.

Notifications are data records only. External delivery is outside the MVP.

## Added Modules

```text
src/gamification_engine/notifications/
  __init__.py
  notification_engine.py
  notification_repository.py
```

## Event Sources

Notifications are generated from:

- `RewardEvent`
- `BadgeAssignment`

## Notification Types

```text
CHALLENGE_REWARD
BADGE_EARNED
```

Default channel:

```text
IN_APP
```

Callers may override the channel, for example to `BIP`.

## Duplicate Guard

Duplicate key:

```text
notification_type + source_ref
```

Reward notifications use:

```text
source_ref = RewardEvent.reward_id
```

Badge notifications use:

```text
source_ref = BadgeAssignment.badge_id
```

If `badge_id` is missing, the fallback source reference is:

```text
user_id|badge_type
```

## Deterministic ID Strategy

Notification IDs are generated with SHA-256:

```text
notification_id = notification-{sha256(user_id|notification_type|source_ref)[:16]}
```

## Timestamp Strategy

Notification timestamps are deterministic:

```text
created_at = event date at 00:00:00 UTC
```

Reward event date comes from `RewardEvent.reward_date`.

Badge event date comes from `BadgeAssignment.awarded_at`.

## Sorting

Notifications are sorted by:

```text
created_at ascending
user_id ascending
notification_type ascending
source_ref ascending
notification_id ascending
```

## Persistence

`notification_repository.py` provides JSON helpers:

- Missing file means empty history.
- Top-level JSON must be a list.
- Invalid payloads raise `IngestionError`.
- Output JSON is pretty-printed with UTF-8 encoding.

## Definition of Done

Sprint 9 is complete when:

- Reward notifications are generated.
- Badge notifications are generated.
- Existing notifications are preserved.
- Duplicate notifications are skipped.
- Notification IDs are deterministic.
- Notification timestamps are deterministic.
- JSON repository helpers can load and write notifications.
- Unit tests cover generation, duplicate guard, determinism, channel override,
  and repository behavior.
