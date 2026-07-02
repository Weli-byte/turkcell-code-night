"""CSV loading functions for domain ingestion."""

from __future__ import annotations

import csv
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from gamification_engine.domain.errors import IngestionError
from gamification_engine.domain.models import ChallengeDefinition, UserActivity
from gamification_engine.ingestion.schemas import (
    CHALLENGE_DEFINITION_SCHEMA,
    USER_ACTIVITY_SCHEMA,
    CsvSchema,
)
from gamification_engine.ingestion.validators import (
    parse_challenge_definition_row,
    parse_user_activity_row,
    validate_headers,
    validate_unique_challenge_ids,
)

T = TypeVar("T")


def load_user_activities_csv(path: str | Path) -> list[UserActivity]:
    """Load and validate user activity CSV data.

    Output order is deterministic by activity date, user ID, and event ID.
    """

    activities = _load_csv_rows(
        path=path,
        schema=USER_ACTIVITY_SCHEMA,
        parser=parse_user_activity_row,
    )
    return sorted(
        activities,
        key=lambda activity: (
            activity.activity_date,
            activity.user_id,
            activity.event_id or "",
        ),
    )


def load_challenge_definitions_csv(path: str | Path) -> list[ChallengeDefinition]:
    """Load and validate challenge definition CSV data.

    Output order is deterministic by challenge ID.
    """

    challenges = _load_csv_rows(
        path=path,
        schema=CHALLENGE_DEFINITION_SCHEMA,
        parser=parse_challenge_definition_row,
    )
    validate_unique_challenge_ids(challenges)
    return sorted(challenges, key=lambda challenge: challenge.challenge_id)


def _load_csv_rows(
    path: str | Path,
    schema: CsvSchema,
    parser: Callable[[dict[str, str], int], T],
) -> list[T]:
    csv_path = Path(path)
    if not csv_path.is_file():
        raise IngestionError(f"CSV file does not exist: {csv_path}.")

    parsed_rows: list[T] = []
    try:
        with csv_path.open(newline="", encoding="utf-8-sig") as csv_file:
            reader = csv.DictReader(csv_file)
            validate_headers(reader.fieldnames, schema)
            for row_number, row in enumerate(reader, start=2):
                normalized_row = {
                    (key or "").strip(): (value or "").strip()
                    for key, value in row.items()
                }
                parsed_rows.append(parser(normalized_row, row_number))
    except OSError as exc:
        raise IngestionError(f"Could not read CSV file: {csv_path}.") from exc

    return parsed_rows
