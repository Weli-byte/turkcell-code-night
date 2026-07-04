"""User account repository."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from gamification_backend.db.models import UserRecord


class UserRepository:
    """Create and look up platform accounts."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        username: str,
        password_hash: str | None,
        email: str | None = None,
        is_admin: bool = False,
        is_bot: bool = False,
    ) -> UserRecord:
        """Insert a new user with a generated id and return it."""

        user = UserRecord(
            id=f"u-{uuid4().hex[:12]}",
            username=username,
            email=email,
            password_hash=password_hash,
            is_admin=is_admin,
            is_bot=is_bot,
        )
        self._session.add(user)
        self._session.commit()
        return user

    def get_by_username(self, username: str) -> UserRecord | None:
        """Look up a user by unique username."""

        stmt = select(UserRecord).where(UserRecord.username == username)
        return self._session.execute(stmt).scalar_one_or_none()

    def get_by_id(self, user_id: str) -> UserRecord | None:
        """Look up a user by primary key."""

        return self._session.get(UserRecord, user_id)
