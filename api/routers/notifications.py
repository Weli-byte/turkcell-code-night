"""
Bildirim API'si.
GET  /api/notifications/stream        → SSE EventSource bağlantısı
GET  /api/notifications/list          → Kalıcı bildirim geçmişi (DB)
GET  /api/notifications/unread-count  → Okunmamış sayısı (DB)
POST /api/notifications/read          → Okundu işaretle (ids veya all)
GET  /api/notifications/count         → In-memory kuyruk (polling fallback)
"""

import json
import time
from typing import Optional

import jwt
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.auth_utils import verify_token, SECRET, ALGORITHM
from api.notifications_store import pop_notifications, peek_count
from database.setup import get_db

router = APIRouter(tags=["Notifications"])


class ReadBody(BaseModel):
    ids: Optional[list[int]] = None
    all: bool = False

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


@router.get("/list")
def notification_list(
    limit: int = Query(30, ge=1, le=100),
    unread_only: bool = Query(False),
    token: dict = Depends(verify_token),
):
    """Kalıcı bildirim geçmişi — bildirim merkezi paneli için."""
    db    = get_db()
    query = ("SELECT id, type, title, message, is_read, created_at "
             "FROM notifications WHERE user_id=?")
    args: list = [token["sub"]]
    if unread_only:
        query += " AND is_read=0"
    query += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    rows = db.execute(query, args).fetchall()
    db.close()
    return {
        "notifications": [
            dict(r) | {"is_read": bool(r["is_read"])} for r in rows
        ],
    }


@router.get("/unread-count")
def unread_count(token: dict = Depends(verify_token)):
    """DB'deki okunmamış bildirim sayısı — sayfa yenilense de korunur."""
    db  = get_db()
    row = db.execute(
        "SELECT COUNT(*) AS c FROM notifications WHERE user_id=? AND is_read=0",
        (token["sub"],),
    ).fetchone()
    db.close()
    return {"count": int(row["c"])}


@router.post("/read")
def mark_read(body: ReadBody, token: dict = Depends(verify_token)):
    """Bildirimleri okundu işaretle: ids listesi veya all=true."""
    db = get_db()
    if body.all:
        cur = db.execute(
            "UPDATE notifications SET is_read=1 WHERE user_id=? AND is_read=0",
            (token["sub"],),
        )
    elif body.ids:
        marks = ",".join("?" for _ in body.ids)
        cur = db.execute(
            f"UPDATE notifications SET is_read=1 "
            f"WHERE user_id=? AND id IN ({marks})",
            [token["sub"], *body.ids],
        )
    else:
        db.close()
        raise HTTPException(422, "ids veya all=true gerekli")
    db.commit()
    updated = cur.rowcount
    db.close()
    return {"ok": True, "marked": updated}


@router.get("/count")
def notification_count(token: dict = Depends(verify_token)):
    """Polling fallback — SSE desteklenmeyen ortamlar için."""
    return {"count": peek_count(token["sub"])}


@router.get("/count-sse")
def notification_count_sse(token: str = Query(...)):
    """Query token ile count — SSE desteksiz istemciler için."""
    payload = _decode_query_token(token)
    return {"count": peek_count(payload["sub"])}
