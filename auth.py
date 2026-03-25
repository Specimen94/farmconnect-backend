# auth.py
# Handles two things:
#   1. Password hashing (bcrypt directly — no passlib)
#   2. JWT token creation and verification (python-jose)

import os
import bcrypt
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from database import get_db
import models

load_dotenv()

SECRET_KEY         = os.getenv("SECRET_KEY", "change-this-in-production")
ALGORITHM          = "HS256"
TOKEN_EXPIRE_HOURS = 24 * 7

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ── PASSWORD HELPERS ──────────────────────────────────────────────────────────
def hash_password(plain: str) -> str:
    """Hash a password using bcrypt directly."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a login attempt against the stored hash."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ── JWT HELPERS ───────────────────────────────────────────────────────────────
def create_token(user_id: str, role: str) -> str:
    payload = {
        "sub":  user_id,
        "role": role,
        "exp":  datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


# ── FASTAPI DEPENDENCY ────────────────────────────────────────────────────────
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> models.User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(token)
    if not payload:
        raise credentials_error

    user = db.query(models.User).filter(
        models.User.id == payload["sub"]
    ).first()
    if not user or not user.is_active:
        raise credentials_error
    return user


def require_role(*roles: str):
    """Role-based access control dependency factory."""
    def checker(current_user: models.User = Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access restricted to: {', '.join(roles)}"
            )
        return current_user
    return checker