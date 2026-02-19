≥"""
End-to-End Mailbox Protocol Test
================================
Simulates the full lifecycle:
1. [Watcher Mock] Calculates sats using Oracle logic (Chainlink Mock)
2. [Watcher Mock] calls /v1/admin/mint
3. [Gateway] Stores token in persistent mailbox
4. [Wallet] Polls /v1/balance/claim to pick it up
5. [Wallet] Spends the token to prove it works
"""

import requests
import time
import json
import secrets
import os
from wallet_client import SovereignWallet

# CONFIG
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000")
ADMIN_KEY = os.getenv("ADMIN_KEY", "sovereign_mint_key_x7k9m2p4q8r6t1w3y5z0a8b6c4d2e0f7") # From mint_secret.json

def test_full_flow():
    print("üöÄ STARTING MAILBOX PROTOCOL TEST")
    print("=================================")
    
    # 1. Simulate Polygon Deposit
    tx_hash = f"0x{secrets.token_hex(32)}"
    amount_usdc = 10.0
    
    # Simulate Chainlink Price Fetch (Mocking the Oracle logic)
    print(f"\nüì° [STEP 1] Watcher detects ${amount_usdc} USDC deposit...")
    btc_price = 70000 # Mock Price
    sats_per_usdc = int(100_000_000 // btc_price) # Floor division
    amount_sats = int(amount_usdc * sats_per_usdc)
    print(f"   Oracle Rate: {sats_per_usdc} sats/$1")
    print(f"   Mint Amount: {amount_sats} sats")
    
    # 2. Watcher calls Admin Mint
    print(f"\nVE [STEP 2] Watcher calls Gateway Mint...")
    payload = {
        "amount_sats": amount_sats,
        "identifier": tx_hash
    }
    resp = requests.post(
        f"{GATEWAY_URL}/v1/admin/mint",
        json=payload,
        headers={"X-Admin-Key": ADMIN_KEY}
    )
    
    if resp.status_code == 200:
        print("‚úÖ Gateway accepted mint request.")
        print("   Token should be in PENDING_CLAIMS (mailbox).")
    else:
        print(f"‚ùå Mint Failed: {resp.text}")
        return

    # 3. Validation: Check if Pending File exists and contains our hash
    # (This verifies the 'Persistence' fix)
    try:
        with open(".agent/data/pending_claims.json", "r") as f:
            data = json.load(f)
            if tx_hash in data:
                print("‚úÖ [PERSISTENCE] Token found in pending_claims.json disk storage!")
            else:
                print("‚ùå [PERSISTENCE] Token NOT found in disk storage!")
                return
    except Exception as e:
        print(f"‚ùå Could not read pending_claims.json: {e}")
        return

    # 4. Wallet Claims the Token
    print(f"\nüëõ [STEP 3] Wallet attempts to claim {tx_hash[:10]}...")
    wallet = SovereignWallet()
    
    # We deliberately wait 2 seconds to simulate network latency
    time.sleep(2)
    
    success = wallet.top_up(tx_hash)
    
    if success:
        print("‚úÖ Wallet successfully claimed the token!")
    else:
        print("‚ùå Wallet failed to claim token.")
        return

    # 5. Verify Mailbox is Empty (Claimed)
    with open(".agent/data/pending_claims.json", "r") as f:
        data = json.load(f)
        if tx_hash not in data:
            print("‚úÖ [CLEANUP] Token properly removed from mailbox after claim.")
        else:
            print("‚ùå [CLEANUP] Token still in mailbox! Double-spend risk.")

    # 6. Spend the Token to prove it's valid
    print(f"\nüß† [STEP 4] Spending token on a thought...")
    answer = wallet.think("What is 5 * 5?")
    
    if answer:
        print(f"‚úÖ AI Response: {answer[:50]}...")
        print("\nüéâ TEST COMPLETE: SUCCESS")
    else:
        print("‚ùå AI Request failed.")

if __name__ == "__main__":
    test_full_flow()
˘ *cascade08˘§§≠ *cascade08≠∏*cascade08∏˝ *cascade08˝ñ*cascade08ñ≠ *cascade08≠Æ*cascade08Æª *cascade08ª“*cascade08“à *cascade08àâ*cascade08â≥ *cascade08"(d4e7a325d0144b3814ef864593774f7a395132062;file:///c:/Users/rovie%20segubre/agent/test_mailbox_flow.py:&file:///c:/Users/rovie%20segubre/agent