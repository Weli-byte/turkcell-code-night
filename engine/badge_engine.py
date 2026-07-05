"""
Badge engine.
Eşikler sabit tanımlı, DB'deki puana göre atama yapar.
UNIQUE constraint sayesinde duplicate badge olmaz.
"""

from database.setup import get_db
from datetime import datetime

BADGE_THRESHOLDS = [
    ("BRONZE",   500),
    ("SILVER",   1500),
    ("GOLD",     3000),
    ("PLATINUM", 5000),
]


def assign_badges(user_id: str, total_points: int) -> list:
    """
    Kullanıcının toplam puanına göre hak ettiği
    rozetleri atar. Zaten varsa atlar (UNIQUE).
    Döner: bu çalışmada yeni atanan rozetlerin listesi
    """
    db = get_db()
    newly_awarded = []

    for tier, threshold in BADGE_THRESHOLDS:
        if total_points >= threshold:
            try:
                db.execute("""
                    INSERT INTO user_badges
                    (user_id, badge_tier, awarded_at,
                     total_points_at_award)
                    VALUES (?,?,?,?)
                """, (
                    user_id, tier,
                    datetime.now().isoformat(),
                    total_points
                ))
                newly_awarded.append(tier)
            except Exception:
                pass

    db.commit()
    db.close()
    return newly_awarded


def get_user_badges(user_id: str) -> list:
    db = get_db()
    rows = db.execute("""
        SELECT badge_tier, awarded_at, total_points_at_award
        FROM user_badges
        WHERE user_id = ?
        ORDER BY total_points_at_award ASC
    """, (user_id,)).fetchall()
    db.close()
    return [dict(r) for r in rows]


def get_badge_progress(user_id: str, total_points: int) -> dict:
    """Sonraki rozet için ilerleme bilgisi döndürür."""
    current_badge = None
    next_badge = None
    next_threshold = None

    for tier, threshold in BADGE_THRESHOLDS:
        if total_points >= threshold:
            current_badge = tier
        elif next_badge is None:
            next_badge = tier
            next_threshold = threshold

    tiers = []
    for tier, threshold in BADGE_THRESHOLDS:
        tiers.append({
            "tier": tier,
            "threshold": threshold,
            "earned": total_points >= threshold,
            "percentage": min(100, round(
                (total_points / threshold * 100) if threshold > 0 else 0
            )),
        })

    return {
        "current_points":  total_points,
        "current_badge":   current_badge,
        "next_badge":      next_badge,
        "next_threshold":  next_threshold,
        "points_needed":   max(0, (next_threshold or 0) - total_points),
        "percentage":      min(100, round(
            total_points / next_threshold * 100
        )) if next_threshold else 100,
        "tiers": tiers,
    }
