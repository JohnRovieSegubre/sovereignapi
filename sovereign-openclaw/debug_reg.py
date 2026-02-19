import requests
import json

import requests
import json
import uuid

name = f"sovereign-{str(uuid.uuid4())[:8]}"
url = "https://api.sovereign-api.com/v1/register"
payload = {"name": name}
headers = {"Content-Type": "application/json"}

print(f"Testing registration with: {payload}")
try:
    response = requests.post(url, json=payload, headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
