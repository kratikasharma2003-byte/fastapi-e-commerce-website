from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    phone = Column(String, default="")
    dob = Column(String, default="")
    gender = Column(String, default="")
    role = Column(String, default="user")
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    cart_items = relationship("CartItem", back_populates="user", foreign_keys="CartItem.user_email")
    orders = relationship("Order", back_populates="user", foreign_keys="Order.user_id")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, default="")
    price = Column(Float, nullable=False)
    image = Column(String, default="")
    category = Column(String, default="General")
    stock = Column(Integer, default=0)
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    cart_items = relationship("CartItem", back_populates="product")
    order_items = relationship("OrderItem", back_populates="product")

    @property
    def image_url(self):
        return self.image or ""

    @image_url.setter
    def image_url(self, value):
        self.image = value or ""


class CartItem(Base):
    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True, index=True)
    user_email = Column(String, ForeignKey("users.email", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    quantity = Column(Integer, default=1)

    user = relationship("User", back_populates="cart_items", foreign_keys=[user_email])
    product = relationship("Product", back_populates="cart_items")

    __table_args__ = (
        UniqueConstraint("user_email", "product_id", name="unique_user_product_cart"),
    )


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user_email = Column(String, nullable=False)
    user_name = Column(String, default="")
    total = Column(Float, nullable=False)
    status = Column(String, default="Pending")
    transaction_id = Column(String, unique=True, nullable=True)
    stripe_session_id = Column(String, nullable=True)
    paypal_order_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    return_reason = Column(Text, nullable=True)
    return_requested_at = Column(DateTime(timezone=True), nullable=True)
    
    user = relationship("User", back_populates="orders", foreign_keys=[user_id])
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payment = relationship("Payment", back_populates="order", uselist=False)


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    product_name = Column(String, default="")
    price = Column(Float, nullable=False)
    quantity = Column(Integer, default=1)

    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    payment_id = Column(String, nullable=False)
    payer_id = Column(String, default="")
    status = Column(String, default="Pending")
    method = Column(String, default="PayPal")
    created_at = Column(DateTime, default=datetime.utcnow)

    order = relationship("Order", back_populates="payment")


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String, unique=True, index=True)
    event_type = Column(String)
    raw_body = Column(Text)
    received_at = Column(DateTime, default=datetime.utcnow)
