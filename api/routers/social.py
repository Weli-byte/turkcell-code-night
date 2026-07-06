from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from api.auth_utils import verify_token
from api.notifications_store import push_notification
from database.setup import get_db
from datetime import datetime, timedelta
import uuid

router = APIRouter(tags=["Social"])

BADGE_LABELS = {
    "bronze": "Bronz", "silver": "Gümüş",
    "gold": "Altın", "platinum": "Platin",
}
STARS = {1: "⭐", 2: "⭐⭐", 3: "⭐⭐⭐", 4: "⭐⭐⭐⭐", 5: "⭐⭐⭐⭐⭐"}


class RateBody(BaseModel):
    content_id: str
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = Field(None, max_length=300)


class CommentBody(BaseModel):
    content_id: str
    comment: str = Field(..., min_length=3, max_length=300)


@router.post("/rate")
def rate_content(body: RateBody, token: dict = Depends(verify_token)):
    """İçerik oyla (1-5 yıldız). İlk oyda +10 puan, ratings_given güncellenir."""
    db      = get_db()
    user_id = token["sub"]
    today   = datetime.now().strftime("%Y-%m-%d")
    now_iso = datetime.now().isoformat()

    content = db.execute(
        "SELECT id, title FROM content_catalog WHERE id=?", (body.content_id,)
    ).fetchone()
    if not content:
        db.close()
        raise HTTPException(404, "İçerik bulunamadı")

    existing = db.execute(
        "SELECT id FROM content_ratings WHERE user_id=? AND content_id=?",
        (user_id, body.content_id),
    ).fetchone()

    bonus_points = 0
    is_new = existing is None

    if existing:
        db.execute(
            "UPDATE content_ratings SET rating=?, updated_at=? WHERE id=?",
            (body.rating, now_iso, existing["id"]),
        )
    else:
        rating_id = "r_" + uuid.uuid4().hex[:12]
        db.execute(
            "INSERT INTO content_ratings (id, user_id, content_id, rating, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (rating_id, user_id, body.content_id, body.rating, now_iso, now_iso),
        )
        bonus_points = 10
        db.execute(
            "INSERT OR IGNORE INTO points_ledger "
            "(user_id, points, reason, activity_date, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, bonus_points, f"{content['title']} oylandı", today, now_iso),
        )
        act = db.execute(
            "SELECT id FROM user_activities WHERE user_id=? AND activity_date=?",
            (user_id, today),
        ).fetchone()
        if act:
            db.execute(
                "UPDATE user_activities SET ratings_given=ratings_given+1 WHERE id=?",
                (act["id"],),
            )
        else:
            db.execute(
                "INSERT INTO user_activities "
                "(user_id, activity_date, watch_minutes, episodes_completed, genres_watched, "
                "watch_party_minutes, ratings_given, created_at) "
                "VALUES (?, ?, 0, 0, 0, 0, 1, ?)",
                (user_id, today, now_iso),
            )

    if body.comment:
        cm_id = "cm_" + uuid.uuid4().hex[:12]
        db.execute(
            "INSERT INTO content_comments (id, user_id, content_id, comment, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (cm_id, user_id, body.content_id, body.comment, now_iso),
        )

    db.commit()

    avg_row = db.execute(
        "SELECT AVG(rating) AS avg_r, COUNT(*) AS cnt FROM content_ratings WHERE content_id=?",
        (body.content_id,),
    ).fetchone()
    total_pts = db.execute(
        "SELECT COALESCE(SUM(points),0) AS total FROM points_ledger WHERE user_id=?",
        (user_id,),
    ).fetchone()
    db.close()

    # Başarım kontrolü (İlk Oy / Eleştirmen)
    from engine.achievement_engine import check_achievements
    new_achievements = check_achievements(user_id)

    return {
        "ok":           True,
        "rating":       body.rating,
        "is_new":       is_new,
        "bonus_points": bonus_points,
        "total_points": int(total_pts["total"]),
        "avg_rating":   round(float(avg_row["avg_r"] or 0), 1),
        "rating_count": int(avg_row["cnt"]),
        "new_achievements": new_achievements,
        "message":      ("Oy verildi" if is_new else "Oy güncellendi") +
                        (f" +{bonus_points} puan!" if bonus_points else ""),
    }


