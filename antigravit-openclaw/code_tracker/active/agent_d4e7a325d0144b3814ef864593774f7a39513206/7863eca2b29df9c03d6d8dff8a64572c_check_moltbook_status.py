çimport requests
import json
import pathlib

# Load creds
creds_path = pathlib.Path(__file__).parent / ".agent" / "secure" / "moltbook_credentials.json"
with open(creds_path, 'r') as f:
    creds = json.load(f)

api_key = creds["api_key"]
url = "https://www.moltbook.com/api/v1/agents/status"
headers = {
    "Authorization": f"Bearer {api_key}"
}

try:
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    print(json.dumps(response.json(), indent=2))
except Exception as e:
    print(f"Error: {e}")
    if 'response' in locals():
        print(response.text)
ç*cascade08"(d4e7a325d0144b3814ef864593774f7a395132062?file:///c:/Users/rovie%20segubre/agent/check_moltbook_status.py:&file:///c:/Users/rovie%20segubre/agent