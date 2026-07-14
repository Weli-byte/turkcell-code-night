"""api/routers/auth.py — kayit / giris / token yenileme."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from database.setup import get_db
from api.auth_utils import hash_password, create_token, verify_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


class Credentials(BaseModel):
    username: str
    password: str


@router.post("/register")
def register(body: Credentials):
    username = body.username.strip()
    if not username or not body.password:
        raise HTTPException(status_code=400, detail="Kullanici adi ve parola gerekli")

    db = get_db()
    try:
        exists = db.execute(
            "SELECT 1 FROM users WHERE username=?", (username,)
        ).fetchone()
        if exists:
            raise HTTPException(status_code=400, detail="Bu kullanici adi zaten kayitli")

        user_id = "user_" + uuid.uuid4().hex[:12]
        db.execute(
            "INSERT INTO users (id, username, password_hash, role, created_at) "
            "VALUES (?,?,?,?,?)",
            (user_id, username, hash_password(body.password), "user",
             datetime.now().isoformat()),
        )
        db.commit()
    finally:
        db.close()

    token = create_token(user_id, username, "user")
    return {"token": token, "user_id": user_id, "username": username, "role": "user"}


@router.post("/login")
def login(body: Credentials):
    db = get_db()
    try:
        row = db.execute(
            "SELECT id, username, password_hash, role FROM users WHERE username=?",
            (body.username.strip(),),
        ).fetchone()
    finally:
        db.close()

    if not row or row["password_hash"] != hash_password(body.password):
        raise HTTPException(status_code=401, detail="Kullanici adi veya parola hatali")

    token = create_token(row["id"], row["username"], row["role"])
    return {
        "token": token,
        "user_id": row["id"],
        "username": row["username"],
        "role": row["role"],
    }


@router.post("/refresh")
def refresh(token: dict = Depends(verify_token)):
    new_token = create_token(token["sub"], token["username"], token["role"])
    return {"token": new_token}
