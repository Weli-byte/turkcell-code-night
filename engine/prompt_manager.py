"""
engine/prompt_manager.py — Prompt versiyonlama, A/B test ve analitik.

A/B atamasi DETERMINISTIK: user_id+prompt_name md5 hash'inden agirlikli secim
(rastgelelik yok — ayni kullanici daima ayni varyanti alir). Kullanim kayitlari
prompt_analytics tablosuna APPEND-ONLY yazilir (sadece INSERT + SELECT).
"""

import os
import json
import hashlib
from datetime import datetime, timedelta

from database.setup import get_db

# ── KISIM 1: Prompt Registry ─────────────────────────────────────────

PROMPTS = {

    # ── CHALLENGE GENERATION ─────────────
    "challenge_generation_v1": {
        "template": (
            "Kullanici profili: {state}\n"
            "Hafiza: {memory}\n"
            "Gecmis challenge basarilari: {history}\n\n"
            "Bu kullanici icin 3 adet kisisel challenge olustur.\n"
            "JSON formatinda don:\n"
            '{"challenges": [{"id": str, "name": str, "condition": str, '
            '"reward_points": int, "reason": str}]}\n\n'
            "condition alanlari SADECE:\n"
            "watch_minutes_today, episodes_completed_today,\n"
            "watch_party_minutes_today, ratings_given_today,\n"
            "watch_minutes_7d, streak_days, genres_watched_today\n"
            "reward_points: 50-500 arasi"
        ),
        "version": "1.0",
        "model": "gpt-4o",
        "temperature": 0.7,
        "max_tokens": 500,
        "ab_weight": 0.5,
        "active": True,
    },

    "challenge_generation_v2": {
        "template": (
            "SEN: Video platformu gamification uzmanisin.\n"
            "KULLANICI DURUMU: {state}\n"
            "KULLANICI HAFIZASI: {memory}\n"
            "GECMIS BASARILAR: {history}\n\n"
            "GOREV: Kullanicinin mevcut durumuna uygun,\n"
            "ulasilabilir 3 challenge olustur.\n\n"
            "ZORUNLU FORMAT:\n"
            '{"challenges": [{"id": "ai_ch_<timestamp>", "name": "<kisa isim>", '
            '"condition": "<alan> <op> <deger>", "reward_points": <50-500>, '
            '"reason": "<neden bu challenge>", "difficulty": "easy|medium|hard"}]}\n\n'
            "KISITLAMALAR:\n"
            "- condition: sadece izin verilen alanlar\n"
            "- Zaten tamamlanmis challenge onermez\n"
            "- Her challenge birbirinden farkli olsun"
        ),
        "version": "2.0",
        "model": "gpt-4o",
        "temperature": 0.5,
        "max_tokens": 600,
        "ab_weight": 0.5,
        "active": True,
    },

    # ── EXPLANATION ──────────────────────
    "explanation_v1": {
        "template": (
            "Sen bir video platformu oyunlastirma asistanisin.\n"
            "SADECE verilen evidence verilerini kullan.\n"
            "Sayilari degistirme. Maks 3 cumle. Turkce yaz.\n\n"
            "Soru: {question}\n"
            "Evidence: {evidence}"
        ),
        "version": "1.0",
        "model": "gpt-4o",
        "temperature": 0.4,
        "max_tokens": 300,
        "ab_weight": 1.0,
        "active": True,
    },

    # ── INTENT DETECTION ─────────────────
    "intent_detection_v1": {
        "template": (
            "Kullanici sorusu: {question}\n"
            "Intent kategorisi belirle.\n"
            'JSON don: {{"intent": "..."}}\n'
            "Kategoriler: points_query, rank_query, badge_progress,\n"
            "streak, compare, today, history, suggestion, general"
        ),
        "version": "1.0",
        "model": "gpt-4o",
        "temperature": 0.1,
        "max_tokens": 50,
        "ab_weight": 1.0,
        "active": True,
    },

    # ── MOTIVATION ───────────────────────
    "motivation_v1": {
        "template": (
            "Sen bir video platformu kocusun.\n"
            "Kullanicinin motivasyon tipine gore\n"
            "kisa (1-2 cumle) motive edici mesaj yaz.\n"
            "Gercek veriler kullan. Uydurma yazma.\n\n"
            "Motivasyon tipi: {motivation_type}\n"
            "Baglam: {context}\n"
            "Kullanici durumu: {state}"
        ),
        "version": "1.0",
        "model": "gpt-4o-mini",
        "temperature": 0.6,
        "max_tokens": 150,
        "ab_weight": 1.0,
        "active": True,
    },

    # ── GOAL GENERATION ──────────────────
    "goal_generation_v1": {
        "template": (
            "Sen bir video platformu kocusun.\n"
            "Kullanicinin verilerine dayanarak\n"
            "gercekci ve motive edici hedefler belirliyorsun.\n"
            "SADECE verilen verileri kullan.\n\n"
            "Kullanici profili: {profile}\n"
            "Mevcut durum: {state}\n"
            "Hafiza: {memory}\n\n"
            "Bu kullanici icin bu hafta ulasilabilir 1 ana hedef belirle.\n"
            "JSON formatinda don:\n"
            '{"goal_type": str, "title": str, "description": str,\n'
            ' "target_value": int, "current_value": int,\n'
            ' "deadline": str, "difficulty": str,\n'
            ' "reason": str, "action_steps": [str]}'
        ),
        "version": "1.0",
        "model": "gpt-4o",
        "temperature": 0.5,
        "max_tokens": 500,
        "ab_weight": 1.0,
        "active": True,
    },
}


