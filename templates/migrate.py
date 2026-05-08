"""
Run this ONCE to add missing columns to your database.
Usage: python migrate.py
"""
from database import engine
from sqlalchemy import text

migrations = [
    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS stripe_session_id VARCHAR",
    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS transaction_id VARCHAR UNIQUE",
]

with engine.connect() as conn:
    for sql in migrations:
        try:
            conn.execute(text(sql))
            print(f"✅ {sql}")
        except Exception as e:
            print(f"⚠️  Skipped ({e})")
    conn.commit()
    print("\n✅ Migration complete! Restart your FastAPI server now.")