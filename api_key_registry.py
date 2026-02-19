"""
API Key Registry - Sovereign Intelligence License Manager
==========================================================
Manages persistent API Keys (Licenses) for registered agents.

Storage: .agent/data/api_keys.json
Format: sk-sov-{random32}

CLI Usage:
    python api_key_registry.py create "Agent_Name"     # Generate new key
    python api_key_registry.py list                    # Show all keys
    python api_key_registry.py revoke sk-sov-xxx       # Disable a key
    python api_key_registry.py validate sk-sov-xxx    # Check if valid

Import Usage:
    from api_key_registry import validate_key, get_agent_name
    
    if validate_key("sk-sov-xxx"):
        agent = get_agent_name("sk-sov-xxx")
"""

import json
import secrets
import sys
import os
from pathlib import Path
from datetime import datetime

# Storage Location
DATA_DIR = Path(__file__).parent / ".agent" / "data"
REGISTRY_FILE = DATA_DIR / "api_keys.json"


def _load_registry():
    """Load the API key registry from disk."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if REGISTRY_FILE.exists():
        try:
            with open(REGISTRY_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}


def _save_registry(registry):
    """Save the API key registry to disk."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY_FILE, 'w') as f:
        json.dump(registry, f, indent=2, default=str)


def generate_key():
    """Generate a new API key in sk-sov-{random32} format."""
    return f"sk-sov-{secrets.token_hex(16)}"


def create_key(agent_name, description=""):
    """
    Create a new API key for an agent.
    
    Returns:
        tuple: (api_key, success_message)
    """
    registry = _load_registry()
    
    # Check if agent already exists
    for key, data in registry.items():
        if data.get("agent_name") == agent_name and data.get("active", True):
            return None, f"Agent '{agent_name}' already has an active key."
    
    # Generate new key
    api_key = generate_key()
    
    registry[api_key] = {
        "agent_name": agent_name,
        "description": description,
        "created_at": datetime.utcnow().isoformat(),
        "active": True,
        "usage_count": 0
    }
    
    _save_registry(registry)
    return api_key, f"Created key for '{agent_name}'"


def validate_key(api_key):
    """
    Check if an API key is valid and active.
    
    Returns:
        bool: True if valid and active, False otherwise
    """
    if not api_key:
        return False
    
    # Handle "Bearer" prefix
    if api_key.startswith("Bearer "):
        api_key = api_key[7:]
    
    registry = _load_registry()
    
    if api_key not in registry:
        return False
    
    return registry[api_key].get("active", False)


def get_agent_name(api_key):
    """
    Get the agent name associated with an API key.
    
    Returns:
        str or None: Agent name if found, None otherwise
    """
    if api_key and api_key.startswith("Bearer "):
        api_key = api_key[7:]
    
    registry = _load_registry()
    
    if api_key in registry:
        return registry[api_key].get("agent_name")
    return None


def increment_usage(api_key):
    """Increment the usage counter for an API key."""
    if api_key and api_key.startswith("Bearer "):
        api_key = api_key[7:]
    
    registry = _load_registry()
    
    if api_key in registry:
        registry[api_key]["usage_count"] = registry[api_key].get("usage_count", 0) + 1
        registry[api_key]["last_used"] = datetime.utcnow().isoformat()
        _save_registry(registry)


def revoke_key(api_key):
    """
    Revoke (deactivate) an API key.
    
    Returns:
        tuple: (success, message)
    """
    registry = _load_registry()
    
    if api_key not in registry:
        return False, f"Key not found: {api_key[:20]}..."
    
    registry[api_key]["active"] = False
    registry[api_key]["revoked_at"] = datetime.utcnow().isoformat()
    _save_registry(registry)
    
    agent = registry[api_key].get("agent_name", "Unknown")
    return True, f"Revoked key for agent '{agent}'"


def list_keys():
    """
    List all registered API keys.
    
    Returns:
        list: List of key info dictionaries
    """
    registry = _load_registry()
    
    result = []
    for key, data in registry.items():
        result.append({
            "key": f"{key[:12]}...{key[-4:]}",  # Masked for security
            "full_key": key,
            "agent_name": data.get("agent_name"),
            "active": data.get("active", True),
            "usage_count": data.get("usage_count", 0),
            "created_at": data.get("created_at")
        })
    
    return result


# --- CLI Interface ---
def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python api_key_registry.py create <agent_name> [description]")
        print("  python api_key_registry.py list")
        print("  python api_key_registry.py revoke <api_key>")
        print("  python api_key_registry.py validate <api_key>")
        return

    command = sys.argv[1].lower()

    if command == "create":
        if len(sys.argv) < 3:
            print("Error: Agent name required")
            return
        
        agent_name = sys.argv[2]
        description = sys.argv[3] if len(sys.argv) > 3 else ""
        
        api_key, message = create_key(agent_name, description)
        
        if api_key:
            print(f"✅ {message}")
            print(f"=" * 60)
            print(f"🔑 API KEY: {api_key}")
            print(f"=" * 60)
            print("⚠️  Store this key securely. It will not be shown again in full.")
        else:
            print(f"❌ {message}")

    elif command == "list":
        keys = list_keys()
        
        if not keys:
            print("No API keys registered.")
            return
        
        print(f"{'Agent':<20} {'Key (Masked)':<25} {'Active':<8} {'Uses':<6}")
        print("-" * 65)
        
        for k in keys:
            status = "✅" if k["active"] else "❌"
            print(f"{k['agent_name']:<20} {k['key']:<25} {status:<8} {k['usage_count']:<6}")

    elif command == "revoke":
        if len(sys.argv) < 3:
            print("Error: API key required")
            return
        
        api_key = sys.argv[2]
        success, message = revoke_key(api_key)
        
        if success:
            print(f"✅ {message}")
        else:
            print(f"❌ {message}")

    elif command == "validate":
        if len(sys.argv) < 3:
            print("Error: API key required")
            return
        
        api_key = sys.argv[2]
        is_valid = validate_key(api_key)
        
        if is_valid:
            agent = get_agent_name(api_key)
            print(f"✅ Valid key for agent: {agent}")
        else:
            print("❌ Invalid or revoked key")

    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
