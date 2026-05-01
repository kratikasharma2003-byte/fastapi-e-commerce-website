from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv


# ── Update these credentials to match your PostgreSQL setup ───────
DATABASE_URL = "postgresql+psycopg2://postgres:root@localhost:5432/authdb_new"

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,       # auto-reconnect on stale connections
    pool_size=10,             # keep up to 10 connections open
    max_overflow=20,          # allow up to 20 extra connections under load
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