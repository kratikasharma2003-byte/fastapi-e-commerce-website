import json
import time
import re
import uuid
import os

from contextlib import asynccontextmanager, contextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Depends, HTTPException, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from pydantic import BaseModel, EmailStr, constr, field_validator
from typing import Optional
from datetime import datetime, timezone
from loguru import logger
from sqlalchemy import or_, desc, asc
from fastapi.staticfiles import StaticFiles

# ── Load .env FIRST ─────────────────────────────────────────────────────────
logger.add("logs/app.log", rotation="1 MB")
from dotenv import load_dotenv
load_dotenv()
#DATABASE_URL = os.getenv("DATABASE_URL")
BASE_URL = os.getenv("BASE_URL")

import models, schemas, auth
from database import engine, get_db
from otp_store import generate_otp, verify_otp, is_verified
from email_utils import send_email, send_order_confirmation
from models import User, Product, CartItem, Order, OrderItem, Payment
from schemas import EmailRequest
import stripe

# ── Stripe Configuration ─────────────────────────────────────────────────────

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# ── Cache imports ────────────────────────────────────────────────────────────
from cache import (
    cache, Keys, TTL,
    invalidate_product, invalidate_user_profile,
    invalidate_cart, invalidate_user_orders,
    invalidate_admin_stats,
    redis_startup, redis_shutdown,
)

# ══════════════════════════════════════════════════════════════════
#  LIFESPAN  (startup + shutdown hooks)
# ══════════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── startup ──
    models.Base.metadata.create_all(bind=engine)
    try:
        redis_startup()
    except Exception:
        pass  # Redis is optional
    yield
    # ── shutdown ──
    try:
        redis_shutdown()
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════
#  APP SETUP
# ══════════════════════════════════════════════════════════════════

app = FastAPI(title="ShopFast API", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ── TemplateResponse fix (Starlette/Jinja2 version compatibility) ────────────
# Some Starlette versions swap the name/context arguments internally, causing
# 'dict has no attribute split' or 'unhashable type: dict' errors.
# This wrapper calls Jinja2 directly, bypassing the broken Starlette code path.
from starlette.responses import HTMLResponse as _HTMLResponse

def render(template_name: str, context: dict) -> _HTMLResponse:
    tmpl = templates.env.get_template(template_name)
    html = tmpl.render(**context)
    return _HTMLResponse(content=html)
# ─────────────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8000",
        "https://new-fastapi-e-commerce-website.onrender.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET", "change-me-in-production"),
    https_only=True,   # ← add this line
    same_site="none",  # ← add this line
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    import time

    start = time.time()

    try:
        response = await call_next(request)

        process_time = time.time() - start

        logger.info(
            f"{request.method} {request.url.path} "
            f"- {response.status_code} "
            f"- {process_time:.4f}s"
        )

        return response

    except Exception as e:
        logger.error(f"ERROR: {str(e)}")
        raise


@contextmanager
def db_transaction(db: Session):
    try:
        yield
        db.commit()
    except Exception as e:
        db.rollback()
        raise e


