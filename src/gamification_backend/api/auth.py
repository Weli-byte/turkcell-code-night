"""Registration and login endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from gamification_backend.api.deps import SessionDep
from gamification_backend.api.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from gamification_backend.config import BackendSettings
from gamification_backend.db.models import UserRecord
from gamification_backend.repositories.users import UserRepository
from gamification_backend.security import (
    create_access_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_response(user: UserRecord, settings: BackendSettings) -> TokenResponse:
    token = create_access_token(
        user_id=user.id,
        is_admin=user.is_admin,
        secret=settings.jwt_secret,
        expires_minutes=settings.jwt_expires_minutes,
    )
    return TokenResponse(
        access_token=token,
        token_type="bearer",  # noqa: S106 (public token scheme, not a secret)
        user=UserResponse.model_validate(user),
    )


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterRequest, session: SessionDep, request: Request
) -> TokenResponse:
    """Create an account and return an access token for it."""

    settings: BackendSettings = request.app.state.settings
    repo = UserRepository(session)
    if repo.get_by_username(body.username) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu kullanıcı adı zaten alınmış.",
        )
    user = repo.create(
        username=body.username,
        password_hash=hash_password(body.password, settings.bcrypt_rounds),
        email=body.email,
    )
    return _token_response(user, settings)


@router.post("/login")
def login(body: LoginRequest, session: SessionDep, request: Request) -> TokenResponse:
    """Verify credentials and return an access token."""

    settings: BackendSettings = request.app.state.settings
    user = UserRepository(session).get_by_username(body.username)
    if (
        user is None
        or user.password_hash is None
        or not verify_password(body.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanıcı adı veya parola hatalı.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _token_response(user, settings)
