
import requests
import json
from pathlib import Path

# Load Token
TOKEN_PATH = Path(__file__).parent.parent / ".agent" / "secure" / "alby_token.json"

try:
    with open(TOKEN_PATH, 'r') as f:
        data = json.load(f)
        token = data.get("ALBY_ACCESS_TOKEN")
except Exception as e:
    print(f"[ERROR] Could not load token: {e}")
    exit(1)

# Verify Token against Alby API
url = "https://api.getalby.com/user/me"
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

print(f"[INFO] Testing Token against {url}...")
try:
    response = requests.get(url, headers=headers, timeout=10)
    
    if response.status_code == 200:
        user_data = response.json()
        print("[SUCCESS] Token is VALID.")
        print(f"User: {user_data.get('email', 'Unknown')}")
        print(f"Lightning Address: {user_data.get('lightning_address', 'Unknown')}")
        # print("Scopes:", user_data.get("scopes", "Unknown")) # Alby API might not return scopes here directly depending on version, but 200 OK is good.
    else:
        print(f"[FAILED] API returned {response.status_code}")
        print(response.text)

except Exception as e:
    print(f"[ERROR] Connection failed: {e}")
