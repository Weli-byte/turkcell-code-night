"""
Challenge Tips Engine — Sprint 7.
Her aktif challenge için gerçek anlık gap hesaplar, GPT-4o motivasyon metni üretir.
"""

from database.setup import get_db
from engine.state_builder import build_user_state
from datetime import datetime


def _parse_condition(cond: str) -> tuple[str, str, float]:
    """'watch_minutes_today >= 60' → ('watch_minutes_today', '>=', 60.0)"""
    for op in (">=", ">", "<=", "<", "==", "!="):
        if op in cond:
            parts = cond.split(op, 1)
            try:
                return parts[0].strip(), op, float(parts[1].strip())
            except ValueError:
                return parts[0].strip(), op, 0.0
    return cond.strip(), ">=", 0.0


_FIELD_MAP: dict[str, str] = {
    "watch_minutes_today":       "watch_minutes_today",
    "episodes_completed_today":  "episodes_completed_today",
    "watch_party_minutes_today": "watch_party_minutes_today",
    "watch_minutes_7d":          "watch_minutes_7d",
    "streak_days":               "streak_days",
}


def _field_value(state: dict, field: str) -> float:
    return float(state.get(_FIELD_MAP.get(field, field), 0))


def _template_tip(name: str, field: str, gap: float, current: float, target: float) -> str:
    if field == "watch_minutes_today":
        return f"'{name}': {gap:.0f} dakika daha izle, hedefe ulaşırsın! ({current:.0f}/{target:.0f} dk)"
    if field == "episodes_completed_today":
        return f"'{name}': {gap:.0f} bölüm daha tamamla. ({current:.0f}/{target:.0f})"
    if field == "watch_party_minutes_today":
        return f"'{name}': {gap:.0f} dakika watch party yap."
    if field == "watch_minutes_7d":
        return f"'{name}': Bu hafta {gap:.0f} dakika daha izle. ({current:.0f}/{target:.0f} dk)"
    return f"'{name}': Hedefe {gap:.0f} kaldı."


def get_challenge_tips(user_id: str) -> dict:
    """
    Tüm aktif challenge'lar için gerçek ilerleme + AI ipucu döndürür.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    state = build_user_state(user_id, today)

    db  = get_db()
    chs = db.execute(
        "SELECT * FROM challenges WHERE is_active=1 ORDER BY priority DESC"
    ).fetchall()
    db.close()

    tips: list[dict] = []

    for ch in chs:
        field, op, threshold = _parse_condition(ch["condition"])
        current = _field_value(state, field)
        pct     = min(100.0, (current / threshold * 100)) if threshold > 0 else 100.0
        gap     = max(0.0, threshold - current)
        done    = pct >= 100.0

        if done:
            tip_text = f"'{ch['name']}' tamamlandı! {ch['reward_points']} puan kazandın. 🎉"
        else:
            tip_text = _template_tip(ch["name"], field, gap, current, threshold)

        tips.append({
            "id":            ch["id"],
            "name":          ch["name"],
            "condition":     ch["condition"],
            "reward_points": ch["reward_points"],
            "current_value": round(current, 1),
            "target_value":  threshold,
            "pct":           round(pct, 1),
            "gap":           round(gap, 1),
            "done":          done,
            "tip":           tip_text,
            "llm_enhanced":  False,
        })

    # GPT-4o motivasyon metni (sadece tamamlanmamışlar için) — merkezi adapter
    from engine.llm_adapter import llm_call
    pending = [t for t in tips if not t["done"]]

    if pending:
        ch_lines = "\n".join(
            f"- {t['name']}: {t['current_value']:.0f}/{t['target_value']:.0f} "
            f"({t['pct']:.0f}% tamamlandı, {t['gap']:.0f} kaldı, {t['reward_points']} puan)"
            for t in pending
        )
        prompt = (
            f"Kullanıcının aktif görev durumu:\n{ch_lines}\n\n"
            f"Streak: {state['streak_days']} gün, "
            f"Bugün: {state['watch_minutes_today']:.0f} dk izleme, "
            f"{state['today_points']} puan.\n\n"
            f"Her tamamlanmamış görev için tam olarak 1 satır motivasyon mesajı yaz. "
            f"Görev adıyla başla. Türkçe, enerjik, kısa. "
            f"Kesinlikle {len(pending)} satır yaz, başka bir şey ekleme."
        )
        llm_answer = llm_call(
            system="Sen bir oyunlaştırma motivasyon asistanısın. Kullanıcıları kısa, enerjik Türkçe mesajlarla motive et.",
            user=prompt,
            max_tokens=250,
            temperature=0.5,
        )
        if llm_answer:  # LLM yoksa/hatalıysa template ipuçları zaten hazır
            lines = [l.strip() for l in llm_answer.split("\n") if l.strip()]
            for i, t in enumerate(pending):
                if i < len(lines):
                    t["tip"]          = lines[i]
                    t["llm_enhanced"] = True

    return {
        "tips":  tips,
        "today": today,
        "state": {
            "watch_minutes_today": round(state["watch_minutes_today"], 1),
            "streak_days":         state["streak_days"],
            "today_points":        state["today_points"],
        },
    }
