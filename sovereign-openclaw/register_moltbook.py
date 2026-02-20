
import os
import requests
import json
from pathlib import Path
from dotenv import load_dotenv

# Load Env
env_path = Path(".env").resolve()
load_dotenv(dotenv_path=env_path, override=True)

AGENT_NAME = os.getenv("AGENT_NAME", "SovereignAgent")
MOLTBOOK_API_KEY = os.getenv("MOLTBOOK_API_KEY")

def register():
    if MOLTBOOK_API_KEY:
        print(f"✅ Agent '{AGENT_NAME}' is already configured with a Moltbook API Key.")
        print("   Skipping registration.")
        return

    print(f"🚀 Registering agent '{AGENT_NAME}' on Moltbook...")
    
    url = "https://www.moltbook.com/api/v1/agents/register"
    payload = {
        "name": AGENT_NAME,
        "description": "An autonomous AI agent running on Sovereign API infrastructure."
    }
    
    try:
        resp = requests.post(url, json=payload, timeout=20)
        
        if resp.status_code == 200:
            data = resp.json()
            agent_data = data.get("agent", {})
            new_key = agent_data.get("api_key")
            claim_url = agent_data.get("claim_url")
            
            print("\n🎉 Registration Successful!")
            print(f"🔑 New API Key: {new_key[:10]}...")
            print(f"🔗 Claim URL:   {claim_url}")
            print("\n🛑 ACTION REQUIRED: You must visit the Claim URL to activate this agent!")
            
            # Save to .env
            update_env(env_path, "MOLTBOOK_API_KEY", new_key)
            
        else:
            print(f"❌ Registration Failed: {resp.status_code} - {resp.text}")
            
    except Exception as e:
        print(f"❌ Network Error: {e}")

def update_env(path, key, value):
    # Simple append/replace
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    new_lines = []
    found = False
    for line in lines:
        if line.startswith(f"{key}="):
            new_lines.append(f"{key}={value}\n")
            found = True
        else:
            new_lines.append(line)
            
    if not found:
        # Ensure newline before appending if missing
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] += "\n"
        new_lines.append(f"{key}={value}\n")
        
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    print(f"💾 Updated {path} with new credentials.")

if __name__ == "__main__":
    register()
