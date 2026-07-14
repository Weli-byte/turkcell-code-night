"""api/routers/ingestion.py — CSV yukleme (admin) ve import gecmisi."""

import os
import tempfile

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File

from database.setup import get_db
from engine.csv_ingestion import load_csv, CSV_MARKER
from api.auth_utils import verify_token, require_admin

router = APIRouter(prefix="/api/ingestion", tags=["ingestion"])


@router.post("/csv")
async def upload_csv(file: UploadFile = File(...), token: dict = Depends(verify_token)):
    require_admin(token)

    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Sadece .csv dosyasi kabul edilir")

    content = await file.read()
    fd, tmp_path = tempfile.mkstemp(suffix=".csv")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(content)
        result = load_csv(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    result["filename"] = file.filename
    return result


@router.get("/status")
def status(token: dict = Depends(verify_token)):
    require_admin(token)
    db = get_db()
    try:
        rows = db.execute(
            "SELECT activity_date, COUNT(*) AS cnt FROM user_activities "
            "WHERE session_id=? GROUP BY activity_date ORDER BY activity_date DESC",
            (CSV_MARKER,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()
