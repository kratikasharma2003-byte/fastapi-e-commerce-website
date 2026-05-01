---
name: async-db
description: SQLAlchemy 2.x async session, query, and transaction patterns.
---

# Async Database (SQLAlchemy 2.x)

## Setup

```python
# app/database.py
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

engine = create_async_engine(settings.database_url, echo=settings.debug)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
```

## Model Definition (typed columns)

```python
from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
```

## Service Pattern

```python
from sqlalchemy import select

class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: int) -> User | None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def create(self, data: UserCreate) -> User:
        user = User(email=data.email, name=data.name)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user
```

## Explicit Transactions

```python
async def transfer(self, from_id: int, to_id: int, amount: int):
    async with self.db.begin():
        sender = await self.get_by_id(from_id)
        receiver = await self.get_by_id(to_id)
        sender.balance -= amount
        receiver.balance += amount
        # auto-commit on context exit
```

## Prevent N+1 with selectinload

```python
from sqlalchemy.orm import selectinload

result = await self.db.execute(
    select(User).options(selectinload(User.posts))
)
```
