
import os
import sys
import json
import base64
from pathlib import Path
from dotenv import load_dotenv
from eth_account import Account
from web3 import Web3

env_path = Path("sovereign-openclaw/.env").resolve()
load_dotenv(dotenv_path=env_path, override=True)

sys.path.insert(0, os.path.abspath("sovereign-openclaw"))
from sdk.sovereign import SovereignClient

def debug_payment():
    client = SovereignClient()
    
    # 1. Check Balances
    w3 = Web3(Web3.HTTPProvider("https://sepolia.base.org")) # Base Sepolia RPC
    address = client.address
    print(f"🔍 Wallet: {address}")
    
    native_bal = w3.eth.get_balance(address)
    print(f"💰 Native ETH Balance: {native_bal} wei ({w3.from_wei(native_bal, 'ether')} ETH)")
    
    # Check USDC Balance (Base Sepolia)
    USDC_ADDR = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"
    abi = [{"constant":True,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]
    usdc = w3.eth.contract(address=USDC_ADDR, abi=abi)
    try:
        usdc_bal = usdc.functions.balanceOf(address).call()
        print(f"💰 USDC Balance: {usdc_bal} units ({usdc_bal / 1e6} USDC)")
    except Exception as e:
        print(f"⚠️ Could not check USDC: {e}")

    # 2. Trigger 402
    print("\n🚀 Sending Request...")
    url = f"{client.base_url}/chat/completions"
    headers = {"X-Sovereign-Api-Key": client.api_key}
    
    import requests
    resp = requests.post(url, json={"model": "sovereign/deepseek-r1", "messages": [{"role": "user", "content": "hi"}]}, headers=headers)
    
    if resp.status_code == 402:
        print("\n💡 402 Header Decoded:")
        b64 = resp.headers.get("payment-required")
        if b64:
            try:
                decoded = base64.b64decode(b64).decode()
                print(json.dumps(json.loads(decoded), indent=2))
            except:
                print(f"Raw: {b64}")

if __name__ == "__main__":
    debug_payment()
