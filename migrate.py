from database import engine

with engine.connect() as conn:
    conn.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS paypal_order_id VARCHAR")
    conn.commit()
    print("Migration done ✅")