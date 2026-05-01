---
name: fastapi-patterns
description: FastAPI patterns for routes, dependency injection, middleware, and error handling.
---

# FastAPI Patterns

## Router Organization

One file per resource. Mount all routers in `app/main.py`.

```python
# app/routers/users.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.user import UserCreate, UserResponse
from app.services.user_service import UserService

router = APIRouter(prefix="/api/v1/users", tags=["users"])

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    user = await UserService(db).get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.post("/", response_model=UserResponse, status_code=201)
async def create_user(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    return await UserService(db).create(payload)
```

## Shared Dependencies

```python
# app/dependencies.py
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.database import get_db
from app.services.auth_service import AuthService

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db=Depends(get_db),
):
    user = await AuthService(db).verify_token(credentials.credentials)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user
```

## Global Error Handling

```python
# in app/main.py
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})
```

## Lifespan (use this, not deprecated on_event)

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    await init_db()
    yield
    await engine.dispose()

app = FastAPI(lifespan=lifespan)
```

## Background Tasks

```python
from fastapi import BackgroundTasks

@router.post("/notify")
async def notify(bg: BackgroundTasks, email: str):
    bg.add_task(send_email, email)
    return {"queued": True}
```

## Mounting Routers

```python
# app/main.py
from app.routers import users, products
app.include_router(users.router)
app.include_router(products.router)
```
