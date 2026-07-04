"""FastAPI application factory.

Run the service with:

    uvicorn gamification_backend.main:app --reload

Startup initializes the database schema (including the append-only ledger
triggers) and seeds challenge definitions from the configured CSV.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.orm import Session, sessionmaker

from gamification_backend.api.admin import router as admin_router
from gamification_backend.api.auth import router as auth_router
from gamification_backend.api.health import router as health_router
from gamification_backend.api.me import router as me_router
from gamification_backend.config import BackendSettings
from gamification_backend.db.base import (
    create_db_engine,
    create_session_factory,
    init_database,
)
from gamification_backend.repositories.challenges import seed_challenges_from_csv
from gamification_backend.repositories.users import UserRepository
from gamification_backend.security import hash_password


def _bootstrap_admin(
    session_factory: sessionmaker[Session], settings: BackendSettings
) -> None:
    """Create the configured admin account once, if it does not exist."""

    if not settings.admin_username or not settings.admin_password:
        return
    with session_factory() as session:
        repo = UserRepository(session)
        if repo.get_by_username(settings.admin_username) is not None:
            return
        repo.create(
            username=settings.admin_username,
            password_hash=hash_password(
                settings.admin_password, settings.bcrypt_rounds
            ),
            is_admin=True,
        )


def create_app(settings: BackendSettings | None = None) -> FastAPI:
    """Build the FastAPI application with its database wiring."""

    app_settings = settings if settings is not None else BackendSettings()
    engine = create_db_engine(app_settings.database_url)
    session_factory = create_session_factory(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        init_database(engine)
        if app_settings.seed_on_startup and app_settings.challenges_csv.exists():
            with session_factory() as session:
                seed_challenges_from_csv(session, app_settings.challenges_csv)
        _bootstrap_admin(session_factory, app_settings)
        yield
        engine.dispose()

    app = FastAPI(
        title="Gamification Platform API",
        version="2.0.0",
        lifespan=lifespan,
    )
    app.state.settings = app_settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(me_router)
    app.include_router(admin_router)
    return app


app = create_app()
