import requests
import json
import time

# CONFIG
GATEWAY_URL = "https://indecomposable-adelia-impolitely.ngrok-free.dev/v1/chat/completions"
# GATEWAY_URL = "http://localhost:8000/v1/chat/completions" # Fallback

def test_manual_payment():
    print(f"\n--- 🧪 Manual Payment Test (The Stranger) ---")
    print(f"Target: {GATEWAY_URL}")
    print("Goal: Buy intelligence from the Sovereign Node.")

    # 1. ATTEMPT TO BUY (Expect 402)
    print("\n[Client] Sending initial request...")
    payload = {
        "model": "sovereign-r1",
        "messages": [{"role": "user", "content": "Hello Sovereign Node. Can you verify this payment?"}],
        "stream": False
    }

    try:
        response = requests.post(GATEWAY_URL, json=payload, timeout=10)
    except Exception as e:
        print(f"[Error] Could not connect: {e}")
        return

    if response.status_code != 402:
        print(f"[Error] Expected 402, got {response.status_code}")
        print(response.text)
        return

    # 2. CAPTURE INVOICE
    data = response.json()
    invoice = data.get("invoice")
    price = data.get("price_sats")
    
    print(f"\n[Gateway] 402 Payment Required.")
    print(f"   Price: {price} sats")
    print(f"   Invoice: {invoice}")
    
    print("\n" + "="*60)
    print("ACTION REQUIRED: Pay this invoice with your Lightning Wallet!")
    print("="*60)
    print(f"\n{invoice}\n")
    print("="*60)

    # 3. USER INTERACTION
    input("Press Enter AFTER you have paid...")
    preimage = input("Paste the PREIMAGE (Hex string) from your wallet here: ").strip()

    if not preimage:
        print("[Error] No preimage provided.")
        return

    # 4. REDEEM TOKEN
    print(f"\n[Client] Authenticating with Preimage: {preimage[:8]}...")
    
    # Construct L402 Header
    # L402 <Preimage>:<Signature>
    # We use a dummy signature because the server (Stage 2) only verifies the Preimage hash.
    token = f"L402 {preimage}:dummy_signature"
    
    headers = {
        "Authorization": token,
        "Content-Type": "application/json"
    }

    try:
        response2 = requests.post(GATEWAY_URL, json=payload, headers=headers, timeout=120)
    except Exception as e:
        print(f"[Error] Request failed: {e}")
        return

    # 5. RESULT
    if response2.status_code == 200:
        print("\n[Success] 🟢 Payment Verified! Intelligence Received:")
        print("-" * 40)
        try:
            print(response2.json()['choices'][0]['message']['content'])
        except:
            print(response2.text)
        print("-" * 40)
    else:
        print(f"\n[Failure] 🔴 Server rejected the payment.")
        print(f"Status: {response2.status_code}")
        print(f"Body: {response2.text}")

if __name__ == "__main__":
    test_manual_payment()
