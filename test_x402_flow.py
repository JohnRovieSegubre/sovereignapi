"""
test_x402_flow.py — Local End-to-End x402 Payment Test
=======================================================
Tests the full flow:
  1. Check agent wallet has Base Sepolia USDC
  2. Start gateway server (or connect to existing)
  3. Send request → get 402 → auto-pay via x402 → get 200

Usage:
  python test_x402_flow.py              # Full test (needs gateway running)
  python test_x402_flow.py --check-only # Just check wallet balance
  python test_x402_flow.py --info-only  # Just hit /v1/x402/info endpoint
"""

import os
import sys
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load agent env
agent_env = Path(__file__).parent / "sovereign-openclaw" / ".env"
if agent_env.exists():
    load_dotenv(agent_env)
    print(f"✅ Loaded agent config from {agent_env}")

# Load gateway env (for x402 config)
gateway_env = Path(__file__).parent / ".env"
if gateway_env.exists():
    load_dotenv(gateway_env, override=False)

# --- CONFIG ---
AGENT_PRIVATE_KEY = os.getenv("AGENT_PRIVATE_KEY")
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000/v1")
API_KEY = os.getenv("SOVEREIGN_API_KEY")

# Base Sepolia USDC contract
BASE_SEPOLIA_USDC = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"
BASE_SEPOLIA_RPC = "https://base-sepolia.g.alchemy.com/v2/S__e1JUkM03zL4EonOpfV"
BASE_SEPOLIA_CHAIN_ID = 84532

# Minimal ERC20 ABI (balanceOf only)
BALANCE_ABI = [{"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"}]


def check_wallet():
    """Check agent wallet address and Base Sepolia USDC balance."""
    if not AGENT_PRIVATE_KEY:
        print("❌ AGENT_PRIVATE_KEY not set. Check sovereign-openclaw/.env")
        return None, 0

    from eth_account import Account
    from web3 import Web3

    account = Account.from_key(AGENT_PRIVATE_KEY)
    address = account.address
    print(f"🔑 Agent Wallet: {address}")

    # Check Base Sepolia ETH balance (for gas)
    w3 = Web3(Web3.HTTPProvider(BASE_SEPOLIA_RPC))
    if not w3.is_connected():
        print(f"⚠️  Cannot connect to Base Sepolia RPC: {BASE_SEPOLIA_RPC}")
        return address, 0

    eth_balance = w3.eth.get_balance(address)
    eth_formatted = w3.from_wei(eth_balance, 'ether')
    print(f"⛽ Base Sepolia ETH: {eth_formatted}")

    # Check USDC balance
    usdc = w3.eth.contract(address=BASE_SEPOLIA_USDC, abi=BALANCE_ABI)
    try:
        usdc_raw = usdc.functions.balanceOf(address).call()
        usdc_formatted = usdc_raw / 1e6
        print(f"💰 Base Sepolia USDC: {usdc_formatted}")
    except Exception as e:
        print(f"⚠️  Could not read USDC balance: {e}")
        usdc_formatted = 0

    if usdc_formatted < 0.001:
        print()
        print("=" * 60)
        print("⚠️  INSUFFICIENT USDC FOR x402 TEST")
        print("=" * 60)
        print(f"   You need at least 0.001 USDC on Base Sepolia.")
        print(f"   Agent wallet: {address}")
        print()
        print("   Option 1: Circle Faucet (20 USDC, free)")
        print(f"   → https://faucet.circle.com/  (select Base Sepolia)")
        print(f"   → Paste address: {address}")
        print()
        print("   Option 2: CDP Faucet (1 USDC, free)")
        print(f"   → https://portal.cdp.coinbase.com/faucet")
        print(f"   → Select Base Sepolia, paste address: {address}")
        print("=" * 60)

    if eth_balance == 0:
        print()
        print("⚠️  NO ETH FOR GAS — You also need Base Sepolia ETH.")
        print(f"   → https://www.alchemy.com/faucets/base-sepolia")
        print(f"   → Paste address: {address}")

    return address, usdc_formatted


def check_x402_info():
    """Hit the /v1/x402/info endpoint to verify gateway x402 config."""
    url = GATEWAY_URL.rstrip('/').replace('/v1', '') + '/v1/x402/info'
    print(f"\n📡 Checking gateway x402 info: {url}")

    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            info = resp.json()
            print(f"   x402 Enabled: {info.get('x402_enabled')}")
            print(f"   Network:      {info.get('supported_networks')}")
            print(f"   Price:        {info.get('price')}")
            print(f"   Pay To:       {info.get('pay_to')}")
            print(f"   Facilitator:  {info.get('facilitator')}")
            return info
        else:
            print(f"   ❌ Got {resp.status_code}: {resp.text}")
            return None
    except requests.exceptions.ConnectionError:
        print(f"   ❌ Cannot connect to gateway at {url}")
        print(f"   → Is the gateway running? Try: python gateway_server.py")
        return None
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None


