"""
engine/model_router.py — Multi-provider AI model yonlendirici + failover.

Gorev tipine gore deterministik model secimi; gercek API ping'li health check
(5 dk cache), saglik dususunde otomatik fallback + ai_calls_log'a failover
kaydi. Token maliyeti hesaplama ve kullanim istatistikleri dahil.
"""

import os
import json
import time
from datetime import datetime, timedelta

from dotenv import load_dotenv
from openai import OpenAI

from database.setup import get_db

load_dotenv()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

MODEL_REGISTRY = {
    "fast_response":     "gpt-4o-mini",
    "complex_reasoning": "gpt-4o",
    "creative":          "gpt-4o",
    "embedding":         "text-embedding-3-small",
    "intent_detection":  "gpt-4o",
    "challenge_gen":     "gpt-4o",
    "explanation":       "gpt-4o",
    "motivation":        "gpt-4o-mini",
    "fallback":          "gpt-4o-mini",
}

PROVIDER_REGISTRY = {
    "gpt-4o":                 "openai",
    "gpt-4o-mini":            "openai",
    "text-embedding-3-small": "openai",
}

TASK_TYPES = list(MODEL_REGISTRY.keys())

COST_PER_1K_TOKENS = {
    "gpt-4o":      {"input": 0.005,   "output": 0.015},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "text-embedding-3-small": {"input": 0.00002, "output": 0},
}

# ── KISIM 2: Health check (in-memory cache) ───────────────────────────

_health_cache = {}
HEALTH_CACHE_TTL = 300  # saniye (5 dakika)


def health_check(model: str) -> bool:
    """
    Modelin erisilebilirligini GERCEK API ping'iyle kontrol eder.
    Sonuc 5 dk cache'lenir. Hata -> False (exception firlatmaz).
    """
    cached = _health_cache.get(model)
    if cached:
        age = (datetime.now() - cached["checked_at"]).total_seconds()
        if age < HEALTH_CACHE_TTL:
            return cached["status"]

    provider = PROVIDER_REGISTRY.get(model, "openai")
    status = False
    latency_ms = None

    t0 = time.perf_counter()
    try:
        if provider == "openai":
            if not OPENAI_API_KEY:
                raise RuntimeError("OPENAI_API_KEY tanimli degil")
            client = OpenAI(api_key=OPENAI_API_KEY, timeout=5)
            client.models.retrieve(model)  # hafif ping — token harcamaz
            status = True
        latency_ms = int((time.perf_counter() - t0) * 1000)
    except Exception as e:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        print(f"[model_router] health check hatasi ({model}):", e)
        status = False

    _health_cache[model] = {
        "status": status,
        "checked_at": datetime.now(),
        "latency_ms": latency_ms,
    }
    return status


# ── KISIM 4: Failover logging ─────────────────────────────────────────

def log_failover(task_type: str, failed_model: str, fallback_model: str) -> None:
    """Failover olayini ai_calls_log'a kaydeder (audit)."""
    db = get_db()
    try:
        db.execute(
            "INSERT INTO ai_calls_log "
            "(model, tokens_in, tokens_out, latency_ms, grounding_score, cost, "
            " user_id, intent, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (failed_model, 0, 0, 0, None, 0.0, None,
             f"failover:{task_type}", datetime.now().isoformat()),
        )
        db.commit()
    finally:
        db.close()
    print(f"[model_router] FAILOVER: {task_type}: {failed_model} -> {fallback_model}")


# ── KISIM 3: Ana route ────────────────────────────────────────────────

def route(task_type: str) -> str:
    """
    Gorev tipine gore model secer (deterministik). Bilinmeyen tip -> fallback.
    Model sagliksizsa fallback'e duser ve olayi loglar.
    """
    if task_type not in TASK_TYPES:
        return MODEL_REGISTRY["fallback"]

    model = MODEL_REGISTRY.get(task_type, MODEL_REGISTRY["fallback"])

    if not health_check(model):
        fallback = MODEL_REGISTRY["fallback"]
        log_failover(task_type, model, fallback)
        return fallback

    return model


# ── KISIM 5: Model bilgisi ────────────────────────────────────────────

