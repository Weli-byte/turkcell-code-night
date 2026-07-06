from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from api.auth_utils import verify_token, require_admin
from database.setup import get_db
from typing import Optional
import uuid

router = APIRouter(tags=["Content"])


class ContentCreate(BaseModel):
    title:            str = Field(..., min_length=2, max_length=120)
    content_type:     str = Field(..., min_length=2, max_length=30)
    genre:            str = Field(..., min_length=2, max_length=30)
    duration_minutes: int = Field(..., ge=1, le=600)
    stream_url:       str = Field(..., min_length=8, max_length=500)
    thumbnail_color:  str = Field("#1a1a2e", pattern=r"^#[0-9a-fA-F]{6}$")
    series_id:        Optional[str] = Field(None, max_length=50)
    episode_number:   Optional[int] = Field(None, ge=1, le=999)


class ContentUpdate(BaseModel):
    title:            Optional[str] = Field(None, min_length=2, max_length=120)
    content_type:     Optional[str] = Field(None, min_length=2, max_length=30)
    genre:            Optional[str] = Field(None, min_length=2, max_length=30)
    duration_minutes: Optional[int] = Field(None, ge=1, le=600)
    stream_url:       Optional[str] = Field(None, min_length=8, max_length=500)
    thumbnail_color:  Optional[str] = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    series_id:        Optional[str] = Field(None, max_length=50)
    episode_number:   Optional[int] = Field(None, ge=1, le=999)


def _validate_stream_url(url: str) -> None:
    if not (url.startswith("http://") or url.startswith("https://")):
        raise HTTPException(422, "stream_url http(s):// ile başlamalı")


@router.get("/catalog")
def catalog(
    genre:        Optional[str] = None,
    content_type: Optional[str] = None,
    token: dict = Depends(verify_token),
):
    db    = get_db()
    query = """
        SELECT cc.*,
               COALESCE(AVG(cr.rating), 0) AS avg_rating,
               COUNT(cr.id)               AS rating_count
        FROM content_catalog cc
        LEFT JOIN content_ratings cr ON cr.content_id = cc.id
        WHERE 1=1
    """
    args  = []
    if genre:
        query += " AND cc.genre = ?"
        args.append(genre)
    if content_type:
        query += " AND cc.content_type = ?"
        args.append(content_type)
    query += " GROUP BY cc.id ORDER BY cc.title ASC"
    rows  = db.execute(query, args).fetchall()
    db.close()
    return [
        dict(r) | {
            "avg_rating":   round(float(r["avg_rating"]), 1),
            "rating_count": int(r["rating_count"]),
        }
        for r in rows
    ]


# ── Admin İçerik Yönetimi (Sprint 21) ─────────────────────────
# NOT: /admin-list, /{content_id} catch-all'ından ÖNCE tanımlı olmalı.

@router.get("/admin-list")
def admin_content_list(token: dict = Depends(verify_token)):
    """Tüm videolar + gerçek kullanım istatistikleri — admin tablosu."""
    require_admin(token)
    db   = get_db()
    rows = db.execute("""
        SELECT cc.*,
               (SELECT COUNT(*) FROM watch_sessions ws
                WHERE ws.content_id=cc.id AND ws.ended_at IS NOT NULL) AS watch_count,
               (SELECT COALESCE(SUM(ws.watch_minutes),0) FROM watch_sessions ws
                WHERE ws.content_id=cc.id AND ws.ended_at IS NOT NULL) AS total_minutes,
               (SELECT COALESCE(AVG(rating),0) FROM content_ratings cr
                WHERE cr.content_id=cc.id) AS avg_rating,
               (SELECT COUNT(*) FROM content_ratings cr
                WHERE cr.content_id=cc.id) AS rating_count,
               (SELECT COUNT(*) FROM content_comments cm
                WHERE cm.content_id=cc.id) AS comment_count
        FROM content_catalog cc
        ORDER BY cc.title ASC
    """).fetchall()
    db.close()
    return [
        dict(r) | {
            "watch_count":   int(r["watch_count"]),
            "total_minutes": round(float(r["total_minutes"]), 1),
            "avg_rating":    round(float(r["avg_rating"]), 1),
            "rating_count":  int(r["rating_count"]),
            "comment_count": int(r["comment_count"]),
        }
        for r in rows
    ]


