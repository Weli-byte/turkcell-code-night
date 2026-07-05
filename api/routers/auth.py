from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from database.setup import get_db
from api.auth_utils import hash_password, create_token, verify_token
import uuid
from datetime import datetime

router = APIRouter(tags=["Auth"])


class AuthBody(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=4)


@router.post("/register")
def register(body: AuthBody):
    db = get_db()
    existing = db.execute(
        "SELECT id FROM users WHERE username = ?",
        (body.username,)
    ).fetchone()
    if existing:
        db.close()
        raise HTTPException(400, "Bu kullanici adi zaten alinmis")

    user_id = "user_" + uuid.uuid4().hex[:12]
    db.execute("""
        INSERT INTO users (id, username, password_hash, role, created_at)
        VALUES (?, ?, ?, 'user', ?)
    """, (user_id, body.username,
          hash_password(body.password),
          datetime.now().isoformat()))
    db.commit()
    db.close()

    token = create_token(user_id, body.username, "user")
    return {
        "token":    token,
        "user_id":  user_id,
        "username": body.username,
        "role":     "user",
    }


@router.post("/login")
def login(body: AuthBody):
    db = get_db()
    user = db.execute("""
        SELECT id, username, password_hash, role
        FROM users WHERE username = ?
    """, (body.username,)).fetchone()
    db.close()

    if not user or user["password_hash"] != hash_password(body.password):
        raise HTTPException(401, "Kullanici adi veya sifre yanlis")

    token = create_token(user["id"], user["username"], user["role"])
    return {
        "token":    token,
        "user_id":  user["id"],
        "username": user["username"],
        "role":     user["role"],
    }


@router.post("/refresh")
def refresh_token(token: dict = Depends(verify_token)):
    """Gecerli token varsa yeni token uret (sureyi uzat)."""
    new_token = create_token(
        token["sub"],
        token["username"],
        token["role"],
    )
    return {"token": new_token}
