�import os
import sys
import json
import base64
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

# --- SETUP PATHS ---
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock secrets to avoid "CRITICAL" warnings during import
with patch.dict(os.environ, {
    "MINT_SECRET": "test_secret_123",
    "ENABLE_X402": "true",
    "OPENROUTER_API_KEY": "sk-or-v1-mock",
    "X402_WALLET_ADDRESS": "0xTestWallet"
}):
    from gateway_server import app, verify_x402_payment

client = TestClient(app)

def test_x402_flow_mock():
    print("\n--- TEST: x402 Hybrid Flow ---")
    
    # 1. GUEST REQUEST (No Auth)
    print("1. Sending Guest Request (No Auth)...")
    url = "/v1/chat/completions"
    payload = {
        "model": "sovereign/deepseek-r1",
        "messages": [{"role": "user", "content": "Hi"}]
    }
    
    resp_402 = client.post(url, json=payload)
    
    # 2. VERIFY 402 RESPONSE FORMAT
    assert resp_402.status_code == 402, f"Expected 402, got {resp_402.status_code}"
    
    x402_header = resp_402.headers.get("PAYMENT-REQUIRED")
    assert x402_header, "Missing PAYMENT-REQUIRED header"
    print("✅ 402 Response Received with Header!")
    
    # 3. DECODE HEADER
    decoded_json = json.loads(base64.b64decode(x402_header).decode())
    assert "x402Version" in decoded_json
    assert "accepts" in decoded_json
    print(f"✅ Header Parsed: {decoded_json['accepts'][0]['network']} Price: {decoded_json['accepts'][0]['price']}")
    
    # 4. SIMULATE PAYMENT (Mocking the verification)
    print("4. Simulating Payment & Signature...")
    mock_signature = "0xValidSignatureMock"
    
    # Mock the gateway's verify/settle calls to x402.org
    with patch("gateway_server.requests.post") as mock_post:
        # Verify Response
        mock_post.side_effect = [
            MagicMock(status_code=200, json=lambda: {"paymentId": "pay_123"}), # /verify
            MagicMock(status_code=200, json=lambda: {"status": "settled"})     # /settle
        ]
        
        # Mock OpenRouter (to avoid real API call)
        with patch("gateway_server.httpx.AsyncClient.post") as mock_llm:
            mock_llm.return_value = MagicMock(
                status_code=200, 
                content=b'{"choices": [{"message": {"content": "Hello via x402"}}]}', 
                headers={"content-type": "application/json"}
            )
            
            # 5. RETRY WITH SIGNATURE
            headers = {"PAYMENT-SIGNATURE": mock_signature}
            resp_200 = client.post(url, json=payload, headers=headers)
            
            # 6. VERIFY SUCCESS
            assert resp_200.status_code == 200, f"Expected 200, got {resp_200.status_code}: {resp_200.text}"
            print("✅ Request Succeeded with valid Signature!")
            
            # 7. VERIFY RECEIPT
            receipt = resp_200.headers.get("PAYMENT-RESPONSE")
            assert receipt, "Missing PAYMENT-RESPONSE receipt header"
            receipt_data = json.loads(base64.b64decode(receipt).decode())
            assert receipt_data["status"] == "settled"
            print("✅ Receipt Verified!")

if __name__ == "__main__":
    try:
        test_x402_flow_mock()
        print("\n🎉 ALL TESTS PASSED")
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
    except Exception as e:
        print(f"\n❌ EXCEPTION: {e}")
�*cascade08"(d4e7a325d0144b3814ef864593774f7a395132062Sfile:///c:/Users/rovie%20segubre/agent/sovereign_api/tests/test_x402_integration.py:&file:///c:/Users/rovie%20segubre/agent