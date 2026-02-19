import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"
ADMIN_KEY = "sovereign_mint_key_x7k9m2p4q8r6t1w3y5z0a8b6c4d2e0f7"

def run_security_test():
    print("--- 🛡️ Sovereign Mint: Security Verification Test ---")
    
    # 1. MINT TOKEN
    print("\n[Step 1] Minting fresh token (1000 sats)...")
    identifier = f"test_verify_{int(time.time())}"
    try:
        resp = requests.post(
            f"{BASE_URL}/v1/admin/mint",
            headers={"X-Admin-Key": ADMIN_KEY},
            json={"amount_sats": 1000, "identifier": identifier},
            timeout=10
        )
        if resp.status_code != 200:
            print(f"❌ Failed to mint: {resp.text}")
            return
        token_a = resp.json()["access_token"]
        print(f"✅ Token A Minted.")
    except Exception as e:
        print(f"❌ Connection Error (Mint): {e}")
        return

    # 2. FIRST SPEND (Success) - Verification Logic happens BEFORE upstream
    # However, standard flow waits for upstream. OpenRouter can be slow.
    print("\n[Step 2] Performing initial spend (Token A)...")
    payload = {"model": "sovereign-r1", "messages": [{"role": "user", "content": "Hi"}]}
    try:
        resp = requests.post(
            f"{BASE_URL}/v1/chat/completions",
            headers={"Authorization": f"Bearer {token_a}"},
            json=payload,
            timeout=60 # Extended timeout for AI latency
        )
        if resp.status_code == 200:
            print("✅ First Spend: SUCCESS (as expected).")
            token_b = resp.headers.get("X-Sovereign-Balance-Token")
            print("✅ Change Token B received.")
        else:
            print(f"❌ First Spend FAILED: {resp.status_code} - {resp.text}")
            return
    except Exception as e:
         print(f"❌ Connection Error (Spend 1): {e}")
         return

    # 3. REPLAY ATTEMPT (The Vulnerability Check)
    # This should be FAST because it's rejected locally.
    print("\n[Step 3] Attempting REPLAY ATTACK (Sending Token A again)...")
    try:
        resp = requests.post(
            f"{BASE_URL}/v1/chat/completions",
            headers={"Authorization": f"Bearer {token_a}"},
            json=payload,
            timeout=10 
        )
        if resp.status_code == 403:
            print("✅ REPLAY REJECTED: Server returned 403 (Attack Foiled).")
            print(f"   Error Msg: {resp.json().get('error')}")
        elif resp.status_code == 200:
            print("❌ VULNERABILITY DETECTED: Token A was accepted twice! Infinite money glitch alive.")
        else:
            print(f"❓ Unexpected status: {resp.status_code} - {resp.text}")
    except Exception as e:
         print(f"❌ Connection Error (Replay): {e}")

    # 4. USE CHANGE (Stateless Flow Check)
    if token_b:
        print("\n[Step 4] Verifying Change Token B works...")
        try:
            resp = requests.post(
                f"{BASE_URL}/v1/chat/completions",
                headers={"Authorization": f"Bearer {token_b}"},
                json=payload,
                timeout=60
            )
            if resp.status_code == 200:
                print("✅ Change Token B: SUCCESS.")
                print("✅ Whole lifecycle verified.")
            else:
                print(f"❌ Change Token B FAILED: {resp.status_code} - {resp.text}")
        except Exception as e:
            print(f"❌ Connection Error (Spend Change): {e}")

if __name__ == "__main__":
    run_security_test()
