# models.py
# Defines every database table as a Python class.
# SQLAlchemy translates these into real PostgreSQL tables.
#
# TABLES:
#   User          → stores all account types (buyer, farmer, transporter, admin)
#   Product       → marketplace listings, linked to a farmer (User)
#   Order         → purchase records, linked to buyer + seller (both Users)
#   LogisticsJob  → delivery jobs, linked to an Order + optionally a driver (User)
#   Conversation  → chat threads between two users
#   Message       → individual chat messages inside a Conversation

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, Boolean,
    DateTime, ForeignKey, Text, Enum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from database import Base


def new_uuid():
    return str(uuid.uuid4())


# ── USERS ─────────────────────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id         = Column(String, primary_key=True, default=new_uuid)
    username   = Column(String, unique=True, nullable=False, index=True)
    email      = Column(String, unique=True, nullable=True)   # optional for MVP
    name       = Column(String, nullable=False)
    role       = Column(
        Enum("Buyer", "Farmer", "Transporter", "Admin", name="user_role"),
        nullable=False
    )
    password_hash = Column(String, nullable=False)

    # Extended profile fields
    phone      = Column(String, nullable=True)
    location   = Column(String, nullable=True)
    nin        = Column(String, nullable=True)     # Nigerian ID number
    is_active  = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)   # NIN verified by admin

    wallet_balance = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    products   = relationship("Product",      back_populates="seller")
    orders_as_buyer  = relationship("Order", back_populates="buyer",
                                    foreign_keys="Order.buyer_id")
    orders_as_seller = relationship("Order", back_populates="seller",
                                    foreign_keys="Order.seller_id")
    jobs_as_driver   = relationship("LogisticsJob", back_populates="driver")


# ── PRODUCTS ──────────────────────────────────────────────────────────────────
class Product(Base):
    __tablename__ = "products"

    id         = Column(String, primary_key=True, default=new_uuid)
    name       = Column(String, nullable=False)
    category   = Column(
        Enum("grains", "tubers", "vegetables", "fruits", "oils", name="product_category"),
        nullable=False
    )
    price      = Column(Float, nullable=False)
    unit       = Column(String, nullable=False)       # e.g. "50kg Bag"
    stock      = Column(String, default="Medium")     # High / Medium / Low / etc.
    trend      = Column(String, default="stable")     # up / down / stable
    icon       = Column(String, default="📦")
    location   = Column(String, nullable=True)
    desc       = Column(Text, nullable=True)
    is_active  = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    seller_id  = Column(String, ForeignKey("users.id"), nullable=True)
    seller     = relationship("User", back_populates="products")


# ── ORDERS ────────────────────────────────────────────────────────────────────
class Order(Base):
    __tablename__ = "orders"

    id             = Column(String, primary_key=True, default=new_uuid)
    item           = Column(String, nullable=False)   # e.g. "3x Local Rice (Ofada)"
    icon           = Column(String, default="📦")
    quantity       = Column(Integer, default=1)
    amount         = Column(Float, nullable=False)    # total including fees
    payment_method = Column(String, default="transfer")
    status         = Column(String, default="Processing")
    # Status values: Processing → In Transit → Delivered | Cancelled

    buyer_address  = Column(String, nullable=True)
    buyer_phone    = Column(String, nullable=True)

    buyer_id   = Column(String, ForeignKey("users.id"), nullable=True)
    seller_id  = Column(String, ForeignKey("users.id"), nullable=True)
    product_id = Column(String, ForeignKey("products.id"), nullable=True)

    buyer  = relationship("User", back_populates="orders_as_buyer",
                          foreign_keys=[buyer_id])
    seller = relationship("User", back_populates="orders_as_seller",
                          foreign_keys=[seller_id])
    job    = relationship("LogisticsJob", back_populates="order", uselist=False)

    created_at = Column(DateTime, default=datetime.utcnow)


# ── LOGISTICS JOBS ────────────────────────────────────────────────────────────
class LogisticsJob(Base):
    __tablename__ = "logistics_jobs"

    id         = Column(String, primary_key=True, default=new_uuid)
    product    = Column(String, nullable=False)   # display name of what's being delivered
    pickup     = Column(String, nullable=False)
    dropoff    = Column(String, nullable=False)
    weight     = Column(Float, default=0)         # kg
    pay        = Column(Float, default=4500)      # driver payout in ₦
    distance   = Column(String, default="")       # e.g. "45km"
    status     = Column(String, default="pending")
    # Status values: pending → active → delivered

    order_id   = Column(String, ForeignKey("orders.id"), nullable=True)
    driver_id  = Column(String, ForeignKey("users.id"), nullable=True)

    order  = relationship("Order", back_populates="job")
    driver = relationship("User", back_populates="jobs_as_driver")

    created_at = Column(DateTime, default=datetime.utcnow)


# ── CONVERSATIONS ─────────────────────────────────────────────────────────────
class Conversation(Base):
    __tablename__ = "conversations"

    id         = Column(String, primary_key=True, default=new_uuid)
    user_a_id  = Column(String, ForeignKey("users.id"), nullable=False)
    user_b_id  = Column(String, ForeignKey("users.id"), nullable=False)
    product_id = Column(String, ForeignKey("products.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    messages   = relationship("Message", back_populates="conversation",
                              order_by="Message.created_at")


# ── MESSAGES ──────────────────────────────────────────────────────────────────
class Message(Base):
    __tablename__ = "messages"

    id              = Column(String, primary_key=True, default=new_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    sender_id       = Column(String, ForeignKey("users.id"), nullable=False)
    text            = Column(Text, nullable=True)
    msg_type        = Column(String, default="text")   # text | offer
    offer_price     = Column(Float, nullable=True)     # set when msg_type = offer
    created_at      = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")