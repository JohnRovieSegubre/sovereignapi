–import requests
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
        print(f"ğŸ¦ {sub['name']} ({sub['slug']}) - {sub['description']}")
except Exception as e:
    print(f"âŒ Error: {e}")
    if 'response' in locals():
        print(response.text)
 *cascade08®*cascade08®· *cascade08·¹*cascade08¹º *cascade08º¼*cascade08¼¾ *cascade08¾¿*cascade08¿À *cascade08ÀÎ*cascade08ÎÏ *cascade08Ï×*cascade08×İ *cascade08İê*cascade08êì *cascade08ìğ*cascade08ğú *cascade08úû*cascade08ûü *cascade08üş*cascade08şÿ *cascade08ÿƒ*cascade08ƒ„ *cascade08„*cascade08º *cascade08º½*cascade08½– *cascade08"(d4e7a325d0144b3814ef864593774f7a395132062@file:///c:/Users/rovie%20segubre/agent/list_moltbook_submolts.py:&file:///c:/Users/rovie%20segubre/agent