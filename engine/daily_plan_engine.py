"""
Daily Plan Engine — Sprint 27.
Proaktif "Günün Planı": dünkü gerçek performans + aktif görev açıkları +
streak riski + sezon durumu → GPT-4o 3 maddelik somut plan yazar.

- Günde bir kez üretilir, daily_plans'a kalıcı yazılır (cache) — panel her
  açılışta GPT'ye gitmez; force=True ile elle yenilenir.
- LLM yoksa fallback plan da EZBER DEĞİL: en yakın görev, streak durumu ve
  sezon farkı gerçek sayılardan deterministik kurulur.
- LLM iş kararı vermez: tüm sayılar evidence'tan, plan sadece dil katmanı.
"""

import json
from datetime import datetime, timedelta
from database.setup import get_db
from engine.state_builder import build_user_state
from engine.challenge_tips_engine import _parse_condition, _field_value
from engine.level_engine import get_level
from engine.season_engine import season_id_for, week_bounds, _weekly_standings


def _collect_evidence(user_id: str) -> dict:
    now       = datetime.now()
    today     = now.strftime("%Y-%m-%d")
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")

    state = build_user_state(user_id, today)
    db    = get_db()

    y_act = db.execute(
        "SELECT COALESCE(SUM(watch_minutes),0) AS m, "
        "COALESCE(SUM(episodes_completed),0) AS e "
        "FROM user_activities WHERE user_id=? AND activity_date=?",
        (user_id, yesterday),
    ).fetchone()
    y_pts = db.execute(
        "SELECT COALESCE(SUM(points),0) AS p FROM points_ledger "
        "WHERE user_id=? AND activity_date=?",
        (user_id, yesterday),
    ).fetchone()

    # Aktif görevler + gerçek anlık açıklar
    chs = db.execute(
        "SELECT name, condition, reward_points FROM challenges "
        "WHERE is_active=1 ORDER BY priority DESC"
    ).fetchall()
    challenges = []
    for ch in chs:
        field, _, threshold = _parse_condition(ch["condition"])
        current = _field_value(state, field)
        gap     = max(0.0, threshold - current)
        challenges.append({
            "name":          ch["name"],
            "condition":     ch["condition"],
            "reward_points": ch["reward_points"],
            "current":       round(current, 1),
            "target":        threshold,
            "gap":           round(gap, 1),
            "done":          gap <= 0,
        })

    # Sezon: güncel sıra + bir üstle fark (gerçek haftalık standings)
    w_start, w_end = week_bounds(now)
    standings      = _weekly_standings(db, w_start, w_end)
    my   = next((s for s in standings if s["user_id"] == user_id), None)
    above = None
    if my and my["rank"] > 1:
        above = next((s for s in standings if s["rank"] == my["rank"] - 1), None)

    db.close()

    level = get_level(state["total_points"])

    # Streak riski: dün izledi ama bugün henüz izlemedi → seri kırılabilir
    streak_at_risk = (
        state["streak_days"] > 0
        and float(y_act["m"]) > 0
        and state["watch_minutes_today"] <= 0
    )

    return {
        "today":       today,
        "yesterday": {
            "watch_minutes": round(float(y_act["m"]), 1),
            "episodes":      int(y_act["e"]),
            "points":        int(y_pts["p"]),
        },
        "today_so_far": {
            "watch_minutes": round(state["watch_minutes_today"], 1),
            "episodes":      state["episodes_completed_today"],
            "points":        state["today_points"],
        },
        "streak_days":    state["streak_days"],
        "streak_at_risk": streak_at_risk,
        "total_points":   state["total_points"],
        "level": {
            "level":     level["level"],
            "title":     level["title"],
            "xp_needed": level["xp_needed"],
        },
        "challenges": challenges,
        "season": {
            "season_id": season_id_for(now),
            "my_rank":   my["rank"] if my else None,
            "my_points": my["points"] if my else 0,
            "gap_to_above": (above["points"] - my["points"]) if (my and above) else None,
            "above_username": above["username"] if above else None,
        },
    }


