"""
Rivalry Engine — Sprint 28.
İki kullanıcının GERÇEK istatistiklerinden kafa kafaya kıyas + GPT-4o
taktik analizi.

- Tüm sayılar DB'den; yakalama süresi tahmini iki tarafın GERÇEK son 7 gün
  temposundan türetilir (sabit katsayı yok).
- GPT-4o sadece anlatır; kim önde / fark / tempo deterministik hesaplanır.
- LLM yoksa deterministik kıyas metni döner.
"""

import json
from datetime import datetime, timedelta
from database.setup import get_db
from engine.state_builder import build_user_state
from engine.level_engine import get_level


def _profile(db, user_id: str, username: str) -> dict:
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    total = db.execute(
        "SELECT COALESCE(SUM(points),0) AS t FROM points_ledger WHERE user_id=?",
        (user_id,),
    ).fetchone()["t"]
    week_pts = db.execute(
        "SELECT COALESCE(SUM(points),0) AS t FROM points_ledger "
        "WHERE user_id=? AND activity_date>=?",
        (user_id, week_ago),
    ).fetchone()["t"]
    week_min = db.execute(
        "SELECT COALESCE(SUM(watch_minutes),0) AS m FROM user_activities "
        "WHERE user_id=? AND activity_date>=?",
        (user_id, week_ago),
    ).fetchone()["m"]
    challenges_7d = db.execute(
        "SELECT COUNT(*) AS c FROM points_ledger "
        "WHERE user_id=? AND activity_date>=? AND challenge_id IS NOT NULL",
        (user_id, week_ago),
    ).fetchone()["c"]
    badges = db.execute(
        "SELECT COUNT(*) AS c FROM user_badges WHERE user_id=?", (user_id,)
    ).fetchone()["c"]
    achievements = db.execute(
        "SELECT COUNT(*) AS c FROM user_achievements WHERE user_id=?", (user_id,)
    ).fetchone()["c"]

    state = build_user_state(user_id)
    level = get_level(int(total))

    return {
        "username":        username,
        "total_points":    int(total),
        "level":           level["level"],
        "level_title":     level["title"],
        "week_points":     int(week_pts),
        "week_minutes":    round(float(week_min), 1),
        "daily_tempo":     round(int(week_pts) / 7.0, 1),  # gerçek 7g ortalaması
        "streak_days":     state["streak_days"],
        "challenges_7d":   int(challenges_7d),
        "badges":          int(badges),
        "achievements":    int(achievements),
    }


def build_rivalry(user_id: str, rival_username: str) -> dict | None:
    """Kıyas raporu. Rakip yoksa None; kendinle kıyas ValueError."""
    db    = get_db()
    rival = db.execute(
        "SELECT id, username FROM users WHERE username=?", (rival_username,)
    ).fetchone()
    if not rival:
        db.close()
        return None
    if rival["id"] == user_id:
        db.close()
        raise ValueError("Kendinle kıyaslanamazsın")

    me_name = db.execute(
        "SELECT username FROM users WHERE id=?", (user_id,)
    ).fetchone()["username"]

    me    = _profile(db, user_id, me_name)
    other = _profile(db, rival["id"], rival["username"])
    db.close()

    # Deterministik kıyas
    point_diff = other["total_points"] - me["total_points"]  # + → rakip önde
    tempo_diff = me["daily_tempo"] - other["daily_tempo"]    # + → ben hızlıyım
    leader     = other["username"] if point_diff > 0 else (
                 me["username"] if point_diff < 0 else "berabere")

    catch_up_days = None
    if point_diff > 0 and tempo_diff > 0:
        catch_up_days = max(1, round(point_diff / tempo_diff))
    elif point_diff < 0 and tempo_diff < 0:
        # rakip beni yakalıyor
        catch_up_days = -max(1, round(-point_diff / -tempo_diff))

    evidence = {
        "me":    me,
        "rival": other,
        "comparison": {
            "point_diff":    abs(point_diff),
            "leader":        leader,
            "my_daily_tempo":    me["daily_tempo"],
            "rival_daily_tempo": other["daily_tempo"],
            "catch_up_days": catch_up_days,  # + gün: yakalarım; - gün: yakalanırım
        },
    }

    # Deterministik özet (fallback + LLM tabanı)
    if point_diff == 0:
        base = f"{me['username']} ve {other['username']} {me['total_points']} puanla berabere!"
    elif point_diff > 0:
        base = (f"{other['username']} {point_diff} puan önde. "
                f"Günlük tempon {me['daily_tempo']:g} puan, onunki "
                f"{other['daily_tempo']:g}. "
                + (f"Bu tempoyla yaklaşık {catch_up_days} günde yakalarsın."
                   if catch_up_days and catch_up_days > 0
                   else "Yakalamak için temponu artırmalısın."))
    else:
        base = (f"{-point_diff} puan öndesin. "
                + (f"Ama dikkat: {other['username']} daha hızlı — "
                   f"yaklaşık {-catch_up_days} günde seni yakalayabilir."
                   if catch_up_days and catch_up_days < 0
                   else "Tempoyu korursan lider kalırsın."))

    from engine.llm_adapter import llm_call, is_llm_available, LLM_MODEL
    llm_answer = llm_call(
        system=(
            "Sen bir e-spor yorumcusu gibi konuşan oyunlaştırma analistisin. "
            "İki oyuncunun GERÇEK istatistiklerini kıyaslar, kısa taktik "
            "analiz yaparsın. Sayıları asla değiştirme, Türkçe yaz."
        ),
        user=(
            f"İki oyuncunun gerçek verileri:\n"
            f"{json.dumps(evidence, ensure_ascii=False, indent=2)}\n\n"
            f"'{me['username']}' perspektifinden 3-4 cümlelik taktik kıyas "
            f"yaz: kim önde ve neden, tempo/streak/görev farklarından hangisi "
            f"belirleyici, yakalamak/önde kalmak için tek somut hamle öner."
        ),
        max_tokens=320,
        temperature=0.5,
    )

    if llm_answer:
        answer, llm_enhanced, model = llm_answer, True, LLM_MODEL
    else:
        answer, llm_enhanced = base, False
        model = LLM_MODEL if is_llm_available() else "deterministic"

    return {
        "answer":       answer,
        "evidence":     evidence,
        "llm_enhanced": llm_enhanced,
        "model":        model,
    }
