import os
import asyncio
from dotenv import load_dotenv
from sovereign_openclaw.sdk.sovereign import SovereignClient

# Load env variables (API Key, Gateway URL, etc.)
load_dotenv(dotenv_path="sovereign-openclaw/.env")

async def say_hi():
    print("🤖 Waking up Sovereign Client...")
    
    # Initialize client
    client = SovereignClient(
        gateway_url=os.getenv("GATEWAY_URL"),
        api_key=os.getenv("SOVEREIGN_API_KEY"),
        private_key=os.getenv("AGENT_PRIVATE_KEY")
    )
    
    # Check if we have fuel (should be yes from previous run)
    fuel = client.verify_token()
    print(f"⛽ Fuel Status: {fuel} sats")
    
    if not fuel:
        print("❌ No fuel! Run the main agent loop to refuel first.")
        return

    # Send a prompt
    prompt = "Hi! Are you ready for missions?"
    print(f"\n🗣️  Sending: '{prompt}'")
    
    try:
        response = client.chat(prompt, model="sovereign/llama3-70b") # Using cheaper model for test
        print(f"\n🧠 Agent Replied:\n{'-'*20}\n{response}\n{'-'*20}")
    except Exception as e:
        print(f"❌ Error talking to gateway: {e}")

if __name__ == "__main__":
    asyncio.run(say_hi())
