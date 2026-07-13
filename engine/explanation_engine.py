"""
engine/explanation_engine.py — AI aciklama motoru (LLM intent + grounded response).

Intent tamamen GPT-4o ile belirlenir (anahtar-kelime parser YOK). Her cevap gercek DB
kanitina dayanir ve grounding kontrolunden gecer. Uydurma sayi -> hallucination isareti.
"""

import os
import re
import json
import math

from dotenv import load_dotenv
from openai import OpenAI

from database.setup import get_db
from engine.state_builder import build_user_state
from engine.badge_engine import get_badge_progress
from engine.ai_leaderboard import get_leaderboard
from engine.ai_challenge_engine import get_active_challenges

load_dotenv()

LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

VALID_INTENTS = {
    "points_query", "rank_query", "badge_progress", "streak",
    "compare", "today", "history", "suggestion", "general",
}

DATE_FMT = "%Y-%m-%d"

_INTENT_INSTRUCTION = (
    "Intent kategorisi belirle. JSON dondur: {\"intent\": \"kategori\"}\n"
    "Kategoriler:\n"
    "  points_query   -> puan sorulari\n"
    "  rank_query     -> sira sorulari\n"
    "  badge_progress -> rozet sorulari\n"
    "  streak         -> seri sorulari\n"
    "  compare        -> karsilastirma sorulari\n"
    "  today          -> bugunku durum sorulari\n"
    "  history        -> gecmis sorulari\n"
    "  suggestion     -> oneri sorulari\n"
    "  general        -> diger"
)

_SYSTEM_PROMPT = (
    "Sen bir video platformu oyunlastirma asistanisin. SADECE verilen evidence "
    "verilerini kullan. Sayilari degistirme veya uydurma. Maksimum 3 cumle. Turkce yaz."
)


def _client():
    return OpenAI(api_key=OPENAI_API_KEY)


def _today():
    from datetime import datetime
    return datetime.now().strftime(DATE_FMT)


def _get_memory(user_id: str) -> dict:
    """memory_store henuz hazir degilse (Sprint 1H) guvenli {} doner."""
    try:
        from engine import memory_store
        mem = memory_store.get(user_id)
        return mem if isinstance(mem, dict) else {}
    except Exception:
        return {}


def _rank_info(user_id: str) -> dict:
    """Kullanicinin sirasi, toplam kullanici, bir ust ile puan farki (DB'den)."""
    board = get_leaderboard(1000)
    total_users = len(board)
    rank = None
    total_points = 0
    for entry in board:
        if entry["user_id"] == user_id:
            rank = entry["rank"]
            total_points = entry["total_points"]
            break
    gap_to_next = 0
    if rank and rank > 1:
        above = board[rank - 2]
        gap_to_next = int(above["total_points"]) - int(total_points)
    return {
        "rank": rank,
        "total_users": total_users,
        "gap_to_next": gap_to_next,
        "total_points": int(total_points),
    }


def _week_totals(user_id: str) -> dict:
    """Bu haftanin (Pazartesi->bugun) puani ve izleme dakikasi."""
    from datetime import datetime, timedelta
    d = datetime.strptime(_today(), DATE_FMT)
    monday = (d - timedelta(days=d.weekday())).strftime(DATE_FMT)
    today = _today()
    db = get_db()
    try:
        pts = db.execute(
            "SELECT COALESCE(SUM(points),0) AS s FROM points_ledger "
            "WHERE user_id=? AND activity_date >= ? AND activity_date <= ?",
            (user_id, monday, today),
        ).fetchone()["s"]
        mins = db.execute(
            "SELECT COALESCE(SUM(watch_minutes),0) AS s FROM user_activities "
            "WHERE user_id=? AND activity_date >= ? AND activity_date <= ?",
            (user_id, monday, today),
        ).fetchone()["s"]
        return {"week_points": int(pts), "week_minutes": float(mins)}
    finally:
        db.close()


def detect_intent(question: str, user_id: str) -> str:
    """GPT-4o ile intent belirler (json_object). Gecersiz sonuc -> 'general'."""
    if not OPENAI_API_KEY:
        return "general"
    resp = _client().chat.completions.create(
        model=LLM_MODEL,
        response_format={"type": "json_object"},
        temperature=0,
        max_tokens=30,
        messages=[{
            "role": "user",
            "content": f"Kullanici sorusu: {question}\n{_INTENT_INSTRUCTION}",
        }],
    )
    try:
        intent = json.loads(resp.choices[0].message.content).get("intent", "general")
    except json.JSONDecodeError:
        return "general"
    return intent if intent in VALID_INTENTS else "general"


