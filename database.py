import os
from dotenv import load_dotenv

# ── Load .env FIRST, before anything else ────────────────────────────────────
load_dotenv()

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "\n\n❌ DATABASE_URL is not set!\n"
        "Make sure your .env file exists in the project root and contains:\n"
        "  DATABASE_URL=postgresql://authuser:YourPassword@localhost:5432/authdb\n"
    )

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,   # auto-reconnect on stale connections
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db():
    """FastAPI dependency — yields a DB session and closes it when done."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()