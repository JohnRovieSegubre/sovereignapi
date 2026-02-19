�import requests
import json
import os
from pathlib import Path

# --- CONFIGURATION (EDIT ME) ---
CLOUD_IP = "34.55.175.24"
GATEWAY_URL = f"http://{CLOUD_IP}:8000"
ADMIN_KEY = "your_super_secret"  # MUST MATCH docker-compose.yml on server!

# Local Wallet Path
WALLET_FILE = Path(".agent/wallet/wallet.json")

def mint_and_save():
    print(f"☁️  Connecting to Cloud Gateway: {GATEWAY_URL}")
    
    # 1. Mint Request
    payload = {
        "amount_sats": 5000000,  # 5 Million Sats (Rich!)
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
            print(f"✅ [MINT SUCCESS] Generated Cloud Token.")
            
            # 2. Save to Wallet
            WALLET_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(WALLET_FILE, 'w') as f:
                json.dump({
                    "access_token": token, 
                    "gateway": GATEWAY_URL,
                    "note": "Minted via cloud_mint.py"
                }, f)
                
            print(f"💾 [SAVED] Token written to {WALLET_FILE}")
            print("\n🚀 You can now run: python wallet_client.py")
            
        else:
            print(f"❌ [ERROR] Server said: {resp.status_code} {resp.text}")
            print("   Did you set the correct ADMIN_KEY in this script?")
            
    except Exception as e:
        print(f"🔥 [CONNECTION ERROR] {e}")

if __name__ == "__main__":
    mint_and_save()
�*cascade08"(d4e7a325d0144b3814ef864593774f7a3951320624file:///c:/Users/rovie%20segubre/agent/cloud_mint.py:&file:///c:/Users/rovie%20segubre/agent