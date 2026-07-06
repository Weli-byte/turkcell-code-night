from fastapi import APIRouter, Depends
from api.auth_utils import verify_token, require_admin
from database.setup import get_db
from engine.achievement_engine import (
    ACHIEVEMENTS, check_achievements, get_achievements_status,
)

router = APIRouter(tags=["Achievements"])


@router.get("/mine")
def my_achievements(token: dict = Depends(verify_token)):
    """Tüm başarımlar — kazanılan + kilitli (gerçek ilerlemeyle).
    Çağrı öncesi hak edilmiş ama işlenmemiş başarımlar idempotent işlenir."""
    check_achievements(token["sub"])
    return get_achievements_status(token["sub"])


@router.get("/stats")
def achievement_stats(token: dict = Depends(verify_token)):
    """Başarım dağılımı — her başarımı kaç kullanıcı kazandı (admin)."""
    require_admin(token)
    db = get_db()
    counts = {
        r["achievement_id"]: int(r["c"]) for r in db.execute(
            "SELECT achievement_id, COUNT(*) AS c FROM user_achievements "
            "GROUP BY achievement_id"
        ).fetchall()
    }
    total_users = db.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    db.close()
    return {
        "total_users": int(total_users),
        "stats": [
            {
                "id": a["id"], "name": a["name"], "icon": a["icon"],
                "earned_by": counts.get(a["id"], 0),
                "pct": round(counts.get(a["id"], 0) / max(total_users, 1) * 100, 1),
            }
            for a in ACHIEVEMENTS
        ],
    }
