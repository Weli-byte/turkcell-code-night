"""
Weekly Report Engine — Sprint 14.
Son 7 günün GERÇEK verilerinden haftalık koç raporu üretir.
Tüm sayılar DB'den; GPT-4o sadece anlatıyı yazar, fallback deterministik.
"""

import json
from datetime import datetime, timedelta
from database.setup import get_db
from engine.state_builder import build_user_state
from engine.leaderboard_engine import get_leaderboard
from engine.badge_engine import get_badge_progress


def build_weekly_report(user_id: str) -> dict:
    now        = datetime.now()
    today      = now.strftime("%Y-%m-%d")
    week_start = (now - timedelta(days=6)).strftime("%Y-%m-%d")
    prev_start = (now - timedelta(days=13)).strftime("%Y-%m-%d")
    prev_end   = (now - timedelta(days=7)).strftime("%Y-%m-%d")

    state = build_user_state(user_id, today)
    db    = get_db()

    # Gün gün kırılım (son 7 gün)
    daily = []
    for i in range(6, -1, -1):
        d   = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        act = db.execute(
            "SELECT COALESCE(SUM(watch_minutes),0) AS m, "
            "COALESCE(SUM(episodes_completed),0) AS e "
            "FROM user_activities WHERE user_id=? AND activity_date=?",
            (user_id, d),
        ).fetchone()
        pts = db.execute(
            "SELECT COALESCE(SUM(points),0) AS p FROM points_ledger "
            "WHERE user_id=? AND activity_date=?",
            (user_id, d),
        ).fetchone()
        daily.append({
            "date":     d,
            "minutes":  round(float(act["m"]), 1),
            "episodes": int(act["e"]),
            "points":   int(pts["p"]),
        })

    # Haftalık toplamlar + önceki haftayla kıyas
    this_week_min = sum(d["minutes"] for d in daily)
    this_week_pts = sum(d["points"] for d in daily)
    prev_row = db.execute(
        "SELECT COALESCE(SUM(watch_minutes),0) AS m FROM user_activities "
        "WHERE user_id=? AND activity_date>=? AND activity_date<=?",
        (user_id, prev_start, prev_end),
    ).fetchone()
    prev_week_min = float(prev_row["m"])
    change_pct = (
        round((this_week_min - prev_week_min) / prev_week_min * 100, 1)
        if prev_week_min > 0 else None
    )

    # En çok izlenen tür (7 gün, gerçek seanslardan)
    top_genre_row = db.execute("""
        SELECT cc.genre, COALESCE(SUM(ws.watch_minutes),0) AS m
        FROM watch_sessions ws
        JOIN content_catalog cc ON cc.id = ws.content_id
        WHERE ws.user_id=? AND ws.ended_at IS NOT NULL AND ws.ended_at>=?
        GROUP BY cc.genre ORDER BY m DESC LIMIT 1
    """, (user_id, week_start)).fetchone()

    # Tamamlanan görevler (7 gün)
    challenges = db.execute("""
        SELECT c.name, pl.points, pl.activity_date
        FROM points_ledger pl
        JOIN challenges c ON c.id = pl.challenge_id
        WHERE pl.user_id=? AND pl.activity_date>=?
        ORDER BY pl.activity_date
    """, (user_id, week_start)).fetchall()

    # En iyi gün
    best_day = max(daily, key=lambda d: d["minutes"]) if daily else None
    active_days = sum(1 for d in daily if d["minutes"] > 0)

    db.close()

    leaderboard = get_leaderboard(10000)
    rank        = next((e["rank"] for e in leaderboard if e["user_id"] == user_id),
                       len(leaderboard) + 1)
    progress    = get_badge_progress(user_id, state["total_points"])

    evidence = {
        "week_start":       week_start,
        "week_end":         today,
        "daily":            daily,
        "this_week_minutes": round(this_week_min, 1),
        "this_week_points":  this_week_pts,
        "prev_week_minutes": round(prev_week_min, 1),
        "change_pct":        change_pct,
        "active_days":       active_days,
        "best_day":          best_day,
        "top_genre": (
            {"genre": top_genre_row["genre"],
             "minutes": round(float(top_genre_row["m"]), 1)}
            if top_genre_row else None
        ),
        "challenges_completed": [
            {"name": c["name"], "points": c["points"], "date": c["activity_date"]}
            for c in challenges
        ],
        "streak_days":   state["streak_days"],
        "rank":          rank,
        "total_users":   len(leaderboard),
        "total_points":  state["total_points"],
        "current_badge": progress["current_badge"],
        "next_badge":    progress["next_badge"],
        "points_to_next": progress["points_needed"],
    }

    # Deterministik rapor (fallback + LLM'e taban)
    trend = (
        f"Önceki haftaya göre %{abs(change_pct)} "
        f"{'artış' if change_pct >= 0 else 'düşüş'}."
        if change_pct is not None else "Önceki hafta verisi yok."
    )
    genre_txt = (
        f"En çok izlediğin tür: {evidence['top_genre']['genre']} "
        f"({evidence['top_genre']['minutes']:.0f} dk)."
        if evidence["top_genre"] else ""
    )
    template = (
        f"{week_start} – {today} haftası: {this_week_min:.0f} dakika izledin, "
        f"{this_week_pts} puan kazandın, {len(challenges)} görev tamamladın. "
        f"{active_days}/7 gün aktiftin. {trend} {genre_txt} "
        f"Streak: {state['streak_days']} gün. "
        f"{len(leaderboard)} kullanıcı arasında {rank}. sıradasın."
    ).strip()

    # GPT-4o koç anlatısı
    from engine.llm_adapter import llm_call, is_llm_available, LLM_MODEL
    llm_answer = llm_call(
        system=(
            "Sen bir video platformu performans koçusun. Kullanıcının haftalık "
            "verilerini analiz edip kişisel, dengeli bir rapor yazarsın: "
            "güçlü yönler + somut gelişim önerisi. Sayıları asla değiştirme."
        ),
        user=(
            f"Haftalık veriler:\n{json.dumps(evidence, ensure_ascii=False, indent=2)}\n\n"
            f"Bu verilerle 5-6 cümlelik Türkçe haftalık koç raporu yaz: "
            f"en güçlü gün, trend yorumu, tür alışkanlığı ve önümüzdeki hafta "
            f"için tek somut öneri içersin."
        ),
        max_tokens=400,
        temperature=0.45,
    )

    if llm_answer:
        answer, llm_enhanced, model = llm_answer, True, LLM_MODEL
    else:
        answer, llm_enhanced = template, False
        model = LLM_MODEL if is_llm_available() else "template"

    return {
        "answer":       answer,
        "evidence":     evidence,
        "llm_enhanced": llm_enhanced,
        "model":        model,
    }
