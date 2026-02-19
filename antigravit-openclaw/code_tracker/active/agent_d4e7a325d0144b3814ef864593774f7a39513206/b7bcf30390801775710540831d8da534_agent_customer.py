õ"""
Sovereign SDK - Test Agent
==========================
A demo AI agent that uses the Sovereign SDK to pay for intelligence.

This script:
1. Initializes a SovereignClient with a private key
2. Attempts to chat with the Gateway
3. If 402 (Payment Required), it auto-pays via Polygon
4. Claims the token from the Mailbox
5. Retries the request

IMPORTANT: For real testing, you need a wallet with:
- MATIC (for gas fees)
- USDC (to pay for intelligence)
"""

import os
import sys

# Add parent directory to path for local import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sdk.sovereign import SovereignClient

# --- CONFIGURATION ---
# Cloud Gateway URL (Your GCloud Server)
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://34.55.175.24:8000/v1")

# Gateway Wallet (Where the SDK sends USDC - must match polygon_watcher.py)
GATEWAY_WALLET = os.getenv("GATEWAY_WALLET", "0xC8Dc2795352cdedEF3a11f1fC9E360D85C5aAC4d")

# Your Private Key (NEVER HARDCODE IN PRODUCTION!)
# For testing, you can use a throwaway key with small amounts of MATIC/USDC
AGENT_PRIVATE_KEY = os.getenv("AGENT_PRIVATE_KEY")

# --- MAIN ---
def main():
    print("=" * 60)
    print("  SOVEREIGN SDK - Agent Customer Demo")
    print("=" * 60)
    
    # Check for Private Key
    if not AGENT_PRIVATE_KEY:
        print("\n‚ùå ERROR: AGENT_PRIVATE_KEY not set!")
        print("\nTo run this demo, set your private key as an environment variable:")
        print("  PowerShell: $env:AGENT_PRIVATE_KEY='0x...'")
        print("  CMD:        set AGENT_PRIVATE_KEY=0x...")
        print("\n‚ö†Ô∏è  WARNING: Use a throwaway wallet with small amounts for testing!")
        return

    # Initialize Client
    client = SovereignClient(
        private_key=AGENT_PRIVATE_KEY,
        base_url=GATEWAY_URL,
        gateway_wallet=GATEWAY_WALLET
    )

    print()
    print("-" * 60)
    print("  MISSION: Get an answer to 'What is 2 + 2?'")
    print("-" * 60)
    print()

    # Attempt to chat
    response = client.chat.completions.create(
        model="sovereign/deepseek-r1",  # Cheapest model (5 sats)
        messages=[{"role": "user", "content": "What is 2 + 2?"}]
    )

    # Display Result
    print()
    print("=" * 60)
    if "error" in response:
        print(f"‚ùå FAILED: {response}")
    else:
        # Extract the answer
        try:
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            print(f"‚úÖ AI RESPONSE: {content}")
        except:
            print(f"‚úÖ RAW RESPONSE: {response}")
    print("=" * 60)


if __name__ == "__main__":
    main()
Ÿ *cascade08Ÿ‚*cascade08‚õ *cascade08"(d4e7a325d0144b3814ef864593774f7a395132062<file:///c:/Users/rovie%20segubre/agent/sdk/agent_customer.py:&file:///c:/Users/rovie%20segubre/agent