def get_model_info(model: str) -> dict:
    """Model bilgisi (cache'ten okur, ping YAPMAZ)."""
    cached = _health_cache.get(model)
    return {
        "model": model,
        "provider": PROVIDER_REGISTRY.get(model, "openai"),
        "healthy": cached["status"] if cached else False,
        "last_checked": cached["checked_at"].isoformat() if cached else None,
        "latency_ms": cached["latency_ms"] if cached else None,
        "task_types": sorted(
            t for t, m in MODEL_REGISTRY.items() if m == model
        ),
    }


def get_all_model_status() -> list:
    """Kayitli tum modellerin durumu (sadece cache — ping yapmaz)."""
    models = sorted(set(MODEL_REGISTRY.values()))
    return [get_model_info(m) for m in models]


# ── KISIM 6: Token ve maliyet takibi ─────────────────────────────────

def calculate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    """Cagri maliyeti (USD). Bilinmeyen model -> 0."""
    rates = COST_PER_1K_TOKENS.get(model)
    if not rates:
        return 0.0
    return (tokens_in / 1000.0) * rates["input"] + \
           (tokens_out / 1000.0) * rates["output"]


def log_model_call(model: str, task_type: str, tokens_in: int, tokens_out: int,
                   latency_ms: int, grounding_score: float = None,
                   user_id: str = None, intent: str = None) -> None:
    """Model cagrisini maliyetiyle birlikte ai_calls_log'a kaydeder."""
    cost = calculate_cost(model, tokens_in, tokens_out)
    db = get_db()
    try:
        db.execute(
            "INSERT INTO ai_calls_log "
            "(model, tokens_in, tokens_out, latency_ms, grounding_score, cost, "
            " user_id, intent, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (model, int(tokens_in), int(tokens_out), int(latency_ms),
             grounding_score, cost, user_id,
             intent or f"task:{task_type}", datetime.now().isoformat()),
        )
        db.commit()
    finally:
        db.close()


# ── KISIM 7: Istatistikler ────────────────────────────────────────────

def get_usage_stats(hours: int = 24) -> dict:
    """Son X saatin kullanim istatistikleri (DB aggregation)."""
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    db = get_db()
    try:
        totals = db.execute(
            """
            SELECT COUNT(*)                                  AS calls,
                   COALESCE(SUM(tokens_in + tokens_out), 0)  AS tokens,
                   COALESCE(SUM(cost), 0)                    AS cost,
                   COALESCE(AVG(latency_ms), 0)              AS avg_latency
            FROM ai_calls_log WHERE created_at >= ?
            """,
            (cutoff,),
        ).fetchone()

        by_model_rows = db.execute(
            """
            SELECT model,
                   COUNT(*)                                 AS calls,
                   COALESCE(SUM(tokens_in + tokens_out), 0) AS tokens,
                   COALESCE(SUM(cost), 0)                   AS cost,
                   COALESCE(AVG(latency_ms), 0)             AS avg_latency
            FROM ai_calls_log WHERE created_at >= ?
            GROUP BY model ORDER BY model
            """,
            (cutoff,),
        ).fetchall()

        failover_count = int(db.execute(
            "SELECT COUNT(*) FROM ai_calls_log "
            "WHERE created_at >= ? AND intent LIKE 'failover:%'",
            (cutoff,),
        ).fetchone()[0])
    finally:
        db.close()

    by_model = {
        r["model"]: {
            "calls": int(r["calls"]),
            "tokens": int(r["tokens"]),
            "cost": round(float(r["cost"]), 6),
            "avg_latency": round(float(r["avg_latency"]), 1),
        }
        for r in by_model_rows
    }

    return {
        "period_hours": hours,
        "total_calls": int(totals["calls"]),
        "total_tokens": int(totals["tokens"]),
        "total_cost": round(float(totals["cost"]), 6),
        "avg_latency_ms": round(float(totals["avg_latency"]), 1),
        "by_model": by_model,
        "failover_count": failover_count,
    }


# ── KISIM 8: Kolay erisim yardimcilari ───────────────────────────────

def get_fast_model() -> str:
    return route("fast_response")


def get_reasoning_model() -> str:
    return route("complex_reasoning")


def get_creative_model() -> str:
    return route("creative")


def get_embedding_model() -> str:
    return route("embedding")
