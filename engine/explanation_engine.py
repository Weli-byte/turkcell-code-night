"""
AI Explanation Engine.
Karar vermez, açıklar.
LLM olmadan template ile çalışır.
LLM varsa (OPENAI_API_KEY + LLM_ENABLED=true) GPT-4o ile doğallaştırır.
"""

from datetime import datetime, timedelta
from engine.state_builder import build_user_state
from engine.leaderboard_engine import get_leaderboard
from engine.badge_engine import get_badge_progress
from engine.ledger import get_history
from database.setup import get_db


def detect_intent(question: str) -> str:
    q = question.lower()

    if any(w in q for w in ["streak", "seri", "arka arkaya", "kesintisiz"]):
        return "streak"

    if any(w in q for w in ["gerideyim", "fark", "digerlerinden", "ne kadar geride"]):
        return "compare"

    if any(w in q for w in ["bugun ne", "bugunku", "gunluk ozet", "bugun ne yaptim"]):
        return "today"

    if any(w in q for w in ["gecen hafta", "bu ay", "son 7", "haftalik", "bu hafta"]):
        return "history"

    if any(w in q for w in ["kac puan", "toplam puan", "puanim", "kac puanim"]):
        return "points_query"

    if any(w in q for w in ["sira", "rank", "liderlik", "kacinci", "neden bu sira"]):
        return "rank_query"

    if any(w in q for w in ["rozet", "badge", "bronze", "silver", "gold", "platinum", "ne zaman"]):
        return "badge_progress"

    if any(w in q for w in ["neden kazandim", "nasil kazandim", "hangi odul", "odulum"]):
        return "reward_explanation"

    if any(w in q for w in ["ne yapmali", "nasil artir", "oneri", "tavsiye", "ne yapabilirim"]):
        return "suggestion"

    return "general"


