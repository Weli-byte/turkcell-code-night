"""Tiny stdlib daily scheduler for the end-of-day batch.

Deliberately not APScheduler: an asyncio task sleeping until the next
configured time keeps the runtime dependency-free and fully typed. The job
callable is injected, which makes the loop trivially testable.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

logger = logging.getLogger(__name__)


def seconds_until_next_run(now: datetime, *, hour: int, minute: int) -> float:
    """Seconds from ``now`` until the next daily occurrence of hour:minute."""

    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


class DailyJobScheduler:
    """Runs a job once per day at a fixed UTC time until stopped."""

    def __init__(self, job: Callable[[], None], *, hour: int, minute: int) -> None:
        self._job = job
        self._hour = hour
        self._minute = minute
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        """Begin the schedule loop on the running event loop."""

        self._task = asyncio.get_running_loop().create_task(self._loop())

    async def stop(self) -> None:
        """Cancel the schedule loop and wait for it to finish."""

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
            delay = seconds_until_next_run(
                datetime.now(UTC), hour=self._hour, minute=self._minute
            )
            await asyncio.sleep(delay)
            try:
                await asyncio.to_thread(self._job)
            except Exception:
                logger.exception("Daily batch job failed; will retry tomorrow.")
