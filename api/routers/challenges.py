from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from api.auth_utils import verify_token, require_admin
from database.setup import get_db
from engine.state_builder import build_user_state
from engine.condition_parser import parse_condition, get_progress, ALLOWED_FIELDS
from engine.ledger import already_rewarded
from datetime import datetime
import uuid

router = APIRouter(tags=["Challenges"])


def _validate_condition(condition: str) -> None:
    """Boş bir state ile koşulu doğrula — eval kullanılmaz."""
    empty_state = {f: 0 for f in ALLOWED_FIELDS}
    try:
        parse_condition(condition, empty_state)
    except ValueError as exc:
        raise HTTPException(422, f"Geçersiz koşul: {exc}") from exc


class ChallengeCreate(BaseModel):
    name:          str   = Field(..., min_length=2, max_length=100)
    condition:     str   = Field(..., min_length=5, max_length=200)
    reward_points: int   = Field(..., ge=1, le=10000)
    priority:      int   = Field(default=5, ge=1, le=20)
    is_active:     bool  = True


class ChallengeUpdate(BaseModel):
    name:          Optional[str]  = Field(None, min_length=2, max_length=100)
    condition:     Optional[str]  = Field(None, min_length=5, max_length=200)
    reward_points: Optional[int]  = Field(None, ge=1, le=10000)
    priority:      Optional[int]  = Field(None, ge=1, le=20)
    is_active:     Optional[bool] = None


@router.get("/active")
def active_challenges(token: dict = Depends(verify_token)):
    db    = get_db()
    today = datetime.now().strftime("%Y-%m-%d")
    chs   = db.execute(
        "SELECT * FROM challenges WHERE is_active = 1 ORDER BY priority DESC"
    ).fetchall()
    db.close()

    state  = build_user_state(token["sub"], today)
    result = []

    for ch in chs:
        try:
            passed = parse_condition(ch["condition"], state)
        except ValueError:
            passed = False

        prog     = get_progress(ch["condition"], state)
        rewarded = already_rewarded(token["sub"], ch["id"], today)

        result.append({
            "id":             ch["id"],
            "name":           ch["name"],
            "condition":      ch["condition"],
            "reward_points":  ch["reward_points"],
            "priority":       ch["priority"],
            "is_active":      bool(ch["is_active"]),
            "passed":         passed,
            "rewarded_today": rewarded,
            "current_value":  prog["current"],
            "target_value":   prog["target"],
            "percentage":     prog["percentage"],
        })

    return result


# ── Admin CRUD ─────────────────────────────────────────────────

@router.get("/all")
def all_challenges(token: dict = Depends(verify_token)):
    """Tüm challengelar (aktif+pasif) — admin görünümü."""
    require_admin(token)
    db   = get_db()
    rows = db.execute("SELECT * FROM challenges ORDER BY priority DESC").fetchall()
    db.close()
    return [dict(r) | {"is_active": bool(r["is_active"])} for r in rows]


@router.post("/")
def create_challenge(body: ChallengeCreate, token: dict = Depends(verify_token)):
    require_admin(token)
    _validate_condition(body.condition)
    ch_id = "c_" + uuid.uuid4().hex[:10]
    db    = get_db()
    db.execute(
        "INSERT INTO challenges (id, name, condition, reward_points, priority, is_active) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (ch_id, body.name, body.condition, body.reward_points, body.priority, int(body.is_active)),
    )
    db.commit()
    row = db.execute("SELECT * FROM challenges WHERE id=?", (ch_id,)).fetchone()
    db.close()
    return dict(row) | {"is_active": bool(row["is_active"])}


@router.put("/{ch_id}")
def update_challenge(ch_id: str, body: ChallengeUpdate, token: dict = Depends(verify_token)):
    require_admin(token)
    if body.condition is not None:
        _validate_condition(body.condition)
    db  = get_db()
    row = db.execute("SELECT * FROM challenges WHERE id=?", (ch_id,)).fetchone()
    if not row:
        db.close()
        raise HTTPException(404, "Challenge bulunamadı")
    updates = {
        "name":          body.name          if body.name          is not None else row["name"],
        "condition":     body.condition     if body.condition     is not None else row["condition"],
        "reward_points": body.reward_points if body.reward_points is not None else row["reward_points"],
        "priority":      body.priority      if body.priority      is not None else row["priority"],
        "is_active":     int(body.is_active if body.is_active     is not None else bool(row["is_active"])),
    }
    db.execute(
        "UPDATE challenges SET name=?, condition=?, reward_points=?, priority=?, is_active=? WHERE id=?",
        (updates["name"], updates["condition"], updates["reward_points"],
         updates["priority"], updates["is_active"], ch_id),
    )
    db.commit()
    updated = db.execute("SELECT * FROM challenges WHERE id=?", (ch_id,)).fetchone()
    db.close()
    return dict(updated) | {"is_active": bool(updated["is_active"])}


@router.post("/{ch_id}/toggle")
def toggle_challenge(ch_id: str, token: dict = Depends(verify_token)):
    require_admin(token)
    db  = get_db()
    row = db.execute("SELECT * FROM challenges WHERE id=?", (ch_id,)).fetchone()
    if not row:
        db.close()
        raise HTTPException(404, "Challenge bulunamadı")
    new_state = 0 if row["is_active"] else 1
    db.execute("UPDATE challenges SET is_active=? WHERE id=?", (new_state, ch_id))
    db.commit()
    db.close()
    return {"id": ch_id, "is_active": bool(new_state)}


@router.delete("/{ch_id}")
def delete_challenge(ch_id: str, token: dict = Depends(verify_token)):
    require_admin(token)
    db  = get_db()
    row = db.execute("SELECT id FROM challenges WHERE id=?", (ch_id,)).fetchone()
    if not row:
        db.close()
        raise HTTPException(404, "Challenge bulunamadı")
    db.execute("DELETE FROM challenges WHERE id=?", (ch_id,))
    db.commit()
    db.close()
    return {"deleted": ch_id}


@router.get("/fields")
def allowed_fields():
    """Admin form için geçerli alan listesi."""
    return {"fields": sorted(ALLOWED_FIELDS), "operators": [">=", ">", "<=", "<", "==", "!="]}


@router.post("/ai-suggest")
def ai_suggest_challenges(token: dict = Depends(verify_token)):
    """GPT-4o gerçek platform metriklerinden görev önerir (Sprint 24).
    Öneriler safe parser'dan geçirilir; görev ancak admin kaydederse oluşur."""
    require_admin(token)
    from engine.challenge_designer_engine import suggest_challenges
    return suggest_challenges()
