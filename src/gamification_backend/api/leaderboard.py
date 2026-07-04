"""Live leaderboard endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Query

from gamification_backend.api.deps import CurrentUserDep, SessionDep
from gamification_backend.api.schemas import LeaderboardEntryResponse
from gamification_backend.repositories.leaderboard import build_leaderboard

router = APIRouter(tags=["leaderboard"])


@router.get("/leaderboard")
def read_leaderboard(
    user: CurrentUserDep,
    session: SessionDep,
    limit: int | None = Query(default=None, ge=1, le=500),
) -> list[LeaderboardEntryResponse]:
    """Current ranking computed live from the points ledger."""

    return [
        LeaderboardEntryResponse(
            rank=row.rank,
            user_id=row.user_id,
            username=row.username,
            total_points=row.total_points,
            badges=list(row.badges),
            is_bot=row.is_bot,
        )
        for row in build_leaderboard(session, limit=limit)
    ]
