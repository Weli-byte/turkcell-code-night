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


class VideoResponse(BaseModel):
    """Public representation of a catalog video."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    series_id: str | None
    title: str
    genre: str
    duration_seconds: int
    url: str
    episode_number: int | None


class SeriesResponse(BaseModel):
    """A series with its episodes in watch order."""

    id: str
    title: str
    genre: str
    description: str | None
    episodes: list[VideoResponse]


class CatalogResponse(BaseModel):
    """The full catalog: series plus standalone films."""

    series: list[SeriesResponse]
    films: list[VideoResponse]


class HeartbeatRequest(BaseModel):
    """Watched seconds since the player's previous report (max 5 min)."""

    video_id: str
    watch_seconds: int = Field(gt=0, le=300)


class CompleteRequest(BaseModel):
    """The player finished a video/episode."""

    video_id: str


class RatingRequest(BaseModel):
    """A 1-5 star rating for a video."""

    video_id: str
    rating: int = Field(ge=1, le=5)


class WatchPartyRequest(BaseModel):
    """Watch-party seconds since the previous report (max 5 min)."""

    video_id: str
    party_seconds: int = Field(gt=0, le=300)


class EventResponse(BaseModel):
    """Ingestion result; ``counted=False`` means the event was ignored
    (duplicate or daily-cap exceeded), which is not an error."""

    status: str
    counted: bool
