from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey,Text,Boolean
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime



class User(Base):
    __tablename__ = "users"

    id               = Column(Integer, primary_key=True, index=True)
    username         = Column(String)
    email            = Column(String, unique=True, index=True)
    hashed_password  = Column(String)
    phone            = Column(String, default="")
    dob              = Column(String, default="")
    gender           = Column(String, default="")
    role = Column(String, default="user") 
    cart_items = relationship("CartItem", back_populates="user")
    orders = relationship("Order",back_populates="user",foreign_keys="Order.user_id")
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

class Product(Base):
    __tablename__ = "products"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String,  nullable=False)
    description = Column(String,  default="")
    price       = Column(Float,   nullable=False)
    image_url   = Column(String,  default="")
    category    = Column(String,  default="General")
    stock       = Column(Integer, default=0)

    cart_items  = relationship("CartItem",  back_populates="product")
    order_items = relationship("OrderItem", back_populates="product")
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

class CartItem(Base):
    __tablename__ = "cart_items"

    id         = Column(Integer, primary_key=True, index=True)
    user_email = Column(String,  ForeignKey("users.email", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    quantity   = Column(Integer, default=1)

    user    = relationship("User",    back_populates="cart_items", foreign_keys=[user_email])
    product = relationship("Product", back_populates="cart_items")


class Order(Base):
    __tablename__ = "orders"

    id         = Column(Integer, primary_key=True, index=True)

    # Main FK (use this for relationships)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Optional (for display only, NOT used for relationship logic)
    user_email = Column(String, nullable=False)

    user_name  = Column(String, default="")
    total      = Column(Float, nullable=False)
    status     = Column(String, default="Pending")
    transaction_id = Column(String, unique=True, nullable=True)
    stripe_session_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)




    # Relationships
    user  = relationship("User", back_populates="orders", foreign_keys=[user_id])
    items = relationship("OrderItem", back_populates="order")
    payment = relationship("Payment", back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"

    id           = Column(Integer, primary_key=True, index=True)
    order_id     = Column(Integer, ForeignKey("orders.id",   ondelete="CASCADE"), nullable=False)
    product_id   = Column(Integer, ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    product_name = Column(String,  default="")
    price        = Column(Float,   nullable=False)
    quantity     = Column(Integer, default=1)

    order   = relationship("Order",   back_populates="items")
    product = relationship("Product", back_populates="order_items")


class Payment(Base):
    __tablename__ = "payments"
 
    id         = Column(Integer, primary_key=True, index=True)
    order_id   = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    payment_id = Column(String, nullable=False)          # PayPal PAY-XXXXXX token
    payer_id   = Column(String, default="")              # PayPal PayerID
    status     = Column(String, default="Pending")       # Pending / Completed / Failed
    method     = Column(String, default="PayPal")        # PayPal / Stripe / etc.
    created_at = Column(DateTime, default=datetime.utcnow)
 
    order = relationship("Order", back_populates="payment")

class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id         = Column(Integer, primary_key=True, index=True)
    event_id   = Column(String, unique=True, index=True)   # PayPal event ID (idempotency key)
    event_type = Column(String)
    raw_body   = Column(Text )
    received_at = Column(DateTime, default=datetime.utcnow)