# ── KISIM 2: Deterministik A/B test router ───────────────────────────

def assign_ab_variant(user_id: str, prompt_name: str) -> str:
    """
    Rastgelelik YOK: user_id+prompt_name md5 hash'inden agirlikli secim.
    Ayni kullanici ayni prompt icin daima ayni varyanti alir.
    """
    variants = sorted(
        k for k in PROMPTS
        if (k.startswith(prompt_name + "_v") or k == prompt_name)
        and PROMPTS[k].get("active", False)
    )
    if not variants:
        return prompt_name

    key = f"{user_id}:{prompt_name}"
    hash_val = int(hashlib.md5(key.encode()).hexdigest(), 16)

    total_weight = sum(PROMPTS[v]["ab_weight"] for v in variants)
    if total_weight <= 0:
        return variants[-1]

    threshold = (hash_val % 10000) / 10000.0
    cumulative = 0.0
    for variant in variants:
        cumulative += PROMPTS[variant]["ab_weight"] / total_weight
        if threshold < cumulative:
            return variant

    return variants[-1]


# ── KISIM 3: Ana get_prompt ──────────────────────────────────────────

def get_prompt(name: str, user_id: str = None) -> dict:
    """Prompt'u getirir (direkt key veya A/B varyant) ve kullanimini loglar."""
    if name in PROMPTS:
        variant = name
    else:
        variant = assign_ab_variant(user_id or "default", name)
        if variant not in PROMPTS:
            raise ValueError(f"{name} icin prompt bulunamadi")

    prompt = dict(PROMPTS[variant])
    prompt["variant_key"] = variant

    log_prompt_use(name, variant, user_id, model=prompt.get("model"))
    return prompt


# ── KISIM 4: Prompt render ───────────────────────────────────────────

def render_prompt(name: str, variables: dict, user_id: str = None) -> dict:
    """Prompt'u alir ve {degisken} yerlerini doldurur (eksikte ham sablon)."""
    prompt = get_prompt(name, user_id)
    try:
        rendered = prompt["template"].format(**variables)
    except (KeyError, ValueError, IndexError):
        rendered = prompt["template"]
    prompt["rendered_template"] = rendered
    return prompt


# ── KISIM 5: Analitik (APPEND-ONLY) ──────────────────────────────────

def log_prompt_use(prompt_name: str, variant: str, user_id: str = None,
                   model: str = None, tokens_used: int = 0,
                   latency_ms: int = 0, success: bool = True) -> None:
    """prompt_analytics'e SADECE INSERT. Hata sessizce gecilir."""
    try:
        db = get_db()
        try:
            db.execute(
                "INSERT INTO prompt_analytics "
                "(prompt_name, variant, user_id, model, tokens_used, "
                " latency_ms, success, created_at) VALUES (?,?,?,?,?,?,?,?)",
                (prompt_name, variant, user_id, model, int(tokens_used),
                 int(latency_ms), 1 if success else 0,
                 datetime.now().isoformat()),
            )
            db.commit()
        finally:
            db.close()
    except Exception as e:
        print("[prompt_manager] analitik kayit hatasi:", e)


