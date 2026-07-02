"""Tests for the domain exception hierarchy."""

from gamification_engine.domain.errors import (
    ConfigurationError,
    DomainError,
    GamificationEngineError,
    IngestionError,
    IntegrityValidationError,
    RuleEvaluationError,
)


def test_expected_errors_share_base_type() -> None:
    """All expected application errors should be catchable by one base type."""

    error_types = [
        DomainError,
        IngestionError,
        ConfigurationError,
        RuleEvaluationError,
        IntegrityValidationError,
    ]

    for error_type in error_types:
        assert issubclass(error_type, GamificationEngineError)

