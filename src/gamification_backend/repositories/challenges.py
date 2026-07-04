"""Challenge repository and CSV seeding.

Seeding reuses the engine's strict CSV loader so database challenges pass
exactly the same validation (safe condition syntax, positive points and
priority) as the batch pipeline's input.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from gamification_backend.db.models import ChallengeRecord
from gamification_engine.ingestion.csv_loader import load_challenge_definitions_csv


def seed_challenges_from_csv(session: Session, csv_path: Path) -> int:
    """Insert challenges from the CSV that are not yet in the database.

    Existing rows are left untouched (admin edits win over the seed file),
    so calling this on every startup is safe. Returns the number of newly
    inserted challenges.
    """

    definitions = load_challenge_definitions_csv(csv_path)
    inserted = 0
    for definition in definitions:
        if session.get(ChallengeRecord, definition.challenge_id) is not None:
            continue
        session.add(
            ChallengeRecord(
                challenge_id=definition.challenge_id,
                name=definition.name,
                challenge_type=definition.challenge_type.value,
                condition=definition.condition,
                reward_points=definition.reward_points,
                priority=definition.priority,
                is_active=definition.is_active,
            )
        )
        inserted += 1
    session.commit()
    return inserted


def list_active_challenges(session: Session) -> list[ChallengeRecord]:
    """Active challenges ordered deterministically (priority, then id)."""

    stmt = (
        select(ChallengeRecord)
        .where(ChallengeRecord.is_active.is_(True))
        .order_by(ChallengeRecord.priority, ChallengeRecord.challenge_id)
    )
    return list(session.execute(stmt).scalars())
