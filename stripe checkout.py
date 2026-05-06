"""
stripe_checkout.py  —  Drop this file into your FastAPI project
================================================================
Wire it up in main.py:
    from stripe_checkout import stripe_router
    app.include_router(stripe_router)

Install:
    pip install stripe httpx

Your .env already has the keys — just make sure python-dotenv loads them,
or export them in your shell before starting uvicorn.
"""

import os
import stripe
import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# ── Config ────────────────────────────────────────────────────────
stripe.api_key  = os.getenv("STRIPE_SECRET_KEY")          # sk_test_...
WEBHOOK_SECRET  = os.getenv("STRIPE_WEBHOOK_SECRET", "")  # whsec_...
APP_HOST        = os.getenv("APP_HOST", "https://new-fastapi-e-commerce-website.onrender.com")

stripe_router = APIRouter(prefix="/stripe", tags=["Stripe"])


class CheckoutRequest(BaseModel):
    user_email: str


# ══════════════════════════════════════════════════════════════════
#  POST /stripe/create-checkout-session
#  Called by the 'Pay with Stripe' button in shop.html
# ══════════════════════════════════════════════════════════════════
@stripe_router.post("/create-checkout-session")
async def create_checkout_session(body: CheckoutRequest):
    if not stripe.api_key:
        raise HTTPException(
            status_code=500,
            detail="STRIPE_SECRET_KEY is not set in environment"
        )

    # ── 1. Load cart via your existing /cart endpoint ─────────────
    # This reuses the cart API you already have, so no extra DB code needed.
    # If you'd rather query the DB directly, replace this block.
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{APP_HOST}/cart",
                params={"email": body.user_email},
                timeout=5.0
            )
            r.raise_for_status()
            cart  = r.json()
            items = cart.get("items", [])
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Cart API error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not load cart: {str(e)}")

    if not items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    # ── 2. Build Stripe line_items ────────────────────────────────
    line_items = []
    for item in items:
        price_cents  = max(1, int(round(float(item.get("price", 0)) * 100)))
        product_data = {"name": item.get("name", "Product")}
        img = item.get("image_url", "") or ""
        if img.startswith("https://"):          # Stripe requires HTTPS images
            product_data["images"] = [img]
        line_items.append({
            "price_data": {
                "currency": "usd",
                "product_data": product_data,
                "unit_amount": price_cents,
            },
            "quantity": max(1, int(item.get("quantity", 1))),
        })

    # ── 3. Create Stripe Checkout Session ─────────────────────────
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=line_items,
            mode="payment",
            customer_email=body.user_email,
            success_url=f"{APP_HOST}/payment-success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{APP_HOST}/shop",
            metadata={"user_email": body.user_email},
        )
    except stripe.error.AuthenticationError:
        raise HTTPException(
            status_code=500,
            detail="Invalid Stripe key — check STRIPE_SECRET_KEY in .env"
        )
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=502, detail=f"Stripe error: {str(e)}")

    # ── 4. Return checkout URL → browser redirects there ─────────
    return JSONResponse({"checkout_url": session.url})


# ══════════════════════════════════════════════════════════════════
#  POST /stripe/webhook
#  Register in Stripe Dashboard → Developers → Webhooks
#  URL: https://yourdomain.com/stripe/webhook
#  Events to listen for: checkout.session.completed
# ══════════════════════════════════════════════════════════════════
@stripe_router.post("/webhook")
async def stripe_webhook(request: Request):
    payload    = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")

    if event["type"] == "checkout.session.completed":
        sess       = event["data"]["object"]
        user_email = (sess.get("metadata") or {}).get("user_email", "unknown")
        amount     = (sess.get("amount_total") or 0) / 100
        session_id = sess.get("id", "")
        print(f"[Stripe] ✅ {user_email} paid ${amount:.2f} — session {session_id}")

        # TODO: mark order as paid in your DB:
        # await db.execute(
        #     "UPDATE orders SET payment_status='paid' WHERE user_email=:e",
        #     {"e": user_email}
        # )

    return JSONResponse({"status": "ok"})