def get_prompt_analytics(prompt_name: str = None, hours: int = 24) -> dict:
    """Son X saatin kullanim analitigi (DB aggregation)."""
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    db = get_db()
    try:
        if prompt_name:
            rows = db.execute(
                "SELECT prompt_name, variant, COUNT(*) AS cnt, "
                "AVG(success) AS sr, AVG(tokens_used) AS avg_tok, "
                "AVG(latency_ms) AS avg_lat "
                "FROM prompt_analytics "
                "WHERE created_at >= ? AND prompt_name = ? "
                "GROUP BY prompt_name, variant",
                (cutoff, prompt_name),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT prompt_name, variant, COUNT(*) AS cnt, "
                "AVG(success) AS sr, AVG(tokens_used) AS avg_tok, "
                "AVG(latency_ms) AS avg_lat "
                "FROM prompt_analytics "
                "WHERE created_at >= ? "
                "GROUP BY prompt_name, variant",
                (cutoff,),
            ).fetchall()
    finally:
        db.close()

    by_prompt = {}
    total_uses = 0
    for r in rows:
        base = r["prompt_name"]
        cnt = int(r["cnt"])
        total_uses += cnt
        by_prompt.setdefault(base, {"total": 0, "variants": {}})
        by_prompt[base]["total"] += cnt
        by_prompt[base]["variants"][r["variant"]] = {
            "count": cnt,
            "success_rate": round(float(r["sr"] or 0), 3),
            "avg_tokens": round(float(r["avg_tok"] or 0), 1),
            "avg_latency": round(float(r["avg_lat"] or 0), 1),
        }

    ab_test_results = {}
    for base, data in by_prompt.items():
        variants = sorted(data["variants"].keys())
        if len(variants) < 2:
            continue
        v1, v2 = variants[0], variants[1]
        d1, d2 = data["variants"][v1], data["variants"][v2]
        if d1["success_rate"] > d2["success_rate"]:
            winner = v1
        elif d2["success_rate"] > d1["success_rate"]:
            winner = v2
        else:
            winner = None
        total = d1["count"] + d2["count"]
        confidence = "low" if total < 30 else ("medium" if total < 100 else "high")
        ab_test_results[base] = {
            "winner": winner,
            "v1_count": d1["count"],
            "v2_count": d2["count"],
            "confidence": confidence,
        }

    return {
        "period_hours": hours,
        "total_uses": total_uses,
        "by_prompt": by_prompt,
        "ab_test_results": ab_test_results,
    }


# ── KISIM 6: Prompt yonetimi ─────────────────────────────────────────

def get_all_prompts() -> dict:
    """Tum kayitli prompt'lar (template ilk 80 karaktere kisaltilir)."""
    result = {}
    for name, p in PROMPTS.items():
        info = dict(p)
        info["template"] = p["template"][:80]
        result[name] = info
    return result


def get_active_prompts() -> list:
    """active=True olan prompt isimleri."""
    return sorted(k for k, p in PROMPTS.items() if p.get("active", False))


def get_prompt_versions(base_name: str) -> list:
    """Bir prompt'un tum versiyonlari."""
    return sorted(
        k for k in PROMPTS
        if k.startswith(base_name + "_v") or k == base_name
    )


def get_ab_distribution(prompt_name: str, sample_size: int = 1000) -> dict:
    """
    A/B dagilimini deterministik hesaplar: 1..N sentetik kullanici kimligi
    icin assign_ab_variant kosulur (DB'ye yazilmaz, rastgelelik yok).
    """
    counts = {}
    for i in range(1, sample_size + 1):
        v = assign_ab_variant(f"probe_{i:05d}", prompt_name)
        counts[v] = counts.get(v, 0) + 1

    distribution = {
        v: round(c / sample_size, 4) for v, c in counts.items()
    }
    return {"variants": counts, "distribution": distribution}
