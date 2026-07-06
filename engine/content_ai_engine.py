"""
Content AI Engine — Sprint 20.
İçerik detayı (gerçek istatistikler + benzer videolar) ve GPT-4o topluluk
özeti. Özet, gerçek yorum + rating verisinden üretilir; kaynak veri
değişmediyse cache'ten döner (performans — sahte veri değil, aynı gerçek
verinin aynı özeti). LLM yoksa deterministik özet.
"""

import json
from datetime import datetime
from database.setup import get_db


def get_content_detail(content_id: str, user_id: str) -> dict | None:
    """Video + gerçek istatistikler + yıldız dağılımı + benzer videolar."""
    db      = get_db()
    content = db.execute(
        "SELECT * FROM content_catalog WHERE id=?", (content_id,)
    ).fetchone()
    if not content:
        db.close()
        return None

    stats = db.execute("""
        SELECT COUNT(*)                        AS watch_count,
               COALESCE(SUM(watch_minutes),0)  AS total_minutes,
               COALESCE(SUM(completed),0)      AS completions
        FROM watch_sessions
        WHERE content_id=? AND ended_at IS NOT NULL
    """, (content_id,)).fetchone()

    rating_row = db.execute(
        "SELECT COUNT(*) AS cnt, COALESCE(AVG(rating),0) AS avg_r "
        "FROM content_ratings WHERE content_id=?",
        (content_id,),
    ).fetchone()

    # Yıldız dağılımı (1-5 histogram)
    dist_rows = db.execute(
        "SELECT rating, COUNT(*) AS c FROM content_ratings "
        "WHERE content_id=? GROUP BY rating",
        (content_id,),
    ).fetchall()
    dist = {i: 0 for i in range(1, 6)}
    for r in dist_rows:
        dist[int(r["rating"])] = int(r["c"])
    max_dist = max(dist.values()) or 1

    my_rating = db.execute(
        "SELECT rating FROM content_ratings WHERE user_id=? AND content_id=?",
        (user_id, content_id),
    ).fetchone()

    comment_cnt = db.execute(
        "SELECT COUNT(*) AS c FROM content_comments WHERE content_id=?",
        (content_id,),
    ).fetchone()["c"]

    # Benzer videolar: aynı tür, kendisi hariç, gerçek izlenmeye göre
    similar = db.execute("""
        SELECT cc.id, cc.title, cc.genre, cc.duration_minutes, cc.thumbnail_color,
               (SELECT COUNT(*) FROM watch_sessions ws
                WHERE ws.content_id=cc.id AND ws.ended_at IS NOT NULL) AS watches,
               (SELECT COALESCE(AVG(rating),0) FROM content_ratings cr
                WHERE cr.content_id=cc.id) AS avg_rating
        FROM content_catalog cc
        WHERE cc.genre = ? AND cc.id != ?
        ORDER BY watches DESC, cc.title ASC
        LIMIT 4
    """, (content["genre"], content_id)).fetchall()

    # Seri bilgisi: aynı serinin diğer bölümleri
    series_eps = []
    if content["series_id"]:
        eps = db.execute(
            "SELECT id, title, episode_number FROM content_catalog "
            "WHERE series_id=? ORDER BY episode_number",
            (content["series_id"],),
        ).fetchall()
        series_eps = [dict(e) for e in eps]

    db.close()

    return {
        "content":        dict(content),
        "watch_count":    int(stats["watch_count"]),
        "total_minutes":  round(float(stats["total_minutes"]), 1),
        "completions":    int(stats["completions"]),
        "avg_rating":     round(float(rating_row["avg_r"]), 1),
        "rating_count":   int(rating_row["cnt"]),
        "comment_count":  int(comment_cnt),
        "my_rating":      my_rating["rating"] if my_rating else None,
        "rating_dist": [
            {"stars": i, "count": dist[i],
             "pct": round(dist[i] / max_dist * 100, 1)}
            for i in range(5, 0, -1)
        ],
        "similar": [dict(s) | {"avg_rating": round(float(s["avg_rating"]), 1)}
                    for s in similar],
        "series_episodes": series_eps,
    }


