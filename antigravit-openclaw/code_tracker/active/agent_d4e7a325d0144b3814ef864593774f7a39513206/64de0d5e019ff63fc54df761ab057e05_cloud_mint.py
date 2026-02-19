¹"""
Cloud Mint - Admin Tool for Minting Credits
============================================
Connects to a remote Sovereign Gateway and mints credits.

Usage:
    Set environment variables, then run:
    
    GATEWAY_URL=http://YOUR_SERVER:8000 ADMIN_KEY=your_secret python cloud_mint.py
"""

import requests
import json
import os
from pathlib import Path

# --- CONFIGURATION (via Environment Variables) ---
GATEWAY_URL = os.getenv("GATEWAY_URL")
ADMIN_KEY = os.getenv("ADMIN_KEY")

if not GATEWAY_URL:
    print("[ERROR] GATEWAY_URL not set! Example: http://YOUR_SERVER:8000")
    exit(1)

if not ADMIN_KEY:
    print("[ERROR] ADMIN_KEY not set! Must match MINT_SECRET on the server.")
    exit(1)

# Local Wallet Path
WALLET_FILE = Path(".agent/wallet/wallet.json")

def mint_and_save():
    print(f">>> Connecting to Cloud Gateway: {GATEWAY_URL}")
    
    # 1. Mint Request
    payload = {
        "amount_sats": 5000000,  # 5 Million Sats
        "identifier": f"cloud_admin_mint_{os.urandom(4).hex()}"
    }
    
    try:
        resp = requests.post(
            f"{GATEWAY_URL}/v1/admin/mint",
            json=payload,
            headers={"X-Admin-Key": ADMIN_KEY},
            timeout=5
        )
        
        if resp.status_code == 200:
            data = resp.json()
            token = data.get("access_token")
            print(">>> Mint successful. Token generated.")
            
            # 2. Save to Wallet
            WALLET_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(WALLET_FILE, 'w') as f:
                json.dump({
                    "access_token": token, 
                    "gateway": GATEWAY_URL,
                    "note": "Minted via cloud_mint.py"
                }, f)
                
            print(f">>> Token saved to {WALLET_FILE}")
            print(">>> You can now run: python wallet_client.py")
            
        else:
            print(f">>> Error: {resp.status_code} {resp.text}")
            print("   Did you set the correct ADMIN_KEY?")
            
    except Exception as e:
        print(f">>> Connection Error: {e}")

if __name__ == "__main__":
    mint_and_save()
¹*cascade08"(d4e7a325d0144b3814ef864593774f7a395132062Bfile:///c:/Users/rovie%20segubre/agent/sovereign_api/cloud_mint.py:&file:///c:/Users/rovie%20segubre/agent