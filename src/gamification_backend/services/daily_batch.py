"""End-of-day batch: seals a day's rewards, badges and leaderboard.

The batch replays live evaluation for every user in deterministic order
(user id ascending). Because every write path is idempotent — rewards via
``UNIQUE(user_id, reward_date)``, ledger via ``UNIQUE(user_id, source_ref)``,
badges and notifications via their own guards — the batch can never
contradict what live evaluation already granted; it only fills gaps (for
example events ingested while evaluation was down) and records a run entry.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from gamification_backend.db.models import RunRecord, UserRecord
from gamification_backend.repositories.leaderboard import build_leaderboard
from gamification_backend.services.live_evaluator import evaluate_user_live


@dataclass(frozen=True)
class DailyBatchSummary:
    """Outcome of one batch execution (new grants only)."""

    run_date: str
    users_processed: int
    new_rewards: int
    new_badges: int
    new_notifications: int
    leaderboard_size: int


def run_daily_batch(session: Session, *, run_date: date) -> DailyBatchSummary:
    """Evaluate every user for the given day and record the run."""

    user_ids = list(
        session.execute(select(UserRecord.id).order_by(UserRecord.id)).scalars()
    )
    new_rewards = 0
    new_badges = 0
    new_notifications = 0
    for user_id in user_ids:
        result = evaluate_user_live(session, user_id=user_id, event_date=run_date)
        if result.reward is not None:
            new_rewards += 1
        new_badges += len(result.new_badges)
        new_notifications += len(result.notifications)

    leaderboard = build_leaderboard(session)
    summary = DailyBatchSummary(
        run_date=run_date.isoformat(),
        users_processed=len(user_ids),
        new_rewards=new_rewards,
        new_badges=new_badges,
        new_notifications=new_notifications,
        leaderboard_size=len(leaderboard),
    )
    session.add(
        RunRecord(
            run_date=run_date,
            run_type="daily",
            status="success",
            summary_json=json.dumps(asdict(summary), sort_keys=True),
        )
    )
    session.commit()
    return summary
