"""Backend service settings.

All backend environment variables are read here and nowhere else, mirroring
the engine-side rule that ``config/llm_config.py`` is the single place LLM
environment variables are read. Backend variables use the
``GAMIFICATION_BACKEND_`` prefix so they cannot collide with the engine's
LLM variables (``GEMINI_API_KEY``, ``OPENAI_API_KEY``,
``GAMIFICATION_LLM_ENABLED``).
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[2]


class BackendSettings(BaseSettings):
    """Runtime configuration for the FastAPI service.

    Attributes:
        database_url: SQLAlchemy database URL. Defaults to a SQLite file in
            the repository root; tests override it with ``sqlite://``
            (in-memory).
        challenges_csv: Challenge definitions seeded into the database on
            startup when the file exists.
        seed_on_startup: Disable to skip challenge seeding (used by tests
            that want full control over database contents).
        jwt_secret: HS256 signing key for access tokens. The default is a
            development-only value; set a strong secret in production.
        jwt_expires_minutes: Access token lifetime.
        bcrypt_rounds: bcrypt cost factor (tests lower it for speed).
        admin_username / admin_password: when both are set, an admin
            account is bootstrapped on startup if it does not exist yet.
    """

    model_config = SettingsConfigDict(
        env_prefix="GAMIFICATION_BACKEND_",
        extra="ignore",
    )

    database_url: str = f"sqlite:///{(_REPO_ROOT / 'gamification.db').as_posix()}"
    challenges_csv: Path = _REPO_ROOT / "data" / "input" / "challenges.csv"
    seed_on_startup: bool = True
    jwt_secret: str = "change-me-dev-secret"  # noqa: S105 (dev default)
    jwt_expires_minutes: int = 60 * 24
    bcrypt_rounds: int = 12
    admin_username: str | None = None
    admin_password: str | None = None
