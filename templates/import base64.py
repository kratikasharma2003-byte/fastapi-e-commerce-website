import base64
import json
import uuid
import requests

MERCHANT_ID = "YOUR_MERCHANT_ID"
SALT_KEY = "YOUR_SALT_KEY"
SALT_INDEX = 1

BASE_URL = "https://api.phonepe.com/apis/hermes/pg/v1/pay"


def create_payment(amount, redirect_url):
    transaction_id = str(uuid.uuid4())

    payload = {
        "merchantId": MERCHANT_ID,
        "merchantTransactionId": transaction_id,
        "merchantUserId": "USER_" + transaction_id[:8],
        "amount": amount * 100,  # paise
        "redirectUrl": redirect_url,
        "redirectMode": "POST",
        "paymentInstrument": {
            "type": "PAY_PAGE"
        }
    }

    encoded_payload = base64.b64encode(
        json.dumps(payload).encode()
    ).decode()

    request_body = {
        "request": encoded_payload
    }

    # ⚠️ You MUST replace this with real checksum (X-VERIFY)
    headers = {
        "Content-Type": "application/json",
        "X-VERIFY": "PUT_CHECKSUM_HERE"
    }

    response = requests.post(BASE_URL, json=request_body, headers=headers)

    return response.json(), transaction_id


def check_payment_status(transaction_id):
    url = f"https://api.phonepe.com/apis/hermes/pg/v1/status/{MERCHANT_ID}/{transaction_id}"

    headers = {
        "Content-Type": "application/json",
        "X-VERIFY": "PUT_CHECKSUM_HERE"
    }

    response = requests.get(url, headers=headers)
    return response.json()