"""Pydantic request/response schemas for the HTTP API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RegisterRequest(BaseModel):
    """Payload for creating a new account."""

    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=72)
    email: str | None = Field(default=None, max_length=254)


class LoginRequest(BaseModel):
    """Payload for username/password login."""

    username: str
    password: str


class UserResponse(BaseModel):
    """Public representation of an account."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    email: str | None
    is_admin: bool
    created_at: datetime


class TokenResponse(BaseModel):
    """Access token issued after register/login."""

    access_token: str
    token_type: str
    user: UserResponse
