"""
AI Explanation Engine.
Karar vermez, açıklar. Tüm sayılar gerçek DB verisinden gelir.

Akış:
1. Soru Türkçe-normalize edilir (aksan katlama) → keyword intent tespiti.
2. Keyword eşleşmezse GPT-4o soruyu sınıflandırır (gerçek AI intent tespiti).
3. Intent'e göre deterministik cevap gerçek veriden kurulur.
4. GPT-4o cevabı doğal dile çevirir; LLM yoksa deterministik cevap döner.

Ezber yok: gün tahminleri kullanıcının GERÇEK son 7 gün puan ortalamasından
hesaplanır, sabit katsayı kullanılmaz.
"""

from datetime import datetime, timedelta
from engine.state_builder import build_user_state
from engine.leaderboard_engine import get_leaderboard
from engine.badge_engine import get_badge_progress
from database.setup import get_db

_TR_FOLD = str.maketrans("çğıiöşüÇĞIİÖŞÜ", "cgiiosucgiiosu")

INTENTS = [
    "streak", "compare", "today", "history", "points_query",
    "rank_query", "badge_progress", "reward_explanation", "suggestion",
]


def _normalize(text: str) -> str:
    """Türkçe aksanları katlar: 'Kaç puanım?' → 'kac puanim?'"""
    return text.translate(_TR_FOLD).lower()


def detect_intent(question: str) -> str:
    q = _normalize(question)

    if any(w in q for w in ["streak", "seri", "arka arkaya", "kesintisiz", "ust uste"]):
        return "streak"

    if any(w in q for w in ["gerideyim", "fark", "digerlerinden", "ne kadar geride",
                            "one gec", "yakala", "aradaki"]):
        return "compare"

    if any(w in q for w in ["bugun ne", "bugunku", "gunluk ozet", "bugun ne yaptim",
                            "bugun kac"]):
        return "today"

    if any(w in q for w in ["gecen hafta", "bu ay", "son 7", "haftalik", "bu hafta",
                            "gecmis", "onceki gun"]):
        return "history"

    if any(w in q for w in ["kac puan", "toplam puan", "puanim", "kac puanim",
                            "puan durum", "skorum"]):
        return "points_query"

    if any(w in q for w in ["sira", "rank", "liderlik", "kacinci", "neden bu sira",
                            "siralama"]):
        return "rank_query"

    if any(w in q for w in ["rozet", "badge", "bronze", "bronz", "silver", "gumus",
                            "gold", "altin", "platinum", "platin", "ne zaman"]):
        return "badge_progress"

    if any(w in q for w in ["neden kazandim", "nasil kazandim", "hangi odul",
                            "odulum", "odul"]):
        return "reward_explanation"

    if any(w in q for w in ["ne yapmali", "nasil artir", "oneri", "tavsiye",
                            "ne yapabilirim", "ne izlemeli", "nasil kazanirim",
                            "ipucu"]):
        return "suggestion"

    return "general"


def _daily_avg_points(user_id: str) -> float:
    """
    Kullanıcının son 7 gündeki GERÇEK günlük puan ortalaması.
    Hiç puanı yoksa aktif challenge ödüllerinin ortalaması kullanılır
    (o da yoksa 0 döner — çağıran taraf tahmini atlar).
    """
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    db  = get_db()
    row = db.execute(
        "SELECT COALESCE(SUM(points),0) AS total, "
        "COUNT(DISTINCT activity_date) AS days "
        "FROM points_ledger WHERE user_id=? AND activity_date>=?",
        (user_id, week_ago),
    ).fetchone()
    if row and row["days"] > 0 and row["total"] > 0:
        db.close()
        return float(row["total"]) / float(row["days"])
    ch = db.execute(
        "SELECT AVG(reward_points) AS avg_r FROM challenges WHERE is_active=1"
    ).fetchone()
    db.close()
    return float(ch["avg_r"]) if ch and ch["avg_r"] else 0.0


