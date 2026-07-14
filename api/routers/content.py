"""api/routers/content.py — video katalogu (DB'den)."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from database.setup import get_db
from api.auth_utils import verify_token

router = APIRouter(prefix="/api/content", tags=["content"])


@router.get("/catalog")
def catalog(
    genre: Optional[str] = None,
    content_type: Optional[str] = None,
    token: dict = Depends(verify_token),
):
    query = (
        "SELECT id, title, content_type, genre, duration_minutes, "
        "series_id, episode_number, stream_url, thumbnail_color "
        "FROM content_catalog"
    )
    clauses = []
    params = []
    if genre:
        clauses.append("genre = ?")
        params.append(genre)
    if content_type:
        clauses.append("content_type = ?")
        params.append(content_type)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY title"

    db = get_db()
    try:
        rows = db.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()


@router.get("/{content_id}")
def get_content(content_id: str, token: dict = Depends(verify_token)):
    db = get_db()
    try:
        row = db.execute(
            "SELECT id, title, content_type, genre, duration_minutes, "
            "series_id, episode_number, stream_url, thumbnail_color "
            "FROM content_catalog WHERE id=?",
            (content_id,),
        ).fetchone()
    finally:
        db.close()

    if not row:
        raise HTTPException(status_code=404, detail="Video bulunamadi")
    return dict(row)
