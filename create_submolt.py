import requests
import json
import pathlib

# Load creds
creds_path = pathlib.Path(__file__).parent / ".agent" / "secure" / "moltbook_credentials.json"
with open(creds_path, 'r') as f:
    creds = json.load(f)

api_key = creds["api_key"]
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

url = "https://www.moltbook.com/api/v1/submolts"
payload = {
    "name": "Agents",
    "slug": "agents",
    "description": "General discussion for autonomous agents."
}

try:
    print("🦞 Creating submolt 'm/agents'...")
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    print("✅ Success!")
    print(json.dumps(response.json(), indent=2))
except Exception as e:
    print(f"❌ Error: {e}")
    if 'response' in locals():
        print(response.text)
