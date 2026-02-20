
import requests
import json
import os

def tool(func):
    func._is_tool = True
    return func

@tool
def read_url(url: str) -> str:
    """
    Reads the content of a URL (webpage or API).
    Useful for reading documentation or instructions.
    """
    try:
        print(f"🌐 Agent Reading: {url}")
        resp = requests.get(url, timeout=10)
        return resp.text[:5000] # Limit context
    except Exception as e:
        return f"Error reading URL: {e}"

@tool
def http_request(method: str, url: str, headers: str = "{}", body: str = "{}") -> str:
    """
    Makes a generic HTTP request.
    Args:
        method: "GET" or "POST"
        url: The target URL
        headers: JSON string of headers
        body: JSON string of body payload (for POST)
    """
    try:
        header_dict = json.loads(headers)
        body_dict = json.loads(body)
        
        print(f"⚡ Agent Request: {method} {url}")
        
        if method.upper() == "GET":
            resp = requests.get(url, headers=header_dict, timeout=10)
        elif method.upper() == "POST":
            resp = requests.post(url, json=body_dict, headers=header_dict, timeout=10)
        else:
            return "Unsupported method"
            
        return f"Status: {resp.status_code}\nBody: {resp.text}"
        
    except Exception as e:
        return f"Request failed: {e}"

@tool
def save_to_env(key: str, value: str) -> str:
    """
    Saves a secret or configuration to the agent's local .env file.
    Use this to persist API keys you receive.
    """
    try:
        env_path = ".env"
        # Reading existing
        lines = []
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        
        # Updating
        new_lines = []
        found = False
        for line in lines:
            if line.startswith(f"{key}="):
                new_lines.append(f"{key}={value}\n")
                found = True
            else:
                new_lines.append(line)
        
        if not found:
            if new_lines and not new_lines[-1].endswith("\n"):
                new_lines[-1] += "\n"
            new_lines.append(f"{key}={value}\n")
            
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
            
        return f"✅ Saved {key} to configuration."
    except Exception as e:
        return f"Failed to save config: {e}"
