import random
import time

otp_db = {}

def generate_otp(email: str) -> str:
    otp = str(random.randint(100000, 999999))
    otp_db[email] = {
        "otp": otp,
        "expiry": time.time() + 300,  # 5 minutes
        "verified": False
    }
    return otp


def verify_otp(email: str, otp: str) -> bool:
    """
    Verify OTP. On success, marks it as verified but does NOT delete it,
    so the /reset-password endpoint can confirm verification happened.
    """
    if email not in otp_db:
        return False

    data = otp_db[email]

    if time.time() > data["expiry"]:
        del otp_db[email]
        return False

    if data["otp"] == otp:
        otp_db[email]["verified"] = True   # mark verified, keep for reset step
        return True

    return False


def is_verified(email: str) -> bool:
    """
    Check if OTP was already verified for this email (used by /reset-password).
    Clears the record after checking so it cannot be reused.
    """
    if email not in otp_db:
        return False

    data = otp_db[email]

    if time.time() > data["expiry"]:
        del otp_db[email]
        return False

    verified = data.get("verified", False)
    if verified:
        del otp_db[email]   # consumed — one-time use
    return verified