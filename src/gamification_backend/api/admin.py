"""Admin panel API: challenges, users, runs, batch trigger, simulator."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import func, select

from gamification_backend.api.deps import AdminDep, SessionDep
from gamification_backend.api.schemas import (
    AdminUserResponse,
    BatchRunRequest,
    BatchRunSummaryResponse,
    ChallengeAdminResponse,
    ChallengeCreateRequest,
    ChallengeUpdateRequest,
    RunResponse,
    SimulatorStartRequest,
    SimulatorStatusResponse,
)
from gamification_backend.db.models import (
    ChallengeRecord,
    PointsLedgerRecord,
    RunRecord,
    UserRecord,
)
from gamification_backend.repositories.events import today_utc
from gamification_backend.services.condition_validation import validate_condition
from gamification_backend.services.daily_batch import run_daily_batch
from gamification_backend.services.simulator import TrafficSimulator

router = APIRouter(prefix="/admin", tags=["admin"])


def _validate_condition_or_422(condition: str) -> None:
    error = validate_condition(condition)
    if error is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Geçersiz koşul: {error}",
        )


@router.get("/ping")
def ping(admin: AdminDep) -> dict[str, str]:
    """Verify admin access works."""

    return {"status": "ok", "admin": admin.username}


@router.get("/challenges")
def list_challenges(
    admin: AdminDep, session: SessionDep
) -> list[ChallengeAdminResponse]:
    """All challenges including inactive, ordered by priority then id."""

    stmt = select(ChallengeRecord).order_by(
        ChallengeRecord.priority, ChallengeRecord.challenge_id
    )
    return [
        ChallengeAdminResponse.model_validate(record)
        for record in session.execute(stmt).scalars()
    ]


@router.post("/challenges", status_code=status.HTTP_201_CREATED)
def create_challenge(
    body: ChallengeCreateRequest, admin: AdminDep, session: SessionDep
) -> ChallengeAdminResponse:
    """Create a challenge; the condition must pass the engine's safe parser."""

    _validate_condition_or_422(body.condition)
    if session.get(ChallengeRecord, body.challenge_id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu challenge_id zaten var.",
        )
    record = ChallengeRecord(
        challenge_id=body.challenge_id,
        name=body.name,
        challenge_type=body.challenge_type,
        condition=body.condition,
        reward_points=body.reward_points,
        priority=body.priority,
        is_active=body.is_active,
    )
    session.add(record)
    session.commit()
    return ChallengeAdminResponse.model_validate(record)


@router.put("/challenges/{challenge_id}")
def update_challenge(
    challenge_id: str,
    body: ChallengeUpdateRequest,
    admin: AdminDep,
    session: SessionDep,
) -> ChallengeAdminResponse:
    """Partially update a challenge; affects future evaluations only —
    already-granted rewards live in the append-only ledger and never change."""

    record = session.get(ChallengeRecord, challenge_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Challenge bulunamadı.",
        )
    if body.condition is not None:
        _validate_condition_or_422(body.condition)
        record.condition = body.condition
    if body.name is not None:
        record.name = body.name
    if body.challenge_type is not None:
        record.challenge_type = body.challenge_type
    if body.reward_points is not None:
        record.reward_points = body.reward_points
    if body.priority is not None:
        record.priority = body.priority
    if body.is_active is not None:
        record.is_active = body.is_active
    session.commit()
    return ChallengeAdminResponse.model_validate(record)


@router.get("/users")
def list_users(admin: AdminDep, session: SessionDep) -> list[AdminUserResponse]:
    """All accounts with their point totals, ordered by username."""

    total = func.coalesce(func.sum(PointsLedgerRecord.points_delta), 0)
    stmt = (
        select(UserRecord, total.label("total_points"))
        .join(
            PointsLedgerRecord,
            PointsLedgerRecord.user_id == UserRecord.id,
            isouter=True,
        )
        .group_by(UserRecord.id)
        .order_by(UserRecord.username)
    )
    return [
        AdminUserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            is_admin=user.is_admin,
            is_bot=user.is_bot,
            created_at=user.created_at,
            total_points=int(total_points),
        )
        for user, total_points in session.execute(stmt).all()
    ]


def _simulator_response(simulator: TrafficSimulator) -> SimulatorStatusResponse:
    state = simulator.status()
    detail = (
        f"{state.bot_count} bot canlı trafik üretiyor."
        if state.running
        else "Simülatör durdu."
    )
    return SimulatorStatusResponse(
        running=state.running,
        bot_count=state.bot_count,
        tick_seconds=state.tick_seconds,
        ticks_completed=state.ticks_completed,
        events_recorded=state.events_recorded,
        detail=detail,
    )


@router.get("/simulator")
def simulator_status(admin: AdminDep, request: Request) -> SimulatorStatusResponse:
    """Traffic simulator status and counters."""

    return _simulator_response(request.app.state.simulator)


@router.post("/simulator/start")
async def start_simulator(
    body: SimulatorStartRequest, admin: AdminDep, request: Request
) -> SimulatorStatusResponse:
    """Create/reuse bot accounts and begin emitting live traffic."""

    simulator: TrafficSimulator = request.app.state.simulator
    started = await simulator.start(
        bot_count=body.bot_count, tick_seconds=body.tick_seconds
    )
    if not started:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Simülatör zaten çalışıyor.",
        )
    return _simulator_response(simulator)


@router.post("/simulator/stop")
async def stop_simulator(admin: AdminDep, request: Request) -> SimulatorStatusResponse:
    """Stop the traffic simulator (idempotent)."""

    simulator: TrafficSimulator = request.app.state.simulator
    await simulator.stop()
    return _simulator_response(simulator)


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
