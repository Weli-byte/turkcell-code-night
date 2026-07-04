"""Liveness/readiness endpoint."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from gamification_backend.api.deps import SessionDep

router = APIRouter(tags=["health"])


@router.get("/health")
def health(session: SessionDep) -> dict[str, str]:
    """Report service and database availability."""

    session.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}
