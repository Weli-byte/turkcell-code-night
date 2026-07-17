"""
engine/goal_engine.py — AI ile kisisel hedef belirleme.

GPT-4o gercek profil/state verisiyle haftalik hedef uretir; current_value
grounding kontrolunden gecer (gercek degerle eslesmezse duzeltilir) ve hedef
hafizaya kaydedilir.
"""

import os
import json
from datetime import datetime

from dotenv import load_dotenv
from openai import OpenAI

from database.setup import get_db
from engine.state_builder import build_user_state
from engine.memory_store import get as mem_get, update as mem_update
from engine.ledger import get_total_points
from engine.personalization_engine import get_user_profile_summary

load_dotenv()

LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

DATE_FMT = "%Y-%m-%d"

_SYSTEM = (
    "Sen bir video platformu kocususun. Kullanicinin verilerine dayanarak "
    "gercekci ve motive edici hedefler belirliyorsun. SADECE verilen verileri "
    "kullan. Sayilari degistirme. Uydurma veri ekleme."
)

GOAL_TYPES = ["points", "badge", "streak", "watch_time", "challenge"]


def _real_current(goal_type: str, state: dict, user_id: str) -> int:
    """goal_type icin gercek mevcut deger (DB/state'ten)."""
    if goal_type == "points":
        return int(state["total_points"])
    if goal_type == "watch_time":
        return int(state["watch_minutes_today"])
    if goal_type == "streak":
        return int(state["streak_days"])
    if goal_type == "badge":
        return len(state.get("badges", []))
    if goal_type == "challenge":
        db = get_db()
        try:
            n = db.execute(
                "SELECT COUNT(*) FROM points_ledger "
                "WHERE user_id=? AND challenge_id IS NOT NULL AND activity_date=?",
                (user_id, state["run_date"]),
            ).fetchone()[0]
            return int(n)
        finally:
            db.close()
    return 0


def generate_goal(user_id: str) -> dict:
    """GPT-4o ile haftalik hedef uretir; grounding kontrolu + hafizaya kayit."""
    today = datetime.now().strftime(DATE_FMT)
    state = build_user_state(user_id, today)
    memory = mem_get(user_id)
    profile = get_user_profile_summary(user_id)

    prompt = (
        f"Kullanici profili: {json.dumps(profile, ensure_ascii=False)}\n"
        f"Mevcut durum: {json.dumps(state, ensure_ascii=False)}\n"
        f"Hafiza: {json.dumps(memory, ensure_ascii=False)}\n\n"
        "Bu kullanici icin bu hafta ulasilabilir 1 adet ana hedef belirle.\n"
        "JSON formatinda dondur:\n"
        "{"
        "'goal_type': 'points|badge|streak|watch_time|challenge', "
        "'title': str, 'description': str, 'target_value': int, "
        "'current_value': int, 'deadline': 'bu hafta sonu', "
        "'difficulty': 'easy|medium|hard', 'reason': str, "
        "'action_steps': [str, str, str]}\n\n"
        "KISITLAMALAR:\n"
        "- target_value mevcut degerin en fazla 2 kati olsun (mevcut 0 ise kucuk somut hedef sec)\n"
        "- Zaten ulasilmis hedefe yonlendirme\n"
        "- action_steps somut ve uygulanabilir olsun"
    )

    client = OpenAI(api_key=OPENAI_API_KEY)
    resp = client.chat.completions.create(
        model=LLM_MODEL,
        response_format={"type": "json_object"},
        temperature=0.5,
        max_tokens=500,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": prompt},
        ],
    )
    goal = json.loads(resp.choices[0].message.content)

    # Grounding: current_value gercek degerle eslesiyor mu?
    gtype = goal.get("goal_type", "points")
    if gtype not in GOAL_TYPES:
        gtype = "points"
        goal["goal_type"] = gtype
    real_current = _real_current(gtype, state, user_id)
    grounding_verified = int(goal.get("current_value", -1)) == real_current
    goal["current_value"] = real_current  # her durumda gercek deger yazilir

    goal["generated_at"] = datetime.now().isoformat()
    goal["grounding_verified"] = grounding_verified

    mem_update(user_id, "current_goal", json.dumps(goal, ensure_ascii=False))
    return goal


def get_current_goal(user_id: str):
    """Hafizadaki mevcut hedef; yoksa yeni uretir."""
    memory = mem_get(user_id)
    raw = memory.get("current_goal")
    if raw:
        try:
            return json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            pass
    return generate_goal(user_id)


def check_goal_progress(user_id: str):
    """Mevcut hedefe gore guncel ilerleme (gercek state'ten)."""
    goal = get_current_goal(user_id)
    if not goal:
        return None

    today = datetime.now().strftime(DATE_FMT)
    state = build_user_state(user_id, today)
    current = _real_current(goal.get("goal_type", "points"), state, user_id)

    target = int(goal.get("target_value", 0) or 0)
    percentage = min(100.0, (current / target * 100)) if target > 0 else 100.0
    completed = percentage >= 100

    if completed:
        message = f"Tebrikler! '{goal.get('title', 'Hedef')}' tamamlandi."
    else:
        message = (f"'{goal.get('title', 'Hedef')}' icin {target - current} "
                   f"birim kaldi (%{percentage:.0f}).")

    return {
        "goal": goal,
        "current_value": current,
        "percentage": round(percentage, 1),
        "completed": completed,
        "message": message,
    }
