"""api/routers/events.py — Event Bus API'si."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from database.setup import get_db
from engine import event_bus
from api.auth_utils import verify_token

router = APIRouter(tags=["events"])

EVENT_TYPES = [
    "video_started",
    "video_progress",
    "video_ended",
    "challenge_completed",
    "badge_earned",
    "user_login",
]


class EventBody(BaseModel):
    event_type: str
    data: dict = {}


@router.post("/publish")
def publish_event(body: EventBody, token: dict = Depends(verify_token)):
    if body.event_type not in EVENT_TYPES:
        raise HTTPException(status_code=400, detail=f"Gecersiz event tipi: {body.event_type}")

    payload = dict(body.data)
    # user_id daima JWT'den gelir — istemci govdesindeki deger guvenilmez (spoof onlemi).
    payload["user_id"] = token["sub"]
    event_bus.publish(body.event_type, payload)

    # Audit kaydi
    db = get_db()
    try:
        db.execute(
            "INSERT INTO ai_calls_log "
            "(model, tokens_in, tokens_out, latency_ms, grounding_score, cost, "
            " user_id, intent, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            ("event_bus", 0, 0, 0, None, 0.0, token["sub"],
             f"event:{body.event_type}", datetime.now().isoformat()),
        )
        db.commit()
    finally:
        db.close()

    return {
        "event_type": body.event_type,
        "published": True,
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/types")
def event_types(token: dict = Depends(verify_token)):
    return {"event_types": EVENT_TYPES}
