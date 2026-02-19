# Wallet Client Implementation Plan (The Buyer)

## Goal
Build `wallet_client.py` to purchase compute from our own `gateway_server.py`.

## 1. The Purchase Flow
1.  **Attempt:** Client sends `POST /v1/chat/completions` (No Auth).
2.  **Rejection:** Server returns `402 Payment Required` + `WWW-Authenticate: L402 token`.
    *   Header: `L402 macaroon="...", invoice="lnbc..."`
3.  **Payment (Mock):** Client "pays" the invoice (simulated).
    *   In Prod: Calls Alby API `pay_bolt11(invoice)`.
    *   In Mock: Just grabs the `MOCK_PREIMAGE`.
4.  **Authorization:** Client constructs the `Authorization` header.
    *   `L402 <PREIMAGE>:<SIGNATURE>`
5.  **Retry:** Client resends the request with the header.
6.  **Success:** Server returns the JSON response.

## 2. Code Structure
*   **File:** `wallet_client.py`
*   **Dependencies:** `httpx`

```python
import httpx

GATEWAY_URL = "http://localhost:8000/v1/chat/completions"

def buy_compute_mock():
    # 1. Try to buy (Expecting 402)
    resp = httpx.post(GATEWAY_URL, json={"model": "sovereign-llama3-8b"})
    
    if resp.status_code == 402:
        print("⚡ Payment Required! Handling L402...")
        data = resp.json()
        
        # 2. Extract Invoice (Mock Payment)
        invoice = data["invoice"]
        # In real life, we would do: preimage = alby.pay(invoice)
        preimage = "secret_proof_of_payment" 
        
        # 3. Construct Token
        token = f"L402 {preimage}:signed_challenge_123"
        
        # 4. Retry with Token
        resp2 = httpx.post(
            GATEWAY_URL, 
            json={"model": "sovereign-llama3-8b"},
            headers={"Authorization": token}
        )
        print("✅ Success:", resp2.json())
```
