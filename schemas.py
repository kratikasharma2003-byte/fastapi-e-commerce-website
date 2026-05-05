from pydantic import BaseModel, EmailStr
from typing import Optional


class UserLogin(BaseModel):
    email: EmailStr
    password: str

class ForgotPassword(BaseModel):
    email: EmailStr

class VerifyOTP(BaseModel):
    email: EmailStr
    otp: str

class ResetPassword(BaseModel):
    email: EmailStr
    new_password: str
    confirm_password: str

class ProductCreate(BaseModel):
    name: str
    price: float
    description: Optional[str] = ""
    image_url: Optional[str] = ""
    category: Optional[str] = "General"
    stock: Optional[int] = 0

class ProductResponse(BaseModel):
    id: int
    name: str
    price: float
    description: str
    image_url: str
    category: str
    stock: int

    class Config:
        from_attributes = True


class EmailRequest(BaseModel):
    email: EmailStr