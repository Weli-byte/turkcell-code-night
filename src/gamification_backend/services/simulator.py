"""Live traffic simulator: persona-driven bots that play the platform.

Bots go through the exact same ingestion path as the real player
(``EventRepository`` guards + ``evaluate_user_live``), so daily caps,
dedupe rules and live rewards all apply to them identically.

Randomness note: the engine forbids randomness in business decisions; a
traffic *generator* is inherently random, so it uses a dedicated seeded
``random.Random`` instance — the same seed replays the same traffic, and
engine outputs stay deterministic for any given event set.
"""

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

from gamification_backend.repositories.catalog import list_videos
from gamification_backend.repositories.events import EventRepository, today_utc
from gamification_backend.repositories.users import UserRepository
from gamification_backend.services.live_evaluator import evaluate_user_live

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BotPersona:
    """Behavioral profile for a simulated viewer."""

    key: str
    watch_probability: float
    watch_seconds_range: tuple[int, int]
    complete_probability: float
    rating_probability: float


PERSONAS: tuple[BotPersona, ...] = (
    BotPersona("binge", 1.0, (180, 300), 0.5, 0.1),
    BotPersona("gundelik", 0.6, (30, 120), 0.2, 0.1),
    BotPersona("elestirmen", 0.4, (60, 180), 0.3, 0.6),
)


@dataclass(frozen=True)
class SimulatorState:
    """Snapshot of the simulator's current state."""

    running: bool
    bot_count: int
    tick_seconds: float
    ticks_completed: int
    events_recorded: int


class TrafficSimulator:
    """Persona bots emitting activity events on a fixed tick."""

    def __init__(
        self, session_factory: sessionmaker[Session], *, seed: int = 1453
    ) -> None:
        self._session_factory = session_factory
        self._rng = random.Random(seed)  # noqa: S311 (reproducible traffic, not crypto)
        self._task: asyncio.Task[None] | None = None
        self._bots: list[tuple[str, BotPersona]] = []
        self._tick_seconds = 5.0
        self._ticks_completed = 0
        self._events_recorded = 0

    @property
    def running(self) -> bool:
        """Whether the tick loop is active."""

        return self._task is not None and not self._task.done()

    def status(self) -> SimulatorState:
        """Current counters and configuration."""

        return SimulatorState(
            running=self.running,
            bot_count=len(self._bots),
            tick_seconds=self._tick_seconds,
            ticks_completed=self._ticks_completed,
            events_recorded=self._events_recorded,
        )

    def ensure_bots(self, count: int) -> None:
        """Create (or reuse) ``count`` bot accounts and cache their ids."""

        self._bots = []
        with self._session_factory() as session:
            repo = UserRepository(session)
            for index in range(count):
                persona = PERSONAS[index % len(PERSONAS)]
                username = f"sim-{persona.key}-{index + 1}"
                user = repo.get_by_username(username)
                if user is None:
                    user = repo.create(
                        username=username, password_hash=None, is_bot=True
                    )
                self._bots.append((user.id, persona))

    async def start(self, *, bot_count: int, tick_seconds: float) -> bool:
        """Begin emitting traffic; returns False when already running."""

        if self.running:
            return False
        self._tick_seconds = tick_seconds
        await asyncio.to_thread(self.ensure_bots, bot_count)
        self._task = asyncio.get_running_loop().create_task(self._loop())
        return True

    async def stop(self) -> None:
        """Stop the tick loop (idempotent)."""

        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _loop(self) -> None:
        while True:
            try:
                await asyncio.to_thread(self._tick)
            except Exception:
                logger.exception("Simulator tick failed; continuing.")
            await asyncio.sleep(self._tick_seconds)

    def _tick(self) -> None:
        """One round: every bot may watch/complete/rate, then is evaluated."""

        with self._session_factory() as session:
            videos = list_videos(session)
            if not videos:
                return
            today = today_utc()
            repo = EventRepository(session)
            for user_id, persona in self._bots:
                if self._rng.random() > persona.watch_probability:
                    continue
                video = self._rng.choice(videos)
                low, high = persona.watch_seconds_range
                seconds = min(self._rng.randint(low, high), 300)
                if repo.record_heartbeat(
                    user_id=user_id,
                    video=video,
                    watch_seconds=seconds,
                    event_date=today,
                ):
                    self._events_recorded += 1
                if self._rng.random() < persona.complete_probability:
                    if repo.record_complete(
                        user_id=user_id, video=video, event_date=today
                    ):
                        self._events_recorded += 1
                if self._rng.random() < persona.rating_probability:
                    if repo.record_rating(
                        user_id=user_id,
                        video=video,
                        rating=self._rng.randint(1, 5),
                        event_date=today,
                    ):
                        self._events_recorded += 1
                evaluate_user_live(session, user_id=user_id, event_date=today)
            self._ticks_completed += 1
