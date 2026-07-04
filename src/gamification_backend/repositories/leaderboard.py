"""Leaderboard built live from the append-only ledger.

Engine ordering rules apply: total points descending, deterministic
tie-break (alphabetical username), sequential ranks starting at 1. Only
users with at least one ledger entry appear.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gamification_backend.db.models import (
    BadgeRecord,
    PointsLedgerRecord,
    UserRecord,
)


@dataclass(frozen=True)
class LeaderboardRow:
    """One ranked leaderboard entry."""

    rank: int
    user_id: str
    username: str
    total_points: int
    badges: tuple[str, ...]
    is_bot: bool


def build_leaderboard(
    session: Session, *, limit: int | None = None
) -> list[LeaderboardRow]:
    """Rank all users that have earned points."""

    totals_stmt = (
        select(
            UserRecord.id,
            UserRecord.username,
            UserRecord.is_bot,
            func.sum(PointsLedgerRecord.points_delta).label("total"),
        )
        .join(PointsLedgerRecord, PointsLedgerRecord.user_id == UserRecord.id)
        .group_by(UserRecord.id, UserRecord.username, UserRecord.is_bot)
    )
    rows = session.execute(totals_stmt).all()

    badge_stmt = select(BadgeRecord.user_id, BadgeRecord.badge_type).order_by(
        BadgeRecord.id
    )
    badges_by_user: dict[str, list[str]] = {}
    for user_id, badge_type in session.execute(badge_stmt).all():
        badges_by_user.setdefault(user_id, []).append(badge_type)

    ordered = sorted(rows, key=lambda row: (-int(row.total), row.username))
    if limit is not None:
        ordered = ordered[:limit]
    return [
        LeaderboardRow(
            rank=index + 1,
            user_id=row.id,
            username=row.username,
            total_points=int(row.total),
            badges=tuple(badges_by_user.get(row.id, [])),
            is_bot=bool(row.is_bot),
        )
        for index, row in enumerate(ordered)
    ]
