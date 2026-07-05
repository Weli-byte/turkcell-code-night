from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from api.auth_utils import verify_token, require_admin
from engine.csv_ingestion import load_csv
from database.setup import get_db
import tempfile
import os

router = APIRouter(tags=["Ingestion"])


@router.post("/csv")
async def upload_csv(
    file:  UploadFile = File(...),
    token: dict = Depends(verify_token),
):
    require_admin(token)
    if not file.filename.endswith(".csv"):
        raise HTTPException(400, "Sadece .csv kabul edilir")

    with tempfile.NamedTemporaryFile(
        delete=False, suffix=".csv", mode="wb"
    ) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        result = load_csv(tmp_path)
    finally:
        os.unlink(tmp_path)

    return result


@router.get("/status")
def ingestion_status(token: dict = Depends(verify_token)):
    require_admin(token)
    db   = get_db()
    rows = db.execute("""
        SELECT activity_date,
               COUNT(*) AS cnt
        FROM user_activities
        WHERE session_id = 'csv_import'
        GROUP BY activity_date
        ORDER BY activity_date DESC
        LIMIT 10
    """).fetchall()
    db.close()
    return [dict(r) for r in rows]
