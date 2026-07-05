from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from api.auth_utils import verify_token
from database.setup import get_db
from engine.pipeline import run_pipeline
from datetime import datetime
import uuid
import threading

router = APIRouter(tags=["Watch"])


class StartBody(BaseModel):
    content_id: str


class EndBody(BaseModel):
    session_id: str


@router.post("/session/start")
def start_session(body: StartBody, token: dict = Depends(verify_token)):
    db = get_db()
    content = db.execute(
        "SELECT id, title, duration_minutes FROM content_catalog WHERE id = ?",
        (body.content_id,)
    ).fetchone()
    if not content:
        db.close()
        raise HTTPException(404, "Icerik bulunamadi")

    session_id = "sess_" + uuid.uuid4().hex[:16]
    db.execute("""
        INSERT INTO watch_sessions
        (id, user_id, content_id, started_at)
        VALUES (?, ?, ?, ?)
    """, (session_id, token["sub"],
          body.content_id, datetime.now().isoformat()))
    db.commit()
    db.close()

    return {
        "session_id": session_id,
        "content_id": body.content_id,
        "title":      content["title"],
        "started_at": datetime.now().isoformat(),
    }


@router.post("/session/end")
def end_session(body: EndBody, token: dict = Depends(verify_token)):
    db = get_db()
    session = db.execute("""
        SELECT ws.*, cc.duration_minutes, cc.title, cc.genre
        FROM watch_sessions ws
        JOIN content_catalog cc ON cc.id = ws.content_id
        WHERE ws.id = ? AND ws.user_id = ?
    """, (body.session_id, token["sub"])).fetchone()

    if not session:
        db.close()
        raise HTTPException(404, "Session bulunamadi")
    if session["ended_at"]:
        db.close()
        raise HTTPException(400, "Session zaten kapatildi")

    started  = datetime.fromisoformat(session["started_at"])
    ended    = datetime.now()
    real_min = (ended - started).total_seconds() / 60.0
    watch_min = min(real_min, float(session["duration_minutes"]))
    completed = 1 if real_min >= session["duration_minutes"] * 0.85 else 0
    today     = ended.strftime("%Y-%m-%d")

    db.execute("""
        UPDATE watch_sessions
        SET ended_at = ?, watch_minutes = ?, completed = ?
        WHERE id = ?
    """, (ended.isoformat(), watch_min, completed, body.session_id))

    # Gunluk cap kontrolu: ayni kullanici + ayni video + ayni gun
    already_today = db.execute("""
        SELECT COALESCE(SUM(ua.watch_minutes), 0) AS total
        FROM user_activities ua
        JOIN watch_sessions ws ON ws.id = ua.session_id
        WHERE ua.user_id = ?
          AND ua.activity_date = ?
          AND ws.content_id = ?
    """, (token["sub"], today, session["content_id"])).fetchone()

    max_allowed = float(session["duration_minutes"])
    already_min = float(already_today["total"])

    if already_min >= max_allowed:
        db.commit()
        db.close()
        return {
            "session_id":    body.session_id,
            "watch_minutes": round(watch_min, 1),
            "completed":     bool(completed),
            "activity_date": today,
            "message":       "Bu video bugun zaten tam izlendi, puan eklenmedi.",
            "capped":        True,
        }

    effective_minutes = min(watch_min, max_allowed - already_min)

    db.execute("""
        INSERT INTO user_activities
        (user_id, activity_date, watch_minutes,
         episodes_completed, genres_watched,
         watch_party_minutes, ratings_given,
         session_id, created_at)
        VALUES (?, ?, ?, ?, 1, 0, 0, ?, ?)
    """, (
        token["sub"], today,
        effective_minutes, completed,
        body.session_id, ended.isoformat()
    ))
    db.commit()
    db.close()

    def _run():
        try:
            run_pipeline(today)
        except Exception as e:
            print(f"[PIPELINE ERROR] {e}")

    threading.Thread(target=_run, daemon=True).start()

    return {
        "session_id":    body.session_id,
        "watch_minutes": round(effective_minutes, 1),
        "completed":     bool(completed),
        "activity_date": today,
        "message":       (
            f"{round(effective_minutes, 1)} dakika izlendi. "
            "Puanlar hesaplaniyor..."
        ),
        "capped":        False,
    }


@router.post("/session/heartbeat")
def heartbeat(body: EndBody, token: dict = Depends(verify_token)):
    """Frontend her 30 saniyede cagirir. Session aktifligini kaydeder."""
    db  = get_db()
    row = db.execute(
        "SELECT id FROM watch_sessions WHERE id = ? AND user_id = ? AND ended_at IS NULL",
        (body.session_id, token["sub"])
    ).fetchone()
    db.close()
    if not row:
        raise HTTPException(404, "Aktif session yok")
    return {"ok": True, "session_id": body.session_id}
