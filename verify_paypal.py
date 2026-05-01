import os
import sys
from unittest.mock import patch, MagicMock

# Add current directory and env directory to sys.path
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), "env"))

from env.paypal_payment import create_paypal_order, _inr_to_usd

def test_conversion():
    print("Testing INR to USD conversion...")
    # Default rate 0.012: 1000 INR * 0.012 = 12.00 USD
    assert _inr_to_usd(1000.0) == "12.00"
    # Small amount
    assert _inr_to_usd(0.5) == "0.01" # Minimum 0.01
    print("Conversion test passed!")

def test_order_payload():
    print("Testing PayPal order payload generation...")
    
    with patch('requests.post') as mock_post:
        # Mock the PayPal API response
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "id": "MOCK_PP_ORDER_ID",
            "links": [{"rel": "approve", "href": "https://paypal.com/approve/MOCK"}]
        }
        mock_resp.status_code = 201
        mock_post.return_value = mock_resp
        
        # Mock the access token
        with patch('env.paypal_payment._get_access_token', return_value="MOCK_TOKEN"):
            result = create_paypal_order(
                total_amount=1000.0,
                currency="INR", # Should be ignored and set to USD
                return_url="http://return",
                cancel_url="http://cancel"
            )
            
            # Check if requests.post was called with correct payload
            args, kwargs = mock_post.call_args
            payload = kwargs['json']
            
            amount = payload['purchase_units'][0]['amount']
            print(f"Generated Payload Amount: {amount}")
            
            assert amount['currency_code'] == "USD"
            assert amount['value'] == "12.00"
            assert result['order_id'] == "MOCK_PP_ORDER_ID"
            print("Order payload test passed!")

if __name__ == "__main__":
    try:
        test_conversion()
        test_order_payload()
        print("\nAll PayPal integration tests PASSED!")
    except Exception as e:
        print(f"\nTests FAILED: {e}")
        sys.exit(1)
