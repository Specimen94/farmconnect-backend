# database.py
# Handles the connection to PostgreSQL.
# SQLAlchemy creates a connection pool automatically.

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

# Render provides DATABASE_URL automatically when you attach a PostgreSQL DB.
# Locally, put it in your .env file.
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Render's PostgreSQL URLs start with "postgres://" but SQLAlchemy needs
# "postgresql://" — this one-liner fixes that silently.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+pg8000://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+pg8000://", 1)

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# Dependency used in every route that needs DB access.
# FastAPI calls this automatically via Depends(get_db).
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()