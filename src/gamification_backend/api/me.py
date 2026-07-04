"""Endpoints about the authenticated user."""

from __future__ import annotations

from fastapi import APIRouter

from gamification_backend.api.deps import CurrentUserDep
from gamification_backend.api.schemas import UserResponse

router = APIRouter(tags=["me"])


@router.get("/me")
def read_me(user: CurrentUserDep) -> UserResponse:
    """Return the authenticated user's profile."""

    return UserResponse.model_validate(user)
