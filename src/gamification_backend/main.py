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
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, sessionmaker

from gamification_backend.api.admin import router as admin_router
from gamification_backend.api.auth import router as auth_router
from gamification_backend.api.catalog import router as catalog_router
from gamification_backend.api.events import router as events_router
from gamification_backend.api.health import router as health_router
from gamification_backend.api.leaderboard import router as leaderboard_router
from gamification_backend.api.me import router as me_router
from gamification_backend.api.sse import router as sse_router
from gamification_backend.config import BackendSettings
from gamification_backend.db.base import (
    create_db_engine,
    create_session_factory,
    init_database,
)
from gamification_backend.repositories.catalog import seed_catalog_from_json
from gamification_backend.repositories.challenges import seed_challenges_from_csv
from gamification_backend.repositories.events import today_utc
from gamification_backend.repositories.users import UserRepository
from gamification_backend.security import hash_password
from gamification_backend.services.daily_batch import run_daily_batch
from gamification_backend.services.notifier import NotificationBroker
from gamification_backend.services.scheduler import DailyJobScheduler


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

    def _batch_job() -> None:
        with session_factory() as session:
            run_daily_batch(session, run_date=today_utc())

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        init_database(engine)
        if app_settings.seed_on_startup:
            with session_factory() as session:
                if app_settings.challenges_csv.exists():
                    seed_challenges_from_csv(session, app_settings.challenges_csv)
                if app_settings.catalog_json.exists():
                    seed_catalog_from_json(session, app_settings.catalog_json)
        _bootstrap_admin(session_factory, app_settings)
        scheduler: DailyJobScheduler | None = None
        if app_settings.scheduler_enabled:
            scheduler = DailyJobScheduler(
                _batch_job,
                hour=app_settings.batch_hour,
                minute=app_settings.batch_minute,
            )
            scheduler.start()
        app.state.scheduler = scheduler
        yield
        if scheduler is not None:
            await scheduler.stop()
        engine.dispose()

    app = FastAPI(
        title="Gamification Platform API",
        version="2.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origin_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.settings = app_settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.broker = NotificationBroker()
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(me_router)
    app.include_router(admin_router)
    app.include_router(catalog_router)
    app.include_router(events_router)
    app.include_router(sse_router)
    app.include_router(leaderboard_router)
    return app


app = create_app()
