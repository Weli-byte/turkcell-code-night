"""CSV schema definitions for ingestion."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CsvSchema:
    """Expected CSV schema contract."""

    required_headers: frozenset[str]
    optional_headers: frozenset[str]

    @property
    def known_headers(self) -> frozenset[str]:
        """Return all headers known by the schema."""

        return self.required_headers | self.optional_headers


USER_ACTIVITY_SCHEMA = CsvSchema(
    required_headers=frozenset(
        {
            "user_id",
            "date",
            "shows_watched",
            "unique_genres",
            "watch_minutes",
            "episodes_completed",
            "watch_party_minutes",
            "ratings",
        }
    ),
    optional_headers=frozenset({"event_id"}),
)

CHALLENGE_DEFINITION_SCHEMA = CsvSchema(
    required_headers=frozenset(
        {
            "challenge_id",
            "challenge_name",
            "challenge_type",
            "condition",
            "reward_points",
            "priority",
            "is_active",
        }
    ),
    optional_headers=frozenset(),
)
