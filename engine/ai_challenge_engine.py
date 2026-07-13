"""
engine/ai_challenge_engine.py — AI kisisel challenge uretimi.

Sabit challenge tablosuna EK OLARAK calisir; sabitleri silmez. GPT-4o kullanicinin
GERCEK DB durumuna (state + gecmis + hafiza) dayanarak kisisel challenge uretir.
Grounding: uretilen her condition guvenli whitelist ile dogrulanir; gecersizler atilir.
"""

import os
import json
from datetime import datetime, timedelta

from dotenv import load_dotenv
from openai import OpenAI

from database.setup import get_db
from engine.condition_parser import ALLOWED_FIELDS, parse_condition, get_progress
from engine.state_builder import build_user_state

load_dotenv()

LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

MIN_REWARD = 0
MAX_REWARD = 1000
AI_CHALLENGE_PRIORITY = 6


def get_challenge_history(user_id: str) -> list:
    """
    Kullanicinin son 30 gunluk challenge basarilari (points_ledger, challenge_id dolu).
    Doner: list of dict (en yeniden eskiye).
    """
    db = get_db()
    try:
        cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        rows = db.execute(
            """
            SELECT id, points, reason, challenge_id, activity_date, created_at
            FROM points_ledger
            WHERE user_id=? AND challenge_id IS NOT NULL AND activity_date >= ?
            ORDER BY id DESC
            """,
            (user_id, cutoff),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()


def validate_condition(condition: str) -> bool:
    """
    AI'in urettigi condition guvenli mi? condition_parser whitelist'i ile dogrular.
    Sadece ALLOWED_FIELDS alanlari + tanimli operator + sayisal deger kabul edilir.
    Guvensiz/gecersiz ifade -> False. Kod calistirma yok.
    """
    if not isinstance(condition, str):
        return False
    try:
        # Bos state ile dener: alan/operator/deger gecersizse ValueError firlar.
        parse_condition(condition, {})
        return True
    except Exception:
        return False


def _get_memory(user_id: str) -> dict:
    """memory_store henuz kurulmamis olabilir (Sprint 1H). Guvenli sekilde {} doner."""
    try:
        from engine import memory_store
        mem = memory_store.get(user_id)
        return mem if isinstance(mem, dict) else {}
    except Exception:
        return {}


def validate_and_store_challenges(user_id: str, challenges: list) -> list:
    """
    Her AI challenge'i dogrular; gecerlileri challenges tablosuna INSERT OR IGNORE eder.
    Kurallar: id/name/condition/reward_points alanlari var; condition whitelist-gecerli;
    reward_points 0-1000 arasi. Gecersizler atlanir ve loglanir.
    Doner: gecerli challenge listesi (dict).
    """
    db = get_db()
    valid = []
    try:
        for ch in challenges:
            if not isinstance(ch, dict):
                print("[ai_challenge] atlandi: dict degil ->", ch)
                continue
            missing = [k for k in ("id", "name", "condition", "reward_points") if k not in ch]
            if missing:
                print(f"[ai_challenge] atlandi: eksik alan {missing} -> {ch}")
                continue
            cond = ch["condition"]
            if not validate_condition(cond):
                print(f"[ai_challenge] atlandi: gecersiz condition -> {cond!r}")
                continue
            try:
                pts = int(ch["reward_points"])
            except (TypeError, ValueError):
                print(f"[ai_challenge] atlandi: reward_points sayisal degil -> {ch['reward_points']!r}")
                continue
            if not (MIN_REWARD <= pts <= MAX_REWARD):
                print(f"[ai_challenge] atlandi: reward_points aralik disi ({pts})")
                continue

            db.execute(
                "INSERT OR IGNORE INTO challenges "
                "(id, name, condition, reward_points, priority, is_active) "
                "VALUES (?,?,?,?,?,1)",
                (ch["id"], str(ch["name"]), cond, pts, AI_CHALLENGE_PRIORITY),
            )
            valid.append({
                "id": ch["id"],
                "name": str(ch["name"]),
                "condition": cond,
                "reward_points": pts,
                "reason": ch.get("reason", ""),
            })
        db.commit()
        return valid
    finally:
        db.close()


def generate_personal_challenges(user_id: str) -> list:
    """
    Kullanici icin GPT-4o ile 3 kisisel challenge uretir.
    Gercek DB state + gecmis + hafizaya dayanir (grounding). Uretilenler dogrulanip saklanir.
    """
    if not OPENAI_API_KEY:
        print("[ai_challenge] OPENAI_API_KEY yok — kisisel challenge uretilemedi.")
        return []

    today = datetime.now().strftime("%Y-%m-%d")
    state = build_user_state(user_id, today)
    memory = _get_memory(user_id)
    history = get_challenge_history(user_id)

    allowed = ", ".join(sorted(ALLOWED_FIELDS))
    ts = datetime.now().strftime("%Y%m%d%H%M%S")

    prompt = (
        f"Kullanici durumu: {json.dumps(state, ensure_ascii=False)}\n"
        f"Hafiza: {json.dumps(memory, ensure_ascii=False)}\n"
        f"Gecmis challenge basarilari: {json.dumps(history, ensure_ascii=False)}\n\n"
        "Bu kullanici icin 3 adet kisisel challenge olustur. "
        'JSON formatinda dondur: {"challenges": [ '
        '{"id": "ai_ch_...", "name": "string", '
        '"condition": "watch_minutes_today >= 90", '
        '"reward_points": 100, "reason": "Neden bu challenge onerildi?"} ] }\n\n'
        "KISITLAMALAR:\n"
        f"- condition alaninda SADECE su alanlar kullanilabilir: {allowed}\n"
        "- condition formati: '<alan> <operator> <sayi>' (or: watch_minutes_today >= 90). "
        "Operatorler: >=, <=, >, <, ==, !=\n"
        "- reward_points 50-500 arasi bir tam sayi olmali\n"
        "- Challenge'lar bu kullanicinin gercek durumuna gore kisisel olmali\n"
        "- Verilen sayilari degistirme, uydurma veri ekleme"
    )

    client = OpenAI(api_key=OPENAI_API_KEY)
    resp = client.chat.completions.create(
        model=LLM_MODEL,
        response_format={"type": "json_object"},
        temperature=0.7,
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )
    content = resp.choices[0].message.content
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        print("[ai_challenge] LLM cevabi JSON degil, atlandi.")
        return []

    raw = data.get("challenges", []) if isinstance(data, dict) else []

    # id'leri sunucu tarafinda benzersizlestir (cakisma/format garantisi).
    for i, ch in enumerate(raw):
        if isinstance(ch, dict):
            ch["id"] = f"ai_ch_{user_id}_{ts}_{i}"

    return validate_and_store_challenges(user_id, raw)


def get_active_challenges(user_id: str) -> list:
    """
    Aktif (is_active=1) tum challenge'lar: sabit + AI uretimi.
    Her biri icin condition_parser ile kullanicinin mevcut ilerleme yuzdesi eklenir.
    Doner: list of dict (percentage alani ile).
    """
    today = datetime.now().strftime("%Y-%m-%d")
    state = build_user_state(user_id, today)

    db = get_db()
    try:
        rows = db.execute(
            "SELECT id, name, condition, reward_points, priority, is_active "
            "FROM challenges WHERE is_active=1 ORDER BY priority DESC, id",
        ).fetchall()
    finally:
        db.close()

    result = []
    for r in rows:
        d = dict(r)
        try:
            prog = get_progress(d["condition"], state)
            d["percentage"] = prog["percentage"]
            d["current"] = prog["current"]
            d["target"] = prog["target"]
        except Exception:
            d["percentage"] = 0
        result.append(d)
    return result
