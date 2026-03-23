# auth.py
# Handles two things:
#   1. Password hashing (bcrypt via passlib)
#   2. JWT token creation and verification (python-jose)
#
# NEVER put your SECRET_KEY in code — it lives in .env only.

import os
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from database import get_db
import models

load_dotenv()

# ── CONFIG ────────────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-in-production")
ALGORITHM  = "HS256"
TOKEN_EXPIRE_HOURS = 24 * 7   # tokens last 7 days

pwd_context   = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ── PASSWORD HELPERS ──────────────────────────────────────────────────────────
def hash_password(plain: str) -> str:
    """Turn a plain password into a bcrypt hash for storage."""
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Check a login attempt against the stored hash."""
    return pwd_context.verify(plain, hashed)


# ── JWT HELPERS ───────────────────────────────────────────────────────────────
def create_token(user_id: str, role: str) -> str:
    """Create a signed JWT containing the user's id and role."""
    payload = {
        "sub":  user_id,
        "role": role,
        "exp":  datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """Decode a JWT. Returns the payload dict or None if invalid/expired."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


# ── FASTAPI DEPENDENCY ────────────────────────────────────────────────────────
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> models.User:
    """
    FastAPI dependency injected into any route that needs authentication.
    Usage in a route:  current_user: models.User = Depends(get_current_user)
    """
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_token(token)
    if not payload:
        raise credentials_error

    user = db.query(models.User).filter(models.User.id == payload["sub"]).first()
    if not user or not user.is_active:
        raise credentials_error

    return user


def require_role(*roles: str):
    """
    Role-based access control dependency factory.
    Usage:  Depends(require_role("Admin"))
            Depends(require_role("Farmer", "Admin"))
    """
    def checker(current_user: models.User = Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access restricted to: {', '.join(roles)}"
            )
        return current_user
    return checker