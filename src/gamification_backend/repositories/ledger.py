"""Append-only points ledger repository.

By design this repository exposes no update or delete operations — the
class simply has no such methods, and the database backs this up with
SQLite triggers (see ``db/base.py``) plus a unique ``(user_id, source_ref)``
constraint that makes reward writes idempotent.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from gamification_backend.db.models import PointsLedgerRecord


class AppendOnlyLedgerRepository:
    """Insert-only access to the ``points_ledger`` table."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def append(
        self,
        *,
        ledger_id: str,
        user_id: str,
        points_delta: int,
        source: str,
        source_ref: str,
        created_at: datetime,
    ) -> bool:
        """Insert one ledger entry.

        Returns True when the entry was written, False when an entry with
        the same ``(user_id, source_ref)`` already exists (idempotent
        re-delivery of the same reward). Raises ValueError for a
        non-positive delta before touching the database.
        """

        if points_delta <= 0:
            msg = f"points_delta must be positive, got {points_delta}"
            raise ValueError(msg)
        if self._exists(user_id=user_id, source_ref=source_ref):
            return False
        record = PointsLedgerRecord(
            ledger_id=ledger_id,
            user_id=user_id,
            points_delta=points_delta,
            source=source,
            source_ref=source_ref,
            created_at=created_at,
        )
        self._session.add(record)
        try:
            self._session.commit()
        except IntegrityError:
            # Concurrent writer inserted the same (user_id, source_ref)
            # between our existence check and the commit.
            self._session.rollback()
            return False
        return True

    def total_points(self, user_id: str) -> int:
        """Sum of all point deltas for the user (0 when no entries)."""

        total = func.coalesce(func.sum(PointsLedgerRecord.points_delta), 0)
        stmt = select(total).where(PointsLedgerRecord.user_id == user_id)
        return int(self._session.execute(stmt).scalar_one())

    def entries_for_user(self, user_id: str) -> list[PointsLedgerRecord]:
        """All entries for the user in insertion order."""

        stmt = (
            select(PointsLedgerRecord)
            .where(PointsLedgerRecord.user_id == user_id)
            .order_by(PointsLedgerRecord.id)
        )
        return list(self._session.execute(stmt).scalars())

    def _exists(self, *, user_id: str, source_ref: str) -> bool:
        stmt = select(PointsLedgerRecord.id).where(
            PointsLedgerRecord.user_id == user_id,
            PointsLedgerRecord.source_ref == source_ref,
        )
        return self._session.execute(stmt).first() is not None
