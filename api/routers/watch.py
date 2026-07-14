"""
api/routers/watch.py — gercek izleme oturumlari.

Sure GERCEK zamandan hesaplanir: (ended_at - started_at). Gunluk cap: ayni video
ayni gun toplamda video suresinden fazla sayilamaz. Bitiste event bus'a video_ended
yayinlanir ve pipeline arka planda calisir.
"""

import uuid
import threading
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from database.setup import get_db
from engine import event_bus
from engine.pipeline import run_pipeline
from api.auth_utils import verify_token

router = APIRouter(prefix="/api/watch", tags=["watch"])

DATE_FMT = "%Y-%m-%d"


class StartBody(BaseModel):
    content_id: str


class SessionBody(BaseModel):
    session_id: str


@router.post("/session/start")
def start_session(body: StartBody, token: dict = Depends(verify_token)):
    db = get_db()
    try:
        content = db.execute(
            "SELECT id, title, duration_minutes FROM content_catalog WHERE id=?",
            (body.content_id,),
        ).fetchone()
        if not content:
            raise HTTPException(status_code=404, detail="Video bulunamadi")

        session_id = "sess_" + uuid.uuid4().hex[:16]
        started_at = datetime.now().isoformat()
        db.execute(
            "INSERT INTO watch_sessions (id, user_id, content_id, started_at) "
            "VALUES (?,?,?,?)",
            (session_id, token["sub"], body.content_id, started_at),
        )
        db.commit()
    finally:
        db.close()

    return {
        "session_id": session_id,
        "content_id": content["id"],
        "title": content["title"],
        "started_at": started_at,
    }


@router.post("/session/end")
def end_session(body: SessionBody, token: dict = Depends(verify_token)):
    user_id = token["sub"]
    now = datetime.now()
    today = now.strftime(DATE_FMT)

    db = get_db()
    try:
        # ADIM 1 — Session dogrulama
        session = db.execute(
            "SELECT ws.id, ws.user_id, ws.content_id, ws.started_at, ws.ended_at, "
            "       cc.duration_minutes, cc.title "
            "FROM watch_sessions ws JOIN content_catalog cc ON cc.id = ws.content_id "
            "WHERE ws.id=?",
            (body.session_id,),
        ).fetchone()

        if not session:
            raise HTTPException(status_code=404, detail="Oturum bulunamadi")
        if session["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Bu oturum sana ait degil")
        if session["ended_at"]:
            raise HTTPException(status_code=400, detail="Session zaten kapatildi")

        # ADIM 2 — Gercek sure (started_at ile simdiki an arasindaki fark)
        started = datetime.fromisoformat(session["started_at"])
        real_min = (now - started).total_seconds() / 60.0
        duration = float(session["duration_minutes"])
        watch_min = min(real_min, duration)
        completed = 1 if real_min >= (duration * 0.85) else 0

        # ADIM 3 — Gunluk cap: ayni kullanici + ayni video + bugun
        already = db.execute(
            """
            SELECT COALESCE(SUM(ua.watch_minutes), 0) AS total
            FROM user_activities ua
            JOIN watch_sessions ws ON ws.id = ua.session_id
            WHERE ua.user_id=? AND ua.activity_date=? AND ws.content_id=?
            """,
            (user_id, today, session["content_id"]),
        ).fetchone()
        max_allowed = duration
        already_min = float(already["total"])

        if already_min >= max_allowed:
            # Cap: oturumu kapat, aktivite EKLEME, pipeline CALISTIRMA.
            db.execute(
                "UPDATE watch_sessions SET ended_at=?, watch_minutes=?, completed=? WHERE id=?",
                (now.isoformat(), watch_min, completed, body.session_id),
            )
            db.commit()
            return {
                "session_id": body.session_id,
                "watch_minutes": round(watch_min, 1),
                "completed": bool(completed),
                "activity_date": today,
                "capped": True,
                "message": "Bu video bugun tam izlendi, puan eklenmedi",
            }

        effective_minutes = min(watch_min, max_allowed - already_min)

        # ADIM 4 — DB'ye yaz
        db.execute(
            "UPDATE watch_sessions SET ended_at=?, watch_minutes=?, completed=? WHERE id=?",
            (now.isoformat(), watch_min, completed, body.session_id),
        )
        db.execute(
            """
            INSERT INTO user_activities
                (user_id, activity_date, watch_minutes, episodes_completed,
                 genres_watched, watch_party_minutes, ratings_given,
                 session_id, created_at)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (user_id, today, effective_minutes, completed, 1, 0, 0,
             body.session_id, now.isoformat()),
        )
        db.commit()
    finally:
        db.close()

    # ADIM 5 — Event Bus + arka planda pipeline
    event_bus.publish("video_ended", {
        "user_id": user_id,
        "content_id": session["content_id"],
        "watch_min": effective_minutes,
        "completed": bool(completed),
        "activity_date": today,
    })
    threading.Thread(target=lambda: run_pipeline(today), daemon=True).start()

    # ADIM 6 — Cevap
    return {
        "session_id": body.session_id,
        "watch_minutes": round(effective_minutes, 1),
        "completed": bool(completed),
        "activity_date": today,
        "capped": False,
        "message": f"{round(effective_minutes, 1)} dakika izlendi. Puanlar hesaplaniyor...",
    }


@router.post("/session/heartbeat")
def heartbeat(body: SessionBody, token: dict = Depends(verify_token)):
    db = get_db()
    try:
        row = db.execute(
            "SELECT id FROM watch_sessions WHERE id=? AND user_id=? AND ended_at IS NULL",
            (body.session_id, token["sub"]),
        ).fetchone()
    finally:
        db.close()

    if not row:
        raise HTTPException(status_code=404, detail="Aktif oturum bulunamadi")
    return {"ok": True, "session_id": body.session_id}
