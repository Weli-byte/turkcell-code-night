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
    query = "SELECT * FROM content_catalog WHERE 1=1"
    args  = []
    if genre:
        query += " AND genre = ?"
        args.append(genre)
    if content_type:
        query += " AND content_type = ?"
        args.append(content_type)
    query += " ORDER BY title ASC"
    rows  = db.execute(query, args).fetchall()
    db.close()
    return [dict(r) for r in rows]


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