@router.post("/comment")
def add_comment(body: CommentBody, token: dict = Depends(verify_token)):
    """İçeriğe yorum ekle."""
    db = get_db()
    if not db.execute("SELECT id FROM content_catalog WHERE id=?", (body.content_id,)).fetchone():
        db.close()
        raise HTTPException(404, "İçerik bulunamadı")

    cm_id   = "cm_" + uuid.uuid4().hex[:12]
    now_iso = datetime.now().isoformat()
    db.execute(
        "INSERT INTO content_comments (id, user_id, content_id, comment, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (cm_id, token["sub"], body.content_id, body.comment, now_iso),
    )
    db.commit()
    username = db.execute(
        "SELECT username FROM users WHERE id=?", (token["sub"],)
    ).fetchone()
    db.close()

    # Başarım kontrolü (İlk Yorum)
    from engine.achievement_engine import check_achievements
    check_achievements(token["sub"])

    return {
        "id":         cm_id,
        "user_id":    token["sub"],
        "username":   username["username"] if username else "?",
        "content_id": body.content_id,
        "comment":    body.comment,
        "created_at": now_iso,
    }


@router.get("/comments/{content_id}")
def get_comments(content_id: str, token: dict = Depends(verify_token)):
    """İçerik yorumları + kullanıcının mevcut oyunu."""
    db   = get_db()
    rows = db.execute("""
        SELECT cc.id, cc.comment, cc.created_at,
               u.username, u.id AS user_id
        FROM content_comments cc
        JOIN users u ON u.id = cc.user_id
        WHERE cc.content_id = ?
        ORDER BY cc.created_at DESC
        LIMIT 50
    """, (content_id,)).fetchall()

    my_rating = db.execute(
        "SELECT rating FROM content_ratings WHERE user_id=? AND content_id=?",
        (token["sub"], content_id),
    ).fetchone()
    db.close()

    return {
        "comments":  [dict(r) for r in rows],
        "my_rating": my_rating["rating"] if my_rating else None,
    }


@router.get("/content-stats/{content_id}")
def content_stats(content_id: str, token: dict = Depends(verify_token)):
    """İçerik istatistikleri: ortalama puan, izlenme, yorum sayısı."""
    db = get_db()
    avg_row  = db.execute(
        "SELECT AVG(rating) AS avg_r, COUNT(*) AS cnt FROM content_ratings WHERE content_id=?",
        (content_id,),
    ).fetchone()
    watches  = db.execute(
        "SELECT COUNT(*) AS cnt FROM watch_sessions WHERE content_id=? AND ended_at IS NOT NULL",
        (content_id,),
    ).fetchone()
    comments = db.execute(
        "SELECT COUNT(*) AS cnt FROM content_comments WHERE content_id=?",
        (content_id,),
    ).fetchone()
    my_rating = db.execute(
        "SELECT rating FROM content_ratings WHERE user_id=? AND content_id=?",
        (token["sub"], content_id),
    ).fetchone()
    db.close()

    return {
        "content_id":    content_id,
        "avg_rating":    round(float(avg_row["avg_r"] or 0), 1),
        "rating_count":  int(avg_row["cnt"]),
        "watch_count":   int(watches["cnt"]),
        "comment_count": int(comments["cnt"]),
        "my_rating":     my_rating["rating"] if my_rating else None,
    }


