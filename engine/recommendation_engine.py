"""
engine/recommendation_engine.py — Kisisel oneri motoru (Sprint 4A).

6 oneri tipi: video, challenge, friend, watch_party, badge, leaderboard.
Tum skorlar gercek DB verisi + hafiza + embedding'den DETERMINISTIK hesaplanir
(rastgelelik yok). Benzer kullanici onerisi gercek profil embedding'i +
cosine benzerligi kullanir.
"""

import json
from datetime import datetime, timedelta

from database.setup import get_db
from engine.embedding_service import encode_user_profile, cosine_similarity
from engine.memory_store import get as mem_get
from engine.vector_store import search as vec_search
from engine.state_builder import build_user_state

RECOMMENDATION_TYPES = [
    "video",
    "challenge",
    "friend",
    "watch_party",
    "badge",
    "leaderboard",
]

DATE_FMT = "%Y-%m-%d"

BADGE_THRESHOLDS = [
    ("BRONZE", 500),
    ("SILVER", 1500),
    ("GOLD", 3000),
    ("PLATINUM", 5000),
]


def _today() -> str:
    return datetime.now().strftime(DATE_FMT)


# ── KISIM 2: Video onerileri ──────────────────────────────────────────

def recommend_videos(user_id: str, n: int = 5) -> list:
    """Izlenmemis videolar; tur tercihi + kisa sure bonuslu deterministik skor."""
    db = get_db()
    try:
        watched = {
            r["content_id"] for r in db.execute(
                "SELECT DISTINCT content_id FROM watch_sessions "
                "WHERE user_id=? AND watch_minutes > 0",
                (user_id,),
            ).fetchall()
        }
        all_videos = [dict(r) for r in db.execute(
            "SELECT id, title, genre, content_type, duration_minutes, stream_url "
            "FROM content_catalog ORDER BY id"
        ).fetchall()]
    finally:
        db.close()

    memory = mem_get(user_id)
    preferred = memory.get("genre_preferences", [])
    if not isinstance(preferred, list):
        preferred = []

    items = []
    for v in all_videos:
        if v["id"] in watched:
            continue

        score = 0.0
        reasons = []
        if v["duration_minutes"] < 30:
            score += 1
            reasons.append("kisa sure")
        if v["genre"] in preferred:
            score += 2
            reasons.append(f"tur tercihine uyuyor: {v['genre']}")
        # Aday listesi zaten izlenmemislerden olusur
        score += 1
        reasons.append("henuz izlenmedi")

        items.append({
            "id": v["id"],
            "title": v["title"],
            "genre": v["genre"],
            "duration_minutes": v["duration_minutes"],
            "stream_url": v["stream_url"],
            "score": score,
            "reason": ", ".join(reasons),
            "type": "video",
        })

    # Deterministik: skor DESC, esitlikte id ASC
    items.sort(key=lambda x: x["id"])
    items.sort(key=lambda x: -x["score"])
    return items[:n]


# ── KISIM 3: Challenge onerileri ──────────────────────────────────────

def recommend_challenges(user_id: str, n: int = 3) -> list:
    """Tamamlanmaya yakin, henuz odullenmemis challenge'lar one cikar."""
    from engine.condition_parser import get_progress
    from engine.ledger import already_rewarded

    today = _today()
    state = build_user_state(user_id, today)

    db = get_db()
    try:
        rows = [dict(r) for r in db.execute(
            "SELECT id, name, condition, reward_points, priority "
            "FROM challenges WHERE is_active=1"
        ).fetchall()]
    finally:
        db.close()

    items = []
    for ch in rows:
        if already_rewarded(user_id, ch["id"], today):
            continue
        try:
            prog = get_progress(ch["condition"], state)
            pct = int(prog["percentage"])
        except Exception:
            continue

        if 80 <= pct <= 99:
            score = 5.0
            reason = f"%{pct} tamamlandi — neredeyse bitti!"
        elif 50 <= pct < 80:
            score = 3.0
            reason = f"%{pct} tamamlandi — ulasilabilir hedef"
        else:
            score = 1.0
            reason = f"%{pct} tamamlandi — {ch['reward_points']} puan seni bekliyor"
        score += int(ch["priority"]) / 10.0

        items.append({
            "id": ch["id"],
            "name": ch["name"],
            "condition": ch["condition"],
            "reward_points": int(ch["reward_points"]),
            "percentage": pct,
            "score": score,
            "reason": reason,
            "type": "challenge",
        })

    items.sort(key=lambda x: x["id"])
    items.sort(key=lambda x: -x["score"])
    return items[:n]


# ── KISIM 4: Rozet onerisi ────────────────────────────────────────────

def recommend_badge(user_id: str):
    """Siradaki rozet + son 7 gun ortalamasina gore tahmini gun sayisi."""
    db = get_db()
    try:
        total = int(db.execute(
            "SELECT COALESCE(SUM(points),0) FROM points_ledger WHERE user_id=?",
            (user_id,),
        ).fetchone()[0])

        week_start = (datetime.now() - timedelta(days=6)).strftime(DATE_FMT)
        week_pts = float(db.execute(
            "SELECT COALESCE(SUM(points),0) FROM points_ledger "
            "WHERE user_id=? AND activity_date >= ?",
            (user_id, week_start),
        ).fetchone()[0])
    finally:
        db.close()

    next_tier = None
    next_threshold = None
    for tier, threshold in BADGE_THRESHOLDS:
        if total < threshold:
            next_tier = tier
            next_threshold = threshold
            break

    if next_tier is None:
        return None  # Tum rozetler kazanilmis

    points_needed = next_threshold - total
    avg_daily = week_pts / 7.0
    days_estimated = int(points_needed / avg_daily) + 1 if avg_daily > 0 else None

    if days_estimated is not None:
        reason = (f"{points_needed} puan sonra {next_tier} — bu tempoyla "
                  f"yaklasik {days_estimated} gunde ulasirsin")
    else:
        reason = f"{points_needed} puan sonra {next_tier} rozetini kazanirsin"

    return {
        "tier": next_tier,
        "points_needed": points_needed,
        "days_estimated": days_estimated,
        "current_points": total,
        "reason": reason,
        "type": "badge",
    }