def _deterministic_plan(ev: dict) -> str:
    """LLM'siz plan — tamamen gerçek sayılardan kurulur."""
    lines: list[str] = []

    pending = [c for c in ev["challenges"] if not c["done"] and c["target"] > 0]
    if pending:
        nearest = min(pending, key=lambda c: c["gap"] / c["target"])
        lines.append(
            f"1. '{nearest['name']}' görevine {nearest['gap']:g} birim kaldı "
            f"({nearest['current']:g}/{nearest['target']:g}) — tamamla, "
            f"{nearest['reward_points']} puan kazan."
        )
    if ev["streak_at_risk"]:
        lines.append(
            f"{len(lines)+1}. {ev['streak_days']} günlük serin risk altında — "
            f"bugün en az bir video izleyerek seriyi koru."
        )
    s = ev["season"]
    if s["gap_to_above"] is not None:
        lines.append(
            f"{len(lines)+1}. Sezonda {s['my_rank']}. sıradasın; "
            f"{s['above_username']} ile aran {s['gap_to_above']} puan."
        )
    elif ev["level"]["xp_needed"] > 0:
        lines.append(
            f"{len(lines)+1}. Seviye {ev['level']['level']+1} için "
            f"{ev['level']['xp_needed']} puan kaldı."
        )
    if not lines:
        lines.append("1. Bugün için aktif hedef yok — katalogdan yeni bir video keşfet.")
    return "\n".join(lines[:3])


def build_daily_plan(user_id: str, force: bool = False) -> dict:
    today = datetime.now().strftime("%Y-%m-%d")

    db = get_db()
    if not force:
        cached = db.execute(
            "SELECT answer, evidence, model, created_at FROM daily_plans "
            "WHERE user_id=? AND plan_date=?",
            (user_id, today),
        ).fetchone()
        if cached:
            db.close()
            return {
                "answer":     cached["answer"],
                "evidence":   json.loads(cached["evidence"]) if cached["evidence"] else {},
                "model":      cached["model"],
                "cached":     True,
                "created_at": cached["created_at"],
                "llm_enhanced": cached["model"] != "deterministic",
            }
    db.close()

    ev       = _collect_evidence(user_id)
    fallback = _deterministic_plan(ev)

    from engine.llm_adapter import llm_call, is_llm_available, LLM_MODEL
    llm_answer = llm_call(
        system=(
            "Sen bir video platformu günlük koçusun. Kullanıcının gerçek "
            "verilerinden BUGÜN için 3 maddelik somut plan yazarsın. "
            "Her madde tek cümle, numaralı (1. 2. 3.), hangi ödüle/hedefe "
            "bağlı olduğunu söyler. Sayıları asla değiştirme, Türkçe yaz."
        ),
        user=(
            f"Kullanıcının bugünkü verileri:\n"
            f"{json.dumps(ev, ensure_ascii=False, indent=2)}\n\n"
            f"3 maddelik günün planını yaz. Öncelik sırası: streak riski varsa "
            f"önce o, sonra en yakın görev(ler), sonra sezon/seviye hedefi. "
            f"SADECE 3 numaralı madde yaz, başka bir şey ekleme."
        ),
        max_tokens=300,
        temperature=0.45,
    )

    if llm_answer:
        answer, model = llm_answer, LLM_MODEL
    else:
        answer = fallback
        model  = LLM_MODEL if is_llm_available() else "deterministic"
        if not is_llm_available():
            model = "deterministic"

    db = get_db()
    db.execute(
        "INSERT INTO daily_plans (user_id, plan_date, answer, evidence, model, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(user_id, plan_date) DO UPDATE SET "
        "answer=excluded.answer, evidence=excluded.evidence, "
        "model=excluded.model, created_at=excluded.created_at",
        (user_id, today, answer, json.dumps(ev, ensure_ascii=False),
         model, datetime.now().isoformat()),
    )
    db.commit()
    db.close()

    return {
        "answer":       answer,
        "evidence":     ev,
        "model":        model,
        "cached":       False,
        "created_at":   datetime.now().isoformat(),
        "llm_enhanced": model not in ("deterministic",),
    }
