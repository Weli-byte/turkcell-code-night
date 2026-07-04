"""Admin-only endpoints (grows into the admin panel API in Sprint 27)."""

from __future__ import annotations

from fastapi import APIRouter

from gamification_backend.api.deps import AdminDep

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/ping")
def ping(admin: AdminDep) -> dict[str, str]:
    """Verify admin access works."""

    return {"status": "ok", "admin": admin.username}
