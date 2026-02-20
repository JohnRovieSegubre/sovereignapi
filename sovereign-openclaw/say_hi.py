
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure we can import sdk
agent_dir = Path(__file__).parent
sys.path.append(str(agent_dir))
sys.path.append(str(agent_dir.parent))  # Add root agent dir

# Load env variables
load_dotenv(agent_dir / ".env")

# Default to Local Gateway if not set
if "GATEWAY_URL" not in os.environ:
    os.environ["GATEWAY_URL"] = "http://localhost:8000/v1"

from sdk.sovereign import SovereignClient
import sdk
print(f"DEBUG: Loaded SDK from {sdk.__file__}")
print(f"DEBUG: Client Module: {SovereignClient.__module__}")

def say_hi():
    print("🤖 Waking up Sovereign Client (x402 Edition)...")
    
    # Initialize client
    client = SovereignClient(api_key=os.getenv("SOVEREIGN_API_KEY"))
    
    # 1. Ensure Fuel
    print("\n⛽ Checking Fuel...")
    token = client.refuel_balance()
    if token:
        print("✅ Refuel/Token Check Passed.")
    else:
        print("❌ Failed to get token.")
        return

    # 2. Say Hi
    prompt = "Hi! Are you ready for missions?"
    print(f"\n🗣️  Sending: '{prompt}'")
    
    try:
        response = client.chat.completions.create(
            model="sovereign/deepseek-r1", 
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Handle dict response (new SDK behavior)
        if isinstance(response, dict) and "choices" in response:
            content = response["choices"][0]["message"]["content"]
            print(f"\n🧠 Agent Replied:\n{'-'*20}\n{content}\n{'-'*20}")
        elif isinstance(response, dict) and "error" in response:
            print(f"❌ Gateway Error: {response['error']}")
            if "402" in str(response):
                print("   (Note: 402 from OpenRouter is expected if credits are low)")
        else:
            print(f"🤔 Unexpected response format: {response}")
            
    except Exception as e:
        print(f"❌ Error talking to gateway: {e}")

if __name__ == "__main__":
    say_hi()
