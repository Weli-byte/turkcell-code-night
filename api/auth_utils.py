"""
api/auth_utils.py — JWT + parola yardimcilari.

SECRET_KEY ve ALGORITHM .env'den okunur. Token suresi 24 saat.
"""

import os
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from dotenv import load_dotenv
from fastapi import Header, HTTPException

load_dotenv()

SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY:
    # Fail-closed: bos secret ile JWT imzalanamaz (token sahtecilige acik olurdu).
    raise RuntimeError("SECRET_KEY .env'de tanimli olmali (bos birakilamaz)")
if len(SECRET_KEY) < 32:
    print("[auth] UYARI: SECRET_KEY 32 karakterden kisa — production'da guclu anahtar kullan.")

ALGORITHM = os.environ.get("ALGORITHM", "HS256")
TOKEN_TTL_HOURS = 24


def hash_password(password: str) -> str:
    """SHA256 hex digest."""
    return hashlib.sha256(password.encode()).hexdigest()


def create_token(user_id: str, username: str, role: str) -> str:
    """24 saatlik JWT uretir."""
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(authorization: Optional[str] = Header(None)) -> dict:
    """Bearer token dogrular. Gecersiz/suresi dolmus -> 401."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer token gerekli")
    token = authorization.split(" ", 1)[1].strip()
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token suresi dolmus")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Gecersiz token")


def require_admin(token: dict) -> dict:
    """role != admin -> 403."""
    if token.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin yetkisi gerekli")
    return token
