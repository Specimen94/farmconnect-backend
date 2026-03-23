# schemas.py
# Pydantic models — these define what JSON goes IN and OUT of every endpoint.
# FastAPI uses these for automatic validation and the Swagger docs page.
#
# Naming convention:
#   XxxCreate  → body of a POST request (what the frontend sends)
#   XxxOut     → what the API returns (what the frontend receives)

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel


# ── AUTH ──────────────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    firstName:  str
    lastName:   str
    username:   str
    password:   str
    role:       str           # "buyer" | "farmer" | "transporter"
    phone:      Optional[str] = None
    location:   Optional[str] = None
    nin:        Optional[str] = None


class UserOut(BaseModel):
    id:          str
    name:        str
    username:    str
    role:        str
    phone:       Optional[str]
    location:    Optional[str]
    is_verified: bool
    wallet_balance: float
    isLoggedIn:  bool = True   # frontend expects this field

    class Config:
        from_attributes = True   # lets Pydantic read SQLAlchemy objects


class AuthResponse(BaseModel):
    user:  UserOut
    token: str


# ── PRODUCTS ──────────────────────────────────────────────────────────────────
class ProductCreate(BaseModel):
    name:      str
    category:  str
    price:     float
    unit:      str
    stock:     Optional[str]  = "Medium"
    trend:     Optional[str]  = "stable"
    icon:      Optional[str]  = "📦"
    location:  Optional[str]  = None
    desc:      Optional[str]  = None


class ProductOut(BaseModel):
    id:        str
    name:      str
    category:  str
    price:     float
    unit:      str
    stock:     str
    trend:     str
    icon:      str
    location:  Optional[str]
    desc:      Optional[str]
    seller_id: Optional[str]

    class Config:
        from_attributes = True


# ── ORDERS ────────────────────────────────────────────────────────────────────
class OrderCreate(BaseModel):
    item:           str
    icon:           Optional[str]  = "📦"
    productId:      Optional[str]  = None
    quantity:       Optional[int]  = 1
    amount:         float
    paymentMethod:  Optional[str]  = "transfer"
    buyer:          Optional[str]  = None    # display name
    buyerPhone:     Optional[str]  = None
    buyerAddress:   Optional[str]  = None
    seller:         Optional[str]  = None    # display name / location
    sellerId:       Optional[str]  = None    # farmer's user ID


class OrderOut(BaseModel):
    id:      str
    item:    str
    icon:    str
    amount:  float
    status:  str
    date:    str              # formatted string for frontend
    buyer:   Optional[str]
    seller:  Optional[str]

    class Config:
        from_attributes = True


# ── LOGISTICS ─────────────────────────────────────────────────────────────────
class JobOut(BaseModel):
    id:       str
    product:  str
    pickup:   str
    dropoff:  str
    weight:   float
    pay:      float
    distance: str
    status:   str
    orderId:  Optional[str]    # frontend expects camelCase

    class Config:
        from_attributes = True


# ── USER PROFILE ──────────────────────────────────────────────────────────────
class ProfileUpdate(BaseModel):
    phone:    Optional[str] = None
    location: Optional[str] = None


# ── ADMIN ─────────────────────────────────────────────────────────────────────
class UserAdminOut(BaseModel):
    id:          str
    name:        str
    username:    str
    role:        str
    is_active:   bool
    is_verified: bool
    created_at:  datetime

    class Config:
        from_attributes = True