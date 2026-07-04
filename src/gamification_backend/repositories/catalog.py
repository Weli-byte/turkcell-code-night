"""Catalog repository and JSON seeding for series/videos."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from gamification_backend.db.models import SeriesRecord, VideoRecord


def seed_catalog_from_json(session: Session, json_path: Path) -> tuple[int, int]:
    """Insert series/videos from the catalog file that are not yet present.

    Existing rows are left untouched so repeated startups are safe.
    Returns ``(series_inserted, videos_inserted)``.
    """

    data = json.loads(json_path.read_text(encoding="utf-8"))
    series_inserted = 0
    for entry in data.get("series", []):
        if session.get(SeriesRecord, entry["id"]) is not None:
            continue
        session.add(
            SeriesRecord(
                id=entry["id"],
                title=entry["title"],
                genre=entry["genre"],
                description=entry.get("description"),
            )
        )
        series_inserted += 1
    videos_inserted = 0
    for entry in data.get("videos", []):
        if session.get(VideoRecord, entry["id"]) is not None:
            continue
        session.add(
            VideoRecord(
                id=entry["id"],
                series_id=entry.get("series_id"),
                title=entry["title"],
                genre=entry["genre"],
                duration_seconds=entry["duration_seconds"],
                url=entry["url"],
                episode_number=entry.get("episode_number"),
            )
        )
        videos_inserted += 1
    session.commit()
    return series_inserted, videos_inserted


def list_series(session: Session) -> list[SeriesRecord]:
    """All series ordered by id."""

    stmt = select(SeriesRecord).order_by(SeriesRecord.id)
    return list(session.execute(stmt).scalars())


def list_videos(session: Session) -> list[VideoRecord]:
    """All videos ordered by id."""

    stmt = select(VideoRecord).order_by(VideoRecord.id)
    return list(session.execute(stmt).scalars())


def episodes_of(session: Session, series_id: str) -> list[VideoRecord]:
    """Episodes of a series ordered by episode number, then id."""

    stmt = (
        select(VideoRecord)
        .where(VideoRecord.series_id == series_id)
        .order_by(VideoRecord.episode_number, VideoRecord.id)
    )
    return list(session.execute(stmt).scalars())


def standalone_films(session: Session) -> list[VideoRecord]:
    """Videos without a series, ordered by id."""

    stmt = (
        select(VideoRecord)
        .where(VideoRecord.series_id.is_(None))
        .order_by(VideoRecord.id)
    )
    return list(session.execute(stmt).scalars())


def get_video(session: Session, video_id: str) -> VideoRecord | None:
    """Look up one video by id."""

    return session.get(VideoRecord, video_id)
