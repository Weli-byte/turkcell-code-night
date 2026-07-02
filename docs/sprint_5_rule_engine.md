# Sprint 5 Rule Engine and Challenge Evaluation

## Goal

Sprint 5 adds a safe deterministic rule engine for the new production package.

The rule engine evaluates active `ChallengeDefinition` records against
`DailyUserState` records from Sprint 4 and selects at most one reward per user
according to challenge priority.

## Added Modules

```text
src/gamification_engine/rules/
  __init__.py
  condition_parser.py
  evaluator.py
  challenge_repository.py
  reward_selector.py
```

## Condition Syntax

The MVP supports only simple comparison expressions:

```text
field operator integer_literal
```

Examples:

```text
watch_minutes_today >= 60
episodes_completed_today >= 2
ratings_7d == 4
```

Supported operators:

```text
>=
>
<=
<
==
!=
```

Unsupported:

- Compound expressions such as `A and B`.
- Function calls.
- Arithmetic expressions.
- Unknown state fields.
- Python code execution.

## Safety

The new rule engine does not use Python `eval()`.

`condition_parser.py` parses conditions with a strict regular expression and
validates field names against `DailyUserState.to_rule_context()`.

## Challenge Repository

`ChallengeRepository` is a read-only in-memory repository.

Responsibilities:

- Normalize challenge order by `challenge_id`.
- Return all challenges.
- Return active challenges.
- Reject duplicate challenge IDs.

## Evaluation

`evaluate_challenge()` evaluates one challenge.

Inactive challenges always return `False`.

`evaluate_challenges_for_state()` evaluates a list of challenges for one user
state and returns triggered challenges sorted by:

```text
priority ascending
challenge_id ascending
```

## Reward Selection

`select_reward()` receives triggered challenges and returns one `RewardEvent`.

Priority policy:

```text
Lowest numeric priority wins.
```

Tie-break:

```text
challenge_id ascending
```

Suppressed challenges are included in `RewardEvent.suppressed_challenge_ids`.

Reward IDs are deterministic:

```text
reward_id = reward-{sha256(user_id|reward_date|challenge_id)[:16]}
```

## Inputs

```python
state: DailyUserState
challenges: list[ChallengeDefinition]
reward_date: date
```

## Outputs

```python
triggered_challenges: list[ChallengeDefinition]
reward_event: RewardEvent | None
```

## Definition of Done

Sprint 5 is complete when:

- Rule parsing is implemented without `eval()`.
- Unsupported fields and syntax fail with `RuleEvaluationError`.
- All MVP comparison operators are supported.
- Inactive challenges do not trigger.
- Triggered challenges are returned in deterministic order.
- Reward selection returns only one reward.
- Priority and tie-break rules are tested.
- Reward IDs are deterministic.
