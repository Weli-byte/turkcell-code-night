"""
engine/badge_engine.py — Rozet motoru (deterministik).

Esik tabanli rozet atama. Rastgelelik yok. user_badges UNIQUE(user_id,badge_tier)
sayesinde ayni rozet iki kez atanmaz (INSERT + IntegrityError yakalama).
"""

import sqlite3
from datetime import datetime

from database.setup import get_db

# (tier, esik puan) — dusukten yuksege sirali
BADGE_THRESHOLDS = [
    ("BRONZE", 500),
    ("SILVER", 1500),
    ("GOLD", 3000),
    ("PLATINUM", 5000),
]


def assign_badges(user_id: str, total_points: int) -> list:
    """
    total_points esigi gecen her rozet icin user_badges'a INSERT dener.
    Zaten varsa UNIQUE constraint IntegrityError verir -> atlanir.
    Doner: bu calismada YENI atanan rozet tier'lari.
    """
    db = get_db()
    new_badges = []
    try:
        now = datetime.now().isoformat()
        for tier, threshold in BADGE_THRESHOLDS:
            if int(total_points) >= threshold:
                try:
                    db.execute(
                        "INSERT INTO user_badges "
                        "(user_id, badge_tier, awarded_at, total_points_at_award) "
                        "VALUES (?,?,?,?)",
                        (user_id, tier, now, int(total_points)),
                    )
                    new_badges.append(tier)
                except sqlite3.IntegrityError:
                    # Zaten var — normal, atla.
                    pass
        db.commit()
        return new_badges
    finally:
        db.close()


def get_user_badges(user_id: str) -> list:
    """Kullanicinin kazandigi rozetler (list of dict)."""
    db = get_db()
    try:
        rows = db.execute(
            "SELECT id, user_id, badge_tier, awarded_at, total_points_at_award "
            "FROM user_badges WHERE user_id=? ORDER BY total_points_at_award, id",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()


def get_badge_progress(user_id: str, total_points: int) -> dict:
    """
    Rozet ilerlemesi. Esikler BADGE_THRESHOLDS'tan, puan cagirandan.
    Doner: {current_badge, next_badge, next_threshold, points_needed, percentage, tiers}
    """
    pts = int(total_points)
    tiers = []
    current_badge = None
    current_threshold = 0
    for tier, threshold in BADGE_THRESHOLDS:
        achieved = pts >= threshold
        tiers.append({"tier": tier, "threshold": threshold, "achieved": achieved})
        if achieved:
            current_badge = tier
            current_threshold = threshold

    next_badge = None
    next_threshold = None
    for tier, threshold in BADGE_THRESHOLDS:
        if threshold > pts:
            next_badge = tier
            next_threshold = threshold
            break

    if next_threshold is None:
        # Tum rozetler kazanilmis
        points_needed = 0
        percentage = 100
    else:
        points_needed = max(0, next_threshold - pts)
        span = next_threshold - current_threshold
        percentage = min(100, round((pts - current_threshold) / span * 100)) if span > 0 else 100

    return {
        "current_badge": current_badge,
        "next_badge": next_badge,
        "next_threshold": next_threshold,
        "points_needed": points_needed,
        "percentage": percentage,
        "tiers": tiers,
    }
