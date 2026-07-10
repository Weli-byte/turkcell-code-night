"""
Admin Insights Engine — Sprint 15.
Platform genelinin GERÇEK agregalarını çıkarır, GPT-4o yönetici özeti +
somut aksiyon önerileri üretir. Tüm sayılar DB'den; LLM sadece yorumlar.
"""

import json
from datetime import datetime, timedelta
from database.setup import get_db


def collect_platform_metrics() -> dict:
    """Tüm platform metriklerini gerçek DB sorgularıyla toplar."""
    now        = datetime.now()
    today      = now.strftime("%Y-%m-%d")
    week_start = (now - timedelta(days=6)).strftime("%Y-%m-%d")

    db = get_db()

    users_total = db.execute(
        "SELECT COUNT(*) AS c FROM users"
    ).fetchone()["c"]
    active_today = db.execute(
        "SELECT COUNT(DISTINCT user_id) AS c FROM user_activities WHERE activity_date=?",
        (today,),
    ).fetchone()["c"]
    active_7d = db.execute(
        "SELECT COUNT(DISTINCT user_id) AS c FROM user_activities WHERE activity_date>=?",
        (week_start,),
    ).fetchone()["c"]

    # Churn adayları: kayıtlı ama son 7 gün hiç aktivitesi olmayanlar
    inactive_7d = db.execute("""
        SELECT COUNT(*) AS c FROM users u
        WHERE NOT EXISTS (
            SELECT 1 FROM user_activities ua
            WHERE ua.user_id = u.id AND ua.activity_date >= ?
        )
    """, (week_start,)).fetchone()["c"]

    watch = db.execute("""
        SELECT COALESCE(SUM(watch_minutes),0)      AS total_min,
               COALESCE(SUM(episodes_completed),0) AS total_eps
        FROM user_activities
    """).fetchone()
    watch_7d = db.execute(
        "SELECT COALESCE(SUM(watch_minutes),0) AS m FROM user_activities WHERE activity_date>=?",
        (week_start,),
    ).fetchone()["m"]

    points = db.execute("""
        SELECT COALESCE(SUM(points),0) AS total,
               COUNT(*)                AS entries
        FROM points_ledger
    """).fetchone()
    points_7d = db.execute(
        "SELECT COALESCE(SUM(points),0) AS p FROM points_ledger WHERE activity_date>=?",
        (week_start,),
    ).fetchone()["p"]

    # Görev tamamlama kırılımı (7 gün)
    challenge_stats = db.execute("""
        SELECT c.name, COUNT(*) AS completions, SUM(pl.points) AS pts
        FROM points_ledger pl
        JOIN challenges c ON c.id = pl.challenge_id
        WHERE pl.activity_date >= ?
        GROUP BY c.id ORDER BY completions DESC
    """, (week_start,)).fetchall()

    # Hiç tamamlanmayan aktif görevler (7 gün) — zorluk sinyali
    never_completed = db.execute("""
        SELECT c.name, c.condition, c.reward_points
        FROM challenges c
        WHERE c.is_active = 1
          AND NOT EXISTS (
              SELECT 1 FROM points_ledger pl
              WHERE pl.challenge_id = c.id AND pl.activity_date >= ?
          )
    """, (week_start,)).fetchall()

    # En popüler içerik (7 gün, gerçek seanslar)
    top_content = db.execute("""
        SELECT cc.title, cc.genre,
               COUNT(ws.id) AS watches,
               COALESCE(SUM(ws.watch_minutes),0) AS minutes
        FROM watch_sessions ws
        JOIN content_catalog cc ON cc.id = ws.content_id
        WHERE ws.ended_at IS NOT NULL AND ws.ended_at >= ?
        GROUP BY cc.id ORDER BY watches DESC LIMIT 5
    """, (week_start,)).fetchall()

    # Rating durumu
    ratings = db.execute("""
        SELECT COUNT(*) AS cnt, COALESCE(AVG(rating),0) AS avg_r
        FROM content_ratings
    """).fetchone()

    # Watch party kullanımı
    parties = db.execute(
        "SELECT COUNT(*) AS total, SUM(is_active) AS active FROM watch_parties"
    ).fetchone()
    party_minutes = db.execute(
        "SELECT COALESCE(SUM(watch_party_minutes),0) AS m FROM user_activities"
    ).fetchone()["m"]

    # Rozet dağılımı
    badges = db.execute("""
        SELECT badge_tier, COUNT(*) AS cnt FROM user_badges
        GROUP BY badge_tier ORDER BY cnt DESC
    """).fetchall()

    # AI sohbet kullanımı
    chat_stats = db.execute("""
        SELECT COUNT(*) AS msgs, COUNT(DISTINCT user_id) AS users
        FROM chat_messages
    """).fetchone()

    # Başarım dağılımı (Sprint 21)
    ach_rows = db.execute("""
        SELECT achievement_id, COUNT(*) AS c FROM user_achievements
        GROUP BY achievement_id ORDER BY c DESC
    """).fetchall()

    db.close()

    return {
        "generated_at":   now.isoformat(timespec="seconds"),
        "week_start":     week_start,
        "users": {
            "total":        int(users_total),
            "active_today": int(active_today),
            "active_7d":    int(active_7d),
            "inactive_7d":  int(inactive_7d),
        },
        "watch": {
            "total_minutes":  round(float(watch["total_min"]), 1),
            "total_episodes": int(watch["total_eps"]),
            "minutes_7d":     round(float(watch_7d), 1),
        },
        "points": {
            "total_distributed": int(points["total"]),
            "ledger_entries":    int(points["entries"]),
            "points_7d":         int(points_7d),
        },
        "challenges_7d": [
            {"name": c["name"], "completions": int(c["completions"]),
             "points_given": int(c["pts"])}
            for c in challenge_stats
        ],
        "challenges_never_completed_7d": [
            {"name": c["name"], "condition": c["condition"],
             "reward_points": c["reward_points"]}
            for c in never_completed
        ],
        "top_content_7d": [
            {"title": t["title"], "genre": t["genre"],
             "watches": int(t["watches"]), "minutes": round(float(t["minutes"]), 1)}
            for t in top_content
        ],
        "ratings": {
            "count": int(ratings["cnt"]),
            "avg":   round(float(ratings["avg_r"]), 2),
        },
        "watch_party": {
            "rooms_total":   int(parties["total"] or 0),
            "rooms_active":  int(parties["active"] or 0),
            "party_minutes": round(float(party_minutes), 1),
        },
        "badges": {b["badge_tier"]: int(b["cnt"]) for b in badges},
        "ai_chat": {
            "messages": int(chat_stats["msgs"]),
            "users":    int(chat_stats["users"]),
        },
        "achievements_earned": {
            r["achievement_id"]: int(r["c"]) for r in ach_rows
        },
        "community_sentiment": _platform_sentiment(),
    }


