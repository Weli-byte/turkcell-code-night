from fastapi import APIRouter, Depends, HTTPException
from api.auth_utils import verify_token
from database.setup import get_db
from typing import Optional

router = APIRouter(tags=["Content"])


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