@router.post("/")
def create_content(body: ContentCreate, token: dict = Depends(verify_token)):
    """Kataloga yeni video ekle. Yeni tür otomatik olarak katalogda görünür
    ve Kaşif başarımının hedefini büyütür (dinamik target)."""
    require_admin(token)
    _validate_stream_url(body.stream_url)
    content_id = "v_" + uuid.uuid4().hex[:8]
    db = get_db()
    db.execute(
        "INSERT INTO content_catalog "
        "(id, title, content_type, genre, duration_minutes, series_id, "
        " episode_number, stream_url, thumbnail_color) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (content_id, body.title.strip(), body.content_type.strip().lower(),
         body.genre.strip().lower(), body.duration_minutes,
         body.series_id.strip() if body.series_id else None,
         body.episode_number, body.stream_url.strip(), body.thumbnail_color),
    )
    db.commit()
    row = db.execute("SELECT * FROM content_catalog WHERE id=?", (content_id,)).fetchone()
    db.close()
    return dict(row)


@router.put("/{content_id}")
def update_content(content_id: str, body: ContentUpdate,
                   token: dict = Depends(verify_token)):
    """Videoyu kısmi güncelle."""
    require_admin(token)
    if body.stream_url is not None:
        _validate_stream_url(body.stream_url)
    db  = get_db()
    row = db.execute("SELECT * FROM content_catalog WHERE id=?", (content_id,)).fetchone()
    if not row:
        db.close()
        raise HTTPException(404, "İçerik bulunamadı")
    updates = {
        "title":            body.title.strip() if body.title is not None else row["title"],
        "content_type":     body.content_type.strip().lower() if body.content_type is not None else row["content_type"],
        "genre":            body.genre.strip().lower() if body.genre is not None else row["genre"],
        "duration_minutes": body.duration_minutes if body.duration_minutes is not None else row["duration_minutes"],
        "stream_url":       body.stream_url.strip() if body.stream_url is not None else row["stream_url"],
        "thumbnail_color":  body.thumbnail_color if body.thumbnail_color is not None else row["thumbnail_color"],
        "series_id":        body.series_id if body.series_id is not None else row["series_id"],
        "episode_number":   body.episode_number if body.episode_number is not None else row["episode_number"],
    }
    db.execute(
        "UPDATE content_catalog SET title=?, content_type=?, genre=?, "
        "duration_minutes=?, stream_url=?, thumbnail_color=?, series_id=?, "
        "episode_number=? WHERE id=?",
        (updates["title"], updates["content_type"], updates["genre"],
         updates["duration_minutes"], updates["stream_url"],
         updates["thumbnail_color"], updates["series_id"],
         updates["episode_number"], content_id),
    )
    db.commit()
    updated = db.execute("SELECT * FROM content_catalog WHERE id=?", (content_id,)).fetchone()
    db.close()
    return dict(updated)


@router.delete("/{content_id}")
def delete_content(content_id: str, token: dict = Depends(verify_token)):
    """Videoyu sil. İzleme geçmişi varsa veri bütünlüğü için reddedilir."""
    require_admin(token)
    db  = get_db()
    row = db.execute("SELECT id FROM content_catalog WHERE id=?", (content_id,)).fetchone()
    if not row:
        db.close()
        raise HTTPException(404, "İçerik bulunamadı")
    watched = db.execute(
        "SELECT COUNT(*) AS c FROM watch_sessions WHERE content_id=?", (content_id,)
    ).fetchone()["c"]
    if watched > 0:
        db.close()
        raise HTTPException(
            409, f"Bu videonun {watched} izleme kaydı var — veri bütünlüğü "
                 f"için silinemez. Gerekirse stream_url'i değiştirin.")
    db.execute("DELETE FROM content_ratings WHERE content_id=?", (content_id,))
    db.execute("DELETE FROM content_comments WHERE content_id=?", (content_id,))
    db.execute("DELETE FROM content_ai_summaries WHERE content_id=?", (content_id,))
    db.execute("DELETE FROM content_catalog WHERE id=?", (content_id,))
    db.commit()
    db.close()
    return {"deleted": content_id}


@router.get("/{content_id}")
def get_content(
    content_id: str,
    token: dict = Depends(verify_token),
):
    db  = get_db()
    row = db.execute(
        "SELECT * FROM content_catalog WHERE id = ?",
        (content_id,)
    ).fetchone()
    db.close()
    if not row:
        raise HTTPException(404, "Icerik bulunamadi")
    return dict(row)


@router.get("/{content_id}/detail")
def content_detail(content_id: str, token: dict = Depends(verify_token)):
    """Detay sayfası: gerçek istatistikler + yıldız dağılımı + benzer videolar."""
    from engine.content_ai_engine import get_content_detail
    detail = get_content_detail(content_id, token["sub"])
    if detail is None:
        raise HTTPException(404, "Icerik bulunamadi")
    return detail


@router.get("/{content_id}/review-summary")
def content_review_summary(content_id: str, token: dict = Depends(verify_token)):
    """GPT-4o topluluk özeti — gerçek yorum+puan verisinden, cache'li."""
    from engine.content_ai_engine import build_review_summary
    return build_review_summary(content_id)
