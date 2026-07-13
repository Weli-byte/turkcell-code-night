"""
engine/pipeline.py — Ana degerlendirme pipeline'i (idempotent + thread-safe).

threading.Lock ile ayni anda tek calisma (race condition korumasi). Deterministik:
rastgelelik yok. Idempotent: already_rewarded ile ayni gun ayni challenge tekrar
odullendirilmez -> duplicate puan olmaz. Tum degerler DB'den.
"""

import time
import threading
from datetime import datetime

from database.setup import get_db
from engine.state_builder import build_user_state
from engine.condition_parser import parse_condition
from engine.ledger import append_points, already_rewarded, get_total_points
from engine.badge_engine import assign_badges

_pipeline_lock = threading.Lock()

DATE_FMT = "%Y-%m-%d"


def run_pipeline(run_date: str = None) -> dict:
    """Pipeline'i thread-safe calistirir (ayni anda tek thread)."""
    with _pipeline_lock:
        return _run_pipeline_locked(run_date)


def _run_pipeline_locked(run_date: str) -> dict:
    t0 = time.perf_counter()

    if not run_date:
        run_date = datetime.now().strftime(DATE_FMT)

    # Kullanicilar ve aktif challenge'lar (sabit + AI uretimi, is_active=1) DB'den.
    db = get_db()
    try:
        users = [r["id"] for r in db.execute("SELECT id FROM users").fetchall()]
        challenges = [
            dict(r) for r in db.execute(
                "SELECT id, name, condition, reward_points, priority "
                "FROM challenges WHERE is_active=1"
            ).fetchall()
        ]
    finally:
        db.close()

    challenges_evaluated = 0
    points_distributed = 0
    badges_awarded = 0
    user_results = []

    for uid in users:
        state = build_user_state(uid, run_date)

        passing = []
        for ch in challenges:
            challenges_evaluated += 1
            try:
                ok = parse_condition(ch["condition"], state)
            except Exception:
                ok = False
            if ok and not already_rewarded(uid, ch["id"], run_date):
                passing.append(ch)

        awarded_challenge = None
        awarded_points = 0
        if passing:
            # En yuksek priority'li gecen challenge (esitlikte daha yuksek puan), deterministik.
            best = max(passing, key=lambda c: (int(c["priority"]), int(c["reward_points"]), c["id"]))
            append_points(
                uid, int(best["reward_points"]),
                f"Challenge: {best['name']}", run_date, best["id"],
            )
            awarded_points = int(best["reward_points"])
            points_distributed += awarded_points
            awarded_challenge = best["id"]

        total = get_total_points(uid)
        new_badges = assign_badges(uid, total)
        badges_awarded += len(new_badges)

        user_results.append({
            "user_id": uid,
            "awarded_challenge": awarded_challenge,
            "awarded_points": awarded_points,
            "total_points": total,
            "new_badges": new_badges,
        })

    duration_ms = int((time.perf_counter() - t0) * 1000)

    db = get_db()
    try:
        db.execute(
            "INSERT INTO pipeline_runs "
            "(run_date, users_processed, badges_awarded, points_distributed, duration_ms, ran_at) "
            "VALUES (?,?,?,?,?,?)",
            (run_date, len(users), badges_awarded, points_distributed, duration_ms,
             datetime.now().isoformat()),
        )
        db.commit()
    finally:
        db.close()

    return {
        "run_date": run_date,
        "users_processed": len(users),
        "challenges_evaluated": challenges_evaluated,
        "points_distributed": points_distributed,
        "badges_awarded": badges_awarded,
        "duration_ms": duration_ms,
        "user_results": user_results,
    }


if __name__ == "__main__":
    stats = run_pipeline()
    print("Pipeline tamamlandi:", stats["run_date"])
    print("  Islenen kullanici :", stats["users_processed"])
    print("  Degerlendirilen ch.:", stats["challenges_evaluated"])
    print("  Dagitilan puan    :", stats["points_distributed"])
    print("  Atanan rozet      :", stats["badges_awarded"])
    print("  Sure              :", stats["duration_ms"], "ms")