def test_x402_payment(skip_wallet=False):
    """Full x402 payment test: send request, get 402, auto-pay, get 200."""
    print("\n" + "=" * 60)
    print("🧪 FULL x402 PAYMENT TEST")
    print("=" * 60)

    # Step 1: Check wallet
    if not skip_wallet:
        address, usdc_balance = check_wallet()
        if not address:
            return False
        if usdc_balance < 0.001:
            print("\n❌ Cannot proceed: insufficient USDC. Fund wallet first.")
            return False
    else:
        print("⚠️  Skipping wallet check (assuming funded)...")

    # Step 2: Check gateway
    info = check_x402_info()
    if not info or not info.get('x402_enabled'):
        print("\n❌ Cannot proceed: gateway x402 not enabled.")
        return False

    # Step 3: Try x402 auto-pay
    print("\n🚀 Sending chat request (expect 402 → auto-pay → 200)...")

    try:
        from x402 import x402ClientSync
        from x402.http.clients import x402_requests
        from x402.mechanisms.evm import EthAccountSigner
        from x402.mechanisms.evm.exact.register import register_exact_evm_client
        from eth_account import Account
    except ImportError:
        print("❌ x402 SDK not installed. Run: pip install 'x402[requests]'")
        return False

    # Create x402-aware session
    client = x402ClientSync()
    account = Account.from_key(AGENT_PRIVATE_KEY)
    register_exact_evm_client(client, EthAccountSigner(account))
    session = x402_requests(client)

    # Send the request
    url = f"{GATEWAY_URL.rstrip('/')}/chat/completions"
    payload = {
        "model": "sovereign/deepseek-r1",
        "messages": [{"role": "user", "content": "Say 'x402 payment works!' in exactly those words."}]
    }
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["X-Sovereign-Api-Key"] = API_KEY

    try:
        print(f"   → POST {url}")
        resp = session.post(url, json=payload, headers=headers, timeout=120)

        print(f"   ← Status: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            print(f"\n✅ x402 PAYMENT TEST PASSED!")
            print(f"   Response: {content[:200]}")

            # Check for payment receipt
            receipt = resp.headers.get("PAYMENT-RESPONSE")
            if receipt:
                print(f"   🧾 Payment Receipt: {receipt[:80]}...")

            return True
        elif resp.status_code == 402:
            print(f"\n❌ Still got 402 — x402 auto-pay did not work.")
            print(f"   Headers: {dict(resp.headers)}")
            print(f"   Body: {resp.text[:500]}")
            return False
        else:
            print(f"\n⚠️  Unexpected status: {resp.status_code}")
            print(f"   Body: {resp.text[:500]}")
            return False

    except Exception as e:
        print(f"\n❌ Request failed: {e}")
        return False



def test_topup_flow():
    """Test x402 refueling (buying a macaroon)."""
    print("\n" + "-" * 60)
    print("⛽ TESTING x402 REFUELING (Topup Endpoint)")
    print("-" * 60)

    url = f"{GATEWAY_URL.rstrip('/')}/balance/topup"
    print(f"🚀 Requesting topup ($1.00)...")
    print(f"   → POST {url}")

    from x402 import x402ClientSync
    from x402.http.clients import x402_requests
    from x402.mechanisms.evm import EthAccountSigner
    from x402.mechanisms.evm.exact.register import register_exact_evm_client
    from eth_account import Account

    client = x402ClientSync()
    account = Account.from_key(AGENT_PRIVATE_KEY)
    register_exact_evm_client(client, EthAccountSigner(account))
    session = x402_requests(client)

    try:
        resp = session.post(url, json={}, headers={"Content-Type": "application/json"}, timeout=120)
        
        print(f"   ← Status: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            token = data.get("token")
            credits = data.get("credits_sats")
            print(f"\n✅ REFUEL SUCCESSFUL!")
            print(f"   Credits: {credits} sats")
            print(f"   Token:   {token[:20]}...")
            return True
        else:
            print(f"\n❌ Refuel Failed: {resp.status_code}")
            print(f"   Body: {resp.text[:500]}")
            return False
            
    except Exception as e:
        print(f"\n❌ Refuel Request Failed: {e}")
        return False


def main():
    print("=" * 60)
    print("🔬 Sovereign x402 Payment Test Suite")
    print("=" * 60)
    print(f"   Gateway: {GATEWAY_URL}")
    print(f"   API Key: {API_KEY[:15]}..." if API_KEY else "   API Key: Not Set")
    print()

    args = sys.argv[1:]

    skip_check = "--skip-check" in args

    if "--check-only" in args:
        check_wallet()
    elif "--info-only" in args:
        check_x402_info()
    else:
        # Run both tests
        if not skip_check:
            address, usdc = check_wallet()
            if usdc < 0.001:
                print("\n❌ Cannot proceed: insufficient USDC. Fund wallet first.")
                s1 = False
            else:
                s1 = test_x402_payment()
        else:
            print("⚠️  Skipping wallet check...")
            s1 = test_x402_payment(skip_wallet=True)

        s2 = test_topup_flow()
        
        print("\n" + "=" * 60)
        if s1 and s2:
            print("🎉 ALL WORKFLOWS PASSED (Chat + Refuel)!")
        else:
            print("💔 SOME TESTS FAILED.")
        print("=" * 60)


if __name__ == "__main__":
    main()