def _platform_sentiment() -> dict:
    """GPT-4o ile etiketlenmiş yorumların platform geneli dağılımı (Sprint 26)."""
    from engine.sentiment_engine import get_platform_sentiment
    return get_platform_sentiment()


def build_admin_insights() -> dict:
    """Metrikler + GPT-4o yönetici analizi. Fallback deterministik özet."""
    metrics = collect_platform_metrics()

    u, w, p = metrics["users"], metrics["watch"], metrics["points"]
    top_ch  = metrics["challenges_7d"][0] if metrics["challenges_7d"] else None
    top_vid = metrics["top_content_7d"][0] if metrics["top_content_7d"] else None

    template = (
        f"Platform: {u['total']} kullanıcı ({u['active_today']} bugün, "
        f"{u['active_7d']} son 7 gün aktif; {u['inactive_7d']} pasif). "
        f"Bu hafta {w['minutes_7d']:.0f} dk izleme, {p['points_7d']} puan dağıtıldı. "
        + (f"En popüler görev: {top_ch['name']} ({top_ch['completions']} tamamlama). " if top_ch else "")
        + (f"En popüler içerik: {top_vid['title']} ({top_vid['watches']} izlenme). " if top_vid else "")
        + (f"{len(metrics['challenges_never_completed_7d'])} görev bu hafta hiç tamamlanmadı." if metrics["challenges_never_completed_7d"] else "")
    ).strip()

    from engine.llm_adapter import llm_call, is_llm_available, LLM_MODEL
    llm_answer = llm_call(
        system=(
            "Sen bir video platformunun veri analisti ve ürün danışmanısın. "
            "Yöneticiye platform metriklerini yorumlar, riskleri işaret eder "
            "ve somut aksiyonlar önerirsin. Sayıları asla değiştirme."
        ),
        user=(
            f"Platform metrikleri (gerçek veriler):\n"
            f"{json.dumps(metrics, ensure_ascii=False, indent=2)}\n\n"
            f"Türkçe bir yönetici analizi yaz:\n"
            f"1. Genel durum (2-3 cümle)\n"
            f"2. Dikkat çeken riskler (pasif kullanıcılar, tamamlanmayan görevler vb.)\n"
            f"3. TAM OLARAK 3 somut aksiyon önerisi (madde işaretli, her biri 1 cümle)\n"
            f"Toplam 10 cümleyi geçme."
        ),
        max_tokens=500,
        temperature=0.4,
    )

    if llm_answer:
        answer, llm_enhanced, model = llm_answer, True, LLM_MODEL
    else:
        answer, llm_enhanced = template, False
        model = LLM_MODEL if is_llm_available() else "template"

    return {
        "answer":       answer,
        "metrics":      metrics,
        "llm_enhanced": llm_enhanced,
        "model":        model,
    }