def _coerce_text(value, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value
    return str(value)


def _serialize_product(product) -> dict:
    if isinstance(product, dict):
        return {
            "id": product.get("id"),
            "name": _coerce_text(product.get("name")),
            "price": product.get("price"),
            "description": _coerce_text(product.get("description")),
            "image_url": _coerce_text(product.get("image_url") or product.get("image")),
            "category": _coerce_text(product.get("category"), "General"),
            "stock": product.get("stock") if product.get("stock") is not None else 0,
        }

    return {
        "id": product.id,
        "name": _coerce_text(product.name),
        "price": product.price,
        "description": _coerce_text(product.description),
        "image_url": _coerce_text(product.image_url),
        "category": _coerce_text(product.category, "General"),
        "stock": product.stock if product.stock is not None else 0,
    }

app.mount("/static", StaticFiles(directory="static"), name="static")
# ══════════════════════════════════════════════════════════════════
#  PYDANTIC SCHEMAS
# ══════════════════════════════════════════════════════════════════

class OrderEmailRequest(BaseModel):
    user_email: EmailStr
    order_id: Optional[str] = None
    total: Optional[str] = None
    items: Optional[list] = None


class UserCreate(BaseModel):
    username: constr(min_length=3, max_length=20)
    email: EmailStr
    password: constr(min_length=6)
    confirm_password: constr(min_length=6)
    phone: constr(min_length=10, max_length=15)
    dob: str
    gender: str

    @field_validator("username")
    def validate_username(cls, v):
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError("Username can only contain letters, numbers and underscores")
        return v

    @field_validator("phone")
    def validate_phone(cls, v):
        if not re.match(r"^[0-9]{10,15}$", v):
            raise ValueError("Phone must be 10-15 digits")
        return v

    @field_validator("dob")
    def validate_dob(cls, v):
        try:
            dob = datetime.strptime(v, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("Invalid DOB format (use YYYY-MM-DD)")
        if dob >= datetime.today().date():
            raise ValueError("DOB must be in the past")
        return v

    @field_validator("gender")
    def validate_gender(cls, v):
        if v.lower() not in ["male", "female", "other"]:
            raise ValueError("Gender must be male, female or other")
        return v


class UpdateProfile(BaseModel):
    email: EmailStr
    username: Optional[str] = None
    phone: Optional[str] = None
    dob: Optional[str] = None
    gender: Optional[str] = None

    @field_validator("phone")
    def validate_phone(cls, v):
        if v and not re.match(r"^[0-9]{10,15}$", v):
            raise ValueError("Phone must be 10-15 digits")
        return v

    @field_validator("dob")
    def validate_dob(cls, v):
        if v:
            try:
                dob = datetime.strptime(v, "%Y-%m-%d").date()
                if dob >= datetime.today().date():
                    raise ValueError("DOB must be in the past")
            except ValueError:
                raise ValueError("Invalid DOB format")
        return v

    @field_validator("gender")
    def validate_gender(cls, v):
        if v and v.lower() not in ["male", "female", "other"]:
            raise ValueError("Gender must be male, female or other")
        return v


class CartAdd(BaseModel):
    user_email: EmailStr
    product_id: int
    quantity: int = 1


class CheckoutRequest(BaseModel):
    user_email: EmailStr


class AdminUpdateUser(BaseModel):
    username: Optional[str] = None
    phone: Optional[str] = None
    dob: Optional[str] = None
    gender: Optional[str] = None
    role: Optional[str] = None

    @field_validator("phone")
    def validate_phone(cls, v):
        if v and not re.match(r"^[0-9]{10,15}$", v):
            raise ValueError("Phone must be 10-15 digits")
        return v

    @field_validator("gender")
    def validate_gender(cls, v):
        if v and v.lower() not in ["male", "female", "other"]:
            raise ValueError("Gender must be male, female or other")
        return v

    @field_validator("role")
    def validate_role(cls, v):
        if v and v.lower() not in ["user", "admin"]:
            raise ValueError("Role must be 'user' or 'admin'")
        return v

class ProductCreate(BaseModel):
    name: str
    price: float
    category: str
    stock: int
    image_url: Optional[str] = None
    description: str

class PaymentCompleteRequest(BaseModel):
    user_email:     EmailStr
    order_id:       int
    payment_method: str
    amount:         float


# ── Helpers ──────────────────────────────────────────────────────

ADMIN_EMAILS = {
    "admin@shopfast.com",
    "superadmin@shopfast.com",
}


def validate_password(password: str):
    if not re.search(r"[A-Z]", password):
        return "Password must contain at least one uppercase letter"
    if not re.search(r"[a-z]", password):
        return "Password must contain at least one lowercase letter"
    if not re.search(r"[0-9]", password):
        return "Password must contain at least one number"
    if not re.search(r"[!@#$%^&*]", password):
        return "Password must contain at least one special character (!@#$%^&*)"
    return None


def _now_utc():
    return datetime.now(timezone.utc)


def _soft_delete(obj):
    obj.is_deleted = True
    obj.deleted_at = _now_utc()


def _restore(obj):
    obj.is_deleted = False
    obj.deleted_at = None


# ══════════════════════════════════════════════════════════════════
#  CACHE HEALTH CHECK
# ══════════════════════════════════════════════════════════════════

@app.get("/cache/health")
def cache_health():
    """Verify Redis is reachable (admin use)."""
    ok = cache.ping()
    return {
        "redis_connected": ok,
        "redis_url": os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    }


@app.delete("/cache/clear-products")
def clear_products_cache():
    """Force-clear the products cache so stale/empty results are evicted."""
    try:
        products_key = Keys.products_all()
        cache.delete(products_key)
        logger.info("[cache/clear-products] products_all cache cleared")
        return {"message": "Products cache cleared — next GET /products will reload from DB"}
    except Exception as e:
        logger.error(f"[cache/clear-products] Failed: {e}")
        raise HTTPException(500, f"Cache clear failed: {e}")


# ══════════════════════════════════════════════════════════════════
#  AUTH ROUTES
# ══════════════════════════════════════════════════════════════════

@app.post("/register")
async def register(user: UserCreate, db: Session = Depends(get_db)):
    if user.password != user.confirm_password:
        raise HTTPException(400, "Passwords do not match")
    pwd_error = validate_password(user.password)
    if pwd_error:
        raise HTTPException(400, pwd_error)
    existing = db.query(models.User).filter(
        (models.User.username == user.username) | (models.User.email == user.email),
        or_(models.User.is_deleted == False, models.User.is_deleted == None),  # noqa: E712, E711
    ).first()
    if existing:
        raise HTTPException(400, "Username or email already registered")
    assigned_role = "admin" if user.email.lower() in ADMIN_EMAILS else "user"
    new_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=auth.hash_password(user.password),
        phone=user.phone,
        dob=user.dob,
        gender=user.gender.lower(),
        role=assigned_role,
    )
    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(500, f"Database error: {str(e)}")
    try:
        invalidate_admin_stats()
    except Exception:
        pass  # Redis optional
    return {"message": "User registered successfully"}


@app.post("/login")
async def login(request: Request, data: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(
        models.User.email == data.email,
        or_(models.User.is_deleted == False, models.User.is_deleted == None),  # noqa: E712, E711
    ).first()
    if not user:
        raise HTTPException(400, "No account found")
    if not auth.verify_password(data.password, user.hashed_password):
        raise HTTPException(400, "Incorrect password")
    request.session["email"] = user.email
    request.session["role"]  = user.role
    if user.role == "admin":
        return RedirectResponse(url="/admin-dashboard", status_code=303)
    return RedirectResponse(url="/user-dashboard", status_code=303)


@app.get("/profile")
async def get_profile(email: str = Query(...), db: Session = Depends(get_db)):
    cache_key = Keys.user_profile(email)
    cached = cache.get(cache_key)
    if cached:
        return cached

    user = db.query(models.User).filter(
        models.User.email == email,
        or_(models.User.is_deleted == False, models.User.is_deleted == None),  # noqa: E712, E711
    ).first()
    if not user:
        raise HTTPException(404, "User not found")

    data = {
        "username": user.username,
        "email":    user.email,
        "phone":    user.phone,
        "dob":      user.dob,
        "gender":   user.gender,
    }
    cache.set(cache_key, data, TTL["user_profile"])
    return data


@app.put("/update-profile")
def update_profile(data: UpdateProfile, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(
        models.User.email == data.email,
        or_(models.User.is_deleted == False, models.User.is_deleted == None),  # noqa: E712, E711
    ).first()
    if not user:
        raise HTTPException(404, "User not found")
    updated = []
    if data.username is not None:
        clash = db.query(models.User).filter(
            models.User.username == data.username,
            models.User.email    != data.email,
        ).first()
        if clash:
            raise HTTPException(400, "Username already taken")
        user.username = data.username
        updated.append("username")
    if data.phone  is not None: user.phone  = data.phone;          updated.append("phone")
    if data.dob    is not None: user.dob    = data.dob;            updated.append("dob")
    if data.gender is not None: user.gender = data.gender.lower(); updated.append("gender")
    if not updated:
        raise HTTPException(400, "No fields provided to update")
    try:
        db.commit()
        db.refresh(user)
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(500, str(e))

    try:
        invalidate_user_profile(data.email)
    except Exception:
        pass  # Redis optional
    return {
        "message":        "Profile updated successfully",
        "updated_fields": updated,
        "user": {
            "username": user.username, "email": user.email,
            "phone":    user.phone,    "dob":   user.dob, "gender": user.gender,
        },
    }


@app.post("/forgot-password")
async def forgot_password(data: schemas.ForgotPassword, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(
        models.User.email == data.email,
        or_(models.User.is_deleted == False, models.User.is_deleted == None),  # noqa: E712, E711
    ).first()
    if not user:
        raise HTTPException(404, "Email not registered")
    otp = generate_otp(data.email)
    try:
        send_email(data.email, "Your OTP Code", f"Your OTP is: {otp}")
        print(f"[DEV] OTP for {data.email}: {otp}")
    except Exception as e:
        # Allow the reset flow to continue locally even if SMTP isn't configured.
        print(f"[DEV] OTP for {data.email}: {otp}")
        print(f"[forgot-password] Email send skipped/failing: {e}")
        return {"message": "OTP generated. Check server logs for the OTP in local development."}
    return {"message": "OTP sent to your email"}


@app.post("/verify-otp")
async def verify_otp_api(data: schemas.VerifyOTP):
    if not verify_otp(data.email, data.otp):
        raise HTTPException(400, "Invalid or expired OTP")
    return {"message": "OTP verified successfully"}


@app.post("/reset-password")
async def reset_password(data: schemas.ResetPassword, db: Session = Depends(get_db)):
    if data.new_password != data.confirm_password:
        raise HTTPException(400, "Passwords do not match")
    pwd_error = validate_password(data.new_password)
    if pwd_error:
        raise HTTPException(400, pwd_error)
    if not is_verified(data.email):
        raise HTTPException(400, "OTP verification required before resetting password")
    user = db.query(models.User).filter(
        models.User.email == data.email,
        or_(models.User.is_deleted == False, models.User.is_deleted == None),  # noqa: E712, E711
    ).first()
    if not user:
        raise HTTPException(404, "User not found")
    user.hashed_password = auth.hash_password(data.new_password)
    db.commit()
    return {"message": "Password reset successfully"}


# ══════════════════════════════════════════════════════════════════
#  PRODUCT ROUTES
# ══════════════════════════════════════════════════════════════════

@app.get("/products/search")
def search_products(
    q: str = "",
    category: str = "",
    min_price: float = 0,
    max_price: float = 100000,
    rating: float = 0,
    sort: str = "",
    db: Session = Depends(get_db),
):
    cache_key = Keys.product_search(q, category, min_price, max_price, sort)

    def _load():
        query = db.query(models.Product).filter(or_(models.Product.is_deleted == False, models.Product.is_deleted == None))  # noqa: E712, E711
        if q:
            query = query.filter(
                or_(
                    models.Product.name.ilike(f"%{q}%"),
                    models.Product.description.ilike(f"%{q}%"),
                )
            )
        if category:
            query = query.filter(models.Product.category == category)
        query = query.filter(
            models.Product.price >= min_price,
            models.Product.price <= max_price,
        )
        if sort == "price-asc":
            query = query.order_by(asc(models.Product.price))
        elif sort == "price-desc":
            query = query.order_by(desc(models.Product.price))
        elif sort == "newest":
            query = query.order_by(desc(models.Product.id))

        return [_serialize_product(p) for p in query.all()]

    data = cache.get_or_set(cache_key, _load, TTL["product_search"])
    return [_serialize_product(item) for item in data]


@app.get("/products", response_model=list[schemas.ProductResponse])
def get_products(db: Session = Depends(get_db)):
    cache_key = Keys.products_all()

    # Only use cache if it has a non-empty list (stale empty cache causes demo-mode fallback)
    cached = cache.get(cache_key)
    if cached and isinstance(cached, list) and len(cached) > 0:
        normalized = [_serialize_product(item) for item in cached]
        if normalized != cached:
            cache.set(cache_key, normalized, TTL["products_all"])
        return normalized

    products = (
        db.query(models.Product)
        .filter(or_(models.Product.is_deleted == False, models.Product.is_deleted == None))  # noqa: E712, E711
        .order_by(models.Product.id.desc())
        .all()
    )
    result = [_serialize_product(p) for p in products]

    # Never cache an empty list — that would poison the cache
    if result:
        cache.set(cache_key, result, TTL["products_all"])
    else:
        logger.warning("[GET /products] DB returned 0 products — skipping cache write")

    return result


@app.get("/products/{product_id}", response_model=schemas.ProductResponse)
def get_product(product_id: int, db: Session = Depends(get_db)):
    cache_key = Keys.product(product_id)
    cached = cache.get(cache_key)
    if cached:
        normalized = _serialize_product(cached)
        if normalized != cached:
            cache.set(cache_key, normalized, TTL["product_single"])
        return normalized

    product = db.query(models.Product).filter(
        models.Product.id == product_id,
        or_(models.Product.is_deleted == False, models.Product.is_deleted == None),  # noqa: E712, E711
    ).first()
    if not product:
        raise HTTPException(404, "Product not found")

    data = _serialize_product(product)
    cache.set(cache_key, data, TTL["product_single"])
    return data


@app.post("/products", response_model=schemas.ProductResponse)
def create_product(
    name:        str   = Form(...),
    price:       float = Form(...),
    description: str   = Form(""),
    image_url:   str   = Form(""),
    category:    str   = Form("General"),
    stock:       int   = Form(0),
    db: Session = Depends(get_db),
):
    if price < 0:
        raise HTTPException(400, "Price cannot be negative")
    if stock < 0:
        raise HTTPException(400, "Stock cannot be negative")
    product = models.Product(
        name=name, price=price, description=description,
        image=image_url, category=category, stock=stock,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    try:
        invalidate_product(product.id)
    except Exception:
        pass  # Redis optional
    try:
        invalidate_admin_stats()
    except Exception:
        pass  # Redis optional
    return product


@app.put("/products/{product_id}", response_model=schemas.ProductResponse)
def update_product(
    product_id:  int,
    name:        str   = Form(None),
    price:       float = Form(None),
    description: str   = Form(None),
    image_url:   str   = Form(None),
    category:    str   = Form(None),
    stock:       int   = Form(None),
    db: Session = Depends(get_db),
):
    product = db.query(models.Product).filter(
        models.Product.id == product_id,
        or_(models.Product.is_deleted == False, models.Product.is_deleted == None),  # noqa: E712, E711
    ).first()
    if not product:
        raise HTTPException(404, "Product not found")
    if name        is not None: product.name        = name
    if price       is not None: product.price       = price
    if description is not None: product.description = description
    if image_url   is not None: product.image       = image_url
    if category    is not None: product.category    = category
    if stock       is not None: product.stock       = stock
    db.commit()
    db.refresh(product)
    try:
        invalidate_product(product_id)
    except Exception:
        pass  # Redis optional
    return product


@app.delete("/products/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(
        models.Product.id == product_id,
        or_(models.Product.is_deleted == False, models.Product.is_deleted == None),  # noqa: E712, E711
    ).first()
    if not product:
        raise HTTPException(404, "Product not found or already deleted")
    _soft_delete(product)
    db.commit()
    try:
        invalidate_product(product_id)
    except Exception:
        pass  # Redis optional
    try:
        invalidate_admin_stats()
    except Exception:
        pass  # Redis optional
    return {"message": "Product soft-deleted successfully", "product_id": product_id}


@app.post("/admin/products/{product_id}/restore")
def restore_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(
        models.Product.id == product_id,
        models.Product.is_deleted == True,  # noqa: E712
    ).first()
    if not product:
        raise HTTPException(404, "Product not found or is not deleted")
    _restore(product)
    db.commit()
    db.refresh(product)
    try:
        invalidate_product(product_id)
    except Exception:
        pass  # Redis optional
    return {"message": "Product restored successfully", "product_id": product_id}


@app.get("/admin/products/deleted")
def list_deleted_products(db: Session = Depends(get_db)):
    products = db.query(models.Product).filter(
        models.Product.is_deleted == True  # noqa: E712
    ).order_by(models.Product.deleted_at.desc()).all()
    return [
        {
            "id":         p.id,
            "name":       p.name,
            "category":   p.category,
            "price":      p.price,
            "deleted_at": str(p.deleted_at),
        }
        for p in products
    ]


# ══════════════════════════════════════════════════════════════════
#  CART ROUTES
# ══════════════════════════════════════════════════════════════════

@app.post("/cart/add")
def add_to_cart(data: CartAdd, db: Session = Depends(get_db)):
    # Treat NULL is_deleted as not-deleted for backwards compatibility
    user = db.query(models.User).filter(
        models.User.email == data.user_email,
        or_(models.User.is_deleted == False, models.User.is_deleted == None),  # noqa: E712, E711
    ).first()
    if not user:
        logger.warning(f"[cart/add] User not found: {data.user_email}")
        raise HTTPException(404, "User not found")
    product = db.query(models.Product).filter(
        models.Product.id == data.product_id,
        or_(models.Product.is_deleted == False, models.Product.is_deleted == None),  # noqa: E712, E711
    ).first()
    if not product:
        logger.warning(f"[cart/add] Product not found: id={data.product_id}")
        raise HTTPException(404, f"Product not found (id={data.product_id})")
    if product.stock < data.quantity:
        raise HTTPException(400, f"Only {product.stock} item(s) left in stock")
    existing = db.query(models.CartItem).filter_by(
        user_email=data.user_email, product_id=data.product_id
    ).first()
    if existing:
        new_total = existing.quantity + data.quantity
        if product.stock < new_total:
            raise HTTPException(400, f"Only {product.stock - existing.quantity} more available")
        existing.quantity = new_total
    else:
        db.add(models.CartItem(
            user_email=data.user_email,
            product_id=data.product_id,
            quantity=data.quantity,
        ))
    db.commit()
    try:
        invalidate_cart(data.user_email)
    except Exception:
        pass  # Redis optional
    return {"message": "Added to cart"}


@app.get("/cart")
def view_cart(email: str = Query(...), db: Session = Depends(get_db)):
    cache_key = Keys.cart(email)
    cached = cache.get(cache_key)
    if cached:
        return cached

    items = db.query(models.CartItem).filter_by(user_email=email).all()
    result, total = [], 0.0
    for item in items:
        p        = item.product
        subtotal = p.price * item.quantity
        total   += subtotal
        result.append({
            "cart_item_id": item.id,
            "product_id":   p.id,
            "name":         p.name,
            "price":        p.price,
            "quantity":     item.quantity,
            "subtotal":     round(subtotal, 2),
            "image_url":    p.image_url,
            "stock":        p.stock,
        })

    data = {"items": result, "total": round(total, 2)}
    cache.set(cache_key, data, TTL["cart"])
    return data


@app.put("/cart/update/{cart_item_id}")
def update_cart(cart_item_id: int, quantity: int = Query(...), db: Session = Depends(get_db)):
    item = db.query(models.CartItem).filter(models.CartItem.id == cart_item_id).first()
    if not item:
        raise HTTPException(404, "Cart item not found")
    email = item.user_email
    if quantity <= 0:
        db.delete(item)
    else:
        if item.product.stock < quantity:
            raise HTTPException(400, f"Only {item.product.stock} item(s) in stock")
        item.quantity = quantity
    db.commit()
    try:
        invalidate_cart(email)
    except Exception:
        pass  # Redis optional
    return {"message": "Cart updated"}


@app.delete("/cart/remove/{cart_item_id}")
def remove_from_cart(cart_item_id: int, db: Session = Depends(get_db)):
    item = db.query(models.CartItem).filter(models.CartItem.id == cart_item_id).first()
    if not item:
        raise HTTPException(404, "Cart item not found")
    email = item.user_email
    db.delete(item)
    db.commit()
    try:
        invalidate_cart(email)
    except Exception:
        pass  # Redis optional
    return {"message": "Item removed from cart"}


@app.delete("/cart/clear")
def clear_cart(email: str = Query(...), db: Session = Depends(get_db)):
    db.query(models.CartItem).filter_by(user_email=email).delete()
    db.commit()
    try:
        invalidate_cart(email)
    except Exception:
        pass  # Redis optional
    return {"message": "Cart cleared"}


# ══════════════════════════════════════════════════════════════════
#  ORDER HELPERS
# ══════════════════════════════════════════════════════════════════

def _build_order_from_cart(email: str, db: Session):
    user = db.query(User).filter(
        User.email == email,
        User.is_deleted == False,  # noqa: E712
    ).first()
    if not user:
        raise HTTPException(404, "User not found")

    cart_items = db.query(CartItem).filter(CartItem.user_email == email).all()
    if not cart_items:
        raise HTTPException(400, "Cart is empty")

    active_cart_items = [
        item for item in cart_items
        if not getattr(item.product, "is_deleted", False)
    ]
    if not active_cart_items:
        raise HTTPException(
            400,
            "All items in your cart are no longer available. Please add new items to continue.",
        )

    total = sum(item.quantity * item.product.price for item in active_cart_items)

    order = Order(
        user_email=email,
        user_name=user.username,
        total=total,
        user_id=user.id,
        status="Pending",
    )
    db.add(order)
    db.flush()

    items_for_email = []
    for item in active_cart_items:
        items_for_email.append({
            "name":     item.product.name,
            "quantity": item.quantity,
            "price":    item.product.price,
        })
        db.add(OrderItem(
            order_id=order.id,
            product_id=item.product_id,
            product_name=item.product.name,
            price=item.product.price,
            quantity=item.quantity,
        ))
        item.product.stock -= item.quantity

    db.query(CartItem).filter(CartItem.user_email == email).delete()
    return order, items_for_email

# ══════════════════════════════════════════════════════════════════
#  ORDER ROUTES
# ══════════════════════════════════════════════════════════════════

@app.post("/checkout")
def checkout(data: CheckoutRequest, db: Session = Depends(get_db)):
    with db_transaction(db):
        order, items_for_email = _build_order_from_cart(data.user_email, db)

    try:
        invalidate_cart(data.user_email)
    except Exception:
        pass  # Redis optional
    try:
        invalidate_user_orders(data.user_email)
    except Exception:
        pass  # Redis optional
    try:
        invalidate_admin_stats()
    except Exception:
        pass  # Redis optional

    try:
        send_order_confirmation(data.user_email, order.id, order.total, items_for_email)
    except Exception as e:
        print("Email failed:", e)

    return {"message": "Order placed successfully", "order_id": order.id}


@app.get("/orders")
def get_orders(email: str = Query(...), db: Session = Depends(get_db)):
    cache_key = Keys.orders_user(email)
    cached = cache.get(cache_key)
    if cached:
        return cached

    orders = (
        db.query(Order)
        .filter(Order.user_email == email)
        .order_by(Order.created_at.desc())
        .all()
    )
    data = [
        {
            "order_id":   o.id,
            "total":      o.total,
            "status":     o.status,
            "created_at": str(o.created_at),
            "items": [
                {
                    "product_name": oi.product_name,
                    "quantity":     oi.quantity,
                    "price":        oi.price,
                    "subtotal":     round(oi.price * oi.quantity, 2),
                }
                for oi in o.items
            ],
        }
        for o in orders
    ]
    cache.set(cache_key, data, TTL["orders_user"])
    return data


@app.get("/orders/{order_id}")
def get_order_detail(order_id: int, email: str = Query(...), db: Session = Depends(get_db)):
    cache_key = Keys.order_single(order_id)
    cached = cache.get(cache_key)
    # Only serve from cache if ownership matches (security check)
    if cached and cached.get("_owner") == email:
        return {k: v for k, v in cached.items() if k != "_owner"}

    order = db.query(Order).filter(Order.id == order_id, Order.user_email == email).first()
    if not order:
        raise HTTPException(404, "Order not found")

    data = {
        "_owner":      order.user_email,          # internal, stripped before return
        "order_id":    order.id,
        "total":       order.total,
        "status":      order.status,
        "created_at":  str(order.created_at),
        "items": [
            {
                "product_name": oi.product_name,
                "image_url":    oi.product.image_url if oi.product else "",
                "quantity":     oi.quantity,
                "price":        oi.price,
                "subtotal":     round(oi.price * oi.quantity, 2),
            }
            for oi in order.items
        ],
    }
    cache.set(cache_key, data, TTL["order_single"])
    return {k: v for k, v in data.items() if k != "_owner"}


@app.post("/send-order-email")
def send_order_email(data: OrderEmailRequest, db: Session = Depends(get_db)):
    try:
        latest = (
            db.query(Order)
            .filter(Order.user_email == data.user_email)
            .order_by(Order.created_at.desc())
            .first()
        )
        if latest:
            items_for_email = [
                {"name": oi.product_name, "quantity": oi.quantity, "price": oi.price}
                for oi in latest.items
            ]
            send_order_confirmation(data.user_email, latest.id, latest.total, items_for_email)
        else:
            send_email(data.user_email, "Order Placed", "Your order has been successfully placed.")
        return {"message": "Email sent"}
    except Exception as e:
        raise HTTPException(500, str(e))


# ══════════════════════════════════════════════════════════════════
#  ADMIN ORDER ROUTES
# ══════════════════════════════════════════════════════════════════

@app.get("/admin/orders")
def admin_get_orders(db: Session = Depends(get_db)):
    return [
        {
            "id":        o.id,
            "user_name": o.user_name,
            "email":     o.user_email,
            "total":     o.total,
            "status":    o.status,
            "items": [
                {"product": i.product_name, "price": i.price, "qty": i.quantity}
                for i in o.items
            ],
        }
        for o in db.query(Order).all()
    ]


@app.put("/admin/order/{order_id}")
def update_order_status_admin(order_id: int, status: str, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(404, "Order not found")
    order.status = status
    db.commit()
    try:
        invalidate_user_orders(order.user_email, order_id=order_id)
    except Exception:
        pass  # Redis optional
    return {"message": "Status updated"}


# ══════════════════════════════════════════════════════════════════
#  ADMIN STATS  (new cached endpoint)
# ══════════════════════════════════════════════════════════════════

@app.get("/admin/stats")
def admin_stats(db: Session = Depends(get_db)):
    """Cached admin dashboard counters — refreshes every 60 seconds."""
    cache_key = Keys.admin_stats()
    cached = cache.get(cache_key)
    if cached:
        return cached

    total_users    = db.query(models.User).filter(models.User.is_deleted == False).count()  # noqa
    total_products = db.query(models.Product).filter(models.Product.is_deleted == False).count()  # noqa
    total_orders   = db.query(Order).count()
    pending_orders = db.query(Order).filter(Order.status == "Pending").count()
    paid_orders    = db.query(Order).filter(Order.status == "Paid").count()
    paid_list      = db.query(Order).filter(Order.status == "Paid").all()
    revenue        = round(sum(o.total for o in paid_list), 2)

    data = {
        "total_users":    total_users,
        "total_products": total_products,
        "total_orders":   total_orders,
        "pending_orders": pending_orders,
        "paid_orders":    paid_orders,
        "total_revenue":  revenue,
    }
    cache.set(cache_key, data, TTL["admin_stats"])
    return data


# ══════════════════════════════════════════════════════════════════
#  ADMIN USER MANAGEMENT ROUTES
# ══════════════════════════════════════════════════════════════

@app.post("/admin/add-product")
def add_product(product: ProductCreate, db: Session = Depends(get_db)):
    new_product = Product(
        name=product.name,
        price=product.price,
        category=product.category,
        stock=product.stock,
        image=product.image_url,
        description=product.description
    )

    db.add(new_product)
    db.commit()
    db.refresh(new_product)

    return {"message": "Product added"}


@app.get("/admin/users")
def get_all_users(db: Session = Depends(get_db)):
    users = db.query(models.User).filter(
        models.User.is_deleted == False  # noqa: E712
    ).order_by(models.User.id.asc()).all()
    return [
        {
            "id": u.id, "username": u.username, "email": u.email,
            "phone": u.phone, "dob": u.dob, "gender": u.gender, "role": u.role,
        }
        for u in users
    ]


@app.put("/admin/users/{user_id}")
def admin_update_user(user_id: int, data: AdminUpdateUser, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(
        models.User.id == user_id,
        or_(models.User.is_deleted == False, models.User.is_deleted == None),  # noqa: E712, E711
    ).first()
    if not user:
        raise HTTPException(404, "User not found")
    updated = []
    if data.username is not None:
        clash = db.query(models.User).filter(
            models.User.username == data.username, models.User.id != user_id
        ).first()
        if clash:
            raise HTTPException(400, "Username already taken")
        user.username = data.username; updated.append("username")
    if data.phone  is not None: user.phone  = data.phone;          updated.append("phone")
    if data.dob    is not None: user.dob    = data.dob;            updated.append("dob")
    if data.gender is not None: user.gender = data.gender.lower(); updated.append("gender")
    if data.role   is not None: user.role   = data.role.lower();   updated.append("role")
    if not updated:
        raise HTTPException(400, "No fields provided to update")
    try:
        db.commit(); db.refresh(user)
    except SQLAlchemyError as e:
        db.rollback(); raise HTTPException(500, str(e))

    try:
        invalidate_user_profile(user.email)
    except Exception:
        pass  # Redis optional

    return {
        "message": "User updated successfully",
        "updated_fields": updated,
        "user": {
            "id": user.id, "username": user.username, "email": user.email,
            "phone": user.phone, "dob": user.dob, "gender": user.gender, "role": user.role,
        },
    }


@app.delete("/admin/users/{user_id}")
def admin_delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(
        models.User.id == user_id,
        or_(models.User.is_deleted == False, models.User.is_deleted == None),  # noqa: E712, E711
    ).first()
    if not user:
        raise HTTPException(404, "User not found or already deleted")
    email = user.email
    _soft_delete(user)
    db.commit()
    try:
        invalidate_user_profile(email)
    except Exception:
        pass  # Redis optional
    try:
        invalidate_cart(email)
    except Exception:
        pass  # Redis optional
    try:
        invalidate_admin_stats()
    except Exception:
        pass  # Redis optional
    return {"message": f"User {email} soft-deleted successfully"}


@app.post("/admin/users/{user_id}/restore")
def admin_restore_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(
        models.User.id == user_id,
        models.User.is_deleted == True,  # noqa: E712
    ).first()
    if not user:
        raise HTTPException(404, "User not found or is not deleted")
    _restore(user)
    db.commit()
    db.refresh(user)
    try:
        invalidate_admin_stats()
    except Exception:
        pass  # Redis optional
    return {
        "message": "User restored successfully",
        "user": {
            "id": user.id, "username": user.username,
            "email": user.email, "role": user.role,
        },
    }


@app.get("/admin/users/deleted")
def admin_list_deleted_users(db: Session = Depends(get_db)):
    users = db.query(models.User).filter(
        models.User.is_deleted == True  # noqa: E712
    ).order_by(models.User.deleted_at.desc()).all()
    return [
        {
            "id":         u.id,
            "username":   u.username,
            "email":      u.email,
            "role":       u.role,
            "deleted_at": str(u.deleted_at),
        }
        for u in users
    ]


@app.get("/admin/check")
def check_admin_role(email: str = Query(...), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(
        models.User.email == email,
        or_(models.User.is_deleted == False, models.User.is_deleted == None),  # noqa: E712, E711
    ).first()
    if not user:
        raise HTTPException(404, "User not found")
    return {"is_admin": user.role == "admin", "role": user.role, "username": user.username}


# ══════════════════════════════════════════════════════════════════
#  STRIPE ROUTES
# ══════════════════════════════════════════════════════════════════

INR_TO_USD_RATE = 0.012


def inr_to_usd(inr_amount: float) -> float:
    return max(round(inr_amount * INR_TO_USD_RATE, 2), 0.01)


@app.post("/stripe/create-checkout-session")
def create_checkout_session(data: CheckoutRequest, db: Session = Depends(get_db)):
    if not data.user_email:
        raise HTTPException(status_code=400, detail="Email is required")

    try:
        app_host = os.getenv("BASE_URL") or os.getenv("APP_HOST") or "http://127.0.0.1:8000"
        with db_transaction(db):
            order, _ = _build_order_from_cart(data.user_email, db)
            order_id = order.id
            order_total = round(order.total, 2)

            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                mode="payment",
                line_items=[{
                    "price_data": {
                        "currency": "inr",
                        "product_data": {
                            "name": f"ShopFast Order #{order_id}",
                        },
                        "unit_amount": int(round(order_total * 100)),
                    },
                    "quantity": 1,
                }],
                customer_email=data.user_email,
                metadata={
                    "order_id": str(order_id),
                    "user_email": data.user_email,
                },
                success_url=f"{app_host}/stripe/success?session_id={{CHECKOUT_SESSION_ID}}&order_id={order_id}",
                cancel_url=f"{app_host}/stripe/cancel-page?order_id={order_id}",
            )
            order.stripe_session_id = session.id

        try:
            invalidate_cart(data.user_email)
        except Exception:
            pass  # Redis optional
        try:
            invalidate_user_orders(data.user_email, order_id=order_id)
        except Exception:
            pass  # Redis optional
        try:
            invalidate_admin_stats()
        except Exception:
            pass  # Redis optional

        return {"checkout_url": session.url, "order_id": order_id, "total": order_total}

    except Exception as e:
        print("Stripe error:", str(e))
        raise HTTPException(status_code=400, detail=str(e))
    
    
'''@app.get("/stripe/success")
def stripe_success(
    request: Request,
    session_id: str,
    order_id: int = None,
    db: Session = Depends(get_db),
):
    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except stripe.error.StripeError:
        return RedirectResponse(url="/stripe/cancel-page?reason=stripe_error", status_code=303)

    # ✅ Get email safely
    user_email = (
        request.session.get("stripe_email")
        or session.customer_email
        or session.metadata.get("user_email")
    )

    # ✅ Get order_id safely
    order_id = order_id or session.metadata.get("order_id")

    if not order_id:
        return RedirectResponse(url="/stripe/cancel-page?reason=missing_order_id", status_code=303)

    # ✅ Fetch order
    order = db.query(Order).filter(Order.id == int(order_id)).first()

    if not order:
        print(f"[Stripe] ❌ Order not found: {order_id}")
        return RedirectResponse(url="/stripe/cancel-page?reason=order_not_found", status_code=303)

    if order.status == "Paid":
        return RedirectResponse(url="/stripe/success-page", status_code=303)

    # ✅ Verify payment
    if session.payment_status != "paid":
        order.status = "Failed"
        db.commit()
        return RedirectResponse(url="/stripe/cancel-page?reason=not_paid", status_code=303)

    payment_intent_id = session.payment_intent

    existing = db.query(Payment).filter(Payment.payment_id == payment_intent_id).first()
    if existing:
        return RedirectResponse(url="/stripe/success-page", status_code=303)

    payment = Payment(
        order_id=order.id,
        payment_id=payment_intent_id or session_id,
        status="Completed",
        method="Stripe",
    )

    db.add(payment)
    order.status = "Paid"

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        print("DB Error:", e)
        return RedirectResponse(url="/stripe/cancel-page?reason=db_error", status_code=303)

    request.session.pop("stripe_email", None)
    request.session.pop("stripe_order_id", None)

    return RedirectResponse(url="/stripe/success-page", status_code=303)

'''

@app.get("/stripe/success")
def stripe_success(
    request: Request,
    session_id: str,
    order_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except stripe.error.StripeError:
        return RedirectResponse(url="/stripe/cancel-page?reason=stripe_error", status_code=303)

    # ✅ Get email safely
    user_email = (
        request.session.get("stripe_email")
        or session.customer_email
        or session.metadata.get("user_email")
    )

    # ✅ Get order_id from metadata if missing
    order_id = order_id or session.metadata.get("order_id")

    if not order_id:
        return RedirectResponse(url="/stripe/cancel-page?reason=missing_order_id", status_code=303)

    order = db.query(Order).filter(Order.id == int(order_id)).first()

    if not order:
        return RedirectResponse(url="/stripe/cancel-page?reason=order_not_found", status_code=303)

    if order.status == "Paid":
        return RedirectResponse(url="/stripe/success-page", status_code=303)

    if session.payment_status != "paid":
        order.status = "Failed"
        db.commit()
        return RedirectResponse(url="/stripe/cancel-page?reason=not_paid", status_code=303)

    payment_intent_id = session.payment_intent

    existing = db.query(Payment).filter(Payment.payment_id == payment_intent_id).first()

    if not existing:
        payment = Payment(
            order_id=order.id,
            payment_id=payment_intent_id or session_id,
            status="Completed",
            method="Stripe",
        )
        db.add(payment)

    order.status = "Paid"

    try:
        db.commit()
    except Exception:
        db.rollback()
        return RedirectResponse(url="/stripe/cancel-page?reason=db_error", status_code=303)

    return RedirectResponse(url="/stripe/success-page", status_code=303)


@app.get("/stripe/cancel")
def stripe_cancel(request: Request):
    request.session.pop("stripe_email",    None)
    request.session.pop("stripe_order_id", None)
    return RedirectResponse(url="/stripe/cancel-page", status_code=303)


@app.get("/stripe/payment-status/{payment_id}")
def stripe_payment_status(payment_id: str, db: Session = Depends(get_db)):
    payment = db.query(Payment).filter(Payment.payment_id == payment_id).first()
    if not payment:
        return {"found": False, "status": "Pending"}
    order = db.query(Order).filter(Order.id == payment.order_id).first()
    return {
        "found":        True,
        "status":       payment.status,
        "order_id":     payment.order_id,
        "method":       payment.method,
        "order_status": order.status if order else "Unknown",
    }


# ══════════════════════════════════════════════════════════════════
#  STRIPE WEBHOOK
# ══════════════════════════════════════════════════════════════════

@app.post("/stripe/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload    = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError:
        print("[Stripe Webhook] ❌ Invalid signature")
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")
    except Exception as e:
        print(f"[Stripe Webhook] ❌ Error: {e}")
        raise HTTPException(status_code=400, detail="Webhook error")

    event_type = event["type"]
    print(f"[Stripe Webhook] Event: {event_type}")

    if event_type == "checkout.session.completed":
        session     = event["data"]["object"]
        order_id    = session.get("metadata", {}).get("order_id")
        user_email  = session.get("metadata", {}).get("user_email") or session.get("customer_email")
        pi_id       = session.get("payment_intent")
        pay_status  = session.get("payment_status")

        if pay_status != "paid":
            print(f"[Stripe Webhook] ℹ️  Session not paid yet: {pay_status}")
            return {"status": "not_paid"}

        if not order_id:
            print("[Stripe Webhook] Missing order_id in metadata")
            return {"status": "missing_order_id"}

        existing = db.query(Payment).filter(Payment.payment_id == pi_id).first()
        if existing:
            print(f"[Stripe Webhook] Already processed PI {pi_id}")
            return {"status": "already_processed"}

        order = db.query(Order).filter(Order.id == int(order_id)).first()
        if not order:
            print(f"[Stripe Webhook] ⚠️  Order #{order_id} not found")
            return {"status": "order_not_found"}

        order.status = "Paid"
        payment = Payment(
            order_id   = order.id,
            payment_id = pi_id or session["id"],
            status     = "Completed",
            method     = "Stripe",
        )
        db.add(payment)
        db.commit()

        try:
            invalidate_user_orders(order.user_email, order_id=order.id)
        except Exception:
            pass  # Redis optional
        try:
            invalidate_admin_stats()
        except Exception:
            pass  # Redis optional

        print(f"[Stripe Webhook] ✅ Payment saved | Order #{order.id} | PI={pi_id}")

        try:
            items_for_email = [
                {"name": oi.product_name, "quantity": oi.quantity, "price": oi.price}
                for oi in order.items
            ]
            send_order_confirmation(order.user_email, order.id, order.total, items_for_email)
            print(f"[Stripe Webhook] 📧 Email sent to {order.user_email}")
        except Exception as e:
            print(f"[Stripe Webhook] ⚠️  Email failed: {e}")

    return {"status": "ok"}


# ══════════════════════════════════════════════════════════════════
#  PAYMENT COMPLETE  (Card / UPI / Net Banking)
# ══════════════════════════════════════════════════════════════════

@app.post("/payment/complete")
def payment_complete(data: PaymentCompleteRequest, db: Session = Depends(get_db)):
    order = db.query(Order).filter(
        Order.id == data.order_id,
        Order.user_email == data.user_email,
    ).first()

    if not order:
        raise HTTPException(404, "Order not found")
    if order.status == "Paid":
        raise HTTPException(400, "Order is already paid")

    txn_id = f"TXN-{uuid.uuid4().hex[:12].upper()}"

    payment_record = Payment(
        order_id   = order.id,
        payment_id = txn_id,
        status     = "Completed",
        method     = data.payment_method,
    )
    db.add(payment_record)
    order.status = "Paid"

    try:
        db.commit()
        db.refresh(order)
        print(f"[DB] ✅ Custom payment saved | Order #{order.id} | TXN: {txn_id}")
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(500, f"Database error: {str(e)}")

    try:
        invalidate_user_orders(data.user_email, order_id=data.order_id)
    except Exception:
        pass  # Redis optional
    try:
        invalidate_admin_stats()
    except Exception:
        pass  # Redis optional

    try:
        items_for_email = [
            {"name": oi.product_name, "quantity": oi.quantity, "price": oi.price}
            for oi in order.items
        ]
        send_order_confirmation(data.user_email, order.id, order.total, items_for_email)
    except Exception as e:
        print(f"[payment/complete] ⚠️  Email failed: {e}")

    return {
        "message":        "Payment successful",
        "order_id":       order.id,
        "transaction_id": txn_id,
        "status":         order.status,
        "method":         data.payment_method,
        "amount":         data.amount,
    }


# ══════════════════════════════════════════════════════════════════
#  HTML PAGE ROUTES
# ══════════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return RedirectResponse(url="/login")

@app.get("/register",        response_class=HTMLResponse)
def register_page(request: Request):
    return render("register.html", {"request": request})

@app.get("/login")
def login_page(request: Request):
    template_name = "login.html"
    return render("login.html", {"request": request})

@app.get("/forgot-password", response_class=HTMLResponse)
def forgot_page(request: Request):
    return render("forgot_password.html", {"request": request})

@app.get("/verify-otp",      response_class=HTMLResponse)
def verify_otp_page(request: Request):
    return render("verify_otp.html", {"request": request})

@app.get("/reset-password",  response_class=HTMLResponse)
def reset_password_page(request: Request):
    return render("reset_password.html", {"request": request})

@app.get("/dashboard",       response_class=HTMLResponse)
def dashboard_page(request: Request):
    return render("dashboard.html", {"request": request})

@app.get("/admin",           response_class=HTMLResponse)
def admin_page(request: Request):
    return render("admin.html", {"request": request})

@app.get("/admin-dashboard", response_class=HTMLResponse)
def admin_dashboard(request: Request):
    if request.session.get("role") != "admin":
        return RedirectResponse(url="/login")
    return render("admin_dashboard.html", {"request": request})

@app.get("/user-dashboard",  response_class=HTMLResponse)
def user_dashboard(request: Request):
    if request.session.get("role") != "user":
        return RedirectResponse(url="/login")
    return render("user_dashboard.html", {"request": request})

@app.get("/shop",            response_class=HTMLResponse)
def shop_page(request: Request):
    return render("shop.html", {"request": request})

@app.get("/cart-page",       response_class=HTMLResponse)
def cart_page(request: Request):
    return render("cart.html", {"request": request})




@app.get("/success")
def payment_success(request: Request):
    return render("success.html", {"request": request})

@app.get("/payment_success", response_class=HTMLResponse)
def payment_success_page(request: Request):
    # This must match your file name: payment_success.html
    return render("payment_success.html", {"request": request})

@app.get("/stripe/success-page", response_class=HTMLResponse)
def stripe_success_page(
    request: Request,
    order_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    total = None
    if order_id is not None:
        order = db.query(Order).filter(Order.id == order_id).first()
        if order:
            total = order.total

    return render("stripe_success.html", {"request": request, "order_id": order_id, "total": total})

@app.get("/stripe/cancel-page", response_class=HTMLResponse)
def stripe_cancel_page(request: Request, reason: Optional[str] = None):
    return render("stripe_cancel.html", {"request": request, "reason": reason})