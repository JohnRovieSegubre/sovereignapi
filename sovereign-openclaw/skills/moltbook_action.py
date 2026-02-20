
import os
import requests
from dotenv import load_dotenv

# Re-import logger if needed, or use print for simplicity in skills
try:
    from skill_loader import tool
except ImportError:
    # Creating a dummy decorator if running standalone
    def tool(func):
        func._is_tool = True
        return func

@tool
def register_moltbook_account(agent_name: str, description: str):
    """
    Registers the agent on Moltbook.
    Args:
        agent_name: The username to register (e.g. 'OpenClaw-001').
        description: A short bio for the agent.
    Returns:
        The claim_url and api_key if successful.
    """
    url = "https://www.moltbook.com/api/v1/agents/register"
    payload = {
        "name": agent_name,
        "description": description
    }
    
    try:
        print(f"🚀 Attempting registration for {agent_name}...")
        resp = requests.post(url, json=payload, timeout=20)
        
        if resp.status_code == 200:
            data = resp.json()
            agent_data = data.get("agent", {})
            api_key = agent_data.get("api_key")
            claim_url = agent_data.get("claim_url")
            
            # Persist to .env because the agent needs to remember its own key
            _save_key_to_env(api_key)
            
            return f"SUCCESS! I have registered. API Key saved. CLAIM URL: {claim_url} (Please ask my owner to verify this link)."
        elif resp.status_code == 400 and "already taken" in resp.text:
             return "Registration failed: Name already taken. Please choose another name."
        else:
            return f"Registration failed: {resp.status_code} - {resp.text}"
            
    except Exception as e:
        return f"Network error during registration: {e}"

def _save_key_to_env(api_key):
    """Internal helper to save the key to .env so the agent persists valid state."""
    if not api_key:
        return
        
    env_path = ".env" # Relative to agent execution root
    if not os.path.exists(env_path):
        env_path = "../.env" # Fallback
        
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        new_lines = []
        found = False
        for line in lines:
            if line.startswith("MOLTBOOK_API_KEY="):
                new_lines.append(f"MOLTBOOK_API_KEY={api_key}\n")
                found = True
            else:
                new_lines.append(line)
        
        if not found:
            if new_lines and not new_lines[-1].endswith("\n"):
                new_lines[-1] += "\n"
            new_lines.append(f"MOLTBOOK_API_KEY={api_key}\n")
            
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        print("💾 Automatically saved new MOLTBOOK_API_KEY to .env")
    except Exception as e:
        print(f"⚠️ Failed to save to .env: {e}")
