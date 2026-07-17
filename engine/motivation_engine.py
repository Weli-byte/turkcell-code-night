"""
engine/motivation_engine.py — Motivasyon tipi analizi ve kisisel mesajlar.

Tip, gercek davranis verisinden deterministik cikarilir (hafizada cache'lenir);
uzun gecmiste GPT-4o ile dogrulanir. Mesajlar gercek state verisiyle uretilir.

Not: leaderboard goruntuleme sayisi sistemde izlenmiyor; competitive skoru icin
deterministik vekil olarak tamamlanan challenge sayisi kullanilir (yaris gostergesi).
"""

import os
import json
from datetime import datetime, timedelta

from dotenv import load_dotenv
from openai import OpenAI

from database.setup import get_db
from engine.memory_store import get as mem_get, update as mem_update
from engine.ledger import get_history, get_total_points
from engine.state_builder import build_user_state

load_dotenv()

LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

DATE_FMT = "%Y-%m-%d"

MOTIVATION_TYPES = [
    "competitive",
    "social",
    "individual",
    "achievement",
]

# Deterministik normalizasyon esikleri
_NORM = {
    "social": 120.0,        # watch party dakikasi
    "competitive": 5.0,     # tamamlanan challenge sayisi (vekil)
    "individual": 7.0,      # streak gun
    "achievement": 4.0,     # rozet sayisi
}

# Tipe gore sistem sabiti ipuclari (spec: burada sabit listeye izin var)
_TIPS = {
    "competitive": [
        "Liderlik tablosunu her gun kontrol et — rakiplerinle farki gor.",
        "Yuksek puanli challenge'lara oncelik ver.",
        "Haftalik siralamada yukselmek icin gun sonunda eksik puani kapat.",
    ],
    "social": [
        "Watch Party baslatarak arkadaslarinla birlikte izle.",
        "Benzer zevkli kullanicilari kesfet ve onlarla yarisin.",
        "Sosyal rozetler icin birlikte izleme surene odaklan.",
    ],
    "individual": [
        "Gunluk serini koru — her gun en az bir video izle.",
        "Kendi rekorunu kirmaya odaklan, baskalarini dusunme.",
        "Kisisel hedefini kucuk gunluk adimlara bol.",
    ],
    "achievement": [
        "Bir sonraki rozete ne kadar kaldigini takip et.",
        "Challenge'lari tek tek tamamlayarak koleksiyonunu buyut.",
        "Zor challenge'lar daha cok puan verir — cesaret et.",
    ],
}


