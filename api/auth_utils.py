import hashlib
import os
import jwt
from datetime import datetime, timedelta
from fastapi import HTTPException, Header
from typing import Optional

SECRET    = os.environ.get("SECRET_KEY", "gizli_anahtar_degistir_2026")
ALGORITHM = "HS256"
EXPIRE_H  = 24


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def create_token(user_id: str, username: str, role: str) -> str:
    payload = {
        "sub":      user_id,
        "username": username,
        "role":     role,
        "exp":      datetime.utcnow() + timedelta(hours=EXPIRE_H),
    }
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)


def verify_token(
    authorization: Optional[str] = Header(None)
) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Token gerekli")
    token = authorization.split(" ", 1)[1]
    try:
        return jwt.decode(token, SECRET, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token suresi doldu")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Gecersiz token")


def require_admin(token: dict) -> dict:
    if token.get("role") != "admin":
        raise HTTPException(403, "Admin yetkisi gerekli")
    return token
