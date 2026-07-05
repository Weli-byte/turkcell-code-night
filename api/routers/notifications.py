"""
SSE (Server-Sent Events) bildirim akışı.
GET /api/notifications/stream  → EventSource bağlantısı
GET /api/notifications/count   → Bekleyen bildirim sayısı (polling fallback)
"""

import json
import time

import jwt
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse

from api.auth_utils import verify_token, SECRET, ALGORITHM
from api.notifications_store import pop_notifications, peek_count

router = APIRouter(tags=["Notifications"])

_POLL_INTERVAL = 1.5   # saniye
_HEARTBEAT_SEC = 20    # SSE keep-alive ping aralığı
_MAX_DURATION  = 300   # bağlantı en fazla 5 dakika açık kalır


def _decode_query_token(token: str) -> dict:
    """EventSource query param token doğrulama."""
    try:
        return jwt.decode(token, SECRET, algorithms=[ALGORITHM])
    except Exception:
        raise HTTPException(401, "Gecersiz token")


@router.get("/stream")
def notification_stream(token: str = Query(...)):
    """
    EventSource endpoint. text/event-stream formatında bildirim iter.
    Frontend her event'i JSON parse eder.
    Token query param olarak alınır (EventSource header gönderemez).
    """
    payload = _decode_query_token(token)
    user_id = payload["sub"]

    def event_generator():
        # Bağlantı onayı
        yield f"data: {json.dumps({'type': 'connected', 'user_id': user_id})}\n\n"

        deadline  = time.time() + _MAX_DURATION
        last_ping = time.time()

        while time.time() < deadline:
            notifs = pop_notifications(user_id)
            for n in notifs:
                yield f"data: {json.dumps(n)}\n\n"

            # Keep-alive ping
            if time.time() - last_ping >= _HEARTBEAT_SEC:
                yield ": ping\n\n"
                last_ping = time.time()

            time.sleep(_POLL_INTERVAL)

        # Bağlantı süre doldu — client yeniden bağlanır
        yield f"data: {json.dumps({'type': 'reconnect'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":       "keep-alive",
        },
    )


@router.get("/count")
def notification_count(token: dict = Depends(verify_token)):
    """Polling fallback — SSE desteklenmeyen ortamlar için."""
    return {"count": peek_count(token["sub"])}


@router.get("/count-sse")
def notification_count_sse(token: str = Query(...)):
    """Query token ile count — SSE desteksiz istemciler için."""
    payload = _decode_query_token(token)
    return {"count": peek_count(payload["sub"])}
