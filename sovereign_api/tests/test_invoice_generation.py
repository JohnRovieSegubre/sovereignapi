
import os
import json
import httpx
import asyncio
from pathlib import Path

# Load Token
TOKEN_PATH = Path(__file__).parent.parent / ".agent" / "secure" / "alby_token.json"

async def test_invoice():
    try:
        with open(TOKEN_PATH, 'r') as f:
            token = json.load(f).get("ALBY_ACCESS_TOKEN")
    except Exception as e:
        print(f"[ERROR] Could not load token: {e}")
        return

    url = "https://api.getalby.com/invoices"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "amount": 10, # 10 sats
        "description": "Test Invoice from Antigravity"
    }

    print(f"[INFO] Attempting to create invoice with token: {token[:6]}...")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers)
        
    print(f"[INFO] Status Code: {response.status_code}")
    print(f"[INFO] Response: {response.text}")

    if response.status_code == 201:
        print("✅ SUCCESS! Invoice created.")
        print(f"Payment Request: {response.json().get('payment_request')}")
    else:
        print("❌ FAILED. Please check Alby Dashboard connections.")

if __name__ == "__main__":
    asyncio.run(test_invoice())
