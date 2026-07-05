"""
Digest Engine — Sprint 7.
Günlük kişisel özet: gerçek DB verisi + GPT-4o doğal dil anlatısı.
"""

import json
from datetime import datetime, timedelta
from database.setup import get_db
from engine.state_builder import build_user_state
from engine.leaderboard_engine import get_leaderboard
from engine.badge_engine import get_badge_progress


def build_digest(user_id: str) -> dict:
    today = datetime.now().strftime("%Y-%m-%d")
    state = build_user_state(user_id, today)

    db = get_db()

    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    week_row = db.execute(
        "SELECT COALESCE(SUM(points),0) AS total FROM points_ledger "
        "WHERE user_id=? AND activity_date>=?",
        (user_id, week_ago),
    ).fetchone()

    ch_today = db.execute(
        "SELECT COUNT(*) AS cnt FROM points_ledger "
        "WHERE user_id=? AND activity_date=? AND challenge_id IS NOT NULL",
        (user_id, today),
    ).fetchone()

    last_badge = db.execute(
        "SELECT badge_tier, awarded_at FROM user_badges "
        "WHERE user_id=? ORDER BY awarded_at DESC LIMIT 1",
        (user_id,),
    ).fetchone()

    sessions = db.execute(
        "SELECT COUNT(*) AS cnt FROM watch_sessions WHERE user_id=? AND ended_at IS NOT NULL",
        (user_id,),
    ).fetchone()

    db.close()

    leaderboard = get_leaderboard(10000)
    rank        = next((e["rank"] for e in leaderboard if e["user_id"] == user_id), len(leaderboard) + 1)
    total_users = len(leaderboard)
    progress    = get_badge_progress(user_id, state["total_points"])

    evidence: dict = {
        "today":               today,
        "watch_minutes_today": round(state["watch_minutes_today"], 1),
        "episodes_today":      state["episodes_completed_today"],
        "today_points":        state["today_points"],
        "total_points":        state["total_points"],
        "streak_days":         state["streak_days"],
        "rank":                rank,
        "total_users":         total_users,
        "week_points":         int(week_row["total"]),
        "challenges_today":    int(ch_today["cnt"]),
        "current_badge":       progress["current_badge"],
        "next_badge":          progress["next_badge"],
        "points_to_next_badge": progress["points_needed"],
        "total_sessions":      int(sessions["cnt"]),
        "last_badge":          dict(last_badge) if last_badge else None,
    }

    # Template cevap
    next_badge_text = (
        f"Sonraki rozet: {progress['next_badge']} için {progress['points_needed']} puan gerekli."
        if progress["next_badge"]
        else "En yüksek rozete ulaştın!"
    )
    template = (
        f"{today}: {state['watch_minutes_today']:.0f} dk izledin, "
        f"{state['episodes_completed_today']} bölüm tamamladın, "
        f"{state['today_points']} puan kazandın. "
        f"Streak: {state['streak_days']} gün. "
        f"{total_users} kullanıcı arasında {rank}. sıradasın. "
        f"Bu hafta {int(week_row['total'])} puan. "
        f"{next_badge_text}"
    )

    # GPT-4o
    from engine.llm_adapter import LLM_ENABLED, OPENAI_API_KEY, LLM_MODEL, LLM_MAX_TOKENS
    if LLM_ENABLED and OPENAI_API_KEY:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY)
            prompt = (
                f"Kullanıcının günlük özet verileri:\n"
                f"{json.dumps(evidence, ensure_ascii=False, indent=2)}\n\n"
                f"Bu verilere dayanarak kullanıcıya kişisel, sıcak ve motive edici bir günlük özet yaz. "
                f"Rakamları olduğu gibi kullan, değiştirme. Maksimum 4 cümle. Türkçe."
            )
            resp = client.chat.completions.create(
                model=LLM_MODEL, max_tokens=LLM_MAX_TOKENS, temperature=0.45,
                messages=[
                    {"role": "system", "content": "Sen bir video platformu koçusun. Kullanıcıların günlük performansını özetleyerek onları motive et."},
                    {"role": "user",   "content": prompt},
                ],
            )
            answer       = resp.choices[0].message.content.strip()
            llm_enhanced = True
            llm_error    = None
            model        = LLM_MODEL
        except Exception as exc:
            answer       = template
            llm_enhanced = False
            llm_error    = str(exc)
            model        = LLM_MODEL
    else:
        answer       = template
        llm_enhanced = False
        llm_error    = None
        model        = "template"

    return {
        "answer":       answer,
        "evidence":     evidence,
        "llm_enhanced": llm_enhanced,
        "llm_error":    llm_error,
        "model":        model,
    }
