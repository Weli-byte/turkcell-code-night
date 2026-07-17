"""
engine/feedback_loop.py — AI kararlarina kullanici geri bildirimi.

ai_feedback tablosu APPEND-ONLY tutulur: bu dosyada SADECE INSERT ve SELECT
vardir (points_ledger ile ayni kural). Boylece geri bildirim gecmisi
denetlenebilir kalir.
"""

import json
from datetime import datetime

from database.setup import get_db

FEEDBACK_TYPES = ["accepted", "rejected", "ignored"]
DECISION_TYPES = [
    "challenge", "recommendation", "goal",
    "badge", "leaderboard", "ai_response",
]


def record_feedback(user_id: str, decision_id: str, decision_type: str,
                    feedback_type: str, context: dict = None) -> bool:
    """
    Geri bildirimi kaydeder (sadece INSERT) ve ogrenme pipeline'ini tetikler.
    Gecersiz tip -> ValueError.
    """
    if feedback_type not in FEEDBACK_TYPES:
        raise ValueError(f"Gecersiz feedback_type: {feedback_type}")
    if decision_type not in DECISION_TYPES:
        raise ValueError(f"Gecersiz decision_type: {decision_type}")

    db = get_db()
    try:
        db.execute(
            "INSERT INTO ai_feedback "
            "(user_id, decision_id, decision_type, feedback_type, context, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (user_id, decision_id, decision_type, feedback_type,
             json.dumps(context, ensure_ascii=False) if context else None,
             datetime.now().isoformat()),
        )
        db.commit()
    finally:
        db.close()

    # Ogrenme pipeline'i (gec import: dairesel bagimliligi kirar).
    # Ogrenme hatasi geri bildirim kaydini bozmamali.
    try:
        from engine.learning_pipeline import trigger as lp_trigger
        lp_trigger(user_id)
    except Exception as e:
        print("[feedback] ogrenme tetikleme hatasi:", e)

    return True


def get_user_feedback(user_id: str, decision_type: str = None,
                      limit: int = 50) -> list:
    """Kullanicinin geri bildirimleri, en yeniden eskiye."""
    db = get_db()
    try:
        if decision_type:
            rows = db.execute(
                "SELECT id, user_id, decision_id, decision_type, feedback_type, "
                "context, created_at FROM ai_feedback "
                "WHERE user_id=? AND decision_type=? ORDER BY id DESC LIMIT ?",
                (user_id, decision_type, limit),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT id, user_id, decision_id, decision_type, feedback_type, "
                "context, created_at FROM ai_feedback "
                "WHERE user_id=? ORDER BY id DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()


def get_feedback_stats(user_id: str) -> dict:
    """Geri bildirim istatistikleri (DB aggregation)."""
    db = get_db()
    try:
        totals = db.execute(
            "SELECT feedback_type, COUNT(*) AS n FROM ai_feedback "
            "WHERE user_id=? GROUP BY feedback_type",
            (user_id,),
        ).fetchall()
        by_type_rows = db.execute(
            "SELECT decision_type, feedback_type, COUNT(*) AS n FROM ai_feedback "
            "WHERE user_id=? GROUP BY decision_type, feedback_type",
            (user_id,),
        ).fetchall()
    finally:
        db.close()

    counts = {"accepted": 0, "rejected": 0, "ignored": 0}
    for r in totals:
        counts[r["feedback_type"]] = int(r["n"])
    total = sum(counts.values())

    by_type = {}
    for r in by_type_rows:
        dt = r["decision_type"]
        by_type.setdefault(dt, {"accepted": 0, "rejected": 0, "ignored": 0})
        by_type[dt][r["feedback_type"]] = int(r["n"])

    return {
        "total": total,
        "accepted": counts["accepted"],
        "rejected": counts["rejected"],
        "ignored": counts["ignored"],
        "acceptance_rate": round(counts["accepted"] / total, 3) if total > 0 else 0.0,
        "by_type": by_type,
    }


def get_rejected_decisions(user_id: str, decision_type: str = None) -> list:
    """Reddedilen karar id'leri; hafizadaki rejected_suggestions ile senkron."""
    db = get_db()
    try:
        if decision_type:
            rows = db.execute(
                "SELECT DISTINCT decision_id FROM ai_feedback "
                "WHERE user_id=? AND feedback_type='rejected' AND decision_type=?",
                (user_id, decision_type),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT DISTINCT decision_id FROM ai_feedback "
                "WHERE user_id=? AND feedback_type='rejected'",
                (user_id,),
            ).fetchall()
    finally:
        db.close()

    rejected = [r["decision_id"] for r in rows]

    # Hafiza senkronu (tekrarsiz ekleme)
    try:
        from engine.memory_store import add_rejected_suggestion
        for rid in rejected:
            add_rejected_suggestion(user_id, rid)
    except Exception as e:
        print("[feedback] hafiza senkron hatasi:", e)

    return rejected


def should_retry_decision(user_id: str, decision_id: str) -> bool:
    """
    Karar tekrar onerilmeli mi?
    - Reddedildiyse: hayir.
    - Kabul edildiyse: evet (basarili oneri).
    - Sadece gormezden gelindiyse: bir kez daha denenebilir (tek ignore'a evet).
    - Hic geri bildirim yoksa: evet.
    """
    db = get_db()
    try:
        rows = db.execute(
            "SELECT feedback_type FROM ai_feedback "
            "WHERE user_id=? AND decision_id=? ORDER BY id DESC",
            (user_id, decision_id),
        ).fetchall()
    finally:
        db.close()

    types = [r["feedback_type"] for r in rows]
    if "rejected" in types:
        return False
    if "accepted" in types:
        return True
    ignored_count = types.count("ignored")
    return ignored_count <= 1
