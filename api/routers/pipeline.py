from fastapi import APIRouter, Depends
from api.auth_utils import verify_token, require_admin
from engine.pipeline import run_pipeline

router = APIRouter(tags=["Admin"])


@router.post("/run")
def trigger_pipeline(token: dict = Depends(verify_token)):
    require_admin(token)
    return run_pipeline()
