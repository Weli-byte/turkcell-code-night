"""
engine/learning_pipeline.py — AI'in kullanicidan surekli ogrenmesi.

Geri bildirimlerden GPT-4o ile tercih oruntusu cikarir (grounding: guven skoru
gercek feedback sayisindan hesaplanir, LLM'e birakilmaz) ve tur tercihlerini
gercek izleme verisinden deterministik gunceller. Sonuclar hafizaya yazilir.
"""

import os
import json
from datetime import datetime

from dotenv import load_dotenv
from openai import OpenAI

from database.setup import get_db
from engine.memory_store import get as mem_get, update as mem_update, update_batch
from engine.feedback_loop import get_user_feedback, get_feedback_stats

load_dotenv()

LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

MIN_FEEDBACK_TO_LEARN = 3

_SYSTEM = (
    "Sen bir AI ogrenme motorusun. Kullanicinin geri bildirimlerinden tercih "
    "oruntuleri cikariyorsun. SADECE verilen verileri analiz et. Uydurma "
    "cikarim yapma. JSON formatinda dondur."
)

PATTERN_FIELDS = [
    "preferred_challenge_types",
    "avoided_challenge_types",
    "preferred_content_length",
    "social_preference",
    "motivation_signals",
    "learning_confidence",
]


def trigger(user_id: str) -> bool:
    """Her feedback sonrasi cagrilir. Yeterli veri yoksa erken cikar."""
    stats = get_feedback_stats(user_id)
    if stats["total"] < MIN_FEEDBACK_TO_LEARN:
        return False

    learn_from_feedback(user_id)
    update_genre_preferences(user_id)
    return True


def learn_from_feedback(user_id: str) -> dict:
    """Geri bildirimlerden GPT-4o ile oruntu cikarir; hafizaya kaydeder."""
    feedback = get_user_feedback(user_id, limit=20)
    stats = get_feedback_stats(user_id)
    memory = mem_get(user_id)

    if not feedback:
        return {}

    patterns = {}
    if OPENAI_API_KEY:
        try:
            client = OpenAI(api_key=OPENAI_API_KEY)
            resp = client.chat.completions.create(
                model=LLM_MODEL,
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=300,
                messages=[
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": (
                        f"Geri bildirimler: {json.dumps(feedback, ensure_ascii=False)}\n"
                        f"Istatistikler: {json.dumps(stats, ensure_ascii=False)}\n"
                        f"Mevcut hafiza: {json.dumps(memory, ensure_ascii=False)}\n\n"
                        "Su alanlari JSON olarak dondur:\n"
                        "{'preferred_challenge_types': [str], "
                        "'avoided_challenge_types': [str], "
                        "'preferred_content_length': 'short|medium|long', "
                        "'social_preference': bool, "
                        "'motivation_signals': [str], "
                        "'learning_confidence': float}\n\n"
                        "NOT: learning_confidence feedback sayisina gore 0-1 arasi olsun. "
                        "Az veri = dusuk guven."
                    )},
                ],
            )
            patterns = json.loads(resp.choices[0].message.content)
        except Exception as e:
            print("[learning] LLM analiz hatasi:", e)
            patterns = {}

    # Grounding: guven skoru LLM'e birakilmaz — gercek feedback sayisindan.
    patterns["learning_confidence"] = round(min(1.0, stats["total"] / 20.0), 3)

    # Sadece beklenen alanlari sakla
    to_store = {k: v for k, v in patterns.items() if k in PATTERN_FIELDS}
    if to_store:
        update_batch(user_id, to_store)

    learned_at = datetime.now().isoformat()
    mem_update(user_id, "last_learned_at", learned_at)

    to_store["learned_at"] = learned_at
    return to_store


def update_genre_preferences(user_id: str) -> list:
    """Gercek izleme verisinden en cok izlenen 3 tur (deterministik, AI'sisiz)."""
    db = get_db()
    try:
        rows = db.execute(
            """
            SELECT cc.genre AS genre, COALESCE(SUM(ws.watch_minutes),0) AS mins
            FROM watch_sessions ws
            JOIN content_catalog cc ON cc.id = ws.content_id
            WHERE ws.user_id=? AND cc.genre IS NOT NULL
            GROUP BY cc.genre
            ORDER BY mins DESC, cc.genre ASC
            """,
            (user_id,),
        ).fetchall()
    finally:
        db.close()

    top_genres = [r["genre"] for r in rows if float(r["mins"]) > 0][:3]
    mem_update(user_id, "genre_preferences", top_genres)
    return top_genres


def learn_from_user(user_id: str) -> dict:
    """Tum ogrenme adimlari (manuel tetikleme)."""
    feedback_patterns = learn_from_feedback(user_id)
    genre_preferences = update_genre_preferences(user_id)

    return {
        "user_id": user_id,
        "feedback_patterns": feedback_patterns,
        "genre_preferences": genre_preferences,
        "learned_at": datetime.now().isoformat(),
    }


def get_learning_status(user_id: str) -> dict:
    """Ogrenme sisteminin durumu."""
    stats = get_feedback_stats(user_id)
    memory = mem_get(user_id)

    patterns_learned = [k for k in PATTERN_FIELDS if k in memory]

    return {
        "total_feedback": stats["total"],
        "acceptance_rate": stats["acceptance_rate"],
        "patterns_learned": patterns_learned,
        "genre_preferences": memory.get("genre_preferences", []),
        "last_learned_at": memory.get("last_learned_at"),
        "confidence": round(min(1.0, stats["total"] / 20.0), 3),
        "ready_to_learn": stats["total"] >= MIN_FEEDBACK_TO_LEARN,
    }
