"""Password hashing and JWT access-token helpers.

Kept free of FastAPI imports so the primitives are trivially unit-testable;
HTTP wiring lives in ``api/deps.py`` and ``api/auth.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

_JWT_ALGORITHM = "HS256"


class TokenError(Exception):
    """Raised when an access token is invalid, expired or malformed."""


@dataclass(frozen=True)
class TokenPayload:
    """Verified claims extracted from an access token."""

    user_id: str
    is_admin: bool


def hash_password(password: str, rounds: int = 12) -> str:
    """Hash a password with bcrypt using the given cost factor."""

    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds))
    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Check a candidate password against a stored bcrypt hash."""

    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(
    *,
    user_id: str,
    is_admin: bool,
    secret: str,
    expires_minutes: int,
    now: datetime | None = None,
) -> str:
    """Create a signed HS256 access token for the given user.

    ``now`` is injectable for tests; production callers omit it.
    """

    issued_at = now if now is not None else datetime.now(UTC)
    payload = {
        "sub": user_id,
        "admin": is_admin,
        "iat": int(issued_at.timestamp()),
        "exp": int((issued_at + timedelta(minutes=expires_minutes)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=_JWT_ALGORITHM)


def decode_access_token(token: str, secret: str) -> TokenPayload:
    """Verify a token's signature and expiry and return its claims.

    Raises TokenError for any invalid token (bad signature, expired,
    malformed, missing subject).
    """

    try:
        data = jwt.decode(token, secret, algorithms=[_JWT_ALGORITHM])
    except jwt.InvalidTokenError as exc:
        msg = "Invalid or expired access token"
        raise TokenError(msg) from exc
    subject = data.get("sub")
    if not isinstance(subject, str) or not subject:
        msg = "Access token has no subject"
        raise TokenError(msg)
    return TokenPayload(user_id=subject, is_admin=bool(data.get("admin", False)))
