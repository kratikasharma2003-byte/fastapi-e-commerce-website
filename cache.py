"""
cache.py  ─  Redis Caching Layer for ShopFast
=============================================
Local Redis (no Docker).  Start Redis with:
    sudo apt install redis-server -y && sudo systemctl start redis

Environment variables (.env):
    REDIS_URL=redis://localhost:6379/0   ← default, no change needed for local
    CACHE_DEFAULT_TTL=300                ← seconds (default 5 min)

Install:
    pip install "redis[hiredis]>=5.0.0"
"""

import json
import os
from typing import Any, Optional, Callable
from loguru import logger

import redis

# ─── Config ───────────────────────────────────────────────────────────────────

REDIS_URL    = os.getenv("REDIS_URL", "redis://localhost:6379/0")
DEFAULT_TTL  = int(os.getenv("CACHE_DEFAULT_TTL", 300))

# Per-domain TTLs (seconds)
TTL = {
    "products_all":   600,   # 10 min
    "product_single": 600,   # 10 min
    "product_search": 120,   # 2 min
    "user_profile":   300,   # 5 min
    "cart":            60,   # 1 min  – feel near-live
    "orders_user":    120,   # 2 min
    "order_single":   300,   # 5 min
    "admin_stats":     60,   # 1 min
}

# ─── Key builders ─────────────────────────────────────────────────────────────

class Keys:
    @staticmethod
    def products_all(sort: str = "") -> str:
        return f"products:all:sort={sort}"

    @staticmethod
    def product(product_id: int) -> str:
        return f"product:{product_id}"

    @staticmethod
    def product_search(q: str, category: str, min_price: float,
                       max_price: float, sort: str) -> str:
        return (
            f"products:search:"
            f"q={q}:cat={category}:min={min_price}:max={max_price}:sort={sort}"
        )

    @staticmethod
    def user_profile(email: str) -> str:
        return f"user:profile:{email}"

    @staticmethod
    def cart(email: str) -> str:
        return f"cart:{email}"

    @staticmethod
    def orders_user(email: str) -> str:
        return f"orders:user:{email}"

    @staticmethod
    def order_single(order_id: int) -> str:
        return f"order:{order_id}"

    @staticmethod
    def admin_stats() -> str:
        return "admin:stats"


# ─── Redis client (sync, reused) ─────────────────────────────────────────────

_client: Optional[redis.Redis] = None

def _get_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(
            REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        logger.info(f"[Cache] Redis connected → {REDIS_URL}")
    return _client


# ─── Core Cache class ─────────────────────────────────────────────────────────

class Cache:
    """
    Thin sync wrapper used by all FastAPI route functions (def and async def).
    All methods silently degrade — if Redis is down, callers get None and
    fall through to the database.
    """

    @property
    def r(self) -> redis.Redis:
        return _get_client()

    # ── Primitives ────────────────────────────────────────────────────────────

    def get(self, key: str) -> Optional[Any]:
        """Return a Python object from cache, or None on miss / Redis error."""
        try:
            raw = self.r.get(key)
            if raw is None:
                return None
            logger.debug(f"[Cache] HIT  {key}")
            return json.loads(raw)
        except Exception as exc:
            logger.warning(f"[Cache] GET error key={key}: {exc}")
            return None

    def set(self, key: str, value: Any, ttl: int = DEFAULT_TTL) -> bool:
        """Serialise value → JSON and store with TTL. Returns True on success."""
        try:
            self.r.setex(key, ttl, json.dumps(value, default=str))
            logger.debug(f"[Cache] SET  {key}  ttl={ttl}s")
            return True
        except Exception as exc:
            logger.warning(f"[Cache] SET error key={key}: {exc}")
            return False

    def delete(self, *keys: str) -> int:
        """Delete one or more keys. Returns number deleted."""
        try:
            return self.r.delete(*keys) if keys else 0
        except Exception as exc:
            logger.warning(f"[Cache] DELETE error: {exc}")
            return 0

    def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching a glob pattern using SCAN (safe for prod —
        never blocks the server unlike KEYS *).
        """
        try:
            deleted = 0
            cursor   = 0
            while True:
                cursor, batch = self.r.scan(cursor, match=pattern, count=200)
                if batch:
                    deleted += self.r.delete(*batch)
                if cursor == 0:
                    break
            return deleted
        except Exception as exc:
            logger.warning(f"[Cache] SCAN/DELETE error pattern={pattern}: {exc}")
            return 0

    def ping(self) -> bool:
        try:
            return self.r.ping()
        except Exception:
            return False

    # ── Cache-aside helper ────────────────────────────────────────────────────

    def get_or_set(self, key: str, loader: Callable, ttl: int = DEFAULT_TTL) -> Any:
        """
        Classic cache-aside pattern:
          1. Return from cache if present.
          2. Call loader() on miss, store result, return it.
        loader must be a zero-arg callable (lambda or nested def).
        """
        cached = self.get(key)
        if cached is not None:
            return cached
        logger.debug(f"[Cache] MISS {key}")
        data = loader()
        if data is not None:
            self.set(key, data, ttl)
        return data


# Module-level singleton
cache = Cache()


# ─── Invalidation helpers ─────────────────────────────────────────────────────

def invalidate_product(product_id: int):
    """Call after create / update / soft-delete / restore of a product."""
    n  = cache.delete(Keys.product(product_id))
    n += cache.delete_pattern("products:*")
    logger.info(f"[Cache] Invalidated product {product_id} — {n} keys cleared")


def invalidate_user_profile(email: str):
    """Call after updating a user's profile or role."""
    n = cache.delete(Keys.user_profile(email))
    logger.info(f"[Cache] Invalidated profile {email} — {n} keys cleared")


def invalidate_cart(email: str):
    """Call after any cart mutation (add / update / remove / clear / checkout)."""
    n = cache.delete(Keys.cart(email))
    logger.info(f"[Cache] Invalidated cart {email} — {n} keys cleared")


def invalidate_user_orders(email: str, order_id: Optional[int] = None):
    """Call after placing or updating an order."""
    n = cache.delete(Keys.orders_user(email))
    if order_id:
        n += cache.delete(Keys.order_single(order_id))
    logger.info(f"[Cache] Invalidated orders {email} — {n} keys cleared")


def invalidate_admin_stats():
    """Call after any write that changes dashboard counters."""
    n = cache.delete(Keys.admin_stats())
    logger.info(f"[Cache] Invalidated admin stats — {n} keys cleared")


# ─── Startup / shutdown (called from FastAPI lifespan) ───────────────────────

def redis_startup():
    """Verify Redis is reachable at startup. Logs a warning if not."""
    ok = cache.ping()
    if ok:
        logger.info("[Cache] Redis connection verified ✅")
    else:
        logger.warning(
            "[Cache] Redis ping failed — caching disabled, all reads fall through to DB ⚠️"
        )


def redis_shutdown():
    """Close the Redis connection on app shutdown."""
    global _client
    if _client:
        _client.close()
        _client = None
        logger.info("[Cache] Redis connection closed")