@router.get("/feed")
def activity_feed(token: dict = Depends(verify_token)):
    """Global aktivite akışı — son 30 olay."""
    db = get_db()

    sessions = db.execute("""
        SELECT u.username, cc.title, cc.genre,
               ws.watch_minutes, ws.completed, ws.ended_at
        FROM watch_sessions ws
        JOIN users u ON u.id = ws.user_id
        JOIN content_catalog cc ON cc.id = ws.content_id
        WHERE ws.ended_at IS NOT NULL AND ws.watch_minutes > 0
        ORDER BY ws.ended_at DESC LIMIT 15
    """).fetchall()

    badges_rows = db.execute("""
        SELECT u.username, ub.badge_tier, ub.awarded_at
        FROM user_badges ub
        JOIN users u ON u.id = ub.user_id
        ORDER BY ub.awarded_at DESC LIMIT 10
    """).fetchall()

    ratings_rows = db.execute("""
        SELECT u.username, cc.title, cr.rating, cr.created_at
        FROM content_ratings cr
        JOIN users u ON u.id = cr.user_id
        JOIN content_catalog cc ON cc.id = cr.content_id
        ORDER BY cr.created_at DESC LIMIT 10
    """).fetchall()

    db.close()

    feed = []
    for s in sessions:
        feed.append({
            "type":      "watch",
            "username":  s["username"],
            "content":   s["title"],
            "genre":     s["genre"],
            "minutes":   round(float(s["watch_minutes"]), 1),
            "completed": bool(s["completed"]),
            "ts":        s["ended_at"],
        })
    for b in badges_rows:
        feed.append({
            "type":    "badge",
            "username": b["username"],
            "badge":   BADGE_LABELS.get(b["badge_tier"].lower(), b["badge_tier"]),
            "ts":      b["awarded_at"],
        })
    for r in ratings_rows:
        feed.append({
            "type":     "rating",
            "username": r["username"],
            "content":  r["title"],
            "rating":   r["rating"],
            "stars":    STARS.get(r["rating"], "⭐"),
            "ts":       r["created_at"],
        })

    feed.sort(key=lambda x: x["ts"] or "", reverse=True)
    return {"feed": feed[:30]}


# ── Takip Sistemi (Sprint 18) ──────────────────────────────────

def _user_by_username(db, username: str):
    return db.execute(
        "SELECT id, username FROM users WHERE username=?", (username,)
    ).fetchone()


@router.post("/follow/{username}")
def follow_user(username: str, token: dict = Depends(verify_token)):
    """Kullanıcıyı takip et. Takip edilene kalıcı bildirim düşer."""
    db     = get_db()
    target = _user_by_username(db, username)
    if not target:
        db.close()
        raise HTTPException(404, "Kullanıcı bulunamadı")
    if target["id"] == token["sub"]:
        db.close()
        raise HTTPException(422, "Kendini takip edemezsin")

    existing = db.execute(
        "SELECT id FROM follows WHERE follower_id=? AND following_id=?",
        (token["sub"], target["id"]),
    ).fetchone()
    if existing:
        db.close()
        return {"ok": True, "following": True, "message": "Zaten takip ediyorsun"}

    db.execute(
        "INSERT INTO follows (follower_id, following_id, created_at) VALUES (?, ?, ?)",
        (token["sub"], target["id"], datetime.now().isoformat()),
    )
    db.commit()
    follower_name = db.execute(
        "SELECT username FROM users WHERE id=?", (token["sub"],)
    ).fetchone()["username"]
    db.close()

    push_notification(target["id"], {
        "type":    "info",
        "message": f"👤 {follower_name} seni takip etmeye başladı",
    })

    # Takip EDİLEN için başarım kontrolü (Sosyal Kelebek / Popüler)
    from engine.achievement_engine import check_achievements
    check_achievements(target["id"])

    return {"ok": True, "following": True, "message": f"{username} takip edildi"}


@router.delete("/follow/{username}")
def unfollow_user(username: str, token: dict = Depends(verify_token)):
    """Takibi bırak."""
    db     = get_db()
    target = _user_by_username(db, username)
    if not target:
        db.close()
        raise HTTPException(404, "Kullanıcı bulunamadı")
    db.execute(
        "DELETE FROM follows WHERE follower_id=? AND following_id=?",
        (token["sub"], target["id"]),
    )
    db.commit()
    db.close()
    return {"ok": True, "following": False, "message": f"{username} takipten çıkarıldı"}


@router.get("/followers")
def my_followers(token: dict = Depends(verify_token)):
    """Beni takip edenler + toplam puanları."""
    db   = get_db()
    rows = db.execute("""
        SELECT u.username, f.created_at,
               COALESCE((SELECT SUM(points) FROM points_ledger WHERE user_id=u.id), 0) AS total_points,
               EXISTS(SELECT 1 FROM follows f2
                      WHERE f2.follower_id=? AND f2.following_id=u.id) AS i_follow_back
        FROM follows f
        JOIN users u ON u.id = f.follower_id
        WHERE f.following_id = ?
        ORDER BY f.created_at DESC
    """, (token["sub"], token["sub"])).fetchall()
    db.close()
    return {"followers": [
        {"username": r["username"], "since": r["created_at"],
         "total_points": int(r["total_points"]),
         "i_follow_back": bool(r["i_follow_back"])}
        for r in rows
    ]}


