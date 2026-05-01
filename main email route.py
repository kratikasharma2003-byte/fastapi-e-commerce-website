# ═══════════════════════════════════════════════════════════════════════════
#  ADD THIS ENTIRE BLOCK TO YOUR main.py
#  Place the import at the top of your file with the other imports.
#  Place the route with your other @app routes.
# ═══════════════════════════════════════════════════════════════════════════

# ── 1. Add this import at the TOP of main.py (with your other imports) ────
from email_utils import send_order_confirmation

# ── 2. Add this Pydantic model (put it with your other models) ────────────
from pydantic import BaseModel
from typing import List, Optional

class OrderEmailRequest(BaseModel):
    user_email : str
    order_id   : str
    total      : str
    items      : Optional[List[dict]] = []

# ── 3. Add this route to main.py ──────────────────────────────────────────
from fastapi import HTTPException

@app.post("/send-order-email")
def send_order_email(req: OrderEmailRequest):
    """
    Called by shop.html after a successful checkout.
    Sends an order-placed confirmation email to the customer.
    """
    try:
        send_order_confirmation(
            to_email = req.user_email,
            order_id = req.order_id,
            total    = req.total,
            items    = req.items or []
        )
        return {"status": "sent", "message": f"Email sent to {req.user_email}"}
    except Exception as e:
        print(f"[main] ❌ Order email error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ═══════════════════════════════════════════════════════════════════════════
#  ALTERNATIVELY — send the email DIRECTLY inside your /checkout route.
#  This is the simplest approach: no separate /send-order-email needed.
#
#  Find your existing /checkout route and add these 3 lines at the end,
#  just before the return statement:
#
#      try:
#          send_order_confirmation(user_email, order.id, order.total, [])
#      except Exception as email_err:
#          print(f"[checkout] Email failed (non-critical): {email_err}")
#
# ═══════════════════════════════════════════════════════════════════════════