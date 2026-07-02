# Sprint 0 Deterministic Rules

## Determinism Goal

Given the same input files, same persisted history, same configuration, and
same run date, the engine must produce the same business outputs every time.

Determinism is a product requirement because the system awards points, badges,
rankings, and user-facing explanations. These outputs must be auditable.

## Deterministic Inputs

Every run should be defined by:

```text
run_date
activity input path
challenge input path
existing ledger path
existing badge path
configuration version
engine version
```

The pipeline should not depend on the current system date for business
decisions.

## Sorting Rules

All outputs should be written in stable order.

Recommended ordering:

- User state: `user_id` ascending.
- Challenge awards: `as_of_date`, `user_id`, `selected_challenge`.
- Ledger: transaction date, `user_id`, source challenge, entry ID.
- Badge awards: award date, `user_id`, badge tier.
- Notifications: notification date, `user_id`, notification ID.
- Leaderboard: rank ascending.
- Challenge decisions: `user_id`, priority, challenge ID.

## Leaderboard Rules

Leaderboard sorting:

```text
1. total_points descending
2. user_id ascending
3. consecutive rank assignment
```

Example:

```text
rank  user_id  total_points
1     u001     500
2     u002     500
3     u003     300
```

Equal scores do not share rank in the recommended MVP policy. This makes
explanations and downstream display simpler.

## Challenge Priority Rules

The current code treats the lowest numeric priority as highest priority:

```text
priority 1 > priority 2 > priority 3
```

This policy should be explicitly accepted or changed before future refactors.
Whichever policy is chosen must be documented and tested.

Recommended tie-breaks:

```text
1. priority according to chosen policy
2. challenge_id ascending
```

## Rule Evaluation Rules

Challenge conditions must be evaluated with a safe parser, not Python `eval()`.

Supported MVP operators:

```text
>=
>
<=
<
==
!=
```

Supported MVP expression shape:

```text
field operator literal
```

Example:

```text
watch_minutes_today >= 60
```

Allowed fields should be whitelisted from user state. Unknown fields should
fail validation.

## ID Generation Rules

Random IDs reduce reproducibility. Future implementation should prefer
deterministic IDs derived from stable business keys.

Recommended examples:

```text
award_id = hash(user_id, run_date, selected_challenge)
ledger_entry_id = hash(user_id, run_date, source_type, source_id)
notification_id = hash(user_id, run_date, notification_type, source_id)
badge_award_id = hash(user_id, badge_name)
```

Hashes should use a stable algorithm such as SHA-256 and a documented prefix.

## Timestamp Rules

Business timestamps should be derived from `run_date` unless operational
timestamps are explicitly needed.

Recommended distinction:

- `business_date`: deterministic date used for decisions.
- `created_at`: optional operational timestamp for logs only.

If `created_at` is included in exported business files, repeated outputs will
not match exactly. Therefore, avoid current time in exported business outputs
unless the field is excluded from determinism tests.

## Ledger Rules

The points ledger must be append-only:

- Do not update existing entries.
- Do not delete existing entries.
- Add new entries only when a new reward is earned.
- Calculate point totals from ledger history.
- Prevent duplicate entries for the same logical reward.

Recommended duplicate key:

```text
user_id + business_date + selected_challenge
```

If re-running the same day with the same inputs, no duplicate points should be
added.

## Badge Rules

Badge assignment must be idempotent:

- Same user cannot receive the same badge twice.
- Badge threshold comparison must be deterministic.
- Badge ordering should be explicit.

Recommended MVP thresholds:

```text
Bronze: 500
Silver: 1500
Gold: 3000
```

If a user crosses multiple thresholds in one run, recommended behavior is to
award all missing earned badges in tier order.

## AI Layer Rules

The AI layer must be deterministic by default.

It may explain:

- Why a reward was earned.
- Why another triggered challenge was suppressed.
- How many points are needed for a badge.
- Why a user has a specific leaderboard rank.
- Which evidence was used.

It must not:

- Award points.
- Change challenge decisions.
- Change badge decisions.
- Change leaderboard rank.
- Invent missing state.

If an LLM adapter is added, it may only rephrase a deterministic explanation.

## File Output Rules

JSON output should use:

```text
indent=2
sort_keys or stable model-defined key order
ISO date formatting
UTF-8 encoding
```

CSV output should use:

```text
stable column order
UTF-8 encoding
stable row order
no index column
```

## Randomness Rules

The core engine should not use:

- `random`
- random UUIDs for business IDs
- current system time for business decisions
- unordered set iteration for output order
- non-deterministic parallel reduction

## Floating Point Rules

Use integers for points and minutes. Avoid floating point values in business
rules unless a future requirement explicitly needs them.

## Current Determinism Risks

The current codebase should address these in later implementation sprints:

- `logic_engine/rule_engine.py` uses `eval()`.
- `logic_engine/rule_engine.py` generates random UUID award IDs.
- `logic_engine/rule_engine.py` uses current UTC time for award timestamps.
- Any output containing current-time metadata will differ across repeated runs.
- Input files should be normalized before processing if row order can vary.

## Determinism Test Requirements

Future tests should verify:

- Same input produces identical outputs.
- Reordered input rows produce identical business outputs.
- Re-running the same date does not duplicate ledger entries.
- Equal leaderboard scores sort by `user_id`.
- Challenge priority tie-break is stable.
- Badge duplicate guard works.
- AI explanation returns the same answer for the same context.

## Open Determinism Decisions

- Should output include operational timestamps?
- Should deterministic IDs replace all UUIDs?
- Should the engine support exact golden-file comparison?
- Should lower priority number or higher priority number mean higher priority?
- Should rank be consecutive or shared for equal scores?
- Should data ingestion fail on the first error or collect all errors?

## Sprint 0 Determinism Definition of Done

Determinism work is complete when:

- Deterministic input assumptions are documented.
- Sorting and tie-break rules are documented.
- Ledger and badge idempotency rules are documented.
- AI layer boundaries are documented.
- Current determinism risks are documented.
- Future determinism tests are specified.
