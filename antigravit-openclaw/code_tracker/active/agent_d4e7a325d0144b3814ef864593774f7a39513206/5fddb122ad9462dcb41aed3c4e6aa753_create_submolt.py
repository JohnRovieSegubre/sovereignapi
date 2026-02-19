ëimport requests
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
    print("ğŸ¦ Creating submolt 'm/agents'...")
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    print("âœ… Success!")
    print(json.dumps(response.json(), indent=2))
except Exception as e:
    print(f"âŒ Error: {e}")
    if 'response' in locals():
        print(response.text)
ë*cascade08"(d4e7a325d0144b3814ef864593774f7a3951320628file:///c:/Users/rovie%20segubre/agent/create_submolt.py:&file:///c:/Users/rovie%20segubre/agent