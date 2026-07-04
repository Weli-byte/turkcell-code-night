"""Pydantic request/response schemas for the HTTP API."""

from __future__ import annotations

from datetime import date, datetime

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


class RewardInfo(BaseModel):
    """A reward granted by the live evaluation triggered by this event."""

    challenge_id: str
    challenge_name: str
    points: int


class EventResponse(BaseModel):
    """Ingestion result; ``counted=False`` means the event was ignored
    (duplicate or daily-cap exceeded), which is not an error. ``reward``
    and ``new_badges`` report anything granted by live evaluation."""

    status: str
    counted: bool
    reward: RewardInfo | None = None
    new_badges: list[str] = Field(default_factory=list)


class LedgerEntryResponse(BaseModel):
    """One append-only point transaction."""

    model_config = ConfigDict(from_attributes=True)

    ledger_id: str
    points_delta: int
    source: str
    source_ref: str
    created_at: datetime


class PointsResponse(BaseModel):
    """The user's point total with full transaction history."""

    total_points: int
    entries: list[LedgerEntryResponse]


class BadgeResponse(BaseModel):
    """An owned badge."""

    model_config = ConfigDict(from_attributes=True)

    badge_type: str
    awarded_at: date


class ChallengeProgressResponse(BaseModel):
    """An active challenge with the user's live progress toward it."""

    challenge_id: str
    name: str
    condition: str
    reward_points: int
    priority: int
    progress_current: int
    progress_target: int
    progress_percent: int
    satisfied: bool
    won_today: bool


class LeaderboardEntryResponse(BaseModel):
    """One ranked leaderboard row."""

    rank: int
    user_id: str
    username: str
    total_points: int
    badges: list[str]
    is_bot: bool


class RunResponse(BaseModel):
    """One recorded pipeline execution."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    run_date: date
    run_type: str
    status: str
    executed_at: datetime
    summary_json: str | None


class BatchRunRequest(BaseModel):
    """Manual batch trigger; defaults to today (UTC) when omitted."""

    run_date: date | None = None


class BatchRunSummaryResponse(BaseModel):
    """Outcome of a manual batch run."""

    run_date: date
    users_processed: int
    new_rewards: int
    new_badges: int
    new_notifications: int
    leaderboard_size: int


class NotificationResponse(BaseModel):
    """A stored notification."""

    model_config = ConfigDict(from_attributes=True)

    notification_id: str
    notification_type: str
    channel: str
    message: str
    source_ref: str
    created_at: datetime
