# main.py
# The entire FarmConnect API lives here.
# FastAPI automatically generates Swagger docs at /docs
# and ReDoc at /redoc — use these to test every endpoint.
#
# ROUTE GROUPS:
#   /api/auth        → login, register
#   /api/products    → browse, create listings
#   /api/orders      → place, track, update orders
#   /api/logistics   → driver job board
#   /api/users       → profile, admin tools

import math
import random
import string
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

import models, schemas
from auth import (
    hash_password, verify_password,
    create_token, get_current_user, require_role
)
from database import engine, get_db
import models as m

app = FastAPI(
    title="FarmConnect API",
    description="Backend for the FarmConnect agricultural marketplace",
    version="1.0.0",
)

@app.on_event("startup")
async def startup_event():
    """Runs once when the server starts. Creates any missing DB tables."""
    try:
        models.Base.metadata.create_all(bind=engine)
        print("✅ Database tables created/verified successfully")
    except Exception as e:
        print(f"⚠️  Database startup error: {e}")


# ── CORS ──────────────────────────────────────────────────────────────────────
# Allows your Vercel frontend to call this API.
# In production, replace "*" with your exact Vercel URL.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://farmconnect-ivory.vercel.app",
        "http://localhost:5500",    # VS Code Live Server
        "http://127.0.0.1:5500",
        "*",                        # remove this line after testing
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── HELPERS ───────────────────────────────────────────────────────────────────
def format_date(dt: datetime) -> str:
    """Convert a datetime to the display format the frontend expects."""
    return dt.strftime("%d %b %Y").lstrip("0")   # e.g. "15 Feb 2026"


def order_id() -> str:
    """Generate a readable order ID like FC-48291."""
    return "FC-" + "".join(random.choices(string.digits, k=5))


