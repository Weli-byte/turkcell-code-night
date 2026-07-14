"""api/routers/pipeline.py — admin pipeline tetikleme."""

from fastapi import APIRouter, Depends

from engine.pipeline import run_pipeline
from api.auth_utils import verify_token, require_admin

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


@router.post("/run")
def trigger(token: dict = Depends(verify_token)):
    require_admin(token)
    return run_pipeline()
