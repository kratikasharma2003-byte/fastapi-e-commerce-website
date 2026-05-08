from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

DATABASE_URL = "postgresql://postgres:root@localhost:5432/authdb"

try:
    engine = create_engine(DATABASE_URL)

    with engine.connect() as connection:
        print("✅ Database connection successful!")

except OperationalError as e:
    print("❌ Database connection failed!")
    print(e)

except Exception as e:
    print("❌ Unexpected error:")
    print(e)