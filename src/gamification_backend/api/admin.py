"""Admin-only endpoints (grows into the admin panel API in Sprint 27)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter
from sqlalchemy import select

from gamification_backend.api.deps import AdminDep, SessionDep
from gamification_backend.api.schemas import (
    BatchRunRequest,
    BatchRunSummaryResponse,
    RunResponse,
)
from gamification_backend.db.models import RunRecord
from gamification_backend.repositories.events import today_utc
from gamification_backend.services.daily_batch import run_daily_batch

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/ping")
def ping(admin: AdminDep) -> dict[str, str]:
    """Verify admin access works."""

    return {"status": "ok", "admin": admin.username}


@router.get("/runs")
def list_runs(admin: AdminDep, session: SessionDep) -> list[RunResponse]:
    """Pipeline run history, newest first."""

    stmt = select(RunRecord).order_by(RunRecord.id.desc())
    return [
        RunResponse.model_validate(record) for record in session.execute(stmt).scalars()
    ]


@router.post("/batch-run")
def trigger_batch(
    body: BatchRunRequest, admin: AdminDep, session: SessionDep
) -> BatchRunSummaryResponse:
    """Run the end-of-day batch now (defaults to today, UTC)."""

    run_date = body.run_date if body.run_date is not None else today_utc()
    summary = run_daily_batch(session, run_date=run_date)
    return BatchRunSummaryResponse(
        run_date=date.fromisoformat(summary.run_date),
        users_processed=summary.users_processed,
        new_rewards=summary.new_rewards,
        new_badges=summary.new_badges,
        new_notifications=summary.new_notifications,
        leaderboard_size=summary.leaderboard_size,
    )