def gather_evidence(intent: str, user_id: str) -> dict:
    """Intent'e gore DB'den kanit toplar. Sabit deger yok — hepsi DB'den hesaplanir."""
    today = _today()
    state = build_user_state(user_id, today)
    rank = _rank_info(user_id)

    if intent == "points_query":
        return {
            "total_points": state["total_points"],
            "today_points": state["today_points"],
            "rank": rank["rank"],
            "total_users": rank["total_users"],
        }

    if intent == "rank_query":
        return {
            "rank": rank["rank"],
            "total_users": rank["total_users"],
            "gap_to_next": rank["gap_to_next"],
        }

    if intent == "badge_progress":
        prog = get_badge_progress(user_id, state["total_points"])
        return {
            "current_badge": prog["current_badge"],
            "next_badge": prog["next_badge"],
            "next_threshold": prog["next_threshold"],
            "points_needed": prog["points_needed"],
            "percentage": prog["percentage"],
        }

    if intent == "streak":
        return {
            "streak_days": state["streak_days"],
            "watch_minutes_today": state["watch_minutes_today"],
        }

    if intent == "compare":
        week = _week_totals(user_id)
        avg_daily = week["week_points"] / 7.0
        gap = rank["gap_to_next"]
        days_estimated = math.ceil(gap / avg_daily) if avg_daily > 0 and gap > 0 else None
        return {
            "rank": rank["rank"],
            "gap_to_next": gap,
            "days_estimated": days_estimated,
        }

    if intent == "today":
        active = get_active_challenges(user_id)
        completed_today = sum(1 for c in active if c.get("percentage", 0) >= 100)
        return {
            "watch_minutes_today": state["watch_minutes_today"],
            "episodes_today": state["episodes_completed_today"],
            "today_points": state["today_points"],
            "today_challenges": completed_today,
        }

    if intent == "history":
        week = _week_totals(user_id)
        return {"week_points": week["week_points"], "week_minutes": week["week_minutes"]}

    if intent == "suggestion":
        active = get_active_challenges(user_id)
        incomplete = [c for c in active if c.get("percentage", 0) < 100]
        pool = incomplete if incomplete else active
        easiest = max(pool, key=lambda c: c.get("percentage", 0)) if pool else None
        summary = [
            {"name": c["name"], "condition": c["condition"],
             "reward_points": c["reward_points"], "percentage": c.get("percentage", 0)}
            for c in active[:5]
        ]
        return {
            "active_challenges": summary,
            "easiest_challenge": (
                {"name": easiest["name"], "condition": easiest["condition"],
                 "reward_points": easiest["reward_points"],
                 "percentage": easiest.get("percentage", 0)}
                if easiest else None
            ),
        }

    # general
    return {
        "total_points": state["total_points"],
        "rank": rank["rank"],
        "watch_minutes_today": state["watch_minutes_today"],
    }


def _collect_numbers(obj, acc):
    """evidence icindeki tum sayisal degerleri toplar (recursive)."""
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        acc.append(float(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            _collect_numbers(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _collect_numbers(v, acc)


def check_grounding(answer: str, evidence: dict) -> dict:
    """
    Cevaptaki sayilarin evidence ile uyumu.
    grounding = desteklenen sayi / cevaptaki toplam sayi (sayi yoksa 1.0).
    Cevapta evidence'da olmayan sayi varsa hallucination_detected=True.
    """
    evidence_numbers = []
    _collect_numbers(evidence, evidence_numbers)

    answer_numbers = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", answer or "")]
    if not answer_numbers:
        return {"grounding": 1.0, "hallucination_detected": False, "issues": []}

    tol = 0.5
    issues = []
    supported = 0
    for x in answer_numbers:
        if any(abs(x - e) <= tol for e in evidence_numbers):
            supported += 1
        else:
            issues.append(x)

    grounding = supported / len(answer_numbers)
    return {
        "grounding": round(grounding, 3),
        "hallucination_detected": len(issues) > 0,
        "issues": issues,
    }


def build_grounded_answer(question: str, intent: str, evidence: dict, user_id: str) -> str:
    """GPT-4o ile SADECE evidence'a dayali, max 3 cumle Turkce cevap uretir."""
    if not OPENAI_API_KEY:
        return ""
    user_msg = (
        f"Soru: {question}\n"
        f"Evidence (bu verileri kullan): {json.dumps(evidence, ensure_ascii=False)}\n"
        f"Intent: {intent}"
    )
    resp = _client().chat.completions.create(
        model=LLM_MODEL,
        temperature=0.4,
        max_tokens=200,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
    )
    return resp.choices[0].message.content.strip()


def explain(question: str, user_id: str) -> dict:
    """Tam akis: LLM intent -> DB state/memory -> evidence -> grounded cevap -> grounding kontrol."""
    intent = detect_intent(question, user_id)
    state = build_user_state(user_id, _today())          # DB state (audit icin)
    memory = _get_memory(user_id)                        # bossa {}
    evidence = gather_evidence(intent, user_id)
    answer = build_grounded_answer(question, intent, evidence, user_id)
    grounding = check_grounding(answer, evidence)

    return {
        "answer": answer,
        "evidence": evidence,
        "intent": intent,
        "grounding_score": grounding["grounding"],
        "hallucination_detected": grounding["hallucination_detected"],
        "llm_enhanced": True,
        "model": "gpt-4o",
        "state_summary": {
            "total_points": state["total_points"],
            "memory_keys": list(memory.keys()),
        },
    }