def get_challenge_history(user_id: str) -> list:
    """Son 30 gunun challenge kayitlari (points_ledger, challenge_id dolu)."""
    cutoff = (datetime.now() - timedelta(days=30)).strftime(DATE_FMT)
    db = get_db()
    try:
        rows = db.execute(
            "SELECT id, points, reason, challenge_id, activity_date, created_at "
            "FROM points_ledger "
            "WHERE user_id=? AND challenge_id IS NOT NULL AND activity_date >= ? "
            "ORDER BY id DESC",
            (user_id, cutoff),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()


def _behavior_scores(user_id: str) -> dict:
    """Gercek davranis metriklerinden 0-1 normalize skorlar."""
    today = datetime.now().strftime(DATE_FMT)
    state = build_user_state(user_id, today)

    db = get_db()
    try:
        party = float(db.execute(
            "SELECT COALESCE(SUM(watch_party_minutes),0) FROM user_activities "
            "WHERE user_id=?",
            (user_id,),
        ).fetchone()[0])
        completions = int(db.execute(
            "SELECT COUNT(*) FROM points_ledger "
            "WHERE user_id=? AND challenge_id IS NOT NULL",
            (user_id,),
        ).fetchone()[0])
        badges = int(db.execute(
            "SELECT COUNT(*) FROM user_badges WHERE user_id=?",
            (user_id,),
        ).fetchone()[0])
    finally:
        db.close()

    streak = int(state["streak_days"])

    return {
        "social": min(1.0, party / _NORM["social"]),
        "competitive": min(1.0, completions / _NORM["competitive"]),
        "individual": min(1.0, streak / _NORM["individual"]),
        "achievement": min(1.0, badges / _NORM["achievement"]),
    }


def analyze_motivation_type(user_id: str) -> str:
    """
    Motivasyon tipini belirler. Hafizada varsa cache'ten doner (deterministik).
    Yoksa davranistan hesaplar; uzun gecmiste (>5 kayit) GPT-4o ile dogrular
    ve sonucu hafizaya yazar.
    """
    memory = mem_get(user_id)
    cached = memory.get("motivation_type")
    if cached in MOTIVATION_TYPES:
        return cached

    history = get_challenge_history(user_id)
    scores = _behavior_scores(user_id)

    # En yuksek skor; esitlikte 'achievement' varsayilani kazansin diye
    # once sabit oncelik sirasiyla gez.
    best_type = "achievement"
    best_score = scores["achievement"]
    for t in ("competitive", "social", "individual"):
        if scores[t] > best_score:
            best_type = t
            best_score = scores[t]

    final_type = best_type

    # AI dogrulamasi (uzun gecmiste)
    if len(history) > 5 and OPENAI_API_KEY:
        try:
            client = OpenAI(api_key=OPENAI_API_KEY)
            resp = client.chat.completions.create(
                model=LLM_MODEL,
                response_format={"type": "json_object"},
                temperature=0,
                max_tokens=30,
                messages=[
                    {"role": "system", "content": (
                        "Kullanicinin davranis gecmisine gore motivasyon tipini "
                        "belirle. Sadece su degerlerden birini dondur: "
                        "competitive | social | individual | achievement. "
                        "JSON: {\"motivation_type\": \"...\"}"
                    )},
                    {"role": "user", "content": (
                        f"Davranis gecmisi: {json.dumps(history[-5:], ensure_ascii=False)}\n"
                        f"Hesaplanan tip: {best_type}\n"
                        "Dogrula veya duzelt."
                    )},
                ],
            )
            ai_type = json.loads(resp.choices[0].message.content).get("motivation_type")
            if ai_type in MOTIVATION_TYPES:
                final_type = ai_type
        except Exception as e:
            print("[motivation] AI dogrulama hatasi:", e)

    mem_update(user_id, "motivation_type", final_type)
    return final_type


def generate_motivation_message(user_id: str, context: str = "general") -> str:
    """Motivasyon tipine + gercek duruma gore kisa kisisel mesaj (GPT-4o)."""
    motivation_type = analyze_motivation_type(user_id)
    today = datetime.now().strftime(DATE_FMT)
    state = build_user_state(user_id, today)

    if not OPENAI_API_KEY:
        # Anahtar yoksa deterministik ipucundan mesaj
        return _TIPS[motivation_type][0]

    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model=LLM_MODEL,
            temperature=0.6,
            max_tokens=100,
            messages=[
                {"role": "system", "content": (
                    "Sen bir video platformu kocususun. Kullanicinin motivasyon "
                    "tipine gore kisa (1-2 cumle) motive edici mesaj yaz. "
                    "Gercek veriler kullan. Uydurma yazma. Turkce yaz."
                )},
                {"role": "user", "content": (
                    f"Motivasyon tipi: {motivation_type}\n"
                    f"Baglam: {context}\n"
                    f"Kullanici durumu: {json.dumps(state, ensure_ascii=False)}"
                )},
            ],
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print("[motivation] mesaj uretim hatasi:", e)
        return _TIPS[motivation_type][0]


def get_motivation_summary(user_id: str) -> dict:
    """Tum motivasyon bilgilerinin ozeti."""
    from engine.goal_engine import get_current_goal, check_goal_progress

    motivation_type = analyze_motivation_type(user_id)
    message = generate_motivation_message(user_id, "general")

    try:
        current_goal = get_current_goal(user_id)
    except Exception as e:
        print("[motivation] hedef alinamadi:", e)
        current_goal = None

    try:
        goal_progress = check_goal_progress(user_id) if current_goal else None
    except Exception as e:
        print("[motivation] ilerleme alinamadi:", e)
        goal_progress = None

    return {
        "motivation_type": motivation_type,
        "message": message,
        "current_goal": current_goal,
        "goal_progress": goal_progress,
        "tips": list(_TIPS[motivation_type]),
    }