# ── KISIM 5: Benzer kullanici onerileri ───────────────────────────────

def recommend_friends(user_id: str, n: int = 3) -> list:
    """Profil embedding benzerligine gore en yakin kullanicilar (deterministik)."""
    try:
        base = encode_user_profile(user_id)
        if base is None:
            return []

        db = get_db()
        try:
            others = [dict(r) for r in db.execute(
                "SELECT id, username FROM users WHERE id != ? ORDER BY id",
                (user_id,),
            ).fetchall()]
            totals = {
                r["user_id"]: int(r["t"]) for r in db.execute(
                    "SELECT user_id, COALESCE(SUM(points),0) AS t "
                    "FROM points_ledger GROUP BY user_id"
                ).fetchall()
            }
        finally:
            db.close()

        items = []
        for u in others:
            vec = encode_user_profile(u["id"])
            if vec is None:
                continue
            sim = cosine_similarity(base, vec)
            items.append({
                "user_id": u["id"],
                "username": u["username"],
                "similarity": round(sim, 4),
                "total_points": totals.get(u["id"], 0),
                "reason": f"izleme profili %{round(sim * 100)} benzer",
                "type": "friend",
            })

        # Deterministik: benzerlik DESC, esitlikte user_id ASC
        items.sort(key=lambda x: x["user_id"])
        items.sort(key=lambda x: -x["similarity"])
        return items[:n]
    except Exception as e:
        print("[recommendation] friend onerisi hatasi:", e)
        return []


# ── KISIM 7: Leaderboard onerisi ──────────────────────────────────────

def recommend_leaderboard(user_id: str) -> list:
    """Kullanicinin one cikabilecegi leaderboard kategorileri."""
    from engine.ai_leaderboard import get_leaderboard, get_category_leaderboard

    suggestions = []
    try:
        board = get_leaderboard(1000)
        rank = next((e["rank"] for e in board if e["user_id"] == user_id), None)

        # Yeni baslayan mi? (son 7 gunde kayit)
        db = get_db()
        try:
            row = db.execute(
                "SELECT created_at FROM users WHERE id=?", (user_id,)
            ).fetchone()
        finally:
            db.close()
        cutoff = (datetime.now() - timedelta(days=7)).strftime(DATE_FMT)
        if row and (row["created_at"] or "")[:10] >= cutoff and rank is not None and rank < 10:
            suggestions.append({
                "category": "yeni_baslayanlar",
                "current_rank": rank,
                "reason": f"Yeni katildin ve genel siralaman {rank} — "
                          "yeni baslayanlar tablosunda one cikabilirsin",
                "type": "leaderboard",
            })

        # Hangi kategorilerde ust siralarda?
        for cat in ("en_aktif", "en_sosyal", "en_istikrarli"):
            cat_board = get_category_leaderboard(cat, 50)
            cat_rank = next(
                (e["rank"] for e in cat_board if e["user_id"] == user_id), None
            )
            if cat_rank is not None and cat_rank <= 3:
                suggestions.append({
                    "category": cat,
                    "current_rank": cat_rank,
                    "reason": f"'{cat}' kategorisinde {cat_rank}. siradasin — "
                              "zirveyi zorla!",
                    "type": "leaderboard",
                })
    except Exception as e:
        print("[recommendation] leaderboard onerisi hatasi:", e)

    return suggestions


# ── KISIM 6: Ana recommend fonksiyonu ─────────────────────────────────

def recommend(user_id: str, rec_type: str, n: int = 5) -> list:
    """Tek tip icin oneri listesi. Gecersiz tip -> ValueError."""
    if rec_type not in RECOMMENDATION_TYPES:
        raise ValueError(f"Gecersiz oneri tipi: {rec_type}")

    try:
        if rec_type == "video":
            return recommend_videos(user_id, n)
        if rec_type == "challenge":
            return recommend_challenges(user_id, n)
        if rec_type == "badge":
            badge = recommend_badge(user_id)
            return [badge] if badge else []
        if rec_type in ("friend", "watch_party"):
            return recommend_friends(user_id, n)
        return recommend_leaderboard(user_id)
    except Exception as e:
        print(f"[recommendation] {rec_type} onerisi hatasi:", e)
        return []


# ── KISIM 8: Tum oneriler ─────────────────────────────────────────────

def get_all_recommendations(user_id: str) -> dict:
    """Tum tipler icin oneriler; hatali tip atlanir."""
    recommendations = {}
    for t in RECOMMENDATION_TYPES:
        try:
            recommendations[t] = recommend(user_id, t)
        except Exception as e:
            print(f"[recommendation] {t} atlandi:", e)
            recommendations[t] = []

    return {
        "user_id": user_id,
        "recommendations": recommendations,
        "generated_at": datetime.now().isoformat(),
    }


def recommend_all(user_id: str, n: int = 5) -> dict:
    """API uyumluluk sarmalayicisi: {tip: [oneriler]} dondurur."""
    return {t: recommend(user_id, t, n) for t in RECOMMENDATION_TYPES}
