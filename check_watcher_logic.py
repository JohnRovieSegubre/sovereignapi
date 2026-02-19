
import os
import json
import sys
from web3 import Web3

# Config
POLYGON_RPC = os.getenv("POLYGON_RPC", "https://polygon-rpc.com") # Use container default if env missing
USDC_CONTRACT_ADDRESS = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"
MY_WALLET_ADDRESS = "0xC8Dc2795352cdedEF3a11f1fC9E360D85C5aAC4d"
TARGET_BLOCK = 82950665
TARGET_TX = "0xc9d60fd3a7db854d20761064e1bdb7dcf3071ca934bb0cee744191816ee05044"

# ABI
ERC20_ABI = json.loads('[{"anonymous":false,"inputs":[{"indexed":true,"internalType":"address","name":"from","type":"address"},{"indexed":true,"internalType":"address","name":"to","type":"address"},{"indexed":false,"internalType":"uint256","name":"value","type":"uint256"}],"name":"Transfer","type":"event"}]')

def check_logic():
    print(f"🔌 Connecting to {POLYGON_RPC}...")
    w3 = Web3(Web3.HTTPProvider(POLYGON_RPC))
    if not w3.is_connected():
        print("❌ Failed to connect.")
        return

    contract = w3.eth.contract(address=USDC_CONTRACT_ADDRESS, abi=ERC20_ABI)
    
    print(f"🔍 querying get_logs for block {TARGET_BLOCK}...")
    try:
        logs = contract.events.Transfer.get_logs(
            fromBlock=TARGET_BLOCK,
            toBlock=TARGET_BLOCK
        )
        print(f"✅ Found {len(logs)} Transfer events in block.")
        
        found = False
        for i, log in enumerate(logs):
            tx_hash = log['transactionHash'].hex()
            to_addr = log['args']['to']
            
            if tx_hash.lower() == TARGET_TX.lower():
                print(f"   🎯 Found Target TX Log #{i}")
                print(f"      To: {to_addr}")
                print(f"      Value: {log['args']['value']}")
                
                if to_addr.lower() == MY_WALLET_ADDRESS.lower():
                    print("      ✅ Matches Wallet Address!")
                    found = True
                else:
                    print(f"      ❌ Mismatch Address: {to_addr} != {MY_WALLET_ADDRESS}")

        if found:
            print("\n✅ Logic Verification: SUCCESS. web3.py sees the log.")
        else:
            print("\n❌ Logic Verification: FAILED. Log not found in get_logs output.")

    except Exception as e:
        print(f"❌ Error in get_logs: {e}")

if __name__ == "__main__":
    check_logic()
