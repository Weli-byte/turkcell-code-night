"""
Recommendation Engine — Sprint 7.
Gerçek izleme geçmişinden tür profili çıkarır, GPT-4o ile açıklamalı öneri üretir.
Sıfır mock: tüm veri DB'den gelir.
"""

import json
from database.setup import get_db


def get_user_genre_profile(user_id: str) -> dict[str, float]:
    """Kullanıcının türlere göre toplam izleme süresi (dakika)."""
    db   = get_db()
    rows = db.execute("""
        SELECT cc.genre, COALESCE(SUM(ws.watch_minutes), 0) AS total_minutes
        FROM watch_sessions ws
        JOIN content_catalog cc ON cc.id = ws.content_id
        WHERE ws.user_id = ? AND ws.ended_at IS NOT NULL
        GROUP BY cc.genre
        ORDER BY total_minutes DESC
    """, (user_id,)).fetchall()
    db.close()
    return {r["genre"]: round(float(r["total_minutes"]), 1) for r in rows}


def get_watched_content_ids(user_id: str) -> set[str]:
    """Kullanıcının daha önce seans başlattığı video id'leri."""
    db   = get_db()
    rows = db.execute(
        "SELECT DISTINCT content_id FROM watch_sessions WHERE user_id = ?",
        (user_id,)
    ).fetchall()
    db.close()
    return {r["content_id"] for r in rows}


def _all_catalog() -> list[dict]:
    db   = get_db()
    rows = db.execute("SELECT * FROM content_catalog ORDER BY title ASC").fetchall()
    db.close()
    return [dict(r) for r in rows]


def get_recommendations(user_id: str) -> dict:
    """
    1. Tür profilini DB'den çıkar.
    2. İzlenmemiş videolara tür puanı ver, sırala.
    3. GPT-4o ile kişiselleştirilmiş açıklama üret.
    """
    genre_profile = get_user_genre_profile(user_id)
    watched_ids   = get_watched_content_ids(user_id)
    all_videos    = _all_catalog()

    candidates = [v for v in all_videos if v["id"] not in watched_ids]
    # Hepsini izlediyse tüm katalog üzerinden çalış
    if not candidates:
        candidates = all_videos

    scored = sorted(candidates, key=lambda v: genre_profile.get(v["genre"], 0), reverse=True)
    top    = scored[:5]

    evidence = {
        "genre_profile": genre_profile,
        "watched_count": len(watched_ids),
        "catalog_size":  len(all_videos),
        "candidates":    len(candidates),
        "top_videos":    [{"id": v["id"], "title": v["title"], "genre": v["genre"],
                           "duration_minutes": v["duration_minutes"]} for v in top],
    }

    # Template cevap
    if not top:
        template = "Katalogda henüz içerik yok."
    elif genre_profile:
        top_genre = max(genre_profile, key=lambda g: genre_profile[g])
        template  = (
            f"En çok izlediğin tür: {top_genre} "
            f"({genre_profile[top_genre]:.0f} dakika). "
            "Sana özel öneri: " +
            ", ".join(v["title"] for v in top[:3]) + ". "
            "Bu videolar izleme profilinden seçildi."
        )
    else:
        template = (
            "Henüz izleme geçmişin yok. "
            "Şunlarla başlayabilirsin: " +
            ", ".join(v["title"] for v in top[:3]) + "."
        )

    # GPT-4o — merkezi adapter üzerinden; hata → deterministik template
    from engine.llm_adapter import llm_call, is_llm_available, LLM_MODEL
    prompt = (
        f"Kullanıcının izleme profili (tür → toplam dakika):\n"
        f"{json.dumps(genre_profile, ensure_ascii=False)}\n\n"
        f"Önerilen içerikler (henüz izlememiş):\n"
        f"{json.dumps([{'başlık': v['title'], 'tür': v['genre'], 'süre': str(v['duration_minutes']) + ' dk'} for v in top], ensure_ascii=False, indent=2)}\n\n"
        f"Bu kullanıcıya neden bu videoları öneriyorsun? "
        f"Her video için en fazla 1 cümle yaz. Türkçe, samimi, motive edici. Toplam 4 cümleyi geçme."
    )
    llm_answer = llm_call(
        system="Sen bir video platformu öneri asistanısın. Kullanıcının izleme profiline göre kişiselleştirilmiş, samimi öneriler yap.",
        user=prompt,
    )
    if llm_answer:
        answer, llm_enhanced, llm_error, model = llm_answer, True, None, LLM_MODEL
    else:
        answer       = template
        llm_enhanced = False
        llm_error    = "LLM cevabı alınamadı" if is_llm_available() else None
        model        = LLM_MODEL if is_llm_available() else "template"

    return {
        "answer":       answer,
        "videos":       top,
        "evidence":     evidence,
        "llm_enhanced": llm_enhanced,
        "llm_error":    llm_error,
        "model":        model,
    }
