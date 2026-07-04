"""SQLAlchemy ORM models for the live gamification platform.

Schema notes:

- ``points_ledger`` is append-only. The application layer exposes no
  update/delete operations and :func:`gamification_backend.db.base.init_database`
  installs SQLite triggers that abort any ``UPDATE``/``DELETE`` on the table.
- Idempotency guards are database-level unique constraints:
  one ledger entry per ``(user_id, source_ref)`` and one badge per
  ``(user_id, badge_type)``.
- Enum-like columns store the string values of the engine's domain enums
  (``ChallengeType``, ``BadgeType`` etc.) so engine objects map 1:1.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    """Timezone-aware UTC timestamp for record bookkeeping columns."""

    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Declarative base for all backend tables."""


class UserRecord(Base):
    """A platform account (human, admin or simulator bot)."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(254))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_bot: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class ChallengeRecord(Base):
    """A configured challenge; conditions use the engine's safe parser syntax."""

    __tablename__ = "challenges"
    __table_args__ = (
        CheckConstraint("reward_points > 0", name="ck_challenge_points_positive"),
        CheckConstraint("priority > 0", name="ck_challenge_priority_positive"),
    )

    challenge_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    challenge_type: Mapped[str] = mapped_column(String(16))
    condition: Mapped[str] = mapped_column(String(255))
    reward_points: Mapped[int] = mapped_column(Integer)
    priority: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SeriesRecord(Base):
    """A show/series grouping catalog videos."""

    __tablename__ = "series"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    genre: Mapped[str] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text)


class VideoRecord(Base):
    """A single watchable catalog item (episode or standalone video)."""

    __tablename__ = "videos"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    series_id: Mapped[str | None] = mapped_column(ForeignKey("series.id"))
    title: Mapped[str] = mapped_column(String(200))
    genre: Mapped[str] = mapped_column(String(64))
    duration_seconds: Mapped[int] = mapped_column(Integer)
    url: Mapped[str] = mapped_column(String(500))
    episode_number: Mapped[int | None] = mapped_column(Integer)


class WatchEventRecord(Base):
    """A raw activity event reported by the player or the simulator."""

    __tablename__ = "watch_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    video_id: Mapped[str | None] = mapped_column(ForeignKey("videos.id"))
    event_type: Mapped[str] = mapped_column(String(16))
    event_date: Mapped[date] = mapped_column(Date, index=True)
    watch_seconds: Mapped[int] = mapped_column(Integer, default=0)
    episodes_completed: Mapped[int] = mapped_column(Integer, default=0)
    watch_party_seconds: Mapped[int] = mapped_column(Integer, default=0)
    rating_value: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class PointsLedgerRecord(Base):
    """One append-only point transaction.

    Never updated or deleted; enforced by application design and SQLite
    triggers (see ``base.init_database``).
    """

    __tablename__ = "points_ledger"
    __table_args__ = (
        UniqueConstraint("user_id", "source_ref", name="uq_ledger_user_source"),
        CheckConstraint("points_delta > 0", name="ck_ledger_delta_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ledger_id: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    points_delta: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(32))
    source_ref: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class RewardEventRecord(Base):
    """The selected daily reward for a user.

    ``UNIQUE(user_id, reward_date)`` enforces the engine's "one reward per
    user per day" rule at the database level, including under live
    (per-event) evaluation.
    """

    __tablename__ = "reward_events"
    __table_args__ = (
        UniqueConstraint("user_id", "reward_date", name="uq_reward_user_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reward_id: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    challenge_id: Mapped[str] = mapped_column(ForeignKey("challenges.challenge_id"))
    reward_points: Mapped[int] = mapped_column(Integer)
    reward_date: Mapped[date] = mapped_column(Date, index=True)
    suppressed_challenge_ids: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class BadgeRecord(Base):
    """An awarded badge; at most one per user and badge tier."""

    __tablename__ = "badges"
    __table_args__ = (
        UniqueConstraint("user_id", "badge_type", name="uq_badge_user_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    badge_type: Mapped[str] = mapped_column(String(16))
    awarded_at: Mapped[date] = mapped_column(Date)


class NotificationRecord(Base):
    """A generated notification record."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    notification_id: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    notification_type: Mapped[str] = mapped_column(String(32))
    channel: Mapped[str] = mapped_column(String(16))
    message: Mapped[str] = mapped_column(Text)
    source_ref: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class RunRecord(Base):
    """Bookkeeping for pipeline executions (live ticks and daily batches)."""

    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_date: Mapped[date] = mapped_column(Date, index=True)
    run_type: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16))
    executed_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    summary_json: Mapped[str | None] = mapped_column(Text)
