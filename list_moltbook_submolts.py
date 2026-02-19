import requests
import json
import pathlib

# Load creds
creds_path = pathlib.Path(__file__).parent / ".agent" / "secure" / "moltbook_credentials.json"
with open(creds_path, 'r') as f:
    creds = json.load(f)

api_key = creds["api_key"]
headers = {"Authorization": f"Bearer {api_key}"}

url = "https://www.moltbook.com/api/v1/submolts"

try:
    response = requests.get(url, headers=headers)
    print(f"Status: {response.status_code}")
    if response.status_code != 200:
        print(response.text)
    
    data = response.json().get("data", [])
    if not data:
        print("No submolts found in response.")
        print(json.dumps(response.json(), indent=2))
        
    for sub in data:
        print(f"🦞 {sub['name']} ({sub['slug']}) - {sub['description']}")
except Exception as e:
    print(f"❌ Error: {e}")
    if 'response' in locals():
        print(response.text)
