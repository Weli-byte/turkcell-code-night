"""Server-Sent Events stream for live notifications.

Browsers' ``EventSource`` cannot set headers, so the access token is passed
as a query parameter instead of the Authorization header.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from queue import Empty

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from gamification_backend.security import TokenError, decode_access_token
from gamification_backend.services.notifier import NotificationBroker, format_sse

_POLL_SECONDS = 0.25
_KEEPALIVE_SECONDS = 15.0

router = APIRouter(tags=["sse"])


@router.get("/sse/notifications")
async def notifications_stream(request: Request, token: str) -> StreamingResponse:
    """Stream the authenticated user's notifications as SSE events."""

    try:
        payload = decode_access_token(token, request.app.state.settings.jwt_secret)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz veya süresi dolmuş token.",
        ) from exc
    broker: NotificationBroker = request.app.state.broker

    async def stream() -> AsyncIterator[str]:
        subscription_id, queue = broker.subscribe(payload.user_id)
        try:
            yield ": connected\n\n"
            idle_seconds = 0.0
            while not await request.is_disconnected():
                try:
                    item = queue.get_nowait()
                except Empty:
                    await asyncio.sleep(_POLL_SECONDS)
                    idle_seconds += _POLL_SECONDS
                    if idle_seconds >= _KEEPALIVE_SECONDS:
                        idle_seconds = 0.0
                        yield ": keepalive\n\n"
                    continue
                idle_seconds = 0.0
                yield format_sse(item)
        finally:
            broker.unsubscribe(subscription_id)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