@router.get("/following")
def my_following(token: dict = Depends(verify_token)):
    """Takip ettiklerim + toplam puanları."""
    db   = get_db()
    rows = db.execute("""
        SELECT u.username, f.created_at,
               COALESCE((SELECT SUM(points) FROM points_ledger WHERE user_id=u.id), 0) AS total_points
        FROM follows f
        JOIN users u ON u.id = f.following_id
        WHERE f.follower_id = ?
        ORDER BY f.created_at DESC
    """, (token["sub"],)).fetchall()
    db.close()
    return {"following": [
        {"username": r["username"], "since": r["created_at"],
         "total_points": int(r["total_points"])}
        for r in rows
    ]}


@router.get("/friends-leaderboard")
def friends_leaderboard(token: dict = Depends(verify_token)):
    """Takip ettiklerim + ben — puana göre mini liderlik."""
    db   = get_db()
    rows = db.execute("""
        SELECT u.id, u.username,
               COALESCE((SELECT SUM(points) FROM points_ledger WHERE user_id=u.id), 0) AS total_points
        FROM users u
        WHERE u.id = ?
           OR u.id IN (SELECT following_id FROM follows WHERE follower_id=?)
        ORDER BY total_points DESC, u.username ASC
    """, (token["sub"], token["sub"])).fetchall()
    db.close()
    return {"leaderboard": [
        {"rank": i + 1, "username": r["username"],
         "total_points": int(r["total_points"]),
         "is_current_user": r["id"] == token["sub"]}
        for i, r in enumerate(rows)
    ]}


@router.get("/follow-suggestions")
def follow_suggestions(token: dict = Depends(verify_token)):
    """Takip önerileri — henüz takip etmediğim en yüksek puanlı gerçek kullanıcılar."""
    db   = get_db()
    rows = db.execute("""
        SELECT u.username,
               COALESCE((SELECT SUM(points) FROM points_ledger WHERE user_id=u.id), 0) AS total_points,
               (SELECT COUNT(*) FROM follows WHERE following_id=u.id) AS follower_count
        FROM users u
        WHERE u.id != ?
          AND u.id NOT IN (SELECT following_id FROM follows WHERE follower_id=?)
        ORDER BY total_points DESC, u.username ASC
        LIMIT 5
    """, (token["sub"], token["sub"])).fetchall()
    db.close()
    return {"suggestions": [
        {"username": r["username"], "total_points": int(r["total_points"]),
         "follower_count": int(r["follower_count"])}
        for r in rows
    ]}


@router.get("/trending")
def trending_content(token: dict = Depends(verify_token)):
    """Bu haftanın trend içerikleri — izlenme + puan bazlı sıralama."""
    week_start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    db = get_db()
    rows = db.execute("""
        SELECT cc.id, cc.title, cc.genre, cc.duration_minutes, cc.thumbnail_color,
               COUNT(ws.id)                            AS watch_count,
               COALESCE(SUM(ws.watch_minutes), 0)      AS total_minutes,
               COALESCE(AVG(cr.rating), 0)             AS avg_rating,
               COUNT(DISTINCT cr.user_id)              AS rating_count
        FROM content_catalog cc
        LEFT JOIN watch_sessions ws
            ON ws.content_id = cc.id
           AND ws.ended_at IS NOT NULL
           AND ws.ended_at >= ?
        LEFT JOIN content_ratings cr ON cr.content_id = cc.id
        GROUP BY cc.id
        ORDER BY watch_count DESC, total_minutes DESC
        LIMIT 8
    """, (week_start,)).fetchall()
    db.close()

    return {
        "trending": [
            {
                "id":               r["id"],
                "title":            r["title"],
                "genre":            r["genre"],
                "duration_minutes": r["duration_minutes"],
                "thumbnail_color":  r["thumbnail_color"],
                "watch_count":      int(r["watch_count"]),
                "total_minutes":    round(float(r["total_minutes"]), 1),
                "avg_rating":       round(float(r["avg_rating"]), 1),
                "rating_count":     int(r["rating_count"]),
            }
            for r in rows
        ],
        "week_start": week_start,
    }
