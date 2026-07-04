"""Shared FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from gamification_backend.db.models import UserRecord
from gamification_backend.security import TokenError, decode_access_token

_bearer_scheme = HTTPBearer(auto_error=False)


def get_session(request: Request) -> Iterator[Session]:
    """Yield a database session from the application's session factory."""

    session: Session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


SessionDep = Annotated[Session, Depends(get_session)]

_CredentialsDep = Annotated[
    HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)
]


def get_current_user(
    request: Request, session: SessionDep, credentials: _CredentialsDep
) -> UserRecord:
    """Resolve the authenticated user from the Bearer token."""

    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Kimlik doğrulama gerekli.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        payload = decode_access_token(
            credentials.credentials, request.app.state.settings.jwt_secret
        )
    except TokenError as exc:
        raise unauthorized from exc
    user = session.get(UserRecord, payload.user_id)
    if user is None:
        raise unauthorized
    return user


CurrentUserDep = Annotated[UserRecord, Depends(get_current_user)]


def get_current_admin(user: CurrentUserDep) -> UserRecord:
    """Require the authenticated user to have the admin role."""

    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu işlem yönetici yetkisi gerektirir.",
        )
    return user


AdminDep = Annotated[UserRecord, Depends(get_current_admin)]
