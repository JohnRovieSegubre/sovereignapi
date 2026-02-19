Åimport requests
import json
import pathlib

# Load creds
creds_path = pathlib.Path(__file__).parent / ".agent" / "secure" / "moltbook_credentials.json"
with open(creds_path, 'r') as f:
    creds = json.load(f)

api_key = creds["api_key"]
headers = {"Authorization": f"Bearer {api_key}"}

print("Debugging Moltbook API...")
url = f"https://www.moltbook.com/api/v1/posts?sort=new&limit=5"
try:
    response = requests.get(url, headers=headers)
    print(f"Status Code: {response.status_code}")
    
    debug_file = "moltbook_debug.json"
    with open(debug_file, 'w', encoding='utf-8') as f:
        json.dump(response.json(), f, indent=2)
    
    print(f"Raw response dumped to {debug_file}")

except Exception as e:
    print(f"Error: {e}")
Å*cascade08"(d4e7a325d0144b3814ef864593774f7a395132062<file:///c:/Users/rovie%20segubre/agent/debug_moltbook_raw.py:&file:///c:/Users/rovie%20segubre/agent