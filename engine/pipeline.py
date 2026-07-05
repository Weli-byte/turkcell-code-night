"""
Ana pipeline — tüm engine modüllerini sırayla çalıştırır.
Idempotent: aynı gün iki kez çalışırsa duplicate puan eklemez.
"""

import threading

from database.setup import get_db
from engine.state_builder import build_user_state
from engine.condition_parser import parse_condition, get_progress
from engine.ledger import append_points, already_rewarded, get_total_points
from engine.badge_engine import assign_badges
from engine.leaderboard_engine import get_leaderboard
from datetime import datetime

_pipeline_lock = threading.Lock()


def run_pipeline(run_date: str = None) -> dict:
    with _pipeline_lock:
        return _run_pipeline_locked(run_date)


def _run_pipeline_locked(run_date: str = None) -> dict:
    if run_date is None:
        run_date = datetime.now().strftime("%Y-%m-%d")

    db = get_db()
    t0 = datetime.now()

    users = db.execute(
        "SELECT id, username FROM users"
    ).fetchall()

    challenges = db.execute(
        "SELECT * FROM challenges WHERE is_active = 1"
    ).fetchall()

    db.close()

    stats = {
        "run_date":               run_date,
        "users_processed":        0,
        "challenges_evaluated":   0,
        "points_distributed":     0,
        "badges_awarded":         0,
        "user_results":           [],
    }

    for user in users:
        user_id  = user["id"]
        username = user["username"]

        state = build_user_state(user_id, run_date)

        user_result = {
            "user_id":           user_id,
            "username":          username,
            "challenges_passed": [],
            "reward_given":      None,
            "points_earned":     0,
            "new_badges":        [],
        }

        passed_challenges = []
        for ch in challenges:
            stats["challenges_evaluated"] += 1
            try:
                passed = parse_condition(ch["condition"], state)
            except ValueError as e:
                print(f"  [WARN] Challenge parse hatasi ({ch['id']}): {e}")
                continue

            if passed:
                if not already_rewarded(user_id, ch["id"], run_date):
                    passed_challenges.append(dict(ch))

        if passed_challenges:
            best = max(passed_challenges, key=lambda c: c["priority"])
            append_points(
                user_id      = user_id,
                points       = best["reward_points"],
                reason       = f"Challenge tamamlandi: {best['name']}",
                activity_date= run_date,
                challenge_id = best["id"],
            )
            stats["points_distributed"] += best["reward_points"]
            user_result["reward_given"]  = best["name"]
            user_result["points_earned"] = best["reward_points"]
            user_result["challenges_passed"] = [c["name"] for c in passed_challenges]

        total = get_total_points(user_id)
        new_badges = assign_badges(user_id, total)
        stats["badges_awarded"]  += len(new_badges)
        user_result["new_badges"] = new_badges

        stats["user_results"].append(user_result)
        stats["users_processed"] += 1

    duration_ms = int((datetime.now() - t0).total_seconds() * 1000)
    db2 = get_db()
    db2.execute("""
        INSERT INTO pipeline_runs
        (run_date, users_processed, badges_awarded,
         points_distributed, duration_ms, ran_at)
        VALUES (?,?,?,?,?,?)
    """, (
        run_date,
        stats["users_processed"],
        stats["badges_awarded"],
        stats["points_distributed"],
        duration_ms,
        datetime.now().isoformat()
    ))
    db2.commit()
    db2.close()

    stats["duration_ms"] = duration_ms
    return stats


def evaluate_user(user_id: str, run_date: str = None) -> dict:
    """
    Tek kullanıcı için senkron evaluasyon — end_session tarafından çağrılır.
    Sadece bu kullanıcının challenge/badge durumunu hesaplar.
    """
    if run_date is None:
        run_date = datetime.now().strftime("%Y-%m-%d")

    db = get_db()
    challenges = db.execute(
        "SELECT * FROM challenges WHERE is_active = 1"
    ).fetchall()
    db.close()

    state = build_user_state(user_id, run_date)

    passed: list = []
    for ch in challenges:
        try:
            ok = parse_condition(ch["condition"], state)
        except ValueError:
            continue
        if ok and not already_rewarded(user_id, ch["id"], run_date):
            passed.append(dict(ch))

    points_earned = 0
    reward_name: str | None = None

    if passed:
        best = max(passed, key=lambda c: c["priority"])
        append_points(
            user_id       = user_id,
            points        = best["reward_points"],
            reason        = f"Challenge tamamlandi: {best['name']}",
            activity_date = run_date,
            challenge_id  = best["id"],
        )
        points_earned = best["reward_points"]
        reward_name   = best["name"]

    total      = get_total_points(user_id)
    new_badges = assign_badges(user_id, total)

    return {
        "user_id":       user_id,
        "points_earned": points_earned,
        "reward_name":   reward_name,
        "new_badges":    new_badges,
        "total_points":  total,
        "run_date":      run_date,
    }


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    print("Pipeline calisiyor...")
    result = run_pipeline()
    print(f"\n{'='*50}")
    print(f"Pipeline tamamlandi: {result['run_date']}")
    print(f"{'='*50}")
    print(f"Islenen kullanici  : {result['users_processed']}")
    print(f"Degerlendirilen ch.: {result['challenges_evaluated']}")
    print(f"Dagitilan puan     : {result['points_distributed']}")
    print(f"Atanan rozet       : {result['badges_awarded']}")
    print(f"Sure               : {result['duration_ms']} ms")
    print(f"\nKullanici detaylari:")
    for u in result["user_results"]:
        print(f"\n  [{u['username']}]")
        print(f"    Kazanilan odul : {u['reward_given'] or 'Yok (esik gecilmedi)'}")
        print(f"    Puan           : +{u['points_earned']}")
        print(f"    Yeni rozetler  : {u['new_badges'] or 'Yok'}")
