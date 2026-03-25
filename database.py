# database.py
# Handles the connection to PostgreSQL.
# SQLAlchemy creates a connection pool automatically.

import os
import ssl
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")

# Fix URL prefix for pg8000 driver
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+pg8000://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+pg8000://", 1)

# Strip any ?ssl_context=True from the URL — we handle SSL via connect_args
DATABASE_URL = DATABASE_URL.split("?")[0]

# Build a proper SSL context for Render's PostgreSQL
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

engine = create_engine(
    DATABASE_URL,
    connect_args={"ssl_context": ssl_context}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# Dependency used in every route that needs DB access.
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()