def build_answer(intent: str, user_id: str) -> dict:
    today = datetime.now().strftime("%Y-%m-%d")
    state = build_user_state(user_id, today)
    total = state["total_points"]

    leaderboard = get_leaderboard(1000)
    rank        = next(
        (e["rank"] for e in leaderboard if e["user_id"] == user_id),
        len(leaderboard) + 1,
    )
    total_users = len(leaderboard)
    progress    = get_badge_progress(user_id, total)

    db = get_db()
    last_reward = db.execute("""
        SELECT pl.points, pl.reason, pl.activity_date,
               c.name AS challenge_name, c.condition
        FROM points_ledger pl
        LEFT JOIN challenges c ON c.id = pl.challenge_id
        WHERE pl.user_id = ?
          AND pl.challenge_id IS NOT NULL
        ORDER BY pl.created_at DESC LIMIT 1
    """, (user_id,)).fetchone()

    active_chs = db.execute("""
        SELECT name, condition, reward_points
        FROM challenges WHERE is_active=1
        ORDER BY priority DESC
    """).fetchall()
    db.close()

    evidence = {
        "total_points":        total,
        "rank":                rank,
        "total_users":         total_users,
        "current_badge":       progress["current_badge"],
        "next_badge":          progress["next_badge"],
        "next_threshold":      progress["next_threshold"],
        "points_needed":       progress["points_needed"],
        "watch_minutes_today": state["watch_minutes_today"],
        "streak_days":         state["streak_days"],
    }

    if intent == "streak":
        answer = (
            f"{state['streak_days']} gunluk kesintisiz "
            f"serin var. "
            f"Bugun {state['watch_minutes_today']:.0f} "
            f"dakika izledin. "
            f"Seriyi korumak icin bu gece de izle."
        )
        evidence["streak_days"]         = state["streak_days"]
        evidence["watch_minutes_today"] = state["watch_minutes_today"]

    elif intent == "compare":
        above = next(
            (e for e in leaderboard if e["rank"] == rank - 1),
            None,
        )
        if above:
            gap      = above["total_points"] - total
            days_est = max(1, round(gap / 80))
            answer = (
                f"Bir ustundeki kullaniciyla fark {gap} puan. "
                f"Gunluk challengelari tamamlarsan "
                f"yaklasik {days_est} gunde o siraya ulasirsin."
            )
            evidence["gap_to_next"]    = gap
            evidence["days_estimated"] = days_est
        else:
            answer = (
                f"Liderlik tablosunun zirveindesin! "
                f"Toplam {total} puanla 1. siradasin."
            )

    elif intent == "today":
        db_tmp = get_db()
        ch_cnt = db_tmp.execute("""
            SELECT COUNT(*) AS cnt FROM points_ledger
            WHERE user_id = ? AND activity_date = ?
              AND challenge_id IS NOT NULL
        """, (user_id, today)).fetchone()
        db_tmp.close()
        answer = (
            f"Bugun {state['watch_minutes_today']:.0f} "
            f"dakika izledin, "
            f"{state['episodes_completed_today']} bolum "
            f"tamamladin ve "
            f"{state['today_points']} puan kazandin. "
            f"{ch_cnt['cnt']} challenge tamamlandi."
        )
        evidence["today_challenges"] = ch_cnt["cnt"]
        evidence["today_points"]     = state["today_points"]

    elif intent == "history":
        db_tmp   = get_db()
        week_ago = (
            datetime.now() - timedelta(days=7)
        ).strftime("%Y-%m-%d")
        week_row = db_tmp.execute("""
            SELECT COALESCE(SUM(points), 0) AS total
            FROM points_ledger
            WHERE user_id = ? AND activity_date >= ?
        """, (user_id, week_ago)).fetchone()
        db_tmp.close()
        answer = (
            f"Son 7 gunde {week_row['total']} puan kazandin. "
            f"Bu haftanin toplam izleme suresi: "
            f"{state['watch_minutes_7d']:.0f} dakika."
        )
        evidence["week_points"]  = int(week_row["total"])
        evidence["week_minutes"] = state["watch_minutes_7d"]

    elif intent == "points_query":
        answer = (
            f"Toplam {total} puanin var. "
            f"Bugun {state['watch_minutes_today']:.0f} dakika izledin "
            f"ve {state['today_points']} puan kazandin. "
            f"{total_users} kullanici arasinda {rank}. siradasin."
        )

    elif intent == "rank_query":
        if rank > 1:
            above = next(
                (e for e in leaderboard if e["rank"] == rank - 1), None
            )
            gap = (above["total_points"] - total) if above else 0
            answer = (
                f"{rank}. siradasin ({total_users} kullanici arasinda). "
                f"Bir ustundeki kullaniciyla arandaki fark {gap} puan. "
                f"O kadar puan kazanirsan siran yukselir."
            )
        else:
            answer = (
                f"Liderlik tablosunun zirveindesin! "
                f"{total_users} kullanici arasinda 1. siradasin "
                f"ve {total} puanin var."
            )

    elif intent == "badge_progress":
        if progress["next_badge"]:
            days = max(1, round(progress["points_needed"] / 80))
            answer = (
                f"Mevcut rozet: {progress['current_badge'] or 'Yok'}. "
                f"Hedef: {progress['next_badge']} "
                f"({progress['next_threshold']} puan gerekli). "
                f"{progress['points_needed']} puana daha ihtiyacin var. "
                f"Gunluk challengelarla yaklasik {days} gunde ulasirsin."
            )
        else:
            answer = (
                f"Tebrikler! En yuksek rozet PLATINUM'a ulastin. "
                f"Toplam {total} puanin var."
            )

    elif intent == "reward_explanation":
        if last_reward:
            answer = (
                f"Son odulunu '{last_reward['challenge_name']}' "
                f"challengeini tamamlayarak kazandin. "
                f"Kosul: {last_reward['condition']}. "
                f"Kazanilan: {last_reward['points']} puan. "
                f"Tarih: {last_reward['activity_date']}."
            )
        else:
            answer = (
                "Henuz bir challenge odulu kazanmadin. "
                "Video izlemeye basla ve challenge kosullarini tamamla!"
            )

    elif intent == "suggestion":
        if active_chs:
            easiest = min(active_chs, key=lambda c: c["reward_points"])
            answer = (
                f"En kolay challenge: '{easiest['name']}' "
                f"({easiest['condition']}). "
                f"Tamamlarsan {easiest['reward_points']} puan kazanirsin. "
                f"Bugun {state['watch_minutes_today']:.0f} dakika izledin, "
                f"devam et!"
            )
        else:
            answer = "Su an aktif challenge bulunmuyor."

    else:
        answer = (
            f"Toplam {total} puanin ve {rank}. siran var. "
            f"Bugun {state['watch_minutes_today']:.0f} dakika izledin. "
            f"Daha spesifik bir soru sorabilirsin: "
            f"'kac puanim var', 'rozetim ne zaman gelir', "
            f"'ne yapmaliyim' gibi."
        )

    return {"answer": answer, "evidence": evidence, "intent": intent}


def explain(question: str, user_id: str) -> dict:
    intent = detect_intent(question)
    result = build_answer(intent, user_id)

    from engine.llm_adapter import enhance_with_llm
    llm_result = enhance_with_llm(
        question        = question,
        template_answer = result["answer"],
        evidence        = result["evidence"],
        intent          = intent,
    )

    return {
        "answer":       llm_result["answer"],
        "evidence":     result["evidence"],
        "intent":       intent,
        "llm_enhanced": llm_result["llm_enhanced"],
        "llm_error":    llm_result["llm_error"],
        "model":        llm_result["model"],
    }