def _estimate_days(user_id: str, points_needed: float) -> int | None:
    """Gerçek tempoya göre kaç gün süreceği. Veri yoksa None (tahmin verilmez)."""
    avg = _daily_avg_points(user_id)
    if avg <= 0:
        return None
    return max(1, round(points_needed / avg))


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
            f"{state['streak_days']} günlük kesintisiz serin var. "
            f"Bugün {state['watch_minutes_today']:.0f} dakika izledin. "
            f"Seriyi korumak için bu gece de izle."
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
            days_est = _estimate_days(user_id, gap)
            tempo    = (
                f"Mevcut temponla yaklaşık {days_est} günde o sıraya ulaşırsın."
                if days_est is not None
                else "Görevleri tamamlayarak farkı kapatabilirsin."
            )
            answer = f"Bir üstündeki kullanıcıyla fark {gap} puan. {tempo}"
            evidence["gap_to_next"] = gap
            if days_est is not None:
                evidence["days_estimated"]   = days_est
                evidence["daily_avg_points"] = round(_daily_avg_points(user_id), 1)
        else:
            answer = (
                f"Liderlik tablosunun zirvesindesin! "
                f"Toplam {total} puanla 1. sıradasın."
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
            f"Bugün {state['watch_minutes_today']:.0f} dakika izledin, "
            f"{state['episodes_completed_today']} bölüm tamamladın ve "
            f"{state['today_points']} puan kazandın. "
            f"{ch_cnt['cnt']} görev tamamlandı."
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
            f"Son 7 günde {week_row['total']} puan kazandın. "
            f"Bu haftanın toplam izleme süresi: "
            f"{state['watch_minutes_7d']:.0f} dakika."
        )
        evidence["week_points"]  = int(week_row["total"])
        evidence["week_minutes"] = state["watch_minutes_7d"]

    elif intent == "points_query":
        answer = (
            f"Toplam {total} puanın var. "
            f"Bugün {state['watch_minutes_today']:.0f} dakika izledin "
            f"ve {state['today_points']} puan kazandın. "
            f"{total_users} kullanıcı arasında {rank}. sıradasın."
        )

    elif intent == "rank_query":
        if rank > 1:
            above = next(
                (e for e in leaderboard if e["rank"] == rank - 1), None
            )
            gap = (above["total_points"] - total) if above else 0
            answer = (
                f"{rank}. sıradasın ({total_users} kullanıcı arasında). "
                f"Bir üstündeki kullanıcıyla arandaki fark {gap} puan. "
                f"O kadar puan kazanırsan sıran yükselir."
            )
        else:
            answer = (
                f"Liderlik tablosunun zirvesindesin! "
                f"{total_users} kullanıcı arasında 1. sıradasın "
                f"ve {total} puanın var."
            )

    elif intent == "badge_progress":
        if progress["next_badge"]:
            days_est = _estimate_days(user_id, progress["points_needed"])
            tempo    = (
                f"Mevcut temponla yaklaşık {days_est} günde ulaşırsın."
                if days_est is not None
                else "Görevleri tamamlayarak hızlanabilirsin."
            )
            answer = (
                f"Mevcut rozet: {progress['current_badge'] or 'Yok'}. "
                f"Hedef: {progress['next_badge']} "
                f"({progress['next_threshold']} puan gerekli). "
                f"{progress['points_needed']} puana daha ihtiyacın var. {tempo}"
            )
            if days_est is not None:
                evidence["days_estimated"]   = days_est
                evidence["daily_avg_points"] = round(_daily_avg_points(user_id), 1)
        else:
            answer = (
                f"Tebrikler! En yüksek rozet PLATINUM'a ulaştın. "
                f"Toplam {total} puanın var."
            )

    elif intent == "reward_explanation":
        if last_reward:
            answer = (
                f"Son ödülünü '{last_reward['challenge_name']}' "
                f"görevini tamamlayarak kazandın. "
                f"Koşul: {last_reward['condition']}. "
                f"Kazanılan: {last_reward['points']} puan. "
                f"Tarih: {last_reward['activity_date']}."
            )
        else:
            answer = (
                "Henüz bir görev ödülü kazanmadın. "
                "Video izlemeye başla ve görev koşullarını tamamla!"
            )

    elif intent == "suggestion":
        if active_chs:
            easiest = min(active_chs, key=lambda c: c["reward_points"])
            answer = (
                f"En kolay görev: '{easiest['name']}' "
                f"({easiest['condition']}). "
                f"Tamamlarsan {easiest['reward_points']} puan kazanırsın. "
                f"Bugün {state['watch_minutes_today']:.0f} dakika izledin, "
                f"devam et!"
            )
        else:
            answer = "Şu an aktif görev bulunmuyor."

    else:
        answer = (
            f"Toplam {total} puanın ve {rank}. sıran var. "
            f"Bugün {state['watch_minutes_today']:.0f} dakika izledin. "
            f"Daha spesifik bir soru sorabilirsin: "
            f"'kaç puanım var', 'rozetim ne zaman gelir', "
            f"'ne yapmalıyım' gibi."
        )

    return {"answer": answer, "evidence": evidence, "intent": intent}


def explain(question: str, user_id: str) -> dict:
    intent        = detect_intent(question)
    intent_source = "keyword"

    # Keyword eşleşmediyse gerçek AI intent sınıflandırması dene
    if intent == "general":
        from engine.llm_adapter import classify_intent_llm
        llm_intent = classify_intent_llm(question, INTENTS)
        if llm_intent:
            intent        = llm_intent
            intent_source = "llm"

    result = build_answer(intent, user_id)

    from engine.llm_adapter import enhance_with_llm
    llm_result = enhance_with_llm(
        question        = question,
        template_answer = result["answer"],
        evidence        = result["evidence"],
        intent          = intent,
    )

    return {
        "answer":        llm_result["answer"],
        "evidence":      result["evidence"],
        "intent":        intent,
        "intent_source": intent_source,
        "llm_enhanced":  llm_result["llm_enhanced"],
        "llm_error":     llm_result["llm_error"],
        "model":         llm_result["model"],
    }
