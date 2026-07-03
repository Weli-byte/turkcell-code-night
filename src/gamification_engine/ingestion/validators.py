"""Validation and row parsing helpers for CSV ingestion."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date

from gamification_engine.domain.enums import ChallengeType
from gamification_engine.domain.errors import DomainError, IngestionError
from gamification_engine.domain.models import ChallengeDefinition, UserActivity
from gamification_engine.ingestion.schemas import CsvSchema

CsvRow = Mapping[str, str]


def validate_headers(headers: Sequence[str] | None, schema: CsvSchema) -> None:
    """Validate that a CSV file contains required headers.

    Args:
        headers: Headers returned by ``csv.DictReader``.
        schema: Expected schema.

    Raises:
        IngestionError: If the file has no header row or required columns are
            missing.
    """

    if headers is None:
        raise IngestionError("CSV file is missing a header row.")

    normalized_headers = {header.strip() for header in headers if header.strip()}
    missing_headers = sorted(schema.required_headers - normalized_headers)
    if missing_headers:
        joined = ", ".join(missing_headers)
        raise IngestionError(f"CSV file is missing required headers: {joined}.")


def parse_user_activity_row(row: CsvRow, row_number: int) -> UserActivity:
    """Parse one user activity CSV row into a domain model."""

    try:
        return UserActivity(
            event_id=_optional_text(row, "event_id"),
            user_id=_required_text(row, "user_id"),
            activity_date=_parse_date(_required_text(row, "date"), "date"),
            shows_watched=_parse_pipe_list(row.get("shows_watched", "")),
            unique_genres=_parse_non_negative_int(row, "unique_genres"),
            watch_minutes=_parse_non_negative_int(row, "watch_minutes"),
            episodes_completed=_parse_non_negative_int(row, "episodes_completed"),
            watch_party_minutes=_parse_non_negative_int(row, "watch_party_minutes"),
            ratings_given=_parse_non_negative_int(row, "ratings"),
        )
    except (DomainError, ValueError) as exc:
        raise IngestionError(f"Invalid user activity row {row_number}: {exc}") from exc


def parse_challenge_definition_row(
    row: CsvRow,
    row_number: int,
) -> ChallengeDefinition:
    """Parse one challenge definition CSV row into a domain model."""

    try:
        return ChallengeDefinition(
            challenge_id=_required_text(row, "challenge_id"),
            name=_required_text(row, "challenge_name"),
            challenge_type=_parse_challenge_type(_required_text(row, "challenge_type")),
            condition=_required_text(row, "condition"),
            reward_points=_parse_positive_int(row, "reward_points"),
            priority=_parse_positive_int(row, "priority"),
            is_active=_parse_bool(_required_text(row, "is_active"), "is_active"),
        )
    except (DomainError, ValueError) as exc:
        raise IngestionError(
            f"Invalid challenge definition row {row_number}: {exc}"
        ) from exc


def validate_unique_challenge_ids(challenges: Sequence[ChallengeDefinition]) -> None:
    """Ensure challenge IDs are unique."""

    seen: set[str] = set()
    duplicates: set[str] = set()
    for challenge in challenges:
        if challenge.challenge_id in seen:
            duplicates.add(challenge.challenge_id)
        seen.add(challenge.challenge_id)

    if duplicates:
        joined = ", ".join(sorted(duplicates))
        raise IngestionError(f"Duplicate challenge_id values found: {joined}.")


def _required_text(row: CsvRow, field_name: str) -> str:
    value = row.get(field_name)
    if value is None or not value.strip():
        raise ValueError(f"{field_name} must not be empty.")
    return value.strip()


def _optional_text(row: CsvRow, field_name: str) -> str | None:
    value = row.get(field_name)
    if value is None or not value.strip():
        return None
    return value.strip()


def _parse_date(value: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must use YYYY-MM-DD format.") from exc


def _parse_non_negative_int(row: CsvRow, field_name: str) -> int:
    value = _parse_int(_required_text(row, field_name), field_name)
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative.")
    return value


def _parse_positive_int(row: CsvRow, field_name: str) -> int:
    value = _parse_int(_required_text(row, field_name), field_name)
    if value <= 0:
        raise ValueError(f"{field_name} must be positive.")
    return value


def _parse_int(value: str, field_name: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an integer.") from exc


def _parse_bool(value: str, field_name: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "y"}:
        return True
    if normalized in {"false", "0", "no", "n"}:
        return False
    raise ValueError(f"{field_name} must be a boolean value.")


def _parse_challenge_type(value: str) -> ChallengeType:
    try:
        return ChallengeType(value.strip().upper())
    except ValueError as exc:
        allowed = ", ".join(challenge_type.value for challenge_type in ChallengeType)
        raise ValueError(f"challenge_type must be one of: {allowed}.") from exc


def _parse_pipe_list(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split("|") if item.strip())