def build_review_summary(content_id: str) -> dict:
    """
    Topluluk özeti: gerçek yorumlar + rating dağılımından GPT-4o anlatısı.
    source_hash aynıysa cache'ten döner; veri değişince yeniden üretilir.
    """
    db      = get_db()
    content = db.execute(
        "SELECT id, title, genre FROM content_catalog WHERE id=?", (content_id,)
    ).fetchone()
    if not content:
        db.close()
        return {"summary": None, "error": "İçerik bulunamadı"}

    comments = db.execute("""
        SELECT cc.comment, cc.created_at, u.username
        FROM content_comments cc
        JOIN users u ON u.id = cc.user_id
        WHERE cc.content_id=?
        ORDER BY cc.created_at DESC LIMIT 30
    """, (content_id,)).fetchall()

    rating_row = db.execute(
        "SELECT COUNT(*) AS cnt, COALESCE(AVG(rating),0) AS avg_r "
        "FROM content_ratings WHERE content_id=?",
        (content_id,),
    ).fetchone()
    r_cnt, r_avg = int(rating_row["cnt"]), round(float(rating_row["avg_r"]), 2)

    if not comments and r_cnt == 0:
        db.close()
        return {
            "summary":      "Bu içerik hakkında henüz yorum veya oy yok — ilk görüşü sen paylaş!",
            "llm_enhanced": False,
            "model":        "template",
            "cached":       False,
            "comment_count": 0, "rating_count": 0,
        }

    # Kaynak imzası: yorum sayısı + son yorum zamanı + rating istatistiği
    last_comment = comments[0]["created_at"] if comments else ""
    source_hash  = f"c{len(comments)}|{last_comment}|r{r_cnt}|a{r_avg}"

    cached = db.execute(
        "SELECT summary, model, source_hash FROM content_ai_summaries WHERE content_id=?",
        (content_id,),
    ).fetchone()
    if cached and cached["source_hash"] == source_hash:
        db.close()
        return {
            "summary":      cached["summary"],
            "llm_enhanced": cached["model"] != "template",
            "model":        cached["model"],
            "cached":       True,
            "comment_count": len(comments), "rating_count": r_cnt,
        }

    # Deterministik taban özet
    template = (
        f"{content['title']}: {r_cnt} oy, ortalama {r_avg}/5. "
        f"{len(comments)} yorum yapıldı."
    )

    # GPT-4o — gerçek yorum metinleriyle
    from engine.llm_adapter import llm_call, is_llm_available, LLM_MODEL
    summary, model = template, "template"
    if comments or r_cnt > 0:
        comment_lines = "\n".join(
            f"- {c['username']}: {c['comment']}" for c in comments
        ) or "(yorum yok)"
        llm_answer = llm_call(
            system=(
                "Sen bir video platformu topluluk analisti/editörüsün. "
                "Gerçek kullanıcı yorumları ve puanlardan kısa, dengeli bir "
                "'topluluk ne diyor' özeti yazarsın. Yorum yoksa puanlara dayan. "
                "Sayı uydurma."
            ),
            user=(
                f"Video: {content['title']} (tür: {content['genre']})\n"
                f"Puan: {r_cnt} oy, ortalama {r_avg}/5\n\n"
                f"Kullanıcı yorumları:\n{comment_lines}\n\n"
                f"2-3 cümlelik Türkçe topluluk özeti yaz."
            ),
            max_tokens=200,
            temperature=0.4,
        )
        if llm_answer:
            summary, model = llm_answer, LLM_MODEL
        elif is_llm_available():
            model = LLM_MODEL  # denendi, düşemedi → template ile işaretle

    db.execute(
        "INSERT INTO content_ai_summaries (content_id, summary, source_hash, model, updated_at) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(content_id) DO UPDATE SET "
        "summary=excluded.summary, source_hash=excluded.source_hash, "
        "model=excluded.model, updated_at=excluded.updated_at",
        (content_id, summary, source_hash,
         "template" if summary == template else model,
         datetime.now().isoformat()),
    )
    db.commit()
    db.close()

    return {
        "summary":      summary,
        "llm_enhanced": summary != template,
        "model":        model if summary != template else "template",
        "cached":       False,
        "comment_count": len(comments), "rating_count": r_cnt,
    }
