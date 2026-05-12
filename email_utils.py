import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_HOST       = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT       = int(os.getenv("SMTP_PORT", "587"))
SENDER_EMAIL    = os.getenv("SENDER_EMAIL", "")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "")


def _ensure_email_config():
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        raise Exception(
            "Email is not configured. Set SENDER_EMAIL and SENDER_PASSWORD in your environment."
        )


# ─────────────────────────────────────────────────────────────────────────────
#  OTP / generic email
# ─────────────────────────────────────────────────────────────────────────────
def send_email(to_email: str, subject: str, body: str):
    """
    Sends a plain-text / OTP email via Gmail SMTP.

    Args:
        to_email   : recipient email address
        subject    : email subject line
        body       : plain-text body  e.g. "Your OTP is 123456"

    Raises:
        Exception  : re-raises any SMTP / connection error so the
                     caller (main.py) can return a proper HTTP 500.
    """
    try:
        _ensure_email_config()
        msg            = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = SENDER_EMAIL
        msg["To"]      = to_email

        text_part = MIMEText(body, "plain")

        html_body = f"""
        <html>
          <body style="font-family:Arial,sans-serif;background:#f4f6f9;padding:30px;">
            <div style="max-width:400px;margin:auto;background:white;
                        border-radius:10px;padding:30px;
                        box-shadow:0 2px 8px rgba(0,0,0,0.1);">
              <h2 style="color:#4facfe;text-align:center;">OTP Verification</h2>
              <p style="font-size:15px;color:#555;">
                Use the OTP below to reset your password.<br>
                It is valid for <strong>5 minutes</strong>.
              </p>
              <div style="text-align:center;margin:25px 0;">
                <span style="font-size:36px;font-weight:bold;
                             letter-spacing:8px;color:#333;">
                  {body.split()[-1]}
                </span>
              </div>
              <p style="font-size:12px;color:#999;text-align:center;">
                If you did not request this, please ignore this email.
              </p>
            </div>
          </body>
        </html>
        """
        html_part = MIMEText(html_body, "html")

        msg.attach(text_part)
        msg.attach(html_part)

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, to_email, msg.as_string())

        print(f"[email_utils] ✅ OTP email sent to {to_email}")

    except smtplib.SMTPAuthenticationError:
        raise Exception(
            "SMTP Authentication failed. "
            "Use a Gmail App Password (not your normal password). "
            "Enable 2-FA → https://myaccount.google.com/security → App Passwords"
        )
    except smtplib.SMTPException as e:
        raise Exception(f"SMTP error: {e}")
    except Exception as e:
        raise Exception(f"Email send failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
#  Order-placed confirmation email
# ─────────────────────────────────────────────────────────────────────────────
def send_order_confirmation(to_email: str, order_id, total, items: list = None):
    """
    Sends a branded 'Order Placed Successfully' email to the customer.

    Args:
        to_email  : customer's registered email address
        order_id  : order ID from the database / checkout response
        total     : numeric or string total  e.g.  1299  or  "₹1,299"
        items     : optional list of dicts  [{name, quantity, price}, ...]

    Raises:
        Exception : re-raises any SMTP / connection error.

    Usage in main.py (call this INSIDE your /checkout route):
        from email_utils import send_order_confirmation
        send_order_confirmation(user_email, data.order_id, data.total, data.items)
    """

    # ── Format total neatly ───────────────────────────────────────────
    try:
        total_str = f"₹{int(float(str(total).replace('₹','').replace(',',''))):,}"
    except Exception:
        total_str = str(total)

    # ── Build items rows ──────────────────────────────────────────────
    items_html = ""
    items_text = ""
    if items:
        rows = ""
        for item in items:
            name  = item.get("name", "")
            qty   = item.get("quantity", 1)
            price = item.get("price", "")
            try:
                price_str = f"₹{int(float(str(price))):,}"
            except Exception:
                price_str = str(price)
            rows += f"""
            <tr>
              <td style="padding:9px 14px;border-bottom:1px solid #f0eeff;
                         color:#2d2d44;font-size:14px;">{name}</td>
              <td style="padding:9px 14px;border-bottom:1px solid #f0eeff;
                         text-align:center;color:#6c5ce7;font-weight:700;font-size:14px;">{qty}</td>
              <td style="padding:9px 14px;border-bottom:1px solid #f0eeff;
                         text-align:right;color:#2d2d44;font-size:14px;">{price_str}</td>
            </tr>"""
            items_text += f"  • {name}  ×{qty}  {price_str}\n"

        items_html = f"""
        <p style="font-size:13px;color:#8888a0;font-weight:700;
                  text-transform:uppercase;letter-spacing:1px;margin:20px 0 8px;">
          Items Ordered
        </p>
        <table width="100%" cellpadding="0" cellspacing="0"
               style="border-collapse:collapse;border-radius:10px;overflow:hidden;
                      border:1px solid #f0eeff;">
          <thead>
            <tr style="background:#f4f3ff;">
              <th style="padding:10px 14px;text-align:left;font-size:11px;
                         color:#8888a0;text-transform:uppercase;letter-spacing:1px;">Product</th>
              <th style="padding:10px 14px;text-align:center;font-size:11px;
                         color:#8888a0;text-transform:uppercase;letter-spacing:1px;">Qty</th>
              <th style="padding:10px 14px;text-align:right;font-size:11px;
                         color:#8888a0;text-transform:uppercase;letter-spacing:1px;">Price</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>"""

    # ── Plain-text fallback ───────────────────────────────────────────
    plain_text = f"""
🎉 Order Placed Successfully!

Hi there,

Thank you for shopping on ShopFast!
Your order has been received and is being processed.

━━━━━━━━━━━━━━━━━━━━━━━━
  Order ID   : #{order_id}
  Total Paid : {total_str}
  Status     : Pending
━━━━━━━━━━━━━━━━━━━━━━━━

{("Items Ordered:\n" + items_text) if items_text else ""}
We'll notify you once your order is shipped.

Thanks for choosing ShopFast!
— The ShopFast Team
    """.strip()

    # ── HTML email ────────────────────────────────────────────────────
    html_body = f"""
    <html>
      <body style="font-family:Arial,sans-serif;background:#f4f3ff;padding:30px;margin:0;">
        <div style="max-width:500px;margin:auto;background:white;
                    border-radius:18px;overflow:hidden;
                    box-shadow:0 6px 32px rgba(108,92,231,0.14);">

          <!-- ── Header ── -->
          <div style="background:linear-gradient(135deg,#6c5ce7 0%,#a29bfe 100%);
                      padding:36px 28px;text-align:center;">
            <div style="font-size:58px;margin-bottom:12px;line-height:1;">🎉</div>
            <h1 style="color:white;font-size:24px;margin:0;font-weight:800;letter-spacing:-0.5px;">
              Order Placed Successfully!
            </h1>
            <p style="color:rgba(255,255,255,0.88);font-size:15px;margin:10px 0 0;">
              Thank you for shopping with <strong>ShopFast</strong> 🛍️
            </p>
          </div>

          <!-- ── Body ── -->
          <div style="padding:30px 28px;">
            <p style="font-size:15px;color:#555;margin:0 0 22px;line-height:1.6;">
              Hi there! 👋<br>
              Great news — your order has been received and is now being
              processed. Here's a summary of your purchase:
            </p>

            <!-- Order detail box -->
            <div style="background:#f4f3ff;border-radius:14px;padding:20px 22px;margin-bottom:22px;">
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="font-size:12px;color:#8888a0;text-transform:uppercase;
                             letter-spacing:0.9px;padding-bottom:12px;">Order ID</td>
                  <td style="text-align:right;font-size:15px;font-weight:800;
                             color:#2d2d44;padding-bottom:12px;">#{order_id}</td>
                </tr>
                <tr>
                  <td style="font-size:12px;color:#8888a0;text-transform:uppercase;
                             letter-spacing:0.9px;padding-bottom:12px;">Amount Paid</td>
                  <td style="text-align:right;font-size:18px;font-weight:800;
                             color:#6c5ce7;padding-bottom:12px;">{total_str}</td>
                </tr>
                <tr>
                  <td style="font-size:12px;color:#8888a0;text-transform:uppercase;
                             letter-spacing:0.9px;">Status</td>
                  <td style="text-align:right;">
                    <span style="display:inline-block;font-size:12px;font-weight:700;
                                 color:#00b894;background:#d4f8ec;
                                 padding:4px 14px;border-radius:20px;">
                      ✅ Confirmed
                    </span>
                  </td>
                </tr>
              </table>
            </div>

            {items_html}

            <!-- Note -->
            <p style="font-size:13px;color:#aaa;text-align:center;margin-top:24px;line-height:1.7;">
              We'll send you another email once your order is shipped.<br>
              Questions? Reply to this email anytime.
            </p>
          </div>

          <!-- ── Footer ── -->
          <div style="background:#1a1a2e;padding:20px 28px;text-align:center;">
            <p style="color:rgba(255,255,255,0.45);font-size:12px;margin:0;">
              © 2025 <span style="color:#a29bfe;font-weight:700;">ShopFast</span>
              &nbsp;•&nbsp; All rights reserved
            </p>
          </div>

        </div>
      </body>
    </html>"""

    # ── Send ──────────────────────────────────────────────────────────
    try:
        _ensure_email_config()
        msg            = MIMEMultipart("alternative")
        msg["Subject"] = f"🎉 Order Placed Successfully! — Order #{order_id}"
        msg["From"]    = SENDER_EMAIL
        msg["To"]      = to_email

        msg.attach(MIMEText(plain_text, "plain"))
        msg.attach(MIMEText(html_body,  "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, to_email, msg.as_string())

        (f"[email_utils] ✅ Order confirmation sent → {to_email}  (order #{order_id})")

    except smtplib.SMTPAuthenticationError:
        raise Exception(
            "SMTP Authentication failed. "
            "Use a Gmail App Password — not your normal Gmail password. "
            "Enable 2-FA → https://myaccount.google.com/security → App Passwords"
        )
    except smtplib.SMTPException as e:
        raise Exception(f"SMTP error while sending order email: {e}")
    except Exception as e:
        raise Exception(f"Order confirmation email failed: {e}")