# ══════════════════════════════════════════════════════════════════════════════
# AUTH ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/api/auth/register", response_model=schemas.AuthResponse)
def register(body: schemas.RegisterRequest, db: Session = Depends(get_db)):
    """
    Create a new account. Returns the user object + JWT token.
    Frontend sends: { firstName, lastName, username, password, role, ... }
    """
    # Block duplicate usernames
    if db.query(m.User).filter(m.User.username == body.username).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken"
        )

    role_map = {
        "farmer":      "Farmer",
        "buyer":       "Buyer",
        "transporter": "Transporter",
    }
    role = role_map.get(body.role.lower(), "Buyer")

    user = m.User(
        name          = f"{body.firstName} {body.lastName}",
        username      = body.username.lower(),
        role          = role,
        password_hash = hash_password(body.password),
        phone         = body.phone,
        location      = body.location,
        nin           = body.nin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_token(user.id, user.role)
    return {"user": user, "token": token}


@app.post("/api/auth/login", response_model=schemas.AuthResponse)
def login(body: schemas.LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate and return a JWT token.
    Frontend sends: { username, password }
    """
    user = db.query(m.User).filter(
        m.User.username == body.username.lower()
    ).first()

    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been suspended"
        )

    token = create_token(user.id, user.role)
    return {"user": user, "token": token}


# ══════════════════════════════════════════════════════════════════════════════
# PRODUCT ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/products", response_model=List[schemas.ProductOut])
def get_products(
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Return all active products. Optionally filter by category.
    Public — no login required (buyers can browse before signing up).
    """
    q = db.query(m.Product).filter(m.Product.is_active == True)
    if category:
        q = q.filter(m.Product.category == category)
    return q.order_by(m.Product.created_at.desc()).all()


@app.get("/api/products/{product_id}", response_model=schemas.ProductOut)
def get_product(product_id: str, db: Session = Depends(get_db)):
    """Return a single product by its ID."""
    product = db.query(m.Product).filter(
        m.Product.id == product_id,
        m.Product.is_active == True
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@app.post("/api/products", response_model=schemas.ProductOut,
          status_code=status.HTTP_201_CREATED)
def create_product(
    body: schemas.ProductCreate,
    current_user: m.User = Depends(require_role("Farmer", "Admin")),
    db: Session = Depends(get_db)
):
    """
    Create a new product listing. Farmers only.
    The seller_id is set automatically from the logged-in user's JWT.
    """
    product = m.Product(
        **body.model_dump(),
        seller_id = current_user.id
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@app.delete("/api/products/{product_id}", status_code=204)
def delete_product(
    product_id: str,
    current_user: m.User = Depends(require_role("Farmer", "Admin")),
    db: Session = Depends(get_db)
):
    """Soft-delete a product (sets is_active = False)."""
    product = db.query(m.Product).filter(m.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if product.seller_id != current_user.id and current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="Not your listing")
    product.is_active = False
    db.commit()


# ══════════════════════════════════════════════════════════════════════════════
# ORDER ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/orders/mine", response_model=List[schemas.OrderOut])
def get_my_orders(
    current_user: m.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Return all orders placed by the logged-in buyer."""
    orders = db.query(m.Order).filter(
        m.Order.buyer_id == current_user.id
    ).order_by(m.Order.created_at.desc()).all()

    # Format dates for frontend
    result = []
    for o in orders:
        result.append({
            "id":     o.id,
            "item":   o.item,
            "icon":   o.icon,
            "amount": o.amount,
            "status": o.status,
            "date":   format_date(o.created_at),
            "buyer":  current_user.name,
            "seller": o.seller.name if o.seller else None,
        })
    return result


@app.get("/api/orders/farmer", response_model=List[schemas.OrderOut])
def get_farmer_orders(
    current_user: m.User = Depends(require_role("Farmer", "Admin")),
    db: Session = Depends(get_db)
):
    """Return all orders received by the logged-in farmer."""
    orders = db.query(m.Order).filter(
        m.Order.seller_id == current_user.id
    ).order_by(m.Order.created_at.desc()).all()

    result = []
    for o in orders:
        result.append({
            "id":     o.id,
            "item":   o.item,
            "icon":   o.icon,
            "amount": o.amount,
            "status": o.status,
            "date":   format_date(o.created_at),
            "buyer":  o.buyer.name if o.buyer else None,
            "seller": current_user.name,
        })
    return result


@app.post("/api/orders", response_model=schemas.OrderOut,
          status_code=status.HTTP_201_CREATED)
def create_order(
    body: schemas.OrderCreate,
    current_user: m.User = Depends(require_role("Buyer")),
    db: Session = Depends(get_db)
):
    """
    Place a new order. Buyers only.
    Also auto-creates a pending logistics job for the order.
    """
    order = m.Order(
        id             = order_id(),
        item           = body.item,
        icon           = body.icon or "📦",
        quantity       = body.quantity or 1,
        amount         = body.amount,
        payment_method = body.paymentMethod or "transfer",
        buyer_address  = body.buyerAddress,
        buyer_phone    = body.buyerPhone,
        buyer_id       = current_user.id,
        seller_id      = body.sellerId,
        product_id     = body.productId,
        status         = "Processing",
    )
    db.add(order)
    db.flush()   # get the order.id before committing

    # Auto-create a logistics job for every order
    job = m.LogisticsJob(
        product  = body.item,
        pickup   = body.seller or "Farm Depot",
        dropoff  = body.buyerAddress or "Buyer Location",
        weight   = random.uniform(10, 80),
        pay      = 4500,
        distance = f"{random.randint(5, 150)}km",
        status   = "pending",
        order_id = order.id,
    )
    db.add(job)
    db.commit()
    db.refresh(order)

    return {
        "id":     order.id,
        "item":   order.item,
        "icon":   order.icon,
        "amount": order.amount,
        "status": order.status,
        "date":   format_date(order.created_at),
        "buyer":  current_user.name,
        "seller": body.seller,
    }


@app.patch("/api/orders/{order_id}/status")
def update_order_status(
    order_id: str,
    body: dict,
    current_user: m.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update an order's status. Used by logistics to mark delivered."""
    order = db.query(m.Order).filter(m.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    order.status = body.get("status", order.status)
    db.commit()
    return {"success": True}


# ══════════════════════════════════════════════════════════════════════════════
# LOGISTICS ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/logistics/jobs", response_model=List[schemas.JobOut])
def get_jobs(
    current_user: m.User = Depends(require_role("Transporter", "Admin")),
    db: Session = Depends(get_db)
):
    """Return all available + active logistics jobs."""
    jobs = db.query(m.LogisticsJob).filter(
        m.LogisticsJob.status.in_(["pending", "active"])
    ).order_by(m.LogisticsJob.created_at.desc()).all()

    # Map snake_case DB field to camelCase for frontend
    return [
        {
            "id":      j.id,
            "product": j.product,
            "pickup":  j.pickup,
            "dropoff": j.dropoff,
            "weight":  j.weight,
            "pay":     j.pay,
            "distance": j.distance,
            "status":  j.status,
            "orderId": j.order_id,
        }
        for j in jobs
    ]


@app.patch("/api/logistics/jobs/{job_id}/accept")
def accept_job(
    job_id: str,
    current_user: m.User = Depends(require_role("Transporter")),
    db: Session = Depends(get_db)
):
    """Driver accepts a job — sets status to active and links driver."""
    job = db.query(m.LogisticsJob).filter(m.LogisticsJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "pending":
        raise HTTPException(status_code=400, detail="Job is no longer available")

    job.status    = "active"
    job.driver_id = current_user.id

    # Also update the linked order
    if job.order:
        job.order.status = "In Transit"

    db.commit()
    return {"success": True}


@app.patch("/api/logistics/jobs/{job_id}/complete")
def complete_job(
    job_id: str,
    current_user: m.User = Depends(require_role("Transporter")),
    db: Session = Depends(get_db)
):
    """Driver marks a job as delivered."""
    job = db.query(m.LogisticsJob).filter(
        m.LogisticsJob.id == job_id,
        m.LogisticsJob.driver_id == current_user.id
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job.status = "delivered"

    if job.order:
        job.order.status = "Delivered"

    db.commit()
    return {"success": True}


# ══════════════════════════════════════════════════════════════════════════════
# USER / PROFILE ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/users/me", response_model=schemas.UserOut)
def get_profile(current_user: m.User = Depends(get_current_user)):
    """Return the logged-in user's full profile."""
    return current_user


@app.patch("/api/users/me", response_model=schemas.UserOut)
def update_profile(
    body: schemas.ProfileUpdate,
    current_user: m.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update phone and/or location."""
    if body.phone    is not None: current_user.phone    = body.phone
    if body.location is not None: current_user.location = body.location
    db.commit()
    db.refresh(current_user)
    return current_user


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/admin/users", response_model=List[schemas.UserAdminOut])
def admin_get_users(
    current_user: m.User = Depends(require_role("Admin")),
    db: Session = Depends(get_db)
):
    """List all users. Admin only."""
    return db.query(m.User).order_by(m.User.created_at.desc()).all()


@app.patch("/api/admin/users/{user_id}/ban")
def admin_toggle_ban(
    user_id: str,
    current_user: m.User = Depends(require_role("Admin")),
    db: Session = Depends(get_db)
):
    """Toggle a user's active/banned status."""
    user = db.query(m.User).filter(m.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = not user.is_active
    db.commit()
    return {"is_active": user.is_active}


@app.get("/api/admin/verifications", response_model=List[schemas.UserAdminOut])
def admin_pending_verifications(
    current_user: m.User = Depends(require_role("Admin")),
    db: Session = Depends(get_db)
):
    """Return users whose NIN has not been verified yet."""
    return db.query(m.User).filter(
        m.User.nin != None,
        m.User.is_verified == False
    ).all()


@app.patch("/api/admin/verifications/{user_id}/approve")
def admin_approve_verification(
    user_id: str,
    current_user: m.User = Depends(require_role("Admin")),
    db: Session = Depends(get_db)
):
    """Mark a user's NIN as verified."""
    user = db.query(m.User).filter(m.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_verified = True
    db.commit()
    return {"success": True}


@app.get("/api/admin/stats")
def admin_stats(
    current_user: m.User = Depends(require_role("Admin")),
    db: Session = Depends(get_db)
):
    """Dashboard stats for the admin panel."""
    total    = db.query(m.User).count()
    farmers  = db.query(m.User).filter(m.User.role == "Farmer").count()
    buyers   = db.query(m.User).filter(m.User.role == "Buyer").count()
    logistics = db.query(m.User).filter(m.User.role == "Transporter").count()
    return {
        "totalUsers": total,
        "farmers":    farmers,
        "buyers":     buyers,
        "logistics":  logistics,
    }


# ── HEALTH CHECK ──────────────────────────────────────────────────────────────
@app.get("/")
def health():
    """Render uses this to confirm the service is running."""
    return {"status": "FarmConnect API is running"}