"""Unit tests for password hashing and JWT helpers."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from gamification_backend.security import (
    TokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

SECRET = "test-secret"  # noqa: S105


def test_password_hash_round_trip() -> None:
    hashed = hash_password("parola-123", rounds=4)

    assert hashed != "parola-123"
    assert verify_password("parola-123", hashed) is True
    assert verify_password("yanlis-parola", hashed) is False


def test_hashes_are_salted() -> None:
    first = hash_password("parola-123", rounds=4)
    second = hash_password("parola-123", rounds=4)

    assert first != second


def test_token_round_trip() -> None:
    token = create_access_token(
        user_id="u-abc", is_admin=True, secret=SECRET, expires_minutes=60
    )

    payload = decode_access_token(token, SECRET)

    assert payload.user_id == "u-abc"
    assert payload.is_admin is True


def test_expired_token_is_rejected() -> None:
    token = create_access_token(
        user_id="u-abc",
        is_admin=False,
        secret=SECRET,
        expires_minutes=60,
        now=datetime(2020, 1, 1, tzinfo=UTC),
    )

    with pytest.raises(TokenError):
        decode_access_token(token, SECRET)


def test_wrong_secret_is_rejected() -> None:
    token = create_access_token(
        user_id="u-abc", is_admin=False, secret=SECRET, expires_minutes=60
    )

    with pytest.raises(TokenError):
        decode_access_token(token, "other-secret")


def test_garbage_token_is_rejected() -> None:
    with pytest.raises(TokenError):
        decode_access_token("not-a-token", SECRET)


def test_token_without_subject_is_rejected() -> None:
    import jwt as pyjwt

    token = pyjwt.encode({"admin": True}, SECRET, algorithm="HS256")

    with pytest.raises(TokenError, match="subject"):
        decode_access_token(token, SECRET)
