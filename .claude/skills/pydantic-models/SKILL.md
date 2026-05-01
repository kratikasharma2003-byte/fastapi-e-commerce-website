---
name: pydantic-models
description: Pydantic v2 patterns for validation, serialization, and settings management.
---

# Pydantic v2 Models

## Separate Input and Output Schemas

```python
# app/schemas/user.py
from pydantic import BaseModel, EmailStr, field_validator, ConfigDict
from datetime import datetime

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str

    @field_validator("password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

class UserResponse(BaseModel):
    id: int
    email: str
    name: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)  # replaces orm_mode=True

class UserUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
```

## Settings

```python
# app/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str
    secret_key: str
    debug: bool = False
    cors_origins: list[str] = []
    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
```

## Field Constraints

```python
from pydantic import Field

class Product(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    price: float = Field(gt=0, description="Price in USD")
    tags: list[str] = Field(default_factory=list)
```

## Cross-Field Validation

```python
from pydantic import model_validator

class DateRange(BaseModel):
    start: datetime
    end: datetime

    @model_validator(mode="after")
    def end_after_start(self) -> "DateRange":
        if self.end <= self.start:
            raise ValueError("end must be after start")
        return self
```

## Common Gotcha

Pydantic v2 replaces `class Config: orm_mode = True` with
`model_config = ConfigDict(from_attributes=True)`. The old style silently no-ops.
