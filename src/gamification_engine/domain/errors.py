"""Application-specific exception hierarchy.

The project uses explicit exception types so orchestration code can distinguish
between invalid inputs, invalid configuration, rule failures, and integrity
problems without relying on fragile message parsing.
"""


class GamificationEngineError(Exception):
    """Base class for all expected gamification engine errors."""


class DomainError(GamificationEngineError):
    """Raised when domain data violates business invariants."""


class IngestionError(GamificationEngineError):
    """Raised when input files cannot be parsed or validated."""


class ConfigurationError(GamificationEngineError):
    """Raised when engine configuration is missing or invalid."""


class RuleEvaluationError(GamificationEngineError):
    """Raised when a challenge rule cannot be parsed or evaluated safely."""


class IntegrityValidationError(GamificationEngineError):
    """Raised when generated outputs fail cross-file consistency checks."""
